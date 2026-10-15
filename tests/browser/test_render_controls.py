"""Control stability, browser shell, accessibility, and ring tests."""

import io
import os
import re
from datetime import datetime, timedelta

import pytest
from browser_sources import browser_function
from click.testing import CliRunner
from interact_support import (
    append_carried_log_record,
    append_command,
    declare_work,
    element_declaration,
    end_work,
    record_claim,
    response_reference,
    working,
)
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import leases as leases_model
from leaf import service as service_model
from leaf import state as cleanup_model
from leaf.render_checks import rendered, wait_until_ready
from leaf.schema import ELEMENT_ID
from PIL import Image
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_cases_interaction import (
    SEATED_ASK_LAYER,
    SEATED_ASK_WIDGETS,
    SUGGESTION_PAGE,
    live_url,
    panel_comment,
)
from render_cases_layout import (
    BANNER_WATCH,
    DEFINE_BOXES,
    NEIGHBOUR,
    NEIGHBOURHOOD,
    ONE_ASK,
    PANEL_DIFF_MARKUP,
    SHOT_SRC,
    UNBREAKABLE_PAGE,
    WIDE_DIFF_PAGE,
    banner_control,
    displaced,
    mark_edges,
    page_at_rest,
    ring_faults,
    rings_drawn,
    serious_axe_violations,
    standing_ring,
    toggle_queue,
    token_colour,
)
from render_cases_navigation import (
    ADDRESSED_PAGE,
    DIFF_PAGE,
    actions,
    go_to_address,
)
from render_cases_widgets import (
    SCROLLED,
    WIDE_DIAGRAM_PAGE,
)
from render_harness import (
    CORPUS_SOURCES,
    EXAMPLES,
    FEATURE_GALLERY,
    LONG_PAGE,
    RELEASE_FOCUS,
    REPLAYED_PAGE,
    REPLY_HOST_PAGE,
    ROOT,
    SHELL_BOX,
    Traffic,
    _traffic,
    accessible_expanded,
    any_owner_entry,
    any_suggestion_control,
    expect_asks_answered,
    expect_comment_notes,
    held_frames,
    holding,
    leaf_page,
    nudge,
    open_page,
    open_versions,
    page_comment,
    panel_settled,
    refuse,
    resized,
    root_overflow,
    round_trip,
    scroll_settled,
    select,
    sending,
    shown,
    stamp_page,
    take_browser_errors,
    told,
    undo,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("touch", [False, True])
def test_native_disclosure_inherits_the_offered_control_target(browser, serve, touch):
    """A native disclosure gets the same press target without a widget-specific rule."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=touch
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Native disclosure",
                """<h1>Comparison</h1>
<details id="comparison"><p>Inspection controls.</p></details>
<details id="wrapped-comparison" style="width: 160px"><p>Wrapped controls.</p></details>
<script type="module">
import {offer} from '/runtime/widget-api.js';
const summary = offer('summary', '', 'Inspect comparison');
summary.id = 'inspect';
document.querySelector('#comparison').prepend(summary);
const wrapped = offer('summary', '', 'A long disclosure label that wraps across several lines');
wrapped.id = 'wrapped-inspect';
document.querySelector('#wrapped-comparison').prepend(wrapped);
</script>""",
            )
        ),
        context=context,
    )
    for control_id, detail_id in (
        ("inspect", "comparison"),
        ("wrapped-inspect", "wrapped-comparison"),
    ):
        control = page.locator(f"#{control_id}")
        before = control.bounding_box()
        floor = 44 if touch else 24
        assert min(before["width"], before["height"]) >= floor - 0.5, before
        label_room = control.evaluate(
            """node => {
              const range = document.createRange(); range.selectNodeContents(node);
              const box = node.getBoundingClientRect(), text = range.getBoundingClientRect();
              return {above: text.top-box.top, below: box.bottom-text.bottom,
                      display: getComputedStyle(node).display};
            }"""
        )
        assert abs(label_room["above"] - label_room["below"]) <= 2, label_room
        assert label_room["display"] == "list-item", label_room
        if touch:
            control.tap()
        else:
            control.click()
        expect(page.locator(f"#{detail_id}")).to_have_attribute("open", "")
        assert control.bounding_box() == before
        control.press("Space")
        expect(page.locator(f"#{detail_id}")).not_to_have_attribute("open", "")
        assert control.bounding_box() == before
        control.press("Enter")
        expect(page.locator(f"#{detail_id}")).to_have_attribute("open", "")
        assert control.bounding_box() == before


def test_offered_native_targets_keep_their_navigation_meaning(browser, serve):
    """An offered disclosure or link keeps its native Go-to arrival, not a generic press."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Native routes",
                """<h1>Comparison</h1>
<details id="comparison"><p>Inspection controls.</p></details>
<p id="destination">Destination evidence.</p>
<script type="module">
import {offer} from '/runtime/widget-api.js';
const summary = offer('summary', '', 'Inspect comparison');
summary.id = 'inspect';
document.querySelector('#comparison').prepend(summary);
const link = offer('a', '', 'Evidence');
link.id = 'evidence';
link.href = '#destination';
document.querySelector('main').append(link);
</script>""",
            )
        ),
    )
    summary = page.locator("#inspect")
    go_to_address(page, "Fold", "inspect")
    expect(summary).to_be_focused()
    expect(page.locator("#comparison")).to_have_attribute("open", "")
    page.keyboard.press("Enter")
    expect(page.locator("#comparison")).not_to_have_attribute("open", "")
    go_to_address(page, "Link", "evidence")
    expect(page).to_have_url(re.compile(r"#destination$"))


@pytest.mark.parametrize("width", [1440])
def test_merge_film_keyboard_routes_hold_steps_and_respect_the_scrubber(
    browser, serve, width
):
    source = next(path for path in EXAMPLES if path.name == "wt-merge.html")
    page = open_page(browser, serve(source))
    resized(page, width, 900)
    page.clock.install(time=0)
    page.clock.pause_at(1)
    play = page.locator(".film-play")
    page.locator("#step-rebase button").click()
    play.click()
    play.press("ArrowLeft")
    expect(page.locator("#step-squash")).to_have_attribute("data-now", "")
    expect(play).to_have_text("Play")
    held = page.locator(".film-scrub").input_value()
    page.locator("#step-squash button").click()
    assert page.locator(".film-scrub").input_value() == held
    play.press("ArrowRight")
    expect(page.locator("#step-rebase")).to_have_attribute("data-now", "")
    expect(play).to_have_text("Play")
    play.click()
    page.locator(".film-scrub").press("Home")
    expect(page.locator(".film-scrub")).to_have_value("0")
    expect(play).to_have_text("Play")


@pytest.mark.parametrize("width", [390])
def test_merge_film_inspection_and_step_availability_follow_the_run(
    browser, serve, width
):
    source = next(path for path in EXAMPLES if path.name == "wt-merge.html")
    page = open_page(browser, serve(source))
    resized(page, width, 900)
    inspect = page.get_by_role("button", name="Inspect next element")
    inspect.click()
    expect(page.locator(".film-picked")).to_have_count(1)
    if width < 560:
        page.locator(".film-settings summary").click()
    page.get_by_label("--no-remove", exact=True).check()
    for _ in range(8):
        inspect.click()
    expect(page.locator(".film-inspect strong")).to_have_text("ref feature")
    expect(page.locator(".film-inspect span")).to_contain_text("Kept")
    if width < 560:
        page.locator(".film-settings summary").click()
    page.get_by_label("--no-squash", exact=True).check()
    page.get_by_label("--no-rebase", exact=True).check()
    page.locator("#step-end button").click()
    expect(page.locator(".film-caption")).to_contain_text("Rebase refused")
    expect(page.locator("#step-merge button")).to_be_disabled()
    if width < 560:
        page.locator(".film-settings summary").click()
    page.get_by_label("--no-rebase", exact=True).uncheck()
    expect(page.locator("#step-merge button")).to_be_enabled()


# The phone's terminal; the journey then reflows to the desk and back.
@pytest.mark.parametrize("width", [390])
def test_merge_film_terminal_seeks_to_the_result_it_reports(browser, serve, width):
    source = next(path for path in EXAMPLES if path.name == "wt-merge.html")
    page = open_page(browser, serve(source))
    resized(page, width, 900)
    page.locator("#step-end button").click()
    if width < 560:
        page.locator(".film-phone-terminal summary").click()
    line = page.get_by_role("button", name="✓ Squashed @ cb12e61", exact=True)
    line.focus()
    line.press("Enter")
    expect(line).to_be_visible()
    expect(line).to_be_focused()
    expect(page.locator("#step-squash")).to_have_attribute("data-now", "")
    if width < 560:
        expect(page.locator(".film-phone-latest")).to_have_text("✓ Squashed @ cb12e61")
        expect(page.locator(".film-phone-tree").last).to_contain_text("clean")
    expect(page.locator('[data-label="commit cb12e61"]:visible')).to_be_visible()
    expect(page.locator(".film-play")).to_have_text("Play")

    # Replacing the composition preserves the user's place, not only film time.
    position = page.locator(".film-scrub").input_value()
    for target in (1440 if width == 390 else 390, width):
        resized(page, target, 900)
        expect(line).to_be_focused()
        box = line.bounding_box()
        assert box["y"] >= 0 and box["y"] + box["height"] <= 900
        assert line.evaluate("""element => {
            const box = element.getBoundingClientRect();
            return element.contains(document.elementFromPoint(
                box.x + box.width / 2, box.y + box.height / 2));
        }""")
        line.press("Space")
        expect(line).to_be_focused()
        assert page.locator(".film-scrub").input_value() == position

    resized(page, 390, 900)
    page.locator(".film-settings summary").focus()
    resized(page, 1440, 900)
    flag = page.locator("input[name=film-flag-moved]")
    expect(flag).to_be_focused()
    resized(page, 390, 900)
    expect(flag).to_be_focused()
    box = flag.bounding_box()
    assert box["y"] >= 0 and box["y"] + box["height"] <= 900
    expect(page.locator(".film-settings")).to_have_attribute("open", "")
    page.locator(".film-next").focus()
    resized(page, 1440, 900)
    expect(page.locator(".film-play")).to_be_focused()


def test_merge_film_steps_have_a_keyboard_route(browser, serve):
    source = next(path for path in EXAMPLES if path.name == "wt-merge.html")
    page = open_page(browser, serve(source))
    page.locator("#merge-film").evaluate("film => film.seek(1e9)")

    for _ in range(100):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement?.closest('li')?.id") == "step-setup":
            break
    assert page.evaluate("document.activeElement?.closest('li')?.id") == "step-setup"
    expect(page.locator("#step-setup button")).to_be_focused()
    expect(page.locator("#step-setup button:focus-visible")).to_have_count(1)

    for key in ("Space", "Enter"):
        page.locator("#merge-film").evaluate("film => film.seek(1e9)")
        page.keyboard.press(key)
        expect(page.locator("#step-setup")).to_have_attribute("data-now", "")
        expect(page.locator(".film-play")).to_have_text("Play")
        expect(
            page.locator('.film-stage > svg [data-label="commit b72c9e4"]')
        ).to_be_visible()

    # A step selected during playback holds its outcome so the explanation stays open.
    page.locator(".film-play").click()
    expect(page.locator(".film-play")).to_have_text("Pause")
    page.locator("#step-rebase button").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#step-rebase")).to_have_attribute("data-now", "")
    expect(page.locator(".film-play")).to_have_text("Play")
    expect(
        page.locator('.film-stage > svg [data-label="commit f62bab1"]')
    ).to_be_visible()


def test_merge_film_phone_holds_readable_outcomes_and_preserves_them_on_reflow(
    browser, serve
):
    """The same merge story fits a phone without shrinking its labels or losing refs."""
    source = next(path for path in EXAMPLES if path.name == "wt-merge.html")
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(source), context=context)
    film = page.locator("#merge-film")
    expect(film).to_have_attribute("data-phone", "")
    labels = page.locator(".film-phone svg text")
    sizes = labels.evaluate_all(
        "nodes => nodes.filter(n => n.textContent !== 'fork').map(n => "
        "parseFloat(getComputedStyle(n).fontSize) * n.getScreenCTM().a)"
    )
    assert min(sizes) >= 14
    for _ in range(5):
        page.get_by_role("button", name="Next step", exact=True).tap()
    expect(page.locator("#step-merge")).to_have_attribute("data-now", "")
    # Main and feature now name the same commit; both labels must remain legible.
    refs = page.locator('.film-phone [data-label^="ref "]')
    visible = refs.evaluate_all(
        "nodes => nodes.filter(n=>Number(n.getAttribute('opacity')) >= .3)"
        ".map(n=>({label:n.dataset.label, top:n.getBoundingClientRect().top}))"
    )
    assert {ref["label"] for ref in visible} == {"ref main", "ref feature"}
    assert abs(visible[0]["top"] - visible[1]["top"]) >= 20
    page.locator(".film-settings summary").tap()
    page.locator("input[name=film-flag-ff]").tap()
    expect(page.locator("#step-merge")).to_have_attribute("data-now", "")
    expect(page.locator('.film-phone [data-label="commit cc2c26f"]')).to_be_visible()
    expect(page.locator(".film-phone-latest")).to_contain_text("Merged to main")
    page.locator(".film-settings summary").tap()

    position = page.locator(".film-scrub").input_value()
    resized(page, 1440, 900)
    expect(film).not_to_have_attribute("data-phone", "")
    assert page.locator(".film-scrub").input_value() == position
    expect(page.locator("#step-merge")).to_have_attribute("data-now", "")
    resized(page, 320, 844)
    expect(film).to_have_attribute("data-phone", "")
    assert page.locator(".film-scrub").input_value() == position
    # The focused settings control remains exposed across the round trip.
    expect(page.locator(".film-settings")).to_have_attribute("open", "")
    page.locator("input[name=film-flag-hookFails]").tap()
    page.locator(".film-scrub").focus()
    page.keyboard.press("End")
    expect(page.locator("#step-premerge")).to_have_attribute("data-state", "fail")
    expect(page.locator('.film-phone [data-label="commit e90b4f6"]')).to_be_visible()
    expect(page.locator('.film-phone-tree[data-gone="true"]')).to_have_count(0)
    page.locator("#step-setup button").tap()
    scroll_settled(page)
    assert film.bounding_box()["y"] >= 0
    expect(page.locator(".film-settings")).not_to_have_attribute("open", "")
    expect(page.locator('.film-phone-tree[data-gone="true"]')).to_have_count(0)
    expect(page.locator('.film-phone [data-label="commit b72c9e4"]')).to_be_visible()
    expect(page.locator(".film-play")).to_have_text("Play")


KEYBOARD_HINT_REGISTRY = {
    "lf-keyboard-probe": {
        "description": "Exercises declared keyboard commands and their controls.",
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": f"^{ELEMENT_ID}$"},
            "asks": {"type": "boolean"},
            "restated": {"type": "boolean"},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
        "x-state": SEATED_ASK_LAYER["lf-verdict"]["x-state"],
        "x-awaits": SEATED_ASK_LAYER["lf-verdict"]["x-awaits"],
    }
}

KEYBOARD_HINT_MODULE = """\
import {commandScope, commands, keeps, keepsText, offer, paintKeys} from '/runtime/widget-api.js';

customElements.define('lf-keyboard-probe', class extends HTMLElement {
  connectedCallback() {
    this.count = 0;
    this.allowed = true;
    this.disabled = false;
    this.ariaRefused = false;
    this.result = offer('output', '', '0');
    const editor = offer('input');
    editor.setAttribute('aria-label', 'Practice note');
    this.makeControl();
    this.append(this.seat, editor, this.result);
    const disable = offer('button', '', 'Toggle disabled');
    disable.onclick = () => {
      this.disabled = !this.disabled;
      paintKeys();
    };
    const ariaDisable = offer('button', '', 'Toggle ARIA disabled');
    ariaDisable.onclick = () => {
      this.ariaRefused = !this.ariaRefused;
      paintKeys();
    };
    const guard = offer('button', '', 'Toggle availability');
    guard.onclick = () => { this.allowed = !this.allowed; paintKeys(); };
    const replace = offer('button', '', 'Replace action control');
    replace.onclick = () => {
      const prior = this.seat;
      this.makeControl();
      prior.replaceWith(this.seat);
      paintKeys();
    };
    const quiet = offer('button', '', 'Quiet action');
    this.append(disable, ariaDisable, guard, replace, quiet);
    const scope = commandScope('In the command probe', [
      {
        id: 'probe.apply', keys: ['x'], contextKeys: ['1'],
        control: () => this.control, bindingBadge: () => this.badge,
        title: 'Apply the operation', line: 'apply',
        when: () => this.allowed && !this.disabled && !this.ariaRefused,
        run: () => keepsText(this.result, String(++this.count)),
      },
      {
        id: 'probe.quiet', keys: ['q'], control: quiet,
        title: 'Activate without an inline hint', line: 'quiet action',
        run: () => keepsText(quiet, 'Quiet action applied'),
      },
    ]);
    commands(this, scope);
    commands(editor, scope);
    commands(this.closest('main'), 'Outside the widget', [{
      id: 'probe.outer', title: 'Outer digit', keys: ['1'],
      run: () => keepsText(this.result, 'Outer applied'),
    }]);
  }

  makeControl() {
    this.control = offer('button', '', 'Apply');
    this.badge = offer('kbd', 'lf-key-badge');
    this.badge.setAttribute('aria-hidden', 'true');
    this.seat = offer('span');
    this.seat.style.cssText = 'display: inline-block; position: relative; margin-left: 24px';
    this.badge.style.cssText = 'right: calc(100% + 4px); top: 0';
    this.seat.append(this.badge, this.control);
  }
});
"""


@pytest.mark.parametrize("hint_seat", ["widget", "corner"])
def test_widget_owned_inline_hints_follow_reachable_commands(browser, serve, hint_seat):
    """A package command needs no Ask role to expose its working keyboard route.

    The same scope stands on the widget and its question context. Focus, native text
    entry, control availability, and replacement change dispatch and the inline hint
    together; forwarding never creates a second badge for the same action.
    """
    page = open_page(
        browser,
        serve(
            leaf_page(
                "command hints",
                '<h1>Command hints</h1><button id="outside">Outside the widget</button>'
                '<lf-ask id="question"><h2>Apply the operation?</h2>'
                '<lf-keyboard-probe id="probe" asks></lf-keyboard-probe></lf-ask>',
            ),
            layer_registry=KEYBOARD_HINT_REGISTRY,
            layer_widgets={
                "lf-keyboard-probe.js": (
                    KEYBOARD_HINT_MODULE
                    if hint_seat == "widget"
                    else KEYBOARD_HINT_MODULE.replace(
                        "bindingBadge: () => this.badge", "bindingBadge: null"
                    )
                )
            },
        ),
    )
    widget = page.locator("#probe")
    badge = (
        widget.locator("kbd")
        if hint_seat == "widget"
        else page.locator(".lf-command-binding-badges .lf-command-binding-badge")
    )
    active_hints = page.locator(
        "[data-lf-binding-badge], .lf-command-binding-badges .lf-command-binding-badge"
    )
    result = widget.locator("output")
    action = widget.get_by_role("button", name="Apply", exact=True)

    # A badge reveal must leave both the labeled control and its neighbours fixed.
    def control_boxes():
        return widget.locator("button, input").evaluate_all(
            "nodes => nodes.slice(0, 2).map(node => { const b = node.getBoundingClientRect(); "
            "return [b.x, b.y, b.width, b.height]; })"
        )

    # No scope stands while focus is outside, so an empty seat advertises nothing.
    page.locator("#outside").focus()
    rendered(page)
    expect(badge).to_be_hidden()
    unfocused_boxes = control_boxes()
    page.keyboard.press("x")
    rendered(page)
    expect(result).to_have_text("0")

    # The question context forwards the widget's declaration without an Ask allocator.
    page.keyboard.press("m")
    expect(page.locator("#question")).to_be_focused()
    expect(badge).to_be_visible()
    expect(badge).to_have_text("1")
    expect(active_hints).to_have_count(1)
    assert control_boxes() == unfocused_boxes
    page.keyboard.press("1")
    expect(result).to_have_text("1")

    page.keyboard.press("Tab")
    expect(action).to_be_focused()
    expect(badge).to_be_visible()
    assert control_boxes() == unfocused_boxes
    expect(active_hints).to_have_count(1)
    page.keyboard.press("x")
    expect(result).to_have_text("2")

    # Even an exact editor scope leaves its contextual digit to native editing.
    # Its ordinary exact-control x command retains priority.
    page.keyboard.press("Tab")
    editor = widget.get_by_role("textbox", name="Practice note")
    expect(editor).to_be_focused()
    rendered(page)
    expect(badge).to_have_text("x")
    assert control_boxes() == unfocused_boxes
    page.keyboard.type("1")
    expect(editor).to_have_value("1")
    expect(result).to_have_text("2")
    page.keyboard.press("x")
    expect(result).to_have_text("3")
    expect(editor).to_have_value("1")

    widget.get_by_role("button", name="Toggle disabled").click()
    rendered(page)
    expect(action).to_be_disabled()
    expect(badge).to_be_hidden()
    page.keyboard.press("1")
    rendered(page)
    expect(result).to_have_text("3")
    widget.get_by_role("button", name="Toggle disabled").click()
    expect(badge).to_be_visible()

    # ARIA-disabled controls also suppress the keyboard callback, not just clicks.
    widget.get_by_role("button", name="Toggle ARIA disabled").click()
    rendered(page)
    expect(badge).to_be_hidden()
    page.keyboard.press("1")
    rendered(page)
    expect(result).to_have_text("3")
    widget.get_by_role("button", name="Toggle ARIA disabled").click()
    expect(badge).to_be_visible()

    widget.get_by_role("button", name="Toggle availability").click()
    rendered(page)
    expect(badge).to_be_hidden()
    page.keyboard.press("1")
    rendered(page)
    expect(result).to_have_text("3")
    widget.get_by_role("button", name="Toggle availability").click()
    expect(badge).to_be_visible()

    widget.get_by_role("button", name="Replace action control").click()
    expect(badge).to_be_visible()
    expect(badge).to_have_text("1")
    expect(active_hints).to_have_count(1)
    page.keyboard.press("1")
    expect(result).to_have_text("4")
    # A control whose command omitted bindingBadge has no hint, but its key works.
    page.keyboard.press("q")
    expect(widget.get_by_role("button", name="Quiet action applied")).to_be_visible()
    expect(active_hints).to_have_count(1)

    page.locator("#outside").focus()
    rendered(page)
    expect(badge).to_be_hidden()
    page.keyboard.press("x")
    rendered(page)
    expect(result).to_have_text("4")

    assert control_boxes() == unfocused_boxes
    if hint_seat == "widget":
        expect(widget.locator("kbd")).to_have_class(re.compile(r"\blf-binding-seat\b"))
        assert (
            widget.locator("kbd").evaluate("badge => getComputedStyle(badge).position")
            == "absolute"
        )
        expect(action.locator("kbd")).to_have_count(0)

    # Native pointer, Enter and Space use the command's callback once each. The
    # owner's private availability also disables a real pointer press, then restores
    # the same retained button without adding another activation listener.
    box = action.bounding_box()
    page.mouse.click(box["x"] + 1, box["y"] + box["height"] / 2)
    expect(result).to_have_text("5")
    rendered(page)
    assert control_boxes() == unfocused_boxes
    page.keyboard.press("Enter")
    expect(result).to_have_text("6")
    page.keyboard.press("Space")
    expect(result).to_have_text("7")
    widget.get_by_role("button", name="Toggle availability").click()
    expect(action).to_be_disabled()
    box = action.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    expect(result).to_have_text("7")
    widget.get_by_role("button", name="Toggle availability").click()
    page.locator("#outside").focus()
    rendered(page)
    assert control_boxes() == unfocused_boxes
    page.mouse.click(box["x"] + box["width"] - 1, box["y"] + box["height"] / 2)
    expect(result).to_have_text("8")


@pytest.mark.parametrize("annotation_mode", ["overlay", "page"])
def test_widget_context_keys_work_without_an_ask(browser, serve, annotation_mode):
    """Widget aliases and inline hints work with either annotation presentation owner."""
    source = leaf_page(
        "standalone widget commands",
        '<h1>Standalone command</h1><button id="outside">Outside</button>'
        '<lf-keyboard-probe id="probe"></lf-keyboard-probe>',
    )
    if annotation_mode == "page":
        source = source.replace("<body>", '<body data-annotations="page">')
    page = open_page(
        browser,
        serve(
            source,
            layer_registry=KEYBOARD_HINT_REGISTRY,
            layer_widgets={"lf-keyboard-probe.js": KEYBOARD_HINT_MODULE},
        ),
    )
    expect(page.locator(".lf-margin-projection")).to_have_count(
        int(annotation_mode == "overlay")
    )
    widget = page.locator("#probe")
    result = widget.locator("output")
    badge = widget.locator("kbd")
    page.locator("#outside").focus()
    expect(page.locator("#outside")).to_be_focused()
    rendered(page)
    expect(badge).to_be_hidden()
    page.keyboard.press("1")
    expect(result).to_have_text("Outer applied")
    page.keyboard.press("Tab")
    expect(widget.get_by_role("button", name="Apply", exact=True)).to_be_focused()
    page.keyboard.press("1")
    expect(result).to_have_text("1")
    expect(badge).to_be_visible()
    expect(badge).to_have_text("1")
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(
        page.locator('.lf-command-reference-command[data-lf-command="probe.outer"]')
    ).to_have_attribute("data-lf-available", "false")
    page.keyboard.press("Escape")
    page.keyboard.press("Tab")
    editor = widget.get_by_role("textbox", name="Practice note")
    expect(editor).to_be_focused()
    page.keyboard.type("1")
    expect(editor).to_have_value("1")
    expect(result).to_have_text("1")
    expect(badge).to_have_text("x")
    page.locator("#outside").focus()
    rendered(page)
    expect(badge).to_be_hidden()


KEYBOARD_ROUTE_MODULE = """\
import {commands, keepsText, offer} from '/runtime/widget-api.js';

customElements.define('lf-keyboard-probe', class extends HTMLElement {
  connectedCallback() {
    const first = offer('button', '', 'First action');
    const second = offer('button', '', 'Second action');
    const result = offer('output', '', 'No action');
    const firstHint = offer('kbd', 'lf-key-badge');
    const secondHint = offer('kbd', 'lf-key-badge');
    for (const badge of [firstHint, secondHint]) badge.setAttribute('aria-hidden', 'true');
    const firstSeat = offer('span');
    const secondSeat = offer('span');
    for (const seat of [firstSeat, secondSeat])
      seat.style.cssText = 'display: inline-block; position: relative; margin-left: 24px';
    for (const badge of [firstHint, secondHint])
      badge.style.cssText = 'right: calc(100% + 4px); top: 0';
    firstSeat.append(firstHint, first);
    secondSeat.append(secondHint, second);
    const firstUnavailable = DISABLE_FIRST
    const apply = (binding) => keepsText(result, binding === '1' ? 'First applied' : 'Second applied');
    this.append(firstSeat, secondSeat, result);
    commands(this, 'In parameterized actions', [{
      id: 'probe.apply', keys: ['1', '2'], title: 'Apply an action', line: 'apply',
      routes: [
        {id: 'probe.first', binding: '1', control: first, when: () => !firstUnavailable,
         bindingBadge: firstHint, title: 'Apply the first action'},
        {id: 'probe.second', binding: '2', control: second,
         bindingBadge: secondHint, title: 'Apply the second action'},
      ],
      run: apply,
    }]);
    commands(this.closest('section'), 'Outside parameterized actions', [{
      id: 'probe.outer', keys: ['1'], title: 'Apply the outer action', line: 'outer action',
      run: () => keepsText(result, 'Outer applied'),
    }]);
  }
});
"""


@pytest.mark.parametrize("disabled", ["native", "aria"])
def test_disabled_command_route_keeps_its_key_and_enabled_sibling(
    browser, serve, disabled
):
    """A disabled route cannot invoke its row's handler or expose an outer meaning.

    The sibling route in the same row remains live, with its working inline hint. The
    row's handler directly applies the operation, so a native button's click refusal
    cannot mask a missing check at the keyboard invocation boundary.
    """
    module = KEYBOARD_ROUTE_MODULE.replace(
        "DISABLE_FIRST",
        "true;"
        if disabled == "native"
        else "true; first.setAttribute('aria-disabled', 'true');",
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "disabled command routes",
                "<h1>Command routes</h1><section><h2>Apply an action</h2>"
                '<lf-keyboard-probe id="probe"></lf-keyboard-probe></section>',
            ),
            layer_registry=KEYBOARD_HINT_REGISTRY,
            layer_widgets={"lf-keyboard-probe.js": module},
        ),
    )
    first = page.get_by_role("button", name="First action")
    second = page.get_by_role("button", name="Second action")
    result = page.locator("#probe output")

    second.focus()
    rendered(page)
    expect(first).to_be_disabled()
    expect(page.locator("#probe kbd").nth(0)).to_be_hidden()
    expect(page.locator("#probe kbd").nth(1)).to_be_visible()
    expect(page.locator("#probe kbd").nth(1)).to_have_text("2")
    expect(page.locator("#probe")).to_have_attribute("aria-keyshortcuts", "2")
    offered = page.locator(
        '.lf-shortcut-bar .lf-shortcut[data-lf-command-ids~="probe.second"]'
    )
    expect(offered).to_have_count(1)
    expect(offered.locator("kbd")).to_have_text("2")
    expect(
        page.locator('.lf-shortcut-bar [data-lf-command-ids~="probe.first"]')
    ).to_have_count(0)

    page.keyboard.press("1")
    rendered(page)
    expect(result).to_have_text("No action")
    page.keyboard.press("2")
    expect(result).to_have_text("Second applied")
    expect(page.locator("#probe kbd").nth(1)).to_be_visible()
    page.keyboard.press("1")
    rendered(page)
    expect(result).to_have_text("Second applied")
    page.keyboard.press("?")
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(
        reference.locator('[data-lf-command="probe.second"][data-lf-available="true"]')
    ).to_have_count(1)
    expect(
        reference.locator(
            '[data-lf-command="probe.first"][data-lf-available="true"], '
            '[data-lf-command="probe.outer"][data-lf-available="true"]'
        )
    ).to_have_count(0)


CONTEXT_COMMAND_MODULE = """\
import {commands, keepsText, offer, paintKeys} from '/runtime/widget-api.js';

customElements.define('lf-keyboard-probe', class extends HTMLElement {
  connectedCallback() {
    const result = offer('output', '', 'No action');
    const rows = [];
    for (let index = 1; index <= 12; index++) {
      const control = offer('button', '', `Action ${index}`);
      const apply = () => keepsText(result, `Action ${index} applied`);
      this.append(control);
      rows.push({id: `probe.action-${index}`, title: `Action ${index}`, decision: true,
        contextKeys: index <= 9 ? [String(index)] : index === 10 ? ['F10'] : [],
        keys: index === 12 ? ['F12'] : [], control, run: apply});
    }
    this.append(result);
    commands(this, 'In explicit actions', rows);
    const replace = offer('button', '', 'Replace declaration');
    replace.onclick = () => {
      commands(this, 'In explicit actions', [{id: 'probe.replacement', title: 'Replacement',
        contextKeys: ['2'], run: () => keepsText(result, 'Replacement applied')}]);
      paintKeys();
    };
    this.append(replace);
  }
});
"""


