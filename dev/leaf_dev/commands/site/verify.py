"""Verify that leaf.page serves one exact, coherent release in a real browser.

    uv run leaf-dev site verify [TARGET] [--release RELEASE] [--wait SECONDS]

The release pass loads three pages, holds each to the release `leaf-dev site build` built
(or `--release`), and prints their startup profile. `website-worker` runs it against
the built site through the local Worker and its page container, printing the Worker's
log beside a failure. That local pass also restores a private document, comment and
choice while its page container is stopped, then wakes the container for a mechanical
write after removing its mutable source and log to prove external-record recovery.
`.github/workflows/publish-site.yaml` runs the local pass before deploying and the
release pass again against the deployed release.

A deployment reaches Cloudflare's edge within moments, and each session object runs
the deployed image from its first request after the deploy on. A pass starts sessions
of its own, so it verifies once the edge serves the release.
`--wait` owns that wait for every deploy: it reruns the whole pass until one verifies
or its seconds run out, and the last failure is the report.
"""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable
from urllib.parse import urljoin, urlsplit

import click
from playwright.sync_api import Error as PlaywrightError

from leaf.source.render_checks import open_render_context, open_render_page
from leaf_dev.browser import go_to_threads, headless_shell, panel_view
from leaf_dev.startup import startup_line, startup_profile, startup_reading
from leaf_dev.website import (
    SITE,
    AgentSession,
    LocalWorker,
    activation_read,
    activation_url,
    answered,
    check,
    load_presented,
    local_worker,
    read_state,
    said,
    user_session,
    wait_for_host_network,
)
from leaf_website import SITE_MANIFEST

PAGES = (
    ("/", "product", True),
    ("/examples/triage-board/", "example", True),
    ("/examples/feature-gallery/versions/v1.html", "example", False),
)


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
    context = open_render_context(browser)
    page = open_render_page(context)
    url = urljoin(f"{origin}/", path.lstrip("/"))
    with page.expect_response(
        lambda response: (
            response.url.endswith("/api/performance")
            and response.request.method == "POST"
        )
    ) as startup_report:
        failures, _ = load_presented(page, url)
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
    check(not failures, f"{url} reported browser errors: {said(failures)}")
    startup = startup_reading(page)
    if not activate:
        context.close()
        return startup

    state_url = urljoin(url, "api/state")
    passive_response = read_state(context.request, state_url)
    check(
        passive_response.headers.get("leaf-session") == "passive",
        f"{state_url} left the edge before interaction",
    )
    activation = activation_url(url, passive_response.json())
    # No wait here: `--wait` reruns the whole pass until the release verifies.
    activation_response = activation_read(context, activation)
    check(
        activation_response.headers.get("leaf-session") == "active",
        f"{activation} did not activate a private container",
    )
    check(
        isinstance(activation_response.json().get("document"), dict),
        f"{activation} returned no document",
    )
    if settle_after_activation is not None:
        settle_after_activation()
    state_response = read_state(
        context.request,
        state_url,
        headers={"Leaf-Layer": identity["layer"], "Leaf-Release": release},
    )
    check(
        state_response.headers.get("leaf-session") == "active",
        f"{state_url} did not reach a private container",
    )
    state = state_response.json()
    check(
        state.get("release") == release,
        f"{state_url} reached a container on another release",
    )
    check(
        state.get("publication", {}).get("kind") == kind,
        f"{state_url} returned the wrong page kind",
    )
    if path == "/examples/triage-board/":
        neighbor_url = urljoin(f"{origin}/", "how-it-works/")
        neighbor = open_render_page(context)
        with neighbor.expect_response(
            lambda response: (
                response.url.endswith("/api/performance")
                and response.request.method == "POST"
            )
        ) as neighbor_report:
            neighbor_failures, neighbor_response = load_presented(
                neighbor,
                neighbor_url,
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
            f"{neighbor_url} reported browser errors: {said(neighbor_failures)}",
        )
        neighbor.close()
    context.close()
    return startup


def verify_cross_tab_activation(
    browser, *, origin: str, settle_after_activation: Callable[[], None] | None = None
) -> None:
    """One interacting tab must wake another tab sharing its browser session."""
    context = open_render_context(browser)
    if settle_after_activation is not None:
        # Allocate this identity's local container before Chrome's interaction.
        # Docker changes host interfaces; the page under test must remain passive.
        neighbor = f"{origin}/"
        state_url = urljoin(neighbor, "api/state")
        state = read_state(context.request, state_url).json()
        activation_read(context, activation_url(neighbor, state))
        settle_after_activation()
    url = f"{origin}/examples/triage-board/"
    state_url = urljoin(url, "api/state")
    leader = open_render_page(context)
    follower = open_render_page(context)
    for page in (leader, follower):
        load_presented(page, url)
    passive = read_state(context.request, state_url)
    check(
        passive.headers.get("leaf-session") == "passive",
        f"{state_url} activated before the cross-tab interaction",
    )
    follower.evaluate("window.__leafVerifier.observeCrossTabActivation")
    # Admit the response that really allocated this session, not a synthetic active
    # header whose background news request could allocate after this fixture closes.
    activation = activation_url(url, passive.json())
    with leader.expect_response(
        lambda response: response.url == activation
    ) as response:
        leader.evaluate(
            """(url) => {
                window.__leafVerifier.activateSession(url).catch(console.error);
            }""",
            activation,
        )
    activated = answered(response.value, activation).json()
    check(
        isinstance(activated.get("document"), dict),
        "activation returned no document",
    )
    follower.wait_for_function("window.__leafVerifier.crossTabActivated")
    context.close()


