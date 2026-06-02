from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from omnisync import paths
from omnisync.config import load_settings, save_settings
from omnisync.scraper.models import CourseSlot, SchoolEvent

GCAL_SOURCE = "omnisync"
GCAL_SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Couleurs Google Calendar par type d'événement
COLOR = {
    "assignment": "5",   # Banana (jaune) — deadline importante
    "exam":       "11",  # Tomato (rouge) — toujours critique
    "class":      "9",   # Blueberry (bleu) — horaire de cours
    "reading":    "2",   # Sage (vert discret) — lecture basse priorité
    "event":      "8",   # Graphite (gris) — annonce informative
}

# Heures de fallback par kind — élimine les all-day events
_FALLBACK_TIMES: dict[str, tuple[str, str]] = {
    "assignment": ("23:00", "23:59"),   # deadline ce soir
    "exam":       ("09:00", "12:00"),   # bloc matin (3h)
    "reading":    ("21:00", "22:00"),   # lecture ce soir
    "event":      ("08:00", "08:15"),   # annonce matinale (15 min)
    "class":      ("09:00", "11:00"),   # fallback si class event sans slot
}

# Rappels par type (minutes avant)
_REMINDERS: dict[str, list[dict]] = {
    "exam": [
        {"method": "popup", "minutes": 7 * 24 * 60},   # J-7
        {"method": "popup", "minutes": 2 * 24 * 60},   # J-2
        {"method": "popup", "minutes": 2 * 60},         # 2h avant
    ],
    "assignment": [
        {"method": "popup", "minutes": 2 * 24 * 60},   # J-2
        {"method": "popup", "minutes": 2 * 60},         # 2h avant
    ],
    "reading": [
        {"method": "popup", "minutes": 24 * 60},        # J-1
    ],
    "class": [
        {"method": "popup", "minutes": 30},             # 30 min avant
    ],
    # "event" / annonces : aucun rappel
}

OMNISYNC_CALENDAR_NAME = "OmniSync"
OMNISYNC_CALENDAR_COLOR = "teal"


def _credentials_path() -> Path | None:
    env_path = os.environ.get("OMNISYNC_GOOGLE_CREDENTIALS")
    if env_path:
        return Path(env_path)
    if paths.credentials_path().exists():
        return paths.credentials_path()

    legacy = os.environ.get("OMNISYNC_LEGACY_PROJECT")
    if legacy:
        candidate = Path(legacy) / "credentials.json"
        if candidate.exists():
            return candidate
    return None


def _get_service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("Dependances Google manquantes. Lancez install.bat.") from exc

    credentials_path = _credentials_path()
    if credentials_path is None:
        raise RuntimeError(
            "credentials.json Google introuvable. Placez-le dans %LOCALAPPDATA%\\OmniSync "
            "ou definissez OMNISYNC_GOOGLE_CREDENTIALS."
        )

    paths.ensure_runtime_dirs()
    creds = None
    token_path = paths.token_path()
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), GCAL_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), GCAL_SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("calendar", "v3", credentials=creds)


def _find_or_create_omnisync_calendar(service) -> str:
    """Trouve le calendrier 'OmniSync' ou le crée. Retourne son ID."""
    try:
        cal_list = service.calendarList().list().execute()
        for cal in cal_list.get("items", []):
            if cal.get("summary") == OMNISYNC_CALENDAR_NAME:
                return cal["id"]
    except Exception as exc:
        raise RuntimeError(f"Impossible de lire la liste des agendas: {exc}") from exc

    # Créer le calendrier
    try:
        new_cal = service.calendars().insert(body={
            "summary": OMNISYNC_CALENDAR_NAME,
            "description": "Horaire et deadlines synchronises depuis Omnivox par OmniSync.",
            "timeZone": "America/Toronto",
        }).execute()
        cal_id = new_cal["id"]
        print(f"Calendrier '{OMNISYNC_CALENDAR_NAME}' cree: {cal_id}")
    except Exception as exc:
        raise RuntimeError(f"Impossible de créer le calendrier OmniSync: {exc}") from exc

    # Appliquer la couleur teal via calendarList
    try:
        service.calendarList().patch(
            calendarId=cal_id,
            body={"colorId": OMNISYNC_CALENDAR_COLOR},
        ).execute()
    except Exception:
        pass  # La couleur est cosmétique — on ignore l'échec

    return cal_id


def _resolve_calendar_id(service, settings) -> str:
    """Résout 'auto' en cherchant/créant le calendrier OmniSync. Met à jour config si besoin."""
    cal_id = settings.calendar_id
    if cal_id and cal_id != "auto":
        return cal_id

    cal_id = _find_or_create_omnisync_calendar(service)
    settings.calendar_id = cal_id
    save_settings(settings)
    return cal_id


