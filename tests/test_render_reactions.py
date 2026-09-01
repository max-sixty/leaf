"""Reactions: one-press tokens on a passage, an item, a reply, or the page."""

import json
import re

import pytest
from leaf import conversation as conversation_model
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from playwright.sync_api import expect
from render_cases_navigation import pending_text
from render_harness import leaf_page
from render_support import (
    PANEL_PAGE,
    PART_DIAGRAM_PAGE,
    SUGGESTION_PAGE,
    TARGETS_PAGE,
    key_line,
    open_page,
    panel_comment,
    panel_settled,
    resized,
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
    .map(m => [m.parentElement.dataset.lfFor, m.dataset.token]),
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


NEAREST_HINT = """(selector) => {
  const target = document.querySelector(selector).getBoundingClientRect();
  return [...document.querySelectorAll('.lf-target-hint')]
    .sort((a, b) => {
      const ar = a.getBoundingClientRect(), br = b.getBoundingClientRect();
      return Math.hypot(ar.left - target.left, ar.top - target.top)
           - Math.hypot(br.left - target.left, br.top - target.top);
    })[0].dataset.lfTarget;
}"""


def hint_code(page, selector, hints):
    """Press `s` and hand back the code the hint nearest one item carries.

    The codes are the layer's to hand out, so a test naming one names whichever item
    the run gave it to. `hints` is the count the page offers, asserted before the codes
    are read: the overlay paints on a frame of its own, and a read before it lands finds
    no hint to be nearest to.
    """
    page.keyboard.press("s")
    expect(page.locator(".lf-target-hint")).to_have_count(hints)
    return page.evaluate(NEAREST_HINT, selector)


def painted(page, glyphs):
    """Wait for the page's reaction paint to show exactly these seated glyphs, then
    return the whole reading. `data-lf-applied` counts replayed actions and covers no
    comment, so the paint itself is the fact a reaction's arrival states."""
    page.wait_for_function(
        "(want) => JSON.stringify((" + PAINTED + ")().glyphs) === want",
        arg=json.dumps(glyphs, separators=(",", ":")),
    )
    return page.evaluate(PAINTED)


def test_a_late_standing_reaction_does_not_move_the_readable_column(browser, serve):
    """Passive information may join the RHS after presentation without claiming space."""
    page, errors = open_page(browser, serve(PANEL_PAGE))
    resized(page, 1440, 900)
    column = page.locator("main").evaluate(
        "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "token": "ok",
            "anchor": {"section": "how-store"},
        },
    )
    told(page)
    painted(page, [["how-store", "ok"]])
    assert (
        page.locator("main").evaluate(
            "el => { const box = el.getBoundingClientRect(); return [box.left, box.right]; }"
        )
        == column
    )
    expect(page.locator(".lf-reacts").locator("xpath=..")).not_to_have_attribute(
        "data-lf-claims-rail", ""
    )
    assert errors == []
    page.close()


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
    expect(bar.locator(".lf-fab-input")).to_be_visible()
    expect(bar.locator(".lf-fab-input")).not_to_be_focused()
    page.keyboard.press("c")
    expect(bar.locator(".lf-fab-input")).to_have_attribute(
        "placeholder", re.compile(r"^Comment… .*⏎$")
    )
    expect(bar.locator(".lf-fab-input")).to_have_attribute("autocomplete", "off")
    expect(bar.locator(".lf-fab-input")).to_have_attribute(
        "aria-label", re.compile(r"^Comment")
    )
    expect(
        bar.locator(":scope > .lf-react-trigger .lf-response-action-glyph")
    ).to_have_text("…")
    expect(bar.locator(".lf-react-trigger")).to_have_attribute(
        "aria-label", "Show other responses"
    )
    expect(bar.locator(".lf-react-trigger")).to_have_class(
        re.compile(r"lf-response-action")
    )
    expect(bar.locator(".lf-react-trigger")).to_have_attribute(
        "data-lf-behavior", "options"
    )
    expect(bar.locator(".lf-react:visible")).to_have_count(0)
    expect(bar.locator(".lf-fab-input")).to_be_focused()
    page.keyboard.press("Tab")
    surface = bar
    expect(bar).to_be_visible()
    expect(bar.locator(".lf-fab-input")).to_be_hidden()
    expect(surface).to_have_class(re.compile("lf-react-open"))
    expect(surface.locator(".lf-react-trigger:visible")).to_have_count(0)
    expect(surface.locator(".lf-react:visible")).to_have_count(6)
    expect(surface.locator(".lf-fab")).to_be_focused()

    surface.locator('.lf-react[data-token="cut"]').click()
    round_trip(page)
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["kind"] == "comment" and sent["token"] == "cut" and "text" not in sent
    assert sent["anchor"]["section"] == "how-store"
    assert "holds every edit" in sent["anchor"]["quote"]
    expect(bar).to_be_hidden()  # the mark is the receipt

    shown = painted(page, [["how-store", "cut"]])
    assert "holdseveryedit" in shown["washed"], shown
    assert shown["outlined"] == []
    # The receipt contributes to the target's one complete RHS item, which stands level
    # with the block's first line in the margin.
    level = page.evaluate(
        """() => {
          const p = document.querySelector('#how-store').getBoundingClientRect();
          const receipt = document.querySelector('.lf-reacts');
          const item = receipt.closest('.lf-margin-item');
          const g = item.getBoundingClientRect();
          return { dy: g.top - p.top, right: g.left - p.right,
                   target: item.dataset.lfMarginFor, parent: receipt.parentElement === item };
        }"""
    )
    assert (
        -2 <= level["dy"] <= 6
        and level["right"] > 0
        and level["target"] == "how-store"
        and level["parent"]
    ), level
    # A mark, not a thread: nothing in the panel, and nothing in its count.
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads (0)")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-thread")).to_have_count(0)
    # The panel's page row shows it standing nowhere: it is on a passage, not the page.
    assert (
        page.evaluate(
            "() => document.querySelectorAll('.lf-page-strip [aria-pressed=\"true\"]').length"
        )
        == 0
    )

    # The bar raised on the same passage again says the token stands, and pressing it
    # there is the same take-back as the glyph's. The panel closed first: open, it takes
    # the margin, the seat docks into the paragraph's own line, and a drag to the
    # paragraph's end would end on the glyph rather than on the words.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page, open=False)
    receipt_item = page.locator('.lf-margin-item[data-lf-margin-for="how-store"]')
    expect(receipt_item).not_to_have_class(re.compile("lf-docked"))
    select_paragraph(page, "#how-store")
    expect(bar).to_be_visible()
    bar.locator(".lf-react-trigger").click()
    surface = bar
    expect(receipt_item).to_have_count(1)
    expect(receipt_item.locator(":scope > .lf-reacts")).to_have_count(1)
    expect(receipt_item.locator(":scope > .lf-margin-reactions")).to_have_count(0)
    expect(surface.locator('.lf-react[data-token="cut"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(surface.locator('.lf-react[data-token="ok"]')).to_have_attribute(
        "aria-pressed", "false"
    )
    page.mouse.click(40, 300)  # the bar down, the glyph is the eraser
    expect(bar).to_be_hidden()
    page.locator('.lf-reacts .lf-react-mark[data-token="cut"]').click()
    round_trip(page)
    withdrawn = events_model.read_events(serve.page_dir)[-1]
    assert withdrawn["kind"] == "undo" and withdrawn["undoes"] == sent["id"]
    assert painted(page, []) == {"washed": "", "glyphs": [], "outlined": []}
    assert errors == []
    page.close()


def test_tab_changes_the_compact_bar_in_place_and_r_still_needs_a_target(
    browser, serve
):
    """Tab yields the compact field to one visually and semantically stable choice bar.

    Comment is the first stop, then Tab and arrows wrap through every visible response.
    Digits remain optional accelerators in declaration order. Once the surface has been
    dismissed, `r` with no target names what is missing without opening Threads.
    """
    page, errors = open_page(browser, serve(PANEL_PAGE))
    select_paragraph(page, "#how-cap")
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    expect(bar.locator(".lf-fab-input")).not_to_be_focused()
    page.keyboard.press("c")
    field_reading = bar.locator(".lf-fab-input").evaluate(
        """el => { const box = el.getBoundingClientRect(); const bar = el.closest('.lf-fab-bar');
          const style = getComputedStyle(el);
          return {
            center: Math.round(box.y + box.height / 2), parent: bar.parentElement.className,
            label: bar.getAttribute('aria-label'), fontFamily: style.fontFamily,
            fontSize: style.fontSize, fontWeight: style.fontWeight,
            height: Math.round(box.height), borderRadius: style.borderRadius,
            borderTopWidth: style.borderTopWidth, borderTopStyle: style.borderTopStyle,
            backgroundColor: style.backgroundColor, paddingTop: style.paddingTop,
            paddingBottom: style.paddingBottom, borderColor: style.borderTopColor,
            outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth,
            boxShadow: style.boxShadow}; }"""
    )
    trigger_shape = bar.locator(":scope > .lf-react-trigger").evaluate(
        """el => { const box = el.getBoundingClientRect(); const style = getComputedStyle(el);
              return [Math.round(box.height), style.borderRadius, style.fontFamily,
                      style.fontSize, style.fontWeight, style.borderTopWidth,
                      style.borderTopStyle]; }"""
    )
    page.keyboard.press("Tab")
    line = key_line(page)
    assert "1–6" in line and "react" in line, line
    surface = bar
    expect(surface).to_have_class(re.compile("lf-react-open"))
    expect(surface.locator(".lf-react-trigger:visible")).to_have_count(0)
    expect(surface.locator(".lf-react:visible")).to_have_count(6)
    expect(bar).to_be_visible()
    expect(bar.locator(".lf-fab-input")).to_be_hidden()
    expect(page.locator(".lf-margin-reactions")).to_have_count(0)
    expect(surface.locator(".lf-fab")).to_be_visible()
    choices = surface.locator(
        ":scope > .lf-response-action:visible, :scope > .lf-react-palette > .lf-react:visible"
    )
    expect(choices).to_have_count(8)
    assert (
        choices.evaluate_all(
            """els => els.map(el => { const box = el.getBoundingClientRect();
          const style = getComputedStyle(el);
              return [Math.round(box.height), style.borderRadius, style.fontFamily,
                      style.fontSize, style.fontWeight, style.borderTopWidth,
                      style.borderTopStyle]; })"""
        )
        == [trigger_shape] * 8
    )
    stable = surface.evaluate(
        """el => { const controls = [...el.querySelectorAll('.lf-response-action')]
            .filter(control => control.checkVisibility());
          return {parent: el.parentElement.className, label: el.getAttribute('aria-label'),
            centers: [...new Set(controls.map(control => { const box = control.getBoundingClientRect();
              return Math.round(box.y + box.height / 2); }))],
            heights: [...new Set(controls.map(control => Math.round(control.getBoundingClientRect().height)))],
            radii: [...new Set(controls.map(control => getComputedStyle(control).borderRadius))],
            backgrounds: [...new Set(controls.map(control => getComputedStyle(control).backgroundColor))],
            weights: [...new Set(controls.map(control => getComputedStyle(control).fontWeight))],
            families: [...new Set(controls.map(control => getComputedStyle(control).fontFamily))],
            sizes: [...new Set(controls.map(control => getComputedStyle(control).fontSize))],
            paddingTops: [...new Set(controls.map(control => getComputedStyle(control).paddingTop))],
            paddingBottoms: [...new Set(controls.map(control => getComputedStyle(control).paddingBottom))]}; }"""
    )
    assert stable == {
        "parent": field_reading["parent"],
        "label": field_reading["label"],
        "centers": [field_reading["center"]],
        "heights": [field_reading["height"]],
        "radii": [field_reading["borderRadius"]],
        "backgrounds": [field_reading["backgroundColor"]],
        "weights": [field_reading["fontWeight"]],
        "families": [field_reading["fontFamily"]],
        "sizes": [field_reading["fontSize"]],
        "paddingTops": [field_reading["paddingTop"]],
        "paddingBottoms": [field_reading["paddingBottom"]],
    }, (field_reading, stable)
    focused_reading = surface.locator(".lf-fab").evaluate(
        """el => { const style = getComputedStyle(el); return {
          borderColor: style.borderTopColor, outlineStyle: style.outlineStyle,
          outlineWidth: style.outlineWidth, boxShadow: style.boxShadow}; }"""
    )
    assert focused_reading == {
        key: field_reading[key]
        for key in ("borderColor", "outlineStyle", "outlineWidth", "boxShadow")
    }, (field_reading, focused_reading)
    expect(surface.locator(".lf-fab")).to_be_focused()
    page.keyboard.press("Tab")
    expect(surface.locator(".lf-fab-suggest")).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(surface.locator(".lf-fab")).to_be_focused()
    page.keyboard.press("ArrowLeft")
    expect(surface.locator('[aria-label="this"]')).to_be_focused()
    page.keyboard.press("ArrowRight")
    expect(surface.locator(".lf-fab")).to_be_focused()
    for label in ["Suggest", "ok", "no", "lost", "cut", "more", "this", "Comment"]:
        page.keyboard.press("ArrowRight")
        expect(surface.locator(f'[aria-label="{label}"]')).to_be_focused()
    assert (
        surface.locator(".lf-fab, .lf-react:visible").evaluate_all(
            """els => new Set(els.map(el => {
              const box = el.getBoundingClientRect();
              return Math.round(box.y + box.height / 2);
            })).size"""
        )
        == 1
    )
    expect(surface.locator(".lf-address")).to_have_count(0)
    page.keyboard.press("4")
    round_trip(page)
    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["token"], sent["anchor"]["section"]) == (
        "comment",
        "cut",
        "how-cap",
    )
    painted(page, [["how-cap", "cut"]])
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    # The sentence behind the chip, off the register: the reference's z row names the
    # token and the passage it stands on, where it promised a generic take-back before.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_be_visible()
    rows = page.locator(".lf-help").inner_text()
    assert "Take back: cut on “The store is capped" in rows, rows
    page.keyboard.press("Escape")
    expect(page.locator(".lf-help")).to_be_hidden()

    # Nothing selected: r opens no surface and explains what target is missing.
    page.keyboard.press("Escape")
    page.evaluate("() => getSelection().removeAllRanges()")
    page.keyboard.press("r")
    expect(page.locator(".lf-toast")).to_have_text("Select something to react to")
    expect(page.locator(".lf-panel")).to_be_hidden()
    expect(page.locator(".lf-fab-bar")).to_be_hidden()

    # Page-wide reactions remain explicit inside Threads instead of being r's fallback.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page_strip = page.locator(".lf-page-strip")
    expect(page_strip.locator(".lf-react:visible")).to_have_count(0)
    page_strip.locator(".lf-react-trigger").click()
    expect(page_strip.locator(".lf-react:visible")).to_have_count(6)
    page_strip.locator('.lf-react[data-token="more"]').click()
    round_trip(page)
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["token"] == "more" and "anchor" not in sent, sent
    expect(page.locator(".lf-panel")).to_be_visible()
    expect(
        page.locator('.lf-page-strip .lf-react[data-token="more"]')
    ).to_have_attribute("aria-pressed", "true")
    undo(page)
    expect(
        page.locator('.lf-page-strip .lf-react[data-token="more"]')
    ).to_have_attribute("aria-pressed", "false")
    assert errors == []
    page.close()


