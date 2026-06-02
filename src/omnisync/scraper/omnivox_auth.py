"""
Navigation Omnivox et authentification complète.
Responsabilité unique : SSO LEA/ESTD, login, MFA, recovery.
Utilise config.omnivox_base (pas de global rebindable) et MODULES (dict mutable partagé).
"""
import os
import time
from typing import Iterable, Optional

from playwright.sync_api import (
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from .omnivox_models import Config, lea_host, estd_host
from .omnivox_helpers import log
from .omnivox_browser import wait_net, debug_screenshot
from .omnivox_loader import MODULES


# ── Helpers de sélection ──────────────────────────────────────────────────────

def first_visible(page: Page, selectors: Iterable[str]) -> Optional[Locator]:
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            if loc.count() and loc.is_visible(timeout=1_500):
                return loc
        except PlaywrightTimeoutError:
            continue
    return None


def click_first(page: Page, selectors: Iterable[str], timeout_ms: int) -> bool:
    loc = first_visible(page, selectors)
    if not loc:
        return False
    loc.click(timeout=timeout_ms)
    return True


# ── Navigation principale ─────────────────────────────────────────────────────

def safe_goto(page: Page, module_name: str, config: Config) -> None:
    """Navigation centrale et déterministe.
    - Pour LEA/ESTD : établit la session SSO via l'intranet d'abord
    - Pour les autres : URL directe
    - Vérifie le marqueur URL après navigation
    - Screenshot + RuntimeError si validation échoue
    """
    mod    = MODULES[module_name]
    url    = mod["url"]
    marker = mod["marker"]
    sel    = mod.get("selector")

    LEA_MODULES  = {"lea", "lea_travaux", "lea_documents", "lea_notes", "lea_calendrier"}
    ESTD_MODULES = {"cheminement", "examens", "documents_officiels"}

    if module_name in LEA_MODULES:
        _ensure_lea(page, config)
        if module_name != "lea":
            log(f"  [NAV] {module_name} -> {url[:60]}")
            page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)
    elif module_name in ESTD_MODULES:
        _ensure_estd(page, config)
        if estd_host(config.slug) in page.url:
            wait_net(page, 2_000)
            log(f"  [NAV] {module_name} -> {url[:60]}")
            page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)
        else:
            raise RuntimeError(
                f"Module ESTD '{module_name}' inaccessible — "
                f"session ESTD non etablie (URL actuelle: {page.url[:60]})"
            )
    else:
        log(f"  [NAV] {module_name} -> {url[:60]}")
        page.goto(url, wait_until="domcontentloaded", timeout=config.timeout_ms)

    if sel:
        try:
            page.wait_for_selector(sel, state="attached", timeout=10_000)
        except PlaywrightTimeoutError:
            pass

    current = page.url
    if marker.lower() not in current.lower():
        debug_screenshot(page, f"nav_fail_{module_name}")
        raise RuntimeError(
            f"Navigation '{module_name}' échouée — redirection silencieuse?\n"
            f"  Attendu  : '{marker}' dans l'URL\n"
            f"  Obtenu   : {current}"
        )
    log(f"  [OK]  {module_name}  url={current[:70]}")


def recover_home(page: Page, config: Config) -> None:
    """Retour sécurisé à l'intranet après un crash de module."""
    try:
        log("  [RECOVERY] Retour home...")
        page.goto(
            f"{config.omnivox_base}/intr/",
            wait_until="domcontentloaded",
            timeout=config.timeout_ms,
        )
        log(f"  [RECOVERY] OK — url={page.url[:60]}")
    except Exception as exc:
        log(f"  [RECOVERY] Échec: {exc}")


# ── Helpers de session SSO ────────────────────────────────────────────────────

def _ensure_intr(page: Page, config: Config) -> None:
    """Retourne à l'intranet si on n'y est pas déjà."""
    if "/intr/" in page.url and "omnivox.ca" in page.url:
        return
    safe_goto(page, "home", config)


