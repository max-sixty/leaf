"""Keyboard semantic-selection browser journeys."""

import json
import re

import pytest
from playwright.sync_api import expect
from render_cases_layout import DRAFT_MARK
from render_cases_navigation import (
    TARGETS_PAGE,
    pending_text,
)
from render_cases_widgets import (
    PART_DIAGRAM_PAGE,
)
from render_harness import (
    EXAMPLES,
    ROOT,
    available_commands,
    expect_panel_says,
    leaf_page,
    open_page,
    panel_control,
    panel_field,
    resized,
    scroll_settled,
    selection_field,
    sending,
    write,
)

from leaf import event_log as events_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_selection_snap_stops_at_explicit_table_line_break(browser, serve):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Table line selection",
                "<table><tr><td><strong>Short label here</strong><br>"
                "<span>Then a second line of text.</span></td></tr></table>",
            )
        ),
    )
    first = page.locator("td strong").bounding_box()
    page.mouse.move(first["x"] + 2, first["y"] + first["height"] / 2)
    page.mouse.down()
    before = page.evaluate("""() => {
      const first = document.querySelector('td strong').firstChild;
      const next = document.querySelector('td span').firstChild;
      const selection = getSelection();
      selection.setBaseAndExtent(first, 0, next, 0);
      return selection.toString();
    }""")
    page.mouse.up()
    rendered(page)
    after, quote = page.evaluate("""async () => {
      const first = document.querySelector('td strong').firstChild;
      const next = document.querySelector('td span').firstChild;
      const selection = getSelection();
      const after = selection.toString();
      selection.setBaseAndExtent(first, 0, next, 4);
      const {anchorForRange} = await window.__lfCheckApi();
      return [after, anchorForRange(selection.getRangeAt(0)).quote];
    }""")
    assert before == "Short label here\n"
    assert after == before
    assert quote == "Short label here Then"


