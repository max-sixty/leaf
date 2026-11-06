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

The hook used to tell the agent to run `leaf server start` instead, which left the
user's tab without a server until the agent acted. Of 18 Claude Code sessions told
over 20 days, 6 acted at their next tool call and 4 never did.
"""

from pathlib import Path

from .event_log import initialized
from .findings import Finding
from .harness import HOOK_TIMEOUT_S, Harness
from .refusals import Refused
from .schema import PREVIEW_FILE
from .service import claim_is_active, claim_records, prepare_claim

# How long the prompt waits for each page's server. A start takes under a second.
# One waiting on a port another process holds is refused at this bound and tried
# again at the next prompt, which still leaves the hook time to hand the turn its
# input inline (`hook_transport.CONFIRM_WITHIN`).
SERVE_WITHIN = HOOK_TIMEOUT_S / 4


def serve_again(harness: Harness) -> list[Finding]:
    """Serve each page `harness`'s session still means to serve whose ownership or
    server is down, and say what kept any of them from serving."""
    pages = to_serve(harness)
    if not pages:
        # Most prompts, which load no page servers.
        return []
    from .hosting import claim_and_start
    from .vendoring import renew_layer

    found = []
    for page_dir in pages:
        if unready := renew_layer(page_dir, harness, command=False):
            found.append(unready)
        try:
            prepared = prepare_claim(harness, page_dir)
            with (
                harness.preparing_delivery(),
                claim_and_start(
                    page_dir, prepared_claim=prepared, timeout=SERVE_WITHIN
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


def to_serve(harness: Harness) -> list[Path]:
    """The pages `harness`'s session still means to serve whose ownership or server
    is down, by the rules the module header gives."""
    from .server import read_service, running_server

    pages = []
    for claim in claim_records(harness.session):
        page_dir = Path(claim["page"])
        if (
            claim["harness"] != harness.name
            or (page_dir / PREVIEW_FILE).exists()
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
