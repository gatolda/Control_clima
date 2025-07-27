import RPi.GPIO as GPIO
import time

class CO2PWMSensor:
    def __init__(self, pin=17):
        self.pin = pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.IN)
    
    def read(self):
        try:
            # Espera a que comience el pulso
            GPIO.wait_for_edge(self.pin, GPIO.FALLING)
            start = time.time()

            # Espera a que termine el pulso
            GPIO.wait_for_edge(self.pin, GPIO.RISING)
            end = time.time()

            # Calcula duración del pulso en microsegundos
            duration = (end - start) * 1_000_000

            # Conversión PWM a ppm (según hoja técnica del MH-Z19)
            ppm = (duration - 2000) * 5000 / (10000 - 2000)

            return {
                "co2": int(ppm),
                "pulse": int(duration)
            }
        except Exception as e:
            print(f"⚠️ Error en lectura PWM: {e}")
            return None

    def cleanup(self):
        GPIO.cleanup(self.pin)
