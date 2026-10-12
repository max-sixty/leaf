"""Published documents and modules retain their complete captured revision."""

import json

import pytest
from interact_support import PAGE
from interact_support import append_carried_log_record as append_event
from leaf.files import replace_files, revision_path
from leaf.live_shell import write_live_shell
from leaf.revision_artifact import javascript_imports, read_artifact
from leaf.revision_delivery import (
    PublicationAddress,
    delivered_resource,
    json_script,
    layer_import_map,
)
from leaf.revisioning import activate_source


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
        'import "/runtime/widget-api.js"; '
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
        activation = activate_source(page_dir)
        assert activation.error is None, activation.error
        append_event(
            page_dir,
            {
                "kind": "note",
                "author": "agent",
                "version": version,
                "revision": activation.revision,
                "text": "Published",
            },
        )
        return activation.revision

    first = publish(1)
    first_artifact = read_artifact(page_dir, first)
    (authored / "nested" / "value.js").write_text("export const value = 2;")
    page_widget = 'import { value } from "../nested/value.js"; window.widget = value; export default class extends HTMLElement {};'
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
        head=additions,
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
        assert (destination / "revisions" / marker).read_text() == document
        assert f'name="lf-revision" data-lf-runtime content="{revision}"' in document
        assert f'name="lf-version" data-lf-runtime content="{version}"' in document
        kernel_root = (
            (asset_root if asset_root is not None else page_root)
            + "/revisions/"
            + revision_path(page_dir, second).stem
        )
        assert f'src="{kernel_root}/leaf.js"' in document
        assert f'src="{root}/page/app.js"' in document
        assert f'href="{root}/page/style.css"' in document
        assert f'data-lf-probe="{kernel_root}/registry.json"' in document
        assert f'data-lf-vocabulary-root="{root}/registry.json"' in document
        assert f'href="{page_root}/" data-lf-runtime' in document
        assert additions in document
        assert (
            json.loads((resources / "registry.json").read_text()) == artifact.registry
        )
        assert (
            resources / "page" / "nested" / "value.js"
        ).read_text() == f"export const value = {version};"
        assert (resources / "page" / "app.js").read_text() == (
            'import "/runtime/widget-api.js"; '
            f'import {{ value }} from "{root}/page/nested/value.js"; window.result = value;'
        )
        assert (
            resources / "page" / "style.css"
        ).read_text() == f'@import "{root}/page/nested/theme.css";'
        assert (resources / "page" / "nested" / "theme.css").read_text() == (
            f'main {{ background-image: url("{root}/page/image.svg#paint"); }}'
        )
        # The layer is published as captured; the document's import map sends its
        # rooted imports to this revision.
        if revision == second:
            assert (resources / "leaf.js").read_bytes() == second_artifact.resources[
                "/leaf.js"
            ].data
            assert "/runtime/dom-move.js" in {
                specifier
                for _, _, specifier in javascript_imports(
                    (resources / "vendor" / "lit.js").read_bytes(), "/vendor/lit.js"
                )
            }
        else:
            assert not (resources / "leaf.js").exists()
            assert not (resources / "runtime").exists()
        assert (
            second_artifact.resources["/runtime/bootstrap.js"].data.decode() in document
        )
        assert json_script(layer_import_map(kernel_root)) in document
        expected_widget = (
            f'export {{default}} from "{root}/page/widgets/lf-options.js";\n'.encode()
            if version == 2
            else delivered_resource(
                artifact,
                "/widgets/lf-options.js",
                PublicationAddress(page_root, root, artifact.shared_modules),
            ).data
        )
        assert (resources / "widgets" / "lf-options.js").read_bytes() == expected_widget
        if version == 2:
            assert (resources / "page" / "widgets" / "lf-options.js").read_text() == (
                f'import {{ value }} from "{root}/page/nested/value.js"; window.widget = value; export default class extends HTMLElement {{}};'
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
