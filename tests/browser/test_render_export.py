"""Preview and offline export tests."""

import hashlib
import json
import re

import pytest
from click.testing import CliRunner
from interact_support import (
    append_carried_log_record,
)
from leaf_dev.example_data import patch_manifest
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATION_PAGE, live_url
from render_cases_layout import solid_png
from render_cases_navigation import (
    source_revision,
)
from render_harness import (
    leaf_page,
    open_page,
    round_trip,
    sending,
    write,
)

from browser.threads import open_panel_thread
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import exporting as exporting_model
from leaf import files as files_model
from leaf import media as media_model
from leaf.render_checks import HANDOVER_DEADLINE_MS, wait_until_ready
from leaf.structure import UTF8_BOM

pytestmark = pytest.mark.shifts_unsurveyed

from journeys.test_render_export import (  # noqa: F401 (fixtures)
    OFFLINE_REGISTRY,
    OFFLINE_WIDGET,
    PIXEL,
    POLICY_ATTEMPTS,
    ROOT,
    _reachable,
    requested_documents,
)


def test_interactive_export_with_an_obligation_reaches_application_presentation(
    browser, serve, tmp_path
):
    """Offline mode omits page controls without leaving their ticket pending."""
    serve(ROOT / "examples" / "notification-playground.html")
    interactive = tmp_path / "interactive-with-ask.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "export",
            str(serve.page_dir),
            "--out",
            str(interactive),
        ],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output

    page = browser.new_page()
    page.goto(interactive.as_uri(), wait_until="load")
    expect(page.locator('meta[name="viewport"]')).to_have_attribute(
        "content", "width=device-width, initial-scale=1, viewport-fit=cover"
    )
    expect(page.locator("body")).to_have_attribute(
        "data-lf-presented", "1", timeout=HANDOVER_DEADLINE_MS
    )
    expect(page.locator(".lf-chrome > #lf-media-viewer:not([open])")).to_have_count(1)
    expect(page.locator(".lf-floating-panel")).to_have_count(0)


def test_an_interactive_export_paints_a_widget_owned_text_box(browser, serve, tmp_path):
    """A text box paints in the repaint frame, which an export mounts without page controls.

    A choosable group builds its addition field offline too. Its placeholder, disabled
    Add and empty-field flag are that paint's; focus alone repaints the placeholder with
    its send key, and typing repaints the flag."""
    serve(OBLIGATION_PAGE)
    interactive = tmp_path / "interactive-addition.html"
    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "export", str(serve.page_dir), "--out", str(interactive)],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output

    page = browser.new_page()
    page.goto(interactive.as_uri(), wait_until="load")
    expect(page.locator("body")).to_have_attribute(
        "data-lf-presented", "1", timeout=HANDOVER_DEADLINE_MS
    )
    form = page.locator("#jobs > .lf-another")
    field = form.locator("leaf-text")
    add = form.locator(".lf-compose-submit")
    expect(field).to_have_attribute("placeholder", "Add another option")
    expect(add).to_have_attribute("aria-disabled", "true")
    expect(add).to_have_attribute("data-lf-empty", "")
    expect(add).to_be_hidden()
    field.click()
    expect(field).to_have_attribute("placeholder", "Add another option ⏎")
    write(field, "Portrait sketch")
    expect(add).not_to_have_attribute("data-lf-empty", "")


