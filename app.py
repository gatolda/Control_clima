from flask import Flask, render_template, jsonify
from sensor_reader import SensorReader
from actuator_manager import ActuatorManager
from config_loader import ConfigLoader

# 🚀 Inicializar la app Flask
app = Flask(__name__)

# 📦 Cargar configuración y módulos
config = ConfigLoader()
config.cargar_configuracion()
sensor_reader = SensorReader(config)
actuator_manager = ActuatorManager(config)

# 🌐 Ruta principal que devuelve la página web
@app.route("/")
def dashboard():
    return render_template("index.html")

# 🛰️ API para obtener las lecturas de sensores
@app.route("/api/sensores")
def api_sensores():
    datos = sensor_reader.read_all()
    return jsonify(datos)

# 🛰️ API para encender o apagar un relé
@app.route("/api/relay/<nombre>/<accion>")
def api_relay(nombre, accion):
    if accion == "on":
        actuator_manager.turn_on(nombre)
        return jsonify({"status": f"{nombre} activado"})
    elif accion == "off":
        actuator_manager.turn_off(nombre)
        return jsonify({"status": f"{nombre} desactivado"})
    else:
        return jsonify({"error": "Acción no válida"}), 400

# 🚀 Lanzar el servidor
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
