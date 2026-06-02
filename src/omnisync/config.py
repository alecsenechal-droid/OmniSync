from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import getpass
import os
import tomllib

from . import paths

try:
    import keyring
except Exception:  # pragma: no cover
    keyring = None

SERVICE_NAME = "OmniSync Omnivox"
MOODLE_SERVICE_NAME = "OmniSync Moodle"
MOODLE_TOKEN_SERVICE_NAME = "OmniSync Moodle Token"


@dataclass
class Settings:
    cegep_slug: str = "climoilou"
    institution_code: str = "CLI"
    lang: str = "FRA"
    headless: bool = True
    calendar_id: str = "auto"   # "auto" = créer/trouver le calendrier "OmniSync" automatiquement
    sync_time: str = "05:00"
    sync_assignments: bool = True
    sync_exams: bool = True
    sync_schedule: bool = True
    sync_mio: bool = False
    sync_moodle: bool = True
    sync_actualites: bool = True
    sync_documents: bool = True
    sync_courses: bool = True   # import des cours récurrents via RRULE
    da: str | None = None
    term: str = ""
    moodle_url: str = ""
    moodle_ms_email: str = ""   # email Microsoft pour SSO (ex: 2534700@cegeplimoilou.ca)
    moodle_token: str = ""      # token API direct (optionnel, bypass SSO — voir profil Moodle → Clés de sécurité)
    legacy_project_path: str | None = None
    notify_email: str = ""      # email de destination des alertes d'échec
    notify_smtp_user: str = ""  # compte Gmail expéditeur (ex: omnisync@gmail.com)
    actualites_keywords: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.actualites_keywords is None:
            self.actualites_keywords = []


def _bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "oui"}
    return default


def load_settings() -> Settings:
    path = paths.config_path()
    if not path.exists():
        return Settings()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    omnivox = data.get("omnivox", {})
    calendar = data.get("calendar", {})
    scheduler = data.get("scheduler", {})
    features = data.get("features", {})
    moodle = data.get("moodle", {})
    # Token Moodle : keyring OS en priorité, TOML en fallback (migration transparente)
    _da_key = omnivox.get("da") or "omnisync"
    _moodle_token = get_moodle_token(_da_key) or moodle.get("token", "")
    raw_keywords = features.get("actualites_keywords", [])
    keywords = [str(k) for k in raw_keywords] if isinstance(raw_keywords, list) else []
    return Settings(
        cegep_slug=omnivox.get("cegep_slug", "climoilou"),
        institution_code=omnivox.get("institution_code", "CLI"),
        lang=omnivox.get("lang", "FRA"),
        headless=_bool(omnivox.get("headless"), True),
        da=omnivox.get("da"),
        term=omnivox.get("term", ""),
        calendar_id=calendar.get("calendar_id", "auto"),
        sync_time=scheduler.get("sync_time", "05:00"),
        sync_assignments=_bool(features.get("sync_assignments"), True),
        sync_exams=_bool(features.get("sync_exams"), True),
        sync_schedule=_bool(features.get("sync_schedule"), True),
        sync_mio=_bool(features.get("sync_mio"), False),
        sync_moodle=_bool(features.get("sync_moodle"), True),
        sync_actualites=_bool(features.get("sync_actualites"), True),
        sync_documents=_bool(features.get("sync_documents"), True),
        sync_courses=_bool(features.get("sync_courses"), True),
        actualites_keywords=keywords,
        moodle_url=moodle.get("url", ""),
        moodle_ms_email=moodle.get("ms_email", ""),
        moodle_token=_moodle_token,
        legacy_project_path=data.get("development", {}).get("legacy_project_path"),
        notify_email=data.get("notify", {}).get("email", ""),
        notify_smtp_user=data.get("notify", {}).get("smtp_user", ""),
    )


def save_settings(settings: Settings) -> Path:
    paths.ensure_runtime_dirs()
    # Token Moodle : stocker dans le keyring OS.
    # Si keyring indisponible, conserver en TOML comme fallback (dégradé sécurisé).
    _toml_token = ""
    if settings.moodle_token:
        if not store_moodle_token(settings.moodle_token, settings.da or "omnisync"):
            _toml_token = settings.moodle_token  # keyring indisponible — fallback TOML
    # Sérialiser la liste de mots-clés actualités en TOML array
    _kw = settings.actualites_keywords or []
    _kw_toml = "[" + ", ".join(f'"{k}"' for k in _kw) + "]"
    content = f'''[omnivox]
cegep_slug = "{settings.cegep_slug}"
institution_code = "{settings.institution_code}"
lang = "{settings.lang}"
headless = {str(settings.headless).lower()}
da = "{settings.da or ''}"
term = "{settings.term or ''}"

[calendar]
calendar_id = "{settings.calendar_id}"

[scheduler]
sync_time = "{settings.sync_time}"

[features]
sync_assignments = {str(settings.sync_assignments).lower()}
sync_exams = {str(settings.sync_exams).lower()}
sync_schedule = {str(settings.sync_schedule).lower()}
sync_mio = {str(settings.sync_mio).lower()}
sync_moodle = {str(settings.sync_moodle).lower()}
sync_actualites = {str(settings.sync_actualites).lower()}
sync_documents = {str(settings.sync_documents).lower()}
sync_courses = {str(settings.sync_courses).lower()}
actualites_keywords = {_kw_toml}

[moodle]
url = "{settings.moodle_url or ''}"
ms_email = "{settings.moodle_ms_email or ''}"
token = "{_toml_token}"

[development]
legacy_project_path = "{settings.legacy_project_path or ''}"

[notify]
email = "{settings.notify_email}"
smtp_user = "{settings.notify_smtp_user}"
'''
    paths.config_path().write_text(content, encoding="utf-8")
    return paths.config_path()


