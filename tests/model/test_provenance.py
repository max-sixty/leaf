"""Which of the user's messages waited while a version was saved, and where each
revision stands in the log (`provenance.py`, `revisioning.py`): what a version says
it was saved after."""

from click.testing import CliRunner
from interact_support import append_command, model_layer, response_reference
from model_folds import leaf_page, served_view

from leaf import cli as cli_model
from leaf import event_log as event_log_model
from leaf.revisioning import activate_source
from model.interact_contract.test_thread_resolution import (
    ASKED,
    CLOSED,
    PICKED,
    SETTLED,
)

AGENT = {"author": "agent", "agent": "Claude", "session": "s1"}
PAGE = {
    revision: leaf_page("Plan", f'<p id="p">Version {revision}.</p>')
    for revision in (1, 2, 3)
}


def live(revision):
    """The `activation` a read appends as the revision goes live."""
    return {
        "kind": "activation",
        "author": "page",
        "revision": revision,
        "publication": f"r{revision}-{revision:016x}",
    }


def waited(message, words, thread=None):
    return {"thread": thread or message, "message": message, "words": words}


def saved_after(events, base, shown, documents=PAGE, registry=None):
    return served_view(documents, events, base, shown, registry=registry)["saved_after"]


def test_a_version_names_what_waited_as_it_read_then_and_nothing_later_moves_it():
    """A version names each message that waited while it was saved, with its opening
    line as it read then, Markdown as it shows. Taking back a rewrite or the comment
    itself after the version went live changes nothing it says; taking either back
    before, or the agent answering before, does."""
    comment = {"kind": "comment", "text": "Make it **blue**\nfor the header"}
    rewrite = {"kind": "edit", "message": "e2", "text": "Make it red"}
    saved = [live(1), comment, rewrite, live(2)]
    assert saved_after(saved, 1, 2) == [waited("e2", "Make it red")]
    taken_back = [
        *saved,
        {"kind": "undo", "undoes": "e3"},
        {"kind": "undo", "undoes": "e2"},
    ]
    assert saved_after(taken_back, 1, 2) == [waited("e2", "Make it red")]
    assert saved_after(
        [live(1), comment, rewrite, {"kind": "undo", "undoes": "e3"}, live(2)], 1, 2
    ) == [waited("e2", "Make it blue")]
    assert (
        saved_after([live(1), comment, {"kind": "undo", "undoes": "e2"}, live(2)], 1, 2)
        == []
    )
    answered = {
        "kind": "reply",
        "parent": "e2",
        "responds": "e2",
        "text": "Blue.",
        **AGENT,
    }
    assert saved_after([live(1), comment, answered, live(2)], 1, 2) == []


def test_a_message_is_quoted_by_the_opening_line_its_thread_shows():
    """A quote is the first line the thread shows of the whole message: a code block's
    first line, not its fence, and a link's words where its reference comes later."""
    code = {"kind": "comment", "text": '```\nprint("check the plan")\n```'}
    link = {"kind": "comment", "text": "See [the plan][1] first\n\n[1]: https://x.test"}
    assert saved_after([code, link, live(2)], 1, 2) == [
        waited("e1", 'print("check the plan")'),
        waited("e2", "See the plan first"),
    ]


def test_a_message_reads_as_it_did_at_the_latest_revision_it_waited_at():
    """A comment that waited across one of a version's revisions, was answered, then
    rewritten and answered again before the version's last revision went live, is
    quoted as it read where it waited, not as it read when the version went live.
    One that waited at two of the version's revisions in different words is quoted
    in the later."""
    comment = {"kind": "comment", "text": "Make it blue"}
    rewrite = {"kind": "edit", "message": "e1", "text": "Make it red"}

    def answer(turn):
        return {
            "kind": "reply",
            "parent": "e1",
            "responds": turn,
            "text": "Done.",
            **AGENT,
        }

    answered_twice = [comment, live(2), answer("e1"), rewrite, answer("e4"), live(3)]
    assert saved_after(answered_twice, 1, 3) == [waited("e1", "Make it blue")]
    waited_twice = [comment, live(2), rewrite, live(3)]
    assert saved_after(waited_twice, 1, 3) == [waited("e1", "Make it red")]
    assert saved_after(waited_twice, 1, 2) == [waited("e1", "Make it blue")]


def test_a_message_waited_where_its_thread_stood_open_at_any_of_the_versions_revisions():
    """A version whose revisions went live while a message waited at any of them names
    it, though it was resolved before the last. Accepting a suggestion closes its
    thread as a resolution does; taking the accept back while the user's resolution
    stands leaves it closed, and taking back a reopening closes it again."""
    resolved = [
        live(1),
        {"kind": "comment", "text": "Why?"},
        live(2),
        {"kind": "resolve", "parent": "e2"},
        live(3),
    ]
    assert saved_after(resolved, 1, 3) == [waited("e2", "Why?")]
    assert saved_after(resolved, 2, 3) == []

    # The suggestions answer `e1`, so the comment comes first.
    pages = {1: SETTLED, 2: SETTLED, 3: SETTLED}
    assert saved_after([ASKED, live(2)], 1, 2, pages) == [
        waited("e1", "cameras are flaky")
    ]
    assert saved_after([ASKED, PICKED, live(2)], 1, 2, pages) == []
    overlapping = [ASKED, PICKED, CLOSED, {"kind": "undo", "undoes": "e2"}, live(2)]
    assert saved_after(overlapping, 1, 2, pages) == []
    reopened = [
        ASKED,
        CLOSED,
        {"kind": "unresolve", "parent": "e1"},
        live(2),
        {"kind": "undo", "undoes": "e3"},
        live(3),
    ]
    assert saved_after(reopened, 1, 3, pages) == [waited("e1", "cameras are flaky")]
    assert saved_after(reopened, 2, 3, pages) == []


