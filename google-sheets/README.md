# Google Sheet - setup

You give the bot **your Google Sheet's link**, and it edits that sheet itself:
every job it saves becomes a row of a **"Saved jobs"** tab (made with its header
row the first time):

| Saved at | Job title | Company | Location | Job link | Jobright link | Card | Result | Computer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

A job link that is already in the tab is not added again, so several computers
can write to the same sheet.

The bot edits the sheet as a **robot Google account** (a "service account"),
which has its own email address like
`job-bot@your-project.iam.gserviceaccount.com`. You share your sheet with that
email, the same way you share with a person, and the bot signs in with the
robot's key file.

## A. Make the robot account (once, about 10 minutes, free)

1. Open <https://console.cloud.google.com> with your Google account. Accept the
   terms if asked. No billing or card is needed for this.
2. Top bar > project picker > **New project**. Name it `Job Saving Bot` >
   **Create**, and make sure it is the selected project.
3. **APIs & Services > Library**, search **Google Sheets API** > **Enable**.
4. **IAM & Admin > Service accounts > + Create service account**. Name it
   `job-bot` > **Create and continue** > skip the optional steps > **Done**.
   (No roles are needed: the robot can only open sheets you share with it.)
5. Click the new account > **Keys** tab > **Add key > Create new key > JSON** >
   **Create**. A `.json` file downloads. This is the robot's key.

## B. Connect the bot (on each computer, 1 minute)

1. In the bot's window, **3 - Google Sheet** box: **Choose key file...** and
   pick that `.json` file. The bot keeps a copy as `google-key.json` next to
   `app.py`, so copying the bot's folder to another computer takes it along.
   The box now shows *Share your sheet (Editor) with: job-bot@...*.
2. **Copy email**. In your Google Sheet: **Share** > paste the email > set
   **Editor** > untick *Notify people* > **Share**.
3. Paste your sheet's link (from the browser address bar,
   `https://docs.google.com/spreadsheets/d/...`) in **Sheet link** > **Save** >
   **Test**. "Connected - My sheet > Saved jobs" means it works.

From now on each saved job is added to the sheet in the background. If the
internet or Google is down, rows wait in
`%LOCALAPPDATA%\JobSavingBot\sheet_outbox.jsonl` and go with the next send or
the next run.

**Keep `google-key.json` private.** Anyone with it can edit the sheets you
shared with the robot (and nothing else). If it ever leaks: Google Cloud >
the service account > Keys > delete that key, then make a new one.

## If Test says...

- *share it with ... as Editor*: the sheet isn't shared with the robot's email,
  or only as Viewer.
- *the Google Sheets API is off*: step A3 for the key's project.
- *not a service account key*: you picked a different JSON (an "OAuth client"
  file). Use the key from step A5.
- *Google refused the key file*: the key was deleted in Google Cloud, or this
  computer's clock is wrong.

## Other way: without Google Cloud (Apps Script)

If you'd rather not make a Google Cloud project, the sheet can do the writing
with a small script instead:

1. In the sheet: **Extensions > Apps Script**, replace `Code.gs` with this
   folder's `Code.gs`, change `const SECRET = 'change-me';` to your own
   password-like text, **Save**.
2. **Deploy > New deployment** > gear > **Web app**. Execute as **Me**, Who has
   access **Anyone** > **Deploy** > authorize (Advanced > Go to project >
   Allow). Copy the **Web app URL** (ends in `/exec`).
3. In the bot: paste that URL in **Sheet link**, the secret in **Secret** >
   **Save** > **Test**.

"Anyone" means anyone with that long URL can call it, which is why the script
checks SECRET. After changing `Code.gs`: **Deploy > Manage deployments > Edit >
Version: New version > Deploy**, so the same URL runs the new code.
