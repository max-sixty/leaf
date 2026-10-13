"""Preview and offline export tests."""

import json
import re
from contextlib import ExitStack

import pytest
from click.testing import CliRunner
from interact_support import (
    COMPOSITE_TIMEOUT,
    append_carried_log_record,
    wait_for,
)
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import exporting as exporting_model
from leaf import files as files_model
from leaf import media as media_model
from leaf import server as server_model
from leaf import state as cleanup_model
from leaf.render_checks import HANDOVER_DEADLINE_MS, wait_until_ready
from leaf.structure import UTF8_BOM
from leaf_dev.example_data import patch_manifest
from playwright.sync_api import expect
from render_cases_interaction import ASK_PAGE, live_url
from render_cases_navigation import (
    source_revision,
)
from render_harness import (
    is_problem,
    leaf_page,
    open_page,
    restarting,
    round_trip,
    sending,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed

from journeys.test_render_export import (  # noqa: F401 (fixtures)
    OFFLINE_REGISTRY,
    OFFLINE_WIDGET,
    PIXEL,
    POLICY_ATTEMPTS,
    ROOT,
    _reachable,
    preview_slot_fixture,
    requested_documents,
    served_preview_fixture,
    watched_preview_fixture,
)


def test_preview_watches_source_without_losing_user_state(browser, watched_preview):
    """The open tab follows source edits; rejected source never replaces its last good
    page. A runtime edit's restart is `test_every_tab_follows_a_runtime_edit`'s."""
    source, _, directory, _, url, log = watched_preview
    original = source.read_text(encoding="utf-8")
    page = open_page(browser, url)
    with sending(page, "the watched user option pick"):
        page.locator("#opt-shim .lf-pick").click()
    expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    feedback = (directory / "events.jsonl").read_bytes()
    assert b'"kind": "action"' in feedback
    inode = (directory / "events.jsonl").stat().st_ino

    # A source edit leaves the server up, so it is not a restart span: the tab takes
    # the new revision in place, and anything it complains about is a fault.
    revised = original.replace("Rollout", "A watched source revision", 1)
    source.write_text(revised, encoding="utf-8")
    expect(page.get_by_role("heading", name="A watched source revision")).to_be_visible(
        timeout=HANDOVER_DEADLINE_MS
    )
    expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)

    source.write_text("<p>invalid source</p>", encoding="utf-8")
    wait_for(
        log.read_text,
        lambda output: "Preview update refused" in output,
        failure="the invalid preview update was not refused",
    )
    expect(
        page.get_by_role("heading", name="A watched source revision")
    ).to_be_visible()
    assert (directory / "index.html").read_text() == revised
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)

    source.write_text(
        revised.replace("A watched source revision", "Recovered watched source"),
        encoding="utf-8",
    )
    expect(page.get_by_role("heading", name="Recovered watched source")).to_be_visible(
        timeout=HANDOVER_DEADLINE_MS
    )
    expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)
    assert (directory / "events.jsonl").stat().st_ino == inode


def test_every_tab_follows_a_runtime_edit(browser, watched_preview):
    """A runtime edit replaces the server, and every tab of the page follows it.

    An open tab takes the new layer with the user's state and log intact. A tab whose
    start failed hears the replacement too: supervision precedes entry, dependency,
    registry and stylesheet loading. Each fault is a different detector in the
    prepaint, so each gets its own tab, and one restart serves them all, since a
    restart at the recorded port waits out TCP cooldown.
    """
    _, runtime, directory, _, url, _ = watched_preview
    standing = open_page(browser, url)
    with sending(standing, "the standing user option pick"):
        standing.locator("#opt-shim .lf-pick").click()
    expect(standing.locator("#opt-shim")).to_have_attribute("chosen", "")
    feedback = (directory / "events.jsonl").read_bytes()
    inode = (directory / "events.jsonl").stat().st_ino
    generation = json.loads((directory / "registry.json").read_text())["$layer"][
        "generation"
    ]
    resources = (
        "leaf.js",
        "runtime/context.js",
        "widgets/lf-options.js",
        "registry.json",
        "theme.css",
        "syntax",
    )
    pages = {}
    # The interruption and the replacement server between them are a restart, and
    # what the browser says inside one is the fetch that was in flight rather than
    # the condition: a refused resource, a connection to a server that has gone, a
    # decoding that stopped halfway. The span is bracketed rather than the wordings
    # listed (tests/AGENTS.md, "Test-made noise").
    with ExitStack() as restarts:
        restarts.enter_context(restarting(standing))
        for resource in resources:
            page = browser.new_page()
            failures = []
            documents = requested_documents(page)

            def interrupt_resource(route, resource=resource, failures=failures):
                if failures:
                    route.continue_()
                    return
                failures.append(True)
                if resource == "syntax":
                    route.fulfill(
                        content_type="text/javascript", body="const = broken;"
                    )
                else:
                    route.abort()

            page.route(
                "**/" + ("leaf.js" if resource == "syntax" else resource),
                interrupt_resource,
            )
            restarts.enter_context(restarting(page))
            page.goto(url, wait_until="load")
            status = page.get_by_text(
                "Leaf couldn't start. Waiting for the server to update."
            )
            expect(status).to_be_visible()
            # Hearing the same server does not loop on a persistent syntax/startup
            # fault.
            with page.expect_response("**/registry.json") as response:
                pass
            assert response.value.ok
            assert len(documents) == 1, resource
            expect(status).to_be_visible()
            pages[resource] = (page, status, documents)
        # A changed layer replaces the server. An invalid input is now refused
        # before that replacement, so change a valid theme to test recovery.
        theme = runtime / "skills" / "leaf" / "assets" / "theme.css"
        with theme.open("a", encoding="utf-8") as stream:
            stream.write("\nh1 { color: navy; }\n")
        expect(standing.locator("h1")).to_have_css(
            "color", "rgb(0, 0, 128)", timeout=HANDOVER_DEADLINE_MS
        )
        for page, status, _ in pages.values():
            expect(page.locator("body")).to_have_attribute(
                "data-lf-presented", "1", timeout=HANDOVER_DEADLINE_MS
            )
            # Re-vendoring the full layer can outlast the default browser wait.
            expect(status).not_to_be_visible(timeout=HANDOVER_DEADLINE_MS)
    for resource, (page, _, documents) in pages.items():
        assert len(documents) >= 2, resource
        expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    expect(standing.locator("#opt-shim")).to_have_attribute("chosen", "")
    assert (directory / "events.jsonl").read_bytes().startswith(feedback)
    assert (directory / "events.jsonl").stat().st_ino == inode
    assert (
        json.loads((directory / "registry.json").read_text())["$layer"]["generation"]
        != generation
    )


