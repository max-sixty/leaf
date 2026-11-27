"""Serve an example or developer fixture as a live page, beside a base's with
`--base`, or export it as one file.

An example is authored content, not a page directory; opened from disk it is a dead
page, since Chrome refuses ES modules from file://. This builds the page directory
(`page_fixtures.prepare_page`, companion `.jsonl` history and `.data.json` values
included) and serves it until stopped. `--export` instead writes one HTML file that
opens offline.

A plain preview takes no claim: its comments settle in the page's log and nowhere
else, so a session can drive it. `--user` serves the page from its durable service. In
a session started normally that serves it unclaimed, since a checkout acts for no
session (`harness.session_harness`), and the checkout's `bin/leaf wait` hears it, as
the reading printed beneath the URL says (`serves-for-no-session`). Only where the
session's hooks run the preview's runtime, as in `leaf-dev journey session`, does it
claim the page for the session, so presses arrive through the harness's feedback path.
Ending the preview stops its service and withdraws its acquisition.

A preview runs in the foreground; SIGTERM takes the same cleanup path as Ctrl-C.
User previews resume the page in their slot, preserving its feedback and authored
revisions. Plain previews build fresh from the fixture. A start into a slot another
preview is serving is refused. The slot is a page directory under
`LEAF_PREVIEWS_ROOT` (default `.tmp/previews/`), marked by its `preview.json`, with
its lease at `<slot>.lock` beside it (`arms.preview_lease`).

A product document is served as builders read it, with the parts other sources own
composed in (`page_fixtures.authored_markup`), and an edit to one of those owners
refreshes it like an edit to the document. A corpus preview follows the original
sources and regenerates their composition before refreshing its page.

Changes to the watcher's Python, schemas or dependencies need an explicit restart;
the current preview stays served until then.

`--base` serves a base runtime's preview beside this working tree's: the merge base
with `main`, or the commit it names (`leaf_dev.arms.choose_arms`). The head preview
follows runtime edits as any preview does. Both read the head's authored source,
following its edits, unless `--authored` has the base read its own copy
(`leaf_dev.arms.own_source`). Each invocation owns fresh preview slots, named after the
source and the run, and the base's files stay under `.tmp/preview-base`. The two
previews end together.

The preview serves the selected checkout in place, with its runtime's source modules,
so a runtime edit reaches the page with no build.

While it runs, a native subscription (`leaf.log.file_changes`) reports edits.
Initialization decides whether the layer actually changed; identical saves leave the
browser and server alone. A source or `.page/` companion edit is stamped into the
live page at the same URL. A package or runtime edit restarts the server, which
composes the layer afresh, and a changed selection goes through `page init`, which
mints a new layer generation the browser follows into a fresh document. A refused
update is printed and retried after the next edit.
Fixture history, literal data seeds and earlier versions initialize a fresh slot.
Live updates follow current markup, page-owned files, captured data files, media
and the browser runtime. Restarting a user preview preserves its history and current
seed data, while captures continue following their authored companion declarations.

    uv run leaf-dev preview [EXAMPLE] [--source FILE] [--runtime CHECKOUT]
        [--slot NAME] [--user] [--export] [--authored] [--base [REF]]

The command execs the selected checkout's own worker,
`python -m leaf_dev.commands.preview --worker`, into its environment
(`start_preview_worker`). The worker and the server share that checkout's contracts.
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
import time
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import NamedTuple

import click

from leaf.base.locations import canonical_path
from leaf.base.refusals import Refused
from leaf.base.schema import LAYER_FILE, PACKAGES_DIR
from leaf.log.file_changes import FileChanges
from leaf.records.publishing import (
    authored_digest,
    authored_files,
    write_authored_files,
)
from leaf.source.runtime_selection import forget_tree, read_runtime
from leaf_dev import ROOT
from leaf_dev.arms import (
    STOP_SIGNALS,
    arm_python,
    base_option,
    preview_lease,
    terminated,
)
from leaf_dev.example_data import (
    capture_file,
    data_companion,
    data_file,
    named_source,
    page_files,
)
from leaf_dev.leaf_assets import CACHE as ASSETS_CACHE
from leaf_dev.leaf_assets import LOCK as ASSETS_LOCK
from leaf_dev.leaf_assets import assets_checkout
from leaf_dev.page_fixtures import (
    DEFAULT_PACKAGES,
    authored_markup,
    composition_inputs,
    import_referenced_media,
    media_source,
    package_selection_args,
    prepare_page,
    read_fixture,
    record_run_context,
    refresh_captures,
    refresh_composition,
    source_manifest,
    source_manifest_candidates,
    source_packages,
)

TMP = ROOT / ".tmp"
# A slot names a page directory, so its name must stay inside the root.
SLOT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
# The idle wake-up at which a preview checks its server and owning session.
WATCH_INTERVAL_MS = 250
# A refused bind is retried without requiring the author to edit the page. Keep
# starts apart while the port is occupied; repeat diagnostics only when they change.
REVIVE_INTERVAL_SECS = 1


def worker_inputs(runtime: Path) -> list[Path]:
    """Inputs loaded by Python, which a server restart alone cannot refresh."""
    from leaf.source.layer import payload_python_inputs

    return [
        *payload_python_inputs(runtime),
        *(
            path
            for path in runtime.joinpath("dev/leaf_dev").rglob("*.py")
            if path.is_file()
        ),
        runtime / "dev/pyproject.toml",
    ]


def worker_identity(runtime: Path) -> str:
    from leaf.source.layer import files_identity

    return files_identity(
        {
            str(path.relative_to(runtime)): path.read_bytes()
            for path in sorted(worker_inputs(runtime))
        }
    )


class LeafFailed(RuntimeError):
    """A `leaf` command exited nonzero, having already said why.

    Its own type rather than `SystemExit`, so a refresh can refuse a failed update
    without also swallowing the exit a SIGTERM raises.
    """

    def __init__(self, args: tuple, returncode: int):
        super().__init__(f"leaf {' '.join(args[:2])} exited {returncode}")
        self.returncode = returncode


def leaf(launcher: Path, runtime: Path, *args, input_text: str | None = None) -> str:
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
    return result.stdout


def slot_name(_ctx, _param, value: str | None) -> str | None:
    if value is not None and not SLOT_NAME.fullmatch(value):
        raise click.BadParameter("use letters, digits, dots, underscores, or hyphens")
    return value


def checkout(value: Path) -> tuple[Path, Path]:
    runtime = canonical_path(value.expanduser())
    launcher = runtime / "bin" / "leaf"
    if not launcher.is_file():
        raise click.UsageError(f"{runtime} has no bin/leaf launcher")
    return runtime, launcher


def authored_source(example: str | None, source: Path | None) -> Path:
    if source:
        selected = canonical_path(source.expanduser())
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


def fixture_identity(source: Path) -> str:
    """Name an authored source without exposing its absolute path to the browser."""
    return hashlib.sha256(str(source).encode()).hexdigest()


def mark_preview(
    source: Path, page: Path, runtime: Path, user: bool, authored: str
) -> None:
    """Record the preview the browser chrome labels, and mark the page as one.

    Every field written here reaches the browser: the server hands the file to
    the page whole. It serves neither the file itself nor an absolute checkout path.
    `input` records the fixture publication this watcher last applied, so a later
    watcher can distinguish source edits from competing page edits. The page's own
    authored files and event log remain authoritative.
    """
    from leaf.base.service import PREVIEW

    PREVIEW.write(
        page / "preview.json",
        {
            "example": source.stem,
            "checkout": runtime.name,
            "interaction": "user" if user else "author",
            "started": datetime.now(UTC).isoformat(),
            "input": {"source": fixture_identity(source), "authored": authored},
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


def copy_media(media: Path, page: Path) -> None:
    """Copy in new media. A name already copied keeps its bytes, since earlier
    revisions may reference it."""
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


def incoming_files(source: Path) -> dict[str, bytes]:
    """The authored inputs a preview installs: the markup as builders read it
    (`authored_markup`), and the source's page-owned files."""
    return {
        **authored_files(source, page_files(source)),
        "index.html": authored_markup(source).encode(),
    }


