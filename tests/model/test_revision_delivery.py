"""Captured dependency addresses are independent of the document's public URL."""

import json
import struct
from urllib.parse import urljoin, urlsplit

import pytest
import tinycss2
from interact_support import PAGE

from leaf import revisioning as revisioning_model
from leaf.exporting import AssetInliner, ReadableAssets
from leaf.files import revision_path
from leaf.http import scope_page_urls
from leaf.revision_artifact import (
    ArtifactError,
    Resource,
    capture_artifact,
    capture_local_resource,
    read_artifact,
    resource_dependencies,
    rewrite_css,
)
from leaf.revision_delivery import (
    Delivery,
    DeliveryAddress,
    compose_document,
    deliver_resource,
    json_script,
    mark_declared,
    rebase_document,
)
from leaf.runtime_selection import executing
from leaf.schema import ASSETS
from leaf.structure import SourceDocument

PAGE_ROOT = "/p/user"
ROOT = PAGE_ROOT + "/revisions/r1-0123456789abcdef"
ADDRESS = DeliveryAddress(PAGE_ROOT, ROOT)


def test_declared_markdown_body_is_delivered_formatted_with_exact_source_retained():
    source = '<lf-editable id="note"><pre>**Keep** `--dry-run`.\n\n- One\n- Two</pre></lf-editable>'
    marked = mark_declared(source, {"lf-editable": {"x-text-format": "markdown"}}, {})
    document = SourceDocument(marked)
    [host] = document.tree.find_all("lf-editable")
    assert host.select_one("pre").text == "**Keep** `--dry-run`.\n\n- One\n- Two"
    body = host.select_one(".lf-markdown-body")
    assert body.select_one("strong").text == "Keep"
    assert body.select_one("code").text == "--dry-run"
    assert len(body.find_all("li")) == 2
    assert body.attrs["data-lf-source-words"] == host.select_one("pre").text
    assert "data-lf-prepaint" in body.attrs


def test_delivered_markdown_refuses_unsafe_links_and_images_before_runtime_loads():
    source = '<lf-editable id="note"><pre>[unsafe link](javascript:alert(1)) ![unsafe image](data:text/html,boom) [safe link](https://example.com)</pre></lf-editable>'
    delivered = mark_declared(
        source, {"lf-editable": {"x-text-format": "markdown"}}, {}
    )
    body = SourceDocument(delivered).tree.select_one(".lf-markdown-body")
    assert [link.attrs["href"] for link in body.find_all("a")] == [
        "https://example.com"
    ]
    assert not body.find_all("img")
    assert body.text.strip() == "unsafe link unsafe image safe link"


@pytest.mark.parametrize(
    "inliner_type,depth", [(AssetInliner, 1200), (ReadableAssets, 3)]
)
def test_export_walks_css_imports_without_recursion_and_retains_their_meaning(
    inliner_type, depth
):
    """Object-URL graphs can exceed Python's stack; readable data URLs are nested.

    Both walks retain namespaces and import conditions, suppress only the cyclic
    edge, and read shared resources once. The data-URL case stays shallow because
    each parent base64-encodes its child, expanding the result with every level.
    """
    import base64
    from collections import Counter

    resources = {
        f"/page/{index}.css": Resource(
            (
                f'@import "./{(index + 1) % depth}.css" '
                "layer(order) supports(display: grid) screen;\n"
                '@namespace svg "http://www.w3.org/2000/svg";\n'
                f".sheet-{index} {{ color: red; background-image: url('./badge.svg#mark'); }}"
            ).encode(),
            "text/css",
        )
        for index in range(depth)
    }
    resources["/page/badge.svg"] = Resource(b"<svg/>", "image/svg+xml")
    reads = Counter()

    def read(path):
        reads[path] += 1
        return resources[path]

    inliner = inliner_type(read)
    css = inliner.stylesheet("/page/0.css")
    for index in range(depth):
        assert f".sheet-{index}" in css
        assert "layer(order) supports(display: grid) screen;" in css
        assert '@namespace svg "http://www.w3.org/2000/svg";' in css
        assert "color: red;" in css
        if inliner_type is AssetInliner:
            assert "#mark" in css
        else:
            assert "background-image" not in css
        imported = next(
            rule
            for rule in tinycss2.parse_stylesheet(css)
            if rule.type == "at-rule" and rule.lower_at_keyword == "import"
        )
        address = next(
            token.value for token in imported.prelude if token.type == "string"
        )
        css = (
            inliner.embedded[address].data.decode()
            if inliner_type is AssetInliner
            else base64.b64decode(address.partition(",")[2]).decode()
        )
    assert css == ""
    assert reads == Counter({path: 1 for path in resources})


