"""Verify that leaf.page serves one exact, coherent release in a real browser.

    uv run leaf-dev verify-site [TARGET] [--release RELEASE] [--agent]

The release pass loads three pages, holds each to the release `leaf-dev site` built
(or `--release`), and prints their startup profile. `wrangler` runs it against the
built site through the local Worker and its page container, printing the Worker's log
beside a failure; `.github/workflows/publish-site.yaml` runs it there before deploying
and again against the deployed release.

`--agent` instead sends one private comment through the Threads composer and requires
the hosted Codex task to publish the requested heading and reply. A `startup_failed`
receipt gets one more ask; any other failure receipt fails on the first
(`worker/README.md` owns that contract). It prints the turn's timings to stderr and
one JSON sample on stdout. Without `--release` it takes the release the origin names.
`local` runs the agent pass through the Python adapter against the host's Codex
login, bypassing the Worker, container limits, and credential proxy.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, NamedTuple
from urllib.parse import urlencode, urljoin, urlsplit

import click
import psutil
from playwright.sync_api import APIResponse, BrowserContext, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from leaf_dev import ROOT
from leaf_dev.browser import chrome
from leaf_dev.harness import codex_home, copy_working, environment, run_directory
from leaf_dev.site import asset_site
from leaf_dev.startup import observe_startup as record_startup
from leaf_dev.startup import startup_reading

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

MANIFEST = ROOT / ".tmp" / "site" / "_leaf" / "site.json"
# The site build, run from ROOT, which writes ROOT/.tmp/site (`leaf_dev.site`).
BUILD_SITE = [sys.executable, "-m", "leaf_dev", "site"]
# The website's Python server, as its container runs it (`leaf_website`).
SERVE_SITE = [sys.executable, "-m", "leaf_website"]
VERIFIER_SCRIPT = Path(__file__).with_name("verify_site_browser.js")
PAGES = (
    ("/", "product", True),
    ("/examples/triage-board/", "example", True),
    ("/examples/feature-gallery/versions/v1.html", "example", False),
)


# A turn's wait ends at `TURN_PATIENCE` unless the page says a turn is still working on
# the comment, which holds it to `TURN_LIMIT`. `TURN_LIMIT` bounds the whole pass, so
# raising it means raising `publish-site.yaml`'s `timeout-minutes` too.
TURN_PATIENCE = 300
TURN_LIMIT = 600
TURN_ASKS = 2
# The reload after the turn gets this long to present, then as long again to follow
# the published revision: its container may take seconds to answer the first read.
TURN_PRESENTATION = 120_000
# How long Threads gets to draw a reply the container has admitted; the runtime's own
# quiet-stream bound (`SILENCE_MS` in `runtime/state-feed.js`) is the same 30 s.
VISIBLE_REPLY_PATIENCE = 30_000


class AgentSession(NamedTuple):
    """One user session bound to a container serving the requested release."""

    context: BrowserContext
    page: Page
    failures: list[str]
    url: str
    state_url: str
    state: dict


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def answered(response: APIResponse, url: str) -> APIResponse:
    """Hold one API answer to being an answer, quoting what a refusal said (a Leaf
    fault's body is `{"error": "<class>: <message>"}`)."""
    if not response.ok:
        said = response.text().strip()[:400]
        raise RuntimeError(f"{url} returned {response.status}: {said}")
    return response


def observe_startup(page: Page) -> list[str]:
    """Every verifier page records milestones and the errors that stop reaching them."""
    record_startup(page)
    page.add_init_script(path=VERIFIER_SCRIPT)
    failures: list[str] = []
    page.on(
        "console",
        lambda message: (
            failures.append(message.text) if message.type == "error" else None
        ),
    )
    page.on("pageerror", lambda error: failures.append(str(error)))
    return failures


def await_presentation(
    page, url: str, failures: list[str], timeout: int = 30_000
) -> None:
    """Wait for presentation; a page that never presents names the startup stamps it
    reached (none: upgrade stalled; `upgraded` alone: the first state read did)."""
    try:
        page.locator("body[data-lf-presented]").wait_for(timeout=timeout)
    except PlaywrightTimeout:
        reached = page.evaluate("window.__leafStartup.milestones")
        raise RuntimeError(
            f"{url} never presented, reaching "
            f"{', '.join(reached) or 'no startup milestone'}; browser errors: {failures}"
        ) from None


def activation_url(page_url: str, state: dict) -> str:
    """A canonical private read at the boundary named by passive state."""
    events = state.get("events") or []
    query = urlencode(
        {
            "revision": state["active"]["revision"],
            "through_seq": events[-1]["seq"] if events else 0,
        }
    )
    return urljoin(page_url, f"api/view?{query}")


STILL_STARTING = "was answered before the image rollout reached its container"


def activation_read(context, activation: str) -> APIResponse | None:
    """The read that allocates this session's container, or `None` while it rolls out.

    Until the image rollout reaches the allocated container, the Worker answers `503`
    with `Retry-After` (`worker/README.md`); any other refusal is this release failing.
    """
    response = context.request.get(activation, timeout=120_000)
    if response.status == 503 and response.headers.get("retry-after") is not None:
        return None
    return answered(response, activation)


def host_addresses() -> dict[str, frozenset]:
    """The host's interfaces and their addresses."""
    return {
        name: frozenset((address.family, address.address) for address in addresses)
        for name, addresses in psutil.net_if_addrs().items()
    }


def wait_for_host_network() -> None:
    """Wait for Docker's host interface changes to stop for 2.5 s.

    Chrome and Docker share only this local host: starting a page container adds a host
    interface, and Chromium answers an address change by failing in-flight loads with
    ERR_NETWORK_CHANGED, loopback included.
    """
    previous = host_addresses()
    now = time.monotonic()
    quiet_since = now
    deadline = now + 15
    while now - quiet_since < 2.5:
        check(now < deadline, "host interface addresses did not settle")
        time.sleep(0.1)
        current = host_addresses()
        now = time.monotonic()
        if current != previous:
            previous = current
            quiet_since = now


def verify_page(
    browser,
    path: str,
    kind: str,
    release: str,
    activate: bool,
    *,
    origin: str,
    settle_after_activation: Callable[[], None] | None = None,
) -> dict:
    context = browser.new_context()
    page = context.new_page()
    failures = observe_startup(page)
    url = urljoin(f"{origin}/", path.lstrip("/"))
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/performance")
            and response.request.method == "POST"
        )
    ) as startup_report:
        response = page.goto(url, wait_until="load", timeout=120_000)
        check(response is not None and response.ok, f"{url} did not load")
        await_presentation(page, url, failures)
    check(
        startup_report.value.status == 204,
        f"{url} startup report returned {startup_report.value.status}",
    )

    identity = page.evaluate("window.__leafVerifier.identity")
    check(identity["release"] == release, f"{url} served release {identity['release']}")
    prefix = f"/_leaf-release/{release}/"
    resources = page.evaluate("window.__leafStartup.resourceNames")
    code = [
        resource
        for resource in resources
        if urlsplit(resource).path.endswith((".js", ".css", "registry.json"))
        and urlsplit(resource).netloc == urlsplit(origin).netloc
    ]
    check(code, f"{url} loaded no runtime resources")
    check(
        all(urlsplit(resource).path.startswith(prefix) for resource in code),
        f"{url} loaded unversioned runtime resources: {code}",
    )
    check(
        not any(
            urlsplit(resource).path.endswith("/api/news") for resource in resources
        ),
        f"{url} asked for freshness before interaction",
    )
    secure = urlsplit(origin).scheme == "https"
    identity_cookie = "__Host-leaf-page" if secure else "leaf-page-local"
    cookie_names = {cookie["name"] for cookie in context.cookies()}
    check(
        identity_cookie in cookie_names, f"{url} did not establish one session identity"
    )
    check(
        not any(
            name.startswith(
                (
                    "__Host-leaf-active-",
                    "leaf-active-local-",
                )
            )
            for name in cookie_names
        ),
        f"{url} activated a container before interaction",
    )
    media = page.evaluate("window.__leafVerifier.scopedMedia")
    expected_media = f"{media['root']}/media/0123456789abcdef.png"
    check(
        media["path"] == expected_media,
        f"{url} scoped private media into the release namespace: {media['path']}",
    )
    check(not failures, f"{url} reported browser errors: {failures}")
    startup = startup_reading(page)
    if not activate:
        context.close()
        return startup

    state_url = urljoin(url, "api/state")
    passive_response = answered(
        context.request.get(state_url, timeout=120_000), state_url
    )
    check(
        passive_response.headers.get("leaf-session") == "passive",
        f"{state_url} left the edge before interaction",
    )
    activation = activation_url(url, passive_response.json())
    # No wait here: `publish-site` reruns the whole pass until the release verifies.
    activation_response = activation_read(context, activation)
    check(activation_response is not None, f"{activation} {STILL_STARTING}")
    check(
        activation_response.headers.get("leaf-session") == "active",
        f"{activation} did not activate a private container",
    )
    check(
        isinstance(activation_response.json().get("browser"), dict),
        f"{activation} returned no browser projection",
    )
    if settle_after_activation is not None:
        settle_after_activation()
    state_response = answered(
        context.request.get(
            state_url,
            headers={"Leaf-Layer": identity["layer"], "Leaf-Release": release},
            timeout=120_000,
        ),
        state_url,
    )
    check(
        state_response.headers.get("leaf-session") == "active",
        f"{state_url} did not reach a private container",
    )
    check(
        state_response.headers.get("leaf-release") == release,
        f"{state_url} reached a different container release",
    )
    state = state_response.json()
    check(
        state.get("release") == release, f"{state_url} body belongs to another release"
    )
    check(
        state.get("publication", {}).get("kind") == kind,
        f"{state_url} returned the wrong page kind",
    )
    if path == "/examples/triage-board/":
        neighbor_url = urljoin(f"{origin}/", "how-it-works/")
        neighbor = context.new_page()
        neighbor_failures = observe_startup(neighbor)
        with neighbor.expect_response(
            lambda response: (
                response.url.endswith("/api/performance")
                and response.request.method == "POST"
            )
        ) as neighbor_report:
            neighbor_response = neighbor.goto(
                neighbor_url, wait_until="load", timeout=120_000
            )
            await_presentation(neighbor, neighbor_url, neighbor_failures)
        check(
            neighbor_response is not None and neighbor_response.ok,
            f"{neighbor_url} did not load beside an active page",
        )
        check(
            neighbor_response.headers.get("leaf-session") != "active",
            f"{neighbor_url} inherited another page's private container",
        )
        check(
            neighbor_report.value.status == 204,
            f"{neighbor_url} startup report returned {neighbor_report.value.status}",
        )
        check(
            not neighbor_failures,
            f"{neighbor_url} reported browser errors: {neighbor_failures}",
        )
        neighbor.close()
    context.close()
    return startup