def test_an_item_hint_raises_the_bar_and_a_token_outlines_the_item(browser, serve):
    """Keyboard item selection leaves the response open. Choosing a token puts an
    element anchor in the log, which paints as a dashed hairline on the item's boxes
    and a glyph seated at its first line."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    page.keyboard.type(hint_code(page, "#prose", 3))
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(bar.locator(".lf-fab-input")).to_be_focused()
    bar.locator(".lf-react-trigger").click()
    bar.locator('.lf-react[data-token="this"]').click()
    round_trip(page)
    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["token"] == "this" and sent["anchor"] == {"section": "prose"}
    shown = painted(page, [["prose", "this"]])
    assert shown["outlined"] and shown["washed"] == "", shown
    assert errors == []
    page.close()


def test_putting_a_reaction_down_folds_back_only_the_cluster_it_unfolded(
    browser, serve
):
    """A raise stands the choices in the target's own fold, so putting them down folds
    that cluster back rather than leaving an empty fold for the reader to close. Only the
    cluster this raise unfolded, and only where it did the unfolding: the put-down runs on
    every disarm, a reply strip's included, and that one never raised the margin at all —
    `marginOffer?.unregister()` is written for exactly that case. Folding on the strength
    of the disarm alone took away a layer the gesture had never put on, from a reader
    working in the panel with their own `…` open out on the page."""
    url = serve(SUGGESTION_PAGE)
    root = panel_comment(serve.page_dir, "Why thistle?", {"section": "insert"})
    reply = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Claude",
            "parent": root,
            "text": "Because the finches take it through the cold.",
        },
    )["id"]
    page, errors = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    unfolded = page.locator("[data-lf-options-open]")
    item = page.locator('[data-lf-margin-for="sug-refill"]')
    more = item.locator(":scope > .lf-margin-more")
    more.click()
    expect(unfolded).to_have_count(1)

    # The reader's own fold, and a reaction on a reply whose surface is that reply's
    # strip: the disarm has no fold of its own to put back and must leave theirs alone.
    strip = page.locator(f'.lf-msg[data-mid="{reply}"] .lf-react-strip')
    strip.locator(".lf-react-trigger").click()
    expect(strip.locator(".lf-react:visible")).to_have_count(6)
    page.keyboard.press("Escape")
    expect(strip.locator(".lf-react:visible")).to_have_count(0)
    expect(unfolded).to_have_count(1)

    # Nor does the raise that finds the fold already open: standing the choices in a
    # cluster the reader unfolded for themselves borrows it, and `openButtonOptions` is
    # a no-op there, so putting them down leaves the fold where the press found it.
    # Focus goes back to the page first, the panel's own scope owning `s` where it is.
    page.evaluate("() => document.body.focus()")
    page.keyboard.type(hint_code(page, "#sug-refill", 10))
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.evaluate("() => document.body.focus()")
    page.keyboard.press("r")
    expect(page.locator(".lf-margin-reactions")).to_be_visible()
    expect(unfolded).to_have_count(1)
    expect(item).to_have_attribute("data-lf-options-open", "")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-reactions")).to_have_count(0)
    expect(item).to_have_attribute("data-lf-options-open", "")

    # The raise that does unfold a cluster to stand its choices in still folds it back.
    item.locator(".lf-margin-options .lf-margin-action:visible").first.focus()
    page.keyboard.press("Escape")
    expect(unfolded).to_have_count(0)
    select_paragraph(page, "#replace")
    # The bar standing is the selection's arrival: the anchor `r` reads is captured on
    # the frame that raises it, and a press before then has no reaction target at all.
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.evaluate("() => document.body.focus()")
    page.keyboard.press("r")
    surface = page.locator(".lf-margin-reactions")
    expect(surface).to_have_class(re.compile("lf-react-open"))
    expect(unfolded).to_have_count(1)
    page.keyboard.press("Escape")
    expect(surface).to_have_count(0)
    expect(unfolded).to_have_count(0)
    assert errors == []
    page.close()


def test_the_fold_a_put_down_takes_back_does_not_take_the_readers_focus(browser, serve):
    """The Escape rung folds from inside the cluster, so it can put the reader back on
    the `…` they opened it with. The put-down has no such standing: it runs on every
    disarm, from wherever the reader happens to be, so claiming the focus as well threw
    them out onto a cluster they had already left — and a press already on its way
    landed on a Button they were not standing on."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    unfolded = page.locator("[data-lf-options-open]")
    refill = page.locator('[data-lf-margin-for="sug-refill"]')
    thistle = page.locator('[data-lf-margin-for="sug-thistle"]')
    thistle_more = thistle.locator(":scope > .lf-margin-more")

    def raise_choices_on_refill():
        page.keyboard.type(hint_code(page, "#sug-refill", 10))
        expect(page.locator(".lf-fab-bar")).to_be_visible()
        page.evaluate("() => document.body.focus()")
        page.keyboard.press("r")
        expect(page.locator(".lf-margin-reactions")).to_be_visible()
        expect(refill).to_have_attribute("data-lf-options-open", "")

    # Standing on another cluster's `…` when the chord is disarmed: the choices go, the
    # fold the raise opened goes back, and the reader is left where they were standing.
    raise_choices_on_refill()
    thistle_more.focus()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-reactions")).to_have_count(0)
    expect(unfolded).to_have_count(0)
    expect(thistle_more).to_be_focused()

    # And the press that does the disarming reaches the Button it was aimed at. Enter on
    # that same `…` disarms first; a fold-back that moved focus would land the activation
    # on the other cluster instead, opening the fold the reader had just closed.
    raise_choices_on_refill()
    thistle_more.focus()
    page.keyboard.press("Enter")
    expect(unfolded).to_have_count(1)
    expect(thistle).to_have_attribute("data-lf-options-open", "")
    assert errors == []
    page.close()


