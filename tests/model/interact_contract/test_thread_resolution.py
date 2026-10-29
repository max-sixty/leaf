"""How an answer, an undo, a resolve or new words settle or reopen a thread, read the
same by every fold and its membership."""

import itertools
import json
from copy import deepcopy

import model_folds as model
from interact_support import (
    ACCEPT,
    COMMENT,
    FLOW_PAGE,
    PAGE,
    ModelPage,
    append_carried_log_record,
    fetch,
    publish,
)

from leaf import delivery as delivery_model
from leaf import event_contracts as event_contracts_model
from leaf import event_log as events_model
from leaf import events as event_folds_model
from leaf import files as files_model
from leaf import passages as passages_model
from leaf import structure as structure_model
from leaf import thread as thread_model
from leaf.registry import storage as registry_storage
from model.interact_contract import declare_vocabulary, vocabulary


def test_new_words_reopen_a_thread_without_settling_a_newer_user_turn(page_dir):
    """Late answers keep their exact scope; marks and failure receipts stay closed."""
    publish(page_dir)
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "question", "author": "user", "text": "Why?"},
    )
    thread_model.cmd_resolve(page_dir, "question")
    for message in (
        {"author": "user", "token": "keep"},
        {
            "author": "agent",
            "text": "Delivery failed",
            "failure": "unavailable",
            "responds": "question",
        },
    ):
        append_carried_log_record(
            page_dir, {"kind": "reply", "parent": "question", **message}
        )
        threads = event_folds_model.build_threads(
            events_model.read_events(page_dir), {}
        )
        assert threads["question"]["resolved"] is not None

    answer = thread_model.post_reply(
        page_dir,
        {"parent": "question", "responds": "question"},
        "Here is the completed answer.",
        settlement=thread_model.ProviderFinal("test-final"),
    )
    assert answer["responds"] == "question"
    threads = event_folds_model.build_threads(events_model.read_events(page_dir), {})
    assert threads["question"]["resolved"] is None
    assert not event_folds_model.awaits_agent(threads["question"])
    assert (
        delivery_model.current_responses(page_dir, events_model.read_events(page_dir))
        == {}
    )

    thread_model.cmd_resolve(page_dir, answer["id"])
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "id": "correction",
            "author": "user",
            "parent": answer["id"],
            "text": "Please address this correction too.",
        },
    )
    threads = event_folds_model.build_threads(events_model.read_events(page_dir), {})
    assert threads["question"]["resolved"] is None
    thread_model.post_reply(
        page_dir,
        {"parent": "question", "responds": "question"},
        "Additional detail on the original question.",
        settlement=thread_model.ProviderFinal("test-final"),
    )
    assert delivery_model.current_responses(
        page_dir, events_model.read_events(page_dir)
    ) == {
        "correction": {
            "kind": "reply",
            "parent": "correction",
            "responds": "correction",
        }
    }
    closed = thread_model.cmd_resolve(page_dir, "question")
    threads = event_folds_model.build_threads(events_model.read_events(page_dir), {})
    assert threads["question"]["resolved"]["id"] == closed["id"]


def test_late_answer_to_a_frozen_widget_reopens_without_repeating_its_obligation(
    server, page_dir
):
    """Reopening restores the thread while its completed choice stays answered."""
    publish(page_dir)
    question = thread_model.cmd_comment(
        page_dir,
        None,
        None,
        None,
        "Choose an option.",
        '<lf-ask id="thread-ask"><h2>Choose one</h2>'
        '<lf-options id="thread-picks" choose><lf-option id="thread-option">'
        "Thread option</lf-option></lf-options></lf-ask>",
    )
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {
                "kind": "action",
                "revision": files_model.latest_revision(page_dir),
                "widget": "thread-picks",
                "action": "choose",
                "detail": {"value": ["thread-option"]},
            }
        ).encode(),
    )
    assert status == 200, body
    choice = json.loads(body)["state"]["events"][-1]
    assert choice["id"] in delivery_model.current_responses(
        page_dir, events_model.read_events(page_dir)
    )
    thread_model.cmd_resolve(page_dir, question["id"])
    answer = thread_model.post_reply(
        page_dir,
        {"parent": question["id"], "responds": choice["id"]},
        "I applied your choice.",
        settlement=thread_model.ProviderFinal("test-final"),
    )
    assert answer["responds"] == choice["id"]
    threads = event_folds_model.build_threads(events_model.read_events(page_dir), {})
    assert threads[question["id"]]["resolved"] is None
    assert (
        delivery_model.current_responses(page_dir, events_model.read_events(page_dir))
        == {}
    )


