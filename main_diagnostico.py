"""
main_diagnostico.py - Diagnóstico rápido del sistema de control climático
Este script prueba la inicialización del sensor de temperatura/humedad
y muestra mensajes paso a paso para detectar posibles fallos.
"""

print("🔍 Iniciando diagnóstico del sistema...")

try:
    # Intentar importar el módulo del sensor
    print("📦 Importando módulo TempHumiditySensor...")
    from Sensores.temp_humidity import TempHumiditySensor
    print("✅ Módulo TempHumiditySensor importado correctamente.")
except ImportError as e:
    print(f"❌ Error al importar TempHumiditySensor: {e}")
    exit(1)

try:
    # Intentar inicializar el sensor
    print("⚡ Inicializando sensor de temperatura y humedad en pin GPIO 4...")
    sensor = TempHumiditySensor(pin=4)
    print("✅ Sensor inicializado correctamente.")
except Exception as e:
    print(f"❌ Error al inicializar el sensor: {e}")
    exit(1)

try:
    # Intentar leer datos del sensor
    print("📡 Leyendo datos del sensor...")
    datos = sensor.read()
    if datos and datos.get("status") == "OK":
        print(f"🌡️ Temperatura: {datos['temperature']}°C")
        print(f"💧 Humedad: {datos['humidity']}%")
    else:
        print("⚠️ El sensor no devolvió datos válidos.")
except Exception as e:
    print(f"❌ Error al leer datos del sensor: {e}")

print("✅ Diagnóstico finalizado.")
