# main.py
from config_loader import ConfigLoader
from sensor_reader import SensorReader
from actuator_manager import ActuatorManager
from modos.manual_mode import modo_manual
import time

# === INICIALIZACIÓN ===
try:
    # Cargar configuración
    config = ConfigLoader()
    config.cargar_configuracion()

    # Inicializar sensores
    sensores_config = config.obtener("sensores", {})
    sensor_reader = SensorReader(sensores_config)
    print(f"✅ SensorReader inicializado con sensores: {list(sensores_config.keys())}")

    # Inicializar actuadores
    relay_pins = config.obtener("actuadores.rele_board.pines", {})
    actuator_manager = ActuatorManager(relay_pins)

    # Mostrar configuración cargada
    print("\n==== CONFIGURACIÓN DEL SISTEMA ====")
    for nombre, conf in sensores_config.items():
        tipo = conf.get("tipo", "Desconocido")
        pin = conf.get("pin", "N/A")
        print(f"📡 {nombre}: Tipo={tipo} Pin={pin}")

    print("⚡ Actuadores (Relés):")
    for nombre, pin in relay_pins.items():
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
    actuator_manager.cleanup()
    print("♻️ GPIO liberado.")
