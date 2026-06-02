"""
Utilitaires purs partagés entre tous les scrapers Omnivox.
Responsabilité unique : fonctions sans état (texte, dates, fichiers).
Dépendances : stdlib + Playwright (types uniquement pour safe_text/download_document).
"""
import hashlib
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import Locator, Page

from .omnivox_models import Config, GCAL_COLOR, MOIS_FR_MAP, MOIS_ABBR_MAP


# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    if os.getenv("OMNISYNC_VERBOSE"):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ── Utilitaires texte ─────────────────────────────────────────────────────────

def slugify(value: str, fallback: str = "fichier") -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._-")
    return (value or fallback)[:80]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_text(locator: Locator, timeout: int = 5_000) -> str:
    try:
        return re.sub(r"\n{3,}", "\n\n", locator.inner_text(timeout=timeout)).strip()
    except Exception:
        return ""


def _title_key(title: str) -> str:
    return " ".join(title.lower().replace("—", "-").split())[:100]


# ── Classification des travaux ────────────────────────────────────────────────

def classify_assignment(title: str, config: Config) -> tuple[str, str]:
    exam_kw = config.exam_keywords or [
        "examen", "exam", "intra", "final", "test", "quiz", "évaluation"
    ]
    pattern = re.compile(r'\b(' + '|'.join(re.escape(k) for k in exam_kw) + r')\b', re.IGNORECASE)
    if pattern.search(title):
        return "exam", GCAL_COLOR["exam"]
    return "assignment", GCAL_COLOR["assignment"]


# ── Parsing de dates françaises ───────────────────────────────────────────────

def _parse_fr_date(text: str) -> Optional[str]:
    m = re.search(
        r'(\d{1,2})\s+(' + '|'.join(MOIS_FR_MAP) + r')\s+(\d{4})',
        text, re.IGNORECASE,
    )
    if m:
        mois = MOIS_FR_MAP.get(m.group(2).lower())
        if mois:
            return f"{m.group(3)}-{mois:02d}-{int(m.group(1)):02d}"
    m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    return m2.group(0) if m2 else None


def _parse_date_from_text(text: str) -> Optional[str]:
    normalized = re.sub(r'(\d)-([A-Za-zÀ-ÿ])', r'\1 \2', text)
    normalized = re.sub(r'([A-Za-zÀ-ÿ])-(\d)', r'\1 \2', normalized)
    m = re.search(
        r"(\d{1,2})\s+(jan|fév|mar|avr|mai|juin|juil|août|sep|oct|nov|déc)\w*\s+(\d{4})",
        normalized, re.IGNORECASE,
    )
    if m:
        mois = next((v for k, v in MOIS_ABBR_MAP.items() if m.group(2).lower().startswith(k)), None)
        if mois:
            return f"{m.group(3)}-{mois:02d}-{int(m.group(1)):02d}"
    fr = _parse_fr_date(text)
    if fr:
        return fr
    m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    return m2.group(0) if m2 else None


def _parse_colonne_date_lea(text: str) -> tuple[Optional[str], Optional[str]]:
    """Parse td.colonneDate: '28-fév-2026 à 12:00' ou '28 février 2026'."""
    text = (text or "").strip().replace("\xa0", " ")
    m = re.search(
        r"(\d{1,2})-([a-zéûôàèêù]+)-(\d{4})\s*(?:à\s*)?(\d{1,2})?:?(\d{2})?",
        text,
        re.IGNORECASE,
    )
    if m:
        mon_raw = m.group(2).lower()
        mois = MOIS_FR_MAP.get(mon_raw) or MOIS_ABBR_MAP.get(mon_raw[:3])
        if mois:
            date_iso = f"{m.group(3)}-{mois:02d}-{int(m.group(1)):02d}"
            time_start = ""
            if m.group(4) and m.group(5):
                time_start = f"{int(m.group(4)):02d}:{m.group(5)}"
            return date_iso, time_start or None
    date_iso = _parse_date_from_text(text)
    if date_iso:
        ts, _ = _parse_time_range(text)
        return date_iso, ts or None
    return None, None


def _parse_time_range(text: str) -> tuple[str, str]:
    m = re.search(r'(\d{1,2})[h:](\d{2})\s+[àa]\s+(\d{1,2})[h:](\d{2})', text)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}", f"{int(m.group(3)):02d}:{m.group(4)}"
    m2 = re.search(r'(\d{1,2})[h:](\d{2})', text)
    return (f"{int(m2.group(1)):02d}:{m2.group(2)}", "") if m2 else ("", "")


