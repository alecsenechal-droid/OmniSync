# OmniSync — Boot Context
updated: 2026-06-01 | 13 étapes validées | 8 en attente

## État
---
**Omnivox** : stable — DA=2534700, mot de passe keyring OS, headless=true.
**Google Calendar** : stable — calendrier "OmniSync" en production.
**Moodle** : TOKEN VALIDE — 19 travaux au dernier run.
**Notifications** : actives — `omnisyncqc@gmail.com` → `alec.senechal@gmail.com`.
**Doctor** : 15/15 PASS ✅
**run --scrape-only** : PASS — 82 events Omnivox + 19 Moodle, `[OK] Aucune anomalie` ✅
**Multi-cégep** : diagnostics SSO + logs préfixés + doctor checks — prêt pour beta ✅
---
### Refactoring God File (session 2026-06-01)
- `omnivox_engine.py` : 4388 → 86 lignes (thin shell). 11 modules extraits.
- Commits : `dce848b` (refactor + SSO), `880e086` (doctor 15/15), `f54dddb` (logs slug)

## Architecture
```
Omnivox(Playwright) + Moodle(REST) + Actualités → SQLite(%LOCALAPPDATA%\OmniSync) → Google Calendar
```

## Modules critiques (post-refactoring)
```
scraper/
  omnivox_engine.py   (86 L)  ← thin shell de re-exports
  omnivox_models.py  (165 L)  ← dataclasses + constantes
  omnivox_helpers.py (197 L)  ← utilitaires purs
  omnivox_browser.py (126 L)  ← cycle de vie Playwright
  omnivox_loader.py  (149 L)  ← MODULES + load_config()
  omnivox_auth.py    (328 L)  ← SSO LEA/ESTD + login + MFA
  scrape_mio.py      (480 L)  ← messagerie MIO
  scrape_horaire.py   (91 L)  ← horaire cours
  scrape_notes.py    (232 L)  ← notes d'évaluation
  scrape_lea.py      (340 L)  ← documents, actualités, vue LEA
  scrape_travaux.py  (609 L)  ← travaux et évaluations
  scrape_calendrier.py(583 L) ← calendrier LEA, examens, ICS
```

## Règles figées (JAMAIS modifier sans demande explicite)
- `SchoolEvent` + `_dedupe()` : schéma immuable
- Sélecteur LEA : `table#tabListeTravEtu tr` — sans classe CSS, jamais `.LigneListTrav1`
- Moodle : bloc `try/except` SÉPARÉ de Playwright, `MoodleMFARequired` en PREMIER
- `input[name='passwd']` : attendre `state="visible"` (SPA AAD, invisible au chargement)
- `channel="chrome"` → page blanche. `wait_for_load_state` inopérant sur SPA AAD.
- Clés `config.toml`, `pyproject.toml`, sélecteurs `omnivox_engine` : figés

## Risques actifs
- **Token Moodle** : expiration inconnue → Edge F12 → Network → launch.php → `run.bat token-moodle`
- **Sélecteurs Omnivox** : non testés sur csfoy/cegepgarneau
- **SSO WARN sur Limoilou** : format `lk=` (pas `C=CLI`) → faux positif cosmétique, SSO OK quand même

## Prochaines étapes
- **Beta testeur Ste-Foy ou Garneau** — PRIORITÉ 1 (logs prêts pour diagnostiquer)
- **Valider cours récurrents en prod** — début août
- **Valider écriture Calendar automne 2026** — dès session automne
- **ESTD examens finaux** — retester en août
- **PyInstaller .exe** — hors scope immédiat

## Commandes
```powershell
cd C:\Users\alecs\Desktop\Omnisync
.\run.bat doctor                  # vérifier l'état complet (15/15)
.\run.bat run --scrape-only       # scraper sans toucher Calendar
.\run.bat run --calendar-dry-run  # scraper + valider sans écrire Calendar
.\run.bat run --verbose           # logs détaillés avec prefixe [climoilou]
.\run.bat run                     # pipeline complet
python scripts/build_memory.py     # régénérer ce fichier
```
