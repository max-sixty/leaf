"""The page holds still under the user's aim (browser/AGENTS.md): wherever the user is,
a change they didn't make leaves what they are reading, pointing at or typing into
where it stood.

The cases are generated from two lists, `PLACES` (where the user is, and the box that
marks it) and `CHANGES` (what arrives), crossed wherever the change can reach the
place: a place names what stands around it (`Place.around`) and a change acts on one
of those (`Change.on`). Each case, in Chromium and in Firefox, puts the user there,
takes where the box stands, makes the change, waits for the page to show it and
settle, and reads the box again. Between those readings it reads the box after every
frame renders, so a move the page paints and then takes back fails too, and so does a
frame without the box.

Where the user's own act or the change's own result moves the place, its descriptor
says how, and frames are held to that alone: the user's own scroll keeps the place on
its path to the scroll's goal (`Place.travel`), a new thread drawn at once above it
moves it by what the thread adds (what `Change.make` returns), and the dial's glide
is passed over until it ends (`turn`). A case marked as failing expects only `Moved`,
the verdict on where the place stood: one the runtime gets wrong (`MOVES_ON_MAIN`), or
one where a rule the user chose moves the place (`MOVES_BY_CHOICE`), so the choices
that bound the guarantee are listed beside the cases that hold it. The places include
a thread's two boxes over the page, its margin card and the floating panel's view of
it (`floating_places`). Each case records what it measured (`moved`,
`painted` and the rest) as JUnit properties, so a run's `--junitxml` holds the whole
matrix.

The shift watch is off here: these cases measure the guarantee it watches directly, and
a case marked as failing would otherwise fail its teardown a second time."""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from browser.threads import append_agent_reply
from click.testing import CliRunner
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import live_url, panel_comment
from render_harness import (
    holding,
    leaf_page,
    open_page,
    panel_settled,
    resized,
    scroll_settled,
    stamp_page,
    told,
    wait_for_revision,
)

from leaf import cli as cli_model
from leaf import data as data_model
from leaf.render_checks import rendered
from leaf_dev.browser import go_to_threads, settle
from leaf_dev.example_data import named_source

pytestmark = pytest.mark.shifts_unsurveyed

# How far a box may stand from where it stood: sub-pixel layout rounding.
TOLERANCE = 1

WORDS = (
    "This message has enough words in it to wrap onto a second line at a normal "
    "reading width, so a thread of several stands taller than a short window. "
)


def leaf(*args):
    """Run a `leaf` command as the agent does, and return the records it printed."""
    made = CliRunner().invoke(cli_model.cli, [str(arg) for arg in args])
    assert made.exit_code == 0, made.output
    return [json.loads(line) for line in made.output.splitlines() if line.strip()]


def paragraphs(start, count, prefix="p"):
    """Paragraphs of two lines each, with ids `prefix-n`."""
    return "".join(
        f'<p id="{prefix}-{n}">Paragraph {n}, long enough to occupy a line of reading '
        "in the column, and then a little more so that it wraps onto a second.</p>"
        for n in range(start, start + count)
    )


# ---------------------------------------------------------------------------------
# Pages. Each builds its fixture on a fresh page directory and returns what the places
# and changes on it name.


@dataclass
class Built:
    """A served page, its source, the ids its places and changes act on, and what a
    change notes about where it acted, which the case records."""

    url: str
    page_dir: Path
    source: str
    ids: dict = field(default_factory=dict)
    revision: int = 1
    notes: dict = field(default_factory=dict)


THREAD_PAGE = leaf_page(
    "Holding still",
    '<h1 id="title">Holding still</h1>'
    + paragraphs(0, 30)
    + '<lf-test-plan id="hub" label="Before the frost">'
    '<lf-test-task id="upper" status="active" talk><strong>Which visit first?</strong>'
    " The mounts came down in January.</lf-test-task>"
    '<lf-test-task id="fresh" status="planned" talk><strong>Which tools to bring?'
    "</strong> The shed is locked.</lf-test-task>"
    '<lf-test-task id="jobs" status="active" talk><strong>Which jobs are worth '
    "starting?</strong> The beds need turning.</lf-test-task></lf-test-plan>"
    + paragraphs(30, 30)
    + '<lf-test-plan id="later" label="After the frost">'
    '<lf-test-task id="notes" status="active" talk><strong>What did we learn?'
    "</strong> The frost came early.</lf-test-task></lf-test-plan>"
    + paragraphs(60, 30)
    + '<lf-test-plan id="last" label="In the spring">'
    '<lf-test-task id="long" status="active" talk><strong>What changed?</strong>'
    " The lines below.</lf-test-task></lf-test-plan>",
)


# A paragraph of `count` lines from `first`, each ending in a hard break.
def line_list(first=0, count=80, word="Line"):
    return "  \n".join(
        f"{word} {n}: words that keep their place as the message changes around them."
        for n in range(first, first + count)
    )


LINES = line_list()


def thread_page(serve):
    """Two plans of seats between screens of paragraphs. In the first, `upper` holds a
    thread of one message, `fresh` none, and `jobs` a short thread the user works in,
    whose agent messages `early` and `linked` stand among the user's; in the second,
    `notes` holds a long one whose agent message `read` (a short paragraph, then a long
    one) stands a screen above its reply box. A third, after the page's paragraphs, holds
    `long`, whose agent message `lines` is one paragraph of eighty lines, each its own
    words between line breaks. A user's comment on paragraph 31 puts a pin in the
    margin."""
    url = serve(THREAD_PAGE, anchored=[("p-31", "Paragraph 31")])
    d = serve.page_dir
    upper = panel_comment(d, "Mounts or beds first?", {"section": "upper"}, "agent")
    jobs = panel_comment(d, "Which jobs first?", {"section": "jobs"}, "agent")
    notes = panel_comment(d, "What did we learn?", {"section": "notes"}, "agent")

    def user(thread, text):
        append_carried_log_record(
            d, {"kind": "reply", "author": "user", "parent": thread, "text": text}
        )

    user(jobs, "The beds, I think.")
    early = append_agent_reply(d, jobs, "The beds first, then. " + WORDS)["id"]
    user(jobs, "And the mounts?")
    linked = append_agent_reply(
        d, jobs, "See [the mounts](#p-5) before you start. " + WORDS
    )["id"]
    user(jobs, "Fine, and after that?")
    user(notes, "That the beds drain slowly.")
    read = append_agent_reply(
        d, notes, "A short first paragraph.\n\nThe paragraph being read. " + WORDS * 2
    )["id"]
    for n in range(4):
        user(notes, f"And then {n}?")
        append_agent_reply(d, notes, f"Then step {n}. " + WORDS)
    long = panel_comment(d, "What changed?", {"section": "long"}, "agent")
    user(long, "Show me the lines.")
    lines = append_agent_reply(d, long, LINES)["id"]
    ids = {"upper": upper, "jobs": jobs, "notes": notes, "long": long}
    ids |= {"early": early, "linked": linked, "read": read, "lines": lines}
    return Built(live_url(url), d, THREAD_PAGE, ids)


MAP_PAGE = leaf_page(
    "Page Map",
    "".join(f'<p id="place-{n}">Target {n} of the plan.</p>' for n in range(30)),
)


def map_page(serve):
    """Thirty paragraphs, each with the agent's question but the fifteenth, so Page Map
    lists a row for each of those."""
    url = serve(MAP_PAGE)
    for n in range(30):
        if n != 14:
            panel_comment(
                serve.page_dir, f"Question {n:02d}?", {"section": f"place-{n}"}, "agent"
            )
    return Built(live_url(url), serve.page_dir, MAP_PAGE)


def diff_rows(deleted):
    """A file of twenty context lines and sixty added, `deleted` lines removed after
    the nineteenth."""
    rows = [(" " if n <= 20 else "+") + f"row {n}\n" for n in range(1, 81)]
    rows[19:19] = [f"-removed {n}\n" for n in range(deleted)]
    return (
        "diff --git a/review.py b/review.py\n--- a/review.py\n+++ b/review.py\n"
        f"@@ -1,{20 + deleted} +1,80 @@\n" + "".join(rows)
    )


