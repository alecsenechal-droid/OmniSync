@echo off
setlocal
cd /d "%~dp0"

if not exist .venv (
    echo Creation de l'environnement virtuel Python...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo [ERREUR] Impossible de creer l'environnement Python.
        echo Assurez-vous d'avoir Python 3.10+ installe.
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

echo Mise a jour de pip...
python -m pip install --upgrade pip --quiet

echo Installation des dependances OmniSync...
pip install -e . --quiet
if errorlevel 1 (
    echo [ERREUR] Installation echouee. Verifiez votre connexion internet.
    exit /b 1
)

echo Telechargement de Chromium ^(navigateur, ~170MB -- peut prendre 1-2 min^)...
python -m playwright install chromium
if errorlevel 1 (
    echo [ERREUR] Installation de Chromium echouee.
    exit /b 1
)

:: ── Credentials Google Calendar ──────────────────────────────────────────────
set CREDS_DIR=%LOCALAPPDATA%\OmniSync
set CREDS_FILE=%CREDS_DIR%\credentials.json
set CREDS_URL=https://github.com/alecsenechal-droid/OmniSync/releases/latest/download/credentials.json

if exist "%CREDS_FILE%" (
    echo credentials.json Google deja present -- OK.
) else (
    echo Telechargement de credentials.json Google Calendar...
    if not exist "%CREDS_DIR%" mkdir "%CREDS_DIR%"
    powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%CREDS_URL%' -OutFile '%CREDS_FILE%' -UseBasicParsing -ErrorAction Stop; Write-Host 'credentials.json telecharge.' } catch { Write-Host '[AVERTISSEMENT] Impossible de telecharger credentials.json : ' + $_.Exception.Message; exit 0 }"
    if not exist "%CREDS_FILE%" (
        echo.
        echo [AVERTISSEMENT] credentials.json introuvable apres telechargement.
        echo Recuperez-le manuellement depuis :
        echo   %CREDS_URL%
        echo et placez-le dans : %CREDS_DIR%\
        echo Vous pourrez quand meme utiliser OmniSync en mode --scrape-only.
        echo.
    )
)
:: ─────────────────────────────────────────────────────────────────────────────

echo.
echo Installation terminee.
