"""Open a thread card in each configuration of `CASES`, with the comment box before it
where the reader starts the thread, and write a gallery of where each stands and how
it is shaped.

    uv run leaf-dev placement cards [--case NAME]... [--base [REF]] [--browser ENGINE]

A case is one configuration a reader meets: the subject the thread is on (words quoted
in a block, a whole block, or one part of a picture, such as a chart's point), the
messages the thread holds, the route that opens its card (`m` from the page's top or
with the subject in view, a press on its margin marker or its words, by a finger in a
touch window, or a comment the reader sends from the box they open on its words with
`c` or on its whole block with ⌥-click, and may carry by its grip), what follows the
opening, such as the agent's answer arriving or a scroll, the windows it opens in, the
1728×999, 1440×900 and 1000×700 ones unless it names others, and the Layout its page
uses, the reading column unless it names another. Every case opens on
`fixture(layout)`, whose blocks span the subjects pages hold: a one-line, a three-line
and a sixteen-line paragraph, a heading, a list, a block of code wider than the
column, a choice widget, a chart of dots, a section holding a table wider than the
column, and the paragraphs at the page's top and foot. Add a case for a shape someone
meets: a line in `CASES`, and a block in `fixture()` and `SUBJECTS` if its subject
isn't there yet. A quote is the first run of its words in its block's text
(`browser.QUOTE_RANGE`).

A page matters to placement only through its Layout, which sets the room around the
words, so the page's content is the same on every layout and `LAYOUTS` holds each
wrapper. `bare` is a `main` with no Layout, whose words run the window's width and
leave no room beside them. `sidebar` and `workspace` are the
other two page Layouts (`skills/leaf/references/page-layout.md`): a body beside an
`aside`, and a screen filling the window whose body is an `lf-pane` that scrolls on its
own. `layout-tiles` arranges one block's children, not the page, and is left out. Each
non-column layout repeats the `LAYOUT_SHAPES`, the shapes whose placement depends most
on room, in the wide and narrow windows.

Each case is visited in each window on each arm through `leaf_dev.visits`, the loop
`leaf-dev probe` runs, so a case reads what Leaf draws on its own: it sets only the
page, the thread's words and the reader's input. `--base` adds the merge base with
`main`, or REF, beside this working tree.

Where the reader comments, the gallery draws the box as it opens and once their
comment is typed, beside the card Send opens, so a box that opens at another width or
edge than its card shows in its row. The `commented` cases type a first line that
widens the box, and stand it beside its words on either side, under, over and
carried in the 1728 and 1440 windows; the 1000 window leaves no room beside the
column, so there it stands under, over or carried.

Each run writes, under `.tmp/cards/run-*/`, `index.html`, a Leaf page source of
the gallery, with its captures in `media/` under the names a page's media take
(`leaf page media` adds them to another page under the same names); `gallery.html`,
its sections alone, for a page that shows them among its own with `STYLE`;
`readings.jsonl`, one line per case, window and arm; and each failure's traceback.
Each capture outlines in orange what Leaf resolves the thread to and its card keeps
clear of, the block or the picture's part, and fills the quoted words, drawn after the
capture so the outline shows where a card covers them. What the gallery reports beside each capture is
measured in the tab:

- the card's or box's side and size, and the inline edge it stands by, which it
  widens away from (floating.js, `held`), or the floating panel where the thread
  opens there;
- how much narrower it stands than it could, and which limit that is: the width its
  contents take unwrapped, the measure (`cardMeasure`), its room, which runs from
  the edge it stands by to the far edge of the placement boundary
  (`commentBoundary`), or, for a card that declares it stands slim
  (`data-lf-widens`), the least width (`cardMinimum`);
- how much wider it stands than its contents take unwrapped;
- the part of its subject's block it covers, and whether it covers the quoted words,
  a fault where card and block would fit in the boundary together, side by side for a
  card beside its subject and one above the other for any other, unless the reader
  carried it there;
- how far the page scrolled from the input that opened the card, except where `m`
  travelled from the page's top;
- for a card Send opens, a fault where it stands by another edge than its box did, or
  while slim at another width.

    uv run leaf-dev preview --source .tmp/cards/run-XXXX/index.html
"""

