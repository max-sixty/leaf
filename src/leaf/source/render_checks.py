"""Named browser probes, and the waits built on them, shared by the render gate and the
test suite."""

import time
from pathlib import Path
from urllib.parse import urljoin

from leaf.base.schema import RENDER_CHECKS_DIR

# The fixed desktop window, sized as a laptop's, since many readers get a window about
# 540-730px tall. The suite reads pages here, and so does `page check --render` where
# the user's own window is unknown or the caller pins this one
# (`render_gate.command.desktop_viewport`).
RENDER_VIEWPORT = {"width": 1280, "height": 720}

# The bound on one probe or request, sized for an oversubscribed host rather than an
# idle one: it separates a wedged preview, which it turns into a useful failure rather
# than an unbounded evaluate, from a machine that has not got there yet. At Playwright's
# own 30s, browser tests on a host stacked with other sessions' suites can time out in a
# different place each run and pass alone, and re-running a red run whole adds the load
# that failed it. A longer bound costs only a slower failure for a real hang.
SERVED_TIMEOUT_MS = 120_000
# How long a page handover may go without progress before the page counts as wedged.
# A handover is the wait, from navigation, for the page to state every readiness fact
# (`wait_until_ready`), and `HandoverProgress` says what counts as progress.
# `SERVED_TIMEOUT_MS` bounds one request or one probe, and a handover is all of a
# page's work at once. The bound is on progress rather than on the whole handover,
# because the whole grows with the page: each live sample a check starts loads a page
# of its own, three at a time (`MAX_LOADING_SAMPLES` in runtime/host/sample.js), so a
# gallery of them on a starved machine takes minutes while its samples keep landing.
# A bound on the whole would fail such a page on any machine slow enough, and an agent
# checking it on a busy machine would read a false failure. A bound on progress need
# only outlast the page's slowest arrival, such as one sample's whole page, which counts
# as one arrival of the page holding it until it has arrived. Waiting longer weakens no
# claim, since the readiness facts say the same whenever they arrive; the bound only
# separates a page that has stopped from a machine that has not got there yet.
HANDOVER_DEADLINE_MS = 240_000
# How often a probe wait re-reads its fact. The waits poll on a timer rather than on
# animation frames (see `_load_probes`), and most waits are a frame or a settle, so the
# interval is added to what they wait for: at 16 ms, `one_frame` took about 22 ms where
# a Promise resolved by the frame takes 14, and at 4 ms it took 14 too. A read is one
# synchronous call, so polling this often costs the page nothing it would notice.
PROBE_POLL_MS = 4

PROBE_ROOT = Path(__file__).with_name("render-checks")
PROBE_ROUTE = f"/{RENDER_CHECKS_DIR}/index.js"
DRIVER_SOURCE = PROBE_ROOT / "driver.js"
WINDOW_ERRORS_SOURCE = PROBE_ROOT / "init.js"
PROBE_SOURCES = {
    f"/{RENDER_CHECKS_DIR}/{source.name}": source
    for source in sorted(PROBE_ROOT.glob("*.js"))
    if source != DRIVER_SOURCE
}

_DRIVER_PRESENT = "() => Boolean(globalThis.__leafRenderDriver)"
# Null when this document has no driver yet: one opened before the driver was installed.
_LOAD_PROBES = "route => globalThis.__leafRenderDriver?.load(route) ?? null"
# Whether the probe load has settled, arrived or failed. A wait's predicate must not
# throw: Playwright's poller then rejects a promise the page never handles, so the page
# hears its own unhandled rejection, which the runtime reports as a page fault, and
# that echo races the wait's rejection to the reader collecting the page's console.
_PROBES_SETTLED = (
    f"route => {{ try {{ return ({_LOAD_PROBES})(route); }} catch {{ return true; }} }}"
)
_PROBE = "call => globalThis.__leafRenderDriver.call(call)"
_REQUEST_FRAME = "() => globalThis.__leafRenderDriver?.requestFrame() ?? null"
_FRAME_PRESENTED = "asked => globalThis.__leafRenderDriver.framePresented(asked)"
_RENDERING_SETTLED = """facts => {
  const state = globalThis.__leafRenderDriver.renderingState();
  return (facts ?? Object.keys(state)).every(fact => state[fact]);
}"""


