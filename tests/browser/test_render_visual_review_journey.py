"""Visual review preserves evidence, focus and discussion across live source changes."""

import hashlib
import json

import pytest
from playwright.sync_api import expect
from render_cases_layout import (
    current_location_ring,
    ring_faults,
    solid_png,
)
from render_harness import (
    CORPUS_SOURCES,
    consume_browser_errors,
    holding,
    leaf_page,
    open_page,
    refuse,
    resized,
    scroll_settled,
    sending,
    stamp_page,
    told,
    undo,
)

from leaf import data as data_model
from leaf import event_log as events_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed

VISUAL_REVIEW_GALLERY = next(
    path for path in CORPUS_SOURCES if path.stem == "visual-review-gallery"
)


def test_a_visual_review_in_flow_takes_its_evidence_height(browser, serve):
    """An embedded review scrolls with its document instead of clipping captures."""
    url = serve(VISUAL_REVIEW_GALLERY)
    stamp_page(
        serve.page_dir,
        leaf_page(
            "visual inspection in flow",
            """
<h1>Review the package change</h1>
<section><lf-visual-review id="visual-review-run" source="gallery-visual-run"></lf-visual-review></section>
<p style="min-height: 40rem">The decision record continues after the evidence.</p>
""",
        ),
        "put visual inspection in document flow",
    )
    url = url.rsplit("/versions/", 1)[0] + "/?" + url.partition("?")[2]
    page = open_page(browser, url)
    resized(page, 1000, 700)
    case = page.locator('.lf-vr-case[aria-hidden="false"]')
    case.get_by_role("button", name="Image options").click()
    case.get_by_role("checkbox", name="Full frame").check()
    page.keyboard.press("Escape")
    case.get_by_role("button", name="Image options").click()
    case.get_by_role("button", name="100%", exact=True).click()
    host = case.locator(".lf-vr-capture")
    for mode in ("Pair", "Slider", "Pixels"):
        case.get_by_role("button", name=mode, exact=True).click()
        rendered(page)
        assert host.evaluate("node => node.scrollHeight <= node.clientHeight + 1")
    assert page.evaluate("document.scrollingElement.scrollHeight > innerHeight")
    page.emulate_media(media="print")
    cases = page.locator(".lf-vr-case")
    expect(cases).to_have_count(3)
    for printed in cases.all():
        expect(printed).to_be_visible()
    expect(page.locator(".lf-vr-queue")).to_be_hidden()
    expect(case.locator(".lf-vr-decision")).to_be_hidden()


def go_to(page, target, kind="Control"):
    """Type the opaque hint painted beside one rendered destination."""
    # Hints label what the window shows, so the reader scrolls the page to it first.
    target.scroll_into_view_if_needed()
    scroll_settled(page)
    page.keyboard.press("g")
    hints = page.locator(".lf-go-to-hint[data-lf-hint-code]")
    expect(hints.first).to_be_visible()
    code = target.evaluate(
        """(target, kind) => {
          const at = target.getBoundingClientRect();
          const chips = [...document.querySelectorAll(
            '.lf-go-to-hint[data-lf-hint-code]')]
            .filter(chip => chip.dataset.lfGoToKind === kind);
          return chips.map(chip => {
            const box = chip.getBoundingClientRect();
            return {code: chip.dataset.lfHintCode,
              distance: Math.hypot(box.left - at.left, box.top - at.top)};
          }).sort((a, b) => a.distance - b.distance)[0]?.code ?? null;
        }""",
        kind,
    )
    assert code, f"the rendered {kind.lower()} had no Go-to hint"
    page.keyboard.type(code)