@pytest.mark.parametrize("opener", ["click", "keyboard"])
def test_the_in_place_response_bar_stays_inside_a_narrow_screen(browser, serve, opener):
    """Changing the compact bar's contents does not create a second margin surface."""
    page, errors = open_page(browser, serve(PANEL_PAGE))
    resized(page, 390, 900)
    select_paragraph(page, "#how-cap")
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    if opener == "click":
        bar.locator(".lf-react-trigger").click()
    else:
        page.keyboard.press("Tab")
    expect(bar).to_have_class(re.compile("lf-react-open"))
    expect(page.locator(".lf-margin-reactions")).to_have_count(0)
    bounds = bar.bounding_box()
    banner = page.locator(".lf-banner").bounding_box()
    assert bounds and 8 <= bounds["x"] and bounds["x"] + bounds["width"] <= 382, bounds
    assert banner and bounds["y"] >= banner["y"] + banner["height"] + 6, (
        banner,
        bounds,
    )
    page.keyboard.press("Escape")
    expect(bar.locator(".lf-react-trigger")).to_be_visible()
    expect(bar.locator(".lf-fab-input")).to_be_focused()
    resized(page, 1280, 900)
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-reactions")).to_have_count(0)
    assert errors == []
    page.close()


def test_a_reaction_on_a_visual_part_names_and_outlines_only_that_part(browser, serve):
    """A declared visual part is the same anchor for a reaction and a comment. The
    send announcement names the part's declared label, while replay paints only the
    part's resolved box rather than the diagram that owns its stable id."""
    page, errors = open_page(browser, serve(PART_DIAGRAM_PAGE))
    diagram = page.locator("#flow")
    start = diagram.locator('g[id*="flowchart-S-"]')
    start.click()
    expect(page.locator(".lf-fab-bar")).to_be_visible()

    page.keyboard.press("Tab")
    surface = page.locator(".lf-fab-bar")
    expect(surface.locator(".lf-fab-suggest")).to_be_hidden()
    expect(surface.locator(".lf-fab")).to_be_focused()
    page.keyboard.press("ArrowLeft")
    reaction = page.locator('.lf-fab-bar .lf-react[data-token="this"]')
    expect(reaction).to_be_focused()
    page.evaluate("() => window.lfTestReactionClicked = false")
    reaction.evaluate(
        "button => button.addEventListener('click', () => "
        "window.lfTestReactionClicked = true, {once: true})"
    )
    # The register owns Space on keydown. A miss here can look healthy after keyup,
    # because Chromium's native button behavior then supplies a click of its own.
    page.keyboard.down("Space")
    assert page.evaluate("() => window.lfTestReactionClicked")
    page.keyboard.up("Space")
    round_trip(page)
    expect(page.locator(".lf-live")).to_contain_text("this on Start request")

    sent = events_model.read_events(serve.page_dir)[-1]
    assert sent["token"] == "this" and sent["anchor"] == {
        "section": "flow",
        "visual": "node:S",
    }
    shown = painted(page, [["flow", "this"]])
    assert shown["outlined"] == [start.get_attribute("id")], shown
    expect(diagram).not_to_have_class(re.compile(r"\blf-react-el\b"))
    assert errors == []
    page.close()


