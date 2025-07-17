"""
main.py
Sistema de Control Climático usando configuración YAML
"""

import time
from config_loader import ConfigLoader

# Cargar la configuración
config = ConfigLoader()
config.cargar_configuracion()

# Mostrar configuración cargada
print("\n==== CONFIGURACIÓN DEL SISTEMA ====")
sensores = config.obtener("sensores", {})
for sensor, settings in sensores.items():
    pin = settings.get("pin", "N/A")
    tipo = settings.get("tipo", "N/A")
    print(f"📡 {sensor}: Pin={pin} Tipo={tipo}")

actuadores = config.obtener("actuadores", {})
for act, settings in actuadores.items():
    pines = settings.get("pines", {})
    tipo_activacion = settings.get("tipo_activacion", "N/A")
    print(f"⚡ {act}: Pines={pines} Activación={tipo_activacion}")
print("====================================\n")

# Ciclo principal simulado
print("🔄 Iniciando ciclo principal...")
try:
    while True:
        # Leer sensores (simulado)
        print("📡 Leyendo sensores...")
        for sensor, settings in sensores.items():
            tipo = settings.get("tipo", "N/A")
            pin = settings.get("pin", "N/A")
            print(f"🌡️ Sensor: {sensor} | Tipo: {tipo} | Pin: {pin}")

        # Gestionar actuadores (simulado)
        print("⚡ Gestionando actuadores...")

        # Esperar intervalo definido en config
        intervalo = config.obtener("general.intervalo_lectura", 5)
        time.sleep(intervalo)

except KeyboardInterrupt:
    print("\n🛑 Programa detenido por el usuario.")
