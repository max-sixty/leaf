"""Where a comment stands before and after Send: the comment box the user types in, and
the thread card the sent comment becomes.

Each case is one gesture at one window size: words selected in a long paragraph, or an
element pointed at with ⌥-click. It types a comment, reads where the box stands,
presses Enter, and reads where the card stands once placed. The snapshot records the
effect rather than the pixels, in one document a reviewer reads as a scoreboard, so a
change of a few pixels records nothing and a change in where either goes records a
line:

- `expected`: the side the case is built to give both.
- `side`: where each stands relative to what it is about: `right`, `left`, `below` or
  `above`. Where the case allows more than one side and the surface took one of them,
  it records the case's `expected`: which of under and over has more room turns on the
  fonts a platform draws the page in, and the snapshot is read on more than one.
  `moves` still says whether the card took the box's side.
- `stands`: whether it stands where that side puts it: beside the block `level with
  the words`, or `clear of the block` under or over it, else how far off.
- `moves`: how far the card stands from where the box stood, at the edge each holds
  (the left edge across; the top down, or the foot where the card stands above),
  bucketed `still` (the same place), `near` (a line or two) or `away`.

Each case also writes the pair it read to `.tmp/send-placement/<case>.png`: the box as
the user typed in it on the left, the card on the right with the box's outline drawn
over it, so a move shows at a glance. After an intentional change, re-record and read
the diff beside those pictures:

  uv run pytest --regtest-reset -n0 tests/test_render_send_placement.py"""

import base64
import io
import re
from pathlib import Path

import pytest
from interact_support import wait_for, yaml_document
from leaf.render_checks import rendered
from model_folds import leaf_page
from PIL import Image, ImageDraw
from playwright.sync_api import expect
from render_harness import (
    judge_watches,
    open_page,
    pane_posture,
    regions_side_by_side,
    resized,
    scroll_settled,
    select,
)

SHOTS = Path(__file__).resolve().parent.parent / ".tmp" / "send-placement"

# One source line, so a phrase's offset in the source is its offset in the text node.
LONG = (
    "The workflows currently replace the Actions working tree with PR code after "
    "trusted setup, so cleanup then needs local-action paths repaired before the next "
    "job can run. Repository setup runs separately from the agent, and Claude and "
    "Codex have different sandbox and shutdown paths, which means every change to one "
    "has to be mirrored by hand in the other. The runner checkout stays fixed while "
    "repository code moves into a disposable clone, and a trusted supervisor controls "
    "the whole run: setup, agent execution, process shutdown, then output collection. "
    "Nothing the agent writes survives the run except the outputs the supervisor "
    "collects, and the supervisor alone decides which of those reach the pull request. "
    "The setup and shutdown changes below incorporate the last two discussions, and "
    "the self-hosted rollout is the remaining decision."
)

PAGE = leaf_page(
    "Send placement",
    f"""
<h1 id="title">Move the agent runs into one sandbox</h1>
<p id="lede">The workflow's checkout and separate setup step become one disposable
working copy and one sandboxed execution path.</p>
<p id="long">{LONG}</p>
<ol id="steps">
<li id="step-checkout">Change the workflows. In the review and mention templates,
remove the second checkout and the cleanup of restored local actions.</li>
<li id="step-workspace">Add workspace preparation, which resolves the pull request,
clones it, and writes the manifest the supervisor reads.</li>
<li id="step-runner">Keep one runner per job, so a failed run leaves nothing behind
for the next.</li>
</ol>
<p id="close">The rollout order and the checks that gate each step follow once the
plan is settled.</p>
<p>A page long enough to scroll, so the room under and over each target includes
the room the page can make by scrolling.</p>
<p>Each paragraph here is only there to give the page its length.</p>
<p>The cases read where the box and the card stand, never these words.</p>
<p>The last paragraph of the page.</p>
""",
)

COMMENT = "This step should say which runner it targets"

# How far apart two places are before they read as different, in CSS pixels: within
# `STILL` they are the same place, within `NEAR` a line or two apart.
STILL = 8
NEAR = 48

# The client rectangle of a phrase in the long paragraph.
PHRASE = """(words) => {
  const text = document.querySelector('#long').firstChild;
  const range = document.createRange();
  range.setStart(text, text.data.indexOf(words));
  range.setEnd(text, text.data.indexOf(words) + words.length);
  return range;
}"""