def test_a_whole_visual_reaction_does_not_stand_on_one_of_its_parts(browser, serve):
    """Whole and part anchors differ in both directions: a reaction on the diagram
    must not read pressed when the action bar moves to one declared node."""
    url = serve(PART_DIAGRAM_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "token": "this",
            "anchor": {"section": "flow"},
        },
    )
    page, errors = open_page(browser, url)
    page.locator('#flow g[id*="flowchart-S-"]').click()
    expect(page.locator('.lf-fab-bar .lf-react[data-token="this"]')).to_have_attribute(
        "aria-pressed", "false"
    )
    assert errors == []
    page.close()


def test_a_visual_target_places_the_bar_from_the_target_and_keeps_it_through_reflow(
    browser, serve
):
    """The target, not the point inside it, places the action bar. A layout change
    resolves that same target again, and the quiet outline stays on it until an
    outside press dismisses both."""
    page, errors = open_page(browser, serve(PART_DIAGRAM_PAGE))
    start = page.locator('#flow g[id*="flowchart-S-"]')
    bar = page.locator(".lf-fab-bar")

    box = start.bounding_box()
    page.mouse.click(box["x"] + 4, box["y"] + box["height"] / 2)
    assert errors == []
    expect(bar).to_be_visible()
    expect(start).to_have_class(re.compile(r"\blf-pending\b"))
    first = bar.bounding_box()

    page.mouse.click(
        box["x"] + box["width"] - 4,
        box["y"] + box["height"] / 2,
    )
    second = bar.bounding_box()
    assert abs(second["x"] - first["x"]) <= 1, (first, second)
    assert abs(second["y"] - first["y"]) <= 1, (first, second)

    resized(page, 860, 720)
    after_resize = bar.bounding_box()
    box = start.bounding_box()
    page.mouse.click(
        box["x"] + box["width"] / 2,
        box["y"] + box["height"] - 4,
    )
    after_reactivation = bar.bounding_box()
    assert abs(after_resize["x"] - after_reactivation["x"]) <= 1, (
        after_resize,
        after_reactivation,
    )
    assert abs(after_resize["y"] - after_reactivation["y"]) <= 1, (
        after_resize,
        after_reactivation,
    )

    page.locator('#flow g[id*="flowchart-U-"]').click()
    expect(page.locator("#flow")).to_have_class(re.compile(r"\blf-pending\b"))
    expect(start).not_to_have_class(re.compile(r"\blf-pending\b"))
    whole = bar.bounding_box()
    assert (
        abs(whole["x"] - after_reactivation["x"]) > 1
        or abs(whole["y"] - after_reactivation["y"]) > 1
    ), (after_reactivation, whole)

    start.click()
    expect(start).to_have_class(re.compile(r"\blf-pending\b"))
    expect(page.locator("#flow")).not_to_have_class(re.compile(r"\blf-pending\b"))

    page.locator("h1").click()
    expect(bar).to_be_hidden()
    expect(start).not_to_have_class(re.compile(r"\blf-pending\b"))
    assert errors == []
    page.close()


def test_a_declared_visual_keeps_its_parts_inside_a_generic_figure(browser, serve):
    """A semantic visual provider owns hits inside it even when ordinary figure markup
    wraps it. The generic fallback must not swallow the provider's stable part API."""
    wrapped = PART_DIAGRAM_PAGE.replace(
        '<lf-diagram id="flow"', '<figure id="frame"><lf-diagram id="flow"', 1
    ).replace(
        "</lf-diagram>",
        '</lf-diagram><figcaption id="caption">Request path caption</figcaption></figure>',
        1,
    )
    page, errors = open_page(browser, serve(wrapped))
    start = page.locator('#flow g[id*="flowchart-S-"]')

    page.locator("#caption").click()
    expect(page.locator("#flow")).to_have_class(re.compile(r"\blf-pending\b"))
    expect(page.locator("#frame")).not_to_have_class(re.compile(r"\blf-pending\b"))
    assert page.locator(".lf-visual-action").evaluate_all(
        "controls => controls.map(control => control.lfAnchor)"
    ) == [
        {"section": "flow"},
        {"section": "flow", "visual": "node:S"},
    ]

    start.click()
    expect(start).to_have_class(re.compile(r"\blf-pending\b"))
    expect(page.locator(".lf-fab-bar")).to_have_attribute(
        "aria-label", re.compile("Start request")
    )
    expect(page.get_by_role("button", name="Respond to Start request")).to_have_count(1)
    assert errors == []
    page.close()


