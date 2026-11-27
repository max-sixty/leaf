"""What the page says the agent is doing: the floating panel's leaf and field, the tab's
mark, and each message's workflow, dated by the server's clock."""

import os
import re

import pytest
from interact_support import (
    declare,
    declare_work,
    end_work,
    record_claim,
)
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_cases_navigation import TAB_AND_DOT, TAB_TONE, live_watcher
from render_harness import (
    LONG_PAGE,
    CutOff,
    nudge,
    open_page,
    open_threads,
    panel_settled,
    shown,
    told,
)

from leaf.source import render_checks as render_checks_model

pytestmark = pytest.mark.shifts_unsurveyed

# Where the folded leaf says the status's whole sentence: under its name in its
# preview (annotations/preview.js), once that opens after the pointer's dwell. Closed, the preview
# still holds the lines of whatever it last showed, such as a thread row's.
PEEK = "#lf-preview:popover-open .lf-preview-detail"
LEAF = ".lf-fp-leaf"


def expect_status_says(page, words):
    """Fold the panel to its leaf, the one seat that says the status's whole sentence
    when pointed at, read it in the leaf's preview, which keeps what it opened with
    while it shows (annotations/preview.js), and unfold the panel again. Folding puts away what
    stands open in the panel, and the pointer leaves, so the next reading is a new
    one."""
    close = page.locator(".lf-fp-close")
    if close.is_visible():
        close.click()
        panel_settled(page, open=False)
    page.evaluate("() => document.activeElement?.blur()")
    page.keyboard.press(".")
    leaf = page.locator(LEAF)
    expect(leaf).to_have_attribute("aria-label", re.compile(r"^Unfold Leaf"))
    leaf.hover()
    expect(page.locator(PEEK)).to_have_text(words)
    page.mouse.move(5, 5)
    expect(page.locator("#lf-preview")).to_be_hidden()
    page.keyboard.press(".")
    expect(leaf).to_have_attribute("aria-label", re.compile(r"^Page menu"))


def workflow_of(scope, message):
    """The workflow line on `message`'s head where `scope` draws it."""
    return scope.locator(
        f'.lf-msg[data-lf-event="{message}"] > .lf-msg-head .lf-msg-sending'
    )


def thread_row_says(page, thread, resolved=False):
    """Open the panel's Threads and return what `thread`'s row says of where it stands,
    beside its name, among the open threads or, where `resolved`, under Resolved."""
    open_threads(page)
    state = "[data-lf-resolved]" if resolved else ":not([data-lf-resolved])"
    return page.locator(f'.lf-fp-thread[data-lf-key="{thread}"]{state} .lf-row-end')


def test_the_leaf_perks_as_the_agent_takes_up_work_not_as_the_page_reconnects(
    browser, serve
):
    """The panel's leaf perks once as the agent takes up work. A read that fails while
    it works shows the page cut off, and the next shows the work again; the agent
    never stopped, so the leaf doesn't perk again."""
    page = open_page(browser, serve(LONG_PAGE))
    d = serve.page_dir
    record_claim(d, id="s", pid=os.getpid(), agent="Claude")
    # The sequence of motions the leaf's mark starts, each by the turn it reaches first
    # (panel/floating-panel.js, `MOTIONS`).
    page.evaluate(
        """() => {
          window.__lfLeaf = [];
          const animate = Element.prototype.animate;
          Element.prototype.animate = function (keyframes, options) {
            if (this.matches('.lf-fp-leaf > svg'))
              window.__lfLeaf.push(keyframes[1].transform);
            return animate.call(this, keyframes, options);
          };
        }"""
    )
    perk = "translateY(-3px) scale(1.14)"
    declare_work(d, "Writing the page")
    told(page)
    expect(page.locator(LEAF)).to_have_attribute("data-lf-tone", "working")
    page.wait_for_function("() => window.__lfLeaf.length === 1")
    assert page.evaluate("() => window.__lfLeaf") == [perk]

    reads = CutOff().hold(page)
    nudge(d)
    expect(page.locator(LEAF)).to_have_attribute("data-lf-tone", "blocked")
    reads.restore()
    nudge(d)
    told(page)
    expect(page.locator(LEAF)).to_have_attribute("data-lf-tone", "working")
    told(page)
    assert page.evaluate("() => window.__lfLeaf") == [perk]


def test_the_tab_wears_what_the_leaf_says(browser, serve, tmp_path, dead_pid):
    """The judgment's third seat, and the only one a user with six leaves open in a
    row of tabs can see without opening any. The mark is the vendored icon.svg and the
    runtime paints the element it declares in whatever colour the dot is wearing, so the
    tab and the leaf are one fact read twice: a palette written out again for the tab
    would be free to drift from the theme the day a project overrode a token, and drift
    silently, since a tab nobody is watching closely is exactly the case this is for."""
    page = open_page(browser, serve(LONG_PAGE))
    d = serve.page_dir

    def tone(want, why):
        try:
            return page.wait_for_function(TAB_TONE, arg=want).json_value()
        except PlaywrightTimeout:
            # The console with it: a mark the runtime refuses reads here as a tab with
            # no tone on it, and the reason it refused is the only thing that says why.
            found = page.evaluate(TAB_AND_DOT, want)
            pytest.fail(
                f"the tab never said {why} as the leaf does: {found}\n"
                + shown(page.lf_errors)
            )

    declare_work(d, "Writing the page")
    told(page)
    working = tone("working", "working")
    end_work(d)
    declare(d)
    told(page)
    with live_watcher(d, page):
        awaits = tone("listening", "awaits")
    # The distinctness is the half agreement alone can't prove: a tab painted once and
    # never again agrees with a dot that never moved either, and the two states a user
    # is choosing between — this page wants me, that one is busy — are exactly the pair
    # that would collapse.
    assert awaits != working, (
        f"a page awaiting its user wears the same tab as one that is working ({awaits})"
    )

    # The claimant is gone, so nothing is behind the page: grey on the leaf, and grey
    # in the tab, which is the whole of what the user can see of it from a tab strip.
    record_claim(d, id="s", pid=dead_pid)
    unheld = tone("", "unheld")
    assert unheld not in (
        working,
        awaits,
    ), f"a page nothing holds wears a tab claiming a session ({unheld})"

    # And the mark itself is an image the browser will render, which is the one thing
    # a string comparison above cannot say: an SVG this file mangles decodes to nothing
    # and shows as a blank tab, with no error anywhere to find it by.
    page.evaluate("""() => {
        const img = new Image();
        globalThis.__lfTabMarkWidth = null;
        globalThis.__lfTabMarkImage = img;
        const done = (width) => {
          globalThis.__lfTabMarkWidth = width;
          delete globalThis.__lfTabMarkImage;
        };
        img.onload = () => done(img.naturalWidth);
        img.onerror = () => done(0);
        img.src = document.querySelector('link[rel=icon]').getAttribute('href');
    }""")
    page.wait_for_function(
        "() => globalThis.__lfTabMarkWidth !== null",
        timeout=render_checks_model.SERVED_TIMEOUT_MS,
    )
    drawn = page.evaluate("() => globalThis.__lfTabMarkWidth")
    assert drawn > 0, "the tab's mark is not an image the browser can decode"
