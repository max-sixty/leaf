"""Where a script's scroll write through `setScroll` lands: it moves a box as far as the
browser lets it, on whichever side of zero the box scrolls, and writes nothing that would
leave a still box where it stands (`runtime/arrivals.js`)."""

import pytest
from render_harness import consume_browser_errors, leaf_page, open_page

# Each style that decides which side of zero a box scrolls on, alone and in the
# combinations where two of them cancel. Chromium and Firefox agree on every one.
ORIGINS = {
    "plain": "",
    "rtl": "direction: rtl;",
    "row-reverse": "display: flex; flex-direction: row-reverse;",
    "row-reverse-rtl": "display: flex; flex-direction: row-reverse; direction: rtl;",
    "column-reverse": "display: flex; flex-direction: column-reverse;",
    "inline-column-reverse": "display: inline-flex; flex-direction: column-reverse;",
    "wrap-reverse": "display: flex; flex-wrap: wrap-reverse;",
    "column-wrap-reverse": "display: flex; flex-flow: column wrap-reverse;",
    "grid": "display: grid;",
    "vertical-rl": "writing-mode: vertical-rl;",
    "vertical-lr": "writing-mode: vertical-lr;",
    "vertical-rl-rtl": "writing-mode: vertical-rl; direction: rtl;",
    "vertical-lr-rtl": "writing-mode: vertical-lr; direction: rtl;",
    "sideways-lr": "writing-mode: sideways-lr;",
    "sideways-rl": "writing-mode: sideways-rl;",
}

# For each box the selector names, where `setScroll` put it from zero against where the
# browser's own range, read by this test's writes, lets a write past each side go.
MISPLACED = """async (selector) => {
  const {setScroll} = await window.__lfWidgetApi();
  const result = {};
  for (const box of document.querySelectorAll(selector)) {
    const name = box.id || box.localName;
    for (const axis of ['top', 'left']) {
      const key = axis === 'top' ? 'scrollTop' : 'scrollLeft';
      box.scrollTo({[axis]: -1e6, behavior: 'instant'});
      const low = box[key];
      box.scrollTo({[axis]: 1e6, behavior: 'instant'});
      const high = box[key];
      for (const to of [-50, 50]) {
        box.scrollTo({[axis]: 0, behavior: 'instant'});
        setScroll(box, {[axis]: to});
        const expected = Math.min(Math.max(to, low), high);
        if (box[key] !== expected)
          result[`${name} ${axis} ${to}`] = {landed: box[key], expected};
      }
    }
  }
  return result;
}"""


def test_a_write_from_zero_moves_a_box_as_far_as_the_browser_lets_it(browser, serve):
    """From rest at zero, a write past either side moves a box to the edge its range
    reaches on that side, or writes nothing where that side is the one it stands at. A
    box scrolls on the negative side where its content flows from the bottom or right
    edge, which nothing but its style shows while it stands at zero: a reversed flex
    column's first move up was dropped as a write past its top, and a plain box's move
    past its top was written though it moved nothing. The write watch fails any write
    that moves nothing (`write_watch.js`)."""
    boxes = "".join(
        f'<div class="origin" id="{name}" '
        f'style="width:200px;height:200px;overflow:auto;{style}">'
        '<div style="width:600px;height:600px;flex:none"></div>'
        '<div style="width:600px;height:600px;flex:none"></div></div>'
        for name, style in ORIGINS.items()
    )
    page = open_page(browser, serve(leaf_page("Scroll origins", boxes)))
    assert page.evaluate(MISPLACED, ".origin") == {}


@pytest.mark.parametrize(
    ("style", "open_axes"),
    [
        ("html { display: flex; flex-direction: column-reverse; }", 0),
        ("body { writing-mode: vertical-rl; }", 1),
    ],
    ids=["root-column-reverse", "body-vertical-rl"],
)
def test_the_page_scrolls_from_the_start_of_its_principal_flow(
    browser, serve, style, open_axes
):
    """The page's own scroll starts where its principal flow does, which no flex flow on
    the root reverses. That flow is the root's or the body's, by rules that turn on
    containment and on which the engines differ, so where the two disagree a write from
    zero is judged against both sides: it is never dropped, and the one past the side
    the page doesn't scroll on moves nothing, as the write watch reports."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Page origin",
                '<div style="width:4000px;height:4000px"></div>',
                head=f"<style>{style}</style>",
            )
        ),
    )
    assert page.evaluate(MISPLACED, "html") == {}
    if open_axes:
        unmoved = consume_browser_errors(page, {"code": "unmoved-scroll"})
        assert len(unmoved) == open_axes, unmoved
