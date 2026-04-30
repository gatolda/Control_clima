# app.py
from functools import wraps
from flask import Flask, render_template, jsonify, request, redirect, url_for, abort
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from core.config_loader import ConfigLoader
from core.sensor_reader import SensorReader
from core.actuator_manager import ActuatorManager
from core.gpio_setup import inicializar_gpio, limpiar_gpio
from data.database import Database
from core.irrigation_manager import IrrigationManager
from core.camera_manager import CameraManager
from core.climate_controller import ClimateController
from data.models import STAGE_THRESHOLDS, STAGE_ORDER, CROP_EVENT_TYPES
from cloud_agent.config import AgentConfig
from cloud_agent.agent import CloudAgent
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

# Inicializar hardware + DB (DB antes que nada para poder bootstrap admin)
inicializar_gpio()
config = ConfigLoader()
config.cargar_configuracion()
sensor_reader = SensorReader(config)
actuator_manager = ActuatorManager(config)
db = Database()

# Bootstrap: si la tabla users esta vacia, crear el admin desde .env
def _bootstrap_admin():
    if not db.list_users(include_inactive=True):
        admin_user = os.environ.get("ADMIN_USER", "admin")
        admin_pass = os.environ.get("ADMIN_PASSWORD")
        if not admin_pass:
            print("[auth] WARN: ADMIN_PASSWORD no definida y no hay usuarios en la DB. Login deshabilitado hasta crear uno.")
            return
        uid = db.create_user(admin_user, admin_pass, role="admin")
        if uid:
            print(f"[auth] Admin inicial creado: {admin_user} (id={uid})")
_bootstrap_admin()

class User(UserMixin):
    def __init__(self, user_id, username, role):
        self.id = str(user_id)
        self.user_id = int(user_id)
        self.username = username
        self.role = role

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def can_write(self):
        return self.role in ("admin", "operator")

@login_manager.user_loader
def load_user(user_id):
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    row = db.get_user_by_id(uid)
    if row and row.get("active"):
        return User(row["id"], row["username"], row["role"])
    return None

# --- Decoradores de rol ---
def role_required(*roles):
    """Protege un endpoint HTTP. El usuario debe tener alguno de los roles listados."""
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator
irrigation_manager = IrrigationManager(config, sensor_reader, actuator_manager, db)
camera_manager = CameraManager(config, db)
climate_controller = ClimateController(config, sensor_reader, actuator_manager, db)

# --- Cloud agent (opcional, se activa si ~/.greenhouse-agent/agent.json existe) ---

def _read_sensors_for_cloud():
    """Adapta read_all() al formato {variable, sensor_id, value} que espera el backend."""
    out = []
    try:
        data = sensor_reader.read_all()
        temp = data.get("temperatura_humedad", {}).get("temperature")
        hum = data.get("temperatura_humedad", {}).get("humidity")
        co2 = data.get("co2", {}).get("co2")
        if temp is not None:
            out.append({"variable": "temperatura", "sensor_id": "dht22_1", "value": float(temp)})
        if hum is not None:
            out.append({"variable": "humedad", "sensor_id": "dht22_1", "value": float(hum)})
        if co2 is not None:
            out.append({"variable": "co2", "sensor_id": "mhz19", "value": float(co2)})
        zone_data = sensor_reader.read_zone_data()
        for zone_id, readings in zone_data.items():
            for variable, value in readings.items():
                if value is not None:
                    out.append({
                        "variable": variable,
                        "sensor_id": f"{zone_id}_{variable}",
                        "value": float(value),
                    })
    except Exception as e:
        print(f"[cloud] error leyendo sensores: {e}", flush=True)
    return out

def _toggle_actuator_for_cloud(nombre, accion):
    """Ejecuta un comando remoto contra el actuator_manager."""
    if accion == "on":
        return actuator_manager.turn_on(nombre)
    return actuator_manager.turn_off(nombre)

cloud_config = AgentConfig.load()
cloud_agent = CloudAgent(
    config=cloud_config,
    read_sensors=_read_sensors_for_cloud,
    toggle_actuator=_toggle_actuator_for_cloud,
)

