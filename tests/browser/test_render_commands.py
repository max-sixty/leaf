"""Render, shot, and browser-gate command tests."""

import hashlib
import json
import os
import re
import subprocess

import pytest
from conftest import LEAF_COMMAND
from interact_support import (
    add_test_widget,
    append_carried_log_record,
    wait_for,
)
from playwright.sync_api import expect
from render_cases_layout import (
    BADGE_CHROME,
    SHORT_CHIP_PAGE,
    SHOT_PAGE,
    SHOT_SRC,
    SHOTS,
    shown_frames,
    solid_png,
)
from render_harness import (
    CARRIED_PAGE,
    EXAMPLE_PACKAGES,
    INLINE_PAGE,
    LONG_PAGE,
    REPLY_HOST_PAGE,
    SAMPLE_MARKUP,
    SAMPLE_TEXT,
    consume_browser_errors,
    holding,
    leaf_page,
    open_page,
    opened_tab,
    page_registry,
    primed,
    resized,
    scroll_settled,
    select,
)

from browser.threads import open_panel_thread
from leaf import event_log as events_model
from leaf import render_checks as render_checks_model
from leaf.render_gate import browser as browser_model
from leaf.render_gate import version as render_gate_model

pytestmark = pytest.mark.shifts_unsurveyed


def unnamed_browser():
    """This process's environment with every browser variable cleared, for a child
    whose subject is the launch a host that named none gets.

    Unnaming means clearing all of them, not leaf's alone: `named_executable` reads
    three, and empty is none in each. The GitHub runner image really does export
    CHROME_BIN, so a test that cleared one and inherited the rest would run the named
    arm twice and never reach the channel it meant to check."""
    return os.environ | dict.fromkeys(browser_model.VARIABLES, "")


def test_a_driver_that_never_starts_is_reported_rather_than_raised(serve, tmp_path):
    """Driver startup failures become an unavailable render check, before a reader runs."""
    serve(LONG_PAGE)
    d = serve.page_dir
    silent = tmp_path / "not-a-node"
    silent.write_text("#!/bin/sh\nexit 1\n")
    silent.chmod(0o755)
    missing = tmp_path / "no-node-here"

    def answered(result, reason):
        assert result.returncode == 0, result.stdout + result.stderr
        report = json.loads(result.stdout)
        assert report["status"] == 0
        assert report["browser"]["asked"] == ["render check"]
        assert report["browser"]["ran"] == []
        unavailable = report["browser"]["unavailable"]
        assert "Playwright's driver did not start: " in unavailable
        assert reason in unavailable

    def ran(node, *command):
        return subprocess.run(
            [*LEAF_COMMAND, *command],
            capture_output=True,
            text=True,
            check=False,
            env=os.environ | {"PLAYWRIGHT_NODEJS_PATH": str(node)},
        )

    ended = "Connection closed while reading from the driver"
    answered(ran(silent, "page", "check", str(d), "--render"), ended)
    answered(
        ran(missing, "page", "check", str(d), "--render"),
        "No such file or directory",
    )


@pytest.mark.parametrize("touch", [False, True])
def test_shot_controls_have_disjoint_targets_and_labels_stay_passive(
    scrollbar_browser, serve, touch
):
    """Controls and image taps work on touch; source labels stay passive."""
    browser = scrollbar_browser
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=touch
    )
    page = open_page(
        browser,
        serve(SHOT_PAGE, media={SHOT_SRC[n]: d for n, d in SHOTS.items()}),
        context=context,
        # A classic track changes the stage's available width when its view changes.
        # This sheet models the platform outside Leaf's authored-CSS isolation.
        init_script="""(() => {
          const sheet = new CSSStyleSheet();
          sheet.replaceSync('.lf-shotstage::-webkit-scrollbar { width: 15px; height: 15px; }');
          document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
        })()""",
    )
    shot = page.locator("lf-shot")

    def assert_source_words():
        reading = shot.evaluate("""async node => {
          const {says} = await import('/runtime/widget-api.js');
          const labels = [...node.querySelectorAll('.lf-shotcap')]
            .filter(label => label.checkVisibility());
          return {whole: says(node), visible: labels.map(label =>
            ({text: label.textContent, said: says(label)}))};
        }""")
        assert len(reading["visible"]) == 2
        assert reading["whole"] == " ".join(
            label["text"] for label in reading["visible"]
        )
        for label in reading["visible"]:
            assert label["said"] == label["text"]

    assert_source_words()
    expect(shot).to_have_attribute("data-lf-shot-mode", "flip")
    assert_source_words()
    assert (
        shot.locator(".lf-shotstage").evaluate(
            "node => node.offsetWidth - node.clientWidth"
        )
        == 15
    )
    toolbar = shot.locator(".lf-shot-toolbar")
    toolbar.scroll_into_view_if_needed()
    controls = toolbar.get_by_role("button").all()
    controls = [control for control in controls if control.is_visible()]
    boxes = [control.bounding_box() for control in controls]
    assert len(boxes) == 5
    floor = 44 if touch else 24
    for index, box in enumerate(boxes):
        assert box["width"] >= floor - 0.5, box
        if touch:
            assert controls[index].evaluate(
                """(control, floor) => {
              const box = control.getBoundingClientRect();
              const x = box.left + box.width / 2;
              const y = box.top + box.height / 2;
              return [-1, 1].every(side => {
                const offset = side * (floor / 2 - 0.5);
                const hit = document.elementFromPoint(x, y + offset);
                return hit === control || control.contains(hit);
              });
            }""",
                floor,
            ), box
        else:
            assert box["height"] >= floor - 0.5, box
        for other in boxes[index + 1 :]:
            assert (
                box["x"] + box["width"] <= other["x"] + 0.5
                or other["x"] + other["width"] <= box["x"] + 0.5
                or box["y"] + box["height"] <= other["y"] + 0.5
                or other["y"] + other["height"] <= box["y"] + 0.5
            ), (box, other)
    captions = toolbar.locator(".lf-shotcap")
    expect(captions).to_have_text(["Before", "After"])
    label_colors = captions.evaluate_all(
        "nodes => nodes.map(n => getComputedStyle(n).color)"
    )
    label_fills = captions.evaluate_all(
        "nodes => nodes.map(n => getComputedStyle(n).backgroundColor)"
    )
    assert all(fill != "rgba(0, 0, 0, 0)" for fill in label_fills)
    for caption in captions.all():
        caption.tap() if touch else caption.click()
        expect(shot.locator("wa-comparison")).to_have_attribute("position", "50")
        expect(shot.get_by_role("button", name="Slider", exact=True)).to_have_attribute(
            "aria-pressed", "true"
        )
    # Source labels remain selectable words.
    box = captions.first.bounding_box()
    select(
        page,
        (box["x"] + 1, box["y"] + box["height"] / 2),
        (box["x"] + box["width"] - 1, box["y"] + box["height"] / 2),
    )
    assert "before" in page.evaluate("getSelection().toString()").lower()

    # Custom source names cannot borrow space from the controls at phone width.
    shot.evaluate("""node => node.inspect({labels: {
        before: 'Previous deployment with an unusually long source name',
        after: 'Current candidate with another unusually long source name'
    }})""")
    expect(captions).to_have_text(
        [
            "Previous deployment with an unusually long source name",
            "Current candidate with another unusually long source name",
        ]
    )
    assert [
        control.bounding_box() for control in controls if control.is_visible()
    ] == boxes
    toolbar_box = toolbar.bounding_box()
    for caption in captions.all():
        box = caption.bounding_box()
        assert box["width"] > 0
        assert box["x"] >= toolbar_box["x"] - 1
        assert box["x"] + box["width"] <= toolbar_box["x"] + toolbar_box["width"] + 1
    assert shot.evaluate("node => node.scrollWidth <= node.clientWidth + 1")

    comparison = shot.locator("wa-comparison")
    for endpoint in ("100", "0"):
        point = {"x": 20, "y": 40}
        comparison.tap(position=point) if touch else comparison.click(position=point)
        expect(comparison).to_have_attribute("position", endpoint)
        hidden = 1 if endpoint == "100" else 0
        expect(captions.nth(hidden)).to_have_css("background-color", "rgba(0, 0, 0, 0)")
        expect(captions.nth(1 - hidden)).to_have_css(
            "background-color", label_fills[1 - hidden]
        )
        expect(captions.nth(hidden)).not_to_have_css("color", label_colors[hidden])
        expect(captions.nth(1 - hidden)).to_have_css("color", label_colors[1 - hidden])
        expect(shot.get_by_role("button", name="Slider", exact=True)).to_have_attribute(
            "aria-pressed", "true"
        )
    handle = comparison.get_by_role("scrollbar")
    handle.focus()
    for key, position in (("End", "100"), ("Home", "0"), ("ArrowRight", "1")):
        page.keyboard.press(key)
        expect(comparison).to_have_attribute("position", position)
        for index in (0, 1):
            hidden = (index == 0 and position == "0") or (
                index == 1 and position == "100"
            )
            if hidden:
                expect(captions.nth(index)).not_to_have_css(
                    "color", label_colors[index]
                )
            else:
                expect(captions.nth(index)).to_have_css("color", label_colors[index])
    shot.get_by_role("button", name="Pair", exact=True).click()
    for index in (0, 1):
        expect(captions.nth(index)).to_have_css("color", label_colors[index])
    # Controls and the image area's top stay put; Pair may shrink the content
    # below them instead of reserving unused space for the other views.
    # This fixture ends at the widget: a shorter document may clamp scrollY.
    # Compare document coordinates rather than requiring empty space below it.
    boxes = """node => {
      const box = element => {
        const r = element.getBoundingClientRect();
        return {x: r.x, y: r.y + scrollY, width: r.width, height: r.height};
      };
      return {toolbar: box(node.querySelector('.lf-shot-toolbar')),
        controls: [...node.querySelectorAll(
          '.lf-shot-views button, .lf-shot-tools > button'
        )].map(box), stageTop: box(node.querySelector('.lf-shotstage')).y};
    }"""
    for width in (390, 500, 1000):
        page.set_viewport_size({"width": width, "height": 844})
        shot.get_by_role("button", name="Slider", exact=True).click()
        toolbar.scroll_into_view_if_needed()
        allocation = shot.evaluate(boxes)
        for view in ("Pair", "Pixels", "Slider"):
            shot.get_by_role("button", name=view, exact=True).click()
            assert shot.evaluate(boxes) == allocation, view
            page.evaluate("() => new Promise(requestAnimationFrame)")
            assert shot.evaluate(boxes) == allocation, view
            assert_source_words()
            if view == "Pair":
                unused_height = shot.evaluate("""node => {
                  const stage = node.querySelector('.lf-shotstage');
                  const style = getComputedStyle(stage);
                  return stage.clientHeight - parseFloat(style.paddingTop)
                    - parseFloat(style.paddingBottom)
                    - node.querySelector('.lf-shotcanvas').getBoundingClientRect().height;
                }""")
                assert abs(unused_height) <= 1
    # Pair takes the arrangement that draws the 2:1 captures larger on screen.
    shot.get_by_role("button", name="Pair", exact=True).click()
    for width, height, layout in (
        (1000, 844, "stack"),
        (1000, 360, "side"),
        (390, 844, "stack"),
    ):
        page.set_viewport_size({"width": width, "height": height})
        expect(shot).to_have_attribute("data-lf-shot-layout", layout)
        assert_source_words()