def refresh_media(source: Path, page: Path, run_leaf) -> None:
    """Supply local and pinned media needed by the complete authored inputs."""
    copy_media(media_source(source), page)
    import_referenced_media(
        page,
        [authored_markup(source)],
        run_leaf,
        source=source,
    )


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
    around a layer change. The two modes are told apart here and nowhere else.
    """

    def __init__(self, page: Path, user: bool):
        self.page = page
        self.user = user
        self.temporary = None
        self.address: dict = {}
        self.revive_at = 0.0
        self.revive_refusal: str | None = None
        self.claim: dict | None = None

    @contextlib.contextmanager
    def starting(self):
        """Prepare serving; claim the page only when the caller accepts on exit."""
        from leaf.pages.hosting import claim_and_start

        if not self.user:
            yield self._serve_temporary()
            return
        with claim_and_start(self.page) as started:
            self.claim = started.claim
            yield started.url

    def reading(self, url: str) -> str:
        """Describe the committed service at `url`: a `--user` one as one JSON line,
        as `leaf server start` prints it, with its URL, its reading
        (`hosting.server_reading`) and what serving it noted (`findings.with_held`),
        such as that it serves for no session."""
        from leaf.base.findings import with_held
        from leaf.pages.hosting import server_reading

        if not self.user:
            return WATCHER_NOTE
        return json.dumps(with_held({"url": url} | server_reading(self.page)))

    def serve_again(self) -> None:
        """Put a `--user` service that is down but still wanted back up.

        A revival: it claims nothing, since the claim the first start took is
        still this session's and taking it again would reopen a turn the Stop hook
        closed, and it starts only a service still enabled, so a stop that lands
        first is kept. A refused start is retried on later watcher polls; the same
        refusal is printed once while it stands."""
        from leaf.base.detached import StartRefused
        from leaf.base.harness import claim_harness
        from leaf.pages.hosting import start_server

        if time.monotonic() < self.revive_at:
            return
        try:
            start_server(
                self.page,
                revive=True,
                harness=claim_harness(self.claim) if self.claim else None,
            )
        except StartRefused as error:
            refusal = str(error)
            if refusal != self.revive_refusal:
                print(refusal, file=sys.stderr, flush=True)
            self.revive_refusal = refusal
            self.revive_at = time.monotonic() + REVIVE_INTERVAL_SECS
        else:
            self.revive_refusal = None
            self.revive_at = 0.0

    @contextlib.contextmanager
    def replacing(self, initializing: bool):
        """Hold a process-owned server down across a layer change and bring it back,
        admitted or not, unless the preview itself is ending. A `--user` service is
        restarted by the `page init` the block runs when `initializing`, and here
        otherwise, since a server composes its layer once, as it starts. A
        process-owned server runs in this process, which holds the runtime and the
        layers it read for as long as it runs, so its replacement drops them first."""
        if self.user:
            if initializing:
                yield
                return
            from leaf.base.harness import claim_harness
            from leaf.pages.hosting import restarting_server

            with restarting_server(
                self.page, claim_harness(self.claim) if self.claim else None
            ):
                yield
            return
        self._close_temporary()
        forget_tree()
        try:
            yield
        except Exception:
            self._serve_temporary()
            raise
        self._serve_temporary()

    def _serve_temporary(self) -> str:
        from leaf.pages.hosting import TemporaryPageServer

        self.temporary = TemporaryPageServer(self.page, **self.address).start()
        self.address = {
            "token": self.temporary.token,
            "port": self.temporary.port,
        }
        return self.temporary.url

    def _close_temporary(self) -> None:
        if self.temporary is not None:
            self.temporary.close()
            self.temporary = None

    def stop(self) -> None:
        """Stop serving and withdraw this preview's acquisition, keeping successors."""
        from leaf.pages.hosting import cmd_stop
        from leaf.records.transaction import ClaimTransition, PageTransaction

        if self.user:
            cmd_stop(self.page, owner=self.claim)
            if self.claim is not None:
                with PageTransaction(self.page) as page:
                    page.restore_claim(ClaimTransition(None, self.claim, {}))
        else:
            self._close_temporary()

    @property
    def running(self) -> bool:
        """Whether the server is up. A `--user` one also ends with its claim."""
        from leaf.base.server import running_server

        if not self.user:
            return self.temporary is not None and self.temporary.running
        return running_server(self.page) is not None

    @property
    def ended(self) -> bool:
        """Whether the server is down because its owner ended it, which ends the
        preview: a process-owned one whenever it is down, and a `--user` one when
        its service was stopped or its claim left this session.

        A `--user` service still enabled but down is not ended. That is a server
        that died, or one `page init` restarted but could not start again (the
        recorded port was taken), and the watcher tries it again."""
        from leaf.base.server import read_service
        from leaf.base.service import claim_is_active, page_claim, same_claim

        if not self.user:
            return not self.running
        service = read_service(self.page)
        if not service or not service["enabled"]:
            return True
        claim = page_claim(self.page)
        return not same_claim(claim, self.claim) or (
            claim is not None and not claim_is_active(claim)
        )


