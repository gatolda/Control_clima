# Dashboard GUI classes

import customtkinter as ctk
import RPi.GPIO as GPIO
import Adafruit_DHT
from collections import deque
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import time
import os
import threading

from Sensores.temp_humidity import TempHumiditySensor


class CO2PWMSensor:
    """Simple PWM based CO2 sensor reader."""

    def __init__(self, pin, cal_file):
        self.pin = pin
        self.cal_file = cal_file
        self._load_calibration()
        GPIO.setup(self.pin, GPIO.IN)

    def _load_calibration(self):
        try:
            with open(self.cal_file, "r") as f:
                self.pulse_min = float(f.readline().strip())
                self.pulse_max = float(f.readline().strip())
        except FileNotFoundError:
            self.pulse_min, self.pulse_max = 0.002, 0.010

    def _measure_pulse(self):
        try:
            GPIO.wait_for_edge(self.pin, GPIO.RISING)
            t1 = time.time()
            GPIO.wait_for_edge(self.pin, GPIO.FALLING)
            t2 = time.time()
            return t2 - t1
        except Exception:
            return None

    def read(self):
        pulse = self._measure_pulse()
        if not pulse:
            return 0
        ppm = ((pulse - self.pulse_min) / (self.pulse_max - self.pulse_min)) * (5000 - 500) + 500
        ppm = max(500, min(int(ppm), 5000))
        return ppm

    def save_calibration(self):
        with open(self.cal_file, "w") as f:
            f.write(f"{self.pulse_min}\n{self.pulse_max}\n")


class Gauge:
    """Encapsulates the gauge drawing on a CTkCanvas."""

    def __init__(self, parent, title, color, max_value):
        self.max_value = max_value
        self.color = color
        self.canvas = ctk.CTkCanvas(parent, width=200, height=200, bg="#2B2B2B", highlightthickness=0)
        self.canvas.pack(pady=10)

        fig = Figure(figsize=(3, 2), dpi=100)
        self.ax = fig.add_subplot(111)
        self.ax.set_title(title, fontsize=10)
        self.ax.tick_params(axis='both', which='major', labelsize=8)
        self.ax.grid(True)
        self.line, = self.ax.plot([], [], color=color)
        self.graph = FigureCanvasTkAgg(fig, master=parent)
        self.graph.get_tk_widget().pack()

    def draw(self, value):
        self.canvas.delete("gauge")
        x = y = 100
        radius = 70
        start = -90
        extent = 180
        self.canvas.create_arc(x-radius, y-radius, x+radius, y+radius, start=start, extent=extent, style="arc", outline="#555", width=15, tags="gauge")
        angle = extent * (value / self.max_value)
        self.canvas.create_arc(x-radius, y-radius, x+radius, y+radius, start=start, extent=angle, style="arc", outline=self.color, width=15, tags="gauge")
        self.canvas.create_text(x, y, text=f"{value}", fill="white", font=("Roboto", 20, "bold"), tags="gauge")


