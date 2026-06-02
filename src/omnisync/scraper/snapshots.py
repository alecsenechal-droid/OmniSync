"""
Snapshots — sauvegarde HTML automatique + replay local.

Chaque run crée un dossier horodaté dans %LOCALAPPDATA%/OmniSync/snapshots/.
Le HTML brut de chaque module y est sauvegardé avec ses métadonnées.

Structure:
    snapshots/
        2026-05-27T05-00-01/
            lea_assignments.html
            lea_assignments.meta.json
            lea_calendar.html
            lea_calendar.meta.json
            final_exams.html
            final_exams.meta.json

Replay:
    omnisync replay                         # liste les runs
    omnisync replay 2026-05-27T05-00-01     # inspecte un run spécifique
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from omnisync import paths

if TYPE_CHECKING:
    from playwright.sync_api import Page


# Run courant — initialisé au début de chaque scrape
_CURRENT_RUN_DIR: Path | None = None


def start_run() -> Path:
    """
    Crée le dossier horodaté pour le run courant.
    À appeler UNE FOIS au début du scraping.
    """
    global _CURRENT_RUN_DIR
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    _CURRENT_RUN_DIR = paths.snapshots_dir() / ts
    _CURRENT_RUN_DIR.mkdir(parents=True, exist_ok=True)
    from omnisync.ui import vlog as _vlog
    _vlog(f"[SNAPSHOT] Run demarre: {_CURRENT_RUN_DIR}")
    return _CURRENT_RUN_DIR


def current_run_dir() -> Path | None:
    return _CURRENT_RUN_DIR


def save(page: "Page", module: str, extra: dict[str, Any] | None = None) -> Path | None:
    """
    Sauvegarde le HTML courant + métadonnées du module.

    Args:
        page: Page Playwright active.
        module: Identifiant du module (ex: 'lea_assignments', 'final_exams').
        extra: Métadonnées supplémentaires (ex: nb items trouvés).

    Returns:
        Chemin du fichier HTML, ou None si erreur.
    """
    global _CURRENT_RUN_DIR
    if _CURRENT_RUN_DIR is None:
        _CURRENT_RUN_DIR = start_run()

    html_path = _CURRENT_RUN_DIR / f"{module}.html"
    meta_path = _CURRENT_RUN_DIR / f"{module}.meta.json"

    # Sauvegarder le HTML
    try:
        html = page.content()
        html_path.write_text(html, encoding="utf-8")
        html_size = len(html)
    except Exception as exc:
        html_path.write_text(f"<!-- snapshot failed: {exc} -->", encoding="utf-8")
        html_size = 0

    # Sauvegarder les métadonnées
    meta: dict[str, Any] = {
        "module": module,
        "url": page.url,
        "title": _safe_title(page),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "html_bytes": html_size,
    }
    if extra:
        meta.update(extra)

    try:
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

    return html_path


def _safe_title(page: "Page") -> str:
    try:
        return page.title()
    except Exception:
        return ""


def list_runs() -> list[Path]:
    """Liste les runs disponibles, du plus récent au plus ancien."""
    d = paths.snapshots_dir()
    if not d.exists():
        return []
    return sorted(
        (p for p in d.iterdir() if p.is_dir()),
        reverse=True,
    )


def load(run_dir: Path, module: str) -> tuple[str, dict]:
    """
    Charge HTML + métadonnées d'un module dans un run.

    Returns: (html_content, metadata_dict)
    """
    html_path = run_dir / f"{module}.html"
    meta_path = run_dir / f"{module}.meta.json"

    html = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
    meta: dict = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return html, meta


def print_run_summary(run_dir: Path) -> None:
    """Affiche un résumé d'un run spécifique."""
    modules = sorted(p.stem for p in run_dir.glob("*.html"))
    print(f"\nRun: {run_dir.name}")
    print(f"Modules: {', '.join(modules) or '(aucun)'}")
    for module in modules:
        _, meta = load(run_dir, module)
        if meta:
            items = meta.get("items_found", "?")
            url = meta.get("url", "")[:60]
            ts = meta.get("timestamp", "")[:19]
            print(f"  [{module}] items={items} url={url} at={ts}")
    print()


def print_all_runs() -> None:
    """Affiche tous les runs disponibles."""
    runs = list_runs()
    if not runs:
        print("Aucun snapshot disponible. Lancez d'abord: run.bat run")
        return
    print(f"\n{len(runs)} run(s) disponible(s) (10 plus récents):\n")
    for run in runs[:10]:
        modules = [p.stem for p in run.glob("*.html")]
        print(f"  {run.name}  [{', '.join(modules)}]")
    print("\nPour inspecter un run: run.bat replay <nom-du-run>")
    print()
