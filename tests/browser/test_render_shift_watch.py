"""The browser fixture fails the layout shifts the "Stability" rule forbids
(`shift_watch.js`): a shift without input, and typing that carries its field."""

from datetime import UTC, datetime
from html import escape
from urllib.parse import quote

import pytest
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_harness import (
    INPUT_WORK_WATCH_SOURCE,
    WATCH_PLATFORM_SOURCE,
    consume_browser_errors,
    holding,
    is_problem,
    judge_watches,
    leaf_page,
    open_page,
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


def held_stretch(page):
    """Idle frames the sensor keeps unchanged readings for, on a CPU as slow as a CI
    runner's, so a credited move that follows is compared from a held frame
    (`shift_watch.js`, "Unchanged frames") with the frame timing CI has."""
    page.context.new_cdp_session(page).send(
        "Emulation.setCPUThrottlingRate", {"rate": 6}
    )
    page.evaluate(
        """count => new Promise((done) => {
          const next = () => (--count ? requestAnimationFrame(next) : done());
          requestAnimationFrame(next);
        })""",
        60,
    )


def field_page(browser, key=""):
    page = browser.new_page()
    page.goto("data:text/html," + quote(FIELD))
    paint(page)
    page.evaluate("key => { document.body.dataset.key = key; }", key)
    return page


def within(node, place):
    """Whether the watch's name for a node places it at `place` or inside it, as it
    names a text node (`#text in button#control`) or a node in a shadow tree
    (`div.cm-line in shadow of leaf-text#field`)."""
    return node == place or node.endswith((f" in {place}", f" of {place}"))


def moved_within(place, by=None):
    """A report that a node at `place` or inside it moved without input, `by` far
    where given (`is_problem`)."""
    return lambda problem: (
        problem.code == "moved-without-input"
        and within(problem.values["node"], place)
        and by in (None, problem.values["by"])
    )


def names_move(errors, node, *, typing_in=None):
    """Whether the watch reported a node at `node` or inside it moving: without input,
    or carried by typing in the field `typing_in`."""
    expected = (
        {"code": "typing-moved", "field": typing_in, "node": node}
        if typing_in
        else moved_within(node)
    )
    return any(is_problem(error, expected) for error in errors)


def shift_evidence(error):
    """Every reported credit is explained by the terms its owner accepted."""
    evidence = error.values["evidence"]
    assert evidence["comparisons"], evidence
    for comparison in evidence["comparisons"]:
        for axis in ["left", "top"]:
            for kind in ["scroll", "animation"]:
                terms = comparison[kind + "_terms"]
                assert all(term["branch"] and term["owner"] for term in terms), terms
                assert sum(
                    term["amount"] for term in terms if term["axis"] == axis
                ) == pytest.approx(comparison[kind + "_credit"][axis]), comparison
            assert comparison["residual"][axis] == pytest.approx(
                comparison["observed"][axis]
                - comparison["scroll_credit"][axis]
                - comparison["animation_credit"][axis]
            ), comparison
    return evidence


def test_typing_that_carries_its_field_fails_at_the_last_keystroke(browser):
    page = field_page(browser, "carry")
    page.locator("#field").fill("a")
    judge_watches()
    errors = consume_browser_errors(
        page,
        {"code": "typing-moved", "field": "textarea#field", "node": "textarea#field"},
    )
    evidence = shift_evidence(errors[0])
    assert evidence["kind"] == "typing"
    comparison = evidence["comparisons"][0]
    assert comparison["observed"] == {"left": 0, "top": 59}
    assert comparison["scroll_credit"] == {"left": 0, "top": 0}
    assert comparison["animation_credit"] == {"left": 0, "top": 0}
    assert comparison["residual"] == comparison["observed"]
    assert comparison["before"]["at"] < comparison["after"]["at"]


def test_typing_may_grow_its_field(browser):
    page = field_page(browser, "grow")
    page.locator("#field").fill("a")
    judge_watches()


def test_native_document_replacement_preserves_sensor_input_ownership(browser):
    """A parser replacement retains sensors, including their input listeners.

    A real click owns its movement; later passive movement and lost words still fail.
    The same realm replaces its document twice; application listeners retire normally.
    """
    page = browser.new_page()
    page.goto("data:text/html,<!doctype html><body>")
    page.evaluate("""() => {
      window.retiredClicks = 0;
      addEventListener('click', () => retiredClicks++);
    }""")
    source = """<!doctype html><body style="margin:0">
      <button id="press">Move the control</button><div id="above"></div>
      <button id="control">Keep this control usable</button><textarea id="field"></textarea>
      <script>
        document.querySelector('#press').addEventListener('click', () => {
          window.inputSource = lfInputWork.current()?.event.type ?? null;
          document.querySelector('#above').style.height = '40px';
        });
      </script>"""
    for _ in range(2):
        page.evaluate(
            "source => { document.open(); document.write(source); document.close(); }",
            source,
        )
    paint(page)
    page.locator("#press").click()
    paint(page)
    assert page.evaluate("inputSource") == "click"
    assert page.evaluate("retiredClicks") == 0
    assert page.locator("#above").bounding_box()["height"] == 40
    judge_watches()
    assert page.lf_errors == []

    page.locator("#control").evaluate("node => { node.style.marginTop = '30px'; }")
    paint(page)
    judge_watches()
    consume_browser_errors(page, {"code": "moved-without-input"})

    page.locator("#field").fill("Half a thought")
    page.locator("#field").evaluate("node => { node.value = ''; }")
    judge_watches()
    consume_browser_errors(page, {"code": "words-left-screen"})


@pytest.mark.parametrize("nested", [False, True])
def test_hidden_opaque_frames_drain_without_waiting_for_suppressed_paint(
    browser, nested
):
    """The owner is visible only to the driver, including an ancestor above a child."""
    child = '<p id="reading">An isolated document.</p>'
    embedded = f'<iframe sandbox="allow-scripts" srcdoc="{escape(child, quote=True)}"></iframe>'
    if nested:
        embedded = f'<iframe hidden srcdoc="{escape(embedded, quote=True)}"></iframe>'
    else:
        embedded = embedded.replace("<iframe ", "<iframe hidden ", 1)
    page = browser.new_page()
    page.goto("data:text/html," + quote(f"<!doctype html><body>{embedded}</body>"))
    frame = page.frame_locator("iframe")
    if nested:
        frame = frame.frame_locator("iframe")
    expect(frame.locator("#reading")).to_have_text("An isolated document.")
    assert frame.locator("#reading").evaluate(
        "() => !document.hidden && window.frameElement === null"
    )
    judge_watches()

    page.locator("iframe").evaluate("element => { element.hidden = false; }")
    expect(frame.locator("#reading")).to_be_visible()
    frame.locator("#reading").evaluate(PAINTED)
    judge_watches()

    # Hide an ancestor after the driver starts a drain whose native paint is held.
    # Completion must use refreshed visibility rather than the initial true value.
    page.evaluate("""() => {
      window.hiddenDuringDrain = false;
      window.hideDrainingFrame = event => {
        if (event.data !== 'sensor-draining') return;
        document.querySelector('iframe').hidden = true;
        hiddenDuringDrain = true;
      };
      addEventListener('message', hideDrainingFrame);
    }""")
    frame.locator("#reading").evaluate("""() => {
      const nativeFrame = lfWatchPlatform.frame;
      window.restoreFrames = () => { lfWatchPlatform.frame = nativeFrame; };
      lfWatchPlatform.frame = () => {
        if (window.lfWatchJudgement && !lfWatchJudgement.complete)
          top.postMessage('sensor-draining', '*');
      };
    }""")
    reading = frame.locator("#reading").element_handle()
    child_frame = reading.owner_frame()
    reading.dispose()
    try:
        judge_watches()
        assert page.evaluate("hiddenDuringDrain") is True
    finally:
        child_frame.evaluate("restoreFrames()")
        page.evaluate("removeEventListener('message', hideDrainingFrame)")


def test_hidden_returns_protect_only_the_resumed_reading(browser, serve):
    """The return boundary ends at presentation, including two rapid absences."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Return boundary",
                '<div id="above"></div><p id="reading">Read here.</p>',
            )
        ),
    )
    held = []
    page.route("**/api/news", lambda route: held.append(route))
    page.evaluate("""async () => {
      window.returnBoundary = await window.__lfCheckApi();
      window.returnVisibility = 'visible';
      Object.defineProperty(document, 'visibilityState', {
        configurable: true, get: () => window.returnVisibility,
      });
      window.setReturnVisibility = value => {
        window.returnVisibility = value;
        document.dispatchEvent(new Event('visibilitychange'));
      };
      setReturnVisibility('hidden'); setReturnVisibility('visible');
      document.getElementById('above').style.height = '40px';
    }""")
    paint(page)
    judge_watches()
    page.evaluate("""() => {
      returnBoundary.completeReadingReturn(returnBoundary.readingReturn());
      // Before its completion frames run, another absence opens another return.
      setReturnVisibility('hidden'); setReturnVisibility('visible');
    }""")
    paint(page)
    page.evaluate("document.getElementById('above').style.height = '80px'")
    paint(page)
    judge_watches()
    page.evaluate(
        "returnBoundary.completeReadingReturn(returnBoundary.readingReturn())"
    )
    paint(page)
    page.evaluate("document.getElementById('above').style.height = '120px'")
    paint(page)
    judge_watches()
    consume_browser_errors(page, {"code": "moved-without-input"})


@pytest.mark.parametrize("cause", ["typing", "passive"])
def test_editcontext_growth_keeps_input_credit_with_its_actual_field(
    browser, serve, cause
):
    """Native EditContext growth is typing; carrying its field still violates stability."""
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/153.0.0.0 Mobile Safari/537.36"
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Native typing geometry", '<h1>Edit a reply</h1><div id="above"></div>'
            )
        ),
        context=context,
    )
    page.evaluate(
        """cause => {
      const field = document.createElement('leaf-text'); field.id = 'field';
      field.style.cssText = 'display:block;width:300px';
      document.querySelector('main').append(field);
      field.addEventListener('input', () => {
        const source = lfInputWork.current();
        window.nativeGeometryInput = {type:source.event.type,
          trusted:source.event.isTrusted,field:source.node === field};
        if(cause === 'typing') document.getElementById('above').style.height = '40px';
      });
    }""",
        cause,
    )
    field = page.locator("#field")
    field.focus()
    paint(page)
    before = field.bounding_box()
    page.keyboard.insert_text("First line\nSecond line\nThird line")
    expect(field).to_have_js_property("value", "First line\nSecond line\nThird line")
    assert page.evaluate("window.nativeGeometryInput") == {
        "type": "textupdate",
        "trusted": True,
        "field": True,
    }
    paint(page)
    assert field.bounding_box()["height"] > before["height"]
    judge_watches()
    if cause == "typing":
        assert field.bounding_box()["y"] == pytest.approx(before["y"] + 40)
        consume_browser_errors(
            page,
            {
                "code": "typing-moved",
                "field": "leaf-text#field",
                "node": "leaf-text#field",
            },
        )
    else:
        assert field.bounding_box()["y"] == pytest.approx(before["y"])
        page.evaluate("document.getElementById('above').style.height = '40px'")
        judge_watches()
        consume_browser_errors(page, moved_within("leaf-text#field"))


@pytest.mark.parametrize(
    "compensate,holder",
    [(True, "inert"), (False, "inert"), (True, "region"), (True, "painted")],
)
def test_typing_protects_subjects_through_a_coordinate_carrier_rebase(
    browser, compensate, holder
):
    """Carrier coordinates are disposable; controls and declared regions are not."""
    page = browser.new_page()
    declared = 'data-lf-reflow="controls"' if holder == "region" else ""
    background = (
        "background:white;border:1px solid black;box-shadow:0 1px 3px #888"
        if holder == "painted"
        else ""
    )
    page.goto(
        "data:text/html,"
        + quote(f"""<!doctype html><body style="margin:0">
<div id="carrier" {declared} style="position:relative;width:300px;height:100px;{background}">
  <div id="inside" style="position:relative"><textarea id="field" rows="1"></textarea></div>
</div><script>
  field.addEventListener('beforeinput', () => {{
    carrier.style.left = '20px';
    inside.style.left = '{-20 if compensate else 0}px';
  }});
</script></body>""")
    )
    paint(page)
    read = """() => Object.fromEntries(['carrier','field'].map(id =>
      [id, document.getElementById(id).getBoundingClientRect().x]))"""
    before = page.evaluate(read)
    page.locator("#field").fill("a")
    paint(page)
    after = page.evaluate(read)
    assert after["carrier"] - before["carrier"] == 20
    assert after["field"] - before["field"] == (0 if compensate else 20)
    judge_watches()
    if not compensate:
        consume_browser_errors(
            page,
            {
                "code": "typing-moved",
                "field": "textarea#field",
                "node": "textarea#field",
            },
        )
    elif holder != "inert":
        consume_browser_errors(
            page,
            {"code": "typing-moved", "field": "textarea#field", "node": "div#carrier"},
        )


@pytest.mark.parametrize("distance", [6, 40])
def test_a_shift_without_input_fails(browser, distance):
    page = field_page(browser)
    page.evaluate(
        "distance => { document.getElementById('above').style.height = distance + 'px'; }",
        distance,
    )
    judge_watches()
    consume_browser_errors(
        page,
        moved_within("textarea#field", by=[0, distance]),
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


PASSIVE_FAULTS = [
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
]


# The owner kind changes only how the region declares itself the runtime's, so the inline
# owner runs the faults that read that declaration rather than the whole list.
@pytest.mark.parametrize(
    "fault, protected, owner_kind",
    [(*case, "chrome") for case in PASSIVE_FAULTS]
    + [
        (fault, protected, "inline")
        for fault, protected in PASSIVE_FAULTS
        if fault in {"", "outside_runtime", "moving_region"}
    ],
)
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
        errors = consume_browser_errors(page, {"code": "moved-without-input"})
        assert names_move(errors, protected), errors


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
        errors = consume_browser_errors(page, {"code": "moved-without-input"})
        assert names_move(errors, protected), errors


@pytest.mark.parametrize(
    "fault, protected",
    [
        ("", None),
        ("sticky_tail", None),
        ("sticky_extra", "button#reply"),
        ("prepend", "p#old"),
        ("old_growth", "button#reply"),
        ("extra_carry", "button#later"),
        ("moving_port", "button#reply"),
        ("outside", "button#outside"),
        ("outside_runtime", "button#reply"),
        ("port_outside_runtime", "button#reply"),
        ("enclosing_text", "button#reply"),
    ],
)
def test_append_reflow_credits_only_its_measured_suffix_growth(
    browser, fault, protected
):
    """An arrival may move its reply and later cards, preserving the transcript."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><body style="margin:0;font:16px monospace">'
            '<div id="port" data-lf-runtime style="width:360px;height:300px;'
            'padding:5px;box-sizing:border-box;overflow:auto;overflow-anchor:none">'
            '<section style="overflow:clip">'
            '<div id="source" data-lf-reflow="append">'
            '<p id="old" style="margin:0;height:40px">Already reading.</p></div>'
            '<button id="reply" style="display:block;position:sticky;bottom:0">Reply</button></section>'
            '<article><p style="margin:0">Another conversation.</p>'
            '<button id="later">Later thread</button></article></div>'
            '<button id="outside">Outside the panel</button></body>'
        )
    )
    if fault in {"outside_runtime", "port_outside_runtime"}:
        page.locator("#port").evaluate(
            "node => node.removeAttribute('data-lf-runtime')"
        )
    if fault == "port_outside_runtime":
        page.locator("#source").evaluate(
            "node => node.setAttribute('data-lf-runtime', '')"
        )
    if fault == "enclosing_text":
        page.locator("#port > section").evaluate(
            "node => node.setAttribute('data-lf-reflow', 'text')"
        )
    paint(page)
    before = page.locator("#old").bounding_box()
    reply_before = page.locator("#reply").bounding_box()
    page.evaluate(
        """fault => {
          const source = document.getElementById('source');
          const next = document.createElement('p');
          next.textContent = 'The newly appended reply.';
          next.style.cssText = `margin:0;height:${fault.startsWith('sticky_') ? 400 : 40}px`;
          if (fault === 'prepend') source.prepend(next);
          else source.append(next);
          if (fault === 'old_growth') document.getElementById('old').style.height = '60px';
          if (fault === 'extra_carry') document.getElementById('later').style.marginTop = '7px';
          if (fault === 'sticky_extra') document.getElementById('reply').style.bottom = '7px';
          if (fault === 'moving_port') document.getElementById('port').style.marginTop = '7px';
          if (fault === 'outside') document.getElementById('outside').style.marginTop = '7px';
        }""",
        fault,
    )
    judge_watches()
    if not protected:
        assert page.locator("#old").bounding_box() == before
        if fault == "sticky_tail":
            port = page.locator("#port").bounding_box()
            assert page.locator("#reply").bounding_box()["y"] == (
                port["y"] + port["height"] - 5 - reply_before["height"]
            )
        else:
            assert page.locator("#reply").bounding_box()["y"] == reply_before["y"] + 40
    else:
        errors = consume_browser_errors(page, {"code": "moved-without-input"})
        assert names_move(errors, protected), errors