# Every context and page Leaf's code opens outside the suite, a developer tool's
# included, comes from one of these two openers
# (`test_the_pages_leaf_opens_take_the_served_deadline`). Each sets the default on the
# context, which its pages and its `request` calls inherit, so every Playwright wait
# that names no deadline takes `SERVED_TIMEOUT_MS` rather than Playwright's own 30s,
# which a page's `load` overruns on a starved host. A default a caller then sets on
# the page itself wins over the context's.


def open_render_context(browser, **options):
    """A new context from `browser`, opened with Playwright's `new_context` `options`,
    whose waits take `SERVED_TIMEOUT_MS`, and `expect`'s too (`bound_expectations`)."""
    context = browser.new_context(**options)
    context.set_default_timeout(SERVED_TIMEOUT_MS)
    bound_expectations()
    return context


def open_render_page(opener, **options):
    """A new page from `opener`, a browser or a context, opened with Playwright's
    `new_page` `options`, in a context whose waits take `SERVED_TIMEOUT_MS`, and
    `expect`'s too (`bound_expectations`)."""
    page = opener.new_page(**options)
    page.context.set_default_timeout(SERVED_TIMEOUT_MS)
    bound_expectations()
    return page


def bound_expectations() -> None:
    """Give every Playwright `expect` in this process that names no deadline
    `SERVED_TIMEOUT_MS` in place of Playwright's own five seconds, which an
    expectation on a starved host overruns. Playwright keeps this default for the
    whole process, not for a page or a context. The suite sets it once
    (`render_harness`); Leaf's tools share no entry point but the openers above, so
    each opener sets it."""
    from playwright.sync_api import expect

    expect.set_options(timeout=SERVED_TIMEOUT_MS)


def _timeout(page, timeout_ms: int | None) -> int:
    page = getattr(page, "page", page)
    return timeout_ms or getattr(page, "_leaf_probe_timeout_ms", SERVED_TIMEOUT_MS)


def install_driver(page) -> None:
    """Install the guarded document-side probe driver before navigation."""
    # A frame uses its containing page's initialization scripts; evaluations and
    # probe imports remain in the frame's own document.
    page = getattr(page, "page", page)
    if getattr(page, "_leaf_render_driver_installed", False):
        return
    page.add_init_script(path=DRIVER_SOURCE)
    page._leaf_render_driver_installed = True


def is_runtime_entry(request) -> bool:
    """Whether this request names its document's delivered runtime entry.

    The delivery's bootstrap marker precedes loadable resources. Read it without
    waiting for the parser: a classic authored script can also be named leaf.js.
    """
    entry = request.frame.evaluate("""() => {
      const entry = document.querySelector('script[data-lf-entry]')?.dataset.lfEntry;
      return entry ? new URL(entry, location.href).href : null;
    }""")
    return request.url == entry


def observe_output_documents(page) -> None:
    """Capture producer publications before the checked document or a sample upgrades.

    The binding retains values outside their realm, including a disposed sample.
    Only render tools install it; the ordinary runtime retains no publication history.
    """
    from playwright.sync_api import Error as PlaywrightError

    if hasattr(page, "_leaf_output_values"):
        return
    install_driver(page)
    page._leaf_output_values = []
    page._leaf_output_documents = {}

    def heard(source, value):
        if source["frame"] != page.main_frame:
            value["document"] = source["frame"].url
        page._leaf_output_values.append(value)

    page.expose_binding("__leafOutputValue", heard)

    def before_entry(route):
        frame = route.request.frame
        if not is_runtime_entry(route.request):
            route.fallback()
            return
        # Let the browser order the subscription before this entry's upgrade. A route
        # callback must not wait for a document: sibling sample routes can nest while
        # its parser is awaiting another response, stranding both. This imports the
        # same check API graph as the runtime; no publication can precede the call.
        try:
            response = route.fetch(timeout=_timeout(page, None))
        except PlaywrightError:
            route.abort()
            return
        document = frame.url
        probe = urljoin(route.request.url, f"{RENDER_CHECKS_DIR}/outputs.js")
        route.fulfill(
            response=response,
            body=(
                f'import {{ observeOutputValues }} from "{probe}";\n'
                "observeOutputValues();\n" + response.text()
            ),
        )
        page._leaf_output_documents[frame] = document

    # Observe publications before each document's entry runs, including the main
    # document and samples opened later by the check's sweep.
    page.route("**/leaf.js", before_entry)


