#!/usr/bin/env python3
"""
Test de Reles - Control Climatico Invernadero
Permite probar cada rele individualmente o todos en secuencia.

Uso:
  python3 test_relay.py          # Menu interactivo
  python3 test_relay.py 3        # Probar rele 3
  python3 test_relay.py todos    # Secuencia 1 al 8
  python3 test_relay.py on       # Todos ON por 5 seg
"""
import RPi.GPIO as GPIO
import time
import sys

# Mapa de reles verificado: numero de rele -> pin BOARD
RELES = {
    1: 37,
    2: 35,
    3: 33,
    4: 31,
    5: 29,
    6: 32,
    7: 36,
    8: 38,
}

def setup():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    for r, pin in RELES.items():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)  # HIGH = apagado (activo_bajo)

def activar(rele, duracion=3):
    pin = RELES[rele]
    print(f"  Rele {rele} (pin {pin}) -> ON")
    GPIO.output(pin, GPIO.LOW)   # LOW = encendido (activo_bajo)
    time.sleep(duracion)
    GPIO.output(pin, GPIO.HIGH)  # HIGH = apagado
    print(f"  Rele {rele} -> OFF")

def test_individual():
    while True:
        print("\n--- Test Individual ---")
        print("Ingresa numero de rele (1-8), 'todos', o 'salir':")
        entrada = input("> ").strip().lower()

        if entrada in ("salir", "q"):
            break
        elif entrada == "todos":
            test_secuencia()
        elif entrada.isdigit() and 1 <= int(entrada) <= 8:
            activar(int(entrada))
        else:
            print("  Opcion no valida. Usa 1-8, 'todos' o 'salir'")

def test_secuencia():
    print("\n--- Test Secuencia (1 al 8) ---")
    for r in range(1, 9):
        activar(r, 2)
        time.sleep(0.5)
    print("  Secuencia completada.")

def test_todos_on():
    print("\n--- Todos ON por 5 segundos ---")
    for r, pin in RELES.items():
        GPIO.output(pin, GPIO.LOW)   # LOW = encendido (activo_bajo)
        print(f"  Rele {r} -> ON")
        time.sleep(0.3)
    print("  Esperando 5 segundos...")
    time.sleep(5)
    for r, pin in RELES.items():
        GPIO.output(pin, GPIO.HIGH)  # HIGH = apagado
    print("  Todos OFF")

def menu():
    print("=" * 40)
    print("  TEST DE RELES - Invernadero")
    print("=" * 40)
    print()
    print("  1. Test individual (elegir rele)")
    print("  2. Test secuencia (1 al 8)")
    print("  3. Todos ON por 5 segundos")
    print("  4. Salir")
    print()

    while True:
        opcion = input("Opcion> ").strip()
        if opcion == "1":
            test_individual()
        elif opcion == "2":
            test_secuencia()
        elif opcion == "3":
            test_todos_on()
        elif opcion in ("4", "q"):
            break
        else:
            print("  Opcion no valida")

        print()
        print("  1=Individual  2=Secuencia  3=Todos ON  4=Salir")

if __name__ == "__main__":
    try:
        setup()

        if len(sys.argv) > 1:
            arg = sys.argv[1].lower()
            if arg == "todos":
                test_secuencia()
            elif arg == "on":
                test_todos_on()
            elif arg.isdigit() and 1 <= int(arg) <= 8:
                activar(int(arg))
            else:
                print(f"Uso: python3 test_relay.py [1-8|todos|on]")
        else:
            menu()
    except KeyboardInterrupt:
        print("\n  Cancelado")
    finally:
        GPIO.cleanup()
        print("  GPIO liberado")
