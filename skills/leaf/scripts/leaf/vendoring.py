"""Page initialization and atomic layer vendoring."""

import contextlib
import json
import secrets
import sys
from pathlib import Path
from typing import NamedTuple

from .data_contracts import (
    data_contract_transition_errors,
    merge_data_bindings,
    page_data_documents,
    working_data_bindings,
)
from .event_log import now_iso
from .files import (
    json_bytes,
    latest_revision,
    read_json,
    replace_files,
    write_json,
)
from .layer import (
    LayerComposition,
    checked_layer_inputs,
    compose_layer,
    input_paths,
    layer_fingerprint,
    layer_inputs,
    payload_provenance,
    payload_runtime_fingerprint,
)
from .leases import lock_is_held, page_locked
from .locations import located, locations_overlap, path_is_within, path_location
from .projection import page_reading
from .registry.contract import read_registry_declarations
from .registry.page import compose_page_registry
from .schema import (
    CURSOR_FILE,
    EVENTS_FILE,
    LAYER_PLACEHOLDER,
    PACKAGE_DIRS,
    PAGE_OWNED_DIRS,
    PAGE_OWNED_FILES,
    SERVER_LOCK,
    SERVICE_FILE,
    STATUS_FILE,
)
from .service import PageTransaction, claim_path
from .structure import SourceDocument, parse_revision
from .validation.compatibility import candidate_vocabulary_gaps
from .validation.source import check_source
from .work import widget_work_without_targets


def cmd_init(page_dir: Path, selected: tuple[str, ...] | None = None) -> None:
    # The page lock is the directory itself, so a page that does not exist yet is
    # made first, owner-only: the directory holds the discussion and service
    # state whose URL carries the machine key. A directory the caller already
    # made keeps the mode they chose. The lock then covers the complete vendoring,
    # and a refused init takes back the empty directory it made.
    made = not page_dir.exists()
    if made:
        _refuse_package_target(page_dir, layer_inputs(selected or ()))
        page_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    with page_locked(page_dir):
        try:
            _init_page(page_dir, selected)
        except BaseException:
            if made and not any(page_dir.iterdir()):
                page_dir.rmdir()
            raise


def _refuse_package_target(page_dir: Path, inputs: list[Path]) -> None:
    """Refuse a page directory inside one of its own layer's packages.

    This runs before anything is written, since a rejected init must not put page
    state inside an input it was trying to protect."""
    target = page_dir.resolve()
    if package := next((root for root in inputs if path_is_within(target, root)), None):
        sys.exit(f"{page_dir} is inside package {package}, not a page directory")


def _init_page(page_dir: Path, selected: tuple[str, ...] | None) -> None:
    service = read_json(page_dir / SERVICE_FILE)
    server_live = lock_is_held(page_dir / SERVER_LOCK)
    if server_live or (service and service["enabled"]):
        sys.exit(
            f"cannot re-vendor {page_dir} while its service is enabled. "
            f"Run `leaf server stop {page_dir}` first."
        )
    # Successful init creates the append-only log's stable inode. A directory
    # the caller prepared is still a fresh page until that marker exists: it
    # keeps the caller's chosen mode, takes no PageTransaction yet, and a failed
    # validation leaves it untouched.
    fresh = not (page_dir / EVENTS_FILE).is_file()
    if selected is None and fresh:
        selected = ()
    elif selected is None:
        recorded = (
            (read_json(page_dir / "registry.json") or {})
            .get("$layer", {})
            .get("packages", [])
        )
        if (
            not isinstance(recorded, list)
            or not all(
                isinstance(selection, str) and selection for selection in recorded
            )
            or len(set(recorded)) != len(recorded)
        ):
            sys.exit(
                f"{page_dir / 'registry.json'}: $layer.packages must be a unique "
                "list of non-empty package selections"
            )
        selected = tuple(recorded)
    inputs = layer_inputs(selected)
    page_target = page_dir.resolve()
    _refuse_package_target(page_dir, inputs)
    if fresh:
        _vendor_page(
            page_dir,
            fresh=True,
            events=[],
            inputs=inputs,
            page_target=page_target,
            selected=selected,
        )
        return
    # The page lock serializes this operation with other inits; an existing
    # page also has its ordinary transaction, which gives the vocabulary check
    # and contract commit one order against every browser append. No path takes
    # the page transaction and then the page lock, so this order cannot invert.
    with PageTransaction(page_dir) as page:
        _vendor_page(
            page_dir,
            fresh=False,
            events=page.events,
            inputs=inputs,
            page_target=page_target,
            selected=selected,
        )
        events = page.events
    # The re-vendored layer is in place, but the page shows it only once index.html
    # activates, which runs the same check `version check` does. Say now what would
    # hold it back, rather than leave the next read to refuse it unseen.
    check = check_source(page_dir, events, allow_transition=False)
    if check.errors:
        print(
            f"re-vendored {page_dir}, but index.html will not activate until "
            "`leaf version check` passes:",
            file=sys.stderr,
        )
        for error in check.errors:
            print(f"  - {error}", file=sys.stderr)