def test_initial_producers_are_captured_once_and_called_after_each_complete_host():
    source = (
        "<html><head><title>Initial</title></head><body><main>"
        '<lf-early id="first"><p>First</p></lf-early>'
        '<lf-early id="second"><p>Second</p></lf-early>'
        "<template><lf-unused></lf-unused></template>"
        "</main></body></html>"
    )
    registry = {
        "lf-early": {"x-initial": "/vendor/early.js"},
        "lf-unused": {"x-initial": "/vendor/unused.js"},
    }
    resources = {
        "/runtime/prepaint.js": Resource(
            b'window.prepaint = "</script>";', "application/javascript"
        ),
        "/vendor/lit-initial.js": Resource(
            b"window.lit = true;", "application/javascript"
        ),
        "/vendor/early.js": Resource(
            b'window.initial = "</script>";', "application/javascript"
        ),
        "/runtime/annotation-overlay/annotation-theme.css": Resource(b"", "text/css"),
        "/runtime/chrome.css": Resource(b"", "text/css"),
        "/runtime/marks.css": Resource(b"", "text/css"),
        "/runtime/annotation-overlay/annotation-chrome.css": Resource(b"", "text/css"),
        "/runtime/annotation-overlay/annotation-marks.css": Resource(b"", "text/css"),
    }
    delivered = compose_document(
        source,
        1,
        None,
        executable="sha256:fixture",
        resources=resources,
        registry=registry,
        delivery=Delivery(
            address=ADDRESS,
            import_map={"imports": {"/vendor/": ADDRESS("/vendor/")}},
            runtime="<script data-lf-runtime>window.boot = true;</script>",
        ),
    )
    parsed = SourceDocument(delivered.removeprefix("\ufeff"))
    scripts = parsed.tree.find_all("script")
    calls = [script for script in scripts if "lfInitial.mount" in script.text]
    assert len(calls) == 2
    assert [script.previous_sibling.tag for script in calls[:2]] == [
        "lf-early",
        "lf-early",
    ]
    assert delivered.count("<lf-early data-lf-arriving") == 2
    assert delivered.count('window.initial = "<\\/script>";') == 1
    assert delivered.count('window.prepaint = "<\\/script>";') == 1
    assert (
        delivered.index("window.prepaint")
        < delivered.index("window.initial")
        < delivered.index("window.boot")
    )
    import_map = json.loads(parsed.tree.select_one('script[type="importmap"]').text)[
        "imports"
    ]
    assert (
        delivered.index("window.prepaint")
        < delivered.index("window.lit =")
        < delivered.index("window.initial")
    )
    assert import_map["/vendor/lit.js"] == ADDRESS("/vendor/lit-shared.js")
    assert import_map[ADDRESS("/vendor/lit.js")] == ADDRESS("/vendor/lit-shared.js")
    assert mark_declared(source, registry, resources) == source


def test_capture_refuses_a_declared_initial_producer_that_is_absent(tmp_path):
    with pytest.raises(ArtifactError) as refused:
        capture_artifact(
            tmp_path,
            SourceDocument(PAGE),
            {"lf-early": {"x-initial": "/page/early.js"}},
        )
    [finding] = refused.value.findings
    assert (finding.code, finding.values["file"]) == (
        "dependency-unreadable",
        "/page/early.js",
    )


