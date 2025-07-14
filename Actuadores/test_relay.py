import RPi.GPIO as GPIO
import time

# Define los pines GPIO usados (ajusta si los cambiaste)
relay_pins = [18, 20, 21, 23]  # [Canal1, Canal2, Canal3, Canal4]

# Configura los pines
GPIO.setmode(GPIO.BCM)
for pin in relay_pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)  # Apaga todos al inicio (puede ser HIGH para algunas placas)

try:
    print("Prueba: Encendiendo cada relé por 2 segundos...")
    for idx, pin in enumerate(relay_pins):
        print(f"Encendiendo canal {idx+1} (GPIO{pin})")
        GPIO.output(pin, GPIO.HIGH)  # Cambia a GPIO.LOW si tu placa activa en bajo
        time.sleep(2)
        print(f"Apagando canal {idx+1}")
        GPIO.output(pin, GPIO.LOW)
        time.sleep(1)

    print("Encendiendo todos los canales por 3 segundos...")
    for pin in relay_pins:
        GPIO.output(pin, GPIO.HIGH)
    time.sleep(3)
    print("Apagando todos los canales.")
    for pin in relay_pins:
        GPIO.output(pin, GPIO.LOW)

except KeyboardInterrupt:
    print("Prueba interrumpida por el usuario.")
finally:
    GPIO.cleanup()
    
    
		
