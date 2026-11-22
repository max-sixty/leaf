"""The layer's `$` contract: how layers merge its members, the event handling and routes
each delivery tells the agent, and the docs held to it."""

import itertools
import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest
from click.testing import CliRunner
from interact_support import (
    Prose,
    command_findings,
    command_notes,
    fetch,
    found,
    page_packages,
    publish,
    registry_refusal,
    shipped_core_registry,
    yaml_document,
)

from leaf import cli as cli_model
from leaf import codex as codex_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import harness as harness_model
from leaf import hooks as hooks_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf.findings import Finding
from leaf.json_block import read_json_block
from leaf.registry import contract as registry_contract
from leaf.registry import layer as registry_layer
from leaf.registry import storage as registry_storage
from leaf.registry import validation as registry_validation
from leaf_dev.page_fixtures import package_selection_args
from model.interact_contract import vocabulary


@pytest.mark.parametrize(
    ("changes", "keyword", "path"),
    [
        ({"description": " \n\t"}, "pattern", ["description"]),
        ({"example": " \n\t"}, "pattern", ["example"]),
        ({"example": False}, "type", ["example"]),
        ({"example": None}, "required", []),
        ({"instructions": ""}, "pattern", ["instructions"]),
        ({"work": True}, "additionalProperties", []),
    ],
)
def test_idioms_have_nonblank_authoring_fields_and_no_widget_behavior(
    changes, keyword, path
):
    registry = shipped_core_registry()
    entry = {
        "description": "An opening.",
        "example": '<p class="lf-lede">Opening</p>',
    }
    registry[".lf-lede"] = entry
    registry_validation.validate_layer_declarations(registry, "registry.json")
    entry["instructions"] = "Use above a heading."
    registry_validation.validate_layer_declarations(registry, "registry.json")
    for key, value in changes.items():
        if value is None:
            del entry[key]
        else:
            entry[key] = value
    refused = registry_refusal(
        lambda: registry_validation.validate_layer_declarations(
            registry, "registry.json"
        )
    )
    assert found(
        [refused], "idiom-schema", selector=".lf-lede", keyword=keyword, path=path
    )


def test_layer_facts_read_names_whole_and_an_absent_records_as_null():
    """The layer facts' schema holds names as the hand checks before it did: a
    trailing newline is no part of a token or contract name, and an optional
    `records: null` a package declares reads as absent."""
    kernel = shipped_core_registry()

    def facts(**changes):
        registry = deepcopy(kernel)
        for fact, value in changes.items():
            registry[f"${fact}"] = {**registry[f"${fact}"], **value}
        registry_validation.check_layer_facts(registry, "kernel")

    facts()
    absent = {"description": "Build facts.", "schema": {}, "records": None}
    facts(data={"contracts": {"builds": absent}})
    named = {"description": "Build facts.", "schema": {}}
    refused = registry_refusal(lambda: facts(data={"contracts": {"builds\n": named}}))
    assert refused.values["keyword"] == "pattern"
    refused = registry_refusal(
        lambda: facts(reactions={"tokens": {"keep\n": {"glyph": "+"}}})
    )
    assert refused.values["keyword"] == "pattern"


def test_one_check_names_the_first_departure_in_each_layer_fact():
    """Each layer fact holds its schema independently of the others, so one refusal
    names a departure in each, and only the first within one."""
    registry = shipped_core_registry()
    named = {"description": "Build facts.", "schema": {}}
    registry["$data"] = {"contracts": {"a\n": named, "b\n": named}}
    registry["$reactions"] = {
        **registry["$reactions"],
        "tokens": {"keep\n": {"glyph": "+"}},
    }

    with pytest.raises(registry_contract.RegistryError) as refused:
        registry_validation.check_layer_facts(registry, "kernel")

    assert [finding.values["path"][0] for finding in refused.value.findings] == [
        "$data",
        "$reactions",
    ]


def test_one_check_names_each_missing_layer_fact():
    """A missing fact is named for itself, not folded into another that is missing."""
    registry = shipped_core_registry()
    del registry["$languages"], registry["$tones"]

    with pytest.raises(registry_contract.RegistryError) as refused:
        registry_validation.check_layer_facts(registry, "kernel")

    assert [finding.values["reason"] for finding in refused.value.findings] == [
        "'$languages' is a required property",
        "'$tones' is a required property",
    ]


