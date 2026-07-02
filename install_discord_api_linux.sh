#!/bin/bash
# Installation API Discord sur VPS Linux (Ubuntu/Debian)
set -e
cd "$(dirname "$0")"

echo "=== Installation API Discord TOOL OAP (Linux) ==="

if ! command -v python3 >/dev/null 2>&1; then
    echo "Installation de python3..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -qq
        sudo apt-get install -y python3 python3-venv
    else
        echo "Installe python3 manuellement puis relance ce script."
        exit 1
    fi
fi

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
# Pas de pip requis: discord_api_server.py utilise la bibliotheque standard.

if [ ! -f "discord_api.env" ]; then
    cp discord_api.env.example discord_api.env
    echo ""
    echo "IMPORTANT: edite discord_api.env :"
    echo "  - DISCORD_TOKEN"
    echo "  - DISCORD_API_KEY (meme valeur que sur ton PC)"
    echo "  - DISCORD_API_PUBLISH_DIR (optionnel, ex: /srv/tool_oap)"
    echo ""
    echo "Puis relance: ./install_discord_api_linux.sh"
    exit 0
fi

chmod +x start_discord_api.sh

echo "Ouverture du port 8780..."
if command -v ufw >/dev/null 2>&1; then
    sudo ufw allow 8780/tcp || true
    echo "UFW: port 8780/tcp autorise"
elif command -v firewall-cmd >/dev/null 2>&1; then
    sudo firewall-cmd --permanent --add-port=8780/tcp
    sudo firewall-cmd --reload
    echo "firewalld: port 8780/tcp autorise"
else
    echo "Aucun pare-feu detecte (ufw/firewalld). Ouvre le port 8780 dans le panneau de ton hebergeur VPS."
fi

SERVICE_FILE="/etc/systemd/system/tool-oap-discord-api.service"
INSTALL_DIR="$(pwd)"
USER_NAME="$(whoami)"

sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=TOOL OAP Discord API
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/discord_api_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable tool-oap-discord-api
sudo systemctl restart tool-oap-discord-api

echo ""
echo "OK: service demarre."
echo "Statut: sudo systemctl status tool-oap-discord-api"
echo "Logs:   sudo journalctl -u tool-oap-discord-api -f"
echo ""
echo "Test depuis ton PC:"
echo "  curl http://TON_IP_VPS:8780/api/discord/status"
echo ""
