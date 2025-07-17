"""
main.py
Programa principal que carga la configuración y muestra información básica
"""

from config_loader import ConfigLoader
import time

def mostrar_configuracion(config):
    print("\n==== CONFIGURACIÓN DEL SISTEMA ====")
    # Mostrar Sensores
    print("📡 Sensores:")
    sensores = config.obtener("sensores", {})
    for nombre, datos in sensores.items():
        print(f"  - {nombre.capitalize()}: Pin={datos.get('pin')} Tipo={datos.get('tipo')}")

    # Mostrar Actuadores
    print("⚡ Actuadores:")
    actuadores = config.obtener("actuadores", {})
    for nombre, datos in actuadores.items():
        if nombre == "rele_board":
            print(f"  - Placa de relés: Pines={datos.get('pines')} modo={datos.get('modo')}")
        else:
            print(f"  - {nombre.capitalize()}")

    print("====================================\n")

def main():
    # Cargar configuración
    config = ConfigLoader()
    try:
        config.cargar_configuracion()
    except Exception as e:
        print(f"❌ Error cargando configuración: {e}")
        return

    # Mostrar la configuración cargada
    mostrar_configuracion(config)

    # Ciclo principal (simulación)
    print("🔄 Iniciando ciclo principal...")
    try:
        while True:
            # Aquí en el futuro leeremos sensores y controlaremos actuadores
            print("📡 Leyendo sensores... (simulado)")
            print("⚡ Gestionando actuadores... (simulado)")
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n🛑 Programa detenido por el usuario.")

if __name__ == "__main__":
    main()