def test_context_commands_keep_widget_assigned_aliases_and_source_lifetime(
    browser, serve
):
    """Forwarding has no nine-action cap and never assigns a missing binding.

    A source declaration replacement withdraws its old routes and installs references
    to the replacement callback; the ordinary widget key never leaks to its question.
    """
    page = open_page(
        browser,
        serve(
            leaf_page(
                "explicit context commands",
                '<h1>Explicit bindings</h1><lf-ask id="question"><h2>Which action?</h2>'
                '<lf-keyboard-probe id="probe" asks></lf-keyboard-probe></lf-ask>',
            ),
            layer_registry=KEYBOARD_HINT_REGISTRY,
            layer_widgets={"lf-keyboard-probe.js": CONTEXT_COMMAND_MODULE},
        ),
    )
    result = page.locator("#probe output")
    page.keyboard.press("m")
    expect(page.locator("#question")).to_be_focused()
    expect(
        page.locator('.lf-shortcut-bar [data-lf-command-ids~="probe.action-1"]')
    ).to_contain_text("Action 1")
    page.keyboard.press("9")
    expect(result).to_have_text("Action 9 applied")
    page.keyboard.press("F10")
    expect(result).to_have_text("Action 10 applied")
    page.keyboard.press("F12")
    rendered(page)
    expect(result).to_have_text("Action 10 applied")
    page.keyboard.press("Tab")
    expect(page.get_by_role("button", name="Action 1", exact=True)).to_be_focused()
    page.keyboard.press("F12")
    expect(result).to_have_text("Action 12 applied")
    page.get_by_role("button", name="Action 11", exact=True).click()
    expect(result).to_have_text("Action 11 applied")
    page.keyboard.press("?")
    page.keyboard.press("?")
    unbound = page.locator(
        '.lf-command-reference tr[data-lf-command="probe.action-11"]'
    )
    expect(unbound.locator(".lf-command-reference-command")).to_have_attribute(
        "data-lf-available", "true"
    )
    expect(unbound).to_contain_text("Action 11")
    unbound.locator(".lf-command-reference-command").click()
    expect(result).to_have_text("Action 11 applied")

    page.get_by_role("button", name="Replace declaration").click()
    page.locator("#question").focus()
    rendered(page)
    page.keyboard.press("1")
    rendered(page)
    expect(result).to_have_text("Action 11 applied")
    page.keyboard.press("2")
    expect(result).to_have_text("Replacement applied")
    expect(
        page.locator('.lf-shortcut-bar [data-lf-command-ids~="probe.replacement"]')
    ).to_contain_text("Replacement")
    page.keyboard.press("F10")
    rendered(page)
    expect(result).to_have_text("Replacement applied")


def test_restoring_ask_focus_can_execute_its_command_in_the_same_turn(browser, serve):
    """Focus determines forwarded scopes synchronously, without a paint registering them."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "synchronous context commands",
                '<h1>Explicit bindings</h1><button id="outside">Outside</button>'
                '<lf-ask id="question"><h2>Which action?</h2>'
                '<lf-keyboard-probe id="probe" asks></lf-keyboard-probe></lf-ask>',
            ),
            layer_registry=KEYBOARD_HINT_REGISTRY,
            layer_widgets={"lf-keyboard-probe.js": CONTEXT_COMMAND_MODULE},
        ),
    )
    page.locator("#outside").focus()
    rendered(page)
    immediate = page.evaluate(
        """async () => {
          const {focusDestination} = await window.__lfWidgetApi();
          const {executeCommand} = await window.__lfCheckApi();
          focusDestination(document.getElementById('question'), 'move');
          const executed = executeCommand('probe.action-10');
          return {executed, held: document.activeElement.id,
            output: document.querySelector('#probe output').textContent};
        }"""
    )
    assert immediate == {
        "executed": True,
        "held": "question",
        "output": "Action 10 applied",
    }


def test_contextual_escape_agrees_across_dispatch_hints_and_reference(browser, serve):
    """Escape forwarding stays live when its context scope is read more than once."""
    module = """\
import {commands, keepsText, offer} from '/runtime/widget-api.js';

customElements.define('lf-keyboard-probe', class extends HTMLElement {
  connectedCallback() {
    const control = offer('button', '', 'Apply operation');
    const result = offer('output', '', 'No action');
    let count = 0;
    this.append(control, result);
    commands(this, 'In escape operation', [{id: 'probe.escape', title: 'Apply operation',
      keys: ['x'], contextKeys: ['Escape'], control, bindingBadge: null,
      run: () => keepsText(result, `Applied ${++count}`)}]);
  }
});
"""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "contextual escape",
                '<h1>Explicit bindings</h1><lf-ask id="question"><h2>Which action?</h2>'
                '<lf-keyboard-probe id="probe" asks></lf-keyboard-probe></lf-ask>',
            ),
            layer_registry=KEYBOARD_HINT_REGISTRY,
            layer_widgets={"lf-keyboard-probe.js": module},
        ),
    )
    result = page.locator("#probe output")
    page.keyboard.press("m")
    expect(page.locator("#question")).to_be_focused()
    rendered(page)
    routes = page.evaluate(
        """async () => {
          const {availableCommandRoutes} = await window.__lfCheckApi();
          const {commandEntries} = await window.__lfCheckApi();
          return [...availableCommandRoutes()].flatMap(([row, bindings]) =>
            commandEntries(row, [...bindings]).filter(entry => entry.id === 'probe.escape')
              .map(entry => entry.binding));
        }"""
    )
    assert routes == ["Escape"]
    expect(
        page.locator(".lf-command-binding-badges .lf-command-binding-badge")
    ).to_be_visible()
    expect(
        page.locator('.lf-shortcut-bar [data-lf-command-ids~="probe.escape"]')
    ).to_contain_text("Apply operation")
    page.keyboard.press("Escape")
    expect(result).to_have_text("Applied 1")
    page.keyboard.press("?")
    page.keyboard.press("?")
    reference_action = page.locator(
        '.lf-command-reference tr[data-lf-command="probe.escape"] '
        ".lf-command-reference-command"
    )
    expect(reference_action).to_have_attribute("data-lf-available", "true")
    reference_action.click()
    expect(result).to_have_text("Applied 2")
    expect(page.locator("#question")).to_be_focused()
    page.keyboard.press("Tab")
    expect(
        page.get_by_role("button", name="Apply operation", exact=True)
    ).to_be_focused()
    page.keyboard.press("x")
    expect(result).to_have_text("Applied 3")
    page.keyboard.press("Escape")
    expect(result).to_have_text("Applied 4")


def test_context_aliases_do_not_collide_with_authored_command_ids(browser, serve):
    """A contextual projection keeps both commands when an authored id ends in .context."""
    module = """\
import {commands, keepsText, offer} from '/runtime/widget-api.js';

customElements.define('lf-keyboard-probe', class extends HTMLElement {
  connectedCallback() {
    const control = offer('button', '', 'Apply operation');
    const neighbour = offer('button', '', 'Neighbour operation');
    const result = offer('output', '', 'No action');
    let count = 0;
    this.append(control, neighbour, result);
    commands(this, 'In named operations', [
      {id: 'probe.apply', title: 'Apply operation', keys: ['F8'], contextKeys: ['1'],
        control, run: () => keepsText(result, `Applied ${++count}`)},
      {id: 'probe.apply.context', title: 'Neighbour operation', keys: ['F9'],
        control: neighbour, run: () => keepsText(result, 'Neighbour applied')},
    ]);
  }
});
"""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "context command identity",
                '<h1>Explicit bindings</h1><button id="outside">Outside</button>'
                '<lf-ask id="question"><h2>Which action?</h2>'
                '<lf-keyboard-probe id="probe" asks></lf-keyboard-probe></lf-ask>',
            ),
            layer_registry=KEYBOARD_HINT_REGISTRY,
            layer_widgets={"lf-keyboard-probe.js": module},
        ),
    )
    result = page.locator("#probe output")
    page.locator("#outside").focus()
    for standing in ["outside", "question"]:
        page.keyboard.press("?")
        page.keyboard.press("?")
        for command_id, title in [
            ("probe.apply", "Apply operation"),
            ("probe.apply.context", "Neighbour operation"),
        ]:
            row = page.locator(
                f'.lf-command-reference tr[data-lf-command="{command_id}"]'
            )
            expect(row).to_have_count(1)
            expect(row).to_contain_text(title)
            expect(row.locator(".lf-command-reference-command")).to_have_attribute(
                "data-lf-available",
                str(standing == "question" and command_id == "probe.apply").lower(),
            )
        page.keyboard.press("Escape")
        if standing == "outside":
            page.keyboard.press("m")
            expect(page.locator("#question")).to_be_focused()
    page.keyboard.press("1")
    expect(result).to_have_text("Applied 1")
    page.keyboard.press("F9")
    rendered(page)
    expect(result).to_have_text("Applied 1")
    page.keyboard.press("Tab")
    expect(
        page.get_by_role("button", name="Apply operation", exact=True)
    ).to_be_focused()
    page.keyboard.press("F8")
    expect(result).to_have_text("Applied 2")
    page.keyboard.press("F9")
    expect(result).to_have_text("Neighbour applied")


def test_context_forwarding_preserves_reference_activation_opt_out(browser, serve):
    """A contextual alias cannot turn a reading-only reference row into an action."""
    module = """\
import {commands, keepsText, offer} from '/runtime/widget-api.js';

customElements.define('lf-keyboard-probe', class extends HTMLElement {
  connectedCallback() {
    const result = offer('output', '', 'No action');
    let count = 0;
    this.append(result);
    commands(this, 'In guarded operation', [{id: 'probe.guarded', title: 'Guarded operation',
      contextKeys: ['F8'], runFromCommandReference: false,
      run: () => keepsText(result, `Applied ${++count}`)}]);
  }
});
"""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "contextual reference policy",
                '<h1>Explicit bindings</h1><lf-ask id="question"><h2>Which action?</h2>'
                '<lf-keyboard-probe id="probe" asks></lf-keyboard-probe></lf-ask>',
            ),
            layer_registry=KEYBOARD_HINT_REGISTRY,
            layer_widgets={"lf-keyboard-probe.js": module},
        ),
    )
    result = page.locator("#probe output")
    page.keyboard.press("m")
    expect(page.locator("#question")).to_be_focused()
    page.keyboard.press("F8")
    expect(result).to_have_text("Applied 1")
    page.keyboard.press("?")
    page.keyboard.press("?")
    reference_row = page.locator(
        '.lf-command-reference tr[data-lf-command="probe.guarded"]'
    )
    expect(reference_row).to_contain_text("Guarded operation")
    expect(reference_row.locator(".lf-command-reference-command")).to_have_count(0)
    reference_row.click()
    rendered(page)
    expect(result).to_have_text("Applied 1")
    page.keyboard.press("Escape")
    expect(page.locator("#question")).to_be_focused()
    page.keyboard.press("F8")
    expect(result).to_have_text("Applied 2")


@pytest.mark.parametrize(
    ("answered", "resolved"), [(False, False), (False, True), (True, False)]
)
def test_context_keys_follow_an_ask_into_its_associated_thread(
    browser, serve, answered, resolved
):
    """A thread representative forwards explicit aliases without local widget keys.

    The relationship survives resolution and answering the Ask. Typing in its comment
    field keeps the contextual digit rather than running the page widget.
    """
    url = serve(
        leaf_page(
            "associated context commands",
            '<h1>Explicit bindings</h1><lf-ask id="question"><h2>Which action?</h2>'
            '<lf-keyboard-probe id="probe" asks></lf-keyboard-probe></lf-ask>',
        ),
        layer_registry=KEYBOARD_HINT_REGISTRY,
        layer_widgets={"lf-keyboard-probe.js": CONTEXT_COMMAND_MODULE},
    )
    thread = panel_comment(
        serve.page_dir, "Discuss the action first.", {"section": "question"}
    )
    if answered:
        append_command(
            serve.page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "probe",
                "action": "settle",
                "detail": {"answer": "yes"},
            },
        )
    if resolved:
        events_model.append_event(
            serve.page_dir, {"kind": "resolve", "author": "user", "parent": thread}
        )
    page = open_page(browser, url)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, True)
    if resolved:
        page.locator(".lf-thread-filter-toggle").click()
        page.locator(
            '[data-filter-kind="status"][data-filter-value="resolved"]'
        ).click()
    summary = page.locator(f'.lf-thread[data-id="{thread}"] > .lf-thread-summary')
    summary.focus()
    expect(summary).to_be_focused()
    result = page.locator("#probe output")
    page.keyboard.press("9")
    expect(result).to_have_text("Action 9 applied")
    page.keyboard.press("F12")
    rendered(page)
    expect(result).to_have_text("Action 9 applied")
    page.keyboard.press("F10")
    expect(result).to_have_text("Action 10 applied")
    if not resolved:
        page.keyboard.press("c")
        editor = page.locator(f'.lf-thread[data-id="{thread}"] leaf-text')
        expect(editor).to_be_focused()
        page.keyboard.type("1")
        expect(editor).to_have_js_property("value", "1")
        expect(result).to_have_text("Action 10 applied")


ROUTE_HINT_OVERRIDE_MODULE = """\
import {commands, keepsText, offer} from '/runtime/widget-api.js';

customElements.define('lf-verdict', class extends HTMLElement {
  connectedCallback() {
    const control = offer('button', '', 'Inspect');
    const inheritedHint = offer('kbd', 'lf-key-badge');
    inheritedHint.setAttribute('aria-hidden', 'true');
    const result = offer('output', '', '0');
    let count = 0;
    this.append(control, inheritedHint, result);
    commands(this, 'In the inspection', [{
      id: 'probe.inspect', keys: ['x'], title: 'Inspect the proposal', line: 'inspect',
      bindingBadge: inheritedHint,
      routes: [{
        id: 'probe.inspect-proposal', binding: 'x', contextKeys: ['1'], decision: true,
        control, bindingBadge: null, title: 'Inspect the proposal',
      }],
      run: binding => keepsText(result, `${binding}:${++count}`),
    }]);
  }
});
"""


def test_route_corner_hint_overrides_the_rows_face_in_ask_and_widget(browser, serve):
    """Explicit null chooses a corner hint instead of inheriting the row's face.

    Ask forwarding and the intrinsic route must preserve that choice and merge into
    one hint when both bindings reach the same original command.
    """
    registry = {
        "lf-verdict": {
            key: value
            for key, value in SEATED_ASK_LAYER["lf-verdict"].items()
            if key != "x-thread-seat"
        }
    }
    page = open_page(
        browser,
        serve(
            leaf_page(
                "route hint override",
                '<h1>Inspection</h1><lf-ask id="question"><h2>Inspect this?</h2>'
                '<lf-verdict id="probe" asks>The proposal.</lf-verdict></lf-ask>',
            ),
            layer_registry=registry,
            layer_widgets={"lf-verdict.js": ROUTE_HINT_OVERRIDE_MODULE},
        ),
    )
    control = page.get_by_role("button", name="Inspect", exact=True)
    inherited = page.locator("#probe kbd")
    chip = page.locator(".lf-command-binding-badges .lf-command-binding-badge")
    result = page.locator("#probe output")

    page.keyboard.press("m")
    expect(page.locator("#question")).to_be_focused()
    expect(chip).to_have_text("1")
    expect(chip).to_be_visible()
    expect(inherited).to_be_hidden()
    page.keyboard.press("1")
    expect(result).to_have_text("x:1")

    page.keyboard.press("Tab")
    expect(control).to_be_focused()
    rendered(page)
    expect(chip).to_have_count(1)
    expect(chip).to_have_text("1")
    expect(inherited).to_be_hidden()
    assert set(control.get_attribute("aria-keyshortcuts").split()) == {"1", "x"}
    page.keyboard.press("x")
    expect(result).to_have_text("x:2")
    expect(chip).to_have_count(1)


VISUAL_REVIEW_GALLERY = next(
    path for path in CORPUS_SOURCES if path.stem == "visual-review-gallery"
)


SAMPLE_STARTUP_FAILURE = """<script type="module">
if (new URL(location.href).searchParams.has('startup-failure'))
  window.dispatchEvent(new CustomEvent('lf-startup-failed', {
    detail: {reason: 'Practice could not start'},
  }));
</script>"""


LIVE_SAMPLES_PAGE = leaf_page(
    "Independent practice pages",
    """
<h1 id="host-heading">Practice without changing this page</h1>
<lf-sample id="first-practice" label="First practice">
  <template id="first-source" data-sample>
    <h1 id="child-heading">A practice decision</h1>
    <lf-ask id="child-ask"><h2>Which approach?</h2>
      <lf-options id="child-options" choose>
        <lf-option id="child-a">First approach</lf-option>
        <lf-option id="child-b">Second approach</lf-option>
      </lf-options>
    </lf-ask>
  </template>
</lf-sample>
<lf-sample id="second-practice" label="Second practice">
  <template id="second-source" data-sample>
    <h1 id="child-heading">Another practice decision</h1>
    <lf-ask id="child-ask"><h2>Which approach?</h2>
      <lf-options id="child-options" choose>
        <lf-option id="child-a">First approach</lf-option>
        <lf-option id="child-b">Second approach</lf-option>
      </lf-options>
    </lf-ask>
  </template>
</lf-sample>
""",
).replace("</template>", SAMPLE_STARTUP_FAILURE + "</template>")


# One practice page, for the journeys that need no second child to compare against:
# each child is a whole page to load.
LIVE_SAMPLE_PAGE = re.sub(
    r'<lf-sample id="second-practice".*?</lf-sample>\n',
    "",
    LIVE_SAMPLES_PAGE,
    flags=re.DOTALL,
)
assert "second-practice" not in LIVE_SAMPLE_PAGE


def fail_sample_startup(route):
    """The real child reports its fixture's failure over the private bridge.

    Keep native document delivery: an intercepted synthetic response has no network
    address space, so Chromium refuses its opaque origin's real loopback resources.
    """
    route.fulfill(
        status=307, headers={"Location": route.request.url + "?startup-failure"}
    )


def test_tab_walks_into_and_out_of_a_full_view_sample(browser, serve):
    """Full view is modal and holds its frame, and Tab is the browser's there: it walks
    into the child's controls, on out of the frame, and round to the view's own controls,
    never onto the page beneath."""
    page = open_page(browser, serve(LIVE_SAMPLES_PAGE))
    sample = page.locator("#first-practice")
    frame = sample.locator("iframe")
    child = frame.element_handle().content_frame()
    sample.get_by_role("button", name="Full view", exact=True).click()
    view = sample.locator("dialog.lf-sample-view")
    expect(
        sample.get_by_role("button", name="Return to page", exact=True)
    ).to_be_focused()

    # Where focus stands in the containing page: in the view, on its frame, or out at
    # the browser's own interface.
    standing = """view => {
      let at = document.activeElement;
      while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
      if (at === document.body) return "browser";
      if (!view.contains(at)) return "page";
      return at.localName === "iframe" ? "frame" : "view";
    }"""
    entered = left = False
    for _ in range(40):
        page.keyboard.press("Tab")
        at = view.evaluate(standing)
        assert at != "page", "Tab left Full view for the page beneath"
        entered |= at == "frame" and child.evaluate("() => document.hasFocus()")
        if entered and at == "view":
            left = True
            break
    assert entered, "Tab never entered the sample's own page"
    assert left, "Tab never came back out of the sample to the view's controls"

    # Back on the page, Tab past the child's last stop goes on to the page's next stop.
    page.keyboard.press("Escape")
    expect(sample.get_by_role("button", name="Full view", exact=True)).to_be_focused()
    child.evaluate(
        """async () => {
          const { tabStops } = await window.__lfCheckApi();
          tabStops(document.body).at(-1).focus();
        }"""
    )
    expect(frame).to_be_focused()
    page.keyboard.press("Tab")
    expect(frame).not_to_be_focused()


REPLY_SAMPLE = """<lf-sample id="reply-practice" label="Practice in a reply">
  <template id="reply-practice-source" data-sample>
    <h1 id="reply-child-heading">Practice from a reply</h1>
    <lf-ask id="reply-child-ask"><h2>Which approach?</h2>
      <lf-options id="reply-child-options" choose>
        <lf-option id="reply-child-a">First approach</lf-option>
        <lf-option id="reply-child-b">Second approach</lf-option>
      </lf-options>
    </lf-ask>
  </template>
</lf-sample>"""


def test_an_agent_reply_runs_its_live_sample_in_the_thread(browser, serve):
    """A live sample an agent posts in a reply is a page the user operates in the
    thread: its template is the message's, and its gestures reach only its own log."""
    url = serve(leaf_page("Reply host", '<h1 id="host">Session store</h1>'))
    question = panel_comment(serve.page_dir, "What would the alternative look like?")
    replied = CliRunner().invoke(
        cli_model.cli,
        [
            "response",
            "reply",
            "--done",
            response_reference(serve.page_dir, question),
            "--text",
            "Try it here:",
            "--markup",
            REPLY_SAMPLE,
        ],
    )
    assert replied.exit_code == 0, replied.output
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    page.locator(f'.lf-thread[data-id="{question}"] .lf-thread-summary').click()
    sample = page.locator("#reply-practice")
    sample.evaluate("async sample => await sample.ready")
    child = sample.locator("iframe").element_handle().content_frame()
    child.lf_traffic = Traffic(child)
    expect(child.locator("#reply-child-heading")).to_have_text("Practice from a reply")
    with sending(child, "the sample choice"):
        child.locator("#reply-child-b .lf-pick").click()
    expect(child.locator("#reply-child-b .lf-pick")).to_have_attribute(
        "aria-checked", "true"
    )
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert take_browser_errors(page) == []


def _sample_containment_page():
    """A host can change a distant child's view; its passage needs two scrollports."""
    return leaf_page(
        "Contained practice",
        """
<h1>Contained practice</h1>
<div id="host-controls">
  <button id="show-page" type="button">Show page conversation</button>
  <button id="show-panel" type="button">Show panel conversation</button>
  <button id="reset-child" type="button">Restart conversation</button>
  <output id="completed">0</output>
</div>
<div style="height: 1400px"></div>
<lf-sample id="practice" label="Contained conversation" window>
  <template id="practice-source" data-sample data-sample-events="history">
    <h1>Child conversation</h1>
    <div style="height: 900px"></div>
    <div id="nested-reading" style="height: 240px; overflow: auto">
      <div style="height: 900px"></div>
      <p id="destination">Nested landing target.</p>
      <div style="height: 300px"></div>
    </div>
    <div style="height: 800px"></div>
  </template>
</lf-sample>
<div style="height: 1400px"></div>
""",
        head="""
<style>#host-controls { position: fixed; top: 90px; left: 20px; z-index: 2;
  background: white; padding: 8px; }</style>
<script id="history" type="application/json">
  [{"id":"question","kind":"comment","anchor":{"section":"destination"},
    "text":"Can you check the destination?"},
   {"kind":"reply","author":"agent","parent":"question","ephemeral":true,
    "text":"Checking the nested reading region."},
   {"kind":"reply","author":"agent","parent":"question",
    "text":"The destination is inside the nested reading region."}]
</script>
<script type="module">
  const sample = document.querySelector('#practice');
  let surface = 'page';
  let completed = 0;
  for (const button of document.querySelectorAll('#host-controls button')) {
    button.addEventListener('click', async () => {
      if (button.id === 'reset-child') await sample.reset();
      else surface = button.id === 'show-page' ? 'page' : 'panel';
      const shown = await sample.showThread('question', {surface});
      document.querySelector('#completed').textContent =
        shown ? String(++completed) : 'cancelled';
    });
  }
</script>
""".replace(
            "Checking the nested reading region.",
            "Checking the nested reading region and its surrounding reading context. "
            * 50,
        ),
    )


def test_reading_keys_page_on_from_a_sample_to_its_page(browser, serve):
    """d/u in a sample whose own page is spent move the containing page, as the
    wheel does; in Full view the modal keeps them inside."""
    filler = "".join(
        f'<p id="line-{i}">Line {i} of a long child page.</p>' for i in range(60)
    )
    source = leaf_page(
        "Sample reading keys",
        f"""
<h1>Sample reading keys</h1>
<div style="height: 300px"></div>
<lf-sample id="block" label="A block sample">
  <template id="block-page" data-sample>
    <p id="child-text">A short child page.</p>
  </template>
</lf-sample>
<lf-sample id="window" label="A window sample" window>
  <template id="window-page" data-sample>{filler}</template>
</lf-sample>
<div style="height: 2400px"></div>
""",
    )
    page = open_page(browser, serve(source))
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1200, 800)
    block = page.locator("#block")
    block.evaluate("async sample => { await sample.ready; }")
    child = block.locator("iframe").element_handle().content_frame()
    assert child.evaluate("() => document.scrollingElement.scrollHeight <= innerHeight")
    child.locator("#child-text").click()
    page.keyboard.press("d")
    expect(page.locator(":root")).not_to_have_js_property("scrollTop", 0)
    below = page.evaluate("scrollY")
    page.keyboard.press("u")
    page.wait_for_function("below => scrollY < below", arg=below)

    window = page.locator("#window")
    window.evaluate("async sample => { await sample.ready; }")
    window.get_by_role("button", name="Full view", exact=True).click()
    inside = window.locator("iframe").element_handle().content_frame()
    inside.locator("#line-59").click()
    inside.evaluate("() => scrollTo(0, document.scrollingElement.scrollHeight)")
    at = page.evaluate("scrollY")
    page.keyboard.press("d")
    page.wait_for_timeout(300)
    assert page.evaluate("scrollY") == at


CONTROL_STABILITY_PAGE = leaf_page(
    "control stability",
    """
<h1 id="control-target">Control stability</h1>
<lf-suggestion id="stable-suggestion">
  <lf-old>Keep the broad sweep.</lf-old>
  <lf-new>Keep one causal case per control archetype.</lf-new>
</lf-suggestion>
<lf-ask id="stable-options-decision"><h2>Which control should stay?</h2>
<lf-options id="stable-options" choose>
  <lf-option id="stable-choice-a" for="control-target">Keep A</lf-option>
  <lf-option id="stable-choice-b" for="control-target">Keep B</lf-option>
</lf-options></lf-ask>
<lf-tabs id="stable-tabs">
  <lf-tab id="stable-tab-a" label="First">First panel.</lf-tab>
  <lf-tab id="stable-tab-b" label="Second">Second panel.</lf-tab>
</lf-tabs>

<lf-ask id="stable-playground-decision"><h2>How should the release card look?</h2>
<lf-playground id="stable-playground" submit-label="Use these settings">
  <lf-playground-control name="radius" label="Corner radius" kind="range"
    value="12" min="0" max="24" step="1" unit="px"></lf-playground-control>
  <lf-playground-control name="tone" label="Tone" kind="choice" value="quiet">
    <lf-playground-choice value="quiet" label="Quiet"></lf-playground-choice>
    <lf-playground-choice value="bold" label="Bold"></lf-playground-choice>
  </lf-playground-control>
  <lf-playground-preview id="stable-playground-preview">
    <article id="stable-playground-card"><strong>Release card</strong><p>The ceiling doubles per approval.</p></article>
  </lf-playground-preview>
  <lf-playground-output id="stable-playground-instruction">Use a
    <lf-playground-value for="radius"></lf-playground-value> corner radius and a
    <lf-playground-value for="tone"></lf-playground-value> tone.
  </lf-playground-output>
</lf-playground></lf-ask>
<lf-diff id="stable-diff"><pre>
diff --git a/gateway/limits.py b/gateway/limits.py
--- a/gateway/limits.py
+++ b/gateway/limits.py
@@ -1,2 +1,3 @@
 def ceiling(limit, approvals):
-    return limit
+    # the ceiling doubles per approval
+    return "over" if approvals &gt; 12 else limit
</pre></lf-diff>
"""
    f"""<lf-shot id="stable-shot" alt="the release card"
         before="{SHOT_SRC["before"]}" after="{SHOT_SRC["after"]}"></lf-shot>
""",
    head='<meta name="lf-review" content="sign-off">',
)


def test_controls_share_pointer_and_keyboard_focus_rings(browser, serve):
    """Focus has one ring for native controls, linked carriers, and shadow controls."""
    declaration = element_declaration("lf-shadow-focus", upgrade=True)
    declaration["x-shadow"] = True
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Focus routes",
                """
<h1 id="focus-heading">Focus routes</h1>
<p><button class="button" id="focus-button" type="button">Ordinary button</button></p>
<lf-tabs id="focus-tabs">
  <lf-tab id="focus-first" label="First">First panel.</lf-tab>
  <lf-tab id="focus-second" label="Second">Second panel.</lf-tab>
</lf-tabs>
<lf-ask id="focus-decision"><h2>Which option?</h2>
<lf-options id="focus-options" choose>
  <lf-option id="focus-choice" for="focus-heading">Keep this option.</lf-option>
  <lf-option id="focus-peer" for="focus-heading">Keep another option.</lf-option>
</lf-options></lf-ask>
<lf-shadow-focus id="focus-shadow"><button class="button" type="button">Shadow button</button></lf-shadow-focus>
""",
            ),
            layer_registry={"lf-shadow-focus": declaration},
            layer_widgets={
                "lf-shadow-focus.js": """
import {once, shadowStage} from '/runtime/widget-api.js';
import '/vendor/webawesome.esm.js';
customElements.define('lf-shadow-focus', class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    const select = document.createElement('wa-select');
    select.label = 'Choose a route';
    select.withClear = true;
    select.value = 'first';
    for (const [value, label] of [['first', 'First route'], ['second', 'Second route']]) {
      const option = document.createElement('wa-option');
      option.value = value;
      option.textContent = label;
      select.append(option);
    }
    shadowStage(this, [...this.childNodes, select]);
  }
});
"""
            },
        ),
    )
    paint = """el => { const s = getComputedStyle(el); return {
      style: s.outlineStyle, width: s.outlineWidth, color: s.outlineColor,
      offset: s.outlineOffset, name: s.getPropertyValue('--lf-focus-ring').trim()
    }; }"""
    button = page.locator("#focus-button")
    tab = page.get_by_role("tab", name="First", exact=True)
    choice = page.locator("#focus-choice > .lf-pick")
    shadow_button = page.locator("#focus-shadow").get_by_role(
        "button", name="Shadow button", exact=True
    )
    for control, carrier in (
        (button, button),
        (tab, tab.locator(".lf-tab-name")),
        (choice, page.locator("#focus-choice")),
        (shadow_button, shadow_button),
    ):
        control.click()
        expect(control).to_be_focused()
        rendered(page)
        pointer = carrier.evaluate(paint)
        assert pointer["style"] == "solid" and pointer["name"] != "none", pointer
        drawn = rings_drawn(page)
        samples = [ring for ring in drawn if ring["sample"]]
        assert len(samples) == 1, drawn
        assert not ring_faults(drawn, "after pointer arrival")

        # Return by sequential navigation to cover the tab list's roving stop and
        # the option row's carrier through a real keyboard arrival.
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("Tab")
        expect(control).to_be_focused()
        rendered(page)
        assert carrier.evaluate(paint) == pointer
        drawn = rings_drawn(page)
        assert len([ring for ring in drawn if ring["sample"]]) == 1, drawn
        assert not ring_faults(drawn, "after keyboard arrival")

    assert page.locator("#focus-shadow").evaluate(paint)["style"] == "none", (
        "retargeting focus to the widget host drew a second ring around its button"
    )

    select = page.locator("#focus-shadow wa-select")
    combobox = select.get_by_role("combobox")
    listbox = select.locator('[part~="listbox"]')
    first = select.get_by_role("option", name="First route", exact=True)
    second = select.get_by_role("option", name="Second route", exact=True)

    def one_select_ring(control, where):
        expect(control).to_be_focused()
        expect(control).to_be_visible()
        rendered(page)
        drawn = rings_drawn(page)
        assert len(drawn) == 1 and drawn[0]["sample"], (where, drawn)
        assert not ring_faults(drawn, where)

    # The popup's options are slotted beside the combobox. Focus within the select
    # host must not ring both the combobox and an option outside its ancestry.
    combobox.click()
    one_select_ring(first, "after opening the select")
    page.keyboard.press("ArrowDown")
    one_select_ring(second, "after moving to the next option")
    page.keyboard.press("Enter")
    expect(select).to_have_js_property("value", "second")
    one_select_ring(combobox, "after choosing an option")
    expect(listbox).to_be_hidden()
    combobox.click()
    one_select_ring(second, "after reopening the select")
    page.keyboard.press("Escape")
    one_select_ring(combobox, "after closing the select")
    expect(listbox).to_be_hidden()
    select.locator('[part~="clear-button"]').click()
    expect(select).to_have_js_property("value", None)
    one_select_ring(combobox, "after clearing the select")
    shadow_button.click()
    one_select_ring(shadow_button, "after leaving the select")
    assert not select.locator('[part~="combobox"]').evaluate(
        "el => el.part.contains('lf-focus-within')"
    ), "the field retained its public focus part after focus left"