# Two suggestions on one page, and the decisions a user takes on them. The
# widgets are here rather than named only in the events because a settlement
# rests on its widget: the door derives each action's coordinate and its answer
# from this markup, so a log that named a widget the page has not got would be
# refused rather than folded.
SETTLED = model.leaf_page(
    "feeders",
    """<h1 id="feeders">Feeders</h1>
<lf-suggestion id="sug-a" resolves="e1">
  <lf-old><p id="a-old">Refill every feeder each morning.</p></lf-old>
  <lf-new><p id="a-new">Refill when the camera shows it half-empty.</p></lf-new>
</lf-suggestion>
<lf-suggestion id="sug-b" resolves="e1">
  <lf-old><p id="b-old">Check the cameras weekly.</p></lf-old>
  <lf-new><p id="b-new">Check the cameras each morning.</p></lf-new>
</lf-suggestion>""",
)


ASKED = {"kind": "comment", "text": "cameras are flaky"}


PICKED = {
    "kind": "action",
    "widget": "sug-a",
    "action": "decide",
    "detail": {"outcome": "accept"},
}


TURNED_DOWN = {
    "kind": "action",
    "widget": "sug-a",
    "action": "decide",
    "detail": {"outcome": "reject"},
}


CLOSED = {"kind": "resolve", "parent": "e1"}


def settlement(*events):
    """What the thread `e1` stands resolved by, after exactly this log."""
    return model.threads(model.reading(SETTLED, events))["e1"]["resolved"]


def test_an_accept_carries_its_thread_resolution():
    """One atomic event: admission reads the thread the accept answers off the
    widget's authored `resolves` in the document it was made on, because the honoring
    version retires the wrapper that held the mapping. A reject declines the fix and
    closes nothing."""
    threads = model.threads(
        model.reading(
            SETTLED,
            (
                ASKED,
                {"kind": "comment", "text": "the other thing"},
                PICKED,
                {**TURNED_DOWN, "widget": "sug-b"},
            ),
        )
    )
    assert threads["e1"]["resolved"]["widget"] == "sug-a"
    assert threads["e2"]["resolved"] is None
    assert threads["e1"]["resolved"]["meaning"]["answer"] == "e1"


def test_the_answer_that_settles_a_thread_acknowledges_what_it_said():
    """Deciding the suggestion a thread asked for is a move in that thread even
    though the widget stands on the page, so the agent's reply before it reads as
    taken in, as a reply or resolve there would. A move that changes the thread
    without being made in it shows the user nothing there: neither the undo that
    takes the answer back nor a later decision that supersedes it reads the
    agent's words, so what those words say stays unread."""
    reply = {
        "kind": "reply",
        "author": "agent",
        "agent": "Agent",
        "session": "session-1",
        "parent": "e1",
        "text": "Try sug-a.",
    }
    edit = {
        "kind": "edit",
        "author": "agent",
        "agent": "Agent",
        "session": "session-1",
        "message": "e2",
    }

    def unread(*events):
        thread = model.threads(model.reading(SETTLED, (ASKED, reply, *events)))["e1"]
        return [item["version"] for item in thread["unread"]]

    assert unread() == ["e2"]
    assert unread(PICKED) == []
    assert unread(PICKED, {"kind": "undo", "undoes": "e3"}) == ["e2"]
    assert unread(PICKED, {**edit, "text": "Try sug-a first."}, TURNED_DOWN) == ["e4"]