DIFF_PAGE = leaf_page(
    "A diff",
    '<h1 id="title">Review</h1>'
    + paragraphs(0, 6)
    + '<lf-diff id="patch" source="review-patch"></lf-diff>'
    + paragraphs(6, 10)
    + '<details id="context"><summary>Show context</summary>'
    '<div style="height: 140px">Context the reader opens.</div></details>'
    + paragraphs(16, 20)
    + '<textarea id="note" aria-label="Note"></textarea>',
)


def diff_page(serve):
    url = serve(DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", diff_rows(0))
    return Built(live_url(url), serve.page_dir, DIFF_PAGE)


def dial_page(serve, repeat=1):
    """The detail example's incident report, with the words of the cause's first
    paragraph, `repeat` times over, in an `em`, inline text the dial's Skim folds behind
    the section's gist."""
    source = named_source("detail").read_text()
    start = source.index('<p id="detail-cause-1">') + len('<p id="detail-cause-1">')
    end = source.index("</p>", start)
    words = " ".join([source[start:end]] * repeat)
    source = f"{source[:start]}<em>{words}</em>{source[end:]}"
    return Built(serve(source), serve.page_dir, source)


def tall_dial_page(serve):
    """The dial's page with the cause's first paragraph taller than the window."""
    return dial_page(serve, 12)


PANE_PAGE = leaf_page(
    "Panes",
    '<header><h1>Reading workspace</h1></header><div id="split">'
    '<lf-pane id="left" label="Left reading"><div id="left-body">'
    + paragraphs(0, 60, "q")
    + '</div></lf-pane><lf-pane id="right" label="Right reading"><div>'
    + paragraphs(0, 60, "r")
    + "</div></lf-pane></div>",
    head="<style>#split { display: grid; grid-template-columns: 1fr 1fr; }</style>",
    layout="workspace",
)


def pane_page(serve):
    """Two panes side by side in a workspace, each a scroller of sixty paragraphs."""
    return Built(live_url(serve(PANE_PAGE)), serve.page_dir, PANE_PAGE)


ASKS = 14
QUEUE_PAGE = leaf_page(
    "Asks",
    "".join(
        f'<section id="ask-{n}"><h2>Part {n}</h2>{paragraphs(n * 3, 3)}</section>'
        for n in range(ASKS + 1)
    ),
)


def queue_page(serve):
    """Fourteen asks the agent waits on the user for, one on each part but the first."""
    url = serve(QUEUE_PAGE)
    for n in range(1, ASKS + 1):
        panel_comment(
            serve.page_dir,
            f"Ask {n}: which way should part {n} go?",
            {"section": f"ask-{n}"},
            "agent",
            obligation=True,
        )
    return Built(live_url(url), serve.page_dir, QUEUE_PAGE)


DECISIONS_PAGE = leaf_page(
    "Decisions",
    '<section id="ask-0"><h2>Part 0</h2>'
    + paragraphs(0, 3)
    + "</section>"
    + "".join(
        f'<section id="ask-{n}"><h2>Part {n}</h2>{paragraphs(n * 3, 2)}'
        f'<lf-ask id="decide-{n}"><h3>Ask {n}: which way should part {n} go?</h3>'
        f'<lf-options id="ways-{n}" choose><lf-option id="north-{n}">North</lf-option>'
        f'<lf-option id="south-{n}">South</lf-option></lf-options></lf-ask></section>'
        for n in range(1, ASKS + 1)
    ),
)


def decisions_page(serve):
    """Fourteen decisions the page itself asks, one on each part but the first, so On
    Me's cards hold widgets' questions and no message for Leaf's reader to draw."""
    return Built(live_url(serve(DECISIONS_PAGE)), serve.page_dir, DECISIONS_PAGE)


FLOATING_PAGE = leaf_page(
    "Floating", '<h1 id="title">Floating</h1>' + paragraphs(0, 90)
)


def floating_page(serve):
    """Ninety paragraphs, with two threads on words of the page, which the margin shows
    as rows and opens as cards: `told`, where the agent spoke last, so its next message
    is news, and `asked`, where the user did, so its next message is the answer they
    wait for."""
    url = serve(FLOATING_PAGE)
    d = serve.page_dir

    def turn(thread, author, text):
        event = {"kind": "reply", "author": author, "parent": thread, "text": text}
        if author == "agent":
            return append_agent_reply(d, thread, text)["id"]
        return append_carried_log_record(d, event)["id"]

    told = panel_comment(d, "Does paragraph 20 hold?", {"section": "p-20"}, "agent")
    turn(told, "user", "It does, I think.")
    turn(told, "agent", "Good. " + WORDS)
    asked = panel_comment(d, "Does paragraph 22 hold?", {"section": "p-22"}, "agent")
    turn(asked, "agent", "It may. " + WORDS)
    turn(asked, "user", "Which part of it?")
    return Built(live_url(url), d, FLOATING_PAGE, {"told": told, "asked": asked})


PAGES = {
    "thread": thread_page,
    "map": map_page,
    "diff": diff_page,
    "dial": dial_page,
    "tall-dial": tall_dial_page,
    "pane": pane_page,
    "queue": queue_page,
    "decisions": decisions_page,
    "floating": floating_page,
}

# ---------------------------------------------------------------------------------
# Where the user is.


@dataclass(frozen=True)
class Place:
    """Where the user is: the page it stands on, how a user gets there (`put`), the box
    that marks it, as a page function that finds it afresh at each reading (`box`), and
    what stands around it that a change can grow (`around`, a role to its target).

    `during` is the user's own act, a scroll, made as the change arrives: a driver
    call, or a page statement the page runs in the task that starts watching the
    scroll, so a glide can't end in the round trip between them. `travel` is how far
    it moves the box. A scroll that glides is `midway`: the change draws while
    it is still under way, where the engine lets the case hand it over then (`midway`
    in `arriving`)."""

    name: str
    page: str
    put: Callable
    box: "Found | str"
    around: dict
    travel: float = 0
    during: Callable | str | None = None
    midway: bool = False


def ids_in(selector, built):
    """`selector` with each `$key` replaced by the id the page was built with."""
    for key, value in built.ids.items():
        selector = selector.replace(f"${key}", value)
    return selector


@dataclass(frozen=True)
class Found:
    """The first element matching `selector` and holding `text`, through open shadow
    roots; `$key` in the selector names an id the page was built with."""

    selector: str
    text: str | None = None

    def js(self, built):
        selector = ids_in(self.selector, built)
        return f"""() => {{
          const holds = (n) => {json.dumps(self.text)} === null
            || n.textContent.includes({json.dumps(self.text)});
          const find = (root) => [...root.querySelectorAll({json.dumps(selector)})]
              .find(holds)
            ?? [...root.querySelectorAll('*')]
              .map(n => n.shadowRoot && find(n.shadowRoot)).find(Boolean) ?? null;
          return find(document);
        }}"""


def thread_of(built, key):
    return f'.lf-page-thread[data-lf-thread="{built.ids[key]}"]'


def message(built, key):
    return f'.lf-msg[data-lf-event="{built.ids[key]}"]'


def reply_box(key):
    return f'.lf-page-thread[data-lf-thread="${key}"] > .lf-thread-reply leaf-text'


SEND = '.lf-page-thread[data-lf-thread="$jobs"] .lf-compose-submit'


def scroll_to(page, node, at):
    """Scroll the document so `node`, a selector or locator, stands `at` px down the
    window."""
    node = page.locator(node) if isinstance(node, str) else node
    node.evaluate(
        """(node, at) => document.scrollingElement.scrollBy({
          top: node.getBoundingClientRect().top - at, behavior: 'instant'})""",
        at,
    )
    scroll_settled(page)


def type_in_reply(page, built, thread="jobs"):
    """Bring the thread's reply box near the window's foot, click into it and type, as
    a user answering does; the pointer stays on the box."""
    box = page.locator(ids_in(reply_box(thread), built))
    box.evaluate(
        """box => document.scrollingElement.scrollBy({
          top: box.getBoundingClientRect().bottom - (innerHeight - 160),
          behavior: 'instant'})"""
    )
    scroll_settled(page)
    box.click()
    page.keyboard.type("Half a thought")


# The pointer stands over the page's left edge, on no control and no words.
ASIDE = (12, 450)

# Where a reader reads, a quarter down the window.
READING_LINE = 900 / 4 - 25


def put_send(page, built):
    type_in_reply(page, built)
    page.keyboard.press("Tab")
    expect(page.locator(ids_in(SEND, built))).to_be_focused()


def put_message(page, built):
    """Click a message's words, which stands the user in its thread with the caret in
    the message and the pointer resting on it. (Tab would reach the message's link in
    Chromium, but Firefox on macOS tabs to no link or button.)"""
    scroll_to(page, message(built, "linked"), 700)
    page.locator(message(built, "linked")).get_by_text("before you start").click()
    expect(page.locator(thread_of(built, "jobs"))).to_be_focused()


def put_reading(page, built):
    """Type in the long thread's reply box, then scroll up away from it to read the
    second paragraph of an earlier message at the reading line."""
    type_in_reply(page, built, "notes")
    page.mouse.move(*ASIDE)
    read = page.locator(f"{message(built, 'read')} p", has_text="being read")
    scroll_to(page, read, READING_LINE)
    expect(page.locator(ids_in(reply_box("notes"), built))).not_to_be_in_viewport()


def put_reading_page(page, built):
    """Type in the short thread's reply box, then scroll down away from it to read a
    paragraph of the page at the reading line."""
    type_in_reply(page, built)
    page.mouse.move(*ASIDE)
    scroll_to(page, "#p-40", READING_LINE)
    expect(page.locator(ids_in(reply_box("jobs"), built))).not_to_be_in_viewport()


PIN = '[data-lf-margin-for="p-31"] .lf-margin-marker'


def put_pin(page, built):
    scroll_to(page, "#p-31", 450)
    page.locator(PIN).first.hover()


# The pin the thread the user works in stands at in the margin, by its seat's head.
JOBS_PIN = '[data-lf-margin-for="jobs"] .lf-margin-marker'


def put_typing_pin(page, built):
    """Type in the reply box, then rest the pointer on its thread's margin pin, in sight
    above it, as a user glancing at the thread does; focus stays in the box."""
    type_in_reply(page, built)
    pin = page.locator(JOBS_PIN).first
    assert pin.evaluate(
        "(pin, box) => pin.getBoundingClientRect().bottom > 0"
        " && pin.getBoundingClientRect().bottom < box.getBoundingClientRect().top",
        page.locator(ids_in(reply_box("jobs"), built)).element_handle(),
    ), "the pin doesn't stand in sight above the reply box"
    pin.hover()


# Over the page's right edge, past the column: its background, no control and no words.
EDGE = (1440 - 1, 400)


def put_typing_edge(page, built):
    """Type in the reply box, then park the pointer on the page's background."""
    type_in_reply(page, built)
    page.mouse.move(*EDGE)


def put_send_words(page, built):
    """Tab to Send from the reply box, then rest the pointer on an earlier message's
    words, which no press acts on, the last thing the user did."""
    put_send(page, built)
    page.locator(message(built, "early")).get_by_text("The beds first").hover()
    expect(page.locator(ids_in(SEND, built))).to_be_focused()


# The fortieth line of `lines`, read as the box of its first letter, so it is the words
# and not the tall paragraph holding them.
LINES_READING = """() => {
  const walk = document.createTreeWalker(document.querySelector('main'),
    NodeFilter.SHOW_TEXT);
  for (let text; (text = walk.nextNode()); )
    if (text.data.trimStart().startsWith('Line 40:')) {
      const at = text.data.search(/\\S/);
      const range = document.createRange();
      range.setStart(text, at);
      range.setEnd(text, at + 1);
      return range;
    }
  return null;
}"""


def put_reading_lines(page, built):
    """Type in the reply box under `lines`, then scroll up away from it to read the
    fortieth line at the reading line, deep inside its paragraph."""
    type_in_reply(page, built, "long")
    page.mouse.move(*ASIDE)
    paragraph = page.locator(f"{message(built, 'lines')} p").first
    paragraph.evaluate(
        """(p, at) => {
          const walk = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
          for (let text; (text = walk.nextNode()); )
            if (text.data.trimStart().startsWith('Line 40:')) {
              const range = document.createRange();
              range.selectNodeContents(text);
              document.scrollingElement.scrollBy({
                top: range.getBoundingClientRect().top - at, behavior: 'instant'});
              return;
            }
          throw new Error('no fortieth line');
        }""",
        READING_LINE,
    )
    scroll_settled(page)
    assert paragraph.evaluate("p => p.getBoundingClientRect().top < 0"), (
        "the paragraph's top stands in the window"
    )
    expect(page.locator(ids_in(reply_box("long"), built))).not_to_be_in_viewport()


def put_left_window(page, built):
    """Type in the reply box, then hover an earlier message and leave the window."""
    type_in_reply(page, built)
    page.locator(message(built, "early")).hover()
    page.mouse.move(-100, -100)


def put_scrolling(page, built):
    """Type in the reply box, then move the pointer onto the page to scroll it."""
    type_in_reply(page, built)
    page.mouse.move(*ASIDE)


SCROLL = 300


def wheel(page):
    page.mouse.wheel(0, SCROLL)


# A scroll that glides, as a key's or a landing's does.
SMOOTH = f"scrollBy({{top: {SCROLL}, behavior: 'smooth'}})"


def map_row(page, label):
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    return dialog.locator(".lf-page-map-action").filter(has_text=label)


def open_map(page):
    resized(page, 1280, 600)
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    expect(page.get_by_role("dialog", name="Page Map", exact=True)).to_be_visible()


def put_map_row(page, built):
    """Walk Page Map's rows down from its search to the fifteenth question's."""
    open_map(page)
    for _ in range(15):
        page.keyboard.press("ArrowDown")
    expect(map_row(page, "Question 15?")).to_be_focused()
    page.mouse.move(*ASIDE)


def put_map_pointer(page, built):
    """Page Map open with focus in its search, the pointer resting on a row."""
    open_map(page)
    row = map_row(page, "Question 15?")
    row.evaluate("node => node.scrollIntoView({block: 'center'})")
    scroll_settled(page, ".lf-page-map-list")
    row.hover()
    expect(page.get_by_role("searchbox")).to_be_focused()


GUTTER = '[data-lf-datum=\'["review.py","new",28]\']'
COMMENT = "button.lf-diff-line-comment"


def to_gutter(page):
    """Bring the diff's twenty-eighth new line halfway down the window, and return its
    Comment."""
    line = page.locator(GUTTER).first
    expect(line).to_be_visible()
    line.evaluate(
        "n => scrollBy({top: n.getBoundingClientRect().top - 500, behavior: 'instant'})"
    )
    scroll_settled(page)
    return line.locator("xpath=..").locator(COMMENT)


def put_disclosure(page, built):
    """Type a note at the page's foot, then scroll up away from it to read the paragraphs
    after the diff, with the disclosure above them 80px down the window."""
    page.locator("#note").click()
    page.keyboard.type("Half a note")
    page.mouse.move(*ASIDE)
    scroll_to(page, "#context summary", 80)
    expect(page.locator("#note")).not_to_be_in_viewport()


def nothing_focused(page):
    """Rest the pointer aside, and check the reader holds nothing focused."""
    page.mouse.move(*ASIDE)
    assert page.evaluate("document.activeElement === document.body"), (
        "something is focused"
    )


def put_reading_unfocused(page, built):
    """Read the second paragraph of an earlier message at the reading line, having
    focused nothing on the page."""
    read = page.locator(f"{message(built, 'read')} p", has_text="being read")
    scroll_to(page, read, READING_LINE)
    nothing_focused(page)


def put_reading_under_thread(page, built):
    """Read a paragraph of the page two thirds down the window, under the threads of
    the first plan, having focused nothing on the page: a reader who only reads."""
    scroll_to(page, "#p-33", 600)
    expect(page.locator(thread_of(built, "jobs"))).to_be_in_viewport()
    nothing_focused(page)


def put_diff_reading(page, built):
    """Read the diff's twenty-eighth new line at the reading line, having focused
    nothing on the page."""
    line = page.locator(GUTTER).first
    expect(line).to_be_visible()
    scroll_to(page, line, READING_LINE)
    nothing_focused(page)


def put_gutter_focus(page, built):
    to_gutter(page).focus()
    page.mouse.move(*ASIDE)


def put_gutter_pointer(page, built):
    """The pointer resting on a line's Comment, in the diff's open shadow root."""
    comment = to_gutter(page)
    page.locator(GUTTER).first.locator("xpath=..").hover()
    comment.hover()


# That line, found inside the diff's shadow root.
GUTTER_LINE = f"""() => {{
  const deep = (root) => root.querySelector({json.dumps(GUTTER)})
    ?? [...root.querySelectorAll('*')].map(n => n.shadowRoot && deep(n.shadowRoot))
      .find(Boolean) ?? null;
  return deep(document);
}}"""

# That Comment, found inside the diff's shadow root.
GUTTER_COMMENT = f"""() => {{
  const deep = (root) => root.querySelector({json.dumps(GUTTER)})
    ?? [...root.querySelectorAll('*')].map(n => n.shadowRoot && deep(n.shadowRoot))
      .find(Boolean) ?? null;
  return deep(document)?.parentElement.querySelector({json.dumps(COMMENT)}) ?? null;
}}"""


def put_dial(motion, at=900 * 0.25 - 10):
    def put(page, built):
        page.emulate_media(reduced_motion=motion)
        scroll_to(page, "#detail-cause-1", at)

    return put


# The line the reader reads: the em's first line while its paragraph shows, and from
# its fold on, the first line of the gist that stands for it, which the reader reads
# on through the turn back to Read. Each is read as the box of its first word's first
# letter, so the em's inline box and the gist's block compare line for line.
DIAL_READING = """() => {
  const em = document.querySelector('#detail-cause-1 em');
  if (!em.checkVisibility()) window.__lfDialFolded = true;
  const read = window.__lfDialFolded ? document.getElementById('detail-cause-gist') : em;
  const text = read.firstChild;
  const at = text.data.search(/\\S/);
  const range = document.createRange();
  range.setStart(text, at);
  range.setEnd(text, at + 1);
  return range;
}"""

# For a reader in the middle of a paragraph that began above the window: the first
# letter of the line at the reading line, a quarter down the window, found once, and
# from the fold on, the gist. Its box lands where those letters stood, which puts its
# own letters half a leading lower, 2.1-2.5px, a step below what the eye takes in
# across a fold.
DIAL_WORDS = """() => {
  const em = document.querySelector('#detail-cause-1 em');
  if (!em.checkVisibility()) window.__lfDialFolded = true;
  if (window.__lfDialFolded) return document.getElementById('detail-cause-gist');
  if (window.__lfDialWords) return window.__lfDialWords;
  const {offsetNode: text, offset} = document.caretPositionFromPoint(
    em.parentElement.getBoundingClientRect().left + 1, innerHeight / 4);
  const at = offset + text.data.slice(offset).search(/\\S/);
  const range = window.__lfDialWords = document.createRange();
  range.setStart(text, at);
  range.setEnd(text, at + 1);
  return range;
}"""


def put_pane(page, built):
    """Read the left pane's thirty-first paragraph a quarter down the pane."""
    page.locator("#left-body").evaluate(
        """body => { const p = document.getElementById('q-30');
          body.scrollTop += p.getBoundingClientRect().top
            - body.getBoundingClientRect().top - body.clientHeight / 4; }"""
    )
    scroll_settled(page, "#left-body")
    page.mouse.move(*ASIDE)


def put_on_me_row(page, built):
    """On Me open in the panel, its list scrolled past its first rows, the user on a
    row in sight."""
    page.locator(".lf-fp-on-user").click()
    rows = page.locator(".lf-fp-on-item")
    expect(rows).to_have_count(ASKS)
    rows.first.evaluate(
        """row => {
          for (let n = row.parentElement; n; n = n.parentElement)
            if (/auto|scroll/.test(getComputedStyle(n).overflowY)
                && n.scrollHeight > n.clientHeight) {
              n.scrollTop = 3 * row.getBoundingClientRect().height;
              return;
            }
          throw new Error('On Me does not scroll');
        }"""
    )
    row = rows.filter(has_text="Ask 6:")
    row.focus()
    expect(row).to_be_in_viewport()
    page.mouse.move(*ASIDE)


def put_on_me_turned_back(page, built):
    """On Me turned to On <agent> and back by its tabs, which fits the list afresh, then
    scrolled with the wheel past its first cards, the pointer resting on one in sight.
    Nothing the user does after the tab press repaints the panel, and no card holds a
    message for Leaf's reader to draw, so the list's next paint is the news's."""
    page.locator(".lf-fp-on-user").click()
    cards = page.locator(".lf-fp-on-item")
    expect(cards).to_have_count(ASKS)
    tabs = page.locator(".lf-fp-controls .lf-fp-filters button")
    tabs.filter(has_text=re.compile(r"^\s*On (?!Me)")).click()
    expect(cards).to_have_count(0)
    tabs.filter(has_text="On Me").click()
    expect(cards).to_have_count(ASKS)
    view = page.locator(".lf-floating-panel .lf-fp-view:not([data-lf-leaving])")
    box = view.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, 3 * cards.first.bounding_box()["height"])
    expect(view).not_to_have_js_property("scrollTop", 0)
    scroll_settled(page, ".lf-floating-panel .lf-fp-view:not([data-lf-leaving])")
    card = cards.filter(has_text="Ask 6:")
    expect(card).to_be_in_viewport()
    card.hover()


