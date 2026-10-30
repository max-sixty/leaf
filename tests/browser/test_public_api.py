"""Public package capabilities and check-only output observations cross the real loader."""

import json

import pytest
from interact_support import add_test_widget
from model_folds import leaf_page
from render_harness import open_page

from leaf.render_checks import (
    HANDOVER_DEADLINE_MS,
    RENDER_VIEWPORT,
    SERVED_TIMEOUT_MS,
    observe_output_documents,
    rendered,
    wait_until_ready,
)
from leaf.render_gate.scheme import _render_scheme
from leaf.render_gate.widget_quality import widget_findings
from leaf.revision_artifact import read_artifact


def test_package_imports_fail_at_the_browser_module_boundary(browser, serve):
    page = open_page(browser, serve(leaf_page("Public API", "<p>A package page.</p>")))
    problem = page.evaluate("""async () => {
      const module = new Blob([
        `import { setRuntimeRootStyle } from ${JSON.stringify(new URL('/runtime/widget-api.js', location.href).href)};`
      ], {type: 'text/javascript'});
      const url = URL.createObjectURL(module);
      try { await import(url); return null; }
      catch (error) { return {name: error.name, message: error.message}; }
      finally { URL.revokeObjectURL(url); }
    }""")
    assert problem["name"] == "SyntaxError"
    assert "setRuntimeRootStyle" in problem["message"]


def test_formatted_page_words_follow_rendered_blocks_and_whitespace(browser, serve):
    page = open_page(
        browser, serve(leaf_page("Formatted words", "<p>A package page.</p>"))
    )
    readings = page.evaluate("""async () => {
      const {says} = await import('/runtime/widget-api.js');
      return lfUnwatched(() => {
        const cases = {
          divs: '<div>Step one</div><div>Step two</div>',
          indented: '<div>Step one</div>\\n  <div>Step two</div>',
          pre: '<p>Apply:</p><pre>a: 1\\n  b: 2</pre>',
          preWrap: '<div style="white-space:pre-wrap">a: 1\\n  b: 2</div>',
          preLine: '<div style="white-space:pre-line">a:  1  \\n  b: 2</div>',
          table: '<table><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr></table>',
          list: '<ul><li>Outer<ul><li>Inner</li></ul></li><li>Next</li></ul>',
          inline: '<div>Use <span data-lf-gen="1" data-lf-said>cpu</span>.</div>',
          br: 'Line one<br>Line two',
          island: '<div>Intro <span data-lf-markdown-words><strong>bold</strong> tail</span> rest</div>',
          inlineDiv: '<div style="display:inline">Alpha</div><div style="display:inline">beta</div>',
          blockSpan: '<span style="display:block">Alpha</span><span style="display:block">beta</span>',
          ruby: '<p>Use <ruby>漢<rt>kan</rt></ruby> here.</p>',
          chrome: '<p>Apply <b>these settings</b><span class="lf-ui">1 comment</span>.</p>',
        };
        return Object.fromEntries(Object.entries(cases).map(([name, html]) => {
          const root = document.createElement('section');
          root.innerHTML = html;
          document.body.append(root);
          const lines = says(root, {format: 'lines'});
          root.querySelectorAll('.lf-ui').forEach(node => node.remove());
          const shown = root.innerText;
          root.remove();
          // Lines keeps boundaries, not the browser's extra paragraph spacing.
          const normalize = text => text.replace(/\\n{2,}/g, '\\n');
          return [name, {lines: normalize(lines), shown: normalize(shown)}];
        }));
      });
    }""")
    assert {name: value["lines"] for name, value in readings.items()} == {
        name: value["shown"] for name, value in readings.items()
    }


