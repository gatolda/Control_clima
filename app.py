# app.py
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
from config_loader import ConfigLoader
from sensor_reader import SensorReader
from actuator_manager import ActuatorManager
from gpio_setup import inicializar_gpio, limpiar_gpio
import threading
import time

app = Flask(__name__)
app.config["SECRET_KEY"] = "invernadero-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Inicializar configuracion, sensores y actuadores
inicializar_gpio()
config = ConfigLoader()
config.cargar_configuracion()
sensor_reader = SensorReader(config)
actuator_manager = ActuatorManager(config)

# Ultima lectura de sensores (compartida entre threads)
latest_sensor_data = {}
sensor_lock = threading.Lock()

# --- Rutas HTTP ---

@app.route("/")
def index():
    actuadores = list(actuator_manager.relay_pins.keys())
    return render_template("index.html", actuadores=actuadores)

@app.route("/sensores")
def get_sensores():
    with sensor_lock:
        return jsonify(latest_sensor_data)

@app.route("/actuadores/estado")
def estado_actuadores():
    return jsonify(actuator_manager.status())

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
    socketio.emit("actuator_status", actuator_manager.status())

# --- Background thread para lecturas de sensores ---

def sensor_background_thread():
    global latest_sensor_data
    print("Background thread de sensores iniciado")
    while True:
        try:
            datos = sensor_reader.read_all()
            with sensor_lock:
                latest_sensor_data = datos
            print(f"Sensores: temp={datos.get('temperatura_humedad', {}).get('temperature')}, hum={datos.get('temperatura_humedad', {}).get('humidity')}, co2={datos.get('co2', {}).get('co2')}", flush=True)
            socketio.emit("sensor_data", datos)
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
