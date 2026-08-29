"""Lifecycle and trusted inputs for one browser color scheme."""

from pathlib import Path
from urllib.parse import urljoin, urlsplit

from leaf.files import version_num
from leaf.render_checks import (
    RENDER_VIEWPORT,
    SERVED_TIMEOUT_MS,
    evaluate_probe,
    install_window_errors,
    wait_for_probe,
)

from .models import _SchemeContext
from .readings import _read_scheme
from .reporting import _scheme_result


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


RESIZE_OBSERVER_ERROR = "window error: ResizeObserver loop"


def resize_observer_error(text: str) -> bool:
    return text.startswith(RESIZE_OBSERVER_ERROR)


def recurring_resize_observer_error(unit: str) -> str:
    return f"{RESIZE_OBSERVER_ERROR} notice recurred on the confirming {unit}"


def _render_scheme(browser, url, scheme, served_timeout_ms, opened_pages):
    """Read and report the browser gate for one color scheme."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    page = browser.new_page(viewport=RENDER_VIEWPORT, color_scheme=scheme)
    opened_pages.append(page)
    page._leaf_probe_timeout_ms = served_timeout_ms
    errors = []
    resize_notices = []

    def served_here(path):
        return served(page, url, path, timeout_ms=served_timeout_ms)

    def console_message(message):
        if message.type != "error":
            return
        (resize_notices if resize_observer_error(message.text) else errors).append(
            message.text
        )

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
        # `load`, not `networkidle`: the page holds a request open to hear
        # about news, so the network is never idle and never will be. The
        # wait that matters is the next line, which asks the runtime itself.
        page.goto(url, wait_until="load")
        wait_for_probe(page, "runtimeStarted")
    except PlaywrightTimeout:
        page.close()
        explanations = [*errors, *resize_notices]
        return (
            [
                f"[{scheme}] the runtime never injected its banner — "
                + ("; ".join(explanations) or "and no console error explains why")
            ],
            [],
            False,
        )
    except PlaywrightError as error:
        return probe_failure(error)
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
                + ("; ".join(explanations) or "and no console error explains why")
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
        # The readings in the page mean widgets, so they are handed only those:
        # $keys spells its members in the x- keys' own names, and a sweep over
        # every entry took it for a widget called $keys.
        widgets = {tag: e for tag, e in registry.items() if tag.startswith("lf-")}
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
    # The widgets the log has moved, in the log's order. Both replayed kinds,
    # once: the caught-up stamp counts reports beside actions, so the wait below
    # counts what this holds, and the verbatim reading excuses exactly these.
    touched = [
        e["widget"] for e in state["events"] if e["kind"] in ("action", "report")
    ]
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
    unsettled = []
    replayed = True
    try:
        wait_for_probe(page, "dataApplied", state["data"]["revision"])
    except PlaywrightTimeout:
        replayed = False
        unsettled = [
            (
                "the runtime never presented external data revision "
                f"{state['data']['revision']}"
            )
        ]
    if replayed and touched:
        applied = len(touched)
        try:
            wait_for_probe(page, "logApplied", applied)
        except PlaywrightTimeout:
            replayed = False
            stalled = (
                f"the runtime never finished replaying the log ({applied} action(s))"
            )
            unsettled = [stalled]
    if replayed:
        try:
            wait_for_probe(page, "presented")
        except PlaywrightTimeout:
            replayed = False
            unsettled = [
                "the runtime never presented the page after applying its current state"
            ]
    if replayed:
        try:
            wait_for_probe(page, "pageSettled")
        except PlaywrightTimeout:
            unsettled = [
                "the page never stopped moving: "
                + ", ".join(evaluate_probe(page, "moving"))
            ]
    context = _SchemeContext(
        page=page,
        scheme=scheme,
        errors=errors,
        resize_notices=resize_notices,
        registry=registry,
        widgets=widgets,
        state=state,
        markup=markup,
        here=here,
        earlier=earlier,
        touched=touched,
        replayed=replayed,
        unsettled=unsettled,
    )
    readings = _read_scheme(context)
    page.close()
    return _scheme_result(context, readings)
