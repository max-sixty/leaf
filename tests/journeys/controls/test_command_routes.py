"""Tests scheduled by the measured cost of their boundary."""

import re

import pytest
from browser.controls.test_command_routes import (
    KEYBOARD_HINT_MODULE,
    KEYBOARD_HINT_REGISTRY,
)
from playwright.sync_api import expect
from render_cases_navigation import go_to_address
from render_harness import leaf_page, open_page

from leaf.source.render_checks import rendered

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
import {offer} from '/runtime/lib/controls.js';
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
import {offer} from '/runtime/lib/controls.js';
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


@pytest.mark.parametrize("annotation_mode", ["overlay", "page"])
def test_widget_context_keys_work_without_an_obligation(
    browser, serve, annotation_mode
):
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


@pytest.mark.parametrize("hint_seat", ["widget", "corner"])
def test_widget_owned_inline_hints_follow_reachable_commands(browser, serve, hint_seat):
    """A package command needs no obligation role to expose its working keyboard route.

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
                '<lf-group id="question" label="Apply the operation?"><h2 id="question-h">Apply the operation?</h2>'
                '<lf-keyboard-probe id="probe" asks></lf-keyboard-probe></lf-group>',
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

    # The question context forwards the widget's declaration without an obligation allocator.
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
