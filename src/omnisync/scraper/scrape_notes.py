"""
Scraper : notes d'évaluation depuis LÉA.
Responsabilité unique : extraire les notes par cours depuis doce/Default.aspx.
"""
import re
from datetime import date
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from .omnivox_models import Config, CourseNote, COURSE_CODE_RE
from .omnivox_helpers import log, smart_save_text, ensure_dir, _parse_fr_date
from .omnivox_auth import _ensure_lea, recover_home


def scrape_notes(page: Page, config: Config, output_base: Path) -> list[CourseNote]:
    """
    Scrape les notes depuis LÉA.

    Structure DOM confirmée (2024) :
      span.note-principale  → "48.9/61"
      span.pourcentage      → "80%"
    """
    log(f" [{config.slug}] === Notes d'évaluation ===")
    try:
        _ensure_lea(page, config)
        log(f"  [{config.slug}] Attente du chargement des cartes de cours (AJAX)...")
        try:
            page.wait_for_function(
                """() => document.querySelectorAll(
                    'span.note-principale, [class*="note-principal"]'
                ).length > 0""",
                timeout=30_000,
            )
        except PlaywrightTimeoutError:
            try:
                _debug_html = page.content()
                _debug_dest = Path(__file__).parent / "debug" / "lea_notes_debug.html"
                _debug_dest.parent.mkdir(exist_ok=True)
                _debug_dest.write_text(_debug_html, encoding="utf-8")
                log(f"  [{config.slug}] Debug HTML sauvegardé: {_debug_dest}")
            except Exception:
                pass
            log(f" [{config.slug}] Avertissement: span.note-principale non détecté après 30s, extraction tentée")
    except Exception as exc:
        log(f"  [{config.slug}] Notes: inaccessible ({exc})")
        recover_home(page, config)
        return []

    log(f"  [{config.slug}] Notes page: {page.url[:70]}")
    notes: list[CourseNote] = []

    # ── Méthode 1 : DOM structuré ──
    try:
        dom_notes = page.evaluate("""
            () => {
                const results = [];
                const courseCodeRe = /\\b(\\d{3}-\\d{3}-\\w{2})\\b/;
                const scoreRe = /(\\d+(?:[.,]\\d+)?)\\s*\\/\\s*(\\d+(?:[.,]\\d+)?)/;
                const pctRe = /(\\d+)%/;

                const noteEls = document.querySelectorAll(
                    'span.note-principale, [class*="note-principal"]'
                );

                noteEls.forEach(noteEl => {
                    const scoreText = noteEl.innerText.trim();
                    const mScore = scoreRe.exec(scoreText);
                    if (!mScore) return;

                    const pctEl = noteEl.parentElement
                        ? noteEl.parentElement.querySelector('span.pourcentage, [class*="pourcentage"]')
                        : null;
                    const pctText = pctEl ? pctEl.innerText.trim() : '';
                    const mPct = pctRe.exec(pctText);

                    let ancestor = noteEl;
                    let courseCode = '';
                    let courseName = '';
                    for (let d = 0; d < 20 && ancestor; d++) {
                        const t = ancestor.innerText || '';
                        const mc = courseCodeRe.exec(t);
                        if (mc) { courseCode = mc[1]; break; }
                        ancestor = ancestor.parentElement;
                    }
                    if (!courseCode) return;

                    const titleEl = ancestor
                        ? ancestor.querySelector('.course-title, h2, h3, .titre, [class*="title"]')
                        : null;
                    courseName = titleEl ? titleEl.innerText.trim() : '';

                    const blockText = ancestor ? ancestor.innerText : '';
                    let avg = 0;
                    const avgM = /Moyenne de la classe[^\\d]*(\\d+[.,]\\d+)\\s*%/i.exec(blockText);
                    if (avgM) avg = parseFloat(avgM[1].replace(',', '.'));

                    let absences = 0;
                    const absM = /Retards et absences[^\\d]*(\\d+[.,]\\d*)\\s*h/i.exec(blockText);
                    if (absM) absences = parseFloat(absM[1].replace(',', '.'));

                    results.push({
                        courseCode, courseName,
                        score: parseFloat(mScore[1].replace(',', '.')),
                        maxScore: parseFloat(mScore[2].replace(',', '.')),
                        percentage: mPct ? parseFloat(mPct[1]) : 0,
                        avg, absences
                    });
                });
                return results;
            }
        """)

        for item in dom_notes:
            if item.get("courseCode") and item.get("score", 0) > 0:
                notes.append(CourseNote(
                    course_code=item["courseCode"],
                    course_name=item.get("courseName", ""),
                    score=item["score"],
                    max_score=item["maxScore"],
                    percentage=item["percentage"],
                    group_avg=item["avg"],
                    absences_hours=item["absences"],
                ))
                log(f"  [{config.slug}] {item['courseCode']}: {item['score']}/{item['maxScore']}"
                    f" ({item['percentage']}%) | moy: {item['avg']}% | abs: {item['absences']}h")
    except Exception as exc:
        log(f"  [{config.slug}] DOM extraction error: {exc}")

    # ── Méthode 2 : Fallback text ──
    if not notes:
        try:
            _debug_html = page.content()
            _debug_dest = Path(__file__).parent / "debug" / "lea_notes_debug.html"
            _debug_dest.parent.mkdir(exist_ok=True)
            _debug_dest.write_text(_debug_html, encoding="utf-8")
            log(f"  [{config.slug}] Debug HTML sauvegardé: {_debug_dest}")
        except Exception:
            pass
        log(f" [{config.slug}] Fallback text: scan du body pour score patterns...")
        try:
            body = page.locator("body").inner_text(timeout=10_000)
            course_re = re.compile(r'(\d{3}-\d{3}-\w{2})')
            score_re  = re.compile(r'(\d+(?:[\.,]\d+)?)\s*/\s*(\d+(?:[\.,]\d+)?)')
            pct_re    = re.compile(r'(\d+)\s*%')
            avg_re    = re.compile(r'Moyenne de la classe[^\d]*([\d,.]+)\s*%', re.IGNORECASE)
            abs_re    = re.compile(r'Retards et absences[^\d]*([\d,.]+)\s*h', re.IGNORECASE)

            lines = [l.strip() for l in body.splitlines() if l.strip()]
            i = 0
            current_code = None
            current_name = ""
            while i < len(lines):
                line = lines[i]
                mc = course_re.search(line)
                if mc and len(line) < 25:
                    current_code = mc.group(1)
                    current_name = lines[i + 1] if i + 1 < len(lines) else ""
                    i += 1
                    continue
                if current_code and "note actuelle" in line.lower():
                    window = "\n".join(lines[i:i + 6])
                    ms = score_re.search(window)
                    mp = pct_re.search(window)
                    ma = avg_re.search("\n".join(lines[i:i + 10]))
                    mab = abs_re.search("\n".join(lines[i:i + 12]))
                    if ms and mp:
                        notes.append(CourseNote(
                            course_code=current_code, course_name=current_name,
                            score=float(ms.group(1).replace(",", ".")),
                            max_score=float(ms.group(2).replace(",", ".")),
                            percentage=float(mp.group(1)),
                            group_avg=float((ma.group(1) if ma else "0").replace(",", ".")),
                            absences_hours=float((mab.group(1) if mab else "0").replace(",", ".")),
                        ))
                        log(f"  [{config.slug}] {current_code} (text): {ms.group(1)}/{ms.group(2)} ({mp.group(1)}%)")
                        current_code = None
                i += 1
        except Exception as exc:
            log(f"  [{config.slug}] Fallback text echec: {exc}")

    # ── Méthode 3 : Fallback liens ──
    if not notes:
        log(f" [{config.slug}] Fallback liens: extraction depuis les liens LEA homepage...")
        try:
            notes = _scrape_notes_from_links(page, config.slug)
        except Exception as exc:
            log(f"  [{config.slug}] Fallback liens echec: {exc}")

    if notes:
        session_dir = ensure_dir(output_base / config.term)
        lines_md = [f"# Notes — {config.term}\n",
                    f"*Mis a jour: {date.today().isoformat()}*\n\n",
                    "| Cours | Note | % | Moy. groupe | Absences |\n",
                    "|---|---|---|---|---|\n"]
        for n in notes:
            lines_md.append(
                f"| {n.course_code} {n.course_name[:30]} "
                f"| {n.score}/{n.max_score} "
                f"| **{n.percentage}%** "
                f"| {n.group_avg}% "
                f"| {n.absences_hours}h |\n"
            )
        status = smart_save_text(session_dir / "_notes_resume.md", "".join(lines_md))
        log(f"  [{config.slug}] Notes resume [{status}]: {session_dir / '_notes_resume.md'}")

    return notes


