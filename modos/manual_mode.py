# modos/manual_mode.py

def mostrar_estado_sensores(self):
    print("📊 Sensores:")
    datos = self.sensor_reader.read_all()
    for nombre, valores in datos.items():
        linea = f"  🌡️ {nombre}: "
        if "temperature" in valores and "humidity" in valores:
            temp = valores["temperature"]
            hum = valores["humidity"]
            linea += f"{temp if temp is not None else 'N/A'}°C 💧 {hum if hum is not None else 'N/A'}%"
        elif "co2" in valores:
            co2 = valores["co2"]
            linea += f"🌿 CO₂: {co2 if co2 is not None else 'N/A'} ppm"
        else:
            linea += "Sin datos"

        print(linea)
