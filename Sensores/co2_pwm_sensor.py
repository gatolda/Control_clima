import RPi.GPIO as GPIO
import time

class CO2PWMSensor:
    def __init__(self, pin):
        self.pin = pin
        GPIO.setup(self.pin, GPIO.IN)
        print(f"Sensor PWM CO2 inicializado en pin fisico {self.pin} (BOARD)")

    def read(self):
        try:
            GPIO.wait_for_edge(self.pin, GPIO.RISING, timeout=5000)
            start = time.time()

            GPIO.wait_for_edge(self.pin, GPIO.FALLING, timeout=5000)
            end = time.time()

            pulse_duration_us = (end - start) * 1_000_000

            # Formula MH-Z19D: CO2 = 5000 * (TH_ms - 2) / 1000
            # TH_ms = pulse_duration_us / 1000
            co2_ppm = int((pulse_duration_us - 2000) * 5000 / 1_000_000)

            if co2_ppm < 0:
                co2_ppm = 0

            return {"co2": co2_ppm}
        except Exception as e:
            print(f"Error leyendo CO2 por PWM: {e}")
            return {"co2": None}
