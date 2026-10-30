"""Portable regressions for captured module URL and resource identities."""

import json
from dataclasses import replace
from types import MappingProxyType

import pytest

from leaf.runtime_selection import ServingRuntime


def running(artifact, runtime: dict[str, str], layer=None, vocabulary=None):
    """`artifact` as it runs under a runtime and a layer of these files
    (`runtime_selection.executing`), read in `vocabulary`: the one these tests
    capture under, which stands for the vocabulary a Leaf composes from the
    revision's layer selection and its own declarations
    (`registry.storage.revision_vocabulary`)."""
    from leaf.revision_artifact import Resource

    served = ServingRuntime(
        MappingProxyType({path: data.encode() for path, data in runtime.items()}),
        None,
        frozenset(),
        MappingProxyType({}),
    )
    layer = {
        path: Resource(data.encode(), "application/javascript")
        for path, data in (layer or {}).items()
    }
    vocabulary = vocabulary or {}
    layer["/registry.json"] = Resource(
        json.dumps(vocabulary).encode(), "application/json"
    )
    executed = replace(artifact, resources=served.resources(layer, artifact.resources))
    vars(executed)["registry"] = vocabulary
    return executed


@pytest.mark.parametrize(
    ("reference", "importer", "expected"),
    [
        (
            " ./page/État%20v1.svg?theme=dark#shape ",
            "/index.html",
            ("/page/État v1.svg", "?theme=dark#shape"),
        ),
        ("./child%2Fimage.svg", "/page/main.css", ("/page/child/image.svg", "")),
        ("./im\tage.svg", "/page/main.css", ("/page/image.svg", "")),
        ("./im\nage.svg", "/page/main.css", ("/page/image.svg", "")),
        (r"./sub\image.svg", "/page/main.css", ("/page/sub/image.svg", "")),
        ("HTTPS :image.svg", "/page/main.css", ("/page/HTTPS :image.svg", "")),
        ("./next.svg", "/page/?#%dir/main.css", ("/page/?#%dir/next.svg", "")),
        (
            "/page/%252e%252e/value.svg",
            "/index.html",
            ("/page/%2e%2e/value.svg", ""),
        ),
    ],
)
def test_capture_and_delivery_resolve_the_same_browser_url(
    reference, importer, expected
):
    from leaf.revision_artifact import resolve_dependency
    from leaf.revision_delivery import page_path

    assert resolve_dependency(reference, importer) == expected[0]
    assert page_path(reference, importer) == expected


@pytest.mark.parametrize(
    "reference",
    [
        "https://leaf.invalid/page/image.svg",
        "https://relative.invalid/page/image.svg",
        "http://leaf.invalid/page/image.svg",
        "http://relative.invalid/page/image.svg",
        "https:///page/image.svg",
        "//leaf.invalid/page/image.svg",
        "//relative.invalid/page/image.svg",
        r"\\leaf.invalid\page\image.svg",
        r"\\other-host\page\image.svg",
        "data:image/png,abc",
        " \t#paint \n",
        " # ",
    ],
)
def test_nonlocal_and_fragment_resources_stay_as_written(reference):
    from leaf.revision_artifact import dependency_reference
    from leaf.revision_delivery import page_path

    assert dependency_reference(reference, "/page/image.svg") is None
    assert page_path(reference, "/page/image.svg") is None


@pytest.mark.parametrize("scheme", ["http", "https"])
@pytest.mark.parametrize("path", ["/page/image.svg", "page/image.svg"])
def test_scheme_dependent_html_resources_are_refused(tmp_path, scheme, path):
    from leaf.revision_artifact import ArtifactError, capture_artifact
    from leaf.revision_delivery import page_path
    from leaf.structure import SourceDocument

    reference = f"{scheme}:{path}"
    (tmp_path / "leaf.js").write_text("export {};")
    (tmp_path / "page").mkdir()
    (tmp_path / "page/image.svg").write_text("<svg/>")
    document = SourceDocument(f'<img src="{reference}">')
    for read in (
        lambda: capture_artifact(tmp_path, document, {}),
        lambda: page_path(reference, "/index.html"),
    ):
        with pytest.raises(ArtifactError, match="depends on the page's URL scheme"):
            read()


@pytest.mark.parametrize(
    "reference", ["https:", "http:", "https:#paint", "http:#paint", "https://["]
)
def test_invalid_or_scheme_dependent_resource_urls_reach_admission(tmp_path, reference):
    from leaf.revision_artifact import ArtifactError, capture_artifact
    from leaf.structure import SourceDocument

    (tmp_path / "leaf.js").write_text("export {};")
    with pytest.raises(ArtifactError):
        capture_artifact(tmp_path, SourceDocument(f'<img src="{reference}">'), {})


def test_an_explicit_self_resource_keeps_its_fragment():
    from leaf.revision_delivery import page_path

    assert page_path("./image.svg#paint", "/page/image.svg") == (
        "/page/image.svg",
        "#paint",
    )


