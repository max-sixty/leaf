"""Screenshot a fixed catalogue of UI states on BASE_REF's runtime and HEAD's, and
show which ones changed.

    uv run leaf-dev stills [BASE_REF]

BASE_REF defaults to the merge base of HEAD and `main`; each arm is the payload at its
commit (`leaf_dev.harness.build_pair`), so commit what you want compared. Each page is
built from this checkout's example source and served by the arm's own launcher, so
only the runtime, theme and server differ between the two stills of a state.

A state is an example, a viewport, a color scheme and a pointer, and the input that
brings a fresh tab there (`DRIVERS`, which `leaf-dev probe --do drive:NAME` also runs).
The catalogue (`STATES`) covers states a user reaches by acting, not only pages at rest;
add one where a change touches a surface it does not reach.

Whether a state changed, and where, is `lf-shot`'s reading of its two stills, from the
module that owns the rule (`runtime/image-difference.js`), loaded into the browser.
Each state's directory under `.tmp/stills/` holds `base.png` and `head.png`, and for a
change `base-crop.png` and `head-crop.png` cropped to the union of its regions (or
whole, when the reading names none), ready to hand off as an `lf-shot` pair, and
`diff.png` outlining the head's own regions, a change in red and a move in blue. The
crops cover both stills' regions.
"""

import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import click
from leaf.render_checks import PageNotReady
from PIL import Image, ImageDraw
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from leaf_dev import ROOT
from leaf_dev.browser import BESIDE, DESKTOP, chrome, load, settle, tab
from leaf_dev.harness import build_pair, serving_source

OUT = ROOT / ".tmp" / "stills"
CROP_MARGIN = 32
DIFFERENCE = ROOT / "skills" / "leaf" / "assets" / "runtime" / "image-difference.js"
# Where `differences` serves the stills and the module that compares them.
ORIGIN = "http://stills.invalid"
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


def card_reply_sent(page: Page) -> None:
    """The margin card's message metadata after sending a reply."""
    card_reply(page)
    card = page.locator(".lf-margin-preview")
    card.get_by_role("button", name="Send", exact=True).click()
    card.locator("[data-event].user .lf-msg-sending").last.wait_for()


def card_reply_large(page: Page) -> None:
    """A pasted reply exhausting the room below the thread, with its caret at the end."""
    card_reply(page)
    page.keyboard.insert_text("\n" + "\n".join(f"Reply line {n}" for n in range(40)))


def threads_panel(page: Page) -> None:
    """The Threads panel, opened from the banner."""
    page.locator(".lf-threads-toggle").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-thread-panel')?.checkVisibility()"
    )


