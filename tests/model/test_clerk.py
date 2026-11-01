"""Leaf's clerk: the question a turn-end fork is asked, the answer it must give, and
what Leaf writes from that answer and tells the agent at its next step."""

import json

import pytest
from interact_support import DRAFTED, PAGE, append_carried_log_record, edit

from leaf import clerk as clerk_model
from leaf import event_log as events_model
from leaf import hooks as hooks_model
from leaf import todos as todos_model
from leaf.agent_state import cmd_page_state
from leaf.files import require_revision
from leaf.refusals import Refused
from leaf.revisioning import activate_source


def hook(capsys, event: str, prompt_id: str = "p1") -> str:
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": event, "session_id": "s1", "prompt_id": prompt_id},
    )
    out = capsys.readouterr().out
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""


def asked() -> dict:
    question = clerk_model.question("s1")
    assert question is not None
    return question


def reply(page, *titles: str, passage: str = "") -> str:
    return json.dumps(
        {
            "asks": [
                {
                    "page": str(page),
                    "kind": "question",
                    "title": title,
                    "text": f"{title}: which would you like?",
                    "passage": passage,
                    "quote": title,
                }
                for title in titles
            ],
            "findings": [],
        }
    )


def test_the_clerk_asks_what_the_reply_left_and_the_next_step_hears_it(claimed, capsys):
    """Each ask the fork names opens a thread of its own on the page, the agent's
    message asking the whole question with nothing marking the fork, and lands On me
    until the user answers; the next tool boundary tells the agent each one and its
    words, once. A question the agent already asked isn't asked again, and a question
    the agent withdrew stays withdrawn: the next fork is shown it as settled, and Leaf
    doesn't ask it again."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    question = asked()
    assert str(page) in question["prompt"]
    assert (
        "On me, what the page lists as waiting on the user:\n(none)"
        in question["prompt"]
    )

    # A thread the agent opened to tell rather than ask holds no ask, whatever its
    # title.
    append_carried_log_record(
        claimed,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Claude",
            "session": "s1",
            "revision": 1,
            "title": "The retry limit",
            "text": "The suite retries each flaky test.",
        },
    )
    wrote = clerk_model.take_answer(
        "s1", reply(page, "The retry limit", "A PR for this branch"), question["basis"]
    )["wrote"]
    assert [
        (record["kind"], record["title"], record["text"], record["obligation"])
        for record in wrote
    ] == [
        ("comment", "The retry limit", "The retry limit: which would you like?", True),
        (
            "comment",
            "A PR for this branch",
            "A PR for this branch: which would you like?",
            True,
        ),
    ]
    assert {(record["author"], record["session"]) for record in wrote} == {
        ("agent", "s1")
    }
    assert not any("anchor" in record or "by" in record for record in wrote)
    on_me = cmd_page_state(claimed)["queues"]["on_user"]
    assert [row["id"] for row in on_me] == [
        f"message:{record['id']}" for record in wrote
    ]

    context = hook(capsys, "PostToolBatch")
    assert (
        f'Leaf asked the user "The retry limit" On me, in a new thread on {page} as a '
        "whole," in context
    )
    assert "> The retry limit: which would you like?" in context
    assert f"leaf task end {page} message:{wrote[1]['id']} dropped" in context
    assert hook(capsys, "PostToolBatch") == ""

    again = clerk_model.take_answer(
        "s1", reply(page, "The retry limit"), question["basis"]
    )
    assert again["wrote"] == []

    # The agent, keeping its say over the record, withdraws one as not the user's.
    append_carried_log_record(
        claimed,
        {
            "kind": "todo_end",
            "author": "agent",
            "agent": "Claude",
            "session": "s1",
            "todo": f"message:{wrote[1]['id']}",
            "outcome": "dropped",
        },
    )
    question = asked()
    assert (
        "don't ask these again:\n- A PR for this branch: which would you like? (dropped)"
        in question["prompt"]
    )
    reasked = clerk_model.take_answer(
        "s1", reply(page, "A PR for this branch"), question["basis"]
    )
    assert reasked["wrote"] == []


def test_an_ask_about_a_passage_stands_on_it_or_else_on_the_page(claimed, capsys):
    """An ask about one passage opens its thread on the page's words the fork names,
    as `thread create --quote` would. Words the page doesn't show leave the ask on the
    page as a whole rather than unasked, since the fork has no next attempt, and the
    agent hears where each went."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    basis = asked()["basis"]
    answer = json.loads(reply(page, "Where the cutoff lives", "The retry budget"))
    answer["asks"][0]["passage"] = "The cutoff lives in"
    answer["asks"][1]["passage"] = "the retry budget"
    wrote = clerk_model.take_answer("s1", json.dumps(answer), basis)["wrote"]
    assert [record.get("anchor", {}).get("quote") for record in wrote] == [
        "The cutoff lives in",
        None,
    ]
    assert all(record["obligation"] for record in wrote)
    context = hook(capsys, "PostToolBatch")
    assert f'in a new thread on the words "The cutoff lives in" in {page},' in context
    assert f'"The retry budget" On me, in a new thread on {page} as a whole,' in context


