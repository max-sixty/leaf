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
reports its check errors. A page with no active revision stays unactivated. A server
another installed copy of Leaf started hands its page to this one (`follow_copy`),
which renews the page's layer where it needs that and restarts the server under
this Leaf.

A page's look is one of the packages it lists, Leaf's own `reading` among them: Leaf
composes the mandatory layer and then the listed packages in order
(`layer.layer_inputs`), and adds none of its own. The user chose this over a theme
selected apart from the packages, and over composing `reading` under every page. One
list keeps a look an ordinary package, which a page builds on by listing it first and
replaces by leaving it out; a look Leaf added would be one each such page had to
decline. A page that lists no look draws in the browser's defaults, so the shipped
instructions tell an author to list one (`skills/leaf/SKILL.md`, "Author the page"),
and `page init` returns the selection it recorded.
"""

from __future__ import annotations

import os
import re
import secrets
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from leaf.base.findings import Finding, note
from leaf.base.harness import Harness, claim_harness, session_harness
from leaf.base.leases import lock_is_held, page_locked
from leaf.base.locations import first_overlap, located, path_is_within, paths_same
from leaf.base.refusals import Refused
from leaf.base.schema import (
    HTML_NAME,
    INIT_LOCK,
    PACKAGES_DIR,
    PAGE_OWNED_DIRS,
    PAGE_OWNED_FILES,
    SERVER_LOCK,
)
from leaf.base.server import running_server
from leaf.base.service import (
    claim_is_active,
    claim_path,
    held_elsewhere,
    page_claim,
    refuse_held,
)
from leaf.base.state import flocked, hooks_run_here, remove_claim
from leaf.log.event_log import initialized, start_log
from leaf.pages.hosting import check_servable, restarting_server
from leaf.records.transaction import PageTransaction
from leaf.source.layer import (
    checked_layer_inputs,
    compose_layer,
    input_paths,
    layer_inputs,
    named_package,
    package_files,
)
from leaf.source.registry.storage import (
    IncompatibleLayer,
    layer_packages,
    layer_record,
    write_layer,
)


def cmd_init(
    page_dir: Path,
    selected: tuple[str, ...] | None = None,
    *,
    dry_run: bool = False,
) -> dict:
    """Create a page, or rewrite an existing one's layer record inside a restart of
    its service. The result names the page and the packages its record now selects,
    so whoever chose them reads the whole selection back, as after an init that
    replaced it.

    Everything that can refuse the rewrite is decided first, in a dry run with the
    page still served, so a refused one leaves its server untouched: a restart
    would bring this Leaf's server back over a record it may not serve. A page a
    live session holds is rewritten only for that session (`service.refuse_held`).
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
        _refuse_package_target(page_dir, layer_inputs(selected or ()))
        page_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    harness = session_harness()
    if initialized(page_dir):
        refuse_held(page_dir, harness)
        if dry_run:
            with page_locked(page_dir):
                plan = _plan_page(page_dir, selected, fresh=False)
            return {"page": str(page_dir), "changed": plan.changed}
        errors, advice = _reinit(page_dir, selected, harness)
        if unready := _unready(page_dir, errors):
            note(unready)
    else:
        if dry_run:
            raise Refused(f"{page_dir} is not initialized")
        with restarting_server(page_dir, harness), page_locked(page_dir):
            try:
                _, advice = _init_page(page_dir, selected)
            except BaseException:
                if made and not any(page_dir.iterdir()):
                    page_dir.rmdir()
                raise
    # What the selected packages advise their authors, who chose them here.
    note(*advice)
    return {"page": str(page_dir), "packages": layer_packages(page_dir)}