SIGNOFF_STABILITY_PAGE = LONG_PAGE.replace(
    "<title>long</title>",
    '<title>long</title><meta name="lf-review" content="sign-off">',
)

# The rendered control mechanisms whose rows must keep their geometry across a press.
# `target` is the one causal transition that proves each mechanism's stability contract.
CONTROL_ARCHETYPES = (
    {
        "name": "banner",
        "source": SIGNOFF_STABILITY_PAGE,
        "target": ".lf-signoff",
    },
    {
        # Accept and Reject share the resting row. A thread adds the third margin entry that
        # puts the secondary choices behind `…`; opening it must leave Accept still.
        "name": "margin-entry",
        "target": '[data-lf-margin-for="stable-suggestion"] > .lf-margin-more',
    },
    {
        "name": "option-pick",
        "target": "#stable-choice-a .lf-pick",
    },
    {
        "name": "tab",
        "target": "#stable-tabs .lf-tab-btn:nth-child(2)",
    },
    {
        # The playground's action row: Reset, Copy instruction, and the send beside each
        # other under the controls. The send is the press with something to prove — it
        # posts the configuration and comes back disabled, and a control that changes its
        # own paint on the press is where a neighbour moves.
        "name": "playground-actions",
        "target": "#stable-playground .lf-playground-submit",
    },
    {
        # The comparison rail: Before and After stand beside each other above the frames,
        # and each caption chooses its own frame. Pressing After is the transition with
        # something to prove — the caption the user leaves and the one they arrive at
        # both change their active paint, and a rule that spent width on the active word
        # would move the other caption under the user's pointer.
        "name": "shot-caption",
        "target": '#stable-shot .lf-shotcap[data-lf-state="after"]',
    },
    {
        # The case queue's Previous, case selector, and Next controls share the
        # row above the evidence. Selecting another title changes the select's
        # contents without moving the buttons around it.
        "name": "visual-review-navigation",
        "source": VISUAL_REVIEW_GALLERY,
        "target": ".lf-vr-case-select",
        "option": "All mobile destinations remain reachable",
    },
    {
        # The visual inspector's view and size presses are joined groups whose selected
        # treatment changes in place. Pressing Flip exercises both states while its
        # Compare, Overlay, and size neighbours stay under the user's pointer.
        "name": "visual-review-inspection",
        "source": VISUAL_REVIEW_GALLERY,
        "open": ".lf-vr-inspection-summary",
        "target": '.lf-vr-mode-group > [value="flip"]',
    },
    {
        # A disposition changes both its selected paint and the case's durable review
        # state while its opposite remains beside it.
        "name": "visual-review-disposition",
        "source": VISUAL_REVIEW_GALLERY,
        "target": ".lf-vr-case[data-selected] .lf-vr-needs-work",
    },
)


def _touch_drag(cdp, x, y, *, dx=0, dy=0, steps=14):
    """Send the touch stream a device produces, through Chromium's input boundary."""
    x, y = round(x), round(y)
    cdp.send(
        "Input.dispatchTouchEvent",
        {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]},
    )
    for step in range(1, steps + 1):
        cdp.send(
            "Input.dispatchTouchEvent",
            {
                "type": "touchMove",
                "touchPoints": [
                    {
                        "x": x + dx * step // steps,
                        "y": y + dy * step // steps,
                    }
                ],
            },
        )
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


def test_sign_off_stands_through_a_draft_and_moves_nothing(browser, serve):
    """Approval is on the banner's row wherever the page declares sign-off, stamped or
    not. It came and went with the stamp, and at a width where Approval takes the
    banner to two rows a draft arriving took it back to one and moved the whole
    document: news moving the page. Before a stamp the press is refused and says why."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page = open_page(browser, live_url(serve(html)))
    resized(page, 560, 800)
    button = page.locator(".lf-signoff")
    expect(button).to_be_visible()
    height = page.evaluate(BANNER_HEIGHT)
    top = page.evaluate(
        "() => document.querySelector('main').getBoundingClientRect().top"
    )
    (serve.page_dir / "index.html").write_text(
        html.replace("</main>", "<p>A draft's new paragraph.</p></main>")
    )
    told(page)
    expect(page.locator(".lf-version")).to_have_text("Showing Draft")
    expect(button).to_be_visible()
    expect(button).to_have_attribute(
        "title", "There is no stamped version to approve yet"
    )
    assert page.evaluate(BANNER_HEIGHT) == height
    after = page.evaluate(
        "() => document.querySelector('main').getBoundingClientRect().top"
    )
    assert after == pytest.approx(top, abs=1), (top, after)


def test_a_page_asking_for_sign_off_records_the_approval(browser, serve):
    """The declared ask puts the button there, and the press posts `done`.

    Drive the shipped browser through the real POST door, since a button that merely
    looks right says nothing about the event the agent's loop receives.
    """
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page = open_page(browser, serve(html))
    button = page.locator(".lf-signoff")
    expect(button).to_be_visible()
    expect(button).to_have_attribute(
        "title", "Approve this work; the page stays open for follow-up"
    )
    expect(button).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    button.click()
    holding(page, held, 1, "the approval")
    expect(button).to_be_disabled()
    expect(button).to_have_attribute("aria-busy", "true")
    button.dispatch_event("click")
    assert _traffic(page).sends == 1, "one approval press became two log events"

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    event = events_model.read_events(serve.page_dir)[-1]
    assert (event["kind"], event["author"], event["version"]) == ("done", "user", 1)
    expect(button).to_be_disabled()


@pytest.mark.parametrize("width", [1200, 390])
def test_required_approval_is_an_ask_until_approved(browser, serve, width):
    """Sign-off belongs to On me and leads to the real approval control,
    including its phone overflow seat. A task's Done cannot substitute for it."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page = open_page(browser, serve(html))
    page.set_viewport_size({"width": width, "height": 900})
    on_me = page.get_by_role("button", name="On me: 1", exact=True, include_hidden=True)
    expect(on_me).to_be_attached()
    target = page.evaluate("""async () => {
      const {readAsks, askActions} = await window.__lfWidgetApi();
      const ask = readAsks().all.find(q => q.source.kind === 'approval');
      const target = document.getElementById(ask.prompt.target);
      await askActions.open(ask.id);
      return target === document.querySelector('.lf-signoff') && document.activeElement === target;
    }""")
    assert target, "the public ask route did not reach its declared approval target"
    page.keyboard.press("m")
    approval = page.locator(".lf-signoff")
    expect(approval).to_be_visible()
    expect(approval).to_be_focused()
    approval.click()
    round_trip(page)
    expect(
        page.get_by_role(
            "button",
            name="On me: 0",
            exact=True,
            include_hidden=True,
        )
    ).to_be_attached()
    page.keyboard.press("z")
    round_trip(page)
    expect(on_me).to_be_attached()
    page.keyboard.press("Escape")
    if width < 600:
        page.locator(".lf-banner-more").click()
    on_me.click()
    row = page.locator("button[data-lf-row]").filter(has_text="Approve v1?")
    expect(row).to_be_visible()
    expect(
        page.get_by_role("button", name="Done: Approve v1?", exact=True)
    ).to_have_count(0)
    row.click()
    expect(approval).to_be_visible()
    expect(approval).to_be_focused()


def test_an_approval_can_be_taken_back_like_any_other_user_gesture(browser, serve):
    """Approval, its ask and its history agree during send, undo and refusal.

    Holding each POST proves the result is visible before admission; a definitive
    refusal restores the same admitted approval through every consumer.
    """
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page = open_page(browser, serve(html))
    button = page.locator(".lf-signoff")
    expect(button).to_have_attribute(
        "title", "Approve this work; the page stays open for follow-up"
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    history = page.locator(".lf-threads > .lf-system")
    on_me = page.get_by_role("button", name="On me: 1", exact=True, include_hidden=True)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    button.click()
    holding(page, held, 1, "the refused approval")
    expect(button).to_have_text("✓ Version approved")
    expect(on_me).to_have_count(0)
    expect(history).to_contain_text("Approved")
    held[0].fulfill(
        json={
            "ok": False,
            "attempt": held[0].request.post_data_json["attempt"],
            "error": "This approval was refused.",
            "final": True,
        }
    )
    round_trip(page)
    expect(button).to_have_text("Approve version")
    expect(on_me).to_be_attached()
    expect(history).to_have_count(0)
    held.clear()
    button.click()
    holding(page, held, 1, "the accepted approval")
    expect(button).to_have_text("✓ Version approved")
    expect(on_me).to_have_count(0)
    expect(history).to_contain_text("Approved")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(button).to_have_text("✓ Version approved")
    expect(button).to_have_attribute(
        "title", "Approved. Press z to undo while approval is still the latest update"
    )

    expect(history).to_contain_text("Approved")
    expect(on_me).to_have_count(0)
    held.clear()
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("z")
    holding(page, held, 1, "the refused approval undo")
    expect(button).to_have_text("Approve version")
    expect(on_me).to_be_attached()
    expect(history).to_have_count(0)
    held[0].fulfill(
        json={
            "ok": False,
            "attempt": held[0].request.post_data_json["attempt"],
            "error": "This withdrawal was refused.",
            "final": True,
        }
    )
    page.unroute("**/api/event")
    round_trip(page)
    expect(button).to_have_text("✓ Version approved")
    expect(on_me).to_have_count(0)
    expect(history).to_contain_text("Approved")
    held.clear()
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("z")
    holding(page, held, 1, "the accepted approval undo")
    expect(button).to_have_text("Approve version")
    expect(on_me).to_be_attached()
    expect(history).to_have_count(0)
    expect(button).to_be_enabled()
    expect(button).to_have_attribute(
        "title", "Approve this work; the page stays open for follow-up"
    )
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(button).to_have_text("Approve version")
    expect(on_me).to_be_attached()
    expect(history).to_have_count(0)
    kinds = [e["kind"] for e in events_model.read_events(serve.page_dir)]
    assert kinds[-2:] == [
        "done",
        "undo",
    ], f"the withdrawal is not in the log as its own event: {kinds}"

    # And the press is available again, which is what makes this a correction rather than
    # a page the user has spent.
    held.clear()
    page.route("**/api/event", lambda route: held.append(route))
    button.click()
    holding(page, held, 1, "the second approval")
    expect(button).to_have_text("✓ Version approved")
    expect(on_me).to_have_count(0)
    expect(history).to_contain_text("Approved")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(history).to_contain_text("Approved")
    assert [e["kind"] for e in events_model.read_events(serve.page_dir)][-1] == "done"


def test_sign_off_waits_for_the_page_while_comments_stay_live(browser, serve):
    """Approval belongs to the presented page; runtime discussion does not wait for it."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    held = []
    page = browser.new_page()
    page.route("**/api/state*", lambda route: held.append(route))
    with page.expect_request("**/api/state*"):
        page.goto(serve(html), wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    assert held, "the positive control did not hold the first state response"
    button = page.locator(".lf-signoff")
    expect(button).to_be_visible()
    expect(button).to_be_disabled()

    page.locator(".lf-threads-toggle").click()
    expect(page.locator(".lf-thread-panel")).to_have_class(re.compile(r"\bopen\b"))

    held.pop(0).continue_()
    wait_until_ready(page)
    expect(button).to_be_enabled()


def test_a_page_that_asks_nothing_carries_no_terminal_control(browser, serve):
    """An informational page offers Comment on the page, On me, Threads and More
    without an approval action."""
    page = open_page(browser, serve(LONG_PAGE))
    # The banner is built in one pass, so a control standing in it is what makes the
    # absence beside it worth reading rather than a row that never rendered.
    expect(page.locator(".lf-threads-toggle")).to_be_visible()
    assert page.locator(".lf-banner").evaluate("element => element.localName") == (
        "header"
    )
    row = page.locator(".lf-banner-actions > *:visible")
    expect(row).to_have_count(4)
    expect(row.nth(0)).to_have_class(re.compile(r"\blf-page-comment\b"))
    expect(row.nth(1)).to_have_class(re.compile(r"\blf-queue\b"))
    expect(row.nth(2)).to_have_class(re.compile(r"\blf-threads-toggle\b"))
    expect(row.nth(3)).to_have_class(re.compile(r"\blf-banner-more\b"))
    approval = page.locator(".lf-signoff")
    expect(approval).to_have_count(1)
    expect(approval).to_be_hidden()
    expect(approval).to_be_disabled()
    events_before = len(events_model.read_events(serve.page_dir))
    approval.evaluate("control => control.click()")
    assert len(events_model.read_events(serve.page_dir)) == events_before, (
        "the retained control approved a page that did not declare sign-off"
    )


def test_banner_status_keeps_publication_links_outside_its_disclosure(browser, serve):
    """Publication links remain ordinary links, with no disclosure left to open; the
    ordinary status is a native disclosure the browser announces open and shut."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    page.evaluate(
        "() => { window.__lfStatusOwner = document.querySelector('leaf-banner-status'); }"
    )
    door = page.locator(".lf-status-button")
    detail = page.locator(".lf-status-detail")
    door.focus()
    page.keyboard.press("Enter")
    expect(detail).to_be_visible()
    expect(detail).to_be_focused()
    assert accessible_expanded(page, ".lf-status-button") is True

    for _ in range(2):
        page.evaluate(
            """() => window.__lfStatusOwner.present(Object.freeze({
              tone: '', summary: '', queues: '', queuesWidest: '',
              explanation: 'Published copy Install Leaf',
              publication: Object.freeze({
                copy: 'Published copy ', install: 'Install Leaf',
                installUrl: '/#install',
              }),
            }))"""
        )
        expect(door).to_have_count(0)
        expect(detail).to_have_count(0)
        expect(page.locator(".lf-status-text")).to_have_text(
            "Published copy Install Leaf"
        )
        link = page.get_by_role("link", name="Install Leaf", exact=True)
        expect(link).to_have_attribute("href", "/#install")
        assert not link.evaluate("node => !!node.closest('button')")

        page.evaluate(
            """() => window.__lfStatusOwner.present(Object.freeze({
              tone: 'offline', summary: 'Server offline', queues: '', queuesWidest: '',
              explanation: 'Server offline detail', publication: null,
            }))"""
        )
        expect(page.locator(".lf-publication-install")).to_have_count(0)
        expect(door).to_have_text("Server offline")
        expect(door).to_have_attribute("popovertarget", "lf-status-detail")
        assert accessible_expanded(page, ".lf-status-button") is False
        door.focus()
        page.keyboard.press("Enter")
        expect(detail).to_be_visible()
        expect(detail).to_be_focused()
        expect(detail).to_have_text("Server offline detail")
        assert accessible_expanded(page, ".lf-status-button") is True
        page.keyboard.press("Escape")
        expect(detail).to_be_hidden()
        expect(door).to_be_focused()
        assert accessible_expanded(page, ".lf-status-button") is False


WEBSITE_LINE = (
    "This is an example on the Leaf website. Leaf guide replies and revises this "
    "private copy. Other examples Install Leaf"
)

# Measure the real status and its complete hover text in the same rendering turn.
STATUS_FIT = """() => {
  const status = document.querySelector('.lf-status-text');
  const style = getComputedStyle(status);
  const actions = document.querySelector('.lf-banner-actions');
  return {across: {shown: status.clientWidth, needed: status.scrollWidth},
          down: {shown: status.clientHeight, needed: status.scrollHeight},
          lineHeight: parseFloat(style.lineHeight), ellipsis: style.textOverflow,
          title: status.title, text: status.textContent,
          actions: {shown: actions.clientWidth, needed: actions.scrollWidth}};
}"""


def test_every_more_row_wears_one_face_and_rings_inside_the_menu(browser, serve):
    """The developer preview stands in More at every width, so it is one of More's
    rows and wears their face: a badge's smaller type and padding made it a 24px row
    among 30px ones. Every row is packed 4px from the menu's border, so a row's ring
    is drawn inside it; outside, it stood a pixel from the border."""
    url = serve(
        SUGGESTION_PAGE,
        preview={
            "kind": "example",
            "example": "feature-gallery",
            "checkout": "leaf.menu-rows",
            "commit": "c79736ebfcc7",
            "interaction": "author",
            "started": "2026-09-06T12:00:00+00:00",
        },
    )
    page = open_page(browser, url)
    resized(page, 1440, 900)
    page.locator(".lf-banner-more").focus()
    page.keyboard.press("Enter")
    menu = page.locator(".lf-banner-menu")
    expect(menu).to_be_visible()
    rows = page.evaluate(
        """() => [...document.querySelectorAll('.lf-banner-menu .lf-btn')]
          .filter((row) => row.checkVisibility())
          .map((row) => {
            const style = getComputedStyle(row);
            return [row.className, row.getBoundingClientRect().height, style.fontSize,
                    style.paddingInlineStart];
          })"""
    )
    assert any("lf-preview" in row[0] for row in rows), rows
    assert len({tuple(row[1:]) for row in rows}) == 1, rows
    preview = page.locator(".lf-banner-menu .lf-preview")
    expect(preview).to_be_focused()
    ring = preview.evaluate(
        """row => {
          const style = getComputedStyle(row);
          const width = parseFloat(style.outlineWidth);
          const offset = parseFloat(style.outlineOffset);
          const box = row.getBoundingClientRect();
          const menu = row.closest('.lf-banner-menu');
          const edge = menu.getBoundingClientRect();
          const border = parseFloat(getComputedStyle(menu).borderTopWidth);
          return {matches: row.matches(':focus-visible'),
                  clear: box.top - offset - width - (edge.top + border)};
        }"""
    )
    assert ring["matches"] and ring["clear"] >= 2, ring


