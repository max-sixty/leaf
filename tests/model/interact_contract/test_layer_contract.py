"""The layer's `$` contract: how layers merge its members, the event handling and routes
each delivery tells the agent, and the docs held to it."""

import itertools
import json
import os
import re
import textwrap
from copy import deepcopy
from pathlib import Path

import pytest
from click.testing import CliRunner
from interact_support import (
    Json,
    Prose,
    command_findings,
    fetch,
    found,
    page_packages,
    publish,
    registry_refusal,
    shipped_core_registry,
    yaml_block,
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
from leaf.registry import contract as registry_contract
from leaf.registry import layer as registry_layer
from leaf.registry import storage as registry_storage
from leaf_dev.page_fixtures import package_selection_args
from model.interact_contract import vocabulary


@pytest.mark.parametrize(
    ("changes", "keyword", "path"),
    [
        ({"description": " \n\t"}, "pattern", ["description"]),
        ({"x-example": " \n\t"}, "pattern", ["x-example"]),
        ({"x-example": False}, "type", ["x-example"]),
        ({"x-example": None}, "required", []),
        ({"x-instructions": ""}, "pattern", ["x-instructions"]),
        ({"x-work": True}, "additionalProperties", []),
    ],
)
def test_idioms_have_nonblank_authoring_fields_and_no_widget_behavior(
    changes, keyword, path
):
    registry = shipped_core_registry()
    entry = {"description": "An eyebrow.", "x-example": '<p class="eyebrow">Title</p>'}
    registry[".eyebrow"] = entry
    registry_layer.validate_layer_declarations(registry, "registry.json")
    entry["x-instructions"] = "Use above a heading."
    registry_layer.validate_layer_declarations(registry, "registry.json")
    for key, value in changes.items():
        if value is None:
            del entry[key]
        else:
            entry[key] = value
    refused = registry_refusal(
        lambda: registry_layer.validate_layer_declarations(registry, "registry.json")
    )
    assert found(
        [refused], "idiom-schema", selector=".eyebrow", keyword=keyword, path=path
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
        registry_layer.check_layer_facts(registry, "kernel")

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
        registry_layer.check_layer_facts(registry, "kernel")

    assert [finding.values["path"][0] for finding in refused.value.findings] == [
        "$data",
        "$reactions",
    ]


def test_one_check_names_each_missing_layer_fact():
    """A missing fact is named for itself, not folded into another that is missing."""
    registry = shipped_core_registry()
    del registry["$languages"], registry["$tones"]

    with pytest.raises(registry_contract.RegistryError) as refused:
        registry_layer.check_layer_facts(registry, "kernel")

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


def _handling(clauses):
    return {"handling": clauses}


@pytest.mark.parametrize(
    ("events", "code"),
    [
        (
            _handling({"bogus-kind": [{"text": "A clause for no kind."}]}),
            "undeclared-event-kind",
        ),
        (
            {"answering": {"markdown": [{"text": "A clause for no answer."}]}},
            "undeclared-event-kind",
        ),
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


HANDLING_WALKTHROUGH = """\
What the agent is told when a user acts on a page
===================================================

A test records this file; nobody writes it by hand. The lines starting with `#`
explain it, and everything else is the recorded data. The walkthrough below is
one real run: the test serves a page, posts a comment to it the way the browser
does, runs `leaf wait` in a Claude Code session, and acknowledges its complete
delivery. Only the id, the times and the page's path are pinned, so the file
stays the same from run to run.

How this text reaches the agent, by example
-------------------------------------------

1. The page's `plan` section reads "The nightly backfill moves to Tuesdays so it
   stops colliding with the report run." The user selects "moves to Tuesdays"
   and comments "why here?". The page's JavaScript sends this to the page's
   server as POST /api/event:

@POSTED@

2. The server checks the comment against the page, adds who wrote it (`author`),
   when (`ts`) and an `id`, and appends it to the page's event log, events.jsonl,
   as this one line:

@LOGGED@

3. The agent runs `leaf wait`, which notices the new input and prints a complete
   delivery for the comment. The explicit wait carries the input even if the
   session's hooks no longer run.
   The comment is owed a reply, which the delivery records as its `answer` (step
   4): a `reply` for `leaf thread reply <answer.ref>` here; the Codex App Server route
   would record a `turn`, which the turn's own messages write. For the
   instructions, `leaf wait` reads the clauses under
   `$events.handling.comment` in the page's copy of registry.json, then those
   under `$events.answering.reply`, the answer it owes. Each clause has a `text`
   and may have a `when`, a JSON Schema that must hold for the clause to apply.
   It is tested against the log line together with its `answer` and its
   `thread`'s entry in the delivery's `threads` (step 4). There are
   @COUNT@; here they all are, with whether the comment satisfies each `when`:

@CLAUSES@

4. The wait prints the delivery as JSON. The delivery's event is the log line
   from step 2 less @DROPPED@, the browser's retry key, and with these fields added:
   @ADDED@.
   The batch's `handling` maps clause ids to their text, each distinct text
   appearing once. The event's `handling` names its applicable clauses in order.
   The envelope's `acknowledge` tells the agent to confirm receipt before work;
   printing alone does not mark the comment Picked up. Large readings expose
   numbered parts and a `next` command; read all parts before acknowledging.
   This comment fits in one reading, shown here as the wait prints it:

@DELIVERY@

5. The agent acknowledges the delivery, then follows `handling`. For requested
   work it opens with `leaf thread reply <answer.ref> --ephemeral --text "<plan>"`,
   does the work, and answers with `leaf thread reply <answer.ref>`.

What this file records
----------------------

Step 3, for one example of every case, using the clauses in
browser/runtime/kernel-registry.json (which `leaf page init` composes into a page).
Each top-level key below names a case and holds:

  event:  the input: a log line's `kind`, the kind of answer its delivery
          says it owes (`answer`), and the fields some `when` reads, its
          `thread`'s among them, and nothing else. A field no `when`
          names, such as a comment's `anchor` or `text`, cannot change what
          the agent is told, so it is left out; the test checks both halves of
          that.
  told:   the output, the clauses that apply to that line, in order. Each
          clause has a `text` and may have a `when`:
  when:   the clause's `when`, exactly as registry.json writes it: a JSON
          Schema the log line must satisfy for the clause to apply. A clause
          with no `when` always applies, and has no `when` key here either.
  text:   the clause's text.

The walkthrough's comment is the first case. No `when` reads any field of its
log line from step 2 except `kind`, so the case is that line cut down to `kind`,
the reply it owes and its new thread's missing title, and it gets the
clauses marked "applies" in step 3. It is recorded as:

@RECORDED@

After changing a clause, re-record this file and review the diff:

  uv run pytest --regtest-reset -n0 tests/model/interact_contract/test_layer_contract.py::test_each_case_of_an_event_is_told_what_the_snapshot_shows"""


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


def test_each_case_of_an_event_is_told_what_the_snapshot_shows(
    snapshot, page_dir, server, capsys
):
    """The snapshot is the table a developer reads to see what the agent is told for
    each case: every kind, and every condition a clause's `when` names, resolved
    through the shipped layer clause by clause, each under the condition that let it
    in. A wording or condition change shows up as a diff per case. The assertions
    keep the table whole: every declared kind has a case, and every clause reaches
    at least one case, so no `when` is dead. Its header walks one real comment from
    the HTTP route through `leaf wait` and its acknowledged delivery, and holds that
    the clauses it lists as applying are exactly the `handling` the delivery
    carries."""
    registry = shipped_core_registry()
    # Each case holds its `kind` and the fields some `when` reads, and nothing else:
    # a field no `when` names cannot change what the agent is told.
    on_page = {"scope": "page"}

    def owes(kind):
        return {
            "answer": {
                "kind": "reply" if kind == "turn" else kind,
                **(
                    {"writer": "turn" if kind == "turn" else "agent"}
                    if kind in {"reply", "turn"}
                    else {}
                ),
            }
        }

    untitled = {"thread": {"title": None}}
    titled = {"thread": {"title": "Tuesday backfill"}}
    cases = {
        "comment": {"kind": "comment", **untitled, **owes("reply")},
        "comment over App Server": {"kind": "comment", **untitled, **owes("turn")},
        "comment with a drawing": {
            "kind": "comment",
            "drawing": {
                "strokes": [[[0, 0], [9, 9]]],
                "box": [640, 120],
                "viewport": [1200, 900],
                "scheme": "light",
            },
            **owes("reply"),
        },
        "comment with a pasted image": {
            "kind": "comment",
            "text": "this looks off ![screenshot](/media/0a1b2c.png)",
            **owes("reply"),
        },
        "comment a newer message answers through": {"kind": "comment"},
        "suggestion": {"kind": "comment", "suggestion": True, **owes("reply")},
        "design comment": {"kind": "comment", "about": "design", **owes("reply")},
        "reaction on the page": {"kind": "comment", "token": "+1"},
        "reply": {"kind": "reply", **titled, **owes("reply")},
        "reply in an untitled thread": {
            "kind": "reply",
            **untitled,
            **owes("reply"),
        },
        "reply with a pasted image": {
            "kind": "reply",
            "text": "like this ![sketch](/media/3d4e5f.png)",
            **owes("reply"),
        },
        "reply in a long thread": {
            "kind": "reply",
            "thread": {
                "title": "Tuesday backfill",
                "summary_hint": {"from": "m1", "through": "m8"},
            },
            **owes("reply"),
        },
        "reaction on a message": {"kind": "reply", "token": "+1"},
        "rewritten message": {"kind": "edit", **titled, **owes("reply")},
        "rewritten suggestion": {
            "kind": "edit",
            "suggestion": True,
            **titled,
            **owes("reply"),
        },
        "pick on the page": {"kind": "action", "meaning": on_page, **owes("markup")},
        "option the user added": {
            "kind": "action",
            "action": "add",
            "meaning": on_page,
        },
        "pick before Done": {"kind": "action", "meaning": on_page},
        "pick a thread's open question is about": {
            "kind": "action",
            "meaning": on_page,
            "waiting": [{"id": "message:m1", "text": "Try the previews first."}],
            **owes("markup"),
        },
        "decided suggestion": {
            "kind": "action",
            "action": "decide",
            "meaning": on_page,
            **owes("markup"),
        },
        "pick inside a thread": {
            "kind": "action",
            "meaning": {"scope": "thread"},
            **owes("reply"),
        },
        "pick inside a thread over App Server": {
            "kind": "action",
            "meaning": {"scope": "thread"},
            **owes("turn"),
        },
        "resolve": {"kind": "resolve"},
        "unresolve": {"kind": "unresolve"},
        "Done on a to-do on the user": {"kind": "todo_end"},
        "undo": {"kind": "undo"},
        "report": {"kind": "report"},
        "error": {"kind": "error"},
    }
    told = {
        name: registry_contract.event_clauses(event, registry)
        for name, event in cases.items()
    }

    declared = registry["$events"]["handling"]
    answering = registry["$events"]["answering"]
    assert {event["kind"] for event in cases.values()} == set(declared)

    def owed(event):
        return event.get("answer", {}).get("kind")

    assert {owed(event) for event in cases.values()} - {None} == set(answering)
    read = {
        field
        for clauses in (*declared.values(), *answering.values())
        for clause in clauses
        if "when" in clause
        for field in fields_named(clause["when"])
    }
    for name, event in cases.items():
        unread = set(event) - {"kind", "answer"} - read
        assert not unread, (name, unread)
    for kind, clauses in declared.items():
        reached = [told[name] for name, event in cases.items() if event["kind"] == kind]
        for clause in clauses:
            assert any(clause in matched for matched in reached), (kind, clause)
    for kind, clauses in answering.items():
        reached = [told[name] for name, event in cases.items() if owed(event) == kind]
        for clause in clauses:
            assert any(clause in matched for matched in reached), (kind, clause)

    # The walkthrough: one comment through the real HTTP route and the explicit
    # wait's complete delivery, acknowledged by its reader.
    (page_dir / "index.html").write_text(WALKTHROUGH_PAGE)
    publish(page_dir)
    service_model.claim_page(page_dir)
    session_model.cmd_waiting(page_dir)
    posted = {
        "kind": "comment",
        "revision": 1,
        "text": "why here?",
        "anchor": {"section": "plan", "quote": "moves to Tuesdays"},
        "attempt": "9f86d081884c7d659a2feaa0c55ad015",
    }
    status, answer = fetch(f"{server}/api/event", data=json.dumps(posted).encode())
    assert status == 200, answer
    logged = (page_dir / "events.jsonl").read_text().splitlines()[-1]
    capsys.readouterr()
    assert session_model.cmd_wait(page_dir) == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["acknowledge"] is not None
    assert delivery_model.receive_delivery(envelope["id"]) == [page_dir]
    record = json.loads(logged)
    [batch] = envelope["batches"]
    [delivered] = batch["events"]
    page_events = registry_storage.load_registry(page_dir)["$events"]
    page_clauses = [
        *page_events["handling"]["comment"],
        *page_events["answering"][delivered["answer"]["kind"]],
    ]
    [thread] = batch["threads"]
    applying = registry_contract.event_clauses(
        {
            **record,
            "answer": delivered["answer"],
            "thread": thread,
        },
        registry_storage.load_registry(page_dir),
    )
    assert [clause["text"] for clause in applying] == [
        batch["handling"][ref] for ref in delivered["handling"]
    ]
    # The full line, anchor and all, gets exactly the `comment` case's clauses.
    assert applying == told["comment"]

    pinned = {
        record["id"]: "1946b466",
        record["ts"]: "2026-09-21T20:12:30-07:00",
        envelope["id"]: "e8417b8a",
        batch["claim"]: "page-session",
        str(page_dir): "/path/to/page",
    }
    envelope["created_at"] = 1790046750.29

    def pin(shown: str) -> str:
        for actual, steady in pinned.items():
            shown = shown.replace(actual, steady)
        return shown

    def indented(block: str) -> str:
        return textwrap.indent(block, " " * 5)

    listing = []
    for number, clause in enumerate(page_clauses, 1):
        verdict = "applies" if clause in applying else "does not apply"
        listing.append(f"clause {number}, {verdict}:")
        if "when" in clause:
            listing.append(f"  when: {json.dumps(clause['when'])}")
        else:
            listing.append("  (no `when`, so it always applies)")
        listing.append(
            textwrap.fill(
                clause["text"],
                79,
                initial_indent="  text: ",
                subsequent_indent=" " * 8,
                break_on_hyphens=False,
            )
        )
    added = [f"`{key}`" for key in delivered if key not in record]
    [dropped] = [f"`{key}`" for key in record if key not in delivered]
    header = (
        HANDLING_WALKTHROUGH.replace("@POSTED@", indented(json.dumps(posted)))
        .replace("@LOGGED@", indented(pin(logged)))
        .replace("@COUNT@", str(len(page_clauses)))
        .replace("@CLAUSES@", indented("\n".join(listing)))
        .replace("@ADDED@", ", ".join(added[:-1]) + " and " + added[-1])
        .replace("@DROPPED@", dropped)
        .replace("@DELIVERY@", indented(pin(json.dumps(envelope, indent=2))))
    )

    recorded = {
        name: {
            "event": event,
            "told": [
                {
                    **({"when": Json(clause["when"])} if "when" in clause else {}),
                    "text": Prose(clause["text"]),
                }
                for clause in told[name]
            ],
        }
        for name, event in cases.items()
    }
    header = header.replace(
        "@RECORDED@", indented(yaml_block({"comment": recorded["comment"]}).rstrip())
    )
    snapshot.check(yaml_document(header, recorded))


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
                     delivery on the next line, and what Leaf asks of the turn
                     after it.
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
    woke = session_model.watch_between_turns(harness_2)
    assert woke is not None
    hooks_model.cmd_hook(
        "claude-code", {"hook_event_name": "UserPromptSubmit", "session_id": session}
    )
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"][
        "additionalContext"
    ]
    instruction, hooked, *attention = context.split("\n")

    pinned = {
        logged["id"]: "1946b466",
        logged["ts"]: "2026-09-21T20:12:30-07:00",
        json.loads(waited)["id"]: "11111111",
        queued.payload["id"]: "22222222",
        prepared.payload["id"]: "33333333",
        json.loads(hooked)["id"]: "44444444",
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
                        "delivery": readable(hooked),
                        "attention": Prose(pin("\n".join(attention))),
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


def fields_named(schema: dict) -> set[str]:
    """Every event field a `when` schema names at its top level, through `not`,
    `anyOf` and `allOf`."""
    named = set(schema.get("required", [])) | set(schema.get("properties", {}))
    for part in [
        *([schema["not"]] if "not" in schema else []),
        *schema.get("anyOf", []),
        *schema.get("allOf", []),
    ]:
        named |= fields_named(part)
    return named


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


def test_init_holds_the_key_docs_to_the_keys_the_lint_admits(page_dir, tmp_path):
    """$keys documents each x- key an entry may declare, and exactly those: a member
    for a key the lint doesn't admit is documentation of nothing, and one missing is a
    key the registry then leaves unsaid. A project layer overrides a member (its own
    reading of a key) and adds none — the set is closed where the keys are checked."""
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    (overlay / "registry.json").write_text(
        json.dumps({"$keys": {"x-space": "wider, in this project", "x-nope": "?"}})
    )
    finding = init_refusal(page_dir)
    assert found([finding], "keys-documentation", missing=[], unadmitted=["x-nope"])

    (overlay / "registry.json").write_text(
        json.dumps({"$keys": {"x-space": "wider, in this project"}})
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
    assert keys["x-space"] == "wider, in this project"
    assert keys["x-says"]  # the rest of the shipped members stand


@pytest.mark.parametrize("fact", ["$state", "$awaits"])
def test_the_field_docs_hold_to_the_fields_their_schema_admits(fact):
    """`$state` documents the fields of an x-state verb and `$awaits` those of
    x-awaits, held to their schemas as `$keys` is to the x- keys: a field the schema
    admits with no member is one an author reads the registry for and finds unsaid."""
    kernel = shipped_core_registry()
    registry_layer.validate_layer_declarations(kernel, "kernel")
    documented = deepcopy(kernel)
    field = min(registry_layer.DOCUMENTED_KEYS[fact]["properties"])
    del documented[fact][field]
    documented[fact]["nope"] = "?"
    refused = registry_refusal(
        lambda: registry_layer.validate_layer_declarations(documented, "kernel")
    )
    assert found(
        [refused], "keys-documentation", fact=fact, missing=[field], unadmitted=["nope"]
    )


@pytest.mark.parametrize("key", ["kinds", "ownership", "protocol"])
def test_the_kernel_event_contract_is_not_a_layer_extension(page_dir, tmp_path, key):
    """A layer cannot change the event kinds, their ownership, or the protocol
    numbering them, so every page's vocabulary carries the kernel's of the Leaf
    reading it."""
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

    finding = init_refusal(page_dir)
    assert found([finding], "fixed-events", key=key)

    (overlay / "registry.json").write_text(json.dumps({"$events": {key: None}}))
    finding = init_refusal(page_dir)
    assert found([finding], "fixed-events", key=key)


@pytest.mark.parametrize("fact", ["$passages", "$names", "$marks"])
def test_the_kernel_facts_are_not_a_layer_extension(page_dir, tmp_path, fact):
    """Python reads the running Leaf's kernel facts and the browser a copy generated
    from them, so a layer's change to one, even taking a member out, would reach
    neither runtime."""
    overlay = tmp_path / ".leaf"
    overlay.mkdir(parents=True)
    shipped = registry_storage.load_registry(page_dir)[fact]
    member = next(key for key in shipped if key != "description")
    (overlay / "registry.json").write_text(json.dumps({fact: {member: None}}))

    finding = init_refusal(page_dir)
    assert found([finding], "fixed-kernel-fact", name=fact)


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
