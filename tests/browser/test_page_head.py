"""The page's own head: a header the page fixes at the window's top, or makes the sticky
first thing in `body` or `main`, which Leaf finds and starts its sticky-header slot
below (root-headers.js, `pageHead`). A landing arrives below it, a block's Copy
scrolled under it passes under it, a box sticking at `var(--lf-top)` sticks below it,
and a pin on its own words keeps one seat on screen wherever the document is
scrolled."""

import re

import pytest
from playwright.sync_api import expect
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
LOOK = (
    "#site-head { top: 0; z-index: 5; padding: 8px 16px; background: var(--paper);"
    " border-block-end: 1px solid var(--rule); }"
    " #site-head > p { margin: 0; }"
)
BODY = (
    '<h1 id="title">Operations brief</h1>'
    + _filler(0, 8)
    + '<pre id="deploy"><code>./build --release\n./deploy --to production --wait\n'
    "./verify --all\necho done</code></pre>"
    + _filler(8, 4)
    + '<p id="tool" style="position: sticky; top: var(--lf-top); z-index: 1;'
    ' background: var(--paper)">A row a package sticks at the slot.</p>'
    + _filler(12, 8)
    + '<section id="risks"><h2>Risks</h2><p>Disk pressure remains the risk.</p></section>'
    + _filler(20, 30)
)


def _fixed_beside_main():
    """A site header fixed at the window's top, in a box of its own in `body` beside
    `main`, which only the hit test finds."""
    style = (
        f"<style>{LOOK} #site-head {{ position: fixed; inset-inline: 0; }}"
        " main { padding-block-start: 120px; }</style>"
    )
    return leaf_page("A fixed site header", BODY, head=style).replace(
        "<body>", f'<body><div class="site">{HEAD}</div>'
    )


def _sticky_in_main():
    """A header sticking a gap below the window's top, the first thing in `main`."""
    style = f"<style>{LOOK} #site-head {{ position: sticky; top: 8px; }}</style>"
    return leaf_page("A sticky site header", HEAD + BODY, head=style)


READ = """async () => {
  const geometry = await window.__lfCheckApi();
  const box = (id) => document.getElementById(id).getBoundingClientRect();
  const deploy = document.getElementById('deploy');
  const words = document.getElementById('head-words');
  return {
    head: box('site-head').bottom,
    tool: box('tool').top,
    deploy: box('deploy').top,
    deployShown: geometry.shownRect(deploy, new Map())?.top,
    words: box('head-words').top,
    wordsShown: geometry.shownRect(words, new Map())?.top,
  };
}"""

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


@pytest.mark.parametrize("source", [_fixed_beside_main, _sticky_in_main])
def test_the_pages_own_head_stands_over_what_leaf_draws_and_lands(
    browser, serve, subtests, source
):
    """Leaf's chrome stands above every page box, so a Copy or a pin scrolled under the
    page's header was drawn over it, and a landing, Leaf's sticky boxes and a pin
    seated while the page was scrolled all counted the window's top as clear. On a
    header nobody declares, each read the page as though the header weren't there."""
    page = open_page(
        browser,
        serve(
            source(),
            events=[
                _comment_on("head-words", quote="operations brief from the platform")
            ],
        ),
    )
    resized(page, 1280, 800)

    with subtests.test("a pin on the head's words keeps its seat on screen"):
        # A pass made while the document is scrolled reads the same room: the head's
        # own, in the window, where a seat above the window's top never shows.
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

    with subtests.test("what passes under the head is not on screen"):
        page.evaluate(
            "() => scrollBy({top: document.getElementById('deploy')"
            ".getBoundingClientRect().top - 30, behavior: 'instant'})"
        )
        scroll_settled(page)
        read = page.evaluate(READ)
        assert read["deploy"] < read["head"] - 20, read
        assert read["deployShown"] == pytest.approx(read["head"], abs=0.5), read
        # The head's own words stand over the slot, not under it.
        assert read["wordsShown"] == pytest.approx(read["words"], abs=0.5), read

    with subtests.test("a block's Copy passes under the head"):
        deploy = page.locator("#deploy").bounding_box()
        page.mouse.move(
            deploy["x"] + deploy["width"] / 2, deploy["y"] + deploy["height"] - 8
        )
        copy = page.locator(".lf-code-copy")
        expect(copy).to_have_class(re.compile(r"lf-code-copy-hover"))
        on_top = page.evaluate("""() => {
          const {left, top, right, bottom} = document.querySelector('.lf-code-copy')
            .getBoundingClientRect();
          const hit = document.elementFromPoint((left + right) / 2, (top + bottom) / 2);
          return hit?.closest('#site-head, .lf-code-copy')?.id || hit?.className;
        }""")
        assert on_top == "site-head", on_top

    with subtests.test("a box sticking at the slot sticks below the head"):
        page.evaluate(
            "() => scrollBy({top: document.getElementById('tool')"
            ".getBoundingClientRect().top + 400, behavior: 'instant'})"
        )
        scroll_settled(page)
        read = page.evaluate(READ)
        assert read["tool"] == pytest.approx(read["head"], abs=1), read

    with subtests.test("a link in the head lands below it"):
        page.mouse.move(5, 400)
        _scroll_to(page, 0)
        page.locator("#to-risks").click()
        page.wait_for_function("() => location.hash === '#risks'")
        scroll_settled(page)
        landed = page.evaluate(
            "() => ({head: document.getElementById('site-head').getBoundingClientRect()"
            ".bottom, risks: document.getElementById('risks').getBoundingClientRect().top,"
            " scrolled: scrollY})"
        )
        assert landed["scrolled"] > 0, landed
        assert landed["risks"] >= landed["head"], landed
