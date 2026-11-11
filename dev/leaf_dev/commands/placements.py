"""Open a thread card in each configuration of `CASES`, and write a gallery of where
each card stands and how it is shaped.

    uv run leaf-dev placements [--case NAME]... [--base [REF]] [--browser ENGINE]

A case is one configuration a reader meets: a window, the subject the thread is on
(words quoted in a block, or a whole block), the messages the thread holds, the route
that opens its card (`m` from the page's top or with the subject in view, a press on
its margin marker, a tap on its words, or a comment the reader sends), and what
follows the opening, such as the agent's answer arriving or a scroll. Every case opens
on one page, `fixture()`, whose blocks span the subjects pages hold: a one-line, a
three-line and a sixteen-line paragraph, a heading, a list, a choice widget, and a
section whose table spans the window. Add a case for a shape someone meets: a line in
`CASES`, and a block in `fixture()` and `SUBJECTS` if its subject isn't there yet.

Each case is visited on each arm through `leaf_dev.visits`, the loop `leaf-dev probe`
runs, so a case reads what Leaf draws on its own: the case sets only the page, the
thread's words and the reader's input. `--base` adds the merge base with `main`, or
REF, beside this working tree.

Each run writes, under `.tmp/placements/run-*/`, `index.html`, a Leaf page source of
the gallery, with its captures in `media/` under the names a page's media take
(`leaf page media` adds them to another page under the same names); `gallery.html`,
its sections alone, for a page that shows them among its own with `STYLE`;
`readings.jsonl`, one line per case and arm; and each failure's traceback. Each
capture outlines the subject's block in orange and fills the quoted words, drawn after
the capture so the outline shows where a card covers them. What the gallery reports
beside each capture is measured in the tab:

- the card's side and size, or the floating panel where the thread opens there;
- how much narrower the card stands than it could: the least of the width its
  contents take unwrapped, the measure (`--thread-card`), and its room, which runs
  from the card's inner edge to the far edge of the placement boundary
  (`commentBoundary`) beside its subject, and is the boundary's width over or under it;
- how far it covers its subject's block and whether it covers the quoted words;
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
from leaf_dev.states import OPEN_CARD, State
from leaf_dev.visits import said, visits

OUT = ROOT / ".tmp" / "placements"

WIDE = Window((1728, 999), description="a 1728px by 999px window")
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
    "wide": "a section whose table spans the window",
    "wide-table": "a table that spans the window",
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
    "click": "opened by a tap on its words",
    "comment": "the reader comments, and Send opens the card",
}


@dataclass(frozen=True)
class Case:
    """One configuration: `subject` is the id of the block the thread is on, `quote`
    the words it quotes there, or None for the whole block. `thread` holds its
    messages before the page opens, the agent's question first and then the reader's
    and the agent's in turn; a thread the reader starts by `route` "comment" holds
    none, and opens with `typed`. `arrives` is the agent's message arriving once the
    card is open, and `scroll` the pixels a wheel then scrolls the page."""

    name: str
    title: str
    subject: str
    quote: str | None = None
    thread: tuple[str, ...] = (QUESTION,)
    route: str = "m"
    typed: str = "Why a week?"
    arrives: str | None = None
    scroll: int = 0
    window: Window = WIDE

    def __post_init__(self):
        assert self.route in ROUTE_WORDS, self.route
        assert (self.route == "comment") == (not self.thread), self.name


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
        "A conversation on a section whose table spans the window",
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
        "narrow-words",
        "A short question on a few words",
        "p-medium",
        WARM,
        window=NARROW,
    ),
    Case(
        "narrow-words-long",
        "A long question on a few words",
        "p-medium",
        WARM,
        (LONG,),
        window=NARROW,
    ),
    Case(
        "narrow-words-long-near",
        "A long question on a few words already in view",
        "p-medium",
        WARM,
        (LONG,),
        route="m-near",
        window=NARROW,
    ),
    Case(
        "narrow-comment-answered",
        "The reader's short comment, then a long answer arrives",
        "p-medium",
        WARM,
        (),
        route="comment",
        arrives=ANSWER,
        window=NARROW,
    ),
    Case(
        "narrow-paragraph",
        "A long question on a sixteen-line paragraph",
        "p-long",
        None,
        (LONG,),
        window=NARROW,
    ),
    Case(
        "narrow-scrolled",
        "A long question opened by m, then the page scrolled down 300 px",
        "p-medium",
        WARM,
        (LONG,),
        scroll=300,
        window=NARROW,
    ),
    Case(
        "narrow-section",
        "A conversation on a section whose table spans the window",
        "wide",
        None,
        TURNS,
        route="marker",
        window=NARROW,
    ),
    Case(
        "phone-words",
        "A question on a few words, tapped",
        "p-medium",
        WARM,
        (MEDIUM,),
        route="click",
        window=PHONE,
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


# The subject's block and the client rectangles of its quoted words, in the window.
PASSAGE = """([subject, quote]) => {
  const block = document.getElementById(subject);
  if (!quote) return {block, range: null};
  const nodes = [];
  const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) nodes.push(node);
  const text = nodes.map((node) => node.data).join('').replace(/\\s+/g, ' ');
  const at = (offset) => {
    let seen = 0;
    for (const node of nodes) {
      const squeezed = node.data.replace(/\\s+/g, ' ');
      if (offset <= seen + squeezed.length) return [node, offset - seen];
      seen += squeezed.length;
    }
  };
  const start = text.indexOf(quote);
  const range = document.createRange();
  range.setStart(...at(start));
  range.setEnd(...at(start + quote.length));
  return {block, range};
}"""

READ = f"""async ([subject, quote]) => {{
  const box = (r) => r && {{left: Math.round(r.left), top: Math.round(r.top),
    right: Math.round(r.right), bottom: Math.round(r.bottom)}};
  const {{block, range}} = ({PASSAGE})([subject, quote]);
  const card = document.querySelector('.lf-margin-preview');
  const panel = document.querySelector('.lf-fp-opened');
  const shown = (node) => node && node.checkVisibility() ? node : null;
  // The card's width with nothing narrowing it: as wide as its words and rows
  // need to stand on one line each.
  const natural = (card) => {{
    const style = card.style, saved = [style.width, style.minWidth, style.maxWidth];
    [style.width, style.minWidth, style.maxWidth] = ['max-content', '0px', 'none'];
    const width = card.getBoundingClientRect().width;
    [style.width, style.minWidth, style.maxWidth] = saved;
    return Math.round(width);
  }};
  let boundary = {{left: 8, top: 8, right: innerWidth - 8, bottom: innerHeight - 8}};
  try {{
    const entry = document.querySelector('script[data-lf-entry]').dataset.lfEntry;
    const placement = await import(new URL(
      'runtime/annotation-overlay/comment-placement.js', new URL(entry, location.href)));
    boundary = box(placement.commentBoundary());
  }} catch {{}}
  return {{
    window: [innerWidth, innerHeight],
    scrollY: Math.round(scrollY),
    measure: parseFloat(getComputedStyle(document.documentElement)
      .getPropertyValue('--thread-card')),
    boundary,
    card: box(shown(card)?.getBoundingClientRect()),
    natural: shown(card) && natural(card),
    side: shown(card)?.getAttribute('data-lf-thread-placement') ?? null,
    panel: box(shown(panel)?.getBoundingClientRect()),
    block: box(block.getBoundingClientRect()),
    quote: range ? [...range.getClientRects()].map(box) : [],
  }};
}}"""


def centre(page: Page, case: Case) -> None:
    """Scroll the case's quoted words, or its block, to the window's middle, or the
    block's top to the window's top where the block is taller than the window."""
    page.evaluate(
        f"""(args) => {{
          const {{block, range}} = ({PASSAGE})(args);
          const r = (range ?? block).getBoundingClientRect();
          scrollBy(0, r.top - Math.max(0, (innerHeight - r.height) / 2));
        }}""",
        [case.subject, case.quote],
    )
    scroll_settled(page)
    settle(page)


# Each route returns the page's scroll just before the input that opens the card.


def by_walk(page: Page, case: Case) -> float:
    page.locator("body").focus()
    before = page.evaluate("scrollY")
    page.keyboard.press("m")
    page.wait_for_function(OPEN_CARD)
    return before


def by_marker(page: Page, case: Case) -> float:
    """A press on the margin marker, brought into the window first where the subject's
    middle left it out, as a reader scrolls to it."""
    marker = page.locator(f'[data-lf-margin-for="{case.subject}"] .lf-margin-marker')
    marker.evaluate(
        "m => { const box = m.getBoundingClientRect();"
        " if (box.top < 0 || box.bottom > innerHeight)"
        " scrollBy(0, box.top - innerHeight / 3); }"
    )
    settle(page)
    before = page.evaluate("scrollY")
    marker.click()
    page.wait_for_function(OPEN_CARD)
    return before


def by_tap(page: Page, case: Case) -> float:
    before = page.evaluate("scrollY")
    first = page.evaluate(
        f"(args) => {{ const {{block, range}} = ({PASSAGE})(args);"
        " return (range ?? block).getClientRects()[0].toJSON(); }",
        [case.subject, case.quote],
    )
    page.mouse.click(first["left"] + 4, first["top"] + first["height"] / 2)
    page.wait_for_function(
        "() => document.querySelector('.lf-margin-preview:not([hidden]), .lf-fp-opened')"
    )
    return before


def by_comment(page: Page, case: Case) -> float:
    page.evaluate(
        f"""(args) => {{
          let {{block, range}} = ({PASSAGE})(args);
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
    "click": by_tap,
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


def converse(page: Page, case: Case) -> None:
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
    wait_until_ready(page, PageClient(served.address).state(), through="state")
    settle(page)


def journey(case: Case):
    """The reader's input for `case`, returning how far opening the card scrolled."""

    def run(page: Page) -> dict:
        settle(page)
        served = served_page.get()
        if len(case.thread) > 1:
            converse(page, case)
        if case.route != "m":
            centre(page, case)
        before = ROUTES[case.route](page, case)
        settle(page)
        page.mouse.move(0, 0)
        opened = page.evaluate("scrollY")
        if case.arrives:
            answer(case.arrives, "--done")
            state = PageClient(served.address).state()
            wait_until_ready(page, state, through="state")
            settle(page)
            # A card holding the answer behind its notice shows it at the reader's
            # press (held-news.js).
            news = page.locator(".lf-margin-preview .lf-thread-news")
            if news.is_visible():
                news.click()
                settle(page)
                page.mouse.move(0, 0)
        if case.scroll:
            page.mouse.move(2, case.window.size[1] / 2)
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


def findings(reading: dict) -> dict:
    """What the gallery says of one capture, from its reading."""
    card, boundary = reading["card"], reading["boundary"]
    if not card:
        return {"where": "in the panel" if reading["panel"] else "no card"}
    side = reading["side"]
    room = {
        "right": boundary["right"] - card["left"],
        "left": card["right"] - boundary["left"],
    }.get(side, boundary["right"] - boundary["left"])
    width, height = card["right"] - card["left"], card["bottom"] - card["top"]
    window = {
        "left": 0,
        "top": 0,
        "right": reading["window"][0],
        "bottom": reading["window"][1],
    }
    shown = {
        **reading["block"],
        "top": max(reading["block"]["top"], 0),
        "bottom": min(reading["block"]["bottom"], reading["window"][1]),
    }
    across, covered = overlap(card, shown)
    return {
        "where": {
            "right": "beside its subject, on the right",
            "left": "beside its subject, on the left",
            "above": "over its subject",
            "below": "under its subject",
        }.get(side, f"at {side}"),
        "size": [width, height],
        "narrower": max(
            0, round(min(reading["natural"], reading["measure"], room) - width)
        ),
        "covers": covered if across else 0,
        "covers_quote": any(all(overlap(card, words)) for words in reading["quote"]),
        "outside": overlap(card, window) != (width, height),
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


def words(n: int) -> str:
    return f"{n} words"


def described(case: Case) -> str:
    """The case's configuration in a line, after its title."""
    width, height = case.window.size
    if case.thread:
        counts = [len(m.split()) for m in case.thread]
        thread = (
            f"the agent's question, {words(counts[0])}"
            if len(counts) == 1
            else f"{len(counts)} messages, {words(sum(counts))} in all"
        )
    else:
        thread = f"the reader's comment, {words(len(case.typed.split()))}"
    steps = [
        f"{width}×{height}{', touch' if case.window.touch else ''}",
        f"on “{case.quote}” in {SUBJECTS[case.subject]}"
        if case.quote
        else f"on {SUBJECTS[case.subject]}",
        thread,
        ROUTE_WORDS[case.route],
    ]
    if case.arrives:
        steps.append(
            f"then the agent's answer arrives, {words(len(case.arrives.split()))}"
        )
    if case.scroll:
        steps.append(f"then the page scrolls {case.scroll} px")
    return " · ".join(steps)


def result_html(case: Case, found: dict, scrolled: int | None) -> str:
    if "size" not in found:
        return f"The thread opens {found['where']}."
    width, height = found["size"]
    tags = []
    if found["narrower"] > 2:
        tags.append(("warn", f"{found['narrower']} px narrower than its room"))
    if found["covers_quote"]:
        tags.append(("danger", "covers the quoted words"))
    elif found["covers"]:
        tags.append(("warn", f"covers {found['covers']} px of its subject"))
    if found["outside"]:
        tags.append(("danger", "partly outside the window"))
    # `m` from the page's top travels to the thread, as the reader expects.
    if scrolled and case.route != "m":
        tags.append(("", f"page scrolled {abs(scrolled)} px to open it"))
    chips = "".join(
        f' <small class="tag{" " + tone if tone else ""}">{html.escape(t)}</small>'
        for tone, t in tags
    )
    return f"The card stands {found['where']}, {width} × {height} px.{chips}"


def tile(case: Case, arms: dict[str, dict]) -> str:
    """One figure: the case's capture on each arm, its configuration and result."""
    shots = {arm: got for arm, got in arms.items() if got.get("image")}
    alt = {
        arm: html.escape(f"{case.title}: {got['words']}", quote=True)
        for arm, got in shots.items()
    }
    if set(shots) == {"base", "head"}:
        picture = (
            f'<lf-shot id="shot-{case.name}" before="{shots["base"]["image"]}"'
            f' after="{shots["head"]["image"]}" alt="{alt["head"]}"></lf-shot>'
        )
    else:
        picture = "".join(
            f'<a href="{got["image"]}"><img src="{got["image"]}" alt="{alt[arm]}"></a>'
            for arm, got in shots.items()
        )
    results = "".join(
        f"<br>{arm.capitalize() + ': ' if len(arms) > 1 else ''}"
        + (
            got["result"]
            if got.get("image")
            else f"Failed: {html.escape(got['failed'])}"
        )
        for arm, got in arms.items()
    )
    return (
        f'<figure id="case-{case.name}">{picture}\n<figcaption><strong>'
        f"{html.escape(case.title)}</strong> {html.escape(described(case))}"
        f"{results}</figcaption></figure>"
    )


# The gallery's tiles, wide enough to show a card's shape in a whole-window capture.
STYLE = """<style>
  .placements {
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 28rem), 1fr));
  }
</style>"""


def gallery(cases: list[Case], tiles: dict[str, str]) -> str:
    """The tiles, a section for each window, which a page holding `STYLE` shows."""
    sections = []
    for window in dict.fromkeys(case.window for case in cases):
        width, height = window.size
        figures = "\n".join(tiles[c.name] for c in cases if c.window == window)
        sections.append(
            f'<section id="window-{width}x{height}" class="layout-flow">\n'
            f"<h2>{width}×{height} window{', under a finger' if window.touch else ''}"
            f'</h2>\n<div class="layout-tiles placements" data-width="available">\n'
            f"{figures}\n</div>\n</section>"
        )
    return "\n".join(sections)


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
its subject's block outlined in orange and the quoted words filled. Regenerate with
<code>uv run leaf-dev placements</code>; add a case to <code>CASES</code> in
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
    help="Run only this case; repeat for more.",
)
@engine_option
@base_option()
def placements(names, engine, base) -> None:
    """Open a thread card in each case of CASES and write a gallery of where it
    stands and how it is shaped (this module's header says what each reports)."""
    cases = [case for case in CASES if not names or case.name in names]
    out = run_directory(OUT)
    media = out / "media"
    media.mkdir()
    (out / "fixture.html").write_text(fixture())
    tiles = {}
    failed = False
    with launch(engine) as browser:
        arms = choose_arms(base, out / "scratch")
        with (out / "readings.jsonl").open("w") as readings:
            for case in cases:
                log = out / "scratch" / f"{case.name}.jsonl"
                log.parent.mkdir(exist_ok=True)
                log.write_text(
                    "".join(json.dumps(line) + "\n" for line in log_lines(case))
                )
                got: dict[str, dict] = {}

                def read(arm, visit, case=case):
                    visit.doing = "read"
                    visit.reading["placement"] = visit.page.evaluate(
                        READ, [case.subject, case.quote]
                    )
                    shot = out / "scratch" / f"{case.name}-{arm}.png"
                    shot.write_bytes(screenshot(visit.page))
                    visit.reading["shot"] = str(shot)

                with visits(
                    browser,
                    arms,
                    State(case.name, str(out / "fixture.html"), window=case.window),
                    out / "fixture.html",
                    out / "scratch" / case.name,
                    window=case.window,
                    scheme="light",
                    motion="no-preference",
                    read=read,
                    log=log,
                    run=journey(case),
                ) as each:
                    for arm, visit in each:
                        record: dict = {
                            "case": case.name,
                            "arm": arm,
                            "commit": visit.commit,
                        }
                        if visit.error:
                            failed = True
                            trace = out / f"{case.name}-{arm}-error.txt"
                            trace.write_text(
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
                            result = result_html(case, found, scrolled)
                            got[arm] = {
                                "image": f"/media/{name}",
                                "result": result,
                                "words": html.unescape(
                                    result.split("<small")[0].strip()
                                ),
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
                            f"{case.name} {arm}: "
                            + (record.get("failed") or json.dumps(record["found"]))
                        )
                tiles[case.name] = tile(case, got)
    sections = gallery(cases, tiles)
    (out / "gallery.html").write_text(sections)
    (out / "index.html").write_text(page(sections, arms, engine))
    click.echo(f"wrote {out / 'index.html'}")
    if failed:
        raise click.ClickException("a case failed; see its line in readings.jsonl")