def test_native_controls_keep_visual_gestures_they_already_own(browser, serve):
    """A linked picture and a button icon retain their native activation. Leaf adds no
    nested proxy and pointer activation does not raise the visual action bar."""
    page_markup = leaf_page(
        "interactive pictures",
        """
<h1 id="top">Interactive pictures</h1>
<a id="visit" href="#after"><svg id="linked-picture" viewBox="0 0 20 20" width="40" height="40"><circle cx="10" cy="10" r="8" /></svg></a>
<button id="native-button" type="button"><svg id="button-picture" viewBox="0 0 20 20" width="20" height="20"><circle cx="10" cy="10" r="8" /></svg>Run</button>
<p id="after">Destination</p>
""",
    )
    page, errors = open_page(browser, serve(page_markup))

    expect(page.locator(".lf-visual-action")).to_have_count(0)
    page.locator("#linked-picture").click()
    expect(page).to_have_url(re.compile(r"#after$"))
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    page.locator("#button-picture").click()
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    assert errors == []
    page.close()


def test_custom_controls_keep_visual_gestures_they_already_own(browser, serve):
    """ARIA widgets are controls even when their implementation contains a picture.
    The shared interaction boundary keeps Leaf from adding a second activation target."""
    page_markup = leaf_page(
        "custom control pictures",
        """
<h1 id="top">Custom control pictures</h1>
<div id="gain" role="slider" tabindex="0" aria-label="Gain" aria-valuemin="0" aria-valuemax="10" aria-valuenow="5">
  <svg id="gain-picture" viewBox="0 0 100 20" width="200" height="40"><rect x="0" y="8" width="100" height="4" /></svg>
</div>
""",
    )
    page, errors = open_page(browser, serve(page_markup))

    expect(page.locator(".lf-visual-action")).to_have_count(0)
    page.locator("#gain-picture").click()
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    assert errors == []
    page.close()


def test_a_declared_visual_part_can_raise_the_same_bar_from_the_keyboard(
    browser, serve
):
    """A declared visual part is a keyboard target as well as a pointer target.
    Enter uses the click path and wins over an older text selection, just as a fresh
    pointer activation does."""
    page, errors = open_page(browser, serve(PART_DIAGRAM_PAGE))
    title = page.locator("h1")
    box = title.bounding_box()
    select(
        page,
        (box["x"] + 2, box["y"] + box["height"] / 2),
        (box["x"] + box["width"] - 2, box["y"] + box["height"] / 2),
    )
    expect(page.locator(".lf-fab-bar")).to_be_visible()

    start = page.locator('#flow g[id*="flowchart-S-"]')
    expect(start).not_to_have_attribute("role", "button")
    expect(start).not_to_have_attribute("tabindex", re.compile(".+"))
    expect(page.get_by_role("button", name="Respond to Handle request")).to_have_count(
        0
    )

    whole_control = page.locator(".lf-visual-action").first
    page.locator("#flow").evaluate("flow => { flow.style.marginTop = '1100px'; }")
    whole_control.focus()
    expect(page.locator("#flow")).to_be_in_viewport()
    page.keyboard.press("Enter")
    expect(page.locator("#flow")).to_have_class(re.compile(r"\blf-pending\b"))
    assert page.evaluate("() => getSelection().toString().trim()") == ""
    whole_bar = page.locator(".lf-fab-bar").bounding_box()
    keyline = page.locator(".lf-keyline").bounding_box()
    assert (
        whole_bar["x"] + whole_bar["width"] <= keyline["x"]
        or keyline["x"] + keyline["width"] <= whole_bar["x"]
        or whole_bar["y"] + whole_bar["height"] <= keyline["y"] - 6
    ), (whole_bar, keyline)

    control = page.locator(".lf-visual-action").filter(
        has_text=re.compile(r"^Respond to Start request$")
    )
    control.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(start).to_have_class(re.compile(r"\blf-pending\b"))
    assert page.evaluate("() => getSelection().toString().trim()") == ""
    expect(page.locator(".lf-fab-input")).to_be_focused()
    # The captured target spends the short line's two contextual slots on immediate
    # comment entry and the route to its other responses.
    line = key_line(page)
    assert "comment" in line and "other responses" in line
    assert "unselect" not in line

    page.keyboard.press("Escape")
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    expect(start).not_to_have_class(re.compile(r"\blf-pending\b"))
    expect(control).to_be_focused()
    assert errors == []
    page.close()


def test_one_semantic_visual_target_gets_one_keyboard_proxy(browser, serve):
    """Sibling anonymous pictures under one authored item are one durable target. Leaf
    exposes one Tab stop for that anchor and returns Escape to the control that opened it."""
    page_markup = leaf_page(
        "picture gallery",
        """
<h1 id="top">Picture gallery</h1>
<section id="gallery">
  <h2>Gallery</h2>
  <svg viewBox="0 0 20 20" width="40" height="40"><circle cx="10" cy="10" r="8" /></svg>
  <svg viewBox="0 0 20 20" width="40" height="40"><rect x="2" y="2" width="16" height="16" /></svg>
</section>
""",
    )
    page, errors = open_page(browser, serve(page_markup))
    controls = page.locator(".lf-visual-action")

    expect(controls).to_have_count(1)
    control = controls.first
    control.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.keyboard.press("Escape")
    expect(control).to_be_focused()
    assert errors == []
    page.close()


def test_a_visual_proxy_resolves_a_rebuilt_part_and_reveals_it_on_focus(browser, serve):
    """A retained proxy resolves its stable anchor when focused. It does not keep a
    renderer node that has been replaced, and it opens the container before scrolling."""
    folded = PART_DIAGRAM_PAGE.replace(
        '<lf-diagram id="flow"',
        '<details id="folded" open><summary>Flow</summary><lf-diagram id="flow"',
        1,
    ).replace("</lf-diagram>", "</lf-diagram></details>", 1)
    page, errors = open_page(browser, serve(folded))
    control = page.locator(".lf-visual-action").filter(
        has_text=re.compile(r"^Respond to Start request$")
    )
    expect(control).to_have_count(1)
    page.evaluate(
        """() => {
          const oldPart = document.querySelector('#flow g[id*="flowchart-S-"]');
          const newPart = oldPart.cloneNode(true);
          oldPart.scrollIntoView = () => { window.lfScrolledPart = 'old'; };
          newPart.scrollIntoView = () => { window.lfScrolledPart = 'new'; };
          oldPart.replaceWith(newPart);
          document.querySelector('#flow').visualParts.set('node:S', {
            element: newPart,
            label: 'Start request',
          });
          document.querySelector('#folded').open = false;
        }"""
    )

    control.focus()
    expect(control).to_be_focused()
    expect(page.locator("#folded")).to_have_attribute("open", "")
    assert page.evaluate("() => window.lfScrolledPart") == "new"
    assert errors == []
    page.close()