def test_short_inline_code_selection_offers_comment(browser, serve):
    """A complete code term is commentable even when it is one or two characters."""
    page = open_page(
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
        expect(selection_field(page)).to_be_visible()
        assert page.evaluate("() => getSelection().toString()") == term
        expect(page.locator(".lf-fab-input:focus")).to_have_count(0)

    page.keyboard.press("c")
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    write(field, "Name this variable more clearly.")
    with sending(page, "the short-code comment"):
        page.keyboard.press("ControlOrMeta+Enter")

    event = events_model.read_events(serve.page_dir)[-1]
    assert event["anchor"] == {
        "section": "code",
        "quote": "id",
        "prefix": "Compare x with",
        "suffix": ".",
    }


def test_desktop_target_picker_arms_the_page_as_alt_does(browser, serve):
    """While `s` stands, the mouse shows and takes a target as Alt-click does."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Desktop targets",
                '<p id="link"><a href="#elsewhere">Follow this link</a></p><p id="elsewhere">Destination</p>',
            )
        ),
    )
    link = page.get_by_role("link", name="Follow this link")
    link.hover()
    expect(page.locator(".lf-aim[data-for]")).to_have_count(0)
    # Opened under a still mouse, the promise paints without waiting for a move.
    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint")).not_to_have_count(0)
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "link")
    # A middle press is armed too: it opens no tab and chooses nothing, so the picker stands.
    link.click(button="middle")
    expect(page.locator(".lf-target-picker-hint")).not_to_have_count(0)
    # The first click chooses and closes the picker; the second is the same gesture's.
    link.dblclick()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-target-picker-hint")).to_have_count(0)
    expect(page.locator(".lf-aim[data-for]")).to_have_count(0)
    assert not page.url.endswith("#elsewhere"), "the picker's press followed the link"
    assert page.context.pages == [page], "the picker's middle press opened the link"


def test_target_picker_takes_a_margin_press_as_the_target_it_stands_by(browser, serve):
    """Over a suggestion's ✓ Accept, the picker comments on the change, as Alt does."""
    page = open_page(
        browser, serve(next(p for p in EXAMPLES if p.stem == "release-notes"))
    )
    before = len(events_model.read_events(serve.page_dir))
    accept = page.locator(".lf-margin-cluster .lf-sug-accept").first
    accept.scroll_into_view_if_needed()
    accept.hover()
    page.keyboard.press("s")
    promised = page.locator(".lf-aim").get_attribute("data-for")
    assert promised, "the picker painted no target over the margin row"
    accept.click()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    assert page.evaluate(DRAFT_MARK) == promised
    assert not [
        e
        for e in events_model.read_events(serve.page_dir)[before:]
        if e["kind"] == "action"
    ], "the picker's press accepted the suggestion"


def test_select_element_obeys_covering_surfaces_and_pointer_modes(browser, serve):
    """The picker shares Design targets, while Draw mode owns input."""
    page = open_page(browser, serve(TARGETS_PAGE))
    for key, available in (("l", True), ("w", False)):
        page.keyboard.press(key)
        assert ("target.picker.open" in available_commands(page)) is available, key
        # Text search remains available inside these pointer modes.
        page.keyboard.press("/")
        page.get_by_role("searchbox", name="Search page text").fill("paragraph")
        expect(page.locator(".lf-page-search-match")).not_to_have_count(0)
        page.keyboard.press("Escape")
        page.keyboard.press("Escape")


def test_the_picker_s_way_out_stays_available_across_pointer_changes(browser, serve):
    """The picker's ✕ stays in the panel's row as the primary pointer changes under
    it."""
    page = open_page(browser, serve(TARGETS_PAGE))
    cancel = page.locator('.lf-fp-exit[aria-label="Close picker"]')
    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint")).to_have_count(3)
    expect(cancel).to_be_visible()

    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": True})
    expect(cancel).to_be_visible()
    cancel.click()
    expect(page.locator(".lf-target-picker-hint")).to_have_count(0)
    page.keyboard.press("s")
    expect(cancel).to_be_visible()
    cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": False})
    expect(cancel).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-target-picker-hint")).to_have_count(0)


def test_s_aims_at_the_addressable_element_named_by_its_hint(browser, serve):
    """The keyboard target is the same addressable element Alt-click would take. Choosing the
    paragraph focuses its in-place Comment field without making a native selection."""
    page = open_page(browser, serve(TARGETS_PAGE))
    page.keyboard.press("s")

    hints = page.locator(".lf-target-picker-hint")
    expect(hints).to_have_count(3)  # heading, paragraph, and figure
    page.keyboard.press("Tab")
    expect_panel_says(page, "Target 1 of 3")
    expect(page.locator(".lf-target-picker-hint.lf-current")).to_have_count(1)
    expect(page.locator(".lf-live")).to_contain_text("Hint a: heading: Targets")
    page.keyboard.press("?")
    expect(
        page.locator(".lf-command-reference").get_by_role(
            "heading", name="In the target picker", exact=True
        )
    ).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-command-reference")).to_be_hidden()
    expect(hints).to_have_count(3)  # help was a layer over the picker, not its end
    prose_code = page.evaluate(
        """() => {
          const top = document.querySelector('#prose').getBoundingClientRect().top;
          return [...document.querySelectorAll('.lf-target-picker-hint')]
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

    # Text entry owns letters. Tab extends the same response surface; Escape restores
    # the same draft.
    bar = page.locator(".lf-fab-bar")
    page.keyboard.press("s")
    expect(field).to_have_js_property("value", "s")
    write(field, "Keep this draft")
    page.keyboard.press("Tab")
    expect(bar.locator('[data-token="keep"]')).to_be_focused()
    expect(field).to_be_visible()
    page.keyboard.press("Escape")
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "Keep this draft")
    assert page.evaluate(DRAFT_MARK) == "prose"
    assert pending_text(page) == ""
    page.keyboard.press("Escape")
    expect(field).to_be_hidden()


def test_a_keyboard_comment_gesture_carries_the_current_unsent_draft(browser, serve):
    """Keyboard and pointer Comment gestures make the same explicit re-anchoring."""
    page = open_page(browser, serve(TARGETS_PAGE))
    field = page.locator(".lf-fab-input")
    draft = "Carry these deliberate words."

    page.locator("h1").click(modifiers=["Alt"])
    expect(field).to_be_focused()
    write(field, draft)
    page.evaluate("document.activeElement.blur()")

    page.keyboard.press("s")
    hints = page.locator(".lf-target-picker-hint")
    expect(hints).to_have_count(3)
    prose_code = page.evaluate(
        """() => {
          const top = document.querySelector('#prose').getBoundingClientRect().top;
          return [...document.querySelectorAll('.lf-target-picker-hint')]
            .sort((a, b) => Math.abs(a.getBoundingClientRect().top - top)
                          - Math.abs(b.getBoundingClientRect().top - top))[0]
            .dataset.lfHintCode;
        }"""
    )
    page.keyboard.type(prose_code)

    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", draft)
    assert page.evaluate(DRAFT_MARK) == "prose"


def test_a_selected_target_keeps_escape_when_the_layer_has_no_reactions(browser, serve):
    """Without reactions, the focused composer still takes Escape."""
    registry = json.loads((ROOT / "packages/default/registry.json").read_text())
    tokens = {name: None for name in registry["$reactions"]["tokens"]}
    page = open_page(
        browser,
        serve(TARGETS_PAGE, layer_registry={"$reactions": {"tokens": tokens}}),
    )
    page.keyboard.press("s")
    code = (
        page.locator(".lf-target-picker-hint").nth(1).get_attribute("data-lf-hint-code")
    )
    page.keyboard.type(code)

    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    expect(bar).to_have_attribute("aria-label", re.compile(r"^Respond to "))
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-fab-input")).to_have_attribute(
        "aria-keyshortcuts", "Enter Meta+Enter Control+Enter"
    )

    page.keyboard.press("Escape")
    expect(page.locator(".lf-fab-input")).to_be_hidden()


def test_the_panel_field_offers_selected_words_to_a_press_alone(browser, serve):
    """Words a script selects are quoted in the panel's field beside c, the key that
    comments on them as a press there does, while a Tab into the field writes on the
    page. A page draft hiding the quote shows a Selection mode chip, and on a page
    drawing its own annotations the field stands in an open comment box's place while
    it quotes."""
    source = leaf_page(
        "Offered words",
        '<p id="first">The first passage holds its words.</p>'
        '<p id="second">A second passage comes after it.</p>',
    )
    page = open_page(browser, serve(source))
    field = panel_field(page)
    offered = selection_field(page)
    composer = page.locator(".lf-fab-input")

    def select(paragraph):
        page.locator(paragraph).evaluate("el => getSelection().selectAllChildren(el)")

    select("#first")
    expect(offered).to_have_attribute(
        "placeholder", "“The first passage holds its words.” c"
    )
    expect(offered).to_have_attribute("aria-label", "Comment on the selection")
    page.locator(".lf-fp-leaf").focus()
    page.keyboard.press("Tab")
    expect(field).to_be_focused()
    page.keyboard.type("A page note")
    expect(field).to_have_js_property("value", "A page note")
    expect(field).to_have_attribute("aria-label", "Comment on the page")
    expect(composer).to_be_hidden()

    page.locator(".lf-fp-leaf").focus()
    select("#first")
    context = page.locator(".lf-fp-mode")
    expect(context).to_have_text("Selection")
    expect(context).to_have_attribute("title", "“The first passage holds its words.”")
    field.click()
    expect(composer).to_be_focused()
    expect(field).to_have_js_property("value", "A page note")
    expect(context).to_have_text("")

    # Where the open box stands in the field's place, it leaves that place to the field
    # while new words are offered.
    page = open_page(
        browser,
        serve(source.replace("<body>", '<body data-annotations="page">', 1)),
    )
    offered = selection_field(page)
    composer = page.locator(".lf-fab-input")
    select("#first")
    expect(offered).to_be_visible()
    # A native selectionchange can deliver the next passage before the preceding
    # press's handoff timer runs. Hold that ordering so the offer cannot depend on
    # a second notification after the handoff ends.
    page.clock.install(time=0)
    page.clock.pause_at(1)
    offered.click()
    # Focus the native editor while its scheduled landing is also held.
    composer.focus()
    composer.blur()
    page.evaluate("""async () => {
      await new Promise(resolve => {
        document.addEventListener('selectionchange', resolve, {once: true});
        getSelection().selectAllChildren(document.querySelector('#second'));
      });
    }""")
    page.clock.resume()
    expect(offered).to_have_attribute(
        "placeholder", "“A second passage comes after it.” c"
    )
    offered.click()
    expect(composer).to_be_focused()
    expect(page.locator("#lf-composer-quote")).to_contain_text("A second passage")


def test_a_passage_still_offers_suggest_when_the_layer_has_no_reactions(browser, serve):
    """Tab means other responses rather than reactions specifically: removing the
    reaction vocabulary must not strand Suggest for a selected passage."""
    registry = json.loads((ROOT / "packages/default/registry.json").read_text())
    tokens = {name: None for name in registry["$reactions"]["tokens"]}
    page = open_page(
        browser,
        serve(TARGETS_PAGE, layer_registry={"$reactions": {"tokens": tokens}}),
    )

    prose = page.locator("#prose")
    prose.select_text()
    field = page.locator(".lf-fab-input")
    expect(selection_field(page)).to_be_visible()
    # The composer has not opened, so its field is not on the page to hold focus.
    expect(page.locator(".lf-fab-input:focus")).to_have_count(0)
    page.keyboard.press("c")
    expect(field).to_be_focused()
    expect(page.locator(".lf-fab-bar .lf-react")).to_have_count(0)
    page.keyboard.press("Tab")

    responses = page.locator(".lf-fab-bar")
    expect(responses.locator(".lf-response-options")).to_be_visible()
    expect(responses.locator(".lf-fab-suggest")).to_be_focused()
    expect(responses.locator(".lf-react")).to_have_count(0)


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
    page = open_page(browser, serve(html))
    page.keyboard.press("s")

    hints = page.locator(".lf-target-picker-hint")
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


def test_nested_target_hints_show_containment_without_covering_each_other(
    browser, serve
):
    """A container and its first child may paint the same box corner. Both remain
    reachable, with separate chips outside their targets and each other, and the
    child's chip stands right of its container's, so the two read as an outline."""
    html = leaf_page(
        "nested targets",
        '<section id="outer"><p id="inner">The child fills its parent.</p></section>',
        head="<style>section { padding-bottom: 5rem; } section, p { margin: 0; }</style>",
    )
    page = open_page(browser, serve(html))
    page.keyboard.press("s")

    hints = page.locator(".lf-target-picker-hint")
    expect(hints).to_have_count(2)
    geometry = page.evaluate(
        """() => ({
          targetLefts: ['outer', 'inner'].map(id =>
            document.getElementById(id).getBoundingClientRect().left),
          hints: [...document.querySelectorAll('.lf-target-picker-hint')].map(node => {
          const { left, top, right, bottom } = node.getBoundingClientRect();
            return { left, top, right, bottom, centre: (left + right) / 2 };
          }),
        })"""
    )
    boxes = geometry["hints"]
    assert abs(geometry["targetLefts"][0] - geometry["targetLefts"][1]) < 0.5
    assert all(box["right"] <= geometry["targetLefts"][0] for box in boxes), geometry
    assert boxes[1]["left"] >= boxes[0]["left"] + 8, geometry
    assert not (
        boxes[0]["left"] < boxes[1]["right"]
        and boxes[1]["left"] < boxes[0]["right"]
        and boxes[0]["top"] < boxes[1]["bottom"]
        and boxes[1]["top"] < boxes[0]["bottom"]
    ), geometry


def test_identical_nested_target_hints_choose_the_innermost_target(browser, serve):
    """A transparent wrapper and its only child can describe one visible box. The
    picker names that box once and agrees with direct aiming by opening Comment on
    the child."""
    html = leaf_page(
        "identical nested targets",
        '<section id="outer"><div id="inner">One visible box.</div></section>',
        head="<style>section, div { margin: 0; }</style>",
    )
    page = open_page(browser, serve(html))
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
    hints = page.locator(".lf-target-picker-hint")
    expect(hints).to_have_count(1)
    page.keyboard.type(hints.get_attribute("data-lf-hint-code"))
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(DRAFT_MARK) == "inner"


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
    page = open_page(browser, serve(html))

    page.keyboard.press("s")
    hints = page.locator(".lf-target-picker-hint")
    expect(hints).to_have_count(2)  # heading and disclosure

    page.keyboard.press("Escape")
    page.locator("#evidence > summary").click()
    page.keyboard.press("s")
    expect(hints).to_have_count(32)

    codes = hints.evaluate_all("nodes => nodes.map(node => node.dataset.lfHintCode)")
    tail = next(code for code in codes if len(code) > 1)
    page.keyboard.press(tail[0])
    expect(hints).to_have_count(sum(code.startswith(tail[0]) for code in codes))
    continued = page.locator(
        f'.lf-target-picker-hint[data-lf-hint-code="{tail}"] .lf-binding-sequence'
    )
    assert continued.locator("kbd").evaluate_all(
        "keys => keys.map(key => [key.textContent, key.dataset.lfSequenceStepState])"
    ) == [[tail[0], "pressed"], [tail[1], "neutral"]]
    expect(continued).to_have_css("gap", "1px")
    page.locator("#evidence > summary").click()
    expect(hints).to_have_count(0)


@pytest.mark.parametrize("route", ["keyboard", "touch"])
def test_selection_opens_the_same_comment_field_on_a_declared_visual_part(
    browser, serve, route
):
    """Keyboard hints and touch presses open a composer anchored to the named shape."""
    context = browser.new_context(has_touch=route == "touch")
    page = open_page(browser, serve(PART_DIAGRAM_PAGE), context=context)
    if route == "touch":
        panel_control(page, "command:target.picker.open", at="annotate").tap()
        page.locator('#flow [data-id="S"]').tap()
    else:
        page.keyboard.press("s")
        expect(page.locator(".lf-target-picker-hint").first).to_be_visible()
        start_code = page.evaluate(
            """() => {
              const part = document.querySelector('#flow [data-id="S"]')
                .getBoundingClientRect();
              return [...document.querySelectorAll('.lf-target-picker-hint')]
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
    write(page.locator(".lf-fab-input"), "Explain this shape.")
    with sending(page, "the selected shape comment"):
        submit = page.locator(".lf-fab-bar .lf-compose-submit")
        submit.tap() if route == "touch" else submit.click()
    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [comment["anchor"] for comment in comments] == [
        {"section": "flow", "visual": "node:S"}
    ]


def test_slash_finds_page_text_without_a_target_kind(browser, serve):
    """Slash is ordinary whole-page find. It narrows by the words the user knows,
    highlights one exact occurrence, and Enter hands that range to the same comment
    surface as a hint. No target picker or paragraph/sentence/widget key is needed
    first."""
    page = open_page(browser, serve(TARGETS_PAGE))

    # Selection and whole-page search are named in the reference.
    page.keyboard.press("?")
    help_el = page.locator(".lf-command-reference")
    search_command = help_el.locator('[role=row][data-lf-command="page.search.open"]')
    select_command = help_el.locator('[role=row][data-lf-command="target.picker.open"]')
    expect(search_command.locator("kbd")).to_have_text("/")
    expect(search_command.get_by_role("button")).to_have_text("Search page")
    expect(search_command.locator(".lf-command-reference-description")).to_have_count(0)
    expect(select_command.locator("kbd")).to_have_text("s")
    expect(select_command.get_by_role("button")).to_have_text("Select mode")
    expect(select_command.get_by_role("button")).to_have_attribute(
        "title", "Choose an element by pressing it or typing its hint, then comment"
    )
    page.keyboard.press("Escape")
    page.keyboard.press("/")

    search = page.get_by_role("searchbox", name="Search page text")
    expect(search).to_be_focused()
    status = page.locator(".lf-page-search-status")
    expect(status).to_be_empty()
    search_field = page.locator(".lf-page-search-box")
    # Focus arrives before the panel presents its Close control. Measure the
    # completed search row before comparing query and feedback changes.
    rendered(page)
    search_box = search_field.bounding_box()
    search.fill("words absent from this page")
    expect(status).to_have_attribute("aria-label", "No matches")
    assert search_field.bounding_box() == pytest.approx(search_box, abs=0.5)
    # Query and feedback stay in the panel, with a persistent mode label even once
    # typing replaces the placeholder. Both share one row even on a phone.
    frame = search.evaluate("""input => {
      const box = document.querySelector('.lf-fp-row').getBoundingClientRect();
      const status = document.querySelector('.lf-page-search-status').getBoundingClientRect();
      return {
        statusInside: status.left >= box.left && status.right <= box.right &&
          status.top >= box.top && status.bottom <= box.bottom,
      };
    }""")
    assert frame["statusInside"], frame
    expect(page.locator(".lf-fp-mode")).to_have_text("Search page")
    search.press("ControlOrMeta+a")
    search.press("Backspace")
    expect(search).to_have_value("")
    expect(search).to_be_focused()
    expect(status).to_be_empty()
    assert search_field.bounding_box() == pytest.approx(search_box, abs=0.5)
    page.keyboard.type("b")
    expect(status).to_have_text(re.compile(r"\d+ of \d+"))
    assert search_field.bounding_box() == pytest.approx(search_box, abs=0.5)
    expect(page.locator(".lf-page-search-match")).not_to_have_count(0)
    search.fill("button the key")
    expect(status).to_have_text("1 of 1")
    assert search_field.bounding_box() == pytest.approx(search_box, abs=0.5)
    expect(page.locator(".lf-page-search-match")).not_to_have_count(0)
    page.keyboard.press("Tab")
    expect_panel_says(page, "Match 1 of 1")
    expect(page.locator(".lf-live")).to_contain_text(
        "raises the button the key then presses"
    )

    page.keyboard.press("Enter")
    expect(page.locator(".lf-page-search")).to_be_hidden()
    expect_panel_says(page, "Match 1 of 1")
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate("() => getSelection().toString()") == "button the key"
    assert pending_text(page) == "button the key"
    page.keyboard.press("n")
    expect_panel_says(page, "Match 1 of 1")


def test_page_search_starts_with_the_first_match_at_the_reading_edge(browser, serve):
    """Search begins at the top of the visible reading rather than whichever match is
    nearest the viewport midpoint, so an opening title is the result that gets paint.
    Tab still reaches the next match after the words under the search are rewritten."""
    html = leaf_page(
        "search from reading edge",
        """
<h1 id="title">Unified title</h1>
<div style="height: 260px" aria-hidden="true"></div>
<p>Unified body.</p>
""",
    )
    page = open_page(browser, serve(html))
    page.keyboard.press("/")
    page.keyboard.type("Unified")

    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 2")
    title = page.locator("#title").bounding_box()
    match = page.locator(".lf-page-search-match").first.bounding_box()
    assert title is not None and match is not None
    assert title["x"] <= match["x"] < title["x"] + title["width"]
    assert title["y"] <= match["y"] < title["y"] + title["height"]

    # Words rewritten under the open search, as a revision does, leave the matches naming
    # nodes the page no longer reads. Moving on finds them again rather than placing a
    # match in a reading that has no position for it, which once never returned.
    page.evaluate(
        """() => {
          const body = document.querySelector('main p');
          body.firstChild.replaceWith(document.createTextNode('Unified body, rewritten.'));
        }"""
    )
    page.get_by_role("searchbox", name="Search page text").press("Tab")
    expect(page.locator(".lf-page-search-status")).to_have_text("2 of 2")
    expect(page.locator(".lf-live")).to_contain_text(
        "Match 2 of 2: …Unified title Unified body, rewritten."
    )


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
    page = open_page(browser, serve(html))
    page.set_viewport_size({"width": 1200, "height": 900})
    page.keyboard.press("/")
    page.keyboard.type("needle")
    expect(page.get_by_role("searchbox", name="Search page text")).to_have_value(
        "needle"
    )
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
    expect_panel_says(page, "Match 1 of 2")

    # A new query owns the field while it is open. Canceling it retires that position
    # without replacing the accepted query that n/N will resume.
    page.keyboard.press("/")
    search = page.get_by_role("searchbox", name="Search page text")
    search.fill("absent from this page")
    page.keyboard.press("Escape")
    expect(search).to_be_hidden()
    expect_panel_says(page, "Match", says=False)

    page.keyboard.press("?")
    help_el = page.locator(".lf-command-reference")
    expect(
        help_el.locator('[role=row][data-lf-command="page.search.next"] kbd')
    ).to_have_text("n")
    expect(
        help_el.locator('[role=row][data-lf-command="page.search.previous"] kbd')
    ).to_have_text("N")
    page.keyboard.press("Escape")

    page.keyboard.press("n")
    assert page.evaluate(selected_in) == "second"
    expect_panel_says(page, "Match 2 of 2")
    page.keyboard.press("Shift+n")
    assert page.evaluate(selected_in) == "first"
    expect_panel_says(page, "Match 1 of 2")

    # A page rewrite can split the text node under a captured match. Its old offsets
    # then retire the walk rather than throwing from Range construction on every paint.
    page.evaluate(
        """async () => {
          const selected = getSelection().getRangeAt(0);
          selected.startContainer.splitText(selected.startOffset + 1);
          dispatchEvent(new Event('resize'));
        }"""
    )
    expect_panel_says(page, "Match", says=False)

    page.keyboard.press("Shift+n")
    expect_panel_says(page, "Match 2 of 2")
    page.keyboard.press("n")
    expect_panel_says(page, "Match 1 of 2")

    composer = page.locator(".lf-fab-input")
    composer.focus()
    page.keyboard.type("nN")
    expect(composer).to_have_js_property("value", "nN")
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
          dispatchEvent(new Event('resize'));
        }"""
    )
    expect_panel_says(page, "Match", says=False)

    # A pointer accepts the same selected match as Return, including its position.
    page.keyboard.press("Escape")
    page.keyboard.press("/")
    search.fill("needle")
    search.press("Tab")
    expect(page.locator(".lf-page-search-status")).to_have_text("2 of 2")
    rendered(page)
    match = page.locator(".lf-page-search-match").first.bounding_box()
    assert match is not None
    page.mouse.click(match["x"] + match["width"] / 2, match["y"] + match["height"] / 2)
    expect(search).to_be_hidden()
    expect_panel_says(page, "Match 2 of 2")


def test_touch_search_keeps_its_match_position_and_comment_route(browser, serve):
    """The selected quote offers a touch comment without hiding its search position."""
    html = leaf_page(
        "touch search",
        "<h1>Repeated words</h1><p>The first copper needle is here.</p>"
        '<p id="second">The second copper needle is here.</p>',
    )
    context = browser.new_context(
        has_touch=True, viewport={"width": 390, "height": 844}
    )
    page = open_page(browser, serve(html), context=context)
    panel_control(page, "command:page.search.open", at="navigate").tap()
    search = page.get_by_role("searchbox", name="Search page text")
    search.fill("needle")
    page.get_by_role("button", name="Next match", exact=True).tap()
    expect(page.locator(".lf-page-search-status")).to_have_text("2 of 2")
    rendered(page)
    match = page.locator(".lf-page-search-match").first.bounding_box()
    assert match is not None
    page.touchscreen.tap(
        match["x"] + match["width"] / 2, match["y"] + match["height"] / 2
    )
    expect(search).to_be_hidden()
    expect_panel_says(page, "Match 2 of 2")
    selection_field(page).tap()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    assert pending_text(page) == "needle"
    assert (
        page.evaluate(
            """() => [...CSS.highlights.get('lf-pending')][0]
          .startContainer.parentElement.closest('p').id"""
        )
        == "second"
    )


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
    page = open_page(browser, serve(html))
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
    assert page.evaluate(
        "() => Boolean(getSelection().anchorNode.parentElement.closest('.lf-draft-body'))"
    )
    assert response_bar_is_clear_of("#draft .lf-draft-body"), (
        "the response bar covered the readable body of a widget-rendered passage"
    )


def test_slash_stays_native_in_text_entry(browser, serve):
    """An editable field owns slash as text."""
    html = leaf_page(
        "scoped slash",
        '<label>Path <input id="path"></label><p>Searchable page words.</p>',
    )
    page = open_page(browser, serve(html))
    path = page.locator("#path")
    path.focus()
    page.keyboard.type("/")
    expect(path).to_have_value("/")
    expect(page.locator(".lf-page-search")).to_be_hidden()


def test_selection_search_announces_context_across_inline_node_boundaries(
    browser, serve
):
    """Repeated matches that fill separate inline nodes remain distinguishable to a
    nonvisual user by context drawn from the shared page reading on both sides."""
    html = leaf_page(
        "search context",
        """
<p>Before alpha <em>repeat</em> after alpha.</p>
<p>Before beta <strong>repeat</strong> after beta.</p>
""",
    )
    page = open_page(browser, serve(html))
    page.keyboard.press("s")
    page.keyboard.press("/")
    page.keyboard.type("repeat")
    expect(page.locator(".lf-page-search-status")).to_contain_text(" of 2")

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


def test_selection_search_brings_an_offscreen_match_into_view(browser, serve):
    """A search result is a target, not only a count. When the query exists solely below
    the fold, the first complete search moves that occurrence into view and paints it;
    otherwise Enter would silently select words the user still could not see."""
    html = leaf_page(
        "offscreen search",
        """
<h1 id="title">Search the whole page</h1>
<div style="height: 1400px" aria-hidden="true"></div>
<p id="far">The distant phrase is the one this search should reveal.</p>
""",
    )
    page = open_page(browser, serve(html))
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


def test_selection_search_scrolls_to_the_match_inside_a_tall_text_block(browser, serve):
    """Whole-page find travels to the exact range, not merely to the block containing
    it. A match near the foot of a multi-screen pre is visible before Enter selects it."""
    lines = "\n".join(["an ordinary line"] * 90 + ["the solitary copper needle"])
    page = open_page(
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
    row_top = page.locator(".lf-fp-row").bounding_box()["y"]
    assert mark["y"] > 0 and mark["y"] + mark["height"] < row_top

    page.keyboard.press("Enter")
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    assert page.evaluate("() => getSelection().toString()") == "copper needle"
    assert pending_text(page) == "copper needle"


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
    page = open_page(browser, serve(html))
    page.keyboard.press("s")
    page.keyboard.press("Tab")
    expect(page.locator(".lf-live")).to_contain_text("initially announced heading")
    expect(page.locator(".lf-target-picker-hint.lf-current")).to_have_count(1)

    page.evaluate("() => { document.scrollingElement.scrollTop = 1050; }")
    expect(page.locator(".lf-target-picker-hint.lf-current")).to_have_count(0)
    page.keyboard.press("Enter")
    assert page.evaluate("() => getSelection().toString()") == ""


def test_a_scroll_with_no_scrollend_still_refreshes_the_target_map(browser, serve):
    """A page can move and never send `scrollend`: the scroll a replaced scene restores
    ends without one. The map freezes its membership for the length of a scroll, so
    with nothing to settle it the chips go on naming the scene the first frame left
    behind.

    A hidden target is dropped from the paint either way; the codes are what say whether
    the map was read again, because a fresh reading gives the survivors the head of the
    alphabet.

    Before that, a letter the map does not hold is reported and costs the user nothing
    else: resetting instead would throw away the letters they had already typed right."""
    page = open_page(browser, serve(TARGETS_PAGE))
    codes = """() => [...document.querySelectorAll('.lf-target-picker-hint')]
      .map(chip => chip.dataset.lfHintCode)"""
    page.keyboard.press("s")
    hints = page.locator(".lf-target-picker-hint")
    expect(hints).to_have_count(3)
    assert page.evaluate(codes) == ["a", "s", "d"]

    page.keyboard.press("q")
    expect(page.locator(".lf-live")).to_have_text(
        "No hint q. The current hints are unchanged."
    )
    expect(hints).to_have_count(3)
    expect(page.locator(".lf-fab-input")).to_be_hidden()

    page.evaluate(
        """() => {
          document.querySelector('#t').style.display = 'none';
          document.dispatchEvent(new Event('scroll'));
        }"""
    )

    expect(hints).to_have_count(2)
    expect(hints.nth(1)).to_have_attribute("data-lf-hint-code", "s")
    assert page.evaluate(codes) == ["a", "s"]

    page.keyboard.press("Escape")
    expect(hints).to_have_count(0)
    resized(page, 400, 900)
    page.keyboard.press("s")
    expect(hints).not_to_have_count(0)
    page.keyboard.press("Escape")
    expect(hints).to_have_count(0)


def test_an_open_search_mark_follows_the_page_it_marks(browser, serve):
    """The mark is paint in a layer no ancestor scrolls, so it stays where the page put
    it until something asks for a frame. Slash pressed from the page raises no target
    map, so nothing else on screen is watching the scroll on the mark's behalf."""
    html = leaf_page(
        "search mark travel",
        """
<div style="height: 600px" aria-hidden="true"></div>
<p id="mid">the solitary copper needle sits here</p>
<div style="height: 2400px" aria-hidden="true"></div>
""",
    )
    page = open_page(browser, serve(html))
    gap = """() => {
      const mark = document.querySelector('.lf-page-search-match');
      const text = document.querySelector('#mid');
      return Math.round(mark.getBoundingClientRect().top
                        - text.getBoundingClientRect().top);
    }"""

    page.keyboard.press("/")
    page.keyboard.type("copper needle")
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")
    expect(page.locator(".lf-page-search-match")).to_have_count(1)
    seated = page.evaluate(gap)
    assert abs(seated) < 6, f"the mark did not land on its own words: {seated}"

    page.evaluate("() => { document.scrollingElement.scrollTop += 60; }")

    page.wait_for_function(f"() => Math.abs(({gap})() - {seated}) < 6")


def test_a_nested_target_hint_follows_when_the_nesting_changes(browser, serve):
    """A nested target's chip keeps its offset outside the target when layout moves it."""
    html = leaf_page(
        "nested targets",
        '<section id="outer"><p id="inner">The child fills its parent.</p></section>',
        head="<style>section { padding-bottom: 5rem; } section, p { margin: 0; }</style>",
    )
    page = open_page(browser, serve(html))
    # The chip's own corner against the corner it names, so the step is the only thing
    # that moves when the box does.
    step = """() => {
      const chip = [...document.querySelectorAll('.lf-target-picker-hint')]
        .find(node => node.dataset.lfHintCode === 's');
      return Math.round(chip.getBoundingClientRect().left
                        - document.querySelector('#inner').getBoundingClientRect().left);
    }"""

    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint")).to_have_count(2)
    indented = page.evaluate(step)
    chip_left = page.locator('.lf-target-picker-hint[data-lf-hint-code="s"]').evaluate(
        "chip => Math.round(chip.getBoundingClientRect().left)"
    )

    # Break the containment and ask for a frame, without scrolling or resizing the window.
    page.evaluate(
        """() => {
          document.querySelector('#inner').style.marginLeft = '-60px';
          document.querySelector('.lf-fp-row').style.height = '80px';
        }"""
    )
    page.wait_for_function(
        "left => Math.round(document.querySelector('[data-lf-hint-code=\"s\"]')"
        ".getBoundingClientRect().left) === left - 60",
        arg=chip_left,
    )
    assert page.evaluate(step) == indented


def test_a_target_behind_a_page_sheet_is_offered_no_letter(browser, serve):
    """The same promise read the other way. An opaque box covers a member without
    clipping its rectangle, so geometry alone still reports the member standing there;
    a letter over the cover names something the user cannot see, and choosing it opens
    a comment on a block they never read."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "a target behind a sheet",
                """
<h1 id="head">Covered</h1>
<p id="hidden">Completely behind the sheet.</p>
<div id="sheet">An opaque page sheet.</div>
""",
                head="""<style>
  #hidden { position: relative; margin: 0; height: 4rem; }
  #sheet { position: absolute; left: 0; top: 6rem; width: 100vw; height: 10rem;
    background: white; z-index: 5; }
</style>""",
            )
        ),
    )
    page.keyboard.press("s")
    hints = page.locator(".lf-target-picker-hint")
    expect(hints.first).to_be_visible()

    # The premise: the paragraph keeps its whole rectangle and the sheet answers for
    # every point of it.
    covered = page.evaluate(
        """() => {
          const box = document.querySelector('#hidden').getBoundingClientRect();
          const at = (x, y) => document.elementFromPoint(x, y)?.id;
          return {
            box: box.toJSON(),
            corner: at(box.left + 1, box.top + 1),
            middle: at((box.left + box.right) / 2, (box.top + box.bottom) / 2),
          };
        }"""
    )
    assert covered["box"]["height"] > 0, covered
    assert covered["corner"] == covered["middle"] == "sheet", covered

    # The heading and the sheet itself; not the paragraph behind it.
    expect(hints).to_have_count(2)


def test_a_boxless_target_is_read_where_it_paints(browser, serve):
    """A `display: contents` member's bounds are the union of its children's, so the
    middle of those bounds can be the gap between two of them, where the page behind
    answers. Asking there would cost the member its letter while the user is looking
    straight at it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "a boxless target",
                """
<h1 id="head">Split</h1>
<div id="split" style="display: contents">
  <p id="one">First run of the split target.</p>
  <p id="two">Second run of the split target.</p>
</div>
""",
                # The split runs need ordinary block flow. In the column grid,
                # they become separate items and the wrapper can sort before the heading.
                layout=None,
                head="""<style>
  #one, #two { margin: 0; }
  #two { margin-top: 14rem; }
</style>""",
            )
        ),
    )
    page.keyboard.press("s")
    hints = page.locator(".lf-target-picker-hint")
    expect(hints.first).to_be_visible()

    # The premise: the wrapper paints nothing of its own between its two runs.
    assert (
        page.evaluate(
            """() => {
              const runs = ['#one', '#two'].map(
                id => document.querySelector(id).getBoundingClientRect());
              const middle = (runs[0].top + runs[1].bottom) / 2;
              const at = document.elementFromPoint(runs[0].left + 1, middle);
              return document.querySelector('#split').contains(at);
            }"""
        )
        is False
    )

    # The heading, the wrapper, and each of its two runs.
    expect(hints).to_have_count(4)
    page.keyboard.press("Tab")
    expect(page.locator(".lf-live")).to_contain_text("heading: Split")
    page.keyboard.press("Tab")
    # The one target whose words span both runs is the wrapper, not either run.
    expect(page.locator(".lf-live")).to_contain_text(
        "div: First run of the split target. Second run"
    )


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
    page = open_page(browser, serve(html))
    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint")).to_have_count(3)

    page.evaluate(
        """() => {
          const originalRect = Element.prototype.getBoundingClientRect;
          window.lfHintScrollReads = {hiddenRectReads: 0};
          Element.prototype.getBoundingClientRect = function (...args) {
            if (this.id.startsWith('hidden-'))
              window.lfHintScrollReads.hiddenRectReads += 1;
            return originalRect.apply(this, args);
          };
          window.lfStopCounting = () => {
            Element.prototype.getBoundingClientRect = originalRect;
          };
          document.scrollingElement.scrollTo({top: 600, behavior: 'smooth'});
        }"""
    )
    # The membership refresh runs in the passes after the scroll rests, so the count is
    # read once those have run, not at the scroll's end.
    page.wait_for_function("() => scrollY > 0")
    scroll_settled(page)
    rendered(page)
    reads = page.evaluate(
        "() => { lfStopCounting(); return window.lfHintScrollReads; }"
    )

    assert reads["hiddenRectReads"] == 0, reads