def observed_time(value: float | None) -> str:
    """Render an optional browser milestone without inventing a zero reading."""
    return "not observed" if value is None else f"{value:.0f} ms"


def startup_profile(startup: dict) -> dict:
    """Return browser startup readings in a stable machine-readable shape."""
    presented = startup["presented"]
    return {
        "htmlFirstByteMs": startup["first_byte"],
        "htmlCompleteMs": startup["document"],
        "firstContentfulPaintMs": startup.get("paint", {}).get(
            "first-contentful-paint"
        ),
        "javascriptFetchedMs": presented["js_loaded"],
        "upgradedMs": startup["upgraded"]["at"],
        "stateAnsweredMs": presented["state_loaded"],
        "presentedMs": presented["at"],
        "requestsAtPresentation": presented["requests"],
        "bytesAtPresentation": presented["bytes"],
        "javascriptRequestsAtPresentation": presented["js_requests"],
        "javascriptBytesAtPresentation": presented["js_bytes"],
        "codeRequestsAtPresentation": presented["code_requests"],
        "codeBytesAtPresentation": presented["code_bytes"],
        "layoutShifts": startup["shifts"],
    }


def startup_line(path: str, startup: dict) -> str:
    """Render observed startup costs without turning machine speed into a gate."""
    profile = startup_profile(startup)
    line = (
        f"  {path} — HTML first byte {profile['htmlFirstByteMs']:.0f} ms, "
        f"complete {profile['htmlCompleteMs']:.0f} ms; "
        "first contentful paint "
        f"{observed_time(profile['firstContentfulPaintMs'])}; "
        f"JS fetched {observed_time(profile['javascriptFetchedMs'])}; "
        f"upgraded {profile['upgradedMs']:.0f} ms; "
        f"state answered {observed_time(profile['stateAnsweredMs'])}; "
        f"presented {profile['presentedMs']:.0f} ms; "
        f"by presentation {profile['javascriptRequestsAtPresentation']} JS / "
        f"{profile['javascriptBytesAtPresentation'] / 1024:.0f} KiB, "
        f"{profile['codeRequestsAtPresentation']} code / "
        f"{profile['codeBytesAtPresentation'] / 1024:.0f} KiB, "
        f"{profile['requestsAtPresentation']} total / "
        f"{profile['bytesAtPresentation'] / 1024:.0f} KiB; "
        f"{len(profile['layoutShifts'])} initial layout shifts (diagnostic)"
    )
    for shift in profile["layoutShifts"]:
        sources = []
        for source in shift["sources"]:
            before, after = source["previousRect"], source["currentRect"]
            sources.append(
                f"{source['node']} ({before['x']:g},{before['y']:g} "
                f"{before['width']:g}x{before['height']:g}) → "
                f"({after['x']:g},{after['y']:g} "
                f"{after['width']:g}x{after['height']:g})"
            )
        line += (
            f"\n    {shift['startTime']:.0f} ms {shift['phase']}, "
            f"value {shift['value']:.6g}, recent input {shift['hadRecentInput']}: "
            + "; ".join(sources)
        )
    return line


