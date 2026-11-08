"""Open one page in a browser, bring it to a state, and print what it shows.

    uv run leaf-dev probe --state plan-card-keyboard \\
        --js "document.activeElement.getBoundingClientRect().toJSON()" --base

SOURCE is a page name (`leaf_dev.example_data.named_source`) or an authored `.html`
path, built fresh with the checkout's own launcher, so the working tree runs,
uncommitted edits included. `--state NAME` opens a state of `leaf_dev.states` instead:
its page, in its window, brought there by its input before any `--do` step. `--base`
adds the same page on an arm at the merge base with `main`, or at the ref it names
(`leaf_dev.arms.choose_arms`).

Each arm runs through `leaf_dev.visits`, the loop `leaf-dev stills` runs too. An arm
that fails prints the stage and error, with its traceback under `.tmp/probe/`, and
the next arm still runs, since a probe is most often run where one version is broken.

`--log` starts the page from a log that already holds given events: threads, replies,
resolutions, a message still waiting for its delivery. Each arm admits them through its
own `event_contracts.append_admitted` (`page_fixtures.admit_events`) after the source's
companion history, which a receipt acknowledges, so they stay unacknowledged as a
writer's would.
"""

import json
import runpy
import tempfile
import traceback
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from urllib.parse import urlsplit

import click
from playwright.sync_api import Page

from leaf_dev import ROOT
from leaf_dev.arms import base_option, choose_arms, run_directory
from leaf_dev.browser import (
    chosen_window,
    engine_option,
    launch,
    screenshot,
    tab_options,
)
from leaf_dev.example_data import named_source
from leaf_dev.recording import recording
from leaf_dev.states import STATES, State
from leaf_dev.visits import Visit, said, visits

OUT = ROOT / ".tmp" / "probe"

STEPS = {
    "press": lambda page, key: page.keyboard.press(key),
    "click": lambda page, sel: page.locator(sel).first.click(),
    "focus": lambda page, sel: page.locator(sel).first.focus(),
}


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
    help="Open a state of dev/leaf_dev/states.py in place of SOURCE.",
)
@click.option(
    "--authored",
    is_flag=True,
    help="Build the base's page from its own authored source.",
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
    authored,
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
    imports /page/theme.css needs its STEM.page/ copied too. Its /media/ files come from
    a media/ beside it, so a page directory's index.html builds as it stands, a fresh
    copy without the page's log. --base builds the base's
    page from this working tree's source too, so only Leaf differs between the arms;
    --authored builds it from the base's own copy, to show an edit to the page.

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
    later stage such as --shot can add beside a `result`, so read `failed` first, and
    `traceback`, the path of its whole traceback under .tmp/probe/; the page's console
    errors and warnings and its uncaught exceptions; and with --shot the screenshot's
    path under .tmp/probe/.

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
    difference only iPhones show. The iPhone sets the viewport, touch and motion, and
    Playwright's --record doesn't reach it. Its WebDriver taps reached a page as a
    pointerdown and touchstart with no pointerup or click (iOS 26.1, 2026-10-27), so a
    --do step, a --journey or a state's input fails each arm before its page is
    built: --js can call a control's click(). WebDriver reads no console, so an arm
    reports instead the errors the runtime logged to the page.
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
    if engine == "ios" and record_dir:
        raise click.UsageError("--record needs Playwright, which --browser ios lacks")
    if isinstance(source, str) and (base is not None or log or authored):
        raise click.UsageError(
            "--base, --authored and --log require a Leaf source, not a URL"
        )
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
    shots = run_directory(OUT) if shot else None
    traces = shots

    def read(arm: str, visit: Visit) -> None:
        if expression:
            visit.doing = "js"
            visit.reading["result"] = visit.page.evaluate(expression)
        if shots:
            visit.doing = "shot"
            shot = shots / f"{arm}.png"
            visit.reading["shot"] = str(shot)
            shot.write_bytes(screenshot(visit.page))

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
            window=chosen_window(state.window, viewport, touch),
            scheme=scheme,
            read=read,
            motion=motion or "no-preference",
            log=log,
            authored=authored,
            steps=steps,
            run=run,
            record=record if record_dir else None,
            throttle=throttle,
        ) as each,
    ):
        failed = False
        for arm, visit in each:
            reading = visit.reading
            if record_dir and visit.page:
                reading["recording"] = str(record_dir.resolve() / arm)
            if "console" in reading:
                reading["console"] = list(map(str, reading["console"]))
            if visit.error:
                failed = True
                traces = traces or run_directory(OUT)
                reading["failed"] = f"{visit.doing}: {said(visit.error)}"
                reading["traceback"] = str(traces / f"{arm}-error.txt")
                Path(reading["traceback"]).write_text(
                    "".join(traceback.format_exception(visit.error))
                )
            click.echo(json.dumps({"arm": arm, "commit": visit.commit, **reading}))
    if failed:
        raise click.ClickException("probe failed; see the arm's reading and recording")
