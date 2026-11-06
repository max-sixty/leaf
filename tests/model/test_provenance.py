"""Which of the user's messages waited while a version was saved, and where each
revision stands in the log (`provenance.py`, `revisioning.py`): what a version says
it was saved after."""

import random
from copy import deepcopy
from operator import itemgetter

from click.testing import CliRunner
from interact_support import ModelPage, append_command, model_layer, response_reference
from model_folds import NOW, leaf_page, served_view

from leaf import cli as cli_model
from leaf import event_log as event_log_model
from leaf.event_contracts import admitted_event
from leaf.event_log import EventRefused
from leaf.events import build_threads, spoken_turns, taken_back, unanswered_turns
from leaf.passages import SourceReading, enclosing_ids
from leaf.provenance import revision_places
from leaf.provenance import saved_after as line_of
from leaf.registry.kernel import kernel_event_kinds
from leaf.revisioning import activate_source
from leaf.structure import SourceDocument
from model.interact_contract.test_thread_resolution import (
    ASKED,
    CLOSED,
    PICKED,
    SETTLED,
)

AGENT = {"author": "agent", "agent": "Claude", "session": "s1"}
PAGE = {
    revision: leaf_page("Plan", f'<p id="p">Version {revision}.</p>')
    for revision in (1, 2, 3)
}


def live(revision):
    """The `activation` a read appends as the revision goes live."""
    return {
        "kind": "activation",
        "author": "page",
        "revision": revision,
        "publication": f"r{revision}-{revision:016x}",
    }


def waited(message, said=None, thread=None):
    """A message the line names, with the event whose words stood: its own, unless
    `said` names a rewrite of it."""
    return {"thread": thread or message, "message": message, "said": said or message}


def saved_after(events, base, shown, documents=PAGE, registry=None):
    return served_view(documents, events, base, shown, registry=registry)["saved_after"]


def test_a_version_names_what_waited_as_it_read_then_and_nothing_later_moves_it():
    """A version names each message that waited while it was saved, with the event
    whose words it had then. Taking back a rewrite or the comment itself after the
    version went live changes nothing it says; taking either back before, or the agent
    answering before, does."""
    comment = {"kind": "comment", "text": "Make it **blue**\nfor the header"}
    rewrite = {"kind": "edit", "message": "e2", "text": "Make it red"}
    saved = [live(1), comment, rewrite, live(2)]
    assert saved_after(saved, 1, 2) == [waited("e2", "e3")]
    taken_back = [
        *saved,
        {"kind": "undo", "undoes": "e3"},
        {"kind": "undo", "undoes": "e2"},
    ]
    assert saved_after(taken_back, 1, 2) == [waited("e2", "e3")]
    assert saved_after(
        [live(1), comment, rewrite, {"kind": "undo", "undoes": "e3"}, live(2)], 1, 2
    ) == [waited("e2")]
    assert (
        saved_after([live(1), comment, {"kind": "undo", "undoes": "e2"}, live(2)], 1, 2)
        == []
    )
    answered = {
        "kind": "reply",
        "parent": "e2",
        "responds": "e2",
        "text": "Blue.",
        **AGENT,
    }
    assert saved_after([live(1), comment, answered, live(2)], 1, 2) == []


def test_a_message_reads_as_it_did_at_the_latest_revision_it_waited_at():
    """A comment that waited across one of a version's revisions, was answered, then
    rewritten and answered again before the version's last revision went live, is
    quoted as it read where it waited, not as it read when the version went live.
    One that waited at two of the version's revisions in different words is quoted
    in the later."""
    comment = {"kind": "comment", "text": "Make it blue"}
    rewrite = {"kind": "edit", "message": "e1", "text": "Make it red"}

    def answer(turn):
        return {
            "kind": "reply",
            "parent": "e1",
            "responds": turn,
            "text": "Done.",
            **AGENT,
        }

    answered_twice = [comment, live(2), answer("e1"), rewrite, answer("e4"), live(3)]
    assert saved_after(answered_twice, 1, 3) == [waited("e1")]
    waited_twice = [comment, live(2), rewrite, live(3)]
    assert saved_after(waited_twice, 1, 3) == [waited("e1", "e3")]
    assert saved_after(waited_twice, 1, 2) == [waited("e1")]


