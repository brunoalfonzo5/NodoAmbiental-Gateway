"""API de demostración del Nodo Ambiental: MQTT procesado -> SQLite -> web.

No modifica el gateway ni el normalizador MQTT existentes.
Arrancar desde la raíz de NodoAmbiental-Gateway:
    python src/api_server.py
"""

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
load_dotenv()  # permite ejecutarlo desde otro directorio

MQTT_HOST = os.getenv("MQTT_HOST", "192.168.88.36")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TOPIC_PROCESSED = os.getenv("MQTT_TOPIC_PROCESSED", "nodoambiental/procesado/+")
API_HOST = os.getenv("API_HOST", "192.168.88.36")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_DB_PATH = Path(os.getenv("API_DB_PATH", str(ROOT / "data" / "nodos.sqlite3")))
OFFLINE_SECONDS = int(os.getenv("NODE_OFFLINE_SECONDS", "300"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("nodoambiental.api")
app = Flask(__name__)
connected = threading.Event()


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db():
    con = sqlite3.connect(API_DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    API_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("""CREATE TABLE IF NOT EXISTS nodos (
            id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            primero_visto TEXT NOT NULL,
            ultimo_visto TEXT NOT NULL,
            ultimo_json TEXT NOT NULL,
            lat REAL,
            lon REAL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS lecturas (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            nodo_id TEXT NOT NULL,
            recibido_en TEXT NOT NULL,
            payload TEXT NOT NULL
        )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_lecturas_nodo ON lecturas(nodo_id, seq)")


def ingest(payload):
    """Guarda mensajes emitidos por el normalizador, sin inventar mediciones."""
    if not isinstance(payload, dict):
        return False
    node_id = payload.get("node_id")
    measurements = payload.get("measurements")
    if not isinstance(node_id, str) or not node_id or not isinstance(measurements, dict):
        return False
    received = utc_now()
    payload_json = json.dumps(payload, ensure_ascii=False)
    name = f"Nodo {node_id.lstrip('!')[-8:]}"
    with db() as con:
        con.execute("""INSERT INTO nodos(id, nombre, primero_visto, ultimo_visto, ultimo_json)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(id) DO UPDATE SET
                       ultimo_visto=excluded.ultimo_visto, ultimo_json=excluded.ultimo_json""",
                    (node_id, name, received, received, payload_json))
        con.execute("INSERT INTO lecturas(nodo_id, recibido_en, payload) VALUES (?, ?, ?)",
                    (node_id, received, payload_json))
    log.info("Medición guardada: %s", node_id)
    return True


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        connected.set()
        client.subscribe(MQTT_TOPIC_PROCESSED, qos=1)
        log.info("MQTT conectado; escuchando %s", MQTT_TOPIC_PROCESSED)
    else:
        connected.clear()
        log.error("Error conectando a MQTT: %s", reason_code)


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    connected.clear()
    log.warning("MQTT desconectado: %s (reconexión automática)", reason_code)


def on_message(client, userdata, message):
    try:
        item = json.loads(message.payload.decode("utf-8"))
        if not ingest(item):
            log.warning("Mensaje ignorado, formato no reconocido: %s", message.topic)
    except (ValueError, UnicodeError, sqlite3.Error):
        log.exception("No se pudo guardar mensaje de %s", message.topic)


def mqtt_start():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="nodoambiental-web-api")
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=2, max_delay=30)
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()
    return client


def as_number_or_none(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def build_node(row):
    payload = json.loads(row["ultimo_json"])
    m = payload.get("measurements", {})
    last = datetime.fromisoformat(row["ultimo_visto"])
    age_s = (datetime.now(timezone.utc) - last).total_seconds()
    online = age_s <= OFFLINE_SECONDS
    # El índice 1..5 se recibirá del PIC más adelante. No se calcula ni inventa.
    intensity = m.get("wind_intensity", m.get("wind_level"))
    if intensity is not None:
        try:
            intensity = int(intensity)
        except (ValueError, TypeError):
            intensity = None
    if intensity is not None and intensity not in (1, 2, 3, 4, 5):
        intensity = None

    return {
        "id": row["id"],
        "nombre": row["nombre"],
        "estado": "conectado" if online else "desconectado",
        "ultima_actualizacion": row["ultimo_visto"],
        "gateway_id": payload.get("gateway_id"),
        "packet_id": payload.get("packet_id"),
        "posicion": {"lat": row["lat"], "lng": row["lon"]} if row["lat"] is not None and row["lon"] is not None else None,
        "mediciones": {
            "temperatura_c": as_number_or_none(m.get("temperature")),
            "humedad_pct": as_number_or_none(m.get("relative_humidity", m.get("humidity"))),
            "intensidad_viento": intensity,
            # Transición: compatibilidad con la interfaz v0.1; datos de prueba, no velocidad calibrada.
            "viento_kmh": as_number_or_none(m.get("wind_speed")),
            "direccion_viento": m.get("wind_direction"),
            "riesgo_incendio": m.get("fire_risk"),
        },
    }


@app.after_request
def allow_frontend(res):
    # Para la demostración con Live Server en la misma PC.
    res.headers["Access-Control-Allow-Origin"] = "*"
    res.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    res.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return res


@app.get("/api/health")
def health():
    return jsonify({"api": "ok", "mqtt": "conectado" if connected.is_set() else "desconectado"})


@app.get("/api/nodos")
def nodes():
    with db() as con:
        rows = con.execute("SELECT * FROM nodos ORDER BY ultimo_visto DESC").fetchall()
    nodes_out = [build_node(row) for row in rows]
    return jsonify({"nodos": nodes_out, "total": len(nodes_out)})


@app.get("/api/nodos/<node_id>/historial")
def history(node_id):
    try:
        limit = min(max(int(request.args.get("limit", 60)), 1), 500)
    except ValueError:
        return jsonify({"error": "limit debe ser numérico"}), 400
    with db() as con:
        rows = con.execute("""SELECT recibido_en, payload FROM lecturas
                           WHERE nodo_id=? ORDER BY seq DESC LIMIT ?""", (node_id, limit)).fetchall()
    data = [{"recibido_en": r["recibido_en"], "measurements": json.loads(r["payload"]).get("measurements", {})}
            for r in reversed(rows)]
    return jsonify({"node_id": node_id, "historial": data})


@app.route("/api/nodos/<node_id>/config", methods=["POST", "OPTIONS"])
def node_config(node_id):
    if request.method == "OPTIONS":
        return "", 204
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Se espera JSON"}), 400
    allowed = {"nombre", "lat", "lon"}
    if not body or set(body) - allowed:
        return jsonify({"error": "Usar nombre, lat o lon"}), 400
    with db() as con:
        row = con.execute("SELECT id FROM nodos WHERE id=?", (node_id,)).fetchone()
        if row is None:
            return jsonify({"error": "Nodo no encontrado"}), 404
        if "nombre" in body:
            nombre = str(body["nombre"]).strip()[:60]
            if not nombre:
                return jsonify({"error": "Nombre vacío"}), 400
            con.execute("UPDATE nodos SET nombre=? WHERE id=?", (nombre, node_id))
        if "lat" in body or "lon" in body:
            if "lat" not in body or "lon" not in body:
                return jsonify({"error": "Indicar lat y lon juntos"}), 400
            try:
                lat, lon = float(body["lat"]), float(body["lon"])
            except (ValueError, TypeError):
                return jsonify({"error": "Coordenadas inválidas"}), 400
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return jsonify({"error": "Coordenadas fuera de rango"}), 400
            con.execute("UPDATE nodos SET lat=?, lon=? WHERE id=?", (lat, lon, node_id))
    return jsonify({"ok": True, "node_id": node_id})


if __name__ == "__main__":
    init_db()
    mqtt_client = mqtt_start()
    try:
        # Waitress es un servidor HTTP simple, estable y compatible con Windows.
        from waitress import serve
        log.info("API disponible en http://%s:%s/api/nodos", API_HOST, API_PORT)
        serve(app, host=API_HOST, port=API_PORT, threads=4)
    finally:
        mqtt_client.loop_stop()
