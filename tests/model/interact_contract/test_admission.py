"""What the event door admits: picks and moves on stated pages, created children and
ids, undos, reactions, authorship and recorded dependencies."""

import json
import threading
from copy import deepcopy

import model_folds as model
import pytest
from interact_support import (
    PAGE,
    STATED_TIMEOUT,
    ModelPage,
    append_carried_log_record,
    comment,
    element_declaration,
    fetch,
    lock_contention,
    model_layer,
    publish,
    published,
    queue_board_registry,
    refused_on,
    wait_for,
)

from leaf import event_contracts as event_contracts_model
from leaf import event_log as events_model
from leaf import events as event_folds_model
from leaf import passages as passages_model
from leaf import schema as schema_model
from leaf import structure as structure_model
from leaf import thread as thread_model
from leaf.findings import Finding
from leaf.projection import page_reading, retirement_outcomes
from leaf.registry import contract as registry_contract
from leaf.registry.layer import stamp_composition
from leaf.registry.validation import validate_registry
from leaf.validation.instances import widget_errors

# One question quoted back and the same question live. The pair is what makes the
# exhibit refusal below the exhibit's doing: the two groups are the same markup
# under different holders.
STATED_KIT = """<!doctype html>
<html lang="en">
<head>
<title>Kit</title>
</head>
<body>
<main>
<lf-sample id="last-year" label="the kit we took last year">
  <lf-options id="quoted-pick" choose>
    <lf-option id="quoted-paper"><strong>Paper maps</strong> Nothing to charge.</lf-option>
    <lf-option id="quoted-gps"><strong>Dedicated GPS</strong> Offline maps.</lf-option>
  </lf-options>
</lf-sample>
<lf-ask id="kit-decision">
  <h2>Which navigation kit this year?</h2>
  <lf-options id="live-pick" choose>
    <lf-option id="live-paper"><strong>Paper maps</strong> Nothing to charge.</lf-option>
    <lf-option id="live-gps"><strong>Dedicated GPS</strong> Offline maps.</lf-option>
  </lf-options>
</lf-ask>
</main>
</body>
</html>
"""


STATED_LOG = [
    {
        "kind": "comment",
        "id": "c1",
        "seq": 1,
        "ts": "2026-09-19T12:00:00+00:00",
        "author": "user",
        "revision": 1,
        "text": "Which one did we take?",
    }
]


STATED_PICK = {"kind": "action", "author": "user", "revision": 1, "action": "choose"}


@pytest.mark.parametrize("unit", ["row", "widget"])
def test_an_outcome_field_does_not_make_a_domain_action_a_decision(unit):
    registry = deepcopy(model_layer())
    entry = element_declaration("lf-review", upgrade=True)
    entry["properties"]["restated"] = {"type": "boolean"}
    entry["x-state"] = {
        "review": {
            "unit": unit,
            "detail": {
                "type": "object",
                "properties": {
                    "row": {"type": "string"},
                    "outcome": {"enum": ["pass", "fail"]},
                },
                "required": ["row", "outcome"],
                "additionalProperties": False,
            },
        }
    }
    registry["lf-review"] = entry
    validate_registry(registry, "review package")
    stamp_composition(registry)
    assert "lf-review" not in registry["$decisions"]
    page = ModelPage('<lf-review id="review"></lf-review>', registry=registry)
    action = event_contracts_model.admitted_event(
        page,
        [],
        {
            **STATED_PICK,
            "id": "e1",
            "seq": 1,
            "widget": "review",
            "action": "review",
            "detail": {"row": "test-row", "outcome": "pass"},
        },
    )
    reading = page_reading(page.reading(1, registry), [action], 1)
    assert list(reading.projection.actions) == [
        ("review", "test-row" if unit == "row" else "review", "review")
    ]
    assert retirement_outcomes(reading.projection.actions) == {}
    assert action["meaning"]["state"]["decides"] is False

    # Reusing the verb as a whole-widget decision does not reinterpret that answer.
    entry["x-state"]["review"] |= {"unit": "widget", "decides": True}
    validate_registry(registry, "revised review package")
    assert page_reading(page.reading(1, registry), [action], 1).projection.actions == {}


