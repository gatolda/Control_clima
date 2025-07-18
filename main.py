# main.py
from config_loader import ConfigLoader
from sensor_reader import SensorReader
from actuator_manager import ActuatorManager
from modos.manual_mode import ManualMode

# Cargar configuración
config = ConfigLoader()
config.cargar_configuracion()

# Inicializar sensores y actuadores
sensor_reader = SensorReader(config)
actuator_manager = ActuatorManager(config)

# Mostrar configuración cargada
print("✅ Configuración cargada correctamente desde config.yml")
print("\n==== CONFIGURACIÓN DEL SISTEMA ====")
for sensor, settings in config.obtener("sensores", {}).items():
    print(f"📡 {sensor}: Tipo={settings['tipo']} Pin={settings.get('pin', 'N/A')}")
print("====================================\n")

# Preguntar modo al usuario
modo = input("Selecciona el modo (manual/automatico/ia): ").strip().lower()

if modo == "manual":
    manual_mode = ManualMode(sensor_reader, actuator_manager)
    manual_mode.run()
else:
    print(f"⚠️ Modo '{modo}' no implementado todavía.")

