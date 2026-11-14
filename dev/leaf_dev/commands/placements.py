"""Open a thread card in each configuration of `CASES`, and write a gallery of where
each card stands and how it is shaped.

    uv run leaf-dev placements [--case NAME]... [--base [REF]] [--browser ENGINE]

A case is one configuration a reader meets: the subject the thread is on (words quoted
in a block, or a whole block), the messages the thread holds, the route that opens its
card (`m` from the page's top or with the subject in view, a press on its margin
marker or its words, by a finger in a touch window, or a comment the reader sends),
what follows the opening,
such as the agent's answer arriving or a scroll, and the windows it opens in, the
1728×999, 1440×900 and 1000×700 ones unless it names others. Every case opens on one page,
`fixture()`, whose blocks span the subjects pages hold: a one-line, a three-line and a
sixteen-line paragraph, a heading, a list, a choice widget, and a section holding a
table wider than the column. Add a case for a shape someone meets: a line in `CASES`,
and a block in `fixture()` and `SUBJECTS` if its subject isn't there yet. A quote lies
within one text node of its block.

Each case is visited in each window on each arm through `leaf_dev.visits`, the loop
`leaf-dev probe` runs, so a case reads what Leaf draws on its own: it sets only the
page, the thread's words and the reader's input. `--base` adds the merge base with
`main`, or REF, beside this working tree.

Each run writes, under `.tmp/placements/run-*/`, `index.html`, a Leaf page source of
the gallery, with its captures in `media/` under the names a page's media take
(`leaf page media` adds them to another page under the same names); `gallery.html`,
its sections alone, for a page that shows them among its own with `STYLE`;
`readings.jsonl`, one line per case, window and arm; and each failure's traceback.
Each capture outlines in orange the block Leaf resolves the thread to, which its card
keeps clear of, and fills the quoted words, drawn after the capture so the outline
shows where a card covers them. What the gallery reports beside each capture is
measured in the tab:

- the card's side and size, or the floating panel where the thread opens there;
- how much narrower the card stands than it could, and which limit that is: the width
  its contents take unwrapped, the measure (`cardMeasure`), or its room, which runs
  from the card's inner edge to the far edge of the placement boundary
  (`commentBoundary`) beside its subject, and is the boundary's width above or below;
- how much wider the card stands than its contents take unwrapped;
- the part of its subject's block it covers, and whether it covers the quoted words,
  a fault where card and block would fit in the boundary together, side by side for a
  card beside its subject and one above the other for any other;
- how far the page scrolled from the input that opened the card, except where `m`
  travelled from the page's top.

    uv run leaf-dev preview --source .tmp/placements/run-XXXX/index.html
"""

import html
import json
import traceback
from dataclasses import dataclass
from pathlib import Path

import click
from PIL import Image, ImageDraw
from playwright.sync_api import Page

from leaf.event_log import read_events
from leaf.media import media_name
from leaf.render_checks import wait_until_ready
from leaf_dev import ROOT
from leaf_dev.arms import (
    PageClient,
    base_option,
    choose_arms,
    run_directory,
    served_page,
)
from leaf_dev.browser import (
    WINDOWS,
    Window,
    engine_option,
    launch,
    screenshot,
    scroll_settled,
    settle,
)
from leaf_dev.states import OPEN_CARD, State, open_card
from leaf_dev.visits import said, visits

OUT = ROOT / ".tmp" / "placements"

WIDE = Window((1728, 999), description="a 1728px by 999px window")
MIDDLE = WINDOWS["macbook"]
NARROW = Window((1000, 700), description="a 1000px by 700px window")
PHONE = WINDOWS["phone"]

QUESTION = "Should the old cluster stay warm for a whole week, or would three days do?"
REASONS = (
    "A week covers the slowest batch jobs, which run on Sundays.",
    "Three days would save most of the cost, since the cluster idles after the first.",
    "The risk is a rollback after day three, which the last two migrations never needed.",
    "Keeping it warm means the on-call rotation watches both clusters' alerts.",
    "I'd keep a week for the first region and shorten it once the others follow cleanly.",
    "That also gives the billing team a full cycle of numbers to compare.",
    "Either way, the switch-over date doesn't move.",
)
MEDIUM = " ".join((QUESTION, *REASONS[:3]))
LONG = " ".join((QUESTION, *REASONS, *REASONS))
ANSWER = " ".join(REASONS * 2)
TURNS = (
    QUESTION,
    "Three days, unless something needs the week.",
    " ".join(REASONS[:4]),
    "Then a week for the first region. What about the alerts?",
    " ".join(REASONS[3:]),
    "Fine. Who watches the old cluster's alerts?",
    " ".join(REASONS),
)