import html
import json
import traceback
from dataclasses import dataclass, replace
from pathlib import Path

import click
from playwright.sync_api import Page

from leaf.log.event_log import read_events
from leaf.source.render_checks import SERVED_TIMEOUT_MS, wait_until_ready
from leaf_dev import ROOT, gallery
from leaf_dev.arms import (
    PageClient,
    base_option,
    choose_arms,
    run_directory,
    served_page,
)
from leaf_dev.browser import (
    QUOTE_RANGE,
    WINDOWS,
    Window,
    engine_option,
    launch,
    screenshot,
    scroll_settled,
    settle,
)
from leaf_dev.states import OPEN_THREAD, State, open_card
from leaf_dev.visits import said, visits

OUT = ROOT / ".tmp" / "cards"

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
    "before-1": "the page's first paragraph",
    "p-medium": "a short paragraph",
    "p-long": "a sixteen-line paragraph",
    "h-steps": "a heading",
    "step-1": "a list item",
    "wide-code": "a block of code wider than the column",
    "choice": "a choice widget",
    "moved": "a chart of dots",
    "wide": "a section holding a table wider than the column",
    "wide-table": "a table wider than the column",
    "after-10": "the page's last paragraph",
}

# Words each case quotes, each found once on the page.
WARM = "keep the old cluster warm for a week"
FIREWALL = "waits on the firewall change"
STEP = "compare the answers for a day"
CODE = "keep-warm=7d"
LAST = "Follow-up 10"

# The routes that open a card (`ROUTES`), as the gallery names them.
ROUTE_WORDS = {
    "m": "opened by m from the page's top",
    "m-near": "opened by m with its words already in the window's middle",
    "marker": "opened from its margin marker",
    "tap": "opened by a press on its words",
    "comment": "the reader comments, and Send opens the card",
}


# The Layouts a case's page can use, as the gallery names them.
LAYOUTS = {
    "column": "the reading column",
    "bare": "no Layout",
    "sidebar": "a sidebar beside the body",
    "workspace": "a workspace pane",
}
# The cases each non-column layout repeats.
LAYOUT_SHAPES = ("words", "words-long", "heading")


@dataclass(frozen=True)
class Case:
    """One configuration: `subject` is the id of the block the thread is on, `quote`
    the words it quotes there, or `visual` the part of the picture it is on, as an
    anchor names it, or neither for the whole block. `thread` holds its messages
    before the page opens, the agent's question first and then the reader's
    and the agent's in turn, ending with the agent's; a thread the reader starts by
    `route` "comment" holds none, and opens with `typed`, which `arrives` answers once
    the card is open. `scroll` is the pixels a wheel then scrolls the page,
    `layout` the key in `LAYOUTS` of the Layout its page uses, and `carry` the pixels
    across and down the reader carries the comment box by its grip before typing."""

    name: str
    title: str
    subject: str
    quote: str | None = None
    thread: tuple[str, ...] = (QUESTION,)
    visual: str | None = None
    route: str = "m"
    typed: str = "Why a week?"
    arrives: str | None = None
    scroll: int = 0
    windows: tuple[Window, ...] = (WIDE, MIDDLE, NARROW)
    layout: str = "column"
    carry: tuple[int, int] | None = None

    def __post_init__(self):
        assert self.subject in SUBJECTS, f"{self.name}: add {self.subject} to SUBJECTS"
        assert self.route in ROUTE_WORDS, f"{self.name}: no route {self.route}"
        assert self.layout in LAYOUTS, f"{self.name}: no layout {self.layout}"
        assert not (self.quote and self.visual), f"{self.name}: words or a part"
        assert not self.carry or self.route == "comment", f"{self.name}: no box"
        assert not self.visual or self.route not in ("tap", "comment"), (
            f"{self.name}: {self.route} aims at words or a block, not a part"
        )
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


