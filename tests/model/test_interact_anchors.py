"""File-side anchor and thread-projection tests."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import hooks_run_this_tree
from interact_support import (
    DRAFTED,
    FLOW_PAGE,
    PAGE,
    PAGE_GROUP,
    SUGGESTED,
    append_carried_log_record,
    append_command,
    before_choice,
    check_findings,
    command_findings,
    comment,
    decide,
    drafted,
    edit,
    found,
    obligations_on_user,
    owed_answers,
    page_state,
    publish,
    published,
    refused_on,
    response_reference,
    stamp,
    state_json,
    suggested,
    thread_records,
    with_modules,
)

from leaf.agents.delivery import current_responses
from leaf.base import files as files_model
from leaf.commands import cli as cli_model
from leaf.commands import hook_transport as hook_transport_model
from leaf.log import event_log as events_model
from leaf.log.events import build_threads
from leaf.log.thread_context import logged_fragment
from leaf.pages.render_gate import browser as browser_model
from leaf.records import render_reading as render_reading_model
from leaf.records.revisioning import activate_source
from leaf.source import passages as passages_model
from leaf.source import structure as structure_model
from leaf.source.anchor_capture import Drawing, drawn_part
from leaf.source.data import read_data
from leaf.source.revision_artifact import read_artifact, read_revision


def unplaced(result) -> int | None:
    """How many times Leaf's reading of the page's files found a posted thread's
    quote, where it noted that it didn't find it once (`unplaced-quote`), else None."""
    assert result.exit_code == 0, result.output
    notes = [
        finding["values"]["found"]
        for finding in json.loads(result.output).get("findings", [])
        if finding["code"] == "unplaced-quote"
    ]
    return notes[0] if notes else None


def undelivered(page_dir, input_id: str) -> str:
    """How a refusal names the answer to an input no receipt has carried, on a page
    this session has not claimed: no reference exists yet, so it names the wait that
    delivers one, after the claim that wait's receipt needs."""
    return (
        "`leaf thread reply <answer.ref>` with the `answer.ref` that "
        f"`leaf wait {page_dir}` delivers for {input_id} (`leaf page claim "
        f"{page_dir}` first, since this session does not hold the page)"
    )


def test_an_explicit_line_break_separates_quoted_words():
    document = structure_model.SourceDocument(
        "<main><p id='line'>Short label here<br>Then a second line.</p></main>"
    )
    assert passages_model.page_passages(document).text == (
        "Short label here Then a second line."
    )


def test_an_edge_shows_no_space_before_a_closing_mark_or_after_an_opening_one():
    """Outside a text block, two elements' words that meet show a space, as a chip beside
    its title or a title above its description is drawn, but none before a closing mark
    or after an opening one, so `leaf page state` reads an inline title's sentence as its
    author punctuated it. A straight quote opening a title is no closing mark, so the
    chip before it still reads apart. The runtime's `says` shows the same words."""
    document = structure_model.SourceDocument(
        '<main><lf-option id="punctuated"><strong>Leave it</strong>; the send keeps '
        "<code>Foo</code>'s place (<code>beta</code>).</lf-option>"
        '<lf-option id="chipped"><small class="lf-tag">recommended</small>'
        "<strong>Apply</strong>Ship it.</lf-option>"
        '<lf-option id="quoted"><small class="lf-tag">recommended</small>'
        '<strong>"Update" for mixed input</strong></lf-option></main>'
    )
    assert passages_model.page_passages(document).text == (
        "Leave it; the send keeps Foo's place (beta). recommended Apply Ship it. "
        'recommended "Update" for mixed input'
    )


def test_a_whitespace_quote_refuses_instead_of_searching_forever(page_dir):
    result = comment(
        published(page_dir), "--quote", " \t\n ", "--text", "Which passage?"
    )
    assert result.exit_code != 0, result.output
    assert refused_on(result.output).code == "unanchorable"
    assert not any(
        event["kind"] == "comment" for event in events_model.read_events(page_dir)
    )


def test_detached_capture_remains_detached_when_an_identical_copy_survives(page_dir):
    """A revision moves no quote: a selection captured as detached stays detached
    when a revision leaves one copy of its words, and an agent's quote of words the
    files hold several times is stored with a note on where the page shows it."""
    repeated = "<p>Repeated passed text.</p>"
    unique = "<p>Unique passed text.</p>"
    original = PAGE.replace(
        "<h2>Plan</h2>",
        '<h2>Plan</h2><section id="runs">' + repeated * 2 + unique + "</section>",
    )
    (page_dir / "index.html").write_text(original)
    publish(page_dir)
    noted = comment(
        page_dir, "--section", "runs", "--quote", "passed", "--text", "Which?"
    )
    assert noted.exit_code == 0, noted.output
    record = json.loads(noted.output)
    assert record["anchor"] == {"section": "runs", "quote": "passed"}
    [note] = record["findings"]
    assert note["code"] == "unplaced-quote" and note["values"]["found"] == 3
    anchor = {
        "section": "runs",
        "quote": "passed",
        "prefix": "Repeated",
        "suffix": "text.",
        "detached": True,
    }
    detached = append_command(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": anchor,
            "text": "The selected second occurrence.",
        },
    )
    exact = json.loads(
        comment(
            page_dir,
            "--section",
            "runs",
            "--quote",
            "Unique passed text.",
            "--text",
            "Unique.",
        ).output
    )
    assert exact["anchor"] == {"section": "runs", "quote": "Unique passed text."}
    assert "findings" not in exact
    revised = original.replace(repeated * 2 + unique, repeated + unique)
    (page_dir / "index.html").write_text(revised)
    publish(page_dir)
    threads = build_threads(events_model.read_events(page_dir), {})
    assert threads[detached["id"]]["anchor"] == anchor
    assert threads[exact["id"]]["anchor"] == exact["anchor"]


def test_comment_anchors_on_a_quote_and_posts_as_agent(page_dir, sessionless):
    result = comment(
        published(page_dir), "--quote", "Ship dark", "--text", "dark for how long?"
    )
    assert result.exit_code == 0, result.output
    event = json.loads(result.output)
    assert (
        event["kind"] == "comment"
        and event["author"] == "agent"
        and event["revision"] == 1
    )
    # A bare run has no harness session behind it, so the event carries no voice
    # fields — users' generic label covers it — rather than a stored
    # placeholder wearing a name.
    assert "agent" not in event and "session" not in event
    assert event["anchor"]["quote"] == "Ship dark"
    # The section is derived the way the browser derives it — the nearest enclosing id.
    assert event["anchor"]["section"] == "flag-first"
    assert event["text"] == "dark for how long?"


def test_a_written_comment_quotes_the_whole_passage(page_dir):
    """A quote is the passage the page marks, so the capture writes the whole of it
    however long. Cut at four hundred characters, the comment landed on the passage's
    opening."""
    passage = (
        "The cutoff moves whenever the backfill runs, and the guard reads a column "
        "the writer never fills, so the batch replays from the top on each release, "
        "and the counters disagree with the log and with each other, and the retry "
        "budget is spent long before anyone looks at it, and the operator reads the "
        "dashboard at noon and files the incident against the wrong service, and "
        "the runbook it links still names a host that was retired last spring."
    )
    assert len(passage) > 400, "the fixture no longer outruns the old cap"
    long = PAGE.replace(
        "</section>",
        f"  <p>{passage}</p>\n  <p>Deploys pause overnight.</p>\n</section>",
    )
    (page_dir / "index.html").write_text(long)
    event = json.loads(
        comment(published(page_dir), "--quote", passage, "--text", "x").output
    )
    assert event["anchor"] == {"section": "plan", "quote": passage}


def test_a_quote_the_files_do_not_hold_posts_with_a_note(page_dir):
    """Only the drawn page says whether it shows the words, so the quote is stored
    as given, on no section, and the note says where the page shows the thread if it
    doesn't show them once either."""
    result = comment(published(page_dir), "--quote", "ship it on Friday", "--text", "x")
    assert unplaced(result) == 0
    assert json.loads(result.output)["anchor"] == {
        "section": None,
        "quote": "ship it on Friday",
    }
    assert "in Threads" in result.output


def test_a_quote_the_files_hold_twice_posts_with_a_note(page_dir):
    """The words repeat and the anchor names no section, so the note says the thread
    stands in Threads unless the drawn page shows them once; a section that holds one
    copy places the thread on it with no note."""
    twice = PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>\n  <p>Ship dark.</p>")
    (page_dir / "index.html").write_text(twice)
    result = comment(published(page_dir), "--quote", "Ship dark", "--text", "x")
    assert unplaced(result) == 2
    assert json.loads(result.output)["anchor"] == {
        "section": None,
        "quote": "Ship dark",
    }
    assert "in Threads" in result.output and "--section" not in result.output
    scoped = comment(
        page_dir, "--quote", "Ship dark", "--section", "flag-first", "--text", "x"
    )
    assert unplaced(scoped) is None
    assert json.loads(scoped.output)["anchor"] == {
        "section": "flag-first",
        "quote": "Ship dark",
    }


def test_a_section_the_version_has_no_id_for_is_refused(page_dir):
    """The first gate on a written anchor, and the one a typo meets. An id the version
    doesn't hold reaches nobody in the browser — the runtime looks the element up and
    finds nothing — so it is refused here, where the writer can still fix it, rather
    than posting a comment that arrives pointing at the page's edge."""
    result = comment(published(page_dir), "--section", "backfil-first", "--text", "x")
    assert result.exit_code != 0
    assert "no element id 'backfil-first'" in result.output


