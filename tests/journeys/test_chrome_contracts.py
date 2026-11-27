"""Everyday browser contracts for shared chrome."""

import pytest
from browser.test_chrome_contracts import (
    BANDED_EVENTS,
    BANDED_PAGE,
    CONTINUED,
    KEEP_ROOTS,
    NESTING,
    open_page_map,
    open_reference,
    open_threads_list,
    type_drafts,
)
from browser.threads import open_panel_thread
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    panel_comment,
)
from render_harness import (
    LONG_PAGE,
    open_page,
    panel_field,
    panel_settled,
    resized,
    sending,
    write,
)

from leaf.log import event_log as events_model
from leaf_dev.browser import choose_threads_in_panel, text_field


# Each scheme and each pointer once: the faces compared are the same scheme's, and a
# finger changes the layout the two places stand in rather than their colours.
@pytest.mark.parametrize(
    ("touch", "scheme"),
    [(False, "light"), (True, "dark")],
    ids=["desktop-light", "touch-dark"],
)
def test_a_conversation_keeps_its_face_and_sends_from_margin_and_panel(
    browser, serve, scheme, touch
):
    """One conversation has the same typography and reply field in both places.

    A short opening and a long Markdown answer exercise both message roles. Compare
    the rendered faces instead of pinning a font size: changing the shared theme is
    allowed, shrinking only the panel's face is not. Both reply routes append to the
    same conversation.
    """
    url = serve(LONG_PAGE)
    root = panel_comment(
        serve.page_dir, "Which detail should we keep?", {"section": "p0"}
    )
    answer = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": "**Keep the evidence.** "
            + "Explain how the result was measured. " * 40,
        },
    )
    context = browser.new_context(has_touch=touch, is_mobile=touch, color_scheme=scheme)
    page = open_page(browser, url, context=context)
    resized(page, 1440, 900)
    page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').click()
    margin = page.locator(".lf-margin-preview .lf-page-thread")
    expect(text_field(margin, name="Reply", exact=True)).to_be_visible()

    def faces(thread):
        return thread.evaluate(
            """thread => {
              const styles = (node, properties) => {
                const style = getComputedStyle(node);
                return Object.fromEntries(properties.map(p => [p, style.getPropertyValue(p)]));
              };
              const type = ['font-family', 'font-size', 'font-weight', 'line-height', 'color'];
              const field = thread.querySelector(
                '.lf-thread-reply leaf-text, .lf-fp-field leaf-text');
              return {
                messages: [...thread.querySelectorAll('.lf-msg')].map(message => ({
                  body: styles(message.querySelector('.lf-msg-body'), type),
                  author: styles(message.querySelector(':scope > .lf-msg-head b'), type),
                })),
                metadata: styles(thread.querySelector('.lf-msg-meta'), type),
                field: styles(field, [...type, 'padding-top', 'padding-right', 'padding-bottom',
                  'padding-left', 'min-height']),
                surround: styles(field.closest('.lf-compose-field'),
                  ['border-radius', 'border-top-width', 'border-top-color', 'background-color']),
              };
            }"""
        )

    anchored = faces(margin)
    assert len(anchored["messages"]) == 2
    panel = open_panel_thread(page, root)
    # The panel's view draws the messages, and its reply stands in the panel's field.
    viewed = faces(page.locator(".lf-floating-panel"))
    assert viewed["messages"] == anchored["messages"], scheme
    assert viewed["metadata"] == anchored["metadata"], scheme
    expect(panel.locator(f'.lf-msg[data-lf-event="{answer["id"]}"]')).to_contain_text(
        "Keep the evidence."
    )
    write(panel_field(page), "Sent from Threads.")
    with sending(page, "the panel follow-up"):
        page.locator(".lf-fp-field").get_by_role(
            "button", name="Send", exact=True
        ).click()
    expect(panel.locator(".lf-msg").last).to_contain_text("Sent from Threads.")

    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    # Reading the thread in the panel chose the panel for threads, so the tab opens
    # them beside their passages again before the marker opens the card.
    choose_threads_in_panel(page, on=False)
    page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').click()
    write(text_field(margin, name="Reply", exact=True), "Sent beside the page.")
    with sending(page, "the anchored follow-up"):
        margin.get_by_role("button", name="Send", exact=True).click()
    expect(margin.locator(".lf-msg").last).to_contain_text("Sent beside the page.")
    sent = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reply" and event["author"] == "user"
    ]
    assert [(event["parent"], event["text"]) for event in sent] == [
        (root, "Sent from Threads."),
        (root, "Sent beside the page."),
    ]


