"""Captured dependency addresses are independent of the document's public URL."""

from urllib.parse import urljoin, urlsplit

import pytest
import tinycss2
from interact_support import PAGE
from leaf.revision_artifact import ArtifactError, Resource, capture_artifact
from leaf.revision_delivery import deliver_document, deliver_resource
from leaf.structure import SourceDocument

ROOT = "/p/reader/revisions/r1-0123456789abcdef"


def test_document_rewrites_only_resource_references_with_exact_source_spans():
    source = """<html><head><title>🍂 route ./page/app.js</title>
<script type="module" src=./page/app.js></script>
<script type="module">
const prose = 'import "./page/unused.js"';
const api = "/api/state";
import "./page/inline.js";
const lazy = () => import('/page/later.js');
</script>
<link rel=stylesheet href="page/style.css">
<style>main { background: url(./page/background.svg#leaf) }</style>
</head><body><main>
<p title="./page/app.js">A literal /page/app.js and &amp; spelling.</p>
<img src="./page/café.svg#leaf" alt='🍂 /page/café.svg'>
<img srcset="./page/café.svg 1x, /page/poster.png 2x" alt="Responsive leaf">
<video poster="/page/poster.png"></video>
<svg><image href="/page/café.svg#leaf"></image><filter><feImage href="/page/poster.png"></feImage></filter></svg>
<img src="data:image/svg+xml;base64,PHN2Zy8+" alt="Embedded">
<div style="background: url(&quot;./page/inline.svg&quot;); color: red">Text</div>
</main></body></html>""".replace("\n", "\r\n")

    delivered = deliver_document(source, ROOT)
    parsed = SourceDocument(delivered)

    assert parsed.external_scripts[0]["attrs"]["src"] == ROOT + "/page/app.js"
    assert parsed.links[0]["attrs"]["href"] == ROOT + "/page/style.css"
    assert f'import "{ROOT}/page/inline.js";' in delivered
    assert f'import("{ROOT}/page/later.js")' in delivered
    assert parsed.tree.find("img").attrs["src"] == ROOT + "/page/caf%C3%A9.svg#leaf"
    assert (
        parsed.tree.find_all("img")[1].attrs["srcset"]
        == f"{ROOT}/page/caf%C3%A9.svg 1x, {ROOT}/page/poster.png 2x"
    )
    assert parsed.tree.find("video").attrs["poster"] == ROOT + "/page/poster.png"
    assert parsed.tree.find("image").attrs["href"] == ROOT + "/page/caf%C3%A9.svg#leaf"
    assert parsed.tree.find("feImage").attrs["href"] == ROOT + "/page/poster.png"
    assert f"{ROOT}/page/background.svg#leaf" in parsed.css
    assert ROOT + "/page/inline.svg" in parsed.inline_styles[0]
    for unchanged in (
        "<title>🍂 route ./page/app.js</title>",
        "const prose = 'import \"./page/unused.js\"';",
        'const api = "/api/state";',
        '<p title="./page/app.js">A literal /page/app.js and &amp; spelling.</p>',
        "alt='🍂 /page/café.svg'",
        '<img src="data:image/svg+xml;base64,PHN2Zy8+" alt="Embedded">',
    ):
        assert unchanged in delivered


