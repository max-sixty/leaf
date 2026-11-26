"""Writing a response: the response reference an answer cites, the author API, and
the reply reservation that decides whether the agent or the provider's turn
answers an input."""

import json
import os
import shutil
import subprocess
import sys
from typing import TypedDict

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND, hooks_run_this_tree
from interact_support import (
    PAGE,
    PAGE_GROUP,
    _codex_delivery,
    _observer,
    acknowledged_through,
    append_carried_log_record,
    append_command,
    command_findings,
    command_notes,
    delivered_ref,
    delivery_through,
    last_deliverable_seq,
    owed,
    owed_answers,
    page_state,
    publish,
    read_record,
    receive_through,
    record_claim,
    refused_on,
    response_reference,
    served_updates,
    state_json,
)

from leaf.agents import codex as codex_model
from leaf.agents import delivery as delivery_model
from leaf.agents import thread as thread_model
from leaf.base import files as files_model
from leaf.base import harness as harness_model
from leaf.base import service as service_model
from leaf.base import state as cleanup_model
from leaf.base.refusals import Refused
from leaf.commands import cli as cli_model
from leaf.commands import delivery_ack as delivery_ack_model
from leaf.commands import tasks as tasks_model
from leaf.log import event_log as events_model
from leaf.log.events import build_threads, logged_fragment
from leaf.records import revisioning as revisioning_model
from leaf.records import todos as todos_model
from leaf.records import transaction as transaction_model
from leaf.source.revision_artifact import active_enclosing


class ResponseOptions(TypedDict, total=False):
    ephemeral: bool
    failure: str


QUESTION = (
    '<lf-options id="question"><lf-option id="question-a" label="A"><strong>A</strong> '
    "</lf-option></lf-options>"
)


def test_reply_is_fenced_to_the_exact_current_obligation(page_dir):
    first = append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "first", "author": "user", "text": "Use A."},
    )
    reference = response_reference(page_dir, first)
    second = append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "correction",
            "author": "user",
            "parent": first["id"],
            "text": "Correction: use B.",
        },
    )

    stale = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            reference,
            "--text",
            "Used A.",
        ],
    )
    assert stale.exit_code != 0
    assert refused_on(stale.stdout).code == "superseded-reply"

    current = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, second["id"]),
            "--text",
            "Used B.",
            "--title",
            "Thread title",
        ],
    )
    assert current.exit_code == 0, current.output
    assert events_model.read_events(page_dir)[-1]["responds"] == second["id"]


def test_the_agents_reply_names_a_thread_nobody_titled(page_dir):
    """Every thread has a title. Where nothing titled a user's thread as they posted,
    as on a page no session claims, the agent's reply is refused without --title,
    progress or answer, and names the thread with one; a later reply needs none.
    Leaf's own writes, such as a line fork's working line, owe no title."""

    def titles() -> dict:
        events = events_model.read_events(page_dir)
        threads = build_threads(events, active_enclosing(page_dir))
        return {thread: read["title"] for thread, read in threads.items()}

    asked = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Which store?"}
    )
    reference = response_reference(page_dir, asked)
    before = events_model.read_events(page_dir)
    for declared in ("--ephemeral", "--done"):
        [refused] = command_findings(
            "thread", "reply", reference, declared, "--text", "Checking."
        )
        assert (refused.code, refused.severity) == ("untitled-thread", "error")
        assert refused.values == {"thread": asked["id"]}
    assert events_model.read_events(page_dir) == before

    progress = ["--ephemeral", "--text", "Checking.", "--title", "Choosing a store"]
    assert command_notes("thread", "reply", reference, *progress) == []
    assert titles() == {asked["id"]: "Choosing a store"}
    assert (
        command_notes("thread", "reply", reference, "--done", "--text", "SQLite") == []
    )

    other = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "And the cache?"}
    )
    thread_model.post_reply(
        page_dir, {"responds": other["id"]}, "On it.", ephemeral=True
    )
    assert titles()[other["id"]] is None


def test_a_message_that_asks_by_its_widget_and_its_words_is_told_it_asks_twice(
    page_dir,
):
    """Only the user's words answer `--obligation`, so beside a widget that asks it
    keeps the message on On Me after the user picks. Both writers post the message,
    which may ask in words what the widget doesn't, and say beside it that it asks
    twice."""
    revisioning_model.activate_source(page_dir)
    asked = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Which one?"},
    )
    for command, question in (
        (
            [
                "thread",
                "reply",
                response_reference(page_dir, asked),
                "--title",
                "Thread title",
            ],
            QUESTION,
        ),
        (
            ["thread", "create", str(page_dir), "--title", "Agent thread"],
            QUESTION.replace("question", "again"),
        ),
    ):
        noted = command_notes(
            *command, "--obligation", "--text", f"Which?\n\n{question}"
        )
        assert [f.code for f in noted] == ["obligation-beside-widget"]
        assert events_model.read_events(page_dir)[-1].get("obligation") is True


def test_a_message_beside_an_owed_answer_names_a_ref_only_while_its_owner_holds_the_page(
    claimed, monkeypatch
):
    """A message posted into a thread that owes an answer answers nothing, and the
    command notes the exact `answer.ref` the owed message's receipt recorded. Once
    another session claims the page the reply writer refuses that reference, so the
    note stops naming it and names the `leaf wait` that hands the message to the new
    owner with a reference of its own."""
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    earlier = delivery_through(claimed, last_deliverable_seq(claimed))
    delivery_ack_model.receive_delivery(earlier)
    ref = delivered_ref(claimed, asked["id"])
    reply = ["thread", "reply", str(claimed), asked["id"], "--text", "B"]
    reply += ["--title", "Why B"]

    def owed_note() -> str:
        posted = CliRunner().invoke(cli_model.cli, reply)
        assert posted.exit_code == 0, posted.output
        [owed] = json.loads(posted.stdout)["findings"]
        assert (owed["code"], owed["severity"]) == ("owed-response", "advice")
        assert asked["id"] in delivery_model.current_responses(
            claimed, events_model.read_events(claimed)
        )
        return owed["text"]

    assert f"`leaf thread reply {ref}` answers it" in owed_note()

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s2")
    hooks_run_this_tree("s2")
    assert transaction_model.claim_page(claimed)
    noted = owed_note()
    assert ref not in noted
    assert f"`leaf wait {claimed}` delivers for {asked['id']}" in noted

    # A delivery captured under the new claim gives it a ref of its own, which a
    # late receipt of the earlier owner's delivery neither hides nor records again.
    receive_through(claimed, last_deliverable_seq(claimed))
    successor = delivered_ref(claimed, asked["id"])
    assert successor != ref
    pickups = len(
        [e for e in events_model.read_events(claimed) if e["kind"] == "pickup"]
    )
    delivery_ack_model.receive_delivery(earlier)
    assert delivered_ref(claimed, asked["id"]) == successor
    assert pickups == len(
        [e for e in events_model.read_events(claimed) if e["kind"] == "pickup"]
    )


