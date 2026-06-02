"""
OmniSync UI layer — centralized terminal output.

Mode normal  : dashboard lisible en < 3 secondes, zero log technique.
Mode verbose : logs complets (--verbose ou OMNISYNC_VERBOSE=1).
"""
from __future__ import annotations

import os
import sys
import threading
import time
from datetime import date, datetime
from typing import Any

# ── Colorama ──────────────────────────────────────────────────────────────────
try:
    import colorama
    colorama.init(autoreset=True)
    _G    = colorama.Fore.GREEN   + colorama.Style.BRIGHT
    _R    = colorama.Fore.RED     + colorama.Style.BRIGHT
    _Y    = colorama.Fore.YELLOW  + colorama.Style.BRIGHT
    _B    = colorama.Fore.BLUE    + colorama.Style.BRIGHT
    _C    = colorama.Fore.CYAN    + colorama.Style.BRIGHT
    _DIM  = colorama.Style.DIM
    _BOLD = colorama.Style.BRIGHT
    _RST  = colorama.Style.RESET_ALL
except ImportError:
    _G = _R = _Y = _B = _C = _DIM = _BOLD = _RST = ""

# ── Unicode detection ──────────────────────────────────────────────────────────
_enc = (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "")
_UNI = _enc in ("utf8", "utf16", "utf32", "utf")


def _u(uni: str, asc: str) -> str:
    return uni if _UNI else asc


_BAR  = _u("━", "=")   # ━  heavy horizontal
_OK   = _u("✓", "[OK]") # ✓
_WARN = _u("⚠", "[!]")  # ⚠
_ERR  = _u("✗", "[!!]") # ✗
_BULL = _u("•", "-")    # •

# ── State ──────────────────────────────────────────────────────────────────────
_verbose: bool = False
_module_current: int = 0
_module_total: int = 0
_active_spinner: "_Spinner | None" = None


def init(module_total: int = 0) -> None:
    global _verbose, _module_total, _module_current
    _verbose = bool(os.getenv("OMNISYNC_VERBOSE"))
    _module_total = module_total
    _module_current = 0


def is_verbose() -> bool:
    return _verbose


# ── Spinner ────────────────────────────────────────────────────────────────────
_FRAMES = ["|", "/", "-", "\\"]


class _Spinner:
    def __init__(self, msg: str) -> None:
        self._msg = msg
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._running = False

    def _run(self) -> None:
        i = 0
        while not self._stop.is_set():
            f = _FRAMES[i % len(_FRAMES)]
            sys.stdout.write(f"\r{_B}{f}{_RST} {_DIM}{self._msg}{_RST}   ")
            sys.stdout.flush()
            time.sleep(0.12)
            i += 1

    def start(self) -> "_Spinner":
        if not _verbose:
            if sys.stdout.isatty():
                self._t.start()
                self._running = True
            else:
                # Non-TTY (pipe, capture, redirect) : une seule ligne statique
                sys.stdout.write(f"-- {self._msg}\n")
                sys.stdout.flush()
        return self

    def stop(self) -> None:
        if self._running:
            self._stop.set()
            self._t.join(timeout=0.5)
            width = len(self._msg) + 10
            sys.stdout.write("\r" + " " * width + "\r")
            sys.stdout.flush()
            self._running = False


def start_spinner(msg: str) -> _Spinner:
    """Demarre un spinner. Appelez .stop() quand c'est pret."""
    return _Spinner(msg).start()


# ── Labels ────────────────────────────────────────────────────────────────────
_MODULE_LABELS: dict[str, str] = {
    "lea_assignments":      "Travaux LEA",
    "lea_calendar":         "Calendrier LEA",
    "final_exams":          "Examens finaux",
    "actualites":           "Actualites",
    "documents_deadlines":  "Documents LEA",
    "moodle":               "Moodle",
    "horaire":              "Horaire de cours",
}