def test_an_answer_the_user_took_back_leaves_its_thread_open(page_dir):
    """An action names the thread it settles, and it settles it only while the
    user still stands behind it. Withdrawing the answer is one of the three ways
    an action stops being in force — a `restated` version and a later answer from the
    same widget are the others — and the thread reading owes all three the same
    reply, or a question would read as answered by a gesture the log itself records
    as taken back."""
    append_carried_log_record(
        page_dir,
        {"kind": "comment", "id": "c1", "author": "user", "text": "which mounts?"},
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "action",
            "id": "a1",
            "author": "user",
            "revision": 1,
            "widget": "picks",
            "action": "choose",
            "detail": {"value": ["flag-first"]},
            "meaning": {
                "scope": "page",
                "unit": "picks",
                "depends": ["flag-first", "picks"],
                "answer": "c1",
            },
        },
    )
    spk = passages_model.SourceReading(
        structure_model.SourceDocument(
            (page_dir / "index.html").read_text(encoding="utf-8")
        ),
        registry_storage.require_registry(page_dir),
    ).spoken
    threads = event_folds_model.build_threads(
        events_model.read_events(page_dir), passages_model.enclosing_of(spk)
    )
    assert threads["c1"]["resolved"]["id"] == "a1"

    append_carried_log_record(
        page_dir, {"kind": "undo", "author": "user", "undoes": "a1"}
    )
    threads = event_folds_model.build_threads(
        events_model.read_events(page_dir), passages_model.enclosing_of(spk)
    )
    assert threads["c1"]["resolved"] is None


def test_a_reject_after_an_accept_reopens_the_thread():
    """A thread stands settled by its widget's answer in force, not by the fact an
    answer was once given. Turning the fix down and leaving the question filed away
    as answered by it is invisible from both sides — the fold reports the suggestion
    rejected while the panel reports the thread closed, and nothing says so.

    Read across the reject rather than after it: an assertion that the thread is open
    passes just as well on a log where the accept never settled it."""
    assert settlement(ASKED, PICKED)["detail"] == {"outcome": "accept"}
    assert settlement(ASKED, PICKED, TURNED_DOWN) is None


def test_an_accept_after_a_reject_settles_the_thread():
    """The other order, which the one-way latch already got right — this pins it
    against the fix for the latch, not against the latch. A fold that kept the
    first answer per widget rather than the last reads every case here correctly
    except this one, where nothing would ever settle the thread."""
    assert settlement(ASKED, TURNED_DOWN) is None
    assert settlement(ASKED, TURNED_DOWN, PICKED)["detail"] == {"outcome": "accept"}


def test_a_resolve_between_two_decisions_outlives_the_second():
    """A resolve is a person saying the thread is done, and the log cannot
    take that back the way it takes back a decision. The one-way latch got this
    right by never clearing anything; what it pins is the obvious wrong fix for the
    latch — a reject that clears whatever its widget resolved — which would wipe a
    press made in between. Settling in place is what makes it hold: the superseded
    accept never stood, so it has nothing to clear."""
    assert settlement(ASKED, PICKED, CLOSED)["kind"] == "resolve"
    assert settlement(ASKED, PICKED, CLOSED, TURNED_DOWN)["kind"] == "resolve"


def test_taking_back_a_reject_lets_the_accept_it_superseded_stand_again():
    """The two ways an answer stops being in force compose, and this is where they meet: a
    reject supersedes the accept before it, and taking the reject back leaves the
    accept in force as the widget's answer once more. A withdrawal read only by the
    walk and not by the answer in force would leave the thread open with the log
    holding nothing that says so."""
    assert settlement(ASKED, PICKED, TURNED_DOWN) is None
    # The reject is the third event written, so `e3` is what the undo names.
    taken_back = {"kind": "undo", "undoes": "e3"}
    assert settlement(ASKED, PICKED, TURNED_DOWN, taken_back)["detail"] == {
        "outcome": "accept"
    }


def test_another_widget_s_answer_holds_a_thread_two_widgets_answered():
    """Superseding is per widget, because the decision is. Two suggestions can answer one
    question, and deciding against the second says nothing about the first — a fold
    keyed on the thread instead of the widget would have let it."""
    held = settlement(ASKED, {**PICKED, "widget": "sug-b"}, PICKED, TURNED_DOWN)
    assert held["widget"] == "sug-b"


