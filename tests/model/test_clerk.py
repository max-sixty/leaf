"""Leaf's clerk: the question a turn-end fork is asked, the answer it must give, and
what Leaf writes from that answer and tells the agent at its next step."""

import json

import pytest
from interact_support import DRAFTED, PAGE, append_carried_log_record, edit

from leaf.agents import clerk as clerk_model
from leaf.base import harness as harness_model
from leaf.base import state as state_model
from leaf.base.files import require_revision
from leaf.base.refusals import Refused
from leaf.commands import hooks as hooks_model
from leaf.commands import tasks as tasks_model
from leaf.commands.agent_state import cmd_page_state
from leaf.log import event_log as events_model
from leaf.log.interaction_log import read_interactions
from leaf.records.revisioning import activate_source
from leaf.source.registry.kernel import title_limit


def hook(capsys, event: str, prompt_id: str = "p1") -> str:
    hooks_model.cmd_hook(
        "claude-code",
        {"hook_event_name": event, "session_id": "s1", "prompt_id": prompt_id},
    )
    out = capsys.readouterr().out
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""


def asked() -> dict:
    """The turn-end check's question as the hooks module gets it at a turn's end
    (`hooks.cmd_fork`), with the turn its fork reads (`clerk.basis`)."""
    answer = hooks_model.cmd_fork({"session_id": "s1", "turn_end": True})
    assert answer is not None
    [check] = answer["do"]
    return {"prompt": check["request"]["prompt"], "basis": clerk_model.basis("s1")}


def reply(page, *titles: str, passage: str = "", again: str = "", choice="") -> str:
    return json.dumps(
        {
            "asks": [
                {
                    "page": str(page),
                    "title": title,
                    "text": f"{title}: which would you like?"
                    + (f"\n\n{choice}" if choice else ""),
                    "passage": passage,
                    "again": again,
                    "quote": title,
                }
                for title in titles
            ],
            "findings": [],
        }
    )


def caches(group: str = "cache") -> str:
    """A choice of the two answers the agent's reply offered, the first one it
    advised, as `threads.md` ("Ask for a pick") writes one, under ids new to the
    page."""
    return (
        f'<lf-options id="{group}">\n'
        f'<lf-option id="{group}-lru" label="Use the LRU cache" recommended><strong>Use the LRU cache</strong> '
        "81% hits</lf-option>\n"
        f'<lf-option id="{group}-ttl" label="Use the TTL cache"><strong>Use the TTL cache</strong></lf-option>\n'
        "</lf-options>"
    )


