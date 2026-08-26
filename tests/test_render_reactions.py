"""Reactions: one-press tokens on a passage, an item, a reply, or the page."""

import json

import pytest
from conftest import interact
from playwright.sync_api import expect
from render_support import (
    PANEL_PAGE,
    key_line,
    open_page,
    panel_comment,
    panel_settled,
    round_trip,
    select,
    told,
    undo,
    watched,
)

pytestmark = pytest.mark.nightly

# The wash and the glyphs a standing reaction paints, read off the page: the ranges in
# the highlight registry (their words, whitespace dropped, the way the corpus reads a
# comment's mark) and every seated glyph by the block it sits in and its token.
PAINTED = """() => ({
  washed: [...(CSS.highlights.get('lf-react') ?? [])].map(r => r.toString().replace(/\\s/g, '')).join(''),
  glyphs: [...document.querySelectorAll('.lf-reacts > .lf-react-mark')]
    .map(m => [m.parentElement.parentElement.id, m.dataset.token]),
  outlined: [...document.querySelectorAll('.lf-react-el')].map(el => el.id),
})"""


def select_paragraph(page, selector):
    """Drag across most of one paragraph, the way the anchor tests do."""
    box = page.locator(selector).bounding_box()
    select(
        page,
        (box["x"] + 4, box["y"] + 6),
        (box["x"] + box["width"] - 8, box["y"] + box["height"] - 6),
        steps=16,
    )


def painted(page, glyphs):
    """Wait for the page's reaction paint to show exactly these seated glyphs, then
    return the whole reading. `data-lf-applied` counts replayed actions and covers no
    comment, so the paint itself is the fact a reaction's arrival states."""
    page.wait_for_function(
        "(want) => JSON.stringify((" + PAINTED + ")().glyphs) === want",
        arg=json.dumps(glyphs, separators=(",", ":")),
    )
    return page.evaluate(PAINTED)


def test_a_token_press_marks_the_passage_and_a_second_press_takes_it_back(
    browser, serve
):
    """The cheapest legal answer to a passage: select, press one token. What the log
    gets is a comment carrying the token in place of words, on the anchor a comment
    from the same bar would carry — the same capture — so the file meets it the way it
    meets a comment. What the page gets is paint and nothing else: the words washed
    through the highlight registry, a glyph in the margin level with the paragraph,
    no card in the panel and nothing in its count, because a reaction is a mark and not
    a conversation. The glyph is its own eraser: pressing it sends the ordinary undo
    naming the event, and the paint goes with the gesture."""
    page, errors = open_page(browser, serve(PANEL_PAGE))
    select_paragraph(page, "#how-store")
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    tokens = page.evaluate(
        "() => [...document.querySelectorAll('.lf-fab-bar .lf-react')].map(p => p.dataset.token)"
    )
    assert tokens == ["ok", "no", "lost", "cut", "more", "this"], tokens
    expect(page.locator(".lf-fab-bar .lf-fab")).to_be_visible()  # Comment stands last

    page.locator('.lf-fab-bar .lf-react[data-token="cut"]').click()
    round_trip(page)
    sent = interact.read_events(serve.page_dir)[-1]
    assert sent["kind"] == "comment" and sent["token"] == "cut" and "text" not in sent
    assert sent["anchor"]["section"] == "how-store"
    assert "holds every edit" in sent["anchor"]["quote"]
    expect(bar).to_be_hidden()  # the mark is the receipt

    shown = painted(page, [["how-store", "cut"]])
    assert "holdseveryedit" in shown["washed"], shown
    assert shown["outlined"] == []
    # Level with its block: the glyph's top is the paragraph's first line, in the margin.
    level = page.evaluate(
        """() => {
          const p = document.querySelector('#how-store').getBoundingClientRect();
          const g = document.querySelector('.lf-reacts').getBoundingClientRect();
          return { dy: g.top - p.top, right: g.left - p.right };
        }"""
    )
    assert -2 <= level["dy"] <= 6 and level["right"] > 0, level
    # A mark, not a thread: nothing in the panel, and nothing in its count.
    expect(page.locator(".lf-comments")).to_have_text("Comments (0)")
    page.locator(".lf-comments").click()
    panel_settled(page)
    expect(page.locator(".lf-thread")).to_have_count(0)
    # The panel's page row shows it standing nowhere: it is on a passage, not the page.
    assert (
        page.evaluate(
            "() => document.querySelectorAll('.lf-page-strip [aria-pressed=\"true\"]').length"
        )
        == 0
    )

    page.locator('.lf-reacts .lf-react-mark[data-token="cut"]').click()
    round_trip(page)
    withdrawn = interact.read_events(serve.page_dir)[-1]
    assert withdrawn["kind"] == "undo" and withdrawn["undoes"] == sent["id"]
    assert painted(page, []) == {"washed": "", "glyphs": [], "outlined": []}
    assert errors == []
    page.close()


