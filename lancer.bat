@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist "dist\TOOL_OAP.exe" (
    cd dist
)

if exist "..\.env" copy /Y "..\.env" ".env" >nul
if exist "..\accounts.json" copy /Y "..\accounts.json" "accounts.json" >nul

if exist "TOOL_OAP.exe" (
    start "" /wait "TOOL_OAP.exe"
    exit /b 0
)

if not exist ".env" (
    if exist "config.example.env" copy /Y "config.example.env" ".env" >nul
)

py -m pip install -r requirements.txt -q 2>nul
py export_discord.py
pause