def close_render_page(page) -> None:
    """Cancel route callbacks before disposing a render check's page and responses.

    Context closure disposes fetched responses before the page reports closed, so
    callback-local checks of `is_closed()` cannot recognize every cancellation.
    Playwright's route lifecycle suppresses errors from those cancelled callbacks.
    """
    page.unroute_all(behavior="ignoreErrors")
    page.close()


def output_values(page) -> list[dict]:
    """Wait for live realms' reports, then read all publications retained by the check."""
    for frame, document in page._leaf_output_documents.items():
        if not frame.is_detached() and frame.url == document:
            wait_for_probe(frame, "outputsReported")
    return page._leaf_output_values


def _ensure_driver(page) -> None:
    """Make the driver available to callers that received an open page."""
    install_driver(page)
    if not page.evaluate(_DRIVER_PRESENT):
        page.evaluate(DRIVER_SOURCE.read_text(encoding="utf-8"))


def _load_probes(page, timeout_ms: int) -> None:
    """Start the module load and observe its result from a bounded driver wait.

    Once a document's probes have arrived this is one round trip, which every probe
    call and wait pays."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    loaded = page.evaluate(_LOAD_PROBES, PROBE_ROUTE)
    if loaded is None:
        _ensure_driver(page)
        loaded = page.evaluate(_LOAD_PROBES, PROBE_ROUTE)
    if not loaded:
        try:
            # Probe readiness is independent of animation frames. A complete child
            # document in a closed disclosure or inactive tab still needs inspection,
            # but browsers suspend its requestAnimationFrame callbacks.
            page.wait_for_function(
                _PROBES_SETTLED,
                arg=PROBE_ROUTE,
                timeout=timeout_ms,
                polling=PROBE_POLL_MS,
            )
        except PlaywrightTimeout as error:
            raise PlaywrightError(
                f"Leaf browser probes did not load from {PROBE_ROUTE} "
                f"within {timeout_ms}ms"
            ) from error
        # A failed load throws its own error here, from an evaluate the page never sees.
        page.evaluate(_LOAD_PROBES, PROBE_ROUTE)


def evaluate_probe(page, name: str, *args):
    """Invoke one named export from the browser probe module."""
    _load_probes(page, _timeout(page, None))
    return page.evaluate(_PROBE, {"name": name, "args": list(args)})


def wait_for_probe(
    page,
    name: str,
    *args,
    timeout_ms: int | None = None,
    fixed_server: bool = False,
) -> None:
    """Wait until one named browser probe returns a truthy value.

    The default patience suits a reading that arrives once the page settles. A caller
    waiting on work the page is doing on its behalf states its own budget, because the
    page answers nothing at all while that work holds its main thread. A caller whose
    server nothing replaces passes `fixed_server`, as `wait_until_ready` takes it: a
    page that declares it cannot start then raises `PageNotReady` at once.
    """
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    timeout_ms = _timeout(page, timeout_ms)
    _load_probes(page, timeout_ms)
    try:
        page.wait_for_function(
            _PROBE_OR_REFUSED if fixed_server else _PROBE,
            arg={"name": name, "args": list(args)},
            timeout=timeout_ms,
            polling=PROBE_POLL_MS,
        )
    except PlaywrightTimeout as error:
        raise PlaywrightTimeout(
            f"Leaf wait probe {name} did not become true within {timeout_ms}ms"
        ) from error
    if fixed_server:
        _refuse_unstarted(page)


def _wait_for_driver(page, fact: str, arg, missing: str) -> None:
    """Poll one synchronous driver fact until it is true, naming `missing` on timeout."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    timeout_ms = _timeout(page, None)
    try:
        page.wait_for_function(fact, arg=arg, timeout=timeout_ms, polling=PROBE_POLL_MS)
    except PlaywrightTimeout as error:
        raise PlaywrightTimeout(f"{missing} within {timeout_ms}ms") from error


