"""
moodle_engine.py — Scraper Moodle REST API pour OmniSync.

Supporte trois modes d'authentification :
  1. Token direct : si l'utilisateur a un wstoken Moodle (Profil → Clés de sécurité),
     passer directement via scrape_moodle_with_token().

  2. Native (REST direct) : instances Moodle avec login/mot de passe natif.
     POST /login/token.php → token → appels REST.

  3. SSO Microsoft (Playwright) : instances Decclic et autres avec Azure AD/SAML2.
     Playwright navigue le flow SSO, intercepte le token depuis moodlemobile://.
     La page AAD de Cégep Limoilou est une SPA — l'URL ne change pas entre les
     étapes email et mot de passe. Le champ passwd est présent dans le DOM dès
     le départ mais devient visible seulement après clic sur Suivant.
     Nécessite state="visible" pour attendre la transition.

  4. SSO avec session persistante : charge un storage_state sauvegardé depuis
     un run précédent (init-moodle). Si la session Microsoft est encore valide,
     le MFA est skippé.
"""
from __future__ import annotations

import base64
import re
import time
from typing import TYPE_CHECKING, Iterator
from zoneinfo import ZoneInfo

import requests

if TYPE_CHECKING:
    from playwright.sync_api import Page

TZ_UTC = ZoneInfo("UTC")
_TIMEOUT = 30


class MoodleAuthError(RuntimeError):
    """Identifiants invalides, service non activé, SSO requis, ou session expirée."""


class MoodleMFARequired(MoodleAuthError):
    """MFA Microsoft requis — impossible de compléter automatiquement.
    Lancez: run.bat init-moodle pour sauvegarder une session valide.
    """


class MoodleAPIError(RuntimeError):
    """Erreur retournée par l'API Moodle."""


# ── Auth natif (REST) ─────────────────────────────────────────────────────────

def get_token(base_url: str, username: str, password: str) -> str:
    """
    Obtient un token Moodle via /login/token.php (auth native, sans SSO).

    Lève MoodleAuthError si les credentials sont invalides ou si le service
    moodle_mobile_app n'est pas activé.
    """
    url = f"{base_url.rstrip('/')}/login/token.php"
    try:
        resp = requests.post(url, data={
            "username": username,
            "password": password,
            "service": "moodle_mobile_app",
        }, timeout=_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise MoodleAuthError(f"Connexion Moodle impossible ({base_url}): {exc}") from exc

    data = resp.json()
    if "error" in data:
        raise MoodleAuthError(f"Moodle auth: {data.get('error', 'erreur inconnue')}")
    token = data.get("token")
    if not token:
        raise MoodleAuthError("Moodle: token absent dans la réponse")
    return token


def _uses_sso(base_url: str) -> bool:
    """Détecte si l'instance Moodle utilise une auth SSO (Microsoft, Google, etc.)."""
    try:
        r = requests.get(
            f"{base_url.rstrip('/')}/login/index.php",
            timeout=_TIMEOUT, allow_redirects=True,
        )
        return "microsoftonline.com" in r.url or "login.live.com" in r.url
    except Exception:
        return False


# ── Auth SSO via Playwright ───────────────────────────────────────────────────

def _setup_token_capture(page: "Page", token_holder: list[str]):
    """
    Installe les listeners pour capturer le token moodlemobile://.

    page.route() ne fonctionne pas pour les schémas custom dans Chromium.
    On utilise response (Location header), requestfailed (ERR_UNKNOWN_URL_SCHEME)
    et request (navigation) comme trois niveaux de capture.

    Retourne une fonction cleanup() à appeler après.
    """
    def _extract(url_str: str) -> None:
        m = re.search(r"moodlemobile://token=([A-Za-z0-9+/=_-]+)", url_str)
        if m and not token_holder:
            try:
                raw = m.group(1) + "==="
                decoded = base64.b64decode(raw[:len(raw) - len(raw) % 4]).decode("utf-8")
                parts = decoded.split(":::")
                if len(parts) >= 2:
                    token_holder.append(parts[1])
            except Exception:
                pass

    def on_response(response) -> None:
        try:
            location = response.headers.get("location", "")
            if "moodlemobile://" in location:
                _extract(location)
        except Exception:
            pass

    def on_requestfailed(request) -> None:
        if "moodlemobile://" in request.url:
            _extract(request.url)

    def on_request(request) -> None:
        if "moodlemobile://" in request.url:
            _extract(request.url)

    page.on("response", on_response)
    page.on("requestfailed", on_requestfailed)
    page.on("request", on_request)

    def cleanup() -> None:
        try:
            page.remove_listener("response", on_response)
            page.remove_listener("requestfailed", on_requestfailed)
            page.remove_listener("request", on_request)
        except Exception:
            pass

    return cleanup


def _wait_for_token_after_login(
    page: "Page",
    base_url: str,
    token_holder: list[str],
    launch_url: str,
    timeout: float = 30.0,
) -> None:
    """
    Après le login Microsoft, attend que le token soit capturé.

    Stratégie : dès que l'URL revient sur le domaine Moodle (SSO terminé),
    re-navigue vers launch.php — Moodle voit la session active et redirige
    immédiatement vers moodlemobile://token=... (capturé par les listeners).
    """
    moodle_domain = base_url.replace("https://", "").replace("http://", "").split("/")[0]
    deadline = time.time() + timeout
    retried = False
    kmsi_handled = False

    while not token_holder and time.time() < deadline:
        try:
            current_url = page.url
            # Page KMSI ("Rester connecté ?") — clic JS puis fallback navigation
            if "kmsi" in current_url.lower() and not kmsi_handled:
                kmsi_handled = True
                try:
                    page.evaluate(
                        "() => { const b = document.getElementById('idBtn_Back')"
                        " || document.getElementById('idSIButton9');"
                        " if (b) b.click(); }"
                    )
                except Exception:
                    pass
                time.sleep(2)
                try:
                    if "kmsi" in page.url.lower():
                        page.goto(launch_url, wait_until="domcontentloaded", timeout=15_000)
                except Exception:
                    pass
            elif (moodle_domain in current_url
                    and "microsoftonline" not in current_url
                    and not retried):
                retried = True
                time.sleep(1)
                try:
                    page.goto(launch_url, wait_until="domcontentloaded", timeout=15_000)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=2_000)
        except Exception:
            pass


