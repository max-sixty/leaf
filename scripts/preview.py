#!/usr/bin/env python3
"""Prepare an example or developer fixture as a live page or review file.

An example is authored content, not a page directory: Leaf adds its theme and
runtime when serving from the layer `page init` vendors. Opening one
from disk gets a dead page, because Chrome refuses ES modules from a file://
origin — nothing upgrades, and a tabbed page renders as every tab at once. This
script builds the directory the runtime expects, then watches the fixture and
selected runtime until Ctrl-C. `--export` writes the browser-drawn result as one
standalone HTML file instead.

The live result is a page, not a picture of one: it takes comments. They cross the
real HTTP and event-log boundary and settle in the page's log, which is all a
preview does with them.

`--reader` hands the preview to someone else. It claims the page for this session,
which puts the page in the session's delivery loop: presses arrive as reader input,
`leaf wait` carries them, and the Stop hook holds the turn open until each is
answered. A session driving its own preview would read every gesture it makes back
as reader input, so nothing claims a preview unless this flag asks for it.

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
`LEAF_PREVIEWS_ROOT` moves where slots live, which is how the suite keeps its own
out of the checkout and out of the way of a developer's standing preview.

A slot is its page directory. The fixture it was built from, the digest of the
source last stamped into it, and the browser chrome's own preview identity are
one record in the page's `preview.json`, written only by the watcher that holds
the slot. A background watcher's log sits beside the directory and belongs to the
launcher that names it, which clears it on `--reset`. The watcher's lifetime lease
and a stop's request are page locks in the state home, where the page's transition
lease already lives, so a discard removes the page and its claim and a stop cannot
end up waiting on an inode the discard replaced.

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
# What a slot's own `preview.json` records for this script rather than for the browser:
# the fixture and checkout it was built from, the seeded history that was installed
# once, which interaction it serves, and the digest of the source last stamped into it.
SLOT_KEYS = ("source", "runtime", "seed", "interaction", "source_digest")


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
        "--reader",
        action="store_true",
        help="hand this preview to a reader: claim the page so presses arrive as feedback",
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
    if parsed.reader and parsed.export:
        parser.error("--reader serves a page; omit --export")
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


def mark_preview(source: Path, page: Path, runtime: Path, identity: dict) -> None:
    """Record the whole slot: the preview a reader sees, and the fixture behind it.

    The first fields are the ones the server projects into preview chrome; the
    identity beside them is this script's own bookkeeping, and the server serves
    neither this file nor an absolute checkout path.
    """
    from leaf.files import write_json

    layer = json.loads((page / "registry.json").read_text(encoding="utf-8"))["$layer"]
    producer = layer.get("producer", {})
    write_json(
        page / "preview.json",
        {
            "kind": "example",
            "example": source.stem,
            "checkout": runtime.name,
            "started": datetime.now(timezone.utc).isoformat(),
            **({"commit": producer["commit"]} if "commit" in producer else {}),
            **({"dirty": producer["dirty"]} if "dirty" in producer else {}),
            **identity,
        },
    )


def previews_root() -> Path:
    """Where this command's slots live.

    Read per call rather than at import, so a test that sets the variable resolves
    the same directory the preview it launches will. The suite points it at its
    own temporary root: a slot is a page directory the checkout's `.tmp` otherwise
    keeps forever, and a preview left running there by a developer is a page the
    suite would find and count. The launcher hands the worker this answer, already
    resolved, since the worker runs in the selected checkout and would read a
    relative setting against a different directory.
    """
    return Path(os.environ.get("LEAF_PREVIEWS_ROOT") or TMP / "previews").resolve()


def preview_directory(source: Path, slot: str | None, reader: bool) -> Path:
    if slot:
        return previews_root() / slot
    # The suffix is part of the name `--slot` carries into the worker, so it comes
    # out of the ceiling rather than past it.
    suffix = "-reader" if reader else ""
    stem = re.sub(r"[^A-Za-z0-9._-]", "-", source.stem).strip("._-")
    return previews_root() / ((stem[: 64 - len(suffix)] or "preview") + suffix)


def preview_log(page: Path) -> Path:
    """A background watcher's diagnostics, beside the page it follows."""
    return page.with_name(f"{page.name}.preview.log")


