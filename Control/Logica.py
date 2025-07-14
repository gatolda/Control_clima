# Control/logica.py

def analizar_acciones(sensor_data):
    """
    Analiza los datos de sensor y retorna una lista de acciones a ejecutar.
    Por ejemplo, si la temperatura supera 22°C, enciende el canal 2.
    """
    acciones = []
    if sensor_data["status"] == "OK":
        if sensor_data["temperature"] > 22:
            acciones.append({"canal": 2, "accion": "on"})
        else:
            acciones.append({"canal": 2, "accion": "off"})
    return acciones
