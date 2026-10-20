"""The Jobright page logic against the mock card list (ported test_fixture.py)."""

from __future__ import annotations

from conftest import FIXTURE_URL

from jobsavingbot.jobright import APPLY_NOW, AUTOFILL, EASY_APPLY, JobrightPage


def test_cards_are_read_removed_and_applied_on_the_mock_list(context):
    page = context.new_page()
    page.goto(FIXTURE_URL)
    jr = JobrightPage(page, timeout_ms=5000, human=False)

    assert jr.wait_for_list()
    assert not jr.shows_sign_in()

    top = jr.top_card()
    assert top is not None and top.kind == AUTOFILL
    assert "Principal Engineer I, Data" in top.signature
    assert 100 < top.card_height < 400, top.card_height
    assert jr.applied_count() == 187

    # Skipping the first card surfaces the second, which is APPLY NOW.
    second = jr.top_card(skip=[top.signature])
    assert second is not None and second.signature != top.signature
    assert second.kind == APPLY_NOW and "RENFROE" in second.signature

    # Kebab detection and Remove From List on that APPLY NOW card.
    assert jr.open_kebab()
    assert jr.click_remove_from_list(3000)
    assert jr.wait_until_card_changed(second.signature, 3000)
    page.wait_for_timeout(200)
    assert "RENFROE" not in page.inner_text("#list")

    # Back to the autofill flow on the (still first) CareMetx card.
    top = jr.top_card()
    assert top.kind == AUTOFILL
    jr.click_action()
    assert jr.wait_for_autofill_modal(3000)
    before = set(context.pages)
    jr.ctrl_click_apply_manually()
    page.wait_for_timeout(600)
    opened = [p for p in context.pages if p not in before]
    assert len(opened) == 1, "Ctrl+click should open exactly one background tab"
    assert page.evaluate("() => window.__ctrlUsed === true")

    assert jr.wait_for_did_you_apply(3000)
    jr.click_yes_applied()
    assert jr.wait_until_card_changed(top.signature, 3000)
    page.wait_for_timeout(200)
    assert "CareMetx" not in page.inner_text("#list")
    assert jr.top_card() is not None


def test_the_easy_apply_card_and_its_company_site_button(context):
    page = context.new_page()
    page.goto(FIXTURE_URL)
    jr = JobrightPage(page, timeout_ms=5000, human=False)
    skip = []
    top = jr.top_card()
    while top is not None and top.kind != EASY_APPLY:
        skip.append(top.signature)
        top = jr.top_card(skip=skip)
    assert top is not None and "Marketplace Payments" in top.signature
    assert jr.action_button().inner_text().strip() == "EASY APPLY"
    jr.click_action()
    assert jr.wait_for_company_site_button(3000)
    assert jr.company_site_button().inner_text().strip() == "Continue to company site"


JOBRIGHT_EASY_APPLY = """
<div style="display:flex">
  <main style="width:600px">
    <div class="card" style="height:200px;width:560px;border:1px solid">
      <h3>Senior Software Engineer, Marketplace Payments</h3>
      <p>Fleetio - Remote</p>
      <button style="width:120px;height:36px">EASY APPLY</button>
    </div>
    <div class="card" style="height:200px;width:560px;border:1px solid">
      <h3>Backend Engineer</h3>
      <p>Acme - Remote</p>
      <button style="width:120px;height:36px">APPLY NOW</button>
    </div>
  </main>
  <aside style="width:600px">
    <h2>Easy Apply</h2>
    <button style="width:160px;height:36px">Turn off Easy Apply</button>
    <button style="width:160px;height:36px">Start to Autofill</button>
    <button style="width:160px;height:36px">Continue to company site</button>
    <button style="width:160px;height:36px">Submit application</button>
  </aside>
</div>
"""


def test_an_easy_apply_card_is_picked_up_and_its_panel_leads_out(context):
    """Ported from test_steps.py: only the company-site button is a way out."""
    page = context.new_page()
    page.set_viewport_size({"width": 1300, "height": 900})
    page.set_content(JOBRIGHT_EASY_APPLY)
    jr = JobrightPage(page, timeout_ms=3000, human=False)

    top = jr.top_card()
    assert top is not None and top.kind == EASY_APPLY, top
    assert "Marketplace Payments" in top.title
    assert jr.action_button().inner_text().strip() == "EASY APPLY"
    assert jr.wait_for_company_site_button(2000)
    assert jr.company_site_button().inner_text().strip() == "Continue to company site"
    for never in ("Turn off Easy Apply", "Submit application", "APPLY NOW", "Start to Autofill"):
        assert not JobrightPage.COMPANY_SITE.search(never), never


SIGN_IN = """
<h1>Welcome to Jobright</h1>
<input type="email" style="width:200px;height:30px">
<input type="password" style="width:200px;height:30px">
<button style="width:120px;height:36px">Sign in</button>
"""


def test_a_sign_in_page_is_recognised(context):
    page = context.new_page()
    page.set_content(SIGN_IN)
    assert JobrightPage(page, timeout_ms=2000, human=False).shows_sign_in()
