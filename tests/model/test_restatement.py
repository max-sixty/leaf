"""What a version that marks an element `restated` leaves in force: each decision that
named the element, as the version now reads it, and never a decision the user had
replaced.

A decision that records a set of the widget's members, as an `lf-options` pick does,
loses the rewritten member and keeps the rest. Any other decision that named the
element no longer applies, and neither does any decision it replaced, so its
coordinate reads the version's markup. Every reader of what stands agrees: the
served projection the browser folds, the obligation, the undo list and the threads a
decision closes."""

import model_folds as model

from leaf.base import standing as standing_model
from leaf.log import events as event_folds_model
from leaf.log import obligations as obligations_model

CHOOSE = ("choice", "choice", "choose")


def group(*, multiple: bool = False, restated: tuple[str, ...] = ()) -> str:
    """A page asking one question of options a, b and c, `restated` marking some."""
    options = "".join(
        f'<lf-option id="{option}"{" restated" if option in restated else ""}>'
        f"{option.upper()}</lf-option>"
        for option in "abc"
    )
    kind = " multiple" if multiple else ""
    return model.leaf_page(
        "Questions", f'<lf-options id="choice"{kind}>{options}</lf-options>'
    )


def picked(*options: str, answered: bool) -> dict:
    return {
        "kind": "action",
        "widget": "choice",
        "action": "choose",
        "detail": {"value": list(options)},
        "facts": {"answered": answered},
    }


def rewrote(*ids: str) -> dict:
    """The note of version 1, at revision 2, which rewrote `ids`."""
    return {
        "kind": "note",
        "author": "agent",
        "version": 1,
        "revision": 2,
        "text": "Rewrote an option.",
        "restated": list(ids),
    }


def standing(state: dict, coordinate: tuple, revision: int = 2):
    """The value standing at `coordinate` in `revision`'s view, as the browser folds
    the served projection: the entry the server says wins there, with the value it
    says stands. None where no decision stands, so the markup decides."""
    projection = model.projected(state, revision)
    winners = set(projection["desired"])
    [*values] = (
        entry["value"]
        for entry in projection["entries"]
        if entry["event"]["id"] in winners and tuple(entry["coordinate"]) == coordinate
    )
    assert all(
        entry["stands"]
        for entry in projection["entries"]
        if entry["event"]["id"] in winners
    )
    return values[0] if values else None


def question(state: dict, revision: int = 2) -> dict:
    [item] = obligations_model.collection(
        [
            item
            for item in state["views"][str(revision)]["obligations"]
            if item["source"]["kind"] == "widget"
        ]
    )["all"]
    return item


def test_a_rewritten_option_leaves_a_single_choice_unpicked():
    """The user picked a, then b in its place, and a version rewrote b. Nothing is
    picked and the question asks again: the pick of a, which the user replaced, does
    not come back. Undo then takes back the pick of b, the user's newest gesture,
    which brings back the pick before it."""
    documents = {1: group(), 2: group(restated=("b",))}
    events = [picked("a", answered=True), picked("b", answered=True), rewrote("b")]
    state = model.reading(documents, events)
    assert standing(state, CHOOSE) == []
    item = question(state)
    assert (item["state"], item["next_actor"]) == ("waiting", "user")
    head = state["views"]["2"]["undo"][0]
    assert (head["event"]["id"], head.get("newest")) == ("e2", True)
    undone = model.reading(
        documents,
        [
            *events,
            {
                "kind": "undo",
                "undoes": "e2",
                "revision": 2,
                "facts": {"answered": True},
            },
        ],
    )
    assert standing(undone, CHOOSE) == ["a"]
    assert standing_model.answered(question(undone))


def test_a_rewritten_option_leaves_the_rest_of_a_multiple_pick():
    """The user picked a, then a and b, and a version rewrote b: a stays picked."""
    documents = {1: group(multiple=True), 2: group(multiple=True, restated=("b",))}
    state = model.reading(
        documents,
        [
            picked("a", answered=False),
            picked("a", "b", answered=False),
            rewrote("b"),
        ],
    )
    assert standing(state, CHOOSE) == ["a"]


