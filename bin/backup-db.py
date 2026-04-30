#!/usr/bin/env python3
"""
backup-db.py - Backup diario de la SQLite del greenhouse.

Usa el API .backup() de sqlite3 (modulo Python builtin, sin depender del
binario sqlite3 CLI). Hace copia consistente aunque la app este escribiendo.

Config via env:
- DB_PATH (default: <repo>/data/greenhouse.db)
- BACKUP_DIR (default: <repo>/data/backups)
- RETENTION_DAYS (default: 14)
- BACKUP_RSYNC_DEST (opcional: rsync a USB/NAS despues del backup)
- BACKUP_LOG (default: /var/log/greenhouse-backup.log)
"""
from __future__ import annotations

import os
import sys
import gzip
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_PATH = Path(os.environ.get("DB_PATH", PROJECT_ROOT / "data" / "greenhouse.db"))
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", PROJECT_ROOT / "data" / "backups"))
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "14"))
RSYNC_DEST = os.environ.get("BACKUP_RSYNC_DEST", "").strip()
LOG_PATH = Path(os.environ.get("BACKUP_LOG", "/var/log/greenhouse-backup.log"))


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with LOG_PATH.open("a") as f:
            f.write(line + "\n")
    except PermissionError:
        pass  # log file no writable, solo stdout


def backup_consistent(src: Path, dst: Path) -> None:
    """Usa sqlite3 .backup() para copia consistente con DB en uso."""
    with sqlite3.connect(str(src)) as src_conn:
        with sqlite3.connect(str(dst)) as dst_conn:
            src_conn.backup(dst_conn)


def gzip_file(path: Path) -> Path:
    out = Path(str(path) + ".gz")
    with path.open("rb") as f_in, gzip.open(out, "wb", compresslevel=6) as f_out:
        shutil.copyfileobj(f_in, f_out)
    path.unlink()  # borrar el .db sin comprimir
    return out


def cleanup_old(directory: Path, days: int) -> int:
    cutoff = datetime.now().timestamp() - days * 86400
    deleted = 0
    for f in directory.glob("greenhouse-*.db.gz"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
        except OSError as e:
            log(f"WARN: no pude borrar {f.name}: {e}")
    return deleted


def human_size(path: Path) -> str:
    n = path.stat().st_size
    for unit in ("B", "K", "M", "G"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}T"


def folder_size(path: Path) -> str:
    total = sum(f.stat().st_size for f in path.glob("**/*") if f.is_file())
    n = total
    for unit in ("B", "K", "M", "G"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}T"


def main() -> int:
    if not DB_PATH.exists():
        log(f"ERROR: DB no encontrada en {DB_PATH}")
        return 1

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    raw = BACKUP_DIR / f"greenhouse-{ts}.db"
    log(f"Backup: {DB_PATH} -> {raw}")

    try:
        backup_consistent(DB_PATH, raw)
    except Exception as e:
        log(f"ERROR backup: {e}")
        if raw.exists():
            try: raw.unlink()
            except OSError: pass
        return 1

    out_gz = gzip_file(raw)
    log(f"Backup OK: {out_gz.name} ({human_size(out_gz)})")

    deleted = cleanup_old(BACKUP_DIR, RETENTION_DAYS)
    if deleted:
        log(f"Borrados {deleted} backups con mas de {RETENTION_DAYS} dias")

    if RSYNC_DEST:
        try:
            subprocess.run(
                ["rsync", "-a", "--delete", str(BACKUP_DIR) + "/", RSYNC_DEST],
                check=True,
                capture_output=True,
                timeout=300,
            )
            log(f"Rsync a {RSYNC_DEST} OK")
        except subprocess.CalledProcessError as e:
            log(f"WARN: rsync a {RSYNC_DEST} fallo: {e.stderr.decode()[:200] if e.stderr else e}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            log(f"WARN: rsync no disponible o timeout: {e}")

    log(f"Backups totales: {folder_size(BACKUP_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
