"""The state home's one retirement rule, and the sweep that applies it.

Every record in the state home stands for something that lives somewhere else,
and leaf rarely sees that subject end. A page goes with the worktree or scratch
directory that held it (`wt remove`, a temp-directory cleanup); a process that
held a lease exits. No leaf process is there at either moment, so a record is
retired by the first sweep that finds its subject gone, whichever version wrote
it. A missing page or an unheld lock is the same fact to every reader.

There are two subjects:

- A page. A claim names it as `page`; an immutable delivery, and a Codex task's
  delivery record, live or archived under `history/`, name each batch's
  `page`. The record goes once every page it names is gone: nothing can act on
  it again, since answering a delivery or holding a claim needs the page. A
  record that names no page this version can read stays, since another version
  may be reading it (AGENTS.md, "The reader throws it away").
- A holder. A lock or lease file means something only while a process holds
  it, whether it guards a page transition (`page-locks/`), a wait or adapter
  lease, or a Codex task's start and records. Nobody holding it is its end:
  `leases.retire_lock` removes it under its own lock, and every taker re-checks
  the path after locking (`event_log.names_locked`), so the next one simply
  makes a new file. A wait's `.told` stands for the start token in the wait
  lease beside it, and goes with that lease's holder.

Page locks are why this has to be a sweep rather than a reading: they are keyed
on a digest of the page's path, and nothing ever enumerates them. They are also
most of what accumulated, because every page any command transitions mints one
(`leases.page_lock`), and site builds and previews make and discard pages by the
dozen.

What stays: `pages/`, whose entries are pages rather than records about them;
`packages/`; `access.json`; `deliveries.lock`, one file for the whole machine;
and every name this version does not write, which belongs to the version that
does.

The sweep runs at most once per `SWEEP_INTERVAL_S`, from the first `leaf`
command after that much time, so its cost is what that interval wrote."""

import time
from pathlib import Path

from leaf.files import read_json
from leaf.leases import lock_is_held, retire_lock, take_lease
from leaf.machine import state_home

SWEEP_INTERVAL_S = 3600

# The stamp whose mtime is the last sweep's start.
SWEPT = "swept"

# Lock and lease files, by where they sit in the state home.
LOCKS = (
    "page-locks/*.lock",
    "sessions/*.wait",
    "sessions/*.adapter",
    "sessions/*.start",
    "sessions/*.delivery.lock",
)


def retire_if_due() -> None:
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
    retire()


def retire() -> None:
    """Remove every record whose subject is gone (see the module docstring)."""
    home = state_home()
    for path in [*home.glob("claims/*.json"), *home.glob("deliveries/*.json")]:
        _retire_page_record(path)
    for records in home.glob("sessions/*.deliveries"):
        _retire_task_records(records)
    for pattern in LOCKS:
        for path in home.glob(pattern):
            retire_lock(path)
    for told in home.glob("sessions/*.told"):
        if not lock_is_held(told.with_suffix(".wait")):
            told.unlink(missing_ok=True)


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
