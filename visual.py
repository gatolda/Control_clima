import customtkinter as ctk
import RPi.GPIO as GPIO
import Adafruit_DHT
from collections import deque
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import time
import os
import threading

# ----------- Configuración GPIO relés -----------
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

pines_reles = [18, 20, 21, 23]  # CH1 a CH4
for pin in pines_reles:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.HIGH)  # Relés apagados al inicio

# ----------- Configuración sensores -----------
SENSOR_DHT = Adafruit_DHT.DHT22
PIN_DHT = 4  # GPIO 4 para DHT22
PIN_PWM = 17  # GPIO 17 para MH-Z19 PWM

# ----------- Leer calibración PWM -----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAL_FILE = os.path.join(BASE_DIR, "calibracion_pwm.txt")

# Cargar valores de calibración
def cargar_calibracion():
    global pulso_min, pulso_max
    try:
        with open(CAL_FILE, "r") as f:
            pulso_min = float(f.readline().strip())
            pulso_max = float(f.readline().strip())
        print(f"✅ Calibración cargada: min={pulso_min*1000:.2f}ms, max={pulso_max*1000:.2f}ms")
    except FileNotFoundError:
        print("⚠️ Archivo de calibración no encontrado. Usando valores por defecto.")
        pulso_min, pulso_max = 0.002, 0.010  # Valores por defecto

cargar_calibracion()

GPIO.setup(PIN_PWM, GPIO.IN)

# ----------- Función para medir un pulso PWM -----------
def medir_pulso():
    try:
        GPIO.wait_for_edge(PIN_PWM, GPIO.RISING)
        t1 = time.time()
        GPIO.wait_for_edge(PIN_PWM, GPIO.FALLING)
        t2 = time.time()
        return t2 - t1
    except:
        return None

# ----------- Función para leer CO₂ -----------
def leer_pwm():
    pulso = medir_pulso()
    if pulso:
        ppm = ((pulso - pulso_min) / (pulso_max - pulso_min)) * (5000 - 500) + 500
        ppm = max(500, min(int(ppm), 5000))  # Limitar a rango 500-5000 ppm
        return ppm
    else:
        return 0

# ----------- Variables para gráficos -----------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

max_datos = 30
datos_temp = deque([0]*max_datos, maxlen=max_datos)
datos_hum = deque([0]*max_datos, maxlen=max_datos)
datos_co2 = deque([0]*max_datos, maxlen=max_datos)

reles_estado = [False]*4
modo_automatico = [False]

componentes = [
    "🔄 Extractor", "🌬️ Instractor", "🔃 Circulación", "💧 Humidificador"
]

# ----------- Funciones de control relés -----------
def toggle_rele(idx):
    if modo_automatico[0]:  # Bloquear en modo automático
        return
    reles_estado[idx] = not reles_estado[idx]
    GPIO.output(pines_reles[idx], GPIO.LOW if reles_estado[idx] else GPIO.HIGH)
    actualizar_botones_reles()

def toggle_modo_automatico():
    modo_automatico[0] = not modo_automatico[0]
    if modo_automatico[0]:
        btn_auto.configure(text="🤖 Modo Automático: ON", fg_color="#27AE60")
    else:
        btn_auto.configure(text="⚙️ Modo Automático: OFF", fg_color="#C0392B")
        for i in range(4):
            reles_estado[i] = False
            GPIO.output(pines_reles[i], GPIO.HIGH)
        actualizar_botones_reles()

def actualizar_botones_reles():
    for i, btn in enumerate(botones_reles):
        btn.configure(
            text=f"{componentes[i]} {'🟢 ON' if reles_estado[i] else '🔴 OFF'}",
            fg_color="#27AE60" if reles_estado[i] else "#C0392B"
        )

# ----------- Calibración manual desde la interfaz -----------
def calibrar_minimo():
    def promediar_minimo():
        txt_status.configure(text="🌿 Midiendo pulso mínimo (30s en aire limpio)...")
        pulsos = []
        start = time.time()
        while time.time() - start < 30:
            p = medir_pulso()
            if p:
                pulsos.append(p)
        global pulso_min
        pulso_min = sum(pulsos) / len(pulsos)
        txt_status.configure(text=f"✅ Pulso mínimo guardado: {pulso_min*1000:.2f} ms")
        guardar_calibracion()
    threading.Thread(target=promediar_minimo).start()

def calibrar_maximo():
    def promediar_maximo():
        txt_status.configure(text="🫧 Midiendo pulso máximo (30s en CO₂ saturado)...")
        pulsos = []
        start = time.time()
        while time.time() - start < 30:
            p = medir_pulso()
            if p:
                pulsos.append(p)
        global pulso_max
        pulso_max = sum(pulsos) / len(pulsos)
        txt_status.configure(text=f"✅ Pulso máximo guardado: {pulso_max*1000:.2f} ms")
        guardar_calibracion()
    threading.Thread(target=promediar_maximo).start()

def guardar_calibracion():
    with open(CAL_FILE, "w") as f:
        f.write(f"{pulso_min}\n{pulso_max}\n")
    print("💾 Calibración guardada en archivo.")

# ----------- Ventana principal y visualización -----------
ventana = ctk.CTk()
ventana.geometry("1200x1050")
ventana.title("🌱 Dashboard Climático con Calibración Manual")

frame_sensores = ctk.CTkFrame(ventana)
frame_sensores.pack(padx=10, pady=10, fill="both", expand=True)

