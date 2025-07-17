"""
Controlador central del sistema. Se encarga de leer sensores y
ejecutar acciones sobre los actuadores según el modo de operación.
"""

from logica.modos import ModeManager, Modo
from logica.reglas_clima import ReglasClima
# Ejemplo de integración con otros paquetes
from Actuadores.relay import RelayBoard
from Sensores.temp_humidity import TempHumiditySensor


class ControladorClima:
    """
    Orquesta sensores, modos de operación y actuadores.
    """

    def __init__(
        self,
        sensor: TempHumiditySensor,
        actuador: RelayBoard,
        mode_manager: ModeManager,
    ):
        self.sensor = sensor
        self.actuador = actuador
        self.mode_manager = mode_manager
        self.reglas = ReglasClima()

    def iniciar(self) -> None:
        """Inicia el ciclo principal de lectura y control."""
        pass

    def leer_sensores(self):
        """Obtiene y normaliza las lecturas de todos los sensores."""
        pass

    def aplicar_modo(self, datos):
        """
        Aplica la lógica correspondiente al modo actual
        (manual, automático o IA).
        """
        pass

    def cambiar_modo(self, nuevo_modo: Modo) -> None:
        """Permite cambiar el modo desde la GUI o web."""
        self.mode_manager.cambiar_modo(nuevo_modo)
