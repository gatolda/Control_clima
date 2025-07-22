# app.py
from flask import Flask, render_template, request, jsonify
from config_loader import ConfigLoader
from sensor_reader import SensorReader
from actuator_manager import ActuatorManager
from gpio_setup import setup_gpio, cleanup_gpio

app = Flask(__name__)

# ✅ Inicializar configuración, sensores y actuadores
setup_gpio()
config = ConfigLoader()
config.cargar_configuracion()
sensor_reader = SensorReader(config)
actuator_manager = ActuatorManager(config)

@app.route("/")
def index():
    # 🔑 Enviar lista de actuadores (corrigido relay_pins.keys())
    return render_template("index.html", actuadores=actuator_manager.relay_pins.keys())

@app.route("/sensores")
def get_sensores():
    datos = sensor_reader.read_all()
    return jsonify(datos)

@app.route("/actuador/<nombre>/<accion>", methods=["POST"])
def controlar_actuador(nombre, accion):
    if accion == "on":
        actuator_manager.turn_on(nombre)
        estado = "activado"
    elif accion == "off":
        actuator_manager.turn_off(nombre)
        estado = "desactivado"
    else:
        estado = "comando desconocido"
    return jsonify({"actuador": nombre, "accion": accion, "estado": estado})

@app.route("/actuadores/estado")
def estado_actuadores():
    # 📢 Devuelve estados de los actuadores
    return jsonify(actuator_manager.status())

@app.errorhandler(404)
def not_found(error):
    return "Página no encontrada", 404

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5000, debug=True)
    finally:
        cleanup_gpio()
