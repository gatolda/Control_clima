import tkinter as tk
from Sensores.temp_humidity import TempHumiditySensor
from logica.reglas_clima import ReglasClima
import time

class VisualClima:
    def __init__(self, root):
        self.root = root
        self.root.title("Control Climático")

        # Sensores
        self.sensor = TempHumiditySensor(pin=4)
        self.logica = ReglasClima()
        self.logica.configurar_actuadores(ventilador_pin=17, humidificador_pin=18)

        # Etiquetas
        self.temp_label = tk.Label(root, text="Temperatura: -- °C")
        self.temp_label.pack()
        self.hum_label = tk.Label(root, text="Humedad: -- %")
        self.hum_label.pack()

        # Botones y estados de actuadores
        self.vent_state = tk.BooleanVar(value=False)
        self.humid_state = tk.BooleanVar(value=False)
        self.vent_button = tk.Button(root, text="Ventilador (Off)", command=self.toggle_ventilador)
        self.vent_button.pack()
        self.humid_button = tk.Button(root, text="Humidificador (Off)", command=self.toggle_humidificador)
        self.humid_button.pack()

        # Actualización
        self.update()

    def update(self):
        datos = self.sensor.leer()
        if datos["estado"] == "OK":
            self.temp_label.config(text=f"Temperatura: {datos['temperatura']:.1f} °C")
            self.hum_label.config(text=f"Humedad: {datos['humedad']:.1f} %")
            decisiones = self.logica.decidir(datos)
            self.logica.ejecutar(decisiones)

            # Actualizar estados manuales
            self.vent_state.set(self.logica.get_estado_actuador("ventilador"))
            self.humid_state.set(self.logica.get_estado_actuador("humidificador"))
            self.vent_button.config(text=f"Ventilador ({'On' if self.vent_state.get() else 'Off'})")
            self.humid_button.config(text=f"Humidificador ({'On' if self.humid_state.get() else 'Off'})")

        self.root.after(5000, self.update)  # Actualizar cada 5 segundos

    def toggle_ventilador(self):
        new_state = not self.vent_state.get()
        self.logica.actuadores["ventilador"].activar(new_state)
        self.vent_state.set(new_state)
        self.vent_button.config(text=f"Ventilador ({'On' if new_state else 'Off'})")

    def toggle_humidificador(self):
        new_state = not self.humid_state.get()
        self.logica.actuadores["humidificador"].activar(new_state)
        self.humid_state.set(new_state)
        self.humid_button.config(text=f"Humidificador ({'On' if new_state else 'Off'})")

if __name__ == "__main__":
    root = tk.Tk()
    app = VisualClima(root)
    root.mainloop()
