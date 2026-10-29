"""The Job Saving Bot window: Open Chrome, Start N, Stop, a log and the counts.

Connected to KIASA (box 4), it also takes runs KIASA's admins ask for, tells
KIASA how each run goes, and stays in the tray when its window is closed."""

from __future__ import annotations

import os
import shutil
import sys
import threading
import time
from pathlib import Path

from PySide6 import QtCore, QtGui, QtNetwork, QtWidgets

from . import __version__, winstart
from . import chrome as chrome_mod
from . import kiasa as kiasa_mod
from . import sheets
from .config import APP_DIR, Settings, default_profile_dir
from .extension import ExtensionNotFound, find_extension_id, load_instructions
from .runner import BotRunner, SetupError, StopRequested

LOG_COLORS = {
    "info": "#c9d1d9",
    "ok": "#3fb950",
    "warn": "#d29922",
    "error": "#f85149",
    "step": "#58a6ff",
}

STYLESHEET = """
QWidget { background: #0d1117; color: #c9d1d9; font-size: 13px; }
QGroupBox {
    border: 1px solid #21262d; border-radius: 8px;
    margin-top: 14px; padding: 12px 10px 10px 10px; font-weight: 600;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #8b949e; }
QPushButton {
    background: #21262d; border: 1px solid #30363d; border-radius: 6px;
    padding: 7px 14px; color: #c9d1d9;
}
QPushButton:hover:enabled { background: #30363d; border-color: #8b949e; }
QPushButton:disabled { color: #484f58; border-color: #21262d; }
QPushButton#primary { background: #238636; border-color: #2ea043; color: #ffffff; font-weight: 600; }
QPushButton#primary:hover:enabled { background: #2ea043; }
QPushButton#danger { background: #4d1f1f; border-color: #8b2c2c; color: #ffb4b4; }
QPushButton#danger:hover:enabled { background: #6b2a2a; }
QPushButton#danger:disabled { background: #21262d; border-color: #21262d; color: #484f58; }
QPushButton#primary:disabled { background: #21262d; border-color: #21262d; color: #484f58; }
QSpinBox {
    background: #010409; border: 1px solid #30363d; border-radius: 6px; padding: 5px 7px;
}
QSpinBox:focus { border-color: #58a6ff; }
QLineEdit {
    background: #010409; border: 1px solid #30363d; border-radius: 6px; padding: 5px 7px;
}
QLineEdit:focus { border-color: #58a6ff; }
QTextEdit {
    background: #010409; border: 1px solid #21262d; border-radius: 8px;
    font-family: Consolas, 'Cascadia Mono', monospace; font-size: 12px;
}
QProgressBar {
    background: #010409; border: 1px solid #21262d; border-radius: 6px;
    height: 16px; text-align: center; color: #c9d1d9;
}
QProgressBar::chunk { background: #238636; border-radius: 5px; }
QLabel#hint { color: #8b949e; font-size: 11px; }
QLabel#counts { font-size: 14px; font-weight: 600; }
"""


class _Worker(QtCore.QObject):
    """Runs one callable off the UI thread."""

    log = QtCore.Signal(str, str)
    done = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, job):
        super().__init__()
        self._job = job

    @QtCore.Slot()
    def run(self):
        try:
            result = self._job(self.log.emit)
        except Exception as exc:  # noqa: BLE001 - reported in the log pane
            self.failed.emit(str(exc))
            return
        self.done.emit(result)


class _OnUiThread(QtCore.QObject):
    """Calls a function on the UI thread (a signal connected straight to a
    closure would run it on the worker thread)."""

    def __init__(self, function, parent):
        super().__init__(parent)
        self._function = function

    @QtCore.Slot(object)
    def call(self, value):
        self._function(value)


class RunWorker(QtCore.QObject):
    log = QtCore.Signal(str, str)
    stats = QtCore.Signal(dict)
    progress = QtCore.Signal(int, int)
    done = QtCore.Signal(dict)
    failed = QtCore.Signal(str)

    def __init__(self, settings: Settings, count: int, on_saved=None):
        super().__init__()
        self.count = count
        self.runner = BotRunner(
            settings,
            log=lambda message, level="info": self.log.emit(message, level),
            on_stats=self.stats.emit,
            on_progress=self.progress.emit,
            on_saved=on_saved,
        )

    @QtCore.Slot()
    def run(self):
        try:
            stats = self.runner.run(self.count)
        except StopRequested:
            self.log.emit("Stopped by you.", "warn")
            self.done.emit(self.runner.stats.as_dict())
            return
        except SetupError as exc:
            self.failed.emit(f"cannot start - {exc}")
            return
        except Exception as exc:  # noqa: BLE001 - reported in the log pane
            self.failed.emit(str(exc))
            return
        self.done.emit(stats.as_dict())

    def request_stop(self):
        self.runner.stop_event.set()


