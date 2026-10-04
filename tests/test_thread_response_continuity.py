"""Thread response geometry through delivery refusal and retry."""

import pytest
from leaf import data as data_model
from leaf import event_log as events_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_navigation import source_revision
from render_harness import leaf_page, open_page, round_trip, write


@pytest.mark.parametrize(
    "place", ["outlet", "seat", "nested-room", "nested-end", "margin", "panel"]
)
def test_refused_reply_retains_its_live_foot(browser, serve, place):
    """Removing a provisional turn preserves the live Send and following passage.

    Native and panel thread bodies and both scroll boundaries exercise the same rule.
    The refused draft is retryable, and only its eventual acceptance reaches the log.
    """
    from render_cases_interaction import SEATED_QUESTION_PAGE
    from render_harness import (
        consume_browser_errors,
        holding,
        panel_settled,
        scroll_settled,
        stored_draft_text,
    )

    tail = '<p id="continuity-tail">Review the next step here.</p>'
    if place == "seat":
        authored = SEATED_QUESTION_PAGE.replace("</lf-command>", "</lf-command>" + tail)
        anchor = {"section": "jobs"}
        selector = '[data-lf-thread-seat="jobs"] > .lf-page-thread'
    elif place in ("margin", "panel"):
        authored = leaf_page(
            "Response continuity",
            '<h1 id="h">Shipping order</h1><p id="plan">Keep the release order visible.</p>'
            + tail,
        )
        anchor = {"section": "plan"}
        selector = (
            ".lf-margin-preview .lf-page-thread"
            if place == "margin"
            else ".lf-threads > .lf-thread"
        )
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
    if place not in ("seat", "margin", "panel"):
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
    elif place == "panel":
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        if page.locator(selector).get_attribute("open") is None:
            page.locator(selector).locator(".lf-thread-summary").click()
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


