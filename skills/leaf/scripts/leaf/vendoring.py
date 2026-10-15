"""Page initialization and atomic layer vendoring."""

from __future__ import annotations

import contextlib
import json
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from .files import read_json, replace_files
from .findings import Finding, note
from .harness import Harness, session_harness
from .hosting import restarting_server
from .layer import (
    LayerComposition,
    checked_layer_inputs,
    compose_layer,
    input_paths,
    layer_fingerprint,
    layer_inputs,
    payload_provenance,
    payload_server_fingerprint,
)
from .leases import lock_is_held, page_locked
from .locations import located, locations_overlap, path_is_within, path_location
from .refusals import Refused
from .registry.storage import RegistryError, layer_metadata, layer_packages
from .schema import (
    CURSOR_FILE,
    LAYER_PLACEHOLDER,
    PACKAGE_DIRS,
    PAGE_OWNED_DIRS,
    PAGE_OWNED_FILES,
    SERVER_LOCK,
)
from .service import (
    PageTransaction,
    claim_is_active,
    claim_path,
    claimant_matches,
    page_claim,
)
from .state import EVENTS_FILE, json_bytes
from .validation.source import check_source


def cmd_init(
    page_dir: Path, selected: tuple[str, ...] | None = None, *, dry_run: bool = False
) -> None:
    """Create a page, or re-vendor one inside a restart of its service.

    Everything that can refuse a re-vendor is decided first, in a dry run with the
    page still served, so a refused re-vendor leaves its server untouched: a
    restart would bring this Leaf's server back over the layer the page keeps.
    An identical installed layer and serving contract need no transition, so neither
    files nor the server change. `dry_run` reports this decision without committing.
    Only a changed contract takes the service down (`hosting.restarting_server`)
    for the init itself, which decides again under the page transaction, since the page may
    have moved in between: the restart's stop needs the page lock, so neither step
    can hold it across the gap.

    The page lock is the directory itself, so a page that does not exist yet is
    made first, owner-only: the directory holds the discussion and service state
    whose URL carries the machine key. A directory the caller already made keeps
    the mode they chose, and a refused init takes back the empty directory it made.
    """
    made = not page_dir.exists()
    if dry_run and made:
        raise Refused(
            f"{page_dir} does not exist; initialize it before planning a re-vendor"
        )
    if made:
        _refuse_package_target(page_dir, layer_inputs(selected or ()))
        page_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if (page_dir / EVENTS_FILE).is_file():
        if dry_run:
            with page_locked(page_dir):
                plan = _plan_page(page_dir, selected, fresh=False)
            print(json.dumps({"page": str(page_dir), "changed": plan.changed}))
            return
        unready = _unready(page_dir, _revendor(page_dir, selected, session_harness()))
        print(json.dumps({"page": str(page_dir)}))
        if unready:
            note(unready)
        return
    if dry_run:
        raise Refused(f"{page_dir} is not initialized")
    with restarting_server(page_dir, session_harness()), page_locked(page_dir):
        try:
            _init_page(page_dir, selected)
        except BaseException:
            if made and not any(page_dir.iterdir()):
                page_dir.rmdir()
            raise
    print(json.dumps({"page": str(page_dir)}))


def renew_layer(page_dir: Path, harness: Harness | None) -> Finding | None:
    """Re-vendor a page vendored at an older page protocol, which this Leaf cannot
    serve (`event_contracts.write_refusal`), for the session `harness` names, and say
    what still holds the page back, for its agent to act on.

    A plugin update that bumps the page protocol reaches a running session, and its
    Leaf then refuses every page the session holds until the agent runs the
    `leaf page init` the refusal names. That re-vendor keeps the page's log, and so
    its threads and decisions, and its source, so it asks nothing of the agent's
    judgment, and the first Leaf to act for the page's session makes it instead: a
    command naming the page (`cli.resolve_dir`) or a prompt or Stop hook
    (`hook_transport.read_plans`). Only the session holding the page renews it, or
    any caller while no live session does: another session may still run the Leaf
    that vendored the page, which a re-vendor would lock out of it, and its own
    first hook under this Leaf renews it. Nor does it renew a page a newer Leaf
    vendored, which `_plan_page` refuses. A layer documenting an x- key this Leaf
    does not admit stays refused too: the key may be one a newer Leaf added at the
    same protocol, which a re-vendor here would strip.

    What it finds is why the re-vendor was refused, or the `page check` errors that
    keep index.html from activating under the new layer, since a source an older
    Leaf accepted may fail this one's checks. None where the page needed no
    re-vendor or took one cleanly. Each of these readings is taken again under the
    page lock and transaction the re-vendor holds, since another Leaf, newer or
    older, may re-vendor the page or another session take it in between."""

    def renewable() -> bool:
        from .event_contracts import write_refusal

        refusal = write_refusal(page_dir)
        if refusal is None or refusal.code != "foreign-layer":
            return False
        claim = page_claim(page_dir)
        return not claim_is_active(claim) or claimant_matches(claim, harness)

    if not renewable():
        return None
    try:
        return _unready(page_dir, _revendor(page_dir, None, harness, renewable))
    except Refused as error:
        return Finding(
            "revendor-refused", values={"page": str(page_dir), "error": str(error)}
        )