def test_interactive_export_runs_captured_local_behavior_without_a_host(
    browser, serve, tmp_path
):
    """One file boots the captured runtime, but never resurrects its host boundary."""
    source = leaf_page(
        "offline interactive",
        """
<h1>Offline interactive</h1>
<lf-offline-test id="offline-widget" choice="idle"></lf-offline-test>
<a id="jump" href="#destination">Jump locally</a>
<h2 id="destination">Destination</h2>
""",
    )
    url = serve(
        source,
        page_files={
            "registry.json": json.dumps(OFFLINE_REGISTRY),
            "widgets/lf-offline-test.js": OFFLINE_WIDGET,
        },
    )
    live = open_page(browser, url)
    with sending(live, "the accepted page-owned choice"):
        live.locator("#offline-widget").get_by_role(
            "button", name="Choose on host"
        ).click()
    round_trip(live)
    expect(live.locator("#offline-widget #choice")).to_have_text("chosen")
    live.close()

    # Export resolves the stamped artifact, never the page's mutable source.
    (serve.page_dir / "page" / "widgets" / "lf-offline-test.js").write_text(
        'throw new Error("mutable widget source escaped its revision");',
        encoding="utf-8",
    )

    interactive = tmp_path / "interactive.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "export",
            str(serve.page_dir),
            "--out",
            str(interactive),
        ],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["file"] == str(interactive)

    page = browser.new_page(viewport={"width": 1000, "height": 800})
    external = []
    document_url = interactive.as_uri()
    page.on(
        "request",
        lambda request: (
            external.append(request.url)
            if request.url != document_url
            and not request.url.startswith(("data:", "blob:"))
            else None
        ),
    )
    page.goto(document_url, wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(page.locator("#offline-widget #choice")).to_have_text("chosen")
    expect(page.locator(".lf-chrome > #lf-media-viewer:not([open])")).to_have_count(1)
    expect(page.locator(".lf-floating-panel")).to_have_count(0)
    assert (
        page.locator("#offline-widget #local").evaluate(
            "control => getComputedStyle(control).color"
        )
        == "rgb(12, 34, 56)"
    )

    page.locator("#offline-widget").get_by_role(
        "button", name="Increment locally"
    ).click()
    expect(page.locator("#offline-widget #local-value")).to_have_text("1")
    page.locator("#jump").click()
    assert page.url.endswith("#destination")

    expect(page.locator("#offline-widget #choose")).to_be_disabled()
    expect(page.locator("#offline-widget #unavailable")).to_have_text(
        "no agent or server is available"
    )
    refused = page.locator("#offline-widget").evaluate(
        """owner => [
          owner.choose(),
          owner.controller.dispatch({kind: 'undo', target: 'missing'}),
        ]"""
    )
    assert refused == [None, None]
    expect(page.locator("#offline-widget #choice")).to_have_text("chosen")
    assert external == []


def test_interactive_export_hydrates_captured_deferred_values_offline(
    browser, serve, tmp_path
):
    """A frozen interactive copy keeps unopened deferred payloads usable."""
    serve(
        leaf_page(
            "offline deferred data",
            '<h1>Review</h1><lf-diff id="patch" source="review-patch" collapsed>'
            "<pre></pre></lf-diff>",
        )
    )
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        '@@ -1 +1 @@\n-return "old"\n+return "new"\n'
    )
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch_manifest(patch))
    interactive = tmp_path / "deferred-interactive.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "export",
            str(serve.page_dir),
            "--out",
            str(interactive),
        ],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output

    page = browser.new_page()
    external = []
    document_url = interactive.as_uri()
    page.on(
        "request",
        lambda request: (
            external.append(request.url)
            if request.url != document_url
            and not request.url.startswith(("data:", "blob:"))
            else None
        ),
    )
    page.goto(document_url, wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    page.locator("lf-diff summary").click()
    expect(
        page.locator('lf-diff [data-lf-datum=\'["app.py","new",1]\']')
    ).to_have_count(1)
    assert external == []


def test_an_export_keeps_visual_review_images_and_inspection_offline(
    browser, serve, tmp_path
):
    """Data-owned captures, including unopened cases, travel with the offline review."""
    source = leaf_page(
        "Offline visual review",
        '<lf-visual-review id="review" source="visual-run"></lf-visual-review>',
    )
    cases = []
    media = {}
    for index, title in enumerate(("Navigation", "Search")):
        width = 320 + index * 40
        captures = [
            solid_png(width, 200, color) for color in ((232, 226, 213), (214, 226, 235))
        ]
        before, after = (
            f"/media/{hashlib.sha256(image).hexdigest()[:16]}.png" for image in captures
        )
        media.update(zip((before, after), captures, strict=True))
        cases.append(
            {
                "id": title.lower(),
                "title": title,
                "path": f"/{title.lower()}",
                "action": "Open the page.",
                "result": "The background changed.",
                "classification": "changed",
                "before": before,
                "after": after,
                "capture": {
                    "observedAt": "2026-10-22T10:00:00-07:00",
                    "browser": "Chrome",
                    "browserVersion": "140",
                    "viewport": {"width": width, "height": 200},
                    "deviceScaleFactor": 1,
                    "colorScheme": "light",
                    "locale": "en-US",
                    "timezone": "America/Los_Angeles",
                },
            }
        )
    serve(source, packages=("visual-review",), media=media)
    data_model.cmd_data_set(
        serve.page_dir,
        "visual-run",
        {
            "title": "Visual review",
            "base": {"revision": "base"},
            "candidate": {"revision": "candidate"},
            "cases": cases,
        },
    )
    out = tmp_path / "visual-review.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    context = browser.new_context(offline=True, viewport={"width": 1200, "height": 900})
    page = context.new_page()
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    page.goto(out.as_uri(), wait_until="load")
    wait_until_ready(page)
    widget = page.locator("#review")
    selected = widget.locator('.lf-vr-case[aria-hidden="false"]')
    for index, case in enumerate(cases):
        if index:
            widget.locator('.lf-vr-case-button[aria-current="true"]').click()
            page.keyboard.press("n")
        expect(selected).to_have_attribute("data-lf-datum", case["id"])
        images = selected.locator("lf-shot img")
        expect(images).to_have_count(2)
        for image in images.all():
            expect(image).to_have_js_property("naturalWidth", 320 + index * 40)
        assert images.evaluate_all(
            "async images => { await Promise.all(images.map(image => image.decode())); return true; }"
        )
    shot = selected.locator("lf-shot")
    shot.get_by_role("button", name="Slider", exact=True).click()
    comparison = shot.locator("wa-comparison")
    handle = comparison.get_by_role("scrollbar")
    handle.press("Home")
    expect(comparison).to_have_js_property("position", 0)
    handle.press("ArrowRight")
    expect(comparison).to_have_js_property("position", 1)
    assert [url for url in requests if not url.startswith(("blob:", "data:"))] == [
        out.as_uri()
    ]


def test_an_export_keeps_utf8(browser, serve, tmp_path):
    literal = "urn:leaf-resource:" + "a" * 64
    source = leaf_page(
        "Café handoff",
        f'<h1>Café handoff</h1><p id="literal">{literal}</p><section id="native-shadow"><template shadowrootmode="open"><p id="shadow-text">Captured shadow text</p></template></section><script id="body-probe" type="module">window.order.push("body");</script>',
        head='<style>#literal::after {content:"</noscript>";}</style><meta name="parser-probe" content="head"><script id="head-probe" type="module">window.order = [document.querySelector("#head-probe").parentElement.tagName.toLowerCase()];</script>',
    )
    serve(source)
    out = tmp_path / "cafe.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    assert out.read_text(encoding="utf-8").startswith(UTF8_BOM)

    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    wait_until_ready(page)
    assert page.evaluate("document.characterSet") == "UTF-8"
    assert page.evaluate("window.order") == ["head", "body"]
    assert page.evaluate("document.doctype.name") == "html"
    assert page.locator("head > meta[charset]").count() == 1
    expect(page.locator("#native-shadow #shadow-text")).to_have_text(
        "Captured shadow text"
    )
    expect(page.locator("#literal")).to_have_text(literal)
    expect(page.get_by_role("heading", name="Café handoff")).to_have_count(1)
    expect(page.get_by_role("heading", name="Café handoff")).to_be_visible()
    disabled = browser.new_page(java_script_enabled=False)
    disabled.goto(out.as_uri(), wait_until="load")
    expect(disabled.get_by_role("heading", name="Café handoff")).to_have_count(1)
    expect(disabled.locator("#literal")).to_have_text(literal)
    expect(disabled.locator("#literal")).to_have_css(
        "content", '"</noscript>"', pseudo="after"
    )


def test_an_export_without_scripts_keeps_text_layout_and_alt_text(
    browser, serve, tmp_path
):
    source = (
        leaf_page(
            "Readable record",
            '<h1>Readable record</h1><p id="words">The recording compares two routes.</p>'
            '<img id="poster" src="/media/d7cf2b4e22c063dd.png?ignored=1#frame" alt="First frame: two routes">'
            '<video controls src="/media/2930ad3df7819c50.mp4#t=2"></video>'
            '<div id="layout" style="display:grid;grid-template-columns:1fr 1fr;background:url(/media/d7cf2b4e22c063dd.png)"><p>Before</p><p>After</p></div>',
            head="<style>@media screen { #words { color: rgb(12, 34, 56); background:url(/media/d7cf2b4e22c063dd.png); } }</style>",
        )
        .replace("<html ", '<html data-author="record" ')
        .replace("<body>", '<body class="authored">')
    )
    serve(source)
    out = tmp_path / "readable.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    page = browser.new_page(
        java_script_enabled=False, viewport={"width": 390, "height": 844}
    )
    requests = []
    failures = []
    page.on("request", lambda request: requests.append(request.url))
    page.on("requestfailed", lambda request: failures.append(request.url))
    page.goto(out.as_uri(), wait_until="load")
    expect(page.get_by_role("heading", name="Readable record")).to_be_visible()
    expect(page.get_by_role("note")).to_contain_text("JavaScript")
    expect(page.locator("#words")).to_have_css("color", "rgb(12, 34, 56)")
    expect(page.locator("#layout")).to_have_css("display", "grid")
    assert page.locator("#poster").get_attribute("alt") == "First frame: two routes"
    assert page.locator("#poster").get_attribute("src") is None
    assert page.locator("video").get_attribute("src") is None
    assert page.locator("#poster").get_attribute("data-lf-media-width") == "320"
    assert page.locator("html").get_attribute("data-author") == "record"
    assert page.locator("body").get_attribute("class") == "authored"
    assert page.locator("script[src]").count() == 0
    assert failures == []
    assert requests == [out.as_uri()]
    assert page.locator("body").bounding_box()["width"] <= 390


