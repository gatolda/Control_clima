#!/usr/bin/env bash
# deploy.sh - Pull seguro de cambios + restart + healthcheck + auto-rollback.
#
# Uso (en la Pi):
#   bash bin/deploy.sh             # deploy desde origin/main
#   bash bin/deploy.sh v1.2.0      # deploy de un tag especifico
#
# Hace:
#   1. Backup pre-deploy de la DB
#   2. git fetch + pull (o checkout tag)
#   3. pip install si requirements.txt cambio
#   4. systemctl restart greenhouse
#   5. Espera 8s + curl /health
#   6. Si /health no responde 200 -> rollback al commit previo + alerta
#   7. Si OK -> log y opcionalmente Telegram

set -uo pipefail

REPO_DIR="${REPO_DIR:-/home/kowen/proyectos/Control_clima}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:5000/health}"
LOG="/var/log/greenhouse-deploy.log"
ENV_FILE="$REPO_DIR/.env"
TARGET_REF="${1:-origin/main}"

# Cargar Telegram creds
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

log() {
    local line="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$line"
    # No tee a archivo si no tenemos permisos (el script puede correrse como kowen)
    if [ -w "$LOG" ] || sudo touch "$LOG" 2>/dev/null; then
        echo "$line" | sudo tee -a "$LOG" > /dev/null
    fi
}

send_telegram() {
    local msg="$1"
    if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
        return
    fi
    curl -s --max-time 10 \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        --data-urlencode "text=${msg}" \
        -d "parse_mode=Markdown" \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" > /dev/null 2>&1 || true
}

check_health() {
    curl -sf --max-time 10 "$HEALTH_URL" > /dev/null 2>&1
}

cd "$REPO_DIR" || { log "ERROR: $REPO_DIR no existe"; exit 1; }

HOST_LABEL="$(hostname)"
CURRENT_COMMIT=$(git rev-parse HEAD)
log "=== Deploy start: $HOST_LABEL ==="
log "Current commit: $CURRENT_COMMIT"
log "Target: $TARGET_REF"

# 1. Pre-deploy backup
log "Backup pre-deploy..."
if /usr/bin/python3 bin/backup-db.py > /dev/null 2>&1; then
    log "  OK"
else
    log "  WARN: backup fallo, continuando igual"
fi

# 2. Fetch + checkout
git fetch origin --tags 2>&1 | tee -a /dev/null || {
    log "ERROR: git fetch fallo"
    exit 1
}

# Determinar el SHA destino
if [[ "$TARGET_REF" == origin/* ]]; then
    TARGET_COMMIT=$(git rev-parse "$TARGET_REF")
elif git rev-parse --verify "$TARGET_REF" > /dev/null 2>&1; then
    TARGET_COMMIT=$(git rev-parse "$TARGET_REF")
else
    log "ERROR: ref '$TARGET_REF' no existe."
    exit 1
fi

log "Target commit: $TARGET_COMMIT"

if [ "$CURRENT_COMMIT" = "$TARGET_COMMIT" ]; then
    log "Ya estamos en $TARGET_COMMIT. Nada para deployar."
    exit 0
fi

# Verificar si requirements.txt va a cambiar
REQS_CHANGED=0
if git diff "$CURRENT_COMMIT".."$TARGET_COMMIT" --name-only 2>/dev/null | grep -q '^requirements\.txt$'; then
    REQS_CHANGED=1
fi

# 3. Checkout
log "Checkout a $TARGET_COMMIT..."
if ! git checkout "$TARGET_COMMIT" --quiet 2>&1; then
    log "ERROR: checkout fallo"
    exit 1
fi

# 4. pip install si cambio requirements
if [ "$REQS_CHANGED" = "1" ]; then
    log "requirements.txt cambio, pip install..."
    /usr/bin/pip3 install --quiet -r requirements.txt 2>&1 | tee -a /dev/null || {
        log "WARN: pip install fallo, intentando deploy igual"
    }
fi

# 5. Restart
log "Restart greenhouse.service..."
sudo systemctl restart greenhouse
sleep 8

# 6. Healthcheck con retry
log "Healthcheck..."
HEALTH_OK=0
for i in 1 2 3 4 5; do
    if check_health; then
        HEALTH_OK=1
        break
    fi
    log "  intento $i/5 fallo, esperando 3s..."
    sleep 3
done

if [ "$HEALTH_OK" = "1" ]; then
    NEW_SHORT=$(git rev-parse --short HEAD)
    OLD_SHORT=$(echo "$CURRENT_COMMIT" | cut -c1-7)
    log "OK: deploy exitoso $OLD_SHORT -> $NEW_SHORT"
    send_telegram "✅ *${HOST_LABEL}*: deploy OK \`${OLD_SHORT}\` -> \`${NEW_SHORT}\`"
    exit 0
fi

# 7. Rollback
log "ERROR: /health no responde tras 5 intentos. Rollback..."
git checkout "$CURRENT_COMMIT" --quiet
sudo systemctl restart greenhouse
sleep 8

if check_health; then
    log "Rollback OK a $CURRENT_COMMIT"
    send_telegram "⚠️ *${HOST_LABEL}*: Deploy fallo, rollback OK a \`$(echo "$CURRENT_COMMIT" | cut -c1-7)\`. /health respondia 200 con la version vieja."
    exit 1
else
    log "CRITICAL: rollback NO recupero /health. Pi en estado degradado."
    send_telegram "🚨 *${HOST_LABEL}*: DEPLOY + ROLLBACK FALLARON. La app NO responde. Intervencion manual urgente."
    exit 2
fi
