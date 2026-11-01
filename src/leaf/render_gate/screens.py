"""The screens `page check --render` saves for the author to read.

The gate's findings say what is broken; they cannot say whether the page reads well,
which is the author's judgment of a picture. The check captures a fresh desktop
arrival, then resizes that desktop through selected expansion views: the widest
window the sweep reaches, followed by the widths where the page's arrangement is
at its tightest before it changes or its margin content changes. These are resized
desktop views, not fresh arrivals at each width or a replay of every sweep width;
page code that depends on its initial window keeps the desktop's startup state.
A separate fresh phone supplies mobile input capabilities from startup.

Desktop, widest-window and phone captures each cover the first eight screens at
most, with the label saying how many of the page's screens they are. Arrangement
captures show the box that changed. An independent desktop arrival walks the first
eight open obligations with `m` from the top, opening the view that holds each one;
this keeps the walk's opened disclosures out of the expansion views. `m` walks
everything waiting on the user, so a thread or a handed-back widget action it stops
at on the way gets no screen. The screens go to one directory per page under the
state home's screens/, which the check names; a check writes a fresh directory
beside it and then puts it in its place, so a reader never meets half of one check's
screens and half of another's. The page directory is the page's record, and a file
there would count as activity on the page.

A screen is the window as the reader sees it, fixed chrome included, scrolled by most
of a window at a time, because the document is the page's scroller and a full-page
capture would draw the floating panel in the wrong place."""

import shutil
import tempfile
from pathlib import Path

from leaf.render_checks import rendered, wait_until_ready
from leaf.render_gate.readings import SWEEP_WIDTHS, settle_at
from leaf.state import page_key, state_home

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


# Where a press of `m` left the user: the obligation they stand in, as the runtime marks it
# (the outermost element wearing its ring, outside the panel's On view, which mirrors the
# same reading); else the thread holding focus; else the page widget holding it, where
# the walk puts the user on an update handed back to them. Those are the walk's other
# kinds of stop (queue-walk.js), which the screens pass, so each is read only to step
# past it.
CURRENT_OBLIGATION = """() => {
  const item = [...document.querySelectorAll('[data-lf-obligation]')]
    .find((el) => !el.parentElement?.closest('[data-lf-obligation]'))?.id;
  if (item) return {obligation: true, id: item};
  let held = document.activeElement;
  while (held?.shadowRoot?.activeElement) held = held.shadowRoot.activeElement;
  const thread = held?.closest?.('.lf-thread, .lf-page-thread');
  const id = thread?.dataset.id ?? thread?.dataset.thread;
  if (id) return {obligation: false, id};
  const page = document.activeElement;
  const widget = page?.closest?.('.lf-chrome') ? null : page?.closest?.('[id]');
  return widget ? {obligation: false, id: widget.id} : null;
}"""


def _obligations_in_turn(page, into: Path) -> tuple[list[Path], bool]:
    """The window at each open obligation `m` reaches from the top, as far as MOST_SCREENS,
    and whether the walk goes on past them. Which obligation a press reached is the runtime's
    own mark, so the walk covers whatever `m` does, a suggestion as much as an
    `lf-ask`. The walk stops at its last item rather than wrapping, so a press that
    reaches an item it has already stood on has reached the end."""
    shots, seen = [], set()
    while True:
        page.keyboard.press("m")
        rendered(page)
        here = page.evaluate(CURRENT_OBLIGATION)
        if here is None or (here["obligation"], here["id"]) in seen:
            return shots, False
        seen.add((here["obligation"], here["id"]))
        if not here["obligation"]:
            continue
        if len(shots) == MOST_SCREENS:
            return shots, True
        shot = into / f"{page.viewport_size['width']}px-obligation-{len(shots) + 1}.png"
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
    browser, url: str, reading, page_dir: Path, desktop: dict
) -> tuple[Path, list[tuple[Path, str]]]:
    """Save the screens for `reading`'s page, replacing the last check's, with the
    desktop and wide screens at the `desktop` window's height; return their directory
    and each file with what it shows."""
    final = screens_dir(page_dir)
    final.parent.mkdir(exist_ok=True)
    into = Path(tempfile.mkdtemp(dir=final.parent, prefix=f".{final.name}-"))
    saved = []

    def whole(page, label):
        shots, total = _down_the_page(page, into, f"{page.viewport_size['width']}px")
        if total > len(shots):
            label = f"{label}, the first {len(shots)} of the page's {total} screens"
        saved.extend((shot, label) for shot in shots)

    context, page = _open(browser, url, desktop, False)
    try:
        obligation_shots, more = _obligations_in_turn(page, into)
        obligation_label = (
            "desktop, each press of `m` from the top, at the next open obligation"
        )
        if more:
            obligation_label = (
                f"{obligation_label}, the first {len(obligation_shots)}"
                " of the page's open obligations"
            )
    finally:
        context.close()
    context, page = _open(browser, url, desktop, False)
    try:
        whole(page, "desktop")
        saved.extend((shot, obligation_label) for shot in obligation_shots)
        settle_at(page, max(SWEEP_WIDTHS), desktop["height"])
        whole(page, "resized desktop, the widest window")
        for width, selector, said in reading.arrangement:
            settle_at(page, width, desktop["height"])
            page.evaluate(
                "(s) => document.querySelector(s)?.scrollIntoView({block: 'start'})",
                selector,
            )
            rendered(page)
            shot = into / f"{width}px-arrangement.png"
            page.screenshot(path=shot)
            saved.append((shot, f"resized desktop, the tightest before {said}"))
    finally:
        context.close()
    context, page = _open(browser, url, PHONE, True)
    try:
        whole(page, "phone")
    finally:
        context.close()
    if final.exists():
        shutil.rmtree(final)
    into.rename(final)
    return final, [(final / shot.name, label) for shot, label in saved]
