"""Serve an example or developer fixture as a live page, or export it as one file.

An example is authored content, not a page directory; opened from disk it is a dead
page, since Chrome refuses ES modules from file://. This builds the page directory
(`page_fixtures.prepare_page`, companion `.jsonl` history and `.data.json` values
included) and serves it until stopped. `--export` instead writes one HTML file that
opens offline.

A plain preview takes no claim: its comments settle in the page's log and nowhere
else, so a session can drive it. `--user` claims the page for this session, so presses
arrive through the host's feedback path, and serves it from the page's durable
service, which the preview stops on the way out. In Codex it also starts or joins
the task's delivery adapter, so comments can start a new turn after this one ends.

A preview is a foreground process, like any dev server; SIGTERM takes the same cleanup
path as Ctrl-C. Each start discards what an earlier one left in its slot, claim
included, and builds the page fresh from the fixture; a start into a slot another
preview is serving is refused. The slot is a page directory under
`LEAF_PREVIEWS_ROOT` (default `.tmp/previews/`), marked by its `preview.json`, with
its lease at `<slot>.lock` beside it.

While it runs, `watchfiles` reports edits. A source edit is stamped into the live page
at the same URL; a layer edit (a vendored file, the runtime's Python, its lock)
re-vendors through `page init`, which mints a new layer generation the browser follows
into a fresh document. A refused update is printed and retried after the next edit.
Seeded history is installed once, so a change to it is refused until a restart.

    uv run leaf-dev preview [EXAMPLE] [--source FILE] [--runtime CHECKOUT]
        [--slot NAME] [--user] [--export]

The command execs the worker, `python -m leaf_dev.preview --worker`, into the
selected checkout's environment (`start_preview_worker`).
"""

import contextlib
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

import click

from leaf_dev import ROOT
from leaf_dev.example_data import capture_files, example_versions, named_source
from leaf_dev.leaf_assets import CACHE as ASSETS_CACHE
from leaf_dev.leaf_assets import assets_lock
from leaf_dev.page_fixtures import (
    DEFAULT_PACKAGES,
    media_source,
    package_selection_args,
    prepare_page,
    read_fixture,
    source_manifest,
    source_manifest_candidates,
    source_packages,
)

TMP = ROOT / ".tmp"
# A slot is a directory the start discards, so its name must stay inside the root.
SLOT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
# The watcher's own dependency, which the root `pyproject.toml`'s dev group declares. A
# checkout named by `--runtime` has the `--no-dev` environment `bin/leaf` syncs, so the
# worker command overlays it there. Move this floor whenever `pyproject.toml`'s moves.
WATCHER_PACKAGE = "watchfiles>=1.1.0"
# The quiet gap that closes an editor's save batch (`step`), and the idle wake-up at
# which the watcher re-reads the server's liveness (`rust_timeout`).
WATCH_INTERVAL_MS = 250
STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM)


class LeafFailed(RuntimeError):
    """A `leaf` command exited nonzero, having already said why.

    Its own type rather than `SystemExit`, so a refresh can refuse a failed update
    without also swallowing the exit a SIGTERM raises.
    """

    def __init__(self, args: tuple, returncode: int):
        super().__init__(f"leaf {' '.join(args[:2])} exited {returncode}")
        self.returncode = returncode


def leaf(launcher: Path, runtime: Path, *args, input_text: str | None = None) -> None:
    """Hide successful chatter; a failure replays its stdout."""
    result = subprocess.run(
        [str(launcher), *args],
        cwd=runtime,
        check=False,
        input=input_text,
        stdout=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout, end="", flush=True)
        raise LeafFailed(args, result.returncode)


def slot_name(_ctx, _param, value: str | None) -> str | None:
    if value is not None and not SLOT_NAME.fullmatch(value):
        raise click.BadParameter("use letters, digits, dots, underscores, or hyphens")
    return value


def checkout(value: Path) -> tuple[Path, Path]:
    runtime = value.expanduser().resolve()
    launcher = runtime / "bin" / "leaf"
    if not launcher.is_file():
        raise click.UsageError(f"{runtime} has no bin/leaf launcher")
    return runtime, launcher