class _VendoredLayer(NamedTuple):
    top_files: dict[str, bytes]
    directory_files: dict[str, dict[str, bytes]]


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
        sys.exit(
            f"package {package} overlaps page destination "
            f"{destination}; package and page paths must be separate"
        )


def _refuse_vocabulary_drift(
    page_dir: Path, events: list[dict], incoming: dict
) -> None:
    revision = latest_revision(page_dir)
    if revision is None:
        return
    try:
        document = SourceDocument((page_dir / "index.html").read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError):
        # An unreadable candidate cannot activate, but re-vendoring must still
        # preserve the active page until the source is repaired.
        document = parse_revision(page_dir, revision)
    gaps = candidate_vocabulary_gaps(
        page_dir,
        events,
        document,
        incoming,
        revision,
    )
    if gaps:
        sys.exit(
            "this page's log holds vocabulary the incoming layer no longer speaks:\n"
            + "\n".join(f"  - {g}" for g in gaps)
            + "\nre-vendoring would silently stop these replaying — the user's"
            " recorded decisions among them."
        )


def _refuse_data_contract_drift(
    page_dir: Path, events: list[dict], incoming: dict
) -> None:
    # The outgoing registry is historical input, not a contract arriving at the
    # current code's boundary. It may legitimately predate a new kernel invariant;
    # validating it with today's rules would prevent `page init` from replacing the
    # exact older layer it exists to migrate. Binding discovery only reads x-data.
    if current := read_json(page_dir / "registry.json"):
        documents = page_data_documents(page_dir, events)
        standing_bindings, standing_errors = working_data_bindings(
            page_dir, current, events
        )
        incoming_bindings, incoming_errors = merge_data_bindings(documents, incoming)
        binding_errors = list(dict.fromkeys(standing_errors + incoming_errors))
        binding_changes = [
            (
                f"source {source!r} loses its contract {contract!r}"
                if source not in incoming_bindings
                else f"source {source!r} changes from contract {contract!r} to "
                f"{incoming_bindings[source]!r}"
            )
            for source, contract in standing_bindings.items()
            if incoming_bindings.get(source) != contract
        ]
        contract_changes = data_contract_transition_errors(page_dir, events, incoming)
        if binding_errors or binding_changes or contract_changes:
            sys.exit(
                "this page's immutable documents do not keep one meaning for each "
                "data source:\n"
                + "\n".join(
                    f"  - {error}"
                    for error in binding_errors + binding_changes + contract_changes
                )
                + "\npreserve those bindings in the incoming registry before "
                "re-vendoring."
            )


def _refuse_untargeted_work(page_dir: Path, events: list[dict], incoming: dict) -> None:
    revision = latest_revision(page_dir)
    if revision is None:
        return
    document = parse_revision(page_dir, revision)
    page = page_reading(document, events, incoming, revision)
    untargeted = widget_work_without_targets(
        document,
        page.projection,
        events,
        read_json(page_dir / STATUS_FILE) or {},
        incoming,
    )
    if untargeted:
        sys.exit(
            "the incoming layer would remove the local target for active widget work on "
            + ", ".join(repr(widget) for widget in untargeted)
            + "; stamp a later version with --completes for that work before "
            "re-vendoring"
        )


def _validate_page_transition(
    page_dir: Path, events: list[dict], incoming: dict
) -> None:
    _refuse_vocabulary_drift(page_dir, events, incoming)
    _refuse_data_contract_drift(page_dir, events, incoming)
    _refuse_untargeted_work(page_dir, events, incoming)


def _effective_registry(page_dir: Path, composition: LayerComposition) -> dict:
    """Compose authored declarations over the prospective vendored layer."""
    source = page_dir / "page" / "registry.json"
    declarations = read_registry_declarations(source) or {}
    widget_paths = {
        *(f"widgets/{name}" for name in composition.directory_files["widgets"]),
        *(
            path.relative_to(page_dir).as_posix()
            for path in (page_dir / "page" / "widgets").glob("lf-*.js")
            if path.is_file()
        ),
    }
    return compose_page_registry(
        composition.registry,
        declarations,
        widget_paths,
        source=source,
    ).registry


