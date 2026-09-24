"""Read the authored catalog, regression inputs, and page companions."""

import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEST_PAGES = ROOT / "tests" / "fixtures" / "pages"
PATCH_MANIFEST = (
    ROOT / "skills" / "leaf" / "packages" / "diff" / "scripts" / "patch_manifest.py"
)


def regression_sources() -> list[Path]:
    """Full-page regression inputs that are neither examples nor website routes."""
    return sorted(TEST_PAGES.glob("*.html"))


def catalog_sources() -> list[Path]:
    """The authored catalog owns its selection and order; commented cards are omitted.

    HTML comments deliberately contribute no links. Keeping this reading with the
    fixture readers lets preview generation follow the curated page without another
    list of featured names or promoting every regression input to the showcase.
    """

    class Catalog(HTMLParser):
        def __init__(self):
            super().__init__()
            self.sources = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag != "a" or "example-link" not in attrs.get("class", "").split():
                return
            match = re.fullmatch(r"/examples/([a-z0-9-]+)/", attrs["href"])
            if match is None:
                raise ValueError(
                    f"catalog entry must name an example route: {attrs['href']}"
                )
            source = ROOT / "examples" / f"{match.group(1)}.html"
            if not source.is_file() or source in self.sources:
                raise ValueError(f"catalog example is missing or repeated: {source}")
            self.sources.append(source)

    catalog = Catalog()
    catalog.feed((ROOT / "docs" / "examples.html").read_text(encoding="utf-8"))
    if not catalog.sources:
        raise ValueError("the examples catalog is empty")
    return catalog.sources


# A prior version ships under the source directory's versions/, so a builder's
# top-level `*.html` glob never reads one as a page of its own.
PRIOR_VERSION = re.compile(r"\.v([1-9][0-9]*)$")


def example_versions(source: Path) -> list[Path]:
    """Every authored version of one example, oldest first.

    The example's own file is its current version, and for most examples that is the
    whole list. One that was revised ships each earlier version as
    the source directory's `versions/<stem>.vN.html`; every builder stamps this list in
    order, so the page a user opens carries the version chooser, the changes-since
    marks, and a thread opened against the document before the revision.
    """
    priors = sorted(
        (source.parent / "versions").glob(f"{source.stem}.v*.html"),
        key=lambda path: int(PRIOR_VERSION.search(path.stem).group(1)),
    )
    # The published number is the position in this list, so a gap in the file names
    # would renumber every later version without a word; refuse it instead.
    numbers = [int(PRIOR_VERSION.search(path.stem).group(1)) for path in priors]
    if numbers != list(range(1, len(numbers) + 1)):
        raise ValueError(
            f"{source.name}: prior versions must run v1 to v{len(numbers)} without "
            f"a gap, found {numbers}"
        )
    return [*priors, source]


def patch_manifest(patch: str) -> dict:
    """The `diff` package's producer script's manifest for one patch.

    It runs as a process, reading stdin and writing stdout as an agent's pipeline
    does, but under this project's interpreter rather than `leaf package run`: the
    dev group carries the script's `unidiff` at the version `uv.lock` pins, so the
    fixtures and the suite read the same manifest on every machine and fetch nothing.
    A refused patch raises with the script's stderr."""
    produced = subprocess.run(
        [sys.executable, str(PATCH_MANIFEST)],
        input=patch.encode("utf-8"),
        capture_output=True,
        check=False,
    )
    if produced.returncode != 0:
        raise ValueError(produced.stderr.decode("utf-8").strip())
    return json.loads(produced.stdout)


def captured_value(file: Path, spec: dict):
    """One `$captures` entry's value: the file's text, an inclusive `lines` range of
    it, or, for `"format": "unified-diff"`, the whole patch's file manifest. A
    patch is captured whole, so a `lines` range beside that format is refused."""
    text = file.read_text(encoding="utf-8")
    if spec.get("format") == "unified-diff":
        if "lines" in spec:
            raise ValueError(
                f"{file}: a unified-diff capture takes the whole patch, not lines "
                f"{spec['lines']}"
            )
        return patch_manifest(text)
    if (lines := spec.get("lines")) is None:
        return text
    start, end = (int(bound) for bound in lines.split(":"))
    selected = text.splitlines(keepends=True)[start - 1 : end]
    if len(selected) != end - start + 1:
        raise ValueError(f"{file}: lines {lines} run past the file's end")
    return "".join(selected)


def data_operations(source: Path) -> list[dict]:
    """Every source value one example sets: captures first, then written values."""
    companion = source.with_suffix(".data.json")
    if not companion.exists():
        return []
    document = json.loads(companion.read_text(encoding="utf-8"))
    captures = [
        {"source": name, "value": captured_value(source.parent / spec["file"], spec)}
        for name, spec in document.pop("$captures", {}).items()
    ]
    return [
        *captures,
        *({"source": name, "value": value} for name, value in document.items()),
    ]
