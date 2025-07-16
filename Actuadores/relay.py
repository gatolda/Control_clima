import RPi.GPIO as GPIO

class RelayBoard:
    """
    Clase para controlar una placa de relés conectada a la Raspberry Pi.
    """

    def __init__(self, relay_pins=None):
        """
        Inicializa la placa de relés con los pines especificados.

        :param relay_pins: Lista de números de pin GPIO.
        """
        if relay_pins is None:
            # Puedes cambiar estos pines según tu hardware
            relay_pins = [12, 38]

        self.relay_pins = relay_pins

        # Configurar GPIO
        GPIO.setmode(GPIO.BOARD)

        # Limpia configuración previa de los pines
        print("⚡ Limpieza previa de pines GPIO...")
        GPIO.cleanup()

        # Configurar cada pin solo si no está configurado ya
        for pin in self.relay_pins:
            if GPIO.gpio_function(pin) != GPIO.OUT:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)  # Relé apagado por defecto
        print(f"✅ Relés inicializados en pines: {self.relay_pins}")

    def activar(self, canal):
        """
        Activa un canal de relé específico.
        :param canal: Número de canal (basado en la lista relay_pins).
        """
        if canal < 0 or canal >= len(self.relay_pins):
            print(f"❌ Canal {canal} fuera de rango")
            return
        GPIO.output(self.relay_pins[canal], GPIO.HIGH)
        print(f"⚡ Relé {canal} activado (pin {self.relay_pins[canal]})")

    def desactivar(self, canal):
        """
        Desactiva un canal de relé específico.
        :param canal: Número de canal (basado en la lista relay_pins).
        """
        if canal < 0 or canal >= len(self.relay_pins):
            print(f"❌ Canal {canal} fuera de rango")
            return
        GPIO.output(self.relay_pins[canal], GPIO.LOW)
        print(f"🔌 Relé {canal} desactivado (pin {self.relay_pins[canal]})")

    def cleanup(self):
        """
        Libera los pines GPIO utilizados.
        """
        print("⚡ Liberando los pines GPIO de la placa de relés...")
        GPIO.cleanup()
