import time

class AutomaticMode:
    def __init__(self, sensor_reader, actuator_manager, config):
        self.sensor_reader = sensor_reader
        self.actuator_manager = actuator_manager
        self.umbrales = config.obtener("umbrales_automatico", {})
        self.intervalo = config.obtener("general.intervalo_lectura", 5)
        print("🤖 Modo automático inicializado con umbrales:", self.umbrales)

    def run(self):
        print("=== 🤖 MODO AUTOMÁTICO ===")
        print("📈 Gestionando sensores y actuadores según umbrales...")
        try:
            while True:
                datos = self.sensor_reader.read_all()
                temperatura = datos.get("temperatura_humedad", {}).get("temperature")
                humedad = datos.get("temperatura_humedad", {}).get("humidity")

                # --- Temperatura ---
                if temperatura is not None:
                    temp_min = self.umbrales.get("temperatura", {}).get("min", 0)
                    temp_max = self.umbrales.get("temperatura", {}).get("max", 50)

                    if temperatura > temp_max:
                        print(f"🌡️ {temperatura}°C > {temp_max}°C → Encendiendo ventiladores.")
                        self.actuator_manager.turn_on("ventiladores")
                        self.actuator_manager.turn_off("calefactor")
                    elif temperatura < temp_min:
                        print(f"🌡️ {temperatura}°C < {temp_min}°C → Encendiendo calefactor.")
                        self.actuator_manager.turn_on("calefactor")
                        self.actuator_manager.turn_off("ventiladores")
                    else:
                        print(f"🌡️ {temperatura}°C en rango → Apagando calefactor y ventiladores.")
                        self.actuator_manager.turn_off("ventiladores")
                        self.actuator_manager.turn_off("calefactor")

                # --- Humedad ---
                if humedad is not None:
                    hum_min = self.umbrales.get("humedad", {}).get("min", 30)
                    hum_max = self.umbrales.get("humedad", {}).get("max", 70)

                    if humedad > hum_max:
                        print(f"💧 {humedad}% > {hum_max}% → Encendiendo deshumidificador.")
                        self.actuator_manager.turn_on("deshumidificador")
                        self.actuator_manager.turn_off("humidificador")
                    elif humedad < hum_min:
                        print(f"💧 {humedad}% < {hum_min}% → Encendiendo humidificador.")
                        self.actuator_manager.turn_on("humidificador")
                        self.actuator_manager.turn_off("deshumidificador")
                    else:
                        print(f"💧 {humedad}% en rango → Apagando humidificador y deshumidificador.")
                        self.actuator_manager.turn_off("humidificador")
                        self.actuator_manager.turn_off("deshumidificador")

                time.sleep(self.intervalo)

        except KeyboardInterrupt:
            print("\n🛑 Modo automático detenido por el usuario.")
        finally:
            self.actuator_manager.cleanup()
