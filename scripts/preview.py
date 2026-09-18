#!/usr/bin/env python3
"""Prepare an example or developer fixture as a live page or review file.

An example is authored content, not a page directory: Leaf adds its theme and
runtime when serving from the layer `page init` vendors. Opening one
from disk gets a dead page, because Chrome refuses ES modules from a file://
origin — nothing upgrades, and a tabbed page renders as every tab at once. This
script builds the directory the runtime expects, then watches the fixture and
selected runtime until Ctrl-C. `--export` writes the browser-drawn result as one
standalone HTML file instead.

The live result is a page, not a picture of one: it takes comments. Served from
an agent session, `leaf wait` on the same directory carries them to the agent and
the example gets revised like any other page. Outside an agent host, gestures remain
in the log until an agent claims the page. `--automation` uses the same temporary
page server as the browser harness: gestures traverse the real HTTP and event-log
boundary, but the server creates no claim or durable service.

An example can also ship companion `.jsonl` events and `.data.json` source
values. The first lets a page arrive mid-conversation; the second supplies the
same page-bound external data a real host would replace through `leaf data set`.

A source or layer edit stops the preview service, stamps changed source, and restarts
at the same URL. `watchfiles` owns the watching: it reports which paths changed and
groups an editor's save batch, so this script only says which paths it follows and
what each one means. A layer edit also re-vendors, through the normal compatibility
gate; a source edit alone does not, because vendoring mints a fresh layer generation
and a revision carrying one is a different program, which the browser can only follow
into a fresh document. So a prose edit here arrives the way it arrives for a reader,
patched into the page they are standing in. The page log
and reader decisions survive; a refused update stays visible in the terminal
or background log and is retried after the next edit. Existing slots resume.
Changing fixture identity or seeded history is refused so a slot keeps its feedback.
Use `--reset` to discard that feedback and rebuild the slot. `version stamp` lints
the example on the way past. The browser gate a page normally passes before its URL
goes out is left to the suite: `version check --render` and
`test_page_fixture_renders` drive the same `render_version` over the same files, so
running it here would only repeat what the suite has already said about these exact
pages.

Named slots let several previews coexist. `--source` keeps one authored fixture
fixed while `--runtime` vendors it from another Leaf checkout. `--background`
detaches the watcher and returns its URL instead of holding the terminal.

Usage: preview.py [page] [options]  (default: triage-board)
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
from functools import partial
from pathlib import Path
from typing import NamedTuple

from example_data import TEST_PAGES, example_versions
from page_fixtures import (
    DEFAULT_PACKAGES,
    media_source,
    package_selection_args,
    prepare_page,
    read_fixture,
    source_manifest,
    source_manifest_candidates,
    source_packages,
)

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"
NAMED_SOURCE_DIRS = (ROOT / "examples", ROOT / "examples" / "developer", TEST_PAGES)
SLOT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
# The watcher's own dependency, which the dev group beside this script declares. A
# checkout named by `--runtime` has the `--no-dev` environment `bin/leaf` syncs, so the
# worker command overlays it there. Move this floor whenever `pyproject.toml`'s moves.
WATCHER_PACKAGE = "watchfiles>=1.1.0"
# One interval serves two jobs: it is the quiet gap that closes an editor's save batch
# (`step`), and the idle wake-up at which the watcher re-reads its stop flag and the
# server's liveness (`rust_timeout`). `debounce` keeps watchfiles' 1.6s default ceiling,
# so writes that never go quiet still reach the page rather than starving there.
WATCH_INTERVAL_MS = 250


def leaf(
    launcher: Path,
    runtime: Path,
    *args,
    check: bool = True,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    show_output: bool = False,
) -> None:
    """Hide successful chatter; checked failures replay their stdout."""
    result = subprocess.run(
        [str(launcher), *args],
        cwd=runtime,
        env=env,
        check=False,
        input=input_text,
        stdout=None if show_output else subprocess.PIPE,
        text=True,
    )
    if check and result.returncode != 0:
        if not show_output and result.stdout:
            print(result.stdout, end="", flush=True)
        raise SystemExit(result.returncode)


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
        help="public example or developer fixture name (default: triage-board)",
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
    parser.add_argument(
        "--automation",
        action="store_true",
        help="watch through the process-owned browser harness",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="discard this preview's feedback and rebuild it from the fixture",
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
        "--stop", action="store_true", help="stop this preview watcher and its server"
    )
    parsed = parser.parse_args()
    if parsed.source and parsed.example:
        parser.error("choose an example name or --source, not both")
    if parsed.automation and (parsed.background or parsed.export):
        parser.error(
            "--automation is a foreground watcher; omit --background or --export"
        )
    if parsed.reset and (parsed.stop or parsed.export):
        parser.error("--reset starts a fresh preview; omit --stop or --export")
    return parser, parsed


def checkout(parser: argparse.ArgumentParser, value: Path) -> tuple[Path, Path]:
    runtime = value.expanduser().resolve()
    launcher = runtime / "bin" / "leaf"
    if not launcher.is_file():
        parser.error(f"{runtime} has no bin/leaf launcher")
    result = subprocess.run(
        [str(launcher), "--root"],
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
    name = (example or "triage-board").removesuffix(".html")
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


def preparation_note(source: Path, data_sources: int, versions: int) -> str:
    """Summarize successful setup without replaying each child command."""
    details = []
    if data_sources:
        data_label = "data source" if data_sources == 1 else "data sources"
        details.append(f"{data_sources} {data_label}")
    version_label = "version" if versions == 1 else "versions"
    details.append(f"{versions} {version_label}")
    return f"prepared {source.stem} ({', '.join(details)})"


def mark_preview(source: Path, page: Path, runtime: Path, *, automation: bool) -> None:
    """Identify the live runtime without exposing its absolute path to the browser."""
    layer = json.loads((page / "registry.json").read_text(encoding="utf-8"))["$layer"]
    producer = layer.get("producer", {})
    metadata = {
        "kind": "example",
        "example": source.stem,
        "checkout": runtime.name,
        "interaction": "automation" if automation else "reader",
        "started": datetime.now(timezone.utc).isoformat(),
        **({"commit": producer["commit"]} if "commit" in producer else {}),
        **({"dirty": producer["dirty"]} if "dirty" in producer else {}),
    }
    (page / "preview.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )


def preview_directory(source: Path, slot: str | None, automation: bool) -> Path:
    name = re.sub(r"[^A-Za-z0-9._-]", "-", source.stem).strip("._-")[:64] or "preview"
    if automation and slot is None:
        name = f"{name}-automation"
    return TMP / "previews" / (slot or name)


def preview_files(page: Path) -> tuple[Path, Path, Path]:
    """Developer ownership and diagnostics live beside the frozen page."""
    return tuple(
        page.with_name(f"{page.name}.preview.{suffix}")
        for suffix in ("json", "lock", "log")
    )


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
    capture_inputs = [
        operation["input_file"]
        for operation in read_fixture(source).data
        if operation["kind"] == "capture"
    ]
    paths = [
        source.with_suffix(".jsonl"),
        source.with_suffix(".data.json"),
        *example_versions(source)[:-1],
        *capture_inputs,
    ]
    return {str(path): digest(path) for path in paths}


def source_identity(source: Path, runtime: Path, automation: bool) -> dict:
    return {
        "source": str(source),
        "runtime": str(runtime),
        "seed": fixture_seed(source),
        "interaction": "automation" if automation else "reader",
    }


def refresh_preview(
    source: Path,
    page: Path,
    launcher: Path,
    runtime: Path,
    identity: dict,
    automation: bool,
    vendor: bool = True,
) -> None:
    """Replace only admitted layer/source changes; never recreate the page log.

    Runtime updates do not overwrite an agent's direct page edits. If the fixture
    and the live authored source both changed, neither silently wins.

    `vendor` re-copies the layer, which is what a runtime edit needs and what a prose
    edit must not do. Vendoring mints a fresh layer generation, and the generation is
    part of what a revision is as executable code, so re-vendoring on every save made
    every preview revision a different program from the one before it — and a preview,
    the one place this is watched by eye, could only ever show the reload path. The
    watcher re-vendors when the layer it watches changed, and copies the source alone
    when that is all that changed.
    """
    if source_identity(source, runtime, automation) != {
        key: identity[key] for key in ("source", "runtime", "seed", "interaction")
    }:
        raise ValueError(
            "fixture identity or seeded history changed; choose a new --slot to "
            "preserve feedback, or rerun with --reset to discard it"
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
    selection_args = package_selection_args(packages)
    # The page's own package selection is vendored too, so a source that changed which
    # packages it asks for needs the layer copied again whatever else stood still.
    vendored_packages = json.loads(
        (page / "registry.json").read_text(encoding="utf-8")
    )["$layer"]["packages"]
    if vendor or packages != vendored_packages:
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
                "Updated in the checkout",
            )
        except BaseException:
            authored.write_bytes(previous)
            raise
        identity["source_digest"] = incoming_digest
        update_preview_state(page, source_digest=identity["source_digest"])
    mark_preview(source, page, runtime, automation=automation)


class Watched(NamedTuple):
    """One filesystem subscription and what the paths it reports mean.

    `roots` is what watchfiles is given, each watched recursively, so a path that does
    not exist yet — a first `versions/` directory, a `media/` directory nearer the
    source than the layer's — still arrives as a change under the directory that will
    hold it. Every path in `paths` sits under one of those roots; a path that did not
    would be an input the preview had silently stopped following.
    """

    roots: tuple[Path, ...]
    paths: frozenset[str]
    layer: frozenset[str]


def watch_paths(source: Path, runtime: Path, roots: list[Path], seed: dict) -> Watched:
    """The inputs one preview follows, and which of them `page init` vendors.

    A reported path is matched against `paths` for whether it is watched at all, and
    against `layer` for whether the refresh re-copies the layer. The two are told
    apart because re-copying the layer changes what a revision is as executable code
    while editing the page's own source does not: a fresh layer generation makes the
    next revision a different program, which the browser can only follow into a fresh
    document, while a prose edit is a revision the reader keeps their page for.
    """
    from leaf.layer import input_paths

    # Every path is resolved before it enters a set or a subscription. `input_paths`
    # answers in resolved paths, and a watcher can report a change under the root
    # string it was given, so a package root reached through a symlink or a `..`
    # would otherwise name its changes in a form nothing here matches.
    runtime = runtime.resolve()
    scripts = runtime / "skills" / "leaf" / "scripts"
    resolved_roots = {root.resolve() for root in roots}
    # The layer reading follows a link inside a package as well as one at its root,
    # so a vendored file can resolve outside every package root.
    package = [
        path
        for path in input_paths(roots)
        if path not in resolved_roots and not path.is_dir()
    ]
    layer = {
        *(str(path) for path in package),
        *(str(path) for path in scripts.rglob("*.py")),
        str(runtime / "pyproject.toml"),
        str(runtime / "uv.lock"),
    }
    manifest = source_manifest(source)
    page = {
        path.resolve()
        for path in (
            source,
            *source_manifest_candidates(source),
            manifest or DEFAULT_PACKAGES,
            *(Path(path) for path in seed),
            *(source.parent / "versions").glob(f"{source.stem}.v*.html"),
            *media_source(source).rglob("*"),
            # The nearer of these two directories is the one the page's images come
            # from, so either arriving changes which images the refresh copies.
            source.parent / "media",
            *([manifest.parent / "media"] if manifest is not None else []),
        )
    }
    holders = sorted(
        {
            path
            for path in (
                *resolved_roots,
                scripts,
                runtime / "pyproject.toml",
                runtime / "uv.lock",
                *(path.parent for path in package),
                *(path.parent for path in page),
            )
            if path.exists()
        }
    )
    # A recursive root already covers everything below it, so keep only the outermost.
    # Sorted, an ancestor precedes its descendants. The subscription is then the same
    # set whether or not the page has media or prior versions yet, which is what keeps
    # it open — and collecting — across the refreshes those arriving files cause.
    subscribed: list[Path] = []
    for path in holders:
        if not any(root in path.parents for root in subscribed):
            subscribed.append(path)
    return Watched(
        tuple(subscribed),
        frozenset(layer | {str(path) for path in page}),
        frozenset(layer),
    )


def watch_changes(watched: Watched):
    """Subscribe to one watched set; the rust watcher starts on the first read."""
    from watchfiles import watch

    return watch(
        *watched.roots,
        step=WATCH_INTERVAL_MS,
        rust_timeout=WATCH_INTERVAL_MS,
        yield_on_timeout=True,
    )


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


def retire_preview(page: Path, *, discard: bool) -> None:
    """Wait for the watcher to retire, then optionally discard the preview."""
    from leaf.event_log import flocked
    from leaf.hosting import cmd_stop
    from leaf.leases import transition_lock
    from leaf.service import PageTransaction, claim_path

    metadata, lease_path, log_path = preview_files(page)
    state_lock = metadata.with_suffix(".state.lock")
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    update_preview_state(page, enabled=False)
    with flocked(lease_path):
        cmd_stop(page)
        if discard:
            with flocked(state_lock), flocked(transition_lock(page)):
                if (page / "events.jsonl").is_file():
                    with PageTransaction(page):
                        shutil.rmtree(page)
                elif page.exists():
                    shutil.rmtree(page)
                claim_path(page).unlink(missing_ok=True)
                metadata.unlink(missing_ok=True)
                log_path.unlink(missing_ok=True)


def stop_preview(page: Path) -> None:
    """Stop the selected watcher while preserving its page and feedback."""
    retire_preview(page, discard=False)
    print(f"stopped preview {page}", flush=True)


def reset_preview(page: Path) -> None:
    """Stop and discard the selected preview so its next start is fresh."""
    retire_preview(page, discard=True)


def preview_ready(
    announcement: dict, ready_fd: int | None, log_path: Path | None = None
) -> None:
    if ready_fd is None:
        announce_preview(announcement, log_path)
    else:
        with os.fdopen(ready_fd, "w") as channel:
            channel.write(json.dumps(announcement) + "\n")


def watch_preview(
    source: Path,
    page: Path,
    launcher: Path,
    runtime: Path,
    ready_fd: int | None,
    automation: bool,
) -> None:
    from leaf.event_log import flocked
    from leaf.files import read_json, write_json
    from leaf.host import session_harness
    from leaf.hosting import (
        TEMPORARY_SERVER_NOTE,
        TemporaryPageServer,
        cmd_stop,
        start_server,
        startup_note,
    )
    from leaf.layer import layer_inputs
    from leaf.leases import take_waiter_lease
    from leaf.server import running_server
    from leaf.service import PageTransaction

    metadata, lease_path, log_path = preview_files(page)
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    # Serialize startup intent against --stop, separately from the lifetime lease
    # that stop waits for after writing its intent.
    with flocked(metadata.with_suffix(".state.lock")):
        lease = take_waiter_lease(lease_path)
        identity = read_json(metadata)
        if lease is not None:
            expected = source_identity(source, runtime, automation)
            if page.exists() and (
                identity is None
                or expected
                != {
                    key: identity.get(key)
                    for key in ("source", "runtime", "seed", "interaction")
                }
            ):
                lease.close()
                raise ValueError(
                    f"{page} contains another fixture or changed seed history; "
                    "choose a new --slot to preserve feedback, or rerun with "
                    "--reset to discard it"
                )
            identity = (
                identity
                if page.exists()
                else {
                    **expected,
                    "source_digest": digest(source),
                }
            )
            write_json(metadata, {**identity, "enabled": True})
    if lease is None:
        expected = source_identity(source, runtime, automation)
        if identity and expected == {
            key: identity.get(key)
            for key in ("source", "runtime", "seed", "interaction")
        }:
            if automation:
                raise ValueError(
                    "automation preview already running; use the URL printed by its foreground command"
                )
            running = running_server(page)
            while running is None and (read_json(metadata) or {}).get("enabled"):
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
            f"a watcher already owns {page}; choose a new --slot to preserve it, "
            "or rerun with --reset to replace it"
        )
    temporary = None
    changes = None
    with lease:
        try:
            if automation and PageTransaction(page).active_claim is not None:
                raise ValueError(
                    f"{page} has an active task claim; choose a new --slot to "
                    "preserve it, or rerun with --reset to replace it"
                )
            if page.exists():
                if not automation:
                    cmd_stop(page)
                try:
                    refresh_preview(
                        source, page, launcher, runtime, identity, automation
                    )
                except (SystemExit, ValueError, OSError) as error:
                    print(
                        f"Preview update refused: {error}. Feedback is preserved; edit the inputs to retry.",
                        file=sys.stderr,
                        flush=True,
                    )
                prepared = f"resumed {source.stem} (feedback preserved)"
            else:
                prepared_page = prepare_page(
                    page,
                    read_fixture(source),
                    partial(leaf, launcher, runtime),
                )
                mark_preview(source, page, runtime, automation=automation)
                prepared = preparation_note(
                    source, prepared_page.data_sources, prepared_page.versions
                )
            if not read_json(metadata)["enabled"]:
                return
            if automation:
                temporary = TemporaryPageServer(page).start()
                url, note = temporary.url, TEMPORARY_SERVER_NOTE
            else:
                ready = start_preview_server(page, launcher, runtime)
                if ready is None:
                    raise RuntimeError(f"could not start preview {page}")
                url, note = ready
            roots = layer_inputs(
                tuple(read_json(page / "registry.json")["$layer"]["packages"])
            )
            watched = watch_paths(source, runtime, roots, identity["seed"])
            changes = watch_changes(watched)
            preview_ready({"prepared": prepared, "url": url, "note": note}, ready_fd)
            print(
                f"Watching {source} and {runtime}; feedback stays in {page}", flush=True
            )
            serving = True
            while read_json(metadata)["enabled"]:
                reported = {path for _, path in next(changes)}
                live = temporary.running if automation else running_server(page)
                if serving and not live:
                    return  # an explicit service stop or the owning session ended
                if not serving and not automation:
                    # A refused restart has no service watching the claim's
                    # lifetime. Lost ownership ends this watcher as well.
                    with PageTransaction(page) as state:
                        if not state.owned_by(session_harness()):
                            return
                if not reported:
                    continue  # the idle wake-up that carried the two checks above
                # An added input is only in the reading taken after it arrived, and a
                # deleted one only in the reading taken while it was still there.
                current = watch_paths(source, runtime, roots, identity["seed"])
                if not reported & (watched.paths | current.paths):
                    continue
                vendored = bool(reported & (watched.layer | current.layer))
                if automation:
                    token, port = temporary.token, temporary.port
                    temporary.close()
                    temporary = None
                else:
                    cmd_stop(page)
                try:
                    refresh_preview(
                        source,
                        page,
                        launcher,
                        runtime,
                        identity,
                        automation,
                        vendor=vendored,
                    )
                    roots = layer_inputs(
                        tuple(read_json(page / "registry.json")["$layer"]["packages"])
                    )
                    rebuilt = watch_paths(source, runtime, roots, identity["seed"])
                except (SystemExit, ValueError, OSError) as error:
                    print(
                        f"Preview update refused: {error}. Feedback is preserved; edit the inputs to retry.",
                        file=sys.stderr,
                        flush=True,
                    )
                    rebuilt = current
                if rebuilt.roots != watched.roots:
                    # A refresh can change which packages the page vendors, and a
                    # subscription is fixed for its lifetime. Holding the old one
                    # wherever the roots stand still keeps the edits made during the
                    # refresh, which the rust watcher collected while this was busy.
                    changes.close()
                    changes = watch_changes(rebuilt)
                watched = rebuilt
                if not read_json(metadata)["enabled"]:
                    return
                if automation:
                    temporary = TemporaryPageServer(
                        page, token=token, port=port
                    ).start()
                    serving = True
                else:
                    # Ownership was claimed while the launch still had its host
                    # ancestor. A detached refresh preserves that lifetime; the
                    # serving child validates the retained claim before restarting.
                    serving = start_server(page) is not None
                if serving:
                    print(f"Reloaded {source.stem}", flush=True)
        finally:
            update_preview_state(page, enabled=False)
            if changes is not None:
                changes.close()
            if temporary is not None:
                temporary.close()
            elif not automation:
                cmd_stop(page)


def announce_preview(announcement: dict, log_path: Path | None) -> None:
    print(announcement["prepared"], end="\n\n", flush=True)
    print(announcement["note"], file=sys.stderr, flush=True)
    if log_path is not None:
        print(f"watch log {log_path}", file=sys.stderr, flush=True)
    print(announcement["url"], flush=True)


def start_preview_worker(
    source: Path,
    page: Path,
    runtime: Path,
    background: bool,
    stop: bool,
    automation: bool,
    reset: bool,
) -> None:
    """Run in the selected checkout's uv environment, including --runtime previews.

    That environment is the one `bin/leaf` syncs, which carries no dev group, so the
    watcher's own dependency is overlaid onto it rather than installed into it.
    """
    command = [
        "uv",
        "run",
        "-q",
        "--no-dev",
        "--project",
        str(runtime),
        "--with",
        WATCHER_PACKAGE,
        "python",
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
    if automation:
        command.append("--automation")
    if reset:
        result = subprocess.run([*command, "--reset"], cwd=runtime, check=False)
        if result.returncode:
            raise SystemExit(result.returncode)
    if stop:
        command.append("--stop")
    if not background:
        os.chdir(runtime)
        os.execvp(command[0], command)
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
        page = preview_directory(source, args.slot, args.automation)
        if args.reset:
            reset_preview(page)
        elif args.stop:
            stop_preview(page)
        else:
            watch_preview(
                source,
                page,
                runtime / "bin" / "leaf",
                runtime,
                args._ready_fd,
                args.automation,
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
            prepared = prepare_page(
                page,
                read_fixture(source),
                partial(leaf, launcher, runtime),
            )
            suffix = f"-{args.slot}" if args.slot else ""
            out = TMP / f"example-{source.stem}{suffix}.html"
            out.unlink(missing_ok=True)
            leaf(launcher, runtime, "version", "export", str(page), "-o", str(out))
        print(
            preparation_note(source, prepared.data_sources, prepared.versions),
            end="\n\n",
        )
        print(out.resolve())
        return

    page = preview_directory(source, args.slot, args.automation)
    start_preview_worker(
        source,
        page,
        runtime,
        args.background,
        args.stop,
        args.automation,
        args.reset,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except (ValueError, OSError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
