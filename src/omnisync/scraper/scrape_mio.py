"""
Scraper : messages MIO (messagerie interne Omnivox).
Responsabilité unique : naviguer dans le frameset MIO et extraire les messages.
Protocole iframe propriétaire Skytech — le plus complexe du projet.
"""
import time
from datetime import date
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from .omnivox_models import Config, MioMessage, COURSE_CODE_RE
from .omnivox_helpers import log, _parse_date_from_text
from .omnivox_browser import debug_screenshot, wait_net, ensure_alive
from .omnivox_auth import safe_goto, recover_home, _ensure_intr


def scrape_notifications(page: Page, config: Config) -> dict:
    """Lit le widget 'Quoi de neuf ?' sur la page d'accueil."""
    import re
    log(f" [{config.slug}] === Notifications ===")
    _ensure_intr(page, config)
    try:
        body = page.locator("body").inner_text(timeout=8_000)
    except Exception:
        return {}
    notifs = {}
    patterns = [
        ("mio",        r'(\d+)\s+[Nn]ouveau[x]?\s+[Mm]io'),
        ("travaux",    r'(\d+)\s+[Nn]ouveau[x]?\s+[eé]nonc[eé]'),
        ("notes",      r'(\d+)\s+[Nn]ouvelle[s]?\s+note'),
        ("documents",  r'(\d+)\s+[Nn]ouveau[x]?\s+document'),
        ("commentaires", r'(\d+)\s+[Nn]ouveau[x]?\s+commentaire'),
    ]
    for key, pat in patterns:
        m = re.search(pat, body, re.IGNORECASE)
        if m:
            notifs[key] = int(m.group(1))
            log(f"  [{config.slug}] {key}: {notifs[key]} nouveau(x)")
    return notifs


def _wait_for_mio_frames(
    page: Page, omnivox_base: str, slug: str = "", timeout_s: int = 25
) -> tuple[Optional[object], Optional[object]]:
    """
    Attend que les frames MioListe.aspx et MioDetail.aspx soient disponibles.

    Structure réelle (confirmée par debug) :
      Default.aspx (frameset principal)
        ├── MenuBarreO.aspx
        ├── MenuPrinci.aspx
        └── MioListeDefault.aspx (nested frameset — URL contient "MioListeD")
              ├── FrListeHaut → MioListe.aspx (table#lstMIO)
              └── FrListeBas  → MioDetail.aspx (span#spanAffichage)

    Stratégie :
    1. Attendre que le nested frameset (MioListeD...) soit dans page.frames
    2. Extraire les src de FrListeHaut et FrListeBas depuis son HTML
    3. Attendre que MioListe.aspx et MioDetail.aspx chargent comme frames fils
    4. Si toujours absents → naviguer directement vers MioListe.aspx
    """
    deadline = time.time() + timeout_s

    # Phase 1 — attendre le nested frameset (MioListeD...)
    nested_fs_frame = None
    while time.time() < deadline:
        for fr in page.frames:
            url = fr.url
            if ("MioListe" in url and "MioListe.aspx" not in url
                    and "MioDetail" not in url and fr.url != "about:blank"):
                nested_fs_frame = fr
                break
        if nested_fs_frame is not None:
            break
        time.sleep(0.5)

    if nested_fs_frame is None:
        log(f" [{slug}] MIO: nested frameset introuvable après attente")
    else:
        log(f"  [{slug}] MIO nested frameset: {nested_fs_frame.url[:80]}")

    # Phase 2 — attendre MioListe.aspx et MioDetail.aspx comme frames fils
    while time.time() < deadline:
        liste_frame = None
        detail_frame = None
        for fr in page.frames:
            url = fr.url
            if "MioListe.aspx" in url:
                liste_frame = fr
            elif "MioDetail.aspx" in url:
                detail_frame = fr
        if liste_frame is not None:
            try:
                count = liste_frame.evaluate(
                    "() => document.querySelectorAll('#lstMIO tbody tr').length"
                )
                if count > 0:
                    log(f"  [{slug}] MIO frames prêtes: {count} message(s) (MioListe.aspx chargé)")
                    return liste_frame, detail_frame
            except Exception:
                pass
        time.sleep(0.5)

    # Phase 3 — fallback : extraire l'URL MioListe.aspx depuis le nested frameset et naviguer
    log(f" [{slug}] MIO: MioListe.aspx non chargé — tentative navigation directe")
    if nested_fs_frame is not None:
        try:
            mio_list_src = nested_fs_frame.evaluate("""
                () => {
                    const f = document.querySelector(
                        'frame#FrListeHaut, frame[src*="MioListe.aspx"]'
                    );
                    return f ? f.getAttribute('src') : '';
                }
            """)
            if mio_list_src:
                full_url = (f"{omnivox_base}{mio_list_src}"
                            if mio_list_src.startswith("/") else mio_list_src)
                log(f"  [{slug}] MIO: navigation directe vers {full_url[:80]}")
                page.goto(full_url, wait_until="domcontentloaded", timeout=15_000)
                time.sleep(2)
                for fr in page.frames:
                    if "MioListe.aspx" in fr.url:
                        try:
                            count = fr.evaluate(
                                "() => document.querySelectorAll('#lstMIO tbody tr').length"
                            )
                            log(f"  [{slug}] MIO direct: {count} message(s)")
                            return fr, None
                        except Exception:
                            pass
                try:
                    count = page.evaluate(
                        "() => document.querySelectorAll('#lstMIO tbody tr').length"
                    )
                    log(f"  [{slug}] MIO page directe: {count} message(s)")
                    return page, None  # type: ignore[return-value]
                except Exception:
                    pass
        except Exception as exc:
            log(f"  [{slug}] MIO fallback navigation: {exc}")

    liste_frame = None
    detail_frame = None
    for fr in page.frames:
        url = fr.url
        if "MioListe.aspx" in url:
            liste_frame = fr
        elif "MioDetail.aspx" in url:
            detail_frame = fr
    return liste_frame, detail_frame


