from __future__ import annotations

import hashlib
import os
import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

from . import moodle_engine
from . import omnivox_engine as engine
from . import session_guard, snapshots
from .models import CourseSlot, SchoolEvent
from .validator import ModuleStats, ValidationReport, validate
from .. import ui

_TZ_UTC = ZoneInfo("UTC")
_TZ_MTL = ZoneInfo("America/Toronto")
_EXAM_RE = re.compile(r'\b(examen|exam|intra|final|test|quiz|[eé]valuation)\b', re.IGNORECASE)


def _uid(prefix: str, *parts: object) -> str:
    raw = "|".join(str(p or "") for p in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _assignment_to_event(item: Any) -> SchoolEvent | None:
    due_date = getattr(item, "due_date", None)
    course_code = getattr(item, "course_code", "") or None
    kind = getattr(item, "kind", "assignment") or "assignment"
    title = getattr(item, "title", "Remise Omnivox") or "Remise Omnivox"
    weight = getattr(item, "weight", None)
    time_start = getattr(item, "time_start", None) or None
    course_name = getattr(item, "course", "") or ""
    # Description : seulement l'info extra (pas redondante avec les champs SchoolEvent)
    desc_parts = []
    if course_name:
        desc_parts.append(f"Cours: {course_name}")
    if weight:
        try:
            w_float = float(weight)
            if w_float > 0:
                desc_parts.append(f"Pondération: {weight}%")
        except (ValueError, TypeError):
            desc_parts.append(f"Pondération: {weight}")
    description = "\n".join(desc_parts) or None
    ideval = getattr(item, "ideval", None)
    return SchoolEvent(
        uid=_uid("asgn", ideval or course_code, title, due_date),
        title=title,
        kind="exam" if str(kind).lower() in {"exam", "examen", "evaluation"} else "assignment",
        course_code=course_code,
        date_iso=due_date,
        time_start=time_start,
        description=description,
    )


def _lea_event_to_event(item: Any) -> SchoolEvent | None:
    date_iso = getattr(item, "date_iso", None)
    if not date_iso:
        return None
    course_code = getattr(item, "course_code", "") or None
    kind = getattr(item, "kind", "event") or "event"
    title = getattr(item, "title", "Evenement Omnivox") or "Evenement Omnivox"
    weight = getattr(item, "weight", None)
    course_name = getattr(item, "course_name", "") or ""
    time_start = getattr(item, "time_start", None) or None

    # Description : seulement l'info extra (pondération — le cours/heure sont dans les champs)
    desc_parts = []
    if course_name:
        desc_parts.append(f"Cours: {course_name}")
    if weight:
        try:
            w_float = float(str(weight).rstrip("%"))
            if w_float > 0:
                desc_parts.append(f"Pondération: {weight}")
        except (ValueError, TypeError):
            if weight:
                desc_parts.append(f"Pondération: {weight}")
    description = "\n".join(desc_parts) or None

    mapped_kind = {
        "evaluation": "exam",
        "travail": "assignment",
        "cours": "class",
        "lire": "reading",
    }.get(str(kind).lower(), "event")
    return SchoolEvent(
        uid=_uid("evt", course_code, title, date_iso, time_start),
        title=title,
        kind=mapped_kind,
        course_code=course_code,
        date_iso=date_iso,
        time_start=time_start,
        time_end=getattr(item, "time_end", None) or None,
        room=getattr(item, "room", None) or None,
        description=description,
    )


def _final_exam_to_event(item: Any) -> SchoolEvent | None:
    date_iso = getattr(item, "date_iso", None)
    if not date_iso:
        return None
    course_code = getattr(item, "course_code", "") or None
    course_name = getattr(item, "course_name", "") or course_code or "Examen final"
    return SchoolEvent(
        uid=_uid("exam", course_code, date_iso, getattr(item, "time_start", None)),
        title=f"Examen final — {course_name}",
        kind="exam",
        course_code=course_code,
        date_iso=date_iso,
        time_start=getattr(item, "time_start", None) or None,
        time_end=getattr(item, "time_end", None) or None,
        room=getattr(item, "room", None) or None,
        teacher=getattr(item, "teacher", None) or None,
        description=None,
    )


def _actualite_to_event(item: Any) -> SchoolEvent | None:
    date_iso = getattr(item, "date_iso", None)
    if not date_iso:
        return None
    title = getattr(item, "title", "Actualité") or "Actualité"
    return SchoolEvent(
        uid=_uid("news", title, date_iso),
        title=title,
        kind="event",
        course_code=None,
        date_iso=date_iso,
        time_start=None,
        description=None,
    )


def _document_deadline_to_event(item: Any) -> SchoolEvent | None:
    due_date = getattr(item, "due_date", None)
    if not due_date:
        return None
    course_code = getattr(item, "course_code", "") or None
    title = getattr(item, "title", "Lire document") or "Lire document"
    course = getattr(item, "course", "") or ""
    desc = f"Cours: {course}" if course else None
    return SchoolEvent(
        uid=_uid("doc", course_code, title, due_date),
        title=title,
        kind="reading",
        course_code=course_code,
        date_iso=due_date,
        time_start=None,
        description=desc,
    )


def _moodle_to_event(item: dict) -> SchoolEvent | None:
    """Convertit un dict Moodle (scrape_moodle) en SchoolEvent."""
    duedate = item.get("due_date", 0)
    if not duedate:
        return None

    # Unix timestamp UTC → America/Toronto
    dt_local = datetime.fromtimestamp(duedate, tz=_TZ_UTC).astimezone(_TZ_MTL)
    date_iso = dt_local.date().isoformat()
    time_start = dt_local.strftime("%H:%M")

    # Normaliser le code cours : "235-203-LI 00" → "235-203-LI"
    shortname = (item.get("course_shortname") or "").strip()
    course_code = shortname.split()[0] if shortname else None

    title = (item.get("title") or "Remise Moodle").strip()
    kind = "exam" if _EXAM_RE.search(title) else "assignment"

    desc_parts = []
    fullname = item.get("course_fullname", "")
    if fullname:
        desc_parts.append(f"Cours: {fullname}")
    intro = (item.get("intro") or "").strip()
    if intro:
        desc_parts.append(intro[:200])
    description = "\n".join(desc_parts) or None

    return SchoolEvent(
        uid=_uid("moodle", course_code, title, date_iso),
        title=title,
        kind=kind,
        course_code=course_code,
        date_iso=date_iso,
        time_start=time_start,
        description=description,
    )


def _dedupe(events: list[SchoolEvent]) -> list[SchoolEvent]:
    by_uid: dict[str, SchoolEvent] = {}
    for event in events:
        existing = by_uid.get(event.uid)
        if existing is None or (not existing.date_iso and event.date_iso):
            by_uid[event.uid] = event

    # Déduplication sémantique : même titre + même date = même événement, peu importe la source.
    # Priorité : version avec time_start > version avec kind="assignment" > autre
    by_semantic: dict[tuple[str, str], SchoolEvent] = {}
    for event in by_uid.values():
        title_key = " ".join(event.title.lower().replace("—", "-").split())
        key = (title_key, event.date_iso or "")
        existing = by_semantic.get(key)
        if existing is None:
            by_semantic[key] = event
            continue
        # Préférer l'événement avec heure exacte (vient du calendrier LEA)
        if event.time_start and not existing.time_start:
            by_semantic[key] = event
        # Préférer si la date était inconnue avant
        elif not existing.date_iso and event.date_iso:
            by_semantic[key] = event

    return list(by_semantic.values())


_ICAL_DAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def extract_course_slots(
    events: list[SchoolEvent],
    sync_courses: bool = True,
) -> tuple[list[SchoolEvent], list[CourseSlot]]:
    """Sépare les événements de cours (kind='class') des autres.

    Si sync_courses=True : extrait les class events, les groupe en CourseSlot récurrents,
    et les retire de la liste principale (évite les doublons avec les recurring events).
    Si sync_courses=False : retourne les events tels quels, aucun CourseSlot.
    """
    if not sync_courses:
        return events, []

    class_events = [e for e in events if e.kind == "class" and e.date_iso and e.time_start]
    other_events = [e for e in events if not (e.kind == "class" and e.date_iso and e.time_start)]

    slots = _build_course_slots(class_events)
    return other_events, slots


def _build_course_slots(class_events: list[SchoolEvent]) -> list[CourseSlot]:
    """Groupe les occurrences de cours individuelles en CourseSlot récurrents."""
    groups: dict[tuple[str, str, str], dict] = {}

    for ev in class_events:
        key = (ev.course_code or "", ev.time_start or "", ev.time_end or "")
        if key not in groups:
            groups[key] = {
                "course_code": ev.course_code or "",
                "title": ev.title,
                "time_start": ev.time_start or "",
                "time_end": ev.time_end or "",
                "room": ev.room,
                "teacher": ev.teacher,
                "dates": [],
            }
        groups[key]["dates"].append(ev.date_iso)
        if not groups[key]["room"] and ev.room:
            groups[key]["room"] = ev.room
        if not groups[key]["teacher"] and ev.teacher:
            groups[key]["teacher"] = ev.teacher

    slots: list[CourseSlot] = []
    for (code, ts, te), data in groups.items():
        dates = sorted(set(data["dates"]))
        if not dates:
            continue

        date_objs = [date.fromisoformat(d) for d in dates]
        weekdays = sorted(set(d.weekday() for d in date_objs))
        days_ical = tuple(_ICAL_DAYS[w] for w in weekdays)

        raw = f"{code}|{ts}|{te}"
        uid = f"course_{hashlib.sha1(raw.encode()).hexdigest()[:12]}"

        slots.append(CourseSlot(
            uid=uid,
            course_code=code,
            title=data["title"],
            days_ical=days_ical,
            time_start=ts,
            time_end=te,
            room=data["room"],
            teacher=data["teacher"],
            dtstart_iso=dates[0],
            until_iso=dates[-1],
        ))

    return slots


# ── Configuration des scrapers ────────────────────────────────────────────────
# (module_name, scraper_fn, converter, expected_domain_fragment)
_SCRAPER_REGISTRY = [
    ("lea_assignments",     engine.scrape_lea_travaux,               _assignment_to_event,       "lea"),
    ("lea_calendar",        engine.scrape_lea_calendrier,            _lea_event_to_event,        "lea"),
    ("final_exams",         engine.scrape_examens_finaux,            _final_exam_to_event,       "estd"),
    ("actualites",          engine.scrape_actualites_events,         _actualite_to_event,        "intr"),
    ("documents_deadlines", engine.scrape_lea_documents_deadlines,   _document_deadline_to_event,"lea"),
]


def _scrape_live() -> tuple[list[SchoolEvent], dict[str, ModuleStats], ValidationReport]:
    from omnisync.config import load_settings

    settings = load_settings()
    config = engine.load_config()

    # ── Garde MFA ─────────────────────────────────────────────────────────────
    original_handle_mfa = engine.handle_mfa

    def guarded_handle_mfa(page: Any, cfg: Any, wait_seconds: int = 90) -> None:
        if not engine.is_mfa_page(page):
            return
        wait_raw = os.environ.get("OMNISYNC_MFA_WAIT_SECONDS", "").strip()
        if wait_raw:
            wait = int(wait_raw)
        elif not getattr(cfg, "headless", True):
            wait = 120
        else:
            wait = 0
        if wait <= 0:
            try:
                engine.debug_screenshot(page, "omnisync_mfa_required")
            except Exception:
                pass
            raise RuntimeError(
                "MFA_REQUIRED: Omnivox demande une validation humaine. "
                "Relancez avec HEADLESS=false et OMNISYNC_MFA_WAIT_SECONDS=120."
            )
        original_handle_mfa(page, cfg, wait_seconds=wait)

    engine.handle_mfa = guarded_handle_mfa

    # ── Démarrer le run (snapshots horodatés) ─────────────────────────────────
    run_dir = snapshots.start_run()

    events: list[SchoolEvent] = []
    module_stats: dict[str, ModuleStats] = {}
    playwright_instance = None
    context = None

    # Sélectionner les scrapers actifs selon config
    feature_map = {
        "lea_assignments":     settings.sync_assignments,
        "lea_calendar":        settings.sync_schedule,
        "final_exams":         settings.sync_exams,
        "actualites":          settings.sync_actualites,
        "documents_deadlines": settings.sync_documents,
    }
    active = [(n, fn, cv, dom) for (n, fn, cv, dom) in _SCRAPER_REGISTRY
              if feature_map.get(n, True)]

    # Calculer le total de modules pour l'affichage de progression
    n_moodle = 1 if (settings.sync_moodle and settings.moodle_url) else 0
    n_horaire = 1 if settings.sync_courses else 0
    ui.init(module_total=len(active) + n_moodle + n_horaire)

    try:
        playwright_instance = sync_playwright().start()
        context, page = engine.launch(playwright_instance, config)

        # Login
        try:
            engine.login(page, config)
        except RuntimeError as exc:
            if "/intr/" in page.url:
                ui.vlog("Login Omnivox: session active apres MFA.")
            elif "ERROR_0028" in page.url or "ERROR_0028" in str(exc):
                raise RuntimeError(
                    "Connexion Omnivox refusee (ERROR_0028): DA ou mot de passe incorrect. "
                    "Relancez: run.bat init"
                ) from exc
            else:
                raise

        # ── Module par module ─────────────────────────────────────────────────
        for mod_name, fn, converter, expected_domain in active:
            ui.module_start(mod_name)
            try:
                # 1. Session Guard — vérifie login redirect / page cassée
                # On ne vérifie PAS le domaine ici car le scraper n'a pas encore navigué.
                # Le domaine attendu sera correct APRÈS la navigation interne du scraper.
                guard = session_guard.check(page)  # sans expected_domain
                ui.vlog(str(guard))

                if not guard.valid and guard.severity == "fail":
                    ui.vlog("Session invalide. Tentative de recuperation...")
                    try:
                        engine.recover_home(page, config)
                        guard2 = session_guard.check(page, expected_domain)
                        ui.vlog(str(guard2))
                        if not guard2.valid and guard2.severity == "fail":
                            raise RuntimeError("Recuperation session echouee")
                    except Exception as rec_exc:
                        ui.module_error(mod_name, str(rec_exc))
                        engine.debug_screenshot(page, f"omnisync_guard_{mod_name}")
                        module_stats[mod_name] = ModuleStats(
                            module=mod_name, count=0,
                            snapshot_path=str(snapshots.save(page, f"{mod_name}_guard_fail") or ""),
                        )
                        continue

                # 2. Scraper
                rows = fn(page, config) or []
                ui.module_done(mod_name, len(rows))

                # 3. Snapshot HTML (après scraping, pendant que la page est encore là)
                count_with_dates = sum(
                    1 for r in rows
                    if getattr(r, "due_date", None) or getattr(r, "date_iso", None)
                )
                snap_path = snapshots.save(page, mod_name, extra={
                    "items_found": len(rows),
                    "items_with_dates": count_with_dates,
                })

                # 4. Conversion → SchoolEvent
                for row in rows:
                    event = converter(row)
                    if event:
                        events.append(event)

                module_stats[mod_name] = ModuleStats(
                    module=mod_name,
                    count=len(rows),
                    count_with_dates=count_with_dates,
                    snapshot_path=str(snap_path) if snap_path else "",
                )

            except Exception as exc:
                ui.module_error(mod_name, str(exc))
                try:
                    engine.debug_screenshot(page, f"omnisync_{mod_name}_error")
                    engine.recover_home(page, config)
                except Exception:
                    pass
                module_stats[mod_name] = ModuleStats(module=mod_name, count=0)

        # ── Moodle ────────────────────────────────────────────────────────────
        if settings.sync_moodle and settings.moodle_url:
            ui.module_start("moodle")
            try:
                from omnisync import paths as _paths
                from omnisync.config import get_moodle_password
                moodle_items: list[dict] = []

                # Priorité 1 : token direct configuré dans config.toml [moodle] token = ...
                if settings.moodle_token:
                    ui.vlog("Mode token direct (bypass SSO)...")
                    moodle_items = moodle_engine.scrape_moodle_with_token(
                        settings.moodle_url, settings.moodle_token
                    )

                else:
                    ms_password = get_moodle_password(settings.da) if settings.da else None
                    if not ms_password:
                        ui.module_error("moodle", "mot de passe Moodle introuvable")
                    else:
                        # Priorité 2 : auth native REST (cégeps sans SSO)
                        try:
                            moodle_items = moodle_engine.scrape_moodle(
                                settings.moodle_url, settings.da or "", ms_password
                            )
                        except moodle_engine.MoodleAuthError:
                            # Priorité 3 : SSO Microsoft avec session persistante
                            ms_email = settings.moodle_ms_email or ""
                            if not ms_email:
                                ui.module_error("moodle", "ms_email absent dans config.toml")
                            else:
                                session_path = str(_paths.moodle_session_path())
                                ui.vlog(f"Auth native echouee -- tentative SSO ({ms_email})...")
                                moodle_items = moodle_engine.scrape_moodle_with_browser(
                                    context.browser,
                                    settings.moodle_url,
                                    ms_email,
                                    ms_password,
                                    session_path=session_path,
                                )

                moodle_events = 0
                for item in moodle_items:
                    ev = _moodle_to_event(item)
                    if ev:
                        events.append(ev)
                        moodle_events += 1
                ui.module_done("moodle", len(moodle_items),
                               f"{moodle_events} avec date" if moodle_events != len(moodle_items) else "")
                module_stats["moodle"] = ModuleStats(
                    module="moodle",
                    count=len(moodle_items),
                    count_with_dates=moodle_events,
                )
            except moodle_engine.MoodleMFARequired as exc:
                ui.module_error("moodle", f"MFA requis -- relancez run.bat init-moodle")
            except moodle_engine.MoodleAuthError as exc:
                ui.module_error("moodle", f"auth echouee -- {exc}")
            except Exception as exc:
                ui.module_error("moodle", str(exc))

        # ── Horaire (cours récurrents) ────────────────────────────────────────
        if settings.sync_courses:
            ui.module_start("horaire")
            try:
                from datetime import timedelta
                class_events = engine.scrape_horaire(page, config)
                if class_events:
                    today = date.today()
                    if today.month <= 6:
                        sem_start = date(today.year, 1, 15)
                        sem_end = date(today.year, 4, 30)
                    else:
                        sem_start = date(today.year, 8, 28)
                        sem_end = date(today.year, 12, 15)
                    occ_count = 0
                    for ce in class_events:
                        d = sem_start
                        while d <= sem_end:
                            day_fr = engine.JOURS_LIST[d.weekday()]
                            if day_fr in ce.days_fr:
                                events.append(SchoolEvent(
                                    uid=f"class_{ce.course_code}_{d.isoformat()}_{(ce.start_time or '').replace(':', '')}",
                                    title=ce.course or ce.course_code,
                                    kind="class",
                                    course_code=ce.course_code,
                                    date_iso=d.isoformat(),
                                    time_start=ce.start_time or None,
                                    time_end=ce.end_time or None,
                                    room=ce.room or None,
                                    teacher=ce.teacher or None,
                                ))
                                occ_count += 1
                            d += timedelta(days=1)
                    ui.module_done("horaire", len(class_events),
                                   f"{occ_count} occurrences ({sem_start} -> {sem_end})")
                else:
                    ui.module_done("horaire", 0)
            except Exception as exc:
                ui.module_error("horaire", str(exc))

    finally:
        if context is not None:
            context.close()
        if playwright_instance is not None:
            playwright_instance.stop()
        engine.handle_mfa = original_handle_mfa

    # ── Filtre actualités par mots-clés ──────────────────────────────────────
    # Liste utilisée si config vide — évite le "liste vide = tout passe" footgun
    _DEFAULT_ACTUALITES_KW = [
        "hockey", "basketball", "volleyball", "soccer", "football", "match", "tournoi",
        "concert", "soiree", "conference", "expo", "spectacle",
        "inscription", "bourse", "stage", "emploi",
    ]
    kw = settings.actualites_keywords or _DEFAULT_ACTUALITES_KW
    if settings.sync_actualites:
        before = len(events)
        events = [
            e for e in events
            if not (
                e.kind == "event"
                and e.course_code is None
                and not any(k.lower() in e.title.lower() for k in kw)
            )
        ]
        filtered = before - len(events)
        if filtered:
            ui.vlog(f"Actualites: {filtered} annonce(s) filtrees (hors mots-cles)")

    # ── Validation post-scrape ────────────────────────────────────────────────
    report = validate(module_stats, run_dir)
    if ui.is_verbose():
        report.print()

    return _dedupe(events), module_stats, report


def scrape_omnivox(
    *, dry_run: bool = False
) -> tuple[list[SchoolEvent], dict[str, ModuleStats] | None, ValidationReport | None]:
    """
    Scrape Omnivox ou retourne des données de démo.

    Returns:
        (events, module_stats, validation_report)
        module_stats et validation_report sont None en dry-run.
    """
    if dry_run:
        return (
            [
                SchoolEvent(
                    uid="demo_assignment_001",
                    title="Demo remise - rapport de laboratoire",
                    kind="assignment",
                    course_code="XXX-000",
                    date_iso="2026-06-01",
                    description="Evenement de demonstration.",
                ),
                SchoolEvent(
                    uid="demo_exam_001",
                    title="Demo examen final",
                    kind="exam",
                    course_code="XXX-000",
                    date_iso="2026-06-05",
                    time_start="09:00",
                    time_end="12:00",
                    room="Local a confirmer",
                ),
            ],
            None,
            None,
        )
    return _scrape_live()