def store_password(da: str, password: str) -> bool:
    if keyring is None:
        return False
    keyring.set_password(SERVICE_NAME, da, password)
    return True


def get_password(da: str) -> str | None:
    if keyring is None:
        return None
    return keyring.get_password(SERVICE_NAME, da)


def store_moodle_password(da: str, password: str) -> bool:
    """Stocke un mot de passe Moodle séparé dans le keyring OS."""
    if keyring is None:
        return False
    keyring.set_password(MOODLE_SERVICE_NAME, da, password)
    return True


def store_moodle_token(token: str, da: str = "omnisync") -> bool:
    """Stocke le token API Moodle dans le keyring OS (jamais en clair sur disque)."""
    if keyring is None:
        return False
    keyring.set_password(MOODLE_TOKEN_SERVICE_NAME, da or "omnisync", token)
    return True


def get_moodle_token(da: str = "omnisync") -> str:
    """Retourne le token API Moodle depuis le keyring OS."""
    if keyring is None:
        return ""
    return keyring.get_password(MOODLE_TOKEN_SERVICE_NAME, da or "omnisync") or ""


def get_moodle_password(da: str) -> str | None:
    """
    Retourne le mot de passe Moodle pour ce DA.

    Priorité :
      1. Variable d'environnement OMNISYNC_MOODLE_PASSWORD
      2. Keyring "OmniSync Moodle" (défini via run.bat init-moodle ou à la main)
      3. Keyring Omnivox (même mot de passe, cas le plus commun)
    """
    env = os.environ.get("OMNISYNC_MOODLE_PASSWORD", "").strip()
    if env:
        return env
    if keyring is not None:
        specific = keyring.get_password(MOODLE_SERVICE_NAME, da)
        if specific:
            return specific
        return keyring.get_password(SERVICE_NAME, da)
    return None


KNOWN_CEGEPS: dict[str, tuple[str, str]] = {
    # slug → (institution_code, nom)
    "climoilou":    ("CLI", "Cégep Limoilou"),
    "csfoy":        ("SFO", "Cégep de Sainte-Foy"),
    "cegepgarneau": ("FXG", "Cégep Garneau"),
}


