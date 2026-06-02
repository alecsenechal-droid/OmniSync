"""
Scrapers : calendrier LEA, examens finaux, actualités-events, deadlines documents, ICS.
Responsabilité unique : extraction des événements datés depuis LÉA et génération ICS.
"""
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from .omnivox_models import (
    Config, ClassEvent, Assignment, LeaEvent, FinalExam,
    JOURS_ICAL, JOURS_LIST,
)
from .omnivox_helpers import log, safe_text, _parse_fr_date, _parse_date_from_text, _parse_time_range
from .omnivox_browser import wait_net, get_viewstate, wait_viewstate_change
from .omnivox_auth import safe_goto, recover_home, _ensure_lea, click_first


def scrape_lea_calendrier(page: Page, config: Config) -> list[LeaEvent]:
    """
    Scrape le calendrier LÉA (DivToolTip — structure 2026 Limoilou).

    Extrait les événements depuis les div.divToolTip avec inner div[style*="white-space"].
    Chaque tooltip contient : code de cours, type, titre, date, heure, pondération.
    Navigation vers les mois précédents pour couvrir toute la session.
    """
    log(f" [{config.slug}] === LÉA — Calendrier ===")
    _ensure_lea(page, config)
    try:
        safe_goto(page, "lea_calendrier", config)
    except RuntimeError as exc:
        log(f"  [{config.slug}] Calendrier LEA via URL directe impossible: {exc}")
        click_first(page, ["a[href*='clre']", "a:has-text('Calendrier')"], config.timeout_ms)
        wait_net(page, config.timeout_ms)
    log(f"  [{config.slug}] Calendrier: {page.url}")

    try:
        page.wait_for_function(
            "() => document.querySelectorAll('div.divToolTip').length > 0"
            " || document.querySelectorAll('table').length > 0",
            timeout=12_000,
        )
    except PlaywrightTimeoutError:
        log(f" [{config.slug}] Aucune DivToolTip détectée après 12s")

    _JS_EXTRACT_TOOLTIPS = r"""
    () => {
        const MOIS = {
            'janvier':1,'f\xe9vrier':2,'fevrier':2,'mars':3,'avril':4,'mai':5,'juin':6,
            'juillet':7,'ao\xfbt':8,'aout':8,'septembre':9,'octobre':10,'novembre':11,'d\xe9cembre':12
        };
        function parseDate(txt) {
            if (!txt) return '';
            txt = txt.replace(/\xa0/g,' ');
            const m = txt.match(/(\d{1,2})(?:er|e)?\s+(\w+)(?:\s+(\d{4}))?/i);
            if (!m) return '';
            const mon = MOIS[m[2].toLowerCase()];
            if (!mon) return '';
            const yr = m[3] || String(new Date().getFullYear());
            return yr + '-' + String(mon).padStart(2,'0') + '-' + String(parseInt(m[1],10)).padStart(2,'0');
        }
        function parseTime(txt) {
            if (!txt) return '';
            const m = txt.match(/(\d{1,2})[h:](\d{2})/);
            if (!m) return '';
            return String(parseInt(m[1],10)).padStart(2,'0') + ':' + m[2];
        }

        const courseNames = {};
        document.querySelectorAll('[onclick*="DoSelect"]').forEach(function(el) {
            const oc = el.getAttribute('onclick') || '';
            const cm = oc.match(/DoSelect\('groupe',\s*'(\w+)'/);
            if (!cm) return;
            const raw = cm[1];
            const code = raw.replace(/(\d{3})(\d{3})(\w+)/, '$1-$2-$3');
            const span = el.querySelector('span');
            if (span) {
                const nm = (span.textContent || '').replace(/\.\.\.$/,'').trim();
                if (nm) courseNames[code] = nm;
            }
        });

        const results = [];
        document.querySelectorAll('div.divToolTip').forEach(function(toolDiv) {
            const inner = toolDiv.querySelector('div[style*="white-space"]');
            if (!inner) return;

            const rawHtml = inner.innerHTML
                .replace(/<br\s*\/?>/gi, '\n')
                .replace(/<[^>]+>/g, '')
                .replace(/\xa0/g, ' ')
                .replace(/&amp;/g, '&')
                .replace(/&lt;/g, '<')
                .replace(/&gt;/g, '>')
                .replace(/&[a-z]+;/g, ' ');

            const lines = rawHtml.split('\n').map(function(l){return l.trim();}).filter(Boolean);
            if (!lines.length) return;
            const full = lines.join('\n');

            var courseCode = '', type = '', title = '', dateIso = '', timeStr = '', ponderation = '', isCalendrier = false;

            const classeM = full.match(/Classe:\s*([\d\-A-Za-z]+)\s+gr\.\s*(\d+)/);
            if (classeM) courseCode = classeM[1].trim();

            if (lines[0] === 'Calendrier scolaire') {
                isCalendrier = true;
                title = lines.slice(1).join(' - ');
                type = 'calendrier';
            } else {
                for (var i = 0; i < lines.length; i++) {
                    var l = lines[i];
                    if (/^(\xc9valuation|Evaluation|Travail \xe0 remettre|Avoir lu le document|S\xe9ance de tutorat|Examen)/i.test(l)) {
                        type = l;
                        if (i+1 < lines.length && !/^(Remise via|Pond\xe9ration|Date|Classe:)/i.test(lines[i+1])) {
                            title = lines[i+1];
                        }
                        break;
                    }
                }
            }

            const pondM = full.match(/Pond.ration\s*([\d.,]+\s*%?)/i);
            if (pondM) ponderation = pondM[1].trim();

            const remiseM = full.match(/Date de remise:\s*(.+?)(?:\s*\xe0\s*([\d:h]+))?\s*$/im);
            if (remiseM) {
                dateIso = parseDate(remiseM[1]);
                if (remiseM[2]) timeStr = parseTime(remiseM[2]);
            }

            if (!dateIso) {
                const dateM = full.match(/(?:^|\n)Date\s+(\d{1,2}(?:er|e)?\s+\w+(?:\s+\d{4})?)/im);
                if (dateM) dateIso = parseDate(dateM[1]);
            }

            if (!dateIso) {
                var el = toolDiv.parentElement;
                while (el && el.tagName !== 'TD') el = el.parentElement;
                if (el) {
                    var dateLink = el.querySelector('a.NumeroJourMois');
                    if (!dateLink) {
                        var parentRow = el.parentElement;
                        if (parentRow) {
                            var allTd = parentRow.querySelectorAll('td');
                            for (var ti = 0; ti < allTd.length && !dateLink; ti++) {
                                dateLink = allTd[ti].querySelector('a.NumeroJourMois');
                            }
                        }
                    }
                    if (dateLink) {
                        var tm = dateLink.title.match(/le\s+(\d{1,2})\s+(\w+)\s+(\d{4})/i);
                        if (tm) {
                            var mon = MOIS[tm[2].toLowerCase()];
                            if (mon) dateIso = tm[3] + '-' + String(mon).padStart(2,'0') + '-' + String(parseInt(tm[1],10)).padStart(2,'0');
                        }
                    }
                }
            }

            if (!dateIso) return;

            const courseName = courseCode ? (courseNames[courseCode] || '') : '';
            results.push({
                course_code: courseCode,
                course_name: courseName,
                type: type,
                title: title,
                date_iso: dateIso,
                time_str: timeStr,
                ponderation: ponderation,
                is_calendrier: isCalendrier,
            });
        });
        return results;
    }
    """

    def _extract_tooltips(pg: Page) -> list[dict]:
        try:
            return pg.evaluate(_JS_EXTRACT_TOOLTIPS) or []
        except Exception as exc:
            log(f"    [{config.slug}] JS DivToolTip error: {exc}")
            return []

    def _goto_month(pg: Page, yr: int, mo: int) -> bool:
        base_url = pg.url.split('?')[0]
        url = (
            f"{base_url}?mode=mois&annee={yr}&mois={mo}"
            f"&jour=1&cal=somm&anneeselect={yr}&moisselect={mo}"
        )
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)
            pg.wait_for_function(
                "() => document.querySelectorAll('div.divToolTip').length > 0"
                " || document.querySelectorAll('table').length > 0",
                timeout=8_000,
            )
            return True
        except Exception:
            return False

    all_raw: list[dict] = []
    seen_keys: set[str] = set()

    def _add_raw(raw_list: list[dict]) -> int:
        added = 0
        for r in raw_list:
            k = f"{r.get('date_iso')}|{r.get('title')}|{r.get('course_code')}"
            if k not in seen_keys:
                seen_keys.add(k)
                all_raw.append(r)
                added += 1
        return added

    cur_raw = _extract_tooltips(page)
    n = _add_raw(cur_raw)
    log(f"  [{config.slug}] Mois courant: {n} événements trouvés")

    today = date.today()
    semester_start = 1 if today.month <= 6 else 9
    for delta in range(1, 7):
        yr, mo = today.year, today.month - delta
        while mo <= 0:
            mo += 12
            yr -= 1
        if yr < today.year or (yr == today.year and mo < semester_start):
            break
        if _goto_month(page, yr, mo):
            n = _add_raw(_extract_tooltips(page))
            log(f"  [{config.slug}] {yr}-{mo:02d}: {n} nouveaux événements")

    yr, mo = today.year, today.month + 1
    if mo > 12:
        mo, yr = 1, yr + 1
    if _goto_month(page, yr, mo):
        n = _add_raw(_extract_tooltips(page))
        log(f"  [{config.slug}] {yr}-{mo:02d}: {n} nouveaux événements")

    events: list[LeaEvent] = []
    for raw in all_raw:
        date_iso = raw.get("date_iso", "") or ""
        title    = (raw.get("title", "") or "").strip()
        if not date_iso or not title:
            continue
        course    = raw.get("course_code", "") or ""
        cname     = raw.get("course_name", "") or ""
        type_str  = raw.get("type", "") or ""
        time_str  = raw.get("time_str", "") or ""
        ponderat  = raw.get("ponderation", "") or ""
        is_cal    = raw.get("is_calendrier", False)

        if is_cal:
            kind = "autre"
        elif re.search(r'travail\s+\xe0\s+remettre|remise', type_str, re.IGNORECASE):
            kind = "travail"
        elif re.search(r'\xe9valuation|evaluation|examen', type_str, re.IGNORECASE):
            kind = "evaluation"
        elif re.search(r'avoir\s+lu|document|lire', type_str, re.IGNORECASE):
            kind = "lire"
        elif re.search(r'cours|p\xe9riode', type_str, re.IGNORECASE):
            kind = "cours"
        else:
            kind = "autre"

        events.append(LeaEvent(
            date_iso=date_iso,
            time_start=time_str,
            time_end="",
            kind=kind,
            title=title,
            course_code=course,
            course_name=cname,
            room="",
            weight=ponderat,
        ))

    cours_n = sum(1 for e in events if e.kind == "cours")
    dead_n  = sum(1 for e in events if e.kind in ("travail", "evaluation"))
    lire_n  = sum(1 for e in events if e.kind == "lire")
    log(f"  [{config.slug}] Calendrier: {len(events)} événements ({cours_n} cours, {dead_n} deadlines, {lire_n} lectures)")
    return events


