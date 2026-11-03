"""Open one page in a browser, bring it to a state, and print what it shows.

    uv run leaf-dev probe --state plan-card-keyboard \\
        --js "document.activeElement.getBoundingClientRect().toJSON()" --base

SOURCE is a page name (`leaf_dev.example_data.named_source`) or an authored `.html`
path, built fresh with the checkout's own launcher, so the working tree runs,
uncommitted edits included. `--state NAME` opens a state of `leaf_dev.states` instead:
its page, in its window, brought there by its input before any `--do` step. `--base`
adds the same page on an arm at the merge base with `main`, or at the ref it names
(`leaf_dev.arms.choose_arms`).

`visits` is the loop each arm runs through, here and in `leaf-dev stills`: serve the
page from the arm, open a fresh tab in the run's engine, load it, drive it, settle it,
and hand the tab to the command's own reading. An arm that fails records the stage and
error and the next arm still runs, since a probe is most often run where one version
is broken.

`--log` starts the page from a log that already holds given events: threads, replies,
resolutions, a message still waiting for its delivery. Each arm admits them through its
own `event_contracts.append_admitted` (`page_fixtures.admit_events`) after the source's
companion history, which a receipt acknowledges, so they stay unacknowledged as a
writer's would.
"""

import json
import runpy
import tempfile
from collections.abc import Callable, Generator, Sequence
from contextlib import AbstractContextManager, ExitStack, contextmanager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import click
from playwright.sync_api import Page
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver

from leaf.event_log import read_events
from leaf.findings import Finding
from leaf.render_gate.scheme import collect_page_exceptions, console_finding
from leaf_dev import ROOT, ios_safari
from leaf_dev.arms import (
    Arm,
    base_option,
    choose_arms,
    own_source,
    served_page,
    serving_source,
)
from leaf_dev.browser import (
    engine_option,
    launch,
    load,
    settle,
    slow_cpu,
    tab,
    tab_options,
)
from leaf_dev.example_data import named_source
from leaf_dev.main_thread import SCRIPT as MAIN_THREAD_SCRIPT
from leaf_dev.main_thread import reading as main_thread_reading
from leaf_dev.recording import recording
from leaf_dev.startup import layout_shifts_reading, observe_startup, startup_reading
from leaf_dev.states import STATES, State

OUT = ROOT / ".tmp" / "probe"

STEPS = {
    "press": lambda page, key: page.keyboard.press(key),
    "click": lambda page, sel: page.locator(sel).first.click(),
    "focus": lambda page, sel: page.locator(sel).first.focus(),
}


@dataclass
class Visit:
    """One arm's visit to a state: the arm's commit, the tab it reached (a Playwright
    page, or the simulator's Safari as one, `ios_safari.Tab`), what was read there, and
    the stage it reached, with the error that stopped it there if one did."""

    commit: str
    page: Any = None
    doing: str = "build"
    error: Exception | None = None
    reading: dict = field(default_factory=dict)


def said(error: Exception) -> str:
    """An error's own words: the last line a `leaf` command printed, a WebDriver error's
    message without the documentation link Selenium appends, or any other error's first
    line."""
    if isinstance(error, click.ClickException):
        words = error.format_message().strip().rsplit("\n", 1)[-1].split("; ")[0]
    elif isinstance(error, WebDriverException):
        words = error.msg or ""
    else:
        words = str(error).split("\n", 1)[0]
    return words or type(error).__name__