def test_send_returns_to_more_when_a_gesture_step_displaced_the_comment_control(
    browser, serve
):
    """Send closes the page comment card onto the control that opened it, and where a
    gesture step has taken that control's place on the row, onto More, the door that
    still reaches it (`bannerControlDoor`). A task on the user puts its Done step on
    the row in the reading loop's place."""
    url = serve(
        leaf_page(
            "Task on you",
            '<section id="plan"><h2>Plan</h2>'
            "<p>Ship it on Tuesday, after the backfill.</p></section>"
            '<p id="tail">Nothing else is planned.</p>',
        )
    )
    page = open_page(browser, url)
    resized(page, 1280, 800)
    actions = page.locator(".lf-banner-actions")
    comment = actions.locator(".lf-page-comment")
    done = actions.get_by_role("button", name="Done", exact=True)
    more = page.locator(".lf-banner-more")
    field = page.get_by_role("textbox", name="Comment on the page", exact=True)

    def send(words):
        page.evaluate(RELEASE_FOCUS)
        page.keyboard.press("c")
        expect(field).to_be_focused()
        page.keyboard.type(words)
        with sending(page, words):
            page.keyboard.press("ControlOrMeta+Enter")
        expect(page.locator(".lf-page-comment-card")).to_be_hidden()

    # The control: with nothing displacing it, Send lands on the row's Comment.
    expect(comment).to_be_visible()
    send("With the row as it was")
    expect(comment).to_be_focused()

    # A task the agent puts on the user stands its Done step on the row.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "todo",
            "author": "agent",
            "agent": "Agent",
            "session": "displaced-row",
            "owner": "user",
            "subject": {"kind": "element", "id": "plan"},
            "title": "Check the plan",
        },
    )
    told(page)
    expect(done).to_be_visible()
    expect(comment).to_be_hidden()
    send("With the row displaced")
    expect(more).to_be_focused()
    assert [
        event["text"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ] == ["With the row as it was", "With the row displaced"]


def test_a_selection_that_reaches_the_layer_stops_at_the_page(browser, serve):
    """A drag out of a paragraph takes the passage, not the page and the panel with it.

    The layer is fixed and stands after the document in it, so one range crossing into
    anything selectable in the chrome runs through everything between. Three surfaces
    said user-select: none and the rest did not, so a drag rightwards out of a paragraph
    that overshot the open thread panel's left edge by five pixels took 14,472 characters
    instead of the 67 aimed at, and pressing `c` put the whole page — the passage, every
    widget under it, and the panel's own furniture — into the composer's quote and into
    the field's accessible name.

    The apparatus is answered at the layer's root now, so this asserts the statement
    rather than the three surfaces: everything in here is unselectable except the words
    somebody said, which are a reply and the passage it is about, and those stay
    copyable.
    """
    # Anchored, so the thread carries both of the things a user may want out of the
    # panel: the passage it is about and the reply somebody wrote under it.
    url = serve(LONG_PAGE, anchored=[("p40", "Paragraph 40.")])
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-summary").click()
    expect(page.locator(".lf-thread")).to_have_count(1)

    aim = page.evaluate(
        """() => {
          const para = [...document.querySelectorAll('p')].find((el) => {
            const r = el.getBoundingClientRect();
            return r.width > 200 && r.top > 140 && r.bottom < innerHeight - 60;
          });
          const r = para.getBoundingClientRect();
          return {start: [r.left + 40, r.top + 8],
                  edge: document.querySelector('.lf-thread-panel').getBoundingClientRect().left,
                  words: para.textContent,
                  whole: document.body.textContent.length};
        }"""
    )
    # Five pixels past the edge: the overshoot a user gives a drag they meant to end at
    # the end of a line, which at the covering width lands mid-line on every paragraph.
    select(page, aim["start"], (aim["edge"] + 5, aim["start"][1]))
    took = page.evaluate("() => getSelection().toString()")
    assert took and took in aim["words"], (
        f"the drag took {len(took)} characters from outside the paragraph it started in, "
        f"out of {aim['whole']} in the document: {took[:80]!r}…{took[-80:]!r}"
    )

    # The statement, rather than the surfaces that happened to carry it: apparatus is
    # unselectable, and what a user may copy says so for itself.
    open_layer = page.evaluate(
        """() => {
          const said = '.lf-quote, .lf-msg-body';
          return [...document.querySelector('.lf-chrome').querySelectorAll('*')]
            .filter((el) => getComputedStyle(el).webkitUserSelect !== 'none')
            .filter((el) => !el.closest(said))
            .map((el) => (el.className || el.tagName).toString().trim().split(/\\s+/)[0]);
        }"""
    )
    assert open_layer == [], (
        f"chrome surfaces outside a reply and its passage stayed selectable: {open_layer}"
    )
    copyable = page.evaluate(
        """() => {
          const out = {};
          for (const [name, sel] of [
            ['quote', '.lf-thread-panel.open .lf-thread .lf-quote'],
            ['reply', '.lf-thread-panel.open .lf-thread .lf-msg-body'],
          ]) {
            const range = document.createRange();
            range.selectNodeContents(document.querySelector(sel));
            const selection = getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            out[name] = selection.toString().trim().length;
            selection.removeAllRanges();
          }
          return out;
        }"""
    )
    assert copyable["quote"] and copyable["reply"], (
        f"the panel stopped a user copying the words somebody said: {copyable}"
    )


def test_one_version_opens_a_menu_with_its_version(browser, serve):
    """A lone version keeps its note reachable without advertising a version walk."""
    page = open_page(browser, serve(LONG_PAGE))
    version = page.locator(".lf-version")
    expect(version).to_be_enabled()
    expect(version).to_have_text("Showing v1")
    expect(version).to_have_attribute("aria-haspopup", "menu")
    banner_control(page, ".lf-version").click()
    menu = page.locator(".lf-version-menu")
    expect(menu).to_be_visible()
    expect(menu.locator(".lf-version-row")).to_have_count(1)
    expect(menu.locator(".lf-version-row")).to_have_attribute("aria-current", "true")
    expect(menu.locator(".lf-version-num")).to_have_text("v1 (latest version)")
    expect(menu.locator(".lf-version-note")).to_have_text("t")


def test_the_versions_menu_uses_the_banner_panel_and_its_doors_edge(browser, serve):
    """Versions shares the banner panel's fixed top and its door's horizontal edge."""
    page = open_page(browser, serve(LONG_PAGE))
    picker = page.locator(".lf-version")
    expect(picker).to_be_enabled()
    banner_control(page, ".lf-version").click()
    menu = page.locator(".lf-version-menu")
    expect(menu).to_be_visible()
    boxes = menu.evaluate(
        """menu => {
              const button = document.querySelector('.lf-banner-more').getBoundingClientRect();
              const banner = document.querySelector('.lf-banner').getBoundingClientRect();
              const box = menu.getBoundingClientRect();
              return {banner: {bottom: banner.bottom},
                      button: {top: button.top, bottom: button.bottom, right: button.right},
                      menu: {top: box.top, right: box.right, left: box.left}};
            }"""
    )
    assert boxes["menu"]["top"] == pytest.approx(
        boxes["banner"]["bottom"] + 6, abs=2
    ), boxes
    assert boxes["menu"]["right"] == pytest.approx(boxes["button"]["right"], abs=2), (
        f"the versions menu did not line up with More's right edge: {boxes}"
    )

    resized(page, 320, 844)
    phone = menu.evaluate(
        """menu => {
              const button = document.querySelector('.lf-banner-more').getBoundingClientRect();
              const banner = document.querySelector('.lf-banner').getBoundingClientRect();
              const box = menu.getBoundingClientRect();
              return {banner: {bottom: banner.bottom},
                      button: {bottom: button.bottom, right: button.right},
                      menu: {top: box.top, right: box.right, left: box.left},
                      viewport: innerWidth};
            }"""
    )
    assert phone["menu"]["top"] == pytest.approx(
        phone["banner"]["bottom"] + 6, abs=2
    ), phone
    assert phone["menu"]["right"] == pytest.approx(phone["button"]["right"], abs=2), (
        f"the phone menu did not line up with More's trailing edge: {phone}"
    )
    assert phone["menu"]["left"] >= 0 and phone["menu"]["right"] <= phone["viewport"], (
        f"the phone menu left the viewport: {phone}"
    )
    assert phone["menu"]["right"] - phone["menu"]["left"] <= min(
        360, phone["viewport"] - 16
    ), phone
    assert root_overflow(page) == 0

    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    open_versions(page)
    shortcut = menu.evaluate(
        "menu => ({top: menu.getBoundingClientRect().top, "
        "banner: document.querySelector('.lf-banner').getBoundingClientRect().bottom})"
    )
    assert shortcut["top"] == pytest.approx(shortcut["banner"] + 6, abs=2), shortcut


def test_more_wears_a_dot_while_a_press_would_approve(browser, serve):
    """On a phone Approval stands behind More as a waiting ask, and More wears
    its dot and names both reasons. Approving takes the dot down and taking the
    approval back puts it up again; on a desk Approval stands on the row and More
    wears no dot for it."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    page = open_page(browser, serve(html))
    resized(page, 390, 800)
    more = page.locator(".lf-banner-more")
    approval = page.locator(".lf-signoff")
    expect(more).to_have_attribute("data-lf-news", "")
    expect(more).to_have_attribute(
        "aria-label", "More page controls, approval open, items on me"
    )
    more.click()
    expect(page.locator(".lf-banner-menu > :visible").first).to_have_class(
        re.compile(r"\blf-signoff\b")
    )
    with sending(page, "the approval"):
        approval.click()
    expect(approval).to_have_text("✓ Version approved")
    expect(more).not_to_have_attribute("data-lf-news", re.compile(".*"))
    expect(more).to_have_attribute("aria-label", "More page controls")
    page.keyboard.press("Escape")
    undo(page)
    expect(more).to_have_attribute("data-lf-news", "")

    # Crossing the phone width reseats Approval, and focus goes with it, both ways,
    # here with More open throughout.
    more.click()
    approval.focus()
    resized(page, 1200, 800)
    expect(page.locator(".lf-banner-actions > .lf-signoff")).to_be_visible()
    expect(approval).to_be_focused()
    expect(more).not_to_have_attribute("data-lf-news", re.compile(".*"))
    resized(page, 390, 800)
    expect(page.locator(".lf-banner-menu > .lf-signoff")).to_be_visible()
    expect(approval).to_be_focused()


# Where the banner's two parts stand, the height the theme states for it (the document's
# head is reserved at that height), and each control on its row that the banner cuts off.
BANNER_ROWS = """() => {
  const box = (selector) => document.querySelector(selector).getBoundingClientRect();
  const banner = box('.lf-banner'), status = box('.lf-banner-status'),
        actions = box('.lf-banner-actions');
  const shown = [...document.querySelectorAll('.lf-banner-actions > *')]
    .filter((control) => control.checkVisibility());
  const clipped = shown
    .filter((control) => {
      const at = control.getBoundingClientRect();
      return at.left < Math.max(banner.left, actions.left) - 0.5
        || at.right > Math.min(banner.right, actions.right) + 0.5
        || at.bottom > banner.bottom + 0.5;
    })
    .map((control) => control.textContent.trim());
  return {wrapped: actions.top >= status.bottom - 1,
          height: banner.height, bannerBottom: banner.bottom,
          stated: parseFloat(getComputedStyle(document.body, '::before').height),
          clipped, controls: shown.map((control) => control.textContent.trim()),
          main: document.querySelector('body > main').getBoundingClientRect().top};
}"""
BANNER_HEIGHT = (
    "() => document.querySelector('.lf-banner').getBoundingClientRect().height"
)


def signed_off(html):
    return html.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )


def assert_banner_as_stated(read, wrapped):
    assert read["wrapped"] == wrapped, read
    assert read["height"] == pytest.approx(read["stated"], abs=0.5), (
        f"the banner drew a height other than the one the theme states: {read}"
    )
    assert read["main"] == pytest.approx(read["bannerBottom"], abs=1), (
        f"the document's head does not end where the banner does: {read}"
    )
    assert not read["clipped"], f"the banner cut off {read['clipped']}: {read}"


@pytest.mark.parametrize(
    ("width", "touch", "signoff", "wrapped"),
    [
        # A tablet's window holds the status and the queue counts beside Threads.
        (820, True, False, False),
        # Below that, a landscape phone gives the run, led by the counts, a row of its
        # own, so the sentence keeps a row of its own too.
        (740, True, False, True),
        # Capability arrival cannot change this window's row allocation. Approval
        # arriving or leaving at the other widths is
        # test_approval_capability_changes_keep_banner_targets.
        (600, False, False, True),
        (600, False, True, True),
        # A phone held upright is one row: the status, Threads and More, with Approval
        # behind More.
        (390, True, False, False),
        (470, True, False, False),
    ],
)
def test_the_banner_rows_follow_the_window_independently_of_sign_off(
    browser, serve, width, touch, signoff, wrapped
):
    """The viewport, UI type and aim size allocate the banner before controls arrive.

    Approval and its absence share that allocation, so a revision cannot change the
    document's top reservation. Each control fits the height the theme states.
    """
    html = signed_off(SUGGESTION_PAGE) if signoff else SUGGESTION_PAGE
    context = browser.new_context(
        viewport={"width": width, "height": 800}, has_touch=touch, is_mobile=touch
    )
    page = open_page(browser, serve(html), context=context)
    page_at_rest(page)
    read = page.evaluate(BANNER_ROWS)
    assert_banner_as_stated(read, wrapped)
    row = 53 if touch else 52 if width <= 480 else 42
    assert read["height"] == pytest.approx(row + (36 if wrapped else 0), abs=1), read


def test_stylesheet_motion_inputs_drive_css_and_web_animations(browser, serve):
    """A theme's time expressions reach both consumers through native CSS resolution."""
    source = leaf_page(
        "Motion inputs",
        '<h1>Motion inputs</h1><p id="subject">A visible arrival.</p>'
        '<lf-suggestion id="edit"><lf-old><p>Before</p></lf-old>'
        "<lf-new><p>After</p></lf-new></lf-suggestion>",
        head="""<style>:root {
          --lf-motion-flash: calc(.7s + 30ms);
          --lf-motion-fold: 170ms;
          --lf-motion-agent-arrival: .91s;
        }</style>""",
    )
    context = browser.new_context(reduced_motion="no-preference")
    page = open_page(browser, serve(source), context=context)
    result = page.evaluate("""async () => {
      const owner = await window.__lfWidgetApi();
      const chrome = document.querySelector('.lf-chrome');
      const cue = document.createElement('div');
      cue.className = 'lf-msg flash';
      const arrival = document.createElement('button');
      arrival.className = 'lf-margin-entry';
      arrival.dataset.lfAgentArrival = '1';
      chrome.append(cue, arrival);
      const cssFlash = getComputedStyle(cue).animationDuration;
      const cssArrival = getComputedStyle(arrival).animationDuration;
      const cssFold = getComputedStyle(document.querySelector('lf-old')).transitionDuration;
      const {flashDuration, agentArrivalDuration} = await window.__lfCheckApi();
      const animation = owner.backgroundFlash(document.querySelector('#subject'), flashDuration());
      const played = animation.effect.getTiming().duration;
      animation.finish();
      cue.remove(); arrival.remove();
      return {cssFlash, cssArrival, cssFold, played,
        fold: owner.foldDuration(), agent: agentArrivalDuration()};
    }""")
    assert result == {
        "cssFlash": "0.73s",
        "cssArrival": "0.91s",
        "cssFold": "0.17s",
        "played": 730,
        "fold": 170,
        "agent": 910,
    }


def test_a_panel_uses_the_stylesheet_default_until_the_user_draws_it(browser, serve):
    """The default is a theme input; a retained user choice is a separate authority."""
    source = leaf_page(
        "Panel width input",
        "<h1>Panel width input</h1><p>Keep the chosen edge.</p>",
        head="<style>:root {--lf-thread-panel-default-width:calc(30rem + 16px)}</style>",
    )
    page = open_page(browser, serve(source))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    panel = page.locator(".lf-thread-panel")
    initial = page.evaluate("""() => parseFloat(getComputedStyle(document.documentElement)
      .getPropertyValue('--lf-thread-panel-default-width'))""")
    assert initial > 480
    assert panel.bounding_box()["width"] == pytest.approx(initial)
    page.evaluate("""() => {
      document.documentElement.style.setProperty('--lf-thread-panel-default-width','508px');
      dispatchEvent(new Event('resize'));
    }""")
    assert panel.bounding_box()["width"] == pytest.approx(508)
    edge = panel.get_by_role("separator")
    edge.focus()
    edge.press("ArrowLeft")
    assert panel.bounding_box()["width"] == pytest.approx(532)
    page.evaluate("""() => {
      document.documentElement.style.setProperty('--lf-thread-panel-default-width','600px');
      dispatchEvent(new Event('resize'));
    }""")
    assert panel.bounding_box()["width"] == pytest.approx(532)
    page.reload()
    wait_until_ready(page)
    assert panel.bounding_box()["width"] == pytest.approx(532)


def test_a_finger_s_steps_keep_the_banner_s_rows(browser, serve):
    """A step a finger takes on the banner, here page search's, stands in the reading
    loop's place on the row the banner already has. Just wider than a phone's upright
    face, where the steps have the least room beside the status, they still fit, and
    the banner keeps its height, so opening search moves nothing."""
    context = browser.new_context(
        viewport={"width": 490, "height": 800}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(SUGGESTION_PAGE), context=context)
    page_at_rest(page)
    before = page.evaluate(BANNER_ROWS)
    assert_banner_as_stated(before, wrapped=True)
    page.keyboard.press("/")
    page.keyboard.type("feeder")
    expect(
        page.locator(".lf-banner-actions > .lf-btn", has_text="Next")
    ).to_be_visible()
    page_at_rest(page)
    read = page.evaluate(BANNER_ROWS)
    assert "Close search" in read["controls"], read
    assert_banner_as_stated(read, wrapped=True)
    assert read["main"] == pytest.approx(before["main"], abs=1), (before, read)


def test_a_revision_that_asks_for_sign_off_keeps_the_banner_s_rows(browser, serve):
    """An arriving approval capability uses the banner's existing second row."""
    page = open_page(browser, live_url(serve(SUGGESTION_PAGE)))
    resized(page, 600, 800)
    page_at_rest(page)
    before = page.evaluate(BANNER_ROWS)
    assert_banner_as_stated(before, wrapped=True)
    page.wait_for_timeout(600)  # Let Chrome's recent-input grace expire before news.
    (serve.page_dir / "index.html").write_text(
        signed_off(SUGGESTION_PAGE).replace(
            "</lf-board>", "</lf-board>\n<p>A draft asking for sign-off.</p>"
        )
    )
    told(page)
    expect(page.locator(".lf-banner-actions > .lf-signoff")).to_be_visible()
    page_at_rest(page)
    after = page.evaluate(BANNER_ROWS)
    assert_banner_as_stated(after, wrapped=True)
    for position in ("height", "bannerBottom", "stated", "main"):
        assert after[position] == pytest.approx(before[position], abs=0.5), (
            before,
            after,
        )


def test_open_banner_menu_holds_seats_until_the_next_opening(browser, serve):
    """Passive removals and arrivals keep the reading and its keyboard destinations."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    page.evaluate("""async () => {
      window.toolbar = await window.__lfCheckApi();
      for (const [key, rank, offered] of [
        ['retiring', -30, true], ['arriving', -25, false], ['staying', -20, true],
        ['returning', -15, false],
      ]) {
        const control = document.createElement('button');
        control.className = `lf-ui lf-btn test-${key}`;
        control.textContent = key;
        toolbar.registerBannerControl({key, control, rank, conditional:true, offered, row: {label: key, group: 'page'}});
      }
    }""")
    more = page.locator(".lf-banner-more")
    more.focus()
    page.keyboard.press("Enter")
    retiring = page.locator(".test-retiring")
    staying = page.locator(".test-staying")
    arriving = page.locator(".test-arriving")
    retiring.focus()
    expect(retiring).to_be_focused()
    before = staying.bounding_box()
    page.evaluate("""() => {
      toolbar.showNews(document.querySelector('.test-retiring'), false);
      toolbar.showNews(document.querySelector('.test-arriving'), true);
      toolbar.markBannerControl(document.querySelector('.test-arriving'), 'new action');
    }""")
    expect(retiring).to_be_hidden()
    assert arriving.is_hidden()
    expect(staying).to_be_focused()
    expect(more).to_have_attribute("aria-label", re.compile("new action"))
    assert staying.bounding_box() == before
    assert retiring.evaluate("node => node.offsetHeight") > 0
    page.keyboard.press("Tab")
    expect(arriving).not_to_be_focused()
    page.keyboard.press("Escape")
    expect(more).to_be_focused()
    page.keyboard.press("Enter")
    expect(arriving).to_be_visible()
    expect(arriving).to_be_focused()
    assert retiring.evaluate("node => node.offsetHeight") == 0
    # Explicit travel can reveal a newly offered destination in the held menu.
    # Both the shared reveal route and a nested layer's return use that same owner.
    page.evaluate("""async () => {
      const {reveal} = await window.__lfCheckApi();
      const target = document.querySelector('.test-retiring');
      document.querySelector('.test-arriving').onclick = () => reveal(target, () => true);
      toolbar.showNews(target, true);
    }""")
    assert retiring.is_hidden()
    arriving.press("Enter")
    expect(retiring).to_be_visible()
    page.evaluate("""() => {
      const target = document.querySelector('.test-returning');
      document.querySelector('.test-arriving').onclick = () => toolbar.returnToBannerControl(target);
      toolbar.showNews(target, true);
    }""")
    returning = page.locator(".test-returning")
    assert returning.is_hidden()
    arriving.press("Enter")
    expect(returning).to_be_focused()


def test_ask_banner_controls_keep_identity_and_focus_in_the_fixed_menu(
    browser, serve, other_leaf
):
    """The fixed menu retains each Lit-faced control and hands off removed focus."""
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    panel_comment(serve.page_dir, "Is this ready?", author="agent")
    page = open_page(browser, url)
    resized(page, 1440, 900)
    answer_all = page.locator(".lf-answer-all")
    expect(answer_all).to_be_hidden()
    expect(page.locator(".lf-banner-menu > .lf-answer-all")).to_have_count(1)
    page.evaluate(
        "button => { window.__lfBulkControl = button; }", answer_all.element_handle()
    )
    resized(page, 390, 900)
    expect(page.locator(".lf-banner-menu > .lf-answer-all")).to_have_count(1)
    assert answer_all.evaluate("button => button === window.__lfBulkControl")
    assert answer_all.locator(":scope > lf-ask-banner-face").count() == 1
    order = page.evaluate(
        """() => [...document.querySelector('.lf-banner-menu').children,
                    ...document.querySelector('.lf-banner-actions').children]
          .map(control => control.matches('.lf-page-map-toggle') ? 'map' :
                          control.matches('.lf-answer-all') ? 'blanket' : null)
          .filter(Boolean)"""
    )
    assert order == [
        "map",
        "blanket",
    ], f"the toolbar changed the established Map-before-blanket order: {order}"

    page.evaluate(
        """async () => {
          const toolbar = await window.__lfCheckApi();
          for (let i = 0; i < 3; i++) {
            const control = document.createElement('button');
            control.className = `lf-ui lf-btn lf-focus-candidate-${i}`;
            control.textContent = `Focus candidate ${i + 1}`;
            control.disabled = i === 1;
            toolbar.registerBannerControl({
              key: `test-focus-candidate-${i}`,
              control,
              rank: toolbar.BANNER_CONTROL_RANK.blanket + i + 1,
              row: { label: control.textContent, group: "page" },
            });
          }
        }"""
    )
    page.locator(".lf-banner-more").click()
    retiring = page.locator(".lf-focus-candidate-0")
    retiring.focus()
    page.evaluate(
        """async control => {
          const toolbar = await window.__lfCheckApi();
          toolbar.showBannerControl(control, false);
        }""",
        retiring.element_handle(),
    )
    expect(page.locator(".lf-focus-candidate-2")).to_be_focused()

    # Semantic presence can change while the user is inside the overflow without
    # repartitioning the list under them or stranding focus on the retired control.
    expect(page.locator(".lf-banner-menu")).to_be_visible()
    answer_all.focus()
    page.evaluate(
        """async button => {
          const toolbar = await window.__lfCheckApi();
          toolbar.showNews(button, false);
        }""",
        answer_all.element_handle(),
    )
    expect(answer_all).to_be_hidden()
    expect(page.locator(".lf-banner-menu")).to_be_visible()
    assert answer_all.evaluate(
        "button => button.parentElement.matches('.lf-banner-menu')"
    )
    assert page.evaluate(
        "() => Boolean(document.activeElement.closest('.lf-banner-menu'))"
    )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-banner-more")).to_be_visible()


def test_a_status_kind_change_is_announced_in_the_banners_own_words(browser, serve):
    """The dot going red is not an announcement.

    The banner flipped to the offline colour and rewrote its line while the live region
    went on holding whatever it last said, so a user who is not watching the top of the
    window learned nothing. A kind changing — work starting, a turn ending, the server
    going — is what is worth interrupting for, and what it says is the banner's own
    sentence rather than a second account of it. The age moving and a count turning over
    are not kinds and stay out of the region."""
    url = serve(SUGGESTION_PAGE)
    # The agent has the page in hand when the user opens it.
    working(serve.page_dir, "Writing the page")
    page = open_page(browser, url)
    live = page.locator(".lf-live")
    expect(page.locator(".lf-banner .lf-dot.working")).to_be_visible()
    # The page arriving is the document's own announcement, not a change in it.
    assert live.text_content() == "", (
        f"the banner announced its first reading: {live.text_content()!r}"
    )

    claim = record_claim(serve.page_dir, id="s", pid=os.getpid())
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(serve.page_dir, claim["id"])
    )
    assert lease
    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.set_stream_activity(
            claim["id"], "provider-turn", {"kind": "awaiting_input"}
        )
    told(page)
    expect(live).to_contain_text("Claude is waiting for input")
    announced_wait = live.text_content()

    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.set_stream_activity(
            claim["id"], "provider-turn", {"kind": "tool", "detail": "Checking"}
        )
    told(page)
    assert live.text_content() == announced_wait

    with service_model.PageTransaction(serve.page_dir) as transaction:
        transaction.set_stream_activity(
            claim["id"], "provider-turn", {"kind": "awaiting_approval"}
        )
    told(page)
    expect(live).to_contain_text("Claude is waiting for approval")
    leases_model.release_lease(lease)

    page.route("**/api/**", refuse)
    try:
        # A healthy page never asks without news, so give it one: the read that follows
        # is the one the route refuses.
        nudge(serve.page_dir)
        expect(page.locator(".lf-banner .lf-dot.offline")).to_be_visible()
        offline = " ".join(page.locator(".lf-status-detail").text_content().split())
        assert offline.startswith("Server offline"), (
            f"the banner's offline line has moved: {offline!r}"
        )
        expect(live).to_have_text(offline)
    finally:
        page.unroute("**/api/**")


def test_the_keyboard_reference_is_a_modal_tab_loop_and_returns_to_its_door(
    browser, serve
):
    """A dialog-shaped command reference behaves like a dialog for the native Tab walk."""
    page = open_page(browser, serve(LONG_PAGE))
    door = page.locator(".lf-threads-toggle")
    door.focus()
    page.keyboard.press("?")
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    assert reference.evaluate("el => el.matches(':modal')"), (
        "the command reference looked modal but left the page interactive behind it"
    )
    stops = reference.locator("input, button, [tabindex]:not([tabindex='-1'])")
    assert stops.count() >= 2, "the reference had no meaningful native Tab loop"
    for _ in range(stops.count() + 2):
        page.keyboard.press("Tab")
        assert reference.evaluate(
            "el => el.contains(document.activeElement)"
            "   || document.activeElement === document.body"
        ), "Tab escaped the command reference onto the suspended page"
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()
    expect(door).to_be_focused()


def test_motion_preference_changes_are_heard_without_reloading(browser, serve):
    """The JS motion contract follows a live media preference, like the CSS does."""
    page = open_page(browser, serve(LONG_PAGE))
    reading = """() => window.__lfWidgetApi().then(
      motion => ({reduced: motion.reducedMotion(), scroll: motion.scrollBehavior()}))"""
    assert page.evaluate(reading) == {"reduced": False, "scroll": "smooth"}

    page.emulate_media(reduced_motion="reduce")
    assert page.evaluate(reading) == {"reduced": True, "scroll": "instant"}
    step = page.evaluate(
        "() => { const s = getComputedStyle(document.scrollingElement); return ("
        " document.scrollingElement.clientHeight - parseFloat(s.scrollPaddingTop)"
        " - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
    )
    page.evaluate(
        "() => document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})"
    )
    page.keyboard.press("d")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == pytest.approx(
        step, abs=1
    ), "the navigation factory kept its load-time motion preference"

    page.emulate_media(reduced_motion="no-preference")
    assert page.evaluate(reading) == {"reduced": False, "scroll": "smooth"}

    page.evaluate(
        """() => {
          window.__lfFrames = [];
          window.requestAnimationFrame = callback =>
            (window.__lfFrames.push(callback), window.__lfFrames.length);
          window.cancelAnimationFrame = () => {};
          document.scrollingElement.scrollTo({top: 0, behavior: 'instant'});
        }"""
    )
    page.keyboard.press("d")
    assert page.evaluate("() => window.__lfFrames.length") > 0
    page.emulate_media(reduced_motion="reduce")
    page.evaluate(
        """() => {
          const frames = window.__lfFrames.splice(0);
          for (const callback of frames) callback(0);
        }"""
    )
    assert page.evaluate("() => document.scrollingElement.scrollTop") == pytest.approx(
        step, abs=1
    ), "an active glide kept moving after the user asked for reduced motion"


def test_coarse_pointer_chrome_gives_its_compact_controls_humane_aims(browser, serve):
    """Touch keeps Leaf's compact paint while expanding the boxes a finger works."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    page = open_page(browser, serve(html, comments=1), context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches"), (
        "the touch fixture never reached Leaf's coarse-pointer rules"
    )

    # A phone's row holds Threads and More; Approval leads More.
    primary = page.locator(".lf-threads-toggle, .lf-banner-more")
    expect(primary).to_have_count(2)
    for index in range(primary.count()):
        box = primary.nth(index).bounding_box()
        assert box["width"] >= 43.9 and box["height"] >= 43.9, (
            f"a primary touch aim stayed at {box}"
        )

    page.locator(".lf-threads-toggle").tap()
    panel_settled(page)
    # The shortcut bar is not among them: a touch device has no keyboard to advertise, so
    # the whole line stands down and takes its More control with it.
    expect(page.locator(".lf-shortcut-bar")).to_be_hidden()
    compact = page.locator(
        ".lf-thread-panel .lf-react:visible, .lf-thread-panel-head .lf-btn:visible"
    )
    assert compact.count() >= 1, "the covering panel exposed no compact touch controls"
    for index in range(compact.count()):
        box = compact.nth(index).bounding_box()
        assert box["width"] >= 43.9 and box["height"] >= 43.9, (
            f"a compact panel control kept a mouse-sized aim: {box}"
        )
    page.get_by_role("button", name="Close threads").tap()
    panel_settled(page, open=False)

    # The page comment's empty action and Send both keep a finger-sized aim.
    page_comment(page)
    for words in ("", "Review this page"):
        write(page.locator(".lf-page-comment-card leaf-text"), words)
        action = page.locator(".lf-page-comment-card .lf-general button:visible")
        expect(action).to_be_visible()
        box = action.bounding_box()
        assert box["width"] >= 43.9 and box["height"] >= 43.9, (
            f"the page comment card's action kept a mouse-sized aim: {box}"
        )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-page-comment-card")).to_be_hidden()

    # Across the covering boundary the banner fits the same touch aims. Its toolbar and
    # a keyboard ring remain inside the derived edge rather than centred through it.
    for width in (840, 841, 900, 1200, 1440):
        resized(page, width, 844)
        page.locator(".lf-threads-toggle").focus()
        geometry = page.locator(".lf-threads-toggle").evaluate(
            """control => {
                  const banner = control.closest('.lf-banner').getBoundingClientRect();
                  const toolbar = control.parentElement.getBoundingClientRect();
                  const box = control.getBoundingClientRect();
                  const style = getComputedStyle(control);
                  const outset = parseFloat(style.outlineWidth) +
                    parseFloat(style.outlineOffset);
                  return {banner: {top: banner.top, bottom: banner.bottom},
                          toolbar: {top: toolbar.top, bottom: toolbar.bottom},
                          ring: {top: box.top - outset, bottom: box.bottom + outset}};
                }"""
        )
        for item in ("toolbar", "ring"):
            # Centered flex boxes round to device pixels independently of the
            # banner's stated height; subpixel overhang is not a clipped aim.
            assert (
                geometry[item]["top"] >= geometry["banner"]["top"] - 1
                and geometry[item]["bottom"] <= geometry["banner"]["bottom"] + 1
            ), f"the wide coarse {item} escaped its banner at {width}px: {geometry}"

    # The browser's root is Leaf's page scrollport, and native touch beginning in
    # fixed chrome reaches it. The row itself has nothing to travel along: what it
    # cannot hold is behind its menu, so a finger dragged sideways across it moves
    # nothing rather than uncovering a control that was hiding off the edge.
    cdp = context.new_cdp_session(page)
    resized(page, 390, 700)
    page.wait_for_function(
        "() => getComputedStyle(document.scrollingElement).overflowY !== 'hidden'"
    )
    actions = page.locator(".lf-banner-actions")
    page.evaluate(
        """async () => {
              const toolbar = await window.__lfCheckApi();
              for (let i = 0; i < 3; i++) {
                const button = document.createElement('button');
                button.className = 'lf-ui lf-btn';
                button.textContent = `Secondary touch destination ${i + 1}`;
                toolbar.registerBannerControl({
                  key: `test-touch-secondary-${i}`,
                  control: button,
                  rank: toolbar.BANNER_CONTROL_RANK.blanket + (i + 1) / 10,
                  row: { label: button.textContent, group: "page" },
                });
              }
            }"""
    )
    crowded = actions.evaluate(
        "el => ({shown: el.clientWidth, needed: el.scrollWidth,"
        " folded: document.querySelector('.lf-banner-menu').children.length})"
    )
    assert crowded["folded"] >= 3 and crowded["shown"] == crowded["needed"], (
        f"the crowded touch row did not fold what it could not hold: {crowded}"
    )
    point = actions.bounding_box()
    x = point["x"] + point["width"] / 2
    y = point["y"] + point["height"] / 2
    page.evaluate("() => { document.scrollingElement.scrollTop = 200; }")
    _touch_drag(cdp, x, y, dy=-160)
    page.wait_for_function("() => document.scrollingElement.scrollTop > 200")
    vertical = page.evaluate(
        "() => ({toolbar: document.querySelector('.lf-banner-actions').scrollLeft,"
        " page: document.scrollingElement.scrollTop,"
        " overflow: getComputedStyle(document.scrollingElement).overflowY})"
    )
    assert (
        vertical["toolbar"] == 0
        and vertical["page"] > 200
        and vertical["overflow"] != "hidden"
    ), f"a vertical touch over the row never reached the page: {vertical}"
    page.evaluate("() => { document.scrollingElement.scrollTop = 200; }")
    _touch_drag(cdp, x, y, dx=-160)
    horizontal = page.evaluate(
        "() => ({toolbar: document.querySelector('.lf-banner-actions').scrollLeft,"
        " page: document.scrollingElement.scrollTop})"
    )
    assert horizontal["toolbar"] == 0, (
        f"the row still had a strip of itself to drag along: {horizontal}"
    )

    resized(page, 1200, 700)
    status = page.locator(".lf-banner-status").bounding_box()
    page.evaluate("() => { document.scrollingElement.scrollTop = 200; }")
    _touch_drag(
        cdp,
        status["x"] + status["width"] / 2,
        status["y"] + status["height"] / 2,
        dy=-160,
    )
    page.wait_for_function("() => document.scrollingElement.scrollTop > 200")
    assert page.evaluate("() => document.scrollingElement.scrollTop") > 200, (
        "the status half of the fixed banner remained a dead touch-scroll strip"
    )


def test_forced_colors_restore_a_real_outline_to_shadow_focused_fields(browser, serve):
    """High-contrast mode keeps a real outline on the focused comment frame."""
    context = browser.new_context(
        viewport={"width": 420, "height": 800}, forced_colors="active"
    )
    page = open_page(browser, serve(LONG_PAGE), context=context)
    box = page_comment(page)
    focus = box.evaluate(
        "el => { const s = getComputedStyle(el.closest('.lf-compose-field'));"
        " return {style: s.outlineStyle, width: s.outlineWidth}; }"
    )
    assert focus["style"] != "none" and focus["width"] != "0px", focus


def test_the_neighbour_reading_detects_a_whole_row_moving_on_press(browser):
    """Moving the containing row must not cancel a control's screen displacement."""
    page = browser.unwatched.new_page()
    page.set_viewport_size({"width": 800, "height": 600})
    page.set_content("""
      <div class="lf-playground-actions">
        <button id="move" onclick="this.parentElement.style.transform =
          this.parentElement.style.transform ? 'translate(2000px, 24px)' :
            'translate(32px, 24px)'">Move row</button>
        <button>Neighbour</button>
      </div>
    """)
    page.evaluate(DEFINE_BOXES)
    before = page.locator("#move").evaluate(NEIGHBOURHOOD, NEIGHBOUR)
    assert before["names"] == ['button "Neighbour"']
    assert displaced(before, page.evaluate("() => window.__lfBoxes()")) == []

    page.locator("#move").click()
    assert displaced(before, page.evaluate("() => window.__lfBoxes()")) == [
        'button "Neighbour" moved by [32, 24, 0, 0] (left, top, width, height)'
    ]
    # Moving beyond the viewport is displacement too, not hiding the control.
    page.locator("#move").click()
    assert page.get_by_role("button", name="Neighbour").bounding_box()["x"] > 800
    assert displaced(before, page.evaluate("() => window.__lfBoxes()")) == [
        'button "Neighbour" moved by [2000, 24, 0, 0] (left, top, width, height)'
    ]


def test_a_seat_thread_leaves_the_pick_it_is_about_live(browser, serve):
    """The user's own remark must not lock the control it is a remark about.

    A thread standing in the widget's seat takes the decision off the user's
    list — the banner stops counting it — but answers nothing, so the press that would
    answer it is still live. This is the browser half of the split, and the half the
    user meets first: the POST door only sees a hand-posted event, while here
    the controller reading paints the control and its dispatcher guards the press, and
    the module has already painted the answer by the time either runs. Reading the
    user's list at this door therefore does not refuse the press so much as swallow
    it — the widget flips, nothing is logged, no notice fires, and the next poll puts it
    back with nothing anywhere saying why.

    The subject is the project widget SEATED_ASK_ENTRY declares, whose seat is where a
    user most often starts such a thread; any thread anchored on an ask splits it the
    same way, and the reading under test never asks which widget it is."""
    url = serve(
        leaf_page(
            "seated eligibility",
            '<h1 id="heading">Choose</h1><lf-ask id="pick-decision">'
            "<h2>Cap the retries?</h2>"
            '<lf-verdict id="pick" asks>Three attempts, then stop.</lf-verdict>'
            "</lf-ask>",
        ),
        layer_registry=SEATED_ASK_LAYER,
        layer_widgets=SEATED_ASK_WIDGETS,
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "pick"},
            "text": "neither — cap the retries instead",
        },
    )
    page = open_page(browser, url)
    # Off the user's list, which is the whole reason the two readings differ here.
    expect_asks_answered(page, "0/1")

    page.get_by_role("button", name="Accept").click()
    round_trip(page)

    expect(page.get_by_role("button", name="Accepted")).to_have_count(1)
    # The log is what holds this, and the control above cannot: the module paints the
    # answer before either guard runs, so with the wrong reading at this door the press
    # reads exactly as it does here and the log stays empty.
    assert [event["action"] for event in actions(serve.page_dir)] == ["settle"]


def test_a_marked_element_draws_nothing_under_the_pointer_and_a_complete_row_contour(
    browser, serve
):
    """An element's comment draws no contour at rest, nor while the pointer rests inside
    the element, which is where a reader's mouse sits. The hand still says a press opens
    the thread. Its row in Threads raises one complete boundary that the element's own
    children do not paint over, in a window wide enough that the open panel covers none
    of it."""
    context = browser.new_context(
        viewport={"width": 1801, "height": 900},
        color_scheme="light",
        device_scale_factor=2,
    )
    url = serve(REPLAYED_PAGE)
    for ident in ("approach", "col-doing"):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": "Say more about this.",
                "anchor": {"section": ident},
            },
        )
    page = open_page(browser, url, context=context)
    ink = tuple(int(n) for n in re.findall(r"\d+", token_colour(page, "--mark-ink")))
    accent = tuple(int(n) for n in re.findall(r"\d+", token_colour(page, "--accent")))
    for ident in ("approach", "col-doing"):
        target = page.locator(f"#{ident}")
        expect(target).to_have_class(re.compile(r"\blf-mark-el\b"))
        target.evaluate(
            "node => node.scrollIntoView({block: 'center', inline: 'nearest', "
            "behavior: 'instant'})"
        )
        box = target.bounding_box()
        inside = (box["x"] + 6, box["y"] + box["height"] / 2)
        page.mouse.move(*inside)
        expect(page.locator("body")).to_have_class(re.compile(r"\blf-over-mark\b"))
        expect(page.locator(f'.lf-visual-mark[data-for="{ident}"]')).to_have_count(0)
        rest = mark_edges(page, ident, ink)
        assert all(seen == {0} for seen in rest.values()), (
            f"the comment on #{ident} drew a contour under the pointer: {rest}"
        )

        # The row in Threads raises it. Threads lists the page's threads in page order.
        page.locator(".lf-threads-toggle").click()
        page.locator(".lf-threads > .lf-thread").nth(
            ("approach", "col-doing").index(ident)
        ).locator(":scope > .lf-thread-summary").hover()
        expect(page.locator(f'.lf-visual-mark[data-for="{ident}"]')).to_have_class(
            re.compile(r"\blf-visual-mark-hover\b")
        )
        edges = mark_edges(page, ident, accent)
        assert all(seen == {4} for seen in edges.values()), (
            f"the contour its row in Threads raises on #{ident} was incomplete: {edges}"
        )
        page.locator(".lf-threads-toggle").click()


def test_the_poll_leaves_the_banner_where_it_was(browser, serve):
    """The other half of the same rule, for the changes nobody asked for.

    A press has a line — the row the pressed control stands on, where the next gesture
    is already aimed — and below it the page is content and may move. News arriving on
    the poll has no gesture at all, so there is no line to draw: the user was
    somewhere else entirely, and every control in the chrome is a control they are
    holding. The document may still change under them, because a fact arriving is what
    they are here to see; its resulting destination may not be. A control whose own words
    the news rewrote may grow or shrink into free room, as the status press does when the
    sentence it carries changes; nothing else may move for it.

    The banner is where all of it lands, and it is packed to the right against a spacer,
    which decides who pays. A control that grows moves itself and everything to its
    *left*; everything to its right keeps its place. So `Threads: 9` becoming
    `Threads: 10` — a comment posted from the terminal while the user reads —
    slid the version picker 6px left, and the Accept all a second tab's decision puts
    away took the New-version chip with it.

    Driven by writing the events a real one would leave, since that is what the page
    reads either way, and there is no other way to reach this half: every gesture the
    press sweep above can make is one the user made, and none of these are."""
    # Three pending suggestions, so the Accept all count has somewhere to go before it
    # runs out; sign-off asked, so the row is the full one; nine comments already, so the
    # tenth crosses a digit; and pinned, so a v2 landing leaves the page where it is and
    # offers the chip rather than following it.
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html, comments=9)
    d = serve.page_dir
    page = open_page(browser, url, pin=True)
    comments = ".lf-banner .lf-threads-toggle"
    accept_all = '[title^="Accept every"]'
    page.wait_for_function(
        f"() => document.querySelector('{comments}').textContent === 'Threads: 9'"
    )
    page_at_rest(page)

    def publish_v2():
        stamp_page(d, html, "two")

    # The same events a second tab's presses would have posted, which is the only way one
    # user's browser hears about another's decisions.
    def decide(*widgets):
        for widget in widgets:
            append_command(
                d,
                {
                    "kind": "action",
                    "author": "user",
                    "revision": 1,
                    "widget": widget,
                    "action": "decide",
                    "detail": {"outcome": "accept"},
                },
            )

    for what, drive, arrived in [
        (
            "a tenth comment arrives",
            lambda: append_carried_log_record(
                d,
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "A tenth.",
                },
            ),
            f"() => document.querySelector('{comments}').textContent === 'Threads: 10'",
        ),
        (
            "a new version is published",
            publish_v2,
            # Legible wherever the fold has put it: on the row in its own words, or behind
            # the door with the door saying there is something there.
            (
                "() => { const chip = document.querySelector('.lf-latest-chip');"
                "  const door = document.querySelector('.lf-banner-more');"
                "  return chip.checkVisibility({visibilityProperty: true})"
                "    || (chip.classList.contains('lf-news-shown')"
                "        && door.hasAttribute('data-lf-news')); }"
            ),
        ),
        (
            "another tab decides two of the three pending suggestions",
            lambda: decide("sug-refill", "sug-thistle"),
            (
                f"() => document.querySelector('{accept_all}')"
                ".textContent === 'Accept all (1)'"
            ),
        ),
        (
            "another tab decides the last one",
            lambda: decide("sug-in-card"),
            # Gone, asked the way it is now gone: a control that has stood on this row keeps
            # its room, so its box is exactly what must not have changed here.
            (
                f"() => !document.querySelector('{accept_all}')"
                f" || !document.querySelector('{accept_all}')"
                ".checkVisibility({visibilityProperty: true})"
            ),
        ),
    ]:
        page.evaluate(DEFINE_BOXES)
        before = page.evaluate(BANNER_WATCH, NEIGHBOUR)
        assert len(before["names"]) >= 4, (
            f"before {what} the banner was showing only {before['names']}, which is "
            "fewer controls than it always has — this step asserts almost nothing"
        )
        drive()
        page.wait_for_function(arrived)
        page_at_rest(page)
        moved = displaced(before, page.evaluate("() => window.__lfBoxes()"), news=True)
        assert not moved, f"{what} and the banner moved:\n  " + "\n  ".join(moved)

    # The two primary controls keep their reserved words when the row narrows.
    holds_its_width = (
        "(names) => Object.fromEntries(names.map((s) => "
        "  [s, document.querySelector('.lf-banner-actions > ' + s)?.offsetWidth ?? null]))"
    )
    named = [
        ".lf-threads-toggle",
        ".lf-signoff",
    ]
    wide = page.evaluate(holds_its_width, named)
    # Narrowed, but not past the covering breakpoint: that row deliberately spends less
    # padding, so its controls are legitimately a few pixels narrower and a comparison
    # across it would read that as the collapse this is about.
    resized(page, 900, 900)
    narrow = page.evaluate(holds_its_width, named)
    stayed = {name: width for name, width in narrow.items() if width is not None}
    assert len(stayed) >= 2, f"the primary row lost one of its controls: {stayed}"
    assert stayed == {name: wide[name] for name in stayed}, (
        f"a primary control changed width: {stayed} against {wide}"
    )