def test_cancelling_page_search_restores_the_control_that_opened_it(browser, serve):
    """Direct search is one layer. A repeated slash cannot change that when focus has
    left its box: Escape still closes search and returns to the original control."""
    html = leaf_page(
        "selection focus",
        '<button id="opener">Starting control</button><p>A passage to select.</p>',
    )
    page = open_page(browser, serve(html))
    opener = page.locator("#opener")
    opener.focus()

    page.keyboard.press("/")
    expect(page.get_by_role("searchbox", name="Search page text")).to_be_focused()
    page.locator("main p").click()
    page.keyboard.press("/")
    page.keyboard.press("Escape")
    expect(opener).to_be_focused()


def test_cancelling_selection_restores_an_opener_inside_shadow_dom(browser, serve):
    """The exact focused control opens the mode, even across a shadow boundary. Closing
    both selection layers returns to that control rather than only to its host."""
    html = leaf_page(
        "shadow selection focus",
        '<div id="opener"></div><p>A passage to select.</p>',
    )
    page = open_page(browser, serve(html))
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
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    assert (
        page.evaluate(
            "() => document.querySelector('#opener').shadowRoot.activeElement?.id"
        )
        == "inside"
    )


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
    page = open_page(browser, serve(html))
    page.evaluate(
        "() => { document.scrollingElement.scrollTop = document.scrollingElement.scrollHeight; }"
    )
    page.wait_for_function("() => document.scrollingElement.scrollTop > 500")

    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint")).to_have_count(0)
    page.keyboard.press("/")
    page.keyboard.type("phrase only appears")
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")
    expect(page.locator(".lf-page-search-match")).not_to_have_count(0)

    page.keyboard.press("Enter")
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    assert page.evaluate("() => getSelection().toString()") == "phrase only appears"
    assert pending_text(page) == "phrase only appears"


