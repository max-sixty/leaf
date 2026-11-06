"""Time the server's paths on the pages `leaf-dev bench` generates, in this process.

`build` makes one collection's page (`bench.COLLECTIONS`) at each size in a scratch
directory, with its versions activated in turn and then its log, and `measure` reads
the CPU each of the server's `PATHS` takes on each page, least of `RUNS`:

- `state`: the served state a page server answers each read with
  (`PageStateService.page_state`), read after an append has changed the log, or
  with nothing changed on a page with no log;
- `append`: admitting one more event like the log's last, where it has one, in the
  transaction every writer takes (`event_contracts.append_admitted`);
- `delivery`: what `leaf wait` hands the agent of everything no receipt has passed,
  captured, frozen and read (`delivery.batch_data`);
- `agent`: `leaf page state` for the page;
- `thread`: `leaf page state` for the log's first thread, where it has one;
- `activate`: making a changed source the next revision (`activate_source`).

It runs this checkout's `leaf`, with `XDG_STATE_HOME` in the scratch directory for
the duration (`scratch_state`). A page server keeps a page's readings between
requests (`page_memory`), and so does this process, so each path is timed as a
server takes it again, with the readings of what didn't change kept. A `leaf`
command starts with none kept, so `agent`, `thread` and a hook's `delivery` cost a
command more than these, by the page's parse and the imports.

A log is written as admission writes it. Admitting each of thousands of events
through `append_admitted` costs a fold of the log apiece, which is the cost the
`events` collection measures, so it would cost the square of the log to build one.
`write_log` admits the first event of each shape through the door and writes every
other as a copy of what admission made of it, renamed, since admission derives the
same fields for events that differ only in the ids and numbers they name. It admits
the last of each shape through the door too, and fails where the copy would differ.
"""

import cProfile
import gc
import json
import os
import re
import shutil
import time
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from pathlib import Path

from leaf_dev.commands.bench import (
    BUDGET_MS,
    REFERENCE,
    Collection,
    interleaved,
    lowest,
)

PATHS = ("state", "append", "delivery", "agent", "thread", "activate")
# A click's paths: admitting its event and computing the reading the server answers
# with. Root `AGENTS.md`, "Responsiveness", puts that reading on screen within
# `BUDGET_MS`, so the two together take no more at `REFERENCE` (`over_budget`); it
# holds the agent's paths only to growing no faster than the page. Admission reads
# the page as a reading does, so on the `events` page both may grow with the log.
CLICK = ("append", "state")
RUNS = 3
# How many of the largest sizes an exponent is fitted over: 256 to 1,600, a ratio of
# 6.25. Over three, a ratio of 3.1, a host at load 50 fitted linear costs past 1.5.
FITTED = 4


def floors(rows: list[dict]) -> dict[str, float]:
    """Each path's noise floor (`bench.exponent`) in `rows`, one run's readings by
    size from BASE: the path's own reading on the BASE page, a reading of the same run,
    as the browser's floors are shares of its load (`bench.floor`). A path's own
    fixed cost sets the floor, so a cheap path's growth isn't judged against a dearer
    one's fixed work."""
    return {path: rows[0][path] for path in PATHS if path in rows[0]}


@contextmanager
def scratch_state(directory: Path) -> Generator[None]:
    """Point Leaf's state home into `directory` while the pages are built and read,
    so claims, deliveries and presence stay out of the machine's own."""
    directory.mkdir(parents=True, exist_ok=True)
    was = os.environ.get("XDG_STATE_HOME")
    os.environ["XDG_STATE_HOME"] = str(directory)
    try:
        yield
    finally:
        if was is None:
            del os.environ["XDG_STATE_HOME"]
        else:
            os.environ["XDG_STATE_HOME"] = was


def build(collection: Collection, sizes: list[int], directory: Path) -> dict[int, Path]:
    """Make `collection`'s page at each of `sizes` under `directory`: each version
    activated in turn, then the log. Where a page's versions begin with a smaller
    page's, they are activated once, on a page each size copies before its log is
    written, so the pages of every size together activate each version once."""
    from leaf.revisioning import activate_source
    from leaf.vendoring import cmd_init

    pages = {}
    versions, built = directory, []
    for n in sorted(sizes):
        sources = collection.sources(n)
        if not built or sources[: len(built)] != built:
            versions, built = directory / f"{n}-versions", []
            versions.mkdir(parents=True)
        for source in sources[len(built) :]:
            (versions / "index.html").write_text(source)
            if not built:
                cmd_init(versions)
            activation = activate_source(versions)
            assert activation.error is None, activation.error
            built.append(source)
        pages[n] = shutil.copytree(versions, directory / str(n), symlinks=True)
        write_log(pages[n], collection.log(n))
    return pages


