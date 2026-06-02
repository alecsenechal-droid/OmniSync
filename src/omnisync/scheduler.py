from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

TASK_NAME = "OmniSync Daily Sync"


@dataclass
class SchedulerResult:
    ok: bool
    message: str


def _python_command() -> str:
    project_root = Path(__file__).resolve().parents[2]
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    exe = venv_python if venv_python.exists() else Path(sys.executable)
    return f'"{exe}" -m omnisync run'


def install(time: str = "05:00") -> SchedulerResult:
    command = _python_command()
    args = [
        "schtasks", "/Create",
        "/TN", TASK_NAME,
        "/TR", command,
        "/SC", "DAILY",
        "/ST", time,
        "/F",
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode == 0:
        return SchedulerResult(True, f"Tache planifiee installee a {time}.")
    return SchedulerResult(False, result.stderr.strip() or result.stdout.strip())


def remove() -> SchedulerResult:
    result = subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], capture_output=True, text=True)
    if result.returncode == 0:
        return SchedulerResult(True, "Tache planifiee supprimee.")
    return SchedulerResult(False, result.stderr.strip() or result.stdout.strip())


def status() -> SchedulerResult:
    result = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME], capture_output=True, text=True)
    if result.returncode == 0:
        return SchedulerResult(True, result.stdout.strip())
    return SchedulerResult(False, "Tache planifiee absente ou inaccessible.")
