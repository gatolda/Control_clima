#!/bin/bash
# prune-vps-backups.sh — retention policy GFS para Pi-Backups en el VPS.
#
# Corre via cron diario en el VPS (NO en la Pi):
#   0 4 * * * /home/kowen/bin/prune-vps-backups.sh >> /var/log/prune-backups.log 2>&1
#
# Politica:
#   - Mantiene daily (cualquier hora) de los últimos 14 días
#   - Mantiene 1 por semana (lunes) de los últimos 60 días
#   - Mantiene 1 por mes (día 1) de los últimos 365 días
#   - Borra todo lo demás
#
# Total esperado: ~14 daily + ~8 weekly + ~12 monthly = ~34 archivos
# A ~6MB cada uno = ~204MB en VPS. Sobrado.

set -euo pipefail
BACKUP_DIR="${BACKUP_DIR:-/home/kowen/Pi-Backups}"
DAYS_DAILY=14
DAYS_WEEKLY=60
DAYS_MONTHLY=365
DRY_RUN="${DRY_RUN:-0}"   # set DRY_RUN=1 para solo loguear, sin borrar

cd "$BACKUP_DIR" || { echo "ERROR: no existe $BACKUP_DIR"; exit 1; }

declare -A KEEP
NOW=$(date +%s)
log() { echo "[$(date +%Y-%m-%d_%H:%M)] $*"; }

# Decidir qué archivos quedan
for f in greenhouse-*.db.gz; do
    [[ -f "$f" ]] || continue
    # Extraer YYYY-MM-DD del nombre "greenhouse-YYYY-MM-DD_HHMM.db.gz"
    date_part="${f#greenhouse-}"
    date_part="${date_part%_*}"
    file_ts=$(date -d "$date_part" +%s 2>/dev/null || echo "")
    [[ -z "$file_ts" ]] && { log "SKIP nombre raro: $f"; continue; }
    age_days=$(( (NOW - file_ts) / 86400 ))

    if (( age_days <= DAYS_DAILY )); then
        KEEP["$f"]=daily
    elif (( age_days <= DAYS_WEEKLY )); then
        dow=$(date -d "$date_part" +%u)        # 1=lunes
        [[ "$dow" == "1" ]] && KEEP["$f"]=weekly
    elif (( age_days <= DAYS_MONTHLY )); then
        day=$(date -d "$date_part" +%d)        # día del mes
        [[ "$day" == "01" ]] && KEEP["$f"]=monthly
    fi
done

kept=0
deleted=0
for f in greenhouse-*.db.gz; do
    [[ -f "$f" ]] || continue
    if [[ -n "${KEEP[$f]:-}" ]]; then
        kept=$((kept + 1))
    else
        if [[ "$DRY_RUN" == "1" ]]; then
            log "[DRY-RUN] DELETE $f"
        else
            rm -- "$f"
            log "DELETE $f"
        fi
        deleted=$((deleted + 1))
    fi
done

total_size=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
log "RESUMEN: kept=$kept deleted=$deleted total=$total_size"
