from logica.modos import ModeManager, Modo
from logica.reglas_clima import ReglasClima
from actuator_manager import ActuatorManager
from Sensores.temp_humidity import TempHumiditySensor

class ControladorClima:
    """
    Orquestador principal que gestiona sensores, actuadores y modos de operación.
    """

    def __init__(self, sensor: TempHumiditySensor, actuador: ActuatorManager, mode_manager: ModeManager):
        self.sensor = sensor
        self.actuador = actuador
        self.mode_manager = mode_manager
        self.reglas = ReglasClima()

    def leer_sensores(self):
        """
        Lee los datos de todos los sensores conectados.
        """
        print("🛠 DEBUG: Entrando a ControladorClima.leer_sensores()")
        datos = self.sensor.read()
        print(f"🛠 DEBUG: Datos leídos: {datos}")
        return datos

    def aplicar_modo(self, datos):
        """
        Aplica la lógica según el modo actual (manual, automático, IA).
        """
        modo_actual = self.mode_manager.obtener_modo()
        print(f"🛠 DEBUG: Aplicando lógica para modo {modo_actual.value}")

        if modo_actual == Modo.MANUAL:
            print("🛠 DEBUG: En modo manual, esperando instrucciones del usuario.")
        elif modo_actual == Modo.AUTOMATICO:
            acciones = self.reglas.evaluar(datos)
            print(f"🛠 DEBUG: Acciones automáticas evaluadas: {acciones}")
        elif modo_actual == Modo.IA:
            print("🧠 Modo IA aún no implementado.")