def test_a_section_handed_a_message_id_is_sent_to_the_option_that_takes_one(page_dir):
    """The CLI names several kinds of id with bare strings, and only the log says which
    namespace a value came from. An agent holding the id of the comment it is answering
    reaches for `--section`, and `no element id` alone leaves it guessing at the page's
    markup for an id that was never going to be there. So the refusal names the writer
    that settles what the log still owes for the value."""
    root = append_carried_log_record(
        published(page_dir),
        {"kind": "comment", "author": "user", "text": "how long?"},
    )
    mistaken = comment(
        page_dir,
        "--section",
        root["id"],
        "--text",
        "answering the comment I was handed",
    )
    assert mistaken.exit_code != 0
    assert f"no element id {root['id']!r}" in mistaken.output
    assert (
        f"{root['id']} is a comment in this page's log — "
        f"{undelivered(page_dir, root['id'])} answers it"
    ) in mistaken.output
    assert all(event["kind"] != "reply" for event in events_model.read_events(page_dir))


def test_a_section_handed_a_message_owed_nothing_is_sent_to_its_thread(page_dir):
    """A message the log owes nothing still names its thread to `leaf thread reply`.
    Proactive replies name PAGE MESSAGE when nothing is owed; the diagnostic
    must provide a route the writer can take."""
    own = json.loads(
        comment(published(page_dir), "--quote", "Ship dark", "--text", "note").output
    )
    mistaken = comment(page_dir, "--section", own["id"], "--text", "more")
    assert mistaken.exit_code != 0
    route = f"`leaf thread reply <page> {own['id']}` replies to it"
    assert (
        f"{own['id']} is a comment in this page's log, and nothing is owed for it — "
        f"{route}"
    ) in mistaken.output

    followed = CliRunner().invoke(
        cli_model.cli,
        ["thread", "reply", str(page_dir), own["id"], "--text", "more"],
    )
    assert followed.exit_code == 0, followed.output


def test_a_message_whose_thread_owes_a_reply_is_sent_to_its_delivery_reference(
    page_dir,
):
    """A diagnostic on any message names the delivery route for the thread's
    exact owed input; a proactive reply cannot infer that input, so it answers
    nothing and its note names the route too."""
    own = json.loads(
        comment(published(page_dir), "--quote", "Ship dark", "--text", "note").output
    )
    asked = append_carried_log_record(
        page_dir,
        {"kind": "reply", "author": "user", "parent": own["id"], "text": "how long?"},
    )

    mistaken = comment(page_dir, "--section", own["id"], "--text", "more")
    assert mistaken.exit_code != 0
    assert (
        f"{own['id']} is a comment in this page's log, and its thread is owed "
        f"a reply — {undelivered(page_dir, asked['id'])} answers it"
    ) in mistaken.output

    # The writer the refusal names takes it, and the one it passed over says so too.
    posted = CliRunner().invoke(
        cli_model.cli,
        ["thread", "reply", str(page_dir), own["id"], "--text", "more"],
    )
    assert posted.exit_code == 0, posted.output
    [owed] = json.loads(posted.stdout)["findings"]
    assert f"{undelivered(page_dir, asked['id'])} answers it" in owed["text"]
    answered = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, asked["id"]),
            "--text",
            "a week",
        ],
    )
    assert answered.exit_code == 0, answered.output


def test_a_section_handed_a_settled_move_is_told_nothing_is_owed(page_dir):
    """A route is only worth naming where the writer it names takes the value. What a
    writer takes is what the log still owes, not the event's kind: a resolve is owed
    nothing, so sending the agent to an addressed reply hands it a second refusal with no
    route at all."""
    root = append_carried_log_record(
        published(page_dir),
        {"kind": "comment", "author": "user", "text": "how long?"},
    )
    resolved = CliRunner().invoke(
        cli_model.cli, ["thread", "resolve", str(page_dir), root["id"]]
    )
    assert resolved.exit_code == 0, resolved.output
    settled = events_model.read_events(page_dir)[-1]
    assert settled["kind"] == "resolve"

    mistaken = comment(page_dir, "--section", settled["id"], "--text", "hi")
    assert mistaken.exit_code != 0
    assert (
        f"{settled['id']} is a resolve in this page's log, and nothing is owed for it"
    ) in mistaken.output
    assert "--for" not in mistaken.output


def test_a_request_the_user_resolved_is_answered_at_its_reference(page_dir):
    """The user's resolve takes the thread off their list and leaves the request
    owed, so the reply the delivery addressed still answers it, in the thread the
    user closed. The thread stays closed for what the agent says in it, until the
    agent reopens it or asks the user something."""
    root = append_carried_log_record(
        published(page_dir),
        {"kind": "comment", "author": "user", "text": "Can you check this?"},
    )
    reference = response_reference(page_dir, root["id"])
    append_carried_log_record(
        page_dir,
        {"kind": "resolve", "author": "user", "parent": root["id"]},
    )
    assert [item["input"] for item in owed_answers(page_dir)] == [root["id"]]
    misplaced = comment(page_dir, "--section", root["id"], "--text", "I checked it.")
    assert "answers it" in misplaced.output
    assert "resolved the thread" not in misplaced.output

    answered = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            reference,
            "--text",
            "I checked it.",
            "--title",
            "Thread title",
        ],
    )

    assert answered.exit_code == 0, answered.output
    events = events_model.read_events(page_dir)
    assert events[-1]["responds"] == root["id"]
    assert owed_answers(page_dir) == []
    [thread] = state_json(page_dir)["threads"]
    assert thread["resolved"] == "user"

    def says(*flags):
        said = CliRunner().invoke(
            cli_model.cli,
            ["thread", "reply", str(page_dir), root["id"], "--text", "More.", *flags],
        )
        assert said.exit_code == 0, said.output
        [thread] = state_json(page_dir)["threads"]
        return thread["resolved"], events_model.read_events(page_dir)[-1].get(
            "unannounced"
        )

    assert says() == ("user", True)
    # The agent's own resolve on top of the user's changes nothing for a later
    # message, which still goes in unannounced.
    resolved = CliRunner().invoke(
        cli_model.cli, ["thread", "resolve", str(page_dir), root["id"]]
    )
    assert resolved.exit_code == 0, resolved.output
    assert says() == ("agent", True)
    # A question brings the thread back by itself.
    assert says("--obligation") == (None, None)
    append_carried_log_record(
        page_dir, {"kind": "resolve", "author": "user", "parent": root["id"]}
    )
    # A message that stays closed says so beside its record, with the command that
    # brings the thread back, which is the agent's call.
    quiet = CliRunner().invoke(
        cli_model.cli,
        ["thread", "reply", str(page_dir), root["id"], "--text", "It can't be done."],
    )
    said = events_model.read_events(page_dir)[-1]
    assert said["unannounced"]
    assert f"leaf thread reopen {page_dir} {said['id']}" in quiet.output
    reopened = CliRunner().invoke(
        cli_model.cli, ["thread", "reopen", str(page_dir), said["id"]]
    )
    assert reopened.exit_code == 0, reopened.output
    [thread] = state_json(page_dir)["threads"]
    assert (thread["resolved"], thread["unread"]) == (None, [said["id"]])
    assert says() == (None, None)


def test_the_result_of_promised_work_stays_in_the_thread_the_user_closed(page_dir):
    """The agent answers a request the user resolved its thread over with a promise,
    and later with the result at the same reference, which names no input. Both go
    into the thread without reopening it."""
    root = append_carried_log_record(
        published(page_dir),
        {"kind": "comment", "author": "user", "text": "Can you check this?"},
    )
    reference = response_reference(page_dir, root["id"])
    append_carried_log_record(
        page_dir,
        {"kind": "resolve", "author": "user", "parent": root["id"]},
    )
    for text, flags in (("On it.", ["--todo", "Check it"]), ("Checked.", ["--done"])):
        said = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                reference,
                "--text",
                text,
                *flags,
                "--title",
                "Thread title",
            ],
        )
        assert said.exit_code == 0, said.output
        [thread] = state_json(page_dir)["threads"]
        assert thread["resolved"] == "user"
    assert "responds" not in events_model.read_events(page_dir)[-1]


def test_a_reply_refused_after_the_agents_resolution_names_the_resolution(page_dir):
    """The agent's own resolve answers for its thread, and an agent whose delivered
    reply became unnecessary should know why."""
    root = append_carried_log_record(
        published(page_dir),
        {"kind": "comment", "author": "user", "text": "Can you check this?"},
    )
    reference = response_reference(page_dir, root["id"])
    resolution = append_carried_log_record(
        page_dir,
        {"kind": "resolve", "author": "agent", "parent": root["id"]},
    )

    refused = CliRunner().invoke(
        cli_model.cli,
        ["thread", "reply", "--done", reference, "--text", "I checked it."],
    )

    assert refused.exit_code != 0
    assert "the agent resolved the thread" in refused.output
    assert resolution["ts"] in refused.output
    assert "leaf thread reply" not in refused.output
    misplaced = comment(page_dir, "--section", root["id"], "--text", "I checked it.")
    assert "the agent resolved the thread" in misplaced.output
    assert "leaf thread reply" not in misplaced.output
    # The user closing the thread after the agent leaves the agent's resolve
    # answering for it, and the refusal still names that one.
    append_carried_log_record(
        page_dir, {"kind": "resolve", "author": "user", "parent": root["id"]}
    )
    again = comment(page_dir, "--section", root["id"], "--text", "I checked it.")
    assert "the agent resolved the thread" in again.output
    assert not any(e["kind"] == "reply" for e in events_model.read_events(page_dir))