CARD = ".lf-margin-preview:not([hidden])"
CARD_REPLY = f"{CARD} .lf-thread-reply leaf-text"
CARD_RESOLVE = f'{CARD} button[aria-label="Resolve thread"]'
PANEL_VIEW = '.lf-fp-view[data-lf-route="thread"]:not([data-lf-leaving])'
PANEL_REPLY = ".lf-floating-panel .lf-thread-reply leaf-text"
PANEL_RESOLVE = '.lf-floating-panel .lf-fp-head button[aria-label="Resolve thread"]'


def open_card(page, built, thread):
    """Open `thread`'s margin card by a click on its row's marker, its words a third of
    the way down the window; the click leaves the caret in the card's reply box."""
    section = {"told": "p-20", "asked": "p-22"}[thread]
    scroll_to(page, f"#{section}", 300)
    page.locator(f'[data-lf-margin-for="{section}"] .lf-margin-marker').first.click()
    card = page.locator(CARD)
    expect(
        card.locator(f'.lf-page-thread[data-lf-thread="{built.ids[thread]}"]')
    ).to_be_visible()
    settle(page)
    return card


def put_card(thread, *, words=False, on=None):
    def put(page, built):
        card = open_card(page, built, thread)
        if words:
            card.get_by_role("textbox", name="Reply", exact=True).click()
            page.keyboard.type("Half a thought")
        if on:
            page.locator(on).first.hover()
        else:
            page.mouse.move(*ASIDE)

    return put


