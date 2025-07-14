# Actuadores/relay.py

import RPi.GPIO as GPIO
import time

class RelayBoard:
    def __init__(self, relay_pins):
        """
        relay_pins: lista de GPIOs donde está conectado cada canal [canal1, canal2, canal3, canal4]
        """
        self.relay_pins = relay_pins
        GPIO.setmode(GPIO.BCM)
        for pin in self.relay_pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)  # Inicialmente apagado

    def on(self, channel):
        """
        channel: número de canal (1 a 4)
        """
        pin = self.relay_pins[channel - 1]
        GPIO.output(pin, GPIO.HIGH)
        print(f"Relay canal {channel} (pin {pin}) encendido.")

    def off(self, channel):
        pin = self.relay_pins[channel - 1]
        GPIO.output(pin, GPIO.LOW)
        print(f"Relay canal {channel} (pin {pin}) apagado.")

    def all_on(self):
        for pin in self.relay_pins:
            GPIO.output(pin, GPIO.HIGH)

    def all_off(self):
		
        for pin in self.relay_pins:
            GPIO.output(pin, GPIO.LOW)

    def cleanup(self):
        GPIO.cleanup()