def test_containment_reads_the_same_with_a_vocabulary_and_without_one(page_dir):
    """The two halves of a `spoken` reading come from different places. Words are
    the vocabulary's word — fences, x-says, chrome — but where an element sits is
    recorded off the tag stack before anything asks the registry what it shows.
    That is the whole of what liveness asks a page, and it is why the readings
    that may not raise on the registry gate need give nothing up.

    The words are the control: they must differ, or `spoken({})` would be the
    whole reading and the distinction this rests on would not exist. The diagram's
    data body is the element whose words the vocabulary changes."""
    document = structure_model.SourceDocument(FLOW_PAGE)
    registry = registry_storage.require_registry(page_dir)
    full = passages_model.SourceReading(document, registry).spoken
    assert passages_model.enclosing_ids(document) == passages_model.enclosing_of(full)
    bare = passages_model.SourceReading(document, {}).spoken
    assert any(full[wid].words != bare[wid].words for wid in full)


SUGGESTION_HOLDING_A_NAMESAKE = PAGE.replace(
    "</section>",
    '<lf-suggestion id="sug-a" resolves="c1"><lf-new><p id="c1">Poll every '
    "5 minutes.</p></lf-new></lf-suggestion>\n</section>",
)


def test_a_thread_answer_reads_the_same_wherever_it_is_folded(page_dir):
    """`resolves` names a thread, and thread ids and page ids are separate
    namespaces that can spell the same string. Read like any other detail value it
    would rest the accept on whichever element shared the name — here a paragraph
    the suggestion itself proposes — and the version that rewrote that paragraph
    would take back an answer it has nothing to do with.

    Every fold gets the same containment, so `page state` and the transcript,
    which hold the whole page, answer as the Stop hook and a wait's delivery do,
    which hold only where each id sits. A decision cannot stand at one and be
    missing at the other.

    Flooring the widget itself is the control: it retracts in every reading, so a
    green result cannot come from a floor that never reached this fold."""
    html = SUGGESTION_HOLDING_A_NAMESAKE
    document = structure_model.SourceDocument(html)
    append_carried_log_record(page_dir, dict(COMMENT))
    append_carried_log_record(page_dir, dict(ACCEPT))
    append_carried_log_record(
        page_dir,
        {
            "kind": "note",
            "author": "agent",
            "version": 2,
            "revision": 2,
            "text": "reworded the poll interval",
            "restated": ["c1"],
        },
    )
    spk = passages_model.SourceReading(
        document, registry_storage.require_registry(page_dir)
    ).spoken
    assert "sug-a" in spk["c1"].within  # the namesake really is inside the widget
    folds = [passages_model.enclosing_of(spk), passages_model.enclosing_ids(document)]
    events: list[dict] = events_model.read_events(page_dir)
    for within in folds:
        assert event_folds_model.build_threads(events, within)["c1"]["resolved"][
            "detail"
        ] == {"outcome": "accept"}

    append_carried_log_record(
        page_dir,
        {
            "kind": "note",
            "author": "agent",
            "version": 3,
            "revision": 3,
            "text": "rewrote the suggestion",
            "restated": ["sug-a"],
        },
    )
    events: list[dict] = events_model.read_events(page_dir)
    for within in folds:
        assert event_folds_model.build_threads(events, within)["c1"]["resolved"] is None