def _scrape_notes_from_links(page: Page, slug: str = "") -> list[CourseNote]:
    """
    Extraction des notes depuis les textes des liens de la page LEA homepage.
    Format confirmé du texte de lien:
      'Notes d'évaluation Votre note actuelle 48.9/61 80%'
    """
    notes = []
    score_re = re.compile(r'(\d+(?:[\.,]\d+)?)\s*/\s*(\d+(?:[\.,]\d+)?)\s+(\d+)%')

    course_links = page.evaluate("""
        () => {
            const results = [];
            document.querySelectorAll('a').forEach(a => {
                const text = (a.innerText || '').trim();
                if (text.includes('note actuelle') || (text.includes('/') && text.includes('%'))) {
                    let el = a;
                    let courseCode = '';
                    for (let depth = 0; depth < 10 && el; depth++) {
                        const parentText = el.innerText || '';
                        const m = parentText.match(/\\b(\\d{3}-\\d{3}-\\w{2})\\b/);
                        if (m) { courseCode = m[1]; break; }
                        el = el.parentElement;
                    }
                    results.push({ text, courseCode });
                }
            });
            return results;
        }
    """)
    seen = set()
    for item in course_links:
        code = item.get("courseCode", "")
        text = item.get("text", "")
        if not code or code in seen:
            continue
        m = score_re.search(text)
        if m:
            seen.add(code)
            notes.append(CourseNote(
                course_code=code, course_name="",
                score=float(m.group(1).replace(",", ".")),
                max_score=float(m.group(2).replace(",", ".")),
                percentage=float(m.group(3)),
                group_avg=0.0, absences_hours=0.0,
            ))
            log(f"  [{slug}] {code}: {m.group(1)}/{m.group(2)} ({m.group(3)}%)")
    return notes
