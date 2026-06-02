"""
Scrapers LEA : documents, actualités, vue d'ensemble, cheminement, documents officiels.
Responsabilité unique : portails LEA et ESTD hors travaux/calendrier.
"""
import re
from datetime import date
from pathlib import Path

from playwright.sync_api import Page

from .omnivox_models import Config, LeaCourse, COURSE_CODE_RE
from .omnivox_helpers import (
    log, safe_text, slugify, ensure_dir, smart_save_text,
    download_document, _strip_sid, _parse_fr_date,
)
from .omnivox_browser import wait_net
from .omnivox_auth import safe_goto, recover_home, _ensure_lea, relogin_if_needed


def scrape_cheminement(page: Page, config: Config, output_base: Path) -> None:
    """Scrape la grille de cheminement du programme."""
    log(f" [{config.slug}] === Grille de cheminement ===")
    try:
        safe_goto(page, "cheminement", config)
        body = page.locator("body").inner_text(timeout=8_000)
    except Exception as exc:
        log(f"  [{config.slug}] Cheminement: inaccessible ({exc})")
        recover_home(page, config)
        return

    dest = ensure_dir(output_base / config.term / "_general") / "_cheminement.md"
    content = f"# Grille de cheminement\n\n*Mis à jour: {date.today().isoformat()}*\n\n```\n{body}\n```\n"
    status = smart_save_text(dest, content)
    log(f"  [{config.slug}] Cheminement [{status}]")


def scrape_documents_officiels(page: Page, config: Config, output_base: Path) -> None:
    """Télécharge les documents officiels distribués par le collège."""
    log(f" [{config.slug}] === Documents officiels ===")
    try:
        safe_goto(page, "documents_officiels", config)
    except Exception as exc:
        log(f"  [{config.slug}] Documents officiels: inaccessible ({exc})")
        recover_home(page, config)
        return

    dest_dir = ensure_dir(output_base / config.term / "_general" / "documents_officiels")
    links = page.locator("a[href*='telecharger'], a[href*='Consulter'], a[href*='.pdf'], a[href*='.docx']")
    n = links.count()
    log(f"  [{config.slug}] {n} document(s) officiel(s) trouvé(s)")

    for i in range(n):
        lnk = links.nth(i)
        href = lnk.get_attribute("href") or ""
        title = safe_text(lnk)
        if not href or not title:
            continue
        if href.startswith("/"):
            href = f"{config.estd_base}{href}"
        ext = Path(href.split("?")[0]).suffix or ".pdf"
        fname = slugify(title) + ext
        status = download_document(page, href, dest_dir / fname)
        if status != "unchanged":
            log(f"   [{config.slug}]  [{status.upper()}] {title[:50]}")


def scrape_actualites(page: Page, config: Config, output_base: Path) -> None:
    """Scrape les actualités/nouvelles du collège."""
    log(f" [{config.slug}] === Actualités ===")
    try:
        safe_goto(page, "actualites", config)
    except Exception as exc:
        log(f"  [{config.slug}] Actualités: inaccessible ({exc})")
        recover_home(page, config)
        return

    dest_dir = ensure_dir(output_base / config.term / "_general" / "actualites")

    article_links = page.locator("a[href*='idNews'], a[href*='mode=one']")
    n = article_links.count()
    log(f"  [{config.slug}] {n} article(s) trouvé(s)")

    seen_urls: set[str] = set()
    for i in range(n):
        lnk = article_links.nth(i)
        href = lnk.get_attribute("href") or ""
        title = safe_text(lnk)
        if not href or href in seen_urls or not title:
            continue
        seen_urls.add(href)

        full_url = href if href.startswith("http") else f"{config.omnivox_base}{href}"
        try:
            page.goto(full_url, wait_until="domcontentloaded", timeout=config.timeout_ms)
            wait_net(page, 8_000)
            body_text = safe_text(page.locator("body"))
            article_date = _parse_fr_date(body_text) or date.today().isoformat()
            fname = f"{article_date}_{slugify(title[:50])}.md"
            content = f"# {title}\n\n*Date: {article_date}*\n\n{body_text}\n"
            status = smart_save_text(dest_dir / fname, content)
            if status != "unchanged":
                log(f"   [{config.slug}]  [{status.upper()}] {title[:50]}")
        except Exception as exc:
            log(f"    [{config.slug}] Erreur article '{title[:40]}': {exc}")
        finally:
            page.go_back()
            wait_net(page, 5_000)


