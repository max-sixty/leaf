"""One Question inventory, its canonical values, and its presentation context."""

import json
from copy import deepcopy
from pathlib import Path

import model_folds as model
import pytest
from interact_support import served_thread
from leaf import questions as questions_model
from leaf.gesture_words import element_name
from leaf.passages import SourceReading
from leaf.projection import page_reading
from leaf.served_state.browser import browser_state
from leaf.structure import SourceDocument
from leaf.work_reading import WorkReading

OPTIONS = '<lf-options id="choice" {attrs}><lf-option id="a">A</lf-option><lf-option id="b">B</lf-option></lf-options>'


def page(attrs="choose", context=None):
    content = OPTIONS.format(attrs=attrs)
    if context:
        content = f'<lf-ask id="{context}"><h2>Which route?</h2>{content}</lf-ask>'
    return model.leaf_page("Questions", content)


def questions(state, revision=1):
    return state["views"][str(revision)]["document"]["asks"]


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
    assert state["todos"] == []


def test_questions_name_their_exact_owning_message_without_conflating_thread_identity():
    document = page().replace(
        "</head>", '<meta name="lf-review" content="sign-off"></head>'
    )
    events = [
        {
            "kind": "note",
            "id": "stamp",
            "author": "agent",
            "version": 1,
            "text": "Ready",
        },
        {
            "kind": "comment",
            "id": "thread",
            "author": "agent",
            "text": "Choose the first route.",
            "markup": OPTIONS.format(attrs="choose").replace('id="', 'id="root-'),
        },
        {
            "kind": "reply",
            "id": "later",
            "author": "agent",
            "parent": "thread",
            "text": "Choose the later route too.",
            "markup": OPTIONS.format(attrs="choose").replace('id="', 'id="later-'),
        },
        {
            "kind": "comment",
            "id": "prompt",
            "author": "agent",
            "text": "Is this useful?",
        },
    ]
    state = model.reading(document, events)
    inventory = {
        question["id"]: (question["thread"], question["message"])
        for question in [*questions(state)["all"], *served_thread(state)["asks"]["all"]]
    }
    assert inventory == {
        "widget:choice": (None, None),
        "approval:v1": (None, None),
        "widget:root-choice": ("thread", "thread"),
        "widget:later-choice": ("thread", "later"),
        "reply:prompt": ("prompt", "prompt"),
    }


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


def test_a_pinned_view_reads_its_frozen_threads_under_its_own_registry():
    """A revision captured its thread widgets under its own registry, so a view
    pinned to it classifies their decisions there. A decision whose operation that
    registry defines otherwise is none in that view: the ask it answers stays open
    and the thread the user's, while the active view reads it answered and the
    thread waiting on the agent to pick it up."""

    def registry(attr):
        layer = deepcopy(model.model_layer())
        layer["lf-value-question"] = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "active": {"type": "boolean"},
                "value": {"type": "boolean"},
                "chosen": {"type": "boolean"},
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
                "set": {"unit": "widget", "record": {"kind": "value", "attr": attr}}
            },
        }
        return layer

    earlier, later = registry("value"), registry("chosen")
    document = model.leaf_page("Value", '<p id="p">Notes.</p>')
    events = model.served_reading(
        document,
        [
            {
                "kind": "comment",
                "author": "agent",
                "text": "Ship it?",
                "markup": '<lf-value-question id="typed" active></lf-value-question>',
            },
            {
                "kind": "action",
                "widget": "typed",
                "action": "set",
                "detail": {"value": True},
            },
        ],
        registry=later,
    )["events"]
    parsed = SourceDocument(document)
    state, _ = browser_state(
        {1: SourceReading(parsed, earlier), 2: SourceReading(parsed, later)},
        events,
        2,
        model.UNCLAIMED,
        {"revision": 2, "version": 2},
        {1, 2},
        model.NOW,
    )

    def read(revision):
        view = state["views"][str(revision)]
        [thread] = view["thread"]["threads"]
        [ask] = view["thread"]["asks"]["all"]
        return (
            [entry["event"]["id"] for entry in view["thread"]["projection"]["entries"]],
            (ask["id"], ask["status"]),
            thread["attention"],
            [item["id"] for item in view["queues"]["questions"]],
        )

    assert read(2) == (
        [events[1]["id"]],
        ("widget:typed", "answered"),
        {"kind": "waiting", "reason": "workflow", "workflow": events[1]["id"]},
        [],
    )
    assert read(1) == (
        [],
        ("widget:typed", "open"),
        {"kind": "needs_user", "reason": "ask", "workflow": None},
        ["widget:typed"],
    )


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
        question["source"]["kind"] for question in served_thread(state)["asks"]["all"]
    ] == ["reply"]


def conditional_registry():
    """A value write can originate a request between document revisions."""
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
    return registry


def test_conditional_request_retains_registration_between_value_actions():
    registry = conditional_registry()
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


