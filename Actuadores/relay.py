import RPi.GPIO as GPIO
import time

class RelayBoard:
    def __init__(self, relay_pins=None):
        """
        Inicializa la placa de relés con advertencias activadas.
        :param relay_pins: Lista de pines físicos usados para los relés.
        """
        if relay_pins is None:
            relay_pins = [12, 38]  # Pines físicos de tu hardware

        self.relay_pins = relay_pins
        GPIO.setwarnings(True)  # ⚠️ Mantenemos advertencias activas
        GPIO.setmode(GPIO.BOARD)  # Usamos numeración física de la placa

        # Limpia configuración previa de pines (evita conflictos)
        print("♻️ Liberando pines GPIO anteriores (si aplica)...")
        GPIO.cleanup()

        print("⚡ Inicializando placa de relés...")
        for pin in self.relay_pins:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
            print(f"✅ Pin físico {pin} configurado como salida y apagado por defecto.")

    def activar(self, canal):
        """
        Activa un relé específico.
        :param canal: Índice del canal (0 = primer relé).
        """
        if canal < 0 or canal >= len(self.relay_pins):
            print(f"❌ Canal {canal} fuera de rango")
            return
        GPIO.output(self.relay_pins[canal], GPIO.HIGH)
        print(f"⚡ Relé {canal} activado (pin físico {self.relay_pins[canal]})")

    def desactivar(self, canal):
        """
        Desactiva un relé específico.
        :param canal: Índice del canal (0 = primer relé).
        """
        if canal < 0 or canal >= len(self.relay_pins):
            print(f"❌ Canal {canal} fuera de rango")
            return
        GPIO.output(self.relay_pins[canal], GPIO.LOW)
        print(f"🔌 Relé {canal} desactivado (pin físico {self.relay_pins[canal]})")

    # Adaptadores con nombres en inglés
    turn_on = activar
    turn_off = desactivar

    def apagar_todos(self):
        """Apaga todos los relés."""
        print("🔌 Apagando todos los relés...")
        for pin in self.relay_pins:
            GPIO.output(pin, GPIO.LOW)
        print("✅ Todos los relés apagados.")

    def cleanup(self):
        """Limpia la configuración de los pines GPIO."""
        print("♻️ Liberando pines GPIO...")
        GPIO.cleanup()