def test_an_export_draws_a_chart_whose_body_is_plot_code(browser, serve, tmp_path):
    """An lf-chart body is a Plot expression the widget compiles, so the export's policy
    admits compiling it as the served page's does. Refused, the chart shows an error
    over its source in the file a user was sent, while it drew in the author's
    preview."""
    serve(
        leaf_page(
            "Exported chart",
            '<h1>Exported chart</h1><lf-chart id="c"><pre>'
            '{ariaLabel: "one bar of 3", marks: [Plot.barY([3])]}'
            "</pre></lf-chart>",
        )
    )
    out = tmp_path / "chart.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(page.locator("#c svg[role=img]")).to_have_attribute(
        "aria-label", "one bar of 3"
    )
    expect(page.locator("#c .lf-error")).to_have_count(0)


def test_an_export_keeps_its_quiet_words_off_screen(browser, serve, tmp_path):
    """A word written for a user listening (`.lf-quiet`), here a highlighted code
    line's, is clipped on screen in an export as in the live page. The rule that clips
    it once lived only in the chrome's sheet, which an export never adopts, so quiet
    words in an exported file appeared on screen as well as their tint."""
    serve(
        leaf_page(
            "Quiet words",
            '<h1>Quiet words</h1><lf-code id="m" language="python" hi="1">'
            "<pre>ship()</pre></lf-code>",
        )
    )
    out = tmp_path / "quiet.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    quiet = page.locator("#m .lf-quiet")
    expect(quiet).to_have_count(1)
    box = quiet.evaluate(
        "el => { const r = el.getBoundingClientRect();"
        " return [r.width, r.height, getComputedStyle(el).clipPath]; }"
    )
    assert box[0] <= 1 and box[1] <= 1 and box[2] != "none", box