def comment_on_target(page, target):
    """Choose one rendered datum through Leaf's keyboard target map."""
    page.keyboard.press("s")
    hints = page.locator(".lf-target-picker-hint[data-lf-hint-code]")
    expect(hints.first).to_be_visible()
    code = target.evaluate(
        """target => {
          const at = target.getBoundingClientRect();
          const chips = [...document.querySelectorAll(
            '.lf-target-picker-hint[data-lf-hint-code]')];
          return chips.map(chip => {
            const box = chip.getBoundingClientRect();
            return {code: chip.dataset.lfHintCode,
              distance: Math.hypot(box.left - at.left, box.top - at.top)};
          }).sort((a, b) => a.distance - b.distance)[0]?.code ?? null;
        }"""
    )
    assert code, "the rendered datum had no target-picker hint"
    page.keyboard.type(code)


def assert_keyboard_focus(page, control):
    """The focused destination declares a visible treatment and is not covered.

    A text field always shows its focus, as a textarea does. Chrome never gives a host
    that delegates focus `:focus-visible`, so the field's treatment keys on `:focus`,
    and that is the state asked of it here."""
    expect(control).to_be_focused()
    focus = control.evaluate(
        """node => {
          const box = node.getBoundingClientRect();
          const hit = document.elementFromPoint(
            box.left + box.width / 2, box.top + box.height / 2);
          const shown = node.localName === 'leaf-text' ? ':focus' : ':focus-visible';
          return {
            focusVisible: node.matches(shown),
            unobscured: Boolean(hit && (hit === node || node.contains(hit))),
            inViewport: box.top >= 0 && box.left >= 0
              && box.bottom <= innerHeight && box.right <= innerWidth,
          };
        }"""
    )
    assert focus == {
        "focusVisible": True,
        "unobscured": True,
        "inViewport": True,
    }, f"the keyboard destination has no visible, reachable focus treatment: {focus}"
    ring = current_location_ring(page)
    assert ring, "the focused destination paints no keyboard ring"
    assert not (faults := ring_faults([ring], "the focused destination")), "\n".join(
        faults
    )


def target_document(title, body):
    """One small release site whose links and pixels are the capture subject."""
    style = """<style>
    * { box-sizing: border-box; }
    body { margin: 0; color: #25231f; background: #f7f5ef;
      font: 16px/1.45 system-ui, sans-serif; }
    main { width: min(760px, calc(100% - 48px)); margin: 48px auto; }
    header { display: flex; align-items: baseline; justify-content: space-between;
      border-bottom: 1px solid #cfc9bd; margin-bottom: 28px; }
    h1 { font: 700 34px/1.05 Georgia, serif; }
    a { color: #174f82; }
    .release { display: grid; grid-template-columns: 1fr auto; gap: 12px;
      padding: 18px; margin: 12px 0; background: white;
      border: 1px solid #d7d1c7; border-radius: 8px; }
    .status { align-self: start; padding: 3px 8px; color: #245734;
      background: #e0efe3; border-radius: 999px; font-size: 13px; font-weight: 700; }
    .meta { color: #68635a; }
  </style>"""
    return leaf_page(
        title,
        f"<header><strong>Northstar releases</strong><span>Acme team</span></header>{body}",
        head=style,
    )