def verify_cross_tab_activation(browser, *, origin: str) -> None:
    """One interacting tab must wake another tab sharing its browser session."""
    context = browser.new_context()
    url = f"{origin}/examples/triage-board/"
    leader = context.new_page()
    follower = context.new_page()
    for page in (leader, follower):
        failures = observe_startup(page)
        response = page.goto(url, wait_until="load", timeout=120_000)
        check(response is not None and response.ok, f"{url} did not load")
        await_presentation(page, url, failures)
    follower.evaluate("window.__leafVerifier.observeCrossTabActivation")
    leader.evaluate("window.__leafVerifier.activateSession")
    follower.wait_for_function("window.__leafVerifier.crossTabActivated", timeout=5_000)
    context.close()


def served_instead(reached: str | None, release: str) -> str:
    """What an allocation on the wrong release gave back, for the wait reporting it."""
    served = f"release {reached[:8]}" if reached else "no release"
    return f"served {served}, not {release[:8]}"


def user_session(
    browser,
    url: str,
    state_url: str,
    release: str | None,
    *,
    direct_agent: bool = False,
) -> AgentSession | str:
    """One activated user session, or why this allocation cannot admit a turn."""
    context = browser.new_context()
    page = context.new_page()
    failures = observe_startup(page)
    response = page.goto(url, wait_until="load", timeout=120_000)
    check(response is not None and response.ok, f"{url} did not load for its agent")
    await_presentation(page, url, failures)
    passive = answered(context.request.get(state_url, timeout=120_000), state_url)
    if direct_agent:
        reached = passive.headers.get("leaf-release")
        if release is not None and reached != release:
            context.close()
            return served_instead(reached, release)
        return AgentSession(context, page, failures, url, state_url, passive.json())
    activation = activation_url(url, passive.json())
    activated = activation_read(context, activation)
    if activated is None:
        context.close()
        return STILL_STARTING
    check(
        activated.headers.get("leaf-session") == "active",
        f"{activation} did not activate a private container for its agent",
    )
    headers = {"Leaf-Release": release} if release is not None else None
    state_response = answered(
        context.request.get(state_url, headers=headers, timeout=120_000), state_url
    )
    # The edge answers a passive read with the deployed release, so the release header
    # is the container's own only once the session has left the edge.
    check(
        state_response.headers.get("leaf-session") == "active",
        f"{state_url} did not reach a private container for its agent",
    )
    reached = state_response.headers.get("leaf-release")
    if release is not None and reached != release:
        context.close()
        return served_instead(reached, release)
    return AgentSession(context, page, failures, url, state_url, state_response.json())


