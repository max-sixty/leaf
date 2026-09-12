#!/usr/bin/env python3
"""Verify that leaf.page serves one exact, coherent release in a real browser."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlencode, urljoin, urlsplit

import click
from leaf.render_gate.browser import launch_browser
from playwright.sync_api import BrowserContext, Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".tmp" / "site" / "_leaf" / "site.json"
VERIFIER_SCRIPT = ROOT / "scripts" / "verify-site-browser.js"
PAGES = (
    ("/", "product", True),
    ("/examples/triage-board/", "example", True),
    ("/examples/feature-gallery/versions/v1.html", "example", False),
)


# One hosted Codex turn runs at the model's pace, not this gate's. `TURN_PATIENCE`
# is the budget a turn observed healthy has finished well inside, and it bounds one
# ask; `TURN_LIMIT` is the far end, past which no reading the page offers is worth
# waiting on, and it bounds the whole pass however many asks that takes. What holds
# that tail is the `timeout-minutes` of `.github/workflows/publish-site.yaml`'s job,
# behind the release wait that runs ahead of this pass, so raising `TURN_LIMIT` is a
# change there too. Between the two bounds the page's own `activity` reading decides,
# because a stopwatch cannot tell a turn that is still working from one that has
# stopped.
TURN_PATIENCE = 300
TURN_LIMIT = 600
# How long the page reloaded after the turn gets to reach each of its two gates. It must
# first present; the release pass's ordinary bound is calibrated for pages the edge
# serves in about a second, while this container-backed reload may spend ten seconds at
# the runtime's own presentation wait. Presentation does not mean that the first state
# read has answered, so the same patience then lets that read activate the revision the
# agent published. If it expires, the revision check reports what the page says about
# the read. This second wait starts after presentation, so it outlasts the runtime's
# first-read bound and samples only after that read has ended.
TURN_PRESENTATION = 120_000
# The activity readings that mean a turn is on this work. A page that reads away,
# unheld, listening, stalled or closed is not going to answer, so its wait ends at
# `TURN_PATIENCE` rather than running out the limit.
ANSWERING = frozenset({"queued", "handling", "working"})
TURN_ASKS = 2


class AgentSession(NamedTuple):
    """One reader session bound to a container serving the requested release."""

    context: BrowserContext
    page: Page
    failures: list[str]
    url: str
    state_url: str
    state: dict


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def unpresented(url: str, reached: list[str], failures: list[str]) -> str:
    """What a page that never presented has to say for the next reader of a red run.

    Presentation is every later check's precondition, so the timeout is where this
    gate stops, and the run log has held only the wait's own traceback: not the page
    that stalled, and not how far it got. The browser verifier records each
    startup stamp as it lands, and the two stamps separate the two ways to stall —
    an upgrade that never settled leaves none, while a first state read that never
    answered leaves `upgraded` standing alone.
    """
    milestones = ", ".join(reached) if reached else "no startup milestone"
    reported = f"; browser errors: {failures}" if failures else ""
    return f"{url} never presented, reaching {milestones}{reported}"


def observe_startup(page: Page) -> list[str]:
    """Every verifier page records milestones and the errors that stop reaching them."""
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
    try:
        page.locator("body[data-lf-presented]").wait_for(timeout=timeout)
    except PlaywrightTimeout:
        reached = page.evaluate("window.__leafVerifier.startupMilestones")
        raise RuntimeError(unpresented(url, reached, failures)) from None


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


def verify_page(
    browser, path: str, kind: str, release: str, activate: bool, *, origin: str
) -> dict:
    context = browser.new_context()
    page = context.new_page()
    failures = observe_startup(page)
    url = urljoin(f"{origin}/", path.lstrip("/"))
    response = page.goto(url, wait_until="load", timeout=120_000)
    check(response is not None and response.ok, f"{url} did not load")
    await_presentation(page, url, failures)

    identity = page.evaluate("window.__leafVerifier.identity")
    check(identity["release"] == release, f"{url} served release {identity['release']}")
    prefix = f"/_leaf-release/{release}/"
    resources = page.evaluate("window.__leafVerifier.resourceNames")
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
        f"{url} opened a news stream before interaction",
    )
    secure = urlsplit(origin).scheme == "https"
    identity_cookie = "__Host-leaf-page" if secure else "leaf-page-local"
    cookie_names = {cookie["name"] for cookie in context.cookies()}
    check(
        identity_cookie in cookie_names, f"{url} did not establish one session identity"
    )
    check(
        not cookie_names.intersection(
            {
                "__Host-leaf-active",
                "leaf-active-local",
                "__Host-leaf-container",
                "leaf-container-local",
            }
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
    startup = page.evaluate("window.__leafVerifier.startupReading")
    if not activate:
        context.close()
        return startup

    state_url = urljoin(url, "api/state")
    passive_response = context.request.get(state_url, timeout=120_000)
    check(passive_response.ok, f"{state_url} returned {passive_response.status}")
    check(
        passive_response.headers.get("leaf-session") == "passive",
        f"{state_url} left the edge before interaction",
    )
    activation = activation_url(url, passive_response.json())
    activation_response = context.request.get(activation, timeout=120_000)
    check(
        activation_response.ok,
        f"{activation} returned {activation_response.status}",
    )
    check(
        activation_response.headers.get("leaf-session") == "active",
        f"{activation} did not activate a private container",
    )
    check(
        isinstance(activation_response.json().get("browser"), dict),
        f"{activation} returned no browser projection",
    )
    state_response = context.request.get(
        state_url,
        headers={"Leaf-Layer": identity["layer"], "Leaf-Release": release},
        timeout=120_000,
    )
    check(state_response.ok, f"{state_url} returned {state_response.status}")
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
    }


def startup_line(path: str, startup: dict) -> str:
    """Render observed startup costs without turning machine speed into a gate."""
    profile = startup_profile(startup)
    return (
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
        f"{profile['bytesAtPresentation'] / 1024:.0f} KiB"
    )


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


def reader_session(
    browser,
    url: str,
    state_url: str,
    release: str | None,
    *,
    direct_agent: bool = False,
) -> AgentSession | str:
    """One activated reader session, or the release its container served instead."""
    context = browser.new_context()
    page = context.new_page()
    failures = observe_startup(page)
    response = page.goto(url, wait_until="load", timeout=120_000)
    check(response is not None and response.ok, f"{url} did not load for its agent")
    await_presentation(page, url, failures)
    passive = context.request.get(state_url, timeout=120_000)
    check(passive.ok, f"{state_url} returned {passive.status}")
    if direct_agent:
        reached = passive.headers.get("leaf-release")
        if release is not None and reached != release:
            context.close()
            return reached or "no release"
        return AgentSession(context, page, failures, url, state_url, passive.json())
    activation = activation_url(url, passive.json())
    activated = context.request.get(activation, timeout=120_000)
    check(activated.ok, f"{activation} returned {activated.status}")
    check(
        activated.headers.get("leaf-session") == "active",
        f"{activation} did not activate a private container for its agent",
    )
    headers = {"Leaf-Release": release} if release is not None else None
    state_response = context.request.get(state_url, headers=headers, timeout=120_000)
    check(state_response.ok, f"{state_url} returned {state_response.status}")
    # The edge answers a passive `api/state` with the deployed release whatever the
    # containers run, so the release below reads as this container's own only once
    # the session is known to have left the edge.
    check(
        state_response.headers.get("leaf-session") == "active",
        f"{state_url} did not reach a private container for its agent",
    )
    reached = state_response.headers.get("leaf-release")
    if release is not None and reached != release:
        context.close()
        return reached or "no release"
    return AgentSession(context, page, failures, url, state_url, state_response.json())


def agent_session(
    browser, release: str | None, *, origin: str, direct_agent: bool = False
) -> AgentSession:
    """Open one reader session whose private container is serving `release`.

    The Worker keys a container on the reader session alone, so a session that lands
    on a draining allocation stays on that image for its whole life; only a fresh
    session can reach a different one. The page checks answer for their own sessions
    rather than for this one, and the edge answers a passive `api/state` out of the
    built site whatever the containers are running — so neither establishes the
    container that has to admit this turn's comment. This does, by activating a
    session and reading the release back out of an answer the container itself gave,
    and it takes a fresh session while a rollout drains. Nothing here writes: the
    turn is posted once, afterwards.
    """
    url = f"{origin}/examples/triage-board/"
    state_url = urljoin(url, "api/state")
    # The release verification ahead of this pass already waited out most of the
    # rollout, so this is the tail of a drain rather than the drain, and this wait
    # plus the turn's `TURN_LIMIT` still has to sit inside the job's own budget.
    deadline = time.monotonic() + 180
    while True:
        session = reader_session(
            browser, url, state_url, release, direct_agent=direct_agent
        )
        if isinstance(session, AgentSession):
            return session
        check(release is not None, f"{url} returned no active release")
        check(
            time.monotonic() < deadline,
            f"{url} reached no container serving release {release[:8]} for its "
            f"agent; the last allocation served {session[:8]}",
        )
        time.sleep(10)


def still_answering(state: dict, event_id: str) -> bool:
    """Whether the page itself says a live agent turn still owes this comment a reply.

    `activity` is the one reading Leaf derives for every consumer of agent state, and
    it answers the question a wall clock cannot: an obligation that is still standing
    says nothing has answered the comment, and the reading beside it says whether
    anything is going to. So the gate consumes it rather than deciding locally that a
    turn past its budget has failed.
    """
    activity = state.get("activity") or {}
    if activity.get("kind") not in ANSWERING:
        return False
    return any(
        obligation.get("event") == event_id and not obligation.get("dropped")
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


def elapsed_time(seconds: float) -> str:
    """Format one observed interval at a useful scale."""
    return f"{seconds * 1000:.0f} ms" if seconds < 1 else f"{seconds:.1f} s"


def print_agent_profile(profile: AgentProfile) -> None:
    """Print the request and hosted-agent milestones."""
    print("Hosted agent profile (observed from the first request):")
    if profile.reference is not None:
        print(f"  session reference {profile.reference}")
    for event_id in profile.event_ids:
        print(f"  event {event_id}")
    for ask in range(1, profile.ask_count + 1):
        suffix = "" if ask == 1 else f" {ask}"
        print(
            f"  request{suffix} acknowledged "
            f"{elapsed_time(profile.milestones[f'acknowledged {ask}'])}"
        )
    for at, kind, detail in profile.activities:
        description = f": {detail}" if detail else ""
        print(f"  activity {kind}{description} at {elapsed_time(at)}")
    for name in ("published", "response visible", "replied", "answered"):
        if name in profile.milestones:
            print(f"  {name} at {elapsed_time(profile.milestones[name])}")


def agent_profile(profile: AgentProfile) -> dict:
    """Return one comment-to-answer profile without rounding away comparisons."""
    acknowledged = [
        profile.milestones[f"acknowledged {ask}"] * 1000
        for ask in range(1, profile.ask_count + 1)
    ]
    return {
        "sessionReference": profile.reference,
        "eventIds": profile.event_ids,
        "asks": profile.ask_count,
        "acknowledgedMs": acknowledged,
        "activity": [
            {"atMs": at * 1000, "kind": kind, "detail": detail}
            for at, kind, detail in profile.activities
        ],
        "publishedMs": profile.milestones.get("published", 0) * 1000
        if "published" in profile.milestones
        else None,
        "responseVisibleMs": profile.milestones.get("response visible", 0) * 1000
        if "response visible" in profile.milestones
        else None,
        "repliedMs": profile.milestones.get("replied", 0) * 1000
        if "replied" in profile.milestones
        else None,
        "answeredMs": profile.milestones.get("answered", 0) * 1000
        if "answered" in profile.milestones
        else None,
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


def start_direct_agent(context, url: str, comment: dict) -> None:
    """Run the local adapter's side of the production Worker dispatch."""
    endpoint = urljoin(url, "_leaf/agent/")
    event = {"event": comment["id"]}
    started = context.request.post(
        urljoin(endpoint, "start"), data=event, timeout=120_000
    )
    check(started.ok, f"{endpoint}start returned {started.status}")
    reading = started.json()
    check(
        reading.get("status") in {"started", "settled"},
        f"{endpoint}start returned {reading}",
    )


