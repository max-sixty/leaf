#!/usr/bin/env python3
"""Verify that leaf.page serves one exact, coherent release in a real browser."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlencode, urljoin, urlsplit

from leaf.render_gate.browser import launch_browser
from playwright.sync_api import BrowserContext, Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".tmp" / "site" / "_leaf" / "site.json"
ORIGIN = os.environ.get("LEAF_SITE_ORIGIN", "https://leaf.page").rstrip("/")
PAGES = (
    ("/", "product", True),
    ("/examples/design-decision/", "example", True),
    ("/examples/feature-gallery/versions/v1.html", "example", False),
)
PROFILE_SCRIPT = """(() => {
  window.__leafStartup = {};
  const snapshot = () => {
    const resources = performance.getEntriesByType("resource");
    const code = resources.filter(entry => {
      const url = new URL(entry.name);
      return url.origin === location.origin &&
        (url.pathname.endsWith(".js") || url.pathname.endsWith(".css") ||
         url.pathname.endsWith("/registry.json"));
    });
    const javascript = code.filter(entry => new URL(entry.name).pathname.endsWith(".js"));
    const state = resources.filter(entry =>
      new URL(entry.name).pathname.endsWith("/api/state"));
    const bytes = entries => entries.reduce((total, entry) => total + entry.encodedBodySize, 0);
    const lastResponse = entries => Math.max(0, ...entries.map(entry => entry.responseEnd));
    return {
      at: performance.now(),
      code_loaded: lastResponse(code),
      js_loaded: lastResponse(javascript),
      state_loaded: lastResponse(state),
      requests: resources.length,
      bytes: bytes(resources),
      code_requests: code.length,
      code_bytes: bytes(code),
      js_requests: javascript.length,
      js_bytes: bytes(javascript),
    };
  };
  const record = () => {
    const body = document.body;
    if (!body) return;
    for (const [name, attribute] of [
      ["upgraded", "data-lf-upgraded"],
      ["presented", "data-lf-presented"],
    ]) {
      if (body.hasAttribute(attribute) && !window.__leafStartup[name])
        window.__leafStartup[name] = snapshot();
    }
  };
  new MutationObserver(record).observe(document, {
    attributes: true,
    attributeFilter: ["data-lf-upgraded", "data-lf-presented"],
    childList: true,
    subtree: true,
  });
  record();
})()"""
STARTUP_READING = """() => {
  const navigation = performance.getEntriesByType("navigation")[0];
  return {
    first_byte: navigation.responseStart,
    document: navigation.responseEnd,
    paint: Object.fromEntries(
      performance.getEntriesByType("paint").map(entry => [entry.name, entry.startTime])
    ),
    ...window.__leafStartup,
  };
}"""


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
# How long the page reloaded after the turn may take to present. The release pass walks
# pages the edge serves, which present in about a second, and `await_presentation`'s own
# bound is calibrated for those. This reload is answered by a container that has just run
# a hosted model turn, whose first `/api/state` read is measured in seconds rather than
# milliseconds and varies with what the turn did — so it gets the same patience as every
# other read this pass makes of that container, and reports what it cost.
TURN_PRESENTATION = 120_000
# The activity readings that mean a turn is on this work. A page that reads away,
# unheld, listening, stalled or closed is not going to answer, so its wait ends at
# `TURN_PATIENCE` rather than running out the limit.
ANSWERING = frozenset({"queued", "handling", "working"})
# The container's own settlement for a turn that ended without generating a reply,
# mirroring `worker/server.py`'s `GENERATION_FAILURE_REPLY`. Reaching it is the
# deployment working: the container noticed a turn that never completed, closed it,
# and answered the reader's standing ask rather than leaving it open. What it says
# about the release is only that this one generation did not happen, so the gate does
# what the text itself asks for and sends one more message. A deployment that cannot
# run a hosted turn settles the same way twice; a model-side failure does not.
GENERATION_FAILURE_REPLY = (
    "I couldn’t generate a reply just now. Please send a new message to try again."
)
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
    that stalled, and not how far it got. `PROFILE_SCRIPT` already records each
    startup stamp as it lands, and the two stamps separate the two ways to stall —
    an upgrade that never settled leaves none, while a first state read that never
    answered leaves `upgraded` standing alone.
    """
    milestones = ", ".join(reached) if reached else "no startup milestone"
    reported = f"; browser errors: {failures}" if failures else ""
    return f"{url} never presented, reaching {milestones}{reported}"


