"""Screenshot a fixed catalogue of UI states on BASE_REF's runtime and HEAD's, and
show which ones changed.

    uv run leaf-dev stills [BASE_REF]

BASE_REF defaults to the merge base of HEAD and `main`. Each arm is the plugin payload
at its commit (`leaf_dev.harness.build_pair`), so commit what you want compared. Every
page is built from this checkout's example source by the arm's own launcher and served
by that arm's `leaf server run --temporary`, so only the runtime, theme and server
differ between the two stills of a state.

A state is an example, a viewport and color scheme, and the input that brings the page
there from a fresh load (`DRIVERS`): a margin card opened by pointer or by keyboard, a
reply being drafted, the Threads panel open and a reply sent from it, a board card
grabbed, a code block focused. `leaf-dev probe --do drive:NAME` runs the same input.
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


def panel_reply_sent(page: Page) -> None:
    """A reply sent from the Threads panel's open thread, its stage on the message
    and the thread's attention on the other rows."""
    threads_panel(page)
    thread = page.locator(".lf-thread[open]")
    thread.locator("leaf-text").focus()
    page.keyboard.insert_text("A reply sent from the panel")
    thread.get_by_role("button", name="Send", exact=True).click()
    thread.locator(".lf-msg.user .lf-msg-sending").last.wait_for()


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
        panel_reply_sent,
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
    # Last on its page, since the reply it sends stays in the log.
    State("plan-panel-sent", "review-a-plan", panel_reply_sent),
    State("triage", "triage-board", at_rest),
    State("triage-composer", "triage-board", composer),
    State("triage-grabbed", "triage-board", card_grabbed),
    State("walkthrough-code", "pr-walkthrough", code_focused),
    State("walkthrough-code-dark", "pr-walkthrough", code_focused, scheme="dark"),
)


def capture(browser, address: str, state: State, path: Path) -> str | None:
    """Bring a fresh tab to `state` and screenshot its viewport to `path`; return
    the error if the state's input failed."""
    try:
        with tab(browser, state.viewport, state.scheme) as page:
            load(page, address)
            state.drive(page)
            settle(page)
            page.screenshot(path=path)
    except (PlaywrightError, PageNotReady) as error:
        return str(error).splitlines()[0]
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
def stills(base_ref: str | None) -> None:
    """Screenshot a catalogue of UI states on BASE_REF's runtime and HEAD's, and crop
    each state that changed into a before/after pair under .tmp/stills/."""
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    failures: dict[str, dict] = {state.name: {} for state in STATES}
    with tempfile.TemporaryDirectory(prefix="leaf-stills-") as built:
        scratch = Path(built)
        arms, commits = build_pair(base_ref, scratch)
        with chrome() as browser:
            for source in dict.fromkeys(state.source for state in STATES):
                states = [state for state in STATES if state.source == source]
                for arm, arm_dir in arms.items():
                    with serving_source(
                        arm_dir,
                        ROOT / "examples" / f"{source}.html",
                        scratch / f"{arm}-{source}",
                    ) as address:
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