def one_frame(page) -> None:
    """Wait until one whole rendering update has run since the call, its observer
    deliveries included (`requestFrame` in render-checks/driver.js).

    Wait here only where one update is itself the claim: the turn a resize is heard in,
    or the turn that delivers an observer's notice. A read of what the runtime renders
    waits for `rendered`."""
    requested = page.evaluate(_REQUEST_FRAME)
    if requested is None:
        _ensure_driver(page)
        requested = page.evaluate(_REQUEST_FRAME)
    _wait_for_driver(page, _FRAME_PRESENTED, requested, "no rendering update arrived")


def rendered(page, *, facts: tuple[str, ...] | None = None) -> None:
    """Wait until the runtime has rendered what the input so far asked for.

    Its renderingState (runtime/base/rendering.js) says no registered preparation or queued
    rendering is waiting and its last update was quiet. By default every fact must be
    settled; an intermediate reader can select facts, such as updatesSettled while
    deliberately holding a preparation. A read after a coalesced repaint, however many
    updates that repaint chains through, waits here instead of guessing a count. One
    whole update passes first, so a change no Leaf callback took part in — a wheel, a
    resize — has had its turn to unsettle the reading.

    Work that re-queues itself on every update never settles: a fold held
    mid-animation keeps its place hold correcting each frame. Wait `one_frame` there.

    Both waits poll a synchronous fact from the driver, so their deadline holds even
    against a compositor that stops drawing or a page whose main thread is held, and
    they need no probe module, so they hold on a page served without one."""
    one_frame(page)
    _wait_for_driver(
        page, _RENDERING_SETTLED, facts, "the page's rendering never settled"
    )


# Where the page stands on its way to readiness: 'ready', or the first stage it has yet
# to state (`pageReadiness` in runtime/readings/presentation.js) with how many arrivals it has
# yet to land (`arrivalsOutstanding`), read off the entry script so a bundled entry
# answers too. A page whose entry has not run yet has no reading, and starting is the
# first stage it owes. `answering` is the one stage read from out here: a page too busy
# to say which stage it is at. A reader without Playwright's waits, such as the iOS
# probe's WebDriver, polls this itself (`leaf_dev.ios_safari`).
STANDING = """({held, through}) => {
  const entry = document.querySelector('script[data-lf-entry]');
  if (!entry?.lfReadiness) return ['started', 0];
  const stage = entry.lfReadiness(held, through ?? undefined);
  return stage === null ? 'ready' : [stage, entry.lfArrivalsOutstanding()];
}"""
# The reason a page declared it cannot start (an incomplete startup fault, prepaint.js),
# or null. Such a page upgrades nothing more until a replacement server reloads it
# (bootstrap.js).
_REFUSED = """() => {
  const root = document.documentElement;
  return root.hasAttribute('data-lf-startup-error')
    && !root.hasAttribute('data-lf-interactive') ? root.dataset.lfStartupError : null;
}"""
_PROBE_OR_REFUSED = f"call => ({_PROBE})(call) || ({_REFUSED})() !== null"
# The page's standing once it differs from `last`, with 'refused' for a page that
# declared it cannot start where the caller's server will not replace it.
_STANDING_MOVED = f"""({{asked, refusable, last}}) => {{
  const now = refusable && ({_REFUSED})() !== null ? 'refused' : ({STANDING})(asked);
  return JSON.stringify(now) !== JSON.stringify(last) && now;
}}"""
# The stage the page has yet to state, or 'ready'.
OUTSTANDING = f"""asked => {{
  const standing = ({STANDING})(asked);
  return standing === 'ready' ? standing : standing[0];
}}"""
# How a failure words each stage `pageReadiness` names. `state` fails only against an
# answer the caller holds.
UNREADY = {
    "answering": "the page stopped answering",
    "started": "the runtime never started",
    "upgraded": "the widget layer never finished upgrading",
    "log": "the runtime never finished replaying the log",
    "state": "the runtime never applied the state the server held (reading {reading})",
    "presented": "the runtime never presented the page after applying its current state",
    "arrived": "work the page deferred past presentation never landed",
    "rendering": "the page's rendering never settled",
}
# How long a page that has missed its deadline gets to say which stage it is at.
_STAGE_READ_MS = 5_000


