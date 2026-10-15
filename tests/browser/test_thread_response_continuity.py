"""Thread response geometry through delivery refusal and retry."""

import pytest
from leaf import event_log as events_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_harness import leaf_page, open_page, round_trip, write


@pytest.mark.parametrize(
    ("contents", "integer_band", "viewport"),
    [("short", False, (390, 740)), ("long", True, (420, 741))],
    ids=["short-fractional", "long-integer"],
)
def test_narrow_panel_editor_growth_retains_the_live_send(
    browser, serve, contents, integer_band, viewport
):
    """Wrapping keeps a short editor's top and a long editor's pinned action steady.

    Default typography gives the list a fractional height. An authored integer
    line-box theme supplies its contrast without changing any geometry rule.
    Both the first wrap and a later wrap beside a held send preserve that placement
    while the empty field's microphone gives way to Send.
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
        const action = [...row.querySelectorAll('.lf-compose-submit, .lf-compose-dictate')]
          .find(button => button.checkVisibility());
        const list = row.closest('.lf-threads');
        const floor = list.getBoundingClientRect().bottom
          - parseFloat(getComputedStyle(list).paddingBottom)
          - parseFloat(getComputedStyle(row).bottom);
        window.editorGrowth.push({type, field: field.getBoundingClientRect().toJSON(),
          action: action.getBoundingClientRect().toJSON(), row: row.getBoundingClientRect().toJSON(), floor});
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
            assert abs(after["action"][edge] - before["action"][edge]) < 0.5, poses
        if contents == "short":
            assert after["field"]["top"] == pytest.approx(
                before["field"]["top"], abs=0.5
            ), poses
            growth = after["field"]["height"] - before["field"]["height"]
            for edge in ("top", "bottom"):
                assert after["action"][edge] - before["action"][edge] == pytest.approx(
                    growth, abs=0.5
                ), poses
        else:
            for pose in (before, after):
                assert pose["row"]["bottom"] == pose["floor"], poses
            for edge in ("top", "bottom"):
                assert abs(after["action"][edge] - before["action"][edge]) < 0.5, poses
        assert 0 <= after["field"]["top"] < after["field"]["bottom"] <= viewport[1]
        assert 0 <= after["action"]["top"] < after["action"]["bottom"] <= viewport[1]
    held.pop().continue_()
    round_trip(page)
    rendered(page)
    assert draft.evaluate("node => node.value") == newer
    page.unroute_all(behavior="wait")


def test_context_paste_after_rewrap_keeps_the_previous_panel_turn_visible(
    browser, serve
):
    """Pinned reply growth uses its current height before every editor command.

    Widening the panel shrinks a wrapped draft without another edit. A context-menu
    paste then grows it without native beforeinput; the former height would underpay
    that growth and leave the preceding words under the sticky writing area.
    """
    from render_cases_interaction import PANEL_PAGE, panel_comment
    from render_harness import scroll_settled

    from browser.test_render_threads import open_threads_list, reply_by_keyboard

    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Keep this review visible.")
    for text in (
        "The last answer remains useful while composing a response.\n\n" * 18,
        "These final words stay beside the reply.",
    ):
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": root,
                "text": text,
            },
        )
    context = browser.new_context(
        viewport={"width": 300, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    open_threads_list(page, 300, 900)
    card = reply_by_keyboard(page, root)
    editor = card.locator("leaf-text")
    draft = "A stable native draft that wraps at the narrow width. " * 3
    write(editor, draft)
    rendered(page)
    narrow = editor.bounding_box()
    page.set_viewport_size({"width": 1600, "height": 900})
    rendered(page)
    # Rewrapping retains the reading position. Start at the list end before
    # wheeling back to test how paste growth keeps the latest turn visible.
    page.locator(".lf-threads").evaluate("list => list.scrollTop = list.scrollHeight")
    page.locator(".lf-threads").hover()
    page.mouse.wheel(0, -8)
    scroll_settled(page, ".lf-threads")
    latest = card.locator(".lf-msg.agent").last
    before = editor.bounding_box()
    previous = latest.bounding_box()
    assert before["height"] < narrow["height"] - 10, (narrow, before)
    assert previous["y"] + previous["height"] < before["y"], (previous, before)

    context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.evaluate("""async () => {
      window.previousGrowthClipboard = await navigator.clipboard.read();
    }""")
    pasted = "\n\n\n\nMore"
    try:
        page.evaluate(
            """async words => {
              await navigator.clipboard.writeText(words);
              window.growthPasteEvents = [];
              for (const type of ['keydown', 'beforeinput', 'paste'])
                document.addEventListener(type,
                  () => window.growthPasteEvents.push(type), {capture: true});
            }""",
            pasted,
        )
        context.new_cdp_session(page).send(
            "Input.dispatchKeyEvent",
            {"type": "char", "key": "Unidentified", "commands": ["Paste"]},
        )
        expect(editor).to_have_js_property("value", draft + pasted)
        assert page.evaluate("window.growthPasteEvents") == ["paste"]
        rendered(page)
    finally:
        page.evaluate("""async () => {
          const previous = window.previousGrowthClipboard;
          if (previous.length) await navigator.clipboard.write(previous);
          else await navigator.clipboard.writeText('');
        }""")
    grown = editor.bounding_box()
    previous = latest.bounding_box()
    assert grown["height"] > before["height"] + 40, (before, grown)
    assert previous["y"] + previous["height"] < grown["y"], (previous, grown)
    expect(editor).to_be_focused()
