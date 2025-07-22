# app.py
from flask import Flask, render_template, jsonify
from config_loader import ConfigLoader
from sensor_reader import SensorReader
from actuator_manager import ActuatorManager
import gpio_setup
import time

app = Flask(__name__)

# Inicialización
config = ConfigLoader()
config.cargar_configuracion()

sensor_reader = SensorReader(config)
actuator_manager = ActuatorManager(config)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/lecturas")
def api_lecturas():
    """
    Devuelve las últimas lecturas de sensores en formato JSON
    """
    datos = sensor_reader.read_all()
    return jsonify(datos)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
