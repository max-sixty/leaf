"""Keyboard semantic-selection browser journeys."""

import json
import re

import pytest
from playwright.sync_api import expect
from render_support import (
    DRAFT_MARK,
    PART_DIAGRAM_PAGE,
    ROOT,
    TARGETS_PAGE,
    leaf_page,
    open_page,
    pending_text,
    resized,
)

pytestmark = pytest.mark.nightly


def test_s_aims_at_the_item_named_by_its_hint(browser, serve):
    """The keyboard target is the same stable item Alt-click would take. Choosing the
    paragraph focuses its in-place Comment field without making a native selection."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    page.keyboard.press("s")

    hints = page.locator(".lf-target-hint")
    expect(hints).to_have_count(3)  # heading, paragraph, and figure
    expect(page.locator(".lf-keyline")).to_contain_text("choose hint")
    page.keyboard.press("Tab")
    expect(page.locator(".lf-target-hint.lf-current")).to_have_count(1)
    expect(page.locator(".lf-live")).to_contain_text("Hint a: heading: Targets")
    page.keyboard.press("?")
    expect(page.locator(".lf-keyline")).to_have_attribute("data-lf-expanded", "true")
    expect(page.locator(".lf-help")).to_be_hidden()
    expect(page.locator(".lf-live")).to_contain_text(
        "More keyboard shortcuts shown. Press question mark again for all shortcuts"
    )
    page.keyboard.press("?")
    expect(
        page.locator(".lf-help").get_by_role(
            "heading", name="Selecting an item", exact=True
        )
    ).to_be_visible()
    page.keyboard.press("Escape")
    expect(hints).to_have_count(3)  # help was a layer over the chooser, not its end
    expect(page.locator(".lf-keyline")).to_have_attribute("data-lf-expanded", "true")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-keyline")).to_have_attribute("data-lf-expanded", "false")
    expect(hints).to_have_count(3)
    prose_code = page.evaluate(
        """() => {
          const top = document.querySelector('#prose').getBoundingClientRect().top;
          return [...document.querySelectorAll('.lf-target-hint')]
            .sort((a, b) => Math.abs(a.getBoundingClientRect().top - top)
                          - Math.abs(b.getBoundingClientRect().top - top))[0]
            .dataset.lfTarget;
        }"""
    )
    page.keyboard.type(prose_code)

    assert page.evaluate("() => getSelection().toString()") == ""
    expect(page.locator(".lf-live")).to_contain_text(
        "Selected paragraph: A paragraph with enough words"
    )
    expect(hints).to_have_count(0)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    shown = page.locator(".lf-keyline .lf-key:not([hidden])")
    expect(shown).to_have_count(2)
    expect(shown.nth(0).locator("kbd")).to_have_text("⏎")
    expect(shown.nth(0)).to_contain_text("comment")
    expect(shown.nth(1).locator("kbd")).to_have_text("⇥")
    expect(shown.nth(1)).to_contain_text("other responses")

    # Text entry owns letters. Tab replaces the field with the same-position Comment
    # action; Escape from that response row restores the same draft.
    page.keyboard.press("s")
    expect(field).to_have_value("s")
    field.fill("")
    page.keyboard.press("Tab")
    expect(page.locator(".lf-fab-bar")).to_have_class(re.compile(r"\blf-react-open\b"))
    expect(page.locator(".lf-fab-bar > .lf-fab")).to_be_focused()
    expect(field).to_be_hidden()
    page.keyboard.press("Escape")
    expect(field).to_be_focused()
    assert page.evaluate(DRAFT_MARK) == "prose"
    assert pending_text(page) == ""
    page.keyboard.press("Escape")
    expect(field).to_be_hidden()
    assert errors == []
    page.close()


def test_a_keyboard_comment_gesture_carries_the_current_unsent_draft(browser, serve):
    """Keyboard and pointer Comment gestures make the same explicit re-anchoring."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    field = page.locator(".lf-fab-input")
    draft = "Carry these deliberate words."

    page.locator("h1").click(modifiers=["Alt"])
    expect(field).to_be_focused()
    field.fill(draft)
    page.evaluate("document.activeElement.blur()")

    page.keyboard.press("s")
    hints = page.locator(".lf-target-hint")
    expect(hints).to_have_count(3)
    prose_code = page.evaluate(
        """() => {
          const top = document.querySelector('#prose').getBoundingClientRect().top;
          return [...document.querySelectorAll('.lf-target-hint')]
            .sort((a, b) => Math.abs(a.getBoundingClientRect().top - top)
                          - Math.abs(b.getBoundingClientRect().top - top))[0]
            .dataset.lfTarget;
        }"""
    )
    page.keyboard.type(prose_code)

    expect(field).to_be_focused()
    expect(field).to_have_value(draft)
    assert page.evaluate(DRAFT_MARK) == "prose"
    assert errors == []
    page.close()


