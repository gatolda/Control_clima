#!/usr/bin/env python3
"""
daily-analysis.py — análisis IA diario del cultivo.

Lo invoca el systemd timer `greenhouse-daily-analysis.timer` (default: 14:00 todos los días).

Flow:
  1. Toma una foto fresh con la cámara
  2. Analiza con Claude Vision (incluye etapa del cultivo como contexto)
  3. Guarda resultado en camera_snapshots.analysis_json
  4. Si salud_general < 6 o detecta plagas/deficiencias → manda alerta Telegram

Exit codes:
  0 = OK (con o sin alerta)
  1 = falla de captura
  2 = falla de análisis IA
  3 = falla de config
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

ALERT_HEALTH_THRESHOLD = 6  # salud_general < 6 dispara alerta


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def send_telegram_alert(token: str, chat_id: str, photo_path: Path, msg: str) -> bool:
    import requests
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        with open(photo_path, "rb") as f:
            r = requests.post(
                url,
                data={"chat_id": chat_id, "caption": msg, "parse_mode": "Markdown"},
                files={"photo": f},
                timeout=30,
            )
        return r.ok
    except Exception as e:
        print(f"[telegram] error: {e}", file=sys.stderr)
        return False


def main() -> int:
    print(f"=== daily-analysis ===")
    try:
        from core.config_loader import ConfigLoader
        from data.database import Database
        from core.camera_manager import CameraManager
        from core.vision_analyzer import analyze_image
    except Exception as e:
        print(f"ERROR import: {e}", file=sys.stderr)
        return 3

    # Setup
    env = load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    try:
        cfg = ConfigLoader(str(PROJECT_ROOT / "config.yml"))
        cfg.cargar_configuracion()
        db = Database(str(PROJECT_ROOT / "data" / "greenhouse.db"))
        cam = CameraManager(cfg, db)
    except Exception as e:
        print(f"ERROR init: {e}", file=sys.stderr)
        return 3

    # 1. Capturar foto
    print("Capturando foto…")
    capture = cam.capture()
    if not capture.get("ok"):
        print(f"ERROR captura: {capture.get('error')}", file=sys.stderr)
        return 1
    snapshot_id = capture.get("snapshot_id")
    photo_path = Path(capture["path"])
    print(f"OK foto: {capture['filename']} ({capture['size_bytes']}b)")

    # 2. Contexto adicional desde config DB
    extra_context = None
    try:
        all_cfg = db.get_all_config() if hasattr(db, "get_all_config") else {}
        stage = all_cfg.get("stage") if isinstance(all_cfg, dict) else None
        if stage:
            extra_context = f"Etapa actual del cultivo: {stage}"
    except Exception:
        pass

    # 3. Análisis IA
    print("Analizando con Claude Vision…")
    try:
        analysis = analyze_image(photo_path, extra_context=extra_context)
    except Exception as e:
        print(f"ERROR análisis: {e}", file=sys.stderr)
        return 2

    salud = analysis.get("salud_general", 0)
    plagas = analysis.get("signos_plagas", {}).get("detectado", False)
    deficits = analysis.get("signos_deficiencias", {}).get("detectado", False)
    usage = analysis.get("_usage", {})
    print(f"OK análisis: salud={salud}/10  plagas={plagas}  defic={deficits}")
    print(f"   tokens in={usage.get('input_tokens', 0)} out={usage.get('output_tokens', 0)} cached={usage.get('cache_read_input_tokens', 0)}")

    # 4. Guardar en DB
    if snapshot_id:
        db.save_snapshot_analysis(snapshot_id, analysis)
        print(f"OK guardado en DB (snapshot_id={snapshot_id})")

    # 5. Alerta Telegram si corresponde
    needs_alert = (salud < ALERT_HEALTH_THRESHOLD) or plagas or deficits
    if not needs_alert:
        print("Sin alertas. Salud OK.")
        return 0

    token = env.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("WARN: TELEGRAM no configurado, no se envía alerta")
        return 0

    # Componer el mensaje
    icon = "🔴" if salud < 4 else "🟡" if salud < 6 else "⚠️"
    lines = [f"{icon} *Diagnóstico IA — alerta en el cultivo*", ""]
    lines.append(f"*Salud:* `{salud}/10`  ·  *Vigor:* `{analysis.get('vigor', '?')}`")
    lines.append(f"*Etapa estimada:* `{analysis.get('etapa_estimada', '?')}`")
    lines.append("")
    if plagas:
        desc = analysis.get("signos_plagas", {}).get("descripcion", "—")
        lines.append(f"🐛 *Plagas:* {desc}")
    if deficits:
        desc = analysis.get("signos_deficiencias", {}).get("descripcion", "—")
        lines.append(f"🍂 *Deficiencias:* {desc}")
    recs = analysis.get("recomendaciones", [])
    if recs:
        lines.append("")
        lines.append("*Recomendaciones:*")
        for r in recs[:5]:
            lines.append(f"• {r}")
    lines.append("")
    lines.append("[Ver dashboard](https://iagrow.cl/cultivo)")
    msg = "\n".join(lines)

    if send_telegram_alert(token, chat_id, photo_path, msg):
        print(f"OK alerta enviada a Telegram (chat={chat_id})")
    else:
        print("ERROR enviando alerta Telegram", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