# Ultima lectura de sensores (compartida entre threads)
latest_sensor_data = {}
app_started_at = time.time()
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
        row = db.get_user_by_username(username)
        if row and db.verify_password(row["id"], password):
            login_user(User(row["id"], row["username"], row["role"]), remember=True)
            db.update_last_login(row["id"])
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
@role_required("admin", "operator")
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

# --- Health endpoint (publico, para monitoring externo) ---
@app.route("/health")
def health():
    """
    Devuelve el estado general del sistema en JSON.
    No requiere login para que monitoring externo pueda chequearlo.
    Status: ok (todo bien), degraded (algo no esta optimo), error (critico).
    """
    issues = []
    components = {}

    # 1. DB
    try:
        with sensor_lock:
            pass  # solo para asegurar que la app no esta deadlocked
        db.get_config("stage")
        components["db"] = "ok"
    except Exception as e:
        components["db"] = f"error: {e}"
        issues.append("db")

    # 2. Sensor freshness
    last_age = None
    try:
        with sensor_lock:
            data = latest_sensor_data or {}
        ts = data.get("_ts")
        if ts:
            last_age = round(time.time() - ts, 1)
            if last_age > 60:
                issues.append(f"sensores stale ({last_age}s)")
                components["sensors"] = f"stale ({last_age}s)"
            else:
                components["sensors"] = "ok"
        else:
            components["sensors"] = "no_data_yet"
    except Exception as e:
        components["sensors"] = f"error: {e}"
        issues.append("sensors")

    # 3. Sensor health (DHT22, CO2, etc.)
    try:
        sh = sensor_reader.get_sensor_health()
        for name, info in (sh or {}).items():
            ok = info.get("status") == "ok" or info.get("healthy") is True
            if not ok:
                issues.append(f"{name}_unhealthy")
        components["sensor_health"] = sh
    except Exception as e:
        components["sensor_health"] = f"error: {e}"

    # 4. Cloud agent (informativo, no bloquea)
    components["cloud_agent"] = "active" if cloud_config.is_activated else "disabled"

    # 5. App uptime
    uptime_s = round(time.time() - app_started_at, 1)
    components["uptime_seconds"] = uptime_s

    if not issues:
        status = "ok"
        http_code = 200
    elif any(k.startswith("db") for k in issues):
        status = "error"
        http_code = 503
    else:
        status = "degraded"
        http_code = 200  # respondemos 200 para no alertar prematuramente, pero el body lo dice

    return jsonify({
        "status": status,
        "issues": issues,
        "components": components,
        "last_reading_age_seconds": last_age,
        "timestamp": time.time(),
    }), http_code

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
@role_required("admin", "operator")
def irrigation_manual():
    data = request.get_json()
    zone_id = data.get("zone_id")
    duration = data.get("duration_minutes", 5)
    result = irrigation_manager.manual_irrigate(zone_id, duration)
    if result.get("ok"):
        socketio.emit("irrigation_status", irrigation_manager.get_status())
    return jsonify(result)

@app.route("/api/irrigation/stop", methods=["POST"])
@role_required("admin", "operator")
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
@role_required("admin", "operator")
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
@role_required("admin", "operator")
def climate_set_mode():
    data = request.get_json()
    mode = data.get("mode")
    if mode not in ("auto", "manual"):
        return jsonify({"ok": False, "error": "Modo debe ser 'auto' o 'manual'"})
    climate_controller.set_mode(mode)
    socketio.emit("climate_status", climate_controller.get_status())
    return jsonify({"ok": True, "mode": mode})

@app.route("/api/climate/stage", methods=["POST"])
@role_required("admin", "operator")
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
@role_required("admin", "operator")
def climate_set_light():
    data = request.get_json()
    light_on_hour = data.get("light_on_hour")
    if light_on_hour is not None:
        db.set_config("light_on_hour", str(int(light_on_hour)))
    return jsonify({"ok": True})

# --- Users API (admin) ---

