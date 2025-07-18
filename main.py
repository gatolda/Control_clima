"""
main.py
Programa principal para el sistema de control climático
"""

from config_loader import ConfigLoader
from sensor_reader import SensorReader
import time

# Cargar configuración
config = ConfigLoader()
config.cargar_configuracion()

# Inicializar lectura de sensores
sensor_reader = SensorReader(config)

# Mostrar configuración cargada
print("\n==== CONFIGURACIÓN DEL SISTEMA ====")
for sensor, settings in config.obtener("sensores").items():
    tipo = settings.get("tipo", "Desconocido")
    pin = settings.get("pin", "N/A")
    print(f"📡 {sensor}: Tipo={tipo} Pin={pin}")
print("====================================\n")

# Bucle principal
try:
    print("🔄 Iniciando ciclo principal...")
    while True:
        datos = sensor_reader.leer_todos()

        if not datos:
            print("⚠️ No se pudieron obtener lecturas de sensores.")
        else:
            print("📊 Lecturas actuales:")
            for sensor, lectura in datos.items():
                if "error" in lectura:
                    print(f"  ❌ {sensor}: {lectura['error']}")
                else:
                    temp = lectura.get("temperatura", "N/A")
                    hum = lectura.get("humedad", "N/A")
                    print(f"  🌡️ {sensor}: {temp}°C, 💧 {hum}%")
        print("⏳ Esperando 5 segundos...\n")
        time.sleep(config.obtener("general.intervalo_lectura", 5))

except KeyboardInterrupt:
    print("\n🛑 Programa detenido por el usuario.")