def test_a_section_handed_a_delivered_move_names_the_option_for_one(page_dir):
    """A message is not the only id an agent is handed. A user's press on a widget
    in a reply is answered through its exact delivery reference. The
    diagnostic must name that response route for the action rather than treating
    its event id as a page element or a proactive thread destination."""
    publish(page_dir)
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "Choose?"},
    )
    ask = (
        '<lf-group id="thread-ask" label="Choose one">\n<h2 id="thread-ask-h">Choose one</h2>'
        '<lf-options id="thread-picks"><lf-option id="thread-option">'
        "Thread option</lf-option></lf-options></lf-group>"
    )
    answered = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, "c1"),
            "--text",
            f"Which?\n\n{ask}",
            "--title",
            "Thread title",
        ],
    )
    assert answered.exit_code == 0, answered.output
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": files_model.latest_revision(page_dir),
            "widget": "thread-picks",
            "action": "choose",
            "detail": {"value": ["thread-option"]},
            "answered": True,
        },
    )
    events = events_model.read_events(page_dir)
    pressed = next(event for event in events if event["kind"] == "action")
    assert (
        current_responses(page_dir, events)[pressed["id"]]["responds"] == pressed["id"]
    )
    mistaken = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, pressed["id"]),
            "--section",
            pressed["id"],
            "--text",
            "answering the press I was handed",
        ],
    )
    assert mistaken.exit_code != 0
    assert (
        f"{pressed['id']} is an action in this page's log — "
        f"{undelivered(page_dir, pressed['id'])} answers it"
    ) in mistaken.output
    assert "`leaf thread reply <page> <id>`" not in mistaken.output


def test_a_section_scopes_where_a_quote_may_land(page_dir):
    """Naming a section is one of the two ways out of the ambiguity message, so it has
    to be a bound and not a label: the words go in the anchor's section field, and the
    browser then searches inside that element alone. A quote the page holds elsewhere is not a quote
    this section says, and taking it would write a comment whose two halves disagree —
    a section that doesn't hold the passage the quote names, which is exactly the claim
    the file's reading may never make on the page's behalf."""
    elsewhere = comment(
        published(page_dir),
        "--quote",
        "Verify, then flip",
        "--section",
        "flag-first",
        "--text",
        "x",
    )
    # Named as the section's silence, not the page's: the page does say it, one option over.
    assert unplaced(elsewhere) == 0
    assert "in § flag-first" in elsewhere.output
    held = comment(
        page_dir,
        "--quote",
        "Verify, then flip",
        "--section",
        "backfill-first",
        "--text",
        "x",
    )
    assert unplaced(held) is None
    assert json.loads(held.output)["anchor"]["section"] == "backfill-first"


def test_a_widgets_data_body_is_not_quotable_but_the_widget_is(page_dir):
    """A diagram's source is a picture by the time the user sees it, so quoting the
    source anchors on text no search will find. Pointing at the element is what a click
    on that diagram does in the browser, and that is the anchor offered instead."""
    (page_dir / "index.html").write_text(FLOW_PAGE)
    body = comment(published(page_dir), "--quote", "graph LR", "--text", "x")
    assert unplaced(body) == 0 and "in Threads" in body.output
    element = comment(
        page_dir, "--section", "flow", "--text", "the retry edge is missing"
    )
    assert element.exit_code == 0, element.output
    assert json.loads(element.output)["anchor"] == {"section": "flow"}


BOX_A = {"id": "node:A", "label": "A"}
BOX_B = {"id": "node:B", "label": "B"}


def leave_drawing(page_dir: Path, visuals: dict[str, dict]) -> None:
    """The render reading a check of the live version leaves, with the data the page
    holds and what each visual drew (`visuals`)."""
    revision = files_model.latest_revision(page_dir)
    assert revision is not None
    data = read_data(page_dir, read_revision(page_dir, revision).registry)
    render_reading_model.write_reading(
        page_dir, read_artifact(page_dir, revision).digest, data["version"], [], visuals
    )


def noted(result) -> list[str]:
    """What a command that succeeded said beside its record."""
    assert result.exit_code == 0, result.output
    return [found["text"] for found in json.loads(result.output).get("findings", [])]


def test_a_part_is_one_its_visual_drew(page_dir):
    """`--part` takes a box the page's last render check saw the diagram draw. A
    diagram shows a thread on a box it didn't draw nowhere, so a box it lacks is
    refused, naming the boxes it drew and the way to put the thread on the whole
    diagram."""
    (page_dir / "index.html").write_text(FLOW_PAGE)
    published(page_dir)
    leave_drawing(page_dir, {"flow": {"parts": [BOX_A, BOX_B], "whole": False}})

    named = comment(
        page_dir, "--section", "flow", "--part", "node:A", "--text", "this retry?"
    )
    assert noted(named) == []
    assert json.loads(named.output)["anchor"] == {"section": "flow", "visual": "node:A"}

    undrawn = comment(page_dir, "--section", "flow", "--part", "node:C", "--text", "x")
    assert undrawn.exit_code != 0
    assert (
        "§ flow drew no part 'node:C' when the page was last checked; it drew node:A,"
        " node:B. Name one of those, or leave out --part to put the thread on the whole"
        " visual"
    ) in undrawn.output

    unseated = comment(page_dir, "--part", "node:A", "--text", "x")
    assert unseated.exit_code != 0
    assert "--part needs --section" in unseated.output


CHECKED = "when the page was last checked"


@pytest.mark.parametrize(
    ("parts", "whole", "part", "said"),
    [
        pytest.param([BOX_A, BOX_B], False, "node:A", None, id="drawn"),
        pytest.param(
            [BOX_A],
            True,
            "node:C",
            "§ flow drew no part 'node:C' when the page was last checked, so the"
            " thread stands on the whole visual until the visual draws that part; it"
            " drew node:A",
            id="on-the-whole",
        ),
        pytest.param([], True, "node:C", None, id="lists-none-and-finds-by-id"),
        pytest.param(
            [BOX_A, BOX_B],
            False,
            "node:C",
            "refused: § flow drew no part 'node:C' when the page was last checked; it"
            " drew node:A, node:B. Name one of those, or leave out --part to put the"
            " thread on the whole visual",
            id="nowhere",
        ),
        pytest.param(
            [],
            False,
            "node:C",
            "refused: § flow drew no part 'node:C' when the page was last checked; it"
            " drew no part at all. Leave out --part to put the thread on the whole"
            " visual",
            id="nowhere-and-drew-none",
        ),
    ],
)
def test_a_part_is_judged_by_where_the_page_would_show_its_thread(
    parts, whole, part, said
):
    """A part the visual drew takes the thread. One it didn't takes it where the page
    would show it: on the whole visual, for a visual that draws a part on request or
    once it can (`whole`), with a note naming the parts it drew, or without one where
    it lists none, as a chart lists none of the points it finds by id; and nowhere,
    for any other visual, so the part is refused with the way to put the thread on the
    whole visual."""
    drawing = Drawing({"flow": {"parts": parts, "whole": whole}}, CHECKED)
    try:
        found = drawn_part("flow", part, drawing)
    except ValueError as refusal:
        outcome = f"refused: {refusal}"
    else:
        outcome = None if found is None else str(found)
    assert outcome == said


def test_a_part_no_browser_could_check_is_taken_with_a_note(
    page_dir, monkeypatch, tmp_path
):
    """Where no render check has read the version the page shows, `--part` draws the
    page to see what its visual draws. Where no browser can, the command takes any part
    the visual declares, which it may draw, and says it didn't check it."""
    for variable in browser_model.VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv(browser_model.VARIABLE, str(tmp_path / "not-a-browser"))
    (page_dir / "index.html").write_text(FLOW_PAGE)
    published(page_dir)

    unchecked = comment(
        page_dir, "--section", "flow", "--part", "node:C", "--text", "x"
    )
    assert noted(unchecked) == [
        "Leaf couldn't read what § flow draws, so it didn't check part 'node:C'"
    ]
    assert json.loads(unchecked.output)["anchor"] == {
        "section": "flow",
        "visual": "node:C",
    }


def test_reply_replacement_precedes_automatic_fallback_for_other_threads(page_dir):
    original = PAGE.replace(
        "<h2>Plan</h2>", '<h2>Plan</h2><p id="wording">Alpha and Gamma</p>'
    )
    (page_dir / "index.html").write_text(original)
    publish(page_dir)
    roots = [
        json.loads(comment(page_dir, "--quote", q, "--text", q).output)
        for q in ("Alpha", "Gamma")
    ]
    (page_dir / "index.html").write_text(
        original.replace("Alpha and Gamma", "Beta and Delta")
    )
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            roots[0]["id"],
            "--quote",
            "Beta",
            "--text",
            "Revised this.",
        ],
    )
    assert result.exit_code == 0, result.output
    reply = json.loads(result.stdout)
    assert reply["anchor"]["quote"] == "Beta"
    # The reply tells its author where the revision moved the thread it left alone.
    [moved] = json.loads(result.stdout).get("findings", [])
    assert (moved["code"], moved["values"]) == (
        "relocated-anchor",
        {"thread": roots[1]["id"], "section": "wording"},
    )
    threads = {t["id"]: t for t in state_json(page_dir)["threads"]}
    assert threads[roots[0]["id"]]["anchor"] == reply["anchor"]
    assert threads[roots[1]["id"]]["anchor"] == {"section": "wording"}
    moves = [e for e in events_model.read_events(page_dir) if e["kind"] == "reanchor"]
    assert [e["thread"] for e in moves] == [roots[1]["id"]]