def test_the_keyboard_arms_the_bar_with_digits_and_the_line_names_what_z_takes_back(
    browser, serve
):
    """`r` arms the same bar the pointer sees, each token wearing its digit in declared
    order, so the press survives any layer's vocabulary; a digit sends and disarms, and
    Escape or a stray key lets go. The target is the selection when one stands and the
    page when nothing does. Afterwards the undo row's sentence names its target rather
    than promising a generic take-back."""
    page, errors = open_page(browser, serve(PANEL_PAGE))
    select_paragraph(page, "#how-cap")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.keyboard.press("r")
    line = key_line(page)
    assert "1–6" in line and "react" in line, line
    chips = page.evaluate(
        "() => [...document.querySelectorAll('.lf-fab-bar.lf-armed .lf-react > .lf-address')]"
        "  .filter(c => c.checkVisibility()).map(c => c.textContent)"
    )
    assert chips == ["1", "2", "3", "4", "5", "6"], chips
    page.keyboard.press("4")
    round_trip(page)
    sent = interact.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["token"], sent["anchor"]["section"]) == (
        "comment",
        "cut",
        "how-cap",
    )
    painted(page, [["how-cap", "cut"]])
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    expect(page.locator(".lf-keyline")).to_contain_text("undo")
    # The sentence behind the chip, off the register: the reference's z row names the
    # token and the passage it stands on, where it promised a generic take-back before.
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_be_visible()
    rows = page.locator(".lf-help").inner_text()
    assert "Take back: cut on" in rows and "capped at forty" in rows, rows
    page.keyboard.press("Escape")
    expect(page.locator(".lf-help")).to_be_hidden()

    # Nothing selected: r aims at the page whole, offers the tokens and no Comment.
    page.keyboard.press("Escape")
    page.evaluate("() => getSelection().removeAllRanges()")
    page.keyboard.press("r")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(page.locator(".lf-fab-bar .lf-fab")).to_be_hidden()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    page.keyboard.press("r")
    page.keyboard.press("5")
    round_trip(page)
    sent = interact.read_events(serve.page_dir)[-1]
    assert sent["token"] == "more" and "anchor" not in sent, sent
    page.locator(".lf-comments").click()
    panel_settled(page)
    expect(
        page.locator('.lf-page-strip .lf-react[data-token="more"]')
    ).to_have_attribute("aria-pressed", "true")
    undo(page)
    expect(
        page.locator('.lf-page-strip .lf-react[data-token="more"]')
    ).to_have_attribute("aria-pressed", "false")
    assert errors == []
    page.close()


def test_alt_click_raises_the_bar_on_an_item_and_a_token_outlines_it(browser, serve):
    """A whole element goes through the gesture that already names one: ⌥-click. The
    bar comes up on the item — tokens, then Comment — and a token puts an element
    anchor in the log, which paints as a dashed hairline on the item's boxes and a glyph
    seated at its first line."""
    page, errors = open_page(browser, serve(PANEL_PAGE))
    page.keyboard.down("Alt")
    page.locator("#how-patch").click()
    page.keyboard.up("Alt")
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    expect(page.locator(".lf-composer")).to_be_hidden()
    page.locator('.lf-fab-bar .lf-react[data-token="this"]').click()
    round_trip(page)
    sent = interact.read_events(serve.page_dir)[-1]
    assert sent["token"] == "this" and sent["anchor"] == {"section": "how-patch"}
    shown = painted(page, [["how-patch", "this"]])
    assert shown["outlined"] and shown["washed"] == "", shown
    assert errors == []
    page.close()


def _thread(page_dir):
    """A thread the agent spoke in last: the reader's question and Claude's answer."""
    root = panel_comment(page_dir, "Why forty?", {"section": "how-cap"})
    reply = interact.append_event(
        page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Claude",
            "parent": root,
            "text": "Forty is what the slowest device we ship on can hold.",
        },
    )
    return root, reply["id"]