def source_roots(source: Path, runtime: Path) -> list[Path]:
    """The package roots the source's selection names, where `page init` runs from
    (`leaf`), whose edits reach the page as copies at its next init."""
    from leaf.source.layer import layer_inputs

    return layer_inputs(tuple(source_packages(source, runtime)), runtime)


def refresh_preview(
    source: Path,
    page: Path,
    launcher: Path,
    runtime: Path,
    state: dict,
    service: PreviewService,
) -> bool:
    """Carry an edit into the live page, keeping its log; False if refused.

    Initialization compares the desired contract with the installed layer, so a
    retry also adopts layer edits a previous refusal held back. Only a changed
    layer takes a process-owned server down. A
    source edit replaces the authored HTML and companion files and stamps them,
    the way an agent revises a page, so it arrives in the tab the user is reading
    in. An agent's own revision of a `--user` preview survives a runtime edit; a
    source edit over competing authored inputs is refused rather than replacing
    them. A refused stamp restores the previous mutable inputs as well.
    """
    try:
        refresh_composition(source)
        fixture = read_fixture(source, runtime=runtime, base=runtime)
        incoming = incoming_files(source)
        incoming_digest = authored_digest(incoming)
        source_changed = incoming_digest != state["authored"]
        previous = authored_files(page / "index.html", page / "page")
        previous_digest = authored_digest(previous)
        if source_changed and previous_digest not in (
            state["authored"],
            incoming_digest,
        ):
            return refused(
                "both the fixture and the preview's authored files changed; "
                "reconcile them before retrying"
            )
        selection_args = package_selection_args(fixture.packages)
        # Initialization owns the change decision. Ask before a process-owned
        # server is taken down; the actual init checks again before committing.
        planned = json.loads(
            leaf(
                launcher,
                runtime,
                "page",
                "init",
                "--dry-run",
                *selection_args,
                str(page),
            )
        )
        # A page composes its layer from the Leaf serving it, so a runtime or
        # package edit needs a server that read it as much as a new selection does.
        # This process runs in the selected checkout, so its runtime is `runtime`.
        serving = read_runtime().identity
        if planned["changed"] or serving != state.get("serving"):
            with service.replacing(planned["changed"]):
                if planned["changed"]:
                    leaf(launcher, runtime, "page", "init", *selection_args, str(page))
            state["serving"] = serving
        if source_changed and previous_digest != incoming_digest:
            # Resolve the complete candidate before touching served authored files.
            # The selected payload's stamp owner installs and publishes it under
            # one transaction, including a final check against competing edits.
            with tempfile.TemporaryDirectory(prefix="leaf-preview-candidate-") as raw:
                candidate = Path(raw) / "page"
                candidate.mkdir()
                shutil.copyfile(page / LAYER_FILE, candidate / LAYER_FILE)
                if (page / PACKAGES_DIR).is_dir():
                    shutil.copytree(page / PACKAGES_DIR, candidate / PACKAGES_DIR)
                if (page / "media").is_dir():
                    shutil.copytree(page / "media", candidate / "media")
                # Media's ordinary CLI door needs an initialized, isolated log.
                # The candidate holds no history or feedback from the served page.
                (candidate / "events.jsonl").write_text("")
                (candidate / "data").mkdir()
                write_authored_files(candidate, incoming, {})
                # Check capture bindings and values against the complete candidate
                # before replacing the source that the reader currently has.
                refresh_captures(fixture, candidate, partial(leaf, launcher, runtime))
                refresh_media(source, candidate, partial(leaf, launcher, runtime))
                copy_media(candidate / "media", page)
                leaf(
                    launcher,
                    runtime,
                    "page",
                    "stamp",
                    str(page),
                    "--text",
                    "Updated in the checkout",
                    "--replace",
                    str(candidate),
                    authored_digest(previous),
                )
        else:
            refresh_media(source, page, partial(leaf, launcher, runtime))
        refresh_captures(
            fixture,
            page,
            partial(leaf, launcher, runtime),
        )
        state["authored"] = incoming_digest
        mark_preview(source, page, runtime, service.user, state["authored"])
    except (
        LeafFailed,
        Refused,
        ValueError,
        OSError,
        RuntimeError,
        subprocess.CalledProcessError,
    ) as error:
        return refused(error)
    return True


