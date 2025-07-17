"""
main.py
Programa principal del sistema de control climático.
Lee la configuración desde config.yml y gestiona sensores y actuadores.
"""

from config_loader import ConfigLoader
import time
import Adafruit_DHT

# Cargar configuración
config = ConfigLoader()
config.cargar_configuracion()

# Mostrar configuración cargada
print("\n==== CONFIGURACIÓN DEL SISTEMA ====")
sensores = config.obtener("sensores", {})
for sensor, settings in sensores.items():
    print(f"📡 {sensor}: Pin={settings['pin']} Tipo={settings['tipo']}")

actuadores = config.obtener("actuadores.rele_board.pines", {})
print("⚡ Actuadores (Placa de relés):")
for nombre, pin in actuadores.items():
    print(f"  - {nombre}: Pin={pin}")
print("====================================\n")

# Inicializar sensor DHT22 si está configurado
sensor_dht = None
pin_dht = None
if "temperatura_humedad" in sensores:
    pin_dht = sensores["temperatura_humedad"]["pin"]
    tipo_dht = sensores["temperatura_humedad"]["tipo"]
    if tipo_dht.upper() == "DHT22":
        sensor_dht = Adafruit_DHT.DHT22
        print(f"✅ Sensor DHT22 configurado en GPIO {pin_dht}")
    else:
        print(f"⚠️ Tipo de sensor {tipo_dht} no soportado.")
else:
    print("⚠️ No se encontró configuración para temperatura y humedad.")

# Ciclo principal
print("🔄 Iniciando ciclo principal...")
try:
    while True:
        # Leer DHT22
        if sensor_dht and pin_dht is not None:
            print("📡 Leyendo sensor DHT22...")
            humedad, temperatura = Adafruit_DHT.read_retry(sensor_dht, pin_dht)
            if humedad is not None and temperatura is not None:
                print(f"🌡️ Temp: {temperatura:.1f}°C  💧 Humedad: {humedad:.1f}%")
            else:
                print("❌ Error al leer el sensor DHT22.")
        else:
            print("📡 Sensor DHT22 no inicializado o no configurado.")

        # Simular gestión de actuadores
        print("⚡ Gestionando actuadores... (simulado)")
        time.sleep(5)

except KeyboardInterrupt:
    print("\n🛑 Programa detenido por el usuario.")