@contextmanager
def visits(
    browser,
    arms: dict[str, Arm],
    state: State,
    source: Path | str,
    scratch: Path,
    *,
    window: tuple[tuple[int, int], str, bool],
    read: Callable[[str, Visit], None],
    motion: str = "reduce",
    scale: int = 1,
    log: Path | None = None,
    authored: bool = False,
    steps: Sequence[tuple[str, Callable[[Page], object]]] = (),
    run: Callable[[Page], object] | None = None,
    record: Callable[[Page, str], AbstractContextManager] | None = None,
    throttle: float | None = None,
) -> Generator[dict[str, Visit]]:
    """Visit `state` on each arm, base first: serve `source`, an authored page, from the
    arm (its own copy when `authored`, `own_source`; with `log`'s events admitted), or
    open it as the URL it is; open a fresh tab in `window`, at `scale` device pixels to
    a CSS pixel and with `motion`, or the simulator's Safari when `browser` is one; load
    the page, run the state's input, each of `steps` and `run`, settle, and call
    `read(arm, visit)`. Yield the visits with every tab still open, so a command can
    read the arms side by side.

    Each visit records the startup reading, long frames through startup and through the
    inputs, the layout shifts, and the console's errors and warnings (or, in the
    simulator, the errors the runtime logged to the page). `run`'s return is the
    reading's `result`. `record(page, arm)` wraps the tab's visit, as a recording does.
    A stage that fails ends that arm's visit with its error; the next arm still runs."""
    ios = isinstance(browser, WebDriver)
    leaf = not isinstance(source, str)
    inputs = [*([(state.name, state.drive)] if state.drive else []), *steps]
    found = {}
    with ExitStack() as held:
        for arm, version in arms.items():
            visit = found[arm] = Visit(version.commit)
            reading = visit.reading
            served = None
            try:
                if isinstance(source, str):
                    address = source
                else:
                    page_source = own_source(version, source) if authored else source
                    address = held.enter_context(
                        serving_source(
                            version.directory, page_source, scratch / arm, log
                        )
                    )
                if ios:
                    served = served_page.get() if leaf else None
                    if inputs or run:
                        raise click.ClickException(
                            "Safari on the iOS simulator takes no input: its taps "
                            "never reach pointerup or click"
                        )
                    if not state.activated:
                        raise click.ClickException(
                            "Safari on the iOS simulator can't hold the runtime's "
                            "entry module, as this state needs"
                        )
                    visit.page = ios_safari.Tab(browser)
                    visit.doing = "load"
                    ios_safari.load(browser, address, leaf=leaf)
                    read(arm, visit)
                else:
                    visit.page = page = held.enter_context(
                        tab(browser, *window, motion=motion, scale=scale)
                    )
                    with record(page, arm) if record else nullcontext():
                        reading["console"] = console_findings(page)
                        page.add_init_script(path=MAIN_THREAD_SCRIPT)
                        observe_startup(page)
                        if throttle:
                            slow_cpu(page, throttle)
                        visit.doing = "load"
                        if not leaf:
                            page.goto(address)
                        elif state.activated:
                            load(page, address)
                            reading["startup"] = startup_reading(page)
                        else:
                            held.callback(hold_runtime(page, address))
                        reading["main_thread"] = {"startup": main_thread_reading(page)}
                        try:
                            for label, act in inputs:
                                visit.doing = label
                                act(page)
                            if run:
                                visit.doing = "journey"
                                returned = run(page)
                            visit.doing = "settle"
                            if leaf and state.activated:
                                settle(page)
                            if run:
                                reading["result"] = returned
                        finally:
                            if not page.is_closed():
                                if inputs or run:
                                    reading["main_thread"]["interaction"] = (
                                        main_thread_reading(page)
                                    )
                                reading["layout_shifts"] = layout_shifts_reading(page)
                        read(arm, visit)
            except Exception as error:
                visit.error = error
            finally:
                if ios and served:
                    reading["errors"] = logged_errors(served.directory)
        yield found


def hold_runtime(page: Page, address: str) -> Callable[[], None]:
    """Open `address` with the runtime's entry module held in flight, once the authored
    layout has painted in its fonts, and return what releases the held requests."""
    held = []
    # Playwright marks its handler with an attribute, which a bound builtin can't take.
    page.route("**/leaf.js", lambda route: held.append(route))
    page.goto(address, wait_until="commit")
    # A visible node can precede the render-blocking stylesheet.
    page.wait_for_function("""() => performance.getEntriesByType('paint')
        .some(entry => entry.name === 'first-contentful-paint')""")
    page.evaluate("() => document.fonts.ready")

    def release() -> None:
        for route in held:
            route.abort()

    return release


def step(value: str) -> tuple[str, Callable[[Page], object]]:
    verb, _, arg = value.partition(":")
    if verb not in STEPS or not arg:
        raise click.BadParameter(
            f"{value!r}: a step is VERB:ARG, VERB one of {', '.join(STEPS)}"
        )
    return value, lambda page: STEPS[verb](page, arg)


def source_path(value: str | None) -> Path | str | None:
    if value is None:
        return None
    if urlsplit(value).scheme in {"http", "https"}:
        if not urlsplit(value).netloc:
            raise click.BadParameter("a URL needs a host")
        return value
    path = Path(value).expanduser()
    if path.suffix == ".html":
        return path.resolve()
    try:
        return named_source(value)
    except ValueError as error:
        raise click.BadParameter(str(error)) from error