def scrape_examens_finaux(page: Page, config: Config) -> list[FinalExam]:
    """Scrape l'horaire d'examens finaux depuis ESTD."""
    log(f" [{config.slug}] === Examens finaux ===")
    try:
        safe_goto(page, "examens", config)
    except RuntimeError as exc:
        log(f"  [{config.slug}] Examens finaux: inaccessible ({exc})")
        recover_home(page, config)
        return []

    sel_el = page.locator(
        "select#ctl00_cntFormulaire_ddlSession, "
        "select[id*='ddlSession'], "
        "select[name*='ddlSession']"
    ).first
    try:
        if sel_el.count():
            all_opts = [(opt.get_attribute("value") or "", (opt.inner_text() or "").strip())
                        for opt in sel_el.locator("option").all()]
            selected_label = next((lbl for _, lbl in all_opts if lbl), "")

            target_val: str = ""
            if config.term:
                parts = config.term.split("-", 1)
                if len(parts) == 2:
                    year, session_name = parts
                    for val, lbl in all_opts:
                        if year in lbl and session_name.lower() in lbl.lower():
                            target_val = val
                            break

            if target_val:
                old_vs = get_viewstate(page)
                sel_el.select_option(value=target_val)
                submit = page.locator("input[type='submit'], button[type='submit']").first
                if submit.count():
                    submit.click()
                wait_viewstate_change(page, old_vs, timeout_ms=8_000)
                log(f"  [{config.slug}] Session examens: '{config.term}' sélectionnée")
            else:
                log(f"  [{config.slug}] Session examens: auto ('{selected_label}' — options: {[l for _, l in all_opts]})")
    except Exception as exc:
        log(f"  [{config.slug}] Session examens: erreur sélection ({exc}), session par défaut utilisée")

    try:
        body = page.locator("body").inner_text(timeout=10_000)
    except Exception:
        return []

    exams: list[FinalExam] = []
    current_date: Optional[str] = None
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        d = _parse_fr_date(line)
        if d:
            current_date = d
            continue
        if not current_date:
            continue
        ts, te = _parse_time_range(line)
        if ts and te:
            exams.append(FinalExam(
                date_iso=current_date, time_start=ts, time_end=te,
                course_code="", course_name="", room="", teacher="",
            ))
            continue
        if not exams:
            continue
        if line.startswith("Local "):
            exams[-1].room = line[6:].strip()
        elif line.startswith("Cours:"):
            from .omnivox_models import COURSE_CODE_RE
            m = COURSE_CODE_RE.search(line)
            if m:
                exams[-1].course_code = m.group(1)
        elif line.startswith("Enseignant:"):
            exams[-1].teacher = line.split(":", 1)[1].strip()
        elif not exams[-1].course_name:
            skip_prefixes = ("Local ", "Cours:", "Enseignant:", "Cet examen")
            if (not any(line.startswith(p) for p in skip_prefixes)
                    and not _parse_time_range(line)[0]
                    and not _parse_fr_date(line)
                    and len(line) > 3):
                exams[-1].course_name = line

    for ex in exams:
        log(f"  [{config.slug}] {ex.date_iso} {ex.time_start}-{ex.time_end} [{ex.course_code}] {ex.course_name[:40]}")
    return exams


