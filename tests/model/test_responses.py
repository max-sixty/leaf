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
from conftest import LEAF_COMMAND
from interact_support import (
    PAGE,
    _codex_delivery,
    _observer,
    acknowledged_through,
    append_carried_log_record,
    append_command,
    command_findings,
    delivered_ref,
    delivery_through,
    last_deliverable_seq,
    owed_answers,
    page_state,
    publish,
    read_record,
    receive_through,
    record_claim,
    refused_on,
    response_reference,
    served_updates,
)

from leaf import cli as cli_model
from leaf import codex as codex_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import harness as harness_model
from leaf import revisioning as revisioning_model
from leaf import service as service_model
from leaf import state as cleanup_model
from leaf import thread as thread_model
from leaf import todos as todos_model
from leaf.refusals import Refused


class ResponseOptions(TypedDict, total=False):
    ephemeral: bool
    failure: str
    markup: str


QUESTION = (
    '<lf-options id="question" choose><lf-option id="question-a"><strong>A</strong>'
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
    assert refused_on(stale.stderr).code == "superseded-reply"

    current = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, second["id"]),
            "--text",
            "Used B.",
        ],
    )
    assert current.exit_code == 0, current.output
    assert events_model.read_events(page_dir)[-1]["responds"] == second["id"]


@pytest.mark.parametrize("markup", ["", "<p>Here is the table.</p>"])
def test_an_answer_that_declares_nothing_is_refused(page_dir, markup):
    asked = append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": "Which one?"}
    )
    before = events_model.read_events(page_dir)
    reply = ["thread", "reply", response_reference(page_dir, asked), "--text", "B."]
    refused = CliRunner().invoke(cli_model.cli, [*reply, "--markup", markup])

    assert refused.exit_code != 0
    assert refused_on(refused.stderr).code == "undeclared-answer"
    assert events_model.read_events(page_dir) == before


def test_a_message_asks_by_its_widget_or_its_words_not_both(page_dir):
    """Only the user's words answer `--obligation`, so beside a widget that asks it
    would keep the message on On me after the user picks. Both writers refuse it."""
    revisioning_model.activate_source(page_dir)
    asked = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Which one?"},
    )
    before = events_model.read_events(page_dir)
    for command in (
        ["thread", "reply", response_reference(page_dir, asked)],
        ["thread", "create", str(page_dir)],
    ):
        refused = CliRunner().invoke(
            cli_model.cli,
            [*command, "--obligation", "--text", "Which?", "--markup", QUESTION],
        )
        assert refused.exit_code != 0
        assert refused_on(refused.stderr).code == "obligation-beside-widget"
    assert events_model.read_events(page_dir) == before