def test_independent_document_headers_contribute_measured_landing_room(browser, serve):
    page = open_page(browser, serve(leaf_page("Headers", "<p>A package page.</p>")))
    initial = page.evaluate("""async () => {
      const {landingInsets, registerRootHeader} = await window.__lfWidgetApi();
      const before = landingInsets(document.documentElement).top;
      const make = (id, height) => {
        const header = document.createElement('div');
        header.id = id;
        header.style.cssText = `position:fixed; height:${height}px`;
        document.querySelector('main').append(header);
        return header;
      };
      const first = make('package-header-one', 19);
      const second = make('package-header-two', 31);
      window.headerStops = [registerRootHeader(first), registerRootHeader(second)];
      return before;
    }""")

    def added():
        rendered(page)
        return (
            page.evaluate("""async () => {
          const {landingInsets} = await window.__lfWidgetApi();
          return landingInsets(document.documentElement).top;
        }""")
            - initial
        )

    assert added() == pytest.approx(50)
    page.locator("#package-header-one").evaluate("el => el.style.height = '43px'")
    assert added() == pytest.approx(74)
    page.locator("#package-header-two").evaluate(
        "el => {window.detachedHeader=el; el.remove()}"
    )
    assert added() == pytest.approx(43)
    page.evaluate("document.querySelector('main').append(window.detachedHeader)")
    assert added() == pytest.approx(74)
    page.evaluate("window.headerStops[0]()")
    assert added() == pytest.approx(31)
    page.evaluate("window.headerStops[1]()")
    assert added() == pytest.approx(0)


def output_package(path, value):
    tag = "lf-output-proof"
    add_test_widget(path, tag, upgrade=True)
    registry_path = path / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["$data"] = {
        "contracts": {
            "count": {
                "description": "A measured count.",
                "schema": {
                    "type": "object",
                    "properties": {"count": {"type": "integer"}},
                    "required": ["count"],
                    "additionalProperties": False,
                },
            }
        }
    }
    registry[tag]["x-output"] = {"count": {"contract": "count"}}
    registry[tag]["x-example"] = (
        '<lf-output-proof id="proof">Output example.</lf-output-proof>'
    )
    registry_path.write_text(json.dumps(registry))
    module = f"""import {{ LeafElement, html, publishOutput }} from "/runtime/widget-api.js";
customElements.define("lf-output-proof", class extends LeafElement {{
  setup() {{
    publishOutput(this, "count", {{count: 2}});
    publishOutput(this, "count", {json.dumps(value)});
    publishOutput(this, "count", null);
  }}
  render() {{ return html`Output example.`; }}
}});
"""
    (path / "widgets/lf-output-proof.js").write_text(module)
    return module


@pytest.mark.parametrize("value", [{"count": 3}, {"count": "wrong"}])
def test_package_render_checks_every_exercised_output_before_withdrawal(
    tmp_path, browser, value
):
    package = tmp_path / "output-package"
    output_package(package, value)
    failures = [
        f for f in widget_findings(browser.unwatched, package) if f.severity == "error"
    ]
    if isinstance(value["count"], int):
        assert failures == []
    else:
        assert failures
        assert all(f.code == "invalid-output" for f in failures)
        failure = failures[0]
        assert failure.at == "<lf-output-proof id=proof>"
        assert failure.values["owner"] == "package"
        assert failure.values["output"] == "count"
        assert failure.values["contract"] == "count"
        assert "$.count" in failure.values["error"]
        assert "<lf-output-proof id=proof> (package producer)" in str(failure)


def test_page_render_attributes_invalid_output_to_the_overriding_implementation(
    tmp_path, browser, serve
):
    package = tmp_path / "output-package"
    module = output_package(package, {"count": 2})
    url = serve(
        leaf_page(
            "Page output",
            '<lf-output-proof id="proof">Output example.</lf-output-proof>',
        ),
        packages=(package,),
        page_files={
            "widgets/lf-output-proof.js": module.replace(
                '{"count": 2}', '{"count": "wrong"}'
            )
        },
    )
    artifact = read_artifact(serve.page_dir, 1)
    pages = []
    findings, _, complete = _render_scheme(
        browser.unwatched,
        url,
        "light",
        RENDER_VIEWPORT,
        SERVED_TIMEOUT_MS,
        pages,
        implementations=artifact.implementations,
        declaration_sources=artifact.declaration_sources,
    )
    assert complete
    failures = [f for f in findings if f.code == "invalid-output"]
    assert len(failures) == 1
    assert failures[0].severity == "error"
    assert failures[0].values["owner"] == "page"
    assert failures[0].values["module"] == "/page/widgets/lf-output-proof.js"
    assert "$.count" in failures[0].values["error"]


def test_render_check_preserves_an_authored_classic_script_named_leaf(browser, serve):
    url = serve(
        leaf_page(
            "Authored script",
            "<p>A page with its own script.</p>",
            head='<script defer src="/page/leaf.js"></script>',
        ),
        page_files={"leaf.js": "window.authoredScriptRan = true;"},
    )
    pages = []

    def read_script(page, registry):
        assert page.evaluate("window.authoredScriptRan") is True

    findings, _, complete = _render_scheme(
        browser.unwatched,
        url,
        "light",
        RENDER_VIEWPORT,
        SERVED_TIMEOUT_MS,
        pages,
        then=read_script,
    )
    assert complete
    assert not [f for f in findings if f.severity == "error"]