def test_capture_follows_deep_and_cyclic_dependencies_once(tmp_path):
    """A complete authored graph does not depend on Python's recursion limit."""
    directory = tmp_path / "page"
    directory.mkdir()
    depth = 1200
    for index in range(depth):
        target = index + 1 if index + 1 < depth else 0
        (directory / f"{index}.js").write_text(
            f'import "./{target}.js"; import "./shared.js";', encoding="utf-8"
        )
    (directory / "shared.js").write_text("export const shared = true;")
    (directory / "first.css").write_text('@import "./second.css";')
    (directory / "second.css").write_text('@import "./first.css";')
    source = PAGE.replace(
        "</head>",
        '<script type="module" src="/page/0.js"></script>'
        '<link rel="stylesheet" href="/page/first.css"></head>',
    )
    reads = []

    def read_resource(path):
        reads.append(path)
        return capture_local_resource(tmp_path, path)

    artifact = capture_artifact(
        tmp_path, SourceDocument(source), {}, read_resource=read_resource
    )

    expected = {f"/page/{index}.js" for index in range(depth)} | {
        "/page/shared.js",
        "/page/first.css",
        "/page/second.css",
    }
    assert set(reads) == expected
    assert len(reads) == len(expected)
    assert expected <= artifact.resources.keys()


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

    assert parsed.authoring.external_scripts[0]["attrs"]["src"] == ROOT + "/page/app.js"
    assert parsed.authoring.links[0]["attrs"]["href"] == ROOT + "/page/style.css"
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
    assert f"{ROOT}/page/background.svg#leaf" in parsed.authoring.style_blocks[0]["css"]
    assert ROOT + "/page/inline.svg" in parsed.authoring.inline_styles[0]["style"]
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
        '<html><head><link rel="StyleSheet" media="screen" href="/page/style.css"></head>'
        "<body><main></main></body></html>"
    )

    delivered = SourceDocument(rebase_document(source, ADDRESS))
    assert delivered.authoring.links[0]["attrs"]["href"] == ROOT + "/page/style.css"

    embedded = AssetInliner(lambda url: Resource(b"main { color: green; }", "text/css"))
    exported = rebase_document(
        source, embedded.address, inline_stylesheet=embedded.stylesheet
    )
    assert "<link" not in exported
    assert SourceDocument(exported).tree.find("style").attrs["media"] == "screen"
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
  background-image: image-set(url(../images/1x.png) 1x, "../images/2x.png" 2x);
} }
"""
    delivered = deliver_resource(
        Resource(source.encode(), "text/css"), "/page/styles/main.css", ADDRESS
    ).data.decode()

    assert f'@import "{ROOT}/page/styles/theme.css" layer(palette);' in delivered
    assert f'url("{ROOT}/page/shared.css") screen;' in delivered
    assert f'url("{ROOT}/page/images/leaf.svg#shape")' in delivered
    assert f'url("{ROOT}/page/mask.svg#mask")' in delivered
    assert f'url("{ROOT}/page/images/a%23b.svg")' in delivered
    assert f'url("{ROOT}/page/images/leaf.svg#escaped")' in delivered
    assert "filter: url(#local)" in delivered
    assert 'content: "url(../not-an-asset.png)";' in delivered
    assert 'url("data:image/svg+xml;base64,PHN2Zy8+")' in delivered
    assert (
        f'image-set(url("{ROOT}/page/images/1x.png") 1x, '
        f'"{ROOT}/page/images/2x.png" 2x)'
    ) in delivered
    assert "/* url(../not-an-asset.png) */" in delivered
    assert not any(
        token.type == "error" for token in tinycss2.parse_stylesheet(delivered)
    )


def test_an_unavailable_url_drops_its_declaration_beside_one_the_browser_drops():
    """A sheet the capture accepts may hold a declaration the browser ignores; omitting
    an unavailable URL beside it keeps the rest of the rule instead of failing."""
    rewritten = rewrite_css(
        'main { broken; background: url("x.png"); color: red }', lambda url: None
    )

    assert "color: red" in rewritten
    assert "x.png" not in rewritten


def test_capture_delivery_and_export_read_one_set_of_stylesheet_urls(tmp_path):
    """Capture decides which files a stylesheet needs, delivery re-addresses them, and
    export embeds them, so all three have to find the same URLs in one sheet: a URL
    only capture finds is a file capture refuses to be missing though nothing loads
    it, and one only delivery or export finds is a file nobody checked. An `@import`
    nested in a block is none of them in either spelling, because a browser ignores
    it."""
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
    assert (
        set(resource_dependencies("/page/style.css", captured.data, captured.mime))
        == expected
    )

    delivered = deliver_resource(captured, "/page/style.css", ADDRESS).data.decode()
    assert {path for path in expected if f'"{ROOT}{path}"' in delivered} == expected
    assert '@import "./ignored.css"; @import url(./ignored.css);' in delivered

    read = []

    def reader(url):
        read.append(url)
        return artifact.resources[url]

    AssetInliner(reader).css(sheet, "/page/style.css")
    assert set(read) == expected


def test_a_revision_shares_the_files_it_captured_unchanged(page_dir):
    """A new revision links each resource the one before it captured with the same
    bytes, and writes the ones that changed."""
    sheet = page_dir / "page" / "style.css"
    sheet.parent.mkdir(exist_ok=True)
    source = PAGE.replace(
        "</head>", '<link rel="stylesheet" href="page/style.css"></head>'
    )

    def activate(text, css):
        sheet.write_text(css)
        (page_dir / "index.html").write_text(source.replace("Ship dark.", text))
        activated = revisioning_model.activate_source(page_dir)
        assert activated.error is None, activated.error
        bundle = revision_path(page_dir, activated.revision).with_suffix("")
        manifest = json.loads((bundle / "manifest.json").read_bytes())
        return {
            logical: bundle / ("resources" + logical)
            for logical in manifest["resources"]
        }

    first = activate("Ship dark.", "main { color: red; }")
    second = activate("Ship it dark.", "main { color: blue; }")

    changed = {"/page/style.css"}
    assert changed < set(first) and set(first) == set(second)
    shared = {p for p in first if first[p].stat().st_ino == second[p].stat().st_ino}
    assert shared == set(first) - changed
    assert second["/page/style.css"].read_text() == "main { color: blue; }"
    assert first["/page/style.css"].read_text() == "main { color: red; }"


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
    ).data
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
        assert deliver_resource(resource, path, ADDRESS) is resource
    assert (
        deliver_resource(
            Resource(b'.mark { mask: url("/icon.svg") }', "text/css"),
            "/runtime/chrome.css",
            ADDRESS,
        ).data
        == f'.mark {{ mask: url("{ROOT}/icon.svg") }}'.encode()
    )


def test_authored_lazy_positioning_import_uses_the_runtimes_public_provider(page_dir):
    """An authored import names the public provider, which the revision does not
    capture: the Leaf delivering it supplies the provider with its runtime."""
    provider = "/vendor/floating-ui.esm.js"
    module = f'export const position = () => import("{provider}");'
    (page_dir / "page" / "position.js").write_text(module)
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</head>",
            '<script type="module" src="/page/position.js"></script></head>',
        )
    )
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None, activated.error
    artifact = read_artifact(page_dir, activated.revision)
    resource = artifact.resources["/page/position.js"]
    assert provider in json.loads(artifact.manifest)["public_modules"]
    assert provider not in artifact.resources
    assert (
        executing(artifact).resources[provider].data
        == (ASSETS / provider[1:]).read_bytes()
    )
    assert deliver_resource(
        resource, "/page/position.js", ADDRESS
    ).data.decode() == module.replace(provider, ROOT + provider)


def test_a_vendored_replacement_of_a_public_provider_is_captured_and_served(page_dir):
    """A package may replace a public vendor module, and the page then runs its own:
    the revision captures the vendored file, which wins over the runtime's."""
    provider = "/vendor/floating-ui.esm.js"
    own = b"export const computePosition = () => 'the package\\'s own';"
    (page_dir / provider[1:]).write_bytes(own)
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None, activated.error
    artifact = read_artifact(page_dir, activated.revision)
    assert artifact.resources[provider].data == own
    assert executing(artifact).resources[provider].data == own


