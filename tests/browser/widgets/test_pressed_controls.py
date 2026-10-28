"""A pressed control keeps its face while its gesture travels, and takes the next press.

The rule is `browser/AGENTS.md`'s: a gesture draws its own result in the task that
handles it, and a disabled control, spinner or delivery status is not that result. A
widget that keeps its own record of a send in flight breaks it twice: the control under
the pointer flickers to a busy cursor or a disabled face for one round trip, and a
second press in that window is swallowed. Four bundled widgets once did both, each
found by hand, so this presses every control in every bundled package's worked
examples (`widget_quality.served_examples`) with the server's answer held."""

import pytest
from known_widget_findings import PACKAGES

from leaf import layer as layer_model
from leaf import schema as schema_model
from leaf.layer import checked_layer_inputs, compose_layer
from leaf.packages import package_layer_inputs
from leaf.render_checks import RENDER_VIEWPORT, rendered, wait_until_ready
from leaf.render_gate.scheme import arm_interception, served
from leaf.render_gate.widget_quality import example_pages, own_tags, served_examples
from leaf.structure import SourceDocument

# What a reader presses: a button, or a control that holds a choice.
CONTROL = (
    'button, [role="button"], [role="checkbox"], [role="radio"], [role="switch"], '
    '[role="option"], [role="tab"]'
)

# Every visible, enabled control inside one of the package's own widgets or the margin
# entries Leaf draws for one, shadow trees included, each marked so the driver can
# press it with the pointer, and named by its widget and words.
MARK_CONTROLS = f"""(tags) => {{
  const own = new Set(tags);
  const widgetOf = (element) => {{
    for (let at = element; at; at = at.parentElement ?? at.getRootNode().host) {{
      if (own.has(at.localName)) return at;
      const entry = at.dataset?.lfMarginFor;
      if (entry) return widgetOf(document.getElementById(entry));
    }}
    return null;
  }};
  const found = [];
  const walk = (root) => {{
    for (const element of root.querySelectorAll('*')) {{
      if (element.shadowRoot) walk(element.shadowRoot);
      delete element.dataset?.lfPressCheck;
      if (!element.matches({CONTROL!r})) continue;
      const widget = widgetOf(element);
      if (!widget) continue;
      if (element.disabled || element.getAttribute('aria-disabled') === 'true') continue;
      if (!element.checkVisibility({{ visibilityProperty: true }})) continue;
      element.dataset.lfPressCheck = String(found.length);
      const words = element.getAttribute('aria-label') || element.textContent.trim();
      found.push(`${{widget.localName}}#${{widget.id}} ${{JSON.stringify(words)}}`);
    }}
  }};
  walk(document.body);
  return found;
}}"""

# The deepest element at a point, read through shadow trees, and the control holding it.
AT_POINT = f"""const atPoint = (x, y) => {{
  let at = document.elementFromPoint(x, y);
  while (at?.shadowRoot) {{
    const inner = at.shadowRoot.elementFromPoint(x, y);
    if (!inner || inner === at) break;
    at = inner;
  }}
  let control = at;
  while (control && !control.matches?.({CONTROL!r}))
    control = control.parentElement ?? control.getRootNode().host;
  return {{ at, control }};
}};"""

# What the reader sees at the point: the cursor the element there computes, and whether
# the control holding it says it is unavailable or waiting. Null where no control
# stands there.
FACE_AT = f"""([x, y]) => {{
  {AT_POINT}
  const {{ at, control }} = atPoint(x, y);
  if (!control) return null;
  return {{
    cursor: getComputedStyle(at).cursor,
    disabled: control.disabled || control.getAttribute('aria-disabled') === 'true',
    busy: control.getAttribute('aria-busy') === 'true',
  }};
}}"""

# Whether the control at the point is still the element pressed there, which a widget
# relabels rather than replaces.
STILL_PRESSED = f"""([x, y, index]) => {{
  {AT_POINT}
  return atPoint(x, y).control?.dataset.lfPressCheck === String(index);
}}"""

