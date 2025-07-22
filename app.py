from flask import Flask, render_template, jsonify, request
from config_loader import ConfigLoader
from sensor_reader import SensorReader
from actuator_manager import ActuatorManager
import gpio_setup

# Inicializar Flask
app = Flask(__name__)

# Inicializar configuración
config = ConfigLoader()
config.cargar_configuracion()

# Inicializar sensores y actuadores
sensor_reader = SensorReader(config)
actuator_manager = ActuatorManager(config)

@app.route("/")
def index():
    """
    Página principal
    """
    return render_template("index.html", actuadores=actuator_manager.relays.keys())

@app.route("/api/lecturas")
def api_lecturas():
    """
    API para devolver datos de los sensores
    """
    try:
        datos = sensor_reader.read_all()
        return jsonify(datos)
    except Exception as e:
        print(f"⚠️ Error al leer sensores: {e}")
        # Datos simulados en caso de fallo
        return jsonify({
            "temperatura_humedad": {
                "temperature": 20 + (5 * (time.time() % 1)),  # Simulación
                "humidity": 50 + (10 * (time.time() % 1))
            },
            "co2": {"co2": 400 + (50 * (time.time() % 1))}
        })

@app.route("/api/actuadores/<actuador>/<accion>", methods=["POST"])
def api_actuadores(actuador, accion):
    """
    API para controlar actuadores (on/off)
    """
    if actuador not in actuator_manager.relays:
        return jsonify({"status": "error", "message": "Actuador no encontrado"}), 404

    if accion == "on":
        actuator_manager.turn_on(actuador)
    elif accion == "off":
        actuator_manager.turn_off(actuador)
    else:
        return jsonify({"status": "error", "message": "Acción no válida"}), 400

    return jsonify({"status": "ok", "actuador": actuador, "accion": accion})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
