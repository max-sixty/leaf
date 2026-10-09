"""The composer shows the actual page beneath a drawing, frozen beside the draft."""

import pytest
from playwright.sync_api import expect
from render_harness import holding, leaf_page, open_page, rendered
from test_render_drawing import draw_over, trace

pytestmark = pytest.mark.nightly

CONTEXT_PAGE = leaf_page(
    "drawing context",
    '<h1 id="title">Review the highlighted area</h1>'
    '<div id="subject">Words underneath the drawing</div>',
    head="<style>#subject { width: 320px; height: 160px; padding: 0; "
    "background: rgb(239, 82, 76); color: black; }</style>",
)


@pytest.mark.parametrize("scheme,touch", [("light", False), ("dark", True)])
def test_drawing_preview_contains_page_content_and_freezes_it(
    browser, serve, scheme, touch
):
    context = browser.new_context(
        color_scheme=scheme,
        has_touch=touch,
        viewport={"width": 390 if touch else 1280, "height": 900},
    )
    page = open_page(browser, serve(CONTEXT_PAGE), context=context, color_scheme=scheme)
    target = page.locator("#subject")
    draw_over(page, target)
    preview = page.locator(".lf-composer-drawing canvas")
    expect(preview).to_have_attribute("data-lf-drawing-context", "ready")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    pixels = preview.evaluate("""canvas => {
      const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      let red = 0, ink = 0;
      for (let i = 0; i < pixels.length; i += 4) {
        if (pixels[i] > 200 && pixels[i+1] < 120 && pixels[i+2] < 120) red++;
            if (pixels[i] < 180 && pixels[i+1] > 60 && pixels[i+2] > 100) ink++;
      }
      return {red, ink, picture: canvas.toDataURL()};
    }""")
    assert pixels["red"] > 1000, "the picture must show the page underneath the strokes"
    assert pixels["ink"] > 20, "the picture must include the drawing over the page"
    shelf = page.locator(".lf-fab-bar .lf-composer-media")
    assert shelf.evaluate("el => el.scrollWidth <= el.clientWidth"), (
        "both drawing controls must fit"
    )
    for label in ("Undo last stroke", "Remove drawing"):
        button = shelf.get_by_role("button", name=label)
        expect(button).to_be_visible()
        if touch:
            box = button.bounding_box()
            assert box["width"] >= 44 and box["height"] >= 44
    target.evaluate("el => el.style.background = 'blue'")
    page.keyboard.type("A comment about this area")
    rendered(page)
    assert preview.evaluate("canvas => canvas.toDataURL()") == pixels["picture"]


def test_drawing_preview_reads_shadow_content_and_scrolled_area(browser, serve):
    page = open_page(browser, serve(CONTEXT_PAGE))
    target = page.locator("#subject")
    target.evaluate("""el => {
      el.style.background = 'transparent';
      const root = el.attachShadow({mode: 'open'});
      root.innerHTML = '<div style="height:160px; overflow:auto">'
        + '<div style="height:160px;background:blue">Hidden above</div>'
        + '<div style="height:160px;background:rgb(239,82,76)">Visible detail</div></div>';
      root.firstChild.scrollTop = 160;
    }""")
    draw_over(page, target)
    preview = page.locator(".lf-composer-drawing canvas")
    expect(preview).to_have_attribute("data-lf-drawing-context", "ready")
    colors = preview.evaluate("""canvas => {
      const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      let red = 0, blue = 0;
      for (let i = 0; i < pixels.length; i += 4) {
        if (pixels[i] > 200 && pixels[i+1] < 120 && pixels[i+2] < 120) red++;
        if (pixels[i] < 20 && pixels[i+1] < 20 && pixels[i+2] > 200) blue++;
      }
      return {red, blue};
    }""")
    assert colors["red"] > 1000
    assert colors["blue"] == 0, (
        "the preview must preserve the content viewport's scroll"
    )