@pytest.mark.parametrize("earlier", [None, "progress", "failure-markup"])
def test_the_first_reply_on_a_revision_notes_what_page_check_advises(page_dir, earlier):
    """A revision that answers a message gets no `page check` before its reply, so
    the first successful reply notes the advice `page check` gives on it, beside
    its result. Progress and failure reports do not consume that advice; later
    successful replies on that revision repeat none of it."""

    def advised(comment):
        asked = append_carried_log_record(
            page_dir,
            {"kind": "comment", "id": comment, "author": "user", "text": "Tidy it"},
        )
        posted = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "reply",
                response_reference(page_dir, asked),
                "--done",
                "--title",
                "Thread title",
            ]
            + ["--text", "Tidied."],
        )
        assert posted.exit_code == 0, posted.output
        return json.loads(posted.stdout).get("findings", [])

    (page_dir / "index.html").write_text(
        '<!doctype html><html lang="en"><head><title>t</title></head>'
        "<body><main><h1>Title</h1><p>words</p></main></body></html>",
        encoding="utf-8",
    )
    revisioning_model.activate_source(page_dir)
    checked = CliRunner().invoke(cli_model.cli, ["page", "check", str(page_dir)])
    report = json.loads(checked.stdout)
    assert {finding["code"] for finding in report["findings"]} == {"unpointable"}
    if earlier:
        asked = append_carried_log_record(
            page_dir,
            {"kind": "comment", "author": "user", "text": "Can you check this?"},
        )
        reference = response_reference(page_dir, asked)
        if earlier == "progress":
            with pytest.raises(Refused) as refused:
                thread_model.post_response(
                    reference,
                    'Checking.\n\n<lf-options id="check">'
                    '<lf-option id="check-now">Now</lf-option></lf-options>',
                    ephemeral=True,
                )
            assert refused_on(refused.value).code == "ephemeral-content"
        options: ResponseOptions = (
            {"ephemeral": True} if earlier == "progress" else {"failure": "unavailable"}
        )
        thread_model.post_response(
            reference,
            "Checking."
            if earlier == "progress"
            else "Unavailable.\n\n<p>Unavailable.</p>",
            **options,
        )
    assert advised("first") == report["findings"]
    assert advised("second") == []


def test_response_reference_preserves_page_identity_and_retries(page_dir, tmp_path):
    other = tmp_path / "other-response"
    shutil.copytree(page_dir, other)
    batches = []
    for page in (page_dir, other):
        asked = append_carried_log_record(
            page, {"kind": "comment", "id": "same-id", "author": "user", "text": "Why?"}
        )
        with transaction_model.PageTransaction(page) as transaction:
            batches.append(delivery_model.batch_data(page, transaction, [asked]))
    payload = delivery_model.freeze_delivery(batches)
    refs = [batch["events"][0]["answer"]["ref"] for batch in payload["batches"]]
    assert refs[0] != refs[1]
    for page, reference in zip((page_dir, other), refs, strict=True):
        answer = ["thread", "reply", "--done", reference, "--text", str(page)]
        posted = CliRunner().invoke(cli_model.cli, [*answer, "--title", "Why"])
        assert posted.exit_code == 0, posted.output
        retry = CliRunner().invoke(cli_model.cli, [*answer, "--title", "Why"])
        assert retry.exit_code == 0, retry.output
        assert json.loads(posted.output) == json.loads(retry.output)
        # Reworded, it is another reply at the thread's newest input, which goes in
        # and answers nothing new.
        reworded = CliRunner().invoke(
            cli_model.cli, ["thread", "reply", "--done", reference, "--text", "Again"]
        )
        assert reworded.exit_code == 0, reworded.output
        replies = [
            event
            for event in events_model.read_events(page)
            if event["kind"] == "reply"
        ]
        assert [
            (reply["parent"], reply.get("responds"), reply["text"]) for reply in replies
        ] == [("same-id", "same-id", str(page)), ("same-id", None, "Again")]


def test_a_done_answer_after_a_todo_answer_on_one_ref_names_the_open_todo(page_dir):
    """An agent answers with `--todo` while the work runs, then with `--done` on the
    same reference once it finishes. Both go in: the second posts in the thread and
    answers nothing, and the command names the to-do the first opened, still open,
    with the command that ends it. Repeated word for word it adds nothing."""
    asked = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Rebuild the chart."}
    )
    reference = response_reference(page_dir, asked)

    def reply(*flags):
        posted = CliRunner().invoke(
            cli_model.cli,
            ["thread", "reply", reference, *flags, "--title", "Thread title"],
        )
        assert posted.exit_code == 0, posted.output
        return json.loads(posted.stdout)

    promise = reply("--todo", "Rebuild the chart", "--text", "Rebuilding it.")
    delivered = reply("--done", "--text", "Rebuilt it.")
    assert delivered["parent"] == asked["id"]
    assert "responds" not in delivered
    [noted] = delivered.pop("findings")
    assert noted["code"] == "promised-todo"
    assert (
        f'`leaf task end {page_dir} {promise["id"]} done --text "<where the result'
        in noted["text"]
    )
    events = events_model.read_events(page_dir)
    assert events[-1] == delivered
    assert [todo["id"] for todo in todos_model.TodoReading(events).owed] == [
        promise["id"]
    ]
    assert thread_model.successful_replies(events, asked["id"]) == [promise]

    assert reply("--done", "--text", "Rebuilt it.") == delivered
    assert events_model.read_events(page_dir) == events
    # With the to-do ended, another reply at the reference still goes in, since the
    # comment is still the thread's newest input, and names no to-do.
    tasks_model.cmd_end(page_dir, promise["id"], "done", f"reply {delivered['id']}")
    again = reply("--done", "--text", "Rebuilt it again.")
    assert "responds" not in again and "findings" not in again