@pytest.mark.parametrize("height", [600, 760])
def test_visual_review_keeps_its_inline_comment_editor_in_view_after_phone_resize(
    browser, serve, height
):
    """A focused comment editor remains reachable when its visual-review seat narrows."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    resized(page, 1366, 768)
    widget = page.locator("#visual-review-run")
    widget.locator(".lf-vr-case-button").nth(1).click()
    datum = widget.locator('[data-lf-datum="keep-mobile-destinations"]')
    comment_on_target(page, datum)
    field = page.locator(".lf-fab-input")
    expect(field).to_be_focused()
    page.keyboard.type("Keep the destinations together")
    page.keyboard.press("Shift+ArrowLeft")
    caret = field.evaluate("node => [node.selectionStart, node.selectionEnd]")
    assert_keyboard_focus(page, field)

    # Resizing alone must keep the focused editor in view. The reader has not scrolled.
    resized(page, 390, height)
    expect(field).to_have_js_property("value", "Keep the destinations together")
    assert field.evaluate("node => [node.selectionStart, node.selectionEnd]") == caret
    assert_keyboard_focus(page, field)

    # A shorter window changes the visible band even when the inline seat's
    # width and scroll container stay the same.
    resized(page, 390, height - 120)
    assert_keyboard_focus(page, field)
    assert field.evaluate("node => [node.selectionStart, node.selectionEnd]") == caret

    # Native scrolling can leave the same editor focused. The next reflow must
    # keep that newer reading instead of pulling the draft back into view.
    page.mouse.wheel(0, -10000)
    page.wait_for_function("document.scrollingElement.scrollTop === 0")
    scroll_settled(page)
    expect(field).to_be_focused()
    assert field.evaluate("node => node.getBoundingClientRect().bottom > innerHeight")
    resized(page, 420, height - 120)
    assert page.evaluate("document.scrollingElement.scrollTop") == 0
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "Keep the destinations together")


def test_visual_review_allocates_focused_evidence_before_images_decode(browser, serve):
    """The declared focus sizes the first comparison, even over a slow media load."""
    url = serve(VISUAL_REVIEW_GALLERY)
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    held = []
    context.route("**/media/*.png", lambda route: held.append(route))
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded")
    widget = page.locator("#visual-review-run")
    expect(widget.locator(".lf-vr-title").first).to_be_visible()
    host = widget.locator('.lf-vr-case[aria-hidden="false"] .lf-vr-capture')
    geometry = """node => ({
      host: node.getBoundingClientRect().toJSON(),
      frames: [...node.querySelectorAll('.lf-shotframe')]
        .map(frame => frame.getBoundingClientRect().toJSON()),
    })"""
    before = host.evaluate(geometry)
    assert before["frames"][0]["height"] > 500, before
    assert before["frames"][1]["top"] == before["frames"][0]["top"], before
    assert before["frames"][1]["height"] == before["frames"][0]["height"], before
    assert host.locator("img").evaluate_all(
        "images => images.every(image => image.naturalWidth === 0)"
    )
    for route in held:
        route.continue_()
    context.unroute("**/media/*.png")
    expect(host.locator("img").first).to_have_js_property("naturalWidth", 780)
    expect(host.locator("img").last).to_have_js_property("naturalWidth", 780)
    page.wait_for_function("document.body.hasAttribute('data-lf-presented')")
    after = host.evaluate(geometry)
    assert after == before, {"before": before, "after": after}


def test_visual_review_reports_an_image_failure_after_its_peer_has_loaded(
    browser, serve
):
    """A late image failure reports the refused pair beside retained inspection."""
    url = serve(VISUAL_REVIEW_GALLERY)
    run = json.loads(
        data_model.source_file(serve.page_dir, "gallery-visual-run").read_text()
    )["value"]
    failed_source = run["cases"][0]["after"]
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    held = []
    context.route(f"**{failed_source}", lambda route: held.append(route))
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded")
    host = page.locator('.lf-vr-case[aria-hidden="false"] .lf-vr-capture')
    images = host.locator("img")
    holding(page, held, 1, "the second selected capture")
    # One loaded image cannot publish half a comparison. Both visible images stay
    # empty until the incoming pair has loaded; its declared geometry stays reserved.
    rendered(page, facts=("updatesSettled",))
    assert images.evaluate_all("images => images.every(image => !image.naturalWidth)")
    assert (
        host.locator(".lf-shotframe").first.evaluate(
            "node => node.getBoundingClientRect().height"
        )
        > 500
    )
    expect(host.locator(".lf-error")).to_have_count(0)
    refuse(held[0])
    expect(host.locator(".lf-error")).to_contain_text("focus needs two decoded images")
    expect(host.get_by_role("button", name="Pair", exact=True)).to_be_visible()
    consume_browser_errors(page, "focus needs two decoded images")
    unrelated = run | {
        "cases": [
            run["cases"][0],
            run["cases"][1] | {"result": "Another case has a new observation."},
            *run["cases"][2:],
        ]
    }
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", unrelated)
    told(page)
    rendered(page, facts=("updatesSettled",))
    assert len(held) == 1, "an unrelated update retried the refused image"


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_visual_review_refresh_retains_inspection_and_hands_focus_off_removed_cases(
    request, serve, engine
):
    """New captures retain inspection; a removed case returns focus to the next case."""
    browser = request.getfixturevalue(engine)
    captures = [
        solid_png(1200, 1000, color) for color in ((220, 230, 240), (240, 230, 220))
    ]
    sources = [
        f"/media/{hashlib.sha256(data).hexdigest()[:16]}.png" for data in captures
    ]
    page = open_page(
        browser,
        serve(VISUAL_REVIEW_GALLERY, media=dict(zip(sources, captures, strict=True))),
    )
    widget = page.locator("#visual-review-run")
    case = widget.locator('.lf-vr-case[aria-hidden="false"]')
    shot = case.locator("lf-shot")
    control = case.get_by_role("button", name="Slider", exact=True)
    control.click()
    case.get_by_role("button", name="Image options").click()
    case.get_by_role("button", name="100%", exact=True).click()
    divider = shot.get_by_role("scrollbar")
    divider.press("Home")
    divider.press("ArrowRight")
    control.focus()
    expect(control).to_be_focused()
    original = shot.element_handle()
    record = json.loads(VISUAL_REVIEW_GALLERY.with_suffix(".data.json").read_text())[
        "gallery-visual-run"
    ]
    changed = record | {
        "cases": [
            record["cases"][0]
            | {
                "before": record["cases"][0]["after"],
                "after": record["cases"][0]["before"],
            },
            *record["cases"][1:],
        ]
    }
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", changed)
    told(page)
    expect(control).to_be_focused()
    assert shot.evaluate("(node, original) => node === original", original)
    expect(control).to_have_attribute("aria-pressed", "true")
    expect(shot.locator("wa-comparison")).to_have_attribute("position", "1")
    expect(
        case.get_by_role("button", name="100%", exact=True, include_hidden=True)
    ).to_have_attribute("aria-pressed", "true")

    # A refused replacement leaves usable old evidence, and correcting it must
    # publish new dimensions even in Firefox, whose reused-image decode can be stale.
    invalid = changed | {
        "cases": [changed["cases"][0] | {"after": sources[1]}, *changed["cases"][1:]]
    }
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", invalid)
    told(page)
    expect(shot.locator(".lf-error")).to_contain_text(
        "a pair has to be shot at one viewport"
    )
    consume_browser_errors(page, "a pair has to be shot at one viewport")
    expect(control).to_be_focused()
    changed = invalid | {
        "cases": [
            invalid["cases"][0]
            | {
                "before": sources[0],
                "capture": invalid["cases"][0]["capture"]
                | {"viewport": {"width": 600, "height": 500}, "deviceScaleFactor": 2},
                "focus": {"x": 300, "y": 200, "width": 200, "height": 200},
            },
            *invalid["cases"][1:],
        ]
    }
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", changed)
    told(page)
    expect(shot.locator(".lf-error")).to_have_count(0)
    expect(control).to_be_focused()
    assert shot.locator(".lf-shotframe img").evaluate_all(
        "images => images.map(image => [image.naturalWidth, image.naturalHeight, image.getBoundingClientRect().width])"
    ) == [[1200, 1000, 600], [1200, 1000, 600]]

    # Refreshing captures also replaces the cached pixel mask and its background.
    pixels = case.get_by_role("button", name="Pixels", exact=True)
    pixels.click()
    page.wait_for_function(
        """() => document.querySelector(
          '.lf-vr-case[aria-hidden="false"] .lf-shotpixels .lf-shot-pixel-mask'
        )?.style.getPropertyValue('--lf-shot-pixels')"""
    )
    painted_pixels = """node => ({
      ground: node.querySelector('.lf-shotpixels img').src,
      mask: node.querySelector('.lf-shotpixels .lf-shot-pixel-mask')
        .style.getPropertyValue('--lf-shot-pixels'),
    })"""
    previous_pixels = shot.evaluate(painted_pixels)
    # Hold the platform's mask encoding at an actual asynchronous boundary.
    # Refresh must keep the whole old difference until the new mask is ready.
    page.evaluate(
        """() => {
          const encode = OffscreenCanvas.prototype.convertToBlob;
          window.heldShotMasks = [];
          OffscreenCanvas.prototype.convertToBlob = async function(...args) {
            const blob = await encode.apply(this, args);
            await new Promise(resolve => window.heldShotMasks.push(resolve));
            return blob;
          };
          window.releaseShotMasks = () => {
            OffscreenCanvas.prototype.convertToBlob = encode;
            for (const release of window.heldShotMasks) release();
          };
        }"""
    )
    identical = changed | {
        "cases": [
            changed["cases"][0] | {"after": changed["cases"][0]["before"]},
            *changed["cases"][1:],
        ]
    }
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", identical)
    told(page)
    page.wait_for_function("window.heldShotMasks.length === 1")
    assert shot.evaluate(painted_pixels) == previous_pixels
    # Metadata arriving after image validation owns a new request; it cannot
    # smuggle an invalid crop into the already-preparing pair.
    invalid_focus = identical | {
        "cases": [
            identical["cases"][0]
            | {"focus": {"x": 900, "y": 200, "width": 200, "height": 200}},
            *identical["cases"][1:],
        ]
    }
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", invalid_focus)
    told(page)
    expect(shot.locator(".lf-error")).to_contain_text(
        "falls outside its captured images"
    )
    consume_browser_errors(page, "falls outside its captured images")
    assert shot.evaluate(painted_pixels) == previous_pixels
    page.evaluate("window.releaseShotMasks()")
    # Correcting metadata alone must recover without changing either image URL.
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", identical)
    told(page)
    expect(shot.locator(".lf-error")).to_have_count(0)
    expect(pixels).to_be_focused()
    expect(pixels).to_have_attribute("aria-pressed", "true")
    expect(shot.locator(".lf-shot-outline")).to_have_attribute(
        "aria-description", "identical"
    )
    corrected_pixels = shot.evaluate(painted_pixels)
    assert corrected_pixels["mask"]
    assert corrected_pixels["mask"] != previous_pixels["mask"]
    assert shot.locator(".lf-shotpixels img").evaluate(
        "node => node.src"
    ) == shot.locator('.lf-shotframe[data-lf-state="after"] img').evaluate(
        "node => node.src"
    )
    data_model.cmd_data_set(
        serve.page_dir, "gallery-visual-run", record | {"cases": record["cases"][1:]}
    )
    told(page)
    expect(case.locator(".lf-vr-title")).to_be_focused()
    expect(case.locator(".lf-vr-title")).to_have_text(record["cases"][1]["title"])
    expect(case.locator(".lf-vr-title")).to_be_in_viewport()


@pytest.mark.parametrize("viewport", [(390, 844), (1366, 768)])
def test_visual_review_refresh_keeps_the_focused_verdict_in_place(
    browser, serve, viewport
):
    """A source revision reflows reading content without moving the aimed action."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    resized(page, *viewport)
    widget = page.locator("#visual-review-run")
    case = widget.locator('.lf-vr-case[aria-hidden="false"]')
    verdict = case.get_by_role("checkbox", name="Looks right")
    verdict.scroll_into_view_if_needed()
    verdict.focus()
    scroll_settled(page)
    before = verdict.bounding_box()
    record = json.loads(VISUAL_REVIEW_GALLERY.with_suffix(".data.json").read_text())[
        "gallery-visual-run"
    ]
    result = (
        "Updated observation with enough reading text to occupy several lines. " * 8
    )
    changed = record | {
        "cases": [record["cases"][0] | {"result": result}, *record["cases"][1:]]
    }
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", changed)
    told(page)
    expect(case.locator(".lf-vr-result")).to_contain_text(result.strip())
    expect(verdict).to_be_focused()
    after = verdict.bounding_box()
    assert abs(after["y"] - before["y"]) <= 1, (before, after)
    assert abs(after["x"] - before["x"]) <= 1, (before, after)


