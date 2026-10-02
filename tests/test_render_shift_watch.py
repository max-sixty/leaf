"""The browser fixture fails the layout shifts the "Stability" rule forbids
(`shift_watch.js`): a shift without input, and typing that carries its field."""

from datetime import datetime, timedelta
from urllib.parse import quote

import pytest
from playwright.sync_api import expect
from render_cases_interaction import ASK_PAGE
from render_harness import (
    consume_browser_errors,
    judge_watches,
    leaf_page,
    open_page,
    panel_settled,
    resized,
    take_browser_errors,
)

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


PASSIVE_LABELS = """<!doctype html><body class="lf-chrome" style="margin:0; font:12px monospace">
<div id="row" data-lf-reflow="text" style="display:flex; align-items:baseline; width:360px; line-height:24px">
  <div id="header" style="display:flex; align-items:baseline">
    <b>You</b><span id="labels" style="display:flex; gap:8px; margin-left:8px">
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
        ("informational_group", None),
        ("stationary_control", None),
        ("boxless_header", None),
        ("nested_stable_region", None),
        ("nested_unstable_region", "span#receipt"),
        ("nested_boxless_region", "span#receipt"),
        ("moving_region", "div#row"),
        ("contained_aria_control", "span#receipt"),
        ("tabbable_group", "span#receipt"),
        ("outside_runtime", "span#receipt"),
        ("undeclared", "span#receipt"),
        ("adjacent_control", "button#action"),
        ("contained_control", "button#action"),
        ("growing_header", "p#reading"),
        ("escaping_label", "span#receipt"),
    ],
)
@pytest.mark.parametrize("owner_kind", ["chrome", "inline"])
def test_passive_motion_is_confined_to_a_runtime_owned_region(
    browser, fault, protected, owner_kind
):
    """A real label shift passes; a moved control, reading line or escaped label fails."""
    page = browser.new_page()
    source = PASSIVE_LABELS
    if owner_kind == "inline":
        source = source.replace('class="lf-chrome"', "").replace(
            'id="row"', 'id="row" data-lf-runtime'
        )
    page.goto("data:text/html," + quote(source))
    if fault in {
        "boxless_header",
        "nested_stable_region",
        "nested_unstable_region",
        "nested_boxless_region",
    }:
        page.locator("#header").evaluate(
            """(node, fault) => {
              if (fault !== 'boxless_header') node.setAttribute('data-lf-reflow', 'text');
              if (fault === 'boxless_header' || fault === 'nested_boxless_region')
                node.style.display = 'contents';
              if (fault === 'nested_stable_region') node.style.width = '180px';
            }""",
            fault,
        )
    if fault == "stationary_control":
        page.locator("#row").evaluate(
            """row => {
              const control = document.createElement('button');
              control.id = 'action'; control.textContent = 'Resolve';
              control.style.marginInlineStart = 'auto'; row.append(control);
            }"""
        )
    if fault in {"informational_group", "contained_aria_control", "tabbable_group"}:
        page.locator("#receipt").evaluate(
            """(node, fault) => {
              node.setAttribute('role', fault === 'contained_aria_control' ? 'button' : 'group');
              if (fault === 'tabbable_group') node.tabIndex = 0;
            }""",
            fault,
        )
    if fault == "outside_runtime":
        if owner_kind == "chrome":
            page.evaluate("document.body.className = ''")
        else:
            page.locator("[data-lf-runtime]").evaluate(
                "node => node.removeAttribute('data-lf-runtime')"
            )
    if fault == "undeclared":
        page.locator("[data-lf-reflow]").evaluate(
            "node => node.removeAttribute('data-lf-reflow')"
        )
    if fault in {"adjacent_control", "contained_control"}:
        page.evaluate(
            """fault => {
              const button = document.createElement('button');
              button.id = 'action';
              button.textContent = 'Act';
              document.querySelector(fault === 'contained_control' ? '#labels' : '#row')
                .append(button);
            }""",
            fault,
        )
    page.evaluate(PAINTED)
    receipt = page.locator("#receipt")
    before = receipt.bounding_box()
    owner_before = page.locator("#row").bounding_box()
    control_before = (
        page.locator("#action").bounding_box()
        if fault == "stationary_control"
        else None
    )
    page.evaluate(
        """fault => {
          document.getElementById('age').textContent = '1m ago';
          const metadata = document.getElementById('age').parentElement;
          if (fault === 'growing_header') metadata.style.paddingBlockStart = '20px';
          if (fault === 'moving_region') document.getElementById('row').style.marginLeft = '6px';
          if (fault === 'escaping_label') metadata.style.paddingInlineStart = '420px';
        }""",
        fault,
    )
    judge_watches()
    assert receipt.bounding_box()["x"] != before["x"]
    if not protected:
        assert page.locator("#row").bounding_box() == owner_before
    if control_before:
        assert page.locator("#action").bounding_box() == control_before
    if protected:
        errors = consume_browser_errors(page, "moved without input")
        assert any(f"{protected} moved without input" in error for error in errors), (
            errors
        )


@pytest.mark.parametrize(
    "fault, protected",
    [
        ("", None),
        ("text_only", "button#action"),
        ("enclosing_text", "button#action"),
        ("enclosing_controls", None),
        ("escaping_outer", "button#action"),
        ("moving_outer", "div#outer"),
        ("undeclared", "button#action"),
        ("outside_runtime", "button#action"),
        ("boxless_region", "button#action"),
        ("moving_region", "div#region"),
        ("growing_region", "p#reading"),
        ("escaping_control", "button#action"),
        ("moving_neighbour", "button#neighbour"),
    ],
)
def test_control_reflow_stays_inside_its_runtime_region(browser, fault, protected):
    """Adaptive commands may repack; their box, outside controls and content may not."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><body class="lf-chrome" style="margin:0;font:12px monospace">'
            '<div id="region" data-lf-reflow="controls" '
            'style="display:flex;align-items:center;gap:8px;width:240px;height:40px">'
            '<span id="hint">Short hint</span><button id="action">More</button></div>'
            '<p id="reading">Read this paragraph.</p><button id="neighbour">Outside</button>'
            "</body>"
        )
    )
    if fault in {
        "enclosing_text",
        "enclosing_controls",
        "escaping_outer",
        "moving_outer",
    }:
        page.locator("#region").evaluate(
            """(region, fault) => {
              const outer = document.createElement('div');
              outer.id = 'outer';
              outer.setAttribute('data-lf-reflow', fault === 'enclosing_text' ? 'text' : 'controls');
              outer.style.cssText = 'width:360px;height:40px';
              if (fault === 'escaping_outer') outer.style.width = '140px';
              region.replaceWith(outer); outer.append(region);
              if (fault === 'moving_outer')
                region.style.cssText += ';position:fixed;left:0;top:0';
            }""",
            fault,
        )
    if fault == "text_only":
        page.locator("#region").evaluate(
            "node => node.setAttribute('data-lf-reflow', 'text')"
        )
    if fault == "undeclared":
        page.locator("#region").evaluate(
            "node => node.removeAttribute('data-lf-reflow')"
        )
    if fault == "outside_runtime":
        page.evaluate("document.body.className = ''")
    if fault == "boxless_region":
        page.locator("#region").evaluate("node => node.style.display = 'contents'")
    page.evaluate(PAINTED)
    before = page.locator("#action").bounding_box()
    region_before = page.locator("#region").bounding_box()
    outer_before = (
        page.locator("#outer").bounding_box()
        if page.locator("#outer").count()
        else None
    )
    page.evaluate(
        """fault => {
          document.getElementById('hint').textContent = 'A longer hint';
          const region = document.getElementById('region');
          if (fault === 'moving_region') region.style.marginLeft = '6px';
          if (fault === 'moving_outer') document.getElementById('outer').style.marginLeft = '6px';
          if (fault === 'growing_region') region.style.height = '60px';
          if (fault === 'escaping_control') region.style.gap = '300px';
          if (fault === 'moving_neighbour')
            document.getElementById('neighbour').style.marginLeft = '6px';
        }""",
        fault,
    )
    judge_watches()
    assert page.locator("#action").bounding_box()["x"] != before["x"]
    if not protected or fault == "moving_outer":
        assert page.locator("#region").bounding_box() == region_before
    if outer_before and not protected:
        assert page.locator("#outer").bounding_box() == outer_before
    if protected:
        errors = consume_browser_errors(page, "moved without input")
        assert any(f"{protected} moved without input" in error for error in errors), (
            errors
        )


