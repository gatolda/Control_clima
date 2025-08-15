import unittest
from unittest.mock import patch

import unittest
from unittest.mock import patch

from modos.manual_mode import ManualMode


class DummySensorReader:
    def read_all(self):
        return {}


class StubActuatorManager:
    def __init__(self):
        self.actions = []

    def turn_on(self, name):
        self.actions.append(("on", name))

    def turn_off(self, name):
        self.actions.append(("off", name))


class ManualModeTest(unittest.TestCase):
    def test_run_commands(self):
        actuator = StubActuatorManager()
        manual = ManualMode(actuator, DummySensorReader())
        with patch("builtins.input", side_effect=["on fan", "off fan", "exit"]):
            manual.run()
        self.assertEqual(actuator.actions, [("on", "fan"), ("off", "fan")])


if __name__ == "__main__":
    unittest.main()