# The blocks of `fixture()` a thread can be on, as the gallery names them.
SUBJECTS = {
    "p-medium": "a short paragraph",
    "p-long": "a sixteen-line paragraph",
    "h-steps": "a heading",
    "step-1": "a list item",
    "choice": "a choice widget",
    "wide": "a section holding a table wider than the column",
    "wide-table": "a table wider than the column",
}

# Words each case quotes, each found once on the page.
WARM = "keep the old cluster warm for a week"
FIREWALL = "waits on the firewall change"
STEP = "compare the answers for a day"

# The routes that open a card (`ROUTES`), as the gallery names them.
ROUTE_WORDS = {
    "m": "opened by m from the page's top",
    "m-near": "opened by m with its words already in the window's middle",
    "marker": "opened from its margin marker",
    "tap": "opened by a press on its words",
    "comment": "the reader comments, and Send opens the card",
}


@dataclass(frozen=True)
class Case:
    """One configuration: `subject` is the id of the block the thread is on, `quote`
    the words it quotes there, or None for the whole block. `thread` holds its
    messages before the page opens, the agent's question first and then the reader's
    and the agent's in turn, ending with the agent's; a thread the reader starts by
    `route` "comment" holds none, and opens with `typed`, which `arrives` answers once
    the card is open. `scroll` is the pixels a wheel then scrolls the page."""

    name: str
    title: str
    subject: str
    quote: str | None = None
    thread: tuple[str, ...] = (QUESTION,)
    route: str = "m"
    typed: str = "Why a week?"
    arrives: str | None = None
    scroll: int = 0
    windows: tuple[Window, ...] = (WIDE, MIDDLE, NARROW)

    def __post_init__(self):
        assert self.subject in SUBJECTS, f"{self.name}: add {self.subject} to SUBJECTS"
        assert self.route in ROUTE_WORDS, f"{self.name}: no route {self.route}"
        commented = self.route == "comment"
        assert commented == (not self.thread), (
            f"{self.name}: a thread holds messages unless the reader starts it"
        )
        assert commented or len(self.thread) % 2, (
            f"{self.name}: the agent's message opens and ends a thread"
        )
        assert commented or not self.arrives, (
            f"{self.name}: what arrives answers the reader's comment"
        )
        assert self.route in ("tap", "marker") or not any(
            w.touch for w in self.windows
        ), f"{self.name}: {self.route} takes keys, which a touch window lacks"


CASES = (
    Case("words", "A short question on a few words", "p-medium", WARM),
    Case("words-long", "A long question on a few words", "p-medium", WARM, (LONG,)),
    Case(
        "comment-answered",
        "The reader's short comment, then a long answer arrives",
        "p-medium",
        WARM,
        (),
        route="comment",
        arrives=ANSWER,
    ),
    Case("turns", "A conversation of seven messages", "p-medium", WARM, TURNS),
    Case(
        "paragraph",
        "A long question on a sixteen-line paragraph",
        "p-long",
        None,
        (LONG,),
    ),
    Case(
        "section",
        "A conversation on a section holding a wide table",
        "wide",
        None,
        TURNS,
        route="marker",
    ),
    Case(
        "cell", "A question on words in a table cell", "wide-table", FIREWALL, (MEDIUM,)
    ),
    Case("heading", "A question on a heading", "h-steps", None, (MEDIUM,)),
    Case("list-item", "A question on words in a list item", "step-1", STEP, (MEDIUM,)),
    Case("widget", "A question on a choice widget", "choice", None, (MEDIUM,)),
    Case(
        "words-long-near",
        "A long question on a few words already in view",
        "p-medium",
        WARM,
        (LONG,),
        route="m-near",
        windows=(NARROW,),
    ),
    Case(
        "scrolled",
        "A long question opened by m, then the page scrolled down 300 px",
        "p-medium",
        WARM,
        (LONG,),
        scroll=300,
        windows=(NARROW,),
    ),
    Case(
        "phone",
        "A question on a few words, tapped",
        "p-medium",
        WARM,
        (MEDIUM,),
        route="tap",
        windows=(PHONE,),
    ),
)

