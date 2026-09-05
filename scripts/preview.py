#!/usr/bin/env python3
"""Prepare an example or developer fixture as a live page or review file.

An example is a page body, not a page directory: it links /theme.css and
/leaf.js at the server root, which is where `page init` vendors them. Opening one
from disk gets a dead page, because Chrome refuses ES modules from a file://
origin — nothing upgrades, and a tabbed page renders as every tab at once. This
script builds the directory the runtime expects, then watches the fixture and
selected runtime until Ctrl-C. `--export` writes the browser-drawn result as one
standalone HTML file instead.

The live result is a page, not a picture of one: it takes comments. Served from
an agent session, `leaf wait` on the same directory carries them to the agent and
the example gets revised like any other page; run from a bare shell, they queue
in the log until an agent next reads it. Which of those happens follows from the
host identity the launcher puts in the environment.

An example can also ship companion `.jsonl` events and `.data.json` source
values. The first lets a page arrive mid-conversation; the second supplies the
same page-bound external data a real host would replace through `leaf data set`.

A source or layer edit stops the preview service, re-vendors through the normal
compatibility gate, stamps changed source, and restarts at the same URL. The
browser reloads through the existing layer generation handshake. The page log
and reader decisions survive; a refused update stays visible in the terminal
or background log and is retried after the next edit. Existing slots resume.
Changing fixture identity or seeded history requires a new slot. `version stamp`
lints the example on the way past. The browser gate a page normally passes before
its URL goes out is left to the suite: `version check --render` and `test_page_fixture_renders` drive the same
`render_version` over the same files, so running it here would only repeat what
the suite has already said about these exact pages.

Named slots let several previews coexist. `--source` keeps one authored fixture
fixed while `--runtime` vendors it from another Leaf checkout. `--background`
detaches the watcher and returns its URL instead of holding the terminal.

Usage: preview.py [page] [options]  (default: design-decision)
Stop:  preview.py [page] [--slot name] --stop
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from example_data import data_operations, example_versions

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"
DEFAULT_PACKAGES = ROOT / "examples" / "layer.json"
NAMED_SOURCE_DIRS = (ROOT / "examples", ROOT / "examples" / "developer")
SLOT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def leaf(
    launcher: Path,
    runtime: Path,
    *args,
    check: bool = True,
    input_text: str | None = None,
    show_output: bool = False,
) -> None:
    """Hide successful chatter; checked failures replay their stdout."""
    result = subprocess.run(
        [str(launcher), *args],
        cwd=runtime,
        check=False,
        input=input_text,
        stdout=None if show_output else subprocess.PIPE,
        text=True,
    )
    if check and result.returncode != 0:
        if not show_output and result.stdout:
            print(result.stdout, end="", flush=True)
        raise SystemExit(result.returncode)


def seed_data(
    operations: list[dict], page: Path, launcher: Path, runtime: Path
) -> None:
    """Apply each page-bound data operation shipped beside an example."""
    for operation in operations:
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
        help="watch in the background and return the preview URL",
    )
    mode.add_argument(
        "--export",
        action="store_true",
        help="write a standalone HTML file instead of serving the page",
    )
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--_ready-fd", type=int, help=argparse.SUPPRESS)
    mode.add_argument(
        "--stop", action="store_true", help="stop this preview watcher and its service"
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


def prepare(source: Path, page: Path, launcher: Path, runtime: Path) -> tuple[int, int]:
    """Build one page from the selected runtime and the source's fixtures."""
    packages = source_packages(source)
    selection_args = [arg for package in packages for arg in ("--package", package)]
    leaf(launcher, runtime, "page", "init", *selection_args, str(page))
    # The data door validates a source against the page's markup, and the current
    # version is the one that has to bind it, so the newest version goes in first and
    # the loop below walks back to the oldest and stamps forward from there.
    (page / "index.html").write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )
    media = media_source(source)
    if media.is_dir():
        shutil.copytree(media, page / "media", dirs_exist_ok=True)
    operations = data_operations(source)
    seed_data(operations, page, launcher, runtime)
    # Each authored version in order, through the real stamp boundary, so a revised
    # example arrives with the chooser, the marks and the notes a reader travels by.
    versions = example_versions(source)
    for order, version in enumerate(versions):
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
    return len({operation["source"] for operation in operations}), len(versions)


