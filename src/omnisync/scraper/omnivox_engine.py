"""
Moteur Playwright Omnivox pour OmniSync.
Ce fichier est en cours de découpage — les modules extraits sont importés ci-dessous.
"""
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional, Union

if sys.stdout.encoding and sys.stdout.encoding.lower() not in {"utf-8", "utf8"}:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from playwright.sync_api import (
    BrowserContext,
    FrameLocator,
    Locator,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
)

# ── Re-exports depuis les modules extraits ────────────────────────────────────
from .omnivox_models import (
    GCAL_COLOR, GCAL_TAG, JOURS_ICAL, JOURS_ABBR, JOURS_LIST,
    MOIS_FR_MAP, MOIS_ABBR_MAP, GCAL_SCOPES, EXAM_PATTERN, COURSE_CODE_RE,
    DEFAULT_TIMEOUT_MS,
    Config, ClassEvent, Assignment, LeaEvent, FinalExam,
    MioMessage, CourseNote, LeaCourse,
    lea_host, estd_host,
)
from .omnivox_helpers import (
    log, slugify, ensure_dir, safe_text,
    classify_assignment,
    _parse_fr_date, _parse_date_from_text, _parse_colonne_date_lea,
    _title_key, _parse_time_range,
    file_hash, smart_save_text, smart_save_bytes,
    _CT_EXTS, _strip_sid, _extract_pdf_url_from_viewer, download_document,
)
from .omnivox_loader import (
    MODULES,
    OMNIVOX_URL, OMNIVOX_BASE, LEA_BASE, ESTD_BASE, MIO_BASE, MOODLE_BASE,
    load_config,
)
from .omnivox_browser import (
    launch, wait_net, debug_screenshot, ensure_alive,
    get_frame, get_frame_safe,
    wait_postback, get_viewstate, wait_viewstate_change,
)
from .omnivox_auth import (
    safe_goto, recover_home, first_visible, click_first,
    _ensure_intr, _navigate_to_lea_via_sso, _ensure_lea, _ensure_estd,
    is_mfa_page, handle_mfa, _do_login_form,
    login, relogin_if_needed,
)

ContentRoot = Union[Page, FrameLocator]

# ── Re-exports scrapers ───────────────────────────────────────────────────────
from .scrape_mio import (
    scrape_notifications, scrape_mio,
    _wait_for_mio_frames, _mio_body_from_frame, _extract_mio_rows,
    _get_mio_body_modern, _mio_get_liste_url, _build_mio_messages,
)
from .scrape_horaire import scrape_horaire
from .scrape_notes import scrape_notes, _scrape_notes_from_links
from .scrape_lea import (
    scrape_cheminement, scrape_documents_officiels, scrape_actualites,
    scrape_lea_overview, scrape_lea_documents,
    _patch_disk_documents, _find_course_folder,
)
from .scrape_travaux import (
    scrape_lea_travaux,
    _scrape_travaux_course, _extract_title_date_from_cells,
    _scrape_course_name_from_page, _scrape_travaux_via_doce_links,
    _scrape_liste_travaux_etu, _merge_liste_travaux,
)
from .scrape_calendrier import (
    scrape_lea_calendrier, scrape_examens_finaux,
    scrape_actualites_events, scrape_lea_documents_deadlines,
    generate_ics,
)

# ── Anciens scrapers (supprimés) ──────────────────────────────────────────────
# sync_google_calendar, _obsidian_*, main(), _persist_to_db,
# _sync_calendar_incremental : supprimés — dead code, doublons de calendar/google.py
