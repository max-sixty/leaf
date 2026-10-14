"""The shift watch's gate, which every browser test runs (`shift_watch.js`, "The
gate"): Chrome's layout-shift entries, owned by the watch's record of input rather than
by Chrome's recent-input window, and typing judged on its field's holders alone. What
the gate shares with the ledger, its declared regions and native placement, runs in
both modes in `test_render_shift_watch.py`."""

from urllib.parse import quote

import pytest
from render_harness import SHIFT_LEDGER, consume_browser_errors, judge_watches

from browser.test_render_shift_watch import (
    FIELD,
    PAINTED,
    field_page,
    moved_within,
    names_move,
)

# The ledger setting must not turn these tests into the ledger's.
pytestmark = pytest.mark.shift_ledger(False)

# Chrome's own reading of each shift, beside the watch's.
NATIVE_SHIFTS = """() => {
  window.nativeShifts = [];
  new PerformanceObserver((list) => nativeShifts.push(...list.getEntries().map(
    (entry) => ({recent: entry.hadRecentInput, value: entry.value}))))
    .observe({type: 'layout-shift'});
}"""


def native_shifts(page):
    """Chrome's entries since `NATIVE_SHIFTS`, once the watch has judged them."""
    judge_watches()
    shifts = page.evaluate("nativeShifts")
    assert shifts, "the change painted no layout shift"
    return shifts


def test_a_shift_without_input_fails_and_names_the_ledger(browser):
    page = field_page(browser)
    page.evaluate("() => { document.getElementById('above').style.height = '40px'; }")
    judge_watches()
    errors = consume_browser_errors(page, moved_within("textarea#field", by=[0, 40]))
    assert f"rerun with {SHIFT_LEDGER}=1" in str(errors[0]), errors[0]
    assert errors[0].values["evidence"]["kind"] == "native"


@pytest.mark.parametrize("cause", ["press", "script"])
def test_only_the_press_owns_a_shift_in_chromes_recent_input_window(browser, cause):
    """Chrome credits every shift for half a second after a press. The watch credits the
    press's own rendering, so a script's move painted inside that window still fails.
    The script waits out the press's rendering, which ends a frame after it settles,
    and moves well within Chrome's window."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><body style="margin:0"><div id="above"></div>'
            '<p id="reading" style="margin:0">Read this paragraph.</p>'
            '<button id="press">Press</button>'
            "<script>const grow = () => { above.style.height = '40px'; };"
            "press.onclick = () => { if (document.body.dataset.cause === 'press') grow(); };"
            "</script>"
        )
    )
    page.evaluate(PAINTED)
    page.evaluate(NATIVE_SHIFTS)
    page.evaluate("cause => { document.body.dataset.cause = cause; }", cause)
    page.locator("#press").click()
    if cause == "script":
        page.evaluate(
            """() => new Promise((done) => {
              let count = 4;
              const next = () => (--count ? requestAnimationFrame(next) : done(grow()));
              requestAnimationFrame(next);
            })"""
        )
    assert all(shift["recent"] for shift in native_shifts(page))
    if cause == "script":
        errors = consume_browser_errors(page, {"code": "moved-without-input"})
        assert names_move(errors, "p#reading"), errors


def test_typing_through_fill_owns_the_reflow_it_causes(browser):
    """`fill` sends no key, so Chrome counts its reflow as unrequested; the watch's
    record of the edit owns it."""
    page = browser.new_page()
    page.goto("data:text/html," + quote(FIELD + '<p id="below">Below the field.</p>'))
    page.evaluate(PAINTED)
    page.evaluate(NATIVE_SHIFTS)
    page.evaluate("() => { document.body.dataset.key = 'grow'; }")
    page.locator("#field").fill("a")
    assert not any(shift["recent"] for shift in native_shifts(page))


def test_typing_through_fill_that_carries_its_field_fails(browser):
    page = field_page(browser, "carry")
    page.locator("#field").fill("a")
    judge_watches()
    errors = consume_browser_errors(
        page,
        {"code": "typing-moved", "field": "textarea#field", "node": "textarea#field"},
    )
    assert errors[0].values["by"] == [0, 59], errors[0]
    assert f"rerun with {SHIFT_LEDGER}=1" in str(errors[0]), errors[0]
