@echo off
setlocal
cd /d "%~dp0"

echo.
echo ============================================
echo   OmniSync -- Premier lancement
echo ============================================
echo.

:: [1/3] Verifier que Python est installe
py -3 --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python 3 n'est pas installe ou pas dans PATH.
    echo.
    echo Telechargez Python depuis : https://www.python.org/downloads/
    echo Important : cochez "Add Python to PATH" lors de l'installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('py -3 --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
if %PY_MAJOR% LSS 3 goto :py_old
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 10 goto :py_old
goto :py_ok
:py_old
echo [ERREUR] Python %PYVER% detecte, mais OmniSync requiert Python 3.10 ou plus recent.
echo.
echo Telechargez Python 3.12 depuis : https://www.python.org/downloads/
echo Important : cochez "Add Python to PATH" lors de l'installation.
echo.
pause
exit /b 1
:py_ok
for /f "delims=" %%p in ('py -3 -c "import sys; print(sys.executable)" 2^>^&1') do set PYPATH=%%p
echo [1/3] Python %PYVER% detecte.
echo          %PYPATH%

if not exist .venv\Scripts\activate.bat (
    echo [2/3] Installation des dependances (2-3 minutes, une seule fois)...
    echo.
    call install.bat
    if errorlevel 1 (
        echo.
        echo [ERREUR] L'installation a echoue.
        echo Verifiez votre connexion internet et relancez setup.bat
        echo.
        pause
        exit /b 1
    )
) else (
    echo [2/3] Dependances deja installees.
    call .venv\Scripts\activate.bat
)

echo.
echo [3/3] Configuration de ton compte...
echo.
python -m omnisync init
if errorlevel 1 (
    echo.
    echo [ERREUR] La configuration a echoue.
    echo Relance : setup.bat  ou  run.bat init
    echo.
    pause
    exit /b 1
)

echo.
python -m omnisync doctor
set DOCTOR_CODE=%errorlevel%

echo.
if %DOCTOR_CODE% EQU 0 (
    echo   Tout est pret ! Lance ta premiere synchro :
    echo.
    echo     run.bat run --calendar-dry-run    ^<-- apercu sans modifier ton calendrier
    echo     run.bat run                       ^<-- synchronisation complete
) else (
    echo   Quelques elements restent a configurer ^(voir [!!] ci-dessus^).
    echo   Une fois corriges, lance :
    echo.
    echo     run.bat doctor                    ^<-- verifier que tout est OK
    echo     run.bat run --calendar-dry-run
)
echo.
pause
