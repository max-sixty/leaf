"""Keyboard routes to commands: inline hints, contextual aliases and their forwarding,
disabled and overridden routes, and the targets offered native controls get."""

import pytest
from playwright.sync_api import expect
from render_cases_interaction import SEATED_OBLIGATION_LAYER
from render_harness import leaf_page, open_page, put_preview_away

from browser.navigation import offered_routes
from leaf.source.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


KEYBOARD_HINT_REGISTRY = {
    "lf-keyboard-probe": {
        "description": "Exercises declared keyboard commands and their controls.",
        "attributes": {
            "properties": {
                "asks": {"type": "boolean"},
            },
            "required": ["id"],
        },
        "content": "empty",
        "verbs": SEATED_OBLIGATION_LAYER["lf-verdict"]["verbs"],
        "awaits": SEATED_OBLIGATION_LAYER["lf-verdict"]["awaits"],
    }
}


KEYBOARD_HINT_MODULE = """\
import { offer } from '/runtime/lib/controls.js';
import { keeps, keepsText } from '/runtime/lib/keeps.js';

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
      this.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
    };
    const ariaDisable = offer('button', '', 'Toggle ARIA disabled');
    ariaDisable.onclick = () => {
      this.ariaRefused = !this.ariaRefused;
      this.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
    };
    const guard = offer('button', '', 'Toggle availability');
    guard.onclick = () => { this.allowed = !this.allowed; this.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true })); };
    const replace = offer('button', '', 'Replace action control');
    replace.onclick = () => {
      const prior = this.seat;
      this.makeControl();
      prior.replaceWith(this.seat);
      this.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
    };
    const quiet = offer('button', '', 'Quiet action');
    this.append(disable, ariaDisable, guard, replace, quiet);
    const scope = { title: 'In the command probe', rows: [
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
    ] };
    this.lfCommands = scope;
    this.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
    editor.lfCommands = scope;
    editor.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
    this.closest('main').lfCommands = { title: 'Outside the widget', rows: [{
      id: 'probe.outer', title: 'Outer digit', keys: ['1'],
      run: () => keepsText(this.result, 'Outer applied'),
    }] };
    this.closest('main').dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
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


KEYBOARD_ROUTE_MODULE = """\
import { offer } from '/runtime/lib/controls.js';
import { keepsText } from '/runtime/lib/keeps.js';

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
    this.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
    this.closest('section').lfCommands = { title: 'Outside parameterized actions', rows: [{
      id: 'probe.outer', keys: ['1'], title: 'Apply the outer action', line: 'outer action',
      run: () => keepsText(result, 'Outer applied'),
    }] };
    this.closest('section').dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
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
import { offer } from '/runtime/lib/controls.js';
import { keepsText } from '/runtime/lib/keeps.js';

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
    this.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
    const replace = offer('button', '', 'Replace declaration');
    replace.onclick = () => {
      this.lfCommands = { title: 'In explicit actions', rows: [{id: 'probe.replacement', title: 'Replacement',
        contextKeys: ['2'], run: () => keepsText(result, 'Replacement applied')}] };
      this.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
      this.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
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
                '<h1>Explicit bindings</h1><lf-group id="question" label="Which action?"><h2 id="question-h">Which action?</h2>'
                '<lf-keyboard-probe id="probe" asks></lf-keyboard-probe></lf-group>',
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
                '<lf-group id="question" label="Which action?"><h2 id="question-h">Which action?</h2>'
                '<lf-keyboard-probe id="probe" asks></lf-keyboard-probe></lf-group>',
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
import { offer } from '/runtime/lib/controls.js';
import { keepsText } from '/runtime/lib/keeps.js';

customElements.define('lf-keyboard-probe', class extends HTMLElement {
  connectedCallback() {
    const control = offer('button', '', 'Apply operation');
    const result = offer('output', '', 'No action');
    let count = 0;
    this.append(control, result);
    this.lfCommands = { title: 'In escape operation', rows: [{id: 'probe.escape', title: 'Apply operation',
      keys: ['x'], contextKeys: ['Escape'], control, bindingBadge: null,
      run: () => keepsText(result, `Applied ${++count}`)}] };
    this.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
  }
});
"""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "contextual escape",
                '<h1>Explicit bindings</h1><lf-group id="question" label="Which action?"><h2 id="question-h">Which action?</h2>'
                '<lf-keyboard-probe id="probe" asks></lf-keyboard-probe></lf-group>',
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
    # The Tab showed the control's preview, Escape's first step (WCAG 1.4.13).
    put_preview_away(page)
    page.keyboard.press("Escape")
    expect(result).to_have_text("Applied 4")


def test_context_aliases_do_not_collide_with_authored_command_ids(browser, serve):
    """A contextual projection keeps both commands when an authored id ends in .context."""
    module = """\
import { offer } from '/runtime/lib/controls.js';
import { keepsText } from '/runtime/lib/keeps.js';

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
    this.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
  }
});
"""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "context command identity",
                '<h1>Explicit bindings</h1><button id="outside">Outside</button>'
                '<lf-group id="question" label="Which action?"><h2 id="question-h">Which action?</h2>'
                '<lf-keyboard-probe id="probe" asks></lf-keyboard-probe></lf-group>',
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
import { offer } from '/runtime/lib/controls.js';
import { keepsText } from '/runtime/lib/keeps.js';

customElements.define('lf-keyboard-probe', class extends HTMLElement {
  connectedCallback() {
    const result = offer('output', '', 'No action');
    let count = 0;
    this.append(result);
    this.lfCommands = { title: 'In guarded operation', rows: [{id: 'probe.guarded', title: 'Guarded operation',
      contextKeys: ['F8'], runFromCommandReference: false,
      run: () => keepsText(result, `Applied ${++count}`)}] };
    this.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
  }
});
"""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "contextual reference policy",
                '<h1>Explicit bindings</h1><lf-group id="question" label="Which action?"><h2 id="question-h">Which action?</h2>'
                '<lf-keyboard-probe id="probe" asks></lf-keyboard-probe></lf-group>',
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
import { offer } from '/runtime/lib/controls.js';
import { keepsText } from '/runtime/lib/keeps.js';

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
      runKey: binding => keepsText(result, `${binding}:${++count}`),
    }] };
    this.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
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
    registry = {"lf-verdict": dict(SEATED_OBLIGATION_LAYER["lf-verdict"])}
    page = open_page(
        browser,
        serve(
            leaf_page(
                "route hint override",
                '<h1>Inspection</h1><lf-group id="question" label="Inspect this?"><h2 id="question-h">Inspect this?</h2>'
                '<lf-verdict id="probe" asks>The proposal.</lf-verdict></lf-group>',
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


SHIFTING_CONTROL_MODULE = """\
import { offer } from '/runtime/lib/controls.js';
import { keepsText } from '/runtime/lib/keeps.js';

customElements.define('lf-keyboard-probe', class extends HTMLElement {
  connectedCallback() {
    const neighbour = offer('button', '', 'Neighbour');
    const control = offer('button', '', 'Apply');
    const result = offer('output', '', '0');
    this.append(neighbour, control, result);
    this.shift = (by) => { control.style.translate = by; this.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true })); };
    this.lfCommands = { title: 'In the probe', rows: [{
      id: 'probe.apply', title: 'Apply', contextKeys: ['1'], control,
      bindingBadge: null, run: () => keepsText(result, 'Applied'),
    }] };
    this.dispatchEvent(new CustomEvent('lf-commands', { bubbles: true, composed: true }));
  }
});
"""


def test_a_key_chip_keeps_its_corner_while_that_corner_serves(browser, serve):
    """A corner chip moves off a corner only when that corner stops serving.

    The chip leaves its control's upper-left corner, where it would cover the
    neighbour, for the upper-right. A change that frees the upper-left, as a press's
    scale can by a pixel, leaves it there, so it doesn't cross its control and back
    with every press.
    """
    page = open_page(
        browser,
        serve(
            leaf_page(
                "a chip keeps its corner",
                '<h1>Corners</h1><lf-group id="question" label="Apply this?"><h2 id="question-h">Apply this?</h2>'
                '<lf-keyboard-probe id="probe" asks></lf-keyboard-probe></lf-group>',
            ),
            layer_registry=KEYBOARD_HINT_REGISTRY,
            layer_widgets={"lf-keyboard-probe.js": SHIFTING_CONTROL_MODULE},
        ),
    )
    chip = page.locator(".lf-command-binding-badges .lf-command-binding-badge")
    control = page.get_by_role("button", name="Apply", exact=True)

    def side():
        rendered(page)
        at = chip.bounding_box()
        box = control.bounding_box()
        assert at and box
        middle = at["x"] + at["width"] / 2
        return "left" if middle < box["x"] + box["width"] / 2 else "right"

    page.keyboard.press("m")
    expect(chip).to_have_text("1")
    expect(chip).to_be_visible()
    assert side() == "right"
    page.locator("#probe").evaluate("probe => probe.shift('80px 0')")
    assert side() == "right"
    page.locator("#probe").evaluate("probe => probe.shift('')")
    assert side() == "right"