def test_a_revision_moves_a_comment_on_a_formatted_label_to_its_section(page_dir):
    """The browser captures a passage's context as the page shows it, a chip's label
    apart from the formatted title beside it, so the file reads the revision's
    predecessor the same way and sees the passage leave."""
    from leaf.records.revisioning import activate_source

    labels = (
        '<div id="labels"><small>MARK</small><strong><em>one</em></strong>'
        " <small>MARK</small><strong><em>two</em></strong></div>"
    )
    original = PAGE.replace("<h2>Plan</h2>", f"<h2>Plan</h2>{labels}")
    (page_dir / "index.html").write_text(original)
    publish(page_dir)
    root = append_command(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {
                "section": "labels",
                "quote": "MARK",
                "prefix": "Plan",
                "suffix": "one MARK two",
            },
            "text": "Rename this one.",
        },
    )
    (page_dir / "index.html").write_text(original.replace("MARK", "TERM"))
    assert activate_source(page_dir).created
    threads = build_threads(events_model.read_events(page_dir), {})
    assert threads[root["id"]]["anchor"] == {"section": "labels"}


def test_a_reply_names_the_threads_a_save_already_moved(page_dir):
    """The server activates a valid save before anyone checks it, so the moves are
    in the log by then. `page check` still names every thread the active revision
    moved, and so does the reply, except the one it moves itself."""
    from leaf.records.revisioning import activate_source

    original = PAGE.replace(
        "<h2>Plan</h2>", '<h2>Plan</h2><p id="wording">Alpha and Gamma</p>'
    )
    (page_dir / "index.html").write_text(original)
    publish(page_dir)
    roots = [
        json.loads(comment(page_dir, "--quote", q, "--text", q).output)
        for q in ("Alpha", "Gamma")
    ]
    (page_dir / "index.html").write_text(
        original.replace("Alpha and Gamma", "Beta and Delta")
    )
    assert activate_source(page_dir).created

    def checked():
        result = CliRunner().invoke(cli_model.cli, ["page", "check", str(page_dir)])
        assert result.exit_code == 0, result.output
        return [
            finding["values"]
            for finding in json.loads(result.stdout)["findings"]
            if finding["code"] == "relocated-anchor"
        ]

    assert checked() == [{"thread": root["id"], "section": "wording"} for root in roots]

    def reply(*options):
        result = CliRunner().invoke(
            cli_model.cli,
            ["thread", "reply", str(page_dir), roots[0]["id"], *options],
        )
        assert result.exit_code == 0, result.output
        return json.loads(result.stdout).get("findings", [])

    [moved] = reply("--quote", "Beta", "--text", "Revised this.")
    assert (moved["code"], moved["values"]) == (
        "relocated-anchor",
        {"thread": roots[1]["id"], "section": "wording"},
    )
    assert reply("--text", "And checked it.") == []
    # The reply placed the first thread itself, so only the second still stands
    # where the move put it.
    assert checked() == [{"thread": roots[1]["id"], "section": "wording"}]

    # Two saves move the first thread twice before the next reply, which names each
    # thread once, where it stands now.
    (page_dir / "index.html").write_text(
        original.replace("Alpha and Gamma", "Beta and Epsilon")
    )
    assert activate_source(page_dir).created
    (page_dir / "index.html").write_text(
        original.replace('<p id="wording">Alpha and Gamma</p>', "")
    )
    assert activate_source(page_dir).created
    assert [moved["values"] for moved in reply("--text", "Removed the wording.")] == [
        {"thread": roots[0]["id"], "section": None},
        {"thread": roots[1]["id"], "section": None},
    ]


def test_page_check_names_no_move_of_a_withdrawn_reaction(page_dir):
    """A reaction the user took back opens no thread, so a save that moved it
    before the undo leaves `page check` nothing to name."""
    from leaf.records.revisioning import activate_source

    original = PAGE.replace(
        "<h2>Plan</h2>", '<h2>Plan</h2><p id="wording">Alpha and Gamma</p>'
    )
    (page_dir / "index.html").write_text(original)
    publish(page_dir)
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "emoji": "✂️",
            "anchor": {"section": "wording"},
        },
    )
    (page_dir / "index.html").write_text(
        original.replace('<p id="wording">Alpha and Gamma</p>', "")
    )
    assert activate_source(page_dir).created
    assert [
        e["thread"]
        for e in events_model.read_events(page_dir)
        if e["kind"] == "reanchor"
    ] == [root["id"]]
    append_carried_log_record(
        page_dir, {"kind": "undo", "author": "user", "undoes": root["id"]}
    )
    result = CliRunner().invoke(cli_model.cli, ["page", "check", str(page_dir)])
    assert result.exit_code == 0, result.output
    assert "relocated-anchor" not in {
        finding["code"] for finding in json.loads(result.stdout)["findings"]
    }


def test_a_stamp_preserves_threads_its_restatement_reopens(page_dir):
    from leaf.log.events import build_threads

    original = SUGGESTED.replace(
        "<h2>Plan</h2>", '<h2>Plan</h2><p id="wording">Alpha</p>'
    )
    (page_dir / "index.html").write_text(original)
    publish(page_dir)
    root = json.loads(
        comment(page_dir, "--quote", "Alpha", "--text", "Discuss this.").output
    )
    anchored = original.replace(
        '<lf-suggestion id="sug-refill">',
        f'<lf-suggestion id="sug-refill" resolves="{root["id"]}">',
    )
    (page_dir / "index.html").write_text(anchored)
    assert stamp(page_dir, "Proposal").exit_code == 0
    decide(page_dir, "accept")
    assert build_threads(events_model.read_events(page_dir), {})[root["id"]]["resolved"]
    revised = (
        anchored.replace("Alpha", "Beta")
        .replace(
            '<lf-suggestion id="sug-refill"', '<lf-suggestion restated id="sug-refill"'
        )
        .replace(
            "Refill when the camera shows it half-empty.", "Refill every afternoon."
        )
    )
    (page_dir / "index.html").write_text(revised)
    result = stamp(page_dir, "Revised the proposal")
    assert result.exit_code == 0, result.output
    events = events_model.read_events(page_dir)
    thread = build_threads(events, {})[root["id"]]
    assert not thread["resolved"] and thread["anchor"] == {"section": "wording"}
    assert events[-1]["kind"] == "reanchor" and events[-1]["revision"] == 3


def test_quote_preservation_reads_restated_body_at_the_candidate_revision(page_dir):
    (page_dir / "index.html").write_text(DRAFTED)
    publish(page_dir)
    edit(page_dir, "Alpha")
    root = json.loads(
        comment(
            page_dir, "--section", "note", "--quote", "Alpha", "--text", "Discuss this."
        ).output
    )
    revised = DRAFTED.replace(
        '<lf-draft id="note">', '<lf-draft id="note" restated>'
    ).replace("Adds --dry-run to every mutating command.", "Beta")
    (page_dir / "index.html").write_text(revised)
    result = stamp(page_dir, "Restated the draft")
    assert result.exit_code == 0, result.output
    thread = next(
        thread
        for thread in state_json(page_dir)["threads"]
        if thread["id"] == root["id"]
    )
    assert thread["anchor"] == {"section": "note"}
    # The words the thread is about stay readable once the page no longer shows them.
    assert thread["rewritten_from"]["quote"] == "Alpha"


def test_a_stamp_detaches_a_reopened_quote_without_a_surviving_section(page_dir):
    original = SUGGESTED.replace("</main>", "<p>Alpha</p></main>")
    (page_dir / "index.html").write_text(original)
    publish(page_dir)
    root = json.loads(
        comment(page_dir, "--quote", "Alpha", "--text", "Discuss this.").output
    )
    anchored = original.replace(
        '<lf-suggestion id="sug-refill">',
        f'<lf-suggestion id="sug-refill" resolves="{root["id"]}">',
    )
    (page_dir / "index.html").write_text(anchored)
    assert stamp(page_dir, "Proposal").exit_code == 0
    decide(page_dir, "accept")
    before = events_model.read_events(page_dir)
    revised = (
        anchored.replace("Alpha", "Beta")
        .replace(
            '<lf-suggestion id="sug-refill"', '<lf-suggestion restated id="sug-refill"'
        )
        .replace(
            "Refill when the camera shows it half-empty.", "Refill every afternoon."
        )
    )
    (page_dir / "index.html").write_text(revised)
    result = stamp(page_dir, "Revised the proposal")
    assert result.exit_code == 0, result.output
    assert files_model.latest_revision(page_dir) == 3
    events = events_model.read_events(page_dir)
    assert events[: len(before)] == before
    thread = build_threads(events, {})[root["id"]]
    assert not thread["resolved"]
    assert thread["anchor"] is None
    assert thread["detached_from"] == root["anchor"]
    assert events[-1]["kind"] == "reanchor" and events[-1]["revision"] == 3


def test_a_refused_stamp_does_not_publish_quote_fallbacks(page_dir):
    original = PAGE.replace("<h2>Plan</h2>", '<h2>Plan</h2><p id="wording">Alpha</p>')
    (page_dir / "index.html").write_text(original)
    publish(page_dir)
    root = json.loads(
        comment(page_dir, "--quote", "Alpha", "--text", "Keep this").output
    )
    before = events_model.read_events(page_dir)
    (page_dir / "index.html").write_text(original.replace("Alpha", "Beta"))
    refused = stamp(page_dir, "Revised", completes=("unknown-widget",))
    assert refused.exit_code == 1 and "no open to-do on" in refused.output
    assert files_model.latest_revision(page_dir) == 1
    assert events_model.read_events(page_dir) == before
    accepted = stamp(page_dir, "Revised")
    assert accepted.exit_code == 0, accepted.output
    events = events_model.read_events(page_dir)
    assert events[-1]["kind"] == "reanchor" and events[-1]["thread"] == root["id"]
    assert events[-2]["kind"] == "note" and events[-2]["revision"] == 2


