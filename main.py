"""
main.py
Programa principal del sistema de control climático
"""

from config_loader import ConfigLoader
from sensor_reader import SensorReader
import time

# 🔧 Cargar configuración
config = ConfigLoader()
config.cargar_configuracion()

# 📡 Inicializar SensorReader
sensor_reader = SensorReader(config)

# ✅ Mostrar configuración
print("\n==== CONFIGURACIÓN DEL SISTEMA ====")
for sensor, settings in config.obtener("sensores").items():
    print(f"📡 {sensor}: Tipo={settings['tipo']} Pin={settings.get('pin', 'N/A')}")
print("====================================\n")

# 🔄 Bucle principal
print("🔄 Iniciando ciclo principal...")
try:
    while True:
        # Leer sensores
        datos = sensor_reader.leer_todos()
        print("📊 Lecturas actuales:")
        for sensor, lectura in datos.items():
            print(f"  📡 {sensor}: {lectura}")

        # TODO: Gestionar actuadores aquí
        print("⚡ Gestionando actuadores...\n")

        # Esperar intervalo configurado
        intervalo = config.obtener("general.intervalo_lectura", 5)
        print(f"⏳ Esperando {intervalo} segundos...\n")
        time.sleep(intervalo)

except KeyboardInterrupt:
    print("\n🛑 Programa detenido por el usuario.")
