#!/usr/bin/env python3
"""
Génère docs/PROJECT_STATE.md — contexte de boot pour nouvelle session Claude.
Objectif : ~45 lignes, ~600 tokens. Un seul fichier à lire en début de session.
Usage : python scripts/build_memory.py
"""
from __future__ import annotations
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"
SRC = ROOT / "src" / "omnisync"

CRITICAL_MODULES = [
    ("omnivox_engine", "Playwright — scraping LEA/Omnivox (sélecteurs figés)"),
    ("scraper/moodle_engine", "REST wstoken Moodle + SSO SAML2"),
    ("sync", "Orchestrateur pipeline principal"),
    ("calendar/google", "Google Calendar API — CRUD events"),
    ("storage/db", "SQLite — source de vérité locale"),
]


def read(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default


def pending(todo: str) -> list[str]:
    out = []
    for l in todo.splitlines():
        if "- [ ]" not in l:
            continue
        # Supprime le préfixe "- [ ] " et les marqueurs gras optionnels "**N. ...**"
        item = re.sub(r"^[\s-]*\[ \]\s*", "", l).strip()       # strip "- [ ] "
        item = re.sub(r"^\*+\d+\.\s*", "", item)                # strip "**6. "
        item = re.sub(r"\*+\s*$", "", item).strip()             # strip trailing "**"
        item = re.sub(r"\s*—\s*(FAIT|TODO).*$", "", item).strip()
        if item:
            out.append(item)
    return out


def current_state(session: str) -> str:
    """Extrait le bloc d'état sans les entêtes ni la section debug."""
    lines = []
    for l in session.splitlines():
        s = l.strip()
        if not s or s.startswith("# ") or s.startswith("## "):
            continue
        if s.startswith("**Fichiers de debug") or s.startswith("**Commit**"):
            break
        lines.append(s)
    return "\n".join(lines[:12])


def build() -> str:
    today = date.today().isoformat()
    session = read(DOCS / "SESSION_HANDOFF.md")
    todo = read(DOCS / "TODO.md")

    done = sum(1 for l in todo.splitlines() if "- [x]" in l)
    pending_items = pending(todo)
    state = current_state(session)
    next_steps = "\n".join(f"- {p}" for p in pending_items[:5])
    modules = "\n".join(f"- `{name}` : {role}" for name, role in CRITICAL_MODULES)

    return f"""# OmniSync — Boot Context
updated: {today} | {done} étapes validées | {len(pending_items)} en attente

## État
{state}

## Architecture
```
Omnivox(Playwright) + Moodle(REST) + Actualités → SQLite(%LOCALAPPDATA%\\OmniSync) → Google Calendar
```

## Modules critiques
{modules}

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
{next_steps}

## Commandes
```powershell
cd C:\\Users\\alecs\\Desktop\\Omnisync
.\\run.bat doctor                  # vérifier l'état complet
.\\run.bat run --scrape-only       # scraper sans toucher Calendar
.\\run.bat run --calendar-dry-run  # scraper + valider sans écrire Calendar
.\\run.bat run                     # pipeline complet
python scripts/build_memory.py     # régénérer ce fichier
```
""".strip()


if __name__ == "__main__":
    out = DOCS / "PROJECT_STATE.md"
    content = build()
    out.write_text(content, encoding="utf-8")
    lines = content.count("\n") + 1
    tokens_approx = len(content) // 4
    print(f"[OK] {out} — {lines} lignes, ~{tokens_approx} tokens")