@pytest.mark.parametrize("overflow", ["visible", "auto"])
def test_boxless_overflow_does_not_hide_carried_reading(browser, overflow):
    """Overflow on a display:contents wrapper cannot clip its visible descendants."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><body style="margin:0">'
            f'<div id="wrapper" style="display:contents;overflow:{overflow};padding:10%">'
            '<div id="above" style="height:40px"></div>'
            '<button id="target">Reading control</button></div></body>'
        )
    )
    paint(page)
    assert (
        page.locator("#wrapper").evaluate("node => node.getClientRects().length") == 0
    )
    assert page.locator("#target").bounding_box()["y"] == 40
    page.locator("#above").evaluate("node => node.style.height = '80px'")
    judge_watches()
    assert page.locator("#target").bounding_box()["y"] == 80
    errors = consume_browser_errors(page, {"code": "moved-without-input"})
    assert names_move(errors, "button#target"), errors


@pytest.mark.parametrize("bounded", [False, True])
@pytest.mark.parametrize("position", ["static", "sticky"])
def test_append_uses_an_actual_scrollport_past_boxless_overflow(
    browser, bounded, position
):
    """A boxless ancestor cannot own append growth; an actual outer scrollport can."""
    page = browser.new_page()
    contents = (
        '<div data-lf-runtime style="display:contents;overflow:auto;padding:10%;'
        f'position:{position};bottom:0">'
        '<div id="source" data-lf-reflow="append">'
        '<p style="height:40px;margin:0">Earlier message.</p></div>'
        '<button id="target">Reply</button></div>'
    )
    if bounded:
        contents = (
            '<div data-lf-runtime style="width:360px;height:300px;overflow:auto">'
            + contents
            + "</div>"
        )
    page.goto(
        "data:text/html," + quote('<!doctype html><body style="margin:0">' + contents)
    )
    paint(page)
    assert page.locator("#target").bounding_box()["y"] == 40
    page.evaluate("""() => {
      const message = document.createElement('p');
      message.style.cssText = 'height:400px;margin:0';
      message.textContent = 'The new message.';
      document.getElementById('source').append(message);
    }""")
    judge_watches()
    assert page.locator("#target").bounding_box()["y"] == 440
    if not bounded:
        errors = consume_browser_errors(page, {"code": "moved-without-input"})
        assert names_move(errors, "button#target"), errors


def test_append_reflow_preserves_nested_text_reflow(browser):
    """A stationary old header may still repack inside its own declared boundary."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><body style="margin:0;font:16px monospace">'
            '<div data-lf-runtime style="width:360px;height:300px;overflow:auto">'
            '<div id="source" data-lf-reflow="append">'
            '<div style="height:40px"><div data-lf-reflow="text" '
            'style="display:flex;width:360px;height:24px">'
            '<span id="receipt">Waiting</span><span id="time">Today</span>'
            '</div></div></div><button id="reply">Reply</button></div>'
        )
    )
    paint(page)
    before = page.locator("#time").bounding_box()
    page.evaluate("""() => {
      document.getElementById('receipt').textContent = 'Responded just now';
      const next = document.createElement('p'); next.textContent = 'New reply';
      next.style.cssText = 'margin:0;height:40px';
      document.getElementById('source').append(next);
    }""")
    judge_watches()
    assert page.locator("#time").bounding_box()["x"] > before["x"]


