from config_loader import ConfigLoader
from sensor_reader import SensorReader
from actuator_manager import ActuatorManager
from modos.manual_mode import ManualMode
from modos.automatic_mode import AutomaticMode
import time

# 🛠️ Cargar configuración
config_loader = ConfigLoader()
config_loader.cargar_configuracion()

# ✅ Inicializar sensores y actuadores
sensor_reader = SensorReader(config_loader)
actuator_manager = ActuatorManager(config_loader)

# ♻️ Limpiar GPIO al inicio para evitar relés encendidos
actuator_manager.cleanup()

# Mostrar configuración cargada
print("\n==== CONFIGURACIÓN DEL SISTEMA ====")
for sensor, settings in config_loader.obtener("sensores", {}).items():
    print(f"📡 {sensor}: Tipo={settings.get('tipo')} Pin={settings.get('pin', 'N/A')}")
print("====================================\n")

# 🌟 Selección de modo
modo = input("Selecciona el modo (manual/automatico): ").strip().lower()

try:
    if modo == "manual":
        manual_mode = ManualMode(sensor_reader, actuator_manager)
        manual_mode.run()
    elif modo == "automatico":
        umbrales = config_loader.obtener("umbrales_automatico")
        auto_mode = AutomaticMode(sensor_reader, actuator_manager, umbrales)
        auto_mode.run()
    else:
        print("❌ Modo no reconocido. Usa 'manual' o 'automatico'.")
except KeyboardInterrupt:
    print("\n🛑 Programa detenido por el usuario.")
finally:
    actuator_manager.cleanup()
    print("♻️ GPIO liberado correctamente.")
