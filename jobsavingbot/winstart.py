"""Keeping the bot ready on a computer that stays on, for KIASA to start it.

* Start with Windows: a "Run" entry for this user starts the app in the tray
  when they sign in to Windows.
* Started again if it ever stops: a Windows task for this user starts it every
  10 minutes; a copy already running makes the new one leave at once.
* Kept awake: while the bot is connected to KIASA, Windows is asked not to put
  the computer to sleep (the screen may still turn off).

None of this needs administrator rights. Off Windows these do nothing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .config import APP_DIR
from .safety import safe_mode

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "JobSavingBot"
TASK_NAME = "Job Saving Bot - keep running"
BACKGROUND_FLAG = "--background"


def launch_command() -> list[str]:
    """This app, started without a console window, into the tray."""
    python = Path(sys.executable)
    windowless = python.with_name("pythonw.exe")
    return [str(windowless if windowless.exists() else python), str(APP_DIR / "app.py"), BACKGROUND_FLAG]


def _run_hidden(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=30,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, RUN_NAME)
        return True
    except OSError:
        return False


def set_autostart(on: bool) -> str:
    """Start with Windows (and again if it stops), or not. "" when done, else what went wrong."""
    if sys.platform != "win32":
        return "only on Windows"
    if safe_mode():  # the tests: the real start list is not theirs to change
        return "safe mode: the Windows start list is left alone"
    import winreg

    command = subprocess.list2cmdline(launch_command())
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if on:
                winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, RUN_NAME)
                except FileNotFoundError:
                    pass
    except OSError as exc:
        return f"could not change the Windows start list ({exc})"
    if on:
        done = _run_hidden(["schtasks", "/Create", "/F", "/SC", "MINUTE", "/MO", "10", "/TN", TASK_NAME, "/TR", command])
    else:
        done = _run_hidden(["schtasks", "/Delete", "/F", "/TN", TASK_NAME])
        if done.returncode and "cannot find" in (done.stderr or "").lower():
            return ""
    if done.returncode:
        return f"the keep-running task: {(done.stderr or done.stdout or '').strip()[:200]}"
    return ""


# SetThreadExecutionState flags.
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def keep_awake(on: bool) -> None:
    """Ask Windows to keep the computer from sleeping (on), or let it (off).
    Holds for the thread that asks, so the window's own thread asks."""
    if sys.platform != "win32" or safe_mode():
        return
    import ctypes

    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
