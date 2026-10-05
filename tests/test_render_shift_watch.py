"""The browser fixture fails the layout shifts the "Stability" rule forbids
(`shift_watch.js`): a shift without input, and typing that carries its field."""

from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import pytest
from leaf.render_checks import rendered
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


def paint(page):
    """Let Chrome paint before sampling native layout shifts."""
    page.evaluate(PAINTED)
    page.screenshot()


def field_page(browser, key=""):
    page = browser.new_page()
    page.goto("data:text/html," + quote(FIELD))
    paint(page)
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
              if (fault === 'escaping_outer') {
                const action = region.querySelector('#action').getBoundingClientRect();
                outer.style.width = `${action.right - region.getBoundingClientRect().left + 1}px`;
              }
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
    action_after = page.locator("#action").bounding_box()
    assert action_after["x"] != before["x"]
    if fault == "escaping_outer":
        assert (
            before["x"] + before["width"] <= outer_before["x"] + outer_before["width"]
        )
        assert (
            action_after["x"] + action_after["width"]
            > outer_before["x"] + outer_before["width"]
        )
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
    page.evaluate("""() => {
      const opener = document.createElement('button');
      opener.id = 'open-slide'; opener.textContent = 'Open'; document.body.append(opener);
      opener.addEventListener('click', () => {
        window.slideMotion = document.getElementById('foot').animate(
          [{ transform: 'translateX(-200px)' }, { transform: 'none' }], 3000);
        slideMotion.playbackRate = 0;
        slideMotion.currentTime = 150;
      });
    }""")
    paint(page)
    page.locator("#open-slide").click()
    assert page.evaluate("slideMotion.playState") == "running"
    page.locator("#field").fill("a")
    page.locator("#field").fill("ab")
    page.evaluate(
        "() => { slideMotion.playbackRate = 1; slideMotion.finish(); return slideMotion.finished; }"
    )
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


@pytest.mark.parametrize("work_ms", [30, 300], ids=["ordinary", "ten-times-slower"])
def test_an_input_owns_its_counted_rendering_until_it_settles(browser, serve, work_ms):
    """Counted input work can cross frames; its completion ends movement credit."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Counted input rendering",
                '<button id="press">Move the control</button><div id="above"></div>'
                '<button id="control">Keep this control usable</button>',
            )
        ),
    )
    page.evaluate(
        """async work => {
      const {nextFrame} = await window.__lfRuntimeImport('/runtime/rendering.js');
      const above = document.querySelector('#above');
      document.querySelector('#press').addEventListener('click', () => {
        let turn = 0;
        const move = () => {
          // Real work delays native paint; counted completion remains outstanding.
          const until = performance.now() + work;
          while (performance.now() < until) {}
          above.style.height = `${++turn * 20}px`;
          if (turn < 4) nextFrame(move);
        };
        nextFrame(move);
      }, {once:true});
    }""",
        work_ms,
    )
    control = page.locator("#control")
    before = control.bounding_box()["y"]
    page.locator("#press").click()
    rendered(page)
    assert control.bounding_box()["y"] == pytest.approx(before + 80, abs=1)
    judge_watches()
    assert page.lf_errors == []

    # A later passive move has the same native input in its history, but none
    # of the counted work that input began remains outstanding.
    control.evaluate("node => node.style.marginTop = '40px'")
    rendered(page)
    judge_watches()
    consume_browser_errors(page, "button#control moved without input")


def test_shift_judgement_waits_for_paint_instead_of_a_time_cap(browser):
    """A held native frame keeps judgment pending; release still reports the fault."""
    page = field_page(browser)
    page.evaluate("""() => {
      const nativeFrame = window.lfWatchPlatform.frame;
      const held = [];
      window.lfWatchPlatform.frame = callback => { held.push(callback); return 0; };
      window.releaseFrames = () => {
        window.lfWatchPlatform.frame = nativeFrame;
        for (const callback of held.splice(0)) nativeFrame(callback);
      };
      document.getElementById('above').style.height = '40px';
      window.shiftJudged = false;
      window.lfShiftsJudged().then(() => window.shiftJudged = true);
      // This callback proves the former 500ms fallback would have run, without
      // assuming the machine completes any work within a particular duration.
      setTimeout(() => window.pastFormerCap = true, 600);
    }""")
    try:
        page.wait_for_function("window.pastFormerCap === true", polling=100)
        assert page.evaluate("window.shiftJudged") is False
    finally:
        page.evaluate("window.releaseFrames()")
    page.wait_for_function("window.shiftJudged === true", polling=100)
    consume_browser_errors(page, "textarea#field moved without input by (0, 40)px")


@pytest.mark.parametrize(
    "when",
    [
        "already-hidden",
        "hidden-during-drain",
        "resize-during-drain",
        "cssom-during-drain",
    ],
)
def test_a_hidden_frame_judges_existing_records_without_awaiting_paint(browser, when):
    page = field_page(browser)
    page.set_viewport_size({"width": 900, "height": 600})
    page.evaluate(
        """when => {
      const style = document.createElement('style');
      style.textContent = '@media(max-width:600px){iframe{display:none}}';
      document.head.append(style);
      const frame = document.createElement('iframe');
      if (when === 'already-hidden') frame.style.display = 'none';
      frame.srcdoc = '<!doctype html><body><button>Hidden control</button></body>';
      document.body.append(frame);
    }""",
        when,
    )
    page.wait_for_function(
        "document.querySelector('iframe').contentDocument?.readyState === 'complete'"
    )
    frame = page.frames[1]
    frame.evaluate("""() => {
      const nativeFrame = window.lfWatchPlatform.frame;
      const held = [];
      window.lfWatchPlatform.frame = callback => { held.push(callback); return 0; };
      window.restoreFrame = () => {
        window.lfWatchPlatform.frame = nativeFrame;
        for (const callback of held.splice(0)) nativeFrame(callback);
      };
      window.hiddenJudged = false;
      window.lfShiftsJudged().then(() => window.hiddenJudged = true);
    }""")
    try:
        if when != "already-hidden":
            assert frame.evaluate("window.hiddenJudged") is False
            if when == "resize-during-drain":
                page.set_viewport_size({"width": 500, "height": 600})
            elif when == "cssom-during-drain":
                page.evaluate(
                    "document.querySelector('style').sheet.insertRule('iframe{display:none}', 0)"
                )
            else:
                page.evaluate("document.querySelector('iframe').style.display = 'none'")
        frame.wait_for_function("window.hiddenJudged === true", polling=100)
        assert frame.evaluate("window.frameElement.checkVisibility()") is False
    finally:
        frame.evaluate("window.restoreFrame()")


@pytest.mark.parametrize(
    "detached", [False, True], ids=["targetless", "target-removed"]
)
@pytest.mark.parametrize("method", ["play", "reverse"])
def test_motion_instrumentation_preserves_targetless_native_effects(
    browser, detached, method
):
    """A native effect may have no target and still be played or reversed."""
    page = field_page(browser)
    assert page.evaluate(
        """async ({detached, method}) => {
          const effect = new KeyframeEffect(detached ? field : null,
            [{transform:'none'},{transform:'translateX(20px)'}],100);
          const animation = new Animation(effect, document.timeline);
          if(detached){
            animation.play();animation.playbackRate=0;animation.currentTime=0;
            await new Promise(done=>lfWatchPlatform.frame(()=>lfWatchPlatform.frame(done)));
            effect.target=null;animation.playbackRate=1;
          }
          animation[method]();
          const running = animation.playState === 'running';
          animation.finish();
          await animation.finished;
          return running && animation.playState === 'finished';
        }""",
        {"detached": detached, "method": method},
    )
    judge_watches()


def test_native_shift_evidence_survives_a_controlled_timer_clock(browser):
    """Advancing product timers cannot put native paint outside the sensor ledger."""
    context = browser.new_context()
    context.clock.set_fixed_time(datetime(2026, 10, 3, tzinfo=UTC).timestamp())
    page = field_page(context)
    page.clock.run_for(5000)
    page.evaluate("document.getElementById('above').style.height = '40px'")
    judge_watches()
    consume_browser_errors(page, "textarea#field moved without input by (0, 40)px")


def test_a_native_resize_seals_typing_before_its_layout_even_with_controlled_time(
    browser,
):
    """Resize owns its new viewport layout; subsequent passive carry still fails."""
    context = browser.new_context()
    context.clock.set_fixed_time(datetime(2026, 10, 3, tzinfo=UTC).timestamp())
    page = context.new_page()
    page.set_viewport_size({"width": 900, "height": 600})
    page.goto(
        "data:text/html,"
        + quote(
            FIELD.replace(
                '<div id="above">',
                '<div style="width:60%;margin:auto"><div id="above">',
            )
            + "</div>"
        )
    )
    paint(page)
    page.clock.run_for(5000)
    page.locator("#field").fill("Typed before resizing")
    before = page.locator("#field").bounding_box()
    page.set_viewport_size({"width": 500, "height": 600})
    paint(page)
    assert page.locator("#field").bounding_box()["x"] < before["x"] - 40
    judge_watches()
    assert take_browser_errors(page) == []
    page.evaluate("document.getElementById('above').style.height = '40px'")
    judge_watches()
    consume_browser_errors(page, "textarea#field moved without input by (0, 40)px")


def test_a_resize_cannot_own_a_passive_shift_painted_before_dispatch(browser):
    """Delayed health sampling cannot let a later resize excuse existing paint."""
    page = field_page(browser)
    page.set_viewport_size({"width": 900, "height": 600})
    page.locator("#field").fill("x")
    judge_watches()
    page.evaluate("""() => {
      const original = lfWatchPlatform.frame;
      const held = [];
      window.paintNative = () => new Promise(done => original(() => original(done)));
      lfWatchPlatform.frame = callback => held.push(callback);
      window.releaseHealth = () => {
        lfWatchPlatform.frame = original;
        held.splice(0).forEach(callback => original(callback));
      };
      window.queuedPaint = [];
      new PerformanceObserver(list => queuedPaint.push(...list.getEntries().map(entry => entry.startTime)))
        .observe({type:'layout-shift'});
    }""")
    try:
        page.evaluate("paintNative()")
        page.evaluate("above.style.height='40px'")
        page.evaluate("paintNative()")
        page.wait_for_function("queuedPaint.length > 0", polling=100)
        page.set_viewport_size({"width": 500, "height": 600})
        page.evaluate("paintNative()")
    finally:
        page.evaluate("releaseHealth()")
    judge_watches()
    consume_browser_errors(page, "textarea#field moved without input by (0, 40)px")


# A context script, so it registers ahead of the page's health sensors and a held
# `resize` reaches no listener until it is dispatched again. Playwright does not promise
# that order, so the script records whether the shift watch was already installed.
HOLD_RESIZE = """window.resizeHoldFirst = window.lfShiftsJudged === undefined;
addEventListener("resize", (event) => {
  if (!window.resizesHeld || !event.isTrusted) return;
  event.stopImmediatePropagation();
  resizesHeld.push(event.type);
});"""


def test_a_resize_owns_its_layout_before_its_event_dispatches(browser):
    """Chrome lays out a resized viewport before it dispatches `resize`, and on a busy
    machine a layout-shift record can reach the observer in between, its fresh pose
    already at the new size. The size is the input; the event is late news of it.
    Holding both the event and the health frames puts the record in that gap: the
    column's reflow gives Chrome a record, and the button it does not name is carried."""
    context = browser.new_context(viewport={"width": 900, "height": 600})
    context.add_init_script(HOLD_RESIZE)
    page = context.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><body style="margin:0">'
            '<p style="width:60%;margin:auto">A column the width follows.</p>'
            '<button style="display:block;width:120px;margin-left:auto">Right</button>'
        )
    )
    paint(page)
    assert page.evaluate("resizeHoldFirst")
    page.evaluate("""() => {
      const original = lfWatchPlatform.frame;
      const frames = [];
      window.paintNative = () => new Promise(done => original(() => original(done)));
      lfWatchPlatform.frame = callback => frames.push(callback);
      window.resizesHeld = [];
      window.recorded = 0;
      new PerformanceObserver(list => { recorded += list.getEntries().length; })
        .observe({type: "layout-shift"});
      window.release = () => {
        lfWatchPlatform.frame = original;
        frames.splice(0).forEach(callback => original(callback));
        const events = resizesHeld.splice(0);
        window.resizesHeld = null;
        events.forEach(type => dispatchEvent(new Event(type)));
      };
    }""")
    # The health frame already requested runs before the resize, so none runs between
    # the resized layout and its record.
    page.evaluate("paintNative()")
    try:
        page.set_viewport_size({"width": 500, "height": 600})
        page.evaluate("paintNative()")
        # The resized layout's record has reached every observer, the watch's first,
        # while its event waits.
        page.wait_for_function("recorded > 0", polling=100)
        assert page.evaluate("resizesHeld.length") == 1
    finally:
        page.evaluate("release()")
    judge_watches()
    assert take_browser_errors(page) == []
    # A passive move after the resize still fails.
    page.evaluate("document.querySelector('button').style.marginTop = '40px'")
    judge_watches()
    consume_browser_errors(page, "moved without input by (0, 40)px")