def test_the_clerk_asks_what_the_reply_left_and_the_next_step_hears_it(claimed, capsys):
    """Each ask the fork names opens a thread of its own on the page, the agent's
    message asking the whole question with nothing marking the fork, and lands On Me
    until the user answers; the next tool boundary tells the agent each one and its
    words, once. A question the agent withdrew is shown to the next fork as settled,
    with its id, which is how the fork knows not to word it anew; an ask the fork
    makes under the same title is still asked, as a new question."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    question = asked()
    assert str(page) in question["prompt"]
    assert (
        "On Me, what the page lists as waiting on the user:\n(none)"
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
        f'Leaf asked the user "The retry limit" On Me, in a new thread on {page} as a '
        "whole," in context
    )
    assert "> The retry limit: which would you like?" in context
    assert f"leaf thread resolve {page} {wrote[1]['id']}" in context
    assert hook(capsys, "PostToolBatch") == ""

    # The agent, keeping its say over the record, withdraws one as not the user's.
    append_carried_log_record(
        claimed,
        {
            "kind": "resolve",
            "author": "agent",
            "agent": "Claude",
            "session": "s1",
            "parent": wrote[1]["id"],
        },
    )
    question = asked()
    assert (
        f'- message:{wrote[1]["id"]}, in "A PR for this branch", closed by the agent: '
        "A PR for this branch: which would you like?" in question["prompt"]
    )
    [asked_anew] = clerk_model.take_answer(
        "s1", reply(page, "A PR for this branch"), question["basis"]
    )["wrote"]
    assert asked_anew["title"] == "A PR for this branch"


def test_a_question_asked_again_reopens_its_thread_under_its_id(claimed, capsys):
    """The user closed a question's thread without replying, and the agent asks it
    again in chat, as when the step they took didn't work. The next fork sees the
    closed question with its id, and an ask naming that id asks it again in its
    thread as the agent's message, which reopens the thread and puts the question
    back On Me under its own id, standing on the new message. An id Leaf can't ask
    again leaves the ask a thread of its own."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    first = clerk_model.take_answer(
        "s1", reply(page, "Reloading the plugin"), asked()["basis"]
    )["wrote"][0]
    question = f"message:{first['id']}"
    append_carried_log_record(
        claimed, {"kind": "resolve", "author": "user", "parent": first["id"]}
    )
    hook(capsys, "PostToolBatch")

    basis = asked()
    assert (
        f'- {question}, in "Reloading the plugin", closed by the user: '
        "Reloading the plugin: which would you like?" in basis["prompt"]
    )
    again = clerk_model.take_answer(
        "s1",
        reply(page, "Reloading the plugin in the other session", again=question),
        basis["basis"],
    )["wrote"]
    assert [(r["kind"], r["parent"], r["obligation"]) for r in again] == [
        ("reply", first["id"], [question])
    ]
    state = cmd_page_state(claimed)
    assert {t["id"]: t["resolved"] for t in state["threads"]}[first["id"]] is None
    assert [(row["id"], row["also"]) for row in state["queues"]["on_user"]] == [
        (question, [])
    ]
    [record] = [o for o in state["obligations"] if o["id"] == question]
    assert (record["message"], record["next_actor"]) == (again[0]["id"], "user")
    # The next fork reads it On Me in the words it is asked in now.
    assert (
        '- a reply to the agent\'s message in "Reloading the plugin": Reloading the '
        "plugin in the other session: which would you like?" in asked()["prompt"]
    )
    context = hook(capsys, "PostToolBatch")
    assert (
        f"On Me again, as {question}, with your message {again[0]['id']} in its "
        f"thread on {page}," in context
    )
    assert f"leaf thread resolve {page} {again[0]['id']}" in context

    elsewhere = clerk_model.take_answer(
        "s1", reply(page, "The retry limit", again="message:nowhere"), basis["basis"]
    )["wrote"]
    assert [(r["kind"], r["title"]) for r in elsewhere] == [
        ("comment", "The retry limit")
    ]


def test_an_ask_about_a_passage_quotes_it_and_says_where_the_files_miss(
    claimed, capsys
):
    """An ask about one passage opens its thread quoting the page's words the fork
    names, as `thread create --quote` would, and is asked whether or not the page's
    files hold them. The agent hears what Leaf noted of words its reading of the files
    doesn't find once, which the page shows in Threads unless it draws them once."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    basis = asked()["basis"]
    answer = json.loads(reply(page, "Where the cutoff lives", "The retry budget"))
    answer["asks"][0]["passage"] = "The cutoff lives in"
    answer["asks"][1]["passage"] = "the retry budget"
    wrote = clerk_model.take_answer("s1", json.dumps(answer), basis)["wrote"]
    assert [record["anchor"]["quote"] for record in wrote] == [
        "The cutoff lives in",
        "the retry budget",
    ]
    assert all(record["obligation"] for record in wrote)
    context = hook(capsys, "PostToolBatch")
    assert f'in a new thread quoting "The cutoff lives in" in {page},' in context
    assert f'in a new thread quoting "the retry budget" in {page},' in context
    assert context.count("Leaf's reading of the page's files finds") == 1
    assert "finds 'the retry budget' nowhere" in context


def test_an_ask_with_listable_answers_is_a_choice_the_user_presses(claimed, capsys):
    """Where the fork's message holds a choice of the answers the agent's reply
    offered, as `threads.md` has the agent ask ("Ask for a pick"), Leaf posts it as
    the agent's command would, so the choice draws and asks in place of an
    obligation: it waits on the user On Me until they pick, and a reply in words
    doesn't answer it. The agent hears the choice it now owns, and the next fork sees
    it On Me."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    basis = asked()["basis"]
    [record] = clerk_model.take_answer(
        "s1", reply(page, "LRU or TTL", choice=caches()), basis
    )["wrote"]
    assert (record["kind"], record["title"]) == ("comment", "LRU or TTL")
    assert "obligation" not in record

    def choice() -> dict:
        [obligation] = [
            o
            for o in cmd_page_state(claimed)["obligations"]
            if o["message"] == record["id"]
        ]
        return obligation

    asking = choice()
    assert (asking["source"], asking["next_actor"]) == (
        {"kind": "widget", "id": "cache", "tag": "lf-options"},
        "user",
    )
    assert [row["id"] for row in cmd_page_state(claimed)["queues"]["on_user"]] == [
        asking["id"]
    ]

    context = hook(capsys, "PostToolBatch")
    assert (
        f'Leaf asked the user "LRU or TTL" On Me, in a new thread on {page} as a '
        f"whole, opened by your message {record['id']}:\n> LRU or TTL: which would "
        'you like?\n> \n> <lf-options id="cache">\n'
    ) in context
    assert "the user's answer in its widget reaches you as any answer does" in context
    assert (
        '\n- decision in the agent\'s message in "LRU or TTL": LRU or TTL: which '
        'would you like? <lf-options id="cache">' in asked()["prompt"]
    )

    append_carried_log_record(
        claimed,
        {
            "kind": "reply",
            "author": "user",
            "parent": record["id"],
            "text": "Before I pick, how stale can a result get?",
        },
    )
    assert choice()["state"] == "waiting"


