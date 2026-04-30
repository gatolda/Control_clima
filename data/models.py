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
    triggered_by TEXT DEFAULT 'manual',
    user_id INTEGER
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT (datetime('now', 'localtime')),
    last_login DATETIME
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS soil_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
    zone_id TEXT NOT NULL,
    sensor_id TEXT NOT NULL,
    variable TEXT NOT NULL,
    value REAL
);

CREATE TABLE IF NOT EXISTS irrigation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
    zone_id TEXT NOT NULL,
    action TEXT NOT NULL,
    duration_seconds INTEGER,
    soil_humidity REAL,
    soil_ph REAL,
    reason TEXT,
    triggered_by TEXT DEFAULT 'scheduler'
);

CREATE TABLE IF NOT EXISTS camera_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
    filename TEXT NOT NULL,
    analysis TEXT
);

CREATE TABLE IF NOT EXISTS crop_cycles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    start_date DATE NOT NULL,
    current_stage TEXT NOT NULL DEFAULT 'germinacion',
    stage_started_at DATE NOT NULL,
    end_date DATE,
    active INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    created_at DATETIME DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS crop_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id INTEGER NOT NULL,
    date DATE NOT NULL,
    event_type TEXT NOT NULL,
    notes TEXT,
    completed INTEGER NOT NULL DEFAULT 0,
    completed_at DATETIME,
    telegram_sent_at DATETIME,
    created_by INTEGER,
    created_at DATETIME DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (cycle_id) REFERENCES crop_cycles(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- Bitacora estructurada de riego/abono. Un evento aqui puede o no estar
-- vinculado a un crop_events tag (event_id NULL es un riego sin abono notable).
-- Permite trazar EC/pH y nutrientes en el tiempo.
CREATE TABLE IF NOT EXISTS feed_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id INTEGER NOT NULL,
    crop_event_id INTEGER,
    date DATE NOT NULL,
    liters REAL,
    ec_in REAL,
    ph_in REAL,
    ec_runoff REAL,
    ph_runoff REAL,
    products TEXT,             -- JSON: [{"nombre":"BloomA","ml":10},{"nombre":"BloomB","ml":10}]
    notes TEXT,
    created_by INTEGER,
    created_at DATETIME DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (cycle_id) REFERENCES crop_cycles(id),
    FOREIGN KEY (crop_event_id) REFERENCES crop_events(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- Fotos del ciclo (bitacora visual)
CREATE TABLE IF NOT EXISTS cycle_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id INTEGER NOT NULL,
    plant_id INTEGER,
    date DATE NOT NULL,
    filename TEXT NOT NULL,
    stage_at_capture TEXT,
    notes TEXT,
    created_at DATETIME DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (cycle_id) REFERENCES crop_cycles(id)
);

-- Plantas individuales del ciclo (para tracking per-planta)
CREATE TABLE IF NOT EXISTS plants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    strain TEXT,
    planted_date DATE,
    notes TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (cycle_id) REFERENCES crop_cycles(id)
);

-- Inventario de insumos (productos, nutrientes, sustratos)
CREATE TABLE IF NOT EXISTS supplies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT,           -- 'nutriente', 'sustrato', 'agua', 'pesticida', 'otro'
    unit TEXT NOT NULL,      -- 'ml', 'g', 'L', 'unidad'
    current_qty REAL NOT NULL DEFAULT 0,
    cost_per_unit REAL,      -- en $ (CLP/USD/etc.)
    expiry_date DATE,
    low_threshold REAL,      -- alertar cuando current_qty < low_threshold
    notes TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT (datetime('now', 'localtime'))
);

-- Costos del ciclo (categorias: luz, agua, nutes, sustrato, otros)
CREATE TABLE IF NOT EXISTS cycle_costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id INTEGER NOT NULL,
    date DATE NOT NULL,
    category TEXT NOT NULL,
    amount REAL NOT NULL,
    notes TEXT,
    created_at DATETIME DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (cycle_id) REFERENCES crop_cycles(id)
);

-- Tasks recurrentes (una sola entrada que genera recordatorios cada N dias o ciertos dias)
-- Cuando se cumple, el notifier lo envia (similar a crop_events) pero no lo "completa",
-- sino que avanza a la siguiente fecha programada.
CREATE TABLE IF NOT EXISTS recurring_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id INTEGER,         -- NULL = tarea global, no por ciclo
    title TEXT NOT NULL,
    description TEXT,
    every_days INTEGER,       -- ej: cada 3 dias
    weekdays TEXT,            -- alternativa: "0,3" para lun y jue (0=lun, 6=dom)
    only_in_stages TEXT,      -- JSON list: solo en estas etapas
    next_run DATE NOT NULL,
    last_sent_at DATETIME,
    active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_sensor_timestamp ON sensor_readings(timestamp);
