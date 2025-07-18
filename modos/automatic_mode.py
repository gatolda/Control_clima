import time

class AutomaticMode:
    def __init__(self, sensor_reader, actuator_manager, umbrales):
        self.sensor_reader = sensor_reader
        self.actuator_manager = actuator_manager
        self.umbrales = umbrales  # Ya es un dict directo
        print(f"🤖 Modo automático inicializado con umbrales: {self.umbrales}")

    def run(self):
        print("=== 🤖 MODO AUTOMÁTICO ===")
        print("📈 Gestionando sensores y actuadores según umbrales...")

        try:
            while True:
                datos = self.sensor_reader.read_all()
                temp = datos["temperatura_humedad"].get("temperature")
                hum = datos["temperatura_humedad"].get("humidity")
                print(f"🌡️ Temp: {temp}°C, 💧 Hum: {hum}%")

                # Gestionar temperatura
                if temp is not None:
                    if temp > self.umbrales["temperatura"]["max"]:
                        print("⚠️ Temperatura alta. Activando ventiladores...")
                        self.actuator_manager.turn_on("ventiladores")
                    elif temp < self.umbrales["temperatura"]["min"]:
                        print("❄️ Temperatura baja. Activando calefactor...")
                        self.actuator_manager.turn_on("calefactor")
                    else:
                        print("🌡️ Temperatura dentro de rango. Apagando ventiladores y calefactor.")
                        self.actuator_manager.turn_off("ventiladores")
                        self.actuator_manager.turn_off("calefactor")

                # Gestionar humedad
                if hum is not None:
                    if hum > self.umbrales["humedad"]["max"]:
                        print("⚠️ Humedad alta. Activando deshumidificador...")
                        self.actuator_manager.turn_on("deshumidificador")
                    elif hum < self.umbrales["humedad"]["min"]:
                        print("💧 Humedad baja. Activando humidificador...")
                        self.actuator_manager.turn_on("humidificador")
                    else:
                        print("💧 Humedad dentro de rango. Apagando humidificador y deshumidificador.")
                        self.actuator_manager.turn_off("humidificador")
                        self.actuator_manager.turn_off("deshumidificador")

                time.sleep(5)  # Ajusta al intervalo deseado

        except KeyboardInterrupt:
            print("\n🛑 Programa detenido por el usuario.")
        finally:
            self.actuator_manager.cleanup()
            print("♻️ GPIO liberado correctamente.")
