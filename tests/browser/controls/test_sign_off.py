"""Sign-off approval and the obligations it joins: where the control stands, how a press
records, is taken back or refused, and when it waits."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    SEATED_OBLIGATION_LAYER,
    SEATED_OBLIGATION_WIDGETS,
    live_url,
)
from render_cases_navigation import actions
from render_harness import (
    LONG_PAGE,
    _traffic,
    expect_obligations_answered,
    holding,
    leaf_page,
    open_page,
    panel_control,
    panel_menu,
    panel_settled,
    resized,
    round_trip,
    told,
)

from leaf import event_log as events_model
from leaf.render_checks import wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed

SIGN_OFF = LONG_PAGE.replace(
    "<title>long</title>",
    '<title>long</title><meta name="lf-review" content="sign-off">',
)


# The approval's control in the leaf's menu, under Versions (floating-panel.js).
APPROVAL = ".lf-fp-approval"


def test_sign_off_stands_through_a_draft_and_moves_nothing(browser, serve):
    """Approval stands under Versions wherever the page declares sign-off, stamped or
    not, and a draft arriving moves nothing on the page. Before a stamp the press is
    refused and says why."""
    page = open_page(browser, live_url(serve(SIGN_OFF)))
    resized(page, 560, 800)
    expect(panel_control(page, "approval")).to_be_enabled()
    page.locator(".lf-fp-leaf").click()
    top = page.evaluate(
        "() => document.querySelector('main').getBoundingClientRect().top"
    )
    (serve.page_dir / "index.html").write_text(
        SIGN_OFF.replace("</main>", "<p>A draft's new paragraph.</p></main>")
    )
    told(page)
    # The menu holds the rows it opened with, so it opens once the draft has arrived.
    approval = panel_control(page, "approval")
    expect(approval).to_be_disabled()
    expect(page.locator(APPROVAL)).to_have_attribute(
        "title", "There is no stamped version to approve yet"
    )
    after = page.evaluate(
        "() => document.querySelector('main').getBoundingClientRect().top"
    )
    assert after == pytest.approx(top, abs=1), (top, after)


def test_a_page_asking_for_sign_off_records_the_approval(browser, serve):
    """The declared obligation puts the approval there, and the press posts `done`, once
    however often it is pressed while the first is on its way.

    Drive the shipped browser through the real POST door, since a control that merely
    looks right says nothing about the event the agent's loop receives.
    """
    page = open_page(browser, serve(SIGN_OFF))
    button = panel_control(page, "approval")
    expect(button).to_contain_text("Approve version")
    expect(button).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    button.click()
    holding(page, held, 1, "the approval")
    button.dispatch_event("click")
    assert _traffic(page).sends == 1, "one approval press became two log events"

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    event = events_model.read_events(serve.page_dir)[-1]
    assert (event["kind"], event["author"], event["version"]) == ("done", "user", 1)


def test_an_approval_can_be_taken_back_like_any_other_user_gesture(browser, serve):
    """Approval and its obligation agree during send, undo and refusal.

    Holding each POST proves the result is visible before admission; a definitive
    refusal restores the same admitted approval through every consumer: the row's word
    that the version is approved, and On me's count.
    """
    page = open_page(browser, serve(SIGN_OFF))
    approved = page.locator(".lf-fp-row-notice")
    on_me = page.locator(".lf-fp-on-user")
    owed = re.compile(r"^On me: 1")
    clear = re.compile(r"^On me$")
    expect(on_me).to_have_attribute("aria-label", owed)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    panel_control(page, "approval").click()
    holding(page, held, 1, "the refused approval")
    expect(approved).to_have_text(re.compile(r"✓ v1 approved"))
    expect(on_me).to_have_attribute("aria-label", clear)
    held[0].fulfill(
        json={
            "ok": False,
            "attempt": held[0].request.post_data_json["attempt"],
            "error": "This approval was refused.",
            "final": True,
        }
    )
    round_trip(page)
    expect(approved).to_be_hidden()
    expect(on_me).to_have_attribute("aria-label", owed)
    held.clear()
    page.keyboard.press("Escape")
    panel_control(page, "approval").click()
    holding(page, held, 1, "the accepted approval")
    expect(approved).to_have_text(re.compile(r"✓ v1 approved"))
    expect(on_me).to_have_attribute("aria-label", clear)
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(approved).to_have_text(re.compile(r"✓ v1 approved"))
    expect(on_me).to_have_attribute("aria-label", clear)

    page.keyboard.press("Escape")
    page.locator("body").focus()
    held.clear()
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("z")
    holding(page, held, 1, "the refused approval undo")
    expect(approved).to_be_hidden()
    expect(on_me).to_have_attribute("aria-label", owed)
    held[0].fulfill(
        json={
            "ok": False,
            "attempt": held[0].request.post_data_json["attempt"],
            "error": "This withdrawal was refused.",
            "final": True,
        }
    )
    page.unroute("**/api/event")
    round_trip(page)
    expect(approved).to_have_text(re.compile(r"✓ v1 approved"))
    expect(on_me).to_have_attribute("aria-label", clear)
    held.clear()
    page.route("**/api/event", lambda route: held.append(route))
    page.locator("body").focus()
    page.keyboard.press("z")
    holding(page, held, 1, "the accepted approval undo")
    expect(approved).to_be_hidden()
    expect(on_me).to_have_attribute("aria-label", owed)
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(approved).to_be_hidden()
    expect(on_me).to_have_attribute("aria-label", owed)
    expect(panel_control(page, "approval")).to_be_enabled()
    kinds = [e["kind"] for e in events_model.read_events(serve.page_dir)]
    assert kinds[-2:] == [
        "done",
        "undo",
    ], f"the withdrawal is not in the log as its own event: {kinds}"

    # And the press is available again, which is what makes this a correction rather than
    # a page the user has spent.
    held.clear()
    page.route("**/api/event", lambda route: held.append(route))
    panel_control(page, "approval").click()
    holding(page, held, 1, "the second approval")
    expect(approved).to_have_text(re.compile(r"✓ v1 approved"))
    expect(on_me).to_have_attribute("aria-label", clear)
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    assert [e["kind"] for e in events_model.read_events(serve.page_dir)][-1] == "done"


def test_sign_off_waits_for_the_page_while_comments_stay_live(browser, serve):
    """Approval belongs to the presented page; runtime discussion does not wait for it."""
    held = []
    page = browser.new_page()
    page.route("**/api/state*", lambda route: held.append(route))
    with page.expect_request("**/api/state*"):
        page.goto(serve(SIGN_OFF), wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    assert held, "the positive control did not hold the first state response"

    page.locator(".lf-fp-threads").click()
    panel_settled(page, view="threads")

    held.pop(0).continue_()
    wait_until_ready(page)
    page.locator(".lf-fp-close").click()
    expect(panel_control(page, "approval")).to_be_enabled()


def test_a_page_that_asks_nothing_carries_no_terminal_control(browser, serve):
    """An informational page lists its versions without an approval action."""
    page = open_page(browser, serve(LONG_PAGE))
    # The versions list is drawn in one pass, so a version standing in it is what makes
    # the absence beside it worth reading rather than a list that never rendered.
    menu = panel_menu(page, "versions")
    expect(menu.locator(".lf-fp-version")).to_have_count(1)
    expect(menu.locator(APPROVAL)).to_have_count(0)


def test_a_seat_thread_leaves_the_pick_it_is_about_live(browser, serve):
    """The user's own remark must not lock the control it is a remark about.

    A thread current location in the widget's seat takes the decision off the user's
    list — On me stops counting it — but answers nothing, so the press that would
    answer it is still live. This is the browser half of the split, and the half the
    user meets first: the POST door only sees a hand-posted event, while here
    the controller reading paints the control and its dispatcher guards the press, and
    the module has already painted the answer by the time either runs. Reading the
    user's list at this door therefore does not refuse the press so much as swallow
    it — the widget flips, nothing is logged, no notice fires, and the next poll puts it
    back with nothing anywhere saying why.

    The subject is the project widget SEATED_OBLIGATION_ENTRY declares, whose seat is where a
    user most often starts such a thread; any thread anchored on an obligation splits it the
    same way, and the reading under test never asks which widget it is."""
    url = serve(
        leaf_page(
            "seated eligibility",
            '<h1 id="heading">Choose</h1><lf-ask id="pick-decision">'
            "<h2>Cap the retries?</h2>"
            '<lf-verdict id="pick" asks>Three attempts, then stop.</lf-verdict>'
            "</lf-ask>",
        ),
        layer_registry=SEATED_OBLIGATION_LAYER,
        layer_widgets=SEATED_OBLIGATION_WIDGETS,
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "pick"},
            "text": "neither — cap the retries instead",
        },
    )
    page = open_page(browser, url)
    # Off the user's list, which is the whole reason the two readings differ here.
    expect_obligations_answered(page, "0/1")

    page.get_by_role("button", name="Accept").click()
    round_trip(page)

    expect(page.get_by_role("button", name="Accepted")).to_have_count(1)
    # The log is what holds this, and the control above cannot: the module paints the
    # answer before either guard runs, so with the wrong reading at this door the press
    # reads exactly as it does here and the log stays empty.
    assert [event["action"] for event in actions(serve.page_dir)] == ["settle"]
