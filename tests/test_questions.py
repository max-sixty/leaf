"""One Question inventory, its canonical values, and its presentation context."""

from copy import deepcopy

import model_folds as model
import pytest
from leaf.passages import SourceReading
from leaf.served_state.browser import browser_state
from leaf.structure import SourceDocument

OPTIONS = '<lf-options id="choice" {attrs}><lf-option id="a">A</lf-option><lf-option id="b">B</lf-option></lf-options>'


def page(attrs="choose", context=None):
    content = OPTIONS.format(attrs=attrs)
    if context:
        content = f'<lf-ask id="{context}"><h2>Which route?</h2>{content}</lf-ask>'
    return model.leaf_page("Questions", content)


def questions(state, revision=1):
    return state["views"][str(revision)]["document"]["questions"]


def test_context_changes_prompt_target_without_changing_question_identity_or_value():
    state = model.reading(
        {1: page(), 2: page(context="evidence")},
        [
            {
                "kind": "action",
                "widget": "choice",
                "action": "choose",
                "detail": {"value": ["a"]},
            }
        ],
    )
    [question] = questions(state, 2)["all"]
    assert (question["id"], question["source"]["id"]) == ("widget:choice", "choice")
    assert question["prompt"] == {"text": "Which route?", "target": "evidence"}
    assert question["answer"]["value"] == ["a"]
    assert question["status"] == "answered"
    assert state["tasks"] == []


def test_partial_and_completed_empty_values_are_distinct_from_no_answer_and_undo_reopens():
    document = page("choose multiple")
    events = [
        {
            "kind": "action",
            "widget": "choice",
            "action": "choose",
            "detail": {"value": []},
        }
    ]
    [initial] = questions(model.reading(document))["all"]
    assert initial["answer"] is None
    [partial] = questions(model.reading(document, events))["all"]
    assert (partial["status"], partial["answer"]["value"]) == ("open", [])
    events.append(
        {"kind": "action", "widget": "choice", "action": "answer", "detail": {}}
    )
    [completed] = questions(model.reading(document, events))["all"]
    assert (completed["status"], completed["answer"]["value"]) == ("answered", [])
    assert completed["answer"]["event"]["id"] == "e2"
    events.append({"kind": "undo", "undoes": "e2"})
    [reopened] = questions(model.reading(document, events))["all"]
    assert (reopened["status"], reopened["answer"]["value"]) == ("open", [])


def test_unrequested_widget_is_absent_but_removed_predicate_withdraws_existing_request():
    assert questions(model.reading(page("")))["all"] == []
    [withdrawn] = questions(model.reading({1: page(), 2: page("")}), 2)["all"]
    assert (withdrawn["status"], withdrawn["answer"], withdrawn["next_actor"]) == (
        "withdrawn",
        None,
        None,
    )
    assert questions(model.reading({1: page(), 2: page("restated")}), 2)["all"] == []


def test_pinned_document_uses_unrequested_intermediate_history_for_registration():
    registry = model.model_layer()
    readings = {
        index: SourceReading(
            SourceDocument(page("choose" if index == 2 else "")), registry
        )
        for index in range(1, 5)
    }
    state, _ = browser_state(
        {3: readings[3], 4: readings[4]},
        [],
        4,
        model.UNCLAIMED,
        {"revision": 4, "version": 4},
        {3, 4},
        model.NOW,
        revisions=readings.__getitem__,
        revision_ids=set(readings),
    )
    for revision in (3, 4):
        [question] = questions(state, revision)["all"]
        assert (question["id"], question["status"]) == ("widget:choice", "withdrawn")