# News three frames after a press, as a reply lands just after a click: the page adopts
# a server reading. A stand-in for the runtime never settles its rendering, so the
# press's rendering is still open when the news lands. What moves the line is the
# page's `data-motion`: the news growing a box above it (none), the news beginning a
# bar's slide above it (`news`), or the press beginning that slide, which runs on past
# news that moves nothing (`press`). The height slide is a conservative sensor
# boundary: native height-induced sibling flow has no exact translation proof.
# The matched marginTop arm proves press/news ownership with supported displacement.
NEWS = """<!doctype html><body style="margin:0">
<script data-lf-entry>document.currentScript.lfRenderingSettled = () => false;</script>
<button id="press">Press</button>
<div id="bar"></div><div id="above"></div><div id="below">Below.</div>
<script>
  const frames = (n, then) => requestAnimationFrame(() => n > 1 ? frames(n - 1, then) : then());
  const motion = () => document.body.dataset.motion;
  const slide = () => document.body.dataset.translation === 'true'
    ? document.getElementById("below").animate(
        [{ marginTop: "0px" }, { marginTop: "300px" }], { duration: 400, fill: "forwards" })
    : document.getElementById("bar").animate(
        [{ height: "0px" }, { height: "300px" }], { duration: 400, fill: "forwards" });
  document.getElementById("press").addEventListener("pointerdown", (event) => {
    if (motion() === "press") slide();
    const until = performance.now() + Number(document.body.dataset.work);
    while (performance.now() < until) {}
    frames(3, () => {
      document.body.dataset.inputHeld = String(!document.querySelector('script[data-lf-entry]').lfRenderingSettled());
      document.body.setAttribute("data-lf-reading", "news");
      if (motion() === "news") slide();
      if (!motion()) document.getElementById("above").style.height = "40px";
      document.body.dataset.newsFromTrustedPress = String(event.isTrusted);
    });
  });
</script>"""