def test_a_selected_target_keeps_escape_when_the_layer_has_no_reactions(browser, serve):
    """Without reactions, the focused composer offers no dead Tab route."""
    registry = json.loads(
        (ROOT / "skills/leaf/packages/default/registry.json").read_text()
    )
    tokens = {name: None for name in registry["$reactions"]["tokens"]}
    page, errors = open_page(
        browser,
        serve(TARGETS_PAGE, layer_registry={"$reactions": {"tokens": tokens}}),
    )
    page.keyboard.press("s")
    code = page.locator(".lf-target-hint").first.get_attribute("data-lf-target")
    page.keyboard.type(code)

    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    expect(bar).to_have_attribute("aria-label", re.compile(r"^Respond to "))
    expect(page.locator(".lf-fab-input")).to_be_focused()
    shown = page.locator(".lf-keyline .lf-key:not([hidden])")
    expect(shown).to_have_count(2)
    expect(page.locator(".lf-fab-input")).to_have_attribute(
        "aria-keyshortcuts", "Enter"
    )

    page.keyboard.press("Escape")
    expect(page.locator(".lf-fab-input")).to_be_hidden()
    assert errors == []
    page.close()


def test_a_passage_still_offers_suggest_when_the_layer_has_no_reactions(browser, serve):
    """Tab means other responses rather than reactions specifically: removing the
    reaction vocabulary must not strand Suggest for a selected passage."""
    registry = json.loads(
        (ROOT / "skills/leaf/packages/default/registry.json").read_text()
    )
    tokens = {name: None for name in registry["$reactions"]["tokens"]}
    page, errors = open_page(
        browser,
        serve(TARGETS_PAGE, layer_registry={"$reactions": {"tokens": tokens}}),
    )

    prose = page.locator("#prose")
    prose.select_text()
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    expect(page.locator(".lf-fab-bar .lf-react")).to_have_count(0)
    page.keyboard.press("Tab")

    responses = page.locator(".lf-fab-bar")
    expect(responses).to_have_class(re.compile(r"\blf-react-open\b"))
    expect(responses.locator(":scope > .lf-fab")).to_be_focused()
    page.keyboard.press("ArrowRight")
    expect(responses.locator(".lf-fab-suggest")).to_be_focused()
    expect(responses.locator(".lf-react")).to_have_count(0)
    assert errors == []
    page.close()


def test_dense_selection_hints_stay_short_and_reach_an_atomic_visual(browser, serve):
    """The hint alphabet is a prefix-free tree, so adding a twenty-seventh target does
    not turn every target into a two-key address. Many remain one key and only the tail
    branches. A two-key tail hint raises the same ordinary item anchor as Alt-click."""
    figures = "".join(
        f'<figure id="visual-{i}"><svg viewBox="0 0 32 18" width="32" height="18" '
        f'role="img" aria-label="Visual {i}"><rect x="1" y="1" width="30" '
        'height="16" fill="none" stroke="currentColor"></rect></svg></figure>'
        for i in range(60)
    )
    html = leaf_page(
        "dense visual targets",
        f'<h1 id="title">Visual targets</h1><div class="visual-grid">{figures}</div>',
        head="""
<style>
.visual-grid { display: grid; grid-template-columns: repeat(10, 44px); gap: 12px; }
.visual-grid figure { margin: 0; width: 32px; height: 18px; }
</style>
""",
    )
    page, errors = open_page(browser, serve(html))
    page.keyboard.press("s")

    hints = page.locator(".lf-target-hint")
    expect(hints).to_have_count(61)  # heading plus sixty atomic figures
    codes = hints.evaluate_all("nodes => nodes.map(node => node.dataset.lfTarget)")
    assert any(len(code) == 1 for code in codes)
    assert max(map(len, codes)) == 2
    page.keyboard.press("Tab")
    page.keyboard.press("Tab")
    expect(page.locator(".lf-live")).to_contain_text("figure: Visual 0")

    last = codes[-1]
    page.keyboard.press(last[0])
    expect(hints).to_have_count(sum(code.startswith(last[0]) for code in codes))
    page.keyboard.press(last[1])
    expect(hints).to_have_count(0)
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-keyline")).to_contain_text("comment")
    geometry = page.evaluate(
        """() => {
          const figure = document.querySelector('#visual-59').getBoundingClientRect();
          const bar = document.querySelector('.lf-fab-bar').getBoundingClientRect();
          return { figureTop: figure.top, barTop: bar.top };
        }"""
    )
    assert abs(geometry["barTop"] - geometry["figureTop"]) < 100, geometry

    page.keyboard.press("Escape")
    expect(page.locator(".lf-fab-input")).to_be_hidden()

    page.keyboard.press("s")
    page.keyboard.type(last)
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer .lf-suggest-row")).to_be_hidden()
    assert errors == []
    page.close()