@pytest.mark.parametrize("value", [False, 0])
def test_false_and_zero_are_typed_answers(value):
    registry = deepcopy(model.model_layer())
    registry["lf-value-question"] = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "active": {"type": "boolean"},
            "value": {"type": ["boolean", "integer"]},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "none",
        "x-awaits": {
            "when": {"active": [True]},
            "value": "set",
            "answered": {"set": {}},
        },
        "x-state": {
            "set": {"unit": "widget", "record": {"kind": "value", "attr": "value"}}
        },
    }
    document = model.leaf_page(
        "Value", '<lf-value-question id="typed" active></lf-value-question>'
    )
    [question] = questions(
        model.reading(
            document,
            [
                {
                    "kind": "action",
                    "widget": "typed",
                    "action": "set",
                    "detail": {"value": value},
                }
            ],
            registry=registry,
        )
    )["all"]
    assert question["status"] == "answered"
    assert question["answer"]["value"] is value


def test_changed_partial_value_does_not_reuse_an_earlier_completion_event():
    events = [
        {
            "kind": "action",
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["a"]},
        },
        {"kind": "action", "widget": "choice", "action": "answer", "detail": {}},
        {
            "kind": "action",
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["b"]},
        },
    ]
    state = model.reading(page("choose multiple"), events)
    [question] = questions(state)["all"]
    assert question["answer"] == {"value": ["b"], "event": None}


def test_display_only_widget_does_not_suppress_a_prose_question():
    state = model.reading(
        page(),
        [
            {
                "kind": "comment",
                "author": "agent",
                "text": "Is this useful?",
                "markup": OPTIONS.format(attrs=""),
                "anchor": {"section": "choice"},
            },
        ],
    )
    assert [
        question["source"]["kind"] for question in state["thread"]["questions"]["all"]
    ] == ["reply"]


def test_conditional_request_retains_registration_between_value_actions():
    registry = deepcopy(model.model_layer())
    registry["lf-conditional"] = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "phase": {"enum": ["closed", "open"]},
            "ready": {"type": "boolean"},
        },
        "required": ["id", "phase"],
        "additionalProperties": False,
        "x-content": "none",
        "x-state": {
            "phase": {"unit": "widget", "record": {"kind": "value", "attr": "phase"}},
            "answer": {
                "unit": "widget",
                "detail": {"type": "object", "additionalProperties": False},
            },
        },
        "x-awaits": {
            "when": {"phase": ["open"], "ready": [True]},
            "value": "answer",
            "answered": {"answer": {}},
        },
    }
    document = model.leaf_page(
        "Conditional",
        '<lf-conditional id="conditional" phase="closed" ready></lf-conditional>',
    )
    events = [
        {
            "kind": "action",
            "widget": "conditional",
            "action": "phase",
            "detail": {"value": phase},
        }
        for phase in ("open", "closed")
    ]
    assert questions(model.reading(document, registry=registry))["all"] == []
    [opened] = questions(model.reading(document, events[:1], registry=registry))["user"]
    assert opened["status"] == "open"
    closed = questions(model.reading(document, events, registry=registry))
    [withdrawn] = closed["all"]
    assert (withdrawn["status"], withdrawn["answer"], closed["user"]) == (
        "withdrawn",
        None,
        [],
    )
    not_ready = document.replace(" ready", "")
    assert (
        questions(
            model.reading({1: not_ready, 2: document}, events, registry=registry), 2
        )["all"]
        == []
    )
    [historical] = questions(
        model.reading({1: document, 2: not_ready}, events, registry=registry), 2
    )["all"]
    assert historical["status"] == "withdrawn"
    report_registry = deepcopy(registry)
    report_registry["lf-conditional"]["x-state"]["phase"]["writer"] = "agent"
    reports = [{**event, "kind": "report", "author": "agent"} for event in events]
    [reported] = questions(model.reading(document, reports, registry=report_registry))[
        "all"
    ]
    assert reported["status"] == "withdrawn"
    completed = model.reading(
        document,
        [
            events[0],
            {
                "kind": "action",
                "widget": "conditional",
                "action": "answer",
                "detail": {},
            },
        ],
        registry=registry,
    )
    assert questions(completed)["all"][0]["status"] == "answered"
    assert any(workflow["answer"] is not None for workflow in completed["workflows"])
    events.append({"kind": "undo", "undoes": "e1"})
    assert questions(model.reading(document, events, registry=registry))["all"] == []


