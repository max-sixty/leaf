"""Tests scheduled by the measured cost of their boundary."""

from base64 import b64encode

import pytest
from browser.widgets.test_code_and_documents import HOLD_QUEUE, ROWS, closed_documents
from playwright.sync_api import expect
from render_harness import (
    held_frames,
    leaf_page,
    open_page,
    resized,
    scroll_settled,
    select_words,
    sending,
    write,
)

from leaf.records import page_data as page_data_model
from leaf.source.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_closed_tab_s_document_reports_its_draw_while_later_ones_wait(browser, serve):
    """A closed tab's document reports its draw, marking its text and stamping its
    data's provenance, as it draws, whether its tab shows or not, so the stamp a
    comment on its text anchors to stands while the documents after it still wait to
    draw."""
    url = closed_documents(serve, 4)
    page = open_page(browser, url, init_script=HOLD_QUEUE, upgraded=False)
    page.wait_for_function("() => document.body.hasAttribute('data-lf-presented')")
    last = page.locator("#doc-3")
    expect(page.locator("#doc-1 figure")).to_have_attribute("data-lf-source", "text-1")
    expect(last).not_to_have_class("lf-rendered")
    page.get_by_role("tab", name="Doc 2", exact=True).click()
    expect(page.locator("#doc-2 figure")).to_have_attribute("data-lf-source", "text-2")
    expect(last).not_to_have_class("lf-rendered")
    expect(page.locator("#doc-3 figure")).to_have_attribute("data-lf-source", "text-3")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_long_text_document_draws_the_lines_in_view_and_keeps_the_rest_whole(
    request, serve, engine
):
    """A long text document draws only the runs of lines in view: styling every line on
    each change to the page took tens of seconds and gigabytes at a few megabytes of
    text. The lines out of view stay whole for the reader. The listing holds every
    line, its numbers stand in one column from the first run to the last, and a thread
    on a line far down jumps to the line drawn there. Each run is sized by the lines
    its rows fill: sized a line a row, Firefox drew the far line's run for a returning
    reader. A run drawn before the window narrows forgets the height it was drawn at:
    kept, it left a drag to the bottom short of the last line in both engines. Long
    tokens, which Firefox also breaks after a slash, fill more lines than the size
    says, and the run the travel lands in is drawn for the jump: left skipped,
    Firefox's jump stopped short and a second scroll followed. A second travel while
    the first still holds the run drawn jumps too: it glided."""
    # Long tokens stand in every run but the last, which the drag to the bottom draws:
    # Firefox draws more lines than the size says over them, and the drag would stop
    # short, a limit Leaf accepts.
    text = "".join(
        f"line {i} "
        + (
            b64encode(bytes((i * 31 + k * 101) % 256 for k in range(240))).decode()
            if i % 7 == 0 and i <= 7 * 128
            else "wrapping words " * 20
            if i % 3 == 0
            else "short"
        )
        + "\n"
        for i in range(1, 1001)
    )
    url = serve(
        leaf_page(
            "Long evidence",
            '<h1>Run log</h1><lf-text-document id="log" source="log-text">'
            "</lf-text-document>",
        )
    )
    page_data_model.cmd_data_set(serve.page_dir, "log-text", text)
    page = open_page(request.getfixturevalue(engine), url)
    assert page.locator("#log code").text_content() == text
    expect(page.locator("#log .lf-text-document-run")).to_have_count(8)
    first, far = page.locator(ROWS).nth(0), page.locator(ROWS).nth(879)
    # A run itself always has a box; the browser skips the lines inside it.
    drawn = "line => line.checkVisibility({contentVisibilityAuto: true})"
    assert first.evaluate(drawn)
    assert not far.evaluate(drawn)
    left = "line => line.getBoundingClientRect().left"
    first_left = first.evaluate(left)

    # The last run, drawn and then skipped, meets a narrower window.
    pre, last = page.locator("#log pre"), page.locator(ROWS).nth(999)
    width, height = page.viewport_size["width"], page.viewport_size["height"]
    bottom = "pre => { pre.scrollTop = pre.scrollHeight; }"
    for to, shown in ((bottom, "line"), ("pre => { pre.scrollTop = 0; }", "!line")):
        pre.evaluate(to)
        page.wait_for_function(
            f"line => {shown}.checkVisibility({{contentVisibilityAuto: true}})",
            arg=last.element_handle(),
        )
    resized(page, 560, height)
    rendered(page)
    pre.evaluate(bottom)
    rendered(page)
    below = last.evaluate(
        "line => line.getBoundingClientRect().bottom"
        " - line.closest('pre').getBoundingClientRect().bottom"
    )
    assert below <= 1
    resized(page, width, height)
    pre.evaluate("pre => { pre.scrollTop = 0; }")

    for line, words in ((840, "Where does this start?"), (880, "Why does it repeat?")):
        select_words(page, f"{ROWS} >> nth={line - 1}")
        write(page.locator(".lf-composer leaf-text"), words)
        with sending(page, f"the comment on line {line}"):
            page.keyboard.press("ControlOrMeta+Enter")
        page.keyboard.press("Escape")
    assert far.evaluate(left) == pytest.approx(first_left, abs=0.5)
    # The open card keeps its passage's run drawn; a returning reader finds it skipped.
    page.reload()
    wait_until_ready(page)
    assert not far.evaluate(drawn)
    # Each travel jumps: a glide across the runs drew each one it passed, for seconds.
    # The second leaves while the first still holds the run drawn, as a held `t` does:
    # the frames that would release it are held.
    page.locator("#log pre").evaluate(
        "pre => { window.steps = 0; pre.addEventListener('scroll', () => steps++); }"
    )
    with held_frames(page):
        page.keyboard.press("t")
        page.wait_for_function("() => steps > 0")
        page.keyboard.press("t")
    expect(page.locator(".lf-page-thread")).to_be_focused()
    scroll_settled(page, "#log pre")
    assert page.evaluate("steps") == 2
    landed = far.evaluate("""line => {
      const box = line.closest('pre').getBoundingClientRect();
      const at = line.getBoundingClientRect();
      const hit = document.elementFromPoint(at.left + 30, at.top + 8);
      return {shown: at.top >= box.top && at.bottom <= box.bottom,
              hit: hit && [...line.closest('code').querySelectorAll('.lf-text-document-run > *')]
                .indexOf(hit.closest('.lf-text-document-run > *')) + 1,
              top: at.top - box.top};
    }""")
    assert landed == {"shown": True, "hit": 880, "top": landed["top"]}, landed
