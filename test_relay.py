import RPi.GPIO as GPIO
import time

# Pines GPIO (BCM) para cada relé
relay_pins = [26, 19, 13, 6, 5, 12, 16, 20]

# Configurar los pines GPIO
GPIO.setmode(GPIO.BCM)  # Usamos numeración BCM
GPIO.setwarnings(False)  # Desactiva advertencias

# Inicializa todos los pines como salidas y apaga los relés
print("⚡ Inicializando pines de la placa de relés...")
for pin in relay_pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)  # Relé apagado por defecto

try:
    print("🔄 Encendiendo cada relé uno por uno durante 2 segundos...")
    for idx, pin in enumerate(relay_pins):
        print(f"🔛 Activando relé {idx + 1} (GPIO {pin})")
        GPIO.output(pin, GPIO.HIGH)  # Cambia a GPIO.LOW si tu placa es activo bajo
        time.sleep(2)
        print(f"🔌 Apagando relé {idx + 1}")
        GPIO.output(pin, GPIO.LOW)
        time.sleep(1)

    print("🔛 Encendiendo todos los relés durante 3 segundos...")
    for pin in relay_pins:
        GPIO.output(pin, GPIO.HIGH)
    time.sleep(3)

    print("🔌 Apagando todos los relés...")
    for pin in relay_pins:
        GPIO.output(pin, GPIO.LOW)

except KeyboardInterrupt:
    print("\n🛑 Prueba interrumpida por el usuario.")

finally:
    print("♻️ Liberando pines GPIO...")
    GPIO.cleanup()
    print("✅ Prueba finalizada.")

