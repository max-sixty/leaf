"""Fold one document and one log into the reading a browser receives.

The document starts state and the log changes it, and every current-state
projection is that pair put through one construction. `read_served_page` builds
the complete server response from a `PageRead`: documents, events, a registry,
and a presence reading — no page directory, server, or browser. A test whose
subject is that reading calls it here with literal markup and a literal log.

What a fixture here cannot answer is anything a renderer decides. The reading is
what the runtime is handed, not what a widget module draws with it, so a claim
about a painted word, a node's identity across a poll, or an elapsed line a
browser clock advances stays in `test_render_*.py`.

A test of what the door refuses belongs with the door, on
`interact_support.ModelPage`, which states a page the same way for
`event_contracts.admitted_event`. The two divide by subject rather than by
machinery — a rule the door decides goes there, a reading the fold produces
comes here — and they state the page through the same class and compose the
same vocabulary through `model_layer`.

That is also why every command written here goes through that door on its way
into the log. A fold is only worth what its premise is worth, and a premise
assembled beside the door can be one the product would never have accepted: an
action naming a widget the page has not got, a `holds` on a widget that does
not take one, a coordinate written by hand rather than derived. Each of those
now raises `EventRefused` instead of folding.

Every value the server would read from a file is a literal in this module, so a
reading it returns is caused by the markup and the log the test wrote and by
nothing else on the machine.
"""

from interact_support import ModelPage, model_layer
from leaf.event_contracts import admitted_event
from leaf.files import document_descriptor, version_descriptors
from leaf.passages import SourceReading
from leaf.served_state.context import PageRead
from leaf.served_state.page import read_served_page
from leaf.structure import SourceDocument

NOW = "2026-09-19T12:00:00+00:00"

# A page nobody has claimed, as `presence.presence` reports one: the agent has
# declared nothing and no session holds it now. Written out because these are the
# facts a fold is allowed to see, and a fixture that reached for the real reading
# would bring the developer's own machine with it.
UNCLAIMED = {
    "status": {"state": "waiting", "detail": ""},
    "listening": False,
    "cursor": 0,
    "pending": 0,
    "agent": "Agent",
    "session_alive": None,
    "claim_session": None,
    "claim_turn": None,
    "turn_closed": None,
    "viewed": None,
    "session_cwd": None,
}


def leaf_page(
    title: str, body: str, *, head: str = "", layout: str | None = "column"
) -> str:
    """A complete page carrying the presentation boundary every fixture shares. `layout`
    names the Layout `main` takes (`wide` is `<main class="layout-wide">`): the column,
    the Layout most pages take, unless the test says otherwise, and None for a `main`
    with no Layout at all."""
    extra_head = f"{head}\n" if head else ""
    main = f'<main class="layout-{layout}">' if layout else "<main>"
    return f"""<!doctype html>
<html lang="en">
<head>
<title>{title}</title>
{extra_head}
</head>
<body>
{main}{body}</main>
</body>
</html>
"""


def served_reading(
    documents: dict[int, str] | str,
    events: tuple[dict, ...] | list[dict] = (),
    *,
    registry: dict | None = None,
    view_revision: int | None = None,
) -> dict:
    """The `/api/state` reading of one page, folded in this process.

    `documents` holds the revisions available at this point, or one string for
    a single revision. The newest is active; `view_revision` also reads a historical
    document, through the same route as the browser.

    `events` are written the way a command states them. The log's own fields —
    `id` (`e1`, `e2`, … in written order, which is what a later event names its
    parent by), `seq`, `ts`, `author` (the user) and `revision` (1) — are filled
    where the test leaves them out.

    Each one then goes through the same append door the server admits it through,
    so what this folds is a log the page could really have. A command the door
    would refuse raises `EventRefused` here rather than folding: the fixture cannot
    state a premise the product would not have accepted. The work the agent has in hand is
    such a command too: a `start` naming a move or task, as `leaf task start`
    writes it.
    """
    if isinstance(documents, str):
        documents = {1: documents}
    parsed = {rev: SourceDocument(html) for rev, html in documents.items()}
    # The layer identity is fixed fixture input; the vocabulary is composed from
    # the same packages the page would install, without writing an installation.
    registry = {
        **(registry or model_layer()),
        "$layer": {
            "generation": "0" * 32,
            "fingerprint": "0" * 64,
            "runtime": "0" * 64,
            "server": "0" * 64,
            "packages": [],
        },
    }
    door = ModelPage(documents=parsed, registry=registry)
    kinds = registry["$events"]["kinds"]
    log = []
    for seq, command in enumerate(events, 1):
        # Which envelope fields a kind carries is the kind's own declaration, so
        # the revision goes on only where the record has somewhere to put it: a
        # resolve or an undo names no document and is refused if handed one.
        carries = kinds.get(command.get("kind"), {}).get("record", {})
        stamped = {"id": f"e{seq}", "seq": seq, "ts": NOW, "author": "user"}
        if "revision" in carries.get("properties", {}):
            stamped["revision"] = 1
        log.append(admitted_event(door, log, {**stamped, **command}))
    active_revision = max(parsed)
    active = document_descriptor(
        active_revision,
        log,
        url=f"/revisions/r{active_revision}-{'0' * 16}.html",
        executable="0" * 64,
        activated_at=NOW,
    )
    readings = {
        rev: SourceReading(document, registry) for rev, document in parsed.items()
    }
    return read_served_page(
        PageRead(
            active=active,
            events=log,
            revisions=frozenset(parsed),
            revision=readings.__getitem__,
            registry=registry,
            layer=registry["$layer"],
            stored_data=lambda: {"version": "0" * 16, "sources": {}},
            versions=tuple(version_descriptors(log, parsed)),
            presence=UNCLAIMED,
            live_stream=None,
            now=NOW,
            taken=float(len(log) + 1),
        ),
        view_revision=view_revision,
    ).state


def reading(
    documents: dict[int, str] | str,
    events: tuple[dict, ...] | list[dict] = (),
    *,
    registry: dict | None = None,
    view_revision: int | None = None,
) -> dict:
    """The semantic browser projection beside its page-wide work readings.

    Model assertions select from this view; wire consumers use `served_reading`
    for the complete `/api/state` answer, including its envelope.
    """
    state = served_reading(
        documents, events, registry=registry, view_revision=view_revision
    )
    return {
        **state["browser"],
        "activity": state["activity"],
        "workflows": state["workflows"],
    }


def threads(state: dict) -> dict:
    """Threads by id, as the panel is handed them."""
    return {thread["id"]: thread for thread in state["thread"]["threads"]}


def projected(state: dict, revision: int) -> dict:
    """One revision's document projection, as the runtime applies it."""
    return state["views"][str(revision)]["document"]["projection"]