def test_response_author_api_covers_markup_question_title_progress_and_anchor(page_dir):
    revisioning_model.activate_source(page_dir)
    asked = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Which option?"},
    )
    reference = response_reference(page_dir, asked)
    progress = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            reference,
            "--ephemeral",
            "--text",
            "Checking the options.",
            "--title",
            "Options",
        ],
    )
    assert progress.exit_code == 0, progress.output
    assert (
        delivery_model.current_responses(page_dir, events_model.read_events(page_dir))[
            asked["id"]
        ]["kind"]
        == "reply"
    )
    invalid = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            reference,
            "--text",
            'Choose\n\n<lf-unknown id="bad"></lf-unknown>',
            "--title",
            "Options",
        ],
    )
    assert invalid.exit_code != 0
    assert not any(
        event["kind"] == "thread_title" for event in events_model.read_events(page_dir)
    )
    markup = '<lf-options id="response-options"><lf-option id="response-yes" label="Yes"><strong>Yes</strong></lf-option></lf-options>'
    posted = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            reference,
            "--text",
            f"Choose here.\n\n{markup}",
            "--section",
            "plan",
        ],
    )
    assert posted.exit_code == 0, posted.output
    records = [json.loads(line) for line in posted.output.splitlines()]
    assert [event["kind"] for event in records] == ["reply"]
    assert markup in records[0]["text"]
    assert records[0]["anchor"]["section"] == "plan"
    threads = build_threads(
        events_model.read_events(page_dir), active_enclosing(page_dir)
    )
    assert threads[asked["id"]]["title"] == "Options"
    selected = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "response-options",
            "action": "choose",
            "detail": {"value": ["response-yes"]},
        },
    )
    # A widget input is answered on the message holding it, not on its own event id.
    selected_ref = response_reference(page_dir, selected)
    destination = delivery_model.response_address(selected_ref)
    assert destination["parent"] == asked["id"]
    questioned = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            selected_ref,
            "--text",
            f"Which store owns it?\n\n{QUESTION}",
            "--detach",
        ],
    )
    assert questioned.exit_code == 0, questioned.output
    record = json.loads(questioned.output)
    assert record["parent"] == asked["id"]
    assert record["responds"] == selected["id"]
    assert QUESTION in record["text"]
    assert record["anchor"] is None


def test_response_refuses_stale_replaced_foreign_and_reserved_inputs(
    page_dir, monkeypatch
):
    def cli_refuses(reference, text, reason):
        args = ["thread", "reply", "--done", reference, "--text", text]
        refused = CliRunner().invoke(cli_model.cli, args)
        assert refused.exit_code == 1
        assert reason in json.loads(refused.stdout)["error"]
        assert isinstance(refused.exception, SystemExit)
        launched = subprocess.run(
            [*LEAF_COMMAND, *args], capture_output=True, text=True, check=False
        )
        assert launched.returncode == 1, (launched.stdout, launched.stderr)
        assert launched.stdout == refused.stdout

    revisioning_model.activate_source(page_dir)
    original = append_command(
        page_dir, {"kind": "comment", "author": "user", "revision": 1, "text": "Use A."}
    )
    stale = response_reference(page_dir, original)
    corrected = append_command(
        page_dir,
        {"kind": "reply", "author": "user", "parent": original["id"], "text": "Use B."},
    )
    before = events_model.read_events(page_dir)
    refused = CliRunner().invoke(
        cli_model.cli, ["thread", "reply", "--done", stale, "--text", "Used A."]
    )
    assert refused.exit_code != 0
    assert events_model.read_events(page_dir) == before
    fresh = response_reference(page_dir, corrected)
    (page_dir / "events.jsonl").write_text("")
    append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Replacement"},
    )
    with pytest.raises(delivery_model.ReceiptRefused, match="matches its page log"):
        thread_model.post_response(fresh, "Old log")
    cli_refuses(fresh, "Old log", "matches its page log")
    # A new owned delivery cannot be answered by another session, even if the id fits.
    event = events_model.read_events(page_dir)[0]
    reference = response_reference(page_dir, event)
    record_claim(page_dir, id="owner", harness="embedded", agent="Owner")
    with pytest.raises(
        delivery_model.ReceiptRefused, match="claim no longer matches its delivery"
    ):
        thread_model.post_response(
            reference, "Foreign", identity={"session": "foreign"}
        )
    cli_refuses(
        reference, "Foreign", "response page claim no longer matches its delivery"
    )
    prepared = codex_model.prepare_codex_delivery(
        page_dir, harness_model.EmbeddedHarness("owner", "Owner", os.getpid())
    )
    turn_ref = prepared.payload["batches"][0]["events"][0]["answer"]["ref"]
    # Capture-time guidance does not reserve the reply before a reservation exists.
    answer = thread_model.post_response(
        turn_ref, "Answer before reservation", identity={"session": "owner"}
    )
    assert answer is not None
    assert answer["responds"] == event["id"]

    # CLI presentation adapts known refusals only; failures and numeric status
    # from another owner retain their identity and meaning.
    for failure in (RuntimeError("unexpected writer failure"), SystemExit(7)):

        def fail(*_args, _failure=failure, **_kwargs):
            raise _failure

        with monkeypatch.context() as patched:
            patched.setattr(thread_model, "post_response", fail)
            result = CliRunner().invoke(
                cli_model.cli,
                ["thread", "reply", "--done", reference, "--text", "Control"],
            )
        assert result.exception is failure
        assert result.exit_code == (7 if isinstance(failure, SystemExit) else 1)
        assert result.output == ""

    light_help = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from click.testing import CliRunner; from leaf.commands.cli import cli; import sys; "
                "assert 'leaf.agents.delivery' not in sys.modules; "
                "result = CliRunner().invoke(cli, ['thread', 'reply', '--help']); "
                "assert result.exit_code == 0, result.output; "
                "assert 'leaf.agents.delivery' not in sys.modules"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert light_help.returncode == 0, (light_help.stdout, light_help.stderr)


