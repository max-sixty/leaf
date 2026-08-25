"""Shared fixtures and assertions for the browser integration modules.

check is static — it parses the file and validates the vocabulary. Everything
downstream of that (a widget's upgrade, the theme's CSS, the runtime's injected
chrome) meets for the first time in the browser, and the failures that live
there are invisible to a linter. This suite drives the shipped examples through
Playwright's pinned Chromium headless shell and asserts the handful of things
that were each, at some point, wrong:

  - a widget that upgrades into a box of no size (lf-tabs marked itself with a
    class the runtime's chrome had already claimed for its visually-hidden live
    region, so every tabbed page rendered blank below the lede);
  - the document and the comment panel scrolling in one region, which stacks two
    scrollbars in the same few pixels at the window's right edge;
  - a text box sized by script, which had to shrink itself to re-measure and so
    flashed a scrollbar on every keystroke;
  - the passage under the open composer going unmarked, because focusing the box
    drops the browser's own selection and nothing drew it back.

One journey test walks the loop the product is — select a passage, comment on
it, drag a card, follow the next version, and find the comment still anchored —
and asserts the event log those gestures leave behind. The log is the trail
Claude actually reads, so it is the artifact worth pinning; the DOM along the
way is checked only where a step depends on it.

Playwright's default Chromium launch selects its separate headless shell. The
matching build is installed once with `playwright install chromium --only-shell`.
"""

import fcntl
import hashlib
import io
import itertools
import json
import math
import os
import shutil
import struct
import threading
import time
import zlib
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from axe_playwright_python.sync_playwright import Axe
from click.testing import CliRunner
from conftest import interact
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect

pytestmark = pytest.mark.nightly

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.html"))
assert EXAMPLES, "no examples found — parametrizing over an empty list tests nothing"
# The bytes an example names but cannot hold: a lf-shot's pair, content-addressed
# exactly as `leaf page media` names it in a real page directory. examples/CLAUDE.md
# lists every publisher that has to lay this beside the markup, this one among them.
EXAMPLE_MEDIA = Path(__file__).parent.parent / "examples" / "media"


def leaf_page(title: str, body: str, *, head: str = "") -> str:
    """A complete page carrying the presentation boundary every fixture shares."""
    extra_head = f"{head}\n" if head else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta http-equiv="Content-Security-Policy" content="{interact.PAGE_CSP}">
<link rel="stylesheet" href="/theme.css">
{extra_head}<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>{body}</main>
</body>
</html>
"""


# A long page, so the document scrolls, and nothing else — the panel is the subject.
LONG_PAGE = leaf_page(
    "long",
    """
<h1 id="t">Long</h1>
{paras}
""",
).format(
    paras="\n".join(
        f"<p id='p{i}'>Paragraph {i}. " + "Filler. " * 20 + "</p>" for i in range(60)
    )
)

# A passage is quotable only in the form the page itself holds. The shapes the shipped
# examples already carry are swept by test_every_passage_in_a_real_page_can_be_quoted;
# what this fixture is for is the ones they don't have — inline markup (several text nodes
# to one selection), a widget whose body the runtime's own chrome sits inside, adjacent
# blocks (a selection across them reads as one line to the browser and as none to the
# source), a compound the page writes both ways, and a character straddling the quote cap.
INLINE_PAGE = leaf_page(
    "inline",
    """
<h1 id="t">Inline</h1>
<lf-options id="opts" choose>
  <lf-option id="opt-a"><strong>Keep the store</strong> Sessions stay where they are,
  which costs a replica and buys revocation for free.</lf-option>
  <lf-option id="opt-b"><strong>Signed tokens</strong> No store at all, until revocation
  quietly puts one back.</lf-option>
</lf-options>
<p id="p">A paragraph carrying <strong>bold text</strong> and <em>emphasis</em> inside it,
so that a selection across the middle of it lands in more than one text node.</p>
<p id="p2">A neighbouring block, so a selection reaching across the boundary between
them has a break in what the reader sees and none in what the document holds.</p>
<p id="compound">The setup is in the runbook and the rollback is one flag. When the
shadow index is ready we set up the comparison job and roll back the old one.</p>
<p id="cap">{long}&#128512;</p>
{filler}
<p id="q">A passage far enough down the page that a composer opened on it leaves the
first paragraph uncovered, which is what lets a test click a highlight up there.</p>
<figure id="fig"><svg viewBox="0 0 120 40" width="120" height="40" role="img"
aria-label="specimen"><rect x="2" y="2" width="116" height="36" fill="none"
stroke="currentColor"></rect></svg><figcaption>A specimen, for element anchors.</figcaption></figure>
""",
).format(
    filler="\n".join(
        f"<p id='f{i}'>Filler {i}. " + "Words. " * 20 + "</p>" for i in range(6)
    ),
    # Exactly 399 characters before the emoji, so the 400-character cap falls between its
    # two UTF-16 halves — the boundary a naive slice cuts a character in two at.
    long=("Capped. " * 50)[:399],
)

# A decision already made and acted on, with the alternatives kept for the record.
SETTLED_PAGE = leaf_page(
    "settled",
    """
<h1 id="h">Session transport</h1>
<p id="lede">Decided last week; open the row for the alternatives.</p>
<lf-options id="transport" choose settled>
  <lf-option id="opt-lax" chosen><strong>Lax cookie</strong> Host-only, set by the auth
  origin, nothing for a script to read.</lf-option>
  <lf-option id="opt-strict"><strong>Strict cookie</strong> Tighter, but a session
  started from an emailed link arrives logged out.</lf-option>
  <lf-option id="opt-bearer"><strong>Bearer header</strong> Suits the mobile client;
  puts the id where every script can read it.</lf-option>
</lf-options>
""",
)


# A decision the page reports rather than offers: no `choose`, so there is nothing to
# press, and the mark the upgrade puts on the carried option is the page saying which
# one the document holds. The paragraph above it is the control — a passage nobody has
# ever doubted was quotable.
CARRIED_PAGE = leaf_page(
    "carried",
    """
<h1 id="h">Session transport</h1>
<p id="lede">Where the decision stands, for the record.</p>
<lf-options id="carried">
  <lf-option id="c-lax" chosen><strong>Lax cookie</strong> Host-only, set by the auth
  origin, nothing for a script to read.</lf-option>
  <lf-option id="c-bearer"><strong>Bearer header</strong> Suits the mobile client;
  puts the id where every script can read it.</lf-option>
</lf-options>
""",
)


# The words a widget renders from an attribute — a column's heading, a metric's number —
# with room around them, so a drag across one is an ordinary drag and not a two-pixel
# feat. Both column labels differ, so a quote can only anchor where it was picked.
SAID_PAGE = leaf_page(
    "said",
    """
<h1 id="h">This week</h1>
<lf-metrics id="numbers">
  <lf-metric id="m-open" value="1,204" delta="+18%" direction="up-good">Open sessions</lf-metric>
</lf-metrics>
<lf-board id="board">
  <lf-column id="col-now" label="In flight">
    <lf-card id="c-importer"><strong>Wire the importer</strong> Half done.</lf-card>
  </lf-column>
  <lf-column id="col-next" label="Queued">
    <lf-card id="c-backfill"><strong>Backfill the index</strong> Waiting on the importer.</lf-card>
  </lf-column>
</lf-board>
""",
)


# Short card titles, so the whole board fits in an expected ARIA snapshot and the
# snapshot stays about structure. One column starts empty: a keyboard user has to
# hear it to move a card into it.
BOARD_PAGE = leaf_page(
    "board",
    """
<h1 id="h">Sprint</h1>
<lf-board id="sprint">
  <lf-column id="col-todo" label="Todo">
    <lf-card id="card-heater"><strong>Heated perch</strong></lf-card>
    <lf-card id="card-baffle"><strong>Squirrel baffle</strong></lf-card>
  </lf-column>
  <lf-column id="col-done" label="Done"></lf-column>
</lf-board>
""",
)


# Exhibited widgets beside live ones, so a missing affordance can be pinned on the
# quoting rather than on a broken upgrade. Both forms of a question are quoted, because
# the card's answer to the pointer is a lift and the row's is a wash — two rules keyed on
# the form, and a corpus holding only quoted cards leaves the row's pair matching nothing
# anywhere.
SPECIMEN_PAGE = leaf_page(
    "specimen",
    """
<h1 id="h">What a decision looks like</h1>
<lf-specimen id="spec" label="a decision">
  <lf-options id="quoted-group" choose>
    <lf-option id="q-shim"><strong>Shim the old schema</strong> Fastest to ship.</lf-option>
    <lf-option id="q-stage" recommended><strong>Migrate in stages</strong> Table by table.</lf-option>
  </lf-options>
  <lf-board id="quoted-board">
    <lf-column id="q-col" label="Doing">
      <lf-card id="q-card"><strong>Wire the importer</strong></lf-card>
    </lf-column>
    <lf-column id="q-col-next" label="Next">
      <lf-card id="q-card-backfill"><strong>Backfill last month</strong></lf-card>
    </lf-column>
    <lf-column id="q-col-done" label="Done">
      <lf-card id="q-card-tokens"><strong>Tokenize the palette</strong></lf-card>
    </lf-column>
  </lf-board>
  <lf-options id="quoted-rows" choose>
    <lf-option id="q-row-keep">Keep the nightly job</lf-option>
    <lf-option id="q-row-drop">Drop it and poll on demand</lf-option>
  </lf-options>
  <lf-options id="quoted-settled" choose settled>
    <lf-option id="q-lax" chosen><strong>Lax cookie</strong> Host-only.</lf-option>
    <lf-option id="q-bearer"><strong>Bearer header</strong> Suits mobile.</lf-option>
    <lf-option id="q-signed" recommended><strong>Signed token</strong> No store.</lf-option>
  </lf-options>
  <p id="q-prose">Refill rules:
    <lf-suggestion id="quoted-suggestion">
      <lf-old>Refill every feeder each morning.</lf-old>
      <lf-new>Refill when the camera shows it half-empty.</lf-new>
    </lf-suggestion></p>
</lf-specimen>
<lf-options id="live-group" choose>
  <lf-option id="l-shim"><strong>Shim the old schema</strong> Fastest to ship.</lf-option>
  <lf-option id="l-stage" recommended><strong>Migrate in stages</strong> Table by table.</lf-option>
</lf-options>
<lf-options id="live-rows" choose>
  <lf-option id="l-row-keep">Keep the nightly job</lf-option>
  <lf-option id="l-row-drop">Drop it and poll on demand</lf-option>
</lf-options>
<lf-options id="live-settled" choose settled>
  <lf-option id="l-lax" chosen><strong>Lax cookie</strong> Host-only.</lf-option>
  <lf-option id="l-bearer"><strong>Bearer header</strong> Suits mobile.</lf-option>
  <lf-option id="l-signed" recommended><strong>Signed token</strong> No store.</lf-option>
</lf-options>
<lf-board id="live-board">
  <lf-column id="l-col" label="Doing">
    <lf-card id="l-card"><strong>Wire the importer</strong></lf-card>
  </lf-column>
</lf-board>
<p id="l-prose">Refill rules:
  <lf-suggestion id="live-suggestion">
    <lf-old>Refill every feeder each morning.</lf-old>
    <lf-new>Refill when the camera shows it half-empty.</lf-new>
  </lf-suggestion></p>
""",
)


# A page with nothing to decide: the widgets under test arrive in the panel, on a
# reply, which is the other place markup renders.
REPLY_HOST_PAGE = leaf_page(
    "reply",
    """
<h1 id="h">Session store</h1>
<p id="intro">Redis, with a signed-cookie fallback for reads.</p>
""",
)

# Claude answering with a question to put and, beside it, the framing that question
# replaced — quoted, so the reply asks one thing rather than two. The words ride
# `text` and the widgets ride `markup`, as `leaf reply` writes them.
SPECIMEN_TEXT = (
    "Two shapes for the same question — first the one I'd ship, then, for the "
    "record, the framing it replaces:"
)
SPECIMEN_MARKUP = """<lf-options id="rp-live" choose>
  <lf-option id="rp-shim"><strong>Shim the old schema</strong> Fastest to ship.</lf-option>
  <lf-option id="rp-stage" recommended><strong>Migrate in stages</strong> Table by table.</lf-option>
</lf-options>
<lf-specimen id="rp-spec" label="the April thread">
  <lf-options id="rp-quoted" choose>
    <lf-option id="rp-memory"><strong>App memory</strong> Nothing to build.</lf-option>
    <lf-option id="rp-sticky"><strong>Sticky sessions</strong> Until an instance recycles.</lf-option>
  </lf-options>
</lf-specimen>
"""

# Two decisions for a user to take and a later version to honor, carry, or
# contradict: a pick and a move.
IMPORTER_CARD = (
    '<lf-card id="card-importer"><strong>Wire the importer</strong></lf-card>'
)
REPLAYED_PAGE = leaf_page(
    "replayed",
    f"""
<h1 id="t">Rollout</h1>
<lf-options id="approach" choose>
  <lf-option id="opt-shim"><strong>Shim the old schema</strong> Fastest to ship.</lf-option>
  <lf-option id="opt-stage"><strong>Migrate in stages</strong> Table by table.</lf-option>
</lf-options>
<lf-board id="work">
  <lf-column id="col-doing" label="Doing">{IMPORTER_CARD}</lf-column>
  <lf-column id="col-done" label="Done"><lf-card id="card-notes"><strong>Draft the notes</strong></lf-card></lf-column>
</lf-board>
""",
)


# A page's key is minted per page; fixed here so a test can build a URL for a
# server it did not start.
TOKEN = "test-page-key"


def record_claim(page, **fields):
    record = {
        "page": str(page.resolve()),
        "id": "s",
        "host": "claude-code",
        "pid": os.getpid(),
        "agent": "Claude",
        "cwd": str(Path.cwd()),
        "ts": "t",
        "released": None,
        "turn_closed": None,
        **fields,
    }
    path = interact.claim_path(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    interact.write_json(path, record)
    return record


@pytest.fixture
def serve(tmp_path, monkeypatch):
    """Publish HTML as v1 of a fresh page directory and serve it, as the real
    server does — vendoring included, so the assets under test are this repo's.

    Handed an example's path rather than its markup, it also lays in the two
    things that example ships beside itself: the media it names, and the event
    log, where it has one. The log for the same reason `test_examples_pass_check`
    reads one — a page is what its markup and its standing log make together, and
    a corpus that reads only the markup is reading half of it. A thread and any
    widget a message carries exist nowhere else, so without this every sweep is
    green over a page the reader never gets.

    Each call gets its own directory, reached through `serve.page_dir`. Sharing one
    meant a test that serves two examples in a single body re-initialised over the
    first and appended the second's events to a log already holding the first's,
    which reads as a page rather than failing."""

    def go(source, comments=0, anchored=()):
        monkeypatch.chdir(tmp_path)  # keep the project layer out of the overlay
        example = source if isinstance(source, Path) else None
        d = tmp_path / f"page{len(servers)}"
        assert CliRunner().invoke(interact.cli, ["page", "init", str(d)]).exit_code == 0
        (d / "versions" / "v1.html").write_text(
            example.read_text() if example else source
        )
        shutil.copytree(EXAMPLE_MEDIA, d / "media", dirs_exist_ok=True)
        interact.append_event(
            d, {"kind": "note", "author": "claude", "version": 1, "text": "t"}
        )
        # After the note, so v1's announcement stays the log's first line and the
        # exchange reads in the order it happened, which is preview.py's ordering.
        # (The site build writes the seed alone and announces its versions
        # elsewhere, so it has no note to come after.) Split on the writer's own
        # separator, never splitlines(), whose wider class reads a U+2028 inside a
        # comment's text as a break.
        if example and (seed := example.with_suffix(".jsonl")).exists():
            for line in seed.read_text(encoding="utf-8").split("\n"):
                if line.strip():
                    interact.append_event(d, json.loads(line))
            # A seed is history rather than news, so the page opens acknowledged
            # through it — the state every other publisher of a seeded example
            # serves. Left at nought the banner tells the reader their own comment
            # is queued for somebody, which is an arrival regression this corpus
            # would have manufactured for itself. Read back for the seq rather than
            # counted, because a seq is what the log's reader assigns and an append
            # hands back no such number.
            interact.write_json(
                d / "cursor.json", {"seq": interact.read_events(d)[-1]["seq"]}
            )
        for i in range(comments):
            interact.append_event(
                d,
                {
                    "kind": "comment",
                    "author": "user",
                    "version": 1,
                    "text": f"Comment {i}. " + "Long enough to wrap. " * 4,
                },
            )
        for section, quote in anchored:
            interact.append_event(
                d,
                {
                    "kind": "comment",
                    "author": "user",
                    "version": 1,
                    "text": "About this bit.",
                    "anchor": {"section": section, "quote": quote},
                },
            )
        httpd = interact.LeafHTTPServer(
            ("127.0.0.1", 0), interact.handler_for(d, TOKEN)
        )
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        servers.append(httpd)
        go.httpd = httpd
        go.servers = servers
        go.page_dir = d  # for tests that publish a v2 or read the event log
        # The key rides in the URL exactly as it does in a handover, so the first
        # navigation of each browser context earns the cookie the rest of the
        # page's own fetches go out under.
        return f"http://127.0.0.1:{httpd.server_address[1]}/versions/v1.html?t={TOKEN}"

    servers = []
    yield go
    for httpd in servers:
        httpd.shutdown()


def page_registry(page):
    """The registry this page was served, read the way the render gate reads it.

    The readings `render_version` runs are handed their registry rather than fetching
    one, so a test driving one directly supplies the same thing from the same place —
    the page's own server, not this repo's tree, since what a vendored page holds is
    the whole question those readings answer.
    """
    return interact.served(page, page.url, "/registry.json").json()


def post_event(page, url, **kwargs):
    """An event arriving from another tab running this page's current layer."""
    generation = page_registry(page)["$layer"]["generation"]
    return page.request.post(url, headers={"Leaf-Layer": generation}, **kwargs)


# What the page has sent and how much of it has come back, counted where the traffic is:
# outside the page, on the browser's own request and response events. The runtime posts
# every action and comment through fetch and reads state back the same way, so one watcher
# sees both halves and no widget has to say anything.
#
# Outside, because a test has no business inside the thing it is testing. This counted the
# same five numbers by wrapping `window.fetch` in an init script, on every page of every
# run and behind no flag — permanent surgery on the runtime under test, to learn what the
# browser was already willing to say. These events are that willingness, and the suite
# already reaches for their other half wherever it needs a request stopped (`page.route`),
# so the wrapper was a hand-rolled second copy of a primitive already in use here.
class Traffic:
    """One page's trips to the server, counted as the browser reports them.

    `pending` is keyed by the attempt the runtime sends, not by physical requests. A
    failed request therefore stays pending while the outbox retries it; a definitive
    refusal or a response naming the accepted attempt clears it. This tracks delivery,
    observed outside the page. Whether the page then applied the returned state is a
    separate product fact asserted on the surface that needs it.

    The count is the page's whole life, reloads included, where the init script started
    over at each navigation. Navigation clears unresolved attempts because it destroys
    that page's outbox; later sends still advance the lifetime counters."""

    def __init__(self, page):
        self.sends = 0  # events posted
        self.acked = 0  # posts the server has answered
        self.asked = 0  # state the page has gone out for
        self.heard = 0  # ... and been given
        self.pending = set()  # browser attempt ids with no known delivery outcome
        self._token = {}  # outbox request -> its browser attempt
        self._flying = (
            set()
        )  # event posts in the air, each counted once whichever way it ends
        self._responses = []  # bodies are read outside Playwright's response callback
        page.on("request", self._out)
        page.on("response", self._responded)
        page.on("requestfailed", self._back)
        # A navigation is the third way a trip ends, and the one the browser reports
        # for neither kind: a post the reload kills mid-flight gets no `response` and
        # no `requestfailed`. Left uncounted it holds `acked` under `sends` for the
        # rest of the page's life — the counters are the whole life on purpose — so
        # every later `round_trip` waits its timeout out on a trip that ended at the
        # reload. Accept-all is where this bit: it answers its asks one awaited trip
        # at a time, so a sweep's reload lands mid-cascade about as often as not.
        page.on("framenavigated", self._navigated)

    def _out(self, request):
        if "/api/event" in request.url:
            self.sends += 1
            self._flying.add(request)
            event = request.post_data_json
            token = event.get("attempt") if isinstance(event, dict) else None
            if token:
                self._token[request] = token
                self.pending.add(token)
        elif "/api/state" in request.url:
            self.asked += 1

    def _back(self, request):
        # Counted only while in the air, so a straggling report of a post the
        # navigation already settled can't count it twice.
        if "/api/event" in request.url:
            if request in self._flying:
                self._flying.discard(request)
                self.acked += 1
        elif "/api/state" in request.url:
            self.heard += 1

    def _responded(self, response):
        request = response.request
        self._back(request)
        self._responses.append(response)

    def settle(self):
        """Read queued bodies from ordinary test control flow, never an event callback.

        Playwright may yield while `response.json()` asks its driver for the body. Doing
        that inside `_responded` let the test re-enter between `acked` and `pending`,
        after the response event that could wake it had already fired."""
        while self._responses:
            responses, self._responses = self._responses, []
            for response in responses:
                self._settle(response)

    def _settle(self, response):
        request = response.request
        if "/api/event" in request.url:
            try:
                answer = response.json()
            except Exception:  # noqa: BLE001 - malformed answers are retryable evidence
                return
            token = self._token.get(request)
            state = answer.get("state")
            state_events = state.get("events") if isinstance(state, dict) else None
            state_attempts = (
                {
                    event.get("attempt")
                    for event in state_events
                    if isinstance(event, dict) and event.get("attempt")
                }
                if isinstance(state_events, list)
                else set()
            )
            accepted = answer.get("ok") is True and token in state_attempts
            refused = (
                answer.get("ok") is False
                and answer.get("final") is True
                and ("attempt" not in answer or answer.get("attempt") == token)
            )
            if accepted or refused:
                self.pending.discard(token)
        elif "/api/state" in request.url and response.ok:
            try:
                state = response.json()
            except Exception:  # noqa: BLE001 - it accounted for nothing the page can read
                return
            state_events = state.get("events") if isinstance(state, dict) else None
            if not isinstance(state_events, list):
                return
            attempts = {
                event.get("attempt")
                for event in state_events
                if isinstance(event, dict) and event.get("attempt")
            }
            self.pending.difference_update(attempts)

    def _navigated(self, frame):
        if frame.parent_frame is not None:
            return
        self.acked += len(self._flying)
        self._flying.clear()
        self.pending.clear()
        self._token.clear()
        self._responses.clear()

    def __str__(self):
        return (
            f"sends={self.sends} acked={self.acked} pending={len(self.pending)} "
            f"asked={self.asked} heard={self.heard}"
        )


def _traffic(page):
    """The watcher `open_page` hung on this page when it made it."""
    page.lf_traffic.settle()
    return page.lf_traffic


def _until(page, fact, wanted):
    """Block until `fact` holds of the page's traffic.

    The events the counters are built from arrive while the client is blocked inside a
    Playwright call, so this blocks on each next response and asks again — no polling
    interval to pick, and nothing added to the page. Response bodies are settled only
    after that event returns, so the delivery fact changes atomically from this caller's
    point of view.

    It wakes on responses alone, where the counters answer to failures too, so a fact that
    came true through a failed request waits for the next poll that is answered to be
    noticed. A page with every poll routed to `abort` has no such next, and a wait on one
    runs its timeout out and says so rather than passing.

    A wait that runs out names the caller's wanted fact and prints its starting and final
    counters. No response preserves Playwright's timeout as the cause; a busy response
    stream reaches the same explicit deadline instead of waking this loop forever."""
    if fact(_traffic(page)):
        return
    began = str(_traffic(page))
    deadline = time.monotonic() + 30
    try:
        while not fact(_traffic(page)):
            remaining = int((deadline - time.monotonic()) * 1000)
            if remaining <= 0:
                raise PlaywrightTimeout("responses outlived the wait deadline")
            page.wait_for_event("response", timeout=remaining)
    except PlaywrightTimeout as ran_out:
        raise AssertionError(
            f"the page never {wanted}: the wait began on {began} and gave up on "
            f"{_traffic(page)}"
        ) from ran_out


# A browser trip is over when the response names the accepted attempt, definitively
# refuses it, or a periodic poll observes it after the response was lost. Traffic records
# those delivery outcomes as one fact. It deliberately says nothing about whether the
# runtime then applied the response state; tests assert that on the affected page surface.
# A request failure does not finish delivery, because the outbox keeps the same attempt
# and retries; waiting merely for `acked` would return on that ambiguous edge.
def round_trip(page):
    """Wait for what this page has sent to have come back to it."""
    _until(page, lambda t: not t.pending, "heard back what it sent")


# The other direction of the same trip. Nothing a test writes into the page directory
# announces itself — a declared status, a changed wait lease, an appended event all reach
# the page when its next poll asks — so an assertion made straight after the write is
# waiting out the poll interval on whatever budget expect() happens to carry. Timed, that
# wait takes 1.8 to 2.3 of the default five seconds, and it takes them every time: an
# assertion returns just after a poll lands, leaving the next one a whole interval away.
#
# So the wait is the trip again, watched rather than timed. A poll counted out after the
# write is one that went looking for it, and its answer is the page being told; the
# expect that follows only has to read what arrived.
def told(page):
    """Wait for a poll that goes out from here on to come back."""
    asked = _traffic(page).asked
    _until(page, lambda t: t.heard > asked, "finished a poll that went out from here")


