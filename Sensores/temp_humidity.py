import Adafruit_DHT

class TempHumiditySensor:
    def __init__(self, pin, sensor_type=Adafruit_DHT.DHT22):
        self.sensor_type = sensor_type
        self.pin = pin
        

    def read(self):
        humidity, temperature = Adafruit_DHT.read_retry(self.sensor_type, self.pin)
        if humidity is not None and temperature is not None:
            return {
                "temperature": temperature,
                "humidity": humidity,
                "status": "OK"
            }
        else:
            return {
                "temperature": None,
                "humidity": None,
                "status": "ERROR"
            }
