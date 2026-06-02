"""
Chargement de configuration et registre d'URLs Omnivox.
Responsabilité unique : construire la Config Playwright depuis les settings utilisateur
et maintenir le registre MODULES (URLs par module, mis à jour selon le cégep actif).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

from .omnivox_models import Config, DEFAULT_TIMEOUT_MS

# ── URL globals — valeurs par défaut Limoilou, mises à jour par load_config() ─

_SLUG         = os.getenv("OMNIVOX_SLUG", "climoilou")
OMNIVOX_URL   = f"https://{_SLUG}.omnivox.ca/"
OMNIVOX_BASE  = f"https://{_SLUG}.omnivox.ca"
LEA_BASE      = f"https://{_SLUG}-lea.omnivox.ca"
ESTD_BASE     = f"https://{_SLUG}-estd.omnivox.ca"
MIO_BASE      = f"https://{_SLUG}.omnivox.ca/WebApplication/Module.MIOE"
MOODLE_BASE   = f"https://{_SLUG}.moodle.decclic.qc.ca"

# ── Registre de navigation — routes fixes ─────────────────────────────────────
# Dict mutable mis à jour in-place par load_config() — les importeurs gardent
# toujours une référence au même objet, jamais rebindé.
MODULES: dict[str, dict] = {
    "home": {
        "url":      f"{OMNIVOX_BASE}/intr/",
        "marker":   "/intr/",
        "selector": None,
    },
    "mio": {
        "url":      f"{OMNIVOX_BASE}/intr/Module/ServicesExterne/RedirigeMio.ashx",
        "marker":   "Module.MIOE",
        "selector": None,
    },
    "lea": {
        "url":      f"{LEA_BASE}/cvir/",
        "marker":   "climoilou-lea.omnivox.ca",
        "selector": "body",
    },
    "lea_travaux": {
        "url":      f"{LEA_BASE}/cvir/dtrv/SommaireTravauxEtu.aspx",
        "marker":   "SommaireTravauxEtu",
        "selector": "body",
    },
    "lea_documents": {
        "url":      f"{LEA_BASE}/cvir/ddle/SommaireDocuments.aspx",
        "marker":   "SommaireDocuments",
        "selector": "body",
    },
    "lea_notes": {
        "url":      f"{LEA_BASE}/cvir/note/ListeEvalCVIR.ovx?ModeAff=SOMMAIREEVAL",
        "marker":   "ListeEvalCVIR",
        "selector": "body",
    },
    "lea_calendrier": {
        "url":      f"{LEA_BASE}/cvir/clre/Default.aspx?cal=somm",
        "marker":   "clre",
        "selector": "body",
    },
    "cheminement": {
        "url":      f"{ESTD_BASE}/estd/grch/Main.ovx",
        "marker":   "grch",
        "selector": "body",
    },
    "examens": {
        "url":      f"{ESTD_BASE}/estd/hrex/Examen.ovx",
        "marker":   "hrex",
        "selector": "body",
    },
    "documents_officiels": {
        "url":      f"{ESTD_BASE}/estd/dinf/ListeDocumentsDistribues.ovx",
        "marker":   "ListeDocumentsDistribues",
        "selector": "body",
    },
    "actualites": {
        "url":      (f"{OMNIVOX_BASE}/intr/UI/WebParts/SiteIntra_Actualites/"
                     f"WebPart_2_Liste.aspx?C=LIM&E=P&L=FRA&FSA=true"),
        "marker":   "Actualites",
        "selector": "body",
    },
}


def load_config() -> Config:
    from omnisync import paths
    from omnisync.config import get_password, load_settings

    settings = load_settings()
    matricule = (settings.da or "").strip()
    if not matricule:
        raise RuntimeError("DA Omnivox manquant. Lancez: run.bat init")

    password = get_password(matricule)
    if not password:
        env_path = paths.app_data_dir() / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            password = os.getenv("PASSWORD")
        if not password:
            raise RuntimeError(
                "Mot de passe Omnivox introuvable. Relancez run.bat init "
                "(keyring) ou definissez PASSWORD dans %LOCALAPPDATA%\\OmniSync\\.env"
            )

    slug = settings.cegep_slug.strip().lower()
    inst = settings.institution_code.strip().upper()
    lang = settings.lang.strip().upper()

    headless_env = os.environ.get("HEADLESS", "").strip().lower()
    if headless_env in {"1", "true", "yes"}:
        headless = True
    elif headless_env in {"0", "false", "no"}:
        headless = False
    else:
        headless = settings.headless

    gcal_cred = os.environ.get("OMNISYNC_GOOGLE_CREDENTIALS")
    if not gcal_cred and paths.credentials_path().exists():
        gcal_cred = str(paths.credentials_path())

    # Mettre à jour les globals et le registre MODULES selon le cégep configuré
    global OMNIVOX_URL, OMNIVOX_BASE, LEA_BASE, ESTD_BASE, MIO_BASE, MOODLE_BASE
    OMNIVOX_URL  = f"https://{slug}.omnivox.ca/"
    OMNIVOX_BASE = f"https://{slug}.omnivox.ca"
    LEA_BASE     = f"https://{slug}-lea.omnivox.ca"
    ESTD_BASE    = f"https://{slug}-estd.omnivox.ca"
    MIO_BASE     = f"https://{slug}.omnivox.ca/WebApplication/Module.MIOE"
    MOODLE_BASE  = f"https://{slug}.moodle.decclic.qc.ca"
    MODULES.update({
        "home":              {"url": f"{OMNIVOX_BASE}/intr/",            "marker": "/intr/",              "selector": None},
        "mio":               {"url": f"{OMNIVOX_BASE}/intr/Module/ServicesExterne/RedirigeMio.ashx", "marker": "Module.MIOE", "selector": None},
        "lea":               {"url": f"{LEA_BASE}/cvir/",                "marker": f"{slug}-lea",         "selector": "body"},
        "lea_travaux":       {"url": f"{LEA_BASE}/cvir/dtrv/SommaireTravauxEtu.aspx", "marker": "SommaireTravauxEtu", "selector": "body"},
        "lea_documents":     {"url": f"{LEA_BASE}/cvir/ddle/SommaireDocuments.aspx",  "marker": "SommaireDocuments",  "selector": "body"},
        "lea_notes":         {"url": f"{LEA_BASE}/cvir/note/ListeEvalCVIR.ovx?ModeAff=SOMMAIREEVAL", "marker": "ListeEvalCVIR", "selector": "body"},
        "lea_calendrier":    {"url": f"{LEA_BASE}/cvir/clre/Default.aspx?cal=somm", "marker": "clre",     "selector": "body"},
        "cheminement":       {"url": f"{ESTD_BASE}/estd/grch/Main.ovx",   "marker": "grch",               "selector": "body"},
        "examens":           {"url": f"{ESTD_BASE}/estd/hrex/Examen.ovx", "marker": "hrex",               "selector": "body"},
        "documents_officiels": {"url": f"{ESTD_BASE}/estd/dinf/ListeDocumentsDistribues.ovx", "marker": "ListeDocumentsDistribues", "selector": "body"},
        "actualites":        {"url": f"{OMNIVOX_BASE}/intr/UI/WebParts/SiteIntra_Actualites/WebPart_2_Liste.aspx?C={inst}&E=P&L={lang}&FSA=true", "marker": "Actualites", "selector": "body"},
    })

    return Config(
        matricule=matricule,
        password=password,
        base_dir=paths.app_data_dir() / "downloads",
        slug=slug,
        institution_code=inst,
        lang=lang,
        term=os.getenv("OMNIVOX_TERM") or settings.term or "",
        timeout_ms=int(os.getenv("TIMEOUT_MS", str(DEFAULT_TIMEOUT_MS))),
        headless=headless,
        gcal_credentials=Path(gcal_cred) if gcal_cred else None,
        gcal_calendar_id=settings.calendar_id,
        work_days=[],
        semester_start=None,
        semester_end=None,
        exam_keywords=[],
        assignment_keywords=[],
        exclude_keywords=[],
    )