# `z` is the one press whose subject is read rather than pointed at, so the dispatcher
# holds it dead while the page holds a gesture no log read has accounted for — this
# press's own trip included (unrecordedGesture). Every other press acts on what is under
# the reader and can be made the moment the paint is there; the paint arrives a turn
# before the trip it was made on is over, so a `z` made on it is a press the dispatcher
# refuses, and what the refusal leaves behind is the page an assertion on the un-undone
# state would find anyway. A test cannot tell that from an undo that did the wrong thing:
# it reads the no-op as the wrong answer, or waits its budget out and calls it a hang.
#
# So the press waits on the fact the page states rather than on the gesture before it
# having painted. The line and the dispatcher ask one predicate (`live`), so no surface
# can promise a press the dispatcher refuses — which makes the offer standing on the
# line the page saying this press will be taken. Then the trip: the press's own send is
# not counted at the moment it is made, and a `round_trip` that reads the counters
# before the browser has reported the request is a wait on a page that has not started
# moving.
#
# The line answers about room as well as about liveness: renderLine drops chips from the
# end when the window is too narrow to hold them, and the end is the outside of the
# stack, where a page-level key like this one sits. So the wait needs the suite's
# default 1200×900 or something near it; under a viewport set narrow on purpose it would
# run its budget out on a press that is perfectly live.
def undo(page):
    """Take the last gesture back, from the moment the line offers to."""
    expect(page.locator(".lf-keyline")).to_contain_text("undo")
    sent = _traffic(page).sends
    page.keyboard.press("z")
    _until(page, lambda t: t.sends > sent, "put the withdrawal in the wire")
    round_trip(page)


# A poll a test stops is cancelled rather than failed. The page cannot tell the two
# apart — both reject the fetch the runtime awaits and leave it on the same `catch`.
# The console can tell them apart, which is what the reason is chosen for:
# tests/CLAUDE.md, "A test cannot assert over noise it makes itself". A refused event
# request remains unresolved, deliberately: the outbox keeps its attempt and retries.
def refuse(route):
    """Stop this request with nothing for the page's console to report."""
    route.abort("aborted")


# A tab a test holds stale is stale for one poll interval and no longer: every poll
# reconciles the draft store against shared storage before it settles anything
# (settleAcceptedDrafts), so a stale view the assertions take their time reaching is a
# race a loaded runner loses. Refusing the polls states it — but only from before the
# page exists. `page.route` reaches no request already in the wire, and a poll
# reconciles when its response lands rather than when its request went out, so a
# refusal registered on a live page leaves whatever is outstanding free to arrive
# later, against storage the test has moved in the meantime. Registered through
# `primed`, the route is on the page before it navigates and no poll is ever unrouted.
#
# The first is let through because `open_page` waits for the page's readiness facts,
# including `lf-applied`, which rides on it — and that same wait is what leaves nothing
# outstanding when the page is handed over. Where the tab has to hear the log again,
# the test lifts the refusal itself.
class CutOff:
    """A page's polls, stopped from outside it until the test says it can hear again."""

    def __init__(self, lets_through=0):
        self._lets_through = lets_through
        self._live = False

    def hold(self, page):
        seen = itertools.count()
        page.route(
            "**/api/state*",
            lambda route: (
                route.continue_()
                if self._live or next(seen) < self._lets_through
                else refuse(route)
            ),
        )
        return self

    def restore(self):
        self._live = True

    # Preserve the initial-poll count when cutting the page off again.
    def cut(self):
        self._live = False


def held_stale(context):
    """A context whose next page is refused every poll after the one that stamps it."""
    cut = CutOff(lets_through=1)
    stale = primed(context, cut.hold)
    stale.restore = cut.restore
    return stale


# The page's three readiness facts: `lf-upgraded` is the document's — widgets upgraded
# and the anchor pass run — `lf-applied` is the log's, written at the end of every replay
# pass, and `lf-presented` says a deliberately shown waiting surface has completed its
# minimum dwell. Applied state is not yet a completed page while that surface stands.
# The runtime stamps the document in the same breath as it starts that first poll and
# never awaits it, so a page can be done becoming itself while knowing nothing of what
# the reader has decided or which version is newest.
#
# One predicate, because it was spelled out in eleven places and only the one that
# noticed ever grew the second half. `open_page` took it when a loaded Linux runner
# dropped three keypresses into pages with nothing yet to answer them; every navigation a
# test makes for itself kept waiting on the document alone. What that leaves out is not a nicety of
# the log: the version chooser and the live-pages button are drawn from a poll's answer
# and Comments has no count until one lands, so a page at the document's stamp is a page
# whose banner the reader would not recognize.
BOTH_STAMPS = (
    "() => document.body.dataset.lfUpgraded === '1'"
    " && document.body.dataset.lfApplied !== undefined"
    " && document.body.dataset.lfPresented === '1'"
)
STORED_DRAFT_TEXT = """ctx => {
  try {
    const record = JSON.parse(localStorage.getItem('lf-draft:' + ctx));
    return record && !record.settled ? record.text : null;
  } catch { return null; }
}"""
STORED_DRAFT_SETTLED = """ctx => {
  try {
    return JSON.parse(localStorage.getItem('lf-draft:' + ctx))?.settled === true;
  } catch { return false; }
}"""


def watched(page):
    """Everything a page says went wrong, on every channel that carries it.

    `pageerror` is an uncaught exception and the console is what the page itself wrote,
    and between them a whole channel goes unread: an `error` event with no exception
    behind it reaches neither. Chrome reports a ResizeObserver loop that way. A runtime
    change that put the layout writer inside an observation of the box that writer
    resizes made every load report one, and the suite called it clean — 754 tests, no
    console output, nothing on `pageerror`. Routed into the console here, which is the
    one channel every reader in this file already has, and only for the events with no
    exception, since the rest arrive on `pageerror` already.

    The script is `interact.WINDOW_ERRORS`, which `render_version` lays in for the same
    reason: one implementation with two callers is what keeps `version check --render`
    and this suite holding the same invariants, and a channel read on one side only is
    that drift in its quietest form.

    Must be called before the page navigates, the init script being what carries it."""
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script(interact.WINDOW_ERRORS)
    return errors


def navigate(page, errors, url, *, wait_until="networkidle", ready=BOTH_STAMPS):
    """Navigate through a complete page handover, classifying only the
    ResizeObserver notices raised during that navigation.

    A platform notice seen once under load is not a page fault; one repeated by the
    confirming navigation is. Everything else remains in `errors` from the attempt
    that reported it, and anything arriving after this helper returns remains strict.
    """

    def complete_navigation():
        start = len(errors)
        page.goto(url, wait_until=wait_until)
        page.wait_for_function(ready)
        # Let the rendering turn that earned the readiness stamp finish. A loop
        # notice is delivered by that turn, rather than by the DOM write alone.
        page.evaluate("() => new Promise(requestAnimationFrame)")
        fresh = errors[start:]
        del errors[start:]
        notices = [error for error in fresh if interact.resize_observer_error(error)]
        errors.extend(
            error for error in fresh if not interact.resize_observer_error(error)
        )
        return notices

    notices = complete_navigation()
    if not notices:
        return
    try:
        confirming_notices = complete_navigation()
    except Exception:
        errors.extend(notice for notice in notices if notice not in errors)
        raise
    if confirming_notices:
        errors.append(interact.recurring_resize_observer_error("navigation"))


def open_page(
    browser,
    url,
    *,
    pin=False,
    init_script=None,
    wait_until="load",
    context=None,
    upgraded=True,
):
    """A page with its console errors collected and its document and log state applied.

    `pin` asks for the version the URL names rather than the newest, and is a keyword
    because the URL a handover carries already has a query holding the page's key: a
    test appending its own `?pin` overwrote that key and got a page that never loaded.

    `upgraded` takes the page's three readiness facts for having finished, `BOTH_STAMPS`
    above saying what each answers. Twenty-two tests stood on the first pair the day it
    was written here, and a dockerised Linux runner had named three.

    Navigation waits for `load`, so the stylesheet and media that determine layout have
    arrived. Network silence is not a readiness fact; the stamps state that the document
    and its log finished applying.

    False is for the one test whose subject is the interval between them, which holds the
    registry fetch open and so never earns either. It waits on the banner instead, which
    says only that the runtime's module evaluated — long before the anchor pass has run,
    and so before the Comment button can answer a selection at all. A test that reads
    there without an auto-retrying wait is racing the upgrade and loses on a loaded
    machine: the passage sweep lost it on the gallery, the heaviest page here, and what
    it reported was a passage it had not tested rather than one that failed."""
    page = (
        context.new_page()
        if context
        else browser.new_page(
            viewport={"width": 1200, "height": 900}, color_scheme="light"
        )
    )
    # Before the first navigation, so the count is of everything this page ever asked for.
    page.lf_traffic = Traffic(page)
    errors = watched(page)
    # The console's own word for a bad response is "Failed to load resource", which
    # names nothing; carry the status and URL so a failure says what went missing.
    page.on(
        "response",
        lambda r: errors.append(f"{r.status} {r.url}") if r.status >= 400 else None,
    )
    if init_script:
        page.add_init_script(init_script)
    if pin:
        url += ("&" if "?" in url else "?") + "pin"
    navigate(
        page,
        errors,
        url,
        wait_until=wait_until,
        ready=(
            BOTH_STAMPS
            if upgraded
            else "() => document.querySelector('.lf-banner') !== null"
        ),
    )
    return page, errors


def primed(browser, prepare):
    """A browser whose pages reach the product with the suite's hands already on them.

    `render_version` and `export_page` open their own pages, so a test can otherwise only
    watch them from outside — on the failure list or the copy they return — and can never
    state the conditions the page meets them under. `new_page` is all either asks of a
    browser, so a stand-in that makes the page, hands it to `prepare`, and returns it
    needs no parameter added to production for a caller that is only ever a test.

    What a test states there is `page.route`, which stops or delays a request from outside
    the page as everything else here now does. Refusing the first `/api/state` is the one
    that has earned its keep: the runtime stamps `lf-upgraded` in the same breath as it
    starts that poll, never awaiting it, so a refusal puts replay on the far side of the
    document's stamp — where a slow machine would have put it — deterministically and in
    a second."""

    def new_page(**kwargs):
        page = browser.new_page(**kwargs)
        prepare(page)
        return page

    return SimpleNamespace(new_page=new_page)


def panel_settled(page, open=True):
    """Wait for the panel to reach `open` and the page to finish making room for it.

    Two things happen, and they don't finish together: the class flips at once and the
    document slides into its new width over about a fifth of a second (syncLayout). A
    geometry read taken on the flip is a read of the page mid-flight — its right edge
    still under the panel, its column still the width it had — so an assertion fed by
    one is about a layout that exists for a sixth of a second and then doesn't.

    Ask the transition itself, via getAnimations(): the call flushes pending style, so
    the transition the class just brought into play is visible to the very first read, a
    finished one has left the list, and a change that runs untransitioned — the
    covering sheet, a pre-stamp load, reduced motion — reports empty and returns at
    once. Waiting a duration instead would encode a number the stylesheet is free to
    change, and still be a guess on a loaded machine; the frame-sampling this replaced
    is the failure CLAUDE.md's wait norm is named for."""
    page.wait_for_function(
        "(open) => document.querySelector('.lf-panel').classList.contains('open') === open",
        arg=open,
    )
    page.wait_for_function("() => document.body.getAnimations().length === 0")


def resized(page, width, height):
    """Resize the window, and wait for the page to have handled it.

    `set_viewport_size` returns once the browser is the new size, which is a fact about
    the browser and not about the page: the page may not have been told yet, so its
    layout — the strip the panel holds, the covering sheet, and with it which region a
    half-page key moves — can still be the old window's. A test that reads layout on
    that frame reads the width it just left, and only on a machine loaded enough to fit
    the read in first, which is the shape of every wait this suite has had to learn
    (`tests/CLAUDE.md`, "A wait consumes a fact the system states").

    The fact the page states here is the event reaching its listeners, counted by one
    added now: the runtime registered its own when it loaded, so this one runs after
    them. The rest of the page's answer lands in the same rendering update — the strip
    the panel holds is the stylesheet's, and syncLayout runs from an observation of the
    box, which Chrome delivers before that update ends — so the whole of it is behind
    us by the time the next command reaches the page at all. What the answer moved is a
    separate question, and a test whose subject is the new layout still waits for the
    piece of it that it is about; a margin easing into place is the ordinary case.

    A window already the size asked for fires nothing, so waiting on it would hang out
    a whole timeout rather than return at once. The sweep that walks each example at
    both a desk's width and a phone's asks for the first of those on a page opened at
    it."""
    if page.viewport_size == {"width": width, "height": height}:
        return
    page.evaluate("""() => {
        if (window.lfResizes === undefined) {
            window.lfResizes = 0;
            addEventListener("resize", () => window.lfResizes++);
        }
        window.lfResizesWas = window.lfResizes;
    }""")
    page.set_viewport_size({"width": width, "height": height})
    page.wait_for_function("() => window.lfResizes > window.lfResizesWas")


def select(page, start, end, steps=8):
    """Drag a selection from one point to another, pressing on a whole pixel.

    A fractional start point loses the selection outright wherever it and its own
    floor fall either side of a glyph's caret boundary: the drag runs, the mouseup
    lands, and `getSelection()` comes back empty. It reads as the widget under the
    pointer refusing the gesture, and it is neither that nor Playwright's
    interpolation — plain prose in a bare document does it, and ten separate moves do
    it identically. Sixty start points along one line came back empty at exactly the
    points where the two disagree, and correct at every other.

    So the press is floored. Where the two agree, which is everywhere a drag works at
    all, that changes nothing; where they disagree it is the whole of the fix. The end
    is passed as given — it is read at the precision it arrives with, and flooring it
    moves the selection a character."""
    page.mouse.move(math.floor(start[0]), math.floor(start[1]))
    page.mouse.down()
    page.mouse.move(end[0], end[1], steps=steps)
    page.mouse.up()


def compare_with(page, version=None):
    """Mark what changed since a version, the way the page offers it.

    The chooser opens and the row for that version carries the press, beside the note
    that says in words what it changed. With no version named it is the one before the
    version being read — the last Δ in the menu, a row offering one only where it is
    older than this."""
    page.locator(".lf-version").click()
    press = (
        page.locator(".lf-version-diff").last
        if version is None
        else page.locator(f'.lf-version-diff[data-lf-version="{version}"]')
    )
    press.click()


CUSTOM_WIDGET_PAGE = leaf_page(
    "custom widget",
    """
<h1 id="title">Project vocabulary</h1>
<lf-callout id="custom-note">
  <strong>Heads up</strong> This widget came from the project layer.
</lf-callout>
""",
)

RESIZE_LOOP_EVENT = """dispatchEvent(new ErrorEvent('error', {
  message: 'ResizeObserver loop completed with undelivered notifications.'
}));"""


def resize_notice_after_last_probe(page):
    """Schedule the notice for the rendering turn after the gate's last probe."""
    evaluate = page.evaluate

    def with_notice(expression, *args, **kwargs):
        result = evaluate(expression, *args, **kwargs)
        if expression == interact.RELATIVE_REPLAYS:
            evaluate("() => requestAnimationFrame(() => {" + RESIZE_LOOP_EVENT + "})")
        return result

    page.evaluate = with_notice


# What a returning reader's browser puts back before the page runs, declared by the
# runtime that puts it back (leaf.js, ARRANGEMENTS). Read from the page rather than
# listed here: which surfaces remember anything is the runtime's to say, and a list on
# this side would stop at the ones it was taught.
ARRANGEMENTS = "() => import('/leaf.js').then((leaf) => leaf.ARRANGEMENTS)"

# One arrangement and no other, written the way a reader's own browser holds it. Both
# stores are cleared first, so each arrival is the arrangement it names rather than that
# one plus whatever the last reload left. Nothing is caught: a browser that will not
# store is a browser this reading cannot make, and swallowing that would turn every
# arrival into a first visit and every arrival finding into a pass.
ARRANGE = """(a) => {
  localStorage.clear();
  sessionStorage.clear();
  (a.store === "session" ? sessionStorage : localStorage).setItem(a.key, a.value);
}"""


def arrival_findings(browser, url):
    """Whether a page comes up at all in each arrangement a reader can return to.

    The suite's, not `render_version`'s, and the line between them is whose fault a
    finding is. Everything the gate reads is something the page's author wrote and
    can change; a restore is the layer's, identical under every version, so an agent
    running the gate at handover would be paying for a verdict on code it did not
    write and cannot fix.

    What it reads: a fresh context holds nothing, so every other reading in the suite
    is of a first visit — the comment panel shut, no tray standing, design mode off —
    and each of those is something a reader turns on once and gets back on every load
    afterwards. That left the restores as the one road onto a page with nothing
    watching it, and a tray someone had left standing came up as a ReferenceError
    instead of a page: it was put up by code running while the runtime was still
    evaluating, which could reach almost nothing. It reached the reader, who reported
    it.

    One page, reloaded into each arrangement, which is what a returning reader does:
    the store is written on the origin the page is already on and read while the next
    load evaluates. What comes back is the upgrade stamp and the console and no more,
    because coming up is the whole question here. Boxes are not measured again: every
    shipped example was measured in each of these arrangements and none of them moved
    a box that a first visit didn't.
    """
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    page = browser.new_page(viewport=interact.RENDER_VIEWPORT, color_scheme="light")
    errors = []
    notices = []

    def console_message(message):
        if message.type != "error":
            return
        target = notices if interact.resize_observer_error(message.text) else errors
        target.append(message.text)

    page.on("console", console_message)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on(
        "response",
        lambda r: errors.append(f"{r.status} {r.url}") if r.status >= 400 else None,
    )
    page.add_init_script(interact.WINDOW_ERRORS)
    found = []
    try:
        # A first visit, to be arranged from and to read the arrangements off. Reported
        # rather than raised when it doesn't arrive: this is the reading that says what
        # happens on a load, so a load it could not make is its own answer, and a page
        # that never came up has nothing to be arranged into.
        try:
            # `load`, where the gate's scheme passes wait for network quiet: those read
            # the served documents and want a page that has stopped asking for things,
            # while everything here is either the stamp below — which the page raises
            # for itself, and which is the stronger fact — or a console the handlers
            # above are already attached to. Network quiet costs 3.5x what the load
            # event does over the five navigations here, measured on
            # design-decision.html, and buys this nothing.
            page.goto(url, wait_until="load")
            page.wait_for_function(interact.UPGRADED)
        except PlaywrightTimeout:
            return [
                "[arrivals] the page never came up unarranged, so nothing could be "
                "arranged — "
                + ("; ".join([*errors, *notices]) or "and no console error says why")
            ]
        for arrangement in page.evaluate(ARRANGEMENTS):
            page.evaluate(ARRANGE, arrangement)
            # A console the last arrangement dirtied is not this one's news.
            errors.clear()
            notices.clear()
            try:
                page.reload(wait_until="load")
                page.wait_for_function(interact.UPGRADED)
            except PlaywrightTimeout:
                found.append(
                    f"[{arrangement['name']}] the page never finished coming up — "
                    + (
                        "; ".join([*errors, *notices])
                        or "and no console error says why"
                    )
                )
                continue
            # A ResizeObserver notice is the gate's to adjudicate over two attempts on
            # the same document; one seen here says nothing on its own.
            found += [f"[{arrangement['name']}] console: {e}" for e in errors]
    finally:
        page.close()
    return found


def motions(events):
    """The settling motions the browser reported, keyed by the motion, not by its target.

    Settling and not living, which is `interact.MOVING`'s distinction and is here for
    its reason: the banner's dot pulses for as long as the tab is open, and something
    that never ends never arrived anywhere. An unbounded iteration count cannot cross
    JSON, so the browser omits it, and that omission is the reading.

    A target is a backend node id, and the same tray over two loads is two of them,
    so an id cannot say whether the second load moved what the first one did. The kind
    of motion, the property or keyframes it plays and how long it runs are one string
    whichever load painted it, and that is the key. The id rides along beside it for
    the failure message alone: a person reading one wants the element, and that is the
    only place a name is worth a round trip.
    """
    found = {}
    for event in events:
        animation = event["animation"]
        source = animation.get("source") or {}
        if source.get("iterations") is None:
            continue
        key = (
            f"{animation['type']} {animation.get('name') or ''}"
            f" {source.get('duration')}ms"
        )
        found.setdefault(key, source.get("backendNodeId"))
    return found


def moved_at(cdp, node):
    """Where a reported motion was, named the way the rest of the suite names elements."""
    if node is None:
        return "an element the browser did not identify"
    # The node map is the inspector's own and is populated by asking for the document;
    # a describeNode on a fresh document without it is refused outright.
    cdp.send("DOM.getDocument", {"depth": 1})
    described = cdp.send("DOM.describeNode", {"backendNodeId": node})["node"]
    pairs = described.get("attributes", [])
    attributes = dict(zip(pairs[::2], pairs[1::2]))
    name = described.get("localName") or described.get("nodeName")
    if attributes.get("id"):
        return f"{name}#{attributes['id']}"
    if attributes.get("class"):
        return f"{name}.{attributes['class'].replace(' ', '.')}"
    return name


# The host case of the same failure: the declarations are on the element that stages the
# tree, so both passes find it — it is in the document — and write into a light DOM the
# shadow root hides. The markup then holds every word the entry promised and the reader
# gets none of them, which is why the gate reads the rendered page rather than the markup.
SHADOW_HOST_PAGE = CUSTOM_WIDGET_PAGE.replace(
    '<lf-callout id="custom-note">',
    '<lf-callout id="custom-note" label="Escalated" urgent>',
)
# Every cell one unbreakable token, so no amount of wrapping gets this table
# inside the column and the third of the theme's three cases is the one on trial.
WIDE_TABLE_PAGE = leaf_page(
    "wide",
    """
<h1 id="t">Sessions</h1>
<p id="p">One row, and more of it than the measure holds.</p>
<table id="sessions">
<thead><tr>{heads}</tr></thead>
<tbody><tr>{cells}</tr></tbody>
</table>
""",
).format(
    heads="".join(f"<th>heading_number_{i}</th>" for i in range(8)),
    cells="".join(f"<td>value_number_{i}</td>" for i in range(8)),
)

# A block wider than the column and narrower than the window: 70% of 1200px is
# 840px against a 720px column, so it stands 120px out in the margin with
# the body not scrolling by a pixel. In vw rather than px because the static lint
# counts pixels and would have caught it before a browser ever saw it.
SPILLING_PAGE = LONG_PAGE.replace(
    "</main>", "<div id='too-wide' style='width: 70vw'>Wide.</div>\n</main>"
)
# Two wrappers that generate no box, differing only in whether anything inside them does.
# `#veiled` is the shape the vocabulary shipped while a suggestion was display: contents,
# and any page can still write in a line — it is the control: the gate must not report
# it, or it reports every page that styles a wrapper away. `#ghost` is the same wrapper
# with its words loose inside it, where there is nothing at all for a mark to hang on.
UNMARKABLE_PAGE = LONG_PAGE.replace(
    "</main>",
    "<div id='veiled' style='display: contents'>"
    "<p id='seen'>Words in a box of their own.</p></div>"
    "<div id='ghost' style='display: contents'>Words in no box at all.</div>\n</main>",
)
# The shapes a float takes at the column's edge. The first three are laid out from the
# same left content edge, so the only difference is how far each one's own negative
# margin carries it: far enough and the whole box is out in the margin, which is what a
# sidenote is; not far enough and the box straddles the edge, which is a spill. The
# fourth says the same side in the logical spelling, and the fifth is the run of prose a
# resident holds — every one of which inherits the box its parent put out there.
FLOATING_PAGE = LONG_PAGE.replace(
    "</main>",
    "<div id='in-the-margin' style='float: left; clear: left; width: 180px;"
    " margin-left: -204px'>Beside <code id='inner-word'>--flag</code>.</div>"
    "<div id='half-out' style='float: left; clear: left; width: 180px;"
    " margin-left: -90px'>Across.</div>"
    "<div id='logical' style='float: inline-start; clear: left; width: 180px;"
    " margin-left: -204px'>Beside.</div>"
    "<div id='off-window' style='float: left; clear: left; width: 180px;"
    " margin-left: -900px'>Gone.</div>\n</main>",
)
SIDENOTE_IN_A_WIDGET = LONG_PAGE.replace(
    "</main>",
    """<lf-options id="where" choose>
  <lf-option id="opt-a"><strong>First</strong>
    <aside class="sidenote" id="boxed-note">Measured over a quarter.</aside>
    <p>An option carrying a note written inside it.</p>
  </lf-option>
  <lf-option id="opt-b"><strong>Second</strong> The other one.</lf-option>
</lf-options>
</main>""",
)


