#!/usr/bin/env python3
"""Verify that leaf.page serves one exact, coherent release in a real browser."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit

from leaf.render_gate.browser import launch_browser
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

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


def verify_agent_turn(browser, release: str) -> None:
    """Require one deployed Codex turn to revise and answer a private page."""
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
    url = f"{ORIGIN}/examples/design-decision/"
    response = page.goto(url, wait_until="load", timeout=120_000)
    check(response is not None and response.ok, f"{url} did not load for its agent")
    await_presentation(page, url, failures)
    state_url = urljoin(url, "api/state")
    state_response = context.request.get(state_url, timeout=120_000)
    check(state_response.ok, f"{state_url} returned {state_response.status}")
    state = state_response.json()
    initial_revision = state["active"]["revision"]
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
    comment = next(
        (
            event
            for event in accepted.get("state", {}).get("events", [])
            if event.get("attempt") == attempt
        ),
        None,
    )
    check(comment is not None, f"{url} did not return its deployment-check comment")

    deadline = time.monotonic() + 300
    reply = None
    current = state
    while time.monotonic() < deadline:
        current_response = context.request.get(
            state_url,
            headers={"Leaf-Layer": layer, "Leaf-Release": release},
            timeout=120_000,
        )
        check(current_response.ok, f"{state_url} returned {current_response.status}")
        current = current_response.json()
        reply = next(
            (
                event
                for event in current.get("events", [])
                if event.get("kind") == "reply" and event.get("parent") == comment["id"]
            ),
            None,
        )
        if current["active"]["revision"] > initial_revision and reply is not None:
            break
        time.sleep(2)
    check(
        current["active"]["revision"] > initial_revision,
        f"{url} agent did not publish a revision"
        + (f"; it replied: {reply['text']}" if reply else ""),
    )
    check(reply is not None, f"{url} agent published but did not reply")
    check(
        "deployment verified" in reply["text"].casefold(),
        f"{url} agent returned an unexpected reply: {reply['text']}",
    )
    page.reload(wait_until="load", timeout=120_000)
    await_presentation(page, url, failures)
    check(not failures, f"{url} reported browser errors: {failures}")
    check(
        page.locator("h1").inner_text() == heading,
        f"{url} did not render the agent's published heading; browser errors: {failures}",
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