STATUS_PRESS = """() => {
  const press = document.querySelector('.lf-status-button');
  const text = press.querySelector('.lf-status-text');
  const status = document.querySelector('.lf-banner-status');
  const roomRight = status.getBoundingClientRect().right
    - parseFloat(getComputedStyle(status).paddingRight);
  const box = press.getBoundingClientRect();
  return {left: box.left, top: box.top, right: box.right, roomRight,
          words: text.textContent, shown: text.clientWidth, needed: text.scrollWidth};
}"""


STATUS_COUNTS = """() => {
  const counts = document.querySelector('.lf-status-queues');
  const box = counts.getBoundingClientRect();
  const bar = document.querySelector('.lf-banner');
  const banner = bar.getBoundingClientRect();
  // Where the banner's rows end: its rule below them draws no row.
  const rowsEnd = banner.bottom - parseFloat(getComputedStyle(bar).borderBottomWidth);
  const meets = (other) => box.left < other.right - 0.5 && other.left < box.right - 0.5
    && box.top < other.bottom - 0.5 && other.top < box.bottom - 0.5;
  const others = [document.querySelector('.lf-banner-status'),
    ...document.querySelectorAll('.lf-banner-actions > :not([hidden])')];
  const approval = document.querySelector('.lf-banner-actions > .lf-signoff');
  // A room cuts its words inside its own child (controls.css), which the control's
  // scroll width does not see.
  const words = (n) => n.querySelector('[data-lf-room] > *') ?? n;
  return {shown: words(counts).clientWidth, needed: words(counts).scrollWidth,
          left: box.left, top: box.top, inert: counts.inert,
          statusLeft: document.querySelector('.lf-status-button').getBoundingClientRect().left,
          statusBottom: document.querySelector('.lf-banner-status').getBoundingClientRect().bottom,
          inBanner: box.left >= banner.left && box.right <= banner.right
            && box.top >= banner.top && box.bottom <= banner.bottom,
          drawn: box.top < rowsEnd - 0.5 && box.bottom > banner.top + 0.5,
          approval: approval?.checkVisibility()
            ? {shown: words(approval).clientWidth, needed: words(approval).scrollWidth}
            : null,
          overlaps: others.filter((n) => meets(n.getBoundingClientRect()))
            .map((n) => n.className)};
}"""


@pytest.mark.parametrize(("width", "counts_drawn"), [(1280, True), (390, False)])
def test_the_status_press_grows_into_free_room_and_moves_nothing(
    browser, serve, width, counts_drawn
):
    """The status press is as wide as its words: its ring and its hit box are the
    sentence's, not the empty banner's. As the sentence the agent declares grows, the
    press grows rightward into the room the controls leave, and nothing else on the banner
    moves; once that room runs out its words truncate rather than push More. Approval and
    the agent's On count stay whole throughout. At 390 the status shares the phone's
    one row with Threads and More, Approval and On me stand behind More, and the count
    gives way to the sentence, which keeps what the two controls leave."""
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    page = open_page(browser, url)
    resized(page, width, 844)

    def say(detail):
        working(serve.page_dir, detail)
        told(page)
        page.wait_for_function(
            "(words) => document.querySelector('.lf-status-text').textContent === words",
            arg=f"Claude working — {detail}",
        )
        page_at_rest(page)
        return page.evaluate(STATUS_PRESS)

    short = say("tests")
    assert short["shown"] >= short["needed"], short
    # A press spanning the room would end at its edge; a phone's room is narrow.
    assert short["right"] < short["roomRight"] - 20, (
        f"a short status press still spans the banner's free room: {short}"
    )
    # The page's three suggestions and required approval wait on the user in
    # On me. The page task waits on the agent, so the agent's count stands beside status.
    expect(page.locator(".lf-queue")).to_have_text("On me: 4")
    expect(page.locator(".lf-status-queues")).to_have_text("On Claude: 1")
    page.evaluate(DEFINE_BOXES)
    beside = page.evaluate(
        BANNER_WATCH, f":is({NEIGHBOUR}, .lf-status-queues):not(.lf-status-button)"
    )
    assert any("lf-banner-more" in name for name in beside["names"]), beside["names"]

    # Longer, and still inside a phone's room beside Threads and More, with room to
    # spare for Linux's wider sans and the agent's name.
    longer = say("tests again")
    assert longer["shown"] >= longer["needed"], longer
    assert (longer["left"], longer["top"]) == (short["left"], short["top"])
    assert longer["right"] > short["right"], (short, longer)
    moved = displaced(beside, page.evaluate("() => window.__lfBoxes()"))
    assert not moved, "a longer status moved the banner:\n  " + "\n  ".join(moved)

    endless = say("checking every thread on the page before recording the update " * 4)
    assert endless["shown"] < endless["needed"], (
        f"a sentence longer than the room was shown whole: {endless}"
    )
    assert endless["right"] <= endless["roomRight"] + 0.5, endless
    # The sentence gives up its room, and the counts never cut Approval: where they
    # are drawn they stand whole, inside the banner, clear of the status and every
    # control, and on a phone's one row the banner leaves them out whole, with
    # Approval behind More.
    counts = page.evaluate(STATUS_COUNTS)
    if counts_drawn:
        assert counts["approval"], counts
        assert counts["approval"]["shown"] >= counts["approval"]["needed"], counts
    else:
        assert counts["approval"] is None, counts
    assert counts["drawn"] == counts_drawn, counts
    # The counts are a press; one the banner does not draw takes no Tab stop.
    assert counts["inert"] != counts_drawn, counts
    if counts_drawn:
        assert counts["shown"] >= counts["needed"] > 0, counts
        assert counts["inBanner"] and not counts["overlaps"], counts
    assert (endless["left"], endless["top"]) == (short["left"], short["top"])
    moved = displaced(beside, page.evaluate("() => window.__lfBoxes()"))
    assert not moved, "a status past its room pushed the banner:\n  " + "\n  ".join(
        moved
    )


def test_the_counts_lead_the_second_row_where_the_run_leaves_room(browser, serve):
    """Just wider than a phone held upright, the banner's status sentence has the first
    row, and the agent's On count leads the second, under the sentence's start, where
    the run leaves it room whole. A finger's search steps share that row: the count
    stands whole beside them where the font leaves it room, or gives way to them, never
    cutting a step or being cut itself, and comes back where it stood once the search
    closes."""
    context = browser.new_context(
        viewport={"width": 490, "height": 800}, has_touch=True, is_mobile=True
    )
    url = serve(SUGGESTION_PAGE)
    # A comment the agent owes a reply, so there is an agent's count to stand there.
    panel_comment(serve.page_dir, "Is the feeder sized right?")
    page = open_page(browser, url, context=context)
    expect(page.locator(".lf-status-queues")).to_have_text("On Claude: 1")
    page_at_rest(page)
    resting = page.evaluate(STATUS_COUNTS)
    assert resting["drawn"] and resting["inBanner"] and not resting["inert"], resting
    assert resting["shown"] >= resting["needed"] > 0, resting
    assert not resting["overlaps"], resting
    assert resting["left"] == pytest.approx(resting["statusLeft"], abs=1), resting
    assert resting["top"] >= resting["statusBottom"] - 0.5, resting

    page.keyboard.press("/")
    page.keyboard.type("feeder")
    expect(
        page.locator(".lf-banner-actions > .lf-btn", has_text="Next")
    ).to_be_visible()
    page_at_rest(page)
    searching = page.evaluate(STATUS_COUNTS)
    # Whether "On Claude: 1" fits beside the steps is the font's to say: macOS's leaves it
    # room at this width and Linux's does not. Either way it is drawn whole and live, or
    # gone and out of reach.
    assert searching["drawn"] != searching["inert"], searching
    if searching["drawn"]:
        assert searching["inBanner"] and not searching["overlaps"], searching
    clipped = page.evaluate(BANNER_ROWS)["clipped"]
    assert not clipped, f"the search steps were cut off: {clipped}"

    page.keyboard.press("Escape")
    expect(page.locator(".lf-banner-actions > .lf-btn", has_text="Next")).to_be_hidden()
    page_at_rest(page)
    back = page.evaluate(STATUS_COUNTS)
    assert (back["drawn"], back["inert"], back["left"], back["top"]) == (
        True,
        False,
        resting["left"],
        resting["top"],
    ), (resting, back)


def test_a_phone_s_one_row_seats_a_finger_s_steps_and_leaves_the_counts_out(
    browser, serve
):
    """On a phone the banner is one row and the queue counts stand down, inert, which
    the status's disclosure still says. A finger's search steps take Threads' place on
    that row whole, the status keeping what they leave, and the banner keeps its height
    while they stand and after they go."""
    context = browser.new_context(
        viewport={"width": 390, "height": 800}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(SUGGESTION_PAGE), context=context)
    expect(page.locator(".lf-status-detail")).to_contain_text("Waiting on me")
    page_at_rest(page)
    resting = page.evaluate(BANNER_ROWS)
    assert_banner_as_stated(resting, wrapped=False)
    counts = page.evaluate(STATUS_COUNTS)
    assert not counts["drawn"] and counts["inert"], counts

    page.keyboard.press("/")
    page.keyboard.type("feeder")
    expect(
        page.locator(".lf-banner-actions > .lf-btn", has_text="Next")
    ).to_be_visible()
    page_at_rest(page)
    searching = page.evaluate(BANNER_ROWS)
    assert_banner_as_stated(searching, wrapped=False)
    assert "Close search" in searching["controls"], searching
    assert page.locator(".lf-status-button").bounding_box()["width"] > 0

    page.keyboard.press("Escape")
    expect(page.locator(".lf-banner-actions > .lf-btn", has_text="Next")).to_be_hidden()
    page_at_rest(page)
    back = page.evaluate(BANNER_ROWS)
    assert back["main"] == pytest.approx(resting["main"], abs=0.5), (resting, back)


def test_the_band_stays_over_the_covering_leaves_drawer(browser, serve, other_leaf):
    """A drawer stands under the bottom bar, its list ending above the band's height, and
    the Pages drawer, which always covers the page, is no exception: the band states the
    keys the drawer answers and stays over it and its scrim, its More control live. The
    covering drawer used to stand over the band, hiding the hints it painted for the drawer
    ("open it in a tab", "close pages") under the drawer and the scrim, where the Asks
    drawer, standing beside the page, left them in view."""
    page = open_page(browser, serve(LONG_PAGE))
    resized(page, 1440, 900)
    expect(page.locator(".lf-others")).to_have_text("All pages (2)")
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    drawer = page.locator(".lf-others-panel")
    assert drawer.evaluate("surface => surface.closest('dialog').matches(':modal')")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("close pages")
    reading = page.evaluate(
        """() => {
          const band = document.querySelector('.lf-shortcut-bar');
          const more = band.querySelector('.lf-shortcut-more');
          const box = more.getBoundingClientRect();
          const hit = document.elementFromPoint(box.x + box.width / 2,
                                                box.y + box.height / 2);
          const z = (selector) =>
            Number(getComputedStyle(document.querySelector(selector)).zIndex);
          return {more: more.contains(hit), inert: Boolean(band.closest('[inert]')),
                  over: z('.lf-shortcut-bar') > Math.max(
                    z('.lf-others-panel'), z('.lf-auxiliary-scrim'))};
        }"""
    )
    assert reading == {"more": True, "inert": False, "over": True}, reading
    page.keyboard.press("Escape")
    expect(drawer).not_to_be_visible()
    expect(page.locator(".lf-shortcut-bar")).not_to_have_attribute(
        "data-lf-over-covering", ""
    )


def test_the_banner_uses_the_page_mark_and_puts_each_edge_by_its_panel(
    browser, serve, other_leaf
):
    """The page mark and fixed primary/secondary seats survive every width."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    stamp_page(serve.page_dir, html, "two")
    page = open_page(browser, url)
    expect(page.locator(".lf-others")).to_have_text("All pages (2)")
    expect(page.locator(".lf-signoff")).to_be_visible()

    mark = page.locator(".lf-banner .lf-dot")
    mask = mark.evaluate("el => getComputedStyle(el).maskImage")
    assert "/icon.svg" in mask, f"the banner mark came from {mask!r}, not icon.svg"
    page.emulate_media(forced_colors="active")
    forced = mark.evaluate(
        """el => ({mark: getComputedStyle(el).backgroundColor,
                    banner: getComputedStyle(el.closest('.lf-banner')).backgroundColor})"""
    )
    assert forced["mark"] != forced["banner"], (
        "the masked page mark disappears into the forced-colors banner"
    )
    page.emulate_media(forced_colors="none")

    def actions():
        return page.evaluate(
            """() => {
                 const toolbar = document.querySelector('.lf-banner-actions');
                 const menu = document.querySelector('.lf-banner-menu');
                 return [...menu.children, ...toolbar.children].map(el =>
                   [['others', 'lf-others'], ['latest', 'lf-latest-chip'],
                    ['queue', 'lf-queue'], ['version', 'lf-version'],
                    ['comments', 'lf-threads-toggle'], ['signoff', 'lf-signoff']]
                     .find(([, cls]) => el.classList.contains(cls))?.[0])
                   .filter(Boolean);
               }"""
        )

    # A phone moves Approval and On me to the head of More, off the row.
    desk = ["others", "latest", "version", "signoff", "queue", "comments"]
    phone = ["signoff", "queue", "others", "latest", "version", "comments"]
    for width in (1200, 390, 320):
        resized(page, width, 900)
        assert actions() == (desk if width > 480 else phone)
        expect(page.locator(".lf-banner-menu > .lf-others")).to_have_count(1)
        expect(page.locator(".lf-banner-menu > .lf-version")).to_have_count(1)
        seat = ".lf-banner-actions" if width > 480 else ".lf-banner-menu"
        expect(page.locator(f"{seat} > .lf-signoff")).to_have_count(1)
        expect(page.locator(".lf-banner-actions > .lf-threads-toggle")).to_be_visible()
        fit = page.evaluate(
            """() => { const actions = document.querySelector('.lf-banner-actions');
              const threads = document.querySelector('.lf-threads-toggle');
              const box = threads.getBoundingClientRect();
              const edge = document.elementFromPoint(box.right - 1, box.top + box.height / 2);
              return {shown: actions.clientWidth, needed: actions.scrollWidth,
                      threads: {left: box.left, right: box.right,
                                visible: threads.checkVisibility(),
                                ownsRightEdge: edge === threads || threads.contains(edge)}}; }"""
        )
        assert fit["needed"] <= fit["shown"] + 1, fit
        assert root_overflow(page) == 0, fit
        assert fit["threads"]["visible"] and fit["threads"]["ownsRightEdge"], fit
        assert 0 <= fit["threads"]["left"] < fit["threads"]["right"] <= width, fit


def test_a_panel_row_follows_its_pages_status_live(
    browser, serve, other_leaf, tmp_path
):
    """The panel is a status surface, not a snapshot: a neighbour's declaration
    changing on disk repaints its row at the next poll, in place, and the row's
    hover follows it, being the same account written where there is room for it
    whole."""
    _, other_dir = other_leaf
    page = open_page(browser, serve(LONG_PAGE))
    # The key is live once the list has arrived, which the button's count states.
    expect(page.locator(".lf-others")).to_have_text("All pages (2)")
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    row = page.locator("a.lf-others-row")
    expect(row.locator(".lf-others-line")).to_have_text("Working — running the suite")
    declare_work(other_dir, "recording the demo")
    told(page)
    expect(row.locator(".lf-others-line")).to_have_text("Working — recording the demo")
    # A neighbour waiting on its own user says so in this seat's shorter words, and
    # in the same term its banner uses, with what it is waiting for: the panel is
    # where a user picks which page to go to. The hover holds it whole, since the
    # line ellipsizes at the panel's width, and it is the row's hover and not the
    # line's, the innermost title winning where two overlap.
    end_work(other_dir)
    cleanup_model.write_json(
        other_dir / "status.json",
        {
            "state": "waiting",
            "detail": "pick a storage engine",
            "ts": cleanup_model.now_iso(),
        },
    )
    told(page)
    line = row.locator(".lf-others-line")
    expect(line).to_have_text("Awaits — pick a storage engine")
    expect(row).to_have_attribute(
        "title",
        f"The other leaf\n{tmp_path / 'other-work'}\nAwaits — pick a storage engine",
    )
    assert line.get_attribute("title") is None, (
        "the line carries a tooltip of its own again, which wins under the pointer "
        "over the row's whole account"
    )


def test_a_closed_leaf_clears_itself_off_the_drawer(browser, serve, other_leaf):
    """A closed leaf leaves the drawer on the poll that says so. Its server stays
    up — a persistent one for good — so the row would otherwise stand forever and the
    count a user glances at to find who needs them would become a tally of
    everything that has ever run here. This page's own row never drops — a user
    looking at a closed page is still looking at it — so a drawer with nothing live
    left on it still says where the user is, and the count says (1) for it."""
    _, other_dir = other_leaf
    page = open_page(browser, serve(LONG_PAGE))
    btn = page.locator(".lf-others")
    expect(btn).to_have_text("All pages (2)")
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    rows = page.locator("a.lf-others-row")
    expect(rows).to_have_count(1)
    rows.first.focus()
    cleanup_model.write_json(
        other_dir / "status.json",
        {"state": "idle", "detail": "", "ts": cleanup_model.now_iso()},
    )
    told(page)
    expect(rows).to_have_count(0)
    expect(btn).to_have_text("All pages (1)")
    expect(page.locator(".lf-others-self .lf-others-title")).to_have_text("long")
    expect(page.locator(".lf-others-panel")).to_be_focused()
    # The open panel remains the modal destination after its last link leaves. Its own
    # nav is the fallback landing, and its global destination remains the same toggle as the
    # banner door even though that inert door is unavailable to a pointer.
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(page.locator(".lf-others-panel")).not_to_be_visible()
    expect(btn).to_have_attribute("aria-expanded", "false")
    # Nothing live remains to reopen it: its button stands while the panel does and
    # stands down with it, which is the count's other half.
    told(page)
    expect(btn).not_to_be_visible()


def test_a_removed_leaf_hands_focus_on_without_revealing_the_old_reading(
    browser, serve, other_leaf
):
    """A disappearing focused row preserves the later rows reached with the wheel."""
    page = open_page(browser, serve(LONG_PAGE))
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(page.locator(".lf-others-panel")).to_have_class(re.compile(r"\bopen\b"))
    page.evaluate(
        "document.querySelector('.lf-others-panel').getAnimations().forEach(a => a.finish())"
    )
    page.evaluate(
        """async () => {
          const list = document.querySelector('lf-leaves-list');
          const row = list.model.rows.find(row => !row.self);
          window.auditLeaves = Array.from({length: 30}, (_,index) => ({
            ...row, key: `audit-${index}`, href: `${row.href}&audit=${index}`,
            title: `Live leaf ${index}`,
          }));
          await list.present({...list.model, rows: window.auditLeaves});
        }"""
    )
    page.keyboard.press("Home")
    rows = page.locator("a.lf-others-row")
    expect(rows.first).to_be_focused()
    box = page.locator("lf-leaves-list")
    area = box.bounding_box()
    assert area is not None
    page.mouse.move(area["x"] + 50, area["y"] + 100)
    page.mouse.wheel(0, 700)
    page.wait_for_function("document.querySelector('lf-leaves-list').scrollTop > 500")
    scroll_settled(page, "lf-leaves-list")
    expect(rows.first).to_be_focused()
    reading = rows.nth(15).bounding_box()
    assert reading is not None
    page.evaluate(
        """async () => {
          const list = document.querySelector('lf-leaves-list');
          await list.present({...list.model, rows: window.auditLeaves.slice(1)});
        }"""
    )
    expect(rows.first).to_be_focused()
    after = rows.nth(14).bounding_box()
    assert after is not None
    assert abs(after["y"] - reading["y"]) <= 1


def test_a_leaves_clock_change_reopens_only_its_same_epoch_presentation(
    browser, serve, other_leaf
):
    """A time-only Leaves repaint repairs presentation at the current epoch."""
    now = datetime.now().astimezone()
    page = browser.new_page()

    def quiet_neighbor(route):
        answer = route.fetch()
        state = answer.json()
        for neighbor in state["others"]:
            activity = neighbor["activity"]
            activity.update(kind="away", dropped=False, ts=now.isoformat())
            activity["counts"]["overdue"] = 1
        route.fulfill(response=answer, json=state)

    # The test's neighbor arrives through the real state boundary. Its clock alone
    # changes afterward; no second runtime reading is mutated beside the publisher.
    page.route("**/api/state*", quiet_neighbor)
    page.goto(serve(LONG_PAGE), wait_until="load")
    wait_until_ready(page)
    told(page, until=lambda state: bool(state["others"]))
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    before = page.evaluate(
        """async () => {
          const presentation = await window.__lfCheckApi();
          const list = document.querySelector('lf-leaves-list');
          const schedule = list.scheduleUpdate.bind(list);
          let release;
          const held = new Promise(resolve => { release = resolve; });
          let armed = true;
          list.scheduleUpdate = () => {
            if (!armed) return schedule();
            armed = false;
            window.leavesClockHeld = true;
            return held.then(schedule);
          };
          window.releaseLeavesClock = release;
          window.leavesPresentation = presentation;
          const reading = presentation.readApplicationPresentation();
          return {
            semanticEpoch: reading.semanticEpoch,
            presentedEpoch: reading.presentedEpoch,
          };
        }"""
    )
    expect(page.locator("a.lf-others-row .lf-others-line")).to_have_text(
        "Quiet (just now)"
    )
    page.unroute("**/api/state*", quiet_neighbor)
    page.route("**/api/state*", refuse)
    page.clock.set_fixed_time(now + timedelta(minutes=1))
    page.wait_for_function("window.leavesClockHeld")
    held = page.evaluate(
        """() => {
          window.leavesReady = false;
          leavesPresentation.whenApplicationPresented().then(() => {
            window.leavesReady = true;
          });
          const reading = leavesPresentation.readApplicationPresentation();
          return {
            pending: reading.pending,
            semanticEpoch: reading.semanticEpoch,
            presentedEpoch: reading.presentedEpoch,
            ready: leavesReady,
          };
        }"""
    )
    assert held == {
        "pending": ["leaves"],
        "semanticEpoch": before["semanticEpoch"],
        "presentedEpoch": before["presentedEpoch"],
        "ready": False,
    }
    page.evaluate("releaseLeavesClock()")
    page.wait_for_function("window.leavesReady")
    expect(page.locator("a.lf-others-row .lf-others-line")).to_have_text(
        "Quiet (1m ago)"
    )
    assert page.evaluate(
        """() => {
          const reading = leavesPresentation.readApplicationPresentation();
          return [reading.semanticEpoch, reading.presentedEpoch];
        }"""
    ) == [before["semanticEpoch"], before["presentedEpoch"]]


def test_a_press_on_the_pages_words_is_a_newer_word_than_a_waiting_hold(browser, serve):
    """A hold hands focus back only if the user has not moved on since it began. With no
    stop on body, a press on the page's words takes focus off the control and puts it
    nowhere, with no focusin to count, so a hold still waiting pulled the user back
    from the words they had chosen."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "hold",
                '<h1 id="t">Hold</h1><details id="d"><summary>More</summary>'
                "<p>Inside.</p></details><p id='words'>Words to press.</p>",
            )
        ),
    )
    page.keyboard.press("Tab")
    page.locator("#d > summary").focus()
    page.evaluate(
        """async () => {
          const { holdFocus } = await window.__lfWidgetApi();
          window.__restore = holdFocus(document.querySelector('main'));
        }"""
    )
    page.locator("#words").click()
    assert page.evaluate("() => document.activeElement === document.body")
    assert page.evaluate("() => window.__restore()") is False
    assert page.evaluate("() => document.activeElement === document.body")
    # Nor is the control the user left the place a later change drops them from: a
    # rebuild removing it, read after the press, holds nothing to hand them back to.
    assert (
        page.evaluate(
            """async () => {
          const { holdFocus } = await window.__lfWidgetApi();
          const details = document.querySelector('#d');
          details.remove();
          return holdFocus(details) !== null;
        }"""
        )
        is False
    )


def test_a_page_nobody_has_touched_scrolls_from_the_keyboard(browser, serve):
    """A fresh page gives ordinary keyboard scrolling to the browser's root scrollport.

    Space, PageDown, and arrows work before a user has clicked anywhere. Leaf still
    places focus on body so there is a stable page location to return to after chrome,
    but scrolling no longer depends on teaching the browser about a non-root box.

    All three keys, because they are one fact about which box the browser is scrolling
    rather than three rows in a table — a fix that reached only the key this test named
    would read as a working page here and a dead one to the user. The somewhere is
    asserted as well as the scrolling, and `body` is where focus sits by default: what
    that pins is the page itself as the place to stand, rather than a box built to hold
    the user, which would have a ring to draw and a Tab stop to spend."""
    page = open_page(browser, serve(LONG_PAGE))
    assert page.evaluate("() => document.activeElement === document.body")
    assert (
        page.evaluate("() => getComputedStyle(document.body).outlineStyle") == "none"
    ), "the page wears a focus ring before the user has pressed anything"

    for key in ("Space", "PageDown", "ArrowDown"):
        # Programmatic, so the page is still one nobody has put themselves in: a click
        # to get back to the top would be the very thing this test says is not needed.
        page.evaluate("() => { document.scrollingElement.scrollTop = 0; }")
        page.keyboard.press(key)
        try:
            page.wait_for_function(SCROLLED)
        except PlaywrightTimeout:
            # The console with it: the press can move nothing because the runtime
            # threw, and this names what it said.
            pytest.fail(
                f"{key} moved nothing on a page nobody had clicked in:\n"
                + shown(page.lf_errors)
            )
        # And then the rest of the glide, so the next key's reset lands on a scroll
        # that is over rather than on one still on its way somewhere.
        scroll_settled(page)


def test_esc_hands_the_page_back_after_it_has_closed_the_last_panel(browser, serve):
    """Closing the panel hands the user back the place they held before they opened it.

    Opened with the pointer from the page, the panel's Escape lands on the page. The click
    put focus on the toggle, but the user never chose that button: leaving them on it
    rang a control they did not stand on and handed their next Space to it, so the panel
    they had just dismissed came back and nothing said why. Opened from the keyboard, the
    toggle was the user's place, and the same press hands it back — ringed, since a
    keypress closed — with the rung below that takes them off the chrome.

    The scroll is what the landing has to hand back. Root scrolling is native now, but a
    focused button still owns Space; focus therefore returns to the page rather than
    merely blurring to nowhere."""
    page = open_page(browser, serve(LONG_PAGE, comments=1))
    toggle = page.locator(".lf-threads-toggle")
    panel = page.locator(".lf-thread-panel")
    ringed = """() => getComputedStyle(document.querySelector('.lf-threads-toggle'))
      .outlineStyle !== 'none'"""
    top = "() => document.scrollingElement.scrollTop"
    on_body = "() => document.activeElement === document.body"

    # A user reading: native Space still pages through the document from body.
    page.keyboard.press("Space")
    page.wait_for_function(SCROLLED)
    scroll_settled(page)
    was = page.evaluate(top)

    # Opened with the pointer, the focused button draws the same ring as a keyboard arrival.
    toggle.click()
    expect(panel).to_be_visible()
    expect(toggle).to_be_focused()
    assert page.evaluate(ringed)

    # Closed with the key, the user is back on the page: nothing rings, and Space is
    # the page's again rather than the button's.
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate(on_body)
    assert not page.evaluate(ringed)
    # And body wears no ring of its own, which is the thing a focus does that a blur
    # cannot: the user has to be somewhere, and the somewhere must not be drawn.
    assert (
        page.evaluate("() => getComputedStyle(document.body).outlineStyle") == "none"
    ), "landing on the page drew a ring around it"
    page.keyboard.press("Space")
    expect(panel).to_be_hidden()
    page.wait_for_function(
        "(was) => document.scrollingElement.scrollTop > was", arg=was
    )
    scroll_settled(page)

    # Opened from the keyboard, and left the same way one opened by pointer is: the
    # panel's parent is the document, so Escape lands the user there rather than on
    # the toggle that reopens it.
    toggle.focus()
    assert page.evaluate(ringed), "the control the user is standing on says nothing"
    page.keyboard.press("Enter")
    expect(panel).to_be_visible()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate("() => document.activeElement === document.body")

    # And Space is the page's again.
    page.keyboard.press("Escape")
    assert page.evaluate(on_body)
    assert not page.evaluate(ringed)


def test_a_covering_auxiliary_surface_keeps_a_replacement_document_inert(
    browser, serve
):
    """A live version can update main without reopening the covering auxiliary surface.

    The modal boundary remains authoritative while the document changes, so the page
    cannot become a pointer or keyboard target while the sheet still claims modal
    semantics. Closing restores the updated document.
    """
    source = LONG_PAGE.replace('<h1 id="t">Long</h1>', f'<h1 id="t">Long</h1>{ONE_ASK}')
    url = serve(source)
    page = open_page(browser, live_url(url))
    resized(page, 500, 640)
    toggle_queue(page)
    assert bool(page.locator("dialog:modal").count())

    revised = source.replace(
        '<h1 id="t">Long</h1>', '<h1 id="t">Long after replacement</h1>'
    )
    stamp_page(serve.page_dir, revised, "replace the document")
    told(page)
    expect(page.locator("#t")).to_have_text("Long after replacement")

    state = page.evaluate(
        """() => ({
          covered: Boolean(document.querySelector('.lf-auxiliary-envelope:modal')),
          modal: document.querySelector('.lf-queue-panel').closest('dialog').matches(':modal'),
          focusInside: document.querySelector('.lf-queue-panel').contains(document.activeElement),
        })"""
    )
    assert state == {
        "covered": True,
        "modal": True,
        "focusInside": True,
    }, f"the updated document escaped its covering auxiliary surface: {state}"

    page.get_by_role("button", name="Close the On panel").click()
    expect(page.locator(".lf-queue-panel")).not_to_have_class(re.compile(r"\bopen\b"))
    assert not bool(page.locator("dialog:modal").count())


