"""KIASA: the team's site. Each job the bot saves is posted to KIASA Jobs, and
KIASA's admins start, stop, watch and schedule runs from its job desk.

The bot connects with a code an admin makes on KIASA (Job desk > Jobs >
Jobright bot > Connect a computer): "KIASA-BOT1." and, packed in it, the
address of KIASA's database, its public key (the one every KIASA page has) and
this bot's own secret key. With it the bot calls three functions there, and
nothing else:

* job_bot_check_in - every few seconds, how the bot is; KIASA answers with a
  run to do when an admin (or the schedule) asked for one;
* job_bot_report - a run's start, its counts and lines as they come, and its
  end; KIASA answers whether an admin pressed Stop;
* job_bot_add_jobs - the jobs saved, through an outbox like the Google Sheet's,
  so none is lost while the internet is down.

KIASA never calls this computer: the bot only asks, so no port is opened here.
"""

from __future__ import annotations

import base64
import json
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import __version__
from .config import app_data_dir
from .safety import guard
from .sheets import SheetLogger

CODE_PREFIX = "KIASA-BOT1."
#: Seconds between check-ins, and between a run's reports.
CHECK_EVERY = 3.0
REPORT_EVERY = 1.5
#: The longest wait between check-ins while KIASA cannot be reached.
CHECK_BACKOFF = 30.0
#: How long a finished run keeps trying to tell KIASA how it ended.
END_PATIENCE = 600.0
#: Levels of the bot's log that KIASA's admins see in a run's lines.
SHOWN_LEVELS = ("step", "ok", "warn", "error")


class KiasaError(RuntimeError):
    """KIASA could not be reached, or refused the call."""


class NotConnected(KiasaError):
    """KIASA no longer knows this bot: its code was replaced, or it was disconnected."""


@dataclass(frozen=True)
class Connection:
    url: str      # KIASA's database (https://....supabase.co)
    apikey: str   # its public key
    key: str      # this bot's secret


def parse_code(code: str) -> Connection:
    """The connection a KIASA code holds. Raises ValueError saying what is wrong."""
    text = "".join((code or "").split())
    if not text.startswith(CODE_PREFIX):
        raise ValueError("That is not a KIASA bot code: it starts with KIASA-BOT1.")
    packed = text[len(CODE_PREFIX):]
    try:
        data = json.loads(base64.urlsafe_b64decode(packed + "=" * (-len(packed) % 4)).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        data = None
    url, apikey, key = (str(data.get(name) or "") for name in ("u", "k", "s")) if isinstance(data, dict) else ("", "", "")
    if not url.startswith(("https://", "http://")) or not apikey or not key.startswith("kbot_"):
        raise ValueError("That code is cut short or changed: copy it again from KIASA.")
    return Connection(url.rstrip("/"), apikey, key)


#: Parts of a link that only track who clicked it (as KIASA's lib/jobs/links.ts).
TRACKING = re.compile(r"^(utm_|trk|refid$|trackingid$|fbclid$|gclid$|mc_cid$|mc_eid$|ebp$|lipi$|_hs|src$|source$)", re.I)


def clean_link(link: str) -> str:
    """The link as KIASA keeps it (cleanLink in KIASA's lib/jobs/links.ts): no
    #part and no tracking, a LinkedIn or Indeed job by its own id - so a job an
    admin also pastes on KIASA is posted once. "" for anything not http(s)."""
    parts = urlsplit((link or "").strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return ""
    host = parts.hostname
    query = parse_qsl(parts.query, keep_blank_values=True)
    asked = dict(query)
    if re.search(r"(^|\.)linkedin\.com$", host):
        found = re.search(r"/jobs/view/(?:[^/]*?-)?(\d{6,})", parts.path)
        job = asked.get("currentJobId") or (found.group(1) if found else "")
        if job.isdigit():
            return f"https://www.linkedin.com/jobs/view/{job}/"
    if re.search(r"(^|\.)indeed\.[a-z.]+$", host):
        job = asked.get("jk") or asked.get("vjk") or ""
        if re.fullmatch(r"[\w-]+", job):
            return f"https://{host}/viewjob?jk={job}"
    kept = [(name, value) for name, value in query if not TRACKING.match(name)]
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or "/",
                       urlencode(kept) if len(kept) != len(query) else parts.query, ""))


