#!/usr/bin/env python3
"""Verify that leaf.page serves one exact, coherent release in a real browser."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit

from leaf.render_gate.browser import launch_browser
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".tmp" / "site" / "_leaf" / "site.json"
ORIGIN = os.environ.get("LEAF_SITE_ORIGIN", "https://leaf.page").rstrip("/")
PAGES = (
    ("/", "product", True),
    ("/examples/design-decision/", "example", True),
    ("/examples/feature-gallery/versions/v1.html", "example", False),
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def activation_url(page_url: str, state: dict) -> str:
    """The private read that moves one reader off the edge and onto a container.

    A passive reader's `/api/state` is answered by the edge, so activation has to
    name a route the canonical server owns, carrying the parameters that route
    requires. This is the projection a tab asks for when it travels to a revision
    it has already observed: a read the page server answers, with no write behind it.
    """
    events = state.get("events") or []
    query = urlencode(
        {
            "revision": state["active"]["revision"],
            "through_seq": events[-1]["seq"] if events else 0,
        }
    )
    return urljoin(page_url, f"api/view?{query}")


def verify_page(browser, path: str, kind: str, release: str, activate: bool) -> None:
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
    url = urljoin(f"{ORIGIN}/", path.lstrip("/"))
    response = page.goto(url, wait_until="load", timeout=120_000)
    check(response is not None and response.ok, f"{url} did not load")
    page.locator("body[data-lf-presented]").wait_for(timeout=30_000)

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
    if not activate:
        context.close()
        return

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


def verify_cross_tab_activation(browser) -> None:
    """One interacting tab must wake another tab sharing its browser session."""
    context = browser.new_context()
    url = f"{ORIGIN}/examples/design-decision/"
    leader = context.new_page()
    follower = context.new_page()
    for page in (leader, follower):
        response = page.goto(url, wait_until="load", timeout=120_000)
        check(response is not None and response.ok, f"{url} did not load")
        page.locator("body[data-lf-presented]").wait_for(timeout=30_000)
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


def main() -> None:
    if len(sys.argv) > 2:
        raise SystemExit("usage: uv run scripts/verify-site.py [release]")
    built = json.loads(MANIFEST.read_text(encoding="utf-8"))["release"]
    release = sys.argv[1] if len(sys.argv) == 2 else built
    check(release == built, "the requested release differs from the built site")
    with sync_playwright() as playwright:
        browser, browser_name = launch_browser(playwright)
        try:
            for path, kind, activate in PAGES:
                verify_page(browser, path, kind, release, activate)
            verify_cross_tab_activation(browser)
        finally:
            browser.close()
    print(f"✓ leaf.page serves release {release} in {browser_name}")


if __name__ == "__main__":
    main()