def agent_session(
    browser, release: str | None, *, origin: str, direct_agent: bool = False
) -> AgentSession:
    """Open one user session whose private container is serving `release`, retrying
    with a fresh context for up to 180 s while the rollout reaches allocations (they
    answer as another release or as the edge's `503`). Nothing here writes."""
    url = f"{origin}/examples/triage-board/"
    state_url = urljoin(url, "api/state")
    deadline = time.monotonic() + 180
    while True:
        session = user_session(
            browser, url, state_url, release, direct_agent=direct_agent
        )
        if isinstance(session, AgentSession):
            return session
        check(
            time.monotonic() < deadline,
            f"{url} reached no container able to admit its agent's turn; "
            f"the last allocation {session}",
        )
        time.sleep(10)


def still_answering(state: dict, event_id: str) -> bool:
    """Whether the page's `activity` says a working turn still owes this comment a
    reply, which a wall clock cannot tell."""
    activity = state.get("activity") or {}
    if activity.get("kind") != "working":
        return False
    return any(
        obligation.get("input") == event_id and not obligation.get("dropped")
        for obligation in activity.get("obligations") or ()
    )


class TurnReading(NamedTuple):
    """What one deployment ask reached before its turn stopped answering it."""

    state: dict
    published: dict | None
    replies: list[dict]
    answer: dict | None


class AgentProfile:
    """Observed milestones for one hosted-agent request, all from its first send."""

    def __init__(self) -> None:
        self.started = time.monotonic()
        self.visible_reply_started_ms: float | None = None
        self.milestones: dict[str, float] = {}
        self.activities: list[tuple[float, str, str]] = []
        self.ask_count = 0
        self.reference: str | None = None
        self.event_ids: list[str] = []

    def mark(self, name: str) -> None:
        self.milestones.setdefault(name, time.monotonic() - self.started)

    def observe(self, state: dict) -> None:
        activity = state.get("activity") or {}
        reading = (activity.get("kind") or "unknown", activity.get("detail") or "")
        if self.activities and self.activities[-1][1:] == reading:
            return
        self.activities.append((time.monotonic() - self.started, *reading))


class AgentAsks(NamedTuple):
    """The reading the pass ended on, with the asks and revision behind it."""

    turn: TurnReading
    asks: int
    revision: int
    profile: AgentProfile


def agent_profile(profile: AgentProfile) -> dict:
    """One comment-to-answer profile, in milliseconds from the first send."""

    def ms(name: str) -> float | None:
        at = profile.milestones.get(name)
        return None if at is None else at * 1000

    return {
        "sessionReference": profile.reference,
        "eventIds": profile.event_ids,
        "asks": profile.ask_count,
        "acknowledgedMs": [
            ms(f"acknowledged {ask}") for ask in range(1, profile.ask_count + 1)
        ],
        "activity": [
            {"atMs": at * 1000, "kind": kind, "detail": detail}
            for at, kind, detail in profile.activities
        ],
        "titledMs": ms("titled"),
        "publishedMs": ms("published"),
        "responseVisibleMs": ms("response visible"),
        "repliedMs": ms("replied"),
        "answeredMs": ms("answered"),
    }