def test_independent_state_does_not_reopen_an_answer_even_after_retirement(
    server, page_dir
):
    registry = vocabulary(page_dir)
    registry["lf-suggestion"]["x-state"]["label"] = {
        "detail": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        "unit": "widget",
    }
    declare_vocabulary(page_dir, registry)
    snippet = '<lf-suggestion id="proposal" resolves="c1"><lf-new><p id="proposed">Ship after validation.</p></lf-new></lf-suggestion>'
    source = PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + snippet)
    (page_dir / "index.html").write_text(source)
    append_carried_log_record(page_dir, dict(COMMENT))
    publish(page_dir)
    from leaf.files import latest_revision

    revision = latest_revision(page_dir)

    def send(action, detail, attempt):
        command = {
            "kind": "action",
            "revision": revision,
            "widget": "proposal",
            "action": action,
            "detail": detail,
            "attempt": attempt,
        }
        status, body = fetch(f"{server}/api/event", data=json.dumps(command).encode())
        assert status == 200, body
        return json.loads(body)["state"]["events"][-1]

    accepted = send("decide", {"outcome": "accept"}, "accepted-proposal")
    labeled = send("label", {"text": "proposed"}, "labelled-proposal")
    assert accepted["meaning"]["answer"] == "c1"
    assert "answer" not in labeled["meaning"]
    assert labeled["meaning"]["depends"] == ["proposal"]
    # Literal text matching an id is not a dependency; ancestry remains live for
    # declared identities, tested in the named-dependency contrast below.
    assert revision is not None
    assert not event_folds_model.action_retracted(
        labeled, {"proposed": revision + 1}, {"proposed": ("proposal", "proposed")}
    )
    result = event_folds_model.build_threads(
        events_model.read_events(page_dir),
        passages_model.enclosing_ids(structure_model.SourceDocument(source)),
    )
    assert result["c1"]["resolved"]["id"] == accepted["id"]
    retired = source.replace(snippet, '<p id="proposed">Ship after validation.</p>')
    (page_dir / "index.html").write_text(retired)
    publish(page_dir)
    result = event_folds_model.build_threads(
        events_model.read_events(page_dir),
        passages_model.enclosing_ids(structure_model.SourceDocument(retired)),
    )
    assert result["c1"]["resolved"]["id"] == accepted["id"]
    # The immutable old command document still admits a different answer; a reject
    # declines the fix, so it answers the obligation and reopens the thread it was for.
    rejected = send("decide", {"outcome": "reject"}, "rejected-proposal")
    assert rejected["meaning"]["answer"] is None
    result = event_folds_model.build_threads(
        events_model.read_events(page_dir),
        passages_model.enclosing_ids(structure_model.SourceDocument(retired)),
    )
    assert result["c1"]["resolved"] is None


def test_an_independent_verb_leaves_a_decisions_thread_resolved(page_dir):
    """Each verb is its own coordinate, so another verb on the deciding widget stands
    beside the decision: neither the thread it closed nor its membership moves."""

    from leaf.projection import page_reading
    from leaf.thread_context import thread_memberships

    registry = registry_storage.require_registry(page_dir)
    registry = deepcopy(registry)
    registry["lf-suggestion"]["x-state"]["label"] = {
        "detail": {"type": "object"},
        "unit": "widget",
    }
    event = {
        "kind": "action",
        "id": "label1",
        "seq": 3,
        "author": "user",
        "revision": 1,
        "widget": "sug-a",
        "action": "label",
        "detail": {},
    }
    html = '<lf-suggestion id="sug-a" resolves="c1"><lf-new><p>Proposed</p></lf-new></lf-suggestion>'
    stated = ModelPage(html, registry=registry)
    events: list[dict] = [{**COMMENT, "seq": 1}]
    accepted = event_contracts_model.admitted_event(
        stated,
        events,
        {key: value for key, value in ACCEPT.items() if key != "meaning"},
    )
    events.append({**accepted, "id": "accept1", "seq": 2})
    events.append(event_contracts_model.admitted_event(stated, events, event))
    page = page_reading(
        passages_model.SourceReading(structure_model.SourceDocument(html), registry),
        events,
        1,
    )
    winner, _ = page.projection.actions[("sug-a", "sug-a", "decide")]
    assert winner["id"] == "accept1"
    threads = event_folds_model.build_threads(events, page.within)
    assert threads["c1"]["resolved"]["id"] == "accept1"
    memberships = thread_memberships(events, {"c1": "c1"}, {}, {})
    assert memberships["label1"] == []