def test_a_visual_proxy_keeps_focus_when_a_provider_changes_its_label(browser, serve):
    """A provider can update one part's current label without replacing the proxy for
    that stable anchor. The focused control changes its name and remains focused."""
    page, errors = open_page(browser, serve(PART_DIAGRAM_PAGE))
    control = page.locator(".lf-visual-action").filter(
        has_text=re.compile(r"^Respond to Start request$")
    )
    control.focus()
    control.evaluate("control => { window.lfRetainedVisualControl = control; }")
    page.evaluate(
        """() => {
          const diagram = document.querySelector('#flow');
          const current = diagram.visualParts.get('node:S');
          diagram.visualParts.set('node:S', { ...current, label: 'Begin request' });
          document.dispatchEvent(new CustomEvent('lf-projection'));
        }"""
    )

    page.wait_for_function(
        "() => window.lfRetainedVisualControl.textContent.endsWith('Begin request')"
    )
    assert page.evaluate(
        """() => window.lfRetainedVisualControl.isConnected &&
          document.activeElement === window.lfRetainedVisualControl"""
    )
    assert errors == []
    page.close()


def test_visual_proxies_keep_focus_when_one_shadow_host_is_repainted(browser, serve):
    """Several visuals staged in one declared shadow root share a stable proxy holder.
    Repainting anchors must not detach and blur the control the reader is standing on."""
    page_markup = leaf_page(
        "shadow pictures",
        """
<h1 id="top">Shadow pictures</h1>
<lf-diff id="patch"><pre>
diff --git a/value.txt b/value.txt
--- a/value.txt
+++ b/value.txt
@@ -1 +1 @@
-before
+after
</pre></lf-diff>
""",
    )
    page, errors = open_page(browser, serve(page_markup))
    page.evaluate(
        """() => {
          const root = document.querySelector('#patch').shadowRoot;
          for (const id of ['shadow-first', 'shadow-second']) {
            const picture = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            picture.id = id;
            picture.setAttribute('viewBox', '0 0 20 20');
            root.append(picture);
          }
          document.dispatchEvent(new CustomEvent('lf-projection'));
        }"""
    )
    controls = page.locator(".lf-visual-action")
    expect(controls).to_have_count(2)
    expect(page.locator(".lf-visual-actions")).to_have_count(1)
    second = controls.nth(1)
    second.focus()
    expect(second).to_be_focused()

    page.evaluate("() => document.dispatchEvent(new CustomEvent('lf-projection'))")
    expect(second).to_be_focused()
    assert errors == []
    page.close()


def test_a_visual_action_follows_its_own_scroller_until_the_target_is_gone(
    browser, serve
):
    """The shared placement path listens to nested scroll boxes, clips target
    geometry to what is actually shown, and retracts the bar once none remains."""
    page, errors = open_page(browser, serve(PART_DIAGRAM_PAGE))
    diagram = page.locator("#flow")
    start = diagram.locator('g[id*="flowchart-S-"]')
    bar = page.locator(".lf-fab-bar")
    diagram.evaluate("element => { element.style.width = '240px'; }")

    control = page.get_by_role("button", name="Respond to Start request")
    control.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    before_target = start.bounding_box()
    before_bar = bar.bounding_box()
    moved = diagram.evaluate(
        """element => {
          element.scrollLeft = Math.min(24, element.scrollWidth - element.clientWidth);
          return element.scrollLeft;
        }"""
    )
    assert moved > 0
    page.wait_for_function(
        """([was, beforeTarget]) => {
          const now = document.querySelector('.lf-fab-bar').getBoundingClientRect();
          const box = document.querySelector('#flow g[id*="flowchart-S-"]')
            .getBoundingClientRect();
          return Math.abs(now.left - was) > 1 && box.left < beforeTarget;
        }""",
        arg=[before_bar["x"], before_target["x"]],
    )
    after_target = start.bounding_box()
    after_bar = bar.bounding_box()
    assert (
        abs(
            (after_bar["x"] - before_bar["x"])
            - (after_target["x"] - before_target["x"])
        )
        <= 2
    ), (before_target, before_bar, after_target, after_bar)

    diagram.evaluate("element => { element.scrollLeft = element.scrollWidth; }")
    expect(bar).to_be_hidden()
    expect(start).not_to_have_class(re.compile(r"\blf-pending\b"))
    assert page.evaluate("() => document.activeElement === document.body")
    assert errors == []
    page.close()


def test_dragging_a_diagram_label_keeps_the_passage_instead_of_clicking_the_node(
    browser, serve
):
    """The compatibility click after a drag must not replace freshly selected words
    with the visual target that happens to contain the drag's endpoint."""
    page, errors = open_page(browser, serve(PART_DIAGRAM_PAGE))
    start = page.locator('#flow g[id*="flowchart-S-"]')
    label = start.get_by_text("Start request", exact=True)
    box = label.bounding_box()
    select(
        page,
        (box["x"] + 2, box["y"] + box["height"] / 2),
        (box["x"] + box["width"] - 2, box["y"] + box["height"] / 2),
        steps=12,
    )

    expect(page.locator(".lf-fab-bar")).to_be_visible()
    assert "Start request" in pending_text(page)
    expect(start).not_to_have_class(re.compile(r"\blf-pending\b"))
    expect(page.locator(".lf-fab-bar")).to_have_attribute(
        "aria-label", re.compile("Start request")
    )

    # Repeating the same drag still counts as a selection gesture even though the final
    # semantic passage equals the selection that existed before the press.
    select(
        page,
        (box["x"] + 2, box["y"] + box["height"] / 2),
        (box["x"] + box["width"] - 2, box["y"] + box["height"] / 2),
        steps=12,
    )
    # Focusing the composer collapses the native range, but the durable pending paint
    # still names the repeated passage captured by the compatibility click.
    page.wait_for_function(
        "() => [...(CSS.highlights.get('lf-pending') ?? [])].some(r => r.toString().includes('Start request'))"
    )
    assert "Start request" in pending_text(page)
    expect(start).not_to_have_class(re.compile(r"\blf-pending\b"))

    # A plain click is not a drag. It can still choose the visual under the retained
    # passage, and that explicit target clears the native selection.
    start.click()
    assert page.evaluate("() => getSelection().toString()") == ""
    expect(start).to_have_class(re.compile(r"\blf-pending\b"))
    assert errors == []
    page.close()


def test_a_keyboard_reaction_returns_focus_to_the_visual_target(browser, serve):
    """When a keyboard-raised action completes, focus returns to the proxy that named
    the target instead of remaining inside a hidden action bar."""
    page, errors = open_page(browser, serve(PART_DIAGRAM_PAGE))
    control = page.get_by_role("button", name="Respond to Start request")
    control.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    page.keyboard.press("Tab")
    page.keyboard.press("1")
    round_trip(page)
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    expect(control).to_be_focused()
    assert errors == []
    page.close()