class Watched(NamedTuple):
    """One filesystem subscription and what the paths it reports mean.

    `roots` hold individual files and recursive directories. `trees` name where
    new inputs may arrive; existing inputs elsewhere match only their exact path.
    A missing tree is subscribed through its existing parent, without admitting
    unrelated writes in that parent to expensive input discovery.
    """

    roots: tuple[Path, ...]
    paths: frozenset[str]
    trees: frozenset[Path]

    def relevant(self, path: str) -> bool:
        if path in self.paths:
            return True
        candidate = Path(path)
        return not self.trees.isdisjoint((candidate, *candidate.parents))


def watch_paths(source: Path, runtime: Path, roots: list[Path]) -> Watched:
    """The inputs one preview follows (`paths`).

    Every path is resolved: `input_paths` answers in resolved paths, so a package
    root reached through a symlink or `..` would otherwise match nothing.
    """
    from leaf.source.layer import input_paths, payload_server_inputs

    runtime = runtime.resolve()
    scripts = runtime / "src"
    resolved_roots = {root.resolve() for root in roots}
    # The layer reading follows a link inside a package as well as one at its root,
    # so a layer file can resolve outside every package root.
    package = [
        path
        for path in input_paths(roots)
        if path not in resolved_roots and not path.is_dir()
    ]
    layer = {
        *(str(path) for path in package),
        *(str(path) for path in payload_server_inputs(runtime)),
        *(str(path) for path in worker_inputs(runtime)),
    }
    manifest = source_manifest(source)
    companions = page_files(source)
    media = media_source(source)
    checkout = assets_checkout(source)
    composed, composed_trees = composition_inputs(source)
    page = {
        path.resolve()
        for path in (
            source,
            data_file(source),
            *(
                capture_file(source, spec)
                for spec in data_companion(source).get("$captures", {}).values()
                if "asset" not in spec
            ),
            *composed,
            *composed_trees,
            companions,
            *companions.rglob("*"),
            *source_manifest_candidates(source),
            manifest or DEFAULT_PACKAGES,
            # A pinned copy's bytes change only with its pin, which is followed
            # instead, and it sits under `.tmp`, which no subscription may cover.
            *(() if media.is_relative_to(ASSETS_CACHE) else media.rglob("*")),
            *([checkout / ASSETS_LOCK] if checkout is not None else []),
            # The nearer of these two directories is the one the page's images come
            # from, so either arriving changes which images the refresh copies.
            source.parent / "media",
            *([manifest.parent / "media"] if manifest is not None else []),
        )
    }
    discovering = {
        *(path.resolve() for path in composed_trees),
        companions,
        source.parent / "media",
        *([manifest.parent / "media"] if manifest is not None else []),
    }
    trees = {
        *resolved_roots,
        scripts,
        runtime / "dev/leaf_dev",
        *(path.parent for path in package),
        *discovering,
    }
    # Discovery subscriptions stay at the parent even after a missing directory
    # arrives, so rebuilding does not discard events collected during refresh.
    holders = (trees - discovering) | {tree.parent for tree in discovering}
    holders.update(Path(path) for path in layer)
    holders.update(page)
    existing = set()
    for path in holders:
        while not path.exists():
            path = path.parent
        existing.add(path)
    # Only directories cover descendants. A pin at the checkout root is a file
    # subscription, never a recursive subscription to the checkout itself.
    subscribed: list[Path] = []
    for path in sorted(existing):
        if not any(root in path.parents for root in subscribed):
            subscribed.append(path)
    return Watched(
        tuple(subscribed),
        frozenset(layer | {str(path) for path in page}),
        frozenset(tree.resolve() for tree in trees),
    )


