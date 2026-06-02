# OmniSync — Boot Context
updated: 2026-06-02 | 20 étapes validées | 14 en attente

## État
---
**Omnivox** : stable — DA=2534700, mot de passe keyring OS, headless=true.
**Google Calendar** : stable — calendrier "OmniSync" en production.
**Moodle** : TOKEN VALIDE — 19 travaux au dernier run.
**Notifications** : actives — `omnisyncqc@gmail.com` → `alec.senechal@gmail.com`.
**Doctor** : 15/15 PASS ✅
**run --scrape-only** : PASS — 82 events Omnivox + 19 Moodle, `[OK] Aucune anomalie` ✅
**Git repo** : pushé sur `https://github.com/alecsenechal-droid/OmniSync` (public) — commit `c7e533f`
---
### 1. Repo GitHub public en ligne (commit c7e533f)
- `.gitignore` mis à jour : CLAUDE.md exclu (données personnelles)
- `README-CREDENTIALS.md` : instructions distribution `credentials.json` via Releases

## Architecture
```
Omnivox(Playwright) + Moodle(REST) + Actualités → SQLite(%LOCALAPPDATA%\OmniSync) → Google Calendar
```

## Modules critiques
- `omnivox_engine` : Playwright — scraping LEA/Omnivox (sélecteurs figés)
- `scraper/moodle_engine` : REST wstoken Moodle + SSO SAML2
- `sync` : Orchestrateur pipeline principal
- `calendar/google` : Google Calendar API — CRUD events
- `storage/db` : SQLite — source de vérité locale

## Règles figées (JAMAIS modifier sans demande explicite)
- `SchoolEvent` + `_dedupe()` : schéma immuable
- Sélecteur LEA : `table#tabListeTravEtu tr` — sans classe CSS, jamais `.LigneListTrav1`
- Moodle : bloc `try/except` SÉPARÉ de Playwright, `MoodleMFARequired` en PREMIER
- `input[name='passwd']` : attendre `state="visible"` (SPA AAD, invisible au chargement)
- `channel="chrome"` → page blanche. `wait_for_load_state` inopérant sur SPA AAD.
- Clés `config.toml`, `pyproject.toml`, sélecteurs `omnivox_engine` : figés

## Risques actifs
- **Token Moodle** : expiration inconnue → Edge F12 → Network → launch.php → `run.bat token-moodle`
- **Sélecteurs Omnivox** : fragiles aux mises à jour du portail Omnivox

## Prochaines étapes
- **Télécharger credentials.json** — console.cloud.google.com/apis/credentials → OmniSync Desktop → ⬇
- **Créer GitHub Release v1.0-beta** — attacher credentials.json, tag v1.0-beta, publier
- **Intégrer setup_google.ps1** — script automatisation OAuth dans `scripts/setup_google.ps1`
- **Beta testeur Ste-Foy ou Garneau** — PRIORITÉ SUIVANTE (dès credentials distribués)
- **PyInstaller .exe** — 0 Python requis pour l'utilisateur

## Commandes
```powershell
cd C:\Users\alecs\Desktop\Omnisync
.\run.bat doctor                  # vérifier l'état complet
.\run.bat run --scrape-only       # scraper sans toucher Calendar
.\run.bat run --calendar-dry-run  # scraper + valider sans écrire Calendar
.\run.bat run                     # pipeline complet
python scripts/build_memory.py     # régénérer ce fichier
```