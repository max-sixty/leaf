"""Keyboard routes to commands: inline hints, contextual aliases and their forwarding,
disabled and overridden routes, and the targets offered native controls get."""

import re

import pytest
from playwright.sync_api import expect
from render_cases_interaction import SEATED_OBLIGATION_LAYER
from render_cases_navigation import go_to_address
from render_harness import leaf_page, open_page

from browser.navigation import offered_routes
from leaf.render_checks import rendered
from leaf.schema import ELEMENT_ID

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
        "x-state": SEATED_OBLIGATION_LAYER["lf-verdict"]["x-state"],
        "x-awaits": SEATED_OBLIGATION_LAYER["lf-verdict"]["x-awaits"],
    }
}


KEYBOARD_HINT_MODULE = """\
import {commandScope, keeps, keepsText, offer, commandsChanged} from '/runtime/widget-api.js';

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
      commandsChanged(this);
    };
    const ariaDisable = offer('button', '', 'Toggle ARIA disabled');
    ariaDisable.onclick = () => {
      this.ariaRefused = !this.ariaRefused;
      commandsChanged(this);
    };
    const guard = offer('button', '', 'Toggle availability');
    guard.onclick = () => { this.allowed = !this.allowed; commandsChanged(this); };
    const replace = offer('button', '', 'Replace action control');
    replace.onclick = () => {
      const prior = this.seat;
      this.makeControl();
      prior.replaceWith(this.seat);
      commandsChanged(this);
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
    this.lfCommands = scope;
    commandsChanged(this);
    editor.lfCommands = scope;
    commandsChanged(editor);
    this.closest('main').lfCommands = { title: 'Outside the widget', rows: [{
      id: 'probe.outer', title: 'Outer digit', keys: ['1'],
      run: () => keepsText(this.result, 'Outer applied'),
    }] };
    commandsChanged(this.closest('main'));
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


KEYBOARD_ROUTE_MODULE = """\
import {keepsText, offer, commandsChanged} from '/runtime/widget-api.js';

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
    this.lfCommands = { title: 'In parameterized actions', rows: [{
      id: 'probe.apply', keys: ['1', '2'], title: 'Apply an action', line: 'apply',
      routes: [
        {id: 'probe.first', binding: '1', control: first, when: () => !firstUnavailable,
         bindingBadge: firstHint, title: 'Apply the first action'},
        {id: 'probe.second', binding: '2', control: second,
         bindingBadge: secondHint, title: 'Apply the second action'},
      ],
      run: apply,
    }] };
    commandsChanged(this);
    this.closest('section').lfCommands = { title: 'Outside parameterized actions', rows: [{
      id: 'probe.outer', keys: ['1'], title: 'Apply the outer action', line: 'outer action',
      run: () => keepsText(result, 'Outer applied'),
    }] };
    commandsChanged(this.closest('section'));
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
    offered = offered_routes(page)
    assert offered["probe.second"] == ["2"]
    assert "probe.first" not in offered

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
import {keepsText, offer, commandsChanged} from '/runtime/widget-api.js';

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
    this.lfCommands = { title: 'In explicit actions', rows: rows };
    commandsChanged(this);
    const replace = offer('button', '', 'Replace declaration');
    replace.onclick = () => {
      this.lfCommands = { title: 'In explicit actions', rows: [{id: 'probe.replacement', title: 'Replacement',
        contextKeys: ['2'], run: () => keepsText(result, 'Replacement applied')}] };
      commandsChanged(this);
      commandsChanged(this);
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
    assert offered_routes(page)["probe.action-1"] == ["1"]
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
    unbound = page.locator(
        '.lf-command-reference [role=option][data-lf-command="probe.action-11"]'
    )
    expect(unbound).to_have_attribute("data-lf-available", "true")
    expect(unbound).to_contain_text("Action 11")
    unbound.click()
    expect(result).to_have_text("Action 11 applied")

    page.get_by_role("button", name="Replace declaration").click()
    page.locator("#question").focus()
    rendered(page)
    page.keyboard.press("1")
    rendered(page)
    expect(result).to_have_text("Action 11 applied")
    page.keyboard.press("2")
    expect(result).to_have_text("Replacement applied")
    assert offered_routes(page)["probe.replacement"] == ["2"]
    page.keyboard.press("F10")
    rendered(page)
    expect(result).to_have_text("Replacement applied")


def test_restoring_obligation_focus_can_execute_its_command_in_the_same_turn(
    browser, serve
):
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
import {keepsText, offer, commandsChanged} from '/runtime/widget-api.js';

customElements.define('lf-keyboard-probe', class extends HTMLElement {
  connectedCallback() {
    const control = offer('button', '', 'Apply operation');
    const result = offer('output', '', 'No action');
    let count = 0;
    this.append(control, result);
    this.lfCommands = { title: 'In escape operation', rows: [{id: 'probe.escape', title: 'Apply operation',
      keys: ['x'], contextKeys: ['Escape'], control, bindingBadge: null,
      run: () => keepsText(result, `Applied ${++count}`)}] };
    commandsChanged(this);
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
    page.keyboard.press("Escape")
    expect(result).to_have_text("Applied 1")
    page.keyboard.press("?")
    reference_action = page.locator(
        '.lf-command-reference [role=option][data-lf-command="probe.escape"]'
        ".lf-command-reference-command"
    )
    expect(reference_action).to_have_attribute("data-lf-available", "true")
    reference_action.click()
    expect(result).to_have_text("Applied 2")
    expect(page.locator("#question")).to_be_focused()
    page.keyboard.press("Tab")
    expect(
        page.locator("#probe").get_by_role("button", name="Apply operation", exact=True)
    ).to_be_focused()
    page.keyboard.press("x")
    expect(result).to_have_text("Applied 3")
    page.keyboard.press("Escape")
    expect(result).to_have_text("Applied 4")


def test_context_aliases_do_not_collide_with_authored_command_ids(browser, serve):
    """A contextual projection keeps both commands when an authored id ends in .context."""
    module = """\
import {keepsText, offer, commandsChanged} from '/runtime/widget-api.js';

customElements.define('lf-keyboard-probe', class extends HTMLElement {
  connectedCallback() {
    const control = offer('button', '', 'Apply operation');
    const neighbour = offer('button', '', 'Neighbour operation');
    const result = offer('output', '', 'No action');
    let count = 0;
    this.append(control, neighbour, result);
    this.lfCommands = { title: 'In named operations', rows: [
      {id: 'probe.apply', title: 'Apply operation', keys: ['F8'], contextKeys: ['1'],
        control, run: () => keepsText(result, `Applied ${++count}`)},
      {id: 'probe.apply.context', title: 'Neighbour operation', keys: ['F9'],
        control: neighbour, run: () => keepsText(result, 'Neighbour applied')},
    ] };
    commandsChanged(this);
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
    for current_location in ["outside", "question"]:
        page.keyboard.press("?")
        for command_id, title in [
            ("probe.apply", "Apply operation"),
            ("probe.apply.context", "Neighbour operation"),
        ]:
            row = page.locator(
                f'.lf-command-reference [role=option][data-lf-command="{command_id}"]'
            )
            expect(row).to_have_count(1)
            expect(row).to_contain_text(title)
            expect(row).to_have_attribute(
                "data-lf-available",
                str(
                    current_location == "question" and command_id == "probe.apply"
                ).lower(),
            )
        page.keyboard.press("Escape")
        if current_location == "outside":
            page.keyboard.press("m")
            expect(page.locator("#question")).to_be_focused()
    page.keyboard.press("1")
    expect(result).to_have_text("Applied 1")
    page.keyboard.press("F9")
    rendered(page)
    expect(result).to_have_text("Applied 1")
    page.keyboard.press("Tab")
    expect(
        page.locator("#probe").get_by_role("button", name="Apply operation", exact=True)
    ).to_be_focused()
    page.keyboard.press("F8")
    expect(result).to_have_text("Applied 2")
    page.keyboard.press("F9")
    expect(result).to_have_text("Neighbour applied")


def test_context_forwarding_preserves_reference_activation_opt_out(browser, serve):
    """A contextual alias cannot turn a reading-only reference row into an action."""
    module = """\
import {keepsText, offer, commandsChanged} from '/runtime/widget-api.js';

customElements.define('lf-keyboard-probe', class extends HTMLElement {
  connectedCallback() {
    const result = offer('output', '', 'No action');
    let count = 0;
    this.append(result);
    this.lfCommands = { title: 'In guarded operation', rows: [{id: 'probe.guarded', title: 'Guarded operation',
      contextKeys: ['F8'], runFromCommandReference: false,
      run: () => keepsText(result, `Applied ${++count}`)}] };
    commandsChanged(this);
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
    reference_row = page.locator(
        '.lf-command-reference [role=option][data-lf-command="probe.guarded"]'
    )
    expect(reference_row).to_contain_text("Guarded operation")
    expect(reference_row).to_have_attribute("aria-disabled", "true")
    reference_row.click(force=True)
    rendered(page)
    expect(result).to_have_text("Applied 1")
    page.keyboard.press("Escape")
    expect(page.locator("#question")).to_be_focused()
    page.keyboard.press("F8")
    expect(result).to_have_text("Applied 2")


ROUTE_HINT_OVERRIDE_MODULE = """\
import {keepsText, offer, commandsChanged} from '/runtime/widget-api.js';

customElements.define('lf-verdict', class extends HTMLElement {
  connectedCallback() {
    const control = offer('button', '', 'Inspect');
    const inheritedHint = offer('kbd', 'lf-key-badge');
    inheritedHint.setAttribute('aria-hidden', 'true');
    const result = offer('output', '', '0');
    let count = 0;
    this.append(control, inheritedHint, result);
    this.lfCommands = { title: 'In the inspection', rows: [{
      id: 'probe.inspect', keys: ['x'], title: 'Inspect the proposal', line: 'inspect',
      bindingBadge: inheritedHint,
      routes: [{
        id: 'probe.inspect-proposal', binding: 'x', contextKeys: ['1'], decision: true,
        control, bindingBadge: null, title: 'Inspect the proposal',
      }],
      run: binding => keepsText(result, `${binding}:${++count}`),
    }] };
    commandsChanged(this);
  }
});
"""


def test_route_corner_hint_overrides_the_rows_face_in_obligation_and_widget(
    browser, serve
):
    """Explicit null chooses a corner hint instead of inheriting the row's face.

    Obligation forwarding and the intrinsic route must preserve that choice and merge into
    one hint when both bindings reach the same original command.
    """
    registry = {
        "lf-verdict": {
            key: value
            for key, value in SEATED_OBLIGATION_LAYER["lf-verdict"].items()
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
