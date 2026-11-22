"""Tests scheduled by the measured cost of their boundary."""

import json
import textwrap

from interact_support import (
    Json,
    Prose,
    fetch,
    publish,
    shipped_core_registry,
    yaml_block,
    yaml_document,
)
from model.interact_contract.test_layer_contract import (
    WALKTHROUGH_PAGE,
)

from leaf import delivery as delivery_model
from leaf import service as service_model
from leaf import session as session_model
from leaf.registry import contract as registry_contract
from leaf.registry import storage as registry_storage

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

  uv run pytest --regtest-reset -n0 tests/journeys/interact_contract/test_layer_contract.py::test_each_case_of_an_event_is_told_what_the_snapshot_shows"""


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
        "comment on the page, written while slides showed": {
            "kind": "comment",
            "viewing": ["results"],
            **untitled,
            **owes("reply"),
        },
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
        "reply in words to a choice the agent sent": {
            "kind": "reply",
            **titled,
            "waiting": [{"id": "widget:w1", "text": "Which store should own it?"}],
            **owes("reply"),
        },
        "reply in words that answered the agent's question": {
            "kind": "reply",
            **titled,
            "settled": [{"id": "message:m1", "text": "Can you try the build?"}],
            **owes("reply"),
        },
        "reaction on a message": {"kind": "reply", "token": "+1"},
        "rewritten message": {
            "kind": "edit",
            "text": "Tuesdays, after the report run",
            **titled,
            **owes("reply"),
        },
        "deleted message": {"kind": "edit", "text": "", **titled, **owes("reply")},
        "rewritten suggestion": {
            "kind": "edit",
            "text": "moves to Wednesdays",
            "suggestion": True,
            **titled,
            **owes("reply"),
        },
        "deleted suggestion": {
            "kind": "edit",
            "text": "",
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
        "undo": {"kind": "undo"},
        "report": {"kind": "report"},
        "error": {"kind": "error"},
        "render": {"kind": "render"},
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
