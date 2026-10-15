# ==========================================
# NODO AMBIENTAL - PROCESADOR MQTT
# ==========================================

# Imagen base de Python
FROM python:3.12-slim

# Configuracion de Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directorio de trabajo
WORKDIR /app

# ==========================================
# NODO AMBIENTAL - PROCESADOR MQTT
# ==========================================

FROM python:3.12-slim

# Configuracion de Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directorio de trabajo
WORKDIR /app

# Copiar dependencias del procesador
COPY infra/processor/requirements.txt ./requirements.txt

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar codigo del procesador
COPY src/mqtt_receiver.py ./src/mqtt_receiver.py

# Ejecutar el procesador
CMD ["python", "src/mqtt_receiver.py"]