def put_panel(thread, *, words=False, on=None):
    def put(page, built):
        """Open `thread` in the floating panel from Threads."""
        scroll_to(page, "#p-20", 300)
        go_to_threads(page)
        topic = {"told": "paragraph 20", "asked": "paragraph 22"}[thread]
        page.locator(".lf-fp-thread", has_text=topic).click()
        view = page.locator(PANEL_VIEW)
        expect(view).to_be_visible()
        panel_settled(page)
        if words:
            page.locator(PANEL_REPLY).click()
            page.keyboard.type("Half a thought")
        if on:
            page.locator(on).first.hover()
        else:
            page.mouse.move(*ASIDE)

    return put


def floating_places():
    """The places in a thread's two floating boxes, the margin card and the floating
    panel's view: writing a reply, the caret in the empty reply box, and the pointer
    resting on Resolve at the box's head, with and without words in the reply box, in
    a thread whose next message is news (`told`) and in one whose next message answers
    the user (`asked`)."""
    for thread in ("told", "asked"):
        for box, put, reply, resolve in (
            ("card", put_card, CARD_REPLY, CARD_RESOLVE),
            ("panel", put_panel, PANEL_REPLY, PANEL_RESOLVE),
        ):
            yield Place(
                f"{box}-typing-{thread}",
                "floating",
                put(thread, words=True),
                Found(reply),
                {"thread above": thread},
            )
            yield Place(
                f"{box}-caret-{thread}",
                "floating",
                put(thread),
                Found(reply),
                {"thread above": thread},
            )
            yield Place(
                f"{box}-resolve-{thread}",
                "floating",
                put(thread, on=resolve),
                Found(resolve),
                {"thread below": thread},
            )
            yield Place(
                f"{box}-writing-on-resolve-{thread}",
                "floating",
                put(thread, words=True, on=resolve),
                Found(resolve),
                {"thread below": thread},
            )


