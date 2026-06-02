"""
Scraper : travaux et évaluations depuis LÉA.
Responsabilité unique : doce/Default.aspx → IDEval → ListeTravauxEtu.
"""
import re
from datetime import date
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from .omnivox_models import Config, Assignment, COURSE_CODE_RE, EXAM_PATTERN, GCAL_COLOR, MOIS_FR_MAP
from .omnivox_helpers import (
    log, safe_text,
    _parse_date_from_text, _parse_colonne_date_lea, classify_assignment, _title_key,
)
from .omnivox_browser import wait_net, debug_screenshot
from .omnivox_auth import _ensure_lea, recover_home


# Regex pour détecter une cellule contenant une date Omnivox (ex: "28-fév-2026" ou "2026-05-12")
_DATE_CELL_RE = re.compile(
    r'\d{1,2}[-/][a-zéûôàèêù]{2,}[-/]\d{4}'   # 28-fév-2026
    r'|\d{4}-\d{2}-\d{2}'                       # 2026-05-12
    r'|\d{1,2}\s+[a-zéûôàèêù]{3,}\s+\d{4}',   # 28 février 2026
    re.IGNORECASE,
)


def _scrape_travaux_course(page: Page, course_title: str,
                            code: str, config: Config) -> list[Assignment]:
    assignments: list[Assignment] = []
    seen: set[str] = set()
    try:
        body = page.locator("body").inner_text(timeout=8_000)
    except Exception:
        return []
    if "Aucun énoncé" in body:
        return []

    NAV_SKIP = {"infos sur vos enseignants", "version imprimable"}
    js_links = page.locator('a[href="javascript:;"]')
    count = js_links.count()

    for i in range(count):
        lnk = js_links.nth(i)
        title = safe_text(lnk)
        if not title or title.lower() in NAV_SKIP or title in seen:
            continue
        if any(kw.lower() in title.lower() for kw in config.exclude_keywords or []):
            continue
        seen.add(title)
        due_date = None
        try:
            row_text = safe_text(lnk.locator("xpath=ancestor::tr[1]"))
            due_date = _parse_date_from_text(row_text)
        except Exception:
            pass
        kind, color_id = classify_assignment(title, config)
        assignments.append(Assignment(
            title=title, course=course_title, course_code=code,
            due_date=due_date, weight=None, kind=kind, color_id=color_id,
        ))
    return assignments


def _extract_title_date_from_cells(
    cells: list,
) -> tuple[str, str]:
    """
    Détecte dynamiquement le titre et la date depuis les cellules d'une ligne de tableau.

    Retourne (title, date_text).
    - title : première cellule non-vide sans pattern date (et pas un simple nombre)
    - date_text : première cellule contenant un pattern date Omnivox
    Compatibilité toutes implémentations Omnivox (Limoilou, Ahuntsic, Maisonneuve, etc.).
    """
    title = ""
    date_txt = ""
    for cell in cells:
        try:
            text = (cell.inner_text(timeout=3_000) or "").strip()
        except Exception:
            continue
        if not text:
            continue
        if _DATE_CELL_RE.search(text):
            if not date_txt:
                date_txt = re.sub(r'via\s*\S+', '', text, flags=re.IGNORECASE).strip()
        elif not title and not re.fullmatch(r'\d+', text):
            title = text
    return title, date_txt


def _scrape_course_name_from_page(page: Page) -> str:
    """
    Tente de lire le nom du cours depuis le <h1>, <h2> ou des sélecteurs LÉA connus.
    Retourne une chaîne vide si rien trouvé.
    Compatible avec différentes implémentations Omnivox.
    """
    for sel in [
        "h1", "h2",
        ".titreSection", ".titrePage", ".titreModule",
        "#titreSection", "#titrePage",
        "span.titrePage", "td.titrePage",
    ]:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                txt = loc.inner_text(timeout=2_000).strip()
                if txt and len(txt) > 4 and not txt.lower().startswith("omnivox"):
                    return txt
        except Exception:
            continue
    return ""


