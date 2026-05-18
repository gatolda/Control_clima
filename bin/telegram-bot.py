#!/usr/bin/env python3
"""
telegram-bot.py - Bot interactivo de Telegram para ia grow.

Hace long-polling al Bot API y responde a comandos del admin (TELEGRAM_CHAT_ID).
Mensajes de otros chats se ignoran silenciosamente.

Comandos READ:
    /start, /help        → muestra comandos disponibles
    /status, /report     → reporte completo del greenhouse
    /uptime              → uptime corto del sistema
    /ping                → respuesta rápida "pong"
    /photo               → toma una foto AHORA

Comandos WRITE (recovery remoto cuando SSH/Tailscale tambien cae):
    /restart_greenhouse  → systemctl restart greenhouse.service
    /restart_tailscale   → systemctl restart tailscaled
    /restart_watchdog    → systemctl restart greenhouse-watchdog.service
    /usb_reset           → USB reset al CH340 del Arduino (vía sysfs)
    /reboot              → reinicio completo de la Pi (2-tap para confirmar)

Free-text matching SOLO para comandos read (status/photo). Los write requieren
slash explicito para evitar disparos accidentales.

Cualquier comando write usa sudo via NOPASSWD (configurado para user kowen en
/etc/sudoers.d/010-kowen-nopasswd).
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))  # para `from core.x import ...` desde el bot
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

*Lectura:*
• `/status` o `/report` → reporte completo (sensores, clima, servicios, recursos)
• `/photo` → toma una foto AHORA con la cámara de la carpa
• `/uptime` → uptime corto del sistema
• `/ping` → verificar que el bot está vivo
• `/help` → este mensaje

*Recovery remoto:*
• `/restart_greenhouse` → reinicia la app Flask
• `/restart_tailscale` → reinicia tailscaled (recupera SSH remoto)
• `/restart_watchdog` → reinicia el watchdog de alertas
• `/usb_reset` → resetea el USB del Arduino (cura CH340 colgado)
• `/reboot` → reinicia toda la Pi (mandalo dos veces en 30s para confirmar)

También respondo a texto libre como _"dame un reporte"_ o _"sacame una foto"_ (solo para lectura — los comandos de recovery requieren slash explicito)."""


# Estado para confirmacion de /reboot (2-tap dentro de la ventana de 30s)
PENDING_REBOOT: dict[int, float] = {}
REBOOT_CONFIRM_WINDOW_S = 30


def run_admin_command(
    token: str,
    chat_id: int,
    label: str,
    argv: list[str],
    success_msg: str,
    timeout_s: int = 30,
) -> None:
    """Ejecuta un comando admin con feedback a Telegram.

    No ejecuta shell. argv es una lista exacta para evitar inyeccion.
    Devuelve stderr/stdout del comando si falla.
    """
    send_message(token, chat_id, f"⚙️ {label}…")
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if result.returncode == 0:
            send_message(token, chat_id, f"✅ {success_msg}")
        else:
            err = (result.stderr or result.stdout or "").strip()[:500]
            send_message(token, chat_id, f"❌ Falló (exit={result.returncode}): `{err or 'sin output'}`")
    except subprocess.TimeoutExpired:
        send_message(token, chat_id, f"⏱ Timeout ejecutando: `{label}`")
    except Exception as e:
        send_message(token, chat_id, f"❌ Excepción: `{e}`")


def handle_ping(token: str, chat_id: int) -> None:
    send_message(token, chat_id, f"🏓 pong · {datetime.now():%H:%M:%S}")


def handle_restart_greenhouse(token: str, chat_id: int) -> None:
    run_admin_command(
        token, chat_id,
        "Reiniciando greenhouse.service",
        ["sudo", "systemctl", "restart", "greenhouse.service"],
        "greenhouse.service reiniciado. /health debería responder en ~10s.",
    )


def handle_restart_tailscale(token: str, chat_id: int) -> None:
    run_admin_command(
        token, chat_id,
        "Reiniciando tailscaled",
        ["sudo", "systemctl", "restart", "tailscaled"],
        "tailscaled reiniciado. SSH remoto e iagrow.cl deberían volver en ~15s.",
    )


def handle_restart_watchdog(token: str, chat_id: int) -> None:
    run_admin_command(
        token, chat_id,
        "Reiniciando greenhouse-watchdog",
        ["sudo", "systemctl", "restart", "greenhouse-watchdog.service"],
        "watchdog reiniciado.",
    )


def handle_usb_reset(token: str, chat_id: int) -> None:
    script = str(PROJECT_ROOT / "bin" / "usb-reset-ch340.sh")
    run_admin_command(
        token, chat_id,
        "USB reset al CH340 del Arduino",
        ["sudo", script],
        "USB reset enviado. Sensores deberían volver en ~15s. Mandá `/status` para confirmar.",
    )