def _mio_body_from_frame(frame, guid: str, config: Config) -> dict:
    """
    Charge MioDetail dans un frame et extrait le corps du message.
    Structure réelle : span#spanAffichage contient le contenu du message.
    """
    url = f"{config.mio_base}/Commun/Message/MioDetail.aspx?id={guid}"
    try:
        frame.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)
        try:
            frame.wait_for_selector(
                "span#spanAffichage:not(:empty), div#divAffichage table, "
                "div#AucunMsg[style*='none'], .cMessageBody, td.cBody",
                timeout=8_000
            )
        except PlaywrightTimeoutError:
            pass
        time.sleep(0.5)
        return frame.evaluate("""
            () => {
                const bodyEl = document.querySelector(
                    'span#spanAffichage, div#divAffichage, .cMessageBody, td.cBody, div#contenuWrapper'
                );
                const attach = document.querySelector(
                    'a[href*="MioPJ"], a[href*="telecharger"], .pj, .attachment, [class*="piecejoin"]'
                );
                const senderEl  = document.querySelector('.cDe, .expediteur, td.from, .msgSender');
                const subjectEl = document.querySelector('.cSujet, .sujet, .msgSubject, td.subject');
                const dateEl    = document.querySelector('.cDate, .msgDate, td.date, .dateEnvoi');
                return {
                    body:   bodyEl  ? bodyEl.innerText.trim()  : '',
                    sender: senderEl ? senderEl.innerText.trim() : '',
                    subject: subjectEl ? subjectEl.innerText.trim() : '',
                    date:   dateEl  ? dateEl.innerText.trim()  : '',
                    has_attachment: !!attach,
                };
            }
        """)
    except Exception as exc:
        log(f"    [{config.slug}] _mio_body_from_frame({guid[:8]}): {exc}")
        return {}