@click.command()
@click.argument(
    "source",
    required=False,
    type=click.UNPROCESSED,
    callback=lambda c, p, v: source_path(v),
)
@click.option(
    "--state",
    "state_name",
    type=click.Choice([state.name for state in STATES]),
    metavar="NAME",
    help="Open a `leaf_dev.states` state in place of SOURCE.",
)
@click.option(
    "--do",
    "steps",
    multiple=True,
    callback=lambda c, p, v: [step(s) for s in v],
    help="An input step, VERB:ARG, run in order; repeat for more.",
)
@click.option(
    "--js",
    "expression",
    help="A JavaScript expression or function to evaluate once settled; "
    "its JSON value is the result.",
)
@click.option(
    "--log",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="A JSON-lines file of events to admit before the page loads.",
)
@click.option("--shot", is_flag=True, help="Screenshot the viewport.")
@click.option(
    "--journey",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Python file defining run(page); run after --do steps. Its return is JSON "
    "and is the arm's `result`, as --js's value is; the two are exclusive.",
)
@click.option(
    "--record",
    "record_dir",
    type=click.Path(file_okay=False, path_type=Path),
    help="Write a Playwright trace and video to DIR/ARM, including failures.",
)
@click.option("--gif", is_flag=True, help="Also encode a GIF (short recordings only).")
@click.option(
    "--checkpoint-images",
    is_flag=True,
    help="Add native PNG images at trace checkpoints; adds capture work and briefly hides the caret.",
)
@click.option(
    "--actions",
    is_flag=True,
    help="Decorate inputs for a demo; adds Playwright's 500 ms wait per annotation.",
)
@click.option(
    "--motion",
    type=click.Choice(["reduce", "no-preference"]),
    default=None,
    help="Defaults to normal motion, as the user sees it; reduce settles transitions at once.",
)
@tab_options
@engine_option
@click.option(
    "--cpu-throttle",
    "throttle",
    type=click.FloatRange(min=1),
    help="Slow Chromium's CPU this many times from before the page loads.",
)
@base_option()
def probe(
    source,
    state_name,
    steps,
    expression,
    log,
    shot,
    journey,
    record_dir,
    gif,
    checkpoint_images,
    actions,
    motion,
    viewport,
    scheme,
    touch,
    engine,
    throttle,
    base,
) -> None:
    """Open SOURCE, or a state with --state NAME, in Chromium, Firefox or WebKit, or
    Safari on an iPhone simulator (--browser), run each --do step, and print what --js
    or --journey returns.

    SOURCE is an example or fixture name, an authored .html path built fresh
    from this working tree, or any http(s) URL. A path takes its companions from
    beside it (examples/AGENTS.md, "Companions"), so a copy of an example that
    imports /page/theme.css needs its STEM.page/ copied too.

    --state NAME opens one of the states `leaf-dev stills` compares
    (dev/leaf_dev/states.py): its page, in its window unless --viewport or --touch
    says otherwise, brought there by its input. Reach a surface no state reaches
    with --do steps or a --journey, or add a state for it there. Each --do step is
    one input, run after the state's:

    \b
      press:KEY     a key or chord, as Playwright names it (Tab, Shift+a)
      click:SEL     click the first element matching the CSS selector
      focus:SEL     focus it

    Controls and reading destinations follow browser focus-visible; use keyboard
    input to inspect their rings. Text editors retain their entry cue.

    --log FILE admits each line, one event as its writer would hand it to the
    log, after the source's own history and before the page loads, so a user's
    message in it is still waiting for its delivery. A line may name its id for a
    later one to answer; give the revision a message was made on:

    \b
      {"kind":"comment","author":"user","revision":1,"id":"q","text":"Can the gutters wait?","anchor":{"section":"gutters"}}
      {"kind":"reply","author":"agent","agent":"Codex","parent":"q","revision":1,"text":"Until spring, yes."}
      {"kind":"resolve","author":"user","parent":"q"}

    News that arrives while the user is in a thread is input after load, not
    history: --state plan-card-held-news or hub-seat-held-news, or a --journey
    that writes as states.py's held_news does.

    Prints one JSON line per arm, `base` before `head` (this working tree), each with
    its commit: startup phases and resources; native layout shifts
    through the journey, including recent input and affected node rectangles;
    long animation frames during startup and input steps, with script
    entry points and forced layout; `result`, what --js or --journey returned when
    evaluation completed; `failed`, the stage and error that stopped the arm, which a
    later stage such as --shot can add beside a `result`, so read `failed` first;
    the page's console errors and warnings and its uncaught exceptions; and with
    --shot the screenshot's path under .tmp/probe/.

    Layout shifts are diagnostics, not a stability gate; their sources name affected
    nodes, not the code that moved them. Main-thread readings are diagnostics, not
    timing gates: native frames of at least 50 ms, not all CPU work. Script entry points are clues for profiling,
    not proof which widget caused a pause. Unsupported browsers say so. A journey
    that navigates reports the current document's frames and layout shifts. The journey
    must wait for its own result, including delayed completion, before returning.

    --journey loads a Python file with run(page), using the full Playwright API
    for clicks, typing, scrolling and assertions. --record DIR saves trace.zip
    and video.webm under DIR/head (and DIR/base with --base); --gif adds
    recording.gif. View the action timeline, filmstrip, DOM, console and network:

    \b
      uv run leaf-dev trace-server DIR/head/trace.zip

    The server prints its viewer URL and opens no browser window.

    Recordings add observation overhead; they are behavior evidence, not timing
    benchmarks. Plain recording inserts no pauses. --actions adds visible input
    annotations and Playwright's 500 ms wait before each annotated input; use it
    for a demo video, not timing-sensitive reproductions. A trace shown in lf-trace
    needs none: lf-trace marks each recorded input itself, and the annotations
    would draw a second cursor and pointer into every frame. --motion reproduces either
    motion preference. Native video holds the final frame for at least one second.
    A journey must keep its page and context open for video finalization; if it
    closes its page, the live context can still save the trace and GIF frames.

    --browser ios runs in an iOS simulator's Safari (`leaf_dev.ios_safari`), for a
    difference only iPhones show. It takes --js, --shot, --scheme, --log, --base and a
    --state with no input; the iPhone sets the viewport, and touch and motion are the
    simulator's own. Its WebDriver taps reached a page as a pointerdown and touchstart
    with no pointerup or click (iOS 26.1, 2026-10-27), so an arm with a --do step, a
    --journey or a state's input fails: --js can call a control's click(). WebDriver
    reads no console, so an arm reports instead the errors the runtime logged to the
    page.
    """
    if (source is None) == (state_name is None):
        raise click.UsageError("give either SOURCE or --state NAME")
    if (gif or actions or checkpoint_images) and record_dir is None:
        raise click.UsageError(
            "--gif, --actions and --checkpoint-images require --record DIR"
        )
    if expression and journey:
        raise click.UsageError(
            "--js and --journey both set `result`; have the journey return the value"
        )
    if throttle and engine != "chromium":
        raise click.UsageError(f"--cpu-throttle needs Chromium's CDP, not {engine}")
    if engine == "ios" and (record_dir or touch or motion or viewport):
        raise click.UsageError(
            "--browser ios takes neither --record, --touch, --motion nor --viewport, "
            "which set Playwright's tab"
        )
    if isinstance(source, str) and (base is not None or log):
        raise click.UsageError("--base and --log require a Leaf source, not a URL")
    state = next((state for state in STATES if state.name == state_name), None)
    if state is not None:
        source = named_source(state.source)
    else:
        # SOURCE as it loads, in the run's window.
        state = State(str(source), str(source))
    run = None
    if journey:
        run = runpy.run_path(str(journey.resolve())).get("run")
        if not callable(run):
            raise click.BadParameter(
                "the journey must define run(page)", param_hint="--journey"
            )
    shots = None
    if shot:
        OUT.mkdir(parents=True, exist_ok=True)
        shots = Path(tempfile.mkdtemp(prefix="run-", dir=OUT))

    def read(arm: str, visit: Visit) -> None:
        if expression:
            visit.doing = "js"
            visit.reading["result"] = visit.page.evaluate(expression)
        if shots:
            visit.doing = "shot"
            visit.reading["shot"] = str(shots / f"{arm}.png")
            visit.page.screenshot(path=visit.reading["shot"])

    def record(page: Page, arm: str) -> AbstractContextManager:
        assert record_dir
        return recording(
            page,
            record_dir.resolve() / arm,
            gif=gif,
            checkpoint_images=checkpoint_images,
            actions=actions,
        )

    with (
        tempfile.TemporaryDirectory(prefix="leaf-probe-") as built,
        launch(engine, scheme) as browser,
        visits(
            browser,
            choose_arms(base, Path(built)),
            state,
            source,
            Path(built),
            window=state.window(viewport, scheme, touch),
            read=read,
            motion=motion or "no-preference",
            log=log,
            steps=steps,
            run=run,
            record=record if record_dir else None,
            throttle=throttle,
        ) as found,
    ):
        for arm, visit in found.items():
            reading = visit.reading
            if record_dir and visit.page:
                reading["recording"] = str(record_dir.resolve() / arm)
            if "console" in reading:
                reading["console"] = list(map(str, reading["console"]))
            if visit.error:
                reading["failed"] = f"{visit.doing}: {said(visit.error)}"
            click.echo(json.dumps({"arm": arm, "commit": visit.commit, **reading}))
    if any(visit.error for visit in found.values()):
        raise click.ClickException("probe failed; see the arm's reading and recording")


def logged_errors(directory: Path) -> list[str]:
    """The errors the runtime logged to the page served from `directory`
    (`reportPageError`), which an arm reports where its browser's console is out of
    reach."""
    return [
        event["text"] for event in read_events(directory) if event["kind"] == "error"
    ]


def console_findings(page) -> list[Finding]:
    """The console errors and warnings and the uncaught exceptions of every document
    in the page, collected from here on. Warnings carry the browser's own diagnostics,
    such as Firefox's note that a `document.write` forced a reparse."""
    found = []

    def heard(message):
        if (finding := console_finding(message)) is not None:
            found.append(finding)

    page.on("console", heard)
    collect_page_exceptions(page, found)
    return found
