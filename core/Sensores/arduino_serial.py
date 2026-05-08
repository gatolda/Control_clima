"""
Hub de comunicacion serial con Arduino.
Lee JSON desde Arduino via USB serial y cachea las lecturas.

Protocolo (sketch v2):
    {"sensors":[
        {"id":"dht22_1","type":"temperature","value":22.5},
        {"id":"dht22_1","type":"humidity","value":58.3},
        {"id":"mhz19_1","type":"co2","value":850},
        {"id":"soil_s1","type":"humidity","zone":"esq_sup_izq","value":67.2,
         "raw":420,"dry":600,"field":320,"calibrated":true},
        ...
    ]}

DHT22 manda 2 lecturas con el MISMO id pero diferente type. Por eso usamos
clave compuesta (id, type) internamente.

Comandos a Arduino (via send_command):
    "CAL_DRY soil_s1"   - calibra punto seco
    "CAL_FIELD soil_s1" - calibra capacidad de campo
    "GET_CAL"           - devuelve todas las calibraciones
    "RESET_CAL"         - reset a defaults
"""
import threading
import time
import json

try:
    import serial
except ImportError:
    serial = None
    print("AVISO: pyserial no instalado. Arduino hub no disponible.")


# Cuanto tiempo es "fresco" un reading antes de descartarlo
STALE_AFTER_SEC = 60


