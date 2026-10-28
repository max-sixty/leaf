"""The visual review gallery: its layout in a workspace or section, frame fitting, focus
disclosure, keyboard navigation, and late evidence loads."""

import pytest
from leaf import data as data_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    CORPUS_SOURCES,
    example_media,
    leaf_page,
    open_page,
    resized,
    root_overflow,
    scroll_settled,
    sending,
    told,
)

pytestmark = pytest.mark.shifts_unsurveyed


VISUAL_REVIEW_GALLERY = next(
    path for path in CORPUS_SOURCES if path.stem == "visual-review-gallery"
)


def test_visual_review_controls_keep_keyboard_navigation_local(browser, serve):
    """Radio arrows, opacity keys, and select typeahead do not also navigate the case."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    widget = page.locator("#visual-review-run")
    selector = widget.locator(".lf-vr-case-select")
    initial = selector.evaluate("node => node.value")
    assert widget.evaluate(
        """owner => lfUnwatched(() => {
          const parent = owner.parentNode;
          const next = owner.nextSibling;
          const nodes = [...owner.querySelectorAll('*')];
          owner.remove();
          parent.insertBefore(owner, next);
          return nodes.every((node, index) => owner.querySelectorAll('*')[index] === node);
        })"""
    )
    widget.get_by_text("Inspect comparison", exact=True).click()
    widget.get_by_role("radio", name="Compare").click()
    page.keyboard.press("ArrowDown")
    expect(widget).to_have_attribute("data-inspection-mode", "flip")
    expect(selector).to_have_js_property("value", initial)
    page.keyboard.press("ArrowDown")
    expect(widget).to_have_attribute("data-inspection-mode", "overlay")
    slider = widget.get_by_role("slider", name="Candidate opacity")
    slider.focus()
    page.keyboard.press("ArrowUp")
    expect(widget.locator(".lf-vr-opacity-value")).to_have_text("55%")
    page.keyboard.press("Shift+ArrowRight")
    expect(widget.locator(".lf-vr-opacity-value")).to_have_text("60%")
    expect(selector).to_have_js_property("value", initial)
    widget.get_by_role("radio", name="Compare").focus()
    page.keyboard.press("Enter")
    expect(widget).to_have_attribute("data-inspection-mode", "compare")
    selector.click()
    page.keyboard.press("2")
    expect(widget.get_by_role("option", name="2 of 3", exact=False)).to_be_focused()
    page.keyboard.press("ArrowUp")
    page.keyboard.press("g")
    expect(page.locator(".lf-go-to-hint")).to_have_count(0)
    expect(selector).to_have_js_property("value", initial)
    page.keyboard.press("Escape")
    expect(selector).to_have_js_property("open", False)
    expect(widget.get_by_role("combobox", name="Selected visual case")).to_be_focused()


def test_visual_review_empty_navigation_is_unavailable(browser, serve):
    url = live_url(
        serve(
            leaf_page(
                "empty visual review",
                '<lf-visual-review id="visual-run" source="missing-run"></lf-visual-review>',
            ),
            packages=("visual-review",),
        )
    )
    page = open_page(browser, url)
    widget = page.locator("#visual-run")
    expect(widget.get_by_role("button", name="Previous")).to_be_disabled()
    expect(widget.get_by_role("combobox", name="Selected visual case")).to_be_disabled()
    expect(widget.get_by_role("button", name="Next", exact=True)).to_be_disabled()
    expect(widget.get_by_text("Waiting for visual-run data.")).to_be_visible()


def test_visual_review_ignores_a_late_load_from_detached_evidence(browser, serve):
    authored = leaf_page(
        "visual review replacement",
        '<lf-visual-review id="visual-run" source="docs-run"></lf-visual-review>',
    )
    media = {
        "/media/3cf0e3efe80c6b01.png": (
            example_media() / "3cf0e3efe80c6b01.png"
        ).read_bytes(),
        "/media/4f465a0582ab00fe.png": (
            example_media() / "4f465a0582ab00fe.png"
        ).read_bytes(),
    }
    url = live_url(serve(authored, packages=("visual-review",), media=media))
    capture = {
        "observedAt": "2026-09-10T10:30:00-07:00",
        "browser": "Chrome",
        "browserVersion": "140",
        "viewport": {"width": 900, "height": 373},
        "deviceScaleFactor": 2,
        "colorScheme": "light",
        "locale": "en-US",
        "timezone": "America/Los_Angeles",
    }

    def run(before, after, *, viewport_width):
        return {
            "title": "Replacement run",
            "base": {"revision": "base", "url": "https://base.example/"},
            "candidate": {
                "revision": "candidate",
                "url": "https://candidate.example/",
            },
            "cases": [
                {
                    "id": "changed",
                    "title": "Changed surface",
                    "path": "/changed",
                    "action": "Open the surface.",
                    "result": "The evidence remains aligned.",
                    "classification": "changed",
                    "capture": capture
                    | {"viewport": capture["viewport"] | {"width": viewport_width}},
                    "focus": {"x": 20, "y": 80, "width": 300, "height": 150},
                    "before": before,
                    "after": after,
                }
            ],
        }

    data_model.cmd_data_set(
        serve.page_dir,
        "docs-run",
        run(
            "/media/3cf0e3efe80c6b01.png",
            "/media/4f465a0582ab00fe.png",
            viewport_width=900,
        ),
    )
    context = browser.new_context(viewport={"width": 1200, "height": 900})
    held = []
    context.route("**/media/slow-*.svg", lambda route: held.append(route))
    page = None
    try:
        page = open_page(browser, url, context=context)
        data_model.cmd_data_set(
            serve.page_dir,
            "docs-run",
            run(
                "/media/slow-before.svg",
                "/media/slow-after.svg",
                viewport_width=900,
            ),
        )
        told(page)
        expect(page.locator("#visual-run lf-shot img")).to_have_count(2)
        page.evaluate(
            "window.oldVisualReviewImages = [...document.querySelectorAll('#visual-run lf-shot img')]"
        )
        expect(page.locator("#visual-run lf-shot img").first).to_have_js_property(
            "naturalWidth", 0
        )
        assert len(held) == 2

        data_model.cmd_data_set(
            serve.page_dir,
            "docs-run",
            run(
                "/media/3cf0e3efe80c6b01.png",
                "/media/4f465a0582ab00fe.png",
                viewport_width=900,
            ),
        )
        told(page)
        host = page.locator("#visual-run .lf-vr-shot-host")
        expect(host.locator("lf-shot img")).to_have_count(2)
        expect(host.locator("lf-shot img").first).to_have_js_property(
            "naturalWidth", 780
        )
        rendered(page, facts=("updatesSettled",))
        shown = host.locator("lf-shot").bounding_box()

        stale_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="746"/>'
        )
        while held:
            held.pop(0).fulfill(content_type="image/svg+xml", body=stale_svg)
        page.wait_for_function(
            "() => window.oldVisualReviewImages.every(image => image.naturalWidth === 1800)"
        )
        rendered(page)
        assert host.locator("lf-shot").bounding_box() == shown
    finally:
        while held:
            held.pop(0).abort()


def test_visual_review_gallery_gives_a_laptop_to_the_evidence(browser, serve):
    """A focused review is a workspace, not prose followed by a narrow widget.

    The case picker never taxes the evidence width, and disposition follows the
    pixels. The review fills the window; Fit shrinks a mobile pair to fit its pane
    when the captured text remains readable, otherwise the pane scrolls the pair.
    Capture facts follow the comparison rather than delaying it.
    """
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    resized(page, 1440, 900)
    widget = page.locator("#visual-review-run")
    fit_reading = """node => {
          const body = node.querySelector('.lf-vr-cases');
          const frames = [...node.querySelectorAll(
            '.lf-vr-case[data-selected] .lf-shotframe')];
          return {bodyBottom: body.getBoundingClientRect().bottom,
                  framesBottom: Math.max(...frames.map(
                    frame => frame.getBoundingClientRect().bottom)),
                  image: frames[0].querySelector('img').getBoundingClientRect().width,
                  page: document.scrollingElement.scrollHeight - innerHeight};
        }"""
    contained = widget.evaluate(fit_reading)
    assert contained["framesBottom"] <= contained["bodyBottom"] + 0.5, contained
    assert 0.7 * 350 < contained["image"] < 350, contained
    assert contained["page"] <= 0, contained
    # Opening the inspector takes space from the pair in this rendering update.
    # A settled read would miss a frame with its bottom cut off by the pane.
    widget.evaluate("""node => {
        window.evidenceFits = [];
        window.evidenceSize = new ResizeObserver(() => {
            const bottom = node.querySelector('.lf-vr-cases').getBoundingClientRect().bottom;
            evidenceFits.push([...node.querySelectorAll(
                '.lf-vr-case[data-selected] .lf-shotframe')]
                .every(frame => frame.getBoundingClientRect().bottom <= bottom + 0.5));
        });
        evidenceSize.observe(node.querySelector('.lf-vr-case[data-selected] .lf-vr-toolbar-slot'));
    }""")
    widget.get_by_text("Inspect comparison", exact=True).click()
    page.wait_for_function(
        """node => {
          const body = node.querySelector('.lf-vr-cases').getBoundingClientRect();
          return [...node.querySelectorAll('.lf-vr-case[data-selected] .lf-shotframe')]
            .every(frame => frame.getBoundingClientRect().bottom <= body.bottom + 0.5);
        }""",
        arg=widget.element_handle(),
    )
    opened = widget.evaluate(fit_reading)
    assert opened["image"] < contained["image"], opened
    fits = page.evaluate("""() => {
        evidenceSize.disconnect();
        return evidenceFits;
    }""")
    assert fits and all(fits), fits
    widget.get_by_text("Inspect comparison", exact=True).click()
    page.wait_for_function(
        "(args) => args.node.querySelector('.lf-vr-case[data-selected] img')"
        ".getBoundingClientRect().width === args.width",
        arg={"node": widget.element_handle(), "width": contained["image"]},
    )
    resized(page, 1366, 600)
    widget.get_by_text("Inspect comparison", exact=True).click()
    gallery_scope = widget.get_by_role("radiogroup", name="Scope")
    expect(gallery_scope).to_be_visible()
    expect(widget).to_have_attribute("data-inspection-scope", "focus")
    geometry = widget.evaluate(
        """node => {
          const box = selector => node.querySelector(selector).getBoundingClientRect();
          const frames = [...node.querySelectorAll(
            '.lf-vr-case[data-selected] .lf-shotframe')]
            .map(frame => frame.getBoundingClientRect());
          return {widget: node.getBoundingClientRect(), title: box('.lf-vr-case-title'),
                  decision: box('.lf-vr-dispositions'), evidence: box('.lf-vr-shot-host'),
                  capture: box('.lf-vr-shot-host lf-shot'),
                  support: box('.lf-vr-support'), frames};
        }"""
    )
    assert geometry["widget"]["width"] > 1000
    assert geometry["decision"]["top"] >= geometry["evidence"]["bottom"]
    assert geometry["capture"]["bottom"] <= geometry["evidence"]["bottom"] + 1, geometry
    # The capture opens at the stage's top edge, inside its border: the stage sets the
    # box of the lf-shot it holds over that widget's own block margin.
    assert geometry["capture"]["top"] - geometry["evidence"]["top"] <= 1.5, geometry
    assert widget.get_attribute("data-compare-layout") == "side", geometry
    assert geometry["frames"][1]["left"] >= geometry["frames"][0]["right"]
    case_image_width = widget.locator(
        ".lf-vr-case[data-selected] .lf-shotframe img"
    ).first.evaluate("node => node.getBoundingClientRect().width")
    assert case_image_width == pytest.approx(350, abs=1), geometry
    assert widget.locator(".lf-vr-case[data-selected] .lf-vr-shot-host").evaluate(
        "node => node.scrollHeight <= node.clientHeight + 1"
    )
    assert widget.locator(".lf-vr-cases").evaluate(
        "node => node.scrollHeight > node.clientHeight"
    )
    assert geometry["support"]["top"] >= geometry["evidence"]["bottom"]
    case = widget.locator(".lf-vr-case[data-selected]")
    claim_geometry = case.evaluate(
        """node => {
          const box = selector => node.querySelector(selector).getBoundingClientRect();
          const style = selector => getComputedStyle(node.querySelector(selector));
          return {
            actionTerm: box('.lf-vr-action-term'), action: box('.lf-vr-action'),
            resultTerm: box('.lf-vr-result-term'), result: box('.lf-vr-result'),
            titleFamily: style('.lf-vr-case-title').fontFamily,
            labelFamily: style('.lf-vr-action-term').fontFamily,
            valueFamily: style('.lf-vr-action').fontFamily,
          };
        }"""
    )
    assert claim_geometry["titleFamily"] == claim_geometry["valueFamily"]
    assert claim_geometry["labelFamily"] == claim_geometry["valueFamily"]
    assert claim_geometry["actionTerm"]["left"] == pytest.approx(
        claim_geometry["action"]["left"], abs=1
    )
    assert claim_geometry["resultTerm"]["left"] == pytest.approx(
        claim_geometry["result"]["left"], abs=1
    )
    assert claim_geometry["actionTerm"]["bottom"] <= claim_geometry["action"]["top"]
    assert claim_geometry["resultTerm"]["bottom"] <= claim_geometry["result"]["top"]
    # Archived captures keep pinned revisions without advertising invented destinations.
    expect(case.locator(".lf-vr-links > a:visible")).to_have_count(0)
    expect(case.get_by_text("Capture details", exact=True)).to_be_visible()
    expect(case.locator(".lf-vr-provenance")).to_be_hidden()
    summary = case.get_by_text("Capture details", exact=True)
    summary.scroll_into_view_if_needed()
    scroll_settled(page)
    summary_box = summary.bounding_box()
    summary.click()
    expect(case.locator(".lf-vr-provenance")).to_be_visible()
    assert summary.bounding_box() == summary_box, (
        "opening capture facts moved their press"
    )

    revision = case.locator(".lf-vr-candidate-revision")
    assert revision.evaluate("node => node.getClientRects().length") == 1
    details_box = case.locator(".lf-vr-details").bounding_box()
    support_box = case.locator(".lf-vr-support").bounding_box()
    assert details_box and support_box
    assert details_box["x"] >= support_box["x"]
    assert (
        details_box["x"] + details_box["width"]
        <= support_box["x"] + support_box["width"] + 1
    )
    revision.evaluate("node => node.textContent = 'a'.repeat(40)")
    assert case.locator(".lf-vr-provenance").evaluate(
        "node => node.scrollWidth <= node.clientWidth"
    )
    resized(page, 560, 720)
    assert root_overflow(page) == 0
    resized(page, 390, 900)
    assert root_overflow(page) == 0
    resized(page, 1366, 768)
    shot_host = widget.locator(".lf-vr-case[data-selected] .lf-vr-shot-host")
    assert shot_host.evaluate("node => node.scrollWidth == node.clientWidth")
    expect(widget).to_have_attribute("data-compare-layout", "side")

    page.emulate_media(media="print")
    print_widths = widget.locator(".lf-vr-case lf-shot img").evaluate_all(
        "images => images.map(image => image.getBoundingClientRect().width)"
    )
    assert len(print_widths) == 6
    assert widget.locator(".lf-vr-case lf-shot img").evaluate_all(
        "images => images.every(image => image.getBoundingClientRect().width <= image.naturalWidth / 2 + 1)"
    )
    expect(widget.locator(".lf-vr-focus").first).to_be_visible()
    page.emulate_media(media="screen")

    selected = widget.locator(".lf-vr-case-select")
    with sending(page, "the intended responsive change disposition"):
        case.get_by_role("button", name="Looks right").click()
    page.keyboard.press("ArrowDown")
    expect(selected).to_have_js_property("value", "keep-mobile-destinations")
    expect(widget).to_have_attribute("data-compare-layout", "stack")
    expect(gallery_scope).to_be_visible()
    expect(widget).to_have_attribute("data-inspection-scope", "focus")
    with sending(page, "the seeded responsive regression disposition"):
        widget.locator(".lf-vr-case[data-selected]").get_by_role(
            "button", name="Needs work"
        ).click()
    expect(widget.locator(".lf-vr-progress")).to_have_text("2 of 3 cases reviewed")
    page.keyboard.press("ArrowDown")
    expect(selected).to_have_js_property("value", "check-desktop-navigation")
    expect(widget).to_have_attribute("data-compare-layout", "stack")
    expect(gallery_scope).to_be_hidden()
    expect(widget).to_have_attribute("data-inspection-scope", "full")
    assert widget.locator(".lf-vr-case[data-selected] .lf-vr-shot-host").evaluate(
        "node => node.scrollHeight <= node.clientHeight + 1"
    )


def test_a_visual_review_inside_a_section_of_a_workspace_flows(browser, serve):
    """Only a review the workspace gives a height fills it. In a section of the body it is
    not told it has one (`--lf-full-height` does not inherit), so it takes its content's
    height with its pair at the stage's width, the body scrolls it, and it settles:
    sized from its own pane, it grew a little on each pass."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    resized(page, 1440, 900)
    widget = page.locator("#visual-review-run")
    expect(widget.locator(".lf-vr-case[data-selected] lf-shot")).to_be_visible()
    widget.evaluate(
        """review => {
          const section = document.createElement('section');
          const intro = document.createElement('p');
          intro.textContent = 'An intro paragraph before the review.';
          review.before(section);
          section.append(intro, review);
        }"""
    )
    reading = """review => ({
      image: review.querySelector('.lf-vr-case[data-selected] .lf-shotframe img')
        .getBoundingClientRect().width,
      paneScrolls: getComputedStyle(review.querySelector('.lf-vr-cases')).overflowY,
    })"""
    rendered(page)
    first = widget.evaluate(reading)
    page.wait_for_timeout(500)
    rendered(page)
    assert widget.evaluate(reading) == first == {"image": 350, "paneScrolls": "visible"}


