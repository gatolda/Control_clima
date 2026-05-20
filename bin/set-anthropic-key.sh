#!/bin/bash
# Setea ANTHROPIC_API_KEY de forma segura: lee de stdin sin echo, valida,
# limpia previas, appendea, reinicia el servicio. Backup va a /tmp y se
# borra al salir (los backups en plain text con secrets son riesgo).
set -euo pipefail
ENV_FILE="$HOME/proyectos/Control_clima/.env"
BACKUP="/tmp/.env.bak.$$"
trap 'rm -f "$BACKUP"' EXIT

echo "Pegá tu API key de Anthropic y presioná Enter:"
echo "(no vas a ver lo que tipeás — es a propósito)"
read -rs API_KEY
echo

if [[ ${#API_KEY} -lt 50 ]] || [[ "$API_KEY" != sk-ant-api* ]]; then
    echo "❌ La key no parece válida."
    echo "   Largo: ${#API_KEY} (esperaba 100+)"
    echo "   Prefijo: ${API_KEY:0:12}... (esperaba sk-ant-api*)"
    unset API_KEY
    exit 1
fi

cp "$ENV_FILE" "$BACKUP"
sed -i '/^ANTHROPIC_API_KEY=/d' "$ENV_FILE"
printf 'ANTHROPIC_API_KEY=%s\n' "$API_KEY" >> "$ENV_FILE"
unset API_KEY

echo "✅ Key actualizada"
sudo systemctl restart greenhouse.service
echo "✅ greenhouse.service reiniciado"
echo "   (backup temporal eliminado de /tmp)"
