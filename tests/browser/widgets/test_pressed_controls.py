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
from leaf.render_checks import (
    RENDER_VIEWPORT,
    rendered,
    wait_for_probe,
    wait_until_ready,
)
from leaf.render_gate.scheme import served
from leaf.render_gate.widget_quality import (
    WRAPPERS,
    example_pages,
    own_tags,
    served_examples,
)
from leaf.structure import SourceDocument

# What a reader presses: a button, or a control that holds a choice.
CONTROL = (
    'button, [role="button"], [role="checkbox"], [role="radio"], [role="switch"], '
    '[role="option"], [role="tab"]'
)

# Every visible, enabled control inside an element the selector `within` matches, or in
# a margin entry Leaf draws for one, shadow trees included, each marked so the driver
# can press it with the pointer, and named by that element and its words.
MARK_CONTROLS = f"""(within) => {{
  const holderOf = (element) => {{
    for (let at = element; at; at = at.parentElement ?? at.getRootNode().host) {{
      if (within && at.matches(within)) return at;
      const entry = at.dataset?.lfMarginFor;
      if (entry) return holderOf(document.getElementById(entry));
    }}
    return null;
  }};
  const found = [];
  const walk = (root) => {{
    for (const element of root.querySelectorAll('*')) {{
      if (element.shadowRoot) walk(element.shadowRoot);
      delete element.dataset?.lfPressCheck;
      if (!element.matches({CONTROL!r})) continue;
      const holder = holderOf(element);
      if (!holder) continue;
      if (element.disabled || element.getAttribute('aria-disabled') === 'true') continue;
      if (!element.checkVisibility({{ visibilityProperty: true }})) continue;
      element.dataset.lfPressCheck = String(found.length);
      const words = element.getAttribute('aria-label') || element.textContent.trim();
      found.push(`${{holder.localName}}#${{holder.id}} ${{JSON.stringify(words)}}`);
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

# Whether the control at the point is the one marked, as the pointer reaches it before
# the press, and as a widget that relabels rather than replaces it keeps it there after.
UNDER_POINTER = f"""([x, y, index]) => {{
  {AT_POINT}
  return atPoint(x, y).control?.dataset.lfPressCheck === String(index);
}}"""

# The tab's unresolved gestures by attempt and kind, read through the check entry, and
# whether each records only what the user hasn't sent (`$state.attention`), as a
# playground's settings: a press that set them, pressed again while they stand, has
# nothing new to record.
UNRESOLVED = """async () => {
  const boot = new URL(document.querySelector('script[data-lf-entry]').dataset.lfEntry,
    location.href);
  const api = await import(new URL('runtime/check-api.js', boot));
  const { declarationFor } = await import(new URL('runtime/widget-api.js', boot));
  const unsent = (event) => event.kind === 'action' &&
    declarationFor(document.getElementById(event.widget), 'x-state')?.[event.action]
      ?.attention === false;
  return api.readApplication().unresolved.map(({ event }) =>
    [event.attempt, event.kind, unsent(event)]);
}"""

# Whether every send has its outcome, by the runtime's own traffic ledger
# (runtime/traffic.js).
DELIVERED = """() => {
  const traffic = document.documentElement.dataset.lfTraffic;
  return !traffic || !JSON.parse(traffic).pending.length;
}"""

# Controls no worked example shows, by package directory: a `multiple` group's Done.
STATES = {
    "default": """<lf-options id="pressed-many" choose multiple>
  <lf-option id="pressed-first"><strong>Cache the parsed config</strong></lf-option>
  <lf-option id="pressed-second"><strong>Parse it lazily</strong></lf-option>
