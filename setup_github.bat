@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === Configuration GitHub pour TOOL OAP ===
echo.

where git >nul 2>&1
if errorlevel 1 (
    echo Git n'est pas installe.
    echo Telecharge-le ici: https://git-scm.com/download/win
    echo Puis relance ce script.
    pause
    exit /b 1
)

where gh >nul 2>&1
if errorlevel 1 (
    echo GitHub CLI ^(gh^) non installe - optionnel.
    echo https://cli.github.com/
    echo.
)

if not exist ".git" (
    git init
    git branch -M main
)

git add .
git status

echo.
set /p REPO=Nom du repo GitHub ^(ex: mon-compte/tool-oap^): 
if "%REPO%"=="" (
    echo Annule.
    pause
    exit /b 1
)

findstr /V "GITHUB_REPO=" .env > .env.tmp 2>nul
move /Y .env.tmp .env >nul 2>nul
echo GITHUB_REPO=%REPO%>> .env
echo AUTO_UPDATE_ON_START=true>> .env

echo.
echo Etapes suivantes:
echo   1. Creer le repo sur https://github.com/new
echo   2. git remote add origin https://github.com/%REPO%.git
echo   3. git commit -m "Initial commit TOOL OAP"
echo   4. git push -u origin main
echo   5. git tag v1.0.0 ^&^& git push origin v1.0.0
echo.
echo GITHUB_REPO=%REPO% ajoute dans .env
pause