def _navigate_to_lea_via_sso(page: Page, config: Config) -> bool:
    """
    Établit la session LEA via le SSO du portail Omnivox.
    Navigation : intranet → clic lien "LÉA" (Skytech SSO) → climoilou-lea.omnivox.ca/cvir/

    Omnivox LEA = IdService=CVIE dans les liens Skytech.aspx de l'intranet.
    IMPORTANT : Ne jamais aller directement sur climoilou-lea.omnivox.ca
    sans passer par ce SSO — ça provoque une déconnexion forcée.
    """
    omnivox_base = config.omnivox_base
    if "/intr/" not in page.url or "omnivox.ca" not in page.url:
        page.goto(f"{omnivox_base}/intr/",
                  wait_until="domcontentloaded", timeout=config.timeout_ms)
        wait_net(page, 8_000)

    if "/intr/" not in page.url:
        log("  [LEA-SSO] Impossible d'atteindre l'intranet")
        return False

    lea_selectors = [
        "a[href*='Skytech.aspx'][href*='IdService=CVIE']",
        "a[href*='Skytech.aspx'][href*='CVIE']",
        "a[href*='Skytech.aspx'][href*='cvie']",
        "a[href*='RedirigeLEA']",
        f"a[href*='{config.slug}-lea']",
        "a:has-text('LÉA')",
        "a:has-text('Léa')",
    ]
    lea_link = first_visible(page, lea_selectors)

    if lea_link is None:
        try:
            href_js = page.evaluate("""
                () => {
                    const a = Array.from(document.querySelectorAll('a[href]')).find(a => {
                        const h = a.getAttribute('href') || '';
                        return h.includes('IdService=CVIE') || h.includes('Skytech') &&
                               (h.includes('cvie') || h.includes('CVIE'));
                    });
                    return a ? a.getAttribute('href') : null;
                }
            """)
            if href_js:
                full = href_js if href_js.startswith("http") else f"{omnivox_base}{href_js}"
                log(f"  [LEA-SSO] Lien JS: {full[:70]}")
                page.goto(full, wait_until="domcontentloaded", timeout=config.timeout_ms)
                wait_net(page, config.timeout_ms)
                deadline = time.time() + 15
                while time.time() < deadline:
                    if lea_host(config.slug) in page.url:
                        log(f"  [LEA-SSO] Session etablie via JS: {page.url[:60]}")
                        return True
                    time.sleep(0.5)
        except Exception as exc:
            log(f"  [LEA-SSO] Scan JS echoue: {exc}")
        log("  [LEA-SSO] Aucun lien LEA trouve")
        return False

    href = lea_link.get_attribute("href") or ""
    log(f"  [LEA-SSO] Lien trouve: {href[:70]}")
    expected = f"C={config.institution_code}"
    if expected in href:
        log(f"  [{config.slug}] SSO OK vers LEA")
    elif "lk=" in href:
        log(f"  [{config.slug}] SSO OK vers LEA (format lk=, C= absent)")
    else:
        log(f"  [{config.slug}] WARN SSO mismatch: href ne contient pas {expected} (href={href[:80]})")
    lea_link.click()
    wait_net(page, config.timeout_ms)
    deadline = time.time() + 20
    while time.time() < deadline:
        if lea_host(config.slug) in page.url:
            log(f"  [LEA-SSO] Session etablie: {page.url[:60]}")
            return True
        time.sleep(0.5)
    log(f"  [LEA-SSO] Pas redirige vers LEA apres 20s — URL: {page.url[:70]}")
    return False


def _ensure_lea(page: Page, config: Config) -> None:
    """
    Navigue vers Léa via le SSO du portail (pas d'URL directe).
    La navigation directe vers climoilou-lea.omnivox.ca provoque
    une déconnexion forcée — toujours passer par l'intranet.
    """
    if lea_host(config.slug) in page.url and "/cvir/" in page.url:
        return
    if not _navigate_to_lea_via_sso(page, config):
        raise RuntimeError("Navigation vers LEA echouee (SSO)")


def _ensure_estd(page: Page, config: Config) -> None:
    """
    Navigue vers ESTD via le SSO du portail.
    Même logique que LEA — pas d'URL directe.
    """
    if estd_host(config.slug) in page.url:
        return
    omnivox_base = config.omnivox_base
    if "/intr/" not in page.url or "omnivox.ca" not in page.url:
        page.goto(f"{omnivox_base}/intr/",
                  wait_until="domcontentloaded", timeout=config.timeout_ms)
        wait_net(page, 8_000)

    estd_selectors = [
        "a[href*='Skytech.aspx'][href*='IdService=GRCH']",
        "a[href*='Skytech.aspx'][href*='IdService=HOREX']",
        "a[href*='Skytech.aspx'][href*='IdService=DINF']",
        "a[href*='Skytech.aspx'][href*='lk=%2festd%2fgrch']",
        "a[href*='Skytech.aspx'][href*='lk=%2festd%2fhrex']",
        "a[href*='RedirigESTD']",
        f"a[href*='{config.slug}-estd']",
    ]
    estd_link = first_visible(page, estd_selectors)
    if estd_link:
        href = estd_link.get_attribute("href") or ""
        log(f"  [ESTD-SSO] Lien trouve: {href[:70]}")
        expected = f"C={config.institution_code}"
        if expected in href:
            log(f"  [{config.slug}] SSO OK vers ESTD")
        elif "lk=" in href:
            log(f"  [{config.slug}] SSO OK vers ESTD (format lk=, C= absent)")
        else:
            log(f"  [{config.slug}] WARN SSO mismatch: href ne contient pas {expected} (href={href[:80]})")
        estd_link.click()
        wait_net(page, config.timeout_ms)
        deadline = time.time() + 20
        while time.time() < deadline:
            if estd_host(config.slug) in page.url:
                log(f"  [ESTD-SSO] Session etablie: {page.url[:60]}")
                return
            time.sleep(0.5)
        log(f"  [ESTD-SSO] Pas redirige vers ESTD — URL: {page.url[:60]}")
        return
    log("  [ESTD-SSO] Aucun lien ESTD trouve dans l'intranet (normal si pas accessible)")