_KIND_LABELS: dict[str, str] = {
    "assignment": "Remise",
    "exam":       "Examen",
    "reading":    "Lecture",
    "event":      "Annonce",
    "class":      "Cours",
}

_REASON_STEPS: dict[str, list[str]] = {
    "sudden_drop_to_zero": [
        "Reessayer dans 5 min  :  run.bat run",
        "Voir le snapshot      :  run.bat replay",
        "Si ca persiste        :  verifier omnivox.ca",
    ],
    "major_data_loss": [
        "Verifier Omnivox manuellement sur omnivox.ca",
        "Reessayer             :  run.bat run",
        "Voir le snapshot      :  run.bat replay",
    ],
    "significant_drop": [
        "Peut etre normal en fin de session",
        "Si ca surprend        :  run.bat replay",
    ],
    "session_expired": [
        "Normal en fin de session -- aucune action requise.",
        "Les travaux reapparaitront au debut de la prochaine session.",
    ],
}

_REASON_CAUSE: dict[str, str] = {
    "sudden_drop_to_zero": "Session expiree ou changement Omnivox",
    "major_data_loss":     "Perte massive -- verifier Omnivox",
    "significant_drop":    "Baisse importante depuis le dernier run",
    "session_expired":     "Fin de session -- aucun travail actif normal",
}


# ── Section helpers ────────────────────────────────────────────────────────────
def _sep() -> str:
    return f"{_DIM}{_BAR * 44}{_RST}"


def _section(title: str) -> None:
    print()
    print(_sep())
    print(f"  {_BOLD}{title}{_RST}")
    print(_sep())


# ── Banner ─────────────────────────────────────────────────────────────────────
def banner(mode: str = "live") -> None:
    mode_label = {
        "dry":    f"{_Y}DRY RUN{_RST}",
        "scrape": f"{_Y}SCRAPE ONLY{_RST}",
        "live":   f"{_G}SYNC{_RST}",
    }.get(mode, mode.upper())

    now = datetime.now().strftime("%Y-%m-%d  %H:%M")
    arrow = _u("→", "->")

    print()
    print(f"  {_BOLD}{_C}OMNISYNC{_RST}")
    print(f"  {_DIM}Omnivox {arrow} Google Calendar{_RST}")
    print(f"  {_DIM}{now}{_RST}  {_DIM}|{_RST}  {mode_label}")
    print()


# ── String helpers (for other modules) ────────────────────────────────────────
def ok(msg: str) -> str:
    return f"{_G}[OK]{_RST} {msg}"


def err(msg: str) -> str:
    return f"{_R}[!!]{_RST} {msg}"


def warn(msg: str) -> str:
    return f"{_Y}[!]{_RST} {msg}"


def inf(msg: str) -> str:
    return f"{_C}-->{_RST} {msg}"


def bold(msg: str) -> str:
    return f"{_BOLD}{msg}{_RST}"


def dim(msg: str) -> str:
    return f"{_DIM}{msg}{_RST}"


def section(title: str) -> None:
    _section(title)


def header(title: str) -> None:
    line = "=" * (len(title) + 4)
    print(f"\n{_BOLD}{line}")
    print(f"  {title}")
    print(f"{line}{_RST}\n")


# ── Public print API ───────────────────────────────────────────────────────────
def success(msg: str) -> None:
    print(f"{_G}[OK]{_RST} {msg}")


def error(msg: str) -> None:
    print(f"{_R}[!!]{_RST} {msg}")


def warning(msg: str) -> None:
    print(f"  {_Y}[!]{_RST} {msg}")


def info(msg: str) -> None:
    print(f"  {_C}-->{_RST} {msg}")


def vlog(msg: str) -> None:
    """Print uniquement en mode verbose."""
    if _verbose:
        print(f"{_DIM}    {msg}{_RST}")