def scrape_actualites_events(page: Page, config: Config) -> list[LeaEvent]:
    """Scrape les actualités du portail et retourne celles qui ont une date (annulations, rappels)."""
    log(f" [{config.slug}] === Actualités (calendrier) ===")
    try:
        safe_goto(page, "actualites", config)
    except Exception as exc:
        log(f"  [{config.slug}] Actualités: inaccessible ({exc})")
        recover_home(page, config)
        return []

    events: list[LeaEvent] = []
    try:
        page.wait_for_selector("a.carte-portail", state="attached", timeout=8_000)
    except Exception:
        log(f" [{config.slug}] Actualités: aucune carte trouvée")
        return events

    cards = page.locator("a.carte-portail.carte-actualite").all()
    log(f"  [{config.slug}] {len(cards)} actualité(s) détectée(s)")
    for card in cards:
        try:
            title = safe_text(card.locator("h3.carte-portail-titre").first) or safe_text(card)
            title = " ".join(title.split())[:100]
            if not title:
                continue
            desc_text = safe_text(card.locator("div.carte-portail-desc").first) or ""
            date_iso = _parse_fr_date(desc_text)
            if not date_iso:
                continue
            events.append(LeaEvent(
                date_iso=date_iso,
                time_start="",
                time_end="",
                kind="autre",
                title=title,
                course_code="",
                course_name="Actualité cégep",
                room="",
                weight="",
            ))
        except Exception as exc:
            log(f"  [{config.slug}] Actualité erreur: {exc}")

    log(f"  [{config.slug}] {len(events)} actualité(s) avec date retenue(s)")
    return events


