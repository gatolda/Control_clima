import Adafruit_DHT

class SensorReader:
    def __init__(self, config):
        self.sensors = config.obtener("sensores")
        print(f"✅ SensorReader inicializado con sensores: {self.sensors.keys()}")

    def read_all_sensors(self):
        """
        Lee todos los sensores configurados y devuelve un diccionario con los datos.
        """
        datos = {}
        for nombre, settings in self.sensors.items():
            tipo = settings.get("tipo")
            pin = settings.get("pin")

            if tipo == "DHT22":
                humedad, temperatura = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, pin)
                datos[nombre] = {
                    "temperature": round(temperatura, 1) if temperatura else None,
                    "humidity": round(humedad, 1) if humedad else None
                }
            elif tipo == "MH-Z19":
                # Simulación para CO2 por ahora
                datos[nombre] = {
                    "temperature": None,
                    "humidity": None,
                    "co2": None
                }
            else:
                datos[nombre] = {
                    "temperature": None,
                    "humidity": None
                }

        return datos

    # Alias para compatibilidad
    def read_all(self):
        return self.read_all_sensors()