CAPPED_METADATA = "".join(
    '<div data-lf-reflow="text" style="display:flex;width:360px;height:30px;align-items:baseline">'
    '<b>You</b><span class="lf-msg-meta" style="display:flex;gap:8px;margin-left:8px">'
    f'<time>just now</time><span id="receipt{n}" style="width:150px">Sent</span>'
    "</span></div>"
    for n in range(6)
)


@pytest.mark.parametrize(
    "motion",
    [
        "",
        "control",
        "resize",
        "hidden",
        "clipped",
        "scroll",
        "sticky",
        "visible_child",
        "revealed",
        "moving_offscreen",
        "withdrawn",
        "withdrawn_with_control",
        "moved_then_withdrawn",
        "moved_then_hidden",
        "moved_then_removed",
    ],
)
def test_metadata_at_the_source_cap_cannot_hide_a_control(browser, motion):
    """Five receipt sources pass only when an omitted control also holds still."""
    rows = CAPPED_METADATA
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    button = (
        '<button id="action" style="font-size:8px;padding:0;width:40px;height:12px;'
        + ("visibility:hidden;" if motion == "hidden" else "")
        + ("margin-top:40px;" if motion == "clipped" else "")
        + ("position:sticky;top:0;" if motion == "sticky" else "")
        + ("visibility:visible;" if motion == "visible_child" else "")
        + (
            "visibility:hidden;position:absolute;left:-9999px;top:220px;"
            if motion == "revealed"
            else ""
        )
        + (
            "position:absolute;left:400px;top:220px;"
            if motion.startswith("moved_then_") or motion == "moving_offscreen"
            else ""
        )
        + '">Act</button>'
    )
    if motion == "clipped":
        button = '<div style="height:10px;overflow:hidden">' + button + "</div>"
    if motion == "visible_child":
        button = '<div style="visibility:hidden">' + button + "</div>"
    if motion == "withdrawn_with_control":
        button += '<button id="survivor" style="position:absolute;left:400px;top:220px;font-size:8px;padding:0;width:40px;height:12px">Stay</button>'
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
            '<!doctype html><body class="lf-chrome" style="margin:0;font:12px monospace">'
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
            for (const entry of list.getEntries()) {
              window.sources.push(entry.sources.map(source => source.node?.id));
              if (motion.startsWith('moved_then_')) {
                const button = document.getElementById('action');
                window.paintedControl = button.getBoundingClientRect().toJSON();
                if (motion === 'moved_then_withdrawn') button.style.display = 'none';
                if (motion === 'moved_then_hidden') button.style.visibility = 'hidden';
                if (motion === 'moved_then_removed') button.remove();
              }
            }
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
          if (motion === 'revealed') {
            button.style.left = '400px'; button.style.visibility = 'visible';
          }
          if (motion === 'moving_offscreen') button.style.left = '1406px';
          if (motion.startsWith('withdrawn')) button.style.display = 'none';
          if (motion === 'withdrawn_with_control')
            document.getElementById('survivor').style.left = '406px';
          if (motion.startsWith('moved_then_')) button.style.left = '406px';
        }""",
        motion,
    )
    judge_watches()
    sources = page.evaluate("window.sources")
    assert len(sources) == 1 and len(sources[0]) == 5, sources
    assert all(source.startswith("receipt") for source in sources[0]), sources
    if motion == "revealed":
        expect(page.locator("#action")).to_be_visible()
        assert page.locator("#action").bounding_box()["x"] == 400
    if motion == "moving_offscreen":
        assert page.locator("#action").bounding_box()["x"] == 1406
    if motion.startswith("withdrawn"):
        assert page.locator("#action").bounding_box() is None
    if motion.startswith("moved_then_"):
        assert page.evaluate("window.paintedControl.x") == 406
        assert page.evaluate("window.paintedControl.width") == 40
    if motion == "moved_then_withdrawn":
        assert page.locator("#action").bounding_box() is None
    if motion == "moved_then_hidden":
        expect(page.locator("#action")).to_be_hidden()
    if motion == "moved_then_removed":
        expect(page.locator("#action")).to_have_count(0)
    if motion in {
        "control",
        "resize",
        "visible_child",
        "moving_offscreen",
        "withdrawn_with_control",
        "moved_then_withdrawn",
        "moved_then_hidden",
        "moved_then_removed",
    }:
        consume_browser_errors(page, "moved without input")


@pytest.mark.parametrize("outer_mode", ["text", "controls"])
@pytest.mark.parametrize("shadow_mode", ["open", "closed"])
@pytest.mark.parametrize("departure", ["", "reparent", "remove"])
def test_nested_shadow_regions_keep_enclosing_guarantees_at_source_cap(
    browser, outer_mode, shadow_mode, departure
):
    """Omitted shadow controls keep the region guarantees under which they painted."""
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><body class="lf-chrome" style="margin:0;font:12px monospace">'
            + CAPPED_METADATA
            + f'<div id="outer" data-lf-reflow="{outer_mode}" style="width:400px;height:80px">'
            '<div id="host" style="width:240px;height:40px"></div></div></body>'
        )
    )
    page.evaluate(
        """mode => {
          window.nestedRoot = document.getElementById('host').attachShadow({mode});
          nestedRoot.innerHTML = '<div id="inner" data-lf-runtime data-lf-reflow="controls" '
            + 'style="width:240px;height:40px;display:flex;align-items:center;gap:8px">'
            + '<span id="hint">Short hint</span><button id="action">More</button></div>';
        }""",
        shadow_mode,
    )
    page.evaluate(PAINTED)
    read = """() => Object.fromEntries(['outer', 'inner', 'action'].map(id => [id,
      (document.getElementById(id) ?? nestedRoot.getElementById(id))
        .getBoundingClientRect().toJSON()]))"""
    before = page.evaluate(read)
    page.evaluate(
        """departure => {
          window.sources = [];
          new PerformanceObserver(list => {
            for (const entry of list.getEntries()) {
              sources.push(entry.sources.map(source => source.node?.id));
              const control = nestedRoot.getElementById('action');
              if (!control) continue;
              window.paintedControl = control.getBoundingClientRect().toJSON();
              if (departure === 'remove') control.remove();
              if (departure === 'reparent') {
                control.style.position = 'fixed';
                control.style.left = paintedControl.x + 'px';
                control.style.top = paintedControl.y + 'px';
                document.body.append(control);
              }
            }
          }).observe({type: 'layout-shift'});
          for (const age of document.querySelectorAll('time')) age.textContent = '1m ago';
          nestedRoot.getElementById('hint').textContent = 'A longer hint';
        }""",
        departure,
    )
    judge_watches()
    sources = page.evaluate("window.sources")
    assert len(sources) == 1 and len(sources[0]) == 5, sources
    assert all(source.startswith("receipt") for source in sources[0]), sources
    assert page.evaluate("window.paintedControl.x") != before["action"]["x"]
    after = page.evaluate(
        """() => Object.fromEntries(['outer', 'inner'].map(id => [id,
          (document.getElementById(id) ?? nestedRoot.getElementById(id))
            .getBoundingClientRect().toJSON()]))"""
    )
    assert after == {key: before[key] for key in after}
    if outer_mode == "text":
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


@pytest.mark.parametrize("surface", ["card", "panel", "inline"])
def test_message_age_may_shift_metadata_but_leaves_the_thread_in_place(
    browser, serve, surface
):
    """Age and receipt may rearrange; the thread and its controls stay put."""
    source = (
        leaf_page(
            "Inline task thread",
            '<h1 id="title">Before the frost</h1><lf-command id="jobs" label="Jobs">'
            '<lf-task id="bracket" status="active" talk>'
            "<strong>Which jobs can share a visit?</strong></lf-task></lf-command>",
        )
        if surface == "inline"
        else ASK_PAGE
    )
    page = open_page(
        browser,
        serve(
            source,
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
    elif surface == "inline":
        surface_root = page.locator(".lf-page-thread[data-lf-runtime]")
    else:
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        surface_root = page.locator(".lf-thread[open]")
    header = surface_root.locator(".lf-msg-head").first
    receipt = header.locator(".lf-msg-sending")
    timestamp = header.locator("time")
    expect(receipt).to_have_text("Sent")
    expect(timestamp).to_have_text("just now")
    # Age changes are news after Chrome's recent-input grace, even when opening the
    # surface and resizing it happened immediately before this clock transition.
    page.wait_for_timeout(600)
    protected = surface_root.locator("b, button, leaf-text, .lf-msg-body")
    boxes = "nodes => nodes.map(node => node.getBoundingClientRect().toJSON())"
    before = protected.evaluate_all(boxes)
    assert before
    owner = surface_root.locator(".lf-thread-root-meta").first
    owner_before = owner.bounding_box()
    receipt.evaluate(
        """receipt => {
          window.ageShifts = [];
          new PerformanceObserver(list => {
            for (const entry of list.getEntries()) {
              for (const source of entry.sources) {
                if (source.node === receipt || receipt.contains(source.node)) {
                  window.ageShifts.push({
                    input: entry.hadRecentInput,
                    before: source.previousRect.toJSON(),
                    after: source.currentRect.toJSON(),
                  });
                }
              }
            }
          }).observe({type: 'layout-shift'});
        }"""
    )
    held = []
    page.route("**/api/state*", lambda route: held.append(route))
    now = datetime.now().astimezone()
    for delta, age in [
        (timedelta(minutes=1), "1m ago"),
        (timedelta(minutes=10), "10m ago"),
        (timedelta(hours=3), "3h ago"),
    ]:
        receipt_before = receipt.bounding_box()
        header_before = header.bounding_box()
        count = page.evaluate("window.ageShifts.length")
        # Advance Leaf's calibrated server clock without changing the browser's
        # monotonic clock: native LayoutShift and frame readings must share time.
        page.evaluate(
            """async now => {
              const clock = await window.__lfRuntimeImport('/runtime/presence.js');
              const {reportPageError} = await window.__lfRuntimeImport('/runtime/layer-client.js');
              clock.observeServerNow(now);
              await clock.tickClock(reportPageError);
            }""",
            (now + delta).isoformat(),
        )
        expect(timestamp).to_have_text(age)
        judge_watches()
        native = page.evaluate("window.ageShifts")[count:]
        assert native and all(not entry["input"] for entry in native)
        assert any(entry["before"]["x"] != entry["after"]["x"] for entry in native)
        assert receipt.bounding_box()["x"] != receipt_before["x"]
        header_after = header.bounding_box()
        assert (header_after["x"], header_after["y"]) == (
            header_before["x"],
            header_before["y"],
        )
        assert owner.bounding_box() == owner_before
        assert protected.evaluate_all(boxes) == before


@pytest.mark.parametrize(
    "fault, protected",
    [
        ("growth", None),
        ("words", "span#words"),
        ("action", "button#action"),
        ("words-hidden", "span#words"),
        ("action-hidden", "button#action"),
    ],
)
def test_reading_and_controls_keep_their_place_inside_a_stationary_parent(
    browser, fault, protected
):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<!doctype html><body style="margin:0">
<div style="width:300px;height:150px;position:relative">
  <span id="words" style="position:absolute;left:10px;top:10px">Read these words.</span>
  <button id="action" style="position:absolute;left:10px;top:50px">Act</button>
  <div id="free" style="position:absolute;left:100px;bottom:0;width:50px;height:20px;background:gray"></div>
</div></body>""")
    )
    page.evaluate(PAINTED)
    page.evaluate(
        """fault => {
      if (fault === 'growth') document.querySelector('#free').style.height = '50px';
      else document.getElementById(fault.split('-')[0]).style.left = '30px';
    }""",
        fault,
    )
    page.evaluate(PAINTED)
    if fault.endswith("-hidden"):
        page.locator("#" + fault.split("-")[0]).evaluate(
            "node => node.style.visibility = 'hidden'"
        )
    judge_watches()
    if protected:
        consume_browser_errors(page, f"{protected} moved without input")


