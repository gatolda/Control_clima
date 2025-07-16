import RPi.GPIO as GPIO
import time

# ⚡ Pines que controla la placa de relés (ajusta según tu hardware)
relay_pins = [12, 38]  # [Canal1, Canal2]

# Configura los pines
GPIO.setwarnings(False)  # Desactiva advertencias sobre pines ya usados
GPIO.setmode(GPIO.BOARD)  # Usa numeración física de la placa

for pin in relay_pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)  # Apaga todos los relés al inicio
print("✅ Pines configurados correctamente.")

try:
    print("🔁 Prueba: Encendiendo cada relé por 2 segundos...")
    for idx, pin in enumerate(relay_pins):
        print(f"⚡ Encendiendo canal {idx+1} (pin {pin})")
        GPIO.output(pin, GPIO.HIGH)  # Cambia a GPIO.LOW si tu placa activa en bajo
        time.sleep(2)
        print(f"🔌 Apagando canal {idx+1}")
        GPIO.output(pin, GPIO.LOW)
        time.sleep(1)

    print("🔁 Encendiendo todos los relés por 3 segundos...")
    for pin in relay_pins:
        GPIO.output(pin, GPIO.HIGH)
    time.sleep(3)
    print("🔌 Apagando todos los relés.")
    for pin in relay_pins:
        GPIO.output(pin, GPIO.LOW)

except KeyboardInterrupt:
    print("🛑 Prueba interrumpida por el usuario.")
finally:
    GPIO.cleanup()
    print("✅ Pines liberados (GPIO cleanup).")
