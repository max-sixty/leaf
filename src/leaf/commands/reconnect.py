"""Serve again the pages a session still means to serve, as its next prompt opens.

A resumed session holds the claims its earlier process made, which name a lifetime
that has ended, and the servers of those pages retired with it; a server can also die
under a session that lives on. Either way the user's tab has no server. So the prompt
hook takes back and serves each such page for its session as `leaf server start`
would: it renews the page's layer (`vendoring.renew_layer`), prepares the harness's
delivery and starts the server under a new claim (`hosting.claim_and_start`). It does
this before the prompt opens the turn and before it reads the session's pages, so the
turn joins the generation the claim starts (`state.ensure_session`) and the input
waiting on a page reaches that same turn. The agent hears only of a page that did
not start, and why, and each prompt tries again while the page's service stays
enabled. A renewal for a session no longer live stops the service
(`hosting.restarting_server`), and only the start re-enables it, so a page whose
start then fails waits for the agent's own `leaf server start`.

A page qualifies while its last claim names this session under this harness, it is
initialized and carries no `preview.json`, its service is enabled with a session
lifetime, and its ownership or its server is down. That leaves out a page the agent
stopped or released, a persistent service, a preview, which its own command serves,
a page another session took, and a page never served.

Only the prompt hook serves pages here. A session's start opens no turn, and a claim
in a session with no live generation would open one; a resumed session's first
prompt follows. Between turns the watch revives a dead server once for each page it
watches (`session.Watch`), and the next prompt tries again where that failed.

Telling the agent to run `leaf server start` instead leaves the user's tab without
a server until the agent acts, which an agent can put off or never do.

A page whose server still runs in the grace its earlier session left it keeps that
server, whichever copy started it. Once the page's claim is live again, the server
itself moves to the Leaf the session's hooks run
(`server_lifetime.stop_when_service_ends`).
"""

import time
from pathlib import Path

from leaf.base.findings import Finding
from leaf.base.harness import Harness
from leaf.base.refusals import Refused
from leaf.base.schema import PREVIEW_FILE
from leaf.base.service import PREVIEW, claim_is_active, claim_records, prepare_claim
from leaf.log.event_log import initialized


def serve_again(harness: Harness, started: float) -> list[Finding]:
    """Serve each page `harness`'s session still means to serve whose ownership or
    server is down, and say what kept any of them from serving.

    The starts share the hook's one deadline, `CONFIRM_WITHIN` after `started`, its
    `time.monotonic()` as it began. A start takes about a second, or several on a
    loaded machine, and one not ready and confirmed by the deadline is refused, so
    the hook exits inside its timeout; a start that took the time the hook had to
    hand over input inline leaves that input to a pointer instead
    (`hook_transport`). A port another process holds refuses at once
    (`hosting.listening_socket`)."""
    found = []
    if pages := to_serve(harness):
        from leaf.pages.hosting import claim_and_start, preparing_delivery
        from leaf.pages.vendoring import renew_layer

        deadline = _deadline(started)
        for page_dir in pages:
            if unready := renew_layer(page_dir, harness):
                found.append(unready)
            try:
                if time.monotonic() >= deadline:
                    raise Refused("the prompt had no time left to start it")
                prepared = prepare_claim(harness, page_dir)
                with (
                    preparing_delivery(harness),
                    claim_and_start(
                        page_dir, prepared_claim=prepared, deadline=deadline
                    ),
                ):
                    pass
            except Refused as error:
                found.append(
                    Finding(
                        "revive-refused",
                        values={"page": str(page_dir), "error": str(error)},
                    )
                )
    return found


def _deadline(started: float) -> float:
    """When the prompt hook's starts must be ready and confirmed, given its
    `time.monotonic()` as it began (`serve_again`)."""
    from leaf.commands.hook_transport import CONFIRM_WITHIN

    return started + CONFIRM_WITHIN


def to_serve(harness: Harness) -> list[Path]:
    """The pages `harness`'s session still means to serve whose ownership or server
    is down, by the rules the module header gives."""
    from leaf.base.server import read_service, running_server

    pages = []
    for claim in claim_records(harness.session):
        page_dir = Path(claim["page"])
        if (
            claim["harness"] != harness.name
            or PREVIEW.file(page_dir / PREVIEW_FILE).exists()
            or not initialized(page_dir)
        ):
            continue
        service = read_service(page_dir)
        if (
            service is not None
            and service["enabled"]
            and service["lifetime"] == "session"
            and not (claim_is_active(claim) and running_server(page_dir) is not None)
        ):
            pages.append(page_dir)
    return pages
