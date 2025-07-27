import mh_z19

print("📡 Leyendo sensor MH-Z19...")
data = mh_z19.read()

if data:
    print(f"✅ CO₂: {data['co2']} ppm")
    print(f"🌡️ Temp interna: {data['temperature']}°C")
else:
    print("❌ No se pudo leer el sensor.")