# A note written level with a change, which is the one arrangement that puts two
# residents of the right margin on the same line.
NOTE_BESIDE_A_CHANGE = LONG_PAGE.replace(
    "</main>",
    """<aside class="sidenote" id="level-note">Measured over a quarter, and the number
moved twice inside it.</aside>
<lf-suggestion id="sug-level">
  <lf-old><p id="old-level">About three thousand writes a second at peak.</p></lf-old>
  <lf-new><p>3,400 writes a second at p99, over the last quarter.</p></lf-new>
</lf-suggestion>
</main>""",
)
# Boxes over their container, differing only in what holds them and how. The first two
# are the rule and neither alone proves it: a page that named both would refuse every
# wide table the theme puts in a scroller, and one that named neither is the gate before
# it could see a clipped box at all. The third says which box holds this one — it is
# written inside a clipping box and placed against the column, so the markup and the
# containing blocks answer differently and only one of them paints. The fourth is that
# question the other way up: containment makes a static box the containing block of what
# it then cuts, while the overflow every gate before this one read computes `visible`.
# The fifth is a box that says it cuts. The sixth is where the cut falls: a border hides
# what is drawn under it, and a border box says nothing about that. The last pair is why
# the report is suppressed per container rather than per subtree — nested, and lost out
# of two different boxes by two very different amounts.
OVER_ITS_CONTAINER = LONG_PAGE.replace(
    "</main>",
    "<div id='clipping' style='width: 300px; overflow: hidden'>"
    "<div id='eaten' style='width: 420px'>Nobody sees the end of this.</div></div>"
    "<div id='scrolling' style='width: 300px; overflow-x: auto'>"
    "<div id='reachable' style='width: 420px'>This one scrolls into view.</div></div>"
    "<div id='holding' style='width: 300px; height: 40px; overflow: hidden'>"
    "<div id='hung' style='position: absolute; width: 420px'>Placed, so this one "
    "holds it not at all.</div></div>"
    "<div id='contained' style='width: 300px; height: 40px; contain: paint'>"
    "<div id='cut-by-paint' style='position: absolute; width: 420px'>Containment cuts "
    "this one while overflow says visible.</div></div>"
    "<div id='telling' style='width: 300px; overflow: hidden; "
    "text-overflow: ellipsis; white-space: nowrap'>"
    "<span id='told'>A line long enough to run past the end of the box it is written "
    "inside, which says so with an ellipsis.</span></div>"
    "<div id='bordered' style='width: 300px; border-left: 20px solid #888; "
    "overflow: hidden'>"
    "<div id='under-border' style='margin-left: -20px; width: 300px'>The first 20px of "
    "this are behind the border.</div></div>"
    "<svg id='drawn' width='300' height='60' xmlns='http://www.w3.org/2000/svg'>"
    "<foreignObject width='120' height='40'>"
    "<div xmlns='http://www.w3.org/1999/xhtml' style='width: 128px'>The drawing's own "
    "accounting.</div></foreignObject></svg>"
    "<div id='barely' style='width: 300px; overflow: hidden'>"
    "<div id='over-by-three' style='width: 303px'>Three pixels over this one."
    "<div id='inner-box' style='position: relative; width: 200px; height: 40px; "
    "overflow: hidden'>"
    "<div id='over-by-far' style='position: absolute; left: 0; width: 600px'>Four "
    "hundred over that one.</div></div></div></div>"
    "\n</main>",
)
SCROLLED_CONTAINER = LONG_PAGE.replace(
    "</main>",
    "<div id='rolled' style='width: 300px; overflow-x: auto'>"
    "<div id='riding' style='width: 900px'>Where the content of a scrolled box "
    "starts.</div></div>\n</main>",
)
# The two edges the reader draws, and what a reading of either has to know: a page that
# offers the region, what puts it up, the region's own selector, which side of the window
# it is held to, and the numbers the runtime holds it to. Two records rather than two
# tests, because the whole claim of `drawnEdge` is that the two are one piece of furniture
# reflected — a reading written for the panel alone would go on passing on the day the
# tray's edge stopped working, and the tray's edge exists precisely because the panel's
# did not have to be written a second time.
#
# `html` is a call rather than the markup, because the page the trays need is declared
# with the other tray readings a long way below here, and a parametrize list is read at
# import. `squeeze` is the window that has no room for what the reader chose and the width
# the region stands at there — per edge, because each is capped against its own half of a
# window and covers the page at a different one.
EDGES = [
    SimpleNamespace(
        name="comments",
        html=lambda: LONG_PAGE,
        comments=1,
        stand=lambda page: page.locator(".lf-comments").click(),
        region=".lf-panel",
        side="right",
        store="lf-panel-width",
        wide=420,
        squeeze=(1000, 500),
    ),
    SimpleNamespace(
        name="trays",
        html=lambda: ASKS_PAGE,
        comments=0,
        stand=lambda page: page.keyboard.press("a"),
        region=".lf-asks-panel",
        side="left",
        store="lf-tray-width",
        wide=300,
        squeeze=(800, 400),
    ),
]
EDGE_IDS = [edge.name for edge in EDGES]


def edge_settled(page, edge):
    """Wait for the region to stand and for the page to finish making room for it.

    Two animations, on two elements, and `panel_settled`'s reasoning covers both: the
    strip the page yields is a transition on body, and the region's arrival is its own
    slide. A geometry read between them is a read of a box still under a transform.
    """
    expect(page.locator(edge.region)).to_be_visible()
    page.wait_for_function(
        "(region) => document.body.getAnimations().length === 0"
        " && document.querySelector(region).getAnimations().length === 0",
        arg=edge.region,
    )


def geometry(page, edge):
    """What the edge reads back as, and what the page has left beside it.

    The two numbers are one fact asked from both sides: the strip is body's margin and
    the region's own box, and the whole point of the width being the reader's is that
    nothing may hold a copy of it their gesture doesn't reach.
    """
    return page.evaluate(
        """([region, side, store]) => {
            const box = document.querySelector(region).getBoundingClientRect();
            const body = document.body.getBoundingClientRect();
            return {
                width: Math.round(box.width),
                edge: Math.round(side === 'right' ? box.left : box.right),
                page: Math.round(side === 'right' ? body.right : body.left),
                chosen: localStorage.getItem(store),
            };
        }""",
        [edge.region, edge.side, edge.store],
    )


def draw_edge(page, edge, by):
    """Draw the region's edge `by` pixels wider, as a hand on it would.

    Whole pixels, per `select`'s reason (tests/CLAUDE.md): a press on a fractional point
    is a press the browser is free to round somewhere else. In steps, because one jump
    from press to release is a drag with no `pointermove` between its ends, and the move
    is the whole of what this gesture is made of. Wider is away from the side the region
    is held to, which is the reading the runtime makes of the same gesture.
    """
    box = page.locator(f"{edge.region} .lf-edge").bounding_box()
    x, y = math.floor(box["x"] + box["width"] / 2), math.floor(box["y"] + 200)
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + (by if edge.side == "left" else -by), y, steps=8)
    page.mouse.up()
    # The slide stands down for the length of a drag and comes back at its end, so what
    # is waited on is the page holding still rather than a transition finishing — which
    # `panel_settled` reads the same way, and which is empty here on both counts.
    page.wait_for_function("() => document.body.getAnimations().length === 0")


# The room, sampled every frame for as long as a slide lasts. A property is asked of the
# root rather than of any element that spends it, because it is the fact and an exhibit is
# one reader of it.
ROOM_EVERY_FRAME = """(frames) => {
  window.__room = [];
  // The first sample is taken now rather than on the first frame, so the width before the
  // press is always in the trace: a frame is free to land after the keypress that follows
  // this call, and a trace that opens after the strip is taken has one value in it and
  // nothing to compare.
  const tick = () => {
    window.__room.push(
      getComputedStyle(document.documentElement).getPropertyValue('--lf-room'));
    if (window.__room.length < frames) requestAnimationFrame(tick);
  };
  tick();
}"""
# Enough code for the roles to differ from each other and from the block: a comment, a
# keyword, a string, a name, a number.
COLORED_CODE_PAGE = LONG_PAGE.replace(
    "</main>",
    """<pre id="snippet"><code class="language-python"># the ceiling doubles per approval
def ceiling(limit, approvals):
    return "over" if approvals > 12 else limit
</code></pre>
</main>""",
)

# Both bugs go back as CSS, which is the shape the regression takes for real: the
# attribute lands either way, and it is the stylesheet answering it that stops working.
# A rule at document level with the theme's own specificity, so the later one wins.
UNANSWERED_CODE_PAGE = COLORED_CODE_PAGE.replace(
    "</head>", "<style>[data-lf-syn] { color: inherit; }</style>\n</head>"
)
# What --syn-comment carried until this gate was written: 3.3:1 on --pre-bg, and the
# reading a user reported as the highlighting being gone.
FAINT_CODE_PAGE = COLORED_CODE_PAGE.replace(
    "</head>", '<style>[data-lf-syn="cm"] { color: #8b8577; }</style>\n</head>'
)

# A role that reads on the block and not on the tint one of its lines wears. The clean
# line comes first on purpose: a gate that stopped at a role's first span would take the
# 7.9:1 reading and never reach the 1.6:1 one two lines down, and a walkthrough's hi band
# is the surface where a code line is most often set on something other than --pre-bg.
TINTED_LINE_PAGE = LONG_PAGE.replace(
    "</head>", "<style>:root { --hi-tint: #6f6a60; }</style>\n</head>"
).replace(
    "</main>",
    """<lf-code id="tinted" language="python" hi="2"><pre>
first = "on the block's own colour"
second = "on the band"
</pre></lf-code>
</main>""",
)

# The same reading, in a shadow tree. lf-diff renders the page's words into one, so its
# spans are in no document.querySelectorAll — and the page carries no other code, so a
# probe that stopped at the boundary would sweep this and find nothing to say. The token
# is what goes back rather than a rule: a custom property inherits through the boundary
# where a selector does not, which is both why this reaches the spans and why a project's
# own palette reaches them too, gate or no gate.
SHADOWED_DIFF = """<lf-diff id="shadowed"><pre>
diff --git a/gateway/limits.py b/gateway/limits.py
--- a/gateway/limits.py
+++ b/gateway/limits.py
@@ -1,3 +1,4 @@
 def ceiling(limit, approvals):
-    return limit
+    # the ceiling doubles per approval
+    return "over" if approvals > 12 else limit
</pre></lf-diff>
</main>"""
SHADOW_CODE_PAGE = LONG_PAGE.replace(
    "</head>", "<style>:root { --syn-comment: #8b8577; }</style>\n</head>"
).replace("</main>", SHADOWED_DIFF)

# The other half of the boundary: what is painted behind a shadowed span is on the
# elements above the host, and a span at the top of a root has no parentElement to climb
# to. Today's theme hides that — the box a diff renders into carries an opaque --card, so
# a composite that stopped at the boundary would land on the same colour — which is a
# coincidence of the palette and not a reason to read the light tree. Flattening that one
# surface is all it takes to part them: the paper under it is what the reader has behind
# the comment, and against the white a stalled climb falls back to, a dark page's ink
# reads as either a pass or a failure that isn't on the screen.
FLAT_SHADOW_PAGE = LONG_PAGE.replace(
    "</head>", "<style>:root { --card: transparent; }</style>\n</head>"
).replace("</main>", SHADOWED_DIFF)
# Two sets, because pointing at a control and pressing it are different questions.
#
# What must hold still is everything a user aims at, however the widget that built
# one made it: the runtime's real buttons and selects, the spans `offer` builds, a tab, a
# pick mark, a reference. Naming the ways a control is constructed rather than the widgets
# that construct them is what lets a twelfth widget's join this sweep without editing it.
NEIGHBOUR = (
    "[data-lf-offer], [role=tab], [role=button], .lf-btn, .lf-pick, "
    "button, select, summary, a[href]"
)
# What this sweep presses is narrower, and both exclusions are about the press landing
# rather than about the control. A <select> opens a native popup the page cannot see and
# the next click closes instead of pressing — which is how this sweep first passed while
# pressing nothing at all, the shape of vacuous pass CLAUDE.md is about. A link is a
# user's control and its press is a scroll, so it belongs to the set above and has
# nothing here to disturb.
PRESS = "[data-lf-offer], [role=tab], [role=button], .lf-btn, .lf-pick, button, summary"

# The controls a press is aimed *past*: the ones sharing its parent, standing on the same
# line, and on screen at both ends of the gesture. Held in a JS array rather than looked
# up again afterwards, because identity has to survive a press that adds or removes a
# sibling; measured with offset*, which is the layout box before any transform, so a card
# still lifted under the pointer reads as the nothing it is.
#
# On screen is the load-bearing half. A control inside a fold the press opens was nowhere
# the user could aim, and one the press puts away — a suggestion's ✗ Reject, once ✓
# Accept has settled the pair — is not a control that moved. Both are the press doing what
# it was pressed for. `[hidden]` is asked separately because hidden="until-found", which is
# what a folded region wears, measures zero and still reports itself visible.
ON_SCREEN = "(n) => n.checkVisibility() && !n.closest('[hidden]') && n.offsetWidth > 0"
# What to call a control in a failure message. Its words are in it because they are
# usually the whole of what distinguishes one button in a row from the next — and out of
# the key it is looked up by, since a control that rewrites them (a count gaining a
# digit) is the same control saying something new.
NAMED = """(n) => n.tagName.toLowerCase()
    + (typeof n.className === 'string' && n.className.trim()
       ? '.' + n.className.trim().split(/\\s+/).join('.') : '')
    + ' ' + JSON.stringify((n.textContent || '').trim().slice(0, 24))"""
NEIGHBOURHOOD = f"""(el, sel) => {{
  const band = el.getBoundingClientRect();
  const sameLine = (n) => {{
    const r = n.getBoundingClientRect();
    return Math.min(r.bottom, band.bottom) - Math.max(r.top, band.top) > 1;
  }};
  window.__lfOnScreen = {ON_SCREEN};
  window.__lfNeighbours = [...el.parentElement.children]
      .filter((n) => n !== el && !n.contains(el))
      .flatMap((n) => (n.matches(sel) ? [n] : [...n.querySelectorAll(sel)]))
      .filter((n) => window.__lfOnScreen(n) && sameLine(n));
  return {{ names: window.__lfNeighbours.map({NAMED}), boxes: window.__lfBoxes() }};
}}"""
# The same capture, of the banner rather than of one control's line: every control the
# chrome is showing, held by identity so the news can rewrite their words without
# changing who they are.
BANNER_WATCH = f"""(sel) => {{
  window.__lfOnScreen = {ON_SCREEN};
  window.__lfNeighbours = [...document.querySelector(".lf-banner").querySelectorAll(sel)]
      .filter(window.__lfOnScreen);
  return {{ names: window.__lfNeighbours.map({NAMED}), boxes: window.__lfBoxes() }};
}}"""
# One reading, named once, so the rendered-frame wait and the assertion cannot measure
# differently.
DEFINE_BOXES = """() => { window.__lfBoxes = () => window.__lfNeighbours.map(
    (n) => window.__lfOnScreen(n)
      ? [n.offsetLeft, n.offsetTop, n.offsetWidth, n.offsetHeight] : null); }"""
# Nested animation-frame callbacks have one complete rendering turn between them, so
# this states rendered progress rather than elapsed time between two frame polls.
RENDERED = "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"


def page_at_rest(page):
    """Render the known edge, finish finite motion, then render its ending."""
    page.evaluate(RENDERED)
    page.wait_for_function(f"() => ({interact.MOVING})().length === 0")
    page.evaluate(RENDERED)


def displaced(before, boxes):
    """Which of the watched controls are somewhere else, in the failure's own words.

    A control that has gone off screen reads None and is left out: it was put away
    rather than moved, which is a thing both sweeps below deliberately allow."""
    return [
        f"{name} moved by "
        f"{[round(a - b, 1) for a, b in zip(now, was)]} (left, top, width, height)"
        for name, was, now in zip(before["names"], before["boxes"], boxes)
        if now is not None and was != now
    ]


def aim_targets(page_dir):
    """Everything an ⌥-press can land on that something is waiting to answer.

    Every control however its widget built one, and every element of the vocabulary,
    whose handlers sit on the widget rather than on a control — an option is picked by
    clicking its prose. The vocabulary is read from the page's own registry rather than
    listed, so the twelfth widget is swept by existing. Prose has no handler at all, so
    one press into it proves what fifty would."""
    tags = ", ".join(
        t for t in interact.load_registry(page_dir) if not t.startswith("$")
    )
    return f":is({PRESS}, {tags}):not(.lf-chrome *)"


# Where in a target to aim, asked of the rendered page rather than assumed: near its
# leading corner, since the middle of a container is usually one of its children, and only
# where the point is really the target's — an element under the banner or clipped to
# nothing is somewhere no aim can land, which is a skip rather than a failure.
AIM_POINT = """(el) => {
  const r = el.getBoundingClientRect();
  const spots = [[r.left + Math.min(8, r.width / 2), r.top + Math.min(8, r.height / 2)],
                 [r.left + r.width / 2, r.top + r.height / 2]];
  for (const [x, y] of spots) {
    const at = document.elementFromPoint(x, y);
    if (at && (at === el || el.contains(at))) return [x, y];
  }
  return null;
}"""
# The promise itself, read where the runtime states it: the aim's box in the chrome's
# layer carries the aimed item's id (data-for, refreshAim's one write of it). The
# composer's own mark then stands on that same item once the press is made, so the box's
# answer before the press and the draft's after it agreeing is the promise being kept.
AIMED = """() => document.querySelector(".lf-aim")?.getAttribute("data-for") ?? null"""
# The item the draft stands on, which is not always the element wearing the outline: a
# mark hangs on the boxes its item shows through, and a display: contents wrapper shows
# through its slots. Reading the raw id said the promise was broken for every suggestion
# on every example — while the reading that had passed all along was the vacuous one, the
# outline sitting on a wrapper that draws nothing.
DRAFT_MARK = """() =>
  document.querySelector(".lf-mark-el.lf-pending")?.closest("[id]")?.id ?? null"""
# What the arm says about the next press, in the one property that is on screen before
# the box is read. Asked of body, where the aim declares it and from where it is
# inherited by everything on the page that doesn't state a cursor of its own.
AIM_CURSOR = """() => getComputedStyle(document.body).cursor"""
# Where focus ended up, which is the effect a press has that leaves no mark in the markup:
# `offer` gives every press it builds a tabindex, so a press the page received lands on
# the control, where the aim's own leaves focus to the composer it opened.
FOCUS_IN_PAGE = """() => {
  const at = document.activeElement;
  return !!at && at !== document.body && !at.closest(".lf-chrome");
}"""
# The page as against the layer over it, which is where an effect nobody asked for shows.
# Read as markup because a widget acting states itself there however it renders — an
# attribute picked, a panel hidden, an editor opened — and a sweep that knew which to look
# for would be a sweep that stops at the widgets it was taught.
#
# Except for an emptied class attribute, which is the outline coming off an element that
# had no class of its own: DOMTokenList leaves `class=""` behind, and that is a residue of
# the runtime's paint rather than anything the page says.
# Generated text is blanked before the compare, because a widget may render a clock
# and a clock is not a press: lf-agent's elapsed line re-renders on every poll, so the
# minute turning during a long sweep read as a press that had reached a widget. What the
# check is for survives untouched — a stray pick writes `chosen` on the option and a
# stray tab switch moves the panels' attributes, both of them authored rather than
# generated, and structure is compared either way.
PAGE_MARKUP = """() => [...document.body.children]
    .filter((n) => !n.classList.contains("lf-chrome"))
    .map((n) => {
        const c = n.cloneNode(true);
        for (const g of c.querySelectorAll("[data-lf-gen]")) g.textContent = "";
        if (c.dataset && c.dataset.lfGen !== undefined) c.textContent = "";
        return c.outerHTML;
    })
    .join("").replaceAll(' class=""', "")"""
# Every legend box stands on its item: same corner, one pixel out, for every item wholly
# on screen. Items partly off it are clipped to the scroller (shownRect) and are not
# compared, and items off it have no box shown at all. An item with no box of its own —
# one a page styles display: contents — reads as what its contents paint, mirroring
# shownRect's fallback: its host rect is 0×0 at the origin, which would otherwise count
# as "wholly on screen" and fail every off-screen one for its rightly hidden box.
LEGEND_TRUE = """() => [...document.querySelectorAll('.lf-legend-box')].every(b => {
  const it = document.getElementById(b.dataset.for);
  let r = it.getBoundingClientRect();
  if (!r.width && !r.height) {
    const contents = document.createRange();
    contents.selectNodeContents(it);
    r = contents.getBoundingClientRect();
  }
  if (r.top < 0 || r.bottom > innerHeight) return true;
  if (b.style.display === 'none') return false;
  const bb = b.getBoundingClientRect();
  return Math.abs(bb.left + 1 - r.left) < 1.5 && Math.abs(bb.top + 1 - r.top) < 1.5
    && Math.abs(bb.width - 2 - r.width) < 1.5 && Math.abs(bb.height - 2 - r.height) < 1.5;
})"""
CORNER_PAGE = leaf_page(
    "corner",
    """
<h1 id="t">Corner</h1>
<section id="wrap"><p id="inner">The section's first block starts at its corner.</p></section>
""",
)
AIM_PAINT_PAGE = leaf_page(
    "aim paint",
    """
<h1 id="t">Aim paint</h1>
<lf-options id="cards" choose>
  <lf-option id="card-plain"><strong>Plain</strong> The first card's argument.</lf-option>
  <lf-option id="card-star" recommended><strong>Starred</strong> A border already the accent.</lf-option>
</lf-options>
<lf-options id="rows" choose>
  <lf-option id="row-ship">Ship it as is</lf-option>
  <lf-option id="row-hold">Hold for the backfill</lf-option>
</lf-options>
""",
)
MARK_PAD = 6  # CSS px of ground kept around the element in the clip
MARK_NEAR = 12  # per channel, wide enough for the stroke's antialiased shoulder only


def token_colour(page, name):
    """What a theme token resolves to on this page, as the browser serializes it.

    The mark's own reading is no reading at all: taken off the marked element's
    `outlineColor`, every measurement below is against whatever that rule happens to
    say, so pointing `.lf-mark-el` at the accent leaves the gate green. The token is
    the thing the rule is supposed to name, so the colour comes from there and the
    rule is checked against it."""
    return page.evaluate(
        """(name) => {
        const probe = document.createElement('span');
        probe.style.color = `var(${name})`;
        document.body.append(probe);
        const seen = getComputedStyle(probe).color;
        probe.remove();
        return seen;
    }""",
        name,
    )