class KiasaClient:
    """Calls KIASA's job_bot_* functions with this bot's key."""

    def __init__(self, connection: Connection, timeout: float = 20.0):
        self.connection = connection
        self.timeout = timeout

    def call(self, name: str, body: dict):
        url = f"{self.connection.url}/rest/v1/rpc/{name}"
        guard("kiasa", url, f"call {name} on KIASA")
        headers = {"Content-Type": "application/json", "Accept": "application/json", "apikey": self.connection.apikey}
        if self.connection.apikey.startswith("eyJ"):  # an older-style public key is also sent as the bearer
            headers["Authorization"] = f"Bearer {self.connection.apikey}"
        request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                text = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            try:
                said = json.loads(exc.read().decode("utf-8", errors="replace") or "{}")
            except ValueError:
                said = {}
            message = str(said.get("message") or exc.reason or "").strip() if isinstance(said, dict) else ""
            if isinstance(said, dict) and said.get("code") == "28000":
                raise NotConnected(message or "KIASA no longer knows this bot.") from None
            raise KiasaError(f"KIASA refused it ({exc.code}{': ' + message if message else ''})") from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", None) or exc
            raise KiasaError(f"KIASA could not be reached ({reason})") from None
        try:
            return json.loads(text) if text else None
        except ValueError:
            raise KiasaError("KIASA answered with something that is not JSON") from None

    def check_in(self, info: dict) -> dict:
        return self.call("job_bot_check_in", {"bot_key": self.connection.key, "info": info}) or {}

    def report(self, run: str | None, report: dict) -> dict:
        return self.call("job_bot_report", {"bot_key": self.connection.key, "run": run, "report": report}) or {}

    def add_jobs(self, jobs: list[dict]) -> dict:
        return self.call("job_bot_add_jobs", {"bot_key": self.connection.key, "jobs": jobs}) or {}


class KiasaOutbox(SheetLogger):
    """The saved jobs on their way to KIASA: kept in kiasa_outbox.jsonl and sent
    from a background thread, like the Google Sheet's rows. KIASA posts each link
    once, so sending one twice does no harm."""

    LABEL = "KIASA"
    ITEMS = "job(s)"
    THREAD = "kiasa-sender"

    def __init__(self, client: KiasaClient | None, log=None, outbox: Path | None = None):
        super().__init__(client.connection.url if client else "", log=log, outbox=outbox)
        self.client = client

    @staticmethod
    def default_outbox() -> Path:
        return app_data_dir() / "kiasa_outbox.jsonl"

    def _send(self, rows: list[dict]) -> dict:
        added = known = 0
        for at in range(0, len(rows), 50):
            reply = self.client.add_jobs(rows[at:at + 50])
            added += int(reply.get("added") or 0)
            known += int(reply.get("known") or 0)
        return {"added": added, "skipped": known}


def job_for_kiasa(saved: dict, run: str | None) -> dict:
    """A saved job (the runner's on_saved) as KIASA takes it."""
    return {
        "url": clean_link(saved.get("job_url", "")) or saved.get("job_url", ""),
        "title": (saved.get("title") or "")[:200],
        "company": (saved.get("company") or "")[:120],
        "location": (saved.get("location") or "")[:120],
        # Its description, for the members' tailored résumés on KIASA.
        "description": (saved.get("description") or "")[:30000],
        "run": run or "",
    }


