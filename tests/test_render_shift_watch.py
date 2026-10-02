"""The browser fixture fails the layout shifts the "Stability" rule forbids
(`shift_watch.js`): a shift without input, and typing that carries its field."""

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pytest
from known_faults import known
from playwright.sync_api import expect
from render_cases_interaction import ASK_PAGE
from render_harness import (
    consume_browser_errors,
    judge_watches,
    open_page,
    panel_settled,
    resized,
    ticked,
)


def test_known_thread_fold_classifies_each_source_of_the_same_shift():
    test = SimpleNamespace(
        path=Path("test_website_server.py"),
        originalname="test_a_website_turn_posts_its_answer_when_the_move_is_settled_first",
    )
    assert known(
        test,
        "span.lf-thread-topic moved without input by (8, 0)px; "
        "the same frame moved details.lf-thread-compact.flash.lf-thread, "
        "span.lf-thread-trailing",
    )
    assert not known(test, "span.lf-thread-topic moved without input by (8, 0)px")


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


# Chrome reports no shift before a page first paints, and `load` can come before it.
PAINTED = """() => new Promise((done) => requestAnimationFrame(() =>
  requestAnimationFrame(done)))"""


def field_page(browser, key=""):
    page = browser.new_page()
    page.goto("data:text/html," + quote(FIELD))
    page.evaluate(PAINTED)
    page.evaluate("key => { document.body.dataset.key = key; }", key)
    return page


def test_typing_that_carries_its_field_fails_at_the_last_keystroke(browser):
    page = field_page(browser, "carry")
    page.locator("#field").fill("a")
    judge_watches()
    consume_browser_errors(page, "typing in textarea#field moved textarea#field")


def test_typing_may_grow_its_field(browser):
    page = field_page(browser, "grow")
    page.locator("#field").fill("a")
    judge_watches()


@pytest.mark.parametrize("distance", [6, 40])
def test_a_shift_without_input_fails(browser, distance):
    page = field_page(browser)
    page.evaluate(
        "distance => { document.getElementById('above').style.height = distance + 'px'; }",
        distance,
    )
    judge_watches()
    consume_browser_errors(
        page, f"textarea#field moved without input by (0, {distance})px"
    )


METADATA = """<!doctype html><body style="margin:0; font:12px monospace">
<div id="row" style="display:flex; align-items:baseline; width:360px; line-height:24px">
  <div id="header" style="display:contents">
    <b>You</b><span class="lf-msg-meta" style="display:flex; gap:8px; margin-left:8px">
      <time id="age">just now</time><span id="receipt">Sent</span>
    </span>
  </div>
</div>
<p id="reading">Read this paragraph.</p>
<textarea id="field" rows="1"></textarea>
</body>"""


@pytest.mark.parametrize(
    "fault, protected",
    [
        ("", None),
        ("adjacent_control", "button#action"),
        ("contained_control", "button#action"),
        ("growing_header", "p#reading"),
        ("escaping_label", "span#receipt"),
    ],
)
def test_metadata_motion_is_confined_to_a_passive_header(browser, fault, protected):
    """A real label shift passes; a moved control, reading line or escaped label fails."""
    page = browser.new_page()
    page.goto("data:text/html," + quote(METADATA))
    if fault in {"adjacent_control", "contained_control"}:
        page.evaluate(
            """fault => {
              const button = document.createElement('button');
              button.id = 'action';
              button.textContent = 'Act';
              document.querySelector(fault === 'contained_control' ? '.lf-msg-meta' : '#row')
                .append(button);
            }""",
            fault,
        )
    page.evaluate(PAINTED)
    receipt = page.locator("#receipt")
    before = receipt.bounding_box()
    page.evaluate(
        """fault => {
          document.getElementById('age').textContent = '1m ago';
          const metadata = document.querySelector('.lf-msg-meta');
          if (fault === 'growing_header') metadata.style.paddingBlockStart = '20px';
          if (fault === 'escaping_label') metadata.style.paddingInlineStart = '420px';
        }""",
        fault,
    )
    judge_watches()
    assert receipt.bounding_box()["x"] != before["x"]
    if protected:
        errors = consume_browser_errors(page, "moved without input")
        assert any(f"{protected} moved without input" in error for error in errors), (
            errors
        )