def test_a_step_goes_on_me_as_a_todo_titled_as_the_action(claimed, capsys):
    """A step the user takes and confirms with Done goes On me as the agent's to-do on
    the user, on the element holding the passage it concerns or else on the page, and
    the agent hears its id. A step the agent already put on the user isn't put there
    again, open or ended."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    basis = asked()["basis"]

    def step(title, passage=""):
        return {
            "page": str(page),
            "kind": "step",
            "title": title,
            "text": "",
            "passage": passage,
            "quote": title,
        }

    answer = {
        "asks": [
            step("Run the backfill job on staging", "The cutoff lives in"),
            step("Run /reload-plugins in this Claude session"),
        ],
        "findings": [],
    }
    wrote = clerk_model.take_answer("s1", json.dumps(answer), basis)["wrote"]
    assert [
        (record["kind"], record["owner"], record["subject"]) for record in wrote
    ] == [
        ("todo", "user", {"kind": "element", "id": "plan"}),
        ("todo", "user", {"kind": "page"}),
    ]
    assert {(record["author"], record["session"]) for record in wrote} == {
        ("agent", "s1")
    }
    on_me = cmd_page_state(claimed)["queues"]["on_user"]
    assert [row["id"] for row in on_me] == [record["id"] for record in wrote]
    context = hook(capsys, "PostToolBatch")
    assert (
        f'Leaf put the step "Run /reload-plugins in this Claude session" On me as your '
        f"to-do {wrote[1]['id']} on the user, on {page} as a whole." in context
    )
    assert f"leaf task end {page} {wrote[0]['id']} dropped" in context

    append_carried_log_record(
        claimed,
        {
            "kind": "todo_end",
            "author": "agent",
            "agent": "Claude",
            "session": "s1",
            "todo": wrote[1]["id"],
            "outcome": "dropped",
        },
    )
    again = clerk_model.take_answer("s1", json.dumps(answer), asked()["basis"])
    assert again["wrote"] == []


def test_the_fork_is_asked_the_skills_account_of_the_check(claimed, capsys):
    """The fork reads the check as the skill ships it, Leaf's rule for On me as the
    agent reads it, then each page's facts, among
    them each item the agent has started with its line, which tells the fork what the
    page shows under way."""
    hook(capsys, "UserPromptSubmit")
    todo = todos_model.cmd_create(claimed, "page", "Revise the plan", "agent")
    todos_model.cmd_start(claimed, todo["id"], "revising the plan")
    prompt = asked()["prompt"]
    assert clerk_model.REFERENCE.read_text().strip() in prompt
    # The asks follow the On me rule the agent reads, sent whole.
    rule = clerk_model.on_me_rule()
    assert rule.startswith("The user's **On me** list holds everything waiting on them")
    assert rule.endswith("is not an obligation.")
    assert f"## Leaf's rule for On me\n\n{rule}\n\n" in prompt
    assert (
        "Started items, which the page shows as under way, each with its line:\n"
        f'- {todo["id"]}, the agent\'s to-do "Revise the plan": "revising the plan"'
    ) in prompt
    assert f"each title under {clerk_model.TITLE_LIMIT} characters" in prompt


def test_a_finding_reaches_the_agent_whatever_turn_opened_since(claimed, capsys):
    """A finding only the agent can act on reaches it at its next step with the
    fork's summary, the turn the fork read and the words the finding rests on. It
    still reaches the agent once another turn has opened, since the agent judges
    whether it holds, but Leaf then writes nothing: the asks beside it are dropped,
    and its fix isn't made, since that turn's agent may be editing the page."""
    page = claimed.resolve()
    source = (claimed / "index.html").read_text()
    hook(capsys, "UserPromptSubmit")
    question = asked()
    hook(capsys, "UserPromptSubmit", "p2")
    before = len(events_model.read_events(claimed))
    answer = json.loads(reply(page, "Pick one?"))
    answer["findings"] = [
        {
            "kind": "stale",
            "page": str(page),
            "summary": "The lede still gives the old cutoff of 30 days.",
            "quote": "Let's make the cutoff 14 days.",
            "edit": {"words": "Ship dark.", "replacement": "Ship behind a flag."},
        }
    ]
    done = clerk_model.take_answer("s1", json.dumps(answer), question["basis"])
    assert done["wrote"] == [] and done["changed"] == [] and "dropped" in done
    assert len(events_model.read_events(claimed)) == before
    assert (claimed / "index.html").read_text() == source
    context = hook(capsys, "PostToolBatch")
    assert (
        "read a turn before the user's latest message and found the page saying what "
        "has since changed on "
        f"{page}: The lede still gives the old cutoff of 30 days." in context
    )
    assert "(session s1):\n> Let's make the cutoff 14 days." in context
    assert "Leaf changed nothing for this" in context
    assert "Pick one?" not in context


def _stale(page, words: str, replacement: str) -> str:
    return json.dumps(
        {
            "asks": [],
            "findings": [
                {
                    "kind": "stale",
                    "page": str(page),
                    "summary": "The plan has moved on.",
                    "quote": "Let's change the plan.",
                    "edit": {"words": words, "replacement": replacement},
                }
            ],
        }
    )


def _reads(page_dir) -> str:
    """The page's words as the user reads them."""
    events = events_model.read_events(page_dir)
    reading = clerk_model._reading(page_dir, events, require_revision(page_dir))
    return reading.passages().text