def commented(name: str, title: str, subject: str, quote: str | None, **rest) -> Case:
    """A thread the reader starts on `quote` in `subject`, or on the whole block, with a
    first line long enough to widen the box."""
    return Case(
        name, title, subject, quote, (), route="comment", typed=QUESTION, **rest
    )


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
    commented("comment-words", "The reader comments on a few words", "p-medium", WARM),
    commented(
        "comment-wide", "The reader comments on words in wide code", "wide-code", CODE
    ),
    # With no room beside it, a box under a block near the page's top, and over words
    # near its foot.
    commented(
        "comment-block",
        "The reader comments on a whole paragraph",
        "before-1",
        None,
        layout="bare",
    ),
    commented(
        "comment-foot",
        "The reader comments on words at the page's foot",
        "after-10",
        LAST,
        layout="bare",
    ),
    commented(
        "comment-carried",
        "The reader carries the box by its grip, then comments",
        "wide-code",
        CODE,
        carry=(-80, -60),
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
        "chart-point",
        "A question on one point of a chart",
        "moved",
        thread=(MEDIUM,),
        visual="point:0;x=3;y=30",
    ),
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

CASES += tuple(
    replace(
        case,
        name=f"{case.name}-{layout}",
        title=f"{case.title}, on {LAYOUTS[layout]}",
        windows=(WIDE, NARROW),
        layout=layout,
    )
    for layout in LAYOUTS
    if layout != "column"
    for case in CASES
    if case.name in LAYOUT_SHAPES
)


def wrapped(layout: str, title: str, blocks: str) -> tuple[str, str]:
    """The classes of the page's `main`, and its body, holding `title` and `blocks`
    as `layout` arranges them."""
    match layout:
        case "column":
            return "layout-column", title + blocks
        case "bare":
            return "", title + blocks
        case "sidebar":
            return (
                "layout-sidebar",
                '<aside id="route"><div class="layout-track">'
                '<lf-toc id="contents"></lf-toc></div></aside>\n'
                f'<article id="document" class="layout-column">{title}{blocks}</article>',
            )
        case "workspace":
            return (
                "layout-workspace",
                f'<header>{title}</header>\n<lf-pane id="notes" label="Notes">'
                f"<div>{blocks}</div></lf-pane>",
            )
    raise ValueError(layout)


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