@pytest.mark.parametrize("touch", [False, True])
def test_shot_inspects_either_original_without_flipping_or_moving(
    browser, serve, touch
):
    """Full-page evidence stays inspectable on a phone through the shared viewer.

    Pair images are links on mouse, keyboard and touch; closing the viewer returns
    to the image without shifting the comparison. Slider gestures remain separate.
    """
    shots = {
        "before": solid_png(1200, 600, (210, 220, 235)),
        "after": solid_png(1200, 600, (235, 215, 205)),
    }
    sources = {
        state: f"/media/{hashlib.sha256(data).hexdigest()[:16]}.png"
        for state, data in shots.items()
    }
    source = SHOT_PAGE
    for state in shots:
        source = source.replace(SHOT_SRC[state], sources[state])
    context = browser.new_context(
        viewport={"width": 390 if touch else 1200, "height": 900}, has_touch=touch
    )
    page = open_page(
        browser,
        serve(source, media={sources[n]: d for n, d in shots.items()}),
        context=context,
    )
    shot = page.locator("lf-shot")
    shot.scroll_into_view_if_needed()
    expect(shot).to_have_attribute("data-lf-shot-mode", "flip")
    comparison = shot.locator("wa-comparison")
    expect(comparison).to_have_attribute("position", "50")
    viewer = page.get_by_role("dialog", name="Image preview")
    comparison.get_by_role("scrollbar").press("End")
    expect(comparison).to_have_attribute("position", "100")
    comparison.get_by_role("scrollbar").press("Home")
    expect(comparison).to_have_attribute("position", "0")
    expect(viewer).not_to_be_visible()

    shot.get_by_role("button", name="Pair", exact=True).click()
    links = shot.get_by_role("link")
    expect(links).to_have_count(2)
    before = shot.bounding_box()
    link_bounds = [link.bounding_box() for link in links.all()]
    if not touch:
        box = link_bounds[0]
        start = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.move(*start)
        page.mouse.down()
        page.mouse.move(start[0] + 40, start[1] + 20, steps=4)
        page.mouse.up()
        expect(viewer).not_to_be_visible()
    assert not page.evaluate(
        "performance.getEntriesByType('resource').some(e => e.name.includes('photoswipe'))"
    )
    for index, state in enumerate(("before", "after")):
        link = shot.get_by_role(
            "link", name=f"Open {state} image — the navigation rail"
        )
        link.scroll_into_view_if_needed()
        box = link.bounding_box()
        before = shot.bounding_box()
        floor = 44 if touch else 24
        assert min(box["width"], box["height"]) >= floor
        link.hover()
        assert link.bounding_box() == box
        assert shot.bounding_box() == before
        if touch:
            link.tap()
        elif index == 0:
            link.click()
        else:
            # Escape restored the first image; Tab reaches the second image.
            page.keyboard.press("Tab")
            expect(link).to_be_focused()
            before = shot.bounding_box()
            box = link.bounding_box()
            page.keyboard.press("Enter")
        expect(viewer).to_be_visible()
        expect(viewer.locator(".lf-media-viewer-original")).to_have_attribute(
            "href",
            re.compile(re.escape(sources[state]) + "$"),
        )
        expect(viewer.locator("img.pswp__img")).to_have_attribute(
            "alt", f"{state}: the navigation rail"
        )
        expect(viewer.locator(".lf-media-viewer-caption")).to_have_text(
            f"{state}: the navigation rail"
        )
        viewer.get_by_role("button", name="Zoom to actual size", exact=True).click()
        expect(viewer.locator("img.pswp__img")).to_have_css("width", "1200px")
        page.keyboard.press("Escape")
        expect(viewer).not_to_be_visible()
        expect(link).to_be_focused()
        expect(shot.get_by_role("button", name="Pair", exact=True)).to_have_attribute(
            "aria-pressed", "true"
        )
        assert shot.bounding_box() == before
        assert link.bounding_box() == box

    # A modified image link retains its ordinary browser destination.
    after = links.nth(1)
    original = opened_tab(
        page,
        after.evaluate("link => link.href"),
        lambda: after.click(modifiers=["ControlOrMeta"]),
    )
    assert original.url.endswith(sources["after"])
    original.close()
    expect(viewer).not_to_be_visible()
    shot.evaluate("node => node.setAttribute('alt', 'the updated rail')")
    expect(after).to_have_accessible_name("Open after image — the updated rail")
    after.click()
    expect(viewer.locator("img.pswp__img")).to_have_attribute(
        "alt", "after: the updated rail"
    )
    expect(viewer.locator(".lf-media-viewer-caption")).to_have_text(
        "after: the updated rail"
    )
    page.keyboard.press("Escape")
    expect(viewer).not_to_be_visible()
    expect(after).to_be_focused()
    if touch:
        shot.get_by_role("button", name="Image options").tap()
        shot.get_by_role("button", name="100%", exact=True).tap()
        viewport = shot.locator(".lf-shotviewport").first
        viewport.scroll_into_view_if_needed()
        box = viewport.bounding_box()
        point = {"x": box["x"] + box["width"] * 0.75, "y": box["y"] + box["height"] / 2}
        finger = page.context.new_cdp_session(page)
        for kind, points in (
            ("touchStart", [point]),
            ("touchMove", [point | {"x": point["x"] - 100}]),
            ("touchEnd", []),
        ):
            finger.send(
                "Input.dispatchTouchEvent", {"type": kind, "touchPoints": points}
            )
        page.wait_for_function(
            "node => node.scrollLeft > 0", arg=viewport.element_handle()
        )
        scroll_settled(page)
        expect(viewer).not_to_be_visible()
        finger.detach()
    page.emulate_media(media="print")
    assert shown_frames(page) == ["before", "after"]


