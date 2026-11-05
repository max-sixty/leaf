"""The page holds still under the user's aim (browser/AGENTS.md): wherever the user is,
a change they didn't make leaves what they are reading, pointing at or typing into
where it stood.

The cases are generated from two lists, `PLACES` (where the user is, and the box that
marks it) and `CHANGES` (what arrives), crossed wherever the change can reach the
place: a place names what stands around it (`Place.around`) and a change acts on one
of those (`Change.on`). Each case, in Chromium and in Firefox, puts the user there,
takes the box's top, makes the change, waits for the page to show it and settle, and
reads the box again. Between those readings it reads the box after every frame
renders, so a move the page paints and then takes back fails too.

Where the change's own result is to move the place, its descriptor says by how much:
the user's own scroll (`Place.travel`), a new thread drawn at once above it (what
`Change.make` returns), and the dial's glide, whose landing alone is held
(`Change.glides`). Each case records what it measured (`moved`, `painted` and the
rest) as JUnit properties, so a run's `--junitxml` holds the whole matrix.

The shift watch is off here: these cases measure the guarantee it watches directly, and
a case marked as failing would otherwise fail its teardown a second time."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import live_url, panel_comment
from render_harness import (
    holding,
    leaf_page,
    open_page,
    resized,
    scroll_settled,
    stamp_page,
    told,
    wait_for_revision,
)

from browser.threads import append_agent_reply
from leaf import cli as cli_model
from leaf import data as data_model
from leaf.render_checks import rendered
from leaf_dev.browser import settle
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
    """A served page, its source, and the ids its places and changes act on."""

    url: str
    page_dir: Path
    source: str
    ids: dict = field(default_factory=dict)
    revision: int = 1


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
    + paragraphs(60, 30),
)


def thread_page(serve):
    """Two plans of seats between screens of paragraphs. In the first, `upper` holds a
    thread of one message, `fresh` none, and `jobs` a short thread the user works in,
    whose agent messages `early` and `linked` stand among the user's; in the second,
    `notes` holds a long one whose agent message `read` (a short paragraph, then a long
    one) stands a screen above its reply box. A user's comment on paragraph 31 puts a
    pin in the margin."""
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
    ids = {"upper": upper, "jobs": jobs, "notes": notes}
    ids |= {"early": early, "linked": linked, "read": read}
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
    + paragraphs(6, 20),
)


def diff_page(serve):
    url = serve(DIFF_PAGE)
    data_model.cmd_data_set(serve.page_dir, "review-patch", diff_rows(0))
    return Built(live_url(url), serve.page_dir, DIFF_PAGE)


def dial_page(serve):
    """The detail example's incident report, with the words of the cause's first
    paragraph in an `em`, inline text the dial's Skim folds behind the section's
    gist."""
    source = named_source("detail").read_text()
    start = source.index('<p id="detail-cause-1">') + len('<p id="detail-cause-1">')
    end = source.index("</p>", start)
    source = f"{source[:start]}<em>{source[start:end]}</em>{source[end:]}"
    return Built(serve(source), serve.page_dir, source)


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


PAGES = {
    "thread": thread_page,
    "map": map_page,
    "diff": diff_page,
    "dial": dial_page,
    "pane": pane_page,
    "queue": queue_page,
}

# ---------------------------------------------------------------------------------
# Where the user is.


@dataclass(frozen=True)
class Place:
    """Where the user is: the page it stands on, how a user gets there (`put`), the box
    that marks it, as a page function that finds it afresh at each reading (`box`), and
    what stands around it that a change can grow (`around`, a role to its target).

    `during` is the user's own act, a scroll, under way as the change arrives, and
    `travel` how far it moves the box."""

    name: str
    page: str
    put: Callable
    box: "Found | str"
    around: dict
    travel: float = 0
    during: Callable | None = None


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


def smooth(page):
    """A scroll that glides, as a key's or a landing's does."""
    page.evaluate("by => scrollBy({top: by, behavior: 'smooth'})", SCROLL)


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


def put_gutter_focus(page, built):
    to_gutter(page).focus()
    page.mouse.move(*ASIDE)


def put_gutter_pointer(page, built):
    """The pointer resting on a line's Comment, in the diff's open shadow root."""
    comment = to_gutter(page)
    page.locator(GUTTER).first.locator("xpath=..").hover()
    comment.hover()


# That Comment, found inside the diff's shadow root.
GUTTER_COMMENT = f"""() => {{
  const deep = (root) => root.querySelector({json.dumps(GUTTER)})
    ?? [...root.querySelectorAll('*')].map(n => n.shadowRoot && deep(n.shadowRoot))
      .find(Boolean) ?? null;
  return deep(document)?.parentElement.querySelector({json.dumps(COMMENT)}) ?? null;
}}"""


def put_dial(motion):
    def put(page, built):
        page.emulate_media(reduced_motion=motion)
        scroll_to(page, "#detail-cause-1", 900 * 0.25 - 10)

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
    """On me open in the panel, its list scrolled past its first rows, the user on a
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
          throw new Error('On me does not scroll');
        }"""
    )
    row = rows.filter(has_text="Ask 6:")
    row.focus()
    expect(row).to_be_in_viewport()
    page.mouse.move(*ASIDE)


PLACES = [
    Place(
        "typing",
        "thread",
        type_in_reply,
        Found(reply_box("jobs")),
        {
            "thread above": "jobs",
            "message above": "early",
            "seat above": "fresh",
            "page above": None,
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
            "page above": None,
        },
    ),
    Place(
        "reading-page",
        "thread",
        put_reading_page,
        Found("#p-40"),
        {"thread above": "jobs", "page above": None, "on screen above": None},
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
        during=smooth,
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
    Place(
        "shadow-pointer", "diff", put_gutter_pointer, GUTTER_COMMENT, {"lines above": 5}
    ),
    Place("dial", "dial", put_dial("no-preference"), DIAL_READING, {"dial": None}),
    Place("dial-reduced", "dial", put_dial("reduce"), DIAL_READING, {"dial": None}),
    Place("pane", "pane", put_pane, Found("#q-30"), {"pane above": "left-body"}),
    Place(
        "on-me-row",
        "queue",
        put_on_me_row,
        Found(".lf-fp-on-item", "Ask 6:"),
        {"ask above": "ask-0"},
    ),
]

# ---------------------------------------------------------------------------------
# What changes.


@dataclass(frozen=True)
class Change:
    """What arrives: the role around a place it acts on (`on`), and how it is made and
    seen to have arrived (`make`, given the page, the built page, the role's target and
    the place). `make` returns how far the change's own result may move the place, if
    it may.

    A change that `glides` is the user's own, whose result moves what it replaces with
    motion the eye can follow (browser/AGENTS.md, "Controls stay where the user aims"),
    so only where it lands is held to the place."""

    name: str
    on: str
    make: Callable
    glides: bool = False


# Where the document's scroll stood when the change first grew it, which says whether
# the user's scroll was still under way.
SCROLL_AT_GROWTH = """() => {
  const page = document.scrollingElement;
  const record = window.__lfPlaceRecord;
  const observer = new MutationObserver(() => {
    if (page.scrollHeight === record.height) return;
    record.scrollAtGrowth = page.scrollTop;
    observer.disconnect();
  });
  observer.observe(document.body, {childList: true, subtree: true, characterData: true});
}"""


def arriving(page, place, write, drawn):
    """Write a change behind the page and wait until the page shows it.

    Where the user scrolls, the scroll starts while the server holds the page's read of
    the change, and the read goes once the scroll has begun to move, so the page takes
    the change in while the scroll is under way. Chromium's headless shell finishes a
    wheel or smooth scroll at once, so there the change lands on a finished scroll."""
    if place.during:
        held = []

        def hold(route):
            held.append(route)

        page.route("**/api/state*", hold)
        write()
        holding(page, held, 1, "the page's read of the change")
        page.evaluate(SCROLL_AT_GROWTH)
        place.during(page)
        page.wait_for_function(
            "() => document.scrollingElement.scrollTop !== window.__lfPlaceRecord.scroll"
        )
        page.unroute("**/api/state*", hold)
        for route in held:
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
                  return thread.querySelectorAll('.lf-msg').length > count
                    || thread.querySelector('.lf-thread-news');
                }""",
                arg=[selector, count],
            ),
        )

    return make


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
    """The agent asks on the page's opening part, whose row joins On me's head, above
    the rows in sight."""
    asked = ["--section", target, "--obligation", "--text", "One more ask?"]
    arriving(
        page,
        place,
        lambda: leaf("thread", "create", built.page_dir, *asked),
        lambda: expect(page.locator(".lf-fp-on-item")).to_have_count(ASKS + 1),
    )


