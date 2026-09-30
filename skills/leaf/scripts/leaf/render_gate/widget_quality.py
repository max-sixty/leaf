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
repeat one already on the page. A page is rendered as authored, without `page check`:
an example may point at data or an element a package cannot carry, and what the report
reads is the widget, not the page. A package carries no media either, so a blank
image stands in for each one an example names.

Each check has one name in `CHECKS`, which a finding carries:

- `example`: each of the package's tags appears in some worked example, since a tag no
  example shows is one no other check reads.
- `keeps-first-box`: a widget paints its final box before it upgrades, so upgrade adds
  behavior and moves nothing (`../../../assets/AGENTS.md`, "Stability"). Its reading is
  `changedBoxes` in `render-checks/widgets.js`, against the box each authored widget had
  at first paint, which the pre-upgrade proof keeps (`scheme.start_with_pre_upgrade_proof`).
"""

import struct
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path

from leaf.layer import LayerComposition, checked_layer_inputs, compose_layer
from leaf.packages import package_layer_inputs
from leaf.registry.contract import read_registry_declarations
from leaf.registry.storage import read_page_registry
from leaf.render_checks import (
    RENDER_VIEWPORT,
    evaluate_probe,
    install_window_errors,
    wait_for_probe,
    wait_until_ready,
)
from leaf.revision_artifact import capture_artifact
from leaf.structure import SourceDocument
from leaf.vendoring import start_throwaway_page

from .preview import preview_server
from .scheme import arm_interception, served, start_with_pre_upgrade_proof

CHECKS = ("example", "keeps-first-box")


@dataclass(frozen=True, slots=True)
class Finding:
    """One check's reading of one widget: `id` names the instance where the check read
    one, and `fact` is what it measured."""

    tag: str
    check: str
    fact: str
    id: str = ""

    def __str__(self) -> str:
        widget = f"<{self.tag} id={self.id!r}>" if self.id else f"<{self.tag}>"
        return f"{widget} {self.check}: {self.fact}"


class UnreadablePage(Exception):
    """A page of worked examples the browser could not bring to presentation."""


def own_tags(package: Path) -> list[str]:
    """The widget tags the package's own `registry.json` declares, in its order."""
    declarations = read_registry_declarations(package / "registry.json") or {}
    return [tag for tag in declarations if tag.startswith("lf-")]


def example_pages(registry: dict, tags: list[str]) -> list[str]:
    """The worked examples of `tags`, gathered into as few pages as their ids allow."""
    pages = []
    ids = set()
    for tag in tags:
        if (example := registry[tag].get("x-example")) is None:
            continue
        own = SourceDocument(example).ids
        if not pages or own & ids:
            pages.append([])
            ids = set()
        pages[-1].append(example)
        ids |= own
    return [
        "<!doctype html>\n<html lang='en'>\n<head><title>Worked examples</title></head>"
        "\n<body>\n<main class='layout-column'>\n"
        + "\n".join(examples)
        + "\n</main>\n</body>\n</html>\n"
        for examples in pages
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


def _size(box: dict) -> str:
    return f"{round(box['width'])}x{round(box['height'])}"


def _changed_boxes(browser, url: str) -> list[dict]:
    """Each widget on the served page whose box changed from first paint to presented."""
    from playwright.sync_api import Error as PlaywrightError

    page = browser.new_page(viewport=RENDER_VIEWPORT)
    arm_interception(page)
    install_window_errors(page)
    try:
        if faults := start_with_pre_upgrade_proof(page, url):
            raise UnreadablePage("; ".join(faults))
        wait_until_ready(page, served(page, url, "/api/state").json())
        wait_for_probe(page, "pageSettled")
        return evaluate_probe(page, "changedBoxes")
    except (PlaywrightError, RuntimeError, TimeoutError) as error:
        raise UnreadablePage(str(error).strip().splitlines()[0]) from error
    finally:
        page.close()


def _changed_box_findings(
    browser, composition: LayerComposition, pages: list[SourceDocument], tags: list[str]
) -> list[Finding]:
    """`keeps-first-box` over each page of examples, served from a page vendored with
    the package's layer and thrown away after."""
    findings = []
    with tempfile.TemporaryDirectory(prefix="leaf-widgets-") as temporary:
        page_dir = Path(temporary)
        start_throwaway_page(page_dir, composition)
        candidate = read_page_registry(page_dir)
        for document in pages:
            for reference in document.media_refs:
                image = page_dir / reference.lstrip("/")
                image.parent.mkdir(exist_ok=True)
                image.write_bytes(_blank_image(image.suffix))
            artifact = capture_artifact(
                page_dir,
                document,
                candidate.registry,
                declaration_sources=candidate.declaration_sources,
                widget_sources=candidate.widget_sources,
            )
            with preview_server(page_dir, document, 1, artifact=artifact) as url:
                changed = _changed_boxes(browser, url)
            findings += [
                Finding(
                    box["tag"],
                    "keeps-first-box",
                    f"first painted {_size(box['first'])}, "
                    f"{_size(box['now'])} once presented",
                    box["id"],
                )
                for box in changed
                if box["tag"] in tags
            ]
    return findings


def widget_findings(browser, package: Path) -> list[Finding]:
    """Every check's findings for the widgets `package` declares, read in `browser`.

    Raises `UnreadablePage` where a page of its examples never presents, which leaves
    nothing to read."""
    package = package.resolve()
    tags = own_tags(package)
    composition = compose_layer(checked_layer_inputs(package_layer_inputs(package)))
    pages = [SourceDocument(html) for html in example_pages(composition.registry, tags)]
    shown = {record["tag"] for page in pages for record in page.lf_elements}
    findings = [
        Finding(tag, "example", "no worked example shows it")
        for tag in tags
        if tag not in shown
    ]
    if pages:
        findings += _changed_box_findings(browser, composition, pages, tags)
    return findings
