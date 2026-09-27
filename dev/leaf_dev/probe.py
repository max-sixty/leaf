"""Open one authored page in Chrome, bring it to a state, and print what it shows.

    uv run leaf-dev probe review-a-plan --do drive:card-by-keyboard \\
        --eval "document.activeElement.getBoundingClientRect().toJSON()" --base

SOURCE is a page name (`leaf_dev.example_data.named_source`) or an authored `.html`
path. The page is built fresh from it with the checkout's own launcher, so the working
tree is what runs, uncommitted edits included, and served under a state home of its
own. `--base` adds the same page on an arm built at the merge base with `main`, or at
the ref it names, so a probe compares a change with where it started in one command.

The tab opens at the viewport and color scheme asked for, with reduced motion, and
settles before and after the input (`leaf_dev.browser`). The steps (`STEPS`, listed in
`probe --help`) are the inputs throwaway probes kept writing; `drive:NAME` reuses a
`leaf-dev stills` state's input, so a state added there is reachable here too.

Console errors are collected from the first request, so a page that fails to boot
says why. A failure at any stage, from building the page to the screenshot, ends
that arm's reading with the stage and the error, and the next arm still runs: a
probe is most often run where one version is broken.

The page is not held open afterwards: each run is a fresh page, so two runs read the
same starting state. Each run's screenshots go in a directory of their own under
`.tmp/probe/`, so concurrent probes never overwrite each other.
"""

import json
import tempfile
from pathlib import Path

import click
from leaf.render_checks import PageNotReady
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from leaf_dev import ROOT
from leaf_dev.browser import DESKTOP, chrome, load, settle, tab
from leaf_dev.example_data import named_source
from leaf_dev.harness import base_ref, build_arm, serving_source
from leaf_dev.stills import DRIVERS

OUT = ROOT / ".tmp" / "probe"
CROP_MARGIN = 16

STEPS = {
    "press": lambda page, key: page.keyboard.press(key),
    "click": lambda page, sel: page.locator(sel).first.click(),
    "focus": lambda page, sel: page.locator(sel).first.focus(),
    "hover": lambda page, sel: page.locator(sel).first.hover(),
    "scroll": lambda page, sel: page.locator(sel).first.evaluate(
        "el => el.scrollIntoView({block: 'center'})"
    ),
    "wait": lambda page, sel: page.locator(sel).first.wait_for(state="visible"),
    "type": lambda page, text: page.keyboard.insert_text(text),
    "drive": lambda page, name: DRIVERS[name](page),
}


class NotShown(Exception):
    """The element a screenshot was to be cropped to is not displayed."""


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
        if not path.is_file():
            raise click.BadParameter(f"no file at {path}")
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


def crop(page: Page, selector: str) -> dict:
    """The viewport region around the first element `selector` matches, scrolled into
    view. A viewport capture clipped to it, rather than an element screenshot, keeps
    fixed chrome where the user sees it."""
    element = page.locator(selector).first
    if not element.is_visible():
        raise NotShown(f"nothing matching {selector} is displayed")
    element.scroll_into_view_if_needed()
    box = element.bounding_box()
    size = page.viewport_size
    left, top = max(box["x"] - CROP_MARGIN, 0), max(box["y"] - CROP_MARGIN, 0)
    right = min(box["x"] + box["width"] + CROP_MARGIN, size["width"])
    bottom = min(box["y"] + box["height"] + CROP_MARGIN, size["height"])
    return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def read_arm(browser, label: str, arm: Path, source: Path, look: dict) -> dict:
    """Build and serve `source` on `arm`, bring a tab to the state `look` asks for,
    and read it. A stage that fails ends the reading with the stage and its error."""
    errors, reading = [], {}
    doing = "build"
    try:
        with (
            serving_source(arm, source, look["scratch"] / label) as address,
            tab(browser, look["viewport"], look["scheme"]) as page,
        ):
            page.on(
                "console",
                lambda message: message.type == "error" and errors.append(message.text),
            )
            page.on("pageerror", lambda error: errors.append(str(error)))
            doing = "load"
            load(page, address)
            for verb, arg in look["steps"]:
                doing = f"{verb}:{arg}"
                STEPS[verb](page, arg)
            doing = "settle"
            settle(page)
            doing = "eval"
            expression = look["expression"]
            reading["result"] = page.evaluate(expression) if expression else None
            if (shot := look["shot"]) is not None:
                doing = "shot"
                path = look["out"] / f"{label}.png"
                page.screenshot(path=path, clip=crop(page, shot) if shot else None)
                reading["shot"] = str(path)
    except click.ClickException as error:
        reading["failed"] = f"{doing}: {error.format_message()}"
    except (PlaywrightError, PageNotReady, NotShown) as error:
        reading["failed"] = f"{doing}: {str(error).splitlines()[0]}"
    return {**reading, "errors": errors}


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
    "--eval",
    "expression",
    help="A JavaScript expression or function to evaluate once settled; "
    "its JSON value is the result.",
)
@click.option(
    "--shot",
    is_flag=False,
    flag_value="",
    default=None,
    help="Screenshot the viewport, or with a selector, the viewport cropped to it.",
)
@click.option(
    "--viewport",
    "size",
    default=f"{DESKTOP[0]}x{DESKTOP[1]}",
    callback=lambda c, p, v: viewport(v),
    help="WIDTHxHEIGHT.",
)
@click.option("--dark", is_flag=True, help="Prefer the dark color scheme.")
@click.option(
    "--base",
    is_flag=False,
    flag_value="",
    default=None,
    help="Also probe the merge base with main, or the ref given.",
)
def probe(source, steps, expression, shot, size, dark, base) -> None:
    """Open SOURCE in Chrome, run each --do step, and print what --eval returns.

    SOURCE is an example or fixture name, or an authored .html path, built fresh
    from this working tree. Each --do step is one input, run in order:

    \b
      press:KEY     a key or chord, as Playwright names it (Tab, Shift+a)
      click:SEL     click the first element matching the CSS selector
      focus:SEL     focus it
      hover:SEL     move the pointer over it
      scroll:SEL    scroll it to the viewport's centre
      wait:SEL      wait until it is visible
      type:TEXT     insert text where the focus is
      drive:NAME    a `leaf-dev stills` state's input, e.g. card-by-keyboard

    Focus rings draw only once a key has been pressed, so start a keyboard journey
    with press:Tab or a drive: input that does. --shot and --base take an optional
    value, so put SOURCE before them or give them one (--base=, --shot=SEL).

    Prints one JSON line per arm: what --eval returned, or the stage that failed
    and why; the page's console errors and uncaught exceptions from its first
    request; and with --shot the screenshot's path under .tmp/probe/.
    """
    OUT.mkdir(parents=True, exist_ok=True)
    look = {
        "steps": steps,
        "expression": expression,
        "shot": shot,
        "viewport": size,
        "scheme": "dark" if dark else "light",
        "out": Path(tempfile.mkdtemp(prefix=f"{source.stem}-", dir=OUT)),
    }
    with tempfile.TemporaryDirectory(prefix="leaf-probe-") as built:
        scratch = look["scratch"] = Path(built)
        arms = {"worktree": ("worktree", ROOT)}
        if base is not None:
            commit = build_arm(base_ref(base), scratch / "base-arm")
            arms = {"base": (commit, scratch / "base-arm"), **arms}
        with chrome() as browser:
            for arm, (ran, arm_dir) in arms.items():
                reading = read_arm(browser, arm, arm_dir, source, look)
                click.echo(json.dumps({"arm": arm, "ran": ran, **reading}))
