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
from leaf import event_log as events_model
from leaf import render_checks as render_checks_model
from leaf.render_gate import browser as browser_model
from leaf.render_gate import version as render_gate_model
from playwright.sync_api import expect
from render_cases_layout import (
    BADGE_CHROME,
    SHOT_PAGE,
    SHOT_SRC,
    SHOTS,
    shown_frames,
    solid_png,
)
from render_harness import (
    CARRIED_PAGE,
    EXAMPLE_PACKAGES,
    LONG_PAGE,
    REPLY_HOST_PAGE,
    SAMPLE_MARKUP,
    SAMPLE_TEXT,
    consume_browser_errors,
    holding,
    leaf_page,
    margins_laid_out,
    open_page,
    opened_tab,
    page_registry,
    primed,
    resized,
    scroll_settled,
    select,
)

from browser.threads import open_panel_thread

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
    """Under the browser the render gate launches sits Playwright's driver, a Node process
    leaf never names. Where it ends at startup, no launch is reached, so the guard
    that answers for a browser cannot: `sync_playwright()`'s start raises the
    connection's failed initialization, with a traceback through Playwright's
    internals. A page author reading that has been handed a leaf bug where the host
    has an old Node.

    Two hosts reach it — a glibc older than the bundled Node needs, and a
    PLAYWRIGHT_NODEJS_PATH naming a Node older than the driver bundle needs — and
    both end at the same observable point, which a stub that exits without answering
    stands in for. What the gate owes is one line: the connection's reason,
    the Node that ran, and the variable that chooses one, since neither real failure
    names that variable and it is the whole of what settles them.

    A third host names a Node it does not have, so the driver never runs at all and
    the spawn fails a step earlier than the silence above. It owes the same line,
    and it is where cleaning up after a failed start goes wrong: Playwright's stop
    asserts a transport handle that spawn never assigned, so a manager exited after
    a failed entry answers with a private of its own instead of the missing file.

    No traceback is half the subject. The shapes asserted away are the ones the
    reader sees where the gate raises instead of answering: a Playwright private,
    an unretrieved asyncio exception, and any traceback at all."""
    serve(LONG_PAGE)
    d = serve.page_dir
    silent = tmp_path / "not-a-node"
    silent.write_text("#!/bin/sh\nexit 1\n")
    silent.chmod(0o755)
    missing = tmp_path / "no-node-here"

    def answered(result, node, reason):
        assert result.returncode == 0, result.stdout + result.stderr
        report = json.loads(result.stdout)
        assert report["status"] == 0
        assert report["browser"]["asked"] == ["render check"]
        assert report["browser"]["ran"] == []
        unavailable = report["browser"]["unavailable"]
        assert "Playwright's driver did not start: " in unavailable
        assert browser_model.DRIVER_VARIABLE in unavailable
        assert str(node) in unavailable
        assert reason in unavailable
        assert result.stderr == ""
        assert "Traceback" not in result.stdout
        assert "_playwright" not in result.stdout
        assert "_output" not in result.stdout
        assert "Task exception was never retrieved" not in result.stdout

    def ran(node, *command):
        return subprocess.run(
            [*LEAF_COMMAND, *command],
            capture_output=True,
            text=True,
            check=False,
            env=os.environ | {browser_model.DRIVER_VARIABLE: str(node)},
        )

    ended = "Connection closed while reading from the driver"
    answered(ran(silent, "page", "check", str(d), "--render"), silent, ended)
    answered(
        ran(missing, "page", "check", str(d), "--render"),
        missing,
        "No such file or directory",
    )


