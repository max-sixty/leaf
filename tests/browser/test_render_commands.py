"""Render, shot, and browser-gate command tests."""

import hashlib
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
    panel_settled,
    primed,
    resized,
    scroll_settled,
    select,
)

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
        assert "· render check: not run, Playwright's driver did not start: " in (
            result.stderr
        )
        assert browser_model.DRIVER_VARIABLE in result.stderr
        assert str(node) in result.stderr
        assert reason in result.stderr
        assert "Traceback" not in result.stderr
        assert "_playwright" not in result.stderr
        assert "_output" not in result.stderr
        assert "Task exception was never retrieved" not in result.stderr

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
    A containing inspector's compare view still withdraws the complete rail.
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

    # Parent-owned inspectors select a mode through the widget's inspection API.
    shot.evaluate("node => node.inspect({mode: 'compare'})")
    expect(comparison).to_have_count(0)
    expect(links.first).not_to_be_visible()
    box = shot.locator("input.lf-shotflip")
    expect(box).to_be_checked()
    assert shown_frames(page) == ["before", "after"]
    shot.evaluate("node => node.inspect({mode: 'flip'})")
    expect(comparison).to_have_count(1)
    expect(comparison).to_have_attribute("position", "0")
    expect(links.first).to_be_visible()
    expect(box).to_be_checked()
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
        f'<lf-shot id="sample-shot" outlines alt="a changed run list" '
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
    expect(shot.get_by_role("radio", name="Outlines", exact=True)).to_have_attribute(
        "aria-description", "1 changed area"
    )
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
def test_a_tall_shot_keeps_its_endpoint_labels_in_view(browser, serve, holder):
    """The pair stays identifiable below page tabs and inside a workspace scroller."""
    before = solid_png(390, 1200, (232, 226, 213))
    after = solid_png(390, 1200, (214, 226, 235))
    shot = f'<lf-shot id="sticky-shot" alt="a tall comparison" before="{SHOT_SRC["before"]}" after="{SHOT_SRC["after"]}"></lf-shot>'
    tail = '<p style="min-height: 1200px">Reading after the comparison.</p>'
    if holder == "tabs":
        markup = leaf_page(
            "Sticky comparison",
            f'<lf-tabs id="sticky-tabs"><lf-tab id="sticky-pair" label="Comparison"><lf-tabs id="embedded-tabs"><lf-tab id="embedded-pair" label="Pair">{shot}<div id="sideways-reading" data-bound="start" style="overflow:auto; width:100%"><div style="width:2000px"><p id="embedded-destination" style="margin-left:1600px; width:200px">A passage below the comparison.</p></div></div>{tail}</lf-tab><lf-tab id="embedded-notes" label="Notes"><p>Short notes.</p></lf-tab></lf-tabs>{tail}</lf-tab>'
            '<lf-tab id="sticky-other" label="Other"><p>Another view.</p></lf-tab></lf-tabs>',
        )
    else:
        markup = leaf_page(
            "Sticky comparison",
            f'<lf-pane id="sticky-pane" label="Comparison"><header>Comparison</header><section>{shot}{tail}</section></lf-pane>',
            layout="workspace",
        )
    page = open_page(
        browser,
        serve(markup, media={SHOT_SRC["before"]: before, SHOT_SRC["after"]: after}),
    )
    resized(page, 1200, 800)
    comparison = page.locator("#sticky-shot wa-comparison")
    expect(comparison).to_be_visible()
    rail = page.locator("#sticky-shot .lf-shotrail")
    page.mouse.move(600, 350)
    page.mouse.wheel(0, 600)
    scroll_settled(page)
    reading = rail.evaluate("""rail => {
      const r = rail.getBoundingClientRect();
      const pane = rail.closest('lf-pane')?.querySelector(':scope > section');
      return {top: r.top, bottom: r.bottom,
            expected: (pane ? pane.getBoundingClientRect().top
              + parseFloat(getComputedStyle(pane).paddingTop) : 0)
          + parseFloat(getComputedStyle(rail).top)};
    }""")
    assert abs(reading["top"] - reading["expected"]) <= 1, reading
    for state, position in (("before", "100"), ("after", "0")):
        rail.locator(f'[data-lf-state="{state}"]').click()
        expect(comparison).to_have_attribute("position", position)
    scroll = page.evaluate("document.scrollingElement.scrollTop")
    page.keyboard.press("Shift+Tab")
    scroll_settled(page)
    assert abs(page.evaluate("document.scrollingElement.scrollTop") - scroll) <= 1
    if holder == "tabs":
        outer = page.locator("#sticky-tabs > .lf-tabstrip").bounding_box()
        inner = page.locator("#embedded-tabs > .lf-tabstrip").bounding_box()
        assert inner["y"] == pytest.approx(outer["y"] + outer["height"], abs=1)
        assert reading["top"] == pytest.approx(inner["y"] + inner["height"], abs=1)
        page.locator("#embedded-tabs > .lf-tabstrip").get_by_role(
            "tab", name="Notes", exact=True
        ).click()
        scroll_settled(page)
        assert (
            page.locator("#embedded-notes p").bounding_box()["y"]
            >= inner["y"] + inner["height"]
        )
        page.keyboard.press("ArrowLeft")
        scroll_settled(page)
        expect(page.locator("#embedded-pair")).to_be_visible()
        page.mouse.wheel(0, 600)
        scroll_settled(page)
        landed = page.evaluate("""async () => {
          const {scrollIntoReadingBand} = await window.__lfRuntimeImport('/runtime/landing-scroll.js');
          const {scrollToFragment} = await window.__lfRuntimeImport('/runtime/anchor-travel.js');
          const {landingBand} = await window.__lfRuntimeImport('/runtime/geometry.js');
          const passage = document.querySelector('#embedded-destination');
          const strip = document.querySelector('#embedded-tabs > .lf-tabstrip');
          scrollToFragment(passage);
          const elementTop = passage.getBoundingClientRect().top;
          const range = document.createRange();
          range.selectNodeContents(passage);
          scrollIntoReadingBand(range, passage, 'start', 'instant');
          return {elementTop, rangeTop: range.getBoundingClientRect().top,
            rangeBottom: range.getBoundingClientRect().bottom,
            landingBottom: landingBand(document.scrollingElement).bottom,
            stripBottom: strip.getBoundingClientRect().bottom,
            sidewaysVisible: passage.getBoundingClientRect().right <= document.querySelector('#sideways-reading').getBoundingClientRect().right + 1};
        }""")
        assert landed["sidewaysVisible"], landed
        assert landed["elementTop"] >= landed["stripBottom"] - 1, landed
        assert landed["rangeTop"] >= landed["stripBottom"] - 1, landed
        assert landed["rangeBottom"] <= landed["landingBottom"] + 1, landed
        page.locator("#sticky-shot").evaluate("""node => {
          const tab = document.querySelector('#sticky-tabs [role="tab"]');
          const r = tab.getBoundingClientRect();
          document.scrollingElement.scrollBy(0,
            node.getBoundingClientRect().bottom - (r.top + r.height / 2 + 5));
        }""")
        scroll_settled(page)
        assert page.locator('#sticky-tabs [role="tab"]').first.evaluate("""tab => {
          const r = tab.getBoundingClientRect();
          return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)
            ?.closest('[role="tab"]') === tab;
        }"""), "the departing comparison header covered the page tabs"
    page.locator("#sticky-shot").evaluate("node => node.scrollIntoView({block: 'end'})")
    page.mouse.wheel(0, 1000)
    scroll_settled(page)
    assert rail.bounding_box()["y"] < reading["top"] - 100