def test_a_choice_leaf_refuses_is_handed_to_the_agent(claimed, capsys):
    """A choice whose HTML Leaf refuses, here for an id the page's first choice
    already took, isn't asked: the fork has no next attempt, so the agent hears the
    message and why, and asks it itself."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    basis = asked()["basis"]
    clerk_model.take_answer("s1", reply(page, "LRU or TTL", choice=caches()), basis)
    hook(capsys, "PostToolBatch")
    answer = reply(page, "The cache's size", choice=caches())
    assert clerk_model.take_answer("s1", answer, basis)["wrote"] == []
    context = hook(capsys, "PostToolBatch")
    assert 'Leaf would have asked the user "The cache\'s size"' in context
    assert '<lf-options id="cache">' in context
    assert "cache" in context.split("It refused the message, so nothing was asked")[1]


def test_a_question_asked_again_with_listable_answers_is_a_choice_in_its_thread(
    claimed, capsys
):
    """A clarifying reply answered a question asked in words, the user closed its
    thread once the agent answered them, and the agent asks the question again in
    chat with answers it can list. Leaf asks it in its thread with a choice, which
    reopens the thread, rather than in words under its id."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    first = clerk_model.take_answer("s1", reply(page, "LRU or TTL"), asked()["basis"])[
        "wrote"
    ][0]
    asked_back = append_carried_log_record(
        claimed,
        {
            "kind": "reply",
            "author": "user",
            "parent": first["id"],
            "text": "How stale can a result get?",
        },
    )
    append_carried_log_record(
        claimed,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "session": "s1",
            "parent": first["id"],
            "responds": asked_back["id"],
            "text": "Up to 41 minutes with LRU, five with TTL.",
        },
    )
    append_carried_log_record(
        claimed, {"kind": "resolve", "author": "user", "parent": first["id"]}
    )
    hook(capsys, "PostToolBatch")
    question = f"message:{first['id']}"
    [again] = clerk_model.take_answer(
        "s1",
        reply(page, "LRU or TTL", again=question, choice=caches()),
        asked()["basis"],
    )["wrote"]
    assert (again["kind"], again["parent"]) == ("reply", first["id"])
    assert "obligation" not in again
    state = cmd_page_state(claimed)
    assert {t["id"]: t["resolved"] for t in state["threads"]}[first["id"]] is None
    records = {o["message"]: o for o in state["obligations"]}
    assert records[first["id"]]["answered"]
    assert (records[again["id"]]["source"]["kind"], records[again["id"]]["state"]) == (
        "widget",
        "waiting",
    )
    assert (
        f"On Me again, with your message {again['id']} in the thread of {question} "
        f"on {page}, which reopens the thread if it was closed:"
    ) in hook(capsys, "PostToolBatch")


