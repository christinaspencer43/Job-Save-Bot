"""End-to-end test of BotRunner._loop against the mock Jobright list (ported test_loop.py)."""

from __future__ import annotations

import pytest
from conftest import FIXTURE_URL

from jobsavingbot.config import Settings
from jobsavingbot.extension import SaveOutcome
from jobsavingbot.jobright import JobrightPage
from jobsavingbot.runner import BotRunner, StopRequested


class FakeBridge:
    """Stands in for the Job Intelligence extension."""

    def __init__(self, fail_urls=(), local_only=False):
        self.saved = []
        self.fail_urls = fail_urls
        self.local_only = local_only

    def save_job(self, url, timeout=45.0, expect=None):
        self.saved.append(url)
        if any(token in url for token in self.fail_urls):
            return SaveOutcome(False, "Nothing to save - the extension read this page as UNKNOWN.", {}, "NOT_SENT")
        if self.local_only:
            return SaveOutcome(False, "Not saved to the board - Not signed in.",
                               {"saved": True, "synced": False}, "REJECTED")
        company = url.split("company=")[-1].split("&")[0] if "company=" in url else ""
        return SaveOutcome(True, "Saved and synced.", {"saved": True, "synced": True, "jobTitle": "",
                                                       "company": company, "location": "Remote"}, "ACKED")


def build_runner(**overrides):
    settings = Settings(pause_lo=0.05, pause_hi=0.1, page_timeout=8.0, human_mode=False)
    for key, value in overrides.items():
        setattr(settings, key, value)
    lines = []
    runner = BotRunner(settings, log=lambda message, level="info": lines.append(f"[{level}] {message}"))
    return runner, lines


def open_list(context):
    page = context.new_page()
    page.goto(FIXTURE_URL)
    return JobrightPage(page, timeout_ms=8000, human=False)


def job_tabs(context):
    return [p for p in context.pages if "job.html" in (p.url or "")]


def test_all_saves_succeed(context):
    jr = open_list(context)
    runner, lines = build_runner()
    bridge = FakeBridge()

    runner._loop(jr, bridge, context, 5)

    stats = runner.stats
    assert stats.processed == 5
    assert stats.saved == 3, lines  # two autofill cards and one Easy Apply card
    assert stats.removed == 2
    assert stats.failed == 0 and stats.skipped == 0
    assert len(bridge.saved) == 3
    assert all("job.html" in u for u in bridge.saved), "saved the employer posting, not Jobright"
    assert any("Marketplace" in u for u in bridge.saved), "the Easy Apply posting was saved"
    assert jr.top_card() is None, "the list should be empty"
    assert job_tabs(context) == [], "posting tabs must be closed"
    assert jr.page.evaluate("() => window.__companySiteClicks") == 1


def test_run_stops_when_the_list_is_empty(context):
    jr = open_list(context)
    runner, lines = build_runner()
    runner._loop(jr, FakeBridge(), context, 20)
    assert runner.stats.processed == 5
    assert runner.stopped_reason == "the list is empty"
    assert any("No more job cards" in line for line in lines)


def test_count_n_is_respected(context):
    jr = open_list(context)
    runner, _ = build_runner()
    runner._loop(jr, FakeBridge(), context, 2)
    assert runner.stats.processed == 2
    assert runner.stats.saved == 1 and runner.stats.removed == 1
    assert jr.top_card() is not None, "cards beyond N are left alone"


def test_a_failing_card_is_tried_twice_then_skipped(context):
    jr = open_list(context)
    runner, lines = build_runner()
    bridge = FakeBridge(fail_urls=("job.html",))

    runner._loop(jr, bridge, context, 6)

    stats = runner.stats
    assert stats.processed == 6
    assert stats.saved == 0
    assert stats.failed == 4, lines   # CareMetx x2, Ping Identity x2
    assert stats.skipped == 2
    assert stats.removed == 2         # RENFROE and BigRio
    assert len(stats.skipped_signatures) == 2
    body = jr.page.inner_text("#list")
    assert "CareMetx" in body and "Ping Identity" in body, "unsaved jobs stay in the list"
    assert any("will try this card once more" in line for line in lines)
    assert any("skipping this card" in line for line in lines)
    assert any("No, I didn't apply" in line for line in lines)
    assert job_tabs(context) == []


def test_too_many_failures_in_a_row_stop_the_run(context):
    jr = open_list(context)
    runner, lines = build_runner(max_attempts_per_card=10, max_consecutive_failures=3)
    runner._loop(jr, FakeBridge(fail_urls=("job.html",)), context, 10)
    assert runner.stats.processed == 3
    assert runner.stopped_reason == "3 failures in a row"


def test_a_local_only_save_counts_only_when_allowed(context):
    jr = open_list(context)
    runner, _ = build_runner(accept_local_save=True)
    runner._loop(jr, FakeBridge(local_only=True), context, 1)
    assert runner.stats.saved == 1

    jr2 = open_list(context)
    runner2, _ = build_runner()
    runner2._loop(jr2, FakeBridge(local_only=True), context, 1)
    assert runner2.stats.saved == 0 and runner2.stats.failed == 1


def test_stop_is_honoured_mid_run(context):
    jr = open_list(context)
    runner, _ = build_runner()
    original = runner._handle_remove

    def stop_after_first(jr_, top):
        result = original(jr_, top)
        runner.stop_event.set()
        return result

    runner._handle_remove = stop_after_first
    with pytest.raises(StopRequested):
        runner._loop(jr, FakeBridge(), context, 10)
    assert runner.stats.processed < 10
    assert runner.stopped_reason == "stopped by the user"


def test_saved_cards_are_removed_when_jobright_never_asks(context):
    """Jobright stopped asking "Did you apply?" for many cards: a saved posting's
    card is then removed from the list, not called failed and tried again."""
    page = context.new_page()
    page.goto(FIXTURE_URL + "?noask=1")
    jr = JobrightPage(page, timeout_ms=8000, human=False)
    runner, lines = build_runner()
    bridge = FakeBridge()

    runner._loop(jr, bridge, context, 5)

    stats = runner.stats
    assert stats.saved == 3, lines
    assert stats.removed == 2
    assert stats.failed == 0 and stats.skipped == 0, lines
    assert jr.top_card() is None, "the list should be empty"
    assert sum("Jobright didn't ask" in line for line in lines) == 3
    assert not any("didn't apply" in line.lower() and "answering" in line for line in lines)
    assert job_tabs(context) == []
