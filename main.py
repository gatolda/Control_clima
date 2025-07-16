"""
main.py - Programa principal para el sistema de control climático (versión debug)
"""

import time
from logica.modos import ModeManager, Modo
from logica.controlador import ControladorClima
from Actuadores.relay import RelayBoard
from Sensores.temp_humidity import TempHumiditySensor


def seleccionar_modo_inicial():
    """Pregunta al usuario el modo de operación al inicio"""
    print("==== Sistema de Control Climático ====")
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
    print("🔄 Iniciando sistema...")
    # Configurar el modo inicial
    modo_inicial = seleccionar_modo_inicial()
    mode_manager = ModeManager(modo_inicial)
    print(f"✅ Modo actual: {mode_manager.obtener_modo().value}")

    # Inicializar sensores y actuadores
    print("📡 Inicializando sensores y actuadores...")
    sensor = TempHumiditySensor(pin=4)  # Ajusta el pin según tu hardware
    actuador = RelayBoard(relay_pins=[12, 38])  # Pines para CH1 y CH2
    controlador = ControladorClima(sensor, actuador, mode_manager)
    print("✅ Sensores y actuadores inicializados correctamente.")

    # Ciclo de prueba: solo 1 iteración para debug
    try:
        print("🔁 Iniciando ciclo de lectura y control (1 iteración)...")
        for _ in range(1):
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
