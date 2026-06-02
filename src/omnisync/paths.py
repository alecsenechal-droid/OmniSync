from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "OmniSync"


def app_data_dir() -> Path:
    override = os.environ.get("OMNISYNC_HOME")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / ".omnisync"


def config_path() -> Path:
    return app_data_dir() / "config.toml"


def db_path() -> Path:
    return app_data_dir() / "omnivox.db"


def logs_dir() -> Path:
    return app_data_dir() / "logs"


def browser_profile_dir() -> Path:
    return app_data_dir() / "browser_profile"


def token_path() -> Path:
    return app_data_dir() / "token.json"


def credentials_path() -> Path:
    return app_data_dir() / "credentials.json"


def snapshots_dir() -> Path:
    return app_data_dir() / "snapshots"


def moodle_session_path() -> Path:
    """Chemin vers le fichier de session Microsoft sauvegardé pour Moodle SSO."""
    return app_data_dir() / "moodle_session.json"


def ensure_runtime_dirs() -> None:
    for path in [app_data_dir(), logs_dir(), browser_profile_dir(), snapshots_dir()]:
        path.mkdir(parents=True, exist_ok=True)