def interactive_init() -> Settings:
    from .ui import ok, err, warn, info, bold, section, header

    paths.ensure_runtime_dirs()
    current = load_settings()

    header("OmniSync -- Configuration")
    print("OmniSync lit ton horaire Omnivox et l'ajoute dans Google Calendar.")
    print("Tes donnees restent sur ton ordinateur :")
    print(f"  {paths.app_data_dir()}\n")

    # ── Boucle saisie : recommence étapes 1+2 si l'utilisateur refuse ────────────
    while True:
        section("Etape 1 -- Ton cegep")
        print("Cegeps supportes :")
        for slug, (code, nom) in KNOWN_CEGEPS.items():
            print(f"  {slug:<18} {nom}")
        print()

        cegep = input(f"Slug de ton cegep [{current.cegep_slug}]: ").strip() or current.cegep_slug
        if cegep not in KNOWN_CEGEPS:
            print(warn(f"Slug inconnu : '{cegep}'"))
            print("  Slugs valides :")
            for s, (_, nom) in KNOWN_CEGEPS.items():
                print(f"    {s:<18} {nom}")
            print()
            _slug_ok = input("Continuer quand meme avec ce slug ? [o/N]: ").strip().lower()
            if _slug_ok not in {"o", "oui", "y", "yes"}:
                print("Correction du slug...")
                continue
        known_code = KNOWN_CEGEPS.get(cegep, (current.institution_code, ""))[0]
        inst = input(f"Code institution [{known_code}]: ").strip().upper() or known_code

        section("Etape 2 -- Ton compte Omnivox")
        print("Ton mot de passe sera stocke dans Credential Manager Windows.")
        print("Il ne quitte jamais ton ordinateur.\n")

        da = input("Ton DA / matricule (ex: 2534700): ").strip()
        password = getpass.getpass("Ton mot de passe Omnivox: ")

        print("\nSession active (ex: 2026-Automne). Laisse vide pour auto-detecter.")
        term_default = current.term or ""
        term = input(f"Session [{term_default or 'auto'}]: ").strip() or term_default

        sync_time = input(f"\nHeure de sync quotidienne [{current.sync_time}]: ").strip() or current.sync_time

        # ── Résumé avant toute sauvegarde ─────────────────────────────────────
        section("Confirmation")
        cegep_name = KNOWN_CEGEPS.get(cegep, ("", cegep))[1] or cegep
        google_status = "connecte (token existant)" if paths.token_path().exists() else "non connecte (etape suivante)"
        print(f"  Cegep      : {cegep_name}  ({cegep})")
        print(f"  Code inst. : {inst}")
        print(f"  DA         : {da}")
        print(f"  Session    : {term or 'auto-detectee'}")
        print(f"  Sync       : chaque jour a {sync_time}")
        print(f"  Config     : {paths.config_path()}")
        print(f"  Google     : {google_status}")
        print()
        _confirm = input("Confirmer cette configuration ? [O/n]: ").strip().lower()
        if _confirm in {"", "o", "oui", "y", "yes"}:
            break
        print("\nReprenons depuis le debut (Ctrl+C pour annuler)...\n")

    settings = Settings(
        cegep_slug=cegep,
        institution_code=inst,
        lang=current.lang,
        headless=current.headless,
        da=da,
        term=term,
        calendar_id="auto",
        sync_time=sync_time,
        actualites_keywords=current.actualites_keywords,
        sync_courses=current.sync_courses,
    )
    save_settings(settings)

    if password:
        stored = store_password(da, password)
        if stored:
            print(ok("Mot de passe enregistre dans Credential Manager Windows."))
        else:
            print(warn("Keyring indisponible -- mot de passe non stocke."))
            print("  Relance run.bat init pour reessayer.")
    print(ok("Configuration enregistree."))

    section("Etape 3 -- Connexion Google Calendar")
    print("OmniSync va creer un calendrier 'OmniSync' dans ton Google Calendar.\n")

    if not paths.credentials_path().exists():
        print(warn("credentials.json introuvable.\n"))
        print("Pour l'obtenir (2 minutes) :")
        print("  1. Va sur : https://console.cloud.google.com/")
        print("  2. Cree un projet  (nom : OmniSync)")
        print("  3. Active l'API  Google Calendar API")
        print("  4. Cree des identifiants OAuth 2.0  (type : Application de bureau)")
        print("  5. Telecharge le JSON --> renomme-le credentials.json")
        print(f"  6. Deplace-le ici : {paths.credentials_path()}\n")
        print("  Guide complet : docs/INSTALLATION.md\n")
        try:
            input("  Appuie sur Entree quand credentials.json est en place (Ctrl+C pour plus tard)...")
        except KeyboardInterrupt:
            print("\n  Lance plus tard : run.bat auth-google")
        print()

    connect = input("Connecter Google Calendar maintenant? [O/n]: ").strip().lower()
    if connect in {"", "o", "oui", "y", "yes"}:
        from .calendar import connect_google_calendar
        try:
            cal_id = connect_google_calendar()
            print(ok("Google Calendar connecte -- calendrier OmniSync cree."))
        except RuntimeError as exc:
            print(err(f"Connexion Google echouee : {exc}"))
            print(info("Lance quand credentials.json est pret : run.bat auth-google"))

    section("Etape 4 -- Sync automatique")
    schedule = input(f"Activer la sync automatique a {sync_time} chaque jour? [O/n]: ").strip().lower()
    if schedule in {"", "o", "oui", "y", "yes"}:
        from .scheduler import install as scheduler_install
        res = scheduler_install(sync_time)
        if res.ok:
            print(ok(res.message))
        else:
            print(warn(f"Sync automatique non installee : {res.message}"))
            print("  Lance manuellement : run.bat scheduler install")

    section("Etape 5 -- Moodle (optionnel)")
    print("Certains profs publient les deadlines sur Moodle.")
    print("Active, OmniSync les ajoute aussi dans ton calendrier.\n")
    moodle = input("Activer Moodle? [o/N]: ").strip().lower()
    if moodle in {"o", "oui", "y", "yes"}:
        moodle_url_default = current.moodle_url or ""
        moodle_url = input(f"URL Moodle [{moodle_url_default or 'ex: https://climoilou.moodle.decclic.qc.ca'}]: ").strip() or moodle_url_default
        moodle_email_default = current.moodle_ms_email or ""
        moodle_email = input(f"Ton email Microsoft [{moodle_email_default}]: ").strip() or moodle_email_default
        settings.sync_moodle = True
        settings.moodle_url = moodle_url
        settings.moodle_ms_email = moodle_email
        save_settings(settings)
        print(ok("Moodle configure."))
        print(info("Lance maintenant : run.bat init-moodle"))
        print("  Un browser va s'ouvrir --> login Microsoft + MFA --> token sauvegarde automatiquement.")
    else:
        settings.sync_moodle = False
        save_settings(settings)

    print("\n" + "-" * 52)
    print(bold("  Configuration terminee !") + " Prochaines etapes :")
    print()
    print("  run.bat run --calendar-dry-run    <-- apercu sans modifier ton calendrier")
    print("  run.bat run                       <-- synchronisation complete")
    if settings.sync_moodle and not settings.moodle_token:
        print("  run.bat init-moodle               <-- connexion Moodle (une seule fois)")
    print()

    return settings