def test_visual_review_text_refresh_retains_comparison_choice_and_focus(browser, serve):
    """An accessible description change does not replace the aligned image pair."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    widget = page.locator("#visual-review-run")
    case = widget.locator('.lf-vr-case[aria-hidden="false"]')
    control = case.get_by_role("button", name="Slider", exact=True)
    control.click()
    expect(control).to_have_attribute("aria-pressed", "true")
    control.focus()
    old_control = control.element_handle()
    before = control.bounding_box()
    record = json.loads(VISUAL_REVIEW_GALLERY.with_suffix(".data.json").read_text())[
        "gallery-visual-run"
    ]
    result = "The accessible description changes without replacing captured evidence."
    changed = record | {
        "cases": [record["cases"][0] | {"result": result}, *record["cases"][1:]]
    }
    data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", changed)
    told(page)
    expect(control).to_be_focused()
    assert control.evaluate("(node, old) => node === old", old_control)
    expect(control).to_have_attribute("aria-pressed", "true")
    expect(case.locator("lf-shot img").first).to_have_attribute(
        "alt", f"before: {record['cases'][0]['title']}. {result}"
    )
    expect(case.locator(".lf-shotstage")).to_have_attribute(
        "aria-label",
        f"Screenshot comparison — {record['cases'][0]['title']}. {result}",
    )
    after = control.bounding_box()
    assert abs(after["y"] - before["y"]) <= 1, (before, after)


def test_visual_review_source_reorder_keeps_the_focused_case_draft(browser, serve):
    """Moving a keyed case retains its comment editor, text selection and focus."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    widget = page.locator("#visual-review-run")
    case = widget.locator('.lf-vr-case[aria-hidden="false"]')
    comment_on_target(page, case)
    field = case.locator(".lf-fab-input")
    expect(field).to_be_focused()
    page.keyboard.type("Keep this draft while the case order changes")
    page.keyboard.press("Shift+ArrowLeft")
    selection = field.evaluate("node => [node.selectionStart, node.selectionEnd]")
    record = json.loads(VISUAL_REVIEW_GALLERY.with_suffix(".data.json").read_text())[
        "gallery-visual-run"
    ]
    data_model.cmd_data_set(
        serve.page_dir, "gallery-visual-run", record | {"cases": record["cases"][::-1]}
    )
    told(page)
    expect(widget.locator(".lf-vr-case").last).to_have_attribute(
        "data-lf-datum", record["cases"][0]["id"]
    )
    expect(field).to_be_focused()
    expect(field).to_have_js_property(
        "value", "Keep this draft while the case order changes"
    )
    assert (
        field.evaluate("node => [node.selectionStart, node.selectionEnd]") == selection
    )
    # The editor kept is the one typed into, so its undo history came with it.
    page.keyboard.press("ControlOrMeta+z")
    expect(field).not_to_have_js_property(
        "value", "Keep this draft while the case order changes"
    )