class PageNotReady(TimeoutError):
    """A page that never stated one of its readiness facts; `stage` names which, or is
    `refused` where the page declared it cannot start (`wait_until_ready`)."""

    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


class HandoverProgress:
    """Whether each standing a wait reads (`STANDING`) moves the page's handover on: a
    stage the wait has not yet seen it at, or fewer arrivals left at its stage than at
    any reading there before. Arrivals that land only for others to take their place,
    or a stage that swings back and forth, move it no further, so such a page's wait
    still ends (`HANDOVER_DEADLINE_MS`)."""

    def __init__(self):
        self._fewest: dict[str, int] = {}

    def moved(self, stage: str, left: int) -> bool:
        if stage in self._fewest and left >= self._fewest[stage]:
            return False
        self._fewest[stage] = left
        return True


# The query marks `runtime/bootstrap.js` takes off a document's address before the user
# sees it: a revision mark, startup recovery's mark (`asked_again`) and the host key.
ADDRESS_MARKS = frozenset({"_leaf-revision", "_leaf-recovered", "t"})


def asked_again(url: str) -> str:
    """`url` as the document startup recovery asks the server for once more
    (`_leaf-recovered`, bootstrap.js). A page opened there that cannot start waits for
    another server rather than reloading itself from this one, so a reader that judges
    the document it opened, such as a check against a fixed server, opens it here."""
    return f"{url}{'&' if '?' in url else '?'}_leaf-recovered"


