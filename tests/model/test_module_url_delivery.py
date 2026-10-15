"""Portable regressions for captured module URL and resource identities."""

import json

import pytest


@pytest.mark.parametrize(
    ("directory", "name", "specifier"),
    [
        (directory, name, specifier)
        for directory in ("runtime/helpers", "vendor", "page")
        for name, specifier in [
            ("État+v1.mjs", "État+v1.mjs"),
            ("💧state.mjs", "💧state.mjs"),
            ('"state.mjs', "%22state.mjs"),
        ]
    ]
    + [("page", "#state.mjs", "%23state.mjs"), ("page", "?state.mjs", "%3Fstate.mjs")],
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
    tmp_path, directory, name, specifier, module
):
    """Module URL spelling preserves logical filenames across delivery and export."""
    import base64

    from leaf.exporting import _module_urls
    from leaf.revision_artifact import Resource, capture_artifact
    from leaf.revision_delivery import DeliveryAddress, deliver_resource, rebase_module
    from leaf.structure import SourceDocument

    alias = "/widgets/lf-risk-note.js"
    widget = "/page" + alias if directory == "page" else alias
    helper = f"/{directory}/{name}"
    public = "/runtime/widget-api.js"
    address = DeliveryAddress("", "/revisions/r1-package")
    module = module.replace("HELPER", f"/{directory}/{specifier}")
    delivered = deliver_resource(
        Resource(module.encode(), "application/javascript"), widget, address
    )
    # Layer modules keep captured bytes; the import map addresses their graph.
    if directory == "page":
        rebased = rebase_module(module.encode(), widget, address)
        assert delivered.data == rebased
        assert address(f"/{directory}/{specifier}") in rebased.decode()
    else:
        assert delivered.data == module.encode()
    files = {
        "/leaf.js": "export {};",
        widget: module,
        helper: f'export {{ once }} from "{public}";',
        public: "export const once = () => true;",
    }
    for logical, source in files.items():
        path = tmp_path / logical.lstrip("/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    document = SourceDocument("<main><lf-risk-note></lf-risk-note></main>")
    artifact = capture_artifact(
        tmp_path,
        document,
        {"lf-risk-note": {"x-upgrade": True}},
        widget_sources={"lf-risk-note": widget.lstrip("/")},
    )
    assert artifact.resources[helper].mime == "application/javascript"
    embedded = _module_urls(artifact, [document])
    assert set(embedded) == {"/leaf.js", alias, widget, helper, public}
    assert embedded[alias] == embedded[widget]
    source = base64.b64decode(embedded[widget].split(",", 1)[1]).decode()
    assert json.dumps(f"leaf:{helper}") in source


def test_delivery_css_urls_preserve_query_and_fragment_suffixes():
    """CSS addresses URLs with suffixes while module targets are logical paths."""
    from leaf.revision_artifact import Resource
    from leaf.revision_delivery import DeliveryAddress, deliver_resource

    address = DeliveryAddress("", "/revisions/r1-package")
    source = 'main { background: url("/runtime/État.svg?theme=dark#shape"); mask: url("/vendor/État.svg?theme=dark#shape"); cursor: url("/page/leaf%23shape.svg?theme=dark#shape"), auto; }'
    delivered = deliver_resource(
        Resource(source.encode(), "text/css"), "/theme.css", address
    ).data.decode()
    assert (
        'url("/revisions/r1-package/runtime/%C3%89tat.svg?theme=dark#shape")'
        in delivered
    )
    assert (
        'url("/revisions/r1-package/vendor/%C3%89tat.svg?theme=dark#shape")'
        in delivered
    )
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

    from leaf.exporting import _module_urls, export_document
    from leaf.revision_artifact import capture_artifact
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
    modules = _module_urls(artifact, [document])
    logical = "/page/" + name
    assert logical in modules
    exported = export_document(
        artifact,
        document,
        {"events": []},
        {},
        1,
        1,
        {},
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