def fixture(layout: str = "column") -> str:
    """The page every case opens, in `layout` (a key of `LAYOUTS`): the blocks the
    cases' threads are on, with enough paragraphs around them for any of them to stand
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
    classes, body = wrapped(
        layout,
        '<h1 id="title">Moving to the new cluster</h1>\n',
        f"""{before}<p id="p-short">The rollout starts on Monday.</p>
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
<pre id="wide-code" data-width="wide">migrate --regions=all --mirror-reads --compare-for=1d --writes=10% --then=all --{CODE}
rollback --region=9 --to=old-cluster --if=answers-differ --notify=support,on-call</pre>
<lf-group id="choice-q" label="How long should the old cluster stay warm?">
<lf-options id="choice">
<lf-option id="choice-week" label="Keep the old cluster for a week" selected><strong>Keep the old cluster for a week</strong> Covers the
Sunday batch jobs.</lf-option>
<lf-option id="choice-days" label="Keep it for three days"><strong>Keep it for three days</strong> Saves most of the
cost.</lf-option>
</lf-options>
</lf-group>
<section id="wide">
<h2>Where each region stands</h2>
<p id="wide-lede">Every region's state, its traffic and its error budget.</p>
<table id="wide-table" data-width="available">
<thead><tr><th scope="col">Region</th><th scope="col">State</th><th scope="col">Notes</th><th scope="col">Traffic</th></tr></thead>
<tbody>
{rows}</tbody>
</table>
</section>
<lf-chart id="moved" data-height="220"><pre>
{{
  ariaLabel: "Share of traffic on the new cluster by week, rising from 3% to 80%",
  x: {{label: "week"}},
  y: {{label: "% of traffic"}},
  marks: [
    Plot.dot(
      [3, 12, 30, 55, 80].map((share, i) => ({{week: i + 1, share}})),
      {{x: "week", y: "share"}},
    ),
  ],
}}
</pre></lf-chart>
{after}""",
    )
    return gallery.page(
        "Placement fixture",
        "The page leaf-dev placement cards opens thread cards on.",
        body,
        layout=classes,
    )


def log_lines(case: Case) -> list[dict]:
    """The agent's question that opens the thread, as `leaf-dev probe --log` takes
    it; `converse` adds the turns after it."""
    if not case.thread:
        return []
    anchor = {
        "section": case.subject,
        **({"quote": case.quote} if case.quote else {}),
        **({"visual": case.visual} if case.visual else {}),
    }
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
AIM = f"""([subject, quote]) => {{
  const block = document.getElementById(subject);
  if (!quote) return {{block, range: null}};
  const range = ({QUOTE_RANGE})(block, quote);
  if (!range) throw new Error(`“${{quote}}” is not in #${{subject}}`);
  return {{block, range}};
}}"""

# What the tab shows once the surface the selector names, the card or the comment box,
# has opened, read with Leaf's own modules: what Leaf resolves the thread to, the
# element where it names one and else the block, or before Send the block and words the
# reader aimed at, and the rectangles of its quoted words, the surface, and the
# placement boundary and measure the surface stands by.
READ = (
    """async ([selector, aim]) => {
  const box = (r) => r && {left: Math.round(r.left), top: Math.round(r.top),
    right: Math.round(r.right), bottom: Math.round(r.bottom)};
  const script = document.querySelector('script[data-lf-entry]');
  const entry = new URL(script.dataset.lfEntry, location.href);
  const runtime = (path) => import(new URL(`runtime/${path}`, entry));
  const [api, anchors, placement] = await Promise.all([runtime('widget-api.js'),
    runtime('readings/anchor-resolution.js'), runtime('annotations/annotation-overlay/comment-placement.js')]);
  const [thread] = api.readThreads().threads;
  const target = thread && anchors.resolveAnchor(thread.anchor);
  const aimed = target ? null : ("""
    + AIM
    + """)(aim);
  const quote = target ? (target.segments ?? []).flatMap((segment) => {
    const range = document.createRange();
    range.setStart(segment.node, segment.start);
    range.setEnd(segment.node, segment.end);
    return [...range.getClientRects()].map(box);
  }) : [...(aimed.range?.getClientRects() ?? [])].map(box);
  const surface = document.querySelector(selector);
  const panel = document.querySelector('.lf-fp-opened');
  const shown = (node) => node && node.checkVisibility() ? node : null;
  // The surface's width with nothing narrowing it: as wide as its words and rows
  // need to stand on one line each.
  const natural = (surface) => {
    const style = surface.style, saved = [style.width, style.minWidth, style.maxWidth];
    [style.width, style.minWidth, style.maxWidth] = ['max-content', '0px', 'none'];
    const width = surface.getBoundingClientRect().width;
    [style.width, style.minWidth, style.maxWidth] = saved;
    return Math.round(width);
  };
  return {
    window: [innerWidth, innerHeight],
    scrollY: Math.round(scrollY),
    measure: placement.cardMeasure(),
    gap: placement.COMMENT_GAP,
    boundary: box(placement.commentBoundary()),
    surface: box(shown(surface)?.getBoundingClientRect()),
    natural: shown(surface) && natural(surface),
    // A card at the width it starts at, the least width or the box's Send opened it
    // from, declares it (`data-lf-widens`) until a message it shows stands tall enough
    // to widen it.
    least: shown(surface)?.hasAttribute('data-lf-widens') ? placement.cardMinimum() : null,
    // The card's side, or the side in the box's placement (`right-start`).
    side: shown(surface) && (surface.getAttribute('data-lf-thread-placement') ??
      {right: 'right', left: 'left', bottom: 'below', top: 'above'}[
        surface.getAttribute('data-lf-placement')?.split('-')[0]] ?? null),
    // The inline edge the surface stands by, which it widens away from (floating.js,
    // `held`).
    held: shown(surface) && (script.lfFloatingSelections()
      .find((selection) => selection.floating === surface)?.edges.left ?? null),
    panel: box(shown(panel)?.getBoundingClientRect()),
    block: box((target ? target.element ?? target.place : aimed.block)
      .getBoundingClientRect()),
    quote,
  };
}"""
)


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
# which a finger presses in a touch window and a mouse in any other, once the card, or
# on a phone the floating panel's view of its thread, has opened (`OPEN_THREAD`). A
# route that opens the comment box first adds to `boxes` its reading and capture at
# each stage.


def by_walk(page: Page, case: Case, window: Window, boxes: list) -> float:
    page.locator("body").focus()
    before = page.evaluate("scrollY")
    page.keyboard.press("m")
    page.wait_for_function(OPEN_THREAD)
    return before


def by_marker(page: Page, case: Case, window: Window, boxes: list) -> float:
    marker = page.locator(f'[data-lf-margin-for="{case.subject}"] .lf-margin-marker')
    if not window.touch:
        return open_card(page, marker)
    marker.scroll_into_view_if_needed()
    settle(page)
    before = page.evaluate("scrollY")
    marker.tap()
    page.wait_for_function(OPEN_THREAD)
    return before


def by_tap(page: Page, case: Case, window: Window, boxes: list) -> float:
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
    page.wait_for_function(OPEN_THREAD)
    return before


def by_comment(page: Page, case: Case, window: Window, boxes: list) -> float:
    """The reader selects the quoted words and presses `c`, or ⌥-clicks the whole
    block, carries the box by its grip where the case says, and types."""
    aim = [case.subject, case.quote]
    if case.quote:
        page.evaluate(
            f"""(args) => {{
              getSelection().removeAllRanges();
              getSelection().addRange(({AIM})(args).range);
            }}""",
            aim,
        )
        page.keyboard.press("c")
    else:
        page.locator(f"#{case.subject}").click(
            modifiers=["Alt"], position={"x": 40, "y": 8}
        )
    page.locator(".lf-fab-bar[data-lf-placement]").wait_for()
    if case.carry:
        grip = page.locator(".lf-fab-bar > .lf-surface-grip").bounding_box()
        assert grip is not None
        x, y = grip["x"] + grip["width"] / 2, grip["y"] + 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + case.carry[0], y + case.carry[1], steps=8)
        page.mouse.up()
    for stage, typed in (("opened", ""), ("typed", case.typed)):
        page.keyboard.insert_text(typed)
        page.mouse.move(0, 0)
        settle(page)
        reading = page.evaluate(READ, [".lf-fab-bar", aim])
        boxes.append({"stage": stage, "reading": reading, "image": screenshot(page)})
    before = page.evaluate("scrollY")
    page.keyboard.press("ControlOrMeta+Enter")
    page.wait_for_function(OPEN_THREAD)
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
    delivery = json.loads(
        served.leaf(
            "wait", str(served.directory), timeout=SERVED_TIMEOUT_MS / 1000
        ).stdout
    )
    ref = next(
        event["answer"]["ref"]
        for batch in delivery["batches"]
        for event in batch["events"]
        if "answer" in event
    )
    served.leaf("delivery", "ack", delivery["id"])
    served.leaf(
        "thread", "reply", "--title", "Card placement", ref, leaves, "--text", words
    )


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
    from the input that opened the card, and the comment box at each stage before."""

    def run(page: Page) -> dict:
        settle(page)
        if len(case.thread) > 1:
            converse(case)
            caught_up(page)
        if case.route != "m":
            centre(page, case)
        boxes: list[dict] = []
        before = ROUTES[case.route](page, case, window, boxes)
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
        return {"opening_scrolled": round(opened - before), "boxes": boxes}

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
    card, boundary = reading["surface"], reading["boundary"]
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
            "left": boundary["right"] - card["left"],
            "right": card["right"] - boundary["left"],
        }.get(reading["held"], boundary["right"] - boundary["left"]),
    }
    if reading["least"]:
        limits["the least width, until a message stands tall"] = reading["least"]
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
        "held": reading["held"],
        "widens": reading["least"] is not None,
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
    out = Path(shot).with_suffix(".outlined.png")
    gallery.marked(
        shot, ORANGE, outlined=[reading["block"]], filled=reading["quote"]
    ).save(out)
    return out.read_bytes()


