#!/usr/bin/env python3
"""Prepare an example or developer fixture as a live page or review file.

An example is a page body, not a page directory: it links /theme.css and
/leaf.js at the server root, which is where `page init` vendors them. Opening one
from disk gets a dead page, because Chrome refuses ES modules from a file://
origin — nothing upgrades, and a tabbed page renders as every tab at once. This
script builds the directory the runtime expects. By default it hands that page to
`server run`, which serves in the foreground until Ctrl-C; `--export` writes the
browser-drawn result as one standalone HTML file instead.

The live result is a page, not a picture of one: it takes comments. Served from
an agent session, `leaf wait` on the same directory carries them to the agent and
the example gets revised like any other page; run from a bare shell, they queue
in the log until an agent next reads it. Which of those happens follows from the
host identity the launcher puts in the environment.

An example can also ship companion `.jsonl` events and `.data.json` source
values. The first lets a page arrive mid-conversation; the second supplies the
same page-bound external data a real host would replace through `leaf data set`.

Vendoring runs fresh each time, so an edit to the theme, the registry, or a
widget shows up on the next run. `version stamp` lints the example on the way
past. The browser gate a page normally passes before its URL goes out is left to
the suite: `version check --render` and `test_page_fixture_renders` drive the same
`render_version` over the same files, so running it here would only repeat what
the suite has already said about these exact pages.

Named slots let several previews coexist. `--source` keeps one authored fixture
fixed while `--runtime` vendors it from another Leaf checkout. `--background`
starts the page service and returns its URL instead of holding the terminal.

Usage: preview.py [page] [options]  (default: design-decision)
"""

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from example_data import data_operations, example_versions

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"
PAGE = TMP / "preview"  # gitignored, and stable so the port persists
DEFAULT_PACKAGES = ROOT / "examples" / "layer.json"
NAMED_SOURCE_DIRS = (ROOT / "examples", ROOT / "examples" / "developer")
SLOT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def leaf(launcher: Path, runtime: Path, *args, check=True, input_text=None):
    return subprocess.run(
        [str(launcher), *args],
        cwd=runtime,
        check=check,
        input=input_text,
        text=input_text is not None,
    )


def seed_data(source: Path, page: Path, launcher: Path, runtime: Path) -> None:
    """Apply each page-bound data operation shipped beside an example."""
    for operation in data_operations(source):
        if operation["kind"] == "set":
            args = ["data", "set", str(page), operation["source"]]
            if operation["capture_label"] is not None:
                args.extend(("--capture-label", operation["capture_label"]))
            leaf(
                launcher,
                runtime,
                *args,
                input_text=json.dumps(operation["value"]),
            )
            continue
        args = [
            "data",
            "capture",
            str(page),
            operation["source"],
            "--file",
            str(operation["input_file"]),
            "--format",
            operation["format"],
        ]
        if operation["label"] is not None:
            args.extend(("--label", operation["label"]))
        if operation["lines"] is not None:
            args.extend(("--lines", operation["lines"]))
        leaf(launcher, runtime, *args)


def seed_log(source: Path, page: Path) -> None:
    """Lay an example's companion log in, where it ships one.

    A thread is log state — no markup describes one — so an example that wants to
    show a conversation ships the events beside it, the way one that wants a
    screenshot ships the bytes beside it. Appended after the first `version stamp`
    and before any later one, so the note announcing v1 stays the log's first line
    and a revised example reads in the order it happened: the version, what the
    reader said about it, then the version that answered them.
    """
    seed = source.with_suffix(".jsonl")
    if not seed.exists():
        return
    with (page / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(seed.read_text(encoding="utf-8"))


def acknowledge_log(source: Path, page: Path) -> None:
    """Put the cursor at the end of a seeded log, because a seed is history not news.

    Without this, every preview of a seeded example hands the next agent session a
    question to answer that the same log already answers two lines further down,
    and the loop guard is right to nag about it each time — the demo would spend
    its first move undoing itself. Run after the last stamp, so a revised example's
    closing note is inside the acknowledgement rather than left as unread news.
    """
    if not source.with_suffix(".jsonl").exists():
        return
    # An event's seq is its line number, so the last line's number is the cursor.
    # Split on the writer's own separator, never splitlines(), whose wider class
    # reads a U+2028 inside a comment's text as a break.
    log = (page / "events.jsonl").read_text(encoding="utf-8")
    lines = [n for n in log.split("\n") if n.strip()]
    (page / "cursor.json").write_text(
        json.dumps({"seq": len(lines)}) + "\n", encoding="utf-8"
    )


def slot_name(value: str) -> str:
    if not SLOT_NAME.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "use 1-64 letters, digits, dots, underscores, or hyphens"
        )
    return value