def test_a_refusal_names_a_ref_only_while_its_owner_holds_the_page(
    claimed, monkeypatch
):
    """A refusal on an owed message names the exact `answer.ref` its receipt
    recorded. Once another session claims the page the reply writer refuses that
    reference, so the refusal stops naming it and names the `leaf wait` that hands
    the message to the new owner with a reference of its own."""
    asked = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "why B?"}
    )
    earlier = delivery_through(claimed, last_deliverable_seq(claimed))
    delivery_model.receive_delivery(earlier)
    ref = delivered_ref(claimed, asked["id"])
    reply = ["thread", "reply", str(claimed), asked["id"], "--text", "B"]
    refused = CliRunner().invoke(cli_model.cli, reply)
    assert refused.exit_code == 1
    assert f"`leaf thread reply {ref}` answers it" in refused.output

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s2")
    assert service_model.claim_page(claimed)
    refused = CliRunner().invoke(cli_model.cli, reply)
    assert refused.exit_code == 1
    assert ref not in refused.output
    assert f"`leaf wait {claimed}` delivers for {asked['id']}" in refused.output

    # A delivery captured under the new claim gives it a ref of its own, which a
    # late receipt of the earlier owner's delivery neither hides nor records again.
    receive_through(claimed, last_deliverable_seq(claimed))
    successor = delivered_ref(claimed, asked["id"])
    assert successor != ref
    pickups = len(
        [e for e in events_model.read_events(claimed) if e["kind"] == "pickup"]
    )
    delivery_model.receive_delivery(earlier)
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
            ["thread", "reply", response_reference(page_dir, asked), "--done"]
            + ["--text", "Tidied."],
        )
        assert posted.exit_code == 0, posted.output
        return [json.loads(line) for line in posted.stderr.splitlines()]

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
                    reference, "Checking.", ephemeral=True, markup="<p>Checking.</p>"
                )
            assert refused_on(refused.value).code == "ephemeral-content"
        options: ResponseOptions = (
            {"ephemeral": True}
            if earlier == "progress"
            else {"failure": "unavailable", "markup": "<p>Unavailable.</p>"}
        )
        thread_model.post_response(
            reference,
            "Checking." if earlier == "progress" else "Unavailable.",
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
        with service_model.PageTransaction(page) as transaction:
            batches.append(delivery_model.batch_data(page, transaction, [asked]))
    payload = delivery_model.freeze_delivery(batches)
    refs = [batch["events"][0]["answer"]["ref"] for batch in payload["batches"]]
    assert refs[0] != refs[1]
    for page, reference in zip((page_dir, other), refs, strict=True):
        posted = CliRunner().invoke(
            cli_model.cli,
            ["thread", "reply", "--done", reference, "--text", str(page)],
        )
        assert posted.exit_code == 0, posted.output
        retry = CliRunner().invoke(
            cli_model.cli,
            ["thread", "reply", "--done", reference, "--text", "Retried"],
        )
        assert retry.exit_code == 0, retry.output
        assert json.loads(posted.output) == json.loads(retry.output)
        replies = [
            event
            for event in events_model.read_events(page)
            if event["kind"] == "reply"
        ]
        assert len(replies) == 1
        assert (replies[0]["parent"], replies[0]["responds"], replies[0]["text"]) == (
            "same-id",
            "same-id",
            str(page),
        )


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
            "Choose",
            "--markup",
            '<lf-unknown id="bad"></lf-unknown>',
            "--title",
            "Options",
        ],
    )
    assert invalid.exit_code != 0
    assert not any(
        event["kind"] == "thread_title" for event in events_model.read_events(page_dir)
    )
    markup = '<lf-options id="response-options" choose><lf-option id="response-yes"><strong>Yes</strong></lf-option></lf-options>'
    posted = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            reference,
            "--text",
            "Choose here.",
            "--markup",
            markup,
            "--title",
            "Options",
            "--section",
            "plan",
        ],
    )
    assert posted.exit_code == 0, posted.output
    records = [json.loads(line) for line in posted.output.splitlines()]
    assert [event["kind"] for event in records] == ["reply"]
    assert records[0]["markup"] == markup
    assert records[0]["anchor"]["section"] == "plan"
    assert records[0]["title"] == "Options"
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
    # A widget input is answered on its frozen message, not on its own event id.
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
            "Which store owns it?",
            "--markup",
            QUESTION,
            "--detach",
        ],
    )
    assert questioned.exit_code == 0, questioned.output
    record = json.loads(questioned.output)
    assert record["parent"] == asked["id"]
    assert record["responds"] == selected["id"]
    assert record["markup"] == QUESTION
    assert record["anchor"] is None