def news_page(browser, motion="", work_ms=65, *, translation=False):
    page = browser.new_page()
    page.goto("data:text/html," + quote(NEWS))
    # The stand-in's page has presented, so its shifts are judged.
    page.evaluate("document.body.setAttribute('data-lf-presented', '')")
    page.evaluate(
        "args => { document.body.dataset.motion = args.motion; document.body.dataset.work = args.work; document.body.dataset.translation = String(args.translation); }",
        {"motion": motion, "work": work_ms, "translation": translation},
    )
    page.locator("#press").click()
    page.wait_for_function("document.body.dataset.newsFromTrustedPress !== undefined")
    # News follows the trusted press while its declared rendering is still held.
    # Execution speed and Chrome's recent-input duration do not decide ownership.
    assert page.evaluate("document.body.dataset.newsFromTrustedPress") == "true"
    assert page.evaluate("document.body.dataset.inputHeld") == "true"
    return page


@pytest.mark.parametrize("motion", ["", "news"], ids=["grows a box", "begins a slide"])
@pytest.mark.parametrize("work_ms", [65, 650], ids=["ordinary", "ten-times-slower"])
def test_news_just_after_a_press_moves_nothing(browser, motion, work_ms):
    page = news_page(browser, motion, work_ms)
    judge_watches()
    consume_browser_errors(page, "div#below moved without input")


def test_native_height_sibling_flow_without_displacement_proof_is_reported(browser):
    """The sensor reports genuine native flow it cannot attribute, rather than guessing."""
    page = news_page(browser, "press")
    assert page.evaluate("parseFloat(getComputedStyle(bar).height)") > 0
    assert (
        page.locator("#below").bounding_box()["y"]
        > page.locator("#bar").bounding_box()["y"]
    )
    judge_watches()
    consume_browser_errors(page, "div#below moved without input")


@pytest.mark.parametrize("motion", ["press", "news"])
def test_sampled_native_translation_distinguishes_press_from_news(browser, motion):
    """Identical native motion survives news only when the trusted press began it."""
    page = news_page(browser, motion, translation=True)
    page.wait_for_function("parseFloat(getComputedStyle(below).marginTop) > 0")
    judge_watches()
    if motion == "press":
        assert take_browser_errors(page) == []
    else:
        consume_browser_errors(page, "div#below moved without input")


@pytest.mark.parametrize("motion", ["none", "scroll", "stalled", "finite", "unbounded"])
def test_completed_input_does_not_own_an_effects_unrelated_passive_motion(
    browser, motion
):
    """An effect's lifetime cannot extend its creator's whole-page input credit."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<!doctype html><body><button id="attach">Attach moving surface</button>
<div id="source" style="height:80px;width:200px;overflow:auto"><div style="height:400px">Scroll source</div></div>
<div id="attachment" style="position:absolute;left:250px;top:130px">Moving attachment</div>
<textarea id="field" style="position:absolute;left:250px;top:250px"></textarea>
<script>attach.addEventListener('click',()=>{
  const options=window.motionKind==='scroll'
    ? {timeline:new ScrollTimeline({source:source,axis:'y'}),duration:'auto',fill:'both'}
    : {duration:1000000,iterations:window.motionKind==='unbounded'?Infinity:1,fill:'both'};
  window.attachmentMotion=attachment.animate(
    [{transform:'translateY(0px)'},{transform:'translateY(-300px)'}],options);
  if(window.motionKind==='stalled')attachmentMotion.playbackRate=0;
});</script></body>""")
    )
    paint(page)
    if motion != "none":
        page.evaluate("kind=>window.motionKind=kind", motion)
        page.locator("#attach").click()
        assert page.evaluate("attachmentMotion.playState") == "running"
    judge_watches()
    assert take_browser_errors(page) == []
    before = page.locator("#field").bounding_box()
    page.evaluate("field.style.left='330px'")
    paint(page)
    after = page.locator("#field").bounding_box()
    assert after["x"] - before["x"] == 80
    judge_watches()
    consume_browser_errors(page, "textarea#field moved without input by (80, 0)px")


@pytest.mark.parametrize("local_motion", [False, True])
def test_completed_input_keeps_only_its_native_attachment_displacement(
    browser, local_motion
):
    """A retained scroll effect carries its field without owning the field's own move."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<!doctype html><body><button id="attach">Attach moving surface</button>
<div id="source" style="height:80px;width:200px;overflow:auto"><div style="height:400px">Scroll source</div></div>
<div id="attachment" style="position:absolute;left:250px;top:130px"><textarea id="field"></textarea></div>
<svg id="evidence" aria-hidden="true" style="position:absolute;left:0;top:400px;width:300px;height:30px;background:gray"></svg>
<script>attach.addEventListener('click',()=>{
  window.attachmentMotion=attachment.animate(
    [{transform:'translateY(0px)'},{transform:'translateY(-320px)'}],
    {timeline:new ScrollTimeline({source:source,axis:'y'}),duration:'auto',fill:'both'});
});</script></body>""")
    )
    paint(page)
    page.locator("#attach").click()
    assert page.evaluate("attachmentMotion.playState") == "running"
    judge_watches()
    assert take_browser_errors(page) == []
    before = page.locator("#field").bounding_box()
    page.evaluate(
        "carry=>{source.scrollTop=20;if(carry)field.style.marginLeft='80px';evidence.style.left='20px'}",
        local_motion,
    )
    paint(page)
    after = page.locator("#field").bounding_box()
    assert page.evaluate("source.scrollTop") == 20
    assert after["y"] - before["y"] == pytest.approx(-20, abs=0.5)
    assert after["x"] - before["x"] == (80 if local_motion else 0)
    judge_watches()
    if local_motion:
        consume_browser_errors(page, "textarea#field moved without input")
    else:
        assert take_browser_errors(page) == []


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
    owner = header.locator("xpath=..")
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
    paint(page)
    page.locator("#field").fill("a")
    page.screenshot()
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


def test_a_wheel_gesture_does_not_own_later_passive_carry(browser):
    page = field_page(browser)
    page.evaluate("""() => addEventListener('wheel', () => {
      document.querySelector('#above').style.height = '20px';
    }, {once:true})""")
    page.mouse.wheel(0, 100)
    page.wait_for_function("document.querySelector('#above').style.height === '20px'")
    paint(page)
    judge_watches()
    page.evaluate(PAINTED)
    page.evaluate("document.querySelector('#above').style.height = '40px'")
    page.screenshot()
    judge_watches()
    consume_browser_errors(page, "textarea#field moved without input")


@pytest.mark.parametrize("subject", ["background", "older", "current"])
@pytest.mark.parametrize("reverse", [False, True])
def test_native_modality_keeps_its_exposed_controls_in_place(
    browser, serve, subject, reverse
):
    from render_harness import leaf_page, open_page

    page = open_page(
        browser,
        serve(
            leaf_page(
                "Native layers",
                """
<button id="background" style="position:absolute;left:10px;top:10px">Background</button>
<dialog id="first" style="width:250px;height:150px"><button style="position:absolute;left:10px;top:10px">First action</button></dialog>
<dialog id="second" style="width:250px;height:150px"><button style="position:absolute;left:10px;top:10px">Second action</button></dialog>
""",
            )
        ),
    )
    page.evaluate(
        """reverse => {
      const dialogs = [document.querySelector('#first'), document.querySelector('#second')];
      if (reverse) dialogs.reverse();
      dialogs[0].showModal(); dialogs[1].showModal();
      dialogs[0].querySelector('button').id = 'older';
      dialogs[1].querySelector('button').id = 'current';
    }""",
        reverse,
    )
    page.screenshot()
    page.locator("#" + subject).evaluate("node => node.style.left = '30px'")
    page.screenshot()
    judge_watches()
    if subject == "current":
        consume_browser_errors(page, "button#current moved without input")


