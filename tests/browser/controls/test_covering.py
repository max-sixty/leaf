"""The floating panel's views over the page: what they cover, a document replaced under
an open view, separate scrolling, and where selection stops."""

import pytest
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_cases_layout import ONE_OBLIGATION, toggle_queue
from render_harness import (
    LONG_PAGE,
    PANEL,
    PANEL_THREAD,
    SHELL_BOX,
    open_page,
    open_threads,
    panel_settled,
    panel_view,
    resized,
    select,
    stamp_page,
    told,
)

from browser.threads import open_panel_thread

pytestmark = pytest.mark.shifts_unsurveyed


# The box in an open view that scrolls what it holds, or null where it holds all of it.
VIEW_SCROLLER = """() => {
  const view = document.querySelector('.lf-fp-view:not([data-leaving])');
  return [view, ...view.querySelectorAll('*')].find((node) =>
    node.scrollHeight > node.clientHeight + 1
      && ['auto', 'scroll'].includes(getComputedStyle(node).overflowY)) ?? null;
}"""


def test_a_selection_that_reaches_the_layer_stops_at_the_page(browser, serve):
    """A drag out of a paragraph takes the passage, not the page and the panel with it.

    The layer is fixed and stands after the document in it, so one range crossing into
    anything selectable in the chrome runs through everything between. Three surfaces
    said user-select: none and the rest did not, so a drag that overshot the open thread
    panel's edge by five pixels took 14,472 characters instead of the 67 aimed at, and
    pressing `c` put the whole page — the passage, every widget under it, and the
    panel's own furniture — into the composer's quote and into the field's accessible
    name.

    The apparatus is answered at the layer's root now, so this asserts the statement
    rather than the surfaces: everything in here is unselectable except the words
    somebody said, which are a reply and the passage it is about, and those stay
    copyable.
    """
    # Anchored, so the thread carries both of the things a user may want out of the
    # panel: the passage it is about and the reply somebody wrote under it.
    url = serve(LONG_PAGE, anchored=[("p40", "Paragraph 40.")])
    page = open_page(browser, url)
    resized(page, 1200, 900)
    thread = page.evaluate(
        """async () => (await window.__lfWidgetApi()).readThreads().threads[0].id"""
    )
    open_panel_thread(page, thread)

    aim = page.evaluate(
        """() => {
          const view = document.querySelector('.lf-fp-view[data-view="thread"]')
            .getBoundingClientRect();
          const para = [...document.querySelectorAll('main p')].find((el) => {
            const r = el.getBoundingClientRect();
            return r.width > 200 && r.top > 40 && r.bottom < view.top - 40;
          });
          const r = para.getBoundingClientRect();
          return {start: [r.left + 40, r.top + 8],
                  end: [view.left + 40, view.top + 5],
                  main: document.querySelector('main').textContent,
                  whole: document.body.textContent.length};
        }"""
    )
    # Five pixels into the open view: the overshoot a user gives a drag they meant to end
    # at the foot of what they were reading.
    select(page, aim["start"], aim["end"])
    took = page.evaluate("() => getSelection().toString()")
    main = " ".join(aim["main"].split())
    assert took and all(
        " ".join(line.split()) in main for line in took.splitlines() if line.strip()
    ), (
        f"the drag took {len(took)} characters from outside the page, out of "
        f"{aim['whole']} in the document: {took[:80]!r}…{took[-80:]!r}"
    )

    # The statement, rather than the surfaces that happened to carry it: apparatus is
    # unselectable, and what a user may copy says so for itself. The drag began on the
    # page, a press there, which put the view away, so it opens again to be read.
    open_panel_thread(page, thread)
    open_layer = page.evaluate(
        """() => {
          const said = '.lf-quote, .lf-fp-quote, .lf-msg-body';
          return [...document.querySelector('.lf-chrome').querySelectorAll('*')]
            .filter((el) => getComputedStyle(el).webkitUserSelect !== 'none')
            .filter((el) => !el.closest(said))
            .map((el) => (el.className || el.tagName).toString().trim().split(/\\s+/)[0]);
        }"""
    )
    assert open_layer == [], (
        f"chrome surfaces outside a reply and its passage stayed selectable: {open_layer}"
    )
    copyable = page.evaluate(
        """(thread) => {
          const out = {};
          for (const [name, sel] of [
            ['quote', `${thread} .lf-fp-quote`],
            ['reply', `${thread} .lf-msg-body`],
          ]) {
            const range = document.createRange();
            range.selectNodeContents(document.querySelector(sel));
            const selection = getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            out[name] = selection.toString().trim().length;
            selection.removeAllRanges();
          }
          return out;
        }""",
        PANEL_THREAD,
    )
    assert copyable["quote"] and copyable["reply"], (
        f"the panel stopped a user copying the words somebody said: {copyable}"
    )


