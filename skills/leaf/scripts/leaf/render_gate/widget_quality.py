"""Widget quality: how a package's own widgets behave on a page, told to their author.

A finding here is advice for whoever writes the widget. It refuses nothing: the widget
still renders, a page using it still passes its checks, and `package check --render`
exits as it would without it. It stays out of `page check --render` too, whose reader
is a page's author and cannot change a widget's internals (`readings.py`, header).

The report renders the package's worked examples (`x-example`) under the layer the
package appears in (`packages.package_layer_inputs`), and reads only the tags the
package's own `registry.json` declares. Examples share a page where their ids allow,
so an example that points at another's element finds it, and a page costs one render
however many examples it holds; the next page starts where an example's ids would
repeat one already on the page. Each page is read twice, once as a column document and
once in the pane of a full-height workspace (`WRAPPERS`), since a widget meets both and
what holds its height or its width differs between them; a finding names which one it
was read in (`layout`). A page is rendered as authored, without `page check`:
an example may point at data or an element a package cannot carry, and what the report
reads is the widget, not the page. A package carries no media either, so a blank
image stands in for each one an example names.

Each check has one name in `CHECKS`, which is the code of the finding
(`findings.Finding`) it reports, with the widget's tag in its values:

- `example`: each of the package's tags appears in some worked example, since a tag no
  example shows is one no other check reads.
- `keeps-first-box`: a widget paints its final box before it upgrades, so upgrade adds
  behavior and moves nothing (`../../../assets/AGENTS.md`, "Stability"). Its reading is
  `changedBoxes` in `render-checks/widgets.js`, against the box each authored widget had
  at first paint, which the pre-upgrade proof keeps (`scheme.start_with_pre_upgrade_proof`).
- `grows-with-content`: a box in the widget holds its own height and scrolls inside it,
  where a widget in ordinary flow grows with what it holds (`../../../assets/AGENTS.md`,
  "Space and scrolling"). A box that needs a scroll of its own says so with
  `--lf-holds-height: 1`, as a bounded block does. Its reading is `heldScrollers` in
  `render-checks/widgets.js`, which names a box that scrolls vertically now, or that
  asks to and overflows once a tall block is added to it. It writes the page, so it is
  taken after `changedBoxes`, last on the page.
- `shows-context-keys`: a command that declares context keys, the aliases a widget
  offers for pressing a control from elsewhere, also declares a `bindingBadge`, so the
  page shows the key it adds (`../../references/module-input.md`, "Commands and
  keyboard routes"). Its reading is `unshownContextKeys` in `render-checks/widgets.js`,
  which reads the declarations rather than the keys reachable now.
"""

import re
import struct
import tempfile
import zlib
from pathlib import Path

from leaf.findings import Finding, element_at
from leaf.layer import LayerComposition, checked_layer_inputs, compose_layer
from leaf.packages import package_layer_inputs
from leaf.registry.contract import element_declarations, read_registry_declarations
from leaf.registry.storage import read_page_registry
from leaf.render_checks import (
    RENDER_VIEWPORT,
    evaluate_probe,
    install_driver,
    wait_for_probe,
    wait_until_ready,
)
from leaf.revision_artifact import ArtifactError, capture_artifact
from leaf.schema import DIR_FILES, MEDIA_DIR
from leaf.structure import SourceDocument
from leaf.vendoring import start_throwaway_page

from .preview import preview_server
from .scheme import (
    answer_reports,
    arm_interception,
    collect_page_errors,
    served,
    start_with_pre_upgrade_proof,
)

CHECKS = ("example", "keeps-first-box", "grows-with-content", "shows-context-keys")

MEDIA_REFERENCE = re.compile(f"/{MEDIA_DIR}/{DIR_FILES[MEDIA_DIR]}")

# Where a page of examples stands: the `main` it opens and closes in, by the Layout a
# finding names.
WRAPPERS = {
    "column": ("<main class='layout-column'>", "</main>"),
    "workspace": (
        (
            "<main class='layout-workspace density-working'>"
            "<lf-pane id='worked-examples' label='Worked examples'><div>"
        ),
        "</div></lf-pane></main>",
    ),
}


def _finding(check: str, tag: str, id: str = "", **values) -> Finding:
    """One check's reading of one widget, named by its instance where the check read
    one."""
    return Finding(
        check, element_at(tag, id), {"tag": tag, **values}, severity="advice"
    )


class UnreadablePage(Exception):
    """A page of worked examples that could not be drawn and brought to
    presentation."""


def own_tags(package: Path) -> list[str]:
    """The widget tags the package's own `registry.json` declares, in its order."""
    declarations = read_registry_declarations(package / "registry.json") or {}
    return list(element_declarations(declarations))


