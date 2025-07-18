# main.py
import time
from config_loader import ConfigLoader
from sensor_reader import SensorReader
from actuator_manager import ActuatorManager
from modos.manual_mode import ManualMode
from modos.automatic_mode import AutomaticMode
from gpio_setup import inicializar_gpio, limpiar_gpio

# 🟢 Inicializar configuración GPIO (modo BOARD)
inicializar_gpio("BOARD")

try:
    # 🔧 Cargar configuración
    config = ConfigLoader()
    config.cargar_configuracion()

    # 📡 Inicializar sensores y actuadores
    sensor_reader = SensorReader(config)
    actuator_manager = ActuatorManager(config)

    print("\n==== CONFIGURACIÓN DEL SISTEMA ====")
    for sensor, settings in config.obtener("sensores", {}).items():
        print(f"📡 {sensor}: Tipo={settings.get('tipo')} Pin={settings.get('pin', 'N/A')}")
    print("====================================\n")

    # 👉 Selección de modo
    modo = input("Selecciona el modo (manual/automatico): ").strip().lower()

    if modo == "manual":
        manual_mode = ManualMode(sensor_reader, actuator_manager)
        manual_mode.run()

    elif modo == "automatico":
        umbrales = config.obtener("umbrales_automatico", {})
        auto_mode = AutomaticMode(sensor_reader, actuator_manager, umbrales)
        auto_mode.run()

    else:
        print("❌ Modo no reconocido. Usa 'manual' o 'automatico'.")

except KeyboardInterrupt:
    print("\n🛑 Programa detenido por el usuario.")

finally:
    # ♻️ Limpieza de pines GPIO
    limpiar_gpio()
