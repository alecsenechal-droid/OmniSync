"""
Validator — détecte les scrapes anormaux avant écriture en base.

Principe: compare les résultats du run courant avec le dernier run réussi.
Une chute soudaine à 0 sur un module précédemment non-vide = suspect.

Aucune décision n'est silencieuse. Chaque anomalie est loggée avec:
- le module concerné
- les valeurs comparées
- la raison exacte
- le snapshot associé
- le niveau de gravité

Log format:
    [VALIDATOR][FAIL][HIGH] module=lea_assignments previous=14 current=0 reason=sudden_drop_to_zero snapshot=...
    [VALIDATOR][WARN][MEDIUM] module=lea_calendar previous=8 current=3 reason=significant_drop detail=Perte 62%
    [VALIDATOR][INFO][LOW] module=final_exams previous=0 current=5 reason=first_run
    [VALIDATOR][PASS] Tous les modules nominaux.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from omnisync import paths

# ── Seuils ────────────────────────────────────────────────────────────────────

# Si le module avait N items et retourne 0 → FAIL HIGH
SUDDEN_ZERO_MIN_PREVIOUS = 1  # minimum d'items précédents pour déclencher

# Perte de plus de 85% → FAIL HIGH
FAIL_DROP_PCT = 0.85

# Perte de 50-85% → WARN MEDIUM
WARN_DROP_PCT = 0.50


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class ModuleStats:
    """Résultats d'un module de scraping pour un run donné."""
    module: str
    count: int
    count_with_dates: int = 0
    snapshot_path: str = ""


@dataclass
class ValidationEvent:
    level: str      # "INFO" | "WARN" | "FAIL"
    severity: str   # "LOW" | "MEDIUM" | "HIGH"
    module: str
    reason: str
    previous: int
    current: int
    detail: str = ""
    snapshot_path: str = ""

    def __str__(self) -> str:
        parts = [
            f"[VALIDATOR][{self.level}][{self.severity}]",
            f"module={self.module}",
            f"previous={self.previous}",
            f"current={self.current}",
            f"reason={self.reason}",
        ]
        if self.detail:
            parts.append(f"detail={self.detail}")
        if self.snapshot_path:
            parts.append(f"snapshot={self.snapshot_path}")
        return " ".join(parts)

    def log(self) -> None:
        print(str(self))


@dataclass
class ValidationReport:
    passed: bool
    events: list[ValidationEvent] = field(default_factory=list)
    stats: dict[str, ModuleStats] = field(default_factory=dict)

    def print(self) -> None:
        if self.passed:
            if self.events:
                print(f"[VALIDATOR][PASS] {len(self.events)} info/warn(s):")
                for evt in self.events:
                    evt.log()
            else:
                print("[VALIDATOR][PASS] Tous les modules nominaux.")
        else:
            fails = [e for e in self.events if e.level == "FAIL"]
            print(f"[VALIDATOR][FAIL] {len(fails)} anomalie(s) critique(s):")
            for evt in self.events:
                evt.log()
        print()

    @property
    def has_failures(self) -> bool:
        return any(e.level == "FAIL" for e in self.events)

    @property
    def has_warnings(self) -> bool:
        return any(e.level == "WARN" for e in self.events)


# ── Persistance des stats de run ──────────────────────────────────────────────

_STATS_SCHEMA = """
CREATE TABLE IF NOT EXISTS sync_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at       TEXT NOT NULL,
    stats_json   TEXT NOT NULL,
    passed       INTEGER NOT NULL DEFAULT 1,
    snapshot_dir TEXT
);
"""


