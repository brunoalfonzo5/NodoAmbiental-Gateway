import json
import os
import logging

from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from collections import OrderedDict
from time import monotonic

# ==========================================
# 1. CONFIGURACION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT","1883"))

MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

MQTT_TOPIC = os.getenv(
    "MQTT_TOPIC",
    "nodoambiental/2/json/#"
)

# Topico donde publicaremos las mediciones procesadas
MQTT_OUTPUT_PREFIX = os.getenv(
    "MQTT_OUTPUT_PREFIX",
    "nodoambiental/procesado"
).rstrip("/")

# ==========================================
# CONTROL DE PAQUETES DUPLICADOS
# ==========================================

# Tiempo durante el cual recordamos cada paquete
DEDUP_TTL = 3600  # 1 hora

# Cantidad maxima de paquetes almacenados
MAX_PAQUETES = 5000

# Diccionario de paquetes recibidos
paquetes_vistos = OrderedDict()

# ==========================================
# 2. LOGS
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ==========================================
# 3. NORMALIZACION DE MEDICIONES
# ==========================================

def normalizar_medicion(datos,topic):

    # Verificar que exista un payload
    payload = datos.get("payload")

    if not isinstance(payload, dict):
        return None

    # Procesarsolamente telemetria
    tipo = datos.get("type")

    if tipo is not None and tipo != "telemetry":
        return None

    # Identificar nodo transmisor
    nodo_num = datos.get("from")

    if nodo_num is None:
        return None

    try:
        nodo_num = int(nodo_num)
    except (ValueError, TypeError):
        return None

    nodo_id = f"!{nodo_num:08x}"

    # Identificar el Gateway que publico el mensaje
    gateway_id = topic.split("/")[-1]

    # Crear estructura normalizada
    medicion = {

        "node_id": nodo_id,

        "node_num": nodo_num,

        "gateway_id": gateway_id,

        "packet_id": datos.get("id"),

        "channel": datos.get("channel"),

        "receive_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "measurements": payload
    }

    return medicion

# ==========================================
# DETECCION DE DUPLICADOS
# ==========================================

def obtener_clave_paquete(medicion):

    packet_id = medicion.get("packet_id")

    if packet_id is None:
        return None

    return (
        medicion["node_num"],
        medicion["channel"],
        packet_id
    )


def es_duplicado(clave):

    if clave is None:
        return False

    ahora = monotonic()

    # Eliminar paquetes que superaron el TTL
    while paquetes_vistos:

        primera_clave, instante = next(
            iter(paquetes_vistos.items())
        )

        if ahora - instante <= DEDUP_TTL:
            break

        paquetes_vistos.popitem(last=False)

    return clave in paquetes_vistos


def registrar_paquete(clave):

    if clave is None:
        return

    paquetes_vistos[clave] = monotonic()

    # Limitar la cantidad de identificadores
    while len(paquetes_vistos) > MAX_PAQUETES:
        paquetes_vistos.popitem(last=False)

# ==========================================
# 4. EVENTOS MQTT
# ==========================================

def on_connect(client, userdata, flags, reason_code, properties):

    if reason_code == 0:

        logging.info("Conectado correctamente a Mosquitto")

        client.subscribe(MQTT_TOPIC, qos=1)

        logging.info(f"Suscrito a: {MQTT_TOPIC}")

    else:

        logging.error(
            f"Error de conexion MQTT: {reason_code}"
        )


def on_disconnect(client, userdata, flags, reason_code, properties):

    logging.warning(
        f"Conexion MQTT interrumpida: {reason_code}"
    )


# ==========================================
# 4. RECEPCION Y PUBLICACION MQTT
# ==========================================

def on_message(client, userdata, msg):

    try:

        # ==================================
        # 1. DECODIFICAR MENSAJE ORIGINAL
        # ==================================

        datos = json.loads(
            msg.payload.decode("utf-8")
        )

        # ==================================
        # 2. NORMALIZAR MEDICIONES
        # ==================================

        medicion = normalizar_medicion(
            datos,
            msg.topic
        )

        # Ignorar paquetes que no contienen
        # mediciones ambientales validas

        if medicion is None:
          return

        # ==================================
        # VERIFICAR DUPLICADOS
        # ==================================

        clave = obtener_clave_paquete(medicion)

        if es_duplicado(clave):
        
            logging.warning(
                f"Paquete duplicado descartado: {clave}"
            )
        
            return
        
        logging.info("Nueva medicion recibida")

        # Mostrar datos normalizados
        print(
            json.dumps(
                medicion,
                indent=4,
                ensure_ascii=False
            ),
            flush=True
        )

        # ==================================
        # 3. CONSTRUIR TOPICO DE SALIDA
        # ==================================

        nodo_id = medicion["node_id"]

        topic_salida = (
            f"{MQTT_OUTPUT_PREFIX}/{nodo_id}"
        )

        # ==================================
        # 4. PREPARAR MENSAJE JSON
        # ==================================

        mensaje_salida = json.dumps(
            medicion,
            ensure_ascii=False
        )

        # ==================================
        # 5. PUBLICAR EN MQTT
        # ==================================

        resultado = client.publish(
            topic=topic_salida,
            payload=mensaje_salida,
            qos=1,
            retain=False
        )

        if resultado.rc == mqtt.MQTT_ERR_SUCCESS:

            registrar_paquete(clave)

            logging.info(
                f"Publicacion encolada: {topic_salida}"
            )

        else:

            logging.error(
                f"Error publicando MQTT: "
                f"{mqtt.error_string(resultado.rc)}"
            )

    except (json.JSONDecodeError, UnicodeDecodeError):

        logging.warning(
            "Mensaje recibido con formato JSON invalido"
        )

    except Exception:

        logging.exception(
            "Error procesando mensaje MQTT"
        )


# ==========================================
# 5. INICIO DEL PROCESADOR
# ==========================================

def main():

    logging.info("Iniciando procesador Nodo Ambiental")

    if not MQTT_USERNAME or not MQTT_PASSWORD:
        raise RuntimeError(
            "Faltan las credenciales MQTT en el archivo .env"
        )

    # Crear cliente MQTT
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"nodoambiental-processor-{os.getpid()}"
    )

    # Configurar autenticacion
    client.username_pw_set(
        MQTT_USERNAME,
        MQTT_PASSWORD
    )

    # Configurar eventos
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    # Reconexiones automaticas
    client.reconnect_delay_set(
        min_delay=1,
        max_delay=30
    )

    # Conectar al broker
    client.connect_async(
        MQTT_HOST,
        MQTT_PORT,
        keepalive=60
    )

    logging.info(
        f"Conectando con {MQTT_HOST}:{MQTT_PORT}"
    )

    try:
        client.loop_forever(retry_first_connection=True)

    except KeyboardInterrupt:
        logging.info("Deteniendo procesador")

    finally:
        client.disconnect()


if __name__ == "__main__":
    main()