def test_an_export_runs_the_exporters_runtime(page_dir, monkeypatch):
    """An export pairs the state the exporting Leaf reads with that Leaf's runtime,
    whichever Leaf captured the version, since only that runtime reads that state."""
    from click.testing import CliRunner

    from leaf import cli as cli_model
    from leaf import runtime_selection
    from leaf.exporting import cmd_export

    stamped = CliRunner().invoke(
        cli_model.cli, ["page", "stamp", str(page_dir), "--text", "Exported"]
    )
    assert stamped.exit_code == 0, stamped.output
    current = runtime_selection.read_runtime()
    marker = b"/* the exporting Leaf's runtime */"
    exporter = runtime_selection.ServingRuntime(
        {
            **current.source,
            "/runtime/prepaint.js": current.source["/runtime/prepaint.js"] + marker,
        },
        None,
        frozenset(),
        current.probes,
    )
    monkeypatch.setattr(runtime_selection, "serving_runtime", lambda: exporter)

    out = page_dir.parent / "export.html"
    cmd_export(page_dir, out, 1)

    assert marker.decode() in out.read_text()


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
        delivered.authoring.external_scripts[0]["attrs"]["src"],
        delivered.authoring.links[0]["attrs"]["href"],
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

    with pytest.raises(ArtifactError) as refused:
        capture_artifact(tmp_path, SourceDocument(source), {})
    [finding] = refused.value.findings
    assert (finding.code, finding.values["file"]) == (
        "dependency-unreadable",
        "/page/missing.svg",
    )