def test_nested_item_hints_show_containment_without_covering_each_other(browser, serve):
    """A container and its first child may paint the same box corner. Both remain
    reachable, while the enclosed target steps right to show which hint names it."""
    html = leaf_page(
        "nested targets",
        '<section id="outer"><p id="inner">The child fills its parent.</p></section>',
        head="<style>section { padding-bottom: 5rem; } section, p { margin: 0; }</style>",
    )
    page, errors = open_page(browser, serve(html))
    page.keyboard.press("s")

    hints = page.locator(".lf-target-hint")
    expect(hints).to_have_count(2)
    geometry = page.evaluate(
        """() => ({
          targetLefts: ['outer', 'inner'].map(id =>
            document.getElementById(id).getBoundingClientRect().left),
          hints: [...document.querySelectorAll('.lf-target-hint')].map(node => {
          const { left, top, right, bottom } = node.getBoundingClientRect();
            return { left, top, right, bottom, centre: (left + right) / 2 };
          }),
        })"""
    )
    boxes = geometry["hints"]
    assert abs(geometry["targetLefts"][0] - geometry["targetLefts"][1]) < 0.5
    assert boxes[1]["centre"] - boxes[0]["centre"] >= 9, geometry
    assert not (
        boxes[0]["left"] < boxes[1]["right"]
        and boxes[1]["left"] < boxes[0]["right"]
        and boxes[0]["top"] < boxes[1]["bottom"]
        and boxes[1]["top"] < boxes[0]["bottom"]
    ), geometry
    assert errors == []
    page.close()


def test_identical_nested_item_hints_choose_the_innermost_target(browser, serve):
    """A transparent wrapper and its only child can describe one visible box. The
    chooser names that box once and agrees with direct aiming by selecting the child."""
    html = leaf_page(
        "identical nested targets",
        '<section id="outer"><div id="inner">One visible box.</div></section>',
        head="<style>section, div { margin: 0; }</style>",
    )
    page, errors = open_page(browser, serve(html))
    geometry = page.evaluate(
        """() => ['outer', 'inner'].map(id => {
          const { left, top, right, bottom } =
            document.getElementById(id).getBoundingClientRect();
          return { left, top, right, bottom };
        })"""
    )
    assert all(
        abs(geometry[0][edge] - geometry[1][edge]) < 0.5
        for edge in ("left", "top", "right", "bottom")
    ), geometry

    page.keyboard.press("s")
    hints = page.locator(".lf-target-hint")
    expect(hints).to_have_count(1)
    page.keyboard.type(hints.get_attribute("data-lf-target"))
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(DRAFT_MARK) == "inner"
    assert errors == []
    page.close()


