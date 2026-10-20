"""Extension discovery, the save script and reading its reply (ported tests)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from jobsavingbot import safety
from jobsavingbot.extension import (
    SAVE_SCRIPT,
    ExtensionBridge,
    ExtensionNotFound,
    find_extension_id,
    load_instructions,
    save_outcome_of,
)

OURS = "pcemejcdbfcieeonenklibinbgmecidj"
COMPONENT = "glbjnfimcajjenihimblfaponejbkoph"


class FakeContext:
    def __init__(self, workers):
        self.service_workers = [SimpleNamespace(url=f"chrome-extension://{w}/background.js") for w in workers]
        self.pages = []

    def new_page(self):
        raise RuntimeError("no chrome://extensions in this fake")


def _profile(tmp_path, with_ours=True):
    unpacked = tmp_path / "unpacked"
    unpacked.mkdir()
    (unpacked / "manifest.json").write_text(json.dumps({"name": "Job Intelligence — Posting & Application Extractor"}))
    settings = {COMPONENT: {"location": 5, "manifest": {"name": "Chromium component"}}}
    if with_ours:
        settings[OURS] = {"path": str(unpacked), "location": 4, "manifest": {}}
    (tmp_path / "Default").mkdir()
    (tmp_path / "Default" / "Secure Preferences").write_text(json.dumps({"extensions": {"settings": settings}}))
    return tmp_path


def test_a_listed_component_extension_is_not_taken_for_ours(tmp_path):
    profile = _profile(tmp_path)
    assert find_extension_id(FakeContext([COMPONENT, OURS]), profile, timeout_ms=500) == OURS


def test_an_unidentified_extension_is_never_used(tmp_path):
    profile = _profile(tmp_path, with_ours=False)
    with pytest.raises(ExtensionNotFound):
        find_extension_id(FakeContext([COMPONENT]), profile, timeout_ms=500)


def test_load_instructions_name_the_folder():
    text = load_instructions(r"D:\x\dist\chrome")
    assert "Load unpacked" in text and r"D:\x\dist\chrome" in text and "Developer mode" in text


# -- the save reply ------------------------------------------------------------

def _done(**extra):
    return {"stage": "done", "pageType": "JOB_LISTING", "saved": True, **extra}


def test_an_acknowledged_save_is_saved():
    outcome = save_outcome_of(_done(synced=True, fingerprint="fp-1"))
    assert (outcome.ok, outcome.state, outcome.fingerprint) == (True, "ACKED", "fp-1")


def test_an_existing_entry_is_saved():
    outcome = save_outcome_of(_done(synced=True, existing={"where": "remote"}))
    assert outcome.ok and "Already" in outcome.message


def test_a_save_kept_only_in_the_extension_is_not_saved():
    outcome = save_outcome_of(_done(synced=False, error="Not signed in.", syncFailure="rejected"))
    assert not outcome.ok and outcome.local_only


def test_no_answer_from_the_database_is_uncertain():
    outcome = save_outcome_of(_done(synced=False, error="Failed to fetch", syncFailure="unreachable"))
    assert (outcome.ok, outcome.state) == (False, "UNCERTAIN")


def test_nothing_to_save_is_not_saved():
    outcome = save_outcome_of({"stage": "done", "saved": False, "pageType": "UNKNOWN"})
    assert (outcome.ok, outcome.state) == (False, "NOT_SENT")


def test_two_tabs_on_one_address_are_not_guessed_between():
    outcome = save_outcome_of({"stage": "tabs", "error": "tab-ambiguous", "count": 2})
    assert (outcome.ok, outcome.state) == (False, "NOT_SENT")


# -- the save script, against a stand-in chrome.* ----------------------------------

FAKE_EXTENSION = """
() => {
  window.__sent = [];
  const tabs = [
    {id: 1, url: "https://careers.example/jobs/1"},
    {id: 2, url: "https://careers.example/jobs/2?gh_src=abc"},
  ];
  let scans = 0;
  window.chrome = {
    runtime: {
      lastError: null,
      sendMessage: (msg, done) => {
        window.__sent.push(msg.type + ':' + msg.payload.tabId);
        if (msg.type === "ui/rescan") { scans += 1; done({ok: true}); return; }
        if (msg.type === "ui/get-tab-state") {
          done({ok: true, data: {url: tabs[msg.payload.tabId - 1].url,
                classification: {pageType: scans ? "JOB_LISTING" : "UNKNOWN"}}});
          return;
        }
        if (msg.type === "ui/save-job") {
          done({ok: true, data: {saved: true, synced: true, fingerprint: "fp-" + msg.payload.tabId}});
        }
      },
    },
    tabs: {query: (_q, done) => done(tabs)},
  };
}
"""


def test_the_save_script_uses_the_three_messages_on_the_right_tab(browser):
    page = browser.new_page()
    page.evaluate(FAKE_EXTENSION)
    got = page.evaluate(SAVE_SCRIPT, {"jobUrl": "https://careers.example/jobs/2?gh_src=abc#top",
                                      "settleMs": 10, "expect": None})
    sent = page.evaluate("() => window.__sent")
    page.close()
    assert got["stage"] == "done" and got["saved"] and got["synced"], got
    assert got["tabId"] == 2
    assert sent[0] == "ui/get-tab-state:2"
    assert "ui/rescan:2" in sent and sent[-1] == "ui/save-job:2"
    assert save_outcome_of(got).ok


def test_the_bridge_save_is_guarded_in_safe_mode():
    bridge = ExtensionBridge(context=None, extension_id=OURS)
    with pytest.raises(safety.ExternalActionBlocked):
        bridge.save_job("https://careers.example/jobs/1")