def test_delegated_response_survives_its_coordinators_end_without_a_competing_claim(
    page_dir, monkeypatch
):
    revisioning_model.activate_source(page_dir)
    record_claim(page_dir, id="coordinator", harness="embedded", agent="Coordinator")
    comment = append_command(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Check reconnect.",
        },
    )
    reference = response_reference(page_dir, comment)
    cleanup_model.end_session("coordinator")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "worker-1")
    hooks_run_this_tree("worker-1")
    monkeypatch.setenv("LEAF_AGENT", "Indexer")
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            reference,
            "--text",
            "The queue survives reconnect.",
            "--title",
            "Thread title",
        ],
    )
    assert result.exit_code == 0, result.output
    reply = json.loads(result.output)
    assert (reply["session"], reply["agent"], reply["responds"]) == (
        "worker-1",
        "Indexer",
        comment["id"],
    )
    assert not service_model.claim_is_active(service_model.page_claim(page_dir))


def test_superseded_response_stays_refused_after_successor_ends(claimed):
    publish(claimed)
    comment = append_command(
        claimed,
        {
            "kind": "comment",
            "revision": 1,
            "author": "user",
            "text": "Check the parser",
        },
    )
    reference = response_reference(claimed, comment)
    with transaction_model.PageTransaction(claimed) as page:
        page.take_claim(
            harness_model.EmbeddedHarness("successor", "Successor", os.getpid())
        )
    cleanup_model.end_session("successor")
    before = events_model.read_events(claimed)
    result = CliRunner().invoke(
        cli_model.cli,
        ["thread", "reply", "--done", reference, "--text", "Old worker"],
    )
    assert result.exit_code == 1
    assert "claim no longer matches its delivery" in result.stdout
    assert events_model.read_events(claimed) == before


def test_delegated_author_write_survives_same_owner_process_restart(claimed):
    publish(claimed)
    comment = append_command(
        claimed,
        {
            "kind": "comment",
            "revision": 1,
            "author": "user",
            "text": "Check the parser",
        },
    )
    reference = response_reference(claimed, comment)
    original = service_model.page_claim(claimed)
    assert original is not None
    cleanup_model.ensure_session(original["id"], {"pid": os.getppid()})
    with transaction_model.PageTransaction(claimed) as page:
        assert original is not None
        page.take_claim(
            harness_model.EmbeddedHarness(original["id"], "Coordinator", os.getpid())
        )
    claim_record = service_model.page_claim(claimed)
    assert claim_record is not None
    assert claim_record["generation"] != original["generation"]
    answer = thread_model.post_response(
        reference,
        "Parser checked",
        identity={"session": "worker-1", "agent": "Indexer"},
    )
    assert answer is not None
    assert (answer["responds"], answer["session"], answer["agent"]) == (
        comment["id"],
        "worker-1",
        "Indexer",
    )


def test_response_api_records_failure_without_reopening_thread(page_dir):
    revisioning_model.activate_source(page_dir)
    source = page_dir / "index.html"
    active = files_model.latest_revision(page_dir)
    asked = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Please answer."}
    )
    reference = response_reference(page_dir, asked)
    progress = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            reference,
            "--ephemeral",
            "--text",
            "Looking into it.",
            "--title",
            "Thread title",
        ],
    )
    assert progress.exit_code == 0, progress.output
    saved = source.read_text()
    source.write_text("<lf-unknown>Unfinished draft</lf-unknown>")
    reply = thread_model.post_response(
        reference, "No answer is coming.", failure="unavailable"
    )
    assert files_model.latest_revision(page_dir) == active
    assert source.read_text() == "<lf-unknown>Unfinished draft</lf-unknown>"
    assert reply is not None
    assert reply["failure"] == "unavailable"
    assert reply["responds"] == asked["id"]
    assert (
        delivery_model.current_responses(page_dir, events_model.read_events(page_dir))
        == {}
    )
    assert state_json(page_dir)["queues"]["on_user"][0]["id"] == f"update:{asked['id']}"
    # A turn that recovers answers at the same reference, the thread's newest input,
    # and the failure no longer waits on the user.
    source.write_text(saved)
    answered = CliRunner().invoke(
        cli_model.cli, ["thread", "reply", reference, "--done", "--text", "Here it is."]
    )
    assert answered.exit_code == 0, answered.output
    assert events_model.read_events(page_dir)[-1]["responds"] == asked["id"]
    assert state_json(page_dir)["queues"]["on_user"] == []
    # That answer is the input's, so a second reply there answers nothing new, and a
    # turn's final at the same reference yields to it.
    again = CliRunner().invoke(
        cli_model.cli, ["thread", "reply", reference, "--done", "--text", "Also this."]
    )
    assert again.exit_code == 0, again.output
    assert "responds" not in events_model.read_events(page_dir)[-1]
    assert (
        thread_model.post_reply(
            page_dir,
            {"parent": asked["id"], "responds": asked["id"]},
            "Here it is.",
            settlement=thread_model.ProviderFinal("turn"),
        )
        is None
    )


def _reserved_author_response(page_dir):
    revisioning_model.activate_source(page_dir)
    comment = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Which option?"},
    )
    prepared = codex_model.prepare_codex_delivery(
        page_dir, harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid())
    )
    target = codex_model.stream_reply_target(prepared.payload)
    assert target is not None
    thread_model.reserve_delivery_reply("codex-thread", prepared.payload["id"], target)
    cleanup_model.prompt_turn("codex-thread", "author-turn")
    stream = codex_model.AppServerReplyStream(
        "codex-thread", "author-turn", prepared.payload["id"], target
    )
    return comment, target, prepared.payload["id"], stream


