@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist "dist\TOOL_OAP.exe" (
    start "" /wait "dist\TOOL_OAP.exe"
    exit /b 0
)

if exist "TOOL_OAP.exe" (
    start "" /wait "TOOL_OAP.exe"
    exit /b 0
)

py -m pip install -r requirements.txt -q 2>nul
py export_discord.py
pause