def test_each_revision_is_judged_by_the_log_before_it():
    """Who waited at each of a version's revisions is read from the log up to it: a
    comment taken back after one revision went live waited there, and a rewrite taken
    back after it is quoted, for it was what waited."""
    undone_comment = [
        live(1),
        {"kind": "comment", "text": "Why?"},
        live(2),
        {"kind": "undo", "undoes": "e2"},
        live(3),
    ]
    assert saved_after(undone_comment, 1, 3) == [waited("e2", "Why?")]
    assert saved_after(undone_comment, 2, 3) == []
    undone_rewrite = [
        {"kind": "comment", "text": "Make it blue"},
        {"kind": "edit", "message": "e1", "text": "Make it red"},
        live(2),
        {"kind": "reply", "parent": "e1", "responds": "e2", "text": "Red.", **AGENT},
        {"kind": "undo", "undoes": "e2"},
        live(3),
    ]
    assert saved_after(undone_rewrite, 1, 3) == [waited("e1", "Make it red")]


def test_each_revision_is_read_under_the_document_live_there():
    """A choice closes a comment's thread; the next version restates the chosen
    option, which reopens it, so the comment waits as the version after it goes live.
    A later version moving the option into another group changes nothing an earlier
    comparison says, since each revision's place is read under its own document."""
    registry = model_layer()
    registry["lf-options"]["properties"]["resolves"] = {"type": "string"}
    first = leaf_page(
        "Options",
        '<lf-options id="picks" choose resolves="e2">'
        '<lf-option id="option-a">A</lf-option><lf-option id="option-b">B</lf-option>'
        '</lf-options><lf-options id="other"><lf-option id="option-c">C</lf-option>'
        "</lf-options>",
    )
    second = first.replace('id="option-a"', 'id="option-a" restated').replace(
        ">A<", ">A reconsidered<"
    )
    third = second.replace(">A reconsidered<", ">A reconsidered again<")
    moved = '<lf-option id="option-a" restated>A reconsidered again</lf-option>'
    fourth = third.replace(moved, "").replace(
        '<lf-options id="other">', f'<lf-options id="other">{moved}'
    )
    events = [
        live(1),
        {"kind": "comment", "text": "Please reconsider A"},
        {
            "kind": "action",
            "widget": "picks",
            "action": "choose",
            "detail": {"value": ["option-a"]},
        },
        {
            "kind": "note",
            "revision": 2,
            "version": 1,
            "text": "Reconsider A",
            "restated": ["option-a"],
            **AGENT,
        },
        live(2),
        live(3),
    ]
    asked = [waited("e2", "Please reconsider A")]
    documents = {1: first, 2: second, 3: third}
    assert saved_after(events, 2, 3, documents, registry) == asked
    documents = {**documents, 4: fourth}
    assert saved_after([*events, live(4)], 2, 3, documents, registry) == asked


def test_a_comparison_across_a_stamped_version_says_nothing():
    """Nothing knows which of several versions made a change."""
    stamped = [
        live(1),
        live(2),
        {"kind": "note", "version": 1, "revision": 2, "text": "Two.", **AGENT},
        live(3),
    ]
    assert saved_after(stamped, 1, 3) is None
    assert saved_after(stamped, 2, 3) == []
    assert served_view(PAGE, stamped, 2)["saved_after"] is None


def test_a_revision_takes_its_place_in_the_log_from_the_event_naming_its_bundle(
    page_dir,
):
    """A save a read activates appends an `activation` naming its bundle, after every
    event before it, however old a revision a message names; a save a reply publishes
    takes the reply's place, the end of the wait it answers."""
    index = page_dir / "index.html"
    said = ["Ship dark."]

    def save(words):
        index.write_text(index.read_text().replace(said[-1], words, 1))
        said.append(words)

    def place(revision):
        [named] = [
            event
            for event in event_log_model.read_events(page_dir)
            if event.get("publication") and event["revision"] == revision
        ]
        return named["seq"]

    first = activate_source(page_dir).revision
    save("Ship dark, behind a flag.")
    unread = activate_source(page_dir).revision
    asked = append_command(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": first,
            "text": "Which flag?",
            "anchor": {"section": "plan"},
        },
    )
    assert place(unread) < asked["seq"]
    save("Ship dark, behind the rollout flag.")
    assert place(activate_source(page_dir).revision) > asked["seq"]

    save("Ship dark, behind the rollout flag, off by default.")
    replied = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, asked),
            "--text",
            "The rollout flag, off by default.",
        ],
        catch_exceptions=False,
    )
    assert replied.exit_code == 0, replied.output
    [reply] = [
        event
        for event in event_log_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    assert place(reply["revision"]) == reply["seq"]
