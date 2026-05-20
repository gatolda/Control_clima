#!/usr/bin/env bash
# fleet.sh - Wrapper para administrar la flota de Pis desde tu laptop.
#
# Lee bin/fleet.yml con la lista de Pis y ejecuta deploy/status/health en una o varias.
#
# Uso:
#   bash bin/fleet.sh status                    # estado de todas las Pis
#   bash bin/fleet.sh deploy <cliente>          # deploy a 1 Pi
#   bash bin/fleet.sh deploy all                # deploy a todas
#   bash bin/fleet.sh deploy <cliente> v1.2.0   # deploy de un tag especifico
#   bash bin/fleet.sh ssh <cliente>             # SSH interactivo a una Pi
#   bash bin/fleet.sh logs <cliente>            # tail logs remotos
#
# Ejemplo de fleet.yml:
#   pis:
#     - name: kowen
#       host: 100.90.99.32           # IP Tailscale (o hostname)
#       user: kowen
#     - name: cliente-juan
#       host: 100.x.y.z
#       user: kowen

set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLEET_FILE="${FLEET_FILE:-$REPO_DIR/bin/fleet.yml}"

if [ ! -f "$FLEET_FILE" ]; then
    cat <<EOF
[fleet] No existe $FLEET_FILE
Crealo con el formato:

pis:
  - name: kowen
    host: 100.90.99.32
    user: kowen
  - name: cliente-juan
    host: 100.x.y.z
    user: kowen

(podes usar IPs Tailscale o hostnames .ts.net)
EOF
    exit 1
fi

# Parsear el fleet.yml con Python (mas robusto que awk)
parse_fleet() {
    python3 - <<PYEOF
import yaml, sys, json
try:
    with open("$FLEET_FILE") as f:
        cfg = yaml.safe_load(f) or {}
    print(json.dumps(cfg.get("pis", [])))
except Exception as e:
    print(f"ERROR parseando fleet.yml: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
}

list_pis() {
    parse_fleet | python3 -c "import json, sys; print('\n'.join(p['name'] for p in json.load(sys.stdin)))"
}

get_pi() {
    local name="$1"
    parse_fleet | python3 -c "
import json, sys
pis = json.load(sys.stdin)
for p in pis:
    if p['name'] == '$name':
        print(f\"{p.get('user', 'kowen')}@{p['host']}\")
        sys.exit(0)
sys.exit(1)
"
}

# Acciones
cmd_status() {
    echo "=== Fleet Status ==="
    parse_fleet | python3 -c "
import json, sys
pis = json.load(sys.stdin)
for p in pis:
    print(f\"{p['name']:20} {p.get('user', 'kowen')}@{p['host']}\")
" | while read line; do
        name=$(echo "$line" | awk '{print $1}')
        target=$(echo "$line" | awk '{print $2}')
        printf "%-20s " "$name"
        if ssh -o BatchMode=yes -o ConnectTimeout=5 "$target" 'curl -sf --max-time 3 http://127.0.0.1:5000/health > /dev/null && echo OK || echo FAIL' 2>/dev/null; then
            :
        else
            echo "UNREACHABLE"
        fi
    done
}

cmd_deploy() {
    local target_name="${1:-}"
    local ref="${2:-origin/main}"
    if [ -z "$target_name" ]; then
        echo "Uso: bash bin/fleet.sh deploy <cliente|all> [tag]"
        echo "Pis disponibles:"
        list_pis | sed 's/^/  - /'
        exit 1
    fi

    if [ "$target_name" = "all" ]; then
        for name in $(list_pis); do
            echo
            echo "=== Deploy a $name ==="
            deploy_one "$name" "$ref" || echo "  Deploy a $name fallo, continuando con el resto"
        done
    else
        deploy_one "$target_name" "$ref"
    fi
}

deploy_one() {
    local name="$1"
    local ref="${2:-origin/main}"
    local target
    target=$(get_pi "$name") || { echo "Pi '$name' no esta en fleet.yml"; return 1; }
    echo "  Conectando a $target..."
    ssh -o BatchMode=yes -o ConnectTimeout=10 "$target" "cd ~/proyectos/Control_clima && bash bin/deploy.sh $ref"
}

cmd_ssh() {
    local name="${1:-}"
    if [ -z "$name" ]; then
        echo "Uso: bash bin/fleet.sh ssh <cliente>"
        list_pis | sed 's/^/  - /'
        exit 1
    fi
    local target
    target=$(get_pi "$name") || { echo "Pi '$name' no esta en fleet.yml"; exit 1; }
    exec ssh "$target"
}

cmd_logs() {
    local name="${1:-}"
    if [ -z "$name" ]; then
        echo "Uso: bash bin/fleet.sh logs <cliente>"
        exit 1
    fi
    local target
    target=$(get_pi "$name") || { echo "Pi '$name' no esta en fleet.yml"; exit 1; }
    exec ssh "$target" "tail -f /var/log/greenhouse.log"
}

# Dispatcher
case "${1:-status}" in
    status)         cmd_status ;;
    deploy)         shift; cmd_deploy "$@" ;;
    ssh)            shift; cmd_ssh "$@" ;;
    logs)           shift; cmd_logs "$@" ;;
    list)           list_pis ;;
    *)
        echo "Comandos: status | deploy <name|all> [ref] | ssh <name> | logs <name> | list"
        exit 1
        ;;
esac