def renew_layer(
    page_dir: Path, harness: Harness | None, still: Callable[[], bool] = lambda: True
) -> Finding | None:
    """Take a page at an older page protocol, which this Leaf cannot serve
    (`event_contracts.write_refusal`), to this Leaf's, for the session `harness`
    names, and say what still holds the page back, for its agent to act on.

    A plugin update that bumps the page protocol reaches a session once its hooks
    run the update (`session-lifetime.md`, "Which Leaf runs a session"), and its
    Leaf then refuses every page the session holds until the agent runs the
    `leaf page init` the refusal names. That init keeps the page's log, and so
    its threads and decisions, its source and its selection, so it asks nothing of
    the agent's judgment, and the first Leaf to act for the page's session makes it
    instead: a write command naming the page (`cli.resolve_dir`), the prompt hook
    serving the page again (`reconnect`), a hook that reads the session's pages
    (`renew_held`), or the restart of a page server that follows the session's copy
    (`follow_copy`). A command that only reads the page leaves it as it is.
    Only the session holding the page renews it, or any caller while no live
    session does: another session may still run the
    Leaf that initialized the page, which renewing would lock out of it, and its own
    first hook under this Leaf renews it. Nor does it renew a page a newer Leaf
    initialized, which `_plan_page` refuses. `still` says whether the caller still
    wants the renewal, asked wherever the renewal reads the page again (`_reinit`).

    What it finds is why the renewal was refused, or the `page check` errors that
    keep index.html from activating under the new layer, since a source an older
    Leaf accepted may fail this one's checks. None where the page needed no
    renewal or took one cleanly. Each of these readings is taken again under the
    page lock and transaction the renewal holds, since another Leaf, newer or
    older, may re-initialize the page or another session take it in between."""

    def renewable() -> bool:
        from leaf.records.event_contracts import write_refusal

        refusal = write_refusal(page_dir)
        if refusal is None or refusal.code != "foreign-layer":
            return False
        return held_elsewhere(page_dir, harness) is None and still()

    if not renewable():
        return None
    try:
        errors, _ = _reinit(page_dir, None, harness, renewable)
    except Refused as error:
        return Finding(
            "renewal-refused", values={"page": str(page_dir), "error": str(error)}
        )
    return _unready(page_dir, errors)


def renew_held(
    page_dir: Path, session_id: str, still: Callable[[], bool] = lambda: True
) -> Finding | None:
    """`renew_layer` for a reader acting for `session_id`, the session holding the
    page: a hook that reads the session's pages (`hook_transport.read_plans`), as the
    prompt and Stop hooks do and a tool boundary does with something to carry or a
    status check due, and the restart of a page server that follows the session's
    Leaf (`follow_copy`). After an update in place that moves the page
    protocol, the restart's renewal comes before the session's next hook, so the
    successors of the session's watch and of Codex's adapter, which only read the
    page, deliver its input once the renewal lands.

    A page another session holds is left alone, and so is one whose session's hooks
    last ran another Leaf (`state.hooks_run_here`), as a server another harness's
    copy started can serve a page a session of another harness took since: renewed,
    the page would be one its session's hooks can no longer read."""
    held = page_claim(page_dir)
    if held is None or held["id"] != session_id or not hooks_run_here(session_id):
        return None
    return renew_layer(page_dir, claim_harness(held), still)


def follow_copy(page_dir: Path, server_id: str) -> None:
    """`server _follow`: restart at its address, under this Leaf, the server
    `server_id` names, which another installed copy started and which asked
    (`server_lifetime.stop_when_service_ends`): the copy this Leaf replaced at the
    same path, or one the session holding the page ran before its hooks ran this
    Leaf.

    A page at an older page protocol, as an update can leave it, is renewed first,
    for the live session holding the page (`renew_held`) or while none does
    (`renew_layer`), and what holds the renewal back is queued for that session's
    next step (`clerk.queue`). After an update in place, no hook runs before this
    renewal, so the successors of the session's watch and of Codex's adapter read the
    page once it lands. The renewal restarts the server itself, and takes turns with a
    hook's renewal of the same page (`_reinit`). It renews only while no server but
    the one that asked serves the page, asked with each of the renewal's readings
    under its locks, since its restart would stop a server another start put in place
    of the one that asked.

    Otherwise the restart (`hosting.restarting_server`) follows, for the session
    holding the page, unless the page changed since the server asked: a page this
    Leaf still can't serve, as one whose renewal was refused, stays with the server
    serving it (`hosting.check_servable`); a server another start put in place, such
    as a checkout's or a renewal's, keeps running; and a session service whose
    session has ended retires after its grace, as it would have on the old copy.
    These checks come last, so that little time passes between them and the stop."""

    def no_other_server() -> bool:
        # The renewal's own restart stops the server that asked before its last
        # reading, so a page no server serves still counts as that server's.
        running = running_server(page_dir)
        return running is None or running["server_id"] == server_id

    held = page_claim(page_dir)
    if held is None or not claim_is_active(held):
        renew_layer(page_dir, None, no_other_server)
    elif unready := renew_held(page_dir, held["id"], no_other_server):
        from leaf.agents.clerk import queue

        queue(held["id"], [str(unready)], wake=True)
    check_servable(page_dir)
    running = running_server(page_dir)
    held = page_claim(page_dir)
    live = claim_is_active(held)
    if running is None or running["server_id"] != server_id:
        return
    if running["lifetime"] == "session" and not live:
        return
    with restarting_server(page_dir, claim_harness(held) if live else None):
        pass