def test_selection_hints_name_only_items_shown_by_a_disclosure(browser, serve):
    """A shut disclosure keeps its own hint but not hints for its contents. The same
    rule applies after a prefix narrows the open disclosure's map."""
    inside = "".join(f'<span id="inside-{i}">{i}</span>' for i in range(30))
    html = leaf_page(
        "disclosed targets",
        f"""
<h1 id="title">Visible targets</h1>
<details id="evidence">
  <summary>Supporting evidence</summary>
  <div class="target-grid">{inside}</div>
</details>
""",
        head="""
<style>
.target-grid { display: grid; grid-template-columns: repeat(10, 2rem); gap: 4px; }
.target-grid span { display: block; }
</style>
""",
    )
    page, errors = open_page(browser, serve(html))

    page.keyboard.press("s")
    hints = page.locator(".lf-target-hint")
    expect(hints).to_have_count(2)  # heading and disclosure

    page.keyboard.press("Escape")
    page.locator("summary").click()
    page.keyboard.press("s")
    expect(hints).to_have_count(32)

    codes = hints.evaluate_all("nodes => nodes.map(node => node.dataset.lfTarget)")
    tail = next(code for code in codes if len(code) > 1)
    page.keyboard.press(tail[0])
    expect(hints).to_have_count(sum(code.startswith(tail[0]) for code in codes))
    page.locator("summary").click()
    expect(hints).to_have_count(0)

    assert errors == []
    page.close()


def test_s_raises_the_same_action_bar_on_a_declared_visual_part(browser, serve):
    """A declared picture part outranks its enclosing item without changing what aim
    means. Choosing its hint focuses the part-anchored composer."""
    page, errors = open_page(browser, serve(PART_DIAGRAM_PAGE))
    page.keyboard.press("s")
    expect(page.locator(".lf-target-hint")).to_have_count(4)

    start_code = page.evaluate(
        """() => {
          const part = document.querySelector('#flow g[id*="flowchart-S-"]')
            .getBoundingClientRect();
          return [...document.querySelectorAll('.lf-target-hint')]
            .sort((a, b) => {
              const ar = a.getBoundingClientRect(), br = b.getBoundingClientRect();
              return Math.hypot(ar.left - part.left, ar.top - part.top)
                   - Math.hypot(br.left - part.left, br.top - part.top);
            })[0].dataset.lfTarget;
        }"""
    )
    page.keyboard.type(start_code)

    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    start = page.locator('#flow g[id*="flowchart-S-"]')
    expect(start).not_to_have_class(re.compile(r"\blf-action-target\b"))
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_have_text("§ diagram · Start request")
    expect(start).to_have_class(re.compile(r"\blf-mark-el\b.*\blf-pending\b"))
    expect(page.locator("#flow")).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    assert page.evaluate("() => getSelection().toString()") == ""
    assert errors == []
    page.close()


def test_selection_hints_do_not_name_page_content_behind_a_covering_panel(
    browser, serve
):
    """A fixed panel covers rather than clips the page. Hint geometry read from the page
    alone therefore still exists behind it, but a key drawn above the chrome there would
    appear to name a panel control and choose hidden document content. The rendered stack
    at each target's corner decides whether it is actually exposed."""
    page, errors = open_page(browser, serve(ROOT / "examples" / "corpus.html"))
    resized(page, 700, 900)
    page.get_by_role("button", name=re.compile(r"^Threads")).click()
    expect(page.locator(".lf-panel")).to_be_visible()
    page.keyboard.press("s")
    expect(page.locator(".lf-target-hint")).not_to_have_count(0)

    geometry = page.evaluate(
        """() => {
          const panel = document.querySelector('.lf-panel').getBoundingClientRect();
          return {
            panelLeft: panel.left,
            centres: [...document.querySelectorAll('.lf-target-hint')].map((hint) => {
              const box = hint.getBoundingClientRect();
              return box.left + box.width / 2;
            }),
          };
        }"""
    )
    assert geometry["centres"]
    assert max(geometry["centres"]) < geometry["panelLeft"], (
        f"a selection hint is painted on the covering thread panel: {geometry}"
    )
    assert errors == []
    page.close()


