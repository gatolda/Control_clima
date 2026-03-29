# actuator_manager.py
import RPi.GPIO as GPIO

class ActuatorManager:
    def __init__(self, config):
        self.relay_pins = config.obtener("actuadores.rele_board.pines", {})
        self.relay_mode = config.obtener("actuadores.rele_board.tipo_activacion", "activo_bajo")
        self.estado = {nombre: False for nombre in self.relay_pins}

        print("Inicializando actuadores...")
        GPIO.setmode(GPIO.BOARD)
        for nombre, pin in self.relay_pins.items():
            print(f"Configurando {nombre} en pin {pin}...")
            GPIO.setup(pin, GPIO.OUT)
            if self.relay_mode == "activo_bajo":
                GPIO.output(pin, GPIO.HIGH)
            else:
                GPIO.output(pin, GPIO.LOW)

    def turn_on(self, nombre):
        if nombre in self.relay_pins:
            pin = self.relay_pins[nombre]
            GPIO.output(pin, GPIO.LOW if self.relay_mode == "activo_bajo" else GPIO.HIGH)
            self.estado[nombre] = True
            print(f"{nombre} ACTIVADO")
        else:
            print(f"Actuador '{nombre}' no encontrado.")

    def turn_off(self, nombre):
        if nombre in self.relay_pins:
            pin = self.relay_pins[nombre]
            GPIO.output(pin, GPIO.HIGH if self.relay_mode == "activo_bajo" else GPIO.LOW)
            self.estado[nombre] = False
            print(f"{nombre} DESACTIVADO")
        else:
            print(f"Actuador '{nombre}' no encontrado.")

    def status(self):
        return self.estado

    def cleanup(self):
        print("Liberando GPIO...")
        GPIO.cleanup()