def test_response_refuses_stale_replaced_foreign_and_reserved_inputs(
    page_dir, monkeypatch
):
    def cli_refuses(reference, text, reason):
        args = ["thread", "reply", "--done", reference, "--text", text]
        refused = CliRunner().invoke(cli_model.cli, args)
        assert refused.exit_code == 1
        assert reason in json.loads(refused.stderr)["error"]
        assert isinstance(refused.exception, SystemExit)
        launched = subprocess.run(
            [*LEAF_COMMAND, *args], capture_output=True, text=True, check=False
        )
        assert launched.returncode == 1, (launched.stdout, launched.stderr)
        assert launched.stdout == ""
        assert launched.stderr == refused.stderr

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
                "from click.testing import CliRunner; from leaf.cli import cli; import sys; "
                "assert 'leaf.delivery' not in sys.modules; "
                "result = CliRunner().invoke(cli, ['thread', 'reply', '--help']); "
                "assert result.exit_code == 0, result.output; "
                "assert 'leaf.delivery' not in sys.modules"
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
    with service_model.PageTransaction(claimed) as page:
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
    assert "claim no longer matches its delivery" in result.stderr
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
    with service_model.PageTransaction(claimed) as page:
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
        ],
    )
    assert progress.exit_code == 0, progress.output
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
    # An answer to the same reference is not a retry of the receipt: it is refused
    # as an answer to a settled input rather than handed the receipt back.
    [answered] = command_findings(
        "thread", "reply", reference, "--done", "--text", "Here it is."
    )
    assert answered.code == "superseded-reply"
    assert [event["id"] for event in events_model.read_events(page_dir)][-1] == (
        reply["id"]
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


def test_a_turns_opening_posts_as_progress_where_it_was_said(page_dir):
    """A provider turn's opening is the agent's progress line, as any harness's first
    line is: once complete it posts once, taking the update in hand, so a message the
    user sends during the turn follows it, and the answer the turn commits is its
    final message alone. An opening of several paragraphs posts as the one line
    progress is, and one whose completion a reconnect missed posts as the next item
    begins."""
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
    progress, _, answer = replies
    assert progress["ephemeral"] and progress["start"]["item"] == comment["id"]
    assert answer["responds"] in {comment["id"], asked["id"]}


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
    markup = '<lf-options id="provider-choice" choose><lf-option id="provider-yes"><strong>Yes</strong></lf-option></lf-options>'
    flags = {
        "question": [
            "--markup",
            QUESTION,
            "--title",
            "Storage choice",
            "--section",
            "plan",
        ],
        "markup": [
            "--done",
            "--markup",
            markup,
            "--title",
            "Storage choice",
            "--section",
            "plan",
        ],
    }[rich]
    authored = CliRunner().invoke(
        cli_model.cli,
        ["thread", "reply", target["ref"], "--text", "Choose the store.", *flags],
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
        "Choose the store.",
        "Storage choice",
    )
    if rich == "question":
        assert reply["markup"] == QUESTION
        assert reply["anchor"]["section"] == "plan"
    else:
        assert reply["markup"] == markup
        assert reply["anchor"]["section"] == "plan"
    assert (reply["session"], reply["agent"]) == (author, "Worker")
    retried = CliRunner().invoke(
        cli_model.cli,
        ["thread", "reply", target["ref"], "--text", "Choose the store.", *flags],
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
        target["ref"], "Worker question?", markup=QUESTION, identity=identity
    )
    payload = delivery_model.read_delivery(delivery_id)
    before = cleanup_model.session_record("codex-thread")
    cleanup_model.ensure_session("codex-thread", {"pid": os.getppid()})
    if reacquired:
        with service_model.PageTransaction(page_dir) as page:
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
    assert (answer["text"], answer["session"], answer["agent"], answer["markup"]) == (
        "Worker question?",
        "worker-1",
        "Indexer",
        QUESTION,
    ), errors
    assert (
        thread_model.post_response(
            target["ref"], "Worker question?", markup=QUESTION, identity=identity
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
        "My question?",
        markup=QUESTION,
        identity={"session": "codex-thread", "agent": "Codex"},
    )
    assert stream.finish(ending) is None
    assert thread_model.successful_replies(
        events_model.read_events(page_dir), comment["id"]
    ) == [answer]
    assert comment["id"] not in delivery_model.current_responses(
        page_dir, events_model.read_events(page_dir)
    )
    assert thread_model.post_response(target["ref"], "Retry", markup=QUESTION) == answer
    with pytest.raises(Refused) as refused:
        thread_model.post_response(target["ref"], "Retry", todo="Promise it")
    assert refused_on(refused.value).code == "redeclared-answer"


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
    # A proactive command cannot infer which pending input this progress means.
    with pytest.raises(Refused) as refused:
        thread_model.post_reply(
            page_dir, {"parent": comment["id"]}, "Proactive", ephemeral=True
        )
    assert refused_on(refused.value).code == "owed-response"
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
    record = files_model.read_json(path)
    if obsolete == "record":
        record["format"] = "leaf-codex-delivery-v2"
    else:
        payload = dict(prepared.payload, format="leaf-delivery-v4")
        cleanup_model.write_json(delivery_model.delivery_path(identity), payload)
    record.update(state="queued", pending=[0])
    cleanup_model.write_json(path, record)
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
    assert path.exists()  # another checkout's record is not ours to retire


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
        target["ref"], "Older question?", markup=QUESTION, identity=identity
    )
    newer = append_command(
        page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Another thread"},
    )
    with service_model.PageTransaction(page_dir) as transaction:
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
    assert (reply["responds"], reply["text"], reply["markup"]) == (
        comment["id"],
        "Older question?",
        QUESTION,
    )
    stream = read_record(page_dir / "stream.json")
    assert stream["reply"]["text"] == "Newer opening"
    assert newer["id"] in stream["reply_reservations"]
    assert comment["id"] not in stream["reply_reservations"]


def test_bound_thread_refusal_routes_rich_content_to_addressed_reply(page_dir):
    comment, target, _delivery_id, stream = _reserved_author_response(page_dir)
    markup = '<lf-options id="corrected-choice" choose><lf-option id="corrected-yes">Yes</lf-option></lf-options>'
    runner = CliRunner()
    refused = runner.invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            comment["id"],
            "--text",
            "Choose.",
            "--markup",
            markup,
        ],
    )
    assert refused.exit_code != 0
    assert "leaf thread reply <answer.ref>" in refused.output
    corrected = runner.invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            target["ref"],
            "--text",
            "Choose.",
            "--markup",
            markup,
        ],
    )
    assert corrected.exit_code == 0, corrected.output
    answer = json.loads(corrected.output)
    assert answer["markup"] == markup
    assert stream.finish("completed", "Provider final") is None
    assert thread_model.successful_replies(
        events_model.read_events(page_dir), comment["id"]
    ) == [answer]