def test_drawing_preview_keeps_fixed_content_after_root_scroll(browser, serve):
    page = open_page(browser, serve(CONTEXT_PAGE))
    page.locator("#subject").evaluate("""el => {
      document.body.style.height = '2000px';
      Object.assign(el.style, {position:'fixed', left:'50px', top:'100px'});
      // An unrelated rendering island must never participate in this capture.
      const other = document.createElement('canvas');
      other.toDataURL = () => { throw new Error('unrelated canvas captured'); };
      document.body.append(other);
      window.scrollTo(0, 500);
    }""")
    target = page.locator("#subject")
    draw_over(page, target)
    preview = page.locator(".lf-composer-drawing canvas")
    expect(preview).to_have_attribute("data-lf-drawing-context", "ready")
    red = preview.evaluate("""canvas => {
      const pixels = canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
      let red = 0;
      for (let i=0; i<pixels.length; i+=4)
        if(pixels[i]>200 && pixels[i+1]<120 && pixels[i+2]<120) red++;
      return red;
    }""")
    assert red > 1000, (
        "root scrolling must not move fixed page content out of its picture"
    )


def test_drawing_preview_failure_keeps_ink_and_reports_missing_context(browser, serve):
    page = open_page(browser, serve(CONTEXT_PAGE))
    page.route(
        "**/vendor/drawing-context.esm.js",
        lambda route: route.fulfill(
            status=200,
            content_type="text/javascript",
            body="export function domToCanvas() { throw new Error('capture refused'); }",
        ),
    )
    draw_over(page, page.locator("#subject"))
    preview = page.locator(".lf-composer-drawing canvas")
    expect(preview).to_have_attribute("data-lf-drawing-context", "unavailable")
    expect(page.get_by_text("Page preview unavailable", exact=True)).to_be_visible()
    expect(page.get_by_role("img", name="page preview unavailable")).to_be_visible()
    assert preview.evaluate("""canvas => {
      const pixels = canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
      return pixels.some((value,index) => index%4===3 && value>0);
    }"""), "a failed context capture must leave the user's drawing visible"


def test_drawing_preview_crops_fixed_svg_after_root_scroll(browser, serve):
    page = open_page(browser, serve(CONTEXT_PAGE))
    page.locator("#subject").evaluate("""el => {
      document.body.style.height = '2000px';
      el.innerHTML = '<svg width="320" height="160" style="position:fixed;left:50px;top:100px">'
        + '<rect width="320" height="160" fill="rgb(239,82,76)" /></svg>';
      window.scrollTo(0, 500);
    }""")
    draw_over(page, page.locator("#subject svg"))
    preview = page.locator(".lf-composer-drawing canvas")
    expect(preview).to_have_attribute("data-lf-drawing-context", "ready")
    pixel = preview.evaluate(
        "canvas => [...canvas.getContext('2d').getImageData(0,0,1,1).data]"
    )
    assert all(
        abs(actual - expected) <= 1
        for actual, expected in zip(pixel, [239, 82, 76, 255], strict=True)
    ), "fixed SVG content must retain its viewport origin inside the crop"


def test_drawing_preview_captures_one_frame_after_its_renderer_arrives(browser, serve):
    """A transform during the renderer download moves the page and preview ink together."""
    page = open_page(browser, serve(CONTEXT_PAGE))
    held = []
    page.route("**/vendor/drawing-context.esm.js", lambda route: held.append(route))
    target = page.locator("#subject")
    draw_over(page, target, points=((0.25, 0.375), (0.5, 0.5), (0.75, 0.625)))
    holding(page, held, 1, "the drawing context renderer")
    preview = page.locator(".lf-composer-drawing canvas")
    assert preview.evaluate("canvas => [canvas.width, canvas.height]") == [208, 88]

    target.evaluate(
        "el => { el.style.transformOrigin = '0 0'; el.style.transform = 'scale(.5)'; }"
    )
    held[0].continue_()
    expect(preview).to_have_attribute("data-lf-drawing-context", "ready")
    assert preview.evaluate("canvas => [canvas.width, canvas.height]") == [128, 68], (
        "the crop and ink must both use the subject's frame at capture"
    )
    red = preview.evaluate("""canvas => {
      const pixels = canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
      let red = 0;
      for (let i=0; i<pixels.length; i+=4)
        if(pixels[i]>200 && pixels[i+1]<120 && pixels[i+2]<120) red++;
      return red;
    }""")
    assert red > 8000, "the transformed page must still fill the contextual crop"


