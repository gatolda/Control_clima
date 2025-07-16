def read(self):
    """
    Lee la temperatura y la humedad desde el sensor.
    """
    print(f"🛠 DEBUG: Llamando a read() en pin {self.pin}")
    humedad, temperatura = Adafruit_DHT.read_retry(self.sensor_type, self.pin)
    print(f"🛠 DEBUG: Resultado de Adafruit_DHT.read_retry = Temp:{temperatura}, Hum:{humedad}")

    if humedad is None or temperatura is None:
        print("⚠️ DEBUG: Reintentando lectura...")
        humedad, temperatura = Adafruit_DHT.read_retry(self.sensor_type, self.pin)
        print(f"🛠 DEBUG: Segundo intento = Temp:{temperatura}, Hum:{humedad}")

    if humedad is not None and temperatura is not None:
        return {
            "temperature": temperatura,
            "humidity": humedad,
            "status": "OK"
        }
    else:
        print("❌ DEBUG: Sensor devolvió None después de 2 intentos")
        return {
            "temperature": None,
            "humidity": None,
            "status": "ERROR"
        }