PLACES = [
    Place(
        "typing",
        "thread",
        type_in_reply,
        Found(reply_box("jobs")),
        {
            "thread above": "jobs",
            "message above": "early",
            "shrink above": "early",
            "seat above": "fresh",
            "page above": None,
            "removal above": None,
        },
    ),
    Place(
        "message",
        "thread",
        put_message,
        Found('.lf-msg[data-lf-event="$linked"]'),
        {
            "thread above": "upper",
            "thread below": "jobs",
            "message above": "early",
            "seat above": "fresh",
            "page above": None,
        },
    ),
    Place(
        "send",
        "thread",
        put_send,
        Found(SEND),
        {"thread above": "jobs", "message above": "early", "page above": None},
    ),
    Place(
        "reading",
        "thread",
        put_reading,
        Found('.lf-msg[data-lf-event="$read"] p', "being read"),
        {
            "thread above": "jobs",
            "thread below": "notes",
            "paragraph above": "read",
            "shrink above": "read",
            "page above": None,
            "removal above": None,
        },
    ),
    Place(
        "reading-page",
        "thread",
        put_reading_page,
        Found("#p-40"),
        {
            "thread above": "jobs",
            "page above": None,
            "on screen above": None,
            "removal above": None,
        },
    ),
    Place(
        "pin",
        "thread",
        put_pin,
        Found(PIN),
        {
            "thread above": "jobs",
            "message above": "linked",
            "page above": None,
            "on screen above": None,
        },
    ),
    Place(
        "left-window",
        "thread",
        put_left_window,
        Found(reply_box("jobs")),
        {"thread above": "jobs"},
    ),
    Place(
        "typing-pin",
        "thread",
        put_typing_pin,
        Found(reply_box("jobs")),
        {"thread above": "jobs"},
    ),
    Place(
        "typing-edge",
        "thread",
        put_typing_edge,
        Found(reply_box("jobs")),
        {"thread above": "jobs"},
    ),
    Place(
        "send-words", "thread", put_send_words, Found(SEND), {"thread above": "jobs"}
    ),
    Place(
        "reading-unfocused",
        "thread",
        put_reading_unfocused,
        Found('.lf-msg[data-lf-event="$read"] p', "being read"),
        {"paragraph above": "read"},
    ),
    Place(
        "reading-under-thread",
        "thread",
        put_reading_under_thread,
        Found("#p-33"),
        {"thread above": "jobs"},
    ),
    Place(
        "reading-lines",
        "thread",
        put_reading_lines,
        LINES_READING,
        {"lines in the block": "lines"},
    ),
    Place(
        "wheel",
        "thread",
        put_scrolling,
        Found(reply_box("jobs")),
        {"thread above": "jobs", "page above": None},
        travel=-SCROLL,
        during=wheel,
    ),
    Place(
        "smooth",
        "thread",
        put_scrolling,
        Found(reply_box("jobs")),
        {"thread above": "jobs", "page above": None},
        travel=-SCROLL,
        during=SMOOTH,
        midway=True,
    ),
    Place(
        "map-row",
        "map",
        put_map_row,
        Found(".lf-page-map-action", "Question 15?"),
        {"map row above": "place-14", "contribution above": "place-14"},
    ),
    Place(
        "map-pointer",
        "map",
        put_map_pointer,
        Found(".lf-page-map-action", "Question 15?"),
        {"map row above": "place-14", "contribution above": "place-14"},
    ),
    Place("gutter", "diff", put_gutter_focus, GUTTER_COMMENT, {"lines above": 5}),
    Place("diff-reading", "diff", put_diff_reading, GUTTER_LINE, {"lines above": 5}),
    Place(
        "disclosure",
        "diff",
        put_disclosure,
        Found("#context summary"),
        {"grammar pending": None},
    ),
    Place(
        "shadow-pointer", "diff", put_gutter_pointer, GUTTER_COMMENT, {"lines above": 5}
    ),
    Place(
        "dial",
        "dial",
        put_dial("no-preference"),
        DIAL_READING,
        {"dial": None, "glided": "detail-impact-gist"},
    ),
    Place("dial-reduced", "dial", put_dial("reduce"), DIAL_READING, {"dial": None}),
    Place(
        "dial-begun",
        "tall-dial",
        put_dial("no-preference", -400),
        DIAL_WORDS,
        {"dial": None},
    ),
    Place("pane", "pane", put_pane, Found("#q-30"), {"pane above": "left-body"}),
    Place(
        "on-me-row",
        "queue",
        put_on_me_row,
        Found(".lf-fp-on-item", "Ask 6:"),
        {"ask above": "ask-0"},
    ),
    Place(
        "on-me-turned-back",
        "decisions",
        put_on_me_turned_back,
        Found(".lf-fp-on-item", "Ask 6:"),
        {"ask above": "ask-0"},
    ),
    *floating_places(),
]

# ---------------------------------------------------------------------------------
# What changes.


@dataclass(frozen=True)
class Change:
    """What arrives: the role around a place it acts on (`on`), and how it is made and
    seen to have arrived (`make`, given the page, the built page, the role's target and
    the place). `make` returns how far the change's own result may move the place, if
    it may."""

    name: str
    on: str
    make: Callable


# When the page's held read of a change may go: once the user's scroll has come `by`
# px of its way. With `midway` true it goes then, while the scroll is short of its
# `goal`, and a scroll already there is a case that missed what it means to measure.
# Otherwise it goes once the scroll has ended: its `scrollend` has fired, or, where the
# engine fires none, the scroll has stood still `quiet` ms over two frames or more,
# longer than the runtime's own rule for an end it doesn't hear (`SETTLE_MS` in
# browser/runtime/arrivals.js). So whether the page has heard the end is never left
# to timing.
RELEASE = """async ([by, goal, midway, quiet]) => {
  const record = window.__lfPlaceRecord;
  const page = document.scrollingElement;
  const frame = () => new Promise((then) => requestAnimationFrame(then));
  const come = () => Math.abs(page.scrollTop - record.scroll);
  while (come() < by) await frame();
  if (midway) return (record.release = come() < goal - 1 ? 'under way' : 'missed');
  let at = page.scrollTop, since = performance.now(), frames = 0;
  while (!record.ended && (frames < 2 || performance.now() - since < quiet)) {
    await frame();
    if (page.scrollTop === at) frames++;
    else [at, since, frames] = [page.scrollTop, performance.now(), 0];
  }
  return (record.release = record.ended ? 'ended' : 'ended unheard');
}"""

# How long a scroll whose end the engine never announces stands still before the page
# may read the change: past the runtime's 80ms rule, with room for a busy frame.
QUIET_MS = 160


def midway(page, place):
    """Whether this case takes the change in while the user's scroll is under way."""
    return place.midway and page.context.browser.browser_type.name == "firefox"


def arriving(page, place, write, drawn):
    """Write a change behind the page and wait until the page shows it.

    Where the user scrolls, the scroll starts while the server holds the page's read of
    the change, and the read goes once the scroll has come a tenth of its way
    (`RELEASE`). A place `midway` means the change to draw mid-scroll, which the case
    confirms, and two engine facts say where it can. Playwright's wheel scrolls at
    once in both engines, and in Firefox it never fires `scrollend`. While a smooth
    scroll runs in Chromium, Playwright's calls answer some 250ms late, by when the
    scroll has ended, so there the read waits for the end, and only Firefox takes a
    change mid-scroll."""
    if place.during:
        held = []

        def hold(route):
            held.append(route)

        page.route("**/api/state*", hold)
        write()
        holding(page, held, 1, "the page's read of the change")
        if callable(place.during):
            place.during(page)
            release = RELEASE
        else:
            release = f"async (args) => {{ {place.during}; return ({RELEASE})(args); }}"
        page.evaluate(release, [SCROLL / 10, SCROLL, midway(page, place), QUIET_MS])
        # The read goes before the route is taken down, which can take a while.
        released = list(held)
        for route in released:
            route.continue_()
        page.unroute("**/api/state*", hold)
        for route in held[len(released) :]:
            route.continue_()
    else:
        write()
    told(page)
    drawn()


WHERE = """(selector) => {
  const node = document.querySelector(selector);
  const place = window.__lfPlaceBox().getBoundingClientRect();
  const box = node.getBoundingClientRect();
  return {above: box.bottom <= place.top + 1, shown: box.bottom > 0,
          below: box.top >= place.bottom - 1 && box.top < innerHeight};
}"""


