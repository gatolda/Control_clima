import statistics
import time
from collections import deque
from core.Sensores.co2_pwm_sensor import CO2PWMSensor
from core.Sensores.arduino_serial import ArduinoSerialHub

# adafruit_dht/board se importan LAZY adentro de _get_driver porque
# `import board` (blinka) llama RPi.GPIO.setmode(BCM) al importarse, y
# eso entra en conflicto con inicializar_gpio() que setea BOARD.
# Migrar todo el proyecto a BCM mode esta en el backlog (config.yml + gpio_setup).
def _board_pin(bcm_pin):
    import board
    return getattr(board, f"D{bcm_pin}")


# Mapping default de variable interna -> field del JSON del Arduino sketch v2.
# Permite que sensores ARDUINO_SERIAL no tengan que especificar arduino_field
# explicitamente cuando la variable es obvia. Se puede sobrescribir en config.
_VARIABLE_TO_FIELD = {
    "temperatura": "temperature",
    "humedad": "humidity",
    "co2": "co2",
    "humedad_suelo": "humidity",
    "iluminacion": "light_detected",
}


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
        "iluminacion": (0, 1),  # binario: 1=luz, 0=oscuro
    }

    # Mediana movil sobre las ultimas N lecturas por sensor para descartar spikes
    # transitorios (ej. ruido electrico, lectura DHT22 erratica). 5 lecturas con
    # intervalo de 5s = 25s de historia. Aumentar si los peaks son frecuentes,
    # bajar si querés que cambios reales se reflejen mas rapido.
    MEDIAN_WINDOW = 5

    def __init__(self, config):
        self.config = config
        self.sensores = config.obtener("sensores", {})
        self._drivers = {}  # Cache de drivers inicializados
        self._sensor_status = {}  # Estado de salud de cada sensor
        self._arduino_hub = None  # Singleton por puerto serial
        self._reading_buffers = {}  # (variable, sensor_id) -> deque(maxlen=MEDIAN_WINDOW)

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
            # Lazy import (ver nota arriba). Puede fallar con ValueError si
            # RPi.GPIO ya esta en modo BOARD; lo capturamos y devolvemos None.
            try:
                import adafruit_dht
                self._drivers[sensor_id] = adafruit_dht.DHT22(_board_pin(pin), use_pulseio=False)
            except (ValueError, ImportError, RuntimeError) as e:
                self._sensor_status[sensor_id] = f"init_error: {e}"
                self._drivers[sensor_id] = None
        elif tipo == "CO2_PWM":
            self._drivers[sensor_id] = CO2PWMSensor(pin)
        elif tipo == "ARDUINO_SERIAL":
            # Usa el hub compartido, no crea driver individual
            self._drivers[sensor_id] = {"tipo": "ARDUINO_SERIAL", "id": sensor_id}

        return self._drivers.get(sensor_id)

    def _read_single(self, variable, sensor_config):
        """Lee un solo sensor y retorna el valor para la variable.

        El valor pasa por un filtro de mediana movil (MEDIAN_WINDOW lecturas)
        para descartar spikes transitorios antes de llegar al consolidador.
        """
        sensor_id = sensor_config["id"]
        tipo = sensor_config["tipo"]
        raw_value = None

        try:
            if tipo == "DHT22":
                driver = self._get_driver(sensor_config)
                if driver is None:
                    return None  # init fallo (ver _get_driver), status ya anotado
                # adafruit_dht es muy flaky (timing-sensitive). Hasta 5 retries
                # con 2s entre cada uno (el DHT22 necesita >=2s entre lecturas).
                temperature = humidity = None
                for _ in range(5):
                    try:
                        temperature = driver.temperature
                        humidity = driver.humidity
                        if temperature is not None and humidity is not None:
                            break
                    except RuntimeError:
                        pass
                    time.sleep(2.0)
                self._sensor_status[sensor_id] = "ok" if temperature is not None else "sin_datos"
                if variable == "temperatura":
                    raw_value = temperature
                elif variable == "humedad":
                    raw_value = humidity

            elif tipo == "CO2_PWM":
                driver = self._get_driver(sensor_config)
                result = driver.read()
                if result and result.get("co2") is not None:
                    self._sensor_status[sensor_id] = "ok"
                    raw_value = result["co2"]
                else:
                    self._sensor_status[sensor_id] = "sin_datos"

            elif tipo == "ARDUINO_SERIAL":
                if not self._arduino_hub:
                    self._sensor_status[sensor_id] = "hub_no_disponible"
                    return None
                # Si la config tiene arduino_field, lo usamos (sensores
                # multi-tipo como DHT22 que reportan temperature + humidity
                # bajo el mismo id). Si no, mapeamos por la variable que
                # estamos pidiendo.
                field = sensor_config.get("arduino_field") or _VARIABLE_TO_FIELD.get(variable)
                value = self._arduino_hub.get_reading(sensor_id, field=field)
                if value is not None:
                    self._sensor_status[sensor_id] = "ok"
                    raw_value = value
                else:
                    self._sensor_status[sensor_id] = "sin_datos"

        except Exception as e:
            self._sensor_status[sensor_id] = f"error: {e}"
            print(f"Error leyendo sensor {sensor_id}: {e}")
            return None

        return self._apply_median_filter(variable, sensor_id, raw_value)

    def _is_valid(self, variable, value):
        """Verifica si un valor esta dentro del rango valido."""
        if value is None:
            return False
        rango = self.VALID_RANGES.get(variable)
        if rango:
            return rango[0] <= value <= rango[1]
        return True

    def _apply_median_filter(self, variable, sensor_id, value):
        # Mediana movil para descartar spikes. Solo valores validos entran al
        # buffer (lo invalidos siguen siendo invalidos rio abajo).
        if value is None or not self._is_valid(variable, value):
            return value
        key = (variable, sensor_id)
        buf = self._reading_buffers.get(key)
        if buf is None:
            buf = deque(maxlen=self.MEDIAN_WINDOW)
            self._reading_buffers[key] = buf
        buf.append(value)
        return statistics.median(buf)

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
