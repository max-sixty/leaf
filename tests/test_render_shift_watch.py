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
    consume_browser_errors(page, "typing in textarea#field moved textarea#field")


def test_typing_may_grow_its_field(browser):
    page = field_page(browser, "grow")
    page.locator("#field").fill("a")
    judge_shifts()


def test_a_shift_without_input_fails(browser):
    page = field_page(browser)
    page.evaluate("document.getElementById('above').style.height = '40px'")
    judge_shifts()
    consume_browser_errors(page, "textarea#field moved without input by (0, 40)px")


# A composer pinned to the viewport's foot, standing partly past its right edge and
# painting a shadow to its left, whose field grows up as a key lands in it: what Chrome
# reports of it is clipped and shadowed, not its box.
FOOT = """<!doctype html><body style="margin:0">
<div id="foot" style="position: fixed; bottom: 0; right: -300px; width: 400px;
  box-shadow: -60px 0 40px black">
  <textarea id="field" rows="1" style="display: block; width: 100%"></textarea>
</div>
<script>
  const field = document.getElementById("field");
  field.addEventListener("beforeinput", () => { field.rows += 2; });
</script>"""


def foot_page(browser):
    page = browser.new_page()
    page.goto("data:text/html," + quote(FOOT))
    return page


def test_typing_may_grow_a_field_whose_holder_paints_past_the_viewport(browser):
    page = foot_page(browser)
    page.locator("#field").fill("a")
    judge_shifts()


def test_typing_into_a_holder_still_sliding_in_is_the_slide_s(browser):
    page = foot_page(browser)
    page.evaluate(
        """document.getElementById("foot").animate(
          [{ transform: "translateX(-200px)" }, { transform: "none" }], 3000)"""
    )
    page.locator("#field").fill("a")
    page.locator("#field").fill("ab")
    judge_shifts()


def test_a_shift_without_input_after_typing_fails(browser):
    page = field_page(browser)
    page.locator("#field").fill("a")
    page.evaluate(
        """() => new Promise((done) => requestAnimationFrame(() =>
          requestAnimationFrame(() => requestAnimationFrame(done))))"""
    )
    page.evaluate("document.getElementById('above').style.height = '40px'")
    judge_shifts()
    consume_browser_errors(page, "textarea#field moved without input")


# A frame nested in the page, whose button grows a box above a paragraph in that frame.
NESTED = """<!doctype html><body style="margin:0">
<div id="above"></div><p id="below">Below.</p>
<button id="grow" onclick="document.getElementById('above').style.height = '40px'">
  Grow</button>"""


def test_a_press_in_a_nested_frame_is_input(browser):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(f'<iframe src="data:text/html,{quote(NESTED)}"></iframe>')
    )
    page.frame_locator("iframe").locator("#grow").click()
    judge_shifts()


def test_a_press_in_the_page_holding_a_frame_is_input_to_it(browser):
    page = browser.new_page()
    child = '<div id="above"></div><p id="below">Below.</p>'
    page.goto(
        "data:text/html,"
        + quote(
            f"<iframe srcdoc='{child}'></iframe><button id='grow' onclick=\""
            "frames[0].document.getElementById('above').style.height = '40px'"
            '">Grow</button>'
        )
    )
    page.locator("#grow").click()
    judge_shifts()