def write_log(page: Path, commands: list[dict]) -> None:
    """Append `commands` to `page`'s log as admission records them: the first and
    last of each `shape` through `append_admitted`, the rest `renamed` from the
    first. A copy renames only the ids and words its command names, so a field
    admission derives from the document, such as the authored cards a move lies
    among, has to be the same for every command of a shape. The last one is
    checked against its copy, and a collection that breaks this fails here."""
    from leaf.event_contracts import append_admitted
    from leaf.event_log import jsonl_line, new_event_id, read_events
    from leaf.service import PageTransaction

    admitted: dict[str, tuple[dict, dict]] = {}
    last = {shape(command): index for index, command in enumerate(commands)}
    events = read_events(page)
    copies: list[str] = []

    def flush() -> None:
        with (page / "events.jsonl").open("a", encoding="utf-8") as log:
            log.writelines(copies)
        copies.clear()

    def admit(command: dict) -> dict:
        flush()
        with PageTransaction(page) as transaction:
            record, _ = append_admitted(transaction, command)
        events.append(record)
        return record

    for index, command in enumerate(commands):
        key = shape(command)
        if key not in admitted:
            admitted[key] = (command, admit(command))
            continue
        template, record = admitted[key]
        copy = renamed(record, names(template, command))
        copy.pop("seq")
        if index == last[key]:
            made = admit(command)
            if _unstamped(made) != _unstamped(copy):
                raise ValueError(
                    f"admission made {made} of {command}, and its copy {copy}"
                )
            continue
        copy["id"] = command.get("id") or new_event_id(events)
        events.append(copy)
        copies.append(jsonl_line(copy) + "\n")
    flush()


def _unstamped(record: dict) -> dict:
    """`record` without what the append lease stamps on it."""
    return {
        key: value for key, value in record.items() if key not in ("id", "ts", "seq")
    }


def shape(command: dict) -> str:
    """What `command` is with its ids and numbers left out."""
    return json.dumps(_numbers_out(command), sort_keys=True)