def test_an_interrupted_stamp_recovers_the_exact_journaled_revision(
    page_dir, monkeypatch
):
    from leaf.records import revision_publication
    from leaf.records.transaction import PageTransaction

    original = PAGE.replace(
        "<h2>Plan</h2>", '<h2>Plan</h2><p id="wording">Alpha Gamma</p>'
    )
    (page_dir / "index.html").write_text(original)
    publish(page_dir)
    roots = [
        json.loads(comment(page_dir, "--quote", quote, "--text", "Keep this").output)
        for quote in ("Alpha", "Gamma")
    ]
    revised = original.replace("Alpha Gamma", "Beta Delta")
    (page_dir / "index.html").write_text(revised)
    append = revision_publication.append_admitted

    def interrupted(page, event, **kwargs):
        accepted = append(page, event, **kwargs)
        if event["kind"] == "note":
            raise RuntimeError("interrupted after durable note")
        return accepted

    with monkeypatch.context() as fault:
        fault.setattr(revision_publication, "append_admitted", interrupted)
        refused = stamp(page_dir, "Revised")
        assert isinstance(refused.exception, RuntimeError)
    assert files_model.latest_revision(page_dir) == 1
    pending = events_model.read_events(page_dir)
    assert pending[-1]["kind"] == "note" and pending[-1]["revision"] == 2
    assert not any(e["kind"] == "reanchor" for e in pending)
    (page_dir / "index.html").write_text(
        original.replace("Alpha Gamma", "Later unrelated edit")
    )
    with PageTransaction(page_dir) as page:
        assert files_model.latest_revision(page_dir) == 2
        assert files_model.revision_path(page_dir, 2).read_text() == revised
        moves = [event for event in page.events if event["kind"] == "reanchor"]
        assert {event["thread"] for event in moves} == {root["id"] for root in roots}
    recovered = events_model.read_events(page_dir)
    with PageTransaction(page_dir):
        pass
    assert events_model.read_events(page_dir) == recovered


def test_an_explicit_replacement_is_durable_before_its_revision_appears(
    page_dir, monkeypatch
):
    from leaf.records import revision_publication
    from leaf.records.transaction import PageTransaction

    original = PAGE.replace("</main>", "<p>Alpha</p></main>")
    (page_dir / "index.html").write_text(original)
    publish(page_dir)
    root = json.loads(
        comment(page_dir, "--quote", "Alpha", "--text", "Keep this").output
    )
    revised = original.replace("Alpha", "Beta")
    (page_dir / "index.html").write_text(revised)
    args = [
        "thread",
        "reply",
        str(page_dir),
        root["id"],
        "--quote",
        "Beta",
        "--text",
        "Revised this.",
    ]

    def interrupted(*args, **kwargs):
        raise RuntimeError("interrupted before required reply")

    with monkeypatch.context() as fault:
        fault.setattr(revision_publication, "append_admitted", interrupted)
        refused = CliRunner().invoke(cli_model.cli, args)
        assert isinstance(refused.exception, RuntimeError)
    with PageTransaction(page_dir) as page:
        assert files_model.latest_revision(page_dir) == 1
        assert not any(event["kind"] == "reply" for event in page.events)

    with monkeypatch.context() as fault:
        fault.setattr(revision_publication, "publish_artifact", interrupted)
        refused = CliRunner().invoke(cli_model.cli, args)
        assert isinstance(refused.exception, RuntimeError)
    assert files_model.latest_revision(page_dir) == 1
    pending = events_model.read_events(page_dir)
    assert pending[-1]["kind"] == "reply" and pending[-1]["anchor"]["quote"] == "Beta"
    (page_dir / "index.html").write_text(original.replace("Alpha", "Gamma"))
    with PageTransaction(page_dir) as page:
        assert files_model.latest_revision(page_dir) == 2
        assert files_model.revision_path(page_dir, 2).read_text() == revised
        assert page.events == pending


def test_an_interrupted_activation_finishes_all_anchor_transitions(
    page_dir, monkeypatch
):
    from leaf.records import revision_publication, revisioning

    original = PAGE.replace(
        "<h2>Plan</h2>", '<h2>Plan</h2><p id="wording">Alpha Gamma</p>'
    )
    (page_dir / "index.html").write_text(original)
    publish(page_dir)
    roots = [
        json.loads(comment(page_dir, "--quote", q, "--text", q).output)
        for q in ("Alpha", "Gamma")
    ]
    (page_dir / "index.html").write_text(original.replace("Alpha Gamma", "Beta Delta"))
    append = revision_publication.append_admitted

    def interrupted(page, event, **kwargs):
        append(page, event, **kwargs)
        raise RuntimeError("interrupted after the first append")

    with monkeypatch.context() as fault:
        fault.setattr(revision_publication, "append_admitted", interrupted)
        import pytest

        with pytest.raises(RuntimeError, match="interrupted after"):
            revisioning.activate_source(page_dir)
    assert files_model.latest_revision(page_dir) == 1
    # The activation naming the bundle is the publication's prerequisite; neither
    # anchor has moved yet.
    pending = events_model.read_events(page_dir)
    assert pending[-1]["kind"] == "activation" and pending[-1]["revision"] == 2
    assert not any(e["kind"] == "reanchor" for e in pending)
    recovered = revisioning.activate_source(page_dir)
    assert recovered.error is None and recovered.revision == 2 and not recovered.created
    threads = {t["id"]: t for t in state_json(page_dir)["threads"]}
    assert all(
        threads[root["id"]]["anchor"] == {"section": "wording"} for root in roots
    )
    assert (
        len([e for e in events_model.read_events(page_dir) if e["kind"] == "reanchor"])
        == 2
    )


def test_detach_is_a_distinct_reply_target_transition(page_dir):
    root = json.loads(
        comment(published(page_dir), "--quote", "Ship dark", "--text", "Why?").output
    )

    mixed = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            root["id"],
            "--detach",
            "--section",
            "plan",
            "--text",
            "Ambiguous.",
        ],
    )

    assert mixed.exit_code != 0
    assert refused_on(mixed.stdout).code == "detach-with-target"


def test_a_withdrawn_reaction_root_takes_no_reply(page_dir):
    """An undone reaction is a mark taken back: no thread fold shows it, so a reply
    naming it would open a thread with no root. The append door refuses both
    detaching and moving it."""
    (page_dir / "index.html").write_text(FLOW_PAGE)
    published(page_dir)
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "emoji": "✂️",
            "anchor": {"section": "flow"},
        },
    )
    append_carried_log_record(
        page_dir,
        {"kind": "undo", "author": "user", "undoes": root["id"]},
    )

    detached = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            root["id"],
            "--detach",
            "--text",
            "There is no current subject to detach.",
        ],
    )
    assert detached.exit_code != 0
    assert refused_on(detached.stdout).code == "withdrawn-parent"

    moved = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            root["id"],
            "--section",
            "plan",
            "--text",
            "Move the withdrawn mark's thread here.",
        ],
    )
    assert moved.exit_code != 0
    assert refused_on(moved.stdout).code == "withdrawn-parent"

    titled = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            root["id"],
            "--title",
            "Shorter flow",
            "--text",
            "Name the withdrawn mark's thread.",
        ],
    )
    assert titled.exit_code != 0
    assert refused_on(titled.stdout).code == "withdrawn-parent"


def test_a_reply_refuses_to_change_a_held_command_goal_anchor(page_dir):
    """A hold's exact-section anchor is part of the command request's meaning, not
    merely the thread's placement, so a later reply cannot silently retarget it."""
    v1 = PAGE.replace(
        "</section>",
        '<lf-test-tasks id="work"><lf-test-task id="held-goal" status="active" talk>'
        "<strong>Held goal</strong></lf-test-task></lf-test-tasks></section>",
    )
    (page_dir / "index.html").write_text(v1)
    published(page_dir)
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Pause here.",
            "anchor": {"section": "held-goal"},
            "holds": "held-goal",
        },
    )

    moved = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, root["id"]),
            "--section",
            "backfill-first",
            "--text",
            "Move this hold.",
        ],
    )

    assert moved.exit_code != 0
    assert refused_on(moved.stdout).code == "held-anchor"

    detached = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, root["id"]),
            "--detach",
            "--text",
            "Detach this hold.",
        ],
    )
    assert detached.exit_code != 0
    assert refused_on(detached.stdout).code == "held-anchor"


def test_detach_after_a_reader_already_activated_the_removal(page_dir):
    """An open tab activates saved source when it polls, and that activation detaches
    a thread whose passage the edit removed. The agent's `--detach` reply that follows
    finds the thread as it asked, so it lands, and the thread keeps the anchor it
    was detached from."""
    original = PAGE.replace("<h2>Plan</h2>", '<h2>Plan</h2><p id="wording">Alpha</p>')
    (page_dir / "index.html").write_text(original)
    publish(page_dir)
    anchor = json.loads(
        comment(page_dir, "--quote", "Alpha", "--text", "Placed here").output
    )["anchor"]
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Drop this?",
            "anchor": anchor,
        },
    )
    (page_dir / "index.html").write_text(
        original.replace('<p id="wording">Alpha</p>', "")
    )
    activate_source(page_dir)
    assert (
        build_threads(events_model.read_events(page_dir), {})[root["id"]]["anchor"]
        is None
    )

    detached = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, root["id"]),
            "--detach",
            "--text",
            "Removed this.",
            "--title",
            "Thread title",
        ],
    )

    assert detached.exit_code == 0, detached.output
    thread = build_threads(events_model.read_events(page_dir), {})[root["id"]]
    assert thread["anchor"] is None
    assert thread["detached_from"] == root["anchor"]


