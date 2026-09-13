"""Published documents and modules retain their complete captured revision."""

import html
import json
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from interact_support import PAGE
from leaf.event_log import append_event, read_events
from leaf.files import replace_files, revision_path
from leaf.hosting import TemporaryPageServer
from leaf.http import scope_script_routes, script_hash
from leaf.live_shell import write_live_shell
from leaf.revision_artifact import RESOURCE_TYPES, read_artifact
from leaf.revisioning import activate_source
from leaf.structure import SourceDocument
from playwright.sync_api import expect
from render_harness import leaf_page, open_page


@pytest.mark.parametrize(
    ("page_root", "asset_root"),
    [
        ("", None),
        ("/examples/study", None),
        ("/examples/study", "/_leaf-release/build/study"),
    ],
)
def test_published_shells_bind_documents_and_resources_to_their_revision(
    page_dir, tmp_path, page_root, asset_root
):
    authored = page_dir / "page"
    (authored / "nested").mkdir(parents=True)
    (authored / "widgets").mkdir()
    (authored / "app.js").write_text(
        'import { value } from "./nested/value.js"; window.result = value;'
    )
    (authored / "nested" / "value.js").write_text("export const value = 1;")
    (authored / "style.css").write_text('@import "./nested/theme.css";')
    (authored / "nested" / "theme.css").write_text(
        'main { background-image: url("../image.svg#paint"); }'
    )
    (authored / "image.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    entry = json.loads((page_dir / "registry.json").read_text())["lf-options"]
    entry["description"] = "First page declaration"
    (authored / "registry.json").write_text(json.dumps({"lf-options": entry}))
    source = PAGE.replace(
        "</head>",
        '<script type="module" src="./page/app.js"></script>'
        '<script type="module">import "./page/nested/value.js";</script>'
        '<link rel="stylesheet" href="./page/style.css"></head>',
    )
    (page_dir / "index.html").write_text(source)

    def publish(version):
        activation = activate_source(page_dir, read_events(page_dir))
        assert activation.error is None, activation.error
        append_event(
            page_dir,
            {
                "kind": "note",
                "author": "claude",
                "version": version,
                "revision": activation.revision,
                "text": "Published",
            },
        )
        return activation.revision

    first = publish(1)
    first_artifact = read_artifact(page_dir, first)
    (authored / "nested" / "value.js").write_text("export const value = 2;")
    page_widget = 'import { value } from "../nested/value.js"; window.widget = value;'
    (authored / "widgets" / "lf-options.js").write_text(page_widget)
    entry["description"] = "Second page declaration"
    (authored / "registry.json").write_text(json.dumps({"lf-options": entry}))
    (page_dir / "index.html").write_text(source.replace("<title>t", "<title>Second"))
    second = publish(2)
    second_artifact = read_artifact(page_dir, second)

    # Publishing must not validate or read an unactivated candidate, even after a
    # layer replacement. Runtime fixture inputs are hardlinks, so replace atomically.
    (page_dir / "index.html").write_text("invalid candidate")
    (authored / "nested" / "value.js").write_text("invalid candidate")
    (authored / "widgets" / "lf-options.js").write_text("invalid candidate")
    (authored / "registry.json").write_text("invalid candidate")
    replace_files(
        [
            (page_dir / relative, b"invalid candidate", False)
            for relative in (
                "leaf.js",
                "registry.json",
                "runtime/bootstrap.js",
                "widgets/lf-options.js",
            )
        ]
    )
    destination = tmp_path / "published"
    additions = '<meta name="site-owned" content="delivery">'
    write_live_shell(
        page_dir,
        destination,
        page_root=page_root,
        asset_root=asset_root,
        release_id="release",
        before_runtime=additions,
    )

    for version, revision, artifact in [
        (1, first, first_artifact),
        (2, second, second_artifact),
    ]:
        marker = revision_path(page_dir, revision).name
        relative = f"revisions/{marker.removesuffix('.html')}"
        root = (asset_root if asset_root is not None else page_root) + "/" + relative
        resources = destination / relative
        document = (destination / "versions" / f"v{version}.html").read_text()
        parsed = SourceDocument(document)
        assert (destination / "revisions" / marker).read_text() == document
        assert f'name="lf-revision" data-lf-runtime content="{revision}"' in document
        assert f'name="lf-version" data-lf-runtime content="{version}"' in document
        assert f'src="{root}/leaf.js"' in document
        assert f'src="{root}/page/app.js"' in document
        assert f'href="{root}/page/style.css"' in document
        assert f'data-lf-probe="{root}/registry.json"' in document
        assert f'href="{page_root}/" data-lf-runtime' in document
        assert additions in document
        assert (
            json.loads((resources / "registry.json").read_text()) == artifact.registry
        )
        assert (
            resources / "page" / "nested" / "value.js"
        ).read_text() == f"export const value = {version};"
        assert (resources / "page" / "app.js").read_text() == (
            f'import {{ value }} from "{root}/page/nested/value.js"; window.result = value;'
        )
        assert (
            resources / "page" / "style.css"
        ).read_text() == f'@import "{root}/page/nested/theme.css";'
        assert (resources / "page" / "nested" / "theme.css").read_text() == (
            f'main {{ background-image: url("{root}/page/image.svg#paint"); }}'
        )
        assert (resources / "leaf.js").read_bytes() == scope_script_routes(
            artifact.resources["/leaf.js"].data,
            page_root,
            asset_root=root,
        )
        bootstrap = scope_script_routes(
            artifact.resources["/runtime/bootstrap.js"].data,
            page_root,
            asset_root=root,
        ).decode()
        assert bootstrap in document
        for script in parsed.inline_scripts:
            assert script_hash(script["body"]) in html.unescape(document)
        expected_widget = (
            f'export * from "{root}/page/widgets/lf-options.js";\n'.encode()
            if version == 2
            else scope_script_routes(
                artifact.resources["/widgets/lf-options.js"].data,
                page_root,
                asset_root=root,
            )
        )
        assert (resources / "widgets" / "lf-options.js").read_bytes() == expected_widget
        if version == 2:
            assert (resources / "page" / "widgets" / "lf-options.js").read_text() == (
                f'import {{ value }} from "{root}/page/nested/value.js"; window.widget = value;'
            )

    assert (destination / "index.html").read_bytes() == (
        destination / "versions" / "v2.html"
    ).read_bytes()
    for mutable in (
        "leaf.js",
        "registry.json",
        "runtime",
        "widgets",
        "page",
        "events.jsonl",
        "data.json",
    ):
        assert not (destination / mutable).exists()


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
        'document.querySelector("#read").addEventListener("click", () => { '
        'document.querySelector("#result").textContent = value; '
        'document.querySelector("#module").textContent = '
        "`${window.widgetLoads}: ${prose}: ${moduleUrl}`; });"
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
    activation = activate_source(page_dir, [])
    assert activation.error is None, activation.error
    append_event(
        page_dir,
        {
            "kind": "note",
            "author": "claude",
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
            server_id=server.httpd.RequestHandlerClass.server_id,
        )
        root = "/revisions/" + revision_path(page_dir, activation.revision).stem
        if bundled:
            bundler = Path(__file__).parents[1] / "worker" / "bundle-runtime.mjs"
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
        page, errors = open_page(
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
        assert errors == []
