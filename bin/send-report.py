#!/usr/bin/env python3
"""
send-report.py - Reporte de estado on-demand via Telegram.

Ejecuta:
    python3 bin/send-report.py

Lee credenciales de .env (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID).
Consulta /api/climate/status local, lee logs, y manda mensaje al chat.

Tambien util desde systemd timer (futuro: reporte diario a las 09:00).
"""
from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
DB_PATH = PROJECT_ROOT / "data" / "greenhouse.db"
HEALTH_URL = os.environ.get("HEALTH_URL", "http://127.0.0.1:5000/health")
BACKUP_LOG = Path("/var/log/greenhouse-backup.log")


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def fmt_uptime(seconds: float | None) -> str:
    if seconds is None:
        return "?"
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, _ = divmod(s, 60)
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def get_health() -> dict:
    try:
        return requests.get(HEALTH_URL, timeout=5).json()
    except Exception as e:
        return {"error": str(e)}


def _db_conn() -> sqlite3.Connection | None:
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=3)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


def get_climate() -> dict:
    """Lee modo, etapa y fotoperiodo directo de la tabla config."""
    conn = _db_conn()
    if conn is None:
        return {}
    try:
        rows = conn.execute("SELECT key, value FROM config").fetchall()
        cfg = {r["key"]: r["value"] for r in rows}
        light_on = int(cfg["light_on_hour"]) if cfg.get("light_on_hour", "").isdigit() else None
        light_off = int(cfg["light_off_hour"]) if cfg.get("light_off_hour", "").isdigit() else None
        light_hours = None
        if light_on is not None and light_off is not None:
            light_hours = (light_off - light_on) % 24 or 24
        return {
            "mode": cfg.get("mode"),
            "stage": cfg.get("stage"),
            "light_on_hour": light_on,
            "light_off_hour": light_off,
            "light_hours": light_hours,
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()


def get_sensors() -> dict:
    """Lecturas mas recientes leidas directamente de sensor_readings + soil_readings."""
    conn = _db_conn()
    if conn is None:
        return {}
    out: dict = {}
    try:
        # Lectura ambiental mas reciente
        row = conn.execute(
            "SELECT timestamp, temperature, humidity, co2, vpd "
            "FROM sensor_readings ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            out["temperatura"] = {"value": row["temperature"]} if row["temperature"] is not None else None
            out["humedad"]     = {"value": row["humidity"]}    if row["humidity"]    is not None else None
            out["co2"]         = {"value": row["co2"]}         if row["co2"]         is not None else None
            out["vpd"]         = {"value": row["vpd"]}         if row["vpd"]         is not None else None
            out["_timestamp"]  = row["timestamp"]

        # Humedad de suelo: ultima lectura por zona, descartando valores stale.
        # Sin el filtro de tiempo, el reporte mostraba humedad fantasma cuando
        # el Arduino estaba caido y los valores de DB eran de hace horas/dias
        # (incidente 2026-05-18: 67.1% mostrado tras 16h sin lecturas).
        soil_rows = conn.execute("""
            SELECT zone_id, value, MAX(timestamp) as ts
            FROM soil_readings
            WHERE variable = 'humedad_suelo'
              AND timestamp > datetime('now', 'localtime', '-10 minutes')
            GROUP BY zone_id
        """).fetchall()
        if soil_rows:
            zones = {}
            for r in soil_rows:
                zones[r["zone_id"]] = round(r["value"], 1)
            out["humedad_suelo"] = zones
    except Exception as e:
        out["_error"] = str(e)
    finally:
        conn.close()
    return out


def get_last_backup() -> str:
    if not BACKUP_LOG.exists():
        return "sin registro"
    try:
        text = BACKUP_LOG.read_text(encoding="utf-8", errors="replace")
        # Buscar la ultima linea "Backup OK"
        ok_lines = [ln for ln in text.splitlines() if "Backup OK" in ln]
        if not ok_lines:
            return "sin backups exitosos"
        # Extraer timestamp del formato [YYYY-MM-DD HH:MM:SS]
        m = re.match(r"\[([\d\-: ]+)\]", ok_lines[-1])
        return m.group(1) if m else ok_lines[-1][:30]
    except Exception:
        return "error leyendo log"


def get_disk() -> str:
    try:
        out = subprocess.check_output(["df", "-h", "/"], text=True, timeout=3)
        # filesystem size used avail use% mount
        lines = out.strip().splitlines()
        if len(lines) >= 2:
            cols = lines[1].split()
            return f"{cols[3]} libre / {cols[1]} ({cols[4]} usado)"
    except Exception:
        pass
    return "?"


def get_mem() -> str:
    try:
        out = subprocess.check_output(["free", "-h"], text=True, timeout=3)
        for line in out.splitlines():
            if line.startswith("Mem:"):
                cols = line.split()
                return f"{cols[2]} usado / {cols[1]} total"
    except Exception:
        pass
    return "?"


def tailscale_connected() -> bool:
    """Tailscale realmente conectado al tailnet (no solo daemon corriendo).

    Verifica BackendState == "Running" AND Self.Online == true. Sin el segundo
    check, un daemon que perdio contacto con el coordinador da ✅ falso
    (incidente 2026-05-18). Es exactamente el mismo check que hace el
    tailscale-watchdog.sh.
    """
    import json
    try:
        out = subprocess.check_output(["tailscale", "status", "--json"], text=True, timeout=5)
        data = json.loads(out)
        return data.get("BackendState") == "Running" and data.get("Self", {}).get("Online") is True
    except Exception:
        return False


def systemctl_active(unit: str) -> bool:
    try:
        out = subprocess.check_output(["systemctl", "is-active", unit], text=True, timeout=3).strip()
        return out == "active"
    except Exception:
        return False


def build_report() -> str:
    health = get_health()
    climate = get_climate()
    sensors = get_sensors()

    status = health.get("status", "?")
    uptime = fmt_uptime(health.get("components", {}).get("uptime_seconds"))
    last_age = health.get("last_reading_age_seconds")
    issues = health.get("issues", [])
    failsafe = climate.get("failsafe_active", False)
    failsafe_reason = climate.get("failsafe_reason", "")

    mode = (climate.get("mode") or "?").upper()
    stage = (climate.get("stage") or "?").replace("_", " ").title()
    light_on = climate.get("light_on_hour")
    light_h = climate.get("light_hours") or 0
    light_off = (light_on + light_h) % 24 if light_on is not None and light_h else None
    light_str = f"{light_on:02d}:00 → {light_off:02d}:00 ({light_h}h)" if light_on is not None and light_off is not None else "?"

    # Sensor values: lee de la DB. humedad_suelo viene como dict por zona.
    s_lines = []
    unit_map = {"temperatura": "°C", "humedad": "%", "co2": "ppm", "vpd": "kPa"}
    for k in ("temperatura", "humedad", "co2", "vpd"):
        v = sensors.get(k)
        if isinstance(v, dict) and "value" in v:
            v = v["value"]
        if v is not None:
            s_lines.append(f"  {k.replace('_', ' ').title()}: `{v}{unit_map.get(k, '')}`")
    soil = sensors.get("humedad_suelo")
    if isinstance(soil, dict) and soil:
        # zone_id puede contener "_" → meterlo dentro de backticks asi
        # Markdown legacy de Telegram no lo interpreta como italica.
        zones_str = ", ".join(f"`{z}={p}%`" for z, p in sorted(soil.items()))
        s_lines.append(f"  Humedad Suelo: {zones_str}")
    if not s_lines and last_age is not None:
        s_lines.append(f"  Última lectura: hace {int(last_age)}s")

    # Servicios. Para tailscale chequeamos conectividad real (no solo daemon
    # activo), porque un tailscaled vivo pero desconectado del coordinador
    # mostraba ✅ falso en el reporte (incidente 2026-05-18).
    svc = {
        "greenhouse": systemctl_active("greenhouse.service"),
        "watchdog": systemctl_active("greenhouse-watchdog.service"),
        "tailscale": tailscale_connected(),
    }

    icon = "🟢" if status == "ok" and not failsafe else ("🔴" if status == "error" else "🟡")
    failsafe_line = f"\n⚠️ *FAILSAFE ACTIVO:* {failsafe_reason}" if failsafe else ""
    issues_line = f"\n⚠️ Issues: {', '.join(issues)}" if issues else ""

    return f"""{icon} *ia grow — Reporte on-demand*

_{datetime.now().strftime("%Y-%m-%d %H:%M")}_

*Sistema*
• Status: `{status}` · Uptime app: `{uptime}`
• Modo: `{mode}` · Etapa: `{stage}`
• Fotoperiodo: `{light_str}`{failsafe_line}{issues_line}

*Sensores*
{chr(10).join(s_lines) if s_lines else '  (sin datos)'}

*Servicios*
• greenhouse: {'✅' if svc['greenhouse'] else '❌'}
• watchdog: {'✅' if svc['watchdog'] else '❌'}
• tailscale: {'✅' if svc['tailscale'] else '❌'}

*Backup*
• Último OK: `{get_last_backup()}`

*Recursos Pi*
• Disco: {get_disk()}
• RAM: {get_mem()}

*Acceso*
[Dashboard](https://iagrow.cl)"""


def send(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": chat_id, "parse_mode": "Markdown", "disable_web_page_preview": "true", "text": text},
            timeout=15,
        )
        if r.ok:
            return True
        print(f"Telegram fail {r.status_code}: {r.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"Telegram exception: {e}", file=sys.stderr)
    return False


def main() -> int:
    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no definidos en .env", file=sys.stderr)
        return 1

    msg = build_report()
    return 0 if send(token, chat_id, msg) else 1


if __name__ == "__main__":
    sys.exit(main())
