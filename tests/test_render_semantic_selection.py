"""Keyboard semantic-selection browser journeys."""

import json
import re

import pytest
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_support import (
    DRAFT_MARK,
    PART_DIAGRAM_PAGE,
    RENDERED,
    ROOT,
    TARGETS_PAGE,
    leaf_page,
    open_page,
    pending_text,
    resized,
    sending,
)

pytestmark = pytest.mark.nightly


def test_short_inline_code_selection_offers_comment(browser, serve):
    """A complete code term is commentable even when it is one or two characters."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "short code selection",
                '<p id="code">Compare <code>x</code> with <code>id</code>.</p>',
            )
        ),
    )

    for term in ("x", "id"):
        page.get_by_text(term, exact=True).select_text()
        bar = page.locator(".lf-fab-bar")
        expect(bar).to_be_visible()
        expect(bar).to_have_attribute("aria-label", f"Respond to “{term}”")
        expect(page.locator(".lf-fab-input")).not_to_be_focused()

    page.keyboard.press("c")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    field.fill("Name this variable more clearly.")
    with sending(page, "the short-code comment"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["anchor"] == {
        "section": "code",
        "quote": "id",
        "prefix": "Compare x with",
        "suffix": ".",
    }

    assert errors == []
    page.close()


def test_s_aims_at_the_addressable_element_named_by_its_hint(browser, serve):
    """The keyboard target is the same addressable element Alt-click would take. Choosing the
    paragraph focuses its in-place Comment field without making a native selection."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    page.keyboard.press("s")

    hints = page.locator(".lf-target-chooser-hint")
    expect(hints).to_have_count(3)  # heading, paragraph, and figure
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("type hint")
    page.keyboard.press("Tab")
    expect(page.locator(".lf-walk-position")).to_have_text("Target 1 of 3")
    expect(page.locator(".lf-target-chooser-hint.lf-current")).to_have_count(1)
    expect(page.locator(".lf-live")).to_contain_text("Hint a: heading: Targets")
    page.keyboard.press("?")
    expect(page.locator(".lf-shortcut-bar")).to_have_attribute(
        "data-lf-shelf-open", "true"
    )
    expect(page.locator(".lf-command-reference")).to_be_hidden()
    expect(page.locator(".lf-live")).to_contain_text(
        "Shortcut shelf expanded. Press question mark again for Command reference"
    )
    page.keyboard.press("?")
    expect(
        page.locator(".lf-command-reference").get_by_role(
            "heading", name="In the target chooser", exact=True
        )
    ).to_be_visible()
    page.keyboard.press("Escape")
    expect(hints).to_have_count(3)  # help was a layer over the chooser, not its end
    expect(page.locator(".lf-shortcut-bar")).to_have_attribute(
        "data-lf-shelf-open", "true"
    )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-shortcut-bar")).to_have_attribute(
        "data-lf-shelf-open", "false"
    )
    expect(hints).to_have_count(3)
    prose_code = page.evaluate(
        """() => {
          const top = document.querySelector('#prose').getBoundingClientRect().top;
          return [...document.querySelectorAll('.lf-target-chooser-hint')]
            .sort((a, b) => Math.abs(a.getBoundingClientRect().top - top)
                          - Math.abs(b.getBoundingClientRect().top - top))[0]
            .dataset.lfHintCode;
        }"""
    )
    page.keyboard.type(prose_code)

    assert page.evaluate("() => getSelection().toString()") == ""
    expect(page.locator(".lf-live")).to_contain_text(
        "Chosen paragraph: A paragraph with enough words"
    )
    expect(hints).to_have_count(0)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    shown = page.locator(".lf-shortcut-bar .lf-shortcut:not([hidden])")
    expect(shown).to_have_count(2)
    expect(shown.nth(0).locator("kbd")).to_have_text(re.compile(r"^(⌘⏎|Ctrl\+⏎)$"))
    expect(shown.nth(0)).to_contain_text("comment")
    expect(shown.nth(1).locator("kbd")).to_have_text("⇥")
    expect(shown.nth(1)).to_contain_text("other responses")

    # Text entry owns letters. Tab extends the same response surface; Escape restores
    # the same draft.
    bar = page.locator(".lf-fab-bar")
    page.keyboard.press("s")
    expect(field).to_have_value("s")
    field.fill("Keep this draft")
    page.keyboard.press("Tab")
    expect(bar.locator('[data-token="keep"]')).to_be_focused()
    expect(field).to_be_visible()
    page.keyboard.press("Escape")
    expect(field).to_be_focused()
    expect(field).to_have_value("Keep this draft")
    assert page.evaluate(DRAFT_MARK) == "prose"
    assert pending_text(page) == ""
    page.keyboard.press("Escape")
    expect(field).to_be_hidden()
    assert errors == []
    page.close()