def preparation_note(source: Path, data_sources: int, versions: int) -> str:
    """Summarize successful setup without replaying each child command."""
    details = []
    if data_sources:
        data_label = "data source" if data_sources == 1 else "data sources"
        details.append(f"{data_sources} {data_label}")
    version_label = "version" if versions == 1 else "versions"
    details.append(f"{versions} {version_label}")
    return f"prepared {source.stem} ({', '.join(details)})"


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


def preview_directory(source: Path, slot: str | None) -> Path:
    name = re.sub(r"[^A-Za-z0-9._-]", "-", source.stem).strip("._-")[:64] or "preview"
    return TMP / "previews" / (slot or name)


def preview_files(page: Path) -> tuple[Path, Path, Path]:
    """Developer ownership and diagnostics live beside the frozen page."""
    return tuple(
        page.with_name(f"{page.name}.preview.{suffix}")
        for suffix in ("json", "lock", "log")
    )


def source_packages(source: Path) -> list[str]:
    manifest = source.parent / "layer.json"
    if not manifest.is_file():
        manifest = DEFAULT_PACKAGES
    return json.loads(manifest.read_text(encoding="utf-8"))


def media_source(source: Path) -> Path:
    media = source.parent / "media"
    if not media.is_dir() and source.parent == ROOT / "examples" / "developer":
        return ROOT / "examples" / "media"
    return media


def refresh_media(source: Path, page: Path) -> None:
    """Add immutable assets; historical revisions may still reference every copy."""
    media = media_source(source)
    incoming = [path for path in media.rglob("*") if path.is_file()]
    for path in incoming:
        target = page / "media" / path.relative_to(media)
        if digest(target) not in (None, digest(path)):
            raise ValueError(
                f"media/{path.relative_to(media)} has different bytes in the preview; use a new filename to preserve historical revisions"
            )
    for path in incoming:
        target = page / "media" / path.relative_to(media)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def fixture_seed(source: Path) -> dict:
    """Seed history is installed once, never replayed over reader feedback."""
    paths = [
        source.with_suffix(".jsonl"),
        source.with_suffix(".data.json"),
        *example_versions(source)[:-1],
    ]
    return {str(path): digest(path) for path in paths}


def source_identity(source: Path, runtime: Path) -> dict:
    return {
        "source": str(source),
        "runtime": str(runtime),
        "seed": fixture_seed(source),
    }


def refresh_preview(
    source: Path, page: Path, launcher: Path, runtime: Path, identity: dict
) -> None:
    """Replace only admitted layer/source changes; never recreate the page log.

    Runtime updates do not overwrite an agent's direct page edits. If the fixture
    and the live authored source both changed, neither silently wins.
    """
    if source_identity(source, runtime) != {
        key: identity[key] for key in ("source", "runtime", "seed")
    }:
        raise ValueError(
            "fixture identity or seeded history changed; use a new --slot to preview it"
        )
    incoming = source.read_bytes()
    incoming_digest = hashlib.sha256(incoming).hexdigest()
    source_changed = incoming_digest != identity["source_digest"]
    authored = page / "index.html"
    if source_changed and digest(authored) not in (
        identity["source_digest"],
        incoming_digest,
    ):
        raise ValueError(
            "both the fixture and preview index.html changed; reconcile them before retrying"
        )
    packages = source_packages(source)
    selection_args = [
        arg for package in packages for arg in ("--package", package)
    ] or ["--no-packages"]
    leaf(launcher, runtime, "page", "init", *selection_args, str(page))
    refresh_media(source, page)
    if source_changed:
        previous = authored.read_bytes()
        authored.write_bytes(incoming)
        try:
            leaf(
                launcher,
                runtime,
                "version",
                "stamp",
                str(page),
                "--text",
                f"{source.name}, updated in the checkout",
            )
        except BaseException:
            authored.write_bytes(previous)
            raise
        identity["source_digest"] = incoming_digest
        update_preview_state(page, source_digest=identity["source_digest"])
    mark_preview(source, page, runtime)


def watch_paths(
    source: Path, runtime: Path, roots: list[Path], seed: dict
) -> list[Path]:
    from leaf.layer import input_paths

    paths = input_paths(roots)
    paths.extend((source, source.parent / "layer.json", DEFAULT_PACKAGES))
    paths.extend(Path(path) for path in seed)
    paths.extend((source.parent / "versions").glob(f"{source.stem}.v*.html"))
    paths.extend((runtime / "skills" / "leaf" / "scripts").rglob("*.py"))
    paths.extend((runtime / "pyproject.toml", runtime / "uv.lock"))
    paths.append(media_source(source))
    paths.extend(media_source(source).rglob("*"))
    return paths