# Crear gauges y gráficos
def crear_grafico_y_gauge(frame, titulo, color, max_value):
    tarjeta = ctk.CTkFrame(frame, corner_radius=15)
    tarjeta.pack(side="left", padx=10, pady=10, expand=True)

    canvas_gauge = ctk.CTkCanvas(tarjeta, width=200, height=200, bg="#2B2B2B", highlightthickness=0)
    canvas_gauge.pack(pady=10)

    fig = Figure(figsize=(3, 2), dpi=100)
    ax = fig.add_subplot(111)
    ax.set_title(titulo, fontsize=10)
    ax.tick_params(axis='both', which='major', labelsize=8)
    ax.grid(True)
    linea, = ax.plot([], [], color=color)
    canvas = FigureCanvasTkAgg(fig, master=tarjeta)
    canvas.get_tk_widget().pack()

    return canvas_gauge, ax, linea, canvas, max_value, color

canvas_temp_gauge, ax_temp, linea_temp, canvas_temp, max_temp, color_temp = crear_grafico_y_gauge(
    frame_sensores, "🌡️ Temperatura (°C)", "#E74C3C", 50
)
canvas_hum_gauge, ax_hum, linea_hum, canvas_hum, max_hum, color_hum = crear_grafico_y_gauge(
    frame_sensores, "💧 Humedad (%)", "#3498DB", 100
)
canvas_co2_gauge, ax_co2, linea_co2, canvas_co2, max_co2, color_co2 = crear_grafico_y_gauge(
    frame_sensores, "🍃 CO₂ (ppm)", "#2ECC71", 5000
)

def crear_gauge(canvas, x, y, radius, start_angle, extent, value, max_value, color):
    canvas.delete("gauge")
    canvas.create_arc(
        x-radius, y-radius, x+radius, y+radius,
        start=start_angle, extent=extent,
        style="arc", outline="#555", width=15, tags="gauge"
    )
    angle = extent * (value / max_value)
    canvas.create_arc(
        x-radius, y-radius, x+radius, y+radius,
        start=start_angle, extent=angle,
        style="arc", outline=color, width=15, tags="gauge"
    )
    canvas.create_text(
        x, y, text=f"{value}", fill="white",
        font=("Roboto", 20, "bold"), tags="gauge"
    )

# ----------- Botones -----------
btn_auto = ctk.CTkButton(
    ventana, text="⚙️ Modo Automático: OFF",
    fg_color="#C0392B", font=("Roboto", 16, "bold"),
    corner_radius=10, command=toggle_modo_automatico
)
btn_auto.pack(pady=10)

frame_reles = ctk.CTkFrame(ventana, corner_radius=15)
frame_reles.pack(padx=10, pady=10, fill="x")

botones_reles = []
for i in range(4):
    btn = ctk.CTkButton(
        frame_reles, text=f"{componentes[i]} 🔴 OFF",
        fg_color="#C0392B", font=("Roboto", 14, "bold"),
        corner_radius=10, command=lambda idx=i: toggle_rele(idx)
    )
    btn.grid(row=0, column=i, padx=10, pady=10, sticky="ew")
    botones_reles.append(btn)

# Botones de calibración separados
frame_calibracion = ctk.CTkFrame(ventana, corner_radius=15)
frame_calibracion.pack(padx=10, pady=10)

btn_cal_min = ctk.CTkButton(
    frame_calibracion, text="🌿 Comenzar calibración mínima",
    fg_color="#27AE60", font=("Roboto", 14, "bold"),
    corner_radius=10, command=calibrar_minimo
)
btn_cal_min.pack(side="left", padx=10, pady=5)

btn_cal_max = ctk.CTkButton(
    frame_calibracion, text="🫧 Comenzar calibración máxima",
    fg_color="#C0392B", font=("Roboto", 14, "bold"),
    corner_radius=10, command=calibrar_maximo
)
btn_cal_max.pack(side="left", padx=10, pady=5)

# Texto de estado
txt_status = ctk.CTkLabel(ventana, text="Dashboard iniciado", font=("Roboto", 14))
txt_status.pack(pady=5)

# ----------- Actualización sensores y gráficos -----------
def actualizar():
    temp, hum = Adafruit_DHT.read_retry(SENSOR_DHT, PIN_DHT)
    if temp is None: temp = 0
    if hum is None: hum = 0
    temp, hum = round(temp, 1), round(hum, 1)

    co2 = leer_pwm()

    datos_temp.append(temp)
    datos_hum.append(hum)
    datos_co2.append(co2)

    crear_gauge(canvas_temp_gauge, 100, 100, 70, -90, 180, temp, max_temp, color_temp)
    crear_gauge(canvas_hum_gauge, 100, 100, 70, -90, 180, hum, max_hum, color_hum)
    crear_gauge(canvas_co2_gauge, 100, 100, 70, -90, 180, co2, max_co2, color_co2)

    for ax, linea, datos, canvas in [
        (ax_temp, linea_temp, datos_temp, canvas_temp),
        (ax_hum, linea_hum, datos_hum, canvas_hum),
        (ax_co2, linea_co2, datos_co2, canvas_co2),
    ]:
        linea.set_data(range(len(datos)), list(datos))
        ax.set_xlim(0, max_datos)
        ax.set_ylim(min(datos)-5, max(datos)+5)
        canvas.draw()

    ventana.after(3000, actualizar)

# ----------- Cerrar la app limpiando GPIO -----------
def cerrar_app():
    GPIO.cleanup()
    ventana.destroy()

ventana.protocol("WM_DELETE_WINDOW", cerrar_app)

# ----------- Iniciar actualización -----------
actualizar()
ventana.mainloop()
