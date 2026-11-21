"""A header the page fixes at the window's top. Leaf doesn't look for it: the page states
its room as its targets' `scroll-margin-top` (page-layout.md), and a pin on the
header's own words stands in the header, which stands still in the window
(margin-layout.js, `stillBox`)."""

import pytest
from render_harness import leaf_page, margins_laid_out, open_page, resized

from browser.margin import _comment_on
from leaf_dev.browser import scroll_settled


def _filler(start, count):
    return "".join(
        f"<p>Filler paragraph {i} keeps the page long enough to scroll through several"
        " screens of prose.</p>"
        for i in range(start, start + count)
    )


HEAD = (
    '<header id="site-head"><p id="head-words">Quarterly operations brief from the'
    ' platform team</p><nav><a id="to-risks" href="#risks">Risks</a></nav></header>'
)
# A site header fixed at the window's top, in a box of its own in `body` beside `main`,
# on a page that states its landing room for it as its targets' `scroll-margin-top`.
ROOM = 100
STYLE = (
    "<style>#site-head { position: fixed; inset-inline: 0; top: 0; z-index: 5;"
    " padding: 8px 16px; background: var(--lf-paper);"
    " border-block-end: 1px solid var(--lf-rule); } #site-head > p { margin: 0; }"
    f" main {{ padding-block-start: 120px; }} [id] {{ scroll-margin-top: {ROOM}px; }}"
    "</style>"
)
BODY = (
    '<h1 id="title">Operations brief</h1>'
    + _filler(0, 20)
    + '<section id="risks"><h2>Risks</h2><p>Disk pressure remains the risk.</p></section>'
    + _filler(20, 30)
)

PIN = """() => {
  const pin = document.querySelector('[data-lf-margin-for="head-words"]')
    .getBoundingClientRect();
  const words = document.getElementById('head-words').getBoundingClientRect();
  return {dx: Math.round(pin.left - words.left), dy: Math.round(pin.top - words.top),
          top: Math.round(pin.top)};
}"""


def _scroll_to(page, y):
    page.evaluate("(y) => scrollTo({top: y, behavior: 'instant'})", y)
    scroll_settled(page)


def test_a_page_s_fixed_header_keeps_its_pins_and_lands_by_its_scroll_margin(
    browser, serve, subtests
):
    """A pin on the header's words keeps one seat on screen wherever the document is
    scrolled, since it reads the room in the header rather than the page scrolling
    under it. A link lands its target below the header by the room the page states,
    once: the root's band adds only Leaf's own."""
    html = leaf_page("A fixed site header", BODY, head=STYLE).replace(
        "<body>", f'<body><div class="site">{HEAD}</div>'
    )
    page = open_page(
        browser,
        serve(
            html,
            events=[
                _comment_on("head-words", quote="operations brief from the platform")
            ],
        ),
    )
    resized(page, 1280, 800)

    with subtests.test("a pin on the head's words keeps its seat on screen"):
        _scroll_to(page, 0)
        margins_laid_out(page)
        rest = page.evaluate(PIN)
        _scroll_to(page, 1500)
        margins_laid_out(page)
        scrolled = page.evaluate(PIN)
        assert (scrolled["dx"], scrolled["dy"]) == (rest["dx"], rest["dy"]), (
            rest,
            scrolled,
        )
        assert scrolled["top"] >= 0, scrolled

    with subtests.test("a link in the head lands below it, once"):
        page.mouse.move(5, 400)
        _scroll_to(page, 0)
        page.locator("#to-risks").click()
        page.wait_for_function("() => location.hash === '#risks'")
        scroll_settled(page)
        landed = page.evaluate(
            "() => ({head: document.getElementById('site-head').getBoundingClientRect()"
            ".bottom, risks: document.getElementById('risks').getBoundingClientRect().top,"
            " band: parseFloat(getComputedStyle(document.scrollingElement)"
            ".scrollPaddingTop), scrolled: scrollY})"
        )
        assert landed["scrolled"] > 0, landed
        assert landed["risks"] >= landed["head"], landed
        assert landed["risks"] == pytest.approx(landed["band"] + ROOM, abs=1), landed
