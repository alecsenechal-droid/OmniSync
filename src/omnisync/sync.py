from __future__ import annotations

import os

from .calendar import sync_events, sync_recurring_courses
from .config import load_settings
from .notify import notify_if_configured
from .scraper import scrape_omnivox
from .scraper.adapter import extract_course_slots
from .storage import mark_deleted, upsert_events
from . import ui


def _friendly_scrape_error(msg: str) -> str:
    m = msg.lower()
    if "credentials" in m:
        return (
            "Fichier credentials.json introuvable.\n"
            "  --> Lance : run.bat auth-google"
        )
    if "timeout" in m or "timed out" in m:
        return (
            "Omnivox est trop lent a repondre (timeout).\n"
            "  Cause : portail en maintenance ou connexion lente\n"
            "  --> Reessaie dans quelques minutes : run.bat run"
        )
    if "error_0028" in m or "mot de passe incorrect" in m:
        return (
            "Identifiants Omnivox invalides (DA ou mot de passe).\n"
            "  --> Verifies sur omnivox.ca\n"
            "  --> Reconfigure : run.bat init"
        )
    if "mfa_required" in m or "mfa" in m:
        return (
            "Omnivox demande une verification supplementaire (MFA).\n"
            "  --> Relance avec le browser visible :\n"
            "      set HEADLESS=false\n"
            "      set OMNISYNC_MFA_WAIT_SECONDS=120\n"
            "      run.bat run"
        )
    return f"Erreur lors de la lecture d'Omnivox :\n  {msg}"


def run_sync(
    *,
    dry_run: bool = False,
    scrape_only: bool = False,
    calendar_dry_run: bool = False,
) -> int:
    mode = "dry" if (dry_run or calendar_dry_run) else ("scrape" if scrape_only else "live")
    ui.init()  # lire OMNISYNC_VERBOSE avant le premier is_verbose()
    ui.banner(mode)

    # En mode verbose, les modules s'affichent individuellement pendant le scraping.
    # En mode normal, un spinner unique indique que l'analyse est en cours.
    if ui.is_verbose():
        ui.info("Connexion a Omnivox en cours...")
        ui.info("Si Omnivox demande une verification sur ton telephone --> approuve-la maintenant.")
        print()
    else:
        _sp = ui.start_spinner("Analyse de ton Omnivox en cours...")

    try:
        events, module_stats, validation_report = scrape_omnivox(dry_run=dry_run)
    except RuntimeError as exc:
        if not ui.is_verbose():
            _sp.stop()
        msg = str(exc)
        ui.error(_friendly_scrape_error(msg))
        if os.getenv("OMNISYNC_DEBUG") or os.getenv("OMNISYNC_VERBOSE"):
            import traceback
            traceback.print_exc()
        notify_if_configured("Crash lors du scraping Omnivox", msg)
        return 1

    if not ui.is_verbose():
        _sp.stop()

    # Notify si anomalie
    if validation_report and validation_report.has_failures:
        notify_if_configured(
            "Anomalie detectee dans les donnees scrapees",
            "Le validateur a signale une chute anormale du nombre d'evenements.",
        )

    # SQLite upsert (silencieux)
    upsert_events(events)
    mark_deleted({e.uid for e in events})

    if scrape_only:
        ui.dashboard(
            mode="scrape",
            events=events,
            module_stats=module_stats,
            validation_report=validation_report,
        )
        return 0

    settings = load_settings()
    other_events, course_slots = extract_course_slots(events, sync_courses=settings.sync_courses)

    result = sync_events(other_events, dry_run=dry_run or calendar_dry_run)

    if course_slots or settings.sync_courses:
        course_result = sync_recurring_courses(course_slots, dry_run=dry_run or calendar_dry_run)
        total_errors = result["errors"] + course_result["errors"]
    else:
        course_result = {"created": 0, "updated": 0, "deleted": 0, "errors": 0}
        total_errors = result["errors"]

    cal_created = result["created"] + course_result["created"]
    cal_updated  = result["updated"]  + course_result["updated"]
    cal_deleted  = result["deleted"]  + course_result["deleted"]

    ui.dashboard(
        mode=mode,
        events=events,
        module_stats=module_stats,
        validation_report=validation_report,
        cal_created=cal_created,
        cal_updated=cal_updated,
        cal_deleted=cal_deleted,
    )

    if total_errors > 0:
        notify_if_configured(
            f"Erreurs lors de l'ecriture Google Calendar ({total_errors} erreur(s))",
            f"Events: creations={result['created']}, maj={result['updated']}, "
            f"suppressions={result['deleted']}, erreurs={result['errors']}",
        )
        return 1
    return 0