def test_a_quote_may_not_run_across_a_widgets_parts(page_dir):
    """A module can replace or insert words the file's reading cannot model. A quote
    spanning one of those joins would resolve to nothing in the user's browser, so the
    note says so, where someone can still do something about it. Either side of the
    join quotes fine."""
    fenced = FLOW_PAGE.replace(
        '  <lf-diagram id="flow"><pre>\ngraph LR\n  A --> B\n  </pre></lf-diagram>',
        "  <p>Before the diagram.</p>\n"
        '  <lf-diagram id="flow"><pre>\ngraph LR\n  A --> B\n  </pre></lf-diagram>\n'
        "  <p>After the diagram.</p>",
    )
    (page_dir / "index.html").write_text(fenced)
    published(page_dir)
    across = comment(
        page_dir,
        "--quote",
        "Before the diagram. After the diagram.",
        "--text",
        "x",
    )
    assert unplaced(across) == 0
    assert (
        unplaced(comment(page_dir, "--quote", "Before the diagram.", "--text", "x"))
        is None
    )


def test_a_verbatim_body_is_quotable_where_a_source_body_is_not(page_dir):
    """The registry draws the line: lf-draft renders the authored Markdown into a body
    the anchor pass can see (`verbatim`), and lf-diagram renders a picture instead."""
    result = comment(
        drafted(page_dir), "--quote", "every mutating command", "--text", "which ones?"
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["anchor"]["section"] == "note"


@pytest.mark.parametrize("formatted", [False, True], ids=["plain", "markdown"])
def test_an_edited_draft_reads_as_the_users_words(page_dir, formatted):
    """An `edit` is absolute — the log carries the whole new body, and replay writes
    exactly that into the DOM the anchor pass searches — so the reading
    `leaf thread create` captures against holds the user's words in the authored
    body's place: quotable, collapsed like any passage, genuinely adjacent to the
    prose around them (no fence — the screen shows that adjacency too)."""
    drafted(page_dir)
    text = (
        "*Adds* `--dry-run` to **purge**\nand rebuild only."
        if formatted
        else "Adds --dry-run to purge\nand rebuild only."
    )
    edit(page_dir, text)
    result = comment(page_dir, "--quote", "purge and rebuild only", "--text", "x")
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["anchor"]["section"] == "note"
    across = comment(page_dir, "--quote", "Plan Adds --dry-run to purge", "--text", "x")
    assert across.exit_code == 0, across.output


def test_comments_reach_user_generated_choices_without_source_copying(page_dir):
    html = PAGE.replace(PAGE_GROUP, '<lf-options id="routes">')
    (page_dir / "index.html").write_text(html)
    publish(page_dir)
    identity = "routes-option-user"
    words = "Use <a literal> & keep the source unchanged."
    # The single choice says each pick answers it, and the add alone doesn't.
    moves = [
        ("add", {"option": identity, "text": words}, False),
        ("choose", {"value": [identity]}, True),
        ("choose", {"value": ["flag-first"]}, True),
    ]
    for action, detail, answered in moves:
        append_command(
            page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "routes",
                "action": action,
                "detail": detail,
                "answered": answered,
            },
        )

    element = comment(page_dir, "--section", identity, "--text", "Clarify this route.")
    assert element.exit_code == 0, element.output
    assert json.loads(element.output)["anchor"] == {"section": identity}
    quote = comment(page_dir, "--quote", words, "--text", "These exact words.")
    assert quote.exit_code == 0, quote.output
    assert json.loads(quote.output)["anchor"] == {
        "section": identity,
        "quote": words,
    }

    # A later source version still omits the generated option. The open anchored
    # thread and the option's words must both remain reachable.
    (page_dir / "index.html").write_text(
        html.replace("The cutoff lives", "The active cutoff lives")
    )
    published = stamp(page_dir, "Clarified the cutoff.")
    assert published.exit_code == 0, published.output
    later = comment(
        page_dir, "--section", identity, "--quote", words, "--text", "Still here."
    )
    assert later.exit_code == 0, later.output
    assert json.loads(later.output)["anchor"]["section"] == identity


def test_a_quote_of_words_an_edit_replaced_is_noted(page_dir):
    """The authored body is still in the file, but the user is no longer reading
    it, so the note says the page doesn't show those words; a quote merely reaching
    into the replaced body from outside is the same."""
    drafted(page_dir)
    edit(page_dir, "Adds --dry-run to purge and rebuild only.")
    result = comment(page_dir, "--quote", "every mutating command", "--text", "x")
    assert unplaced(result) == 0
    across = comment(page_dir, "--quote", "Plan Adds --dry-run to every", "--text", "x")
    assert unplaced(across) == 0


# The draft rewritten under `restated`, taking back whatever the user wrote over it.
RESTATED = DRAFTED.replace(
    '<lf-draft id="note"><pre>\nAdds --dry-run to every mutating command.',
    '<lf-draft id="note" restated><pre>\nOnly purge gets a dry-run; the rest apply live.',
)


def test_a_restated_draft_takes_the_pen_back_from_the_reading(page_dir):
    """`restated` retracts the edit, so replay stops painting it and the reading
    returns to the version as authored: the new body quotable, the retracted edit's
    text nowhere. A fresh edit on the new version stands again."""
    drafted(page_dir)
    edit(page_dir, "Adds --dry-run to purge and rebuild only.")
    (page_dir / "index.html").write_text(RESTATED)
    noted = stamp(page_dir, "took the pen back")
    assert noted.exit_code == 0, noted.output
    kept = comment(page_dir, "--quote", "the rest apply live", "--text", "x")
    assert unplaced(kept) is None
    gone = comment(page_dir, "--quote", "purge and rebuild only", "--text", "x")
    assert unplaced(gone) == 0
    edit(page_dir, "Fine, but default the flag on.", version=2)
    again = comment(page_dir, "--quote", "default the flag on", "--text", "x")
    assert unplaced(again) is None


def test_repeating_restatement_retracts_a_new_edit_without_blocking_revision(page_dir):
    """Each revision may restate its draft, including after a fresh user edit."""
    drafted(page_dir)
    edit(page_dir, "Adds --dry-run to purge and rebuild only.")
    (page_dir / "index.html").write_text(RESTATED)
    assert stamp(page_dir, "took the pen back").exit_code == 0
    edit(page_dir, "Keep a fresh dry-run choice.", version=2)
    assert (
        unplaced(comment(page_dir, "--quote", "fresh dry-run choice", "--text", "x"))
        is None
    )

    (page_dir / "index.html").write_text(
        RESTATED.replace("<title>t</title>", "<title>t · again</title>")
    )
    repeated = stamp(page_dir, "again")
    assert repeated.exit_code == 0, repeated.output
    assert files_model.latest_revision(page_dir) == 3
    assert (
        unplaced(comment(page_dir, "--quote", "the rest apply live", "--text", "x"))
        is None
    )
    gone = comment(page_dir, "--quote", "fresh dry-run choice", "--text", "x")
    assert unplaced(gone) == 0


def test_a_record_without_captured_state_does_not_block_or_rewrite_a_revision(page_dir):
    """Unusable historical state stays in the log without becoming current state."""
    drafted(page_dir)
    historical = append_carried_log_record(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "note",
            "action": "scribble",
            "meaning": {
                "scope": "page",
                "unit": "note",
                "depends": ["note"],
            },
            "detail": {"text": "Words no layer speaks."},
        },
    )
    (page_dir / "index.html").write_text(
        DRAFTED.replace("<title>t</title>", "<title>t · revised</title>")
    )
    result = comment(page_dir, "--quote", "every mutating command", "--text", "x")
    assert unplaced(result) is None
    assert files_model.latest_revision(page_dir) == 2
    gone = comment(page_dir, "--quote", "Words no layer speaks", "--text", "x")
    assert unplaced(gone) == 0
    assert (
        next(
            event
            for event in events_model.read_events(page_dir)
            if event["id"] == historical["id"]
        )
        == historical
    )


def test_an_unhonored_edit_outlives_a_republish(page_dir):
    """v2 re-emits the authored body with no `restated`, so the user's words
    still stand over it — replay carries them, and the reading follows: silence
    retracts nothing. This is the drift the whole mechanism closes: the file holds
    words the page stopped showing a version ago."""
    drafted(page_dir)
    edit(page_dir, "Adds --dry-run to purge and rebuild only.")
    (page_dir / "index.html").write_text(
        DRAFTED.replace("<title>t</title>", "<title>t · revised</title>")
    )
    noted = stamp(page_dir, "changes elsewhere")
    assert noted.exit_code == 0, noted.output
    kept = comment(page_dir, "--quote", "purge and rebuild only", "--text", "x")
    assert unplaced(kept) is None
    gone = comment(page_dir, "--quote", "every mutating command", "--text", "x")
    assert unplaced(gone) == 0


