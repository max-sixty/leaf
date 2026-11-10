"""What the render pass reads and what it tells. A version the agent hands over is read
once, one reading at a time on the machine, a failure wakes the agent, and advice goes
with what next reaches it."""

import json
import os
import signal
import subprocess
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from interact_support import (
    acknowledged_through,
    append_carried_log_record,
    append_command,
    continued,
    declare_data_input,
    delivered,
    last_deliverable_seq,
    working,
)

from leaf import data as data_model
from leaf import delivery as delivery_model
from leaf import hooks as hooks_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as state_model
from leaf.event_log import read_events
from leaf.files import latest_revision
from leaf.findings import Finding
from leaf.leases import release_lease, take_lease
from leaf.render_gate import handover_pass as handover_pass_model
from leaf.revision_artifact import read_artifact
from leaf.revisioning import activate_source
from leaf.state import state_home
from leaf.validation.source import check_source

FAILURE: dict[str, Any] = {
    "code": "past-column",
    "severity": "error",
    "at": "<div id=wide>",
    "widths": [360, 900],
    "values": {"by": 40},
    "text": "at 360–900px wide, <div id=wide> is set 40px past the column",
}
ADVICE: dict[str, Any] = {
    "code": "shrunk-labels",
    "severity": "advice",
    "at": "<svg>",
    "text": "<svg> draws labels below 10px",
}


@pytest.fixture
def pass_page(claimed, monkeypatch):
    """A claimed page in an open turn, whose readings this test counts, standing for
    `_read`, and which needs no time to stand before a look reads it."""
    state_model.prompt_turn("s1")
    monkeypatch.setattr(handover_pass_model, "QUIET_S", 0)
    reads = []
    monkeypatch.setattr(
        handover_pass_model.HandoverPass,
        "_read",
        lambda self: reads.append(self) or True,
    )
    return SimpleNamespace(
        dir=claimed, passes=handover_pass_model.HandoverPass(claimed), reads=reads
    )


def write_unread(page_dir: Path, words: str) -> None:
    """Save the page as an agent does, with no tab open to make the save live."""
    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace("</section>", f"<p>{words}</p></section>", 1)
    )


def save(page_dir: Path, words: str) -> None:
    """Save the page with a tab open, which makes the save live."""
    write_unread(page_dir, words)
    assert activate_source(page_dir).error is None


def read_digest(page_dir: Path) -> str:
    revision = latest_revision(page_dir)
    assert revision is not None
    return read_artifact(page_dir, revision).digest


def browser_read(findings: list[dict]) -> SimpleNamespace:
    """A browser that finished reading the page and found `findings`, as
    `command.BrowserCheck` answers."""
    return SimpleNamespace(
        unavailable=None,
        findings=lambda: [
            SimpleNamespace(code=finding["code"], json=lambda f=finding: f)
            for finding in findings
        ],
    )


def leave_reading(
    page_dir: Path, findings: list[dict], digest: str | None = None
) -> None:
    """The reading an agent's own `page check --render` leaves."""
    handover_pass_model.remember_reading(
        page_dir, digest or read_digest(page_dir), browser_read(findings)
    )


def checking(findings: list[dict], digest: str | None = None):
    """`check_page` with the browser's part standing in: a reading of `findings` in the
    live version, or in the version `digest`."""
    return lambda page_dir, **_options: (
        {},
        (digest or read_digest(page_dir), browser_read(findings)),
    )


def test_a_turn_reads_once_however_often_it_saved(pass_page):
    """Saves inside a turn wait for its end, which reads the version it handed over."""
    save(pass_page.dir, "one")
    save(pass_page.dir, "two")
    pass_page.passes.look()
    assert pass_page.reads == []

    state_model.close_session_turn("s1")
    pass_page.passes.look()
    pass_page.passes.look()
    assert len(pass_page.reads) == 1

    state_model.prompt_turn("s1")
    save(pass_page.dir, "three")
    pass_page.passes.look()
    assert len(pass_page.reads) == 1
    state_model.close_session_turn("s1")
    pass_page.passes.look()
    assert len(pass_page.reads) == 2


def test_work_in_hand_waits_and_a_page_declared_open_is_read_in_its_turn(pass_page):
    """Where no hook closes the turn record, the agent's own declaration hands over."""
    item = working(pass_page.dir, "editing the cutover note")
    save(pass_page.dir, "handed over")
    pass_page.passes.look()
    assert pass_page.reads == [], item
    session_model.cmd_waiting(pass_page.dir)
    pass_page.passes.look()
    assert len(pass_page.reads) == 1


