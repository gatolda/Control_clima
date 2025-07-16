"""
main.py - Prueba de sensores sin inicializar placa de relés
"""

import time
from logica.modos import ModeManager, Modo
from Sensores.temp_humidity import TempHumiditySensor


def seleccionar_modo_inicial():
    """Pregunta al usuario el modo de operación al inicio"""
    print("==== Sistema de Control Climático (PRUEBA SIN RELÉS) ====")
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
    print("🔄 Iniciando prueba de sensores...")
    # Configurar el modo inicial
    modo_inicial = seleccionar_modo_inicial()
    mode_manager = ModeManager(modo_inicial)
    print(f"✅ Modo actual: {mode_manager.obtener_modo().value}")

    # Inicializar solo el sensor
    print("📡 Inicializando sensor de temperatura/humedad...")
    sensor = TempHumiditySensor(pin=4)  # Ajusta el pin según tu hardware
    print("✅ Sensor inicializado correctamente.")

    # Ciclo de prueba: solo 1 iteración
    try:
        print("🔁 Leyendo sensores (1 iteración)...")
        datos = sensor.read()
        print(f"📡 Lectura sensores: {datos}")

        # Pausa para observar
        print("⏳ Esperando 2 segundos...\n")
        time.sleep(2)

        print("✅ Fin de la prueba. Sin relés ni controlador.")

    except KeyboardInterrupt:
        print("\n🛑 Programa detenido por el usuario.")


if __name__ == "__main__":
    main()
