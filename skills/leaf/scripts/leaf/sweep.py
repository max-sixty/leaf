"""The state home's one retirement rule, and the sweep that applies it.

Every record in the state home stands for something that lives somewhere else,
and leaf rarely sees that subject end. A page goes with the worktree or scratch
directory that held it (`wt remove`, a temp-directory cleanup), and no leaf
process is there at the moment. So a record is retired by the first sweep that
finds its subject gone, whichever version wrote it: a missing page is the same
fact to every reader.

The subject is a page. A claim names it as `page`; an immutable delivery, and a
Codex task's delivery record, live or archived under `history/`, name each
batch's `page`; a page lock holds the path it guards (`leases.page_lock`). A
record goes once every page it names is gone, since nothing can act on it again:
answering a delivery or holding a claim needs the page. A record that names no
page this version can read stays, since another version may be reading it
(AGENTS.md, "The reader throws it away").

A page lock also has to be unheld, and it is removed under its own lock
(`leases.retire_lock`), so a taker of this version that opened it meanwhile
takes the lock again on a new file (`event_log.names_locked`). A leaf too old to
re-check could end up holding the removed file beside another process's new
one; with the page gone, the only command that opens its lock is one making the
page again, so that takes two of them making the same page at the instant of the
removal. The same argument is why nothing keyed on a session is retired here: a
session's leases and records name no page, and a session that ended can be
resumed.

Page locks are why this is a sweep rather than a reading: they are keyed on a
digest of the path, and nothing ever enumerates them. They are also most of what
accumulated, since every page path any command transitions mints one, and site
builds and previews make and discard pages by the dozen. A lock an older leaf
minted holds no path, so it stays.

What stays: `pages/`, whose entries are pages rather than records about them;
`packages/`; `access.json`; `deliveries.lock`; `sessions/` but for Codex task
records; and every name this version does not write, which belongs to the
version that does.

The sweep runs at most once per `SWEEP_INTERVAL_S`, from the first `leaf`
command after that much time, so its cost is what that interval wrote."""

import time
from pathlib import Path

from leaf.files import read_json
from leaf.leases import retire_lock, take_lease
from leaf.machine import state_home

SWEEP_INTERVAL_S = 3600

# The stamp whose mtime is the last sweep's start.
SWEPT = "swept"


def sweep_if_due() -> None:
    """Sweep the state home if the last sweep started `SWEEP_INTERVAL_S` ago.

    The stamp is touched before the sweep, so a second process arriving during
    it finds the sweep done rather than running another."""
    stamp = state_home() / SWEPT
    try:
        if time.time() - stamp.stat().st_mtime < SWEEP_INTERVAL_S:
            return
    except FileNotFoundError:
        pass
    stamp.touch()
    sweep()


def sweep() -> None:
    """Remove every record whose pages are gone (see the module docstring)."""
    home = state_home()
    for path in [*home.glob("claims/*.json"), *home.glob("deliveries/*.json")]:
        _retire_page_record(path)
    for records in home.glob("sessions/*.deliveries"):
        _retire_task_records(records)
    for lock in home.glob("page-locks/*.lock"):
        try:
            page = lock.read_text(encoding="utf-8")
        except (FileNotFoundError, UnicodeDecodeError):
            continue
        if page and not Path(page).is_dir():
            retire_lock(lock)


def _named_pages(record) -> list[Path] | None:
    """The pages a record stands for: a claim's `page`, or each batch's `page` in
    a delivery or a Codex delivery record. None for a record that names none in
    a shape this version reads."""
    if not isinstance(record, dict):
        return None
    if isinstance(record.get("page"), str):
        return [Path(record["page"])]
    batches = record.get("batches")
    if not isinstance(batches, list) or not batches:
        return None
    pages = [
        batch.get("page") if isinstance(batch, dict) else None for batch in batches
    ]
    return (
        [Path(page) for page in pages]
        if all(isinstance(page, str) for page in pages)
        else None
    )


def _retire_page_record(path: Path) -> None:
    """Remove this record if every page it names is gone.

    A successor written at the same name between this reading and the unlink is
    lost with it. For a claim that takes a `page init` recreating the page and a
    claim on it landing inside that window; a delivery or a task record is never
    rewritten for a page that is gone."""
    try:
        record = read_json(path)
    except ValueError:  # not a record this version reads; its writer's to judge
        return
    pages = _named_pages(record)
    if pages and not any(page.is_dir() for page in pages):
        path.unlink(missing_ok=True)


def _retire_task_records(records: Path) -> None:
    """Retire one Codex task's delivery records, live and archived, whose pages
    are gone, and the directories that leaves empty.

    Its writers make the directories and move records into `history/` holding
    the task's delivery lock (`codex.records_lock`), so this holds it too,
    and passes the task by while one of them does."""
    # Imported here: every command imports this module, and only a sweep needs codex.
    from leaf.codex import records_lock

    held = take_lease(records_lock(records))
    if held is None:
        return
    with held:
        for path in [*records.glob("*.json"), *records.glob("history/*.json")]:
            _retire_page_record(path)
        for directory in (records / "history", records):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
