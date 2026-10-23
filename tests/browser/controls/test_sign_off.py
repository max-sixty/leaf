"""Approval widgets record independent permissions through ordinary action and Undo.

The browser proves immediate drawing, refusal recovery and preservation across live
revisions; the model suite owns obligation folding and admission.
"""

import pytest
from interact_support import append_carried_log_record, stamp
from playwright.sync_api import expect
from render_cases_interaction import (
    SEATED_OBLIGATION_LAYER,
    SEATED_OBLIGATION_WIDGETS,
    live_url,
)
from render_cases_navigation import actions
from render_harness import (
    expect_obligations_answered,
    holding,
    leaf_page,
    open_page,
    round_trip,
    stamp_page,
    told,
)

from browser.threads import open_panel_thread
from leaf import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed

APPROVAL_PAGE = leaf_page(
    "Publish the report",
    '<h1 id="heading">Team report</h1>'
    '<lf-approval id="publish-report"><h2>Publish the report?</h2>'
    "<p>Publish the park survey to the team workspace.</p></lf-approval>"
    '<lf-ask id="next-survey">Where should the next survey run?</lf-ask>',
)


def test_approval_and_undo_draw_immediately_and_recover_after_refusal(browser, serve):
    """Unanswered questions never block this permission; refused gestures restore it."""
    page = open_page(browser, serve(APPROVAL_PAGE))
    approval = page.locator("#publish-report")
    button = approval.get_by_role("button")
    status = approval.get_by_role("status")
    expect_obligations_answered(page, "0/2")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    button.click()
    holding(page, held, 1, "the refused approval")
    expect(status).to_have_text("Approved")
    held.pop().fulfill(json={"ok": False, "error": "Approval refused", "final": True})
    round_trip(page)
    expect(status).to_have_text("Awaiting approval")
    expect_obligations_answered(page, "0/2")

    button.click()
    holding(page, held, 1, "the accepted approval")
    expect(status).to_have_text("Approved")
    held.pop().continue_()
    round_trip(page)
    expect_obligations_answered(page, "1/2")
    event = events_model.read_events(serve.page_dir)[-1]
    assert (event["kind"], event["widget"], event["action"], event["detail"]) == (
        "action",
        "publish-report",
        "approve",
        {},
    )
    expect(button).to_have_text("Undo approval")
    expect(button).to_be_focused()
    page.keyboard.press("Enter")
    holding(page, held, 1, "the refused undo")
    expect(status).to_have_text("Awaiting approval")
    held.pop().fulfill(json={"ok": False, "error": "Undo refused", "final": True})
    round_trip(page)
    expect(status).to_have_text("Approved")
    expect_obligations_answered(page, "1/2")

    page.keyboard.press("Enter")
    holding(page, held, 1, "the accepted undo")
    expect(status).to_have_text("Awaiting approval")
    held.pop().continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect_obligations_answered(page, "0/2")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "undo"
    expect(button).to_have_text("Approve")


def test_approval_survives_a_stamp_until_the_request_is_restated(browser, serve):
    """A request owns permission across live revisions; explicit restatement reopens it."""
    page = open_page(browser, live_url(serve(APPROVAL_PAGE)))
    approval = page.locator("#publish-report")
    approval.get_by_role("button", name="Approve", exact=True).click()
    round_trip(page)
    revised = APPROVAL_PAGE.replace(
        "</main>", '<p id="news">The next survey is being planned.</p></main>'
    )
    (serve.page_dir / "index.html").write_text(revised)
    assert stamp(serve.page_dir, "Added survey news").exit_code == 0
    told(page)
    expect(approval.get_by_role("status")).to_have_text("Approved")
    expect_obligations_answered(page, "1/2")

    restated = revised.replace(
        '<lf-approval id="publish-report">',
        '<lf-approval id="publish-report" restated>',
    ).replace(
        "Publish the park survey to the team workspace.",
        "Publish the park survey and its location data to the public website.",
    )
    (serve.page_dir / "index.html").write_text(restated)
    assert (
        stamp(serve.page_dir, "Ask permission for public location data").exit_code == 0
    )
    told(page)
    expect(approval.get_by_role("status")).to_have_text("Awaiting approval")
    expect_obligations_answered(page, "0/2")


def test_approval_in_a_thread_keeps_its_permission_across_page_revisions(
    browser, serve
):
    """A reply's widget loads its initial drawing and owns its state in the thread."""
    source = leaf_page("Report discussion", '<h1 id="heading">Report</h1>')
    url = serve(source)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-publish",
            "author": "user",
            "revision": 1,
            "text": "Can you publish the finished report?",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-publish",
            "revision": 1,
            "text": "The report is ready. Confirm where it will be published.",
            "markup": '<lf-approval id="thread-publication"><h2>Publish to the team workspace?</h2>'
            "<p>Publish the finished park survey to the private research workspace.</p></lf-approval>",
        },
    )
    page = open_page(browser, live_url(url))
    open_panel_thread(page, "c-publish")
    approval = page.locator("#thread-publication")
    approval.get_by_role("button", name="Approve", exact=True).click()
    round_trip(page)
    expect(approval.get_by_role("status")).to_have_text("Approved")
    stamp_page(
        serve.page_dir,
        source.replace("</main>", "<p>Next survey planned.</p></main>"),
        "Survey news",
    )
    told(page)
    open_panel_thread(page, "c-publish")
    expect(approval.get_by_role("status")).to_have_text("Approved")
    approval.get_by_role("button", name="Undo approval", exact=True).click()
    round_trip(page)
    expect(approval.get_by_role("status")).to_have_text("Awaiting approval")
    expect_obligations_answered(page, "0/1")


def test_a_seat_thread_leaves_the_pick_it_is_about_live(browser, serve):
    """The user's own remark must not lock the control it is a remark about.

    A thread standing in the widget's seat takes the decision off the user's
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
