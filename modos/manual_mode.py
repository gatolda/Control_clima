# modos/manual_mode.py

class ManualMode:
    def __init__(self, sensor_reader, actuator_manager):
        self.sensor_reader = sensor_reader
        self.actuator_manager = actuator_manager

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

    def run(self):
        print("=== 🛠️ MODO MANUAL ===")
        print("👉 Escribe comandos como: on ventiladores, off luz, estado, exit")
        try:
            while True:
                comando = input("💻 Comando: ").strip().lower()
                if comando == "exit":
                    break
                elif comando == "estado":
                    self.mostrar_estado_sensores()
                elif comando.startswith("on "):
                    dispositivo = comando[3:].strip()
                    self.actuator_manager.activar(dispositivo)
                elif comando.startswith("off "):
                    dispositivo = comando[4:].strip()
                    self.actuator_manager.desactivar(dispositivo)
                else:
                    print("❓ Comando no reconocido.")
                self.mostrar_estado_sensores()
        except KeyboardInterrupt:
            print("\n🛑 Lectura interrumpida por el usuario.")