def test_slash_finds_page_text_without_a_target_kind(browser, serve):
    """Slash is ordinary whole-page find. It narrows by the words the reader knows,
    highlights one exact occurrence, and Enter hands that range to the same comment
    surface as a hint. No selection mode or paragraph/sentence/widget key is needed
    first."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))

    line = page.locator(".lf-keyline")
    expect(line).to_contain_text("search page")
    expect(line).to_contain_text("select item")
    page.keyboard.press("?")
    page.keyboard.press("?")
    help_el = page.locator(".lf-help")
    search_command = help_el.locator('tr[data-lf-command="page.search.open"]')
    select_command = help_el.locator('tr[data-lf-command="selection.open"]')
    expect(search_command.locator("kbd")).to_have_text("/")
    expect(search_command.get_by_role("button")).to_have_text(
        "Search all the text on the page"
    )
    expect(select_command.locator("kbd")).to_have_text("s")
    expect(select_command.get_by_role("button")).to_have_text(
        "Select a visible item by hint"
    )
    page.keyboard.press("Escape")
    page.keyboard.press("/")

    search = page.get_by_role("searchbox", name="Search page text")
    expect(search).to_be_focused()
    status = page.locator(".lf-target-search-status")
    expect(status).to_be_empty()
    page.keyboard.type("b")
    expect(status).to_have_text(re.compile(r"\d+ of \d+"))
    expect(page.locator(".lf-target-match")).not_to_have_count(0)
    search.fill("button the key")
    expect(status).to_have_text("1 of 1")
    expect(page.locator(".lf-target-match")).not_to_have_count(0)
    expect(page.locator(".lf-keyline")).to_contain_text("select match")
    page.keyboard.press("Tab")
    expect(page.locator(".lf-live")).to_contain_text(
        "raises the button the key then presses"
    )

    page.keyboard.press("Enter")
    expect(page.locator(".lf-target-search")).to_be_hidden()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert pending_text(page) == "button the key"
    assert errors == []
    page.close()


def test_page_search_starts_with_the_first_match_at_the_reading_edge(browser, serve):
    """Search begins at the top of the visible reading rather than whichever match is
    nearest the viewport midpoint, so an opening title is the result that gets paint."""
    html = leaf_page(
        "search from reading edge",
        """
<h1 id="title">Unified title</h1>
<div style="height: 260px" aria-hidden="true"></div>
<p>Unified body.</p>
""",
    )
    page, errors = open_page(browser, serve(html))
    page.keyboard.press("/")
    page.keyboard.type("Unified")

    expect(page.locator(".lf-target-search-status")).to_have_text("1 of 2")
    title = page.locator("#title").bounding_box()
    match = page.locator(".lf-target-match").first.bounding_box()
    assert title is not None and match is not None
    assert title["x"] <= match["x"] < title["x"] + title["width"]
    assert title["y"] <= match["y"] < title["y"] + title["height"]
    assert errors == []
    page.close()


def test_slash_stays_native_in_text_entry_and_searches_the_scope_in_front(
    browser, serve
):
    """An editable field owns slash as text. From the thread list, the same key opens
    that panel's find box rather than the page search standing behind it."""
    html = leaf_page(
        "scoped slash",
        '<label>Path <input id="path"></label><p>Searchable page words.</p>',
    )
    page, errors = open_page(browser, serve(html, comments=2))
    path = page.locator("#path")
    path.focus()
    page.keyboard.type("/")
    expect(path).to_have_value("/")
    expect(page.locator(".lf-target-search")).to_be_hidden()

    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")
    page.keyboard.press("c")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("/")
    thread_search = page.get_by_role("searchbox", name="Find in threads")
    expect(thread_search).to_be_focused()
    expect(page.locator(".lf-target-search")).to_be_hidden()
    page.keyboard.type("Comment 1")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(1)
    assert errors == []
    page.close()


def test_empty_thread_scope_keeps_slash_in_its_search(browser, serve):
    """An empty thread list still has a usable find box. Slash focuses that nearest
    search rather than opening page search behind the panel."""
    html = leaf_page("empty scoped slash", "<p>Searchable page words.</p>")
    page, errors = open_page(browser, serve(html))

    page.keyboard.press("c")
    threads = page.locator(".lf-threads")
    expect(threads).to_be_focused()
    expect(page.locator(".lf-keyline")).not_to_contain_text("search page")
    page.keyboard.press("/")
    expect(page.get_by_role("searchbox", name="Find in threads")).to_be_focused()
    expect(page.locator(".lf-target-search")).to_be_hidden()
    assert errors == []
    page.close()


