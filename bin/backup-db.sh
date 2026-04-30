#!/usr/bin/env bash
# backup-db.sh - Backup diario de la SQLite del greenhouse.
#
# - Hace una copia consistente con `sqlite3 .backup` (no es solo un cp:
#   asegura que la DB no se corrompa si la app esta escribiendo).
# - Comprime con gzip.
# - Mantiene los ultimos N dias en BACKUP_DIR.
# - Si BACKUP_RSYNC_DEST esta seteado, hace rsync (ej. usb montado).
# - Loguea a /var/log/greenhouse-backup.log

set -euo pipefail

DB_PATH="${DB_PATH:-/home/kowen/proyectos/Control_clima/data/greenhouse.db}"
BACKUP_DIR="${BACKUP_DIR:-/home/kowen/proyectos/Control_clima/data/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
RSYNC_DEST="${BACKUP_RSYNC_DEST:-}"
LOG="${BACKUP_LOG:-/var/log/greenhouse-backup.log}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"
}

mkdir -p "$BACKUP_DIR"

if [[ ! -f "$DB_PATH" ]]; then
    log "ERROR: DB no encontrada en $DB_PATH"
    exit 1
fi

TS=$(date '+%Y-%m-%d_%H%M')
OUT="$BACKUP_DIR/greenhouse-${TS}.db"

log "Backup: $DB_PATH -> $OUT"

# .backup hace una copia consistente aunque la DB este abierta y escribiendo
sqlite3 "$DB_PATH" ".backup '$OUT'"

# Comprimir
gzip "$OUT"
OUT_GZ="${OUT}.gz"
SIZE=$(du -h "$OUT_GZ" | cut -f1)
log "Backup OK: $OUT_GZ ($SIZE)"

# Retencion: borrar archivos mas viejos que RETENTION_DAYS
DELETED=$(find "$BACKUP_DIR" -name "greenhouse-*.db.gz" -type f -mtime "+${RETENTION_DAYS}" -print -delete | wc -l)
if [[ "$DELETED" -gt 0 ]]; then
    log "Borrados $DELETED backups mas viejos que ${RETENTION_DAYS} dias"
fi

# Rsync opcional a destino externo (USB, NAS, etc.)
if [[ -n "$RSYNC_DEST" ]]; then
    if rsync -a --delete "$BACKUP_DIR/" "$RSYNC_DEST/" 2>>"$LOG"; then
        log "Rsync a $RSYNC_DEST OK"
    else
        log "WARN: rsync a $RSYNC_DEST fallo (codigo $?)"
    fi
fi

# Reporte de espacio total ocupado
TOTAL=$(du -sh "$BACKUP_DIR" | cut -f1)
log "Backups totales: $TOTAL"