def test_progress_draws_formatting_and_holds_no_widget(page_dir):
    """A progress line reads as any agent message does, so the HTML formatting its
    words carry draws, but the answer replaces the line, so it holds no widget."""
    publish(page_dir)
    asked = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Can you check this?"}
    )
    reference = response_reference(page_dir, asked)
    with pytest.raises(Refused) as refused:
        thread_model.post_response(
            reference,
            'Checking.\n\n<lf-options id="check">'
            '<lf-option id="check-now">Now</lf-option></lf-options>',
            ephemeral=True,
        )
    assert refused_on(refused.value).code == "ephemeral-content"
    line = thread_model.post_response(
        reference, "Checking <em>this</em> now.", ephemeral=True
    )
    assert line is not None and line["ephemeral"] is True
    assert logged_fragment(line) is not None


def test_a_turns_opening_posts_as_progress_where_it_was_said(page_dir):
    """A provider turn's opening is the agent's progress line, as any harness's first
    line is: once complete it posts once, taking the update in hand, so a message the
    user sends during the turn follows it. The turn's final message posts after that
    message and answers nothing, since the turn never read it, so both stay owed. An
    opening of several paragraphs posts as the one line progress is, and one whose
    completion a reconnect missed posts as the next item begins."""
    comment, _target, _delivery_id, stream = _reserved_author_response(page_dir)
    fold = codex_model.AppServerEvents("codex-thread", "author-turn")
    opening = {
        "id": "opening",
        "type": "agentMessage",
        "phase": "commentary",
        "text": "Comparing the options.\n\nThen the pricing.",
    }

    def told(method, item, **at):
        params = {"threadId": "codex-thread", "turnId": "author-turn", "item": item}
        return stream.update(fold.read({"method": method, "params": params | at}))

    assert not told("item/started", opening, startedAtMs=1)
    # The connection drops before the opening's completion arrives; the snapshot shows
    # it as the turn's last item, so nothing says yet that it is complete.
    fold.restore_turn({"id": "author-turn", "items": [opening]})
    assert not fold.said_opening()
    tool = {
        "id": "tool",
        "type": "commandExecution",
        "command": "ls",
        "commandActions": [],
        "cwd": "/work",
        "status": "inProgress",
    }
    assert told("item/started", tool, startedAtMs=2)
    assert not told("item/completed", opening, completedAtMs=3)
    asked = append_command(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": comment["id"],
            "revision": 1,
            "text": "And the cost?",
        },
    )
    assert stream.finish("completed", "Option B, at half the cost.") is None
    replies = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    assert [(event["author"], event["text"]) for event in replies] == [
        ("agent", "Comparing the options. Then the pricing."),
        ("user", "And the cost?"),
        ("agent", "Option B, at half the cost."),
    ]
    progress, _, final = replies
    assert progress["ephemeral"] and progress["start"]["item"] == comment["id"]
    assert "responds" not in final
    [owed_answer] = owed(state_json(page_dir))
    assert owed_answer["input"] == asked["id"]


@pytest.mark.parametrize("rich", ["question", "markup"])
@pytest.mark.parametrize("author", ["codex-thread", "worker-1"])
def test_provider_response_commits_full_content_before_reconnect(
    page_dir, monkeypatch, rich, author
):
    comment, target, delivery_id, stream = _reserved_author_response(page_dir)
    monkeypatch.setattr(
        thread_model,
        "message_identity",
        lambda: {"session": author, "agent": "Worker"},
    )
    markup = '<lf-options id="provider-choice"><lf-option id="provider-yes" label="Yes"><strong>Yes</strong></lf-option></lf-options>'
    shown = QUESTION if rich == "question" else markup
    flags = {
        "question": [
            "--title",
            "Storage choice",
            "--section",
            "plan",
        ],
        "markup": [
            "--done",
            "--title",
            "Storage choice",
            "--section",
            "plan",
        ],
    }[rich]
    authored = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            target["ref"],
            "--text",
            f"Choose the store.\n\n{shown}",
            *flags,
        ],
    )
    assert authored.exit_code == 0, authored.output
    assert json.loads(authored.output)["kind"] == "reply"
    stream.disconnect()
    # Reconnecting cannot replace the answer already committed by the author.
    thread_model.reserve_delivery_reply("codex-thread", delivery_id, target)
    recovered = codex_model.AppServerReplyStream(
        "codex-thread", "author-turn", delivery_id, target
    )
    recovered.restore("Provider opening after reconnect")
    assert recovered.finish("completed", "Provider completion text") is None
    [reply] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    assert (reply["parent"], reply["responds"], reply["text"], reply["title"]) == (
        comment["id"],
        comment["id"],
        f"Choose the store.\n\n{shown}",
        "Storage choice",
    )
    assert reply["anchor"]["section"] == "plan"
    assert (reply["session"], reply["agent"]) == (author, "Worker")
    retried = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            target["ref"],
            "--text",
            f"Choose the store.\n\n{shown}",
            *flags,
        ],
    )
    assert retried.exit_code == 0, retried.output
    assert json.loads(retried.output) == reply
    assert not thread_model.delivery_reply_reserved("codex-thread", delivery_id, target)
    assert (
        thread_model.build_threads(events_model.read_events(page_dir), {})[
            comment["id"]
        ]["title"]
        == "Storage choice"
    )