NOTE = (
    "The migration plan below is illustrative.",
    "Each region moves on its own schedule.",
    "The dashboards show each step's error budget.",
    "Support hears of each move a day ahead.",
    "Nothing here changes the public API.",
)


def filler(label: str, sentences: int) -> str:
    """A paragraph of `sentences` sentences opened by `label`, which keeps every
    paragraph's words its own."""
    return " ".join([f"{label}:", *(NOTE[i % len(NOTE)] for i in range(sentences))])


def fixture() -> str:
    """The page every case opens: a reading column holding the blocks the cases'
    threads are on, with enough paragraphs around them for any of them to stand
    anywhere in the window."""
    before = "".join(
        f'<p id="before-{n}">{filler(f"Background {n}", 6)}</p>\n' for n in range(1, 7)
    )
    after = "".join(
        f'<p id="after-{n}">{filler(f"Follow-up {n}", 6)}</p>\n' for n in range(1, 11)
    )
    long = " ".join(
        f"In week {n}, region {n} moves its reads first and its writes after a day of"
        " matching answers, and the old cluster takes its traffic back if they differ."
        for n in range(1, 12)
    )
    rows = "".join(
        f'<tr><th scope="row">Region {n}</th><td>{"Moved" if n < 9 else "Waiting"}</td>'
        f"<td>{f'Region {n} {FIREWALL}' if n == 9 else f'Reads and writes on the new cluster since week {n}.'}"
        f" Its batch jobs run on day {n % 7 + 1}, and its on-call shift is team {n % 4 + 1}.</td>"
        f"<td>{n * 3}% of traffic, with an error budget of {n % 5 + 1} minutes a week.</td></tr>\n"
        for n in range(1, 41)
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<title>Placement fixture</title>
<meta name="description" content="The page leaf-dev placements opens thread cards on.">
</head>
<body>
<main class="layout-column">
<h1 id="title">Moving to the new cluster</h1>
{before}<p id="p-short">The rollout starts on Monday.</p>
<p id="p-medium">The migration moves each region's traffic to the new cluster in three
steps. First we mirror reads and compare the answers; then we send a tenth of writes and
watch the error budget; finally we switch the rest over and {WARM}, in case a rollback is
needed.</p>
<p id="p-long">{long}</p>
<h2 id="h-steps">Steps in order</h2>
<ul id="steps">
<li id="step-1">Mirror reads to the new cluster and {STEP}.</li>
<li id="step-2">Send a tenth of writes and watch the error budget.</li>
<li id="step-3">Switch the remaining traffic and keep the old cluster warm.</li>
</ul>
<lf-options id="choice">
<lf-option id="choice-week"><strong>Keep the old cluster for a week</strong> Covers the
Sunday batch jobs.</lf-option>
<lf-option id="choice-days"><strong>Keep it for three days</strong> Saves most of the
cost.</lf-option>
</lf-options>
<section id="wide" class="layout-flow">
<h2>Where each region stands</h2>
<p id="wide-lede">Every region's state, its traffic and its error budget.</p>
<table id="wide-table" data-width="available">
<thead><tr><th scope="col">Region</th><th scope="col">State</th><th scope="col">Notes</th><th scope="col">Traffic</th></tr></thead>
<tbody>
{rows}</tbody>
</table>
</section>
{after}</main>
</body>
</html>
"""


def log_lines(case: Case) -> list[dict]:
    """The agent's question that opens the thread, as `leaf-dev probe --log` takes
    it; `converse` adds the turns after it."""
    if not case.thread:
        return []
    anchor = {"section": case.subject, **({"quote": case.quote} if case.quote else {})}
    return [
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": case.thread[0],
            "anchor": anchor,
            "obligation": True,
        }
    ]


# Where the reader aims: the case's block, and a range over its quoted words.
AIM = """([subject, quote]) => {
  const block = document.getElementById(subject);
  if (!quote) return {block, range: null};
  const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const at = node.data.indexOf(quote);
    if (at < 0) continue;
    const range = document.createRange();
    range.setStart(node, at);
    range.setEnd(node, at + quote.length);
    return {block, range};
  }
  throw new Error(`“${quote}” is in no text node of #${subject}`);
}"""

# What the tab shows once the card has opened, read with Leaf's own modules: the block
# Leaf resolves the thread to and the rectangles of its quoted words, the card, and
# the placement boundary and measure the card stands by.
READ = """async () => {
  const box = (r) => r && {left: Math.round(r.left), top: Math.round(r.top),
    right: Math.round(r.right), bottom: Math.round(r.bottom)};
  const entry = new URL(document.querySelector('script[data-lf-entry]').dataset.lfEntry,
    location.href);
  const runtime = (path) => import(new URL(`runtime/${path}`, entry));
  const [api, anchors, placement] = await Promise.all([runtime('widget-api.js'),
    runtime('anchor-resolution.js'), runtime('annotation-overlay/comment-placement.js')]);
  const [thread] = api.readThreads().threads;
  const target = anchors.resolveAnchor(thread.anchor);
  const quote = (target.segments ?? []).flatMap((segment) => {
    const range = document.createRange();
    range.setStart(segment.node, segment.start);
    range.setEnd(segment.node, segment.end);
    return [...range.getClientRects()].map(box);
  });
  const card = document.querySelector('.lf-margin-preview');
  const panel = document.querySelector('.lf-fp-opened');
  const shown = (node) => node && node.checkVisibility() ? node : null;
  // The card's width with nothing narrowing it: as wide as its words and rows
  // need to stand on one line each.
  const natural = (card) => {
    const style = card.style, saved = [style.width, style.minWidth, style.maxWidth];
    [style.width, style.minWidth, style.maxWidth] = ['max-content', '0px', 'none'];
    const width = card.getBoundingClientRect().width;
    [style.width, style.minWidth, style.maxWidth] = saved;
    return Math.round(width);
  };
  return {
    window: [innerWidth, innerHeight],
    scrollY: Math.round(scrollY),
    measure: placement.cardMeasure(),
    gap: placement.COMMENT_GAP,
    boundary: box(placement.commentBoundary()),
    card: box(shown(card)?.getBoundingClientRect()),
    natural: shown(card) && natural(card),
    side: shown(card)?.getAttribute('data-lf-thread-placement') ?? null,
    panel: box(shown(panel)?.getBoundingClientRect()),
    block: box(target.place.getBoundingClientRect()),
    quote,
  };
}"""


def centre(page: Page, case: Case) -> None:
    """Scroll the case's quoted words, or its block, to the window's middle, or the
    block's top to the window's top where the block is taller than the window."""
    page.evaluate(
        f"""(args) => {{
          const {{block, range}} = ({AIM})(args);
          const r = (range ?? block).getBoundingClientRect();
          scrollBy(0, r.top - Math.max(0, (innerHeight - r.height) / 2));
        }}""",
        [case.subject, case.quote],
    )
    scroll_settled(page)
    settle(page)


# Each route returns the page's scroll just before the input that opens the card,
# which a finger presses in a touch window and a mouse in any other.

# A card the route opened, or on a phone the floating panel's view of its thread.
OPENED = (
    "() => document.querySelector('.lf-margin-preview:not([hidden]), .lf-fp-opened')"
)


def by_walk(page: Page, case: Case, window: Window) -> float:
    page.locator("body").focus()
    before = page.evaluate("scrollY")
    page.keyboard.press("m")
    page.wait_for_function(OPEN_CARD)
    return before


def by_marker(page: Page, case: Case, window: Window) -> float:
    marker = page.locator(f'[data-lf-margin-for="{case.subject}"] .lf-margin-marker')
    if not window.touch:
        return open_card(page, marker)
    marker.scroll_into_view_if_needed()
    settle(page)
    before = page.evaluate("scrollY")
    marker.tap()
    page.wait_for_function(OPENED)
    return before


def by_tap(page: Page, case: Case, window: Window) -> float:
    before = page.evaluate("scrollY")
    first = page.evaluate(
        f"(args) => {{ const {{block, range}} = ({AIM})(args);"
        " return (range ?? block).getClientRects()[0].toJSON(); }",
        [case.subject, case.quote],
    )
    at = (first["left"] + 4, first["top"] + first["height"] / 2)
    if window.touch:
        page.touchscreen.tap(*at)
    else:
        page.mouse.click(*at)
    page.wait_for_function(OPENED)
    return before


def by_comment(page: Page, case: Case, window: Window) -> float:
    page.evaluate(
        f"""(args) => {{
          let {{block, range}} = ({AIM})(args);
          if (!range) range = document.createRange(), range.selectNodeContents(block);
          getSelection().removeAllRanges();
          getSelection().addRange(range);
        }}""",
        [case.subject, case.quote],
    )
    page.keyboard.press("c")
    page.keyboard.insert_text(case.typed)
    before = page.evaluate("scrollY")
    page.keyboard.press("ControlOrMeta+Enter")
    page.wait_for_function(OPEN_CARD)
    return before


ROUTES = {
    "m": by_walk,
    "m-near": by_walk,
    "marker": by_marker,
    "tap": by_tap,
    "comment": by_comment,
}


def answer(words: str, leaves: str) -> None:
    """The agent answers the reader's message as an agent does: from its delivery,
    declaring what the answer leaves (`--done` or `--obligation`)."""
    served = served_page.get()
    delivery = json.loads(served.leaf("wait", str(served.directory), timeout=15).stdout)
    ref = next(
        event["answer"]["ref"]
        for batch in delivery["batches"]
        for event in batch["events"]
        if "answer" in event
    )
    served.leaf("delivery", "ack", delivery["id"])
    served.leaf("thread", "reply", ref, leaves, "--text", words)


def caught_up(page: Page) -> None:
    """Wait until the tab shows the server's reading, and has settled."""
    wait_until_ready(
        page, PageClient(served_page.get().address).state(), through="state"
    )
    settle(page)


