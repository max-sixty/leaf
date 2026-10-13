"""Observe authored pages without treating an unvisited state as absent content.

Arrival screens preserve the composition a reader meets. Supplemental observations
use ordinary controls (disclosures, tabs, selects and declared task destinations)
and scroll the regions the browser actually makes scrollable. Each screenshot
retains its action, accessibility reading and scroll geometry. Limits and failed
operations are evidence gaps, never a verdict about the authored page.

The caller owns a disposable copy of the page and its server. Observing a Leaf page
can append events, so immutable authoring artifacts must never be served directly.
"""

import hashlib
import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path

from playwright.sync_api import Error as BrowserError
from playwright.sync_api import Page

from leaf_dev.eval_user import OPEN, reveal

# Evidence collection is finite. Reaching a limit is recorded, rather than being
# silently presented to the judge as a complete reading of a long page.
MAX_SCREENS = 16
MAX_ACTIONS = 24
MAX_CAPTURES = 64
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

READING = """() => {
  const rect = el => {
    const r = el.getBoundingClientRect();
    return {x:r.x, y:r.y, width:r.width, height:r.height};
  };
  const drawn = el => el.checkVisibility({visibilityProperty:true, opacityProperty:true});
  const identity = el => ({tag:el.localName, id:el.id || null,
    role:el.getAttribute('role'), label:el.getAttribute('aria-label')
      || el.getAttribute('title') || (el.innerText || '').slice(0,160), rect:rect(el)});
  const scrollers = [...document.querySelectorAll('body *')].filter(el => {
    if (!drawn(el) || !el.clientWidth || !el.clientHeight) return false;
    const css = getComputedStyle(el);
    return (el.scrollWidth > el.clientWidth + 1 && /auto|scroll/.test(css.overflowX))
      || (el.scrollHeight > el.clientHeight + 1 && /auto|scroll/.test(css.overflowY));
  }).map(el => ({...identity(el), left:el.scrollLeft, top:el.scrollTop,
    width:el.clientWidth, height:el.clientHeight,
    scrollWidth:el.scrollWidth, scrollHeight:el.scrollHeight}));
  const clipped = [...document.querySelectorAll('body *')].filter(el => {
    if (!drawn(el) || !el.clientWidth || !el.clientHeight) return false;
    const css = getComputedStyle(el);
    return (el.scrollWidth > el.clientWidth + 1 && /hidden|clip/.test(css.overflowX))
      || (el.scrollHeight > el.clientHeight + 1 && /hidden|clip/.test(css.overflowY));
  }).map(identity);
  return {document:{left:scrollX,top:scrollY,width:innerWidth,height:innerHeight,
    scrollWidth:document.documentElement.scrollWidth,
    scrollHeight:document.documentElement.scrollHeight},scrollers,clipped,
    note:'Geometry and accessibility describe this state. Offscreen or clipped accessibility text does not establish visual readability.'};
}"""

SCROLLERS = """() => [...document.querySelectorAll('body *')].filter(el => {
  if (!el.checkVisibility({visibilityProperty:true}) || !el.clientWidth || !el.clientHeight) return false;
  const css = getComputedStyle(el);
  return (el.scrollWidth > el.clientWidth + 1 && /auto|scroll/.test(css.overflowX))
    || (el.scrollHeight > el.clientHeight + 1 && /auto|scroll/.test(css.overflowY));
})"""