def test_an_ordinary_outcome_answers_its_condition_without_withdrawing_a_proposal():
    registry = deepcopy(model_layer())
    entry = registry["lf-suggestion"]
    entry["x-state"]["review"] = {
        key: value
        for key, value in entry["x-state"]["decide"].items()
        if key != "decides"
    }
    entry["x-awaits"]["answered"]["review"] = {"detail": {"outcome": "reject"}}
    validate_registry(registry, "review package")
    stamp_composition(registry)
    source = (
        '<lf-suggestion id="proposal" resolves="e1">'
        '<lf-new><p id="new">Proposed work.</p></lf-new></lf-suggestion>'
    )
    commands = [{"kind": "comment", "text": "Review it."}]
    for outcome, answers in (("accept", False), ("reject", True)):
        commands.append(
            {
                **STATED_PICK,
                "widget": "proposal",
                "action": "review",
                "detail": {"outcome": outcome},
            }
        )
        state = model.served_reading(source, commands, registry=registry)
        meaning = state["events"][-1]["meaning"]
        assert ("answer" in meaning) is answers
        if answers:
            assert meaning["answer"] == "e1"


@pytest.fixture
def instance_input_registry():
    """A generic custom payload with instance-selected, self-contained schemas."""
    registry = deepcopy(model_layer())
    entry = element_declaration("lf-input-box", upgrade=True)
    entry["properties"]["restated"] = {"type": "boolean"}
    entry["properties"]["shape"] = {
        "type": "string",
        "pattern": f"^{schema_model.DATA_CONTRACT_NAME}$",
    }
    entry["x-state"] = {
        "submit": {
            "unit": "widget",
            "contract": {"field": "payload", "attribute": "shape"},
            "detail": {
                "type": "object",
                "properties": {"payload": {"type": "object"}},
                "required": ["payload"],
                "additionalProperties": False,
            },
        }
    }
    registry["lf-input-box"] = entry
    for name, maximum in (("small", 2), ("large", 9)):
        registry["$data"]["contracts"][name] = {
            "description": f"A count no larger than {maximum}.",
            "schema": {
                "$defs": {"count": {"type": "integer", "maximum": maximum}},
                "type": "object",
                "properties": {"count": {"$ref": "#/$defs/count"}},
                "required": ["count"],
                "additionalProperties": False,
            },
        }
    validate_registry(registry, "input package")
    stamp_composition(registry)
    return registry


def test_instance_contracts_validate_complete_values_at_admission(
    instance_input_registry,
):
    registry = instance_input_registry
    page = ModelPage(
        '<lf-input-box id="small" shape="small"></lf-input-box>'
        '<lf-input-box id="large" shape="large"></lf-input-box>'
        '<lf-input-box id="open"></lf-input-box>',
        registry=registry,
    )

    def submit(widget, payload):
        return event_contracts_model.admitted_event(
            page,
            [],
            {
                **STATED_PICK,
                "widget": widget,
                "action": "submit",
                "detail": {"payload": payload},
            },
        )

    assert submit("small", {"count": 2})["detail"] == {"payload": {"count": 2}}
    assert submit("large", {"count": 7})["detail"] == {"payload": {"count": 7}}
    assert submit("open", {"unconstrained": True})["detail"]["payload"]["unconstrained"]
    for payload, field in (
        ({"count": 7}, "/payload/count"),
        ({"count": "two"}, "/payload/count"),
        ({}, "/payload"),
        ({"count": 2, "extra": True}, "/payload"),
    ):
        with pytest.raises(events_model.EventRefused) as refused:
            submit("small", payload)
        finding = refused_on(refused.value)
        assert (finding.code, finding.values["field"]) == ("invalid-detail", field)

    unknown = structure_model.SourceDocument(
        '<lf-input-box id="unknown" shape="missing"></lf-input-box>'
    )
    [finding] = widget_errors(unknown.lf_elements, registry)
    assert finding.code == "instance-contract"
    assert finding.values["contract"] == "missing"


