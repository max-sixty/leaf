"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.widgets.test_workspaces_and_bounds import (
    LONG_PANE,
    clear_of_the_bottom_chrome,
    foot_reserve,
)
from render_harness import (
    fills_the_window,
    leaf_page,
    open_page,
    pane_scroll_behavior,
    resized,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_page_end_clears_the_bottom_chrome_around_a_workspace(browser, serve):
    """A document keeps its end room with a pane inside it; a workspace that flows gives
    its last block that room, and a full-height one does not scroll.

    Where the workspace flows, a grid of panes ends the page with the room below all its
    panes, so the page's end clears the panel whichever pane ends it, and no pane keeps
    the panel's row as an empty band of its own. Held, each pane's body scrolls to the
    window's foot, and each keeps the room."""
    document = leaf_page(
        "a pane mid-document",
        f"""
<h1>A document with a pane</h1>
<p>Before the pane.</p>
{LONG_PANE}
{"<p>After the pane.</p>" * 30}
<p id="document-end">The document's last line.</p>
""",
    )
    page = open_page(browser, serve(document))
    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#workspace-pane"), "flow")
    room = page.evaluate(
        """() => {
          const probe = document.createElement('div');
          probe.style.cssText = 'position:fixed;visibility:hidden;height:var(--lf-foot-room)';
          document.body.append(probe);
          const band = probe.getBoundingClientRect().height;
          probe.remove();
          return {
            padding: parseFloat(getComputedStyle(document.body).paddingBottom),
            band,
            panel: innerHeight
              - document.querySelector('.lf-fp-row').getBoundingClientRect().top,
          };
        }"""
    )
    # The page's end room is the band's stated height, which holds the panel's row.
    assert room["padding"] == room["band"] >= room["panel"] > 0, room
    end = clear_of_the_bottom_chrome(page, "#document-end")
    assert end["clear"], end
    page.close()

    root = leaf_page("a workspace", LONG_PANE, layout="workspace")
    page = open_page(browser, serve(root))
    resized(page, 1280, 420)
    pane_scroll_behavior(page, page.locator("#workspace-pane"), "flow")
    end = clear_of_the_bottom_chrome(page, "#pane-end")
    assert end["clear"], end

    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#workspace-pane"), "bounded")
    fills_the_window(page, page.locator("main"), True)
    page.close()

    # Two columns at every width, the long pane first, so it ends the page on a phone.
    grid = leaf_page(
        "a workspace grid of panes",
        f"""<div id="cells">
  {LONG_PANE}
  <lf-pane id="second-pane" label="Second"><div><p>Second</p></div></lf-pane>
</div>""",
        head="<style>#cells { display: grid; grid-template-columns: 1fr 1fr; }</style>",
        layout="workspace",
    )
    page = open_page(browser, serve(grid))
    for width, height in [(390, 844), (844, 390)]:
        resized(page, width, height)
        pane_scroll_behavior(page, page.locator("#workspace-pane"), "flow")
        assert foot_reserve(page) == 0, (width, height)
        assert foot_reserve(page, "#second-pane") == 0, (width, height)
        end = clear_of_the_bottom_chrome(page, "#pane-end")
        assert end["clear"], (width, height, end)
    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#workspace-pane"), "bounded")
    assert foot_reserve(page) > 0
    assert foot_reserve(page, "#second-pane") > 0
