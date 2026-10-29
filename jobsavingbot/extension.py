"""Bridge to the "Job Intelligence" Chrome extension.

Clicking the toolbar icon and then Save is browser chrome, not page content, so
it cannot be automated through the DOM. The popup's Save button only sends a
message to the extension's service worker:

    {v: 1, type: "ui/save-job", payload: {tabId}}

This module runs that exact message from an extension page, which means the bot
takes the same code path as a real click, with no screen coordinates involved.

Ported from Job Save Bot's jobsavebot/extension.py: SAVE_SCRIPT, save_job,
save_outcome_of and find_extension_id (with all its fallbacks) are unchanged.
The capture/confirm paths used by the apply flow were dropped. The upgraded
"Job JD Scanner" build keeps the same name ("Job Intelligence") and the same
ui/get-tab-state, ui/rescan, ui/save-job messages.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from .safety import guard

EXTENSION_NAME_HINT = "job intelligence"
MESSAGE_VERSION = 1

# Runs inside an extension page, where chrome.* is fully available.
SAVE_SCRIPT = """
async (args) => {
  const { jobUrl, settleMs, expect } = args;

  // Every call into the extension settles, one way or the other. A service
  // worker that has gone to sleep mid-question simply never calls the
  // callback back - and page.evaluate has no timeout of its own, so the
  // whole job hung there with nothing more said (four minutes and counting,
  // 2026-09-20). A timed-out call reports itself as one.
  const limited = (make, ms, whenLate) => new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };
    setTimeout(() => finish(whenLate), ms);
    try {
      make(finish);
    } catch (e) {
      finish(whenLate);
    }
  });

  const send = (msg) => limited((done) => {
    chrome.runtime.sendMessage(msg, (reply) => {
      const err = chrome.runtime.lastError;
      done(err ? { ok: false, error: err.message } : reply);
    });
  }, 20000, { ok: false, error: "the extension did not answer in 20s" });

  const allTabs = () => limited(
    (done) => chrome.tabs.query({}, (tabs) => done(tabs || [])), 10000, []
  );

  const strip = (u) => {
    try {
      const parsed = new URL(u);
      parsed.hash = "";
      return parsed.toString();
    } catch (e) {
      return u;
    }
  };
  const base = (u) => {
    try {
      const parsed = new URL(u);
      return parsed.origin + parsed.pathname;
    } catch (e) {
      return u;
    }
  };

  const tabs = await allTabs();
  if (!tabs.length) return { stage: "tabs", error: "no-tabs-visible" };
  if (!tabs.some((t) => typeof t.url === "string" && t.url)) {
    return { stage: "tabs", error: "no-tab-urls" };
  }

  const want = strip(jobUrl);
  const wantBase = base(jobUrl);
  // The tab showing THIS job, as in the capture script below: the same
  // path is not enough when the job is named in the query, and two tabs
  // that both fit are two jobs the save cannot choose between (Stage 04).
  const tracking = ["jr_id", "gh_src", "source", "src", "ref", "referrer", "iis", "iisn"];
  const telling = (u) => {
    try {
      const parsed = new URL(u);
      const kept = [];
      parsed.searchParams.forEach((value, key) => {
        const name = key.toLowerCase();
        if (tracking.indexOf(name) >= 0 || name.indexOf("utm_") === 0) return;
        kept.push(name + "=" + value);
      });
      return kept.sort().join("&");
    } catch (e) {
      return "";
    }
  };
  const exact = tabs.filter((t) => t.url && strip(t.url) === want);
  let candidates = exact;
  if (!candidates.length) {
    const samePath = tabs.filter((t) => t.url && base(t.url) === wantBase);
    const sameJob = samePath.filter((t) => telling(t.url) === telling(jobUrl));
    candidates = sameJob.length ? sameJob : (samePath.length === 1 ? samePath : []);
  }
  if (!candidates.length) return { stage: "tabs", error: "tab-not-found" };
  if (candidates.length > 1) {
    return { stage: "tabs", error: "tab-ambiguous", count: candidates.length };
  }
  const tab = candidates[0];

  const tabId = tab.id;
  const payload = { tabId };

  // get-tab-state also kicks off the scan and waits for the content script.
  let state = await send({ v: 1, type: "ui/get-tab-state", payload });
  if (!state || state.ok === false) {
    return { stage: "state", tabId, error: (state && state.error) || "state-failed" };
  }

  // A tab that has just loaded often has not been scanned yet, and one scan
  // is not always enough, so rescan with a growing settle time - also when the
  // page type is known but the job description hasn't been read yet (the
  // popup's Rescan button does the same).
  const scanned = (s) => {
    const c = s && s.data && s.data.classification;
    return !!c && c.pageType && c.pageType !== "UNKNOWN";
  };
  const descLength = (s) => {
    const job = s && s.data && s.data.result && s.data.result.job;
    return job && typeof job.description === "string" ? job.description.trim().length : 0;
  };
  const ready = (s) => scanned(s) && descLength(s) >= 300;
  for (let attempt = 0; attempt < 3 && !ready(state); attempt++) {
    await send({ v: 1, type: "ui/rescan", payload });
    await new Promise((r) => setTimeout(r, settleMs * (attempt + 1)));
    state = await send({ v: 1, type: "ui/get-tab-state", payload });
  }

  const info = (state && state.data) || {};
  if (info.needsPermission) {
    return { stage: "permission", tabId, url: info.url, error: "needs-permission" };
  }

  const savePayload = expect ? { tabId, expect } : payload;
  const reply = await send({ v: 1, type: "ui/save-job", payload: savePayload });
  if (!reply || reply.ok === false) {
    // "did not answer": the save message went out and nothing came back -
    // whether the extension wrote the row is unknown, not "no".
    return {
      stage: "save",
      answered: !(reply && String(reply.error || "").indexOf("did not answer") >= 0),
      tabId,
      url: info.url,
      classification: info.classification,
      error: (reply && reply.error) || "save-failed",
    };
  }

  const result = reply.data || {};
  const cls = info.classification || null;
  // What the extension read off the page (the board row has the same).
  const job = (info.result && info.result.job) || {};
  const say = (v) => (typeof v === "string" ? v.replace(/\\s+/g, " ").trim() : "");
  return {
    stage: "done",
    tabId,
    url: info.url,
    pageType: cls ? cls.pageType : null,
    confidence: cls ? cls.confidence : null,
    descLength: descLength(state),
    provider: info.provider,
    alreadySaved: info.alreadySaved,
    saved: !!result.saved,
    synced: !!result.synced,
    existing: !!result.existing,
    error: result.error || null,
    fingerprint: result.fingerprint || null,
    syncFailure: result.syncFailure || null,
    jobTitle: say(job.title),
    company: say(job.company),
    location: say(job.location),
    // The job's description as read (for KIASA's tailored résumés), its lines kept.
    description: typeof job.description === "string" ? job.description.trim().slice(0, 30000) : "",
    answered: true,
  };
}
"""


@dataclass
class SaveOutcome:
    """What a save came to.

    `ok` is True only when the database acknowledged the row.
    `state` is one of ACKED, REJECTED, UNCERTAIN, REFUSED, NOT_SENT: a save
    kept only in the extension's own storage is not "saved" (see
    `local_only`), and a save whose reply was lost is UNCERTAIN.
    """

    ok: bool
    message: str
    detail: dict
    state: str = ""

    @property
    def already_saved(self) -> bool:
        return bool(self.detail.get("existing"))

    @property
    def fingerprint(self) -> str:
        return str(self.detail.get("fingerprint") or "")

    @property
    def local_only(self) -> bool:
        """The extension stored the job itself but did not sync it."""
        return bool(self.detail.get("saved")) and not self.detail.get("synced")


class ExtensionNotFound(RuntimeError):
    pass


def find_extension_id(context, profile_dir: Path | None = None,
                      timeout_ms: int = 12000) -> str:
    """Locate the Job Intelligence extension ID in the running browser.

    Polled, not read once: an extension's service worker registers a few
    seconds after Chrome starts, and Chrome writes its Preferences file
    lazily, so a job begun straight after launching the browser looked into
    a profile that had not admitted to the extension yet (2026-09-20).
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while True:
        # Chrome's own record of what is installed names the extension; a
        # listed service worker is only a candidate until something names it.
        found = _id_from_preferences(profile_dir) or _scan_profile_for_extension(profile_dir)
        if found:
            return found
        for worker in getattr(context, "service_workers", []) or []:
            url = getattr(worker, "url", "") or ""
            if url.startswith("chrome-extension://"):
                candidate = url.split("/")[2]
                if _manifest_matches(profile_dir, candidate):
                    return candidate

        for page in context.pages:
            url = page.url or ""
            if url.startswith("chrome-extension://"):
                candidate = url.split("/")[2]
                if _manifest_matches(profile_dir, candidate):
                    return candidate

        if time.monotonic() >= deadline:
            found = _id_from_extensions_page(context)
            if found:
                return found
            break
        time.sleep(0.5)

    raise ExtensionNotFound(
        "Could not find the 'Job Intelligence' (Job JD Scanner) extension in the "
        "bot's Chrome profile."
    )


