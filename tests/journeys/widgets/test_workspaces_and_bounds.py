"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.widgets.test_workspaces_and_bounds import (
    LONG_PANE,
    STREAMED_LOG_PAGE,
    clear_of_the_bottom_chrome,
)
from render_cases_interaction import live_url
from render_harness import (
    fills_the_window,
    leaf_page,
    open_page,
    pane_scroll_behavior,
    resized,
    scroll_settled,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_page_end_clears_the_bottom_chrome_around_a_workspace(browser, serve):
    """A document's end clears the panel's row with a pane inside it, by the end
    padding its Layout keeps; a workspace that flows ends as a document does, and a
    full-height one does not scroll.

    Where the workspace flows, a grid of panes ends the page with that padding below all
    its panes, so the page's end clears the panel whichever pane ends it."""
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
    # The body keeps no room for the panel; the column's own end padding clears it.
    assert (
        page.evaluate("parseFloat(getComputedStyle(document.body).paddingBottom)") == 0
    )
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
        end = clear_of_the_bottom_chrome(page, "#pane-end")
        assert end["clear"], (width, height, end)
    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#workspace-pane"), "bounded")


@pytest.mark.parametrize(
    "aim", ["u", "PageUp", "PageUp on a link", "wheel", "wheel across"]
)
@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_page_up_in_a_log_a_stream_feeds_leaves_its_end(engine, aim, request, serve):
    """u, PageUp or a wheel aimed up a log following its end takes the reader up while
    entries stream in, and a wheel across its long lines takes them across, at its end.
    u starts a glide whose first frame can leave the box where it stands, and a log
    follower that read only the box's offset would take the next entry for a reader
    still at the end, put the log back there and stop the glide, so the press would do
    nothing. The end keeper every box shares lets a box a glide heads back from go
    (dom/scrolling.js, `followEnd`). Firefox applies a wheel's or PageUp's scroll a frame or
    more after the input, and a keeper's write of the end meanwhile would cancel it, a
    wheel across as well; the scroll is the reader's from the input (dom/scrolling.js,
    `aimScroll`). PageUp on a link in the log, read as a key the link took, would be
    left to the keeper (dom/scrolling.js, `scrollsFor`). Each trial aims once in the middle
    of a stream of an entry every 4ms."""
    if aim != "u":
        # A browser starved of CPU can apply a key's or wheel's scroll after the 80ms
        # the reader's scroll waits for it to move the page (dom/arrivals.js), so the log
        # keeps its end in a trial: Firefox as late as 800ms after the input, and
        # Chromium in the starved macOS nightly. #6348 tracks a fix in the code or this
        # test that lets these marks go. `u` glides by Leaf's own scroll, which this
        # doesn't touch.
        request.applymarker(
            pytest.mark.xfail(
                strict=False,
                reason="#6348: a starved browser applies the scroll after the reader's wait ends",
            )
        )
    page = open_page(
        request.getfixturevalue(engine), live_url(serve(STREAMED_LOG_PAGE))
    )
    page.emulate_media(reduced_motion="no-preference")
    resized(page, 1280, 900)
    log = page.locator("#log")
    log.focus()
    box = log.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    stood = []
    for trial in range(6):
        log.evaluate(
            "log => log.scrollTo({top: log.scrollHeight, left: 0, behavior: 'instant'})"
        )
        scroll_settled(page, "#log")
        page.evaluate(
            """(trial) => { window.lfStream = new Promise((done) => {
              const log = document.getElementById('log');
              let n = 0;
              const tick = () => {
                log.append(Object.assign(document.createElement('p'),
                  {textContent: `Streamed ${trial}.${n}`}));
                if (++n < 60) setTimeout(tick, 4); else done();
              };
              tick();
            }); }""",
            trial,
        )
        page.wait_for_timeout(60)
        if aim == "PageUp on a link":
            page.evaluate(
                """() => { const link = Object.assign(document.createElement('a'),
                  {href: '#t', textContent: 'Aimed at'});
                  document.getElementById('log').append(link);
                  link.focus({preventScroll: true}); }"""
            )
            page.keyboard.press("PageUp")
        elif aim.startswith("wheel"):
            page.mouse.wheel(*((300, 0) if aim == "wheel across" else (0, -300)))
        else:
            page.keyboard.press(aim)
        page.evaluate("() => window.lfStream")
        scroll_settled(page, "#log")
        stood.append(
            log.evaluate(
                """log => ({short: log.scrollHeight - log.clientHeight - log.scrollTop,
                  across: log.scrollLeft})"""
            )
        )
    if aim == "wheel across":
        assert all(at["across"] > 0 and at["short"] <= 2 for at in stood), stood
    else:
        room = log.evaluate("log => log.clientHeight")
        assert all(at["short"] > room / 2 for at in stood), stood