@pytest.mark.parametrize(
    "motion",
    ["", "control", "resize", "hidden", "clipped", "scroll", "sticky", "visible_child"],
)
def test_metadata_at_the_source_cap_cannot_hide_a_control(browser, motion):
    """Five receipt sources pass only when an omitted control also holds still."""
    rows = "".join(
        f'<div style="display:flex;width:360px;height:30px;align-items:baseline">'
        '<b>You</b><span class="lf-msg-meta" style="display:flex;gap:8px;margin-left:8px">'
        f'<time>just now</time><span id="receipt{n}" style="width:150px">Sent</span>'
        "</span></div>"
        for n in range(6)
    )
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    button = (
        '<button id="action" style="font-size:8px;padding:0;width:40px;height:12px;'
        + ("visibility:hidden;" if motion == "hidden" else "")
        + ("margin-top:40px;" if motion == "clipped" else "")
        + ("position:sticky;top:0;" if motion == "sticky" else "")
        + ("visibility:visible;" if motion == "visible_child" else "")
        + '">Act</button>'
    )
    if motion == "clipped":
        button = '<div style="height:10px;overflow:hidden">' + button + "</div>"
    if motion == "visible_child":
        button = '<div style="visibility:hidden">' + button + "</div>"
    if motion in {"scroll", "sticky"}:
        rows = (
            '<div id="scroller" style="height:200px;overflow:auto">'
            + (button if motion == "sticky" else "")
            + rows
            + '<div style="height:400px"></div></div>'
        )
        if motion == "sticky":
            button = ""
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><body style="margin:0;font:12px monospace">'
            + rows
            + button
            + "</body>"
        )
    )
    if motion == "sticky":
        page.evaluate("document.getElementById('scroller').scrollTop = 30")
    page.evaluate(PAINTED)
    page.evaluate(
        """motion => {
          window.sources = [];
          new PerformanceObserver(list => {
            for (const entry of list.getEntries())
              window.sources.push(entry.sources.map(source => source.node?.id));
          }).observe({type: 'layout-shift'});
          for (const age of document.querySelectorAll('time')) age.textContent = '1m ago';
          const button = document.getElementById('action');
          if (['control', 'hidden', 'clipped', 'visible_child'].includes(motion))
            button.style.marginTop = motion === 'clipped' ? '46px' : '6px';
          if (motion === 'resize') {
            button.style.marginLeft = '6px'; button.style.width = '34px';
          }
          if (motion === 'scroll') document.getElementById('scroller').scrollTop = 6;
          if (motion === 'sticky') document.getElementById('scroller').scrollTop = 36;
        }""",
        motion,
    )
    judge_watches()
    sources = page.evaluate("window.sources")
    assert len(sources) == 1 and len(sources[0]) == 5, sources
    assert all(source.startswith("receipt") for source in sources[0]), sources
    if motion in {"control", "resize", "visible_child"}:
        consume_browser_errors(page, "moved without input")


@pytest.mark.nightly
@pytest.mark.watch_shifts
def test_a_nightly_page_watches_typing_and_unasked_shifts(browser):
    """Nightly opt-in uses the same sensor: growing a field is allowed, carrying it
    without input is reported, and typing that carries it is reported too."""
    page = field_page(browser, "grow")
    page.locator("#field").fill("a")
    judge_watches()
    assert page.lf_errors == []
    page.evaluate("document.getElementById('above').style.height = '40px'")
    judge_watches()
    consume_browser_errors(page, "textarea#field moved without input")

    carried = field_page(browser, "carry")
    carried.locator("#field").fill("a")
    judge_watches()
    consume_browser_errors(carried, "typing in textarea#field moved textarea#field")


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
    judge_watches()


def test_typing_into_a_holder_still_sliding_in_is_the_slide_s(browser):
    page = foot_page(browser)
    page.evaluate(
        """document.getElementById("foot").animate(
          [{ transform: "translateX(-200px)" }, { transform: "none" }], 3000)"""
    )
    page.locator("#field").fill("a")
    page.locator("#field").fill("ab")
    judge_watches()


def test_a_shift_without_input_after_typing_fails(browser):
    page = field_page(browser)
    page.locator("#field").fill("a")
    page.evaluate(
        """() => new Promise((done) => requestAnimationFrame(() =>
          requestAnimationFrame(() => requestAnimationFrame(done))))"""
    )
    page.evaluate("document.getElementById('above').style.height = '40px'")
    judge_watches()
    consume_browser_errors(page, "textarea#field moved without input")