def test_a_chrome_reflow_repositions_target_hints_in_its_first_layout_frame(
    browser, serve
):
    """A line resize and its dependent target placement land in one visible frame."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    page.keyboard.press("s")
    hints = page.locator(".lf-target-chooser-hint")
    expect(hints).to_have_count(3)
    page.evaluate(RENDERED)

    page.evaluate(
        """() => {
          const line = document.querySelector('.lf-shortcut-bar');
          const oldHints = [...document.querySelectorAll('.lf-target-chooser-hint')]
            .map(node => node.getBoundingClientRect().toJSON());
          window.__lfFirstChromeResize = null;
          const overlap = (one, other) =>
            one.left < other.right && other.left < one.right &&
            one.top < other.bottom && other.top < one.bottom;
          const observer = new ResizeObserver(() => {
            observer.disconnect();
            requestAnimationFrame(() => {
              const lineBox = line.getBoundingClientRect().toJSON();
              const currentHints = [...document.querySelectorAll('.lf-target-chooser-hint')]
                .map(node => node.getBoundingClientRect().toJSON());
              window.__lfFirstChromeResize = {
                crossedOldHints: oldHints.filter(box => overlap(box, lineBox)).length,
                overlaps: currentHints.filter(box => overlap(box, lineBox)).length,
                currentHints: currentHints.length,
              };
            });
          });
          observer.observe(line);
          line.style.height = '700px';
        }"""
    )
    page.wait_for_function("() => window.__lfFirstChromeResize !== null")
    frame = page.evaluate("() => window.__lfFirstChromeResize")

    assert frame["crossedOldHints"] > 0, (
        f"the resized line crossed no prior hint, so it cannot expose stale placement: {frame}"
    )
    assert frame["currentHints"] == 3, (
        f"the target map dropped a reachable command instead of repositioning it: {frame}"
    )
    assert frame["overlaps"] == 0, (
        f"the first layout frame left target hints under the resized line: {frame}"
    )
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
    hints = page.locator(".lf-target-chooser-hint")
    expect(hints).to_have_count(3)
    prose_code = page.evaluate(
        """() => {
          const top = document.querySelector('#prose').getBoundingClientRect().top;
          return [...document.querySelectorAll('.lf-target-chooser-hint')]
            .sort((a, b) => Math.abs(a.getBoundingClientRect().top - top)
                          - Math.abs(b.getBoundingClientRect().top - top))[0]
            .dataset.lfHintCode;
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
    code = (
        page.locator(".lf-target-chooser-hint")
        .nth(1)
        .get_attribute("data-lf-hint-code")
    )
    page.keyboard.type(code)

    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    expect(bar).to_have_attribute("aria-label", re.compile(r"^Respond to "))
    expect(page.locator(".lf-fab-input")).to_be_focused()
    shown = page.locator(".lf-shortcut-bar .lf-shortcut:not([hidden])")
    expect(shown).to_have_count(2)
    expect(shown.nth(1).locator("kbd")).to_have_text("esc")
    expect(bar.get_by_role("button", name="Show other responses")).to_be_hidden()
    expect(page.locator(".lf-fab-input")).to_have_attribute(
        "aria-keyshortcuts", "Meta+Enter Control+Enter"
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
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(field).not_to_be_focused()
    page.keyboard.press("c")
    expect(field).to_be_focused()
    expect(page.locator(".lf-fab-bar .lf-react")).to_have_count(0)
    page.keyboard.press("Tab")

    responses = page.locator(".lf-fab-bar")
    expect(responses).to_have_class(re.compile(r"\blf-response-open\b"))
    expect(responses.locator(".lf-fab-suggest")).to_be_focused()
    expect(responses.locator(".lf-react")).to_have_count(0)
    assert errors == []
    page.close()


def test_dense_selection_hints_stay_short_and_reach_an_atomic_visual(browser, serve):
    """The hint alphabet is a prefix-free tree, so adding a twenty-seventh target does
    not turn every target into a two-key address. Many remain one key and only the tail
    branches. A two-key tail hint raises the same element anchor as Alt-click."""
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

    hints = page.locator(".lf-target-chooser-hint")
    expect(hints).to_have_count(61)  # heading plus sixty atomic figures
    codes = hints.evaluate_all("nodes => nodes.map(node => node.dataset.lfHintCode)")
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
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("comment")
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


def test_nested_target_hints_show_containment_without_covering_each_other(
    browser, serve
):
    """A container and its first child may paint the same box corner. Both remain
    reachable, while the enclosed target steps right to show which hint names it."""
    html = leaf_page(
        "nested targets",
        '<section id="outer"><p id="inner">The child fills its parent.</p></section>',
        head="<style>section { padding-bottom: 5rem; } section, p { margin: 0; }</style>",
    )
    page, errors = open_page(browser, serve(html))
    page.keyboard.press("s")

    hints = page.locator(".lf-target-chooser-hint")
    expect(hints).to_have_count(2)
    geometry = page.evaluate(
        """() => ({
          targetLefts: ['outer', 'inner'].map(id =>
            document.getElementById(id).getBoundingClientRect().left),
          hints: [...document.querySelectorAll('.lf-target-chooser-hint')].map(node => {
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


def test_identical_nested_target_hints_choose_the_innermost_target(browser, serve):
    """A transparent wrapper and its only child can describe one visible box. The
    chooser names that box once and agrees with direct aiming by opening Comment on
    the child."""
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
    hints = page.locator(".lf-target-chooser-hint")
    expect(hints).to_have_count(1)
    page.keyboard.type(hints.get_attribute("data-lf-hint-code"))
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(DRAFT_MARK) == "inner"
    assert errors == []
    page.close()


def test_target_hints_name_only_addressable_elements_shown_by_a_disclosure(
    browser, serve
):
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
    hints = page.locator(".lf-target-chooser-hint")
    expect(hints).to_have_count(2)  # heading and disclosure

    page.keyboard.press("Escape")
    page.locator("summary").click()
    page.keyboard.press("s")
    expect(hints).to_have_count(32)

    codes = hints.evaluate_all("nodes => nodes.map(node => node.dataset.lfHintCode)")
    tail = next(code for code in codes if len(code) > 1)
    page.keyboard.press(tail[0])
    expect(hints).to_have_count(sum(code.startswith(tail[0]) for code in codes))
    continued = page.locator(
        f'.lf-target-chooser-hint[data-lf-hint-code="{tail}"] .lf-binding-sequence'
    )
    assert continued.locator("kbd").evaluate_all(
        "keys => keys.map(key => [key.textContent, key.dataset.lfSequenceStepState])"
    ) == [[tail[0], "pressed"], [tail[1], "neutral"]]
    expect(continued).to_have_css("gap", "1px")
    page.locator("summary").click()
    expect(hints).to_have_count(0)

    assert errors == []
    page.close()


def test_s_opens_the_same_comment_field_on_a_declared_visual_part(browser, serve):
    """A declared picture part outranks its enclosing addressable element without changing what aim
    means. Choosing its hint focuses the part-anchored composer."""
    page, errors = open_page(browser, serve(PART_DIAGRAM_PAGE))
    page.keyboard.press("s")
    expect(page.locator(".lf-target-chooser-hint")).to_have_count(4)

    start_code = page.evaluate(
        """() => {
          const part = document.querySelector('#flow [data-id="S"]')
            .getBoundingClientRect();
          return [...document.querySelectorAll('.lf-target-chooser-hint')]
            .sort((a, b) => {
              const ar = a.getBoundingClientRect(), br = b.getBoundingClientRect();
              return Math.hypot(ar.left - part.left, ar.top - part.top)
                   - Math.hypot(br.left - part.left, br.top - part.top);
            })[0].dataset.lfHintCode;
        }"""
    )
    page.keyboard.type(start_code)

    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    start = page.locator('#flow [data-id="S"]')
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
    """A covering panel removes the inert document from page-target chooser."""
    page, errors = open_page(browser, serve(ROOT / "examples" / "corpus.html"))
    resized(page, 700, 900)
    page.keyboard.press("s")
    expect(page.locator(".lf-target-chooser-hint")).not_to_have_count(0)
    page.keyboard.press("Escape")
    expect(page.locator(".lf-target-chooser-hint")).to_have_count(0)

    page.get_by_role("button", name=re.compile(r"^Threads")).click()
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    assert page.locator("main").evaluate("el => el.inert")
    expect(page.locator(".lf-thread-panel")).to_have_attribute("aria-modal", "true")
    page.keyboard.press("s")
    assert page.locator(".lf-target-chooser-hint").count() == 0, (
        "page target selection crossed the covering auxiliary surface boundary"
        "page target chooser crossed the covering auxiliary surface boundary"
    )
    assert errors == []
    page.close()


def test_slash_finds_page_text_without_a_target_kind(browser, serve):
    """Slash is ordinary whole-page find. It narrows by the words the reader knows,
    highlights one exact occurrence, and Enter hands that range to the same comment
    surface as a hint. No target chooser or paragraph/sentence/widget key is needed
    first."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))

    # Selection is named on the resting line and whole-page search in the reference.
    # `to_contain_text` on the line would read hidden register rows as well.
    page.keyboard.press("?")
    page.keyboard.press("?")
    help_el = page.locator(".lf-command-reference")
    search_command = help_el.locator('tr[data-lf-command="page.search.open"]')
    select_command = help_el.locator('tr[data-lf-command="target.chooser.open"]')
    expect(search_command.locator("kbd")).to_have_text("/")
    expect(search_command.get_by_role("button")).to_have_text(
        "Search all the text on the page"
    )
    expect(select_command.locator("kbd")).to_have_text("s")
    expect(select_command.get_by_role("button")).to_have_text(
        "Comment on a visible target by hint"
    )
    page.keyboard.press("Escape")
    page.keyboard.press("/")

    search = page.get_by_role("searchbox", name="Search page text")
    expect(search).to_be_focused()
    status = page.locator(".lf-page-search-status")
    expect(status).to_be_empty()
    page.keyboard.type("b")
    expect(status).to_have_text(re.compile(r"\d+ of \d+"))
    expect(page.locator(".lf-page-search-match")).not_to_have_count(0)
    search.fill("button the key")
    expect(status).to_have_text("1 of 1")
    expect(page.locator(".lf-page-search-match")).not_to_have_count(0)
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("select match")
    page.keyboard.press("Tab")
    expect(page.locator(".lf-walk-position")).to_have_text("Match 1 of 1")
    expect(page.locator(".lf-live")).to_contain_text(
        "raises the button the key then presses"
    )

    # The readout's cached reading is refreshed on `lf-actions`, the runtime's broad
    # source invalidation. New page text therefore changes its denominator without
    # another search gesture.
    page.evaluate(
        """async () => {
          const extra = document.createElement('p');
          extra.id = 'late-search-match';
          extra.textContent = 'Another button the key occurrence.';
          document.querySelector('main').append(extra);
          document.dispatchEvent(new Event('lf-actions'));
        }"""
    )
    expect(page.locator(".lf-walk-position")).to_have_text("Match 1 of 2")
    page.evaluate(
        """async () => {
          document.querySelector('#late-search-match').remove();
          document.dispatchEvent(new Event('lf-actions'));
        }"""
    )
    expect(page.locator(".lf-walk-position")).to_have_text("Match 1 of 1")

    page.keyboard.press("Enter")
    expect(page.locator(".lf-page-search")).to_be_hidden()
    expect(page.locator(".lf-walk-position")).to_be_hidden()
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate("() => getSelection().toString()") == "button the key"
    assert pending_text(page) == "button the key"
    page.keyboard.press("n")
    expect(page.locator(".lf-walk-position")).to_have_text("Match 1 of 1")
    page.keyboard.press("n")
    expect(page.locator(".lf-walk-position")).to_have_attribute("data-lf-boundary", "")
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

    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 2")
    title = page.locator("#title").bounding_box()
    match = page.locator(".lf-page-search-match").first.bounding_box()
    assert title is not None and match is not None
    assert title["x"] <= match["x"] < title["x"] + title["width"]
    assert title["y"] <= match["y"] < title["y"] + title["height"]
    assert errors == []
    page.close()


def test_n_repeats_the_last_page_search_in_either_direction(browser, serve):
    """The search prompt keeps letters as query text. Once Enter accepts that search,
    lowercase n advances through its matches and uppercase N goes back, while a focused
    Comment box keeps both letters as text."""
    html = leaf_page(
        "repeat search",
        """
<h1 id="title">Repeated words</h1>
<p id="first">The first copper needle is here.</p>
<p id="second">The second copper needle is here.</p>
""",
    )
    page, errors = open_page(browser, serve(html))
    page.set_viewport_size({"width": 1200, "height": 900})
    page.keyboard.press("/")
    page.keyboard.type("needle")
    expect(page.get_by_role("searchbox", name="Search page text")).to_have_value(
        "needle"
    )
    shown = page.locator(".lf-shortcut-bar .lf-shortcut:not([hidden])")
    expect(shown).to_have_count(2)
    expect(shown.filter(has_text="select match")).to_have_count(1)
    expect(shown.filter(has_text="matches")).to_have_count(1)
    page.keyboard.press("Enter")
    expect(page.locator(".lf-live")).to_contain_text(
        "Press n for next, Shift+n for previous, or c to comment"
    )

    selected_in = """() => {
      const selection = getSelection();
      return selection.rangeCount
        ? selection.getRangeAt(0).startContainer.parentElement.closest('p')?.id
        : null;
    }"""
    assert page.evaluate(selected_in) == "first"

    page.keyboard.press("?")
    page.keyboard.press("?")
    help_el = page.locator(".lf-command-reference")
    expect(help_el.locator('tr[data-lf-command="page.search.next"] kbd')).to_have_text(
        "n"
    )
    expect(
        help_el.locator('tr[data-lf-command="page.search.previous"] kbd')
    ).to_have_text("N")
    page.keyboard.press("Escape")

    page.keyboard.press("n")
    assert page.evaluate(selected_in) == "second"
    expect(page.locator(".lf-walk-position")).to_have_text("Match 2 of 2")
    page.keyboard.press("Shift+n")
    assert page.evaluate(selected_in) == "first"
    position = page.locator(".lf-walk-position")
    expect(position).to_have_text("Match 1 of 2")

    # A page rewrite can split the text node under a captured match. Its old offsets
    # then retire the walk rather than throwing from Range construction on every paint.
    page.evaluate(
        """async () => {
          const selected = getSelection().getRangeAt(0);
          selected.startContainer.splitText(selected.startOffset + 1);
          const {repaint} = await window.__lfRuntimeImport('/runtime/repaint.js');
          repaint();
        }"""
    )
    expect(position).to_be_hidden()
    page.keyboard.press("Shift+n")
    expect(position).to_have_text("Match 2 of 2")
    page.keyboard.press("n")
    expect(position).to_have_text("Match 1 of 2")

    composer = page.locator(".lf-fab-input")
    composer.focus()
    page.keyboard.type("nN")
    expect(composer).to_have_value("nN")
    assert (
        page.evaluate(
            """() => [...CSS.highlights.get('lf-pending')][0]
              .startContainer.parentElement.closest('p').id"""
        )
        == "first"
    )
    page.evaluate(
        """async () => {
          getSelection().removeAllRanges();
          const {repaint} = await window.__lfRuntimeImport('/runtime/repaint.js');
          repaint();
        }"""
    )
    expect(position).to_be_hidden()
    assert errors == []
    page.close()


def test_a_search_selection_keeps_the_response_bar_off_its_passage(browser, serve):
    """A quote's resolved place is the area being read, whether the words remain in
    an authored text block or a widget renders them in its own readable body."""
    html = leaf_page(
        "clear selected passages",
        """
<p id="plain">The plain copper needle is here.</p>
<lf-draft id="draft"><pre>The drafted copper needle is here.</pre></lf-draft>
""",
    )
    page, errors = open_page(browser, serve(html))
    page.set_viewport_size({"width": 1200, "height": 900})

    def response_bar_is_clear_of(target):
        return page.evaluate(
            """target => {
              const bar = document.querySelector('.lf-fab-bar').getBoundingClientRect();
              const passage = document.querySelector(target).getBoundingClientRect();
              return bar.right <= passage.left || bar.left >= passage.right ||
                bar.bottom <= passage.top || bar.top >= passage.bottom;
            }""",
            target,
        )

    page.keyboard.press("/")
    page.keyboard.type("needle")
    page.keyboard.press("Enter")
    assert response_bar_is_clear_of("#plain")

    page.keyboard.press("n")
    assert page.evaluate("() => getSelection().anchorNode.parentElement.className") == (
        "lf-draft-body"
    )
    assert response_bar_is_clear_of("#draft"), (
        "the response bar covered the readable body of a widget-rendered passage"
    )
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
    expect(page.locator(".lf-page-search")).to_be_hidden()

    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("/")
    thread_search = page.get_by_role("searchbox", name="Find in threads")
    expect(thread_search).to_be_focused()
    expect(page.locator(".lf-page-search")).to_be_hidden()
    page.keyboard.type("Comment 1")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)
    assert errors == []
    page.close()


def test_empty_thread_scope_keeps_slash_in_its_search(browser, serve):
    """An empty thread list still has a usable find box. Slash focuses that nearest
    search rather than opening page search behind the panel."""
    html = leaf_page("empty scoped slash", "<p>Searchable page words.</p>")
    page, errors = open_page(browser, serve(html))

    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    threads = page.locator(".lf-threads")
    expect(threads).to_be_focused()
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("search page")
    page.keyboard.press("/")
    expect(page.get_by_role("searchbox", name="Find in threads")).to_be_focused()
    expect(page.locator(".lf-page-search")).to_be_hidden()
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
    expect(page.locator(".lf-page-search-status")).to_contain_text("of 2")

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
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")
    expect(page.locator(".lf-page-search-match")).not_to_have_count(0)
    expect(page.get_by_role("searchbox", name="Search page text")).to_be_focused()

    page.keyboard.press("Enter")
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    assert page.evaluate("() => getSelection().toString()") == "distant phrase"
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

    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")
    match = page.locator(".lf-page-search-match").first
    expect(match).to_be_visible()
    mark = page.evaluate(
        """() => {
          const node = document.querySelector('.lf-page-search-match');
          if (!node) return null;
          const { x, y, width, height } = node.getBoundingClientRect();
          return { x, y, width, height };
        }"""
    )
    assert mark is not None
    shortcut_bar_top = page.locator(".lf-shortcut-bar").bounding_box()["y"]
    assert mark["y"] > 42 and mark["y"] + mark["height"] < shortcut_bar_top

    page.keyboard.press("Enter")
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    assert page.evaluate("() => getSelection().toString()") == "copper needle"
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
    expect(page.locator(".lf-target-chooser-hint.lf-current")).to_have_count(1)

    page.evaluate("() => { document.scrollingElement.scrollTop = 1050; }")
    expect(page.locator(".lf-target-chooser-hint.lf-current")).to_have_count(0)
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("select target")
    page.keyboard.press("Enter")
    assert page.evaluate("() => getSelection().toString()") == ""
    assert errors == []
    page.close()


def test_scrolling_target_hints_does_not_measure_hidden_targets(browser, serve):
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
    expect(page.locator(".lf-target-chooser-hint")).to_have_count(3)

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
    page.locator("main p").click()
    page.keyboard.press("/")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("close search")
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("back to hints")
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
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("back to hints")
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
    expect(page.locator(".lf-target-chooser-hint")).to_have_count(0)
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("search page")
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("choose hint")
    page.keyboard.press("/")
    page.keyboard.type("phrase only appears")
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")
    expect(page.locator(".lf-page-search-match")).not_to_have_count(0)

    page.keyboard.press("Enter")
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    assert page.evaluate("() => getSelection().toString()") == "phrase only appears"
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
    expect(page.locator(".lf-target-chooser-hint")).to_have_count(1)

    geometry = page.evaluate(
        """() => ({
          bannerBottom: document.querySelector('.lf-banner').getBoundingClientRect().bottom,
          hintTop: document.querySelector('.lf-target-chooser-hint').getBoundingClientRect().top,
        })"""
    )
    assert geometry["hintTop"] >= geometry["bannerBottom"], geometry

    page.keyboard.press("Escape")
    page.evaluate(
        """() => {
          const text = document.querySelector('#edge').firstChild;
          const range = document.createRange();
          range.selectNodeContents(text);
          const shortcut_bar = document.querySelector('.lf-shortcut-bar').getBoundingClientRect();
          document.scrollingElement.scrollTop += range.getBoundingClientRect().top - (shortcut_bar.top - 5);
        }"""
    )
    page.keyboard.press("s")
    expect(page.locator(".lf-target-chooser-hint")).to_have_count(1)
    geometry = page.evaluate(
        """() => ({
          shortcutBarTop: document.querySelector('.lf-shortcut-bar').getBoundingClientRect().top,
          hintBottom: document.querySelector('.lf-target-chooser-hint').getBoundingClientRect().bottom,
        })"""
    )
    assert geometry["hintBottom"] <= geometry["shortcutBarTop"], geometry
    assert errors == []
    page.close()


def test_the_shortcut_bar_text_only_hides_targets_in_the_lane_it_paints(browser, serve):
    """Bottom chrome is a rectangle, not a full-width cutoff.

    Fixed nested targets can remain visible below the top of the left-hand shortcut bar while
    crossing its right edge. The selector must keep their uncovered parts reachable and
    spread both hints inside the viewport but outside the band; the old scalar boundary
    dropped both targets, while a center left on their covered corner put replacement
    hints on the shortcut bar or below the viewport."""
    html = leaf_page(
        "target beside the shortcut bar",
        """
<section id="right-edge"
  style="position: fixed; left: 250px; bottom: 4px; width: 500px; padding-bottom: 1px">
  <p id="edge-copy" style="margin: 0">
    This target crosses the edge of the keyboard legend into open space.
  </p>
</section>
""",
    )
    page, errors = open_page(browser, serve(html))
    resized(page, 1200, 800)
    page.keyboard.press("s")

    expect(page.locator(".lf-target-chooser-hint")).to_have_count(2)
    target, line, hints = page.evaluate(
        """() => [
          document.querySelector('#right-edge').getBoundingClientRect().toJSON(),
          document.querySelector('.lf-shortcut-bar').getBoundingClientRect().toJSON(),
          [...document.querySelectorAll('.lf-target-chooser-hint')].map(
            hint => hint.getBoundingClientRect().toJSON()
          ),
        ]"""
    )
    assert target["left"] < line["right"] < target["right"], (
        target,
        line,
    )
    assert target["top"] < line["bottom"] and target["bottom"] > line["top"], (
        target,
        line,
    )
    for hint in hints:
        assert hint["bottom"] <= 800, hint
        assert not (
            hint["left"] < line["right"]
            and line["left"] < hint["right"]
            and hint["top"] < line["bottom"]
            and line["top"] < hint["bottom"]
        ), (hint, line)
    assert not (
        hints[0]["left"] < hints[1]["right"]
        and hints[1]["left"] < hints[0]["right"]
        and hints[0]["top"] < hints[1]["bottom"]
        and hints[1]["top"] < hints[0]["bottom"]
    ), hints

    page.keyboard.press("Escape")
    page.keyboard.press("/")
    page.keyboard.type("crosses the edge")
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")
    expect(page.locator(".lf-page-search-match")).to_have_count(1)
    line, mark = page.evaluate(
        """() => ['.lf-shortcut-bar', '.lf-page-search-match'].map(
          selector => document.querySelector(selector).getBoundingClientRect().toJSON()
        )"""
    )
    assert not (
        mark["left"] < line["right"]
        and line["left"] < mark["right"]
        and mark["top"] < line["bottom"]
        and line["top"] < mark["bottom"]
    ), (mark, line)
    assert errors == []
    page.close()


def test_a_partly_banner_clipped_atomic_element_keeps_its_hint_below_the_banner(
    browser, serve
):
    """Atomic visuals use element geometry rather than text ranges, but obey the same
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
    expect(page.locator(".lf-target-chooser-hint")).to_have_count(1)

    geometry = page.evaluate(
        """() => ({
          bannerBottom: document.querySelector('.lf-banner').getBoundingClientRect().bottom,
          hintTop: document.querySelector('.lf-target-chooser-hint').getBoundingClientRect().top,
        })"""
    )
    assert geometry["hintTop"] >= geometry["bannerBottom"], geometry
    assert errors == []
    page.close()