@pytest.mark.parametrize("reacquired", [False, True])
def test_history_recovery_and_author_retry_survive_owner_process_restart(
    page_dir, capsys, reacquired
):
    comment, target, delivery_id, _stream = _reserved_author_response(page_dir)
    identity = {"session": "worker-1", "agent": "Indexer"}
    thread_model.post_response(
        target["ref"], f"Worker question?\n\n{QUESTION}", identity=identity
    )
    payload = delivery_model.read_delivery(delivery_id)
    before = cleanup_model.session_record("codex-thread")
    cleanup_model.ensure_session("codex-thread", {"pid": os.getppid()})
    if reacquired:
        with transaction_model.PageTransaction(page_dir) as page:
            page.take_claim(
                harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid())
            )
    turn_record = cleanup_model.session_record("codex-thread")
    assert turn_record is not None
    assert before is not None
    assert turn_record["generation"] != before["generation"]
    _observer()._resume(
        {
            "status": {"type": "idle"},
            "turns": [
                {
                    "id": "author-turn",
                    "status": "completed",
                    "itemsView": "full",
                    "items": [
                        {
                            "id": "delivery",
                            "type": "functionCallOutput",
                            "name": "leaf_delivery",
                            "output": json.dumps(payload),
                        },
                        {
                            "id": "final",
                            "type": "agentMessage",
                            "phase": "final_answer",
                            "text": "Recovered provider final",
                        },
                    ],
                }
            ],
        }
    )
    errors = capsys.readouterr().err
    assert isinstance(
        codex_model.read_task_delivery("codex-thread", delivery_id),
        codex_model.Accepted,
    )
    [answer] = thread_model.successful_replies(
        events_model.read_events(page_dir), comment["id"]
    )
    assert (answer["text"], answer["session"], answer["agent"]) == (
        f"Worker question?\n\n{QUESTION}",
        "worker-1",
        "Indexer",
    ), errors
    assert (
        thread_model.post_response(
            target["ref"],
            f"Worker question?\n\n{QUESTION}",
            identity=identity,
        )
        == answer
    )


@pytest.mark.parametrize("ending", ["interrupted", "completed"])
def test_explicit_answer_survives_a_provider_ending_without_final_text(
    page_dir, ending
):
    comment, target, _delivery_id, stream = _reserved_author_response(page_dir)
    answer = thread_model.post_response(
        target["ref"],
        f"My question?\n\n{QUESTION}",
        identity={"session": "codex-thread", "agent": "Codex"},
    )
    assert stream.finish(ending) is None
    assert thread_model.successful_replies(
        events_model.read_events(page_dir), comment["id"]
    ) == [answer]
    assert comment["id"] not in delivery_model.current_responses(
        page_dir, events_model.read_events(page_dir)
    )
    assert (
        thread_model.post_response(
            target["ref"],
            f"My question?\n\n{QUESTION}",
            identity={"session": "codex-thread", "agent": "Codex"},
        )
        == answer
    )


def test_addressed_progress_uses_active_revision_and_starts_work_atomically(page_dir):
    revisioning_model.activate_source(page_dir)
    source = page_dir / "index.html"
    original = source.read_text()
    active = files_model.latest_revision(page_dir)
    comment = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Answer this"}
    )
    reference = response_reference(page_dir, comment)
    # Progress is the Working line, so the kernel schema holds it to one line.
    with pytest.raises(Refused) as refused:
        thread_model.post_response(reference, "Checking\nthe store.", ephemeral=True)
    assert refused_on(refused.value).values["field"] == "/text"
    source.write_text("<lf-unknown>Unfinished draft</lf-unknown>")
    progress = thread_model.post_response(
        reference, "Checking the store.\n", ephemeral=True
    )
    assert files_model.latest_revision(page_dir) == active
    assert source.read_text() == "<lf-unknown>Unfinished draft</lf-unknown>"
    events = events_model.read_events(page_dir)
    assert [event["kind"] for event in events] == ["comment", "reply"]
    assert progress is not None
    assert progress["start"]["item"] == comment["id"]
    assert todos_model.item_starts(events)[comment["id"]]["id"] == progress["id"]
    assert comment["id"] in delivery_model.current_responses(page_dir, events)
    # Progress by message id names no pending input, so it posts taking nothing in
    # hand, and the update stays owed under the start the addressed progress wrote.
    proactive = thread_model.post_reply(
        page_dir, {"parent": comment["id"]}, "Proactive", ephemeral=True
    )
    assert proactive is not None
    assert "start" not in proactive
    events = events_model.read_events(page_dir)
    assert todos_model.item_starts(events)[comment["id"]]["id"] == progress["id"]
    assert comment["id"] in delivery_model.current_responses(page_dir, events)
    source.write_text(original + "<!-- pending edit -->")
    thread_model.post_response(reference, "Verifying the store.", ephemeral=True)
    assert files_model.latest_revision(page_dir) == active
    assert source.read_text() == original + "<!-- pending edit -->"
    answer = thread_model.post_response(reference, "The durable answer.")
    assert files_model.latest_revision(page_dir) != active
    assert answer is not None
    assert answer["responds"] == comment["id"]
    assert comment["id"] not in delivery_model.current_responses(
        page_dir, events_model.read_events(page_dir)
    )


@pytest.mark.parametrize("obsolete", ["record", "envelope"])
def test_codex_ignores_obsolete_addressed_envelopes_and_recaptures_input(
    page_dir, obsolete
):
    prepared = _codex_delivery(page_dir)
    identity = prepared.payload["id"]
    path = codex_model.record_path("codex-thread", identity)
    record = files_model.read_json(codex_model.RECORD.file(path))
    record.update(state="queued", pending=[0])
    if obsolete == "record":
        # The record is one a Leaf of another shape wrote.
        file = path.with_name(f"{path.stem}@999{path.suffix}")
        codex_model.RECORD.remove(path)
        record["format"] = "leaf-codex-delivery/999"
    else:
        # The envelope this Leaf's record addresses is one a Leaf of another shape
        # froze.
        envelope = delivery_model.delivery_path(identity)
        delivery_model.DELIVERY.remove(envelope)
        cleanup_model.write_json(
            envelope.with_name(f"{envelope.stem}@999{envelope.suffix}"),
            dict(prepared.payload, format="leaf-delivery/999"),
        )
        file = codex_model.RECORD.file(path)
    cleanup_model.write_json(file, record)
    held = file.read_bytes()
    assert codex_model.read_record(path) is None
    assert not codex_model.recover_codex_receipt("codex-thread")
    assert acknowledged_through(page_dir) == 0
    fresh = codex_model.prepare_codex_delivery(
        page_dir, harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid())
    )
    assert fresh.payload["id"] != identity
    assert fresh.payload["format"] == delivery_model.DELIVERY.format
    assert fresh.payload["batches"][0]["events"][0]["answer"]["ref"].startswith(
        fresh.payload["id"]
    )
    # Another checkout's record is not ours to retire.
    assert file.read_bytes() == held


