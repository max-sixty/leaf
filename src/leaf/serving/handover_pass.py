"""The render check a page's server runs on what the agent hands over, and the reading
each render check leaves behind.

`page check --render` blocks the agent for the whole browser pass, so an agent making a
quick edit can hand the page over without it. So the server reads the version itself,
and the agent hears what it found at its next delivery.

**What starts a reading.** A live claimant has handed the page over, no file its version
is built from has been written for `QUIET_S` (`version_written`), and its live version
is not the one the latest reading read. A handover is the turn's end, as the activity
fold reads it (`presence.claimant_reading`), or the agent declaring the page open for
feedback (`leaf page open`) after its last save, whichever its harness records first: a
turn record can close only as the session ends, if at all. The declaration keeps its time to
the millisecond, so one made in the millisecond of the save counts as after it. Saves
inside a turn coalesce into the one reading at its handover, and `QUIET_S` coalesces
saves that keep landing after it, such as a build the agent left running. The server
makes a save live only once a reading is due, so on a page with no tab open the saves
inside a turn make no revisions. A page nobody holds, or its agent has closed, has
nobody to tell. The reading outlives the server, so a page served again reads only a
version no reading has read: an older page, its first time served by this Leaf, is read
once. A reading runs in a process of its own at low priority, away from the server that
answers the user's gestures, and a server waits for its reading before it looks again.
Readings of different pages run side by side, with no lock across the state home to run
one at a time: on a real page such a lock rarely holds anything back, and a reading that
never ends would stop every page's. A server started again while its predecessor's
reading still runs may read that version a second time. The first of the two to tell,
inside the page's transaction, tells the version, and the other tells nothing and leaves
its reading. A reading that runs past `DEADLINE_S` is ended by its own alarm. Only a
page whose own script never stops gets there, so its server tells the agent, as a
failure, that the version couldn't be read, and keeps that as the version's reading, so
the page costs the deadline once. Until the alarm, its server reads no later version of
the page. A handover right after the last save waits 10 to 15 s for the version to stand
and the next look, then for the reading.

**What it costs.** A reading costs a little less than `page check --render`, which also
saves the screens, and more on larger pages; on a page that fails plain check it stops
at the markup check, as the check does. Under load a reading takes as long at this
niceness as at 0. A look that finds nothing new,
every `LOOK_S`, costs about 0.16 ms of CPU. A session saving 100 times in one turn pays
one reading.

**What it tells.** The findings the page's latest reading didn't hold, as a `render`
event (`events.md`) whose handling clause tells failures from advice. A reading is kept
only once the agent has heard every finding in it: an agent's own `page check --render`
reports them all, and the server keeps its reading once it has told the agent what was
new in it. A reading whose version a save has replaced since the check froze the source
tells nothing and leaves the page's reading as it was, so the next reading tells its
findings. Under the `error` event's clause agents change the page for advice; this
clause keeps failures fixed and has agents mostly leave the advice. A failure wakes the
agent: failures are rare on real pages, and those found are real. Advice alone wakes
nobody and goes with the agent's next delivery (`delivery.deliverable`), since real
pages often hold only advice, and a wake for it would mostly spend a turn
deciding to leave the page alone. A finding keeps its place by the element it names
(`_place`), so an edit that moves a measurement doesn't tell it again and a fault fixed
and reintroduced is told again. A failure told once isn't told again while it stands, so
an agent that can't fix it isn't woken for each attempt, and a version the agent checked
itself is neither read twice nor told back to it.

A reading a browser couldn't finish (`findings.Finding.unread`) says nothing of the
page, so it leaves no reading. A reading refuses nothing: recording a layout fault
breaks no guarantee a stamp keeps, so `page stamp` takes a version whatever its
reading found.
"""

import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from leaf.agents.delivery import nudge_unwatched
from leaf.agents.presence import claimant_reading
from leaf.base.findings import Finding
from leaf.base.harness import detached_environment
from leaf.log.event_log import read_events
from leaf.log.interaction_log import append_interactions
from leaf.records.event_contracts import append_admitted
from leaf.records.render_reading import read_reading, write_reading
from leaf.records.revisioning import activate_source
from leaf.records.transaction import PageTransaction, requires_agent_attention
from leaf.source.page_inputs import source_readings
from leaf.source.revision_artifact import read_revision, version_written

