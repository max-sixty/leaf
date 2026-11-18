"""Tests scheduled by the measured cost of their boundary."""

import pytest
from interact_support import vendored_at_another_protocol
from model.test_hooks import deliveries_started, select_another_leaf

from leaf import harness as harness_model
from leaf import session_runtime as session_runtime_model
from leaf import vendoring as vendoring_model


@pytest.mark.parametrize("command", ["page init", "renewal"])
def test_a_checkout_that_takes_over_a_held_page_starts_its_sessions_delivery_again(
    claimed, tmp_path, monkeypatch, command
):
    """A checkout's init or renewal of a page its session holds makes the checkout
    the session's Leaf, then starts the session's delivery again, since a Codex
    task's adapter running from the former Leaf leaves once another is selected.
    Doing it again changes no selection, so it leaves the running delivery alone."""
    select_another_leaf(tmp_path)
    started = deliveries_started(monkeypatch)
    own = session_runtime_model.own_launcher()

    def take_over():
        if command == "page init":
            vendoring_model.cmd_init(claimed)
        else:
            vendored_at_another_protocol(claimed)
            vendoring_model.renew_layer(
                claimed, harness_model.session_harness(), command=True
            )

    take_over()
    assert started == [own]
    take_over()
    assert started == [own]