@pytest.mark.parametrize("change", ["case-dropped", "source-cleared"])
def test_a_comment_being_written_on_a_visual_case_stays_in_hand_as_the_case_goes(
    browser, serve, change
):
    """The comment box seated on a case goes back beside the review when a new run
    drops that case or the source is cleared, and the user goes on typing in it.
    Before, the case's article took the box out of the document: it blurred once, and
    a dropped case left the user on the next case's title."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    resized(page, 1366, 768)
    datum = page.locator("#visual-review-run [data-lf-datum]").first
    case = datum.get_attribute("data-lf-datum")
    # A case with no threads draws no discussion; the box seated there opens it.
    discussion = page.locator(f'.lf-vr-case[data-lf-datum="{case}"] .lf-vr-discussion')
    expect(discussion).to_be_hidden()
    comment_on_target(page, datum)
    box = page.locator(".lf-fab-input")
    expect(page.locator(".lf-vr-threads .lf-fab-input")).to_be_focused()
    expect(discussion).to_be_visible()
    page.keyboard.type("Half")
    box.evaluate(
        "box => { window.blurs = 0; box.addEventListener('blur', () => window.blurs++); }"
    )
    if change == "source-cleared":
        data_model.cmd_data_clear(serve.page_dir, "gallery-visual-run")
    else:
        source = VISUAL_REVIEW_GALLERY.with_suffix(".data.json")
        run = json.loads(source.read_text())["gallery-visual-run"]
        run["cases"] = [each for each in run["cases"] if each["id"] != case]
        data_model.cmd_data_set(serve.page_dir, "gallery-visual-run", run)
    told(page)
    expect(page.locator(f'[data-lf-datum="{case}"]')).to_have_count(0)
    expect(box).to_be_focused()
    expect(box).to_be_in_viewport()
    assert page.evaluate("window.blurs") == 0
    page.keyboard.type(" a thought")
    expect(box).to_have_js_property("value", "Half a thought")


def test_visual_review_returns_to_case_feedback_on_phone(browser, serve):
    """Case feedback reveals preserved drafts and chosen threads below tall captures."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    resized(page, 390, 844)
    widget = page.locator("#visual-review-run")
    case = widget.locator('.lf-vr-case[aria-hidden="false"]')
    case.get_by_role("button", name="Add feedback").click()
    field = case.locator(".lf-fab-input")
    expect(field).to_be_focused()
    page.keyboard.type("Keep the return route")
    page.keyboard.press("Escape")
    widget.locator(".lf-vr-case-button").nth(1).click()
    widget.locator(".lf-vr-case-button").first.click()
    case.get_by_role("button", name="Add feedback").click()
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "Keep the return route")
    expect(field).to_be_in_viewport(ratio=1)
    with sending(page, "post the preserved feedback"):
        page.keyboard.press("ControlOrMeta+Enter")
    first_thread = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment" and event["text"] == "Keep the return route"
    )
    case.get_by_role("button", name="Add feedback").click()
    page.keyboard.type("Keep destination names visible")
    with sending(page, "post another conversation on the case"):
        page.keyboard.press("ControlOrMeta+Enter")
    case.get_by_role("button", name="2 threads", exact=True).click()
    case.get_by_role("button", name="Keep the return route", exact=True).click()
    selected = case.locator(f'.lf-page-thread[data-thread="{first_thread}"]')
    expect(selected).to_be_focused()
    expect(selected).to_be_in_viewport(ratio=1)


