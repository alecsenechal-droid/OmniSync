# Guide utilisateur OmniSync (5 minutes)

OmniSync est un programme **sur votre ordinateur**. Il lit Omnivox et met à jour **votre** Google Calendar. Rien n'est envoyé sur un serveur OmniSync.

## 1. Télécharger

- Depuis la landing page : bouton **Télécharger pour Windows** (futur `.exe`) ou lien GitHub.
- Dézippez le dossier `Omnisync` sur le Bureau ou dans `Documents`.

## 2. Installer (une fois)

**Prérequis :** [Python 3.10+](https://www.python.org/downloads/) coché « Add to PATH » à l'installation.

Double-cliquez **`setup.bat`** ou, dans PowerShell :

```powershell
cd chemin\vers\Omnisync
.\setup.bat
```

L'assistant demande :

- votre **DA** Omnivox ;
- votre **mot de passe** (stocké dans le coffre Windows, pas en clair) ;
- votre **cégep** (ex. `climoilou`, code `CLI`) ;
- l'heure de sync (défaut **05:00**) ;
- connexion **Google Calendar** (navigateur) ;
- activation de la **tâche planifiée** quotidienne.

## 3. Google Calendar

1. Créez un projet sur [Google Cloud Console](https://console.cloud.google.com/) (usage personnel).
2. Activez l'API **Google Calendar**.
3. Créez des identifiants **OAuth bureau** → téléchargez `credentials.json`.
4. Copiez-le dans :

   `%LOCALAPPDATA%\OmniSync\credentials.json`

5. Si l'assistant ne l'a pas fait : `run.bat auth-google`.

Google affichera « application non vérifiée » : **Avancé → Accéder** (normal pour un outil communautaire).

## 4. Vérifier

```powershell
run.bat doctor
run.bat run --calendar-dry-run
```

Si Omnivox demande une validation sur le téléphone (MFA) :

```powershell
set HEADLESS=false
set OMNISYNC_MFA_WAIT_SECONDS=120
run.bat run --calendar-dry-run
```

## 5. Sync réelle

```powershell
run.bat run
```

Ouvrez Google Calendar : événements `[REMISE]`, `[EXAM]`, etc.

## 6. Chaque matin

La tâche **OmniSync Daily Sync** tourne à 5h (si le PC est allumé). Pour vérifier :

```powershell
run.bat scheduler status
```

## Dépannage rapide

| Problème | Action |
|----------|--------|
| DA / mot de passe | `run.bat init` |
| Google | `credentials.json` + `run.bat auth-google` |
| MFA | `HEADLESS=false` + `OMNISYNC_MFA_WAIT_SECONDS=120` |
| Logs / captures | `%LOCALAPPDATA%\OmniSync\logs\` |