# ── Utilitaires fichiers ──────────────────────────────────────────────────────

def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest() if path.exists() else ""


def smart_save_text(path: Path, content: str) -> str:
    """Sauvegarde un fichier texte. Retourne 'new'/'updated'/'unchanged'."""
    encoded = content.encode("utf-8")
    new_hash = hashlib.md5(encoded).hexdigest()
    if path.exists():
        if hashlib.md5(path.read_bytes()).hexdigest() == new_hash:
            return "unchanged"
        path.write_bytes(encoded)
        return "updated"
    ensure_dir(path.parent)
    path.write_bytes(encoded)
    return "new"


def smart_save_bytes(path: Path, content: bytes) -> str:
    """Sauvegarde un fichier binaire. Retourne 'new'/'updated'/'unchanged'."""
    new_hash = hashlib.md5(content).hexdigest()
    if path.exists():
        if hashlib.md5(path.read_bytes()).hexdigest() == new_hash:
            return "unchanged"
        path.write_bytes(content)
        return "updated"
    ensure_dir(path.parent)
    path.write_bytes(content)
    return "new"


# ── Téléchargement de documents ───────────────────────────────────────────────

_CT_EXTS: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
    "application/zip": ".zip",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


def _strip_sid(url: str) -> str:
    """Supprime le SID de session de l'URL pour la stabilité des hashes inter-sessions."""
    url = re.sub(r'([?&])SID=[^&]*&?', lambda m: m.group(1) if m.group(0).endswith('&') else '', url)
    return url.rstrip("?&")


def _extract_pdf_url_from_viewer(html: str, viewer_url: str) -> str:
    """Extrait l'URL directe du PDF depuis le HTML d'une page viewer (VisualiseDocument.aspx)."""
    for pattern in [
        r'<iframe[^>]+src=["\']([^"\']+)["\']',
        r'<embed[^>]+src=["\']([^"\']+)["\']',
        r'<object[^>]+data=["\']([^"\']+)["\']',
        r'href=["\']([^"\']+\.pdf[^"\']*)["\']',
        r'src=["\']([^"\']*[Gg]et[Dd]ocument[^"\']*)["\']',
        r'src=["\']([^"\']*[Tt]elecharger[^"\']*)["\']',
        r'src=["\']([^"\']*[Dd]ownload[^"\']*)["\']',
    ]:
        m = re.search(pattern, html)
        if m:
            src = m.group(1)
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                base = re.match(r'(https?://[^/]+)', viewer_url)
                src = (base.group(1) if base else "") + src
            elif not src.startswith("http"):
                src = viewer_url.rsplit("/", 1)[0] + "/" + src
            return src
    return ""


def download_document(page: Page, url: str, dest_path: Path) -> str:
    """Télécharge un document via la session du navigateur. Retourne 'new'/'updated'/'unchanged'/'error'."""
    try:
        import requests as req_lib
        cookies = {c["name"]: c["value"] for c in page.context.cookies()}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = req_lib.get(url, cookies=cookies, headers=headers, timeout=30)
        if resp.status_code != 200:
            return "error"
        ct = resp.headers.get("content-type", "").split(";")[0].strip().lower()

        if ct == "text/html":
            pdf_url = _extract_pdf_url_from_viewer(resp.text, url)
            if not pdf_url:
                return "error"
            resp2 = req_lib.get(pdf_url, cookies=cookies, headers=headers, timeout=30)
            if resp2.status_code != 200:
                return "error"
            ct = resp2.headers.get("content-type", "").split(";")[0].strip().lower()
            if ct == "text/html":
                return "error"
            content = resp2.content
        else:
            content = resp.content

        if ct in _CT_EXTS:
            ext = _CT_EXTS[ct]
            if dest_path.suffix.lower() not in (".pdf", ".docx", ".doc", ".pptx", ".ppt",
                                                 ".xlsx", ".xls", ".zip"):
                dest_path = dest_path.with_suffix(ext)
        return smart_save_bytes(dest_path, content)
    except Exception as exc:
        log(f"    Erreur téléchargement {dest_path.name}: {exc}")
        return "error"