def read_agent_state(context, state_url: str, layer: str, release: str) -> dict:
    """Read the authoritative state for one activated deployment session."""
    response = context.request.get(
        state_url,
        headers={"Leaf-Layer": layer, "Leaf-Release": release},
        timeout=120_000,
    )
    check(response.ok, f"{state_url} returned {response.status}")
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
    """Send one deployment-check comment through the reader's real composer."""
    text = (
        f"Change the main heading to ‘{heading}’. Leave everything else unchanged, "
        "publish the revision, and reply with ‘deployment verified’."
    )
    box = page.locator(".lf-general textarea")
    box.fill(text)
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
    # The response headers are the acknowledgement edge. Read the admitted event
    # through the same authoritative state endpoint that owns every later milestone;
    # consuming this intercepted response body again can wait forever in Playwright
    # after the page's fetch and the Worker have both finished with the stream.
    accepted = read_agent_state(context, state_url, layer, release)
    check(
        "events" in accepted,
        f"{url} answered its deployment-check comment without admitting it: {accepted}",
    )
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
        answer = deployment_answer(replies)
        active = current["active"]
        if published is None and active["revision"] > revision:
            # The published document itself, fetched the way the next reader's browser
            # fetches it: an edge-missing revision only this session's container holds.
            document = context.request.get(urljoin(url, active["url"]), timeout=120_000)
            if document.ok and heading in document.text():
                published = active
                profile.mark("published")
        if published is not None and answer is not None:
            profile.mark("answered")
            break
        # A host failure receipt closes the turn. Either half of a successful outcome
        # can otherwise arrive first — the agent reply or the requested publication —
        # so a reading with only one waits for the other under the bounds below.
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
    report: bool = True,
    direct_agent: bool = False,
) -> AgentAsks:
    """Ask the deployed agent for `heading` until it answers or stops answering.

    A Worker startup failure is retried once while the pass has enough time for a
    healthy turn. Rate limits and turns that stop without answering fail the pass
    on the first ask. The reply's failure code owns this decision, not its wording.
    """
    published = None
    asks = 0
    profile = AgentProfile()
    deadline = time.monotonic() + TURN_LIMIT
    while True:
        asks += 1
        profile.ask_count = asks
        # Each ask is posted against the revision the page stands on now, so a second
        # continues the page the first turn left rather than an earlier reading of it.
        # What that turn published is carried across it: an agent handed a heading it
        # has already published has no reason to publish it again.
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
        # A second ask is only worth posting while a healthy turn's budget is still
        # inside the pass's own limit; past that the gate reports what it has rather
        # than opening a turn it cannot wait for.
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
        if report:
            print(
                f"↻ {url} settled its ask with a startup failure; "
                "sending one new message"
            )