def converse(case: Case) -> None:
    """The turns after the agent's question, the reader's from another tab and the
    agent's answers, the last of which waits on the reader, so `m` walks to it."""
    served = served_page.get()
    root = next(
        event["id"]
        for event in read_events(served.directory)
        if event["kind"] == "comment"
    )
    rest = case.thread[1:]
    for n in range(0, len(rest), 2):
        PageClient(served.address).post(
            {
                "kind": "reply",
                "parent": root,
                "attempt": f"placements-turn-{n:03d}",
                "text": rest[n],
            }
        )
        answer(rest[n + 1], "--done" if n + 2 < len(rest) else "--obligation")


# Whether the card's transcript shows the message holding these words.
ANSWER_SHOWN = """(words) => {
  const transcript = document.querySelector('.lf-margin-preview .lf-thread-transcript');
  const message = [...transcript.querySelectorAll('.lf-msg')]
    .find((node) => node.textContent.includes(words));
  if (!message?.checkVisibility()) return false;
  const shown = transcript.getBoundingClientRect(), box = message.getBoundingClientRect();
  return box.top < shown.bottom && box.bottom > shown.top;
}"""


def journey(case: Case, window: Window):
    """The reader's input for `case` in `window`, returning how far the page scrolled
    from the input that opened the card."""

    def run(page: Page) -> dict:
        settle(page)
        if len(case.thread) > 1:
            converse(case)
            caught_up(page)
        if case.route != "m":
            centre(page, case)
        before = ROUTES[case.route](page, case, window)
        settle(page)
        page.mouse.move(0, 0)
        opened = page.evaluate("scrollY")
        if case.arrives:
            answer(case.arrives, "--done")
            caught_up(page)
            # A card holding the answer behind its notice or New reply shows it at
            # the reader's press (held-news.js, thread-card.js).
            words = case.arrives[:40]
            news = page.locator(".lf-margin-preview [data-lf-news] >> visible=true")
            news.or_(
                page.locator(".lf-margin-preview .lf-msg", has_text=words)
            ).first.wait_for()
            if not page.evaluate(ANSWER_SHOWN, words):
                news.first.click()
                page.wait_for_function(ANSWER_SHOWN, arg=words)
                page.mouse.move(0, 0)
            settle(page)
        if case.scroll:
            page.mouse.move(2, window.size[1] / 2)
            page.mouse.wheel(0, case.scroll)
            scroll_settled(page)
            settle(page)
            page.mouse.move(0, 0)
        return {"opening_scrolled": round(opened - before)}

    return run


