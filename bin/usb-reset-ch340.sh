#!/usr/bin/env bash
# Resetea el CH340 USB-serial (1a86:7523) escribiendo en sysfs.
# Equivalente a desenchufar y volver a enchufar el cable USB del Arduino.
#
# Requiere root (escritura a /sys/bus/usb/devices/.../authorized). Se invoca
# desde el bot de Telegram via `sudo bin/usb-reset-ch340.sh` (kowen tiene
# NOPASSWD sudo).
#
# Usado por:
#   - Bot Telegram /usb_reset (recovery remoto manual)
#   - Implicito en bin/tailscale-watchdog.sh (recovery automatico cuando
#     todos los sensores quedan sin_datos por >=2 chequeos)

set -euo pipefail

CH340_VENDOR="1a86"
CH340_PRODUCT="7523"

for vdr in /sys/bus/usb/devices/*/idVendor; do
    [ -f "$vdr" ] || continue
    [ "$(cat "$vdr" 2>/dev/null)" = "$CH340_VENDOR" ] || continue
    prod="$(dirname "$vdr")/idProduct"
    [ -f "$prod" ] && [ "$(cat "$prod" 2>/dev/null)" = "$CH340_PRODUCT" ] || continue
    path="$(dirname "$vdr")"
    if [ -w "$path/authorized" ]; then
        echo "Reseteando CH340 en $path..."
        echo 0 > "$path/authorized"
        sleep 2
        echo 1 > "$path/authorized"
        echo "OK: USB reset enviado al CH340"
        exit 0
    fi
done

echo "ERROR: CH340 (${CH340_VENDOR}:${CH340_PRODUCT}) no encontrado en USB. Cable suelto?" >&2
exit 1
