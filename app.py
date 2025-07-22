from flask import Flask, render_template, jsonify, request
from config_loader import ConfigLoader
from sensor_reader import SensorReader
from actuator_manager import ActuatorManager
from gpio_setup import setup_gpio, cleanup_gpio

app = Flask(__name__)

# Inicializar configuración y hardware
setup_gpio()
config = ConfigLoader()
config.cargar_configuracion()
sensor_reader = SensorReader(config)
actuator_manager = ActuatorManager(config)

@app.route("/")
def index():
    sensores = sensor_reader.read_all_sensors()
    return render_template("index.html", sensores=sensores)

@app.route("/api/sensores")
def api_sensores():
    """
    Devuelve las lecturas de los sensores en formato JSON.
    """
    datos = sensor_reader.read_all_sensors()
    return jsonify(datos)

@app.route("/api/actuador/<nombre>/<accion>", methods=["POST"])
def controlar_actuador(nombre, accion):
    """
    Controla un actuador: on/off
    """
    if accion == "on":
        actuator_manager.turn_on(nombre)
        estado = "activado"
    elif accion == "off":
        actuator_manager.turn_off(nombre)
        estado = "desactivado"
    else:
        estado = "acción no válida"

    return jsonify({"actuador": nombre, "estado": estado})

@app.teardown_appcontext
def cleanup(exception=None):
    cleanup_gpio()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