def test_a_message_waited_where_its_thread_stood_open_at_any_of_the_versions_revisions():
    """A version whose revisions went live while a message waited at any of them names
    it, though it was resolved before the last. Accepting a suggestion closes its
    thread as a resolution does; taking the accept back while the user's resolution
    stands leaves it closed, and taking back a reopening closes it again."""
    resolved = [
        live(1),
        {"kind": "comment", "text": "Why?"},
        live(2),
        {"kind": "resolve", "parent": "e2"},
        live(3),
    ]
    assert saved_after(resolved, 1, 3) == [waited("e2")]
    assert saved_after(resolved, 2, 3) == []

    # The suggestions answer `e1`, so the comment comes first.
    pages = {1: SETTLED, 2: SETTLED, 3: SETTLED}
    assert saved_after([ASKED, live(2)], 1, 2, pages) == [waited("e1")]
    assert saved_after([ASKED, PICKED, live(2)], 1, 2, pages) == []
    overlapping = [ASKED, PICKED, CLOSED, {"kind": "undo", "undoes": "e2"}, live(2)]
    assert saved_after(overlapping, 1, 2, pages) == []
    reopened = [
        ASKED,
        CLOSED,
        {"kind": "unresolve", "parent": "e1"},
        live(2),
        {"kind": "undo", "undoes": "e3"},
        live(3),
    ]
    assert saved_after(reopened, 1, 3, pages) == [waited("e1")]
    assert saved_after(reopened, 2, 3, pages) == []


def test_each_revision_is_judged_by_the_log_before_it():
    """Who waited at each of a version's revisions is read from the log up to it: a
    comment taken back after one revision went live waited there, and a rewrite taken
    back after it is quoted, for it was what waited."""
    undone_comment = [
        live(1),
        {"kind": "comment", "text": "Why?"},
        live(2),
        {"kind": "undo", "undoes": "e2"},
        live(3),
    ]
    assert saved_after(undone_comment, 1, 3) == [waited("e2")]
    assert saved_after(undone_comment, 2, 3) == []
    undone_rewrite = [
        {"kind": "comment", "text": "Make it blue"},
        {"kind": "edit", "message": "e1", "text": "Make it red"},
        live(2),
        {"kind": "reply", "parent": "e1", "responds": "e2", "text": "Red.", **AGENT},
        {"kind": "undo", "undoes": "e2"},
        live(3),
    ]
    assert saved_after(undone_rewrite, 1, 3) == [waited("e1", "e2")]


def test_each_revision_is_read_under_the_document_live_there():
    """A choice closes a comment's thread; the next version restates the chosen
    option, which reopens it, so the comment waits as the version after it goes live.
    A later version moving the option into another group changes nothing an earlier
    comparison says, since each revision's place is read under its own document."""
    registry = deepcopy(model_layer())
    registry["lf-options"]["properties"]["resolves"] = {"type": "string"}
    first = leaf_page(
        "Options",
        '<lf-options id="picks" choose resolves="e2">'
        '<lf-option id="option-a">A</lf-option><lf-option id="option-b">B</lf-option>'
        '</lf-options><lf-options id="other"><lf-option id="option-c">C</lf-option>'
        "</lf-options>",
    )
    second = first.replace('id="option-a"', 'id="option-a" restated').replace(
        ">A<", ">A reconsidered<"
    )
    third = second.replace(">A reconsidered<", ">A reconsidered again<")
    moved = '<lf-option id="option-a" restated>A reconsidered again</lf-option>'
    fourth = third.replace(moved, "").replace(
        '<lf-options id="other">', f'<lf-options id="other">{moved}'
    )
    events = [
        live(1),
        {"kind": "comment", "text": "Please reconsider A"},
        {
            "kind": "action",
            "widget": "picks",
            "action": "choose",
            "detail": {"value": ["option-a"]},
        },
        {
            "kind": "note",
            "revision": 2,
            "version": 1,
            "text": "Reconsider A",
            "restated": ["option-a"],
            **AGENT,
        },
        live(2),
        live(3),
    ]
    asked = [waited("e2")]
    documents = {1: first, 2: second, 3: third}
    assert saved_after(events, 2, 3, documents, registry) == asked
    documents = {**documents, 4: fourth}
    assert saved_after([*events, live(4)], 2, 3, documents, registry) == asked


def test_a_comparison_across_a_stamped_version_says_nothing():
    """Nothing knows which of several versions made a change."""
    stamped = [
        live(1),
        live(2),
        {"kind": "note", "version": 1, "revision": 2, "text": "Two.", **AGENT},
        live(3),
    ]
    assert saved_after(stamped, 1, 3) is None
    assert saved_after(stamped, 2, 3) == []
    assert served_view(PAGE, stamped, 2)["saved_after"] is None