def _extract_mio_rows(liste_frame) -> list[dict]:
    """
    Extrait les métadonnées de tous les messages depuis le frame MioListe.
    Structure DOM réelle (Omnivox 2024): table#lstMIO tbody tr
    """
    return liste_frame.evaluate("""
        () => {
            const table = document.querySelector('table#lstMIO, table.lstMIO');
            if (!table) return [];

            const rows = Array.from(table.querySelectorAll('tbody tr[id^="tr"]'));

            return rows.map(tr => {
                const pastille = tr.querySelector(
                    '.pastille-indicateur[data-message], .drapeaux[data-message], [data-message]'
                );
                const guid = pastille ? pastille.getAttribute('data-message') : '';

                const senderEl = tr.querySelector('td.name span.msgUser, td.name');
                const sender = senderEl ? senderEl.innerText.trim() : '';

                const subjectEl = tr.querySelector('td.lsTdTitle em, td.lsTdTitle');
                const subject = subjectEl ? subjectEl.innerText.trim() : '';

                const dateEl = tr.querySelector('td.date span, td.date');
                const dateStr = dateEl ? dateEl.innerText.trim() : '';

                const hidIsNew = tr.querySelector('input[id^="hidIsNew"]');
                const isNew = hidIsNew ? hidIsNew.value.toLowerCase() === 'oui' : false;

                const hasAttach = !!tr.querySelector(
                    'a[href*="MioPJ"], .pj, .attach, [class*="attach"], '
                    + '.trombone, [class*="paperclip"], .fileSize:not(.fileSizeVide)'
                );

                const rowNum = tr.id.replace('tr', '');

                return { guid, sender, subject, date: dateStr, is_new: isNew,
                         has_attachment: hasAttach, row_num: rowNum };
            }).filter(r => r.guid && r.guid.length > 10);
        }
    """)


def _get_mio_body_modern(page: Page, guid: str, config: Config,
                         detail_frame=None) -> dict:
    """
    Récupère le corps d'un message MIO via le frame MioDetail.aspx.
    """
    if detail_frame is None:
        for fr in page.frames:
            if "MioDetail.aspx" in fr.url:
                detail_frame = fr
                break

    if detail_frame is not None:
        result = _mio_body_from_frame(detail_frame, guid, config)
        if result.get("body"):
            return result

    try:
        detail_url = f"{config.mio_base}/Commun/Message/MioDetail.aspx?id={guid}"
        page.evaluate(f"window.open('{detail_url}', '_blank')")
        time.sleep(2)
        pages = page.context.pages
        if len(pages) > 1:
            detail_page = pages[-1]
            try:
                try:
                    detail_page.wait_for_selector(
                        "span#spanAffichage, div#divAffichage", timeout=8_000
                    )
                except PlaywrightTimeoutError:
                    pass
                body = detail_page.evaluate("""
                    () => {
                        const el = document.querySelector(
                            'span#spanAffichage, div#divAffichage, body'
                        );
                        return el ? el.innerText.trim() : '';
                    }
                """)
                has_attach = bool(
                    detail_page.locator('a[href*="MioPJ"], a[href*="telecharger"], .pj').count()
                )
                detail_page.close()
                return {"body": body, "has_attachment": has_attach}
            except Exception as exc:
                log(f"  [{config.slug}] MIO body fallback [guid={guid[:8]}]: erreur lecture onglet — {exc}")
                try:
                    detail_page.close()
                except Exception:
                    pass
    except Exception as exc:
        log(f"  [{config.slug}] MIO body fallback [guid={guid[:8]}]: échec ouverture onglet — {exc}")

    log(f"  [{config.slug}] MIO body [guid={guid[:8]}]: corps vide après tous les essais")
    return {"body": "", "has_attachment": False}


