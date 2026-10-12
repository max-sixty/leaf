"""Where a comment stands before and after Send: the comment box the user types in, and
the thread card the sent comment becomes.

Each case is one gesture at one window size: words selected in a long paragraph, or an
element pointed at with ⌥-click. It types a comment, reads where the box stands,
presses Enter, and reads where the card stands once placed. The snapshot records the
effect rather than the pixels, in one document a reviewer reads as a scoreboard, so a
change of a few pixels records nothing and a change in where either goes records a
line:

- `expected`: the side the case is built to give both.
- `side`: where each stands relative to what it is about: `right`, `left`, `below` or
  `above`. Where the case allows more than one side and the surface took one of them,
  it records the case's `expected`: which of under and over has more room turns on the
  fonts a platform draws the page in, and the snapshot is read on more than one.
  `moves` still says whether the card took the box's side.
- `stands`: whether it stands where that side puts it: beside the block `level with
  the words`, or `clear of the block` under or over it, else how far off.
  The touch passage verifies either clear placement or a window-constrained frame
  when the paragraph and frame cannot fit together; font metrics can choose either.
- `moves`: how far the card stands from where the box stood, at the edge each holds
  (the left edge across; the top down, or the foot where the card stands above),
  bucketed `still` (the same place), `near` (a line or two) or `away`.

Each case also writes the pair it read to its test's `tmp_path/<case>.png`: the box as
the user typed in it on the left, the card on the right with the box's outline drawn
over it, so a move shows at a glance. After an intentional change, re-record and read
the diff beside those pictures:

  uv run pytest --regtest-reset -n0 tests/*/test_render_send_placement.py"""

import pytest
from browser.test_render_send_placement import CASES, RECT, sent
from interact_support import yaml_document
from leaf.render_checks import rendered, wait_until_ready
from model_folds import leaf_page
from playwright.sync_api import expect
from render_harness import (
    open_page,
    resized,
    scroll_settled,
    select,
    write,
)


def test_where_a_comment_stands_before_and_after_send(
    browser, serve, snapshot, tmp_path
):
    snapshot.check(
        yaml_document(
            "Where each case's comment box, and the thread card it became, stand.",
            {name: sent(browser, serve, name, tmp_path) for name in CASES},
        )
    )


def test_a_multiline_passage_attaches_to_its_first_words_through_focus_reflow_and_send(
    browser, serve
):
    """A later, less indented line cannot move the passage's inline attachment.
    Native selection and the captured draft/card use the same first fragment, while
    their clearance continues to belong to the whole code block."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Multiline attachment",
                '<div><h1>Review the handler</h1><pre id="source"><code class="language-javascript">'
                'const answer = {\n  decision: "Keep",\n  does: "keep the active card",\n};'
                "</code></pre><p>The handler records the current decision.</p></div>",
                layout="sidebar",
            )
        ),
    )
    resized(page, 1440, 900)
    phrase = """words => {
      const code = document.querySelector('#source code');
      const start = code.textContent.indexOf(words);
      const end = start + words.length;
      const walker = document.createTreeWalker(code, NodeFilter.SHOW_TEXT);
      const range = document.createRange();
      let offset = 0;
      for (let node; (node = walker.nextNode());) {
        const next = offset + node.length;
        if (offset <= start && start < next) range.setStart(node, start - offset);
        if (offset < end && end <= next) range.setEnd(node, end - offset);
        offset = next;
      }
      const fragments = [...range.getClientRects()].filter(r => r.width && r.height);
      return {
        first: fragments[0].toJSON(), last: fragments.at(-1).toJSON(),
        box: range.getBoundingClientRect().toJSON(),
      };
    }"""
    passage = page.evaluate(phrase, 'Keep",\n  does: "keep the active card')
    first, last = passage["first"], passage["last"]
    select(
        page,
        (first["left"] + 1, first["top"] + first["height"] / 2),
        (last["right"] - 1, last["top"] + last["height"] / 2),
    )
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    words = page.evaluate("() => getSelection().toString()")

    def attached(selector):
        rendered(page)
        passage = page.evaluate(phrase, words)
        # The fixture must distinguish the first words from the whole range's left edge.
        assert passage["first"]["left"] - passage["box"]["left"] > 50
        rect = page.evaluate(RECT, selector)
        block = page.evaluate(RECT, "#source")
        assert rect["left"] == pytest.approx(passage["first"]["left"], abs=1)
        assert rect["bottom"] <= block["top"] or rect["top"] >= block["bottom"]
        return rect

    attached(".lf-fab-bar")
    field.click()
    page.keyboard.insert_text("Keep this meaning explicit.")
    expect(field).to_be_focused()
    assert page.evaluate("() => getSelection().isCollapsed")
    attached(".lf-fab-bar")
    resized(page, 1200, 900)
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "Keep this meaning explicit.")
    attached(".lf-fab-bar")
    page.reload(wait_until="load")
    wait_until_ready(page)
    expect(field).to_have_js_property("value", "Keep this meaning explicit.")
    before = attached(".lf-fab-bar")
    field.click()
    page.keyboard.press("Enter")
    card = page.locator(".lf-margin-preview")
    expect(card).to_have_css("opacity", "1")
    after = attached(".lf-margin-preview")
    assert after["left"] == pytest.approx(before["left"], abs=1)
    expect(card.locator(".lf-page-thread")).to_be_focused()
    # Leave the card for its passage, then dismiss it before reopening.
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(card).to_be_hidden()
    page.locator(".lf-margin-marker").click()
    expect(card).to_have_css("opacity", "1")
    attached(".lf-margin-preview")


def test_a_comment_keeps_its_measure_when_its_passage_scrolls_away(browser, serve):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Comment width through scroll",
                '<div style="height:650px"></div>'
                '<p id="subject">Keep the long comment with this passage.</p>'
                '<div style="height:1800px"></div>',
            )
        ),
    )
    resized(page, 900, 600)
    target = page.locator("#subject")
    target.evaluate(
        "node => scrollTo(0, node.getBoundingClientRect().top + scrollY - 400)"
    )
    rendered(page)
    target.click(modifiers=["Alt"], position={"x": 30, "y": 10})
    write(page.locator(".lf-fab-input"), "Keep these words while the page leaves. " * 6)
    rendered(page)
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_have_attribute("data-lf-plane", "page")
    width = bar.bounding_box()["width"]

    page.mouse.wheel(0, 1500)
    scroll_settled(page)
    expect(bar).to_have_attribute("data-lf-plane", "page")
    away = bar.bounding_box()
    assert away["y"] + away["height"] < 0, away
    assert abs(away["width"] - width) <= 1
    page.mouse.wheel(0, -1500)
    scroll_settled(page)
    expect(bar).to_have_attribute("data-lf-plane", "page")
    assert abs(bar.bounding_box()["width"] - width) <= 1
