"""Fold one document and one log into the reading a browser receives.

The document starts state and the log changes it, and every current-state
projection is that pair put through one construction. `browser_state` is where
the server performs it, and it takes documents, events, a registry, and a
presence reading — no page directory, no server, and no browser. A test whose
subject is that fold calls it here with literal markup and a literal log.

What a fixture here cannot answer is anything a renderer decides. The reading is
what the runtime is handed, not what a widget module draws with it, so a claim
about a painted word, a node's identity across a poll, or an elapsed line a
browser clock advances stays in `test_render_*.py`. Nor is the append door's
refusal here: its gates read revisions and data off disk, so a test of what the
door refuses still takes `page_dir`. What the door stamps on an event it admits
is here, through the same `admit_widget_event`.

Every value the server would read from a file is a literal in this module, so a
reading it returns is caused by the markup and the log the test wrote and by
nothing else on the machine.
"""

from leaf.event_meaning import admit_widget_event
from leaf.layer import layer_inputs
from leaf.served_state.browser import browser_state
from leaf.structure import SourceDocument
from leaf.validation.compatibility import incoming_registry

# One composition per package selection per session. The registry is the same
# object `page init` vendors, read from the bundled packages rather than from a
# page, and nothing below mutates it.
_layers: dict[tuple[str, ...], dict] = {}

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


def leaf_page(title: str, body: str, *, head: str = "") -> str:
    """A complete page carrying the presentation boundary every fixture shares."""
    extra_head = f"{head}\n" if head else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<title>{title}</title>
{extra_head}
</head>
<body>
<main>{body}</main>
</body>
</html>
"""


def layer(*packages: str) -> dict:
    """The vendored registry for a package selection, composed once."""
    return _layers.setdefault(packages, incoming_registry(layer_inputs(packages)))


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
    parent by), `seq`, `ts`, `author` (the reader) and `revision` (1) — are filled
    where the test leaves them out, and a widget event gets the `meaning` admission
    would stamp from the revision it names.
    """
    if isinstance(documents, str):
        documents = {1: documents}
    parsed = {rev: SourceDocument(html) for rev, html in documents.items()}
    registry = registry or layer()
    log = []
    for seq, command in enumerate(events, 1):
        event = {
            "id": f"e{seq}",
            "seq": seq,
            "ts": NOW,
            "author": "user",
            "revision": 1,
            **command,
        }
        if event["kind"] in {"action", "report", "request"} and "meaning" not in event:
            event = admit_widget_event(parsed[event["revision"]], event, log, registry)
        log.append(event)
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
    """Conversation threads by root id, as the panel is handed them."""
    return {thread["root"]["id"]: thread for thread in state["conversation"]["threads"]}


def projected(state: dict, revision: int) -> dict:
    """One revision's document projection, as the runtime applies it."""
    return state["views"][str(revision)]["document"]["projection"]
