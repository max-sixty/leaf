"""The render check a page's server runs on what the agent hands over, and the reading
each render check leaves behind.

`page check --render` blocks the agent for the whole browser pass, so an agent making a
quick edit hands the page over without it: 8 of 20 in the 2026-10-24 eval
(`notes/agent-usability-evals.md`), and 20 of the 21 agents that got its findings after
handover fixed the page in the same wake. So the server reads the version itself, and
the agent hears what it found at its next delivery.

**What starts a reading.** A live claimant has handed the page over, and its live
version has stood for `QUIET_S` and is not the version the latest reading read. A
handover is the turn's end, as the activity fold reads it (`presence.claimant_reading`),
or the agent declaring the page open for feedback (`leaf page open`) after its last
save, whichever its harness records first: on 2026-11-05, in 23 of 24 eval sessions the
turn record closed only as the session ended, if at all, and 20 of 21 handovers declared
the page open after the last save. Saves inside a turn coalesce into the one reading at
its handover, and `QUIET_S` coalesces saves that keep landing after it, such as a build
the agent left running. A page nobody holds, or its agent has closed, has nobody to
tell. The reading outlives the server, so a page served again reads only a version no
reading has read: an older page, its first time served by this Leaf, is read once. A
reading runs in a process of its own at low priority, away from the server that answers
the user's gestures, under a lease the whole state home shares, so the machine runs one
at a time and a page handed over meanwhile looks again until the lease is free. A
reading that runs past `DEADLINE_S` tells nobody anything and ends this server's pass,
so a page too heavy to read costs that once. Findings reach the agent about half a
minute after it hands over.

**What it costs**, measured 2026-11-05 on the shared 18-core Mac at load 19-28, on 13
real pages: a median 14 s and 16 CPU-seconds, and 30 s and 36 CPU-seconds on the largest
(216 KB). A reading leaves out the screens `page check --render` saves, which take the
check to 18 s and 20 CPU-seconds, and at this niceness it took as long as at 0 under
that load. A look that finds nothing new costs 0.16 ms of CPU. On the 8,346 revisions of
227 real pages over 49 days, a reading per revision would have run 174 in the busiest
hour, 0.75 of a core. A reading per turn runs 37 to 45 there, about 0.2 of a core, and
161 to 237 on the busiest day, about 0.2% of the machine's day. In 16 eval sessions, 46
revisions took 22 readings, a median 8 s each. A session saving 100 times in one turn
pays one reading, and the lease holds the machine to about one core however many turns
end at once.

**What it tells.** Findings the agent hasn't heard, which each reading records, as a
`render` event (`events.md`) whose handling clause tells failures from advice. A reading
whose version a save has since replaced tells nothing and leaves its findings unheard,
so the next reading tells them. Under the `error` event's clause agents changed the page
for advice every time; this clause kept every failure fixed and had Claude Code leave
the advice in 4 of 5. A failure wakes the agent. Of the versions users first reacted to
on 20 real pages, 2 held one, and both were real. Advice alone wakes nobody and goes
with the agent's next delivery (`delivery.deliverable`), since 11 of those 20 held only
advice, and a wake for it would mostly spend a turn deciding to leave the page alone. A
finding keeps its place by the element it names, so an edit that moves a measurement
doesn't tell it again and a fault fixed and reintroduced is told again. A failure told
once and left stands until its fix or the stamp's refusal, which also keeps an agent
that can't fix it from being woken for each attempt. An agent's own `page check
--render` leaves the reading too, so a version it checked itself is neither read twice
nor told back to it.

**What a reading refuses.** `page stamp` refuses a version the latest reading failed
(`stamp_refusal`), which a fresh `page check --render` replaces. A version no reading
has read yet stamps as before, since making every stamp wait on a browser costs a stamp
its 14 s, and three of four stamps come within 30 s of their revision. A reading a
browser couldn't finish (`UNFINISHED`) says nothing of the page, so it leaves no
reading.
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from leaf.event_log import read_events
from leaf.files import latest_revision, revision_path
from leaf.harness import detached_environment
from leaf.leases import release_lease, take_lease
from leaf.presence import claimant_reading
from leaf.revision_artifact import read_artifact
from leaf.revisioning import activate_source
from leaf.served_state.reading import source_readings
from leaf.service import PageTransaction, requires_agent_attention
from leaf.state import STRING, Record, described, object_schema, page_key, state_home

# Set to `off` by a caller whose pages must hold only what it wrote: the suite.
VARIABLE = "LEAF_RENDER_PASS"
# How often a server looks. A look that finds nothing new compares the page's file
# stamps (`source_readings`).
LOOK_S = 5
# How long a version stands before anyone reads it.
QUIET_S = 10
# The whole reading, far past the 33 s of the slowest real page sampled. The heaviest
# page the suite renders, the corpus, takes 384 s, so a server spends this on it once.
DEADLINE_S = 180
# Lower than the user's and other sessions' work, without the throttling of a background
# QoS, which holds headless Chrome to about 10 fps and breaks a timed reading.
NICENESS = 10
# The one reading the machine runs at a time, under its state home.
LEASE = "render-pass.lock"
# The findings of a browser that failed rather than of the page it was reading.
UNFINISHED = frozenset({"gate-failed", "probe-failed"})

READING = Record(
    "render-reading",
    described(
        "The latest render check of a page, by `page check --render` or its server "
        "(`render_gate.handover_pass`), in the state home's "
        "`render-readings/<page key>.json`. Disposable: without it, a version is read "
        "again.",
        object_schema(
            {
                "page": described("The page directory.", STRING),
                "digest": described("The artifact digest of the version read.", STRING),
                "findings": described(
                    "What it found (`findings.Finding.json`).",
                    {"type": "array", "items": {"type": "object"}},
                ),
                "known": described(
                    "Each finding the agent has heard, as `[code, place]` (`_place`): "
                    "all of them where the agent ran the check, and where the server "
                    "did, those it told and those the agent had already heard.",
                    {"type": "array", "items": {"type": "array"}},
                ),
            }
        ),
    ),
    since=42,
)


def _reading_path(page_dir: Path) -> Path:
    return state_home() / "render-readings" / f"{page_key(page_dir)}.json"


def read_reading(page_dir: Path) -> dict | None:
    return READING.read(_reading_path(page_dir))


def remember_reading(page_dir: Path, digest: str, checked) -> None:
    """Leave what `checked`, a `command.BrowserCheck`, read of the version `digest` as
    the page's latest reading, where a browser finished it, every finding known to the
    agent that read it."""
    findings = checked.findings()
    if checked.unavailable is not None or any(f.code in UNFINISHED for f in findings):
        return
    found = [finding.json() for finding in findings]
    _write(page_dir, digest, found, [list(_place(finding)) for finding in found])


def _write(page_dir: Path, digest: str, findings: list[dict], known: list) -> None:
    path = _reading_path(page_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    READING.write(
        path,
        {"page": str(page_dir), "digest": digest, "findings": findings, "known": known},
    )


def stamp_refusal(page_dir: Path, digest: str) -> str | None:
    """Why a stamp of the version `digest` is refused, or None: the latest reading
    read that version and failed it. What it names is the reading's own words, so a
    finding only a later Leaf knows still reads."""
    reading = read_reading(page_dir)
    if reading is None or reading["digest"] != digest:
        return None
    failed = [f["text"] for f in reading["findings"] if f["severity"] == "error"]
    if not failed:
        return None
    lines = "".join(f"\n  - {text}" for text in failed)
    return (
        "refusing to stamp index.html: the render check failed this version; fix "
        f"these and save, or run `leaf page check --render` to read it again:{lines}"
    )


def _place(finding: dict) -> tuple[str, str]:
    """What makes two readings' findings one fault: its code and the element it names,
    whose measurements an edit may move, or its words where it names none, as two
    console errors differ only by theirs."""
    return finding["code"], finding.get("at") or finding["text"]


def untold(before: dict | None, after: dict) -> list[dict]:
    """The findings of the reading `after` the agent hadn't heard by the reading
    `before`, as a `render` event carries them: their words, with no measurements
    behind them."""
    known = {tuple(place) for place in (before or {"known": []})["known"]}
    return [
        {key: value for key, value in finding.items() if key != "values"}
        for finding in after["findings"]
        if _place(finding) not in known
    ]


def read_and_tell(page_dir: Path) -> None:
    """Read the page's live version and tell its agent what it hasn't heard, in a
    `render` event on that version, unless a save has since moved the page past it: the
    next reading tells them. A diagnostic records what it cost."""
    from leaf.event_contracts import append_admitted
    from leaf.interaction_log import append_interactions
    from leaf.presence import nudge_unwatched
    from leaf.validation.command import cmd_check

    os.nice(NICENESS)
    started = time.monotonic()
    before = read_reading(page_dir)
    activate_source(page_dir)
    cmd_check(page_dir, render=True, screens=False)
    after = read_reading(page_dir)
    told = untold(before, after) if after is not None else []
    if told:
        assert after is not None
        with PageTransaction(page_dir) as page:
            revision = latest_revision(page_dir)
            if (
                revision is None
                or read_artifact(page_dir, revision).digest != after["digest"]
            ):
                # Nobody heard these, so the next reading tells them.
                heard = {tuple(place) for place in (before or {"known": []})["known"]}
                _write(
                    page_dir,
                    after["digest"],
                    after["findings"],
                    [p for p in after["known"] if tuple(p) in heard],
                )
                told = []
            else:
                event, _ = append_admitted(
                    page,
                    {
                        "kind": "render",
                        "author": "page",
                        "revision": revision,
                        "findings": told,
                    },
                )
                if requires_agent_attention(event):
                    nudge_unwatched(page)
    append_interactions(
        page_dir,
        [
            {
                "source": "cli",
                "type": "render_pass",
                "durationMs": round((time.monotonic() - started) * 1000),
                "findings": len(after["findings"]) if after else None,
                "told": len(told),
            }
        ],
    )


def _unread_since(page_dir: Path, present: dict) -> float | None:
    """When the page's live version went live, or None where the agent has closed the
    page or a reading has read that version. `present` is the page's presence reading
    (`presence.presence_with_activity`)."""
    revision = latest_revision(page_dir)
    if revision is None:
        return None
    made = revision_path(page_dir, revision).stat().st_mtime
    reading = read_reading(page_dir)
    if reading and reading["digest"] == read_artifact(page_dir, revision).digest:
        return None
    if present["status"]["state"] == "idle":
        return None
    return made


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

        Activation comes first, since a save reaches no revision until something reads
        the page, and a page handed over with no tab open has no such reader."""
        page_dir = self.page_dir
        if source_readings(page_dir)[0] == self.settled:
            return
        present, turn = claimant_reading(page_dir, read_events(page_dir))
        unread_since = None
        if present["session_alive"]:
            activate_source(page_dir)
            unread_since = _unread_since(page_dir, present)
        source = source_readings(page_dir)[0]
        if unread_since is not None:
            declared = present["status"].get("ts")
            handed_over = not turn.running or (
                declared is not None
                and datetime.fromisoformat(declared).timestamp() >= unread_since
            )
            if not handed_over or time.time() - unread_since < QUIET_S:
                return
            lease = take_lease(state_home() / LEASE)
            if lease is None:
                return
            try:
                self._read()
            finally:
                release_lease(lease)
        self.settled = source

    def _read(self) -> None:
        """Read in a child that speaks for no harness session, so the claimant's command
        diagnostics don't count its seconds as the agent's."""
        subprocess.run(
            [sys.executable, "-m", "leaf", "page", "_read", str(self.page_dir)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            env=detached_environment(None),
            check=False,
            timeout=DEADLINE_S,
        )
