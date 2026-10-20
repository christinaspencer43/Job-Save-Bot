"""Sending each saved job to a Google Sheet.

Two ways, chosen by the link in the settings:

* A sheet link (https://docs.google.com/spreadsheets/d/...): the bot edits the
  sheet itself, as a Google service account - a robot Google account whose key
  file (google-key.json, next to app.py) the bot signs in with. The sheet is
  shared with that account's email as Editor, like with a person. Setup:
  google-sheets/README.md.
* An Apps Script web app URL (.../exec): the sheet has google-sheets/Code.gs
  deployed as a web app, and the bot POSTs rows to it with a shared secret
  (no Google Cloud project or key file needed).

A row is first written to an outbox file (%LOCALAPPDATA%/JobSavingBot/
sheet_outbox.jsonl) and sent from a background thread, so a slow or offline
Google never holds up a save. Rows that could not be sent stay in the outbox
and go with the next send (or the next run). Both ways skip a job link the
sheet already has, so sending a row twice never makes two rows.
"""

from __future__ import annotations

import json
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from .config import APP_DIR, app_data_dir
from .safety import guard

#: The columns, in the order the sheet gets them (Code.gs writes the same).
COLUMNS = ("saved_at", "title", "company", "location", "job_url", "jobright_url", "card", "result", "computer")
HEADERS = ("Saved at", "Job title", "Company", "Location", "Job link", "Jobright link", "Card", "Result", "Computer")
LINK_COLUMN = COLUMNS.index("job_url") + 1
TAB_NAME = "Saved jobs"

SHEET_LINK_RE = re.compile(r"^https://docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]{20,})")
WEB_APP_RE = re.compile(r"^https://script\.google(?:usercontent)?\.com/.+/exec\b")


def outbox_path() -> Path:
    return app_data_dir() / "sheet_outbox.jsonl"


def is_sheet_link(url: str) -> bool:
    return bool(SHEET_LINK_RE.match((url or "").strip()))


def is_web_app(url: str) -> bool:
    return bool(WEB_APP_RE.match((url or "").strip()))


def default_key_file() -> Path:
    """Where the service account's key lives: next to app.py, so copying the
    folder to another computer takes it along."""
    return APP_DIR / "google-key.json"


def key_file_path(setting: str = "") -> Path:
    return Path(setting) if setting else default_key_file()


def key_email(key_file) -> str:
    """The service account's email (what the sheet is shared with). Raises
    ValueError with what is wrong when the file is not a service account key."""
    path = Path(key_file)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"no key file at {path}") from None
    except (OSError, ValueError):
        raise ValueError(f"{path.name} is not a Google key file (not JSON)") from None
    if not isinstance(data, dict) or data.get("type") != "service_account" or not data.get("client_email"):
        raise ValueError(f"{path.name} is not a service account key - in Google Cloud: IAM > Service accounts > "
                         "the account > Keys > Add key > JSON")
    return str(data["client_email"])


def make_row(title: str, company: str, job_url: str, jobright_url: str = "", card: str = "",
             result: str = "Saved", location: str = "") -> dict:
    return {
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "title": (title or "").strip()[:200],
        "company": (company or "").strip()[:120],
        "location": (location or "").strip()[:120],
        "job_url": job_url or "",
        "jobright_url": jobright_url or "",
        "card": card or "",
        "result": result,
        "computer": socket.gethostname(),
    }


def post(url: str, body: dict, timeout: float = 30.0) -> dict:
    """POST `body` as JSON to the web app; its JSON reply. Raises on any failure.

    Apps Script answers a POST with a redirect to the reply, which urllib
    follows as a GET - exactly what Google expects.
    """
    guard("sheet", url, "send saved jobs to the Google Sheet")
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8", errors="replace")
    try:
        reply = json.loads(text)
    except ValueError:
        # A sign-in or "page not found" page instead of the script's JSON: the
        # web app is not deployed for "Anyone", or the URL is not the /exec one.
        raise RuntimeError("the sheet's web app did not answer with JSON - check that the URL ends in /exec "
                           "and the deployment's 'Who has access' is 'Anyone'") from None
    if not isinstance(reply, dict) or not reply.get("ok"):
        raise RuntimeError(f"the sheet refused the rows: {(reply or {}).get('error') or reply}")
    return reply


