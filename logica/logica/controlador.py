def leer_sensores(self):
    """Obtiene y devuelve las lecturas del sensor."""
    print(f"🛠 DEBUG: Tipo de self.sensor = {type(self.sensor)}")
    print("🛠 DEBUG: Llamando a self.sensor.read()...")
    datos = self.sensor.read()
    print(f"🛠 DEBUG: Resultado de self.sensor.read() = {datos}")

    if datos.get("status") != "OK":
        print("❌ Error al leer el sensor dentro de ControladorClima")
        return None
    return datos
