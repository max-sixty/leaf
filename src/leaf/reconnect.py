"""Serve again the pages a session still means to serve, and restart those another
installed Leaf serves, as its next prompt opens.

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

A session whose hooks run an installed update (`session-lifetime.md`, "Which Leaf
runs a session") reads `page check` from it, while a page's server another copy
started goes on running that copy, so what the user's tab draws may differ from what
the agent checked. Claude Code installs each update as a copy at a new path, so a
session it moves onto the update leaves its servers on the old copy. So once the
prompt has served pages again, it restarts the server of each page the session holds
that another installed Leaf started, where the hook runs an installed copy too
(`state.installed_copy`). It finds another Leaf by the test `leaf server start` makes
(`server.other_serving_leaf`), and restarts the server as that command does, at the
same address (`hosting.restarting_server`). A server from a copy Codex or Pi updates
in place has the update restart it within seconds (`server.stop_when_service_ends`).
A server that did not follow, because its copy changed while it was starting or the
update refused to restart it, reads to the same test as the same copy at another
commit, so the prompt restarts it.

As that command does, the hook first asks whether this Leaf can serve the page, as a
fresh bind decides it (`http.page_endpoint`), and leaves a page it can't serve to the
copy serving it. A page at an older protocol fails that test; the hook's reading of
the page renews it, which restarts its server (`hook_transport.read_plans`,
`vendoring.renew_layer`). A restart takes a working server down before it starts
the new one, so the hook begins one only while `RESTART_NEEDS` of its deadline is
left, and leaves the rest to a later prompt, with the other copy serving the page
meanwhile. The agent hears of a server that did not start again. A hook from an
installed copy reads each held page's service record and server lease; one from a
checkout reads nothing more.

The maintainer chose to restart only a server an installed copy started, and only
from an installed copy's hook. Restarting a checkout's server too would replace a
server someone started from a checkout, such as a preview or a trial of a change,
with the installed copy; restarting from a checkout's hook would move the session's
pages onto that checkout. Whether a checkout should move a session's pages at all
(`session_runtime.select_checkout`) is a question the maintainer has left open, and
this rule holds whichever way it is settled. The rule governs the restarts a hook
makes. A server that follows an update of its own installed copy is restarted by
the copy at that same path, and only that server is (`hosting.follow_copy`), so the
follow keeps the rule's purpose: it replaces no checkout's server and moves no page
onto a checkout.
"""

import time
from pathlib import Path

from .event_log import initialized
from .findings import Finding
from .harness import Harness
from .refusals import Refused
from .schema import PREVIEW_FILE
from .service import claim_is_active, claim_records, claimant_matches, prepare_claim
from .state import PLUGIN_ROOT, installed_copy

# How much of the hook's deadline a restart needs left to begin: the old server
# notices its stop within the 2 s between its lifetime checks
# (`server.stop_when_service_ends`), and the new one starts in about a second, or
# several on a loaded machine.
RESTART_NEEDS = 5.0


def serve_again(harness: Harness, started: float) -> list[Finding]:
    """Serve each page `harness`'s session still means to serve whose ownership or
    server is down, then restart each it holds whose server another installed Leaf
    started (`to_restart`), and say what kept any of them from serving.

    The starts share the hook's one deadline, `CONFIRM_WITHIN` after `started`, its
    `time.monotonic()` as it began. A start takes about a second, or several on a
    loaded machine, and one not ready and confirmed by the deadline is refused, so
    the hook exits inside its timeout; a start that took the time the hook had to
    hand over input inline leaves that input to a pointer instead
    (`hook_transport`). A port another process holds refuses at once
    (`hosting.listening_socket`). A restart begins only with `RESTART_NEEDS` left.
    The restarts come after the serves, since a serve keeps a server still running
    through the grace its earlier session left it, whichever copy started it."""
    found = []
    if pages := to_serve(harness):
        from .hosting import claim_and_start
        from .vendoring import renew_layer

        deadline = _deadline(started)
        for page_dir in pages:
            if unready := renew_layer(page_dir, harness, command=False):
                found.append(unready)
            try:
                if time.monotonic() >= deadline:
                    raise Refused("the prompt had no time left to start it")
                prepared = prepare_claim(harness, page_dir)
                with (
                    harness.preparing_delivery(),
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
    if pages := to_restart(harness):
        from .hosting import check_servable, restarting_server

        deadline = _deadline(started)
        for page_dir in pages:
            if deadline - time.monotonic() < RESTART_NEEDS:
                break
            try:
                check_servable(page_dir)
            except Refused:
                # This Leaf can't serve the page, so the copy serving it goes on.
                continue
            try:
                with restarting_server(page_dir, harness, deadline=deadline):
                    pass
            except Refused as error:
                found.append(
                    Finding(
                        "restart-refused",
                        values={"page": str(page_dir), "error": str(error)},
                    )
                )
    return found


def _deadline(started: float) -> float:
    """When the prompt hook's starts must be ready and confirmed, given its
    `time.monotonic()` as it began (`serve_again`)."""
    from .hook_transport import CONFIRM_WITHIN

    return started + CONFIRM_WITHIN


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


def to_restart(harness: Harness) -> list[Path]:
    """The pages `harness`'s session holds whose running server another installed
    Leaf started, where this Leaf is an installed copy too, by the rules the module
    header gives."""
    if not installed_copy(PLUGIN_ROOT):
        return []
    from .server import other_serving_leaf

    pages = []
    for claim in claim_records(harness.session):
        page_dir = Path(claim["page"])
        if not (claimant_matches(claim, harness) and claim_is_active(claim)):
            continue
        served = other_serving_leaf(page_dir)
        if served is not None and installed_copy(Path(served["path"])):
            pages.append(page_dir)
    return pages