def test_settled_request_repicks_keep_the_new_user_gesture_as_provenance():
    state = model.reading(
        {1: page(), 2: page("choose settled")},
        [
            {
                "kind": "action",
                "widget": "choice",
                "action": "choose",
                "detail": {"value": ["a"]},
            },
            {
                "kind": "action",
                "widget": "choice",
                "action": "choose",
                "detail": {"value": ["b"]},
                "revision": 2,
            },
        ],
    )
    [question] = questions(state, 2)["all"]
    assert question["status"] == "answered"
    assert question["answer"]["value"] == ["b"]
    assert question["answer"]["event"]["id"] == "e2"


def test_task_validation_does_not_rewrite_question_identity_and_refuses_bare_source():
    from interact_support import ModelPage
    from leaf.event_contracts import EventRefused, admitted_event

    document = page()
    door = ModelPage(
        documents={1: SourceDocument(document)}, registry=model.model_layer()
    )
    events = [
        admitted_event(
            door,
            [],
            {
                "kind": "comment",
                "id": "prompt",
                "seq": 1,
                "ts": model.NOW,
                "author": "agent",
                "revision": 1,
                "text": "Which path?",
            },
        )
    ]
    command = {
        "kind": "task_end",
        "id": "end",
        "author": "agent",
        "task": "reply:prompt",
        "outcome": "dropped",
    }
    admitted = admitted_event(door, events, command)
    assert command["task"] == admitted["task"] == "reply:prompt"
    with pytest.raises(EventRefused, match="unknown task 'prompt'"):
        admitted_event(door, events, {**command, "task": "prompt"})


@pytest.mark.parametrize("state", ["answered", "withdrawn"])
def test_user_work_can_stand_on_a_source_after_its_question_ends(state):
    documents = page() if state == "answered" else {1: page(), 2: page("")}
    events = (
        [
            {
                "kind": "action",
                "widget": "choice",
                "action": "choose",
                "detail": {"value": ["a"]},
            }
        ]
        if state == "answered"
        else []
    )
    events.append(
        {
            "kind": "task",
            "author": "agent",
            "owner": "user",
            "title": "Check rollout numbers",
            "subject": {"kind": "widget", "id": "choice"},
        }
    )
    reading = model.reading(documents, events)
    revision = 1 if state == "answered" else 2
    assert questions(reading, revision)["all"][0]["status"] == state
    assert reading["tasks"][0]["title"] == "Check rollout numbers"


def test_repicking_a_withdrawn_request_records_provenance_without_reclosing_thread():
    registry = deepcopy(model.model_layer())
    registry["lf-options"]["properties"]["resolves"] = {"type": "string"}
    documents = {
        1: page('choose resolves="thread"'),
        2: page('choose settled resolves="thread"'),
    }
    events = [
        {"kind": "comment", "id": "thread", "text": "Which choice resolves this?"},
        {
            "kind": "action",
            "widget": "choice",
            "action": "choose",
            "detail": {"value": ["a"]},
        },
    ]
    closed = model.reading(documents, events, registry=registry)
    assert model.threads(closed)["thread"]["resolved"]
    events.extend(
        [
            {"kind": "unresolve", "parent": "thread"},
            {
                "kind": "action",
                "widget": "choice",
                "action": "choose",
                "detail": {"value": ["b"]},
                "revision": 2,
            },
        ]
    )
    reading = model.reading(documents, events, registry=registry)
    assert not model.threads(reading)["thread"]["resolved"]
    answer = questions(reading, 2)["all"][0]["answer"]
    assert answer["value"] == ["b"]
    assert answer["event"]["id"] == "e4"