# The scheme reaches every surface through the same tokens, so dark runs once, on the
# composer a widget's thread outlet holds inside the widget's own tree.


import pytest
from render_harness import (
    page_comment,
)

from leaf.source.render_checks import rendered


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_scrolling_draft_shows_the_caret_s_row_with_the_padding_beside_it(
    engine, request, serve
):
    """A line typed at the end of a draft that scrolls leaves nothing below it to scroll
    to, and the caret taken to the first line leaves nothing above. Revealing only the
    caret, as a native textarea does, left the field's padding out of view, and in
    Firefox the foot of the caret's row too."""
    page = open_page(request.getfixturevalue(engine), serve(LONG_PAGE))
    field = page_comment(page)
    hidden = """box => ({
      below: box.scrollHeight - box.clientHeight - box.scrollTop,
      above: box.scrollTop,
    })"""
    page.keyboard.type("line 0")
    for line in range(1, 40):
        page.keyboard.press("Shift+Enter")
        page.keyboard.type(f"line {line}")
        if field.evaluate("box => box.scrollHeight > box.clientHeight + 40"):
            break
    else:
        raise AssertionError("the draft never scrolled")
    for key in ("Shift+Enter", "w", "ControlOrMeta+Home"):
        page.keyboard.press(key)
        rendered(page)
        shown = field.evaluate(hidden)
        if key == "ControlOrMeta+Home":
            assert shown["above"] < 1, shown
        else:
            assert shown["below"] < 1, (key, shown)


def test_opening_a_line_under_the_last_moves_no_words(browser, serve):
    """Shift+Enter opens a line under a draft's last words, and once the first
    character typed there lands, every word above rests where it did: Send's room
    stands on every line, so no keystroke at the end changes where the lines above
    wrap."""
    url = serve(LONG_PAGE)
    panel_comment(serve.page_dir, "Keep the first paragraph.", {"section": "p0"})
    page = open_page(
        browser,
        url,
        init_script="""
          window.editorRoots = new Map();
          const attach = Element.prototype.attachShadow;
          Element.prototype.attachShadow = function(options) {
            const root = attach.call(this, options);
            if (this.localName === 'leaf-text') window.editorRoots.set(this, root);
            return root;
          };
        """,
    )
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    open_panel_thread(page, root)
    field = panel_field(page)
    field.click()

    def reading():
        return field.evaluate(
            """host => {
              const rows = [];
              for (const line of window.editorRoots.get(host).querySelectorAll('.cm-line')) {
                const range = document.createRange();
                range.selectNodeContents(line);
                for (const r of range.getClientRects()) {
                  if (r.width < 0.5) continue;
                  const row = rows.find(o => Math.abs(o.top - r.top) < 4);
                  if (row) row.right = Math.max(row.right, r.right);
                  else rows.push({top: r.top, right: r.right});
                }
              }
              const box = host.getBoundingClientRect();
              return {top: box.top, height: box.height,
                      rows: rows.sort((a, b) => a.top - b.top)
                        .map((row) => ({top: row.top - box.top, right: row.right}))};
            }"""
        )

    page.keyboard.insert_text(
        "The first paragraph runs long enough to wrap once, and then runs on a while"
    )
    # A newly grown line carries the existing words with the panel edge; compare
    # the resulting places after that ride finishes.
    panel_settled(page)
    full = reading()
    page.keyboard.press("Shift+Enter")
    panel_settled(page)
    opened = reading()
    page.keyboard.type("S")
    panel_settled(page)
    typed = reading()
    assert typed["height"] == opened["height"], (opened, typed)
    assert typed["top"] == opened["top"], (opened, typed)
    assert typed["rows"][: len(full["rows"])] == opened["rows"][: len(full["rows"])], (
        opened,
        typed,
    )
    assert [row["right"] for row in opened["rows"]] == [
        row["right"] for row in full["rows"]
    ], (full, opened)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_shift_enter_and_tab_keep_a_draft_in_the_containers_the_message_will_hold(
    engine, request, serve, subtests
):
    """The keys that shape a draft's quotes and lists, typed into one field."""
    page = open_page(
        request.getfixturevalue(engine), serve(LONG_PAGE), init_script=KEEP_ROOTS
    )

    with subtests.test("Shift+Enter continues the containers the message will hold"):
        # Shift+Enter begins a line in each quote and list item the message will read
        # the caret's line in, a fence's code included, and on a line holding only their
        # markers leaves the innermost, an item in an item outdenting; a task's next
        # item is an open task. CodeMirror's own Markdown grammar decided it, which
        # stopped at a fence, so a fence's next line fell out of its quote or item and
        # its closing fence opened another; leaving a list took a third press, the
        # second only loosening it. A bare `> ` after a list read as inside the list's
        # last item, so leaving the quote did nothing.
        field = page_comment(page)
        left = type_drafts(page, field, CONTINUED)
        assert left == {name: draft for name, (_, draft) in CONTINUED.items()}

    with subtests.test("Tab nests a list item and Shift+Tab takes it out"):
        # Tab in a list item nests it under the item above, where the message will draw
        # it as a nested item, in the platform's nested bullet; Shift+Tab takes it out a
        # level, and one undo takes back one Tab. The first item, with no item to nest
        # under, stays and keeps the caret. Elsewhere Tab and Shift+Tab leave the field.
        field = page_comment(page)
        left = type_drafts(page, field, NESTING)
        assert left == {name: draft for name, (_, draft) in NESTING.items()}
        expect(field).to_be_focused()
        # The nested item wears the nested bullet with its words and before them, though
        # the message reads an empty nested item as words of the item above.
        bullets = """box => [...window.__lfRoots.get(box).querySelectorAll('.cm-line')]
          .map(line => [...line.closest('.lf-md-item').classList]
            .find(name => /^lf-md-(disc|circle|square)$/.test(name)))"""
        for erase in (0, len("two")):
            for _ in range(erase):
                page.keyboard.press("Backspace")
            rendered(page)
            assert field.evaluate(bullets) == ["lf-md-disc", "lf-md-circle"], erase
        expect(field).to_have_js_property("value", "- one\n  - ")
        # Outside a list item the press leaves the field as before, and so does Shift+Tab
        # with no item to take out, so a draft that is all list still lets focus out.
        for typed, key in (("plain", "Tab"), ("- one", "Shift+Tab")):
            field.focus()
            page.keyboard.press("ControlOrMeta+a")
            page.keyboard.type(typed)
            page.keyboard.press(key)
            expect(field).not_to_be_focused()
            expect(field).to_have_js_property("value", typed)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize("opens", [open_threads_list, open_page_map, open_reference])
