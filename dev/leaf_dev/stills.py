"""Screenshot a fixed catalogue of UI states on BASE_REF's runtime and HEAD's, and
show which ones changed.

    uv run leaf-dev stills [BASE_REF]

BASE_REF defaults to the merge base of HEAD and `main`; each arm is the payload at its
commit (`leaf_dev.harness.build_pair`), so commit what you want compared. Each page is
built from this checkout's example source and served by the arm's own launcher, so
only the runtime, theme and server differ between the two stills of a state.

A state is an example, a viewport and color scheme, and the input that brings a fresh
tab there (`DRIVERS`, which `leaf-dev probe --do drive:NAME` also runs). The catalogue
(`STATES`) covers states a user reaches by acting, not only pages at rest; add one
where a change touches a surface it does not reach.

A state changed when any pixel differs. Each state's directory under `.tmp/stills/`
holds `base.png` and `head.png`, and for a change `base-crop.png` and `head-crop.png`
cropped to the changed region, ready to hand off as an `lf-shot` pair, and `diff.png`
marking the changed pixels.
"""

import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import click
from leaf.render_checks import PageNotReady
from PIL import Image, ImageChops
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from leaf_dev import ROOT
from leaf_dev.browser import BESIDE, DESKTOP, chrome, load, settle, tab
from leaf_dev.harness import build_pair, serving_source

OUT = ROOT / ".tmp" / "stills"
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


DRIVERS: dict[str, Callable[[Page], None]] = {
    drive.__name__.replace("_", "-"): drive
    for drive in (
        at_rest,
        card_by_pointer,
        card_by_keyboard,
        card_reply,
        threads_panel,
        composer,
        card_grabbed,
        code_focused,
    )
}


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


def capture(browser, address: str, state: State, path: Path) -> None:
    """Bring a fresh tab to `state` and screenshot its viewport to `path`."""
    with tab(browser, state.viewport, state.scheme) as page:
        load(page, address)
        state.drive(page)
        settle(page)
        page.screenshot(path=path)


def compare(folder: Path) -> int:
    """How many pixels the two stills in `folder` differ by; where they differ, write
    the crops and the diff."""
    base = Image.open(folder / "base.png").convert("RGB")
    head = Image.open(folder / "head.png").convert("RGB")
    # A pixel's largest difference in any one channel.
    red, green, blue = ImageChops.difference(base, head).split()
    largest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    mask = largest.point(lambda v: 255 if v else 0)
    changed = mask.histogram()[255]
    if changed:
        left, top, right, bottom = mask.getbbox()
        box = (
            max(left - CROP_MARGIN, 0),
            max(top - CROP_MARGIN, 0),
            min(right + CROP_MARGIN, head.width),
            min(bottom + CROP_MARGIN, head.height),
        )
        base.crop(box).save(folder / "base-crop.png")
        head.crop(box).save(folder / "head-crop.png")
        faded = Image.blend(head, Image.new("RGB", head.size, "white"), 0.6)
        faded.paste(Image.new("RGB", head.size, (220, 0, 0)), mask=mask)
        faded.crop(box).save(folder / "diff.png")
    return changed


@click.command()
@click.argument("base_ref", required=False)
def stills(base_ref: str | None) -> None:
    """Screenshot a catalogue of UI states on BASE_REF's runtime and HEAD's, and crop
    each state that changed into a before/after pair under .tmp/stills/."""
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    failed: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="leaf-stills-") as built:
        scratch = Path(built)
        arms, commits = build_pair(base_ref, scratch)
        with chrome() as browser:
            for source in dict.fromkeys(state.source for state in STATES):
                for arm, arm_dir in arms.items():
                    with serving_source(
                        arm_dir,
                        ROOT / "examples" / f"{source}.html",
                        scratch / f"{arm}-{source}",
                    ) as address:
                        for state in STATES:
                            if state.source != source:
                                continue
                            folder = OUT / state.name
                            folder.mkdir(exist_ok=True)
                            try:
                                capture(browser, address, state, folder / f"{arm}.png")
                            except (PlaywrightError, PageNotReady) as error:
                                failed[state.name] = (
                                    f"on {arm}: {str(error).splitlines()[0]}"
                                )
    click.echo(f"base {commits['base'][:10]} vs head {commits['head'][:10]}")
    unchanged = 0
    for state in STATES:
        folder = OUT / state.name
        if state.name in failed:
            click.echo(f"  failed  {state.name} {failed[state.name]}")
        elif changed := compare(folder):
            click.echo(f"  changed {state.name}: {changed} px -> {folder}")
        else:
            unchanged += 1
    click.echo(f"{unchanged} of {len(STATES)} states unchanged")
