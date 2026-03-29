import statistics
import time
import Adafruit_DHT
from core.Sensores.co2_pwm_sensor import CO2PWMSensor


class SensorReader:
    """
    Lee multiples fuentes de sensores por variable y consolida
    en un solo valor por variable usando mediana.
    """

    # Rangos validos para filtrar lecturas erraticas
    VALID_RANGES = {
        "temperatura": (-40, 80),
        "humedad": (0, 100),
        "co2": (0, 5000),
    }

    def __init__(self, config):
        self.config = config
        self.sensores = config.obtener("sensores", {})
        self._drivers = {}  # Cache de drivers inicializados
        self._sensor_status = {}  # Estado de salud de cada sensor
        print(f"SensorReader inicializado con variables: {list(self.sensores.keys())}")

    def _get_driver(self, sensor_config):
        """Obtiene o crea el driver para un sensor."""
        sensor_id = sensor_config["id"]
        if sensor_id in self._drivers:
            return self._drivers[sensor_id]

        tipo = sensor_config["tipo"]
        pin = sensor_config.get("pin")

        if tipo == "DHT22":
            # Adafruit_DHT no necesita instancia, usamos el modulo directo
            self._drivers[sensor_id] = {"tipo": "DHT22", "pin": pin}
        elif tipo == "CO2_PWM":
            self._drivers[sensor_id] = CO2PWMSensor(pin)
        # Futuro: ARDUINO_SERIAL
        # elif tipo == "ARDUINO_SERIAL":
        #     self._drivers[sensor_id] = ArduinoSerialNode(sensor_config)

        return self._drivers.get(sensor_id)

    def _read_single(self, variable, sensor_config):
        """Lee un solo sensor y retorna el valor para la variable."""
        sensor_id = sensor_config["id"]
        tipo = sensor_config["tipo"]

        try:
            if tipo == "DHT22":
                pin = sensor_config["pin"]
                humidity, temperature = Adafruit_DHT.read_retry(
                    Adafruit_DHT.DHT22, pin, retries=3, delay_seconds=0.5
                )
                self._sensor_status[sensor_id] = "ok"
                if variable == "temperatura":
                    return temperature
                elif variable == "humedad":
                    return humidity

            elif tipo == "CO2_PWM":
                driver = self._get_driver(sensor_config)
                result = driver.read()
                if result and result.get("co2") is not None:
                    self._sensor_status[sensor_id] = "ok"
                    return result["co2"]
                else:
                    self._sensor_status[sensor_id] = "sin_datos"
                    return None

        except Exception as e:
            self._sensor_status[sensor_id] = f"error: {e}"
            print(f"Error leyendo sensor {sensor_id}: {e}")
            return None

    def _is_valid(self, variable, value):
        """Verifica si un valor esta dentro del rango valido."""
        if value is None:
            return False
        rango = self.VALID_RANGES.get(variable)
        if rango:
            return rango[0] <= value <= rango[1]
        return True

    def _consolidate(self, values):
        """Consolida multiples lecturas usando mediana."""
        valid = [v for v in values if v is not None]
        if not valid:
            return None
        if len(valid) == 1:
            return round(valid[0], 1)
        return round(statistics.median(valid), 1)

    def read_variable(self, variable):
        """
        Lee todas las fuentes de una variable y retorna un valor consolidado.
        Retorna: {"value": float|None, "sources": int, "valid": int}
        """
        fuentes = self.sensores.get(variable, [])
        if not fuentes:
            return {"value": None, "sources": 0, "valid": 0}

        readings = []
        for sensor_config in fuentes:
            value = self._read_single(variable, sensor_config)
            if self._is_valid(variable, value):
                readings.append(value)

        return {
            "value": self._consolidate(readings),
            "sources": len(fuentes),
            "valid": len(readings),
        }

    def read_all(self):
        """
        Lee todas las variables y retorna datos consolidados.
        Mantiene compatibilidad con el formato anterior para el dashboard.
        """
        temp = self.read_variable("temperatura")
        hum = self.read_variable("humedad")
        co2 = self.read_variable("co2")

        return {
            "temperatura_humedad": {
                "temperature": temp["value"],
                "humidity": hum["value"],
            },
            "co2": {
                "co2": co2["value"],
            },
        }

    def read_all_detailed(self):
        """
        Lee todas las variables con informacion detallada.
        Util para diagnostico.
        """
        result = {}
        for variable in self.sensores:
            result[variable] = self.read_variable(variable)
        return result

    def get_sensor_health(self):
        """Retorna el estado de salud de cada sensor."""
        return dict(self._sensor_status)