def test_a_shot_adopts_a_fallback_choice_when_the_divider_arrives(browser, serve):
    """View choices preserve the initial split; endpoint choices survive upgrade."""
    after = solid_png(600, 300, (210, 220, 235), patch=(420, 200, 60, 40, (30, 30, 30)))
    url = serve(
        SHOT_PAGE.replace("<lf-shot ", "<lf-shot outlines pixels "),
        media={SHOT_SRC["before"]: SHOTS["before"], SHOT_SRC["after"]: after},
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    held = []
    page.route("**/vendor/webawesome.esm.js", lambda route: held.append(route))
    page.goto(url, wait_until="domcontentloaded")
    holding(page, held, 1, "the deferred comparison divider")
    shot = page.locator("lf-shot")
    views = shot.get_by_role("radiogroup", name="Comparison view")
    expect(views.locator('[aria-checked="true"]')).to_have_text("Outlines")
    for view in ("Plain", "Pixels", "Plain"):
        views.get_by_role("radio", name=view, exact=True).click()
        expect(views.locator('[aria-checked="true"]')).to_have_text(view)
    expect(shot.locator("wa-comparison")).to_have_count(0)
    for route in held:
        route.continue_()
    expect(shot.locator("wa-comparison")).to_have_attribute("position", "50")
    expect(views.locator('[aria-checked="true"]')).to_have_text("Plain")

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.add_init_script(
        """new MutationObserver(() => {
          if (!document.body?.hasAttribute('data-lf-presented') || window.__lfFlipped)
            return;
          const box = document.querySelector('lf-shot input.lf-shotflip');
          if (!box) return;
          window.__lfFlipped = true;
          window.__lfHadComparison = !!document.querySelector('lf-shot wa-comparison');
          box.click();
          // The second press is a second gesture, in a task of its own as a user's is.
          setTimeout(() => {
            window.__lfHadComparison ||= !!document.querySelector('lf-shot wa-comparison');
            box.click();
            window.__lfFallbackShown = [...document.querySelectorAll('.lf-shotframe')]
              .filter(frame => getComputedStyle(frame).visibility === 'visible')
              .map(frame => frame.dataset.lfState);
          });
        }).observe(document, {attributes: true, subtree: true});"""
    )
    page.goto(url)
    comparison = page.locator("lf-shot wa-comparison")
    expect(comparison).to_have_attribute("position", "100")
    assert page.evaluate(
        "() => [window.__lfHadComparison, window.__lfFallbackShown]"
    ) == [False, ["before"]]


def test_a_shot_owns_inspection_without_a_containing_package(browser, serve):
    """A pair owns compare, crop and overlay paint, even without visual-review CSS.
    A containing inspector only chooses local view parameters and its allocation.
    """
    url = serve(
        leaf_page(
            "Inspect an aligned pair",
            f'''<h1>Inspect the pair</h1>
<button id="inspect-pair">Change inspection</button>
<lf-shot id="inspected-pair" alt="two aligned frames"
  before="{SHOT_SRC["before"]}" after="{SHOT_SRC["after"]}"></lf-shot>''',
        ),
        media={SHOT_SRC[n]: data for n, data in SHOTS.items()},
    )
    context = browser.new_context(viewport={"width": 1200, "height": 900})
    held = []
    context.route("**/media/*.png", lambda route: held.append(route))
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded")
    shot = page.locator("#inspected-pair")
    expect(shot.locator(".lf-shotframe")).to_have_count(2)
    # A supported partial request can arrive before decode and without an inspector
    # metadata cache. Delivery's own dimensions reserve the image's complete view.
    shot.evaluate("node => node.inspect({mode: 'overlay'})")
    expect(shot).to_have_attribute("data-lf-shot-mode", "overlay")
    for route in held:
        route.continue_()
    context.unroute("**/media/*.png")
    page.wait_for_function("document.body.hasAttribute('data-lf-presented')")
    page.evaluate("""() => {
      const shot = document.querySelector('#inspected-pair');
      window.inspection = {mode: 'compare', layout: 'side', scale: .5,
        pixelRatio: 1, captureWidth: 600,
        focus: {x: 100, y: 50, width: 200, height: 100}, crop: false,
        labels: {before: 'Base', after: 'Candidate'}, opacity: .35};
      document.querySelector('#inspect-pair').addEventListener('click',
        () => shot.inspect(window.inspection));
    }""")
    change = page.get_by_role("button", name="Change inspection")
    change.click()
    frames = shot.locator(".lf-shotframe")
    before, after = frames.evaluate_all(
        "nodes => nodes.map(node => node.getBoundingClientRect())"
    )
    assert after["left"] > before["right"]
    expect(shot.locator(".lf-shotrail")).to_be_hidden()
    assert shot.locator(".lf-shot-frame-label").evaluate_all(
        "nodes => nodes.map(node => node.dataset.label)"
    ) == ["Base", "Candidate"]
    assert shot.evaluate(
        "node => node.captureGeometry.images.map(image => image.width)"
    ) == [600, 600]
    assert (
        frames.first.evaluate("node => getComputedStyle(node, '::after').content")
        == '""'
    )

    page.evaluate("window.inspection.crop = true")
    change.click()
    expect(frames.first.locator("img")).to_have_css(
        "object-view-box", "inset(50px 300px 150px 100px)"
    )
    assert frames.first.locator("img").bounding_box()["width"] == pytest.approx(100)
    assert frames.first.locator("img").bounding_box()["height"] == pytest.approx(50)
    page.evaluate("window.inspection.mode = 'overlay'")
    change.click()
    before, after = frames.evaluate_all(
        "nodes => nodes.map(node => node.getBoundingClientRect())"
    )
    assert before["left"] == after["left"]
    assert before["top"] == after["top"]
    expect(frames.nth(1)).to_have_css("opacity", "0.35")
    page.evaluate("window.inspection.mode = 'flip'")
    change.click()
    expect(shot.locator(".lf-shotrail")).to_be_visible()
    expect(shot.locator(".lf-shot-frame-label")).to_have_count(0)
    shot.locator('.lf-shotcap[data-lf-state="after"]').click()
    expect(shot.locator('.lf-shotcap[data-lf-state="after"]')).to_have_attribute(
        "aria-pressed", "true"
    )


def test_a_shot_outlines_where_its_images_differ(browser, serve):
    """A reader shown one side of the divider, or a screenshot of the page, can't tell
    where a pair differs, or that it differs nowhere: a handoff once shipped a pair
    whose sides matched in every part its prose described. So the widget outlines what
    changed where each frame holds it, and nothing where a frame holds nothing, and
    offers mutually exclusive Plain, Outlines and Pixels views. The full outline
    count reads on hover, keyboard focus, or a held pointer. A difference too slight
    to point at still reads on the rail. The author offers the enhanced views with
    `outlines` and `pixels`."""
    plain = solid_png(600, 300, (210, 220, 235))
    patched = solid_png(
        600, 300, (210, 220, 235), patch=(420, 200, 60, 40, (30, 30, 30))
    )
    # Ten levels off in each channel, as a redrawn shadow is: nothing to point at.
    tinted = solid_png(
        600, 300, (210, 220, 235), patch=(40, 40, 60, 40, (200, 210, 225))
    )
    sources = {
        data: f"/media/{hashlib.sha256(data).hexdigest()[:16]}.png"
        for data in (plain, patched, tinted)
    }
    url = serve(
        LONG_PAGE.replace(
            "</main>",
            f"""<lf-shot id="shot-patch" outlines alt="a dark square appears"
                 before="{sources[plain]}" after="{sources[patched]}"></lf-shot>
               <lf-shot id="shot-same" outlines alt="nothing"
                 before="{sources[plain]}" after="{sources[plain]}"></lf-shot>
               <lf-shot id="shot-tint" outlines alt="a slight tint"
                 before="{sources[plain]}" after="{sources[tinted]}"></lf-shot>
               <lf-shot id="shot-quiet" alt="a dark square"
                 before="{sources[plain]}" after="{sources[patched]}"></lf-shot>
               <lf-shot id="shot-quiet-same" alt="nothing"
                 before="{sources[plain]}" after="{sources[plain]}"></lf-shot>
               <lf-shot id="shot-quiet-tint" alt="a slight tint"
                 before="{sources[plain]}" after="{sources[tinted]}"></lf-shot>
               <lf-shot id="shot-pixels" pixels alt="a dark square appears"
                 before="{sources[plain]}" after="{sources[patched]}"></lf-shot>
               <lf-shot id="shot-both" outlines pixels alt="a dark square appears"
                 before="{sources[plain]}" after="{sources[patched]}"></lf-shot>
               </main>""",
        ),
        media={source: data for data, source in sources.items()},
    )
    page = open_page(browser, url)
    patch = page.locator("#shot-patch")
    group = patch.get_by_role("radiogroup", name="Comparison view")
    expect(group.get_by_role("radio")).to_have_text(["Plain", "Outlines"])
    outlines = group.get_by_role("radio", name="Outlines", exact=True)
    expect(outlines).to_have_attribute("aria-description", "1 changed area")
    expect(group.locator('[aria-checked="true"]')).to_have_text("Outlines")
    expect(group.locator('[tabindex="0"]')).to_have_count(1)
    expect(page.locator("#shot-same .lf-shotdelta")).to_have_text("identical")
    assert page.locator("#shot-same .lf-shotdiff > span").count() == 0
    expect(page.locator("#shot-tint .lf-shotdelta")).to_have_text("only slight changes")
    assert page.locator("#shot-tint .lf-shotdiff > span").count() == 0

    # The after frame's mark stands just outside the square, in the frame's own scale,
    # and the before frame, which holds nothing there, has none.
    readings = page.locator("#shot-patch .lf-shotframe").evaluate_all(
        """frames => frames.map(frame => {
          const image = frame.querySelector('img').getBoundingClientRect();
          const marks = [...frame.querySelectorAll('.lf-shotdiff > span')];
          const scale = image.width / 600;
          return {state: frame.dataset.lfState, marks: marks.map(mark => {
            const box = mark.getBoundingClientRect();
            return [(box.left - image.left) / scale, (box.top - image.top) / scale,
                    (box.right - image.left) / scale, (box.bottom - image.top) / scale];
          })};
        })"""
    )
    marks = {reading["state"]: reading["marks"] for reading in readings}
    assert marks["before"] == []
    [(left, top, right, bottom)] = marks["after"]
    assert left < 420 and right > 480 and top < 200 and bottom > 240
    assert right - left < 80 and bottom - top < 60

    # Plain hides every outline. Without either opt-in there is no view selector,
    # but warnings still explain pairs with no region to point at.
    quiet = page.locator("#shot-quiet")
    expect(quiet.locator(".lf-shotdiff > span")).to_have_count(1)
    expect(quiet.locator(".lf-shotdiff").first).to_be_hidden()
    expect(quiet.get_by_role("radiogroup")).to_have_count(0)
    for shot, reading in (("same", "identical"), ("tint", "only slight changes")):
        delta = page.locator(f"#shot-quiet-{shot} .lf-shotdelta")
        expect(delta).to_have_text(reading)
        expect(delta).to_be_visible()

    # Tab enters the selected radio only; the full count appears on keyboard
    # arrival, while the resting rail contains just the short labels.
    outlines.scroll_into_view_if_needed()
    page.mouse.move(0, 0)
    outlines.press("Shift+Tab")
    assert (
        outlines.evaluate("node => getComputedStyle(node, '::after').content") == "none"
    )
    page.keyboard.press("Tab")
    expect(outlines).to_be_focused()
    expect(outlines).to_have_attribute("data-lf-focus", "")
    assert (
        outlines.evaluate("node => getComputedStyle(node, '::after').content")
        == '"1 changed area"'
    )
    group.get_by_role("radio", name="Plain", exact=True).click()
    expect(patch).to_have_attribute("data-lf-shot-view", "plain")
    expect(patch.locator(".lf-shotdiff").last).to_be_hidden()

    # Hold Outlines to read without selecting it. Sliding off cancels, releasing
    # on it selects, and pressing an already selected view never toggles it off.
    box = outlines.bounding_box()
    point = {"x": box["x"] + box["width"] / 2, "y": box["y"] + box["height"] / 2}
    page.mouse.move(**point)
    page.mouse.down()
    expect(outlines).to_have_attribute("data-lf-held-word", "")
    assert (
        outlines.evaluate("node => getComputedStyle(node, '::after').content")
        == '"1 changed area"'
    )
    expect(group.locator('[aria-checked="true"]')).to_have_text("Plain")
    page.mouse.move(0, 0)
    page.mouse.up()
    expect(outlines).not_to_have_attribute("data-lf-held-word", "")
    expect(group.locator('[aria-checked="true"]')).to_have_text("Plain")
    page.mouse.move(**point)
    page.mouse.down()
    page.mouse.up()
    expect(outlines).not_to_have_attribute("data-lf-held-word", "")
    expect(group.locator('[aria-checked="true"]')).to_have_text("Outlines")
    expect(patch.locator(".lf-shotdiff > span").first).to_be_visible()
    outlines.press("Space")
    outlines.press("Enter")
    expect(group.locator('[aria-checked="true"]')).to_have_text("Outlines")

    # A pixels-only comparison starts Plain. Selecting Pixels twice keeps it open;
    # selecting Plain, the picture, or an endpoint returns to the same divider.
    shot = page.locator("#shot-pixels")
    views = shot.get_by_role("radiogroup", name="Comparison view")
    expect(views.get_by_role("radio")).to_have_text(["Plain", "Pixels"])
    expect(views.locator('[aria-checked="true"]')).to_have_text("Plain")
    pixels = views.get_by_role("radio", name="Pixels", exact=True)
    view = shot.locator(".lf-shotpixels")
    expect(view).to_have_count(0)
    comparison = shot.locator(".lf-shotcomparison")
    expect(comparison).to_be_attached()
    before = comparison.get_attribute("position")
    pixels.click()
    expect(view).to_be_visible()
    expect(views.locator('[aria-checked="true"]')).to_have_text("Pixels")
    pixels.press("Enter")
    expect(view).to_be_visible()
    for state in ("before", "after"):
        expect(shot.locator(f'.lf-shotcap[data-lf-state="{state}"]')).to_have_attribute(
            "aria-pressed", "false"
        )
    assert view.bounding_box() == pytest.approx(comparison.bounding_box(), abs=1)
    pixels.press("ArrowLeft")
    expect(views.get_by_role("radio", name="Plain", exact=True)).to_be_focused()
    expect(view).to_be_hidden()
    assert comparison.get_attribute("position") == before
    page.keyboard.press("ArrowRight")
    expect(pixels).to_be_focused()
    expect(view).to_be_visible()
    view.click()
    expect(view).to_be_hidden()
    expect(views.locator('[aria-checked="true"]')).to_have_text("Plain")
    assert comparison.get_attribute("position") == before
    pixels.click()
    after = shot.locator('.lf-shotcap[data-lf-state="after"]')
    after.click()
    expect(view).to_be_hidden()
    expect(views.locator('[aria-checked="true"]')).to_have_text("Plain")
    expect(after).to_have_attribute("aria-pressed", "true")

    # The three-view group selects and focuses with every arrow direction, wraps,
    # and keeps exactly one roving Tab stop. Returning from Pixels restores the
    # last non-pixel view, with the divider unchanged.
    both = page.locator("#shot-both")
    views = both.get_by_role("radiogroup", name="Comparison view")
    expect(views.get_by_role("radio")).to_have_text(["Plain", "Outlines", "Pixels"])
    expect(views.locator('[aria-checked="true"]')).to_have_text("Outlines")
    outlines = views.get_by_role("radio", name="Outlines", exact=True)
    outlines.press("ArrowRight")
    expect(views.locator('[aria-checked="true"]')).to_have_text("Pixels")
    expect(both.locator(".lf-shotpixels")).to_be_visible()
    expect(both.locator(".lf-shotdiff").last).to_be_hidden()
    page.keyboard.press("ArrowDown")
    expect(views.locator('[aria-checked="true"]')).to_have_text("Plain")
    page.keyboard.press("ArrowLeft")
    expect(views.locator('[aria-checked="true"]')).to_have_text("Pixels")
    page.keyboard.press("ArrowUp")
    expect(outlines).to_be_focused()
    expect(views.locator('[aria-checked="true"]')).to_have_text("Outlines")
    expect(views.locator('[tabindex="0"]')).to_have_count(1)
    comparison = both.locator(".lf-shotcomparison")
    handle = comparison.locator('[role="scrollbar"]')
    handle.press("Home")
    handle.press("ArrowRight")
    expect(comparison).to_be_attached()
    before = comparison.get_attribute("position")
    views.get_by_role("radio", name="Pixels", exact=True).click()
    both.locator(".lf-shotpixels").click()
    expect(views.locator('[aria-checked="true"]')).to_have_text("Outlines")
    assert comparison.get_attribute("position") == before
    views.get_by_role("radio", name="Plain", exact=True).click()
    views.get_by_role("radio", name="Pixels", exact=True).click()
    both.locator(".lf-shotpixels").click()
    expect(views.locator('[aria-checked="true"]')).to_have_text("Plain")
    assert comparison.get_attribute("position") == before


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
    module.write_text(
        module.read_text().replace(
            "      if (!once(this)) return;",
            "      if (!once(this)) return;\n" + BADGE_CHROME,
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
    assert [f.values["id"] for f in clipped] == ["clipped-offer"] * 2, failures
    assert all(f.values["by"] == "<div id=clipped-holder>" for f in clipped), clipped
    words = sorted(
        {(f.code, f.at, f.values["words"]) for f in failures if f not in pair + clipped}
    )
    assert words == [
        ("chrome-words", "<lf-badge id=rp-badge>", "Sent by the reviewer"),
        ("chrome-words", "<lf-option id=c-lax>", "Session cookies"),
        ("chrome-words", "<lf-option id=c-lax>", "opens in a new tab"),
    ], failures


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

    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-thread-panel #t-bad .lf-error")).to_contain_text(
        "Unexpected token"
    )
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