def _revendor(
    page_dir: Path,
    selected: tuple[str, ...] | None,
    harness: Harness | None,
    still: Callable[[], bool] = lambda: True,
) -> list[Finding]:
    """Re-vendor an initialized page inside a restart of its service, returning the
    errors that keep its index.html from activating under the new layer. Everything
    that can refuse is decided first, with the page still served, and an unchanged
    contract restarts nothing (`cmd_init`). `still` says, under each lock, whether
    the re-vendor is still wanted."""
    with page_locked(page_dir):
        if not still():
            return []
        plan = _plan_page(page_dir, selected, fresh=False)
    if not plan.changed:
        return []
    with restarting_server(page_dir, harness), page_locked(page_dir):
        return _init_page(page_dir, selected, still)


def _unready(page_dir: Path, errors: list[Finding]) -> Finding | None:
    """What a re-vendor that left `errors` tells the agent, or None for none."""
    if not errors:
        return None
    return Finding(
        "unready-revendor",
        values={"page": str(page_dir), "errors": [str(error) for error in errors]},
    )


def start_throwaway_page(page_dir: Path, composition: LayerComposition) -> None:
    """Start a page in an empty directory from a layer already composed, for a reading
    Leaf takes and then deletes, as `package check --render` does with a package's
    worked examples.

    It records no package selection: the composition may include a package by a path
    a page cannot record (`layer.resolve_packages`), and nothing re-vendors a page
    that is thrown away."""
    layer = _stamp_layer(composition, ())
    plan = _PagePlan(True, layer, _checked_destinations(page_dir, layer), True)
    _commit_layer(page_dir, plan)


def _refuse_package_target(page_dir: Path, inputs: list[Path]) -> None:
    """Refuse a page directory inside one of its own layer's packages.

    This runs before anything is written, since a rejected init must not put page
    state inside an input it was trying to protect."""
    target = page_dir.resolve()
    if package := next((root for root in inputs if path_is_within(target, root)), None):
        raise Refused(f"{page_dir} is inside package {package}, not a page directory")


def _init_page(
    page_dir: Path,
    selected: tuple[str, ...] | None,
    still: Callable[[], bool] = lambda: True,
) -> list[Finding]:
    """Start or re-vendor the page under its lock and its service's restart, and
    return what keeps a re-vendored index.html from activating; a re-vendor `still`
    no longer wants under the transaction commits nothing."""
    # The restart around this took the server down, but the page lock came after
    # it, and a start can land in between.
    if lock_is_held(page_dir / SERVER_LOCK):
        raise Refused(
            f"a server started on {page_dir} while it was being re-vendored; "
            f"re-run `leaf page init {page_dir}`"
        )
    # Successful init creates the append-only log's stable inode. A directory
    # the caller prepared is still a fresh page until that marker exists: it
    # keeps the caller's chosen mode, takes no PageTransaction yet, and a failed
    # validation leaves it untouched.
    if not (page_dir / EVENTS_FILE).is_file():
        _commit_layer(page_dir, _plan_page(page_dir, selected, fresh=True))
        return []
    # The page lock serializes this operation with other inits; an existing
    # page also has its ordinary transaction, which gives the layer commit
    # one order against every browser append. No path takes
    # the page transaction and then the page lock, so this order cannot invert.
    with PageTransaction(page_dir) as page:
        if not still():
            return []
        plan = _plan_page(page_dir, selected, fresh=False)
        if not plan.changed:
            return []
        _commit_layer(page_dir, plan)
        events = page.events
    # The re-vendored layer is in place, but the page shows it only once index.html
    # activates, which runs the same check `page check` does. Say now what would
    # hold it back, rather than leave the next read to refuse it unseen.
    return check_source(page_dir, events).errors