def verify_agent_turn(
    browser,
    release: str | None,
    *,
    origin: str,
    direct_agent: bool = False,
    report: bool = True,
) -> dict:
    """Require one deployed Codex turn to revise and answer a private page.

    A turn is a process, not a step: it may publish a checkpoint revision before the
    requested edit. So the wait names the outcome — a published document carrying the
    requested heading, and a reply the host did not generate for the turn — rather
    than the first revision to appear. The heading readings are containments: the
    agent may quote the heading it was handed, and the runtime may add its own words
    to any text a reader can point at.

    The wait's bound is the page rather than a stopwatch. One fixed budget has to be
    long enough for the slowest healthy turn and short enough to report a dead one
    promptly, and no single number is both — so `TURN_PATIENCE` ends the wait on a
    page that says nothing is answering, while a page that says a turn is still on
    this comment holds it open to `TURN_LIMIT`.
    """
    context, page, failures, url, state_url, state = agent_session(
        browser, release, origin=origin, direct_agent=direct_agent
    )
    initial_startup = page.evaluate("window.__leafVerifier.startupReading")
    if release is None:
        release = state.get("release")
        check(isinstance(release, str), f"{state_url} returned no release")
    # The layer the comment is posted under is the one its own container holds, not
    # the one the edge describes: an event whose layer the container does not speak
    # is answered with that container's generation instead of a state.
    layer = state["layer"]["generation"]
    heading = f"Deployment {release[:8]} verified"
    page.locator(".lf-threads-toggle").click()
    asked = ask_until_answered(
        context,
        page,
        url,
        state_url,
        layer,
        release,
        heading,
        state,
        report=report,
        direct_agent=direct_agent,
    )
    turn, asks, revision, profile = asked
    try:
        page.wait_for_function(
            "window.__leafVerifier.visibleReplyRecorded", timeout=30_000
        )
    except PlaywrightTimeout:
        pass
    visible_reply_at = page.evaluate("window.__leafVerifier.visibleReplyAt")
    if visible_reply_at is None:
        visible_reply_debug = page.evaluate("window.__leafVerifier.visibleReplyDebug")
        raise RuntimeError(
            f"{url} reply never became visible in Threads: {visible_reply_debug}"
        )
    check(
        profile.visible_reply_started_ms is not None,
        f"{url} did not record its first submission edge",
    )
    profile.milestones["response visible"] = (
        visible_reply_at - profile.visible_reply_started_ms
    ) / 1000
    state, published, replies, answer = turn
    if report:
        print_agent_profile(profile)
    tried = f" to {asks} asks" if asks > 1 else ""
    reading = (state.get("activity") or {}).get("kind") or "no activity"
    said = "; it replied: " + " / ".join(event["text"] for event in replies)
    check(
        published is not None,
        f"{url} agent did not publish ‘{heading}’{tried}; it reached revision "
        f"{state['active']['revision']} from {revision} with the page "
        f"reading {reading}" + (said if replies else " and did not reply"),
    )
    check(
        replies != [],
        f"{url} agent published but did not reply{tried}; the page read {reading}",
    )
    check(
        answer is not None,
        f"{url} agent returned an unexpected reply{tried}{said}",
    )
    reloaded = page.reload(wait_until="load", timeout=120_000)
    check(
        reloaded is not None and reloaded.ok,
        f"{url} did not reload after its agent turn",
    )
    await_presentation(page, url, failures, timeout=TURN_PRESENTATION)
    startup = page.evaluate("window.__leafVerifier.startupReading")
    presented_at = startup.get("presented", {}).get("at")
    # Presentation no longer says the reload's first read landed: the runtime presents at
    # its own fixed wait whether or not the container has answered, and following the
    # agent's revision is the activation that read triggers. So the gate spends its own
    # patience on the revision rather than sampling it the instant the page appears — a
    # container that answers a second after the runtime stopped waiting is a reader's page
    # arriving late, not a deployment that failed to follow the turn. This elapsed wait
    # is the canonical reading of that post-presentation tail: a resource-timing snapshot
    # taken when the page presents cannot see an `/api/state` request still in flight and
    # would report zero for the case measured here. What runs this wait out is a read that
    # never answered at all, which is the ending the banner below names.
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
    # After the wait rather than before it: the activation this gate is reading for
    # happens during that wait, so a page that threw on its way there would otherwise
    # report the revision it never reached instead of the error that stopped it.
    check(not failures, f"{url} reported browser errors: {failures}")
    # Which of the two ways this can fail: a browser still standing on the built
    # document never followed the agent's revision, while one that followed it and
    # shows another heading is the agent's edit rather than the reader's page.
    shown = page.evaluate("window.__leafVerifier.revision")
    # A page standing on the built document has two ways to get there, and the banner
    # separates them: one whose first read answered was told revision 1 and stands under
    # that reading's activity line, while one that presented offline was never told
    # anything and stands under the offline line over the authored page. The gate cannot
    # see the read, so it reports what the page says about it. A presented page always
    # has this line — the chrome mounts it reading ‘Connecting…’ and every render
    # replaces its words — so there is no third answer to guard for.
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
    # What the turn actually did, on the green run as well as the red one: a gate whose
    # only account of a hosted agent is its own exit status leaves the next reader of a
    # failure with nothing to compare against. This is the only reading anyone has of a
    # container serving a page a hosted turn has just written to, and the wait above is
    # the part of it that can still move: presentation now lands at the runtime's own
    # fixed wait whether the container answered in three seconds or thirty, while the
    # time past it before the first read brought the revision back is the read this step
    # fails on. Printing that every deployment is what makes a drift in it visible
    # before it becomes the next timeout.
    followed = (
        f"followed revision {published['revision']} "
        f"{followed_in:.0f} ms after presentation"
    )
    if report:
        print(
            f"✓ hosted agent published revision {published['revision']} "
            f"and replied: {answer['text']}"
            + (
                f"; the reloaded page presented in {presented_at:.0f} ms and {followed}"
                if presented_at is not None
                else f"; the reloaded page {followed}"
            )
        )
        print(startup_line("changed page", startup))
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