def _user_dto(u):
    """Serializa un usuario omitiendo el password_hash."""
    return {
        "id": u["id"],
        "username": u["username"],
        "role": u["role"],
        "active": bool(u["active"]),
        "created_at": u.get("created_at"),
        "last_login": u.get("last_login"),
    }

@app.route("/api/users", methods=["GET"])
@role_required("admin")
def users_list():
    include_inactive = request.args.get("all") == "1"
    return jsonify([_user_dto(u) for u in db.list_users(include_inactive=include_inactive)])

@app.route("/api/users", methods=["POST"])
@role_required("admin")
def users_create():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = data.get("role") or "viewer"
    if not username or not password:
        return jsonify({"ok": False, "error": "username y password requeridos"}), 400
    try:
        uid = db.create_user(username, password, role)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    if not uid:
        return jsonify({"ok": False, "error": "Username ya existe"}), 409
    return jsonify({"ok": True, "id": uid})

@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@role_required("admin")
def users_deactivate(user_id):
    target = db.get_user_by_id(user_id)
    if not target:
        return jsonify({"ok": False, "error": "Usuario no encontrado"}), 404
    if user_id == current_user.user_id:
        return jsonify({"ok": False, "error": "No podes desactivar tu propia cuenta"}), 400
    # Evitar dejar el sistema sin admins
    if target["role"] == "admin" and db.count_admins() <= 1:
        return jsonify({"ok": False, "error": "No queda ningun otro admin activo"}), 400
    db.set_user_active(user_id, False)
    return jsonify({"ok": True})

@app.route("/api/users/<int:user_id>/password", methods=["POST"])
@login_required
def users_update_password(user_id):
    # Admin puede cambiar cualquier password; usuario comun solo la propia
    if not (current_user.is_admin or current_user.user_id == user_id):
        abort(403)
    data = request.get_json() or {}
    password = data.get("password") or ""
    if len(password) < 6:
        return jsonify({"ok": False, "error": "Password debe tener al menos 6 caracteres"}), 400
    try:
        db.update_user_password(user_id, password)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True})

@app.route("/api/users/<int:user_id>/role", methods=["POST"])
@role_required("admin")
def users_update_role(user_id):
    data = request.get_json() or {}
    new_role = data.get("role")
    target = db.get_user_by_id(user_id)
    if not target:
        return jsonify({"ok": False, "error": "Usuario no encontrado"}), 404
    # No degradar al ultimo admin
    if target["role"] == "admin" and new_role != "admin" and db.count_admins() <= 1:
        return jsonify({"ok": False, "error": "No queda ningun otro admin activo"}), 400
    try:
        db.update_user_role(user_id, new_role)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True})

# Inyectar current_user en el contexto de todos los templates
@app.context_processor
def inject_user():
    return {"user": current_user}

# --- Calendario / Crop cycle API ---

def _next_stage_after(stage):
    """Devuelve el nombre de la etapa que sigue, o None si es la ultima."""
    try:
        i = STAGE_ORDER.index(stage)
        return STAGE_ORDER[i + 1] if i + 1 < len(STAGE_ORDER) else None
    except ValueError:
        return None