class Dashboard:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self.window = ctk.CTk()
        self.window.geometry("1200x1050")
        self.window.title("🌱 Dashboard Climático con Calibración Manual")

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        self.relay_pins = [18, 20, 21, 23]
        self.relay_states = [False] * 4
        self.auto_mode = False
        for pin in self.relay_pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)

        # Sensors
        self.temp_sensor = TempHumiditySensor(4)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.cal_file = os.path.join(os.path.dirname(base_dir), "calibracion_pwm.txt")
        self.co2_sensor = CO2PWMSensor(17, self.cal_file)

        self.max_data = 30
        self.temp_data = deque([0]*self.max_data, maxlen=self.max_data)
        self.hum_data = deque([0]*self.max_data, maxlen=self.max_data)
        self.co2_data = deque([0]*self.max_data, maxlen=self.max_data)

        self._build_ui()
        self.window.protocol("WM_DELETE_WINDOW", self._close)

    # -------------------- UI --------------------
    def _build_ui(self):
        frame_sensores = ctk.CTkFrame(self.window)
        frame_sensores.pack(padx=10, pady=10, fill="both", expand=True)

        self.temp_gauge = Gauge(frame_sensores, "🌡️ Temperatura (°C)", "#E74C3C", 50)
        self.hum_gauge = Gauge(frame_sensores, "💧 Humedad (%)", "#3498DB", 100)
        self.co2_gauge = Gauge(frame_sensores, "🍃 CO₂ (ppm)", "#2ECC71", 5000)

        self.btn_auto = ctk.CTkButton(
            self.window,
            text="⚙️ Modo Automático: OFF",
            fg_color="#C0392B",
            font=("Roboto", 16, "bold"),
            corner_radius=10,
            command=self.toggle_auto_mode,
        )
        self.btn_auto.pack(pady=10)

        self.frame_relays = ctk.CTkFrame(self.window, corner_radius=15)
        self.frame_relays.pack(padx=10, pady=10, fill="x")

        self.components = [
            "🔄 Extractor",
            "🌬️ Instractor",
            "🔃 Circulación",
            "💧 Humidificador",
        ]

        self.relay_buttons = []
        for i, comp in enumerate(self.components):
            btn = ctk.CTkButton(
                self.frame_relays,
                text=f"{comp} 🔴 OFF",
                fg_color="#C0392B",
                font=("Roboto", 14, "bold"),
                corner_radius=10,
                command=lambda idx=i: self.toggle_relay(idx),
            )
            btn.grid(row=0, column=i, padx=10, pady=10, sticky="ew")
            self.relay_buttons.append(btn)

        frame_cal = ctk.CTkFrame(self.window, corner_radius=15)
        frame_cal.pack(padx=10, pady=10)

        self.btn_cal_min = ctk.CTkButton(
            frame_cal,
            text="🌿 Comenzar calibración mínima",
            fg_color="#27AE60",
            font=("Roboto", 14, "bold"),
            corner_radius=10,
            command=self.calibrate_min,
        )
        self.btn_cal_min.pack(side="left", padx=10, pady=5)

        self.btn_cal_max = ctk.CTkButton(
            frame_cal,
            text="🫧 Comenzar calibración máxima",
            fg_color="#C0392B",
            font=("Roboto", 14, "bold"),
            corner_radius=10,
            command=self.calibrate_max,
        )
        self.btn_cal_max.pack(side="left", padx=10, pady=5)

        self.txt_status = ctk.CTkLabel(self.window, text="Dashboard iniciado", font=("Roboto", 14))
        self.txt_status.pack(pady=5)

    # -------------------- Relay control --------------------
    def toggle_relay(self, idx):
        if self.auto_mode:
            return
        self.relay_states[idx] = not self.relay_states[idx]
        GPIO.output(self.relay_pins[idx], GPIO.LOW if self.relay_states[idx] else GPIO.HIGH)
        self._update_relay_buttons()

    def toggle_auto_mode(self):
        self.auto_mode = not self.auto_mode
        if self.auto_mode:
            self.btn_auto.configure(text="🤖 Modo Automático: ON", fg_color="#27AE60")
        else:
            self.btn_auto.configure(text="⚙️ Modo Automático: OFF", fg_color="#C0392B")
            for i in range(4):
                self.relay_states[i] = False
                GPIO.output(self.relay_pins[i], GPIO.HIGH)
            self._update_relay_buttons()

    def _update_relay_buttons(self):
        for i, btn in enumerate(self.relay_buttons):
            btn.configure(
                text=f"{self.components[i]} {'🟢 ON' if self.relay_states[i] else '🔴 OFF'}",
                fg_color="#27AE60" if self.relay_states[i] else "#C0392B",
            )

    # -------------------- Calibration --------------------
    def calibrate_min(self):
        def _average():
            self.txt_status.configure(text="🌿 Midiendo pulso mínimo (30s en aire limpio)...")
            pulses = []
            start = time.time()
            while time.time() - start < 30:
                p = self.co2_sensor._measure_pulse()
                if p:
                    pulses.append(p)
            if pulses:
                self.co2_sensor.pulse_min = sum(pulses) / len(pulses)
                self.txt_status.configure(text=f"✅ Pulso mínimo guardado: {self.co2_sensor.pulse_min*1000:.2f} ms")
                self.co2_sensor.save_calibration()
        threading.Thread(target=_average).start()

    def calibrate_max(self):
        def _average():
            self.txt_status.configure(text="🫧 Midiendo pulso máximo (30s en CO₂ saturado)...")
            pulses = []
            start = time.time()
            while time.time() - start < 30:
                p = self.co2_sensor._measure_pulse()
                if p:
                    pulses.append(p)
            if pulses:
                self.co2_sensor.pulse_max = sum(pulses) / len(pulses)
                self.txt_status.configure(text=f"✅ Pulso máximo guardado: {self.co2_sensor.pulse_max*1000:.2f} ms")
                self.co2_sensor.save_calibration()
        threading.Thread(target=_average).start()

    # -------------------- Update --------------------
    def _update(self):
        data = self.temp_sensor.read()
        temp = round(data.get("temperature") or 0, 1)
        hum = round(data.get("humidity") or 0, 1)
        co2 = self.co2_sensor.read()

        self.temp_data.append(temp)
        self.hum_data.append(hum)
        self.co2_data.append(co2)

        self.temp_gauge.draw(temp)
        self.hum_gauge.draw(hum)
        self.co2_gauge.draw(co2)

        for gauge, line_data in [
            (self.temp_gauge, self.temp_data),
            (self.hum_gauge, self.hum_data),
            (self.co2_gauge, self.co2_data),
        ]:
            gauge.line.set_data(range(len(line_data)), list(line_data))
            gauge.ax.set_xlim(0, self.max_data)
            gauge.ax.set_ylim(min(line_data)-5, max(line_data)+5)
            gauge.graph.draw()

        self.window.after(3000, self._update)

    # -------------------- Lifecycle --------------------
    def _close(self):
        GPIO.cleanup()
        self.window.destroy()

    def run(self):
        self._update()
        self.window.mainloop()
