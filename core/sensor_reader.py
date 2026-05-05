import statistics
import time
import board
import adafruit_dht
from core.Sensores.co2_pwm_sensor import CO2PWMSensor
from core.Sensores.arduino_serial import ArduinoSerialHub


def _board_pin(bcm_pin):
    """Mapea numero de pin BCM a board.DXX (lo que adafruit_dht necesita)."""
    return getattr(board, f"D{bcm_pin}")


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
        "humedad_suelo": (0, 100),
        "ph_suelo": (0, 14),
    }

    def __init__(self, config):
        self.config = config
        self.sensores = config.obtener("sensores", {})
        self._drivers = {}  # Cache de drivers inicializados
        self._sensor_status = {}  # Estado de salud de cada sensor
        self._arduino_hub = None  # Singleton por puerto serial

        # Inicializar Arduino hub si hay sensores ARDUINO_SERIAL
        arduino_config = config.obtener("arduino", {})
        if arduino_config.get("puerto"):
            self._arduino_hub = ArduinoSerialHub(
                port=arduino_config["puerto"],
                baudrate=arduino_config.get("baudrate", 115200),
                timeout=arduino_config.get("timeout", 2)
            )
            self._arduino_hub.start()
            print(f"ArduinoHub iniciado en {arduino_config['puerto']}")

        print(f"SensorReader inicializado con variables: {list(self.sensores.keys())}")

    def _get_driver(self, sensor_config):
        """Obtiene o crea el driver para un sensor."""
        sensor_id = sensor_config["id"]
        if sensor_id in self._drivers:
            return self._drivers[sensor_id]

        tipo = sensor_config["tipo"]
        pin = sensor_config.get("pin")

        if tipo == "DHT22":
            # adafruit_dht: instancia por pin. use_pulseio=False evita libgpiod
            # (mas estable en Pi sin permisos extra).
            self._drivers[sensor_id] = adafruit_dht.DHT22(_board_pin(pin), use_pulseio=False)
        elif tipo == "CO2_PWM":
            self._drivers[sensor_id] = CO2PWMSensor(pin)
        elif tipo == "ARDUINO_SERIAL":
            # Usa el hub compartido, no crea driver individual
            self._drivers[sensor_id] = {"tipo": "ARDUINO_SERIAL", "id": sensor_id}

        return self._drivers.get(sensor_id)

    def _read_single(self, variable, sensor_config):
        """Lee un solo sensor y retorna el valor para la variable."""
        sensor_id = sensor_config["id"]
        tipo = sensor_config["tipo"]

        try:
            if tipo == "DHT22":
                driver = self._get_driver(sensor_config)
                # adafruit_dht es flaky por naturaleza (timing-sensitive),
                # reintentamos hasta 3 veces.
                temperature = humidity = None
                for _ in range(3):
                    try:
                        temperature = driver.temperature
                        humidity = driver.humidity
                        if temperature is not None and humidity is not None:
                            break
                    except RuntimeError:
                        time.sleep(0.5)
                self._sensor_status[sensor_id] = "ok" if temperature is not None else "sin_datos"
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

            elif tipo == "ARDUINO_SERIAL":
                if self._arduino_hub:
                    value = self._arduino_hub.get_reading(sensor_id)
                    if value is not None:
                        self._sensor_status[sensor_id] = "ok"
                        return value
                    else:
                        self._sensor_status[sensor_id] = "sin_datos"
                        return None
                else:
                    self._sensor_status[sensor_id] = "hub_no_disponible"
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

    def read_zone_data(self):
        """
        Lee sensores de suelo agrupados por zona.
        Retorna: {"zona_1": {"humedad_suelo": 45.2, "ph_suelo": 6.3}, ...}
        """
        result = {}
        for variable in ["humedad_suelo", "ph_suelo"]:
            fuentes = self.sensores.get(variable, [])
            for sensor_config in fuentes:
                zone = sensor_config.get("zona", "default")
                if zone not in result:
                    result[zone] = {}
                value = self._read_single(variable, sensor_config)
                if self._is_valid(variable, value):
                    # Acumular valores para promediar si hay multiples sensores
                    key = f"{variable}_values"
                    if key not in result[zone]:
                        result[zone][key] = []
                    result[zone][key].append(value)

        # Consolidar multiples lecturas por zona usando mediana
        for zone in result:
            for variable in ["humedad_suelo", "ph_suelo"]:
                key = f"{variable}_values"
                if key in result[zone]:
                    result[zone][variable] = self._consolidate(result[zone].pop(key))

        return result

    def get_arduino_hub(self):
        """Retorna el hub Arduino para acceso directo."""
        return self._arduino_hub

    def get_sensor_health(self):
        """Retorna el estado de salud de cada sensor."""
        return dict(self._sensor_status)