def verify_saved_state(browser, worker: LocalWorker) -> dict[str, dict]:
    """A cold browser restores a private page while its page container is stopped.

    Fixture writes use Python's canonical transaction inside this run's container;
    they need no model turn. The browser then gets a revised document, its captured
    stylesheet, a saved comment and choice from durable delivery. A mechanical media
    write wakes the container and proves the canonical record is restored for writes.
    Elapsed time is a profile, while an unchanged running-container set is the gate.
    """
    url = f"{worker.origin}/examples/heat-loss/"
    state_url = urljoin(url, "api/state")
    before = worker.containers()
    session = user_session(browser, url, state_url, worker.release)
    if not isinstance(session, AgentSession):
        raise RuntimeError(f"saved-state fixture could not activate: {session}")
    cookies = session.context.cookies()
    session.context.close()
    wait_for_host_network()
    allocated = worker.containers() - before
    check(len(allocated) == 1, f"fixture allocated {len(allocated)} page containers")
    container = allocated.pop()
    seeded = worker.python(container, SAVED_STATE_FIXTURE)
    # Read through the real HTTP owner too; it must agree with the fixture's commits.
    context = open_render_context(browser)
    context.add_cookies(cookies)
    current = read_state(context.request, state_url).json()
    check(
        current["active"]["revision"] == seeded["revision"],
        "private revision was not activated",
    )
    warm_page = open_render_page(context)
    warm_failures, _ = load_presented(
        warm_page, url, "warm private document did not load"
    )
    check(not warm_failures, f"warm saved-state browser errors: {warm_failures}")
    warm_profile = startup_reading(warm_page)
    context.close()
    # Docker may retain a stopped container's writable layer. Remove the fixture's
    # mutable source and log so the next write must restore the external record,
    # just as a replacement container must. Published baseline assets stay intact.
    worker.python(
        container,
        SAVED_STATE_PAGE
        + "\n(page / 'index.html').unlink()\n(page / 'events.jsonl').unlink()\nprint('{}')\n",
    )
    worker.stop(container)
    asleep = worker.containers()
    context = open_render_context(browser)
    context.add_cookies(cookies)
    page = open_render_page(context)
    failures, response = load_presented(
        page, url, "saved private document did not load"
    )
    check(
        response.headers.get("leaf-state-source") == "durable",
        "private document woke its container",
    )
    page.locator("#saved-state-recall").wait_for(state="visible")
    page.locator("#heat-opt-window[selected]").wait_for(state="visible")
    state_response = read_state(context.request, state_url)
    check(
        state_response.headers.get("leaf-state-source") == "durable",
        "saved state woke its container",
    )
    state = state_response.json()
    check(
        {seeded["comment"], seeded["choice"]}
        <= {event["id"] for event in state["events"]},
        "saved events were not restored",
    )
    resource_url = page.locator('link[href*="saved-state-recall.css"]').get_attribute(
        "href"
    )
    check(
        resource_url is not None and "/revisions/" in resource_url,
        "private stylesheet was not revision scoped",
    )
    resource = answered(context.request.get(urljoin(url, resource_url)), resource_url)
    check(
        resource.headers.get("leaf-state-source") == "durable",
        "private revision resource woke its container",
    )
    check(
        resource.text() == seeded["stylesheet"], "private revision stylesheet changed"
    )
    revision_url = urljoin(url, f"revisions/{seeded['revision_name']}")
    revision = answered(context.request.get(revision_url), revision_url)
    check(
        revision.headers.get("leaf-state-source") == "durable",
        "private revision document woke its container",
    )
    check(
        "Saved private document" in revision.text(),
        "private revision document was lost",
    )
    check(
        worker.containers() == asleep, "reading saved content started a page container"
    )
    profile = startup_reading(page)
    # Media ingestion uses the same canonical write transaction but dispatches no
    # agent. It proves that reads did not replace the record the next writer uses.
    uploaded = answered(
        context.request.post(
            urljoin(url, "api/media"),
            data=base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jGbcAAAAASUVORK5CYII="
            ),
            headers={
                "Content-Type": "image/png",
                "Leaf-Layer": state["layer"]["generation"],
                "Leaf-Release": worker.release,
            },
        ),
        urljoin(url, "api/media"),
    )
    check(uploaded.json().get("path"), "the next write did not upload media")
    wait_for_host_network()
    resumed = read_state(context.request, state_url).json()
    check(
        {seeded["comment"], seeded["choice"]}
        <= {event["id"] for event in resumed["events"]},
        "the next write lost saved events",
    )
    check(
        resumed["active"]["revision"] == seeded["revision"],
        "the next write lost the private document",
    )
    check(worker.containers() != asleep, "the mutation did not wake the container")
    # Opening the thread focuses its reply box, and a text box's focus starts the
    # session's container (`prewarmContainer`), so it comes after the reads and
    # the write above, which must each find the container stopped.
    go_to_threads(page)
    page.locator(f'.lf-fp-thread[data-lf-key="{seeded["comment"]}"]').click()
    page.locator(panel_view("thread")).get_by_text(
        "Saved before the container stopped.", exact=True
    ).wait_for(state="visible")
    check(not failures, f"saved-state browser errors: {failures}")
    context.close()
    return {"running": warm_profile, "stopped": profile}