def _numbers_out(value):
    if isinstance(value, dict):
        return {key: _numbers_out(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_numbers_out(item) for item in value]
    return re.sub(r"\d+", "#", value) if isinstance(value, str) else value


def _strings(value, path: tuple = ()) -> Iterator[tuple[tuple, str]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, (*path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, (*path, index))
    elif isinstance(value, str):
        yield path, value


def names(template: dict, command: dict) -> dict[str, str]:
    """Each string `template` holds and what `command`, of the same shape, holds in
    its place."""
    theirs = dict(_strings(command))
    renames: dict[str, str] = {}
    for path, string in _strings(template):
        if renames.setdefault(string, theirs[path]) != theirs[path]:
            raise ValueError(f"{string!r} in {template} names two things in {command}")
    return renames


def renamed(value, renames: dict[str, str]):
    if isinstance(value, dict):
        return {key: renamed(item, renames) for key, item in value.items()}
    if isinstance(value, list):
        return [renamed(item, renames) for item in value]
    return renames.get(value, value) if isinstance(value, str) else value


def cpu_ms(run: Callable[[], object]) -> float:
    """The CPU `run` takes, in ms, with the collector run before it and held off
    during it, as `timeit` holds it: a collection costs what every page this
    process has read holds, not what the call does."""
    gc.collect()
    gc.disable()
    try:
        started = time.process_time()
        run()
        return (time.process_time() - started) * 1000
    finally:
        gc.enable()


def server_paths(page: Path, events: list[dict]) -> dict[str, Callable[[], object]]:
    """Each of `PATHS` on `page`, whose log `events` built, as a call; `append` only
    where the log holds an event to send again, and `thread` only where it opens one."""
    from leaf.agent_state import cmd_page_state
    from leaf.delivery import batch_data, deliverable, delivery_reading, freeze_delivery
    from leaf.event_contracts import append_admitted
    from leaf.revisioning import activate_source
    from leaf.served_state.service import PageStateService
    from leaf.service import PageTransaction

    source = page / "index.html"
    authored = source.read_text()
    saves = iter(range(1, 1_000_000))

    def delivery():
        with PageTransaction(page) as transaction:
            if batch := deliverable(transaction):
                delivery_reading(
                    freeze_delivery([batch_data(page, transaction, batch)])
                )

    def activate():
        source.write_text(authored.replace("</h1>", f", saved {next(saves)}</h1>", 1))
        activation = activate_source(page)
        assert activation.error is None, activation.error

    calls = {
        "state": lambda: PageStateService(page).page_state(),
        "delivery": delivery,
        "agent": lambda: cmd_page_state(page),
        "activate": activate,
    }
    if events:
        # The event is sent again without the id its writer gave it, so admission
        # gives each time its own.
        again = {key: value for key, value in events[-1].items() if key != "id"}

        def append():
            with PageTransaction(page) as transaction:
                append_admitted(transaction, again)

        calls["append"] = append
    if thread := next((e["id"] for e in events if e["kind"] == "comment"), None):
        calls["thread"] = lambda: cmd_page_state(page, thread)
    return calls


def function_times(call: Callable[[], object]) -> dict[str, float]:
    """Inclusive ms per function of one profiled `call`."""
    profile = cProfile.Profile()
    profile.runcall(call)
    return {
        entry.code
        if isinstance(entry.code, str)
        else f"{entry.code.co_name} ({Path(entry.code.co_filename).name}:"
        f"{entry.code.co_firstlineno})": entry.totaltime * 1000
        for entry in profile.getstats()
    }


def measure(
    collection: Collection,
    sizes: list[int],
    directory: Path,
    profile: bool = False,
    rounds: int = RUNS,
) -> tuple[list[dict], dict[str, tuple[dict, dict]]]:
    """Each path's least CPU over `rounds` on `collection`'s page at each of `sizes`,
    built under `directory`, in ms, beside the events its log holds; with
    `profile`, the function times of one more run of each path on the smallest
    page and the largest, in the order the rounds take them.

    The rounds are interleaved (`bench.interleaved`, `bench.lowest`). In each a page
    appends first, as a click does before its reading, and its versions come after
    every round, since a new one leaves the appended events on an earlier
    revision."""
    from leaf.event_log import read_events

    with scratch_state(directory / "state"):
        pages = build(collection, sizes, directory)
        held = {n: len(read_events(pages[n])) for n in sizes}
        calls = {n: server_paths(pages[n], collection.log(n)) for n in sizes}
        order = (("append", "state", "delivery", "agent", "thread"), ("activate",))

        def timed(paths: tuple[str, ...], n: int) -> dict[str, float]:
            return {path: cpu_ms(calls[n][path]) for path in paths if path in calls[n]}

        appended, activated = (
            lowest((n, timed(paths, n)) for _, n in interleaved(rounds, sizes))
            for paths in order
        )
        profiled: dict[str, list[dict]] = {}
        if profile:
            for n in (sizes[0], sizes[-1]):
                for paths in order:
                    for path in paths:
                        if path in calls[n]:
                            profiled.setdefault(path, []).append(
                                function_times(calls[n][path])
                            )
        rows = []
        for n in sizes:
            readings = {**appended[n], **activated[n]}
            rows.append(
                {
                    "n": n,
                    "events": held[n],
                    **{path: readings[path] for path in PATHS if path in readings},
                }
            )
    return rows, {path: (before, after) for path, (before, after) in profiled.items()}


def over_budget(rows: list[dict]) -> str | None:
    """Why a click's paths together take more than `BUDGET_MS` at `REFERENCE` in
    `rows`, or None: on a page with no log, or where `rows` has no `REFERENCE`, there
    is no click to time."""
    at = next((row for row in rows if row["n"] == REFERENCE), None)
    if at is None or not all(path in at for path in CLICK):
        return None
    click = sum(at[path] for path in CLICK)
    if click <= BUDGET_MS:
        return None
    return (
        f"{' + '.join(CLICK)} take {click:.0f} ms at {REFERENCE}, over {BUDGET_MS} ms"
    )
