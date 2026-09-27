#!/usr/bin/env python3
"""Screenshot a fixed catalogue of UI states on BASE_REF's runtime and HEAD's, and
show which ones changed.

    uv run scripts/stills.py [BASE_REF]

BASE_REF defaults to the merge base of HEAD and `main`. Each arm is the plugin payload
at its commit (`eval_harness.build_arm`), so commit what you want compared. Every page
is built from this checkout's example source by the arm's own launcher and served by
that arm's `leaf server run --temporary`, so only the runtime, theme and server differ
between the two stills of a state.

A state is an example, a viewport and color scheme, and the input that brings the page
there from a fresh load: a margin card opened by pointer or by keyboard, a reply
being drafted, the Threads panel open, a board card grabbed, a code block focused.
The catalogue (`STATES`) covers states a user reaches by acting, not only the page at
rest, because a change can move what one of those states draws: a padding moved for
layout covered the ring of a thread the keyboard had focused, which no resting page
shows. Add a state where a change touches a surface the catalogue does not reach.

Each state is captured from a fresh tab once the page is ready and settled, with
reduced motion, at the viewport. States on one example share its page and run in the
same order on both arms, so whatever an earlier state left in the log, both arms see.
A state whose input fails on one arm is reported as failed there, with its error.

A state changed when any pixel differs: two arms with the same runtime capture every
state here identically, pixel for pixel. For each changed state the report crops both
stills to the changed region, with a margin, and marks the changed pixels over the
candidate. Everything lands in `.tmp/stills/`: `index.html` shows the changed states
first, and each state's directory holds `base.png`, `head.png`, and for a change
`base-crop.png`, `head-crop.png` and `diff.png`, ready to hand off as an `lf-shot`
pair.
"""

import html
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import click
from eval_harness import build_arm, merge_base, run_leaf, serving
from leaf.render_checks import PageNotReady, wait_for_probe, wait_until_ready
from leaf.render_gate.browser import launch_browser
from page_fixtures import prepare_page, read_fixture
from PIL import Image, ImageChops
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".tmp" / "stills"
DESKTOP = (1440, 900)
# The width of a window beside an editor.
BESIDE = (900, 900)
CROP_MARGIN = 32
OPEN_CARD = "() => document.querySelector('.lf-margin-preview:not([hidden])')"


def at_rest(page: Page) -> None:
    """The page as it loads."""


def card_by_pointer(page: Page) -> None:
    """The first margin card, opened by a click on its marker."""
    page.locator(".lf-margin-marker").first.click()
    page.wait_for_function(OPEN_CARD)


def card_by_keyboard(page: Page) -> None:
    """The first margin card, opened by Enter on its marker, so its thread holds a
    visible focus."""
    page.keyboard.press("Tab")  # keyboard modality, so focus is drawn
    page.locator(".lf-margin-marker").first.focus()
    page.keyboard.press("Enter")
    page.wait_for_function(
        "() => document.activeElement?.matches('.lf-margin-preview .lf-page-thread')"
    )


def card_reply(page: Page) -> None:
    """The first margin card with a reply being typed."""
    card_by_keyboard(page)
    page.keyboard.press("Enter")
    page.wait_for_function(
        "() => document.activeElement?.matches('.lf-margin-preview leaf-text')"
    )
    page.keyboard.insert_text("A reply being drafted, long enough to wrap onto a line")


def threads_panel(page: Page) -> None:
    """The Threads panel, opened from the banner."""
    page.locator(".lf-threads-toggle").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-thread-panel')?.checkVisibility()"
    )


def composer(page: Page) -> None:
    """A comment being typed on a passage selected by pointer."""
    box = page.locator("#triage-lede").bounding_box()
    y = box["y"] + 10
    page.mouse.move(box["x"] + 2, y)
    page.mouse.down()
    page.mouse.move(box["x"] + 200, y, steps=8)
    page.mouse.up()
    page.locator(".lf-fab-input").click()
    page.locator(".lf-composer leaf-text").focus()
    page.keyboard.insert_text("A comment being drafted on the selected words")