def handle_reboot(token: str, chat_id: int) -> None:
    """Reboot completo con confirmacion 2-tap (evita disparos accidentales)."""
    now = time.time()
    last = PENDING_REBOOT.get(chat_id, 0)
    if now - last < REBOOT_CONFIRM_WINDOW_S:
        send_message(
            token, chat_id,
            "🔄 *REINICIANDO LA PI.*\nBot offline ~2 min. Cuando vuelva voy a saludar."
        )
        # Popen async — el reboot mata el bot, pero mandamos el mensaje antes
        try:
            subprocess.Popen(["sudo", "reboot"])
        except Exception as e:
            send_message(token, chat_id, f"❌ No pude disparar reboot: `{e}`")
        PENDING_REBOOT.pop(chat_id, None)
    else:
        PENDING_REBOOT[chat_id] = now
        send_message(
            token, chat_id,
            f"⚠️ Vas a reiniciar la Pi.\nMandá `/reboot` otra vez en {REBOOT_CONFIRM_WINDOW_S}s para confirmar."
        )


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


def handle_photo(token: str, chat_id: int) -> None:
    """Toma una foto AHORA y la manda al chat."""
    send_message(token, chat_id, "📸 Tomando foto…")
    try:
        # Importar y usar camera_manager directamente (no via subprocess para
        # que sea mas rapido)
        from core.config_loader import ConfigLoader
        from data.database import Database
        from core.camera_manager import CameraManager
        cfg = ConfigLoader(str(PROJECT_ROOT / "config.yml"))
        cfg.cargar_configuracion()
        db = Database(str(PROJECT_ROOT / "data" / "greenhouse.db"))
        cam = CameraManager(cfg, db)
        result = cam.capture()
    except Exception as e:
        send_message(token, chat_id, f"❌ Error tomando foto: `{e}`")
        return

    if not result.get("ok"):
        send_message(token, chat_id, f"❌ Captura fallida: `{result.get('error')}`")
        return

    # Mandar la foto via sendPhoto
    filepath = result["path"]
    caption = (
        f"🌱 *{datetime.now():%Y-%m-%d %H:%M}*\n"
        f"_{result.get('size_bytes', 0) // 1024} KB · brightness {result.get('brightness', '?')}_"
    )
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        with open(filepath, "rb") as f:
            r = requests.post(
                url,
                data={"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"},
                files={"photo": f},
                timeout=30,
            )
        if not r.ok:
            send_message(token, chat_id, f"❌ Telegram sendPhoto fail: `{r.status_code}`")
    except Exception as e:
        send_message(token, chat_id, f"❌ Error enviando foto: `{e}`")


def parse_command(text: str) -> str | None:
    """Devuelve el comando inferido del texto, o None si no se reconoce."""
    t = text.lower().strip()
    # Read commands
    if t.startswith("/start") or t.startswith("/help") or t in ("help", "ayuda", "?"):
        return "help"
    if t.startswith("/ping") or t == "ping":
        return "ping"
    if t.startswith("/uptime") or t == "uptime":
        return "uptime"
    if t.startswith("/status") or t.startswith("/report"):
        return "status"
    if t.startswith("/photo") or t.startswith("/foto"):
        return "photo"
    # Write commands (recovery). Solo slash — no free-text para evitar
    # disparos accidentales.
    if t.startswith("/restart_greenhouse") or t.startswith("/restart_app"):
        return "restart_greenhouse"
    if t.startswith("/restart_tailscale") or t.startswith("/restart_ts"):
        return "restart_tailscale"
    if t.startswith("/restart_watchdog"):
        return "restart_watchdog"
    if t.startswith("/usb_reset") or t.startswith("/reset_arduino"):
        return "usb_reset"
    if t.startswith("/reboot"):
        return "reboot"
    # Texto libre: matchear palabras clave (read-only)
    keywords_status = ("reporte", "report", "estado", "status", "como esta", "cómo está", "informe")
    keywords_photo  = ("foto", "photo", "imagen", "picture")
    if any(k in t for k in keywords_photo):
        return "photo"
    if any(k in t for k in keywords_status):
        return "status"
    return None


def dispatch(token: str, chat_id: int, command: str) -> None:
    handlers = {
        "help": handle_help,
        "ping": handle_ping,
        "uptime": handle_uptime,
        "status": handle_status,
        "photo": handle_photo,
        "restart_greenhouse": handle_restart_greenhouse,
        "restart_tailscale": handle_restart_tailscale,
        "restart_watchdog": handle_restart_watchdog,
        "usb_reset": handle_usb_reset,
        "reboot": handle_reboot,
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