def test_the_shared_auxiliary_scrim_marks_and_dismisses_a_covering_surface(
    browser, serve, other_leaf
):
    """A covering auxiliary surface stands above a scrim covering every inert surface."""
    page = open_page(browser, serve(LONG_PAGE))
    resized(page, 1200, 700)
    scrim = page.locator(".lf-auxiliary-scrim")
    expect(scrim).to_be_hidden()

    leaves_door = banner_control(page, ".lf-others")
    leaves_door.click()
    leaves = page.locator(".lf-others-panel")
    expect(leaves).to_have_class(re.compile(r"\bopen\b"))
    expect(scrim).to_be_visible()
    assert bool(page.locator("dialog:modal").count())
    scrim_reading = page.evaluate(
        """() => {
          const scrim = document.querySelector('.lf-auxiliary-scrim');
          const banner = document.querySelector('.lf-banner');
          const bannerBox = banner.getBoundingClientRect();
          const scrimBox = scrim.getBoundingClientRect();
          const surface = document.querySelector('.lf-others-panel');
          const drawer = document.querySelector('.lf-others-panel').getBoundingClientRect();
          const point = {x: Math.max(drawer.right + 20, innerWidth * .75), y: innerHeight / 2};
          const bannerPoint = {
            x: bannerBox.left + bannerBox.width / 2,
            y: bannerBox.top + bannerBox.height / 2,
          };
          return {
            color: getComputedStyle(scrim).backgroundColor,
            point,
            hit: document.elementFromPoint(point.x, point.y) === scrim,
            top: scrimBox.top,
            coversBanner: scrimBox.top <= bannerBox.top && scrimBox.bottom >= bannerBox.bottom,
            bannerHit: document.elementFromPoint(bannerPoint.x, bannerPoint.y) === scrim,
            bannerLayer: Number(getComputedStyle(banner).zIndex),
            scrimLayer: Number(getComputedStyle(scrim).zIndex),
            surfaceLayer: Number(getComputedStyle(surface).zIndex),
          };
        }"""
    )
    assert scrim_reading["color"] != "rgba(0, 0, 0, 0)", scrim_reading
    assert scrim_reading["hit"], scrim_reading
    assert scrim_reading["top"] == 0, scrim_reading
    assert scrim_reading["coversBanner"], scrim_reading
    assert scrim_reading["bannerHit"], scrim_reading
    assert (
        scrim_reading["surfaceLayer"]
        > scrim_reading["scrimLayer"]
        > scrim_reading["bannerLayer"]
    ), scrim_reading
    page.mouse.click(scrim_reading["point"]["x"], scrim_reading["point"]["y"])
    expect(leaves).not_to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator(".lf-banner-more")).to_be_focused()
    expect(scrim).to_be_hidden()
    assert not bool(page.locator("dialog:modal").count())

    # Threads stands over the page at every width. Where it leaves a usable page beside
    # it, there is no scrim and that page stays live; where what it leaves is a sliver —
    # a 430px phone leaves ten pixels — it covers the page.
    threads_door = page.locator(".lf-threads-toggle")
    threads_door.click()
    panel_settled(page)
    for width in (1200, 760):
        resized(page, width, 700)
        panel_settled(page)
        expect(scrim).to_be_hidden()
        assert not bool(page.locator("dialog:modal").count())
    resized(page, 430, 700)
    panel_settled(page)
    expect(scrim).to_be_visible()
    assert bool(page.locator("dialog:modal").count())
    resized(page, 1200, 700)
    panel_settled(page)
    page.get_by_role("button", name="Close threads").click()
    panel_settled(page, open=False)
    expect(threads_door).to_be_focused()


# A classic scrollbar, which the headless shell hides unless both its flag is dropped
# and the page styles one, here through a constructed sheet.
CLASSIC_SCROLLBAR = """
  document.addEventListener('DOMContentLoaded', () => {
    const sheet = new CSSStyleSheet();
    sheet.replaceSync('::-webkit-scrollbar { width: 15px; }');
    document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
  });
"""


@pytest.mark.parametrize(("width", "covers"), [(730, True), (745, False)])
def test_threads_covering_a_page_holds_while_its_lock_takes_the_scrollbar(
    scrollbar_browser, serve, width, covers
):
    """The covering boundary locks the root's scroll, and a classic scrollbar leaves
    with the lock, widening the root's client box by the bar. Threads covers the page
    where it leaves less than a usable page (320px) beside it, and the window it asks
    that of counts the bar, so the answer is the same on both sides of the lock. At
    745px a reading of the client box would find 310px beside the default panel with
    the bar and 325px without it, so its answer would turn on whether the lock was
    already held (measured: it covered, and held the lock that made its own reading
    wrong). 730px covers on either reading. Each width is read across several syncs (a
    window resize runs one), and holds the one answer."""
    context = scrollbar_browser.new_context(viewport={"width": width, "height": 700})
    page = open_page(
        scrollbar_browser,
        serve(LONG_PAGE, comments=2),
        context=context,
        init_script=CLASSIC_SCROLLBAR,
    )
    bar = page.evaluate("() => innerWidth - document.documentElement.clientWidth")
    assert bar == 15, f"the page drew no classic scrollbar, so nothing is proved: {bar}"
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    readings = []
    for _ in range(4):
        page.evaluate("() => dispatchEvent(new Event('resize'))")
        rendered(page)
        readings.append(
            page.evaluate(
                """() => ({
                  modal: document.querySelector('.lf-thread-panel')
                    .closest('dialog').matches(':modal'),
                  covered: Boolean(document.querySelector('.lf-auxiliary-envelope:modal')),
                  locked: getComputedStyle(document.scrollingElement).overflowY
                    === 'hidden',
                })"""
            )
        )
    held = {"modal": covers, "covered": covers, "locked": covers}
    assert readings == [held] * 4, (
        f"the covering boundary at {width}px did not hold one answer across its "
        f"lock: {readings}"
    )


def test_a_run_with_nothing_to_break_on_stays_inside_the_box_holding_it(browser, serve):
    """Native values and prose paths wrap within their allocated boxes at phone width."""
    page = open_page(browser, serve(UNBREAKABLE_PAGE))
    resized(page, 420, 900)
    inside = """(id) => {
                  const el = document.getElementById(id);
                  const inner = el.querySelector("[data-lf-said='value']") ?? el;
                  const range = document.createRange();
                  range.selectNodeContents(inner);
                  const style = getComputedStyle(el);
                  return range.getBoundingClientRect().right -
                         (el.getBoundingClientRect().right - parseFloat(style.paddingRight));
                }"""
    assert page.evaluate(inside, "m-token") <= 0, (
        "a metric's value paints outside its card"
    )
    assert page.evaluate(inside, "p-token") <= 0, (
        "a path in prose paints outside the column"
    )


def test_a_scroll_box_inside_a_widgets_shadow_tree_takes_the_keyboard(browser, serve):
    """Anything a mouse can scroll, a keyboard can reach — including the box a widget
    renders inside its own shadow tree. `reachScrollers` walks the tree it is handed,
    and `querySelectorAll` stops dead at a shadow boundary, so a diff was the one
    scrolling box on a page that a keyboard user had no way into: no tab stop of its
    own, and unlike a board no control inside to borrow one from. The axe sweep says
    so too, and only while some example's diff happens to carry a line this long; this
    is the same rule asked of the widget rather than of the corpus."""
    page = open_page(browser, serve(WIDE_DIFF_PAGE))
    resized(page, 420, 900)
    measured = page.locator("#wide-diff").evaluate(
        """(d) => {
        const viewport = d.shadowRoot.querySelector('code[data-code]');
        return { scrolls: Math.round(viewport.scrollWidth - viewport.clientWidth),
                 tab: viewport.tabIndex };
    }"""
    )
    # The reach, then that there was anything to reach: a diff narrow enough to fit
    # takes no tab stop and is right not to, which would pass the first assertion
    # while saying nothing about the rule.
    assert measured["scrolls"] > 0, "this diff fits, so it proves nothing"
    assert measured["tab"] == 0, "a diff that scrolls is unreachable from the keyboard"
    page.close()

    page = open_page(browser, serve(DIFF_PAGE))
    resized(page, 1200, 900)
    fitted = page.locator("#patch").evaluate(
        """(d) => [...d.shadowRoot.querySelectorAll('code[data-code]')].map(viewport => ({
          scrolls: Math.round(viewport.scrollWidth - viewport.clientWidth),
          tab: viewport.tabIndex,
        }))"""
    )
    assert fitted and all(item["scrolls"] == 0 for item in fitted), fitted
    assert all(item["tab"] == -1 for item in fitted), (
        "a diff that fits added a keyboard stop with nowhere to scroll"
    )


def test_a_hidden_control_does_not_take_a_scroll_boxes_keyboard_route(browser, serve):
    markup = leaf_page(
        "Hidden control in scroll box",
        '<h1>Review</h1><a id="before" href="#scroll">Read code</a>'
        '<div id="scroll" style="width:220px; overflow-x:auto; white-space:nowrap">'
        '<button style="visibility:hidden">Unavailable</button>'
        "<span>alpha_function_name = compute_the_overly_long_value(first_argument, second_argument)</span>"
        "</div>",
    )
    page = open_page(browser, serve(markup))
    box = page.locator("#scroll")
    assert box.evaluate("el => el.scrollWidth > el.clientWidth")
    expect(box).to_have_attribute("tabindex", "0")
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(box).to_be_focused()
    assert box.evaluate("el => el.matches(':focus-visible')")


def test_a_comment_on_a_scrolling_box_leaves_its_tab_stop_alone(browser, serve):
    """A box already holding a control of its own needs no stop of the sweep's: the
    user reaches what is out of sight through the control. A comment on the box adds
    no control to it, so one comment on a flowchart wider than the window leaves the
    keyboard its way to the half of the graph hanging off the right of it.

    Read with the comment on and off the same box, because the assertion says nothing
    unless the box would otherwise have the stop."""
    url = serve(WIDE_DIAGRAM_PAGE)
    page = open_page(browser, url)
    resized(page, 760, 900)
    diagram = page.locator("#flow")
    assert diagram.evaluate("el => el.scrollWidth > el.clientWidth"), (
        "this diagram fits its room, so it proves nothing"
    )
    expect(diagram).to_have_attribute("tabindex", "0")
    expect_comment_notes(page, "#flow", 0)

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "on-the-flow",
            "author": "user",
            "revision": 1,
            "text": "Where does the fallback go?",
            "anchor": {"section": "flow"},
        },
    )
    told(page)
    expect_comment_notes(page, "#flow", 1)
    expect(diagram).to_have_attribute("tabindex", "0")


def test_a_scroll_box_in_a_panel_reply_takes_the_keyboard(browser, serve):
    """The panel holds the same scroll boxes the page does — a reply carries whatever
    widget markup the gate allows — and its column is the narrower of the two, so a box
    that scrolls anywhere scrolls here.

    The sweep that was supposed to cover this stood where each message body is built,
    and needed two things it did not have: that body is not in the document yet, where
    `getComputedStyle` answers "" for every property, and the widget in it has not
    rendered, where the look a scroll box has arrives with the class its module sets on
    the way out. It read an empty overflow off everything it walked and had tagged
    nothing since it was written, which reads as coverage and is the only reason it
    lasted.

    The reply arrives while the panel is already open, because that is the case with
    exactly one reconcile in it. A diff renders asynchronously, so a sweep run where the
    panel inserts its nodes walks a host whose shadow root is still null, and the panel
    does not reconcile on a timer to fix it later: `renderPanel` runs on an open, on a
    fold finishing, and on a new event. Seeding the reply before the page loads gives
    two reconciles and hides all of that."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-diff",
            "author": "user",
            "revision": 1,
            "text": "What does the change look like?",
        },
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    page.locator(".lf-thread-summary").first.click()
    page.wait_for_selector(".lf-thread")  # the panel is open and reconciled once
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-diff",
            "revision": 1,
            "text": "The one line that decides it:",
            "markup": PANEL_DIFF_MARKUP,
        },
    )
    told(page)
    expect(page.locator('.lf-thread[data-id="c-diff"] .lf-thread-news')).to_have_count(
        0
    )
    page.wait_for_function(
        """() => {
        const d = document.querySelector('#rp-diff');
        const viewport = d && d.shadowRoot
          && d.shadowRoot.querySelector('code[data-code]');
        return Boolean(viewport) && viewport.tabIndex === 0;
    }"""
    )
    scrolls = page.locator("#rp-diff").evaluate(
        "(d) => { const viewport = d.shadowRoot.querySelector('code[data-code]');"
        " return Math.round(viewport.scrollWidth - viewport.clientWidth); }"
    )
    assert scrolls > 0, "this diff fits the panel, so it proves nothing"


def test_the_accessibility_audit_reads_exposed_frames_and_their_names(browser, serve):
    """Hidden documents are absent; exposed documents and frame names are audited."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Frame audit",
                """<h1>Frame audit</h1>
<iframe id="hidden-frame" title="Hidden practice" hidden srcdoc="<button></button>"></iframe>
<iframe title="Hidden from assistive technology" aria-hidden="true" tabindex="-1"
  srcdoc="<button></button>"></iframe>
<iframe id="shown-frame" title="Visible practice"
  srcdoc="<html lang='en'><title>Practice</title><body><main><h1>Practice</h1>
    <button></button></main></body></html>"></iframe>
""",
            )
        ),
    )
    shown = page.locator("#shown-frame")
    child = shown.element_handle().content_frame()
    child.evaluate("""async () => {
      const frame = document.createElement('iframe');
      frame.id = 'nested-frame';
      frame.title = 'Nested practice';
      frame.srcdoc = `<html lang="en"><title>Nested practice</title><body><main>
        <h1>Nested practice</h1><button></button></main></body></html>`;
      const loaded = new Promise(resolve => frame.addEventListener('load', resolve, {once:true}));
      document.body.append(frame);
      await loaded;
    }""")
    violations, _ = serious_axe_violations(page)
    assert [violation["id"] for violation in violations] == ["button-name"]
    assert len(violations[0]["nodes"]) == 2, "both exposed documents must be audited"

    child.locator("button").evaluate("button => button.textContent = 'Continue'")
    child.frame_locator("#nested-frame").locator("button").evaluate(
        "button => button.textContent = 'Continue'"
    )
    shown.evaluate("frame => frame.removeAttribute('title')")
    violations, _ = serious_axe_violations(page)
    assert [violation["id"] for violation in violations] == ["frame-title"]

    shown.evaluate("frame => frame.title = 'Visible practice'")
    violations, report = serious_axe_violations(page)
    assert violations == [], report


