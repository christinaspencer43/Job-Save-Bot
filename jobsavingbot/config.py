"""Persisted settings: %LOCALAPPDATA%/JobSavingBot/settings.json."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

APP_NAME = "JobSavingBot"
JOBRIGHT_DEFAULT_URL = "https://jobright.ai/jobs/recommend"
DEFAULT_PORT = 9444
#: Debugging ports that belong to other tools on this machine (9222 = the
#: old Job Save Bot, 9333 = another agent). This app never uses them.
FORBIDDEN_PORTS = frozenset({9222, 9333})

#: The app's own folder (where app.py and the .bat file are). It can be copied
#: to any computer and any place, so nothing below is a fixed path.
APP_DIR = Path(__file__).resolve().parents[1]
#: The "Job JD Scanner" build (an unpacked Chrome extension) that ships with
#: the app, in its "extension" folder.
DEFAULT_EXTENSION_DIR = str(APP_DIR / "extension")


def extension_is_built(extension_dir) -> bool:
    return bool(extension_dir) and (Path(extension_dir) / "manifest.json").is_file()


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_profile_dir() -> Path:
    return app_data_dir() / "chrome-profile"


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def check_port(port: int) -> int:
    port = int(port)
    if port in FORBIDDEN_PORTS:
        raise ValueError(f"port {port} belongs to another tool - Job Saving Bot never uses it")
    return port


@dataclass
class Settings:
    debug_port: int = DEFAULT_PORT
    run_count: int = 10
    chrome_path: str = ""
    profile_dir: str = ""
    extension_dir: str = DEFAULT_EXTENSION_DIR
    jobright_url: str = JOBRIGHT_DEFAULT_URL

    # Human-ish pacing between cards, in seconds (jittered between lo and hi).
    pause_lo: float = 1.0
    pause_hi: float = 2.5
    # Hard ceilings, in seconds.
    page_timeout: float = 30.0
    save_timeout: float = 45.0

    # Hover before clicking, skim the posting, show a banner on it.
    human_mode: bool = True
    # Raise the Chrome window at every step (off: switch tabs quietly).
    focus_browser: bool = False
    # Count a save the extension kept only locally (not synced to the
    # database) as saved. Off: such a job stays in the Jobright list.
    accept_local_save: bool = False
    # A card that fails this many times is skipped for the rest of the run.
    max_attempts_per_card: int = 2
    # Stop the run after this many failures in a row (something is broken).
    max_consecutive_failures: int = 5

    # Google Sheet export (optional; google-sheets/README.md). Either the
    # sheet's own link, edited with the service account key in
    # google_key_file (empty: google-key.json next to app.py), or the /exec
    # URL of the sheet's Apps Script web app with the SECRET written in that
    # script. Empty URL: nothing is sent.
    google_sheet_url: str = ""
    google_key_file: str = ""
    google_sheet_secret: str = ""

    @classmethod
    def load(cls) -> "Settings":
        path = settings_path()
        data: dict = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
        known = set(cls.__dataclass_fields__)
        settings = cls(**{k: v for k, v in data.items() if k in known})
        try:
            settings.debug_port = check_port(settings.debug_port)
        except (TypeError, ValueError):
            settings.debug_port = DEFAULT_PORT
        if not settings.profile_dir:
            settings.profile_dir = str(default_profile_dir())
        # A settings.json written by an older copy (or before the folder was
        # moved) can name an extension folder that is not there any more.
        if not extension_is_built(settings.extension_dir) and extension_is_built(DEFAULT_EXTENSION_DIR):
            settings.extension_dir = DEFAULT_EXTENSION_DIR
            if path.exists():
                settings.save()
        if not path.exists():
            settings.save()
        return settings

    def save(self) -> None:
        settings_path().write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