@pytest.mark.parametrize("section", ["$events", "$languages", "$tones"])
def test_init_inherits_contract_members_a_layer_does_not_state(
    page_dir, tmp_path, section
):
    """$ members merge, so an empty declaration is the same statement as none.

    There is no incomplete $ replacement to refuse: what a layer doesn't state
    is inherited, and the merged registry carries the complete shipped contract."""
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({section: {}}))

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*page_packages(), "./.leaf")),
            str(page_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    merged = registry_storage.load_registry(page_dir)[section]
    shipped = shipped_core_registry()[section]
    assert merged == shipped


def test_a_layer_restates_one_kind_s_handling_and_inherits_the_rest(page_dir, tmp_path):
    """`$events.handling` merges by kind like `$reactions.tokens`: a project layer
    replaces one kind's clauses, deletes one with null, and inherits every other."""
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(
        json.dumps(
            {
                "$events": {
                    "handling": {
                        "comment": [{"text": "Reply in French."}],
                        "reply": None,
                    }
                }
            }
        )
    )

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*page_packages(), "./.leaf")),
            str(page_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    merged = registry_storage.load_registry(page_dir)["$events"]["handling"]
    shipped = cleanup_model.kernel_registry()["$events"]["handling"]
    assert merged["comment"] == [{"text": "Reply in French."}]
    assert "reply" not in merged
    assert merged["resolve"] == shipped["resolve"]


def init_refusal(page_dir) -> Finding:
    """What `page init` of the page's packages and the project layer `.leaf` over
    them stops at."""
    [refused] = command_findings(
        "page",
        "init",
        *package_selection_args((*page_packages(), "./.leaf")),
        str(page_dir),
    )
    return refused


def init_notes(page_dir) -> list[Finding]:
    """What `page init` of the page's packages and the project layer `.leaf` over
    them notes beside the page it initializes."""
    return command_notes(
        "page",
        "init",
        *package_selection_args((*page_packages(), "./.leaf")),
        str(page_dir),
    )


def _handling(clauses):
    return {"handling": clauses}


@pytest.mark.parametrize(
    ("events", "code"),
    [
        (_handling({"comment": []}), "layer-facts"),
        (_handling({"comment": "Reply in French."}), "layer-facts"),
        (_handling({"comment": [{"text": ""}]}), "layer-facts"),
        (
            _handling({"comment": [{"text": "Reply in French.", "tone": "warm"}]}),
            "layer-facts",
        ),
        (
            _handling({"comment": [{"text": "Reply in French.", "when": {"type": 5}}]}),
            "invalid-when",
        ),
        (_handling("Reply in French."), "layer-facts"),
        (_handling(None), "layer-facts"),
    ],
)
def test_init_refuses_instructions_that_a_batch_could_not_carry(
    page_dir, tmp_path, events, code
):
    """Every delivered event reads `$events.handling` and `$events.answering`
    directly, so the door holds a layer to declared kinds and answers and to
    well-formed clauses rather than passing junk to the agent."""
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"$events": events}))

    finding = init_refusal(page_dir)
    assert finding.code == code
    assert next(iter(events)) in json.dumps(finding.values)


@pytest.mark.parametrize(
    "events",
    [
        _handling({"bogus-kind": [{"text": "A clause for no kind."}]}),
        {"answering": {"markdown": [{"text": "A clause for no answer."}]}},
    ],
)
def test_init_advises_on_instructions_for_a_kind_no_batch_carries(
    page_dir, tmp_path, events
):
    """A clause for a kind or answer this Leaf doesn't have reaches no delivery, and a
    package may be written for a newer Leaf's kind, so `page init` composes the layer
    and says the clause has no effect."""
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"$events": events}))

    [advice] = init_notes(page_dir)
    assert (advice.code, advice.severity, advice.values["key"]) == (
        "undeclared-event-kind",
        "advice",
        next(iter(events)),
    )
    assert advice.values["registry"] == str(overlay / "registry.json")


