#!/usr/bin/env python3
"""
Calendar notifier: corre 1x al dia (via systemd timer).
Manda recordatorios a Telegram para:
1. Eventos pendientes de HOY o MANANA aun no notificados
2. Transicion de fase due (current_stage_duration cumplida)

Lee la DB directamente (no llama a la app HTTP). Si no hay ciclo activo
o si Telegram no esta configurado, sale silenciosamente.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Cargar .env del proyecto
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# Path al proyecto para importar modulos
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import requests
from data.database import Database
from data.models import STAGE_THRESHOLDS, STAGE_ORDER, CROP_EVENT_TYPES

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

EVENT_LABELS = {
    "abono": "💧 Abono",
    "poda": "✂️ Poda",
    "defoliacion": "🍃 Defoliacion",
    "transplante": "🌱 Transplante",
    "plaga": "🐛 Plaga",
    "fase_cambio": "🔄 Cambio de fase",
    "otro": "📌 Evento",
}


def send_telegram(text: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print(f"[notifier] Telegram no configurado. Mensaje no enviado:\n{text}", flush=True)
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        if r.ok:
            return True
        print(f"[notifier] Telegram fallo: {r.status_code} {r.text[:200]}", flush=True)
    except Exception as e:
        print(f"[notifier] Telegram excepcion: {e}", flush=True)
    return False


def next_stage_after(stage: str) -> str | None:
    try:
        i = STAGE_ORDER.index(stage)
        return STAGE_ORDER[i + 1] if i + 1 < len(STAGE_ORDER) else None
    except ValueError:
        return None


def main() -> None:
    db = Database()
    cycle = db.get_active_cycle()
    if not cycle:
        print("[notifier] No hay ciclo activo, saliendo.", flush=True)
        return

    today = date.today()
    tomorrow = today + timedelta(days=1)
    sent_count = 0

    # 1. Cambio de fase due
    stage = cycle["current_stage"]
    stage_started = date.fromisoformat(cycle["stage_started_at"])
    duration = STAGE_THRESHOLDS.get(stage, {}).get("duracion_dias", 0)
    days_in_stage = (today - stage_started).days

    if duration > 0 and days_in_stage >= duration:
        nxt = next_stage_after(stage)
        if nxt:
            stage_label = stage.replace("_", " ").title()
            nxt_label = nxt.replace("_", " ").title()
            days_over = days_in_stage - duration
            extra = f" (+{days_over}d de retraso)" if days_over > 0 else ""
            msg = (
                f"🔄 *Cambio de fase pendiente*\n\n"
                f"Llevas *{days_in_stage} dias* en {stage_label}{extra}.\n"
                f"Te toca avanzar a *{nxt_label}*.\n\n"
                f"Confirmá en el dashboard:\n"
                f"https://raspberrypi.taild496a5.ts.net/calendar"
            )
            if send_telegram(msg):
                sent_count += 1

    # 2. Eventos due (hoy o manana, no completados, no notificados aun)
    due = db.get_due_reminders()
    for ev in due:
        ev_date = ev["date"]
        when = "HOY" if ev_date == today.isoformat() else "MAÑANA"
        label = EVENT_LABELS.get(ev["event_type"], ev["event_type"])
        notes = ev.get("notes") or ""
        notes_block = f"\n_{notes}_" if notes else ""
        msg = (
            f"📅 *{when}* — {label}{notes_block}\n\n"
            f"Marcá como hecho cuando termines:\n"
            f"https://raspberrypi.taild496a5.ts.net/calendar"
        )
        if send_telegram(msg):
            db.mark_event_telegram_sent(ev["id"])
            sent_count += 1

    print(f"[notifier] {sent_count} mensajes enviados", flush=True)


if __name__ == "__main__":
    main()