def _reinit(
    page_dir: Path,
    selected: tuple[str, ...] | None,
    harness: Harness | None,
    still: Callable[[], bool] = lambda: True,
) -> tuple[list[Finding], tuple[Finding, ...]]:
    """Rewrite an initialized page's layer record inside a restart of its service,
    returning the errors that keep its index.html from activating under the new
    layer, and what its packages advise (`_PagePlan`). Everything that can refuse is
    decided first, with the page still served, and an unchanged record restarts
    nothing (`cmd_init`). `still` says, under each lock, whether the rewrite is still
    wanted.

    A rewrite holds the page's init lock from `still`'s second reading through the
    restart, so re-initializations of one page take turns: two renewals at once, as
    a hook reading the session's pages and the restart of a server that follows the
    session's copy can make, would each pass their first reading, since the page
    lock can't span the restart whose stop takes it, and the second would then find
    the old server still exiting from the first's stop, and be refused, or stop the
    server the first had just started. In turn, the second finds the page renewed
    and changes nothing. A re-initialization that changes nothing takes no lock and
    so writes nothing; the plan is taken again only under the transaction
    (`_init_page`)."""
    with page_locked(page_dir):
        if not still():
            return [], ()
        plan = _plan_page(page_dir, selected, fresh=False)
    if not plan.changed:
        return [], plan.advice
    with flocked(page_dir / INIT_LOCK):
        with page_locked(page_dir):
            if not still():
                return [], ()
        with restarting_server(page_dir, harness), page_locked(page_dir):
            return _init_page(page_dir, selected, still)


def _unready(page_dir: Path, errors: list[Finding]) -> Finding | None:
    """What a re-initialization that left `errors` tells the agent, or None for
    none."""
    if not errors:
        return None
    return Finding(
        "unready-reinit",
        values={"page": str(page_dir), "errors": [str(error) for error in errors]},
    )


def start_throwaway_page(page_dir: Path, package: Path) -> None:
    """Start a page in an empty directory selecting `package` as `page init` would, by
    the name it is installed or bundled under, or else by path, for a reading Leaf
    takes and then deletes, as `package check --render` does with a package's worked
    examples. The mandatory layer needs no selection, and the page selects nothing
    beside the package, so the reading is the same on every machine."""
    if any(paths_same(package, root) for root in layer_inputs()):
        selected = ()
    elif (named := named_package(package.name)) and paths_same(named, package):
        selected = (package.name,)
    else:
        selected = (f"./{os.path.relpath(package)}",)
    _init_page(page_dir, selected)


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
) -> tuple[list[Finding], tuple[Finding, ...]]:
    """Start or re-select the page under its lock and its service's restart, and
    return what keeps a re-selected index.html from activating, with what its
    packages advise (`_PagePlan`); a re-selection `still` no longer wants under the
    transaction commits nothing."""
    from leaf.records.authored_checks.source import check_source
    from leaf.records.revision_publication import activate_checked_source

    # The restart around this took the server down, but the page lock came after
    # it, and a start can land in between.
    if lock_is_held(page_dir / SERVER_LOCK):
        raise Refused(
            f"a server started on {page_dir} while it was being re-initialized; "
            f"re-run `leaf page init {page_dir}`"
        )
    # A directory the caller prepared is still a fresh page until it is
    # `initialized`: it keeps the caller's chosen mode, takes no PageTransaction
    # yet, and a failed validation leaves it untouched.
    if not initialized(page_dir):
        plan = _plan_page(page_dir, selected, fresh=True)
        # A page's claim lives outside its directory. Recreating a deleted path
        # creates a new page, so it must not inherit the deleted page's owner.
        remove_claim(claim_path(page_dir))
        _write_record(page_dir, plan)
        start_log(page_dir)
        return [], plan.advice
    # The page lock serializes this operation with other inits; an existing
    # page also has its ordinary transaction, which gives the record one order
    # against every browser append. No path takes the page transaction and then
    # the page lock, so this order cannot invert.
    with PageTransaction(page_dir) as page:
        if not still():
            return [], ()
        plan = _plan_page(page_dir, selected, fresh=False)
        if not plan.changed:
            return [], plan.advice
        _write_record(page_dir, plan)
        checked = check_source(page_dir, page.events)
        if checked.revision.active:
            activate_checked_source(page, checked)
        return checked.errors, plan.advice