def test_a_choice_the_user_answered_with_a_question_stays_asked(claimed, capsys):
    """The user answers a choice with a question of their own, which hands the
    choice to the agent until it answers them, so On Me lists nothing. The next fork
    sees the choice as still open, which keeps it from asking the choice again when
    the agent restates it in chat. An ask that names the choice anyway posts nothing:
    the agent hears that the thread waits on its reply. The user's question is
    theirs, not one the page asked them, so the fork never sees it among the
    questions it may ask again."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    [first] = clerk_model.take_answer(
        "s1", reply(page, "LRU or TTL", choice=caches()), asked()["basis"]
    )["wrote"]
    asked_back = append_carried_log_record(
        claimed,
        {
            "kind": "reply",
            "author": "user",
            "parent": first["id"],
            "text": "How stale can a result get?",
        },
    )
    hook(capsys, "PostToolBatch")
    prompt = asked()["prompt"]
    assert "On Me, what the page lists as waiting on the user:\n(none)" in prompt
    assert (
        "ask none of these again:\n- decision in the agent's message in \"LRU or "
        'TTL": LRU or TTL: which would you like?' in prompt
    )
    answer = reply(
        page, "LRU or TTL", again=f"message:{first['id']}", choice=caches("again")
    )
    assert clerk_model.take_answer("s1", answer, asked()["basis"])["wrote"] == []
    context = hook(capsys, "PostToolBatch")
    assert (
        f"in the thread of message:{first['id']} on {page}, but that thread waits on "
        "your reply" in context
    )
    assert "leaf thread reply" in context

    append_carried_log_record(
        claimed,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "session": "s1",
            "parent": first["id"],
            "responds": asked_back["id"],
            "text": "Up to 41 minutes with LRU, five with TTL.",
        },
    )
    prompt = asked()["prompt"]
    assert (
        "On Me, what the page lists as waiting on the user:\n- decision in the "
        'agent\'s message in "LRU or TTL"' in prompt
    )
    assert "ask none of these again" not in prompt
    assert asked_back["id"] not in prompt


@pytest.mark.parametrize("words", [False, True], ids=["choice", "words"])
def test_a_choice_the_user_closed_is_asked_again_in_its_thread(claimed, capsys, words):
    """The user closed a choice's thread without picking, and the agent asks it
    again in chat. The next fork sees the choice with the id that names it, and an ask
    naming that id asks it again in its thread, reopening it, rather than a title
    check dropping it: as a choice where the fork writes one, and otherwise in words,
    as a new question."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    [first] = clerk_model.take_answer(
        "s1", reply(page, "LRU or TTL", choice=caches()), asked()["basis"]
    )["wrote"]
    append_carried_log_record(
        claimed, {"kind": "resolve", "author": "user", "parent": first["id"]}
    )
    hook(capsys, "PostToolBatch")
    basis = asked()
    question = f"message:{first['id']}"
    assert (
        f'- {question}, in "LRU or TTL", closed by the user: LRU or TTL: which would '
        "you like?" in basis["prompt"]
    )
    choice = "" if words else caches("cache-again")
    [again] = clerk_model.take_answer(
        "s1",
        reply(page, "LRU or TTL", again=question, choice=choice),
        basis["basis"],
    )["wrote"]
    assert (again["kind"], again["parent"]) == ("reply", first["id"])
    assert again.get("obligation") is (True if words else None)
    state = cmd_page_state(claimed)
    assert {t["id"]: t["resolved"] for t in state["threads"]}[first["id"]] is None
    [record] = [o for o in state["obligations"] if o["message"] == again["id"]]
    assert (record["state"], record["next_actor"]) == ("waiting", "user")
    # The agent hears the id the question now stands under: the reply's own where it
    # asks the choice's question anew in words.
    assert (
        f"On Me again, as {record['id']}, with your message {again['id']} in its "
        if words
        else f"On Me again, with your message {again['id']} in the thread of {question} "
    ) in hook(capsys, "PostToolBatch")
    assert not words or record["id"] == f"message:{again['id']}"


