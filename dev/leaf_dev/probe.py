"""Open one authored page in Chrome, bring it to a state, and print what it shows.

    uv run leaf-dev probe review-a-plan --do drive:card-by-keyboard \\
        --js "document.activeElement.getBoundingClientRect().toJSON()" --base

SOURCE is a page name (`leaf_dev.example_data.named_source`) or an authored `.html`
path, built fresh with the checkout's own launcher, so the working tree runs,
uncommitted edits included. `--base` adds the same page on an arm at the merge base
with `main`, or at the ref it names. An arm that fails prints the stage and error and
the next arm still runs, since a probe is most often run where one version is broken.
"""

import json
import runpy
import tempfile
from contextlib import nullcontext
from pathlib import Path
from urllib.parse import urlsplit

import click
from leaf.render_checks import PageNotReady
from playwright.sync_api import Error as PlaywrightError

from leaf_dev import ROOT
from leaf_dev.browser import DESKTOP, chrome, load, settle, tab
from leaf_dev.example_data import named_source
from leaf_dev.harness import base_ref, build_arm, serving_source
from leaf_dev.recording import recording
from leaf_dev.startup import observe_startup, startup_reading
from leaf_dev.stills import DRIVERS

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
@click.option("--shot", is_flag=True, help="Screenshot the viewport.")
@click.option(
    "--journey",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Python file defining run(page); run after --do steps. Its return is JSON.",
)
@click.option(
    "--record",
    "record_dir",
    type=click.Path(file_okay=False, path_type=Path),
    help="Write a Playwright trace and video to DIR/ARM, including failures.",
)
@click.option("--gif", is_flag=True, help="Also encode a GIF (short recordings only).")
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
    help="WIDTHxHEIGHT.",
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
    help="Show the page under a finger: a coarse pointer and a mobile viewport.",
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
    shot,
    journey,
    record_dir,
    gif,
    actions,
    motion,
    size,
    scheme,
    touch,
    base,
) -> None:
    """Open SOURCE in Chrome, run each --do step, and print what --js returns.

    SOURCE is an example or fixture name, an authored .html path built fresh
    from this working tree, or any http(s) URL. Each --do step is one input:

    \b
      press:KEY     a key or chord, as Playwright names it (Tab, Shift+a)
      click:SEL     click the first element matching the CSS selector
      focus:SEL     focus it
      drive:NAME    a `leaf-dev stills` state's input, e.g. card-by-keyboard

    Focus rings draw only once a key has been pressed, so start a keyboard journey
    with press:Tab or a drive: input that does. --base takes an optional ref, so put
    SOURCE before it or give it one (--base=REF).

    Prints one JSON line per arm: startup phases, resources and diagnostic initial
    layout shifts; what --js returned, or the error that stopped the arm;
    the page's console errors and uncaught exceptions; and with --shot the
    screenshot's path under .tmp/probe/.

    --journey loads a Python file with run(page), using the full Playwright API
    for clicks, typing, scrolling and assertions. --record DIR saves trace.zip
    and video.webm under DIR/worktree (and DIR/base with --base); --gif adds
    recording.gif. View the action timeline, filmstrip, DOM, console and network:

    \b
      uv run playwright show-trace DIR/worktree/trace.zip

    Recordings add observation overhead; they are behavior evidence, not timing
    benchmarks. Plain recording inserts no pauses. --actions adds visible input
    annotations and Playwright's 500 ms wait before each annotated input; use it
    for demos, not timing-sensitive reproductions. --motion reproduces either
    motion preference. Native video holds the final frame for at least one second.
    A journey must keep its page and context open for video finalization; if it
    closes its page, the live context can still save the trace and GIF frames.
    """
    if (gif or actions) and record_dir is None:
        raise click.UsageError("--gif and --actions require --record DIR")
    if isinstance(source, str) and base is not None:
        raise click.UsageError("--base requires a Leaf source, not a URL")
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
            commit = build_arm(base_ref(base), scratch / "base-arm")
            arms = {"base": (commit, scratch / "base-arm"), **arms}
        with chrome() as browser:
            for arm, (ran, arm_dir) in arms.items():
                reading, doing = {}, "build"
                try:
                    with (
                        (
                            nullcontext(source)
                            if isinstance(source, str)
                            else serving_source(arm_dir, source, scratch / arm)
                        ) as address,
                        tab(browser, size, scheme, touch, motion=motion) as page,
                        (
                            recording(
                                page,
                                record_dir.resolve() / arm,
                                gif=gif,
                                actions=actions,
                            )
                            if record_dir
                            else nullcontext()
                        ),
                    ):
                        if record_dir:
                            reading["recording"] = str(record_dir.resolve() / arm)
                        reading["errors"] = console_errors(page)
                        doing = "load"
                        if isinstance(source, str):
                            page.goto(address)
                        else:
                            observe_startup(page)
                            load(page, address)
                            reading["startup"] = startup_reading(page)
                        for verb, arg in steps:
                            doing = f"{verb}:{arg}"
                            STEPS[verb](page, arg)
                        if run:
                            doing = "journey"
                            reading["journey"] = run(page)
                        doing = "settle"
                        if not isinstance(source, str):
                            settle(page)
                        if expression:
                            doing = "js"
                            reading["result"] = page.evaluate(expression)
                        if shot:
                            reading["shot"] = str(shot / f"{arm}.png")
                            page.screenshot(path=reading["shot"])
                except click.ClickException as error:
                    reading["failed"] = f"{doing}: {error.format_message()}"
                except (PlaywrightError, PageNotReady, AssertionError) as error:
                    reading["failed"] = (
                        f"{doing}: {str(error).split("\n", 1)[0] or type(error).__name__}"
                    )
                failed |= "failed" in reading
                click.echo(json.dumps({"arm": arm, "ran": ran, **reading}))
    if failed:
        raise click.ClickException("probe failed; see the arm's reading and recording")


def console_errors(page) -> list[str]:
    """The page's console errors and uncaught exceptions, collected from here on."""
    errors = []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda error: errors.append(str(error)))
    return errors
