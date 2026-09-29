"""The browser fixture fails the layout shifts the "Stability" rule forbids
(`shift_watch.js`): a shift without input, and typing that carries its field."""

from urllib.parse import quote

from render_harness import consume_browser_errors, judge_shifts

# A field below a box. A key landing in the field grows the box above it, carrying the
# field, or grows the field itself, as the page's `data-key` says.
FIELD = """<!doctype html><body style="margin:0">
<div id="above"></div><textarea id="field" rows="1" style="display: block"></textarea>
<script>
  const above = document.getElementById("above");
  const field = document.getElementById("field");
  field.addEventListener("beforeinput", () => {
    if (document.body.dataset.key === "carry") above.style.height = "59px";
    if (document.body.dataset.key === "grow") field.rows = 4;
  });
</script>"""


def field_page(browser, key=""):
    page = browser.new_page()
    page.goto("data:text/html," + quote(FIELD))
    page.evaluate("key => { document.body.dataset.key = key; }", key)
    return page


def test_typing_that_carries_its_field_fails_at_the_last_keystroke(browser):
    page = field_page(browser, "carry")
    page.locator("#field").fill("a")
    judge_shifts()
    consume_browser_errors(
        page, "typing in textarea#field moved textarea#field"
    )


def test_typing_may_grow_its_field(browser):
    page = field_page(browser, "grow")
    page.locator("#field").fill("a")
    judge_shifts()


def test_a_shift_without_input_fails(browser):
    page = field_page(browser)
    page.evaluate("document.getElementById('above').style.height = '40px'")
    judge_shifts()
    consume_browser_errors(page, "textarea#field moved without input by (0, 40)px")
