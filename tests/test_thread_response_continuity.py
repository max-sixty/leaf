"""Thread response geometry through delivery refusal and retry."""

import pytest
from leaf import data as data_model
from leaf import event_log as events_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_navigation import source_revision
from render_harness import leaf_page, open_page, round_trip, write


@pytest.mark.parametrize(
    "place", ["outlet", "seat", "nested-room", "nested-end", "margin"]
)
def test_refused_reply_retains_its_live_foot(browser, serve, place):
    """Removing a provisional turn preserves the live Send and following passage.

    Both native thread bodies and both scroll boundaries exercise the same rule.
    The refused draft is retryable, and only its eventual acceptance reaches the log.
    """
    from render_cases_interaction import SEATED_QUESTION_PAGE
    from render_harness import (
        consume_browser_errors,
        holding,
        scroll_settled,
        stored_draft_text,
    )

    tail = '<p id="continuity-tail">Review the next step here.</p>'
    if place == "seat":
        authored = SEATED_QUESTION_PAGE.replace("</lf-command>", "</lf-command>" + tail)
        anchor = {"section": "jobs"}
        selector = '[data-lf-thread-seat="jobs"] > .lf-page-thread'
    elif place == "margin":
        authored = leaf_page(
            "Response continuity",
            '<h1 id="h">Shipping order</h1><p id="plan">Keep the release order visible.</p>'
            + tail,
        )
        anchor = {"section": "plan"}
        selector = ".lf-margin-preview .lf-page-thread"
    else:
        contents = (
            '<h1 id="h">Shipping order</h1><lf-diff id="patch" source="change"><pre></pre></lf-diff>'
            + tail
        )
        if place.startswith("nested"):
            contents = (
                '<div id="continuity-scroll" style="height:550px;overflow:auto"><div style="height:250px"></div>'
                + contents
                + ('<div style="height:450px"></div>' if place == "nested-room" else "")
                + "</div>"
            )
        authored = leaf_page("Response continuity", contents)
        anchor = {"section": "patch", "datum": '["app.py","new",1]', "source": "change"}
        selector = "lf-diff .lf-page-thread"
    url = serve(authored)
    if place not in ("seat", "margin"):
        data_model.cmd_data_set(
            serve.page_dir,
            "change",
            'diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-return "old"\n+return "new"\n',
        )
        anchor["source_revision"] = source_revision(serve.page_dir, "change")
    parent = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep the shipping order visible.",
            "anchor": anchor,
        },
    )["id"]
    context = browser.new_context(
        viewport={"width": 1600, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    if place == "margin":
        page.locator(".lf-margin-marker").first.click()
    owner = page.locator(selector)
    draft = owner.locator("leaf-text")
    expect(draft).to_be_visible()
    if place.startswith("nested"):
        page.evaluate("""async () => {
          const body = document.querySelector('#continuity-scroll');
          const {registerReadingRegion} = await window.__lfRuntimeImport('/runtime/reading-regions.js');
          registerReadingRegion({id: 'continuity-scroll', host: body, body});
        }""")
    held = []

    def hold(route):
        if route.request.post_data_json["kind"] == "reply":
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/event", hold)
    words = "  Preserve this newer thought.\nIts spaces matter.  "
    write(draft, words)
    page.keyboard.press("Enter")
    holding(page, held, 1, "the reply that will be refused")
    rendered(page)
    if place.startswith("nested"):
        scroller = page.locator("#continuity-scroll")
        scroller.evaluate(
            "(node, end) => {node.scrollTop = end ? node.scrollHeight : 250}",
            place == "nested-end",
        )
        scroll_settled(page, scroller)
    attempt = held[0].request.post_data_json["attempt"]
    assert held[0].request.post_data_json["parent"] == parent

    def pose():
        return owner.evaluate("""node => {
          const rect = subject => {
            const {left, top, bottom} = subject.getBoundingClientRect();
            return {left, top, bottom};
          };
          const pose = {send: rect(node.querySelector('.lf-thread-send')),
            tail: rect(document.querySelector('#continuity-tail'))};
          const close = document.querySelector('.lf-margin-preview-close');
          if (close?.checkVisibility()) pose.close = rect(close);
          const popup = node.closest('.lf-margin-preview');
          if (popup) {
            const bounds = popup.getBoundingClientRect();
            const fits = rect => rect.left >= bounds.left && rect.right <= bounds.right
              && rect.top >= bounds.top && rect.bottom <= bounds.bottom;
            const field = node.querySelector('leaf-text').getBoundingClientRect();
            const send = node.querySelector('.lf-thread-send').getBoundingClientRect();
            if (!fits(field) || !fits(send))
              throw new Error('the floating reply exceeds its allocated card');
          }
          return pose;
        }""")

    pending = pose()
    assert 0 < pending["send"]["top"] < pending["send"]["bottom"] < 900
    held.pop().fulfill(
        status=400,
        json={
            "ok": False,
            "attempt": attempt,
            "error": "refused before append",
            "final": True,
        },
    )
    round_trip(page)
    rendered(page)
    consume_browser_errors(page, "400")
    restored = pose()
    for node in pending:
        for edge in pending[node]:
            assert abs(restored[node][edge] - pending[node][edge]) < 0.5, (
                pending,
                restored,
            )
    assert draft.evaluate("node => node.value") == words
    assert stored_draft_text(page, f"reply:{parent}") == words
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply"
    ]
    draft.focus()
    page.keyboard.press("Enter")
    holding(page, held, 1, "the refused reply's retry")
    assert held[0].request.post_data_json["attempt"] == attempt
    held.pop().continue_()
    round_trip(page)
    rendered(page)
    replies = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply"
    ]
    assert len(replies) == 1
    assert (replies[0]["parent"], replies[0]["text"], replies[0]["attempt"]) == (
        parent,
        words,
        attempt,
    )
    assert draft.evaluate("node => node.value") == ""
    pose()
    page.unroute_all(behavior="wait")
    context.close()
