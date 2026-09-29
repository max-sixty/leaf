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
import tempfile
from pathlib import Path

import click
from leaf.render_checks import PageNotReady
from playwright.sync_api import Error as PlaywrightError

from leaf_dev import ROOT
from leaf_dev.browser import DESKTOP, chrome, load, settle, tab
from leaf_dev.example_data import named_source
from leaf_dev.harness import base_ref, build_arm, serving_source
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


def source_path(value: str) -> Path:
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
def probe(source, steps, expression, shot, size, scheme, touch, base) -> None:
    """Open SOURCE in Chrome, run each --do step, and print what --js returns.

    SOURCE is an example or fixture name, or an authored .html path, built fresh
    from this working tree. Each --do step is one input, run in order:

    \b
      press:KEY     a key or chord, as Playwright names it (Tab, Shift+a)
      click:SEL     click the first element matching the CSS selector
      focus:SEL     focus it
      drive:NAME    a `leaf-dev stills` state's input, e.g. card-by-keyboard

    Focus rings draw only once a key has been pressed, so start a keyboard journey
    with press:Tab or a drive: input that does. --base takes an optional ref, so put
    SOURCE before it or give it one (--base=REF).

    Prints one JSON line per arm: what --js returned, or the error that stopped the
    arm; the page's console errors and uncaught exceptions; and with --shot the
    screenshot's path under .tmp/probe/.
    """
    if shot:
        OUT.mkdir(parents=True, exist_ok=True)
        shot = Path(tempfile.mkdtemp(prefix=f"{source.stem}-", dir=OUT))
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
                        serving_source(arm_dir, source, scratch / arm) as address,
                        tab(browser, size, scheme, touch) as page,
                    ):
                        reading["errors"] = console_errors(page)
                        doing = "load"
                        load(page, address)
                        for verb, arg in steps:
                            doing = f"{verb}:{arg}"
                            STEPS[verb](page, arg)
                        doing = "settle"
                        settle(page)
                        if expression:
                            doing = "js"
                            reading["result"] = page.evaluate(expression)
                        if shot:
                            reading["shot"] = str(shot / f"{arm}.png")
                            page.screenshot(path=reading["shot"])
                except click.ClickException as error:
                    reading["failed"] = f"{doing}: {error.format_message()}"
                except (PlaywrightError, PageNotReady) as error:
                    reading["failed"] = f"{doing}: {str(error).splitlines()[0]}"
                click.echo(json.dumps({"arm": arm, "ran": ran, **reading}))


def console_errors(page) -> list[str]:
    """The page's console errors and uncaught exceptions, collected from here on."""
    errors = []
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda error: errors.append(str(error)))
    return errors
