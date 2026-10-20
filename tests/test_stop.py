"""Stop ends the run without claiming success (ported from test_stop_cancel.py)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from jobsavingbot.jobright import APPLY_NOW
from jobsavingbot.runner import BotRunner, StopRequested


class FakeJobright:
    """The Jobright tab, reduced to what the loop asks of it."""

    def __init__(self):
        self.page = SimpleNamespace(bring_to_front=lambda: None,
                                    mouse=SimpleNamespace(wheel=lambda *a: None))
        self.cards_read = 0

    def modal_is_open(self):
        return False

    def close_any_dialog(self):
        return True

    def top_card(self, skip=None):
        self.cards_read += 1
        return SimpleNamespace(kind=APPLY_NOW, title=f"Card {self.cards_read}",
                               signature=f"sig-{self.cards_read}")


def _runner():
    settings = SimpleNamespace(pause_lo=0.01, pause_hi=0.02, focus_browser=True)
    return BotRunner(settings, log=lambda *a: None)


def test_stop_between_cards_reads_no_further_card(monkeypatch):
    bot, jr, handled = _runner(), FakeJobright(), []

    def handle(jr_, top):
        handled.append(top.title)
        bot.stop_event.set()  # Stop pressed while this card is handled
        return True

    monkeypatch.setattr(bot, "_handle_remove", handle)
    with pytest.raises(StopRequested):
        bot._loop(jr, None, None, 5)
    assert handled == ["Card 1"]
    assert jr.cards_read == 1
    assert bot.stats.processed == 1 and bot.stats.saved == 0


def test_stop_in_the_middle_of_a_card_does_not_count_it(monkeypatch):
    bot, jr = _runner(), FakeJobright()

    def handle(jr_, top):
        bot.stop_event.set()
        bot._pause()  # the next wait inside the card notices Stop
        raise AssertionError("work continued after Stop")

    monkeypatch.setattr(bot, "_handle_remove", handle)
    with pytest.raises(StopRequested):
        bot._loop(jr, None, None, 5)
    assert bot.stats.processed == 0 and bot.stats.failed == 0
    assert jr.cards_read == 1


def test_a_saved_card_is_finished_even_if_stop_arrives(monkeypatch):
    """Once the posting is saved, the pause before answering Jobright ignores Stop."""
    bot = _runner()
    bot.stop_event.set()
    bot._pause(0.1, interruptible=False)  # must not raise
    with pytest.raises(StopRequested):
        bot._pause(0.1)