def watcher_note(page: Path) -> str:
    """What ends an unclaimed preview, in the shape a serve states its lifetime.

    `leaf server`'s own note reads the lifetime off `service.json`, and a preview
    nobody was handed writes none. Both things that end one are said here: the
    watcher holds the server, and inside an agent host `PreviewService.running`
    ends the watcher with the session — which a detached preview's URL outlives
    silently unless the line that hands it over says so.
    """
    from leaf.host import session_harness

    ends = "stops with its watcher"
    if session_harness() is not None:
        ends += " and with this agent session"
    return "\n".join(
        (
            f"server   preview (no task claim; {ends})",
            f"stop     scripts/preview.py --slot {page.name} --stop",
        )
    )


def preview_locks(page: Path) -> tuple[Path, Path]:
    """The watcher's lifetime lease and a stop's request, keyed by the page.

    Both sit in the state home beside the page's own transition lease, because a
    lock inside what it guards is an inode a discard unlinks, and a lock on a
    replaced inode excludes nobody: a `--reset` would hand a waiting `--stop` an
    orphaned lock and let it stop the server the reset had just started.
    """
    from leaf.leases import page_lock

    return page_lock(page, "preview"), page_lock(page, "preview-stop")


def slot_identity(page: Path) -> dict | None:
    """The fixture this slot holds, as its own page records it.

    Only the watcher's own keys, so resuming a slot cannot carry the browser
    chrome of the run that prepared it back into the record.
    """
    from leaf.files import read_json

    recorded = read_json(page / "preview.json")
    if recorded is None:
        return None
    return {key: recorded[key] for key in SLOT_KEYS if key in recorded}


def refresh_media(source: Path, page: Path) -> None:
    """Add immutable assets; historical revisions may still reference every copy.

    The assets go in as one set through the writer every other page file uses, so a
    name that already means something here is refused before any of them lands.
    """
    from leaf.files import replace_files

    media = media_source(source)
    writes = []
    for path in sorted(media.rglob("*")):
        if not path.is_file():
            continue
        target = page / "media" / path.relative_to(media)
        if digest(target) not in (None, digest(path)):
            raise ValueError(
                f"media/{path.relative_to(media)} has different bytes in the preview; use a new filename to preserve historical revisions"
            )
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            writes.append((target, path.read_bytes(), False))
    if writes:
        replace_files(writes)


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


def source_identity(source: Path, runtime: Path, reader: bool) -> dict:
    return {
        "source": str(source),
        "runtime": str(runtime),
        "seed": fixture_seed(source),
        "interaction": "reader" if reader else "author",
    }


def identifies(identity: dict | None, expected: dict) -> bool:
    """Whether a recorded slot holds exactly the fixture this command asks for."""
    return (
        identity is not None
        and {key: identity.get(key) for key in expected} == expected
    )


def crossed_interaction(identity: dict | None, expected: dict) -> str | None:
    """The interaction a slot already serves, where this command asked for the other.

    A slot keeps its interaction for its life, and the fixture it was built from
    is usually the same one, so the refusal that covers both reads as a complaint
    about the fixture. One flag decides this half, and naming it is the remedy.
    """
    recorded = (identity or {}).get("interaction")
    if recorded is None or recorded == expected["interaction"]:
        return None
    flag = "add" if recorded == "reader" else "drop"
    return f"serves its {recorded} interaction; {flag} --reader to join it"


def refused(reason) -> bool:
    """Say why the page the reader has is the page that stays up."""
    print(
        f"Preview update refused: {reason}. Feedback is preserved; edit the inputs to retry.",
        file=sys.stderr,
        flush=True,
    )
    return False


