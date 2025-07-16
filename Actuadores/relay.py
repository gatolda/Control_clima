import RPi.GPIO as GPIO

class RelayBoard:
    def __init__(self, relay_pins=None):
        if relay_pins is None:
            relay_pins = [12, 38]  # Ajusta según tu hardware

        self.relay_pins = relay_pins
        GPIO.setmode(GPIO.BOARD)

        print("⚡ Inicializando placa de relés...")
        for pin in self.relay_pins:
            current_function = GPIO.gpio_function(pin)
            if current_function != GPIO.OUT:
                print(f"🛠 Configurando pin {pin} como salida (anterior: {current_function})")
                GPIO.setup(pin, GPIO.OUT)
            else:
                print(f"✅ Pin {pin} ya está configurado como salida")
            GPIO.output(pin, GPIO.LOW)  # Relé apagado por defecto

    def activar(self, canal):
        if canal < 0 or canal >= len(self.relay_pins):
            print(f"❌ Canal {canal} fuera de rango")
            return
        GPIO.output(self.relay_pins[canal], GPIO.HIGH)
        print(f"⚡ Relé {canal} activado (pin {self.relay_pins[canal]})")

    def desactivar(self, canal):
        if canal < 0 or canal >= len(self.relay_pins):
            print(f"❌ Canal {canal} fuera de rango")
            return
        GPIO.output(self.relay_pins[canal], GPIO.LOW)
        print(f"🔌 Relé {canal} desactivado (pin {self.relay_pins[canal]})")

    def cleanup(self):
        print("⚡ Liberando los pines GPIO de la placa de relés...")
        GPIO.cleanup()