@pytest.mark.parametrize("sticky", [False, True])
@pytest.mark.parametrize("carry", [False, True])
def test_typing_keeps_native_scroll_ownership_without_crediting_local_carry(
    browser, sticky, carry
):
    position = "position:sticky;top:0" if sticky else ""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(f"""<!doctype html><body style="margin:0">
<div id="scroller" style="height:300px;overflow:auto;width:400px">
<div style="height:150px"></div>
<header style="{position};height:50px">
<textarea id="field" style="position:relative;top:0;display:block" rows="1"></textarea>
</header><div style="height:700px">Following reading</div></div>
<p id="evidence" style="position:absolute;left:10px;top:400px">Painted source</p>
<script>field.addEventListener('beforeinput', () => {{
  scroller.scrollTop += 6;
  {'field.style.top = "20px"; evidence.style.left = "30px";' if carry else ""}
}})</script></body>""")
    )
    page.evaluate("amount => scroller.scrollTop = amount", 170 if sticky else 100)
    page.screenshot()
    page.locator("#field").fill("a")
    page.screenshot()
    judge_watches()
    if carry:
        consume_browser_errors(page, "typing in textarea#field moved textarea#field")


@pytest.mark.parametrize("carry", [False, True])
def test_typing_root_scroll_keeps_a_fixed_field_but_not_its_local_carry(browser, carry):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(f"""<!doctype html><body style="height:2000px;margin:0">
<textarea id="field" style="position:fixed;left:10px;top:10px" rows="1"></textarea>
<p id="evidence" style="position:fixed;left:10px;top:200px">Painted source</p>
<script>field.addEventListener('beforeinput', () => {{
  scrollBy(0,20);
  evidence.style.left = "30px";
  {'field.style.left = "30px";' if carry else ""}
}})</script></body>""")
    )
    page.evaluate("scrollTo(0,100)")
    page.screenshot()
    before = page.locator("#field").bounding_box()
    page.locator("#field").fill("a")
    page.screenshot()
    assert page.evaluate("scrollY") == 120
    if not carry:
        assert page.locator("#field").bounding_box() == before
    judge_watches()
    if carry:
        consume_browser_errors(page, "typing in textarea#field moved textarea#field")


@pytest.mark.parametrize(
    "fault", ["", "portal_x", "portal_y", "anchor_x", "anchor_y", "declared_unused"]
)
@pytest.mark.parametrize("transform", ["none", "scale(.8)", "scale(.8) rotate(10deg)"])
def test_native_anchor_scroll_retains_local_motion_proof(browser, fault, transform):
    field_style = "position:fixed;position-anchor:--target;left:calc(anchor(left) + 100px);top:calc(anchor(top) + 10px)"
    if fault == "declared_unused":
        field_style = "position:fixed;position-anchor:--target;left:100px;top:50px"
    change = {
        "": "",
        "portal_x": 'field.style.left="calc(anchor(left) + 110px)"',
        "portal_y": 'field.style.top="calc(anchor(top) + 20px)"',
        "anchor_x": 'target.style.marginLeft="10px"',
        "anchor_y": 'target.style.marginTop="70px"',
        "declared_unused": 'field.style.top="40px"',
    }[fault]
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(f"""<!doctype html><body style="margin:0">
<div style="transform:{transform};transform-origin:left top">
<div id="scroller" style="height:140px;width:300px;overflow:auto">
<div style="width:600px;height:300px"><div id="target" style="anchor-name:--target;margin-top:60px;width:70px;height:30px">The target</div></div></div></div>
<textarea id="field" style="{field_style}"></textarea>
<p id="evidence" style="position:absolute;left:10px;top:400px">Independent painted source</p>
<script>field.addEventListener('beforeinput',()=>{{scroller.scrollLeft+=20;scroller.scrollTop+=20;evidence.style.left='30px';{change}}})</script></body>""")
    )
    page.evaluate("scroller.scrollLeft=20;scroller.scrollTop=20")
    paint(page)
    before = page.locator("#field").bounding_box()
    page.locator("#field").fill("a")
    page.screenshot()
    page.evaluate(PAINTED)
    after = page.locator("#field").bounding_box()
    assert page.evaluate("[scroller.scrollLeft,scroller.scrollTop]") == [40, 40]
    assert before != after
    judge_watches()
    errors = take_browser_errors(page)
    if fault:
        assert any(
            "typing in textarea#field moved textarea#field" in error for error in errors
        ), (fault, before, after, errors)
    else:
        assert errors == [], (before, after, errors)


