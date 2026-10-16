"""Sign-off approval and the asks it joins: where the control stands, how a press
records, is taken back or refused, and when it waits."""

import re

import pytest
from interact_support import append_carried_log_record
from leaf import event_log as events_model
from leaf.render_checks import wait_until_ready
from playwright.sync_api import expect
from render_cases_interaction import SEATED_ASK_LAYER, SEATED_ASK_WIDGETS, live_url
from render_cases_navigation import actions
from render_harness import (
    LONG_PAGE,
    _traffic,
    expect_asks_answered,
    holding,
    leaf_page,
    open_page,
    panel_settled,
    resized,
    round_trip,
    sending,
    told,
    undo,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_sign_off_stands_through_a_draft_and_moves_nothing(browser, serve):
    """Approval is on the banner's row wherever the page declares sign-off, stamped or
    not. It came and went with the stamp, and at a width where Approval takes the
    banner to two rows a draft arriving took it back to one and moved the whole
    document: news moving the page. Before a stamp the press is refused and says why."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page = open_page(browser, live_url(serve(html)))
    resized(page, 560, 800)
    button = page.locator(".lf-signoff")
    expect(button).to_be_visible()
    height = page.evaluate(BANNER_HEIGHT)
    top = page.evaluate(
        "() => document.querySelector('main').getBoundingClientRect().top"
    )
    (serve.page_dir / "index.html").write_text(
        html.replace("</main>", "<p>A draft's new paragraph.</p></main>")
    )
    told(page)
    expect(page.locator(".lf-version")).to_have_text("Showing Draft")
    expect(button).to_be_visible()
    expect(button).to_have_attribute(
        "title", "There is no stamped version to approve yet"
    )
    assert page.evaluate(BANNER_HEIGHT) == height
    after = page.evaluate(
        "() => document.querySelector('main').getBoundingClientRect().top"
    )
    assert after == pytest.approx(top, abs=1), (top, after)


def test_a_page_asking_for_sign_off_records_the_approval(browser, serve):
    """The declared ask puts the button there, and the press posts `done`.

    Drive the shipped browser through the real POST door, since a button that merely
    looks right says nothing about the event the agent's loop receives.
    """
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page = open_page(browser, serve(html))
    button = page.locator(".lf-signoff")
    expect(button).to_be_visible()
    expect(button).to_have_attribute(
        "title", "Approve this work; the page stays open for follow-up"
    )
    expect(button).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    button.click()
    holding(page, held, 1, "the approval")
    expect(button).to_be_disabled()
    expect(button).to_have_attribute("aria-busy", "true")
    button.dispatch_event("click")
    assert _traffic(page).sends == 1, "one approval press became two log events"

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    event = events_model.read_events(serve.page_dir)[-1]
    assert (event["kind"], event["author"], event["version"]) == ("done", "user", 1)
    expect(button).to_be_disabled()


@pytest.mark.parametrize("width", [1200, 390])
def test_required_approval_is_an_ask_until_approved(browser, serve, width):
    """Sign-off belongs to On me and leads to the real approval control,
    including its phone overflow seat. A task's Done cannot substitute for it."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page = open_page(browser, serve(html))
    page.set_viewport_size({"width": width, "height": 900})
    on_me = page.get_by_role("button", name="On me: 1", exact=True, include_hidden=True)
    expect(on_me).to_be_attached()
    target = page.evaluate("""async () => {
      const {readAsks, askActions} = await window.__lfWidgetApi();
      const ask = readAsks().all.find(q => q.source.kind === 'approval');
      const target = document.getElementById(ask.prompt.target);
      await askActions.open(ask.id);
      return target === document.querySelector('.lf-signoff') && document.activeElement === target;
    }""")
    assert target, "the public ask route did not reach its declared approval target"
    page.keyboard.press("m")
    approval = page.locator(".lf-signoff")
    expect(approval).to_be_visible()
    expect(approval).to_be_focused()
    approval.click()
    round_trip(page)
    expect(
        page.get_by_role(
            "button",
            name="On me: 0",
            exact=True,
            include_hidden=True,
        )
    ).to_be_attached()
    page.keyboard.press("z")
    round_trip(page)
    expect(on_me).to_be_attached()
    page.keyboard.press("Escape")
    if width < 600:
        page.locator(".lf-banner-more").click()
    on_me.click()
    row = page.locator("button[data-lf-row]").filter(has_text="Approve v1?")
    expect(row).to_be_visible()
    expect(
        page.get_by_role("button", name="Done: Approve v1?", exact=True)
    ).to_have_count(0)
    row.click()
    expect(approval).to_be_visible()
    expect(approval).to_be_focused()


def test_an_approval_can_be_taken_back_like_any_other_user_gesture(browser, serve):
    """Approval, its ask and its history agree during send, undo and refusal.

    Holding each POST proves the result is visible before admission; a definitive
    refusal restores the same admitted approval through every consumer.
    """
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page = open_page(browser, serve(html))
    button = page.locator(".lf-signoff")
    expect(button).to_have_attribute(
        "title", "Approve this work; the page stays open for follow-up"
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    history = page.locator(".lf-threads > .lf-system")
    on_me = page.get_by_role("button", name="On me: 1", exact=True, include_hidden=True)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    button.click()
    holding(page, held, 1, "the refused approval")
    expect(button).to_have_text("✓ Version approved")
    expect(on_me).to_have_count(0)
    expect(history).to_contain_text("Approved")
    held[0].fulfill(
        json={
            "ok": False,
            "attempt": held[0].request.post_data_json["attempt"],
            "error": "This approval was refused.",
            "final": True,
        }
    )
    round_trip(page)
    expect(button).to_have_text("Approve version")
    expect(on_me).to_be_attached()
    expect(history).to_have_count(0)
    held.clear()
    button.click()
    holding(page, held, 1, "the accepted approval")
    expect(button).to_have_text("✓ Version approved")
    expect(on_me).to_have_count(0)
    expect(history).to_contain_text("Approved")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(button).to_have_text("✓ Version approved")
    expect(button).to_have_attribute(
        "title", "Approved. Press z to undo while approval is still the latest update"
    )

    expect(history).to_contain_text("Approved")
    expect(on_me).to_have_count(0)
    held.clear()
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("z")
    holding(page, held, 1, "the refused approval undo")
    expect(button).to_have_text("Approve version")
    expect(on_me).to_be_attached()
    expect(history).to_have_count(0)
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
    expect(button).to_have_text("✓ Version approved")
    expect(on_me).to_have_count(0)
    expect(history).to_contain_text("Approved")
    held.clear()
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("z")
    holding(page, held, 1, "the accepted approval undo")
    expect(button).to_have_text("Approve version")
    expect(on_me).to_be_attached()
    expect(history).to_have_count(0)
    expect(button).to_be_enabled()
    expect(button).to_have_attribute(
        "title", "Approve this work; the page stays open for follow-up"
    )
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(button).to_have_text("Approve version")
    expect(on_me).to_be_attached()
    expect(history).to_have_count(0)
    kinds = [e["kind"] for e in events_model.read_events(serve.page_dir)]
    assert kinds[-2:] == [
        "done",
        "undo",
    ], f"the withdrawal is not in the log as its own event: {kinds}"

    # And the press is available again, which is what makes this a correction rather than
    # a page the user has spent.
    held.clear()
    page.route("**/api/event", lambda route: held.append(route))
    button.click()
    holding(page, held, 1, "the second approval")
    expect(button).to_have_text("✓ Version approved")
    expect(on_me).to_have_count(0)
    expect(history).to_contain_text("Approved")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(history).to_contain_text("Approved")
    assert [e["kind"] for e in events_model.read_events(serve.page_dir)][-1] == "done"


def test_sign_off_waits_for_the_page_while_comments_stay_live(browser, serve):
    """Approval belongs to the presented page; runtime discussion does not wait for it."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    held = []
    page = browser.new_page()
    page.route("**/api/state*", lambda route: held.append(route))
    with page.expect_request("**/api/state*"):
        page.goto(serve(html), wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    assert held, "the positive control did not hold the first state response"
    button = page.locator(".lf-signoff")
    expect(button).to_be_visible()
    expect(button).to_be_disabled()

    page.locator(".lf-threads-toggle").click()
    expect(page.locator(".lf-thread-panel")).to_have_class(re.compile(r"\bopen\b"))

    held.pop(0).continue_()
    wait_until_ready(page)
    expect(button).to_be_enabled()


def test_a_page_that_asks_nothing_carries_no_terminal_control(browser, serve):
    """An informational page offers Comment on the page, On me, Threads and More
    without an approval action."""
    page = open_page(browser, serve(LONG_PAGE))
    # The banner is built in one pass, so a control standing in it is what makes the
    # absence beside it worth reading rather than a row that never rendered.
    expect(page.locator(".lf-threads-toggle")).to_be_visible()
    assert page.locator(".lf-banner").evaluate("element => element.localName") == (
        "header"
    )
    row = page.locator(".lf-banner-actions > *:visible")
    expect(row).to_have_count(4)
    expect(row.nth(0)).to_have_class(re.compile(r"\blf-page-comment\b"))
    expect(row.nth(1)).to_have_class(re.compile(r"\blf-queue\b"))
    expect(row.nth(2)).to_have_class(re.compile(r"\blf-threads-toggle\b"))
    expect(row.nth(3)).to_have_class(re.compile(r"\blf-banner-more\b"))
    approval = page.locator(".lf-signoff")
    expect(approval).to_have_count(1)
    expect(approval).to_be_hidden()
    expect(approval).to_be_disabled()
    events_before = len(events_model.read_events(serve.page_dir))
    approval.evaluate("control => control.click()")
    assert len(events_model.read_events(serve.page_dir)) == events_before, (
        "the retained control approved a page that did not declare sign-off"
    )


def test_more_wears_a_dot_while_a_press_would_approve(browser, serve):
    """On a phone Approval stands behind More as a waiting ask, and More wears
    its dot and names both reasons. Approving takes the dot down and taking the
    approval back puts it up again; on a desk Approval stands on the row and More
    wears no dot for it."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page = open_page(browser, serve(html))
    resized(page, 390, 800)
    more = page.locator(".lf-banner-more")
    approval = page.locator(".lf-signoff")
    expect(more).to_have_attribute("data-lf-news", "")
    expect(more).to_have_attribute(
        "aria-label", "More page controls, approval open, items on me"
    )
    more.click()
    expect(page.locator(".lf-banner-menu > :visible").first).to_have_class(
        re.compile(r"\blf-signoff\b")
    )
    with sending(page, "the approval"):
        approval.click()
    expect(approval).to_have_text("✓ Version approved")
    expect(more).not_to_have_attribute("data-lf-news", re.compile(".*"))
    expect(more).to_have_attribute("aria-label", "More page controls")
    page.keyboard.press("Escape")
    undo(page)
    expect(more).to_have_attribute("data-lf-news", "")

    # Crossing the phone width reseats Approval, and focus goes with it, both ways,
    # here with More open throughout.
    more.click()
    approval.focus()
    resized(page, 1200, 800)
    expect(page.locator(".lf-banner-actions > .lf-signoff")).to_be_visible()
    expect(approval).to_be_focused()
    expect(more).not_to_have_attribute("data-lf-news", re.compile(".*"))
    resized(page, 390, 800)
    expect(page.locator(".lf-banner-menu > .lf-signoff")).to_be_visible()
    expect(approval).to_be_focused()


BANNER_HEIGHT = (
    "() => document.querySelector('.lf-banner').getBoundingClientRect().height"
)


def test_a_seat_thread_leaves_the_pick_it_is_about_live(browser, serve):
    """The user's own remark must not lock the control it is a remark about.

    A thread standing in the widget's seat takes the decision off the user's
    list — the banner stops counting it — but answers nothing, so the press that would
    answer it is still live. This is the browser half of the split, and the half the
    user meets first: the POST door only sees a hand-posted event, while here
    the controller reading paints the control and its dispatcher guards the press, and
    the module has already painted the answer by the time either runs. Reading the
    user's list at this door therefore does not refuse the press so much as swallow
    it — the widget flips, nothing is logged, no notice fires, and the next poll puts it
    back with nothing anywhere saying why.

    The subject is the project widget SEATED_ASK_ENTRY declares, whose seat is where a
    user most often starts such a thread; any thread anchored on an ask splits it the
    same way, and the reading under test never asks which widget it is."""
    url = serve(
        leaf_page(
            "seated eligibility",
            '<h1 id="heading">Choose</h1><lf-ask id="pick-decision">'
            "<h2>Cap the retries?</h2>"
            '<lf-verdict id="pick" asks>Three attempts, then stop.</lf-verdict>'
            "</lf-ask>",
        ),
        layer_registry=SEATED_ASK_LAYER,
        layer_widgets=SEATED_ASK_WIDGETS,
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
    expect_asks_answered(page, "0/1")

    page.get_by_role("button", name="Accept").click()
    round_trip(page)

    expect(page.get_by_role("button", name="Accepted")).to_have_count(1)
    # The log is what holds this, and the control above cannot: the module paints the
    # answer before either guard runs, so with the wrong reading at this door the press
    # reads exactly as it does here and the log stays empty.
    assert [event["action"] for event in actions(serve.page_dir)] == ["settle"]