def connect_google_calendar() -> str:
    """Lance le flux OAuth et retourne l'ID du calendrier utilisé."""
    settings = load_settings()
    service = _get_service()
    return _resolve_calendar_id(service, settings)


def _fetch_existing(service, calendar_id: str) -> dict[str, str]:
    """Retourne {omnisync_uid: event_id} pour tous les events OmniSync du calendrier."""
    existing: dict[str, str] = {}
    page_token = None
    while True:
        result = service.events().list(
            calendarId=calendar_id,
            privateExtendedProperty=f"source={GCAL_SOURCE}",
            pageToken=page_token,
            maxResults=500,
            showDeleted=False,
        ).execute()
        for item in result.get("items", []):
            uid = (
                item.get("extendedProperties", {})
                .get("private", {})
                .get("omnisync_uid", "")
            )
            if uid:
                existing[uid] = item["id"]
        page_token = result.get("nextPageToken")
        if not page_token:
            return existing


def _fetch_course_schedule(service) -> dict[tuple[str, str], dict]:
    """
    Lit tous les agendas pour trouver les créneaux de cours existants.
    Inclut les cours créés par OmniSync (kind='class') pour ancrer les examens/remises.
    Retourne {(date_iso, course_code): {time_start, time_end, room}}.
    """
    schedule: dict[tuple[str, str], dict] = {}
    time_min = "2026-01-01T00:00:00Z"
    time_max = "2027-06-30T23:59:59Z"
    try:
        cals = service.calendarList().list().execute()
    except Exception:
        return schedule

    for cal in cals.get("items", []):
        cal_id = cal["id"]
        try:
            page_token = None
            while True:
                result = service.events().list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=500,
                    singleEvents=True,
                    orderBy="startTime",
                    pageToken=page_token,
                ).execute()
                for ev in result.get("items", []):
                    private = ev.get("extendedProperties", {}).get("private", {})
                    # Inclure les cours OmniSync (omnisync_kind=class), exclure le reste
                    if private.get("source") == GCAL_SOURCE and private.get("omnisync_kind") != "class":
                        continue

                    title = ev.get("summary", "")
                    # Chercher un code de cours dans le titre : (235-215-LI) — parenthèses rondes
                    m = re.search(r"\((\d{3}-\d{3}-\w+)\)", title)
                    if not m:
                        continue
                    code = m.group(1)
                    start_info = ev.get("start", {})
                    end_info = ev.get("end", {})
                    if "dateTime" not in start_info:
                        continue
                    dt_start = datetime.fromisoformat(start_info["dateTime"])
                    dt_end = datetime.fromisoformat(end_info["dateTime"])
                    duration_hours = (dt_end - dt_start).total_seconds() / 3600
                    if not (1 <= duration_hours <= 5):
                        continue
                    key = (dt_start.date().isoformat(), code)
                    if key not in schedule:
                        schedule[key] = {
                            "time_start": dt_start.strftime("%H:%M"),
                            "time_end": dt_end.strftime("%H:%M"),
                            "room": ev.get("location", ""),
                        }
                page_token = result.get("nextPageToken")
                if not page_token:
                    break
        except Exception:
            continue

    return schedule


def _title(event: SchoolEvent) -> str:
    """Format: 'Remise: Titre du travail (235-215-LI)'"""
    prefix = {
        "assignment": "Remise",
        "exam":       "Exam",
        "class":      "Cours",
        "reading":    "Lire",
        "event":      "Annonce",
    }.get(event.kind, "Annonce")

    code_suffix = f" ({event.course_code})" if event.course_code else ""
    # Tronquer le titre si nécessaire pour garder le tout < 100 chars
    max_title = 100 - len(prefix) - 2 - len(code_suffix)  # ": " separator
    title = event.title[:max(max_title, 20)]

    return f"{prefix}: {title}{code_suffix}"


def _description(event: SchoolEvent) -> str:
    """Description structurée et lisible, sans redondance avec les champs titre/location."""
    lines = []

    # Champs structurés
    if event.course_code:
        lines.append(f"Cours: {event.course_code}")
    if event.teacher:
        lines.append(f"Prof: {event.teacher}")
    if event.room:
        lines.append(f"Local: {event.room}")

    # Contenu extra de la description (pondération, intro Moodle, etc.)
    raw = (event.description or "").strip()
    if raw:
        extra: list[str] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            # Sauter les lignes redondantes avec les champs structurés
            if line.startswith("Source:"):
                continue
            if line.startswith("Cours:") and event.course_code:
                continue
            if line.startswith("Local:") and event.room:
                continue
            if line.startswith("Prof:") and event.teacher:
                continue
            extra.append(line)

        if extra:
            if lines:
                lines.append("")
            lines.extend(extra)

    # Pied de page
    if lines:
        lines.append("")
    lines.append("---")
    lines.append("Source: OmniSync")

    return "\n".join(lines)