def test_a_selection_change_replaces_and_clears_a_visual_target(browser, serve):
    """Selection changes can come from touch handles and browser commands without a
    mouseup or keyup in the page. The new passage replaces the visual target, and
    clearing that passage dismisses the shared action surface."""
    page, errors = open_page(browser, serve(PART_DIAGRAM_PAGE))
    control = page.get_by_role("button", name="Respond to Start request")
    start = page.locator('#flow g[id*="flowchart-S-"]')
    control.focus()
    page.keyboard.press("Enter")
    expect(start).to_have_class(re.compile(r"\blf-pending\b"))

    page.evaluate(
        """() => {
          document.activeElement.blur();
          const text = document.querySelector('h1').firstChild;
          const range = document.createRange();
          range.selectNodeContents(text);
          const selection = getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
        }"""
    )
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(start).not_to_have_class(re.compile(r"\blf-pending\b"))

    page.evaluate(
        "() => { document.activeElement.blur(); getSelection().removeAllRanges(); }"
    )
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    assert errors == []
    page.close()


def test_a_copy_drops_visual_action_controls_without_rewriting_the_provider(
    browser, serve, tmp_path
):
    """Keyboard parity belongs to the live Leaf layer: an exported drawing keeps
    neither dead controls nor runtime roles on Mermaid's generated SVG."""
    url = serve(PART_DIAGRAM_PAGE)
    out = tmp_path / "diagram-copy.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    page = browser.new_page()
    errors = watched(page)
    page.goto(out.as_uri(), wait_until="load")
    assert page.evaluate(
        """() => ({
          controls: document.querySelectorAll('.lf-visual-action').length,
          rewritten: document.querySelectorAll(
            '#flow g[role="button"], #flow g[tabindex]'
          ).length,
        })"""
    ) == {"controls": 0, "rewritten": 0}
    assert errors == []
    page.close()


def test_a_thread_at_rest_shows_only_the_marks_that_stand_in_it(browser, serve):
    """A thread at rest shows one ellipsis on its latest agent reply and any marks
    already standing on earlier replies. Entering by pointer or t/T focus reveals older
    ellipses, but the reaction buttons appear only on the one surface the reader opens.
    Taking back the last mark closes the list and returns focus to its ellipsis."""
    url = serve(PANEL_PAGE)
    root, first = _thread(serve.page_dir)
    events_model.append_event(
        serve.page_dir,
        {"kind": "reply", "author": "user", "parent": first, "token": "lost"},
    )
    events_model.append_event(
        serve.page_dir,
        {"kind": "reply", "author": "user", "parent": root, "text": "Which device?"},
    )
    latest = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Claude",
            "parent": root,
            "text": "The one we ship to schools.",
        },
    )["id"]
    quiet_root, quiet_first = _thread(serve.page_dir)
    quiet_latest = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Claude",
            "parent": quiet_root,
            "text": "And nothing stands on the earlier answer here.",
        },
    )["id"]
    page, errors = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    def strip(mid):
        return page.locator(f'.lf-msg[data-mid="{mid}"] .lf-react-strip')

    def card(mid):
        return page.locator(f'.lf-thread:has(.lf-msg[data-mid="{mid}"])')

    # At rest: one trigger under the latest reply of each thread, the marks elsewhere.
    expect(strip(latest).locator(".lf-react-trigger:visible")).to_have_count(1)
    expect(strip(quiet_latest).locator(".lf-react-trigger:visible")).to_have_count(1)
    expect(strip(latest).locator(".lf-react:visible")).to_have_count(0)
    expect(strip(quiet_latest).locator(".lf-react:visible")).to_have_count(0)
    expect(strip(first).locator(".lf-react:visible")).to_have_count(1)
    expect(strip(first).locator(".lf-react:visible")).to_have_attribute(
        "data-token", "lost"
    )
    # The row is built either way; an older empty one takes no room at rest.
    expect(strip(quiet_first).locator(".lf-react")).to_have_count(6)
    expect(strip(quiet_first).locator(".lf-react:visible")).to_have_count(0)
    expect(strip(quiet_first).locator(".lf-react-trigger:visible")).to_have_count(0)
    assert strip(quiet_first).evaluate("(s) => s.getBoundingClientRect().height") == 0

    # The pointer over the card offers each reply's ellipsis without opening its list.
    card(quiet_latest).hover()
    expect(strip(quiet_first).locator(".lf-react-trigger:visible")).to_have_count(1)
    expect(strip(quiet_first).locator(".lf-react:visible")).to_have_count(0)
    page.mouse.move(4, 4)
    expect(strip(quiet_first).locator(".lf-react-trigger:visible")).to_have_count(0)

    # The keyboard's route in is the focus the walk puts on the card; r opens the latest
    # agent reply in that thread without disturbing the standing mark on an older reply.
    card(first).focus()
    page.keyboard.press("r")
    expect(strip(latest)).to_have_class(re.compile("lf-react-open"))
    expect(strip(latest).locator(".lf-react:visible")).to_have_count(6)
    expect(strip(first).locator(".lf-react:visible")).to_have_count(1)
    page.keyboard.press("Escape")

    # An older reply remains available through its explicit trigger while in the thread.
    expect(strip(first).locator(".lf-react-trigger:visible")).to_have_count(1)
    strip(first).locator(".lf-react-trigger").click()
    expect(strip(first).locator(".lf-react:visible")).to_have_count(6)

    # Taking the last mark off a reply closes the list and returns focus to its ellipsis.
    # Reopening offers the same action again without leaving the token wall out.
    mark = strip(first).locator('.lf-react[data-token="lost"]')
    mark.press("Enter")
    round_trip(page)
    withdrawn = events_model.read_events(serve.page_dir)[-1]
    assert withdrawn["kind"] == "undo", withdrawn
    expect(mark).to_have_attribute("aria-pressed", "false")
    expect(mark).to_be_hidden()
    expect(strip(first).locator(".lf-react-trigger")).to_be_focused()
    strip(first).locator(".lf-react-trigger").click()
    mark.press("Enter")
    round_trip(page)
    again = events_model.read_events(serve.page_dir)[-1]
    assert (again["kind"], again["token"], again["parent"]) == ("reply", "lost", first)

    assert errors == []
    page.close()


