"""Open one authored page in Chrome, bring it to a state, and print what it shows.

    uv run leaf-dev probe review-a-plan --do drive:card-by-keyboard \\
        --js "document.activeElement.getBoundingClientRect().toJSON()" --base

SOURCE is a page name (`leaf_dev.example_data.named_source`) or an authored `.html`
path, built fresh with the checkout's own launcher, so the working tree runs,
uncommitted edits included. `--base` adds the same page on an arm at the merge base
with `main`, or at the ref it names. An arm that fails prints the stage and error and
the next arm still runs, since a probe is most often run where one version is broken.

`--log` starts the page from a log that already holds given events: threads, replies,
resolutions, a message still waiting for its delivery. Each arm admits them through its
own `event_contracts.append_admitted` (`arms.admit_log`) after the source's companion
history, which a receipt acknowledges, so they stay unacknowledged as a writer's would.
"""

import json
import runpy
import tempfile
from contextlib import nullcontext
from pathlib import Path
from urllib.parse import urlsplit

import click
from playwright.sync_api import Error as PlaywrightError

from leaf.findings import Finding
from leaf.render_checks import PageNotReady
from leaf.render_gate.scheme import collect_page_exceptions, console_finding
from leaf_dev import ROOT
from leaf_dev.arms import base_ref, extract_arm, serving_source
from leaf_dev.browser import (
    DESKTOP,
    headless_engine,
    headless_shell,
    load,
    settle,
    slow_cpu,
    tab,
)
from leaf_dev.commands.stills import DRIVERS
from leaf_dev.example_data import named_source
from leaf_dev.main_thread import SCRIPT as MAIN_THREAD_SCRIPT
from leaf_dev.main_thread import reading as main_thread_reading
from leaf_dev.recording import recording
from leaf_dev.startup import layout_shifts_reading, observe_startup, startup_reading

OUT = ROOT / ".tmp" / "probe"

STEPS = {
    "press": lambda page, key: page.keyboard.press(key),
    "click": lambda page, sel: page.locator(sel).first.click(),
    "focus": lambda page, sel: page.locator(sel).first.focus(),
    "drive": lambda page, name: DRIVERS[name](page),
}


def step(value: str) -> tuple[str, str]:
    verb, _, arg = value.partition(":")
    if verb not in STEPS or not arg:
        raise click.BadParameter(
            f"{value!r}: a step is VERB:ARG, VERB one of {', '.join(STEPS)}"
        )
    if verb == "drive" and arg not in DRIVERS:
        raise click.BadParameter(f"no input {arg!r}; one of {', '.join(DRIVERS)}")
    return verb, arg


def source_path(value: str) -> Path | str:
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


def viewport(value: str) -> tuple[int, int]:
    width, _, height = value.partition("x")
    if not (width.isdigit() and height.isdigit()):
        raise click.BadParameter(f"{value!r} is not WIDTHxHEIGHT")
    return int(width), int(height)