def revised(page, built, place, html, added):
    """Publish `html` as the page's next revision, and wait until the page shows
    `added`."""
    built.revision += 1
    revision = built.revision
    arriving(
        page,
        place,
        lambda: stamp_page(built.page_dir, html, f"Revision {revision}"),
        lambda: (
            wait_for_revision(page, revision),
            expect(page.locator(added)).to_be_attached(),
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


def turn(page, label):
    """Press a depth with the pointer, as the reader does, and wait out its glide."""
    depth = page.locator("lf-dial .lf-dial-depth", has_text=label)
    box = depth.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    expect(depth).to_have_attribute("aria-pressed", "true")
    page.wait_for_function("() => document.getAnimations().length === 0")


def dial_turn(page, built, target, place):
    """Skim, which folds the paragraph read behind its section's gist, then Read."""
    turn(page, "Skim")
    expect(page.locator("#detail-cause-1")).to_be_hidden()
    settle(page)
    checkpoint(page, "skimmed")
    turn(page, "Read")
    expect(page.locator("#detail-cause-1")).to_be_visible()


CHANGES = [
    Change("reply-above", "thread above", reply("above")),
    Change("reply-below", "thread below", reply("below")),
    Change("edit-above", "message above", edit),
    Change("edit-paragraph", "paragraph above", edit),
    Change("revision-above", "page above", revision_above_window),
    Change("revision-on-screen", "on screen above", revision_on_screen),
    Change("revision-in-pane", "pane above", revision_in_pane),
    Change("seat-thread", "seat above", new_thread),
    Change("map-thread", "map row above", new_thread),
    Change("map-entry", "contribution above", contribution),
    Change("ask", "ask above", ask),
    Change("deletions", "lines above", deletions),
    Change("dial-turn", "dial", dial_turn, glides=True),
]

# ---------------------------------------------------------------------------------
# The measure.

# Read the place's box once after each frame renders, from before the change until the
# page settles: a task posted from a frame callback runs once that frame has rendered.
# Beside it, where the document's scroll and height stood, which says whether the
# change reached the page at all.
ARM = """() => {
  const frame = requestAnimationFrame.bind(window);
  const top = () => {
    const node = window.__lfPlaceBox();
    if (!node || (node instanceof Node && !node.isConnected)) return null;
    const box = node instanceof Range ? node.getClientRects()[0]
      : node.getBoundingClientRect();
    return box && (box.width || box.height) ? box.top : null;
  };
  const page = document.scrollingElement;
  const record = window.__lfPlaceRecord = {
    start: top(), frames: [], marks: {}, top,
    scroll: page.scrollTop, height: page.scrollHeight,
  };
  if (record.start === null) throw new Error('the place has no box to read');
  const next = () => frame(() => {
    const {port1, port2} = new MessageChannel();
    port1.onmessage = () => {
      if (record.done) return;
      record.frames.push(top());
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
  return {start: record.start, end: record.top(), frames: record.frames,
          marks: record.marks, scrolled: page.scrollTop - record.scroll,
          grew: page.scrollHeight - record.height,
          scrolledAtGrowth: record.scrollAtGrowth === undefined ? null
            : record.scrollAtGrowth - record.scroll};
}"""


def checkpoint(page, name):
    """Read the place's box now, under `name`, for a change that passes through a
    state of its own on its way, as the dial's fold does before it unfolds again."""
    page.evaluate(
        "name => { const r = window.__lfPlaceRecord; r.marks[name] = r.top(); }", name
    )


ENGINES = {"browser": "chromium", "firefox_browser": "firefox"}

REPLY_BELOW = "the message clicked scrolls 195px up as the answer joins below it"
REVISION_LANDING = "the revision's landing moves the message clicked 96px up"
EDIT_PARAGRAPH = (
    "the paragraph read moves 84px down as the edit grows the one above it, the "
    "reply box focused off screen"
)
ON_SCREEN = "the paragraph read moves 67.4px down under the paragraph the revision adds"
DELETIONS = "the diff's Comment moves 100px down as five deletions join above it"

# The cases the runtime fails today, with what each measured: a fix flips one to a
# pass, and its strict mark then fails until its entry goes.
MOVES_ON_MAIN = {
    "message-reply-below-chromium": REPLY_BELOW,
    "message-reply-below-firefox": REPLY_BELOW,
    "message-revision-above-chromium": REVISION_LANDING,
    "message-revision-above-firefox": REVISION_LANDING,
    "reading-edit-paragraph-chromium": EDIT_PARAGRAPH,
    "reading-edit-paragraph-firefox": EDIT_PARAGRAPH,
    "reading-page-revision-on-screen-chromium": ON_SCREEN,
    "reading-page-revision-on-screen-firefox": ON_SCREEN,
    "smooth-reply-above-firefox": (
        "drawing the answer stops the smooth scroll under way: the box moves 2-16px "
        "of its 300, by how far the scroll had come"
    ),
    "smooth-revision-above-firefox": (
        "the revision's landing stops the smooth scroll under way: the box moves "
        "12-43px of its 300, by how far the scroll had come"
    ),
    "gutter-deletions-chromium": DELETIONS,
    "gutter-deletions-firefox": DELETIONS,
    "shadow-pointer-deletions-chromium": DELETIONS,
    "shadow-pointer-deletions-firefox": DELETIONS,
    "dial-dial-turn-firefox": (
        "Firefox's anchoring follows the gliding blocks: Skim lands the gist 360.7px "
        "below the line read, and Read moves it 708.6px in all"
    ),
}


def cases():
    for place in PLACES:
        for change in CHANGES:
            if change.on not in place.around:
                continue
            for fixture, engine in ENGINES.items():
                case = f"{place.name}-{change.name}-{engine}"
                reason = MOVES_ON_MAIN.get(case)
                marks = (
                    [pytest.mark.xfail(strict=True, reason=reason)] if reason else []
                )
                yield pytest.param(place, change, fixture, marks=marks, id=case)


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
    assert end is not None, "the place's box is gone"
    stands = [0, allowed] if allowed else [0]
    moved = end - start
    painted = max(
        (
            min(abs(top - start - stand) for stand in stands)
            for top in reading["frames"]
            if top is not None
        ),
        default=0,
    )
    marks = {name: top - start for name, top in reading["marks"].items()}
    for name, value in {
        "moved": moved,
        "painted": painted,
        "allowed": allowed or 0,
        "scrolled": reading["scrolled"],
        "grew": reading["grew"],
        **marks,
    }.items():
        record_property(name, round(value, 1))
    if place.during:
        record_property("scrolled at growth", reading["scrolledAtGrowth"])

    assert any(
        moved == pytest.approx(place.travel + stand, abs=TOLERANCE) for stand in stands
    ), (
        f"the place moved {moved:.1f}px, where the user's own act moves it "
        f"{place.travel}px"
        + (f" and the change may move it {allowed:.1f}px" if allowed else "")
    )
    for name, mark in marks.items():
        assert mark == pytest.approx(0, abs=TOLERANCE), (
            f"the place stood {mark:.1f}px away once {name}"
        )
    glided = change.glides and not page.evaluate(
        "matchMedia('(prefers-reduced-motion: reduce)').matches"
    )
    if not place.travel and not glided:
        assert painted <= TOLERANCE, (
            f"a painted frame showed the place {painted:.1f}px away"
        )