def test_an_export_embeds_only_the_widgets_its_markup_names(browser, serve, tmp_path):
    """A widget the page and its messages never name brings none of its modules.

    The page draws code and a reply carries a diagram; nothing names a diff, so
    Pierre's renderer stays out of the file.
    """
    serve(
        leaf_page(
            "Reachable modules",
            '<h1>Reachable</h1><lf-code id="snippet" language="python">'
            "<pre>print('hi')</pre></lf-code>",
        )
    )
    root = append_carried_log_record(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Sketch it?"},
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": root["id"],
            "revision": 1,
            "text": "Here:",
            "markup": '<lf-diagram id="sketch"><pre>flowchart LR\n  A --> B\n'
            "</pre></lf-diagram>",
        },
    )
    out = tmp_path / "reachable.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    html = out.read_text(encoding="utf-8")
    composed = json.loads(
        re.search(
            r'<script type="application/json" data-lf-export>(.*?)</script>',
            html,
            re.DOTALL,
        )[1]
    )["document"]
    imports = json.loads(
        re.search(r'<script type="importmap"[^>]*>(.*?)</script>', composed, re.DOTALL)[
            1
        ]
    )["imports"]
    assert {"leaf:/widgets/lf-code.js", "leaf:/widgets/lf-diagram.js"} <= set(imports)
    assert not {
        "leaf:/widgets/lf-diff.js",
        "leaf:/vendor/pierre-diffs.esm.js",
    } & set(imports)

    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(page.locator("#snippet")).to_contain_text("print")