class Passage:
    """Words in the long paragraph, selected by dragging across them or, under a
    finger, by the platform's selection and the banner's Comment on selection."""

    block = "#long"

    def __init__(self, words):
        self.words = words

    def open(self, page, touch):
        if touch:
            page.evaluate(
                f"""(words) => {{
                  getSelection().removeAllRanges();
                  getSelection().addRange(({PHRASE})(words));
                }}""",
                self.words,
            )
            page.locator(".lf-banner-actions").get_by_role(
                "button", name="Comment on selection"
            ).tap()
            return
        rect = self.line(page)
        y = rect["top"] + rect["height"] / 2
        select(page, (rect["left"] + 1, y), (rect["right"] - 1, y))
        page.locator(".lf-fab-input").click()

    def line(self, page):
        """Where the words stand now."""
        return page.evaluate(
            f"(words) => ({PHRASE})(words).getBoundingClientRect().toJSON()",
            self.words,
        )


class Element:
    """An element pointed at with ⌥-click, on its first line or, `from_foot`, that far
    over its last."""

    def __init__(self, block, from_foot=None):
        self.block = block
        self.from_foot = from_foot

    def open(self, page, touch):
        target = page.locator(self.block)
        y = (
            8
            if self.from_foot is None
            else target.bounding_box()["height"] - self.from_foot
        )
        target.click(modifiers=["Alt"], position={"x": 40, "y": y})

    def line(self, page):
        """Its top as the window shows it, which a scroll may have clipped."""
        return page.evaluate(
            """([selector, head]) => {
              const {left, top, right, bottom} = document.querySelector(selector)
                .getBoundingClientRect();
              return {left, top: Math.max(top, head), right, bottom};
            }""",
            [self.block, page.evaluate(BANNER_FOOT) + 8],
        )


FIRST_LINE = Passage("replace the Actions")
DEEP_LINE = Passage("supervisor alone decides")
STEP = Element("#step-workspace")
# The long paragraph as a whole, pointed at on its last line.
TALL = Element("#long", from_foot=12)

# name: (window size, under a finger, what the comment is on, the side both should
# take, and optionally how the case differs: `top`, the fraction of the window's height
# its block's top is scrolled to, 0.4 unless it says; `again`, a thread already there,
# so its margin row stands before the box opens).
CASES = {
    "column-passage-first-line": ((1440, 900), False, FIRST_LINE, "right"),
    "column-passage-deep-line": ((1440, 900), False, DEEP_LINE, "right"),
    "column-element": ((1440, 900), False, STEP, "right"),
    "wide-passage-deep-line": ((1920, 1080), False, DEEP_LINE, "right"),
    # Room right of the paragraph for the box's minimum but not the card's.
    "laptop-passage": ((1300, 900), False, FIRST_LINE, "below or above"),
    "laptop-element": ((1240, 900), False, STEP, "below or above"),
    "narrow-rail-passage": ((1100, 800), False, FIRST_LINE, "below or above"),
    "beside-passage": ((900, 900), False, FIRST_LINE, "below or above"),
    "beside-element": ((900, 900), False, STEP, "below or above"),
    "phone-passage": ((390, 844), False, FIRST_LINE, "below or above"),
    "phone-touch-passage": ((390, 844), True, FIRST_LINE, "below"),
    # A block whose top the window has scrolled past.
    "beside-tall-element-clipped": (
        (900, 500),
        False,
        TALL,
        "below or above",
        {"top": -0.3},
    ),
    "wide-passage-with-a-thread": (
        (1920, 1080),
        False,
        FIRST_LINE,
        "right",
        {"again": True},
    ),
}

BANNER_FOOT = (
    "() => document.querySelector('.lf-banner').getBoundingClientRect().bottom"
)

SIDES = {
    "right-start": "right",
    "left-start": "left",
    "bottom-start": "below",
    "top-start": "above",
}

RECT = """(selector) => {
  const {left, top, right, bottom} = document.querySelector(selector)
    .getBoundingClientRect();
  return {left, top, right, bottom};
}"""


def stands(side, rect, words, block):
    """Whether a box on `side` stands where that side puts it: beside the block, its
    top level with the words' line; or under or over the block, clear of it."""
    if side in ("right", "left"):
        off = rect["top"] - words["top"]
        if abs(off) <= STILL:
            return "level with the words"
        return f"{distance(off)} {'under' if off > 0 else 'over'} the words"
    off = (
        rect["top"] - block["bottom"]
        if side == "below"
        else block["top"] - rect["bottom"]
    )
    return (
        "clear of the block" if 0 <= off <= NEAR else f"{distance(off)} off the block"
    )


def distance(pixels):
    pixels = abs(pixels)
    return "still" if pixels <= STILL else "near" if pixels <= NEAR else "away"


