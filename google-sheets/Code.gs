/**
 * Job Saving Bot -> Google Sheet.
 *
 * Paste this whole file into your sheet's Extensions > Apps Script (replace
 * what is there), change SECRET below, then Deploy > New deployment > Web app,
 * Execute as: Me, Who has access: Anyone. Put the web app URL (ending in /exec)
 * and the same SECRET in the bot. Full steps: google-sheets/README.md.
 *
 * Each saved job becomes one row of the "Saved jobs" tab. A job link that is
 * already in the tab is not added again.
 */

// Change this to your own password-like text, and type the same in the bot.
const SECRET = 'change-me';

const SHEET_NAME = 'Saved jobs';
const HEADERS = ['Saved at', 'Job title', 'Company', 'Location', 'Job link', 'Jobright link', 'Card', 'Result', 'Computer'];
const KEYS = ['saved_at', 'title', 'company', 'location', 'job_url', 'jobright_url', 'card', 'result', 'computer'];
const LINK_COLUMN = KEYS.indexOf('job_url') + 1;

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000); // two computers sending at once: one after the other
  try {
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    if (SECRET === 'change-me' || body.secret !== SECRET) {
      return reply({ ok: false, error: SECRET === 'change-me' ? 'set SECRET in the script first' : 'wrong secret' });
    }
    const sheet = savedJobsSheet();
    if (body.test) return reply({ ok: true, added: 0, sheet: sheet.getName(), rows: sheet.getLastRow() - 1 });

    const rows = Array.isArray(body.rows) ? body.rows : [];
    const last = sheet.getLastRow();
    const known = new Set(last > 1
      ? sheet.getRange(2, LINK_COLUMN, last - 1, 1).getValues().map((r) => String(r[0]))
      : []);
    const add = [];
    for (const row of rows) {
      const link = String(row.job_url || '');
      if (link && known.has(link)) continue;
      known.add(link);
      add.push(KEYS.map((key) => cell(row[key])));
    }
    if (add.length) sheet.getRange(sheet.getLastRow() + 1, 1, add.length, KEYS.length).setValues(add);
    return reply({ ok: true, added: add.length, skipped: rows.length - add.length });
  } catch (err) {
    return reply({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

// Opening the /exec URL in a browser shows this, to check the deployment works.
function doGet() {
  return reply({ ok: true, info: 'Job Saving Bot sheet web app is running. The bot sends rows with POST.' });
}

function savedJobsSheet() {
  const book = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = book.getSheetByName(SHEET_NAME) || book.insertSheet(SHEET_NAME);
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(HEADERS);
    sheet.setFrozenRows(1);
    sheet.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold');
  }
  return sheet;
}

// Text from job pages is never run as a formula ("=...", "+...", "@...").
function cell(value) {
  const text = value === null || value === undefined ? '' : String(value);
  return /^[=+\-@]/.test(text) ? "'" + text : text;
}

function reply(object) {
  return ContentService.createTextOutput(JSON.stringify(object)).setMimeType(ContentService.MimeType.JSON);
}
