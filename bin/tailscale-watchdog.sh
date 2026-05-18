#!/usr/bin/env bash
# Tailscale + Funnel watchdog para la Pi del greenhouse.
#
# Corre cada 5 min via systemd timer. Verifica:
#  1. tailscaled corriendo
#  2. Tailscale conectado (BackendState = "Running" Y Self.Online = true)
#  3. Funnel activo apuntando al puerto 5000
#  4. App local respondiendo en /health
#  5. Sensores reportando datos. Si TODOS los sensores estan sin_datos por
#     >=2 chequeos consecutivos (10 min), hace USB reset del CH340 por sysfs
#     (caso CH340 hang en EIO, 2026-05-18 — replug fisico era el unico fix).
#
# Si alguna falla, intenta recuperar. Si recupera, manda Telegram.
# Si no puede recuperar, alerta y deja log.
#
# Notas:
# - Corre como root (necesario para systemctl + tailscale up + funnel +
#   escritura a /sys/bus/usb/devices/.../authorized).
# - "Logged out" requiere re-auth manual (no se puede automatizar
#   sin guardar auth key en disco).
# - BackendState=Running NO garantiza conectividad real al tailnet; tambien
#   chequeamos Self.Online (lo reporta el coordinador). Sin ese check, una
#   Tailscale "running pero ciega" pasaba desapercibida (caso 2026-05-18).

set -uo pipefail

LOG="/var/log/greenhouse-tailscale-watchdog.log"
EXPECTED_PORT="${EXPECTED_FUNNEL_PORT:-5000}"
ENV_FILE="/home/kowen/proyectos/Control_clima/.env"
STATE_DIR="/var/lib/greenhouse-watchdog"
SENSOR_FAIL_COUNT_FILE="$STATE_DIR/sensor-fail-count"
LAST_USB_RESET_FILE="$STATE_DIR/last-usb-reset"
USB_RESET_COOLDOWN_S=900  # no resetear USB mas de una vez cada 15 min

# CH340 USB-serial del Arduino (`lsusb` lo lista como 1a86:7523)
CH340_VENDOR="1a86"
CH340_PRODUCT="7523"

mkdir -p "$STATE_DIR"

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