def wait_until_ready(
    page,
    state: dict | None = None,
    *,
    through: str | None = None,
    timeout_ms: int | None = None,
    fixed_server: bool = False,
) -> None:
    """Wait until the page says a reader outside it may read its final boxes and press
    its keys, or raise `PageNotReady` naming the first fact it never stated.

    Every reader outside the page waits here rather than combining the runtime's
    stamps itself: the stages, and their order, are the runtime's (`pageReadiness`).
    `state` is an `/api/state` answer the caller already holds, and asks the page to
    have applied all of it: log, data, status, versions and presence. The server may
    move on between the caller's read and the page's, so an answer the server took
    later meets it as well. `through` names the last stage the caller needs, for a
    caller that wants the answer taken in while the page is still mid-gesture. Finite
    animation is not readiness; the render gate asks `pageSettled` for that on its own.
    The wait gives up once the page has gone `HANDOVER_DEADLINE_MS` without progress,
    or `timeout_ms` where the caller states one.

    A caller whose server nothing replaces while it waits, such as a check reading a
    preview of one candidate, passes `fixed_server`: a page that declares it cannot
    start is then refused at once, as stage `refused` with the page's own reason,
    rather than at the deadline, since the reload it waits for never comes. Such a
    caller opens the page at `asked_again`, or the page's one reload from the same
    server replaces the document the caller is still reading.
    """
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    asked = {
        "held": (
            None
            if state is None
            else {"reading": state["reading"], "taken": state["taken"]}
        ),
        "through": through,
    }
    timeout_ms = timeout_ms or HANDOVER_DEADLINE_MS
    progress = HandoverProgress()
    standing = None
    stalls = time.monotonic() + timeout_ms / 1000
    left = timeout_ms
    # Playwright reads a zero timeout as none, so the wait ends before one. The reading
    # is polled on a timer, as the probes are (`_load_probes`): a framed page out of
    # sight runs no animation frames.
    while left > 0:
        try:
            standing = page.wait_for_function(
                _STANDING_MOVED,
                arg={"asked": asked, "refusable": fixed_server, "last": standing},
                timeout=left,
                polling=PROBE_POLL_MS,
            ).json_value()
        except PlaywrightTimeout:
            break
        except PlaywrightError as error:
            # The page may replace its document on the way to ready, as a revision
            # that cannot be patched in does, between the standing the old document
            # answered and the read of that answer. The wait goes on in the new one.
            if _DOCUMENT_REPLACED not in str(error):
                raise
            standing = None
            left = round((stalls - time.monotonic()) * 1000)
            continue
        if standing in ("ready", "refused"):
            if fixed_server:
                _refuse_unstarted(page)
            return
        if progress.moved(*standing):
            stalls = time.monotonic() + timeout_ms / 1000
            left = timeout_ms
        else:
            left = round((stalls - time.monotonic()) * 1000)
    # Read the stage through a bounded wait too, since `evaluate` takes no deadline: a
    # page whose own code holds its main thread answers neither.
    try:
        stage = page.wait_for_function(
            OUTSTANDING, arg=asked, timeout=_STAGE_READ_MS
        ).json_value()
    except PlaywrightTimeout:
        stage = "answering"
    if stage == "ready":
        return
    words = UNREADY[stage].format_map(asked["held"] or {})
    raise PageNotReady(stage, f"{words}: no progress in {timeout_ms}ms")


# The words of Playwright's error for a call whose document went away under it.
_DOCUMENT_REPLACED = "Execution context was destroyed"


def _refuse_unstarted(page) -> None:
    """Raise `PageNotReady` as stage `refused`, with the page's own reason, where the
    page declared it cannot start."""
    if (reason := page.evaluate(_REFUSED)) is not None:
        raise PageNotReady("refused", f"the runtime could not start: {reason}")


# Every box holding `frame` in its document, across shadow roots as `renderedParent`
# walks them (lib/shadow-tree.js), with its scroll offsets; `_PUT_BACK` scrolls each back.
# Written out here since it runs in each sample's own document, which no probe reaches.
_HOLDERS = """frame => {
  const held = [];
  for (let node = frame; node;
       node = node.assignedSlot ?? node.parentElement ?? node.getRootNode().host)
    held.push([node, node.scrollLeft, node.scrollTop]);
  return held;
}"""
_PUT_BACK = """held => {
  for (const [node, left, top] of held) node.scrollTo({left, top, behavior: 'instant'});
}"""
_SHOWS = "frame => frame.checkVisibility({visibilityProperty: true})"
_UNSEEN = "frame => frame.hasAttribute('data-lf-unseen')"
_SEEN = "frame => !frame.hasAttribute('data-lf-unseen')"
# True once a document's next rendering has run and delivered its observers'
# readings, a host's reading of whether its frame shows among them. A document out of
# sight renders nothing but still runs its timers, so after 5 s, two orders of
# magnitude above one rendering, it answers false.
_RENDERED = """() => new Promise((settle) => {
  setTimeout(() => settle(false), 5000);
  requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(() => settle(true))));
})"""
_LEAF = "() => Boolean(document.querySelector('script[data-lf-entry]')?.lfReadiness)"