@pytest.mark.parametrize(
    "fault", ["", "passive", "finished", "local", "ancestor_x", "ancestor_y"]
)
def test_owned_animation_retains_local_motion_through_next_gesture(browser, fault):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<!doctype html><body style="margin:0">
<button id="open">Open</button><button id="other">Another gesture</button>
<div id="panel" style="margin-left:350px"><textarea id="field"></textarea><p>Retained reading</p></div>
<script>function move(){window.motion=panel.animate([{marginLeft:'350px'},{marginLeft:'0px'}],{duration:700,fill:'forwards'});motion.playbackRate=0;motion.currentTime=150}document.getElementById('open').addEventListener('click',move)</script>""")
    )
    paint(page)
    if fault == "passive":
        page.evaluate("move()")
    else:
        page.locator("#open").click()
    page.wait_for_function("window.motion && motion.playState === 'running'")
    if fault == "local":
        page.evaluate(
            "field.addEventListener('beforeinput',()=>field.style.marginLeft='10px')"
        )
    page.locator("#field").fill("Type during opening")
    page.locator("#other").click()
    page.evaluate(PAINTED)
    assert page.evaluate("motion.playState") == "running"
    if fault == "ancestor_x":
        page.evaluate("panel.style.position='relative';panel.style.left='80px'")
    if fault == "ancestor_y":
        page.evaluate("panel.style.marginTop='80px'")
    page.evaluate(
        "() => { motion.playbackRate = 1; motion.finish(); return motion.finished; }"
    )
    page.screenshot()
    page.evaluate(PAINTED)
    if fault == "finished":
        judge_watches()
        assert not take_browser_errors(page)
        page.evaluate("field.style.marginLeft='10px'")
        page.screenshot()
        page.evaluate(PAINTED)
    judge_watches()
    errors = take_browser_errors(page)
    if fault:
        assert any(
            (
                "typing in textarea#field moved textarea#field"
                if fault == "local"
                else "textarea#field moved without input"
            )
            in error
            for error in errors
        ), errors
    else:
        assert not errors, errors


@pytest.mark.parametrize("mode", ["static", "fallback"])
def test_unused_anchor_cannot_bank_an_earlier_scroll(browser, mode):
    page = browser.new_page()
    style = (
        "position:static;position-anchor:--target;top:calc(anchor(top) + 10px)"
        if mode == "static"
        else "position:fixed;position-anchor:--target;--fixed:200px;top:var(--fixed,calc(anchor(top) + 10px));left:0px"
    )
    page.goto(
        "data:text/html,"
        + quote(
            """<!doctype html><body style="margin:0"><div id="scroller" style="height:140px;width:300px;overflow:auto"><div style="height:400px"><div id="target" style="anchor-name:--target;margin-top:60px;width:70px;height:30px">Target</div></div></div><textarea id="field" style="FIELD_STYLE"></textarea><p id="evidence" style="position:absolute;left:10px;top:400px">Paint evidence</p></body>""".replace(
                "FIELD_STYLE", style
            )
        )
    )
    paint(page)
    before = page.locator("#field").bounding_box()
    page.evaluate("scroller.scrollTop=20")
    paint(page)
    assert page.locator("#field").bounding_box() == before
    change = "field.style.marginTop='-20px'"
    page.evaluate(
        "field.addEventListener('beforeinput',()=>{"
        + change
        + ";evidence.style.left='30px'})"
    )
    page.locator("#field").fill("a")
    page.screenshot()
    page.evaluate(PAINTED)
    judge_watches()
    errors = take_browser_errors(page)
    assert any("typing in textarea#field moved textarea#field" in e for e in errors), (
        before,
        page.locator("#field").bounding_box(),
        errors,
    )


GESTURE_MOTION = """<!doctype html><body style="margin:0"><button id="open">Open</button><button id="other">Another gesture</button><div id="panel" style="margin-left:350px"><textarea id="field"></textarea><button id="control">Retained control</button><p>Retained reading</p></div><script>function slide(){window.motion=panel.animate([{transform:'translateX(-200px)'},{transform:'none'}],{duration:900,fill:'forwards'});motion.playbackRate=0;motion.currentTime=150}document.getElementById('open').addEventListener('click',slide)</script></body>"""


def gesture_motion_page(browser):
    page = browser.new_page()
    page.goto("data:text/html," + quote(GESTURE_MOTION))
    paint(page)
    return page


def test_immediate_native_opening_and_typing(browser):
    page = gesture_motion_page(browser)
    page.evaluate(
        "document.getElementById('open').addEventListener('keydown',event=>{if(event.key==='a'){slide();field.focus()}})"
    )
    page.locator("#open").focus()
    page.keyboard.press("a")
    page.keyboard.insert_text("b")
    page.evaluate(
        "() => { motion.playbackRate = 1; motion.finish(); return motion.finished; }"
    )
    page.screenshot()
    page.evaluate(PAINTED)
    judge_watches()
    assert not take_browser_errors(page)


@pytest.mark.parametrize("fault", ["late_unowned", "local"])
def test_gesture_close_does_not_own_future_or_local_motion(browser, fault):
    page = gesture_motion_page(browser)
    page.locator("#open").click()
    page.locator("#other").click()
    paint(page)
    if fault == "late_unowned":
        page.evaluate(
            "() => { motion.playbackRate = 1; motion.finish(); return motion.finished; }"
        )
        paint(page)
        page.evaluate(
            "window.late = panel.animate([{marginTop:'0px'},{marginTop:'80px'}],{duration:250,fill:'forwards'})"
        )
        page.evaluate("() => late.finished")
    else:
        assert page.evaluate("motion.playState") == "running"
        page.evaluate("control.style.marginTop='80px'")
        page.evaluate(
            "() => { motion.playbackRate = 1; motion.finish(); return motion.finished; }"
        )
    page.screenshot()
    page.evaluate(PAINTED)
    judge_watches()
    errors = take_browser_errors(page)
    assert any(e.startswith("button#control moved without input") for e in errors), (
        errors
    )


@pytest.mark.parametrize("destination", ["window", "page"])
@pytest.mark.parametrize("guard_mode", ["typing", "passive"])
@pytest.mark.parametrize("fault", ["", "holder_x", "holder_y", "child_x", "child_y"])
def test_real_floating_plane_retains_local_motion(
    browser, serve, fault, guard_mode, destination
):
    """Owned plane changes excuse their placement, never extra holder/child motion.

    The two planes belong to the shared placement factory. An editing presenter need
    not use both: its following policy is independent of this guard's attribution.
    """
    source = leaf_page(
        "Plane evidence",
        '<p id="subject" style="position:fixed;left:100px;top:280px;'
        'width:80px;height:30px;margin:0">Exact subject</p>'
        '<div id="holder" style="visibility:hidden;position:fixed;width:220px;height:90px;'
        'padding:12px;border:1px solid;box-sizing:border-box;background:white">'
        '<textarea id="field" style="display:block;width:160px;height:36px;'
        'box-sizing:border-box;resize:none"></textarea></div>'
        '<p id="evidence" style="position:fixed;left:10px;top:440px;'
        'width:300px;height:30px;margin:0">Paint evidence</p>',
        layout=None,
    )
    page = open_page(browser, serve(source))
    resized(page, 900, 600)
    # An unplaced surface has dimensions for its solver, but no reading to move.
    paint(page)
    expect(page.locator("#field")).to_be_hidden()
    initial = "page" if destination == "window" else "window"
    first = page.evaluate(
        """async initial => {
          const module = await window.__lfRuntimeImport('/runtime/annotation-overlay/floating.js');
          const ui = await module.floatingUi();
          const holder = document.querySelector('#holder');
          const subject = document.querySelector('#subject');
          let plane = initial, answer;
          const selection = () => module.floatingSelections().find(s => s.floating === holder);
          const owner = module.floatingPlacement({floating:holder, update:()=>void place()});
          async function place() {
            owner.begin();
            const reference = {
              contextElement:subject,
              getBoundingClientRect:()=>plane === 'page'
                ? subject.getBoundingClientRect() : new DOMRect(410,150,80,30),
            };
            const placed = await owner.position(ui.computePosition, reference,
              {placement:'right-start',middleware:[]}, ()=>plane, subject);
            if (placed) {owner.stand(placed); answer = placed;}
          }
          owner.watch(subject, subject, ui.autoUpdate);
          await place();
          holder.style.removeProperty('visibility');
          const original = selection();
          window.planeControl = {
            to:async destination => {plane=destination; await place();},
            read:() => {
              const current = selection();
              return {plane:current.plane, sameSubject:current.subject===original.subject,
                sameAnchor:current.anchor===original.anchor, sameTenure:current.tenure===original.tenure,
                expected:{x:answer.x,y:answer.y}};
            },
          };
          return planeControl.read();
        }""",
        initial,
    )
    assert first["plane"] == initial
    field, holder = page.locator("#field"), page.locator("#holder")
    field.fill("Keep these words.")
    paint(page)
    judge_watches()
    assert take_browser_errors(page) == []
    if guard_mode == "passive":
        page.keyboard.press("Shift")
        paint(page)
    before, holder_before = field.bounding_box(), holder.bounding_box()
    page.evaluate("window.beforeField=document.querySelector('#field')")
    page.evaluate("""()=>{
      window.nativePlaneEntries=[];
      new PerformanceObserver(list=>nativePlaneEntries.push(...list.getEntries().map(e=>({
        at:e.startTime,sources:e.sources.map(s=>({kind:s.node?.nodeName,
          previous:s.previousRect.toJSON(),current:s.currentRect.toJSON()}))
      })))).observe({type:'layout-shift'});
    }""")
    page.evaluate(
        """([fault,destination])=>{
          window.planeChanges=0;
          const holder=document.querySelector('#holder');
          let previous=holder.dataset.lfPlane;
          new MutationObserver(()=>{
            if(holder.dataset.lfPlane===previous) return;
            previous=holder.dataset.lfPlane;
            planeChanges++;
            if(previous===destination) {
              if(fault==='holder_x') holder.style.transform='translateX(80px)';
              if(fault==='holder_y') holder.style.transform='translateY(80px)';
              if(fault==='child_x') document.querySelector('#field').style.transform='translateX(80px)';
              if(fault==='child_y') document.querySelector('#field').style.transform='translateY(80px)';
              // Transform-only faults need a native paint signal; this extra source
              // cannot establish the independently asserted field displacement.
              if(fault) document.querySelector('#evidence').style.marginLeft='30px';
            }
          }).observe(holder,{attributes:true,attributeFilter:['data-lf-plane']});
        }""",
        [fault, destination],
    )
    if guard_mode == "typing":
        field.evaluate(
            "(node,destination)=>node.addEventListener('beforeinput',()=>void planeControl.to(destination),{once:true})",
            destination,
        )
        page.keyboard.insert_text("x")
    else:
        page.evaluate("destination=>planeControl.to(destination)", destination)
    page.wait_for_function(
        "destination=>planeControl.read().plane===destination", arg=destination
    )
    paint(page)
    state = page.evaluate("planeControl.read()")
    assert state["sameSubject"] and state["sameAnchor"] and state["sameTenure"], state
    assert page.evaluate("planeChanges") == 1
    judge_watches()
    errors = take_browser_errors(page)
    entries = page.evaluate("nativePlaneEntries")
    assert entries, (fault, guard_mode, destination, "no Chrome paint admission")
    after, holder_after = field.bounding_box(), holder.bounding_box()
    assert page.evaluate("beforeField===document.querySelector('#field')")
    assert after["width"] == before["width"]
    assert after["height"] == before["height"]
    assert holder_after["width"] == holder_before["width"]
    assert holder_after["height"] == holder_before["height"]
    assert state["expected"] != {axis: holder_before[axis] for axis in ["x", "y"]}
    for axis in ["x", "y"]:
        shifted = 80 if fault.endswith("_" + axis) else 0
        assert holder_after[axis] == pytest.approx(
            state["expected"][axis] + (shifted if fault.startswith("holder") else 0),
            abs=1,
        )
        assert after[axis] == pytest.approx(
            state["expected"][axis] + before[axis] - holder_before[axis] + shifted,
            abs=1,
        )
    expected = (
        "typing in textarea#field moved textarea#field"
        if guard_mode == "typing"
        else "textarea#field moved without input"
    )
    if fault:
        assert any(expected in error for error in errors), (fault, errors)
    else:
        assert errors == [], errors


# Native containing blocks, not DOM ancestry, decide which overflow clips apply.
@pytest.mark.parametrize(
    "outer,inner,field,hit,painted,delta",
    [
        (
            "width:100px;height:100px;overflow:hidden",
            "",
            "position:fixed;left:200px;top:200px",
            True,
            True,
            20,
        ),
        (
            "width:100px;height:100px;overflow:hidden;transform:translateX(0)",
            "",
            "position:fixed;left:200px;top:200px",
            False,
            False,
            20,
        ),
        (
            "width:100px;height:100px;overflow:hidden;contain:layout",
            "",
            "position:fixed;left:200px;top:200px",
            False,
            False,
            20,
        ),
        (
            "width:100px;height:100px;overflow:hidden;filter:blur(0)",
            "",
            "position:fixed;left:200px;top:200px",
            False,
            False,
            20,
        ),
        (
            "width:100px;height:100px;overflow:hidden;opacity:0",
            "",
            "position:fixed;left:200px;top:200px",
            True,
            False,
            20,
        ),
        (
            "position:relative;width:500px;height:400px",
            "width:100px;height:100px;overflow:hidden",
            "position:absolute;left:200px;top:200px",
            True,
            True,
            20,
        ),
        (
            "position:relative;width:500px;height:400px",
            "position:relative;width:100px;height:100px;overflow:hidden",
            "position:absolute;left:200px;top:200px",
            False,
            False,
            20,
        ),
        (
            "position:relative;width:100px;height:100px;overflow:hidden",
            "position:absolute;width:100px;height:100px;overflow:hidden",
            "position:fixed;left:200px;top:200px",
            True,
            True,
            20,
        ),
        (
            "width:100px;height:100px;overflow:hidden;transform:scale(2);transform-origin:0 0",
            "",
            "position:fixed;left:75px;top:20px",
            True,
            True,
            3,
        ),
        (
            "width:100px;height:100px;overflow:visible;contain:paint",
            "",
            "position:fixed;left:200px;top:200px",
            False,
            False,
            20,
        ),
        (
            "width:100px;height:100px;overflow:visible;contain:strict",
            "",
            "position:fixed;left:200px;top:200px",
            False,
            False,
            20,
        ),
        (
            "width:100px;height:100px;overflow:visible;content-visibility:auto",
            "",
            "position:fixed;left:200px;top:200px",
            False,
            False,
            20,
        ),
        (
            "position:relative;width:100px;height:100px;overflow-x:visible;overflow-y:clip",
            "",
            "position:absolute;left:200px;top:20px",
            True,
            True,
            20,
        ),
        (
            "position:relative;width:100px;height:100px;overflow-x:clip;overflow-y:visible",
            "",
            "position:absolute;left:20px;top:200px",
            True,
            True,
            20,
        ),
        (
            "position:relative;width:100px;height:0;overflow-x:clip;overflow-y:visible",
            "",
            "position:absolute;left:20px;top:200px",
            True,
            True,
            20,
        ),
    ],
    ids=[
        "viewport-fixed",
        "transformed",
        "contained",
        "filtered",
        "transparent",
        "absolute-outer",
        "absolute-inner",
        "escaped-absolute",
        "scaled",
        "paint-contained",
        "strict-contained",
        "content-visibility",
        "visible-x",
        "visible-y",
        "zero-height-x",
    ],
)
def test_native_clipping_preserves_only_painted_carry(
    browser, serve, outer, inner, field, hit, painted, delta
):
    source = leaf_page(
        "Native clipping",
        f'<div id="outer" style="{outer}"><div id="inner" style="{inner}"><textarea id="field" style="{field};width:14px;height:20px"></textarea></div></div><div id="evidence" style="position:absolute;left:10px;top:400px;width:300px;height:30px;background:red"></div>',
        layout=None,
    )
    page = open_page(browser, serve(source))
    paint(page)
    state = page.evaluate("""async()=>{
      const field=document.querySelector('#field'), box=field.getBoundingClientRect();
      const geometry=await window.__lfRuntimeImport('/runtime/geometry.js');
      return {hit:document.elementFromPoint(box.x+3,box.y+3)===field,
        shown:!!geometry.shownRect(field,new Map()),
        opacity:field.checkVisibility({checkOpacity:true})};
    }""")
    assert state == {"hit": hit, "shown": hit, "opacity": painted or hit is False}
    before = page.locator("#field").bounding_box()
    page.evaluate(
        """delta=>{
      window.nativeClipEntries=[];
      new PerformanceObserver(list=>nativeClipEntries.push(...list.getEntries())).observe({type:'layout-shift'});
      document.querySelector('#field').style.marginLeft=delta+'px';
      document.querySelector('#evidence').style.marginLeft='40px';
    }""",
        delta,
    )
    page.screenshot()
    judge_watches()
    errors = take_browser_errors(page)
    assert page.evaluate("nativeClipEntries.length")
    after = page.locator("#field").bounding_box()
    assert after["x"] - before["x"] == (6 if delta == 3 else delta)
    if painted:
        assert any("textarea#field moved without input" in error for error in errors), (
            errors
        )
    else:
        assert errors == [], errors


@pytest.mark.parametrize("mode", ["typing", "passive"])
def test_new_anchor_relation_cannot_credit_scroll_before_activation(browser, mode):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            """<!doctype html><body style="margin:0"><div id="scroller" style="height:140px;width:300px;overflow:auto"><div style="height:400px"><div id="target" style="anchor-name:--target;margin-top:60px;width:70px;height:30px">Target</div></div></div><textarea id="field" style="position:fixed;position-anchor:--target;left:0;top:200px"></textarea><div id="evidence" style="position:absolute;left:10px;top:400px;width:300px;height:60px;background:red"></div></body>"""
        )
    )
    paint(page)
    before = page.locator("#field").bounding_box()
    page.evaluate("scroller.scrollTop=20")
    paint(page)
    assert page.locator("#field").bounding_box() == before
    page.evaluate("field.style.top='calc(anchor(top) + 160px)'")
    paint(page)
    assert page.locator("#field").bounding_box() == before
    if mode == "typing":
        page.evaluate(
            "field.addEventListener('beforeinput',()=>{field.style.marginTop='-20px';evidence.style.left='50px'})"
        )
        page.locator("#field").fill("a")
    else:
        page.keyboard.press("Shift")
        paint(page)
        page.evaluate("()=>{field.style.marginTop='-20px';evidence.style.left='50px'}")
    page.screenshot()
    page.evaluate(PAINTED)
    judge_watches()
    errors = take_browser_errors(page)
    assert page.locator("#field").bounding_box()["y"] == before["y"] - 20
    expected = (
        "typing in textarea#field moved textarea#field"
        if mode == "typing"
        else "textarea#field moved without input"
    )
    assert any(expected in error for error in errors), errors


@pytest.mark.parametrize("fault", ["", "holder", "child"])
def test_real_factory_invalidates_nonwindow_and_stopped_tenure(browser, serve, fault):
    source = leaf_page(
        "Floating tenure",
        """<p id="subject" style="position:fixed;left:100px;top:100px;width:40px;height:20px;margin:0">Anchor</p><div id="host" style="position:fixed;left:0;top:0;width:600px;height:500px"><div id="holder" style="position:fixed;left:140px;top:100px;width:100px;height:60px"><textarea id="field" style="width:80px;height:20px"></textarea></div></div><div id="evidence" style="position:fixed;left:10px;top:400px;width:300px;height:60px;background:red"></div>""",
        layout=None,
    )
    page = open_page(browser, serve(source))
    initial = page.locator("#holder").bounding_box()
    state = page.evaluate("""async()=>{
      const module=await window.__lfRuntimeImport('/runtime/annotation-overlay/floating.js'); const ui=await module.floatingUi();const holder=document.querySelector('#holder'),subject=document.querySelector('#subject'),host=document.querySelector('#host'); let plane='page';
      const selected=()=>module.floatingSelections().find(s=>s.floating===holder);
      const owner=module.floatingPlacement({floating:holder,update:()=>void place()});
      async function place(){owner.begin();const answer=await owner.position(ui.computePosition,subject,{placement:'right-start',middleware:[]},()=>plane,subject);if(answer)owner.stand(answer);}
      owner.watch(subject,subject,ui.autoUpdate);await place(); const first=selected();
      if(!first||first.plane!=='page')throw Error('First placement was not supported page');
      const original=holder.getBoundingClientRect();host.style.transform='translateX(0)';await place();const unsupported=selected();const nested=holder.getBoundingClientRect();const nativeNonwindow=holder.offsetParent===host;
      host.style.removeProperty('transform');plane='window';await place();const second=selected();
      if(!second)throw Error('Supported window placement missing');
      owner.stop();const stopped=selected();owner.watch(subject,subject,ui.autoUpdate);await place();const third=selected();
      window.reviewOwner=owner;window.reviewPlace=place;
      return {absentUnsupported:unsupported===undefined,unchanged:original.x===nested.x&&original.y===nested.y&&original.width===nested.width&&original.height===nested.height,nativeNonwindow,window:second.plane,newTenure:first.tenure!==second.tenure,sameSubject:first.subject===second.subject,sameAnchor:first.anchor===second.anchor,absentStopped:stopped===undefined,newStoppedTenure:second.tenure!==third.tenure,sameStoppedSubject:second.subject===third.subject};
    }""")
    assert state == {
        "absentUnsupported": True,
        "unchanged": True,
        "nativeNonwindow": True,
        "window": "window",
        "newTenure": True,
        "sameSubject": True,
        "sameAnchor": True,
        "absentStopped": True,
        "newStoppedTenure": True,
        "sameStoppedSubject": True,
    }, state
    paint(page)
    assert page.locator("#holder").bounding_box() == initial
    judge_watches()
    assert take_browser_errors(page) == []
    page.keyboard.press("Shift")
    paint(page)
    if fault:
        page.evaluate(
            """fault=>{document.querySelector(fault==='holder'?'#holder':'#field').style.marginLeft='80px';document.querySelector('#evidence').style.marginLeft='40px'}""",
            fault,
        )
        page.screenshot()
    judge_watches()
    errors = take_browser_errors(page)
    if fault:
        assert any("textarea#field moved without input" in error for error in errors), (
            errors
        )
    else:
        assert errors == [], errors


@pytest.mark.parametrize("mode", ["pointer", "keyboard"])
@pytest.mark.parametrize("fault", ["", "late", "synthetic"])
def test_native_activation_owns_its_release_not_later_motion(browser, mode, fault):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            """<!doctype html><body style="margin:0"><button id="open" style="position:fixed;left:400px;top:0">Open</button><div id="above"></div><textarea id="field"></textarea><script>document.querySelector('#open').addEventListener('click',()=>document.querySelector('#above').style.height='40px')</script></body>"""
        )
    )
    paint(page)
    before = page.locator("#field").bounding_box()
    if fault == "synthetic":
        page.locator("#open").evaluate("n=>n.click()")
    else:
        if mode == "pointer":
            button = page.locator("#open").bounding_box()
            page.mouse.move(button["x"] + 5, button["y"] + 5)
            page.mouse.down()
        else:
            page.locator("#open").focus()
            page.keyboard.down("Space")
        paint(page)
        if mode == "pointer":
            page.mouse.up()
        else:
            page.keyboard.up("Space")
    paint(page)
    judge_watches()
    errors = take_browser_errors(page)
    assert page.locator("#field").bounding_box()["y"] - before["y"] == 40
    if fault == "synthetic":
        assert any("textarea#field moved without input" in e for e in errors), errors
    else:
        assert errors == [], errors
        if fault == "late":
            paint(page)
            page.evaluate("document.querySelector('#above').style.height='80px'")
            paint(page)
            judge_watches()
            errors = take_browser_errors(page)
            assert any("textarea#field moved without input" in e for e in errors), (
                errors
            )


@pytest.mark.parametrize("pressed", [True, False])
def test_native_pointer_motion_owns_only_an_active_drag(browser, pressed):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            """<!doctype html><body style="margin:0"><button id="grip" style="position:fixed;left:400px;top:0">Drag</button><div id="above"></div><textarea id="field"></textarea></body>"""
        )
    )
    paint(page)
    page.mouse.move(405, 5)
    if pressed:
        page.mouse.down()
    paint(page)
    page.evaluate(
        "document.addEventListener('pointermove',()=>document.querySelector('#above').style.height='40px')"
    )
    page.mouse.move(410, 10)
    paint(page)
    judge_watches()
    errors = take_browser_errors(page)
    assert page.locator("#field").bounding_box()["y"] == 40
    if pressed:
        assert errors == [], errors
        page.mouse.up()
    else:
        assert any("textarea#field moved without input" in e for e in errors), errors


@pytest.mark.parametrize(
    ("fault", "close"),
    [(False, False), (True, False), (True, True)],
    ids=["stationary", "active-carry", "closed-carry"],
)
def test_a_delayed_native_frame_keeps_the_typing_origins_camera(browser, fault, close):
    """Frame association precedes its delayed pose, but typing keeps its own origin.

    Hold callbacks with their actual native frame timestamps, then type before they
    sample. The declared rendering stays open across a real paint checkpoint. An
    ancestor changes paint without moving the field, so the field's later comparison
    still needs that ancestor's original camera; the matched carry must still fail,
    including when typing closes after the fault paints but before judgment drains.
    """
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<!doctype html><body style="margin:0">
<script data-lf-entry>document.currentScript.lfRenderingSettled = () => false;</script>
<div id="bar"><div id="above"></div><textarea id="field"></textarea></div>
<p id="evidence" style="position:absolute;top:200px">Paint evidence</p>
<script>field.addEventListener('beforeinput', () => {
  window.typingObservedAt = lfWatchPlatform.performance.now();
  bar.style.opacity = '.99';
});</script></body>""")
    )
    page.evaluate("document.body.setAttribute('data-lf-presented', '')")
    paint(page)
    page.evaluate("""() => {
      const frame = lfWatchPlatform.frame;
      window.delayedSamples = [];
      window.holdSamples = () => {
        lfWatchPlatform.frame = callback =>
          frame(time => delayedSamples.push([callback, time]));
      };
      window.releaseSamples = () => {
        lfWatchPlatform.frame = frame;
        for (const [callback, time] of delayedSamples.splice(0)) callback(time);
      };
      holdSamples();
      window.cameraPaints = [];
      new PerformanceObserver(list => cameraPaints.push(...list.getEntries()))
        .observe({type: 'layout-shift'});
    }""")
    try:
        page.wait_for_function("delayedSamples.length >= 2", polling=50)
        page.locator("#field").fill("Keep this field's place.")
        assert page.evaluate(
            "delayedSamples.every(([, start]) => start < typingObservedAt)"
        )
    finally:
        page.evaluate("releaseSamples()")
    paint(page)
    page.evaluate("lfShiftsJudged()")
    if close:
        page.evaluate("holdSamples()")
        page.wait_for_function("delayedSamples.length >= 2", polling=50)
    try:
        page.evaluate(
            """fault => {
              cameraPaints.length = 0;
              window.cameraFaultAt = lfWatchPlatform.performance.now();
              bar.style.opacity = '.9';
              evidence.style.marginLeft = '20px';
              if (fault) above.style.height = '40px';
            }""",
            fault,
        )
        paint(page)
        page.wait_for_function(
            "cameraPaints.some(entry => entry.startTime >= cameraFaultAt)", polling=50
        )
        if close:
            page.keyboard.press("Shift")
    finally:
        if close:
            page.evaluate("releaseSamples()")
    paint(page)
    judge_watches()
    expect(page.locator("#field")).to_have_value("Keep this field's place.")
    assert page.locator("#field").bounding_box()["y"] == (40 if fault else 0)
    if fault:
        consume_browser_errors(page, "typing in textarea#field moved textarea#field")


