#!/bin/bash
# rotate-auth.sh — rota SECRET_KEY (auto) + ADMIN_PASSWORD (manual).
# Actualiza .env + hash en DB del usuario admin. Mismo patron seguro.
set -euo pipefail
ENV_FILE="$HOME/proyectos/Control_clima/.env"
BACKUP="/tmp/.env.bak.$$"
trap 'rm -f "$BACKUP"' EXIT

echo "Pegá la NUEVA password para admin (mínimo 12 caracteres):"
read -rs NEW_PASS
echo
echo "Confirmá la password (pegá de nuevo):"
read -rs NEW_PASS_CONFIRM
echo

[[ "$NEW_PASS" != "$NEW_PASS_CONFIRM" ]] && { echo "❌ Las passwords no coinciden"; unset NEW_PASS NEW_PASS_CONFIRM; exit 1; }
[[ ${#NEW_PASS} -lt 12 ]] && { echo "❌ Password muy corta (${#NEW_PASS}, min 12)"; unset NEW_PASS NEW_PASS_CONFIRM; exit 1; }
unset NEW_PASS_CONFIRM

NEW_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

cp "$ENV_FILE" "$BACKUP"
sed -i '/^SECRET_KEY=/d;/^ADMIN_PASSWORD=/d' "$ENV_FILE"
printf 'SECRET_KEY=%s\n' "$NEW_SECRET" >> "$ENV_FILE"
printf 'ADMIN_PASSWORD=%s\n' "$NEW_PASS" >> "$ENV_FILE"
unset NEW_SECRET

# Update hash en DB pasando password via env var (no command-line arg)
cd "$HOME/proyectos/Control_clima"
_NEW_PASS="$NEW_PASS" ./.venv/bin/python -c '
import os, sqlite3, sys
from werkzeug.security import generate_password_hash
conn = sqlite3.connect("data/greenhouse.db")
new_hash = generate_password_hash(os.environ["_NEW_PASS"])
cur = conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (new_hash, os.environ.get("_ADMIN_USER", "admin")))
conn.commit()
if cur.rowcount == 0:
    print("❌ usuario admin no encontrado en DB"); sys.exit(1)
print(f"✅ hash en DB actualizado (rowcount={cur.rowcount})")
conn.close()
'
unset NEW_PASS

echo "✅ SECRET_KEY rotada (todas las sesiones activas quedan invalidadas)"
echo "✅ ADMIN_PASSWORD rotada"
sudo systemctl restart greenhouse.service
echo "✅ greenhouse.service reiniciado"
echo "   (backup temporal del .env eliminado de /tmp)"