@pytest.mark.parametrize("reader", ["page", "widgets"])
def test_closing_an_output_observer_during_its_body_read_keeps_the_browser_usable(
    browser, serve, monkeypatch, reader
):
    """A context disposes fetched responses before its page reports itself closed."""
    import asyncio
    import time

    from playwright._impl._fetch import APIRequestContext, APIResponse
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    from leaf.render_gate import scheme, widget_quality

    pages = []
    body, dispose = APIResponse.body, APIRequestContext.dispose
    reading, released, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
    readings = []

    async def held_body(response):
        reading.set()
        await asyncio.wait_for(released.wait(), SERVED_TIMEOUT_MS / 1000)
        readings.append(pages[0].is_closed())
        try:
            return await body(response)
        finally:
            finished.set()

    async def disposed(context, **kwargs):
        await dispose(context, **kwargs)
        # Hold context closure at its real disposal boundary: the page has not
        # closed yet, but the observer's API response is already unavailable.
        released.set()
        await asyncio.wait_for(finished.wait(), SERVED_TIMEOUT_MS / 1000)

    def abandoned_check(page):
        pages.append(page)
        observe_output_documents(page)
        page.goto(url, wait_until="commit")
        deadline = time.monotonic() + SERVED_TIMEOUT_MS / 1000
        while not reading.is_set():
            assert time.monotonic() < deadline, "the observer never read its entry body"
            page.evaluate("1")
        raise PlaywrightTimeout("the check was abandoned during output capture")

    url = serve(leaf_page("closing observer", "<h1>Closing</h1>"), packages=())
    with monkeypatch.context() as patch:
        patch.setattr(APIResponse, "body", held_body)
        patch.setattr(APIRequestContext, "dispose", disposed)
        owner = scheme if reader == "page" else widget_quality
        patch.setattr(owner, "observe_output_documents", abandoned_check)
        if reader == "page":
            _findings, _notices, complete = _render_scheme(
                browser.unwatched, url, "light", RENDER_VIEWPORT, SERVED_TIMEOUT_MS, []
            )
            assert not complete
        else:
            with pytest.raises(widget_quality.UnreadablePage):
                widget_quality._readings(browser.unwatched, url, [])
        next_page = browser.unwatched.new_page()
        assert next_page.evaluate("1 + 1") == 2
        assert readings == [False]


def test_output_capture_fetch_failure_reaches_the_browsers_network_boundary(
    browser, serve, monkeypatch
):
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import Route

    url = serve(leaf_page("Interrupted entry", "<p>A page.</p>"))
    attempted, failed = [], []

    def unavailable(route, **options):
        attempted.append(route.request.url)
        raise PlaywrightError("The entry server stopped answering")

    monkeypatch.setattr(Route, "fetch", unavailable)
    page = browser.unwatched.new_page()
    page.on("requestfailed", lambda request: failed.append(request.url))
    observe_output_documents(page)
    # Aborting ends the browser request, so load completes instead of hanging
    # until the handover deadline behind an unfulfilled interception.
    page.goto(url, wait_until="load", timeout=HANDOVER_DEADLINE_MS)
    assert attempted
    assert set(attempted) <= set(failed)


@pytest.mark.parametrize("ending", ["removed", "navigated"])
def test_render_check_keeps_departed_samples_invalid_outputs(
    tmp_path, browser, serve, ending
):
    package = tmp_path / "sample-output-package"
    output_package(package, {"count": "wrong"})
    url = serve(
        leaf_page(
            "Sample output",
            "<h1>Example producers</h1>"
            + "".join(
                f"""<lf-sample id="example-{n}" label="producer example {n}">
  <template id="example-page-{n}" data-sample>
    <lf-output-proof id="proof">Output example.</lf-output-proof>
  </template>
</lf-sample>"""
                for n in range(3)
            ),
        ),
        packages=(package,),
    )
    artifact = read_artifact(serve.page_dir, 1)
    pages = []

    def leave_samples(page, registry):
        assert len(page.frames) == 4
        if ending == "removed":
            page.locator("lf-sample").evaluate_all(
                "els => els.forEach(el => el.remove())"
            )
        else:
            for frame in page.frames[1:]:
                frame.goto("about:blank")

    findings, _, complete = _render_scheme(
        browser.unwatched,
        url,
        "light",
        RENDER_VIEWPORT,
        SERVED_TIMEOUT_MS,
        pages,
        then=leave_samples,
        implementations=artifact.implementations,
        declaration_sources=artifact.declaration_sources,
    )
    assert complete
    failures = [f for f in findings if f.code == "invalid-output"]
    assert len(failures) == 3
    for failure in failures:
        assert failure.values["owner"] == "package"
        assert "/api/samples/" in failure.values["document"]
        assert "$.count" in failure.values["error"]