def test_instance_contracts_read_the_sending_revision_and_recheck_changed_domains(
    instance_input_registry,
):
    registry = instance_input_registry
    large = '<lf-input-box id="input" shape="large"></lf-input-box>'
    small = large.replace('shape="large"', 'shape="small"')
    page = ModelPage(large, small, large, registry=registry)
    action = event_contracts_model.admitted_event(
        page,
        [],
        {
            **STATED_PICK,
            "id": "e1",
            "seq": 1,
            "widget": "input",
            "action": "submit",
            "detail": {"payload": {"count": 7}},
        },
    )
    for revision, remains in ((1, True), (2, False), (3, True)):
        reading = page_reading(page.reading(revision, registry), [action], revision)
        assert bool(reading.projection.actions) is remains
    command = {
        key: value
        for key, value in action.items()
        if key not in {"meaning", "attention"}
    }
    with pytest.raises(events_model.EventRefused) as refused:
        event_contracts_model.admitted_event(page, [], {**command, "revision": 2})
    assert refused_on(refused.value).code == "invalid-detail"


def test_two_playgrounds_on_one_page_validate_their_own_values(instance_input_registry):
    registry = deepcopy(model_layer("playground"))
    registry["$data"]["contracts"].update(instance_input_registry["$data"]["contracts"])
    page = ModelPage(
        '<lf-playground id="small" contract="small"></lf-playground>'
        '<lf-playground id="large" contract="large"></lf-playground>',
        registry=registry,
    )
    log = []
    for seq, (widget, count) in enumerate((("small", 2), ("large", 7)), 1):
        log.append(
            event_contracts_model.admitted_event(
                page,
                log,
                {
                    **STATED_PICK,
                    "id": f"e{seq}",
                    "seq": seq,
                    "widget": widget,
                    "detail": {
                        "values": {"count": count},
                        "instruction": "Use this count.",
                    },
                },
            )
        )
    with pytest.raises(events_model.EventRefused) as refused:
        event_contracts_model.admitted_event(
            page,
            log,
            {
                **STATED_PICK,
                "widget": "small",
                "detail": log[-1]["detail"],
            },
        )
    assert refused_on(refused.value).code == "invalid-detail"
    assert [(e["widget"], e["detail"]["values"]) for e in log] == [
        ("small", {"count": 2}),
        ("large", {"count": 7}),
    ]


def test_instance_contracts_follow_the_widget_in_frozen_thread_markup(
    instance_input_registry,
):
    commands = [
        {"kind": "comment", "text": "Choose a count."},
        {
            "kind": "reply",
            "author": "agent",
            "parent": "e1",
            "text": "Choose here:",
            "markup": '<lf-input-box id="thread-input" shape="large"></lf-input-box>',
        },
        {
            "kind": "action",
            "widget": "thread-input",
            "action": "submit",
            "detail": {"payload": {"count": 7}},
        },
    ]
    state = model.served_reading(
        "<p>Page</p>", commands, registry=instance_input_registry
    )
    action = state["events"][-1]
    assert action["meaning"]["scope"] == "thread"
    assert action["detail"] == {"payload": {"count": 7}}
    commands[-1]["detail"]["payload"]["count"] = 10
    with pytest.raises(events_model.EventRefused) as refused:
        model.served_reading("<p>Page</p>", commands, registry=instance_input_registry)
    assert refused_on(refused.value).code == "invalid-detail"


# A queue with two cards: only the final move answers its obligation.
STATED_QUEUE = """<!doctype html>
<html lang="en">
<head>
<title>Triage</title>
</head>
<body>
<main>
<lf-ask id="triage-decision">
  <h2>Which follow-ups should we keep?</h2>
  <lf-board id="triage">
    <lf-column id="queue" label="Queued">
      <lf-card id="card-a"><strong>Rolling expiry</strong></lf-card>
      <lf-card id="card-b"><strong>Bounded fallback</strong></lf-card>
    </lf-column>
    <lf-column id="keep" label="Kept"></lf-column>
  </lf-board>
</lf-ask>
</main>
</body>
</html>
"""


STATED_MOVE = {
    "kind": "action",
    "author": "user",
    "revision": 1,
    "widget": "triage",
    "action": "move",
}


