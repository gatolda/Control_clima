import sys
import types
import unittest
import sys
import types
import unittest
from pathlib import Path


class FakeGPIO:
    BOARD = "BOARD"
    OUT = "OUT"
    HIGH = 1
    LOW = 0

    def __init__(self):
        self.calls = []

    def setwarnings(self, flag):
        pass

    def setmode(self, mode):
        self.calls.append(("setmode", mode))

    def setup(self, pin, mode):
        self.calls.append(("setup", pin, mode))

    def output(self, pin, value):
        self.calls.append(("output", pin, value))

    def cleanup(self):
        self.calls.append(("cleanup",))


fake_gpio = FakeGPIO()
sys.modules["RPi"] = types.SimpleNamespace(GPIO=fake_gpio)
sys.modules["RPi.GPIO"] = fake_gpio

sys.path.append(str(Path(__file__).resolve().parents[1]))
from actuator_manager import ActuatorManager


class DummyConfig:
    def obtener(self, clave, por_defecto=None):
        datos = {
            "actuadores.rele_board.pines": {"fan": 7},
            "actuadores.rele_board.tipo_activacion": "activo_bajo",
        }
        return datos.get(clave, por_defecto)


class ActuatorManagerTest(unittest.TestCase):
    def test_turn_on_off(self):
        fake_gpio.calls = []
        am = ActuatorManager(DummyConfig())
        am.turn_on("fan")
        am.turn_off("fan")
        self.assertIn(("output", 7, fake_gpio.LOW), fake_gpio.calls)
        self.assertIn(("output", 7, fake_gpio.HIGH), fake_gpio.calls)


if __name__ == "__main__":
    unittest.main()
