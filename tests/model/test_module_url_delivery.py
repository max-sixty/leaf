"""Portable regressions for captured module URL and resource identities."""

import json

import pytest


@pytest.mark.parametrize(
    ("directory", "shared"),
    [("runtime/helpers", False), ("vendor", True), ("vendor", False), ("page", False)],
)
@pytest.mark.parametrize(
    ("name", "specifier"),
    [
        ("État+v1.mjs", "État+v1.mjs"),
        ("💧state.mjs", "💧state.mjs"),
        ('"state.mjs', "%22state.mjs"),
        ("#state.mjs", "%23state.mjs"),
        ("?state.mjs", "%3Fstate.mjs"),
    ],
)
@pytest.mark.parametrize(
    "module",
    [
        'import { once } from "HELPER";',
        'export { once } from "HELPER";',
        'const loaded = import("HELPER");',
    ],
)
def test_native_package_import_urls_survive_delivery_and_export(
    directory, shared, name, specifier, module
):
    """Module URL spelling preserves logical filenames across delivery and export."""
    import base64

    from leaf.exporting import _module_urls
    from leaf.revision_artifact import Resource
    from leaf.revision_delivery import (
        PublicationAddress,
        deliver_resource,
        rebase_module,
    )

    widget = "/widgets/lf-risk-note.js"
    helper = f"/{directory}/{name}"
    public = "/runtime/widget-api.js"
    root = "/revisions/r1-package"
    address = PublicationAddress(
        "", root, frozenset({helper}) if shared else frozenset()
    )
    module = module.replace("HELPER", f"/{directory}/{specifier}")
    delivered = deliver_resource(
        Resource(module.encode(), "application/javascript"), widget, address
    )
    if directory == "page":
        assert rebase_module(module.encode(), "/page/app.js", address) == delivered.data
    held_helper = (
        helper if shared or directory.startswith("runtime/") else root + helper
    )
    resources = {
        address(widget): delivered,
        held_helper: deliver_resource(
            Resource(
                f'export {{ once }} from "{public}";'.encode(), "application/javascript"
            ),
            helper,
            address,
        ),
        public: Resource(b"export const once = () => true;", "application/javascript"),
    }
    embedded = _module_urls(resources, [address(widget)])
    assert set(embedded) == {address(widget), held_helper, public}
    source = base64.b64decode(embedded[address(widget)].split(",", 1)[1]).decode()
    assert json.dumps(f"leaf:{held_helper}") in source


def test_publication_css_urls_preserve_query_and_fragment_suffixes():
    """CSS addresses URLs with suffixes while module targets are logical paths."""
    from leaf.revision_artifact import Resource
    from leaf.revision_delivery import PublicationAddress, deliver_resource

    address = PublicationAddress(
        "", "/revisions/r1-package", frozenset({"/vendor/État.svg"})
    )
    source = 'main { background: url("/runtime/État.svg?theme=dark#shape"); mask: url("/vendor/État.svg?theme=dark#shape"); cursor: url("/page/leaf%23shape.svg?theme=dark#shape"), auto; }'
    delivered = deliver_resource(
        Resource(source.encode(), "text/css"), "/theme.css", address
    ).data.decode()
    assert 'url("/runtime/%C3%89tat.svg?theme=dark#shape")' in delivered
    assert 'url("/vendor/%C3%89tat.svg?theme=dark#shape")' in delivered
    assert (
        'url("/revisions/r1-package/page/leaf%23shape.svg?theme=dark#shape")'
        in delivered
    )


@pytest.mark.parametrize(
    "name",
    ["app.mjs", "État+v1.mjs", "💧state.mjs", '"state.mjs', "#state.mjs", "?state.mjs"],
)
def test_authored_module_entry_exports_through_its_one_import_map_url(tmp_path, name):
    """Entry URLs resolve to logical captured modules, including native URL syntax."""
    from urllib.parse import quote

    from leaf.exporting import _export_resources, _module_urls, export_document
    from leaf.revision_artifact import artifact_name, capture_artifact
    from leaf.structure import SourceDocument

    files = {
        "leaf.js": "export {};",
        "runtime/widget-api.js": "export {};",
        "runtime/offline-delivery.js": "",
        "runtime/prepaint.js": "",
        "runtime/annotation-overlay/annotation-theme.css": "",
        "runtime/annotation-overlay/annotation-chrome.css": "",
        "runtime/annotation-overlay/annotation-marks.css": "",
        "runtime/chrome.css": "",
        "runtime/marks.css": "",
        "theme.css": "",
        "shadow.css": "",
        "widget-theme.css": "",
        f"page/{name}": 'import "./helper.mjs"; export const entry = true;',
        "page/helper.mjs": "export const helper = true;",
    }
    for filename, source in files.items():
        target = tmp_path / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)
    document = SourceDocument(
        f'<html><head><script type="module" src="./page/{quote(name, safe="")}"></script></head><body><main><h1>Authored entry</h1></main></body></html>'
    )
    artifact = capture_artifact(tmp_path, document, {})
    root = "/revisions/" + artifact_name(1, artifact)
    resources, pending, _ = _export_resources(
        artifact, {1: artifact}, {"1": root}, {1: [document]}, {}
    )
    modules = _module_urls(resources, pending)
    logical = root + "/page/" + name
    assert logical in modules
    exported = export_document(
        artifact,
        document,
        {"events": []},
        {},
        1,
        1,
        {},
        kernel=artifact,
        publications={1: artifact},
    )
    package = json.loads(
        SourceDocument(exported).tree.select_one("script[data-lf-export]").text
    )
    composed = SourceDocument(package["document"])
    import_map = json.loads(composed.tree.select_one('script[type="importmap"]').text)[
        "imports"
    ]
    entry = next(
        script
        for script in composed.external_scripts
        if "data-lf-runtime" not in script["attrs"]
    )
    assert entry["attrs"]["src"] == import_map[f"leaf:{logical}"] == modules[logical]
