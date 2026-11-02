"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.widgets.test_pressed_controls import (
    REACHED,
    UNPRESSABLE,
    _example_pages,
    open_served,
    press_each_control,
)
from known_widget_findings import PACKAGES

from leaf import layer as layer_model
from leaf import schema as schema_model
from leaf.render_gate.widget_quality import (
    served_examples,
)


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
