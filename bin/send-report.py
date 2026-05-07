#!/usr/bin/env python3
"""send-report.py - Reporte de estado del greenhouse via Telegram.

Genera un resumen ad-hoc o scheduled del estado del sistema y lo manda
al chat configurado en TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID del .env.

Usage:
    python3 bin/send-report.py            # reporte completo
    python3 bin/send-report.py --short    # solo header + sensores actuales
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "greenhouse.db"
ENV_PATH = PROJECT_ROOT / ".env"
HEALTH_URL = os.environ.get("HEALTH_URL", "http://127.0.0.1:5000/health")


def load_env() -> dict[str, str]:
    """Carga .env como dict (sin shell, sin dotenv)."""
    env: dict[str, str] = {}
    if not ENV_PATH.exists():
        return env
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def fetch_health() -> dict:
    try:
        r = requests.get(HEALTH_URL, timeout=8)
        return r.json() if r.ok else {"status": f"http_{r.status_code}", "issues": []}
    except Exception as e:
        return {"status": "unreachable", "issues": [str(e)]}


def latest_reading() -> dict | None:
    if not DB_PATH.exists():
        return None
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT timestamp, temperature, humidity, co2, vpd "
            "FROM sensor_readings ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def active_cycle() -> dict | None:
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT name, start_date, current_stage, stage_started_at "
            "FROM crop_cycles WHERE active=1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def recent_actuator_events(hours: int = 24) -> list[dict]:
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT timestamp, actuator, action, triggered_by FROM actuator_events "
            "WHERE timestamp >= datetime('now', 'localtime', ?) "
            "ORDER BY id DESC LIMIT 8",
            (f"-{hours} hours",),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def actuator_event_count(hours: int = 24) -> int:
    con = sqlite3.connect(str(DB_PATH))
    try:
        (count,) = con.execute(
            "SELECT COUNT(*) FROM actuator_events "
            "WHERE timestamp >= datetime('now', 'localtime', ?)",
            (f"-{hours} hours",),
        ).fetchone()
        return count
    finally:
        con.close()


def disk_usage() -> str:
    try:
        out = subprocess.check_output(["df", "-h", "/"], text=True).splitlines()
        return out[1].split()[4]  # Use% column
    except Exception:
        return "?"


def db_size_mb() -> float:
    return DB_PATH.stat().st_size / (1024 * 1024) if DB_PATH.exists() else 0


def fmt_status_emoji(status: str) -> str:
    return {"ok": "🟢", "degraded": "🟡", "error": "🔴", "unreachable": "⚫"}.get(status, "❓")


def format_age(seconds: float | None) -> str:
    if seconds is None:
        return "?"
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    return f"{int(seconds // 3600)}h"


def build_report(short: bool = False) -> str:
    health = fetch_health()
    reading = latest_reading()
    cycle = active_cycle()
    events = recent_actuator_events()
    event_count = actuator_event_count()

    status = health.get("status", "?")
    emoji = fmt_status_emoji(status)
    uptime = health.get("components", {}).get("uptime_seconds")
    last_age = health.get("last_reading_age_seconds")

    lines = [
        f"{emoji} *ia grow — Reporte*",
        f"_{datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        f"*Estado:* `{status}`"
        + (f" · uptime {format_age(uptime)}" if uptime else ""),
    ]
    if last_age is not None:
        lines.append(f"*Lectura mas reciente:* hace {format_age(last_age)}")

    if reading:
        lines.append("")
        lines.append("*📊 Sensores*")
        t = reading.get("temperature")
        h = reading.get("humidity")
        c = reading.get("co2")
        v = reading.get("vpd")
        lines.append(
            f"• T: {t}°C · H: {h}% · CO₂: {c} ppm · VPD: {v} kPa"
        )

    if cycle:
        try:
            day = (datetime.now().date() - datetime.fromisoformat(cycle["start_date"]).date()).days + 1
        except Exception:
            day = "?"
        lines.append("")
        lines.append("*🌱 Ciclo activo*")
        lines.append(f"• Etapa: `{cycle['current_stage']}` · Dia {day}")

    if not short:
        lines.append("")
        lines.append(f"*🔌 Actuadores ultimas 24h:* {event_count} eventos")
        if events:
            for ev in events[:5]:
                ts = ev["timestamp"][11:16] if ev["timestamp"] else "?"  # HH:MM
                trig = ev.get("triggered_by") or "manual"
                lines.append(f"  · `{ts}` {ev['actuator']} → {ev['action']} _({trig})_")

        lines.append("")
        lines.append(f"*💾 Sistema:* disco {disk_usage()} usado · DB {db_size_mb():.1f} MB")

    issues = health.get("issues", [])
    if issues:
        lines.append("")
        lines.append("*⚠ Issues*")
        for i in issues[:3]:
            lines.append(f"• {i}")

    return "\n".join(lines)


def send(text: str, env: dict[str, str]) -> bool:
    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = env.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        print("ERROR: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no definidos en .env")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(
            url,
            data={
                "chat_id": chat,
                "parse_mode": "Markdown",
                "disable_web_page_preview": "true",
                "text": text,
            },
            timeout=15,
        )
        if r.ok:
            return True
        print(f"FAIL {r.status_code}: {r.text[:300]}")
    except Exception as e:
        print(f"FAIL exception: {e}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Reporte de estado via Telegram")
    parser.add_argument("--short", action="store_true", help="reporte resumido (sin actuadores ni sistema)")
    parser.add_argument("--print", action="store_true", help="imprime sin enviar (debug)")
    args = parser.parse_args()

    env = load_env()
    text = build_report(short=args.short)

    if args.print:
        print(text)
        return 0

    ok = send(text, env)
    print("OK enviado" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