@pytest.mark.parametrize("override", ["output", "contract"])
def test_page_output_declaration_keeps_its_owner_beside_the_package_implementation(
    tmp_path, browser, serve, override
):
    package = tmp_path / "output-package"
    output_package(package, {"count": 2})
    registry = json.loads((package / "registry.json").read_text())
    contract = "small-count" if override == "output" else "count"
    registry["$data"]["contracts"][contract] = {
        "description": "The page accepts only small counts.",
        "schema": {
            "type": "object",
            "properties": {"count": {"type": "integer", "maximum": 1}},
        },
    }
    registry["lf-output-proof"]["x-output"]["count"]["contract"] = contract
    if override == "contract":
        registry = {"$data": registry["$data"]}
    url = serve(
        leaf_page(
            "Page output contract",
            '<lf-output-proof id="proof">Output example.</lf-output-proof>',
        ),
        packages=(package,),
        page_files={"registry.json": json.dumps(registry)},
    )
    artifact = read_artifact(serve.page_dir, 1)
    pages = []
    findings, _, complete = _render_scheme(
        browser.unwatched,
        url,
        "light",
        RENDER_VIEWPORT,
        SERVED_TIMEOUT_MS,
        pages,
        implementations=artifact.implementations,
        declaration_sources=artifact.declaration_sources,
    )
    assert complete
    failures = [f for f in findings if f.code == "invalid-output"]
    assert len(failures) == 1
    assert failures[0].values["owner"] == "package"
    assert failures[0].values["declaration_owner"] == (
        "page" if override == "output" else "package"
    )
    assert failures[0].values["contract_owner"] == "page"
    assert failures[0].values["module"] == "/widgets/lf-output-proof.js"
    assert "package implementation" in str(failures[0])
    assert "page contract" in str(failures[0])


def test_a_widget_s_pending_task_holds_the_page_until_its_drawing_is_in(
    tmp_path, browser, serve
):
    """A widget that draws without Leaf's helpers says it has drawing under way with a
    `pending-task` event, as one that also runs off Leaf does (module-authoring.md, "A
    widget that also runs off Leaf"). The page holds the widget's presentation on it, as
    on `present(promise)`, and presents once the drawing is in."""
    package = tmp_path / "pending-package"
    tag = "lf-pending-proof"
    add_test_widget(package, tag, upgrade=True)
    (package / "widgets" / f"{tag}.js").write_text(
        'import { PendingTaskEvent, once } from "/runtime/portable-api.js";\n'
        f'customElements.define("{tag}", class extends HTMLElement {{\n'
        "  connectedCallback() {\n"
        "    if (!once(this)) return;\n"
        "    const held = Promise.withResolvers();\n"
        "    window.releaseDrawing = held.resolve;\n"
        "    const drawing = held.promise.then(() => { this.textContent = 'Drawn.'; });\n"
        "    this.dispatchEvent(new PendingTaskEvent(drawing));\n"
        "  }\n"
        "});\n"
    )
    url = serve(
        leaf_page("Pending", f'<{tag} id="proof">Drawing.</{tag}>'),
        packages=(package,),
    )
    page = browser.new_page()
    page.goto(url)
    page.wait_for_function("() => typeof window.releaseDrawing === 'function'")
    pending = """async () => (await window.__lfCheckApi())
        .readApplicationPresentation().pending.includes('widget:proof:preparation')"""
    assert page.evaluate(pending), "the page must hold the widget's drawing"
    page.evaluate("releaseDrawing()")
    wait_until_ready(page)
    assert page.locator("#proof").text_content() == "Drawn."
    assert not page.evaluate(pending)