def test_a_closed_choice_asked_again_with_html_leaf_refuses_is_handed_to_the_agent(
    claimed, capsys
):
    """The fork asks a closed choice again under its title, with a choice whose HTML
    Leaf refuses, here for the id the first choice took. Leaf asks nothing in its
    thread, and the agent hears the message and why."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    [first] = clerk_model.take_answer(
        "s1", reply(page, "LRU or TTL", choice=caches()), asked()["basis"]
    )["wrote"]
    append_carried_log_record(
        claimed, {"kind": "resolve", "author": "user", "parent": first["id"]}
    )
    hook(capsys, "PostToolBatch")
    answer = reply(page, "LRU or TTL", again=f"message:{first['id']}", choice=caches())
    assert clerk_model.take_answer("s1", answer, asked()["basis"])["wrote"] == []
    assert "It refused the message, so nothing was asked" in hook(
        capsys, "PostToolBatch"
    )


def test_an_ask_again_naming_a_message_that_asks_nothing_opens_its_own_thread(
    claimed, capsys
):
    """An ask naming, as the question it asks again, the agent's answer in a thread
    the user opened, which asks nothing, can't be asked there, whether it holds a
    choice or not, so it opens a thread of its own rather than joining that one."""
    page = claimed.resolve()
    activate_source(claimed)
    hook(capsys, "UserPromptSubmit")
    comment = append_carried_log_record(
        claimed, {"kind": "comment", "author": "user", "text": "Why 50,000 entries?"}
    )
    answer = append_carried_log_record(
        claimed,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "session": "s1",
            "parent": comment["id"],
            "responds": comment["id"],
            "text": "It fits the 2 GB the search hosts spare.",
        },
    )
    hook(capsys, "PostToolBatch")
    basis = asked()["basis"]
    for title, choice in (("LRU or TTL", caches()), ("The cache's size", "")):
        [record] = clerk_model.take_answer(
            "s1",
            reply(page, title, again=f"message:{answer['id']}", choice=choice),
            basis,
        )["wrote"]
        assert (record["kind"], record["title"]) == ("comment", title)


def test_a_widget_in_a_message_reads_as_its_own_question(claimed, capsys):
    """The next fork reads a widget asking in a thread message by the question the
    widget itself asks, and by the message's words only where it asks none, as a
    choice beneath the question its message asks."""
    activate_source(claimed)
    hook(capsys, "UserPromptSubmit")
    append_carried_log_record(
        claimed,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Claude",
            "session": "s1",
            "revision": 1,
            "title": "Next steps",
            "text": "The benchmark is complete. Please answer below.\n\n"
            '<lf-group id="ask-cache" label="Which cache should we use?">\n<h3 id="ask-cache-h">Which cache should we use?</h3>\n'
            '<lf-options id="cache"><lf-option id="lru">LRU</lf-option>'
            '<lf-option id="ttl">TTL</lf-option></lf-options>\n</lf-group>',
        },
    )
    assert (
        '\n- decision in the agent\'s message in "Next steps": Which cache should we '
        "use?\n" in asked()["prompt"]
    )


def test_the_fork_is_asked_the_skills_account_of_the_check(claimed, capsys):
    """The fork reads the check as the skill ships it, the agent's guidance for
    asking as the agent reads it, then each page's facts, among
    them each item the agent has started with its line, which tells the fork what the
    page shows under way."""
    hook(capsys, "UserPromptSubmit")
    todo = tasks_model.cmd_create(claimed, "page", "Revise the plan")
    tasks_model.cmd_start(claimed, todo["id"], "revising the plan")
    prompt = asked()["prompt"]
    assert clerk_model.REFERENCE.read_text().strip() in prompt
    # The asks follow the guidance the agent reads, each paragraph sent whole.
    rule, *rest = clerk_model.guidance()
    assert rule.startswith("The user's **On Me** list holds everything waiting on them")
    assert rule.endswith("is not an obligation.")
    assert f"## Leaf's guidance for asking and for threads\n\n{rule}\n\n" in prompt
    assert all(paragraph in prompt for paragraph in rest)
    # A paragraph comes with the example after it, which shows the markup it asks
    # for, as the advised option's `recommended`; the fork can't open the reference.
    (choice,) = (each for each in rest if each.startswith("When a message asks"))
    assert choice.endswith("</lf-options>\nEOF\n```")
    assert 'label="Keep the account store" recommended>' in choice
    assert (
        "Started items, which the page shows as under way, each with its line:\n"
        f'- {todo["id"]}, the agent\'s to-do "Revise the plan": "revising the plan"'
    ) in prompt
    assert f"each title under {title_limit()} characters" in prompt


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
        "read a turn before the user's latest message and found the page holding what "
        "no longer fits the work on "
        f"{page}: The lede still gives the old cutoff of 30 days." in context
    )
    assert "(session s1):\n> Let's make the cutoff 14 days." in context
    assert "Leaf changed nothing for this" in context
    assert "Pick one?" not in context


def test_a_finding_only_the_agent_can_act_on_wakes_the_idle_session(
    claimed, interactive, capsys, monkeypatch
):
    """A finding Leaf changed nothing for is work the agent owes before the user
    reads the page again, so its line wakes the session once the turn that left it
    has closed, and a session no watch follows is nudged for it, once Leaf has queued
    the line. An ask Leaf wrote itself only tells, so its line waits for the agent's
    next step; once a hook has printed the lines, nothing wakes."""
    nudged = []
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness,
        "nudge",
        lambda harness, page: nudged.append(clerk_model.waking("s1")) or True,
    )
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    question = asked()
    state_model.close_session_turn("s1")
    answer = json.loads(reply(page, "Pick one?"))
    answer["findings"] = [
        {
            "kind": "stale",
            "page": str(page),
            "summary": "The page still opens on the merged cutoff change.",
            "quote": "Next, look at the slow queries.",
            "edit": None,
        }
    ]
    done = clerk_model.take_answer("s1", json.dumps(answer), question["basis"])
    [owed] = [line for line in done["told"] if "merged cutoff change" in line]
    assert clerk_model.waking("s1") == [owed]
    assert len(clerk_model.queued("s1")) == 2
    assert nudged == [[owed]]
    hook(capsys, "UserPromptSubmit", "p2")
    assert clerk_model.queued("s1") == []

    # A fork that read a turn before the latest one still tells the agent, but nudges
    # nothing: that later turn ended on its own terms, Escape perhaps, and waits for
    # the user's next prompt.
    state_model.close_session_turn("s1")
    clerk_model.take_answer("s1", json.dumps(answer), question["basis"])
    assert len(clerk_model.waking("s1")) == 1
    assert nudged == [[owed]]


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
    assert clerk_model.waking("s1") == []
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
        # A gloss's explanation, which the page shows only when opened, beside a
        # paragraph with the same words.
        (
            "",
            "<p>Path <lf-gloss>gloss<span popover>A thin path, built Monday.</span></lf-gloss></p>"
            "<p>Built Monday.</p>",
            "A thin path, built Monday.",
            "A thin path, built Tuesday.",
            "<p>Path <lf-gloss>gloss<span popover>A thin path, built Tuesday.</span></lf-gloss></p>"
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
        # A gloss's explanation, here naming it, and words the page writes beside a
        # character from a private use area, as an icon font's.
        (
            "",
            "<p>Path <lf-gloss>gloss<span popover>Read the tip then go.</span></lf-gloss></p>",
            "Read the tip then go.",
            "Read the hint then go.",
            "<p>Path <lf-gloss>gloss<span popover>Read the hint then go.</span></lf-gloss></p>",
        ),
        (
            "",
            "<p>Prompt \U000f0001 ready. We can't ship.</p>",
            "We can't ship.",
            "We don't ship.",
            "<p>Prompt \U000f0001 ready. We don't ship.</p>",
        ),
        # In preformatted text, a fix that changes how many words stand beside or
        # among a line break, since which line each belongs on is a guess.
        (
            "",
            "<pre>step one: build\nstep two: deploy</pre>",
            "build step two",
            "rebuild two",
            None,
        ),
        (
            "",
            "<pre>make build\nmake deploy</pre>",
            "build make",
            "build --fast make",
            None,
        ),
        # Outside one, a line break is a space.
        (
            "",
            "<p>The plan\nships today.</p>",
            "The plan ships today.",
            "The plan ships.",
            "<p>The plan\nships.</p>",
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
        "inserted",
        "wrapped",
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
        # Replacement words written as markup, which Leaf writes as text alone, so
        # a link would show as its tag.
        ("Ship dark.", 'Ship <a href="https://example.com/pull/12">#12</a>.'),
        ("Ship dark.", "Ship <code>--dark</code>."),
    ],
    ids=["unshown", "repeated", "crossing", "link", "code"],
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


def test_a_message_naming_missing_media_is_handed_to_the_agent(claimed, capsys):
    """A message is checked as `thread create` checks one. One Leaf refuses, here for
    a picture the page hasn't got, isn't asked, and the agent hears it and why; the
    fork's other asks are asked."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    answer = json.loads(reply(page, "The retry limit", "The chart"))
    answer["asks"][1]["text"] = "Does ![the chart](/media/0123456789abcdef.png) read?"
    [record] = clerk_model.take_answer("s1", json.dumps(answer), asked()["basis"])[
        "wrote"
    ]
    assert record["title"] == "The retry limit"
    context = hook(capsys, "PostToolBatch")
    assert 'Leaf would have asked the user "The chart"' in context
    assert "0123456789abcdef.png" in context.split("It refused the message")[1]


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