class _PagePlan(NamedTuple):
    """An admitted init, decided before anything is written: whether it starts
    the page, the stamped layer, and the directories that layer needs."""

    fresh: bool
    layer: _VendoredLayer
    directories: set[Path]
    changed: bool


def _plan_page(
    page_dir: Path, selected: tuple[str, ...] | None, *, fresh: bool
) -> _PagePlan:
    """Validate incoming declarations and file destinations before writing.

    A page a newer Leaf vendored, at a higher page protocol, is refused rather than
    taken back to this Leaf's: a process the session started before its plugin
    updated, or an agent following an older Leaf's advice, would otherwise re-vendor
    the page down, and the newer Leaf's next command or hook up again, reloading the
    user's tabs each time."""
    if not fresh:
        from .event_contracts import write_refusal

        if (refusal := write_refusal(page_dir)) and refusal.code == "newer-layer":
            raise Refused(str(refusal))
    if selected is None and fresh:
        selected = ()
    elif selected is None:
        selected = tuple(layer_packages(page_dir))
    inputs = layer_inputs(selected)
    _refuse_package_target(page_dir, inputs)
    roots = checked_layer_inputs(inputs)
    _refuse_input_destination_overlap(roots, page_dir.resolve())
    # Resolve and read the complete incoming layer before the first page write.
    # A bad late package must not leave the registry newer than the theme or its
    # modules.
    composition = compose_layer(roots)
    previous = None
    if not fresh:
        try:
            layer_metadata(page_dir)
            previous = read_json(page_dir / "registry.json")["$layer"]
        except RegistryError:
            # Init repairs damaged installed metadata as well as installed files.
            pass
    layer = _stamp_layer(composition, selected, previous)
    directories = _checked_destinations(page_dir, layer)
    changed = fresh or not _same_installed_layer(page_dir, layer)
    if changed and layer.reused:
        # The source contract agrees, but missing, stale or damaged installed bytes
        # require repair. Invalidate tabs that may already have loaded those bytes.
        layer = _stamp_layer(composition, selected)
    return _PagePlan(fresh, layer, directories, changed)


class _VendoredLayer(NamedTuple):
    top_files: dict[str, bytes]
    directory_files: dict[str, dict[str, bytes]]
    reused: bool


def _same_installed_layer(page_dir: Path, layer: _VendoredLayer) -> bool:
    """An init is a no-op only when all owned files already carry the desired bytes."""
    wanted = {
        **layer.top_files,
        **{
            f"{directory}/{name}": data
            for directory, entries in layer.directory_files.items()
            for name, data in entries.items()
        },
    }
    for name, data in wanted.items():
        path = page_dir / name
        if path.is_symlink() or not path.is_file() or path.read_bytes() != data:
            return False
    return all(
        f"{directory}/{path.relative_to(page_dir / directory).as_posix()}" in wanted
        for directory in PACKAGE_DIRS
        for path in (page_dir / directory).rglob("*")
        if path.is_file() or path.is_symlink()
    )


def _refuse_input_destination_overlap(roots: list[Path], page_target: Path) -> None:
    destinations = [
        *(page_target / name for name in PAGE_OWNED_FILES),
        *(page_target / sub for sub in PAGE_OWNED_DIRS),
    ]
    located_destinations = located(destinations)
    if overlap := next(
        (
            (package, destination)
            for package, package_at in located(input_paths(roots))
            for destination, destination_at in located_destinations
            if locations_overlap(package_at, destination_at)
        ),
        None,
    ):
        package, destination = overlap
        raise Refused(
            f"package {package} overlaps page destination "
            f"{destination}; package and page paths must be separate"
        )


def _stamp_layer(
    composition: LayerComposition,
    selected: tuple[str, ...],
    previous: dict | None = None,
) -> _VendoredLayer:
    fingerprint = layer_fingerprint(composition)
    producer = payload_provenance()
    metadata = {
        "fingerprint": fingerprint,
        "server": payload_server_fingerprint(),
        "packages": list(selected),
        **({"producer": producer} if producer else {}),
    }
    # A generation names a contract transition, not an invocation. Provenance
    # remains the producer of the installed bytes until the contract changes.
    same = previous is not None and all(
        previous.get(key) == metadata[key]
        for key in ("fingerprint", "server", "packages")
    )
    metadata = previous if same else {"generation": secrets.token_hex(16), **metadata}
    incoming = {**composition.registry, "$layer": metadata}
    generation = metadata["generation"]
    top_files = dict(composition.top_files)
    directory_files = {
        name: dict(files) for name, files in composition.directory_files.items()
    }
    client = directory_files["runtime"]["layer-generation.js"]
    directory_files["runtime"]["layer-generation.js"] = client.replace(
        LAYER_PLACEHOLDER, json.dumps(generation).encode()
    )
    # The registry makes the theme and modules live, so it commits last.
    top_files["registry.json"] = json_bytes(incoming)
    return _VendoredLayer(top_files, directory_files, same)