def test_stylesheet_import_uses_the_same_browser_url_reading():
    from leaf.revision_artifact import Resource
    from leaf.revision_delivery import DeliveryAddress, deliver_resource

    resource = Resource(b'@import " ./palette.css ";', "text/css")
    delivered = deliver_resource(
        resource, "/page/main.css", DeliveryAddress("", "/revision")
    )
    assert delivered.data == b'@import "/revision/page/palette.css";'


@pytest.mark.parametrize("scheme", ["http", "https"])
@pytest.mark.parametrize("path", ["/page/external.mjs", "page/external.mjs"])
def test_javascript_absolute_imports_resolve_without_the_documents_base(
    tmp_path, scheme, path
):
    from leaf.revision_artifact import capture_artifact
    from leaf.revision_delivery import DeliveryAddress, rebase_module
    from leaf.structure import SourceDocument

    source = f'import "{scheme}:{path}";'.encode()
    (tmp_path / "leaf.js").write_text("export {};")
    (tmp_path / "page").mkdir()
    (tmp_path / "page/app.mjs").write_bytes(source)
    document = SourceDocument('<script type="module" src="page/app.mjs"></script>')
    artifact = capture_artifact(tmp_path, document, {})
    assert "/page/app.mjs" in artifact.resources
    assert "/page/external.mjs" not in artifact.resources
    assert (
        rebase_module(source, "/page/app.mjs", DeliveryAddress("", "/revision"))
        == source
    )


