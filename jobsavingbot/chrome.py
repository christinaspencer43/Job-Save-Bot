"""Launching and attaching to the Chrome instance the bot drives.

Chrome 136+ refuses --remote-debugging-port on the default user data
directory, so the bot always runs on its own profile folder
(%LOCALAPPDATA%\\JobSavingBot\\chrome-profile) and its own port (9444).

Ported from Job Save Bot's jobsavebot/chrome.py: find_chrome, launch,
wait_for_devtools, the ownership check and close_bot_chrome are unchanged
apart from the extension flags; profile importing was dropped.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .config import check_port, extension_is_built  # noqa: F401 - extension_is_built is used here and by gui.py

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
]


def find_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        path = Path(os.path.expandvars(candidate))
        if path.exists():
            return str(path)
    return ""


def extension_args(extension_dir) -> list[str]:
    """Flags that load the unpacked extension on start.

    Branded Chrome 137+ ignores --load-extension unless the feature that
    disables it is itself disabled. If Chrome still ignores it, the
    extension has to be loaded once by hand (chrome://extensions ->
    Developer mode -> Load unpacked); it then stays in the profile.
    """
    if not extension_is_built(extension_dir):
        return []
    return [
        f"--load-extension={Path(extension_dir)}",
        "--disable-features=DisableLoadExtensionCommandLineSwitch",
    ]


def port_is_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0


class BrowserNotOwned(RuntimeError):
    """The browser on the debugging port is not the bot's own."""


LOOPBACK = {"127.0.0.1", "::1"}


def debug_port_listeners(port: int) -> list[dict]:
    """Every process listening on this TCP port: address, PID, command line."""
    script = (
        f"$l = @(Get-NetTCPConnection -LocalPort {int(port)} -State Listen -ErrorAction SilentlyContinue); "
        "$out = foreach ($c in $l) { $p = Get-CimInstance Win32_Process -Filter \"ProcessId=$($c.OwningProcess)\"; "
        "[pscustomobject]@{address=$c.LocalAddress; pid=$c.OwningProcess; command_line=$p.CommandLine} }; "
        "ConvertTo-Json -Compress -InputObject @($out)"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    text = (result.stdout or "").strip()
    if not text:
        return []
    data = json.loads(text)
    return data if isinstance(data, list) else [data]


def user_data_dir_of(command_line: str) -> str:
    """The --user-data-dir value, however Windows quoted it."""
    line = command_line or ""
    flag = "--user-data-dir="
    at = line.find(flag)
    if at < 0:
        return ""
    rest = line[at + len(flag):]
    if at > 0 and line[at - 1] == '"':
        return rest.split('"', 1)[0]
    if rest.startswith('"'):
        return rest[1:].split('"', 1)[0]
    return rest.split()[0] if rest.split() else ""


def _same_path(a: str, b: str) -> bool:
    def norm(value):
        try:
            return os.path.normcase(str(Path(value).resolve()))
        except OSError:
            return os.path.normcase(os.path.abspath(value))
    return bool(a) and bool(b) and norm(a) == norm(b)


def check_owned(port: int, profile_dir, listeners=None) -> dict:
    """Refuse any browser on the debugging port but the bot's own.

    Attaches only to a browser started on the bot's own profile folder, and
    only when the port listens on loopback. Unknown is not owned.
    """
    check_port(port)
    if sys.platform != "win32" and listeners is None:
        return {"checked": False, "reason": "ownership is only checked on Windows"}
    found = debug_port_listeners(port) if listeners is None else listeners
    if not found:
        raise BrowserNotOwned(f"nothing is listening on debugging port {port}")
    exposed = [str(l.get("address")) for l in found if str(l.get("address")) not in LOOPBACK]
    if exposed:
        raise BrowserNotOwned(
            f"debugging port {port} listens on {', '.join(exposed)} - not only on this machine; not attaching")
    owners = {user_data_dir_of(str(l.get("command_line") or "")) for l in found}
    if len(owners) != 1 or not _same_path(next(iter(owners)), str(profile_dir)):
        raise BrowserNotOwned(
            f"the browser on debugging port {port} is not running the bot's own profile folder - "
            "not attaching to it")
    return {"checked": True, "pid": found[0].get("pid")}


def connect_owned(pw, port: int, profile_dir, **kwargs):
    """connect_over_cdp, but only to the bot's own browser."""
    check_owned(port, profile_dir)
    return pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", **kwargs)


def devtools_version(port: int) -> dict | None:
    check_port(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def launch_args(chrome_path: str, user_data_dir, port: int, start_url="",
                extension_dir="") -> list[str]:
    check_port(port)
    args = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--profile-directory=Default",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--hide-crash-restore-bubble",
    ]
    args.extend(extension_args(extension_dir))
    for url in ([start_url] if isinstance(start_url, str) else list(start_url or [])):
        if url:
            args.append(url)
    return args


def launch(chrome_path: str, user_data_dir, port: int, start_url="",
           extension_dir="") -> subprocess.Popen | None:
    """Start Chrome with remote debugging, or reuse one already listening."""
    if devtools_version(port):
        return None
    Path(user_data_dir).mkdir(parents=True, exist_ok=True)
    args = launch_args(chrome_path, user_data_dir, port, start_url, extension_dir)
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(args, creationflags=creationflags)


def wait_for_devtools(port: int, timeout: float = 45.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = devtools_version(port)
        if found:
            return found
        time.sleep(0.4)
    raise TimeoutError(
        f"Chrome did not open its debugging port {port} within {timeout:.0f}s. "
        "Close every Chrome window started from this app and try again."
    )


def close_bot_chrome(port: int, profile_dir) -> bool:
    """Shut down the bot's own Chrome (never any other)."""
    if not devtools_version(port):
        return False
    try:
        check_owned(port, profile_dir)
    except BrowserNotOwned:
        return False
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = connect_owned(pw, port, profile_dir)
            browser.new_browser_cdp_session().send("Browser.close")
    except Exception:
        pass
    return _wait_for_port_closed(port)


def _wait_for_port_closed(port: int, timeout: float = 6.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not devtools_version(port):
            return True
        time.sleep(0.25)
    return not devtools_version(port)