def test_append_reflow_does_not_credit_typing_that_carries_its_editor(browser):
    """The append permission does not weaken the independently retained typing pose."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            '<!doctype html><body style="margin:0">'
            '<div data-lf-runtime style="width:360px;height:300px;overflow:auto">'
            '<div id="source" data-lf-reflow="append">'
            '<p style="margin:0;height:40px">Already reading.</p></div>'
            '<textarea id="field"></textarea></div>'
            '<script>document.getElementById("field").addEventListener("beforeinput", () => {'
            'const next = document.createElement("p"); next.textContent = "New reply";'
            'next.style.cssText = "margin:0;height:40px";'
            'document.getElementById("source").append(next); });</script>'
        )
    )
    paint(page)
    page.locator("#field").fill("a")
    judge_watches()
    consume_browser_errors(
        page,
        {"code": "typing-moved", "field": "textarea#field", "node": "textarea#field"},
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
        consume_browser_errors(page, {"code": "moved-without-input"})


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
        consume_browser_errors(page, {"code": "moved-without-input"})


@pytest.mark.shifts_unsurveyed
@pytest.mark.watch_shifts
def test_a_marked_page_watches_typing_and_unasked_shifts(browser):
    """An unsurveyed module's opt-in uses the same sensor: growing a field is allowed, carrying it
    without input is reported, and typing that carries it is reported too."""
    page = field_page(browser, "grow")
    page.locator("#field").fill("a")
    judge_watches()
    assert page.lf_errors == []
    page.evaluate("document.getElementById('above').style.height = '40px'")
    judge_watches()
    consume_browser_errors(page, moved_within("textarea#field"))

    carried = field_page(browser, "carry")
    carried.locator("#field").fill("a")
    judge_watches()
    consume_browser_errors(
        carried,
        {"code": "typing-moved", "field": "textarea#field", "node": "textarea#field"},
    )


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
    consume_browser_errors(page, moved_within("textarea#field"))


def test_an_input_owns_its_counted_rendering_until_it_settles(browser, serve):
    """Counted input work can cross frames; its completion ends movement credit. Each
    step of the work takes ten times an ordinary frame's, so credit that lapsed on a
    clock rather than on the work's completion would fail here."""
    work_ms = 300
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
      const {nextFrame} = await window.__lfWidgetApi();
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
    consume_browser_errors(page, moved_within("button#control"))


def test_an_input_owns_the_landing_of_a_widget_preparation_it_began(browser, serve):
    """A press's declared widget preparation is its result, however late it lands, and
    the press owns nothing while it waits.

    Opening a closed lf-diff file loads its evidence in a promise the widget presents
    (`present`). Holding the grammar keeps complete rendering pending while its
    counted queue rests, as a loaded machine does."""
    patch = "".join(
        f"diff --git a/{name}.md b/{name}.md\n--- a/{name}.md\n+++ b/{name}.md\n"
        "@@ -1 +1 @@\n-old\n+new\n"
        for name in ("first", "second")
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Preparation",
                f'<lf-diff id="patch" collapsed><pre>{escape(patch)}</pre></lf-diff>'
                '<button id="control">Keep this control usable</button>',
            )
        ),
    )
    held = []
    page.route("**/vendor/syntax/markdown.js", lambda route: held.append(route))
    first = page.locator("#patch .lf-diff-file").first
    control = page.locator("#control")
    first.locator(".lf-diff-head").click()
    holding(page, held, 1, "the markdown grammar")
    rendered(page, facts=("updatesSettled",))
    assert not page.evaluate(
        "document.querySelector('script[data-lf-entry]').lfRenderingState().preparationsSettled"
    )
    assert (
        page.evaluate(
            "document.querySelector('script[data-lf-entry]').lfReadiness(null, 'presented')"
        )
        == "presented"
    )
    # While the preparation waits, the press owns no other movement on the page.
    control.evaluate("node => node.style.marginTop = '40px'")
    rendered(page, facts=("updatesSettled",))
    judge_watches()
    consume_browser_errors(page, moved_within("button#control"))

    # Its landing moves the files and the control after it, for the press.
    before = control.bounding_box()["y"]
    held[0].continue_()
    expect(first.locator("[data-line]").last).to_contain_text("new")
    rendered(page)
    assert control.bounding_box()["y"] > before
    judge_watches()
    assert page.lf_errors == []

    # Once it has landed, the press owns nothing further. (The watch names each node
    # once, so this move is the diff's own, which the landing moved for the press.)
    page.locator("#patch").evaluate("node => node.style.marginTop = '40px'")
    rendered(page)
    judge_watches()
    moved = consume_browser_errors(page, {"code": "moved-without-input"})
    assert any(
        "in shadow of lf-diff#patch" in error.values["node"] for error in moved
    ), moved


@pytest.mark.parametrize(
    "retired_at", ["no preparation", "click", "resolve-remove", "remove-resolve"]
)
def test_a_retired_widget_preparation_cannot_credit_a_passive_landing(
    browser, serve, retired_at
):
    """A removed renderer's late completion cannot credit unrelated page movement.

    The no-preparation control proves ordinary input credit expires. A declaration
    retires with its owner even when its promise reaction precedes delivery of the
    removal's mutation record.
    """
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Retired preparation",
                '<button id="press">Press</button>'
                '<lf-options id="choice"><lf-option id="a">A</lf-option></lf-options>'
                '<button id="control" style="display:block">Control</button>',
            )
        ),
    )
    page.evaluate(
        """async retiredAt => {
          const {widgetController} = await window.__lfWidgetApi();
          const widget = document.querySelector('#choice');
          const gate = Promise.withResolvers();
          window.release = gate.resolve;
          const terminal = Promise.withResolvers();
          window.terminal = terminal.promise;
          document.querySelector('#press').addEventListener('click', () => {
            if (retiredAt !== "no preparation") {
              let identity;
              const stop = document.querySelector('script[data-lf-entry]').lfObserveWidgetPreparations((phase, preparation) => {
                if (phase === 'begin') identity ??= preparation;
                else if (preparation === identity) { terminal.resolve(); stop(); }
              });
              widgetController(widget).present(gate.promise);
            } else terminal.resolve();
            if (["no preparation", "click"].includes(retiredAt)) widget.remove();
          }, {once: true});
        }""",
        retired_at,
    )
    page.locator("#press").click()
    rendered(page, facts=("updatesSettled",))
    judge_watches()
    assert page.lf_errors == []
    page.evaluate(
        """async retiredAt => {
          const widget = document.querySelector('#choice');
          if (retiredAt === 'remove-resolve') widget.remove();
          window.release();
          if (retiredAt === 'resolve-remove') widget.remove();
          await window.terminal;
          document.querySelector('#control').style.marginTop = '40px';
        }""",
        retired_at,
    )
    rendered(page)
    judge_watches()
    consume_browser_errors(page, moved_within("button#control"))


@pytest.mark.parametrize("first_outcome", ["rejected", "pending"])
def test_each_capable_preparation_keeps_its_own_input_landing(
    browser, serve, first_outcome
):
    """A sibling can land after another fails or before another completes.

    Semantic presentation aggregates both promises, but each actual producer owns
    its own mechanical landing. Neither an early aggregate rejection nor a pending
    sibling may lose the successful producer's input attribution.
    """
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Sibling preparation",
                '<button id="press">Press</button>'
                '<lf-options id="choice"><lf-option id="a">A</lf-option></lf-options>'
                '<button id="control" style="display:block">Control</button>',
            )
        ),
    )
    page.evaluate("""async () => {
      const {widgetController} = await window.__lfWidgetApi();
      const widget = document.querySelector('#choice');
      const first = Promise.withResolvers();
      const second = Promise.withResolvers();
      window.rejectFirst = first.reject;
      window.releaseFirst = first.resolve;
      window.releaseSecond = second.resolve;
      document.querySelector('#press').addEventListener('click', () => {
        widgetController(widget).present(first.promise);
        widgetController(widget).present(second.promise.then(() => {
          widget.style.height = '120px';
        }));
      }, {once: true});
    }""")
    page.locator("#press").click()
    judge_watches()
    assert page.lf_errors == []
    if first_outcome == "rejected":
        page.evaluate("rejectFirst(new Error('deliberate preparation failure'))")
        page.wait_for_selector("#choice .lf-error")
        judge_watches()
        consume_browser_errors(page, "deliberate preparation failure")
    assert not page.evaluate(
        "document.querySelector('script[data-lf-entry]').lfRenderingState().preparationsSettled"
    )
    page.evaluate("releaseSecond()")
    page.wait_for_function("document.querySelector('#choice').style.height === '120px'")
    judge_watches()
    assert page.lf_errors == []
    if first_outcome == "pending":
        assert not page.evaluate(
            "document.querySelector('script[data-lf-entry]').lfRenderingState().preparationsSettled"
        )
        page.evaluate("releaseFirst()")
    rendered(page)
    judge_watches()
    assert page.lf_errors == []