def overlap(a: dict, b: dict) -> tuple[int, int]:
    width = min(a["right"], b["right"]) - max(a["left"], b["left"])
    height = min(a["bottom"], b["bottom"]) - max(a["top"], b["top"])
    return (max(0, width), max(0, height))


SIDES = {
    "right": "beside its subject, on the right",
    "left": "beside its subject, on the left",
    "above": "above its subject",
    "below": "below its subject",
}


def findings(reading: dict) -> dict:
    """What the gallery says of one capture, from its reading."""
    card, boundary = reading["card"], reading["boundary"]
    if not card:
        return {
            "where": "in the panel" if reading["panel"] else "nowhere: no card opened"
        }
    side = reading["side"]
    width, height = card["right"] - card["left"], card["bottom"] - card["top"]
    limits = {
        "its words need": reading["natural"],
        "the measure": reading["measure"],
        "its room": {
            "right": boundary["right"] - card["left"],
            "left": card["right"] - boundary["left"],
        }.get(side, boundary["right"] - boundary["left"]),
    }
    limit = min(limits, key=lambda name: limits[name])
    window = {
        "left": 0,
        "top": 0,
        "right": reading["window"][0],
        "bottom": reading["window"][1],
    }
    covered = overlap(card, clipped(reading["block"], window))
    block = reading["block"]
    # Whether the card and its block fit in the boundary side by side, for a card
    # beside its subject, or one above the other.
    axis = ("left", "right") if side in ("left", "right") else ("top", "bottom")
    span = {"left": width, "top": height}[axis[0]]
    fits = block[axis[1]] - block[axis[0]] + reading["gap"] + span <= (
        boundary[axis[1]] - boundary[axis[0]]
    )
    return {
        "where": SIDES.get(side, f"at {side}"),
        "size": [width, height],
        "narrower": max(0, round(limits[limit] - width)),
        "limit": limit,
        "wider": max(0, round(width - reading["natural"])),
        "covers": list(covered) if all(covered) else None,
        "covers_quote": any(all(overlap(card, words)) for words in reading["quote"]),
        "fits": fits,
        "outside": overlap(card, window) != (width, height),
    }