def startup_failed(replies: list[dict]) -> bool:
    """Whether the container settled this ask by reporting a turn that never ran."""
    return any(reply.get("failure") == "startup_failed" for reply in replies)


def turn_failed(replies: list[dict]) -> bool:
    """Whether the host closed the turn with one of its failure receipts."""
    return any("failure" in reply for reply in replies)


def deployment_answer(replies: list[dict]) -> dict | None:
    """Return a real agent reply rather than a host-generated failure receipt."""
    return next((reply for reply in replies if "failure" not in reply), None)


def check_turn_answered(
    url: str, heading: str, turn: TurnReading, asks: int, revision: int
) -> None:
    """Require the turn to have published the heading and answered, reading only what
    the container admitted. A missing publication includes the source-validation
    reading, distinguishing a rejected source from a valid source missing the heading."""
    state, published, replies, answer = turn
    tried = f" to {asks} asks" if asks > 1 else ""
    reading = (state.get("activity") or {}).get("kind") or "no activity"
    said = "; it replied: " + " / ".join(event["text"] for event in replies)
    check(
        published is not None,
        f"{url} agent did not publish ‘{heading}’{tried}; it reached revision "
        f"{state['active']['revision']} from {revision} with the page "
        f"reading {reading}"
        + (said if replies else " and did not reply")
        + f"; source validation: {state['source_error'] or 'no error'}",
    )
    check(
        replies != [],
        f"{url} agent published but did not reply{tried}; the page read {reading}",
    )
    check(
        answer is not None,
        f"{url} agent returned an unexpected reply{tried}{said}",
    )


def start_direct_agent(context, url: str, comment: dict) -> None:
    """Run the local adapter's side of the production Worker dispatch."""
    endpoint = urljoin(url, "_leaf/agent/")
    event = {"event": comment["id"]}
    started = answered(
        context.request.post(urljoin(endpoint, "start"), data=event, timeout=120_000),
        f"{endpoint}start",
    )
    reading = started.json()
    check(
        reading.get("status") in {"started", "settled"},
        f"{endpoint}start returned {reading}",
    )


def read_agent_state(context, state_url: str, layer: str, release: str) -> dict:
    """Read the authoritative state for one activated deployment session."""
    response = answered(
        context.request.get(
            state_url,
            headers={"Leaf-Layer": layer, "Leaf-Release": release},
            timeout=120_000,
        ),
        state_url,
    )
    return response.json()


def ask_for_the_heading(
    context,
    page,
    url: str,
    state_url: str,
    layer: str,
    release: str,
    heading: str,
    profile: AgentProfile,
    ask: int,
    *,
    direct_agent: bool = False,
) -> dict:
    """Send one deployment-check comment through the user's real composer."""
    text = (
        f"Change the main heading to ‘{heading}’. Leave everything else unchanged, "
        "publish the revision, and reply with ‘deployment verified’."
    )
    box = page.locator(".lf-general leaf-text")
    box.focus()
    page.keyboard.insert_text(text)
    if ask == 1:
        profile.started = time.monotonic()
        profile.visible_reply_started_ms = page.evaluate(
            "window.__leafVerifier.startVisibleReplyClock"
        )
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/event") and response.request.method == "POST"
        )
    ) as response_info:
        box.press("ControlOrMeta+Enter")
    posted = response_info.value
    check(posted.ok, f"{url} rejected its deployment-check comment")
    profile.reference = posted.headers.get("leaf-session-reference")
    profile.mark(f"acknowledged {ask}")
    # Read the admitted event from state rather than the intercepted response body,
    # which Playwright can wait on forever once the page has consumed it.
    accepted = read_agent_state(context, state_url, layer, release)
    profile.observe(accepted)
    attempt = posted.request.post_data_json["attempt"]
    comment = next(
        (
            event
            for event in accepted.get("events", [])
            if event.get("attempt") == attempt
        ),
        None,
    )
    check(comment is not None, f"{url} did not return its deployment-check comment")
    profile.event_ids.append(comment["id"])
    if direct_agent:
        start_direct_agent(context, url, comment)
    return comment


def await_turn(
    context,
    url: str,
    state_url: str,
    layer: str,
    release: str,
    comment: dict,
    revision: int,
    heading: str,
    published: dict | None,
    deadline: float,
    profile: AgentProfile,
) -> TurnReading:
    """Read the page until this ask is answered or nothing is answering it."""
    started = time.monotonic()
    replies: list[dict] = []
    answer = None
    current: dict = {}
    while True:
        current = read_agent_state(context, state_url, layer, release)
        profile.observe(current)
        replies = [
            event
            for event in current.get("events", [])
            if event.get("kind") == "reply" and event.get("parent") == comment["id"]
        ]
        if replies:
            profile.mark("replied")
        if any(
            event.get("kind") == "thread_title" and event.get("thread") == comment["id"]
            for event in current.get("events", [])
        ):
            profile.mark("titled")
        answer = deployment_answer(replies)
        active = current["active"]
        if published is None and active["revision"] > revision:
            # The turn may publish a checkpoint first, so read the document for the
            # heading rather than taking the first new revision.
            document = context.request.get(urljoin(url, active["url"]), timeout=120_000)
            if document.ok and heading in document.text():
                published = active
                profile.mark("published")
        if published is not None and answer is not None:
            profile.mark("answered")
            break
        # A host failure receipt closes the turn; otherwise either half of a success
        # can arrive first, so one waits for the other.
        if turn_failed(replies):
            break
        if time.monotonic() >= deadline:
            break
        waited = time.monotonic() - started
        if waited >= TURN_PATIENCE and not still_answering(current, comment["id"]):
            break
        time.sleep(2)
    return TurnReading(current, published, replies, answer)