def _body(
    event: SchoolEvent,
    tz: str = "America/Toronto",
    course_schedule: dict[tuple[str, str], dict] | None = None,
) -> dict:
    body: dict = {
        "summary": _title(event),
        "description": _description(event),
        "colorId": COLOR.get(event.kind, COLOR["event"]),
        "extendedProperties": {
            "private": {
                "source": GCAL_SOURCE,
                "omnisync_uid": event.uid,
                "omnisync_kind": event.kind,
            }
        },
    }
    if event.room:
        body["location"] = event.room

    # ── Détermination du créneau horaire ──────────────────────────────────────
    if event.time_start:
        start = datetime.fromisoformat(f"{event.date_iso}T{event.time_start}:00")
        if event.time_end:
            end = datetime.fromisoformat(f"{event.date_iso}T{event.time_end}:00")
        else:
            end = start + timedelta(hours=1)
        body["start"] = {"dateTime": start.isoformat(), "timeZone": tz}
        body["end"] = {"dateTime": end.isoformat(), "timeZone": tz}
    else:
        # Tenter le créneau du cours existant (pour ancrer examen/remise dans le bon slot)
        slot = None
        if course_schedule and event.course_code and event.date_iso:
            slot = course_schedule.get((event.date_iso, event.course_code))

        if slot:
            start = datetime.fromisoformat(f"{event.date_iso}T{slot['time_start']}:00")
            end = datetime.fromisoformat(f"{event.date_iso}T{slot['time_end']}:00")
            body["start"] = {"dateTime": start.isoformat(), "timeZone": tz}
            body["end"] = {"dateTime": end.isoformat(), "timeZone": tz}
            if not body.get("location") and slot.get("room"):
                body["location"] = slot["room"]
        else:
            # Fallback par kind — jamais all-day
            t_start, t_end = _FALLBACK_TIMES.get(event.kind, ("08:00", "09:00"))
            start = datetime.fromisoformat(f"{event.date_iso}T{t_start}:00")
            end = datetime.fromisoformat(f"{event.date_iso}T{t_end}:00")
            body["start"] = {"dateTime": start.isoformat(), "timeZone": tz}
            body["end"] = {"dateTime": end.isoformat(), "timeZone": tz}

    # ── Rappels ───────────────────────────────────────────────────────────────
    reminders = _REMINDERS.get(event.kind, [])
    body["reminders"] = {
        "useDefault": False,
        "overrides": reminders,
    }

    return body


def _course_slot_body(slot: CourseSlot, tz: str = "America/Toronto") -> dict:
    """Corps d'un événement récurrent Google Calendar pour un créneau de cours."""
    until_str = slot.until_iso.replace("-", "") + "T235959Z"
    byday = ",".join(slot.days_ical)
    rrule = f"RRULE:FREQ=WEEKLY;BYDAY={byday};UNTIL={until_str}"

    start_dt = datetime.fromisoformat(f"{slot.dtstart_iso}T{slot.time_start}:00")
    if slot.time_end:
        end_dt = datetime.fromisoformat(f"{slot.dtstart_iso}T{slot.time_end}:00")
    else:
        end_dt = start_dt + timedelta(hours=2)

    code_suffix = f" ({slot.course_code})" if slot.course_code else ""
    summary = f"{slot.title}{code_suffix}"[:100]

    desc_lines = []
    if slot.teacher:
        desc_lines.append(f"Prof: {slot.teacher}")
    if slot.room:
        desc_lines.append(f"Local: {slot.room}")
    desc_lines.append("")
    desc_lines.append("---")
    desc_lines.append("Source: OmniSync (horaire récurrent)")
    description = "\n".join(desc_lines)

    body: dict = {
        "summary": summary,
        "description": description,
        "colorId": COLOR["class"],
        "recurrence": [rrule],
        "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": tz},
        "reminders": {
            "useDefault": False,
            "overrides": _REMINDERS.get("class", []),
        },
        "extendedProperties": {
            "private": {
                "source": GCAL_SOURCE,
                "omnisync_uid": slot.uid,
                "omnisync_kind": "class",
            }
        },
    }
    if slot.room:
        body["location"] = slot.room

    return body