# Set to `off` by a caller whose pages must hold only what it wrote: the suite.
VARIABLE = "LEAF_RENDER_PASS"
# How often a server looks. A look that finds nothing new compares the page's file
# stamps (`source_readings`).
LOOK_S = 5
# How long a version stands before anyone reads it.
QUIET_S = 10
# The whole reading, which only a page whose own script never stops should reach: 47
# times the 38 s of the slowest real reading, and 5 times the 384 s of the corpus, the
# heaviest page the suite renders. The reading's own alarm ends it, so a reading
# outlives its server by no more.
DEADLINE_S = 1800
# Lower than the user's and other sessions' work, without the throttling of a background
# QoS, which holds headless Chrome to about 10 fps and breaks a timed reading.
NICENESS = 10


def remember_reading(page_dir: Path, digest: str, data: str, checked) -> None:
    """Leave what `checked`, a `command.BrowserCheck`, read of the version `digest` with
    the data version `data` as the page's latest reading, where a browser finished it:
    the agent that ran the check read every finding. It writes inside the page's
    transaction, so a server's reading that `_tell` is weighing under it can't replace
    this one unseen."""
    if (found := _finished(checked)) is not None:
        with PageTransaction(page_dir):
            write_reading(page_dir, digest, data, *found)


def _finished(checked) -> tuple[list[dict], dict[str, dict]] | None:
    """Every finding of a browser that finished reading the page, as
    `findings.Finding.json` gives it, with what each visual drew
    (`RenderReading.visuals`, none where failing page code ended the check before the
    render gate), or None where it didn't."""
    findings = checked.findings()
    if any(f.unread for f in findings):
        return None
    visuals = checked.render.visuals if checked.render is not None else {}
    return [finding.json() for finding in findings], visuals


def _place(finding: dict) -> tuple[str, str]:
    """What makes two readings' findings one fault: its code and the element it names,
    whose measurements an edit may move. One that names none is placed by the message it
    carries (`values["text"]`), as two console errors differ only by theirs, and
    otherwise by its code alone, since its words carry measurements, such as how far
    the page scrolls sideways."""
    named = finding.get("at") or finding.get("values", {}).get("text", "")
    return finding["code"], named


def untold(before: dict | None, findings: list[dict]) -> list[dict]:
    """The `findings` the reading `before` didn't hold, as a `render` event carries
    them: their words, with no measurements behind them."""
    heard = {_place(finding) for finding in (before or {"findings": []})["findings"]}
    return [
        {key: value for key, value in finding.items() if key != "values"}
        for finding in findings
        if _place(finding) not in heard
    ]


def read_and_tell(page_dir: Path, check: Callable) -> None:
    """Read the page's live version, where no reading has read it, and tell its agent
    what it hasn't heard, in a `render` event on that version, unless a save has since
    moved the page past it: the next reading tells them. A diagnostic records what a
    reading cost. `check` is `validation.command.check_page`, which reads the page as
    `page check --render` does; its caller passes it in, since the check sits above
    the page's server that runs this pass."""
    if _unread(page_dir):
        _read_and_tell(page_dir, check)


def cmd_read(page_dir: Path, check: Callable) -> None:
    """`leaf page _read`, the process a server starts for each reading
    (`HandoverPass._read`): it reads at `NICENESS`, and its own alarm ends it at
    `DEADLINE_S`. Both settings last as long as the process, so only this process makes
    them: an alarm left armed in another caller of `read_and_tell` would end it
    `DEADLINE_S` later."""
    signal.alarm(DEADLINE_S)
    os.nice(NICENESS)
    read_and_tell(page_dir, check)


def _read_and_tell(page_dir: Path, check: Callable) -> None:
    started = time.monotonic()
    _, read = check(page_dir, render=True, screens=False)
    found = _finished(read[2]) if read is not None else None
    told = []
    if read is not None and found is not None:
        told = _tell(page_dir, read[0], read[1], *found)
    append_interactions(
        page_dir,
        [
            {
                "source": "cli",
                "type": "render_pass",
                "durationMs": round((time.monotonic() - started) * 1000),
                "findings": None if found is None else len(found[0]),
                "told": len(told),
            }
        ],
    )


