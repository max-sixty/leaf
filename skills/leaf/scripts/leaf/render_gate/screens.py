"""The screens `page check --render` saves for the author to read.

The gate's findings say what is broken; they cannot say whether the page reads well,
which is the author's judgment of a picture. So the check saves the page as a reader
meets it: down the page three times, on a desktop, in the widest window the sweep
reaches, where what scales with the window is at its largest, and on a phone, each as
far as its first eight screens, where a reader decides whether to go on, with the
label saying how many of the page's screens they are; one screen at each width
where the page's own arrangement is at its tightest before it changes, or where its
margin content changes, with that box in view; and, on a page with Asks, the desktop
window at each of its first eight open ones as `a` arrives there from the top, which is
how a user working the page reads each question, with the view that holds it opened;
`a` walks everything waiting on the user, so a thread it stops at on the way gets no
screen. The screens go to one directory per page
under the state home's screens/, which the check names; a check writes a fresh
directory beside it and then puts it in its place, so a reader never meets half of one
check's screens and half of another's. The page directory is the page's record, and a
file there would count as activity on the page.

A screen is the window as the reader sees it, fixed chrome included, scrolled by most
of a window at a time, because the document is the page's scroller and a full-page
capture would draw the banner and bottom bar in the wrong places."""

import shutil
import tempfile
from pathlib import Path

from leaf.machine import state_home
from leaf.render_checks import RENDER_VIEWPORT, rendered, wait_until_ready
from leaf.render_gate.readings import SWEEP_WIDTHS
from leaf.state import page_key

PHONE = {"width": 390, "height": 844}
# How far down a long page the screens go.
MOST_SCREENS = 8


def _open(browser, url: str, viewport: dict, phone: bool):
    context = browser.new_context(
        viewport=viewport,
        color_scheme="light",
        is_mobile=phone,
        has_touch=phone,
        reduced_motion="reduce",
    )
    page = context.new_page()
    page.goto(url)
    wait_until_ready(page)
    rendered(page)
    return context, page


def _down_the_page(page, into: Path, stem: str) -> tuple[list[Path], int]:
    """The page's first screens, and how many screens the whole page takes."""
    height = page.viewport_size["height"]
    tall = page.evaluate("document.documentElement.scrollHeight")
    step = int(height * 0.85)
    total = 1 + max(0, tall - height + step - 1) // step
    shots = []
    for k in range(min(MOST_SCREENS, total)):
        page.evaluate("top => window.scrollTo(0, top)", k * step)
        rendered(page)
        shot = into / f"{stem}-{k + 1}.png"
        page.screenshot(path=shot)
        shots.append(shot)
    return shots, total


# Where a press of `a` left the user: the Ask they stand in, as the runtime marks it
# (the outermost element wearing its ring, outside the Asks drawer, which mirrors the
# same reading), or else the thread holding focus, the walk's other kind of stop.
STANDING_ITEM = """() => {
  const ask = [...document.querySelectorAll('[data-lf-ask]:not(.lf-asks-row)')]
    .find((el) => !el.parentElement?.closest('[data-lf-ask]'))?.id;
  if (ask) return {ask: true, id: ask};
  let held = document.activeElement;
  while (held?.shadowRoot?.activeElement) held = held.shadowRoot.activeElement;
  const thread = held?.closest?.('.lf-thread, .lf-page-thread');
  const id = thread?.dataset.id ?? thread?.dataset.thread;
  return id ? {ask: false, id} : null;
}"""


def _asks_in_turn(page, into: Path) -> tuple[list[Path], bool]:
    """The window at each open Ask `a` reaches from the top, as far as MOST_SCREENS,
    and whether the walk goes on past them. Which Ask a press reached is the runtime's
    own mark, so the walk covers whatever `a` does, a suggestion as much as an
    `lf-ask`. The walk stops at its last item rather than wrapping, so a press that
    stays on the same item has reached the end."""
    shots, seen = [], None
    while True:
        page.keyboard.press("a")
        rendered(page)
        here = page.evaluate(STANDING_ITEM)
        if here is None or here == seen:
            return shots, False
        seen = here
        if not here["ask"]:
            continue
        if len(shots) == MOST_SCREENS:
            return shots, True
        shot = into / f"{page.viewport_size['width']}px-ask-{len(shots) + 1}.png"
        page.screenshot(path=shot)
        shots.append(shot)


def page_files(kind: str, page_dir: Path) -> Path:
    """The state home's directory of `kind` files for one page, the same for every
    command that writes them: named for the page, and keyed so that two pages of one
    name keep apart."""
    return state_home() / kind / f"{page_dir.name}-{page_key(page_dir)[:12]}"


def screens_dir(page_dir: Path) -> Path:
    """The page's screens directory, the same for every check of that page."""
    return page_files("screens", page_dir)


def save_screens(
    browser, url: str, reading, page_dir: Path
) -> tuple[Path, list[tuple[Path, str]]]:
    """Save the screens for `reading`'s page, replacing the last check's; return their
    directory and each file with what it shows."""
    final = screens_dir(page_dir)
    final.parent.mkdir(exist_ok=True)
    into = Path(tempfile.mkdtemp(dir=final.parent, prefix=f".{final.name}-"))
    saved = []

    def whole(viewport, phone, label):
        context, page = _open(browser, url, viewport, phone)
        try:
            shots, total = _down_the_page(page, into, f"{viewport['width']}px")
            if total > len(shots):
                label = f"{label}, the first {len(shots)} of the page's {total} screens"
            saved.extend((shot, label) for shot in shots)
        finally:
            context.close()

    def one(width, selector, name, label):
        viewport = {"width": width, "height": RENDER_VIEWPORT["height"]}
        context, page = _open(browser, url, viewport, False)
        try:
            page.evaluate(
                "(s) => document.querySelector(s)?.scrollIntoView({block: 'start'})",
                selector,
            )
            rendered(page)
            shot = into / f"{width}px-{name}.png"
            page.screenshot(path=shot)
            saved.append((shot, label))
        finally:
            context.close()

    whole(RENDER_VIEWPORT, False, "desktop")
    context, page = _open(browser, url, RENDER_VIEWPORT, False)
    try:
        shots, more = _asks_in_turn(page, into)
        label = "desktop, each press of `a` from the top, at the next open Ask"
        if more:
            label = f"{label}, the first {len(shots)} of the page's open Asks"
        saved.extend((shot, label) for shot in shots)
    finally:
        context.close()
    widest = {"width": max(SWEEP_WIDTHS), "height": RENDER_VIEWPORT["height"]}
    whole(widest, False, "the widest window")
    for width, selector, said in reading.arrangement:
        one(width, selector, "arrangement", f"the tightest before {said}")
    for width in reading.margin_widths:
        one(width, "main", "margin", "where the page's margin content changes")
    whole(PHONE, True, "phone")
    if final.exists():
        shutil.rmtree(final)
    into.rename(final)
    return final, [(final / shot.name, label) for shot, label in saved]
