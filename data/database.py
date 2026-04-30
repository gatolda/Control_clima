import sqlite3
import os
import math
from werkzeug.security import generate_password_hash, check_password_hash
from data.models import SCHEMA, DEFAULT_CONFIG, STAGE_THRESHOLDS, VALID_ROLES

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
        # Migracion: columna user_id en actuator_events para DBs creadas antes del multi-user
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(actuator_events)").fetchall()]
        if "user_id" not in cols:
            conn.execute("ALTER TABLE actuator_events ADD COLUMN user_id INTEGER")
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

    def log_actuator_event(self, actuator, action, triggered_by="manual", user_id=None):
        """Registra un evento de actuador."""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO actuator_events (actuator, action, triggered_by, user_id) VALUES (?, ?, ?, ?)",
            (actuator, action, triggered_by, user_id)
        )
        conn.commit()
        conn.close()

    def get_actuator_events(self, hours=24, limit=200):
        """Obtiene eventos de actuadores con nombre de usuario si aplica."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT e.timestamp, e.actuator, e.action, e.triggered_by,
                      e.user_id, u.username
               FROM actuator_events e
               LEFT JOIN users u ON u.id = e.user_id
               WHERE e.timestamp >= datetime('now', 'localtime', ?)
               ORDER BY e.timestamp DESC
               LIMIT ?""",
            (f"-{hours} hours", limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # --- Usuarios ---

    def create_user(self, username, password, role="viewer"):
        """Crea un usuario. Devuelve su id, o None si el username ya existe."""
        if role not in VALID_ROLES:
            raise ValueError(f"Rol invalido: {role}")
        if not username or not password:
            raise ValueError("Username y password son requeridos")
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username.strip(), generate_password_hash(password), role)
            )
            conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    def get_user_by_username(self, username):
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? AND active = 1",
            (username,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_user_by_id(self, user_id):
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def verify_password(self, user_id, password):
        user = self.get_user_by_id(user_id)
        if not user or not user["active"]:
            return False
        return check_password_hash(user["password_hash"], password)

    def list_users(self, include_inactive=False):
        conn = self._get_conn()
        sql = "SELECT id, username, role, active, created_at, last_login FROM users"
        if not include_inactive:
            sql += " WHERE active = 1"
        sql += " ORDER BY created_at ASC"
        rows = conn.execute(sql).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def count_admins(self):
        """Cuenta admins activos. Usado para no dejar el sistema sin admins."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND active = 1"
        ).fetchone()
        conn.close()
        return row["n"] if row else 0

    def update_user_password(self, user_id, password):
        if not password:
            raise ValueError("Password requerida")
        conn = self._get_conn()
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(password), user_id)
        )
        conn.commit()
        conn.close()

    def update_user_role(self, user_id, role):
        if role not in VALID_ROLES:
            raise ValueError(f"Rol invalido: {role}")
        conn = self._get_conn()
        conn.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            (role, user_id)
        )
        conn.commit()
        conn.close()

    def set_user_active(self, user_id, active):
        conn = self._get_conn()
        conn.execute(
            "UPDATE users SET active = ? WHERE id = ?",
            (1 if active else 0, user_id)
        )
        conn.commit()
        conn.close()

    def update_last_login(self, user_id):
        conn = self._get_conn()
        conn.execute(
            "UPDATE users SET last_login = datetime('now', 'localtime') WHERE id = ?",
            (user_id,)
        )
        conn.commit()
        conn.close()

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

    # --- Lecturas de suelo ---

    def save_soil_reading(self, zone_id, sensor_id, variable, value):
        """Guarda una lectura de sensor de suelo."""
        if value is None:
            return
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO soil_readings (zone_id, sensor_id, variable, value) VALUES (?, ?, ?, ?)",
            (zone_id, sensor_id, variable, value)
        )
        conn.commit()
        conn.close()

    def get_soil_readings(self, zone_id=None, hours=24):
        """Obtiene lecturas de suelo."""
        conn = self._get_conn()
        if zone_id:
            rows = conn.execute(
                """SELECT timestamp, zone_id, sensor_id, variable, value
                   FROM soil_readings
                   WHERE zone_id = ? AND timestamp >= datetime('now', 'localtime', ?)
                   ORDER BY timestamp ASC""",
                (zone_id, f"-{hours} hours")
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT timestamp, zone_id, sensor_id, variable, value
                   FROM soil_readings
                   WHERE timestamp >= datetime('now', 'localtime', ?)
                   ORDER BY timestamp ASC""",
                (f"-{hours} hours",)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_latest_soil_reading(self, zone_id, variable="humedad_suelo"):
        """Obtiene la lectura de suelo mas reciente para una zona."""
        conn = self._get_conn()
        row = conn.execute(
            """SELECT value FROM soil_readings
               WHERE zone_id = ? AND variable = ?
               ORDER BY id DESC LIMIT 1""",
            (zone_id, variable)
        ).fetchone()
        conn.close()
        return row["value"] if row else None

    # --- Eventos de riego ---

    def log_irrigation_event(self, zone_id, action, duration_seconds=None,
                             soil_humidity=None, soil_ph=None, reason=None,
                             triggered_by="scheduler"):
        """Registra un evento de riego."""
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO irrigation_events
               (zone_id, action, duration_seconds, soil_humidity, soil_ph, reason, triggered_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (zone_id, action, duration_seconds, soil_humidity, soil_ph, reason, triggered_by)
        )
        conn.commit()
        conn.close()

    def get_irrigation_events(self, zone_id=None, hours=24):
        """Obtiene eventos de riego."""
        conn = self._get_conn()
        if zone_id:
            rows = conn.execute(
                """SELECT * FROM irrigation_events
                   WHERE zone_id = ? AND timestamp >= datetime('now', 'localtime', ?)
                   ORDER BY timestamp DESC""",
                (zone_id, f"-{hours} hours")
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM irrigation_events
                   WHERE timestamp >= datetime('now', 'localtime', ?)
                   ORDER BY timestamp DESC""",
                (f"-{hours} hours",)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # --- Eventos de camara ---

    def save_camera_event(self, filename, analysis=None):
        """Guarda un evento de captura de camara."""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO camera_events (filename, analysis) VALUES (?, ?)",
            (filename, analysis)
        )
        conn.commit()
        conn.close()

    def get_camera_events(self, limit=20):
        """Obtiene eventos de camara recientes."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM camera_events ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # --- Limpieza ---

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
        conn.execute(
            "DELETE FROM soil_readings WHERE timestamp < datetime('now', 'localtime', ?)",
            (f"-{days} days",)
        )
        conn.execute(
            "DELETE FROM irrigation_events WHERE timestamp < datetime('now', 'localtime', ?)",
            (f"-{days} days",)
        )
        conn.commit()
        conn.close()
