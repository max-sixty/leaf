"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.controls.test_focus import EDGE_TARGETS, edges_page
from playwright.sync_api import expect
from render_cases_layout import WIDE_DIFF_PAGE
from render_cases_navigation import DIFF_PAGE
from render_harness import open_page, resized, scroll_settled

from leaf.source.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


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


@pytest.mark.parametrize(
    ("control", "past", "key", "engine"),
    [
        *(
            pytest.param(
                control, past, key, engine, id=f"{control}-{name}-{key}-{engine}"
            )
            for control, past, name, key in [
                ("radio", 6, "past", "Tab"),
                ("radio", -2, "inside", "Tab"),
                ("options", 6, "past", "Tab"),
                ("options", 6, "past", "End"),
                ("filter", 3, "past", "Tab"),
                ("table", 6, "past", "Tab"),
            ]
            for engine in ["browser", "firefox_browser"]
        ),
        # Firefox logs a warning of its own on any playground page.
        pytest.param(
            "playground", 6, "Tab", "browser", id="playground-past-Tab-browser"
        ),
    ],
)
def test_a_key_onto_a_control_at_a_scrollers_edge_shows_its_ring(
    request, serve, control, past, key, engine
):
    """The browser reveals a Tab's arrival only when it counts it out of view, Firefox
    when less than about a line of it shows and Chromium across only when none of it
    does, and neither it nor Leaf's landing knew a box that wears the control's ring.
    So a radio 6px past a bounded log's foot stayed cut in Firefox, and one 2px inside
    it kept its ring cut; a link 6px past a wide table's end stayed cut in both
    engines; and a joined option group's row and a playground choice's face, each
    wearing its control's ring, stayed cut in both, the face once its radio stood 7px
    inside, the row whether Tab or End reached it; and a diff's file filter, holding
    focus in its own shadow tree, stayed cut in both and under the log's fade. `past` is
    how far beyond the edge the box wearing the ring stood before the key; each now
    shows its ring, unfaded."""
    page = open_page(request.getfixturevalue(engine), serve(edges_page(control)))
    # Tall enough that the log's foot stands clear of the floating panel, so the stop the
    # key leaves is where the user is, rather than a stop the key would let go of.
    resized(page, 1280, 720)
    side = "right" if control == "table" else "bottom"
    target = page.locator(EDGE_TARGETS[control])
    # Which box wears the ring is the paint's answer: the nearest box out from the
    # control whose outline is the ring.
    target.focus()
    rendered(page)
    target.evaluate(
        """(el) => {
          const w = getComputedStyle(el).getPropertyValue('--lf-focus-ring-w').trim();
          for (let n = el; n; n = n.parentElement ?? n.getRootNode().host) {
            const cs = getComputedStyle(n);
            if (cs.outlineStyle === 'solid' && cs.outlineWidth === w)
              return void (window.ringed = n);
          }
        }"""
    )
    if key == "Tab":
        page.keyboard.press("Shift+Tab")
    else:
        page.locator("#op-a .lf-pick").focus()
    page.evaluate(
        """([side, past]) => {
          const box = document.querySelector(side === 'bottom' ? '#log' : '#wide');
          const port = box.getBoundingClientRect();
          const at = window.ringed.getBoundingClientRect();
          if (side === 'bottom')
            box.scrollTop += at.bottom - (port.top + box.clientTop + box.clientHeight)
              - past;
          else
            box.scrollLeft += at.right - (port.left + box.clientLeft + box.clientWidth)
              - past;
        }""",
        [side, past],
    )
    scroll_settled(page)
    page.keyboard.press(key)
    expect(target).to_be_focused()
    rendered(page)
    read = page.evaluate(
        """(side) => {
          const el = window.ringed;
          const box = document.querySelector(side === 'bottom' ? '#log' : '#wide');
          const port = box.getBoundingClientRect();
          const at = el.getBoundingClientRect();
          const style = getComputedStyle(el);
          return {
            room: side === 'bottom'
              ? port.top + box.clientTop + box.clientHeight - at.bottom
              : port.left + box.clientLeft + box.clientWidth - at.right,
            ring: parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset),
            fade: getComputedStyle(box).maskImage,
          };
        }""",
        side,
    )
    assert read["room"] >= read["ring"], read
    assert read["fade"] == "none", read
