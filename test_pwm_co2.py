import RPi.GPIO as GPIO
import time

PWM_PIN = 17  # GPIO17 (pin físico 11)

GPIO.setmode(GPIO.BCM)
GPIO.setup(PWM_PIN, GPIO.IN)

def medir_pwm():
    try:
        GPIO.wait_for_edge(PWM_PIN, GPIO.FALLING, timeout=5000)
        start = time.time()
        GPIO.wait_for_edge(PWM_PIN, GPIO.RISING, timeout=5000)
        low_duration = time.time() - start

        start = time.time()
        GPIO.wait_for_edge(PWM_PIN, GPIO.FALLING, timeout=5000)
        high_duration = time.time() - start

        tl = low_duration * 1_000_000  # microsegundos
        th = high_duration * 1_000_000

        total = th + tl
        if total == 0:
            return None

        # Fórmula oficial del datasheet
        ppm = 5000 * (th - 2000) / (total - 4000)
        return round(ppm, 2), int(th), int(tl)

    except Exception as e:
        print(f"⚠️ Error: {e}")
        return None

print("📡 Iniciando lectura por PWM del MH-Z19D...")
try:
    while True:
        resultado = medir_pwm()
        if resultado:
            ppm, th, tl = resultado
            print(f"🌿 CO₂ estimado: {ppm} ppm | Pulso ALTO: {th} µs | Pulso BAJO: {tl} µs")
        else:
            print("❌ No se pudo obtener lectura válida")
        time.sleep(3)

except KeyboardInterrupt:
    print("\n🛑 Lectura interrumpida por el usuario.")
finally:
    GPIO.cleanup()