# ── Verbose module progress (affiché uniquement avec --verbose) ────────────────
def module_start(mod_name: str) -> None:
    global _module_current
    _module_current += 1
    if not _verbose:
        return
    label = _MODULE_LABELS.get(mod_name, mod_name.replace("_", " ").title())
    n, total = _module_current, _module_total
    prefix = f"{_DIM}[{n}/{total}]{_RST} " if total else ""
    print(f"\n{prefix}{_C}{label}{_RST}")


def module_done(mod_name: str, count: int, extra: str = "") -> None:
    if not _verbose:
        return
    label = _MODULE_LABELS.get(mod_name, mod_name.replace("_", " ").title())
    n, total = _module_current, _module_total
    prefix = f"{_DIM}[{n}/{total}]{_RST} " if total else ""
    if count > 0:
        mark = f"{_G}[OK]{_RST}"
        detail = f"{count}" + (f"  {_DIM}{extra}{_RST}" if extra else "")
    else:
        mark = f"{_Y}[!]{_RST}"
        detail = f"{_DIM}aucun resultat{_RST}" + (f"  {_DIM}{extra}{_RST}" if extra else "")
    print(f"  {mark} {prefix}{label} : {detail}")


def module_error(mod_name: str, msg: str) -> None:
    global _module_current
    if not _verbose:
        return
    label = _MODULE_LABELS.get(mod_name, mod_name.replace("_", " ").title())
    n, total = _module_current, _module_total
    prefix = f"{_DIM}[{n}/{total}]{_RST} " if total else ""
    print(f"  {_R}[!!]{_RST} {prefix}{label} : erreur {_DIM}-- {msg}{_RST}")


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

def _statut(
    module_stats: dict,
    anomaly_count: int,
) -> None:
    """Section STATUT — vue globale en 3-5 lignes."""
    _section("STATUT")
    print()

    # Connexion
    print(f"  {_G}{_OK}{_RST} Connexion Omnivox")

    # Calendrier (lea_calendar)
    cal = module_stats.get("lea_calendar")
    if cal is not None:
        n = cal.count
        detail = f"{_DIM}{n} evenements{_RST}" if n else f"{_DIM}session terminee{_RST}"
        mark = f"{_G}{_OK}{_RST}"
        print(f"  {mark} Calendrier          {detail}")

    # Moodle
    moodle = module_stats.get("moodle")
    if moodle is not None:
        n = moodle.count
        detail = f"{_DIM}{n} travaux{_RST}" if n else f"{_DIM}aucun travail{_RST}"
        mark = f"{_G}{_OK}{_RST}"
        print(f"  {mark} Moodle              {detail}")

    # Anomalies
    if anomaly_count:
        label = "anomalie detectee" if anomaly_count == 1 else f"{anomaly_count} anomalies detectees"
        print(f"  {_R}{_WARN}{_RST} {_R}{label}{_RST}")
    else:
        print(f"  {_G}{_OK}{_RST} Aucune anomalie")


def _resultats(
    total_events: int,
    module_stats: dict,
    cal_created: int,
    cal_updated: int,
    cal_deleted: int,
    mode: str,
    actualites_count: int,
) -> None:
    """Section RESULTATS."""
    _section("RESULTATS")
    print()

    moodle = module_stats.get("moodle")
    moodle_count = moodle.count if moodle else 0

    print(f"  {_C}{total_events:>4}{_RST}  evenements Omnivox trouves")
    if moodle_count:
        print(f"  {_C}{moodle_count:>4}{_RST}  travaux Moodle")
    if actualites_count:
        print(f"  {_DIM}{actualites_count:>4}{_RST}  actualites pertinentes")

    if mode == "dry":
        print(f"\n  {_Y}Simulation -- aucune modification dans Calendar{_RST}")
    elif mode == "scrape":
        print(f"\n  {_DIM}Calendar non modifie (--scrape-only){_RST}")
    elif cal_created or cal_updated or cal_deleted:
        print()
        if cal_created:
            print(f"  {_G}{cal_created:>4}{_RST}  crees dans Google Calendar")
        if cal_updated:
            print(f"  {_G}{cal_updated:>4}{_RST}  mis a jour dans Google Calendar")
        if cal_deleted:
            print(f"  {_Y}{cal_deleted:>4}{_RST}  supprimes de Google Calendar")
    else:
        print(f"\n  {_DIM}Calendar deja a jour (0 modification){_RST}")


