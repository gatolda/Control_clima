import time
from logica.modos import ModeManager, Modo
from logica.controlador import ControladorClima
from Actuadores.relay import RelayBoard
from Sensores.temp_humidity import TempHumiditySensor

def seleccionar_modo_inicial():
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
        print("⚠️ Opción inválida. Se usará Modo Manual.")
        return Modo.MANUAL

def main():
    modo_inicial = seleccionar_modo_inicial()
    mode_manager = ModeManager(modo_inicial)
    print(f"✅ Modo actual: {mode_manager.obtener_modo().value}")

    # Inicializar componentes
    sensor = TempHumiditySensor(pin=4)
    actuador = RelayBoard(relay_pins=[12, 38])
    controlador = ControladorClima(sensor, actuador, mode_manager)

    # Bucle principal
    try:
        while True:
            datos = controlador.leer_sensores()
            controlador.aplicar_modo(datos)
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n🛑 Programa detenido por el usuario.")

if __name__ == "__main__":
    main()
