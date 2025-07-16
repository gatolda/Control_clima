"""
Conjunto de reglas para el modo automático. Las reglas evalúan los
datos de sensores y producen acciones para los actuadores.
"""


class ReglasClima:
    """Gestiona y evalúa las reglas definidas por el usuario."""

    def __init__(self):
        self.reglas = []  # Aquí se almacenarían las reglas configurables

    def agregar_regla(self, regla) -> None:
        """Añade una regla a la lista interna."""
        pass

    def evaluar(self, datos_sensores):
        """
        Analiza los datos de sensores y devuelve una lista de acciones
        (por ejemplo, encender o apagar un relé).
        """
        pass