@pytest.mark.parametrize(
    "input_at",
    ["outside", "same-widget", "same-disclosure-attr-node"],
)
def test_a_preparation_no_input_began_lands_passive(browser, serve, input_at):
    """Overlapping an input's rendering or widget does not make its preparation input's.

    A press outside the diff, on its second file's header, or a prevented press on the
    first keeps counted work running until a response requested before the press opens
    the first file. Its passive landing moves the control once the press settles."""
    patch = "diff --git a/first.md b/first.md\n--- a/first.md\n+++ b/first.md\n"
    patch += "@@ -1 +1 @@\n-old\n+new\n"
    patch += (
        "diff --git a/second.txt b/second.txt\n--- a/second.txt\n+++ b/second.txt\n"
    )
    patch += "@@ -1 +1 @@\n-old\n+new\n"
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Passive preparation",
                '<button id="press">Elsewhere</button>'
                f'<lf-diff id="patch" collapsed><pre>{escape(patch)}</pre></lf-diff>'
                '<button id="control">Keep this control usable</button>',
            )
        ),
    )
    answer, grammar = [], []
    page.route("**/held-answer", lambda route: answer.append(route))
    page.route("**/vendor/syntax/markdown.js", lambda route: grammar.append(route))
    page.evaluate(
        """async inputAt => {
      const {nextFrame} = await window.__lfWidgetApi();
      const root = document.querySelector('#patch').shadowRoot;
      const details = root.querySelector('details');
      const opens = () => {
        if (inputAt === 'same-disclosure-attr-node')
          details.setAttributeNode(document.createAttribute('open'));
        else if (inputAt === 'same-disclosure') details.setAttribute('open', '');
        else details.open = true;
      };
      fetch('/held-answer').then(opens, opens);
      const press = inputAt === 'outside' ? document.querySelector('#press')
        : root.querySelectorAll('.lf-diff-head')[inputAt === 'same-widget' ? 1 : 0];
      press.addEventListener('click', event => {
        if (inputAt.startsWith('same-disclosure')) event.preventDefault();
        let after = 0;
        const work = () => { if (!details.open || ++after < 3) nextFrame(work); };
        nextFrame(work);
      }, {once: true});
    }""",
        input_at,
    )
    holding(page, answer, 1, "the page's own request")
    if input_at == "outside":
        page.locator("#press").click()
    else:
        page.locator("#patch .lf-diff-head").nth(
            1 if input_at == "same-widget" else 0
        ).click()
    if input_at.startswith("same-disclosure"):
        assert not page.locator("#patch details").first.evaluate("node => node.open")
    answer[0].fulfill(status=204)
    holding(page, grammar, 1, "the markdown grammar")
    rendered(page, facts=("updatesSettled",))
    judge_watches()
    assert page.lf_errors == []

    grammar[0].continue_()
    expect(
        page.locator("#patch .lf-diff-file").first.locator("[data-line]").last
    ).to_contain_text("new")
    rendered(page)
    judge_watches()
    moved = consume_browser_errors(page, {"code": "moved-without-input"})
    assert names_move(moved, "button#control"), moved


@pytest.fixture
def input_work_page(browser):
    """Isolate the source sensor from subscriber listeners; the browser owns contexts."""
    errors = []

    def open_page(markup):
        context = browser.unwatched.new_context()
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "console",
            lambda message: (
                errors.append(message.text)
                if message.type in {"error", "warning"}
                else None
            ),
        )
        page.add_init_script(
            script=f"{WATCH_PLATFORM_SOURCE.read_text()}\n"
            "window.nativeWatchListen = EventTarget.prototype.addEventListener;\n"
            f"{INPUT_WORK_WATCH_SOURCE.read_text()}"
        )
        page.goto("data:text/html," + quote(markup))
        return page

    yield open_page
    assert errors == [], errors


@pytest.mark.parametrize("route", ["pointer", "keyboard", "passive"])
def test_disclosure_dispatch_carries_source_without_click_listeners(
    input_work_page, route
):
    """Native activation and callback forms share the dispatch's exact source."""
    page = input_work_page(
        """<button id="press">Open</button>
      <details ontoggle="window.inlineSource = lfInputWork.current()?.event.type ?? null">
      <summary>Fold</summary>Content</details>"""
    )
    page.evaluate("""() => {
      document.querySelector('details').addEventListener('toggle', () => {
        window.registeredSource = lfInputWork.current()?.event.type ?? null;
      });
      document.querySelector('#press').addEventListener('keydown', event => {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        document.querySelector('summary').click();
      });
    }""")
    if route == "pointer":
        page.locator("summary").click()
    elif route == "keyboard":
        page.locator("#press").focus()
        page.keyboard.press("Enter")
    else:
        page.evaluate("document.querySelector('summary').click()")
    page.wait_for_function(
        "window.registeredSource !== undefined && window.inlineSource !== undefined"
    )
    source = {"pointer": "click", "keyboard": "keydown", "passive": None}[route]
    assert page.evaluate("[window.inlineSource, window.registeredSource]") == [
        source,
        source,
    ]


@pytest.mark.parametrize("kind", ["synthetic-click", "native-toggle"])
def test_redispatching_an_event_uses_the_new_dispatch_source(input_work_page, kind):
    """An Event object can be reused; its old dispatch cannot own passive work."""
    page = input_work_page(
        '<button id="press">Dispatch</button>'
        '<button id="result">Result</button>'
        "<details><summary>Fold</summary>Content</details>"
    )
    page.evaluate(
        """kind => {
      window.readings = [];
      const details = document.querySelector('details');
      const result = document.querySelector('#result');
      const native = kind === 'native-toggle';
      window.dispatchOwner = native ? details : result;
      window.reusedEvent = native ? null : new MouseEvent('click', {bubbles:true, composed:true});
      dispatchOwner.addEventListener(native ? 'toggle' : 'click', event => {
        reusedEvent ??= event;
        readings.push(lfInputWork.current()?.event.type ?? null);
      });
      document.querySelector('#press').addEventListener('keydown', event => {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        if (native) details.querySelector('summary').click();
        else result.dispatchEvent(reusedEvent);
      });
    }""",
        kind,
    )
    page.locator("#press").focus()
    page.keyboard.press("Enter")
    page.wait_for_function("window.readings.length === 1")
    page.evaluate("dispatchOwner.dispatchEvent(reusedEvent)")
    assert page.evaluate("readings") == ["keydown", None]


def test_a_delivered_disclosure_toggle_releases_its_input_source(input_work_page):
    """Native delivery retires input ownership even without a wrapped page listener."""
    page = input_work_page("<details><summary>Open</summary>Content</details>")
    page.evaluate("""() => {
      window.nativeToggles = 0;
      nativeWatchListen.call(document.querySelector('details'), 'toggle', () => nativeToggles++);
    }""")
    page.locator("summary").click()
    page.wait_for_function("window.nativeToggles === 1")
    page.evaluate("""() => {
      const details = document.querySelector('details');
      details.ontoggle = () => {
        window.propertyToggleSource = lfInputWork.current()?.event.type ?? null;
      };
      details.addEventListener('toggle', () => {
        window.passiveToggleSource = lfInputWork.current()?.event.type ?? null;
      });
      details.attributes.removeNamedItem('open');
    }""")
    page.wait_for_function("window.passiveToggleSource !== undefined")
    assert page.evaluate(
        "[window.passiveToggleSource, window.propertyToggleSource]"
    ) == [None, None]


@pytest.mark.parametrize("cancelled", [True, False], ids=["cancelled", "closed again"])
def test_an_activation_that_opens_nothing_leaves_a_later_open_passive(
    browser, serve, cancelled
):
    """A summary press that leaves its file shut gives a later opening no input.

    Enter on a file's header either has its click cancelled, so no toggle comes, or
    has the click's own listener open the file before the activation shuts it again,
    so the one toggle that comes announces it closed. A script opening the file after
    either is no input's, and its landing moves the control after it passively."""
    patch = "diff --git a/first.md b/first.md\n--- a/first.md\n+++ b/first.md\n"
    patch += "@@ -1 +1 @@\n-old\n+new\n"
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Shut activation",
                f'<lf-diff id="patch" collapsed><pre>{escape(patch)}</pre></lf-diff>'
                '<button id="control">Keep this control usable</button>',
            )
        ),
    )
    grammar = []
    page.route("**/vendor/syntax/markdown.js", lambda route: grammar.append(route))
    page.evaluate(
        """cancelled => {
      const details = document.querySelector('#patch').shadowRoot.querySelector('details');
      window.toggles = [];
      details.addEventListener('toggle', (event) => toggles.push(event.newState));
      details.querySelector('summary').addEventListener('click', (event) => {
        if (cancelled) event.preventDefault();
        else details.open = true;
      }, {once: true});
    }""",
        cancelled,
    )
    head = page.locator("#patch .lf-diff-head")
    head.focus()
    head.press("Enter")
    if not cancelled:
        page.wait_for_function("toggles.length === 1")
        assert page.evaluate("toggles") == ["closed"]
    rendered(page)
    assert page.locator("#patch details").get_attribute("open") is None
    judge_watches()
    if not cancelled:
        # The click's listener restates `open` the activation then takes back.
        consume_browser_errors(
            page,
            {
                "code": "unchanged-write",
                "what": "open",
                "node": "details.lf-diff-fold in shadow of lf-diff#patch.lf-rendered",
            },
        )
    assert page.lf_errors == []

    page.evaluate(
        "document.querySelector('#patch').shadowRoot.querySelector('details').open = true"
    )
    holding(page, grammar, 1, "the markdown grammar")
    paint(page)
    grammar[0].continue_()
    expect(page.locator("#patch [data-line]").last).to_contain_text("new")
    rendered(page)
    judge_watches()
    moved = consume_browser_errors(page, {"code": "moved-without-input"})
    assert names_move(moved, "button#control"), moved


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
    consume_browser_errors(page, moved_within("textarea#field", by=[0, 40]))


