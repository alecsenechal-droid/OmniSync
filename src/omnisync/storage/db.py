from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import Any

from omnisync import paths
from omnisync.scraper.models import SchoolEvent

# ── Schéma principal ──────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    uid          TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    kind         TEXT NOT NULL,
    course_code  TEXT,
    date_iso     TEXT,
    time_start   TEXT,
    time_end     TEXT,
    room         TEXT,
    teacher      TEXT,
    description  TEXT,
    gcal_event_id TEXT,
    -- Canonical event model (ajouté V1.1)
    first_seen_at TEXT,
    updated_at    TEXT NOT NULL,
    source_hash   TEXT,
    status        TEXT NOT NULL DEFAULT 'active'
);
"""

# ── Migrations pour DBs existantes ────────────────────────────────────────────
# SQLite ne supporte pas "ADD COLUMN IF NOT EXISTS" — on ignore l'erreur.
_MIGRATIONS = [
    "ALTER TABLE events ADD COLUMN first_seen_at TEXT",
    "ALTER TABLE events ADD COLUMN source_hash TEXT",
    "ALTER TABLE events ADD COLUMN status TEXT NOT NULL DEFAULT 'active'",
]


def _source_hash(event: SchoolEvent) -> str:
    """
    Hash des champs mutables d'un événement.
    Si le hash change entre deux runs → le contenu a réellement changé.
    Stable sur : title, kind, date, heure, local, enseignant, code cours.
    """
    raw = "|".join(str(v or "") for v in [
        event.title, event.kind, event.course_code, event.date_iso,
        event.time_start, event.time_end, event.room, event.teacher,
    ])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def connect() -> sqlite3.Connection:
    paths.ensure_runtime_dirs()
    conn = sqlite3.connect(paths.db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # Migrations non-destructives
    for sql in _MIGRATIONS:
        try:
            conn.execute(sql)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Colonne déjà présente
    return conn


def upsert_events(events: list[SchoolEvent]) -> tuple[int, int]:
    """
    Insère ou met à jour les événements.

    Returns:
        (created, updated) où "updated" signifie contenu réellement changé,
        pas simplement "vu à nouveau".
    """
    created = updated = 0
    now = datetime.now(timezone.utc).isoformat()

    with connect() as conn:
        for event in events:
            new_hash = _source_hash(event)
            row = conn.execute(
                "SELECT uid, source_hash, status FROM events WHERE uid = ?",
                (event.uid,)
            ).fetchone()

            if row is None:
                # Nouvel événement
                conn.execute(
                    """
                    INSERT INTO events (
                        uid, title, kind, course_code, date_iso, time_start,
                        time_end, room, teacher, description,
                        first_seen_at, updated_at, source_hash, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
                    """,
                    (
                        event.uid, event.title, event.kind, event.course_code,
                        event.date_iso, event.time_start, event.time_end,
                        event.room, event.teacher, event.description,
                        now, now, new_hash,
                    ),
                )
                created += 1

            elif row["source_hash"] != new_hash:
                # Contenu réellement modifié (titre, date, local…)
                conn.execute(
                    """
                    UPDATE events SET
                        title=?, kind=?, course_code=?, date_iso=?,
                        time_start=?, time_end=?, room=?, teacher=?,
                        description=?, updated_at=?, source_hash=?, status='active'
                    WHERE uid=?
                    """,
                    (
                        event.title, event.kind, event.course_code,
                        event.date_iso, event.time_start, event.time_end,
                        event.room, event.teacher, event.description,
                        now, new_hash, event.uid,
                    ),
                )
                updated += 1

            else:
                # Vu à nouveau, contenu identique → on remet active sans compter
                conn.execute(
                    "UPDATE events SET status='active', updated_at=? WHERE uid=?",
                    (now, event.uid),
                )

    return created, updated


def mark_deleted(active_uids: set[str]) -> int:
    """
    Marque comme 'deleted' tous les événements actifs non présents dans ce run.
    Retourne le nombre d'événements marqués supprimés.
    """
    if not active_uids:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        rows = conn.execute(
            "SELECT uid FROM events WHERE status = 'active'"
        ).fetchall()
        to_delete = [r["uid"] for r in rows if r["uid"] not in active_uids]
        for uid in to_delete:
            conn.execute(
                "UPDATE events SET status='deleted', updated_at=? WHERE uid=?",
                (now, uid),
            )
    return len(to_delete)


def get_event_history(uid: str) -> dict[str, Any] | None:
    """Retourne l'enregistrement complet d'un événement (pour debugging)."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM events WHERE uid = ?", (uid,)).fetchone()
        return dict(row) if row else None