def test_inert_json_cannot_end_or_reshape_its_script_element():
    """A user's own words travel inside a script element, and two sequences escape it.

    `</script` closes the element; `<!--` opens a comment the parser reads the rest of
    the document inside, and an exported page carrying one in a comment lost everything
    after it. No `<` survives serialization, and the text parses back exactly."""
    hostile = "</script><!--<script>alert(1)</script>"

    serialized = json_script({"said": hostile})

    assert "<" not in serialized
    assert json.loads(serialized)["said"] == hostile


@pytest.mark.parametrize("explicit_html", [True, False])
def test_a_host_marks_the_delivered_document_where_it_asks(explicit_html):
    """A host's marks land on the document's own wrapper tags, whether or not the
    source spells `<html>`, while the rest of the source stays as written."""
    source = (
        '<!doctype html><html lang="en"><head><title>T</title></head>'
        '<body><main><script type="module">window.ran = 1;</script>'
        "<p>Text.</p></main></body></html>"
    )
    if not explicit_html:
        source = source.replace('<html lang="en">', "").replace("</html>", "")
    delivered = compose_document(
        source,
        1,
        None,
        executable="sha256:fixture",
        resources={},
        registry={},
        delivery=Delivery(
            address=ADDRESS,
            import_map={"imports": {"/runtime/": ROOT + "/runtime/"}},
            page_root=PAGE_ROOT,
            html_attributes={"data-lf-contained": ""},
            body_attributes={"inert": ""},
        ),
    )

    assert delivered.startswith("﻿<!doctype html>")
    served = SourceDocument(delivered.removeprefix("﻿"))
    assert "data-lf-contained" in served.tree.find("html").attrs
    assert "inert" in served.tree.find("body").attrs
    assert served.authoring.title == "T" and "<p>Text.</p>" in delivered


