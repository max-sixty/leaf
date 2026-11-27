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
    declare_on_page,
    found,
    publish,
    published,
    stamp,
    state_json,
    suggested,
)

from leaf.base import files as files_model
from leaf.commands import cli as cli_model
from leaf.log import event_log as events_model
from leaf.log.events import build_threads
from leaf.records import event_contracts as event_contracts_model
from leaf.source import structure as structure_model
from leaf.source import vocabulary as vocabulary_model


def declare_part_prefixes(page_dir, *prefixes):
    """Give the page's diagram other part-id prefixes than it ships with."""
    declare_on_page(
        page_dir,
        lambda registry: registry["lf-diagram"].update(
            {
                "visual": {"prefixes": list(prefixes)},
            }
        ),
    )


def test_a_visual_admits_the_parts_its_prefixes_begin(page_dir):
    """A visual's widget declares its parts' kinds rather than its markup listing
    them: any id a prefix begins is a part a comment may name, and one outside them is
    refused by name."""
    (page_dir / "index.html").write_text(FLOW_PAGE)
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
        vocabulary_model.read_page_registry(page_dir).registry,
    )
    assert (refused.code, refused.values["prefixes"]) == (
        "undeclared-visual",
        ["node:"],
    )
    for unrenderable in ("node:", "node:a b"):
        assert event_contracts_model.visual_anchor_error(
            {"anchor": {"section": "flow", "visual": unrenderable}},
            {"flow": {"tag": "lf-diagram", "attrs": {"id": "flow"}}},
            vocabulary_model.read_page_registry(page_dir).registry,
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
            "title": "Agent thread",
            "detached_from": None,
            "rewritten_from": None,
            "resolved": None,
            "unread": [root["id"], reply["id"]],
            "attention": None,
        }
    ]

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
            "emoji": "✂️",
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

    from leaf.log.events import build_threads
    from leaf.log.thread_context import sample_events
    from leaf.source.passages import enclosing_ids

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
    reply = json.loads(moved.stdout)
    assert [finding["code"] for finding in reply["findings"]] == ["unpointable"]
    assert reply["anchor"]["quote"] == "Beta"


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
            'This must not partly land.\n\n<lf-diagram id="flow">\n<pre>graph LR\n  A --> B</pre></lf-diagram>',
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
    contract = vocabulary_model.require_registry(page_dir)["$events"]["kinds"]["reply"]
    assert event_contracts_model.event_record_error(contract, stored_reply) is None
    assert state_json(page_dir)["threads"] == [
        {
            "id": root["id"],
            "anchor": None,
            "title": "Agent thread",
            "detached_from": root["anchor"],
            "rewritten_from": None,
            "resolved": None,
            "unread": [root["id"], reply["id"]],
            "attention": None,
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
            "Moved this to the revised answer.\n\n"
            '<lf-diagram id="answer">\n<pre>graph LR\n  A --> B</pre></lf-diagram>',
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
    assert gone.exit_code == 0, gone.output
    [note] = json.loads(gone.output)["findings"]
    assert (note["code"], note["values"]["found"]) == ("unplaced-quote", 0)
    assert (
        next(
            event
            for event in events_model.read_events(page_dir)
            if event["id"] == accepted["id"]
        )
        == accepted
    )


from interact_support import (
    response_reference,
)

from leaf.source import passages as passages_model


def test_a_comments_widget_markup_shares_one_id_universe_with_replies(page_dir):
    """A Claude comment's markup lands in the panel exactly as a reply's does, so it
    validates the same way and claims ids from the same pool."""
    published(page_dir)
    assert (
        comment(
            page_dir,
            "--quote",
            "Ship dark",
            "--text",
            "Pick:\n\n"
            '<lf-group id="q1-decision" label="Pick one">\n<h3 id="q1-decision-h">Pick one</h3><lf-options id="q1">'
            '<lf-option id="q1-a" label="A"><strong>A</strong> '
            '<span id="thread-label">Label</span></lf-option></lf-options></lf-group>',
        ).exit_code
        == 0
    )
    append_carried_log_record(
        page_dir, {"kind": "comment", "id": "c1", "author": "user", "text": "hm"}
    )
    clash = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, "c1"),
            "--title",
            "Diagram id clash",
            "--text",
            'See:\n\n<lf-diagram id="q1">\n<pre>\ngraph LR\n  A --> B\n</pre></lf-diagram>',
        ],
    )
    assert clash.exit_code != 0 and "q1" in clash.output

    plain_clash = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, "c1"),
            "--title",
            "Label id clash",
            "--text",
            'See:\n\n<lf-diagram id="thread-label">\n<pre>graph LR\n  A --> B</pre></lf-diagram>',
        ],
    )
    assert plain_clash.exit_code != 0 and "thread-label" in plain_clash.output


def test_a_blank_line_that_splits_a_messages_pre_is_refused(page_dir):
    """A blank line ends a block of HTML, a `<pre>` inside a widget included, and
    Markdown reads the lines after it as its own blocks, such as paragraphs or a list,
    so the code loses its blank lines, indents and marks while the HTML stays well
    formed. A fence, or a `<pre>` opening its own line after a blank line, keeps them."""
    published(page_dir)
    code = "def a():\n    return 1\n\ndef b():\n    return 2"
    for split in (code, "steps:\n\n- build\n- ship"):
        refused = comment(
            page_dir,
            "--text",
            f'Here:\n\n<lf-code id="split">\n<pre>{split}</pre>\n</lf-code>',
        )
        assert refused.exit_code != 0 and "split-pre" in refused.output, refused.output
    for kept in (
        f'<lf-code id="fenced">\n\n```python\n{code}\n```\n\n</lf-code>',
        f'<lf-code id="own-line">\n\n<pre>{code}</pre>\n\n</lf-code>',
    ):
        assert code in passages_model.message_markup(kept)
        assert comment(page_dir, "--text", f"Here:\n\n{kept}").exit_code == 0


def test_a_widget_sharing_its_opening_line_is_refused_for_its_paragraph_alone(
    page_dir,
):
    """A widget whose opening tag shares its line with its content is inline HTML, so
    Markdown draws a paragraph around it, and its `<pre>` closes that paragraph. The
    refusal names that repair alone, not the widget the parser emptied, which the
    agent wrote whole."""
    published(page_dir)
    code = '<lf-code id="snippet">{}<pre><code class="language-python">print(1)</code></pre></lf-code>'
    refused = comment(page_dir, "--text", "Here:\n\n" + code.format(""))
    assert refused.exit_code != 0
    assert [f["code"] for f in json.loads(refused.output)["findings"]] == ["unclosed"]
    kept = comment(page_dir, "--text", "Here:\n\n" + code.format("\n"))
    assert kept.exit_code == 0, kept.output
