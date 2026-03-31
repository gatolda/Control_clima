#!/usr/bin/env python3
"""
Tests automatizados para ActuatorManager.
Ejecutar en Raspberry Pi: python3 -m tests.test_actuators
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import RPi.GPIO as GPIO
from core.config_loader import ConfigLoader
from core.actuator_manager import ActuatorManager
from core.gpio_setup import inicializar_gpio
import time

PASS = 0
FAIL = 0
TESTS = []


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def check(condition, msg):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {msg}")
    else:
        FAIL += 1
        print(f"  FAIL: {msg}")


# --- Tests ---

@test("TC-REL-004: Estado inicial - todos apagados")
def test_initial_state(am):
    for nombre, estado in am.estado.items():
        check(estado == False, f"{nombre} debe estar OFF al inicio")


@test("TC-REL-001: Activar rele individual")
def test_turn_on(am):
    result = am.turn_on("ventiladores")
    check(result["ok"] == True, "turn_on retorna ok=True")
    check(am.estado["ventiladores"] == True, "estado interno = True")
    pin = am.relay_pins["ventiladores"]
    # activo_bajo: ON = LOW
    check(GPIO.input(pin) == GPIO.LOW, f"GPIO pin {pin} = LOW (activo)")
    am.turn_off("ventiladores")


@test("TC-REL-002: Desactivar rele individual")
def test_turn_off(am):
    am.turn_on("ventiladores")
    result = am.turn_off("ventiladores")
    check(result["ok"] == True, "turn_off retorna ok=True")
    check(am.estado["ventiladores"] == False, "estado interno = False")
    pin = am.relay_pins["ventiladores"]
    check(GPIO.input(pin) == GPIO.HIGH, f"GPIO pin {pin} = HIGH (apagado)")


@test("TC-REL-008: Actuador inexistente")
def test_invalid_actuator(am):
    result = am.turn_on("noexiste")
    check(result["ok"] == False, "Retorna ok=False")
    check("error" in result, "Contiene mensaje de error")


@test("TC-CON-001: Calefactor bloquea aire acondicionado")
def test_conflict_heater_ac(am):
    am.turn_on("calefactor")
    result = am.turn_on("aire_acondicionado")
    check(result["ok"] == False, "AC bloqueado")
    check(am.estado["aire_acondicionado"] == False, "AC sigue OFF")
    check(am.estado["calefactor"] == True, "Calefactor sigue ON")
    am.turn_off("calefactor")


@test("TC-CON-002: Aire acondicionado bloquea calefactor")
def test_conflict_ac_heater(am):
    am.turn_on("aire_acondicionado")
    result = am.turn_on("calefactor")
    check(result["ok"] == False, "Calefactor bloqueado")
    check(am.estado["calefactor"] == False, "Calefactor sigue OFF")
    am.turn_off("aire_acondicionado")


@test("TC-CON-003: Humidificador bloquea deshumidificador")
def test_conflict_hum_dehum(am):
    am.turn_on("humidificador")
    result = am.turn_on("deshumidificador")
    check(result["ok"] == False, "Deshumidificador bloqueado")
    check(am.estado["deshumidificador"] == False, "Deshum sigue OFF")
    am.turn_off("humidificador")


@test("TC-CON-004: Deshumidificador bloquea humidificador")
def test_conflict_dehum_hum(am):
    am.turn_on("deshumidificador")
    result = am.turn_on("humidificador")
    check(result["ok"] == False, "Humidificador bloqueado")
    am.turn_off("deshumidificador")


@test("TC-CON-005: Desactivar primero permite activar segundo")
def test_conflict_release(am):
    am.turn_on("calefactor")
    am.turn_off("calefactor")
    result = am.turn_on("aire_acondicionado")
    check(result["ok"] == True, "AC permitido tras apagar calefactor")
    check(am.estado["aire_acondicionado"] == True, "AC activo")
    am.turn_off("aire_acondicionado")


@test("TC-CON-006: Actuadores sin conflicto coexisten")
def test_no_conflict(am):
    am.turn_on("ventiladores")
    am.turn_on("luz")
    am.turn_on("intractor")
    am.turn_on("filtro_carbon")
    check(am.estado["ventiladores"] == True, "Ventiladores ON")
    check(am.estado["luz"] == True, "Luz ON")
    check(am.estado["intractor"] == True, "Intractor ON")
    check(am.estado["filtro_carbon"] == True, "Filtro ON")
    am.emergency_stop()


@test("TC-REL-009: Emergency stop")
def test_emergency_stop(am):
    am.turn_on("ventiladores")
    am.turn_on("luz")
    am.turn_on("calefactor")
    am.emergency_stop()
    all_off = all(not v for v in am.estado.values())
    check(all_off, "Todos los actuadores OFF tras emergency stop")


@test("TC-REL-003: Logica activo_bajo - todos los pines")
def test_all_pins_logic(am):
    for nombre, pin in am.relay_pins.items():
        am.turn_on(nombre)
        check(GPIO.input(pin) == GPIO.LOW, f"{nombre} (pin {pin}): ON = LOW")
        am.turn_off(nombre)
        check(GPIO.input(pin) == GPIO.HIGH, f"{nombre} (pin {pin}): OFF = HIGH")
        time.sleep(0.1)


# --- Runner ---

def main():
    print("=" * 60)
    print("QA Tests - Control Climatico Invernadero")
    print("=" * 60)

    inicializar_gpio()
    config = ConfigLoader()
    config.cargar_configuracion()
    am = ActuatorManager(config)

    print()
    for name, func in TESTS:
        print(f"\n--- {name} ---")
        try:
            func(am)
        except Exception as e:
            global FAIL
            FAIL += 1
            print(f"  ERROR: {e}")

    am.emergency_stop()

    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"Resultado: {PASS}/{total} passed, {FAIL} failed")
    rate = (PASS / total * 100) if total > 0 else 0
    print(f"Pass rate: {rate:.1f}%")

    if FAIL == 0:
        print("QUALITY GATE: PASSED")
    else:
        print("QUALITY GATE: FAILED")

    print("=" * 60)
    GPIO.cleanup()
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
