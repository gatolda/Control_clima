# test_sensor.py
import Adafruit_DHT
import time

SENSOR = Adafruit_DHT.DHT22
PIN = 4  # Cambia este número si mueves el cable a otro GPIO

print("🌡️ Iniciando prueba del sensor DHT22 en GPIO", PIN)

try:
    for i in range(5):
        humedad, temperatura = Adafruit_DHT.read_retry(SENSOR, PIN)
        if humedad is not None and temperatura is not None:
            print(f"✅ Lectura {i+1}: Temp={temperatura:.1f}°C, Hum={humedad:.1f}%")
        else:
            print(f"❌ Lectura {i+1}: Sensor no respondió")
        time.sleep(2)
except KeyboardInterrupt:
    print("\n🛑 Prueba interrumpida por el usuario.")
except Exception as e:
    print(f"⚠️ Error inesperado: {e}")

print("🔁 Prueba finalizada.")