# The tab's unresolved gestures by attempt, read through the check entry.
UNRESOLVED = """async () => {
  const boot = document.querySelector('script[data-lf-entry]').dataset.lfEntry;
  const api = await import(new URL('runtime/check-api.js', new URL(boot, location.href)));
  return api.readApplication().unresolved.map((entry) => entry.event.attempt);
}"""

# Whether every send has its outcome, by the runtime's own traffic ledger
# (runtime/traffic.js).
DELIVERED = """() => {
  const traffic = document.documentElement.dataset.lfTraffic;
  return !traffic || !JSON.parse(traffic).pending.length;
}"""

# The widgets whose presses once flickered, which the sweep must reach sending.
REACHED = {"lf-playground", "lf-option", "lf-suggestion"}


def _example_pages(package):
    composition = compose_layer(checked_layer_inputs(package_layer_inputs(package)))
    tags = own_tags(package)
    pages = [
        (layout, SourceDocument(html), data)
        for layout, html, data in example_pages(composition.registry, tags)
        if layout == "column"
    ]
    return tags, pages


def _press_each_control(browser, url, tags):
    """Press each control on the page with its gesture held, and return the names of
    those whose press sent one, and what went wrong."""
    page = browser.new_page(viewport=RENDER_VIEWPORT)
    arm_interception(page)
    sent, failures, held = [], [], []
    try:
        page.goto(url)
        wait_until_ready(page, served(page, url, "/api/state").json())
        rendered(page)
        # A press may replace the controls beside it, as Accept's Undo takes Reject's
        # seat, so the controls are read again after each, and each name pressed once.
        pressed_names = set()
        while names := [
            (index, name)
            for index, name in enumerate(page.evaluate(MARK_CONTROLS, tags))
            if name not in pressed_names
        ]:
            index, name = names[0]
            pressed_names.add(name)
            control = page.locator(f'[data-lf-press-check="{index}"]')
            control.scroll_into_view_if_needed()
            box = control.bounding_box()
            point = [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2]
            page.route("**/api/event", lambda route: held.append(route))
            before = page.evaluate(UNRESOLVED)
            face = page.evaluate(FACE_AT, point)
            page.mouse.click(*point)
            rendered(page)
            travelling = page.evaluate(FACE_AT, point)
            pressed = page.evaluate(UNRESOLVED)
            # A press that left no control under the pointer leaves nothing to flicker.
            if pressed != before and travelling:
                sent.append(name)
                if travelling != face:
                    failures.append(
                        f"{name}: {face} before the press, {travelling} while its "
                        "gesture travelled"
                    )
                # A control the press replaced, as Undo takes Accept's seat, is another
                # control, whose press may rightly send nothing.
                elif page.evaluate(STILL_PRESSED, [*point, index]):
                    page.mouse.click(*point)
                    rendered(page)
                    if page.evaluate(UNRESOLVED) == pressed:
                        failures.append(
                            f"{name}: a second press while the first travelled sent "
                            "nothing"
                        )
            # The preview server refuses every gesture, which restores the page for
            # the next control.
            for route in held:
                route.continue_()
            held.clear()
            page.unroute("**/api/event")
            page.wait_for_function(DELIVERED)
            rendered(page)
            page.keyboard.press("Escape")
    finally:
        page.close()
    return sent, failures


@pytest.mark.parametrize("package", PACKAGES, ids=lambda package: package.name)
def test_a_pressed_control_keeps_its_face_and_takes_the_next_press(browser, package):
    """While a press's gesture travels, the control under the pointer keeps the cursor
    and the available, idle face it had before the press, whatever it now says, and
    where the same control stands there, a second press sends again rather than being
    swallowed. A control whose press sends nothing, such as one opening a menu, makes
    no claim."""
    if package == schema_model.ASSETS:
        package = layer_model.ASSETS
    tags, pages = _example_pages(package)
    failures, reached = [], set()
    for _, url, _ in served_examples(package, pages):
        sent, found = _press_each_control(browser.unwatched, url, tags)
        reached.update(name.split("#")[0] for name in sent)
        failures += found
    assert REACHED & set(tags) <= reached
    assert not failures, "\n".join(failures)
