# app.py
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from core.config_loader import ConfigLoader
from core.sensor_reader import SensorReader
from core.actuator_manager import ActuatorManager
from core.gpio_setup import inicializar_gpio, limpiar_gpio
from data.database import Database
from core.irrigation_manager import IrrigationManager
from core.camera_manager import CameraManager
from core.climate_controller import ClimateController
from data.models import STAGE_THRESHOLDS, STAGE_ORDER
from dotenv import load_dotenv
import threading
import time
import os

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# --- Autenticacion ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Credenciales desde variables de entorno (.env)
USERS = {
    os.environ.get("ADMIN_USER", "admin"): generate_password_hash(os.environ["ADMIN_PASSWORD"])
}

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(username):
    if username in USERS:
        return User(username)
    return None

# Inicializar hardware
inicializar_gpio()
config = ConfigLoader()
config.cargar_configuracion()
sensor_reader = SensorReader(config)
actuator_manager = ActuatorManager(config)
db = Database()
irrigation_manager = IrrigationManager(config, sensor_reader, actuator_manager, db)
camera_manager = CameraManager(config, db)
climate_controller = ClimateController(config, sensor_reader, actuator_manager, db)

# Ultima lectura de sensores (compartida entre threads)
latest_sensor_data = {}
sensor_lock = threading.Lock()

# --- Login ---

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username in USERS and check_password_hash(USERS[username], password):
            login_user(User(username), remember=True)
            return redirect(request.args.get("next") or url_for("index"))
        error = "Usuario o contrasenya incorrectos"
    return render_template("login.html", error=error)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# --- Rutas HTTP (protegidas) ---

@app.route("/")
@login_required
def index():
    actuadores = list(actuator_manager.relay_pins.keys())
    return render_template("dashboard.html", actuadores=actuadores)

@app.route("/diagnostics")
@login_required
def diagnostics():
    actuadores = list(actuator_manager.relay_pins.keys())
    return render_template("diagnostics.html", actuadores=actuadores)

@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html")

@app.route("/sensores")
@login_required
def get_sensores():
    with sensor_lock:
        return jsonify(latest_sensor_data)

@app.route("/actuadores/estado")
@login_required
def estado_actuadores():
    return jsonify(actuator_manager.status())

@app.route("/api/history")
@login_required
def get_history():
    hours = request.args.get("hours", 24, type=int)
    readings = db.get_readings(hours=hours)
    return jsonify(readings)

@app.route("/api/events")
@login_required
def get_events():
    hours = request.args.get("hours", 24, type=int)
    events = db.get_actuator_events(hours=hours)
    return jsonify(events)

@app.route("/api/config", methods=["GET"])
@login_required
def get_config():
    return jsonify(db.get_all_config())

@app.route("/api/config", methods=["POST"])
@login_required
def update_config():
    data = request.get_json()
    for key, value in data.items():
        db.set_config(key, value)
    return jsonify({"status": "ok"})

@app.route("/api/thresholds")
@login_required
def get_thresholds():
    stage = db.get_config("stage", "vegetativo_temprano")
    thresholds = db.get_stage_thresholds(stage)
    return jsonify({"stage": stage, "thresholds": thresholds})

@app.route("/api/sensor-health")
@login_required
def sensor_health():
    health = sensor_reader.get_sensor_health()
    detailed = sensor_reader.read_all_detailed()
    return jsonify({"health": health, "readings": detailed})

# --- Riego API ---

@app.route("/api/irrigation/status")
@login_required
def irrigation_status():
    return jsonify({
        "zones": irrigation_manager.get_zones(),
        "status": irrigation_manager.get_status(),
        "enabled": irrigation_manager.enabled
    })

@app.route("/api/irrigation/history")
@login_required
def irrigation_history():
    hours = request.args.get("hours", 48, type=int)
    events = db.get_irrigation_events(hours=hours)
    return jsonify(events)

@app.route("/api/irrigation/manual", methods=["POST"])
@login_required
def irrigation_manual():
    data = request.get_json()
    zone_id = data.get("zone_id")
    duration = data.get("duration_minutes", 5)
    result = irrigation_manager.manual_irrigate(zone_id, duration)
    if result.get("ok"):
        socketio.emit("irrigation_status", irrigation_manager.get_status())
    return jsonify(result)

@app.route("/api/irrigation/stop", methods=["POST"])
@login_required
def irrigation_stop():
    data = request.get_json()
    zone_id = data.get("zone_id")
    if zone_id:
        result = irrigation_manager.close_valve(zone_id, reason="manual_stop")
    else:
        irrigation_manager.emergency_stop()
        result = {"ok": True}
    socketio.emit("irrigation_status", irrigation_manager.get_status())
    return jsonify(result)

# --- Suelo API ---

@app.route("/api/soil")
@login_required
def get_soil():
    zone_data = sensor_reader.read_zone_data()
    return jsonify(zone_data)

@app.route("/api/soil/history")
@login_required
def soil_history():
    zone_id = request.args.get("zone_id")
    hours = request.args.get("hours", 24, type=int)
    readings = db.get_soil_readings(zone_id=zone_id, hours=hours)
    return jsonify(readings)

