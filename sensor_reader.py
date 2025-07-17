"""
sensor_reader.py
Lee todos los sensores definidos en config.yml
"""

import Adafruit_DHT
import time

class SensorReader:
    def __init__(self, config):
        self.config = config
        self.sensores = config.obtener("sensores")
        print("✅ SensorReader inicializado con sensores:", self.sensores.keys())

    def leer_dht22(self, pin):
        """Lee el sensor DHT22 en el pin especificado"""
        print(f"🌡️ Leyendo DHT22 en pin GPIO {pin}...")
        humedad, temperatura = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, pin)
        if humedad is not None and temperatura is not None:
            print(f"✅ DHT22: {temperatura:.1f}°C, {humedad:.1f}%")
            return {
                "temperatura": round(temperatura, 1),
                "humedad": round(humedad, 1),
                "status": "OK"
            }
        else:
            print("❌ Error leyendo DHT22 (None recibido)")
            return {
                "temperatura": None,
                "humedad": None,
                "status": "ERROR"
            }

    def leer_todos(self):
        """Lee todos los sensores configurados y devuelve un diccionario"""
        resultados = {}
        for nombre, datos in self.sensores.items():
            tipo = datos.get("tipo")
           