# -- the sheet itself, as a service account -----------------------------------------

_worksheets: dict = {}  # (sheet link, key file) -> the open "Saved jobs" tab
_worksheets_lock = threading.Lock()


def _open_worksheet(url: str, key_file):
    """The sheet's "Saved jobs" tab, made (with its header row) when missing."""
    import gspread
    from gspread.utils import rowcol_to_a1

    client = gspread.service_account(filename=str(key_file))
    book = client.open_by_url(url)
    try:
        tab = book.worksheet(TAB_NAME)
    except gspread.WorksheetNotFound:
        tab = book.add_worksheet(TAB_NAME, rows=1000, cols=len(HEADERS))
    if not tab.row_values(1):
        tab.update(values=[list(HEADERS)], range_name="A1")
        tab.freeze(rows=1)
        tab.format(f"A1:{rowcol_to_a1(1, len(HEADERS))}", {"textFormat": {"bold": True}})
    return tab


def _worksheet(url: str, key_file):
    key = (url, str(key_file))
    with _worksheets_lock:
        tab = _worksheets.get(key)
        if tab is None:
            tab = _worksheets[key] = _open_worksheet(url, key_file)
        return tab


def _forget(url: str, key_file) -> None:
    with _worksheets_lock:
        _worksheets.pop((url, str(key_file)), None)


def explain(exc: Exception, key_file) -> str:
    """What a failed sheet call means, in words the person can act on."""
    try:
        email = key_email(key_file)
    except ValueError as bad_key:
        return str(bad_key)
    text = str(exc)
    name = type(exc).__name__
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if "has not been used" in text or "is disabled" in text or "SERVICE_DISABLED" in text:
        return ("the Google Sheets API is off for the key's Google Cloud project - turn it on: "
                "console.cloud.google.com > APIs & Services > Library > Google Sheets API > Enable")
    if name == "SpreadsheetNotFound" or status in (403, 404) or "PERMISSION_DENIED" in text:
        return f"the bot can't open the sheet - share it with {email} as Editor (Share button in the sheet)"
    if "invalid_grant" in text:
        return "Google refused the key file (deleted key, or this computer's clock is wrong)"
    first = text.splitlines()[0][:200] if text else name
    return f"{name}: {first}"


def append_to_sheet(url: str, key_file, rows: list[dict]) -> dict:
    """Add the rows whose job link the tab doesn't have yet. As text (RAW), so a
    title like "=..." from a job page is never run as a formula."""
    guard("sheet", url, "add saved jobs to the Google Sheet")
    try:
        tab = _worksheet(url, key_file)
        known = set(tab.col_values(LINK_COLUMN))
        add = []
        for row in rows:
            link = str(row.get("job_url") or "")
            if link and link in known:
                continue
            known.add(link)
            add.append([str(row.get(key) or "") for key in COLUMNS])
        if add:
            tab.append_rows(add, value_input_option="RAW", insert_data_option="INSERT_ROWS", table_range="A1")
    except Exception as exc:  # noqa: BLE001 - said in words, the rows wait in the outbox
        _forget(url, key_file)  # opened again next time (the share or the key may have changed)
        raise RuntimeError(explain(exc, key_file)) from None
    return {"ok": True, "added": len(add), "skipped": len(rows) - len(add)}


def send_rows(url: str, secret: str, key_file, rows: list[dict]) -> dict:
    if is_sheet_link(url):
        return append_to_sheet(url, key_file, rows)
    return post(url, {"secret": secret, "rows": rows})


def check_connection(url: str, secret: str = "", key_file=None) -> dict:
    """Open the sheet (or ask the web app) without writing any job; {"sheet", "rows"}."""
    key_file = key_file_path(str(key_file or ""))
    if not is_sheet_link(url):
        return post(url, {"secret": secret, "test": True})
    guard("sheet", url, "open the Google Sheet")
    try:
        tab = _worksheet(url, key_file)
        jobs = max(0, len(tab.col_values(LINK_COLUMN)) - 1)
        return {"ok": True, "sheet": f"{tab.spreadsheet.title} > {tab.title}", "rows": jobs}
    except Exception as exc:  # noqa: BLE001
        _forget(url, key_file)
        raise RuntimeError(explain(exc, key_file)) from None