def mark_edges(page, ident, ink):
    """How wide the mark is painted on each side of an element, in device pixels.

    Geometry can't answer this and neither can the computed style: the mark is an
    outline, so every rect is identical whether the stroke survived or something
    painted over it, and `outlineWidth` is what was asked for rather than what
    landed. Pixels are the only reading — the same recourse the draft's focus ring
    needed, one screenshot up from a byte comparison because the four sides have to
    be compared with each other rather than with an earlier frame.

    Each scan starts at the element's own edge and stops at the first pixel that
    isn't the mark's colour, because the first draft counted the first ink-coloured
    run *anywhere* along the scanline: an accent status dot sitting in the clip's own
    padding reported 26 device pixels of "mark" on a side the mark never reached, and
    a marked code block would have counted its identifiers. What follows from that is
    the tolerance too — ±12 per channel admits the stroke's antialiased shoulder and
    nothing else, where ±40 reached both --accent and --syn-name.

    Three samples a side, returned as a set rather than a majority. A majority is a
    vote for the mark being intact when part of the edge has been painted over, which
    is the failure this exists to catch; a disagreement is the finding, so the caller
    sees {1, 0} rather than 1.

    The clip is squared off to whole CSS pixels first, and each side is then asked for
    its own ground, because a leaf page's boxes do not land on whole pixels — 17px of
    body serif at a line-height of 1.6 is 27.2px a line, so a widget's height is a stack
    of fractions. A clip is asked for in CSS pixels and answered in device ones, and
    Chrome truncates the rect to whole CSS pixels before it scales: asked for the board
    column 101.578px tall on this page, it dropped that 0.578 and took all of it off the
    bottom, which put the element's own edge two device pixels from where MARK_PAD said
    it was — outside the window below — and a stroke painted whole on all four sides was
    read as half of one along the bottom. Squaring the clip is what makes that loss
    nothing to model rather than something to allow for.

    The edge is then snapped in CSS space and scaled, in that order, because that is the
    order Blink paints in: the painted edge lands at `floor(ground + 0.5) * scale`, and it
    was multiplying first that made `round(gap * scale)` disagree with it — by a pixel the
    window below covers, until a scale of 4 makes it two. The window is kept for a device
    pixel of engine drift either side."""
    from PIL import Image  # a dev dependency already, for the demo recorder

    box = page.locator(f"#{ident}").bounding_box()
    clip = {"x": math.floor(box["x"] - MARK_PAD), "y": math.floor(box["y"] - MARK_PAD)}
    clip["width"] = math.ceil(box["x"] + box["width"] + MARK_PAD) - clip["x"]
    clip["height"] = math.ceil(box["y"] + box["height"] + MARK_PAD) - clip["y"]
    fits = page.evaluate(
        """([x, y, w, h]) => x >= 0 && y >= 0
             && x + w <= innerWidth && y + h <= innerHeight""",
        [clip["x"], clip["y"], clip["width"], clip["height"]],
    )
    assert fits, (
        f"#{ident} is not wholly on screen with the {MARK_PAD}px around it this squares "
        f"off, and a screenshot clip is the viewport's: scroll it in and size the "
        f"viewport to it first, or the scans measure a truncated image"
    )
    image = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
    width, height = image.size
    scale = page.evaluate("() => devicePixelRatio")
    # The image is the squared clip and nothing else — asserted rather than assumed,
    # because the trailing scans count in from the far edge, so a single row of slack
    # there reads as a stroke a pixel thin and names the element rather than the shot.
    assert (width, height) == (clip["width"] * scale, clip["height"] * scale), (
        f"the clip asked for {clip['width']}x{clip['height']} CSS px at dpr {scale} and "
        f"came back {width}x{height} device px: every scan below counts from an edge "
        f"this arithmetic no longer locates"
    )
    # Each side's own ground, since squaring the clip is not symmetric: MARK_PAD plus
    # whatever that side's rounding added. Snapped in CSS space and then scaled, per the
    # docstring — and a trailing side counts in from the far end of a clip whose width is
    # a whole number, which flips the half, so the two directions round opposite ways.
    lead = {"top": box["y"] - clip["y"], "left": box["x"] - clip["x"]}
    trail = {
        "bottom": clip["y"] + clip["height"] - box["y"] - box["height"],
        "right": clip["x"] + clip["width"] - box["x"] - box["width"],
    }
    edge = {s: round(math.floor(g + 0.5) * scale) for s, g in lead.items()}
    edge |= {s: round(math.ceil(g - 0.5) * scale) for s, g in trail.items()}

    def stroke(scan, at):
        """Mark-coloured pixels contiguous with the element's edge, and no others."""
        inked = [
            all(abs(a - b) <= MARK_NEAR for a, b in zip(pixel, ink)) for pixel in scan
        ]
        start = next((i for i in range(at - 1, at + 2) if inked[i]), None)
        if start is None:
            return 0
        seen = 0
        while start + seen < len(inked) and inked[start + seen]:
            seen += 1
        return seen

    def quarters(size):
        return (size // 4, size // 2, 3 * size // 4)

    columns = [[image.getpixel((x, y)) for y in range(height)] for x in quarters(width)]
    rows = [[image.getpixel((x, y)) for x in range(width)] for y in quarters(height)]
    return {
        "top": {stroke(c, edge["top"]) for c in columns},
        "bottom": {stroke(c[::-1], edge["bottom"]) for c in columns},
        "left": {stroke(r, edge["left"]) for r in rows},
        "right": {stroke(r[::-1], edge["right"]) for r in rows},
    }


@pytest.fixture
def live_leaf(tmp_path, monkeypatch):
    """Stands up a live leaf for the banner's panel to find: published, served by
    a real handler, and written down under the state home the way `server run` writes
    it — which is the whole of how one page learns another exists. Each claims to be
    working, freshly, so its row has a judged state to show. A factory rather than one
    fixture, because a tray is a list and a walk down it needs somewhere to walk to."""
    monkeypatch.chdir(tmp_path)  # keep the project layer out of the overlay
    servers = []
    held = []

    def go(name, title):
        d = interact.state_home() / "pages" / name
        result = CliRunner().invoke(interact.cli, ["page", "init", str(d)])
        assert result.exit_code == 0, result.output
        (d / "versions" / "v1.html").write_text(
            LONG_PAGE.replace("<title>long</title>", f"<title>{title}</title>")
        )
        interact.append_event(
            d, {"kind": "note", "author": "claude", "version": 1, "text": "t"}
        )
        interact.write_json(
            d / "status.json",
            {
                "state": "working",
                "detail": "running the suite",
                "ts": interact.now_iso(),
            },
        )
        # A live leaf has a session behind it, and what the tray's hover says about a
        # page is the work that session is doing it for — so the fixture's pages come
        # out of somewhere nameable rather than out of nowhere.
        record_claim(
            d,
            id=f"s-{name}",
            cwd=str(tmp_path / f"{name}-work"),
        )
        httpd = interact.LeafHTTPServer(
            ("127.0.0.1", 0), interact.handler_for(d, TOKEN)
        )
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        servers.append(httpd)
        port = httpd.server_address[1]
        # Desired address and a held, contentless lease are the two facts a real
        # server exposes to neighbouring pages.
        interact.write_json(
            d / "service.json",
            {
                "host": "127.0.0.1",
                "bind": "127.0.0.1",
                "port": port,
                "enabled": True,
                "lifetime": "standing",
            },
        )
        lease = open(d / "server.lock", "a+b")  # noqa: SIM115 - held, see above
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        held.append(lease)
        return f"http://127.0.0.1:{port}", d

    yield go
    for httpd in servers:
        httpd.shutdown()
    for lease in held:
        lease.close()


@pytest.fixture
def other_leaf(live_leaf):
    return live_leaf("other", "The other leaf")


# The page's scroll after it has stopped moving. A native Space is a smooth scroll, so
# reading straight after the press reads a frame of the glide and calls it the answer —
# which is the whole of what CLAUDE.md's wait norm is about.
SCROLL_SETTLE_MS = 50
SCROLL_STILL = """(hold) => {
  const at = document.body.scrollTop;
  if (at !== window.__lfScrollAt) {
    window.__lfScrollAt = at;
    window.__lfScrollSince = performance.now();
    return false;
  }
  return performance.now() - window.__lfScrollSince > hold;
}"""
# Twelve things waiting, which is more than any shipped example asks and the point: the
# room a list reserves at its foot is invisible until the list is longer than the tray.
MANY_ASKS_PAGE = leaf_page(
    "many asks",
    """
<h1>Many asks</h1>
<p>A tray long enough to scroll.</p>
<lf-tasks id="plan">
"""
    + "\n".join(
        f'<lf-task id="t-{i}" status="review" owner="wren">'
        f"<strong>Waiting on you, item {i}</strong>"
        f"<p>Something to decide about item {i}.</p></lf-task>"
        for i in range(12)
    )
    + """
</lf-tasks>
""",
)
# A run with nothing to break on, in the three places a page puts one: a metric's headline,
# where the box is a fixed 138px and the value is whatever the number turned out to be;
# ordinary prose, which is where a page about code keeps its paths; and a tree, whose module
# writes the name and its badges with no whitespace between them at all.
UNBREAKABLE_PAGE = leaf_page(
    "unbreakable",
    """
<h1 id="h">Nothing to break on</h1>
<lf-metrics id="numbers">
  <lf-metric id="m-token" value="a_very_long_unbroken_identifier">Bucket key</lf-metric>
</lf-metrics>
<p id="p-token">The one it fails on is
gateway_middleware_authentication_token_bucket_refill_strategy.py, every time.</p>
<lf-tree id="tree"><pre>
gateway/
  middleware/
    authentication/
      token_bucket_refill_strategy.py    +6 -2
</pre></lf-tree>
""",
)
# One line past any phone column, so the box a diff renders in has to scroll and the
# rule is the one on trial rather than the fit.
WIDE_DIFF_PAGE = leaf_page(
    "wide diff",
    """
<h1 id="t">A diff wider than the column</h1>
<lf-diff id="wide-diff"><pre>
diff --git a/client/offline/merge.ts b/client/offline/merge.ts
--- a/client/offline/merge.ts
+++ b/client/offline/merge.ts
@@ -18,2 +18,2 @@ export function merge(base: Doc, mine: Edit[], theirs: Edit[]): Doc {
-  return apply(base, [...theirs, ...mine]);
+  const clash = theirs.find((t) =&gt; t.field === edit.field &amp;&amp; t.at &gt; edit.at);
</pre></lf-diff>
""",
)
# The same diff, arriving the other way a widget reaches a reader: on a reply, into a
# column narrower than any page's.
PANEL_DIFF_MARKUP = WIDE_DIFF_PAGE[
    WIDE_DIFF_PAGE.index("<lf-diff") : WIDE_DIFF_PAGE.index("</lf-diff>")
    + len("</lf-diff>")
].replace('id="wide-diff"', 'id="rp-diff"')


def serious_axe_violations(page):
    """WCAG A/AA violations at serious or critical, as (violations, report) — the
    one reading both the live sweep and the exported copy's gate assert on."""
    result = Axe().run(
        page,
        options={
            "runOnly": {
                "type": "tag",
                "values": [
                    "wcag2a",
                    "wcag2aa",
                    "wcag21a",
                    "wcag21aa",
                    "wcag22a",
                    "wcag22aa",
                ],
            },
            "resultTypes": ["violations"],
        },
    )
    violations = [
        violation
        for violation in result.response["violations"]
        if violation["impact"] in {"serious", "critical"}
    ]
    report = "\n\n".join(
        f"{violation['id']} ({violation['impact']}): {violation['help']}\n"
        + "\n".join(
            "  {}: {}".format(
                ", ".join(
                    # A target inside a shadow tree arrives as a selector chain
                    # (a list), one hop per root.
                    sel if isinstance(sel, str) else " >>> ".join(sel)
                    for sel in node["target"]
                ),
                node["failureSummary"],
            )
            for node in violation["nodes"]
        )
        for violation in violations
    )
    return violations, report


# Chips whose words are a price and nothing else, which is two or three characters and
# about 30px — and an inline suggestion swapping one letter for another, about the same.
# Nothing else on the page is unusual, so these are the only things on it that a floor
# written for widgets laying out a region could catch.
SHORT_CHIP_PAGE = leaf_page(
    "chips",
    """
<h1 id="t">Feeder extras</h1>
<p id="p">The bracket order goes in on Friday and there is room in it. Change the
rack flag from <lf-suggestion id="sug-flag"><lf-old>x</lf-old><lf-new>y</lf-new></lf-suggestion>
before it ships.</p>
<lf-options id="extras" choose multiple>
<lf-option id="x-tray"><lf-chip>£9</lf-chip>
<strong>Seed tray</strong> Catches the spill under the south pair.
</lf-option>
<lf-option id="x-dome"><lf-chip tone="ok">£15</lf-chip>
<strong>Weather dome</strong> Keeps the seed dry through a wet week.
</lf-option>
</lf-options>
""",
)
# A page that says one of its words on screen only. The rule is the page's own, which is
# the point: the gate asks what the printed page still says, not who took the words away.
PRINT_LOSS_PAGE = CARRIED_PAGE.replace(
    "</head>",
    "<style>@media print { #lede, #c-bearer { display: none } }</style></head>",
)


def solid_png(width: int, height: int, rgb: tuple) -> bytes:
    """A solid-colour PNG, written here rather than committed, so the pair a shot
    test flips between is two files whose only difference is the one the test made."""
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


SHOTS = {
    "before": solid_png(600, 300, (210, 220, 235)),
    "after": solid_png(600, 300, (235, 215, 205)),
}
SHOT_SRC = {
    k: f"/media/{hashlib.sha256(v).hexdigest()[:16]}.png" for k, v in SHOTS.items()
}
SHOT_PAGE = LONG_PAGE.replace(
    "</main>",
    f"""<p id="lede">What moved, in words, because the picture cannot say it.</p>
<lf-shot id="shot-nav" alt="the navigation rail"
         before="{SHOT_SRC["before"]}" after="{SHOT_SRC["after"]}"></lf-shot>
</main>""",
)


def shown_frames(page):
    return page.evaluate("""() => [...document.querySelectorAll('.lf-shotframe')]
        .filter(f => getComputedStyle(f).visibility === 'visible')
        .map(f => f.dataset.lfState)""")


def flip_point(page, sel="lf-shot"):
    """The middle of a shot's frame — where a reader comparing would have the pointer.

    Returned rather than clicked, because what the widget is for is alternating from
    one place: a helper that clicked would let a test press two different points and
    still pass, which is the property the old radios failed at.

    Scrolled to first, because `bounding_box` answers in viewport coordinates for an
    element that may be past the fold — on the long page the shot sits on, the point
    comes back below the window and `mouse.click` presses whatever is there instead,
    which reads as the widget refusing the gesture rather than as the test missing it.
    """
    frame = page.locator(f"{sel} .lf-shotframe").first
    frame.scroll_into_view_if_needed()
    box = frame.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


# Two ways a widget leaves words on screen that no comment can land on, written into the
# markup because the gate reads the rendered page and cannot tell who put them there — a
# page-local module is where both actually happen, and standing one up here would test the
# module loader rather than the gate. First: a heading inside a chrome-looking row, with
# nothing said about whose words it is. Second: the words declared the page's, and put
# inside a form control, where no pointer can select them however they are marked.
OUT_OF_REACH_PAGE = CARRIED_PAGE.replace(
    '<lf-option id="c-lax" chosen>',
    '<lf-option id="c-lax" chosen><div class="lf-ui"><strong>Session cookies</strong>'
    "</div><button data-lf-said>Lax, host-only</button>",
)
# A painted fact whose spoken copy is on the page and drawn nowhere, written into the
# markup for the same reason the two above are: the gate reads the rendered page and
# cannot tell who suppressed the word. `recommended` is x-paints, so the runtime writes
# a .lf-quiet span beside each of these; the style takes the box off both. One stands in
# the open and one behind a disclosure the reader has not opened.
PAINTED_IN_SILENCE_PAGE = leaf_page(
    "silence",
    """
<h1 id="h">Transport</h1>
<lf-options id="open-group">
  <lf-option id="p-seen" recommended><strong>Lax cookie</strong> Host-only.</lf-option>
  <lf-option id="p-other"><strong>Bearer header</strong> Every script reads it.</lf-option>
</lf-options>
<details id="folded">
  <summary>Weighed in March</summary>
  <lf-options id="folded-group">
    <lf-option id="p-folded" recommended><strong>Signed URL</strong> Expires.</lf-option>
    <lf-option id="p-spare"><strong>Nothing</strong> Leave it.</lf-option>
  </lf-options>
</details>
""",
    head="<style>.lf-quiet { display: none }</style>",
)
# A module making the mistake the scaffold's own header warns about: words injected
# into the widget wearing the chrome face, with nothing said about whose they are.
# It has to be a module, because a page may not author `.lf-ui` — `reserved_marker_errors`
# refuses it at the door — and no shipped widget makes the mistake, the gate being green.
BADGE_CHROME = """      const row = document.createElement("div");
      row.className = "lf-ui";
      row.textContent = "Sent by the reviewer";
      this.append(row);"""
UNPARSABLE_DIAGRAM = LONG_PAGE.replace(
    "</main>",
    "<lf-diagram id='d-broken'><pre>\nflowchart LR\n  A[Start --&gt; B{{{ ]]] broken\n</pre></lf-diagram>\n</main>",
)
# The thread list is reconciled, not rebuilt, and the tests below are its faces: a
# send is a gesture and reveals what it made; an arrival is news and moves nothing; a
# resolution moves a thread without remaking its neighbours; and all of it holds
# because the nodes survive the poll instead of being replaced by lookalikes. The old
# rebuild passed a lookalike test easily — same markup, fresh nodes — which is why
# these pin identity (a probed element) and geometry (a held thread's own box), not
# appearance.


def in_threads_scrollport(page, selector):
    """Whether the node is fully inside the panel list's scrollport — waited for,
    because the reveal scrolls smoothly and only the arrival is the fact."""
    page.wait_for_function(
        """(sel) => {
            const box = document.querySelector('.lf-threads');
            const node = document.querySelector(sel);
            if (!node) return false;
            const b = box.getBoundingClientRect(), n = node.getBoundingClientRect();
            return n.top >= b.top && n.bottom <= b.bottom;
        }""",
        arg=selector,
    )


# A page with an outline: three headings, and passages under each to hang threads on.
# LONG_PAGE has one heading and sixty paragraphs, which cannot tell an order that
# follows the page from one that follows the log — every thread on it is in the same run.
PANEL_PAGE = leaf_page(
    "panel",
    """
<h1 id="t">Shipping offline editing</h1>
<p id="lede">The lede, which is the first thing anybody reads on the way in.</p>
<section id="s-how">
  <h2 id="h-how">How it works</h2>
  <p id="how-store">A queue holds every edit until the connection comes back.</p>
  <p id="how-cap">The store is capped at forty megabytes a workspace.</p>
  <lf-diff id="how-patch"><pre>
diff --git a/gateway/limits.py b/gateway/limits.py
--- a/gateway/limits.py
+++ b/gateway/limits.py
@@ -1,3 +1,4 @@
 def ceiling(limit, approvals):
-    return limit
+    # the ceiling doubles per approval
+    return "over" if approvals > 12 else limit
</pre></lf-diff>
</section>
<section id="s-merge">
  <h2 id="h-merge">The merge rule</h2>
  <p id="merge-both">Two people editing one document offline is the case to answer.</p>
  """
    + "\n".join(
        f"<p id='m{i}'>Filler {i}. " + "Words. " * 24 + "</p>" for i in range(20)
    )
    + """
</section>
""",
)

# The panel's list, in the order it stands, with the headings among the threads: a
# heading is its own words, a thread its id. One query, because what is asserted about
# the order is always about both — a run is a heading and the threads it names.
LIST_RUNS = """() => [...document.querySelector(".lf-threads").children]
  .map((n) => (n.dataset.group ? "§ " + n.textContent : n.dataset.id))
  .filter(Boolean)"""


def panel_comment(d, text, anchor=None, author="user"):
    """One thread's opening message, written straight to the log."""
    event = {"kind": "comment", "author": author, "version": 1, "text": text}
    if author == "claude":
        event["agent"] = "Claude"
    if anchor:
        event["anchor"] = anchor
    return interact.append_event(d, event)["id"]


# What the list is holding, from the one query that answers both halves of the
# question a departing thread raises: what stands where, and what the keys can still
# reach. The two lists differ by exactly the thread on its way out.
LIST_STATE = """() => {
  const list = document.querySelector(".lf-threads");
  return {
    standing: [...list.children].map((n) => n.dataset.id).filter(Boolean),
    walkable: [...list.querySelectorAll(":scope > .lf-thread")].map(
      (n) => n.dataset.id,
    ),
  };
}"""
# Every frame the fold paints, sampled from the page because there is nowhere else to
# sample it: what a motion looks like is a sequence, and every other check here reads a
# state. One height per animation frame until the node leaves the page, which is the
# fold's own end and so the wait's fact.
FRAME_BY_FRAME = """(sel) => {
  window.__seen = [];
  window.__done = false;
  const tick = () => {
    const el = document.querySelector(sel);
    if (!el) return void (window.__done = true);
    window.__seen.push(+el.getBoundingClientRect().height.toFixed(1));
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}"""
STACKED_OPTIONS_PAGE = leaf_page(
    "stacked options",
    """
<h1 id="h">Clip storage</h1>
<lf-options id="stacked" choose>
  <lf-option id="st-sd"><lf-chip>effort: low</lf-chip><lf-chip tone="danger">risk: high</lf-chip>
    <strong>SD card only</strong>
    <dl class="facts"><dt>Keeps</dt><dd>nine days</dd><dt>Retrieval</dt><dd>a ladder</dd></dl>
    <p>Clips stay on the camera's card and overwrite oldest-first.</p>
  </lf-option>
  <lf-option id="st-pi" recommended><lf-chip>effort: med</lf-chip><lf-chip>risk: low</lf-chip>
    <strong>Pi in the shed</strong>
    <dl class="facts"><dt>Keeps</dt><dd>a season</dd><dt>Retrieval</dt><dd>the couch</dd></dl>
    <p>A nightly pull over the garden wifi; the link is the weak span.</p>
  </lf-option>
</lf-options>
<lf-options id="terse">
  <lf-option id="t-paper"><lf-chip>effort: low</lf-chip><lf-chip>risk: high</lf-chip><strong>Paper maps</strong> Nothing
  to charge.</lf-option>
  <lf-option id="t-gps"><lf-chip>£240</lf-chip><lf-chip>a week of battery</lf-chip><lf-chip>resellable if the season ends early</lf-chip><strong>GPS</strong> A week of
  battery.</lf-option>
</lf-options>
<lf-compare id="pair">
  <lf-variant id="cv-cedar"><strong>Cedar</strong>
    <dl class="facts"><dt>Seal</dt><dd>never</dd></dl>
    <p>Weathers silver; no sealant, no schedule.</p></lf-variant>
  <lf-variant id="cv-pine"><strong>Pine</strong>
    <dl class="facts"><dt>Seal</dt><dd>yearly</dd></dl>
    <p>Cheaper up front; seal it every autumn.</p></lf-variant>
</lf-compare>
<lf-compare id="terse-pair">
  <lf-variant id="cv-oiled"><strong>Oiled</strong> Darker, and a spring job.</lf-variant>
  <lf-variant id="cv-bare"><strong>Bare</strong> Silver by June.</lf-variant>
</lf-compare>
<lf-compare id="spread">
  <lf-variant id="cv-oak"><strong>Oak</strong> Heavy.</lf-variant>
  <lf-variant id="cv-ash"><strong>Ash</strong> Pale, and it moves in damp, so a board
    laid in March stands proud of the one beside it by June and the fixings work
    loose over the winter after that.</lf-variant>
  <lf-variant id="cv-elm"><strong>Elm</strong> Scarce.</lf-variant>
  <lf-variant id="cv-yew"><strong>Yew</strong> Slow.</lf-variant>
  <lf-variant id="cv-fir"><strong>Fir</strong> Cheap, and it rots at the ground.</lf-variant>
</lf-compare>
""",
)
# A question carried on the group rather than in a heading beside it, in every shape a
# group takes it in: the two forms, the joined control and the plain stack, and the
# settled collapse. One page, because the shapes are independent axes and a rule written
# against one governs the rest without saying so — which is how the joined control came
# to give the question none of the padding it gives every other cell while a corpus
# holding one labelled card group stayed green (examples/CLAUDE.md).
ASKED_PAGE = leaf_page(
    "asked",
    """
<h1 id="t">Asked</h1>
<lf-options id="cards" choose label="Where should a session live?">
  <lf-option id="c-redis"><strong>Redis</strong>
  <p>A store we already run, keyed by an opaque id.</p></lf-option>
  <lf-option id="c-pg"><strong>Postgres</strong>
  <p>One fewer moving part, at the cost of write load.</p></lf-option>
</lf-options>
<lf-options id="rows" choose multiple label="Which jobs are worth starting?">
  <lf-option id="r-drill">A revocation drill</lf-option>
  <lf-option id="r-rotate">Key rotation for the fallback cookie</lf-option>
</lf-options>
<lf-options id="done" choose settled label="How do parallel sessions merge?">
  <lf-option id="d-serial" chosen><strong>A branch each</strong>
  <p>Merged one at a time against current main.</p></lf-option>
  <lf-option id="d-shared"><strong>One shared branch</strong>
  <p>Cheapest to set up, and conflicts are the norm.</p></lf-option>
</lf-options>
""",
)
# The other form of a question, on one page beside the first: options that are bare
# labels, naming the blocks of the page they are about, and a group taking more than one.
# One label runs into inline markup and one row carries a chip, because both are things a
# row lays out beside its own apparatus and neither is anything a card would notice.
#
# Form and arity are independent, so the page carries both values of each: `multiple` is
# on a list (#jobs) and on a titled group (#tools), against single-pick cards
# (#bracket). Which is what makes a claim about arity testable on its own — #jobs against
# #bracket differs in two things at once, and a rule that was really the list form's
# would pass that pair either way.
ASK_PAGE = leaf_page(
    "ask",
    """
<h1 id="h">Three jobs</h1>
<lf-options id="jobs" choose multiple>
  <lf-option id="job-mounts" for="sec-mounts">Replace the <code>M8</code> mounts</lf-option>
  <lf-option id="job-heater" for="sec-heater"><lf-chip tone="ok">reversible</lf-chip>Heat the bird bath</lf-option>
  <lf-option id="job-camera">Neither — the camera first</lf-option>
</lf-options>
<section id="sec-mounts"><h2>The mounts</h2><p id="mounts-p">Plastic, and one came
down in January.</p></section>
<section id="sec-heater"><h2>The bird bath</h2><p id="heater-p">Frozen eleven
mornings last winter.</p></section>
<lf-options id="bracket" choose>
  <lf-option id="br-steel"><strong>Steel</strong> Galvanised, drop-in.</lf-option>
  <lf-option id="br-cedar"><strong>Cedar</strong> Cheap; needs sealing.</lf-option>
</lf-options>
<lf-options id="tools" choose multiple>
  <lf-option id="tl-clamp"><strong>Bar clamp</strong> Holds the rail while it sets.</lf-option>
  <lf-option id="tl-torque"><strong>Torque wrench</strong> The mounts are rated.</lf-option>
</lf-options>
<lf-options id="ordered">
  <lf-option id="ord-mounts">Mounts, before the frost</lf-option>
  <lf-option id="ord-heater">Heater, after it</lf-option>
</lf-options>
""",
)


def sent_events(page_dir):
    return [
        json.loads(line)
        for line in (page_dir / "comments.jsonl").read_text().splitlines()
    ]


NESTED_ASK_PAGE = leaf_page(
    "nested",
    """
<h1 id="h">Two jobs</h1>
<lf-options id="outer" choose multiple>
  <lf-option id="out-drill"><strong>The revocation drill</strong>
    <p id="drill-p">Support wants it run at their own volume.</p>
    <lf-options id="inner" choose>
      <lf-option id="in-now">This sprint</lf-option>
      <lf-option id="in-next">Next sprint</lf-option>
    </lf-options>
  </lf-option>
  <lf-option id="out-keys"><strong>Key rotation</strong>
    <p id="keys-p">Cheap, and overdue since the split.</p>
  </lf-option>
</lf-options>
""",
)
# An option arguing its case with the evidence inside it, which is the whole reason the
# card is more than a label. Three things to work stand in one option, one per vocabulary
# the guard reads: a widget's own control (the shot's frame, a label injected through
# `offer` that covers the whole image, so this is most of the card's area rather than a
# corner of it), a
# widget's own words (the draft's body, which is deliberately not chrome and so is reached
# only by being inside a widget the option contains), and an element HTML calls
# interactive that no widget put there (the disclosure). A page holding one of the three
# would leave the other two to a guard that had never been asked about them.
INLINE_CASE_PAGE = leaf_page(
    "inline case",
    """
<h1 id="h">The status column</h1>
<lf-options id="rollout" choose>
  <lf-option id="ro-column"><strong>Ship the column</strong>
    <lf-shot id="ro-shot" alt="the run list, before and after the status column"
      before="/media/051bee487bfb5d13.png" after="/media/a99a1b63048502d0.png"></lf-shot>
    <details id="ro-numbers"><summary>What it costs</summary>
      <p id="ro-cost">One join, 40ms at the list's own volume.</p></details>
    <lf-draft id="ro-note"><pre>
Run status now shows on the run list itself.
</pre></lf-draft>
    <p id="ro-column-p">A failure reads off the list instead of costing a click.</p>
  </lf-option>
  <lf-option id="ro-leave"><strong>Leave it</strong>
    <p id="ro-leave-p">A failure stays one click away.</p>
  </lf-option>
</lf-options>
""",
)
CHIP_PAGE = leaf_page(
    "chips",
    """
<h1 id="h">Short facts</h1>
<p id="intro">The store is <span class="tag">experimental</span> for now.</p>
<lf-options id="picks" choose>
  <lf-option id="p-keep"><lf-chip>reversible</lf-chip><strong>Keep the store</strong></lf-option>
</lf-options>
<lf-tasks id="plan">
  <lf-task id="t-camera" status="active" owner="finch"><strong>Mount the camera</strong></lf-task>
</lf-tasks>
""",
)
PAINTED_PAGE = leaf_page(
    "painted",
    """
<h1 id="h">What the paint says</h1>
<lf-timeline id="tl">
  <lf-event id="e-dark" at="09:12" kind="failure"><strong>Feed stopped</strong>
  The north camera went dark and the alert never fired.</lf-event>
</lf-timeline>
<lf-options id="picks">
  <lf-option id="p-stage" recommended><strong>Migrate in stages</strong> Table by table.</lf-option>
  <lf-option id="p-once"><strong>Migrate at once</strong> One window, one cutover.</lf-option>
</lf-options>
<lf-tasks id="plan">
  <lf-task id="t-baffles" status="blocked" owner="finch"><strong>Fit squirrel baffles</strong>
  Waiting on the brackets.</lf-task>
</lf-tasks>
""",
)
SETTLED_ASK_PAGE = ASK_PAGE.replace(
    '<lf-options id="jobs" choose multiple>',
    '<lf-options id="jobs" choose multiple settled>',
)
# Where an exhibit's own boxes begin and end, which is what the marking beside them has
# to meet. A widget that generates no box hands its boxes to the flow — any wrapper a
# style leaves `display: contents` — so a child with no rect is walked through rather
# than skipped, and that is the case no selector in the theme can reach for itself. The runtime's own
# layer is not the exhibit: `.lf-ui` is chrome standing in the page's blocks, and a
# marking drawn around it would be marking the reading rather than the page.
EXHIBIT_EXTENT = """
(id) => {
  const el = document.getElementById(id);
  const label = el.querySelector(':scope > [data-lf-said="label"]');
  let top = Infinity, bottom = -Infinity;
  const walk = (n) => {
    for (const c of n.children) {
      if (c === label || c.classList.contains('lf-ui')) continue;
      const r = c.getBoundingClientRect();
      if (r.height) { top = Math.min(top, r.top); bottom = Math.max(bottom, r.bottom); }
      else walk(c);
    }
  };
  walk(el);
  return {top, bottom, note: label ? label.getBoundingClientRect().bottom : null};
}
"""

SPECIMEN_EXAMPLES = [p for p in EXAMPLES if "<lf-specimen" in p.read_text()]
assert SPECIMEN_EXAMPLES, (
    "no shipped example holds a specimen — the sweep below would drive the fixture "
    "page alone, and the rule it holds is one the corpus is the whole test of"
)
TABLE_REPLY = """The ceilings, unchanged:

| Plan | A minute | Burst | Counted against | Reference |
| --- | --- | --- | --- | --- |
| Free | 60 | 120 | the token | GW-LIMITS-FREE-2026 |
| Enterprise | 6,000 | 12,000 | the token, per environment | GW-LIMITS-ENTERPRISE-2026 |

Taken from https://example.com/gateway/limits/reference/by-plan/current/table
"""
# Two pending changes a line apart, and a third inside a widget that positions
# its own contents — the case where `left: 100%` resolves against the card rather
# than the column, and drops the controls back into the text, unless the row is
# the column's own child.
SUGGESTION_PAGE = leaf_page(
    "suggestions",
    """
<h1 id="h">Feeder notes</h1>
<p id="replace">The camera survey found two dead zones.
  <lf-suggestion id="sug-refill">
    <lf-old>Refill every feeder each morning.</lf-old>
    <lf-new>Refill a feeder when its camera shows it half-empty.</lf-new>
  </lf-suggestion></p>
<p id="insert">Seed mix stays through the migration.
  <lf-suggestion id="sug-thistle">
    <lf-new>Switch the north feeder to thistle in autumn.</lf-new>
  </lf-suggestion></p>
<lf-board id="feeders">
  <lf-column id="col-todo" label="To do">
    <lf-card id="card-heater"><strong>Heated perch</strong>
      <lf-suggestion id="sug-in-card">
        <lf-old>Wire the south feeder.</lf-old>
        <lf-new>Wire the south feeder to the porch circuit.</lf-new>
      </lf-suggestion></lf-card>
  </lf-column>
  <lf-column id="col-done" label="Done"></lf-column>
</lf-board>
""",
)
# All three shapes, because what says "nobody has decided this" differs in each and
# only one of them has a second half to lean on. A replace shows the pair, an insert
# shows a tint against the prose around it, and a pending deletion is a struck line
# with an empty margin beside it — which is also exactly what a deletion looks like
# once it has happened.
PROPOSED_PAGE = leaf_page(
    "proposed",
    """
<h1 id="h">Feeder notes</h1>
<p id="replace">The camera survey found two dead zones.
  <lf-suggestion id="sug-replace">
    <lf-old>Refill every feeder each morning.</lf-old>
    <lf-new>Refill a feeder when its camera shows it half-empty.</lf-new>
  </lf-suggestion></p>
<p id="insert">Seed mix stays through the migration.
  <lf-suggestion id="sug-insert">
    <lf-new>Switch the north feeder to thistle in autumn.</lf-new>
  </lf-suggestion></p>
<p id="delete">The heater runs from the porch circuit.
  <lf-suggestion id="sug-delete">
    <lf-old>Check the thermostat every Sunday.</lf-old>
  </lf-suggestion></p>
""",
)
# A proposal inside an exhibition: the change is a phrase in one of the cases, so the
# variant holding it is as terse as the one beside it. A suggestion is also the one
# family a decision is taken back by rebuilding — no verb can state its authored value,
# so undo hands the widget a pristine clone of the version's markup, and everything the
# runtime had painted on it is on the node the clone replaced.
REBUILT_INLINE_PAGE = leaf_page(
    "stores",
    """
<h1 id="h">Session store</h1>
<lf-compare id="cmp-stores">
  <lf-variant id="v-service"
    ><lf-suggestion id="sug-store"><lf-old>Redis</lf-old><lf-new>Valkey</lf-new></lf-suggestion
    >, one hop from the app</lf-variant
  >
  <lf-variant id="v-cookie">A signed cookie, with nothing to run</lf-variant>
</lf-compare>
""",
)
SWAP_PAGE = leaf_page(
    "swap",
    """
<h1 id="h">Feeder notes</h1>
<p id="swapped">Plans changed.
  <lf-suggestion id="sug-swap">
    <lf-old>Refill every feeder each morning.</lf-old>
    <lf-new>The cameras watch seed levels overnight instead.</lf-new>
  </lf-suggestion></p>
""",
)
COLLAPSED_PAGE = leaf_page(
    "collapsed",
    """
<h1 id="h">Winter</h1>
<p id="stocked">The feeders are stocked.
  <lf-suggestion id="sug-now">
    <lf-new>Thistle goes out in October.</lf-new>
  </lf-suggestion></p>
<details id="later"><summary id="sum">Deferred</summary>
<p id="deferred">Nest boxes wait for spring.
  <lf-suggestion id="sug-boxes">
    <lf-new>Order them in February.</lf-new>
  </lf-suggestion></p>
</details>
""",
)
SHORT_SUGGESTION = leaf_page(
    "short suggestion",
    """
<h1 id="t">Short</h1>
<section id="s">
<lf-suggestion id="sug">
  <lf-old><p id="was">Retry twice.</p></lf-old>
  <lf-new><p id="now">Retry three times.</p></lf-new>
</lf-suggestion>
<p id="after">The backoff is unchanged either way.</p>
</section>
""",
)
# Every animation the page starts, held at time zero so a test can read it rather than
# race it. What it catches is everything through `motion()`, which is the layer's only
# caller of `animate` — the folds and the board's FLIP, each started synchronously
# inside the gesture that causes it. CSS animations run outside it and are never seen,
# `grow` among them. Installed before anything runs, so the first frame is already held.
HOLD_MOTION = """
  window.__lfHeld = [];
  const inner = Element.prototype.animate;
  Element.prototype.animate = function (...args) {
    const motion = inner.apply(this, args);
    motion.pause();
    motion.currentTime = 0;
    window.__lfHeld.push(motion);
    return motion;
  };
"""
# Every shape the ask predicate has to tell apart, on one page: four things the page is
# waiting on the reader for, and, beneath them, one of each way of not being one. The
# four are in document order, because that is the order the walk below must take them in.
ASKS_PAGE = leaf_page(
    "asks",
    """
<h1 id="h">What is still open</h1>
<lf-options id="live-question" label="Where should sessions live?" choose>
  <lf-option id="lq-keep"><strong>Keep the store</strong> Sessions stay where they are.</lf-option>
  <lf-option id="lq-token"><strong>Signed tokens</strong> No store at all.</lf-option>
</lf-options>
<lf-suggestion id="sug-refill">
  <lf-old><p id="refill-was">Refill every feeder each morning.</p></lf-old>
  <lf-new><p id="refill-now">Refill a feeder when its camera says so.</p></lf-new>
</lf-suggestion>
<lf-tasks id="plan">
  <lf-task id="t-mounts" status="done"><strong>Replace the mounts</strong></lf-task>
  <lf-task id="t-baffles" status="review" owner="finch"><strong>Fit squirrel baffles</strong></lf-task>
  <lf-task id="t-bath" status="blocked"><strong>Heat the bird bath</strong></lf-task>
  <lf-task id="t-camera" status="active"><strong>Mount the camera</strong></lf-task>
</lf-tasks>
<lf-options id="honored" choose>
  <lf-option id="hon-tiers" chosen><strong>Two-tier gates</strong></lf-option>
  <lf-option id="hon-one"><strong>One gate</strong></lf-option>
</lf-options>
<lf-options id="retired" choose settled>
  <lf-option id="ret-lax"><strong>Lax cookie</strong></lf-option>
</lf-options>
<lf-options id="exhibited">
  <lf-option id="exh-paper"><strong>Paper maps</strong></lf-option>
</lf-options>
<lf-milestones id="rail">
  <lf-milestone id="m-survey" status="done"><strong>Survey the sites</strong></lf-milestone>
  <lf-milestone id="m-build" status="active"><strong>Build the feeders</strong></lf-milestone>
  <lf-milestone id="m-install" status="blocked"><strong>Install and watch</strong></lf-milestone>
</lf-milestones>
<lf-specimen id="spec" label="a decision">
  <lf-options id="spec-opts" choose>
    <lf-option id="spec-paper"><strong>Paper maps</strong></lf-option>
  </lf-options>
</lf-specimen>
""",
)
ASKS_IN_ORDER = ["live-question", "sug-refill", "t-baffles", "t-bath"]


ASK_WITH_CONTEXT_PAGE = leaf_page(
    "ask with context",
    f"""
<h1 id="h">A decision with context</h1>
{"".join(f"<p id='lead-{i}'>Earlier finding {i}. " + "Background. " * 18 + "</p>" for i in range(8))}
<lf-ask id="storage-ask">
  <h2 id="storage-heading">How the full store behaves</h2>
  <p id="storage-context-1">The beta never reached the cap, so this is the first
  reader's experience of it. The recommendation follows the observed reopen rate.</p>
  <p id="storage-context-2">The options are useful only after that premise is in view;
  arriving straight at them starts in the middle of the question.</p>
  <lf-options id="storage-options" choose label="What should a full store do?">
    <lf-option id="storage-evict"><strong>Drop the oldest documents</strong>
    Editing continues and the server keeps the work.</lf-option>
    <lf-option id="storage-stop"><strong>Pause offline editing</strong>
    Nothing leaves, but the editor becomes read-only.</lf-option>
  </lf-options>
</lf-ask>
{"".join(f"<p id='tail-{i}'>Later finding {i}. " + "Background. " * 18 + "</p>" for i in range(8))}
""",
)
# The ask the walk is standing on. One ask wears the mark, on however many boxes it
# shows through — every shipped widget draws one, and a wrapper a page styles boxless
# hangs it on the boxes its contents make — so what says the walk is in one place is
# the outermost page element wearing it, never the count of elements that do. Scoped to
# main because the asks tray's row mirrors the same fact in the chrome.
STANDING_ASK = "main [data-lf-ask]:not([data-lf-ask] [data-lf-ask])"
# The document's scroll once it has stopped moving. A leaf's travel is a glide, so any
# reading taken while it runs is of a place the gesture passes through rather than of
# where it went — and "the ask is on screen" is one of those places, true for a moment
# in the wrong position before the glide has started. A test that waited on that passed
# with the travel bug put back, which is how this came to be written.
SCROLL_SETTLED = """(hold) => {
  const now = document.body.scrollTop;
  if (now !== window.__lfScroll) {
    window.__lfScroll = now;
    window.__lfScrollSince = performance.now();
    return false;
  }
  return performance.now() - window.__lfScrollSince > hold;
}"""
# Where the tray's rows say their ask's own words, which is the half of a row a static
# lint can never read: the words are whatever the page renders, after every upgrade.
# Every widget that measures a number off a live box, authored into the page and sent in
# a reply, so the two readings of each can be compared instead of pinned to a number. The
# words are the same in both, which is what makes the room they need the same.
ROOM_WIDGETS = """<lf-options id="{id}-q" choose label="Which extras go in?">
  <lf-option id="{id}-tray">A seed tray under the feeder</lf-option>
  <lf-option id="{id}-pole">A second pole for the north pair</lf-option>
</lf-options>
<lf-board id="{id}-b">
  <lf-column id="{id}-todo" label="To do">
    <lf-card id="{id}-brackets"><strong>Steel brackets</strong> For the north pair.</lf-card>
  </lf-column>
  <lf-column id="{id}-done" label="Done">
    <lf-card id="{id}-mounts"><strong>South mounts</strong></lf-card>
  </lf-column>
</lf-board>
<lf-roster id="{id}-r">
  <lf-agent id="{id}-wren" state="working" branch="north-pair">
    <strong>wren</strong> Fitting the brackets.
  </lf-agent>
</lf-roster>"""

# Which element holds each room, and the custom property the theme spends it through.
ROOMS = [("-q", "--lf-word-room"), ("-b", "--lf-grip-room"), ("-r", "--lf-state-room")]

# What the theme is given, asked of the element that states it.
ROOM_HELD = """([id, prop]) => {
  const el = document.getElementById(id);
  return el && getComputedStyle(el).getPropertyValue(prop).trim();
}"""

MESSAGE_ROOM_PAGE = leaf_page(
    "message-room",
    """
<h1 id="mr-h">Bracket order</h1>
"""
    + ROOM_WIDGETS.format(id="mr-page"),
)


ASK_ROW_SAYS = """() => [...document.querySelectorAll('button.lf-asks-row')].map((r) => ({
  at: r.getAttribute('data-lf-at'),
  kind: r.querySelector('.lf-asks-kind').textContent,
  says: r.querySelector('.lf-asks-says').textContent,
  w: Math.round(r.getBoundingClientRect().width),
  h: Math.round(r.getBoundingClientRect().height),
}))"""
CHANGE_SHAPES_PAGE = leaf_page(
    "retry policy",
    """
<h1 id="title">Retry policy</h1>
<lf-suggestion id="sug-rewrite">
  <lf-old><p id="p-job">The worker retries a failed job three times.</p></lf-old>
  <lf-new><p>The worker retries a failed job, then parks it.</p></lf-new>
</lf-suggestion>
<lf-suggestion id="sug-insert">
  <lf-new><p>Parked jobs are listed on the run page.</p></lf-new>
</lf-suggestion>
<lf-suggestion id="sug-delete">
  <lf-old><p id="p-logs">Retries are logged at debug level.</p></lf-old>
</lf-suggestion>
<lf-options id="shapes-q" label="How long should a parked job wait?" choose>
  <lf-option id="wait-day"><strong>A day</strong></lf-option>
  <lf-option id="wait-week"><strong>A week</strong></lf-option>
</lf-options>
""",
)
# A group that takes a pick, so the layer seats a conversation in it (x-conversation),
# and a paragraph beside it so the diff below has one real change to find.
CONVERSATION_DIFF_PAGE = leaf_page(
    "conversation-diff",
    """
<h1 id="cd-h">Bracket order</h1>
<p id="cd-lede">The south pair is up and drawing traffic.</p>
<lf-options id="cd-q" choose label="Which extras go in?">
  <lf-option id="cd-tray">A seed tray under the feeder</lf-option>
  <lf-option id="cd-pole">A second pole for the north pair</lf-option>
</lf-options>
""",
)
LIVE_READING = (
    "The reader is halfway through this account of the cutover and its evidence."
)
LIVE_V1 = leaf_page(
    "Live first",
    """
<h1 id="live-title">Live first</h1>
{lead}
<p id="live-reading">{reading}</p>
{tail}
""",
    head='<meta name="description" content="first">',
).format(
    lead="\n".join(
        f'<p id="live-lead-{i}">Lead {i}. ' + "Context. " * 18 + "</p>"
        for i in range(18)
    ),
    reading=LIVE_READING,
    tail="\n".join(
        f'<p id="live-tail-{i}">Tail {i}. ' + "Context. " * 18 + "</p>"
        for i in range(18)
    ),
)
LIVE_V2 = (
    LIVE_V1.replace("<title>Live first</title>", "<title>Live second</title>")
    .replace(
        'name="description" content="first"', 'name="description" content="second"'
    )
    .replace('<html lang="en">', '<html lang="fr" data-live-root="second">')
    .replace(
        "<body>",
        '<body class="live-second" data-live-body="second" style="--live-body: 2">',
    )
    .replace(
        '<h1 id="live-title">Live first</h1>',
        '<h1 id="live-title">Live second</h1>'
        + "\n".join(
            f'<p id="live-new-{i}">New finding {i}. ' + "Fresh context. " * 18 + "</p>"
            for i in range(5)
        ),
    )
    .replace(
        '<script type="module" src="/leaf.js"></script>',
        '<meta name="lf-review" content="sign-off">\n'
        "<style>#live-reading { --live-cut: 2; }</style>\n"
        '<script type="module" src="/leaf.js"></script>',
    )
)
LIVE_V3 = (
    LIVE_V2.replace("<title>Live second</title>", "<title>Live third</title>")
    .replace(
        'name="description" content="second"', 'name="description" content="third"'
    )
    .replace('<html lang="fr" data-live-root="second">', '<html lang="en">')
    .replace(
        '<body class="live-second" data-live-body="second" style="--live-body: 2">',
        "<body>",
    )
    .replace(
        '<h1 id="live-title">Live second</h1>', '<h1 id="live-title">Live third</h1>'
    )
    .replace('<meta name="lf-review" content="sign-off">\n', "")
    .replace("<style>#live-reading { --live-cut: 2; }</style>\n", "")
)


def live_url(version_url):
    """The stable handover address for a served fixture's authenticated origin."""
    return version_url.split("/versions/", 1)[0] + f"/?t={TOKEN}"


# A section that generates no box of its own, holding blocks that carry no id. The
# reading position's landmark is whichever id stands nearest the block the reader was
# on, so the wrapper is it — which is what a suggestion around whole sections is, and
# what any layer's wrapper may be.
BOXLESS_SECTION_PAGE = leaf_page(
    "boxless section",
    """
<h1 id="t">Boxless</h1>
{lead}
<div id="wrap" style="display: contents">
{held}
</div>
{tail}
""",
).format(
    lead="\n".join(
        f"<p id='lead{i}'>Lead {i}. " + "Filler. " * 20 + "</p>" for i in range(30)
    ),
    held="\n".join(
        f"<p>Held paragraph {i}, standing under a wrapper with no box of its own. "
        + "More words. " * 12
        + "</p>"
        for i in range(6)
    ),
    tail="\n".join(
        f"<p id='tail{i}'>Tail {i}. " + "Filler. " * 20 + "</p>" for i in range(30)
    ),
)
# The same page with the held blocks' opening word changed, so the quote landmark cannot
# re-resolve and the restore falls to the section — the only branch that reads the
# wrapper's own box. The word is the same length, so the two versions lay out
# identically and whatever moves is the restore's doing.
KEPT_SECTION_PAGE = BOXLESS_SECTION_PAGE.replace("Held paragraph", "Kept paragraph")
# Where the wrapper's words are, which is the reading its own rect cannot give.
WRAP_TOP = """() => { const r = document.createRange();
  r.selectNodeContents(document.getElementById('wrap'));
  return Math.round(r.getBoundingClientRect().top); }"""
# The ring, read as a computed style: whether it is drawn, how thick, and in what
# colour. The band is the fact under test, so the three are taken together — a stroke
# that matched in width and not in colour would be two rings that look like one.
RING = """(el) => { const s = getComputedStyle(el);
    return [s.outlineStyle, s.outlineWidth, s.outlineColor]; }"""
# One target of ordinary height and one taller than any viewport, both far enough down
# that arriving at either is a real scroll.
TRAVEL_PAGE = leaf_page(
    "travel",
    f"""
<h1 id="h">Placement</h1>
{"".join(f"<p>Fill paragraph {i}, long enough to take a line of its own.</p>" for i in range(10))}
<lf-diagram id="flow"><pre>
graph LR
  Cart --&gt; Pay
</pre></lf-diagram>
{"".join(f"<p>More fill, paragraph {i}.</p>" for i in range(10))}
<section id="long-part">
<h2>The long tail</h2>
{"".join(f"<p>Tail fill, paragraph {i}, deep enough that the section outgrows any viewport.</p>" for i in range(24))}
</section>
""",
)
# One parent over two leaves, so a status report has to move both the marker and
# the parent's computed done-fraction — the state a stylesheet cannot recount.
REPORT_PAGE = leaf_page(
    "reports",
    """
<h1 id="h">The feeders</h1>
<lf-tasks id="plan">
  <lf-task id="t-feeders" status="active" owner="wren"><strong>Rebuild the feeders</strong>
    <lf-task id="t-mounts" status="done"><strong>Replace the mounts</strong></lf-task>
    <lf-task id="t-parser" status="active"><strong>Fit squirrel baffles</strong></lf-task>
  </lf-task>
</lf-tasks>
""",
)
# Two workers, one claiming work and one idle, because silence is only news against a
# claim: the elapsed line is about what a row said it was doing, not about the clock.
ROSTER_PAGE = leaf_page(
    "fleet",
    """
<h1 id="h">The aviary crew</h1>
<lf-roster id="crew">
  <lf-agent id="ag-wren" state="working" branch="mounts">
    <strong>wren</strong> The feeders.</lf-agent>
  <lf-agent id="ag-finch" state="idle"><strong>finch</strong> Free.</lf-agent>
  <lf-agent id="ag-siskin" state="working"><strong>siskin</strong> Has never reported.</lf-agent>
</lf-roster>
""",
)


def stale_report(page_dir, widget, doing, hours, state="working"):
    """A report the log took `hours` ago. The grace this is written against is a
    quarter of an hour, so nothing that waits can reach it and nothing that sleeps
    should: the fact under test is what the row does with a timestamp, and the log
    is where a timestamp comes from."""
    return interact.append_event(
        page_dir,
        {
            "kind": "report",
            "author": "claude",
            "agent": "wren",
            "widget": widget,
            "action": "state",
            "detail": {"state": state, "doing": doing},
            "version": 1,
            "ts": (datetime.now().astimezone() - timedelta(hours=hours)).isoformat(
                timespec="seconds"
            ),
        },
    )


def backdate_note(page_dir, version, hours):
    """Age the version's own publish note. The floor under a row's freshness is when
    the version asserting it landed, and a version minted seconds ago cannot exercise
    it — so the log, which is a plain file the writer owns, is rewritten rather than
    waited out."""
    path = page_dir / "comments.jsonl"
    when = (datetime.now().astimezone() - timedelta(hours=hours)).isoformat(
        timespec="seconds"
    )
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        if line:
            event = json.loads(line)
            if event["kind"] == "note" and event["version"] == version:
                event["ts"] = when
            line = json.dumps(event, ensure_ascii=False)
        out.append(line)
    path.write_text("\n".join(out), encoding="utf-8")


# One instance for every verb the vocabulary declares an action or a report for, so a
# log holding one event apiece leaves the whole of it standing at once. Selection and
# completion share one option-group unit but occupy distinct facets, so both stand;
# accept and reject share the settlement facet, so two suggestions let both competing
# verbs stand. The floor below derives the list from the registry, so a twelfth widget's
# verb fails here rather than passing unexercised.
STANDING_PAGE = leaf_page(
    "standing state",
    """
<h1 id="ab-t">The v1 cutover</h1>
<lf-options id="ab-pick" choose>
  <lf-option id="ab-shim"><strong>Shim the old schema</strong> Fastest to ship.</lf-option>
  <lf-option id="ab-stage"><strong>Migrate in stages</strong> Table by table.</lf-option>
</lf-options>
<lf-options id="ab-scope" choose>
  <lf-option id="ab-all"><strong>Every caller</strong> Nobody is left on v1.</lf-option>
  <lf-option id="ab-ten"><strong>The top ten</strong> The rest follow in August.</lf-option>
</lf-options>
<lf-board id="ab-work">
  <lf-column id="ab-doing" label="Doing"><lf-card id="ab-importer"><strong>Wire the importer</strong></lf-card></lf-column>
  <lf-column id="ab-done" label="Done"><lf-card id="ab-notes"><strong>Draft the notes</strong></lf-card></lf-column>
</lf-board>
<lf-tasks id="ab-plan">
  <lf-task id="ab-baffles" status="active" owner="wren"><strong>Fit the baffles</strong></lf-task>
</lf-tasks>
<lf-roster id="ab-crew">
  <lf-agent id="ab-wren" state="working"><strong>wren</strong> The importer.</lf-agent>
</lf-roster>
<lf-draft id="ab-email"><pre>The words as this version authored them.</pre></lf-draft>
<lf-suggestion id="ab-sug-410">
  <lf-old><p id="ab-404">The retired response is a plain 404.</p></lf-old>
  <lf-new><p>The retired response is a 410 Gone.</p></lf-new>
</lf-suggestion>
<lf-suggestion id="ab-sug-logs">
  <lf-old><p id="ab-roll">Access logs roll off after 30 days.</p></lf-old>
  <lf-new><p>Access logs are kept for 90 days.</p></lf-new>
</lf-suggestion>
""",
)

# The event that leaves each declared verb standing, written out because a detail is
# the verb's own shape and a schema is no help in inventing one.
#
# Two moves into one column, both to its head, because one move cannot say what this
# gate has to get right. `move` folds by card, so each is its own standing entry, and
# an absolute `#place` states one card's index and nothing about its neighbours: the
# column ends up holding the second above the first, and re-applying the first *alone*
# is supposed to lift it back over. Measured that way the gate called lf-board relative
# and refused a page with nothing wrong with it. The set has to be re-applied in the
# log's order, and with a single move on the page it passed either way.
STANDING_ACTIONS = [
    ("ab-pick", "choose", {"options": ["ab-stage"]}),
    ("ab-pick", "answer", {}),
    ("ab-work", "move", {"card": "ab-importer", "to": "ab-done", "index": 0}),
    ("ab-work", "move", {"card": "ab-notes", "to": "ab-done", "index": 0}),
    ("ab-email", "edit", {"text": "The words as the reader rewrote them."}),
    ("ab-sug-410", "accept", {}),
    ("ab-sug-logs", "reject", {}),
]
RELATIVE_WIDGET_PAGE = leaf_page(
    "relative widget",
    """
<h1 id="tally-title">Squirrel baffles</h1>
<lf-tally id="tally-fitted" count="2">
  <pre>Baffles fitted. Counted on the last walk round.</pre>
</lf-tally>
<lf-tally id="tally-seen" count="0">
  <pre>Nothing at the feeders this week.</pre>
</lf-tally>
""",
)

RELATIVE_WIDGET_MODULE = """\
import { once } from "/leaf.js";

customElements.define(
  "lf-tally",
  class extends HTMLElement {
    connectedCallback() {
      once(this);
    }
    applyAction(action, detail) {
      if (action === "step")
        this.setAttribute(
          "count",
          Number(this.getAttribute("count")) + Number(detail.count),
        );
      if (action === "caption") this.querySelector("pre").append(detail.text);
    }
  },
);
"""
# A widget that stands out of place and settles into it, for the two tests below. The
# distance is more than the blocks under it are tall, so while it is out of place its
# words are over a neighbour's — which is a page the gate reports, and the whole of
# what these tests measure. `offset` is the state and the transform is a rendering of
# it, so the module never reads a position back off the page.
DRIFT_PAGE = leaf_page(
    "a page still settling",
    """
<h1 id="drift-title">The feeders</h1>
<lf-drift id="drift-note" offset="120"><strong>Two greys at the north feeder</strong> They came over the fence at a run, took the sunflower hearts from the hanging tray, and were gone again before the camera on the shed had finished waking up.</lf-drift>
<p id="drift-four">They came back at four and stayed until dusk.</p>
<p id="drift-week">The baffles went up the following week.</p>
<p id="drift-seed">Nothing has been at the seed since.</p>
<p id="drift-count">The count runs again on Sunday.</p>
<p id="drift-sunday">Sunday is when the tally goes in.</p>
""",
)

DRIFT_MODULE = """\
import { motion, once } from "/leaf.js";

customElements.define(
  "lf-drift",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      // `deep` renders the same words from inside the widget's own root, and moves
      // them there: an animation a document-level reading cannot see.
      if (this.hasAttribute("deep")) {
        const root = this.attachShadow({ mode: "open" });
        // `bare` stages the words with no element over them — the page refuses that,
        // and the refusal is what one of the tests below reads.
        if (this.hasAttribute("bare")) {
          root.append(...this.childNodes);
          return;
        }
        const held = document.createElement("div");
        held.append(...this.childNodes);
        root.append(held);
        held.animate(
          [{ transform: "translateY(120px)" }, { transform: "none" }],
          { duration: 30000 },
        );
      }
      this.#place();
    }
    // Absolute, as every applyAction is: the offset is stated, never stepped.
    applyAction(action, detail) {
      if (action !== "settle") return;
      const from = this.getAttribute("offset");
      this.setAttribute("offset", String(detail.offset));
      this.#place();
      // Held at the old offset for nine tenths of the run, so the words are over
      // their neighbour's for as long as the motion lasts. A move that eased the
      // whole way would leave a last fifth of a second in which a reading taken
      // then happened to be clean, and the test would be measuring when the gate
      // looked rather than whether it waited.
      motion(
        this,
        [
          { transform: `translateY(${from}px)` },
          { transform: `translateY(${from}px)`, offset: 0.9 },
          { transform: "none" },
        ],
        1200,
      );
    }
    #place() {
      this.style.transform = `translateY(${this.getAttribute("offset")}px)`;
    }
  },
);
"""


def drifting_widget(tmp_path, monkeypatch, deep=False, bare=False):
    """Vendor <lf-drift> as a project widget, and hand back the page it renders."""
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        interact.cli, ["customize", "widget", "lf-drift", "--upgrade"]
    )
    assert result.exit_code == 0, result.output
    registry_path = tmp_path / ".leaf" / "registry.json"
    entries = json.loads(registry_path.read_text())
    entries["lf-drift"]["properties"]["offset"] = {
        "type": "string",
        "pattern": "^[0-9]+$",
    }
    entries["lf-drift"].setdefault("required", []).append("offset")
    entries["lf-drift"]["x-example"] = entries["lf-drift"]["x-example"].replace(
        'id="drift-example"', 'id="drift-example" offset="120"'
    )
    entries["lf-drift"]["properties"]["deep"] = {"type": "boolean"}
    entries["lf-drift"]["properties"]["bare"] = {"type": "boolean"}
    deep = deep or bare
    if deep:
        # The body is rendered from the widget's own root, so the entry stops
        # claiming the reader gets it verbatim from the markup.
        entries["lf-drift"]["x-shadow"] = True
        del entries["lf-drift"]["x-verbatim"]
    # The registry holds a widget-unit verb to the attribute a version retracts a
    # decision with, so a state channel arrives with its way out of one.
    entries["lf-drift"]["properties"]["restated"] = {"type": "boolean"}
    entries["lf-drift"]["x-state"] = {
        "settle": {
            "detail": {
                "type": "object",
                "properties": {"offset": {"type": "string", "pattern": "^[0-9]+$"}},
                "required": ["offset"],
                "additionalProperties": False,
            },
            "facet": "offset",
            "unit": "widget",
            "record": {"kind": "value", "attr": "offset", "value": "offset"},
        }
    }
    registry_path.write_text(json.dumps(entries, indent=2))
    (tmp_path / ".leaf" / "widgets" / "lf-drift.js").write_text(DRIFT_MODULE)
    if not deep:
        return DRIFT_PAGE
    opens = "<lf-drift deep bare id=" if bare else "<lf-drift deep id="
    return DRIFT_PAGE.replace("<lf-drift id=", opens)


