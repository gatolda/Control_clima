import time
from Sensores.temp_humidity import TempHumiditySensor

sensor = TempHumiditySensor(pin=4)  # Ajusta el pin si es necesario

while True:
    data = sensor.read()
    print(data)
    print("---- Esperando 2 segundos ----")
    time.sleep(2)  # Espera 2 segundos antes de la próxima lectura


