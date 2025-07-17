import time
import Adafruit_DHT
from config_loader import ConfigLoader

# Cargar la configuración
config = ConfigLoader("config.yml")
print("✅ Configuración cargada correctamente desde config.yml\n")

# Mostrar la configuración cargada
print("==== CONFIGURACIÓN DEL SISTEMA ====")
print("📡 Sensores:")
for sensor, settings in config.data.get("sensores", {}).items():
    print(f"  - {sensor.capitalize()}: Pin={settings['pin']} Tipo={settings['tipo']}")
print("⚡ Actuadores:")
for act, settings in config.data.get("actuadores", {}).items():
    print(f"  - {act.capitalize()}: Pines={settings['pines']} modo={settings['modo']}")
print("====================================\n")

# Inicializar el sensor DHT22
dht_settings = config.data["sensores"]["temperatura_humedad"]
sensor_type = Adafruit_DHT.DHT22 if dht_settings["tipo"] == "DHT22" else Adafruit_DHT.DHT11
sensor_pin = dht_settings["pin"]

print("🔄 Iniciando ciclo principal (lectura de DHT22)...")

try:
    while True:
        # Leer temperatura y humedad
        humidity, temperature = Adafruit_DHT.read_retry(sensor_type, sensor_pin)
        if humidity is not None and temperature is not None:
            print(f"🌡️ Temp: {temperature:.1f}°C  💧 Humedad: {humidity:.1f}%")
        else:
            print("❌ Error al leer el sensor DHT22")

        # Pausa entre lecturas
        time.sleep(3)

except KeyboardInterrupt:
    print("\n🛑 Programa detenido por el usuario.")