def test_a_band_names_the_group_passing_under_it(request, serve, engine, opens):
    """A list that groups its rows keeps the group being read named: scrolled into a
    group, its band stands at the top of the list, across the list's whole surface, and
    a row the user walks up to stands clear below the band rather than under it."""
    page = open_page(
        request.getfixturevalue(engine), serve(BANDED_PAGE, events=BANDED_EVENTS)
    )
    resized(page, 1000, 480)
    scroller, rows = opens(page)
    expect(scroller).to_be_visible()
    scroller.evaluate("list => { list.scrollTop = 160; }")
    rendered(page)
    stuck = """list => {
      const box = list.getBoundingClientRect();
      const at = list.getRootNode().elementFromPoint(
        box.left + box.width / 2, box.top + 2);
      const band = at?.closest('.lf-rows-head');
      if (!band) return null;
      const {top, bottom, left, right} = band.getBoundingClientRect();
      return {name: band.textContent.trim(), top, bottom, left, right,
              list: {top: box.top, left: box.left,
                     right: box.left + list.clientWidth}};
    }"""
    band = scroller.evaluate(stuck)
    assert band, "no band stands at the top of the scrolled list"
    assert band["top"] == pytest.approx(band["list"]["top"], abs=1), band
    assert band["left"] == pytest.approx(band["list"]["left"], abs=1), band
    assert band["right"] == pytest.approx(band["list"]["right"], abs=1), band

    # Up the list by the keys, each row stands clear of the band over it.
    scroller.locator(rows).nth(11).focus()
    for _ in range(11):
        page.keyboard.press("ArrowUp")
        rendered(page)
        at = scroller.evaluate(
            """list => {
              const root = list.getRootNode();
              const row = root.activeElement;
              const {left, top, width} = row.getBoundingClientRect();
              const over = root.elementFromPoint(left + width / 2, top + 1);
              return [row.textContent, over?.closest('.lf-rows-head')?.textContent];
            }"""
        )
        assert at[1] is None, f"{at[0]} stands under the band {at[1]}"