def _scrape_travaux_via_doce_links(page: Page, config: Config) -> list[Assignment]:
    """
    Fallback ListeTravauxEtu quand SommaireTravauxEtu.aspx retourne 404 (ex: Cégep Limoilou).

    Depuis doce/Default.aspx, trouve les liens Travaux par cours (Service.aspx avec session params)
    et navigue vers chaque ListeTravauxEtu. Les hrefs sont collectés en une seule passe JS,
    puis on navigue vers chacun directement — pas besoin de revenir entre chaque cours.
    """
    log(f" [{config.slug}] Fallback doce/Default: recherche liens Travaux par cours...")

    try:
        page.wait_for_function(
            "() => document.querySelectorAll('a[href*=\"IDEval=\"]').length > 0"
            " || document.querySelectorAll('a[href*=\"Service.aspx\"]').length > 5",
            timeout=10_000,
        )
    except PlaywrightTimeoutError:
        log(f" [{config.slug}] doce/Default: cartes non rendues après 10s — tentative de collecte immédiate")

    try:
        course_hrefs: list[str] = page.evaluate("""
            () => {
                const seen = new Set();
                const results = [];
                document.querySelectorAll('a[href*="Service.aspx"]').forEach(a => {
                    const text = (a.textContent || '').trim();
                    const hasEnonces = text.includes('nonc') && text.includes('s distribu');
                    if (text.includes('Travaux') && hasEnonces) {
                        const href = a.href;
                        if (!seen.has(href)) {
                            seen.add(href);
                            results.push(href);
                        }
                    }
                });
                return results;
            }
        """)
    except Exception as exc:
        log(f"  [{config.slug}] Erreur extraction liens Travaux: {exc}")
        return []

    if not course_hrefs:
        log(f" [{config.slug}] doce/Default: aucun lien Travaux trouvé — fallback IDEval actif")
        return []

    log(f"  [{config.slug}] {len(course_hrefs)} lien(s) Travaux trouvé(s) via doce/Default")
    assignments: list[Assignment] = []

    for href in course_hrefs:
        try:
            page.goto(href, wait_until="domcontentloaded", timeout=config.timeout_ms)
            wait_net(page, 5_000)

            if "ListeTravauxEtu" not in page.url:
                log(f"  [{config.slug}] Redirection inattendue: {page.url[:60]}")
                continue

            course_code = ""
            course_name = ""
            try:
                body_text = page.locator("body").inner_text(timeout=4_000)
                cm = COURSE_CODE_RE.search(body_text)
                if cm:
                    course_code = cm.group(1)
            except Exception:
                pass
            course_name = _scrape_course_name_from_page(page)

            # Sélecteur sans classe : compatible Limoilou (pas de LigneListTrav1 etc.)
            rows = page.locator("table#tabListeTravEtu tr").all()

            if not rows:
                log(f"  [{config.slug}] {course_code or '?'}: table#tabListeTravEtu vide (pas de travaux)")

            for row in rows:
                try:
                    cells = row.locator("td").all()
                    if len(cells) < 2:
                        continue
                    title, date_txt = _extract_title_date_from_cells(cells)
                    if not title:
                        continue
                    if date_txt.lower() in {"non définie", "non definie", ""}:
                        date_txt = ""
                    due, time_str = _parse_colonne_date_lea(date_txt) if date_txt else (None, None)
                    kind = "exam" if EXAM_PATTERN.search(title) else "assignment"
                    assignments.append(Assignment(
                        title=title,
                        course=course_name or course_code,
                        course_code=course_code,
                        due_date=due,
                        weight=None,
                        kind=kind,
                        color_id=GCAL_COLOR.get(kind, "3"),
                        detail_href=page.url,
                        time_start=time_str,
                    ))
                except Exception:
                    continue

        except Exception as exc:
            log(f"  [{config.slug}] Erreur Travaux via doce ({exc})")

    with_time = sum(1 for a in assignments if a.time_start)
    log(f"  [{config.slug}] ListeTravauxEtu (via doce): {len(assignments)} travail(aux), "
        f"{sum(1 for a in assignments if a.due_date)} avec date, "
        f"{with_time} avec heure exacte")
    return assignments