def test_a_shot_compares_pixels_inside_an_opaque_live_sample(browser, serve):
    """Sample media grants pixel reads so comparison outlines can settle."""
    after = solid_png(600, 300, (210, 220, 235), (200, 90, 100, 30, (20, 30, 40)))
    after_url = f"/media/{hashlib.sha256(after).hexdigest()[:16]}.png"
    source = leaf_page(
        "Compare captured pixels in practice",
        "<h1>Compare captured pixels in practice</h1>"
        '<lf-sample id="practice" label="Practice comparison" window>'
        '<template id="practice-source" data-sample>'
        "<h1>Inspect the changed region</h1>"
        f'<lf-shot id="sample-shot" alt="a changed run list" '
        f'before="{SHOT_SRC["before"]}" after="{after_url}"></lf-shot>'
        "</template></lf-sample>",
    )
    page = open_page(
        browser,
        serve(source, media={SHOT_SRC["before"]: SHOTS["before"], after_url: after}),
    )
    sample = page.locator("#practice")
    sample.evaluate("async sample => await sample.ready")
    child = sample.locator("iframe").element_handle().content_frame()
    assert child.evaluate("self.origin") == "null"
    shot = child.locator("#sample-shot")
    reading = shot.evaluate("async shot => await shot.difference")
    assert reading["regions"]
    shot.get_by_role("button", name="Outline changes", exact=True).click()
    expect(shot.locator(".lf-shotdiff > span").first).to_be_visible()


def test_a_tall_shot_drags_where_it_was_grabbed_without_moving_the_page(browser, serve):
    """Dragging a tall comparison stays under the pointer on a desk and phone."""
    before = solid_png(390, 700, (232, 226, 213))
    after = solid_png(390, 844, (214, 226, 235))
    url = serve(
        SHOT_PAGE,
        media={SHOT_SRC["before"]: before, SHOT_SRC["after"]: after},
    )
    page = open_page(browser, url)
    page.locator("lf-shot").get_by_role("button", name="Slider", exact=True).click()
    comparison = page.locator("lf-shot wa-comparison")
    handle = comparison.get_by_role("scrollbar")
    expect(handle).to_have_accessible_name("Before and after — the navigation rail")

    for width in (1200, 390):
        resized(page, width, 900)
        comparison.evaluate("node => { node.position = 50; }")
        page.evaluate(
            """() => { const r = document.querySelector('lf-shot .lf-shotframe')
                                  .getBoundingClientRect();
                       document.scrollingElement.scrollBy(0, r.top - 140); }"""
        )
        box = comparison.bounding_box()
        handle_box = handle.bounding_box()
        image_heights = comparison.locator("img").evaluate_all(
            "nodes => nodes.map(node => node.getBoundingClientRect().height)"
        )
        assert box is not None and handle_box is not None
        assert box["height"] >= max(image_heights) - 1
        divider = (
            handle_box["x"] + handle_box["width"] / 2,
            box["y"] + 80,
        )
        # Reading the image keeps the handle faint; aiming at it brings it up.
        page.mouse.move(box["x"] + 20, box["y"] + 40)
        expect(handle).to_have_css("opacity", "0.52")
        handle.hover()
        expect(handle).to_have_css("opacity", "1")
        scroll_before = page.evaluate("document.scrollingElement.scrollTop")
        page.mouse.move(*divider)
        page.mouse.down()
        page.mouse.move(divider[0] + 24, divider[1], steps=3)
        expect(handle).to_have_css("opacity", "1")
        page.mouse.up()
        scroll_settled(page)
        assert 50 < float(comparison.get_attribute("position")) < 100
        expect(page.get_by_role("dialog", name="Image preview")).not_to_be_visible()
        assert (
            abs(page.evaluate("document.scrollingElement.scrollTop") - scroll_before)
            <= 1
        )


@pytest.mark.parametrize("holder", ["tabs", "pane"])
def test_a_tall_shot_scrolls_its_images_then_chains_to_its_container(
    browser, serve, holder
):
    """Captured pixels scroll under stable controls; an edge releases the outer page."""
    before = solid_png(390, 1200, (232, 226, 213))
    after = solid_png(390, 1200, (214, 226, 235))
    shot = f'<lf-shot id="scroll-shot" alt="a tall comparison" before="{SHOT_SRC["before"]}" after="{SHOT_SRC["after"]}"></lf-shot>'
    shot = f'<div style="block-size:500px;--lf-full-height:1">{shot}</div>'
    tail = '<p style="min-height:1200px">Reading after the comparison.</p>'
    markup = (
        f'<lf-tabs id="scroll-tabs"><lf-tab id="scroll-pair" label="Comparison">{shot}{tail}</lf-tab>'
        '<lf-tab id="scroll-other" label="Other"><p>Another view.</p></lf-tab></lf-tabs>'
        if holder == "tabs"
        else f'<lf-pane id="scroll-pane" label="Comparison"><header>Comparison</header><section>{shot}{tail}</section></lf-pane>'
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Scroll captures",
                markup,
                **({"layout": "workspace"} if holder == "pane" else {}),
            ),
            media={SHOT_SRC["before"]: before, SHOT_SRC["after"]: after},
        ),
    )
    shot = page.locator("#scroll-shot")
    shot.get_by_role("button", name="Pair", exact=True).click()
    allocation = shot.locator(".lf-shotstage").bounding_box()
    fitted = [frame.bounding_box() for frame in shot.locator(".lf-shotframe").all()]
    assert len(fitted) == 2
    assert fitted[0]["y"] == pytest.approx(fitted[1]["y"], abs=1)
    for frame in fitted:
        assert frame["y"] >= allocation["y"] - 1
        assert (
            frame["y"] + frame["height"] <= allocation["y"] + allocation["height"] + 1
        )
    shot.get_by_role("button", name="Image options").click()
    shot.get_by_role("button", name="100%", exact=True).click()
    stage = shot.locator(".lf-shotviewport").first
    stage.scroll_into_view_if_needed()
    assert stage.evaluate("node => node.scrollHeight > node.clientHeight")
    rail = shot.locator(".lf-shot-toolbar")
    rail_before = rail.bounding_box()
    outer = (
        page.locator("#scroll-pane > section")
        if holder == "pane"
        else page.locator("html")
    )
    outer_before = outer.evaluate("node => node.scrollTop")
    stage.hover()
    page.mouse.wheel(0, 150)
    page.wait_for_function(
        "document.querySelector('#scroll-shot .lf-shotviewport').scrollTop > 0"
    )
    scroll_settled(page)
    assert outer.evaluate("node => node.scrollTop") == pytest.approx(
        outer_before, abs=1
    )
    assert rail.bounding_box() == pytest.approx(rail_before, abs=1)
    expect(shot.locator(".lf-shotviewport").last).to_have_js_property(
        "scrollTop", stage.evaluate("node => node.scrollTop")
    )
    stage.evaluate("node => { node.scrollTop = node.scrollHeight; }")
    scroll_settled(page)
    stage.hover()
    page.mouse.wheel(0, 350)
    page.wait_for_function(
        "({holder, before}) => (holder === 'pane' ? document.querySelector('#scroll-pane > section') : document.scrollingElement).scrollTop > before",
        arg={"holder": holder, "before": outer_before},
    )
    scroll_settled(page)