def reply(side):
    def make(page, built, target, place):
        """The agent answers in a thread whose last message, where the answer joins,
        stands on `side` of the place. The page may draw it at once or hold it behind
        the thread's notice."""
        selector = thread_of(built, target)
        messages = page.locator(f"{selector} .lf-msg")
        last = messages.last.evaluate("n => n.dataset.lfEvent")
        where = page.evaluate(WHERE, f'{selector} .lf-msg[data-lf-event="{last}"]')
        assert where[side], f"the thread doesn't end {side} the place: {where}"
        count = messages.count()
        arriving(
            page,
            place,
            lambda: append_agent_reply(
                built.page_dir, built.ids[target], "The agent's answer.\n\n" + WORDS * 3
            ),
            lambda: page.wait_for_function(
                """([selector, count]) => {
                  const thread = document.querySelector(selector);
                  const shown = (news) => news && news.checkVisibility();
                  return thread.querySelectorAll('.lf-msg').length > count
                    || shown(thread.querySelector('.lf-thread-news'))
                    || shown(document.querySelector('.lf-fp-news-outlet .lf-thread-news'));
                }""",
                arg=[selector, count],
            ),
        )
        note_news(page, built, selector)

    return make


def note_news(page, built, inside):
    """Note whether the thread holding `inside` drew the news or holds it behind its
    notice, which says what reached the place."""
    built.notes["news"] = page.evaluate(
        """(selector) => document.querySelector(selector)
          .closest('.lf-page-thread').querySelector('.lf-thread-news')?.checkVisibility()
          || document.querySelector('.lf-fp-news-outlet .lf-thread-news')?.checkVisibility()
          ? 'held' : 'drawn'""",
        inside,
    )


def edit(page, built, target, place):
    """The agent rewrites a message of its own above the place, growing its first
    paragraph and keeping the rest."""
    selector = message(built, target)
    where = page.evaluate(WHERE, f"{selector} p")
    assert where["above"], f"the message doesn't stand above the place: {where}"
    rest = "\n\nThe paragraph being read. " + WORDS * 2 if target == "read" else ""
    text = "A first paragraph the agent grew. " + WORDS * 3 + rest
    arriving(
        page,
        place,
        lambda: leaf(
            "thread", "edit", built.page_dir, built.ids[target], "--text", text
        ),
        lambda: page.wait_for_function(
            """(selector) => {
              const message = document.querySelector(selector);
              return message?.textContent.includes('grew')
                || message?.closest('.lf-page-thread').querySelector('.lf-thread-news');
            }""",
            arg=selector,
        ),
    )
    note_news(page, built, selector)


def shrink(page, built, target, place):
    """The agent rewrites a message of its own above the place shorter: the one read
    loses the paragraph before the one read, and any other shrinks to a word."""
    selector = message(built, target)
    where = page.evaluate(WHERE, f"{selector} p")
    assert where["above"], f"the message doesn't stand above the place: {where}"
    if target == "read":
        text, lost = "The paragraph being read. " + WORDS * 2, "A short first paragraph"
    else:
        text, lost = "Shortened.", WORDS[:20]
    height = (
        f"() => document.querySelector('{selector}').getBoundingClientRect().height"
    )
    before = page.evaluate(height)
    arriving(
        page,
        place,
        lambda: leaf(
            "thread", "edit", built.page_dir, built.ids[target], "--text", text
        ),
        lambda: page.wait_for_function(
            """([selector, lost]) => {
              const message = document.querySelector(selector);
              return message && !message.textContent.includes(lost)
                || message?.closest('.lf-page-thread').querySelector('.lf-thread-news');
            }""",
            arg=[selector, lost],
        ),
    )
    note_news(page, built, selector)
    settle(page)
    built.notes["message shrank"] = round(before - page.evaluate(height), 1)


def new_thread(page, built, target, place):
    """The agent starts a thread in a seat on screen above the place, or on a paragraph
    whose Page Map row joins inside the list's view above the place's row.

    A thread not drawn yet draws at once, the rare path on which the user chose to let
    it move what follows it (browser/AGENTS.md, "News moves what the reader reads only
    in the thread they are in"), so a place after the seat may move by what the seat
    grew, and no further."""
    seat = f"() => document.getElementById('{target}').getBoundingClientRect().height"
    if place.page == "map":
        assert map_row(page, "Question 13?").evaluate(
            "n => n.getBoundingClientRect().top"
            " > n.closest('.lf-page-map-list').getBoundingClientRect().top"
        ), "the row would join above the list's view"
        drawn = map_row(page, "One more question?")
    else:
        where = page.evaluate(WHERE, f"#{target}")
        assert where["above"] and where["shown"], f"the seat stands {where}"
        drawn = page.locator(f"#{target} .lf-page-thread")
        before = page.evaluate(seat)
    text = "One more question? " + WORDS
    arriving(
        page,
        place,
        lambda: leaf(
            "thread", "create", built.page_dir, "--section", target, "--text", text
        ),
        lambda: expect(drawn).to_have_count(1),
    )
    if place.page == "map":
        return None
    settle(page)
    return page.evaluate(seat) - before


def ask(page, built, target, place):
    """The agent asks on the page's opening part, whose row joins On Me's head, above
    the rows in sight."""
    asked = ["--section", target, "--obligation", "--text", "One more ask?"]
    arriving(
        page,
        place,
        lambda: leaf("thread", "create", built.page_dir, *asked),
        lambda: expect(page.locator(".lf-fp-on-item")).to_have_count(ASKS + 1),
    )


def revised(page, built, place, html, changed, count=1):
    """Publish `html` as the page's next revision, and wait until the page holds
    `count` of `changed`, what the revision added or took out."""
    built.revision += 1
    revision = built.revision
    arriving(
        page,
        place,
        lambda: stamp_page(built.page_dir, html, f"Revision {revision}"),
        lambda: (
            wait_for_revision(page, revision),
            expect(page.locator(changed)).to_have_count(count),
        ),
    )


ADDED = (
    '<p id="added-{n}">An added paragraph {n}, long enough to wrap onto a second '
    "line of the column, as an agent's revision writes it.</p>"
)


def revision_above_window(page, built, target, place):
    """A revision adds four paragraphs above the window."""
    assert page.locator("#p-3").evaluate("p => p.getBoundingClientRect().bottom < 0")
    added = "".join(ADDED.format(n=n) for n in range(4))
    html = built.source.replace('<p id="p-3">', added + '<p id="p-3">')
    revised(page, built, place, html, "#added-3")


def revision_on_screen(page, built, target, place):
    """A revision adds a paragraph before the last of the page's own standing on screen
    above the place."""
    before = page.evaluate(
        """() => {
          const place = window.__lfPlaceBox().getBoundingClientRect();
          const shown = [...document.querySelectorAll('main > p[id]')].filter(p => {
            const box = p.getBoundingClientRect();
            return box.top >= 0 && box.bottom <= place.top;
          });
          return shown.at(-1)?.id ?? null;
        }"""
    )
    assert before, "no paragraph of the page stands on screen above the place"
    added = ADDED.format(n=0)
    html = built.source.replace(f'<p id="{before}">', added + f'<p id="{before}">')
    revised(page, built, place, html, "#added-0")


def revision_removes(page, built, target, place):
    """A revision takes out the last of the page's own paragraphs standing above the
    place, on screen or above the window, as the case notes."""
    last = page.evaluate(
        """() => {
          const place = window.__lfPlaceBox().getBoundingClientRect();
          const above = [...document.querySelectorAll('main > p[id]')]
            .filter(p => p.getBoundingClientRect().bottom <= place.top);
          const p = above.at(-1);
          return p && {id: p.id, shown: p.getBoundingClientRect().bottom > 0};
        }"""
    )
    assert last, "no paragraph of the page stands above the place"
    built.notes["removed"] = f"{last['id']} {'on screen' if last['shown'] else 'above'}"
    html, taken = re.subn(rf'<p id="{last["id"]}">.*?</p>', "", built.source, count=1)
    assert taken == 1, f"the source holds no {last['id']}"
    revised(page, built, place, html, f"#{last['id']}", count=0)


def revision_in_pane(page, built, target, place):
    """A revision adds five paragraphs at the top of the pane, above what it shows."""
    added = "".join(ADDED.format(n=n) for n in range(5))
    html = built.source.replace(f'<div id="{target}">', f'<div id="{target}">' + added)
    revised(page, built, place, html, "#added-4")


