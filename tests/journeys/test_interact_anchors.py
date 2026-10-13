"""File-side anchor and thread-projection tests."""

import json

from click.testing import CliRunner
from interact_support import (
    FLOW_PAGE,
    PAGE,
    SUGGESTED,
    SUGGESTION,
    append_carried_log_record,
    append_command,
    check,
    check_findings,
    comment,
    decide,
    found,
    publish,
    published,
    stamp,
    state_json,
    suggested,
)
from leaf import cli as cli_model
from leaf import event_contracts as event_contracts_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import structure as structure_model
from leaf.events import build_threads
from leaf.registry import storage as registry_storage
from model.test_interact_anchors import (
    PARTED,
    declare_part_prefixes,
    drop_node_a,
    parted,
)


def test_a_visual_admits_the_parts_its_prefixes_begin(page_dir):
    """A picture drawn from data cannot list its parts in markup, so its widget
    declares their kinds: any id a prefix begins is a part a comment may name, with
    nothing authored on the element, and one outside them is refused by name."""
    (page_dir / "index.html").write_text(FLOW_PAGE)
    declare_part_prefixes(page_dir, "node:")
    published(page_dir)

    named = comment(
        page_dir, "--section", "flow", "--part", "node:B", "--text", "and this?"
    )
    assert named.exit_code == 0, named.output
    root = json.loads(named.output)
    assert root["anchor"] == {"section": "flow", "visual": "node:B"}

    outside = comment(page_dir, "--section", "flow", "--part", "edge:B", "--text", "x")
    assert outside.exit_code != 0
    assert "ids starting with 'node:'" in outside.output

    refused = event_contracts_model.visual_anchor_error(
        {"anchor": {"section": "flow", "visual": "edge:B"}},
        {"flow": {"tag": "lf-diagram", "attrs": {"id": "flow"}}},
        json.loads((page_dir / "registry.json").read_text()),
    )
    assert (refused.code, refused.values["declared"]["prefixes"]) == (
        "undeclared-visual",
        ["node:"],
    )
    for unrenderable in ("node:", "node:a b"):
        assert event_contracts_model.visual_anchor_error(
            {"anchor": {"section": "flow", "visual": unrenderable}},
            {"flow": {"tag": "lf-diagram", "attrs": {"id": "flow"}}},
            json.loads((page_dir / "registry.json").read_text()),
        ), unrenderable

    # The file lists none of these parts, so markup cannot drop one; a declaration
    # that stops admitting a part a thread holds is what drops it.
    declare_part_prefixes(page_dir, "edge:")
    status, findings = check_findings(page_dir)
    assert status == 0
    assert found(findings, "relocated-anchor", thread=root["id"], section="flow")
    assert stamp(page_dir, "Changed the diagram's parts").exit_code == 0
    thread = build_threads(events_model.read_events(page_dir), {})[root["id"]]
    assert thread["anchor"] == {"section": "flow"}
    assert thread["rewritten_from"] == root["anchor"]


def test_an_agent_reply_can_move_a_thread_to_its_revised_visual(page_dir):
    """The reply and replacement anchor are one durable act. The raw opening keeps
    where the question was asked, while every current-state reading follows the new
    visual part and releases the old element from version retention."""
    v1 = FLOW_PAGE.replace(
        '<lf-diagram id="flow">',
        '<p id="old-wording">The retry starts here.</p>'
        '<lf-diagram id="flow" parts="node:A node:B">',
    )
    (page_dir / "index.html").write_text(v1)
    published(page_dir)
    root = json.loads(
        comment(
            page_dir,
            "--quote",
            "The retry starts here.",
            "--text",
            "Should this move onto the diagram?",
        ).output
    )
    v2 = v1.replace('<p id="old-wording">The retry starts here.</p>', "")
    (page_dir / "index.html").write_text(v2)

    mistyped = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            root["id"],
            "--section",
            "flowe",
            "--text",
            "This target must not partly land.",
        ],
    )
    assert mistyped.exit_code != 0
    assert "no element id 'flowe'" in mistyped.output
    assert files_model.latest_revision(page_dir) == 1
    assert all(event["kind"] != "reply" for event in events_model.read_events(page_dir))

    moved = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            root["id"],
            "--section",
            "flow",
            "--part",
            "node:A",
            "--text",
            "I moved the retry into this node and reattached the thread.",
        ],
    )
    assert moved.exit_code == 0, moved.output
    reply = json.loads(moved.output)
    current = {"section": "flow", "visual": "node:A"}
    assert (reply["revision"], reply["anchor"]) == (2, current)

    events = events_model.read_events(page_dir)
    original = next(event for event in events if event["id"] == root["id"])
    assert original["anchor"]["section"] == "old-wording"
    assert original["anchor"]["quote"] == "The retry starts here."
    assert original["anchor"] != current
    assert state_json(page_dir)["threads"] == [
        {
            "id": root["id"],
            "anchor": current,
            "title": None,
            "detached_from": None,
            "resolved": None,
            "unread": [root["id"], reply["id"]],
            "attention": {"kind": "needs_user", "reason": "ask", "workflow": None},
        }
    ]
    transcript = CliRunner().invoke(
        cli_model.cli, ["page", "transcript", str(page_dir)]
    )
    assert transcript.exit_code == 0, transcript.output
    assert "> § flow · node:A" in transcript.output

    checked = CliRunner().invoke(cli_model.cli, ["page", "check", str(page_dir)])
    assert checked.exit_code == 0, checked.output


