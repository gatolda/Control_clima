#!/bin/bash
# Setea TELEGRAM_BOT_TOKEN de forma segura. Mismo patron.
set -euo pipefail
ENV_FILE="$HOME/proyectos/Control_clima/.env"
BACKUP="/tmp/.env.bak.$$"
trap 'rm -f "$BACKUP"' EXIT

echo "Pegá tu Telegram Bot Token y presioná Enter:"
echo "(no vas a ver lo que tipeás — es a propósito)"
read -rs BOT_TOKEN
echo

if [[ ! "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]{20,}$ ]]; then
    echo "❌ El token no parece válido."
    echo "   Largo: ${#BOT_TOKEN} (esperaba 40-50)"
    echo "   Formato esperado: <bot_id>:<string-largo> (ej. 1234567890:AAH...)"
    unset BOT_TOKEN
    exit 1
fi

cp "$ENV_FILE" "$BACKUP"
sed -i '/^TELEGRAM_BOT_TOKEN=/d' "$ENV_FILE"
printf 'TELEGRAM_BOT_TOKEN=%s\n' "$BOT_TOKEN" >> "$ENV_FILE"
unset BOT_TOKEN

echo "✅ Token actualizado en .env"
sudo systemctl restart greenhouse-telegram-bot.service
echo "✅ greenhouse-telegram-bot.service reiniciado"
sudo systemctl restart greenhouse-watchdog.service 2>/dev/null && echo "✅ greenhouse-watchdog.service reiniciado" || true
echo "   (backup temporal eliminado de /tmp)"
