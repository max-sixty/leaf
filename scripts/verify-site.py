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
    const bytes = entries => entries.reduce((total, entry) => total + entry.encodedBodySize, 0);
    return {
      at: performance.now(),
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


# One hosted Codex turn runs at the model's pace, not this gate's. `TURN_PATIENCE`
# is the budget a turn observed healthy has finished well inside; `TURN_LIMIT` is
# what this step can add and still sit inside the job's thirty minutes beside the
# release wait ahead of it. Between the two the page's own `activity` reading
# decides, because a stopwatch cannot tell a turn that is still working from one
# that has stopped.
TURN_PATIENCE = 300
TURN_LIMIT = 600
# The activity readings that mean a turn is on this work. A page that reads away,
# unheld, listening, stalled or closed is not going to answer, so its wait ends at
# `TURN_PATIENCE` rather than running out the limit.
ANSWERING = frozenset({"queued", "handling", "working"})


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


def await_presentation(page, url: str, failures: list[str]) -> None:
    try:
        page.locator("body[data-lf-presented]").wait_for(timeout=30_000)
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
    startup = page.evaluate(
        """() => ({
          document: performance.getEntriesByType("navigation")[0].responseEnd,
          ...window.__leafStartup,
        })"""
    )
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
    return (
        f"  {path} — HTML {startup['document']:.0f} ms; "
        f"upgraded {startup['upgraded']['at']:.0f} ms; "
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
    # rollout, so this is the tail of a drain rather than the drain, and the step's
    # own budget still has to hold the turn's `TURN_LIMIT` inside the job's thirty.
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
    initial_revision = state["active"]["revision"]
    # The layer the comment is posted under is the one its own container holds, not
    # the one the edge describes: an event whose layer the container does not speak
    # is answered with that container's generation instead of a state.
    layer = state["layer"]["generation"]
    heading = f"Deployment {release[:8]} verified"
    attempt = f"deployment-{release[:24]}"
    posted = context.request.post(
        urljoin(url, "api/event"),
        headers={"Leaf-Layer": layer, "Leaf-Release": release},
        data={
            "kind": "comment",
            "revision": initial_revision,
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
    check(
        "state" in accepted,
        f"{url} answered its deployment-check comment without admitting it: {accepted}",
    )
    comment = next(
        (
            event
            for event in accepted.get("state", {}).get("events", [])
            if event.get("attempt") == attempt
        ),
        None,
    )
    check(comment is not None, f"{url} did not return its deployment-check comment")

    started = time.monotonic()
    replies: list[dict] = []
    answer = None
    published = None
    current = state
    while True:
        current_response = context.request.get(
            state_url,
            headers={"Leaf-Layer": layer, "Leaf-Release": release},
            timeout=120_000,
        )
        check(current_response.ok, f"{state_url} returned {current_response.status}")
        current = current_response.json()
        replies = [
            event
            for event in current.get("events", [])
            if event.get("kind") == "reply" and event.get("parent") == comment["id"]
        ]
        answer = next(
            (
                event
                for event in replies
                if "deployment verified" in event["text"].casefold()
            ),
            None,
        )
        active = current["active"]
        if published is None and active["revision"] > initial_revision:
            # The published document itself, fetched the way the next reader's browser
            # fetches it: an edge-missing revision only this session's container holds.
            document = context.request.get(urljoin(url, active["url"]), timeout=120_000)
            if document.ok and heading in document.text():
                published = active
        if published is not None and answer is not None:
            break
        waited = time.monotonic() - started
        if waited >= TURN_LIMIT:
            break
        if waited >= TURN_PATIENCE and not still_answering(current, comment["id"]):
            break
        time.sleep(2)
    reading = (current.get("activity") or {}).get("kind") or "no activity"
    said = "; it replied: " + " / ".join(event["text"] for event in replies)
    check(
        published is not None,
        f"{url} agent did not publish ‘{heading}’; it reached revision "
        f"{current['active']['revision']} from {initial_revision} with the page "
        f"reading {reading}" + (said if replies else " and did not reply"),
    )
    check(
        replies != [],
        f"{url} agent published but did not reply; the page read {reading}",
    )
    check(answer is not None, f"{url} agent returned an unexpected reply{said}")
    page.reload(wait_until="load", timeout=120_000)
    await_presentation(page, url, failures)
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
    # failure with nothing to compare against.
    print(
        f"✓ hosted agent published revision {published['revision']} "
        f"and replied: {answer['text']}"
    )
    context.close()


def main() -> None:
    if len(sys.argv) > 2:
        raise SystemExit("usage: uv run scripts/verify-site.py [release]")
    built = json.loads(MANIFEST.read_text(encoding="utf-8"))["release"]
    release = sys.argv[1] if len(sys.argv) == 2 else built
    check(release == built, "the requested release differs from the built site")
    with sync_playwright() as playwright:
        browser, browser_name = launch_browser(playwright)
        try:
            profiles = [
                (path, verify_page(browser, path, kind, release, activate))
                for path, kind, activate in PAGES
            ]
            verify_cross_tab_activation(browser)
            if os.environ.get("LEAF_VERIFY_AGENT") == "1":
                verify_agent_turn(browser, release)
        finally:
            browser.close()
    print("Leaf startup profile (observed, not a pass/fail budget):")
    for path, profile in profiles:
        print(startup_line(path, profile))
    print(f"✓ leaf.page serves release {release} in {browser_name}")


if __name__ == "__main__":
    main()