def test_a_revision_takes_its_place_in_the_log_from_the_event_naming_its_bundle(
    page_dir,
):
    """A save a read activates appends an `activation` naming its bundle, after every
    event before it, however old a revision a message names; a save a reply publishes
    takes the reply's place, the end of the wait it answers."""
    index = page_dir / "index.html"
    said = ["Ship dark."]

    def save(words):
        index.write_text(index.read_text().replace(said[-1], words, 1))
        said.append(words)

    def place(revision):
        [named] = [
            event
            for event in event_log_model.read_events(page_dir)
            if event.get("publication") and event["revision"] == revision
        ]
        return named["seq"]

    first = activate_source(page_dir).revision
    save("Ship dark, behind a flag.")
    unread = activate_source(page_dir).revision
    asked = append_command(
        page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": first,
            "text": "Which flag?",
            "anchor": {"section": "plan"},
        },
    )
    assert place(unread) < asked["seq"]
    save("Ship dark, behind the rollout flag.")
    assert place(activate_source(page_dir).revision) > asked["seq"]

    save("Ship dark, behind the rollout flag, off by default.")
    replied = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(page_dir, asked),
            "--text",
            "The rollout flag, off by default.",
        ],
        catch_exceptions=False,
    )
    assert replied.exit_code == 0, replied.output
    [reply] = [
        event
        for event in event_log_model.read_events(page_dir)
        if event["kind"] == "reply"
    ]
    assert place(reply["revision"]) == reply["seq"]


# A page of three option groups whose options the versions move, drop and bring back,
# whose `add` creates an option where none of its id stands, and whose single choices
# answer the opening comment `e2`.
OWNED = deepcopy(model_layer())
OWNED["lf-options"]["properties"]["resolves"] = {"type": "string"}
OWNED["lf-options"]["x-state"]["add"] = {
    "detail": {
        "type": "object",
        "properties": {"item": {"type": "string"}, "text": {"type": "string"}},
        "required": ["item", "text"],
        "additionalProperties": False,
    },
    "unit": "item",
    "creates": {"child": "lf-option", "words": "text"},
}
KINDS = kernel_event_kinds()


def owned_page(owners):
    """Groups g0-g2 holding the options `owners` places in each, g2 taking several at
    once; an option placed in no group stands nowhere."""
    return leaf_page(
        "Owned",
        "".join(
            f'<lf-options id="g{group}" choose{" multiple" * (group == 2)} resolves="e2">'
            + "".join(
                f'<lf-option id="o{option}">Option {option}</lf-option>'
                for option, home in enumerate(owners)
                if home == group
            )
            + "</lf-options>"
            for group in range(3)
        ),
    )


def admit(page, log, step, revision=1):
    """`step` as the log holds it: admitted as the door admits it, or an activation
    as the publisher appends it."""
    seq = len(log) + 1
    event = {"id": f"e{seq}", "seq": seq, "ts": NOW, "author": "user", **step}
    if "revision" in KINDS[event["kind"]]["record"]["properties"]:
        event.setdefault("revision", revision)
    if event["kind"] == "activation":
        return {**event, "attention": False}
    return admitted_event(page, log, event)


def folded_at_each_revision(log, within, base, shown):
    """What the line says, read the long way: the log up to each revision of the
    version folded under that revision's containment, and the messages its threads
    still owe an answer where they stand open, in the words they then had."""
    found = {}
    for revision, place in sorted(revision_places(log).items()):
        if not base < revision <= shown:
            continue
        prefix = [event for event in log if event["seq"] < place]
        for thread in build_threads(prefix, within[revision]).values():
            if thread["resolved"]:
                continue
            said = {message["id"]: message for message in thread["msgs"]}
            for turn in unanswered_turns(thread):
                message = said[turn.get("message", turn["id"])]
                found[message["id"]] = (
                    message["seq"],
                    {
                        "thread": thread["id"],
                        "message": message["id"],
                        "said": (message.get("edited") or message)["id"],
                    },
                )
    return [entry for _seq, entry in sorted(found.values(), key=itemgetter(0))]


def read_line(log, documents, base, shown):
    """The line `saved_after` reads, each revision read as a server holds it."""
    readings = {r: SourceReading(document, {}) for r, document in documents.items()}
    return line_of(
        log,
        readings.__getitem__,
        revision_places(log),
        range(1, max(readings) + 1),
        set(),
        base,
        shown,
    )


