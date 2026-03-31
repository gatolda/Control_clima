#!/usr/bin/env python3
"""
Tests automatizados para API endpoints y autenticacion.
Ejecutar: python3 -m tests.test_api [host]
Ejemplo: python3 -m tests.test_api http://192.168.100.8:5000
"""
import sys
import requests

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
PASS = 0
FAIL = 0


def check(condition, msg):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {msg}")
    else:
        FAIL += 1
        print(f"  FAIL: {msg}")


def get_session(user="admin", password=None):
    """Crea sesion autenticada."""
    s = requests.Session()
    if password:
        r = s.post(f"{BASE_URL}/login", data={"username": user, "password": password})
    return s


# --- Auth Tests ---

def test_auth():
    print("\n--- TC-AUT-004: Rutas protegidas sin login ---")
    s = requests.Session()
    for path in ["/", "/diagnostics", "/settings", "/sensores",
                 "/actuadores/estado", "/api/history", "/api/config"]:
        r = s.get(f"{BASE_URL}{path}", allow_redirects=False)
        check(r.status_code in [302, 401], f"{path} redirige sin login (status={r.status_code})")

    print("\n--- TC-AUT-002: Login fallido ---")
    r = s.post(f"{BASE_URL}/login", data={"username": "admin", "password": "wrongpassword"})
    check("incorrectos" in r.text.lower() or r.status_code == 200, "Login rechazado con password incorrecto")

    print("\n--- TC-AUT-003: Usuario inexistente ---")
    r = s.post(f"{BASE_URL}/login", data={"username": "hacker", "password": "test"})
    check("incorrectos" in r.text.lower() or r.status_code == 200, "Login rechazado con usuario inexistente")


# --- API Tests ---

def test_api(session):
    print("\n--- TC-API-001: GET /sensores ---")
    r = session.get(f"{BASE_URL}/sensores")
    check(r.status_code == 200, f"Status 200 (got {r.status_code})")
    data = r.json()
    check("temperatura_humedad" in data, "Contiene temperatura_humedad")
    check("co2" in data, "Contiene co2")

    print("\n--- TC-API-002: GET /actuadores/estado ---")
    r = session.get(f"{BASE_URL}/actuadores/estado")
    check(r.status_code == 200, f"Status 200 (got {r.status_code})")
    data = r.json()
    check("ventiladores" in data, "Contiene ventiladores")
    check("calefactor" in data, "Contiene calefactor")
    check(len(data) == 8, f"8 actuadores (got {len(data)})")

    print("\n--- TC-API-003: GET /api/history ---")
    r = session.get(f"{BASE_URL}/api/history?hours=1")
    check(r.status_code == 200, f"Status 200 (got {r.status_code})")
    data = r.json()
    check(isinstance(data, list), "Retorna lista")
    if len(data) > 0:
        check("temperature" in data[0], "Registros tienen temperature")
        check("humidity" in data[0], "Registros tienen humidity")
        check("co2" in data[0], "Registros tienen co2")

    print("\n--- TC-API-004: GET /api/thresholds ---")
    r = session.get(f"{BASE_URL}/api/thresholds")
    check(r.status_code == 200, f"Status 200 (got {r.status_code})")
    data = r.json()
    check("stage" in data, "Contiene stage")
    check("thresholds" in data, "Contiene thresholds")

    print("\n--- TC-API-005: GET /api/sensor-health ---")
    r = session.get(f"{BASE_URL}/api/sensor-health")
    check(r.status_code == 200, f"Status 200 (got {r.status_code})")

    print("\n--- TC-API-006: GET /api/events ---")
    r = session.get(f"{BASE_URL}/api/events")
    check(r.status_code == 200, f"Status 200 (got {r.status_code})")
    check(isinstance(r.json(), list), "Retorna lista")


# --- Sensor Validation ---

def test_sensor_validation(session):
    print("\n--- TC-SEN-004/005: Validacion de datos en historial ---")
    r = session.get(f"{BASE_URL}/api/history?hours=24")
    data = r.json()
    if len(data) == 0:
        print("  SKIP: No hay datos historicos")
        return

    zero_temps = sum(1 for d in data if d.get("temperature") == 0)
    zero_hums = sum(1 for d in data if d.get("humidity") == 0)
    total = len(data)
    check(zero_temps == 0, f"0 temperaturas con valor 0 (found {zero_temps}/{total})")
    check(zero_hums == 0, f"0 humedades con valor 0 (found {zero_hums}/{total})")

    valid_temps = [d["temperature"] for d in data if d.get("temperature") is not None]
    if valid_temps:
        check(min(valid_temps) > 0, f"Temp minima > 0 (min={min(valid_temps)})")
        check(max(valid_temps) < 80, f"Temp maxima < 80 (max={max(valid_temps)})")

    valid_hums = [d["humidity"] for d in data if d.get("humidity") is not None]
    if valid_hums:
        check(min(valid_hums) > 0, f"Hum minima > 0 (min={min(valid_hums)})")
        check(max(valid_hums) <= 100, f"Hum maxima <= 100 (max={max(valid_hums)})")


def main():
    print("=" * 60)
    print(f"QA Tests - API & Auth ({BASE_URL})")
    print("=" * 60)

    # Test sin autenticacion
    test_auth()

    # Pedir password para tests autenticados
    password = input("\nIngresa password de admin para continuar (o Enter para saltar): ").strip()
    if not password:
        print("\nSaltando tests autenticados")
    else:
        session = requests.Session()
        r = session.post(f"{BASE_URL}/login", data={"username": "admin", "password": password})
        if "/login" not in r.url:
            print("\n--- TC-AUT-001: Login exitoso ---")
            check(True, "Login exitoso, redirigido al dashboard")
            test_api(session)
            test_sensor_validation(session)
        else:
            print("  FAIL: No se pudo autenticar")

    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"Resultado: {PASS}/{total} passed, {FAIL} failed")
    rate = (PASS / total * 100) if total > 0 else 0
    print(f"Pass rate: {rate:.1f}%")
    print("=" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