def test_selection_search_announces_context_across_inline_node_boundaries(
    browser, serve
):
    """Repeated matches that fill separate inline nodes remain distinguishable to a
    nonvisual reader by context drawn from the shared page reading on both sides."""
    html = leaf_page(
        "search context",
        """
<p>Before alpha <em>repeat</em> after alpha.</p>
<p>Before beta <strong>repeat</strong> after beta.</p>
""",
    )
    page, errors = open_page(browser, serve(html))
    page.keyboard.press("s")
    page.keyboard.press("/")
    page.keyboard.type("repeat")
    expect(page.locator(".lf-target-search-status")).to_contain_text("of 2")

    page.keyboard.press("Tab")
    live = page.locator(".lf-live")
    expect(live).to_contain_text("repeat")
    first = live.inner_text()
    page.keyboard.press("Tab")
    page.wait_for_function(
        "first => { const text = document.querySelector('.lf-live').textContent;"
        "           return text && text !== first; }",
        arg=first,
    )
    second = live.inner_text()
    assert "repeat" in first and "repeat" in second
    assert {"alpha", "beta"} <= set(first.split() + second.split())
    assert errors == []
    page.close()


def test_selection_search_brings_an_offscreen_match_into_view(browser, serve):
    """A search result is a target, not only a count. When the query exists solely below
    the fold, the first complete search moves that occurrence into view and paints it;
    otherwise Enter would silently select words the reader still could not see."""
    html = leaf_page(
        "offscreen search",
        """
<h1 id="title">Search the whole page</h1>
<div style="height: 1400px" aria-hidden="true"></div>
<p id="far">The distant phrase is the one this search should reveal.</p>
""",
    )
    page, errors = open_page(browser, serve(html))
    page.keyboard.press("s")
    page.keyboard.press("/")
    page.keyboard.type("distant phrase")

    page.wait_for_function(
        """() => {
          const box = document.querySelector('#far').getBoundingClientRect();
          return box.bottom > 42 && box.top < innerHeight;
        }"""
    )
    expect(page.locator(".lf-target-search-status")).to_have_text("1 of 1")
    expect(page.locator(".lf-target-match")).not_to_have_count(0)
    expect(page.get_by_role("searchbox", name="Search page text")).to_be_focused()

    page.keyboard.press("Enter")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    assert pending_text(page) == "distant phrase"
    assert errors == []
    page.close()


def test_selection_search_scrolls_to_the_match_inside_a_tall_text_block(browser, serve):
    """Whole-page find travels to the exact range, not merely to the block containing
    it. A match near the foot of a multi-screen pre is visible before Enter selects it."""
    lines = "\n".join(["an ordinary line"] * 90 + ["the solitary copper needle"])
    page, errors = open_page(
        browser,
        serve(leaf_page("range search", f'<pre id="long">{lines}</pre>')),
    )
    page.keyboard.press("s")
    page.keyboard.press("/")
    page.keyboard.type("copper needle")

    expect(page.locator(".lf-target-search-status")).to_have_text("1 of 1")
    match = page.locator(".lf-target-match").first
    expect(match).to_be_visible()
    mark = page.evaluate(
        """() => {
          const node = document.querySelector('.lf-target-match');
          if (!node) return null;
          const { x, y, width, height } = node.getBoundingClientRect();
          return { x, y, width, height };
        }"""
    )
    assert mark is not None
    keyline_top = page.locator(".lf-keyline").bounding_box()["y"]
    assert mark["y"] > 42 and mark["y"] + mark["height"] < keyline_top

    page.keyboard.press("Enter")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    assert pending_text(page) == "copper needle"
    assert errors == []
    page.close()


def test_hint_browsing_forgets_a_target_that_scrolls_out_of_the_map(browser, serve):
    """Tab announces one visible target. If scrolling changes the viewport map before
    Enter, that stale index cannot silently become a different target."""
    html = leaf_page(
        "changing hint map",
        """
<h1 id="first">The initially announced heading</h1>
<div style="height: 1200px" aria-hidden="true"></div>
<p id="later">A later visible target.</p>
<div style="height: 600px" aria-hidden="true"></div>
""",
    )
    page, errors = open_page(browser, serve(html))
    page.keyboard.press("s")
    page.keyboard.press("Tab")
    expect(page.locator(".lf-live")).to_contain_text("initially announced heading")
    expect(page.locator(".lf-target-hint.lf-current")).to_have_count(1)

    page.evaluate("() => { document.scrollingElement.scrollTop = 1050; }")
    expect(page.locator(".lf-target-hint.lf-current")).to_have_count(0)
    expect(page.locator(".lf-keyline")).not_to_contain_text("select target")
    page.keyboard.press("Enter")
    assert page.evaluate("() => getSelection().toString()") == ""
    assert errors == []
    page.close()