def _mio_get_liste_url(page: Page, omnivox_base: str, slug: str = "") -> str:
    """
    Depuis le frameset MIO (Default.aspx), extrait l'URL de MioListe.aspx
    en naviguant à travers la hiérarchie de framesets.
    Retourne l'URL complète de MioListe.aspx, ou "" si introuvable.
    """
    try:
        page.wait_for_function(
            "() => !!document.getElementById('frMilieu')",
            timeout=12_000,
        )
        milieu_src: str = page.evaluate(
            "() => document.getElementById('frMilieu').getAttribute('src') || ''"
        )
    except PlaywrightTimeoutError:
        debug_screenshot(page, "mio_frMilieu_missing")
        log(f" [{slug}] MIO: frMilieu introuvable après 12s (screenshot sauvegardé)")
        return ""
    except Exception as exc:
        log(f"  [{slug}] MIO: erreur lecture frMilieu — {exc}")
        return ""

    if not milieu_src:
        log(f" [{slug}] MIO: frMilieu.src est vide")
        return ""

    milieu_url = (f"{omnivox_base}{milieu_src}"
                  if milieu_src.startswith("/") else milieu_src)
    log(f"  [{slug}] MIO frMilieu → {milieu_url[:90]}")

    try:
        page.goto(milieu_url, wait_until="domcontentloaded", timeout=20_000)
    except Exception as exc:
        log(f"  [{slug}] MIO: échec goto frMilieu — {exc}")
        return ""

    try:
        page.wait_for_function(
            """() => {
                return !!(
                    document.getElementById('FrListeHaut')
                    || document.querySelector(
                        'frame[id*="Haut"], frame[name*="Haut"], frame[src*="MioListe"]'
                    )
                );
            }""",
            timeout=10_000,
        )
        liste_src: str = page.evaluate(
            """() => {
                const f = document.getElementById('FrListeHaut')
                    || document.querySelector(
                        'frame[id*="Haut"], frame[name*="Haut"], frame[src*="MioListe"]'
                    );
                return f ? (f.getAttribute('src') || '') : '';
            }"""
        )
    except PlaywrightTimeoutError:
        debug_screenshot(page, "mio_FrListeHaut_missing")
        log(f" [{slug}] MIO: FrListeHaut introuvable après 10s (frame:first-child fallback désactivé)")
        return ""
    except Exception as exc:
        log(f"  [{slug}] MIO: erreur lecture FrListeHaut — {exc}")
        return ""

    if not liste_src:
        log(f" [{slug}] MIO: FrListeHaut.src est vide")
        return ""

    liste_url = (f"{omnivox_base}{liste_src}"
                 if liste_src.startswith("/") else liste_src)
    log(f"  [{slug}] MIO FrListeHaut → {liste_url[:90]}")
    return liste_url


def scrape_mio(page: Page, config: Config, output_base: Path) -> list[MioMessage]:
    """
    Scrape tous les messages MIO.

    Approche directe (sans attente de frame tracking Playwright) :
    1. Naviguer vers Default.aspx (frameset principal MIO)
    2. Extraire l'URL de frMilieu (MioListeDetailFrameset.aspx) via JS
    3. Naviguer vers MioListeDetailFrameset.aspx
    4. Extraire l'URL de FrListeHaut (MioListe.aspx) via JS
    5. Naviguer vers MioListe.aspx — table#lstMIO avec les messages
    6. Pour chaque message, naviguer vers MioDetail.aspx?id={guid} pour le corps
    """
    log(f" [{config.slug}] === MIO ===")
    ensure_alive(page)

    try:
        safe_goto(page, "mio", config)
    except RuntimeError as exc:
        log(f"  [{config.slug}] Navigation MIO échouée: {exc}")
        recover_home(page, config)
        return []

    log(f" [{config.slug}] Extraction URL MioListe.aspx...")
    omnivox_base = config.omnivox_base
    liste_url = _mio_get_liste_url(page, omnivox_base, config.slug)

    if not liste_url:
        log(f" [{config.slug}] MIO fallback: attente frame tracking Playwright...")
        liste_frame, detail_frame = _wait_for_mio_frames(page, omnivox_base, config.slug, timeout_s=15)
        if liste_frame is not None and liste_frame is not page:
            try:
                rows_data = _extract_mio_rows(liste_frame)
                if rows_data:
                    log(f"  [{config.slug}] MIO fallback: {len(rows_data)} message(s) via frame tracking")
                    return _build_mio_messages(page, rows_data, config)
            except Exception:
                pass
        log(f" [{config.slug}] MIO: impossible d'accéder à la liste des messages")
        debug_screenshot(page, "mio_no_liste_frame")
        recover_home(page, config)
        return []

    log(f"  [{config.slug}] Navigation vers MioListe.aspx...")
    try:
        page.goto(liste_url, wait_until="domcontentloaded", timeout=config.timeout_ms)
    except Exception as exc:
        log(f"  [{config.slug}] MIO: échec navigation MioListe.aspx: {exc}")
        recover_home(page, config)
        return []

    try:
        page.wait_for_function(
            "() => document.querySelectorAll('table#lstMIO tbody tr, table.lstMIO tbody tr').length > 0",
            timeout=12_000,
        )
    except PlaywrightTimeoutError:
        pass

    try:
        rows_data: list[dict] = _extract_mio_rows(page)
    except Exception as exc:
        log(f"  [{config.slug}] Erreur extraction liste MIO: {exc}")
        debug_screenshot(page, "mio_extract_error")
        recover_home(page, config)
        return []

    log(f"  [{config.slug}] {len(rows_data)} message(s) dans la liste")
    if not rows_data:
        debug_screenshot(page, "mio_empty_inbox")

    messages = _build_mio_messages(page, rows_data, config)
    log(f"  [{config.slug}] Total MIO: {len(messages)} message(s)")

    try:
        _ensure_intr(page, config)
    except Exception:
        log(f" [{config.slug}] Avertissement: impossible de revenir à l'intranet après MIO")
    return messages