def _scrape_liste_travaux_etu(page: Page, config: Config) -> list[Assignment]:
    """
    Dates fiables depuis ListeTravauxEtu.aspx (table#tabListeTravEtu).

    Navigation via SommaireTravauxEtu.aspx → liens cours → ListeTravauxEtu par cours.
    Si SommaireTravauxEtu n'existe pas (ex: Limoilou retourne 404), tente le fallback
    via doce/Default.aspx (liens Service.aspx avec session params).
    """
    log(f" [{config.slug}] ListeTravauxEtu — navigation via SommaireTravauxEtu...")
    _ensure_lea(page, config)

    lea_base = config.lea_base
    sommaire_url = f"{lea_base}/cvir/dtrv/SommaireTravauxEtu.aspx"
    try:
        page.goto(sommaire_url, wait_until="domcontentloaded", timeout=config.timeout_ms)
        wait_net(page, 3_000)
    except Exception as exc:
        log(f"  [{config.slug}] SommaireTravauxEtu: navigation impossible ({exc})")
        return []

    if "HttpError" in page.url or "404" in page.url:
        log(f" [{config.slug}] SommaireTravauxEtu: page introuvable (404) — tentative via doce/Default")
        try:
            page.goto(f"{lea_base}/cvir/doce/Default.aspx",
                      wait_until="domcontentloaded", timeout=config.timeout_ms)
            wait_net(page, 5_000)
        except Exception:
            log(f" [{config.slug}] doce/Default inaccessible — fallback IDEval actif")
            return []
        return _scrape_travaux_via_doce_links(page, config)

    course_hrefs: list[tuple[str, str]] = page.evaluate("""
        () => {
            const seen = new Set();
            const results = [];
            const candidates = [
                ...document.querySelectorAll('a.RemTrav_Sommaire_NomCours'),
                ...document.querySelectorAll('a[href*="ListeTravauxEtu"]'),
            ];
            for (const a of candidates) {
                const href = a.getAttribute('href') || '';
                if (!href || seen.has(href)) continue;
                seen.add(href);
                results.push([href, (a.textContent || '').trim()]);
            }
            return results;
        }
    """)

    if not course_hrefs:
        log(f" [{config.slug}] SommaireTravauxEtu: aucun lien cours trouvé — fallback IDEval actif")
        return []

    log(f"  [{config.slug}] {len(course_hrefs)} cours trouvé(s) dans SommaireTravauxEtu")

    assignments: list[Assignment] = []
    base = f"{lea_base}/cvir/trav/"

    for raw_href, link_text in course_hrefs:
        if raw_href.startswith("http"):
            list_url = raw_href
        elif raw_href.startswith("/"):
            list_url = f"{lea_base}{raw_href}"
        else:
            list_url = base + raw_href

        nc_m = re.search(r'NoCours=([^&]+)', list_url, re.IGNORECASE)
        course_code_from_url = nc_m.group(1) if nc_m else ""

        try:
            page.goto(list_url, wait_until="domcontentloaded", timeout=config.timeout_ms)
            wait_net(page, 5_000)

            course_code = course_code_from_url
            try:
                body_text = page.locator("body").inner_text(timeout=4_000)
                cm = COURSE_CODE_RE.search(body_text)
                if cm:
                    course_code = cm.group(1)
            except Exception:
                pass
            course_name = _scrape_course_name_from_page(page)

            # Sélecteur sans classe de ligne : compatible Limoilou et autres cégeps.
            rows = page.locator("table#tabListeTravEtu tr").all()

            if not rows:
                log(f"  [{config.slug}] {course_code or link_text}: table#tabListeTravEtu vide")

            for row in rows:
                try:
                    cells = row.locator("td").all()
                    if len(cells) < 2:
                        continue
                    title, date_txt = _extract_title_date_from_cells(cells)
                    if not title:
                        continue
                    if date_txt.lower() in {"non définie", "non definie", ""}:
                        date_txt = ""
                    due, time_str = _parse_colonne_date_lea(date_txt) if date_txt else (None, None)
                    kind = "exam" if EXAM_PATTERN.search(title) else "assignment"
                    assignments.append(Assignment(
                        title=title,
                        course=course_name or course_code,
                        course_code=course_code,
                        due_date=due,
                        weight=None,
                        kind=kind,
                        color_id=GCAL_COLOR.get(kind, "3"),
                        detail_href=list_url,
                        time_start=time_str,
                    ))
                except Exception:
                    continue
        except Exception as exc:
            log(f"  [{config.slug}] ListeTravauxEtu erreur ({course_code_from_url or link_text}): {exc}")
            try:
                debug_screenshot(page, f"omnisync_travaux_{course_code_from_url or 'err'}")
            except Exception:
                pass
        finally:
            try:
                page.goto(sommaire_url, wait_until="domcontentloaded",
                          timeout=config.timeout_ms)
                wait_net(page, 2_000)
            except Exception:
                pass

    log(f"  [{config.slug}] ListeTravauxEtu: {len(assignments)} travail(aux), "
        f"{sum(1 for a in assignments if a.due_date)} avec date")
    return assignments