HAS_ALL_SITES_JS = "() => new Promise((done) => chrome.permissions.contains({origins: ['https://*/*']}, done))"

SITE_ACCESS_HELP = (
    "The Job Intelligence extension is not allowed on all sites in the bot's Chrome, so it can't "
    "see most job pages. In the bot's Chrome: right-click the extension's icon > Options, tick "
    "\"all sites\" and accept - or chrome://extensions > Job Intelligence > Details > Site access: "
    "On all sites. Then press Start again."
)


def load_instructions(extension_dir: str) -> str:
    """The one-time manual step when Chrome ignored --load-extension."""
    return (
        "One-time setup: in the bot's Chrome window open chrome://extensions, turn on "
        "'Developer mode' (top right), press 'Load unpacked' and pick the folder "
        f"{extension_dir or 'extension (next to app.py)'} . "
        "Chrome keeps it in the bot's profile after that. Then open the extension's "
        "Details and set Site access to 'On all sites'."
    )


EXTENSIONS_PAGE = """() => {
  const manager = document.querySelector('extensions-manager');
  if (!manager || !manager.shadowRoot) return [];
  const list = manager.shadowRoot.querySelector('extensions-item-list');
  if (!list || !list.shadowRoot) return [];
  return Array.from(list.shadowRoot.querySelectorAll('extensions-item')).map((item) => ({
    id: item.id,
    name: ((item.shadowRoot && item.shadowRoot.querySelector('#name'))
      || {}).textContent || '',
  }));
}"""


