"""What a delivery carries: the events it freezes, the handling each event's case
asks for, the thread and widget context that makes a gesture readable, the bound
that keeps its envelope small, and its id."""

import json

from interact_support import (
    PAGE,
    SETTLING_ACCEPT,
    SETTLING_DECISION,
    _settling_page,
    append_carried_log_record,
    append_command,
    delivered,
    last_deliverable_seq,
    publish,
    receive_through,
    serving,
    state_json,
)

from leaf import event_contracts as event_contracts_model
from leaf import event_log as events_model
from leaf import event_meaning as event_meaning_model
from leaf import page_view as page_view_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import thread_context as thread_context_model
from leaf.registry import storage as registry_storage


def test_a_page_obligation_that_settles_a_thread_carries_its_thread(page_dir, capsys):
    """A gesture settles a thread through its widget's `resolves`, and the
    widget it is made on need not stand in that thread — for the one shipped
    settling verb, `lf-suggestion`'s decide, it stands on the page and in no
    thread at all. Reading the sending widget alone therefore left the gesture
    that closes a thread as the one gesture arriving with nothing behind it."""
    _settling_page(page_dir)
    receive_through(page_dir, 1)  # c1 delivered; its words are the
    capsys.readouterr()  # envelope's to carry from here
    append_command(page_dir, dict(SETTLING_ACCEPT))
    # The action door accepts this event, so the shape is the product's own.
    events = events_model.read_events(page_dir)
    assert (
        event_contracts_model.action_contract_error(
            page_view_model.PageView(page_dir),
            events[-1],
            event_meaning_model.AdmissionReadings(
                page_view_model.PageView(page_dir),
                events,
                registry_storage.require_registry(page_dir),
            ),
        )
        is None
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, header, _ = delivered(capsys)
    assert [t["resolved"] for t in state_json(page_dir)["threads"]] == ["user"]
    assert [t["id"] for t in header["threads"]] == ["c1"], json.dumps(header)
    message = header["threads"][0]["messages"][0]
    assert "text" not in message
    assert message["drawing"] == SETTLING_DECISION["drawing"]


def test_an_undo_of_a_page_obligation_carries_the_thread_it_reopens(page_dir, capsys):
    """Withdrawing that gesture reopens the thread, so the delivery owes
    the same reading the accept did."""
    _settling_page(page_dir)
    accepted = append_command(page_dir, dict(SETTLING_ACCEPT))
    receive_through(page_dir, last_deliverable_seq(page_dir))
    capsys.readouterr()
    append_carried_log_record(
        page_dir, {"kind": "undo", "author": "user", "undoes": accepted["id"]}
    )

    assert session_model.cmd_wait(page_dir) == 0
    _, header, _ = delivered(capsys)
    assert [t["resolved"] for t in state_json(page_dir)["threads"]] == [None]
    assert [t["id"] for t in header["threads"]] == ["c1"], json.dumps(header)


def test_the_envelope_stops_growing_with_the_thread(page_dir, capsys):
    """A delivery reprints the whole thread every time, because the agent it is
    for may hold none of it. Unbounded, the header grows with the thread
    until it alone outgrows the output it prints into — and that is the one
    shape acknowledgement cannot recover from, since the ack rule's remedy for
    truncation is to rerun, and a rerun prints the same oversize header. So the
    digest keeps the message that opened the thread and the most recent, and
    says how many it dropped between."""
    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir)
    serving(page_dir, 1)
    markup = (
        '<lf-options id="{i}" choose>'
        + "".join(
            f'<lf-option id="{{i}}-o{n}"><strong>Option {n}</strong> '
            + "z" * 60
            + "</lf-option>"
            for n in range(3)
        )
        + "</lf-options>"
    )
    root = append_carried_log_record(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "y" * 188},
    )
    initial_thread_state_size = len(json.dumps(state_json(page_dir)["threads"]))
    parent, headers = root["id"], []
    assert service_model.claim_page(page_dir)
    for turn in range(30):
        agent = append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "parent": parent,
                "text": "x" * 532,  # the shipped ship-review example's reply length
                "markup": markup.format(i=f"w{turn}"),
            },
        )
        parent = append_carried_log_record(
            page_dir,
            {"kind": "reply", "author": "user", "parent": agent["id"], "text": "ok"},
        )["id"]
        assert session_model.cmd_wait(page_dir) == 0
        _, batch, _ = delivered(capsys)
        headers.append(len(json.dumps(batch["threads"])))
        receive_through(page_dir, last_deliverable_seq(page_dir))
        capsys.readouterr()

    # Flat, not merely slower: twenty further exchanges add only the few
    # characters a longer sequence number spends. Page state likewise keeps the
    # thread itself flat; its separate element inventory grows here because
    # every reply deliberately adds a live widget contract.
    assert headers[-1] - headers[9] < 100, headers
    assert (
        len(json.dumps(state_json(page_dir)["threads"])) - initial_thread_state_size
        < 100
    )
    [thread] = batch["threads"]
    assert len(thread["messages"]) == thread_context_model.SHOWN
    assert thread["elided"]["messages"] == 52
    # The opening message survives the bound: it holds what the thread is about.
    assert thread["messages"][0]["id"] == root["id"]
