from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchoolEvent:
    uid: str
    title: str
    kind: str
    course_code: str | None
    date_iso: str | None
    time_start: str | None = None
    time_end: str | None = None
    room: str | None = None
    teacher: str | None = None
    description: str | None = None


@dataclass
class CourseSlot:
    """Un créneau récurrent de cours (ex: Calcul diff, lundi+mercredi 09:30-11:30).

    Créé en regroupant les LeaEvent(kind='cours') par (course_code, time_start, time_end).
    Utilisé pour générer un seul événement récurrent Google Calendar par créneau via RRULE.
    """
    uid: str                      # "course_{hash}" — stable entre les syncs
    course_code: str
    title: str                    # nom complet du cours
    days_ical: tuple[str, ...]    # ("MO", "WE") — jours iCal détectés
    time_start: str               # "09:30"
    time_end: str                 # "11:30"
    room: str | None
    teacher: str | None
    dtstart_iso: str              # "2026-01-12" — première occurrence connue
    until_iso: str                # "2026-04-25" — dernière occurrence connue