def _id_from_extensions_page(context) -> str:
    """Read the ID off chrome://extensions, the way a person would look.

    The last resort, and the only one that works when the extension's
    service worker is asleep (Chrome stops idle MV3 workers, so the
    browser reports none) and Chrome has not yet written the profile's
    Preferences file, which it does lazily - a run started soon after
    launching the browser saw neither (2026-09-20).
    """
    page = None
    try:
        page = context.new_page()
        page.goto("chrome://extensions/", wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        for item in page.evaluate(EXTENSIONS_PAGE) or []:
            if EXTENSION_NAME_HINT in str(item.get("name") or "").lower():
                return str(item.get("id") or "")
    except Exception:
        return ""
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass
    return ""


def _extension_dirs(profile_dir: Path | None) -> list[Path]:
    if not profile_dir:
        return []
    roots = [
        profile_dir / "Default" / "Extensions",
        profile_dir / "Extensions",
    ]
    return [root for root in roots if root.is_dir()]


def _manifest_matches(profile_dir: Path | None, extension_id: str) -> bool:
    """True only when this ID is positively our extension.

    It used to answer True "when we cannot tell" - and it cannot tell for any
    unpacked or built-in extension, whose files are not in the profile's
    Extensions folder. The first such service worker the browser listed was
    then taken for Job Intelligence: a Chromium component extension was
    picked, and every capture failed on its missing options page (found by
    the integrated Cancel check, 2026-09-22).
    """
    for root in _extension_dirs(profile_dir):
        target = root / extension_id
        for manifest in target.glob("*/manifest.json"):
            if EXTENSION_NAME_HINT in _manifest_name(manifest).lower():
                return True
    return extension_id == _id_from_preferences(profile_dir) != ""


def _manifest_name(manifest: Path) -> str:
    try:
        data = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return ""
    return str(data.get("name", ""))


def _id_from_preferences(profile_dir: Path | None) -> str:
    """Find the extension through Chrome's own list of what is installed.

    Needed because the extension is normally loaded unpacked. An unpacked
    extension is never copied into the profile's Extensions folder - Chrome
    records it in "Secure Preferences" with a `path` pointing at wherever it
    was built - so scanning that folder cannot find it.

    Without this, detection depends on the service worker being awake and
    listed in context.service_workers. Manifest V3 workers shut down after a
    few seconds idle, which is why the extension is found one minute and
    reported missing the next.
    """
    if not profile_dir:
        return ""

    for prefs_name in ("Secure Preferences", "Preferences"):
        prefs = Path(profile_dir) / "Default" / prefs_name
        if not prefs.is_file():
            continue
        try:
            data = json.loads(prefs.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            continue

        settings = ((data.get("extensions") or {}).get("settings")) or {}
        for extension_id, config in settings.items():
            if not isinstance(config, dict):
                continue

            # The prefs entry carries a manifest for packed extensions, but an
            # unpacked one has an empty name there, so fall back to the real
            # manifest.json at the recorded path.
            name = str(((config.get("manifest") or {}).get("name")) or "")
            if EXTENSION_NAME_HINT not in name.lower():
                raw_path = str(config.get("path") or "")
                if not raw_path:
                    continue
                source = Path(raw_path)
                if not source.is_absolute():
                    source = Path(profile_dir) / "Default" / "Extensions" / raw_path
                name = _manifest_name(source / "manifest.json")

            if EXTENSION_NAME_HINT in name.lower():
                return extension_id
    return ""


def _scan_profile_for_extension(profile_dir: Path | None) -> str:
    for root in _extension_dirs(profile_dir):
        for manifest in root.glob("*/*/manifest.json"):
            if EXTENSION_NAME_HINT in _manifest_name(manifest).lower():
                return manifest.parent.parent.name
    return ""


class ExtensionBridge:
    """A background extension tab used to run saves."""

    def __init__(self, context, extension_id: str, log=None):
        self.context = context
        self.extension_id = extension_id
        self._log = log or (lambda message: None)
        self._page = None

    @property
    def options_url(self) -> str:
        return f"chrome-extension://{self.extension_id}/options/index.html"

    def open(self):
        if self._page and not self._page.is_closed():
            return self._page
        # Only ever reuse our own options tab. The extension's popup may also
        # be open, and it belongs to the user - driving or closing it would be
        # rude, and it disappears the moment they click elsewhere.
        for page in self.context.pages:
            if (page.url or "").split("#")[0] == self.options_url:
                self._page = page
                return page
        page = self._background_tab(self.options_url)
        self._page = page
        self._log(f"Extension bridge ready ({self.extension_id[:12]}...)")
        return page

    def _background_tab(self, url: str):
        """Open url in a tab that is NOT brought to the front, so the job page
        stays on screen while the bot talks to the extension."""
        try:
            cdp = self.context.browser.new_browser_cdp_session()
            with self.context.expect_page(timeout=10000) as opened:
                cdp.send("Target.createTarget", {"url": url, "background": True})
            page = opened.value
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            return page
        except Exception:  # an old Chrome without background tabs: a normal one
            page = self.context.new_page()
            page.goto(url, wait_until="domcontentloaded")
            return page

    def has_all_sites(self) -> bool | None:
        """Whether the extension may read every site (Site access: On all sites).

        Without it the extension sees only the tabs of its built-in job sites
        (Greenhouse, Lever, Workday...): every other employer page came back
        "tab-not-found" and the run stopped after 5 failures, while a person's
        own click on Save worked (a click lends it that one tab) - a new
        Chrome profile never had it switched on (2026-10-16). None when it
        can't be told.
        """
        try:
            return bool(self.open().evaluate(HAS_ALL_SITES_JS))
        except Exception:  # noqa: BLE001 - can't tell: let the save run
            return None

    def close(self):
        if self._page and not self._page.is_closed():
            try:
                self._page.close()
            except Exception:
                pass
        self._page = None

    def save_job(self, job_url: str, timeout: float = 45.0, expect: dict | None = None) -> SaveOutcome:
        """Save the job on the tab showing `job_url`.

        `expect` - {"fingerprint", "url"} of what the caller checked - makes
        the extension refuse the save if the tab now shows something else.
        """
        # The extension writes the job to the Supabase database.
        guard("database", "", "save a job through the extension")

        def ask():
            page = self.open()
            return page.evaluate(
                SAVE_SCRIPT,
                {"jobUrl": job_url, "settleMs": 1500, "expect": expect or None},
            )

        try:
            raw = ask()
            # Save is the extension's own button, and it has nothing to save
            # until it has scanned the page - which it does a second or two
            # after the page renders. Pressed inside that window it answers
            # "no permission" or "nothing to save" for a page it reads
            # perfectly well straight after (Rippling, 2026-09-21).
            for pause in (2500, 3500):
                detail = raw if isinstance(raw, dict) else {}
                stage = detail.get("stage")
                scanned = bool(detail.get("saved")) or (
                    detail.get("pageType") and detail.get("pageType") != "UNKNOWN"
                )
                if stage == "done" and scanned:
                    break
                if stage == "tabs" and detail.get("error") in ("no-tab-urls", "tab-ambiguous"):
                    break  # A real setting or two candidate tabs, not a slow scan.
                if stage == "save" and not detail.get("answered", True):
                    break  # Sent, and no answer: asking again could write twice.
                if stage == "done" and str(detail.get("error") or "").startswith("page-changed"):
                    break  # Refused: the tab no longer shows the checked job.
                self._log(
                    f"    the extension has not read this page yet - waiting "
                    f"{pause // 1000}s and asking again"
                )
                self.open().wait_for_timeout(pause)
                raw = ask()
        except Exception as exc:  # noqa: BLE001 - surfaced to the user as text
            # The call broke off somewhere between asking and hearing back:
            # whether the row was written is unknown.
            return SaveOutcome(False, f"Extension call failed: {exc}", {}, "UNCERTAIN")
        return save_outcome_of(raw)


def save_outcome_of(raw) -> SaveOutcome:
    """Read the save script's reply. Pure, so every branch is testable."""
    detail = raw if isinstance(raw, dict) else {}
    stage = detail.get("stage")
    error = detail.get("error")

    if stage == "tabs" and error == "no-tab-urls":
        return SaveOutcome(
            False,
            "The extension cannot read tab URLs. Open chrome://extensions, "
            "click Details on Job Intelligence, and set Site access to "
            "'On all sites'.",
            detail, "NOT_SENT",
        )
    if stage == "tabs" and error == "tab-ambiguous":
        return SaveOutcome(
            False,
            f"Not saved: {detail.get('count')} tabs show this address, and the "
            "save cannot tell which one is the selected job.",
            detail, "NOT_SENT",
        )
    if stage == "permission":
        return SaveOutcome(
            False,
            "The extension has no permission for this site. Set its Site "
            "access to 'On all sites'.",
            detail, "NOT_SENT",
        )
    if stage == "save" and not detail.get("answered", True):
        return SaveOutcome(False, f"Save sent, no answer ({error}) - outcome unknown.", detail, "UNCERTAIN")
    if stage != "done":
        return SaveOutcome(False, f"Save failed ({stage}): {error}", detail, "NOT_SENT")

    if str(error or "").startswith("page-changed"):
        return SaveOutcome(False, f"Not saved - {error}.", detail, "REFUSED")

    if not detail.get("saved"):
        page_type = detail.get("pageType") or "UNKNOWN"
        return SaveOutcome(
            False,
            f"Nothing to save - the extension read this page as {page_type}.",
            detail, "NOT_SENT",
        )

    if detail.get("synced"):
        if detail.get("existing"):
            return SaveOutcome(True, "Already on your board - entry updated.", detail, "ACKED")
        return SaveOutcome(True, "Saved and synced.", detail, "ACKED")

    # Kept in the extension's own storage only. Not "saved": the board and
    # the applying worker read the database, and it does not have this job.
    note = error or "not synced"
    if detail.get("syncFailure") == "unreachable":
        return SaveOutcome(False, f"Not confirmed - the database did not answer ({note}).", detail, "UNCERTAIN")
    return SaveOutcome(False, f"Not saved to the board - {note}", detail, "REJECTED")