@pytest.mark.parametrize("fault", [False, True])
def test_long_held_native_anchor_keeps_complete_history(browser, fault):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<!doctype html><body style="margin:0">
<div id="scroller" style="height:140px;width:300px;overflow:auto">
  <div id="ancestor" style="height:500px">
    <div id="target" style="anchor-name:--target;margin-top:60px;width:70px;height:30px">Target</div>
  </div>
</div>
<textarea id="field" style="position:fixed;position-anchor:--target;top:calc(anchor(top) + 10px);left:400px"></textarea>
<p id="evidence" style="position:absolute;left:10px;top:400px">Paint evidence</p></body>""")
    )
    paint(page)
    initial = page.locator("#field").bounding_box()
    page.evaluate(
        "() => {window.nativeEntries=[];new PerformanceObserver(list=>nativeEntries.push(...list.getEntries().map(e=>e.startTime))).observe({type:'layout-shift'})}"
    )
    # The anchor stays put across completed evidence-retirement checkpoints.
    # Each checkpoint drains native observer records; no elapsed window defines it.
    page.evaluate("ancestor.style.opacity='.99'")
    page.evaluate(PAINTED)
    page.evaluate("() => window.lfShiftsJudged()")
    page.evaluate("ancestor.style.opacity='.9'")
    paint(page)
    page.evaluate(
        "fault=>{scroller.scrollTop=20;if(fault){field.style.marginTop='10px';evidence.style.left='30px'}}",
        fault,
    )
    paint(page)
    judge_watches()
    errors = take_browser_errors(page)
    after = page.locator("#field").bounding_box()
    assert after["y"] == initial["y"] - 20 + (10 if fault else 0)
    assert after["x"] == initial["x"]
    assert after["width"] == initial["width"] and after["height"] == initial["height"]
    if fault:
        assert page.evaluate("nativeEntries.length") > 0
        assert any("textarea#field moved without input" in e for e in errors), errors
        assert all("moved without input" in error for error in errors), errors
    else:
        assert not errors, errors


@pytest.mark.parametrize("fault", ["", "child", "target"])
@pytest.mark.parametrize("fill", ["none", "forwards", "replay"])
def test_owned_native_finish_records_the_applied_endpoint(browser, fault, fill):
    """Native cleanup cannot erase final translation or credit a child's own move."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<!doctype html><body style="margin:0">