@pytest.mark.parametrize("touch", [False, True])
def test_shot_captions_have_disjoint_targets_inside_their_rail(browser, serve, touch):
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=touch
    )
    page = open_page(
        browser,
        serve(SHOT_PAGE, media={SHOT_SRC[n]: d for n, d in SHOTS.items()}),
        context=context,
    )
    page.locator("lf-shot").get_by_role("radio", name="Slider", exact=True).click()
    rail = page.locator("lf-shot .lf-shotrail")
    caps = rail.locator(".lf-shotcap")
    rail.scroll_into_view_if_needed()
    floor = 44 if touch else 24
    boxes = [cap.bounding_box() for cap in caps.all()]
    bounds = rail.bounding_box()
    assert len(boxes) == 2
    for box in boxes:
        assert min(box["width"], box["height"]) >= floor - 0.5, box
        assert box["y"] >= bounds["y"]
        assert box["y"] + box["height"] <= bounds["y"] + bounds["height"]
    assert boxes[0]["x"] + boxes[0]["width"] <= boxes[1]["x"]
    for index, position in [(0, "100"), (1, "0")]:
        cap = caps.nth(index)
        cap.click()
        expect(page.locator("lf-shot wa-comparison")).to_have_attribute(
            "position", position
        )
        assert cap.bounding_box() == boxes[index]
    # The captions remain selectable words, rather than native buttons that swallow a drag.
    box = boxes[0]
    select(
        page,
        (box["x"] + 5, box["y"] + box["height"] / 2),
        (box["x"] + box["width"] - 5, box["y"] + box["height"] / 2),
    )
    assert "before" in page.evaluate("getSelection().toString()").lower()
    expect(page.locator("lf-shot wa-comparison")).to_have_attribute("position", "0")