def test_a_partly_clipped_passage_keeps_its_hint_in_sight(browser, serve):
    """A line beginning above the window's head can still be visibly selectable below
    it, and one running under the panel's row above that. Its hint sits at the clipped
    edge instead of putting half its key out of sight or under chrome."""
    html = leaf_page(
        "top-edge target",
        """
<div style="height: 300px" aria-hidden="true"></div>
<p id="edge">This passage begins beyond the window's edge.</p>
<div style="height: 1200px" aria-hidden="true"></div>
""",
    )
    page = open_page(browser, serve(html))
    page.evaluate(
        """() => {
          const text = document.querySelector('#edge').firstChild;
          const range = document.createRange();
          range.selectNodeContents(text);
          document.scrollingElement.scrollTop += range.getBoundingClientRect().top + 5;
        }"""
    )
    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint")).to_have_count(1)

    hint_top = page.locator(".lf-target-picker-hint").bounding_box()["y"]
    assert hint_top >= 0, hint_top

    page.keyboard.press("Escape")
    page.evaluate(
        """() => {
          const text = document.querySelector('#edge').firstChild;
          const range = document.createRange();
          range.selectNodeContents(text);
          const row = document.querySelector('.lf-fp-row').getBoundingClientRect();
          document.scrollingElement.scrollTop += range.getBoundingClientRect().top - (row.top - 5);
        }"""
    )
    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint")).to_have_count(1)
    geometry = page.evaluate(
        """() => ({
          rowTop: document.querySelector('.lf-fp-row').getBoundingClientRect().top,
          hintBottom: document.querySelector('.lf-target-picker-hint').getBoundingClientRect().bottom,
        })"""
    )
    assert geometry["hintBottom"] <= geometry["rowTop"], geometry


