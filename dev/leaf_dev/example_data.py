"""Read the authored catalog, regression inputs, and page companions."""

import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

from leaf.structure import SourceDocument

from leaf_dev import ROOT
from leaf_dev.leaf_assets import pinned_copy

TEST_PAGES = ROOT / "tests" / "fixtures" / "pages"


# Where a page named on a command line is looked up.
NAMED_SOURCE_DIRS = (ROOT / "examples", ROOT / "examples" / "developer", TEST_PAGES)


def named_source(name: str) -> Path:
    """The one authored source a name picks out of `NAMED_SOURCE_DIRS`; a ValueError
    says why a name picks none, or several."""
    name = name.removesuffix(".html")
    found = [
        path for root in NAMED_SOURCE_DIRS if (path := root / f"{name}.html").is_file()
    ]
    if len(found) > 1:
        raise ValueError(f"{name} names more than one source: {found}")
    if not found:
        available = sorted(
            path.stem for root in NAMED_SOURCE_DIRS for path in root.glob("*.html")
        )
        raise ValueError(f"no source named {name}; available: {', '.join(available)}")
    return found[0]


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
            name = attrs["href"].removeprefix("/examples/").strip("/")
            self.sources.append(ROOT / "examples" / f"{name}.html")

    catalog = Catalog()
    catalog.feed((ROOT / "docs" / "examples.html").read_text(encoding="utf-8"))
    return catalog.sources


def document_metadata(source: Path) -> tuple[str, str]:
    """The authored title and description a page's link card and catalog caption show."""
    parsed = SourceDocument(source.read_text(encoding="utf-8"))
    title = parsed.title.strip()
    description = next(
        (
            (meta["content"] or "").strip()
            for meta in parsed.named_metas
            if meta["name"] == "description"
        ),
        "",
    )
    if not title or not description:
        sys.exit(f"{source}: a published page needs a <title> and a description")
    return title, description


# An authored source's companions, named beside it whether or not it has each
# (examples/AGENTS.md): its seeded history, its data values, and its page-owned files.
def seed_log(source: Path) -> Path:
    return source.with_suffix(".jsonl")


def data_file(source: Path) -> Path:
    return source.with_suffix(".data.json")


def page_files(source: Path) -> Path:
    return source.with_suffix(".page")


# A prior version ships under the source directory's versions/, so a builder's
# top-level `*.html` glob never reads one as a page of its own.
PRIOR_VERSION = re.compile(r"\.v([1-9][0-9]*)$")


def prior_version_files(source: Path) -> list[Path]:
    """The files under `versions/` named as one source's earlier versions, unchecked."""
    return list((source.parent / "versions").glob(f"{source.stem}.v*.html"))


def example_versions(source: Path) -> list[Path]:
    """Every authored version of one example, oldest first.

    The example's own file is its current version, and for most examples that is the
    whole list. One that was revised ships each earlier version as
    the source directory's `versions/<stem>.vN.html`; every builder stamps this list in
    order, so the page a user opens carries the version picker, the changes-since
    marks, and a thread opened against the document before the revision.
    """
    priors = sorted(
        prior_version_files(source),
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


def patch_manifest(
    patch: str, *, runtime: Path = ROOT, env: dict[str, str] | None = None
) -> dict:
    """The `diff` package's producer script's manifest for one patch.

    The selected runtime's package runner owns the script and its declared
    dependencies, so a comparison cannot mix one arm's producer with another's
    environment or data contract. `env` carries the consumer's package lookup state.
    A failed run raises with the script's stderr.
    """
    produced = subprocess.run(
        [str(runtime / "bin/leaf"), "package", "run", "diff", "patch_manifest.py"],
        env=env,
        input=patch.encode("utf-8"),
        capture_output=True,
        check=False,
    )
    if produced.returncode != 0:
        raise ValueError(produced.stderr.decode("utf-8").strip())
    return json.loads(produced.stdout)


def captured_value(
    file: Path, spec: dict, *, runtime: Path = ROOT, env: dict[str, str] | None = None
):
    """One `$captures` entry's value: the file's text, an inclusive `lines` range of
    it, for `"format": "json"` the JSON value it holds, or, for
    `"format": "unified-diff"`, the whole patch's file manifest. A patch is captured
    whole, so a `lines` range beside that format is refused."""
    text = file.read_text(encoding="utf-8")
    if spec.get("format") == "json":
        return json.loads(text)
    if spec.get("format") == "unified-diff":
        if "lines" in spec:
            raise ValueError(
                f"{file}: a unified-diff capture takes the whole patch, not lines "
                f"{spec['lines']}"
            )
        return patch_manifest(text, runtime=runtime, env=env)
    if (lines := spec.get("lines")) is None:
        return text
    start, end = (int(bound) for bound in lines.split(":"))
    selected = text.splitlines(keepends=True)[start - 1 : end]
    if len(selected) != end - start + 1:
        raise ValueError(f"{file}: lines {lines} run past the file's end")
    return "".join(selected)


def data_companion(source: Path) -> dict:
    """The example's `.data.json` companion, or nothing when it has none."""
    companion = data_file(source)
    if not companion.exists():
        return {}
    return json.loads(companion.read_text(encoding="utf-8"))


def capture_file(source: Path, spec: dict) -> Path:
    """Where one `$captures` entry's bytes are. `file` names a tracked file beside the
    source; `asset` names one the same way whose bytes are pinned in leaf-assets
    (`leaf_dev.leaf_assets`), for evidence too large for the tree, such as an imported
    Playwright trace."""
    if "asset" in spec:
        return pinned_copy(source.parent / spec["asset"])
    return source.parent / spec["file"]


def data_operations(
    source: Path, *, runtime: Path = ROOT, env: dict[str, str] | None = None
) -> list[dict]:
    """Every source value one example sets: captures first, then written values."""
    document = data_companion(source)
    captures = [
        {
            "source": name,
            "value": captured_value(
                capture_file(source, spec), spec, runtime=runtime, env=env
            ),
        }
        for name, spec in document.pop("$captures", {}).items()
    ]
    return [
        *captures,
        *({"source": name, "value": value} for name, value in document.items()),
    ]