def drawn(
    media: Path,
    case: Case,
    reading: dict,
    shot: Path,
    scrolled: int | None,
    what: str,
    box: dict | None = None,
) -> tuple[dict, dict]:
    """What a tile shows of one capture, its image written into `media`, and the
    capture's findings."""
    found = findings(reading)
    box = box if box and "size" in box else None
    sentence, tags = result(case, found, scrolled, what, box)
    image = gallery.media(media, outlined(shot, reading))
    return {"image": image, "sentence": sentence, "tags": tags}, found


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
        *([LAYOUTS[case.layout]] if case.layout != "column" else []),
        f"on “{case.quote}” in {SUBJECTS[case.subject]}"
        if case.quote
        else f"on {case.visual} of {SUBJECTS[case.subject]}"
        if case.visual
        else f"on {SUBJECTS[case.subject]}",
        thread,
        ROUTE_WORDS[case.route],
    ]
    if case.carry:
        (x, y), sideways = case.carry, "left" if case.carry[0] < 0 else "right"
        carried = f"{abs(x)} px {sideways} and {abs(y)} px {'up' if y < 0 else 'down'}"
        steps.insert(-1, f"the box carried {carried} by its grip")
    if case.arrives:
        steps.append(f"then the agent's answer arrives, {words(case.arrives)}")
    if case.scroll:
        steps.append(f"then the page scrolls {case.scroll} px")
    return " · ".join(steps)