def _tell(
    page_dir: Path,
    digest: str,
    data: str | None,
    found: list[dict],
    visuals: dict[str, dict],
) -> list[dict]:
    """Tell the agent the findings `found` of the version `digest`, read with the data
    version `data`, that the page's latest reading didn't hold, and leave them, with
    the `visuals` it read, as its reading, where that version is still live and no
    reading of it beside this one told first. The findings told."""
    with PageTransaction(page_dir) as page:
        live = _live(page_dir, page)
        before = read_reading(page_dir)
        # A reading of this version beside this one that told first, under this
        # transaction, has told it.
        if live is None or live[1] != digest or _has_read(before, digest):
            return []
        told = untold(before, found)
        if told:
            event, _ = append_admitted(
                page,
                {
                    "kind": "render",
                    "author": "page",
                    "revision": live[0],
                    "findings": told,
                },
            )
            if requires_agent_attention(event):
                nudge_unwatched(page)
        write_reading(page_dir, digest, data, found, visuals)
    return told


def _handed_over(present: dict, turn, saved: int) -> bool:
    """Whether the claimant has handed over the source it saved at `saved`, in
    nanoseconds: its turn has ended, or it declared the page open (`present`, its
    presence reading) in that save's millisecond or later, since the declaration keeps
    its time only to the millisecond."""
    declared = present["status"].get("ts")
    return not turn.running or (
        declared is not None
        and round(datetime.fromisoformat(declared).timestamp() * 1000)
        >= saved // 1_000_000
    )


def _has_read(reading: dict | None, digest: str) -> bool:
    """Whether the page's latest reading, `reading`, read the version `digest`."""
    return reading is not None and reading["digest"] == digest


def _live(page_dir: Path, transaction=None) -> tuple[int, str] | None:
    """The page's live version as of now, with its artifact digest, a save since a
    check froze the source included, made live as a tab would make it; None where the
    page has no valid version. `transaction` is the caller's `PageTransaction`, where it
    holds one."""
    revision = activate_source(page_dir, transaction=transaction).revision
    if revision is None:
        return None
    return revision, read_revision(page_dir, revision).digest


def _unread(page_dir: Path) -> str | None:
    """The digest of the page's live version, which this makes live where no tab has,
    where no reading has read it."""
    if (live := _live(page_dir)) is None:
        return None
    return None if _has_read(read_reading(page_dir), live[1]) else live[1]


class HandoverPass:
    """One page server's reading of what its claimant hands over. `settled` is the
    source reading (`source_readings`) it needs to ask nothing more about, so a page
    that hasn't moved costs a look its file stamps, as a neighbour's row does."""

    def __init__(self, page_dir: Path):
        self.page_dir = page_dir
        self.settled: str | None = None

    def run(self) -> None:
        """Look for this server's lifetime. A reading that fails is the page's loss of
        an early reading and not of its server, so a failure here ends only this."""
        if os.environ.get(VARIABLE) == "off":
            return
        try:
            while True:
                time.sleep(LOOK_S)
                self.look()
        except Exception as error:
            print(
                f"leaf server: {self.page_dir}: render pass stopped: {error}",
                file=sys.stderr,
                flush=True,
            )

    def look(self) -> None:
        """Start a reading if one is due ("What starts a reading"), and wait for it.
        The source's own time decides whether one is due, so nothing is made live
        before then."""
        page_dir = self.page_dir
        source = source_readings(page_dir)[0]
        if source == self.settled:
            return
        present, turn = claimant_reading(page_dir, read_events(page_dir))
        if present["session_alive"] and present["status"]["state"] != "idle":
            saved = version_written(page_dir)
            if (
                not _handed_over(present, turn, saved)
                or time.time() - saved / 1e9 < QUIET_S
            ):
                return
            if (digest := _unread(page_dir)) is not None:
                self._read(digest)
        self.settled = source

    def _read(self, digest: str) -> None:
        """Read the version `digest` in a child that speaks for no harness session, so
        the claimant's command diagnostics don't count its seconds as the agent's. A
        child ended by its alarm told nothing, so this tells the agent that the version
        couldn't be read."""
        ended = subprocess.run(
            [sys.executable, "-P", "-m", "leaf", "page", "_read", str(self.page_dir)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            env=detached_environment(None),
            check=False,
        ).returncode
        if ended == -signal.SIGALRM:
            overran = Finding("reading-overran", values={"seconds": DEADLINE_S})
            _tell(self.page_dir, digest, None, [overran.json()], {})
