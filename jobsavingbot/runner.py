"""The Jobright save loop.

One iteration handles the top card of the Jobright Recommended list:

  APPLY WITH AUTOFILL -> click it, Ctrl+click "No, Apply Manually" so the real
  posting opens in a background tab, save that tab through the Job
  Intelligence (Job JD Scanner) extension, close the tab, then answer
  "Yes, I applied!".

  EASY APPLY -> click it, press the panel's company-site button, save the
  employer's posting through the extension, close that tab, then answer
  Jobright's "Yes, I applied!" the same way.

  APPLY NOW -> open the card's "..." menu and click "Remove From List".

Either way the card leaves the list and the next one moves up.

Ported from Job Save Bot's jobsavebot/runner.py (BotRunner.run -> _loop,
_handle_autofill, _handle_easy_apply, _handle_remove and their tab waits,
with the same timings). The Stage 04 capture/identity store was dropped: the
posting is saved with the extension's own Save message, as originally.
Added: a card that fails is tried once more and then skipped for the rest of
the run; the run stops after N cards, when the list is empty, or after too
many failures in a row.
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import chrome as chrome_mod
from .config import check_port
from .extension import SITE_ACCESS_HELP, ExtensionBridge, ExtensionNotFound, find_extension_id, load_instructions
from .jobright import AUTOFILL, EASY_APPLY, JobrightPage
from .sheets import SheetLogger, make_row

# Browser surfaces that are never a job posting tab.
APP_PREFIXES = ("chrome-extension://", "chrome://", "devtools://")
# A URL the extension could not possibly save.
NON_JOB_PREFIXES = APP_PREFIXES + ("about:",)

KIND_TEXT = {AUTOFILL: "APPLY WITH AUTOFILL", EASY_APPLY: "EASY APPLY"}

# How long a saved card waits for Jobright's "Did you apply?" before it is
# removed from the list instead. Jobright usually asks an Autofill card a few
# seconds after its tab is back in front; an Easy Apply card often never.
AUTOFILL_ASK_WAIT_MS = 10000
EASY_APPLY_ASK_WAIT_MS = 6000


@dataclass
class RunStats:
    saved: int = 0
    removed: int = 0
    skipped: int = 0
    failed: int = 0
    processed: int = 0
    skipped_signatures: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "saved": self.saved,
            "removed": self.removed,
            "skipped": self.skipped,
            "failed": self.failed,
            "processed": self.processed,
        }


class StopRequested(Exception):
    pass


class SetupError(RuntimeError):
    """The run cannot start (no Chrome, no extension, not signed in)."""


class BotRunner:
    """Owns the Playwright session and runs the loop."""

    def __init__(self, settings, log, on_stats=None, on_progress=None):
        self.settings = settings
        self._log = log
        self._on_stats = on_stats or (lambda stats: None)
        self._on_progress = on_progress or (lambda done, total: None)
        self.stop_event = threading.Event()
        self.stats = RunStats()
        self.stopped_reason = ""
        self._attempts: dict[str, int] = {}
        self._browser_cdp = None
        self._target_ids: dict = {}
        self._job_page = None
        self._job_children: list = []
        self._current_card = None
        self.sheet = SheetLogger(self._setting("google_sheet_url", ""), self._setting("google_sheet_secret", ""),
                                 log=self.log, key_file=self._setting("google_key_file", ""))

    # -- helpers -----------------------------------------------------------

    def log(self, message: str, level: str = "info") -> None:
        self._log(message, level)

    def _check_stop(self) -> None:
        if self.stop_event.is_set():
            raise StopRequested()

    def _setting(self, name: str, default):
        return getattr(self.settings, name, default)

    def _pause(self, scale: float = 1.0, interruptible: bool = True) -> None:
        """Human-ish delay; Stop interrupts it unless the card must be finished."""
        low = max(0.05, self.settings.pause_lo * scale)
        high = max(low, self.settings.pause_hi * scale)
        deadline = time.monotonic() + random.uniform(low, high)
        while time.monotonic() < deadline:
            if interruptible:
                self._check_stop()
            time.sleep(0.05)

    def _emit_stats(self) -> None:
        self._on_stats(self.stats.as_dict())

    # -- tab focus ---------------------------------------------------------

    def _activate(self, page) -> None:
        """Show this tab in the bot's Chrome without stealing window focus."""
        if self._setting("focus_browser", False):
            try:
                page.bring_to_front()
            except Exception:
                pass
            return
        try:
            target_id = self._target_id(page)
            if target_id and self._browser_cdp is not None:
                self._browser_cdp.send("Target.activateTarget", {"targetId": target_id})
        except Exception:
            pass

    def _target_id(self, page) -> str:
        cached = self._target_ids.get(page)
        if cached:
            return cached
        try:
            session = page.context.new_cdp_session(page)
            info = session.send("Target.getTargetInfo")
            target_id = info.get("targetInfo", {}).get("targetId", "")
        except Exception:
            target_id = ""
        self._target_ids[page] = target_id
        return target_id

    # -- session -----------------------------------------------------------

    def _find_jobright_page(self, context):
        for page in context.pages:
            if "jobright.ai" in (page.url or ""):
                return page
        page = context.new_page()
        self.log(f"Opening {self.settings.jobright_url}")
        page.goto(self.settings.jobright_url, wait_until="domcontentloaded")
        return page

    def _sign_in_message(self) -> str:
        return ("The Jobright tab is showing a sign-in page. Sign in to Jobright once in "
                "the bot's Chrome window (it stays signed in in this profile), open "
                "Recommended jobs, then press Start again.")

    def run(self, count: int) -> RunStats:
        from playwright.sync_api import sync_playwright

        port = check_port(self.settings.debug_port)
        if not chrome_mod.devtools_version(port):
            raise SetupError(f"No bot Chrome on port {port}. Press 'Open Chrome' first.")

        with sync_playwright() as pw:
            browser = chrome_mod.connect_owned(pw, port, self.settings.profile_dir)
            # Never browser.close() here: on a CDP connection that shuts the
            # bot's Chrome down. Leaving the with-block only disconnects.
            context = browser.contexts[0] if browser.contexts else None
            if context is None:
                raise SetupError("Chrome exposed no browser context.")
            self._target_ids = {}
            try:
                self._browser_cdp = browser.new_browser_cdp_session()
            except Exception:
                self._browser_cdp = None

            try:
                extension_id = find_extension_id(context, Path(self.settings.profile_dir))
            except ExtensionNotFound as exc:
                self.log(str(exc), "error")
                self.log(load_instructions(self._setting("extension_dir", "")), "warn")
                raise SetupError("the Job Intelligence extension is not loaded") from exc
            self.log(f"Extension found ({extension_id})")
            bridge = ExtensionBridge(context, extension_id, lambda m: self.log(m))
            try:
                bridge.open()
                if bridge.has_all_sites() is False:
                    self.log(SITE_ACCESS_HELP, "error")
                    raise SetupError("the extension is not allowed on all sites")
                page = self._find_jobright_page(context)
                self._activate(page)
                jr = JobrightPage(page, int(self.settings.page_timeout * 1000),
                                  human=self._setting("human_mode", True))
                if jr.shows_sign_in():
                    self.log(self._sign_in_message(), "error")
                    raise SetupError("Jobright is not signed in")
                if not jr.wait_for_list():
                    if jr.shows_sign_in():
                        self.log(self._sign_in_message(), "error")
                        raise SetupError("Jobright is not signed in")
                    self.log("Could not see the job list. Make sure the Jobright tab is "
                             "signed in and showing Recommended jobs.", "warn")

                before = jr.applied_count()
                if before is not None:
                    self.log(f"Applied counter before run: {before}")
                if self.sheet.enabled:
                    self.log("Saved jobs also go to the Google Sheet")
                    self.sheet.start()  # also sends rows an earlier run could not
                self._loop(jr, bridge, context, count)
                after = jr.applied_count()
                if before is not None and after is not None:
                    self.log(f"Applied counter after run: {after} (was {before})")
            finally:
                self._close_job_tabs()
                bridge.close()
                self.sheet.close()
        return self.stats

    # -- the loop ----------------------------------------------------------

    def _loop(self, jr, bridge, context, count: int) -> None:
        self.stopped_reason = f"completed {count} card(s)"
        max_attempts = max(1, int(self._setting("max_attempts_per_card", 2)))
        max_in_a_row = max(1, int(self._setting("max_consecutive_failures", 5)))
        in_a_row = 0
        try:
            for index in range(1, count + 1):
                self._check_stop()
                self._on_progress(index - 1, count)
                self._activate(jr.page)

                # A dialog left over from an earlier card covers the whole list
                # and would make every click below it fail.
                if jr.modal_is_open():
                    if jr.close_any_dialog():
                        self.log("    cleared a leftover dialog", "warn")
                    else:
                        self.log("A dialog is stuck open on the Jobright tab - close it "
                                 "and start again.", "error")
                        self.stopped_reason = "a dialog was stuck open on the Jobright tab"
                        break

                top = self._next_card(jr)
                if top is None:
                    self.log("No more job cards to process - stopping.", "warn")
                    self.stopped_reason = "the list is empty"
                    break

                self._current_card = top
                label = top.title or "(untitled card)"
                attempt = self._attempts.get(top.signature, 0) + 1
                retry = f" (attempt {attempt})" if attempt > 1 else ""
                self.log(f"[{index}/{count}] {KIND_TEXT.get(top.kind, 'APPLY NOW')} - {label}{retry}", "step")

                try:
                    if top.kind == AUTOFILL:
                        ok = self._handle_autofill(jr, bridge, context, top)
                    elif top.kind == EASY_APPLY:
                        ok = self._handle_easy_apply(jr, bridge, context, top)
                    else:
                        ok = self._handle_remove(jr, top)
                except StopRequested:
                    raise
                except Exception as exc:  # noqa: BLE001 - one bad card must not kill the run
                    ok = False
                    self.log(f"    unexpected error: {exc}", "error")
                    self._close_job_tabs()
                    try:
                        self._activate(jr.page)
                    except Exception:
                        pass

                self.stats.processed += 1
                if ok:
                    in_a_row = 0
                    self._attempts.pop(top.signature, None)
                else:
                    self.stats.failed += 1
                    in_a_row += 1
                    self._attempts[top.signature] = attempt
                    jr.close_any_dialog()
                    if attempt >= max_attempts:
                        self.stats.skipped += 1
                        self.stats.skipped_signatures.append(top.signature)
                        self.log(f"    failed {attempt} times - skipping this card for the rest of the run", "warn")
                    else:
                        self.log("    will try this card once more", "warn")
                    if in_a_row >= max_in_a_row:
                        self.log(f"{in_a_row} failures in a row - stopping the run. Check the "
                                 "Jobright tab and the extension, then start again.", "error")
                        self.stopped_reason = f"{in_a_row} failures in a row"
                        self._emit_stats()
                        break

                self._emit_stats()
                self._on_progress(index, count)
                if index < count:
                    self._pause()
        except StopRequested:
            self.stopped_reason = "stopped by the user"
            raise
        finally:
            self.log(f"Run ended: {self.stopped_reason}.")

    def _next_card(self, jr):
        """Find the top actionable card, scrolling once if the list looks empty."""
        for attempt in range(3):
            self._check_stop()
            top = jr.top_card(self.stats.skipped_signatures)
            if top is not None:
                return top
            if attempt == 0:
                jr.page.mouse.wheel(0, 400)
            elif attempt == 1:
                jr.page.mouse.wheel(0, -1200)
            self._pause(0.4)
        return None

    # -- case A: apply with autofill ---------------------------------------

    def _handle_autofill(self, jr, bridge, context, top) -> bool:
        known = set(context.pages)
        jr.click_action()

        outcome = self._wait_for_modal_or_tab(jr, context, known, timeout=12.0)
        job_page = None
        if outcome == "modal":
            self.log("    autofill dialog - Ctrl+clicking 'No, Apply Manually'")
            known = set(context.pages)
            # expect_page() is the only wait that reliably catches the new tab:
            # it listens for the event instead of polling a cached page list.
            try:
                with context.expect_page(timeout=20000) as new_page:
                    jr.ctrl_click_apply_manually()
                job_page = new_page.value
            except Exception:
                job_page = self._wait_for_new_tab(jr, context, known, timeout=10.0)
        elif outcome == "tab":
            self.log("    posting opened directly (no autofill dialog)")
            job_page = self._wait_for_new_tab(jr, context, known, timeout=5.0)

        if job_page is not None:
            job_page = self._wait_for_real_url(jr, job_page, timeout=20.0)
        if job_page is None:
            self.log("    the job posting tab never opened", "error")
            return False

        saved = self._save_posting(jr, bridge, job_page)
        self._close_job_tabs()
        self.log("    back to the Jobright tab")
        self._activate(jr.page)
        self._pause(0.4, interruptible=not saved)

        if not saved:
            if jr.wait_for_did_you_apply(int(self.settings.page_timeout * 1000)):
                self.log("    not saved - answering 'No, I didn't apply' so the job stays in the list", "warn")
                jr.click_didnt_apply()
            else:
                self.log("    not saved - leaving the job in the list", "warn")
                jr.close_any_dialog()
            return False
        return self._finish_saved_card(jr, top, AUTOFILL_ASK_WAIT_MS)

    # -- case C: easy apply -> company site -> save -------------------------

    def _handle_easy_apply(self, jr, bridge, context, top) -> bool:
        """An EASY APPLY card: its panel leads out to the employer's site.

        The panel's "Start to Autofill" is never pressed - it spends one of
        the account's Easy Apply credits.
        """
        jr.click_action()
        wait_ms = int(self.settings.page_timeout * 1000)
        if not jr.wait_for_company_site_button(wait_ms):
            self.log("    the Easy Apply panel never offered the company site", "error")
            jr.close_any_dialog()
            return False
        self.log("    Easy Apply panel - opening the company site")

        known = set(context.pages)
        job_page = None
        try:
            with context.expect_page(timeout=20000) as new_page:
                jr.click_company_site()
            job_page = new_page.value
        except Exception:
            job_page = self._wait_for_new_tab(jr, context, known, timeout=10.0)
        if job_page is not None:
            job_page = self._wait_for_real_url(jr, job_page, timeout=20.0)
        if job_page is None:
            self.log("    the company site never opened", "error")
            jr.close_any_dialog()
            return False

        saved = self._save_posting(jr, bridge, job_page)
        self._close_job_tabs()
        self.log("    back to the Jobright tab")
        self._activate(jr.page)
        self._pause(0.4, interruptible=not saved)

        if not saved:
            self.log("    not saved - leaving the job in the list", "warn")
            jr.close_any_dialog()
            return False

        # Jobright asks "Did you apply?" once its tab is back in front. Nothing
        # is pressed to bring it up: the only other Apply on the page belongs
        # to the NEXT card.
        return self._finish_saved_card(jr, top, EASY_APPLY_ASK_WAIT_MS)

    def _finish_saved_card(self, jr, top, ask_wait_ms: int) -> bool:
        """The card's posting is saved: answer Jobright's "Did you apply?" with
        Yes when it comes within `ask_wait_ms`, else close what is open and
        remove the card. True when the card left the list.

        Jobright often never asks for a card (EASY APPLY above all): the run
        used to wait the full timeout, call the saved card failed and leave it
        on top of the list (2026-10-16).
        """
        wait_ms = int(self.settings.page_timeout * 1000)
        if jr.wait_for_did_you_apply(ask_wait_ms):
            jr.click_yes_applied()
            if jr.wait_until_card_changed(top.signature, wait_ms):
                self.stats.saved += 1
                self.log("    saved and marked as applied", "ok")
                return True
            self.log("    card did not leave the list after 'Yes' - removing it", "warn")
        # No question: close the Easy Apply panel (never answering "didn't
        # apply" - the job IS saved), then remove the card.
        jr.close_dropdown()
        for _ in range(2):
            if not jr.modal_is_open():
                break
            if jr.wait_for_did_you_apply(300):  # it came late: Yes, as above
                jr.click_yes_applied()
            else:
                jr.page.keyboard.press("Escape")
            jr.page.wait_for_timeout(400)
        if jr.modal_is_open():  # Escape didn't close the panel: its own close button
            try:
                jr.page.locator('.ant-drawer-close, .ant-modal-close, [role="dialog"] [aria-label*="close" i]') \
                    .filter(visible=True).first.click(timeout=2000)
                jr.page.wait_for_timeout(400)
            except Exception:  # noqa: BLE001 - the menu click below says if it's still in the way
                pass
        if not jr.wait_until_card_changed(top.signature, 1500):  # still on top: remove it
            if not jr.open_kebab():
                self.log("    saved, but I couldn't find the card's '...' menu to remove it", "error")
                return False
            self._pause(0.3)
            if not jr.click_remove_from_list(6000):
                self.log("    saved, but 'Remove From List' never appeared", "error")
                jr.close_dropdown()
                return False
            if not jr.wait_until_card_changed(top.signature, wait_ms):
                self.log("    saved, but the card did not leave the list", "warn")
                return False
        self.stats.saved += 1
        self.log("    saved, and removed from the list (Jobright didn't ask 'Did you apply?')", "ok")
        return True

    # -- case B: apply now -> remove from list ------------------------------

    def _handle_remove(self, jr, top) -> bool:
        if not jr.open_kebab():
            self.log("    could not find the '...' menu on this card", "error")
            return False
        self._pause(0.3)

        if not jr.click_remove_from_list(6000):
            self.log("    'Remove From List' never appeared", "error")
            jr.close_dropdown()
            return False

        if not jr.wait_until_card_changed(top.signature, int(self.settings.page_timeout * 1000)):
            self.log("    card did not leave the list", "warn")
            return False
        self.stats.removed += 1
        self.log("    removed from list", "ok")
        return True

    # -- saving the posting --------------------------------------------------

    def _save_posting(self, jr, bridge, job_page) -> bool:
        """Save the employer posting on `job_page` with the extension."""
        self._job_page = job_page
        self._job_children = []
        try:
            job_page.on("popup", self._job_children.append)
        except Exception:
            pass
        self._activate(job_page)
        timeout_ms = int(self.settings.page_timeout * 1000)
        try:
            job_page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        except Exception:
            pass
        try:
            job_page.wait_for_load_state("load", timeout=min(timeout_ms, 10000))
        except Exception:
            pass
        self._wait_until_ready(job_page, timeout=25.0)

        url = job_page.url or ""
        if not url or url.startswith(NON_JOB_PREFIXES):
            self.log(f"    unusable posting URL: {url!r}", "error")
            return False
        self.log(f"    opened {_short_url(url)}")

        if self._setting("human_mode", True):
            self._read_page(job_page)
        self._check_stop()  # last point to stop before anything is written
        self._banner(job_page, "Job Intelligence - saving this posting...", "busy")
        url = job_page.url or url
        self.log("    saving with Job Intelligence")
        save = bridge.save_job(url, timeout=self.settings.save_timeout)
        ok = bool(save.ok)
        message = save.message
        if not ok and self._setting("accept_local_save", False) and getattr(save, "local_only", False):
            ok = True
            message = f"saved in the extension only ({save.message})"
        self.log(f"    {message}", "ok" if ok else "error")
        self._banner(job_page, f"Job Intelligence - {message}", "ok" if ok else "error")
        if ok:
            self._to_sheet(job_page, url, save)
        return ok

    def _to_sheet(self, job_page, url: str, save) -> None:
        """Queue the saved job for the Google Sheet (sent in the background)."""
        if not self.sheet.enabled:
            return
        card = self._current_card
        read = getattr(save, "detail", None) or {}  # what the extension read off the posting
        try:
            page_title = (job_page.title() or "").strip()
        except Exception:
            page_title = ""
        self.sheet.add(make_row(
            title=read.get("jobTitle") or (card.heading if card else "") or page_title,
            company=read.get("company") or (card.company if card else ""),
            location=read.get("location") or "",
            job_url=url,
            jobright_url=card.link if card else "",
            card=KIND_TEXT.get(card.kind, "") if card else "",
            result="Already on board" if getattr(save, "already_saved", False) else "Saved",
        ))

    def _wait_until_ready(self, page, timeout: float) -> None:
        """Wait until the posting has really rendered: many job sites build the
        page with scripts after "load", so the text keeps growing for a while.
        Ready = the page (or its biggest frame, e.g. iCIMS) shows some real text
        and it has stopped changing for about 1.5 s."""
        script = """() => {
          let best = (document.body && document.body.innerText || '').length;
          for (const f of document.querySelectorAll('iframe')) {
            try { best = Math.max(best, (f.contentDocument.body.innerText || '').length); } catch (e) {}
          }
          return best;
        }"""
        deadline = time.monotonic() + timeout
        last, steady = -1, 0
        while time.monotonic() < deadline:
            self._check_stop()
            try:
                size = int(page.evaluate(script) or 0)
            except Exception:
                size = 0  # navigating: ask again
            steady = steady + 1 if size == last and size > 0 else 0
            last = size
            if steady >= 3 and size >= 400:
                return
            try:
                page.wait_for_timeout(500)
            except Exception:
                time.sleep(0.5)
        self.log("    the page kept changing (or stayed nearly empty) - saving anyway", "warn")

    def _close_job_tabs(self) -> None:
        tabs = [self._job_page, *self._job_children]
        try:
            if self._job_page is not None:
                for tab in self._job_page.context.pages:
                    if tab not in tabs and tab.opener() == self._job_page:
                        tabs.append(tab)
        except Exception:
            pass
        for tab in tabs:
            try:
                if tab is not None and not tab.is_closed():
                    tab.close()
            except Exception:
                pass
        self._job_page = None
        self._job_children = []

    def _read_page(self, page) -> None:
        """Scroll the posting like someone skimming it before saving."""
        try:
            for delta in (260, 340, 280):
                self._check_stop()
                page.mouse.wheel(0, delta)
                page.wait_for_timeout(random.randint(260, 520))
            page.mouse.wheel(0, -500)
            page.wait_for_timeout(random.randint(250, 450))
        except StopRequested:
            raise
        except Exception:
            pass

    def _banner(self, page, message: str, kind: str) -> None:
        """Show what the bot is doing on the posting itself."""
        if not self._setting("human_mode", True):
            return
        colors = {"busy": "#0969da", "ok": "#1a7f37", "error": "#b62324"}
        try:
            page.evaluate(
                """({ message, color }) => {
                  const id = '__jsb_banner';
                  let el = document.getElementById(id);
                  if (!el) {
                    el = document.createElement('div');
                    el.id = id;
                    el.style.cssText = [
                      'position:fixed', 'top:14px', 'right:14px', 'z-index:2147483647',
                      'padding:10px 16px', 'border-radius:8px', 'color:#fff',
                      'font:600 13px/1.4 system-ui,sans-serif', 'max-width:380px',
                      'box-shadow:0 6px 20px rgba(0,0,0,.28)', 'pointer-events:none',
                    ].join(';');
                    document.documentElement.appendChild(el);
                  }
                  el.textContent = message;
                  el.style.background = color;
                }""",
                {"message": message, "color": colors.get(kind, "#0969da")},
            )
        except Exception:
            pass

    # -- waits ---------------------------------------------------------------

    def _wait_for_modal_or_tab(self, jr, context, known, timeout: float) -> str | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._check_stop()
            if jr.wait_for_autofill_modal(300):
                return "modal"
            if any(page not in known for page in context.pages):
                return "tab"
            self._pump(jr, 150)
        return None

    def _wait_for_new_tab(self, jr, context, known, timeout: float):
        """Fallback scan for a tab that expect_page() missed.

        Polls with page.wait_for_timeout rather than time.sleep - Playwright's
        sync API only refreshes context.pages during a round trip.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._check_stop()
            for page in context.pages:
                if page in known or page.is_closed():
                    continue
                url = page.url or ""
                if url.startswith(APP_PREFIXES) or "jobright.ai" in url:
                    continue
                return page
            self._pump(jr, 250)
        return None

    def _wait_for_real_url(self, jr, page, timeout: float):
        """A brand new tab reports about:blank until it navigates."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._check_stop()
            if page.is_closed():
                return page
            url = page.url or ""
            if url and url != "about:blank":
                return page
            self._pump(jr, 250)
        return page

    @staticmethod
    def _pump(jr, millis: int) -> None:
        """Sleep via the browser so Playwright processes pending events."""
        try:
            jr.page.wait_for_timeout(millis)
        except Exception:
            time.sleep(millis / 1000)


def _short_url(url: str, limit: int = 78) -> str:
    return url if len(url) <= limit else url[: limit - 3] + "..."
