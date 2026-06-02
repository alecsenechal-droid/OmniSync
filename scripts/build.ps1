$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path .venv\Scripts\activate.bat)) {
  py -3 -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip build pyinstaller
pip install -e .
python -m playwright install chromium
pyinstaller omnisync.spec --noconfirm
Write-Host ""
Write-Host "Build termine: dist\OmniSync\OmniSync.exe"
Write-Host "Copiez aussi le dossier playwright si besoin sur la machine cible."
