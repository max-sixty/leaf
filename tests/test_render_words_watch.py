"""The browser fixture fails the loss the "Words stay where they were typed" rule
forbids (`words_watch.js`): typed words leaving the screen without a key or press."""

from urllib.parse import quote

import pytest
from render_harness import consume_browser_errors, judge_watches

# A box holding a field, on a page long enough to scroll. What the page does to the box
# when the user scrolls, presses Escape, or presses elsewhere is the page's `data-on`.
BOX = """<!doctype html><body style="margin:0">
<div id="box"><textarea id="field"></textarea></div>
<button id="elsewhere">Elsewhere</button>
<div style="height: 300vh"></div>
<script>
  const box = document.getElementById("box");
  const on = (what, act) => document.body.dataset.on === what && act();
  addEventListener("scroll", () => {
    on("scroll-hides", () => { box.style.display = "none"; });
    on("scroll-veils", () => { box.style.visibility = "hidden"; });
    on("scroll-clears", () => { document.getElementById("field").value = ""; });
    on("scroll-replaces", () => {
      const heir = document.createElement("textarea");
      heir.value = document.getElementById("field").value;
      box.replaceChildren(heir);
    });
  });
  addEventListener("keydown", (event) =>
    event.key === "Escape" && on("escape-hides", () => { box.hidden = true; }));
  document.getElementById("elsewhere").addEventListener("click", () =>
    on("press-hides", () => { box.remove(); }));
</script>"""


def box_page(browser, on):
    page = browser.new_page()
    page.goto("data:text/html," + quote(BOX))
    page.evaluate("on => { document.body.dataset.on = on; }", on)
    page.locator("#field").fill("Half a thought")
    return page


def scrolled(page):
    page.mouse.move(200, 200)
    page.mouse.wheel(0, 600)
    page.wait_for_function("() => scrollY > 0")


def test_words_a_scroll_hides_fail(browser):
    page = box_page(browser, "scroll-hides")
    scrolled(page)
    judge_watches()
    consume_browser_errors(
        page,
        'typed words left the screen without a key or press: "Half a thought"'
        " in textarea#field",
    )


def test_words_a_scroll_hides_fail_after_moving_among_them(browser):
    """A press on the field and a key that moves its caret are the user moving among
    their words, not putting them away, so a scroll that hides the box after them
    still fails."""
    page = box_page(browser, "scroll-hides")
    page.locator("#field").click()
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("Shift")
    scrolled(page)
    judge_watches()
    consume_browser_errors(page, "typed words left the screen without a key or press")


def test_words_a_scroll_clears_fail(browser):
    page = box_page(browser, "scroll-clears")
    scrolled(page)
    judge_watches()
    consume_browser_errors(page, "typed words left the screen without a key or press")


@pytest.mark.parametrize("announced", [False, True])
def test_words_a_handler_clears_in_their_own_turn_fail(browser, announced):
    """A handler that empties the field as the edit lands, and may announce that with an
    `input` of its own, has still taken the user's words."""
    announce = "field.dispatchEvent(new Event('input'));" if announced else ""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            "<textarea id=field></textarea><script>"
            "field.addEventListener('input', (event) => {"
            f" if (event.isTrusted) {{ field.value = ''; {announce} }} }});"
            "</script>"
        )
    )
    page.locator("#field").press_sequentially("x")
    judge_watches()
    consume_browser_errors(
        page, 'typed words left the screen without a key or press: "x"'
    )


def test_words_scrolled_out_of_view_stay(browser):
    page = box_page(browser, "")
    scrolled(page)
    judge_watches()


def test_words_held_out_of_view_stay(browser):
    page = box_page(browser, "scroll-veils")
    scrolled(page)
    judge_watches()


def test_words_handed_to_a_replacing_field_stay(browser):
    page = box_page(browser, "scroll-replaces")
    scrolled(page)
    judge_watches()


def test_words_escape_puts_away_are_put_away(browser):
    page = box_page(browser, "escape-hides")
    page.keyboard.press("Escape")
    judge_watches()


def test_words_a_press_elsewhere_puts_away_are_put_away(browser):
    page = box_page(browser, "press-hides")
    page.locator("#elsewhere").click()
    judge_watches()


def test_words_a_press_in_the_page_holding_their_frame_puts_away_are_put_away(browser):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            "<iframe srcdoc='<textarea id=field></textarea>'></iframe>"
            "<button id='clear' onclick=\""
            "frames[0].document.getElementById('field').remove()"
            '">Clear</button>'
        )
    )
    page.frame_locator("iframe").locator("#field").fill("Half a thought")
    page.locator("#clear").click()
    judge_watches()