def target_origin(target: str) -> str:
    """Require an HTTP origin; page paths belong to the verification journey."""
    parsed = urlsplit(target)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise click.BadParameter("target must be local or an http(s) origin")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise click.BadParameter(
            "target must be an origin without a path, query, or fragment"
        )
    return target.rstrip("/")


@contextmanager
def local_adapter():
    """Own a disposable website adapter and Codex home for one real agent journey.

    The host's login is copied into a private temporary home. The adapter uses
    resumable tasks there and owns their App Server; terminating it closes that
    server before the temporary pages and task history are removed. Build and server
    output stay in the diagnostic log, so a benchmark's stdout contains only JSON.
    """
    log = ROOT / ".tmp" / "website-agent-local.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="leaf-site-agent.") as temporary:
        root = Path(temporary)
        site = root / "site"
        codex_home = root / "codex-home"
        codex_home.mkdir(mode=0o700)
        host_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        shutil.copyfile(
            ROOT / "worker" / "codex-config.toml", codex_home / "config.toml"
        )
        auth = codex_home / "auth.json"
        shutil.copyfile(host_home / "auth.json", auth)
        auth.chmod(0o600)
        with log.open("w") as output:
            try:
                subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "site.py")],
                    cwd=ROOT,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
                shutil.copytree(ROOT / ".tmp" / "site", site)
                release = json.loads((site / "_leaf" / "site.json").read_text())[
                    "release"
                ]
                output.flush()
                server_log_start = output.tell()
                with subprocess.Popen(
                    [sys.executable, str(ROOT / "worker" / "server.py")],
                    cwd=ROOT,
                    env={
                        **os.environ,
                        "CODEX_HOME": str(codex_home),
                        "LEAF_SITE_ROOT": str(site),
                    },
                    stdout=output,
                    stderr=subprocess.STDOUT,
                ) as server:
                    try:
                        origin = "http://127.0.0.1:8080"
                        deadline = time.monotonic() + 30
                        while True:
                            if server.poll() is not None:
                                raise RuntimeError(
                                    "the local website adapter exited before becoming ready"
                                )
                            # The adapter emits this event only after binding its
                            # listener. An unrelated process answering the port must
                            # not satisfy readiness before our child has started.
                            with log.open() as server_log:
                                server_log.seek(server_log_start)
                                ready = False
                                for line in server_log:
                                    if not line.endswith("\n"):
                                        break
                                    try:
                                        record = json.loads(line)
                                    except json.JSONDecodeError:
                                        # stderr shares this log with the structured
                                        # events, including startup tracebacks.
                                        continue
                                    if (
                                        isinstance(record, dict)
                                        and record.get("event")
                                        == "container_http_ready"
                                    ):
                                        ready = True
                                        break
                            if ready:
                                try:
                                    with urllib.request.urlopen(
                                        f"{origin}/health", timeout=1
                                    ):
                                        break
                                except (urllib.error.URLError, TimeoutError):
                                    pass
                            if time.monotonic() >= deadline:
                                raise RuntimeError(
                                    "the local website adapter did not become ready"
                                )
                            time.sleep(0.1)
                        yield origin, release
                    finally:
                        if server.poll() is None:
                            server.terminate()
                        server.wait()
            except BaseException:
                output.flush()
                sys.stderr.write(log.read_text())
                raise