def test_stylesheets_rebase_nested_imports_urls_and_preserve_inert_values():
    source = """/* url(../not-an-asset.png) */
@import "./theme.css" layer(palette);
@import url('../shared.css') screen;
@media screen { .leaf {
  background-image: url(../images/leaf.svg#shape);
  mask-image: url("/page/mask.svg#mask");
  cursor: url(../images/a%23b.svg), auto;
  border-image-source: url("../images/\\6c eaf.svg#escaped");
  filter: url(#local);
  content: "url(../not-an-asset.png)";
  --embedded: url("data:image/svg+xml;base64,PHN2Zy8+");
} }
"""
    delivered = deliver_resource(
        Resource(source.encode(), "text/css"), "/page/styles/main.css", ROOT
    ).decode()

    assert f'@import "{ROOT}/page/styles/theme.css" layer(palette);' in delivered
    assert f'url("{ROOT}/page/shared.css") screen;' in delivered
    assert f'url("{ROOT}/page/images/leaf.svg#shape")' in delivered
    assert f'url("{ROOT}/page/mask.svg#mask")' in delivered
    assert f'url("{ROOT}/page/images/a%23b.svg")' in delivered
    assert f'url("{ROOT}/page/images/leaf.svg#escaped")' in delivered
    assert "filter: url(#local)" in delivered
    assert 'content: "url(../not-an-asset.png)";' in delivered
    assert 'url("data:image/svg+xml;base64,PHN2Zy8+")' in delivered
    assert "/* url(../not-an-asset.png) */" in delivered
    assert not any(
        token.type == "error" for token in tinycss2.parse_stylesheet(delivered)
    )


def test_page_widget_alias_uses_its_captured_path_for_import_resolution():
    source = b"""import { local } from "../helper.js";
import { offer } from "/runtime/widget-api.js";
export { value } from "./value.js";
const plain = "../helper.js";
"""
    delivered = deliver_resource(
        Resource(source, "application/javascript"), "/page/widgets/lf-local.js", ROOT
    )
    assert delivered == source.replace(
        b'from "../helper.js"', f'from "{ROOT}/page/helper.js"'.encode()
    ).replace(
        b'from "/runtime/widget-api.js"',
        f'from "{ROOT}/runtime/widget-api.js"'.encode(),
    ).replace(b'from "./value.js"', f'from "{ROOT}/page/widgets/value.js"'.encode())
    for resource, path in (
        (Resource(b"\x00\xff", "image/png"), "/page/image.png"),
        (
            Resource(b'fetch("/api/state")', "application/javascript"),
            "/runtime/state.js",
        ),
    ):
        assert deliver_resource(resource, path, ROOT) == resource.data


def test_captured_document_entries_resolve_at_every_public_address(tmp_path):
    authored = tmp_path / "page"
    authored.mkdir()
    (authored / "app.js").write_text('import "./helper.js";')
    (authored / "helper.js").write_text('document.body.dataset.helper = "ready";')
    (authored / "style.css").write_text(
        'main { background-image: url("./image.svg"); }'
    )
    (authored / "image.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    (authored / "image-2.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    source = PAGE.replace(
        "</head>",
        '<script type="module" src="./page/app.js"></script>'
        '<link rel="stylesheet" href="page/style.css"></head>',
    ).replace(
        "</main>",
        '<svg><image href="./page/image.svg"></image></svg>'
        '<img srcset="./page/image.svg 1x, ./page/image-2.svg 2x" '
        'alt="Leaf"></main>',
    )
    artifact = capture_artifact(tmp_path, SourceDocument(source), {})
    delivered = SourceDocument(deliver_document(source, ROOT))
    entries = [
        delivered.external_scripts[0]["attrs"]["src"],
        delivered.links[0]["attrs"]["href"],
        delivered.tree.find("image").attrs["href"],
        *(
            candidate.split()[0]
            for candidate in delivered.tree.find("img").attrs["srcset"].split(",")
        ),
    ]
    for address in ("/p/reader/", "/p/reader/versions/v1.html", ROOT + ".html"):
        for entry in entries:
            request = urlsplit(urljoin("https://leaf.example" + address, entry)).path
            assert request.startswith(ROOT + "/")
            logical = request.removeprefix(ROOT)
            assert logical in artifact.resources
            assert deliver_resource(artifact.resources[logical], logical, ROOT)


def test_capture_refuses_a_missing_svg_resource(tmp_path):
    source = PAGE.replace(
        "</main>",
        '<svg><image href="/page/missing.svg"></image></svg></main>',
    )

    with pytest.raises(
        ArtifactError, match=r"/page/missing\.svg: cannot capture dependency"
    ):
        capture_artifact(tmp_path, SourceDocument(source), {})
