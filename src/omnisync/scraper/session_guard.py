"""
Session Guard — détecte les redirects login silencieux et sessions invalides Omnivox.

Omnivox WebForms retourne HTTP 200 même quand la session est expirée.
Un redirect silencieux scrappe une page de login vide → 0 résultats → DB se vide.
Ce module détecte ces cas AVANT que le scraping commence.

Log format:
    [SESSION_GUARD][OK]   url=...
    [SESSION_GUARD][WARN] reason=wrong_domain url=...
    [SESSION_GUARD][FAIL] reason=login_form_in_dom signals=[...] url=...
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

# ── Signaux de session invalide ───────────────────────────────────────────────

# Fragments d'URL indiquant une page de login / logout
_LOGIN_URL_SIGNALS = (
    "islogout=1",
    "/login",
    "login.aspx",
    "authenticate.aspx",
    "error_0028",
)

# Sélecteurs DOM typiques d'une page login Omnivox
_LOGIN_DOM_SELECTORS = (
    "input[name='DA']",
    "input[name='NPA']",
    "input[id*='txtDA']",
    "input[id*='txtPassword']",
    "form[action*='Login']",
    "form[action*='Authenticate']",
)

# Textes typiques des pages d'erreur / déconnexion
_ERROR_TEXTS = (
    "session a expiré",
    "session expired",
    "vous avez été déconnecté",
    "vous n'êtes pas autorisé",
    "accès refusé",
    "please log in",
    "error_0028",
    "connexion requise",
)

# Textes qui CONFIRMENT une session active (réduisent les faux positifs)
_VALID_TEXTS = (
    "bonjour,",
    "bienvenue",
    "mon portail",
    "tableau de bord",
    "mes cours",
    "léa",
    "omnivox",
)


@dataclass
class GuardResult:
    valid: bool
    reason: str
    severity: str  # "ok" | "warn" | "fail"
    url: str
    signals: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        tag = f"[SESSION_GUARD][{self.severity.upper()}]"
        if self.valid:
            return f"{tag} url={self.url[:80]}"
        return (
            f"{tag} reason={self.reason} "
            f"signals={self.signals} "
            f"url={self.url[:80]}"
        )

    def log(self) -> None:
        print(str(self))


def check(page: "Page", expected_domain: str = "") -> GuardResult:
    """
    Vérifie si la session Omnivox est valide sur la page courante.

    Args:
        page: Page Playwright active.
        expected_domain: Fragment attendu dans l'URL (ex: 'climoilou-lea', 'estd').

    Returns:
        GuardResult — valid=True si session OK, False sinon.
    """
    url = page.url
    url_lower = url.lower()
    signals: list[str] = []

    # ── Signal 1 : URL de login ───────────────────────────────────────────────
    for sig in _LOGIN_URL_SIGNALS:
        if sig in url_lower:
            signals.append(f"url:{sig}")

    # ── Signal 2 : Formulaire de login dans le DOM ────────────────────────────
    try:
        for selector in _LOGIN_DOM_SELECTORS:
            try:
                if page.locator(selector).count():
                    signals.append(f"dom:{selector}")
                    break
            except Exception:
                pass
    except Exception:
        signals.append("dom:check_failed")

    # ── Signal 3 : Texte d'erreur / texte de confirmation ─────────────────────
    body_lower = ""
    try:
        body_lower = page.locator("body").inner_text(timeout=3_000).lower()
        for txt in _ERROR_TEXTS:
            if txt in body_lower:
                signals.append(f"text:{txt[:25]}")
        confirmed = [txt for txt in _VALID_TEXTS if txt in body_lower]
        if confirmed:
            signals.append(f"confirmed:{confirmed[0]}")
    except Exception:
        signals.append("body:unavailable")

    # ── Signal 4 : Domaine attendu absent ────────────────────────────────────
    if expected_domain and expected_domain.lower() not in url_lower:
        signals.append(f"domain:expected={expected_domain}")

    # ── Signal 5 : Page trop petite ──────────────────────────────────────────
    try:
        html_len = len(page.content())
        if html_len < 500:
            signals.append(f"html:too_small={html_len}")
    except Exception:
        pass

    # ── Décision ─────────────────────────────────────────────────────────────
    has_confirmed = any(s.startswith("confirmed:") for s in signals)
    login_signals = [s for s in signals
                     if s.startswith("url:") or s.startswith("dom:")]
    error_signals = [s for s in signals if s.startswith("text:")]
    domain_signals = [s for s in signals if s.startswith("domain:")]
    size_signals = [s for s in signals if s.startswith("html:")]

    # Redirect login explicite
    if login_signals:
        return GuardResult(
            valid=False, reason="login_detected",
            severity="fail", url=url, signals=signals,
        )

    # Texte d'erreur sans texte de confirmation
    if error_signals and not has_confirmed:
        return GuardResult(
            valid=False, reason="error_text_no_confirmation",
            severity="fail", url=url, signals=signals,
        )

    # Mauvais domaine
    if domain_signals:
        return GuardResult(
            valid=False, reason="wrong_domain",
            severity="warn", url=url, signals=signals,
        )

    # Page trop petite
    if size_signals:
        return GuardResult(
            valid=False, reason="page_too_small",
            severity="warn", url=url, signals=signals,
        )

    return GuardResult(valid=True, reason="ok", severity="ok",
                       url=url, signals=signals)


def assert_valid(page: "Page", module: str, expected_domain: str = "") -> GuardResult:
    """
    Vérifie la session et lève RuntimeError si invalide (severity=fail).
    Pour severity=warn, log seulement sans bloquer.

    Usage: appelez avant chaque module de scraping.
    """
    result = check(page, expected_domain)
    result.log()

    if not result.valid and result.severity == "fail":
        raise RuntimeError(
            f"[SESSION_GUARD] Session invalide avant scraping module={module}. "
            f"reason={result.reason} url={result.url}"
        )
    return result
