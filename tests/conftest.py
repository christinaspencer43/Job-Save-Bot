"""Test isolation for the whole suite.

Every test runs with:
- safe mode on (jobsavingbot.safety): answering Jobright or saving to the
  database against anything but a local page raises instead of happening;
- a temporary LOCALAPPDATA, so no test touches the real settings or profile;
- a network rule on every browser context a test opens: requests to real
  hosts are aborted. Tests only ever use local file:// fixtures.
"""

from __future__ import annotations

import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_REAL_LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
if _REAL_LOCALAPPDATA and "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(pathlib.Path(_REAL_LOCALAPPDATA) / "ms-playwright")
os.environ["JOBSAVINGBOT_SAFE_MODE"] = "1"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from playwright.sync_api import Browser  # noqa: E402

from jobsavingbot import safety  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parent
FIXTURE_URL = (FIXTURES / "fixture.html").as_uri()


def _deny_real_hosts(route):
    if safety.is_sandbox(route.request.url):
        route.fallback()
    else:
        route.abort("blockedbyclient")


_original_new_context = Browser.new_context
_original_new_page = Browser.new_page


def _new_context(self, *args, **kwargs):
    context = _original_new_context(self, *args, **kwargs)
    context.route("**/*", _deny_real_hosts)
    return context


def _new_page(self, *args, **kwargs):
    page = _original_new_page(self, *args, **kwargs)
    page.context.route("**/*", _deny_real_hosts)
    return page


Browser.new_context = _new_context
Browser.new_page = _new_page


@pytest.fixture(autouse=True)
def isolated_app_data(tmp_path, monkeypatch):
    app_data = tmp_path / "LocalAppData"
    app_data.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(app_data))
    monkeypatch.setenv("JOBSAVINGBOT_SAFE_MODE", "1")
    safety.set_safe_mode(None)
    safety.clear_audit()
    yield app_data
    safety.set_safe_mode(None)


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        instance = pw.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture()
def context(browser):
    ctx = browser.new_context(viewport={"width": 1500, "height": 950})
    yield ctx
    ctx.close()
