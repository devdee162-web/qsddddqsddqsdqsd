@echo off
setlocal
cd /d "%~dp0"

set "VPS=root@151.240.100.86"
set "DEST=/opt/tool_oap_api"

echo === Envoi API vers VPS ===
echo VPS: %VPS%
echo Dossier: %DEST%
echo.
echo Entre le mot de passe root quand demande.
echo.

ssh "%VPS%" "mkdir -p %DEST%"
if errorlevel 1 goto fail

scp "%~dp0discord_api_server.py" "%VPS%:%DEST%/"
if errorlevel 1 goto fail

scp "%~dp0start_discord_api.sh" "%VPS%:%DEST%/"
if errorlevel 1 goto fail

scp "%~dp0install_discord_api_linux.sh" "%VPS%:%DEST%/"
if errorlevel 1 goto fail

scp "%~dp0discord_api.env.linux.example" "%VPS%:%DEST%/"
if errorlevel 1 goto fail

echo.
echo OK fichiers envoyes.
echo.
echo Sur le VPS:
echo   cd /opt/tool_oap_api
echo   cp discord_api.env.linux.example discord_api.env
echo   nano discord_api.env
echo   chmod +x *.sh
echo   ./install_discord_api_linux.sh
echo.
pause
exit /b 0

:fail
echo.
echo ERREUR transfert.
pause
exit /b 1