def start_near_work(page, state: dict | None = None, **ready) -> None:
    """Start the work the page holds back until the reader nears its node, such as
    each live sample's page, and wait until the page has taken it in, as
    `wait_until_ready` waits with `state` and `ready`. A check reads every document the
    page can show, not only those near the window it opened at.

    A sample's page may get no rendering while its frame is off screen, so its host
    stops counting what that page draws there, at once or after a deadline (host/sample.js),
    and marks the frame `data-lf-unseen`. The page holding a marked frame counts none
    of the work that frame's page does after loading, its own samples included, so
    each frame, at any depth, waits for the page holding it, and each `data-lf-unseen`
    frame is then scrolled into view and its holder waited for, and every box the
    scroll moved goes back. One no scroll can show, in a closed disclosure, a shut tab
    or a box clipped to nothing, stays as the page has it."""
    from playwright.sync_api import Error as PlaywrightError

    evaluate_probe(page, "startNearWork")
    wait_until_ready(page, state, **ready)
    frames = getattr(page, "page", page).frames
    tried = {frames[0]}
    while untried := [frame for frame in frames if frame not in tried]:
        for frame in untried:
            tried.add(frame)
            try:
                # The page holding the frame counts its loading and the near work it
                # starts; one still unseen, in a closed disclosure or a shut tab,
                # would never settle.
                holder = frame.parent_frame
                if (
                    holder.parent_frame is not None
                    and holder.frame_element().evaluate(_SEEN)
                    and holder.evaluate(_LEAF)
                ):
                    wait_until_ready(holder, timeout_ms=ready.get("timeout_ms"))
                if frame.frame_element().evaluate(_UNSEEN):
                    _show(frame, page, state, ready)
            except PlaywrightError:
                # A sample retired or reloaded meanwhile has no frame to show.
                if not frame.is_detached():
                    raise
        frames = getattr(page, "page", page).frames
    if len(tried) > 1:
        rendered(page)
        wait_until_ready(page, state, **ready)


def _show(frame, page, state, ready) -> None:
    """Scroll `frame` into view, outermost frame first, wait until its holder has
    taken in what it draws, and scroll every box it moved back."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    elements = []
    while frame.parent_frame is not None:
        elements.append(frame.frame_element())
        frame = frame.parent_frame
    if not all(element.evaluate(_SHOWS) for element in elements):
        return
    held = [element.evaluate_handle(_HOLDERS) for element in elements]
    holder = elements[0].owner_frame()
    try:
        # Outermost first, and each only once the document holding it renders, as
        # Playwright's wait for a stable box needs: a frame an ancestor clips stays out
        # of sight however it scrolls.
        for element in reversed(elements):
            owner = element.owner_frame()
            if owner.parent_frame is not None and not owner.evaluate(_RENDERED):
                break
            element.scroll_into_view_if_needed()
        else:
            # The frame keeps its mark where no scroll shows it, and stays as the
            # page has it.
            holder.evaluate(_RENDERED)
            if elements[0].evaluate(_SEEN):
                if holder.parent_frame is None:
                    wait_until_ready(page, state, **ready)
                else:
                    wait_until_ready(holder, timeout_ms=ready.get("timeout_ms"))
    except PlaywrightTimeout:
        pass  # A box that never stops moving can't be scrolled into view.
    for boxes in held:
        boxes.evaluate(_PUT_BACK)


def install_window_errors(page, heard) -> None:
    """Hand `heard` each error the page's windows raise with no exception behind it,
    as `{"text": ..., "resizeLoop": ...}`, from navigation on.

    Chrome writes those to no console: a ResizeObserver loop notice is one, which the
    gate and the suite each judge over a confirming reading rather than at once, so
    `init.js` says which a report is where it reads the event. One channel per page,
    shared by every reader installed on it, since a binding is registered once."""
    install_driver(page)
    page = getattr(page, "page", page)
    listeners = getattr(page, "_leaf_window_error_listeners", None)
    if listeners is None:
        listeners = page._leaf_window_error_listeners = []
        page.expose_binding(
            "__leafWindowError",
            lambda _source, error: [listener(error) for listener in listeners],
        )
        page.add_init_script(path=WINDOW_ERRORS_SOURCE)
    listeners.append(heard)
