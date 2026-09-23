#!/usr/bin/env python3
"""Prepare an example or developer fixture as a live page or review file.

An example is authored content, not a page directory: Leaf adds its theme and
runtime when serving from the layer `page init` vendors. Opening one
from disk gets a dead page, because Chrome refuses ES modules from a file://
origin — nothing upgrades, and a tabbed page renders as every tab at once. This
script builds the directory the runtime expects, then watches the fixture and
selected runtime until stopped. `--export` writes the browser-drawn result as one
standalone HTML file instead.

The live result is a page, not a picture of one: it takes comments. They cross the
real HTTP and event-log boundary and settle in the page's log, which is all a
preview does with them.

`--user` hands the preview to someone else. It claims the page for this session,
which puts the page in the session's delivery loop: presses arrive as user input,
`leaf wait` carries them, and the Stop hook holds the turn open until each is
answered. A session driving its own preview would read every gesture it makes back
as user input, so nothing claims a preview unless this flag asks for it.

An example can also ship companion `.jsonl` events and `.data.json` source
values. The first lets a page arrive mid-conversation; the second supplies the
same page-bound external data a real host would replace through `leaf data set`.

A preview is a foreground process, like any dev server: it prints its URL and
serves until it is interrupted or terminated, and whoever started it stops it — a
terminal's Ctrl-C, or the agent host's own background runner, which lists and
stops it like any other long-running command. SIGTERM takes
the same cleanup path as Ctrl-C. The one process a preview does not hold is a
`--user` preview's durable service, which serves in a session of its own: the
preview stops it on the way out, and the claim's lifetime ends it if the preview
was killed outright.

A slot's page lives exactly as long as that process. A start discards whatever an
earlier one left in the slot — page and claim — and builds the page fresh from the
fixture, so a preview never carries history the fixture no longer describes and
never has to refuse one it cannot reconcile. A start into a slot another preview
is still serving is refused, since that process is its owner's to stop. The page's feedback is what a restart costs. For a `--user`
preview that includes any move the claim was still carrying: discarding the page
releases the claim, so the Stop hook stops holding the turn for moves that no
longer exist. Until the next start, a stopped preview's page stays readable.

While a preview runs, a source or layer edit stops its server, stamps changed
source, and restarts at the same URL. `watchfiles` owns the watching: it reports
which paths changed and groups an editor's save batch, so this script only says
which paths it follows and what each one means. A layer edit also re-vendors,
through the normal compatibility gate; a source edit alone does not, because
vendoring mints a fresh layer generation and a revision carrying one is a different
program, which the browser can only follow into a fresh document. So a prose edit
here arrives the way it arrives for a user, patched into the page they are standing
in. The page log and user decisions survive; a refused update stays visible in the
output and is retried after the next edit. Seeded history is installed once, when
the page is built, so a change to it is refused until the preview is restarted.
`version stamp` lints the example on the way past. The browser gate a page normally
passes before its URL goes out is left to the suite: `version check --render` and
`test_page_fixture_renders` drive the same `render_version` over the same files, so
running it here would only repeat what the suite has already said about these exact
pages.

Named slots let several previews coexist. `--source` keeps one authored fixture
fixed while `--runtime` vendors it from another Leaf checkout. `LEAF_PREVIEWS_ROOT`
moves where slots live, which is how the suite keeps its own out of the checkout
and out of the way of a developer's standing preview.

A slot is its page directory, and `preview.json` in it is what the browser chrome
and the Stop hook read to know the page is a preview. The lease that says a
preview is serving the slot is a page lock in the state home, where the page's
transition lease already lives, so discarding the page cannot replace the inode
the lease is held on.

Usage: preview.py [page] [options]  (default: triage-board)
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
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
# (`step`), and the idle wake-up at which the watcher re-reads the server's liveness
# (`rust_timeout`). `debounce` keeps watchfiles' 1.6s default ceiling,
# so writes that never go quiet still reach the page rather than starving there.
WATCH_INTERVAL_MS = 250


class LeafFailed(RuntimeError):
    """A checked `leaf` command exited nonzero, having already said why.

    Its own type rather than `SystemExit`, so a refresh can refuse a failed update
    without also swallowing the exit a SIGTERM raises.
    """


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
        raise LeafFailed(f"leaf {' '.join(args[:2])} exited {result.returncode}")


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
        "--user",
        action="store_true",
        help="hand this preview to a user: claim the page so presses arrive as feedback",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="write a standalone HTML file instead of serving the page",
    )
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    parsed = parser.parse_args()
    if parsed.source and parsed.example:
        parser.error("choose an example name or --source, not both")
    if parsed.user and parsed.export:
        parser.error("--user serves a page; omit --export")
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


def mark_preview(source: Path, page: Path, runtime: Path, user: bool) -> None:
    """Record the preview the browser chrome labels, and mark the page as one.

    The server projects these fields into preview chrome and serves neither this
    file nor an absolute checkout path.
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
            "interaction": "user" if user else "author",
            "started": datetime.now(timezone.utc).isoformat(),
            **({"commit": producer["commit"]} if "commit" in producer else {}),
            **({"dirty": producer["dirty"]} if "dirty" in producer else {}),
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


