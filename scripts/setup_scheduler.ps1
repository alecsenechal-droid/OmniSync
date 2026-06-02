# OmniSync — Planificateur de tâche Windows
# Crée une tâche qui tourne tous les jours à 5h AM, avec réveil automatique de l'ordi.
# Exécuter en tant qu'administrateur: clic droit > "Exécuter en tant qu'administrateur"

$TaskName  = "OmniSync - Sync quotidien"
$ScriptDir = Split-Path -Parent $PSScriptRoot
$RunBat    = Join-Path $ScriptDir "run.bat"

if (-not (Test-Path $RunBat)) {
    Write-Host "ERREUR: run.bat introuvable dans $ScriptDir" -ForegroundColor Red
    exit 1
}

# Supprimer la tâche existante si elle existe
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Ancienne tâche supprimée."
}

# Créer la tâche
$Action  = New-ScheduledTaskAction -Execute "cmd.exe" `
           -Argument "/c `"$RunBat`" run" `
           -WorkingDirectory $ScriptDir

$Trigger = New-ScheduledTaskTrigger -Daily -At "05:00"

$Settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -RunOnlyIfNetworkAvailable

$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName  $TaskName `
    -Action    $Action `
    -Trigger   $Trigger `
    -Settings  $Settings `
    -Principal $Principal `
    -Description "Sync Omnivox → Google Calendar. Lance run.bat tous les jours à 5h AM avec réveil automatique." `
    | Out-Null

Write-Host ""
Write-Host "✅ Tâche '$TaskName' créée avec succès!" -ForegroundColor Green
Write-Host ""
Write-Host "  Heure     : 5h00 AM tous les jours"
Write-Host "  Réveil PC : Oui (mode veille → le PC se réveille, sync, rendort)"
Write-Host "  Script    : $RunBat"
Write-Host ""
Write-Host "IMPORTANT: Pour que le réveil fonctionne, l'ordi doit être en VEILLE (pas éteint)."
Write-Host "           Dans les paramètres d'alimentation, activer 'Autoriser les minuteries de réveil'."
Write-Host ""
Write-Host "Pour vérifier: Ouvrir le Planificateur de tâches Windows et chercher '$TaskName'"
