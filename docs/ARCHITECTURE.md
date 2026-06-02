# Architecture

```text
Omnivox -> scraper -> SQLite -> Google Calendar
```

## Principes

- Code public separe des donnees utilisateur.
- Donnees runtime dans `%LOCALAPPDATA%\OmniSync`.
- Secrets jamais dans le repo.
- SQLite comme source de verite locale.
- Google Calendar mis a jour a partir de la DB.
- Scraper isole derriere `scraper.adapter.scrape_omnivox`.

## Portage du scraper existant

Le scraper personnel actuel doit etre migre module par module:

- session/login/SSO;
- LEA travaux;
- LEA calendrier;
- ESTD examens;
- MIO plus tard.

Le CLI public ne doit pas dependre de chemins personnels ni de fichiers locaux du prototype.