@pytest.mark.parametrize("path", [("verbs", "decide", "unit")], ids="-".join)
def test_init_refuses_a_declaration_the_vocabulary_would_read_unchecked(
    page_dir, tmp_path, path
):
    """A layer's vocabulary stamps each widget's states by reading its declaration
    as valid (`layer.compose_vocabulary`), so `page init` validates the registry first
    and names a declaration that leaves out a field the stamp reads, rather than
    failing inside it."""
    entry = deepcopy(vocabulary(page_dir)["lf-suggestion"])
    *parents, field = path
    held = entry
    for key in parents:
        held = held[key]
    del held[field]
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"lf-suggestion": entry}))

    finding = init_refusal(page_dir)
    assert "lf-suggestion" in json.dumps(finding.json()), finding


def test_the_events_reference_names_the_fields_each_kind_declares():
    """events.md's kind table agrees with `$events.kinds`, the schema admission enforces.

    The table has one row per declared kind, opening on the kind's anchor. A code span in a row's Fields cell that
    opens on a name (`messages: [...]` names `messages`) must be a field that kind
    declares; parentheses hold values and qualifications, not fields. Every field
    the kind requires appears in its row, except those the opening paragraph
    describes once for every kind: the fields all kinds require, `revision`, and
    the posting session's `agent` and `session`.
    """
    from markdown_it import MarkdownIt

    kinds = cleanup_model.kernel_registry()["$events"]["kinds"]
    text = Path(schema_model.__file__).with_name("events.md").read_text()
    tokens = MarkdownIt("commonmark").enable("table").parse(text)
    start = next(
        index for index, token in enumerate(tokens) if token.type == "table_open"
    )
    end = next(
        index
        for index in range(start, len(tokens))
        if tokens[index].type == "table_close"
    )
    source_lines = tokens[start].map
    assert source_lines is not None
    opening = "\n".join(text.splitlines()[: source_lines[0]])
    cells = [token.content for token in tokens[start:end] if token.type == "inline"]
    assert cells[:5] == ["Kind", "Author", "Door", "Fields", "Meaning"]
    shared = set.intersection(
        *(set(kind["record"]["required"]) for kind in kinds.values())
    )
    described_once = shared | {"revision", "agent", "session"}
    assert {name for name in described_once if f"`{name}`" not in opening} == set()

    listed, rows = [], {}
    for kind, _author, _door, cell, _meaning in itertools.batched(cells[5:], 5):
        while (bare := re.sub(r"\([^()]*\)", "", cell)) != cell:
            cell = bare
        # Each kind carries its own anchor, which the site's Data structures page
        # links each kind to (`leaf_dev.docs.EVENTS_REFERENCE`).
        anchored = re.fullmatch(r'<a id="kind-([a-z_]+)"></a>`\1`', kind)
        assert anchored, f'{kind} needs its anchor, <a id="kind-<kind>"></a>'
        listed.append(anchored[1])
        rows[listed[-1]] = {
            match[1]
            for span in re.findall(r"`([^`]*)`", cell)
            if (match := re.match(r"([a-z_]+)(?::|$)", span))
        }
    assert sorted(listed) == sorted(kinds)

    drift = {}
    for name, named in rows.items():
        record = kinds[name]["record"]
        undeclared = named - set(record["properties"])
        missing = set(record["required"]) - described_once - named
        if undeclared or missing:
            drift[name] = {"undeclared": undeclared, "missing": missing}
    assert drift == {}


WALKTHROUGH_PAGE = """<!doctype html>
<html lang="en">
<head>
<title>Backfill</title>
</head>
<body>
<main>
<section id="plan">
  <h2>Plan</h2>
  <p>The nightly backfill moves to Tuesdays so it stops colliding with the report run.</p>
</section>
</main>
</body>
</html>
"""


