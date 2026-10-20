"""The panel's Threads list: what each row says."""

import pytest
from interact_support import append_carried_log_record
from leaf import thread as thread_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
    PHOTO_THREAD,
    WORKSHOP_THREAD_EVENTS,
    WORKSHOP_THREADS_PAGE,
    panel_comment,
)
from render_harness import (
    open_page,
    resized,
    take_browser_errors,
    told,
)

from browser.threads import thread_row

pytestmark = pytest.mark.shifts_unsurveyed


def test_thread_rows_name_action_in_existing_status(browser, serve):
    """Each row names its thread and, on the same line after it, the state it stands
    in: the action owed where the user owes one."""
    page = open_page(
        browser, serve(WORKSHOP_THREADS_PAGE, events=WORKSHOP_THREAD_EVENTS)
    )
    resized(page, 1440, 900)
    asked = thread_row(page, PHOTO_THREAD)
    expect(asked.locator(".lf-fp-label")).to_have_text("Workshop room photo")
    expect(asked.locator(".lf-fp-value")).to_have_text("My turn to answer")
    line = asked.evaluate(
        """row => {
          const label = row.querySelector('.lf-fp-label').getBoundingClientRect();
          const value = row.querySelector('.lf-fp-value').getBoundingClientRect();
          const center = rect => rect.top + rect.height / 2;
          return {beside: Math.abs(center(label) - center(value)) < 2,
                  after: label.right <= value.left};
        }"""
    )
    assert line == {"beside": True, "after": True}, line


def test_an_agent_reply_says_when_the_user_owes_an_answer(browser, serve):
    """An open thread and a request to its user are different facts. A complete
    answer stays available for follow-up without the row saying the user owes one; a
    reply holding a question (`lf-ask`) says so until the user answers. A decision
    widget says so the same way: its own current projection puts the thread on the
    user."""
    url = serve(PANEL_PAGE)
    answered = panel_comment(serve.page_dir, "Why forty?", {"section": "how-cap"})
    asked = panel_comment(serve.page_dir, "What remains?", {"section": "how-store"})
    thread_model.post_reply(
        serve.page_dir,
        {"to": answered, "for": answered},
        "Forty is what the slowest supported device can hold.",
    )
    thread_model.post_reply(
        serve.page_dir,
        {"to": asked, "for": asked},
        "One choice remains.",
        markup='<lf-ask id="store-owner">Which store should own the result?</lf-ask>',
    )
    page = open_page(browser, url)
    expect(thread_row(page, asked).locator(".lf-fp-value")).to_have_text(
        "My turn to answer"
    )
    expect(thread_row(page, answered).locator(".lf-fp-value")).not_to_contain_text(
        "My turn"
    )

    thread_model.post_reply(
        serve.page_dir,
        {"to": answered},
        "Choose the backend here.",
        '<lf-ask id="backend-decision"><h3>Which backend?</h3>'
        '<lf-options id="backend" choose>'
        '<lf-option id="backend-sqlite"><strong>SQLite</strong></lf-option>'
        '<lf-option id="backend-postgres"><strong>Postgres</strong></lf-option>'
        "</lf-options></lf-ask>",
    )
    told(page)
    expect(thread_row(page, answered).locator(".lf-fp-value")).to_contain_text(
        "My turn"
    )


def test_an_answer_without_a_title_leaves_the_opening_words(browser, serve):
    """An answer that names nothing leaves the row on the thread's opening words."""
    url = serve(PANEL_PAGE)
    opening = "Which room is the workshop in?"
    root = panel_comment(serve.page_dir, opening, {"section": "h-how"})
    page = open_page(browser, url)
    label = thread_row(page, root).locator(".lf-fp-label")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": root,
            "responds": root,
            "text": "The terrace room.",
        },
    )
    told(page)
    rendered(page)
    expect(label).to_have_text(opening)
    assert not take_browser_errors(page)


def test_a_thread_nobody_picked_up_reads_its_opening_words(browser, serve):
    """A comment no agent has picked up past the pickup grace has nothing naming
    it, so its row reads the comment and says it waits for pickup."""
    url = serve(PANEL_PAGE)
    opening = "Is the workshop room accessible?"
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": opening,
            "ts": "2026-01-01T09:00:00-08:00",
        },
    )["id"]
    page = open_page(browser, url)
    row = thread_row(page, root)
    expect(row.locator(".lf-fp-value")).to_have_text("Waiting for pickup")
    expect(row.locator(".lf-fp-label")).to_have_text(opening)
    assert not take_browser_errors(page)
