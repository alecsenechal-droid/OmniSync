# Roadmap

## Phase 0 - Scaffold public

- Repo propre.
- CLI.
- Config locale.
- Scheduler Windows.
- Docs securite.
- Dry-run Calendar sur donnees Omnivox reelles.

## Phase 1 - Moteur Omnivox

- [x] Portage login / LEA / examens dans `scraper/omnivox_engine.py`.
- Affiner annulations et horaire si necessaire.
- Tests offline sur fixtures anonymes.
- Remplacer le fallback SQLite legacy par une extraction de dates fiable.

## Phase 2 - Google Calendar

- OAuth.
- Creation/update/delete.
- Rappels et couleurs.
- Nettoyage des evenements OmniSync.

## Phase 3 - Distribution

- PyInstaller onedir.
- Inno Setup.
- Release GitHub.

## Phase 4 - Extensions

- GUI.
- Support multi-cegep.
- MIO.
- Obsidian optionnel.
