@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "GIT="
where git >nul 2>&1 && set "GIT=git"
if not defined GIT if exist "C:\Program Files\Git\cmd\git.exe" set "GIT=C:\Program Files\Git\cmd\git.exe"
if not defined GIT if exist "C:\Program Files\Git\bin\git.exe" set "GIT=C:\Program Files\Git\bin\git.exe"
if not defined GIT (
    echo Git non installe.
    pause
    exit /b 1
)

set "GIT_NAME=devdee162-web"
set "GIT_EMAIL=devdee162-web@users.noreply.github.com"
set "GIT_COMMIT=-c user.name=%GIT_NAME% -c user.email=%GIT_EMAIL%"

echo === Push TOOL OAP sur GitHub ===
echo Compte attendu: %GIT_NAME%
echo.

if not exist ".git" (
    "%GIT%" init
    "%GIT%" branch -M main
)

"%GIT%" remote remove origin >nul 2>&1
"%GIT%" remote add origin https://github.com/devdee162-web/qsddddqsddqsdqsd.git

"%GIT%" add .
"%GIT%" status

echo.
set /p CONFIRM=Commit et push ? (o/n): 
if /I not "%CONFIRM%"=="o" exit /b 0

"%GIT%" %GIT_COMMIT% commit -m "Update TOOL OAP" 2>nul
if errorlevel 1 (
    echo Rien de nouveau a committer ou commit deja fait.
)

echo.
echo Push vers GitHub...
"%GIT%" push -u origin main
if errorlevel 1 (
    echo.
    echo ERREUR 403 ? Mauvais compte GitHub enregistre.
    echo.
    echo Solution 1 - Effacer les identifiants Windows:
    echo   Panneau de configuration ^> Gestionnaire d'identifiants
    echo   ^> Identifiants Windows ^> supprimer git:https://github.com
    echo   Puis relance ce script et connecte-toi avec %GIT_NAME%
    echo.
    echo Solution 2 - Token GitHub:
    echo   github.com ^> Settings ^> Developer settings ^> Tokens
    echo   git push https://TOKEN@github.com/devdee162-web/qsddddqsddqsdqsd.git main
    pause
    exit /b 1
)

"%GIT%" tag -f v1.0.0 2>nul
"%GIT%" push -f origin v1.0.0 2>nul

echo.
echo OK: https://github.com/devdee162-web/qsddddqsddqsdqsd
pause