# A suggestion whose losing slot holds a widget. lf-old takes prose, and prose takes
# widgets, so the mark on a chosen option can sit inside the half a decision removes.
# `choose`, because that is the shape that bites: a group offering a pick renders the
# mark as a press, which wears the chrome class *and* declares its word the page's.
RETIRED_WIDGET_PAGE = leaf_page(
    "retired",
    """
<h1 id="h">Session transport</h1>
<p id="lede">Replacing the whole decision block below.</p>
<lf-suggestion id="sug-swap">
  <lf-old id="was">
    <lf-options id="old-group" choose>
      <lf-option id="old-lax" chosen><strong>Lax cookie</strong> The way it stands.</lf-option>
    </lf-options>
  </lf-old>
  <lf-new id="now"><p id="p-now">A bearer header, settled elsewhere.</p></lf-new>
</lf-suggestion>
""",
)


TWO_HOLDER_PAGE = leaf_page(
    "two holders",
    """
<h1 id="th-t">The cache trial</h1>
<lf-trial id="th-cache">
  <lf-current><p id="th-now">The cache is warmed on every deploy.</p></lf-current>
  <lf-proposed><p id="th-next">The cache is warmed on the first request.</p></lf-proposed>
</lf-trial>
""",
)


def trial_family(tmp_path):
    """A third-party settlement family in the project layer, built the way a project
    builds one: `leaf customize widget` scaffolds each tag, and the registry edit
    relates them — x-state verbs on the holders, x-parent/x-retired-when on the
    slots. The holders upgrade, because a tag declaring x-state needs a module to
    define its element; the scaffold module is all they get, so anything a test sees
    settle is the layer's doing, not a module's. Only lf-proposed names two holders,
    for the selector case the two-holder test is about."""
    runner = CliRunner()
    for tag, upgrade in (
        ("lf-trial", True),
        ("lf-pilot", True),
        ("lf-current", False),
        ("lf-proposed", False),
    ):
        made = runner.invoke(
            interact.cli,
            ["customize", "widget", tag, *(["--upgrade"] if upgrade else [])],
        )
        assert made.exit_code == 0, made.output
    source = tmp_path / ".leaf" / "registry.json"
    entries = json.loads(source.read_text())
    verb = {
        "detail": {"type": "object", "additionalProperties": False},
        "facet": "settlement",
        "unit": "widget",
    }
    example = {
        "lf-trial": '<lf-trial id="x-trial"><lf-current><p>As it stands.</p></lf-current>'
        "<lf-proposed><p>As proposed.</p></lf-proposed></lf-trial>",
        "lf-pilot": '<lf-pilot id="x-pilot"><lf-proposed><p>As proposed.</p>'
        "</lf-proposed></lf-pilot>",
    }
    # `pause` settles nothing: the widget-unit verb that displaces a decision in
    # the fold, there for the test that holds the mark to following it out.
    for tag, state in (
        ("lf-trial", ("adopt", "shelve", "pause")),
        ("lf-pilot", ("run", "shelve")),
    ):
        entries[tag]["x-state"] = {name: dict(verb) for name in state}
        entries[tag]["properties"]["restated"] = {"type": "boolean"}
        entries[tag]["x-content"] = "items"
        entries[tag]["x-example"] = example[tag]
    for tag, holders, outcome in (
        ("lf-current", ["lf-trial"], "adopt"),
        ("lf-proposed", ["lf-trial", "lf-pilot"], "shelve"),
    ):
        entries[tag] |= {"x-parent": holders, "x-retired-when": outcome}
        entries[tag].pop("x-example", None)
        entries[tag].pop("required", None)
    source.write_text(json.dumps(entries))
    # The scaffold styles every tag as a card; a slot is a slot, the way the shipped
    # family's lf-old/lf-new draw no box of their own. Left as cards, the slots carry
    # margins that stand trapped under the holder's frame once a settled sibling is
    # hidden — a real TRAPPED_MARGINS finding about the fixture, not about the gate.
    theme = tmp_path / ".leaf" / "theme.css"
    theme.write_text(
        theme.read_text() + "\nlf-current, lf-proposed "
        "{ display: block; margin: 0; padding: 0; border: none; --lf-frame: initial; }\n"
    )