def get_token_via_playwright(
    page: Page,
    base_url: str,
    ms_username: str,
    ms_password: str,
) -> str:
    """Obtient un token Moodle via SSO Microsoft avec Playwright (contexte existant)."""
    token_holder: list[str] = []
    passport = str(int(time.time()))
    launch_url = (
        f"{base_url.rstrip('/')}/admin/tool/mobile/launch.php"
        f"?service=moodle_mobile_app&passport={passport}&urlscheme=moodlemobile"
    )

    cleanup = _setup_token_capture(page, token_holder)
    try:
        try:
            page.goto(launch_url, wait_until="domcontentloaded", timeout=45_000)
        except Exception:
            pass

        if token_holder:
            return token_holder[0]

        if "microsoftonline.com" not in page.url and "login.live.com" not in page.url:
            raise MoodleAuthError(
                f"Redirection SSO inattendue après launch.php: {page.url[:100]}"
            )

        _do_microsoft_login(page, ms_username, ms_password, token_holder)
        _wait_for_token_after_login(page, base_url, token_holder, launch_url)

        if not token_holder:
            _check_for_mfa(page)
            raise MoodleAuthError(
                f"Token Moodle non reçu après SSO Microsoft. URL: {page.url[:100]}\n"
                "Si MFA requis: lancez 'run.bat init-moodle' pour sauvegarder une session."
            )
        return token_holder[0]
    finally:
        cleanup()