def _fixed(capsys, page_dir, words: str, replacement: str) -> dict:
    """What Leaf changed for a stale finding whose fix is `words` → `replacement`,
    asked at the end of the turn it answers, with the page published as its server
    publishes it."""
    activate_source(page_dir)
    hook(capsys, "UserPromptSubmit")
    question = asked()
    return clerk_model.take_answer(
        "s1", _stale(page_dir.resolve(), words, replacement), question["basis"]
    )


@pytest.mark.parametrize(
    ("words", "replacement", "old", "new", "shown"),
    [
        (
            "Ship dark.",
            "Ship behind a flag.",
            "dark.",
            "behind a flag.",
            "Flag first Ship behind a flag.",
        ),
        # The quote crosses a link and a code span; the word that changes doesn't.
        (
            "The cutoff lives in jobs/backfill.py:88.",
            "The cutoff now lives in jobs/backfill.py:88.",
            "lives",
            "now lives",
            "The cutoff now lives in jobs/backfill.py:88.",
        ),
    ],
)
def test_the_fork_fixes_a_few_stale_words_and_tells_the_agent(
    claimed, capsys, words, replacement, old, new, shown
):
    """The fork reads the page as the user does, a block to a line, and where a few
    of its words have gone stale, Leaf swaps in the fork's words, publishes the page
    and tells the agent the old and new words, so the agent can change them back."""
    page = claimed.resolve()
    activate_source(claimed)
    hook(capsys, "UserPromptSubmit")
    question = asked()
    assert (
        "What the page says now, as the user reads it, one block per line:\n"
        "Plan\nThe cutoff lives in jobs/backfill.py:88.\n"
    ) in question["prompt"]
    done = clerk_model.take_answer(
        "s1", _stale(page, words, replacement), question["basis"]
    )
    assert done["changed"] == [{"page": str(page), "old": old, "new": new}]
    assert done["wrote"] == []
    assert shown in _reads(claimed)
    assert (
        f'Leaf changed "{old}" to "{new}" in {page}/index.html and published it.'
        in hook(capsys, "PostToolBatch")
    )