def result(
    case: Case, found: dict, scrolled: int | None, what: str, box: dict | None = None
) -> tuple[str, list]:
    """The sentence a tile says of `what`, the card or the comment box, and its flags,
    each a tone and words; for a card Send opened, whether it starts as the `box` it
    opened from stood when sent."""
    if "size" not in found:
        return f"The thread opens {found['where']}.", []
    width, height = found["size"]
    tags = []
    if found["narrower"] > 2:
        tags.append(("warn", f"{found['narrower']} px narrower than {found['limit']}"))
    if found["wider"] > 2:
        tags.append(("", f"{found['wider']} px wider than its words need"))
    # Covering what it's about is a fault where the card and its block would fit in the
    # window one above the other, and the only way to stand otherwise. A surface the
    # reader carried stands where they dropped it, so what it covers is their choice.
    tone, fitting = (
        ("", "")
        if case.carry
        else ("danger", ", though both fit in the window")
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
    if box and box["held"] != found["held"]:
        tags.append(("danger", f"the box was held by its {box['held']} edge"))
    grown = width - box["size"][0] if box else 0
    if found["widens"] and abs(grown) > 2:
        than = "wider" if grown > 0 else "narrower"
        tags.append(("danger", f"{abs(grown)} px {than} than the box"))
    held = f", held by its {found['held']} edge" if found["held"] else ""
    return f"The {what} stands {found['where']}, {width} × {height} px{held}.", tags


# What each of a case's tiles shows, in order: for a thread the reader starts, the
# comment box as it opens and once its comment is typed, then the card Send opens.
STAGES = {
    "opened": "the comment box as it opens",
    "typed": "the comment box once its comment is typed",
    "card": "the card Send opens",
}


def tile(case: Case, window: Window, arms: dict[str, dict], stage: str) -> str:
    """One figure: the case's capture at `stage` on each arm, its configuration and
    result."""
    key = f"{case.name}-{window.size[0]}x{window.size[1]}"
    key += "" if stage == "card" else f"-{stage}"
    title = case.title + (f": {STAGES[stage]}" if case.route == "comment" else "")
    shots = {arm: got for arm, got in arms.items() if got.get("image")}
    alt = {arm: f"{title}: {got['sentence']}" for arm, got in shots.items()}
    shown = "head" if "head" in shots else next(iter(shots), None)
    picture = (
        ""
        if shown is None
        else gallery.shot(
            f"shot-{key}",
            alt[shown],
            shots["base"]["image"] if shown == "head" and "base" in shots else None,
            shots[shown]["image"],
        )
    )

    def said_of(got: dict) -> str:
        if not got.get("image"):
            return f"Failed: {html.escape(got['failed'])}"
        chips = "".join(
            f' <small class="lf-tag{" " + tone if tone else ""}">{html.escape(text)}</small>'
            for tone, text in got["tags"]
        )
        return html.escape(got["sentence"]) + chips

    results = "".join(
        f"<br>{arm.capitalize() + ': ' if len(arms) > 1 else ''}{said_of(got)}"
        for arm, got in arms.items()
    )
    return (
        f'<figure id="case-{key}">{picture}\n<figcaption><strong>'
        f"{html.escape(title)}</strong> {html.escape(described(case, window))}"
        f"{results}</figcaption></figure>"
    )


# The gallery's tiles, wide enough to show a card's shape in a whole-window capture.
STYLE = """<style>
  .placements {
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 28rem), 1fr));
  }
</style>"""


def window_sections(tiles: dict[Window, list[str]]) -> str:
    """The tiles, a section for each window, which a page holding `STYLE` shows."""
    return "\n".join(
        f'<section id="window-{window.size[0]}x{window.size[1]}">\n'
        f"<h2>{window.size[0]}×{window.size[1]} window"
        f"{', under a finger' if window.touch else ''}</h2>\n"
        f'<div class="layout-tiles placements" data-width="available">\n'
        + "\n".join(figures)
        + "\n</div>\n</section>"
        for window, figures in tiles.items()
    )


def page(sections: str, arms, engine: str) -> str:
    commits = ", ".join(f"{arm} at {arm_.commit[:9]}" for arm, arm_ in arms.items())
    return gallery.page(
        "Thread card placements",
        "Where Leaf stands a thread card, and how it shapes it, in each configuration "
        "of leaf-dev placement cards.",
        f"""<h1 id="title">Thread card placements</h1>
<p id="lede">Each capture is a thread card as Leaf draws it in {engine.capitalize()} ({commits}), with
the block it keeps clear of outlined in orange and its quoted words filled. Regenerate
with <code>uv run leaf-dev placement cards</code>; add a case to <code>CASES</code> in
<code>dev/leaf_dev/commands/placement/cards.py</code>.</p>
{sections}""",
        head=STYLE,
    )


@click.command("cards")
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
    for layout in {case.layout for case, _ in runs}:
        (out / f"fixture-{layout}.html").write_text(fixture(layout))
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
                got: dict[str, dict[str, dict]] = {stage: {} for stage in STAGES}

                def read(arm, visit, key=key, case=case):
                    visit.doing = "read"
                    visit.reading["placement"] = visit.page.evaluate(
                        READ, [".lf-margin-preview", [case.subject, case.quote]]
                    )
                    shot = scratch / f"{key}-{arm}.png"
                    shot.write_bytes(screenshot(visit.page))
                    visit.reading["shot"] = str(shot)

                with visits(
                    browser,
                    arms,
                    State(key, str(out / f"fixture-{case.layout}.html"), window=window),
                    out / f"fixture-{case.layout}.html",
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
                            got["card"][arm] = {"failed": record["failed"]}
                        else:
                            ran = visit.reading.get("result") or {}
                            box = None
                            for boxed in ran.get("boxes", []):
                                stage = boxed["stage"]
                                shot = scratch / f"{key}-{arm}-{stage}.png"
                                shot.write_bytes(boxed["image"])
                                got[stage][arm], box = drawn(
                                    media, case, boxed["reading"], shot, None, "box"
                                )
                                image = got[stage][arm]["image"].lstrip("/")
                                record.setdefault("boxes", []).append(
                                    {"stage": stage, "reading": boxed["reading"]}
                                    | {"found": box, "image": image}
                                )
                                click.echo(f"{key} {arm} {stage}: {json.dumps(box)}")
                            reading = visit.reading["placement"]
                            scrolled = ran.get("opening_scrolled")
                            got["card"][arm], found = drawn(
                                media,
                                case,
                                reading,
                                Path(visit.reading["shot"]),
                                scrolled,
                                "card",
                                box,
                            )
                            record |= {
                                "reading": reading,
                                "found": found,
                                "opening_scrolled": scrolled,
                                "image": got["card"][arm]["image"].lstrip("/"),
                            }
                        readings.write(json.dumps(record) + "\n")
                        readings.flush()
                        click.echo(
                            f"{key} {arm}: "
                            + (record.get("failed") or json.dumps(record["found"]))
                        )
                tiles.setdefault(window, []).extend(
                    tile(case, window, got[stage], stage)
                    for stage in STAGES
                    if got[stage]
                )
    sections = window_sections(tiles)
    (out / "gallery.html").write_text(sections)
    (out / "index.html").write_text(page(sections, arms, engine))
    click.echo(f"wrote {out / 'index.html'}")
    if failed:
        raise click.ClickException("a case failed; see its line in readings.jsonl")
