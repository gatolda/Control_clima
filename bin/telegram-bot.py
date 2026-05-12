#!/usr/bin/env python3
"""
telegram-bot.py - Bot interactivo de Telegram para ia grow.

Hace long-polling al Bot API y responde a comandos del admin (TELEGRAM_CHAT_ID).
Mensajes de otros chats se ignoran silenciosamente.

Comandos:
    /start, /help   → muestra comandos disponibles
    /status         → reporte completo del greenhouse (reutiliza send-report.py)
    /report         → alias de /status
    /uptime         → uptime corto del sistema
    /ping           → respuesta rápida "pong" para verificar que el bot vive

Cualquier texto que contenga "reporte", "estado", "status" → /status.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

# Importar build_report() del send-report.py (con guión en el nombre → importlib)
_SEND_REPORT_PATH = PROJECT_ROOT / "bin" / "send-report.py"
_spec = importlib.util.spec_from_file_location("send_report_mod", _SEND_REPORT_PATH)
_send_report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_send_report)
build_report = _send_report.build_report
fmt_uptime = _send_report.fmt_uptime
get_health = _send_report.get_health


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def send_message(token: str, chat_id: int | str, text: str, parse_mode: str = "Markdown") -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(
            url,
            data={
                "chat_id": chat_id,
                "parse_mode": parse_mode,
                "disable_web_page_preview": "true",
                "text": text,
            },
            timeout=15,
        )
        if r.ok:
            return True
        print(f"[{datetime.now():%H:%M:%S}] sendMessage fail {r.status_code}: {r.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"[{datetime.now():%H:%M:%S}] sendMessage exception: {e}", file=sys.stderr)
    return False


HELP_TEXT = """🌱 *ia grow — bot interactivo*

Comandos disponibles:

• `/status` o `/report` → reporte completo (sensores, clima, servicios, recursos)
• `/uptime` → uptime corto del sistema
• `/ping` → verificar que el bot está vivo
• `/help` → este mensaje

También respondo a texto libre como _"dame un reporte"_, _"como esta"_, _"estado"_."""


def handle_ping(token: str, chat_id: int) -> None:
    send_message(token, chat_id, f"🏓 pong · {datetime.now():%H:%M:%S}")


def handle_uptime(token: str, chat_id: int) -> None:
    health = get_health()
    uptime = fmt_uptime(health.get("components", {}).get("uptime_seconds"))
    status = health.get("status", "?")
    icon = "🟢" if status == "ok" else "🟡" if status == "degraded" else "🔴"
    send_message(token, chat_id, f"{icon} Status: `{status}` · Uptime app: `{uptime}`")


def handle_status(token: str, chat_id: int) -> None:
    try:
        msg = build_report()
        send_message(token, chat_id, msg)
    except Exception as e:
        send_message(token, chat_id, f"❌ Error generando reporte: `{e}`")


def handle_help(token: str, chat_id: int) -> None:
    send_message(token, chat_id, HELP_TEXT)


def parse_command(text: str) -> str | None:
    """Devuelve el comando inferido del texto, o None si no se reconoce."""
    t = text.lower().strip()
    if t.startswith("/start") or t.startswith("/help") or t in ("help", "ayuda", "?"):
        return "help"
    if t.startswith("/ping") or t == "ping":
        return "ping"
    if t.startswith("/uptime") or t == "uptime":
        return "uptime"
    if t.startswith("/status") or t.startswith("/report"):
        return "status"
    # Texto libre: matchear palabras clave
    keywords = ("reporte", "report", "estado", "status", "como esta", "cómo está", "informe")
    if any(k in t for k in keywords):
        return "status"
    return None


def dispatch(token: str, chat_id: int, command: str) -> None:
    handlers = {
        "help": handle_help,
        "ping": handle_ping,
        "uptime": handle_uptime,
        "status": handle_status,
    }
    fn = handlers.get(command)
    if fn:
        print(f"[{datetime.now():%H:%M:%S}] handle: {command}")
        fn(token, chat_id)


def poll_loop(token: str, admin_chat_id: int) -> None:
    """Long-polling: pregunta cada 30s al servidor de Telegram."""
    base = f"https://api.telegram.org/bot{token}"
    offset = 0
    print(f"[{datetime.now():%H:%M:%S}] bot iniciado, admin_chat_id={admin_chat_id}")

    while True:
        try:
            r = requests.get(
                f"{base}/getUpdates",
                params={"offset": offset, "timeout": 30, "allowed_updates": '["message"]'},
                timeout=45,
            )
            if not r.ok:
                print(f"[{datetime.now():%H:%M:%S}] getUpdates fail {r.status_code}", file=sys.stderr)
                time.sleep(10)
                continue
            data = r.json()
            if not data.get("ok"):
                print(f"[{datetime.now():%H:%M:%S}] getUpdates not ok: {data}", file=sys.stderr)
                time.sleep(10)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if not msg:
                    continue
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text") or ""
                # Security: solo responder al admin
                if chat_id != admin_chat_id:
                    print(f"[{datetime.now():%H:%M:%S}] ignored msg from chat_id={chat_id}: {text[:50]}")
                    continue
                command = parse_command(text)
                if command:
                    dispatch(token, chat_id, command)
                else:
                    send_message(token, chat_id, "🤔 No entendí. Escribí `/help` para ver los comandos.")

        except requests.exceptions.Timeout:
            # Normal: long-polling timeout sin updates nuevos
            continue
        except Exception as e:
            print(f"[{datetime.now():%H:%M:%S}] poll loop exception: {e}", file=sys.stderr)
            time.sleep(10)


def main() -> int:
    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id_str = env.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id_str:
        print("ERROR: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no definidos en .env", file=sys.stderr)
        return 1
    try:
        admin_chat_id = int(chat_id_str)
    except ValueError:
        print(f"ERROR: TELEGRAM_CHAT_ID debe ser numerico, no '{chat_id_str}'", file=sys.stderr)
        return 1

    poll_loop(token, admin_chat_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
