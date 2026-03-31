"""
Hub de comunicacion serial con Arduino.
Lee JSON desde Arduino via USB serial y cachea las lecturas.
"""
import threading
import time
import json

try:
    import serial
except ImportError:
    serial = None
    print("AVISO: pyserial no instalado. Arduino hub no disponible.")


class ArduinoSerialHub:
    """
    Lee datos de sensores desde Arduino via serial USB.
    Corre un thread en background que parsea JSON continuamente.

    Protocolo Arduino:
    - Envia lineas JSON: {"sensors":[{"id":"suelo_h_1","type":"humidity","value":45.2}, ...]}
    - Heartbeat cada 10s: {"heartbeat":true}
    """

    def __init__(self, port="/dev/ttyUSB0", baudrate=115200, timeout=2):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._readings = {}       # {sensor_id: {"value": float, "type": str, "timestamp": float}}
        self._lock = threading.Lock()
        self._connected = False
        self._last_received = 0
        self._running = False
        self._serial = None
        self._thread = None

    def start(self):
        """Inicia el thread de lectura serial."""
        if serial is None:
            print("ArduinoHub: pyserial no disponible, modo simulado")
            return
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        print(f"ArduinoHub: iniciado en {self.port} @ {self.baudrate}")

    def stop(self):
        """Detiene el thread y cierra el puerto."""
        self._running = False
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._connected = False

    def _connect(self):
        """Intenta conectar al puerto serial."""
        try:
            if self._serial and self._serial.is_open:
                self._serial.close()
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            self._connected = True
            self._last_received = time.time()
            print(f"ArduinoHub: conectado a {self.port}")
            return True
        except (serial.SerialException, OSError) as e:
            self._connected = False
            print(f"ArduinoHub: no se pudo conectar a {self.port}: {e}")
            return False

    def _read_loop(self):
        """Loop principal de lectura serial."""
        while self._running:
            if not self._connected:
                if not self._connect():
                    time.sleep(5)  # Reintentar en 5 segundos
                    continue

            try:
                line = self._serial.readline()
                if not line:
                    # Timeout sin datos - verificar si Arduino sigue vivo
                    if time.time() - self._last_received > 30:
                        print("ArduinoHub: sin datos por 30s, reconectando...")
                        self._connected = False
                    continue

                self._last_received = time.time()
                data = json.loads(line.decode("utf-8").strip())

                if "heartbeat" in data:
                    continue

                if "sensors" in data:
                    with self._lock:
                        for sensor in data["sensors"]:
                            sid = sensor.get("id")
                            if sid:
                                self._readings[sid] = {
                                    "value": sensor.get("value"),
                                    "type": sensor.get("type", "unknown"),
                                    "zone": sensor.get("zone", "default"),
                                    "timestamp": time.time()
                                }

            except json.JSONDecodeError:
                pass  # Linea corrupta, ignorar
            except (serial.SerialException, OSError):
                print("ArduinoHub: conexion perdida, reconectando...")
                self._connected = False
                time.sleep(2)

    def get_reading(self, sensor_id):
        """Obtiene la ultima lectura de un sensor."""
        with self._lock:
            reading = self._readings.get(sensor_id)
            if reading is None:
                return None
            # Lectura mas antigua que 60s se considera stale
            if time.time() - reading["timestamp"] > 60:
                return None
            return reading["value"]

    def get_all_readings(self):
        """Obtiene todas las lecturas actuales."""
        with self._lock:
            now = time.time()
            return {
                sid: r for sid, r in self._readings.items()
                if now - r["timestamp"] <= 60
            }

    def get_readings_by_zone(self):
        """Agrupa lecturas por zona."""
        with self._lock:
            now = time.time()
            zones = {}
            for sid, r in self._readings.items():
                if now - r["timestamp"] > 60:
                    continue
                zone = r.get("zone", "default")
                if zone not in zones:
                    zones[zone] = {}
                zones[zone][sid] = {
                    "value": r["value"],
                    "type": r["type"]
                }
            return zones

    def is_connected(self):
        return self._connected and (time.time() - self._last_received < 30)

    def get_status(self):
        """Estado del hub para diagnosticos."""
        return {
            "connected": self.is_connected(),
            "port": self.port,
            "last_received": self._last_received,
            "sensors_count": len(self._readings),
            "sensors": list(self._readings.keys())
        }