@pytest.mark.parametrize("writer", ["action", "report"])
def test_historical_conditional_registration_reuses_work_and_tracks_event_changes(
    monkeypatch, writer
):
    """Retries keep completed history work, while changed facts get a fresh fold.

    The same admitted event identities can occur in a regenerated log with changed
    payloads. Withdrawals and stamped transitions also change historical readings;
    later comments and a new active document do not.
    """
    registry = conditional_registry()
    if writer == "report":
        registry["lf-conditional"]["x-state"]["phase"]["writer"] = "agent"
    document = model.leaf_page(
        "Conditional",
        '<lf-conditional id="conditional" phase="closed" ready></lf-conditional>',
    )
    readings = {
        revision: SourceReading(SourceDocument(document), registry)
        for revision in (1, 2)
    }
    events = [
        {
            "kind": writer,
            "author": "agent" if writer == "report" else "user",
            "widget": "conditional",
            "action": "phase",
            "detail": {"value": phase},
        }
        for phase in ("open", "closed")
    ]
    historical = []
    collecting = False
    native = questions_model.previously_requested

    def counted(*args, **kwargs):
        if collecting and args[3] == 1:
            historical.append(args[3])
        return native(*args, **kwargs)

    monkeypatch.setattr(questions_model, "previously_requested", counted)

    def read(commands):
        """Admit a fresh log, then fold it against the same immutable readings."""
        nonlocal collecting
        door = model.ModelPage(
            documents={
                revision: reading.document for revision, reading in readings.items()
            },
            registry=registry,
        )
        log = []
        for seq, command in enumerate(commands, 1):
            stamped = {"id": f"e{seq}", "seq": seq, "ts": model.NOW, "author": "user"}
            if command["kind"] != "undo":
                stamped["revision"] = 1
            log.append(model.admitted_event(door, log, {**stamped, **command}))
        active = max(readings)
        page = page_reading(
            readings[active],
            log,
            active,
            revisions=readings,
            revision_reader=readings.__getitem__,
        )
        collecting = True
        try:
            return WorkReading(
                log,
                registry,
                page,
                registry_for_revision=lambda revision: readings[revision].registry,
                available_revisions=readings,
            ).document.questions
        finally:
            collecting = False

    initial = read(events)
    assert [question["status"] for question in initial["all"]] == ["withdrawn"]
    assert len(historical) == 1
    assert read(events) == initial
    assert len(historical) == 1
    with_comment = [*events, {"kind": "comment", "text": "Keep investigating."}]
    assert read(with_comment) == initial
    readings[3] = SourceReading(SourceDocument(document), registry)
    assert read(with_comment) == initial
    assert len(historical) == 1

    changed = deepcopy(events)
    changed[0]["detail"]["value"] = "closed"
    assert read(changed)["all"] == []
    assert len(historical) == 2
    assert read(events) == initial
    assert len(historical) == 3

    if writer == "action":
        # Undo removes the gesture; a same-revision note preserves its registration.
        assert read([*events, {"kind": "undo", "undoes": "e1"}])["all"] == []
        assert len(historical) == 4
        assert (
            read(
                [
                    *events,
                    {
                        "kind": "note",
                        "author": "agent",
                        "version": 1,
                        "text": "Reconsidered.",
                        "restated": ["conditional"],
                    },
                ]
            )
            == initial
        )
        assert len(historical) == 5
    else:
        # A settled report still records that its prefix requested an answer.
        settled = [
            *events,
            {
                "kind": "note",
                "author": "agent",
                "version": 1,
                "text": "Absorbed.",
                "settles": [{"kind": "report", "id": "e1"}],
            },
        ]
        assert read(settled) == initial
        assert len(historical) == 4
        assert read(settled) == initial
        assert len(historical) == 4


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
        "kind": "todo_end",
        "id": "end",
        "author": "agent",
        "todo": "reply:prompt",
        "outcome": "dropped",
    }
    admitted = admitted_event(door, events, command)
    assert command["todo"] == admitted["todo"] == "reply:prompt"
    with pytest.raises(EventRefused, match="unknown to-do 'prompt'"):
        admitted_event(door, events, {**command, "todo": "prompt"})


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
            "kind": "todo",
            "author": "agent",
            "owner": "user",
            "title": "Check rollout numbers",
            "subject": {"kind": "widget", "id": "choice"},
        }
    )
    reading = model.reading(documents, events)
    revision = 1 if state == "answered" else 2
    assert questions(reading, revision)["all"][0]["status"] == state
    assert reading["todos"][0]["title"] == "Check rollout numbers"


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


def _element(content: list, id: str) -> dict | None:
    for node in content:
        if isinstance(node, str):
            continue
        if node["attrs"].get("id") == id:
            return node
        if found := _element(node["content"], id):
            return found
    return None


@pytest.mark.parametrize(
    "case",
    json.loads((Path(__file__).parents[1].joinpath("name_cases.json")).read_text()),
    ids=lambda case: case["id"],
)
def test_an_element_is_named_as_the_browser_names_it(case):
    """A Question's prompt is its element's name, read off the document by the rule
    the browser's `addressableName` reads off the live page."""
    document = SourceDocument(model.leaf_page("Names", case["markup"]))
    node = _element(document.content, "it")
    assert element_name(node, case.get("registry", {})) == case["name"]


EXHIBITS = json.loads(
    Path(__file__).parents[1].joinpath("exhibit_cases.json").read_text()
)


@pytest.mark.parametrize("case", EXHIBITS["cases"], ids=lambda case: case["id"])
def test_a_widget_is_quoted_where_the_browser_fences_it(case):
    """A widget strictly inside an x-exhibit is a mention, read off the holder chain by
    the rule the browser's `quoted` and its descriptors' `quoted` flag read off the
    page."""
    document = SourceDocument(model.leaf_page("Exhibits", case["markup"]))
    assert {
        rec["attrs"]["id"]: questions_model.quoted_in(rec, EXHIBITS["registry"])
        for rec in document.lf_elements
    } == case["quoted"]
