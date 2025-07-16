"""
Conjunto de reglas para el modo automático. Evalúa datos de sensores
y devuelve acciones para los actuadores.
"""

class ReglasClima:
    """Gestiona y evalúa las reglas definidas para el modo automático."""

    def __init__(self):
        # Mapeo de acciones: {relé: estado (True=ON, False=OFF)}
        self.acciones = {}

    def evaluar(self, datos_sensores):
        """
        Analiza los datos de sensores y define acciones para los relés.
        Retorna un diccionario: {relé: estado}
        """
        temperatura = datos_sensores.get("temperature")
        humedad = datos_sensores.get("humidity")

        # Ejemplo de reglas:
        if temperatura is not None:
            if temperatura > 25.0:
                print("🌡️ Temperatura alta: Activar ventilador (Relé 1)")
                self.acciones[1] = True  # Encender relé 1
            elif temperatura < 22.0:
                print("🌡️ Temperatura baja: Apagar ventilador (Relé 1)")
                self.acciones[1] = False  # Apagar relé 1

        if humedad is not None:
            if humedad < 50.0:
                print("💧 Humedad baja: Activar humidificador (Relé 2)")
                self.acciones[2] = True  # Encender relé 2
            elif humedad > 60.0:
                print("💧 Humedad alta: Apagar humidificador (Relé 2)")
                self.acciones[2] = False  # Apagar relé 2

        return self.acciones