class _PagePlan(NamedTuple):
    """An admitted init, decided before anything is written: the record it writes,
    the package directories it copies into the page, by the name of each copy,
    whether either differs from the page's, and what the selected packages advise
    their authors of their own declarations
    (`authored_checks.declarations.layer_advice`), which `page init` says beside the
    page."""

    record: dict
    copies: dict[str, Path]
    changed: bool
    advice: tuple[Finding, ...]


def _plan_page(
    page_dir: Path,
    selected: tuple[str, ...] | None,
    *,
    fresh: bool,
) -> _PagePlan:
    """Compose the selected layer, refusing a selection this Leaf cannot compose,
    before anything is written.

    A page a newer Leaf initialized, at a higher page protocol, is refused rather
    than taken back to this Leaf's: a process the session started before its plugin
    updated, or an agent following an older Leaf's advice, would otherwise take the
    page down, and the newer Leaf's next command or hook up again, reloading the
    user's tabs each time. A page an older Leaf initialized keeps its selection
    (`layer_packages`) under a new generation."""
    previous = None
    if not fresh:
        try:
            previous = layer_record(page_dir)
        except IncompatibleLayer as refused:
            if refused.findings[0].code == "newer-layer":
                raise
    # A selection the caller names resolves where they run; the page's own, against
    # the copies it holds.
    named = selected is not None
    if not named:
        selected = () if fresh else tuple(layer_packages(page_dir) or ())
    inputs = layer_inputs(selected, Path.cwd() if named else page_dir)
    _refuse_package_target(page_dir, inputs)
    roots = checked_layer_inputs(inputs)
    _refuse_input_destination_overlap(roots, page_dir.resolve())
    composition = compose_layer(roots)
    from leaf.records.authored_checks.declarations import layer_advice

    # Named by the packages the selection names, before any copy into the page.
    advice = tuple(layer_advice(roots, composition.vocabulary.registry))
    copies = _copies(selected) if named else {}
    record = _record(
        tuple(
            f"./{PACKAGES_DIR}/{copies[value].name}" if value in copies else value
            for value in selected
        ),
        previous,
    )
    copied = {root.name: root for root in copies.values()}
    if record == previous and any(
        package_files(root) != package_files(page_dir / PACKAGES_DIR / name)
        for name, root in copied.items()
    ):
        # A copy's new bytes change what an open document runs under.
        record = {**record, "generation": secrets.token_hex(16)}
    return _PagePlan(record, copied, record != previous, advice)


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


def _record(selected: tuple[str, ...], previous: dict | None) -> dict:
    """The layer record selecting `selected`, keeping `previous`'s generation where
    it selects the same: a generation names a change in what an open document runs
    under, not an invocation."""
    if previous is not None and previous["packages"] == list(selected):
        return previous
    return {"packages": list(selected), "generation": secrets.token_hex(16)}


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
        for path, data in package_files(root).items():
            (staged / path).parent.mkdir(parents=True, exist_ok=True)
            (staged / path).write_bytes(data)
        shutil.rmtree(target, ignore_errors=True)
        staged.rename(target)
    write_layer(page_dir, plan.record)


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