def test_a_shot_keeps_its_reserved_frame_while_images_load(browser, serve):
    """Upgrading the controls cannot collapse the image allocation before decode."""
    url = serve(SHOT_PAGE, media={SHOT_SRC[n]: data for n, data in SHOTS.items()})
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    modules, images = [], []
    page.route("**/widgets/lf-shot.js", lambda route: modules.append(route))
    page.route("**/media/*.png", lambda route: images.append(route))
    page.goto(url, wait_until="domcontentloaded")
    holding(page, modules, 1, "the screenshot widget before upgrade")
    shot = page.locator("lf-shot")
    page.wait_for_function(
        "getComputedStyle(document.querySelector('lf-shot')).display === 'flex'"
    )
    before = shot.bounding_box()
    assert before["height"] > 100, before
    for route in modules:
        route.continue_()
    page.unroute("**/widgets/lf-shot.js")
    expect(shot.locator(".lf-shotframe img")).to_have_count(2)
    holding(page, images, 2, "both screenshot image responses")
    pending = shot.bounding_box()
    assert shot.locator("img").evaluate_all(
        "images => images.every(image => image.naturalWidth === 0)"
    )
    for route in images:
        route.continue_()
    page.unroute("**/media/*.png")
    render_checks_model.wait_until_ready(page)
    expect(shot.locator(".lf-shotframe").first).to_be_visible()
    complete = shot.bounding_box()
    assert pending == pytest.approx(before, abs=1), (before, pending, complete)
    assert complete == pytest.approx(before, abs=1), (before, pending, complete)


