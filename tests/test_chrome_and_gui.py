"""Chrome launch flags, port rules, settings, and a GUI smoke check."""

from __future__ import annotations

import json
import os

import pytest

from jobsavingbot import chrome
from jobsavingbot.config import DEFAULT_PORT, Settings, check_port, settings_path


def test_forbidden_ports_are_refused():
    for port in (9222, 9333):
        with pytest.raises(ValueError):
            check_port(port)
        with pytest.raises(ValueError):
            chrome.devtools_version(port)
        with pytest.raises(ValueError):
            chrome.launch_args("chrome.exe", "C:/p", port)
    assert check_port(9444) == 9444


def test_settings_default_to_port_9444_and_own_profile(isolated_app_data):
    settings = Settings.load()
    assert settings.debug_port == DEFAULT_PORT == 9444
    assert settings.profile_dir == str(isolated_app_data / "JobSavingBot" / "chrome-profile")
    assert settings_path().is_file()


def test_a_forbidden_port_in_settings_falls_back_to_9444(isolated_app_data):
    settings_path().write_text(json.dumps({"debug_port": 9222, "run_count": 7}), encoding="utf-8")
    settings = Settings.load()
    assert settings.debug_port == 9444 and settings.run_count == 7


def test_launch_args_load_the_extension_when_it_is_built(tmp_path):
    ext = tmp_path / "dist" / "chrome"
    ext.mkdir(parents=True)
    args = chrome.launch_args("chrome.exe", tmp_path / "profile", 9444, "https://jobright.ai/jobs/recommend", ext)
    assert "--remote-debugging-port=9444" in args
    assert f"--user-data-dir={tmp_path / 'profile'}" in args
    assert not any(a.startswith("--load-extension") for a in args), "no manifest yet -> no flag"

    (ext / "manifest.json").write_text("{}")
    args = chrome.launch_args("chrome.exe", tmp_path / "profile", 9444, "https://jobright.ai/jobs/recommend", ext)
    assert f"--load-extension={ext}" in args
    assert "--disable-features=DisableLoadExtensionCommandLineSwitch" in args
    assert args[-1] == "https://jobright.ai/jobs/recommend"


def test_user_data_dir_is_read_however_windows_quoted_it():
    assert chrome.user_data_dir_of('chrome.exe "--user-data-dir=C:\\a b\\p" --x') == "C:\\a b\\p"
    assert chrome.user_data_dir_of('chrome.exe --user-data-dir="C:\\a b\\p" --x') == "C:\\a b\\p"
    assert chrome.user_data_dir_of("chrome.exe --user-data-dir=C:\\p --x") == "C:\\p"


def test_only_the_bots_own_browser_is_attached(tmp_path):
    ours = [{"address": "127.0.0.1", "pid": 1, "command_line": f'chrome.exe "--user-data-dir={tmp_path}"'}]
    assert chrome.check_owned(9444, tmp_path, listeners=ours)["checked"]
    other = [{"address": "127.0.0.1", "pid": 1, "command_line": "chrome.exe --user-data-dir=C:\\other"}]
    with pytest.raises(chrome.BrowserNotOwned):
        chrome.check_owned(9444, tmp_path, listeners=other)
    exposed = [{"address": "0.0.0.0", "pid": 1, "command_line": f'chrome.exe "--user-data-dir={tmp_path}"'}]
    with pytest.raises(chrome.BrowserNotOwned):
        chrome.check_owned(9444, tmp_path, listeners=exposed)


def test_the_window_constructs_offscreen():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtWidgets

    from jobsavingbot.gui import MainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(poll=False)
    window.show()
    app.processEvents()
    assert window.windowTitle() == "Job Saving Bot"
    assert window.start_button.text() == "Start" and not window.start_button.isEnabled()
    assert window.stop_button.text() == "Stop" and not window.stop_button.isEnabled()
    assert window.open_button.text() == "Open Chrome"
    window._update_counts({"saved": 3, "removed": 2, "skipped": 1, "failed": 4})
    text = window.counts_label.text()
    assert "Saved 3" in text and "Removed 2" in text and "Skipped 1" in text and "Failed 4" in text
    window.append_log("hello <world>", "ok")
    assert "hello <world>" in window.log_view.toPlainText()
    window.close()