# ── MFA ───────────────────────────────────────────────────────────────────────

def is_mfa_page(page: Page) -> bool:
    url = page.url.lower()
    if any(k in url for k in ["/mfa", "/2fa", "/otp", "/verification"]):
        return True
    try:
        body = page.locator("body").inner_text(timeout=3_000).lower()
        return any(k in body for k in [
            "authentification à deux", "double authentification",
            "approuver la demande", "authenticator", "code de vérification",
        ])
    except Exception:
        return False


def handle_mfa(page: Page, config: Config, wait_seconds: int = 90) -> None:
    """Gère la page MFA Omnivox/Microsoft.

    Intègre la logique de garde : en mode headless sans OMNISYNC_MFA_WAIT_SECONDS,
    lève RuntimeError avec instructions plutôt que d'attendre indéfiniment.
    """
    if not is_mfa_page(page):
        return

    wait_raw = os.environ.get("OMNISYNC_MFA_WAIT_SECONDS", "").strip()
    if wait_raw:
        wait = int(wait_raw)
    elif not getattr(config, "headless", True):
        wait = 120
    else:
        wait = 0

    if wait <= 0:
        try:
            debug_screenshot(page, "omnisync_mfa_required")
        except Exception:
            pass
        raise RuntimeError(
            "MFA_REQUIRED: Omnivox demande une validation humaine. "
            "Relancez avec HEADLESS=false et OMNISYNC_MFA_WAIT_SECONDS=120."
        )

    log(""); log("=" * 60)
    log("  MFA DÉTECTÉ — APPROUVE SUR TON TÉLÉPHONE MAINTENANT")
    log("=" * 60)
    for r in range(wait, 0, -1):
        log(f"  Attente MFA: {r}s...")
        time.sleep(1)
    wait_net(page, config.timeout_ms)


# ── Login ─────────────────────────────────────────────────────────────────────

def _do_login_form(page: Page, config: Config) -> bool:
    """Remplit et soumet le formulaire de login. Retourne True si succès."""
    mat = first_visible(page, ["input[name='NoDA']", "input[name='noDA']", "input[type='text']"])
    pwd = first_visible(page, ["input[name='MotPasse']", "input[type='password']"])
    if not mat or not pwd:
        log("  Login: champs de formulaire introuvables")
        debug_screenshot(page, "login_form_missing")
        return False
    mat.fill(config.matricule)
    pwd.fill(config.password)
    if not click_first(page, ["button[type='submit']", "input[type='submit']", "button:has-text('Connexion')"], config.timeout_ms):
        pwd.press("Enter")
    wait_net(page, config.timeout_ms)
    handle_mfa(page, config)
    time.sleep(1)
    wait_net(page, 10_000)
    if "/intr/" in page.url:
        return True
    time.sleep(2)
    wait_net(page, 8_000)
    return "/intr/" in page.url


def login(page: Page, config: Config, max_retries: int = 3) -> None:
    omnivox_url = f"{config.omnivox_base}/"
    log(f"Connexion à {omnivox_url}")
    page.goto(omnivox_url, wait_until="domcontentloaded", timeout=config.timeout_ms)
    wait_net(page, config.timeout_ms)

    if "/intr/" in page.url:
        log("Session déjà active.")
        return

    for attempt in range(1, max_retries + 1):
        log(f"  Tentative de connexion #{attempt}...")
        if "login" not in page.url.lower() and "identification" not in page.url.lower():
            page.goto(omnivox_url, wait_until="domcontentloaded", timeout=config.timeout_ms)
            wait_net(page, 5_000)
        success = _do_login_form(page, config)
        if success:
            log(f"  Connexion réussie (tentative #{attempt})")
            return
        if attempt < max_retries:
            log(f"  Login échoué — URL: {page.url[:60]} — Réessai dans 3s...")
            debug_screenshot(page, f"login_fail_attempt_{attempt}")
            time.sleep(3)
            page.goto(omnivox_url, wait_until="domcontentloaded", timeout=config.timeout_ms)
            wait_net(page, 5_000)

    debug_screenshot(page, "login_final_fail")
    raise RuntimeError(
        f"Login Omnivox échoué après {max_retries} tentatives. "
        f"URL finale: {page.url}"
    )


def relogin_if_needed(page: Page, config: Config) -> bool:
    """Vérifie si la session est expirée et re-log si nécessaire.
    Retourne True si la session est (re)établie, False si échec.
    """
    url = page.url.lower()
    is_login_page = any(k in url for k in ["login", "identification", "connexion", "omnivox.ca/"])
    has_pwd_field = False
    try:
        has_pwd_field = page.locator("input[type='password']").count() > 0
    except Exception:
        pass

    if not (is_login_page or has_pwd_field):
        return True

    log("  [SESSION] Expirée — re-connexion automatique...")
    try:
        login(page, config)
        log("  [SESSION] Re-connexion réussie")
        return True
    except Exception as exc:
        log(f"  [SESSION] Re-connexion échouée: {exc}")
        return False
