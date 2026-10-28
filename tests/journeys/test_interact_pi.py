"""Pi as a harness: the one its environment implies, and Leaf's extension
(`hooks/pi.ts`) carrying a page's input into its runs.

`pi_driver.mjs` stands in for Pi around the extension, which calls the real
launcher, so these hold the extension and the hooks it calls together."""

import json

import pytest
from interact_support import (
    append_carried_log_record,
    page_state,
    wait_for,
)
from process.test_interact_pi import (  # noqa: F401 (fixtures)
    pi_fixture,
    start_pi_fixture,
)

from leaf import event_log as events_model
from leaf import leases as leases_model
from leaf import service as service_model
from leaf import state as cleanup_model


@pytest.mark.parametrize("cancelled", [False, True])
@pytest.mark.parametrize("role", ["user", "custom"])
def test_the_pi_extension_carries_a_comment_into_a_new_run(
    page_dir, pi, cancelled, role
):
    """The extension keeps the watch running from the session's start. A
    comment arriving while Pi is idle wakes the watch, and the extension starts a
    run with an unreceipted notification. The accepted incoming message takes
    the whole delivery into context, using the same envelope as Claude Code. Ending the
    session ends the claim's lifetime."""
    claim = service_model.page_claim(page_dir)
    assert (claim["harness"], claim["id"], claim["agent"]) == ("pi", "pi-s1", "Pi")
    assert cleanup_model.session_record("pi-s1")["lifetime"] == {"pid": pi.pid}

    # A run with nothing pending: no context at its prompt, nothing that keeps it
    # going as it settles.
    assert pi.emit("before_agent_start") is None
    pi.emit("agent_start")
    assert pi.emit("agent_before_settle") is None
    pi.emit("agent_settled", idle=True)
    closed_turn = cleanup_model.session_record("pi-s1")["turn"]

    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
    )
    sent = pi.message()
    # Pi starts a run when none is going, and steers the running one.
    assert sent["options"] == {"triggerTurn": True, "deliverAs": "steer"}
    assert page_state(page_dir)["pending"] == 1
    assert not any(
        event["kind"] == "pickup" for event in events_model.read_events(page_dir)
    )
    assert pi.emit("before_agent_start") is None
    assert page_state(page_dir)["pending"] == 1
    pi.emit("agent_start")
    active = cleanup_model.session_record("pi-s1")
    assert active["turn"] != closed_turn and active["turn_closed"] is None
    assert page_state(page_dir)["pending"] == 1
    if cancelled:
        # An idle notification may become a queued steer when a user run
        # starts beside it. Clearing that notification has received no input.
        assert (
            pi.emit(
                "message_end",
                message={
                    "role": "user",
                    "content": [{"type": "text", "text": "cancelled"}],
                    "timestamp": 0,
                },
                aborted=True,
            )
            is None
        )
        assert pi.emit("turn_end", aborted=True) is None
        assert page_state(page_dir)["pending"] == 1
        pi.emit("agent_settled", idle=True)
        pi.message()
        assert page_state(page_dir)["pending"] == 1
        pi.emit("agent_start")
    assert pi.emit("message_end", message={"role": "assistant", "content": []}) is None
    assert (
        pi.emit(
            "message_end",
            message={"role": "custom", "customType": "other", "content": "other"},
        )
        is None
    )
    assert page_state(page_dir)["pending"] == 1
    incoming = (
        {
            "role": "custom",
            "customType": "leaf",
            "content": "Leaf: input",
            "display": True,
            "timestamp": 0,
        }
        if role == "custom"
        else {
            "role": "user",
            "content": [
                {"type": "text", "text": "user prompt"},
                {"type": "image", "mimeType": "image/png", "data": "image"},
            ],
            "timestamp": 0,
        }
    )
    accepted = pi.emit("message_end", message=incoming)["message"]
    assert accepted["role"] == incoming["role"]
    assert accepted["content"][:-1] == (
        [{"type": "text", "text": incoming["content"]}]
        if role == "custom"
        else incoming["content"]
    )
    delivery = json.loads(accepted["content"][-1]["text"].split("\n")[1])
    assert pi.emit("turn_end") is None
    assert delivery["acknowledge"] is None
    [batch] = delivery["batches"]
    assert [event["id"] for event in batch["events"]] == [comment["id"]]
    assert page_state(page_dir)["pending"] == 0
    [workflow] = page_state(page_dir)["workflows"]
    assert workflow["stage"] == "picked_up"

    pi.quit()
    assert cleanup_model.session_record("pi-s1")["ended"] is not None


def test_input_during_a_run_is_picked_up_only_once_pi_takes_it(page_dir, pi):
    """A move reads Picked up once its delivery is in the session's context. Pi
    queues a steer behind a running tool and Escape clears that queue, so input
    arriving during a run waits for the run's next turn end; a run stopped
    before then never took it, and a fresh watch hands it into a new run."""
    pi.emit("before_agent_start")
    pi.emit("agent_start")
    closed_watches = pi.closed_watches
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "during a tool"}
    )
    wait_for(
        lambda: leases_model.wait_is_live(None, "pi-s1"),
        lambda live: not live,
        failure="the watch did not wake on the comment",
    )

    wait_for(
        lambda: pi.closed_watches > closed_watches,
        bool,
        failure="the watch notification did not finish",
    )

    def stage() -> str:
        [workflow] = page_state(page_dir)["workflows"]
        return workflow["stage"]

    interrupted_turn = cleanup_model.session_record("pi-s1")["turn"]
    assert stage() != "picked_up"
    # Pi emits a turn boundary for the cancelled tool before agent_settled.
    # That boundary still has the old aborted signal and cannot take input.
    assert pi.emit("turn_end", aborted=True) is None
    assert stage() != "picked_up"
    assert cleanup_model.session_record("pi-s1")["turn"] == interrupted_turn
    pi.emit("agent_settled", idle=True)
    assert pi.delivered(until=comment["id"]) == [comment["id"]]
    assert cleanup_model.session_record("pi-s1")["turn"] != interrupted_turn
    assert stage() == "picked_up"


def test_a_reload_keeps_the_pi_session_and_its_watch(page_dir, pi):
    """`/reload` shuts the extension down and loads it again in the same session,
    so the session's claims stand and the reloaded extension watches them."""
    pi.reload()
    assert cleanup_model.session_record("pi-s1")["ended"] is None
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "after reload"}
    )
    assert pi.delivered(until=comment["id"]) == [comment["id"]]
