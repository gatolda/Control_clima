import sqlite3
import os
import math
from werkzeug.security import generate_password_hash, check_password_hash
from data.models import SCHEMA, DEFAULT_CONFIG, STAGE_THRESHOLDS, VALID_ROLES, CROP_EVENT_TYPES, STAGE_ORDER

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
        # Pre-migracion: si actuator_events ya existe sin user_id, agregar la columna
        # ANTES de executescript (que tiene el CREATE INDEX sobre user_id y crashea
        # si la columna no existe en DBs viejas).
        try:
            cols = [r["name"] for r in conn.execute(
                "PRAGMA table_info(actuator_events)"
            ).fetchall()]
            if cols and "user_id" not in cols:
                conn.execute("ALTER TABLE actuator_events ADD COLUMN user_id INTEGER")
                conn.commit()
        except sqlite3.OperationalError:
            pass  # la tabla aun no existe; SCHEMA la creara con la columna
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

    # --- Crop cycles ---

    def create_cycle(self, start_date, current_stage="germinacion", name=None, notes=None):
        """Crea un ciclo nuevo y lo deja como el activo. Si habia uno activo, NO lo cierra
        (eso es responsabilidad del caller; tipicamente end_active_cycle antes)."""
        if current_stage not in STAGE_THRESHOLDS:
            raise ValueError(f"Etapa invalida: {current_stage}")
        conn = self._get_conn()
        cur = conn.execute(
            """INSERT INTO crop_cycles (name, start_date, current_stage, stage_started_at, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (name, start_date, current_stage, start_date, notes)
        )
        conn.commit()
        cid = cur.lastrowid
        conn.close()
        return cid

    def end_active_cycle(self, end_date=None):
        """Marca el ciclo activo como inactivo. Devuelve el id del ciclo cerrado o None."""
        active = self.get_active_cycle()
        if not active:
            return None
        from datetime import date as _date
        ed = end_date or _date.today().isoformat()
        conn = self._get_conn()
        conn.execute(
            "UPDATE crop_cycles SET active = 0, end_date = ? WHERE id = ?",
            (ed, active["id"])
        )
        conn.commit()
        conn.close()
        return active["id"]

    def get_active_cycle(self):
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM crop_cycles WHERE active = 1 ORDER BY start_date DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_cycle(self, cycle_id):
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM crop_cycles WHERE id = ?", (cycle_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def update_cycle_stage(self, cycle_id, new_stage, started_at=None):
        """Cambia la etapa del ciclo y actualiza stage_started_at a hoy (o lo provisto)."""
        if new_stage not in STAGE_THRESHOLDS:
            raise ValueError(f"Etapa invalida: {new_stage}")
        from datetime import date as _date
        sd = started_at or _date.today().isoformat()
        conn = self._get_conn()
        conn.execute(
            "UPDATE crop_cycles SET current_stage = ?, stage_started_at = ? WHERE id = ?",
            (new_stage, sd, cycle_id)
        )
        conn.commit()
        conn.close()

    # --- Crop events ---

    def create_crop_event(self, cycle_id, date, event_type, notes=None, created_by=None):
        if event_type not in CROP_EVENT_TYPES:
            raise ValueError(f"Tipo de evento invalido: {event_type}")
        # Si el evento es del pasado, lo marcamos auto-completed
        from datetime import date as _date
        is_past = date <= _date.today().isoformat()
        completed = 1 if is_past else 0
        completed_at = "datetime('now', 'localtime')" if is_past else None
        conn = self._get_conn()
        if completed:
            cur = conn.execute(
                """INSERT INTO crop_events (cycle_id, date, event_type, notes, completed, completed_at, created_by)
                   VALUES (?, ?, ?, ?, 1, datetime('now', 'localtime'), ?)""",
                (cycle_id, date, event_type, notes, created_by)
            )
        else:
            cur = conn.execute(
                """INSERT INTO crop_events (cycle_id, date, event_type, notes, created_by)
                   VALUES (?, ?, ?, ?, ?)""",
                (cycle_id, date, event_type, notes, created_by)
            )
        conn.commit()
        eid = cur.lastrowid
        conn.close()
        return eid

    def list_crop_events(self, cycle_id, days_past=30, days_future=30):
        """Eventos del ciclo en una ventana de tiempo (pasado y futuro)."""
        from datetime import date as _date, timedelta as _td
        today = _date.today()
        start = (today - _td(days=days_past)).isoformat()
        end = (today + _td(days=days_future)).isoformat()
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT e.*, u.username
               FROM crop_events e
               LEFT JOIN users u ON u.id = e.created_by
               WHERE e.cycle_id = ? AND e.date >= ? AND e.date <= ?
               ORDER BY e.date ASC, e.id ASC""",
            (cycle_id, start, end)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_crop_event(self, event_id):
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM crop_events WHERE id = ?", (event_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def mark_event_completed(self, event_id, completed=True):
        conn = self._get_conn()
        if completed:
            conn.execute(
                "UPDATE crop_events SET completed = 1, completed_at = datetime('now', 'localtime') WHERE id = ?",
                (event_id,)
            )
        else:
            conn.execute(
                "UPDATE crop_events SET completed = 0, completed_at = NULL WHERE id = ?",
                (event_id,)
            )
        conn.commit()
        conn.close()

    def delete_crop_event(self, event_id):
        conn = self._get_conn()
        conn.execute("DELETE FROM crop_events WHERE id = ?", (event_id,))
        conn.commit()
        conn.close()

    def mark_event_telegram_sent(self, event_id):
        conn = self._get_conn()
        conn.execute(
            "UPDATE crop_events SET telegram_sent_at = datetime('now', 'localtime') WHERE id = ?",
            (event_id,)
        )
        conn.commit()
        conn.close()

    # --- Feed events (bitacora de riego/abono estructurada) ---

    def create_feed_event(self, cycle_id, date, liters=None, ec_in=None, ph_in=None,
                          ec_runoff=None, ph_runoff=None, products=None, notes=None,
                          crop_event_id=None, created_by=None):
        """Registra un riego/abono. products es lista de dicts [{nombre, ml}], se serializa a JSON."""
        import json
        products_json = json.dumps(products) if products else None
        conn = self._get_conn()
        cur = conn.execute(
            """INSERT INTO feed_events
               (cycle_id, crop_event_id, date, liters, ec_in, ph_in, ec_runoff, ph_runoff,
                products, notes, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cycle_id, crop_event_id, date, liters, ec_in, ph_in, ec_runoff, ph_runoff,
             products_json, notes, created_by)
        )
        conn.commit()
        eid = cur.lastrowid
        conn.close()
        return eid

    def list_feed_events(self, cycle_id, days_past=30, days_future=0):
        from datetime import date as _date, timedelta as _td
        today = _date.today()
        start = (today - _td(days=days_past)).isoformat()
        end = (today + _td(days=days_future)).isoformat()
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT f.*, u.username FROM feed_events f
               LEFT JOIN users u ON u.id = f.created_by
               WHERE f.cycle_id = ? AND f.date >= ? AND f.date <= ?
               ORDER BY f.date DESC, f.id DESC""",
            (cycle_id, start, end)
        ).fetchall()
        conn.close()
        out = []
        import json
        for r in rows:
            d = dict(r)
            if d.get("products"):
                try: d["products"] = json.loads(d["products"])
                except Exception: pass
            out.append(d)
        return out

    def delete_feed_event(self, feed_id):
        conn = self._get_conn()
        conn.execute("DELETE FROM feed_events WHERE id = ?", (feed_id,))
        conn.commit()
        conn.close()

    def get_due_reminders(self):
        """
        Eventos que necesitan recordatorio Telegram:
        - No completados
        - Fecha = hoy o manana
        - Aun no notificados (telegram_sent_at IS NULL)
        Devuelve lista de eventos ordenados por fecha.
        """
        from datetime import date as _date, timedelta as _td
        today = _date.today().isoformat()
        tomorrow = (_date.today() + _td(days=1)).isoformat()
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM crop_events
               WHERE completed = 0
                 AND telegram_sent_at IS NULL
                 AND date IN (?, ?)
               ORDER BY date ASC""",
            (today, tomorrow)
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
