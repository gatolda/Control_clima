from flask import Flask, render_template, jsonify, request
from sensor_reader import SensorReader
from actuator_manager import ActuatorManager
from config_loader import ConfigLoader

# Inicializa la configuración
config = ConfigLoader()
config.cargar_configuracion()

# Inicializa sensores y actuadores
sensor_reader = SensorReader(config)
actuator_manager = ActuatorManager(config)

# Flask app
app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/sensores")
def api_sensores():
    datos = sensor_reader.read_all()
    return jsonify(datos)

@app.route("/api/actuadores/<nombre>", methods=["POST"])
def api_actuadores(nombre):
    accion = request.json.get("accion")
    if accion == "on":
        actuator_manager.turn_on(nombre)
    elif accion == "off":
        actuator_manager.turn_off(nombre)
    return jsonify({"status": "ok", "accion": accion, "actuador": nombre})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
