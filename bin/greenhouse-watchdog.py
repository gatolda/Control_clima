#!/usr/bin/env python3
"""
Watchdog: chequea /health cada N segundos. Alerta a Telegram si algo se rompe.

Diseño:
- Solo envia alertas en TRANSICIONES (no spam): ok->bad o bad->ok.
- Requiere 2 fallas consecutivas antes de alertar (filtra blips).
- Una vez en estado "bad", recuerda hasta volver a ok y alerta el "recovered".

Config via env vars (en .env del proyecto):
- TELEGRAM_BOT_TOKEN  (obligatorio)
- TELEGRAM_CHAT_ID    (obligatorio)
- HEALTH_URL          (default: http://127.0.0.1:5000/health)
- CHECK_INTERVAL_S    (default: 60)
- FAIL_THRESHOLD      (default: 2)
"""
from __future__ import annotations

import os
import sys
import time
import socket
import requests
from pathlib import Path

# Cargar .env si existe
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
HEALTH_URL = os.environ.get("HEALTH_URL", "http://127.0.0.1:5000/health")
INTERVAL   = int(os.environ.get("CHECK_INTERVAL_S", "60"))
THRESHOLD  = int(os.environ.get("FAIL_THRESHOLD", "2"))
HOST       = socket.gethostname()


def send_telegram(text: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print(f"[watchdog] WARN: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no definidos. Mensaje no enviado:\n{text}", flush=True)
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
        if r.ok:
            return True
        print(f"[watchdog] Telegram fallo: {r.status_code} {r.text[:200]}", flush=True)
    except Exception as e:
        print(f"[watchdog] Telegram excepcion: {e}", flush=True)
    return False


def check_once() -> tuple[str, str]:
    """Devuelve (status, summary). status en {ok, degraded, error, unreachable}."""
    try:
        r = requests.get(HEALTH_URL, timeout=10)
        if r.status_code == 503:
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            return "error", f"HTTP 503 — {data.get('issues', [])}"
        if not r.ok:
            return "error", f"HTTP {r.status_code}"
        data = r.json()
        status = data.get("status", "unknown")
        issues = data.get("issues", [])
        if status == "ok":
            return "ok", "todo OK"
        return status, f"{status} — {issues}"
    except requests.ConnectionError:
        return "unreachable", "no responde"
    except requests.Timeout:
        return "unreachable", "timeout"
    except Exception as e:
        return "unreachable", f"excepcion: {e}"


def main() -> None:
    print(f"[watchdog] iniciado | host={HOST} url={HEALTH_URL} interval={INTERVAL}s threshold={THRESHOLD}", flush=True)
    if not BOT_TOKEN or not CHAT_ID:
        print("[watchdog] WARN: corriendo en modo dry-run (sin Telegram). Defini TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en .env.", flush=True)

    consecutive_fails = 0
    in_alert_state = False  # ya enviamos alerta y esperamos recovery

    while True:
        status, summary = check_once()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[watchdog] {now} status={status} | {summary}", flush=True)

        if status == "ok":
            consecutive_fails = 0
            if in_alert_state:
                send_telegram(f"✅ *{HOST}* — Sistema recuperado.\n\nGreenhouse responde OK de nuevo.")
                in_alert_state = False
        else:
            consecutive_fails += 1
            if consecutive_fails >= THRESHOLD and not in_alert_state:
                msg = (
                    f"🚨 *{HOST}* — Greenhouse en problemas\n\n"
                    f"*Estado:* `{status}`\n"
                    f"*Detalle:* {summary}\n"
                    f"*URL:* {HEALTH_URL}\n"
                    f"*Hora:* {now}"
                )
                if send_telegram(msg):
                    in_alert_state = True

        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[watchdog] detenido", flush=True)
        sys.exit(0)
