import pigpio
import time

GPIO_PIN = 17  # PWM del MH-Z19D conectado a GPIO17 (pin físico 11)

pi = pigpio.pi()
if not pi.connected:
    print("❌ No se pudo conectar a pigpio.")
    exit()

def read_pwm():
    print("📡 Leyendo señal PWM del sensor MH-Z19D...")
    try:
        for i in range(10):  # Leer 10 muestras
            pi.set_mode(GPIO_PIN, pigpio.INPUT)
            pi.set_pull_up_down(GPIO_PIN, pigpio.PUD_OFF)

            # Esperar flanco de bajada
            pi.wait_for_edge(GPIO_PIN, pigpio.FALLING_EDGE)
            start = pi.get_current_tick()

            # Esperar flanco de subida
            pi.wait_for_edge(GPIO_PIN, pigpio.RISING_EDGE)
            duration = pigpio.tickDiff(start, pi.get_current_tick())  # duración en microsegundos

            co2_ppm = (duration - 2000) * 5000 / 2000
            co2_ppm = round(co2_ppm)
            print(f"🌿 CO₂ estimado: {co2_ppm} ppm | Pulso: {duration} µs")
            time.sleep(2)
    except KeyboardInterrupt:
        print("🛑 Interrumpido por el usuario")
    finally:
        pi.stop()

read_pwm()