def scrape_lea_documents_deadlines(page: Page, config: Config) -> list[Assignment]:
    """Extrait les dates 'Avoir lu d'ici au...' depuis les documents distribués (LEA)."""
    log(f" [{config.slug}] === Documents LEA — deadlines lecture ===")
    assignments: list[Assignment] = []
    try:
        safe_goto(page, "lea_documents", config)
    except Exception as exc:
        log(f"  [{config.slug}] Documents LEA: inaccessible ({exc})")
        recover_home(page, config)
        return []

    lea_base = config.lea_base
    seen_hrefs: set[str] = set()
    doc_links: list[tuple[str, str]] = []
    for lnk in page.locator("a[href*='ListeDocuments.aspx']").all():
        href = lnk.get_attribute("href") or ""
        if not href or href in seen_hrefs:
            continue
        full = f"{lea_base}{href}" if href.startswith("/") else href
        seen_hrefs.add(href)
        label = safe_text(lnk) or ""
        doc_links.append((full, label))

    log(f"  [{config.slug}] {len(doc_links)} cours avec documents")

    for i, (url, label) in enumerate(doc_links):
        try:
            if i > 0:
                recover_home(page, config)
                _ensure_lea(page, config)
            page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)
            wait_net(page, 5_000)

            code = ""
            try:
                code_raw = page.evaluate("() => (typeof NoCours !== 'undefined' ? NoCours : '')")
                if code_raw:
                    import re as _re
                    m = _re.match(r"(\d{3})(\d{3})(\w{2})", code_raw)
                    if m:
                        code = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            except Exception:
                pass

            for row in page.locator("tr.ligneDocument").all():
                try:
                    doc_title = safe_text(row.locator("td.colonneTitre a").first) or ""
                    doc_title = " ".join(doc_title.split())[:80]
                    desc_text = safe_text(row.locator("div.descriptionDocument").first) or ""
                    if not desc_text or not doc_title:
                        continue
                    date_iso = _parse_date_from_text(desc_text)
                    if not date_iso:
                        continue
                    assignments.append(Assignment(
                        title=f"Lire: {doc_title}",
                        course=label[:50],
                        course_code=code,
                        due_date=date_iso,
                        weight=None,
                        kind="reading",
                    ))
                except Exception:
                    pass
        except Exception as exc:
            log(f"  [{config.slug}] Documents cours '{label[:30]}': {exc}")

    log(f"  [{config.slug}] {len(assignments)} deadline(s) de lecture trouvée(s)")
    return assignments