def test_an_ok_on_the_agents_latest_reply_takes_the_thread_out_of_waiting(
    browser, serve
):
    """The reply strip offers the tokens under the agent's message. One press records a
    reply carrying the token, on that message; `ok` — the shipped token declaring
    `settles` — standing on the latest agent message takes the thread out of "waiting
    on you" without a second event, and taking the ok back brings the wait back, the
    narrowing being a reading of the log. A token without the flag settles nothing."""
    url = serve(PANEL_PAGE)
    root, reply = _thread(serve.page_dir)
    page, errors = open_page(browser, url)
    page.locator(".lf-comments").click()
    panel_settled(page)
    strip = page.locator(f'.lf-msg[data-mid="{reply}"] .lf-react-strip')
    expect(strip).to_be_visible()
    expect(strip.locator(".lf-react")).to_have_count(6)
    # The reader's own message wears no strip: a reaction is on what the agent said.
    expect(page.locator(f'.lf-msg[data-mid="{root}"] .lf-react-strip')).to_have_count(0)
    page.locator(".lf-needs").click()  # the waiting-on-you narrowing
    expect(page.locator(".lf-needs")).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".lf-thread")).to_have_count(1)

    strip.locator('.lf-react[data-token="no"]').click()
    round_trip(page)
    sent = interact.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["parent"], sent["token"]) == ("reply", reply, "no")
    expect(strip.locator('.lf-react[data-token="no"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.locator(".lf-thread")).to_have_count(1)  # `no` settles nothing

    strip.locator('.lf-react[data-token="ok"]').click()
    round_trip(page)
    ok = interact.read_events(serve.page_dir)[-1]
    assert ok["token"] == "ok" and ok["parent"] == reply
    expect(page.locator(".lf-needs")).to_have_text("Waiting on you")  # none
    expect(page.locator(".lf-thread")).to_have_count(0)  # out of "waiting on you"
    # The mark, pressed again, is the eraser — and the wait comes back with the undo.
    page.locator(".lf-needs").click()  # every comment again, so the strip is on screen
    expect(page.locator(".lf-thread")).to_have_count(1)
    strip.locator('.lf-react[data-token="ok"]').click()
    round_trip(page)
    withdrawn = interact.read_events(serve.page_dir)[-1]
    assert withdrawn["kind"] == "undo" and withdrawn["undoes"] == ok["id"]
    expect(page.locator(".lf-needs")).to_have_text("Waiting on you (1)")
    expect(strip.locator('.lf-react[data-token="ok"]')).to_have_attribute(
        "aria-pressed", "false"
    )
    assert errors == []
    page.close()


def test_a_reply_to_a_reaction_opens_a_thread_and_resolve_is_its_floor(browser, serve):
    """A reaction grows into a conversation only when someone replies to it: the agent
    answers a puzzling `no` on the reaction itself, and the panel then lists it as a
    thread whose root is the mark, painted as a comment's mark rather than a reaction's.
    Resolving it — the agent's, once it has acted — is the floor: the paint clears and
    nothing new is invented to absorb it."""
    url = serve(PANEL_PAGE)
    reaction = interact.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "version": 1,
            "token": "no",
            "anchor": {"section": "merge-both", "quote": "one document offline"},
        },
    )
    page, errors = open_page(browser, url)
    painted(page, [["merge-both", "no"]])
    expect(page.locator(".lf-comments")).to_have_text("Comments (0)")

    interact.cmd_reply(
        serve.page_dir, reaction["id"], "Which part — the case, or the answer?", ""
    )
    told(page)
    expect(page.locator(".lf-comments")).to_have_text("Comments (1)")
    page.locator(".lf-comments").click()
    panel_settled(page)
    thread = page.locator(f'.lf-thread[data-id="{reaction["id"]}"]')
    expect(thread.locator(".lf-react-said")).to_have_text("× no")
    assert painted(page, []) == {"washed": "", "glyphs": [], "outlined": []}
    assert page.evaluate("() => CSS.highlights.get('lf-mark').size") > 0

    interact.cmd_resolve(serve.page_dir, reaction["id"])
    told(page)
    expect(page.locator(".lf-comments")).to_have_text("Comments (0)")
    assert page.evaluate("() => CSS.highlights.get('lf-mark').size") == 0
    assert errors == []
    page.close()


def test_a_copy_keeps_a_standing_reaction_as_a_mark_and_drops_the_press(
    browser, serve, tmp_path
):
    """Export keeps standing reactions as their painted marks and drops the
    affordances, like every other control: the glyph stays in the margin with no tab
    stop or role, and the wash is written into the words, the highlight registry being
    script state no file can carry."""
    url = serve(PANEL_PAGE)
    interact.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "version": 1,
            "token": "cut",
            "anchor": {"section": "how-store", "quote": "every edit"},
        },
    )
    out = tmp_path / "copy.html"
    out.write_text(interact.export_page(browser, url, serve.page_dir))
    page = browser.new_page()
    errors = watched(page)
    page.goto(out.as_uri(), wait_until="load")
    copy = page.evaluate(
        """() => ({
          washed: [...document.querySelectorAll('mark.lf-react')].map(m => m.textContent),
          glyph: [...document.querySelectorAll('#how-store .lf-react-mark')]
            .map(m => [m.textContent, m.getAttribute('role'), m.getAttribute('tabindex')]),
        })"""
    )
    assert copy == {"washed": ["every edit"], "glyph": [["−", None, None]]}, copy
    assert errors == []
    page.close()