def authored_source(example: str | None, source: Path | None) -> Path:
    if source:
        selected = source.expanduser().resolve()
        if not selected.is_file():
            raise click.UsageError(f"no authored source at {selected}")
        return selected
    try:
        return named_source(example or "triage-board")
    except ValueError as error:
        raise click.UsageError(str(error)) from None


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

    Every field written here reaches the browser: the server hands the file to
    the page whole. It serves neither the file itself nor an absolute checkout path.
    """
    from leaf.session_cleanup import write_json

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
            **{
                key: producer[key]
                for key in ("commit", "dirty", "committed", "installed")
                if key in producer
            },
        },
    )


def previews_root() -> Path:
    """Where slots live, read per call so a test that sets the variable agrees with
    the preview it launches. The suite points it at its own temporary root."""
    return Path(os.environ.get("LEAF_PREVIEWS_ROOT") or TMP / "previews").resolve()


def preview_directory(source: Path, slot: str | None, user: bool) -> Path:
    if slot:
        return previews_root() / slot
    stem = re.sub(r"[^A-Za-z0-9._-]", "-", source.stem).strip("._-") or "preview"
    return previews_root() / (stem + ("-user" if user else ""))


WATCHER_NOTE = "server   preview (no task claim; stops with this process)"


def preview_lease(page: Path) -> Path:
    """The lock a running preview holds on its slot: beside the page, not in it,
    since a discard removes the page and a lock on a removed inode excludes nobody.
    """
    page.parent.mkdir(parents=True, exist_ok=True)
    return page.with_name(f"{page.name}.lock")


def refresh_media(source: Path, page: Path) -> None:
    """Copy in new media. A name already copied keeps its bytes, since earlier
    revisions may reference it."""
    media = media_source(source)
    for path in sorted(media.rglob("*")):
        if not path.is_file():
            continue
        target = page / "media" / path.relative_to(media)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        elif target.read_bytes() != path.read_bytes():
            raise ValueError(
                f"media/{path.relative_to(media)} has different bytes in the preview; "
                "use a new filename to preserve historical revisions"
            )


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def fixture_seed(source: Path) -> dict:
    """Seed history is installed once, never replayed over user feedback."""
    paths = [
        source.with_suffix(".jsonl"),
        source.with_suffix(".data.json"),
        *example_versions(source)[:-1],
        *capture_files(source),
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


class PreviewService:
    """The preview's server: a process-owned one on a retained address, or for
    `--user` the page's claimed durable service, which `page init` restarts itself
    around a re-vendor. The two modes are told apart here and nowhere else.
    """

    def __init__(self, page: Path, user: bool):
        self.page = page
        self.user = user
        self.temporary = None
        self.address: dict = {}

    def start(self) -> tuple[str, str]:
        """Put the server up for the first time and report its URL and lifetime
        note. A `--user` preview claims the page for this session here, once, and
        gives the claim back if the start does not commit."""
        from leaf.host import CodexHarness, session_harness
        from leaf.hosting import claim_and_start, start_server
        from leaf.service import starting_claim

        if not self.user:
            return self._serve_temporary()
        if isinstance(session_harness(), CodexHarness):
            from leaf.codex_adapter import cmd_codex_start

            # Both parts must be ready before handing over the URL. The carrier
            # joins an existing task-wide adapter, whose lifetime it owns itself.
            with starting_claim(self.page):
                started = start_server(self.page)
                cmd_codex_start(self.page)
                return started
        return claim_and_start(self.page)

    def serve_again(self) -> None:
        """Put a `--user` service that is down but still wanted back up, or say
        why not.

        A revival: it claims nothing, since the claim the first start took is
        still this session's and taking it again would reopen a turn the Stop hook
        closed, and it starts only a service still enabled, so a stop that lands
        first is kept."""
        from leaf.detached import StartRefused
        from leaf.hosting import start_server

        try:
            start_server(self.page, revive=True)
        except StartRefused as error:
            print(error, file=sys.stderr, flush=True)

    @contextlib.contextmanager
    def replacing(self):
        """Hold a process-owned server down across a re-vendor and bring it back,
        admitted or not, unless the preview itself is ending. `page init` restarts
        a `--user` service itself."""
        if self.user:
            yield
            return
        self._close_temporary()
        try:
            yield
        except Exception:
            self._serve_temporary()
            raise
        self._serve_temporary()

    def _serve_temporary(self) -> tuple[str, str]:
        from leaf.hosting import TemporaryPageServer

        self.temporary = TemporaryPageServer(self.page, **self.address).start()
        self.address = {
            "token": self.temporary.token,
            "port": self.temporary.port,
        }
        return self.temporary.url, WATCHER_NOTE

    def _close_temporary(self) -> None:
        if self.temporary is not None:
            self.temporary.close()
            self.temporary = None

    def stop(self) -> None:
        """Take the server down for good, as the preview ends."""
        from leaf.hosting import cmd_stop

        if self.user:
            cmd_stop(self.page)
        else:
            self._close_temporary()

    @property
    def running(self) -> bool:
        """Whether the server is up. A `--user` one also ends with its claim."""
        from leaf.server import running_server

        if not self.user:
            return self.temporary is not None and self.temporary.running
        return running_server(self.page) is not None

    @property
    def ended(self) -> bool:
        """Whether the server is down because its owner ended it, which ends the
        preview: a process-owned one whenever it is down, and a `--user` one when
        its service was stopped or its claim left this session.

        A `--user` service still enabled but down is not ended. That is a server
        that died, or one `page init` re-vendored but could not start again (the
        recorded port was taken), and the next update tries it again."""
        from leaf.files import read_json
        from leaf.host import session_harness
        from leaf.service import PageTransaction

        if not self.user:
            return not self.running
        service = read_json(self.page / "service.json")
        if not service or not service["enabled"]:
            return True
        with PageTransaction(self.page) as transaction:
            return not transaction.owned_by(session_harness())


def refresh_preview(
    source: Path,
    page: Path,
    launcher: Path,
    runtime: Path,
    state: dict,
    service: PreviewService,
    vendor: bool,
) -> bool:
    """Carry an edit into the live page, keeping its log; False if refused.

    `vendor` says a layer input changed; that, or a changed package selection,
    re-copies the layer, and only a re-copy takes a process-owned server down. A
    source edit is written into `index.html` and stamped, the way an agent revises a
    page, so it arrives in the tab the user is standing in. Only a source edit
    touches `index.html`, so an agent's own revision of a `--user` preview survives
    a runtime edit; a source edit over such a revision is refused rather than
    replacing it.
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
                "both the fixture and the preview's index.html changed; "
                "reconcile them before retrying"
            )
        packages = source_packages(source)
        selection_args = package_selection_args(packages)
        # The page's own package selection is vendored too, so a source that changed which
        # packages it asks for needs the layer copied again whatever else stood still.
        vendored_packages = json.loads(
            (page / "registry.json").read_text(encoding="utf-8")
        )["$layer"]["packages"]
        if vendor or packages != vendored_packages:
            with service.replacing():
                leaf(launcher, runtime, "page", "init", *selection_args, str(page))
        refresh_media(source, page)
        if source_changed:
            previous = authored.read_bytes()
            authored.write_bytes(incoming)
            try:
                leaf(
                    launcher,
                    runtime,
                    "page",
                    "stamp",
                    str(page),
                    "--text",
                    "Updated in the checkout",
                )
            except BaseException:
                authored.write_bytes(previous)
                raise
            state["source_digest"] = incoming_digest
        mark_preview(source, page, runtime, service.user)
    except (LeafFailed, ValueError, OSError) as error:
        return refused(error)
    return True