def test_a_pick_names_only_options_its_group_holds():
    """A `choose` names authored options or ones an `add` in force created.

    The user's own option travels as two sends, the `add` and then the pick of it.
    Were the `add` refused, the pick behind it would otherwise answer the obligation with an
    option nobody can see.
    """
    page = ModelPage(STATED_KIT)
    pick = {**STATED_PICK, "widget": "live-pick", "detail": {"value": ["live-mine"]}}

    def admit(log, event):
        return event_contracts_model.admitted_event(page, log, dict(event))

    with pytest.raises(events_model.EventRefused) as refused:
        admit(STATED_LOG, pick)
    strangers = refused_on(refused.value)
    assert (strangers.code, strangers.values["strangers"]) == (
        "unknown-members",
        ["live-mine"],
    )

    add = admit(
        STATED_LOG,
        {
            **STATED_PICK,
            "widget": "live-pick",
            "action": "add",
            "detail": {"option": "live-mine", "text": "My own way"},
        },
    )
    assert add["meaning"]["unit"] == "live-mine"
    added = {**add, "id": "a1", "ts": "2026-09-19T12:01:00+00:00", "seq": 2}
    assert admit([*STATED_LOG, added], pick)["detail"] == {"value": ["live-mine"]}


@pytest.mark.parametrize(
    "option_title",
    [
        "<strong>Fast path</strong>",
        '<hgroup><p class="eyebrow">Quick delivery</p><h2>Fast path</h2></hgroup>',
        '<header><hgroup><p class="eyebrow">Quick delivery</p><h2>Fast path</h2></hgroup></header>',
    ],
    ids=["strong", "hgroup", "header-hgroup"],
)
def test_history_reaches_only_a_page_that_renders_it_and_keeps_a_pick_as_made(
    option_title,
):
    """The served history words a pick from the document it was made in.

    A later version that removes the question leaves the row naming the option the
    user picked, by its title rather than its eyebrow or description, and a withdrawn
    pick stays a row marked undone. A page whose markup holds no widget declaring
    `x-history` is not served the reading.
    """
    question = model.leaf_page(
        "Route",
        f"""<h1>Route</h1>
<lf-options id="route" choose>
  <lf-option id="fast">{option_title} ships on Friday.</lf-option>
  <lf-option id="slow">Slow path</lf-option>
</lf-options>
<lf-activity id="feed"></lf-activity>""",
    )
    retired = model.leaf_page(
        "Route", '<h1>Route</h1><lf-activity id="feed"></lf-activity>'
    )
    pick = {"kind": "action", "widget": "route", "action": "choose"}
    events = (
        {**pick, "detail": {"value": ["fast"]}},
        {**pick, "detail": {"value": ["slow"]}},
        {"kind": "undo", "undoes": "e2"},
    )

    history = model.reading({1: question, 2: retired}, events)["history"]
    assert [(row["id"], row["gesture"], row["undone"]) for row in history] == [
        ("e2", {"form": "choice", "chosen": ["Slow path"]}, True),
        ("e1", {"form": "choice", "chosen": ["Fast path"]}, False),
    ]

    unwatched = question.replace('<lf-activity id="feed"></lf-activity>', "")
    assert "history" not in model.reading(unwatched, events)


def test_history_words_a_pick_of_an_added_option_by_what_the_user_wrote():
    """An added option is in no document, so its words come from the `add` that
    wrote it, as its inline Markdown shows them. The pick of it reads by those
    words even after the add is undone, since that is what the user picked, and an
    id an undone add freed and a later add reused reads each gesture by the add
    in force when that gesture was made."""
    question = model.leaf_page(
        "Route",
        """<h1>Route</h1>
<lf-options id="route" choose>
  <lf-option id="fast"><strong>Fast path</strong> ships on Friday.</lf-option>
</lf-options>
<lf-activity id="feed"></lf-activity>""",
    )

    def add(text):
        return {
            "kind": "action",
            "widget": "route",
            "action": "add",
            "detail": {"option": "route-mine", "text": text},
        }

    pick = {
        "kind": "action",
        "widget": "route",
        "action": "choose",
        "detail": {"value": ["route-mine"]},
    }
    events = (
        add("**Ship** half"),
        pick,
        {"kind": "undo", "undoes": "e2"},
        {"kind": "undo", "undoes": "e1"},
        add("Ship everything"),
        pick,
    )

    history = model.reading(question, events)["history"]
    assert [(row["id"], row["gesture"]) for row in history] == [
        ("e6", {"form": "choice", "chosen": ["Ship everything"]}),
        ("e5", {"form": "add", "words": "Ship everything"}),
        ("e2", {"form": "choice", "chosen": ["Ship half"]}),
        ("e1", {"form": "add", "words": "Ship half"}),
    ]