def test_a_rewritten_option_never_brings_back_an_option_the_user_unpicked():
    """The user picked a, then a and b, then unpicked a, and a version rewrote b.
    Nothing is picked: the pick of a, which the user withdrew, does not come back."""
    documents = {1: group(multiple=True), 2: group(multiple=True, restated=("b",))}
    state = model.reading(
        documents,
        [
            picked("a", answered=False),
            picked("a", "b", answered=False),
            picked("b", answered=False),
            rewrote("b"),
        ],
    )
    assert standing(state, CHOOSE) == []
    assert [entry["event"]["id"] for entry in state["views"]["2"]["undo"]][:1] == ["e3"]


def test_a_pick_from_a_tab_on_the_older_version_leaves_the_pick_on_the_new_one():
    """A version rewrote the whole question, and the user picked c on it. A tab still
    showing the version before then picks a. That pick rests on the question the
    version rewrote, so it never comes into force, and the pick of c stands, still the
    user's to undo."""
    documents = {
        1: group(),
        2: group().replace(
            '<lf-options id="choice">', '<lf-options id="choice" restated>'
        ),
    }
    state = model.reading(
        documents,
        [
            rewrote("choice"),
            {**picked("c", answered=True), "revision": 2},
            picked("a", answered=True),
        ],
    )
    assert standing(state, CHOOSE) == ["c"]
    assert [entry["event"]["id"] for entry in state["views"]["2"]["undo"]] == ["e2"]


BOARD = (
    '<lf-board id="board">'
    '<lf-column id="todo" label="Todo"><lf-card id="k" label="K">K</lf-card>'
    "</lf-column>"
    '<lf-column id="next" label="Next"></lf-column>'
    '<lf-column id="later" label="Later"></lf-column>'
    "</lf-board>"
)


def moved(column: str) -> dict:
    return {
        "kind": "action",
        "widget": "board",
        "action": "move",
        "detail": {"unit": "k", "value": column, "rank": "1"},
    }


def test_a_rewritten_column_sends_the_card_moved_into_it_back_to_the_markup():
    """The user moved card k to Later, then to Next, and a version rewrote Next. A
    move records no set, so the move into Next no longer applies, and neither does
    the move to Later it replaced: the card stands where the version's markup puts
    it, and nothing is left to undo there. `page check` refuses `restated` on a
    column, so only a log written by hand reaches this; the fold reads it as it
    reads every decision that records no set."""
    documents = {revision: model.leaf_page("Board", BOARD) for revision in (1, 2)}
    state = model.reading(documents, [moved("later"), moved("next"), rewrote("next")])
    assert standing(state, ("board", "k", "move")) is None
    assert not [
        entry
        for entry in state["views"]["2"]["undo"]
        if entry["event"].get("widget") == "board"
    ]


def decide(identity, outcome, answer, depends):
    return {
        "kind": "action",
        "id": identity,
        "revision": 1,
        "widget": "sug-a",
        "action": "decide",
        "detail": {"outcome": outcome},
        "meaning": {"unit": "sug-a", "depends": list(depends), "answer": answer},
    }


def test_a_rewritten_element_under_a_suggestions_decision_brings_back_none_before_it():
    """The user accepted a suggestion, answering thread c1, then rejected it, and the
    rejection rested on a paragraph a version then rewrote. The rejection no longer
    applies, and neither does the acceptance it replaced: the suggestion stands
    undecided and c1 stays open. Admission rests a suggestion's decision on the
    suggestion alone, so only a log written by hand reaches this; the fold reads it
    as it reads a move (`thread_context` memberships and samples read it the same,
    in `test_thread_resolution.py` and `test_authored_markup.py`)."""
    within = {"sug-note": ("sug-a", "sug-note")}
    events = [
        {"kind": "comment", "id": "c1", "author": "user", "ts": "t", "text": "c1"},
        decide("accept", "accept", "c1", ("sug-a",)),
        decide("reject", "reject", None, ("sug-a", "sug-note")),
        {"kind": "note", "id": "v2", "revision": 2, "restated": ["sug-note"]},
    ]
    walk = event_folds_model.InForce(within)
    for event in events:
        if event["kind"] == "action":
            walk.admit(event)
        elif event["kind"] == "note":
            walk.restate(event)
    assert walk.winners() == {}
    assert event_folds_model.build_threads(events, within)["c1"]["resolved"] is None