def test_visual_review_approvals_survive_reload_and_undo(browser, serve):
    """Approval is reversible and independent of case navigation. A case's row says
    Looks right once checked and nothing before, in a line it holds either way."""
    page = open_page(browser, serve(VISUAL_REVIEW_GALLERY))
    resized(page, 702, 898)
    widget = page.locator("#visual-review-run")
    case = widget.locator('.lf-vr-case[aria-hidden="false"]')
    row = widget.locator('.lf-vr-case-button[aria-current="true"]')
    ids = []
    for _ in range(3):
        ids.append(case.get_attribute("data-lf-datum"))
        status = row.locator(".lf-vr-case-status")
        expect(status).to_be_hidden()
        height = row.bounding_box()["height"]
        with sending(page, "approve selected case"):
            case.get_by_role("checkbox", name="Looks right").check()
        expect(case).to_have_attribute("data-lf-datum", ids[-1])
        expect(status).to_be_visible()
        expect(status).to_have_text("Looks right")
        assert row.bounding_box()["height"] == height
        if len(ids) < 3:
            case.get_by_role("button", name="Next unchecked").click()
    assert len(set(ids)) == 3
    expect(case.get_by_role("button", name="Next unchecked")).to_be_disabled()
    page.reload()
    expect(widget.locator(".lf-vr-progress")).to_contain_text("3 of 3")
    undo(page)
    expect(widget.locator(".lf-vr-progress")).to_contain_text("2 of 3")
    case.get_by_role("button", name="Next unchecked").click()
    expect(case).to_have_attribute("data-lf-datum", ids[-1])
    expect(case.get_by_role("checkbox", name="Looks right")).not_to_be_checked()