def generate_ics(
    class_events: list[ClassEvent],
    assignments: list[Assignment],
    config: Config,
    output_path: Path,
    lea_events: Optional[list[LeaEvent]] = None,
    final_exams: Optional[list[FinalExam]] = None,
) -> Path:
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0",
        f"PRODID:-//StudyAgent//Omnivox {config.term}//FR",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        f"X-WR-CALNAME:Omnivox {config.term}",
        "X-WR-TIMEZONE:America/Toronto",
        "BEGIN:VTIMEZONE", "TZID:America/Toronto",
        "BEGIN:DAYLIGHT", "TZOFFSETFROM:-0500", "TZOFFSETTO:-0400",
        "TZNAME:EDT", "DTSTART:20070311T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU", "END:DAYLIGHT",
        "BEGIN:STANDARD", "TZOFFSETFROM:-0400", "TZOFFSETTO:-0500",
        "TZNAME:EST", "DTSTART:20071104T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU", "END:STANDARD",
        "END:VTIMEZONE",
    ]

    for evt in class_events:
        if not config.semester_start or not config.semester_end or not evt.days_fr:
            continue
        byday = ",".join(JOURS_ICAL.get(d.lower(), "") for d in evt.days_fr if JOURS_ICAL.get(d.lower()))
        if not byday or not evt.start_time:
            continue
        try:
            sh, sm = map(int, evt.start_time.split(":"))
        except ValueError:
            continue
        eh, em = (sh + 2, sm)
        if evt.end_time:
            try:
                eh, em = map(int, evt.end_time.split(":"))
            except ValueError:
                pass
        target_wds = [JOURS_LIST.index(d.lower()) for d in evt.days_fr if d.lower() in JOURS_LIST]
        if not target_wds:
            continue
        first = config.semester_start
        while first.weekday() not in target_wds:
            first += timedelta(days=1)
        until = config.semester_end.strftime("%Y%m%dT235959Z")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uuid.uuid4()}@studyagent",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART;TZID=America/Toronto:{first.strftime('%Y%m%d')}T{sh:02d}{sm:02d}00",
            f"DTEND;TZID=America/Toronto:{first.strftime('%Y%m%d')}T{eh:02d}{em:02d}00",
            f"RRULE:FREQ=WEEKLY;BYDAY={byday};UNTIL={until}",
            f"SUMMARY:{evt.course}",
            f"LOCATION:{evt.room}",
            f"DESCRIPTION:Prof: {evt.teacher}\\nCode: {evt.course_code}",
            "END:VEVENT",
        ]

    for asgn in assignments:
        if not asgn.due_date:
            continue
        emoji = "📊" if asgn.kind == "exam" else "📝"
        work_warning = ""
        try:
            due = date.fromisoformat(asgn.due_date)
            day_before_fr = JOURS_LIST[(due - timedelta(days=1)).weekday()]
            if day_before_fr in config.work_days:
                work_warning = f"\\n⚠️ Tu travailles le {day_before_fr.capitalize()} — finis avant ta shift !"
        except Exception:
            pass
        desc = f"Cours: {asgn.course}\\nCode: {asgn.course_code}\\nPoids: {asgn.weight or 'N/A'}{work_warning}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uuid.uuid4()}@studyagent",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART;VALUE=DATE:{asgn.due_date.replace('-', '')}",
            f"DTEND;VALUE=DATE:{asgn.due_date.replace('-', '')}",
            f"SUMMARY:{emoji} {asgn.title}",
            f"DESCRIPTION:{desc}",
            "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Rappel", "TRIGGER:-P1D", "END:VALARM",
        ]
        if asgn.kind == "exam":
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Examen dans 3 jours!", "TRIGGER:-P3D", "END:VALARM"]
        lines.append("END:VEVENT")

    for evt in (lea_events or []):
        if evt.kind not in ("travail", "evaluation", "lire"):
            continue
        emoji_map = {"evaluation": "📊", "lire": "📖", "travail": "📝"}
        emoji = emoji_map.get(evt.kind, "📅")
        desc_parts = [f"Code: {evt.course_code}"] if evt.course_code else []
        if evt.weight:
            desc_parts.append(f"Pondération: {evt.weight}")
        reminders = []
        if evt.kind in ("evaluation", "travail"):
            reminders = [("Rappel 24h", "-P1D")]
        if evt.kind == "evaluation":
            reminders.append(("Examen dans 3 jours", "-P3D"))
        entry = [
            "BEGIN:VEVENT",
            f"UID:{uuid.uuid4()}@studyagent",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART;VALUE=DATE:{evt.date_iso.replace('-', '')}",
            f"DTEND;VALUE=DATE:{evt.date_iso.replace('-', '')}",
            f"SUMMARY:{emoji} {evt.title}",
            f"COLORID:{evt.color_id}",
        ]
        if desc_parts:
            entry.append(f"DESCRIPTION:{chr(92).join(desc_parts)}")
        for rdesc, rtrig in reminders:
            entry += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{rdesc}", f"TRIGGER:{rtrig}", "END:VALARM"]
        entry.append("END:VEVENT")
        lines.extend(entry)

    for ex in (final_exams or []):
        if not ex.time_start or not ex.time_end:
            continue
        try:
            sh, sm = map(int, ex.time_start.split(":"))
            eh, em = map(int, ex.time_end.split(":"))
            d = date.fromisoformat(ex.date_iso)
        except (ValueError, AttributeError):
            continue
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uuid.uuid4()}@studyagent",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART;TZID=America/Toronto:{d.strftime('%Y%m%d')}T{sh:02d}{sm:02d}00",
            f"DTEND;TZID=America/Toronto:{d.strftime('%Y%m%d')}T{eh:02d}{em:02d}00",
            f"SUMMARY:📊 EXAMEN FINAL — {ex.course_name or ex.course_code}",
            f"LOCATION:{ex.room}",
            f"DESCRIPTION:Code: {ex.course_code}\\nProf: {ex.teacher}",
            "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Examen FINAL demain!", "TRIGGER:-P1D", "END:VALARM",
            "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Examen FINAL dans 3 jours!", "TRIGGER:-P3D", "END:VALARM",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\r\n".join(lines), encoding="utf-8")
    log(f"ICS généré: {output_path}")
    return output_path
