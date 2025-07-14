import time
from Sensores.temp_humidity import TempHumiditySensor
import RPi.GPIO as GPIO

# Relé: Canal 1 conectado a GPIO 18
relay_pin = 18

GPIO.setmode(GPIO.BCM)
GPIO.setup(relay_pin, GPIO.OUT)
GPIO.output(relay_pin, GPIO.HIGH)  # Apagar al inicio (lógica inversa)

sensor = TempHumiditySensor(pin=4)

try:
    while True:
        data = sensor.read()
        if data and 'temperature' in data:
            temp = data['temperature']
            print(f"Temperatura actual: {temp} °C")
            if temp > 20:
                print("Temperatura > 18°C, encendiendo canal 1...")
                GPIO.output(relay_pin, GPIO.LOW)   # Encender canal 1
            else:
                print("Temperatura <= 18°C, apagando canal 1...")
                GPIO.output(relay_pin, GPIO.HIGH)  # Apagar canal 1
        else:
            print("No se pudo leer el sensor.")

        print("---- Esperando 5 segundos ----")
        time.sleep(5)
except KeyboardInterrupt:
    print("Programa detenido por el usuario.")
finally:
    GPIO.cleanup()
    print("GPIO limpiados.")