class PreviewChanges(FileChanges):
    """Input path batches with the preview's bounded lifetime-check wake-up."""

    def __iter__(self):
        return self

    def __next__(self):
        return self.batch(WATCH_INTERVAL_MS / 1000)


def watch_roots(watched: Watched) -> dict[Path, bool]:
    """Recursive input trees and shallow parents for replaceable file inputs."""
    directories = {path for path in watched.roots if path.is_dir()}
    roots = {path.parent: False for path in watched.roots if path not in directories}
    roots.update(dict.fromkeys(directories, True))
    return roots


def watch_changes(watched: Watched) -> PreviewChanges:
    """Install the native subscriptions before publishing the preview URL.

    Single files use shallow parent watches: an editor's atomic rename changes
    the inode, so a file watch on Linux otherwise loses later saves. The runtime's
    Python trees are inputs, and every interpreter that imports them writes
    bytecode beside them, so `__pycache__` is ignored.
    """
    return PreviewChanges(
        watch_roots(watched),
        lambda path: "__pycache__" not in path.parts,
        collect=True,
    )


def discard_preview(page: Path) -> None:
    """Remove what an earlier preview left in this slot, claim included.

    Called with the slot's lease held, so no preview is serving it. A durable
    service a `--user` preview left behind when it was killed outright is stopped
    first, since its record goes with the page.
    """
    from leaf.base.service import claim_path
    from leaf.base.state import CLAIM
    from leaf.pages.hosting import cmd_stop

    if page.exists():
        cmd_stop(page)
        shutil.rmtree(page)
    CLAIM.remove(claim_path(page))