def test_a_historical_export_embeds_its_captured_css_graph(browser, serve, tmp_path):
    """Nested imports and images come from the captured revision, not mutable files."""
    icon = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"><rect width="24" height="24" fill="navy"/></svg>'
    source = leaf_page(
        "Captured appearance",
        """
<h1 id="title">Captured appearance</h1>
<figure id="badge"><img src="/page/icon.svg" alt="Captured badge" width="24" height="24"></figure>
<svg id="vector" width="24" height="24"><image href="/page/icon.svg" width="24" height="24"></image></svg>
<img id="responsive" srcset="/page/icon.svg 1x, /page/icon-2.svg 2x" alt="Responsive badge">
<p id="inline" style="background-image: url('/page/icon.svg')">Inline asset</p>
<pre id="quoted"><code>url('/page/icon.svg')</code></pre>
""",
        head='<link rel="stylesheet" href="/page/styles/main.css">',
    )
    serve(
        source,
        page_files={
            "icon.svg": icon,
            "icon-2.svg": icon.replace("navy", "green"),
            "styles/main.css": """
@import "./nested/palette.css" layer(captured) supports(display: grid) screen;
#title { color: var(--export-tone) !important; }
""",
            "styles/nested/palette.css": """
@import "../main.css";
body { --export-tone: rgb(12, 34, 56); }
#badge { background-image: url('../../icon.svg'); }
""",
        },
    )
    # Replacing, not writing through the initialized fixture's immutable hardlinks.
    files_model.replace_files(
        [
            (
                serve.page_dir / "page/styles/nested/palette.css",
                b"body { --export-tone: red; }",
                False,
            ),
            (
                serve.page_dir / "page/icon.svg",
                icon.replace('"24"', '"48"').encode(),
                False,
            ),
        ]
    )
    out = tmp_path / "captured.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    page = browser.new_page()
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    page.goto(out.as_uri(), wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(page.locator("#title")).to_have_css("color", "rgb(12, 34, 56)")
    expect(page.get_by_role("img", name="Captured badge")).to_have_js_property(
        "naturalWidth", 24
    )
    assert page.locator("#vector image").get_attribute("href").startswith("blob:")
    assert page.locator("#responsive").get_attribute("srcset").count("blob:") == 2
    expect(page.locator("#quoted")).to_have_text("url('/page/icon.svg')")
    for selector in ("#badge", "#inline"):
        assert (
            page.locator(selector)
            .evaluate("el => getComputedStyle(el).backgroundImage")
            .startswith('url("blob:')
        )
    assert [url for url in requests if not url.startswith(("data:", "blob:"))] == [
        out.as_uri()
    ]


def test_a_gloss_keeps_its_explanation_in_print(browser, serve):
    """Hover is only the live page's presentation. Print has no pointer contract, so
    the author-written tip becomes visible inline."""
    source = leaf_page(
        "gloss export",
        """
<h1>Rollout</h1>
<p>Start with a <lf-gloss tip="A thin path through the real system."
  >walking skeleton</lf-gloss> before parallelizing.</p>
""",
    )
    url = serve(source)

    live = browser.new_page(viewport={"width": 1200, "height": 900})
    live.goto(url, wait_until="load")
    live.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    tip = live.locator(".lf-gloss-popover")
    expect(tip).to_be_hidden()
    live.emulate_media(media="print")
    expect(tip).to_be_visible()
    assert tip.evaluate("el => getComputedStyle(el).position") == "static"


@pytest.mark.parametrize("resolved", [False, True], ids=["open", "resolved"])
def test_inline_threads_keep_their_words_without_live_controls_in_print(
    browser, serve, tmp_path, resolved
):
    """Paper shows even a closed thread, and none of its live controls."""
    url = serve(
        leaf_page(
            "thread export",
            '<h1>Review</h1><lf-diff id="patch" source="review-patch">'
            "<pre></pre></lf-diff>",
        )
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        '@@ -1 +1 @@\n-return "old"\n+return "new"\n',
    )
    image = tmp_path / "evidence.svg"
    image.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24">'
        '<rect width="24" height="24" fill="navy"/></svg>'
    )
    image_url = media_model.cmd_media(serve.page_dir, [image])[0]["path"]
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep this check beside the changed line.\n\n"
            f"![Review evidence]({image_url})",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )
    if not resolved:
        result = CliRunner().invoke(
            cli_model.cli,
            [
                "task",
                "start",
                str(serve.page_dir),
                root["id"],
                "--text",
                "checking the shard",
            ],
        )
        assert result.exit_code == 0, result.output
    if resolved:
        append_carried_log_record(
            serve.page_dir,
            {"kind": "resolve", "author": "user", "parent": root["id"]},
        )
    selector = f'lf-diff .lf-page-thread[data-thread="{root["id"]}"]'
    live = open_page(browser, url)
    thread = live.locator(selector)
    expect(thread).to_have_count(1)
    expect(thread.locator("button")).not_to_have_count(0)
    if not resolved:
        inline_workflow = thread.locator(".lf-msg-sending")
        expect(inline_workflow).to_have_text("On it")
        # The same message in the panel's view of the thread says it the same way.
        panel_workflow = open_panel_thread(live, root["id"]).locator(".lf-msg-sending")
        expect(panel_workflow).to_have_text("On it")
        workflow_face = """node => {
          const style = getComputedStyle(node);
          const separator = getComputedStyle(node, '::before');
          return [style.color, style.fontWeight, style.whiteSpace,
            separator.content, separator.color];
        }"""
        assert inline_workflow.evaluate(workflow_face) == panel_workflow.evaluate(
            workflow_face
        )
    live.emulate_media(media="print")
    expect(thread.locator(".lf-msg-body")).to_be_visible()
    assert (
        thread.locator(
            "button:visible, leaf-text:visible, .lf-msg-sending:visible"
        ).count()
        == 0
    )


