"""Lifecycle and trusted inputs for one browser color scheme."""

from pathlib import Path
from urllib.parse import urljoin, urlsplit

from leaf.files import version_num
from leaf.render_checks import (
    SERVED_TIMEOUT_MS,
    evaluate_probe,
    install_window_errors,
    wait_for_presentation,
    wait_for_probe,
)

from .readings import _scheme_findings, _SchemeContext


def served(page, url: str, path: str, timeout_ms: int | None = None):
    """A document this page's own server holds, read from out here.

    The one reader in the render gate that can be given a deadline. `page.evaluate`
    sends the driver no timeout at all — measured on playwright 1.62, an evaluate
    awaiting a fetch that never answers is still running at 200s — so a reading
    taken inside the page is a hang with nothing printed and no way to bound it
    from Python. `page.request` takes one, and shares the browser context's cookie
    jar, so it reads as the same authorized client the page is: the handover key
    rides in the URL and becomes a cookie on the first navigation."""
    timeout_ms = SERVED_TIMEOUT_MS if timeout_ms is None else timeout_ms
    return page.request.get(urljoin(url, path), timeout=timeout_ms)


def previous_stamp(revision: int, versions: list[dict]) -> dict | None:
    """The newest stamped revision before ``revision``, if one exists."""
    earlier = [version for version in versions if version["revision"] < revision]
    return max(earlier, key=lambda version: version["revision"]) if earlier else None


def rendered_revision(url: str, state: dict) -> int:
    """Resolve the immutable revision shown at ``url`` from the public state."""
    name = Path(urlsplit(url).path).name
    if not name:
        return state["active"]["revision"]
    version = version_num(name)
    return next(
        stamped["revision"]
        for stamped in state["versions"]
        if stamped["version"] == version
    )


def _projection_was_applied(failed_stage: str | None) -> bool:
    """Whether the readiness failure happened after authoritative presentation."""
    return failed_stage in (None, "pageSettled")


RESIZE_OBSERVER_ERROR = "window error: ResizeObserver loop"


def resize_observer_error(text: str) -> bool:
    return text.startswith(RESIZE_OBSERVER_ERROR)


def recurring_resize_observer_error(unit: str) -> str:
    return f"{RESIZE_OBSERVER_ERROR} notice recurred on the confirming {unit}"


def console_problem(message) -> str | None:
    """A console entry that says the page did not load cleanly."""
    if message.type == "error":
        return message.text
    if message.type == "warning":
        return f"warning: {message.text}"
    return None


class PreUpgradeTimeout(TimeoutError):
    """The authored-document proof or its release did not finish loading."""