CREATE INDEX IF NOT EXISTS idx_actuator_timestamp ON actuator_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_actuator_user ON actuator_events(user_id);
CREATE INDEX IF NOT EXISTS idx_soil_timestamp ON soil_readings(timestamp);
CREATE INDEX IF NOT EXISTS idx_soil_zone ON soil_readings(zone_id);
CREATE INDEX IF NOT EXISTS idx_irrigation_timestamp ON irrigation_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_irrigation_zone ON irrigation_events(zone_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_crop_cycles_active ON crop_cycles(active);
CREATE INDEX IF NOT EXISTS idx_crop_events_cycle_date ON crop_events(cycle_id, date);
CREATE INDEX IF NOT EXISTS idx_feed_events_cycle_date ON feed_events(cycle_id, date);
CREATE INDEX IF NOT EXISTS idx_cycle_photos_cycle_date ON cycle_photos(cycle_id, date);
CREATE INDEX IF NOT EXISTS idx_plants_cycle ON plants(cycle_id);
CREATE INDEX IF NOT EXISTS idx_cycle_costs_cycle ON cycle_costs(cycle_id);
CREATE INDEX IF NOT EXISTS idx_recurring_tasks_next ON recurring_tasks(next_run);
"""

# Roles: admin (todo), operator (controles+config de cultivo, no usuarios), viewer (solo lectura)
VALID_ROLES = ("admin", "operator", "viewer")

# Tipos de evento de cultivo validos
CROP_EVENT_TYPES = (
    "abono",
    "poda",
    "defoliacion",
    "transplante",
    "plaga",
    "fase_cambio",
    "otro",
)

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
    "irrigation_mode": "auto",
    "camera_interval_minutes": "60",
}

# Etapas de cultivo cannabis indoor con condiciones optimas
# Cada etapa define: clima, luz, suelo, VPD y duracion tipica
STAGE_THRESHOLDS = {
    "germinacion": {
        # Clima
        "temp_min": 22.0, "temp_max": 26.0,
        "temp_night_min": 20.0, "temp_night_max": 24.0,
        "hum_min": 70.0, "hum_max": 80.0,
        "co2_min": 400, "co2_max": 600,
        "co2_solo_con_luz": True,
        "vpd_min": 0.4, "vpd_max": 0.8,
        # Luz
        "light_hours": 18, "dark_hours": 6,
        # Suelo
        "soil_hum_min": 65.0, "soil_hum_max": 80.0,
        "soil_ph_min": 6.0, "soil_ph_max": 6.5,
        # Riego
        "riego_frecuencia_horas": 12,
        "riego_duracion_min": 2,
        # Info
        "duracion_dias": 5,
        "descripcion": "Germinacion - semilla a brote",
    },
    "plantula": {
        "temp_min": 22.0, "temp_max": 26.0,
        "temp_night_min": 18.0, "temp_night_max": 22.0,
        "hum_min": 65.0, "hum_max": 75.0,
        "co2_min": 400, "co2_max": 600,
        "vpd_min": 0.4, "vpd_max": 0.8,
        "light_hours": 18, "dark_hours": 6,
        "soil_hum_min": 60.0, "soil_hum_max": 75.0,
        "soil_ph_min": 6.0, "soil_ph_max": 6.5,
        "riego_frecuencia_horas": 12,
        "riego_duracion_min": 3,
        "duracion_dias": 14,
        "descripcion": "Plantula - primeras hojas verdaderas",
    },
    "vegetativo_temprano": {
        "temp_min": 24.0, "temp_max": 28.0,
        "temp_night_min": 18.0, "temp_night_max": 22.0,
        "hum_min": 55.0, "hum_max": 65.0,
        "co2_min": 800, "co2_max": 1200,
        "vpd_min": 0.8, "vpd_max": 1.2,
        "light_hours": 18, "dark_hours": 6,
        "soil_hum_min": 50.0, "soil_hum_max": 70.0,
        "soil_ph_min": 6.0, "soil_ph_max": 7.0,
        "riego_frecuencia_horas": 8,
        "riego_duracion_min": 5,
        "duracion_dias": 21,
        "descripcion": "Vegetativo temprano - crecimiento activo",
    },
    "vegetativo_tardio": {
        "temp_min": 24.0, "temp_max": 28.0,
        "temp_night_min": 18.0, "temp_night_max": 22.0,
        "hum_min": 50.0, "hum_max": 60.0,
        "co2_min": 1000, "co2_max": 1400,
        "vpd_min": 1.0, "vpd_max": 1.4,
        "light_hours": 18, "dark_hours": 6,
        "soil_hum_min": 45.0, "soil_hum_max": 65.0,
        "soil_ph_min": 6.0, "soil_ph_max": 7.0,
        "riego_frecuencia_horas": 6,
        "riego_duracion_min": 5,
        "duracion_dias": 21,
        "descripcion": "Vegetativo tardio - pre-transicion a flora",
    },
    "pre_floracion": {
        "temp_min": 22.0, "temp_max": 26.0,
        "temp_night_min": 17.0, "temp_night_max": 21.0,
        "hum_min": 45.0, "hum_max": 55.0,
        "co2_min": 800, "co2_max": 1200,
        "vpd_min": 1.0, "vpd_max": 1.4,
        "light_hours": 12, "dark_hours": 12,
        "soil_hum_min": 45.0, "soil_hum_max": 65.0,
        "soil_ph_min": 6.0, "soil_ph_max": 6.8,
        "riego_frecuencia_horas": 8,
        "riego_duracion_min": 5,
        "duracion_dias": 14,
        "descripcion": "Pre-floracion - transicion, cambio fotoperiodo 12/12",
    },
    "floracion": {
        "temp_min": 20.0, "temp_max": 26.0,
        "temp_night_min": 16.0, "temp_night_max": 20.0,
        "hum_min": 35.0, "hum_max": 50.0,
        "co2_min": 800, "co2_max": 1200,
        "vpd_min": 1.0, "vpd_max": 1.5,
        "light_hours": 12, "dark_hours": 12,
        "soil_hum_min": 40.0, "soil_hum_max": 60.0,
        "soil_ph_min": 6.0, "soil_ph_max": 6.5,
        "riego_frecuencia_horas": 8,
        "riego_duracion_min": 5,
        "duracion_dias": 42,
        "descripcion": "Floracion - desarrollo de cogollos",
    },
    "floracion_tardia": {
        "temp_min": 18.0, "temp_max": 24.0,
        "temp_night_min": 15.0, "temp_night_max": 19.0,
        "hum_min": 30.0, "hum_max": 40.0,
        "co2_min": 400, "co2_max": 800,
        "vpd_min": 1.2, "vpd_max": 1.6,
        "light_hours": 12, "dark_hours": 12,
        "soil_hum_min": 35.0, "soil_hum_max": 55.0,
        "soil_ph_min": 6.0, "soil_ph_max": 6.5,
        "riego_frecuencia_horas": 10,
        "riego_duracion_min": 4,
        "duracion_dias": 14,
        "descripcion": "Floracion tardia - maduracion, flush final",
    },
    "secado": {
        "temp_min": 18.0, "temp_max": 22.0,
        "temp_night_min": 16.0, "temp_night_max": 20.0,
        "hum_min": 45.0, "hum_max": 55.0,
        "co2_min": 400, "co2_max": 600,
        "vpd_min": 0.8, "vpd_max": 1.2,
        "light_hours": 0, "dark_hours": 24,
        "soil_hum_min": 0, "soil_hum_max": 0,
        "soil_ph_min": 0, "soil_ph_max": 0,
        "riego_frecuencia_horas": 0,
        "riego_duracion_min": 0,
        "duracion_dias": 10,
        "descripcion": "Secado - oscuridad total, ventilacion suave",
    },
    "curado": {
        "temp_min": 18.0, "temp_max": 22.0,
        "temp_night_min": 16.0, "temp_night_max": 20.0,
        "hum_min": 55.0, "hum_max": 65.0,
        "co2_min": 400, "co2_max": 600,
        "vpd_min": 0.6, "vpd_max": 1.0,
        "light_hours": 0, "dark_hours": 24,
        "soil_hum_min": 0, "soil_hum_max": 0,
        "soil_ph_min": 0, "soil_ph_max": 0,
        "riego_frecuencia_horas": 0,
        "riego_duracion_min": 0,
        "duracion_dias": 30,
        "descripcion": "Curado - en frascos, humedad controlada",
    },
}

# Orden de etapas para progresion
STAGE_ORDER = [
    "germinacion", "plantula", "vegetativo_temprano", "vegetativo_tardio",
    "pre_floracion", "floracion", "floracion_tardia", "secado", "curado"
]