class SheetLogger:
    """Queues saved jobs and sends them to the sheet from one background thread."""

    def __init__(self, url: str, secret: str = "", log=None, outbox: Path | None = None, key_file=None):
        self.url = (url or "").strip()
        self.secret = secret or ""
        self.key_file = key_file_path(str(key_file or ""))
        self._log = log or (lambda message, level="info": None)
        self.outbox = Path(outbox) if outbox else outbox_path()
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._attempts = 0      # sends tried so far
        self._last_ok = True    # whether the last one went through
        self._closed = False
        self._thread: threading.Thread | None = None
        self._last_error = ""
        self.sent = 0

    @property
    def enabled(self) -> bool:
        return self.url.startswith(("https://", "http://"))

    def pending(self) -> list[dict]:
        with self._lock:
            return self._read()

    def add(self, row: dict) -> None:
        """Keep the row in the outbox and send it soon."""
        if not self.enabled:
            return
        with self._lock:
            with self.outbox.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.start()
        self._wake.set()

    def start(self) -> None:
        """Start the sender (it also sends rows an earlier run left behind)."""
        if not self.enabled or (self._thread and self._thread.is_alive()):
            return
        self._closed = False
        if self.pending():
            self._wake.set()
        self._thread = threading.Thread(target=self._run, daemon=True, name="sheet-sender")
        self._thread.start()

    def flush(self, timeout: float = 20.0) -> bool:
        """Wait until the outbox is sent, a send has failed, or `timeout`. True when nothing is left."""
        if not self.enabled or self._thread is None:
            return not self.pending()
        deadline = time.monotonic() + timeout
        start = self._attempts
        self._wake.set()
        while self.pending() and time.monotonic() < deadline:
            if self._attempts > start and not self._last_ok:
                break  # offline / refused: the rows wait in the outbox
            time.sleep(0.1)
        return not self.pending()

    def close(self, timeout: float = 20.0) -> None:
        self.flush(timeout)
        self._closed = True
        self._wake.set()
        if self.pending():
            self._log(f"Google Sheet: {len(self.pending())} row(s) not sent yet - they go with the next run", "warn")

    # -- the sender thread ---------------------------------------------------

    def _run(self) -> None:
        while not self._closed:
            self._wake.wait(30)  # a failed send is tried again every 30 s
            self._wake.clear()
            if self._closed:
                break
            while self._send_pending():  # sent, and more rows came meanwhile
                pass

    def _send_pending(self) -> bool:
        """Send the outbox once; True when it went through and rows are still waiting."""
        rows = self.pending()
        if not rows:
            return False
        try:
            reply = send_rows(self.url, self.secret, self.key_file, rows)
        except Exception as exc:  # noqa: BLE001 - kept in the outbox, tried again
            message = str(exc).splitlines()[0][:200] if str(exc) else type(exc).__name__
            if message != self._last_error:  # say it once, not every 30 s
                self._log(f"Google Sheet: could not send {len(rows)} row(s) ({message}) - will try again", "warn")
            self._last_error = message
            self._last_ok = False
            self._attempts += 1
            return False
        self._last_error = ""
        with self._lock:
            # rows added while sending stay for the next round
            left = self._read()[len(rows):]
            self._write(left)
        self.sent += int(reply.get("added") or 0)
        added, skipped = int(reply.get("added") or 0), int(reply.get("skipped") or 0)
        self._log(f"Google Sheet: added {added} row(s)" + (f", {skipped} already there" if skipped else ""), "ok")
        self._last_ok = True
        self._attempts += 1
        return bool(self.pending())

    # -- the outbox file (callers hold the lock) -------------------------------

    def _read(self) -> list[dict]:
        try:
            lines = self.outbox.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        rows = []
        for line in lines:
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
        return rows

    def _write(self, rows: list[dict]) -> None:
        if not rows:
            try:
                self.outbox.unlink()
            except OSError:
                pass
            return
        self.outbox.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
