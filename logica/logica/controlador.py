"""
Controlador central del sistema. Se encarga de leer sensores y
ejecutar acciones sobre los actuadores según el modo de operación.
"""

from logica.modos import ModeManager, Modo
from logica.reglas_clima import ReglasClima


class ControladorClima:
    """
    Orquesta sensores, modos de operación y actuadores.
    """

    def __init__(self, sensor, actuador, mode_manager: ModeManager):
        self.sensor = sensor
        self.actuador = actuador
        self.mode_manager = mode_manager
        self.reglas = ReglasClima()

    def leer_sensores(self):
        """
        Obtiene y devuelve las lecturas del sensor de temperatura/humedad.
        Si hay un error, devuelve None y lo reporta en consola.
        """
        datos = self.sensor.read()
        if datos.get("status") != "OK":
            print("❌ Error al leer el sensor")
            return None
        return datos

    def aplicar_modo(self, datos_sensores):
        """
        Aplica la lógica según el modo de operación activo.
        """
        modo = self.mode_manager.obtener_modo()
        if datos_sensores is None:
            print("⚠️ No se aplicará lógica: datos de sensores no disponibles.")
            return

        if modo == Modo.MANUAL:
            print("🕹️ Modo Manual: no se activan relés automáticamente.")
        elif modo == Modo.AUTOMATICO:
            print("🤖 Modo Automático: evaluando reglas...")
            acciones = self.reglas.evaluar(datos_sensores)
            for rele, estado in acciones.items():
                self.actuador.set_relay(rele, estado)
        elif modo == Modo.IA:
            print("🧠 Modo IA: funcionalidad pendiente de implementación.")
        else:
            print(f"⚠️ Modo desconocido: {modo}")
