# Nodo Ambiental · Interfaz web v0.1

Panel de monitoreo **independiente** del gateway, del broker MQTT y del procesador Python. Esta versión usa únicamente HTML, CSS y JavaScript, con una fuente de datos de demostración que puede reemplazarse por la API del procesador Python más adelante.

## 1. Abrir y probar

1. Abrí la carpeta `web/` en VS Code.
2. Con **Live Server**, hacé clic derecho en `index.html` → **Open with Live Server**.
3. Alternativa sin extensión: abrí una terminal en `web/` y ejecutá `python -m http.server 5500`; luego entrá a `http://localhost:5500`.
4. Verificá que la leyenda superior indique **DEMOSTRACIÓN**. Los puntos del mapa y las mediciones del archivo JSON son ilustrativos, **no datos reales**.
5. Probá la selección de nodos, la actualización y el selector de fuente de datos.

> Importante: no abras `index.html` haciendo doble clic mediante `file://`, porque el navegador puede bloquear la lectura de `data/nodos.json` por motivos de seguridad. El mapa base y las fuentes necesitan internet; el resto de la interfaz no requiere paquetes ni compilación.

## 2. Estructura

```
web/
├── index.html       # Estructura y elementos del panel
├── css/
│   └── styles.css   # Diseño adaptable a PC y celular
├── js/
│   └── app.js       # Consulta de datos, tarjetas, gráfico, tabla y mapa
├── data/
│   └── nodos.json   # Datos simulados para desarrollo
└── README.md
```

## 3. Contrato de datos para Python

La interfaz espera una respuesta JSON que contenga el arreglo `nodos`. En `data/nodos.json` hay un ejemplo completo. Formato mínimo sugerido:

```json
{
  "fuente": "python",
  "actualizado": "2026-10-14T09:30:00-03:00",
  "gateway": {
    "id": "GW-01",
    "estado": "online",
    "ultima_trama": "2026-10-14T09:29:51-03:00"
  },
  "nodos": [
    {
      "id": "NA-01",
      "nombre": "Nodo Norte",
      "lat": -38.94,
      "lon": -69.23,
      "estado": "online",
      "ultima_lectura": "2026-10-14T09:29:51-03:00",
      "bateria_pct": 86,
      "radio": {"rssi_dbm": -91, "snr_db": 7.2},
      "mediciones": {
        "temperatura_c": 25.4,
        "humedad_pct": 32,
        "viento_kmh": 16.8,
        "direccion_viento": "SO",
        "riesgo_incendio": null
      },
      "historial": [
        {"hora": "09:00", "temperatura_c": 24.1, "viento_kmh": 12.5},
        {"hora": "09:15", "temperatura_c": 24.8, "viento_kmh": 15.2}
      ]
    }
  ]
}
```

Los campos de mediciones se pueden incorporar progresivamente conforme avancemos con el PIC. `riesgo_incendio: null` significa que no existe cálculo todavía. El gráfico necesita al menos dos entradas de historial para dibujarse. El frontend no calcula riesgo, y no considera actuales las mediciones de un nodo `offline`.

## 4. Futuro enlace con Python

La secuencia prevista es:

```
PIC → UART → XIAO Meshtastic → LoRa → Gateway → MQTT Mosquitto
                                                 ↓
                                         Procesador Python
                                                 ↓
                                         API HTTP /api/nodos
                                                 ↓
                                             Interfaz web
```

El frontend hace una consulta HTTP cada 15 segundos (configurable en `js/app.js` → `refreshMs`). Por ahora, la opción **API Python** consulta `http://127.0.0.1:8000/api/nodos` — todavía no existe, y mostrará un error hasta que la implementemos.

Para integrar, el procesador Python deberá **exponer una API HTTP** que entregue el JSON del formato anterior. Si el frontend se abre en el puerto 5500 y la API corre en el 8000, hay que habilitar CORS en el backend para el origen `http://127.0.0.1:5500` (o servir el frontend y la API bajo el mismo origen). Más adelante, cuando migremos a Raspberry Pi, podremos mantener este contrato sin cambiar la interfaz.

**Criterio importante:** aunque el JSON incluya `estado`, en la versión real deberemos definir `online` calculando antigüedad de tramas y estado de conectividad. El ejemplo de demostración tiene estados ficticios.

## 5. Versionar en GitHub

Podés agregar la carpeta `web/` al repositorio que ya utilizás sin modificar `firmware/`, el gateway ni el broker. Desde la raíz del repositorio:

```bash
git add web/
git commit -m "feat: interfaz web inicial con datos simulados"
git push
```

Si preferís un repositorio separado para el dashboard, esta carpeta puede usarse como proyecto independiente.
