"""Preview and offline export tests."""

import hashlib
import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner
from interact_support import (
    ROOT,
    append_carried_log_record,
)
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATION_PAGE, live_url
from render_cases_layout import solid_png
from render_cases_navigation import (
    source_revision,
)
from render_harness import (
    example_media,
    leaf_page,
    open_page,
    round_trip,
    scroll_settled,
    sending,
    write,
)

from browser.threads import open_panel_thread
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import exporting as exporting_model
from leaf import files as files_model
from leaf import media as media_model
from leaf.render_checks import HANDOVER_DEADLINE_MS, rendered, wait_until_ready
from leaf.structure import UTF8_BOM
from leaf_dev.example_data import named_source, patch_manifest

pytestmark = pytest.mark.shifts_unsurveyed

from journeys.test_render_export import (  # noqa: F401 (fixtures)
    OFFLINE_REGISTRY,
    OFFLINE_WIDGET,
    PIXEL,
    POLICY_ATTEMPTS,
    _reachable,
    requested_documents,
)


@pytest.mark.parametrize("draft", [False, True], ids=["stamped", "draft"])
def test_interactive_export_with_an_obligation_reaches_application_presentation(
    browser, serve, tmp_path, draft
):
    """Offline mode omits page controls without leaving their ticket pending."""
    serve(named_source("notification-playground"))
    interactive = tmp_path / "interactive-with-ask.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "export",
            str(serve.page_dir),
            "--out",
            str(interactive),
            *(["--draft"] if draft else []),
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
    expect(field).to_have_attribute("placeholder", "Add another option…")
    expect(add).to_have_attribute("aria-disabled", "true")
    expect(add).to_have_attribute("data-lf-empty", "")
    expect(add).to_be_hidden()
    field.click()
    expect(field).to_have_attribute("placeholder", "Add another option… ⏎")
    write(field, "Portrait sketch")
    expect(add).not_to_have_attribute("data-lf-empty", "")


