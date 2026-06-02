# OmniSync — Boot Context
updated: 2026-06-02 | 17 étapes validées | 16 en attente

## État
---
**Omnivox** : stable — DA=2534700, mot de passe keyring OS, headless=true.
**Google Calendar** : stable — calendrier "OmniSync" en production.
**Moodle** : TOKEN VALIDE — 19 travaux au dernier run.
**Notifications** : actives — `omnisyncqc@gmail.com` → `alec.senechal@gmail.com`.
**Doctor** : 15/15 PASS ✅
**run --scrape-only** : PASS — 82 events Omnivox + 19 Moodle, `[OK] Aucune anomalie` ✅
**Git repo** : commit `a44f243` local, remote configuré, push en attente (repo GitHub à créer)
---
### 1. Audit documentaire complet OmniSync
- Scraping : 9 pages visitées, 10 modules, données récupérées vs ignorées documentées
- Sync Calendar : CRUD, RRULE, rappels, couleurs, déduplication documentés

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
- **Créer repo GitHub** — github.com → New repository `alecsenechal/omnisync` (public, vide) → `git push -u origin main`
- **Distribuer credentials.json** — GitHub Releases (pas dans le repo) pour réduire friction onboarding
- **Déployer landing** — `cd C:\Users\alecs\Desktop\study-agent\landing-v3 && vercel deploy --prod`
- **Intégrer setup_google.ps1** — script Agent 2B dans `scripts/setup_google.ps1` du repo
- **Valider cours récurrents en prod** — PRIORITÉ 1

## Commandes
```powershell
cd C:\Users\alecs\Desktop\Omnisync
.\run.bat doctor                  # vérifier l'état complet
.\run.bat run --scrape-only       # scraper sans toucher Calendar
.\run.bat run --calendar-dry-run  # scraper + valider sans écrire Calendar
.\run.bat run                     # pipeline complet
python scripts/build_memory.py     # régénérer ce fichier
```