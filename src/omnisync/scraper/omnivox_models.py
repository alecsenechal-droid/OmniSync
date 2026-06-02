"""
Constantes de domaine et dataclasses Omnivox.
Responsabilité unique : types de données et constantes du domaine Omnivox/LEA.
Zéro logique, zéro I/O, zéro Playwright.
"""
import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

# ── Constantes de dates et jours ─────────────────────────────────────────────

MOIS_FR_MAP = {
    "janvier": 1, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
}
MOIS_ABBR_MAP = {
    "jan": 1, "fév": 2, "mar": 3, "avr": 4, "mai": 5,
    "juin": 6, "juil": 7, "aoû": 8, "sep": 9, "oct": 10, "nov": 11, "déc": 12,
}
JOURS_ICAL = {
    "lundi": "MO", "mardi": "TU", "mercredi": "WE",
    "jeudi": "TH", "vendredi": "FR", "samedi": "SA", "dimanche": "SU",
}
JOURS_ABBR = {
    "lun": "lundi", "mar": "mardi", "mer": "mercredi",
    "jeu": "jeudi", "ven": "vendredi", "sam": "samedi", "dim": "dimanche",
}
JOURS_LIST = list(JOURS_ICAL.keys())

# ── Constantes Google Calendar ────────────────────────────────────────────────

GCAL_COLOR  = {"exam": "11", "assignment": "10", "class": "3", "work": "9"}
GCAL_TAG    = "omnivox-studyagent"
GCAL_SCOPES = ["https://www.googleapis.com/auth/calendar"]

# ── Regex partagées ───────────────────────────────────────────────────────────

EXAM_PATTERN   = re.compile(
    r'\b(examen|exam|intra|final|test|quiz|[eé]valuation)\b', re.IGNORECASE
)
COURSE_CODE_RE = re.compile(r'(\d{3}-\d{3}-\w{2})')

# ── Valeurs par défaut ────────────────────────────────────────────────────────

DEFAULT_TIMEOUT_MS = 30_000


# ── Dataclass principale : config session Playwright ─────────────────────────

@dataclass
class Config:
    matricule: str
    password: str
    base_dir: Path
    # ── Identité du cégep (universel) ─────────────────────────────────────────
    slug: str = "climoilou"               # ex: "climoilou", "cegepsherbrooke"
    institution_code: str = "CLI"         # ex: "CLI", "SHR", "SFO" (pour SSO Skytech)
    lang: str = "FRA"                     # "FRA" ou "ANG" (cégeps anglais)
    # ── Session ───────────────────────────────────────────────────────────────
    term: str = "2026-Hiver"
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    headless: bool = False
    gcal_credentials: Optional[Path] = None
    gcal_calendar_id: str = "primary"
    work_days: list[str] = field(default_factory=list)
    semester_start: Optional[date] = None
    semester_end: Optional[date] = None
    exam_keywords: list[str] = field(default_factory=list)
    assignment_keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)

    @property
    def omnivox_base(self) -> str:
        return f"https://{self.slug}.omnivox.ca"

    @property
    def estd_base(self) -> str:
        return f"https://{self.slug}-estd.omnivox.ca"

    @property
    def lea_base(self) -> str:
        return f"https://{self.slug}-lea.omnivox.ca"

    @property
    def mio_base(self) -> str:
        return f"https://{self.slug}.omnivox.ca/WebApplication/Module.MIOE"

    @property
    def skytech_sso_url(self) -> str:
        return (
            f"{self.omnivox_base}/intr/Module/ServicesExterne/Skytech.aspx"
            f"?IdServiceSkytech=Skytech_Omnivox&C={self.institution_code}"
            f"&E=P&L={self.lang}"
        )


def lea_host(slug: str) -> str:
    return f"{slug}-lea.omnivox.ca"


def estd_host(slug: str) -> str:
    return f"{slug}-estd.omnivox.ca"


# ── Dataclasses scraped data ──────────────────────────────────────────────────

@dataclass
class ClassEvent:
    course: str
    course_code: str
    days_fr: list[str]
    start_time: str
    end_time: str
    room: str
    teacher: str
    color_id: str = GCAL_COLOR["class"]


@dataclass
class Assignment:
    title: str
    course: str
    course_code: str
    due_date: Optional[str]
    weight: Optional[str]
    kind: str = "assignment"
    color_id: str = GCAL_COLOR["assignment"]
    ideval: Optional[str] = None
    detail_href: Optional[str] = None
    time_start: Optional[str] = None  # heure exacte depuis ListeTravauxEtu (ex: "23:55")


@dataclass
class LeaEvent:
    date_iso: str
    time_start: str
    time_end: str
    kind: str
    title: str
    course_code: str
    course_name: str
    room: str
    weight: str

    @property
    def color_id(self) -> str:
        return {
            "cours":      GCAL_COLOR["class"],
            "evaluation": GCAL_COLOR["exam"],
            "travail":    GCAL_COLOR["assignment"],
            "lire": "2", "autre": "1",
        }.get(self.kind, GCAL_COLOR["assignment"])


@dataclass
class FinalExam:
    date_iso: str
    time_start: str
    time_end: str
    course_code: str
    course_name: str
    room: str
    teacher: str


@dataclass
class MioMessage:
    msg_id: str
    sender: str
    course_code: str
    subject: str
    date_iso: str
    body: str
    is_read: bool
    has_attachment: bool


@dataclass
class CourseNote:
    course_code: str
    course_name: str
    score: float
    max_score: float
    percentage: float
    group_avg: float
    absences_hours: float


@dataclass
class LeaCourse:
    code: str
    name: str
    group: str
    teacher: str
    schedule: str
    doc_count: int
    work_count: int