# The two-holder page with a second, undecided trial beside the first: the instance a
# module that invents settlement gets caught on, since on the decided one its mark
# only repeats the log.
TWO_HOLDER_SPARE_PAGE = TWO_HOLDER_PAGE.replace(
    "</main>",
    """<lf-trial id="th-spare">
  <lf-current><p id="sp-now">The spare stands as it is.</p></lf-current>
  <lf-proposed><p id="sp-next">The spare would move.</p></lf-proposed>
</lf-trial>
</main>""",
)
MARKDOWN_REPLY = """Two things, then the fix — details in https://example.com/notes:

- the poll drops a response **behind** the one already rendered
- `lastEventSeq` is what it compares, a Vec<T> of them

```python
def resolve(a, b):
    return a if a.seq > b.seq else b
```

> which one wins?
"""
REF_PAGE = leaf_page(
    "refs",
    f"""
<h1 id="h">Feeder placement</h1>
{"".join(f"<p>Fill paragraph {i}, long enough to take a line of its own.</p>" for i in range(10))}
<lf-tabs id="projects">
  <lf-tab id="tab-feeders" label="Winter feeders">
    <p id="p-feeders">Two of the four feeders are mounted.</p>
  </lf-tab>
  <lf-tab id="tab-bath" label="Heated bird bath">
    <p id="p-bath">The thermostat arrived cracked and a replacement is on order.</p>
  </lf-tab>
</lf-tabs>
<section id="tail">
{"".join(f"<p>Tail fill, paragraph {i}, long enough to stand as a landmark of its own.</p>" for i in range(16))}
<p id="tail-end">The last words on the page, where a reader who read to the end is.</p>
</section>
""",
)
THREAD_ASKS = [
    {
        "kind": "comment",
        "id": "c-which",
        "author": "claude",
        "version": 1,
        "text": "Which store?",
        "markup": '<lf-options id="tq-one" choose>'
        '<lf-option id="tq-redis">Redis</lf-option>'
        '<lf-option id="tq-cookie">Signed cookie</lf-option>'
        "</lf-options>",
    },
    {
        "kind": "comment",
        "id": "c-any",
        "author": "claude",
        "version": 1,
        "text": "Pick any that apply.",
        "markup": '<lf-options id="tq-set" choose multiple>'
        '<lf-option id="tq-logs">Logs</lf-option>'
        '<lf-option id="tq-metrics">Metrics</lf-option>'
        "</lf-options>",
    },
]
ADDRESS_PAGE = leaf_page(
    "addresses",
    """
<h1 id="h">Two questions, two forms</h1>
<lf-options id="cards" choose>
  <lf-option id="c-heater"><strong>Immersion heater</strong> Drops into the basin.</lf-option>
  <lf-option id="c-cable"><strong>Heated cable</strong> A cord across the base.</lf-option>
  <lf-option id="c-hand"><strong>Break the ice</strong> Someone goes out each morning.</lf-option>
</lf-options>
<p id="plan">The camera mount is the part nobody has costed.</p>
<lf-options id="rows" choose>
  <lf-option id="r-now" for="plan">Cost it now</lf-option>
  <lf-option id="r-later" for="plan">Leave it for the spring</lf-option>
</lf-options>
""",
)

# The first ancestor that cuts this element, and by how much. `overflow` and `clip-path`
# cut at the padding box, so the border comes off the ancestor's own box before the
# comparison; half a pixel of tolerance for subpixel layout.
CLIPPED_BY = """el => {
    const r = el.getBoundingClientRect();
    for (let p = el.parentElement; p; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (s.overflow === "visible" && s.clipPath === "none") continue;
      const b = p.getBoundingClientRect();
      const box = {left: b.left + parseFloat(s.borderLeftWidth),
                   right: b.right - parseFloat(s.borderRightWidth),
                   top: b.top + parseFloat(s.borderTopWidth),
                   bottom: b.bottom - parseFloat(s.borderBottomWidth)};
      const cut = {left: box.left - r.left, right: r.right - box.right,
                   top: box.top - r.top, bottom: r.bottom - box.bottom};
      const worst = Math.max(...Object.values(cut));
      if (worst > 0.5)
        return {by: p.tagName.toLowerCase() + (p.id ? "#" + p.id : ""),
                overflow: s.overflow, px: +worst.toFixed(1)};
    }
    return null;
}"""


# Any of the group's own words this element is drawn over, taken a rendered line at a
# time (a wrapped run's box spans the whole column and would answer for a line the chip
# is nowhere near). The runtime's own chrome is not the page's words, so it is skipped.
OVER_WORDS = """(el, id) => {
    const group = document.getElementById(id).closest("lf-options");
    const r = el.getBoundingClientRect();
    const walk = document.createTreeWalker(group, NodeFilter.SHOW_TEXT);
    for (let n = walk.nextNode(); n; n = walk.nextNode()) {
      if (!n.textContent.trim() || n.parentElement.closest(".lf-ui")) continue;
      const range = document.createRange();
      range.selectNodeContents(n);
      for (const b of range.getClientRects())
        if (r.right > b.left && r.left < b.right && r.bottom > b.top && r.top < b.bottom)
          return n.textContent.trim().slice(0, 24);
    }
    return null;
}"""

# Where the chip sits in the option holding it: from its corner, against the option's own
# middle, and whether it reaches past the bottom. Every rect in one pass, because these are
# differences between boxes and a difference is only a fact if both sides were read at one
# instant.
#
# `level` is the middle of the box the row's words fill, not the middle of the first line,
# which is what the row's rule actually promises: a label long enough to wrap carries its
# digit down with it, 13.7px below that first line on a two-line row. Asked of the first
# line this would fail a perfectly good layout the day a shipped label grew a word. It is
# the content box and not the border box, so that a row whose padding stopped being
# symmetric — which is the whole of why centring on the box centres on the words — is a
# failure and not a pass.
#
# Two `bounding_box()` calls are two instants, and the page moves between them: a viewport
# rect is relative to the scroller, so a scroll landing between the two reads is subtracted
# straight into the answer. `n` scrolls to the ask it steps to, the body is the scroller,
# and a page whose content sits on fractional pixels settles that scroll across a frame —
# so the chip's offset came back a pixel out on about half of the runs, on whichever row
# the frame happened to fall between. Nothing had moved by then except the window, which is
# the one thing this measurement is not about.
#
# Every reading is stated from the option's padding box, because that is where the chip is
# placed from and where the option's own room starts: a joined cell wears the hairline
# below it as its own border, so measured from the border box, the last cell of every
# group would sit one pixel apart from the rest while the page shows them level.
INSIDE_ITS_OPTION = """el => {
    const chip = el.getBoundingClientRect();
    const opt = el.parentElement.getBoundingClientRect();
    const s = getComputedStyle(el.parentElement);
    const top = opt.y + parseFloat(s.borderTopWidth);
    const left = opt.x + parseFloat(s.borderLeftWidth);
    const bottom = opt.bottom - parseFloat(s.borderBottomWidth);
    const above = parseFloat(s.paddingTop), below = parseFloat(s.paddingBottom);
    const words = top + above + (bottom - top - above - below) / 2;
    return {x: chip.x - left, y: chip.y - top, past: chip.bottom - bottom,
            level: (chip.y + chip.height / 2) - words};
}"""


def painted(page, name):
    """What the page is painting under a highlight name, whitespace-flattened. Marks are
    ranges in the highlight registry, not elements, so this is where a test looks."""
    return " ".join(
        page.evaluate(
            """(name) => {
        const h = CSS.highlights.get(name);
        return h ? [...h].map(r => r.toString()).join('') : '';
    }""",
            name,
        ).split()
    )


def pending_text(page):
    return painted(page, "lf-pending")


def mark_point(page, name, index=0):
    """A point inside a painted range, for a real mouse press. A highlight is not an
    element, so there is nothing for a locator to click.

    On screen, and asserted here, because a press the reader cannot make proves nothing
    about what a press does. A range keeps its client rects while it is scrolled away —
    they simply go negative — so the arithmetic above will hand back a point above the
    window as readily as one in it, and `page.mouse` will press there. Nothing in the
    page hears that press: `elementFromPoint` answers null outside the window, the
    runtime's hit test declines a point that is over none of the page's words, and the
    click arrives at `<html>`. A caller pressing 141px above the top edge therefore read
    the silence that followed as the mark's thread refusing to open, 30 seconds later
    and in another function."""
    box = page.evaluate(
        """([name, index]) => {
        const r = [...CSS.highlights.get(name)][index].getClientRects()[0];
        return {x: r.left + r.width / 2, y: r.top + r.height / 2,
                w: innerWidth, h: innerHeight};
    }""",
        [name, index],
    )
    assert 0 <= box["x"] < box["w"] and 0 <= box["y"] < box["h"], (
        f"the {name} mark at index {index} is painted at ({box['x']:.0f}, "
        f"{box['y']:.0f}), off a {box['w']:.0f}×{box['h']:.0f} window — scroll the "
        f"passage into view before pressing it"
    )
    return box["x"], box["y"]


def composer_quote(page):
    """What the composer says about its own passage, and whether the reader can see it.
    The node stays in the accessibility tree either way — a painted mark has no exposure,
    so it is the box's aria description — which is why this asks the class, not the text."""
    return page.evaluate("""() => {
        const q = document.getElementById('lf-composer-quote');
        return {text: q.textContent, shown: !q.classList.contains('lf-unseen')};
    }""")


def mark_shows_beside_composer(page):
    """Whether any of the composer's own mark is on screen and not behind the box. The mark
    is the only thing naming the passage the box is about, so a box covering all of it is a
    box about nothing — which no state may reach."""
    return page.evaluate("""() => {
        const box = document.querySelector('.lf-composer').getBoundingClientRect();
        const rects = [...(CSS.highlights.get('lf-pending') ?? [])]
            .flatMap(r => [...r.getClientRects()])
            .concat([...document.querySelectorAll('.lf-mark-el.lf-pending')]
                .map(e => e.getBoundingClientRect()));
        const onScreen = (r) => r.right > 0 && r.left < innerWidth
                             && r.bottom > 48 && r.top < innerHeight;
        const behind = (r) => r.left >= box.left && r.right <= box.right
                           && r.top >= box.top && r.bottom <= box.bottom;
        return rects.some(r => onScreen(r) && !behind(r));
    }""")


# Every list the g chord addresses, on one page: comments (the test adds them), an ask,
# links, and a disclosure. The lists have to stand together, because what the chord is for
# is that one letter chooses between them.
ADDRESSED_PAGE = leaf_page(
    "addressed",
    """
<h1 id="t">Addressed</h1>
<p id="p1">The first passage under discussion, with words
enough for two separate remarks to land in it.</p>
<p id="refs">See <a id="lk1" href="#p1">the first passage, whose link text is long
enough that it runs past the end of one line and carries on onto the next</a>, and then
<a id="lk2" href="#p2">the second</a>.</p>
<details id="dsc"><summary id="dsc-head">What the store costs</summary>
<p id="dsc-body">A replica in each region, and a read on every request that carries a
session.</p></details>
<lf-options id="opts" choose>
  <lf-option id="opt-a"><strong>Keep the store</strong> Sessions stay where they are,
  which costs a replica and buys revocation for free.</lf-option>
  <lf-option id="opt-b"><strong>Signed tokens</strong> No store at all, until revocation
  quietly puts one back.</lf-option>
</lf-options>
<p id="p2">A short second passage.</p>
{tail}
""",
).format(
    # Enough page below the ask that it can be scrolled up under the banner, which is where
    # a chip placed from the page's geometry alone lands on the status line.
    tail="\n".join(
        f"<p id='t{i}'>Tail {i}. " + "Words. " * 20 + "</p>" for i in range(12)
    )
)
# What the chord is offering right now, in the order it drew it. Read through the
# retrying assertion rather than evaluated: the chips are painted on a frame of the
# runtime's own (paintHere), so a press and a plain read race each other. Each chip says
# a whole address, so one reading answers which lists are on offer, which members of
# each, and in what order — three facts a count and a bare digit answered separately.
CHIPS = ".lf-addresses > .lf-address"


NOTED_PAGE = leaf_page(
    "noted",
    """
<h1 id="t">Noted</h1>
<p id="p1">The first passage under discussion, with words
enough for two separate remarks to land in it.</p>
<p id="p2">A short second passage.</p>
<figure id="fig"><svg viewBox="0 0 120 40" width="120" height="40" role="img"
aria-label="specimen"><rect x="2" y="2" width="116" height="36" fill="none"
stroke="currentColor"></rect></svg><figcaption>A figure, for element anchors.</figcaption></figure>
""",
)


def standing_mark(page):
    """Which passage the page is painting as the comment the reader is standing in, and
    which elements wear the same fact as an outline. One reading, because the two are one
    paint over two kinds of anchor and a test that asked for only the text half would go
    green on a page whose element marks had stopped answering."""
    return {
        "text": painted(page, "lf-mark-here"),
        "elements": page.evaluate(
            "() => [...document.querySelectorAll('.lf-mark-here')].map(e => e.id)"
        ),
    }


STANDING = """([text, ids]) => {
    const h = CSS.highlights.get('lf-mark-here');
    const said = (h ? [...h].map(r => r.toString()).join('') : '').split(/\\s+/)
        .filter(Boolean).join(' ');
    const on = [...document.querySelectorAll('.lf-mark-here')].map(e => e.id);
    return said === text && String(on) === String(ids);
}"""


def wait_standing(page, text, ids=()):
    """Wait for the page to be marking exactly this comment's passage.

    The paint follows the focus through the runtime's one coalesced repaint (paintHere),
    so it lands a frame after the press that moved the reader. Reading straight after the
    key reads the press before its answer, and passes or fails on how loaded the machine
    is. The failure carries what was painted instead, since a timeout on a predicate says
    only that it never came true."""
    try:
        page.wait_for_function(STANDING, arg=[text, list(ids)], timeout=4000)
    except PlaywrightTimeout:
        raise AssertionError(
            f"the page should be marking {text or list(ids)!r} as the comment the reader"
            f" is standing in; it is marking {standing_mark(page)}"
        ) from None


def hide_scroll_operation_promises(page):
    """Exercise the scrollend path used by current Firefox and Safari."""
    page.evaluate("""() => {
        const scrollTo = document.body.scrollTo.bind(document.body);
        document.body.scrollTo = options => { scrollTo(options); };
        const scrollIntoView = Element.prototype.scrollIntoView;
        Element.prototype.scrollIntoView = function(options) {
            scrollIntoView.call(this, options);
        };
    }""")


def hold_arrival_scroll_ends(page):
    """Hold each fallback edge so an arrival can be inspected between operations."""
    page.evaluate("""() => {
        const add = document.body.addEventListener.bind(document.body);
        const remove = document.body.removeEventListener.bind(document.body);
        window.__lfHeldScrollEnds = new Set();
        document.body.addEventListener = (type, listener, options) => {
            if (type === 'scrollend') {
                window.__lfHeldScrollEnds.add(listener);
                return;
            }
            return add(type, listener, options);
        };
        document.body.removeEventListener = (type, listener, options) => {
            if (type === 'scrollend') {
                window.__lfHeldScrollEnds.delete(listener);
                return;
            }
            return remove(type, listener, options);
        };
        const scrollIntoView = Element.prototype.scrollIntoView;
        Element.prototype.scrollIntoView = function(options) {
            if (this.closest('.lf-ui')) scrollIntoView.call(this, options);
            else document.body.scrollTop += 1;
        };
        const scrollTo = document.body.scrollTo.bind(document.body);
        window.__lfSmoothGoals = [];
        document.body.scrollTo = options => {
            if (options?.behavior === 'smooth') {
                window.__lfSmoothGoals.push(options.top);
                return;
            }
            scrollTo(options);
        };
        window.__lfArrivalStarts = 0;
        document.addEventListener('animationstart', event => {
            if (event.animationName.endsWith('-arrive')) window.__lfArrivalStarts++;
        }, true);
        window.__lfReleaseScrollEnd = () => {
            const listener = [...window.__lfHeldScrollEnds][0];
            if (!listener) throw new Error('no held scrollend');
            listener(new Event('scrollend'));
        };
    }""")


HOVERED = """(text) => {
    const h = CSS.highlights.get('lf-mark-hover');
    const said = (h ? [...h].map(r => r.toString()).join('') : '').split(/\\s+/)
        .filter(Boolean).join(' ');
    return said === text;
}"""


def wait_hovered(page, text):
    """Wait for the page to be lighting exactly this passage under the pointer.

    Answered in a coalesced frame rather than in the move itself: the page's half reads
    layout, and the panel's half reads the browser's own :hover, which that frame is also
    what settles. Reading straight after the move reads the move before its answer."""
    try:
        page.wait_for_function(HOVERED, arg=text, timeout=4000)
    except PlaywrightTimeout:
        raise AssertionError(
            f"the pointer should be lighting {text!r} on the page; it is lighting"
            f" {painted(page, 'lf-mark-hover')!r}"
        ) from None


