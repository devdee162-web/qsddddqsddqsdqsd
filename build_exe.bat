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

echo Nouvelle version...
python publish_github.py bump

echo Integration config dans l'exe...
python embed_secrets.py

python -c "from PIL import Image; img=Image.open('assets/icon.png'); img.save('assets/icon.ico', format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])"
pyinstaller --noconfirm --clean TOOL_OAP.spec

if not exist "dist\TOOL_OAP.exe" (
    echo ERREUR: compilation echouee.
    pause
    exit /b 1
)

copy /Y "lancer.bat" "dist\lancer.bat" >nul
echo OK: dist\TOOL_OAP.exe

echo.
echo === Publication GitHub ===
python publish_github.py publish
echo.
pause
