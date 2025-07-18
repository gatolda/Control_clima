# main.py
from config_loader import ConfigLoader
from sensor_reader import SensorReader
from actuator_manager import ActuatorManager
from modos.manual_mode import modo_manual
import time

# === INICIALIZACIÓN ===
actuator_manager = None  # Predefinir para evitar NameError

try:
    # Cargar configuración
    config_loader = ConfigLoader()
    config_loader.cargar_configuracion()

    # Obtener el diccionario de configuración
    sensores_config = config_loader.obtener("sensores", {})
    actuadores_config = config_loader.obtener("actuadores.rele_board.pines", {})

    # Inicializar sensores
    sensor_reader = SensorReader(sensores_config)
    print(f"✅ SensorReader inicializado con sensores: {list(sensores_config.keys())}")

    # Inicializar actuadores
    actuator_manager = ActuatorManager(actuadores_config)

    # Mostrar configuración cargada
    print("\n==== CONFIGURACIÓN DEL SISTEMA ====")
    for nombre, conf in sensores_config.items():
        tipo = conf.get("tipo", "Desconocido")
        pin = conf.get("pin", "N/A")
        print(f"📡 {nombre}: Tipo={tipo} Pin={pin}")

    print("⚡ Actuadores (Relés):")
    for nombre, pin in actuadores_config.items():
        print(f"  - {nombre}: Pin {pin}")
    print("====================================\n")

    # Seleccionar modo
    print("Selecciona el modo de operación:")
    print("1 - Manual")
    print("2 - Automático (en desarrollo)")
    modo = input("👉 Ingresa el número de opción: ")

    if modo == "1":
        modo_manual(sensor_reader, actuator_manager)
    elif modo == "2":
        print("🚧 Modo automático aún no implementado.")
    else:
        print("⚠️ Opción no válida. Saliendo...")

except Exception as e:
    print(f"❌ Error: {e}")
finally:
    if actuator_manager:
        actuator_manager.cleanup()
        print("♻️ GPIO liberado.")