def snapshot(paths: list[Path]) -> dict:
    """Stat inputs so idle previews do not repeatedly read vendored bundles."""
    result = {}
    for path in paths:
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue  # an editor's atomic replace is observed on the next pass
        result[str(path)] = (stat.st_mtime_ns, stat.st_size)
    return result


def start_preview_server(
    page: Path, launcher: Path, runtime: Path
) -> tuple[str, str] | None:
    # The CLI owns the claim transition as well as starting the serving child.
    result = subprocess.run(
        [str(launcher), "server", "start", str(page)],
        cwd=runtime,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        print(result.stderr or result.stdout, file=sys.stderr, end="", flush=True)
        return None
    return result.stdout.strip(), result.stderr.strip()


def update_preview_state(page: Path, **changes) -> dict:
    from leaf.event_log import flocked
    from leaf.files import read_json, write_json

    metadata, _, _ = preview_files(page)
    with flocked(metadata.with_suffix(".state.lock")):
        state = {**(read_json(metadata) or {}), **changes}
        write_json(metadata, state)
        return state


def stop_preview(page: Path) -> None:
    """Wait for the watcher to retire, including any in-flight recompose."""
    from leaf.event_log import flocked
    from leaf.hosting import cmd_stop

    _, lease_path, _ = preview_files(page)
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    update_preview_state(page, enabled=False)
    with flocked(lease_path):
        cmd_stop(page)
    print(f"stopped preview {page}", flush=True)


def preview_ready(
    announcement: dict, ready_fd: int | None, log_path: Path | None = None
) -> None:
    if ready_fd is None:
        announce_preview(announcement, log_path)
    else:
        with os.fdopen(ready_fd, "w") as channel:
            channel.write(json.dumps(announcement) + "\n")


def watch_preview(
    source: Path, page: Path, launcher: Path, runtime: Path, ready_fd: int | None
) -> None:
    from leaf.event_log import flocked
    from leaf.files import read_json, write_json
    from leaf.hosting import cmd_stop, startup_note
    from leaf.layer import layer_inputs
    from leaf.leases import take_waiter_lease
    from leaf.server import running_server

    metadata, lease_path, log_path = preview_files(page)
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    # Serialize startup intent against --stop, separately from the lifetime lease
    # that stop waits for after writing its intent.
    with flocked(metadata.with_suffix(".state.lock")):
        lease = take_waiter_lease(lease_path)
        identity = read_json(metadata)
        if lease is not None:
            if page.exists() and (
                identity is None
                or source_identity(source, runtime)
                != {key: identity.get(key) for key in ("source", "runtime", "seed")}
            ):
                lease.close()
                raise ValueError(
                    f"{page} contains another fixture or changed seed history; choose a new --slot (existing feedback is preserved)"
                )
            identity = (
                identity
                if page.exists()
                else {
                    **source_identity(source, runtime),
                    "source_digest": digest(source),
                }
            )
            write_json(metadata, {**identity, "enabled": True})
    if lease is None:
        running = running_server(page)
        if identity and source_identity(source, runtime) == {
            key: identity.get(key) for key in ("source", "runtime", "seed")
        }:
            while running is None and read_json(metadata)["enabled"]:
                time.sleep(0.05)
                running = running_server(page)
            if running is None:
                raise ValueError(f"preview {page} was stopped while updating")
            preview_ready(
                {
                    "prepared": f"watching {source.stem} (feedback preserved)",
                    "url": running["url"],
                    "note": startup_note(page),
                },
                ready_fd,
                log_path,
            )
            return
        raise ValueError(
            f"a watcher already owns {page}; choose a new --slot for another fixture"
        )
    with lease:
        try:
            if page.exists():
                cmd_stop(page)
                try:
                    refresh_preview(source, page, launcher, runtime, identity)
                except (SystemExit, ValueError, OSError) as error:
                    print(
                        f"Preview update refused: {error}. Feedback is preserved; edit the inputs to retry.",
                        file=sys.stderr,
                        flush=True,
                    )
                prepared = f"resumed {source.stem} (feedback preserved)"
            else:
                data_sources, versions = prepare(source, page, launcher, runtime)
                mark_preview(source, page, runtime)
                prepared = preparation_note(source, data_sources, versions)
            if not read_json(metadata)["enabled"]:
                return
            ready = start_preview_server(page, launcher, runtime)
            if ready is None:
                raise RuntimeError(f"could not start preview {page}")
            url, note = ready
            roots = layer_inputs(
                tuple(read_json(page / "registry.json")["$layer"]["packages"])
            )
            previous = snapshot(watch_paths(source, runtime, roots, identity["seed"]))
            candidate = previous
            preview_ready({"prepared": prepared, "url": url, "note": note}, ready_fd)
            print(
                f"Watching {source} and {runtime}; feedback stays in {page}", flush=True
            )
            serving = True
            while read_json(metadata)["enabled"]:
                time.sleep(0.25)
                if serving and not running_server(page):
                    return  # an explicit service stop or the owning session ended
                current = snapshot(
                    watch_paths(source, runtime, roots, identity["seed"])
                )
                if current == previous:
                    candidate = current
                    continue
                if current != candidate:
                    candidate = current
                    continue  # one quiet interval groups an editor's save batch
                previous = current
                cmd_stop(page)
                try:
                    refresh_preview(source, page, launcher, runtime, identity)
                    roots = layer_inputs(
                        tuple(read_json(page / "registry.json")["$layer"]["packages"])
                    )
                except (SystemExit, ValueError, OSError) as error:
                    print(
                        f"Preview update refused: {error}. Feedback is preserved; edit the inputs to retry.",
                        file=sys.stderr,
                        flush=True,
                    )
                if not read_json(metadata)["enabled"]:
                    return
                serving = start_preview_server(page, launcher, runtime) is not None
                if serving:
                    print(f"Reloaded {source.stem}", flush=True)
        finally:
            update_preview_state(page, enabled=False)
            cmd_stop(page)


def announce_preview(announcement: dict, log_path: Path | None) -> None:
    print(announcement["prepared"], end="\n\n", flush=True)
    print(announcement["note"], file=sys.stderr, flush=True)
    if log_path is not None:
        print(f"watch log {log_path}", file=sys.stderr, flush=True)
    print(announcement["url"], flush=True)


def start_preview_worker(
    source: Path, page: Path, runtime: Path, background: bool, stop: bool
) -> None:
    """Run in the selected checkout's uv environment, including --runtime previews."""
    command = [
        str(runtime / ".venv" / "bin" / "python"),
        str(Path(__file__).resolve()),
        "--source",
        str(source),
        "--runtime",
        str(runtime),
        "--_worker",
    ]
    # The caller's page path is retained even when the selected runtime is elsewhere.
    if page.parent == TMP / "previews":
        command.extend(("--slot", page.name))
    if stop:
        command.append("--stop")
    if not background:
        os.chdir(runtime)
        os.execv(command[0], command)
    _, _, log_path = preview_files(page)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    read_fd, write_fd = os.pipe()
    with log_path.open("a", encoding="utf-8") as log:
        child = subprocess.Popen(
            [*command, "--_ready-fd", str(write_fd)],
            cwd=runtime,
            stdout=log,
            stderr=log,
            pass_fds=(write_fd,),
            start_new_session=True,
        )
    os.close(write_fd)
    with os.fdopen(read_fd) as channel:
        message = channel.readline()
    if not message:
        child.wait()
        print(log_path.read_text(encoding="utf-8"), file=sys.stderr, end="")
        raise SystemExit(child.returncode or 1)
    announce_preview(json.loads(message), log_path)


def main() -> None:
    parser, args = arguments()
    if args._worker:
        runtime = args.runtime.resolve()
        source = args.source.resolve()
        page = preview_directory(source, args.slot)
        if args.stop:
            stop_preview(page)
        else:
            watch_preview(
                source, page, runtime / "bin" / "leaf", runtime, args._ready_fd
            )
        return
    runtime, launcher = checkout(parser, args.runtime)
    source = (
        args.source.expanduser().resolve()
        if args.stop and args.source
        else authored_source(parser, args.example, args.source)
    )

    if args.export:
        TMP.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="preview-export-", dir=TMP) as staging:
            page = Path(staging) / "page"
            data_sources, versions = prepare(source, page, launcher, runtime)
            suffix = f"-{args.slot}" if args.slot else ""
            out = TMP / f"example-{source.stem}{suffix}.html"
            out.unlink(missing_ok=True)
            leaf(launcher, runtime, "version", "export", str(page), "-o", str(out))
        print(preparation_note(source, data_sources, versions), end="\n\n")
        print(out.resolve())
        return

    page = preview_directory(source, args.slot)
    start_preview_worker(source, page, runtime, args.background, args.stop)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except (ValueError, OSError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