@pytest.mark.parametrize(
    "when, opaque",
    [
        pytest.param("already-hidden", False, id="already-hidden"),
        pytest.param("hidden-during-drain", False, id="hidden-during-drain"),
        pytest.param("resize-during-drain", False, id="resize-during-drain"),
        pytest.param("resize-during-drain", True, id="opaque-resize-during-drain"),
        pytest.param("cssom-during-drain", False, id="cssom-during-drain"),
    ],
)
def test_a_hidden_frame_judges_existing_records_without_awaiting_paint(
    browser, when, opaque
):
    page = field_page(browser)
    page.set_viewport_size({"width": 900, "height": 600})
    page.evaluate(
        """({when, opaque}) => {
      const style = document.createElement('style');
      style.textContent = '@media(max-width:600px){iframe{display:none}}';
      document.head.append(style);
      const frame = document.createElement('iframe');
      if (when === 'already-hidden') frame.style.display = 'none';
      if (opaque) frame.setAttribute('sandbox', 'allow-scripts');
      frame.srcdoc = '<!doctype html><body><button>Hidden control</button></body>';
      document.body.append(frame);
    }""",
        {"when": when, "opaque": opaque},
    )
    page.frame_locator("iframe").locator("button").wait_for(state="attached")
    frame = page.frames[1]
    drawn = page.locator("iframe").evaluate("frame => frame.checkVisibility()")
    frame.evaluate(
        """async drawn => {
      const nativeFrame = window.lfWatchPlatform.frame;
      const held = [];
      window.lfWatchPlatform.frame = callback => { held.push(callback); return 0; };
      window.restoreFrame = () => {
        window.lfWatchPlatform.frame = nativeFrame;
        for (const callback of held.splice(0)) nativeFrame(callback);
      };
      window.readHeldFrame = () => {
        for (const callback of held.splice(0)) callback(performance.now());
      };
      // Holding future registrations leaves previously requested callbacks live.
      // Let them enter the hold before forcing the next reading to verify itself.
      if (drawn) await new Promise(nativeFrame);
      // The driver publishes owner visibility; this sensor-level fixture supplies
      // the same fact while holding paint. Opaque-frame integration is above.
      window.lfWatchJudgement = {
        ancestorsDrawn: drawn,
      };
      window.hiddenJudged = false;
      window.lfShiftsJudged().then(() => window.hiddenJudged = true);
    }""",
        drawn,
    )
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
        # A native callback may run after the owner hides but before the driver
        # refreshes its visibility fact. Child frames retain complete readings
        # because the embedding page's changes do not announce themselves here.
        frame.evaluate("window.readHeldFrame()")
        drawn = page.locator("iframe").evaluate("frame => frame.checkVisibility()")
        frame.evaluate("drawn => lfWatchJudgement.ancestorsDrawn = drawn", drawn)
        frame.wait_for_function("window.hiddenJudged === true", polling=100)
        assert drawn is False
    finally:
        frame.evaluate("window.restoreFrame(); delete window.lfWatchJudgement")


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
    consume_browser_errors(page, moved_within("textarea#field", by=[0, 40]))


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
    consume_browser_errors(page, moved_within("textarea#field", by=[0, 40]))


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
    consume_browser_errors(page, moved_within("textarea#field", by=[0, 40]))


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
    consume_browser_errors(page, {"code": "moved-without-input", "by": [0, 40]})


# News three frames after a press, as a reply lands just after a click: the page adopts
# a server reading. A stand-in for the runtime never settles its rendering, so the
# press's rendering is still open when the news lands. What moves the line is the
# page's `data-motion`: the news growing a box above it (none), the news beginning a
# bar's slide above it (`news`), or the press beginning that slide, which runs on past
# news that moves nothing (`press`). The height slide is a conservative sensor
# boundary: native height-induced sibling flow has no exact translation proof.
# The matched marginTop arm proves press/news ownership with supported displacement.
NEWS = """<!doctype html><body style="margin:0">
<script data-lf-entry>document.currentScript.lfRenderingState = () => ({updatesSettled: false, preparationsSettled: true});</script>
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
      document.body.dataset.inputHeld = String(!document.querySelector('script[data-lf-entry]').lfRenderingState().updatesSettled);
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
    consume_browser_errors(page, moved_within("div#below"))


def test_native_height_sibling_flow_without_displacement_proof_is_reported(browser):
    """The sensor reports genuine native flow it cannot attribute, rather than guessing."""
    page = news_page(browser, "press")
    assert page.evaluate("parseFloat(getComputedStyle(bar).height)") > 0
    assert (
        page.locator("#below").bounding_box()["y"]
        > page.locator("#bar").bounding_box()["y"]
    )
    judge_watches()
    consume_browser_errors(page, moved_within("div#below"))


@pytest.mark.parametrize("motion", ["press", "news"])
def test_sampled_native_translation_distinguishes_press_from_news(browser, motion):
    """Identical native motion survives news only when the trusted press began it."""
    page = news_page(browser, motion, translation=True)
    page.wait_for_function("parseFloat(getComputedStyle(below).marginTop) > 0")
    judge_watches()
    if motion == "press":
        assert take_browser_errors(page) == []
    else:
        consume_browser_errors(page, moved_within("div#below"))


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
    consume_browser_errors(page, moved_within("textarea#field", by=[80, 0]))


@pytest.mark.parametrize(
    "creation,timeline,scale,property",
    [
        ("startup", "scroll", 1, "transform"),
        ("startup", "view", 1, "transform"),
        ("press", "scroll", 1, "transform"),
        ("startup", "scroll", 0.5, "transform"),
        ("startup", "scroll", 0.5, "top"),
        ("press", "document", 0.5, "transform"),
    ],
)
@pytest.mark.parametrize("local_motion", [False, True])
def test_native_attachment_keeps_only_its_measured_displacement(
    browser, creation, timeline, scale, property, local_motion
):
    """Native effects retain viewport travel without owning their field's own move."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            """<!doctype html><body><button id="attach">Attach moving surface</button>
<div id="source" style="height:80px;width:200px;overflow:auto"><div style="height:400px">Scroll source</div></div>
<div style="position:absolute;left:0;top:0;transform:scale(HOLDER_SCALE);transform-origin:0 0">
<div id="attachment" style="position:absolute;left:250px;top:130px;zoom:TARGET_ZOOM"><textarea id="field"></textarea></div></div>
<svg id="evidence" aria-hidden="true" style="position:absolute;left:0;top:400px;width:300px;height:30px;background:gray"></svg>
<script>function attachMotion(){
  const timeline=TIMELINE;
  const from=timeline instanceof ViewTimeline ? timeline.startOffset.value : 0;
  const to=timeline instanceof ViewTimeline ? timeline.endOffset.value : 320;
  const frames='PROPERTY'==='top'
    ? [{top:`${130-from}px`},{top:`${130-to}px`}]
    : [{transform:`translateY(${-from}px)`},{transform:`translateY(${-to}px)`}];
  window.attachmentMotion=attachment.animate(
    frames,
    {timeline:timeline,duration:timeline===document.timeline?32000000:'auto',fill:'both'});
  if(timeline===document.timeline)attachmentMotion.playbackRate=0;
}
attach.addEventListener('click',attachMotion);
STARTUP</script></body>""".replace(
                "STARTUP", "attachMotion();" if creation == "startup" else ""
            )
            .replace("HOLDER_SCALE", str(scale if property == "transform" else 1))
            .replace("TARGET_ZOOM", str(scale if property == "top" else 1))
            .replace("PROPERTY", property)
            .replace(
                "TIMELINE",
                "new ViewTimeline({subject:source.firstElementChild,axis:'y'})"
                if timeline == "view"
                else "document.timeline"
                if timeline == "document"
                else "new ScrollTimeline({source:source,axis:'y'})",
            )
        )
    )
    paint(page)
    if creation == "press":
        page.locator("#attach").click()
    assert page.evaluate("attachmentMotion.playState") == "running"
    judge_watches()
    assert take_browser_errors(page) == []
    before = page.locator("#field").bounding_box()
    page.evaluate(
        """({carry,scale,timeline})=>{
          source.scrollTop=20;
          if(timeline==='document')attachmentMotion.currentTime+=2000000;
          if(carry){if(scale===1)field.style.marginLeft='80px';else field.style.marginTop='-20px'}
          evidence.style.left='20px';
        }""",
        {"carry": local_motion, "scale": scale, "timeline": timeline},
    )
    paint(page)
    after = page.locator("#field").bounding_box()
    assert page.evaluate("source.scrollTop") == 20
    assert after["y"] - before["y"] == pytest.approx(
        -20 * scale * (2 if local_motion and scale != 1 else 1), abs=0.5
    )
    assert after["x"] - before["x"] == (80 if local_motion and scale == 1 else 0)
    judge_watches()
    if local_motion:
        errors = consume_browser_errors(page, moved_within("textarea#field"))
        evidence = shift_evidence(errors[0])
        assert any(
            term["branch"]
            == ("animation" if timeline == "document" else "scroll_animation")
            and term["owner"] == "div#attachment"
            and term["axis"] == "top"
            and term["amount"] < 0
            for comparison in evidence["comparisons"]
            for term in comparison["animation_terms"]
        ), evidence
    else:
        assert take_browser_errors(page) == []


@pytest.mark.parametrize(
    "change",
    ["rebase", "retarget", "range", "layout", "unscrolled", "faster", "sideways"],
)
def test_native_scroll_credit_requires_its_retained_translation_trajectory(
    browser, change
):
    """Uniform placement rebases retain scroll; changed trajectories cannot borrow it."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(
            """<!doctype html><body>
<div id="source" style="height:80px;width:200px;overflow:auto"><div style="height:400px">Scroll source</div></div>
<div id="attachment" style="position:absolute;left:250px;top:130px"><textarea id="field"></textarea></div>
<svg id="evidence" aria-hidden="true" style="position:absolute;left:0;top:400px;width:300px;height:30px;background:gray"></svg>
<script>
window.attachmentMotion=attachment.animate(
  [{transform:'translateY(0px)'},{transform:'END_TRANSLATION'}],
  {timeline:new ScrollTimeline({source:source,axis:'y'}),duration:'auto',fill:'both'});
</script></body>""".replace(
                "END_TRANSLATION",
                "translateX(-320px)"
                if change == "sideways"
                else "translateY(-640px)"
                if change == "faster"
                else "translateY(-320px)",
            )
        )
    )
    paint(page)
    judge_watches()
    assert take_browser_errors(page) == []
    before = page.locator("#field").bounding_box()
    page.evaluate(
        """change=>{
      if(change!=='unscrolled')source.scrollTop=20;
      if(['rebase','retarget','unscrolled'].includes(change)){
        attachmentMotion.effect.setKeyframes([
          {transform:'translateY(20px)'},
          {transform:`translateY(${change==='retarget'?-280:-300}px)`}]);
        if(change!=='unscrolled')attachment.style.top='110px';
      }
      if(change==='range')attachmentMotion.rangeEnd='640px';
      if(change==='layout')source.firstElementChild.style.height='720px';
      evidence.style.left='20px';
    }""",
        change,
    )
    paint(page)
    after = page.locator("#field").bounding_box()
    assert after["y"] - before["y"] == pytest.approx(
        {
            "rebase": -20,
            "retarget": -18.75,
            "range": -10,
            "layout": -10,
            "unscrolled": 20,
            "faster": -40,
            "sideways": 0,
        }[change],
        abs=0.5,
    )
    assert after["x"] - before["x"] == pytest.approx(
        -20 if change == "sideways" else 0, abs=0.5
    )
    judge_watches()
    if change == "rebase":
        assert take_browser_errors(page) == []
    else:
        consume_browser_errors(page, moved_within("textarea#field"))


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
        consume_browser_errors(page, {"code": "moved-without-input", "by": [0, 200]})


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


