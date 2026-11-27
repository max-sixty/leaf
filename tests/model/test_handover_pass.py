"""What the render pass reads and what it tells. A version the agent hands over is read
once, a failure wakes the agent, and advice goes with what next reaches it. The parts
each visual drew reach `page state` while the version read is the one it shows."""

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
    FLOW_PAGE,
    acknowledged_through,
    append_carried_log_record,
    append_command,
    continued,
    declare_data_input,
    delivered,
    inlined,
    last_deliverable_seq,
    state_json,
    working,
)

from leaf.agents import delivery as delivery_model
from leaf.agents import thread as thread_model
from leaf.base import harness as harness_model
from leaf.base import leases as leases_model
from leaf.base import state as state_model
from leaf.base.files import latest_revision
from leaf.base.findings import Finding
from leaf.commands import hooks as hooks_model
from leaf.commands import session as session_model
from leaf.commands.session import set_status
from leaf.log.event_log import read_events
from leaf.records import page_data as page_data_model
from leaf.records import transaction as transaction_model
from leaf.records.authored_checks.source import check_source
from leaf.records.render_reading import read_reading
from leaf.records.revisioning import activate_source
from leaf.serving import handover_pass as handover_pass_model
from leaf.serving import server_rows as server_rows_model
from leaf.serving.served_state.context import read_page
from leaf.source.revision_artifact import read_artifact