@pytest.mark.parametrize(
    ("head", "body", "words", "replacement", "after"),
    [
        # The title holds the same words, but the user reads the heading's.
        (
            "<title>Backfill: running</title>",
            "<h3>Backfill: <span>running</span></h3>",
            "Backfill: running",
            "Backfill: done",
            "<h3>Backfill: <span>done</span></h3>",
        ),
        # A tip a widget shows from its attribute, beside a paragraph with the
        # same words.
        (
            "",
            '<p>Path <lf-gloss tip="A thin path, built Monday.">gloss</lf-gloss></p>'
            "<p>Built Monday.</p>",
            "A thin path, built Monday.",
            "A thin path, built Tuesday.",
            '<p>Path <lf-gloss tip="A thin path, built Tuesday.">gloss</lf-gloss></p>'
            "<p>Built Monday.</p>",
        ),
        # The source writes a character as a reference.
        (
            "",
            "<p>Ship &amp; flip on Monday.</p>",
            "Ship & flip on Monday.",
            "Ship and flip on Monday.",
            "<p>Ship and flip on Monday.</p>",
        ),
        # Only the words that change are swapped, so a line break the source keeps
        # in preformatted text beside them stays.
        (
            "",
            "<pre>step one: build\nstep two: deploy</pre>",
            "build step two",
            "test step two",
            "<pre>step one: test\nstep two: deploy</pre>",
        ),
        # Changing words the break stands among keep it, a line in preformatted
        # text and a paragraph in a draft's Markdown.
        (
            "",
            "<pre>step one: build\nstep two: deploy</pre>",
            "build step two",
            "test phase two",
            "<pre>step one: test\nphase two: deploy</pre>",
        ),
        (
            "",
            '<lf-draft id="plan-note"><pre>\nShip quietly.\n\nNext we verify.\n</pre>'
            "</lf-draft>",
            "Ship quietly. Next we verify.",
            "Ship loudly. Then we verify.",
            '<lf-draft id="plan-note"><pre>\nShip loudly.\n\nThen we verify.\n</pre>'
            "</lf-draft>",
        ),
        # The words a widget shows from an attribute, here naming it, and words the
        # page writes beside a character from a private use area, as an icon font's.
        (
            "",
            '<p>Path <lf-gloss tip="Read the tip then go.">gloss</lf-gloss></p>',
            "Read the tip then go.",
            "Read the hint then go.",
            '<p>Path <lf-gloss tip="Read the hint then go.">gloss</lf-gloss></p>',
        ),
        (
            "",
            "<p>Prompt \U000f0001 ready. We can't ship.</p>",
            "We can't ship.",
            "We don't ship.",
            "<p>Prompt \U000f0001 ready. We don't ship.</p>",
        ),
        # A fix that would drop a line break: only preformatted text would show it.
        (
            "",
            "<pre>step one: build\nstep two: deploy</pre>",
            "build step two",
            "rebuild two",
            None,
        ),
        # Copies the user never reads: a title, a script, a style and a comment, and
        # a number inside a longer one. The words the page shows cross markup, so
        # Leaf places none of these fixes.
        (
            "<title>Ship soon Monday</title>",
            "<h3>Ship <em>soon</em> Monday</h3>",
            "Ship soon Monday",
            "Ship on Tuesday",
            None,
        ),
        (
            "<style>.wide { max-width: 30rem }</style>",
            "<h3>Cutoff: <b>30</b>rem days</h3>",
            "Cutoff: 30rem days",
            "Cutoff: 14rem days",
            None,
        ),
        (
            "",
            "<!-- old -> Ship soon Monday --><h3>Ship <em>soon</em> Monday</h3>",
            "Ship soon Monday",
            "Ship on Tuesday",
            None,
        ),
        (
            "",
            "<h3>Cutoff <b>3</b>0 days</h3><p>Due in 2030.</p>",
            "Cutoff 30 days",
            "Cutoff 14 days",
            None,
        ),
    ],
    ids=[
        "title",
        "tip",
        "reference",
        "spacing",
        "line",
        "paragraph",
        "named",
        "private",
        "dropped",
        "markup",
        "style",
        "comment",
        "longer",
    ],
)
def test_leaf_changes_the_words_the_user_reads_or_nothing(
    claimed, capsys, head, body, words, replacement, after
):
    """Leaf changes the one place in the source the user reads the words from, or,
    where it finds none, nothing at all, and the finding reaches the agent alone."""
    source = PAGE.replace("<title>t</title>", head or "<title>t</title>").replace(
        "<h2>Plan</h2>", f"<h2>Plan</h2>\n{body}"
    )
    (claimed / "index.html").write_text(source)
    done = _fixed(capsys, claimed, words, replacement)
    written = (claimed / "index.html").read_text()
    if after is None:
        assert done["changed"] == [] and written == source
        assert "Leaf changed nothing for this" in hook(capsys, "PostToolBatch")
        return
    assert len(done["changed"]) == 1
    assert written == source.replace(body, after)
    assert replacement in _reads(claimed)