def _checked_destinations(page_dir: Path, layer: _VendoredLayer) -> set[Path]:
    # Resolve every destination conflict before touching the page. A directory
    # where one vendored file belongs must not leave the top-level layer newer
    # than its modules.
    if (page_dir.exists() or page_dir.is_symlink()) and not page_dir.is_dir():
        raise Refused(f"{page_dir} must be a directory")
    file_targets = [
        *(page_dir / name for name in layer.top_files),
        *(
            page_dir / sub / name
            for sub in PACKAGE_DIRS
            for name in layer.directory_files[sub]
        ),
    ]
    directories = {page_dir / sub for sub in PAGE_OWNED_DIRS}
    for target in file_targets:
        for parent in target.parents:
            if parent == page_dir:
                break
            directories.add(parent)
    located_files = [(target, path_location(target)) for target in file_targets]
    located_directories = [
        (directory, path_location(directory)) for directory in directories
    ]
    if collision := next(
        (
            (left, right)
            for index, (left, left_at) in enumerate(located_files)
            for right, right_at in located_files[index + 1 :]
            if left_at == right_at
        ),
        None,
    ):
        left, right = collision
        raise Refused(f"the incoming layer maps both {left} and {right} to one file")
    if collision := next(
        (
            (file, directory)
            for file, file_at in located_files
            for directory, directory_at in located_directories
            if file_at == directory_at
        ),
        None,
    ):
        file, directory = collision
        raise Refused(
            f"the incoming layer maps {file} as a file and {directory} as a directory"
        )
    for destination in sorted(directories, key=lambda path: len(path.parts)):
        if destination.is_symlink():
            raise Refused(f"{destination} must be a real directory, not a symlink")
        if (
            destination.exists() or destination.is_symlink()
        ) and not destination.is_dir():
            raise Refused(f"{destination} must be a directory")
    for target in file_targets:
        if (target.exists() or target.is_symlink()) and not target.is_file():
            raise Refused(f"{target} must be a file")
    return directories


def _commit_layer(page_dir: Path, plan: _PagePlan) -> None:
    fresh, layer, directories = plan.fresh, plan.layer, plan.directories
    if fresh:
        # A page's claim lives outside its directory. Recreating a deleted path
        # creates a new page, so it must not inherit the deleted page's owner.
        # Re-vendoring an existing page preserves that page and its claim.
        claim_path(page_dir).unlink(missing_ok=True)
    for directory in sorted(directories, key=lambda path: len(path.parts)):
        directory.mkdir(exist_ok=True)
    # Stage the whole layer together. The registry is the declaration that
    # makes every other file live, so it is the final replacement.
    writes = [
        (page_dir / name, data, False)
        for name, data in layer.top_files.items()
        if name != "registry.json"
    ]
    writes.extend(
        (page_dir / sub / name, data, False)
        for sub in PACKAGE_DIRS
        for name, data in layer.directory_files[sub].items()
    )
    writes.append((page_dir / "registry.json", layer.top_files["registry.json"], False))
    replace_files(writes)

    for sub in PACKAGE_DIRS:
        destination = page_dir / sub
        wanted = set(layer.directory_files[sub])
        for stale in sorted(
            destination.rglob("*"), key=lambda path: len(path.parts), reverse=True
        ):
            relative = stale.relative_to(destination).as_posix()
            if relative not in wanted and (stale.is_symlink() or stale.is_file()):
                stale.unlink()
            elif stale.is_dir():
                with contextlib.suppress(OSError):
                    stale.rmdir()
    # The append-only log's stable inode is also the successful-init marker and
    # the page transaction lease. Publish it only after the layer commits, so a
    # failed first write still takes the fresh-init path.
    if fresh:
        # A log this page starts holds nothing the old one's user acknowledged,
        # so the acknowledgement position goes with the log it named. Re-vendoring
        # an existing page keeps both.
        (page_dir / CURSOR_FILE).unlink(missing_ok=True)
        replace_files([(page_dir / EVENTS_FILE, b"", False)])
