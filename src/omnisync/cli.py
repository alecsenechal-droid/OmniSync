from __future__ import annotations

import argparse
import os
import sys

from .config import interactive_init, load_settings
from .diagnostics import doctor
from .scheduler import install as scheduler_install, remove as scheduler_remove, status as scheduler_status
from .sync import run_sync


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omnisync", description="Synchronise Omnivox vers Google Calendar.")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Assistant de configuration locale.")
    sub.add_parser("doctor", help="Verifie l'installation locale.")
    sub.add_parser("auth-google", help="Connecte Google Calendar (OAuth).")

    run = sub.add_parser("run", help="Lance une synchronisation.")
    run.add_argument("--dry-run", action="store_true", help="Affiche ce qui serait fait sans modifier Google Calendar.")
    run.add_argument("--scrape-only", action="store_true", help="Lit Omnivox et met SQLite a jour sans toucher Google Calendar.")
    run.add_argument("--calendar-dry-run", action="store_true", help="Scrape Omnivox reellement, mais n'ecrit rien dans Google Calendar.")
    run.add_argument("--include-past", action="store_true", help="Synchronise aussi les evenements deja passes (utile a la premiere installation).")
    run.add_argument("--verbose", action="store_true", help="Affiche tous les logs techniques (navigation, SSO, debug).")

    sched = sub.add_parser("scheduler", help="Gere la tache planifiee Windows.")
    sched_sub = sched.add_subparsers(dest="scheduler_command")
    sched_install = sched_sub.add_parser("install", help="Installe la tache quotidienne.")
    sched_install.add_argument("--time", default=None, help="Heure HH:MM, defaut config ou 05:00.")
    sched_sub.add_parser("status", help="Affiche l'etat de la tache.")
    sched_sub.add_parser("remove", help="Supprime la tache.")

    sub.add_parser("init-moodle", help="Authentification Moodle SSO (MFA) manuelle — sauvegarde la session.")
    sub.add_parser("token-moodle", help="Enregistre un token Moodle manuellement (Profil → Clés de sécurité).")
    sub.add_parser("notify-setup", help="Configure les alertes email (Gmail SMTP) en cas d'echec de sync.")
    sub.add_parser("paths", help="Affiche les chemins locaux utilises par OmniSync.")

    replay = sub.add_parser("replay", help="Inspecte les snapshots HTML des runs passes.")
    replay.add_argument("run", nargs="?", default=None,
                        help="Nom du run a inspecter (ex: 2026-05-27T05-00-01). Omis = liste tous les runs.")
    replay.add_argument("--history", action="store_true",
                        help="Affiche l'historique des validations.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        if sys.version_info < (3, 10):
            print(f"Erreur: Python 3.10+ requis. Version actuelle: {sys.version.split()[0]}")
            print("Telecharge Python depuis : https://www.python.org/downloads/")
            return 1
        try:
            interactive_init()
        except KeyboardInterrupt:
            print("\n\nConfiguration interrompue. Relance run.bat init pour continuer.")
            return 130
        return 0
    if args.command == "auth-google":
        from . import paths
        from .calendar import connect_google_calendar

        try:
            cal_id = connect_google_calendar()
            print(f"Google Calendar connecte. Calendrier: {cal_id}")
            print(f"Token enregistre dans {paths.token_path()}")
        except RuntimeError as exc:
            print(f"Erreur: {exc}")
            return 1
        return 0
    if args.command == "doctor":
        return doctor()
    if args.command == "run":
        if args.verbose:
            os.environ["OMNISYNC_VERBOSE"] = "1"
        if args.include_past:
            os.environ["OMNISYNC_SYNC_PAST_EVENTS"] = "1"
        return run_sync(
            dry_run=args.dry_run,
            scrape_only=args.scrape_only,
            calendar_dry_run=args.calendar_dry_run,
        )
    if args.command == "scheduler":
        settings = load_settings()
        if args.scheduler_command == "install":
            res = scheduler_install(args.time or settings.sync_time or "05:00")
        elif args.scheduler_command == "status":
            res = scheduler_status()
        elif args.scheduler_command == "remove":
            res = scheduler_remove()
        else:
            parser.error("scheduler demande: install, status ou remove")
        print(res.message)
        return 0 if res.ok else 1
    if args.command == "notify-setup":
        from .config import load_settings, save_settings
        from .notify import store_app_password, send_failure

        settings = load_settings()
        print("\nOmniSync — Configuration des alertes email")
        print("Prérequis : compte Gmail dédié (ex: omnisync@gmail.com) + App Password Google.")
        print("App Password : myaccount.google.com/apppasswords\n")
        to_email = input(f"Email de destination des alertes [{settings.notify_email or 'ton@email.com'}]: ").strip() or settings.notify_email
        smtp_user = input(f"Compte Gmail expéditeur [{settings.notify_smtp_user or 'omnisync@gmail.com'}]: ").strip() or settings.notify_smtp_user
        app_password = input("App Password Google (16 caractères, sans espaces) : ").strip()
        if not to_email or not smtp_user or not app_password:
            print("Champs manquants — configuration annulée.")
            return 1
        ok = store_app_password(smtp_user, app_password)
        if not ok:
            print("ATTENTION: keyring indisponible — App Password non sauvegardé.")
            return 1
        settings.notify_email = to_email
        settings.notify_smtp_user = smtp_user
        save_settings(settings)
        print("\nTest d'envoi...")
        sent = send_failure(to_email, smtp_user, "Test de configuration OmniSync", "Ceci est un test.")
        if sent:
            print(f"Email test envoyé à {to_email}. Vérifie ta boîte mail.")
        else:
            print("Échec de l'envoi. Vérifie l'App Password et que la vérification 2 étapes est activée.")
            return 1
        return 0
    if args.command == "init-moodle":
        from . import paths
        from .config import load_settings, get_moodle_password
        from .scraper import moodle_engine
        import base64, re, time

        settings = load_settings()
        if not settings.moodle_url:
            print("Erreur: moodle.url absent dans config.toml")
            return 1
        ms_email = settings.moodle_ms_email
        ms_password = get_moodle_password(settings.da) if settings.da else None
        if not ms_email or not ms_password:
            print("Erreur: moodle.ms_email ou mot de passe Moodle absent.")
            print("Configurez moodle.ms_email dans config.toml et le mot de passe via keyring.")
            return 1

        session_path = paths.moodle_session_path()
        print("\nOmniSync — init-moodle")
        print(f"Compte  : {ms_email}")
        print(f"Session : {session_path}")
        print()
        print("Un browser va s'ouvrir. Complétez le login Microsoft + MFA.")
        print("La session sera sauvegardée automatiquement après succès.")
        print("(Ctrl+C pour annuler)\n")

        moodle_domain = settings.moodle_url.replace("https://", "").replace("http://", "").split("/")[0]
        passport = str(int(time.time()))
        launch_url = (
            f"{settings.moodle_url.rstrip('/')}/admin/tool/mobile/launch.php"
            f"?service=moodle_mobile_app&passport={passport}&urlscheme=moodlemobile"
        )

        token_holder: list[str] = []
        import requests as _http

        def _extract_token(url_str: str) -> None:
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

        def _on_response(response) -> None:
            try:
                loc = response.headers.get("location", "")
                if "moodlemobile://" in loc:
                    _extract_token(loc)
            except Exception:
                pass

        def _on_requestfailed(request) -> None:
            if "moodlemobile://" in request.url:
                _extract_token(request.url)

        def _on_request(request) -> None:
            if "moodlemobile://" in request.url:
                _extract_token(request.url)

        from rebrowser_playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(locale="fr-CA")
            page = context.new_page()
            page.on("response", _on_response)
            page.on("requestfailed", _on_requestfailed)
            page.on("request", _on_request)

            # Intercepter la page KMSI avant son rendu — extraire SAMLResponse du HTML brut
            # et le POSTer directement vers l'ACS Moodle via requests (bypass rendu DOM blanc)
            _kmsi_saml_done = [False]

            def _handle_kmsi_route(route) -> None:
                if _kmsi_saml_done[0] or route.request.resource_type != "document":
                    try:
                        route.continue_()
                    except Exception:
                        pass
                    return
                _kmsi_saml_done[0] = True
                try:
                    resp = route.fetch()
                    html = resp.text()
                    saml_m = re.search(
                        r'<input[^>]*name=["\']SAMLResponse["\'][^>]*value=["\']([^"\']*)["\']', html
                    ) or re.search(
                        r'value=["\']([A-Za-z0-9+/=\r\n ]{50,})["\'][^>]*name=["\']SAMLResponse["\']',
                        html, re.DOTALL,
                    )
                    if saml_m:
                        saml_value = saml_m.group(1).replace("&amp;", "&")
                        action_m = re.search(r'<form[^>]*action=["\']([^"\']*)["\']', html)
                        acs_url = (
                            action_m.group(1).replace("&amp;", "&") if action_m
                            else f"{settings.moodle_url.rstrip('/')}/auth/saml2/acs.php"
                        )
                        relay_m = re.search(
                            r'<input[^>]*name=["\']RelayState["\'][^>]*value=["\']([^"\']*)["\']', html
                        )
                        post_data: dict = {"SAMLResponse": saml_value}
                        if relay_m:
                            post_data["RelayState"] = relay_m.group(1)
                        sess = _http.Session()
                        sess.headers["User-Agent"] = (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0.0.0 Safari/537.36"
                        )
                        r = sess.post(acs_url, data=post_data, allow_redirects=False, timeout=30)
                        for _ in range(10):
                            loc = r.headers.get("location", "")
                            if "moodlemobile://" in loc:
                                _extract_token(loc)
                                break
                            if r.is_redirect and loc:
                                abs_loc = loc if loc.startswith("http") else f"{settings.moodle_url.rstrip('/')}{loc}"
                                r = sess.get(abs_loc, allow_redirects=False, timeout=30)
                            else:
                                break
                        if not token_holder:
                            r2 = sess.get(launch_url, allow_redirects=False, timeout=30)
                            for _ in range(10):
                                loc = r2.headers.get("location", "")
                                if "moodlemobile://" in loc:
                                    _extract_token(loc)
                                    break
                                if r2.is_redirect and loc:
                                    abs_loc = loc if loc.startswith("http") else f"{settings.moodle_url.rstrip('/')}{loc}"
                                    r2 = sess.get(abs_loc, allow_redirects=False, timeout=30)
                                else:
                                    break
                except Exception:
                    pass
                try:
                    route.abort()
                except Exception:
                    pass

            page.route("**/kmsi**", _handle_kmsi_route)

            try:
                page.goto(launch_url, wait_until="domcontentloaded", timeout=45_000)
            except Exception:
                pass

            print("Browser ouvert. Complétez le login Microsoft + MFA...")
            print("(Attente jusqu'à 5 minutes)\n")

            deadline = time.time() + 300
            _launched = False

            while not token_holder and time.time() < deadline:
                current_url = ""
                try:
                    current_url = page.url
                except Exception:
                    pass
                # Quand le browser arrive sur Moodle (SAML complété par Microsoft),
                # on extrait les cookies Moodle et on appelle launch.php via Python requests
                if (
                    moodle_domain in current_url
                    and "microsoftonline" not in current_url
                    and "saml2" not in current_url
                    and not _launched
                ):
                    _launched = True
                    try:
                        moodle_cookies = {
                            c["name"]: c["value"]
                            for c in context.cookies()
                            if moodle_domain in c.get("domain", "")
                        }
                        sess = _http.Session()
                        sess.headers["User-Agent"] = (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0.0.0 Safari/537.36"
                        )
                        for name, value in moodle_cookies.items():
                            sess.cookies.set(name, value, domain=moodle_domain)
                        r = sess.get(launch_url, allow_redirects=False, timeout=30)
                        for _ in range(10):
                            loc = r.headers.get("location", "")
                            if "moodlemobile://" in loc:
                                _extract_token(loc)
                                break
                            if r.is_redirect and loc:
                                r = sess.get(loc, allow_redirects=False, timeout=30)
                            else:
                                break
                    except Exception:
                        pass
                time.sleep(0.5)

            if token_holder:
                context.storage_state(path=str(session_path))
                from .config import save_settings
                settings.moodle_token = token_holder[0]
                save_settings(settings)
                print(f"\n[OK] Token Moodle sauvegarde dans le gestionnaire d'identifiants OS (keyring).")
                print(f"     Les prochains runs utilisent ce token directement (aucun browser, aucun MFA).")
                print(f"     Si le token expire (changement de mot de passe), relancez init-moodle.")
            else:
                print("\n[TIMEOUT] Aucun token recu apres 5 minutes.")
                print("Verifiez que vous avez complete le MFA dans le browser.")

            browser.close()

        return 0

    if args.command == "token-moodle":
        from .config import load_settings, save_settings
        import webbrowser, base64 as _b64, re as _re
        settings = load_settings()
        print("\nOmniSync — token-moodle")
        if settings.moodle_url:
            token_url = f"{settings.moodle_url.rstrip('/')}/user/managetoken.php"
            print(f"Ouverture de votre Moodle dans le browser: {token_url}")
            webbrowser.open(token_url)
            print()
        print("Deux façons de coller le token:")
        print("  A) URL moodlemobile://  (Edge DevTools F12 → Network → launch.php → Request URL)")
        print("  B) Token 32 caractères  (Moodle → Profil → Clés de sécurité → Moodle mobile web service)")
        print()
        token = input("Collez ici: ").strip()
        if not token:
            print("Token vide — annulé.")
            return 1
        if "moodlemobile://token=" in token:
            m = _re.search(r"moodlemobile://token=([A-Za-z0-9+/=_-]+)", token)
            if not m:
                print("Format moodlemobile:// invalide — assurez-vous de coller l'URL complète.")
                return 1
            raw = m.group(1) + "==="
            try:
                decoded = _b64.b64decode(raw[:len(raw) - len(raw) % 4]).decode("utf-8")
                parts = decoded.split(":::")
                token = parts[1] if len(parts) >= 2 else parts[0]
            except Exception as e:
                print(f"Erreur décodage token: {e}")
                return 1
        settings.moodle_token = token
        save_settings(settings)
        print(f"\n[OK] Token sauvegardé dans le gestionnaire d'identifiants OS (keyring).")
        print("     Prochain run: Moodle synchronisé sans browser ni MFA.")
        return 0

    if args.command == "paths":
        from . import paths
        paths.ensure_runtime_dirs()
        print(f"Runtime  : {paths.app_data_dir()}")
        print(f"Config   : {paths.config_path()}")
        print(f"DB       : {paths.db_path()}")
        print(f"Logs     : {paths.logs_dir()}")
        print(f"Snapshots: {paths.snapshots_dir()}")
        return 0

    if args.command == "replay":
        from .scraper.snapshots import list_runs, print_all_runs, print_run_summary
        from pathlib import Path

        if args.history:
            from .scraper.validator import get_run_history
            history = get_run_history(limit=20)
            if not history:
                print("Aucun historique de runs.")
                return 0
            print(f"\n{len(history)} dernier(s) run(s):\n")
            for h in history:
                status = "PASS" if h["passed"] else "FAIL"
                stats_str = " ".join(f"{k}={v}" for k, v in h["stats"].items())
                print(f"  [{status}] {h['run_at'][:19]}  {stats_str}")
            print()
            return 0

        if args.run:
            from . import paths as _paths
            run_dir = _paths.snapshots_dir() / args.run
            if not run_dir.exists():
                print(f"Run introuvable: {run_dir}")
                print("Runs disponibles:")
                for r in list_runs()[:5]:
                    print(f"  {r.name}")
                return 1
            print_run_summary(run_dir)
        else:
            print_all_runs()
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
