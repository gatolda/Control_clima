import RPi.GPIO as GPIO
import time

class CO2PWMSensor:
    def __init__(self, pin):
        self.pin = pin
        GPIO.setmode(GPIO.BOARD)  # usamos BOARD para mantener consistencia
        GPIO.setup(self.pin, GPIO.IN)
        print(f"🌿 Sensor PWM CO₂ inicializado en pin físico {self.pin} (BOARD)")

    def read_co2(self):
        try:
            # Espera a flanco de bajada y subida para medir duración del pulso alto
            GPIO.wait_for_edge(self.pin, GPIO.FALLING)
            start = time.time()
            GPIO.wait_for_edge(self.pin, GPIO.RISING)
            duration = time.time() - start

            high_level_time = duration * 1_000_000  # en microsegundos
            co2_concentration = self._calculate_co2(high_level_time)

            return int(co2_concentration)
        except Exception as e:
            print(f"⚠️ Error leyendo PWM: {e}")
            return None

    def _calculate_co2(self, high_level_time_us):
        """
        Calcula la concentración de CO₂ a partir del tiempo de pulso.
        Fórmula del datasheet para modo PWM:
        ppm = 5000 * (Th - 2000us) / (Th + Tl - 4000us)
        En este caso, Th es el pulso alto y asumimos ciclo total de 1004ms (1004000us)
        """
        Th = high_level_time_us
        cycle_time_us = 1004000
        Tl = cycle_time_us - Th

        if Th + Tl < 4000:
            return 0  # fuera de rango

        ppm = 5000 * (Th - 2000) / (Th + Tl - 4000)
        return max(0, min(ppm, 5000))  # limitado entre 0 y 5000 ppm