def run_preview(
    source: Path,
    page: Path,
    launcher: Path,
    runtime: Path,
    user: bool,
) -> None:
    """Take the slot, resume a user's page or build a plain preview, then serve."""
    from leaf.base.leases import release_lease, take_lease

    lease = take_lease(preview_lease(page))
    if lease is None:
        raise ValueError(
            f"another preview is serving {page}; stop that process, or choose "
            "another --slot"
        )
    try:
        if not user:
            discard_preview(page)
        serve_preview(source, page, launcher, runtime, user)
    finally:
        release_lease(lease)


def serve_preview(
    source: Path,
    page: Path,
    launcher: Path,
    runtime: Path,
    user: bool,
) -> None:
    """Build this slot's page, serve it, and follow its inputs until stopped."""
    from leaf.base.findings import hold, note, release
    from leaf.base.service import PREVIEW

    loaded = worker_identity(runtime)
    # Fixture progress is distinct from the page's own authored inputs: an agent
    # may have revised those while this watcher was absent.
    refresh_composition(source)
    state = {
        "authored": authored_digest(incoming_files(source)),
    }
    resumed = user and page.exists()
    if resumed:
        record = PREVIEW.read(page / "preview.json")
        if (
            record is None
            or record["input"]["source"] != fixture_identity(source)
            or record["interaction"] != "user"
        ):
            raise ValueError(
                f"{page} belongs to another preview; choose another --slot"
            )
        state["authored"] = record["input"]["authored"]
    service = None
    changes = None
    try:
        state["serving"] = read_runtime().identity
        prepared_page = None
        if resumed:
            service = PreviewService(page, user)
            refresh_preview(source, page, launcher, runtime, state, service)
        else:
            # The fixture owner builds all versions, seed history, data and media
            # privately. Only a complete page directory acquires the public slot;
            # a refused build cannot expose partial state or clean up a successor.
            page.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix=".leaf-preview-", dir=page.parent
            ) as raw:
                staged = Path(raw) / "page"
                prepared_page = prepare_page(
                    staged,
                    read_fixture(source, runtime=runtime, base=runtime),
                    partial(leaf, launcher, runtime),
                )
                mark_preview(source, staged, runtime, user, state["authored"])
                staged.rename(page)
            service = PreviewService(page, user)
        record_run_context(
            page,
            purpose="user-review" if user else "author-preview",
            run=page,
            authored_source=source,
        )
        # What starting notes rides in the reading printed beneath the URL, in the
        # same write, so a reader of the log who waits for the URL meets it too.
        hold()
        try:
            with service.starting() as url:
                pass
            roots = source_roots(source, runtime)
            watched = watch_paths(source, runtime, roots)
            changes = watch_changes(watched)
            print(
                preparation_note(
                    source, prepared_page.data_sources, prepared_page.versions
                )
                if prepared_page is not None
                else f"resumed {source.stem}",
                end="\n\n",
                flush=True,
            )
            print(f"{url}\n{service.reading(url)}", flush=True)
        finally:
            note(*release())
        print(f"Watching {source} and {runtime}; feedback stays in {page}", flush=True)
        while True:
            reported = next(changes)
            if service.ended:
                return  # the service was stopped, or the owning session ended
            if service.user and not service.running:
                service.serve_again()
            replaced = not changes.matches(watch_roots(watched))
            if replaced:
                # Native directory watches expire when their directory is
                # removed, even if its pathname and selected inputs return.
                # Edits during that gap have no file batch, so this invalidates
                # the canonical input reading as well as the subscription.
                changes.close()
                changes = watch_changes(watched)
            if not replaced:
                if not reported:
                    continue  # lifetime and root checks need no input discovery
                if not any(watched.relevant(path) for path in reported):
                    continue
                # An added input is only in the reading taken after it arrived, and a
                # deleted one only in the reading taken while it was still there.
                if not reported & watched.paths:
                    try:
                        current = watch_paths(source, runtime, roots)
                    except (ValueError, OSError) as error:
                        refused(error)
                        continue
                    if not reported & current.paths:
                        continue
            try:
                changed = worker_identity(runtime) != loaded
            except OSError as error:
                refused(error)
                continue
            if changed:
                print(
                    "Leaf Python, schemas or dependencies changed; restart this preview. The current page remains served.",
                    file=sys.stderr,
                    flush=True,
                )
                continue
            refreshed = refresh_preview(source, page, launcher, runtime, state, service)
            # Init can commit a selection even when the following source stamp
            # refuses. Follow the installed layer after every attempt, so that
            # its newly selected packages remain observable while source is fixed.
            roots = source_roots(source, runtime)
            try:
                rebuilt = watch_paths(source, runtime, roots)
            except (ValueError, OSError) as error:
                # A companion being edited can be temporarily unreadable. Keep
                # its previous subscription so its repair reaches this preview.
                refused(error)
                continue
            if not changes.matches(watch_roots(rebuilt)):
                # A refresh can change which packages the page selects, and a
                # subscription's roots are fixed for its lifetime. Holding the old
                # one wherever the roots stand still keeps the edits made during
                # the refresh, which it collected while this was busy.
                changes.close()
                changes = watch_changes(rebuilt)
            watched = rebuilt
            if service.user and not service.running:
                # A server that died, or that `page init` could not start again,
                # which said why. The next watcher poll is another try.
                service.serve_again()
            if refreshed and service.running:
                print(f"Updated {source.stem}", flush=True)
    finally:
        if changes is not None:
            changes.close()
        if service is not None:
            service.stop()