@click.command()
@click.argument("target", default="https://leaf.page")
@click.option("--release", help="Require this exact built release.")
@click.option(
    "--agent",
    is_flag=True,
    help="Verify one agent edit and reply instead of the release boundary.",
)
def main(target: str, release: str | None, agent: bool) -> None:
    """Verify a deployed release, or run the agent journey against LOCAL or an origin.

    The release and agent passes are separate: rollout verification settles the
    release before the agent pass allocates its own private reader session.
    """
    if target == "local":
        with local_adapter() as (origin, built):
            check(
                release is None or release == built,
                "the requested release differs from the built site",
            )
            run_verification(origin, built, agent=True, direct_agent=True)
        return
    origin = target_origin(target)
    built = json.loads(MANIFEST.read_text(encoding="utf-8"))["release"]
    check(
        release is None or release == built,
        "the requested release differs from the built site",
    )
    run_verification(origin, release or built, agent=agent)


def run_verification(
    origin: str, release: str, *, agent: bool, direct_agent: bool = False
) -> None:
    """Run one browser check against explicit transport and release inputs."""
    with sync_playwright() as playwright:
        browser, browser_name = launch_browser(playwright)
        try:
            if agent:
                verify_agent_turn(
                    browser, release, origin=origin, direct_agent=direct_agent
                )
                print(f"✓ {origin} ran one agent turn on release {release}")
                return
            print(
                "Leaf startup profile (observed, not a pass/fail budget):", flush=True
            )
            for path, kind, activate in PAGES:
                profile = verify_page(
                    browser, path, kind, release, activate, origin=origin
                )
                print(startup_line(path, profile), flush=True)
            verify_cross_tab_activation(browser, origin=origin)
        finally:
            browser.close()
    print(f"✓ {origin} serves release {release} in {browser_name}")


if __name__ == "__main__":
    main()