def panel_by_keyboard(page: Page) -> None:
    """The Threads panel with keyboard focus on its current title."""
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    page.wait_for_function(
        "() => document.querySelector('.lf-thread-panel')?.checkVisibility()"
    )
    page.wait_for_function(
        "() => document.activeElement?.matches('.lf-thread-summary')"
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


def code_note(page: Page) -> None:
    """The first code block with a note, the note in view."""
    page.locator("lf-code pre lf-note").first.evaluate(
        "note => note.scrollIntoView({block: 'center'})"
    )


def wide_passage(page: Page) -> None:
    """A selected passage in a wide block, with its comment field beside it."""
    page.locator('#bg-gallery-tabs [role="tab"]').get_by_text(
        "Threads", exact=True
    ).click()
    page.locator("#bg-wide-passage").evaluate(
        "el => el.scrollIntoView({block: 'center'})"
    )
    page.keyboard.press("/")
    page.keyboard.insert_text('"keep the active card"')
    page.keyboard.press("Enter")
    page.locator(".lf-fab-input").wait_for(state="visible")


def multiline_passage(page: Page) -> None:
    """A passage beginning midline and ending on a line that starts further left."""
    page.locator('#bg-gallery-tabs [role="tab"]').get_by_text(
        "Threads", exact=True
    ).click()
    page.locator("#bg-wide-passage").evaluate(
        "el => el.scrollIntoView({block: 'center'})"
    )
    first, last = page.evaluate("""() => {
      const walker = document.createTreeWalker(
        document.querySelector('#bg-wide-passage code'), NodeFilter.SHOW_TEXT);
      const range = document.createRange();
      for (let node; (node = walker.nextNode());) {
        if (node.data.includes('Keep')) range.setStart(node, node.data.indexOf('Keep'));
        if (node.data.includes('card')) range.setEnd(node, node.data.indexOf('card') + 4);
      }
      const fragments = [...range.getClientRects()].filter(r => r.width && r.height);
      return [fragments[0].toJSON(), fragments.at(-1).toJSON()];
    }""")
    page.mouse.move(first["left"] + 1, first["top"] + first["height"] / 2)
    page.mouse.down()
    page.mouse.move(last["right"] - 1, last["top"] + last["height"] / 2, steps=8)
    page.mouse.up()
    page.locator(".lf-fab-input").wait_for(state="visible")


def code_copy_by_pointer(page: Page) -> None:
    """Code's corner control revealed by hovering its source."""
    code_note(page)
    page.locator("lf-code pre").first.hover()


def code_copy_by_keyboard(page: Page) -> None:
    """Code's corner control with the keyboard focus ring visible."""
    code_note(page)
    page.keyboard.press("Tab")
    page.locator("lf-code .lf-code-copy").first.get_by_role("button").focus()


def code_source_by_touch(page: Page) -> None:
    """Reading code by touch, with the corner control disclosed away."""
    code_note(page)
    page.locator("lf-code pre").first.tap(position={"x": 60, "y": 20})


def pane_focused(page: Page) -> None:
    """A workspace pane's body focused by keyboard: a pane standing flush with the
    workspace's own scrollport, which clipped a ring drawn outside the body."""
    page.keyboard.press("Tab")
    page.locator("#sort-source").focus()


def element_thread(page: Page) -> None:
    """An element holding a thread, in view, with nothing indicating it."""
    page.locator("#off-t-vendor").evaluate("el => el.scrollIntoView({block: 'center'})")


def versions_menu(page: Page) -> None:
    """The Versions menu, opened from More: a row for each version, with its note."""
    page.locator(".lf-banner-more").click()
    page.locator(".lf-version").click()
    page.locator(".lf-version-menu .lf-version-row").first.wait_for()


def go_to(page: Page) -> None:
    """The Go-to sequence armed from the keyboard, its destinations on the line."""
    page.keyboard.press("g")
    page.wait_for_function("() => document.body.hasAttribute('data-lf-go-to-active')")


DRIVERS: dict[str, Callable[[Page], None]] = {
    drive.__name__.replace("_", "-"): drive
    for drive in (
        at_rest,
        card_by_pointer,
        card_by_keyboard,
        card_reply,
        card_reply_sent,
        card_reply_large,
        threads_panel,
        panel_by_keyboard,
        panel_reply_sent,
        composer,
        card_grabbed,
        code_note,
        wide_passage,
        multiline_passage,
        code_copy_by_pointer,
        code_copy_by_keyboard,
        code_source_by_touch,
        pane_focused,
        element_thread,
        versions_menu,
        go_to,
    )
}


@dataclass(frozen=True)
class State:
    name: str
    source: str
    drive: Callable[[Page], None]
    viewport: tuple[int, int] = DESKTOP
    scheme: str = "light"
    touch: bool = False


STATES = (
    State("gallery-tabs", "developer/feature-gallery", at_rest),
    State("gallery-wide-passage", "developer/feature-gallery", wide_passage),
    State("gallery-multiline-passage", "developer/feature-gallery", multiline_passage),
    State("plan", "review-a-plan", at_rest),
    State("plan-dark", "review-a-plan", at_rest, scheme="dark"),
    State("plan-beside", "review-a-plan", at_rest, viewport=BESIDE),
    State("plan-card", "review-a-plan", card_by_pointer),
    State("plan-card-keyboard", "review-a-plan", card_by_keyboard),
    State("plan-card-keyboard-dark", "review-a-plan", card_by_keyboard, scheme="dark"),
    State("plan-card-reply", "review-a-plan", card_reply),
    State(
        "plan-card-reply-large", "review-a-plan", card_reply_large, viewport=(1440, 600)
    ),
    State("plan-card-beside", "review-a-plan", card_by_pointer, viewport=BESIDE),
    State("plan-panel", "review-a-plan", threads_panel),
    State("plan-panel-dark", "review-a-plan", threads_panel, scheme="dark"),
    State(
        "plan-panel-keyboard-dark", "review-a-plan", panel_by_keyboard, scheme="dark"
    ),
    State("plan-panel-keyboard", "review-a-plan", panel_by_keyboard),
    State("plan-panel-beside", "review-a-plan", threads_panel, viewport=BESIDE),
    State("plan-go-to", "review-a-plan", go_to, viewport=(1024, 768)),
    State("plan-narrow", "review-a-plan", at_rest, viewport=(360, 740)),
    State(
        "plan-versions-touch",
        "review-a-plan",
        versions_menu,
        viewport=(390, 844),
        touch=True,
    ),
    State(
        "plan-panel-touch",
        "review-a-plan",
        threads_panel,
        viewport=(390, 844),
        touch=True,
    ),
    # Last on its page, since the reply it sends stays in the log.
    State("plan-panel-sent", "review-a-plan", panel_reply_sent),
    State("plan-card-sent", "review-a-plan", card_reply_sent),
    State("triage", "triage-board", at_rest),
    State("triage-composer", "triage-board", composer),
    State("triage-grabbed", "triage-board", card_grabbed),
    State("walkthrough-code", "pr-walkthrough", code_note),
    State("walkthrough-code-dark", "pr-walkthrough", code_note, scheme="dark"),
    State("walkthrough-copy-hover", "pr-walkthrough", code_copy_by_pointer),
    State("walkthrough-copy-keyboard", "pr-walkthrough", code_copy_by_keyboard),
    State(
        "walkthrough-copy-touch",
        "pr-walkthrough",
        code_note,
        viewport=(390, 844),
        touch=True,
    ),
    State(
        "walkthrough-source-touch",
        "pr-walkthrough",
        code_source_by_touch,
        viewport=(390, 844),
        touch=True,
    ),
    State("ship-thread", "ship-review", element_thread),
    State(
        "ship-card-short-window", "ship-review", card_by_pointer, viewport=(1440, 480)
    ),
    State(
        "ship-card-short-window-dark",
        "ship-review",
        card_by_pointer,
        viewport=(1440, 480),
        scheme="dark",
    ),
    State(
        "ship-card-touch",
        "ship-review",
        card_by_pointer,
        viewport=(390, 500),
        touch=True,
    ),
    State("sort", "rust-sort", at_rest),
    State("sort-pane", "rust-sort", pane_focused),
    State("sort-pane-dark", "rust-sort", pane_focused, scheme="dark"),
)


def capture(browser, address: str, state: State, path: Path) -> None:
    """Bring a fresh tab to `state` and screenshot its viewport to `path`."""
    with tab(browser, state.viewport, state.scheme, state.touch) as page:
        load(page, address)
        state.drive(page)
        settle(page)
        page.screenshot(path=path)


def differences(browser, names: list[str]) -> dict[str, dict]:
    """`lf-shot`'s reading of each named state's two stills, from the module that
    owns it, served beside them to a blank page."""

    def serve(route) -> None:
        path = route.request.url.removeprefix(ORIGIN)
        if path == "/image-difference.js":
            route.fulfill(path=DIFFERENCE, content_type="text/javascript")
        elif path.endswith(".png"):
            route.fulfill(path=OUT / path.lstrip("/"))
        else:
            route.fulfill(body="<!doctype html>", content_type="text/html")

    context = browser.new_context()
    try:
        context.route(f"{ORIGIN}/**", serve)
        page = context.new_page()
        page.goto(f"{ORIGIN}/")
        return {
            name: page.evaluate(
                """async (name) => {
                  const { compareImages } = await import("/image-difference.js");
                  const load = async (arm) => {
                    const image = new Image();
                    image.src = `/${name}/${arm}.png`;
                    await image.decode();
                    return image;
                  };
                  return compareImages(await load("base"), await load("head"));
                }""",
                name,
            )
            for name in names
        }
    finally:
        context.close()


def crop(folder: Path, regions: list[dict]) -> None:
    """Write the crops of the two stills in `folder` around `regions`, and the diff."""
    base = Image.open(folder / "base.png").convert("RGB")
    head = Image.open(folder / "head.png").convert("RGB")
    box = (
        (
            max(min(r["x"] for r in regions) - CROP_MARGIN, 0),
            max(min(r["y"] for r in regions) - CROP_MARGIN, 0),
            min(max(r["x"] + r["width"] for r in regions) + CROP_MARGIN, head.width),
            min(max(r["y"] + r["height"] for r in regions) + CROP_MARGIN, head.height),
        )
        if regions
        else (0, 0, head.width, head.height)
    )
    base.crop(box).save(folder / "base-crop.png")
    head.crop(box).save(folder / "head-crop.png")
    faded = Image.blend(head, Image.new("RGB", head.size, "white"), 0.6)
    draw = ImageDraw.Draw(faded)
    for r in (r for r in regions if r["side"] == "after"):
        draw.rectangle(
            (r["x"] - 3, r["y"] - 3, r["x"] + r["width"] + 2, r["y"] + r["height"] + 2),
            outline=(220, 0, 0) if r["kind"] == "changed" else (40, 110, 230),
            width=2,
        )
    faded.crop(box).save(folder / "diff.png")


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
            read = differences(
                browser, [state.name for state in STATES if state.name not in failed]
            )
    click.echo(f"base {commits['base'][:10]} vs head {commits['head'][:10]}")
    unchanged = 0
    for state in STATES:
        folder = OUT / state.name
        if state.name in failed:
            click.echo(f"  failed  {state.name} {failed[state.name]}")
        elif (difference := read[state.name])["changed"]:
            crop(folder, difference["regions"])
            click.echo(
                f"  changed {state.name}: {difference['changed']} px -> {folder}"
            )
        else:
            unchanged += 1
    click.echo(f"{unchanged} of {len(STATES)} states unchanged")
