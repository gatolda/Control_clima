import time

class ManualMode:
    def __init__(self, sensor_reader, actuator_manager):
        self.sensor_reader = sensor_reader
        self.actuator_manager = actuator_manager

    def run(self):
        """
        Ejecuta el modo manual interactivo
        """
        print("=== 🛠️ MODO MANUAL ===")
        print("👉 Escribe comandos como: on ventiladores, off luz, estado, exit")

        try:
            while True:
                # Mostrar lecturas de sensores
                datos = self.sensor_reader.read_all_sensors()
                print("📊 Sensores:")
                for sensor, lectura in datos.items():
                    temp = lectura.get("temperature", "N/A")
                    hum = lectura.get("humidity", "N/A")
                    print(f"  🌡️ {sensor}: {temp}°C 💧 {hum}%")

                # Leer comando
                comando = input("💻 Comando: ").strip().lower()
                if comando == "exit":
                    print("🚪 Saliendo del modo manual...")
                    break
                elif comando.startswith("on "):
                    actuador = comando.split(" ", 1)[1]
                    self.actuator_manager.turn_on(actuador)
                elif comando.startswith("off "):
                    actuador = comando.split(" ", 1)[1]
                    self.actuator_manager.turn_off(actuador)
                elif comando == "estado":
                    self.actuator_manager.status()
                else:
                    print("❌ Comando no reconocido.")

                time.sleep(1)

        except KeyboardInterrupt:
            print("\n🛑 Programa detenido por el usuario.")
        finally:
            self.actuator_manager.cleanup()