def _merge_liste_travaux(assignments: list[Assignment], from_liste: list[Assignment]) -> None:
    """Fusionne les dates ListeTravauxEtu dans les entrées doce/Default."""
    liste_index: dict[tuple[str, str], Assignment] = {}
    for item in from_liste:
        key = (item.course_code or "", _title_key(item.title))
        liste_index[key] = item

    existing = {(a.course_code or "", _title_key(a.title)) for a in assignments}
    for asgn in assignments:
        key = (asgn.course_code or "", _title_key(asgn.title))
        src = liste_index.get(key)
        if src:
            if src.due_date and not asgn.due_date:
                asgn.due_date = src.due_date
            if src.time_start and not asgn.time_start:
                asgn.time_start = src.time_start

    for item in from_liste:
        key = (item.course_code or "", _title_key(item.title))
        if key not in existing:
            assignments.append(item)
            existing.add(key)


def scrape_lea_travaux(page: Page, config: Config) -> list[Assignment]:
    """
    Scrape les évaluations/travaux depuis LÉA (doce/Default.aspx + ListeTravauxEtu.aspx).

    Structure confirmée (2026) :
      - SommaireTravauxEtu / ListeTravauxEtu (dtrv/) : dates en td.colonneDate
      - doce/Default.aspx : tooltips IDEval (complément)
    """
    log(f" [{config.slug}] === LÉA — Travaux ===")
    _ensure_lea(page, config)
    lea_base = config.lea_base
    if "doce/Default.aspx" not in page.url:
        page.goto(f"{lea_base}/cvir/doce/Default.aspx",
                  wait_until="domcontentloaded", timeout=config.timeout_ms)
        wait_net(page, 5_000)
        log(f"  [{config.slug}] Navigué vers doce/Default.aspx — {page.url[:60]}")
    try:
        quick_body = page.locator("body").inner_text(timeout=3_000)
        if any(phrase in quick_body for phrase in (
            "Aucun cours", "Aucune évaluation", "no courses", "session terminée",
        )):
            log(f" [{config.slug}] doce/Default.aspx: aucun cours actif pour cette session")
            return []
    except Exception:
        pass

    try:
        page.wait_for_function(
            "() => document.querySelectorAll('a[href*=\"IDEval=\"]').length > 0",
            timeout=10_000,
        )
    except PlaywrightTimeoutError:
        log(f" [{config.slug}] Aucun IDEval trouvé après 10s — session probablement terminée ou sans travaux")
        return []

    raw_evals: list[dict] = page.evaluate(r"""
        () => {
            const results = [];
            const courseCodeRe = /(\d{3}-\d{3}-\w{2})/;
            const monthMap = {
                'janvier':1,'f\xe9vrier':2,'mars':3,'avril':4,'mai':5,'juin':6,
                'juillet':7,'ao\xfbt':8,'septembre':9,'octobre':10,'novembre':11,'d\xe9cembre':12
            };

            document.querySelectorAll('a[href*="IDEval="]').forEach(a => {
                const hrefM = a.href.match(/IDEval=(\d+)/);
                if (!hrefM) return;
                const ideval = hrefM[1];

                let tooltipText = '';
                let spanEl = a.parentElement;
                for (let d = 0; d < 15 && spanEl; d++) {
                    const ov = (spanEl.getAttribute('onmouseover') || '')
                              + (spanEl.getAttribute('onmouseenter') || '');
                    const tidM = ov.match(/DivToolTip(\d+)/);
                    if (tidM) {
                        const tip = document.getElementById('DivToolTip' + tidM[1]);
                        if (tip) {
                            tooltipText = tip.innerHTML
                                .replace(/<br[\s\/]*>/gi, '\n')
                                .replace(/<[^>]+>/g, ' ')
                                .replace(/&nbsp;/g, ' ')
                                .replace(/&amp;/g, '&')
                                .trim();
                        }
                        break;
                    }
                    spanEl = spanEl.parentElement;
                }

                const lines = tooltipText.split(/\n|\r/).map(l => l.trim()).filter(l => l);
                let title = '', weight = 0, dateIso = '';
                let inEval = false;
                for (let i = 0; i < lines.length; i++) {
                    if (lines[i].toLowerCase().includes('\xe9valuation')) { inEval = true; continue; }
                    if (inEval && !title && !lines[i].toLowerCase().startsWith('pond')
                               && !lines[i].toLowerCase().startsWith('date')) {
                        title = lines[i];
                    }
                    const wM = lines[i].match(/Pond[^\d]*(\d+(?:[.,]\d+)?)\s*%/i);
                    if (wM) weight = parseFloat(wM[1].replace(',', '.'));
                    const dM = lines[i].match(/(?:Date|[ée]ch[ée]ance)\s*:?\s*(\d{1,2})\s+(\w+)\s+(\d{4})/i);
                    if (dM) {
                        const month = monthMap[dM[2].toLowerCase()];
                        if (month) {
                            dateIso = dM[3] + '-' + String(month).padStart(2,'0') + '-' + dM[1].padStart(2,'0');
                        }
                    }
                    if (!dateIso) {
                        const dM2 = lines[i].match(/(\d{1,2})\s+(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)\s+(\d{4})/i);
                        if (dM2) {
                            const month = monthMap[dM2[2].toLowerCase()];
                            if (month) {
                                dateIso = dM2[3] + '-' + String(month).padStart(2,'0') + '-' + dM2[1].padStart(2,'0');
                            }
                        }
                    }
                }

                let courseCode = '';
                let ancestor = a;
                for (let d = 0; d < 15 && ancestor; d++) {
                    const t = ancestor.innerText || '';
                    const cm = /Classe:\s*(\d{3}-\d{3}-\w{2})/.exec(t);
                    if (cm) { courseCode = cm[1]; break; }
                    ancestor = ancestor.parentElement;
                }

                if (!title) {
                    let trEl = a;
                    for (let d = 0; d < 20 && trEl; d++) {
                        if (trEl.tagName === 'TR') break;
                        trEl = trEl.parentElement;
                    }
                    if (trEl && trEl.tagName === 'TR') {
                        const rowText = (trEl.textContent || '').replace(/\s+/g, ' ').trim();
                        const classeM = rowText.match(/Classe:\s*\d{3}-\d{3}-\w{2}\s+gr\.\s*\d+\s+(.+?)(?:\s+Pond)/i);
                        if (classeM) title = classeM[1].trim();
                        const dateM = rowText.match(/(?:lun|mar|mer|jeu|ven|sam|dim)[^\d]*le\s*(\d+)\w*\s+(\w+)/i);
                        if (dateM && !dateIso) {
                            const month = monthMap[dateM[2].toLowerCase()];
                            if (month) {
                                const yr = new Date().getFullYear();
                                dateIso = yr + '-' + String(month).padStart(2,'0') + '-' + dateM[1].padStart(2,'0');
                            }
                        }
                        if (!weight) {
                            const wM = rowText.match(/Pond[^\d]*(\d+(?:[.,]\d+)?)\s*%/i);
                            if (wM) weight = parseFloat(wM[1].replace(',', '.'));
                        }
                    }
                }

                if (!dateIso) {
                    let parentEl = a;
                    while (parentEl && parentEl.tagName !== 'TABLE') parentEl = parentEl.parentElement;
                    if (parentEl) {
                        const dateCell = parentEl.querySelector('td.tdAfficheListeDate');
                        if (dateCell) {
                            const dTxt = (dateCell.textContent || '').replace(/[ \s]+/g, ' ').trim();
                            const dM = dTxt.match(/(?:lun|mar|mer|jeu|ven|sam|dim)\s*le\s*(\d+)\w*\s+(\w+)/i);
                            if (dM) {
                                const m = monthMap[dM[2].toLowerCase()];
                                if (m) {
                                    dateIso = String(new Date().getFullYear()) + '-' + String(m).padStart(2,'0') + '-' + dM[1].padStart(2,'0');
                                }
                            }
                        }
                    }
                }

                if (title || courseCode) {
                    results.push({ ideval, courseCode, title, weight, dateIso, href: a.href });
                }
            });

            const seen = new Set();
            return results.filter(r => {
                if (seen.has(r.ideval)) return false;
                seen.add(r.ideval);
                return true;
            });
        }
    """)

    _html_cache: str | None = None
    def _extract_from_html(ideval_str: str, course_code: str) -> tuple[str, float, str]:
        nonlocal _html_cache
        if _html_cache is None:
            try:
                _html_cache = page.content()
            except Exception:
                _html_cache = ""
        title_found, weight_found, date_found = "", 0.0, ""
        for m in re.finditer(rf'IDEval={ideval_str}', _html_cache):
            chunk = _html_cache[m.start():m.start() + 1000]
            text = re.sub(r'<[^>]+>', ' ', chunk)
            text = re.sub(r'[\xa0\s]+', ' ', text).strip()
            if course_code:
                cc_pat = re.escape(course_code).replace(r'\-', '-')
                pat = rf'Classe:\s*{cc_pat}\s+gr\.\s*\d+\s+(.+?)(?:\s+Pond)'
                cm = re.search(pat, text, re.IGNORECASE)
                if cm:
                    title_found = cm.group(1).strip()
                    wm = re.search(r'Pond[^\d]*(\d+(?:[.,]\d+)?)\s*%', text[cm.start():], re.IGNORECASE)
                    weight_found = float(wm.group(1).replace(',', '.')) if wm else 0.0
                    dm = re.search(r'(?:lun|mar|mer|jeu|ven|sam|dim)[^\d]*le\s*(\d+)\w*\s+(\w+)', text, re.IGNORECASE)
                    if dm:
                        mois = MOIS_FR_MAP.get(dm.group(2).lower())
                        if mois:
                            date_found = f"{date.today().year}-{mois:02d}-{int(dm.group(1)):02d}"
                    break
            if not title_found:
                pat2 = r'\xc9valuation\s+(.+?)\s+Pond'
                cm2 = re.search(pat2, text, re.IGNORECASE)
                if cm2:
                    title_found = cm2.group(1).strip()
                    wm = re.search(r'Pond[^\d]*(\d+(?:[.,]\d+)?)\s*%', text[cm2.start():], re.IGNORECASE)
                    weight_found = float(wm.group(1).replace(',', '.')) if wm else 0.0
                    dm2 = re.search(r'Date\s+(\d{1,2})[\xa0\s]+(\w+)[\xa0\s]+(\d{4})', text, re.IGNORECASE)
                    if dm2:
                        mois = MOIS_FR_MAP.get(dm2.group(2).lower())
                        if mois:
                            date_found = f"{dm2.group(3)}-{mois:02d}-{int(dm2.group(1)):02d}"
                    break
        return title_found, weight_found, date_found

    assignments: list[Assignment] = []
    for ev in raw_evals:
        code = ev.get("courseCode", "")
        title = ev.get("title", "")
        weight = float(ev.get("weight", 0) or 0)
        due = ev.get("dateIso", "") or None
        if not title and code:
            title_fb, weight_fb, due_fb = _extract_from_html(ev.get("ideval", ""), code)
            if title_fb:
                title = title_fb
                if not weight:
                    weight = weight_fb
                if not due:
                    due = due_fb or None
        if not title:
            title = f"Évaluation IDEval={ev.get('ideval')}"
        kind = "exam" if any(k in title.lower() for k in ["examen", "final", "exam"]) else "assignment"
        emoji = "E" if kind == "exam" else "T"
        log(f" [{config.slug}]  [{emoji}] [{code}] {title[:50]} — {due or '(date inconnue)'} ({weight}%)")
        assignments.append(Assignment(
            title=title, course=code, course_code=code,
            due_date=due, weight=str(weight) if weight else None, kind=kind,
            color_id=GCAL_COLOR.get(kind, "3"),
            ideval=ev.get("ideval") or None,
            detail_href=ev.get("href") or None,
        ))

    liste_travaux = _scrape_liste_travaux_etu(page, config)
    _merge_liste_travaux(assignments, liste_travaux)

    by_ideval: dict[str, Assignment] = {
        a.ideval: a for a in assignments if a.ideval
    }

    def _date_from_detail_text(body_txt: str) -> Optional[str]:
        date_found = _parse_date_from_text(body_txt)
        if date_found:
            return date_found
        for pat in [
            r"pour le\s+(\d{1,2})\s+(\w+)\s+(\d{4})",
            r"[ée]ch[ée]ance\s*:?\s*(\d{1,2})\s+(\w+)\s+(\d{4})",
            r"date\s*(?:de remise)?\s*:?\s*(\d{1,2})\s+(\w+)\s+(\d{4})",
            r"remise\s*:?\s*(\d{1,2})\s+(\w+)\s+(\d{4})",
            r"(\d{1,2})\s+(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)\s+(\d{4})",
        ]:
            m = re.search(pat, body_txt, re.IGNORECASE)
            if m:
                mois = MOIS_FR_MAP.get(m.group(2).lower())
                if mois:
                    return f"{m.group(3)}-{mois:02d}-{int(m.group(1)):02d}"
        return None

    no_date_evals = [ev for ev in raw_evals if not (ev.get("dateIso") or "") and ev.get("href")]
    if no_date_evals:
        log(f"  [{config.slug}] Récupération des dates manquantes : {len(no_date_evals)} évaluation(s)...")
        doce_url = f"{lea_base}/cvir/doce/Default.aspx"
        found_dates = 0
        for ev in no_date_evals:
            href = ev.get("href", "")
            ideval = ev.get("ideval", "")
            if not href or not ideval:
                continue
            asgn = by_ideval.get(ideval)
            if asgn is None or asgn.due_date:
                continue
            try:
                page.goto(href, wait_until="domcontentloaded", timeout=config.timeout_ms)
                wait_net(page, 5_000)
                body_txt = page.locator("body").inner_text(timeout=5_000)
                date_found = _date_from_detail_text(body_txt)
                if date_found:
                    asgn.due_date = date_found
                    found_dates += 1
                    log(f"    [{config.slug}] + [{asgn.course_code}] {asgn.title[:45]} -> {date_found}")
            except Exception as exc:
                log(f"    [{config.slug}] Erreur detail IDEval={ideval}: {exc}")
        if found_dates:
            log(f"  [{config.slug}] Dates récupérées sur fiches détail : {found_dates}")
        try:
            page.goto(doce_url, wait_until="domcontentloaded", timeout=config.timeout_ms)
            wait_net(page, 3_000)
        except Exception:
            pass

    log(f"  [{config.slug}] Total travaux: {len(assignments)} ({sum(1 for a in assignments if a.due_date)} avec date)")
    return assignments