</lf-options>""",
}

# The packages with widgets whose worked examples show no control to press, by
# directory, so a sweep that finds none anywhere else has lost its controls.
UNPRESSABLE = {"diagram", "file-tree", "motion", "visual-review"}

# The widgets whose presses once flickered, which the sweep must reach sending.
REACHED = {"lf-playground", "lf-options", "lf-suggestion"}


def _example_pages(package):
    composition = compose_layer(checked_layer_inputs(package_layer_inputs(package)))
    tags = own_tags(package)
    pages = [
        (layout, SourceDocument(html), data)
        for layout, html, data in example_pages(composition.registry, tags)
        if layout == "column"
    ]
    if state := STATES.get(package.name):
        opening, closing = WRAPPERS["column"]
        pages.append(
            (
                "column",
                SourceDocument(
                    "<!doctype html>\n<html lang='en'><head><title>States</title>"
                    f"</head><body>{opening}{state}{closing}</body></html>"
                ),
                {},
            )
        )
    return tags, pages


def open_served(browser, url):
    """The page a Leaf server serves at `url`, ready to be pressed."""
    page = browser.new_page(viewport=RENDER_VIEWPORT)
    page.goto(url)
    wait_until_ready(page, served(page, url, "/api/state").json())
    rendered(page)
    return page


def press_each_control(page, within, restore=None):
    """Press each control `MARK_CONTROLS` reads on the page within `within`, with its
    gesture held, and return the names pressed, the name and event kind of each
    gesture whose press was read, and what went wrong.

    The controls are read again after each press, and each name is pressed once, those
    a press revealed first: the Undo that takes Accept's seat, a palette's reactions,
    or the Resolve of a thread whose row was pressed. A control the pointer can't
    reach, under a surface or drawn for the keyboard alone, is passed over. Once none
    is left, Escape closes what the last press opened, as a reader leaves it, and
    `restore` brings back what a press took away, such as a thread's view; the sweep
    ends when that brings back nothing to press."""
    sent, failures, held = [], [], []
    pressed_names, unreachable, revealed, restored = set(), set(), {}, False
    while True:
        found = page.evaluate(MARK_CONTROLS, within)
        revealed = {shown: revealed.get(shown, len(pressed_names)) for shown in found}
        names = sorted(
            (
                (index, name)
                for index, name in enumerate(found)
                if name not in pressed_names | unreachable
            ),
            key=lambda item: -revealed[item[1]],
        )
        if not names:
            if restored:
                break
            page.keyboard.press("Escape")
            rendered(page)
            if restore:
                restore()
            restored = True
            unreachable.clear()
            continue
        index, name = names[0]
        # Playwright's own scroll would wait out a control that is leaving, and a
        # control that a press set moving, such as a view of the panel, is read where
        # it comes to rest.
        control = page.locator(f'[data-lf-press-check="{index}"]')
        control.evaluate("(control) => control.scrollIntoView({ block: 'nearest' })")
        wait_for_probe(page, "pageSettled")
        box = control.bounding_box() if control.count() else None
        point = box and [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2]
        if not point or not page.evaluate(UNDER_POINTER, [*point, index]):
            unreachable.add(name)
            continue
        pressed_names.add(name)
        restored = False
        page.route("**/api/event", lambda route: held.append(route))
        before = page.evaluate(UNRESOLVED)
        face = page.evaluate(FACE_AT, point)
        page.mouse.click(*point)
        rendered(page)
        travelling = page.evaluate(FACE_AT, point)
        pressed = page.evaluate(UNRESOLVED)
        # A press that left no control under the pointer leaves nothing to flicker.
        if pressed != before and travelling:
            new = [entry for entry in pressed if entry not in before]
            sent += [(name, kind) for _attempt, kind, _unsent in new]
            if travelling != face:
                failures.append(
                    f"{name}: {face} before the press, {travelling} while its "
                    "gesture travelled"
                )
            # A control the press replaced, as Undo takes Accept's seat, is another
            # control, whose press may rightly send nothing.
            elif not all(unsent for *_, unsent in new) and page.evaluate(
                UNDER_POINTER, [*point, index]
            ):
                page.mouse.click(*point)
                rendered(page)
                if page.evaluate(UNRESOLVED) == pressed:
                    failures.append(
                        f"{name}: a second press while the first travelled sent nothing"
                    )
        # A read-only server refuses every gesture, which restores the page; a page
        # that admits them moves on, and its new controls are read above.
        for route in held:
            route.continue_()
        held.clear()
        page.unroute("**/api/event")
        page.wait_for_function(DELIVERED)
        rendered(page)
    return pressed_names, sent, failures


@pytest.mark.parametrize("package", PACKAGES, ids=lambda package: package.name)
def test_a_pressed_control_keeps_its_face_and_takes_the_next_press(browser, package):
    """While a press's gesture travels, the control under the pointer keeps the cursor
    and the available, idle face it had before the press, whatever it now says, and
    where the same control stands there, a second press does what it then says rather
    than being swallowed. A control whose press sends nothing, such as one opening a
    menu, makes no claim."""
    if package == schema_model.ASSETS:
        package = layer_model.ASSETS
    tags, pages = _example_pages(package)
    failures, pressed, reached = [], set(), set()
    for _, url, _ in served_examples(package, pages):
        page = open_served(browser.unwatched, url)
        names, sent, found = press_each_control(page, ", ".join(tags))
        pressed |= names
        reached.update(name.split("#")[0] for name, _ in sent)
        failures += found
    assert bool(pressed) != (not tags or package.name in UNPRESSABLE), sorted(pressed)
    assert REACHED & set(tags) <= reached
    assert not failures, "\n".join(failures)