@pytest.mark.parametrize("touch", [False, True])
def test_shot_inspects_either_original_without_flipping_or_moving(
    browser, serve, touch
):
    """Full-page evidence stays inspectable on a phone through the shared viewer.

    Endpoint choice, inspection, and native modified navigation are separate routes;
    closing the viewer returns to the same route without shifting the comparison.
    Every comparison view keeps the same routes to the original captures.
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
    shot.get_by_role("radio", name="Slider", exact=True).click()
    comparison = shot.locator("wa-comparison")
    expect(comparison).to_have_attribute("position", "50")
    before = shot.bounding_box()
    links = shot.get_by_role("link")
    link_bounds = [link.bounding_box() for link in links.all()]
    assert len(link_bounds) == 2
    assert link_bounds[0]["x"] + link_bounds[0]["width"] <= link_bounds[1]["x"]
    assert not page.evaluate(
        "performance.getEntriesByType('resource').some(e => e.name.includes('photoswipe'))"
    )
    viewer = page.get_by_role("dialog", name="Image preview")
    for index, state in enumerate(("before", "after")):
        link = shot.get_by_role(
            "link", name=f"Open {state} image — the navigation rail"
        )
        floor = 44 if touch else 24
        assert min(link_bounds[index]["width"], link_bounds[index]["height"]) >= floor
        link.hover()
        assert link.bounding_box() == link_bounds[index]
        link.focus()
        assert link.bounding_box() == link_bounds[index]
        assert shot.bounding_box() == before
        if touch:
            link.tap()
        else:
            link.press("Enter")
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
        expect(comparison).to_have_attribute("position", "50")
        assert shot.bounding_box() == before
        assert link.bounding_box() == link_bounds[index]

    # A modified link retains its href and ordinary browser destination.
    after = links.nth(1)
    original = opened_tab(
        page,
        after.evaluate("link => link.href"),
        lambda: after.click(modifiers=["ControlOrMeta"]),
    )
    assert original.url.endswith(sources["after"])
    original.close()
    expect(viewer).not_to_be_visible()
    expect(comparison).to_have_attribute("position", "50")

    shot.locator('.lf-shotcap[data-lf-state="before"]').click()
    expect(comparison).to_have_attribute("position", "100")
    comparison.click(position={"x": 20, "y": 40})
    expect(comparison).to_have_attribute("position", "0")
    assert shot.bounding_box() == before
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

    # Inspection links remain usable when the paired view owns the pictures.
    shot.get_by_role("radio", name="Before & after", exact=True).click()
    expect(links.first).to_be_visible()
    links.first.click()
    expect(viewer).to_be_visible()
    page.keyboard.press("Escape")
    expect(links.first).to_be_focused()
    page.emulate_media(media="print")
    expect(links.first).not_to_be_visible()
    assert shown_frames(page) == ["before", "after"]


@pytest.mark.parametrize("touch", [False, True])
def test_a_wide_shot_owns_comparison_actions_in_its_native_rail(browser, serve, touch):
    """One native rail owns endpoint actions, including in a narrow touch scroller."""
    shot = (
        f'<lf-shot id="wide-shot" alt="a captured inspector" '
        f'before="{SHOT_SRC["before"]}" after="{SHOT_SRC["after"]}"></lf-shot>'
    )
    source = leaf_page(
        "Inspect captured controls",
        '<h1>Inspect captured controls</h1><div style="overflow-x:auto;inline-size:100%">'
        f'<div style="inline-size:1280px;max-inline-size:none">{shot}</div></div>',
    )
    page = open_page(
        browser,
        serve(source, media={SHOT_SRC[n]: data for n, data in SHOTS.items()}),
        context=browser.new_context(
            viewport={"width": 360 if touch else 1440, "height": 900},
            has_touch=touch,
            is_mobile=touch,
        ),
    )
    widget = page.locator("#wide-shot")
    rail = widget.locator(".lf-shotrail")
    widget.get_by_role("radio", name="Slider", exact=True).click()
    comparison = widget.locator("wa-comparison")
    expect(comparison).to_be_visible()
    rail.scroll_into_view_if_needed()
    # Comparison chrome belongs to the rail and native divider. An extra floating
    # endpoint action could cover a Close control baked into this captured image.
    for state, position in (("before", "100"), ("after", "0")):
        caption = rail.locator(f'.lf-shotcap[data-lf-state="{state}"]')
        caption.tap() if touch else caption.press("Enter")
        expect(comparison).to_have_attribute("position", position)
        control = caption.bounding_box()
        capture = comparison.bounding_box()
        assert control["y"] + control["height"] <= capture["y"] + 0.5
        margins_laid_out(page)
        # With no annotations or external contributions, comparison actions belong
        # only to the native rail/divider, not to a second margin projection.
        expect(page.locator('[data-lf-margin-for="wide-shot"] button')).to_have_count(0)
        if touch:
            opener = rail.get_by_role(
                "link", name=f"Open {state} image — a captured inspector"
            )
            opener.tap()
            viewer = page.get_by_role("dialog", name="Image preview")
            expect(viewer).to_be_visible()
            page.keyboard.press("Escape")
            expect(viewer).not_to_be_visible()
            expect(opener).to_be_focused()
            expect(comparison).to_have_attribute("position", position)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


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
    shot.get_by_role("checkbox", name="Outline changes", exact=True).check()
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
    page.locator("lf-shot").get_by_role("radio", name="Slider", exact=True).click()
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
        scroll_before = page.evaluate("document.scrollingElement.scrollTop")
        page.mouse.move(*divider)
        page.mouse.down()
        page.mouse.move(divider[0] + 24, divider[1], steps=3)
        page.mouse.up()
        scroll_settled(page)
        assert float(comparison.get_attribute("position")) > 50
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
    shot.get_by_role("radio", name="100%", exact=True).click()
    stage = shot.locator(".lf-shotstage")
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
        "document.querySelector('#scroll-shot .lf-shotstage').scrollTop > 0"
    )
    scroll_settled(page)
    assert outer.evaluate("node => node.scrollTop") == pytest.approx(
        outer_before, abs=1
    )
    assert rail.bounding_box() == pytest.approx(rail_before, abs=1)
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


def test_a_shot_keeps_paired_images_usable_while_the_slider_loads(browser, serve):
    """The optional divider stays off paired-view startup and never leaves an empty box."""
    source = leaf_page(
        "Request a divider",
        f'<h1>Request a divider</h1><lf-shot id="deferred-pair" alt="a pair" before="{SHOT_SRC["before"]}" after="{SHOT_SRC["after"]}"></lf-shot>',
    )
    url = serve(source, media={SHOT_SRC[n]: data for n, data in SHOTS.items()})
    page = open_page(browser, url)
    shot = page.locator("lf-shot")
    views = shot.get_by_role("radiogroup", name="Comparison view")
    expect(views.locator('[aria-checked="true"]')).to_have_text("Before & after")
    assert not page.evaluate(
        "performance.getEntriesByType('resource').some(e => e.name.endsWith('/vendor/webawesome.esm.js'))"
    )
    held = []
    page.route("**/vendor/webawesome.esm.js", lambda route: held.append(route))
    views.get_by_role("radio", name="Slider", exact=True).click()
    holding(page, held, 1, "the requested comparison divider")
    expect(shot.locator("wa-comparison")).to_have_count(0)
    for image in shot.locator(".lf-shotframe img").all():
        expect(image).to_be_visible()
    views.get_by_role("radio", name="Before & after", exact=True).click()
    for route in held:
        route.continue_()
    page.unroute("**/vendor/webawesome.esm.js")
    views.get_by_role("radio", name="Slider", exact=True).click()
    comparison = shot.locator("wa-comparison")
    expect(comparison).to_have_attribute("position", "50")
    handle = comparison.get_by_role("scrollbar")
    handle.press("Home")
    handle.press("ArrowRight")
    position = comparison.get_attribute("position")
    views.get_by_role("radio", name="Pixel difference", exact=True).click()
    views.get_by_role("radio", name="Slider", exact=True).click()
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
    full = shot.get_by_role("checkbox", name="Full frame", exact=True)
    expect(full).not_to_be_checked()
    shot.get_by_role("radio", name="100%", exact=True).click()
    expect(shot.locator(".lf-shotscale")).to_contain_text("100% · CSS px")
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
    views = shot.get_by_role("radiogroup", name="Comparison view")
    for direction in ("ltr", "rtl"):
        shot.evaluate("(node, direction) => node.dir = direction", direction)
        for view in ("Slider", "Pixel difference", "Before & after"):
            views.get_by_role("radio", name=view, exact=True).click()
            expect(
                shot.get_by_role("radio", name="100%", exact=True)
            ).to_have_attribute("aria-checked", "true")
            viewport = (
                shot.locator(".lf-shotpixels") if view == "Pixel difference" else image
            )
            assert viewport.bounding_box()["width"] == pytest.approx(100, abs=1)
            assert viewport.bounding_box()["height"] == pytest.approx(50, abs=1)
            source_box = viewport.locator(".lf-shotplane").bounding_box()
            assert source_box["x"] == pytest.approx(
                viewport.bounding_box()["x"] - 5, abs=1
            ), (direction, view)
            assert source_box["y"] == pytest.approx(
                viewport.bounding_box()["y"] - 25, abs=1
            ), (direction, view)
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
    expect(shot.get_by_role("radio", name="100%", exact=True)).to_have_attribute(
        "aria-checked", "true"
    )
    expect(shot.locator('.lf-shotcap[data-lf-state="before"]')).to_contain_text(
        "Previous"
    )


def test_a_shot_stacks_wide_captures_and_retains_actual_scale_across_views(
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
        f'<h1>Wide pair</h1><div style="max-width:650px"><lf-shot id="wide-pair" alt="a wide pair" before="{sources["before"]}" after="{sources["after"]}"></lf-shot></div>',
    )
    page = open_page(
        browser,
        serve(source, media={sources[state]: value for state, value in data.items()}),
    )
    shot = page.locator("#wide-pair")
    frames = shot.locator(".lf-shotframe")
    before, after = [frame.bounding_box() for frame in frames.all()]
    assert after["y"] >= before["y"] + before["height"]
    assert after["x"] == pytest.approx(before["x"], abs=1)
    assert frames.first.locator("img").bounding_box()["width"] <= 650
    shot.get_by_role("radio", name="100%", exact=True).click()
    expect(shot.locator(".lf-shotscale")).to_contain_text("100% · image px")
    for view in ("Slider", "Pixel difference", "Before & after"):
        shot.get_by_role("radio", name=view, exact=True).click()
        expect(shot.get_by_role("radio", name="100%", exact=True)).to_have_attribute(
            "aria-checked", "true"
        )
        image = (
            shot.locator(".lf-shotpixels img")
            if view == "Pixel difference"
            else frames.first.locator("img")
        )
        assert image.bounding_box()["width"] == pytest.approx(1200, abs=1)
        assert shot.locator(".lf-shotstage").evaluate(
            "node => node.scrollWidth > node.clientWidth"
        )


def test_a_shot_outlines_and_explains_its_pixel_difference(browser, serve):
    """Views have one keyboard stop; outlines remain an independent remembered choice."""
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
    views = patch.get_by_role("radiogroup", name="Comparison view")
    expect(views.get_by_role("radio")).to_have_text(
        ["Before & after", "Slider", "Pixel difference"]
    )
    expect(views.locator('[aria-checked="true"]')).to_have_text("Before & after")
    expect(views.locator('[tabindex="0"]')).to_have_count(1)
    outlines = patch.get_by_role("checkbox", name="Outline changes", exact=True)
    outlines.check()
    expect(patch.locator(".lf-shotdiff > span").first).to_be_visible()
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
    expect(page.locator("#shot-same .lf-shotdelta")).to_have_text("identical")
    expect(page.locator("#shot-tint .lf-shotdelta")).to_have_text("only slight changes")
    expect(page.locator("#shot-same .lf-shotdiff > span")).to_have_count(0)
    expect(page.locator("#shot-tint .lf-shotdiff > span")).to_have_count(0)
    paired = views.get_by_role("radio", name="Before & after", exact=True)
    paired.click()
    paired.press("ArrowRight")
    expect(views.get_by_role("radio", name="Slider", exact=True)).to_be_focused()
    page.keyboard.press("ArrowRight")
    pixels = views.get_by_role("radio", name="Pixel difference", exact=True)
    expect(pixels).to_be_focused()
    expect(pixels).to_have_attribute("aria-checked", "true")
    expect(outlines).to_be_disabled()
    expect(outlines).to_be_checked()
    expect(patch.locator(".lf-shotpixels")).to_be_visible()
    expect(patch.locator(".lf-shotlegend")).to_be_visible()
    expect(patch.locator(".lf-shotlegend-item")).to_have_text(
        ["Before only", "After only", "Recolored"]
    )
    expect(patch.locator(".lf-shotdiff").last).to_be_hidden()
    page.keyboard.press("ArrowRight")
    expect(paired).to_be_focused()
    expect(paired).to_have_attribute("aria-checked", "true")
    expect(views.locator('[tabindex="0"]')).to_have_count(1)
    expect(outlines).to_be_enabled()
    expect(outlines).to_be_checked()
    expect(patch.locator(".lf-shotdiff > span").first).to_be_visible()
    outlines.uncheck()
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


def test_a_widget_that_fails_in_a_message_reports_when_its_thread_draws(
    browser, serve, tmp_path
):
    """A message's markup is validated as it is posted, and drawn only where a browser
    shows it, so a reply carrying a chart posts as fast as one without and needs no
    browser. A body its module cannot draw reports to the author when the user opens
    its thread, as the page's own widgets do, naming the widget; the log freezes the
    message, so the author answers with a corrected reply."""
    url = serve(LONG_PAGE)
    d = serve.page_dir
    posted = subprocess.run(
        [*LEAF_COMMAND, "thread", "open", str(d), "--text", "See this."]
        + ["--markup", '<lf-chart id="t-bad"><pre>\n{ marks: [ }\n</pre></lf-chart>'],
        capture_output=True,
        text=True,
        check=False,
        env=unnamed_browser() | {"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "none")},
    )
    assert posted.returncode == 0, posted.stdout + posted.stderr
    assert not posted.stderr, "posting asks for no browser"

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