def test_an_unpainted_roundtrip_keeps_the_visible_control_in_place(browser):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<!doctype html><body>
<button id="action" style="position:absolute;left:10px;top:50px">Act</button></body>""")
    )
    page.evaluate(PAINTED)
    page.evaluate("""() => {
      const action = document.querySelector('#action');
      const box = action.getBoundingClientRect;
      action.getBoundingClientRect = function() {
        action.getBoundingClientRect = box;
        action.style.left = '30px';
        const transient = box.call(action);
        action.style.left = '10px';
        return transient;
      };
    }""")
    page.evaluate(PAINTED)
    judge_watches()


@pytest.mark.parametrize("axis", [None, "left", "top"])
def test_scrolling_a_sticky_owner_does_not_credit_its_controls_local_motion(
    browser, axis
):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<!doctype html><body style="margin:0">
<div id="scroller" style="height:300px;overflow:auto;width:400px">
  <div style="height:50px"></div>
  <header style="position:sticky;top:0;height:50px">
    <button id="action" style="position:absolute;left:10px;top:10px">Act</button>
  </header>
  <div style="height:700px">Following reading</div>
</div></body>""")
    )
    page.evaluate("document.querySelector('#scroller').scrollTop = 70")
    page.evaluate(PAINTED)
    page.evaluate(
        """axis => {
      document.querySelector('#scroller').scrollTop = 76;
      if (axis) document.querySelector('#action').style[axis] = '30px';
    }""",
        axis,
    )
    page.evaluate(PAINTED)
    judge_watches()
    if axis:
        consume_browser_errors(page, "button#action moved without input")