@pytest.mark.parametrize(
    ("directory", "name", "specifier"),
    [
        (directory, name, specifier)
        for directory in ("runtime/helpers", "vendor", "page")
        for name, specifier in [
            ("État+v1.mjs", "État+v1.mjs"),
            ("💧state.mjs", "💧state.mjs"),
            ('"state.mjs', "%22state.mjs"),
            ("my 100%20state.mjs", "my%20100%2520state.mjs"),
            ("#state.mjs", "%23state.mjs"),
            ("?state.mjs", "%3Fstate.mjs"),
        ]
    ]
    + [
        ("page", "my state.mjs", "my state.mjs"),
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
    # A page's own modules are captured; a package's arrive with the layer.
    files = {widget: module, helper: f'export {{ once }} from "{public}";'}
    if directory == "page":
        for logical, source in files.items():
            path = tmp_path / logical.lstrip("/")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source)
    document = SourceDocument("<main><lf-risk-note></lf-risk-note></main>")
    vocabulary = {"lf-risk-note": {"x-upgrade": True}}
    artifact = capture_artifact(
        tmp_path,
        document,
        vocabulary,
        widget_sources={"lf-risk-note": widget.lstrip("/")},
    )
    assert (helper in artifact.resources) == (directory == "page")
    artifact = running(
        artifact,
        {"/leaf.js": "export {};", public: "export const once = () => true;"},
        {} if directory == "page" else files,
        vocabulary,
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
    [
        "app.mjs",
        "État+v1.mjs",
        "💧state.mjs",
        '"state.mjs',
        "#state.mjs",
        "?state.mjs",
        "my 100%20state.mjs",
    ],
)
def test_authored_module_entry_exports_through_its_one_import_map_url(tmp_path, name):
    """Entry URLs resolve to logical captured modules, including native URL syntax."""
    from urllib.parse import quote

    from model_folds import served_reading

    from leaf.exporting import _module_urls, export_document
    from leaf.revision_artifact import capture_artifact
    from leaf.structure import SourceDocument

    files = {
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
    vocabulary = {"$layer": {"generation": "exported"}}
    artifact = running(
        capture_artifact(tmp_path, document, vocabulary),
        {
            path: "export {};" if path.endswith(".js") else ""
            for path in [
                "/leaf.js",
                "/runtime/widget-api.js",
                "/runtime/offline-delivery.js",
                "/runtime/prepaint.js",
                "/runtime/annotation-overlay/annotation-theme.css",
                "/runtime/annotation-overlay/annotation-chrome.css",
                "/runtime/annotation-overlay/annotation-marks.css",
                "/runtime/chrome.css",
                "/runtime/marks.css",
                "/theme.css",
                "/shadow.css",
                "/chrome.css",
                "/widget-theme.css",
            ]
        },
        vocabulary=vocabulary,
    )
    modules = _module_urls(artifact, [document])
    logical = "/page/" + name
    assert logical in modules
    exported = export_document(
        artifact,
        document,
        served_reading(document.html),
        {},
        1,
        1,
        {},
    )
    select_one_result = SourceDocument(exported).tree.select_one(
        "script[data-lf-export]"
    )
    assert select_one_result is not None
    package = json.loads(select_one_result.text)
    composed = SourceDocument(package["document"])
    select_one_result_2 = composed.tree.select_one('script[type="importmap"]')
    assert select_one_result_2 is not None
    import_map = json.loads(select_one_result_2.text)["imports"]
    entry = next(
        script
        for script in composed.authoring.external_scripts
        if "data-lf-runtime" not in script["attrs"]
    )
    assert entry["attrs"]["src"] == import_map[f"leaf:{logical}"] == modules[logical]


def test_exported_widgets_share_the_runtime_lit_module(tmp_path):
    """Widgets introduced by a later message use the page's one ordinary Lit module."""
    import base64

    from leaf.exporting import _module_urls
    from leaf.revision_artifact import capture_artifact
    from leaf.structure import SourceDocument

    runtime = {
        "/leaf.js": 'import { render } from "/vendor/lit.js";',
        "/vendor/lit.js": 'export const render = "module implementation";',
    }
    layer = {"/widgets/lf-later.js": 'import { render } from "/vendor/lit.js";'}
    document = SourceDocument("<main>Plain</main>")
    vocabulary = {"lf-later": {"x-upgrade": True}}
    artifact = running(
        capture_artifact(tmp_path, document, vocabulary), runtime, layer, vocabulary
    )
    modules = _module_urls(
        artifact, [document, SourceDocument("<lf-later></lf-later>")]
    )
    implementation = base64.b64decode(
        modules["/vendor/lit.js"].split(",", 1)[1]
    ).decode()
    assert implementation == runtime["/vendor/lit.js"]
    widget = base64.b64decode(modules["/widgets/lf-later.js"].split(",", 1)[1]).decode()
    assert '"leaf:/vendor/lit.js"' in widget


# A name the page serves under media/ (`schema.MEDIA_DIGEST`), so either prefix
# captures it; the last reference spells its first letter as an escape.
IMAGE = "abcdef0123456789.svg"


@pytest.mark.parametrize("prefix", ["page", "media"])
@pytest.mark.parametrize(
    "reference",
    [
        " {prefix}/abcdef0123456789.svg ",
        r"{prefix}\abcdef0123456789.svg",
        "{prefix}/%61bcdef0123456789.svg",
    ],
)
def test_document_resources_capture_the_paths_delivery_rewrites(
    tmp_path, prefix, reference
):
    from leaf.revision_artifact import capture_artifact
    from leaf.revision_delivery import DeliveryAddress, rebase_document
    from leaf.structure import SourceDocument

    (tmp_path / "leaf.js").write_text("export {};")
    (tmp_path / prefix).mkdir()
    (tmp_path / prefix / IMAGE).write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    source = f'<img src="{reference.format(prefix=prefix)}">'
    document = SourceDocument(source)
    artifact = capture_artifact(tmp_path, document, {})
    assert f"/{prefix}/{IMAGE}" in artifact.resources
    if prefix == "media":
        assert document.authoring.media_refs == {f"/media/{IMAGE}"}
    delivered = rebase_document(source, DeliveryAddress("/root", "/revision"))
    expected = (
        f"/root/media/{IMAGE}" if prefix == "media" else f"/revision/page/{IMAGE}"
    )
    assert expected in delivered


def test_media_attributes_share_normalized_resource_identity():
    from leaf.structure import SourceDocument

    document = SourceDocument(
        '<a href=" /media/im%61ge.svg?download=1 ">Image</a><lf-compare before="media/image.svg">'
    )
    assert document.authoring.media_refs == {"/media/image.svg"}


@pytest.mark.parametrize(
    "reference", ["/page/%00.svg", "/page/../secret.svg", "/page/%2e%2e/secret.svg"]
)
def test_actual_resource_attributes_reach_capture_admission(tmp_path, reference):
    from leaf.revision_artifact import ArtifactError, capture_artifact
    from leaf.structure import SourceDocument

    (tmp_path / "leaf.js").write_text("export {};")
    document = SourceDocument(f'<img src="{reference}">')
    with pytest.raises(ArtifactError):
        capture_artifact(tmp_path, document, {})


@pytest.mark.parametrize(
    "reference",
    [
        "https://leaf.invalid/page/image.svg",
        r"\\leaf.invalid\page\image.svg",
        "/icon.svg",
    ],
)
def test_document_resource_collection_preserves_external_and_layer_resources(
    tmp_path, reference
):
    """A document may name an external resource or one its layer serves, such as the
    layer's icon; the revision captures neither, and the layer's arrives with it."""
    from leaf.revision_artifact import capture_artifact
    from leaf.runtime_selection import executing
    from leaf.structure import SourceDocument

    vocabulary = {"$layer": {"generation": "g", "packages": [], "theme": None}}
    artifact = capture_artifact(
        tmp_path, SourceDocument(f'<img src="{reference}">'), vocabulary
    )
    assert not artifact.resources
    assert "/icon.svg" in executing(artifact).resources


@pytest.mark.parametrize(
    "value", ["https:", "https:/", "https:#x", "mailto:hello@example.com"]
)
def test_resource_collection_does_not_interpret_arbitrary_attributes_as_dependencies(
    value,
):
    from leaf.structure import SourceDocument

    document = SourceDocument(f'<p title="{value}">Hi</p>')
    assert not document.authoring.media_refs
    assert not document.authoring.resource_refs