def test_a_choice_stays_conditional_beside_a_creation_of_the_same_option():
    """A choice of `o0` that closes the comment rests on `o0` only while its group
    holds it; an `add` that recreates `o0` there rests on it always. Restating `o0`
    while it stands nowhere leaves the choice in force and the comment closed; the
    next version puts `o0` back in the group, which retracts the choice, and the
    comment waits there again."""
    page = ModelPage(
        *(owned_page(owners) for owners in ([0], [None], [None], [None], [0])),
        registry=OWNED,
    )
    log = []
    for step in [
        live(1),
        {"kind": "comment", "text": "Which one?"},
        {
            "kind": "action",
            "widget": "g0",
            "action": "choose",
            "detail": {"value": ["o0"]},
        },
        live(2),
        {
            "kind": "action",
            "revision": 2,
            "widget": "g0",
            "action": "add",
            "detail": {"item": "o0", "text": "Again"},
        },
        live(3),
        {
            "kind": "note",
            "revision": 3,
            "version": 1,
            "restated": ["o0"],
            "text": "Ask",
            **AGENT,
        },
        live(4),
        live(5),
    ]:
        log.append(admit(page, log, step))
    within = {r: enclosing_ids(document) for r, document in page.documents.items()}
    asked = [waited("e2")]
    assert folded_at_each_revision(log, within, 3, 5) == asked
    assert read_line(log, page.documents, 3, 5) == asked


def test_the_line_reads_each_revision_as_a_fold_up_to_it_would():
    """On random logs of comments, replies, answers, resolutions, rewrites, undos,
    choices, created options and restatements, over versions that move, drop and
    bring back options, the line names the messages a fold of the log up to each of
    the version's revisions under its containment finds waiting, in the same words."""
    moves = ["comment", "reply", "answer", "resolve", "unresolve", "edit", "undo"]
    moves += ["save", "choose", "create", "restate"]
    for seed in range(24):
        rng = random.Random(seed)
        page = ModelPage(owned_page([0, 1, 2, None, 0]), registry=OWNED)
        revision = 1
        log = []
        for step in [live(1), {"kind": "comment", "text": "Opening question"}]:
            log.append(admit(page, log, step))
        for at in range(60):
            threads = list(build_threads(log, page.within).values())
            if not threads:
                log.append(
                    admit(page, log, {"kind": "comment", "text": "Again"}, revision)
                )
                continue
            thread = rng.choice(threads)
            move = rng.choice(moves)
            if move == "save":
                revision += 1
                owners = [rng.choice([0, 1, 2, None]) for _ in range(5)]
                page.documents[revision] = SourceDocument(owned_page(owners))
                step = live(revision)
            elif move == "comment":
                step = {"kind": "comment", "text": f"Comment {at}"}
            elif move == "reply":
                step = {"kind": "reply", "parent": thread["id"], "text": f"Reply {at}"}
            elif move == "answer" and (owed := unanswered_turns(thread)):
                step = {
                    "kind": "reply",
                    "parent": thread["id"],
                    "responds": rng.choice(owed)["id"],
                    "text": f"Answer {at}",
                    **AGENT,
                }
            elif move in ("resolve", "unresolve"):
                step = {"kind": move, "parent": thread["id"]}
            elif move == "edit" and (
                said := [t for t in spoken_turns(thread) if t["author"] == "user"]
            ):
                step = {
                    "kind": "edit",
                    "message": rng.choice(said)["id"],
                    "text": f"Now {at}",
                }
            elif move == "undo" and (
                gestures := [
                    event
                    for event in log
                    if event["author"] == "user"
                    and event["kind"] != "undo"
                    and event["id"] not in taken_back(log)
                ]
            ):
                step = {"kind": "undo", "undoes": rng.choice(gestures)["id"]}
            elif move in ("choose", "create"):
                sent = rng.randrange(1, revision + 1)
                owner = f"g{rng.randrange(3)}"
                held = enclosing_ids(page.documents[sent])
                options = [f"o{o}" for o in range(5) if owner in held.get(f"o{o}", ())]
                detail = (
                    {"value": rng.sample(options, rng.randrange(len(options) + 1))}
                    if move == "choose"
                    else {"item": f"o{rng.randrange(5)}", "text": f"Made {at}"}
                )
                action = {"choose": "choose", "create": "add"}[move]
                step = {
                    "kind": "action",
                    "revision": sent,
                    "widget": owner,
                    "action": action,
                    "detail": detail,
                }
            elif move == "restate":
                restated = rng.sample([f"o{o}" for o in range(5)], rng.randrange(1, 4))
                step = {
                    "kind": "note",
                    "revision": revision,
                    "version": revision,
                    "restated": restated,
                    "text": "Ask",
                    **AGENT,
                }
            else:
                continue
            try:
                log.append(admit(page, log, step, revision))
            except EventRefused:
                continue
        revision += 1
        page.documents[revision] = SourceDocument(owned_page([0, 1, 2, None, 0]))
        log.append(admit(page, log, live(revision)))
        within = {r: enclosing_ids(document) for r, document in page.documents.items()}
        for base in sorted({1, revision - 1, rng.randrange(1, revision)}):
            assert read_line(
                log, page.documents, base, revision
            ) == folded_at_each_revision(log, within, base, revision), (seed, base)