FAILURE: dict[str, Any] = {
    "code": "past-column",
    "severity": "error",
    "at": "<div id=wide>",
    "widths": [360, 900],
    "values": {"by": 40},
    "text": "at 360–900px wide, <div id=wide> is set 40px past the column",
}
DRAWN = {
    "flow": {
        "parts": [{"id": "node:A", "label": "A"}, {"id": "node:B", "label": "B"}],
        "whole": False,
    }
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
        lambda self, _digest: reads.append(self),
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


def browser_read(
    findings: list[dict], visuals: dict[str, dict] | None = None
) -> SimpleNamespace:
    """A browser that finished reading the page, found `findings` and read what each
    visual drew (`visuals`), as `command.BrowserCheck` answers."""
    return SimpleNamespace(
        findings=lambda: [
            SimpleNamespace(
                code=finding["code"], unread=False, json=lambda f=finding: f
            )
            for finding in findings
        ],
        render=SimpleNamespace(visuals=visuals or {}),
    )


def data_version(page_dir: Path) -> str:
    """The version of the data the page holds now (`data.data_version`)."""
    return read_page(page_dir, read_events(page_dir)).data["version"]


def leave_reading(
    page_dir: Path, findings: list[dict], digest: str | None = None
) -> None:
    """The reading an agent's own `page check --render` leaves."""
    handover_pass_model.remember_reading(
        page_dir,
        digest or read_digest(page_dir),
        data_version(page_dir),
        browser_read(findings),
    )


def checking(
    findings: list[dict],
    digest: str | None = None,
    visuals: dict[str, dict] | None = None,
):
    """`check_page` with the browser's part standing in: a reading of `findings`, and of
    what each visual drew (`visuals`), in the live version, or in the version `digest`,
    with the data the page holds."""
    return lambda page_dir, **_options: (
        {},
        (
            digest or read_digest(page_dir),
            data_version(page_dir),
            browser_read(findings, visuals),
        ),
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
    page_data_model.cmd_data_set(pass_page.dir, "builds", ["green"])
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
    with transaction_model.PageTransaction(pass_page.dir) as page:
        set_status(page, "idle")
    pass_page.passes.look()
    assert pass_page.reads == []


def test_a_reading_beside_another_of_its_version_tells_nothing_twice(claimed):
    """A server started again mid-reading may read that version a second time, and a
    reading taken at another viewport may find otherwise. The first reading to tell
    tells the version; the other tells nothing."""
    save(claimed, "read twice")
    first = checking([FAILURE])

    def beside_another(page_dir, **options):
        handover_pass_model.read_and_tell(page_dir, first)
        return checking([ADVICE])(page_dir, **options)

    handover_pass_model.read_and_tell(claimed, beside_another)
    [event] = [e for e in events_of(claimed) if e["kind"] == "render"]
    assert [f["text"] for f in event["findings"]] == [FAILURE["text"]]


def test_a_reading_its_alarm_ended_is_told_as_a_failure_and_costs_it_once(
    claimed, monkeypatch
):
    """A page whose script never stops is told it couldn't be read, its version isn't
    read again, and its next version is."""
    ran = []

    def overran(*args, **_kwargs):
        ran.append(args)
        return subprocess.CompletedProcess(args, -signal.SIGALRM)

    monkeypatch.setattr(handover_pass_model, "QUIET_S", 0)
    monkeypatch.setattr(handover_pass_model.subprocess, "run", overran)
    state_model.prompt_turn("s1")
    save(claimed, "loops")
    state_model.close_session_turn("s1")
    handover_pass_model.HandoverPass(claimed).look()
    handover_pass_model.HandoverPass(claimed).look()
    assert len(ran) == 1
    [event] = [e for e in events_of(claimed) if e["kind"] == "render"]
    [finding] = event["findings"]
    assert finding["severity"] == "error"
    assert "after 30 minutes" in finding["text"]
    state_model.prompt_turn("s1")
    save(claimed, "fixed")
    state_model.close_session_turn("s1")
    handover_pass_model.HandoverPass(claimed).look()
    assert len(ran) == 2


@pytest.mark.parametrize(
    "unread",
    [
        Finding("gate-failed", values={"error": "Target closed"}),
        Finding("probe-failed", values={"error": "Target closed"}),
        Finding("browser-error", values={"error": "Target closed"}),
        Finding("server-stopped", values={"error": "Timeout 30000ms exceeded."}),
        Finding("no-browser", values={"error": "no browser launched: none found"}),
    ],
    ids=lambda finding: finding.code,
)
def test_a_reading_a_browser_could_not_finish_leaves_none(page_dir, unread):
    """A browser that crashed or a preview server that stopped answering says
    nothing of the page, so nothing is told or refused for it, as where no browser
    ran."""
    handover_pass_model.remember_reading(
        page_dir, "sha256:0", "data", SimpleNamespace(findings=lambda: [unread])
    )
    assert read_reading(page_dir) is None


@pytest.fixture
def told(claimed):
    """Save a version and read and tell `findings` of it, as a server's child does
    with each version handed over."""
    versions = iter(range(1, 100))

    def read(findings: list[dict]) -> list[dict]:
        save(claimed, f"version {next(versions)}")
        handover_pass_model.read_and_tell(claimed, checking(findings))
        return [e for e in events_of(claimed) if e["kind"] == "render"]

    return read


def events_of(page_dir: Path) -> list[dict]:
    with transaction_model.PageTransaction(page_dir) as page:
        return list(page.events)


def deliverable(page_dir: Path) -> list[dict]:
    with transaction_model.PageTransaction(page_dir) as page:
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


def test_advice_wakes_nobody_once_what_came_with_it_is_answered(
    claimed, interactive, told, monkeypatch
):
    """A comment the agent answered before its receipt still rides in the receipt
    batch, and the advice told beside it goes with it (`delivery.deliverable`). With
    the comment answered, advice is all that is left for the agent, and it wakes the
    session by none of the three routes: a watch between turns, the nudge a watch
    sends for what it leaves as it ends, and the server's nudge after a turn Escape
    interrupted."""
    session_model.cmd_waiting(claimed)
    [advice] = told([ADVICE])
    comment = append_command(
        claimed,
        {"kind": "comment", "author": "user", "text": "looks good", "revision": 1},
    )
    thread_model.post_reply(
        claimed, {"parent": comment["id"], "responds": comment["id"]}, "Thanks."
    )
    assert [e["id"] for e in deliverable(claimed)] == [advice["id"], comment["id"]]
    nudged = []
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness,
        "nudge",
        lambda harness, page, quoted: nudged.append(page) or True,
    )

    # A Stop hook closed the turn; its watch makes one pass, its harness process then
    # ends, and the watch nudges for what it leaves.
    leases_model.mark_hooks("s1")
    state_model.close_session_turn("s1")
    runs = iter([True])
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness,
        "process_runs",
        lambda harness: next(runs, False),
    )
    monkeypatch.setattr(
        session_model.Watch, "await_news", lambda watch, mark, timeout=0: False
    )
    stop = {"hook_event_name": "Stop", "session_id": "s1"}
    assert hooks_model.cmd_watch("claude-code", stop) is None
    assert nudged == []

    # Escape interrupts the next turn, which Claude Code's record reads as idle.
    state_model.prompt_turn("s1")
    idle = {
        "state": "idle",
        "since": datetime.now().astimezone().isoformat(),
        "command": False,
    }
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness, "live_turn", lambda harness: dict(idle)
    )
    server_rows_model.nudge_interrupted(claimed)
    assert nudged == []


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
    envelope = inlined(continued(json.loads(capsys.readouterr().out)))
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
    """A sideways scroll's words carry how far it scrolls and names no element, so
    another reading that measures it anew holds nothing the agent hasn't heard."""
    scrolls = {
        "code": "page-scrolls",
        "severity": "error",
        "widths": [360, 480],
        "values": {"past": 206},
        "text": "at 360–480px wide, the page scrolls sideways by 206px",
    }
    assert len(told([scrolls])) == 1
    remeasured = {
        **scrolls,
        "widths": [360, 400],
        "values": {"past": 190},
        "text": "at 360–400px wide, the page scrolls sideways by 190px",
    }
    assert len(told([remeasured])) == 1


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

    handover_pass_model.read_and_tell(claimed, saved_first)
    [event] = [e for e in events_of(claimed) if e["kind"] == "render"]
    assert event["revision"] == latest_revision(claimed)
    reading = read_reading(claimed)
    assert reading is not None and reading["digest"] == read_digest(claimed)