def test_an_open_view_stands_through_a_replaced_document(browser, serve):
    """A live version can update main under an open view without putting it away: the
    view and the user's place in it stand, and closing it shows the updated document."""
    source = LONG_PAGE.replace(
        '<h1 id="t">Long</h1>', f'<h1 id="t">Long</h1>{ONE_OBLIGATION}'
    )
    url = serve(source)
    page = open_page(browser, live_url(url))
    resized(page, 500, 640)
    toggle_queue(page)
    view = page.locator(panel_view("queue"))
    page.locator(".lf-fp-on-item").first.focus()

    revised = source.replace(
        '<h1 id="t">Long</h1>', '<h1 id="t">Long after replacement</h1>'
    )
    stamp_page(serve.page_dir, revised, "replace the document")
    told(page)
    expect(page.locator("#t")).to_have_text("Long after replacement")
    expect(page.locator(PANEL)).to_have_attribute("data-open", "queue")
    assert view.evaluate("view => view.contains(document.activeElement)"), (
        "the replaced document took the user out of the view they stood in"
    )

    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    expect(page.locator("#t")).to_be_in_viewport()


def test_page_and_panel_scroll_in_separate_regions(browser, serve):
    """The browser root scrolls the document and an open view keeps its own scrollport.

    Body is the page shell rather than a third scroll region. The panel stands over the
    page and takes no room from it, so the shell keeps the window's width while native
    document scrolling remains rooted in html."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    open_threads(page)
    expect(page.locator(".lf-fp-thread")).to_have_count(30)

    geom = page.evaluate(
        """() => {
        const body = document.body;
        const scroller = ("""
        + VIEW_SCROLLER
        + """)();
        return { rootIsScroller: document.scrollingElement === document.documentElement,
                 rootScrolls: document.scrollingElement.scrollHeight > document.scrollingElement.clientHeight,
                 bodyOverflow: getComputedStyle(body).overflowY,
                 viewScrolls: Boolean(scroller),
                 bodyRight: """
        + SHELL_BOX
        + """.right,
                 window: document.documentElement.clientWidth };
    }"""
    )

    assert geom["rootIsScroller"] and geom["rootScrolls"]
    assert geom["bodyOverflow"] == "visible", geom
    assert geom["viewScrolls"], "the open view did not establish its own scrollport"
    assert geom["bodyRight"] == pytest.approx(geom["window"], abs=1), (
        f"the page yielded room to the panel standing over it: {geom}"
    )


def test_a_wheel_over_an_open_view_scrolls_the_view_and_not_the_page(browser, serve):
    """On a phone the open view stands over most of the page; a wheel over its list moves
    the list and never the page behind it, and once the view is put away the wheel is
    the page's again."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    resized(page, 400, 600)

    # A reading position first, so surviving the view is observable.
    page.mouse.move(120, 200)
    page.mouse.wheel(0, 600)
    page.wait_for_function("() => document.scrollingElement.scrollTop > 0")
    before = page.evaluate("() => document.scrollingElement.scrollTop")

    open_threads(page)
    page.evaluate("() => { window.lfViewScroller = (" + VIEW_SCROLLER + ")(); }")
    assert page.evaluate("() => Boolean(window.lfViewScroller)"), (
        "the open view holds every thread, so nothing is proved"
    )
    row = page.locator(".lf-fp-thread").nth(2).bounding_box()
    page.mouse.move(row["x"] + row["width"] / 2, row["y"] + row["height"] / 2)
    page.mouse.wheel(0, 200)
    page.wait_for_function("() => window.lfViewScroller.scrollTop > 0")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before, (
        "the page scrolled behind the open view"
    )

    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    page.mouse.move(120, 200)
    page.mouse.wheel(0, 200)
    page.wait_for_function(f"() => document.scrollingElement.scrollTop > {before}")