def arguments() -> tuple[argparse.ArgumentParser, argparse.Namespace]:
    parser = argparse.ArgumentParser(
        description="Prepare a public example or developer fixture with a Leaf runtime."
    )
    parser.add_argument(
        "example",
        nargs="?",
        help="public example or developer fixture name (default: design-decision)",
    )
    parser.add_argument("--source", type=Path, help="authored HTML source to preview")
    parser.add_argument(
        "--runtime",
        type=Path,
        default=ROOT,
        help="Leaf checkout whose bin/leaf vendors the page",
    )
    parser.add_argument(
        "--slot",
        type=slot_name,
        help="stable name for a preview that may coexist with other slots",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--background",
        action="store_true",
        help="start the page service and return its URL",
    )
    mode.add_argument(
        "--export",
        action="store_true",
        help="write a standalone HTML file instead of serving the page",
    )
    parsed = parser.parse_args()
    if parsed.source and parsed.example:
        parser.error("choose an example name or --source, not both")
    return parser, parsed


def checkout(parser: argparse.ArgumentParser, value: Path) -> tuple[Path, Path]:
    runtime = value.expanduser().resolve()
    launcher = runtime / "bin" / "leaf"
    if not launcher.is_file():
        parser.error(f"{runtime} has no bin/leaf launcher")
    result = subprocess.run(
        [str(launcher), "--version"],
        cwd=runtime,
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "launcher failed"
        parser.error(f"could not run {launcher}: {detail}")
    try:
        reported = Path(result.stdout.strip()).resolve()
    except (OSError, ValueError):
        parser.error(
            f"{launcher} reported an invalid checkout: {result.stdout.strip()}"
        )
    if reported != runtime:
        parser.error(f"{launcher} runs {reported}, not {runtime}")
    return runtime, launcher


def authored_source(
    parser: argparse.ArgumentParser, example: str | None, source: Path | None
) -> Path:
    if source:
        selected = source.expanduser().resolve()
        if not selected.is_file():
            parser.error(f"no authored source at {selected}")
        return selected
    name = (example or "design-decision").removesuffix(".html")
    candidates = [root / f"{name}.html" for root in NAMED_SOURCE_DIRS]
    found = [path for path in candidates if path.is_file()]
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        parser.error(f"{name} names more than one preview source: {found}")
    available = sorted(
        path.stem for root in NAMED_SOURCE_DIRS for path in root.glob("*.html")
    )
    parser.error(
        f"no preview source named {name}; available pages: " + ", ".join(available)
    )


def prepare(source: Path, page: Path, launcher: Path, runtime: Path) -> None:
    """Build one page from the selected runtime and the source's fixtures."""
    package_manifest = source.parent / "layer.json"
    if not package_manifest.is_file():
        package_manifest = DEFAULT_PACKAGES
    packages = json.loads(package_manifest.read_text(encoding="utf-8"))
    selection_args = [arg for package in packages for arg in ("--package", package)]
    leaf(launcher, runtime, "page", "init", *selection_args, str(page))
    # The data door validates a source against the page's markup, and the current
    # version is the one that has to bind it, so the newest version goes in first and
    # the loop below walks back to the oldest and stamps forward from there.
    (page / "index.html").write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )
    media = source.parent / "media"
    if media.is_dir():
        shutil.copytree(media, page / "media", dirs_exist_ok=True)
    seed_data(source, page, launcher, runtime)
    # Each authored version in order, through the real stamp boundary, so a revised
    # example arrives with the chooser, the marks and the notes a reader travels by.
    for order, version in enumerate(example_versions(source)):
        (page / "index.html").write_text(
            version.read_text(encoding="utf-8"), encoding="utf-8"
        )
        leaf(
            launcher,
            runtime,
            "version",
            "stamp",
            str(page),
            "--text",
            f"{version.name}, as it stands in the tree",
        )
        if order == 0:
            seed_log(source, page)
    acknowledge_log(source, page)


def mark_preview(source: Path, page: Path, runtime: Path) -> None:
    """Identify the live runtime without exposing its absolute path to the browser."""
    layer = json.loads((page / "registry.json").read_text(encoding="utf-8"))["$layer"]
    producer = layer.get("producer", {})
    metadata = {
        "kind": "example",
        "example": source.stem,
        "checkout": runtime.name,
        "started": datetime.now(timezone.utc).isoformat(),
        **({"commit": producer["commit"]} if "commit" in producer else {}),
        **({"dirty": producer["dirty"]} if "dirty" in producer else {}),
    }
    (page / "preview.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser, args = arguments()
    runtime, launcher = checkout(parser, args.runtime)
    source = authored_source(parser, args.example, args.source)

    if args.export:
        TMP.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="preview-export-", dir=TMP) as staging:
            page = Path(staging) / "page"
            prepare(source, page, launcher, runtime)
            suffix = f"-{args.slot}" if args.slot else ""
            out = TMP / f"example-{source.stem}{suffix}.html"
            out.unlink(missing_ok=True)
            leaf(launcher, runtime, "version", "export", str(page), "-o", str(out))
        print(out.resolve())
        return

    page = TMP / "previews" / args.slot if args.slot else PAGE

    if page.exists():  # a previous preview may still hold the port
        leaf(launcher, runtime, "server", "stop", str(page), check=False)
        shutil.rmtree(page)
    prepare(source, page, launcher, runtime)
    mark_preview(source, page, runtime)
    command = "start" if args.background else "run"
    leaf(launcher, runtime, "server", command, str(page))


if __name__ == "__main__":
    main()