def test_explicit_rich_reply_is_committed_before_later_invalid_source(page_dir):
    comment, target, delivery_id, stream = _reserved_author_response(page_dir)
    answer = thread_model.post_response(
        target["ref"],
        "Committed answer",
        section="plan",
        identity={"session": "codex-thread", "agent": "Codex"},
    )
    (page_dir / "index.html").write_text("<lf-unknown>Invalid</lf-unknown>")
    assert stream.finish("completed", "Provider fallback text") is None
    assert thread_model.successful_replies(
        events_model.read_events(page_dir), comment["id"]
    ) == [answer]
    assert not thread_model.delivery_reply_reserved("codex-thread", delivery_id, target)


def test_committed_answer_survives_a_newer_displayed_reply(page_dir):
    comment, target, _delivery_id, old = _reserved_author_response(page_dir)
    identity = {"session": "codex-thread", "agent": "Codex"}
    thread_model.post_response(
        target["ref"], f"Older question?\n\n{QUESTION}", identity=identity
    )
    newer = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Another thread"},
    )
    with transaction_model.PageTransaction(page_dir) as transaction:
        batch = delivery_model.batch_data(page_dir, transaction, [newer])
    payload = delivery_model.freeze_delivery([batch], turn_replies=True)
    new_target = codex_model.stream_reply_target(payload)
    assert new_target is not None
    thread_model.reserve_delivery_reply("codex-thread", payload["id"], new_target)
    cleanup_model.prompt_turn("codex-thread", "newer-turn")
    new = codex_model.AppServerReplyStream(
        "codex-thread", "newer-turn", payload["id"], new_target
    )
    assert new.restore("Newer opening"), service_model.page_claim(page_dir)
    assert old.finish("completed", "Old provider final") is None
    [reply] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    assert (reply["responds"], reply["text"]) == (
        comment["id"],
        f"Older question?\n\n{QUESTION}",
    )
    stream = read_record(page_dir / "stream.json")
    assert stream["reply"]["text"] == "Newer opening"
    assert newer["id"] in stream["reply_reservations"]
    assert comment["id"] not in stream["reply_reservations"]


def test_a_message_by_id_beside_a_reserved_answer_names_the_addressed_reply(page_dir):
    """Rich content posted by message id into a thread a turn's answer is reserved
    for answers nothing: it goes in, and the note names the addressed reply that
    answers, which then commits ahead of the provider's final."""
    comment, target, _delivery_id, stream = _reserved_author_response(page_dir)
    markup = '<lf-options id="corrected-choice"><lf-option id="corrected-yes">Yes</lf-option></lf-options>'
    runner = CliRunner()
    beside = runner.invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            comment["id"],
            "--text",
            "Choosing next.",
            "--title",
            "Thread title",
        ],
    )
    assert beside.exit_code == 0, beside.output
    [owed] = json.loads(beside.stdout)["findings"]
    assert owed["code"] == "owed-response"
    assert "leaf thread reply <answer.ref>" in owed["text"]
    corrected = runner.invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            target["ref"],
            "--text",
            f"Choose.\n\n{markup}",
        ],
    )
    assert corrected.exit_code == 0, corrected.output
    answer = json.loads(corrected.output)
    assert markup in answer["text"]
    assert stream.finish("completed", "Provider final") is None
    assert thread_model.successful_replies(
        events_model.read_events(page_dir), comment["id"]
    ) == [answer]


@pytest.mark.parametrize("invalid", ["source", "html", "title"])
def test_explicit_reply_refusal_reaches_its_author_before_commit(page_dir, invalid):
    comment, target, _delivery_id, stream = _reserved_author_response(page_dir)
    identity = {"session": "codex-thread", "agent": "Codex"}
    source = (page_dir / "index.html").read_text()
    before_revision = files_model.latest_revision(page_dir)
    (page_dir / "index.html").write_text(
        "<lf-unknown>Invalid</lf-unknown>"
        if invalid == "source"
        else source + "<!-- edited -->"
    )
    before = events_model.read_events(page_dir)
    with pytest.raises(Refused):
        thread_model.post_response(
            target["ref"],
            'Invalid\n\n<lf-unknown id="bad"></lf-unknown>'
            if invalid == "html"
            else "Invalid",
            identity=identity,
            title="" if invalid == "title" else None,
        )
    assert events_model.read_events(page_dir) == before
    assert files_model.latest_revision(page_dir) == before_revision
    (page_dir / "index.html").write_text(source)
    answer = thread_model.post_response(
        target["ref"],
        f"Corrected question?\n\n{QUESTION}",
        identity=identity,
    )
    assert stream.finish("completed", "Provider final") is None
    assert thread_model.successful_replies(
        events_model.read_events(page_dir), comment["id"]
    ) == [answer]
    assert answer is not None
    assert QUESTION in answer["text"]


def test_markup_obligation_cannot_be_discharged_by_reply_or_reply_failure(page_dir):
    source = PAGE.replace(PAGE_GROUP, '<lf-options id="plan-choice" multiple>', 1)
    (page_dir / "index.html").write_text(source)
    publish(page_dir)
    action = append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "plan-choice",
            "action": "answer",
            "detail": {},
        },
    )
    reference = response_reference(page_dir, action)
    variants: tuple[ResponseOptions, ...] = (
        {},
        {"ephemeral": True},
        {"failure": "unavailable"},
    )
    for options in variants:
        before = events_model.read_events(page_dir)
        with pytest.raises(Refused) as refused:
            thread_model.post_response(reference, "This is not a revision.", **options)
        assert refused_on(refused.value).code == "not-a-reply"
        assert events_model.read_events(page_dir) == before
    started = tasks_model.cmd_start(
        page_dir, action["id"], "Recording the selected plan."
    )
    assert started["item"] == action["id"]
    with transaction_model.PageTransaction(page_dir) as page:
        delivery_model.record_pickup(
            page, [action], phase="failed", failure="turn_failed"
        )
    state = page_state(page_dir)
    [workflow] = state["workflows"]
    [record] = served_updates(state["browser"])
    assert (workflow["obligation"], record["next_actor"]) == (record["id"], "user")
    assert (workflow["state"], workflow["reason"]) == ("blocked", "failed")
    assert owed_answers(page_dir) == []
    assert not any(
        event["kind"] == "reply" for event in events_model.read_events(page_dir)
    )


