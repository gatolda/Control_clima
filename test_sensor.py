import Adafruit_DHT
import time

# Configurar tipo de sensor (DHT11 o DHT22)
SENSOR = Adafruit_DHT.DHT22  # Cambia a DHT11 si usas ese modelo
GPIO_PIN = 4  # Cambia si tu sensor está conectado a otro GPIO

print("🌡️ Iniciando prueba del sensor de temperatura/humedad...")

while True:
    humedad, temperatura = Adafruit_DHT.read_retry(SENSOR, GPIO_PIN)

    if humedad is not None and temperatura is not None:
        print(f"✅ Temp: {temperatura:.1f}°C  Humedad: {humedad:.1f}%")
    else:
        print("❌ Error al leer el sensor")

    time.sleep(2)