@pytest.mark.parametrize(
    ("words", "replacement"),
    [
        # Words the page doesn't show.
        ("Nothing is running.", "A build is running."),
        # Words the page shows more than once.
        ("risk", "danger"),
        # A changing word that crosses markup: the colon number inside the code span
        # and the full stop outside it.
        (
            "The cutoff lives in jobs/backfill.py:88.",
            "The cutoff lives in jobs/backfill.py:90!",
        ),
    ],
)
def test_a_fix_leaf_cant_place_reaches_the_agent_as_the_finding(
    claimed, capsys, words, replacement
):
    source = (claimed / "index.html").read_text()
    done = _fixed(capsys, claimed, words, replacement)
    assert done["changed"] == []
    assert (claimed / "index.html").read_text() == source
    assert "Leaf changed nothing for this" in hook(capsys, "PostToolBatch")


def test_a_body_the_user_rewrote_keeps_their_words(claimed, capsys):
    """The user's edit stands in the draft's authored body on the page, so the
    authored words are a copy they don't read, which Leaf leaves alone."""
    (claimed / "index.html").write_text(DRAFTED)
    activate_source(claimed)
    edit(claimed, "Adds --dry-run to every mutating command now.")
    source = (claimed / "index.html").read_text()
    done = _fixed(
        capsys, claimed, "to every mutating command now.", "to each command now."
    )
    assert done["changed"] == []
    assert (claimed / "index.html").read_text() == source


def test_a_fix_keeps_the_sources_line_endings(claimed, capsys):
    crlf = PAGE.replace("\n", "\r\n").encode()
    (claimed / "index.html").write_bytes(crlf)
    done = _fixed(capsys, claimed, "Ship dark.", "Ship behind a flag.")
    assert len(done["changed"]) == 1
    assert (claimed / "index.html").read_bytes() == crlf.replace(
        b"Ship dark.", b"Ship behind a flag."
    )


def test_a_message_naming_missing_media_writes_none_of_the_answer(claimed):
    """A message is checked as `thread create` checks one, and every message before
    the first is written, so a refused one leaves the page as the fork found it."""
    page = claimed.resolve()
    answer = json.loads(reply(page, "The retry limit", "The chart"))
    answer["asks"][1]["text"] = "Does ![the chart](/media/0123456789abcdef.png) read?"
    before = len(events_model.read_events(claimed))
    with pytest.raises(Refused):
        clerk_model.take_answer("s1", json.dumps(answer), clerk_model.basis("s1"))
    assert len(events_model.read_events(claimed)) == before


def test_the_clerk_drops_an_answer_once_another_turn_opened(claimed, capsys):
    """The user spoke since the fork read the turn, so what it found may be what they
    are answering now."""
    hook(capsys, "UserPromptSubmit")
    question = asked()
    hook(capsys, "UserPromptSubmit", "p2")
    before = len(events_model.read_events(claimed))
    dropped = clerk_model.take_answer(
        "s1", reply(claimed.resolve(), "Pick one?"), question["basis"]
    )
    assert "dropped" in dropped
    assert len(events_model.read_events(claimed)) == before
    assert clerk_model.queued("s1") == []


@pytest.mark.parametrize(
    "text",
    [
        "Nothing to report.",
        '{"asks": [], "findings": [], "extra": 1}',
        '{"asks": [], "findings": [{"kind": "stale", "page": "p", "summary": " ", '
        '"quote": "", "edit": null}]}',
        '{"asks": [], "findings": [{"kind": "stale", "page": "p", "summary": "s", '
        '"quote": "", "edit": {"words": " ", "replacement": "x"}}]}',
        '{"asks": [{"page": "p", "title": "x"}]}',
        '{"asks": [{"page": "p", "kind": "question", "title": "x", "text": "", '
        '"passage": "", "quote": ""}]}',
    ],
)
def test_an_answer_outside_the_schema_writes_nothing(text):
    with pytest.raises(Refused):
        clerk_model.read_answer(text)


def test_a_finding_needs_no_edit():
    """A fork that leaves `edit` off a finding it can't fix loses none of its answer."""
    answer = {
        "asks": [],
        "findings": [{"kind": "settled", "page": "p", "summary": "s", "quote": ""}],
    }
    assert clerk_model.read_answer(json.dumps(answer)) == answer


def test_a_long_title_is_cut_at_a_word_to_fit_a_thread():
    """A model can't count characters, so a title past a thread's limit is cut rather
    than refusing the answer and the asks it found."""
    words = "Choose " + "the retry limit " * 8 + "for the suite?"
    title = clerk_model._title(words)
    assert len(title) <= clerk_model.TITLE_LIMIT
    assert title.endswith("…") and words.startswith(title[:-1] + " ")


def test_a_fenced_answer_is_read():
    answer = {"asks": [], "findings": []}
    assert clerk_model.read_answer(f"```json\n{json.dumps(answer)}\n```") == answer