def start_preview_worker(source: Path, page: Path, runtime: Path, user: bool) -> None:
    """Become the preview, in the selected checkout's uv environment.

    That environment is the one `bin/leaf` syncs, which carries no dev group, so
    `leaf_dev`, which builds the page from the fixture, is overlaid onto it. The selected
    checkout owns both the worker and `leaf`, so their startup and serving contracts
    stay together when comparing versions. The launcher is replaced rather than
    kept as a parent, so whatever stops this process — Ctrl-C, or a runner's
    SIGTERM, which `uv run` forwards — reaches the preview itself.
    """
    command = [
        *arm_python(runtime, dev=runtime / "dev"),
        "-m",
        "leaf_dev.commands.preview",
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
    help="Leaf checkout whose bin/leaf initializes and serves the page.",
)
@click.option(
    "--slot",
    callback=slot_name,
    help="Stable name for a preview that may coexist with other slots.",
)
@click.option(
    "--user",
    is_flag=True,
    help="Hand this preview to a user: serve its page durably, for this checkout's "
    "`bin/leaf wait PAGE` to hear, or claimed for the session where its hooks run "
    "this runtime.",
)
@click.option(
    "--export",
    is_flag=True,
    help="Write an offline HTML file instead of serving the page.",
)
@click.option(
    "--authored",
    is_flag=True,
    help="With --base, build the base's page from its own authored source.",
)
@base_option()
@click.option("--worker", is_flag=True, hidden=True)
def preview(
    example: str | None,
    source: Path | None,
    runtime: Path,
    slot: str | None,
    user: bool,
    export: bool,
    authored: bool,
    base: str | None,
    worker: bool,
) -> None:
    """Serve an example as a live page, or export it as one file.

    EXAMPLE is a public example or developer fixture, triage-board by default."""
    if source and example:
        raise click.UsageError("choose an example name or --source, not both")
    if user and export:
        raise click.UsageError("--user serves a page; omit --export")
    if authored and base is None:
        raise click.UsageError("--authored builds the base's page; add --base")
    if base is not None:
        if export or slot or runtime != ROOT:
            raise click.UsageError(
                "--base serves two previews; omit --export, --slot and --runtime"
            )
        serve_versions(authored_source(example, source), base, authored, user)
        return
    # An explicitly selected runtime owns its launcher, including in the worker
    # and the page commands it starts. A host override would redirect those calls.
    os.environ.pop("LEAF_HOST_LAUNCHER", None)
    try:
        if worker:
            for stop_signal in STOP_SIGNALS:
                signal.signal(stop_signal, terminated)
            assert source is not None
            source = source.resolve()
            runtime = runtime.resolve()
            page = preview_directory(source, slot, user)
            run_preview(source, page, runtime / "bin" / "leaf", runtime, user)
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
    except (Refused, ValueError, OSError, RuntimeError) as error:
        raise click.ClickException(str(error)) from None