def _a_venir(events: list) -> None:
    """Section A VENIR."""
    today = date.today()
    relevant = [
        e for e in events
        if getattr(e, "date_iso", None)
        and e.date_iso >= today.isoformat()
        and getattr(e, "kind", "") in ("assignment", "exam", "reading", "event")
    ]
    relevant.sort(key=lambda e: e.date_iso or "")
    if not relevant:
        return

    _section("A VENIR")
    print()
    for e in relevant[:5]:
        try:
            d = date.fromisoformat(e.date_iso)
            delta = (d - today).days
            if delta == 0:
                when = f"{_R}Aujourd'hui{_RST}"
            elif delta == 1:
                when = f"{_Y}Demain{_RST}     "
            elif delta <= 7:
                when = f"{_Y}Dans {delta} jours{_RST}"
            else:
                when = f"{_DIM}{d.strftime('%d %b')}{_RST}      "
        except (ValueError, TypeError):
            when = f"{_DIM}{e.date_iso}{_RST}"
        kind = _KIND_LABELS.get(getattr(e, "kind", ""), "")
        kind_str = f"{_DIM}[{kind}]{_RST} " if kind else ""
        title = (getattr(e, "title", "") or "")[:55]
        print(f"  {when:<28}  {kind_str}{title}")


def _attention(validation_report: Any) -> None:
    """Section ATTENTION — uniquement si anomalies."""
    if not validation_report or not validation_report.has_failures:
        return

    failures = [e for e in validation_report.events if e.level == "FAIL"]
    if not failures:
        return

    _section("ATTENTION")
    for f in failures:
        label = _MODULE_LABELS.get(f.module, f.module.replace("_", " ").title())
        cause = _REASON_CAUSE.get(f.reason, f.reason.replace("_", " "))
        steps = _REASON_STEPS.get(f.reason, ["run.bat replay"])

        print()
        print(f"  {_R}{_WARN} {label}{_RST}")
        print(f"     Avant       : {_DIM}{f.previous}{_RST}   "
              f"Maintenant  : {_R}{f.current}{_RST}")
        print(f"     Cause       : {_DIM}{cause}{_RST}")
        print()
        print(f"     Quoi faire :")
        for i, step in enumerate(steps, 1):
            print(f"     {i}. {step}")


def _actions(mode: str, has_anomaly: bool = False) -> None:
    """Section PROCHAINES ACTIONS."""
    _section("PROCHAINES ACTIONS")
    print()
    if mode == "dry":
        print(f"  {_BULL} {_BOLD}run.bat run{_RST}              synchroniser maintenant")
    print(f"  {_BULL} run.bat run --verbose    voir les logs techniques")
    if has_anomaly:
        print(f"  {_BULL} run.bat replay           inspecter les snapshots")
    print()


def dashboard(
    mode: str,
    events: list,
    module_stats: dict | None,
    validation_report: Any,
    cal_created: int = 0,
    cal_updated: int = 0,
    cal_deleted: int = 0,
) -> None:
    """
    Affiche le dashboard complet (mode normal uniquement).
    En mode verbose, les modules ont deja affiche leur output.
    """
    ms = module_stats or {}
    anomaly_count = (
        sum(1 for e in validation_report.events if e.level == "FAIL")
        if validation_report else 0
    )
    actualites_count = len([
        e for e in events
        if getattr(e, "kind", "") == "event" and not getattr(e, "course_code", None)
    ])
    total_events = len(events)

    _statut(ms, anomaly_count)
    _resultats(total_events, ms, cal_created, cal_updated, cal_deleted, mode, actualites_count)
    _a_venir(events)
    _attention(validation_report)
    _actions(mode, has_anomaly=bool(anomaly_count))