@pytest.mark.parametrize("retry", ["same", "different"])
def test_retry_identity_cannot_take_an_open_reply_reservation(
    page_dir, monkeypatch, retry
):
    revisioning_model.activate_source(page_dir)
    comment = append_command(
        page_dir, {"kind": "comment", "author": "user", "revision": 1, "text": "Why?"}
    )
    with transaction_model.PageTransaction(page_dir) as page:
        page.take_claim(
            harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid())
        )
    earlier = response_reference(page_dir, comment)
    prepared = codex_model.prepare_codex_delivery(
        page_dir, harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid())
    )
    target = codex_model.stream_reply_target(prepared.payload)
    assert target is not None
    thread_model.reserve_delivery_reply("codex-thread", prepared.payload["id"], target)
    cleanup_model.prompt_turn("codex-thread", "author-turn")
    stream = codex_model.AppServerReplyStream(
        "codex-thread", "author-turn", prepared.payload["id"], target
    )
    identity = {"session": "codex-thread", "agent": "Codex"}
    monkeypatch.setattr(thread_model, "message_identity", lambda: identity)
    attempt = (
        thread_model.delivery_reply_attempt(prepared.payload["id"])
        if retry == "same"
        else "another-retry"
    )
    with pytest.raises(Refused, match="leaf thread reply"):
        thread_model.post_reply(
            page_dir,
            {"parent": comment["id"], "responds": comment["id"]},
            "Premature",
            attempt=attempt,
            identity=identity,
        )
    authored = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            earlier,
            "--text",
            "Committed by author",
            "--title",
            "Thread title",
        ],
    )
    assert authored.exit_code == 0, authored.output
    assert json.loads(authored.output)["kind"] == "reply"
    assert stream.finish("completed", "Provider final") is None
    [answer] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    assert answer["text"] == "Committed by author"
    assert answer["attempt"] != thread_model.delivery_reply_attempt(
        prepared.payload["id"]
    )
    retried = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            earlier,
            "--text",
            "Committed by author",
            "--title",
            "Thread title",
        ],
    )
    assert retried.exit_code == 0, retried.output
    assert json.loads(retried.output) == answer


def test_failure_reply_is_refused_while_provider_still_owns_the_answer(page_dir):
    comment, target, delivery_id, stream = _reserved_author_response(page_dir)
    with pytest.raises(Refused, match="leaf thread reply"):
        thread_model.post_response(
            target["ref"],
            "No answer is coming.",
            failure="unavailable",
            identity={"session": "codex-thread", "agent": "Codex"},
        )
    assert not thread_model.successful_replies(
        events_model.read_events(page_dir), comment["id"]
    )
    assert thread_model.delivery_reply_reserved("codex-thread", delivery_id, target)
    assert stream.finish("completed", "Provider final") is None
    assert (
        thread_model.successful_replies(
            events_model.read_events(page_dir), comment["id"]
        )[0]["text"]
        == "Provider final"
    )


def test_a_final_into_a_thread_the_user_resolved_leaves_it_closed(page_dir, capfd):
    """A provider's final message goes into a thread the user resolved without
    reopening it, as an answer by command does. Leaf says nothing beside it: no
    agent reads what a provider's process prints, so the note a command prints of a
    thread that stayed closed would reach nobody."""
    comment, _target, _delivery_id, stream = _reserved_author_response(page_dir)
    append_command(
        page_dir, {"kind": "resolve", "author": "user", "parent": comment["id"]}
    )
    capfd.readouterr()
    assert stream.finish("completed", "No badge exists.") is None
    final = events_model.read_events(page_dir)[-1]
    assert (final["responds"], final["unannounced"]) == (comment["id"], True)
    [thread] = state_json(page_dir)["threads"]
    assert thread["resolved"] == "user"
    assert "stays-closed" not in capfd.readouterr().err


@pytest.mark.parametrize("settled", [False, True])
def test_old_provider_final_yields_to_new_reservation_for_same_input(page_dir, settled):
    comment, _target, _delivery_id, old = _reserved_author_response(page_dir)
    # A later delivery reserves the same captured input under a different attempt.
    with transaction_model.PageTransaction(page_dir) as transaction:
        batch = delivery_model.batch_data(page_dir, transaction, [comment])
    payload = delivery_model.freeze_delivery([batch], turn_replies=True)
    new_target = codex_model.stream_reply_target(payload)
    cleanup_model.prompt_turn("codex-thread", "newer-turn")
    assert new_target is not None
    thread_model.reserve_delivery_reply("codex-thread", payload["id"], new_target)
    new = codex_model.AppServerReplyStream(
        "codex-thread", "newer-turn", payload["id"], new_target
    )
    identity = {"session": "codex-thread", "agent": "Codex"}
    thread_model.post_response(
        new_target["ref"],
        f"New owner's question?\n\n{QUESTION}",
        identity=identity,
    )
    if settled:
        append_command(
            page_dir, {"kind": "resolve", "author": "user", "parent": comment["id"]}
        )
    assert old.finish("completed", "Old recovered final") is None
    assert (
        len(
            thread_model.successful_replies(
                events_model.read_events(page_dir), comment["id"]
            )
        )
        == 1
    )
    assert thread_model.delivery_reply_reserved(
        "codex-thread", payload["id"], new_target
    )
    assert new.finish("completed", "New provider final") is None
    [answer] = [
        event
        for event in events_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    assert (answer["responds"], answer["text"]) == (
        comment["id"],
        f"New owner's question?\n\n{QUESTION}",
    )