def _thread(page_dir):
    """A thread the agent spoke in last: the reader's question and Claude's answer."""
    root = panel_comment(page_dir, "Why forty?", {"section": "how-cap"})
    reply = events_model.append_event(
        page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Claude",
            "parent": root,
            "text": "Forty is what the slowest device we ship on can hold.",
            "awaits": True,
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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    strip = page.locator(f'.lf-msg[data-mid="{reply}"] .lf-react-strip')
    expect(strip).to_be_visible()
    expect(strip.locator(".lf-react")).to_have_count(6)
    expect(strip.locator(".lf-react:visible")).to_have_count(0)
    # The reader's own message wears no strip: a reaction is on what the agent said.
    expect(page.locator(f'.lf-msg[data-mid="{root}"] .lf-react-strip')).to_have_count(0)
    page.locator(".lf-needs").click()  # the waiting-on-you narrowing
    expect(page.locator(".lf-needs")).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".lf-thread")).to_have_count(1)

    strip.locator(".lf-react-trigger").click()
    expect(strip.locator(".lf-react:visible")).to_have_count(6)
    strip.locator('.lf-react[data-token="no"]').click()
    round_trip(page)
    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["parent"], sent["token"]) == ("reply", reply, "no")
    expect(strip.locator('.lf-react[data-token="no"]')).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.locator(".lf-thread")).to_have_count(1)  # `no` settles nothing

    strip.locator(".lf-react-trigger").click()
    strip.locator('.lf-react[data-token="ok"]').click()
    round_trip(page)
    ok = events_model.read_events(serve.page_dir)[-1]
    assert ok["token"] == "ok" and ok["parent"] == reply
    expect(page.locator(".lf-needs")).to_have_text("Waiting on you")  # none
    expect(page.locator(".lf-thread")).to_have_count(0)  # out of "waiting on you"
    # The mark, pressed again, is the eraser — and the wait comes back with the undo.
    page.locator(".lf-needs").click()  # every comment again, so the strip is on screen
    expect(page.locator(".lf-thread")).to_have_count(1)
    strip.locator('.lf-react[data-token="ok"]').click()
    round_trip(page)
    withdrawn = events_model.read_events(serve.page_dir)[-1]
    assert withdrawn["kind"] == "undo" and withdrawn["undoes"] == ok["id"]
    expect(page.locator(".lf-needs")).to_have_text("Waiting on you (1)")
    expect(strip.locator('.lf-react[data-token="ok"]')).to_have_attribute(
        "aria-pressed", "false"
    )
    assert errors == []
    page.close()


@pytest.mark.parametrize("removal", ["resolve", "filter"], ids=["fold", "filter"])
def test_removing_an_open_reply_list_disarms_its_keyboard_mode(browser, serve, removal):
    """A remote resolve or settlement can remove the reply whose list is open without
    a pointer or focus gesture in this tab. The detached list stops owning digits, so
    a later key cannot react to a message that is no longer on screen."""
    url = serve(PANEL_PAGE)
    root, reply = _thread(serve.page_dir)
    page, errors = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    if removal == "filter":
        page.locator(".lf-needs").click()
        expect(page.locator(".lf-thread")).to_have_count(1)
    strip = page.locator(f'.lf-msg[data-mid="{reply}"] .lf-react-strip')
    strip.locator(".lf-react-trigger").click()
    expect(strip).to_have_class(re.compile("lf-react-open"))

    if removal == "resolve":
        conversation_model.cmd_resolve(serve.page_dir, root)
    else:
        events_model.append_event(
            serve.page_dir,
            {"kind": "reply", "author": "user", "parent": reply, "token": "ok"},
        )
    told(page)
    expect(page.locator(".lf-react-open")).to_have_count(0)
    if removal == "filter":
        expect(page.locator(".lf-thread")).to_have_count(0)
    count = len(events_model.read_events(serve.page_dir))
    page.keyboard.press("1")
    page.wait_for_timeout(100)
    assert len(events_model.read_events(serve.page_dir)) == count
    assert "1–6" not in key_line(page)
    assert errors == []
    page.close()


def test_a_reply_to_a_reaction_opens_a_thread_and_resolve_is_its_floor(browser, serve):
    """A reaction grows into a conversation only when someone replies to it: the agent
    answers a puzzling `no` on the reaction itself, and the panel then lists it as a
    thread whose root is the mark, painted as a comment's mark rather than a reaction's.
    Resolving it — the agent's, once it has acted — is the floor: the paint clears and
    nothing new is invented to absorb it."""
    url = serve(PANEL_PAGE)
    reaction = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "token": "no",
            "anchor": {"section": "merge-both", "quote": "one document offline"},
        },
    )
    page, errors = open_page(browser, url)
    painted(page, [["merge-both", "no"]])
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads (0)")

    conversation_model.cmd_reply(
        serve.page_dir, reaction["id"], "Which part — the case, or the answer?", ""
    )
    told(page)
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads (1)")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-thread[data-id="{reaction["id"]}"]')
    expect(thread.locator(".lf-react-said")).to_have_text("× no")
    assert painted(page, []) == {"washed": "", "glyphs": [], "outlined": []}
    assert page.evaluate("() => CSS.highlights.get('lf-mark').size") > 0

    conversation_model.cmd_resolve(serve.page_dir, reaction["id"])
    told(page)
    expect(page.locator(".lf-threads-toggle")).to_have_text("Threads (0)")
    assert page.evaluate("() => CSS.highlights.get('lf-mark').size") == 0
    assert errors == []
    page.close()


def test_escape_clears_selection_and_keeps_actions_dismissed(browser, serve):
    """Escape gives back the selected target and its action layer together. The keyup
    half of the same press must not immediately raise the bar again."""
    page, errors = open_page(browser, serve(PANEL_PAGE))
    select_paragraph(page, "#how-store")
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    bar.locator("button[data-lf-offer], [data-lf-offer][tabindex]").first.focus()

    page.keyboard.press("Escape")
    page.evaluate("() => new Promise(resolve => setTimeout(resolve, 0))")
    assert not bar.is_visible()
    assert page.evaluate("() => getSelection().toString()") == ""
    assert errors == []
    page.close()


def test_a_copy_keeps_a_standing_reaction_as_a_mark_and_drops_the_press(
    browser, serve, tmp_path
):
    """Export keeps standing reactions as their painted marks and drops the
    affordances, like every other control: the glyph stays in the margin with no tab
    stop and nothing calling it a press, and the wash is written into the words, the
    highlight registry being script state no file can carry.

    The role it does keep is the picture's. The glyph is aria-hidden paint and the word
    beside it is collapsed away, so the token is the mark's name or the mark has none,
    and a name on a role-less span is the one place the platform refuses one."""
    url = serve(PANEL_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "token": "cut",
            "anchor": {"section": "how-store", "quote": "every edit"},
        },
    )
    out = tmp_path / "copy.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    page = browser.new_page()
    errors = watched(page)
    page.goto(out.as_uri(), wait_until="load")
    copy = page.evaluate(
        """() => ({
          washed: [...document.querySelectorAll('mark.lf-react')].map(m => m.textContent),
          glyph: [...document.querySelectorAll(
            '.lf-margin-item[data-lf-margin-for="how-store"] .lf-react-mark'
          )]
            .map(m => [m.innerText, m.getAttribute('role'),
                       m.getAttribute('aria-label'), m.getAttribute('tabindex')]),
        })"""
    )
    assert copy == {"washed": ["every edit"], "glyph": [["−", "img", "cut", None]]}, (
        copy
    )
    # The other half of the same promise, and the half no gate can see: the copy's
    # `offering` reads the cursor and nothing else, so paint that arrives with the
    # pointer rather than standing on the page is invisible to it. A receipt in a file
    # that lifts under the pointer says a press is there to take.
    mark = page.locator(
        '.lf-margin-item[data-lf-margin-for="how-store"] .lf-react-mark'
    )
    resting = mark.evaluate("el => getComputedStyle(el).backgroundColor")
    mark.hover()
    assert mark.evaluate("el => getComputedStyle(el).backgroundColor") == resting
    assert errors == []
    page.close()
