@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === Compilation TOOL OAP en EXE ===

if not exist "venv\Scripts\python.exe" (
    py -m venv venv
)

call venv\Scripts\activate.bat
pip install -r requirements.txt -q
pip install pyinstaller pillow -q

python -c "from PIL import Image; img=Image.open('assets/icon.png'); img.save('assets/icon.ico', format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])"
pyinstaller --noconfirm --clean TOOL_OAP.spec

if exist "dist\TOOL_OAP.exe" (
    if exist ".env" copy /Y ".env" "dist\.env" >nul
    if exist "accounts.json" copy /Y "accounts.json" "dist\accounts.json" >nul
    if exist "config.example.env" copy /Y "config.example.env" "dist\config.example.env" >nul
    copy /Y "lancer.bat" "dist\lancer.bat" >nul
    echo OK: dist\TOOL_OAP.exe
) else (
    echo ERREUR: compilation echouee.
)
