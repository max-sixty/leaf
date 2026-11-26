"""Reach leaf.page, or the site `leaf-dev site build` built, from a browser as a user does.

`leaf-dev site verify` and `leaf-dev journey run` open the website's pages through
this module. A page loads with its startup and the errors that stop it observed
(`load_presented`), reads its state through connection resets (`read_state`), and
leaves the edge for a private container when it activates (`activation_url`,
`activation_read`); `agent_session` opens a user session whose container serves a
release, waiting while the edge still serves another release or activation loses its
connection. On this machine,
`local_adapter` builds the site and serves it with the website's Python server,
sharing the host's login, and `local_worker` serves the site `leaf-dev site build`
last wrote (`SITE`) through `wrangler dev`: the Worker and its page container. A build
writes its asset tree and the website's installation beside its output (`asset_site`,
`install_tree`), and holds `site_lock` while it writes.

The browser half, `website.js`, is installed before each navigation beside the
startup evidence every probe shares (`leaf_dev.startup`).
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import IO, NamedTuple, Protocol
from urllib.parse import urlencode, urljoin

import psutil
from playwright.sync_api import (
    APIRequestContext,
    APIResponse,
    BrowserContext,
    Page,
    Response,
)
from playwright.sync_api import Error as PlaywrightError

from leaf.base.findings import Finding
from leaf.pages.render_gate.scheme import collect_page_errors
from leaf.source.render_checks import (
    PageNotReady,
    open_render_context,
    open_render_page,
    wait_until_ready,
)
from leaf_dev import ROOT
from leaf_dev.arms import (
    codex_home,
    codex_program,
    copy_working,
    environment,
    install_codex_plugin,
    run_directory,
)
from leaf_dev.startup import observe_startup as record_startup
from leaf_website import SITE_MANIFEST

# Where `leaf-dev site build` writes the site by default, and verification reads it.
SITE = ROOT / ".tmp" / "site"
# The site build, run from ROOT (`leaf_dev.commands.site.build`).
BUILD_SITE = [sys.executable, "-m", "leaf_dev", "site", "build"]
SCRIPT = Path(__file__).with_suffix(".js")


def asset_site(out: Path) -> Path:
    """The sibling tree exposed through Cloudflare's static asset binding."""
    return out.with_name(f"{out.name}-assets")


def install_tree(out: Path) -> Path:
    """The website's sibling installation: a prepared Leaf and `leaf_website` beside it.

    The build runs its `leaf`, and the container image and `local_adapter` install it
    as the website's server."""
    return out.with_name(f"{out.name}-install")


def site_lock(out: Path) -> Path:
    """The lock a build of `out` holds while it writes, and a reader of it takes."""
    return out.with_name(f"{out.name}.lock")


def serve_site(install: Path) -> list[str]:
    """The website's Python server as its container runs it: `leaf_website` in the
    installation a site build wrote (`install_tree`)."""
    return [
        "uv",
        "run",
        "--project",
        str(install),
        "--package",
        "leaf-website",
        "--no-dev",
        "--frozen",
        "python",
        "-m",
        "leaf_website",
    ]


class AgentSession(NamedTuple):
    """One user session bound to a container serving the requested release."""

    context: BrowserContext
    page: Page
    failures: list[Finding]
    url: str
    state_url: str
    state: dict


def check[T](condition: T | None, message: str) -> T:
    if not condition:
        raise RuntimeError(message)
    return condition


def said(failures: list[Finding]) -> str:
    """Browser errors in their words, for a failure message."""
    return "; ".join(map(str, failures)) or "none"


class HttpAnswer(Protocol):
    @property
    def ok(self) -> bool: ...

    @property
    def status(self) -> int: ...

    def text(self) -> str: ...


def answered[Response: HttpAnswer](response: Response, url: str) -> Response:
    """Hold one API answer to being an answer, quoting what a refusal said (a Leaf
    fault's body is `{"error": "<class>: <message>"}`)."""
    if not response.ok:
        said = response.text().strip()[:400]
        raise RuntimeError(f"{url} returned {response.status}: {said}")
    return response