# Runs only in a verifier-owned container. Admission and publication are the same
# Python owners used by HTTP and the hosted agent; no fake state or model is involved.
SAVED_STATE_PAGE = """
import json, os
from pathlib import Path
from leaf_website import SITE_MANIFEST
root = Path(os.environ["LEAF_SITE_ROOT"])
manifest = json.loads((root / SITE_MANIFEST).read_text())
page = root / manifest["pages"]["/examples/heat-loss"]["directory"]
"""
SAVED_STATE_FIXTURE = (
    SAVED_STATE_PAGE
    + r"""
from leaf.records.event_contracts import append_admitted
from leaf.base.files import latest_revision, revision_path
from leaf.records.revisioning import activate_source
from leaf.records.transaction import PageTransaction
stylesheet = "#saved-state-recall { font-weight: 600; }\n"
(page / "page").mkdir(exist_ok=True)
(page / "page/saved-state-recall.css").write_text(stylesheet)
source = (page / "index.html").read_text()
source = source.replace("</head>", '<link rel="stylesheet" href="/page/saved-state-recall.css"></head>')
source = source.replace("</main>", '<p id="saved-state-recall">Saved private document</p></main>')
(page / "index.html").write_text(source)
activation = activate_source(page)
if activation.error:
    raise RuntimeError(activation.error)
revision = latest_revision(page)
with PageTransaction(page) as transaction:
    choice, _ = append_admitted(transaction, {"kind": "action", "author": "user", "revision": revision, "widget": "heat-first", "action": "choose", "detail": {"value": ["heat-opt-window"]}, "answered": True})
    comment, _ = append_admitted(transaction, {"kind": "comment", "author": "user", "revision": revision, "text": "Saved before the container stopped."})
print(json.dumps({"revision": revision, "revision_name": revision_path(page, revision).name, "comment": comment["id"], "choice": choice["id"], "stylesheet": stylesheet}))
"""
)


def built_release() -> str:
    """The release `leaf-dev site build` last built."""
    return json.loads((SITE / SITE_MANIFEST).read_text(encoding="utf-8"))["release"]


@click.command("verify")
@click.argument("target", default="https://leaf.page")
@click.option(
    "--release",
    help="Require this release (default: the one `leaf-dev site build` built).",
)
@click.option(
    "--wait",
    type=int,
    default=0,
    metavar="SECONDS",
    help="Rerun a failed pass until one verifies or SECONDS pass.",
)
def verify_site(target: str, release: str | None, wait: int) -> None:
    """Verify a release at TARGET: an origin, or `website-worker` for the built site
    through the local Worker. `leaf-dev journey run` runs the agent at either."""
    deadline = time.monotonic() + wait
    while True:
        try:
            verify_target(target, release)
            return
        except (RuntimeError, PlaywrightError) as error:
            if time.monotonic() >= deadline:
                raise
            print(f"Not verified yet, retrying: {error}", flush=True)
            time.sleep(10)


def verify_target(target: str, release: str | None) -> None:
    """One release pass at TARGET."""
    if target == "website-worker":
        with local_worker() as worker:
            run_verification(
                worker.origin,
                release or worker.release,
                settle_after_activation=wait_for_host_network,
                worker=worker,
            )
        return
    run_verification(target.rstrip("/"), release or built_release())


def run_verification(
    origin: str,
    release: str,
    *,
    settle_after_activation: Callable[[], None] | None = None,
    worker: LocalWorker | None = None,
) -> None:
    """Run the release pass against `origin`, including stopped-container reads locally."""
    profiles = {}
    with headless_shell() as browser:
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
            profiles[path] = startup_profile(profile)
            print(startup_line(path, profile), flush=True)
        verify_cross_tab_activation(
            browser, origin=origin, settle_after_activation=settle_after_activation
        )
        if worker is not None:
            recalled = verify_saved_state(browser, worker)
            for phase, profile in recalled.items():
                profiles[f"saved-state-{phase}"] = startup_profile(profile)
                print(
                    startup_line(f"saved state, container {phase}", profile), flush=True
                )
    if worker is not None:
        output = worker.evidence / "startup.json"
        output.write_text(
            json.dumps({"release": release, "profiles": profiles}, indent=2) + "\n"
        )
        print(f"Startup evidence: {output}", flush=True)
    print(f"✓ {origin} serves release {release}")