def sync_events(events: list[SchoolEvent], *, dry_run: bool = False) -> dict[str, int]:
    include_past = os.environ.get("OMNISYNC_SYNC_PAST_EVENTS", "").lower() in {"1", "true", "yes"}
    today = date.today()

    all_omnivox_uids: set[str] = set()
    dated_events: list[SchoolEvent] = []
    past_count = 0

    for event in events:
        if not event.date_iso:
            continue
        all_omnivox_uids.add(event.uid)
        event_date = date.fromisoformat(str(event.date_iso))
        if not include_past and event_date < today:
            past_count += 1
        else:
            dated_events.append(event)

    skipped = len(events) - len(all_omnivox_uids)

    if dry_run:
        for event in events:
            date_label = event.date_iso or "date inconnue"
            action = "SKIP"
            if event.date_iso:
                event_date = date.fromisoformat(str(event.date_iso))
                action = "SYNC" if include_past or event_date >= today else "PAST"
            from omnisync.ui import vlog as _vlog
            _vlog(f"[DRY] {action} {event.kind.upper()} {date_label} - {_title(event)}")
        return {"created": len(dated_events), "updated": 0, "deleted": 0, "errors": 0}

    settings = load_settings()
    service = _get_service()
    calendar_id = _resolve_calendar_id(service, settings)
    existing = _fetch_existing(service, calendar_id)

    course_schedule = _fetch_course_schedule(service)
    if course_schedule:
        from omnisync.ui import vlog as _vlog
        _vlog(f"Google Calendar: {len(course_schedule)} creneaux de cours detectes pour le placement automatique.")

    counters = {"created": 0, "updated": 0, "deleted": 0, "errors": 0}
    synced_uids: set[str] = set()

    for event in dated_events:
        synced_uids.add(event.uid)
        body = _body(event, course_schedule=course_schedule)
        try:
            if event.uid in existing:
                service.events().update(
                    calendarId=calendar_id,
                    eventId=existing[event.uid],
                    body=body,
                ).execute()
                counters["updated"] += 1
            else:
                service.events().insert(calendarId=calendar_id, body=body).execute()
                counters["created"] += 1
        except Exception as exc:
            counters["errors"] += 1
            print(f"[GCAL] Erreur {event.uid}: {exc}")

    # Supprimer uniquement les events disparus d'Omnivox (pas les events passés toujours présents)
    # Ne pas toucher les cours récurrents (uid préfixe "course_") — gérés par sync_recurring_courses()
    for uid, event_id in existing.items():
        if uid.startswith("course_"):
            continue
        if uid not in all_omnivox_uids:
            try:
                service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
                counters["deleted"] += 1
            except Exception:
                pass

    if skipped:
        from omnisync.ui import vlog as _vlog
        _vlog(f"Google Calendar: {skipped} evenement(s) ignores (sans date).")
    if past_count:
        from omnisync.ui import vlog as _vlog
        _vlog(f"Google Calendar: {past_count} evenement(s) passes conserves dans le calendrier.")
    return counters


def sync_recurring_courses(
    course_slots: list[CourseSlot],
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Synchronise les créneaux de cours récurrents dans Google Calendar (RRULE)."""
    if dry_run:
        from omnisync.ui import vlog as _vlog
        for slot in course_slots:
            days = ",".join(slot.days_ical)
            _vlog(
                f"[DRY] COURS {slot.course_code} {days} "
                f"{slot.time_start}-{slot.time_end} "
                f"{slot.dtstart_iso} -> {slot.until_iso}"
            )
        return {"created": len(course_slots), "updated": 0, "deleted": 0, "errors": 0}

    if not course_slots:
        return {"created": 0, "updated": 0, "deleted": 0, "errors": 0}

    settings = load_settings()
    service = _get_service()
    calendar_id = _resolve_calendar_id(service, settings)
    existing = _fetch_existing(service, calendar_id)

    counters = {"created": 0, "updated": 0, "deleted": 0, "errors": 0}
    synced_uids: set[str] = set()

    for slot in course_slots:
        synced_uids.add(slot.uid)
        body = _course_slot_body(slot)
        try:
            if slot.uid in existing:
                service.events().update(
                    calendarId=calendar_id,
                    eventId=existing[slot.uid],
                    body=body,
                ).execute()
                counters["updated"] += 1
            else:
                service.events().insert(calendarId=calendar_id, body=body).execute()
                counters["created"] += 1
        except Exception as exc:
            counters["errors"] += 1
            print(f"[GCAL] Erreur cours {slot.uid}: {exc}")

    # Supprimer les cours récurrents qui ont disparu d'Omnivox
    for uid, event_id in existing.items():
        if uid.startswith("course_") and uid not in synced_uids:
            try:
                service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
                counters["deleted"] += 1
            except Exception:
                pass

    return counters