def test_the_move_that_empties_the_queue_answers_its_obligation():
    """Only moving the final real card answers the whole queue's obligation.

    A crafted unknown unit must never count as completing the queue.
    """
    page = ModelPage(STATED_QUEUE, registry=queue_board_registry(model_layer()))

    def admit(log, event):
        return event_contracts_model.admitted_event(page, log, dict(event))

    first = admit(
        [],
        {**STATED_MOVE, "detail": {"unit": "card-a", "value": "keep", "rank": "0i"}},
    )
    assert first["meaning"]["unit"] == "card-a"
    assert "answer" not in first["meaning"]
    log = [{**first, "id": "s1", "ts": "2026-09-19T12:01:00+00:00", "seq": 1}]
    last = admit(
        log,
        {**STATED_MOVE, "detail": {"unit": "card-b", "value": "keep", "rank": "0r"}},
    )
    assert last["meaning"]["answer"] is None

    with pytest.raises(events_model.EventRefused) as refused:
        admit(
            log,
            {
                **STATED_MOVE,
                "detail": {"unit": "not-a-card", "value": "keep", "rank": "0r"},
            },
        )
    unknown = refused_on(refused.value)
    assert (unknown.code, unknown.values["unit"]) == ("unknown-unit", "not-a-card")


def test_admission_decides_from_the_markup_and_the_current_log_alone():
    """The door reads a page through `PageView` and reaches past it for nothing.

    What makes an event admissible is the authored document it names, the
    vocabulary that document captured, and the current log in front of it. So a
    page whose revisions are stated rather than stored reaches the same verdicts,
    and a test of one rule can be the markup that rule is about — which is what
    `ModelPage` is. Each verdict below comes from a different gate, so a gate
    that went back to opening a file of its own fails here.
    """
    captured = deepcopy(model_layer())
    # Ownership belongs to the running transport, not the captured vocabulary.
    del captured["$events"]["ownership"]
    page = ModelPage(STATED_KIT, registry=captured)

    def admit(event):
        return event_contracts_model.admitted_event(page, STATED_LOG, dict(event))

    def refusal(event):
        with pytest.raises(events_model.EventRefused) as refused:
            admit(event)
        return refused_on(refused.value)

    choose_live = {
        **STATED_PICK,
        "widget": "live-pick",
        "detail": {"value": ["live-gps"]},
    }
    assert admit(choose_live)["meaning"]["unit"] == "live-pick"
    assert refusal({**choose_live, "revision": 2}).values["revisions"] == [1]
    quoted = {
        **STATED_PICK,
        "widget": "quoted-pick",
        "detail": {"value": ["quoted-gps"]},
    }
    assert refusal(quoted).code == "quoted-widget"
    answer = {"kind": "reply", "author": "agent", "revision": 1, "text": "The GPS."}
    assert refusal({**answer, "parent": "c9"}) == Finding(
        "unknown-parent", values={"kind": "reply", "parent": "c9"}
    )
    assert admit({**answer, "parent": "c1"})["parent"] == "c1"


def test_a_created_child_is_its_actions_unit_and_its_words_stay_payload():
    # Words that happen to spell an element id never become a dependency; the
    # created id does once the markup holds it inside the sender.
    event = {
        "widget": "group",
        "detail": {"option": "user-child", "text": "authored-child"},
        "meaning": {"depends": ["group", "user-child"]},
    }
    spec = {"unit": "option", "creates": {"child": "lf-option", "words": "text"}}

    assert registry_contract.created_child(event, spec) == (
        "user-child",
        "authored-child",
    )
    assert registry_contract.created_child(event, {"unit": "option"}) is None
    assert event_folds_model.action_rests_on(event, {"authored-child": ("group",)}) == [
        "group"
    ]
    assert event_folds_model.action_rests_on(
        event, {"authored-child": ("group",), "user-child": ("group",)}
    ) == ["group", "user-child"]