@pytest.mark.parametrize(
    ("contents", "integer_band", "viewport"),
    [
        ("short", False, (390, 740)),
        ("long", False, (390, 740)),
        ("short", True, (420, 741)),
        ("long", True, (420, 741)),
    ],
    ids=["short-fractional", "long-fractional", "short-integer", "long-integer"],
)
def test_narrow_panel_editor_growth_retains_the_live_send(
    browser, serve, contents, integer_band, viewport
):
    """Wrapping keeps a short editor's top and a long editor's pinned Send steady.

    Default typography gives the list a fractional height. An authored integer
    line-box theme supplies its contrast without changing any geometry rule.
    Both the first wrap and a later wrap beside a held send preserve that placement.
    """
    from render_harness import holding, panel_settled

    head = (
        "<style>:root { --lf-ui-lh: 1.5; --t-6: 12px; }</style>" if integer_band else ""
    )
    url = serve(leaf_page("Reply wrapping", "<h1>Review the release</h1>", head=head))
    events_model.append_event(
        serve.page_dir,
        {
            "id": "root",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep the review clear.",
        },
    )
    if contents == "long":
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "revision": 1,
                "parent": "root",
                "text": "\n\n".join(
                    ["Retain the release context while writing the next reply."] * 14
                ),
            },
        )
    context = browser.new_context(
        viewport={"width": viewport[0], "height": viewport[1]},
        reduced_motion="no-preference",
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    band = page.locator(".lf-threads").bounding_box()["height"]
    assert (band == round(band)) is integer_band, f"wrong native band contrast: {band}"
    owner = page.locator(".lf-threads > .lf-thread").last
    if owner.get_attribute("open") is None:
        owner.locator(".lf-thread-summary").click()
    draft = owner.locator("leaf-text")
    expect(draft).to_be_visible()
    assert (owner.bounding_box()["height"] > band) is (contents == "long")
    page.evaluate("""() => {
      window.editorGrowth = [];
      for (const type of ['beforeinput', 'input']) document.addEventListener(type, event => {
        if (event.inputType !== 'insertText') return;
        const field = event.composedPath().find(node => node.matches?.('leaf-text'));
        const row = field?.closest('.lf-thread-reply');
        if (!row) return;
        const send = row.querySelector('.lf-thread-send');
        const list = row.closest('.lf-threads');
        const floor = list.getBoundingClientRect().bottom
          - parseFloat(getComputedStyle(list).paddingBottom)
          - parseFloat(getComputedStyle(row).bottom);
        window.editorGrowth.push({type, field: field.getBoundingClientRect().toJSON(),
          send: send.getBoundingClientRect().toJSON(), row: row.getBoundingClientRect().toJSON(), floor});
      }, true);
    }""")
    held = []
    page.route(
        "**/api/event",
        lambda route: (
            held.append(route)
            if route.request.post_data_json["kind"] == "reply"
            else route.continue_()
        ),
    )
    first = "Keep the reader's words in the thread while this reply is being sent."
    newer = "Keep the next draft separate from the reply still being sent."
    draft.click()
    page.keyboard.insert_text(first)
    page.keyboard.press("Enter")
    holding(page, held, 1, "the first narrow-panel reply")
    rendered(page)
    draft.click()
    page.keyboard.insert_text(newer)
    poses = page.evaluate("window.editorGrowth")
    assert len(poses) == 4, poses
    for before, after in zip(poses[::2], poses[1::2], strict=True):
        assert (before["type"], after["type"]) == ("beforeinput", "input")
        assert after["field"]["height"] > before["field"]["height"], poses
        for edge in ("left", "right"):
            assert abs(after["send"][edge] - before["send"][edge]) < 0.5, poses
        if contents == "short":
            assert after["field"]["top"] == pytest.approx(
                before["field"]["top"], abs=0.5
            ), poses
            growth = after["field"]["height"] - before["field"]["height"]
            for edge in ("top", "bottom"):
                assert after["send"][edge] - before["send"][edge] == pytest.approx(
                    growth, abs=0.5
                ), poses
        else:
            for pose in (before, after):
                assert pose["row"]["bottom"] == pose["floor"], poses
            for edge in ("top", "bottom"):
                assert abs(after["send"][edge] - before["send"][edge]) < 0.5, poses
        assert 0 <= after["field"]["top"] < after["field"]["bottom"] <= viewport[1]
        assert 0 <= after["send"]["top"] < after["send"]["bottom"] <= viewport[1]
    held.pop().continue_()
    round_trip(page)
    rendered(page)
    assert draft.evaluate("node => node.value") == newer
    page.unroute_all(behavior="wait")


def test_direct_comment_arrival_keeps_its_canceled_entry_motion_canceled(
    browser, serve
):
    """Clearing a sent draft and editing the next never restart thread entry motion.

    Native animation events observe the displayed transform, rather than the
    renderer's remembered flags, through the real held send and later repaint.
    """
    from leaf.render_checks import wait_for_probe
    from leaf_dev import ROOT
    from render_harness import holding, scroll_settled

    context = browser.new_context(
        viewport={"width": 1600, "height": 900}, reduced_motion="no-preference"
    )
    page = open_page(
        browser, serve(ROOT / "examples/review-a-plan.html"), context=context
    )
    page.locator(".lf-threads-toggle").click()
    field = page.locator(".lf-general leaf-text")
    expect(field).to_be_visible()
    page.evaluate("""() => {
      window.__recuedArrivals = [];
      document.addEventListener('animationstart', event => {
        const card = event.target;
        if (!card.matches?.('.lf-thread[data-attempt]')) return;
        const transform = getComputedStyle(card).transform;
        if (transform !== 'none') window.__recuedArrivals.push({
          animation: event.animationName, transform,
          words: card.querySelector('.lf-msg-body')?.textContent.trim(),
        });
      }, true);
    }""")
    held = []

    def hold(route):
        if route.request.post_data_json["kind"] == "comment":
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/event", hold)
    try:
        write(field, "Keep this comment visible while it is sent.")
        page.keyboard.press("Enter")
        holding(page, held, 1, "the general comment")
        rendered(page)
        wait_for_probe(page, "pageSettled")
        scroll_settled(page, ".lf-threads")

        def reading_place():
            return page.locator(".lf-threads").evaluate("""list => {
              const card = list.querySelector(':scope > .lf-thread[data-attempt]');
              const box = card.getBoundingClientRect();
              return {scroll: list.scrollTop, top: box.top, bottom: box.bottom};
            }""")

        before = reading_place()
        write(field, "Keep the next thought separate.")
        rendered(page)
        wait_for_probe(page, "pageSettled")
        scroll_settled(page, ".lf-threads")
        expect(page.locator(".lf-thread[data-attempt] .lf-msg-body")).to_have_text(
            "Keep this comment visible while it is sent."
        )
        expect(field).to_have_js_property("value", "Keep the next thought separate.")
        assert reading_place() == before
        assert page.evaluate("window.__recuedArrivals") == [], (
            "a retained repaint restarted geometry motion after direct navigation "
            f"had canceled it: {page.evaluate('window.__recuedArrivals')!r}"
        )
    finally:
        for route in held:
            route.continue_()
        page.unroute("**/api/event", hold)
        expect(page.locator('.lf-threads [aria-busy="true"]')).to_have_count(0)