def test_a_delivered_document_carries_its_declared_marks_in_the_source():
    """The theme and the workspace Layout read what an element's registry entry
    declares, and a stylesheet cannot read the registry, so the document arrives with
    each declaration painted on the element: the first paint lays out a board's room and
    a package's pane before any script runs. An occurrence's own `data-width`,
    `data-bound` or `data-height` says it for that occurrence. An element naming page
    media carries the box that holds all of it, read from the images, so a frame stands
    in their shape before they decode. A mark is its tag's, so a selector idiom declares
    none. Markup inside a template is inert, and everything else in the source stays
    as written."""

    def png(width, height):
        return Resource(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + struct.pack(">II", width, height),
            "image/png",
        )

    registry = {
        "lf-zone": {"x-reading-role": "pane"},
        "lf-board": {"x-space": "wide"},
        "lf-label": {"x-inline": True},
        "lf-feed": {"x-bound": "end"},
        "lf-plot": {"x-height": 400},
        "table": {"description": "A table.", "x-example": "<table></table>"},
    }
    source = (
        "<!doctype html><html><head><title>T</title></head><body><main>"
        '<aside class="callout warn" id="note">Paused.</aside>'
        '<aside class="callout" id="chart-note" data-width="wide">Chart.</aside>'
        '<lf-zone id="queue" label="Queue"><div><lf-label>new</lf-label></div></lf-zone>'
        '<lf-board id="board" data-width="available"></lf-board>'
        '<lf-feed id="feed" class="selected"></lf-feed><section id="wide" data-width="wide"></section>'
        '<table id="native"></table>'
        '<pre data-bound="start">log</pre>'
        '<lf-plot id="plot"></lf-plot><lf-plot id="tall" data-height="240"></lf-plot>'
        '<lf-pair id="pair" before="/media/a.png" after="/media/b.png"></lf-pair>'
        "<template><lf-zone id=later label=Later><p>x</p></lf-zone></template>"
        "</main></body></html>"
    )
    delivered = compose_document(
        source,
        1,
        None,
        executable="sha256:fixture",
        resources={"/media/a.png": png(1200, 750), "/media/b.png": png(1100, 800)},
        registry=registry,
        delivery=Delivery(address=ADDRESS),
    )

    served = SourceDocument(delivered.removeprefix("﻿"))
    marks = {
        (element.tag, element.attrs.get("id")): {
            name: value
            for name, value in element.attrs.items()
            if name.startswith("data-lf-")
        }
        for element in served.tree.find("main").find_all(True)
    }
    assert marks[("lf-zone", "queue")] == {"data-lf-reading-role": "pane"}
    assert marks[("lf-label", None)] == {"data-lf-inline": ""}
    assert marks[("lf-board", "board")] == {"data-lf-space": "available"}
    assert marks[("aside", "note")] == {}
    assert marks[("aside", "chart-note")] == {"data-lf-space": "wide"}
    assert marks[("lf-feed", "feed")] == {"data-lf-bound": "end"}
    assert marks[("table", "native")] == {}
    assert marks[("section", "wide")] == {"data-lf-space": "wide"}
    assert marks[("pre", None)] == {"data-lf-bound": "start"}
    assert marks[("lf-plot", "plot")] == {"data-lf-height": "400"}
    assert marks[("lf-plot", "tall")] == {"data-lf-height": "240"}
    assert marks[("lf-pair", "pair")] == {
        "data-lf-media-width": "1200",
        "data-lf-media-height": "800",
    }
    assert marks[("lf-zone", "later")] == {}
    for mark in (
        ' data-lf-space="wide"',
        ' data-lf-reading-role="pane"',
        ' data-lf-inline=""',
        ' data-lf-space="available"',
        ' data-lf-bound="end"',
        ' data-lf-space="wide"',
        ' data-lf-bound="start"',
        ' data-lf-height="400"',
        ' data-lf-height="240"',
        ' data-lf-media-width="1200" data-lf-media-height="800"',
    ):
        delivered = delivered.replace(mark, "", 1)
    # Media is addressed at the page root, which is the rebase's change rather than a mark.
    delivered = delivered.replace(f"{PAGE_ROOT}/media/", "/media/")
    assert (
        source.removeprefix("<!doctype html><html><head>").split("</head>")[1]
        in delivered
    )