def example_pages(registry: dict, tags: list[str]) -> list[tuple[str, str]]:
    """The worked examples of `tags`, gathered into as few pages as their ids allow,
    each page once in every Layout of `WRAPPERS`, with the Layout's name."""
    pages = []
    ids = set()
    for tag in tags:
        if (example := registry[tag].get("x-example")) is None:
            continue
        own = SourceDocument(example, fragment=True).ids
        if not pages or own & ids:
            pages.append([])
            ids = set()
        pages[-1].append(example)
        ids |= own
    return [
        (
            layout,
            "<!doctype html>\n<html lang='en'>\n<head><title>Worked examples</title>"
            f"</head>\n<body>\n{opening}\n"
            + "\n".join(examples)
            + f"\n{closing}\n</body>\n</html>\n",
        )
        for examples in pages
        for layout, (opening, closing) in WRAPPERS.items()
    ]


def _blank_image(suffix: str) -> bytes:
    """A plain 1200x750 image in the format `suffix` names: SVG for `.svg`, and PNG
    for any raster suffix, which a browser decodes by its bytes whatever it is
    named."""
    width, height = 1200, 750
    if suffix == ".svg":
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}"/>'
        ).encode()

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    rows = (b"\x00" + b"\xdd" * width) * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def _readings(
    browser, url: str, tags: list[str]
) -> tuple[list[dict], list[dict], list[dict]]:
    """Each widget on the served page whose box changed from first paint to presented,
    each command in `tags`' widgets whose context keys the page never shows, and each
    box in `tags`' widgets that holds its own height and scrolls inside it."""
    from playwright.sync_api import Error as PlaywrightError

    page = browser.new_page(viewport=RENDER_VIEWPORT)
    arm_interception(page)
    install_driver(page)
    errors = []
    collect_page_errors(page, errors)
    # Runtime reports already reach the console; an example's preview writes no log.
    answer_reports(page, lambda text: None)
    try:
        if faults := start_with_pre_upgrade_proof(page, url):
            raise UnreadablePage("; ".join(map(str, faults)))
        wait_until_ready(page, served(page, url, "/api/state").json())
        wait_for_probe(page, "pageSettled")
        if errors:
            raise UnreadablePage("; ".join(map(str, errors)))
        changed = evaluate_probe(page, "changedBoxes")
        unshown = evaluate_probe(page, "unshownContextKeys", tags)
        return changed, unshown, evaluate_probe(page, "heldScrollers", tags)
    except (PlaywrightError, RuntimeError, TimeoutError) as error:
        raise UnreadablePage(str(error).strip()) from error
    finally:
        page.close()


def _page_findings(
    browser,
    composition: LayerComposition,
    pages: list[tuple[str, SourceDocument]],
    tags: list[str],
) -> list[Finding]:
    """`keeps-first-box`, `shows-context-keys` and `grows-with-content` over each page
    of examples, served
    from a page vendored with the package's layer and thrown away after."""
    findings = []
    with tempfile.TemporaryDirectory(prefix="leaf-widgets-") as temporary:
        page_dir = Path(temporary)
        start_throwaway_page(page_dir, composition)
        candidate = read_page_registry(page_dir)
        (page_dir / MEDIA_DIR).mkdir(exist_ok=True)
        for layout, document in pages:
            for reference in sorted(document.media_refs):
                # Only a name the server serves gets a stand-in, which also keeps
                # every write inside the page: a name cannot hold a directory.
                if not MEDIA_REFERENCE.fullmatch(reference):
                    raise UnreadablePage(
                        f"{reference} isn't a media name a page serves"
                    )
                image = page_dir / reference.lstrip("/")
                image.write_bytes(_blank_image(image.suffix))
            try:
                artifact = capture_artifact(
                    page_dir,
                    document,
                    candidate.registry,
                    declaration_sources=candidate.declaration_sources,
                    widget_sources=candidate.widget_sources,
                )
            except ArtifactError as error:
                raise UnreadablePage(str(error)) from error
            with preview_server(page_dir, document, 1, artifact=artifact) as url:
                changed, unshown, held = _readings(browser, url, tags)
            findings += [
                _finding(
                    "keeps-first-box",
                    box["tag"],
                    box["id"],
                    layout=layout,
                    first=box["first"],
                    now=box["now"],
                )
                for box in changed
                if box["tag"] in tags
            ]
            findings += [
                _finding(
                    "shows-context-keys",
                    command["tag"],
                    command["id"],
                    layout=layout,
                    command=command["command"],
                )
                for command in unshown
            ]
            findings += [
                _finding(
                    "grows-with-content",
                    box["tag"],
                    box["id"],
                    layout=layout,
                    box=box["at"],
                    height=box["height"],
                )
                for box in held
            ]
    return findings


def widget_findings(browser, package: Path) -> list[Finding]:
    """Every check's findings for the widgets `package` declares, read in `browser`.

    Raises `UnreadablePage` where a page of its examples cannot be drawn, which leaves
    nothing to read."""
    package = package.resolve()
    tags = own_tags(package)
    composition = compose_layer(checked_layer_inputs(package_layer_inputs(package)))
    pages = [
        (layout, SourceDocument(html))
        for layout, html in example_pages(composition.registry, tags)
    ]
    shown = {record["tag"] for _, page in pages for record in page.lf_elements}
    findings = [_finding("example", tag) for tag in tags if tag not in shown]
    if pages:
        findings += _page_findings(browser, composition, pages, tags)
    return findings
