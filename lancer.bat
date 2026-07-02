@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist "..\.env" (
    copy /Y "..\.env" ".env" >nul
) else if not exist ".env" (
    if exist "..\config.example.env" (
        copy /Y "..\config.example.env" ".env" >nul
        echo .env cree depuis config.example.env - configure ton token !
    )
)

if exist "..\accounts.json" (
    copy /Y "..\accounts.json" "accounts.json" >nul
)

if not exist ".env" (
    echo Fichier .env manquant.
    echo Copie ton .env dans: %~dp0
    pause
    exit /b 1
)

TOOL_OAP.exe
pause