# News three frames after a press, as a reply lands just after a click: the page adopts
# a server reading. A stand-in for the runtime never settles its rendering, so the
# press's rendering is still open when the news lands. What moves the line is the
# page's `data-motion`: the news growing a box above it (none), the news beginning a
# bar's slide above it (`news`), or the press beginning that slide, which runs on past
# news that moves nothing (`press`).
NEWS = """<!doctype html><body style="margin:0">
<script data-lf-entry>document.currentScript.lfRenderingSettled = () => false;</script>
<button id="press">Press</button>
<div id="bar"></div><div id="above"></div><div id="below">Below.</div>
<script>
  const frames = (n, then) => requestAnimationFrame(() => n > 1 ? frames(n - 1, then) : then());
  const motion = () => document.body.dataset.motion;
  const slide = () => document.getElementById("bar").animate(
    [{ height: "0px" }, { height: "300px" }], { duration: 400, fill: "forwards" });
  document.getElementById("press").addEventListener("pointerdown", (event) => {
    if (motion() === "press") slide();
    const pressed = event.timeStamp;
    frames(3, () => {
      document.body.setAttribute("data-lf-reading", "news");
      if (motion() === "news") slide();
      if (!motion()) document.getElementById("above").style.height = "40px";
      document.body.dataset.newsAfter = performance.now() - pressed;
    });
  });
</script>"""


def news_page(browser, motion=""):
    page = browser.new_page()
    page.goto("data:text/html," + quote(NEWS))
    # The stand-in's page has presented, so its shifts are judged.
    page.evaluate("document.body.setAttribute('data-lf-presented', '')")
    page.evaluate("motion => { document.body.dataset.motion = motion; }", motion)
    page.locator("#press").click()
    page.wait_for_function("document.body.dataset.newsAfter !== undefined")
    # Chrome counts the press as recent input for half a second, so news after it is
    # what this page tests.
    assert float(page.evaluate("document.body.dataset.newsAfter")) < 500
    return page


@pytest.mark.parametrize("motion", ["", "news"], ids=["grows a box", "begins a slide"])
def test_news_just_after_a_press_moves_nothing(browser, motion):
    page = news_page(browser, motion)
    judge_watches()
    consume_browser_errors(page, "div#below moved without input")


def test_motion_a_press_began_is_the_press_s_through_news(browser):
    news_page(browser, "press")
    judge_watches()


# Rows in a box that clips without scrolling, as a diff's file does, and a box among
# them that grows by script. Above the window, the root's scroll anchoring holds the rows
# where they stand, though Chrome measures them against the clipping box and reports
# them moved by the anchoring's amount. In view, the rows below it move.
CLIPPED = """<!doctype html><body style="margin:0">
<div style="overflow: clip">
  <div id="grows" style="height: 100px"></div>
  {rows}
</div>
<div style="height: 3000px"></div>"""


@pytest.mark.parametrize("where", ["above the window", "in view"])
def test_a_row_moved_only_where_its_box_moves_on_screen(browser, where):
    rows = "".join(
        f'<div id="r{n}" style="height: 15px">Row {n}</div>' for n in range(60)
    )
    page = browser.new_page()
    page.goto("data:text/html," + quote(CLIPPED.format(rows=rows)))
    if where == "above the window":
        page.evaluate("scrollTo(0, document.getElementById('r8').offsetTop)")
    page.evaluate(PAINTED)
    page.evaluate("document.getElementById('grows').style.height = '300px'")
    judge_watches()
    if where == "in view":
        consume_browser_errors(page, "moved without input by (0, 200)px")


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
    judge_watches()


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
    judge_watches()


@pytest.mark.parametrize("surface", ["card", "panel"])
def test_message_age_may_shift_metadata_but_leaves_the_thread_in_place(
    browser, serve, surface
):
    """Age and receipt may rearrange; the thread and its controls stay put."""
    page = open_page(
        browser,
        serve(
            ASK_PAGE,
            events=[
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "Check whether these jobs can share one visit.",
                    "anchor": {"section": "bracket"},
                }
            ],
        ),
    )
    resized(page, 1440, 900)
    if surface == "card":
        page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
        surface_root = page.locator(".lf-margin-preview")
        header = surface_root.locator(".lf-page-thread-head").first
    else:
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        surface_root = page.locator(".lf-thread[open]")
        header = surface_root.locator(".lf-msg-head").first
    receipt = header.locator(".lf-msg-sending")
    timestamp = header.locator("time")
    expect(receipt).to_have_text("Sent")
    expect(timestamp).to_have_text("just now")
    protected = surface_root.locator(
        "b, button, leaf-text, .lf-msg-body, .lf-page-thread-body"
    )
    boxes = "nodes => nodes.map(node => node.getBoundingClientRect().toJSON())"
    before = protected.evaluate_all(boxes)
    assert before
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    now = datetime.now().astimezone()
    for delta, age in [
        (timedelta(minutes=1), "1m ago"),
        (timedelta(minutes=10), "10m ago"),
        (timedelta(hours=3), "3h ago"),
    ]:
        page.clock.set_fixed_time(now + delta)
        ticked(page)
        expect(timestamp).to_have_text(age)
        assert protected.evaluate_all(boxes) == before
