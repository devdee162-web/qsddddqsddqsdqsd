#!/bin/bash
# Lance l'API Discord TOOL OAP sur VPS Linux
set -e
cd "$(dirname "$0")"

echo "=== API Discord TOOL OAP (VPS Linux) ==="

if [ ! -f "discord_api.env" ]; then
    echo "discord_api.env introuvable."
    if [ -f "discord_api.env.example" ]; then
        cp discord_api.env.example discord_api.env
        echo "Fichier cree: edite discord_api.env puis relance ce script."
        exit 1
    fi
    echo "ERREUR: discord_api.env.example manquant."
    exit 1
fi

PYTHON="python3"
if [ -x "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
fi

exec "$PYTHON" discord_api_server.py