@click.command()
@click.argument(
    "source", type=click.UNPROCESSED, callback=lambda c, p, v: source_path(v)
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
    help="Defaults to normal motion when recording, reduced motion otherwise.",
)
@click.option(
    "--viewport",
    "size",
    default=f"{DESKTOP[0]}x{DESKTOP[1]}",
    callback=lambda c, p, v: viewport(v),
    help="WIDTHxHEIGHT; independent of --touch, so a phone needs both.",
)
@click.option(
    "--scheme",
    type=click.Choice(["light", "dark"]),
    default="light",
    help="The colour scheme the page is shown in.",
)
@click.option(
    "--touch",
    is_flag=True,
    help="Show the page under a finger: a coarse pointer and mobile emulation. "
    "The size stays at --viewport (default desktop); pass --viewport 390x844 for a phone.",
)
@click.option(
    "--browser",
    "engine",
    type=click.Choice(["chromium", "firefox", "webkit"]),
    default="chromium",
    help="The engine to run in: Playwright's Chromium shell, Firefox or WebKit.",
)
@click.option(
    "--cpu-throttle",
    "throttle",
    type=click.FloatRange(min=1),
    help="Slow Chromium's CPU this many times from before the page loads.",
)
@click.option(
    "--base",
    is_flag=False,
    flag_value="",
    default=None,
    help="Also probe the merge base with main, or the ref given.",
)
def probe(
    source,
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
    size,
    scheme,
    touch,
    engine,
    throttle,
    base,
) -> None:
    """Open SOURCE in Chromium, Firefox or WebKit (--browser), run each --do step,
    and print what --js or --journey returns.

    SOURCE is an example or fixture name, an authored .html path built fresh
    from this working tree, or any http(s) URL. A path takes its companions from
    beside it (examples/AGENTS.md, "Companions"), so a copy of an example that
    imports /page/theme.css needs its STEM.page/ copied too. Each --do step is
    one input:

    \b
      press:KEY     a key or chord, as Playwright names it (Tab, Shift+a)
      click:SEL     click the first element matching the CSS selector
      focus:SEL     focus it
      drive:NAME    a `leaf-dev stills` state's input, e.g. card-by-keyboard

    Controls and reading destinations follow browser focus-visible; use keyboard
    input to inspect their rings. Text editors retain their entry cue.
    --base takes an optional ref, so put
    SOURCE before it or give it one (--base=REF).

    --log FILE admits each line, one event as its writer would hand it to the
    log, after the source's own history and before the page loads, so a user's
    message in it is still waiting for its delivery. A line may name its id for a
    later one to answer; give the revision a message was made on:

    \b
      {"kind":"comment","author":"user","revision":1,"id":"q","text":"Can the gutters wait?","anchor":{"section":"gutters"}}
      {"kind":"reply","author":"agent","agent":"Codex","parent":"q","revision":1,"text":"Until spring, yes."}
      {"kind":"resolve","author":"user","parent":"q"}

    News that arrives while the user is in a thread is input after load, not
    history: drive:card-held-news on review-a-plan, drive:seat-held-news on
    command-hub, or a --journey that writes as stills.py's held_news does.

    Prints one JSON line per arm: startup phases and resources; native layout shifts
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
    and video.webm under DIR/worktree (and DIR/base with --base); --gif adds
    recording.gif. View the action timeline, filmstrip, DOM, console and network:

    \b
      uv run leaf-dev trace-server DIR/worktree/trace.zip

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
    """
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
    if isinstance(source, str) and (base is not None or log):
        raise click.UsageError("--base and --log require a Leaf source, not a URL")
    run = None
    if journey:
        run = runpy.run_path(str(journey.resolve())).get("run")
        if not callable(run):
            raise click.BadParameter(
                "the journey must define run(page)", param_hint="--journey"
            )
    motion = motion or ("no-preference" if record_dir else "reduce")
    if shot:
        OUT.mkdir(parents=True, exist_ok=True)
        shot = Path(tempfile.mkdtemp(prefix="run-", dir=OUT))
    failed = False
    with tempfile.TemporaryDirectory(prefix="leaf-probe-") as built:
        scratch = Path(built)
        arms = {"worktree": ("worktree", ROOT)}
        if base is not None:
            commit = extract_arm(base_ref(base), scratch / "base-arm")
            arms = {"base": (commit, scratch / "base-arm"), **arms}
        with (
            headless_shell() if engine == "chromium" else headless_engine(engine)
        ) as browser:
            for arm, (ran, arm_dir) in arms.items():
                reading, doing = {}, "build"
                try:
                    with (
                        (
                            nullcontext(source)
                            if isinstance(source, str)
                            else serving_source(arm_dir, source, scratch / arm, log)
                        ) as address,
                        tab(browser, size, scheme, touch, motion=motion) as page,
                        (
                            recording(
                                page,
                                record_dir.resolve() / arm,
                                gif=gif,
                                checkpoint_images=checkpoint_images,
                                actions=actions,
                            )
                            if record_dir
                            else nullcontext()
                        ),
                    ):
                        if record_dir:
                            reading["recording"] = str(record_dir.resolve() / arm)
                        reading["console"] = console_findings(page)
                        page.add_init_script(path=MAIN_THREAD_SCRIPT)
                        observe_startup(page)
                        if throttle:
                            slow_cpu(page, throttle)
                        doing = "load"
                        if isinstance(source, str):
                            page.goto(address)
                        else:
                            load(page, address)
                            reading["startup"] = startup_reading(page)
                        reading["main_thread"] = {"startup": main_thread_reading(page)}
                        try:
                            for verb, arg in steps:
                                doing = f"{verb}:{arg}"
                                STEPS[verb](page, arg)
                            if run:
                                doing = "journey"
                                returned = run(page)
                            doing = "settle"
                            if not isinstance(source, str):
                                settle(page)
                            if run:
                                reading["result"] = returned
                        finally:
                            if not page.is_closed():
                                if steps or run:
                                    reading["main_thread"]["interaction"] = (
                                        main_thread_reading(page)
                                    )
                                reading["layout_shifts"] = layout_shifts_reading(page)
                        if expression:
                            doing = "js"
                            reading["result"] = page.evaluate(expression)
                        if shot:
                            reading["shot"] = str(shot / f"{arm}.png")
                            page.screenshot(path=reading["shot"])
                except click.ClickException as error:
                    reading["failed"] = f"{doing}: {error.format_message()}"
                except (PlaywrightError, PageNotReady, AssertionError) as error:
                    message = str(error).split("\n", 1)[0] or type(error).__name__
                    reading["failed"] = f"{doing}: {message}"
                failed |= "failed" in reading
                if "console" in reading:
                    reading["console"] = list(map(str, reading["console"]))
                click.echo(json.dumps({"arm": arm, "ran": ran, **reading}))
    if failed:
        raise click.ClickException("probe failed; see the arm's reading and recording")


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