def clipped(a: dict, b: dict) -> dict:
    """The part of box `a` inside box `b`."""
    return {
        "left": max(a["left"], b["left"]),
        "top": max(a["top"], b["top"]),
        "right": min(a["right"], b["right"]),
        "bottom": min(a["bottom"], b["bottom"]),
    }


ORANGE = (247, 103, 7)


def outlined(shot: Path, reading: dict) -> bytes:
    """The capture with the subject's block outlined and its quoted words filled."""
    image = Image.open(shot).convert("RGBA")
    layer = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(layer)
    for words in reading["quote"]:
        draw.rectangle(
            [words["left"] - 1, words["top"], words["right"] + 1, words["bottom"]],
            fill=(*ORANGE, 70),
        )
    block = reading["block"]
    draw.rounded_rectangle(
        [block["left"] - 4, block["top"] - 3, block["right"] + 4, block["bottom"] + 3],
        radius=4,
        outline=(*ORANGE, 255),
        width=3,
    )
    out = Path(shot).with_suffix(".outlined.png")
    Image.alpha_composite(image, layer).convert("RGB").save(out)
    return out.read_bytes()


def words(text: str) -> str:
    return f"{len(text.split())} words"


def described(case: Case, window: Window) -> str:
    """The case's configuration in a line, after its title."""
    width, height = window.size
    if len(case.thread) == 1:
        thread = f"the agent's question, {words(case.thread[0])}"
    elif case.thread:
        thread = f"{len(case.thread)} messages, {words(' '.join(case.thread))} in all"
    else:
        thread = f"the reader's comment, {words(case.typed)}"
    steps = [
        f"{width}×{height}{', touch' if window.touch else ''}",
        f"on “{case.quote}” in {SUBJECTS[case.subject]}"
        if case.quote
        else f"on {SUBJECTS[case.subject]}",
        thread,
        ROUTE_WORDS[case.route],
    ]
    if case.arrives:
        steps.append(f"then the agent's answer arrives, {words(case.arrives)}")
    if case.scroll:
        steps.append(f"then the page scrolls {case.scroll} px")
    return " · ".join(steps)


