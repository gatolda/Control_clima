from config_loader import ConfigLoader
from sensor_reader import SensorReader
from actuator_manager import ActuatorManager
from modos.manual_mode import ManualMode
import time

try:
    # Cargar configuración
    config_loader = ConfigLoader()
    config_loader.cargar_configuracion()

    # Inicializar módulos
    sensor_reader = SensorReader(config_loader)
    actuator_manager = ActuatorManager(config_loader)

    print("\n==== CONFIGURACIÓN DEL SISTEMA ====")
    for sensor, settings in config_loader.obtener("sensores", {}).items():
        print(f"📡 {sensor}: Tipo={settings['tipo']} Pin={settings.get('pin', 'N/A')}")
    for actuador, settings in config_loader.obtener("actuadores", {}).items():
        print(f"⚡ {actuador}: Pines={settings['pines']} Activación={settings.get('tipo_activacion', 'N/A')}")
    print("====================================\n")

    # Selección de modo
    modo = config_loader.obtener("general.modo_inicial", "manual")
    if modo == "manual":
        modo_manager = ManualMode(sensor_reader, actuator_manager)
        modo_manager.ejecutar()
    else:
        print("⚠️ Solo está implementado el modo manual por ahora.")

except Exception as e:
    print(f"❌ Error: {e}")

finally:
    if 'actuator_manager' in locals():
        actuator_manager.cleanup()
    print("🛑 Sistema detenido.")
