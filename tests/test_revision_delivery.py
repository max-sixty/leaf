"""Captured dependency addresses are independent of the document's public URL."""

import json
from urllib.parse import urljoin, urlsplit

import pytest
import tinycss2
from interact_support import PAGE
from leaf.exporting import inline_assets, inline_css_assets
from leaf.http import scope_page_urls
from leaf.revision_artifact import ArtifactError, Resource, capture_artifact
from leaf.revision_delivery import (
    DeliveryAddress,
    deliver_resource,
    json_script,
    rebase_document,
)
from leaf.structure import SourceDocument

PAGE_ROOT = "/p/user"
ROOT = PAGE_ROOT + "/revisions/r1-0123456789abcdef"
ADDRESS = DeliveryAddress(PAGE_ROOT, ROOT)


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

    delivered = rebase_document(source, ADDRESS)
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
    assert ROOT + "/page/inline.svg" in parsed.inline_styles[0]["style"]
    for unchanged in (
        "<title>🍂 route ./page/app.js</title>",
        "const prose = 'import \"./page/unused.js\"';",
        'const api = "/api/state";',
        '<p title="./page/app.js">A literal /page/app.js and &amp; spelling.</p>',
        "alt='🍂 /page/café.svg'",
        '<img src="data:image/svg+xml;base64,PHN2Zy8+" alt="Embedded">',
    ):
        assert unchanged in delivered


def test_stylesheet_rel_is_case_insensitive_in_delivery_and_export():
    source = (
        '<html><head><link rel="StyleSheet" href="/page/style.css"></head>'
        "<body><main></main></body></html>"
    )

    delivered = SourceDocument(rebase_document(source, ADDRESS))
    assert delivered.links[0]["attrs"]["href"] == ROOT + "/page/style.css"

    exported = inline_assets(
        source,
        read_resource=lambda url: Resource(b"main { color: green; }", "text/css"),
    )
    assert "<link" not in exported
    assert "<style>" in exported
    assert "main { color: green; }" in exported


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
        Resource(source.encode(), "text/css"), "/page/styles/main.css", ADDRESS
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


def test_capture_delivery_and_export_read_one_set_of_stylesheet_urls(tmp_path):
    """Capture decides which files a stylesheet needs, delivery re-addresses them, and
    export embeds them, so all three have to find the same URLs in one sheet: a URL
    only capture finds is a file nobody serves, and one only export finds is a file
    capture never kept. An `@import` nested in a block is none of them in either
    spelling, because a browser ignores it."""
    sheet = """@import "./base.css";
@supports (display: grid) { @import "./ignored.css"; @import url(./ignored.css); }
main { background: image-set("./a.png" 1x, url(./b.png) 2x); }
@font-face { src: url(/page/f.woff2) format("woff2"); }
"""
    authored = tmp_path / "page"
    authored.mkdir()
    (authored / "style.css").write_text(sheet)
    for name in ("base.css", "ignored.css", "a.png", "b.png", "f.woff2"):
        (authored / name).write_text("")
    source = PAGE.replace(
        "</head>", '<link rel="stylesheet" href="page/style.css"></head>'
    )
    expected = {"/page/base.css", "/page/a.png", "/page/b.png", "/page/f.woff2"}

    artifact = capture_artifact(tmp_path, SourceDocument(source), {})
    captured = artifact.resources["/page/style.css"]
    assert set(captured.dependencies) == expected
    assert "/page/ignored.css" not in artifact.resources

    delivered = deliver_resource(captured, "/page/style.css", ADDRESS).decode()
    assert {path for path in expected if f'"{ROOT}{path}"' in delivered} == expected
    assert '@import "./ignored.css"; @import url(./ignored.css);' in delivered

    read = []

    def reader(url):
        read.append(url)
        return artifact.resources[url]

    inline_css_assets(sheet, read_resource=reader, document_url="/page/style.css")
    assert set(read) == expected


