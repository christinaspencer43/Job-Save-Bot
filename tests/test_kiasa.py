"""KIASA: the code, the links, and the bot's calls against a fake KIASA on
127.0.0.1 (safe mode lets the bot talk to nothing else)."""

from __future__ import annotations

import base64
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from jobsavingbot import kiasa

KEY = "kbot_" + "ab" * 32


def make_code(url: str, key: str = KEY, apikey: str = "sb_publishable_test") -> str:
    packed = base64.urlsafe_b64encode(json.dumps({"u": url, "k": apikey, "s": key}).encode()).decode().rstrip("=")
    return kiasa.CODE_PREFIX + packed


class FakeKiasa:
    """KIASA's three job_bot_* functions, in memory."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.waiting: dict | None = None      # a run an admin asked for
        self.runs: dict[str, dict] = {}
        self.jobs: dict[str, dict] = {}
        self.stop: set[str] = set()
        self.lock = threading.Lock()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):  # noqa: N802 - http.server API
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                name = self.path.rsplit("/", 1)[-1]
                if self.headers.get("apikey") != "sb_publishable_test" or body.get("bot_key") != KEY:
                    return self.answer(403, {"code": "28000", "message": "This bot is not connected to KIASA."})
                with fake.lock:
                    fake.calls.append((name, body))
                    answer = getattr(fake, name)(body)
                self.answer(200, answer)

            def answer(self, status, data):
                raw = json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def job_bot_check_in(self, body):
        run = None
        info = body["info"]
        if self.waiting and info.get("state") != "busy" and not info.get("running"):
            run = self.waiting
        return {"name": "Office PC", "run": run}

    def job_bot_report(self, body):
        run, report = body["run"], body["report"]
        if run is None:
            run = f"local-{len(self.runs)}"
        if self.waiting and self.waiting["id"] == run:
            self.waiting = None
        record = self.runs.setdefault(run, {"lines": [], "state": None, "cards": report.get("cards")})
        record["lines"] += [line["text"] for line in report.get("steps", [])]
        record["stats"] = report.get("stats", record.get("stats"))
        record["state"] = report.get("state", record["state"])
        record["message"] = report.get("message", record.get("message"))
        return {"run": run, "stop": run in self.stop}

    def job_bot_add_jobs(self, body):
        added = known = 0
        for job in body["jobs"]:
            if job["url"] in self.jobs:
                known += 1
            else:
                added += 1
                self.jobs[job["url"]] = job
        return {"added": added, "known": known}

    def close(self):
        self.server.shutdown()


@pytest.fixture()
def fake():
    server = FakeKiasa()
    yield server
    server.close()


def wait_for(check, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.05)
    return False


def test_a_code_holds_the_connection():
    connection = kiasa.parse_code("  " + make_code("https://abc.supabase.co/") + "\n")
    assert connection == kiasa.Connection("https://abc.supabase.co", "sb_publishable_test", KEY)
    with pytest.raises(ValueError, match="KIASA-BOT1"):
        kiasa.parse_code("hello")
    with pytest.raises(ValueError, match="copy it again"):
        kiasa.parse_code(make_code("https://abc.supabase.co")[:-12])


@pytest.mark.parametrize("link, kept", [
    ("https://boards.greenhouse.io/acme/jobs/123?utm_source=jobright&gh_src=x#apply",
     "https://boards.greenhouse.io/acme/jobs/123?gh_src=x"),
    ("https://jobs.lever.co/acme/42", "https://jobs.lever.co/acme/42"),
    ("https://www.linkedin.com/jobs/view/data-analyst-at-acme-4012345678?trk=abc", "https://www.linkedin.com/jobs/view/4012345678/"),
    ("https://www.linkedin.com/jobs/search/?currentJobId=4012345678&keywords=x", "https://www.linkedin.com/jobs/view/4012345678/"),
    ("https://www.indeed.com/viewjob?jk=abc123&from=serp", "https://www.indeed.com/viewjob?jk=abc123"),
    ("HTTPS://Careers.Acme.com", "https://careers.acme.com/"),
    ("mailto:jobs@acme.com", ""),
])
def test_links_are_kept_as_kiasa_keeps_them(link, kept):
    assert kiasa.clean_link(link) == kept


def test_a_run_kiasa_asks_for_is_handed_over_reported_and_stopped(fake):
    client = kiasa.KiasaClient(kiasa.parse_code(make_code(fake.url)))
    handed, stopped, statuses = [], threading.Event(), []
    remote = kiasa.RemoteControl(client, status=lambda: {"state": "ready", "detail": ""},
                                 on_run=lambda run, report: handed.append((run, report)),
                                 on_status=lambda text, tone: statuses.append((tone, text)), on_stop=stopped.set)
    fake.waiting = {"id": "run-1", "cards": 5, "origin": "admin"}
    remote.start()
    try:
        assert wait_for(lambda: handed), "the run was not handed over"
        run, report = handed[0]
        assert run["cards"] == 5 and report.run_id == "run-1"
        assert statuses[0] == ("ok", 'Connected to KIASA as "Office PC". KIASA can start, stop and schedule runs.')
        report.line("[1/5] EASY APPLY - Data Analyst", "step")
        report.line("    opened https://jobs.example/1", "info")  # not for KIASA's eyes
        report.stats({"saved": 1, "processed": 1})
        assert wait_for(lambda: fake.runs.get("run-1", {}).get("stats", {}) and fake.runs["run-1"]["stats"]["saved"] == 1)
        assert fake.runs["run-1"]["state"] == "running" and fake.runs["run-1"]["lines"] == ["[1/5] EASY APPLY - Data Analyst"]
        # Busy with it: the check-ins say so, and no run is handed twice.
        time.sleep(kiasa.CHECK_EVERY + 0.5)
        assert len(handed) == 1
        assert any(body["info"].get("state") == "busy" and body["info"].get("running") == "run-1"
                   for name, body in fake.calls if name == "job_bot_check_in")
        fake.stop.add("run-1")
        assert stopped.wait(10), "Stop on KIASA did not reach the bot"
        assert report.finish("stopped", "Stopped from KIASA.")
        assert fake.runs["run-1"]["state"] == "stopped" and fake.runs["run-1"]["message"] == "Stopped from KIASA."
        assert not remote.busy()
    finally:
        remote.close()


def test_a_run_started_here_is_made_on_kiasa(fake):
    client = kiasa.KiasaClient(kiasa.parse_code(make_code(fake.url)))
    report = kiasa.RunReport(client, None, 7).start()
    assert wait_for(lambda: report.run_id is not None)
    assert fake.runs[report.run_id]["cards"] == 7
    assert report.finish("done", "Ended: the list is empty.")
    assert fake.runs[report.run_id]["state"] == "done"


def test_saved_jobs_are_posted_once_even_when_sent_twice(fake, tmp_path):
    client = kiasa.KiasaClient(kiasa.parse_code(make_code(fake.url)))
    logs = []
    outbox = kiasa.KiasaOutbox(client, log=lambda message, level="info": logs.append(message), outbox=tmp_path / "out.jsonl")
    row = {"job_url": "https://jobs.lever.co/acme/1?utm_medium=bot", "title": "Data Analyst", "company": "Acme", "location": "Remote",
           "description": "Analyse data.\nSQL and Python."}
    outbox.add(kiasa.job_for_kiasa(row, "run-9"))
    outbox.add(kiasa.job_for_kiasa(row, "run-9"))
    assert outbox.flush(10)
    assert list(fake.jobs) == ["https://jobs.lever.co/acme/1"]
    assert fake.jobs["https://jobs.lever.co/acme/1"]["run"] == "run-9"
    assert fake.jobs["https://jobs.lever.co/acme/1"]["description"] == "Analyse data.\nSQL and Python."  # for tailored résumés
    assert any(line.startswith("KIASA: added 1 job(s)") for line in logs), logs


def test_jobs_wait_while_kiasa_cannot_be_reached(tmp_path):
    client = kiasa.KiasaClient(kiasa.parse_code(make_code("http://127.0.0.1:9")), timeout=2)
    logs = []
    outbox = kiasa.KiasaOutbox(client, log=lambda message, level="info": logs.append(message), outbox=tmp_path / "out.jsonl")
    outbox.add({"url": "https://jobs.lever.co/acme/1", "title": "", "company": "", "location": "", "run": ""})
    assert not outbox.flush(5)
    assert len(outbox.pending()) == 1
    assert any("could not send 1 job(s)" in line for line in logs)


def test_a_replaced_code_is_told_plainly(fake):
    client = kiasa.KiasaClient(kiasa.parse_code(make_code(fake.url, key="kbot_" + "cd" * 32)))
    with pytest.raises(kiasa.NotConnected, match="not connected"):
        client.check_in({})
    statuses = []
    remote = kiasa.RemoteControl(client, status=lambda: {"state": "ready"}, on_run=lambda run, report: None,
                                 on_status=lambda text, tone: statuses.append(tone)).start()
    assert wait_for(lambda: statuses == ["error"])
    remote.close()


def test_kiasa_is_guarded_in_safe_mode():
    from jobsavingbot.safety import ExternalActionBlocked

    client = kiasa.KiasaClient(kiasa.parse_code(make_code("https://abc.supabase.co")))
    with pytest.raises(ExternalActionBlocked):
        client.check_in({})


def test_each_saved_job_is_handed_to_kiasa(context):
    from test_loop import FakeBridge, build_runner, open_list

    jr = open_list(context)
    runner, lines = build_runner()
    saved = []
    runner._on_saved = saved.append
    runner._loop(jr, FakeBridge(), context, 2)
    assert len(saved) == runner.stats.saved >= 1, lines
    assert all(job["job_url"] and "title" in job and "company" in job for job in saved)


def test_the_window_connects_to_kiasa_and_disconnects(fake):
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtWidgets

    from jobsavingbot.gui import MainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow(poll=False)
    window.show()
    window._connect_kiasa("not a code")
    assert "KIASA-BOT1" in window.kiasa_status_label.text() and window._remote is None

    window._connect_kiasa(make_code(fake.url))
    assert window.settings.kiasa_code.startswith(kiasa.CODE_PREFIX)

    def connected():
        app.processEvents()
        return "Connected to KIASA as \"Office PC\"" in window.kiasa_status_label.text()

    assert wait_for(connected), window.kiasa_status_label.text()
    assert window._kiasa_state() == {"state": "ready", "detail": "Chrome opens when a run starts."}
    window._trouble = ("sign_in", "Jobright wants signing in again in the bot's Chrome.")
    assert window._kiasa_state()["state"] == "sign_in"

    window._disconnect_kiasa()
    assert window._remote is None and window.settings.kiasa_code == "" and window.kiasa_code.text() == ""
    assert "Disconnected" in window.kiasa_status_label.text()
    window.close()