def test_the_panel_only_hides_targets_in_the_lane_it_paints(browser, serve):
    """Fixed nested targets standing under the panel's row stay reachable: the selector
    spreads both hints inside the viewport but outside the row. A scalar boundary at the
    band's top dropped both targets, while a center left on their covered part put
    replacement hints on the band or below the viewport."""
    html = leaf_page(
        "target beside the panel's row",
        """
<section id="right-edge"
  style="position: fixed; left: 250px; bottom: 35px; width: 500px; padding-bottom: 1px">
  <p id="edge-copy" style="margin: 0">
    This target crosses the edge of the keyboard legend into open space.
  </p>
</section>
""",
    )
    page = open_page(browser, serve(html))
    resized(page, 1200, 800)
    page.keyboard.press("s")

    expect(page.locator(".lf-target-picker-hint")).to_have_count(2)
    target, line, hints = page.evaluate(
        """() => [
          document.querySelector('#right-edge').getBoundingClientRect().toJSON(),
          document.querySelector('.lf-fp-row').getBoundingClientRect().toJSON(),
          [...document.querySelectorAll('.lf-target-picker-hint')].map(
            hint => hint.getBoundingClientRect().toJSON()
          ),
        ]"""
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
    # The search box stands centred above the panel, over the middle of the target's
    # first line, and a match it covers takes no mark. Its opening words stand left of
    # both the box and the row whatever the fonts' widths, as "crosses the edge" did
    # not on Linux, where they went under the box.
    page.keyboard.type("This target")
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")
    expect(page.locator(".lf-page-search-match")).to_have_count(1)
    line, mark = page.evaluate(
        """() => ['.lf-fp-row', '.lf-page-search-match'].map(
          selector => document.querySelector(selector).getBoundingClientRect().toJSON()
        )"""
    )
    assert not (
        mark["left"] < line["right"]
        and line["left"] < mark["right"]
        and mark["top"] < line["bottom"]
        and line["top"] < mark["bottom"]
    ), (mark, line)


def test_a_partly_clipped_atomic_element_keeps_its_hint_in_sight(browser, serve):
    """Atomic visuals use element geometry rather than text ranges, but obey the same
    upper boundary, the window's head, when only their lower edge is exposed."""
    html = leaf_page(
        "top-edge visual",
        """
<div style="height: 300px" aria-hidden="true"></div>
<figure id="edge-visual"><svg viewBox="0 0 120 60" width="120" height="60"
  role="img" aria-label="Edge visual"><rect width="120" height="60"></rect></svg></figure>
<div style="height: 1200px" aria-hidden="true"></div>
""",
    )
    page = open_page(browser, serve(html))
    page.evaluate(
        """() => {
          const visual = document.querySelector('#edge-visual').getBoundingClientRect();
          document.scrollingElement.scrollTop += visual.top + 8;
        }"""
    )
    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint")).to_have_count(1)

    hint_top = page.locator(".lf-target-picker-hint").bounding_box()["y"]
    assert hint_top >= 0, hint_top


def test_page_search_skips_hidden_words_but_reaches_disclosures(browser, serve):
    """Search counts rendered words and words its travel can reveal, not hidden data."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "searchable words",
                """<p>needle visible</p>
<div style="display:none"><pre>needle source data</pre></div>
<p style="visibility:hidden">needle invisible</p>
<div style="display:contents"><p>needle contents</p></div>
<section><lf-tabs id="views"><lf-tab id="shown" label="Shown"><p>Shown panel</p></lf-tab>
<lf-tab id="fold" label="Folded"><p>needle folded</p></lf-tab></lf-tabs></section>
<details id="details"><summary>Evidence</summary><p>needle disclosed</p></details>
<p hidden>copper</p><p>copper copper</p>""",
            )
        ),
    )
    page.keyboard.press("/")
    search = page.get_by_role("searchbox", name="Search page text")
    search.fill("needle")
    status = page.locator(".lf-page-search-status")
    expect(status).to_have_text("1 of 4")
    search.press("Tab")
    expect(status).to_have_text("2 of 4")
    search.press("Tab")
    expect(status).to_have_text("3 of 4")
    expect(page.locator("#fold")).not_to_have_attribute("hidden")
    expect(page.locator(".lf-page-search-match")).not_to_have_count(0)
    search.press("Tab")
    expect(status).to_have_text("4 of 4")
    expect(page.locator("#details")).to_have_attribute("open", "")
    search.fill("copper copper")
    expect(status).to_have_text("1 of 1")