def test_each_fork_leaves_a_note_in_the_pages_diagnostics(claimed, capsys):
    """Claude Code keeps no copy of a fork's exchange, so each page the session holds
    notes what the fork named there and what came of it, with the fork's tokens and
    time, whatever it found: nothing, records and a fix, no answer, or one Leaf
    refuses."""
    page = claimed.resolve()
    activate_source(claimed)
    hook(capsys, "UserPromptSubmit")
    question = asked()
    run = {
        "done": "check",
        "do": "fork",
        "basis": {"kind": "check", **question["basis"]},
        "usage": {"output_tokens": 9},
        "elapsed_ms": 1200,
    }

    def notes() -> list[dict]:
        return read_interactions(claimed, types=("turn_end_check",))

    clerk_model.checked("s1", {**run, "answer": '{"asks": [], "findings": []}'})
    answer = json.loads(reply(page, "Pick one?"))
    answer["findings"] = json.loads(_stale(page, "Ship dark.", "Ship behind a flag."))[
        "findings"
    ]
    done = clerk_model.checked("s1", {**run, "answer": json.dumps(answer)})
    assert done["log"].startswith(f"the clerk wrote {len(done['wrote'])} record")
    clerk_model.checked("s1", {**run, "failed": "the fork was aborted"})
    refusal = clerk_model.checked("s1", {**run, "answer": "Nothing to report."})
    assert refusal["refused"] and "the clerk wrote nothing" in refusal["log"]

    empty, found, failed, refused = notes()
    assert {
        name: empty.get(name)
        for name in ("session", "turn", "asks", "findings", "usage", "elapsedMs")
    } == {
        "session": "s1",
        "turn": question["basis"]["turn"],
        "asks": [],
        "findings": [],
        "usage": {"output_tokens": 9},
        "elapsedMs": 1200,
    }
    assert (found["asks"], found["findings"]) == (answer["asks"], answer["findings"])
    assert found["wrote"] == [record["id"] for record in done["wrote"]]
    assert found["changed"] == [{"old": "dark.", "new": "behind a flag."}]
    assert found["told"] == 2
    assert failed["failed"] == "the fork was aborted" and "asks" not in failed
    assert refused["answer"] == "Nothing to report." and refused["refused"]


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
        '{"asks": [{"page": "p", "title": "x", "text": "", "passage": "", '
        '"quote": ""}]}',
        '{"asks": [{"page": "p", "kind": "step", "title": "x", "text": "Run it.", '
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


def test_a_long_title_is_cut_at_a_word_to_fit_a_thread(claimed, capsys):
    """A model can't count characters, so a title past a thread's limit is cut rather
    than refusing the answer and the asks it found."""
    page = claimed.resolve()
    hook(capsys, "UserPromptSubmit")
    words = "Choose " + "the retry limit " * 8 + "for the suite?"
    [record] = clerk_model.take_answer("s1", reply(page, words), asked()["basis"])[
        "wrote"
    ]
    title = record["title"]
    assert len(title) <= title_limit()
    assert title.endswith("…") and words.startswith(title[:-1] + " ")


def test_a_fenced_answer_is_read():
    answer = {"asks": [], "findings": []}
    assert clerk_model.read_answer(f"```json\n{json.dumps(answer)}\n```") == answer