def result(case: Case, found: dict, scrolled: int | None) -> tuple[str, list]:
    """The sentence a tile says of a card, and its flags, each a tone and words."""
    if "size" not in found:
        return f"The thread opens {found['where']}.", []
    width, height = found["size"]
    tags = []
    if found["narrower"] > 2:
        tags.append(("warn", f"{found['narrower']} px narrower than {found['limit']}"))
    if found["wider"] > 2:
        tags.append(("", f"{found['wider']} px wider than its words need"))
    # Covering what it's about is a fault where the card and its block would fit in the
    # window one above the other, and the only way to stand otherwise.
    tone, fitting = (
        ("danger", ", though both fit in the window")
        if found["fits"]
        else ("warn", "; both don't fit in the window")
    )
    if found["covers_quote"]:
        tags.append((tone, f"covers the quoted words{fitting}"))
    elif found["covers"]:
        covered = "covers {} × {} px of its subject".format(*found["covers"])
        tags.append((tone, covered + fitting))
    if found["outside"]:
        tags.append(("danger", "partly outside the window"))
    # `m` from the page's top travels to the thread, as the reader expects.
    if scrolled and case.route != "m":
        tags.append(("", f"page scrolled {abs(scrolled)} px to open it"))
    return f"The card stands {found['where']}, {width} × {height} px.", tags


def tile(case: Case, window: Window, arms: dict[str, dict]) -> str:
    """One figure: the case's capture on each arm, its configuration and result."""
    key = f"{case.name}-{window.size[0]}x{window.size[1]}"
    shots = {arm: got for arm, got in arms.items() if got.get("image")}
    alt = {
        arm: html.escape(f"{case.title}: {got['sentence']}", quote=True)
        for arm, got in shots.items()
    }
    if set(shots) == {"base", "head"}:
        picture = (
            f'<lf-shot id="shot-{key}" before="{shots["base"]["image"]}"'
            f' after="{shots["head"]["image"]}" alt="{alt["head"]}"></lf-shot>'
        )
    else:
        picture = "".join(
            f'<a href="{got["image"]}"><img src="{got["image"]}" alt="{alt[arm]}"></a>'
            for arm, got in shots.items()
        )

    def said_of(got: dict) -> str:
        if not got.get("image"):
            return f"Failed: {html.escape(got['failed'])}"
        chips = "".join(
            f' <small class="tag{" " + tone if tone else ""}">{html.escape(text)}</small>'
            for tone, text in got["tags"]
        )
        return html.escape(got["sentence"]) + chips

    results = "".join(
        f"<br>{arm.capitalize() + ': ' if len(arms) > 1 else ''}{said_of(got)}"
        for arm, got in arms.items()
    )
    return (
        f'<figure id="case-{key}">{picture}\n<figcaption><strong>'
        f"{html.escape(case.title)}</strong> {html.escape(described(case, window))}"
        f"{results}</figcaption></figure>"
    )


# The gallery's tiles, wide enough to show a card's shape in a whole-window capture.
STYLE = """<style>
  .placements {
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 28rem), 1fr));
  }
</style>"""


def gallery(tiles: dict[Window, list[str]]) -> str:
    """The tiles, a section for each window, which a page holding `STYLE` shows."""
    return "\n".join(
        f'<section id="window-{window.size[0]}x{window.size[1]}" class="layout-flow">\n'
        f"<h2>{window.size[0]}×{window.size[1]} window"
        f"{', under a finger' if window.touch else ''}</h2>\n"
        f'<div class="layout-tiles placements" data-width="available">\n'
        + "\n".join(figures)
        + "\n</div>\n</section>"
        for window, figures in tiles.items()
    )