ROUTE_WALKTHROUGH = """\
What each route hands the agent for one comment
=================================================

A test records this file; nobody writes it by hand. The lines starting with `#`
explain it, and everything else is the recorded data. The run below serves the
page from test_each_case_of_an_event_is_told_what_the_snapshot_shows, posts the
same comment ("why here?" on "moves to Tuesdays") through POST /api/event, and
then lets each of Leaf's four routes deliver it. Only ids, times and the
page's path are pinned, so the file stays the same from run to run.

A route is how new user input reaches the agent's task:

  leaf wait          The agent runs `leaf wait` in the background. It prints
                     the delivery as JSON and exits, and the harness hands that
                     output to the agent as the command's result, which wakes
                     it. The agent acknowledges the delivery itself and waits
                     again, with `leaf delivery ack <delivery-id> && leaf wait`,
                     and answers with `leaf thread reply <answer.ref>`. A Codex
                     task without Leaf's adapter uses this route, and so does a
                     bare shell.
  Claude Code hook   Leaf's native hook watcher runs between turns. When input
                     arrives it wakes the session with one line naming the page,
                     which opens a turn. Leaf's prompt hook runs as that
                     turn begins, and its Stop hook as a turn ends; either
                     freezes the delivery, acknowledges it, and adds it to the
                     turn's context after one line saying so. The agent answers
                     with `leaf thread reply <answer.ref>`.
  Codex queue        Leaf's adapter freezes the delivery and runs `codex queue`
                     with a pointer to it as the task's next user message. The
                     agent reads the delivery with `leaf delivery read <id>`,
                     follows every `next` command, and confirms complete receipt
                     with `leaf delivery ack <id>` before answering with
                     `leaf thread reply <answer.ref>`.
  Codex App Server   Leaf starts a turn with `turn/start`, carrying the
                     delivery as a `leaf_delivery` tool output, and binds the
                     turn's opening and final messages as the reply. Leaf
                     acknowledges the delivery once it enters that turn.
                     leaf.page's hosted agent and a `leaf codex launch`
                     terminal use this route.

CLI readings print bounded, indented JSON. Large deliveries expose numbered
parts and a `next` command; read all parts before acknowledging. A CLI reading
requires explicit receipt even when the original envelope's transport could
confirm it. This comment fits in one reading on every route.

Each route freezes a delivery of its own. The envelope's shape is the same on
all four. Two things differ, each stated once: `acknowledge` says how the agent
confirms the delivery, or is null where the route confirmed it; and the
comment's `answer` is a `reply`, for `leaf thread reply`, except on App Server,
where it is a `turn` the turn's own messages write. The `handling` follows from
the answer, so each agent is told only its own route.
The agent's lasting instructions (its harness contract, and on leaf.page the
developer instructions) are not part of a delivery; test_website_server records
leaf.page's.

What this file records
----------------------

One top-level key per route, holding exactly what reaches the agent's task:

  leaf wait:         its output, from a bare shell.
  Claude Code hook:  the native watch's notification, and the prompt hook's
                     `additionalContext`, split into its instruction line, the
                     delivery's JSON block after it, and what Leaf asks of the
                     turn after that.
  Codex queue:       the `--message` given to `codex queue`, and the output of
                     the `leaf delivery read` it points at.
  Codex App Server:  the `turn/start` params. `toolOutput.output` is the
                     delivery serialized as one line of JSON; it is shown
                     decoded here.

JSON is shown as YAML, and each clause in a batch's `handling` as wrapped prose,
so the four read side by side. Every text is exactly what the agent receives.

After changing what a route sends, re-record this file and review the diff:

  uv run pytest --regtest-reset -n0 tests/model/interact_contract/test_layer_contract.py::test_each_route_hands_the_agent_what_the_snapshot_shows"""


