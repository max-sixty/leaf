#!/usr/bin/env python3
"""Prepare an example as a live page or a standalone review file.

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
widget shows up on the next run. `version stamp` lints the example on the way past. The
browser gate a page normally passes before its URL goes out is left to the
suite: `version check --render` and `test_example_renders` drive the same
`render_version` over the same files, so running it here would only repeat what
the suite has already said about these exact pages.

Usage: preview.py [example] [--export]  (default: design-decision)
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from example_data import data_operations

ROOT = Path(__file__).resolve().parent.parent
LEAF = ROOT / "bin" / "leaf"
PAGE = ROOT / ".tmp" / "preview"  # gitignored, and stable so the port persists
PACKAGES = json.loads((ROOT / "examples" / "layer.json").read_text(encoding="utf-8"))


def leaf(*args, check=True, input_text=None):
    return subprocess.run(
        [str(LEAF), *args],
        cwd=ROOT,
        check=check,
        input=input_text,
        text=input_text is not None,
    )


def seed_data(source: Path, page: Path) -> None:
    """Apply each page-bound data operation shipped beside an example."""
    for operation in data_operations(source):
        if operation["kind"] == "set":
            leaf(
                "data",
                "set",
                str(page),
                operation["source"],
                input_text=json.dumps(operation["value"]),
            )
            continue
        args = [
            "data",
            "capture",
            str(page),
            operation["source"],
            "--text-file",
            str(operation["text_file"]),
        ]
        if operation["label"] is not None:
            args.extend(("--label", operation["label"]))
        if operation["lines"] is not None:
            args.extend(("--lines", operation["lines"]))
        leaf(*args)


def seed_log(source: Path, page: Path) -> None:
    """Lay an example's companion log in, where it ships one.

    A thread is log state — no markup describes one — so an example that wants to
    show a conversation ships the events beside it, the way one that wants a
    screenshot ships the bytes beside it. Appended after `version stamp`, so the
    note announcing v1 stays the log's first line and the exchange reads in the
    order it happened.

    The cursor goes to the end of it, because a seed is history rather than news.
    Without that, every preview of a seeded example hands the next agent session a
    question to answer that the same log already answers two lines further down,
    and the loop guard is right to nag about it each time — the demo would spend
    its first move undoing itself.
    """
    seed = source.with_suffix(".jsonl")
    if not seed.exists():
        return
    log = page / "comments.jsonl"
    with log.open("a", encoding="utf-8") as f:
        f.write(seed.read_text(encoding="utf-8"))
    # An event's seq is its line number, so the last line's number is the cursor.
    # Split on the writer's own separator, never splitlines(), whose wider class
    # reads a U+2028 inside a comment's text as a break.
    lines = [n for n in log.read_text(encoding="utf-8").split("\n") if n.strip()]
    (page / "cursor.json").write_text(
        json.dumps({"seq": len(lines)}) + "\n", encoding="utf-8"
    )


def main() -> None:
    args = sys.argv[1:]
    standalone = "--export" in args
    args = [arg for arg in args if arg != "--export"]
    if len(args) > 1 or any(arg.startswith("-") for arg in args):
        sys.exit("usage: preview.py [example] [--export]")
    name = args[0] if args else "design-decision"
    name = name.removesuffix(".html")
    source = ROOT / "examples" / f"{name}.html"
    if not source.exists():
        sys.exit(
            f"no example named {name}; examples/ holds "
            + ", ".join(sorted(p.stem for p in (ROOT / "examples").glob("*.html")))
        )

    if PAGE.exists():  # a previous preview may still hold the port
        leaf("server", "stop", str(PAGE), check=False)
        shutil.rmtree(PAGE)
    selection_args = [arg for package in PACKAGES for arg in ("--package", package)]
    leaf("page", "init", *selection_args, str(PAGE))
    (PAGE / "index.html").write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )
    shutil.copytree(ROOT / "examples" / "media", PAGE / "media", dirs_exist_ok=True)
    seed_data(source, PAGE)
    leaf(
        "version",
        "stamp",
        str(PAGE),
        "--text",
        f"{source.name}, as it stands in the tree",
    )
    seed_log(source, PAGE)
    if standalone:
        out = ROOT / ".tmp" / f"example-{name}.html"
        out.unlink(missing_ok=True)
        leaf("version", "export", str(PAGE), "-o", str(out))
        print(out.resolve())
        return
    leaf("server", "run", str(PAGE))


if __name__ == "__main__":
    main()
