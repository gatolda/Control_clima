from config_loader import ConfigLoader
from sensor_reader import SensorReader
from actuator_manager import ActuatorManager
from modos.manual_mode import ManualMode
from modos.automatic_mode import AutomaticMode

# Cargar configuración
config = ConfigLoader()
config.cargar_configuracion()

# Inicializar sensores y actuadores
sensor_reader = SensorReader(config)
actuator_manager = ActuatorManager(config)

# Mostrar configuración cargada
print("\n==== CONFIGURACIÓN DEL SISTEMA ====")
for nombre, datos in config.obtener("sensores", {}).items():
    print(f"📡 {nombre}: Tipo={datos['tipo']} Pin={datos.get('pin', 'N/A')}")
print("====================================\n")

# Seleccionar modo
modo = input("Selecciona el modo (manual/automatico): ").strip().lower()

if modo == "manual":
    manual_mode = ManualMode(sensor_reader, actuator_manager)
    manual_mode.run()
elif modo == "automatico":
    automatic_mode = AutomaticMode(sensor_reader, actuator_manager, config)
    automatic_mode.run()
else:
    print("❌ Modo no reconocido. Usa 'manual' o 'automatico'.")