def test_markdown_prepaint_has_task_checkboxes_bare_links_and_literal_html():
    from html import escape

    source = "- [x] Done\n- [ ] Todo\n\nhttps://example.com\n\n<div>\n**bold**\n</div>"
    delivered = mark_declared(
        f"<lf-editable><pre>{escape(source)}</pre></lf-editable>",
        {"lf-editable": {"x-text-format": "markdown"}},
        {},
    )
    body = SourceDocument(delivered).tree.select_one(".lf-markdown-body")
    checks = body.find_all("input")
    assert len(checks) == 2 and all("disabled" in check.attrs for check in checks)
    assert "checked" in checks[0].attrs and "checked" not in checks[1].attrs
    assert body.select_one("a").attrs["href"] == "https://example.com"
    assert body.select_one("strong").text == "bold"
    assert not body.find_all("div")


def test_source_fallback_marks_derive_from_open_registry_content_declarations():
    """A new data widget gets the same pre-upgrade reading primitive without a tag list."""
    source = '<lf-new-source id="source"><pre>raw source</pre></lf-new-source><lf-literal id="literal">literal source</lf-literal>'
    registry = {
        "lf-new-source": {"x-content": "data", "x-awaits": {"value": "choose"}},
        "lf-literal": {"x-content": "data", "x-verbatim": True},
    }
    delivered = mark_declared(source, registry, {})
    soup = SourceDocument(delivered).tree
    assert soup.find(id="source").attrs["data-lf-content"] == "data"
    assert soup.find(id="source").attrs["data-lf-awaits"] == ""
    assert "data-lf-awaits" not in soup.find(id="literal").attrs
    assert not "data-lf-verbatim" in soup.find(id="source").attrs
    assert soup.find(id="literal").attrs["data-lf-content"] == "data"
    assert "data-lf-verbatim" in soup.find(id="literal").attrs


def test_an_authored_override_holds_only_where_it_means_something():
    """A room or a bound sizes a block in the page's flow; on `main` or `body` it would
    size the page itself, a column that stops centring or a page held to one screen. A
    stated height reserves room for a module's drawing; on a table, which no module
    marks drawn, it would clip the words for good. Each override is inert there."""
    source = (
        '<body data-bound="end"><main class="layout-column" data-width="wide" '
        'data-bound="end">'
        '<lf-chart id="chart" data-height="240"></lf-chart>'
        '<table id="table" data-height="80" data-width="wide"><tr><td>A</td></tr>'
        '</table><ul id="feed" data-bound="end"><li>A</li></ul></main></body>'
    )
    delivered = mark_declared(source, {"lf-chart": {"x-height": 400}}, {})
    soup = SourceDocument(delivered).tree
    assert soup.find(id="chart").attrs["data-lf-height"] == "240"
    assert soup.find(id="table").attrs["data-lf-space"] == "wide"
    assert "data-lf-height" not in soup.find(id="table").attrs
    assert soup.find(id="feed").attrs["data-lf-bound"] == "end"
    for page in (soup.find("main"), soup.find("body")):
        assert not {"data-lf-space", "data-lf-bound"} & set(page.attrs), page.attrs


def test_exhibit_paint_follows_the_occurrence_condition():
    registry = {"lf-sample": {"x-exhibit": {"when": {"interactive": [False]}}}}
    source = '<lf-sample id="quote"></lf-sample><lf-sample id="working" interactive></lf-sample>'
    tree = SourceDocument(mark_declared(source, registry, {})).tree
    assert "data-lf-exhibit" in tree.find(id="quote").attrs
    assert "data-lf-exhibit" not in tree.find(id="working").attrs
