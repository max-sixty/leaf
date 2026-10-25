"""A board card that shows a section's answer (`x-shows`, `shown_answers.py`): the
answer stays the section widget's one fact, so the door takes no board move of the
card, and `page check` and message admission hold the markup's placement of it to that
answer."""

import pytest
from interact_support import ModelPage, found, model_layer, refused_on
from model_folds import leaf_page

from leaf.event_contracts import EventRefused, admitted_event
from leaf.shown_answers import named_value
from leaf.structure import SourceDocument
from leaf.validation.instances import instance_errors, reference_errors

NOW = "2026-10-25T12:00:00+00:00"


def section(group: str, chosen: str | None = None, extra: str = "") -> str:
    options = "".join(
        f'<lf-option id="{group}-{value}" value="{value}"'
        f"{' chosen' if value == chosen else ''}>{value.title()}</lf-option>"
        for value in ("next", "later", "drop")
    )
    return f'<lf-options id="{group}" choose>{options}{extra}</lf-options>'


def board(columns: dict[str, list[str]], open_column: bool = True) -> str:
    """A board whose columns hold the cards named, each showing the group of its
    name: `rail` shows `rail`, beside a card of the board's own. Without
    `open_column`, every column holds a value."""
    cards = {
        column: "".join(
            f'<lf-card id="card-{group}" shows="{group}"><strong>{group}</strong></lf-card>'
            for group in groups
        )
        for column, groups in columns.items()
    }
    return (
        '<lf-board id="plan">'
        + (
            f'<lf-column id="col-open" label="Undecided">{cards.get("open", "")}</lf-column>'
            if open_column
            else ""
        )
        + "".join(
            f'<lf-column id="col-{value}" label="{value.title()}" value="{value}">'
            f"{cards.get(value, '')}</lf-column>"
            for value in ("next", "later", "drop")
        )
        + '<lf-column id="col-mine" label="Mine"'
        + ("" if open_column else ' value="drop"')
        + '><lf-card id="card-own"><strong>Own</strong></lf-card></lf-column>'
        + "</lf-board>"
    )


PAGE = leaf_page(
    "Proposals",
    section("rail", chosen="later")
    + section("pager")
    + board({"later": ["rail"], "open": ["pager"]}),
)


def shown_findings(html: str):
    return [
        finding
        for finding in instance_errors(SourceDocument(html), model_layer())
        if finding.code.startswith("show")
    ]


def move(card: str, column: str, seq: int = 1) -> dict:
    return {
        "kind": "action",
        "id": f"m{seq}",
        "seq": seq,
        "ts": NOW,
        "author": "user",
        "revision": 1,
        "widget": "plan",
        "action": "move",
        "detail": {"unit": card, "value": column, "rank": "i"},
    }


def test_the_door_takes_no_board_move_of_a_card_showing_an_answer():
    """A drop on the board answers through the section's widget, so a board move of
    its card would be a second record of where the answer stands. A card the board
    owns still moves."""
    door = ModelPage(PAGE)
    with pytest.raises(EventRefused) as refused:
        admitted_event(door, [], move("card-rail", "col-next"))
    finding = refused_on(refused.value)
    assert (finding.code, finding.values["shows"]) == ("shown-unit", "rail")
    assert admitted_event(door, [], move("card-own", "col-next"))["meaning"]


def test_a_card_stands_where_its_widget_s_authored_answer_puts_it():
    assert shown_findings(PAGE) == []
    elsewhere = leaf_page(
        "Proposals",
        section("rail", chosen="later")
        + section("pager")
        + board({"next": ["rail"], "drop": ["pager"]}),
    )
    assert found(
        shown_findings(elsewhere),
        "shown-elsewhere",
        "<lf-card id=card-rail>",
        answer="later",
        stands="next",
    )
    assert found(
        shown_findings(elsewhere),
        "shown-elsewhere",
        "<lf-card id=card-pager>",
        answer=None,
        stands="drop",
    )


def test_an_answer_no_column_holds_stands_with_those_that_name_none():
    """The group may offer an answer the board has no column for; its card then
    stands where the answers naming no value do, rather than nowhere."""
    no_drop = board({"open": ["rail"]}).replace(
        '<lf-column id="col-drop" label="Drop" value="drop"></lf-column>', ""
    )
    page = leaf_page("Proposals", section("rail", chosen="drop") + no_drop)
    assert shown_findings(page) == []


def test_a_board_of_answers_holds_the_answers_that_name_none():
    """A cleared pick, an option the user wrote in, or several picks naming different
    values put the card in a column with no value; a board without one has nowhere to
    put it."""
    page = leaf_page(
        "Proposals",
        section("rail", chosen="later") + board({"later": ["rail"]}, open_column=False),
    )
    assert found(shown_findings(page), "shows-without-open", target="rail")


def test_every_column_value_is_one_the_widget_can_answer():
    page = leaf_page(
        "Proposals",
        section("rail", chosen="later")
        + board({"later": ["rail"]}).replace(
            '<lf-column id="col-mine" label="Mine">',
            '<lf-column id="col-mine" label="Mine" value="someday">',
        ),
    )
    assert found(
        shown_findings(page), "shows-untakeable", target="rail", value="someday"
    )


def test_a_card_shows_only_a_widget_whose_answer_names_a_value():
    page = leaf_page(
        "Proposals", board({"open": ["plan"]}).replace('shows="plan"', 'shows="plan"')
    )
    assert found(shown_findings(page), "shows-no-answer", target="plan")


def test_a_card_in_a_reply_shows_widgets_of_the_same_reply():
    """Frozen markup's answers are its own widgets', in the thread that holds them; a
    card in a reply naming a widget on the page would read state from another
    document."""
    page = SourceDocument(PAGE)
    reply = SourceDocument(
        board({"open": ["rail"]})
        .replace("plan", "reply-plan")
        .replace("card-", "reply-card-")
    )
    findings = reference_errors(
        reply.lf_elements,
        model_layer(),
        page.ids | reply.ids,
        {**page.by_id, **reply.by_id},
        thread_ids=set(),
    )
    assert found(findings, "shows-outside", target="rail")


@pytest.mark.parametrize(
    ("answer", "named"),
    [
        (["rail-next"], "next"),
        ([], None),
        # An option the user wrote in carries no value.
        (["rail-added"], None),
        (["rail-next", "rail-drop"], None),
    ],
)
def test_an_answer_names_a_value_only_when_its_picks_agree_on_one(answer, named):
    by_id = SourceDocument(
        section("rail") + '<lf-option id="rail-added">Ask</lf-option>'
    ).by_id
    assert named_value(answer, "value", by_id) == named
