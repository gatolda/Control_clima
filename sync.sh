#!/bin/bash

echo "🔄 Sincronizando proyecto con GitHub..."

# Ir a la carpeta del proyecto
cd /home/kowen/proyectos/Control_clima || exit

# Traer cambios desde GitHub
echo "📥 Haciendo pull..."
git pull origin main

# Agregar cambios nuevos
echo "📤 Haciendo push..."
git add .
git commit -m "Auto-sync: cambios desde Raspberry Pi"
git push origin main

echo "✅ Sincronización completa."

