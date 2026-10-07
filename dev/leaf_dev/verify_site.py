"""Verify that leaf.page serves one exact, coherent release in a real browser.

    uv run leaf-dev verify-site [TARGET] [--release RELEASE]

The release pass loads three pages, holds each to the release `leaf-dev site` built
(or `--release`), and prints their startup profile. `wrangler` runs it against the
built site through the local Worker and its page container, printing the Worker's log
beside a failure; `.github/workflows/publish-site.yaml` runs it there before deploying
and again against the deployed release.

This module also owns reaching the website for `leaf-dev journey`: a user session
whose private container serves the release (`agent_session`), the website's adapter
on this machine (`local_adapter`), and the local Worker (`local_worker`).
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
from leaf_dev.arms import codex_home, copy_working, environment, run_directory
from leaf_dev.browser import chrome
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
    help="Require this release (default: the one `leaf-dev site` built).",
)
def verify_site(target: str, release: str | None) -> None:
    """Verify a release at TARGET: an origin, or `wrangler` for the built site
    through the local Worker. `leaf-dev journey` runs the agent at either."""
    if target == "wrangler":
        with local_worker() as (origin, built):
            run_verification(
                origin,
                release or built,
                settle_after_activation=wait_for_host_network,
            )
        return
    run_verification(target.rstrip("/"), release or built_release())


def run_verification(
    origin: str,
    release: str,
    *,
    settle_after_activation: Callable[[], None] | None = None,
) -> None:
    """Run the release pass against `origin`."""
    with chrome() as browser:
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
