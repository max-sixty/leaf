"""Published documents and modules retain their complete captured revision."""

import json
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from interact_support import append_carried_log_record as append_event
from leaf.files import revision_path
from leaf.hosting import TemporaryPageServer
from leaf.live_shell import write_live_shell
from leaf.revision_artifact import RESOURCE_TYPES
from leaf.revisioning import activate_source
from playwright.sync_api import expect
from render_harness import leaf_page, open_page


@pytest.mark.parametrize("bundled", [False, True])
def test_a_browser_executes_the_published_capture_with_live_api_routes(
    page_dir, tmp_path, browser, bundled
):
    authored = page_dir / "page"
    (authored / "nested").mkdir(parents=True)
    (authored / "widgets").mkdir()
    (authored / "widgets" / "lf-options.js").write_text(
        "window.widgetLoads = (window.widgetLoads || 0) + 1; "
        "export const moduleUrl = import.meta.url; "
        'export const prose = "import.meta.url"; '
        'customElements.define("lf-options", class extends HTMLElement {});'
    )
    (authored / "app.js").write_text(
        'import { value } from "./nested/value.js"; '
        'import { moduleUrl, prose } from "./widgets/lf-options.js"; '
        "const say = (id, text) => { const out = document.getElementById(id); "
        "if (out.textContent !== text) out.textContent = text; }; "
        'document.querySelector("#read").addEventListener("click", () => { '
        'say("result", value); '
        'say("module", `${window.widgetLoads}: ${prose}: ${moduleUrl}`); });'
    )
    (authored / "nested" / "value.js").write_text('export const value = "Captured";')
    (authored / "style.css").write_text('@import "./nested/theme.css";')
    (authored / "nested" / "theme.css").write_text("#result { color: rgb(1, 2, 3); }")
    source = leaf_page(
        "Published module",
        '<section id="study"><h1>Published module</h1>'
        '<button id="read" type="button">Read captured value</button>'
        '<output id="result">Waiting</output><output id="module">Waiting</output>'
        '<lf-options><lf-option id="only">Only choice</lf-option></lf-options></section>',
        head='<script type="module" src="./page/app.js"></script>'
        '<link rel="stylesheet" href="./page/style.css">',
    )
    (page_dir / "index.html").write_text(source)
    activation = activate_source(page_dir)
    assert activation.error is None, activation.error
    append_event(
        page_dir,
        {
            "kind": "note",
            "author": "agent",
            "version": 1,
            "revision": activation.revision,
            "text": "Published",
        },
    )
    destination = tmp_path / "public"
    with TemporaryPageServer(page_dir) as server, browser.new_context() as context:
        write_live_shell(
            page_dir,
            destination,
            server_id=server.httpd.server_id,
        )
        root = "/revisions/" + revision_path(page_dir, activation.revision).stem
        if bundled:
            bundler = Path(__file__).parents[2] / "worker" / "bundle-runtime.mjs"
            subprocess.run(
                [
                    "node",
                    "--input-type=module",
                    "-e",
                    (
                        f"import {{ bundleLayer }} from {json.dumps(bundler.as_uri())}; "
                        "await bundleLayer(process.argv[1], process.argv[2]);"
                    ),
                    str(destination / root.lstrip("/")),
                    root,
                ],
                check=True,
            )
        # The API stays live, while the static host is only allowed to read the
        # materialized public tree. It cannot silently use the server's asset route.
        assert context.request.get(server.url).ok
        (authored / "nested" / "value.js").write_text('export const value = "Later";')
        loaded = []

        def public_files(route):
            path = urlsplit(route.request.url).path
            if path.startswith("/api/"):
                route.continue_()
                return
            loaded.append(path)
            file = destination / path.lstrip("/")
            assert file.is_file(), f"missing published resource: {path}"
            route.fulfill(
                body=file.read_bytes(), content_type=RESOURCE_TYPES[Path(path).suffix]
            )

        context.route(server.origin + "/**", public_files)
        page = open_page(
            browser,
            server.origin + "/versions/v1.html",
            context=context,
            pin=True,
        )
        button = page.get_by_role("button", name="Read captured value")
        button.click()
        expect(page.locator("#result")).to_have_text("Captured")
        expect(page.locator("#result")).to_have_css("color", "rgb(1, 2, 3)")
        page.keyboard.press("Tab")
        page.keyboard.press("Shift+Tab")
        expect(button).to_be_focused()
        page.keyboard.press("Enter")
        expect(page.locator("#result")).to_have_text("Captured")
        expect(page.locator("#module")).to_have_text(
            f"1: import.meta.url: {server.origin}{root}/page/widgets/lf-options.js"
        )
        assert root + "/widgets/lf-options.js" in loaded
        assert root + "/page/widgets/lf-options.js" in loaded
        assert root + "/page/nested/value.js" in loaded
        assert root + "/page/nested/theme.css" in loaded
        # A layer module named by its rooted path, from a document a directory below
        # the page root, is the revision's: the instance the runtime itself imported.
        assert page.evaluate(
            """async root =>
              (await import('/runtime/widget-api.js')) ===
              (await import(`${root}/runtime/widget-api.js`))""",
            root,
        )