def card_grabbed(page: Page) -> None:
    """A board card grabbed by keyboard and carried one column left."""
    page.keyboard.press("Tab")
    page.locator("#card-tz > .lf-grip").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowLeft")


def code_focused(page: Page) -> None:
    """The first code block with a note, focused by keyboard, with the note in view."""
    page.keyboard.press("Tab")
    pre = page.locator("pre:has(.lf-code-note)").first
    pre.focus()
    pre.locator(".lf-code-note").first.evaluate(
        "note => note.scrollIntoView({block: 'center'})"
    )


@dataclass(frozen=True)
class State:
    name: str
    source: str
    drive: Callable[[Page], None]
    viewport: tuple[int, int] = DESKTOP
    scheme: str = "light"


STATES = (
    State("plan", "review-a-plan", at_rest),
    State("plan-dark", "review-a-plan", at_rest, scheme="dark"),
    State("plan-beside", "review-a-plan", at_rest, viewport=BESIDE),
    State("plan-card", "review-a-plan", card_by_pointer),
    State("plan-card-keyboard", "review-a-plan", card_by_keyboard),
    State("plan-card-keyboard-dark", "review-a-plan", card_by_keyboard, scheme="dark"),
    State("plan-card-reply", "review-a-plan", card_reply),
    State("plan-card-beside", "review-a-plan", card_by_pointer, viewport=BESIDE),
    State("plan-panel", "review-a-plan", threads_panel),
    State("plan-panel-beside", "review-a-plan", threads_panel, viewport=BESIDE),
    State("triage", "triage-board", at_rest),
    State("triage-composer", "triage-board", composer),
    State("triage-grabbed", "triage-board", card_grabbed),
    State("walkthrough-code", "pr-walkthrough", code_focused),
    State("walkthrough-code-dark", "pr-walkthrough", code_focused, scheme="dark"),
)


def settle(page: Page) -> None:
    wait_until_ready(page)
    page.evaluate("() => document.fonts.ready")
    wait_for_probe(page, "pageSettled")


def capture(browser, address: str, state: State, path: Path) -> str | None:
    """Bring a fresh tab to `state` and screenshot its viewport to `path`; return
    the error if the state's input failed."""
    context = browser.new_context(
        viewport={"width": state.viewport[0], "height": state.viewport[1]},
        color_scheme=state.scheme,
        reduced_motion="reduce",
    )
    try:
        page = context.new_page()
        page.set_default_timeout(15_000)
        page.goto(address)
        settle(page)
        state.drive(page)
        settle(page)
        page.screenshot(path=path)
    except (PlaywrightError, PageNotReady) as error:
        return str(error).splitlines()[0]
    finally:
        context.close()
    return None


@dataclass
class Compared:
    state: State
    failed: dict
    changed: int = 0
    box: tuple | None = None


def compare(state: State, folder: Path, failed: dict) -> Compared:
    """Read the two stills and, where they differ, write the crops."""
    result = Compared(state, failed)
    if failed:
        return result
    base = Image.open(folder / "base.png").convert("RGB")
    head = Image.open(folder / "head.png").convert("RGB")
    # A pixel's largest difference in any one channel.
    red, green, blue = ImageChops.difference(base, head).split()
    largest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    mask = largest.point(lambda v: 255 if v else 0)
    changed = mask.histogram()[255]
    if not changed:
        return result
    left, top, right, bottom = mask.getbbox()
    box = (
        max(left - CROP_MARGIN, 0),
        max(top - CROP_MARGIN, 0),
        min(right + CROP_MARGIN, head.width),
        min(bottom + CROP_MARGIN, head.height),
    )
    result.changed, result.box = changed, box
    base.crop(box).save(folder / "base-crop.png")
    head.crop(box).save(folder / "head-crop.png")
    faded = Image.blend(head, Image.new("RGB", head.size, "white"), 0.6)
    faded.paste(Image.new("RGB", head.size, (220, 0, 0)), mask=mask)
    faded.crop(box).save(folder / "diff.png")
    return result