# --- Camara API ---

@app.route("/api/camera/capture", methods=["POST"])
@login_required
def camera_capture():
    result = camera_manager.capture_and_analyze()
    return jsonify(result)

@app.route("/api/camera/status")
@login_required
def camera_status():
    return jsonify(camera_manager.get_status())

@app.route("/api/camera/history")
@login_required
def camera_history():
    events = db.get_camera_events(limit=20)
    return jsonify(events)

@app.route("/api/camera/image/<filename>")
@login_required
def camera_image(filename):
    from flask import send_from_directory
    return send_from_directory("data/captures", filename)

# --- Climate Controller API ---

@app.route("/api/climate/status")
@login_required
def climate_status():
    return jsonify(climate_controller.get_status())

@app.route("/api/climate/mode", methods=["POST"])
@login_required
def climate_set_mode():
    data = request.get_json()
    mode = data.get("mode")
    if mode not in ("auto", "manual"):
        return jsonify({"ok": False, "error": "Modo debe ser 'auto' o 'manual'"})
    climate_controller.set_mode(mode)
    socketio.emit("climate_status", climate_controller.get_status())
    return jsonify({"ok": True, "mode": mode})

@app.route("/api/climate/stage", methods=["POST"])
@login_required
def climate_set_stage():
    data = request.get_json()
    stage = data.get("stage")
    result = climate_controller.set_stage(stage)
    if result.get("ok"):
        socketio.emit("climate_status", climate_controller.get_status())
    return jsonify(result)

@app.route("/api/climate/stages")
@login_required
def climate_stages():
    stages = []
    for name in STAGE_ORDER:
        info = STAGE_THRESHOLDS[name]
        stages.append({
            "id": name,
            "descripcion": info.get("descripcion", name),
            "duracion_dias": info.get("duracion_dias", 0),
            "light_hours": info.get("light_hours", 18),
            "temp_range": f"{info['temp_min']}-{info['temp_max']}°C",
            "hum_range": f"{info['hum_min']}-{info['hum_max']}%",
        })
    return jsonify(stages)

@app.route("/api/climate/light", methods=["POST"])
@login_required
def climate_set_light():
    data = request.get_json()
    light_on_hour = data.get("light_on_hour")
    if light_on_hour is not None:
        db.set_config("light_on_hour", str(int(light_on_hour)))
    return jsonify({"ok": True})

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

@socketio.on("manual_irrigate")
def handle_manual_irrigate(data):
    zone_id = data.get("zone_id")
    duration = data.get("duration_minutes", 5)
    result = irrigation_manager.manual_irrigate(zone_id, duration)
    if not result.get("ok"):
        emit("alert", {"type": "error", "message": result.get("error", "")})
    socketio.emit("irrigation_status", irrigation_manager.get_status())

@socketio.on("stop_irrigation")
def handle_stop_irrigation(data):
    zone_id = data.get("zone_id")
    irrigation_manager.close_valve(zone_id, reason="manual_stop")
    socketio.emit("irrigation_status", irrigation_manager.get_status())

@socketio.on("set_climate_mode")
def handle_set_climate_mode(data):
    mode = data.get("mode")
    if mode in ("auto", "manual"):
        climate_controller.set_mode(mode)
        socketio.emit("climate_status", climate_controller.get_status())

@socketio.on("set_stage")
def handle_set_stage(data):
    stage = data.get("stage")
    result = climate_controller.set_stage(stage)
    if result.get("ok"):
        socketio.emit("climate_status", climate_controller.get_status())

@socketio.on("toggle_actuador")
def handle_toggle(data):
    nombre = data.get("nombre")
    accion = data.get("accion")
    if accion == "on":
        result = actuator_manager.turn_on(nombre)
    elif accion == "off":
        result = actuator_manager.turn_off(nombre)
    else:
        result = {"ok": False, "error": "Accion desconocida"}

    if result.get("ok"):
        db.log_actuator_event(nombre, accion, triggered_by="manual")
    else:
        emit("alert", {"type": "conflict", "message": result.get("error", "")})

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
            if temp is not None and (temp <= 0 or temp > 80):
                temp = None
            if hum is not None and (hum <= 0 or hum > 100):
                hum = None
            if co2 is not None and (co2 <= 0 or co2 > 5000):
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

            # Leer sensores de suelo (Arduino) si disponibles
            try:
                zone_data = sensor_reader.read_zone_data()
                if zone_data:
                    for zone_id, readings in zone_data.items():
                        for variable, value in readings.items():
                            if value is not None:
                                db.save_soil_reading(zone_id, "consolidated", variable, value)
                    socketio.emit("soil_data", zone_data)
            except Exception:
                pass

            # Emitir estado del controlador climatico
            try:
                socketio.emit("climate_status", climate_controller.get_status())
            except Exception:
                pass

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
        irrigation_manager.start()
        camera_manager.start()
        climate_controller.start()
        print("Dashboard disponible en http://0.0.0.0:5000")
        socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
    finally:
        climate_controller.stop()
        irrigation_manager.stop()
        camera_manager.stop()
        limpiar_gpio()