def movement(box, card, side):
    held = "bottom" if side == "above" else "top"
    across = card["left"] - box["left"]
    down = card[held] - box[held]
    return {
        "across": f"{distance(across)}{direction(across, 'right', 'left')}",
        "down": f"{distance(down)}{direction(down, 'down', 'up')}",
    }


def direction(pixels, positive, negative):
    if abs(pixels) <= STILL:
        return ""
    return f" {positive if pixels > 0 else negative}"


def picture(name, before, after, box):
    """The box and the card side by side, the box's outline drawn over the card."""
    left = Image.open(io.BytesIO(before)).convert("RGB")
    right = Image.open(io.BytesIO(after)).convert("RGB")
    scale = right.width / left.width
    ImageDraw.Draw(right).rectangle(
        [box[edge] * scale for edge in ("left", "top", "right", "bottom")],
        outline=(220, 0, 0),
        width=3,
    )
    pair = Image.new("RGB", (left.width * 2 + 12, left.height), (220, 0, 0))
    pair.paste(left, (0, 0))
    pair.paste(right, (left.width + 12, 0))
    pair.save(SHOTS / f"{name}.png")


def send_one(page, on, touch):
    """A thread on what the case's comment is on, its card put away."""
    on.open(page, touch)
    page.keyboard.insert_text("An earlier comment")
    page.keyboard.press("Enter")
    card = page.locator(".lf-margin-preview")
    expect(card).to_have_attribute("data-lf-thread-placement", re.compile(".+"))
    page.keyboard.press("Escape")
    page.mouse.click(4, 300)
    expect(card).to_be_hidden()
    rendered(page)


def sent(browser, serve, name):
    """The case's reading: where the box stood with the comment typed, and where the
    card stands once the comment is sent, both in the page as it stood before Send."""
    size, touch, on, expected, *rest = CASES[name]
    differs = rest[0] if rest else {}
    context = browser.new_context(
        viewport={"width": size[0], "height": size[1]},
        reduced_motion="reduce",
        has_touch=touch,
        is_mobile=touch,
    )
    page = open_page(browser, serve(PAGE), context=context)
    if differs.get("again"):
        send_one(page, on, touch)
    page.locator(on.block).evaluate(
        "(el, at) => scrollTo(0, el.getBoundingClientRect().top + scrollY - innerHeight * at)",
        differs.get("top", 0.4),
    )
    rendered(page)
    on.open(page, touch)
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_have_attribute("data-lf-placement", re.compile(".+"))
    page.keyboard.insert_text(COMMENT)
    rendered(page)
    box_side = SIDES[bar.get_attribute("data-lf-placement")]
    box = page.evaluate(RECT, ".lf-fab-input")
    words, block = on.line(page), page.evaluate(RECT, on.block)
    scrolled = page.evaluate("scrollY")
    before = page.screenshot()

    # A phone's Return starts a new line, so a finger sends with the box's own button.
    if touch:
        bar.get_by_role("button", name="Comment", exact=True).tap()
    else:
        page.keyboard.press("Enter")
    card = page.locator(".lf-margin-preview")
    expect(card, f"{name}: the sent comment opens its card").to_have_attribute(
        "data-lf-thread-placement", re.compile(".+")
    )
    expect(card).to_have_css("opacity", "1")
    rendered(page)
    card_side = card.get_attribute("data-lf-thread-placement")
    # A card that scrolled the page is read where it stands on the page the box stood on.
    carried = page.evaluate("scrollY") - scrolled
    placed = {
        edge: value + (carried if edge in ("top", "bottom") else 0)
        for edge, value in page.evaluate(RECT, ".lf-margin-preview").items()
    }
    picture(
        name,
        before,
        page.screenshot(),
        {
            edge: value - (carried if edge in ("top", "bottom") else 0)
            for edge, value in box.items()
        },
    )

    def allowed(side):
        return expected if side in expected.split(" or ") else side

    reading = {
        "expected": expected,
        "comment box": {
            "side": allowed(box_side),
            "stands": stands(box_side, box, words, block),
        },
        "thread card": {
            "side": allowed(card_side),
            "stands": stands(card_side, placed, words, block),
        },
        "moves": movement(box, placed, card_side),
    }
    # Read, the case is over. A page left open while the later cases run sees its
    # message's age turn from "just now" to "1m ago", which is not what this test reads.
    # Its last frames, Send's included, are judged first, as a test's end judges them.
    judge_watches()
    context.close()
    return reading