def page(sections: str, arms, engine: str) -> str:
    commits = ", ".join(f"{arm} at {arm_.commit[:9]}" for arm, arm_ in arms.items())
    return f"""<!doctype html>
<html lang="en">
<head>
<title>Thread card placements</title>
<meta name="description" content="Where Leaf stands a thread card, and how it shapes it, in each configuration of leaf-dev placements.">
{STYLE}
</head>
<body>
<main class="layout-column">
<h1 id="title">Thread card placements</h1>
<p id="lede">Each capture is a thread card as Leaf draws it in {engine.capitalize()} ({commits}), with
the block it keeps clear of outlined in orange and its quoted words filled. Regenerate
with <code>uv run leaf-dev placements</code>; add a case to <code>CASES</code> in
<code>dev/leaf_dev/commands/placements.py</code>.</p>
{sections}
</main>
</body>
</html>
"""


@click.command()
@click.option(
    "--case",
    "names",
    multiple=True,
    type=click.Choice([case.name for case in CASES]),
    help="Run only this case, in each of its windows; repeat for more.",
)
@engine_option
@base_option()
def placements(names, engine, base) -> None:
    """Open a thread card in each case of CASES and write a gallery of where it
    stands and how it is shaped (this module's header says what each reports)."""
    runs = [
        (case, window)
        for case in CASES
        if not names or case.name in names
        for window in case.windows
    ]
    out = run_directory(OUT)
    media = out / "media"
    media.mkdir()
    scratch = out / "scratch"
    scratch.mkdir()
    (out / "fixture.html").write_text(fixture())
    tiles: dict[Window, list[str]] = {}
    failed = False
    with launch(engine) as browser:
        arms = choose_arms(base, scratch)
        with (out / "readings.jsonl").open("w") as readings:
            for case, window in runs:
                key = f"{case.name}-{window.size[0]}x{window.size[1]}"
                log = scratch / f"{case.name}.jsonl"
                log.write_text(
                    "".join(json.dumps(line) + "\n" for line in log_lines(case))
                )
                got: dict[str, dict] = {}

                def read(arm, visit, key=key):
                    visit.doing = "read"
                    visit.reading["placement"] = visit.page.evaluate(READ)
                    shot = scratch / f"{key}-{arm}.png"
                    shot.write_bytes(screenshot(visit.page))
                    visit.reading["shot"] = str(shot)

                with visits(
                    browser,
                    arms,
                    State(key, str(out / "fixture.html"), window=window),
                    out / "fixture.html",
                    scratch / key,
                    window=window,
                    scheme="light",
                    motion="no-preference",
                    read=read,
                    log=log,
                    run=journey(case, window),
                ) as each:
                    for arm, visit in each:
                        record: dict = {
                            "case": case.name,
                            "window": list(window.size),
                            "arm": arm,
                            "commit": visit.commit,
                        }
                        if visit.error:
                            failed = True
                            (out / f"{key}-{arm}-error.txt").write_text(
                                "".join(traceback.format_exception(visit.error))
                            )
                            record["failed"] = f"{visit.doing}: {said(visit.error)}"
                            got[arm] = {"failed": record["failed"]}
                        else:
                            reading = visit.reading["placement"]
                            scrolled = (visit.reading.get("result") or {}).get(
                                "opening_scrolled"
                            )
                            found = findings(reading)
                            data = outlined(Path(visit.reading["shot"]), reading)
                            name = media_name(data, ".png")
                            (media / name).write_bytes(data)
                            sentence, tags = result(case, found, scrolled)
                            got[arm] = {
                                "image": f"/media/{name}",
                                "sentence": sentence,
                                "tags": tags,
                            }
                            record |= {
                                "reading": reading,
                                "found": found,
                                "opening_scrolled": scrolled,
                                "image": f"media/{name}",
                            }
                        readings.write(json.dumps(record) + "\n")
                        readings.flush()
                        click.echo(
                            f"{key} {arm}: "
                            + (record.get("failed") or json.dumps(record["found"]))
                        )
                tiles.setdefault(window, []).append(tile(case, window, got))
    sections = gallery(tiles)
    (out / "gallery.html").write_text(sections)
    (out / "index.html").write_text(page(sections, arms, engine))
    click.echo(f"wrote {out / 'index.html'}")
    if failed:
        raise click.ClickException("a case failed; see its line in readings.jsonl")
