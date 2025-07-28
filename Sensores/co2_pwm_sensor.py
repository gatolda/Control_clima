import RPi.GPIO as GPIO
import time

class CO2PWMSensor:
    def __init__(self, pin):
        self.pin = pin
        GPIO.setup(self.pin, GPIO.IN)
        print(f"🌿 Sensor PWM CO₂ inicializado en pin físico {self.pin} (BOARD)")

    def read(self):
        try:
            GPIO.wait_for_edge(self.pin, GPIO.RISING, timeout=5000)
            start = time.time()

            GPIO.wait_for_edge(self.pin, GPIO.FALLING, timeout=5000)
            end = time.time()

            pulse_duration = (end - start) * 1_000_000  # en microsegundos

            # Fórmula de conversión PWM (según datasheet MH-Z19D)
            co2_ppm = int((pulse_duration - 2000) * 5000 / 1000)

            return {"co2": co2_ppm}
        except Exception as e:
            print(f"⚠️ Error leyendo CO₂ por PWM: {e}")
            return {"co2": None}
