SCHEMA = """
CREATE TABLE IF NOT EXISTS sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
    temperature REAL,
    humidity REAL,
    co2 REAL,
    vpd REAL
);

CREATE TABLE IF NOT EXISTS actuator_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
    actuator TEXT NOT NULL,
    action TEXT NOT NULL,
    triggered_by TEXT DEFAULT 'manual'
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_sensor_timestamp ON sensor_readings(timestamp);
CREATE INDEX IF NOT EXISTS idx_actuator_timestamp ON actuator_events(timestamp);
"""

# Configuracion por defecto al inicializar
DEFAULT_CONFIG = {
    "mode": "manual",
    "stage": "vegetativo_temprano",
    "light_on_hour": "6",
    "light_off_hour": "0",
    "reading_interval": "5",
    "alert_enabled": "false",
    "telegram_token": "",
    "telegram_chat_id": "",
}

# Umbrales por etapa de cultivo
STAGE_THRESHOLDS = {
    "plantula": {
        "temp_min": 20.0, "temp_max": 25.0,
        "hum_min": 70.0, "hum_max": 80.0,
        "co2_min": 400, "co2_max": 600,
    },
    "vegetativo_temprano": {
        "temp_min": 22.0, "temp_max": 28.0,
        "hum_min": 60.0, "hum_max": 70.0,
        "co2_min": 600, "co2_max": 800,
    },
    "vegetativo_tardio": {
        "temp_min": 22.0, "temp_max": 28.0,
        "hum_min": 50.0, "hum_max": 60.0,
        "co2_min": 800, "co2_max": 1000,
    },
    "floracion": {
        "temp_min": 20.0, "temp_max": 26.0,
        "hum_min": 35.0, "hum_max": 45.0,
        "co2_min": 800, "co2_max": 1200,
    },
    "floracion_tardia": {
        "temp_min": 18.0, "temp_max": 24.0,
        "hum_min": 30.0, "hum_max": 40.0,
        "co2_min": 400, "co2_max": 600,
    },
}
