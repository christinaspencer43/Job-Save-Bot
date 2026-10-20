"""Reading and driving the Jobright recommended-jobs list.

Jobright ships hashed class names, so everything here keys off visible text and
element geometry instead. The one structural assumption is the one the page
makes visually: each job card has its action button, and its "..." menu sits in
the card's top-right corner.

Copied from Job Save Bot's jobsavebot/jobright.py unchanged (the selectors
and waits are the ones proven on the live site); only `shows_sign_in` was
added.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

from .safety import guard

AUTOFILL = "autofill"
APPLY_NOW = "apply_now"
#: A card whose button reads EASY APPLY: it opens Jobright's own apply
#: panel, and the employer's posting is one "Continue to company site"
#: click further on (2026-09-21).
EASY_APPLY = "easy_apply"

# Marks the element so Playwright can address it without a brittle selector.
MARK_ATTR = "data-jsb-mark"

FIND_TOP_ACTION = """
(args) => {
  const markAttr = args.markAttr;
  const skip = new Set(args.skip || []);
  const seen = document.querySelectorAll('[' + markAttr + ']');
  seen.forEach((el) => el.removeAttribute(markAttr));

  const visible = (el) => {
    const rect = el.getBoundingClientRect();
    if (rect.width < 4 || rect.height < 4) return false;
    const style = getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none' && style.opacity !== '0';
  };

  const clickable = Array.from(
    document.querySelectorAll('button, a, [role="button"], div[class*="btn" i], span[class*="btn" i]')
  );

  const matches = [];
  for (const el of clickable) {
    const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
    if (!text || text.length > 40) continue;
    let kind = null;
    if (text.includes('apply with autofill')) kind = 'autofill';
    else if (text === 'apply now' || text.includes('apply now')) kind = 'apply_now';
    // The card's own button - never the open panel's "Turn off Easy Apply".
    else if (text.includes('easy apply') && !/turn (off|on)/.test(text)) kind = 'easy_apply';
    if (!kind) continue;
    if (!visible(el)) continue;
    // Skip anything sitting in a modal or fixed overlay.
    if (el.closest('[role="dialog"]')) continue;
    const rect = el.getBoundingClientRect();
    matches.push({ el, kind, top: rect.top + window.scrollY });
  }

  if (!matches.length) return null;

  // A nested button can match twice; prefer the innermost.
  const filtered = matches.filter(
    (m) => !matches.some((other) => other !== m && m.el.contains(other.el))
  );
  filtered.sort((a, b) => a.top - b.top);

  // Walk up to the card: the first ancestor that is clearly taller and wider
  // than the button itself and holds the whole listing row.
  const cardOf = (el) => {
    const buttonRect = el.getBoundingClientRect();
    let card = el;
    let node = el.parentElement;
    let hops = 0;
    while (node && hops < 12) {
      const rect = node.getBoundingClientRect();
      if (rect.height > buttonRect.height * 2.5 && rect.width > buttonRect.width * 1.8) {
        card = node;
        if (rect.height > 120) break;
      }
      node = node.parentElement;
      hops += 1;
    }
    return card;
  };

  const sigOf = (card) =>
    (card.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 160);

  let chosen = null;
  let skipped = 0;
  for (const match of filtered) {
    const card = cardOf(match.el);
    const signature = sigOf(card);
    if (skip.has(signature)) {
      skipped += 1;
      continue;
    }
    chosen = { match, card, signature };
    break;
  }

  if (!chosen) return { exhausted: true, skipped };

  chosen.match.el.setAttribute(markAttr, 'action');
  chosen.card.setAttribute(markAttr, 'card');

  const cardRect = chosen.card.getBoundingClientRect();
  // What the card says the job is, for checking the employer's page against
  // it later (Stage 04). Read from the card's own elements where it has
  // them; left empty rather than guessed where it does not.
  const say = (el) => (el ? (el.innerText || el.textContent || '') : '').replace(/\\s+/g, ' ').trim();
  const heading = chosen.card.querySelector('h1, h2, h3, h4, [class*="title" i]');
  const employer = chosen.card.querySelector('[class*="company" i], [class*="employer" i]');
  const jobLink = Array.from(chosen.card.querySelectorAll('a[href]'))
    .map((a) => a.href)
    .find((h) => {
      try { return /\\/jobs?\\/(info\\/)?[A-Za-z0-9_-]{8,}/.test(new URL(h, location.href).pathname); }
      catch (e) { return false; }
    }) || '';
  return {
    kind: chosen.match.kind,
    signature: chosen.signature,
    title: chosen.signature.slice(0, 90),
    heading: say(heading).slice(0, 160),
    company: say(employer).slice(0, 120),
    link: jobLink,
    sourceUrl: location.href,
    cardHeight: Math.round(cardRect.height),
    skipped,
  };
}
"""

FIND_KEBAB = """
(markAttr) => {
  const card = document.querySelector('[' + markAttr + '="card"]');
  if (!card) return null;
  const cardRect = card.getBoundingClientRect();

  // The "..." is not inside the visual card. Jobright puts it in the row
  // wrapper that also holds the match-score panel, so the search widens to
  // that wrapper - but never far enough to reach the next job.
  let scope = card;
  let node = card.parentElement;
  for (let i = 0; i < 4 && node; i++) {
    const rect = node.getBoundingClientRect();
    if (rect.height > cardRect.height * 1.6) break;
    scope = node;
    node = node.parentElement;
  }

  const visible = (el) => {
    const rect = el.getBoundingClientRect();
    if (rect.width < 4 || rect.height < 4) return false;
    const style = getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none' && style.opacity !== '0';
  };

  // Icon buttons that sit next to the "..." and must never be clicked.
  const NEGATIVE = /like|heart|favou?rite|save|bookmark|hide|dislike|block|thumb|not.?interest|close/i;
  const POSITIVE = /more|ellipsis|overflow|kebab|dots?\\b/i;

  const candidates = [];
  for (const el of scope.querySelectorAll('*')) {
    if (!visible(el)) continue;
    const rect = el.getBoundingClientRect();
    if (rect.width > 70 || rect.height > 70) continue;

    const text = (el.innerText || el.textContent || '').replace(/\\s+/g, '').trim();
    const cls = String(
      el.className && el.className.baseVal !== undefined ? el.className.baseVal : (el.className || '')
    );
    const label = (el.getAttribute('aria-label') || '') + ' ' + (el.id || '') + ' ' + cls;
    const use = el.querySelector('use');
    const href = use ? (use.getAttribute('href') || '') : '';

    let score = 0;
    // The sprite name is the strongest signal available.
    if (POSITIVE.test(href)) score += 8;
    if (POSITIVE.test(label)) score += 5;
    if (/dropdown-trigger|dropdown-but/i.test(cls)) score += 5;
    if (text === '...' || text === '\\u2026' || text === '\\u22ef' || text === '\\u2022\\u2022\\u2022') score += 6;
    if (NEGATIVE.test(label) || NEGATIVE.test(href)) score -= 12;

    // It sits in the card's top-right corner.
    const fromRight = cardRect.right - rect.right;
    const fromTop = rect.top - cardRect.top;
    if (fromRight < cardRect.width * 0.25 && fromTop < Math.max(60, cardRect.height * 0.35)) {
      score += 4;
    }
    if (getComputedStyle(el).cursor === 'pointer') score += 1;

    // A lone corner position is not enough; require a real signal.
    if (score <= 4) continue;
    candidates.push({ el, score, fromRight, fromTop });
  }

  if (!candidates.length) return null;
  candidates.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    if (a.fromTop !== b.fromTop) return a.fromTop - b.fromTop;
    return a.fromRight - b.fromRight;
  });

  const best = candidates[0];
  // Click the button itself when the match is a wrapper around one.
  let target = best.el;
  const inner = target.querySelector('button, [role="button"]');
  if (inner && inner.getBoundingClientRect().width >= 12) target = inner;

  target.setAttribute(markAttr, 'kebab');
  return { score: best.score, tag: target.tagName.toLowerCase() };
}
"""

DUMP_CARD = """
(markAttr) => {
  const card = document.querySelector('[' + markAttr + '="card"]');
  if (!card) return 'no marked card';
  return card.outerHTML.slice(0, 6000);
}
"""


@dataclass
class TopCard:
    kind: str
    signature: str
    title: str
    card_height: int
    # What the card itself names (Stage 04); "" where it does not say.
    heading: str = ""
    company: str = ""
    link: str = ""
    source_url: str = ""


class JobrightPage:
    """Everything the bot does on the Jobright tab."""

    def __init__(self, page, timeout_ms: int = 30000, human: bool = True):
        self.page = page
        self.timeout = timeout_ms
        # When true, every click is preceded by a visible hover and a pause.
        self.human = human

    # -- reading -----------------------------------------------------------

    def top_card(self, skip: list[str] | None = None) -> TopCard | None:
        data = self.page.evaluate(
            FIND_TOP_ACTION, {"markAttr": MARK_ATTR, "skip": list(skip or [])}
        )
        if not data or data.get("exhausted"):
            return None
        return TopCard(
            kind=data["kind"],
            signature=data.get("signature", ""),
            title=data.get("title", ""),
            card_height=int(data.get("cardHeight") or 0),
            heading=data.get("heading", "") or "",
            company=data.get("company", "") or "",
            link=data.get("link", "") or "",
            source_url=data.get("sourceUrl", "") or "",
        )

    def marked_card_signature(self) -> str | None:
        """The text of the card picked by top_card, now; None if it is gone.

        Jobright redraws its list in place. The card element picked for job A
        can be showing job B a moment later, with no navigation at all.
        """
        try:
            return self.page.evaluate(
                """(markAttr) => {
                  const card = document.querySelector('[' + markAttr + '="card"]');
                  if (!card || !card.isConnected) return null;
                  return (card.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 160);
                }""",
                MARK_ATTR,
            )
        except Exception:
            return None

    def dump_top_card_html(self) -> str:
        return self.page.evaluate(DUMP_CARD, MARK_ATTR)

    def action_button(self):
        return self.page.locator(f'[{MARK_ATTR}="action"]')

    def card(self):
        return self.page.locator(f'[{MARK_ATTR}="card"]')

    def wait_for_list(self) -> bool:
        deadline = self.timeout
        try:
            self.page.wait_for_function(
                """(markAttr) => !!document.body && document.body.innerText.toLowerCase().includes('apply')""",
                arg=MARK_ATTR,
                timeout=deadline,
            )
            return True
        except Exception:
            return False

    def shows_sign_in(self) -> bool:
        """True when the Jobright tab asks to sign in instead of listing jobs."""
        url = (self.page.url or "").lower()
        if any(part in url for part in ("/login", "/signin", "/sign-in", "/signup", "/sign-up")):
            return True
        try:
            return bool(self.page.evaluate(
                """() => {
                  const visible = (el) => {
                    const r = el.getBoundingClientRect();
                    if (r.width < 4 || r.height < 4) return false;
                    const s = getComputedStyle(el);
                    return s.display !== 'none' && s.visibility !== 'hidden';
                  };
                  const controls = Array.from(document.querySelectorAll('button, a, [role="button"]'));
                  const hasJobs = controls.some((el) => visible(el)
                    && /apply with autofill|apply now|easy apply/i.test(el.innerText || ''));
                  if (hasJobs) return false;
                  if (Array.from(document.querySelectorAll('input[type="password"]')).some(visible)) return true;
                  return controls.some((el) => visible(el)
                    && /^\\s*(sign in|log in|sign up|continue with google)\\s*$/i.test(el.innerText || ''));
                }"""
            ))
        except Exception:
            return False

    def applied_count(self) -> int | None:
        """The number next to the 'Applied' tab, used as a sanity check."""
        try:
            value = self.page.evaluate(
                """() => {
                  const nodes = Array.from(document.querySelectorAll('*'));
                  for (const el of nodes) {
                    if (el.children.length > 3) continue;
                    const text = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                    const match = /^Applied\\s+(\\d{1,6})$/i.exec(text);
                    if (match) return parseInt(match[1], 10);
                  }
                  return null;
                }"""
            )
            return int(value) if value is not None else None
        except Exception:
            return None

    # -- acting ------------------------------------------------------------

    def _human_click(self, locator, modifiers=None) -> None:
        """Move to the control and pause before clicking, the way a person does.

        Beyond looking right, hovering first makes the run watchable: you can
        see which control is about to be used.
        """
        if self.human:
            try:
                locator.scroll_into_view_if_needed(timeout=self.timeout)
                locator.hover(timeout=self.timeout)
                self.page.wait_for_timeout(random.randint(220, 480))
            except Exception:
                pass
        if modifiers:
            locator.click(modifiers=modifiers, timeout=self.timeout)
        else:
            locator.click(timeout=self.timeout)

    def click_action(self) -> None:
        self._human_click(self.action_button())

    def _visible_text(self, text):
        """The on-screen match for some text.

        Jobright renders a hidden copy of these controls for every card, so
        matching on text alone picks an invisible one.
        """
        return self.page.get_by_text(text, exact=False).filter(visible=True).first

    def autofill_modal(self):
        return self._visible_text("No, Apply Manually")

    def wait_for_autofill_modal(self, timeout_ms: int) -> bool:
        try:
            self.autofill_modal().wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def ctrl_click_apply_manually(self) -> None:
        self._human_click(self.autofill_modal(), modifiers=["Control"])

    #: The panel's way out to the employer's own posting. Worded a few ways
    #: across builds: "Continue to company site", "Continue on company
    #: site", "Apply on company site", "Go to company site".
    COMPANY_SITE = re.compile(
        r"(continue|apply|go)\s+(to|on|at)?\s*(the\s+)?(company|employer)(.s)?\s*(site|website|page)",
        re.IGNORECASE,
    )

    def company_site_button(self):
        return self.page.get_by_role("button", name=self.COMPANY_SITE).filter(
            visible=True
        ).or_(
            self.page.get_by_role("link", name=self.COMPANY_SITE).filter(visible=True)
        ).or_(
            self.page.get_by_text(self.COMPANY_SITE).filter(visible=True)
        ).first

    def wait_for_company_site_button(self, timeout_ms: int) -> bool:
        try:
            self.company_site_button().wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def click_company_site(self) -> None:
        self._human_click(self.company_site_button())

    def did_you_apply_modal(self):
        return self._visible_text("Yes, I applied")

    def wait_for_did_you_apply(self, timeout_ms: int) -> bool:
        try:
            self.did_you_apply_modal().wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def click_yes_applied(self) -> None:
        guard("jobright", self.page.url, "answer Yes, I applied")
        self._human_click(self.did_you_apply_modal())

    def click_didnt_apply(self) -> bool:
        """Used when the save failed, so the job stays in the list."""
        guard("jobright", self.page.url, "answer I didn't apply")
        # The apostrophe may be typographic, so match around it.
        pattern = re.compile(r"didn.{0,2}t apply", re.IGNORECASE)
        try:
            self.page.get_by_text(pattern).filter(visible=True).first.click(
                timeout=5000
            )
            self.page.wait_for_timeout(250)
            return True
        except Exception:
            # No recovery here: close_any_dialog() is the caller's job and
            # calling it back from this method would recurse.
            return False

    def open_kebab(self) -> bool:
        found = self.page.evaluate(FIND_KEBAB, MARK_ATTR)
        if not found:
            return False
        kebab = self.page.locator(f'[{MARK_ATTR}="kebab"]')
        try:
            self._human_click(kebab)
            return True
        except Exception:
            return False

    def click_remove_from_list(self, timeout_ms: int) -> bool:
        guard("jobright", self.page.url, "remove a job from the list")
        item = self._visible_text("Remove From List")
        try:
            item.wait_for(state="visible", timeout=timeout_ms)
            self._human_click(item)
            return True
        except Exception:
            return False

    def modal_is_open(self) -> bool:
        """Any dialog covering the list blocks every click underneath it."""
        try:
            return bool(
                self.page.evaluate(
                    """() => {
                      const sel = '[role="dialog"], .ant-modal-wrap, .ant-modal';
                      for (const el of document.querySelectorAll(sel)) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width < 40 || rect.height < 40) continue;
                        const style = getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden') continue;
                        if (style.opacity === '0') continue;
                        return true;
                      }
                      return false;
                    }"""
                )
            )
        except Exception:
            return False

    def dropdown_is_open(self) -> bool:
        try:
            return self.page.locator(".ant-dropdown").filter(visible=True).count() > 0
        except Exception:
            return False

    def close_dropdown(self) -> bool:
        """Dismiss an open "..." menu.

        Escape does not close it and left open it covers the next card, so
        this clicks a harmless spot outside it. The close is animated, so the
        result is polled rather than assumed.
        """
        try:
            for _ in range(3):
                if not self.dropdown_is_open():
                    return True
                self.page.mouse.click(8, 8)
                self.page.wait_for_timeout(350)
            return not self.dropdown_is_open()
        except Exception:
            return False

    def close_any_dialog(self) -> bool:
        """Clear a stuck modal, so one bad card cannot wedge every later one.

        Escape alone does not close the "Did you apply?" dialog, so its own
        decline button is used first.
        """
        self.close_dropdown()
        if not self.modal_is_open():
            return True

        self.click_didnt_apply()
        if not self.modal_is_open():
            return True

        for _ in range(2):
            try:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(250)
            except Exception:
                break
            if not self.modal_is_open():
                return True

        # Last resort: the dialog's own close control.
        try:
            self.page.locator(
                '[role="dialog"] [aria-label*="close" i], .ant-modal-close'
            ).filter(visible=True).first.click(timeout=2000)
            self.page.wait_for_timeout(250)
        except Exception:
            pass
        return not self.modal_is_open()

    def wait_until_card_changed(self, previous_signature: str, timeout_ms: int) -> bool:
        """True once the processed card is gone from the top of the list."""
        try:
            self.page.wait_for_function(
                """({ markAttr, previous }) => {
                  const card = document.querySelector('[' + markAttr + '="card"]');
                  if (!card || !card.isConnected) return true;
                  const rect = card.getBoundingClientRect();
                  if (rect.width < 4 || rect.height < 4) return true;
                  const now = (card.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 160);
                  return now !== previous;
                }""",
                arg={"markAttr": MARK_ATTR, "previous": previous_signature},
                timeout=timeout_ms,
            )
            return True
        except Exception:
            return False
