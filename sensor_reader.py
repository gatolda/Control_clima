"""
sensor_reader.py
Clase para manejar la lectura de sensores definidos en la configuración
"""

import Adafruit_DHT

class SensorReader:
    def __init__(self, config):
        self.config = config
        self.sensores = config.obtener("sensores")
        print(f"✅ SensorReader inicializado con sensores: {self.sensores.keys()}")

    def leer_todos(self):
        """
        Lee todos los sensores configurados y devuelve un diccionario con sus valores
        """
        resultados = {}
        for nombre, datos in self.sensores.items():
            tipo = datos.get("tipo", "").upper()

            if tipo == "DHT22":
                resultado = self._leer_dht22(nombre, datos)
            elif tipo == "MH-Z19":
                resultado = self._leer_mhz19(nombre, datos)
            else:
                resultado = {"error": f"Tipo de sensor no soportado: {tipo}"}

            resultados[nombre] = resultado
        return resultados

    def _leer_dht22(self, nombre, datos):
        """
        Lee un sensor DHT22
        """
        pin = datos.get("pin")
        if pin is None:
            return {"error": "Pin no definido para DHT22"}

        sensor = Adafruit_DHT.DHT22
        humedad, temperatura = Adafruit_DHT.read_retry(sensor, pin)

        if humedad is not None and temperatura is not None:
            return {"temperatura": round(temperatura, 1), "humedad": round(humedad, 1)}
        else:
            return {"error": "No se pudo leer el DHT22"}

    def _leer_mhz19(self, nombre, datos):
        """
        Simula la lectura de un sensor de CO2 (MH-Z19)
        """
        # Aquí va la lógica real para MH-Z19 cuando lo conectes
        # Por ahora devuelve valores simulados
        return {"co2": 450, "unidad": "ppm", "nota": "Valor simulado"}