def test_a_save_reaches_a_reading_with_no_tab_open_to_activate_it(pass_page):
    """Nothing has read the page since the save, so the look makes it live itself, once a
    reading is due: the saves inside a turn make no revisions."""
    made = latest_revision(pass_page.dir) or 0
    write_unread(pass_page.dir, "unread")
    pass_page.passes.look()
    assert (latest_revision(pass_page.dir) or 0) == made and pass_page.reads == []

    state_model.close_session_turn("s1")
    pass_page.passes.look()
    assert latest_revision(pass_page.dir) == made + 1 and len(pass_page.reads) == 1


def test_a_data_update_after_the_declaration_still_hands_the_version_over(pass_page):
    """A data update makes no new version, so a process that keeps updating the page's
    data takes back no declaration and holds off no reading."""
    # The save that binds the data, which a tab makes live.
    declare_data_input(pass_page.dir, "builds", {"type": "array"})
    session_model.cmd_waiting(pass_page.dir)
    data_model.cmd_data_set(pass_page.dir, "builds", ["green"])
    pass_page.passes.look()
    assert len(pass_page.reads) == 1


def test_a_declaration_in_the_millisecond_of_the_save_hands_it_over(pass_page):
    """The declaration keeps its time to the millisecond, so a save later in the same
    millisecond was made before it."""
    write_unread(pass_page.dir, "handed over at once")
    status = session_model.cmd_waiting(pass_page.dir)
    declared = round(datetime.fromisoformat(status["ts"]).timestamp() * 1000)
    saved = declared * 1_000_000 + 999_999
    os.utime(pass_page.dir / "index.html", ns=(saved, saved))
    pass_page.passes.look()
    assert len(pass_page.reads) == 1


def test_a_version_a_reading_has_read_is_not_read_again_by_a_later_server(pass_page):
    """The reading outlives the server, so reopening a page reads only what changed, and
    the agent's own check leaves one, so a version it checked isn't read again."""
    save(pass_page.dir, "read before")
    leave_reading(pass_page.dir, [])
    state_model.close_session_turn("s1")
    handover_pass_model.HandoverPass(pass_page.dir).look()
    assert pass_page.reads == []


def test_saves_with_no_turn_open_wait_until_the_version_stands(pass_page, monkeypatch):
    """A build left running after the turn ended coalesces in the quiet window."""
    state_model.close_session_turn("s1")
    save(pass_page.dir, "from a build")
    monkeypatch.setattr(handover_pass_model, "QUIET_S", 3600)
    pass_page.passes.look()
    assert pass_page.reads == []
    monkeypatch.setattr(handover_pass_model, "QUIET_S", 0)
    pass_page.passes.look()
    assert len(pass_page.reads) == 1


def test_a_page_nobody_holds_has_nobody_to_tell(pass_page):
    save(pass_page.dir, "after the session")
    state_model.end_session("s1")
    pass_page.passes.look()
    assert pass_page.reads == []


def test_a_page_its_agent_closed_has_nobody_to_tell(pass_page):
    save(pass_page.dir, "last words")
    state_model.close_session_turn("s1")
    with service_model.PageTransaction(pass_page.dir) as page:
        page.set_status("idle")
    pass_page.passes.look()
    assert pass_page.reads == []


def test_the_machine_runs_one_reading_at_a_time(pass_page, monkeypatch):
    """A reading finding another under way reads nothing, and its server asks again."""
    save(pass_page.dir, "queued")
    state_model.close_session_turn("s1")
    lease = take_lease(state_home() / handover_pass_model.LEASE)
    try:
        assert handover_pass_model.read_and_tell(pass_page.dir) is False
    finally:
        release_lease(lease)
    asked = []
    monkeypatch.setattr(
        handover_pass_model.HandoverPass,
        "_read",
        lambda self: asked.append(self) and len(asked) > 1,
    )
    pass_page.passes.look()
    pass_page.passes.look()
    assert len(asked) == 2