class ArduinoSerialHub:
    def __init__(self, port="/dev/ttyUSB0", baudrate=115200, timeout=2):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        # Clave: (sensor_id, sensor_type). Ej: ("dht22_1", "temperature")
        # Valor: dict con value, type, zone, raw, dry, field, calibrated, timestamp
        self._readings = {}
        # Calibraciones reportadas por GET_CAL: {sensor_id: {dry, field}}
        self._calibrations = {}
        # Eventos de calibración recientes (responses a CAL_DRY/CAL_FIELD): list of dicts
        self._calibration_events = []
        self._lock = threading.Lock()
        self._connected = False
        self._last_received = 0
        self._running = False
        self._serial = None
        self._thread = None

    # ─────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────

    def start(self):
        if serial is None:
            print("ArduinoHub: pyserial no disponible, modo simulado")
            return
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        print(f"ArduinoHub: iniciado en {self.port} @ {self.baudrate}")

    def stop(self):
        self._running = False
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._connected = False

    def _connect(self):
        try:
            if self._serial and self._serial.is_open:
                self._serial.close()
            self._serial = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=self.timeout)
            self._connected = True
            self._last_received = time.time()
            print(f"ArduinoHub: conectado a {self.port}")
            return True
        except (serial.SerialException, OSError) as e:
            self._connected = False
            print(f"ArduinoHub: no se pudo conectar a {self.port}: {e}")
            return False

    # ─────────────────────────────────────────────────────────
    # Read loop
    # ─────────────────────────────────────────────────────────

    def _read_loop(self):
        while self._running:
            if not self._connected:
                if not self._connect():
                    time.sleep(5)
                    continue

            try:
                line = self._serial.readline()
                if not line:
                    if time.time() - self._last_received > 30:
                        print("ArduinoHub: sin datos por 30s, reconectando...")
                        self._connected = False
                    continue

                self._last_received = time.time()
                try:
                    data = json.loads(line.decode("utf-8").strip())
                except json.JSONDecodeError:
                    continue

                self._handle_message(data)

            except (serial.SerialException, OSError):
                print("ArduinoHub: conexion perdida, reconectando...")
                self._connected = False
                time.sleep(2)

    def _handle_message(self, data):
        if "heartbeat" in data:
            return

        if "sensors" in data and isinstance(data["sensors"], list):
            with self._lock:
                for sensor in data["sensors"]:
                    sid = sensor.get("id")
                    stype = sensor.get("type", "unknown")
                    if not sid:
                        continue
                    self._readings[(sid, stype)] = {
                        "value": sensor.get("value"),
                        "type": stype,
                        "zone": sensor.get("zone"),
                        "raw": sensor.get("raw"),
                        "dry": sensor.get("dry"),
                        "field": sensor.get("field"),
                        "calibrated": sensor.get("calibrated"),
                        "timestamp": time.time(),
                    }

        # Respuesta a comando de calibracion
        if "calibrated" in data and "point" in data:
            ev = {
                "id": data.get("calibrated"),
                "point": data.get("point"),
                "raw": data.get("raw"),
                "timestamp": time.time(),
            }
            with self._lock:
                self._calibration_events.append(ev)
                # Mantener solo los ultimos 50 eventos
                if len(self._calibration_events) > 50:
                    self._calibration_events = self._calibration_events[-50:]

        # Respuesta a GET_CAL
        if "calibrations" in data and isinstance(data["calibrations"], list):
            with self._lock:
                for c in data["calibrations"]:
                    cid = c.get("id")
                    if cid:
                        self._calibrations[cid] = {
                            "dry": c.get("dry"),
                            "field": c.get("field"),
                        }

    # ─────────────────────────────────────────────────────────
    # Read API
    # ─────────────────────────────────────────────────────────

    def get_reading(self, sensor_id, field=None):
        """
        Lectura actual de un sensor.

        Si `field` se especifica, busca por (id, type) — necesario para
        DHT22 que tiene 2 readings con el mismo id (temperature + humidity).

        Si no se especifica, devuelve la PRIMERA lectura encontrada con ese id
        (compatible con sensores legacy de 1-tipo como soil capacitivo).
        """
        with self._lock:
            now = time.time()

            if field is not None:
                key = (sensor_id, field)
                r = self._readings.get(key)
                if r and now - r["timestamp"] <= STALE_AFTER_SEC:
                    return r["value"]
                return None

            # Sin field: primera lectura no-stale para ese id
            for (sid, _stype), r in self._readings.items():
                if sid == sensor_id and now - r["timestamp"] <= STALE_AFTER_SEC:
                    return r["value"]
            return None

    def get_record(self, sensor_id, field=None):
        """Lectura completa con metadata (raw, dry, field, etc.). None si stale."""
        with self._lock:
            now = time.time()
            if field is not None:
                r = self._readings.get((sensor_id, field))
            else:
                r = next((r for (sid, _), r in self._readings.items() if sid == sensor_id), None)
            if r and now - r["timestamp"] <= STALE_AFTER_SEC:
                return dict(r)
            return None

    def get_all_readings(self):
        """Todas las lecturas frescas (no-stale)."""
        with self._lock:
            now = time.time()
            return {
                key: dict(r) for key, r in self._readings.items()
                if now - r["timestamp"] <= STALE_AFTER_SEC
            }

    def get_readings_by_zone(self):
        """Agrupa lecturas de suelo por zona."""
        with self._lock:
            now = time.time()
            zones = {}
            for (sid, stype), r in self._readings.items():
                if now - r["timestamp"] > STALE_AFTER_SEC:
                    continue
                zone = r.get("zone")
                if not zone:
                    continue
                if zone not in zones:
                    zones[zone] = {}
                zones[zone][sid] = {"value": r["value"], "type": stype, "raw": r.get("raw")}
            return zones

    def get_calibrations(self):
        """Calibraciones cacheadas (refrescar con send_command('GET_CAL'))."""
        with self._lock:
            return dict(self._calibrations)

    def get_recent_calibration_events(self, limit=10):
        """Eventos recientes de calibración (responses a CAL_DRY/CAL_FIELD)."""
        with self._lock:
            return list(self._calibration_events[-limit:])

    # ─────────────────────────────────────────────────────────
    # Write API (calibration commands)
    # ─────────────────────────────────────────────────────────

    def send_command(self, cmd):
        """
        Envía un comando al Arduino por serial. Returns bool de éxito.

        Comandos soportados (sketch v2):
            "CAL_DRY soil_s1"
            "CAL_FIELD soil_s1"
            "GET_CAL"
            "RESET_CAL"
        """
        if not self._connected or not self._serial:
            print(f"ArduinoHub: no conectado, no puedo enviar '{cmd}'")
            return False
        try:
            self._serial.write((cmd + "\n").encode("utf-8"))
            self._serial.flush()
            return True
        except (serial.SerialException, OSError) as e:
            print(f"ArduinoHub: error enviando comando: {e}")
            self._connected = False
            return False

    def calibrate_soil_dry(self, sensor_id):
        """Pide al Arduino que use el raw actual como punto seco para sensor_id."""
        return self.send_command(f"CAL_DRY {sensor_id}")

    def calibrate_soil_field(self, sensor_id):
        """Pide al Arduino que use el raw actual como capacidad de campo."""
        return self.send_command(f"CAL_FIELD {sensor_id}")

    def request_calibrations(self):
        """Pide al Arduino que reporte todas las calibraciones actuales."""
        return self.send_command("GET_CAL")

    # ─────────────────────────────────────────────────────────
    # Diagnostics
    # ─────────────────────────────────────────────────────────

    def is_connected(self):
        return self._connected and (time.time() - self._last_received < 30)

    def get_status(self):
        with self._lock:
            return {
                "connected": self.is_connected(),
                "port": self.port,
                "last_received": self._last_received,
                "readings_count": len(self._readings),
                "sensors": sorted({sid for sid, _ in self._readings.keys()}),
            }