def test_exported_workspace_tabs_open_new_evidence_below_the_pinned_strip(
    browser, serve, tmp_path
):
    """Exports register the Layout's scrollport, so nested navigation lands in it."""
    paragraphs = "".join(f"<p>Evidence paragraph {i}.</p>" for i in range(24))
    source = leaf_page(
        "Evidence review",
        f"""<header><h1>Evidence review</h1></header>
<lf-tabs id="views">
  <lf-tab id="intro" label="Introduction"><p>Open the review.</p></lf-tab>
  <lf-tab id="review" label="Review"><lf-tabs id="evidence">
    <lf-tab id="first" label="First"><h2>First evidence</h2>{paragraphs}</lf-tab>
    <lf-tab id="second" label="Second"><h2>Second evidence</h2>{paragraphs}</lf-tab>
  </lf-tabs></lf-tab>
</lf-tabs>""",
        head="<style>#views > lf-tab {padding-block-start:0}</style>",
        layout="workspace",
    )
    serve(source)
    out = tmp_path / "evidence-review.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    page = browser.new_page(viewport={"width": 900, "height": 600})
    page.goto(out.as_uri(), wait_until="load")
    wait_until_ready(page)
    page.get_by_role("tab", name="Review", exact=True).click()
    page.locator("#first p").nth(3).hover()
    page.mouse.wheel(0, 150)
    page.wait_for_function("document.querySelector('#views').scrollTop > 100")
    scroll_settled(page, "#views")
    # A sticky tab's visible box is the input target, rather than its flow position.
    button = page.get_by_role("tab", name="Second", exact=True).bounding_box()
    page.mouse.click(
        button["x"] + button["width"] / 2, button["y"] + button["height"] / 2
    )
    rendered(page)
    heading = page.locator("#second h2").bounding_box()
    strip = page.locator("#evidence > .lf-tabstrip").bounding_box()
    assert heading["y"] >= strip["y"] + strip["height"] - 1
    assert heading["y"] + heading["height"] < 600
    # Leaving and reopening the outer view keeps the nested selection readable too.
    page.get_by_role("tab", name="Introduction", exact=True).click()
    page.get_by_role("tab", name="Review", exact=True).click()
    expect(page.get_by_role("tab", name="Second", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.locator("#second h2")).to_be_in_viewport()


def test_interactive_export_runs_captured_local_behavior_without_a_host(
    browser, serve, tmp_path
):
    """One file boots the captured runtime, but never resurrects its host boundary.

    The file keeps the choice recorded on the page's widget and leaves out the thread on
    another, whose seat offers no box to start one in."""
    source = leaf_page(
        "offline interactive",
        """
<h1>Offline interactive</h1>
<lf-offline-test id="offline-widget" choice="idle"></lf-offline-test>
<lf-test-plan id="hub"><lf-test-task id="seated" status="active" talk>Discuss this.</lf-test-task></lf-test-plan>
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
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "A remark the export leaves behind",
            "anchor": {"section": "seated"},
        },
    )
    expect(live.locator("#seated .lf-msg")).to_contain_text(
        "A remark the export leaves behind"
    )
    expect(live.locator("#seated > .lf-thread-seat")).to_have_count(1)
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
    expect(page.locator("#seated")).to_contain_text("Discuss this.")
    expect(page.locator("#seated .lf-msg")).to_have_count(0)
    expect(page.locator("#seated > .lf-thread-seat")).to_have_count(0)
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


def test_an_interactive_export_reads_each_source_offline(browser, serve, tmp_path):
    """Each source reaches the widget bound to it, an unopened tab's and an unopened
    diff file's too, from one file with no host."""
    serve(
        leaf_page(
            "offline data",
            """<h1>Review</h1>
<lf-tabs id="notes" list="side">
  <lf-tab id="first" label="First"><lf-text-document id="one" source="notes-one" label="one.md"></lf-text-document></lf-tab>
  <lf-tab id="second" label="Second"><lf-text-document id="two" source="notes-two" label="two.md"></lf-text-document></lf-tab>
</lf-tabs>
<lf-diff id="patch" source="review-patch" collapsed></lf-diff>""",
        )
    )
    # Text a layer of escaping would mangle: a script end, quotes, a backslash, a
    # line break and characters outside ASCII.
    texts = {
        "notes-one": 'First </script> "quoted" \\ back\nnext line é\n',
        "notes-two": "Second, in the unopened tab ✓\n",
    }
    for source, text in texts.items():
        data_model.cmd_data_set(serve.page_dir, source, text)
    patch = "".join(
        f"diff --git a/{name} b/{name}\n--- a/{name}\n+++ b/{name}\n"
        f'@@ -1 +1 @@\n-return "old"\n+return "{name} new"\n'
        for name in ("app.py", "lib.py")
    )
    data_model.cmd_data_set(serve.page_dir, "review-patch", patch_manifest(patch))
    interactive = tmp_path / "data-interactive.html"
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
    expect(page.locator("#second")).to_have_attribute("hidden", "until-found")
    for widget, source in (("#one", "notes-one"), ("#two", "notes-two")):
        assert page.locator(widget).evaluate("widget => widget.value") == texts[source]
        expect(page.locator(f"{widget} code")).to_have_text(texts[source])
    for name in ("app.py", "lib.py"):
        page.locator("lf-diff summary", has_text=name).click()
        expect(
            page.locator(f'lf-diff [data-lf-datum=\'["{name}","new",1]\']')
        ).to_contain_text(f"{name} new")
    assert external == []


def test_an_export_keeps_data_owned_trace_images_and_the_shot_slider_offline(
    browser, serve, tmp_path
):
    """Images a data source owns, one trace view's included, travel with the offline
    export, an authored `lf-shot`'s slider still answers keys there, and nothing is
    requested outside the file."""
    record = json.loads(
        (ROOT / "examples/developer/playwright-trace-gallery.data.json").read_text()
    )["release-journey"]
    media = {
        image["url"]: (example_media() / Path(image["url"]).name).read_bytes()
        for image in record["images"]
    }
    captures = [
        solid_png(320, 200, color) for color in ((232, 226, 213), (214, 226, 235))
    ]
    before, after = (
        f"/media/{hashlib.sha256(image).hexdigest()[:16]}.png" for image in captures
    )
    media.update(zip((before, after), captures, strict=True))
    serve(
        leaf_page(
            "Offline evidence",
            '<lf-trace id="trace" source="trace"></lf-trace>'
            f'<lf-shot id="pair" alt="pair" before="{before}" after="{after}"></lf-shot>',
        ),
        packages=("playwright",),
        media=media,
    )
    data_model.cmd_data_set(serve.page_dir, "trace", record)
    out = tmp_path / "evidence.html"
    exporting_model.cmd_export(serve.page_dir, out, None)
    context = browser.new_context(offline=True, viewport={"width": 1200, "height": 900})
    page = context.new_page()
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    page.goto(out.as_uri(), wait_until="load")
    wait_until_ready(page)
    trace = page.locator("#trace")
    image = trace.locator(".viewer-canvas img")
    expect(image).to_have_js_property("complete", True)
    first = image.get_attribute("data-lf-datum")
    assert image.evaluate("node => node.decode().then(() => node.naturalWidth)") > 0
    # A later checkpoint draws a different capture, which decodes offline as well.
    timeline = trace.get_by_role("group", name="Recording timeline", exact=True)
    timeline.focus()
    timeline.press("End")
    expect(image).not_to_have_attribute("data-lf-datum", first)
    expect(image).to_have_js_property("complete", True)
    assert image.evaluate("node => node.decode().then(() => node.naturalWidth)") > 0
    shot = page.locator("#pair")
    shot.get_by_role("radio", name="Slider", exact=True).click()
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
    imports = page.evaluate("""() => JSON.parse(
        document.querySelector('script[type="importmap"]').textContent
    ).imports""")
    assert imports
    assert all(url.startswith("blob:") for url in imports.values())
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


def test_an_export_draws_the_widgets_its_markup_names_and_brings_no_others(
    browser, serve, tmp_path, subtests
):
    """One exported file, read for what its widgets need offline.

    An lf-chart body is a Plot expression the widget compiles, so the export's policy
    admits compiling it as the served page's does. Refused, the chart shows an error
    over its source in the file a user was sent, while it drew in the author's preview.

    A word written for a user listening (`.lf-quiet`), here a highlighted code line's,
    is clipped on screen in an export as in the live page. The rule that clips it once
    lived only in the chrome's sheet, which an export never adopts, so quiet words in an
    exported file appeared on screen as well as their tint.

    A widget the page never names brings none of its modules. The page draws code and a
    chart, and only a reply, which the file leaves out, carries a diagram. Nothing names
    a diff, so Pierre's renderer is out of the file too.
    """
    serve(
        leaf_page(
            "Reachable modules",
            '<h1>Reachable</h1><lf-chart id="c"><pre>'
            '{ariaLabel: "one bar of 3", marks: [Plot.barY([3])]}'
            '</pre></lf-chart><lf-code id="m" language="python" hi="1">'
            "<pre>ship()</pre></lf-code>",
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
    match = re.search(
        r'<script type="application/json" data-lf-export>(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None
    composed = json.loads(match[1])["document"]
    match_2 = re.search(
        r'<script type="importmap"[^>]*>(.*?)</script>', composed, re.DOTALL
    )
    assert match_2 is not None
    imports = json.loads(match_2[1])["imports"]
    assert "leaf:/widgets/lf-code.js" in imports
    assert not {
        "leaf:/widgets/lf-diagram.js",
        "leaf:/widgets/lf-diff.js",
        "leaf:/vendor/pierre-diffs.esm.js",
    } & set(imports)

    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    with subtests.test("chart"):
        expect(page.locator("#c svg[role=img]")).to_have_attribute(
            "aria-label", "one bar of 3"
        )
        expect(page.locator("#c .lf-error")).to_have_count(0)
    with subtests.test("quiet words"):
        expect(page.locator("#m")).to_contain_text("ship")
        quiet = page.locator("#m .lf-quiet")
        expect(quiet).to_have_count(1)
        box = quiet.evaluate(
            "el => { const r = el.getBoundingClientRect();"
            " return [r.width, r.height, getComputedStyle(el).clipPath]; }"
        )
        assert box[0] <= 1 and box[1] <= 1 and box[2] != "none", box


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
            '<h1>Review</h1><lf-diff id="patch" source="review-patch"></lf-diff>',
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
    selector = f'lf-diff .lf-page-thread[data-lf-thread="{root["id"]}"]'
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
            '<div class="layout-note"><p id="passage">Advance the migration one cohort at a time.</p>'
            '<aside class="note" id="note">Keep earlier readers available.</aside></div>',
        ).replace(
            '<main class="layout-column">', '<main class="layout-column layout-notes">'
        )
    )
    interactive = tmp_path / "margin-notes.html"
    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "export", str(serve.page_dir), "--out", str(interactive)],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output
    page = browser.new_page(viewport={"width": 1600, "height": 900})
    page.goto(interactive.as_uri(), wait_until="load")
    expect(page.locator("body")).to_have_attribute(
        "data-lf-presented", "1", timeout=HANDOVER_DEADLINE_MS
    )
    wide = page.locator("#note").bounding_box()
    prose = page.locator("#passage").bounding_box()
    assert wide["x"] >= prose["x"] + prose["width"]
    page.set_viewport_size({"width": 390, "height": 900})
    narrow = page.locator("#note").bounding_box()
    prose = page.locator("#passage").bounding_box()
    assert narrow["y"] >= prose["y"] + prose["height"]
    page.set_viewport_size({"width": 1600, "height": 900})
    assert page.locator("#note").bounding_box() == pytest.approx(wide)


def test_an_export_s_preview_takes_escape_before_the_dialog_around_it(
    browser, serve, tmp_path
):
    """Offline the register admits no page scope, so the preview takes Escape itself.
    A pointer's preview over a control in a modal dialog goes on the first Escape and
    the dialog stays open, as on a live page; the next Escape closes the dialog.
    Before, one Escape closed both."""
    serve(leaf_page("Dialog", "<h1>Dialog</h1><p>Words beside it.</p>"))
    exported = tmp_path / "dialog.html"
    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "export", str(serve.page_dir), "--out", str(exported)],
        env={"LEAF_BROWSER_EXECUTABLE": str(tmp_path / "missing-browser")},
    )
    assert result.exit_code == 0, result.output
    page = browser.new_page()
    page.goto(exported.as_uri(), wait_until="load")
    expect(page.locator("body")).to_have_attribute(
        "data-lf-presented", "1", timeout=HANDOVER_DEADLINE_MS
    )
    page.evaluate(
        """() => {
          const dialog = document.createElement('dialog');
          dialog.id = 'dialog';
          dialog.innerHTML = '<button id="open" aria-label="Read report">?</button>';
          document.querySelector('main').append(dialog);
          dialog.querySelector('button').lfPreview = () => ({name: 'Read report',
            detail: ['Offline reading.']});
          dialog.showModal();
        }"""
    )
    dialog = page.locator("#dialog")
    tip = page.locator("#lf-preview")
    page.locator("#open").hover()
    expect(tip.locator(".lf-preview-word")).to_have_text("Read report")
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    expect(dialog).to_have_attribute("open", "")
    page.keyboard.press("Escape")
    expect(dialog).not_to_have_attribute("open", "")