def contribution(page, built, target, place):
    """A widget's own entry joins Page Map on the paragraph above the place's row, as
    the widget draws it."""
    page.evaluate(
        """async (target) => {
          const {contributionEntry, registerContribution} = await window.__lfWidgetApi();
          registerContribution({
            key: 'joining', target: () => document.getElementById(target),
            read: () => ({entries: [contributionEntry(
              {key: 'action', icon: 'dot', label: 'Joining action'})]}),
            activate: () => {},
          }).update({immediate: true});
        }""",
        target,
    )
    joined = map_row(page, "Joining action")
    expect(joined).to_be_visible()
    assert joined.evaluate(
        "(n, row) => n.compareDocumentPosition(row) & Node.DOCUMENT_POSITION_FOLLOWING",
        map_row(page, "Question 15?").element_handle(),
    ), "the entry joined below the place's row"


def deletions(page, built, target, place):
    """Deleted lines join the diff above the place, as its data source changes."""
    arriving(
        page,
        place,
        lambda: data_model.cmd_data_set(
            built.page_dir, "review-patch", diff_rows(target)
        ),
        lambda: expect(
            page.locator('.lf-diff-line[data-line-type="change-deletion"]')
        ).to_have_count(target),
    )


def press_while_pending(page, built, target, place):
    """The agent's new data brings the diff a Go file, whose syntax grammar the diff
    waits on, and while it waits, so the page's showing of that reading is still under
    way, the user opens the disclosure. Opening it is the user's own act, which moves
    what follows the summary and not the summary."""
    held = []

    def hold(route):
        held.append(route)

    page.route("**/vendor/syntax/go.js", hold)
    patch = (
        "diff --git a/review.go b/review.go\n--- a/review.go\n+++ b/review.go\n"
        "@@ -1 +1 @@\n-old\n+new\n"
    )
    data_model.cmd_data_set(built.page_dir, "review-patch", patch)
    holding(page, held, 1, "the diff's request for the Go grammar")
    summary = page.locator("#context summary")
    box = summary.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    expect(page.locator("#context")).to_have_attribute("open", "")
    page.unroute("**/vendor/syntax/go.js", hold)
    for route in held:
        route.continue_()
    expect(page.locator("lf-diff#patch")).to_contain_text("review.go")


def turn(page, label):
    """Press a depth with the pointer, as the reader does, and wait out its glide.

    The glide is the turn's own result, motion the eye can follow (browser/AGENTS.md,
    "Controls stay where the user aims"), so the frames from the press until it ends
    are marked `gliding` (`ARM`) and the place's check passes over them; the frame it
    ends in and every one after are held to the place."""
    depth = page.get_by_role("radio", name=label, exact=True)
    box = depth.bounding_box()
    page.evaluate("() => { window.__lfPlaceRecord.turning = true; }")
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    expect(depth).to_have_attribute("aria-checked", "true")
    page.wait_for_function(
        "() => !window.__lfPlaceRecord.gliding && !document.getAnimations().length"
    )


def dial_turn(page, built, target, place):
    """Skim, which folds the paragraph read behind its section's gist, then Read."""
    turn(page, "Skim")
    expect(page.locator("#detail-cause-1")).to_be_hidden()
    settle(page)
    checkpoint(page, "skimmed")
    turn(page, "Read")
    expect(page.locator("#detail-cause-1")).to_be_visible()


LATE_IMAGE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="200">'
    '<rect width="600" height="200" fill="gray"/></svg>'
)


def grown_after_glide(page, built, target, place):
    """Skim, and once the glide has ended, an image in the gist of the section above
    the one read finishes loading 200px tall."""
    held = []

    def hold(route):
        held.append(route)

    page.route("**/late-image.svg", hold)
    page.locator(f"#{target}").evaluate(
        """gist => {
          const image = Object.assign(new Image(), {id: 'late-image', alt: ''});
          image.style.display = 'block';
          image.src = '/late-image.svg';
          gist.append(image);
        }"""
    )
    holding(page, held, 1, "the image's load")
    turn(page, "Skim")
    expect(page.locator("#detail-cause-1")).to_be_hidden()
    settle(page)
    checkpoint(page, "skimmed")
    held[0].fulfill(status=200, content_type="image/svg+xml", body=LATE_IMAGE)
    page.wait_for_function(
        "() => document.getElementById('late-image').getBoundingClientRect().height"
    )


def rewrite_lines(grows):
    def make(page, built, target, place):
        """The agent rewrites the paragraph of lines, adding five lines at its start or
        taking its first five away; the line read and those after it keep their words."""
        selector = message(built, target)
        text = (
            (line_list(0, 5, "New line") + "  \n" + LINES)
            if grows
            else line_list(5, 75)
        )
        word = "New line 0" if grows else None
        arriving(
            page,
            place,
            lambda: leaf(
                "thread", "edit", built.page_dir, built.ids[target], "--text", text
            ),
            lambda: page.wait_for_function(
                """([selector, word]) => {
                  const message = document.querySelector(selector);
                  return word ? message?.textContent.includes(word)
                    : !message?.textContent.includes('Line 0:');
                }""",
                arg=[selector, word],
            ),
        )
        note_news(page, built, selector)

    return make


CHANGES = [
    Change("reply-above", "thread above", reply("above")),
    Change("reply-below", "thread below", reply("below")),
    Change("edit-above", "message above", edit),
    Change("edit-paragraph", "paragraph above", edit),
    Change("edit-shrinks", "shrink above", shrink),
    Change("revision-above", "page above", revision_above_window),
    Change("revision-on-screen", "on screen above", revision_on_screen),
    Change("revision-removes", "removal above", revision_removes),
    Change("revision-in-pane", "pane above", revision_in_pane),
    Change("seat-thread", "seat above", new_thread),
    Change("map-thread", "map row above", new_thread),
    Change("map-entry", "contribution above", contribution),
    Change("ask", "ask above", ask),
    Change("deletions", "lines above", deletions),
    Change("dial-turn", "dial", dial_turn),
    Change("grown-after-glide", "glided", grown_after_glide),
    Change("press-while-pending", "grammar pending", press_while_pending),
    Change("lines-grow", "lines in the block", rewrite_lines(True)),
    Change("lines-shrink", "lines in the block", rewrite_lines(False)),
]

# ---------------------------------------------------------------------------------
# The measure.

# Read where the place's box stands, its left and top, once after each frame renders,
# from before the change until the page settles: a task posted from a frame callback
# runs once that frame has rendered. A reading of null is a frame without the box, or
# with a box of no width or no height. Each frame says whether a turn's glide was under
# way: from the press of a turn (`gliding`) until the first frame in which no animation
# runs, which is held to the place.
#
# Beside it, where the document's scroll and height stood, which says whether the
# change reached the page at all; each scroll of the document; and how far the user's
# scroll had come by the last of those before the change first grew the document.
ARM = """() => {
  const frame = requestAnimationFrame.bind(window);
  const at = () => {
    const node = window.__lfPlaceBox();
    if (!node || (node instanceof Node && !node.isConnected)) return null;
    const box = node instanceof Range ? node.getClientRects()[0]
      : node.getBoundingClientRect();
    return box && box.width && box.height ? [box.left, box.top] : null;
  };
  const page = document.scrollingElement;
  const record = window.__lfPlaceRecord = {
    start: at(), frames: [], marks: {}, at, turning: false, gliding: false,
    scroll: page.scrollTop, height: page.scrollHeight, scrolls: [], atGrowth: null,
  };
  if (!record.start) throw new Error('the place has no box to read');
  document.addEventListener('click', () => {
    if (record.turning) [record.turning, record.gliding] = [false, true];
  }, {capture: true});
  document.addEventListener('scroll', (event) => {
    if (event.target === document) record.scrolls.push(page.scrollTop - record.scroll);
  });
  document.addEventListener('scrollend', () => { record.ended = true; });
  const growth = new MutationObserver(() => {
    if (page.scrollHeight === record.height) return;
    record.atGrowth = record.scrolls.at(-1) ?? 0;
    growth.disconnect();
  });
  growth.observe(document.body, {childList: true, subtree: true, characterData: true});
  const next = () => frame(() => {
    const {port1, port2} = new MessageChannel();
    port1.onmessage = () => {
      if (record.done) return;
      if (record.gliding && !document.getAnimations().length) record.gliding = false;
      record.frames.push({at: at(), gliding: record.gliding});
      next();
    };
    port2.postMessage(null);
  });
  next();
}"""