class RunReport:
    """One run as KIASA's admins watch it: begun, its counts and lines as they
    come, and how it ended. Sent from its own thread every REPORT_EVERY seconds;
    what could not be sent goes with the next try. When KIASA answers that an
    admin pressed Stop, `on_stop` is called (once).

    `run` is the run KIASA asked for, or None for a run started here (KIASA
    makes one on the first report)."""

    def __init__(self, client: KiasaClient, run: str | None, cards: int, on_stop=None, log=None):
        self.client = client
        self.run_id = run
        self.cards = int(cards)
        self.on_stop = on_stop or (lambda: None)
        self._log = log or (lambda message, level="info": None)
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._lines: list[dict] = []
        self._stats: dict | None = None
        self._end: dict | None = None
        self._ended_at = 0.0
        self._begun = False
        self._stop_told = False
        self._last_error = ""
        self._thread = threading.Thread(target=self._loop, daemon=True, name="kiasa-run")

    @property
    def alive(self) -> bool:
        """Still KIASA's business: running, or its end not yet told."""
        return self._thread.is_alive() or not self._thread.ident

    def start(self) -> "RunReport":
        self._thread.start()
        return self

    def line(self, text: str, level: str = "info") -> None:
        text = " ".join((text or "").split())
        if not text or level not in SHOWN_LEVELS or text.startswith(("KIASA:", "Google Sheet:")):
            return
        with self._lock:
            self._lines.append({"level": level, "text": text[:300]})
            del self._lines[:-200]  # a long time offline keeps the latest
        if level == "step":
            self._wake.set()

    def stats(self, stats: dict) -> None:
        with self._lock:
            self._stats = {name: int(stats.get(name) or 0) for name in ("saved", "removed", "skipped", "failed", "processed")}

    def finish(self, state: str, message: str = "", wait: float = 15.0) -> bool:
        """End the run on KIASA (done, stopped or failed); True once KIASA has it.
        Waits up to `wait` seconds; after that it goes on trying in the background."""
        with self._lock:
            if self._end is None:
                self._end = {"state": state, "message": (message or "")[:300]}
                self._ended_at = time.monotonic()
        if not self._thread.ident:
            self.start()
        self._wake.set()
        self._thread.join(wait)
        return not self._thread.is_alive()

    def _loop(self) -> None:
        while True:
            try:
                if self._send_once():
                    return  # its end is told
            except NotConnected as exc:
                self._log(f"KIASA: {exc}", "error")
                return
            except Exception as exc:  # noqa: BLE001 - tried again
                message = str(exc)
                if message != self._last_error:
                    self._log(f"KIASA: could not report the run ({message}) - will try again", "warn")
                self._last_error = message
                if self._end is not None and time.monotonic() - self._ended_at > END_PATIENCE:
                    return
            self._wake.wait(REPORT_EVERY)
            self._wake.clear()

    def _send_once(self) -> bool:
        """One report; True when it told KIASA the run's end."""
        with self._lock:
            lines = list(self._lines[:50])
            everything = len(lines) == len(self._lines)
            stats = dict(self._stats) if self._stats else None
            end = dict(self._end) if self._end else None
        report: dict = {"steps": lines}
        if not self._begun:
            report.update(state="running", cards=self.cards)
        if stats:
            report["stats"] = stats
        final = end is not None and everything
        if final:
            report["state"] = end["state"]
            if end["message"]:
                report["message"] = end["message"]
        answer = self.client.report(self.run_id, report)
        self._last_error = ""
        self._begun = True
        if self.run_id is None:
            self.run_id = answer.get("run")
        with self._lock:
            del self._lines[:len(lines)]
        if final:
            return True
        if answer.get("stop") and not self._stop_told and end is None:
            self._stop_told = True
            self.on_stop()
        return False


class RemoteControl:
    """Keeps in touch with KIASA while the bot is connected: checks in every
    CHECK_EVERY seconds with how it is (`status()`: state and detail), and when
    KIASA hands it a run, makes its RunReport and passes both to `on_run` (on
    this thread - the window moves it to its own). `on_status(text, tone)` says
    how the connection is: tone ok, warn or error."""

    def __init__(self, client: KiasaClient, status, on_run, on_status=None, on_stop=None, log=None):
        self.client = client
        self._status = status
        self._on_run = on_run
        self._on_status = on_status or (lambda text, tone: None)
        self._on_stop = on_stop or (lambda: None)
        self._log = log or (lambda message, level="info": None)
        self.report: RunReport | None = None
        self.name = ""
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="kiasa-check-in")

    def start(self) -> "RemoteControl":
        self._thread.start()
        return self

    def close(self) -> None:
        self._closed.set()

    def begin(self, run: str | None, cards: int) -> RunReport:
        """A run's report: one KIASA asked for, or (run None) one started here."""
        self.report = RunReport(self.client, run, cards, on_stop=self._on_stop, log=self._log).start()
        return self.report

    def busy(self) -> bool:
        return bool(self.report and self.report.alive)

    def _loop(self) -> None:
        wait = CHECK_EVERY
        said = ""
        while not self._closed.is_set():
            info = {"computer": socket.gethostname()[:80], "version": __version__}
            info.update(self._status())
            if self.busy():
                info.update(state="busy", running=self.report.run_id)
            try:
                answer = self.client.check_in(info)
            except NotConnected as exc:
                self._on_status(f"KIASA no longer knows this bot: {exc} Paste a new code from KIASA.", "error")
                return
            except Exception as exc:  # noqa: BLE001 - offline: tried again, less often
                text = f"Cannot reach KIASA right now ({exc}). Trying again..."
                if text != said:
                    self._on_status(text, "warn")
                    said = text
                wait = min(CHECK_BACKOFF, wait * 2)
                self._closed.wait(wait)
                continue
            wait = CHECK_EVERY
            name = str(answer.get("name") or "")
            text = f"Connected to KIASA as \"{name}\". KIASA can start, stop and schedule runs."
            if text != said:
                self.name = name
                self._on_status(text, "ok")
                said = text
            run = answer.get("run")
            if isinstance(run, dict) and run.get("id") and info.get("state") != "busy" and not self.busy():
                report = self.begin(str(run["id"]), int(run.get("cards") or 1))
                self._on_run(run, report)
            self._closed.wait(CHECK_EVERY)
