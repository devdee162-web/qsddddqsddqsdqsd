@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "GIT="
where git >nul 2>&1 && set "GIT=git"
if not defined GIT if exist "C:\Program Files\Git\cmd\git.exe" set "GIT=C:\Program Files\Git\cmd\git.exe"
if not defined GIT (
    echo Git non installe. Installe-le: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo === Push TOOL OAP sur GitHub ===
echo Repo: devdee162-web/qsddddqsddqsdqsd
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
if /I not "%CONFIRM%"=="o" (
    echo Annule.
    pause
    exit /b 0
)

"%GIT%" commit -m "Initial commit TOOL OAP" 2>nul
if errorlevel 1 (
    "%GIT%" commit -m "Update TOOL OAP"
)

"%GIT%" push -u origin main
if errorlevel 1 (
    echo.
    echo Si erreur auth, connecte-toi avec GitHub Desktop ou:
    echo gh auth login
    pause
    exit /b 1
)

echo.
echo Tag release v1.0.0...
"%GIT%" tag v1.0.0 2>nul
"%GIT%" push origin v1.0.0 2>nul

echo.
echo OK ! GitHub Actions va compiler TOOL_OAP.exe automatiquement.
echo Releases: https://github.com/devdee162-web/qsddddqsddqsdqsd/releases
pause
