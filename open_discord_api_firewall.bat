@echo off
chcp 65001 >nul
:: Ouvre le port 8780 sur la VM (lancer en administrateur)
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
    echo Relance ce fichier en clic droit ^> Executer en tant qu'administrateur
    pause
    exit /b 1
)

netsh advfirewall firewall delete rule name="TOOL OAP Discord API" >nul 2>&1
netsh advfirewall firewall add rule name="TOOL OAP Discord API" dir=in action=allow protocol=TCP localport=8780

echo OK: port TCP 8780 ouvert sur cette VM.
echo Les clients peuvent joindre: http://IP_DE_LA_VM:8780
pause
