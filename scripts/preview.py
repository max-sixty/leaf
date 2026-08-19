#!/usr/bin/env python3
"""Serve an example as a real leaf page, to review how it renders.

An example is a page body, not a page directory: it links /theme.css and
/leaf.js at the server root, which is where `page init` vendors them. Opening one
from disk gets a dead page, because Chrome refuses ES modules from a file://
origin — nothing upgrades, and a tabbed page renders as every tab at once. So
this builds the directory the runtime expects and hands it to `server run`, which
serves in the foreground so Ctrl-C ends the preview. A session runs `server start`
instead, and gets the same server in a process of its own.

The result is a page, not a picture of one: it takes comments. Served from an
agent session, `leaf wait` on the same directory carries them to the agent and the
example gets revised like any other page; run from a bare shell, they queue in
the log until an agent next reads it. Which of those happens follows from the
host identity the launcher puts in the environment.

An example that ships a companion `.jsonl` opens with that log already in it, so
the page arrives mid-conversation rather than blank. That is the only way to see
a thread: it lives in the log, and `version export` drops the layer that draws
one, so no static copy anywhere can carry it.

Vendoring runs fresh each time, so an edit to the theme, the registry, or a
widget shows up on the next run. `version publish` lints the example on the way past. The
browser gate a page normally passes before its URL goes out is left to the
suite: `version check --render` and `test_example_renders` drive the same
`render_version` over the same files, so running it here would only repeat what
the suite has already said about these exact pages.

Usage: preview.py [example]  (default: gallery; Ctrl-C to stop)
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEAF = ROOT / "plugins" / "leaf" / "bin" / "leaf"
PAGE = ROOT / ".tmp" / "preview"  # gitignored, and stable so the port persists


def leaf(*args, check=True):
    return subprocess.run([str(LEAF), *args], check=check)


def seed_log(source: Path, page: Path) -> None:
    """Lay an example's companion log in, where it ships one.

    A thread is log state — no markup describes one — so an example that wants to
    show a conversation ships the events beside it, the way one that wants a
    screenshot ships the bytes beside it. Appended after `version publish`, so the
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
    name = (sys.argv[1] if len(sys.argv) > 1 else "gallery").removesuffix(".html")
    source = ROOT / "examples" / f"{name}.html"
    if not source.exists():
        sys.exit(
            f"no example named {name}; examples/ holds "
            + ", ".join(sorted(p.stem for p in (ROOT / "examples").glob("*.html")))
        )

    if PAGE.exists():  # a previous preview may still hold the port
        leaf("server", "stop", str(PAGE), check=False)
        shutil.rmtree(PAGE)
    leaf("page", "init", str(PAGE))
    (PAGE / "versions" / "v1.html").write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )
    shutil.copytree(ROOT / "examples" / "media", PAGE / "media", dirs_exist_ok=True)
    leaf(
        "version",
        "publish",
        str(PAGE),
        "--version",
        "1",
        "--text",
        f"{source.name}, as it stands in the tree",
    )
    seed_log(source, PAGE)
    leaf("server", "run", str(PAGE))


if __name__ == "__main__":
    main()
