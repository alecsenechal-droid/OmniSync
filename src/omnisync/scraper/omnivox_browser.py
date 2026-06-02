"""
Gestion bas-niveau du navigateur Playwright.
Responsabilité unique : cycle de vie du browser, frames, viewstate ASP.NET.
Zéro logique métier Omnivox, zéro navigation applicative.
"""
import os
import time
from typing import Optional, Union

from playwright.sync_api import (
    BrowserContext,
    FrameLocator,
    Locator,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
)

from .omnivox_models import Config
from .omnivox_helpers import log


def launch(playwright: Playwright, config: Config) -> tuple[BrowserContext, Page]:
    from omnisync import paths

    profile_dir = paths.browser_profile_dir()
    paths.ensure_runtime_dirs()
    context = playwright.chromium.launch_persistent_context(
        str(profile_dir),
        headless=config.headless,
        slow_mo=60,
        accept_downloads=True,
    )
    context.set_default_timeout(config.timeout_ms)
    page = context.pages[0] if context.pages else context.new_page()
    page.set_default_timeout(config.timeout_ms)
    return context, page


def wait_net(page: Page, timeout_ms: int = 10_000) -> None:
    """Attend domcontentloaded. Jamais networkidle — Omnivox garde des requêtes ouvertes."""
    try:
        page.wait_for_load_state("domcontentloaded", timeout=min(timeout_ms, 10_000))
    except PlaywrightTimeoutError:
        pass


def debug_screenshot(page: Page, name: str) -> None:
    """Screenshot de debug — appelé automatiquement sur erreur de navigation."""
    try:
        from omnisync import paths

        dest = paths.logs_dir() / "debug" / f"{name}.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(dest))
        log(f"  [DEBUG] screenshot -> {dest.name}  url={page.url[:70]}")
    except Exception:
        pass


def ensure_alive(page: Page) -> None:
    """Vérifie que la session Omnivox est active.
    Détecte : session expirée (redirect login), page erreur ASP.NET,
    champ password visible (re-auth silencieuse d'ASP.NET Forms Auth).
    """
    url = page.url.lower()
    if any(k in url for k in ["login", "identification", "connexion"]):
        raise RuntimeError("Session expirée — page login détectée")
    try:
        if page.locator("input[type='password']").count():
            raise RuntimeError("Session expirée — champ password détecté dans la page")
    except PlaywrightTimeoutError:
        pass
    try:
        html = page.content()
        html_low = html.lower()
        if ("server error" in html_low or "asp.net" in html_low) and "exception" in html_low:
            raise RuntimeError("Page erreur ASP.NET détectée")
    except PlaywrightTimeoutError:
        raise RuntimeError("Page inaccessible (timeout content)")


def get_frame(page: Page, url_part: str):
    """Retrouve un frame par partie d'URL — toujours re-fetché, jamais mis en cache.
    Omnivox peut recréer des frames ; une référence fixe devient invalide silencieusement.
    Lève RuntimeError si introuvable.
    """
    for fr in page.frames:
        if url_part.lower() in fr.url.lower():
            return fr
    raise RuntimeError(
        f"Frame introuvable: '{url_part}' — frames actifs: "
        + ", ".join(f.url[:40] for f in page.frames)
    )


def get_frame_safe(page: Page, url_part: str):
    """Comme get_frame mais retourne None au lieu de lever."""
    try:
        return get_frame(page, url_part)
    except RuntimeError:
        return None


def wait_postback(page: Page, timeout_ms: int = 8_000) -> None:
    """Attend qu'un postback ASP.NET soit terminé."""
    try:
        page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        pass


def get_viewstate(page: Page) -> str:
    """Lit la valeur courante du ViewState ASP.NET (détection de postback)."""
    try:
        loc = page.locator('input[name="__VIEWSTATE"]').first
        if loc.count():
            return loc.input_value(timeout=2_000) or ""
    except Exception:
        pass
    return ""


def wait_viewstate_change(page: Page, old_viewstate: str, timeout_ms: int = 10_000) -> bool:
    """Attend que le ViewState change après un postback ASP.NET.
    Retourne True si changé, False si timeout.

    Usage:
        old = get_viewstate(page)
        page.locator("select").select_option(value="X")
        wait_viewstate_change(page, old)
    """
    if not old_viewstate:
        wait_postback(page, timeout_ms)
        return True
    try:
        page.wait_for_function(
            """
            old => {
                const vs = document.querySelector('input[name="__VIEWSTATE"]');
                return vs ? vs.value !== old : false;
            }
            """,
            old_viewstate,
            timeout=timeout_ms,
        )
        return True
    except PlaywrightTimeoutError:
        return False