def get_token_via_playwright_with_session(
    browser,
    base_url: str,
    ms_username: str,
    ms_password: str,
    session_path: str | None = None,
    save_session: bool = True,
) -> tuple[str, str | None]:
    """
    Obtient un token Moodle via SSO Microsoft, avec gestion de session persistante.

    Crée un NOUVEAU contexte Playwright (cookies indépendants d'Omnivox).
    Si session_path pointe vers un fichier existant, charge la session sauvegardée
    pour éviter de refaire le MFA.

    Returns:
        (token, saved_session_path_or_None)
        saved_session_path est None si la session n'a pas pu être sauvegardée.

    Raises:
        MoodleMFARequired si Microsoft demande le MFA et qu'il n'y a pas de session.
        MoodleAuthError pour les autres erreurs.
    """
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    ctx_kwargs: dict = {}
    if session_path:
        from pathlib import Path
        if Path(session_path).exists():
            ctx_kwargs["storage_state"] = session_path

    context = browser.new_context(**ctx_kwargs)
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        (function() {
            var _t = setInterval(function() {
                if (window.location.href.indexOf('kmsi') === -1) return;
                var forms = document.querySelectorAll('form');
                for (var i = 0; i < forms.length; i++) {
                    if (forms[i].querySelector('input[name="SAMLResponse"]')) {
                        clearInterval(_t); forms[i].submit(); return;
                    }
                }
                var b = document.getElementById('idSIButton9')
                     || document.getElementById('idBtn_Back');
                if (b) { clearInterval(_t); b.click(); }
            }, 50);
            setTimeout(function() { clearInterval(_t); }, 30000);
        })();
    """)
    page = context.new_page()
    token_holder: list[str] = []

    passport = str(int(time.time()))
    launch_url = (
        f"{base_url.rstrip('/')}/admin/tool/mobile/launch.php"
        f"?service=moodle_mobile_app&passport={passport}&urlscheme=moodlemobile"
    )

    cleanup = _setup_token_capture(page, token_holder)
    try:
        try:
            page.goto(launch_url, wait_until="domcontentloaded", timeout=45_000)
        except Exception:
            pass

        if token_holder:
            # Token immédiat (session encore valide → Microsoft a skippé le login)
            if save_session and session_path:
                context.storage_state(path=session_path)
            return token_holder[0], session_path

        if "microsoftonline.com" not in page.url and "login.live.com" not in page.url:
            raise MoodleAuthError(
                f"Redirection SSO inattendue après launch.php: {page.url[:100]}"
            )

        # Session expirée ou absente — tenter le login interactif
        _do_microsoft_login(page, ms_username, ms_password, token_holder)
        _wait_for_token_after_login(page, base_url, token_holder, launch_url)

        if not token_holder:
            _check_for_mfa(page)
            raise MoodleAuthError(
                f"Token Moodle non reçu après SSO Microsoft. URL: {page.url[:100]}\n"
                "Lancez 'run.bat init-moodle' pour sauvegarder une session MFA."
            )

        # Sauvegarder la session après login réussi
        if save_session and session_path:
            context.storage_state(path=session_path)

        return token_holder[0], session_path

    finally:
        cleanup()
        page.close()
        context.close()


def _do_microsoft_login(
    page: "Page",
    ms_username: str,
    ms_password: str,
    token_holder: list[str],
) -> None:
    """
    Effectue le login Microsoft sur la page AAD (SPA).

    La page SPA garde le même URL tout au long du flow.
    Les inputs email et mot de passe sont dans le DOM dès le départ,
    mais le mot de passe ne devient visible (state="visible") qu'après
    clic sur Suivant.
    """
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    # Étape 1 : email (state="visible" car la SPA peut mettre du temps)
    try:
        page.wait_for_selector(
            "input[name='loginfmt'], input[type='email']",
            timeout=15_000, state="visible",
        )
        email_loc = page.locator("input[name='loginfmt'], input[type='email']").first
        email_loc.click()
        email_loc.fill(ms_username)
    except PlaywrightTimeoutError as exc:
        raise MoodleAuthError(f"Microsoft login — champ email introuvable: {exc}") from exc

    # Clic sur Suivant / Next
    try:
        page.locator(
            "#idSIButton9, input[type='submit'], button[type='submit']"
        ).first.click()
    except Exception as exc:
        raise MoodleAuthError(f"Microsoft login — bouton Suivant introuvable: {exc}") from exc

    # Étape 2 : mot de passe — attendre state="visible" (transition SPA)
    try:
        page.wait_for_selector(
            "input[name='passwd'], input[type='password']",
            timeout=15_000, state="visible",
        )
        passwd_loc = page.locator("input[name='passwd'], input[type='password']").first
        passwd_loc.click()
        passwd_loc.fill(ms_password)
    except PlaywrightTimeoutError as exc:
        raise MoodleAuthError(f"Microsoft login — champ mot de passe introuvable: {exc}") from exc

    # Clic sur Se connecter / Sign in
    try:
        page.locator(
            "#idSIButton9, input[type='submit'], button[type='submit']"
        ).first.click()
        page.wait_for_load_state("networkidle", timeout=45_000)
    except PlaywrightTimeoutError as exc:
        raise MoodleAuthError(
            f"Microsoft login — erreur après soumission mot de passe: {exc}"
        ) from exc


def _check_for_mfa(page: "Page") -> None:
    """Lève MoodleMFARequired si la page Microsoft affiche un défi MFA."""
    try:
        text = page.evaluate("() => document.body.innerText || ''")
        mfa_hints = {"verify your identity", "vérifier votre identité",
                     "text +", "call +", "authenticator app", "application authenticator",
                     "more information", "plus d'informations"}
        text_lower = text.lower()
        if any(hint in text_lower for hint in mfa_hints):
            raise MoodleMFARequired(
                "Microsoft demande une vérification MFA (SMS/appel).\n"
                "Lancez 'run.bat init-moodle' dans un terminal pour compléter le MFA manuellement "
                "et sauvegarder la session."
            )
    except MoodleMFARequired:
        raise
    except Exception:
        pass


# ── Appel générique REST ──────────────────────────────────────────────────────

def _call(base_url: str, token: str, wsfunction: str, **params) -> dict | list:
    """Appel générique à l'API REST Moodle. Lève MoodleAPIError sur erreur JSON."""
    url = f"{base_url.rstrip('/')}/webservice/rest/server.php"
    try:
        resp = requests.get(url, params={
            "wstoken": token,
            "wsfunction": wsfunction,
            "moodlewsrestformat": "json",
            **params,
        }, timeout=_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise MoodleAPIError(f"{wsfunction}: {exc}") from exc

    data = resp.json()
    if isinstance(data, dict) and "exception" in data:
        raise MoodleAPIError(
            f"{wsfunction}: {data.get('message', data.get('exception', 'erreur API'))}"
        )
    return data


# ── Fonctions métier ──────────────────────────────────────────────────────────

def get_userid(base_url: str, token: str) -> int:
    """Retourne le userid de l'utilisateur authentifié."""
    result = _call(base_url, token, "core_webservice_get_site_info")
    return int(result["userid"])


def get_courses(base_url: str, token: str, userid: int) -> list[dict]:
    """
    Retourne la liste des cours inscrits.
    Chaque dict contient au minimum: id, shortname, fullname.
    """
    result = _call(base_url, token, "core_enrol_get_users_courses", userid=userid)
    return result if isinstance(result, list) else []


def get_assignments(
    base_url: str, token: str, course_ids: list[int]
) -> Iterator[dict]:
    """
    Génère les assignments Moodle avec deadline pour les cours donnés.

    Chaque dict yielded:
      - title           : nom de l'assignment
      - course_shortname: shortname du cours (ex: "235-203-LI 00")
      - course_fullname : nom complet du cours
      - due_date        : Unix timestamp UTC (les duedate=0 sont ignorés)
      - intro           : texte de l'énoncé nettoyé (max 300 chars)
    """
    if not course_ids:
        return

    params = {f"courseids[{i}]": cid for i, cid in enumerate(course_ids)}
    result = _call(base_url, token, "mod_assign_get_assignments", **params)

    for course in result.get("courses", []):
        for asgn in course.get("assignments", []):
            duedate = asgn.get("duedate", 0)
            if not duedate:
                continue

            intro_html = asgn.get("intro", "")
            try:
                from bs4 import BeautifulSoup
                intro = BeautifulSoup(intro_html, "html.parser").get_text(separator=" ").strip()
            except Exception:
                intro = re.sub(r"<[^>]+>", " ", intro_html).strip()
            intro = " ".join(intro.split())[:300]

            yield {
                "title": asgn["name"],
                "course_shortname": course.get("shortname", ""),
                "course_fullname": course.get("fullname", ""),
                "due_date": duedate,
                "intro": intro,
            }


def _scrape_with_token(base_url: str, token: str) -> list[dict]:
    """Scrape les assignments Moodle avec un token déjà obtenu."""
    userid = get_userid(base_url, token)
    courses = get_courses(base_url, token, userid)
    if not courses:
        return []
    course_ids = [int(c["id"]) for c in courses]
    return list(get_assignments(base_url, token, course_ids))


# ── Points d'entrée ───────────────────────────────────────────────────────────

def scrape_moodle_with_token(base_url: str, token: str) -> list[dict]:
    """
    Scrape Moodle avec un token wstoken direct (bypass SSO).
    Le token peut être obtenu depuis : Profil Moodle → Préférences → Clés de sécurité.
    """
    return _scrape_with_token(base_url, token)


def scrape_moodle(base_url: str, username: str, password: str) -> list[dict]:
    """
    Scrape via auth native REST (instances sans SSO).
    Lève MoodleAuthError si SSO requis — utiliser scrape_moodle_with_page() dans ce cas.
    """
    token = get_token(base_url, username, password)
    return _scrape_with_token(base_url, token)


def scrape_moodle_with_page(
    page: "Page",
    base_url: str,
    ms_username: str,
    ms_password: str,
) -> list[dict]:
    """
    Scrape Moodle via SSO Microsoft avec Playwright (contexte existant).
    Pour utiliser la session persistante, utiliser scrape_moodle_with_browser() à la place.
    """
    token = get_token_via_playwright(page, base_url, ms_username, ms_password)
    return _scrape_with_token(base_url, token)


def scrape_moodle_with_browser(
    browser,
    base_url: str,
    ms_username: str,
    ms_password: str,
    session_path: str | None = None,
) -> list[dict]:
    """
    Scrape Moodle via SSO Microsoft avec un nouveau contexte Playwright.
    Charge et sauvegarde la session persistante si session_path est fourni.

    Raises:
        MoodleMFARequired si Microsoft demande le MFA sans session valide.
    """
    token, _ = get_token_via_playwright_with_session(
        browser, base_url, ms_username, ms_password,
        session_path=session_path, save_session=True,
    )
    return _scrape_with_token(base_url, token)