def test_scrolling_item_hints_does_not_measure_hidden_targets(browser, serve):
    """A smooth scroll repositions the small visible map and refreshes its membership
    once at rest; targets inside a closed disclosure never incur geometry reads."""
    hidden_count = 1000
    hidden = "".join(f'<span id="hidden-{i}">{i}</span>' for i in range(hidden_count))
    html = leaf_page(
        "hidden hint targets",
        f"""
<h1 id="title">Visible targets</h1>
<div id="contents" style="display: contents"><p>A boxless visible target.</p></div>
<details id="evidence">
  <summary>Hidden targets</summary>
  {hidden}
</details>
<div style="height: 1200px" aria-hidden="true"></div>
""",
    )
    page, errors = open_page(browser, serve(html))
    page.keyboard.press("s")
    expect(page.locator(".lf-target-hint")).to_have_count(3)

    page.evaluate(
        """() => {
          const originalRect = Element.prototype.getBoundingClientRect;
          const originalVisibility = Element.prototype.checkVisibility;
          let rectReads = 0;
          let visibilityReads = 0;
          Element.prototype.getBoundingClientRect = function (...args) {
            rectReads += 1;
            return originalRect.apply(this, args);
          };
          Element.prototype.checkVisibility = function (...args) {
            visibilityReads += 1;
            return originalVisibility.apply(this, args);
          };
          addEventListener('scrollend', () => requestAnimationFrame(() => {
            window.lfHintScrollReads = {rectReads, visibilityReads};
            Element.prototype.getBoundingClientRect = originalRect;
            Element.prototype.checkVisibility = originalVisibility;
          }), {capture: true, once: true});
          document.scrollingElement.scrollTo({top: 600, behavior: 'smooth'});
        }"""
    )
    page.wait_for_function("() => window.lfHintScrollReads")
    reads = page.evaluate("() => window.lfHintScrollReads")

    assert reads["rectReads"] < hidden_count, reads
    assert reads["visibilityReads"] < hidden_count * 3, reads
    assert errors == []
    page.close()


def test_cancelling_page_search_restores_the_control_that_opened_it(browser, serve):
    """Direct search is one layer. A repeated slash cannot change that when focus has
    left its box: Escape still closes search and returns to the original control."""
    html = leaf_page(
        "selection focus",
        '<button id="opener">Starting control</button><p>A passage to select.</p>',
    )
    page, errors = open_page(browser, serve(html))
    opener = page.locator("#opener")
    opener.focus()

    page.keyboard.press("/")
    expect(page.get_by_role("searchbox", name="Search page text")).to_be_focused()
    page.locator("p").click()
    page.keyboard.press("/")
    expect(page.locator(".lf-keyline")).to_contain_text("close search")
    expect(page.locator(".lf-keyline")).not_to_contain_text("back to hints")
    page.keyboard.press("Escape")
    expect(opener).to_be_focused()
    assert errors == []
    page.close()


def test_cancelling_selection_restores_an_opener_inside_shadow_dom(browser, serve):
    """The exact focused control opens the mode, even across a shadow boundary. Closing
    both selection layers returns to that control rather than only to its host."""
    html = leaf_page(
        "shadow selection focus",
        '<div id="opener"></div><p>A passage to select.</p>',
    )
    page, errors = open_page(browser, serve(html))
    page.evaluate(
        """() => {
          const root = document.querySelector('#opener').attachShadow({ mode: 'open' });
          root.innerHTML = '<button id="inside">Starting control</button>';
          root.querySelector('#inside').focus();
        }"""
    )

    page.keyboard.press("s")
    page.keyboard.press("/")
    expect(page.get_by_role("searchbox", name="Search page text")).to_be_focused()
    expect(page.locator(".lf-keyline")).to_contain_text("back to hints")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    assert (
        page.evaluate(
            "() => document.querySelector('#opener').shadowRoot.activeElement?.id"
        )
        == "inside"
    )
    assert errors == []
    page.close()