def _build_mio_messages(
    page: Page, rows_data: list[dict], config: Config
) -> list[MioMessage]:
    """
    Construit les MioMessage depuis rows_data.
    Pour chaque GUID, navigue vers MioDetail.aspx pour obtenir le corps.
    """
    messages: list[MioMessage] = []
    for row in rows_data:
        guid           = row.get("guid", "").strip()
        sender         = row.get("sender", "").strip()
        subject        = row.get("subject", "").strip()
        date_raw       = row.get("date", "").strip()
        is_read        = not row.get("is_new", False)
        has_attachment = row.get("has_attachment", False)

        if not guid:
            continue

        course_code = ""
        m_code = COURSE_CODE_RE.search(sender)
        if m_code:
            course_code = m_code.group(1)

        date_iso = _parse_date_from_text(date_raw) or date.today().isoformat()

        preview_from_list = ""
        if "\xa0\xa0" in subject:
            parts = subject.split("\xa0\xa0", 1)
            subject = parts[0].strip()
            preview_from_list = parts[1].lstrip("\xa0").strip()

        _PLACEHOLDER = "Aucun message sélectionné"
        body_text = ""
        detail_url = f"{config.mio_base}/Commun/Message/MioDetail.aspx?id={guid}"
        try:
            page.goto(detail_url, wait_until="domcontentloaded",
                      timeout=config.timeout_ms)
            try:
                page.wait_for_function(
                    """() => {
                        const el = document.querySelector('span#spanAffichage, div#divAffichage');
                        return el && el.innerText.trim().length > 0;
                    }""",
                    timeout=8_000,
                )
            except PlaywrightTimeoutError:
                pass
            detail_data = page.evaluate("""
                () => {
                    const bodyEl = document.querySelector(
                        'span#spanAffichage, div#divAffichage, .cMessageBody'
                    );
                    const attach = document.querySelector(
                        'a[href*="MioPJ"], a[href*="telecharger"], .pj, .attachment'
                    );
                    return {
                        body: bodyEl ? (bodyEl.innerText || bodyEl.textContent || '').trim() : '',
                        has_attachment: !!attach
                    };
                }
            """)
            body_text = detail_data.get("body", "")
            if detail_data.get("has_attachment"):
                has_attachment = True
        except Exception as exc:
            log(f"    [{config.slug}] Corps '{subject[:30]}': {exc}")

        if not body_text or _PLACEHOLDER in body_text:
            body_text = preview_from_list

        if not subject:
            subject = f"Message_{guid[:8]}"

        msg = MioMessage(
            msg_id=guid,
            sender=sender,
            course_code=course_code,
            subject=subject,
            date_iso=date_iso,
            body=body_text,
            is_read=is_read,
            has_attachment=has_attachment,
        )
        messages.append(msg)
        status = "📬" if not is_read else "📭"
        body_preview = f" [{len(body_text)} chars]" if body_text else " [sans corps]"
        log(f"  [{config.slug}] {status} {sender[:25]} — {subject[:40]}{body_preview}")

    return messages
