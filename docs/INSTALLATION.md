# Installation Windows

## Option simple (recommandee)

1. Installer Python 3.10 ou plus recent (cocher Add to PATH).
2. Telecharger ou cloner le repo OmniSync.
3. Double-cliquer **`setup.bat`** (installe + assistant + doctor).

Alternative manuelle : `install.bat` puis `run.bat init`.

5. Verifier:

```powershell
run.bat doctor
```

6. Tester le mode demo sans modifier Google Calendar:

```powershell
run.bat run --dry-run
```

7. Tester Omnivox reellement sans modifier Google Calendar:

```powershell
run.bat run --calendar-dry-run
```

Si Omnivox demande une validation MFA, relancer en mode visible:

```powershell
set HEADLESS=false
set OMNISYNC_MFA_WAIT_SECONDS=120
run.bat run --calendar-dry-run
```

## Planification a 05:00

```powershell
run.bat scheduler install --time 05:00
```

Voir l'etat:

```powershell
run.bat scheduler status
```

Supprimer:

```powershell
run.bat scheduler remove
```

## Variables utiles pour developpement

- `OMNISYNC_HOME`: dossier runtime alternatif.
- `OMNISYNC_GOOGLE_CREDENTIALS`: chemin vers `credentials.json`.
- `OMNISYNC_SYNC_PAST_EVENTS=true`: autorise la sync d'evenements passes.