def _conn() -> sqlite3.Connection:
    paths.ensure_runtime_dirs()
    conn = sqlite3.connect(paths.db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(_STATS_SCHEMA)
    return conn


def _load_last_stats() -> dict[str, int] | None:
    """
    Charge les stats du dernier run réussi.
    Retourne None si aucun run précédent (première installation).
    """
    with _conn() as conn:
        row = conn.execute(
            "SELECT stats_json FROM sync_runs WHERE passed = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["stats_json"])
    except Exception:
        return None


def _save_run_stats(stats: dict[str, int], passed: bool,
                    snapshot_dir: str = "") -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO sync_runs (run_at, stats_json, passed, snapshot_dir) "
            "VALUES (?, ?, ?, ?)",
            (now, json.dumps(stats), int(passed), snapshot_dir),
        )


def get_run_history(limit: int = 10) -> list[dict[str, Any]]:
    """Retourne l'historique des N derniers runs (pour diagnostic)."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT run_at, stats_json, passed, snapshot_dir "
            "FROM sync_runs ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    result = []
    for row in rows:
        try:
            stats = json.loads(row["stats_json"])
        except Exception:
            stats = {}
        result.append({
            "run_at": row["run_at"],
            "passed": bool(row["passed"]),
            "stats": stats,
            "snapshot_dir": row["snapshot_dir"] or "",
        })
    return result


# ── Core validation ───────────────────────────────────────────────────────────

def validate(
    current_stats: dict[str, ModuleStats],
    snapshot_dir: Path | None = None,
) -> ValidationReport:
    """
    Compare les résultats du scrape courant avec le dernier run réussi.
    Sauvegarde les stats courantes en DB pour le prochain run.

    Args:
        current_stats: Résultats du run courant, clé = nom de module.
        snapshot_dir: Dossier des snapshots HTML du run courant.

    Returns:
        ValidationReport avec la liste des anomalies.
    """
    previous = _load_last_stats()
    events: list[ValidationEvent] = []

    for module, stats in current_stats.items():
        prev_count = (previous or {}).get(module, -1)
        curr_count = stats.count
        snap = stats.snapshot_path or (
            str(snapshot_dir / f"{module}.html")
            if snapshot_dir else ""
        )

        # ── Premier run — pas de référence ───────────────────────────────────
        if prev_count == -1:
            events.append(ValidationEvent(
                level="INFO", severity="LOW",
                module=module, reason="first_run",
                previous=0, current=curr_count,
                detail="Aucun run précédent pour comparaison.",
                snapshot_path=snap,
            ))
            continue

        # ── Chute à zéro sur module précédemment non-vide ────────────────────
        if prev_count >= SUDDEN_ZERO_MIN_PREVIOUS and curr_count == 0:
            # lea_assignments tombe légitimement à 0 en fin de session scolaire.
            # Mois typiques : mai-août (fin hiver) et décembre-janvier (fin automne).
            _today = date.today()
            _end_of_semester = module == "lea_assignments" and _today.month in {5, 6, 7, 8, 12, 1}
            if _end_of_semester:
                events.append(ValidationEvent(
                    level="WARN", severity="LOW",
                    module=module, reason="session_expired",
                    previous=prev_count, current=curr_count,
                    detail="Fin de session probable -- aucun travail actif attendu.",
                    snapshot_path=snap,
                ))
            else:
                events.append(ValidationEvent(
                    level="FAIL", severity="HIGH",
                    module=module, reason="sudden_drop_to_zero",
                    previous=prev_count, current=curr_count,
                    detail="Possible redirect login ou session invalide.",
                    snapshot_path=snap,
                ))
            continue

        # ── Chute massive (>85%) ──────────────────────────────────────────────
        if prev_count > 0 and curr_count < prev_count * (1 - FAIL_DROP_PCT):
            pct = 100 * (1 - curr_count / prev_count)
            events.append(ValidationEvent(
                level="FAIL", severity="HIGH",
                module=module, reason="major_data_loss",
                previous=prev_count, current=curr_count,
                detail=f"Perte de {pct:.0f}% des données.",
                snapshot_path=snap,
            ))
            continue

        # ── Chute modérée (50–85%) ────────────────────────────────────────────
        if prev_count > 0 and curr_count < prev_count * (1 - WARN_DROP_PCT):
            pct = 100 * (1 - curr_count / prev_count)
            events.append(ValidationEvent(
                level="WARN", severity="MEDIUM",
                module=module, reason="significant_drop",
                previous=prev_count, current=curr_count,
                detail=f"Perte de {pct:.0f}% des données.",
                snapshot_path=snap,
            ))

    # Décision globale : FAIL bloquant uniquement si le module avait des données
    passed = not any(e.level == "FAIL" for e in events)

    # Sauvegarder les stats même en cas de FAIL (pour comparaison future)
    flat_stats = {k: v.count for k, v in current_stats.items()}
    snap_dir_str = str(snapshot_dir) if snapshot_dir else ""
    _save_run_stats(flat_stats, passed, snap_dir_str)

    return ValidationReport(passed=passed, events=events, stats=current_stats)