class MainWindow(QtWidgets.QWidget):
    status_ready = QtCore.Signal(dict)
    # From KIASA's threads to the window's: how the connection is, a run asked
    # for, Stop pressed on KIASA, and a line for the log.
    kiasa_status = QtCore.Signal(str, str)
    kiasa_run = QtCore.Signal(object, object)
    kiasa_stop = QtCore.Signal()
    kiasa_log = QtCore.Signal(str, str)

    def __init__(self, poll: bool = True):
        super().__init__()
        self.settings = Settings.load()
        if not self.settings.chrome_path:
            self.settings.chrome_path = chrome_mod.find_chrome()
        if not self.settings.profile_dir:
            self.settings.profile_dir = str(default_profile_dir())

        self._thread: QtCore.QThread | None = None
        self._run_worker: RunWorker | None = None
        self._bg: list[tuple[QtCore.QThread, _Worker]] = []
        self._status_checking = False
        self._closing = False
        self._chrome_live = False
        self._start_time = 0.0
        # KIASA: the check-ins, the saved jobs on their way, the run's report,
        # and what the bot last found wrong (told to KIASA until a run goes).
        self._remote: kiasa_mod.RemoteControl | None = None
        self._outbox: kiasa_mod.KiasaOutbox | None = None
        self._report: kiasa_mod.RunReport | None = None
        self._stop_from_kiasa = False
        self._opening_for_run = False
        self._trouble: tuple[str, str] | None = None
        self._quitting = False
        self._tray: QtWidgets.QSystemTrayIcon | None = None
        self._told_tray = False

        self.setWindowTitle("Job Saving Bot")
        self.setMinimumSize(760, 700)
        self.setStyleSheet(STYLESHEET)
        self._build()
        self.status_ready.connect(self._show_chrome_status)
        self.kiasa_status.connect(self._show_kiasa_status)
        self.kiasa_run.connect(self._kiasa_run)
        self.kiasa_stop.connect(lambda: self._stop(from_kiasa=True))
        self.kiasa_log.connect(self.append_log)
        self._update_counts({})

        self.append_log(
            f"Chrome profile: {self.settings.profile_dir} | debug port {self.settings.debug_port}", "info")
        if not chrome_mod.extension_is_built(self.settings.extension_dir):
            self.append_log(
                f"Extension build not found at {self.settings.extension_dir} - the 'extension' folder "
                "next to app.py is missing (or fix extension_dir in settings.json).", "warn")

        self._status_timer = QtCore.QTimer(self)
        self._status_timer.timeout.connect(self._update_chrome_status)
        if poll:
            self._update_chrome_status()
            self._status_timer.start(3000)
            self._make_tray()
            if self.settings.kiasa_code:
                self._connect_kiasa(self.settings.kiasa_code)

    # -- layout ------------------------------------------------------------

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        title = QtWidgets.QLabel("Job Saving Bot")
        title.setStyleSheet("font-size: 21px; font-weight: 700; color: #f0f6fc;")
        subtitle = QtWidgets.QLabel(
            "Works down your Jobright Recommended list: saves each Autofill / Easy Apply "
            "posting with the Job Intelligence extension and removes the Apply Now cards."
        )
        subtitle.setObjectName("hint")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        browser_box = QtWidgets.QGroupBox("1 - Browser")
        browser = QtWidgets.QHBoxLayout(browser_box)
        self.open_button = QtWidgets.QPushButton("Open Chrome")
        self.open_button.setObjectName("primary")
        self.open_button.clicked.connect(self._open_chrome)
        self.close_button = QtWidgets.QPushButton("Close Chrome")
        self.close_button.clicked.connect(self._close_chrome)
        self.extension_button = QtWidgets.QPushButton("Extension folder")
        self.extension_button.setToolTip(
            "Opens the extension folder and copies its path - for chrome://extensions > Load unpacked")
        self.extension_button.clicked.connect(self._show_extension_folder)
        self.chrome_status = QtWidgets.QLabel("Checking Chrome...")
        self.chrome_status.setObjectName("hint")
        self.chrome_status.setWordWrap(True)
        browser.addWidget(self.open_button)
        browser.addWidget(self.close_button)
        browser.addWidget(self.extension_button)
        browser.addWidget(self.chrome_status, 1)
        root.addWidget(browser_box)

        run_box = QtWidgets.QGroupBox("2 - Run")
        run = QtWidgets.QHBoxLayout(run_box)
        run.addWidget(QtWidgets.QLabel("Cards (N)"))
        self.count_spin = QtWidgets.QSpinBox()
        self.count_spin.setRange(1, 999)
        self.count_spin.setValue(max(1, int(self.settings.run_count or 10)))
        self.count_spin.setFixedWidth(90)
        run.addWidget(self.count_spin)
        run.addStretch(1)
        self.start_button = QtWidgets.QPushButton("Start")
        self.start_button.setObjectName("primary")
        self.start_button.setFixedWidth(110)
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(lambda: self._start())
        self.stop_button = QtWidgets.QPushButton("Stop")
        self.stop_button.setObjectName("danger")
        self.stop_button.setFixedWidth(110)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(lambda: self._stop())
        run.addWidget(self.start_button)
        run.addWidget(self.stop_button)
        root.addWidget(run_box)

        sheet_box = QtWidgets.QGroupBox("3 - Google Sheet (optional)")
        sheet = QtWidgets.QGridLayout(sheet_box)
        self.sheet_url = QtWidgets.QLineEdit(self.settings.google_sheet_url)
        self.sheet_url.setPlaceholderText("https://docs.google.com/spreadsheets/d/...  (your sheet's link)")
        self.key_label = QtWidgets.QLabel()
        self.key_label.setWordWrap(True)
        self.key_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.key_button = QtWidgets.QPushButton("Choose key file...")
        self.key_button.clicked.connect(self._choose_key_file)
        self.copy_email_button = QtWidgets.QPushButton("Copy email")
        self.copy_email_button.clicked.connect(self._copy_robot_email)
        self.sheet_secret = QtWidgets.QLineEdit(self.settings.google_sheet_secret)
        self.sheet_secret.setPlaceholderText("only for an Apps Script .../exec URL - leave empty for a sheet link")
        self.sheet_secret.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.sheet_save_button = QtWidgets.QPushButton("Save")
        self.sheet_save_button.clicked.connect(self._save_sheet)
        self.sheet_test_button = QtWidgets.QPushButton("Test")
        self.sheet_test_button.clicked.connect(self._test_sheet)
        self.sheet_status = QtWidgets.QLabel()
        self.sheet_status.setObjectName("hint")
        self.sheet_status.setWordWrap(True)
        sheet.addWidget(QtWidgets.QLabel("Sheet link"), 0, 0)
        sheet.addWidget(self.sheet_url, 0, 1, 1, 3)
        sheet.addWidget(QtWidgets.QLabel("Robot account"), 1, 0)
        sheet.addWidget(self.key_label, 1, 1)
        sheet.addWidget(self.key_button, 1, 2)
        sheet.addWidget(self.copy_email_button, 1, 3)
        sheet.addWidget(QtWidgets.QLabel("Secret"), 2, 0)
        sheet.addWidget(self.sheet_secret, 2, 1)
        sheet.addWidget(self.sheet_save_button, 2, 2)
        sheet.addWidget(self.sheet_test_button, 2, 3)
        sheet.addWidget(self.sheet_status, 3, 1, 1, 3)
        sheet.setColumnStretch(1, 1)
        root.addWidget(sheet_box)
        self._show_key()
        self._show_sheet_status()

        kiasa_box = QtWidgets.QGroupBox("4 - KIASA (optional)")
        box = QtWidgets.QGridLayout(kiasa_box)
        self.kiasa_code = QtWidgets.QLineEdit(self.settings.kiasa_code)
        self.kiasa_code.setPlaceholderText("KIASA-BOT1....  (from KIASA: Job desk > Jobs > Jobright bot > Connect a computer)")
        self.kiasa_code.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.kiasa_connect_button = QtWidgets.QPushButton("Connect")
        self.kiasa_connect_button.clicked.connect(lambda: self._connect_kiasa(self.kiasa_code.text()))
        self.kiasa_disconnect_button = QtWidgets.QPushButton("Disconnect")
        self.kiasa_disconnect_button.clicked.connect(self._disconnect_kiasa)
        self.kiasa_status_label = QtWidgets.QLabel()
        self.kiasa_status_label.setWordWrap(True)
        self.autostart_box = QtWidgets.QCheckBox("Start with Windows and keep running in the tray")
        self.autostart_box.setToolTip("Starts when you sign in to Windows, starts again within 10 minutes if it "
                                      "ever stops, and keeps the computer awake while connected to KIASA.")
        self.autostart_box.setChecked(winstart.autostart_enabled())
        self.autostart_box.toggled.connect(self._set_autostart)
        box.addWidget(QtWidgets.QLabel("Code"), 0, 0)
        box.addWidget(self.kiasa_code, 0, 1)
        box.addWidget(self.kiasa_connect_button, 0, 2)
        box.addWidget(self.kiasa_disconnect_button, 0, 3)
        box.addWidget(self.kiasa_status_label, 1, 1, 1, 3)
        box.addWidget(self.autostart_box, 2, 1, 1, 3)
        box.setColumnStretch(1, 1)
        root.addWidget(kiasa_box)
        self._show_kiasa_status("Off. Each saved job is also posted to KIASA's job list once you connect, "
                                "and KIASA's admins can start, stop and schedule runs.", "off")

        self.counts_label = QtWidgets.QLabel()
        self.counts_label.setObjectName("counts")
        root.addWidget(self.counts_label)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setValue(0)
        self.progress.setFormat("idle")
        root.addWidget(self.progress)

        self.log_view = QtWidgets.QTextEdit()
        self.log_view.setReadOnly(True)
        root.addWidget(self.log_view, 1)

        footer = QtWidgets.QHBoxLayout()
        clear = QtWidgets.QPushButton("Clear log")
        clear.clicked.connect(self.log_view.clear)
        footer.addStretch(1)
        footer.addWidget(clear)
        root.addLayout(footer)

    # -- logging -----------------------------------------------------------

    @QtCore.Slot(str, str)
    def append_log(self, message: str, level: str = "info"):
        color = LOG_COLORS.get(level, LOG_COLORS["info"])
        stamp = time.strftime("%H:%M:%S")
        safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.log_view.append(
            f'<span style="color:#484f58">{stamp}</span> <span style="color:{color}">{safe}</span>'
        )
        bar = self.log_view.verticalScrollBar()
        bar.setValue(bar.maximum())

    @QtCore.Slot(dict)
    def _update_counts(self, stats: dict):
        self.counts_label.setText(
            f"<span style='color:#3fb950'>Saved {stats.get('saved', 0)}</span> &nbsp;·&nbsp; "
            f"<span style='color:#58a6ff'>Removed {stats.get('removed', 0)}</span> &nbsp;·&nbsp; "
            f"<span style='color:#d29922'>Skipped {stats.get('skipped', 0)}</span> &nbsp;·&nbsp; "
            f"<span style='color:#f85149'>Failed {stats.get('failed', 0)}</span>"
        )

    # -- chrome status -----------------------------------------------------

    def _update_chrome_status(self):
        """Ask about the browser on a thread: a closed port takes ~2s to fail."""
        if self._status_checking or self._closing:
            return
        self._status_checking = True
        port = self.settings.debug_port

        def ask():
            try:
                answer = {"port": port, "live": chrome_mod.devtools_version(port)}
            except Exception:  # noqa: BLE001 - shown as "not running"
                answer = {"port": port, "live": None}
            try:
                self.status_ready.emit(answer)
            except RuntimeError:
                pass  # the window went away

        threading.Thread(target=ask, daemon=True, name="chrome-status").start()

    @QtCore.Slot(dict)
    def _show_chrome_status(self, answer: dict):
        self._status_checking = False
        if self._closing:
            return
        live = answer.get("live")
        self._chrome_live = bool(live)
        port = answer.get("port")
        if live:
            text, color = f"Running - {live.get('Browser', 'Chrome')} on port {port}", "#3fb950"
        else:
            text, color = f"Not running. Press 'Open Chrome' (port {port}).", "#d29922"
        self.chrome_status.setText(text)
        self.chrome_status.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.start_button.setEnabled(self._chrome_live and self._thread is None)

    # -- background jobs -----------------------------------------------------

    def _run_background(self, job, finished, buttons=(), failed=None):
        for button in buttons:
            button.setEnabled(False)
        worker = _Worker(job)
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self.append_log)

        def cleanup():
            thread.quit()
            thread.wait(5000)
            for button in buttons:
                button.setEnabled(True)
            if (thread, worker) in self._bg:
                self._bg.remove((thread, worker))
            self._update_chrome_status()

        def on_done(result):
            try:
                finished(result)
            finally:
                cleanup()

        def on_failed(message):
            self.append_log(message, "error")
            try:
                if failed:
                    failed(message)
            finally:
                cleanup()

        done_relay = _OnUiThread(on_done, self)
        failed_relay = _OnUiThread(on_failed, self)
        worker.done.connect(done_relay.call)
        worker.failed.connect(failed_relay.call)
        self._bg.append((thread, worker))
        thread.start()

    def _open_chrome(self, then=None):
        """Open the bot's Chrome; `then(True)` once it is up, `then(False)` if it did not open."""
        then = then or (lambda ok: None)
        chrome_path = self.settings.chrome_path or chrome_mod.find_chrome()
        if not chrome_path:
            self.append_log("Could not find chrome.exe - set chrome_path in settings.json.", "error")
            then(False)
            return
        port = self.settings.debug_port
        profile_dir = Path(self.settings.profile_dir)
        extension_dir = self.settings.extension_dir
        url = self.settings.jobright_url
        self.append_log(f"Starting Chrome on port {port} with profile {profile_dir}", "step")

        def job(log):
            chrome_mod.launch(chrome_path, profile_dir, port, url, extension_dir)
            info = chrome_mod.wait_for_devtools(port)
            found = ""
            try:
                from playwright.sync_api import sync_playwright

                with sync_playwright() as pw:
                    browser = chrome_mod.connect_owned(pw, port, profile_dir)
                    context = browser.contexts[0]
                    found = find_extension_id(context, profile_dir, timeout_ms=8000)
            except ExtensionNotFound:
                found = ""
            except Exception as exc:  # noqa: BLE001 - reported, not fatal
                log(f"Could not check the extension: {exc}", "warn")
                found = "?"
            return info.get("Browser", "Chrome"), found

        def finished(result):
            browser, found = result
            self.append_log(f"Chrome is up ({browser}).", "ok")
            if found and found != "?":
                self.append_log(f"Job Intelligence extension loaded ({found}).", "ok")
            elif not found:
                self.append_log("The Job Intelligence extension is not loaded in the bot's Chrome.", "error")
                self.append_log(load_instructions(extension_dir), "warn")
            self.append_log(
                "First time? Sign in to Jobright in that window (once - the profile keeps it), "
                "open Recommended jobs, then press Start.", "info")
            self._chrome_live = True
            then(True)

        self._run_background(job, finished, buttons=[self.open_button], failed=lambda message: then(False))

    def _show_extension_folder(self):
        folder = self.settings.extension_dir
        if not chrome_mod.extension_is_built(folder):
            self.append_log(f"No extension build at {folder} - the 'extension' folder next to app.py is missing.",
                            "error")
            return
        QtWidgets.QApplication.clipboard().setText(str(folder))
        if sys.platform == "win32":
            os.startfile(folder)  # noqa: S606 - opens Explorer on our own folder
        self.append_log(f"Extension folder (path copied): {folder}", "info")
        self.append_log(load_instructions(folder), "info")

    # -- google sheet --------------------------------------------------------

    def _key_file(self) -> Path:
        return sheets.key_file_path(self.settings.google_key_file)

    def _robot_email(self) -> str:
        """The service account's email, or "" when there is no usable key file."""
        try:
            return sheets.key_email(self._key_file())
        except ValueError:
            return ""

    def _show_key(self):
        email = self._robot_email()
        if email:
            self.key_label.setText(f"Share your sheet (Editor) with:  {email}")
            self.key_label.setStyleSheet("color: #c9d1d9; font-size: 11px;")
        else:
            self.key_label.setText("No key file yet - needed to edit a sheet by its link (google-sheets/README.md).")
            self.key_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.copy_email_button.setEnabled(bool(email))

    def _show_sheet_status(self, text: str = "", color: str = "#8b949e"):
        url = self.settings.google_sheet_url
        if not text:
            waiting = len(sheets.SheetLogger(url).pending()) if url else 0
            if not url:
                text = "Off - saved jobs go only to your board."
            elif sheets.is_sheet_link(url) and not self._robot_email():
                text, color = "On, but there is no key file: choose one, or the rows only wait.", "#d29922"
            else:
                text = "On - each saved job is added to the sheet's 'Saved jobs' tab."
            if waiting:
                text += f" {waiting} row(s) waiting to be sent."
        self.sheet_status.setText(text)
        self.sheet_status.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _choose_key_file(self):
        picked, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "The service account's key file (JSON)", str(Path.home() / "Downloads"), "Key file (*.json)")
        if not picked:
            return
        try:
            email = sheets.key_email(picked)
        except ValueError as exc:
            self.append_log(f"Not used: {exc}", "error")
            return
        target = sheets.default_key_file()
        try:  # next to app.py: copying the folder to another computer takes it along
            if Path(picked).resolve() != target.resolve():
                shutil.copyfile(picked, target)
            self.settings.google_key_file = ""
        except OSError as exc:  # a read-only folder: use it where it is
            self.append_log(f"Could not copy the key next to app.py ({exc}) - using it from {picked}", "warn")
            self.settings.google_key_file = str(picked)
        self.settings.save()
        self._show_key()
        self._show_sheet_status()
        self.append_log(f"Key file set. Now share your Google Sheet with {email} as Editor "
                        "(the sheet's Share button), paste the sheet's link above and press Test.", "ok")

    def _copy_robot_email(self):
        email = self._robot_email()
        if email:
            QtWidgets.QApplication.clipboard().setText(email)
            self.append_log(f"Copied {email} - paste it in your sheet's Share box, as Editor.", "info")

    def _save_sheet(self) -> bool:
        url = self.sheet_url.text().strip()
        if url and not (sheets.is_sheet_link(url) or sheets.is_web_app(url)):
            self._show_sheet_status("Paste the sheet's link: https://docs.google.com/spreadsheets/d/... "
                                    "(or an Apps Script .../exec URL).", "#f85149")
            return False
        self.settings.google_sheet_url = url
        self.settings.google_sheet_secret = self.sheet_secret.text()
        self.settings.save()
        self.append_log("Google Sheet export " + ("on." if url else "off."), "ok")
        self._show_sheet_status()
        return True

    def _test_sheet(self):
        if not self._save_sheet():
            return
        url, secret = self.settings.google_sheet_url, self.settings.google_sheet_secret
        key_file = self._key_file()
        if not url:
            self._show_sheet_status("Paste your sheet's link first.", "#d29922")
            return
        self._show_sheet_status("Testing...")

        def job(log):
            try:
                return True, sheets.check_connection(url, secret, key_file)
            except Exception as exc:  # noqa: BLE001 - shown in the box
                return False, str(exc).splitlines()[0][:200] if str(exc) else type(exc).__name__

        def finished(result):
            ok, answer = result
            if ok:
                rows = answer.get("rows")
                self._show_sheet_status(f"Connected - tab '{answer.get('sheet', 'Saved jobs')}'"
                                        + (f", {rows} job(s) in it." if rows is not None else "."), "#3fb950")
                self.append_log("Google Sheet test: connected.", "ok")
            else:
                self._show_sheet_status(f"Not connected: {answer}", "#f85149")
                self.append_log(f"Google Sheet test failed: {answer}", "error")

        self._run_background(job, finished, buttons=[self.sheet_test_button])

    def _close_chrome(self):
        port = self.settings.debug_port
        profile_dir = self.settings.profile_dir
        self.append_log(f"Closing the bot's Chrome (port {port})", "step")

        def job(log):
            return chrome_mod.close_bot_chrome(port, profile_dir)

        def finished(closed):
            if closed:
                self.append_log("Chrome closed.", "ok")
            else:
                self.append_log("No bot Chrome to close (or it is not the bot's own).", "warn")

        self._run_background(job, finished, buttons=[self.close_button])

    # -- run ---------------------------------------------------------------

    def _start(self, count: int | None = None, report: kiasa_mod.RunReport | None = None):
        """Start a run: N from the box, or what KIASA asked for (with its report).
        Connected to KIASA, a run started here is reported there too."""
        if self._thread is not None:
            if report:
                report.finish("failed", "The bot was already busy with another run.", wait=0)
            return
        if (self.sheet_url.text().strip() != self.settings.google_sheet_url
                or self.sheet_secret.text() != self.settings.google_sheet_secret) and not self._save_sheet():
            if report:
                report.finish("failed", "The bot's Google Sheet setting needs fixing on the computer.", wait=0)
            return
        if count is None:
            count = self.count_spin.value()
            self.settings.run_count = count
            self.settings.save()
            if self._remote is not None:
                report = self._remote.begin(None, count)
        self._report = report
        self._stop_from_kiasa = False
        self._trouble = None
        self._update_counts({})
        self.progress.setMaximum(count)
        self.progress.setValue(0)
        self.progress.setFormat("%v / %m")
        self._start_time = time.monotonic()
        self.append_log(f"Run started - {count} card(s)", "step")

        worker = RunWorker(self.settings, count, on_saved=self._saved_for_kiasa if self._outbox else None)
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self.append_log)
        worker.stats.connect(self._update_counts)
        worker.progress.connect(self._update_progress)
        worker.done.connect(self._run_finished)
        worker.failed.connect(self._run_failed)
        if report:
            worker.log.connect(report.line)
            worker.stats.connect(report.stats)
        self._thread = thread
        self._run_worker = worker
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.open_button.setEnabled(False)
        self.close_button.setEnabled(False)
        thread.start()

    def _saved_for_kiasa(self, row: dict):
        """A saved job, on its way to KIASA (called on the run's thread)."""
        outbox, report = self._outbox, self._report
        if outbox is not None:
            outbox.add(kiasa_mod.job_for_kiasa(row, report.run_id if report else None))

    def _stop(self, from_kiasa: bool = False):
        if self._run_worker:
            self._stop_from_kiasa = from_kiasa
            self.append_log("Stopped from KIASA - stopping at the current step..." if from_kiasa
                            else "Stopping at the current step...", "warn")
            self._run_worker.request_stop()
            self.stop_button.setEnabled(False)

    @QtCore.Slot(int, int)
    def _update_progress(self, done: int, total: int):
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(done)

    @QtCore.Slot(dict)
    def _run_finished(self, stats: dict):
        elapsed = time.monotonic() - self._start_time
        self._update_counts(stats)
        self.append_log(
            "Run finished - {saved} saved, {removed} removed, {skipped} skipped, {failed} failed "
            "in {mins:.0f}m {secs:02.0f}s".format(mins=elapsed // 60, secs=elapsed % 60, **stats),
            "ok",
        )
        reason = self._run_worker.runner.stopped_reason if self._run_worker else ""
        if self._report:
            self._report.stats(stats)
            if reason == "stopped by the user":
                self._report.finish("stopped", "Stopped from KIASA." if self._stop_from_kiasa
                                    else "Stopped on the computer.", wait=0)
            else:
                self._report.finish("done", f"Ended: {reason}." if reason else "", wait=0)
        self._report = None
        self._teardown_thread()
        self._show_sheet_status()

    @QtCore.Slot(str)
    def _run_failed(self, message: str):
        self.append_log(f"Run failed: {message}", "error")
        if "not signed in" in message:
            self._trouble = ("sign_in", "Jobright wants signing in again in the bot's Chrome.")
        elif "extension" in message:
            self._trouble = ("setup", "The Job Intelligence extension needs a hand on the computer: "
                                      "see Job Saving Bot's log there.")
        elif self._run_worker is not None:
            self._trouble = ("error", f"The last run failed: {message}"[:300])
        if self._report:
            if self._run_worker:
                self._report.stats(self._run_worker.runner.stats.as_dict())
            self._report.finish("failed", message[:300], wait=0)
        self._report = None
        self._teardown_thread()

    def _teardown_thread(self):
        if self._thread:
            self._thread.quit()
            self._thread.wait(5000)
        self._thread = None
        self._run_worker = None
        self.progress.setFormat("idle")
        self.stop_button.setEnabled(False)
        self.open_button.setEnabled(True)
        self.close_button.setEnabled(True)
        self._update_chrome_status()

    # -- KIASA ---------------------------------------------------------------

    def _connect_kiasa(self, code: str):
        """Connect with a code from KIASA (or the saved one, at start)."""
        try:
            connection = kiasa_mod.parse_code(code)
        except ValueError as exc:
            self._show_kiasa_status(str(exc), "error")
            return
        self._drop_kiasa()
        code = "".join(code.split())
        if code != self.settings.kiasa_code:
            self.settings.kiasa_code = code
            self.settings.save()
        self.kiasa_code.setText(code)
        client = kiasa_mod.KiasaClient(connection)
        self._outbox = kiasa_mod.KiasaOutbox(client, log=self.kiasa_log.emit)
        self._outbox.start()  # also sends jobs an earlier run left behind
        self._remote = kiasa_mod.RemoteControl(
            client, status=self._kiasa_state, log=self.kiasa_log.emit,
            on_run=self.kiasa_run.emit, on_status=self.kiasa_status.emit, on_stop=self.kiasa_stop.emit,
        ).start()
        winstart.keep_awake(True)
        self._show_kiasa_status("Connecting to KIASA...", "off")

    def _drop_kiasa(self):
        if self._remote is not None:
            self._remote.close()
        if self._outbox is not None:
            self._outbox.close(timeout=3.0)
        self._remote = None
        self._outbox = None
        winstart.keep_awake(False)

    def _disconnect_kiasa(self):
        self._drop_kiasa()
        self.settings.kiasa_code = ""
        self.settings.save()
        self.kiasa_code.clear()
        if self.autostart_box.isChecked():
            self.autostart_box.setChecked(False)  # nothing to stay ready for
        self._show_kiasa_status("Disconnected. Saved jobs are no longer posted to KIASA, and KIASA cannot "
                                "start runs here.", "off")
        self.append_log("Disconnected from KIASA.", "warn")

    def _kiasa_state(self) -> dict:
        """How the bot is, for KIASA's admins (asked from the check-in thread)."""
        if self._thread is not None or self._opening_for_run:
            return {"state": "busy", "detail": ""}
        if self._trouble:
            state, detail = self._trouble
            return {"state": state, "detail": detail}
        return {"state": "ready", "detail": "" if self._chrome_live else "Chrome opens when a run starts."}

    @QtCore.Slot(str, str)
    def _show_kiasa_status(self, text: str, tone: str):
        colors = {"ok": "#3fb950", "warn": "#d29922", "error": "#f85149"}
        self.kiasa_status_label.setText(text)
        self.kiasa_status_label.setStyleSheet(f"color: {colors.get(tone, '#8b949e')}; font-size: 11px;")
        self.kiasa_disconnect_button.setEnabled(bool(self.settings.kiasa_code))
        if tone == "error" and self._remote is not None and "no longer knows" in text:
            self.append_log(text, "error")

    @QtCore.Slot(object, object)
    def _kiasa_run(self, run: dict, report: kiasa_mod.RunReport):
        """A run KIASA asked for: open Chrome first if it is closed, then go."""
        cards = max(1, int(run.get("cards") or 1))
        origin = {"schedule": "on schedule", "admin": "by an admin"}.get(run.get("origin"), "")
        self.append_log(f"KIASA asks for a run of {cards} card(s) {origin}".strip(), "step")
        if self._thread is not None or self._opening_for_run:
            report.finish("failed", "The bot was already busy with another run.", wait=0)
            return
        if self._chrome_live:
            self._start(cards, report)
            return
        self._opening_for_run = True
        report.line("Opening the bot's Chrome", "step")

        def opened(ok: bool):
            self._opening_for_run = False
            if ok:
                # After the opening job has tidied up its buttons.
                QtCore.QTimer.singleShot(1500, lambda: self._start(cards, report))
            else:
                report.finish("failed", "Chrome could not be opened on the computer.", wait=0)

        self._open_chrome(then=opened)

    def _set_autostart(self, on: bool):
        problem = winstart.set_autostart(on)
        if problem:
            self.append_log(f"Start with Windows: {problem}", "error")
            self.autostart_box.blockSignals(True)
            self.autostart_box.setChecked(winstart.autostart_enabled())
            self.autostart_box.blockSignals(False)
            return
        self.append_log("Starts with Windows (in the tray), and again within 10 minutes if it ever stops."
                        if on else "No longer starts with Windows.", "ok")

    # -- the tray ------------------------------------------------------------

    def _make_tray(self):
        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = QtGui.QIcon(str(APP_DIR / "extension" / "icons" / "icon-32.png"))
        self.setWindowIcon(icon)
        self._tray = QtWidgets.QSystemTrayIcon(icon, self)
        self._tray.setToolTip(f"Job Saving Bot {__version__}")
        menu = QtWidgets.QMenu(self)
        menu.addAction("Open Job Saving Bot", self.bring_up)
        menu.addSeparator()
        menu.addAction("Quit", self.quit_for_good)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(lambda reason: self.bring_up()
                                     if reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger else None)
        self._tray.show()

    def bring_up(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_for_good(self):
        self._quitting = True
        self.close()

    def closeEvent(self, event):  # noqa: N802 - Qt API
        # Connected to KIASA, closing the window leaves the bot in the tray, ready.
        if self._remote is not None and self._tray is not None and not self._quitting:
            event.ignore()
            self.hide()
            if not self._told_tray:
                self._tray.showMessage("Job Saving Bot", "Still running in the tray, ready for KIASA. "
                                       "Right-click the icon to quit.", QtWidgets.QSystemTrayIcon.MessageIcon.Information)
                self._told_tray = True
            return
        self._closing = True
        self._status_timer.stop()
        if self._run_worker is not None:
            self._run_worker.request_stop()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(15000)
        for thread, _ in list(self._bg):
            thread.quit()
            thread.wait(3000)
        self._drop_kiasa()
        if self._tray is not None:
            self._tray.hide()
        super().closeEvent(event)
        QtWidgets.QApplication.quit()


def _single_instance(app: QtWidgets.QApplication, quiet: bool):
    """The one copy of the app for this Windows user: a second one hands over
    (the first shows its window, unless the second was started quietly by
    Windows) and leaves. Returns the server, or None when another copy runs."""
    name = f"JobSavingBot-{os.environ.get('USERNAME') or os.environ.get('USER') or 'user'}"
    other = QtNetwork.QLocalSocket()
    other.connectToServer(name)
    if other.waitForConnected(500):
        other.write(b"quiet" if quiet else b"show")
        other.flush()
        other.waitForBytesWritten(500)
        other.disconnectFromServer()
        return None
    QtNetwork.QLocalServer.removeServer(name)  # left by a copy that crashed
    server = QtNetwork.QLocalServer(app)
    server.listen(name)
    return server


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    background = winstart.BACKGROUND_FLAG in argv
    app = QtWidgets.QApplication([arg for arg in argv if arg != winstart.BACKGROUND_FLAG])
    app.setApplicationName("Job Saving Bot")
    app.setQuitOnLastWindowClosed(False)
    server = _single_instance(app, quiet=background)
    if server is None:
        return 0
    window = MainWindow()

    def knocked():
        while server.hasPendingConnections():
            other = server.nextPendingConnection()
            other.waitForReadyRead(500)
            if bytes(other.readAll().data()) != b"quiet":
                window.bring_up()
            other.disconnectFromServer()

    server.newConnection.connect(knocked)
    # Started by Windows: into the tray, if there is one and KIASA is connected.
    if not (background and window._tray is not None and window._remote is not None):
        window.show()
    return app.exec()
