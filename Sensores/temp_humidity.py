import Adafruit_DHT

class TempHumiditySensor:
    """
    Sensor de temperatura y humedad usando la librería Adafruit_DHT.
    """

    def __init__(self, pin, sensor_type=Adafruit_DHT.DHT22):
        """
        Inicializa el sensor.

        :param pin: Número del GPIO al que está conectado el pin de datos del sensor.
        :param sensor_type: Tipo de sensor (Adafruit_DHT.DHT22 o Adafruit_DHT.DHT11).
        """
        self.pin = pin
        self.sensor_type = sensor_type

    def read(self):
        """
        Lee la temperatura y la humedad desde el sensor.
        :return: Diccionario con temperatura (°C), humedad (%) y status ("OK" o "ERROR").
        """
        humedad, temperatura = Adafruit_DHT.read_retry(self.sensor_type, self.pin)
        if humedad is not None and temperatura is not None:
            return {
                "temperature": temperatura,
                "humidity": humedad,
                "status": "OK"
            }
        else:
            return {
                "temperature": None,
                "humidity": None,
                "status": "ERROR"
            }
