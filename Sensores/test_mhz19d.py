import RPi.GPIO as GPIO
import time
import os

# Ruta del archivo de calibración
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAL_FILE = os.path.join(BASE_DIR, "calibracion_pwm.txt")

PWM_PIN = 17  # Cambia si usas otro pin

min_ppm = 500
max_ppm = 5000

GPIO.setmode(GPIO.BCM)
GPIO.setup(PWM_PIN, GPIO.IN)

def medir_pulso():
    GPIO.wait_for_edge(PWM_PIN, GPIO.RISING)
    t1 = time.time()
    GPIO.wait_for_edge(PWM_PIN, GPIO.FALLING)
    t2 = time.time()
    return t2 - t1

def promedio_pulso(segundos=30):
    print(f"Promediando pulso por {segundos} segundos...")
    pulsos = []
    start = time.time()
    while time.time() - start < segundos:
        pulso = medir_pulso()
        pulsos.append(pulso)
    promedio = sum(pulsos) / len(pulsos)
    print(f"Promedio: {promedio*1000:.2f} ms de {len(pulsos)} muestras")
    return promedio

def guardar_calibracion(pulso_min, pulso_max):
    with open(CAL_FILE, "w") as f:
        f.write(f"{pulso_min}\n{pulso_max}\n")
    print(f"Calibración guardada en '{CAL_FILE}'.")

print("¿Deseas calibrar el sensor MH-Z19D PWM? (s/n)")
op = input().lower()

if op == "s":
    print("\nDeja el sensor en AMBIENTE LIMPIO Y VENTILADO, luego presiona ENTER para comenzar el promedio de 30 segundos...")
    input()
    pulso_min = promedio_pulso(30)
    print(f"Pulso mínimo (ambiente limpio): {pulso_min*1000:.2f} ms")

    print("\nAhora SATURA el sensor con CO₂ (espacio cerrado, sopla cerca), espera unos segundos.")
    input("Cuando esté listo para promediar el máximo, presiona ENTER...")
    pulso_max = promedio_pulso(30)
    print(f"Pulso máximo (CO₂ saturado): {pulso_max*1000:.2f} ms\n")

    guardar_calibracion(pulso_min, pulso_max)
else:
    print("Calibración cancelada. No se actualizó el archivo.")
    GPIO.cleanup()
    exit()

GPIO.cleanup()