@pytest.mark.parametrize("invalid", ["source", "markup", "title"])
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
    options = {
        "source": {},
        "markup": {"markup": '<lf-unknown id="bad"></lf-unknown>'},
        "title": {"title": ""},
    }[invalid]
    before = events_model.read_events(page_dir)
    with pytest.raises(Refused):
        thread_model.post_response(
            target["ref"], "Invalid", identity=identity, **options
        )
    assert events_model.read_events(page_dir) == before
    assert files_model.latest_revision(page_dir) == before_revision
    (page_dir / "index.html").write_text(source)
    answer = thread_model.post_response(
        target["ref"], "Corrected question?", markup=QUESTION, identity=identity
    )
    assert stream.finish("completed", "Provider final") is None
    assert thread_model.successful_replies(
        events_model.read_events(page_dir), comment["id"]
    ) == [answer]
    assert answer is not None
    assert answer["markup"] == QUESTION


def test_markup_obligation_cannot_be_discharged_by_reply_or_reply_failure(page_dir):
    source = PAGE.replace(
        "<lf-options>", '<lf-options id="plan-choice" choose multiple>', 1
    )
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
    started = todos_model.cmd_start(
        page_dir, action["id"], "Recording the selected plan."
    )
    assert started["item"] == action["id"]
    with service_model.PageTransaction(page_dir) as page:
        delivery_model.record_pickup(
            page, [action], phase="failed", failure="turn_failed"
        )
    state = page_state(page_dir)
    [workflow] = state["workflows"]
    [record] = served_updates(state["browser"])
    assert (workflow["obligation"], record["next_actor"]) == (record["id"], "user")
    assert workflow["condition"]["kind"] == "failed"
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
    with service_model.PageTransaction(page_dir) as page:
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


@pytest.mark.parametrize("settled", [False, True])
def test_old_provider_final_yields_to_new_reservation_for_same_input(page_dir, settled):
    comment, _target, _delivery_id, old = _reserved_author_response(page_dir)
    # A later delivery reserves the same captured input under a different attempt.
    with service_model.PageTransaction(page_dir) as transaction:
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
        new_target["ref"], "New owner's question?", markup=QUESTION, identity=identity
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
    assert (answer["responds"], answer["text"], answer["markup"]) == (
        comment["id"],
        "New owner's question?",
        QUESTION,
    )
