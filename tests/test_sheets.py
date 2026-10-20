"""The Google Sheet export, against a local stand-in for the Apps Script web app."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from conftest import FIXTURE_URL
from test_loop import FakeBridge, build_runner, open_list

from jobsavingbot import sheets
from jobsavingbot.safety import ExternalActionBlocked


class FakeWebApp:
    """Answers like Apps Script: a POST runs doPost, then a 302 to the reply (fetched with GET)."""

    def __init__(self, secret="s3cret", reply_text=None):
        self.secret = secret
        self.rows: list[dict] = []
        self.posts = 0
        self.reply_text = reply_text
        app = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):  # noqa: N802
                app.posts += 1
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
                if body.get("secret") != app.secret:
                    answer = {"ok": False, "error": "wrong secret"}
                elif body.get("test"):
                    answer = {"ok": True, "added": 0, "sheet": "Saved jobs", "rows": len(app.rows)}
                else:
                    known = {r["job_url"] for r in app.rows}
                    added = [r for r in body.get("rows", []) if r["job_url"] not in known]
                    app.rows += added
                    answer = {"ok": True, "added": len(added), "skipped": len(body["rows"]) - len(added)}
                app.last = json.dumps(answer) if app.reply_text is None else app.reply_text
                self.send_response(302)
                self.send_header("Location", "/echo")
                self.end_headers()

            def do_GET(self):  # noqa: N802
                data = app.last.encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/macros/s/x/exec"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture()
def webapp():
    app = FakeWebApp()
    yield app
    app.close()


def row(n):
    return sheets.make_row(f"Engineer {n}", "Acme", f"https://jobs.example/{n}", card="EASY APPLY")


def test_rows_are_sent_and_the_outbox_emptied(webapp):
    logger = sheets.SheetLogger(webapp.url, "s3cret")
    logger.add(row(1))
    logger.add(row(2))
    assert logger.flush(10)
    logger.close()
    assert [r["title"] for r in webapp.rows] == ["Engineer 1", "Engineer 2"]
    assert webapp.rows[0]["company"] == "Acme" and webapp.rows[0]["computer"]
    assert set(webapp.rows[0]) == set(sheets.COLUMNS)
    assert not logger.outbox.exists()


def test_rows_wait_in_the_outbox_while_the_sheet_is_unreachable(webapp):
    logs = []
    down = sheets.SheetLogger("http://127.0.0.1:9/exec", "s3cret", log=lambda m, l="info": logs.append(m))
    down.add(row(1))
    assert not down.flush(10)
    down.close(timeout=1)
    assert len(down.pending()) == 1
    assert any("could not send" in m for m in logs)
    assert any("not sent yet" in m for m in logs)

    # the next run (the sheet is back): the left-over row goes first
    later = sheets.SheetLogger(webapp.url, "s3cret")
    later.start()
    assert later.flush(10)
    later.close()
    assert [r["title"] for r in webapp.rows] == ["Engineer 1"]
    assert later.pending() == []


def test_a_link_already_in_the_sheet_is_not_added_twice(webapp):
    logger = sheets.SheetLogger(webapp.url, "s3cret")
    logger.add(row(1))
    logger.flush(10)
    logger.add(row(1))
    logger.flush(10)
    logger.close()
    assert len(webapp.rows) == 1


def test_wrong_secret_and_non_json_replies_are_reported(webapp):
    with pytest.raises(RuntimeError, match="wrong secret"):
        sheets.check_connection(webapp.url, "nope")
    assert sheets.check_connection(webapp.url, "s3cret")["sheet"] == "Saved jobs"

    login_page = FakeWebApp(reply_text="<html>Sign in - Google Accounts</html>")
    try:
        with pytest.raises(RuntimeError, match="/exec"):
            sheets.check_connection(login_page.url, "s3cret")
    finally:
        login_page.close()


def test_safe_mode_never_sends_to_a_real_host():
    with pytest.raises(ExternalActionBlocked):
        sheets.post("https://script.google.com/macros/s/abc/exec", {"secret": "x", "test": True})


def test_no_url_means_nothing_is_kept_or_sent():
    logger = sheets.SheetLogger("", "")
    assert not logger.enabled
    logger.add(row(1))
    assert not logger.outbox.exists()


def test_each_saved_card_of_a_run_becomes_a_row(context, webapp):
    jr = open_list(context)
    runner, lines = build_runner(google_sheet_url=webapp.url, google_sheet_secret="s3cret")
    runner.sheet = sheets.SheetLogger(webapp.url, "s3cret", log=runner.log)  # build_runner set the URL afterwards

    runner._loop(jr, FakeBridge(), context, 5)
    runner.sheet.close()

    assert runner.stats.saved == 3, lines
    assert len(webapp.rows) == 3, lines  # the 2 APPLY NOW cards are removed, not saved
    assert {r["card"] for r in webapp.rows} == {"APPLY WITH AUTOFILL", "EASY APPLY"}
    assert all("job.html" in r["job_url"] for r in webapp.rows)
    assert any(r["company"].startswith("Fleetio") for r in webapp.rows), webapp.rows
    assert all(r["result"] == "Saved" and r["location"] == "Remote" for r in webapp.rows)
    assert all(r["title"] for r in webapp.rows), "no title from the extension: the card's own is used"
    assert FIXTURE_URL  # the list page itself is never a row
    assert not any(r["job_url"].startswith(FIXTURE_URL) for r in webapp.rows)


# -- the sheet itself, edited as a service account (gspread stood in for) -------------

SHEET_LINK = "https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789/edit#gid=0"


class FakeTab:
    def __init__(self, title="Saved jobs"):
        self.title = title
        self.grid: list[list[str]] = []
        self.frozen = 0
        self.append_options = {}
        self.spreadsheet = type("Book", (), {"title": "My job hunt"})()

    def row_values(self, n):
        return self.grid[n - 1] if len(self.grid) >= n else []

    def update(self, values, range_name):
        assert range_name == "A1"
        self.grid[:1] = [list(values[0])]

    def freeze(self, rows):
        self.frozen = rows

    def format(self, rng, fmt):
        pass

    def col_values(self, n):
        return [r[n - 1] for r in self.grid if len(r) >= n]

    def append_rows(self, rows, **options):
        self.append_options = options
        self.grid += [list(r) for r in rows]


class FakeBook:
    def __init__(self, tabs=()):
        self.tabs = {t.title: t for t in tabs}

    def worksheet(self, name):
        import gspread
        if name not in self.tabs:
            raise gspread.WorksheetNotFound(name)
        return self.tabs[name]

    def add_worksheet(self, name, rows, cols):
        assert cols == len(sheets.HEADERS)
        self.tabs[name] = FakeTab(name)
        return self.tabs[name]


@pytest.fixture()
def key_file(tmp_path):
    path = tmp_path / "google-key.json"
    path.write_text(json.dumps({"type": "service_account", "client_email": "job-bot@proj.iam.gserviceaccount.com",
                                "private_key": "x"}), encoding="utf-8")
    return path


@pytest.fixture()
def fake_google(monkeypatch):
    """gspread.service_account(...).open_by_url(...) -> one fake sheet; safe mode off (nothing leaves the test)."""
    import gspread

    book = FakeBook()
    opened = []

    class Client:
        def open_by_url(self, url):
            opened.append(url)
            return book

    monkeypatch.setattr(gspread, "service_account", lambda filename: Client())
    sheets._worksheets.clear()
    from jobsavingbot import safety
    safety.set_safe_mode(False)
    yield book, opened
    sheets._worksheets.clear()


def test_a_sheet_link_is_edited_directly(fake_google, key_file):
    book, opened = fake_google
    logger = sheets.SheetLogger(SHEET_LINK, key_file=key_file)
    logger.add(row(1))
    logger.add(sheets.make_row('=IMPORTXML("http://evil")', "Acme", "https://jobs.example/2"))
    assert logger.flush(10)
    logger.add(row(1))  # the same link again: not a second row
    assert logger.flush(10)
    logger.close()

    tab = book.tabs["Saved jobs"]
    assert tab.grid[0] == list(sheets.HEADERS) and tab.frozen == 1, "the tab and its header row were made"
    assert [r[sheets.LINK_COLUMN - 1] for r in tab.grid[1:]] == ["https://jobs.example/1", "https://jobs.example/2"]
    assert tab.grid[1][1] == "Engineer 1" and tab.grid[1][2] == "Acme"
    assert tab.append_options["value_input_option"] == "RAW", "page text is never run as a formula"
    assert opened == [SHEET_LINK], "the sheet is opened once and kept open"
    assert not logger.outbox.exists()


def test_an_existing_tab_keeps_its_rows(fake_google, key_file):
    book, _ = fake_google
    tab = FakeTab()
    tab.grid = [list(sheets.HEADERS), ["d", "Old job", "Co", "", "https://jobs.example/1"]]
    book.tabs["Saved jobs"] = tab
    reply = sheets.append_to_sheet(SHEET_LINK, key_file, [row(1), row(3)])
    assert reply == {"ok": True, "added": 1, "skipped": 1}
    assert len(tab.grid) == 3 and tab.grid[1][1] == "Old job"
    info = sheets.check_connection(SHEET_LINK, key_file=key_file)
    assert info["sheet"] == "My job hunt > Saved jobs" and info["rows"] == 2


def test_a_sheet_not_shared_with_the_robot_says_so(monkeypatch, key_file):
    import gspread

    class Client:
        def open_by_url(self, url):
            raise gspread.SpreadsheetNotFound("not found")

    monkeypatch.setattr(gspread, "service_account", lambda filename: Client())
    from jobsavingbot import safety
    safety.set_safe_mode(False)
    sheets._worksheets.clear()
    logs = []
    logger = sheets.SheetLogger(SHEET_LINK, key_file=key_file, log=lambda m, l="info": logs.append(m))
    logger.add(row(1))
    assert not logger.flush(10)
    logger.close(timeout=1)
    assert any("share it with job-bot@proj.iam.gserviceaccount.com as Editor" in m for m in logs), logs
    assert len(logger.pending()) == 1, "the row waits for the share"


def test_key_file_problems_are_explained(tmp_path):
    with pytest.raises(ValueError, match="no key file"):
        sheets.key_email(tmp_path / "missing.json")
    oauth = tmp_path / "client.json"
    oauth.write_text(json.dumps({"installed": {"client_id": "x"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="not a service account key"):
        sheets.key_email(oauth)
    assert "no key file" in sheets.explain(RuntimeError("x"), tmp_path / "missing.json")


def test_sheet_api_switched_off_is_explained(key_file):
    text = sheets.explain(RuntimeError("Google Sheets API has not been used in project 123 before or it is disabled"),
                          key_file)
    assert "Google Sheets API" in text and "Enable" in text


def test_safe_mode_never_opens_a_real_sheet(key_file):
    with pytest.raises(ExternalActionBlocked):
        sheets.append_to_sheet(SHEET_LINK, key_file, [row(1)])


def test_links_are_told_apart():
    assert sheets.is_sheet_link(SHEET_LINK) and not sheets.is_web_app(SHEET_LINK)
    assert sheets.is_web_app("https://script.google.com/macros/s/AKfycbx/exec")
    assert not sheets.is_sheet_link("https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123/edit")