def start_with_pre_upgrade_proof(page, url: str) -> list[str]:
    """Inspect the authored document while its first Leaf entry request is held."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    held = []
    released = False
    stage = "navigation"

    def hold_entry(route):
        if released:
            route.continue_()
        else:
            held.append(route)

    # Keep interception until this page closes. Disabling it at either entry
    # release or document load can strand static or dynamic widget imports.
    page.route("**/leaf.js", hold_entry)
    try:
        page.goto(url, wait_until="commit")
        stage = "authored main"
        page.wait_for_selector("body > main", state="attached")
        if page.locator('script[src$="/leaf.js"]').count() != 1:
            raise RuntimeError("the document has no single canonical Leaf entry")
        stage = "theme stylesheet"
        page.wait_for_function(
            "() => [...document.styleSheets].some((sheet) => "
            "sheet.href?.endsWith('/theme.css'))"
        )
        findings = page.evaluate(
            """() => {
              const main = document.querySelectorAll('body > main');
              const custom = [...document.querySelectorAll('*')]
                .map((element) => element.localName)
                .filter((tag) => tag.includes('-'));
              const upgraded = [...new Set(custom)]
                .filter((tag) => customElements.get(tag));
              const painted = ['lf-upgraded', 'lf-applied', 'lf-presented']
                .filter((name) => document.body.hasAttribute('data-' + name));
              const box = main[0]?.getBoundingClientRect();
              return [
                ...(main.length === 1 ? [] : ['authored document has ' + main.length + ' direct main elements']),
                ...(upgraded.length ? ['widgets upgraded before Leaf entry ran: ' + upgraded.join(', ')] : []),
                ...(painted.length ? ['runtime readiness appeared before Leaf entry ran: ' + painted.join(', ')] : []),
                ...(!box || box.width <= 0 || box.height <= 0
                  ? ['authored main has no measurable pre-upgrade layout']
                  : []),
              ];
            }"""
        )
        if len(held) != 1:
            raise RuntimeError("the browser did not request one canonical Leaf entry")
        stage = "release of the Leaf entry"
        released = True
        held[0].continue_()
        stage = "document load after releasing Leaf"
        page.wait_for_load_state("load")
        return findings
    except PlaywrightTimeout as error:
        raise PreUpgradeTimeout(f"the browser timed out waiting for {stage}") from error
    finally:
        if held and not released:
            released = True
            held[0].continue_()


def _render_scheme(browser, url, scheme, viewport, served_timeout_ms, opened_pages):
    """Read and report the browser gate for one color scheme and viewport."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    page = browser.new_page(viewport=viewport, color_scheme=scheme)
    opened_pages.append(page)
    page._leaf_probe_timeout_ms = served_timeout_ms
    errors = []
    resize_notices = []
    pending_requests = set()
    page.on("request", lambda request: pending_requests.add(request))
    page.on("requestfinished", lambda request: pending_requests.discard(request))
    page.on("requestfailed", lambda request: pending_requests.discard(request))

    def served_here(path):
        return served(page, url, path, timeout_ms=served_timeout_ms)

    def console_message(message):
        problem = console_problem(message)
        if problem is None:
            return
        (resize_notices if resize_observer_error(problem) else errors).append(problem)

    def probe_failure(error):
        page.close()
        return (
            [
                (
                    f"[{scheme}] the browser probe module failed: "
                    f"{str(error).strip().splitlines()[0]}"
                )
            ],
            [],
            False,
        )

    page.on("console", console_message)
    page.on("pageerror", lambda e: errors.append(str(e)))
    # The console's own word for a bad response is "Failed to load resource",
    # which names nothing; carry the status and URL so a failure says what
    # went missing.
    page.on(
        "response",
        lambda r: errors.append(f"{r.status} {r.url}") if r.status >= 400 else None,
    )
    install_window_errors(page)
    try:
        # Hold the entry in this navigation: this is the only point at which
        # pre-upgrade authored structure exists without racing module execution.
        pre_upgrade = start_with_pre_upgrade_proof(page, url)
        wait_for_probe(page, "runtimeStarted")
    except (PreUpgradeTimeout, PlaywrightTimeout) as error:
        explanations = [*errors, *resize_notices]
        if pending_requests:
            addresses = [urlsplit(request.url) for request in pending_requests]
            explanations.append(
                "unfinished requests: "
                + ", ".join(
                    sorted(
                        {
                            address._replace(
                                netloc=address.netloc.rsplit("@", 1)[-1],
                                query="",
                                fragment="",
                            ).geturl()
                            for address in addresses
                        }
                    )
                )
            )
        failure = (
            str(error)
            if isinstance(error, PreUpgradeTimeout)
            else "the runtime never injected its banner"
        )
        page.close()
        return (
            [
                f"[{scheme}] {failure} — "
                + ("; ".join(explanations) or "and no console message explains why")
            ],
            [],
            False,
        )
    except PlaywrightError as error:
        return probe_failure(error)
    except RuntimeError as error:
        page.close()
        return ([f"[{scheme}] pre-upgrade proof failed: {error}"], [], False)
    # Every reading below is of a settled page. The widget layer writes half the
    # document, so a box measured while it is still drawing belongs to no version of
    # the page — which is the stamp `version export` waits on for the same reason.
    try:
        wait_for_probe(page, "upgraded")
    except PlaywrightTimeout:
        page.close()
        explanations = [*errors, *resize_notices]
        return (
            [
                f"[{scheme}] the widget layer never finished upgrading — "
                + ("; ".join(explanations) or "and no console message explains why")
            ],
            [],
            False,
        )
    except PlaywrightError as error:
        return probe_failure(error)
    # The served documents every reading below is asked against, read once each
    # (`served` says why they are read from out here rather than fetched inside
    # the page). The registry alone used to be fetched seven times a scheme, to
    # answer seven questions about one document. What the readings get now is
    # data, so most of them are plain synchronous DOM walks with nothing left in
    # them to await, let alone hang in.
    try:
        registry = served_here("/registry.json").json()
        # The readings in the page consume element declarations, so they are handed
        # only those:
        # $keys spells its members in the x- keys' own names, and a sweep over
        # every declaration took it for a widget called $keys.
        declarations = {tag: e for tag, e in registry.items() if tag.startswith("lf-")}
        state = served_here("/api/state").json()
        markup = served_here(urlsplit(url).path).text()
        # Every replay and conflict check is bounded by immutable revision.
        # A stamped URL resolves through the stamp map; an exact source preview
        # uses the synthetic active revision exposed only by its preview server.
        here = rendered_revision(url, state)
        before = previous_stamp(here, state["versions"])
        earlier = served_here(before["url"]).text() if before else None
    except PlaywrightTimeout as e:
        page.close()
        # The first line only: the rest is playwright's call log, which says
        # nothing about the page that a reader of this failure needs.
        return (
            [
                *[f"[{scheme}] console: {error}" for error in errors],
                *[f"[{scheme}] console: {notice}" for notice in resize_notices],
                (f"[{scheme}] the server stopped answering: {str(e).splitlines()[0]}"),
            ],
            [],
            False,
        )
    # The caught-up stamp counts reports beside actions, so the readiness wait counts
    # that same set. Nothing else treats an event's owner as a special case.
    applied = sum(e["kind"] in ("action", "report") for e in state["events"])
    # Every reading below is of a page at rest, and the upgrade stamp above is
    # one part of that. The first read runs beside upgrade, but its answer may still
    # be pending when the stamp lands; a gate reading there sees the authored board,
    # the unanswered question and the body the reader has since rewritten — a page
    # nobody is shown. The caught-up stamp is the log's answer to that, and the frame
    # it lands in is the first frame of whatever the replay set moving, a replay past
    # the presentation boundary moving rather than teleporting. Both waits are taken in
    # both schemes, because every reading below has boxes or words in it. The
    # windows open under load alone, which is how one page passed at a desk and
    # reported words drawn over words under a full suite ("The page finishes
    # twice", in the layer's own CLAUDE.md).
    failed_stage = wait_for_presentation(
        page, state["data"]["revision"], applied, settled=True
    )
    replayed = _projection_was_applied(failed_stage)
    if failed_stage == "dataApplied":
        unsettled = [
            (
                "the runtime never presented external data revision "
                f"{state['data']['revision']}"
            )
        ]
    elif failed_stage == "logApplied":
        unsettled = [
            f"the runtime never finished replaying the log ({applied} action(s))"
        ]
    elif failed_stage == "presented":
        unsettled = [
            "the runtime never presented the page after applying its current state"
        ]
    elif failed_stage == "pageSettled":
        unsettled = [
            "the page never stopped moving: "
            + ", ".join(evaluate_probe(page, "moving"))
        ]
    else:
        unsettled = []
    context = _SchemeContext(
        page=page,
        scheme=scheme,
        errors=[*errors, *[f"pre-upgrade: {item}" for item in pre_upgrade]],
        resize_notices=resize_notices,
        registry=registry,
        declarations=declarations,
        state=state,
        markup=markup,
        here=here,
        earlier=earlier,
        replayed=replayed,
        unsettled=unsettled,
    )
    found, notices = _scheme_findings(context)
    page.close()
    return found, notices, True
