#!/usr/bin/env bash
# Monitor externo de la Pi del greenhouse. Corre en iagrow-vps via cron c/5min.
#
# Cubre el "blind spot" de los watchdogs in-Pi: cuando la Pi se cae completa
# (sin internet, sin luz, kernel panic, SD muerta), los watchdogs internos no
# pueden alertar porque viven en la Pi. Este script vive en el VPS y los
# alerts salen via Telegram Bot API (HTTPS outbound).
#
# Diseño:
#   - Cada run hace `curl /health` a la Pi via Tailscale MagicDNS
#   - Estado persistido en ~/.greenhouse-pi-monitor/{status,fails}
#   - Alerta SOLO en transicion ok→bad (despues de FAIL_THRESHOLD chequeos
#     consecutivos = ~10 min) y bad→ok (recovery). Sin spam.
#   - Antes de declarar a la Pi down, chequea que la VPS tenga Tailscale OK
#     para no culpar a la Pi cuando la rota es la VPS misma.
#
# Instalacion:
#   - Copiar TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID a /home/kowen/.env
#   - Agregar a crontab de kowen: */5 * * * * /home/kowen/proyectos/Control_clima/bin/greenhouse-pi-monitor.sh >> /var/log/greenhouse-pi-monitor.log 2>&1
#   - chmod +x este script

set -uo pipefail

ENV_FILE="${ENV_FILE:-/home/kowen/.env}"
STATE_DIR="${STATE_DIR:-$HOME/.greenhouse-pi-monitor}"
PI_HEALTH_URL="${PI_HEALTH_URL:-http://raspberrypi-1:5000/health}"
FAIL_THRESHOLD="${FAIL_THRESHOLD:-2}"  # 2 chequeos = ~10 min sin respuesta

mkdir -p "$STATE_DIR"
STATE_STATUS="$STATE_DIR/status"
STATE_FAILS="$STATE_DIR/fails"

# Cargar Telegram creds desde .env
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

now() { date '+%Y-%m-%d %H:%M:%S'; }
log()  { echo "[$(now)] $*"; }

send_telegram() {
    local msg="$1"
    if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
        log "WARN: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID no configurados en $ENV_FILE — mensaje no enviado"
        return 1
    fi
    curl -s --max-time 10 \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        --data-urlencode "text=${msg}" \
        -d "parse_mode=Markdown" \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" > /dev/null
}

# Estado anterior
prev_state=$(cat "$STATE_STATUS" 2>/dev/null || echo "OK")
fail_count=$(cat "$STATE_FAILS" 2>/dev/null || echo 0)

# Probe a la Pi
if curl -sf --max-time 10 "$PI_HEALTH_URL" > /dev/null 2>&1; then
    # Pi responde
    if [ "$prev_state" = "ALERTED" ]; then
        send_telegram "✅ *iagrow-vps → Pi*: La Pi volvió a responder a \`/health\`."
        log "Pi recovered, alert resolved"
    fi
    echo "OK" > "$STATE_STATUS"
    echo 0 > "$STATE_FAILS"
    log "OK"
else
    # Pi no responde
    fail_count=$((fail_count + 1))
    echo "$fail_count" > "$STATE_FAILS"
    log "FAIL count=$fail_count threshold=$FAIL_THRESHOLD"

    if [ "$fail_count" -ge "$FAIL_THRESHOLD" ] && [ "$prev_state" = "OK" ]; then
        # Descartar que la VPS sea la rota antes de culpar a la Pi
        vps_ts=$(tailscale status --json 2>/dev/null \
                 | python3 -c "import json,sys; print(json.load(sys.stdin).get('BackendState','Unknown'))" 2>/dev/null)
        if [ "$vps_ts" != "Running" ]; then
            send_telegram "⚠️ *iagrow-vps*: Mi Tailscale esta en \`$vps_ts\` (no Running). Por eso no puedo llegar a la Pi. La Pi podria estar bien."
            log "VPS-side Tailscale issue (state=$vps_ts), not Pi's fault"
        else
            send_telegram "🚨 *iagrow-vps → Pi*: La Pi NO responde a \`/health\` desde el VPS hace ~$((fail_count * 5)) min.

Mi Tailscale esta OK, asi que no soy yo. Posibles causas:
• Pi sin internet o luz
• tailscaled caido en la Pi
• Flask caido (intenta /restart_greenhouse al bot)
• Pi entera colgada

Probá responder al bot con \`/ping\`. Si tampoco contesta → Pi down total, requiere acceso fisico."
            log "ALERT sent: Pi unreachable from VPS"
        fi
        echo "ALERTED" > "$STATE_STATUS"
    fi
fi