def ask_until_answered(
    context,
    page,
    url: str,
    state_url: str,
    layer: str,
    release: str,
    heading: str,
    state: dict,
    *,
    direct_agent: bool = False,
) -> AgentAsks:
    """Ask the deployed agent for `heading` until it answers or stops answering.

    A `startup_failed` receipt is retried once while a healthy turn's budget remains;
    any other receipt, or a turn that stops without answering, ends the pass.
    """
    published = None
    asks = 0
    profile = AgentProfile()
    deadline = time.monotonic() + TURN_LIMIT
    while True:
        asks += 1
        profile.ask_count = asks
        # A second ask continues the revision the first left, and keeps what it
        # published.
        revision = state["active"]["revision"]
        comment = ask_for_the_heading(
            context,
            page,
            url,
            state_url,
            layer,
            release,
            heading,
            profile,
            asks,
            direct_agent=direct_agent,
        )
        state, published, replies, answer = await_turn(
            context,
            url,
            state_url,
            layer,
            release,
            comment,
            revision,
            heading,
            published,
            deadline,
            profile,
        )
        if answer is not None or not (
            asks < TURN_ASKS
            and startup_failed(replies)
            and deadline - time.monotonic() >= TURN_PATIENCE
        ):
            return AgentAsks(
                TurnReading(state, published, replies, answer),
                asks,
                revision,
                profile,
            )
        print(
            f"↻ {url} settled its ask with a startup failure; sending one new message",
            file=sys.stderr,
        )


def wait_for_visible_reply(page, parent: str) -> bool:
    """Open an answered thread's held news, then require its reply on screen."""
    try:
        page.wait_for_function(
            """parent => window.__leafVerifier.visibleReplyRecorded() ||
              [...document.querySelectorAll('.lf-threads > .lf-thread')].some(
                thread => thread.dataset.id === parent &&
                  [...thread.querySelectorAll('.lf-thread-news')].some(
                    notice => notice.checkVisibility()))""",
            arg=parent,
            timeout=VISIBLE_REPLY_PATIENCE,
        )
        if not page.evaluate("window.__leafVerifier.visibleReplyRecorded"):
            page.locator(
                f'.lf-threads > .lf-thread[data-id="{parent}"] .lf-thread-news'
            ).click()
            page.wait_for_function(
                "window.__leafVerifier.visibleReplyRecorded",
                timeout=VISIBLE_REPLY_PATIENCE,
            )
    except PlaywrightTimeout:
        return False
    return True