def card_body(page, says):
    """A point low on a comment's card, below the quote — where a reader's hand rests
    while they read the comment, and where nothing presses."""
    box = page.locator(".lf-thread").filter(has_text=says).first.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] - 8


# Addressable things that start within a chip's width of each other: a run of footnote
# markers, and a link that is the whole of a summary — the second being a member of two
# lists at one corner, which nothing could produce while only one list painted at a time.
CROWDED_PAGE = leaf_page(
    "crowded",
    """
<h1 id="t">Crowded</h1>
<p id="notes">Claims rest on sources<a id="fn1" href="#s1">1</a><a id="fn2" href="#s2">2</a><a
id="fn3" href="#s3">3</a> and are checked below.</p>
<details id="dsc"><summary id="dsc-head"><a id="lk-sum" href="#s1">The sources</a></summary>
<p id="s1">One.</p><p id="s2">Two.</p><p id="s3">Three.</p></details>
""",
)
# Links all the way down, so one of them starts in the corner the key line stands in.
FOOTED_PAGE = leaf_page(
    "footed",
    """
<h1 id="t">Footed</h1>
"""
    + "\n".join(
        f'<p id="p{i}"><a id="lk{i}" href="#t">Source {i}</a> says so, at some length, with '
        + "words enough to carry the paragraph onto a second line. " * 2
        + "</p>"
        for i in range(9)
    ),
)
# c's three destinations on one page: prose to select, a visual to click (no words to
# quote, so it anchors on the element), and the page itself with neither in hand.
TARGETS_PAGE = leaf_page(
    "targets",
    """
<h1 id="t">Targets</h1>
<p id="prose">A paragraph with enough words in it to select by dragging across, which
is what raises the button the key then presses.</p>
<figure id="fig"><svg viewBox="0 0 240 60" width="240" height="60" role="img"
aria-label="specimen"><rect x="2" y="2" width="236" height="56" fill="none"
stroke="currentColor"></rect></svg><figcaption>A specimen.</figcaption></figure>
""",
)
UNDO_PAGE = leaf_page(
    "undo",
    """
<h1 id="h">Undo</h1>
<lf-draft id="note-cli"><pre>
First line of the note.

Second paragraph of the note.
</pre></lf-draft>
<lf-options id="picks" choose>
  <lf-option id="opt-a">Keep the mounts</lf-option>
  <lf-option id="opt-b" chosen>Replace the mounts</lf-option>
</lf-options>
""",
)


def actions(page_dir):
    return [e for e in interact.read_events(page_dir) if e["kind"] == "action"]


NESTED_SUGGESTION = SUGGESTION_PAGE.replace(
    "<lf-new>Switch the north feeder to thistle in autumn.</lf-new>",
    "<lf-new>Switch the north feeder to thistle in autumn."
    '<lf-options id="blend" choose>'
    '<lf-option id="blend-nyjer">Nyjer only</lf-option>'
    '<lf-option id="blend-mixed">Mixed thistle</lf-option>'
    "</lf-options></lf-new>",
)
FENCED_CAPTURE_PAGE = leaf_page(
    "fenced capture",
    """
<h1 id="h">Roadmap</h1>
<lf-milestones>
  <lf-milestone id="gate-milestone" status="active" when="week-1" tags="wood,solar">
    <strong>Build feeders</strong> Two classic models.
  </lf-milestone>
</lf-milestones>
<p id="after-milestone">Ready next.</p>
<lf-options id="fence-options">
  <lf-option id="fence-option"><lf-chip>effort: low</lf-chip><lf-chip>risk: high</lf-chip>
    <strong>Classic feeder</strong> Easy to clean.
  </lf-option>
</lf-options>
""",
)
# A label a widget renders into a control it also built. The tab strip is the case with
# nowhere else to say it: once the strip exists the panel heading stands down, so the
# button is the panel's only name. Every word here is distinct, so a quote can only
# anchor where it was picked, and the panels are long enough that a drag across one of
# these labels is an ordinary drag.
CONTROL_LABEL_PAGE = leaf_page(
    "labels",
    """
<h1 id="h">Aviary projects</h1>
<p id="lede">Two workstreams, one page.</p>
<lf-tabs id="projects">
  <lf-tab id="tab-feeders" label="Winter feeders">
    <p id="p-feeders">Two of the four feeders are mounted; the south pair waits on brackets.</p>
  </lf-tab>
  <lf-tab id="tab-bath" label="Heated bird bath">
    <p id="p-bath">The thermostat arrived cracked and a replacement is on order.</p>
  </lf-tab>
</lf-tabs>
""",
)
CODE_PAGE = leaf_page(
    "code",
    """
<h1 id="t">Code</h1>
<section id="walk">
<p id="lede">The key changes shape:</p>
<lf-code id="walk-code" language="python" hi="2"><pre>
def bucket_key(request):
    if request.token:
        return f"tok:{request.token.id}"
    return "anon"
</pre>
<lf-note at="2">A token id shaped like an address would collide.</lf-note>
</lf-code>
<pre><code class="language-bash"># apply the migration, then run the marked suite
cd gateway &amp;&amp; alembic upgrade head</code></pre>
<lf-code id="plain-code"><pre>
$ leaf version check ./page --render
v1.html: renders clean
</pre></lf-code>
</section>
""",
)
# A diff of three files, one per thing the colouring has to get right: a Python file
# whose second hunk moves a docstring across lines and whose two sides disagree about
# what is open, a yaml file (the grammar that reads a leading `-` as a sequence bullet
# and a leading `+` as a string, so the prefix column has to be off before it looks),
# and a file whose extension names no language at all.
DIFF_PAGE = leaf_page(
    "diff",
    """
<h1 id="t">Diff</h1>
<lf-diff id="patch"><pre>
diff --git a/gateway/limits.py b/gateway/limits.py
--- a/gateway/limits.py
+++ b/gateway/limits.py
@@ -38,7 +38,8 @@ class Limiter:
     def bucket_key(self, request):
-        return request.remote_addr
\\ No newline at end of file
+        if request.token:
+            return f"tok:{request.token.id}"
@@ -71,5 +73,7 @@ class Limiter:
     def reset(self, key):
-        \"\"\"Drop one bucket.
-        Called on logout.\"\"\"
+        \"\"\"Drop one bucket, prefix and all.
+
+        Called on logout, and once per renamed key.
+        \"\"\"
         self.buckets.pop(key, None)
diff --git a/gateway/config.yaml b/gateway/config.yaml
--- a/gateway/config.yaml
+++ b/gateway/config.yaml
@@ -4,6 +4,6 @@ ratelimit:
-  burst: 20
+  burst: 40
   window: 60
diff --git a/deploy/Dockerfile b/deploy/Dockerfile
--- a/deploy/Dockerfile
+++ b/deploy/Dockerfile
@@ -9,2 +9,2 @@ COPY gateway /srv/gateway
-RUN pip install -r requirements.txt
+RUN pip install --no-cache-dir -r requirements.txt
</pre></lf-diff>
""",
)
# One change block per thing the word marks have to get right, and nothing else in the
# diff. A pair that edited one argument, with git's `\\ No newline` remark standing
# between the two lines; a block of three deletions under two additions, so the third has
# nothing to be compared against; a context line separating that block from the next, so
# a deletion under it answers the addition under it and not the leftover above; a pair
# that swapped wholesale, which shares no words to mark; two pairs written one under the
# other, where a deletion following an addition is what ends the block with nothing else
# to say so; a block that grew by two lines, so the addition answering the deletion is
# three lines under it rather than beside it; a block that reordered without growing, so
# there is no answer the count difference allows the search to reach; and a file whose
# path names no language, where the same marks have to land on a line no tokenizer ever
# touched.
#
# `limit = 3` is the leftover and `limit = 8` opens the block after the context line, so
# a walk that ran the two blocks together would pair the leftover against `limit = 9` and
# mark it — the fault that reads as one mark too many rather than as none at all.
MOVED_WORDS_PAGE = leaf_page(
    "moved words",
    """
<h1 id="t">Moved words</h1>
<lf-diff id="patch"><pre>
diff --git a/gateway/limits.py b/gateway/limits.py
--- a/gateway/limits.py
+++ b/gateway/limits.py
@@ -3,4 +3,4 @@ class Limiter:
     def reset(self, key):
-        self.buckets.pop(key, None)
\\ No newline at end of file
+        self.buckets.pop(key, 0)
         return None
@@ -20,8 +20,7 @@ class Limiter:
-        alpha = compute(one, two)
-        beta = compute(three, four)
-        limit = 3
+        alpha = compute(one, five)
+        beta = compute(nine, four)
         self.reset(key)
-        limit = 8
+        limit = 9
@@ -40,3 +39,3 @@ class Limiter:
-        return self.buckets[key].take()
+        raise RuntimeError("no such thing")
@@ -60,4 +59,4 @@ class Limiter:
-        window = 60
+        window = 90
-        burst = 20
+        burst = 40
@@ -80,2 +79,4 @@ class Limiter:
-        return self.tokens[key].take()
+        if key not in self.tokens:
+            self.tokens[key] = Bucket()
+        return self.tokens[key].fill(rate)
@@ -100,4 +99,4 @@ class Limiter:
-        return None
-        soft = 60
-        hard = 20
+
+        soft = 90
+        hard = 40
diff --git a/deploy/Dockerfile b/deploy/Dockerfile
--- a/deploy/Dockerfile
+++ b/deploy/Dockerfile
@@ -9,2 +9,2 @@ COPY gateway /srv/gateway
-RUN pip install -r requirements.txt
+RUN pip install -r reqs.txt
@@ -20,2 +20,2 @@ WORKDIR /srv
-EXPOSE 8080
-CMD ["gunicorn", "gateway:app"]
+CMD ["gunicorn", "gateway:app", "-w", "4"]
+EXPOSE 9090
</pre></lf-diff>
""",
)
# A page carrying both kinds of native control a widget injects: a checkbox in the light
# DOM and a <summary> the widget staged in a shadow tree.
NATIVE_CONTROL_PAGE = DIFF_PAGE.replace(
    "</main>",
    f"""<lf-shot id="shot-keys" alt="the navigation rail"
         before="{SHOT_SRC["before"]}" after="{SHOT_SRC["after"]}"></lf-shot>
</main>""",
)
# A page that says the same thing twice *within one section*, which is the only case a
# quote alone cannot place — scoping to a section already separates copies that live under
# different ids. A unified diff is the case that matters and the reason the section can't
# help: it holds the changed line on both sides, under one id, so the two occurrences are a
# bug and its fix, and landing on the wrong one inverts what the comment means.
TWICE_PAGE = leaf_page(
    "twice",
    """
<h1 id="t">Twice</h1>
<section id="repeat">
<p>Ahead of the repeat, so the copies have different neighbours before them.</p>
<p>A first copy follows. The version stamp never lands. And a first tail after it.</p>
<p>Something else entirely, so the two copies do not touch each other.</p>
<p>A second copy follows. The version stamp never lands. And a second tail after it.</p>
</section>
<lf-diff id="patch"><pre>
diff --git a/gateway/cache.py b/gateway/cache.py
--- a/gateway/cache.py
+++ b/gateway/cache.py
@@ -18,7 +18,7 @@ class Bucket:
 def key(self, request):
-    return request.path
+    return request.path, request.headers.get("Accept")
 def store(self, request):
</pre></lf-diff>
""",
)
DRIFT_V1 = leaf_page(
    "drift",
    """
<h1 id="t">Drift</h1>
<section id="drift">
<p>Cache warmup runs first. {phrase}. Retries are capped at three.</p>
<p>Queue drain runs first. {phrase}. Retries are capped at four.</p>
</section>
""",
).replace("{phrase}", "The version stamp never lands")
# v2 rewrites the words on both sides of the *commented* copy and leaves the other alone,
# so the untouched copy is now the better match for the context the comment stored.
DRIFT_V2 = DRIFT_V1.replace(
    "Cache warmup runs first.", "Cache warmup is gone now."
).replace("lands. Retries are capped at three.", "lands. Backoff is capped at three.")
# A passage among padded emoji, which is the only shape that catches the seam between how a
# context is stored and how it is compared: astral characters make the stored string longer
# in code units than in the code points the capture counted, and the padding makes the
# search's window collapse to less than it read. Both are needed, and the padding is tuned
# rather than decorative — a marker plus three spaces collapses 5 units to 3, which leaves
# the pre-fix window just short of the stored length. Two spaces and it is already long
# enough; five and the window doubles and overshoots. Tied to CONTEXT = 24, and to markers
# outside the BMP: ✅ and ⚠ are one code unit each and will not do it.
# The two inputs a well-meaning edit would touch, asserted so the fixture can't quietly
# stop guarding: BMP symbols and padding outside the band both leave the pre-fix code
# passing, and neither shows up as a failure anywhere.
MARKERS = "🔴🟢🟡🔵🟣🟤🟠🟥🟩🟦🔴🟢🟡🔵🟣🟤"
PAD = "   "
assert all(ord(c) > 0xFFFF for c in MARKERS), "BMP markers will not reproduce this"
assert len(PAD) in (3, 4), "outside the band the window is long enough either way"
ASTRAL_PAGE = (
    leaf_page(
        "astral",
        """
<h1 id="t">Astral</h1>
<section id="astral">
<p>Ordinary prose ahead of the first copy here. {phrase} and a tail.</p>
<p>A divider paragraph between the copies.</p>
<p>{run}{phrase} and a tail.</p>
</section>
""",
    )
    .replace("{run}", "".join(m + PAD for m in MARKERS))
    .replace("{phrase}", "TARGET PHRASE")
)
# Two copies of one phrase behind an identical lead, the second closing its section. The
# words that tell them apart are the next section's, which only a capture reading past the
# section edge can store.
EDGE_PAGE = leaf_page(
    "edge",
    """
<h1 id="t">Edge</h1>
<section id="edge">
<p>First pass: when the deploy fails again in the night, the run is retried until it lands. Nothing else moves.</p>
<p>Second pass: when the deploy fails again in the night, the run is retried until it lands.</p>
</section>
<section id="tail">
<p>Rollout resumes once the queue drains completely.</p>
</section>
""",
)


# The same page with nothing after the section, so the closing copy ends the document —
# the one place no capture can supply a second side. What it stores there is an empty
# suffix, which says the passage had nothing after it anywhere on the page, and only one
# occurrence can be somewhere that is still true of.
TAIL_PAGE = EDGE_PAGE.replace(
    """<section id="tail">
<p>Rollout resumes once the queue drains completely.</p>
</section>
""",
    "",
)
assert TAIL_PAGE != EDGE_PAGE, (
    "the section this removes has moved; the contrast is gone"
)
# A passage longer than the search's pattern, twice over, so the pattern's own lead
# matches both copies and only their neighbours tell them apart. Prose rather than
# filler, because the walk that confirms the rest of a quote steps word by word.
LONG_PASSAGE = "Note: the migration replays on every deploy because the version stamp never lands, and the guard reads a column the writer never fills, and the whole batch runs again from the top on each release, and the counters disagree with the log and with each other, and the retry budget is spent before anyone looks at it, and the operator reads the dashboard at noon and files the incident, and the fix ships behind a flag nobody remembers to turn on, and the runbook still names a host that was retired last spring."
TWO_COPIES_PAGE = leaf_page(
    "long passages",
    """
<h1 id="t">Long passages</h1>
<section id="copies">
<p>Ahead of the first copy sits this line.</p>
<p id="first">{passage}</p>
<p>Between the copies sits this other line.</p>
<p id="second">{passage}</p>
</section>
""",
).replace("{passage}", LONG_PASSAGE)
# Prose past the pattern's own ceiling. One expression with a term per character stops
# compiling somewhere past ten thousand of them — measured on the gallery: 1.3ms at four
# hundred characters, 11.6ms at five thousand, a SyntaxError at twelve — and the throw
# would land inside the pass that draws every mark on the page, not just this one's. A
# reader reaches it in one keystroke, so the guard is a page long enough to prove it.
CEILING_PAGE = leaf_page(
    "everything",
    """
<h1 id="t">Everything</h1>
{paras}
""",
).format(
    paras="\n".join(
        f"<p>Paragraph {i} of the record. "
        + f"The deploy replays and the guard reads a column the writer never fills, "
        f"so the whole batch runs again from the top on release {i}. " * 3 + "</p>"
        for i in range(40)
    )
)
# A passage that opens its section stores no prefix — note there is no whitespace between
# the section tag and the paragraph, which is what makes the copy's leading context empty
# rather than short. Both copies carry the identical tail, so a suffix on its own is a bar
# the other copy clears just as well.
THIN_V1 = leaf_page(
    "thin",
    """
<h1 id="t">Thin</h1>
<section id="thin"><p>{phrase}. Retries are capped at three.</p>
<p>An unrelated middle paragraph.</p>
<p>Queue drain runs first. {phrase}. Retries are capped at three.</p>
</section>
""",
).replace("{phrase}", "The version stamp never lands")
# Only the commented copy's tail changes, so the untouched copy is now the better match for
# the one neighbour the comment stored.
THIN_V2 = THIN_V1.replace(
    "lands. Retries are capped at three.</p>\n<p>An unrelated",
    "lands. Backoff is capped at three.</p>\n<p>An unrelated",
)
# The journey's page: a passage to comment on, a board to drag, and a draft to
# edit. In v2 the commented paragraph moves below the notes heading — same text,
# new position — so the anchor has to re-find its passage rather than replay a
# location. The draft's source lines are indented like any other child content;
# the widget owes the user the text without them.
SENTENCE = "The version stamp never lands, so migration 0041 replays on every deploy."
DRAFT_TEXT = "Run the migration before deploying.\nIt is online."
DRAFT_EDITED = "Run the migration before deploying. It takes about a minute."
JOURNEY_SCAFFOLD = leaf_page(
    "journey",
    """
<h1 id="t">Journey</h1>
{before}
<lf-board id="board">
  <lf-column id="col-todo" label="Todo">
    <lf-card id="card-x"><strong>Guard the session delete</strong> One line.</lf-card>
  </lf-column>
  <lf-column id="col-done" label="Done"></lf-column>
</lf-board>
<lf-draft id="draft-ops"><pre>
    Run the migration before deploying.
    It is online.
</pre></lf-draft>
<h2 id="notes">Notes</h2>
{after}
""",
)
PASSAGE = f'<p id="intro">{SENTENCE}</p>'
JOURNEY_V1 = JOURNEY_SCAFFOLD.format(
    before=PASSAGE, after="<p id='p-filler'>Filler.</p>"
)
JOURNEY_V2 = JOURNEY_SCAFFOLD.format(
    before="<p id='p-filler'>Filler.</p>", after=PASSAGE
)


def _draft_says(html, text, attrs=""):
    """The journey page with its draft rewritten — the source's indentation and
    all, since that is what the widget dedents back out."""
    return html.replace(
        '<lf-draft id="draft-ops"><pre>\n'
        + "\n".join(f"    {l}" for l in DRAFT_TEXT.split("\n")),
        f'<lf-draft id="draft-ops"{attrs}><pre>\n    {text}',
    )


