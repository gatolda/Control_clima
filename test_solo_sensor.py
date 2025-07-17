# test_solo_sensor.py
from Sensores.temp_humidity import TempHumiditySensor
import time

print("🌡️ Iniciando prueba del sensor de temperatura y humedad...")

try:
    # Ajusta el pin GPIO si es necesario
    sensor = TempHumiditySensor(pin=4)
    print("✅ Sensor inicializado correctamente.")

    for i in range(5):
        lectura = sensor.read()
        if lectura["status"] == "OK":
            print(f"📡 Lectura {i+1}: Temp = {lectura['temperature']}°C, Hum = {lectura['humidity']}%")
        else:
            print(f"⚠️ Lectura {i+1}: Sensor devolvió None")
        time.sleep(2)

except Exception as e:
    print(f"❌ Error durante la prueba del sensor: {e}")

print("✅ Prueba del sensor finalizada.")
