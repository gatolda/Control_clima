"""
main.py - Prueba directa al sensor de temperatura/humedad
"""

import time
from Sensores.temp_humidity import TempHumiditySensor

def main():
    print("==== PRUEBA DIRECTA SENSOR ====")

    # Inicializar sensor
    sensor = TempHumiditySensor(pin=4)  # Ajusta el pin según tu hardware
    print("📡 Sensor inicializado correctamente.")

    try:
        while True:
            # Leer datos directamente
            datos = sensor.read()
            if datos.get("status") == "OK":
                temperatura = datos.get("temperature")
                humedad = datos.get("humidity")
                print(f"✅ Temp: {temperatura:.1f}°C  Humedad: {humedad:.1f}%")
            else:
                print("❌ Error al leer el sensor")

            print("⏳ Esperando 2 segundos...\n")
            time.sleep(2)

    except KeyboardInterrupt:
        print("\n🛑 Prueba detenida por el usuario.")


if __name__ == "__main__":
    main()