def test_a_save_past_the_version_read_leaves_its_findings_to_the_next_reading(
    claimed, told
):
    """Nothing is told of a version nobody sees any more, and none of it is lost."""
    activate_source(claimed)
    stale = read_digest(claimed)

    def moved_on(page_dir, **_options):
        save(page_dir, "moved on")
        return checking([FAILURE], stale)(page_dir)

    handover_pass_model.read_and_tell(claimed, moved_on)
    assert [e for e in events_of(claimed) if e["kind"] == "render"] == []

    [event] = told([FAILURE])
    assert event["revision"] == latest_revision(claimed)


def flow_element(page_dir: Path) -> dict:
    """The diagram `flow` as `page state` lists it among the page's elements."""
    (element,) = (e for e in state_json(page_dir)["elements"] if e["id"] == "flow")
    return element


def test_page_state_lists_the_parts_drawn_in_the_version_it_shows(claimed):
    """The reading of a version hands `page state` the parts each visual drew in it,
    on the visual's element, and a later version shows none of them until it is read
    in turn: its visuals may draw other parts."""
    (claimed / "index.html").write_text(FLOW_PAGE)
    assert activate_source(claimed).error is None
    handover_pass_model.read_and_tell(claimed, checking([], visuals=DRAWN))
    assert flow_element(claimed)["parts"] == DRAWN["flow"]["parts"]
    save(claimed, "a later version")
    assert "parts" not in flow_element(claimed)


def test_a_data_update_lists_no_parts_until_a_check_reads_it(claimed):
    """A data update makes no new version but can change what a visual draws, so the
    parts a check drew list only while the page holds the data it read, and the next
    check lists them again."""
    (claimed / "index.html").write_text(FLOW_PAGE)
    declare_data_input(claimed, "builds", {"type": "array"})
    handover_pass_model.remember_reading(
        claimed, read_digest(claimed), data_version(claimed), browser_read([], DRAWN)
    )
    assert flow_element(claimed)["parts"] == DRAWN["flow"]["parts"]
    page_data_model.cmd_data_set(claimed, "builds", ["green"])
    assert "parts" not in flow_element(claimed)
    handover_pass_model.remember_reading(
        claimed, read_digest(claimed), data_version(claimed), browser_read([], DRAWN)
    )
    assert flow_element(claimed)["parts"] == DRAWN["flow"]["parts"]