def test_each_route_hands_the_agent_what_the_snapshot_shows(
    snapshot, page_dir, server, capsys, monkeypatch
):
    """The snapshot is the page a developer reads to compare what one comment puts
    in front of the agent on each route: `leaf wait`, Claude Code's hooks, the
    Codex queue's pointer and the delivery it names, and the Codex App Server
    turn. The explicit and Codex captures leave input unconfirmed; the final hook
    capture confirms it. Each is taken from the code that route runs, after one
    real POST, so a change to
    any route's framing or to a delivery's contents shows up as a diff under the
    route it reaches."""
    (page_dir / "index.html").write_text(WALKTHROUGH_PAGE)
    publish(page_dir)
    posted = {
        "kind": "comment",
        "revision": 1,
        "text": "why here?",
        "anchor": {"section": "plan", "quote": "moves to Tuesdays"},
    }
    status, answer = fetch(f"{server}/api/event", data=json.dumps(posted).encode())
    assert status == 200, answer
    logged = events_model.read_events(page_dir)[-1]

    session_model.cmd_waiting(page_dir)
    capsys.readouterr()
    # A bare shell's wait, the printing kind, which claims nothing.
    harness = harness_model.session_harness()
    assert harness is not None
    session = harness.session
    for name in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_PID"):
        monkeypatch.delenv(name)
    assert session_model.cmd_wait(page_dir) == 0
    waited = capsys.readouterr().out
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", session)
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))

    # The adapter's queue route: collect the batch, then offer its pointer.
    with service_model.PageTransaction(page_dir) as transaction:
        append_batch_result = codex_model.append_batch(
            "codex-queue-task",
            page_dir,
            transaction,
            service_model.unacknowledged(transaction.events, transaction.cursor),
        )
        assert append_batch_result is not None
        path, _, _ = append_batch_result
    record_2 = codex_model.read_record(path)
    assert isinstance(record_2, (codex_model.Collecting, codex_model.Offering))
    queued = codex_model.offer_delivery(path, record_2, transport="queue")
    read = json.dumps(
        delivery_model.cmd_delivery_read(queued.payload["id"]), ensure_ascii=False
    )

    thread = "codex-thread"
    prepared = codex_model.prepare_codex_delivery(
        page_dir, harness_model.EmbeddedHarness(thread, "Codex", os.getpid())
    )
    started = codex_model.app_server_turn_start_params(thread, prepared.payload)
    reader = delivery_model.cmd_delivery_read(prepared.payload["id"])
    assert json.loads(started["toolOutput"]["output"]) == prepared.payload
    assert reader["batches"] == prepared.payload["batches"]
    assert f"leaf delivery ack {prepared.payload['id']}" in reader["acknowledge"]

    # Claude Code: the native watcher wakes the session after its turn closes,
    # and the next prompt hook hands the delivery over.
    assert service_model.claim_page(page_dir)
    cleanup_model.close_session_turn(session)
    harness_2 = harness_model.session_harness()
    assert harness_2 is not None
    woke = session_model.watch_between_turns(
        harness_2, {"hook_event_name": "Stop", "session_id": session}
    )
    assert woke is not None
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": session}
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    instruction, _, rest = context.partition("\n\n")
    hooked, attention = read_json_block(rest)

    pinned = {
        logged["id"]: "1946b466",
        logged["ts"]: "2026-09-21T20:12:30-07:00",
        json.loads(waited)["id"]: "11111111",
        queued.payload["id"]: "22222222",
        prepared.payload["id"]: "33333333",
        hooked["id"]: "44444444",
        session: "claude-session",
        # The turn's reply attempt is derived from the delivery id.
        service_model.delivery_reply_attempt(
            prepared.payload["id"]
        ): service_model.delivery_reply_attempt("33333333"),
        str(page_dir): "/path/to/page",
    }

    def pin(shown: str) -> str:
        for actual, steady in pinned.items():
            shown = shown.replace(actual, steady)
        return shown

    def readable(printed: str) -> dict:
        delivery = json.loads(pin(printed))
        delivery["created_at"] = 1790046750.29
        if delivery["acknowledge"] is not None:
            delivery["acknowledge"] = Prose(delivery["acknowledge"])
        for batch in delivery["batches"]:
            batch["handling"] = {
                ref: Prose(text) for ref, text in batch["handling"].items()
            }
        return delivery

    started = json.loads(pin(json.dumps(started)))
    started["toolOutput"]["output"] = readable(started["toolOutput"]["output"])
    snapshot.check(
        yaml_document(
            ROUTE_WALKTHROUGH,
            {
                "leaf wait": {"output": readable(waited)},
                "Claude Code hook": {
                    "watch notification": pin(woke),
                    "UserPromptSubmit additionalContext": {
                        "instruction": Prose(instruction),
                        "delivery": readable(json.dumps(hooked, ensure_ascii=False)),
                        "attention": Prose(pin(attention)),
                    },
                },
                "Codex queue": {
                    "codex queue --message": Prose(pin(queued.prompt)),
                    "leaf delivery read 22222222": readable(read),
                },
                "Codex App Server": {"turn/start": started},
            },
        )
    )


@pytest.mark.parametrize("names", ["ok", ["ok", "ok"], ["ok", 1]])
def test_init_requires_tones_to_be_a_list_membership_can_be_tested_against(
    page_dir, tmp_path, names
):
    """Presence is not enough, because the tone check asks this list for membership.
    A string answers by substring, so a layer declaring `"names": "ok"` would pass
    `tone="o"` and paint nothing — the invisible failure the tone check exists to
    catch, arriving through the very entry that declares the vocabulary."""
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(json.dumps({"$tones": {"names": names}}))

    finding = init_refusal(page_dir)
    assert finding.code == "layer-facts"
    assert finding.values["path"][:2] == ["$tones", "names"]


