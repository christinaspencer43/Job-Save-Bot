# Job Saving Bot (portable)

A small Windows app that works down your **Jobright Recommended** list and saves
each employer posting to your board with the **Job Intelligence** (Job JD Scanner)
Chrome extension. It is the Jobright save routine of the agent (`my-agent`'s
"save 10 jobs"), packed so it runs on **any Windows computer**: copy this whole
folder, double-click the `.bat`, done. No fixed `D:\` paths; the extension ships
in the `extension` folder.

## What to copy

The whole folder (`app.py`, `Job Saving Bot.bat`, `jobsavingbot\`, `extension\`,
`google-sheets\`, `requirements.txt`). Leave out `.venv` if it is there - it only works on the
computer that made it (the `.bat` rebuilds it if it was copied anyway).

The other computer needs **Windows 10/11**, **Google Chrome** and an internet
connection. Python 3.10 - 3.14 is needed too; if none is found, the `.bat` offers
to install Python 3.13 with `winget` (or get it from python.org and tick
*Add python.exe to PATH*).

## Start

Double-click **`Job Saving Bot.bat`**. The first time it creates `.venv` in this
folder and installs PySide6 and Playwright (a few minutes). Playwright does not
download a browser: the bot drives the installed Google Chrome.

If the window never shows up, run `Job Saving Bot.bat debug` from a command
prompt in this folder: it keeps a console open with the error.

## First run on a new computer

1. Press **Open Chrome**. This opens the bot's own Chrome, with its own profile at
   `%LOCALAPPDATA%\JobSavingBot\chrome-profile` and debugging port **9444**. The
   normal Chrome is not touched.
2. **Load the extension once.** Chrome 137+ ignores the `--load-extension` flag,
   so in the bot's Chrome window: `chrome://extensions` -> turn on
   **Developer mode** -> **Load unpacked** -> pick this folder's `extension`
   folder (the **Extension folder** button opens it and copies its path).
3. Allow it on all sites: the extension's **Details** -> **Site access** ->
   *On all sites*. Without it most employer pages can't be read; the bot checks
   this and refuses to start until it is on.
4. Sign in to the extension's board account (its popup / Options), so saves reach
   the database. A save only counts once the database confirms it.
5. **Sign in to Jobright** in that window and open *Recommended* jobs. The profile
   keeps both sign-ins for next time.
6. Choose the number of cards (N) and press **Start**.

## What it does per card

For the card at the top of the list, N times (or until the list is empty):

| Card button | What the bot does |
| --- | --- |
| **APPLY WITH AUTOFILL** | Clicks it, Ctrl+clicks **No, Apply Manually** so the posting opens in a background tab, saves that tab with the extension, closes the tab, answers **Yes, I applied!** |
| **EASY APPLY** | Clicks it, presses the panel's **Continue to company site**, saves the employer posting, closes the tab, answers **Yes, I applied!** (never presses *Start to Autofill*) |
| **APPLY NOW** | Opens the card's **...** menu and clicks **Remove From List** |

When the posting is saved but Jobright doesn't ask "Did you apply?" (it often
skips it, Easy Apply above all), the bot closes the panel and removes the card
with **... -> Remove From List** instead, and goes on.

If a save fails, the job stays in the list (the bot answers **No, I didn't
apply** when asked), that card is tried once more and then skipped for the rest
of the run. The run stops after N cards, when the list is empty, or after 5
failures in a row. **Stop** stops at the current step.

The status line counts **Saved / Removed / Skipped / Failed**.

## Where the jobs go

1. **Your board (Supabase)** - always. The extension writes each job to the
   `saved_jobs` table of the Supabase project set in its Options page
   (*Job board sync*: Supabase URL, anon key, your email/password). Set this up
   on every computer, with the same project and account so all saves land in
   one place.
2. **Your Google Sheet** - optional. You give the bot your sheet's link and it
   edits the sheet itself: each saved job becomes a row of a "Saved jobs" tab
   (date, title, company, location, job link, Jobright link, card type, result,
   computer). It edits as a robot Google account (service account): make it
   once and share your sheet with its email as Editor - steps in
   [google-sheets/README.md](google-sheets/README.md). Then, in the bot's
   **3 - Google Sheet** box: **Choose key file...**, paste the sheet link,
   **Save**, **Test**. Rows are sent in the background and wait in
   `%LOCALAPPDATA%\JobSavingBot\sheet_outbox.jsonl` if Google can't be reached.

   `google-key.json` (the robot's key, kept next to `app.py`) travels with the
   folder - keep the folder private.

## Settings

`%LOCALAPPDATA%\JobSavingBot\settings.json` is created on first start:

- `debug_port` (default 9444)
- `run_count`
- `extension_dir` (default: this folder's `extension`), `chrome_path`,
  `profile_dir`, `jobright_url`
- `pause_lo` / `pause_hi` (seconds between cards)
- `page_timeout`, `save_timeout`
- `human_mode` (hover before clicks and skim the posting)
- `focus_browser`
- `accept_local_save` (default `false`): when `true`, a job the extension stored
  locally without syncing to the database also counts as saved.
- `max_attempts_per_card` (2), `max_consecutive_failures` (5)
- `google_sheet_url`, `google_key_file` (empty: `google-key.json` next to
  `app.py`), `google_sheet_secret` (Apps Script only) - the Google Sheet box
  writes them

## Updating the extension

`extension\` is a copy of
`Job JD Scanner\apps\browser-extension\dist\chrome` (version 0.1.0, built
2026-09-26). After a new build, copy that folder over `extension\` again, then
press the reload icon on the extension in `chrome://extensions`.

## Tests

The tests run against local HTML fixtures only. They never touch the live site.

```
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe -m pytest -q
```
