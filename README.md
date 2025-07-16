# ✅ README.md

## 🌱 Control_clima - Sistema de Control Climático con Raspberry Pi

Este proyecto es un sistema de control climático automatizado basado en Raspberry Pi. Está diseñado para monitorear y gestionar sensores (temperatura, humedad, CO₂) y controlar actuadores (ventiladores, calefactores, bombas, etc.) para mantener las condiciones óptimas en invernaderos o entornos cerrados.

---

### 🚀 **Características principales (planeadas)**
- Monitoreo en tiempo real de sensores.
- Control manual y automático de actuadores.
- Registro histórico de datos (gráficas).
- Panel web (Flask o FastAPI) accesible desde cualquier dispositivo.
- Notificaciones por Telegram o email cuando se superen umbrales críticos.
- Actualización remota del sistema vía GitHub.

---

### 🖥️ **Requisitos de hardware**
- Raspberry Pi 3 o superior
- Sensores: DHT22 (temperatura/humedad), sensor CO₂
- Actuadores: relés, ventiladores, bombas de agua
- Conexión a Internet para actualizaciones remotas

---

### ⚙️ **Requisitos de software**
Ver `requirements.txt` para dependencias Python.

---

### 📦 **Estructura del proyecto**
```
Control_clima/
├── Actuadores/
├── Control/
├── Sensores/
├── web/ (planeado)
├── main.py
├── README.md
├── requirements.txt
└── .gitignore
```

---

### 🛠️ **Cómo ejecutar**
```bash
# Clonar el repositorio
git clone https://github.com/gatolda/Control_clima.git

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar el sistema
python3 main.py
```

---

### 📄 **Notas**
- Este proyecto está en desarrollo activo.
- Se recomienda usar un entorno virtual Python.
