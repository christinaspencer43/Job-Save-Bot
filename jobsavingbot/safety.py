"""One switch for the actions that change the user's real data.

Answering Jobright's "Did you apply?" / "Remove From List", writing a job
to the database through the extension, and sending it to the Google Sheet pass
through `guard()` first.

Safe mode is off by default. With JOBSAVINGBOT_SAFE_MODE=1 (the test suite
sets it for every test) a guarded action is allowed only against a local
sandbox page - an about:/data:/file: page or localhost - and anything else
raises ExternalActionBlocked before the action happens.

Slimmed from Job Save Bot's jobsavebot/safety.py.
"""

from __future__ import annotations

import os
import threading
from urllib.parse import urlsplit

SAFE_MODE_ENV = "JOBSAVINGBOT_SAFE_MODE"

ACTIONS = frozenset({
    "database",    # saving a job through the extension (Supabase)
    "jobright",    # changing Jobright state (applied / not applied / removed)
    "sheet",       # sending saved jobs to the Google Sheet's web app
})

SANDBOX_SUFFIXES = (".test", ".invalid", ".example", ".localhost")
SANDBOX_HOSTS = {"localhost", "127.0.0.1", "::1"}
SANDBOX_SCHEMES = {"about", "data", "file", "blob"}


class ExternalActionBlocked(RuntimeError):
    """A guarded action was stopped because safe mode is on."""

    def __init__(self, action: str, host: str, detail: str = ""):
        self.action, self.host, self.detail = action, host, detail
        super().__init__(f"{action} blocked in safe mode (target: {host or 'external service'})"
                         + (f" - {detail}" if detail else ""))


_lock = threading.Lock()
_audit: list[dict] = []
_forced: bool | None = None


def safe_mode() -> bool:
    if _forced is not None:
        return _forced
    return os.environ.get(SAFE_MODE_ENV, "").strip() == "1"


def set_safe_mode(on: bool | None) -> None:
    global _forced
    _forced = on


def host_of(target: str) -> str:
    parts = urlsplit(target or "")
    return parts.hostname or parts.scheme or ""


def is_sandbox(target: str) -> bool:
    parts = urlsplit(target or "")
    if parts.scheme in SANDBOX_SCHEMES:
        return True
    host = (parts.hostname or "").lower()
    if not host:
        return False
    return host in SANDBOX_HOSTS or host.endswith(SANDBOX_SUFFIXES)


def guard(action: str, target: str = "", detail: str = "") -> None:
    """Allow `action` against `target`, or raise ExternalActionBlocked in safe mode."""
    if action not in ACTIONS:
        raise ValueError(f"unknown guarded action {action!r}")
    if not safe_mode():
        return
    host = host_of(target)
    allowed = is_sandbox(target)
    with _lock:
        _audit.append({"action": action, "host": host, "allowed": allowed})
    if not allowed:
        raise ExternalActionBlocked(action, host, detail)


def audit() -> list[dict]:
    with _lock:
        return list(_audit)


def clear_audit() -> None:
    with _lock:
        _audit.clear()