def verify_agent_turn(
    browser,
    release: str | None,
    *,
    origin: str,
    direct_agent: bool = False,
) -> dict:
    """Require one deployed Codex turn to publish `heading` on a private page and reply.

    The heading checks are containments: the agent may quote the heading, and the
    runtime may add its own words to pointable text.
    """
    context, page, failures, url, state_url, state = agent_session(
        browser, release, origin=origin, direct_agent=direct_agent
    )
    initial_startup = startup_reading(page)
    if release is None:
        release = state.get("release")
        check(isinstance(release, str), f"{state_url} returned no release")
    # The comment is posted under the layer its own container holds, not the edge's.
    layer = state["layer"]["generation"]
    heading = f"Deployment {release[:8]} verified"
    page.locator(".lf-threads-toggle").click()
    turn, asks, revision, profile = ask_until_answered(
        context,
        page,
        url,
        state_url,
        layer,
        release,
        heading,
        state,
        direct_agent=direct_agent,
    )
    check_turn_answered(url, heading, turn, asks, revision)
    published, answer = turn.published, turn.answer
    reply_visible = wait_for_visible_reply(page, answer["parent"])
    visible_reply_at = page.evaluate("window.__leafVerifier.visibleReplyAt")
    if visible_reply_at is not None:
        profile.milestones["response visible"] = (
            visible_reply_at - profile.visible_reply_started_ms
        ) / 1000
    print(json.dumps(agent_profile(profile), indent=2), file=sys.stderr)
    if not reply_visible or visible_reply_at is None:
        debug = page.evaluate("window.__leafVerifier.visibleReplyDebug")
        raise RuntimeError(
            f"{url} reply never became visible in Threads after opening its "
            f"held news; the answer was read out of "
            f"{turn.state['reading']}, and the page reports {json.dumps(debug)}"
        )
    reloaded = page.reload(wait_until="load", timeout=120_000)
    check(
        reloaded is not None and reloaded.ok,
        f"{url} did not reload after its agent turn",
    )
    await_presentation(page, url, failures, timeout=TURN_PRESENTATION)
    startup = startup_reading(page)
    # The runtime presents without waiting for its first read, which is what brings
    # the revision back, so that follow gets its own wait and its own timing.
    followed_at = time.monotonic()
    try:
        page.wait_for_function(
            "window.__leafVerifier.revisionAtLeast",
            arg=published["revision"],
            timeout=TURN_PRESENTATION,
        )
    except PlaywrightTimeout:
        pass
    followed_in = (time.monotonic() - followed_at) * 1000
    # After the wait, so an error on the way there is reported rather than the
    # revision it never reached.
    check(not failures, f"{url} reported browser errors: {failures}")
    shown = page.evaluate("window.__leafVerifier.revision")
    # The banner separates a page whose first read answered with an old revision from
    # one that presented offline and was never told.
    banner = page.evaluate("window.__leafVerifier.status")
    check(
        (shown or "").isdigit() and int(shown) >= published["revision"],
        f"{url} stands on revision {shown} rather than following the published "
        f"{published['revision']}, with the banner reading ‘{banner}’",
    )
    rendered = page.locator("h1").inner_text()
    check(
        heading in rendered,
        f"{url} rendered ‘{rendered}’ rather than the agent's published ‘{heading}’",
    )
    print(
        f"✓ hosted agent published revision {published['revision']} and replied: "
        f"{answer['text']}; the reloaded page followed it {followed_in:.0f} ms "
        "after presentation",
        file=sys.stderr,
    )
    result = {
        "origin": origin,
        "release": release,
        "page": startup_profile(initial_startup),
        "comment": agent_profile(profile),
        "change": {
            "heading": heading,
            "revision": published["revision"],
            "reply": answer["text"],
        },
        "changedPage": {
            **startup_profile(startup),
            "followedRevisionMs": followed_in,
        },
    }
    context.close()
    return result


def answers(url: str) -> bool:
    """Whether `url` answers with a success status now."""
    try:
        with urllib.request.urlopen(url, timeout=1):
            return True
    except (urllib.error.URLError, TimeoutError):
        return False


def announced_origin(log: Path, event: str) -> str | None:
    """Read the bound address the child published, never a guessed free port."""
    for line in log.read_text().splitlines(keepends=True):
        if not line.endswith("\n") or not line.startswith("{"):
            continue
        record = json.loads(line)
        if record.get("event") == event:
            return f"http://127.0.0.1:{record['port']}"
    return None


@contextmanager
def logged(log: Path) -> Iterator[IO[str]]:
    """Collect a local server's output in `log`, printing it beside any failure."""
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as output:
        try:
            yield output
        except BaseException:
            output.flush()
            sys.stderr.write(log.read_text())
            raise


@contextmanager
def serving(
    command: list[str],
    output: IO[str],
    ready: Callable[[], bool],
    patience: float,
    **popen,
) -> Iterator[None]:
    """Run one local server until the block ends, once `ready` says it is serving."""
    with subprocess.Popen(
        command, stdout=output, stderr=subprocess.STDOUT, **popen
    ) as server:
        try:
            deadline = time.monotonic() + patience
            while not ready():
                check(server.poll() is None, f"{command[0]} exited before serving")
                check(time.monotonic() < deadline, f"{command[0]} did not serve")
                time.sleep(0.1)
            yield
        finally:
            if server.poll() is None:
                server.terminate()
            server.wait()


@contextmanager
def local_adapter():
    """Build the site and serve it with the website adapter under a temporary copy of
    the host's Codex login, removed with the adapter's pages and task history."""
    out = run_directory(ROOT / ".tmp" / "verify-site")
    log = out / "website-agent-local.log"
    origin = None

    def ready():
        nonlocal origin
        origin = announced_origin(log, "container_http_ready")
        return origin is not None and answers(f"{origin}/health")

    with (
        tempfile.TemporaryDirectory(prefix="leaf-site-agent.") as temporary,
        logged(log) as output,
    ):
        root = Path(temporary)
        site = root / "site"
        home = codex_home(
            root / "codex-home",
            (ROOT / "worker" / "codex-config.toml").read_text(),
        )
        subprocess.run(
            [*BUILD_SITE, "--output", str(site)],
            cwd=ROOT,
            stdout=output,
            stderr=subprocess.STDOUT,
            check=True,
        )
        release = json.loads((site / "_leaf" / "site.json").read_text())["release"]
        with serving(
            [*SERVE_SITE, "--port", "0"],
            output,
            ready,
            30,
            cwd=ROOT,
            env=environment(
                CODEX_HOME=str(home),
                LEAF_SITE_ROOT=str(site),
                XDG_STATE_HOME=str(root / "state"),
            ),
        ):
            yield origin, release


