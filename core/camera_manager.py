"""
Gestion de camara USB UVC (Logitech C270 / C920 / similar) via fswebcam.

Toma snapshots on-demand desde la API y los guarda en static/camera/.
El scheduling de fotos periodicas se hace con systemd timer
(`greenhouse-snapshot.timer`), no con thread interno — mas robusto.

Analisis IA con Claude Vision (opcional) queda como hook futuro,
no se invoca por defecto.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

CAMERA_DEVICE_DEFAULT = "/dev/video0"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CAPTURE_DIR  = PROJECT_ROOT / "static" / "camera"
LATEST_LINK  = CAPTURE_DIR / "latest.jpg"


class CameraManager:
    """Captura imagenes USB via fswebcam. Almacena en static/camera/."""

    def __init__(self, config, database):
        self.config = config
        self.db = database
        cam_cfg = config.obtener("camara", {}) if hasattr(config, "obtener") else {}
        self.enabled    = cam_cfg.get("habilitada", True)
        self.device     = cam_cfg.get("dispositivo", CAMERA_DEVICE_DEFAULT)
        # C270 max es 960x720 nativo, 1280x720 escalado. Default seguro.
        self.resolution = cam_cfg.get("resolucion", [960, 720])
        self.skip_frames = int(cam_cfg.get("skip_frames", 10))
        self.capture_frames = int(cam_cfg.get("capture_frames", 3))
        self.jpeg_quality = int(cam_cfg.get("jpeg_quality", 85))

        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

        if self.enabled and not shutil.which("fswebcam"):
            print("CameraManager: fswebcam no instalado. `sudo apt install fswebcam`")
            self.enabled = False

        if self.enabled:
            print(f"CameraManager: ON, device={self.device}, res={self.resolution[0]}x{self.resolution[1]}")
        else:
            print("CameraManager: deshabilitada")

    def capture(self) -> dict:
        """Toma una foto y devuelve info del archivo."""
        if not self.enabled:
            return {"ok": False, "error": "camara_deshabilitada"}

        ts = datetime.now()
        filename = f"snap_{ts:%Y%m%d_%H%M%S}.jpg"
        filepath = CAPTURE_DIR / filename

        # fswebcam params:
        # --skip N: descarta los primeros N frames (la webcam tarda en ajustar
        #   exposicion/balance, los primeros frames suelen estar mal expuestos)
        # -F N: promedia N frames para reducir ruido y movimiento
        # -S N: salta N frames antes de capturar (estabilizacion adicional)
        # --no-banner: evita la barra negra con timestamp/texto en la foto
        # -q: quieter
        cmd = [
            "fswebcam",
            "-d", self.device,
            "-r", f"{self.resolution[0]}x{self.resolution[1]}",
            "--no-banner",
            "--skip", str(self.skip_frames),
            "-F", str(self.capture_frames),
            "-S", "5",
            "--jpeg", str(self.jpeg_quality),
            "-q",
            str(filepath),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=20, text=True)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout_capturando"}
        except Exception as e:
            return {"ok": False, "error": f"exception: {e}"}

        if res.returncode != 0 or not filepath.exists():
            return {"ok": False, "error": f"fswebcam_failed: {res.stderr[:200]}"}

        file_size = filepath.stat().st_size

        # Symlink "latest.jpg" apunta a la ultima capturada (para el dashboard).
        try:
            if LATEST_LINK.exists() or LATEST_LINK.is_symlink():
                LATEST_LINK.unlink()
            LATEST_LINK.symlink_to(filename)
        except Exception:
            # Si symlinks no son soportados (FS raro), copiamos
            try:
                shutil.copy2(filepath, LATEST_LINK)
            except Exception:
                pass

        # Brightness del frame (promedio simple usando PIL si esta disponible).
        # Sirve para detectar "carpa abierta" (spike de brightness vs anteriores).
        brightness = self._compute_brightness(filepath)

        # Persistir metadata en DB si la tabla existe
        snapshot_id = None
        if self.db and hasattr(self.db, "save_camera_snapshot"):
            try:
                snapshot_id = self.db.save_camera_snapshot(
                    filename=filename,
                    timestamp=ts.strftime("%Y-%m-%d %H:%M:%S"),
                    file_size=file_size,
                    brightness=brightness,
                )
            except Exception as e:
                print(f"CameraManager: error guardando metadata DB: {e}")

        return {
            "ok": True,
            "filename": filename,
            "path": str(filepath),
            "size_bytes": file_size,
            "brightness": brightness,
            "snapshot_id": snapshot_id,
            "url": f"/static/camera/{filename}",
            "timestamp": ts.isoformat(),
        }

    def _compute_brightness(self, filepath: Path) -> float | None:
        """Promedio de brightness 0-255. None si PIL no esta disponible."""
        try:
            from PIL import Image, ImageStat
            with Image.open(filepath) as img:
                gray = img.convert("L")
                return round(ImageStat.Stat(gray).mean[0], 2)
        except Exception:
            return None

    def get_latest_path(self) -> Path | None:
        if LATEST_LINK.exists():
            return LATEST_LINK
        # Fallback: el ultimo file por mtime
        files = sorted(CAPTURE_DIR.glob("snap_*.jpg"), reverse=True)
        return files[0] if files else None

    def list_snapshots(self, limit: int = 50) -> list[dict]:
        """Lista snapshots ordenados por timestamp desc, mas reciente primero."""
        # Preferir DB si tiene la info (incluye brightness + metadata)
        if self.db and hasattr(self.db, "get_camera_snapshots"):
            try:
                return self.db.get_camera_snapshots(limit=limit)
            except Exception:
                pass
        # Fallback al filesystem
        files = sorted(CAPTURE_DIR.glob("snap_*.jpg"), reverse=True)[:limit]
        out = []
        for f in files:
            m = re.match(r"snap_(\d{8})_(\d{6})\.jpg", f.name)
            ts = f"{m.group(1)[0:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]} {m.group(2)[0:2]}:{m.group(2)[2:4]}:{m.group(2)[4:6]}" if m else ""
            out.append({
                "filename": f.name,
                "timestamp": ts,
                "size_bytes": f.stat().st_size,
                "url": f"/static/camera/{f.name}",
            })
        return out

    def get_status(self) -> dict:
        latest = self.get_latest_path()
        return {
            "enabled": self.enabled,
            "device": self.device,
            "resolution": self.resolution,
            "snapshots_count": len(list(CAPTURE_DIR.glob("snap_*.jpg"))),
            "latest_file": latest.name if latest else None,
        }

    # ───── stubs para no romper integraciones existentes ─────
    def start(self): pass  # scheduling lo hace systemd timer ahora
    def stop(self):  pass
