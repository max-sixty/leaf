"""Page initialization, and the layer record that selects a page's packages.

A page records its selection (`registry.storage.LAYER`); every Leaf that reads it
composes the layer itself (`layer.selected_layer`). A package selected by name is the
reading Leaf's, bundled or installed on its machine. A package selected by path is
copied into the page's `packages/` and recorded as that copy, since the path names a
directory relative to where `page init` ran, which no other reader can find: the
Codex adapter, a server started elsewhere, or the website's container. Edits to it
reach the page at the next `page init --package`. Changing the selection, or
taking the page to this Leaf's page protocol, refreshes an active revision from
valid source before returning, so deliveries use the new vocabulary without needing
a browser or state read first. Invalid source keeps its last good revision and
reports its check errors. A page with no active revision stays unactivated.
"""

from __future__ import annotations

import re
import secrets
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from .event_log import start_log
from .findings import Finding, note
from .harness import Harness, session_harness
from .hosting import restarting_server
from .layer import (
    checked_layer_inputs,
    compose_layer,
    input_paths,
    layer_inputs,
)
from .leases import lock_is_held, page_locked
from .locations import first_overlap, located, path_is_within
from .refusals import Refused
from .registry.kernel import kernel_protocol
from .registry.storage import LAYER, layer_record
from .schema import (
    HTML_NAME,
    LAYER_FILE,
    PACKAGE_DIRS,
    PACKAGE_FILES,
    PACKAGES_DIR,
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
from .session_runtime import select_checkout
from .state import (
    EVENTS_FILE,
    SESSION_SUFFIX,
    remove_claim,
    session_file,
    session_record,
)
from .themes import ThemeChoice, selected_theme, with_theme
from .validation.source import check_source


def cmd_init(
    page_dir: Path,
    selected: tuple[str, ...] | None = None,
    *,
    theme: ThemeChoice = None,
    dry_run: bool = False,
) -> dict:
    """Create a page, or rewrite an existing one's layer record inside a restart of
    its service.

    Everything that can refuse the rewrite is decided first, in a dry run with the
    page still served, so a refused one leaves its server untouched: a restart
    would bring this Leaf's server back over a record it may not serve.
    An unchanged record and package copies need no transition, so neither
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
            f"{page_dir} does not exist; initialize it before planning a change"
        )
    if made:
        _refuse_package_target(
            page_dir,
            layer_inputs(
                with_theme(selected or (), selected_theme(page_dir, theme, fresh=True))
            ),
        )
        page_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    harness = session_harness()
    if (page_dir / EVENTS_FILE).is_file():
        if dry_run:
            with page_locked(page_dir):
                plan = _plan_page(page_dir, selected, theme=theme, fresh=False)
            return {"page": str(page_dir), "changed": plan.changed}
        if unready := _unready(
            page_dir, _reinit(page_dir, selected, harness, theme=theme)
        ):
            note(unready)
    else:
        if dry_run:
            raise Refused(f"{page_dir} is not initialized")
        with restarting_server(page_dir, harness), page_locked(page_dir):
            try:
                _init_page(page_dir, selected, theme=theme)
            except BaseException:
                if made and not any(page_dir.iterdir()):
                    page_dir.rmdir()
                raise
    if harness is not None:
        # The copy the session loaded may not read the page at this protocol.
        select_checkout(harness.session)
    return {"page": str(page_dir)}


def renew_layer(
    page_dir: Path, harness: Harness | None, *, command: bool
) -> Finding | None:
    """Take a page at an older page protocol, which this Leaf cannot serve
    (`event_contracts.write_refusal`), to this Leaf's, for the session `harness`
    names, and say what still holds the page back, for its agent to act on.

    A plugin update that bumps the page protocol reaches a session once it loads the
    update (`layer-registry.md`, "Page protocol", says when), and its
    Leaf then refuses every page the session holds until the agent runs the
    `leaf page init` the refusal names. That init keeps the page's log, and so
    its threads and decisions, its source and its selection, so it asks nothing of
    the agent's judgment, and the first Leaf to act for the page's session makes it
    instead: a write command naming the page (`cli.page_argument`) or a prompt or
    Stop hook (`hook_transport.read_plans`). Only the session holding the page renews
    it, or any caller while no live session does: another session may still run the
    Leaf that initialized the page, which renewing would lock out of it, and its own
    first hook under this Leaf renews it. Nor does it renew a page a newer Leaf
    initialized, which `_plan_page` refuses.

    A `command` from a checkout also selects that checkout to deliver for the
    session (`session_runtime.select_checkout`); a hook leaves the selection alone.

    What it finds is why the renewal was refused, or the `page check` errors that
    keep index.html from activating under the new layer, since a source an older
    Leaf accepted may fail this one's checks. None where the page needed no
    renewal or took one cleanly. Each of these readings is taken again under the
    page lock and transaction the renewal holds, since another Leaf, newer or
    older, may re-initialize the page or another session take it in between."""

    def renewable() -> bool:
        from .event_contracts import write_refusal

        refusal = write_refusal(page_dir)
        if refusal is None or refusal.code != "foreign-layer":
            return False
        claim = page_claim(page_dir)
        # Record.read leaves another Leaf's format alone. Its file still names
        # an owner we cannot prove ended, so automatic renewal must leave it too.
        if claim is None and claim_path(page_dir).is_file():
            return False
        if claimant_matches(claim, harness):
            return True
        if (
            claim is not None
            and session_record(claim["id"]) is None
            and session_file(claim["id"], SESSION_SUFFIX).is_file()
        ):
            return False
        return not claim_is_active(claim)

    if not renewable():
        return None
    try:
        errors = _reinit(page_dir, None, harness, renewable)
    except Refused as error:
        return Finding(
            "renewal-refused", values={"page": str(page_dir), "error": str(error)}
        )
    if command and harness is not None:
        select_checkout(harness.session)
    return _unready(page_dir, errors)


def _reinit(
    page_dir: Path,
    selected: tuple[str, ...] | None,
    harness: Harness | None,
    still: Callable[[], bool] = lambda: True,
    *,
    theme: ThemeChoice = None,
) -> list[Finding]:
    """Rewrite an initialized page's layer record inside a restart of its service,
    returning the errors that keep its index.html from activating under the new
    layer. Everything that can refuse is decided first, with the page still served,
    and an unchanged record restarts nothing (`cmd_init`). `still` says, under each
    lock, whether the rewrite is still wanted."""
    with page_locked(page_dir):
        if not still():
            return []
        plan = _plan_page(page_dir, selected, theme=theme, fresh=False)
    if not plan.changed:
        return []
    with restarting_server(page_dir, harness), page_locked(page_dir):
        return _init_page(page_dir, selected, still, theme=theme)


def _unready(page_dir: Path, errors: list[Finding]) -> Finding | None:
    """What a re-initialization that left `errors` tells the agent, or None for
    none."""
    if not errors:
        return None
    return Finding(
        "unready-reinit",
        values={"page": str(page_dir), "errors": [str(error) for error in errors]},
    )


def start_throwaway_page(page_dir: Path, packages: tuple[str, ...]) -> None:
    """Start a page in an empty directory selecting `packages`, for a reading Leaf
    takes and then deletes, as `package check --render` does with a package's
    worked examples."""
    LAYER.write(page_dir / LAYER_FILE, _record(packages, None, None))
    start_log(page_dir)


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
    *,
    theme: ThemeChoice = None,
) -> list[Finding]:
    """Start or re-select the page under its lock and its service's restart, and
    return what keeps a re-selected index.html from activating; a re-selection
    `still` no longer wants under the transaction commits nothing."""
    from .revisioning import activate_checked_source

    # The restart around this took the server down, but the page lock came after
    # it, and a start can land in between.
    if lock_is_held(page_dir / SERVER_LOCK):
        raise Refused(
            f"a server started on {page_dir} while it was being re-initialized; "
            f"re-run `leaf page init {page_dir}`"
        )
    # Successful init creates the append-only log's stable inode. A directory
    # the caller prepared is still a fresh page until that marker exists: it
    # keeps the caller's chosen mode, takes no PageTransaction yet, and a failed
    # validation leaves it untouched.
    if not (page_dir / EVENTS_FILE).is_file():
        plan = _plan_page(page_dir, selected, theme=theme, fresh=True)
        # A page's claim lives outside its directory. Recreating a deleted path
        # creates a new page, so it must not inherit the deleted page's owner.
        remove_claim(claim_path(page_dir))
        _write_record(page_dir, plan)
        start_log(page_dir)
        return []
    # The page lock serializes this operation with other inits; an existing
    # page also has its ordinary transaction, which gives the record one order
    # against every browser append. No path takes the page transaction and then
    # the page lock, so this order cannot invert.
    with PageTransaction(page_dir) as page:
        if not still():
            return []
        plan = _plan_page(page_dir, selected, theme=theme, fresh=False)
        if not plan.changed:
            return []
        _write_record(page_dir, plan)
        checked = check_source(page_dir, page.events)
        if checked.revision.active:
            activate_checked_source(page, checked)
        return checked.errors


class _PagePlan(NamedTuple):
    """An admitted init, decided before anything is written: the record it writes,
    the package directories it copies into the page, by the name of each copy, and
    whether either differs from the page's."""

    record: dict
    copies: dict[str, Path]
    changed: bool


def _plan_page(
    page_dir: Path,
    selected: tuple[str, ...] | None,
    *,
    fresh: bool,
    theme: ThemeChoice = None,
) -> _PagePlan:
    """Compose the selected layer, refusing a selection this Leaf cannot compose,
    before anything is written.

    A page a newer Leaf initialized, at a higher page protocol, is refused rather
    than taken back to this Leaf's: a process the session started before its plugin
    updated, or an agent following an older Leaf's advice, would otherwise take the
    page down, and the newer Leaf's next command or hook up again, reloading the
    user's tabs each time."""
    if not fresh:
        from .event_contracts import write_refusal

        if (refusal := write_refusal(page_dir)) and refusal.code == "newer-layer":
            raise Refused(str(refusal))
    previous = None if fresh else layer_record(page_dir)
    captured_theme = selected_theme(page_dir, theme, fresh=fresh)
    # A selection the caller names resolves where they run; the page's own, against
    # the copies it holds.
    named = selected is not None
    if not named:
        selected = tuple(previous["packages"]) if previous else ()
    inputs = layer_inputs(
        with_theme(selected, captured_theme), Path.cwd() if named else page_dir
    )
    _refuse_package_target(page_dir, inputs)
    roots = checked_layer_inputs(inputs)
    _refuse_input_destination_overlap(roots, page_dir.resolve())
    compose_layer(roots)
    copies = _copies(selected) if named else {}
    record = _record(
        tuple(
            f"./{PACKAGES_DIR}/{copies[value].name}" if value in copies else value
            for value in selected
        ),
        captured_theme,
        previous,
    )
    copied = {root.name: root for root in copies.values()}
    if record == previous and any(
        _package_files(root) != _package_files(page_dir / PACKAGES_DIR / name)
        for name, root in copied.items()
    ):
        # A copy's new bytes change what an open document runs under.
        record = {**record, "generation": secrets.token_hex(16)}
    return _PagePlan(record, copied, record != previous)


def _copies(selected: tuple[str, ...]) -> dict[str, Path]:
    """The package directory each path in `selected` names, resolved against the
    working directory, refusing two whose copies in the page would share a name."""
    copies = {}
    for value in selected:
        if re.fullmatch(HTML_NAME, value):
            continue
        root = Path(value).expanduser().resolve()
        if other := next(
            (seen for seen, held in copies.items() if held.name == root.name), None
        ):
            raise Refused(
                f"packages {other!r} and {value!r} share the directory name "
                f"{root.name!r}; a page keeps each package it selects by path under "
                f"{PACKAGES_DIR}/ by that name"
            )
        copies[value] = root
    return copies


def _package_files(root: Path) -> dict[str, bytes]:
    """The files of package `root` a layer composes (`layer.checked_inputs`)."""
    files = {}
    for name in PACKAGE_FILES:
        if (root / name).is_file():
            files[name] = (root / name).read_bytes()
    for sub in PACKAGE_DIRS:
        if (root / sub).is_dir():
            for path in sorted((root / sub).rglob("*")):
                if path.is_file():
                    files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


def _record(
    selected: tuple[str, ...], theme: dict | None, previous: dict | None
) -> dict:
    """The layer record selecting `selected` and `theme` at this Leaf's protocol,
    keeping `previous`'s generation where it selects the same: a generation names a
    change in what an open document runs under, not an invocation."""
    record = {
        "packages": list(selected),
        "theme": theme,
        "protocol": kernel_protocol(),
    }
    if previous is not None and all(
        previous.get(key) == value for key, value in record.items()
    ):
        return previous
    return {**record, "generation": secrets.token_hex(16)}


def _write_record(page_dir: Path, plan: _PagePlan) -> None:
    """Write `plan`'s copies into the page, then its record. A copy the new selection
    drops stays, since a stored revision's manifest may still name it."""
    held = page_dir / PACKAGES_DIR
    for name, root in plan.copies.items():
        target = held / name
        if root == target.resolve():
            continue
        staged = held / f"{name}.staged"
        shutil.rmtree(staged, ignore_errors=True)
        staged.mkdir(parents=True)
        for path, data in _package_files(root).items():
            (staged / path).parent.mkdir(parents=True, exist_ok=True)
            (staged / path).write_bytes(data)
        shutil.rmtree(target, ignore_errors=True)
        staged.rename(target)
    LAYER.write(page_dir / LAYER_FILE, plan.record)


def _refuse_input_destination_overlap(roots: list[Path], page_target: Path) -> None:
    # The page's own package copies are inputs `_write_record` writes.
    destinations = [
        *(page_target / name for name in PAGE_OWNED_FILES),
        *(page_target / sub for sub in PAGE_OWNED_DIRS if sub != PACKAGES_DIR),
    ]
    if overlap := first_overlap(located(input_paths(roots)), located(destinations)):
        package, destination = overlap
        raise Refused(
            f"package {package} overlaps page destination "
            f"{destination}; package and page paths must be separate"
        )
