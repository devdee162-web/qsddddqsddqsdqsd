@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".env" (
    echo Fichier .env manquant. Copie config.example.env vers .env et ajoute ton token.
    pause
    exit /b 1
)

py -m pip install -r requirements.txt -q
py export_discord.py
pause