def test_server_takes_back_only_a_gesture_in_force_of_the_users_own(server, page_dir):
    """`undoes` is checked completely where it enters, so nothing downstream asks a
    second time whether it points at something real. What an undo may name is one
    unwithdrawn gesture of the user's own: an agent's `leaf thread resolve` is not
    theirs to take back, a comment is speech rather than state, an undo is not
    itself undoable (that would be a redo), and one gesture cannot be taken back
    twice."""
    publish(page_dir)
    posted = json.loads(
        fetch(
            f"{server}/api/event",
            data=json.dumps({"kind": "comment", "revision": 1, "text": "hi"}).encode(),
        )[1]
    )["state"]["events"][-1]
    resolved = json.loads(
        fetch(
            f"{server}/api/event",
            data=json.dumps({"kind": "resolve", "parent": posted["id"]}).encode(),
        )[1]
    )["state"]["events"][-1]
    agent_closed = append_carried_log_record(
        page_dir, {"kind": "resolve", "author": "agent", "parent": posted["id"]}
    )

    for bad, says in [
        ({"kind": "undo", "undoes": "nope"}, "unknown"),
        # The user's own gestures only, and only the kinds that carry state.
        (
            {"kind": "undo", "undoes": agent_closed["id"]},
            "not the user's own gesture",
        ),
        ({"kind": "undo", "undoes": posted["id"]}, "is not a reaction"),
        # The one field it carries, and the door refuses it in any other shape.
        ({"kind": "undo"}, "'undoes' is a required property"),
        (
            {"kind": "undo", "undoes": resolved["id"], "widget": "x"},
            "widget",
        ),
    ]:
        status, body = fetch(f"{server}/api/event", data=json.dumps(bad).encode())
        assert status == 400, bad
        answer = json.loads(body)
        assert answer["ok"] is False and answer["final"] is True, bad
        assert says in answer["error"], body

    undone = {"kind": "undo", "undoes": resolved["id"]}
    status, body = fetch(f"{server}/api/event", data=json.dumps(undone).encode())
    assert status == 200, body
    took_back = json.loads(body)["state"]["events"][-1]

    # Once, and never the undo itself: repeated presses walk back through the
    # user's history rather than toggling the last gesture on and off.
    status, body = fetch(f"{server}/api/event", data=json.dumps(undone).encode())
    refusal = json.loads(body)
    assert status == 400 and refused_on(refusal).code == "withdrawn-gesture"
    assert took_back in refusal["state"]["events"]
    assert refusal["state"]["browser"]["basis"]["through_seq"] >= took_back["seq"]
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "undo", "undoes": took_back["id"]}).encode(),
    )
    unundoable = refused_on(body)
    assert status == 400 and (unundoable.code, unundoable.values["target"]) == (
        "unundoable",
        "undo",
    )


def test_two_concurrent_undos_cannot_both_take_back_one_gesture(
    server, page_dir, monkeypatch
):
    """Mutable validation and append are one log transaction. Two request threads
    may arrive together, but the second must read the first withdrawal before it can
    validate its own; otherwise both can truthfully validate against a state neither
    is allowed to append beside the other."""
    publish(page_dir)
    comment = json.loads(
        fetch(
            f"{server}/api/event",
            data=json.dumps(
                {"kind": "comment", "revision": 1, "text": "close this"}
            ).encode(),
        )[1]
    )["state"]["events"][-1]
    target = json.loads(
        fetch(
            f"{server}/api/event",
            data=json.dumps({"kind": "resolve", "parent": comment["id"]}).encode(),
        )[1]
    )["state"]["events"][-1]

    # The old handler validated outside the append transaction. Hold its first
    # validation until the second request states where it is: on that shape both
    # requests read the same current target, so the second validates too, while
    # the transactional handler keeps the second waiting on the log the first holds
    # until the first append is visible.
    real_undo_error = event_contracts_model.undo_error
    validation_lock = threading.Lock()
    second_validation = threading.Event()
    second_held = lock_contention(
        monkeypatch, page_dir, page_dir / schema_model.EVENTS_FILE
    )
    validation_calls = 0

    def expose_validation_gap(event, events, within, absorbed):
        nonlocal validation_calls
        error = real_undo_error(event, events, within, absorbed)
        with validation_lock:
            validation_calls += 1
            call = validation_calls
        if call == 1:
            wait_for(
                lambda: second_validation.is_set() or second_held.is_set(),
                bool,
                failure="the second undo neither validated nor waited on the log",
            )
        else:
            second_validation.set()
        return error

    monkeypatch.setattr(event_contracts_model, "undo_error", expose_validation_gap)
    start = threading.Barrier(3)
    results = []

    def withdraw(attempt):
        start.wait(timeout=STATED_TIMEOUT)
        results.append(
            fetch(
                f"{server}/api/event",
                data=json.dumps(
                    {
                        "kind": "undo",
                        "undoes": target["id"],
                        "attempt": attempt,
                    }
                ).encode(),
            )
        )

    threads = [
        threading.Thread(target=withdraw, args=(f"concurrent-undo-{at}",))
        for at in range(2)
    ]
    for thread in threads:
        thread.start()
    start.wait(timeout=STATED_TIMEOUT)
    for thread in threads:
        thread.join(timeout=STATED_TIMEOUT)

    assert not any(thread.is_alive() for thread in threads), "an undo never returned"
    assert validation_calls == 2
    assert {status for status, _ in results} == {200, 400}
    refusal = next(json.loads(body) for status, body in results if status == 400)
    assert refusal["final"] is True
    assert refused_on(refusal).code == "withdrawn-gesture"
    undos = [
        event
        for event in events_model.read_events(page_dir)
        if event.get("undoes") == target["id"]
    ]
    assert len(undos) == 1


