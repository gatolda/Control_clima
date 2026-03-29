import sqlite3
import os
import math
from data.models import SCHEMA, DEFAULT_CONFIG, STAGE_THRESHOLDS

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "greenhouse.db")


class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript(SCHEMA)
        # Insertar config por defecto si no existe
        for key, value in DEFAULT_CONFIG.items():
            conn.execute(
                "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
                (key, value)
            )
        conn.commit()
        conn.close()
        print("Base de datos inicializada")

    # --- Lecturas de sensores ---

    def save_reading(self, temperature, humidity, co2):
        """Guarda una lectura de sensores, calcula VPD automaticamente."""
        vpd = self._calculate_vpd(temperature, humidity)
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO sensor_readings (temperature, humidity, co2, vpd) VALUES (?, ?, ?, ?)",
            (temperature, humidity, co2, vpd)
        )
        conn.commit()
        conn.close()

    def get_readings(self, hours=24, limit=1440):
        """Obtiene lecturas de las ultimas N horas."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT timestamp, temperature, humidity, co2, vpd
               FROM sensor_readings
               WHERE timestamp >= datetime('now', 'localtime', ?)
               ORDER BY timestamp ASC
               LIMIT ?""",
            (f"-{hours} hours", limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_latest_reading(self):
        """Obtiene la lectura mas reciente."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM sensor_readings ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    # --- Eventos de actuadores ---

    def log_actuator_event(self, actuator, action, triggered_by="manual"):
        """Registra un evento de actuador."""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO actuator_events (actuator, action, triggered_by) VALUES (?, ?, ?)",
            (actuator, action, triggered_by)
        )
        conn.commit()
        conn.close()

    def get_actuator_events(self, hours=24, limit=200):
        """Obtiene eventos de actuadores de las ultimas N horas."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT timestamp, actuator, action, triggered_by
               FROM actuator_events
               WHERE timestamp >= datetime('now', 'localtime', ?)
               ORDER BY timestamp DESC
               LIMIT ?""",
            (f"-{hours} hours", limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # --- Configuracion ---

    def get_config(self, key, default=None):
        """Obtiene un valor de configuracion."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT value FROM config WHERE key = ?", (key,)
        ).fetchone()
        conn.close()
        return row["value"] if row else default

    def set_config(self, key, value):
        """Establece un valor de configuracion."""
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO config (key, value, updated_at)
               VALUES (?, ?, datetime('now', 'localtime'))
               ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = datetime('now', 'localtime')""",
            (key, str(value), str(value))
        )
        conn.commit()
        conn.close()

    def get_all_config(self):
        """Obtiene toda la configuracion."""
        conn = self._get_conn()
        rows = conn.execute("SELECT key, value FROM config").fetchall()
        conn.close()
        return {r["key"]: r["value"] for r in rows}

    def get_stage_thresholds(self, stage=None):
        """Obtiene los umbrales para la etapa actual o la especificada."""
        if stage is None:
            stage = self.get_config("stage", "vegetativo_temprano")
        return STAGE_THRESHOLDS.get(stage, STAGE_THRESHOLDS["vegetativo_temprano"])

    # --- Utilidades ---

    def _calculate_vpd(self, temp, humidity):
        """Calcula VPD (Vapor Pressure Deficit) en kPa."""
        if temp is None or humidity is None:
            return None
        try:
            svp = 0.6108 * math.exp((17.27 * temp) / (temp + 237.3))
            vpd = svp * (1 - humidity / 100.0)
            return round(vpd, 2)
        except (ValueError, ZeroDivisionError):
            return None

    def cleanup_old_data(self, days=30):
        """Elimina datos mas antiguos que N dias."""
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM sensor_readings WHERE timestamp < datetime('now', 'localtime', ?)",
            (f"-{days} days",)
        )
        conn.execute(
            "DELETE FROM actuator_events WHERE timestamp < datetime('now', 'localtime', ?)",
            (f"-{days} days",)
        )
        conn.commit()
        conn.close()