def test_an_export_runs_what_its_served_page_runs(browser, serve, tmp_path):
    """A page's scripts, a deferred classic file and a module, run the same in the
    served page and its export, so a library draws in both or neither: its code may
    compile at run time, start a blob: worker, and reach any server."""
    source = leaf_page(
        "One page",
        "<h1>One page</h1>",
        head='<script defer src="/page/classic.js"></script>\n'
        '<script type="module" src="/page/attempts.js"></script>',
    )
    version = serve(
        source,
        page_files={
            "classic.js": "window.classicRan = 'ran';\n",
            "attempts.js": POLICY_ATTEMPTS,
        },
    )
    out = tmp_path / "offline.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    expected = {
        "eval": "ran",
        "blob worker": "ran",
        "classic script": "ran",
        "remote image": "ran",
        "remote fetch": "data",
    }

    def outside(route):
        is_image = route.request.url.endswith(".png")
        route.fulfill(
            body=PIXEL if is_image else b"data",
            content_type="image/png" if is_image else "text/plain",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    for url in (live_url(version), out.as_uri()):
        context = browser.new_context(viewport={"width": 1200, "height": 900})
        context.route("https://outside.invalid/**", outside)
        page = open_page(browser, url, context=context)
        assert page.evaluate("() => window.policyOutcomes") == expected, url


def test_an_interactive_export_reseats_authored_margin_notes(browser, serve, tmp_path):
    """Offline reading shares the same initial and width-dependent composition."""
    serve(
        leaf_page(
            "Exported notes",
            '<h1 id="title">Migration</h1>'
            '<aside class="sidenote" id="note">Keep earlier readers available.</aside>'
            '<p id="passage">Advance the migration one cohort at a time.</p>',
        )
    )
    interactive = tmp_path / "margin-notes.html"
    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "export", str(serve.page_dir), "--out", str(interactive)],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(interactive.as_uri(), wait_until="load")
    expect(page.locator("body")).to_have_attribute(
        "data-lf-presented", "1", timeout=HANDOVER_DEADLINE_MS
    )
    expect(page.locator("#note")).to_have_css("float", "right")
    page.set_viewport_size({"width": 390, "height": 900})
    expect(page.locator("#note")).to_have_css("float", "none")
    page.set_viewport_size({"width": 1440, "height": 900})
    expect(page.locator("#note")).to_have_css("float", "right")
