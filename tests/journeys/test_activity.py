"""Tests scheduled by the measured cost of their boundary."""

from datetime import datetime, timedelta

from click.testing import CliRunner
from interact_support import (
    activity_reading,
    declare,
    declare_work,
    page_state,
    record_claim,
)

from leaf.base import leases as leases_model
from leaf.base import service as service_model
from leaf.base import state as cleanup_model
from leaf.commands import cli as cli_model
from leaf.records import activity as activity_model


def test_only_a_fresh_turn_whose_hooks_take_input_reads_listening(
    claimed, codex_claimed_page
):
    """Listening between two waits rests on the open turn taking the input, which
    only a session whose hooks hand it over does, and only while the turn is
    plausibly running. A Codex task's open turn takes input once a tool hook has
    proven its hooks run, since the tool hook then offers the pointer between
    steps; before that, with no adapter lease, it is nobody listening. A Claude Code turn
    no Stop closed, as an interrupted one, stops counting once nothing in it has
    renewed it for the working grace: its opening, or a status written during it."""
    now = datetime.now().astimezone()
    for page in (claimed, codex_claimed_page):
        declare(page, ts=now.isoformat())
    codex = page_state(codex_claimed_page)
    # Every other clause of the rule holds, so only the watcher can read it away.
    assert codex["session_alive"] is True
    assert codex["turn"] and codex["turn_closed"] is None
    assert codex["turn_opened"] and not codex["turn_takes_input"]
    assert codex["listening"] is False
    assert codex["activity"]["presence"] == "away"
    leases_model.mark_hooks("codex-thread")
    codex = page_state(codex_claimed_page)
    assert codex["turn_takes_input"] and codex["listening"] is False
    assert codex["activity"]["presence"] == "here"

    assert activity_reading(claimed)["presence"] == "here"
    claim = service_model.page_claim(claimed)

    # A stale status does not mask the open turn's own deadline: with the status
    # already quiet, listening's only remaining source is the turn, so its own
    # working-grace boundary must still be scheduled, or the browser is left
    # showing Listening past the point the turn can plausibly still be running.
    opened = (now - timedelta(minutes=1)).replace(microsecond=0)
    assert claim is not None
    record_claim(claimed, **{**claim, "turn_opened": opened.isoformat()})
    declare(claimed, ts="2020-01-01T00:00:00+00:00")
    listening = activity_reading(claimed)
    assert listening["presence"] == "here"
    assert (
        listening["next_transition_at"]
        == (opened + activity_model.WORKING_GRACE).isoformat()
    )

    # The fresh turn is someone there under a start gone stale too, so that old work
    # reads stalled rather than away, until its task ends.
    old_start = declare_work(
        claimed, "an old task", ts="2020-01-01T00:00:00+00:00", session="s1"
    )
    stalled = activity_reading(claimed)
    assert (stalled["presence"], stalled["state"]) == ("here", "blocked")
    ended = CliRunner().invoke(
        cli_model.cli, ["task", "end", str(claimed), old_start["item"], "done"]
    )
    assert ended.exit_code == 0, ended.output
    claim = service_model.page_claim(claimed)
    opened = now - activity_model.WORKING_GRACE - timedelta(minutes=1)
    assert claim is not None
    record_claim(
        claimed, **{**claim, "turn_opened": opened.isoformat(timespec="seconds")}
    )
    declare(claimed, ts=opened.isoformat())
    stale = page_state(claimed)
    assert (stale["turn_takes_input"], stale["turn_closed"]) == (True, None)
    assert stale["activity"]["presence"] == "away"

    # A status the turn writes renews it: the agent is there to have written it.
    declare(claimed, ts=now.isoformat())
    assert activity_reading(claimed)["presence"] == "here"

    # A session whose record a Leaf of another shape wrote, with no
    # `turn_opened`, owes no belief either: this Leaf reads no record of it.
    lifecycle = cleanup_model.session_record("s1")
    assert lifecycle is not None
    path = cleanup_model.session_file("s1", cleanup_model.SESSION_SUFFIX)
    cleanup_model.SESSION.remove(path)
    cleanup_model.write_json(
        path.with_name(f"{path.stem}@13{path.suffix}"),
        {
            "format": "leaf-session/13",
            **{key: value for key, value in lifecycle.items() if key != "turn_opened"},
        },
    )
    assert activity_reading(claimed)["presence"] == "gone"
