"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.drafts import choose_comment_target
from browser.drafts.test_reading_place import (
    GROW_ABOVE_AND_SCROLL,
    READ_HEADING,
    reading_section_page,
)
from browser.threads import SEAT_DIFF, SEAT_FILLER
from playwright.sync_api import expect
from render_harness import leaf_page, open_page, resized, scroll_settled

from leaf.records import page_data as page_data_model
from leaf.source.render_checks import one_frame
from leaf_dev.rings import current_location_ring, ring_faults

pytestmark = pytest.mark.shifts_unsurveyed


def assert_keyboard_focus(page, control):
    """The focused destination declares a visible treatment, stands whole in the
    window, is not covered, and wears an uncut keyboard ring.

    A text field always shows its focus, as a textarea does. Chrome never gives a host
    that delegates focus `:focus-visible`, so the field's treatment keys on `:focus`,
    and that is the state asked of it here. The hit is read in the control's own tree,
    since the document retargets a hit inside a widget's shadow tree to its host."""
    expect(control).to_be_focused()
    focus = control.evaluate(
        """node => {
          const box = node.getBoundingClientRect();
          const hit = node.getRootNode().elementFromPoint(
            box.left + box.width / 2, box.top + box.height / 2);
          const shown = node.localName === 'leaf-text' ? ':focus' : ':focus-visible';
          return {
            focusVisible: node.matches(shown),
            unobscured: Boolean(hit && (hit === node || node.contains(hit))),
            inViewport: box.top >= 0 && box.left >= 0
              && box.bottom <= innerHeight && box.right <= innerWidth,
          };
        }"""
    )
    assert focus == {
        "focusVisible": True,
        "unobscured": True,
        "inViewport": True,
    }, f"the keyboard destination has no visible, reachable focus treatment: {focus}"
    ring = current_location_ring(page)
    assert ring, "the focused destination paints no keyboard ring"
    assert not (faults := ring_faults([ring], "the focused destination")), "\n".join(
        faults
    )


@pytest.mark.parametrize("height", [600, 760])
def test_a_comment_editor_seated_in_a_widget_stays_in_view_as_the_window_changes(
    browser, serve, height
):
    """A focused comment editor that a widget seats in its own outlet, here beside a
    diff's file row, stays whole in view with its caret as narrowing the window reflows
    the page above it, while the reader hasn't scrolled. Once the reader scrolls it
    away, the next reflow keeps their scroll rather than pulling the editor back."""
    url = serve(
        leaf_page(
            "diff",
            f'<h1 id="title">Review</h1>{SEAT_FILLER}<lf-diff id="patch" '
            f'source="review-patch"></lf-diff>{SEAT_FILLER}',
        )
    )
    page_data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        {"files": [{"path": "app.py", "patch": SEAT_DIFF}]},
    )
    page = open_page(browser, url)
    resized(page, 1366, 768)
    choose_comment_target(page, 'lf-diff [data-lf-datum=\'["app.py","file"]\']')
    seated = page.locator("lf-diff .lf-diff-file-thread-outlet .lf-fab-input")
    field = page.locator(".lf-fab-input")
    expect(seated).to_be_focused()
    page.keyboard.type("Keep the destinations together")
    page.keyboard.press("Shift+ArrowLeft")
    caret = field.evaluate("node => [node.selectionStart, node.selectionEnd]")
    assert_keyboard_focus(page, field)

    # Narrowing rewraps the screens of reading above the diff, which would carry the
    # editor far below the window at the old offset; the reader has not scrolled.
    resized(page, 390, height)
    expect(field).to_have_js_property("value", "Keep the destinations together")
    assert field.evaluate("node => [node.selectionStart, node.selectionEnd]") == caret
    assert_keyboard_focus(page, field)
    expect(seated).to_be_focused()

    # Native scrolling can leave the same editor focused. The next reflow must
    # keep that newer reading instead of pulling the draft back into view.
    page.mouse.wheel(0, -10000)
    page.wait_for_function("document.scrollingElement.scrollTop === 0")
    scroll_settled(page)
    expect(field).to_be_focused()
    assert field.evaluate("node => node.getBoundingClientRect().top > innerHeight")
    resized(page, 420, height)
    assert page.evaluate("document.scrollingElement.scrollTop") == 0
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "Keep the destinations together")


def test_a_page_that_never_settles_lets_the_held_place_go_after_a_while(browser, serve):
    """A chart whose box breathes forever keeps the page's rendering from ever reading
    settled. A width change restores the reader's place and holds it while the layout
    settles, but no longer than a moment: well after, a script that scrolls as content
    grows above the reader moved the page, and the next width change starts from
    there rather than putting the held place back."""
    source = reading_section_page(
        "A page that never settles",
        "<style>@keyframes breathe { from { width: 60%; } to { width: 100%; } }"
        " .breathe #breathing { animation: breathe 3s linear infinite alternate; }"
        "</style>"
        '<div id="breathing"><lf-chart id="spin" data-height="120"><pre>\n'
        '{ ariaLabel: "Two teams", marks: [Plot.barY([{team: "a", n: 12},'
        ' {team: "b", n: 19}], {x: "team", y: "n"})] }\n</pre></lf-chart></div>',
    )
    page = open_page(browser, serve(source))
    page.evaluate("document.documentElement.classList.add('breathe')")

    def settle():
        # The page never reads settled, so wait out its scrolls and a few frames.
        scroll_settled(page)
        page.wait_for_timeout(300)
        one_frame(page)

    resized(page, 390, 800)
    settle()
    page.evaluate("location.hash = 'read'")
    settle()
    box = page.locator("#read p").first.bounding_box()
    page.mouse.move(box["x"] + 20, box["y"] + 5)
    page.mouse.wheel(0, 8)
    settle()
    resized(page, 1200, 800)
    settle()
    held = page.evaluate(READ_HEADING)
    page.wait_for_timeout(1500)
    page.evaluate(GROW_ABOVE_AND_SCROLL)
    settle()
    assert page.evaluate(READ_HEADING) < held - 300, "the script's scroll was undone"
    resized(page, 390, 800)
    settle()
    assert page.evaluate(READ_HEADING) < held - 300, "the held place came back"