def scrape_lea_overview(page: Page, config: Config) -> list[LeaCourse]:
    """Scrape la liste des cours depuis la page d'accueil LÉA (via SSO)."""
    log(f" [{config.slug}] === LÉA — Vue d'ensemble ===")
    _ensure_lea(page, config)
    log(f"  [{config.slug}] Page LEA: {page.url[:60]}")

    courses: list[LeaCourse] = []
    try:
        body = page.locator("body").inner_text(timeout=10_000)
    except Exception:
        return []

    code_positions = [(m.start(), m.group(1)) for m in COURSE_CODE_RE.finditer(body)]
    seen_codes: set[str] = set()

    for pos, code in code_positions:
        if code in seen_codes:
            continue
        seen_codes.add(code)
        ctx = body[max(0, pos-50):pos+150]
        sch_m = re.search(r'((?:lun|mar|mer|jeu|ven|sam|dim)\s+\d+h\d*(?:\s*/\s*(?:lun|mar|mer|jeu|ven|sam|dim)\s+\d+h\d*)*)',
                          ctx, re.IGNORECASE)
        schedule = sch_m.group(1) if sch_m else ""
        doc_m = re.search(r'(\d+)\s+doc', ctx, re.IGNORECASE)
        doc_count = int(doc_m.group(1)) if doc_m else 0
        work_m = re.search(r'(\d+)\s+(?:trav|énoncé|remise)', ctx, re.IGNORECASE)
        work_count = int(work_m.group(1)) if work_m else 0

        courses.append(LeaCourse(
            code=code, name="", group="", teacher="",
            schedule=schedule, doc_count=doc_count, work_count=work_count,
        ))
        log(f"  [{config.slug}] {code} — horaire: '{schedule}' — {doc_count} docs — {work_count} travaux")

    return courses


def scrape_lea_documents(page: Page, config: Config,
                         output_base: Path, courses: list[LeaCourse]) -> None:
    """Télécharge tous les documents de cours depuis LÉA."""
    from omnisync.storage import db  # noqa: PLC0415
    log(f" [{config.slug}] === LÉA — Documents (téléchargement) ===")
    try:
        safe_goto(page, "lea_documents", config)
    except Exception as exc:
        log(f"  [{config.slug}] Documents Léa: inaccessible ({exc})")
        recover_home(page, config)
        return

    lea_base = config.lea_base
    list_doc_links: list[tuple[str, str]] = []
    seen_hrefs: set[str] = set()
    for lnk in page.locator("a[href*='ListeDocuments.aspx']").all():
        href = lnk.get_attribute("href") or ""
        if not href or href in seen_hrefs:
            continue
        full = f"{lea_base}{href}" if href.startswith("/") else href
        seen_hrefs.add(href)
        label = safe_text(lnk) or ""
        list_doc_links.append((full, label))

    if not list_doc_links:
        log(f" [{config.slug}] Documents: aucun lien ListeDocuments.aspx trouvé")
        try:
            _d = Path(__file__).parent / "debug" / "lea_documents_debug2.html"
            _d.write_text(page.content(), encoding="utf-8")
        except Exception:
            pass
        return

    log(f"  [{config.slug}] {len(list_doc_links)} lien(s) ListeDocuments trouvé(s)")

    NAV_TITLES = {
        "calendrier", "sommaire de la classe", "ajouter un évènement privé",
        "sommaire", "liste", "forum de classe", "forum de cette classe",
        "liste de mes absences", "notes d'évaluation", "notes pour un cours",
        "relevé de notes finales", "sites web recommandés", "travaux",
        "forums par équipe", "forums en résumé", "tutorat", "activités",
        "recevoir de l'aide", "devenir tuteur", "disponibilités",
        "mise en page", "version imprimable",
    }

    for i, (list_url, label) in enumerate(list_doc_links):
        try:
            if i > 0:
                recover_home(page, config)
                _ensure_lea(page, config)
        except Exception as reconnect_exc:
            log(f"  [{config.slug}] [RECONNECT] Erreur avant cours {i+1}: {reconnect_exc}")
            try:
                relogin_if_needed(page, config)
            except Exception:
                log(f"  [{config.slug}] [RECONNECT] Re-login échoué — cours {label[:30]} ignoré")
                continue

        try:
            page.goto(list_url, wait_until="domcontentloaded", timeout=config.timeout_ms)
            wait_net(page, 5_000)

            code_raw = page.evaluate(
                "() => (typeof NoCours !== 'undefined' ? NoCours : '')"
            )
            code = ""
            if code_raw:
                m = re.match(r"(\d{3})(\d{3})(\w{2})", code_raw)
                if m:
                    code = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            if not code:
                code_m = COURSE_CODE_RE.search(label + page.url)
                code = code_m.group(1) if code_m else ""
            if not code:
                log(f"  [{config.slug}] [SKIP] Pas de code cours pour: {label[:30]}")
                continue

            course_folder = _find_course_folder(output_base, config.term, code)
            docs_dir = ensure_dir(course_folder / "documents")

            doc_section_link = page.locator("a:has-text('Documents de cours')").first
            if doc_section_link.count() > 0 and "ListeDocuments" not in page.url:
                try:
                    docs_href = doc_section_link.get_attribute("href") or ""
                    if docs_href:
                        if docs_href.startswith("/"):
                            docs_href = f"{lea_base}{docs_href}"
                        page.goto(docs_href, wait_until="domcontentloaded",
                                  timeout=config.timeout_ms)
                        wait_net(page, 5_000)
                except Exception:
                    pass

            FILE_EXTS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx",
                         ".xls", ".zip", ".rar", ".7z", ".mp4", ".mp3"}
            doc_count = 0
            seen_doc_titles: set[str] = set()

            for lnk2 in page.locator("a[href]").all():
                try:
                    href2 = lnk2.get_attribute("href") or ""
                    title2 = (lnk2.text_content() or "").strip()
                    title2 = re.sub(r'[\xa0\s]+', ' ', title2).strip()
                except Exception:
                    continue

                if not href2 or not title2:
                    continue
                if title2.lower() in NAV_TITLES:
                    continue
                if re.search(r'\d+\s*Ko\s*$', title2, re.IGNORECASE):
                    continue
                if len(title2) < 4:
                    continue
                if title2 in seen_doc_titles:
                    continue
                seen_doc_titles.add(title2)

                href_lower = href2.lower()
                is_doc_link = (
                    "VisualiseDocument" in href2
                    or "telecharger" in href_lower
                    or "download" in href_lower
                    or any(href_lower.split("?")[0].endswith(e) for e in FILE_EXTS)
                )
                if not is_doc_link:
                    continue

                if href2.startswith("/"):
                    href2 = f"{lea_base}{href2}"
                elif not href2.startswith("http"):
                    base_url = page.url.rsplit("/", 1)[0]
                    href2 = f"{base_url}/{href2}"

                base_ext = Path(href2.split("?")[0]).suffix or ".bin"
                fname = slugify(title2) + base_ext
                dl_status = download_document(page, href2, docs_dir / fname)

                downloaded_file = None
                if dl_status not in ("error",):
                    stem = slugify(title2)
                    matches = list(docs_dir.glob(f"{stem}.*"))
                    if matches:
                        downloaded_file = str(max(matches, key=lambda p: p.stat().st_mtime))
                    else:
                        downloaded_file = str(docs_dir / fname)
                    if dl_status != "unchanged":
                        log(f"   [{config.slug}]  [{dl_status.upper()}] {code} — {title2[:50]}")
                else:
                    stem = slugify(title2)
                    matches = [p for p in docs_dir.glob(f"{stem}.*")
                               if p.suffix.lower() in {".pdf", ".docx", ".pptx", ".doc", ".xlsx"}]
                    if matches:
                        downloaded_file = str(max(matches, key=lambda p: p.stat().st_mtime))

                stable_url = _strip_sid(href2)
                _, db_status = db.upsert_document(
                    code, title2, config.term,
                    url=stable_url,
                    local_path=downloaded_file or "",
                    downloaded=1 if downloaded_file else 0,
                )
                if db_status in ("new", "updated"):
                    doc_count += 1

            log(f"  [{config.slug}] {code}: {doc_count} document(s) recensé(s) / {page.url[:50]}")
        except Exception as exc:
            log(f"  [{config.slug}] Erreur ListeDocuments ({label[:30]}): {exc}")
            try:
                recover_home(page, config)
            except Exception:
                try:
                    relogin_if_needed(page, config)
                except Exception:
                    pass

    _patch_disk_documents(db, output_base, config.term, config.slug)