READ = """() => {
  const record = window.__lfPlaceRecord;
  record.done = true;
  const page = document.scrollingElement;
  return {start: record.start, end: record.at(), frames: record.frames,
          marks: record.marks, scrolled: page.scrollTop - record.scroll,
          grew: page.scrollHeight - record.height, release: record.release ?? null,
          atGrowth: record.atGrowth, scrolls: record.scrolls};
}"""


def checkpoint(page, name):
    """Read the place's box now, under `name`, for a change that passes through a
    state of its own on its way, as the dial's fold does before it unfolds again."""
    page.evaluate(
        "name => { const r = window.__lfPlaceRecord; r.marks[name] = r.at(); }", name
    )


class Moved(AssertionError):
    """The place moved, or left a painted frame, where neither the user's own act nor
    the change's own result moves it. A case marked as failing expects only this, so a
    setup or delivery that fails still fails it."""


def held(still, message):
    if not still:
        raise Moved(message)


ENGINES = {"browser": "chromium", "firefox_browser": "firefox"}

REVISION_LANDING = "the revision's landing moves the message clicked 96px up"
ON_SCREEN = "the paragraph read moves 67.4px down under the paragraph the revision adds"
REMOVES = "the paragraph read moves 67.4px up into the paragraph the revision takes out"
DELETIONS = "the diff's Comment moves 100px down as five deletions join above it"
DIFF_READING = (
    "the diff line read moves 100px down as five deletions join above it, nothing "
    "focused: anchoring holds the first block in view, above the rows"
)
GROWN_AFTER_GLIDE = (
    "the gist read moves 199.7-199.8px down as the 200px image above it loads after "
    "the glide; Chromium held it before #5397"
)

# The cases the runtime fails today, with what each measured: a fix flips one to a
# pass, and its strict mark then fails until its entry goes.
MOVES_ON_MAIN = {
    "diff-reading-deletions-chromium": DIFF_READING,
    "diff-reading-deletions-firefox": DIFF_READING,
    "message-revision-above-chromium": REVISION_LANDING,
    "message-revision-above-firefox": REVISION_LANDING,
    "reading-page-revision-on-screen-chromium": ON_SCREEN,
    "reading-page-revision-on-screen-firefox": ON_SCREEN,
    "smooth-reply-above-firefox": (
        "drawing the answer stops the smooth scroll under way: the box moves only as "
        "far as the scroll had come, 34-66px of its 300"
    ),
    "smooth-revision-above-firefox": (
        "the revision's landing stops the smooth scroll under way: the box moves only "
        "as far as the scroll had come, 59-102px of its 300"
    ),
    "reading-page-revision-removes-chromium": REMOVES,
    "reading-page-revision-removes-firefox": REMOVES,
    "shadow-pointer-deletions-chromium": DELETIONS,
    "shadow-pointer-deletions-firefox": DELETIONS,
    "dial-grown-after-glide-chromium": GROWN_AFTER_GLIDE,
    "dial-grown-after-glide-firefox": GROWN_AFTER_GLIDE,
}


# The cases where the place moves because the user chose the rule that moves it: the
# rule's owner records the choice, and a change of mind there flips the case to a pass,
# whose strict mark then fails until its entry goes.
EMPTY_REPLY = (
    "a card grows down past the empty reply box a send or an opening left the caret "
    "in, 239px, so the answer shows under the words read (thread-preview.js, the "
    "user's choices of 5 and 9 November 2026)"
)
MOVES_BY_CHOICE = {
    f"card-caret-{thread}-reply-above-{engine}": EMPTY_REPLY
    for thread in ("told", "asked")
    for engine in ("chromium", "firefox")
}


def cases():
    for place in PLACES:
        for change in CHANGES:
            if change.on not in place.around:
                continue
            for fixture, engine in ENGINES.items():
                case = f"{place.name}-{change.name}-{engine}"
                reason = MOVES_ON_MAIN.get(case) or MOVES_BY_CHOICE.get(case)
                marks = (
                    [pytest.mark.xfail(strict=True, raises=Moved, reason=reason)]
                    if reason
                    else []
                )
                yield pytest.param(place, change, fixture, marks=marks, id=case)


def stray(start, at, travel, stands, furthest):
    """How far a painted frame shows the place off where it may stand, and how far
    along its scroll the place has come by then. A still place may stand only at one
    of `stands`; a place the user scrolls may stand only on its path from the start to
    the scroll's goal, and never back toward the start from the furthest it came."""
    dx, dy = at[0] - start[0], at[1] - start[1]
    if not travel:
        return max(abs(dx), min(abs(dy - stand) for stand in stands)), furthest
    along = dy / travel
    beyond = max(-along, along - 1, furthest - along, 0) * abs(travel)
    return max(abs(dx), beyond), max(furthest, along)


@pytest.mark.parametrize(("place", "change", "engine"), list(cases()))
def test_the_page_holds_still_under_the_user(
    request, serve, record_property, place, change, engine
):
    built = PAGES[place.page](serve)
    page = open_page(request.getfixturevalue(engine), built.url)
    resized(page, 1440, 900)
    place.put(page, built)
    settle(page)
    rendered(page)
    box = place.box.js(built) if isinstance(place.box, Found) else place.box
    page.evaluate(f"() => {{ window.__lfPlaceBox = {box}; }}")
    page.evaluate(ARM)
    # How far the change's own result may move the place, besides nothing.
    allowed = change.make(page, built, place.around[change.on], place)
    settle(page)
    rendered(page)
    reading = page.evaluate(READ)
    start, end = reading["start"], reading["end"]
    stands = [0, allowed] if allowed else [0]

    painted, gone, furthest = 0, 0, 0
    for frame in reading["frames"]:
        if frame["gliding"]:
            continue
        if frame["at"] is None:
            gone += 1
            continue
        off, furthest = stray(start, frame["at"], place.travel, stands, furthest)
        painted = max(painted, off)
    moved = end[1] - start[1] if end else None
    sideways = end[0] - start[0] if end else None
    marks = {
        name: at and [at[0] - start[0], at[1] - start[1]]
        for name, at in reading["marks"].items()
    }
    for name, value in {
        "moved": moved,
        "sideways": sideways,
        "painted": painted,
        "gone": gone,
        "allowed": allowed or 0,
        "scrolled": reading["scrolled"],
        "grew": reading["grew"],
    }.items():
        record_property(name, value if value is None else round(value, 1))
    for name, mark in marks.items():
        record_property(name, mark and [round(d, 1) for d in mark])
    for name, note in built.notes.items():
        record_property(name, note)
    if place.during:
        record_property("scroll at release", reading["release"])
        record_property("scrolled at growth", reading["atGrowth"])

    # A case that means the change to draw mid-scroll released the read while the
    # scroll was under way, and the change drew before the scroll ended, or the case
    # measured something else.
    if midway(page, place):
        assert reading["release"] == "under way", (
            "the scroll had ended before the page's read of the change could go; "
            f"it stood at {[round(at) for at in reading['scrolls']]}px at its scroll events"
        )
        progress = reading["atGrowth"]
        assert progress is not None and abs(progress) < SCROLL - TOLERANCE, (
            f"the change drew after the scroll ended, at {progress}px of its {SCROLL}"
        )

    if end is None:
        raise Moved("the place's box is gone")
    sideways, moved = end[0] - start[0], end[1] - start[1]
    held(abs(sideways) <= TOLERANCE, f"the place moved {sideways:.1f}px sideways")
    held(
        any(abs(moved - place.travel - stand) <= TOLERANCE for stand in stands),
        f"the place moved {moved:.1f}px, where the user's own act moves it "
        f"{place.travel}px"
        + (f" and the change may move it {allowed:.1f}px" if allowed else ""),
    )
    for name, mark in marks.items():
        held(
            mark is not None and max(map(abs, mark)) <= TOLERANCE,
            f"the place stood {mark} away once {name}",
        )
    held(not gone, f"the place's box was gone from {gone} painted frames")
    held(
        painted <= TOLERANCE,
        f"a painted frame showed the place {painted:.1f}px off "
        + ("its scroll's path" if place.travel else "where it stood"),
    )
