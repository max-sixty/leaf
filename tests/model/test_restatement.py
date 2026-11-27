"""What the user's decisions on a question come to across a version, by the three rules
`events.md`, "Widget answers", states:

- each of the user's gestures carries the widget's word on whether its question is
  answered, and the latest gesture in force decides;
- a version marking an element `restated` takes that element out of each of the
  user's decisions resting on it, a set losing it as a member and any other decision
  going, and brings back no decision the user had replaced;
- that version asks the question again, until the user's next gesture on it.

Every reader of what stands agrees: the served projection the browser folds, the
obligation and the undo list."""

import model_folds as model

from leaf.base import standing as standing_model
from leaf.log import obligations as obligations_model

CHOOSE = ("choice", "choice", "choose")
DONE = ("choice", "choice", "answer")


def group(
    options: str = "abc", *, multiple: bool = False, restated: tuple[str, ...] = ()
) -> str:
    """A page asking one question of `options`, `restated` marking some of them or the
    group itself (`choice`)."""
    marked = lambda identity: " restated" if identity in restated else ""
    inner = "".join(
        f'<lf-option id="{option}"{marked(option)}>{option.upper()}</lf-option>'
        for option in options
    )
    kind = " multiple" if multiple else ""
    return model.leaf_page(
        "Questions",
        f'<lf-options id="choice"{kind}{marked("choice")}>{inner}</lf-options>',
    )


def picked(*options: str, answered: bool) -> dict:
    return {
        "kind": "action",
        "widget": "choice",
        "action": "choose",
        "detail": {"value": list(options)},
        "answered": answered,
    }


DONE_PRESS = {
    "kind": "action",
    "widget": "choice",
    "action": "answer",
    "detail": {},
    "answered": True,
}


def rewrote(*ids: str) -> dict:
    """The note of the version at revision 2, which rewrote `ids`."""
    return {
        "kind": "note",
        "author": "agent",
        "version": 1,
        "revision": 2,
        "text": "Rewrote the question.",
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
    return values[0] if values else None


def done(state: dict, revision: int = 2) -> bool:
    """Whether the user's Done stands in `revision`'s view."""
    projection = model.projected(state, revision)
    return any(
        tuple(entry["coordinate"]) == DONE
        and entry["event"]["id"] in projection["desired"]
        for entry in projection["entries"]
    )


def question(state: dict, revision: int = 2) -> dict:
    [item] = obligations_model.collection(
        [
            item
            for item in state["views"][str(revision)]["obligations"]
            if item["source"]["kind"] == "widget"
        ]
    )["all"]
    return item


def asks(state: dict, revision: int = 2) -> bool:
    item = question(state, revision)
    return (item["state"], item["next_actor"]) == ("waiting", "user")


def test_a_rewritten_option_leaves_a_single_choice_unpicked():
    """The user picked a, then b in its place, and a version rewrote b. Nothing is
    picked and the question asks again: the pick of a, which the user replaced, does
    not come back. Undo then takes back the pick of b, the user's newest gesture,
    which brings back the pick before it."""
    documents = {1: group(), 2: group(restated=("b",))}
    events = [picked("a", answered=True), picked("b", answered=True), rewrote("b")]
    state = model.reading(documents, events)
    assert standing(state, CHOOSE) == []
    assert asks(state)
    head = state["views"]["2"]["undo"][0]
    assert (head["event"]["id"], head.get("newest")) == ("e2", True)
    undone = model.reading(
        documents, [*events, {"kind": "undo", "undoes": "e2", "answered": True}]
    )
    assert standing(undone, CHOOSE) == ["a"]
    assert standing_model.answered(question(undone))


def test_a_rewritten_option_leaves_the_rest_of_a_multiple_pick_and_asks_again():
    """The user picked a, then a and b, pressed Done, and a version rewrote b: a stays
    picked, and the question asks again although the Done stands."""
    documents = {1: group(multiple=True), 2: group(multiple=True, restated=("b",))}
    state = model.reading(
        documents,
        [
            picked("a", answered=False),
            picked("a", "b", answered=False),
            DONE_PRESS,
            rewrote("b"),
        ],
    )
    assert standing(state, CHOOSE) == ["a"]
    assert done(state)
    assert asks(state)


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
    assert asks(state)
    assert [entry["event"]["id"] for entry in state["views"]["2"]["undo"]][:1] == ["e3"]


def test_a_pick_changed_after_done_leaves_the_question_answered():
    """Done says the set is whole until the user takes it back, so a pick the user
    changes after it carries the word that the question is answered."""
    documents = {1: group(multiple=True)}
    state = model.reading(
        documents,
        [picked("a", answered=False), DONE_PRESS, picked("a", "b", answered=True)],
    )
    assert standing_model.answered(question(state, 1))


def test_a_step_added_without_restated_leaves_a_checklist_answered():
    """A version that gives an answered checklist a step, and restates nothing, leaves
    the question answered: an edit to a widget's markup asks nothing again."""
    documents = {1: group("ab", multiple=True), 2: group("abc", multiple=True)}
    state = model.reading(
        documents,
        [picked("a", answered=False), DONE_PRESS, rewrote()],
    )
    assert standing_model.answered(question(state))


def test_restating_a_group_asks_again_with_every_pick_kept():
    """To ask an answered question again, as about a checklist given a step, a version
    restates the group. Each pick rests on the group but names its options, so every
    pick stands, while the Done, a decision about the group itself, goes."""
    documents = {
        1: group("ab", multiple=True),
        2: group("abc", multiple=True, restated=("choice",)),
    }
    state = model.reading(
        documents,
        [picked("a", "b", answered=False), DONE_PRESS, rewrote("choice")],
    )
    assert standing(state, CHOOSE) == ["a", "b"]
    assert not done(state)
    assert asks(state)
    assert standing_model.answered(
        question(
            model.reading(
                documents,
                [
                    picked("a", "b", answered=False),
                    DONE_PRESS,
                    rewrote("choice"),
                    {**DONE_PRESS, "revision": 2},
                ],
            )
        )
    )


def test_the_last_of_two_crossing_gestures_says_whether_the_question_is_answered():
    """Tab B picks a and presses Done; tab A, which has seen neither, picks a too, and
    its pick lands last saying the question is open. Its word stands: the question
    asks again, while B's Done still stands in the checklist's state."""
    documents = {1: group(multiple=True)}
    state = model.reading(
        documents,
        [picked("a", answered=False), DONE_PRESS, picked("a", answered=False)],
    )
    assert asks(state, 1)
    assert done(state, 1)


def test_a_pick_from_a_tab_on_the_older_version_asks_again():
    """A version rewrote the whole question, and the user picked c on it. A tab still
    showing the version before then picks a. The version reads that pick as it reads
    every decision resting on the group, so it stands and wins, and the question asks
    again, since its word was worked out on the question the version rewrote."""
    documents = {1: group(), 2: group(restated=("choice",))}
    state = model.reading(
        documents,
        [
            rewrote("choice"),
            {**picked("c", answered=True), "revision": 2},
            picked("a", answered=True),
        ],
    )
    assert standing(state, CHOOSE) == ["a"]
    assert asks(state)