def test_page_and_panel_scroll_in_separate_regions(browser, serve):
    """The browser root scrolls the document and the panel keeps its own scrollport.

    Body is the page shell rather than a third scroll region. The panel stands over the
    page and takes no room from it, so the shell keeps the window's width while native
    document scrolling remains rooted in html."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    geom = page.evaluate(
        """() => {
        const box = el => el.getBoundingClientRect();
        const body = document.body, threads = document.querySelector('.lf-threads');
        return { rootIsScroller: document.scrollingElement === document.documentElement,
                 rootScrolls: document.scrollingElement.scrollHeight > document.scrollingElement.clientHeight,
                 bodyOverflow: getComputedStyle(body).overflowY,
                 threadsScroll: threads.scrollHeight > threads.clientHeight,
                 bodyRight: """
        + SHELL_BOX
        + """.right,
                 window: document.documentElement.clientWidth };
    }"""
    )

    assert geom["rootIsScroller"] and geom["rootScrolls"]
    assert geom["bodyOverflow"] == "visible", geom
    assert geom["threadsScroll"], "the panel did not establish its own scrollport"
    assert geom["bodyRight"] == pytest.approx(geom["window"], abs=1), (
        f"the page yielded room to the panel standing over it: {geom}"
    )


@pytest.mark.parametrize(
    ("width", "quote", "stays_open"),
    [
        (1000, "left-words", True),
        (1000, "right-words", False),
        (1920, "right-words", True),
    ],
)
def test_a_quote_closes_the_panel_only_when_its_passage_would_land_under_it(
    browser, serve, width, quote, stays_open
):
    """Pressing a card's quote promises to show its passage. The panel stands over the
    right of the page, so a passage at the right of the column lands under it at a
    desktop width: there the panel makes way. A passage clear of the panel lands with
    the panel still open beside it, as does the same right-hand passage in a window
    wide enough that the panel stands over empty margin."""
    source = leaf_page(
        "quote travel",
        "<h1>Quote travel</h1>"
        '<p id="left">Left words open this line.</p>'
        + "".join(f"<p>Filler {i}. " + "Words. " * 30 + "</p>" for i in range(20))
        + '<p id="right" style="text-align: right">Right words close this line.</p>'
        + "".join(f"<p>Tail {i}. " + "Words. " * 30 + "</p>" for i in range(20)),
    )
    words = {
        "left-words": ("left", "Left words"),
        "right-words": ("right", "Right words"),
    }
    section, text = words[quote]
    page = open_page(browser, serve(source, anchored=[(section, text)]))
    resized(page, width, 800)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(".lf-threads > .lf-thread").first
    card.locator(":scope > .lf-thread-summary").click()
    card.locator(".lf-quote").click()
    if stays_open:
        expect(page.locator(".lf-thread-panel")).to_be_visible()
    else:
        panel_settled(page, open=False)
    page.wait_for_function(
        """() => { const m = [...CSS.highlights.get('lf-mark')][0].getClientRects()[0];
                   return m.top >= 0 && m.bottom <= innerHeight; }"""
    )
    if stays_open:
        panel_left = page.locator(".lf-thread-panel").bounding_box()["x"]
        mark_right = page.evaluate(
            "() => [...CSS.highlights.get('lf-mark')][0].getBoundingClientRect().right"
        )
        assert mark_right <= panel_left, "the passage landed under the open panel"


def test_covering_panel_takes_the_page_scroll_with_it(browser, serve):
    """Where the panel leaves no usable page it covers the page, and the covered page gives
    up scrolling: a wheel moves the sheet's thread list and never the page behind it. A
    quote is a promise to show a passage, so pressing one dismisses the covering sheet
    and lands on visible paper. The resize path reaches the same states, the posture
    being the panel's width against the window's and the panel stating only that it is
    open."""
    page = open_page(
        browser, serve(LONG_PAGE, comments=12, anchored=[("p40", "Paragraph 40.")])
    )
    resized(page, 400, 600)

    # A reading position first, so surviving the sheet is observable.
    page.mouse.move(120, 300)
    page.mouse.wheel(0, 600)
    page.wait_for_function("() => document.scrollingElement.scrollTop > 0")
    before = page.evaluate("() => document.scrollingElement.scrollTop")

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    # Two wheels over the sheet, one where it stands over the banner's row and one over
    # its list. Waiting on the second proves both were processed — input stays in order —
    # so the page having moved nothing is a real outcome rather than a race.
    page.mouse.move(60, 20)
    page.mouse.wheel(0, 400)
    page.mouse.move(300, 300)
    page.mouse.wheel(0, 400)
    page.wait_for_function("() => document.querySelector('.lf-threads').scrollTop > 0")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before, (
        "the page scrolled behind the covering sheet"
    )

    # Navigation closes the covering auxiliary surface before it positions the page. Doing the
    # same scroll behind the lock produces the right numbers and the wrong product: the
    # promised passage remains invisible.
    #
    # The document says where it came to rest as it comes to rest there, which is the
    # only thing that separates arriving from still travelling: the glide below reaches
    # its destination a frame or more before the browser calls it over, and a wheel sent
    # inside that window cancels the animation instead of scrolling — the user's notch
    # is spent stopping a glide that had already stopped moving.
    page.evaluate("""() => {
        window.lfRestedAt = null;
        addEventListener("scrollend", event => {
            if (event.target === document)
                window.lfRestedAt = document.scrollingElement.scrollTop;
        });
    }""")
    quote = page.locator(".lf-quote", has_text="Paragraph 40")
    thread_id = quote.evaluate("quote => quote.closest('.lf-thread').dataset.id")
    page.locator(f'.lf-thread[data-id="{thread_id}"] .lf-thread-summary').click()
    quote.click()
    panel_settled(page, open=False)
    # Arrived where it was aimed, which is the only thing about this the page states. A
    # text-passage destination reveals nested scrollports without writing the document,
    # then makes one smooth document glide to centre the painted range in the landable
    # space between the banner and shortcut bar. Centring is what
    # the runtime aimed for, so the mark reaching the middle is arrival, and a glide that
    # approaches it passes through no earlier position that could be taken for one.
    page.wait_for_function(
        """() => { const m = [...CSS.highlights.get('lf-mark')][0].getClientRects()[0];
                   const style = getComputedStyle(document.scrollingElement);
                   const top = parseFloat(style.scrollPaddingTop);
                   const bottom = innerHeight - parseFloat(style.scrollPaddingBottom);
                   return Math.abs(m.top + m.height / 2 - (top + bottom) / 2) < 1; }"""
    )
    # Centred, and the glide that centred it over: scrollend names the document's final
    # resting position rather than a sampled frame near it.
    page.wait_for_function(
        "() => window.lfRestedAt === document.scrollingElement.scrollTop"
    )
    at_mark = page.evaluate("() => document.scrollingElement.scrollTop")
    assert at_mark != before

    # Scrolling belongs to the visible page again immediately after that navigation.
    page.mouse.move(120, 300)
    page.mouse.wheel(0, 200)
    page.wait_for_function(f"() => document.scrollingElement.scrollTop > {at_mark}")

    # The resize path: narrowing onto an open panel locks, widening unlocks, and neither
    # takes room from the page.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    resized(page, 1000, 600)
    page.wait_for_function(
        "() => getComputedStyle(document.scrollingElement).overflowY !== 'hidden'"
        " && getComputedStyle(document.body).borderRightWidth === '0px'"
    )
    resized(page, 400, 600)
    page.wait_for_function(
        "() => getComputedStyle(document.scrollingElement).overflowY === 'hidden'"
        " && getComputedStyle(document.body).borderRightWidth === '0px'"
    )


def test_a_covering_sheet_cannot_move_the_background_shortcut_bar(browser, serve):
    """Composer growth leaves inert chrome fixed while live status keeps its room.

    The covering panel and shortcut bar can occupy the same viewport pixels, but they are
    not peers: modality puts the panel above the scrim and makes the bar inert background.
    Treating their rectangles as a collision made every newline in a composer inside the
    panel lift the unrelated bar by one line. A thread walk shows no position over that
    panel and takes no room from its list. Over a live page, the live bar yields the
    panel's actual width."""
    context = browser.new_context(
        viewport={"width": 400, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, serve(ADDRESSED_PAGE, comments=6), context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread").first
    thread.locator(":scope > .lf-thread-summary").focus()
    page.keyboard.press("c")
    field = thread.locator("leaf-text")
    expect(field).to_be_focused()
    write(field, "One line")
    rendered(page)

    def boxes():
        return page.evaluate("""() => {
            const rect = node => {
                const r = node.getBoundingClientRect();
                return {left: r.left, right: r.right, top: r.top, bottom: r.bottom,
                        height: r.height};
            };
            const list = document.querySelector(".lf-threads");
            const style = getComputedStyle(list);
            const standing = document.activeElement?.closest(".lf-thread");
            const bar = document.querySelector(".lf-shortcut-bar");
            const box = bar.getBoundingClientRect();
            const hit = document.elementFromPoint((box.left + box.right) / 2,
                                                 box.bottom - 1);
            return {shortcut_bar: rect(document.querySelector(".lf-shortcut-bar")),
                    panel: rect(document.querySelector(".lf-thread-panel")),
                    composer: rect(document.activeElement.closest("leaf-text")
                                   ?? document.body),
                    standingTitle: standing ? rect(document.activeElement) : null,
                    lineCovered: Boolean(document.querySelector("dialog:modal")) &&
                                 Boolean(bar.closest("[inert]")) && !bar.contains(hit),
                    viewportHeight: innerHeight,
                    listPad: parseFloat(style.paddingBottom),
                    listScrollPad: parseFloat(style.scrollPaddingBottom)};
        }""")

    one_line = boxes()
    assert one_line["lineCovered"], one_line
    assert page.evaluate("""() => {
      const held = document.activeElement;
      document.querySelector('.lf-shortcut-bar button').focus();
      return document.activeElement === held;
    }"""), "the suspended bar took focus from the foreground editor"
    assert one_line["shortcut_bar"]["right"] > one_line["panel"]["left"], (
        f"the fixture no longer exercises the overlapping lanes: {one_line}"
    )
    assert one_line["shortcut_bar"]["top"] < one_line["panel"]["bottom"], (
        f"the fixture no longer exercises the vertical overlap: {one_line}"
    )
    assert abs(one_line["shortcut_bar"]["bottom"] - one_line["viewportHeight"]) < 1, (
        one_line
    )

    write(field, "One line\nSecond line\nThird line")
    rendered(page)
    multiline = boxes()
    assert multiline["composer"]["height"] > one_line["composer"]["height"], (
        f"the composer did not grow: {one_line}, {multiline}"
    )
    assert multiline["shortcut_bar"] == one_line["shortcut_bar"], (
        f"growing the foreground composer moved the background shortcut bar: "
        f"{one_line}, {multiline}"
    )
    assert multiline["listPad"] < 20 and multiline["listScrollPad"] < 20, multiline

    # A thread walk over the panel puts no position over its list. Reach the last
    # thread through the real keyboard route: the list keeps its whole height.
    field.evaluate("field => field.blur()")
    page.locator(".lf-threads").focus()
    for _ in range(6):
        page.keyboard.press("t")
        rendered(page)
    expect(page.locator(".lf-bottom-status")).to_be_hidden()
    walked = boxes()
    assert walked["listPad"] < 20 and walked["listScrollPad"] < 20, walked
    assert walked["standingTitle"], walked

    # Over a live page, the bar is live page chrome and stops at the panel's edge.
    resized(page, 1200, 900)
    beside = boxes()
    assert not beside["lineCovered"], beside
    assert beside["shortcut_bar"]["right"] <= beside["panel"]["left"] + 1, (
        f"the line crossed into the panel standing over the page: {beside}"
    )


def test_covering_feedback_clears_the_reply_at_every_reading_position(browser, serve):
    """Feedback keeps one seat above a reply whether that reply is in view or not."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Read this before replying. " * 80)
    context = browser.new_context(
        viewport={"width": 400, "height": 700}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    write(card.locator("leaf-text"), "One line\nSecond line\nThird line")
    listing = page.locator(".lf-threads")
    listing.focus()
    assert listing.evaluate("n => n.scrollHeight > n.clientHeight")
    page.evaluate(
        "async () => (await window.__lfWidgetApi()).notice('Saved this reply', {announce:false})"
    )
    status = page.locator(".lf-bottom-status")
    expect(status).to_be_visible()
    places = []
    for end in (False, True):
        listing.evaluate("(n,end) => {n.scrollTop = end ? n.scrollHeight : 0}", end)
        rendered(page)
        places.append(status.bounding_box())
    assert places[0] == places[1], "scrolling the reply into view moved its feedback"
    assert (
        places[-1]["y"] + places[-1]["height"]
        < card.locator(".lf-thread-reply").bounding_box()["y"]
    )


def test_dynamic_chrome_offsets_keep_the_safe_area_in_their_arithmetic(browser, serve):
    """The bottom bar keeps the inset tokens stated by the stylesheet: it stands on the
    window's foot, grows by the bottom inset, and holds its hints inside the side insets.
    The insets are stated on the root, where the band's own height reads them."""
    page = open_page(browser, serve(LONG_PAGE))
    resized(page, 500, 700)
    insets = {"left": 17, "right": 31, "bottom": 23}
    page.evaluate(
        """insets => {
          for (const [side, value] of Object.entries(insets))
            document.documentElement.style.setProperty(`--lf-safe-${side}`, `${value}px`);
        }""",
        insets,
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-shortcut-bar")).to_be_visible()
    boxes = page.evaluate(
        """() => {
          const rect = node => {
            const r = node.getBoundingClientRect();
            return {left: r.left, right: r.right, top: r.top, bottom: r.bottom};
          };
          const bar = document.querySelector('.lf-shortcut-bar');
          const hints = [...bar.querySelectorAll(".lf-shortcut:not([data-lf-off-line])")];
          return {shortcut_bar: rect(bar), first: rect(hints[0]),
                  width: innerWidth, height: innerHeight};
        }"""
    )
    band = boxes["shortcut_bar"]
    assert abs(band["bottom"] - boxes["height"]) < 1, boxes
    assert abs(band["bottom"] - band["top"] - (44 + insets["bottom"])) < 1, boxes
    assert boxes["first"]["left"] >= 18 + insets["left"] - 1, boxes
    assert boxes["first"]["bottom"] <= boxes["height"] - insets["bottom"] + 1, boxes


def test_the_page_comment_card_keeps_its_action_inside_the_side_safe_area(
    browser, serve
):
    """The page comment card stays inside both unsafe side edges, on a phone where it
    spans the window and beside it where it hangs from its control."""
    page = open_page(browser, serve(LONG_PAGE))
    page.evaluate(
        """() => {
          document.body.style.setProperty('--lf-safe-right', '31px');
          document.body.style.setProperty('--lf-safe-left', '23px');
        }"""
    )
    for width in (500, 420):
        resized(page, width, 700)
        page_comment(page)
        expect(
            page.locator(".lf-page-comment-card .lf-general button:visible")
        ).to_be_visible()
        boxes = page.evaluate(
            """() => {
              const rect = selector => {
                const r = document.querySelector(selector).getBoundingClientRect();
                return {left: r.left, right: r.right, top: r.top, bottom: r.bottom};
              };
              return {card: rect('.lf-page-comment-card'),
                      action: rect('.lf-page-comment-card .lf-general button:not([hidden])'),
                      viewport: {width: innerWidth, height: innerHeight}};
            }"""
        )
        assert boxes["action"]["right"] <= boxes["viewport"]["width"] - 31 + 1, (
            f"the page comment card's action sat under the side safe area at {width}px: "
            f"{boxes}"
        )
        assert boxes["card"]["left"] >= 23 - 1, (
            f"the page comment card sat under the left safe area at {width}px: {boxes}"
        )
        page.keyboard.press("Escape")
        expect(page.locator(".lf-page-comment-card")).to_be_hidden()

    # The banner declares its face once; the page comment card follows that face
    # even when its declaration changes independently of the viewport width.
    resized(page, 1000, 700)
    page.evaluate(
        "document.documentElement.style.setProperty('--lf-banner-face', 'phone')"
    )
    page_comment(page)
    box = page.locator(".lf-page-comment-card").bounding_box()
    assert box["x"] == pytest.approx(23 + 8)
    assert box["x"] + box["width"] == pytest.approx(1000 - 31 - 8)


# A page holding a paragraph and one control, for the readings below that plant the
# shape they are about rather than finding it in the product: which of the layer's
# controls draws an inset ring, or names no z-index, moves with the product and is not
# what these readings are held to.
RING_PROBE_PAGE = leaf_page(
    "ring",
    "<h1>Ring</h1><p>Words.</p>"
    '<div id="ring-holder"><button id="ring-control" type="button">Control</button></div>'
    "<p>After.</p>",
)


def test_the_ring_reading_names_every_way_a_box_can_draw_nothing_past_its_edge(
    browser, serve
):
    """Overflow is one of three, and the other two leave `overflow` computing `visible`.

    The gate below reports a cut ring by asking each box on the way up what band it
    shows. A reading that knows only `overflow` answers "nothing is wrong" for a box that
    clips by paint containment or by `content-visibility`, and answers it in the same
    words it uses when nothing is wrong — which is why the corpus staying green could not
    have told anyone. `shownBand` is the product's own reading and names all three; this
    holds the probe to it rather than to a copy free to drift from it again.

    One control, one ring pushed out past its box, three parents differing only in how
    they clip. The first case is the control: without it a reading that reported at every
    stop would pass the other three and prove nothing.
    """
    example = next(e for e in EXAMPLES if e.stem == "release-notes")
    url = serve(example, comments=2, seed_log=False)
    page = open_page(browser, url)
    any_suggestion_control(page, "accept").first.focus()
    # The probe's control must begin clear of the viewport edge. Its subject is each
    # ancestor's clipping behavior, not where the corpus happened to place this button.
    page.evaluate("document.activeElement.scrollIntoView({block: 'center'})")

    plant = """(how) => {
      const el = document.activeElement;
      const p = el.parentElement;
      p.style.overflow = p.style.contain = p.style.contentVisibility = '';
      // The ring past the parent's edge with the control still inside it. Moving the
      // control out instead takes its own edge out of the box too, and a box is held to
      // a ring only on the sides where it is showing the control's own edge — so all
      // three cases below would be declined for the reason the control case is.
      el.style.outlineOffset = '8px';
      if (how === 'overflow') p.style.overflow = 'hidden';
      if (how === 'contain') p.style.contain = 'paint';
      if (how === 'content-visibility') p.style.contentVisibility = 'auto';
      const s = getComputedStyle(p);
      return `${s.overflowX}/${s.contain}/${s.contentVisibility}`;
    }"""

    clean = page.evaluate(plant, "none")
    assert standing_ring(page)["cuts"] == [], (
        f"the displaced ring is reported cut with nothing clipping it ({clean}), so the "
        "cases below would only be repeating whatever this reading always says"
    )
    for how in ("overflow", "contain", "content-visibility"):
        style = page.evaluate(plant, how)
        cuts = standing_ring(page)["cuts"]
        assert any("left edge" in c for c in cuts), (
            f"a parent clipping by {how} ({style}) drew the ring away and the reading "
            f"said {cuts}"
        )


def test_the_ring_reading_distinguishes_element_marks_from_focus(browser, serve):
    """The reading ignores element contours and still recognizes the real focus ring.

    A hovered passage deliberately shares the ring's accent and width but has no
    focus-ring declaration, so its element-feedback role must keep it out of the
    population of keyboard rings. The named focus state on that same element and an
    unregistered real ring follow as positive controls; without them a reading that
    ignored all element contours would pass the first case and prove only that it was
    silent."""
    example = next(e for e in EXAMPLES if e.stem == "release-notes")
    url = serve(example, comments=2, seed_log=False)
    page = open_page(browser, url)
    any_suggestion_control(page, "accept").first.focus()

    plant = """(how) => {
      const box = document.querySelector('main p');
      box.classList.toggle('probe-target', true);
      for (const name of ['lf-mark-el', 'lf-mark-hover'])
        box.classList.toggle(name, false);
      box.toggleAttribute('data-lf-focus', how === 'focused mark');
      box.style.outline = '';
      box.style.removeProperty('--lf-focus-ring');
      if (how === 'mark') box.classList.add('lf-mark-el', 'lf-mark-hover');
      if (how === 'focused mark') box.classList.add('lf-mark-el');
      if (how === 'the ring itself') box.style.outline = 'var(--focus-ring)';
      if (how === 'unregistered focused mark') {
        box.classList.add('lf-mark-el');
        box.style.outline = 'var(--focus-ring)';
        box.style.setProperty('--lf-focus-ring', 'none');
        box.tabIndex = -1;
        box.focus();
      }
      const cs = getComputedStyle(box);
      return [cs.outlineStyle, cs.outlineWidth, cs.outlineColor];
    }"""

    def claimed():
        """The reading's ring claims for this one box.

        Asked of the box rather than of how many rings the page has: the runtime
        repaints the panel on its own schedule, so two whole-page counts taken a moment
        apart differ for reasons that have nothing to do with what was planted here.
        """
        return [
            seen
            for seen in rings_drawn(page)
            if seen["here"] and "probe-target" in seen["who"]
        ]

    page.evaluate(plant, "none")
    assert not claimed(), "the box is called a ring before anything is painted on it"
    standing = standing_ring(page)
    assert standing and standing["here"], (
        "no ring is painted with the keyboard on a control, so the reading is silent "
        "here and would pass this test however it behaved"
    )

    mark_paint = page.evaluate(plant, "mark")
    style, _width, colour = mark_paint
    assert style == "solid", "the element comment lost its complete contour"
    assert not claimed(), (
        f"the reading counted the mark ({colour}) as a focus ring: {claimed()}"
    )

    _style, _width, colour = page.evaluate(plant, "focused mark")
    focused_claims = claimed()
    assert [seen["ring"] for seen in focused_claims] == ["passage-focus"], (
        f"the marked element's named focus ring ({colour}) was not credited: "
        f"{focused_claims}"
    )

    ring_paint = page.evaluate(plant, "the ring itself")
    assert mark_paint == ring_paint, (
        f"the mark paints {mark_paint} and the ring paints {ring_paint}, so the mark "
        "case above was kept out by paint rather than by the element-feedback role "
        "this reading now divides on"
    )
    ring_claims = claimed()
    assert len(ring_claims) == 1 and not ring_claims[0]["ring"], (
        f"a box wearing the layer's own ring ({ring_paint}) was not counted, so the cases "
        "above prove only that this reading is silent"
    )

    focused_mark_paint = page.evaluate(plant, "unregistered focused mark")
    focused_mark_claims = claimed()
    assert len(focused_mark_claims) == 1 and not focused_mark_claims[0]["ring"], (
        f"a focused element mark wearing an unregistered ring ({focused_mark_paint}) "
        f"was not counted: {focused_mark_claims}"
    )


def test_the_ring_reading_sees_and_measures_a_ring_cast_as_a_shadow(browser, serve):
    """The band has two carriers, and a reading that knew one was blind to the other.

    Most of the layer's rules draw the ring as an outline. A target hint the keyboard
    is browsing casts it as a shadow, on a chip in a layer nothing can focus. To a user
    those are the same band, and a sweep asking only the outline misses the shadow's
    indication and geometry.

    Knowing one on sight is the first half, and the layer offers three shadows to mistake
    for it: the elevation lift every floating surface wears, the inset accent wash a
    search match and an open draft wear, and the accent band a milestone's active dot
    wears at a width of its own. Offsets, blur, `inset` and the ring's own width are what
    separate the four, and nothing else does.

    Measuring it is the second half, and the one the corpus floor rests on. A spread has
    no offset, so the band's width is the whole of what the box draws past its edge — and
    a reading that never finds the band measures nought, drops the box without a word,
    and reports what a clean page reports. So the plant is a box standing on the window's
    own foot, where the band is the only part of it that can be outside the window, with
    the same box and the same place as the control once the band is taken off.
    """
    page = open_page(browser, serve(RING_PROBE_PAGE))

    # On the window's foot, so the only thing that can be outside the window is the band.
    # Placed from `innerHeight` rather than from `100vh`, which is the viewport a
    # scrollbar is not taken out of and so is the same number only while there is none.
    plant = """(how) => {
      const box = document.querySelector('main p');
      box.classList.toggle('probe-target', true);
      box.style.cssText = `position: fixed; left: 40px; top: ${innerHeight - 30}px;
        width: 120px; height: 30px; box-sizing: border-box; margin: 0`;
      if (how === 'a lift') box.style.boxShadow = '0 2px 8px var(--shade)';
      if (how === 'an inset wash')
        box.style.boxShadow = 'inset var(--focus-shadow)';
      if (how === 'a wider band')
        box.style.boxShadow = '0 0 0 calc(var(--focus-ring-w) + 1px) var(--accent)';
      if (how === 'the band itself')
        box.style.boxShadow = 'var(--focus-shadow)';
      const cs = getComputedStyle(box);
      return [cs.boxShadow, cs.outlineStyle, box.getBoundingClientRect().bottom,
              innerHeight];
    }"""

    def reading():
        """What the sweep says about this one box: whether it is a ring, and its cuts.

        Asked of the box and not of the page, because the runtime repaints the panel on
        its own schedule and two whole-page readings a moment apart differ for reasons
        that have nothing to do with what was planted here.
        """
        return next(
            (
                seen
                for seen in rings_drawn(page)
                if "probe-target" in seen["who"] and seen["here"]
            ),
            None,
        )

    for how in ("nothing", "a lift", "an inset wash", "a wider band"):
        shadow, outline, bottom, foot = page.evaluate(plant, how)
        assert outline == "none" and bottom == foot, (
            f"{how} left the box wearing {outline} at {bottom} of {foot}, so the reading "
            "was asked about a box other than the one this is written against"
        )
        assert reading() is None, (
            f"the reading counted {how} ({shadow}) as the focus ring: {reading()}"
        )

    shadow, outline, bottom, foot = page.evaluate(plant, "the band itself")
    seen = reading()
    assert seen, (
        f"a box casting the layer's own band ({shadow}) was not counted, so the four "
        "cases above prove only that this reading is silent"
    )
    # And the band is measured, not merely noticed: the box's own edge is on the window's
    # foot, so the width reported outside it is the whole of the band and nothing else.
    width = page.evaluate(
        "() => parseFloat(getComputedStyle(document.documentElement)"
        "  .getPropertyValue('--focus-ring-w'))"
    )
    assert any(
        f"its bottom edge is {width:g}px outside the window" in cut
        for cut in seen["cuts"]
    ), (
        f"the band stood {width}px past the window's foot and the reading said "
        f"{seen['cuts']}, so nothing above measured it"
    )


def test_the_ring_reading_still_sees_what_is_painted_over_a_ring(browser, serve):
    """The half that answers by hit test, held to firing where it can and not where it

    cannot. It takes whatever the ring's own pixels hit as standing over them, and an
    outline is painted by its control at its control's level while an outline's pixels
    are not hit-testable — so a sample outside the control's box returns whatever is
    beneath. That is sound while the control's surface takes hits and unsound inside one
    that does not, where the answer comes back inverted: the shortcut bar stands over the
    page at z-index 8940 with `pointer-events: none`, and the code under its More button
    read as standing over it.

    So the reading declines inside such a surface, and that is a way for it to go quiet
    everywhere by accident. The plant is the population assertion: thin enough to lie
    over the ring and not over the control, because a cover across the control's own body
    is excused on purpose — a control put where something stands over it is a fact about
    where it was put, not about its ring leaving its box.
    """
    example = next(e for e in EXAMPLES if e.stem == "release-notes")
    url = serve(example, comments=2)
    page = open_page(browser, url)
    page.locator("body").click()
    # Reach the stop by keyboard before testing what can cover its ring.
    page.locator(".lf-threads-toggle").focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    assert standing_ring(page), "no ring is drawn, so nothing is covered"

    assert standing_ring(page)["covers"] == [], (
        "the control is reported covered before anything is put over it"
    )
    page.evaluate(
        """() => {
          const b = document.activeElement.getBoundingClientRect();
          const d = document.createElement('div');
          // Over the ring's top run and clear of the control's own box.
          d.style.cssText = `position: fixed; z-index: 99999; background: red;
            left: ${b.left - 8}px; top: ${b.top - 5}px;
            width: ${b.width + 16}px; height: 4px;`;
          document.body.append(d);
        }"""
    )
    assert any("top edge is under" in c for c in standing_ring(page)["covers"]), (
        "a band laid over the ring's top run was not reported, so this reading answers "
        "nothing and the pages it passes are not evidence"
    )


def test_the_ring_reading_passes_over_a_neighbour_the_control_paints_across(
    browser, serve
):
    """The same half held to the other order, which it read backwards. An outline is
    painted by its control at its control's level, so a box the control stands in front
    of cannot stand over the ring around it — but the hit test that answers this half
    samples the band outside the control's box, where whatever is beneath comes back.

    The panel's edge grip is the shape that made that matter. It floats over the threads
    at z-index 1, so its band crosses their own lines at every width and scroll position,
    and the reading named whichever line it happened to land on: a two-pixel change to a
    card's padding (#374) put a receipt under the coarse grip's foot and took
    `test_coarse_pointer_resize_reach_stays_reachable_without_trapping_scroll` down with
    nothing about the page wrong.

    So: one neighbour under the grip's band and clear of its box, planted three times —
    where the grip paints across it, where a z-index of its own lifts it past the grip,
    and where it is `position: fixed` inside a static box that ranks behind the grip. The
    lifted half is the population assertion; a reading gone quiet would pass the others on
    its own. The third is the grip's `z-index: 1` again: a neighbour that names no z-index
    paints in the layer below it whatever holds it, so leaving its holder's flow does not
    put it over the ring, and the reading that reported it there would be inventing a
    cover the page does not paint.
    """
    url = serve(LONG_PAGE, comments=6)
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    edge = page.locator(".lf-thread-panel > .lf-edge")
    edge.focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    standing = standing_ring(page)
    assert standing and standing["ring"] == "edge", (
        f"the keyboard is not standing on the grip's own ring: {standing}"
    )

    # A band under the grip's right ring run and clear of its own box, inside a holder
    # beside the grip in the panel: that run is within the panel's hit surface, whose
    # enclosing auxiliary envelope takes no hits. The holder is what the reading can
    # rank, and putting the band in the page leaves it with nothing to rank against.
    # Neither paints anything the grip does not already stand in front of, until the band
    # names the z-index that lifts it past.
    plant = """({z, wrap, isolate = false}) => {
      document.querySelector('.lf-under-plant')?.remove();
      const grip = document.querySelector('.lf-thread-panel > .lf-edge');
      const cs = getComputedStyle(grip);
      const grow = parseFloat(cs.outlineWidth) + parseFloat(cs.outlineOffset);
      const b = grip.getBoundingClientRect();
      const mid = (Math.max(b.top - grow, 0) + Math.min(b.bottom + grow, innerHeight)) / 2;
      const holder = document.querySelector('.lf-thread-panel')
        .appendChild(document.createElement('div'));
      holder.className = 'lf-under-plant';
      Object.assign(holder.style, {position: 'absolute', inset: '0'});
      // A static box filling that holder, when the plant wants one: it is what the walk
      // ranks then, and it stands in the flow where the grip is painted over it.
      const under = wrap ? holder.appendChild(document.createElement('div')) : holder;
      if (wrap) Object.assign(under.style, {height: '100%'});
      // A static stacking context around the band, which orders the band's z-index inside
      // it and paints in the positioned layer around it.
      if (isolate) under.style.opacity = '0.99';
      const band = under.appendChild(document.createElement('div'));
      Object.assign(band.style, {
        position: 'fixed', background: 'red',
        left: `${b.right}px`, top: `${mid - 20}px`,
        width: `${grow + 1}px`, height: '40px',
      });
      if (z) band.style.zIndex = String(z);
      return grow;
    }"""

    grow = page.evaluate(plant, {"z": 0, "wrap": False})
    assert grow > 0, (
        f"the grip draws its ring {grow}px outside its box, so there is no band outside "
        "it to lay anything under and this holds nothing"
    )
    assert standing_ring(page)["covers"] == [], (
        "a neighbour the grip paints across was read as standing over its ring"
    )

    page.evaluate(plant, {"z": 2, "wrap": False})
    covers = standing_ring(page)["covers"]
    assert any("right edge is under" in c for c in covers), (
        f"the same band lifted past the grip by a z-index of its own read as {covers}, "
        "so the half above passed on a reading that answers nothing"
    )

    # The same band inside a static box, which is the shape that leaves a holder's flow:
    # it paints in the positioned layer rather than the one its holder is ranked in. That
    # is still the layer under the grip's own, so the page paints the grip in front and
    # the reading has nothing to report.
    page.evaluate(plant, {"z": 0, "wrap": True})
    covers = standing_ring(page)["covers"]
    assert covers == [], (
        f"a band the grip's own z-index stands over read as {covers}, so leaving a "
        "holder's flow was taken for standing over the control that names one"
    )

    # A band whose z-index orders it inside a static stacking context: the walk goes on
    # from that context, so the reading has to agree with the pixels the page paints on
    # the ring's run there, red where the band stands over it.
    for z in (1, 2):
        page.evaluate(plant, {"z": z, "wrap": True, "isolate": True})
        x, y = page.evaluate("""() => {
          const grip = document.querySelector('.lf-thread-panel > .lf-edge');
          const cs = getComputedStyle(grip);
          const b = grip.getBoundingClientRect();
          return [b.right + parseFloat(cs.outlineOffset) + parseFloat(cs.outlineWidth) / 2,
                  (b.top + b.bottom) / 2];
        }""")
        shot = page.screenshot(
            clip={"x": x - 0.5, "y": y - 0.5, "width": 1, "height": 1}
        )
        red, green, blue = Image.open(io.BytesIO(shot)).convert("RGB").getpixel((0, 0))
        painted = red > 200 and green < 80 and blue < 80
        covers = standing_ring(page)["covers"]
        assert bool(covers) == painted, (
            f"a band inside a stacking context at z-index {z} read as {covers} while "
            f"the page {'paints' if painted else 'does not paint'} it over the ring"
        )

    page.evaluate("() => document.querySelector('.lf-under-plant').remove()")


def test_the_ring_reading_sees_a_neighbour_lifted_out_of_the_flow_it_was_ranked_in(
    browser, serve
):
    """The other side of the half above, against a control that names no z-index.

    The reading excuses a neighbour by ranking the box that holds it, and a box that
    ranks behind the control puts what stays in its flow behind the control too. A
    positioned neighbour does not stay: it leaves its holder's place in the flow to paint
    in the positioned layer of the nearest ancestor stacking context, which is the layer a
    control with `position: relative; z-index: auto` is in (a thread card's buttons). So
    a static holder's rank says nothing about it, and taken for an answer it drops a
    cover the page paints.

    The plant is that shape: a fixed band over the ring's top run, held by a static box
    beside the control. The band comes back topmost where the ring is sampled, and the
    reading has to say so. The clean reading first, because a reading that reports at
    every control would pass the planted one without seeing it.
    """
    page = open_page(browser, serve(RING_PROBE_PAGE))
    page.evaluate(
        """() => {
          const control = document.getElementById('ring-control');
          control.style.cssText = `position: relative; z-index: auto;
            outline: var(--focus-ring); outline-offset: 2px;`;
          control.focus();
        }"""
    )
    standing = standing_ring(page)
    assert standing and standing["covers"] == [], (
        f"the control is reported covered before anything is put over it: {standing}"
    )

    page.evaluate(
        """() => {
          const b = document.activeElement.getBoundingClientRect();
          // A static box, so the flow is what its own rank answers for, pulled back over
          // the control it is appended beside rather than adding height under it.
          const holder = document.createElement('div');
          holder.style.cssText = 'margin-top: -100vh; height: 100vh;';
          const band = document.createElement('div');
          // Over the ring's top run and clear of the control's own box, and positioned,
          // so it leaves the holder's flow for the layer the control is in.
          band.style.cssText = `position: fixed; background: red;
            left: ${b.left - 8}px; top: ${b.top - 5}px;
            width: ${b.width + 16}px; height: 4px;`;
          holder.append(band);
          document.getElementById('ring-holder').append(holder);
        }"""
    )
    covers = standing_ring(page)["covers"]
    assert any("top edge is under" in c for c in covers), (
        f"a band standing over the ring read as {covers}, so a neighbour that left the "
        "flow its holder was ranked in goes unreported"
    )

    # The same band with a z-index of its own inside a static stacking context. The
    # z-index orders it only inside that context, which paints in the control's layer
    # after it, so the band still stands over the ring, and the walk that goes on from
    # the context has to say so rather than rank the static holder.
    page.evaluate(
        """() => {
          const band = document.querySelector('#ring-holder > div:last-child > div');
          const context = document.createElement('div');
          context.style.opacity = '0.99';
          band.style.zIndex = '1';
          band.replaceWith(context);
          context.append(band);
        }"""
    )
    covers = standing_ring(page)["covers"]
    assert any("top edge is under" in c for c in covers), (
        f"a band lifted inside a stacking context read as {covers}, so a z-index that "
        "orders a box only inside its context hid a cover the page paints"
    )

    # The same context standing before the control in the tree and overlapping it: it
    # paints as one unit in the control's layer, before the control, so the ring stands
    # over the band, as the page's pixels say. The context's own rank answers for it.
    page.evaluate(
        """() => {
          const context = document.querySelector('#ring-holder > div:last-child > div');
          Object.assign(context.style, {height: '100vh', marginBottom: '-100vh'});
          const holder = document.getElementById('ring-holder');
          holder.prepend(context);
          document.querySelector('#ring-holder > div:last-child').remove();
        }"""
    )
    x, y = page.evaluate("""() => {
      const b = document.activeElement.getBoundingClientRect();
      return [b.left + b.width / 2, b.top - 3];
    }""")
    shot = page.screenshot(clip={"x": x - 0.5, "y": y - 0.5, "width": 1, "height": 1})
    red, green, blue = Image.open(io.BytesIO(shot)).convert("RGB").getpixel((0, 0))
    assert not (red > 200 and green < 80 and blue < 80), (
        "the page paints the band over the ring here, so this case holds nothing"
    )
    covers = standing_ring(page)["covers"]
    assert covers == [], (
        f"a band inside a context the control paints over read as {covers}, so the "
        "walk hoisted the context past the rank that answers for it"
    )


def test_a_user_who_asked_for_no_motion_gets_a_ring_that_does_not_arrive(
    browser, serve
):
    """A duration is a way of keeping an animation and no way at all of keeping a
    transition. An animation is declared and named, and the layer reads `animationend`
    to know one has run, so the guard's near-zero duration keeps that event and spends
    no time on it. A transition is declared by nobody — `transition-property` is `all`
    until something says otherwise — so the same duration over every element made a
    transition out of every property that changed on any of them.

    None of which anybody wrote or listened for, and none of which was free: a ring is
    `outline-width`, `outline-offset` and `outline-color` all changing at once, so a
    user who asked for no motion got a medium currentColor ring at offset nought
    animating into the real one, on every focus, on every page. It is also what a
    computed-style reading of a ring taken in those frames was told, which is how
    `RINGS_DRAWN` came to invent one.

    So this asks the user's own question — is anything moving — of the control they
    just landed on, in the one setting where the answer has to be no."""
    url = serve(LONG_PAGE, comments=3)
    context = browser.new_context(reduced_motion="reduce")
    page = open_page(browser, url, context=context)
    assert page.evaluate(
        "() => matchMedia('(prefers-reduced-motion: reduce)').matches"
    ), "the context did not ask for reduced motion, so the guard under test is off"
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    control = page.locator(".lf-threads .lf-btn").first
    control.focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")

    seen = page.evaluate(
        """() => {
          const el = document.activeElement;
          const cs = getComputedStyle(el);
          return {
            moving: el.getAnimations().map(
              (a) => a.transitionProperty || a.animationName || 'animation'),
            ring: [cs.outlineWidth, cs.outlineStyle, cs.outlineOffset],
            want: cs.getPropertyValue('--focus-ring').trim(),
          };
        }"""
    )
    assert seen["moving"] == [], (
        f"the ring is still arriving under reduced motion: {seen['moving']} are "
        "running, so what the user sees and what any reading of this control gets "
        "is a value on its way rather than the one the rule states"
    )
    # Non-vacuity: a control with no ring has nothing that could have transitioned.
    assert seen["ring"][:2] == [seen["want"].split()[0], "solid"], (
        f"the control reads {seen['ring']} where its ring is {seen['want']}, so "
        "nothing here was ever going to move"
    )


def test_the_ring_reading_sees_a_neighbour_paint_over_a_ring_drawn_inside_its_box(
    browser, serve
):
    """The same half asked of the other shape of ring, and the shape it was quiet about.
    A cover is excused where the control is under the same thing — a control put under a
    fixed bar is where it was put, not a ring leaving its box — and how far in the
    reading looks to ask that is the ring's own band.

    Which is inside the box when the ring is. The test above plants over a ring drawn
    outside its control, where the band is outside too and any step in clears it; asked
    one pixel in, as it was, the same question over an inset ring lands on the ring
    rather than past it, so every covered inset ring answered that the control was under
    the same thing and the reading returned what it returns when nothing is wrong.

    So: a control drawing the layer's ring inside itself, as a thread title does, under a
    band exactly as deep as that ring. The control case first, because a reading that
    reports over any inset control would pass the planted one without seeing it.
    """
    page = open_page(browser, serve(RING_PROBE_PAGE))
    # The layer's band, widened past two pixels: a step in of one pixel from the middle of
    # a 2px band lands on its inner edge, which hit testing may or may not count as the
    # band, so only a wider ring makes a step that stops inside it a step that fails.
    inset = page.evaluate(
        """() => {
      const control = document.getElementById('ring-control');
      control.style.cssText = `--focus-ring-w: 4px;
        outline: var(--focus-ring-w) solid var(--accent);
        outline-offset: calc(-1 * var(--focus-ring-w)); padding: 12px 24px;`;
      control.focus();
      const s = getComputedStyle(control);
      return [parseFloat(s.outlineWidth), parseFloat(s.outlineOffset)];
    }"""
    )
    assert inset[0] > 0 and inset[1] <= -inset[0], (
        f"the control's ring is {inset[0]}px at offset {inset[1]}px, which is not drawn "
        "inside its box, so this holds nothing about a reading of one that is"
    )

    # A band of the page's own paper over the control's top run, and nothing else of it.
    # Fixed and outside the control, because the reading passes over an ancestor or a
    # descendant of the control by design — a widget painting its own edge is not a
    # neighbour.
    plant = """(depth) => {
      document.querySelector('.lf-ring-plant')?.remove();
      if (!depth) return null;
      const r = document.activeElement.getBoundingClientRect();
      const over = document.documentElement.appendChild(
        document.createElement('div'));
      over.className = 'lf-ring-plant';
      Object.assign(over.style, {
        position: 'fixed', zIndex: '9999',
        background: 'var(--card)',
        left: `${r.left}px`, top: `${r.top}px`,
        width: `${r.width}px`, height: `${depth}px`,
      });
      return over.getBoundingClientRect().height;
    }"""

    page.evaluate(plant, 0)
    assert standing_ring(page)["covers"] == [], (
        "the control is reported covered with nothing over it, so the planted case "
        "below would only be repeating whatever this reading always says"
    )

    laid = page.evaluate(plant, inset[0])
    covers = standing_ring(page)["covers"]
    assert any("top edge" in c for c in covers), (
        f"a {laid}px band over the whole of the control's {inset[0]}px inset ring, "
        f"with the rest of the control in full view, and the reading said {covers}"
    )


# The page the chrome's surfaces are sampled on: small, with a board's grips, and served
# with a second version so the versions menu has a comparison to offer.
RING_CHROME = "triage-board"
# A causal sample in each surface the keyboard reaches. Each case names its surface, the
# real keys that open it, the element whose focus state paints the ring, and the ring it
# paints. A null selector means the opening keys themselves leave the required
# non-focusable carrier lit.
RING_CASES = (
    (
        "the page",
        (),
        {
            # The chrome's own surfaces stand on the smallest page that offers them all,
            # since every page carries the same chrome and each reading over a large
            # document costs seconds.
            RING_CHROME: (
                (".lf-skip", "skip"),
                (".lf-grip", "card-grip"),
                (".lf-status-button", "status"),
                (".lf-others", "btn"),
                (".lf-edge:visible", "edge"),
                # Before the fields: More stands down while a field takes its key.
                (".lf-shortcut-more", "key-more"),
                (".lf-find-box input", "text-entry"),
                (".lf-thread-panel leaf-text", "text-box"),
            ),
            "feature-gallery": (
                (".lf-tab-btn", "tab-btn"),
                ("lf-option > .lf-pick", "options-row"),
                (
                    any_owner_entry("suggestion", "accept") + ":visible",
                    "margin-entry",
                ),
                (".lf-draft-edit", "draft-editor"),
            ),
            "heat-loss": ((".lf-visual-action", "visual-target"),),
            "review-a-plan": (("main details > summary", "focus"),),
            "pr-walkthrough": (
                ("lf-gloss:visible > .lf-gloss-mark", "gloss-mark"),
                (".lf-diff-search input", "text-entry"),
                ("lf-diff summary", "code-summary"),
                ("lf-diff code", "code-pre-shadow"),
            ),
            "release-notes": (
                ("main p.lf-mark-el", "passage-focus"),
                ('lf-shot .lf-shotcomparison [part~="handle"]', "comparison-handle"),
                (".lf-shotcap", "pressable"),
            ),
            "ship-review": ((".lf-reopen", "thread-action"),),
            "wt-merge": (
                ('[data-lf-reading-role="pane"] > [tabindex="0"]', "pane-body"),
            ),
        },
    ),
    ("a landed diff line", ("]",), {"pr-walkthrough": ((None, "code-line"),)}),
    (
        "an inline response",
        (),
        {"pr-walkthrough": (("leaf-text.lf-fab-input", "text-box"),)},
    ),
    # The list holds focus itself only while it shows no thread, so the sample finds
    # nothing and backs out of the find box onto the emptied list.
    (
        "the thread list",
        ("g", "Shift+t", "/", "z", "q", "x", "j", "Escape"),
        {RING_CHROME: ((None, "thread-list"),)},
    ),
    (
        "a thread title",
        (),
        {"ship-review": ((".lf-thread-summary:visible", "thread-summary"),)},
    ),
    # The keyboard walk lands on the accordion title, whose inset band also marks
    # its native Tab stop.
    (
        "a walked thread",
        ("g", "Shift+t", "t"),
        {"ship-review": ((None, "thread-summary"),)},
    ),
    # The same walk with the panel shut lands in the margin's thread view, on the
    # thread itself rather than a control inside it.
    ("an inline thread", ("t",), {"ship-review": ((None, "page-thread"),)}),
    (
        "passage search",
        ("/",),
        {RING_CHROME: ((".lf-page-search-box input:visible", "text-entry"),)},
    ),
    # Item hints, and the anchored bar the user answers a chosen item on. Both open the
    # same mode, and both step back and then forward through it, which lands on the last
    # item the window is showing whatever a page's count is: the browse wraps, so one step
    # back from a fresh open is the second from the end. That item is the lowest on
    # screen, which is where the layer has the least room to draw a band around a chip and
    # the least room to hang a bar under one.
    #
    # The Tab in front of both sequences is a stop, not a gesture in the mode: target hints
    # claim Tab for browsing themselves, so the sample below moves nothing once the mode
    # is open, and with the document under it the sample would stand on nothing and read no
    # page at all. Standing on a control first leaves the hint the keyboard is browsing on
    # screen for the sweep, which is where its band is read — the chips are a layer nothing
    # can focus, so the user's place in that mode is not a stop.
    (
        "target hints",
        ("Tab", "s", "Shift+Tab", "Tab"),
        {RING_CHROME: ((None, "target-hint"),)},
    ),
    # Enter opens Comment on the item the keyboard is browsing and focuses its field.
    (
        "the response bar",
        ("Tab", "s", "Shift+Tab", "Tab", "Enter"),
        {RING_CHROME: ((".lf-fab-input", "text-box"),)},
    ),
    # These controls live behind exact page-owned view states: a settled group's
    # disclosure, and the options it puts away.
    (
        "a settled decision",
        (),
        {
            "current-proposed-comparison": (
                ("#comparison-policy > .lf-settled", "options-settled"),
            )
        },
    ),
    (
        "a settled option",
        (),
        {
            "current-proposed-comparison": (
                ("#comparison-policy > lf-option > .lf-pick", "options-pick"),
            )
        },
    ),
    (
        "a contents link",
        (),
        {"feature-gallery": (("#bg-contents li a:visible", "toc-link"),)},
    ),
    # The reaction palette a message's strip opens. Its chips are the last boxes the
    # layer dresses in the chrome's chip face, and they are behind a press: the strip
    # shows a token nobody has pressed only while it is open, so a walk of the panel
    # that never opens one stands on the trigger and nothing under it.
    (
        "a reaction palette",
        (),
        {"ship-review": ((".lf-react-palette:popover-open .lf-react", "chip"),)},
    ),
    ("the On panel", (), {"ship-review": ((".lf-queue-row", "queue-row"),)}),
    ("the pages drawer", ("g", "Shift+l"), {RING_CHROME: ((None, "others-row"),)}),
    ("page status", (), {RING_CHROME: ((None, "status-detail"),)}),
    # The menu's own route after the key that opens it: an open lands on the version being
    # read, which is the first row, and the comparison press beside a row is a Tab forward
    # from the row below it. The walk is clamped, so a second press at the bottom moves
    # nothing and the pair reaches a menu of any length this corpus can hold.
    (
        "the versions menu",
        ("g", "Shift+v", "ArrowDown", "ArrowDown"),
        {
            RING_CHROME: (
                (".lf-version-row", "version-row"),
                (".lf-version-diff:visible:not(:disabled)", "version-diff"),
            )
        },
    ),
    (
        "the command reference",
        ("?", "?"),
        {
            RING_CHROME: (
                (".lf-command-reference-search input:visible", "text-entry"),
                (".lf-command-reference-command", "help-command"),
            )
        },
    ),
    # A Thread card and the compact Page Map dialog are the two layers a Tab walk of the
    # page cannot open for itself. The card is a press on a thread margin entry; the sheet is a
    # press on a Page Map control the wide posture does not draw at all, so its sample asks for
    # the narrow window the control lives in.
    (
        "a thread card",
        (),
        {"ship-review": ((".lf-margin-preview .lf-resolve", "thread"),)},
    ),
    ("message media", (), {"feature-gallery": ((".lf-message-media", "media"),)}),
    # Both controls of a summarized range wear one band: the checkpoint's own button, and
    # the rail that folds the originals back once it has opened them.
    (
        "a summarized range",
        (),
        {"feature-gallery": ((".lf-summary-expand", "summary-fold"),)},
    ),
    (
        "the Page Map dialog",
        (),
        {
            RING_CHROME: (
                (".lf-page-map-action:visible", "page-map-action"),
                (".lf-page-map-search input:visible", "text-entry"),
            )
        },
    ),
)
# The selected pages jointly load the core and optional package stylesheets.
RING_EXAMPLES = tuple(
    dict.fromkeys(name for _scope, _keys, cases in RING_CASES for name in cases)
)
RING_EXAMPLE_FILES = {
    example.stem: example
    for example in (
        *EXAMPLES,
        FEATURE_GALLERY,
        ROOT / "tests/fixtures/pages/current-proposed-comparison.html",
    )
}
# Rings whose carrier is semantic state elsewhere in the page rather than the focused
# control or one of its ancestors. Mark the exact carrier before reading the composed
# paint so an unrelated ring with the same name cannot credit the sample.
RING_REMOTE_CARRIER = {
    "target-hint": ".lf-target-picker-hint.lf-current",
    # A pane draws its focused body's band inset over the body's cell (theme.css).
    "pane-body": '[data-lf-reading-role="pane"]:has(> [data-lf-focus])',
}


# Whether the page is offering a banner control at all, which is not the same question as
# whether the user can see it standing on the row. A control with nothing to show is
# drawn away by the banner's own presence writer (paintPresence, display: none), while one
# the row had no width for is alive behind the fold's menu — and asking a folded control
# whether it is visible answers no for a page that is offering it perfectly well, which
# read as a scope no example reached rather than as a window too narrow to show it.
def offered(page, selector):
    return page.locator(selector).evaluate_all(
        "els => els.some(el => getComputedStyle(el).display !== 'none')"
    )


# A surface must open before its sample can count. Conditional banner controls are
# checked only on a page that offers them.
RING_SCOPE_SURFACE = {
    "an inline response": (
        'lf-diff .lf-fab-bar[data-lf-presentation="inline"] .lf-composer[data-lf-open]',
        None,
    ),
    "the thread list": (".lf-thread-panel.open", None),
    "a walked thread": (".lf-thread-panel.open", None),
    "an inline thread": (".lf-margin-preview:not([hidden])", None),
    "a thread card": (".lf-margin-preview:not([hidden])", None),
    "the Page Map dialog": (".lf-page-map-dialog[open]", None),
    "passage search": (".lf-page-search:not([hidden])", None),
    # The hint the keyboard is browsing, and the field the chosen item's bar opens with.
    # Each is the mode's own state rather than a box that merely exists: the chips are
    # rebuilt from nothing on every open, and the bar is in the document from the first
    # frame and shows only for an anchor.
    "target hints": (".lf-target-picker-hint.lf-current", None),
    "the response bar": (".lf-fab-bar .lf-composer[data-lf-open]", None),
    "the On panel": (".lf-queue-panel.open", ".lf-queue"),
    "the pages drawer": (".lf-others-panel.open", ".lf-others"),
    "the versions menu": (".lf-version-menu:popover-open", None),
    "the command reference": (".lf-command-reference.open", None),
    "page status": (".lf-status-detail:popover-open", None),
    "a reaction palette": (".lf-react-strip.lf-react-open", None),
}
RING_SCOPE_OPENER = {
    "an inline response": "#pr-exact-patch .lf-diff-file-comment",
    "the On panel": ".lf-queue",
    "a thread card": '.lf-margin-marker[data-lf-kinds~="comment"]',
    "the Page Map dialog": ".lf-page-map-toggle",
    "a reaction palette": ".lf-react-strip > .lf-react-trigger",
    # Any control inside the diff puts the user in its scope, where `]` lands a line.
    "a landed diff line": "#pr-exact-patch summary",
}
# The window a scope's own surface stands in, where that is not the page's own. These
# entries are floors the layer states rather than preferences: the Page Map control is drawn
# under the margin's breakpoint and nowhere else, while the contents-link and thread-card
# samples use a wide window where their page-margin surfaces can stand beside the source.
# Every other scope is read at the width the page opened at.
RING_VIEWPORT = (1200, 900)
# Scopes whose own route starts with Threads shut. A thread card and the narrow map need
# page-margin surfaces the panel replaces; the thread-list sample's `g T` is the door
# under test, and now correctly toggles an already-open panel closed.
RING_SCOPES_STARTING_WITHOUT_PANEL = {
    "an inline response",
    "the thread list",
    "a walked thread",
    "an inline thread",
    "a contents link",
    "a thread card",
    "the Page Map dialog",
    "a landed diff line",
}
RING_SCOPE_WIDTH = {
    "a contents link": 1600,
    "an inline thread": 1600,
    "a thread card": 1600,
    "the Page Map dialog": 760,
}
# Focus put back at the document's start. A blur retains the previous sequential
# navigation position, which would make the opening key sequences depend on the last case.
RING_FOCUS_START = RELEASE_FOCUS
RING_NEW_STOP = browser_function("focus_rings.js", "newStop", using="control_name.js")
SEEN_STOP = browser_function("focus_rings.js", "seenStop", using="control_name.js")
# Both readings of a Tab's landing in one round trip: whether the stop is new, and for a
# new one, what it shows of where the keyboard is.
WALKED_STOP = f"""() => {{
  const stop = ({RING_NEW_STOP})();
  return [stop, stop === "new" ? ({SEEN_STOP})() : null];
}}"""


def _tab_stops_without_indication(page, stem):
    """Walk the page's whole ordinary Tab order, Threads open, and name every stop
    that shows nothing of where the keyboard is. The panel is closed again after."""
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.evaluate("() => { window.__lfSeen = new WeakSet(); }")
    page.evaluate(RELEASE_FOCUS)
    failures = []
    empty = 0
    for _ in range(400):
        page.keyboard.press("Tab")
        stop, lost = page.evaluate(WALKED_STOP)
        if stop == "seen":
            break
        if stop == "empty":
            empty += 1
            assert empty <= 2, f"Tab never entered {stem}"
            continue
        empty = 0
        if lost:
            failures.append(f"{stem}: {lost}")
    else:
        raise AssertionError(f"Tab order never came round in {stem}")
    page.get_by_role("button", name="Close threads", exact=True).click()
    panel_settled(page, open=False)
    page.evaluate(RELEASE_FOCUS)
    return failures


def test_the_focus_sweep_distinguishes_stops_inside_a_live_frame(browser):
    page = browser.new_page()
    page.set_content(
        '<iframe srcdoc="<button id=first>First</button>'
        '<button id=second>Second</button>"></iframe>'
    )
    page.evaluate("() => { window.__lfSeen = new WeakSet(); }")
    page.frame_locator("iframe").locator("#first").focus()
    assert page.evaluate(RING_NEW_STOP) == "new"
    page.frame_locator("iframe").locator("#second").focus()
    assert page.evaluate(RING_NEW_STOP) == "new"


# Every declaration in the page's composed layer that lifts a box off the page: a
# box-shadow with a blur radius. A ring is `0 0 0 Npx` and an inset band is `inset …`, so
# the reading asks for a third length that is not nought — which is the one thing that
# separates elevation from the other two uses of the property, and is decidable from the
# declaration where "is this a shadow" is not.
#
# Flat and condition-blind for the reasons RING_NAMES gives next door: nothing re-runs a
# selector, and a shadow painted only in some other medium is one this reading should say
# nothing about.
ELEVATION_SHADOWS = """() => {
  const found = [];
  const eaten = new Set();
  const eat = (sheet) => {
    if (!sheet || eaten.has(sheet)) return;
    eaten.add(sheet);
    let list;
    try { list = sheet.cssRules; } catch { return; }  // a sheet from another origin
    const walk = (from) => {
      for (const rule of from) {
        for (const property of ['box-shadow', '--lf-lift']) {
          const value = rule.style?.getPropertyValue(property)?.trim();
          if (!value || value === 'none') continue;
          // The blur, which is the third length of a layer, past the two offsets. A ring
          // writes `0 0 0 Npx` and has none; an inset band is not a lift at all. Read per
          // layer, because a control may state its ring and its lift in one declaration.
          const lifts = value.split(/,(?![^(]*\\))/).filter((layer) => {
            if (/(^|\\s)inset(\\s|$)/.test(layer)) return false;
            const lengths = layer.trim().split(/\\s+/)
              .filter((token) => /^-?(\\d*\\.)?\\d+(px)?$/.test(token));
            return lengths.length >= 3 && parseFloat(lengths[2]) !== 0;
          });
          if (!lifts.length) continue;
          const own = rule.selectorText;
          const up = rule.parentRule?.selectorText;
          found.push({
            said: own && up ? `${up} { ${own}` : (own ?? up ?? '(a declaration)'),
            property,
            value: lifts.map((layer) => layer.trim()).join(', '),
          });
        }
        if (rule.cssRules) walk(rule.cssRules);
      }
    };
    walk(list);
  };
  const roots = [document];
  for (const root of roots) {
    for (const sheet of root.styleSheets) eat(sheet);
    for (const sheet of root.adoptedStyleSheets) eat(sheet);
    for (const el of root.querySelectorAll('*')) if (el.shadowRoot) roots.push(el.shadowRoot);
  }
  return found;
}"""


# A box that spends --shade, since the token itself is the same `light-dark()` text
# under either scheme.
PAINTED_SHADE = """() => {
  const probe = document.createElement('div');
  probe.style.color = 'var(--shade)';
  document.body.append(probe);
  const ink = getComputedStyle(probe).color;
  probe.remove();
  return ink;
}"""


def test_every_shadow_the_layer_lifts_a_box_with_is_cast_in_the_scheme_s_own_ink(
    browser, serve
):
    """A drop shadow written as rgba(0,0,0,α) can only be right about one ground.

    At .12 over the light paper a menu lifts its ground by 10 L*. The same declaration
    over the dark paper lifts it by 1.4, which is a shadow that is in the stylesheet and
    not on the screen — and nine of the layer's twelve elevation shadows were written that
    way, each with an alpha of its own between .12 and .24. --shade is the ink, stated once
    per scheme, and depth is left to the offsets and the blur that were already saying it.

    Asked of the declarations rather than of the paint, because that is where the fault
    is: on the dark ground the difference between the value that reads and the value that
    does not is 4 L*, which no screenshot of a blurred edge will tell you about reliably,
    while "does this name the token" is exact. The two schemes are then asked for
    different answers from the token itself, which is the whole of what one hard-coded
    colour could not do.
    """
    page = open_page(browser, serve(LONG_PAGE))
    lifted = page.evaluate(ELEVATION_SHADOWS)
    assert len(lifted) >= 10, (
        f"the layer declares {len(lifted)} elevation shadows, which is fewer than it "
        f"ships: this reading has stopped finding them and the assertion below is "
        f"about nothing"
    )
    raw = [shadow for shadow in lifted if "var(--shade)" not in shadow["value"]]
    assert not raw, (
        f"{len(raw)} of the layer's {len(lifted)} elevation shadows are cast in a "
        f"colour of their own rather than in --shade, so the dark scheme cannot answer "
        f"for them:\n  "
        + "\n  ".join(f"{s['said']} — {s['property']}: {s['value']}" for s in raw)
    )
    light = page.evaluate(PAINTED_SHADE)
    page.close()

    dark = open_page(browser, serve(LONG_PAGE), color_scheme="dark")
    shade = dark.evaluate(PAINTED_SHADE)
    assert shade.strip() and shade.strip() != light.strip(), (
        f"both schemes cast their shadows in {shade!r}, so routing them through a token "
        f"bought the dark page nothing it did not already have"
    )


# Every box the layer promises a press on, wherever it stands. Not a list of class names:
# what makes something a target is that the runtime built it (data-lf-offer) or that it
# stands in the runtime's own layer, and that the page under the pointer says a press
# lands there. A twelfth control joins by being one, which is how the six this first
# reported were found.
#
# The reading takes the element's box together with any absolutely positioned pseudo it
# hangs, because a control may enlarge its target outside layout rather than make the
# visible line or row taller.
#
# Inline boxes are out, and that is the target-size exception rather than an excuse: a
# link inside a sentence is sized by the words around it, and nothing can be done about
# that which does not damage the sentence.
AIM_BOXES = """(floor) => {
  const found = [];
  const seen = new Set();
  for (const el of document.querySelectorAll(
    '[data-lf-offer], .lf-chrome button, .lf-chrome [role="button"],' +
    ' .lf-chrome [role="checkbox"], .lf-chrome [role="tab"], .lf-chrome .lf-btn,' +
    ' .lf-chrome .lf-outline-chip, .lf-chrome .lf-quote'
  )) {
    if (seen.has(el)) continue;
    seen.add(el);
    const style = getComputedStyle(el);
    if (!['pointer', 'grab'].includes(style.cursor)) continue;
    // A box that takes no press is not an aim, however its cursor reads.
    if (style.pointerEvents === 'none') continue;
    if (!el.checkVisibility({ visibilityProperty: true, opacityProperty: true })) continue;
    if (style.display === 'inline') continue;
    // The option mark is the one control held out, and it is a handover rather than an
    // exemption: its box is being rewritten alongside the group's pressable rule, and
    // this line goes with that change. It stands at 11x11 today.
    if (el.classList.contains('lf-pick')) continue;
    const box = el.getBoundingClientRect();
    if (!box.width || !box.height) continue;
    let [w, h] = [box.width, box.height];
    for (const pseudo of ['::before', '::after']) {
      const at = getComputedStyle(el, pseudo);
      if (at.content === 'none' || at.position !== 'absolute') continue;
      w = Math.max(w, parseFloat(at.width) || 0);
      h = Math.max(h, parseFloat(at.height) || 0);
    }
    const name = (el.className || el.tagName).toString().trim().split(/\\s+/)[0]
      + ` ${JSON.stringify((el.textContent || '').trim().slice(0, 32))}`;
    if (Math.min(w, h) < floor - 0.5)
      found.push(`${name} at ${w.toFixed(1)}x${h.toFixed(1)}`);
  }
  return found;
}"""

# What the sweep has to have stood in front of before its answer means anything. Each is
# on a surface the walk has to open, and each was under the floor.
AIM_SURFACES = (
    ".lf-thread-action",
    ".lf-preview",
    ".lf-outline-chip",
    ".lf-version-diff",
    ".lf-command-reference-command",
    ".lf-quote",
    ".lf-tab-btn",
    ".lf-grip",
)


def _each_aim_surface(page, page_dir):
    """Stand each surface up in turn, yielding at every stop.

    In turn rather than all at once, because they do not coexist: the reference is modal
    and takes the version menu down as it opens, so a sweep that waited for the last of
    them would meet a page that had put two of the controls away again.
    """
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    comment = next(
        e["id"] for e in events_model.read_events(page_dir) if e["kind"] == "comment"
    )
    resolved_before = page.locator('.lf-thread[data-resolved="true"]').count()
    # A resolved thread, which is the only state that has a Reopen to aim at.
    page.locator(f'.lf-thread[data-id="{comment}"] .lf-thread-summary').click()
    page.locator(f'.lf-thread[data-id="{comment}"] .lf-resolve').click()
    round_trip(page)
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text(
        f"Resolved ({resolved_before + 1})"
    )
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    # Narrowing retains the card's disclosure, so the resolved thread comes back open
    # and a second press on its summary would put the Reopen away again.
    expect(page.locator(f'.lf-thread[data-id="{comment}"]')).to_have_js_property(
        "open", True
    )
    expect(page.locator(f'.lf-thread[data-id="{comment}"] .lf-reopen')).to_be_visible()
    yield

    banner_control(page, ".lf-version").click()
    expect(page.locator(".lf-version-menu")).to_be_visible()
    yield
    page.keyboard.press("Escape")

    # The first press can open the reference or expand the shortcut bar.
    page.keyboard.press("?")
    if not page.locator(".lf-command-reference").is_visible():
        page.keyboard.press("?")
    expect(page.locator(".lf-command-reference-command").first).to_be_visible()
    yield


# Every kind of box AIM_SURFACES names, beside the widgets whose built controls the
# sweep reads at rest: tabs, a board's grips, a question with its own Done and field,
# and a suggestion's margin pair.
AIM_PAGE = leaf_page(
    "aims",
    """<h1 id="t">Aims</h1>
<p id="aim-lead">The first view holds the board and the question.</p>
<lf-tabs id="aim-views">
  <lf-tab id="aim-first" label="First">
    <lf-board id="aim-board">
      <lf-column id="aim-todo" label="Todo">
        <lf-card id="aim-card"><strong>Heated perch</strong></lf-card>
        <lf-card id="aim-other"><strong>Squirrel baffle</strong></lf-card>
      </lf-column>
      <lf-column id="aim-done" label="Done"></lf-column>
    </lf-board>
    <lf-ask id="aim-ask"><h2>Which jobs?</h2>
      <lf-options id="aim-jobs" choose multiple>
        <lf-option id="aim-mounts">Replace the mounts</lf-option>
        <lf-option id="aim-bath">Heat the bird bath</lf-option>
      </lf-options>
    </lf-ask>
    <p>Start at <lf-suggestion id="aim-change"><lf-old>nine.</lf-old><lf-new>ten.</lf-new>
    </lf-suggestion></p>
  </lf-tab>
  <lf-tab id="aim-second" label="Second"><p>The second view.</p></lf-tab>
</lf-tabs>""",
)


DISCLOSURE_TABLE_PAGE = leaf_page(
    "disclosure in a wide table",
    '<h1 id="t">Sessions</h1>\n<table id="sessions"><tbody><tr>'
    '<td><details id="more"><summary>More</summary><p>Detail.</p></details></td>'
    + "".join(f"<td>value_number_{i}</td>" for i in range(12))
    + "</tr></tbody></table>",
)


def test_a_disclosure_is_a_scrolling_box_s_own_stop(browser, serve):
    """A box holding a control of its own is reached through that control, and a
    disclosure's `summary` is one: Tab stands on it, and moving along the box from
    there scrolls it. Counted as nothing, it gave the table a second stop of the
    sweep's in front of the one it already had."""
    page = open_page(browser, serve(DISCLOSURE_TABLE_PAGE))
    resized(page, 420, 900)
    table = page.locator("#sessions")
    assert table.evaluate("t => t.scrollWidth > t.clientWidth"), (
        "this table fits, so it proves nothing"
    )
    expect(table).not_to_have_attribute("tabindex", "0")
    assert page.locator("#more > summary").evaluate("s => s.tabIndex") == 0


def test_a_control_tab_skips_leaves_a_scrolling_box_its_own_stop(browser, serve):
    """A control inside a shadow tree whose host is out of the order is one Tab never
    reaches, so a scrolling box holding only that is still the sweep's to give a stop;
    with the host in the order, its control is the box's own."""
    page = open_page(browser, serve(DISCLOSURE_TABLE_PAGE))
    resized(page, 420, 900)
    # A box a script builds is swept when its builder asks, as a module's would be.
    boxes = page.evaluate(
        """async () => {
          const {reachScrollers} = await window.__lfCheckApi();
          const ids = ["out", "in"].map((order) => {
          const box = document.createElement("div");
          box.id = `box-${order}`;
          box.style.cssText = "width:200px;overflow-x:auto;white-space:nowrap";
          const host = document.createElement("span");
          if (order === "out") host.setAttribute("tabindex", "-1");
          host.attachShadow({mode: "open"}).innerHTML = "<button>Inside</button>";
          box.append(host, "x".repeat(400));
          document.querySelector("main").append(box);
          return box.id;
          });
          reachScrollers(document.querySelector("main"));
          return ids;
        }"""
    )
    out, inside = (page.locator(f"#{box}") for box in boxes)
    expect(out).to_have_attribute("tabindex", "0")
    expect(inside).not_to_have_attribute("tabindex", "0")


# One step of `handBack`, run as a layer closes with the user inside it: `layer` holds
# the button they stand on, and hiding it drops their focus. `shut` is a hidden button
# and `open` a shown one, both at the end of `main`.
HAND_BACK = """async (step) => {
  const {handBack} = await window.__lfWidgetApi();
  const frame = () => new Promise((done) => requestAnimationFrame(() => done()));
  const main = document.querySelector('main');
  const made = (tag, id, parent = main, hidden = false) => {
    document.getElementById(id)?.remove();
    const node = document.createElement(tag);
    node.id = id;
    node.textContent = id;
    node.hidden = hidden;
    parent.prepend(node);
    return node;
  };
  const open = made('button', 'open'), shut = made('button', 'shut', main, true);
  const layer = made('div', 'layer');
  made('button', 'inside', layer).focus();
  layer.hidden = true;
  if (step === 'first that lands') handBack(shut, open);
  if (step === 'nothing to land on') handBack(document.createElement('button'));
  if (step === 'body') handBack(document.body);
  if (step === 'shown by the next frame') {
    handBack(shut);
    shut.hidden = false;
  }
  if (step === 'user moved on') {
    handBack(shut);
    open.focus();
    shut.hidden = false;
  }
  if (step === 'user pressed another key') {
    handBack(shut);
    document.dispatchEvent(new KeyboardEvent('keydown', {key: 'x', bubbles: true}));
    shut.hidden = false;
  }
  if (step === 'user landed and let go') {
    handBack(shut);
    open.focus();
    open.blur();
    shut.hidden = false;
  }
  await frame();
  await frame();
  const at = document.activeElement;
  return at.id || at.localName;
}"""


def test_a_closing_layer_hands_the_user_back_to_the_first_place_that_takes_them(
    browser, serve
):
    """Every closer names where the user goes back to, most particular first, and
    `handBack` lands them on the first that takes focus. A place still in the document
    gets the next frame, for a close whose own paint still hides it, unless the user
    moved, let go after a landing, or pressed another key first. With nowhere to go
    the user is let go on the block they are reading, so their next Tab carries on
    from it: not from the closed layer, which is where the browser left them, and
    not from the top of the document, which is where focusing the body would. The
    body is nowhere, for an opener read while nothing held focus."""
    page = open_page(browser, serve(LONG_PAGE))
    landed = {
        step: page.evaluate(HAND_BACK, step)
        for step in [
            "first that lands",
            "shown by the next frame",
            "user moved on",
            "user pressed another key",
            "user landed and let go",
        ]
    }
    assert landed == {
        "first that lands": "open",
        "shown by the next frame": "shut",
        "user moved on": "open",
        "user pressed another key": "body",
        "user landed and let go": "body",
    }
    for step in ["nothing to land on", "body"]:
        assert page.evaluate(HAND_BACK, step) == "body"
        page.keyboard.press("Tab")
        assert page.evaluate(
            "() => !document.activeElement.matches('#open, #shut, .lf-skip')"
        ), f"{step}: the next Tab did not carry on from the block being read"


@pytest.mark.parametrize("new_composer", [False, True], ids=["control", "composer"])
def test_a_reaction_withdrawal_does_not_take_back_a_newer_place(
    browser, serve, new_composer
):
    """Taking a reaction back ends its response gesture before the log answers it."""
    source = leaf_page(
        "A later response",
        '<h1>Review</h1><section id="first"><h2>First passage</h2>'
        '<button id="first-control">First control</button></section>'
        '<div style="height:1500px"></div>'
        '<section id="later"><h2>Later passage</h2>'
        '<button id="later-control">Later control</button></section>'
        '<div style="height:1200px"></div>',
    )
    url = serve(source)
    append_carried_log_record(
        serve.page_dir,
        {
            "id": "reaction-in-force",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "token": "keep",
            "anchor": {"section": "first-control"},
        },
    )
    page = open_page(browser, url)
    page.locator("#first-control").click()
    page.keyboard.press("e")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("1")
    holding(page, held, 1, "the reaction withdrawal")
    page.locator("#later-control").click()
    current = page.locator("#later-control")
    if new_composer:
        page.keyboard.press("c")
        current = page.locator(".lf-fab-input")
        write(current, "Keep this newer draft")
    expect(current).to_be_focused()
    before = page.evaluate("scrollY")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(current).to_be_visible()
    expect(current).to_be_focused()
    assert page.evaluate("scrollY") == before
    if new_composer:
        expect(current).to_have_js_property("value", "Keep this newer draft")
    withdrawn = events_model.read_events(serve.page_dir)[-1]
    assert (withdrawn["kind"], withdrawn["undoes"]) == (
        "undo",
        "reaction-in-force",
    )


@pytest.mark.parametrize(
    "newer_control", [False, True], ids=["arrival", "newer-control"]
)
def test_a_reference_command_finishes_its_gesture_before_a_newer_control(
    browser, serve, newer_control
):
    """Modal close and command dispatch share one gesture, before another input arrives."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Reference arrival",
                '<h1>Review</h1><div style="height:1200px"></div>'
                '<button id="origin">Original control</button>'
                '<button id="later">Later control</button><div style="height:1000px"></div>',
            )
        ),
    )
    page.locator("#origin").click()
    page.keyboard.press("?")
    page.keyboard.press("?")
    search = page.get_by_role("combobox", name="Search commands")
    search.fill("comment on the control")
    command = page.get_by_role("button", name="Comment on the control", exact=True)
    expect(command).to_be_visible()
    expect(command).to_have_attribute("data-lf-available", "true")
    with held_frames(page):
        box = command.bounding_box()
        assert box is not None
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        expect(page.locator(".lf-command-reference")).to_be_hidden()
        if newer_control:
            box = page.locator("#later").bounding_box()
            assert box is not None
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            expect(page.locator("#later")).to_be_focused()
        before = page.evaluate("scrollY")
    rendered(page)
    if newer_control:
        expect(page.locator("#later")).to_be_focused()
    else:
        expect(page.locator(".lf-fab-input")).to_be_focused()
        expect(page.locator("#origin")).to_have_class(re.compile("lf-projected-mark"))
    assert page.evaluate("scrollY") == before


@pytest.mark.parametrize("native_move", [True, False])
@pytest.mark.parametrize("renderer", ["children", "lit"])
def test_retained_moves_keep_native_editor_and_frame_state(
    browser, serve, native_move, renderer
):
    """A reorder or a move to another parent keeps the user typing in the moved row,
    with no focus hold of the caller's, whether or not the browser has `moveBefore`;
    a native move also keeps the row's iframe document."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Retained rows",
                '<h1>Retained rows</h1><div id="rows"></div><div id="other"></div>',
            )
        ),
    )
    page.evaluate(
        """async ([nativeMove, renderer]) => {
      const {render, repeat} = await window.__lfWidgetApi();
      const {setChildren: orderChildren} = await window.__lfWidgetApi();
      const {move} = await window.__lfWidgetApi();
      const rows = document.querySelector('#rows');
      if (!nativeMove) Element.prototype.moveBefore = undefined;
      const nodes = ['a', 'b', 'c'].map(id => {
        const row = document.createElement('div');
        row.dataset.row = id;
        row.innerHTML = `<input aria-label="${id}">
          <iframe title="${id}" srcdoc="<p>Retained frame</p>"></iframe>`;
        return row;
      });
      const paint = nodes => renderer === 'lit'
        ? render(repeat(nodes, node => node.dataset.row, node => node), rows)
        : orderChildren(rows, nodes);
      paint(nodes);
      const editor = rows.querySelector('[data-row=c] input');
      window.blurs = 0;
      editor.addEventListener('blur', () => window.blurs++);
      editor.addEventListener('keydown', event => {
        if (event.key === 'ArrowUp' && event.altKey) {
          event.preventDefault();
          paint([nodes[2], nodes[0], nodes[1]]);
        } else if (event.key === 'ArrowDown' && event.altKey) {
          event.preventDefault();
          const other = document.querySelector('#other');
          if (renderer === 'lit') render(nodes[2], other);
          else move(other, nodes[2], null);
        }
      });
    }""",
        [native_move, renderer],
    )
    editor = page.get_by_role("textbox", name="c", exact=True)
    editor.fill("unfinished words")
    editor.evaluate("node => node.setSelectionRange(3, 9, 'backward')")
    frame = page.locator("[data-row=c] iframe")
    expect(page.frame_locator("[data-row=c] iframe").locator("p")).to_have_text(
        "Retained frame"
    )
    frame.evaluate("node => window.heldDocument = node.contentDocument")
    for key, parent in [("Alt+ArrowUp", "#rows"), ("Alt+ArrowDown", "#other")]:
        page.keyboard.press(key)
        expect(page.locator(f"{parent} > [data-row=c]")).to_have_count(1)
        if key == "Alt+ArrowUp":
            expect(page.locator("#rows > [data-row]").first).to_have_attribute(
                "data-row", "c"
            )
        expect(editor).to_be_focused()
        expect(editor).to_have_value("unfinished words")
        assert editor.evaluate(
            "node => [node.selectionStart, node.selectionEnd, node.selectionDirection]"
        ) == [3, 9, "backward"]
        if native_move:
            assert page.evaluate("window.blurs") == 0
            assert frame.evaluate(
                "node => node.contentDocument === window.heldDocument"
            )
        else:
            assert page.evaluate("window.blurs") > 0


def test_unfocused_editor_move_leaves_later_selection_alone(browser, serve):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Editor caret",
                "<h1>Editor caret</h1><div id='first'></div><div id='second'></div>",
            )
        ),
    )
    page.evaluate("""() => new Promise(resolve => {
      const field = document.createElement('leaf-text');
      field.value = 'Intentional selection';
      document.querySelector('#first').append(field);
      document.addEventListener('selectionchange', () => queueMicrotask(resolve), {once: true});
      field.focus();
      field.setSelectionRange(4, 4);
    })""")
    held = page.evaluate("""() => {
      const field = document.querySelector('#first leaf-text');
      field.blur();
      const unfocused = !field.matches(':focus');
      document.querySelector('#second').moveBefore(field, null);
      return [field.selectionStart, unfocused];
    }""")
    assert held == [4, True]
    editor = page.locator("#second leaf-text")
    page.evaluate("""() => new Promise(resolve => {
      document.addEventListener('selectionchange', () => queueMicrotask(resolve), {once: true});
      const field = document.querySelector('#second leaf-text');
      field.focus();
      field.setSelectionRange(9, 9);
    })""")
    expect(editor).to_be_focused()
    assert editor.evaluate("node => [node.selectionStart, node.selectionEnd]") == [9, 9]