@contextmanager
def local_worker() -> Iterator[tuple[str, str]]:
    """Serve the built site through `wrangler dev`: the Worker and its page container.

    The patience covers building the container image. Wrangler leaves each container's
    `proxy-everything` sidecar running when it exits, so the run serves under a Worker
    name of its own and removes the containers carrying it on the way out.
    """
    out = run_directory(ROOT / ".tmp" / "verify-site")
    name = f"lv-{out.name}"
    log = out / "wrangler-dev.log"
    origin = None

    def ready():
        nonlocal origin
        origin = announced_origin(log, "local_worker_ready")
        return origin is not None and answers(f"{origin}/")

    try:
        with (
            tempfile.TemporaryDirectory(prefix="leaf-worker-") as temporary,
            logged(log) as output,
        ):
            root = Path(temporary)
            # Freeze both halves of this release. Docker must build from the same
            # private site the edge serves, even if another run rebuilds .tmp/site.
            context = root / "context"
            copy_working(
                [
                    "Dockerfile.website",
                    "pyproject.toml",
                    "uv.lock",
                    "skills/leaf",
                    "worker/pyproject.toml",
                    "worker/leaf_website",
                    "worker/package.json",
                    "worker/package-lock.json",
                    "worker/codex-config.toml",
                ],
                context,
            )
            from leaf.state import flocked

            with flocked(MANIFEST.parents[1].with_name("site.lock")):
                shutil.copytree(MANIFEST.parents[1], context / ".tmp" / "site")
                shutil.copytree(asset_site(MANIFEST.parents[1]), root / "assets")
            release = json.loads(
                (context / ".tmp" / "site" / "_leaf" / "site.json").read_text()
            )["release"]
            config = tomllib.loads((ROOT / "worker" / "wrangler.toml").read_text())
            config.pop("env")
            config["name"] = name
            config["main"] = str(ROOT / "worker" / "src" / "index.ts")
            config["assets"]["directory"] = str(root / "assets")
            config["vars"]["AGENT_PREWARM"] = "false"
            for container in config["containers"]:
                container["image"] = str(context / "Dockerfile.website")
                container["image_build_context"] = str(context)
            config_path = root / "wrangler.json"
            config_path.write_text(json.dumps(config))
            with serving(
                [
                    "node",
                    str(Path(__file__).with_name("wrangler_server.mjs")),
                    str(ROOT),
                    str(config_path),
                    str(root / "state"),
                ],
                output,
                ready,
                180,
                cwd=ROOT / "worker",
            ):
                yield origin, release
    finally:
        listed = subprocess.run(
            ["docker", "ps", "--quiet", "--filter", f"name=^workerd-{name}-"],
            capture_output=True,
            text=True,
            check=True,
        )
        if started := listed.stdout.split():
            subprocess.run(
                ["docker", "rm", "--force", *started],
                stdout=subprocess.DEVNULL,
                check=True,
            )


def built_release() -> str:
    """The release `leaf-dev site` last built."""
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["release"]


@click.command()
@click.argument("target", default="https://leaf.page")
@click.option(
    "--release",
    help="Require this release (default: the one `leaf-dev site` built; with "
    "`--agent` at an origin, whichever it serves). `local` checks its own build.",
)
@click.option(
    "--agent",
    is_flag=True,
    help="Verify one agent edit and reply instead of the release boundary.",
)
def verify_site(target: str, release: str | None, agent: bool) -> None:
    """Verify a release at TARGET, or run the agent journey there with `--agent`.

    TARGET is an origin, `wrangler` for the built site through the local Worker, or
    `local` for the agent journey through the Python adapter alone.
    """
    if target == "local":
        with local_adapter() as (origin, built):
            run_verification(origin, built, agent=True, direct_agent=True)
        return
    if target == "wrangler":
        with local_worker() as (origin, built):
            run_verification(
                origin,
                release or built,
                agent=agent,
                settle_after_activation=None if agent else wait_for_host_network,
            )
        return
    if not agent:
        release = release or built_release()
    run_verification(target.rstrip("/"), release, agent=agent)


def run_verification(
    origin: str,
    release: str | None,
    *,
    agent: bool,
    direct_agent: bool = False,
    settle_after_activation: Callable[[], None] | None = None,
) -> None:
    """Run the release pass, or with `agent` the agent pass, against `origin`."""
    with chrome() as browser:
        if agent:
            result = verify_agent_turn(
                browser, release, origin=origin, direct_agent=direct_agent
            )
            print(json.dumps(result, indent=2))
            return
        print("Leaf startup profile (observed, not a pass/fail budget):", flush=True)
        for path, kind, activate in PAGES:
            profile = verify_page(
                browser,
                path,
                kind,
                release,
                activate,
                origin=origin,
                settle_after_activation=settle_after_activation,
            )
            print(startup_line(path, profile), flush=True)
        verify_cross_tab_activation(browser, origin=origin)
    print(f"✓ {origin} serves release {release}")