def test_disposing_a_frame_releases_parent_input_without_unwatching_its_sibling(
    browser, serve
):
    """Removed documents stop reading parent edits; live siblings retain their sensor."""
    child = """<div id="above"></div><p id="below">Below.</p><script>
      const owner = parent, id = frameElement.id;
      lfInputWork.subscribeEdits(() => owner.editCounts[id]++);
    </script>"""
    embedded = escape(child, quote=True)
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Frame lifetime",
                '<script type="module">window.editCounts = {gone: 0, live: 0};</script>'
                f'<iframe id="gone" srcdoc="{embedded}"></iframe>'
                f'<iframe id="live" srcdoc="{embedded}"></iframe>'
                '<textarea id="field"></textarea>'
                "<button onclick=\"document.getElementById('gone').remove()\">Remove</button>",
            )
        ),
    )
    expect(page.frame_locator("#gone").locator("#below")).to_be_visible()
    expect(page.frame_locator("#live").locator("#below")).to_be_visible()
    page.locator("#field").fill("Before disposal.")
    before = page.evaluate("editCounts")
    assert before["gone"] > 0 and before["live"] > 0
    page.get_by_role("button", name="Remove", exact=True).click()
    expect(page.locator("#gone")).to_have_count(0)
    page.locator("#field").fill("Still editing.")
    judge_watches()
    after = page.evaluate("editCounts")
    assert after["gone"] == before["gone"]
    assert after["live"] > before["live"]

    # Input attribution must still reach a sibling. Its passive shift must also
    # remain visible; dropping every child subscription would conceal that fault.
    live = page.frame_locator("#live").locator("#above")
    live.evaluate("element => { element.style.height = '40px'; }")
    judge_watches()
    consume_browser_errors(
        page, {"code": "moved-without-input", "node": "#text in p#below"}
    )


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
        consume_browser_errors(page, moved_within(protected))


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
        consume_browser_errors(page, moved_within("button#action"))


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
    consume_browser_errors(
        page,
        {"code": "typing-moved", "field": "textarea#field", "node": "textarea#field"},
    )


