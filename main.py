"""
main.py - Sistema de control climático (MODO SEGURO)
Este script no activa los relés físicamente. En su lugar,
imprime las acciones que tomaría para evitar reinicios o cuelgues.
"""

import time
from logica.modos import ModeManager, Modo
from logica.controlador import ControladorClima
from Sensores.temp_humidity import TempHumiditySensor


class RelayBoardSimulada:
    """Simula una placa de relés. Imprime acciones en lugar de activar pines GPIO."""

    def __init__(self, relay_pins):
        self.relay_pins = relay_pins
        self.relay_states = {pin: False for pin in relay_pins}
        print(f"⚡ [SIMULADO] Placa de relés inicializada en pines: {self.relay_pins}")

    def set_relay(self, relay_number, state):
        """Simula encender o apagar un relé."""
        pin = self.relay_pins[relay_number - 1]
        self.relay_states[pin] = state
        action = "ON" if state else "OFF"
        print(f"🔌 [SIMULADO] Relé {relay_number} (GPIO {pin}): {action}")


def seleccionar_modo_inicial():
    """Pregunta al usuario el modo de operación al inicio"""
    print("==== Sistema de Control Climático (MODO SEGURO) ====")
    print("Selecciona el modo de operación:")
    print("1 - Manual")
    print("2 - Automático")
    opcion = input("Ingresa el número de opción: ")

    if opcion == "1":
        return Modo.MANUAL
    elif opcion == "2":
        return Modo.AUTOMATICO
    else:
        print("⚠️ Opción inválida. Iniciando en modo Manual por defecto.")
        return Modo.MANUAL


def main():
    print("🔄 Iniciando sistema de control climático (modo seguro)...")
    # Configurar el modo inicial
    modo_inicial = seleccionar_modo_inicial()
    mode_manager = ModeManager(modo_inicial)
    print(f"✅ Modo actual: {mode_manager.obtener_modo().value}")

    # Inicializar sensores y relés simulados
    print("📡 Inicializando sensores y placa de relés simulada...")
    sensor = TempHumiditySensor(pin=4)  # Ajusta el pin según tu hardware
    actuador = RelayBoardSimulada(relay_pins=[12, 38])  # Simulación en CH1 y CH2
    controlador = ControladorClima(sensor, actuador, mode_manager)
    print("✅ Sensores y relés simulados inicializados correctamente.")

    # Ciclo principal
    try:
        while True:
            # Leer sensores
            datos = controlador.leer_sensores()
            print(f"📡 Lectura sensores: {datos}")

            # Aplicar lógica según el modo
            controlador.aplicar_modo(datos)
            print("✅ Lógica aplicada según el modo actual.")

            # Pausa entre ciclos
            print("⏳ Esperando 2 segundos...\n")
            time.sleep(2)

    except KeyboardInterrupt:
        print("\n🛑 Programa detenido por el usuario.")


if __name__ == "__main__":
    main()