def test_revising_quotes_reparents_every_open_thread_without_answering_it(page_dir):
    """A source save repairs all affected threads, including those not answered.

    Opening records remain historical, closed threads stay put, and reaction
    marks follow their subject. Automatic anchor bookkeeping leaves messages and exact
    response obligations intact. Repeated reads append no duplicate transition.
    """
    original = PAGE.replace(
        "<h2>Plan</h2>",
        '<h2>Plan</h2><table id="labels"><tr><th>Alpha</th><th>Gamma</th><th>Unchanged</th></tr></table>',
    )
    (page_dir / "index.html").write_text(original)
    publish(page_dir)
    roots = {}
    for quote in ("Alpha", "Gamma", "Unchanged"):
        roots[quote] = json.loads(
            comment(page_dir, "--quote", quote, "--text", f"About {quote}").output
        )
    closed = json.loads(
        comment(page_dir, "--quote", "Gamma", "--text", "Already settled").output
    )
    append_command(
        page_dir, {"kind": "resolve", "author": "user", "parent": closed["id"]}
    )
    append_command(
        page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": roots["Gamma"]["id"],
            "text": "Please revise this too.",
        },
    )
    reaction = append_command(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": roots["Alpha"]["anchor"],
            "token": "shorten",
        },
    )
    before = state_json(page_dir)["activity"]["obligations"]
    assert before
    messages = [
        e
        for e in events_model.read_events(page_dir)
        if e["kind"] in {"comment", "reply"}
    ]
    (page_dir / "index.html").write_text(
        original.replace("Alpha", "Beta").replace("Gamma", "Delta")
    )
    status, findings = check_findings(page_dir)
    assert status == 0
    # The reaction mark follows its subject; the unchanged and closed threads stay.
    assert {f.values["thread"] for f in found(findings, "relocated-anchor")} == {
        roots["Alpha"]["id"],
        roots["Gamma"]["id"],
        reaction["id"],
    }
    assert not any(e["kind"] == "reanchor" for e in events_model.read_events(page_dir))
    state = state_json(page_dir)
    threads = {t["id"]: t for t in state["threads"]}
    for quote in ("Alpha", "Gamma"):
        assert threads[roots[quote]["id"]]["anchor"] == {"section": "labels"}
    assert threads[roots["Unchanged"]["id"]]["anchor"] == roots["Unchanged"]["anchor"]
    assert threads[closed["id"]]["anchor"] == closed["anchor"]
    assert reaction["id"] not in threads
    assert state["activity"]["obligations"] == before
    events = events_model.read_events(page_dir)
    moves = [e for e in events if e["kind"] == "reanchor"]
    assert {e["thread"] for e in moves} == {
        roots["Alpha"]["id"],
        roots["Gamma"]["id"],
        reaction["id"],
    }
    assert all(
        e["revision"] == 2 and e["author"] == "page" and not e["attention"]
        for e in moves
    )
    assert [e for e in events if e["kind"] in {"comment", "reply"}] == messages
    assert all(
        e["anchor"] == root["anchor"]
        for q, root in roots.items()
        for e in events
        if e["id"] == root["id"]
    )
    state_json(page_dir)
    assert events_model.read_events(page_dir) == events

    from leaf.events import build_threads
    from leaf.passages import enclosing_ids
    from leaf.thread_context import sample_events

    document = structure_model.SourceDocument((page_dir / "index.html").read_text())
    selected = {roots["Alpha"]["id"], roots["Gamma"]["id"]}
    copied = sample_events(document, events, selected)
    assert len([e for e in copied if e["kind"] == "reanchor"]) == 2
    child_threads = build_threads(copied, enclosing_ids(document))
    assert all(
        child_threads[identity]["anchor"] == {"section": "labels"}
        for identity in selected
    )

    # The fold keeps the words each automatic move left, which the panel goes on
    # naming, until a reply places the thread again, even on that same section.
    folded = build_threads(events, {})
    assert folded[roots["Alpha"]["id"]]["rewritten_from"] == roots["Alpha"]["anchor"]
    assert folded[roots["Unchanged"]["id"]]["rewritten_from"] is None
    assert folded[reaction["id"]]["anchor"] == {"section": "labels"}
    assert folded[reaction["id"]]["rewritten_from"] == reaction["anchor"]
    placed = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            roots["Alpha"]["id"],
            "--section",
            "labels",
            "--text",
            "This section now.",
        ],
    )
    assert placed.exit_code == 0, placed.output
    replaced = build_threads(events_model.read_events(page_dir), {})
    assert replaced[roots["Alpha"]["id"]]["anchor"] == {"section": "labels"}
    assert replaced[roots["Alpha"]["id"]]["rewritten_from"] is None