def preview_directory(source: Path, slot: str | None, user: bool) -> Path:
    if slot:
        return previews_root() / slot
    # The suffix is part of the name `--slot` carries into the worker, so it comes
    # out of the ceiling rather than past it.
    suffix = "-user" if user else ""
    stem = re.sub(r"[^A-Za-z0-9._-]", "-", source.stem).strip("._-")
    return previews_root() / ((stem[: 64 - len(suffix)] or "preview") + suffix)


WATCHER_NOTE = "server   preview (no task claim; stops with this process)"


def preview_lease(page: Path) -> Path:
    """The lock a running preview holds on its slot, keyed by the page.

    It sits in the state home beside the page's own transition lease, because a
    lock inside what it guards is an inode a discard unlinks, and a lock on a
    replaced inode excludes nobody.
    """
    from leaf.leases import page_lock

    return page_lock(page, "preview")


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
    """Seed history is installed once, never replayed over user feedback."""
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


def refused(reason) -> bool:
    """Say why the page the user has is the page that stays up."""
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
    state: dict,
    user: bool,
    vendor: bool = True,
) -> bool:
    """Replace only admitted layer/source changes; never recreate the page log.

    Runtime updates do not overwrite an agent's direct page edits. If the fixture
    and the live authored source both changed, neither silently wins. A refused
    update is reported and answered False: the page the user has stays as it
    was, and the next edit to the inputs is another try.

    `vendor` re-copies the layer, which is what a runtime edit needs and what a prose
    edit must not do. Vendoring mints a fresh layer generation, and the generation is
    part of what a revision is as executable code, so re-vendoring on every save made
    every preview revision a different program from the one before it — and a preview,
    the one place this is watched by eye, could only ever show the reload path. The
    watcher re-vendors when the layer it watches changed, and copies the source alone
    when that is all that changed.
    """
    if fixture_seed(source) != state["seed"]:
        return refused(
            "seeded history changed; restart the preview to rebuild the page "
            "from it, which discards this page's feedback"
        )
    try:
        incoming = source.read_bytes()
        incoming_digest = hashlib.sha256(incoming).hexdigest()
        source_changed = incoming_digest != state["source_digest"]
        authored = page / "index.html"
        if source_changed and digest(authored) not in (
            state["source_digest"],
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
            state["source_digest"] = incoming_digest
        mark_preview(source, page, runtime, user)
    except (LeafFailed, ValueError, OSError) as error:
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
    document, while a prose edit is a revision the user keeps their page for.
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
    service record outlives it. `--user` serves the page's durable service
    instead, claimed and started through the selected checkout's launcher and
    revived in place after each update, so the page belongs to this session and
    the URL a user was handed survives every reload and every `leaf wait`.
    Nothing else about a preview differs, so the two are told apart here and
    nowhere else in its lifetime.
    """

    def __init__(self, page: Path, launcher: Path, runtime: Path, user: bool):
        self.page = page
        self.launcher = launcher
        self.runtime = runtime
        self.user = user
        self.temporary = None
        self.address: dict = {}
        self.claimed = False

    def start(self) -> tuple[str, str] | None:
        """Put the server up and report its URL and lifetime note, or None."""
        from leaf.hosting import TemporaryPageServer, start_server

        if not self.user:
            self.temporary = TemporaryPageServer(self.page, **self.address).start()
            self.address = {
                "token": self.temporary.token,
                "port": self.temporary.port,
            }
            return self.temporary.url, WATCHER_NOTE
        if self.claimed:
            # Ownership was claimed through the launcher, whose serving child
            # validates the retained claim before restarting.
            return start_server(self.page)
        ready = start_preview_server(self.page, self.launcher, self.runtime)
        self.claimed = ready is not None
        return ready

    def stop(self) -> None:
        """Take the server down, keeping whatever a restart has to reuse."""
        from leaf.hosting import cmd_stop

        if self.user:
            cmd_stop(self.page)
        elif self.temporary is not None:
            self.temporary.close()
            self.temporary = None

    @property
    def running(self) -> bool:
        """Whether the server is up. A `--user` one also ends with its claim."""
        from leaf.server import running_server

        if not self.user:
            return self.temporary is not None and self.temporary.running
        return running_server(self.page) is not None


def discard_preview(page: Path) -> None:
    """Remove what an earlier preview left in this slot, claim included.

    Called with the slot's lease held, so no preview is serving it. A durable
    service a `--user` preview left behind when it was killed outright is stopped
    first, since its record goes with the page.
    """
    from leaf.event_log import flocked
    from leaf.hosting import cmd_stop
    from leaf.leases import transition_lock
    from leaf.service import PageTransaction, claim_path

    if page.exists():
        cmd_stop(page)
    with flocked(transition_lock(page)):
        if (page / "events.jsonl").is_file():
            with PageTransaction(page):
                shutil.rmtree(page)
        elif page.exists():
            shutil.rmtree(page)
        claim_path(page).unlink(missing_ok=True)


def run_preview(
    source: Path, page: Path, launcher: Path, runtime: Path, user: bool
) -> None:
    """Take the slot, build it fresh, and serve it until this process ends."""
    from leaf.leases import take_waiter_lease

    lease = take_waiter_lease(preview_lease(page))
    if lease is None:
        raise ValueError(
            f"another preview is serving {page}; stop that process, or choose "
            "another --slot"
        )
    with lease:
        discard_preview(page)
        serve_preview(source, page, launcher, runtime, user)


def serve_preview(
    source: Path, page: Path, launcher: Path, runtime: Path, user: bool
) -> None:
    """Build this slot's page, serve it, and follow its inputs until stopped."""
    from leaf.files import read_json
    from leaf.host import session_harness
    from leaf.layer import layer_inputs
    from leaf.service import PageTransaction

    # What the running preview carries between refreshes: the seeded history it
    # installed, which later edits may not change, and the source last stamped.
    state = {"seed": fixture_seed(source), "source_digest": digest(source)}
    service = PreviewService(page, launcher, runtime, user)
    changes = None
    try:
        page.parent.mkdir(parents=True, exist_ok=True)
        prepared_page = prepare_page(
            page,
            read_fixture(source),
            partial(leaf, launcher, runtime),
        )
        mark_preview(source, page, runtime, user)
        ready = service.start()
        if ready is None:
            raise RuntimeError(f"could not start preview {page}")
        url, note = ready
        roots = layer_inputs(
            tuple(read_json(page / "registry.json")["$layer"]["packages"])
        )
        watched = watch_paths(source, runtime, roots, state["seed"])
        changes = watch_changes(watched)
        print(
            preparation_note(
                source, prepared_page.data_sources, prepared_page.versions
            ),
            end="\n\n",
            flush=True,
        )
        print(note, file=sys.stderr, flush=True)
        print(url, flush=True)
        print(f"Watching {source} and {runtime}; feedback stays in {page}", flush=True)
        serving = True
        while True:
            reported = {path for _, path in next(changes)}
            if serving and not service.running:
                return  # the service was stopped, or the owning session ended
            if not serving and user:
                # A refused restart has no service watching the claim's
                # lifetime. Lost ownership ends this preview as well.
                with PageTransaction(page) as transaction:
                    if not transaction.owned_by(session_harness()):
                        return
            if not reported:
                continue  # the idle wake-up that carried the two checks above
            # An added input is only in the reading taken after it arrived, and a
            # deleted one only in the reading taken while it was still there.
            current = watch_paths(source, runtime, roots, state["seed"])
            if not reported & (watched.paths | current.paths):
                continue
            vendored = bool(reported & (watched.layer | current.layer))
            service.stop()
            if refresh_preview(
                source, page, launcher, runtime, state, user, vendor=vendored
            ):
                roots = layer_inputs(
                    tuple(read_json(page / "registry.json")["$layer"]["packages"])
                )
                rebuilt = watch_paths(source, runtime, roots, state["seed"])
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
            serving = service.start() is not None
            if serving:
                print(f"Reloaded {source.stem}", flush=True)
    finally:
        if changes is not None:
            changes.close()
        service.stop()


def start_preview_worker(source: Path, page: Path, runtime: Path, user: bool) -> None:
    """Become the preview, in the selected checkout's uv environment.

    That environment is the one `bin/leaf` syncs, which carries no dev group, so the
    watcher's own dependency is overlaid onto it rather than installed into it. The
    launcher is replaced rather than kept as a parent, so whatever stops this
    process — Ctrl-C, or a runner's SIGTERM, which `uv run` forwards — reaches the
    preview itself.
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
    if user:
        command.append("--user")
    os.chdir(runtime)
    os.execvp(command[0], command)


def terminated(signum, _frame) -> None:
    """End on SIGTERM the way Ctrl-C ends: through the cleanup it skips by default.

    A runner that signals the whole process group reaches this process twice, once
    directly and once through `uv run`'s forwarding, and a second exit raised inside
    the first one's cleanup would abandon it. So the first is the only one heard.
    """
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    raise SystemExit(128 + signum)


def main() -> None:
    parser, args = arguments()
    if args._worker:
        signal.signal(signal.SIGTERM, terminated)
        source = args.source.resolve()
        runtime = args.runtime.resolve()
        run_preview(
            source,
            preview_directory(source, args.slot, args.user),
            runtime / "bin" / "leaf",
            runtime,
            args.user,
        )
        return
    runtime, launcher = checkout(parser, args.runtime)
    source = authored_source(parser, args.example, args.source)

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

    start_preview_worker(
        source, preview_directory(source, args.slot, args.user), runtime, args.user
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except (ValueError, OSError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