def test_an_empty_agent_name_uses_the_harness_default(
    page_dir, sessionless, monkeypatch
):
    published(page_dir)
    monkeypatch.setenv("LEAF_SESSION_ID", "worker-1")
    monkeypatch.setenv("LEAF_AGENT", "")

    result = comment(page_dir, "--text", "Which worker said this?")

    assert result.exit_code == 0, result.output
    event = events_model.read_events(page_dir)[-1]
    assert (event["agent"], event["session"]) == ("Codex", "worker-1")


def test_the_door_admits_a_reaction_only_as_a_token_the_layer_declares(
    server, page_dir
):
    """A reaction is a comment or reply carrying `token` in place of `text`: one of
    the two and never both, a word the merged vocabulary declares, and no
    suggestion, hold, or markup riding beside it. What the door lets through it
    also lets the user take back — while it is still a mark. An answer under it
    makes it a thread, and a message with words in it was never a mark."""
    publish(page_dir)
    root = json.loads(
        fetch(
            f"{server}/api/event",
            data=json.dumps(
                {"kind": "comment", "revision": 1, "text": "why?"}
            ).encode(),
        )[1]
    )["state"]["events"][-1]
    for bad, says in [
        (
            {"kind": "comment", "revision": 1, "token": "shrug"},
            "unknown reaction token 'shrug'",
        ),
        (
            {"kind": "comment", "revision": 1, "token": "keep", "text": "and"},
            "is valid under each of",
        ),
        ({"kind": "comment", "revision": 1}, "is not valid under any of"),
        (
            {"kind": "comment", "revision": 1, "token": "keep", "suggestion": True},
            "suggestion",
        ),
        (
            {"kind": "reply", "revision": 1, "parent": root["id"], "token": "nope"},
            "unknown",
        ),
    ]:
        status, body = fetch(f"{server}/api/event", data=json.dumps(bad).encode())
        assert status == 400, (bad, body)
        assert says in json.loads(body)["error"], (bad, body)

    reaction = json.loads(
        fetch(
            f"{server}/api/event",
            data=json.dumps(
                {
                    "kind": "comment",
                    "revision": 1,
                    "token": "shorten",
                    "anchor": {"section": "plan", "quote": "Ship dark"},
                }
            ).encode(),
        )[1]
    )["state"]["events"][-1]
    assert reaction["author"] == "user" and "text" not in reaction
    nod = json.loads(
        fetch(
            f"{server}/api/event",
            data=json.dumps(
                {"kind": "reply", "revision": 1, "parent": root["id"], "token": "keep"}
            ).encode(),
        )[1]
    )["state"]["events"][-1]
    assert nod["token"] == "keep" and nod["parent"] == root["id"]

    # A message with words in it is said rather than unsaid.
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "undo", "undoes": root["id"]}).encode(),
    )
    assert status == 400 and refused_on(body).code == "said-message"
    # The mark on the thread comes off with one press.
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "undo", "undoes": nod["id"]}).encode(),
    )
    assert status == 200, body
    # And comes off once, however the second press gets here — the racing tab of the
    # door's own docstring. A withdrawn reaction is gone from `build_threads`, so the
    # kind's thread walk had nothing to find and raised out of the door instead: a 500
    # the browser is told to retry, against a state that will never answer differently.
    # The no-op costs a notice, which is what a final refusal is.
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "undo", "undoes": nod["id"]}).encode(),
    )
    assert status == 400, body
    answer = json.loads(body)
    assert answer["final"] is True, body
    assert refused_on(answer).code == "withdrawn-gesture", body
    # Every thread fold drops a withdrawn message, so nothing may name it as a parent:
    # a reply to it would open a thread with no root.
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps(
            {"kind": "reply", "revision": 1, "parent": nod["id"], "token": "keep"}
        ).encode(),
    )
    assert status == 400 and refused_on(body).code == "withdrawn-parent"
    # Nor may a message another stands on be withdrawn, a reaction to it included.
    mark = json.loads(
        fetch(
            f"{server}/api/event",
            data=json.dumps(
                {
                    "kind": "reply",
                    "revision": 1,
                    "parent": reaction["id"],
                    "token": "keep",
                }
            ).encode(),
        )[1]
    )["state"]["events"][-1]
    assert mark["parent"] == reaction["id"]
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "undo", "undoes": reaction["id"]}).encode(),
    )
    assert status == 400 and refused_on(body).code == "answered-reaction"
    # Answered, the page reaction is a thread, and the withdrawal would orphan
    # the answer; the user's move is in the thread it opened.
    thread_model.post_reply(page_dir, {"parent": reaction["id"]}, "Which part is long?")
    status, body = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "undo", "undoes": reaction["id"]}).encode(),
    )
    assert status == 400 and refused_on(body).code == "answered-reaction"


