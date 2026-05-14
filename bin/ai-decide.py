#!/usr/bin/env python3
"""
ai-decide.py — corre cada 30 min via systemd timer.

Solo actúa si el sistema esta en modo "auto_ia" en la DB. En cualquier
otro modo, exit inmediato sin tocar nada (asi el timer puede correr
siempre habilitado y solo el modo activa el control).

Exit codes:
  0 = OK (con o sin acciones) — incluye "no era modo auto_ia, exit"
  1 = config error
  2 = error de IA o validacion (acciones no aplicadas, registrado en DB)
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_env():
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    print("=== ai-decide ===")
    load_env()

    try:
        from core.config_loader import ConfigLoader
        from data.database import Database
        from core.gpio_setup import inicializar_gpio
        from core.actuator_manager import ActuatorManager
        from core.sensor_reader import SensorReader
        from core.climate_controller import ClimateController
        from core.ai_controller import build_context, decide, validate_and_apply
    except Exception as e:
        print(f"ERROR import: {e}", file=sys.stderr)
        return 1

    try:
        cfg = ConfigLoader(str(PROJECT_ROOT / "config.yml"))
        cfg.cargar_configuracion()
        db = Database(str(PROJECT_ROOT / "data" / "greenhouse.db"))
    except Exception as e:
        print(f"ERROR init config/db: {e}", file=sys.stderr)
        return 1

    # Salir silenciosamente si no esta en modo auto_ia
    mode = db.get_config("mode", "manual")
    if mode != "auto_ia":
        print(f"Modo actual: '{mode}' (no auto_ia) — exit sin actuar")
        return 0

    print("Modo auto_ia activo — procediendo")

    # Inicializar managers (sin start)
    try:
        inicializar_gpio()
        actuators_cfg = cfg.obtener("actuadores", {})
        actuator_manager = ActuatorManager(actuators_cfg, db)
        sensor_reader = SensorReader(cfg)
        climate_controller = ClimateController(cfg, db, sensor_reader, actuator_manager)
    except Exception as e:
        print(f"ERROR init managers: {e}", file=sys.stderr)
        db.save_ai_decision({}, None, None, error=f"init_managers: {e}")
        return 1

    # Failsafe activo → no actuar
    if getattr(climate_controller, "failsafe_active", False):
        print("Failsafe activo — saltando decisión IA")
        db.save_ai_decision({"failsafe": True}, None, None, error="failsafe_active")
        return 0

    # 1. Construir contexto
    print("Construyendo contexto...")
    try:
        context = build_context(db, sensor_reader, actuator_manager, climate_controller)
    except Exception as e:
        print(f"ERROR contexto: {e}", file=sys.stderr)
        db.save_ai_decision({}, None, None, error=f"build_context: {e}")
        return 2

    # 2. Llamar Claude
    print("Llamando Claude Sonnet 4.6...")
    try:
        decision = decide(context)
    except Exception as e:
        print(f"ERROR Claude: {e}", file=sys.stderr)
        db.save_ai_decision(context, None, None, error=f"claude: {e}")
        return 2

    print(f"Confianza: {decision.get('confianza')}/10")
    print(f"Acciones propuestas: {len(decision.get('acciones', []))}")
    if decision.get("alerta_humana"):
        print(f"⚠️ ALERTA HUMANA: {decision['alerta_humana']}")

    # 3. Validar y aplicar
    applied = validate_and_apply(decision, actuator_manager, min_confidence=5)
    print(f"Aplicadas: {len(applied['applied'])} · Skipped: {len(applied['skipped'])} · Errors: {len(applied['errors'])}")
    for a in applied["applied"]:
        print(f"  ✓ {a['actuador']} → {a['estado']}")
    for a in applied["skipped"]:
        print(f"  ⊘ {a['actuador']} → {a['estado']} ({a.get('motivo_skip')})")
    for a in applied["errors"]:
        print(f"  ✗ {a['actuador']} → {a['estado']} ({a.get('error')})")

    # 4. Guardar en DB
    db.save_ai_decision(context, decision, applied)

    # 5. Alertar via Telegram si hay alerta humana
    if decision.get("alerta_humana"):
        try:
            import requests
            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            chat = os.environ.get("TELEGRAM_CHAT_ID")
            if token and chat:
                msg = f"🤖 *Auto IA — alerta*\n\n{decision['alerta_humana']}\n\n_Razonamiento:_\n{decision.get('razonamiento_general', '')}"
                requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data={"chat_id": chat, "text": msg, "parse_mode": "Markdown"},
                    timeout=10,
                )
                print("Alerta enviada a Telegram")
        except Exception as e:
            print(f"WARN: no pude enviar alerta Telegram: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