def test_selection_search_opens_when_the_viewport_has_no_hint_targets(browser, serve):
    """The hint face is viewport-local, but slash is whole-page find. Reaching blank
    space must not close the shared mode and strand searchable text somewhere else."""
    html = leaf_page(
        "search from empty viewport",
        """
<h1 id="title">A searchable beginning</h1>
<p>The phrase only appears above the blank viewport.</p>
<div style="height: 1800px" aria-hidden="true"></div>
""",
    )
    page, errors = open_page(browser, serve(html))
    page.evaluate(
        "() => { document.scrollingElement.scrollTop = document.scrollingElement.scrollHeight; }"
    )
    page.wait_for_function("() => document.scrollingElement.scrollTop > 500")

    page.keyboard.press("s")
    expect(page.locator(".lf-target-hint")).to_have_count(0)
    expect(page.locator(".lf-keyline")).to_contain_text("search page")
    expect(page.locator(".lf-keyline")).not_to_contain_text("choose hint")
    page.keyboard.press("/")
    page.keyboard.type("phrase only appears")
    expect(page.locator(".lf-target-search-status")).to_have_text("1 of 1")
    expect(page.locator(".lf-target-match")).not_to_have_count(0)

    page.keyboard.press("Enter")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    assert pending_text(page) == "phrase only appears"
    assert errors == []
    page.close()


def test_a_partly_banner_clipped_passage_keeps_its_hint_below_the_banner(
    browser, serve
):
    """A line beginning behind the fixed banner can still be visibly selectable below
    it. Its hint sits at the clipped edge instead of putting half its key under chrome."""
    html = leaf_page(
        "top-edge target",
        """
<div style="height: 300px" aria-hidden="true"></div>
<p id="edge">This passage begins beneath the banner edge.</p>
<div style="height: 1200px" aria-hidden="true"></div>
""",
    )
    page, errors = open_page(browser, serve(html))
    page.evaluate(
        """() => {
          const text = document.querySelector('#edge').firstChild;
          const range = document.createRange();
          range.selectNodeContents(text);
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          document.scrollingElement.scrollTop += range.getBoundingClientRect().top - (banner.bottom - 5);
        }"""
    )
    page.keyboard.press("s")
    expect(page.locator(".lf-target-hint")).to_have_count(1)

    geometry = page.evaluate(
        """() => ({
          bannerBottom: document.querySelector('.lf-banner').getBoundingClientRect().bottom,
          hintTop: document.querySelector('.lf-target-hint').getBoundingClientRect().top,
        })"""
    )
    assert geometry["hintTop"] >= geometry["bannerBottom"], geometry

    page.keyboard.press("Escape")
    page.evaluate(
        """() => {
          const text = document.querySelector('#edge').firstChild;
          const range = document.createRange();
          range.selectNodeContents(text);
          const keyline = document.querySelector('.lf-keyline').getBoundingClientRect();
          document.scrollingElement.scrollTop += range.getBoundingClientRect().top - (keyline.top - 5);
        }"""
    )
    page.keyboard.press("s")
    expect(page.locator(".lf-target-hint")).to_have_count(1)
    geometry = page.evaluate(
        """() => ({
          keylineTop: document.querySelector('.lf-keyline').getBoundingClientRect().top,
          hintBottom: document.querySelector('.lf-target-hint').getBoundingClientRect().bottom,
        })"""
    )
    assert geometry["hintBottom"] <= geometry["keylineTop"], geometry
    assert errors == []
    page.close()


def test_a_partly_banner_clipped_atomic_item_keeps_its_hint_below_the_banner(
    browser, serve
):
    """Atomic visuals use item geometry rather than text ranges, but obey the same
    upper chrome boundary when only their lower edge is exposed."""
    html = leaf_page(
        "top-edge visual",
        """
<div style="height: 300px" aria-hidden="true"></div>
<figure id="edge-visual"><svg viewBox="0 0 120 60" width="120" height="60"
  role="img" aria-label="Edge visual"><rect width="120" height="60"></rect></svg></figure>
<div style="height: 1200px" aria-hidden="true"></div>
""",
    )
    page, errors = open_page(browser, serve(html))
    page.evaluate(
        """() => {
          const visual = document.querySelector('#edge-visual').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          document.scrollingElement.scrollTop += visual.top - (banner.bottom - 8);
        }"""
    )
    page.keyboard.press("s")
    expect(page.locator(".lf-target-hint")).to_have_count(1)

    geometry = page.evaluate(
        """() => ({
          bannerBottom: document.querySelector('.lf-banner').getBoundingClientRect().bottom,
          hintTop: document.querySelector('.lf-target-hint').getBoundingClientRect().top,
        })"""
    )
    assert geometry["hintTop"] >= geometry["bannerBottom"], geometry
    assert errors == []
    page.close()