def _publish(page_dir, version, html, note):
    """Write a version and publish it through `version publish`, which lints it
    and records a `note` event with what it says about the user's decisions."""
    (page_dir / "versions" / f"v{version}.html").write_text(html)
    result = CliRunner().invoke(
        interact.cli,
        [
            "version",
            "publish",
            str(page_dir),
            "--version",
            str(version),
            "--text",
            note,
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output


@pytest.fixture
def one_reader(browser):
    """A browser context two pages can share, which is what makes them tabs.

    `Browser.new_page` opens each page in a context of its own, so two of them are two
    readers with no storage between them — and a draft lives in the reader's store now,
    which is the whole of what these tests are about."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, color_scheme="light"
    )
    yield context
    context.close()


def compose(page, passage, text=None):
    """Open the composer on a passage the way a reader does, and type into it.

    Without text it only opens, which is how a second tab meets a draft already
    standing on that passage: the two gestures are the same one, so the anchor the
    key is built from is the same in both tabs."""
    page.locator(passage).scroll_into_view_if_needed()
    page.locator(passage).click(click_count=3)
    page.wait_for_selector(".lf-fab", state="visible")
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer textarea")).to_be_focused()
    if text is not None:
        page.locator(".lf-composer textarea").fill(text)


# The two presses this asks about, on one page: a draft's ✎ (a thing to do) and a pick
# mark (a thing to do that becomes a thing the page says once it is pressed).
KEYS_PAGE = leaf_page(
    "keys",
    """
<h1 id="h">Session store</h1>
<lf-options id="opts" choose>
  <lf-option id="opt-keep"><strong>Keep the store</strong> Sessions stay where they are.</lf-option>
  <lf-option id="opt-token"><strong>Signed tokens</strong> No store at all.</lf-option>
</lf-options>
<lf-draft id="draft-ops"><pre>
    Run the migration before deploying.
</pre></lf-draft>
""",
)
SMOOTH_LONG_PAGE = LONG_PAGE.replace(
    "</head>", "<style>body { scroll-behavior: smooth; }</style>\n</head>"
)
FIRST_PRESENTATION = """
  window.__lfPresentation = { frames: [], releases: 0 };
  new MutationObserver((changes) => {
    window.__lfPresentation.releases += changes.length;
  }).observe(document, {
    subtree: true,
    attributeFilter: ["data-lf-presented"],
  });
  const sample = () => {
    const old = document.querySelector("#sug lf-old");
    if (old) {
      const box = old.getBoundingClientRect();
      window.__lfPresentation.frames.push({
        stale: old.checkVisibility({
          opacityProperty: true,
          visibilityProperty: true,
        }),
        interactive: old.contains(document.elementFromPoint(
          box.left + box.width / 2,
          box.top + box.height / 2,
        )),
        height: old.getBoundingClientRect().height,
        note: getComputedStyle(document.body, "::after").content,
        waitingPainted:
          getComputedStyle(document.body, "::after").visibility !== "hidden"
          && Number(getComputedStyle(document.body, "::after").opacity) > 0,
      });
    }
    if (document.body?.dataset.lfPresented === undefined)
      requestAnimationFrame(sample);
  };
  requestAnimationFrame(sample);
"""
_CARD = (
    '<lf-card id="card-x"><strong>Guard the session delete</strong> One line.</lf-card>'
)


def _card_done(html):
    """The journey page with its card written in Done — the honoring of a
    recorded drag, or the author's own relocation."""
    return html.replace(
        f'    {_CARD}\n  </lf-column>\n  <lf-column id="col-done" label="Done"></lf-column>',
        f'  </lf-column>\n  <lf-column id="col-done" label="Done">{_CARD}</lf-column>',
    )


SUGGEST_BLOCK = (
    '<lf-suggestion id="sug-fix" resolves="c1">'
    '<lf-old><p id="old-claim">It is not online.</p></lf-old>'
    "<lf-new><p>It takes a minute of downtime.</p></lf-new>"
    "</lf-suggestion>"
)


@contextmanager
def live_watcher(page_dir, page):
    """Hold the exact lease `leaf wait` uses for the duration of the block."""
    session = interact.page_claim(page_dir)
    lease = interact.take_waiter_lease(interact.waiter_lease_path(page_dir, session))
    assert lease
    told(page)
    try:
        yield
    finally:
        lease.close()
    # Outside the finally: a block that raised has its own failure to report, and
    # nothing after it to wait for.
    told(page)


# What the tab is wearing, once the banner has judged `want` and the tab agrees with it.
# The runtime builds the href, so reading it back is reading what the browser was handed;
# null until both hold, which is what makes this a wait — a status arrives on a poll, and
# the tab is repainted in the pass that repaints the dot.
#
# Naming the state is what keeps a read off one the page is passing through: dropping the
# watcher takes a waiting page through `away` on its way to `unheld`, and a wait asking
# only for agreement is answered from there, by a tab that is perfectly correct about a
# state the test is not about.
#
# The tone read is the sheet the runtime appended, never the mark's own — and the two are
# not told apart by their colours. The mark is authored in the accent, so a working page
# paints it the shade it already was, and a reading that took the first rule it found
# agreed with the banner on the one state where nothing had to have happened.
TAB_TONE = """(want) => {
    const el = document.querySelector('.lf-banner .lf-dot');
    const judged = el.className.replace('lf-dot', '').trim();
    const prefix = 'data:image/svg+xml,';
    const href = document.querySelector('link[rel=icon]').getAttribute('href');
    const svg = href.startsWith(prefix)
        ? new DOMParser().parseFromString(
              decodeURIComponent(href.slice(prefix.length)), 'image/svg+xml',
          ).documentElement
        : null;
    const sheets = svg ? [...svg.querySelectorAll('style')] : [];
    const tone =
        sheets.length > 1 ? /fill: ([^}]+) \\}/.exec(sheets.at(-1).textContent)?.[1] : null;
    const dot = getComputedStyle(el).backgroundColor;
    return VERDICT;
}"""
# The same reading with nothing required of it, for a failure that says what it found.
TAB_AND_DOT = TAB_TONE.replace("VERDICT", "[judged, tone, dot]")
TAB_TONE = TAB_TONE.replace("VERDICT", "judged === want && tone === dot ? tone : null")
# A project widget whose body is entirely supplied at runtime. Two rows deliberately say
# the same word: text and document order cannot identify either one, while each record's
# key can.
DATA_PROJECTION_PAGE = leaf_page(
    "data projection",
    """
<h1 id="title">Deployments</h1>
<p id="lede">Live status follows.</p>
<lf-feed id="deployments"></lf-feed>
""",
)

DATA_PROJECTION_MODULE = """
import {offer, projectData} from '/leaf.js';
customElements.define('lf-feed', class extends HTMLElement {
  connectedCallback() {
    this.show([
      {key: 'api', value: 'Ready'},
      {key: 'worker', value: 'Ready'},
    ]);
  }
  show(rows) {
    projectData(this, rows, row => row.key, ({value}) => {
      const row = document.createElement('p');
      row.append(value, offer('button', 'inspect', 'Inspect'));
      return row;
    });
  }
});
"""


def data_projection_page(serve):
    url = serve(DATA_PROJECTION_PAGE)
    d = serve.page_dir
    registry_path = d / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-feed"] = {
        "description": "A project-supplied live feed.",
        "type": "object",
        "properties": {"id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "none",
        "x-upgrade": True,
        "x-example": '<lf-feed id="feed-example"></lf-feed>',
    }
    registry_path.write_text(json.dumps(registry))
    (d / "widgets" / "lf-feed.js").write_text(DATA_PROJECTION_MODULE)
    return url


# ---------- anchors written without a browser ----------
# `leaf comment` writes an anchor by reading the version file; the runtime
# resolves it against the DOM that file becomes. Nothing static can check that those
# two readings agree, and every way they can come apart — a widget's upgrade, an
# attribute rendered as text, the space a block boundary stands for — only exists
# once the page is loaded.


def written_anchors(page_dir, html, limit=40):
    """Anchors `leaf comment` would write for windows over a page's own prose. A
    window the page says twice, or one crossing a fence, is refused on purpose —
    skipping those here is that refusal, and what survives is exactly what the command
    promises to place."""
    registry = interact.load_registry(page_dir)
    text = interact.page_passages(html, registry).text
    words = text.split(" ")
    anchors = []
    for start in range(0, len(words), 3):
        quote = " ".join(words[start : start + 8])
        if len(quote) < 20:
            continue
        try:
            anchors.append(
                (quote, interact.capture_anchor(html, registry, quote, None))
            )
        except ValueError:
            continue
        if len(anchors) == limit:
            break
    return anchors


TWIN_V1 = leaf_page(
    "twin",
    """
<h1 id="t">Twin</h1>
<section id="twin">
<p id="p-original">Cache warmup runs first. The version stamp never lands. Retries are capped at three.</p>
</section>
""",
)
# A copy the anchor was not made on, added above it — so first-match now finds the wrong
# one, and only the neighbours the capture stored say which was meant.
TWIN_V2 = TWIN_V1.replace(
    '<p id="p-original">',
    '<p id="p-added">Queue drain runs first. The version stamp never lands. Retries are capped at four.</p>\n'
    '<p id="p-original">',
)
PICTURE_PAGE = leaf_page(
    "pictures",
    """
<h1 id="t">Pictures</h1>
<p id="p">Two renderings, neither of them the page's own words.</p>
<lf-diagram id="flow"><pre>
graph LR
  A --> B
</pre></lf-diagram>
<lf-tree id="tree"><pre>
feeders/
  mount.py  +2 -2
</pre></lf-tree>
""",
)
# A drawing wider than the column on purpose — six nodes across lay out near 1150px
# against 720 — and a board beside it, so what the assertions turn on is which kind each
# widget declares rather than that both are widgets.
WIDE_DIAGRAM_PAGE = leaf_page(
    "wide diagram",
    """
<h1 id="t">Flow</h1>
<lf-diagram id="flow"><pre>
graph LR
  R[request] --> C{cookie valid?}
  C -->|yes| S[read session from Redis]
  S -->|hit| H[handle]
  S -->|miss/outage| F[verify signed fallback]
  F --> H
  C -->|no| L[login]
</pre></lf-diagram>
<lf-board id="plan">
  <lf-column id="d1" label="Todo"><lf-card id="dk1"><strong>One</strong></lf-card></lf-column>
  <lf-column id="d2" label="Doing"></lf-column>
  <lf-column id="d3" label="Done"></lf-column>
</lf-board>
""",
)
# What a diagram is doing with the width it was given, beside what the board on the same
# page is doing with the width it was given: the drawing's own size, the box around it,
# and whether either had to scroll.
DIAGRAM_ROOM = """() => {
    const holder = document.getElementById('flow');
    const svg = holder.querySelector('svg');
    const board = document.getElementById('plan');
    const main = document.querySelector('main'), ms = getComputedStyle(main);
    const mb = main.getBoundingClientRect();
    return { drawn: svg.getBoundingClientRect().width,
             natural: svg.viewBox.baseVal.width,
             box: holder.clientWidth,
             room: parseFloat(getComputedStyle(document.documentElement)
                       .getPropertyValue('--lf-room')),
             wide: parseFloat(getComputedStyle(document.body)
                       .getPropertyValue('--wide')),
             board: board.getBoundingClientRect().width,
             column: mb.width - parseFloat(ms.paddingLeft) - parseFloat(ms.paddingRight),
             scrolls: holder.scrollWidth > holder.clientWidth,
             sideways: document.body.scrollWidth - document.body.clientWidth };
}"""
# A diagram whose source mermaid refuses, which is the shape of every soft failure: the
# module replaces the element's body with the message and the source it choked on. Its
# first line is the length a real source has, because that line is what the box under
# test is floored at: written short, this page passed the assertion below with the rule
# it stands on deleted.
BROKEN_DIAGRAM_PAGE = leaf_page(
    "broken diagram",
    """
<h1 id="t">Broken</h1>
<lf-diagram id="bad"><pre>
sequenceDiagram
  Reader-&gt;&gt;Server: POST /api/event {kind: "action", widget: "lf-board", detail: {card: "card-heater"}}
  Server--&gt;&gt;&gt;--- {{{ not mermaid at all ]]]
</pre></lf-diagram>
""",
)
# A margin with the page's own apparatus in it, and drawings either side of what the free
# margin can hold. A rail is what most shipped pages that carry a wide widget also carry,
# so this is the ordinary case rather than a corner.
DIAGRAM_AND_RAIL_PAGE = leaf_page(
    "diagram and rail",
    """
<h1 id="t">Sessions</h1>
<lf-suggestion id="sug-copy">
  <lf-old><p id="old-line">Refill every feeder each morning.</p></lf-old>
  <lf-new><p>Refill a feeder when its camera shows it half-empty.</p></lf-new>
</lf-suggestion>
<lf-diagram id="small"><pre>
graph LR
  S[Redis] -->|hit| H[handle]
  S -->|miss| F[cookie]
  F --> H
</pre></lf-diagram>
<lf-diagram id="flow"><pre>
graph LR
  R[request] --> C{cookie valid?}
  C -->|yes| S[read session from Redis]
  S -->|hit| H[handle]
  S -->|miss/outage| F[verify signed fallback]
  F --> H
  C -->|no| L[login]
</pre></lf-diagram>
""",
)

# Where each drawing sits against the column it explains and the controls it must not
# reach. The axis is the column's, because that is the line the prose is centred on and
# the one an exhibit off it reads as having slipped.
DRAWING_PLACEMENT = """() => {
    const main = document.querySelector('main'), ms = getComputedStyle(main);
    const mb = main.getBoundingClientRect();
    const col = { left: mb.left + parseFloat(ms.paddingLeft),
                  right: mb.right - parseFloat(ms.paddingRight) };
    col.axis = (col.left + col.right) / 2;
    const acts = document.querySelector('.lf-sug-actions');
    // The drawing's own rect and the box's. A drawing wider than its box keeps a rect
    // that runs on past it — the layout's answer, not the reader's — so what is painted
    // over the margin is the box's edge and what is lost off the scroll's start edge is
    // the drawing's left against the box's.
    const at = (id) => {
        const holder = document.getElementById(id);
        const b = holder.querySelector('svg').getBoundingClientRect();
        const h = holder.getBoundingClientRect();
        return { left: b.left, right: b.right, width: b.width,
                 offAxis: (b.left + b.right) / 2 - col.axis,
                 box: { left: h.left, right: h.right },
                 scrolls: holder.scrollWidth > holder.clientWidth };
    };
    return { col, docked: acts.classList.contains('lf-docked'),
             rail: acts.getBoundingClientRect().left,
             small: at('small'), flow: at('flow'),
             sideways: document.body.scrollWidth - document.body.clientWidth };
}"""
# A widget that declares width beside one that doesn't, so what the assertions turn on is
# the declaration and not the tag: both are widgets, both hold more than the column shows
# comfortably, and only one of them is entitled to more of the window than the prose gets.
WIDE_AND_NARROW_PAGE = leaf_page(
    "room",
    """
<h1 id="t">Release</h1>
<p id="prose">The board is as wide as its columns are; this sentence is not.</p>
<lf-board id="sprint">
  <lf-column id="col-todo" label="Todo">
    <lf-card id="card-heater"><strong>Heated perch</strong> Wire the south feeder.</lf-card>
  </lf-column>
  <lf-column id="col-doing" label="Doing">
    <lf-card id="card-baffle"><strong>Squirrel baffle</strong></lf-card>
  </lf-column>
  <lf-column id="col-review" label="Review"></lf-column>
  <lf-column id="col-done" label="Done"></lf-column>
</lf-board>
<lf-diff id="patch"><pre>
diff --git a/feeders/mount.py b/feeders/mount.py
--- a/feeders/mount.py
+++ b/feeders/mount.py
@@ -1,3 +1,3 @@
 def bracket():
-    return "plastic"
+    return "steel"
</pre></lf-diff>
""",
)

# main's content box, body's, the page's own box, and where each named element stands in
# them. Read together in one pass because the whole subject is their relation: a width
# means nothing here except against the column it is or isn't wider than.
ROOM_GEOMETRY = """() => {
    const span = (el) => {
        const s = getComputedStyle(el), b = el.getBoundingClientRect();
        const left = b.left + parseFloat(s.paddingLeft);
        const right = b.right - parseFloat(s.paddingRight);
        return { left, right, width: right - left, centre: (left + right) / 2 };
    };
    const box = (id) => {
        const el = document.getElementById(id);
        if (!el) return null;
        const b = el.getBoundingClientRect();
        return { left: b.left, right: b.right, width: b.width,
                 top: b.top, bottom: b.bottom,
                 centre: (b.left + b.right) / 2 };
    };
    // The page's box: what body's padding is spent out of and the column centres in.
    // It is not the window. Body owns the document's scroll and reserves a stable
    // gutter for it (leaf.js), so wherever a scrollbar takes room the page is that
    // much narrower than the window and stands half of it to the window's left — a
    // settled decision made where the gutter is, and one no strip has a part in.
    // Padding included, because a strip taken here moves the column inside a box that
    // has not changed size; `room` above is what the strips left and so cannot say
    // where the edge they came out of is.
    const page = () => {
        const b = document.body, s = getComputedStyle(b);
        const left = b.getBoundingClientRect().left + parseFloat(s.borderLeftWidth);
        return { left, right: left + b.clientWidth, width: b.clientWidth,
                 centre: left + b.clientWidth / 2 };
    };
    return { column: span(document.querySelector('main')),
             room: span(document.body), pageBox: page(),
             board: box('sprint'), diff: box('patch'), prose: box('prose'),
             note: box('note'), later: box('later'),
             sideways: document.body.scrollWidth - document.body.clientWidth };
}"""
# A wide widget inside each of the two kinds of holder: a box that paints (the quoted
# frame, the option's card, the metric, the nested task's rail, the note a code block
# builds, the page's own div) and a wrapper that doesn't (a plain section). The div is
# the case the theme cannot name: it draws its box in the page's own style and declares
# the frame there, which is the whole of what a project writes to hold an exhibit inside
# its own card.
FRAMED_WIDE_PAGE = leaf_page(
    "framed",
    """
<h1 id="t">Framed</h1>
<section id="loose">
  <lf-board id="in-section">
    <lf-column id="s1" label="Todo"><lf-card id="sk1"><strong>One</strong></lf-card></lf-column>
    <lf-column id="s2" label="Done"></lf-column>
  </lf-board>
</section>
<lf-specimen id="quoted" label="a board">
  <lf-board id="in-specimen">
    <lf-column id="q1" label="Todo"><lf-card id="qk1"><strong>One</strong></lf-card></lf-column>
    <lf-column id="q2" label="Done"></lf-column>
  </lf-board>
</lf-specimen>
<lf-options id="pick" choose>
  <lf-option id="opt-a"><strong>With evidence</strong>
    <lf-diagram id="in-card"><pre>
graph LR
  A[request] --> B[queue]
  B --> C[worker]
</pre></lf-diagram>
  </lf-option>
  <lf-option id="opt-b"><strong>Without</strong></lf-option>
</lf-options>
<lf-options id="row-pick" choose>
  <lf-option id="row-a">Along the fence line
    <lf-diagram id="in-row"><pre>
graph LR
  A[house] --> B[shed]
  B --> C[feeder]
  C --> D[bath]
  D --> E[gate]
  E --> F[pole]
  F --> G[box]
</pre></lf-diagram>
  </lf-option>
  <lf-option id="row-b">Under the lawn in a trench</lf-option>
</lf-options>
<lf-board id="evidence">
  <lf-column id="e1" label="Todo"><lf-card id="ek1"><strong>With evidence</strong>
    <lf-diagram id="in-board-card"><pre>
graph LR
  A[request] --> B[queue]
  B --> C[worker]
</pre></lf-diagram>
  </lf-card></lf-column>
  <lf-column id="e2" label="Done"></lf-column>
</lf-board>
<lf-metrics id="nums">
  <lf-metric id="me1" value="410ms">p95, with the path it measures
    <lf-diagram id="in-metric"><pre>
graph LR
  A[request] --> B[queue]
  B --> C[worker]
</pre></lf-diagram>
  </lf-metric>
</lf-metrics>
<lf-tasks id="plan">
  <lf-task id="t-outer" status="active"><strong>Rebuild the feeders</strong>
    <lf-task id="t-inner" status="review"><strong>Fit the baffles</strong>
      <lf-diagram id="in-task"><pre>
graph LR
  A[request] --> B[queue]
  B --> C[worker]
</pre></lf-diagram>
    </lf-task>
  </lf-task>
</lf-tasks>
<lf-code id="walk" language="python" hi="2"><pre>
def bracket(temp):
    if temp &lt; 0:
        return "steel"
    return "cedar"
</pre>
  <lf-note id="line-note" at="2">Freezing is the only threshold that matters.
    <lf-diagram id="in-note"><pre>
graph LR
  A[request] --> B[queue]
  B --> C[worker]
</pre></lf-diagram>
  </lf-note>
</lf-code>
<div id="own-box" style="border: 1px solid #999; padding: 10px; --lf-frame: 1">
  <lf-diagram id="in-own-box"><pre>
graph LR
  A[request] --> B[queue]
  B --> C[worker]
</pre></lf-diagram>
</div>
""",
)

# A box of the page's own that both draws and scrolls, holding a wide widget. The theme
# has no rule for a project's box and cannot, so what stands between it and a page drawn
# wrong is the gate — and the gate could not see through the scroll: `answeredFor`
# excused anything inside one, which is every card on every board.
FRAMED_SCROLLER_PAGE = FRAMED_WIDE_PAGE.replace(
    "<main>",
    "<main>\n<div id='own-frame' style='border: 1px solid #999; overflow-x: auto'>"
    "<lf-board id='framed'><lf-column id='f1' label='Todo'>"
    "<lf-card id='fk1'><strong>One</strong></lf-card></lf-column>"
    "<lf-column id='f2' label='Done'></lf-column></lf-board></div>",
)


# A page that reserves the margin rail and stands a wide widget in the flow beside it —
# the pair no shipped example had until ship-review, and the pair the room has to be
# measured after rather than before.
RAIL_AND_WIDE_PAGE = leaf_page(
    "rail",
    """
<h1 id="t">Release</h1>
<lf-suggestion id="sug-copy">
  <lf-old><p id="old-line">Refill every feeder each morning.</p></lf-old>
  <lf-new><p>Refill a feeder when its camera shows it half-empty.</p></lf-new>
</lf-suggestion>
<lf-board id="plan">
  <lf-column id="r1" label="Todo"><lf-card id="rk1"><strong>One</strong></lf-card></lf-column>
  <lf-column id="r2" label="Doing"></lf-column>
  <lf-column id="r3" label="Done"></lf-column>
</lf-board>
""",
)


# How far the exhibit stands outside the page's own box, and the rail it was supposed to
# leave — both edges, since a room read too wide spends itself on whichever side is free.
# One reading for the live page and for a copy of it, the fault being the same fault. The
# room the page states comes with it, so a test waiting for the box to be read again has
# the reading it is waiting to see changed.
RAIL_FIT = """() => {
    const b = document.body, s = getComputedStyle(b);
    const box = b.getBoundingClientRect();
    const r = document.getElementById('plan').getBoundingClientRect();
    return { rail: s.paddingRight, widget: r.width,
             room: getComputedStyle(document.documentElement)
                     .getPropertyValue('--lf-room'),
             past: Math.max(r.right - (box.right - parseFloat(s.paddingRight)),
                            (box.left + parseFloat(s.paddingLeft)) - r.left),
             content: box.width - parseFloat(s.paddingLeft)
                      - parseFloat(s.paddingRight) };
}"""
# The room the document leaves at each end for a bar standing over it. Both are boxes in
# the flow, so the reading is the flow's own: what stands above the page's first block and
# what is left under its last.
CHROME_ROOM = """() => {
    const body = document.body;
    const box = document.querySelector('main').getBoundingClientRect();
    return { head: box.top + body.scrollTop,
             foot: body.scrollHeight - (box.bottom + body.scrollTop),
             banner: document.querySelector('.lf-banner').offsetHeight,
             line: document.querySelector('.lf-keyline').offsetHeight };
}"""
# The same reading taken at the stamp, which is the one moment nothing out here can
# reach: a MutationObserver's callback is a microtask off the stamp's own write, and
# the frame after it is where the runtime's layout observer restates the room.
AT_THE_HANDOVER = (
    "window.__handover = null;\n"
    "new MutationObserver(() => { window.__handover ??= (" + RAIL_FIT + ")(); })\n"
    '  .observe(document, { subtree: true, attributeFilter: ["data-lf-upgraded"] });'
)
LATE_MARGIN_PAGE = leaf_page(
    "late margin",
    """
<h1 id="t">Release</h1>
<lf-callout id="marginal"><strong>Note</strong> Its controls hang in the margin.</lf-callout>
<lf-board id="plan">
  <lf-column id="r1" label="Todo"><lf-card id="rk1"><strong>One</strong></lf-card></lf-column>
  <lf-column id="r2" label="Doing"></lf-column>
  <lf-column id="r3" label="Done"></lf-column>
</lf-board>
""",
)

# A widget that hangs its controls in the page margin, and can only say how wide a margin
# once it has heard what they will say — so the claim rides an answer rather than the
# upgrade that asked for it. lf-suggestion is the same widget with a measurement it
# happens to be able to take on the spot, which is why the moment a claim lands was never
# anybody's subject. The request is answered by the test, which is what puts the claim
# after the handover on every machine rather than on a fast one.
LATE_MARGIN_WIDGET = """\
import { once } from "/leaf.js";

customElements.define(
  "lf-callout",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      fetch("/margin-width").then(() =>
        document.body.style.setProperty("--strip-r", "160px"),
      );
    }
  },
);
"""
# Where the two things in the right margin stand, and how much of the board is over the
# controls. The controls are what the strip was reserved for, and they hang off the column
# rather than out of the strip, so the strip's own edge says nothing about where they are.
RAIL_BAND_PAGE = leaf_page(
    "rail band",
    """
<h1 id="t">Release</h1>
<lf-suggestion id="sug-copy">
  <lf-old><p id="old-line">Refill every feeder each morning.</p></lf-old>
  <lf-new><p>Refill a feeder when its camera shows it half-empty.</p></lf-new>
</lf-suggestion>
<lf-board id="plan">
  <lf-column id="r1" label="Todo"><lf-card id="rk1"><strong>One</strong>
    <lf-suggestion id="sug-card">
      <lf-old><p>By hand.</p></lf-old>
      <lf-new><p>On the timer.</p></lf-new>
    </lf-suggestion></lf-card></lf-column>
  <lf-column id="r2" label="Doing"></lf-column>
  <lf-column id="r3" label="Done"></lf-column>
</lf-board>
<p id="gap" style="margin-block: 600px">Prose far enough below the changes that no row
reaches this part of the page.</p>
<lf-board id="later">
  <lf-column id="l1" label="Todo"><lf-card id="lk1"><strong>Two</strong></lf-card></lf-column>
  <lf-column id="l2" label="Done"></lf-column>
</lf-board>
""",
)


RAIL_BANDS = """() => {
    const box = (el) => {
        const b = el.getBoundingClientRect();
        return { left: b.left, right: b.right, top: b.top, bottom: b.bottom,
                 width: b.width };
    };
    const body = document.body, bs = getComputedStyle(body);
    const bb = body.getBoundingClientRect();
    const m = document.querySelector('main');
    const ms = getComputedStyle(m), mb = m.getBoundingClientRect();
    return { rows: [...document.querySelectorAll('.lf-sug-actions')].map(r => ({
                 ...box(r), docked: r.classList.contains('lf-docked') })),
             plan: box(document.getElementById('plan')),
             later: box(document.getElementById('later')),
             column: { left: mb.left + parseFloat(ms.paddingLeft),
                       right: mb.right - parseFloat(ms.paddingRight) },
             pageRight: bb.right - parseFloat(bs.paddingRight),
             sideways: body.scrollWidth - body.clientWidth };
}"""


DRAWN_PAST_A_RAIL_PAGE = leaf_page(
    "drawn past a rail",
    """
<h1 id="t">Flow</h1>
<lf-suggestion id="sug-copy">
  <lf-old><p id="old-line">Refill every feeder each morning.</p></lf-old>
  <lf-new><p>Refill a feeder when its camera shows it half-empty.</p></lf-new>
</lf-suggestion>
<p id="gap" style="margin-block: 600px">Prose far enough below the change that its row
reaches nothing here.</p>
<lf-diagram id="flow"><pre>
graph LR
  R[request] --> C{cookie valid?}
  C -->|yes| S[read session from Redis]
  S -->|hit| H[handle]
  C -->|no| L[login]
</pre></lf-diagram>
""",
)
# A page hanging apparatus of its own in the margin, level with a wide widget. The theme
# has no rule for a project's own furniture and cannot — this is the case the two claims
# in it are declarations of, seen from the side where nobody has declared anything.
OWN_MARGIN_FURNITURE = WIDE_AND_NARROW_PAGE.replace(
    "<main>",
    "<main>\n<div id='own-rail' style='position: absolute; left: 100%;"
    " margin-left: 22px; top: 0; width: 160px; height: 600px'>Mine.</div>",
)
# One reply holding both answers to the question the block-content lists ask: chips are
# set among the words, a paragraph is not. The pair is the point — the stacking rule
# reaching neither group would read as a pass on the first half alone.
INLINE_REPLY_MARKUP = (
    '<lf-compare id="rp-terse">'
    '<lf-variant id="rp-redis"><lf-chip>a service</lf-chip>Redis</lf-variant>'
    '<lf-variant id="rp-cookie"><lf-chip>no service</lf-chip>Signed cookie</lf-variant>'
    "</lf-compare>"
    '<lf-compare id="rp-argued">'
    '<lf-variant id="rp-keep"><p>Keep the store, and the operator that comes with it.</p></lf-variant>'
    '<lf-variant id="rp-drop"><p>Drop it, and read sessions off the cookie alone.</p></lf-variant>'
    "</lf-compare>"
)
# The two things on this page that want a margin, on one page and level with each other.
# The note is written immediately before the board so they share a band of the page rather
# than stacking, which is the only arrangement in which either can be over the other.
NOTE_AND_WIDE_PAGE = leaf_page(
    "room and margin",
    """
<h1 id="t">Feeders</h1>
<p id="prose">The board is as wide as its columns are; this sentence is not.</p>
<aside class="sidenote" id="note">Counts are the warden's own, taken at dawn from the
south hide, and the perch numbers are the ones she disputes.</aside>
<lf-board id="sprint">
  <lf-column id="col-todo" label="Todo">
    <lf-card id="card-heater"><strong>Heated perch</strong> Wire the south feeder.</lf-card>
  </lf-column>
  <lf-column id="col-doing" label="Doing">
    <lf-card id="card-baffle"><strong>Squirrel baffle</strong></lf-card>
  </lf-column>
  <lf-column id="col-review" label="Review"></lf-column>
  <lf-column id="col-done" label="Done"></lf-column>
</lf-board>
<p id="gap" style="margin-block: 600px">Prose far enough below the note that nothing of
it reaches this part of the page.</p>
<lf-board id="later">
  <lf-column id="late-todo" label="Todo">
    <lf-card id="card-seed"><strong>Seed mix</strong> Switch to sunflower hearts.</lf-card>
  </lf-column>
  <lf-column id="late-done" label="Done"></lf-column>
</lf-board>
""",
)

# Wide enough that the note has its strip (1152px) and narrow enough that the room, not
# the shared cap, is what decides the board's width — above about 1560px the cap binds
# first and the two never compete. A window inside that band is where the question is live.
NOTE_BAND = 1280


def _painted_line(page):
    """Every row in the gesture's next key-line paint, including rows behind More.

    Consume the coalesced frame once: polling could pass on an unrelated later paint.
    Read rows rather than visible text because hidden rows still state liveness.
    """
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    return page.eval_on_selector_all(
        ".lf-keyline .lf-key",
        "els => els.map(e => [...e.children].map(c => c.textContent).join(' '))",
    )


SCROLLED = "() => document.body.scrollTop > 0"


WHERE_I_STAND_PAGE = leaf_page(
    "where i stand",
    """
<h1 id="t">Standing</h1>
<p id="p1">A first passage, with a <a href="https://example.invalid/spec">link into the
spec</a> so the walk has somewhere to stand that is not an ask.</p>
<lf-options id="shape" choose>
  <lf-option id="sh-steel"><strong>Steel</strong> Galvanised, and the
  <a href="https://example.invalid/steel">spec for it</a> is short.</lf-option>
  <lf-option id="sh-cedar"><strong>Cedar</strong> Cheap; needs sealing.</lf-option>
</lf-options>
<lf-options id="settled" choose settled>
  <lf-option id="st-keep" chosen><strong>Keep it</strong> Decided last week, with the
  <a href="https://example.invalid/keep">note behind it</a>.</lf-option>
  <lf-option id="st-drop"><strong>Drop it</strong> The alternative.</lf-option>
</lf-options>
<p id="p2">A passage carrying
<lf-suggestion id="sug-window">
  <lf-old>Refill every feeder each morning.</lf-old>
  <lf-new>Refill when the camera shows it half-empty.</lf-new>
</lf-suggestion></p>
""",
)