@pytest.mark.parametrize("subject", ["button", "span"])
def test_a_retained_landmark_keeps_its_pose_when_a_new_sticky_owner_adopts_it(
    browser, subject
):
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(f"""<!doctype html><body style="margin:0">
<{subject} id="action" style="position:absolute;left:10px;top:10px">Act</{subject}>
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
    assert any(f"{subject}#action" in error.values["node"] for error in errors), errors
    assert {error.code for error in errors} == {"moved-without-input"}, errors


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
        consume_browser_errors(page, moved_within("svg#picture"))


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
    consume_browser_errors(page, moved_within("textarea#field"))


def test_native_modality_keeps_its_exposed_controls_in_place(browser, serve):
    """Only the top modal's controls are exposed, whichever dialog opened last: under
    each opening order each control moves in turn, and only the current one's move is
    reported. Each order names its controls afresh, since the watch reports a message
    once."""
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
    for order, reverse in enumerate((False, True)):
        page.evaluate(
            """([reverse, order]) => {
          const dialogs = [document.querySelector('#first'), document.querySelector('#second')];
          for (const dialog of dialogs) dialog.close();
          if (reverse) dialogs.reverse();
          dialogs[0].showModal(); dialogs[1].showModal();
          dialogs[0].querySelector('button').id = `older-${order}`;
          dialogs[1].querySelector('button').id = `current-${order}`;
        }""",
            [reverse, order],
        )
        page.screenshot()
        judge_watches()
        assert take_browser_errors(page) == [], reverse
        for subject in ("background", f"older-{order}", f"current-{order}"):
            page.locator("#" + subject).evaluate(
                "node => node.style.left = `${parseFloat(node.style.left) + 20}px`"
            )
            page.screenshot()
            judge_watches()
            if subject.startswith("current"):
                consume_browser_errors(page, moved_within(f"button#{subject}"))
            else:
                assert take_browser_errors(page) == [], (reverse, subject)


@pytest.mark.parametrize("sticky", [False, True])
@pytest.mark.parametrize("carry", [False, True])
@pytest.mark.parametrize("slotted", [False, True])
def test_typing_keeps_native_scroll_ownership_without_crediting_local_carry(
    browser, sticky, carry, slotted
):
    position = "position:sticky;top:0" if sticky else ""
    reading = f"""<div style="height:150px"></div>
<header style="{position};height:50px">
<textarea id="field" style="position:relative;top:0;display:block" rows="1"></textarea>
</header><div style="height:700px">Following reading</div>"""
    if slotted:
        reading = f"""<div id="host"><section slot="reading">{reading}</section></div>
<script>host.attachShadow({{mode:'open'}}).innerHTML =
  '<div id="scroller" style="height:300px;overflow:auto;width:400px"><slot name="reading"></slot></div>';
const scroller=host.shadowRoot.getElementById('scroller');</script>"""
    else:
        reading = f'<div id="scroller" style="height:300px;overflow:auto;width:400px">{reading}</div>'
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(f"""<!doctype html><body style="margin:0">
{reading}
<p id="evidence" style="position:absolute;left:10px;top:400px">Painted source</p>
<script>field.addEventListener('beforeinput', () => {{
  scroller.scrollTop += 6;
  evidence.style.left = "30px";
  {'field.style.top = "20px";' if carry else ""}
}})</script></body>""")
    )
    page.evaluate("amount => scroller.scrollTop = amount", 170 if sticky else 100)
    page.screenshot()
    page.locator("#field").fill("a")
    page.screenshot()
    judge_watches()
    if carry:
        errors = consume_browser_errors(
            page,
            {
                "code": "typing-moved",
                "field": "textarea#field",
                "node": "textarea#field",
            },
        )
        evidence = shift_evidence(errors[0])
        if sticky:
            assert any(
                term["branch"] == "sticky_scroll"
                and term["axis"] == "top"
                and any(
                    source["after"]["top"] - source["before"]["top"] == 6
                    for source in term["inputs"]["sources"]
                )
                for comparison in evidence["comparisons"]
                for term in comparison["scroll_terms"]
            ), evidence


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
        consume_browser_errors(
            page,
            {
                "code": "typing-moved",
                "field": "textarea#field",
                "node": "textarea#field",
            },
        )


# The clean case runs under both declarations; each fault runs under one, since where
# the insets are written changes how the credit is found, not what an extra move is.
# Rules disagreeing need the insets in rules, and an important rule over an inline
# inset needs the inset inline.
ANCHOR_SCROLL_CASES = [
    ("", "inline"),
    ("", "scoped_rule"),
    ("portal_x", "inline"),
    ("portal_y", "scoped_rule"),
    ("anchor_x", "scoped_rule"),
    ("anchor_y", "inline"),
    ("declared_unused", "inline"),
    ("rule_unused", "scoped_rule"),
    ("important_rule", "inline"),
]


@pytest.mark.parametrize("fault, declared", ANCHOR_SCROLL_CASES)
@pytest.mark.parametrize("transform", ["none", "scale(.8) rotate(10deg)"])
def test_native_anchor_scroll_retains_local_motion_proof(
    browser, fault, transform, declared
):
    """A portal following its anchor's scroll is credited whether its insets are
    written inline or stated in its tree's stylesheet, and whether its anchor's name is
    unique or repeated under `anchor-scope`; moving either independently still fails.
    A direct anchor inset that a more specific rule overrides credits nothing, even
    where a later rule in sheet order states it, and neither does an inline one an
    important rule overrides."""
    field_style = "position:fixed;position-anchor:--target;left:calc(anchor(left) + 100px);top:calc(anchor(top) + 10px)"
    if fault == "declared_unused":
        field_style = "position:fixed;position-anchor:--target;left:100px;top:50px"
    sheet, scope, decoy = "", "", ""
    if declared == "scoped_rule":
        sheet = f"<style>#field {{ {field_style} }}</style>"
        field_style = ""
        scope = "anchor-scope:--target"
        decoy = '<div style="anchor-scope:--target"><div style="anchor-name:--target">Another</div></div>'
    if fault == "important_rule":
        # The inline inset stays anchored; the important rule holds the field still.
        sheet = "<style>#field { top:50px !important }</style>"
    if fault == "rule_unused":
        # The id's static inset wins on specificity; the anchored rule comes last.
        sheet = """<style>#field { position:fixed;position-anchor:--target;left:100px;top:50px }
.down #field { top:30px }
.f { left:calc(anchor(left) + 100px);top:calc(anchor(top) + 10px) }</style>"""
    change = {
        "": "",
        "portal_x": 'field.style.left="calc(anchor(left) + 110px)"',
        "portal_y": 'field.style.top="calc(anchor(top) + 20px)"',
        "anchor_x": 'target.style.marginLeft="10px"',
        "anchor_y": 'target.style.marginTop="70px"',
        "declared_unused": 'field.style.top="40px"',
        "rule_unused": 'document.body.classList.add("down")',
        "important_rule": 'field.style.marginTop="-20px"',
    }[fault]
    name = "textarea#field.f" if fault == "rule_unused" else "textarea#field"
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(f"""<!doctype html>{sheet}<body style="margin:0"><div style="{scope}">
<div style="transform:{transform};transform-origin:left top">
<div id="scroller" style="height:140px;width:300px;overflow:auto">
<div style="width:600px;height:300px"><div id="target" style="anchor-name:--target;margin-top:60px;width:70px;height:30px">The target</div></div></div></div>
<textarea id="field" class="{"f" if fault == "rule_unused" else ""}" style="{field_style}"></textarea></div>{decoy}
<p id="evidence" style="position:absolute;left:10px;top:400px">Independent painted source</p>
<script>field.addEventListener('beforeinput',()=>{{scroller.scrollLeft+=20;scroller.scrollTop+=20;evidence.style.left='30px';{change}}})</script></body>""")
    )
    # Chrome moves the field after its anchor's scroll a frame late. The watch
    # credits that catch-up to the scroll only from a pose taken before the scroll.
    # A scroll that lands before the watch's first frame leaves it none, and Chrome
    # reports the catch-up as a layout shift of the field. The watch's frame callback
    # runs ahead of any the page registers, so a painted frame here gives it that pose.
    paint(page)
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
        assert names_move(errors, name, typing_in=name), (
            fault,
            before,
            after,
            errors,
        )
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
        assert names_move(
            errors,
            "textarea#field",
            typing_in="textarea#field" if fault == "local" else None,
        ), errors
    else:
        assert not errors, errors


@pytest.mark.parametrize("begun", ["press", "script"])
@pytest.mark.parametrize("property", ["transform", "translate"])
def test_a_pressed_transition_owns_its_travel_whichever_property_carries_it(
    browser, property, begun
):
    """A press beginning a transition of a box's translation owns the travel it
    samples, by the transform or by the individual `translate` property, as the
    floating panel's menu slides in. A later press moving the layout has that travel
    judged with its own rendering: credited where the press began it, and a move
    without input where a script did."""
    moved = {"transform": "translateX(-600px)", "translate": "-600px 0"}[property]
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote(f"""<!doctype html><body style="margin:0">
<button id="slide">Slide</button><button id="grow">Grow</button>
<div id="menu" style="margin-left:650px;width:200px;transition:{property} 3s linear"><button>Row</button><p>Menu reading</p></div>
<div id="room"></div><p>Below</p>
<script>function slideIn(){{window.from=menu.getBoundingClientRect().left;menu.style.{property}='{moved}'}}
slide.addEventListener('click',slideIn);
grow.addEventListener('click',()=>room.style.height='40px')</script>""")
    )
    paint(page)
    if begun == "press":
        page.locator("#slide").click()
    else:
        page.evaluate("slideIn()")
    page.wait_for_function("from - menu.getBoundingClientRect().left > 20")
    page.locator("#grow").click()
    page.evaluate(PAINTED)
    assert page.evaluate("menu.getAnimations()[0].playState") == "running"
    judge_watches()
    if begun == "press":
        assert take_browser_errors(page) == []
    else:
        consume_browser_errors(page, moved_within("div#menu"))


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
    assert names_move(errors, "textarea#field", typing_in="textarea#field"), (
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
    assert names_move(errors, "button#control"), errors


# Native containing blocks, not DOM ancestry, decide which overflow clips apply. The
# watch reads the containing block from `offsetParent` and the clip from the computed
# style (`clippingAxes`), so one case stands for each way Chrome answers either: a
# transform for every property that makes a fixed box's containing block, and paint
# containment for `contain: strict`.
CLIPPING_CASES = (
    # name, outer, inner, field, hit, painted, delta
    (
        "viewport-fixed",
        "width:100px;height:100px;overflow:hidden",
        "",
        "position:fixed;left:200px;top:200px",
        True,
        True,
        20,
    ),
    (
        "transformed",
        "width:100px;height:100px;overflow:hidden;transform:translateX(0)",
        "",
        "position:fixed;left:200px;top:200px",
        False,
        False,
        20,
    ),
    (
        "transparent",
        "width:100px;height:100px;overflow:hidden;opacity:0",
        "",
        "position:fixed;left:200px;top:200px",
        True,
        False,
        20,
    ),
    (
        "absolute-outer",
        "position:relative;width:500px;height:400px",
        "width:100px;height:100px;overflow:hidden",
        "position:absolute;left:200px;top:200px",
        True,
        True,
        20,
    ),
    (
        "absolute-inner",
        "position:relative;width:500px;height:400px",
        "position:relative;width:100px;height:100px;overflow:hidden",
        "position:absolute;left:200px;top:200px",
        False,
        False,
        20,
    ),
    (
        "scaled",
        "width:100px;height:100px;overflow:hidden;transform:scale(2);transform-origin:0 0",
        "",
        "position:fixed;left:75px;top:20px",
        True,
        True,
        3,
    ),
    (
        "paint-contained",
        "width:100px;height:100px;overflow:visible;contain:paint",
        "",
        "position:fixed;left:200px;top:200px",
        False,
        False,
        20,
    ),
    (
        "content-visibility",
        "width:100px;height:100px;overflow:visible;content-visibility:auto",
        "",
        "position:fixed;left:200px;top:200px",
        False,
        False,
        20,
    ),
    (
        "visible-y",
        "position:relative;width:100px;height:100px;overflow-x:clip;overflow-y:visible",
        "",
        "position:absolute;left:20px;top:200px",
        True,
        True,
        20,
    ),
    (
        "zero-height-x",
        "position:relative;width:100px;height:0;overflow-x:clip;overflow-y:visible",
        "",
        "position:absolute;left:20px;top:200px",
        True,
        True,
        20,
    ),
)


def test_native_clipping_preserves_only_painted_carry(browser, serve):
    """Each case stands alone on one page in turn: its boxes shown, the others' out of
    the box tree, so no case's field stands under another's point or clip."""
    source = leaf_page(
        "Native clipping",
        "".join(
            f'<div id="case-{name}" hidden><div id="outer-{name}" style="{outer}">'
            f'<div style="{inner}"><textarea id="field-{name}" style="{field};width:14px;'
            'height:20px"></textarea></div></div></div>'
            for name, outer, inner, field, *_ in CLIPPING_CASES
        )
        + '<div id="evidence" style="position:absolute;left:10px;top:400px;width:300px;'
        'height:30px;background:red"></div>',
        layout=None,
    )
    page = open_page(browser, serve(source))
    for name, _, _, _, hit, painted, delta in CLIPPING_CASES:
        page.evaluate(
            "name => document.getElementById(`case-${name}`).hidden = false", name
        )
        paint(page)
        field = page.locator(f"#field-{name}")
        state = field.evaluate("""async field=>{
          const box=field.getBoundingClientRect();
          const geometry=await window.__lfCheckApi();
          return {hit:document.elementFromPoint(box.x+3,box.y+3)===field,
            shown:!!geometry.shownRect(field,new Map()),
            opacity:field.checkVisibility({checkOpacity:true})};
        }""")
        assert state == {
            "hit": hit,
            "shown": hit,
            "opacity": painted or hit is False,
        }, name
        before = field.bounding_box()
        field.evaluate(
            """(field, delta)=>{
          window.nativeClipEntries=[];
          window.nativeClipObserver?.disconnect();
          window.nativeClipObserver=new PerformanceObserver(list=>nativeClipEntries.push(...list.getEntries()));
          nativeClipObserver.observe({type:'layout-shift'});
          field.style.marginLeft=delta+'px';
          evidence.style.marginLeft=evidence.style.marginLeft==='40px'?'0px':'40px';
        }""",
            delta,
        )
        page.screenshot()
        judge_watches()
        errors = take_browser_errors(page)
        assert page.evaluate("nativeClipEntries.length"), name
        after = field.bounding_box()
        assert after["x"] - before["x"] == (6 if delta == 3 else delta), name
        if painted:
            assert names_move(errors, f"textarea#field-{name}"), (name, errors)
        else:
            assert errors == [], (name, errors)
        page.evaluate(
            "name => document.getElementById(`case-${name}`).hidden = true", name
        )
        paint(page)
        judge_watches()
        assert take_browser_errors(page) == [], name


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
    typing_in = "textarea#field" if mode == "typing" else None
    assert names_move(errors, "textarea#field", typing_in=typing_in), errors


# Each fault runs the clean placement and its quiet judgement first, which is the
# control a separate faultless case would add.
@pytest.mark.parametrize("fault", ["holder", "child"])
def test_real_factory_invalidates_nonwindow_and_stopped_tenure(browser, serve, fault):
    source = leaf_page(
        "Floating tenure",
        """<p id="subject" style="position:fixed;left:100px;top:100px;width:40px;height:20px;margin:0">Anchor</p><div id="host" style="position:fixed;left:0;top:0;width:600px;height:500px"><div id="holder" style="position:fixed;left:140px;top:100px;width:100px;height:60px"><textarea id="field" style="width:80px;height:20px"></textarea></div></div><div id="evidence" style="position:fixed;left:10px;top:400px;width:300px;height:60px;background:red"></div>""",
        layout=None,
    )
    page = open_page(browser, serve(source))
    initial = page.locator("#holder").bounding_box()
    state = page.evaluate("""async()=>{
      const module=await window.__lfOverlayApi(); const ui=await module.floatingUi();const holder=document.querySelector('#holder'),subject=document.querySelector('#subject'),host=document.querySelector('#host'); let plane='page';
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
    page.evaluate(
        """fault=>{document.querySelector(fault==='child'?'#field':'#holder').style.marginLeft='80px';document.querySelector('#evidence').style.marginLeft='40px'}""",
        fault,
    )
    page.screenshot()
    judge_watches()
    errors = take_browser_errors(page)
    assert names_move(errors, "textarea#field"), errors


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
        assert names_move(errors, "textarea#field"), errors
    else:
        assert errors == [], errors
        if fault == "late":
            paint(page)
            page.evaluate("document.querySelector('#above').style.height='80px'")
            paint(page)
            judge_watches()
            errors = take_browser_errors(page)
            assert names_move(errors, "textarea#field"), errors


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
        assert names_move(errors, "textarea#field"), errors


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
<script data-lf-entry>document.currentScript.lfRenderingState = () => ({updatesSettled: false, preparationsSettled: true});</script>
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
        consume_browser_errors(
            page,
            {
                "code": "typing-moved",
                "field": "textarea#field",
                "node": "textarea#field",
            },
        )


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
        error = next(
            e
            for e in errors
            if is_problem(e, {"code": "moved-without-input", "node": "textarea#field"})
        )
        evidence = shift_evidence(error)
        comparisons = evidence["comparisons"]
        assert any(
            term["branch"] == "native_anchor"
            and term["owner"] == "textarea#field"
            and term["inputs"]["anchor"] == "div#target"
            and term["inputs"]["after"]["top"] - term["inputs"]["before"]["top"] == -20
            and term["inputs"]["layout_stable"]
            and term["axis"] == "top"
            and term["amount"] == -20
            for comparison in comparisons
            for term in comparison["scroll_terms"]
        ), comparisons
        assert {error.code for error in errors} == {"moved-without-input"}, errors
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
        error = next(
            e
            for e in errors
            if is_problem(e, {"code": "moved-without-input", "node": "textarea#field"})
        )
        evidence = shift_evidence(error)
        if fault == "child":
            assert any(
                abs(comparison["animation_credit"]["left"]) >= 1
                and any(
                    term["owner"] == "div#panel"
                    and term["inputs"]["before"]["values"]
                    != term["inputs"]["after"]["values"]
                    for term in comparison["animation_terms"]
                )
                for comparison in evidence["comparisons"]
            ), evidence
        assert {error.code for error in errors} == {"moved-without-input"}, errors
    else:
        assert not errors, errors


FRAMES = """count => new Promise((done) => {
  const next = () => (--count ? requestAnimationFrame(next) : done());
  requestAnimationFrame(next);
})"""


# Each case restyles its own words, without moving them, through a change no DOM
# write announces, and names the words and the style it settles on, if it settles.
RESTYLES = {
    "popover": ("tip.showPopover()", "#tip", ("display", "block")),
    "custom state": ("custom.internals.states.add('on')", "#custom", None),
    "sheet text": ("sheet.replaceSync('#replaced{opacity:.5}')", "#replaced", None),
    "adopted sheet": (
        "document.adoptedStyleSheets = [sheet, rules, other]",
        "#adopted",
        None,
    ),
    "checked": ("box.checked = true", "#checked", None),
    "paused animation": ("fade.currentTime = 500", "#faded", None),
    "form reset": ("form.reset()", "#named", None),
    "range text": ("ranged.setRangeText('', 0, 1)", "#ranged", None),
    # Still running when the sensor checks: shadow trees hold their own animations.
    "shadow transition": ("inner.style.opacity = '.2'", "#host", ("opacity", "1")),
    # A rule's own declaration, which the sensor does not hear: only its check can
    # find the change.
    "unannounced": ("rules.cssRules[0].style.opacity = '.5'", "#unheard", None),
}


def restyle_page(browser):
    """The words RESTYLES changes, once the frames that load announced are read."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<!doctype html><style>
#box:checked ~ #checked, custom-words:state(on), :placeholder-shown { opacity: .5 }
</style><input type="checkbox" id="box"><p id="checked">Checked</p>
<p id="replaced">Replaced</p><p id="adopted">Adopted</p><p id="faded">Faded</p>
<p id="unheard">Unheard</p><custom-words id="custom">Custom</custom-words>
<div id="tip" popover>Tip</div><div id="host"></div>
<form id="form"><input id="named" placeholder="Name"></form>
<textarea id="ranged" placeholder="Text">x</textarea>
<script>
customElements.define("custom-words", class extends HTMLElement {
  constructor() { super(); this.internals = this.attachInternals(); }
});
window.sheet = new CSSStyleSheet();
window.other = new CSSStyleSheet();
window.rules = new CSSStyleSheet();
other.replaceSync("#adopted { opacity: .5 }");
rules.replaceSync("#unheard { opacity: 1 }");
document.adoptedStyleSheets = [sheet, rules];
window.fade = faded.animate([{opacity: 1}, {opacity: 0}], {duration: 1000, fill: "both"});
fade.pause();
named.value = "Ada";
host.attachShadow({ mode: "open" }).innerHTML =
  '<p id="inner" style="transition: opacity 3s linear">Inner</p>';
window.inner = host.shadowRoot.getElementById("inner");
</script>""")
    )
    paint(page)
    page.evaluate(FRAMES, 10)
    return page


