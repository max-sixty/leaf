"""The revision the user was last shown, which the page marks its changes since.

A `seen` event names the live revision a visible tab presented (`events.md`, "Read
state"); the served state's `seen` is the newest one named, described as the browser
fetches it (`read_state.seen_revision`, `PageRead.descriptor`)."""

import pytest
from interact_support import append_command, served_state_error

from leaf import event_log as events_model
from leaf import revisioning as revisioning_model
from leaf.event_log import EventRefused
from leaf.served_state.page import full_state


def served(page_dir):
    state = full_state(page_dir, events_model.read_events(page_dir))
    assert served_state_error(state["seen"], ("Revision", "null")) is None
    return state


def revise(page_dir, words):
    source = page_dir / "index.html"
    source.write_text(source.read_text().replace("</main>", f"<p>{words}</p></main>"))
    activated = revisioning_model.activate_source(page_dir)
    assert activated.error is None
    return activated.revision


def test_the_page_is_marked_since_the_newest_revision_a_tab_showed(page_dir):
    first = revisioning_model.activate_source(page_dir).revision
    assert served(page_dir)["seen"] is None

    seen = append_command(
        page_dir, {"kind": "seen", "author": "user", "revision": first}
    )
    # Bookkeeping: it wakes no agent and owes no answer.
    assert seen["attention"] is False
    second = revise(page_dir, "A revision the user has not been shown.")

    state = served(page_dir)
    assert state["seen"]["revision"] == first
    # The browser fetches the base document from the revision's own address.
    assert state["seen"]["url"].startswith(f"/revisions/r{first}-")
    assert state["active"]["revision"] == second

    append_command(page_dir, {"kind": "seen", "author": "user", "revision": second})
    # A tab still showing the older revision moves nothing back.
    append_command(page_dir, {"kind": "seen", "author": "user", "revision": first})
    assert served(page_dir)["seen"] == served(page_dir)["active"]


def test_a_tab_can_say_it_showed_only_a_revision_the_page_holds(page_dir):
    revisioning_model.activate_source(page_dir)
    with pytest.raises(EventRefused, match="unknown-revision|revision"):
        append_command(page_dir, {"kind": "seen", "author": "user", "revision": 9})