def report(results: list[Compared], commits: dict) -> Path:
    def figure(label: str, src: str) -> str:
        return (
            f"<figure><figcaption>{label}</figcaption>"
            f'<a href="{src}"><img src="{src}" alt="{label}"></a></figure>'
        )

    sections = []
    for r in sorted(results, key=lambda r: not r.failed and not r.changed):
        name = html.escape(r.state.name)
        title = (
            f"{name}: {r.state.source}, {r.state.viewport[0]}x"
            f"{r.state.viewport[1]}, {r.state.scheme}, "
            f"{html.escape(r.state.drive.__doc__.strip())}"
        )
        if r.failed:
            body = "".join(
                f"<p>failed on {arm}: {html.escape(error)}</p>"
                for arm, error in r.failed.items()
            )
        elif r.changed:
            body = (
                f"<p>{r.changed} pixels changed in {r.box}.</p><div class=pair>"
                + figure("base", f"{name}/base-crop.png")
                + figure("head", f"{name}/head-crop.png")
                + figure("changed pixels", f"{name}/diff.png")
                + "</div>"
                + f'<p><a href="{name}/base.png">base viewport</a> · '
                f'<a href="{name}/head.png">head viewport</a></p>'
            )
        else:
            body = "<p>Unchanged.</p>"
        sections.append(f"<section><h2>{title}</h2>{body}</section>")
    page = OUT / "index.html"
    page.write_text(
        "<!doctype html><meta charset=utf-8><title>Stills</title><style>"
        "body{font:14px system-ui;margin:24px;color:#222}"
        "h2{font-size:15px;margin:28px 0 6px}"
        ".pair{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-start}"
        "figure{margin:0}figcaption{color:#666;margin-bottom:4px}"
        "img{max-width:100%;border:1px solid #ddd}"
        "</style>"
        f"<h1>Stills: base {commits['base'][:10]} vs head {commits['head'][:10]}</h1>"
        + "".join(sections)
    )
    return page


@click.command()
@click.argument("base_ref", required=False)
def main(base_ref: str | None) -> None:
    """Screenshot every state in STATES on BASE_REF's runtime and HEAD's."""
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    failures: dict[str, dict] = {state.name: {} for state in STATES}
    with tempfile.TemporaryDirectory(prefix="leaf-stills-") as built:
        scratch = Path(built)
        arms = {"base": scratch / "base", "head": scratch / "head"}
        commits = {
            "base": build_arm(base_ref or merge_base(), arms["base"]),
            "head": build_arm("HEAD", arms["head"]),
        }
        with sync_playwright() as playwright:
            browser, _ = launch_browser(playwright)
            try:
                for source in dict.fromkeys(state.source for state in STATES):
                    states = [state for state in STATES if state.source == source]
                    for arm, arm_dir in arms.items():
                        state_home = scratch / f"{arm}-{source}-state"
                        page_dir = scratch / f"{arm}-{source}" / "page"
                        prepare_page(
                            page_dir,
                            read_fixture(ROOT / "examples" / f"{source}.html"),
                            partial(run_leaf, arm_dir, state_home, check=True),
                        )
                        with serving(arm_dir, state_home, page_dir) as address:
                            for state in states:
                                folder = OUT / state.name
                                folder.mkdir(exist_ok=True)
                                error = capture(
                                    browser, address, state, folder / f"{arm}.png"
                                )
                                if error:
                                    failures[state.name][arm] = error
                                click.echo(
                                    f"{state.name} {arm}"
                                    + (f": failed: {error}" if error else ""),
                                    err=True,
                                )
            finally:
                browser.close()
    results = [
        compare(state, OUT / state.name, failures[state.name]) for state in STATES
    ]
    changed = [r for r in results if r.changed]
    failed = [r for r in results if r.failed]
    click.echo(
        f"base {commits['base'][:10]} vs head {commits['head'][:10]}: "
        f"{len(changed)} of {len(STATES)} states changed, {len(failed)} failed"
    )
    for r in changed:
        click.echo(
            f"  changed {r.state.name}: {r.changed} px in {r.box} -> "
            f"{OUT / r.state.name}"
        )
    for r in failed:
        for arm, error in r.failed.items():
            click.echo(f"  failed {r.state.name} on {arm}: {error}")
    click.echo(f"report: {report(results, commits)}")


if __name__ == "__main__":
    main()