def test_words_a_widget_shows_apart_are_quotable_like_any_other_passage(page_dir):
    """Words a widget shows apart from the sentence are still the page's, so the anchor
    pass can find them and this has to offer them: the option's chip band opens the
    element, and the gloss's explanation, a popover until opened, closes it."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "</section>",
            '  <lf-gloss id="k-visits">Traffic<span popover>312 daily visits</span></lf-gloss>\n'
            "</section>",
        )
    )
    published(page_dir)
    for quote, section in (
        ("risk: low Backfill first", "backfill-first"),
        ("Traffic 312 daily visits", "k-visits"),
    ):
        result = comment(page_dir, "--quote", quote, "--text", "x")
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["anchor"]["section"] == section


def test_a_decision_retires_its_losing_slot_from_comments_reach(page_dir):
    """The user's accept removes lf-old from the page (the browser's anchor pass
    skips it), so the note says the page doesn't show a quote into it. The surviving
    slot quotes as ever, and a re-decision moves the line: the reading follows the log
    the way replay does, the last word in force."""
    suggested(page_dir)
    decide(page_dir, "accept")
    gone = comment(
        page_dir, "--quote", "Refill every feeder each morning.", "--text", "x"
    )
    assert unplaced(gone) == 0
    kept = comment(page_dir, "--quote", "camera shows it half-empty", "--text", "x")
    assert unplaced(kept) is None

    decide(page_dir, "reject")
    gone = comment(page_dir, "--quote", "camera shows it half-empty", "--text", "x")
    assert unplaced(gone) == 0
    kept = comment(
        page_dir, "--quote", "Refill every feeder each morning.", "--text", "x"
    )
    assert unplaced(kept) is None


def test_a_section_inside_a_retired_slot_is_refused(page_dir):
    """An element anchor is a click on the element, and a retired slot's children
    are elements nobody can click. The id is still in the file — the refusal has to
    come from the decision, not the structure."""
    suggested(page_dir)
    decide(page_dir, "accept")
    result = comment(page_dir, "--section", "refill-rule", "--text", "x")
    assert result.exit_code != 0
    assert "chose to accept" in result.output and "sug-refill" in result.output


def test_a_decision_that_empties_its_widget_takes_it_off_sections_reach(page_dir):
    """A deletion accepted and an insertion refused both settle to nothing: the
    wrapper's markup is still in the file, but the user's screen shows nothing
    there, so an element anchor on it would read attached while outlining nothing.
    Pending, the wrapper answers like any element; settled empty, the refusal names
    the decision that emptied it."""
    lone = before_choice(
        PAGE,
        '<lf-suggestion id="sug-drop">\n'
        "  <lf-old><p>The manual sightings log.</p></lf-old>\n"
        "</lf-suggestion>\n"
        '<lf-suggestion id="sug-add">\n'
        "  <lf-new><p>Switch the north feeder to thistle.</p></lf-new>\n"
        "</lf-suggestion>",
    )
    (page_dir / "index.html").write_text(lone)
    published(page_dir)
    for wid in ("sug-drop", "sug-add"):
        ok = comment(page_dir, "--section", wid, "--text", "x")
        assert ok.exit_code == 0, ok.output
    decide(page_dir, "accept", widget="sug-drop")
    decide(page_dir, "reject", widget="sug-add")
    for wid, verb in (("sug-drop", "accept"), ("sug-add", "reject")):
        gone = comment(page_dir, "--section", wid, "--text", "x")
        assert gone.exit_code != 0
        assert "settled to nothing" in gone.output and f"chose to {verb}" in gone.output


def test_a_settled_replacement_still_answers_an_element_anchor(page_dir):
    """Deciding a replacement keeps a slot on screen, so the wrapper is still a thing
    to point at — only a decision that leaves nothing takes the element away."""
    suggested(page_dir)
    decide(page_dir, "accept")
    ok = comment(page_dir, "--section", "sug-refill", "--text", "x")
    assert ok.exit_code == 0, ok.output


def test_a_decision_settles_which_copy_a_quote_names(page_dir):
    """The browser counts occurrences on the page as decided, so the file counts the
    same way: otherwise a passage unique in front of the user reads as ambiguous
    here, and loses the section it stands in."""
    twice = SUGGESTED.replace(
        "<h2>Plan</h2>", "<h2>Plan</h2>\n  <p>Refill every feeder each morning.</p>"
    )
    (page_dir / "index.html").write_text(twice)
    published(page_dir)
    ambiguous = comment(
        page_dir, "--quote", "Refill every feeder each morning.", "--text", "x"
    )
    assert unplaced(ambiguous) == 2
    decide(page_dir, "accept")
    result = comment(
        page_dir, "--quote", "Refill every feeder each morning.", "--text", "x"
    )
    assert unplaced(result) is None
    assert json.loads(result.output)["anchor"]["section"] == "plan"


def test_a_restated_suggestion_hands_its_slot_back(page_dir):
    """A version that rewrites under a decision retracts it (`restated`), and replay
    then shows the suggestion pending again — both slots on the page. The reading
    follows the log all the way, not just to the first decision it finds."""
    suggested(page_dir)
    decide(page_dir, "accept")
    revised = SUGGESTED.replace(
        "Refill when the camera shows it half-empty.",
        "Refill when the camera shows it two-thirds empty.",
    ).replace(
        '<lf-suggestion id="sug-refill">', '<lf-suggestion id="sug-refill" restated>'
    )
    (page_dir / "index.html").write_text(revised)
    noted = stamp(page_dir, "revised the proposal")
    assert noted.exit_code == 0, noted.output
    result = comment(
        page_dir, "--quote", "Refill every feeder each morning.", "--text", "x"
    )
    assert unplaced(result) is None


def test_a_decision_the_user_took_back_hands_its_slot_back(page_dir):
    """Withdrawing is the second way a decision stops being in force, and the file's
    reading owes it the same answer as `restated`: the retired half is on the page
    again, so a quote reaches it while the authored suggestion still exists."""
    suggested(page_dir)
    decide(page_dir, "accept")
    retired = ["--quote", "Refill every feeder each morning.", "--text", "x"]
    assert unplaced(comment(page_dir, *retired)) == 0

    accepted = next(
        e for e in events_model.read_events(page_dir) if e["kind"] == "action"
    )
    append_carried_log_record(
        page_dir, {"kind": "undo", "author": "user", "undoes": accepted["id"]}
    )
    assert unplaced(comment(page_dir, *retired)) is None


def test_what_the_user_never_sees_is_not_quotable(page_dir):
    """The runtime roots a section-less anchor at document.body, so a <title> is text no
    anchor can reach — and a page's title is often a sentence from the page as well."""
    (page_dir / "index.html").write_text(
        PAGE.replace("<title>t</title>", "<title>Backfill cutover plan</title>")
    )
    result = comment(
        published(page_dir), "--quote", "Backfill cutover plan", "--text", "x"
    )
    assert unplaced(result) == 0


def test_a_comment_can_point_at_an_unstamped_live_revision(page_dir):
    result = comment(page_dir, "--quote", "Ship dark", "--text", "x")
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["revision"] == 1


def test_a_comment_without_an_anchor_asks_the_page_whole(page_dir):
    """Neither --quote nor --section is the browser's general box's own shape: a
    thread on the page as a whole, where a question about the work belongs."""
    result = comment(published(page_dir), "--text", "just a thought")
    assert result.exit_code == 0, result.output
    event = json.loads(result.output)
    assert event["kind"] == "comment" and event["author"] == "agent"
    assert "anchor" not in event


def test_the_agents_own_comment_is_not_printed_back_to_it(page_dir):
    """`leaf wait` and the panel's unread count both turn on author, so a note
    Claude leaves can't wake its own watcher or read as a comment nobody answered."""
    published(page_dir)
    assert comment(page_dir, "--quote", "Ship dark", "--text", "x").exit_code == 0
    assert page_state(page_dir)["pending"] == 0
    assert hook_transport_model.remedies(hook_transport_model.read_plans("")) == []


