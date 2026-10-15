# NodoAmbiental-Gateway
Gateway Meshtastic LoRa a MQTT para Nodo Ambiental

## Infraestructura MQTT

El proyecto utiliza Eclipse Mosquitto como broker MQTT,
ejecutado mediante Docker Compose.

### Requisitos

- Docker Engine / Docker Desktop
- Docker Compose
- Red local disponible

### Estructura

infra/
├── compose.yaml
└── mosquitto/
    └── mosquitto.conf

### Primera instalación

Ubicarse dentro de la carpeta infra:

```powershell
cd infra
```

Crear el usuario MQTT en el volumen persistente:

```powershell
docker compose run --rm --no-deps --user 1883:1883 --entrypoint mosquitto_passwd mosquitto -c /mosquitto/data/passwords gateway
```

Este comando se utiliza únicamente en la instalación
inicial, ya que la opción -c recrea el archivo de usuarios.

Iniciar el broker:

```powershell
docker compose up -d
```

### Administración

Verificar estado:

```powershell
docker compose ps
```

Consultar registros:

```powershell
docker compose logs --tail=30 mosquitto
```

Reiniciar servicio:

```powershell
docker compose restart mosquitto
```

### Configuración MQTT

- Puerto: 1883
- Autenticación: habilitada
- Usuario inicial: gateway
- Persistencia: habilitada
- Reinicio automático: unless-stopped

Las contraseñas no se almacenan en GitHub.
Se mantienen en un volumen persistente de Docker.

### Pruebas realizadas

- Publicación y suscripción MQTT.
- Conexión desde dispositivos de la red local.
- Autenticación de clientes.
- Persistencia de mensajes retenidos.
- Recuperación después de reiniciar Docker Desktop.

### Migración

La infraestructura está diseñada para trasladarse
posteriormente a una Raspberry Pi 4 utilizando Docker Compose.

En una instalación nueva deberán crearse las credenciales
MQTT antes de iniciar el broker.

## Procesador MQTT

El proyecto cuenta con un procesador Python encargado de:

- Recibir paquetes JSON desde Meshtastic.
- Identificar automáticamente los nodos transmisores.
- Normalizar las mediciones ambientales.
- Detectar paquetes duplicados.
- Publicar las mediciones normalizadas mediante MQTT.
- Recuperar la conexión ante interrupciones.

### Servicios Docker

La infraestructura utiliza Docker Compose con dos servicios:

- mosquitto: broker MQTT.
- processor: procesador Python.

### Iniciar los servicios

Desde la carpeta infra:

docker compose up -d --build

### Verificar funcionamiento

docker compose ps

### Consultar registros

docker compose logs -f processor

### Tópicos MQTT

Datos originales:
nodoambiental/2/json/#

Datos procesados:
nodoambiental/procesado/<node_id>

### Configuración

Las variables de conexión se encuentran en el archivo .env.

Para una instalación nueva, utilizar .env.example como referencia.

El archivo .env no debe subirse a GitHub.

### Observaciones

La detección de duplicados funciona actualmente en memoria.

El almacenamiento persistente de mediciones se incorporará
en la próxima etapa mediante una base de datos.
