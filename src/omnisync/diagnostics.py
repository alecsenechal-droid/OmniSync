from __future__ import annotations

import importlib.util
import sys

from . import paths, ui
from .config import load_settings, get_password, get_moodle_token, KNOWN_CEGEPS


def doctor() -> int:
    paths.ensure_runtime_dirs()
    settings = load_settings()
    checks: list[tuple[str, bool, str]] = []

    checks.append(("Python >= 3.10",             sys.version_info >= (3, 10),                                            sys.version.split()[0]))
    checks.append(("Config locale",               paths.config_path().exists(),                                           str(paths.config_path())))
    checks.append(("Dossier runtime",             paths.app_data_dir().exists(),                                          str(paths.app_data_dir())))
    checks.append(("Playwright installe",          importlib.util.find_spec("playwright") is not None,                    "module playwright"))
    checks.append(("Google API installee",         importlib.util.find_spec("googleapiclient") is not None,               "module googleapiclient"))
    checks.append(("Keyring installe",             importlib.util.find_spec("keyring") is not None,                       "module keyring"))
    checks.append(("Moteur Omnivox",               importlib.util.find_spec("omnisync.scraper.omnivox_engine") is not None,"omnivox_engine"))
    checks.append(("Mot de passe Omnivox stocke",  bool(settings.da and get_password(settings.da)),                       "Windows Credential Manager"))
    checks.append(("credentials.json Google",      paths.credentials_path().exists(),                                     str(paths.credentials_path())))
    checks.append(("token Google",                 paths.token_path().exists(),                                           str(paths.token_path())))

    # ── Checks config multi-cégep (statiques, zéro réseau) ───────────────────
    slug = settings.cegep_slug or ""
    cegep_ok = slug in KNOWN_CEGEPS
    checks.append((
        "Cegep reconnu",
        cegep_ok,
        KNOWN_CEGEPS[slug][1] if cegep_ok else f"slug inconnu : '{slug}' (valides: {', '.join(KNOWN_CEGEPS)})",
    ))

    if cegep_ok:
        expected_code = KNOWN_CEGEPS[slug][0]
        if settings.institution_code == expected_code:
            inst_detail = f"{settings.institution_code}"
        else:
            inst_detail = f"[!] {settings.institution_code} != {expected_code} attendu pour {slug} — corrige via run.bat init"
    else:
        inst_detail = f"{settings.institution_code} (cegep non reconnu, non verifie)"
    checks.append(("Code institution", True, inst_detail))

    if settings.sync_moodle and not settings.moodle_url:
        moodle_url_detail = "[!] sync_moodle actif mais moodle_url vide — run.bat init"
    elif settings.sync_moodle:
        moodle_url_detail = settings.moodle_url
    else:
        moodle_url_detail = "sync_moodle desactive"
    checks.append(("Moodle URL configuree", True, moodle_url_detail))

    if settings.sync_moodle:
        _tok = bool(get_moodle_token(settings.da or "omnisync") or settings.moodle_token)
        checks.append(("Token Moodle", _tok, "keyring OmniSync Moodle Token"))
    if settings.sync_time:
        from .scheduler import status as scheduler_status
        try:
            sched = scheduler_status()
            detail = f"tache Windows a {settings.sync_time}" if sched.ok else "tache Windows absente"
            checks.append(("Sync automatique planifiee", sched.ok, detail))
        except Exception:
            checks.append(("Sync automatique planifiee", False, "impossible de verifier"))

    fixes: dict[str, str] = {
        "Config locale":              "Lance : run.bat init",
        "Mot de passe Omnivox stocke":"Lance : run.bat init  (re-entre ton DA et mot de passe)",
        "credentials.json Google":    (
            "Telecharge depuis : https://console.cloud.google.com/apis/credentials\n"
            f"         Place le fichier ici : {paths.credentials_path()}"
        ),
        "token Google":               "Lance : run.bat auth-google",
        "Playwright installe":        "Lance : pip install playwright  puis : python -m playwright install chromium",
        "Google API installee":       "Lance : pip install google-api-python-client",
        "Keyring installe":           "Lance : pip install keyring",
        "Token Moodle":               "Lance : run.bat token-moodle  ou  run.bat init-moodle",
        "Sync automatique planifiee": "Lance : run.bat scheduler install",
        "Cegep reconnu":              "Lance : run.bat init  (choisis un slug valide : climoilou, csfoy, cegepgarneau)",
    }

    ui.header("OmniSync doctor")
    failed = 0
    for name, ok_check, detail in checks:
        if ok_check:
            if detail.startswith("[!]"):
                print(f"  {ui.warn(name)}  {ui.dim(detail[3:].strip())}")
            else:
                print(f"  {ui.ok(name)}  {ui.dim(detail)}")
        else:
            failed += 1
            print(f"  {ui.err(name)}")
            if name in fixes:
                for i, line in enumerate(fixes[name].splitlines()):
                    prefix = "     --> " if i == 0 else "         "
                    print(f"{prefix}{line}")

    print(f"\n  {ui.dim('Config :')} {ui.dim(str(paths.config_path()))}")
    print(f"  {ui.dim('DB     :')} {ui.dim(str(paths.db_path()))}")
    print(f"  {ui.dim('Logs   :')} {ui.dim(str(paths.logs_dir()))}")
    print(f"  {ui.dim('Profil :')} {ui.dim(str(paths.browser_profile_dir()))}")

    print()
    if failed == 0:
        ui.success(f"Tout est OK ({len(checks)}/{len(checks)}) -- lance : run.bat run --calendar-dry-run")
    else:
        ui.error(f"{failed} point(s) a corriger avant de lancer run.bat run")
    print()

    return 0 if failed == 0 else 1