def _build_timeline(cycle):
    """Construye la metadata visual del ciclo: dia actual, dias en fase, predicciones."""
    if not cycle:
        return None
    from datetime import date as _date
    today = _date.today()
    start = _date.fromisoformat(cycle["start_date"])
    stage_start = _date.fromisoformat(cycle["stage_started_at"])
    day_of_cycle = (today - start).days + 1
    days_in_stage = (today - stage_start).days

    stage = cycle["current_stage"]
    th = STAGE_THRESHOLDS.get(stage, {})
    stage_duration = th.get("duracion_dias", 0)
    days_remaining = max(0, stage_duration - days_in_stage) if stage_duration else None
    transition_due = stage_duration > 0 and days_in_stage >= stage_duration

    # Construir secuencia de etapas con sus fechas previstas
    stages_plan = []
    cursor = start
    for s in STAGE_ORDER:
        d = STAGE_THRESHOLDS.get(s, {}).get("duracion_dias", 0)
        stages_plan.append({
            "stage": s,
            "starts": cursor.isoformat(),
            "ends": (cursor + __import__("datetime").timedelta(days=d)).isoformat() if d else None,
            "days": d,
            "is_current": s == stage,
            "is_past": STAGE_ORDER.index(s) < STAGE_ORDER.index(stage) if stage in STAGE_ORDER else False,
        })
        if d:
            cursor = cursor + __import__("datetime").timedelta(days=d)

    return {
        "cycle": cycle,
        "today": today.isoformat(),
        "day_of_cycle": day_of_cycle,
        "days_in_stage": days_in_stage,
        "stage_duration": stage_duration,
        "days_remaining_in_stage": days_remaining,
        "transition_due": transition_due,
        "next_stage": _next_stage_after(stage),
        "stages_plan": stages_plan,
        "stage_info": th.get("descripcion", ""),
    }

@app.route("/calendar")
@login_required
def calendar_page():
    return render_template("calendar.html")

@app.route("/api/cycle/current")
@login_required
def api_cycle_current():
    active = db.get_active_cycle()
    if not active:
        return jsonify({"active": False})
    return jsonify({"active": True, **_build_timeline(active)})

@app.route("/api/cycle", methods=["POST"])
@role_required("admin", "operator")
def api_cycle_create():
    data = request.get_json() or {}
    start_date = data.get("start_date")
    stage = data.get("current_stage", "germinacion")
    name = data.get("name")
    notes = data.get("notes")
    if not start_date:
        return jsonify({"ok": False, "error": "start_date requerido"}), 400
    # Cerrar ciclo activo si existe
    closed = db.end_active_cycle()
    try:
        cid = db.create_cycle(start_date=start_date, current_stage=stage, name=name, notes=notes)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    # Sincronizar con el climate controller
    db.set_config("stage", stage)
    return jsonify({"ok": True, "cycle_id": cid, "previous_closed": closed})

@app.route("/api/cycle/end", methods=["POST"])
@role_required("admin", "operator")
def api_cycle_end():
    data = request.get_json() or {}
    end_date = data.get("end_date")
    closed = db.end_active_cycle(end_date=end_date)
    if not closed:
        return jsonify({"ok": False, "error": "No hay ciclo activo"}), 404
    return jsonify({"ok": True, "closed_cycle_id": closed})

@app.route("/api/cycle/advance-stage", methods=["POST"])
@role_required("admin", "operator")
def api_cycle_advance():
    """Avanza al siguiente stage del ciclo activo. Tambien acepta target stage especifico."""
    active = db.get_active_cycle()
    if not active:
        return jsonify({"ok": False, "error": "No hay ciclo activo"}), 404
    data = request.get_json() or {}
    target = data.get("stage")
    if not target:
        target = _next_stage_after(active["current_stage"])
    if not target:
        return jsonify({"ok": False, "error": "Ya estas en la ultima etapa"}), 400
    if target not in STAGE_THRESHOLDS:
        return jsonify({"ok": False, "error": "Etapa invalida"}), 400
    db.update_cycle_stage(active["id"], target)
    db.set_config("stage", target)
    # Crear evento automatico de cambio de fase
    from datetime import date as _date
    try:
        db.create_crop_event(
            cycle_id=active["id"],
            date=_date.today().isoformat(),
            event_type="fase_cambio",
            notes=f"Cambio de {active['current_stage']} a {target}",
            created_by=getattr(current_user, "user_id", None),
        )
    except Exception:
        pass
    socketio.emit("climate_status", climate_controller.get_status())
    return jsonify({"ok": True, "new_stage": target})

@app.route("/api/cycle/events", methods=["GET"])
@login_required
def api_cycle_events_list():
    active = db.get_active_cycle()
    if not active:
        return jsonify([])
    days_past = request.args.get("days_past", 30, type=int)
    days_future = request.args.get("days_future", 30, type=int)
    return jsonify(db.list_crop_events(active["id"], days_past=days_past, days_future=days_future))