def test_page_widget_alias_uses_its_captured_path_for_import_resolution():
    source = b"""import { local } from "../helper.js";
import { offer } from "/runtime/widget-api.js";
export { value } from "./value.js";
const plain = "../helper.js";
"""
    delivered = deliver_resource(
        Resource(source, "application/javascript"),
        "/page/widgets/lf-local.js",
        ADDRESS,
    )
    assert delivered == source.replace(
        b'from "../helper.js"', f'from "{ROOT}/page/helper.js"'.encode()
    ).replace(
        b'from "/runtime/widget-api.js"',
        f'from "{ROOT}/runtime/widget-api.js"'.encode(),
    ).replace(b'from "./value.js"', f'from "{ROOT}/page/widgets/value.js"'.encode())
    # A layer module keeps its captured bytes, since the document's import map
    # addresses its rooted imports; a layer stylesheet's URLs are the revision's.
    for resource, path in (
        (Resource(b"\x00\xff", "image/png"), "/page/image.png"),
        (
            Resource(
                b'import { a } from "/runtime/a.js"; fetch("/api/state")',
                "application/javascript",
            ),
            "/runtime/state.js",
        ),
    ):
        assert deliver_resource(resource, path, ADDRESS) == resource.data
    assert (
        deliver_resource(
            Resource(b'.mark { mask: url("/icon.svg") }', "text/css"),
            "/runtime/chrome.css",
            ADDRESS,
        )
        == f'.mark {{ mask: url("{ROOT}/icon.svg") }}'.encode()
    )


def test_media_has_one_address_wherever_a_page_names_it(tmp_path):
    """Media is the page's and shared across revisions, so every host serves it at the
    page root, and the runtime resolves a message's or a widget's media there too. A
    captured document addresses it there in every form capture reads: a resource
    attribute, any attribute naming it whole, a stylesheet, a declarative shadow root,
    and frozen message markup in a state reading. Prose naming it stays as written."""
    media = "/media/0123456789abcdef.png"
    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "0123456789abcdef.png").write_bytes(b"\x89PNG")
    source = PAGE.replace(
        "</head>", f"<style>main {{ background: url({media}) }}</style></head>"
    ).replace(
        "</main>",
        f'<p><a href="{media}">The shot</a> is at {media}.</p>'
        f'<img src="{media}" alt="Shot">'
        f'<div style="background: url({media})"></div>'
        f'<lf-shot before="{media}" after="{media}"></lf-shot>'
        f'<div><template shadowrootmode="open"><img src="{media}" alt="Shot">'
        "</template></div></main>",
    )

    assert media in capture_artifact(tmp_path, SourceDocument(source), {}).entries
    delivered = rebase_document(source, ADDRESS)
    assert delivered.replace(PAGE_ROOT + media, "").count(media) == 1  # the prose
    assert delivered.count(PAGE_ROOT + media) == 7
    markup = scope_page_urls(
        {"markup": f'<p><img src="{media}" alt="Shot"></p>'}, PAGE_ROOT
    )
    assert markup["markup"] == f'<p><img src="{PAGE_ROOT}{media}" alt="Shot"></p>'


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
    delivered = SourceDocument(rebase_document(source, ADDRESS))
    entries = [
        delivered.external_scripts[0]["attrs"]["src"],
        delivered.links[0]["attrs"]["href"],
        delivered.tree.find("image").attrs["href"],
        *(
            candidate.split()[0]
            for candidate in delivered.tree.find("img").attrs["srcset"].split(",")
        ),
    ]
    for address in ("/p/user/", "/p/user/versions/v1.html", ROOT + ".html"):
        for entry in entries:
            request = urlsplit(urljoin("https://leaf.example" + address, entry)).path
            assert request.startswith(ROOT + "/")
            logical = request.removeprefix(ROOT)
            assert logical in artifact.resources
            assert deliver_resource(artifact.resources[logical], logical, ADDRESS)


def test_capture_refuses_a_missing_svg_resource(tmp_path):
    source = PAGE.replace(
        "</main>",
        '<svg><image href="/page/missing.svg"></image></svg></main>',
    )

    with pytest.raises(
        ArtifactError, match=r"/page/missing\.svg: cannot capture dependency"
    ):
        capture_artifact(tmp_path, SourceDocument(source), {})


def test_inert_json_cannot_end_or_reshape_its_script_element():
    """A user's own words travel inside a script element, and two sequences escape it.

    `</script` closes the element; `<!--` opens a comment the parser reads the rest of
    the document inside, and an exported page carrying one in a comment lost everything
    after it. No `<` survives serialization, and the text parses back exactly."""
    hostile = "</script><!--<script>alert(1)</script>"

    serialized = json_script({"said": hostile})

    assert "<" not in serialized
    assert json.loads(serialized)["said"] == hostile
