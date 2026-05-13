#!/usr/bin/env python3
"""
take-snapshot.py — script standalone que toma una foto y guarda metadata.

Se invoca desde:
  - systemd timer (greenhouse-snapshot.timer) cada N horas
  - Telegram bot /photo command
  - API /api/camera/capture (via camera_manager directamente, no este script)

Exit codes:
  0 = foto OK
  1 = error de captura
  2 = error de config / DB
"""
from __future__ import annotations
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    try:
        from core.config_loader import ConfigLoader
        from data.database import Database
        from core.camera_manager import CameraManager
    except Exception as e:
        print(f"ERROR importando modulos: {e}", file=sys.stderr)
        return 2

    try:
        cfg = ConfigLoader(str(PROJECT_ROOT / "config.yml"))
        cfg.cargar_configuracion()
        db = Database(str(PROJECT_ROOT / "data" / "greenhouse.db"))
        cam = CameraManager(cfg, db)
    except Exception as e:
        print(f"ERROR init: {e}", file=sys.stderr)
        return 2

    result = cam.capture()
    if not result.get("ok"):
        print(f"ERROR capture: {result.get('error')}", file=sys.stderr)
        return 1

    print(f"OK {result['filename']} ({result['size_bytes']}b, brightness={result.get('brightness')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