@app.route("/api/cycle/events", methods=["POST"])
@role_required("admin", "operator")
def api_cycle_events_create():
    active = db.get_active_cycle()
    if not active:
        return jsonify({"ok": False, "error": "No hay ciclo activo"}), 400
    data = request.get_json() or {}
    date = data.get("date")
    event_type = data.get("event_type")
    notes = data.get("notes")
    if not date or not event_type:
        return jsonify({"ok": False, "error": "date y event_type son requeridos"}), 400
    try:
        eid = db.create_crop_event(
            cycle_id=active["id"], date=date, event_type=event_type, notes=notes,
            created_by=getattr(current_user, "user_id", None),
        )
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "event_id": eid})

@app.route("/api/cycle/events/<int:event_id>/complete", methods=["POST"])
@role_required("admin", "operator")
def api_event_complete(event_id):
    data = request.get_json() or {}
    completed = data.get("completed", True)
    db.mark_event_completed(event_id, completed=bool(completed))
    return jsonify({"ok": True})

@app.route("/api/cycle/events/<int:event_id>", methods=["DELETE"])
@role_required("admin", "operator")
def api_event_delete(event_id):
    db.delete_crop_event(event_id)
    return jsonify({"ok": True})

@app.route("/api/cycle/event-types")
@login_required
def api_event_types():
    return jsonify(list(CROP_EVENT_TYPES))

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

def _require_write():
    """Valida que el usuario del socket pueda escribir. Emite alerta si no."""
    if not current_user.is_authenticated:
        emit("alert", {"type": "auth", "message": "Debes iniciar sesion"})
        return False
    if not getattr(current_user, "can_write", False):
        emit("alert", {"type": "denied", "message": "Tu usuario es de solo lectura"})
        return False
    return True

@socketio.on("manual_irrigate")
def handle_manual_irrigate(data):
    if not _require_write():
        return
    zone_id = data.get("zone_id")
    duration = data.get("duration_minutes", 5)
    result = irrigation_manager.manual_irrigate(zone_id, duration)
    if not result.get("ok"):
        emit("alert", {"type": "error", "message": result.get("error", "")})
    socketio.emit("irrigation_status", irrigation_manager.get_status())

@socketio.on("stop_irrigation")
def handle_stop_irrigation(data):
    if not _require_write():
        return
    zone_id = data.get("zone_id")
    irrigation_manager.close_valve(zone_id, reason="manual_stop")
    socketio.emit("irrigation_status", irrigation_manager.get_status())

@socketio.on("set_climate_mode")
def handle_set_climate_mode(data):
    if not _require_write():
        return
    mode = data.get("mode")
    if mode in ("auto", "manual"):
        climate_controller.set_mode(mode)
        socketio.emit("climate_status", climate_controller.get_status())

@socketio.on("set_stage")
def handle_set_stage(data):
    if not _require_write():
        return
    stage = data.get("stage")
    result = climate_controller.set_stage(stage)
    if result.get("ok"):
        socketio.emit("climate_status", climate_controller.get_status())

@socketio.on("toggle_actuador")
def handle_toggle(data):
    if not _require_write():
        return
    nombre = data.get("nombre")
    accion = data.get("accion")
    if accion == "on":
        result = actuator_manager.turn_on(nombre)
    elif accion == "off":
        result = actuator_manager.turn_off(nombre)
    else:
        result = {"ok": False, "error": "Accion desconocida"}

    if result.get("ok"):
        uid = getattr(current_user, "user_id", None)
        db.log_actuator_event(nombre, accion, triggered_by="manual", user_id=uid)
        cloud_agent.record_actuator_event(nombre, accion, triggered_by="manual")
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
                "co2": {"co2": co2},
                "_ts": time.time(),
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
        cloud_agent.start()  # no-op si no esta activado
        print("Dashboard disponible en http://0.0.0.0:5000")
        socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
    finally:
        cloud_agent.stop()
        climate_controller.stop()
        irrigation_manager.stop()
        camera_manager.stop()
        limpiar_gpio()