def test_a_quote_without_a_section_detaches_when_its_words_disappear(page_dir):
    original = PAGE.replace("</main>", "<p>Alpha</p></main>")
    (page_dir / "index.html").write_text(original)
    publish(page_dir)
    root = json.loads(
        comment(
            page_dir, "--quote", "Alpha", "--text", "Keep this discussion attached."
        ).output
    )
    assert root["anchor"]["section"] is None
    (page_dir / "index.html").write_text(original.replace("Alpha", "Beta"))
    checked = check(page_dir)
    assert checked.exit_code == 0, checked.output
    assert stamp(page_dir, "Revised the unsectioned passage").exit_code == 0
    thread = build_threads(events_model.read_events(page_dir), {})[root["id"]]
    assert thread["anchor"] is None
    assert thread["detached_from"] == root["anchor"]
    moved = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            root["id"],
            "--quote",
            "Beta",
            "--text",
            "Updated the same subject.",
        ],
    )
    assert moved.exit_code == 0, moved.output
    assert json.loads(moved.output)["anchor"]["quote"] == "Beta"


def test_an_agent_reply_can_remove_a_subject_and_detach_its_open_thread(page_dir):
    """Removing the thing a thread concerns is a current-state transition,
    not permission to attach that thread to some surviving neighbour. The reply
    and revision land together, while the opening anchor remains immutable history."""
    v1 = FLOW_PAGE.replace(
        '<lf-diagram id="flow">',
        '<p id="old-wording">The retry starts here.</p><lf-diagram id="flow">',
    )
    (page_dir / "index.html").write_text(v1)
    published(page_dir)
    root = json.loads(
        comment(
            page_dir,
            "--quote",
            "The retry starts here.",
            "--text",
            "Why is this section here?",
        ).output
    )
    (page_dir / "index.html").write_text(
        v1.replace('<p id="old-wording">The retry starts here.</p>', "")
    )

    refused = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            root["id"],
            "--detach",
            "--text",
            "This must not partly land.",
            "--markup",
            '<lf-diagram id="flow"><pre>graph LR\n  A --> B</pre></lf-diagram>',
        ],
    )
    assert refused.exit_code != 0
    assert (
        "ids already taken by the page or an earlier message" in refused.output
        and "flow" in refused.output
    )
    assert files_model.latest_revision(page_dir) == 1
    assert all(event["kind"] != "reply" for event in events_model.read_events(page_dir))

    detached = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            root["id"],
            "--detach",
            "--text",
            "I removed the section; this thread no longer has a page target.",
        ],
    )

    assert detached.exit_code == 0, detached.output
    reply = json.loads(detached.output)
    assert (reply["revision"], reply["anchor"]) == (2, None)
    events = events_model.read_events(page_dir)
    stored_reply = next(event for event in events if event["id"] == reply["id"])
    contract = registry_storage.require_registry(page_dir)["$events"]["kinds"]["reply"]
    assert event_contracts_model.event_record_error(contract, stored_reply) is None
    assert state_json(page_dir)["threads"] == [
        {
            "id": root["id"],
            "anchor": None,
            "title": None,
            "detached_from": root["anchor"],
            "resolved": None,
            "unread": [root["id"], reply["id"]],
            "attention": {"kind": "needs_user", "reason": "ask", "workflow": None},
        }
    ]
    stored_root = next(event for event in events if event["id"] == root["id"])
    assert stored_root["anchor"] == root["anchor"]
    checked = CliRunner().invoke(cli_model.cli, ["page", "check", str(page_dir)])
    assert checked.exit_code == 0, checked.output

    reattached = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            root["id"],
            "--section",
            "flow",
            "--text",
            "The remaining diagram is now the subject.",
        ],
    )
    assert reattached.exit_code == 0, reattached.output
    [thread] = state_json(page_dir)["threads"]
    assert thread["anchor"] == {"section": "flow"}
    assert thread["detached_from"] is None