def test_an_unchanged_frame_misses_no_restyle(browser):
    """An idle frame keeps its last reading (`shift_watch.js`, "Unchanged frames").

    A change no source announces fails the test, naming the innermost node that
    changed; each change that restyles without a DOM write is announced, so the
    periodic full reading finds nothing. The unannounced change runs first, while
    nothing animates; the announced ones then run in turn on the same page, the shadow
    transition last so it is still running when the sensor checks.
    """
    page = restyle_page(browser)
    for call, (script, words, settled) in [
        ("unannounced", RESTYLES["unannounced"]),
        *((call, case) for call, case in RESTYLES.items() if call != "unannounced"),
    ]:
        page.evaluate(script)
        expect(page.locator(words)).to_have_css(*(settled or ("opacity", "0.5")))
        if call == "unannounced":
            # More frames than the sensor's check interval.
            page.evaluate(FRAMES, 90)
            judge_watches()
            consume_browser_errors(
                page,
                {
                    "code": "shift-watch-missed",
                    "node": "#text in p#unheard",
                    "changed": ["opacity"],
                    "others": 1,
                },
            )
    page.evaluate(FRAMES, 90)
    judge_watches()


def test_unavailable_computed_padding_keeps_an_unchanged_reading(browser):
    """A native media source has no computed padding, even while connected."""
    page = browser.new_page()
    page.goto(
        "data:text/html," + quote('<!doctype html><audio><source id="source"></audio>')
    )
    assert page.locator("#source").evaluate("""node => {
      const style = getComputedStyle(node);
      return [style.paddingTop, style.paddingBottom];
    }""") == ["", ""]
    paint(page)
    page.evaluate(FRAMES, 4)
    judge_watches()


def test_the_verdict_checks_a_change_the_test_ends_on(browser):
    """A test that ends before the periodic check still has its last unannounced
    change found (`shift_watch.js`, "Unchanged frames")."""
    page = restyle_page(browser)
    page.evaluate(RESTYLES["unannounced"][0])
    judge_watches()
    consume_browser_errors(
        page,
        {
            "code": "shift-watch-missed",
            "node": "#text in p#unheard",
            "changed": ["opacity"],
        },
    )


# Each case moves the words below #field's holder with a change the sensor may not
# announce; the shift Chrome paints still has its verdict.
UNHEARD_SHIFTS = {
    "shadow transition": "grow.style.height = '200px'",
    "form reset": "form.reset()",
    "range text": "sized.setRangeText(LINES.slice(0, 4), 0, 0)",
    "unheard rule": "rules.cssRules[0].style.height = '24px'",
}


@pytest.mark.parametrize("change", UNHEARD_SHIFTS)
def test_a_shift_is_judged_on_complete_readings(browser, change):
    """A layout-shift entry makes the reading that judges it complete
    (`shift_watch.js`, "Unchanged frames"), so no announcement list decides whether
    a shift without input is found."""
    page = browser.new_page()
    page.goto(
        "data:text/html,"
        + quote("""<!doctype html><body style="margin:0">
<div id="host"></div><div id="ruled"></div>
<form id="form"><textarea id="sized" style="field-sizing:content;display:block">
</textarea></form>
<p id="below">Words below</p>
<script>
host.attachShadow({ mode: "open" }).innerHTML =
  '<div id="grow" style="height:10px;transition:height 450ms linear"></div>';
window.grow = host.shadowRoot.getElementById("grow");
window.rules = new CSSStyleSheet();
rules.replaceSync("#ruled { height: 10px }");
document.adoptedStyleSheets = [rules];
window.LINES = String.fromCharCode(10).repeat(6);
sized.value = LINES;
</script>""")
    )
    paint(page)
    page.evaluate(FRAMES, 10)
    page.evaluate(UNHEARD_SHIFTS[change])
    page.evaluate(FRAMES, 40)
    judge_watches()
    errors = take_browser_errors(page)
    assert any(error.code == "moved-without-input" for error in errors), errors
    # The unheard rule is also the sensor's own finding when its periodic check
    # happens to fall on the frame after the change, before the paint is heard.
    allowed = {"moved-without-input"} | (
        {"shift-watch-missed"} if change == "unheard rule" else set()
    )
    assert {error.code for error in errors} <= allowed, errors