def await_presentation(
    page, url: str, failures: list[str], timeout: int = 30_000
) -> None:
    try:
        page.locator("body[data-lf-presented]").wait_for(timeout=timeout)
    except PlaywrightTimeout:
        reached = page.evaluate("() => Object.keys(window.__leafStartup ?? {})")
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


def verify_page(browser, path: str, kind: str, release: str, activate: bool) -> dict:
    context = browser.new_context()
    page = context.new_page()
    page.add_init_script(PROFILE_SCRIPT)
    failures: list[str] = []
    page.on(
        "console",
        lambda message: (
            failures.append(message.text) if message.type == "error" else None
        ),
    )
    page.on("pageerror", lambda error: failures.append(str(error)))
    url = urljoin(f"{ORIGIN}/", path.lstrip("/"))
    response = page.goto(url, wait_until="load", timeout=120_000)
    check(response is not None and response.ok, f"{url} did not load")
    await_presentation(page, url, failures)

    identity = page.locator("script[data-lf-runtime]").evaluate(
        "script => ({layer: script.dataset.lfLayer, release: script.dataset.lfRelease})"
    )
    check(identity["release"] == release, f"{url} served release {identity['release']}")
    prefix = f"/_leaf-release/{release}/"
    resources = page.evaluate(
        "performance.getEntriesByType('resource').map(entry => entry.name)"
    )
    code = [
        resource
        for resource in resources
        if urlsplit(resource).path.endswith((".js", ".css", "registry.json"))
        and urlsplit(resource).netloc == urlsplit(ORIGIN).netloc
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
    secure = urlsplit(ORIGIN).scheme == "https"
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
    media = page.evaluate(
        """async () => {
          const script = document.querySelector("script[data-lf-runtime]");
          const moduleUrl = new URL("runtime/media.js", new URL(script.dataset.lfEntry, location.origin));
          return {
            path: (await import(moduleUrl.href)).scopedMediaUrl("/media/0123456789abcdef.png"),
            root: script.dataset.lfPageRoot,
          };
        }"""
    )
    expected_media = f"{media['root']}/media/0123456789abcdef.png"
    check(
        media["path"] == expected_media,
        f"{url} scoped private media into the release namespace: {media['path']}",
    )
    check(not failures, f"{url} reported browser errors: {failures}")
    startup = page.evaluate(STARTUP_READING)
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


def startup_line(path: str, startup: dict) -> str:
    """Render observed startup costs without turning machine speed into a gate."""
    presented = startup["presented"]
    paint = startup.get("paint", {}).get("first-contentful-paint", 0)
    return (
        f"  {path} — HTML first byte {startup['first_byte']:.0f} ms, "
        f"complete {startup['document']:.0f} ms; first paint {paint:.0f} ms; "
        f"JS fetched {presented['js_loaded']:.0f} ms; "
        f"upgraded {startup['upgraded']['at']:.0f} ms; "
        f"state answered {presented['state_loaded']:.0f} ms; "
        f"presented {presented['at']:.0f} ms; "
        f"by presentation {presented['js_requests']} JS / "
        f"{presented['js_bytes'] / 1024:.0f} KiB, "
        f"{presented['code_requests']} code / "
        f"{presented['code_bytes'] / 1024:.0f} KiB, "
        f"{presented['requests']} total / {presented['bytes'] / 1024:.0f} KiB"
    )


def verify_cross_tab_activation(browser) -> None:
    """One interacting tab must wake another tab sharing its browser session."""
    context = browser.new_context()
    url = f"{ORIGIN}/examples/design-decision/"
    leader = context.new_page()
    follower = context.new_page()
    for page in (leader, follower):
        page.add_init_script(PROFILE_SCRIPT)
        response = page.goto(url, wait_until="load", timeout=120_000)
        check(response is not None and response.ok, f"{url} did not load")
        await_presentation(page, url, [])
    follower.evaluate(
        """() => {
          window.__leafActivated = 0;
          document.addEventListener("lf-session-active", () => window.__leafActivated++);
        }"""
    )
    leader.evaluate(
        """async () => {
          const script = document.querySelector("script[data-lf-runtime]");
          const moduleUrl = new URL("runtime/layer-client.js", new URL(script.dataset.lfEntry, location.origin));
          const client = await import(moduleUrl.href);
          client.observeSession(new Response(null, {headers: {"Leaf-Session": "active"}}));
        }"""
    )
    follower.wait_for_function("window.__leafActivated === 1", timeout=5_000)
    context.close()


def reader_session(
    browser, url: str, state_url: str, release: str
) -> AgentSession | str:
    """One activated reader session, or the release its container served instead."""
    context = browser.new_context()
    page = context.new_page()
    # The same startup stamps `verify_page` records, because this page is reloaded
    # after the turn and `unpresented` has no other way to say how far it got. Without
    # it every stall here reports "no startup milestone" whatever stalled.
    page.add_init_script(PROFILE_SCRIPT)
    failures: list[str] = []
    page.on(
        "console",
        lambda message: (
            failures.append(message.text) if message.type == "error" else None
        ),
    )
    page.on("pageerror", lambda error: failures.append(str(error)))
    response = page.goto(url, wait_until="load", timeout=120_000)
    check(response is not None and response.ok, f"{url} did not load for its agent")
    await_presentation(page, url, failures)
    passive = context.request.get(state_url, timeout=120_000)
    check(passive.ok, f"{state_url} returned {passive.status}")
    activation = activation_url(url, passive.json())
    activated = context.request.get(activation, timeout=120_000)
    check(activated.ok, f"{activation} returned {activated.status}")
    check(
        activated.headers.get("leaf-session") == "active",
        f"{activation} did not activate a private container for its agent",
    )
    state_response = context.request.get(
        state_url,
        headers={"Leaf-Release": release},
        timeout=120_000,
    )
    check(state_response.ok, f"{state_url} returned {state_response.status}")
    # The edge answers a passive `api/state` with the deployed release whatever the
    # containers run, so the release below reads as this container's own only once
    # the session is known to have left the edge.
    check(
        state_response.headers.get("leaf-session") == "active",
        f"{state_url} did not reach a private container for its agent",
    )
    reached = state_response.headers.get("leaf-release")
    if reached != release:
        context.close()
        return reached or "no release"
    return AgentSession(context, page, failures, url, state_url, state_response.json())


def agent_session(browser, release: str) -> AgentSession:
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
    url = f"{ORIGIN}/examples/design-decision/"
    state_url = urljoin(url, "api/state")
    # The release verification ahead of this pass already waited out most of the
    # rollout, so this is the tail of a drain rather than the drain, and this wait
    # plus the turn's `TURN_LIMIT` still has to sit inside the job's own budget.
    deadline = time.monotonic() + 180
    while True:
        session = reader_session(browser, url, state_url, release)
        if isinstance(session, AgentSession):
            return session
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
        self.milestones: dict[str, float] = {}
        self.activities: list[tuple[float, str, str]] = []
        self.ask_count = 0

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
    profile: AgentProfile | None = None


def elapsed_time(seconds: float) -> str:
    """Format one observed interval at a useful scale."""
    return f"{seconds * 1000:.0f} ms" if seconds < 1 else f"{seconds:.1f} s"


def print_agent_profile(profile: AgentProfile) -> None:
    """Print the request and hosted-agent milestones."""
    print("Hosted agent profile (observed from the first request):")
    for ask in range(1, profile.ask_count + 1):
        suffix = "" if ask == 1 else f" {ask}"
        print(
            f"  request{suffix} acknowledged "
            f"{elapsed_time(profile.milestones[f'acknowledged {ask}'])}"
        )
    for at, kind, detail in profile.activities:
        description = f": {detail}" if detail else ""
        print(f"  activity {kind}{description} at {elapsed_time(at)}")
    for name in ("published", "replied", "answered"):
        if name in profile.milestones:
            print(f"  {name} at {elapsed_time(profile.milestones[name])}")


def generation_failed(replies: list[dict]) -> bool:
    """Whether the container settled this ask by reporting a turn that never ran."""
    return any(reply["text"].strip() == GENERATION_FAILURE_REPLY for reply in replies)


def deployment_answer(replies: list[dict]) -> dict | None:
    """Return the exact receipt requested by the deployment check."""
    return next(
        (
            reply
            for reply in replies
            if reply["text"].strip().casefold() == "deployment verified"
        ),
        None,
    )


def ask_for_the_heading(
    context,
    url: str,
    layer: str,
    release: str,
    revision: int,
    heading: str,
    attempt: str,
    profile: AgentProfile,
    ask: int,
) -> dict:
    """Post one deployment-check comment and return the event the page admitted."""
    posted = context.request.post(
        urljoin(url, "api/event"),
        headers={"Leaf-Layer": layer, "Leaf-Release": release},
        data={
            "kind": "comment",
            "revision": revision,
            "text": (
                f"Change the main heading to ‘{heading}’. Leave everything else "
                "unchanged, publish the revision, and reply with ‘deployment verified’."
            ),
            "attempt": attempt,
        },
        timeout=120_000,
    )
    check(posted.ok, f"{url} rejected its deployment-check comment")
    accepted = posted.json()
    profile.mark(f"acknowledged {ask}")
    check(
        "state" in accepted,
        f"{url} answered its deployment-check comment without admitting it: {accepted}",
    )
    profile.observe(accepted["state"])
    comment = next(
        (
            event
            for event in accepted.get("state", {}).get("events", [])
            if event.get("attempt") == attempt
        ),
        None,
    )
    check(comment is not None, f"{url} did not return its deployment-check comment")
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
        current_response = context.request.get(
            state_url,
            headers={"Leaf-Layer": layer, "Leaf-Release": release},
            timeout=120_000,
        )
        check(current_response.ok, f"{state_url} returned {current_response.status}")
        current = current_response.json()
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
        # The container posts its generation failure from the same place it closes the
        # turn, so that reply is the turn's own account of having stopped. Every other
        # reading here is one a live turn can still be passing through — an interim
        # reply, a publication its answer precedes — which is why they wait out the
        # bounds below instead of ending the wait early.
        if generation_failed(replies):
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
    url: str,
    state_url: str,
    layer: str,
    release: str,
    heading: str,
    attempt: str,
    state: dict,
) -> AgentAsks:
    """Ask the deployed agent for `heading` until it answers or stops answering.

    One outcome is asked again rather than reported. When the container settles an ask
    with `GENERATION_FAILURE_REPLY`, the deployment has answered for itself correctly —
    it caught a turn that never completed and told the reader to send a new message —
    so this sends it, because a release that cannot run a hosted turn settles the same
    way twice while a model-side failure does not. Every other ending is reported on
    the first ask: a turn that completes without a reply, or replies with something
    else, is the deployed agent breaking its own contract.
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
            context, url, layer, release, revision, heading, attempt, profile, asks
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
            and generation_failed(replies)
            and deadline - time.monotonic() >= TURN_PATIENCE
        ):
            return AgentAsks(
                TurnReading(state, published, replies, answer), asks, revision, profile
            )
        print(
            f"↻ {url} settled its ask with the container's generation failure; "
            "sending the new message that reply asks for"
        )
        attempt = f"{attempt}-{asks + 1}"


def verify_agent_turn(browser, release: str) -> None:
    """Require one deployed Codex turn to revise and answer a private page.

    A turn is a process, not a step: it may publish a checkpoint revision, say
    something about the work, and only then publish what was asked for. So the wait
    names the outcome — a published document carrying the requested heading, and a
    reply that answers for it — rather than the first revision and the first reply to
    appear, either of which the turn can pass through on its way there. The readings
    that follow are containments for the same reason: the agent may quote the heading
    it was handed, and the runtime may add its own words to any text a reader can
    point at.

    The wait's bound is the page rather than a stopwatch. One fixed budget has to be
    long enough for the slowest healthy turn and short enough to report a dead one
    promptly, and no single number is both — so `TURN_PATIENCE` ends the wait on a
    page that says nothing is answering, while a page that says a turn is still on
    this comment holds it open to `TURN_LIMIT`.
    """
    context, page, failures, url, state_url, state = agent_session(browser, release)
    # The layer the comment is posted under is the one its own container holds, not
    # the one the edge describes: an event whose layer the container does not speak
    # is answered with that container's generation instead of a state.
    layer = state["layer"]["generation"]
    heading = f"Deployment {release[:8]} verified"
    asked = ask_until_answered(
        context,
        url,
        state_url,
        layer,
        release,
        heading,
        f"deployment-{release[:24]}",
        state,
    )
    turn, asks, revision, profile = asked
    state, published, replies, answer = turn
    if profile is not None:
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
    startup = page.evaluate(STARTUP_READING)
    presented_at = startup.get("presented", {}).get("at")
    check(not failures, f"{url} reported browser errors: {failures}")
    # Which of the two ways this can fail: a browser still standing on the built
    # document never followed the agent's revision, while one that followed it and
    # shows another heading is the agent's edit rather than the reader's page.
    shown = page.evaluate(
        "() => document.querySelector('meta[name=\"lf-revision\"]')?.content ?? null"
    )
    check(
        (shown or "").isdigit() and int(shown) >= published["revision"],
        f"{url} stands on revision {shown} rather than following the published "
        f"{published['revision']}",
    )
    rendered = page.locator("h1").inner_text()
    check(
        heading in rendered,
        f"{url} rendered ‘{rendered}’ rather than the agent's published ‘{heading}’",
    )
    # What the turn actually did, on the green run as well as the red one: a gate whose
    # only account of a hosted agent is its own exit status leaves the next reader of a
    # failure with nothing to compare against. The reload's cost rides along because this
    # is the only reading anyone has of a container serving a page a hosted turn has just
    # written to, and a number printed every deployment is what makes a drift in it
    # visible before it becomes the next timeout.
    print(
        f"✓ hosted agent published revision {published['revision']} "
        f"and replied: {answer['text']}"
        + (
            f"; the reloaded page presented in {presented_at:.0f} ms"
            if presented_at is not None
            else ""
        )
    )
    print(startup_line("changed page", startup))
    context.close()


def main() -> None:
    """Verify one deployed release, or run the deployed agent turn against it.

    Container rollout is asynchronous and per allocation: a fresh reader session can
    still reach the previous image seconds after another reached the new one. The
    deploy step waits that out by re-running the release pass until it holds, so a
    single coherent sample is what ends the wait. The agent pass therefore runs the
    turn alone — re-sampling the release readings after the wait had already settled
    them turned a rollout that was still draining into a red default branch.
    """
    if len(sys.argv) > 2:
        raise SystemExit("usage: uv run scripts/verify-site.py [release]")
    built = json.loads(MANIFEST.read_text(encoding="utf-8"))["release"]
    release = sys.argv[1] if len(sys.argv) == 2 else built
    check(release == built, "the requested release differs from the built site")
    with sync_playwright() as playwright:
        browser, browser_name = launch_browser(playwright)
        try:
            if os.environ.get("LEAF_VERIFY_AGENT") == "1":
                verify_agent_turn(browser, release)
                print(f"✓ leaf.page ran one deployed agent turn on release {release}")
                return
            profiles = [
                (path, verify_page(browser, path, kind, release, activate))
                for path, kind, activate in PAGES
            ]
            verify_cross_tab_activation(browser)
        finally:
            browser.close()
    print("Leaf startup profile (observed, not a pass/fail budget):")
    for path, profile in profiles:
        print(startup_line(path, profile))
    print(f"✓ leaf.page serves release {release} in {browser_name}")


if __name__ == "__main__":
    main()