@pytest.mark.parametrize("backing", ["solid", "translucent", "gradient", "svg"])
def test_drawing_preview_preserves_the_painted_area(browser, serve, backing):
    page = open_page(browser, serve(CONTEXT_PAGE))
    target = page.locator("#subject")
    target.evaluate(
        """(el, backing) => {
      if (backing === 'solid') {
        el.style.background = 'transparent'; el.style.color = 'white';
        el.parentElement.style.background = 'rgb(20,40,60)';
      } else if (backing === 'translucent') {
        el.style.background = 'rgba(255,0,0,.5)';
        el.parentElement.style.background = 'white';
      } else if (backing === 'gradient') {
        el.style.background = 'transparent';
        el.parentElement.style.background = 'linear-gradient(to right, red, blue)';
      } else {
        el.innerHTML = '<svg id="painted-svg" width="320" height="160">'
          + '<rect width="320" height="160" fill="rgb(239,82,76)" /></svg>';
      }
    }""",
        backing,
    )
    if backing == "svg":
        target = page.locator("#painted-svg")
    draw_over(page, target)
    preview = page.locator(".lf-composer-drawing canvas")
    expect(preview).to_have_attribute("data-lf-drawing-context", "ready")
    pixel = preview.evaluate(
        "canvas => [...canvas.getContext('2d').getImageData(0,0,1,1).data]"
    )
    if backing == "solid":
        assert pixel == [20, 40, 60, 255]
    elif backing == "translucent":
        assert pixel[0] == 255 and pixel[3] == 255
        assert abs(pixel[1] - 127) <= 1 and abs(pixel[2] - 127) <= 1
    elif backing == "gradient":
        assert pixel[0] > 20 and pixel[2] > 20 and pixel[3] == 255
    else:
        assert all(
            abs(actual - expected) <= 1
            for actual, expected in zip(pixel, [239, 82, 76, 255], strict=True)
        )


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_drawing_preview_contains_theme_colored_svg_strokes_inside_a_sample(
    browser, serve, scheme
):
    source = leaf_page(
        "sample drawing context",
        '<h1 id="title">Practice</h1><lf-sample id="practice" window>'
        '<template id="practice-page" data-sample><h1>Field report</h1>'
        '<figure id="routes"><svg class="drawing" viewBox="0 0 600 170">'
        '<path d="M30 80 Q150 0 285 80 T570 80" fill="none" '
        'stroke="var(--accent)" stroke-width="8" />'
        '<path d="M30 140 L280 140 L570 80" fill="none" '
        'stroke="var(--muted)" stroke-width="4" />'
        '<text x="320" y="155">Meadow route</text></svg>'
        "<figcaption>Two routes</figcaption></figure></template></lf-sample>",
    )
    page = open_page(browser, serve(source), color_scheme=scheme)
    sample = page.frame_locator("#practice iframe")
    svg = sample.locator("#routes svg")
    svg.scroll_into_view_if_needed()
    box = svg.bounding_box()
    points = [
        (box["x"] + box["width"] * x / 600, box["y"] + box["height"] * y / 170)
        for x, y in (
            (357, 90),
            (376, 82),
            (399, 83),
            (418, 98),
            (421, 119),
            (402, 132),
            (379, 130),
            (361, 116),
            (357, 90),
        )
    ]
    page.mouse.click(*points[0])
    page.keyboard.press("w")
    expect(sample.locator("html")).to_have_attribute("data-lf-draw-mode", "")
    trace(page, points)
    preview = sample.locator(".lf-composer-drawing canvas")
    expect(preview).to_have_attribute("data-lf-drawing-context", "ready")
    color = (
        svg.locator("path")
        .nth(1)
        .evaluate(
            "el => getComputedStyle(el).stroke.match(/[0-9.]+/g).slice(0,3).map(Number)"
        )
    )
    matching = preview.evaluate(
        """(canvas, color) => {
          const pixels = canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
          let matching = 0;
          for (let at=0; at<pixels.length; at+=4)
            if (color.every((channel,index) => Math.abs(channel-pixels[at+index])<=2)) matching++;
          return matching;
        }""",
        color,
    )
    assert matching > 40, (
        "the sample preview must contain the muted route beneath the accent-colored ink"
    )