def test_a_server_started_again_mid_reading_reads_nothing_twice(claimed, monkeypatch):
    """The second reading waits on the first for the lease, then finds it read."""
    activate_source(claimed)
    leave_reading(claimed, [FAILURE])

    def read_again(*_args, **_kwargs):
        raise AssertionError("read a version a reading had read")

    monkeypatch.setattr("leaf.validation.command.check_page", read_again)
    assert handover_pass_model.read_and_tell(claimed) is True
    assert [e for e in events_of(claimed) if e["kind"] == "render"] == []


def test_a_page_too_heavy_to_read_costs_its_deadline_once(claimed, monkeypatch):
    """A reading its alarm ended stops its server's pass."""
    ran = []

    def overran(*args, **_kwargs):
        ran.append(args)
        return subprocess.CompletedProcess(args, -signal.SIGALRM)

    monkeypatch.delenv(handover_pass_model.VARIABLE)
    monkeypatch.setattr(handover_pass_model, "LOOK_S", 0)
    monkeypatch.setattr(handover_pass_model, "QUIET_S", 0)
    monkeypatch.setattr(handover_pass_model.subprocess, "run", overran)
    state_model.prompt_turn("s1")
    save(claimed, "heavy")
    state_model.close_session_turn("s1")
    handover_pass_model.HandoverPass(claimed).run()
    assert len(ran) == 1


def test_a_reading_a_browser_could_not_finish_leaves_none(page_dir):
    """Chrome failing says nothing of the page, so nothing is told or refused for it."""
    failed = Finding("gate-failed", values={"error": "Target closed"})
    handover_pass_model.remember_reading(
        page_dir,
        "sha256:0",
        SimpleNamespace(unavailable=None, findings=lambda: [failed]),
    )
    handover_pass_model.remember_reading(
        page_dir, "sha256:0", SimpleNamespace(unavailable="no browser", findings=list)
    )
    assert handover_pass_model.read_reading(page_dir) is None


@pytest.fixture
def told(claimed, monkeypatch):
    """Save a version and read and tell `findings` of it, as a server's child does
    with each version handed over."""
    versions = iter(range(1, 100))

    def read(findings: list[dict]) -> list[dict]:
        save(claimed, f"version {next(versions)}")
        monkeypatch.setattr("leaf.validation.command.check_page", checking(findings))
        handover_pass_model.read_and_tell(claimed)
        return [e for e in events_of(claimed) if e["kind"] == "render"]

    return read


def events_of(page_dir: Path) -> list[dict]:
    with service_model.PageTransaction(page_dir) as page:
        return list(page.events)


def deliverable(page_dir: Path) -> list[dict]:
    with service_model.PageTransaction(page_dir) as page:
        return delivery_model.deliverable(page)


def test_a_failure_wakes_the_agent_and_its_words_reach_it(claimed, told, capsys):
    [event] = told([FAILURE, ADVICE])
    assert event["attention"] is True
    assert [e["id"] for e in deliverable(claimed)] == [event["id"]]

    assert session_model.cmd_wait(claimed) == 0
    _, batch, [shown] = delivered(capsys)
    assert [f["text"] for f in shown["findings"]] == [FAILURE["text"], ADVICE["text"]]
    # The words carry the measurements; the log needn't hold them twice.
    assert all("values" not in f for f in shown["findings"])
    [clause] = [batch["handling"][ref] for ref in shown["handling"]]
    assert "Fix each failure" in clause and "Weigh each piece of advice" in clause
    assert "answer" not in shown


def test_advice_alone_wakes_nobody_and_goes_with_what_next_reaches_the_agent(
    claimed, told, capsys
):
    [event] = told([ADVICE])
    assert event["attention"] is False
    assert deliverable(claimed) == []

    comment = append_command(
        claimed,
        {"kind": "comment", "author": "user", "text": "looks good", "revision": 1},
    )
    assert session_model.cmd_wait(claimed) == 0
    _, batch, shown = delivered(capsys)
    assert [e["id"] for e in shown] == [event["id"], comment["id"]]
    assert batch["handling"][shown[0]["handling"][0]].startswith("Leaf's render check")
    # The receipt moved the cursor past it, so it reaches the agent once.
    assert event["id"] not in [e["id"] for e in deliverable(claimed)]


