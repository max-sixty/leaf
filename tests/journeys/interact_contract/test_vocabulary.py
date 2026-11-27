"""Tests scheduled by the measured cost of their boundary."""

import json

from interact_support import append_carried_log_record, append_command, publish
from model.interact_contract import _stateful_page_declaration

from leaf.agents import thread as thread_model
from leaf.base import files as files_model
from leaf.records import revisioning as revisioning_model


def test_candidate_vocabulary_can_change_after_thread_widget_actions(page_dir):
    """A thread widget keeps the contract under which its user command was admitted."""
    authored = page_dir / "page" / "registry.json"
    declaration = _stateful_page_declaration(page_dir, "lf-thread-local")
    authored.write_text(json.dumps({"lf-thread-local": declaration}))
    publish(page_dir)
    revision = files_model.latest_revision(page_dir)
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "Choose."},
    )
    thread_model.post_reply(
        page_dir,
        {"parent": "c1", "responds": "c1"},
        "Use this control.\n\n"
        '<lf-thread-local id="thread-choice" value="author">Local</lf-thread-local>',
    )
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": revision,
            "widget": "thread-choice",
            "action": "first",
            "detail": {"value": "user"},
        },
    )
    declaration["verbs"]["second"] = declaration["verbs"].pop("first")
    authored.write_text(json.dumps({"lf-thread-local": declaration}))

    refused = revisioning_model.activate_source(page_dir)

    assert refused.error is None and refused.created
    assert revision is not None
    assert refused.revision == revision + 1