def serve_versions(source: Path, base: str, authored: bool, user: bool) -> None:
    """Serve the base's preview and this working tree's together, each in a preview
    process of its own (`--base`)."""
    from threading import Thread

    from leaf_dev.arms import choose_arms, own_source, run_directory

    if authored and not source.is_relative_to(ROOT):
        raise click.UsageError("--authored needs a source inside this checkout")
    directory = run_directory(ROOT / ".tmp" / "preview-base")
    arms = choose_arms(base, directory)
    prefix = f"{source.stem}-{directory.name}"
    processes = []
    readers = []

    def output(name, process):
        for line in process.stdout:
            click.echo(f"{name}: {line.rstrip()}")

    def stop(_signal, _frame):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, stop)
    try:
        for name, arm in arms.items():
            process = subprocess.Popen(
                [
                    "uv",
                    "run",
                    "--project",
                    str(ROOT),
                    "leaf-dev",
                    "preview",
                    "--source",
                    str(own_source(arm, source) if authored else source),
                    "--runtime",
                    str(arm.directory),
                    "--slot",
                    f"{prefix}-{name}",
                    *(["--user"] if user else []),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            processes.append(process)
            reader = Thread(target=output, args=(name, process))
            reader.start()
            readers.append(reader)
        # Either arm ending ends the pair. Polling here never inspects page state.
        while True:
            for process in processes:
                code = process.poll()
                if code is not None:
                    if code:
                        raise click.ClickException(f"preview exited {code}")
                    return
            time.sleep(0.1)
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    finally:
        signal.signal(signal.SIGTERM, previous)
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            process.wait()
        for reader in readers:
            reader.join()


def export_preview(
    runtime: Path, launcher: Path, source: Path, slot: str | None
) -> None:
    """Write the page as one offline file under `.tmp/`, and print its path."""
    from leaf_dev.arms import run_directory

    out_dir = run_directory(TMP / "exports")
    with tempfile.TemporaryDirectory(prefix="preview-export-", dir=TMP) as staging:
        page = Path(staging) / "page"
        prepared = prepare_page(
            page,
            read_fixture(source, runtime=runtime, base=runtime),
            partial(leaf, launcher, runtime),
        )
        suffix = f"-{slot}" if slot else ""
        out = out_dir / f"example-{source.stem}{suffix}.html"
        leaf(launcher, runtime, "page", "export", str(page), "-o", str(out))
    print(
        preparation_note(source, prepared.data_sources, prepared.versions),
        end="\n\n",
    )
    print(out.resolve())


if __name__ == "__main__":
    preview()
