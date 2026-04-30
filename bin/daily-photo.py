#!/usr/bin/env python3
"""
Toma una foto diaria del cultivo y la asocia al ciclo activo.
Se invoca desde systemd timer (greenhouse-daily-photo.timer).
Si no hay ciclo activo o la camara no esta disponible, sale sin error.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

# Cargar .env del proyecto
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.database import Database


def main() -> int:
    db = Database()
    cycle = db.get_active_cycle()
    if not cycle:
        print("[daily-photo] No hay ciclo activo. Salgo.", flush=True)
        return 0

    # Importar camera_manager solo aca para evitar dependencia si no se usa
    try:
        from core.camera_manager import CameraManager
        from core.config_loader import ConfigLoader
    except Exception as e:
        print(f"[daily-photo] No pude importar camara: {e}", flush=True)
        return 0

    config = ConfigLoader()
    config.cargar_configuracion()
    cam = CameraManager(config, db)

    result = cam.capture()
    if not result.get("ok"):
        print(f"[daily-photo] Captura fallo: {result.get('error')}", flush=True)
        return 0

    pid = db.add_photo(
        cycle_id=cycle["id"],
        date=date.today().isoformat(),
        filename=result["filename"],
        stage_at_capture=cycle["current_stage"],
    )
    print(f"[daily-photo] OK: photo_id={pid} filename={result['filename']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
