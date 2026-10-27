"""Page initialization, and the layer record that selects a page's packages.

A page records its selection (`registry.storage.LAYER`); every Leaf that reads it
composes the layer itself (`layer.selected_layer`). Changing the selection, or
taking the page to this Leaf's page protocol, refreshes an active revision from
valid source before returning, so deliveries use the new vocabulary without needing
a browser or state read first. Invalid source keeps its last good revision and
reports its check errors. A page with no active revision stays unactivated.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from .event_log import start_log
from .findings import Finding, note
from .harness import Harness, session_harness
from .hosting import restarting_server
from .layer import (
    checked_layer_inputs,
    input_paths,
    layer_inputs,
    selected_layer,
)
from .leases import lock_is_held, page_locked
from .locations import first_overlap, located, path_is_within
from .refusals import Refused
from .registry.kernel import kernel_protocol
from .registry.storage import LAYER, layer_record
from .schema import (
    LAYER_FILE,
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
        _refuse_package_target(
            page_dir,
            layer_inputs(
                with_theme(selected or (), selected_theme(page_dir, theme, fresh=True))
            ),
        )
        page_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if (page_dir / EVENTS_FILE).is_file():
        if dry_run:
            with page_locked(page_dir):
                plan = _plan_page(page_dir, selected, theme=theme, fresh=False)
            return {"page": str(page_dir), "changed": plan.changed}
        unready = _unready(
            page_dir, _revendor(page_dir, selected, session_harness(), theme=theme)
        )
        if unready:
            note(unready)
        return {"page": str(page_dir)}
    if dry_run:
        raise Refused(f"{page_dir} is not initialized")
    with restarting_server(page_dir, session_harness()), page_locked(page_dir):
        try:
            _init_page(page_dir, selected, theme=theme)
        except BaseException:
            if made and not any(page_dir.iterdir()):
                page_dir.rmdir()
            raise
    return {"page": str(page_dir)}


def renew_layer(page_dir: Path, harness: Harness | None) -> Finding | None:
    """Re-vendor a page vendored at an older page protocol, which this Leaf cannot
    serve (`event_contracts.write_refusal`), for the session `harness` names, and say
    what still holds the page back, for its agent to act on.

    A plugin update that bumps the page protocol reaches a running session, and its
    Leaf then refuses every page the session holds until the agent runs the
    `leaf page init` the refusal names. That re-vendor keeps the page's log, and so
    its threads and decisions, and its source, so it asks nothing of the agent's
    judgment, and the first Leaf to act for the page's session makes it instead: a
    write command naming the page (`cli.page_argument`) or a prompt or Stop hook
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
    *,
    theme: ThemeChoice = None,
) -> list[Finding]:
    """Re-vendor an initialized page inside a restart of its service, returning the
    errors that keep its index.html from activating under the new layer. Everything
    that can refuse is decided first, with the page still served, and an unchanged
    contract restarts nothing (`cmd_init`). `still` says, under each lock, whether
    the re-vendor is still wanted."""
    with page_locked(page_dir):
        if not still():
            return []
        plan = _plan_page(page_dir, selected, theme=theme, fresh=False)
    if not plan.changed:
        return []
    with restarting_server(page_dir, harness), page_locked(page_dir):
        return _init_page(page_dir, selected, still, theme=theme)


def _unready(page_dir: Path, errors: list[Finding]) -> Finding | None:
    """What a re-vendor that left `errors` tells the agent, or None for none."""
    if not errors:
        return None
    return Finding(
        "unready-revendor",
        values={"page": str(page_dir), "errors": [str(error) for error in errors]},
    )


def start_throwaway_page(page_dir: Path, packages: tuple[str, ...]) -> None:
    """Start a page in an empty directory selecting `packages`, for a reading Leaf
    takes and then deletes, as `package check --render` does with a package's
    worked examples."""
    _write_record(page_dir, _record(packages, None, None))
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
            f"a server started on {page_dir} while it was being re-vendored; "
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
        _write_record(page_dir, plan.record)
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
        _write_record(page_dir, plan.record)
        checked = check_source(page_dir, page.events)
        if checked.revision.active:
            activate_checked_source(page, checked)
        return checked.errors


class _PagePlan(NamedTuple):
    """An admitted init, decided before anything is written: the record it writes,
    and whether that differs from the page's."""

    record: dict
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
    if selected is None:
        selected = tuple(previous["packages"]) if previous else ()
    captured_theme = selected_theme(page_dir, theme, fresh=fresh)
    inputs = layer_inputs(with_theme(selected, captured_theme))
    _refuse_package_target(page_dir, inputs)
    roots = checked_layer_inputs(inputs)
    _refuse_input_destination_overlap(roots, page_dir.resolve())
    selected_layer(selected, captured_theme["name"] if captured_theme else None)
    record = _record(selected, captured_theme, previous)
    return _PagePlan(record, record != previous)


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


def _write_record(page_dir: Path, record: dict) -> None:
    LAYER.write(page_dir / LAYER_FILE, record)


def _refuse_input_destination_overlap(roots: list[Path], page_target: Path) -> None:
    destinations = [
        *(page_target / name for name in PAGE_OWNED_FILES),
        *(page_target / sub for sub in PAGE_OWNED_DIRS),
    ]
    if overlap := first_overlap(located(input_paths(roots)), located(destinations)):
        package, destination = overlap
        raise Refused(
            f"package {package} overlaps page destination "
            f"{destination}; package and page paths must be separate"
        )