def observe(
    page: Page,
    directory: Path,
    prefix: str,
    settled: Callable[[Page], None],
    *,
    destinations: Iterable[str] = (),
) -> dict:
    """Capture arrival and ordinary inspection states in one existing fresh tab.

    `destinations` names request items, independent of the author's selectors.
    A route is attempted through the page's own labeled controls. Its return value
    is recorded without claiming that a matched word proves the destination works.
    """
    directory.mkdir(parents=True, exist_ok=True)
    states, limitations, captures, restorations = [], [], [], []
    image_by_hash = {}
    actions = 0

    def capture(label: str, action: dict) -> bool:
        if len(captures) >= MAX_CAPTURES:
            if "Screenshot budget exhausted" not in limitations:
                limitations.append("Screenshot budget exhausted")
            return False
        settled(page)
        pixels = page.screenshot()
        checksum = hashlib.sha256(pixels).hexdigest()
        image = image_by_hash.get(checksum)
        if image is None:
            image = directory / f"{prefix}-{len(captures)}.png"
            image.write_bytes(pixels)
            image_by_hash[checksum] = image
            captures.append(str(image))
        reading = page.evaluate(READING)
        reading["accessibility"] = page.locator("body").aria_snapshot()
        states.append(
            {
                "id": f"{prefix}-state-{len(states)}",
                "label": label,
                "origin": "authored_arrival"
                if action["type"] == "arrival"
                else "inspection",
                "action": action,
                "images": [str(image)],
                "reading": reading,
            }
        )
        return True

    def document_screens(label: str, action: dict) -> None:
        page.evaluate("window.scrollTo({top:0,left:0,behavior:'instant'})")
        settled(page)
        height, viewport = page.evaluate(
            "[document.documentElement.scrollHeight, innerHeight]"
        )
        step = int(viewport * 0.85)
        count = 1 + max(0, height - viewport + step - 1) // step
        if count > MAX_SCREENS:
            limitations.append(
                f"{label}: document has {count} screens; captured {MAX_SCREENS}"
            )
        for index in range(min(count, MAX_SCREENS)):
            page.evaluate(
                "y => window.scrollTo({top:y,behavior:'instant'})", index * step
            )
            if not capture(label, {**action, "document_screen": index}):
                break

    def operate(label: str, action: dict, operation: Callable[[], None]) -> bool:
        nonlocal actions
        if actions >= MAX_ACTIONS or len(captures) >= MAX_CAPTURES:
            limitations.append(f"Inspection budget prevented: {label}")
            return False
        actions += 1
        before = page.evaluate(READING)
        try:
            operation()
            settled(page)
        except BrowserError as error:
            limitations.append(
                f"{label}: {type(error).__name__}: {str(error).splitlines()[0]}"
            )
            # A failed click is not evidence of an authored defect: it might be a
            # collector error. Retain the state it left for an independent reading.
            capture(label, {**action, "outcome": "operation_failed", "before": before})
            return False
        capture(label, {**action, "outcome": "operation_completed", "before": before})
        return True

    def region_screens(region, label, action):
        bounds = region.bounding_box()
        if bounds is None:
            return
        top = page.evaluate("scrollY") + bounds["y"]
        viewport = page.viewport_size["height"]
        step = int(viewport * 0.85)
        count = 1 + max(0, int(bounds["height"]) - viewport + step - 1) // step
        if count > MAX_SCREENS:
            limitations.append(
                f"{label}: revealed region exceeds {MAX_SCREENS} screens"
            )
        for index in range(min(count, MAX_SCREENS)):
            page.evaluate(
                "y => window.scrollTo({top:y,behavior:'instant'})", top + index * step
            )
            if not capture(label, {**action, "region_screen": index}):
                break

    def restore(label, operation):
        # Cleanup is not exploration: it must still run after the observation
        # budget ends, or later probes inherit the collector's choices.
        try:
            operation()
            settled(page)
            restorations.append({"label": label, "outcome": "completed"})
        except BrowserError as error:
            limitations.append(f"{label}: {str(error).splitlines()[0]}")
            restorations.append({"label": label, "outcome": "failed"})

    document_screens("Arrival", {"type": "arrival"})
    for target in destinations:
        route = {}

        def destination(target=target, route=route):
            route["result"] = reveal(page, target, re.escape(target), settled)

        if operate(
            f"Inspect {target}",
            {"type": "destination", "target": target},
            destination,
        ):
            states[-1]["action"]["collector_route_result"] = route["result"]
            # A task destination may reveal a long panel without aria-controls.
            # Its below-fold evidence belongs to this state, not a later item.
            document_screens(
                f"After inspecting {target}",
                {"type": "destination", "target": target},
            )

    # These native semantics mean inspection rather than an application decision.
    # Read locators afresh after each input; custom elements may replace controls.
    inspected = set()
    pressed_before = [
        (control, control.get_attribute("aria-pressed"))
        for control in page.locator("button[aria-pressed]").all()
    ]
    while actions < MAX_ACTIONS and len(captures) < MAX_CAPTURES:
        found = None
        for selector in ("details > summary", '[role="tab"]', "button[aria-pressed]"):
            for index, control in enumerate(page.locator(selector).all()):
                if not control.is_visible():
                    continue
                label = control.inner_text().strip()
                key = (selector, index, label)
                if key in inspected:
                    continue
                inspected.add(key)
                if (
                    control.evaluate(OPEN)
                    or control.get_attribute("aria-pressed") == "true"
                ):
                    continue
                found = (control, label, selector)
                break
            if found:
                break
        if found is None:
            break
        control, label, selector = found
        if operate(
            f"Open {label}",
            {"type": "click", "label": label},
            lambda control=control: control.click(timeout=2000),
        ):
            action = {"type": "click", "label": label}
            if selector == "details > summary":
                region_screens(control.locator(".."), f"After opening {label}", action)
            for identity in (control.get_attribute("aria-controls") or "").split():
                region = page.locator(f"[id={json.dumps(identity)}]")
                if region.count() == 1 and region.is_visible():
                    region_screens(region, f"After opening {label}", action)
    else:
        limitations.append(
            "Disclosure/tab exploration stopped at the inspection budget"
        )
    for control, pressed in pressed_before:
        if control.is_visible() and control.get_attribute("aria-pressed") != pressed:
            restore(
                "Restore original pressed state",
                lambda control=control: control.click(timeout=2000),
            )

    # A selector's options can alter the evidence itself, as threshold choices do.
    # Each sample is disposable; preserving its original chosen value keeps later
    # controls from inheriting a collector's setting.
    for select in page.locator("select").all():
        if not select.is_visible() or not select.is_enabled():
            continue
        original = select.input_value()
        label = (
            select.get_attribute("aria-label") or select.get_attribute("id") or "select"
        )
        for option in select.locator("option").all():
            value = option.evaluate("el => el.value")
            if value == original or option.is_disabled():
                continue
            if not operate(
                f"Set {label} to {option.inner_text()}",
                {"type": "select", "label": label, "value": value},
                lambda value=value, select=select: select.select_option(
                    value, timeout=2000
                ),
            ):
                break
        restore(
            f"Restore {label}",
            lambda select=select, original=original: select.select_option(
                original, timeout=2000
            ),
        )

    radios = page.locator('input[type="radio"], [role="radio"]').all()
    chosen_before = [
        control
        for control in radios
        if control.evaluate(
            "el => el.checked === true || el.getAttribute('aria-checked') === 'true'"
        )
    ]
    for control in radios:
        if not control.is_visible() or not control.is_enabled():
            continue
        label = control.aria_snapshot()
        operate(
            f"Choose {label}",
            {"type": "choice", "label": label},
            lambda control=control: control.click(timeout=2000),
        )
    for control in chosen_before:
        if control.is_visible():
            restore(
                "Restore original radio choice",
                lambda control=control: control.click(timeout=2000),
            )

    # Scroll real scroll owners. Hidden overflow is recorded above and never
    # scrolled by script: doing so invents a route the user does not have.
    for handle in page.evaluate_handle(SCROLLERS).get_properties().values():
        owner = handle.as_element()
        if owner is None:
            continue
        geometry = owner.evaluate(
            "el => ({x:el.scrollWidth-el.clientWidth,y:el.scrollHeight-el.clientHeight,"
            "width:el.clientWidth,height:el.clientHeight,label:el.id||el.localName})"
        )
        for axis in ("x", "y"):
            maximum = geometry[axis]
            if maximum <= 1:
                continue

            step = max(1, int(geometry["width" if axis == "x" else "height"] * 0.85))
            count = (maximum + step - 1) // step
            if count > MAX_SCREENS:
                limitations.append(
                    f"{geometry['label']}: internal {axis} scroll exceeds {MAX_SCREENS} screens"
                )
            for number in range(1, min(count, MAX_SCREENS) + 1):
                target = min(maximum, number * step)

                def scroll(owner=owner, axis=axis, target=target):
                    owner.scroll_into_view_if_needed(timeout=2000)
                    current = owner.evaluate(
                        "(el,axis) => axis === 'x' ? el.scrollLeft : el.scrollTop", axis
                    )
                    delta = target - current
                    bounds = owner.bounding_box()
                    if bounds:
                        page.mouse.move(
                            bounds["x"] + min(bounds["width"] / 2, 20),
                            bounds["y"] + min(bounds["height"] / 2, 20),
                        )
                        page.mouse.wheel(
                            delta if axis == "x" else 0, delta if axis == "y" else 0
                        )
                        page.wait_for_function(
                            "([el,axis,end]) => Math.abs((axis === 'x' ? el.scrollLeft : el.scrollTop) - end) <= 1",
                            arg=[owner, axis, target],
                            timeout=2000,
                        )

                if not operate(
                    f"Scroll {geometry['label']} on {axis} to {target}",
                    {
                        "type": "wheel",
                        "owner": geometry["label"],
                        "axis": axis,
                        "requested_position": target,
                    },
                    scroll,
                ):
                    break

    return {
        "collector": {
            "source": "dev/leaf_dev/authoring_observation.py",
            "sha256": SOURCE_SHA256,
        },
        "viewport": list(page.viewport_size.values()),
        "states": states,
        "limitations": limitations,
        "captures": captures,
        "restorations": restorations,
    }