def test_advice_holds_no_turn_and_goes_in_with_what_a_hook_hands_over(
    claimed, printing, told, capsys
):
    [advice] = told([ADVICE])
    repeated = {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True}
    hooks_model.cmd_hook("claude-code", repeated)
    assert capsys.readouterr().out == ""

    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "is it readable?"}
    )
    state_model.prompt_turn("s1")
    hooks_model.cmd_hook("claude-code", repeated)
    envelope = json.loads(continued(json.loads(capsys.readouterr().out)).split("\n")[1])
    [batch] = envelope["batches"]
    assert [e["id"] for e in batch["events"]] == [advice["id"], comment["id"]]

    # The Stop that follows the continued turn confirms what it read, advice included.
    hooks_model.cmd_hook("claude-code", repeated)
    capsys.readouterr()
    assert acknowledged_through(claimed) == last_deliverable_seq(claimed)
    assert advice["id"] not in [e["id"] for e in deliverable(claimed)]


def test_only_what_the_last_reading_did_not_hold_is_told(claimed, told):
    """An edit that moves a measurement tells nothing again; a fault fixed and
    reintroduced is told again."""
    assert len(told([FAILURE])) == 1
    moved = {**FAILURE, "widths": [360, 700], "text": "at 360–700px wide, moved"}
    assert len(told([moved])) == 1
    assert told([]) and len(told([moved])) == 2


def test_a_finding_naming_no_element_is_not_told_again_for_its_measurements(
    claimed, told
):
    """A layout shift's words carry when it started, and a sideways scroll's how far,
    and neither names an element, so another reading that measures them anew holds
    nothing the agent hasn't heard."""
    shift = {
        "code": "startup-layout-shift",
        "severity": "advice",
        "values": {"cls": 0.12, "entries": [{"at": 812.4, "value": 0.12}]},
        "text": "startup CLS 0.1200 before first settled presentation; …812.4…",
    }
    scrolls = {
        "code": "page-scrolls",
        "severity": "error",
        "widths": [360, 480],
        "values": {"past": 206},
        "text": "at 360–480px wide, the page scrolls sideways by 206px",
    }
    assert len(told([shift, scrolls])) == 1
    remeasured = [
        {
            **shift,
            "values": {"cls": 0.12, "entries": [{"at": 905.1, "value": 0.12}]},
            "text": "startup CLS 0.1200 before first settled presentation; …905.1…",
        },
        {
            **scrolls,
            "widths": [360, 400],
            "values": {"past": 190},
            "text": "at 360–400px wide, the page scrolls sideways by 190px",
        },
    ]
    assert len(told(remeasured)) == 1


def test_console_errors_are_told_apart_by_their_words(claimed, told):
    """A console error names no element, so its words are what make it another fault."""
    first = {
        "code": "console-error",
        "severity": "error",
        "text": "console: first",
        "values": {"text": "first"},
    }
    second = {**first, "text": "console: second", "values": {"text": "second"}}
    assert len(told([first])) == 1
    assert len(told([first, second])) == 2


def test_a_save_before_the_check_froze_the_source_is_the_version_told(claimed):
    """The check reads the source as it stands when it starts, a save the activation
    before it missed included, and that save is the version the agent hears about."""
    activate_source(claimed)

    def saved_first(page_dir, **_options):
        write_unread(page_dir, "saved as the check began")
        checked = check_source(page_dir, read_events(page_dir))
        assert checked.artifact is not None
        return checking([FAILURE], checked.artifact.digest)(page_dir)

    with pytest.MonkeyPatch.context() as patched:
        patched.setattr("leaf.validation.command.check_page", saved_first)
        handover_pass_model.read_and_tell(claimed)
    [event] = [e for e in events_of(claimed) if e["kind"] == "render"]
    assert event["revision"] == latest_revision(claimed)
    reading = handover_pass_model.read_reading(claimed)
    assert reading is not None and reading["digest"] == read_digest(claimed)


def test_a_save_past_the_version_read_leaves_its_findings_to_the_next_reading(
    claimed, told, monkeypatch
):
    """Nothing is told of a version nobody sees any more, and none of it is lost."""
    activate_source(claimed)
    stale = read_digest(claimed)

    def moved_on(page_dir, **_options):
        save(page_dir, "moved on")
        return checking([FAILURE], stale)(page_dir)

    monkeypatch.setattr("leaf.validation.command.check_page", moved_on)
    handover_pass_model.read_and_tell(claimed)
    assert [e for e in events_of(claimed) if e["kind"] == "render"] == []

    [event] = told([FAILURE])
    assert event["revision"] == latest_revision(claimed)