# Playwright retries a connection reset after 250 ms, doubling each time, so five
# retries keep one read going through about eight seconds of resets. The resets seen
# on the hosted site came before the Worker recorded the request, and the GET is
# idempotent besides.
STATE_RESET_RETRIES = 5


def read_state(
    request: APIRequestContext,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> APIResponse:
    """Read state, retrying through connection resets (`STATE_RESET_RETRIES`).

    HTTP failures still surface through ``answered``. Publish-site's transport
    capture records failed attempts even when the retry succeeds.
    """
    return answered(
        request.get(
            url, headers=headers, timeout=timeout, max_retries=STATE_RESET_RETRIES
        ),
        url,
    )


def observe_startup(page: Page) -> list[Finding]:
    """Every verifier page records milestones and the errors that stop reaching them."""
    record_startup(page)
    page.add_init_script(path=SCRIPT)
    failures: list[Finding] = []
    collect_page_errors(page, failures)
    return failures


def await_presentation(
    page, url: str, failures: list[Finding], timeout: int | None = None
) -> None:
    """Wait until the page has presented the state it read (`wait_until_ready`
    through `presented`); a page that never does names the readiness stage it
    stopped at and the browser errors it raised on the way."""
    try:
        wait_until_ready(page, through="presented", timeout_ms=timeout)
    except PageNotReady as error:
        raise RuntimeError(
            f"{url} never presented: {error}; browser errors: " + said(failures)
        ) from None


def load_presented(
    page: Page, url: str, unloaded: str | None = None
) -> tuple[list[Finding], Response]:
    """Open `url` in `page` as every pass opens a page: watching its startup and the
    errors that stop it (`observe_startup`), requiring the document to load, else
    failing with `unloaded`, and its state to present (`await_presentation`).
    Returns the errors the page raised and the document's response."""
    failures = observe_startup(page)
    response = page.goto(url, wait_until="load")
    check(response is not None and response.ok, unloaded or f"{url} did not load")
    assert response is not None
    await_presentation(page, url, failures)
    return failures, response


def write_fully(fd: int, data: bytes) -> None:
    """Write all of `data` to `fd`, waiting whenever the pipe behind it is full.

    Playwright's Node driver shares this process's stderr and makes the pipe
    non-blocking, so one large write to it can stop partway with `BlockingIOError`.
    """
    view = memoryview(data)
    while view:
        try:
            view = view[os.write(fd, view) :]
        except BlockingIOError:
            select.select([], [fd], [])


@contextmanager
def capture_script_responses(page: Page):
    """Keep the reload's actual script responses if its verification fails.

    The CI log is the retained artifact, so bodies are gzip/base64 with short lines.
    Decode by joining `gzipBase64`, base64-decoding, then gzip-decompressing. These
    are Playwright's decoded response bytes, not a new request or wire compression.
    Only delivery headers are retained; cookies and other credentials are excluded.
    """
    scripts = []
    delivery_headers = {
        "content-type",
        "content-length",
        "content-encoding",
        "etag",
        "cache-control",
        "cf-cache-status",
        "cf-ray",
        "leaf-release",
        "leaf-state-source",
    }

    def finished(request):
        if request.resource_type != "script":
            return
        response = request.response()
        if response is None:
            return
        script = {
            "url": response.url,
            "status": response.status,
            "headers": {
                name: value
                for name, value in response.headers.items()
                if name in delivery_headers
            },
        }
        body = None
        try:
            body = response.body()
        except PlaywrightError as error:
            script["bodyError"] = str(error)
        scripts.append((script, body))

    page.on("requestfinished", finished)
    try:
        yield
    except Exception:
        for script, body in scripts:
            if body is not None:
                script["sha256"] = hashlib.sha256(body).hexdigest()
                encoded = base64.b64encode(gzip.compress(body, mtime=0)).decode("ascii")
                script["gzipBase64"] = [
                    encoded[start : start + 4096]
                    for start in range(0, len(encoded), 4096)
                ]
        evidence = json.dumps(
            {"scriptResponses": [script for script, _ in scripts]}, indent=2
        )
        sys.stderr.flush()
        write_fully(sys.stderr.fileno(), f"{evidence}\n".encode())
        raise
    finally:
        page.remove_listener("requestfinished", finished)


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


def activation_read(context, activation: str) -> APIResponse:
    """The read that allocates this session's container, held to being an answer."""
    return answered(context.request.get(activation), activation)


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
    context = open_render_context(browser)
    page = open_render_page(context)
    failures, _ = load_presented(page, url, f"{url} did not load for its agent")
    passive = read_state(context.request, state_url)
    if direct_agent:
        reached = passive.json().get("release")
        if release is not None and reached != release:
            context.close()
            return served_instead(reached, release)
        return AgentSession(context, page, failures, url, state_url, passive.json())
    activation = activation_url(url, passive.json())
    try:
        activated = activation_read(context, activation)
    except PlaywrightError as error:
        if "read ECONNRESET" not in str(error):
            raise
        context.close()
        return "lost its activation connection"
    except RuntimeError as error:
        context.close()
        return f"failed: {error}"
    check(
        activated.headers.get("leaf-session") == "active",
        f"{activation} did not activate a private container for its agent",
    )
    headers = {"Leaf-Release": release} if release is not None else None
    state_response = read_state(context.request, state_url, headers=headers)
    check(
        state_response.headers.get("leaf-session") == "active",
        f"{state_url} did not reach a private container for its agent",
    )
    # The edge names its own release on every answer, so the release the container
    # runs is the one its state names.
    reached = state_response.json().get("release")
    if release is not None and reached != release:
        context.close()
        return served_instead(reached, release)
    return AgentSession(context, page, failures, url, state_url, state_response.json())


def agent_session(
    browser, release: str | None, *, origin: str, direct_agent: bool = False
) -> AgentSession:
    """Open one user session whose private container is serving `release`, retrying
    with a fresh context for up to 180 s while the edge serves another release or
    activation loses its connection. Nothing here writes."""
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
        context.request.post(urljoin(endpoint, "start"), data=event),
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
def logged(log: Path) -> Generator[IO[str]]:
    """Collect a local server's output in `log`, printing it beside any failure."""
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as output:
        try:
            yield output
        except BaseException:
            output.flush()
            sys.stderr.flush()
            write_fully(sys.stderr.fileno(), log.read_bytes())
            raise


@contextmanager
def serving(
    command: list[str],
    output: IO[str],
    ready: Callable[[], str | None],
    patience: float,
    **popen,
) -> Generator[str]:
    """Run a local server and yield the origin its readiness probe confirms."""
    with subprocess.Popen(
        command, stdout=output, stderr=subprocess.STDOUT, **popen
    ) as server:
        try:
            deadline = time.monotonic() + patience
            while (origin := ready()) is None:
                check(server.poll() is None, f"{command[0]} exited before serving")
                check(time.monotonic() < deadline, f"{command[0]} did not serve")
                time.sleep(0.1)
            yield origin
        finally:
            if server.poll() is None:
                server.terminate()
            server.wait()


def ready_origin(log: Path, event: str, path: str) -> str | None:
    """The child's announced origin once its HTTP endpoint answers."""
    origin = announced_origin(log, event)
    return origin if origin is not None and answers(f"{origin}{path}") else None


@contextmanager
def local_adapter() -> Generator[tuple[str, str]]:
    """Build the site and serve it with the website adapter sharing the host's login.

    Its isolated Codex home and normal Leaf plugin installation are removed with
    the adapter's pages and task history."""
    out = run_directory(ROOT / ".tmp" / "site-verify")
    log = out / "website-adapter.log"
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
        release = json.loads((site / SITE_MANIFEST).read_text())["release"]
        child_env = environment(
            CODEX_HOME=str(home),
            LEAF_SITE_ROOT=str(site),
            XDG_STATE_HOME=str(root / "state"),
        )
        # Building the pages ran this installation's launcher and created its
        # environment. Native marketplace installation copies the whole payload,
        # so give it only the prepared plugin, as the container image does.
        plugin = root / "leaf-plugin"
        shutil.copytree(
            install_tree(site),
            plugin,
            ignore=shutil.ignore_patterns(".venv", "__pycache__"),
        )
        with logged(out / "plugin-install.log") as install_output:
            install_codex_plugin(
                codex_program(), plugin, cwd=ROOT, env=child_env, output=install_output
            )
        with serving(
            [*serve_site(install_tree(site)), "--port", "0"],
            output,
            lambda: ready_origin(log, "container_http_ready", "/health"),
            30,
            cwd=ROOT,
            env=child_env,
        ) as origin:
            yield origin, release


def docker_command(*arguments: str, input: str | None = None, timeout: int = 30) -> str:
    """Run one verifier-owned Docker operation, surfacing daemon stalls and output."""
    command = ["docker", *arguments]
    try:
        result = subprocess.run(
            command,
            input=input,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        detail = error.stderr or error.stdout or "no output"
        raise RuntimeError(
            f"{' '.join(command)} timed out after {timeout}s: {detail}"
        ) from error
    check(
        result.returncode == 0,
        f"{' '.join(command)} failed:\n{result.stdout}{result.stderr}",
    )
    return result.stdout


def container_filter(name: str) -> str:
    """The `docker ps` filter for the containers a local Worker named `name` runs.

    Miniflare gives each `wrangler dev` session a hex id, and workerd names each
    container `workerd-<session>-<actor key>`, whose key begins with the Worker's name.
    """
    return f"name=^workerd-[0-9a-f]+-{name}-"


@dataclass(frozen=True)
class LocalWorker:
    """One local Worker and only the Docker containers its private name owns."""

    origin: str
    release: str
    name: str
    evidence: Path

    def containers(self, *, include_stopped: bool = False) -> set[str]:
        listed = docker_command(
            "ps",
            *(["--all"] if include_stopped else []),
            "--filter",
            container_filter(self.name),
            "--format",
            "{{json .}}",
        )
        # Miniflare's egress proxy survives independently of the page process. It
        # must remain available while a stopped page is read from its Durable Object.
        return {
            record["ID"]
            for line in listed.splitlines()
            if "cloudflare/proxy-everything"
            not in (record := json.loads(line))["Image"]
        }

    def python(self, container: str, source: str) -> dict:
        check(
            container in self.containers(),
            "the page container is not owned by this verifier",
        )
        result = docker_command(
            "exec",
            "--interactive",
            "--env",
            "LEAF_PAGE_COMMIT=leaf_website.storage",
            container,
            "/app/.venv/bin/python",
            "-",
            input=source,
            timeout=120,
        )
        return json.loads(result.splitlines()[-1])

    def stop(self, container: str) -> None:
        check(
            container in self.containers(), "refusing to stop another run's container"
        )
        stopping = int(time.time())
        docker_command("stop", "--time", "1", container)
        # `docker stop` returns once the container stops running, which can precede
        # the `die` event and the update to the list `docker ps` reads. Wait for
        # that event, so the listing below and the verifier's later readings of
        # it see the container gone.
        with subprocess.Popen(
            [
                "docker",
                "events",
                "--since",
                str(stopping),
                "--filter",
                f"container={container}",
                "--filter",
                "event=die",
                "--format",
                "{{.Action}}",
            ],
            stdout=subprocess.PIPE,
            text=True,
        ) as events:
            try:
                assert events.stdout is not None
                ready, _, _ = select.select([events.stdout], [], [], 30)
                check(
                    bool(ready) and bool(events.stdout.readline()),
                    "the page container did not report its exit",
                )
            finally:
                events.kill()
        check(
            container not in self.containers(),
            "the page container started again after it stopped",
        )
        wait_for_host_network()


@contextmanager
def local_worker() -> Generator[LocalWorker]:
    """Serve the built site through `wrangler dev`: the Worker and its page container.

    Build the image before timing HTTP readiness: a cold dependency download is not
    a Worker startup failure. Wrangler leaves each container's
    `proxy-everything` sidecar running when it exits, so the run serves under a Worker
    name of its own and removes the containers carrying it on the way out. Wrangler
    removes some of them itself as it exits, and may still be removing one when the
    run lists them. So a container already gone or still being removed is no
    failure, and the run removes its image by force, since such a container holds it.
    """
    out = run_directory(ROOT / ".tmp" / "site-verify")
    # Temporary directory suffixes may begin with `_`, which cannot follow a
    # hyphen in a Docker image name. Hex keeps the run identity and uses only
    # characters accepted by both Docker and Wrangler.
    name = f"lv-{out.name.encode().hex()}"
    image_tag = f"{name}:latest"
    log = out / "wrangler-dev.log"
    image = None
    try:
        with (
            tempfile.TemporaryDirectory(prefix="leaf-worker-") as temporary,
            logged(log) as output,
        ):
            root = Path(temporary)
            # Freeze this release. Docker must build from the same private site and
            # installation the edge was built with, even if another run rebuilds
            # .tmp/site.
            context = root / "context"
            copy_working(
                [
                    "worker/Dockerfile",
                    "package.json",
                    "pnpm-lock.yaml",
                    "pnpm-workspace.yaml",
                    "build/*.patch",
                    "worker/codex-config.toml",
                ],
                context,
            )
            from leaf.base.state import flocked

            with flocked(site_lock(SITE)):
                shutil.copytree(SITE, context / ".tmp" / "site")
                shutil.copytree(
                    install_tree(SITE),
                    context / ".tmp" / "site-install",
                    ignore=shutil.ignore_patterns(".venv"),
                )
                shutil.copytree(asset_site(SITE), root / "assets")
            release = json.loads(
                (context / ".tmp" / "site" / SITE_MANIFEST).read_text()
            )["release"]
            # Warm the same Docker build Wrangler runs for production's amd64
            # architecture before the bounded server-readiness check starts.
            # Keep the Dockerfile in Wrangler's config: local image references
            # are pulled from a registry even when Docker already has them.
            subprocess.run(
                [
                    "docker",
                    "build",
                    "--platform",
                    "linux/amd64",
                    "--file",
                    str(context / "worker" / "Dockerfile"),
                    "--tag",
                    image_tag,
                    str(context),
                ],
                cwd=ROOT,
                stdout=output,
                stderr=subprocess.STDOUT,
                check=True,
            )
            image = image_tag
            config = tomllib.loads((ROOT / "worker" / "wrangler.toml").read_text())
            config.pop("env")
            config["name"] = name
            config["main"] = str(ROOT / "worker" / "src" / "index.ts")
            config["assets"]["directory"] = str(root / "assets")
            for container in config["containers"]:
                for build in container["images"].values():
                    build["dockerfile"] = str(context / "worker" / "Dockerfile")
                    build["build_context"] = str(context)
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
                lambda: ready_origin(log, "local_worker_ready", "/"),
                180,
                cwd=ROOT / "worker",
            ) as origin:
                worker = LocalWorker(origin, release, name, out)
                try:
                    yield worker
                except BaseException:
                    # Keep Python's restore/startup evidence beside the Worker
                    # trace before this verifier removes its containers.
                    try:
                        for container in worker.containers(include_stopped=True):
                            print(
                                f"Container {container} log:", file=output, flush=True
                            )
                            subprocess.run(
                                ["docker", "logs", container],
                                stdout=output,
                                stderr=subprocess.STDOUT,
                                check=False,
                                timeout=10,
                            )
                    except (RuntimeError, subprocess.TimeoutExpired) as error:
                        print(f"Cannot collect container logs: {error}", file=output)
                    raise
    finally:
        listed = subprocess.run(
            ["docker", "ps", "--all", "--quiet", "--filter", container_filter(name)],
            capture_output=True,
            text=True,
            check=True,
        )
        if started := listed.stdout.split():
            subprocess.run(
                ["docker", "rm", "--force", *started],
                stdout=subprocess.DEVNULL,
                check=False,
            )
        if image is not None:
            subprocess.run(
                ["docker", "image", "rm", "--force", image],
                stdout=subprocess.DEVNULL,
                check=True,
            )