def test_a_project_layer_restates_a_key_doc(page_dir, tmp_path):
    """A project layer overrides a member of $keys, its own reading of a key, and the
    shipped members it leaves stand."""
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(
        json.dumps({"$keys": {"space": "wider, in this project"}})
    )
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *package_selection_args((*page_packages(), "./.leaf")),
            str(page_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    keys = registry_storage.load_registry(page_dir)["$keys"]
    assert keys["space"] == "wider, in this project"
    assert keys["verbatim"]  # the rest of the shipped members stand


@pytest.mark.parametrize(
    ("fact", "admitted"),
    [
        ("$keys", schema_model.DECLARATION_KEYS),
        ("$verbs", frozenset(cast(dict, schema_model.VERB_SCHEMA["properties"]))),
        ("$awaits", frozenset(cast(dict, schema_model.AWAITS_SCHEMA["properties"]))),
    ],
)
def test_the_key_docs_hold_to_the_keys_their_schema_admits(fact, admitted):
    """Leaf's own `$keys` documents each key a declaration may hold, `$verbs` each
    field of a verb and `$awaits` each of `awaits`, one paragraph apiece beside a
    description: a member for a key the schema doesn't admit is documentation of
    nothing, and a key with no member is one an author reads the registry for and
    finds unsaid. Agents query them, and the site's table is generated from `$keys`."""
    members = dict(shipped_core_registry()[fact])
    assert isinstance(members.pop("description"), str)
    assert set(members) == admitted
    assert all(isinstance(text, str) and text for text in members.values())


@pytest.mark.parametrize("key", ["kinds", "ownership", "protocol"])
def test_the_kernel_event_contract_is_not_a_layer_extension(page_dir, tmp_path, key):
    """A layer cannot change the event kinds, their ownership, or the protocol
    numbering them, so every page's vocabulary carries the kernel's of the Leaf
    reading it, and `page init` says the layer's value has no effect."""
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    registry = vocabulary(page_dir)
    if key == "kinds":
        registry["$events"][key]["signal"] = registry["$events"][key]["error"]
    elif key == "ownership":
        registry["$events"][key]["browser_discard"] = []
    else:
        # Equal to a protocol of 1 in Python, and still not the kernel's number.
        registry["$events"][key] = True
    (overlay / "registry.json").write_text(json.dumps(registry))
    shipped = cleanup_model.kernel_registry()["$events"][key]

    assert found(init_notes(page_dir), "fixed-events", key=key)
    assert registry_storage.load_registry(page_dir)["$events"][key] == shipped

    (overlay / "registry.json").write_text(json.dumps({"$events": {key: None}}))
    assert found(init_notes(page_dir), "fixed-events", key=key)
    assert registry_storage.load_registry(page_dir)["$events"][key] == shipped


@pytest.mark.parametrize("fact", ["$passages", "$names", "$marks"])
def test_the_kernel_facts_are_not_a_layer_extension(page_dir, tmp_path, fact):
    """Python reads the running Leaf's kernel facts and the browser a copy generated
    from them, so a layer's change to one, even taking a member out, would reach
    neither runtime; `page init` keeps the kernel's and says so."""
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    shipped = registry_storage.load_registry(page_dir)[fact]
    member = next(key for key in shipped if key != "description")
    (overlay / "registry.json").write_text(json.dumps({fact: {member: None}}))

    assert found(init_notes(page_dir), "fixed-kernel-fact", name=fact)
    assert registry_storage.load_registry(page_dir)[fact] == shipped


def test_shared_package_declarations_compose_by_member():
    """One package can extend a shared declaration without copying its peers."""
    board = {"role": "holder", "state": "status"}
    lane = {"role": "holder", "state": "phase"}
    merged = {"$workflow": {"widgets": {"lf-board": board}}}

    registry_layer.merge_layer_declarations(
        merged, {"$workflow": {"widgets": {"lf-lane": lane}}}
    )

    assert merged["$workflow"]["widgets"] == {
        "lf-board": board,
        "lf-lane": lane,
    }
