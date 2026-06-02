"""
Scraper : horaire de cours depuis LÉA.
Responsabilité unique : extraire les créneaux de cours (jours, heures, prof).
"""
import re
from typing import Optional

from playwright.sync_api import Page

from .omnivox_models import Config, ClassEvent, COURSE_CODE_RE, JOURS_ABBR
from .omnivox_helpers import log
from .omnivox_browser import wait_net
from .omnivox_auth import _ensure_lea, _ensure_intr, click_first


def scrape_horaire(page: Page, config: Config) -> list[ClassEvent]:
    """Scrape l'horaire depuis la page LÉA (via SSO)."""
    log(f" [{config.slug}] === Horaire de cours ===")
    _ensure_lea(page, config)
    log(f"  [{config.slug}] Page LEA: {page.url[:60]}")

    events: list[ClassEvent] = []
    try:
        body = page.locator("body").inner_text(timeout=10_000)
    except Exception:
        return []

    # Format LÉA: "203-003-LI  00001  Physique appliquée...  mar 08h00  Mustapha Samri"
    lines = body.splitlines()
    for line in lines:
        line = line.strip()
        if not COURSE_CODE_RE.search(line):
            continue
        code_m = COURSE_CODE_RE.search(line)
        if not code_m:
            continue
        code = code_m.group(1)

        schedule_pattern = re.compile(
            r'(lun|mar|mer|jeu|ven|sam|dim)\s+(\d{1,2})[h:](\d{0,2})',
            re.IGNORECASE
        )
        slots = schedule_pattern.findall(line)
        if not slots:
            continue

        days_fr = []
        start_time = ""
        for slot in slots:
            day_abbr, hour, minute = slot
            day_full = JOURS_ABBR.get(day_abbr.lower(), day_abbr.lower())
            if day_full not in days_fr:
                days_fr.append(day_full)
            if not start_time:
                minute = minute or "00"
                start_time = f"{int(hour):02d}:{minute:0<2s}"

        teacher = ""
        parts = [p.strip() for p in re.split(r'\s{2,}|\t', line) if p.strip()]
        if parts:
            teacher = parts[-1] if not COURSE_CODE_RE.search(parts[-1]) else ""

        title_m = re.search(r'\d{3}-\d{3}-\w{2}\s+\d{5}\s+(.+?)\s{2,}', line)
        title = title_m.group(1).strip() if title_m else code

        events.append(ClassEvent(
            course=title,
            course_code=code,
            days_fr=days_fr,
            start_time=start_time,
            end_time="",
            room="",
            teacher=teacher,
        ))
        log(f"  [{config.slug}] {code} — {title[:40]} — {days_fr} {start_time}")

    if not events:
        log(f" [{config.slug}] Horaire LÉA: aucun cours parsé — essai ESTD")
        _ensure_intr(page, config)
        click_first(page, [
            "a[href*='hrre'][href*='Horaire']",
            "a:has-text('Horaire de cours')",
        ], config.timeout_ms)
        wait_net(page, config.timeout_ms)
        try:
            body2 = page.locator("body").inner_text(timeout=8_000)
            for line in body2.splitlines():
                line = line.strip()
                m = COURSE_CODE_RE.search(line)
                if not m:
                    continue
                code = m.group(1)
                parts = re.split(r'\s{2,}', line)
                title = parts[1].strip() if len(parts) > 1 else code
                teacher = parts[-1].strip() if len(parts) > 3 else ""
                events.append(ClassEvent(
                    course=title, course_code=code,
                    days_fr=[], start_time="", end_time="", room="", teacher=teacher,
                ))
                log(f"  [{config.slug}] {code} — {title[:40]}")
        except Exception:
            pass

    return events