class Watched(NamedTuple):
    """One filesystem subscription and what the paths it reports mean.

    `roots` are watched recursively, so a path that does not exist yet still
    arrives under the directory that will hold it. Every path in `paths` sits under
    one of them.
    """

    roots: tuple[Path, ...]
    paths: frozenset[str]
    layer: frozenset[str]


def watch_paths(source: Path, runtime: Path, roots: list[Path], seed: dict) -> Watched:
    """The inputs one preview follows (`paths`), and which of them re-vendor (`layer`).

    Every path is resolved: `input_paths` answers in resolved paths, so a package
    root reached through a symlink or `..` would otherwise match nothing.
    """
    from leaf.layer import input_paths

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
    media = media_source(source)
    lock = assets_lock(source)
    page = {
        path.resolve()
        for path in (
            source,
            *source_manifest_candidates(source),
            manifest or DEFAULT_PACKAGES,
            *(Path(path) for path in seed),
            *(source.parent / "versions").glob(f"{source.stem}.v*.html"),
            # A pinned copy's bytes change only with its pin, which is followed
            # instead, and it sits under `.tmp`, which no subscription may cover.
            *(() if media.is_relative_to(ASSETS_CACHE) else media.rglob("*")),
            *([lock] if lock is not None else []),
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
    # Keep only the outermost roots (sorted, an ancestor comes first), so the
    # subscription stays the same as media or prior versions arrive beneath them.
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

    watchfiles starts watching on the first read, so this reads once before the
    caller prints its URL, and hands that first batch on as the caller's own.
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


def discard_preview(page: Path) -> None:
    """Remove what an earlier preview left in this slot, claim included.

    Called with the slot's lease held, so no preview is serving it. A durable
    service a `--user` preview left behind when it was killed outright is stopped
    first, since its record goes with the page.
    """
    from leaf.hosting import cmd_stop
    from leaf.service import claim_path

    if page.exists():
        cmd_stop(page)
        shutil.rmtree(page)
    claim_path(page).unlink(missing_ok=True)


def run_preview(
    source: Path, page: Path, launcher: Path, runtime: Path, user: bool
) -> None:
    """Take the slot, build it fresh, and serve it until this process ends."""
    from leaf.leases import release_lease, take_lease

    lease = take_lease(preview_lease(page))
    if lease is None:
        raise ValueError(
            f"another preview is serving {page}; stop that process, or choose "
            "another --slot"
        )
    try:
        discard_preview(page)
        serve_preview(source, page, launcher, runtime, user)
    finally:
        release_lease(lease)


def serve_preview(
    source: Path, page: Path, launcher: Path, runtime: Path, user: bool
) -> None:
    """Build this slot's page, serve it, and follow its inputs until stopped."""
    from leaf.files import read_json
    from leaf.layer import layer_inputs

    # The seeded history the page was built with, which later edits may not change,
    # and the source last stamped into it.
    state = {"seed": fixture_seed(source), "source_digest": digest(source)}
    service = PreviewService(page, user)
    changes = None
    try:
        prepared_page = prepare_page(
            page,
            read_fixture(source),
            partial(leaf, launcher, runtime),
        )
        mark_preview(source, page, runtime, user)
        url, note = service.start()
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
        while True:
            reported = {path for _, path in next(changes)}
            if not service.running and service.ended:
                return  # the service was stopped, or the owning session ended
            if not reported:
                continue  # the idle wake-up that carried the check above
            # An added input is only in the reading taken after it arrived, and a
            # deleted one only in the reading taken while it was still there.
            current = watch_paths(source, runtime, roots, state["seed"])
            if not reported & (watched.paths | current.paths):
                continue
            vendored = bool(reported & (watched.layer | current.layer))
            refreshed = refresh_preview(
                source, page, launcher, runtime, state, service, vendored
            )
            if refreshed:
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
            if service.user and not service.running:
                # A server that died, or that a re-vendor could not start again,
                # which said why. Each later update is another try.
                service.serve_again()
            if refreshed and service.running:
                print(f"Reloaded {source.stem}", flush=True)
    finally:
        if changes is not None:
            changes.close()
        service.stop()


def start_preview_worker(source: Path, page: Path, runtime: Path, user: bool) -> None:
    """Become the preview, in the selected checkout's uv environment.

    That environment is the one `bin/leaf` syncs, which carries no dev group, so the
    watcher's own dependency and this checkout's `leaf_dev`, which builds the page from
    the fixture, are overlaid onto it rather than installed into it. `leaf_dev` names
    no `leaf` of its own, so the overlay leaves the selected checkout's `leaf` in
    place. The launcher is replaced rather than kept as a parent, so whatever stops
    this process — Ctrl-C, or a runner's SIGTERM, which `uv run` forwards — reaches
    the preview itself.
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
        "--with-editable",
        str(ROOT / "dev"),
        "python",
        "-m",
        "leaf_dev.preview",
        "--source",
        str(source),
        "--runtime",
        str(runtime),
        "--slot",
        page.name,
        "--worker",
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
    """Begin shutdown once and let its cleanup finish despite later stop signals.

    Ignore both SIGINT and SIGTERM before unwinding so another stop cannot
    interrupt the watcher or service cleanup.
    """
    for stop_signal in STOP_SIGNALS:
        signal.signal(stop_signal, signal.SIG_IGN)
    raise SystemExit(128 + signum)


@click.command()
@click.argument("example", required=False)
@click.option(
    "--source",
    type=click.Path(path_type=Path),
    help="Authored HTML source to preview.",
)
@click.option(
    "--runtime",
    type=click.Path(path_type=Path),
    default=ROOT,
    help="Leaf checkout whose bin/leaf vendors the page.",
)
@click.option(
    "--slot",
    callback=slot_name,
    help="Stable name for a preview that may coexist with other slots.",
)
@click.option(
    "--user",
    is_flag=True,
    help="Hand this preview to a user: claim the page so presses arrive as feedback.",
)
@click.option(
    "--export",
    is_flag=True,
    help="Write an offline HTML file instead of serving the page.",
)
@click.option("--worker", is_flag=True, hidden=True)
def preview(
    example: str | None,
    source: Path | None,
    runtime: Path,
    slot: str | None,
    user: bool,
    export: bool,
    worker: bool,
) -> None:
    """Serve an example as a live page, or export it as one file.

    EXAMPLE is a public example or developer fixture, triage-board by default."""
    if source and example:
        raise click.UsageError("choose an example name or --source, not both")
    if user and export:
        raise click.UsageError("--user serves a page; omit --export")
    try:
        if worker:
            for stop_signal in STOP_SIGNALS:
                signal.signal(stop_signal, terminated)
            source = source.resolve()
            runtime = runtime.resolve()
            run_preview(
                source,
                preview_directory(source, slot, user),
                runtime / "bin" / "leaf",
                runtime,
                user,
            )
        elif export:
            export_preview(*checkout(runtime), authored_source(example, source), slot)
        else:
            runtime, _ = checkout(runtime)
            source = authored_source(example, source)
            start_preview_worker(
                source, preview_directory(source, slot, user), runtime, user
            )
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except LeafFailed as error:
        raise SystemExit(error.returncode) from None
    except (ValueError, OSError, RuntimeError) as error:
        raise click.ClickException(str(error)) from None


def export_preview(
    runtime: Path, launcher: Path, source: Path, slot: str | None
) -> None:
    """Write the page as one offline file under `.tmp/`, and print its path."""
    TMP.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="preview-export-", dir=TMP) as staging:
        page = Path(staging) / "page"
        prepared = prepare_page(
            page,
            read_fixture(source),
            partial(leaf, launcher, runtime),
        )
        suffix = f"-{slot}" if slot else ""
        out = TMP / f"example-{source.stem}{suffix}.html"
        out.unlink(missing_ok=True)
        leaf(launcher, runtime, "page", "export", str(page), "-o", str(out))
    print(
        preparation_note(source, prepared.data_sources, prepared.versions),
        end="\n\n",
    )
    print(out.resolve())


if __name__ == "__main__":
    preview()