def _patch_disk_documents(db_module, output_base: Path, term: str, slug: str = "") -> None:
    """Associe les fichiers présents sur disque aux enregistrements DB sans local_path valide."""
    FILE_EXTS_REAL = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".zip"}
    patched = 0
    try:
        docs = db_module.get_documents()
        for doc in docs:
            lp = doc.get("local_path") or ""
            if lp and Path(lp).exists():
                continue
            course_code = doc.get("course_code") or ""
            filename = doc.get("filename") or ""
            if not course_code or not filename:
                continue

            course_folder = _find_course_folder(output_base, term, course_code)
            docs_dir = course_folder / "documents"
            if not docs_dir.exists():
                continue

            stem = slugify(filename)
            candidates = [p for p in docs_dir.iterdir()
                          if p.suffix.lower() in FILE_EXTS_REAL]
            best: Path | None = None
            for p in candidates:
                if p.stem.lower() == stem.lower():
                    best = p
                    break
            if not best and len(stem) >= 8:
                prefix = stem[:20].lower()
                for p in candidates:
                    if p.stem.lower().startswith(prefix):
                        best = p
                        break
            if not best:
                words = set(re.findall(r'[a-z0-9]{4,}', stem.lower()))
                for p in candidates:
                    p_words = set(re.findall(r'[a-z0-9]{4,}', p.stem.lower()))
                    if words and p_words and len(words & p_words) >= max(1, len(words) // 2):
                        best = p
                        break

            if best:
                _, status = db_module.upsert_document(
                    course_code, filename, term,
                    local_path=str(best),
                    downloaded=1,
                )
                if status in ("new", "updated"):
                    patched += 1

        if patched:
            log(f"  [{slug}] [DISK SCAN] {patched} document(s) liés aux fichiers existants")
    except Exception as exc:
        log(f"  [{slug}] [DISK SCAN] Erreur: {exc}")


def _find_course_folder(output_base: Path, term: str, code: str) -> Path:
    """Trouve ou crée le dossier pour un cours donné."""
    code_slug = code.replace("-", "_")
    candidates = list(output_base.glob(f"{term}/*{code_slug}*"))
    if not candidates:
        candidates = list(output_base.glob(f"{term}/*{code}*"))
    if candidates:
        return candidates[0]
    return ensure_dir(output_base / term / code_slug)
