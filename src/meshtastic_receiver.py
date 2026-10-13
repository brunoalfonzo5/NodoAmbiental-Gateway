import time
import meshtastic.serial_interface
from pubsub import pub
from pprint import pprint

# =====================================
# CONFIGURACIÓN
# =====================================

PUERTO = "COM8" 

# =====================================
# RECEPCIÓN DE PAQUETES
# =====================================

def on_receive(packet, interface):

    # Obtener información decodificada
    decoded = packet.get("decoded", {})

    # Verificar que sea un paquete de telemetría
    if decoded.get("portnum") != "TELEMETRY_APP":
        return

    # Obtener telemetría
    telemetry = decoded.get("telemetry", {})

    # Obtener mediciones ambientales
    ambiente = telemetry.get("environmentMetrics")

    # Si no contiene mediciones ambientales, ignorar
    if not ambiente:
        return

    # Identificar nodo transmisor
    nodo = packet.get("fromId", "Desconocido")

    # Extraer mediciones
    temperatura = ambiente.get("temperature")
    direccion = ambiente.get("windDirection")
    velocidad = ambiente.get("windSpeed")
    rafaga = ambiente.get("windGust")

    # Mostrar resultados
    print("\n====================================")
    print("           NODO AMBIENTAL")
    print("====================================")

    print(f"Nodo: {nodo}\n")

    if temperatura is not None:
        print(f"Temperatura:       {temperatura} °C")

    if direccion is not None:
        print(f"Direccion viento:  {direccion} °")

    if velocidad is not None:
        print(f"Velocidad viento:  {velocidad} m/s")

    if rafaga is not None:
        print(f"Rafaga viento:     {rafaga} m/s")

    print("====================================\n")

# =====================================
# PROGRAMA PRINCIPAL
# =====================================

def main():

    print("=================================")
    print("   GATEWAY NODO AMBIENTAL")
    print("=================================")

    print(f"Conectando al puerto {PUERTO}...")

    interface = None

    try:

        #Suscribirse a los paquetes recibidos
        pub.subscribe(on_receive, "meshtastic.receive")

        #Conectar con el XIAO
        interface = meshtastic.serial_interface.SerialInterface(
            devPath=PUERTO
        )

        print("Conexion establecida correctamente")
        print("Esperando paquetes LoRa...\n")

        #Mantener el programa funcionando
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        
        print("\nDeteniendo Gateway...")

    finally:

        if interface is not None:
            interface.close()

        print("Gateway desconectado")

if __name__== "__main__":
    main()




    