def test_a_gesture_at_a_coordinate_reaches_only_the_answers_still_in_force_there():
    """A later action on a deciding widget changes the thread an earlier answer there
    closed, and its undo the same, until that answer is taken back or a version
    retracts what it rested on: after either, the thread it closed is no longer the
    later gesture's, as a revised suggestion that resolves another thread shows."""
    from leaf.thread_context import thread_memberships

    def decide(id, outcome, answer, revision=1, depends=("sug-a",)):
        return {
            "kind": "action",
            "id": id,
            "revision": revision,
            "widget": "sug-a",
            "action": "decide",
            "detail": {"outcome": outcome},
            "meaning": {"unit": "sug-a", "depends": list(depends), "answer": answer},
        }

    comments = [{"kind": "comment", "id": "c1"}, {"kind": "comment", "id": "c2"}]
    names = {"c1": "c1", "c2": "c2"}
    replaced = thread_memberships(
        [
            *comments,
            decide("accept", "accept", "c1"),
            decide("reject", "reject", None),
            {"kind": "undo", "id": "unreject", "undoes": "reject"},
        ],
        names,
        {},
        {},
    )
    assert (replaced["reject"], replaced["unreject"]) == (["c1"], ["c1"])
    taken_back = thread_memberships(
        [
            *comments,
            decide("accept", "accept", "c1"),
            {"kind": "undo", "id": "unaccept", "undoes": "accept"},
            decide("reject", "reject", None),
        ],
        names,
        {},
        {},
    )
    assert (taken_back["unaccept"], taken_back["reject"]) == (["c1"], [])
    restated = thread_memberships(
        [
            *comments,
            decide("accept", "accept", "c1"),
            {"kind": "note", "id": "v2", "revision": 2, "restated": ["sug-a"]},
            decide("again", "accept", "c2", revision=2),
        ],
        names,
        {},
        {},
    )
    assert (restated["v2"], restated["again"]) == (["c1"], ["c2"])
    late = thread_memberships(
        [
            *comments,
            {"kind": "note", "id": "v2", "revision": 2, "restated": ["sug-a"]},
            decide("stale", "accept", "c1"),
            decide("again", "accept", "c2", revision=2),
        ],
        names,
        {},
        {},
    )
    assert (late["stale"], late["again"]) == (["c1"], ["c2"])
    # A version retracting only the action that superseded an answer gives the
    # coordinate back to that answer, which closes its thread again.
    restored = thread_memberships(
        [
            *comments,
            decide("accept", "accept", "c1"),
            decide("reject", "reject", None, depends=("sug-a", "sug-note")),
            {"kind": "note", "id": "v2", "revision": 2, "restated": ["sug-note"]},
        ],
        names,
        {},
        {"sug-note": ["sug-a", "sug-note"]},
    )
    assert (restored["reject"], restored["v2"]) == (["c1"], ["c1"])
    # Taking back an answer another has since superseded moves no winner, so the
    # undo concerns only the thread its own gesture did.
    behind = thread_memberships(
        [
            *comments,
            decide("accept", "accept", "c1"),
            decide("again", "accept", "c2"),
            {"kind": "undo", "id": "unaccept", "undoes": "accept"},
        ],
        names,
        {},
        {},
    )
    assert behind["unaccept"] == ["c1"]


def test_every_change_to_a_threads_resolution_reaches_its_membership():
    """Membership names every thread whose resolution an event changes, as
    `build_threads` reads it before and after that event, over every three-step
    history of answers, non-answers, undos, and version notes at one coordinate."""
    from leaf.events import build_threads
    from leaf.thread_context import thread_memberships

    within = {"x": ("w", "x"), "y": ("w", "y")}
    comments = [
        {"kind": "comment", "id": thread, "author": "user", "ts": "t", "text": thread}
        for thread in ("c1", "c2")
    ]
    steps = [
        ("act", answer, depends)
        for answer in ("c1", "c2", None)
        for depends in ((), ("x",), ("y",))
    ] + [("undo",), ("note", "x"), ("note", "y")]

    def resolved(events):
        return {
            thread: folded["resolved"] and folded["resolved"]["id"]
            for thread, folded in build_threads(events, within).items()
        }

    for history in itertools.product(steps, repeat=3):
        events: list[dict] = list(comments)
        revision, in_force = 1, []
        for index, step in enumerate(history):
            if step[0] == "act":
                event = {
                    "kind": "action",
                    "id": f"a{index}",
                    "revision": revision,
                    "widget": "w",
                    "action": "decide",
                    "detail": {},
                    "meaning": {"unit": "w", "depends": [*step[2]], "answer": step[1]},
                }
                in_force.append(event["id"])
            elif step[0] == "undo":
                if not in_force:
                    break
                event = {"kind": "undo", "id": f"u{index}", "undoes": in_force.pop()}
            else:
                revision += 1
                event = {
                    "kind": "note",
                    "id": f"n{index}",
                    "revision": revision,
                    "restated": [step[1]],
                }
            assert event is not None
            events.append(event)
        memberships = thread_memberships(events, {"c1": "c1", "c2": "c2"}, {}, within)
        for at in range(len(comments), len(events)):
            before, after = resolved(events[:at]), resolved(events[: at + 1])
            changed = {thread for thread in after if before[thread] != after[thread]}
            assert changed <= set(memberships[events[at]["id"]]), (history, at)
