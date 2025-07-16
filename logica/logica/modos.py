"""
Definición de los modos de funcionamiento y gestor para cambiar entre ellos.
"""

from enum import Enum


class Modo(Enum):
    """Modos disponibles de operación."""
    MANUAL = "manual"
    AUTOMATICO = "automatico"
    IA = "ia"


class ModeManager:
    """
    Mantiene el modo actual del sistema y permite cambiarlo dinámicamente.
    """

    def __init__(self, modo_inicial: Modo = Modo.MANUAL):
        self.modo_actual = modo_inicial

    def seleccionar_modo_inicial(self, modo: Modo) -> None:
        """Establece el modo activo al iniciar el sistema."""
        self.modo_actual = modo

    def cambiar_modo(self, nuevo_modo: Modo) -> None:
        """Cambia el modo en tiempo de ejecución desde la interfaz."""
        self.modo_actual = nuevo_modo

    def obtener_modo(self) -> Modo:
        """Devuelve el modo de operación vigente."""
        return self.modo_actual