# Devuelve "BackendState|Self.Online" (ej: "Running|true").
# Self.Online=true significa que el coordinador realmente nos ve online.
# Si daemon esta colgado o sin red, BackendState puede ser Running pero
# Self.Online queda en false/null.
ts_state() {
    tailscale status --json 2>/dev/null | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    bs = d.get('BackendState', 'Unknown')
    online = d.get('Self', {}).get('Online')
    print(f\"{bs}|{'true' if online else 'false'}\")
except Exception:
    print('Unknown|false')
" 2>/dev/null
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

# --- 2. Tailscale conectado (BackendState + Self.Online) ---
STATE=$(ts_state)
BACKEND_STATE="${STATE%|*}"
SELF_ONLINE="${STATE#*|}"

if [ "$BACKEND_STATE" != "Running" ] || [ "$SELF_ONLINE" != "true" ]; then
    log "WARN: BackendState='$BACKEND_STATE' Self.Online='$SELF_ONLINE' — intentando recovery..."
    if [ "$BACKEND_STATE" = "NeedsLogin" ] || [ "$BACKEND_STATE" = "NoState" ]; then
        log "ERROR: Tailscale necesita re-login manual (BackendState=$BACKEND_STATE). No se puede automatizar."
        send_telegram "🚨 *${HOST_LABEL}*: Tailscale necesita re-login (estado: $BACKEND_STATE). SSH a la Pi en LAN y corré: \`sudo tailscale up\`"
        exit 1
    fi

    # Intento 1: tailscale up (resetea intencion, suele alcanzar)
    tailscale up > /dev/null 2>&1
    sleep 5
    STATE=$(ts_state)
    BACKEND_STATE="${STATE%|*}"
    SELF_ONLINE="${STATE#*|}"

    if [ "$BACKEND_STATE" = "Running" ] && [ "$SELF_ONLINE" = "true" ]; then
        log "OK: Tailscale recuperado tras 'tailscale up'."
        RECOVERED_SOMETHING=1
        PROBLEMS="$PROBLEMS tailscale-reconnect"
    else
        # Intento 2: restart del daemon (mas agresivo, cura el caso de
        # daemon colgado pero Running, observado el 2026-05-18)
        log "WARN: tras 'up' sigue state=$BACKEND_STATE online=$SELF_ONLINE. Restart tailscaled..."
        systemctl restart tailscaled
        sleep 10
        STATE=$(ts_state)
        BACKEND_STATE="${STATE%|*}"
        SELF_ONLINE="${STATE#*|}"

        if [ "$BACKEND_STATE" = "Running" ] && [ "$SELF_ONLINE" = "true" ]; then
            log "OK: Tailscale recuperado tras restart tailscaled."
            RECOVERED_SOMETHING=1
            PROBLEMS="$PROBLEMS tailscaled-restart"
        else
            log "ERROR: Tailscale no recupera (state=$BACKEND_STATE online=$SELF_ONLINE)."
            send_telegram "🚨 *${HOST_LABEL}*: Tailscale no recupera (state=$BACKEND_STATE online=$SELF_ONLINE). SSH a la Pi en LAN y corré: \`sudo systemctl restart tailscaled\`"
            exit 1
        fi
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

# --- 5. Sensores stale → USB reset del CH340 ---
# Si TODOS los sensores reportan algo distinto de "ok" en /health durante
# >=2 chequeos consecutivos (10 min), asumimos que el CH340 USB-serial se
# colgo en estado EIO (caso 2026-05-18). El service-restart no lo cura,
# solo un USB reset por sysfs (equivalente a desenchufar+enchufar el cable).
HEALTH_JSON=$(curl -sf --max-time 5 "http://127.0.0.1:${EXPECTED_PORT}/health" 2>/dev/null || echo '{}')
ALL_SENSORS_DEAD=$(echo "$HEALTH_JSON" | python3 -c "
import json, sys
try:
    sh = json.load(sys.stdin).get('components', {}).get('sensor_health', {})
    print('true' if sh and all(v != 'ok' for v in sh.values()) else 'false')
except Exception:
    print('false')
" 2>/dev/null)

if [ "$ALL_SENSORS_DEAD" = "true" ]; then
    fail_count=$(cat "$SENSOR_FAIL_COUNT_FILE" 2>/dev/null || echo 0)
    fail_count=$((fail_count + 1))
    echo "$fail_count" > "$SENSOR_FAIL_COUNT_FILE"
    log "WARN: Todos los sensores sin_datos (count=$fail_count)."

    if [ "$fail_count" -ge 2 ]; then
        now_epoch=$(date +%s)
        last_reset=$(cat "$LAST_USB_RESET_FILE" 2>/dev/null || echo 0)
        if [ "$((now_epoch - last_reset))" -lt "$USB_RESET_COOLDOWN_S" ]; then
            log "  USB reset en cooldown (ultimo hace $((now_epoch - last_reset))s, threshold ${USB_RESET_COOLDOWN_S}s)."
        else
            # Buscar el path en sysfs del CH340 por vendor:product
            usb_path=""
            for vdr in /sys/bus/usb/devices/*/idVendor; do
                if [ -f "$vdr" ] && [ "$(cat "$vdr" 2>/dev/null)" = "$CH340_VENDOR" ]; then
                    prod_file="$(dirname "$vdr")/idProduct"
                    if [ -f "$prod_file" ] && [ "$(cat "$prod_file" 2>/dev/null)" = "$CH340_PRODUCT" ]; then
                        usb_path="$(dirname "$vdr")"
                        break
                    fi
                fi
            done

            if [ -n "$usb_path" ] && [ -w "$usb_path/authorized" ]; then
                log "  Intentando USB reset del CH340 en $usb_path..."
                echo 0 > "$usb_path/authorized" 2>/dev/null || true
                sleep 2
                echo 1 > "$usb_path/authorized" 2>/dev/null || true
                date +%s > "$LAST_USB_RESET_FILE"
                # Reset el contador — esperamos que el proximo run vea sensores ok
                echo 0 > "$SENSOR_FAIL_COUNT_FILE"
                log "  USB reset enviado. ArduinoHub re-conectara en ~5-15s."
                RECOVERED_SOMETHING=1
                PROBLEMS="$PROBLEMS usb-reset(CH340)"
            else
                log "  ERROR: No encontre el CH340 (${CH340_VENDOR}:${CH340_PRODUCT}) en sysfs, o sin permiso de escritura."
                send_telegram "🚨 *${HOST_LABEL}*: Todos los sensores caidos y CH340 no aparece en USB. Posible cable suelto, requiere inspeccion fisica."
            fi
        fi
    fi
else
    # Hay al menos un sensor ok — reset counter
    rm -f "$SENSOR_FAIL_COUNT_FILE"
fi

# --- Resumen ---
if [ "$RECOVERED_SOMETHING" = "1" ]; then
    send_telegram "🔧 *${HOST_LABEL}*: Watchdog recuperó:${PROBLEMS}"
fi

log "Watchdog OK"