def test_typing_keeps_its_field_when_chrome_reports_only_larger_sources(browser):
    rows = "".join(
        f'<div style="position:absolute;left:10px;top:{100 + i * 80}px;'
        f'width:400px;height:60px;background:gray" data-large>Source {i}</div>'
        for i in range(6)
    )
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto(
        "data:text/html,"
        + quote(
            """<!doctype html><body style="margin:0">
<textarea id="field" style="position:absolute;left:10px;top:10px;width:40px;height:12px;font:8px monospace;padding:0"></textarea>"""
            + rows
            + """<script>field.addEventListener('beforeinput', () => {
          for (const node of document.querySelectorAll('[data-large]')) node.style.left = '80px';
          field.style.left = '16px';
        });</script></body>"""
        )
    )
    page.evaluate(PAINTED)
    page.locator("#field").fill("a")
    judge_watches()
    consume_browser_errors(page, "typing in textarea#field moved textarea#field")


def test_a_retained_control_keeps_its_pose_when_a_new_sticky_owner_adopts_it(browser):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<!doctype html><body style="margin:0">
<button id="action" style="position:absolute;left:10px;top:10px">Act</button>
<p id="other" style="position:absolute;left:10px;top:150px">Following reading</p></body>""")
    )
    page.evaluate(PAINTED)
    page.evaluate("""() => {
      const owner = document.createElement('header');
      owner.style.cssText = 'position:sticky;top:0;margin-left:40px;width:200px;height:100px';
      owner.append(document.querySelector('#action'));
      document.body.append(owner);
      // Chrome treats the reparented control as inserted; another changed reading
      // admits this painted frame, whose retained landmarks still need their history.
      document.querySelector('#other').style.left = '30px';
    }""")
    page.evaluate(PAINTED)
    judge_watches()
    errors = take_browser_errors(page)
    assert any("button#action moved without input" in error for error in errors), errors
    assert all("moved without input" in error for error in errors), errors


@pytest.mark.parametrize("decoration", ["aria-hidden", "presentation", None])
def test_decorative_media_is_not_an_independent_reading_landmark(browser, decoration):
    declaration = 'aria-hidden="true"' if decoration == "aria-hidden" else ""
    role = 'role="presentation"' if decoration == "presentation" else ""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(f"""<!doctype html><body style="margin:0">
<p>Stationary reading.</p>
<div {declaration}>
  <svg id="picture" {role} style="position:absolute;left:10px;top:100px;width:100px;height:60px">
    <rect width="100" height="60" fill="blue" />
  </svg>
</div></body>""")
    )
    page.evaluate(PAINTED)
    page.locator("#picture").evaluate("node => node.style.left = '30px'")
    page.evaluate(PAINTED)
    judge_watches()
    if decoration is None:
        consume_browser_errors(page, "svg#picture moved without input")
