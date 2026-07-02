@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === API Discord TOOL OAP (VM) ===
echo.
echo Si les clients affichent "VM indisponible", lance open_discord_api_firewall.bat en admin.
echo.

if not exist "discord_api.env" (
    echo discord_api.env introuvable, creation automatique...
    if exist ".env" (
        if exist "venv\Scripts\python.exe" (
            venv\Scripts\python setup_discord_api_env.py
        ) else (
            py setup_discord_api_env.py
        )
    )
    if not exist "discord_api.env" (
        if exist "discord_api.env.example" (
            copy /Y "discord_api.env.example" "discord_api.env" >nul
            echo Fichier cree depuis discord_api.env.example
            echo Ouvre discord_api.env et remplis DISCORD_TOKEN + DISCORD_API_KEY.
            pause
            exit /b 1
        )
        echo ERREUR: impossible de creer discord_api.env
        pause
        exit /b 1
    )
)

if exist "venv\Scripts\python.exe" (
    venv\Scripts\python discord_api_server.py
) else (
    py discord_api_server.py
)

pause