def test_resolve_closes_a_thread_the_way_the_panel_does(page_dir, monkeypatch):
    """The agent's ✓ Resolve: the same event the panel's control posts, named by any
    message in the thread the way `leaf thread reply` names one, and carrying the posting
    session's voice — which is the whole of how a user learns a thread they did not
    close was closed."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s-7")
    hooks_run_this_tree("s-7")
    monkeypatch.setenv("LEAF_AGENT", "Indexer")
    published(page_dir)
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "cameras are flaky",
        },
    )
    answer = json.loads(
        CliRunner()
        .invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                "--done",
                response_reference(page_dir, root["id"]),
                "--text",
                "fixed in v2",
                "--title",
                "Thread title",
            ],
        )
        .output
    )

    result = CliRunner().invoke(
        cli_model.cli,
        ["thread", "resolve", str(page_dir), answer["id"]],
    )
    assert result.exit_code == 0, result.output
    event = json.loads(result.output)
    assert event["kind"] == "resolve" and event["author"] == "agent"
    assert event["parent"] == answer["id"]
    assert event["agent"] == "Indexer" and event["session"] == "s-7"

    threads = state_json(page_dir)["threads"]
    assert [t["resolved"] for t in threads] == ["agent"]


def test_resolve_refuses_a_message_the_log_has_not_got(page_dir):
    """The parent rule is the reply door's, so a thread can't be closed by naming
    something outside the thread."""
    [refused] = command_findings("thread", "resolve", page_dir, "c9")
    assert refused.values["name"] == "c9"


def test_unresolve_reopens_a_thread_in_agent_readings(page_dir):
    """The agent-side fold reads the inverse transition from the same log as the
    browser, so page state shows the thread open again."""
    published(page_dir)
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Still relevant?",
        },
    )
    resolved = append_carried_log_record(
        page_dir, {"kind": "resolve", "author": "user", "parent": root["id"]}
    )
    reopened = append_carried_log_record(
        page_dir, {"kind": "unresolve", "author": "user", "parent": root["id"]}
    )

    thread = state_json(page_dir)["threads"][0]
    assert thread["resolved"] is None
    assert thread_records(page_dir, root["id"]) == [
        root["id"],
        resolved["id"],
        reopened["id"],
    ]


def test_a_closed_thread_stops_asking(page_dir):
    """Resolving a thread suppresses its obligation attention while retaining inventory."""
    (page_dir / "index.html").write_text(PAGE)
    publish(page_dir)
    root = append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": 'Which mitigations?\n\n<lf-group id="gm-decision" label="Which mitigations?">\n<h3 id="gm-decision-h">Which mitigations?</h3>'
            "<p>The retry budget is shared.</p>"
            '<lf-options id="gm">'
            '<lf-option id="m-cap" label="Cap retries"><strong>Cap retries</strong></lf-option>'
            "</lf-options></lf-group>",
        },
    )
    assert obligations_on_user(state_json(page_dir)) == [
        {
            "id": "widget:gm",
            "tag": "lf-options",
            "widget": "gm",
            "widget_tag": "lf-options",
            "thread": root["id"],
        }
    ]
    append_carried_log_record(
        page_dir, {"kind": "resolve", "author": "agent", "parent": root["id"]}
    )
    assert obligations_on_user(state_json(page_dir)) == []


def test_thread_obligations_share_one_projection_across_open_fragments(page_dir):
    """Independent thread widgets fold together while retaining their threads."""
    publish(page_dir)
    roots = []
    for suffix in ("a", "b"):
        roots.append(
            append_carried_log_record(
                page_dir,
                {
                    "kind": "comment",
                    "author": "agent",
                    "revision": 1,
                    "text": (
                        f"Choose {suffix}\n\n"
                        f'<lf-group id="group-{suffix}-decision" label="Choose {suffix}">\n<h3 id="group-{suffix}-decision-h">Choose {suffix}</h3>'
                        f'<lf-options id="group-{suffix}">'
                        f'<lf-option id="option-{suffix}" label="{suffix}"><strong>{suffix}</strong></lf-option>'
                        "</lf-options></lf-group>"
                    ),
                },
            )
        )
    assert obligations_on_user(state_json(page_dir)) == [
        {
            "id": "widget:group-a",
            "tag": "lf-options",
            "widget": "group-a",
            "widget_tag": "lf-options",
            "thread": roots[0]["id"],
        },
        {
            "id": "widget:group-b",
            "tag": "lf-options",
            "widget": "group-b",
            "widget_tag": "lf-options",
            "thread": roots[1]["id"],
        },
    ]

    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "group-a",
            "action": "choose",
            "detail": {"value": ["option-a"]},
            "answered": True,
        },
    )
    assert obligations_on_user(state_json(page_dir)) == [
        {
            "id": "widget:group-b",
            "tag": "lf-options",
            "widget": "group-b",
            "widget_tag": "lf-options",
            "thread": roots[1]["id"],
        }
    ]


def test_native_message_html_shares_admission_and_id_ownership(page_dir):
    """Native evidence posts through every agent writer and reserves its ids."""
    published(page_dir)
    table = (
        '<table id="run-results"><caption>Deploy checks</caption>'
        '<tr><th scope="col">Check</th><th scope="col">Result</th></tr>'
        "<tr><td>Smoke test</td><td>Passed</td></tr></table>"
    )
    opened = comment(page_dir, "--text", f"Results:\n\n{table}")
    assert opened.exit_code == 0, opened.output
    root = events_model.read_events(page_dir)[-1]["id"]
    log = '<details id="deploy-log"><summary>Deploy log</summary><pre>Ready\nDone</pre></details>'
    proactive = CliRunner().invoke(
        cli_model.cli,
        ["thread", "reply", str(page_dir), root, "--text", f"Log:\n\n{log}"],
    )
    assert proactive.exit_code == 0, proactive.output
    append_command(
        page_dir,
        {"kind": "reply", "author": "user", "parent": root, "text": "And now?"},
    )
    user = events_model.read_events(page_dir)[-1]["id"]
    answered = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, user),
            "--text",
            'Ready.\n\n<p id="deploy-status">All checks passed.</p>',
        ],
    )
    assert answered.exit_code == 0, answered.output
    held = [e for e in events_model.read_events(page_dir) if logged_fragment(e)]
    assert [e["text"] for e in held] == [
        f"Results:\n\n{table}",
        f"Log:\n\n{log}",
        'Ready.\n\n<p id="deploy-status">All checks passed.</p>',
    ]
    for identifier in ("run-results", "deploy-log", "deploy-status", "plan"):
        refused = comment(
            page_dir,
            "--text",
            f'Again:\n\n<p id="{identifier}">Duplicate</p>',
        )
        assert refused.exit_code != 0, refused.output
        assert "already taken" in refused.output, refused.output
    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace(
            "</main>", '<p id="run-results">New result</p></main>'
        )
    )
    status, findings = check_findings(page_dir)
    assert status == 1
    assert found(findings, "ids-taken-by-messages", ids=["run-results"])


@pytest.mark.parametrize("native", [False, True])
def test_message_html_may_not_dress_the_document_it_is_put_into(page_dir, native):
    """A fragment has no page of its own, so it gets no stylesheet of its own.

    The runtime parses an agent's markup into a template and moves those nodes into the
    message body, where a <style> among them becomes a document stylesheet like any
    other. `main h1 { color: red !important }` in a reply repainted the version's own
    heading, and the same declaration in a version answers to the syntax, column and
    cascade gates this door was never running.

    Native evidence and widgets pass through the same presentation gate."""
    published(page_dir)
    widget = (
        '<lf-group id="d1-decision" label="Choose one">\n<h3 id="d1-decision-h">Choose one</h3><lf-options id="d1">'
        '<lf-option id="d1-a">A</lf-option></lf-options></lf-group>'
    )
    if native:
        widget = '<pre id="native-log">Ready</pre>'

    sheet = comment(
        page_dir,
        "--text",
        "look:\n\n<style>main h1 { color: red }</style>\n\n" + widget,
    )
    assert sheet.exit_code != 0 and "<style>" in sheet.output

    linked = comment(
        page_dir,
        "--text",
        'look:\n\n<link rel="stylesheet" href="/theme.css">\n\n' + widget,
    )
    assert linked.exit_code != 0 and "stylesheet" in linked.output

    assert comment(page_dir, "--text", f"look:\n\n{widget}").exit_code == 0


def test_page_state_holds_a_decision_made_on_a_widget_an_agent_sent(page_dir):
    """The user answering the agent's own question is answering the page.

    `page state` projects the published version's elements, and a widget carried by a
    message is in none of them — so a press on an AskUserQuestion resolved no
    declaration and stood nowhere. A session picking the page up read the question's
    task as answered and `state` reporting that nobody had answered anything,
    while the browser had been folding that same action all along.

    It is named by its thread rather than by a version, because page versions do
    not bound thread markup's state."""
    published(page_dir)
    assert (
        comment(
            page_dir,
            "--text",
            'Pick one:\n\n<lf-group id="ps-decision" label="Which store?">\n<h3 id="ps-decision-h">Which store?</h3>'
            '<lf-options id="ps-q">'
            '<lf-option id="ps-redis">Redis</lf-option>'
            '<lf-option id="ps-cookie">A signed cookie</lf-option>'
            "</lf-options></lf-group>",
        ).exit_code
        == 0
    )
    thread = events_model.read_events(page_dir)[-1]["id"]
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "ps-q",
            "action": "choose",
            "detail": {"value": ["ps-cookie"]},
            "answered": True,
        },
    )
    out = CliRunner().invoke(cli_model.cli, ["page", "state", str(page_dir)])
    assert out.exit_code == 0, out.output
    state = json.loads(out.stdout)
    assert [
        (s["widget"], s["action"], s["detail"], s["thread"]) for s in state["state"]
    ] == [("ps-q", "choose", {"value": ["ps-cookie"]}, thread)]


@pytest.mark.parametrize("native", [False, True])
def test_message_html_may_not_declare_the_document(page_dir, native):
    """A message renders in every revision of its page, so a base, header, or import
    map in one would redirect, navigate, or break that page for good. Handlers are the
    author's to write, as in the page itself."""
    published(page_dir)
    widget = (
        '<lf-group id="d1-decision" label="Choose one">\n<h3 id="d1-decision-h">Choose one</h3><lf-options id="d1">'
        '<lf-option id="d1-a">A</lf-option></lf-options></lf-group>'
    )
    if native:
        widget = '<table id="native-checks"><tr><td>Passed</td></tr></table>'
    for declaration in (
        '<base href="https://outside.example/">',
        '<meta http-equiv="refresh" content="0;url=https://outside.example/">',
        '<script type="importmap">{"imports": {}}</script>',
    ):
        refused = comment(page_dir, "--text", f"look:\n\n{declaration}\n\n{widget}")
        assert refused.exit_code != 0, declaration
        assert "document-declaration" in refused.output, refused.output
    handled = '<p onclick="this.hidden = true">Hide me</p>\n\n' + widget
    assert comment(page_dir, "--text", f"look:\n\n{handled}").exit_code == 0


def test_data_widget_prose_members_are_quotable_without_admitting_source():
    registry = with_modules(
        {
            "lf-source": {
                "content": "data",
            },
            "lf-remark": {
                "content": "markup",
                "owners": ["lf-source"],
            },
        },
        "lf-source",
    )
    document = structure_model.SourceDocument(
        '<p>Before.</p><lf-source id="source"><pre>Hidden source '
        "<lf-remark>Still source.</lf-remark></pre>"
        '<lf-remark id="remark">A <em>readable</em> remark.</lf-remark>'
        "<aside>Undeclared body.</aside></lf-source><p>After.</p>"
    )
    assert passages_model.page_passages(document, registry).text == (
        "Before. A readable remark. After."
    )
    # A member declaration does not reopen an excluded subtree.
    hidden = structure_model.SourceDocument(
        '<div class="lf-ui"><lf-source><lf-remark>Hidden remark.</lf-remark>'
        "</lf-source></div>"
    )
    assert passages_model.page_passages(hidden, registry).text == ""
