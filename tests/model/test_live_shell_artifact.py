"""Published documents and modules retain their complete captured revision."""

import copy
import json

import pytest
from interact_support import PAGE
from interact_support import append_carried_log_record as append_event

from leaf.files import revision_path
from leaf.live_shell import write_live_shell
from leaf.registry.storage import load_registry
from leaf.revision_artifact import read_artifact
from leaf.revision_delivery import json_script, layer_import_map
from leaf.revisioning import activate_source
from leaf.runtime_selection import executing


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
    entry = copy.deepcopy(load_registry(page_dir)["lf-options"])
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
    page_widget = 'import { value } from "../nested/value.js"; window.widget = value;'
    (authored / "widgets" / "lf-options.js").write_text(page_widget)
    entry["description"] = "Second page declaration"
    (authored / "registry.json").write_text(json.dumps({"lf-options": entry}))
    (page_dir / "index.html").write_text(source.replace("<title>t", "<title>Second"))
    second = publish(2)
    second_artifact = read_artifact(page_dir, second)

    # Publishing must not validate or read an unactivated candidate.
    (page_dir / "index.html").write_text("invalid candidate")
    (authored / "nested" / "value.js").write_text("invalid candidate")
    (authored / "widgets" / "lf-options.js").write_text("invalid candidate")
    (authored / "registry.json").write_text("invalid candidate")
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
        assert f'name="lf-revision" content="{revision}" data-lf-runtime' in document
        assert f'name="lf-version" content="{version}" data-lf-runtime' in document
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
        # The publishing Leaf's runtime and layer, which the revision never
        # captured, are published beside it; the document's import map sends its
        # rooted imports to this revision.
        runtime = executing(artifact).resources
        assert "/leaf.js" not in artifact.resources
        assert (resources / "leaf.js").read_bytes() == runtime["/leaf.js"].data
        assert runtime["/runtime/bootstrap.js"].data.decode() in document
        assert json_script(layer_import_map(root)) in document
        expected_widget = (
            f'export * from "{root}/page/widgets/lf-options.js";\n'.encode()
            if version == 2
            else runtime["/widgets/lf-options.js"].data
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
        "data",
    ):
        assert not (destination / mutable).exists()
