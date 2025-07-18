# actuator_manager.py
import RPi.GPIO as GPIO

class ActuatorManager:
    def __init__(self, relay_pins):
        """
        Inicializa la placa de relés
        :param relay_pins: Diccionario con nombres y pines {nombre: pin}
        """
        self.relay_pins = relay_pins
        GPIO.setmode(GPIO.BOARD)  # Usa la numeración física
        self.states = {}

        print("⚡ Inicializando actuadores...")
        for nombre, pin in self.relay_pins.items():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)  # Apaga por defecto
            self.states[nombre] = False
            print(f"✅ {nombre} listo en pin {pin} (apagado)")

    def turn_on(self, nombre):
        if nombre in self.relay_pins:
            GPIO.output(self.relay_pins[nombre], GPIO.HIGH)
            self.states[nombre] = True
            print(f"🔛 Actuador '{nombre}' ENCENDIDO")
        else:
            print(f"❌ Actuador '{nombre}' no encontrado")

    def turn_off(self, nombre):
        if nombre in self.relay_pins:
            GPIO.output(self.relay_pins[nombre], GPIO.LOW)
            self.states[nombre] = False
            print(f"🔌 Actuador '{nombre}' APAGADO")
        else:
            print(f"❌ Actuador '{nombre}' no encontrado")

    def status(self):
        print("📊 Estado de actuadores:")
        for nombre, state in self.states.items():
            estado = "ON" if state else "OFF"
            print(f"  - {nombre}: {estado}")

    def cleanup(self):
        print("♻️ Liberando pines GPIO...")
        GPIO.cleanup()
