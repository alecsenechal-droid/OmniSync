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

echo.
echo Installation terminee.
