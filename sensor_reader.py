import Adafruit_DHT
from Sensores.co2_pwm_sensor import CO2PWMSensor  # 👈 Importamos el nuevo sensor

class SensorReader:
    def __init__(self, config):
        self.sensors = config.obtener("sensores")
        self.co2_pwm = None  # Inicializamos el sensor
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

            elif tipo == "CO2_PWM":
                if self.co2_pwm is None:
                    self.co2_pwm = CO2PWMSensor(pin)
                lectura = self.co2_pwm.read()
                if lectura:
                    datos[nombre] = {
                        "co2": lectura["co2"],
                        "pulse": lectura["pulse"]
                    }
                else:
                    datos[nombre] = {
                        "co2": None,
                        "pulse": None
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