def _stamp_layer(
    composition: LayerComposition, selected: tuple[str, ...]
) -> _VendoredLayer:
    # `page init` is the contract transition, even when its input bytes happen to
    # match the last run. The browser carries this epoch on every write so an open
    # tab cannot post through a runtime whose server contract was re-vendored under it.
    generation = secrets.token_hex(16)
    fingerprint = layer_fingerprint(composition)
    producer = payload_provenance()
    incoming = composition.registry
    incoming["$layer"] = {
        "generation": generation,
        "fingerprint": fingerprint,
        # The kernel half of that composition, stamped on its own because it is the
        # half another Leaf can read the page against anywhere: the selection beside
        # it was resolved against the project `page init` ran in, so nothing away from
        # that directory can recompose the fingerprint. The browser gates compare this
        # to refuse a page whose runtime their probe modules cannot import from.
        "runtime": payload_runtime_fingerprint(),
        "packages": list(selected),
        **({"producer": producer} if producer else {}),
    }
    top_files = composition.top_files
    directory_files = composition.directory_files
    client = directory_files["runtime"]["layer-client.js"]
    directory_files["runtime"]["layer-client.js"] = client.replace(
        LAYER_PLACEHOLDER, json.dumps(generation).encode()
    )
    # The registry makes the theme and modules live, so it commits last.
    top_files["registry.json"] = json_bytes(incoming)
    return _VendoredLayer(top_files, directory_files)


def _checked_destinations(page_dir: Path, layer: _VendoredLayer) -> set[Path]:
    # Resolve every destination conflict before touching the page. A directory
    # where one vendored file belongs must not leave the top-level layer newer
    # than its modules.
    if (page_dir.exists() or page_dir.is_symlink()) and not page_dir.is_dir():
        sys.exit(f"{page_dir} must be a directory")
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
        sys.exit(f"the incoming layer maps both {left} and {right} to one file")
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
        sys.exit(
            f"the incoming layer maps {file} as a file and {directory} as a directory"
        )
    for destination in sorted(directories, key=lambda path: len(path.parts)):
        if destination.is_symlink():
            sys.exit(f"{destination} must be a real directory, not a symlink")
        if (
            destination.exists() or destination.is_symlink()
        ) and not destination.is_dir():
            sys.exit(f"{destination} must be a directory")
    for target in file_targets:
        if (target.exists() or target.is_symlink()) and not target.is_file():
            sys.exit(f"{target} must be a file")
    return directories


def _commit_layer(
    page_dir: Path,
    *,
    fresh: bool,
    layer: _VendoredLayer,
    directories: set[Path],
) -> None:
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
    if not (page_dir / STATUS_FILE).exists():
        # Fresh creation holds only the page lock. Re-vendoring also
        # holds the page transaction. Calling cmd_status would try to re-enter the
        # latter's event-log flock for an existing directory missing status.
        write_json(
            page_dir / STATUS_FILE,
            {
                "state": "working",
                "detail": "Writing the page",
                "ts": now_iso(),
                "after": 0,
            },
        )
    # The append-only log's stable inode is also the successful-init marker and
    # the page transaction lease. Publish it only after the layer and initial
    # status commit, so a failed first write still takes the fresh-init path.
    if fresh:
        # A log this page starts holds nothing the old one's user acknowledged,
        # so the acknowledgement position goes with the log it named. Re-vendoring
        # an existing page keeps both.
        (page_dir / CURSOR_FILE).unlink(missing_ok=True)
        replace_files([(page_dir / EVENTS_FILE, b"", False)])
    print(f"initialized {page_dir}")


def _vendor_page(
    page_dir: Path,
    *,
    fresh: bool,
    events: list[dict],
    inputs: list[Path],
    page_target: Path,
    selected: tuple[str, ...],
) -> None:
    roots = checked_layer_inputs(inputs)
    _refuse_input_destination_overlap(roots, page_target)
    # Resolve and read the complete incoming layer before the first page write.
    # A bad late package must not leave the registry newer than the theme or its
    # modules.
    composition = compose_layer(roots)
    _validate_page_transition(
        page_dir, events, _effective_registry(page_dir, composition)
    )
    layer = _stamp_layer(composition, selected)
    directories = _checked_destinations(page_dir, layer)
    _commit_layer(page_dir, fresh=fresh, layer=layer, directories=directories)
