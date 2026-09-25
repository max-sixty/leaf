"""Fold one document and one log into the reading a browser receives.

The document starts state and the log changes it, and every current-state
projection is that pair put through one construction. `browser_state` is where
the server performs it, and it takes documents, events, a registry, and a
presence reading — no page directory, no server, and no browser. A test whose
subject is that fold calls it here with literal markup and a literal log.

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
from leaf.served_state.browser import browser_state
from leaf.structure import SourceDocument

NOW = "2026-09-19T12:00:00+00:00"

# A page nobody has claimed, as `presence.presence` reports one: the agent said
# what it was doing while writing the page and no session holds it now. Written
# out because these are the facts a fold is allowed to see, and a fixture that
# reached for the real reading would bring the developer's own machine with it.
UNCLAIMED = {
    "status": {"state": "working", "detail": "Writing the page", "ts": NOW, "after": 0},
    "claims": [],
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
    title: str, body: str, *, head: str = "", width: str | None = None
) -> str:
    """A complete page carrying the presentation boundary every fixture shares. `width`
    widens the page itself (`<main data-width>`)."""
    extra_head = f"{head}\n" if head else ""
    main = f'<main data-width="{width}">' if width else "<main>"
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


def reading(
    documents: dict[int, str] | str,
    events: tuple[dict, ...] | list[dict] = (),
    *,
    registry: dict | None = None,
    revision: int | None = None,
) -> dict:
    """The `/api/state` reading of one page, folded in this process.

    `documents` is the authored markup of each revision, or one string for a
    single-revision page; `revision` is the active one, newest by default.

    `events` are written the way a command states them. The log's own fields —
    `id` (`e1`, `e2`, … in written order, which is what a later event names its
    parent by), `seq`, `ts`, `author` (the user) and `revision` (1) — are filled
    where the test leaves them out.

    Each one then goes through the same append door the server admits it through,
    so what this folds is a log the page could really have. A command the door
    would refuse raises `EventRefused` here rather than folding: the fixture cannot
    state a premise the product would not have accepted.
    """
    if isinstance(documents, str):
        documents = {1: documents}
    parsed = {rev: SourceDocument(html) for rev, html in documents.items()}
    registry = registry or model_layer()
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
    active_revision = revision if revision is not None else max(parsed)
    active = {
        "revision": active_revision,
        "version": active_revision,
        "url": f"/revisions/r{active_revision}.html",
        "label": f"v{active_revision}",
        "executable": f"model-r{active_revision}",
        "activated_at": NOW,
    }
    return browser_state(
        parsed,
        log,
        registry,
        active_revision,
        UNCLAIMED,
        active,
        {active_revision},
        NOW,
    )


def threads(state: dict) -> dict:
    """Threads by root id, as the panel is handed them."""
    return {thread["root"]["id"]: thread for thread in state["thread"]["threads"]}


def projected(state: dict, revision: int) -> dict:
    """One revision's document projection, as the runtime applies it."""
    return state["views"][str(revision)]["document"]["projection"]
