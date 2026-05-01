#!/usr/bin/env bash
# Tailscale + Funnel watchdog para la Pi del greenhouse.
#
# Corre cada 5 min via systemd timer. Verifica:
#  1. tailscaled corriendo
#  2. Tailscale conectado (BackendState = "Running")
#  3. Funnel activo apuntando al puerto 5000
#  4. App local respondiendo en /health
#
# Si alguna falla, intenta recuperar. Si recupera, manda Telegram.
# Si no puede recuperar, alerta y deja log.
#
# Notas:
# - Corre como root (necesario para systemctl + tailscale up + funnel).
# - "Logged out" requiere re-auth manual (no se puede automatizar
#   sin guardar auth key en disco).

set -uo pipefail

LOG="/var/log/greenhouse-tailscale-watchdog.log"
EXPECTED_PORT="${EXPECTED_FUNNEL_PORT:-5000}"
ENV_FILE="/home/kowen/proyectos/Control_clima/.env"

# Cargar Telegram creds del .env si existe
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"
}

send_telegram() {
    local msg="$1"
    if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
        log "  (Telegram no configurado, mensaje no enviado: $msg)"
        return
    fi
    curl -s --max-time 10 \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        --data-urlencode "text=${msg}" \
        -d "parse_mode=Markdown" \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" > /dev/null 2>&1 || true
}

HOST_LABEL="$(hostname)"
RECOVERED_SOMETHING=0
PROBLEMS=""

# --- 1. tailscaled corriendo ---
if ! systemctl is-active --quiet tailscaled; then
    log "WARN: tailscaled inactivo. Arrancando..."
    systemctl start tailscaled
    sleep 5
    if systemctl is-active --quiet tailscaled; then
        log "OK: tailscaled levantado."
        RECOVERED_SOMETHING=1
        PROBLEMS="$PROBLEMS tailscaled-restart"
    else
        log "ERROR: tailscaled no arranca."
        send_telegram "🚨 *${HOST_LABEL}*: tailscaled NO ARRANCA. Requiere intervencion manual."
        exit 1
    fi
fi

# --- 2. Tailscale conectado ---
STATUS_JSON=$(tailscale status --json 2>/dev/null || echo '{}')
BACKEND_STATE=$(echo "$STATUS_JSON" | python3 -c "
import json, sys
try:
    print(json.load(sys.stdin).get('BackendState', 'Unknown'))
except Exception:
    print('Unknown')
" 2>/dev/null)

if [ "$BACKEND_STATE" != "Running" ]; then
    log "WARN: BackendState='$BACKEND_STATE' (esperado 'Running'). Intentando tailscale up..."
    if [ "$BACKEND_STATE" = "NeedsLogin" ] || [ "$BACKEND_STATE" = "NoState" ]; then
        log "ERROR: Tailscale necesita re-login manual (BackendState=$BACKEND_STATE). No se puede automatizar."
        send_telegram "🚨 *${HOST_LABEL}*: Tailscale necesita re-login (estado: $BACKEND_STATE). SSH a la Pi en LAN y corré: \`sudo tailscale up\`"
        exit 1
    fi
    tailscale up > /dev/null 2>&1
    sleep 5
    NEW_STATE=$(tailscale status --json 2>/dev/null | python3 -c "
import json, sys
try:
    print(json.load(sys.stdin).get('BackendState', 'Unknown'))
except Exception:
    print('Unknown')
" 2>/dev/null)
    if [ "$NEW_STATE" = "Running" ]; then
        log "OK: Tailscale reconectado."
        RECOVERED_SOMETHING=1
        PROBLEMS="$PROBLEMS tailscale-reconnect"
    else
        log "ERROR: Tailscale sigue '$NEW_STATE' tras up."
        send_telegram "🚨 *${HOST_LABEL}*: Tailscale no reconecta (estado: $NEW_STATE). Requiere intervencion manual."
        exit 1
    fi
fi

# --- 3. Funnel activo ---
FUNNEL_STATUS=$(tailscale funnel status 2>&1 || true)
if ! echo "$FUNNEL_STATUS" | grep -q "Funnel on"; then
    log "WARN: Funnel inactivo. Reactivando puerto $EXPECTED_PORT..."
    tailscale funnel --bg "$EXPECTED_PORT" > /dev/null 2>&1 || true
    sleep 3
    if tailscale funnel status 2>&1 | grep -q "Funnel on"; then
        log "OK: Funnel reactivado."
        RECOVERED_SOMETHING=1
        PROBLEMS="$PROBLEMS funnel-reactivate"
    else
        log "ERROR: No pude reactivar Funnel."
        send_telegram "🚨 *${HOST_LABEL}*: Funnel no reactiva. Conexion remota perdida. SSH a la Pi y corré: \`sudo tailscale funnel --bg $EXPECTED_PORT\`"
    fi
fi

# --- 4. App local responde ---
if ! curl -sf --max-time 5 "http://127.0.0.1:${EXPECTED_PORT}/health" > /dev/null 2>&1; then
    log "WARN: App local no responde en /health. (No reiniciamos desde aca, systemd Restart=on-failure se encarga.)"
    # Si systemd la tiene como failed, intentar arrancarla
    if ! systemctl is-active --quiet greenhouse; then
        log "  greenhouse.service inactivo, arrancando..."
        systemctl start greenhouse
        sleep 8
        if curl -sf --max-time 5 "http://127.0.0.1:${EXPECTED_PORT}/health" > /dev/null 2>&1; then
            log "OK: greenhouse recuperado."
            RECOVERED_SOMETHING=1
            PROBLEMS="$PROBLEMS greenhouse-restart"
        else
            send_telegram "🚨 *${HOST_LABEL}*: greenhouse.service no levanta. Revisar /var/log/greenhouse.log"
        fi
    fi
fi

# --- Resumen ---
if [ "$RECOVERED_SOMETHING" = "1" ]; then
    send_telegram "🔧 *${HOST_LABEL}*: Watchdog recuperó:${PROBLEMS}"
fi

log "Watchdog OK"