def test_a_service_that_goes_away_mid_start_says_only_that_and_comes_back(
    browser, served_preview
):
    """A start the restart interrupts reports the vanished server and comes back.

    The other tests here reach this condition only when the machine is loaded enough to
    lose the race, so the ordering is arranged here rather than waited for. The
    interrupted fetch is the registry's; a widget's dynamic import reaches the same
    supervision with the module's name in its words.

    The restart is the preview's own, set off by a runtime edit. Holding the page
    transaction pauses it after it has stopped the service, so the service stays gone
    until the page has said so, and then comes back at the address the tab already
    has.
    """
    _, runtime, directory, _, url, _ = served_preview
    page = browser.new_page()
    errors = page.lf_errors
    paused = ExitStack()
    stopped = []

    def stop_the_service(route):
        # The registry is the runtime's own fetch, so a service stopped before it is
        # answered is a service that goes away between the document arriving and the
        # start that document began — the transport has nothing left to name it by.
        # Once only: the reload the recovery makes must find a server that answers.
        if not stopped:
            stopped.append(True)
            paused.enter_context(cleanup_model.flocked(directory / "events.jsonl"))
            theme = runtime / "skills" / "leaf" / "assets" / "theme.css"
            with theme.open("a", encoding="utf-8") as stream:
                stream.write("\nh1 { color: navy; }\n")
            # The record says the service is stopping before its socket closes, so
            # the address is what says the start's fetch will find nothing.
            wait_for(
                lambda: _reachable(url),
                lambda reachable: not reachable,
                failure="the runtime edit did not stop the service",
            )
        route.continue_()

    page.route("**/registry.json", stop_the_service)
    with paused, restarting(page):
        page.goto(url, wait_until="load")
        # `load` is not the boundary: a widget is imported after it, so the stop is
        # waited for through the answer the page gives it rather than read straight
        # after the goto.
        expect(
            page.get_by_text("Leaf couldn't start. Waiting for the server to update.")
        ).to_be_visible()
        # The reach: an interrupted start is a fetch the runtime made itself, which no
        # transport error names, and the words are the interrupted fetch's own.
        vanished = "leaf: page failed to start: Failed to fetch"
        assert [error for error in errors if is_problem(error, vanished)], errors
        paused.close()
        # The page's own recovery is bounded; the re-vendor ahead of it is not.
        wait_for(
            lambda: server_model.running_server(directory),
            bool,
            failure="the preview did not bring its service back",
            timeout=COMPOSITE_TIMEOUT,
        )


def test_interactive_export_with_an_ask_reaches_application_presentation(
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
    expect(page.locator("#lf-banner, .lf-thread-panel, .lf-queue-panel")).to_have_count(
        0
    )


def test_an_interactive_export_paints_a_widget_owned_text_box(browser, serve, tmp_path):
    """A text box paints in the standing paint, which an export mounts without page controls.

    A choosable group builds its addition field offline too. Its placeholder, disabled
    Add and empty-field flag are that paint's; focus alone repaints the placeholder with
    its send key, and typing repaints the flag."""
    serve(ASK_PAGE)
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

    # Export resolves the stamped artifact, never the mutable aliases left in the page
    # directory after activation.
    (serve.page_dir / "widgets" / "lf-offline-test.js").write_text(
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
            if request.url != document_url and not request.url.startswith("data:")
            else None
        ),
    )
    page.goto(document_url, wait_until="load")
    expect(page.locator("body")).to_have_attribute("data-lf-presented", "1")
    expect(page.locator("#offline-widget #choice")).to_have_text("chosen")
    expect(page.locator(".lf-chrome > #lf-media-viewer:not([open])")).to_have_count(1)
    expect(page.locator("#lf-banner, .lf-thread-panel, .lf-queue-panel")).to_have_count(
        0
    )
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
            if request.url != document_url and not request.url.startswith("data:")
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
    assert (serve.page_dir / "vendor" / "pierre-diffs.esm.js").is_file()
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
                serve.page_dir / "theme.css",
                b":root { --mutable-theme-only: 1; }",
                False,
            ),
            (
                serve.page_dir / "runtime/chrome.css",
                b":root { --mutable-chrome-only: 1; }",
                False,
            ),
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
    exported = out.read_text(encoding="utf-8")
    assert "--mutable-theme-only" not in exported
    assert "--mutable-chrome-only" not in exported
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
    _, image_url = media_model.cmd_media(serve.page_dir, [image])[0]
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
            ["task", "start", str(serve.page_dir), root["id"], "checking the shard"],
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
        expect(inline_workflow).to_have_text("Working")
        live.keyboard.press("c")
        panel_workflow = live.locator(
            f'.lf-chrome .lf-thread[data-id="{root["id"]}"] .lf-msg-sending'
        )
        expect(panel_workflow).to_have_text("Working")
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