def test_where_a_comment_stands_before_and_after_send(browser, serve, snapshot):
    SHOTS.mkdir(parents=True, exist_ok=True)
    snapshot.check(
        yaml_document(
            "Where each case's comment box, and the thread card it became, stand.",
            {name: sent(browser, serve, name) for name in CASES},
        )
    )


@pytest.mark.parametrize("region", ["document", "pane"])
@pytest.mark.parametrize("route", ["target", "selection"])
def test_a_wheel_return_paints_the_comment_box_at_its_attachment_in_the_first_frame(
    browser, serve, region, route
):
    """The compositor returns CSS-anchored boxes before JS gets the scroll event.
    Reading rectangles in a frame forces layout and hides the stale placement, so
    observe compositor screenshots. Colored authored bands locate the two surfaces;
    their relative positions are the claim, independent of fonts or screenshot bytes."""
    marker_style = """<style>
      #paint-target { background: #ff0044; }
      .lf-fab-bar { outline: 2px solid #00cc44 !important; }
    </style>"""
    passage = '<p id="paint-target">The export keeps each tenant in an archive.</p>'
    if region == "document":
        source = leaf_page(
            "Compositor attachment",
            '<h1 id="title">Comments follow the passage</h1>'
            '<div style="height:650px"></div>'
            + passage
            + '<div style="height:1800px"></div>',
            head=marker_style,
        )
        size, wheel, scroller = (900, 600), 1500, None
    else:
        source = leaf_page(
            "Compositor attachment in a pane",
            '<header><h1 id="title">Comments follow the passage</h1></header>'
            '<div id="paint-split"><lf-pane id="paint-pane" label="Findings"><div>'
            '<div style="height:180px"></div>'
            + passage
            + '<div style="height:1600px"></div></div></lf-pane>'
            '<lf-pane id="other-pane" label="Notes"><div><p>Notes.</p></div></lf-pane></div>',
            head=marker_style + regions_side_by_side("paint-split"),
            layout="workspace",
        )
        size, wheel, scroller = (1440, 600), 1200, "#paint-pane > div"
    page = open_page(browser, serve(source))
    resized(page, *size)
    target = page.locator("#paint-target")
    if region == "document":
        target.evaluate(
            "node => scrollTo(0, node.getBoundingClientRect().top + scrollY - 400)"
        )
        rendered(page)
    else:
        pane_posture(page, page.locator("#paint-pane"), "bounded")
    if route == "target":
        target.click(modifiers=["Alt"], position={"x": 30, "y": 10})
    else:
        box = target.bounding_box()
        select(page, (box["x"] + 2, box["y"] + 10), (box["x"] + 150, box["y"] + 10))
        page.locator(".lf-fab-input").click()
    page.locator(".lf-fab-input").type("Keep these words while the page leaves. " * 6)
    rendered(page)
    cdp = page.context.new_cdp_session(page)
    events, complete = [], []
    cdp.on("Tracing.dataCollected", lambda data: events.extend(data["value"]))
    cdp.on("Tracing.tracingComplete", lambda _: complete.append(True))
    cdp.send(
        "Tracing.start",
        {
            "categories": "disabled-by-default-devtools.screenshot,benchmark",
            "transferMode": "ReportEvents",
        },
    )
    page.mouse.move(120 if scroller else 100, 350)
    page.mouse.wheel(0, wheel)
    scroll_settled(page, scroller)
    page.mouse.wheel(0, -wheel)
    scroll_settled(page, scroller)
    cdp.send("Tracing.end")

    def trace_finished():
        # Pump CDP delivery without reading the page or forcing its layout.
        cdp.send("Tracing.getCategories")
        return bool(complete)

    wait_for(
        trace_finished,
        bool,
        failure="Chrome never completed the compositor screenshot trace",
        timeout=10,
    )
    frames = [event for event in events if event["name"] == "Screenshot"]
    readings = []
    for event in frames:
        image = Image.open(
            io.BytesIO(base64.b64decode(event["args"]["snapshot"]))
        ).convert("RGB")
        pixels = image.load()
        target_rows, box_rows = [], []
        for y in range(image.height):
            for x in range(image.width):
                red, green, blue = pixels[x, y]
                if red - green > 60 and red - blue > 20:
                    target_rows.append(y)
                if green - red > 20 and green - blue > 20 and green > 130:
                    box_rows.append(y)
        readings.append(
            (min(target_rows), min(box_rows)) if target_rows and box_rows else None
        )
    shown = [reading for reading in readings if reading is not None]
    assert len(shown) >= 2 and None in readings, readings
    offset = shown[-1][1] - shown[-1][0]
    assert all(
        abs(box_top - target_top - offset) <= 1 for target_top, box_top in shown
    ), readings