def test_a_moving_reply_validates_markup_against_the_prospective_revision(page_dir):
    """Reply markup validates against the edited source before either lands. It cannot
    take an id the prospective page already owns, and a failed reply leaves the prior
    revision active."""
    published(page_dir)
    root = json.loads(
        comment(
            page_dir, "--section", "backfill-first", "--text", "Move this when fixed."
        ).output
    )
    source = page_dir / "index.html"
    source.write_text(
        source.read_text().replace(
            "</section>", '<p id="answer">The revised answer.</p></section>'
        )
    )

    moved = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            str(page_dir),
            root["id"],
            "--section",
            "answer",
            "--text",
            "Moved this to the revised answer.",
            "--markup",
            '<lf-diagram id="answer"><pre>graph LR\n  A --> B</pre></lf-diagram>',
        ],
    )

    assert moved.exit_code != 0
    assert (
        "ids already taken by the page or an earlier message" in moved.output
        and "answer" in moved.output
    )
    assert all(event["kind"] != "reply" for event in events_model.read_events(page_dir))
    assert files_model.latest_revision(page_dir) == 1
    checked = CliRunner().invoke(cli_model.cli, ["page", "check", str(page_dir)])
    assert checked.exit_code == 0, checked.output


def test_a_removed_visual_part_moves_its_thread_to_the_surviving_section(page_dir):
    assert drop_node_a(parted(page_dir)).exit_code == 0
    (page_dir / "index.html").write_text(PARTED)
    root = json.loads(
        comment(
            page_dir, "--section", "flow", "--part", "node:A", "--text", "Why this one?"
        ).output
    )
    assert root["anchor"] == {"section": "flow", "visual": "node:A"}
    result = drop_node_a(page_dir)
    assert result.exit_code == 0, result.output
    assert stamp(page_dir, "Removed the node").exit_code == 0
    events = events_model.read_events(page_dir)
    thread = build_threads(events, {})[root["id"]]
    assert thread["anchor"] == {"section": "flow"}
    assert thread["rewritten_from"] == root["anchor"]
    assert next(e for e in events if e["id"] == root["id"])["anchor"] == root["anchor"]


def test_withdrawing_a_decision_does_not_veto_an_authored_replacement(page_dir):
    """Undo withdraws a gesture; it does not restore markup the author replaced."""
    suggested(page_dir)
    decide(page_dir, "accept")
    # What honoring an accept looks like: the surviving half written straight,
    # keeping its id, and the wrapper and the retired half gone with the decision.
    honored = SUGGESTED.replace(
        SUGGESTION,
        '<p id="refill-camera">Refill when the camera shows it half-empty.</p>\n',
    )
    assert "sug-refill" not in honored and "refill-rule" not in honored
    (page_dir / "index.html").write_text(honored)
    assert check(page_dir).exit_code == 0

    accepted = next(
        e for e in events_model.read_events(page_dir) if e["kind"] == "action"
    )
    append_carried_log_record(
        page_dir, {"kind": "undo", "author": "user", "undoes": accepted["id"]}
    )
    checked = check(page_dir)
    assert checked.exit_code == 0, checked.output
    assert stamp(page_dir, "Replaced the suggestion").exit_code == 0
    kept = comment(page_dir, "--quote", "camera shows it half-empty", "--text", "x")
    assert kept.exit_code == 0, kept.output
    gone = comment(
        page_dir, "--quote", "Refill every feeder each morning", "--text", "x"
    )
    assert gone.exit_code != 0 and "doesn't say" in gone.output
    assert (
        next(
            event
            for event in events_model.read_events(page_dir)
            if event["id"] == accepted["id"]
        )
        == accepted
    )