def test_admission_names_dependencies_and_revendoring_preserves_their_meaning(
    server, page_dir
):
    """Recorded identities become dependencies and keep their admitted fold and effect."""
    from leaf.files import latest_revision

    source = PAGE.replace("<lf-options>", '<lf-options id="picks" choose>')
    (page_dir / "index.html").write_text(source)
    publish(page_dir)
    revision = latest_revision(page_dir)
    command = {
        "kind": "action",
        "revision": revision,
        "widget": "picks",
        "action": "choose",
        "detail": {"value": ["flag-first"]},
        "attempt": "named-dependencies",
        "attention": False,
    }
    status, body = fetch(f"{server}/api/event", data=json.dumps(command).encode())
    assert status == 200, body
    events = json.loads(body)["state"]["events"]
    accepted = events[-1]
    assert accepted["attention"] is True
    retried_status, retried = fetch(
        f"{server}/api/event", data=json.dumps(command).encode()
    )
    assert retried_status == 200
    assert json.loads(retried)["state"]["events"][-1]["id"] == accepted["id"]
    assert set(accepted["meaning"]["depends"]) == {"picks", "flag-first"}
    within = passages_model.enclosing_ids(structure_model.SourceDocument(source))
    assert event_folds_model.action_retracted(
        accepted, {"flag-first": revision + 1}, within
    )
    moved = {**within, "flag-first": ("elsewhere", "flag-first")}
    assert not event_folds_model.action_retracted(
        accepted, {"flag-first": revision + 1}, moved
    )


def test_created_ids_cannot_collide_across_page_and_frozen_content():
    markup = (
        '<p id="reserved">Page</p><lf-options id="page-options" choose></lf-options>'
    )
    commands = [
        {"kind": "comment", "text": "Pick a seed."},
        {
            "kind": "reply",
            "author": "agent",
            "parent": "e1",
            "text": "Seeds",
            "markup": '<lf-options id="thread-options" choose></lf-options>',
        },
        {
            "kind": "action",
            "widget": "thread-options",
            "action": "add",
            "detail": {"option": "elm", "text": "Elm"},
        },
    ]
    for widget, identity in (("page-options", "elm"), ("thread-options", "reserved")):
        with pytest.raises(events_model.EventRefused) as refused:
            model.reading(
                markup,
                [
                    *commands,
                    {
                        "kind": "action",
                        "widget": widget,
                        "action": "add",
                        "detail": {"option": identity, "text": "Duplicate"},
                    },
                ],
            )
        assert refused_on(refused.value).code == "created-exists"
