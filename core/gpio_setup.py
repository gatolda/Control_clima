# gpio_setup.py
import RPi.GPIO as GPIO

def inicializar_gpio(modo="BOARD"):
    """
    Configura el modo de numeración de pines.
    modo: "BOARD" o "BCM"
    """
    if modo.upper() == "BOARD":
        GPIO.setmode(GPIO.BOARD)
    elif modo.upper() == "BCM":
        GPIO.setmode(GPIO.BCM)
    else:
        raise ValueError("Modo inválido: usa 'BOARD' o 'BCM'")
    print(f"✅ GPIO inicializado en modo {modo}")

def limpiar_gpio():
    """
    Libera los pines GPIO
    """
    GPIO.cleanup()
    print("♻️ GPIO liberado correctamente.")
