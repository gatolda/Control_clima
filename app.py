# app.py
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from core.config_loader import ConfigLoader
from core.sensor_reader import SensorReader
from core.actuator_manager import ActuatorManager
from core.gpio_setup import inicializar_gpio, limpiar_gpio
from data.database import Database
import threading
import time

app = Flask(__name__)
app.config["SECRET_KEY"] = "invernadero-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Inicializar
inicializar_gpio()
config = ConfigLoader()
config.cargar_configuracion()
sensor_reader = SensorReader(config)
actuator_manager = ActuatorManager(config)
db = Database()

# Ultima lectura de sensores (compartida entre threads)
latest_sensor_data = {}
sensor_lock = threading.Lock()

# --- Rutas HTTP ---

@app.route("/")
def index():
    actuadores = list(actuator_manager.relay_pins.keys())
    return render_template("dashboard.html", actuadores=actuadores)

@app.route("/diagnostics")
def diagnostics():
    actuadores = list(actuator_manager.relay_pins.keys())
    return render_template("diagnostics.html", actuadores=actuadores)

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/sensores")
def get_sensores():
    with sensor_lock:
        return jsonify(latest_sensor_data)

@app.route("/actuadores/estado")
def estado_actuadores():
    return jsonify(actuator_manager.status())

@app.route("/api/history")
def get_history():
    hours = request.args.get("hours", 24, type=int)
    readings = db.get_readings(hours=hours)
    return jsonify(readings)

@app.route("/api/events")
def get_events():
    hours = request.args.get("hours", 24, type=int)
    events = db.get_actuator_events(hours=hours)
    return jsonify(events)

@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify(db.get_all_config())

@app.route("/api/config", methods=["POST"])
def update_config():
    data = request.get_json()
    for key, value in data.items():
        db.set_config(key, value)
    return jsonify({"status": "ok"})

@app.route("/api/thresholds")
def get_thresholds():
    stage = db.get_config("stage", "vegetativo_temprano")
    thresholds = db.get_stage_thresholds(stage)
    return jsonify({"stage": stage, "thresholds": thresholds})

# --- Socket.IO Events ---

@socketio.on("connect")
def handle_connect():
    print("Cliente conectado")
    emit("actuator_status", actuator_manager.status())
    with sensor_lock:
        if latest_sensor_data:
            emit("sensor_data", latest_sensor_data)

@socketio.on("disconnect")
def handle_disconnect():
    print("Cliente desconectado")

@socketio.on("toggle_actuador")
def handle_toggle(data):
    nombre = data.get("nombre")
    accion = data.get("accion")
    if accion == "on":
        actuator_manager.turn_on(nombre)
    elif accion == "off":
        actuator_manager.turn_off(nombre)
    # Registrar evento en base de datos
    db.log_actuator_event(nombre, accion, triggered_by="manual")
    socketio.emit("actuator_status", actuator_manager.status())

# --- Background thread para lecturas de sensores ---

def sensor_background_thread():
    global latest_sensor_data
    print("Background thread de sensores iniciado")
    while True:
        try:
            datos = sensor_reader.read_all()
            temp = datos.get("temperatura_humedad", {}).get("temperature")
            hum = datos.get("temperatura_humedad", {}).get("humidity")
            co2 = datos.get("co2", {}).get("co2")

            # Filtrar lecturas erraticas del DHT22
            if temp is not None and (temp < -40 or temp > 80):
                temp = None
            if hum is not None and (hum < 0 or hum > 100):
                hum = None
            if co2 is not None and (co2 < 0 or co2 > 5000):
                co2 = None

            # Reconstruir datos filtrados
            filtered = {
                "temperatura_humedad": {"temperature": temp, "humidity": hum},
                "co2": {"co2": co2}
            }

            with sensor_lock:
                latest_sensor_data = filtered

            # Guardar en base de datos
            db.save_reading(temp, hum, co2)

            print(f"Sensores: temp={temp}, hum={hum}, co2={co2}", flush=True)
            socketio.emit("sensor_data", filtered)

        except Exception as e:
            print(f"Error en lectura de sensores: {e}", flush=True)

        time.sleep(5)

@app.errorhandler(404)
def not_found(error):
    return "Pagina no encontrada", 404

if __name__ == "__main__":
    try:
        sensor_thread = threading.Thread(target=sensor_background_thread, daemon=True)
        sensor_thread.start()
        print("Dashboard disponible en http://0.0.0.0:5000")
        socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
    finally:
        limpiar_gpio()