def test_visual_review_fits_frames_using_the_authored_spacing(browser, serve):
    """Fitting and the painted frame tracks agree when spacing is authored in rem: the
    frames stand a rem apart, and where the page scrolls the review, in a window too
    short for the workspace to fill, the pair takes the stage's whole width."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    widget = page.locator("#visual-review-run")
    widget.locator(".lf-vr-shot-host").evaluate_all(
        "nodes => nodes.forEach(node => node.style.setProperty('--sp-2', '1rem'))"
    )
    for height in (800, 470):
        resized(page, 760, height)
        expect(widget).to_have_attribute("data-compare-layout", "side")
        geometry = widget.locator(
            ".lf-vr-case[data-selected] .lf-vr-shot-host"
        ).evaluate(
            """host => {
              const shot = host.querySelector('lf-shot');
              const frames = [...shot.querySelectorAll('.lf-shotframe')]
                .map(frame => frame.getBoundingClientRect());
              return {available: host.clientWidth,
                      width: shot.getBoundingClientRect().width,
                      gap: frames[1].left - frames[0].right,
                      rem: parseFloat(getComputedStyle(document.documentElement).fontSize),
                      overflow: host.scrollWidth - host.clientWidth};
            }"""
        )
        assert geometry["gap"] == pytest.approx(geometry["rem"], abs=0.1), geometry
        assert geometry["overflow"] == 0, geometry
    assert geometry["width"] == pytest.approx(geometry["available"], abs=0.1), geometry


def test_visual_review_discloses_focus_without_distorting_unsupported_browsers(
    browser, serve
):
    page = open_page(
        browser,
        serve(VISUAL_REVIEW_GALLERY),
        init_script="""
          const supports = CSS.supports.bind(CSS);
          CSS.supports = (property, value) =>
            property === 'object-view-box' ? false : supports(property, value);
        """,
    )
    widget = page.locator("#visual-review-run")
    case = widget.locator(".lf-vr-case[data-selected]")
    host = case.locator(".lf-vr-shot-host")
    expect(widget).to_have_attribute("data-inspection-scope", "full")
    expect(widget.get_by_role("radiogroup", name="Scope")).to_be_hidden()
    scope = widget.locator(".lf-vr-scope-group")
    scope.evaluate("""group => {
      group.value = 'focus';
      group.dispatchEvent(new Event('change', {bubbles: true}));
    }""")
    expect(scope).to_have_js_property("value", "full")
    expect(host.locator("lf-shot")).to_have_attribute("data-lf-shot-focus", "true")
    expect(host.locator("lf-shot")).to_have_attribute("data-lf-shot-crop", "false")
    image = case.locator(".lf-shotframe img").first.evaluate(
        """node => ({
          renderedRatio: node.getBoundingClientRect().width / node.getBoundingClientRect().height,
          naturalRatio: node.naturalWidth / node.naturalHeight,
          objectViewBox: getComputedStyle(node).objectViewBox,
        })"""
    )
    assert image["renderedRatio"] == pytest.approx(image["naturalRatio"], rel=0.01)
    assert image["objectViewBox"] == "none"
    marker = case.locator(".lf-shotframe").first.evaluate(
        "frame => getComputedStyle(frame, '::after').getPropertyValue('content')"
    )
    assert marker == '""'
    expect(case.locator(".lf-vr-focus")).to_have_text("20, 100 · 350 × 640 CSS px")