def test_a_shot_keeps_its_default_slider_stable_while_the_divider_loads(browser, serve):
    """Slider reserves one image from first drawing; Pair stays usable during loading."""
    source = leaf_page(
        "Request a divider",
        f'<h1>Request a divider</h1><lf-shot id="deferred-pair" alt="a pair" before="{SHOT_SRC["before"]}" after="{SHOT_SRC["after"]}"></lf-shot>',
    )
    url = serve(source, media={SHOT_SRC[n]: data for n, data in SHOTS.items()})
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    held = []
    page.route("**/vendor/webawesome.esm.js", lambda route: held.append(route))
    page.goto(url, wait_until="domcontentloaded")
    holding(page, held, 1, "the default comparison divider")
    shot = page.locator("lf-shot")
    views = shot.get_by_role("group", name="Comparison view")
    expect(views.get_by_role("button", name="Slider", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(shot).to_have_attribute("data-lf-shot-mode", "flip")
    expect(shot.locator("wa-comparison")).to_have_count(0)
    images = shot.locator(".lf-shotframe img")
    for image in images.all():
        expect(image).to_be_visible()
    pending = [image.bounding_box() for image in images.all()]
    assert len(pending) == 2
    assert pending[0] == pytest.approx(pending[1], abs=1)
    reserved = shot.bounding_box()
    views.get_by_role("button", name="Pair", exact=True).click()
    expect(shot).to_have_attribute("data-lf-shot-mode", "compare")
    paired = [image.bounding_box() for image in images.all()]
    assert paired[1]["y"] >= paired[0]["y"] + paired[0]["height"], paired
    views.get_by_role("button", name="Slider", exact=True).click()
    for route in held:
        route.continue_()
    page.unroute("**/vendor/webawesome.esm.js")
    render_checks_model.wait_until_ready(page)
    comparison = shot.locator("wa-comparison")
    expect(comparison).to_have_attribute("position", "50")
    assert shot.bounding_box() == pytest.approx(reserved, abs=1)
    for image, box in zip(images.all(), pending, strict=True):
        assert image.bounding_box() == pytest.approx(box, abs=1)
    handle = comparison.get_by_role("scrollbar")
    handle.press("Home")
    handle.press("ArrowRight")
    position = comparison.get_attribute("position")
    views.get_by_role("button", name="Pixels", exact=True).click()
    views.get_by_role("button", name="Slider", exact=True).click()
    expect(comparison).to_have_attribute("position", position)


def test_a_shot_owns_cropped_inspection_and_preserves_choices_when_metadata_changes(
    browser, serve
):
    """One CSS-pixel crop and scale apply to paired images, slider and pixel masks."""
    before = solid_png(600, 300, (210, 220, 235))
    after = solid_png(600, 300, (210, 220, 235), patch=(120, 70, 40, 30, (30, 30, 30)))
    sources = {
        "before": f"/media/{hashlib.sha256(before).hexdigest()[:16]}.png",
        "after": f"/media/{hashlib.sha256(after).hexdigest()[:16]}.png",
    }
    source = leaf_page(
        "Inspect a focus",
        f'<h1>Inspect a focus</h1><lf-shot id="inspected-pair" alt="a focused change" before="{sources["before"]}" after="{sources["after"]}"></lf-shot>',
    )
    page = open_page(
        browser,
        serve(source, media={sources["before"]: before, sources["after"]: after}),
    )
    shot = page.locator("#inspected-pair")
    expect(shot.get_by_role("checkbox", name="Full frame", exact=True)).to_have_count(0)
    shot.evaluate(
        "node => node.inspect({pixelRatio: 2, captureWidth: 300, focus: {x: 5, y: 25, width: 100, height: 50}, labels: {before: 'Base', after: 'Candidate'}})"
    )
    shot.get_by_role("button", name="Image options").click()
    full = shot.get_by_role("checkbox", name="Full frame", exact=True)
    expect(full).not_to_be_checked()
    page.keyboard.press("Escape")
    shot.get_by_role("button", name="Image options").click()
    shot.get_by_role("button", name="100%", exact=True).click()
    expect(
        shot.get_by_role("button", name="100%", exact=True, include_hidden=True)
    ).to_have_attribute("aria-pressed", "true")
    image = shot.locator(".lf-shotframe .lf-shotimage").first
    assert image.bounding_box()["width"] == pytest.approx(100, abs=1)
    assert image.bounding_box()["height"] == pytest.approx(50, abs=1)
    img = image.locator("img")
    assert img.bounding_box()["width"] == pytest.approx(300, abs=1)
    assert img.bounding_box()["x"] == pytest.approx(
        image.bounding_box()["x"] - 5, abs=1
    )
    assert img.bounding_box()["y"] == pytest.approx(
        image.bounding_box()["y"] - 25, abs=1
    )
    views = shot.get_by_role("group", name="Comparison view")
    for direction in ("ltr", "rtl"):
        shot.evaluate("(node, direction) => node.dir = direction", direction)
        for view in ("Slider", "Pixels", "Pair"):
            views.get_by_role("button", name=view, exact=True).click()
            expect(
                shot.get_by_role("button", name="100%", exact=True, include_hidden=True)
            ).to_have_attribute("aria-pressed", "true")
            viewport = shot.locator(".lf-shotpixels") if view == "Pixels" else image
            assert viewport.evaluate(
                "node => [node.clientWidth, node.clientHeight]"
            ) == [
                100,
                50,
            ]
            source_box = viewport.locator(".lf-shotplane").bounding_box()
            assert source_box["x"] == pytest.approx(
                viewport.bounding_box()["x"] - 5, abs=1
            ), (direction, view)
            assert source_box["y"] == pytest.approx(
                viewport.bounding_box()["y"] - 25, abs=1
            ), (direction, view)
    shot.get_by_role("button", name="Image options").click()
    full.check()
    assert image.bounding_box()["width"] == pytest.approx(300, abs=1)
    assert image.bounding_box()["height"] == pytest.approx(150, abs=1)
    full.uncheck()
    full.focus()
    shot.evaluate(
        "node => node.inspect({pixelRatio: 2, captureWidth: 300, focus: {x: 5, y: 25, width: 100, height: 50}, labels: {before: 'Previous', after: 'Current'}})"
    )
    expect(full).to_be_focused()
    expect(full).not_to_be_checked()
    expect(
        shot.get_by_role("button", name="100%", exact=True, include_hidden=True)
    ).to_have_attribute("aria-pressed", "true")
    expect(
        shot.locator('.lf-shot-toolbar .lf-shotcap[data-lf-state="before"]')
    ).to_contain_text("Previous")


def test_a_shot_fits_both_wide_captures_and_retains_actual_scale_across_views(
    browser, serve
):
    """Paired fitting uses the capture and available box; actual size never fits down."""
    data = {
        "before": solid_png(1200, 400, (210, 220, 235)),
        "after": solid_png(1200, 400, (235, 215, 205)),
    }
    sources = {
        state: f"/media/{hashlib.sha256(value).hexdigest()[:16]}.png"
        for state, value in data.items()
    }
    source = leaf_page(
        "Wide pair",
        f'<h1>Wide pair</h1><div style="block-size:500px;--lf-full-height:1"><lf-shot id="wide-pair" alt="a wide pair" before="{sources["before"]}" after="{sources["after"]}"></lf-shot></div>',
    )
    page = open_page(
        browser,
        serve(source, media={sources[state]: value for state, value in data.items()}),
    )
    resized(page, 695, 900)
    shot = page.locator("#wide-pair")
    shot.get_by_role("button", name="Pair", exact=True).click()
    controls = [
        shot.get_by_role("button", name=name, exact=True)
        for name in (
            "Pair",
            "Slider",
            "Pixels",
            "Image options",
            "Outline changes",
        )
    ]
    control_boxes = [control.bounding_box() for control in controls]
    assert max(box["y"] for box in control_boxes) < min(
        box["y"] + box["height"] for box in control_boxes
    ), control_boxes
    stage = shot.locator(".lf-shotstage")
    assert stage.evaluate(
        "node => node.scrollHeight <= node.clientHeight + 1 && node.scrollWidth <= node.clientWidth + 1"
    )
    frames = shot.locator(".lf-shotframe")
    before, after = [frame.bounding_box() for frame in frames.all()]
    assert after["y"] >= before["y"] + before["height"]
    assert after["x"] == pytest.approx(before["x"], abs=1)
    stage_box = stage.bounding_box()
    assert before["y"] >= stage_box["y"] - 1
    assert after["y"] + after["height"] <= stage_box["y"] + stage_box["height"] + 1
    assert after["y"] + after["height"] <= 900
    assert frames.first.locator("img").bounding_box()["width"] <= 650
    shot.get_by_role("button", name="Image options").click()
    shot.get_by_role("button", name="100%", exact=True).click()
    expect(
        shot.get_by_role("button", name="100%", exact=True, include_hidden=True)
    ).to_have_attribute("aria-pressed", "true")
    assert [control.bounding_box() for control in controls] == control_boxes
    headers = shot.locator(".lf-shot-frame-label").all()
    header_boxes = [header.bounding_box() for header in headers]
    panes = shot.locator(".lf-shotviewport")
    assert panes.first.bounding_box()["width"] == pytest.approx(
        stage.evaluate("""node => {
          const style = getComputedStyle(node);
          return node.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
        }""")
        - 2,
        abs=2,
    )
    panes.first.hover()
    page.mouse.wheel(180, 0)
    page.wait_for_function(
        "document.querySelector('#wide-pair .lf-shotviewport').scrollLeft > 0"
    )
    scroll_settled(page)
    expect(panes.last).to_have_js_property(
        "scrollLeft", panes.first.evaluate("node => node.scrollLeft")
    )
    assert [header.bounding_box() for header in headers] == header_boxes
    assert stage.evaluate("node => node.scrollTop === 0 && node.scrollLeft === 0")
    for view in ("Slider", "Pixels", "Pair"):
        shot.get_by_role("button", name=view, exact=True).click()
        expect(shot).to_have_attribute(
            "data-lf-shot-mode",
            {"Slider": "flip", "Pixels": "pixels", "Pair": "compare"}[view],
        )
        expect(
            shot.get_by_role("button", name="100%", exact=True, include_hidden=True)
        ).to_have_attribute("aria-pressed", "true")
        assert [control.bounding_box() for control in controls] == control_boxes
        image = (
            shot.locator(".lf-shotpixels img")
            if view == "Pixels"
            else frames.first.locator("img")
        )
        assert image.bounding_box()["width"] == pytest.approx(1200, abs=1)
        scroller = shot.locator(
            ".lf-shotviewport" if view == "Pair" else ".lf-shotstage"
        ).first
        assert scroller.evaluate("node => node.scrollWidth > node.clientWidth")
    shot.get_by_role("button", name="Image options").click()
    shot.get_by_role("button", name="Fit", exact=True).click()
    for mode in ("Slider", "Pixels"):
        shot.get_by_role("button", name=mode, exact=True).click()
        expect(shot).to_have_attribute(
            "data-lf-shot-mode", {"Slider": "flip", "Pixels": "pixels"}[mode]
        )
        assert [control.bounding_box() for control in controls] == control_boxes
        shot.get_by_role("button", name="Pair", exact=True).click()
        rendered = [frame.bounding_box() for frame in frames.all()]
        stage_box = stage.bounding_box()
        for frame in rendered:
            assert frame["y"] >= stage_box["y"] - 1
            assert (
                frame["y"] + frame["height"] <= stage_box["y"] + stage_box["height"] + 1
            )
        assert stage.evaluate(
            "node => node.scrollHeight <= node.clientHeight + 1 && node.scrollWidth <= node.clientWidth + 1"
        )


def test_a_shot_outlines_and_explains_its_pixel_difference(browser, serve):
    """Visible view controls work by keyboard; outlines remain an independent choice."""
    plain = solid_png(600, 300, (210, 220, 235))
    patched = solid_png(
        600, 300, (210, 220, 235), patch=(420, 200, 60, 40, (30, 30, 30))
    )
    tinted = solid_png(
        600, 300, (210, 220, 235), patch=(40, 40, 60, 40, (200, 210, 225))
    )
    sources = {
        data: f"/media/{hashlib.sha256(data).hexdigest()[:16]}.png"
        for data in (plain, patched, tinted)
    }
    source = leaf_page(
        "Inspect differences",
        "<h1>Inspect differences</h1>"
        + "".join(
            f'<lf-shot id="shot-{name}" alt="{name}" before="{sources[plain]}" after="{sources[data]}"></lf-shot>'
            for name, data in (("patch", patched), ("same", plain), ("tint", tinted))
        ),
    )
    page = open_page(
        browser, serve(source, media={source: data for data, source in sources.items()})
    )
    patch = page.locator("#shot-patch")
    patch.evaluate("async node => await node.difference")
    views = patch.get_by_role("group", name="Comparison view")
    expect(views.get_by_role("button")).to_have_text(["Slider", "Pair", "Pixels"])
    pair = views.get_by_role("button", name="Pair", exact=True)
    slider = views.get_by_role("button", name="Slider", exact=True)
    pixels = views.get_by_role("button", name="Pixels", exact=True)
    expect(slider).to_have_attribute("aria-pressed", "true")
    pair.click()
    outlines = patch.get_by_role("button", name="Outline changes", exact=True)
    outlines.click()
    expect(patch.locator(".lf-shotdiff > span").first).to_be_visible()
    for mark in patch.locator(".lf-shotdiff > span").all():
        expect(mark).to_have_css("background-color", "rgba(0, 0, 0, 0)")
    readings = patch.locator(".lf-shotframe").evaluate_all("""frames => frames.map(frame => {
      const image = frame.querySelector('img').getBoundingClientRect();
      const scale = image.width / 600;
      return {state: frame.dataset.lfState, marks: [...frame.querySelectorAll('.lf-shotdiff > span')].map(mark => {
        const box = mark.getBoundingClientRect();
        return [(box.left - image.left) / scale, (box.top - image.top) / scale,
                (box.right - image.left) / scale, (box.bottom - image.top) / scale];
      })};
    })""")
    marks = {reading["state"]: reading["marks"] for reading in readings}
    assert marks["before"] == []
    [(left, top, right, bottom)] = marks["after"]
    assert left < 420 and right > 480 and top < 200 and bottom > 240
    assert right - left < 80 and bottom - top < 60
    expect(page.locator("#shot-same .lf-shot-outline")).to_have_attribute(
        "aria-description", "identical"
    )
    expect(page.locator("#shot-tint .lf-shot-outline")).to_have_attribute(
        "aria-description", "only slight changes"
    )
    expect(page.locator("#shot-same .lf-shotdiff > span")).to_have_count(0)
    expect(page.locator("#shot-tint .lf-shotdiff > span")).to_have_count(0)
    pair.click()
    page.keyboard.press("Shift+Tab")
    expect(slider).to_be_focused()
    page.keyboard.press("Space")
    expect(slider).to_have_attribute("aria-pressed", "true")
    page.keyboard.press("Tab")
    expect(pair).to_be_focused()
    page.keyboard.press("Tab")
    expect(pixels).to_be_focused()
    page.keyboard.press("Enter")
    expect(pixels).to_have_attribute("aria-pressed", "true")
    expect(outlines).to_be_disabled()
    expect(outlines).to_have_attribute("aria-pressed", "true")
    expect(patch.locator(".lf-shotpixels")).to_be_visible()
    colors = patch.locator(".lf-shotpixels .lf-shotplane > span").evaluate_all(
        "nodes => nodes.map(node => getComputedStyle(node).backgroundColor)"
    )
    assert len(colors) == 1
    options = patch.get_by_role("group", name="Image options", exact=True)
    expect(options).not_to_be_visible()
    patch.get_by_role("button", name="Image options").click()
    expect(options.locator(".lf-shot-pixel-key")).to_have_text("Changed pixels")
    expect(options.locator(".lf-shot-key-swatch")).to_have_css(
        "background-color", colors[0]
    )
    expect(options.get_by_role("link")).to_have_count(0)
    page.keyboard.press("Escape")
    expect(options).not_to_be_visible()
    expect(patch.locator(".lf-shotdiff").last).to_be_hidden()
    # Reading or pointing at evidence cannot silently switch comparison modes.
    patch.locator(".lf-shotpixels").click(position={"x": 10, "y": 10})
    expect(pixels).to_have_attribute("aria-pressed", "true")
    expect(patch.locator(".lf-shotpixels")).to_be_visible()
    pair.click()
    expect(pair).to_have_attribute("aria-pressed", "true")
    expect(outlines).to_be_enabled()
    expect(outlines).to_have_attribute("aria-pressed", "true")
    expect(patch.locator(".lf-shotdiff > span").first).to_be_visible()
    outlines.click()
    expect(patch.locator(".lf-shotdiff").last).to_be_hidden()


def stage_reach_cases(page):
    """Words and controls planted under chrome once the carried options load: a
    link and a hidden note on #c-bearer, a shown note, a chrome row and a button
    on #c-lax, and two offered controls, one below an unscrollable clip."""
    page.add_init_script(
        """addEventListener('DOMContentLoaded', () => {
          const control = document.getElementById('c-bearer');
          const link = document.createElement('a');
          link.id = 'native-link';
          link.className = 'lf-ui';
          link.href = '#h';
          link.textContent = 'Read context';
          const hidden = document.createElement('span');
          hidden.id = 'hidden-note';
          hidden.className = 'lf-ui';
          hidden.hidden = true;
          hidden.textContent = 'opens in a new tab';
          control.prepend(link, hidden);

          const option = document.getElementById('c-lax');
          const shown = document.createElement('span');
          shown.id = 'shown-note';
          shown.className = 'lf-ui';
          shown.textContent = 'opens in a new tab';
          const row = document.createElement('div');
          row.id = 'unreachable-row';
          row.className = 'lf-ui';
          row.innerHTML = '<strong>Session cookies</strong>';
          const button = document.createElement('button');
          button.id = 'unreachable-button';
          button.setAttribute('data-lf-said', '');
          button.textContent = 'Lax, host-only';
          option.prepend(shown, row, button);

          // A visible control and an otherwise identical one below an
          // unscrollable clip keep the control-reachability field non-vacuous.
          const holder = document.createElement('div');
          holder.id = 'clipped-holder';
          holder.className = 'lf-ui';
          holder.style.cssText = 'position:fixed;left:0;top:100px;width:120px;'
            + 'height:40px;overflow:hidden';
          for (const [id, words] of [['shown-offer', 'Reachable'], ['clipped-offer', 'Clipped']]) {
            const offer = document.createElement('button');
            offer.id = id;
            offer.className = 'lf-reach-control lf-ui';
            offer.setAttribute('data-lf-offer', '');
            offer.textContent = words;
            offer.style.cssText = 'display:block;height:20px;margin:0';
            if (id === 'clipped-offer') offer.style.marginTop = '40px';
            holder.append(offer);
          }
          document.body.append(holder);
        }, {once: true});"""
    )


def test_render_reads_widget_chrome_where_it_stands(
    browser, serve, tmp_path, monkeypatch
):
    """The user's reading of a page, on one page.

    The words a widget puts out of reach. A user selected a draft's heading, tried to
    comment on it, and got nothing back — twice, months apart, on the same page. The
    heading was the page's word in a row its author had marked as the runtime's, and
    `.lf-ui` is a look rather than a permission, so the class alone can't be the answer:
    the declaration goes on the label (relabel), and an undeclared word under chrome is
    reported. It is about a word the user was shown, so the check asks that first: a
    word the browser reads out and the page never paints is hidden with [hidden], the
    silence available in every root, and the same word shown is still reported. A
    visible control and an otherwise identical one below an unscrollable clip keep the
    control-reachability reading non-vacuous.

    The chrome half, asked where the nesting turns over. A widget's chrome is a
    `.lf-ui` the widget put inside itself. A widget in a message is the other way up:
    the runtime's own layer is above it and the widget has none of its own, so every
    word it holds sits under a `.lf-ui` with nothing wrong. Asking whether the *words*
    stand in a widget cannot tell those apart and accuses the second; asking whose the
    `.lf-ui` is can. One reply carries three widgets: a question, an exhibit beside it,
    and a badge whose module injects unmarked words under the chrome face. The panel
    around all three says nothing; the badge's own chrome is read exactly as it would
    be on a page. Nothing here had ever been rendered until a fixture asked the gate
    rather than the panel.

    Beside them, a pair shot captured at two widths: both frames render at the frame's
    width, so the pair is scaled by two different factors and every line lands somewhere
    new, and the flip would report that the whole page changed with nothing on screen
    to say otherwise. That is the one shot failure worth an error box rather than a
    caveat, and the gate has to hear about it, since nobody else will. The same shot
    with both frames at one width passes."""
    monkeypatch.chdir(tmp_path)
    package = tmp_path / ".leaf"
    add_test_widget(package, "lf-badge", upgrade=True)
    module = package / "widgets" / "lf-badge.js"
    source = module.read_text()
    starter = "class extends LeafElement {},"
    assert source.count(starter) == 1
    module.write_text(
        source.replace(
            starter,
            "class extends LeafElement {\n    setup() {\n"
            + BADGE_CHROME
            + "\n    }\n  },",
        )
    )
    narrow = solid_png(400, 300, (235, 215, 205))
    narrow_src = f"/media/{hashlib.sha256(narrow).hexdigest()[:16]}.png"
    pair = (
        f'<lf-shot id="shot-pair" alt="the navigation rail" before="{SHOT_SRC["before"]}"'
        f' after="{narrow_src}"></lf-shot>'
        f'<lf-shot id="shot-nav" alt="the navigation rail" before="{SHOT_SRC["before"]}"'
        f' after="{SHOT_SRC["after"]}"></lf-shot>'
    )
    start = CARRIED_PAGE.index('<lf-options id="carried">')
    carried = CARRIED_PAGE[start : CARRIED_PAGE.index("</lf-options>") + 13]
    source = REPLY_HOST_PAGE.replace("</main>", carried + pair + "</main>")
    url = serve(
        source,
        packages=(*EXAMPLE_PACKAGES, "./.leaf"),
        media={
            **{SHOT_SRC[name]: data for name, data in SHOTS.items()},
            narrow_src: narrow,
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-decision",
            "author": "user",
            "revision": 1,
            "text": "What would the alternative look like?",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-decision",
            "revision": 1,
            "text": SAMPLE_TEXT,
            "markup": SAMPLE_MARKUP + '<lf-badge id="rp-badge">Weighed.</lf-badge>',
        },
    )
    page = open_page(primed(browser, stage_reach_cases), url)
    assert (
        page.locator(
            "#native-link, #hidden-note, #shown-note, #unreachable-row, "
            "#unreachable-button"
        ).count()
        == 5
    )
    assert page.locator("#hidden-note").is_hidden()
    assert page.locator("#shown-offer, #clipped-offer").count() == 2
    assert page.locator("#shown-offer").is_visible()
    # A label inside a form control no marker can reach is the suite's question of
    # Leaf's own modules (`test_page_fixture_renders`), not the gate's.
    assert [
        said
        for said in render_checks_model.evaluate_probe(page, "wordsInFormControls")
        if said["at"] == "<lf-option id=c-lax>"
    ] == [
        {
            "code": "form-control-words",
            "at": "<lf-option id=c-lax>",
            "words": "Lax, host-only",
        }
    ]
    # The two-width pair fails soft, as the gate below is to hear.
    consume_browser_errors(page, '<lf-shot id="shot-pair"> failed')
    page.close()

    failures = render_gate_model.render_version(
        primed(browser.unwatched, stage_reach_cases), url
    ).failures
    pair = [f for f in failures if f.code == "console-error"]
    assert pair and all(
        "shot-pair" in f.values["text"]
        and "600px" in f.values["text"]
        and "400px" in f.values["text"]
        for f in pair
    ), failures
    clipped = [f for f in failures if f.code == "clipped-control"]
    assert [(f.values["id"], f.widths) for f in clipped] == [
        ("clipped-offer", (360, 1920))
    ], failures
    assert all(f.values["by"] == "<div id=clipped-holder>" for f in clipped), clipped
    words = sorted(
        {(f.code, f.at, f.values["words"]) for f in failures if f not in pair + clipped}
    )
    assert words == [
        ("chrome-words", "<lf-badge id=rp-badge>", "Sent by the reviewer"),
        ("chrome-words", "<lf-option id=c-lax>", "Session cookies"),
        ("chrome-words", "<lf-option id=c-lax>", "opens in a new tab"),
    ], failures


CONTENTS_MAP_PAGE = leaf_page(
    "Contents map",
    """
<aside class="sidebar" id="contents-sidebar"><lf-toc id="contents"></lf-toc></aside>
<h1 id="t">Contents map</h1>
<h2 id="first">First</h2><p>The first section's words.</p>
<h2 id="second">Second</h2><p>The second section's words.</p>
""",
)


def test_the_gate_passes_a_contents_map_resting_as_its_spine(browser, serve):
    """A contents map written as page-authoring.md's "Contents navigation" shows rests
    in a wide window's margin as a 24px spine whose labels reveal over the page. Held to
    the width floor of a widget that reserves a region, that spine failed the render gate
    on every such page. An overlay at rest is held to the height floor alone, so the
    page passes; the same map at the same width in the flow still fails, so what passes
    it is the resting posture and not a floor gone missing."""
    page = open_page(browser, serve(CONTENTS_MAP_PAGE))
    resized(page, 1200, 900)
    width = page.locator("lf-toc").evaluate(
        "el => Math.round(el.getBoundingClientRect().width)"
    )
    assert width < 40, (
        f"the map is {width}px, so it clears the floor and proves nothing"
    )
    assert (
        render_checks_model.evaluate_probe(page, "tinyBoxes", page_registry(page)) == []
    )

    page.add_style_tag(
        content="lf-toc { position: static !important; pointer-events: auto !important; }"
    )
    flowed = render_checks_model.evaluate_probe(page, "tinyBoxes", page_registry(page))
    page.close()
    assert [box for box in flowed if box["tag"] == "lf-toc"], (
        "a map in the flow at its spine's width reports nothing, so the floor is gone"
    )


FILM_DECLARATION = {
    tag: {
        "description": f"A <{tag}> page widget.",
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
    }
    for tag in ("lf-film", "lf-loader")
}
FILM_PAGE = LONG_PAGE.replace(
    "</main>", '<lf-film id="film"></lf-film><lf-loader id="loader"></lf-loader></main>'
)


def test_a_widget_that_fails_in_a_message_is_refused_where_a_browser_draws_it(
    browser, serve, tmp_path, headless_shell
):
    """Nothing draws a message's widgets before the user opens its thread, and the
    log freezes the message, so a thread command runs markup holding a widget only a
    browser can judge once before it posts, and refuses it with the widget's own
    error, as plain `page check` refuses a page. A host with no browser posts it
    unrun; the body its module cannot draw then reports to the author when the user
    opens its thread, naming the widget, and the author answers with a corrected
    reply."""
    url = serve(LONG_PAGE)
    d = serve.page_dir

    def post(executable):
        return subprocess.run(
            [*LEAF_COMMAND, "thread", "create", str(d), "--text", "See this."]
            + [
                "--markup",
                '<lf-chart id="t-bad"><pre>\n{ marks: [ }\n</pre></lf-chart>',
            ],
            capture_output=True,
            text=True,
            check=False,
            env=unnamed_browser() | {"LEAF_BROWSER_EXECUTABLE": executable},
        )

    refused = post(headless_shell)
    assert refused.returncode != 0, refused.stdout + refused.stderr
    refusal = json.loads(refused.stderr)["error"]
    assert refusal.startswith("comment markup doesn't draw:"), refusal
    assert '<lf-chart id="t-bad"> failed: ' in refusal
    assert not [e for e in events_model.read_events(d) if e["kind"] == "comment"]

    posted = post(str(tmp_path / "none"))
    assert posted.returncode == 0, posted.stdout + posted.stderr

    [root] = [e["id"] for e in events_model.read_events(d) if e["kind"] == "comment"]
    page = open_page(browser, url)
    view = open_panel_thread(page, root)
    expect(view.locator("#t-bad .lf-error")).to_contain_text("Unexpected token")
    report = '<lf-chart id="t-bad"> failed: '
    consume_browser_errors(page, report)
    reported = wait_for(
        lambda: [
            event["text"]
            for event in events_model.read_events(d)
            if event["kind"] == "error"
        ],
        bool,
        failure="the page never reported the chart",
    )
    assert len(reported) == 1 and reported[0].startswith(report), reported


def test_the_gate_passes_collapsed_words_that_overlap_when_visible(browser, serve):
    """Collapsing overlapping words removes them from the gate's screen reading."""
    url = serve(
        leaf_page(
            "collapsed words",
            '<h1>Collapsed words</h1><div id="collapsed" hidden="until-found">'
            '<p style="position:absolute;top:100px;left:100px;margin:0">First hidden line</p>'
            '<p style="position:absolute;top:100px;left:100px;margin:0">Second hidden line</p>'
            "</div>",
        )
    )
    page = open_page(browser, url)
    collapsed = page.locator("#collapsed")
    collapsed.evaluate("node => node.removeAttribute('hidden')")
    expect(collapsed.locator("p").first).to_be_visible()
    visible = render_checks_model.evaluate_probe(page, "coveredWords")
    assert any(
        {found["words"], found["covered"]}
        == {"First hidden line", "Second hidden line"}
        for found in visible
    ), (
        "the visible lines fell on nobody, so a gate that never looked would pass this too"
    )
    collapsed.evaluate("node => node.setAttribute('hidden', 'until-found')")
    expect(collapsed.locator("p").first).to_be_hidden()

    assert render_checks_model.evaluate_probe(page, "coveredWords") == []


def test_the_gate_passes_words_set_close_or_declared_decorative(browser, serve):
    """Display type set solid overlaps its neighbour's line box with no letter near
    another, and a faint numeral the page marks aria-hidden sits behind a label on
    purpose; neither is words drawn on words. Two labels a few pixels apart still are,
    and so is an opaque aria-hidden word over a label, words over capitals a stylesheet
    raised from lowercase, and vertical lines laid along each other."""
    url = serve(
        leaf_page(
            "close words",
            '<h1>Close words</h1><div style="position:relative;height:400px">'
            '<p id="kpi" style="font:700 44px/1 sans-serif;margin:0">'
            '1,204<span style="display:block">requests</span></p>'
            '<span aria-hidden="true" style="position:absolute;top:0;left:0;'
            'font-size:120px;opacity:.08">7</span>'
            '<p id="stacked" style="font:700 80px/.8 Arial;margin:0">HIGH<br>TYPE</p>'
            '<p id="warning" style="position:absolute;top:100px;left:400px;margin:0">'
            "Cannot proceed</p>"
            '<span aria-hidden="true" style="position:absolute;top:100px;left:400px;'
            'background:white">Decoration</span>'
            '<p id="lower" style="position:absolute;top:150px;left:400px;margin:0">'
            "One label</p>"
            '<p id="upper" style="position:absolute;top:154px;left:400px;margin:0">'
            "Another label</p>"
            '<p style="position:absolute;top:300px;left:0;margin:0;'
            'font:80px/1 Arial;text-transform:uppercase">xxxxxx</p>'
            '<p style="position:absolute;top:297px;left:0;margin:0;font:20px Arial">'
            "Over the caps</p>"
            '<p style="position:absolute;top:0;left:700px;margin:0;'
            'font:40px Arial;writing-mode:vertical-rl">MMMMMM</p>'
            '<p style="position:absolute;top:140px;left:700px;margin:0;'
            'font:40px Arial;writing-mode:vertical-rl">WWWWWW</p></div>',
        )
    )
    page = open_page(browser, url)
    found = render_checks_model.evaluate_probe(page, "coveredWords")

    assert sorted(sorted([f["words"], f["covered"]]) for f in found) == [
        ["Another label", "One label"],
        ["Cannot proceed", "Decoration"],
        ["MMMMMM", "WWWWWW"],
        ["Over the caps", "xxxxxx"],
    ], found


def test_the_gate_passes_a_page_that_carries_a_comment(browser, serve):
    """A comment on a widget's option leaves a page the gate passes
    (`test_every_table_the_theme_sets_honestly_passes_the_gate` gates one): the mark
    and the note counting the comment are the runtime's, and none of it is words the
    widget wrote.

    The pass hunting words drawn on other words holds out a control the runtime hangs out
    of flow over the page (`floating` in words.js). A control planted over the option's
    words is held out by the normal reading and reported by the reading with that hold
    disabled, so the hold is what keeps such a control from failing the page."""
    url = serve(INLINE_PAGE, anchored=[("opt-b", "quietly puts one back")])
    page = open_page(browser, url)
    # Vacuous otherwise: the gate has to be looking at a page that carries the comment.
    expect(page.locator(".lf-mark-note")).to_have_count(1)
    page.evaluate(
        """() => {
          const text = document.querySelector('#opt-b strong').firstChild;
          const range = document.createRange();
          range.selectNodeContents(text);
          const word = range.getClientRects()[0];
          const float = Object.assign(document.createElement('span'), {
            className: 'lf-ui', textContent: 'planted float',
          });
          Object.assign(float.dataset, { lfGen: '1', lfOffer: 'button' });
          Object.assign(float.style, {
            position: 'absolute', whiteSpace: 'nowrap',
            left: `${word.left + scrollX}px`, top: `${word.top + scrollY}px`,
          });
          document.body.append(float);
        }"""
    )
    held = render_checks_model.evaluate_probe(page, "coveredWords")
    reported = render_checks_model.evaluate_probe(
        page, "coveredWords", {"holdFloating": False}
    )
    page.close()
    assert held == []
    assert any(
        "planted float" in (found["words"], found["covered"]) for found in reported
    ), "the planted control covers no words, so a gate that never looked would pass too"


def test_the_gate_measures_an_inline_widget_by_its_words(browser, serve):
    """A gloss is set among the words around it, so its box is the words in it and there is
    no width it was ever going to reach. Held to the floor written for a widget that lays
    out a region, a gloss saying `£9` reads as a collapse, and the gate refuses a page with
    nothing wrong with it — for a price, which is the shortest thing an author is likely to
    put in one. A suggestion swapping one short word is the same case in a second tag,
    there because the gate dispatches on the declaration: the day the wrapper took a box
    it stood in front of this floor, and only x-inline says whose floor is whose.

    The floor a gloss does keep is the height, since a line of words is a line tall under
    any layout. Both halves are asserted, because a floor deleted outright passes the
    first on its own."""
    url = serve(SHORT_CHIP_PAGE)
    page = open_page(browser, url)
    widths = page.locator("lf-gloss").evaluate_all(
        "els => els.map(el => Math.round(el.getBoundingClientRect().width))"
    )
    assert widths and max(widths) < 40, (
        f"these glosses are {widths}px, so they clear the floor and prove nothing"
    )
    sug_width = page.locator("#sug-flag").evaluate(
        "el => Math.round(el.getBoundingClientRect().width)"
    )
    assert sug_width < 40, (
        f"the suggestion is {sug_width}px, so it clears the floor and proves nothing"
    )

    assert (
        render_checks_model.evaluate_probe(page, "tinyBoxes", page_registry(page)) == []
    ), "the gate refuses glosses and a suggestion with nothing wrong with them"

    # Asked without the declaration, the same floor flags it — so what passes the page
    # is the declaration, not a floor gone missing.
    undeclared = json.loads(json.dumps(page_registry(page)))
    del undeclared["lf-suggestion"]["x-inline"]
    assert [
        box
        for box in render_checks_model.evaluate_probe(page, "tinyBoxes", undeclared)
        if box["tag"] == "lf-suggestion"
    ], (
        "with x-inline stripped the gate stays quiet, so the floor is gone rather than declared"
    )

    # Flattened, the same glosses are a collapse and the gate says so — the reading the
    # declaration narrows rather than switches off.
    page.add_style_tag(
        content="lf-gloss { display: block; height: 2px; overflow: hidden; }"
    )
    flattened = render_checks_model.evaluate_probe(
        page, "tinyBoxes", page_registry(page)
    )
    page.close()
    assert [box for box in flattened if box["tag"] == "lf-gloss"], (
        "a gloss with no height left reports nothing, so the floor is gone rather than declared"
    )