<button id="open">Open</button><button id="other">Another gesture</button>
<div id="panel" style="margin-left:350px"><textarea id="field"></textarea><p>Retained words</p></div>
<svg id="evidence" aria-hidden="true" style="position:absolute;left:0;top:300px;width:400px;height:60px;background:gray"></svg>
<script>document.getElementById('open').addEventListener('click',()=>{
  if(window.endpointReplay){panel.style.marginLeft='430px';motion.play();}
  else window.motion=panel.animate([{marginLeft:'550px'},{marginLeft:'350px'}],{duration:700,fill:window.endpointFill});
  motion.playbackRate=0;motion.currentTime=150;
  motion.finished.then(()=>queueMicrotask(()=>motion.cancel()));
})</script></body>""")
    )
    paint(page)
    page.evaluate(
        "fill => window.endpointFill = fill", "none" if fill == "replay" else fill
    )
    page.locator("#open").click()
    page.evaluate(PAINTED)
    if fill == "replay":
        page.evaluate("motion.playbackRate=1;motion.finish()")
        paint(page)
        assert page.evaluate("motion.playState") == "idle"
        page.evaluate("window.endpointReplay=true")
        page.locator("#open").click()
        paint(page)
    page.locator("#other").click()
    paint(page)
    page.evaluate("""() => {
      window.finishPaint=[];
      new PerformanceObserver(list=>finishPaint.push(...list.getEntries().map(entry=>entry.startTime)))
        .observe({type:'layout-shift',buffered:false});
    }""")
    before = page.evaluate(
        """fault => {
      const origin = window.endpointReplay ? 430 : 350;
      const before={state:motion.playState,field:field.getBoundingClientRect().toJSON(),
        translation:parseFloat(getComputedStyle(panel).marginLeft)-origin};
      if(fault === 'child')field.style.marginLeft='80px';
      if(fault === 'target')panel.style.marginLeft=(origin+80)+'px';
      evidence.style.left='20px';
      motion.playbackRate=1;
      motion.finish();
      return before;
    }""",
        fault,
    )
    assert before["state"] == "running"
    assert before["translation"] > 1
    paint(page)
    page.wait_for_function("finishPaint.length > 0")
    after = page.locator("#field").bounding_box()
    assert (
        abs(
            after["x"]
            - before["field"]["x"]
            + before["translation"]
            - (80 if fault else 0)
        )
        < 0.5
    )
    assert page.evaluate("motion.playState") == "idle"
    judge_watches()
    errors = take_browser_errors(page)
    if fault:
        assert any("textarea#field moved without input" in error for error in errors), (
            errors
        )
        assert all("moved without input" in error for error in errors), errors
    else:
        assert not errors, errors