def refresh_preview(
    source: Path,
    page: Path,
    launcher: Path,
    runtime: Path,
    identity: dict,
    reader: bool,
    vendor: bool = True,
) -> bool:
    """Replace only admitted layer/source changes; never recreate the page log.

    Runtime updates do not overwrite an agent's direct page edits. If the fixture
    and the live authored source both changed, neither silently wins. A refused
    update is reported and answered False: the page the reader has stays as it
    was, and the next edit to the inputs is another try.

    `vendor` re-copies the layer, which is what a runtime edit needs and what a prose
    edit must not do. Vendoring mints a fresh layer generation, and the generation is
    part of what a revision is as executable code, so re-vendoring on every save made
    every preview revision a different program from the one before it — and a preview,
    the one place this is watched by eye, could only ever show the reload path. The
    watcher re-vendors when the layer it watches changed, and copies the source alone
    when that is all that changed.
    """
    if not identifies(identity, source_identity(source, runtime, reader)):
        return refused(
            "fixture identity or seeded history changed; choose a new --slot to "
            "preserve feedback, or rerun with --reset to discard it"
        )
    try:
        incoming = source.read_bytes()
        incoming_digest = hashlib.sha256(incoming).hexdigest()
        source_changed = incoming_digest != identity["source_digest"]
        authored = page / "index.html"
        if source_changed and digest(authored) not in (
            identity["source_digest"],
            incoming_digest,
        ):
            return refused(
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
        mark_preview(source, page, runtime, identity)
    except (SystemExit, ValueError, OSError) as error:
        return refused(error)
    return True


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
    """Subscribe to one watched set, collecting from before this returns.

    watchfiles starts its rust watcher on the subscription's first read, so a
    subscription nobody has read yet is watching nothing. Reading once here is
    what lets the caller announce a URL knowing that an edit made the moment it
    appears is already being collected — the gap otherwise sat exactly where a
    developer starts a preview and edits the source they started it on, and the
    edit was lost. That first batch is handed on as the caller's own first.
    """
    from watchfiles import watch

    stream = watch(
        *watched.roots,
        step=WATCH_INTERVAL_MS,
        rust_timeout=WATCH_INTERVAL_MS,
        yield_on_timeout=True,
    )
    collected = next(stream)

    def watching():
        try:
            yield collected
            yield from stream
        finally:
            stream.close()

    return watching()


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


class PreviewService:
    """However this preview owns a server, for as long as it wants one up.

    A preview holds a process-owned server on a retained address, so no claim or
    service record outlives its watcher. `--reader` serves the page's durable
    service instead, claimed and started through the selected checkout's launcher
    and revived in place after each update, so the page belongs to this session
    and the URL a reader was handed survives every reload and every `leaf wait`.
    Nothing else about a preview differs, so the two are told apart here and
    nowhere else in its lifetime.
    """

    def __init__(self, page: Path, launcher: Path, runtime: Path, reader: bool):
        from leaf.host import session_harness
        from leaf.service import claim_lifetime

        self.page = page
        self.launcher = launcher
        self.runtime = runtime
        self.reader = reader
        self.temporary = None
        self.address: dict = {}
        self.claimed = False
        # A reader preview is reaped through its claim: the serving process
        # exits when the session's lifetime ends, and `running` reads that from
        # the empty service. An unclaimed preview holds its server in a thread of
        # its own and nothing outside it would notice, so it reads the same
        # lifetime here and ends itself. `claim_is_active` is that one reading,
        # and a harness states the fields it consumes. Outside an agent host
        # there is no session to outlive and the watcher runs until it is
        # stopped.
        harness = None if reader else session_harness()
        self.lifetime = None if harness is None else claim_lifetime(page, harness)

    def start(self) -> tuple[str, str] | None:
        """Put the server up and report its URL and lifetime note, or None."""
        from leaf.hosting import TemporaryPageServer, start_server

        if not self.reader:
            self.temporary = TemporaryPageServer(self.page, **self.address).start()
            self.address = {
                "token": self.temporary.token,
                "port": self.temporary.port,
            }
            return self._serving(self.temporary.url, watcher_note(self.page))
        if self.claimed:
            # Ownership was claimed while the launch still had its host ancestor.
            # A detached refresh preserves that lifetime; the serving child
            # validates the retained claim before restarting.
            return self._serving(*(start_server(self.page) or (None, None)))
        ready = start_preview_server(self.page, self.launcher, self.runtime)
        self.claimed = ready is not None
        return self._serving(*(ready or (None, None)))

    def stop(self) -> None:
        """Take the server down, keeping whatever a restart has to reuse."""
        from leaf.hosting import cmd_stop

        if self.reader:
            cmd_stop(self.page)
        elif self.temporary is not None:
            self.temporary.close()
            self.temporary = None
        self._serving(None, None)

    def _serving(self, url: str | None, note: str | None) -> tuple[str, str] | None:
        """Record where this slot answers and what ends it, or that it answers nowhere.

        A watcher that has detached is the only thing that knows either. An
        unclaimed preview writes no `service.json` to leave its address in, and
        its lifetime is this process's: a second invocation asking its own
        environment would answer for itself rather than for the watcher, and get
        the agent session wrong in both directions. Both are written at every
        transition rather than once, so a joiner is never handed a server that
        has gone.
        """
        from leaf.files import read_json, write_json

        recorded = read_json(self.page / "preview.json")
        serving = {"url": url, "note": note}
        if (
            recorded is not None
            and {key: recorded.get(key) for key in serving} != serving
        ):
            write_json(self.page / "preview.json", {**recorded, **serving})
        return None if url is None else (url, note)

    @property
    def running(self) -> bool:
        from leaf.server import running_server
        from leaf.service import claim_is_active

        if not self.reader:
            return (
                self.temporary is not None
                and self.temporary.running
                and (self.lifetime is None or claim_is_active(self.lifetime))
            )
        return running_server(self.page) is not None


def retire_preview(page: Path, *, discard: bool) -> None:
    """Wait for the watcher to retire, then optionally discard the preview.

    The stop is a request held open for as long as this command waits, rather
    than a flag written down: the watcher reads it between passes and at every
    point it would restart the server, so an update already running finishes and
    its pending restart is suppressed. A watcher that starts after this returns
    is a preview the developer asked for after asking for this one to stop, and
    nothing here can be left behind to stop it too.
    """
    from leaf.event_log import flocked
    from leaf.hosting import cmd_stop
    from leaf.leases import transition_lock
    from leaf.service import PageTransaction, claim_path

    lease_path, stop_path = preview_locks(page)
    with flocked(stop_path), flocked(lease_path):
        cmd_stop(page)
        if discard:
            with flocked(transition_lock(page)):
                if (page / "events.jsonl").is_file():
                    with PageTransaction(page):
                        shutil.rmtree(page)
                elif page.exists():
                    shutil.rmtree(page)
                claim_path(page).unlink(missing_ok=True)


def preview_ready(
    announcement: dict, ready_fd: int | None, log_path: Path | None = None
) -> None:
    if ready_fd is None:
        announce_preview(announcement, log_path)
    else:
        with os.fdopen(ready_fd, "w") as channel:
            channel.write(json.dumps(announcement) + "\n")


def join_running_preview(
    source: Path,
    page: Path,
    lease_path: Path,
    expected: dict,
    ready_fd: int | None,
) -> None:
    """Report where the watcher that already holds this slot serves it, or why not.

    An owner in the middle of an update has no server to name yet, and one still
    preparing a fresh slot has not yet recorded what it is preparing, so the wait
    is on the lease this command could not take rather than on either reading.

    The owner records where it answers and what ends it, whichever kind of server
    it holds, so both are read back here rather than rebuilt. Neither is this
    command's to rebuild: an unclaimed preview has no `service.json` to read an
    address off, and the lifetime belongs to the process that took it.
    """
    from leaf.files import read_json
    from leaf.leases import lock_is_held

    while lock_is_held(lease_path):
        identity = slot_identity(page)
        if identity is not None:
            if crossed := crossed_interaction(identity, expected):
                raise ValueError(
                    f"a watcher already owns {page} and {crossed}, or rerun with "
                    "--reset to replace it"
                )
            if not identifies(identity, expected):
                raise ValueError(
                    f"a watcher already owns {page}; choose a new --slot to "
                    "preserve it, or rerun with --reset to replace it"
                )
            recorded = read_json(page / "preview.json") or {}
            if url := recorded.get("url"):
                preview_ready(
                    {
                        "prepared": f"watching {source.stem} (feedback preserved)",
                        "url": url,
                        "note": recorded["note"],
                    },
                    ready_fd,
                    preview_log(page),
                )
                return
        time.sleep(0.05)
    raise ValueError(f"preview {page} was stopped while starting")


def watch_preview(
    source: Path,
    page: Path,
    launcher: Path,
    runtime: Path,
    ready_fd: int | None,
    reader: bool,
) -> None:
    """Take the slot and serve it, or report the watcher that already holds it."""
    from leaf.leases import take_waiter_lease
    from leaf.service import PageTransaction

    lease_path, stop_path = preview_locks(page)
    expected = source_identity(source, runtime, reader)
    lease = take_waiter_lease(lease_path)
    if lease is None:
        join_running_preview(source, page, lease_path, expected, ready_fd)
        return
    with lease:
        identity = (
            slot_identity(page)
            if page.exists()
            else {**expected, "source_digest": digest(source)}
        )
        if crossed := crossed_interaction(identity, expected):
            raise ValueError(f"{page} {crossed}, or rerun with --reset to rebuild it")
        if not identifies(identity, expected):
            raise ValueError(
                f"{page} contains another fixture or changed seed history; "
                "choose a new --slot to preserve feedback, or rerun with "
                "--reset to discard it"
            )
        if not reader and PageTransaction(page).active_claim is not None:
            raise ValueError(
                f"{page} has an active task claim; choose a new --slot to "
                "preserve it, or rerun with --reset to replace it"
            )
        serve_preview(
            source, page, launcher, runtime, identity, stop_path, ready_fd, reader
        )


def serve_preview(
    source: Path,
    page: Path,
    launcher: Path,
    runtime: Path,
    identity: dict,
    stop_path: Path,
    ready_fd: int | None,
    reader: bool,
) -> None:
    """Serve this slot's page and follow its inputs until something stops it.

    A held stop request is what ends this: it is read between passes and again
    wherever the server would come back up, so an update in flight finishes and
    the restart it would have made is suppressed.
    """
    from leaf.files import read_json
    from leaf.host import session_harness
    from leaf.layer import layer_inputs
    from leaf.leases import lock_is_held
    from leaf.service import PageTransaction

    service = PreviewService(page, launcher, runtime, reader)
    changes = None
    try:
        if page.exists():
            service.stop()
            refresh_preview(source, page, launcher, runtime, identity, reader)
            prepared = f"resumed {source.stem} (feedback preserved)"
        else:
            page.parent.mkdir(parents=True, exist_ok=True)
            prepared_page = prepare_page(
                page,
                read_fixture(source),
                partial(leaf, launcher, runtime),
            )
            mark_preview(source, page, runtime, identity)
            prepared = preparation_note(
                source, prepared_page.data_sources, prepared_page.versions
            )
        if lock_is_held(stop_path):
            raise ValueError(f"preview {page} was stopped while starting")
        ready = service.start()
        if ready is None:
            raise RuntimeError(f"could not start preview {page}")
        url, note = ready
        roots = layer_inputs(
            tuple(read_json(page / "registry.json")["$layer"]["packages"])
        )
        watched = watch_paths(source, runtime, roots, identity["seed"])
        changes = watch_changes(watched)
        preview_ready({"prepared": prepared, "url": url, "note": note}, ready_fd)
        print(f"Watching {source} and {runtime}; feedback stays in {page}", flush=True)
        serving = True
        while not lock_is_held(stop_path):
            reported = {path for _, path in next(changes)}
            if serving and not service.running:
                return  # an explicit service stop or the owning session ended
            if not serving and reader:
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
            service.stop()
            if refresh_preview(
                source, page, launcher, runtime, identity, reader, vendor=vendored
            ):
                roots = layer_inputs(
                    tuple(read_json(page / "registry.json")["$layer"]["packages"])
                )
                rebuilt = watch_paths(source, runtime, roots, identity["seed"])
            else:
                rebuilt = current
            if rebuilt.roots != watched.roots:
                # A refresh can change which packages the page vendors, and a
                # subscription is fixed for its lifetime. Holding the old one
                # wherever the roots stand still keeps the edits made during the
                # refresh, which the rust watcher collected while this was busy.
                changes.close()
                changes = watch_changes(rebuilt)
            watched = rebuilt
            if lock_is_held(stop_path):
                return
            serving = service.start() is not None
            if serving:
                print(f"Reloaded {source.stem}", flush=True)
    finally:
        if changes is not None:
            changes.close()
        service.stop()


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
    reader: bool,
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
        "--slot",
        page.name,
        "--_worker",
    ]
    # The worker runs in the selected checkout, so it is handed the slot by name and
    # the root as this launcher resolved it, rather than reading a relative setting
    # against a directory of its own.
    os.environ["LEAF_PREVIEWS_ROOT"] = str(page.parent)
    if reader:
        command.append("--reader")
    if reset:
        # The log is the launcher's: it names it to the developer and hands it to the
        # watcher as its output, so the old watcher's lines are cleared here rather
        # than by the worker's discard, which would unlink the file this launcher has
        # already opened for the new watcher and leave the name pointing nowhere.
        preview_log(page).unlink(missing_ok=True)
        command.append("--reset")
    if stop:
        command.append("--stop")
    if not background:
        os.chdir(runtime)
        os.execvp(command[0], command)
    log_path = preview_log(page)
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
        page = preview_directory(source, args.slot, args.reader)
        if args.stop:
            retire_preview(page, discard=False)
            print(f"stopped preview {page}", flush=True)
            return
        if args.reset:
            # Discarding and serving are one worker, so the slot is free for as
            # little as it takes to take its lease, and a reset costs one
            # environment rather than two.
            retire_preview(page, discard=True)
        watch_preview(
            source,
            page,
            runtime / "bin" / "leaf",
            runtime,
            args._ready_fd,
            args.reader,
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

    page = preview_directory(source, args.slot, args.reader)
    start_preview_worker(
        source,
        page,
        runtime,
        args.background,
        args.stop,
        args.reader,
        args.reset,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except (ValueError, OSError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
