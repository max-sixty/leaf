"""What only a browser can see: that a page actually renders.

check is static — it parses the file and validates the vocabulary. Everything
downstream of that (a widget's upgrade, the theme's CSS, the runtime's injected
chrome) meets for the first time in the browser, and the failures that live
there are invisible to a linter. This suite drives the shipped examples through
the Chrome already on the machine and asserts the handful of things that were
each, at some point, wrong:

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

Chrome is driven through Playwright's `channel="chrome"`, which attaches to the
installed browser: no download, no build step, `uv` still the one prerequisite.
"""

import fcntl
import hashlib
import io
import itertools
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
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

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.html"))
assert EXAMPLES, "no examples found — parametrizing over an empty list tests nothing"
# The bytes an example names but cannot hold: a lf-shot's pair, content-addressed
# exactly as `leaf page media` names it in a real page directory. examples/CLAUDE.md
# lists every publisher that has to lay this beside the markup, this one among them.
EXAMPLE_MEDIA = Path(__file__).parent.parent / "examples" / "media"

# A long page, so the document scrolls, and nothing else — the panel is the subject.
LONG_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>long</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="t">Long</h1>
{paras}
</main>
</body>
</html>
""".format(
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
INLINE_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>inline</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
""".format(
    filler="\n".join(
        f"<p id='f{i}'>Filler {i}. " + "Words. " * 20 + "</p>" for i in range(6)
    ),
    # Exactly 399 characters before the emoji, so the 400-character cap falls between its
    # two UTF-16 halves — the boundary a naive slice cuts a character in two at.
    long=("Capped. " * 50)[:399],
)

# A decision already made and acted on, with the alternatives kept for the record.
SETTLED_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>settled</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


# A decision the page reports rather than offers: no `choose`, so there is nothing to
# press, and the mark the upgrade puts on the carried option is the page saying which
# one the document holds. The paragraph above it is the control — a passage nobody has
# ever doubted was quotable.
CARRIED_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>carried</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="h">Session transport</h1>
<p id="lede">Where the decision stands, for the record.</p>
<lf-options id="carried">
  <lf-option id="c-lax" chosen><strong>Lax cookie</strong> Host-only, set by the auth
  origin, nothing for a script to read.</lf-option>
  <lf-option id="c-bearer"><strong>Bearer header</strong> Suits the mobile client;
  puts the id where every script can read it.</lf-option>
</lf-options>
</main>
</body>
</html>
"""


# The words a widget renders from an attribute — a column's heading, a metric's number —
# with room around them, so a drag across one is an ordinary drag and not a two-pixel
# feat. Both column labels differ, so a quote can only anchor where it was picked.
SAID_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>said</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


# Short card titles, so the whole board fits in an expected ARIA snapshot and the
# snapshot stays about structure. One column starts empty: a keyboard user has to
# hear it to move a card into it.
BOARD_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>board</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="h">Sprint</h1>
<lf-board id="sprint">
  <lf-column id="col-todo" label="Todo">
    <lf-card id="card-heater"><strong>Heated perch</strong></lf-card>
    <lf-card id="card-baffle"><strong>Squirrel baffle</strong></lf-card>
  </lf-column>
  <lf-column id="col-done" label="Done"></lf-column>
</lf-board>
</main>
</body>
</html>
"""


# Exhibited widgets beside live ones, so a missing affordance can be pinned on the
# quoting rather than on a broken upgrade.
SPECIMEN_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>specimen</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
  <lf-options id="quoted-settled" choose settled>
    <lf-option id="q-lax" chosen><strong>Lax cookie</strong> Host-only.</lf-option>
    <lf-option id="q-bearer"><strong>Bearer header</strong> Suits mobile.</lf-option>
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
</main>
</body>
</html>
"""


# A page with nothing to decide: the widgets under test arrive in the panel, on a
# reply, which is the other place markup renders.
REPLY_HOST_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>reply</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="h">Session store</h1>
<p id="intro">Redis, with a signed-cookie fallback for reads.</p>
</main>
</body>
</html>
"""

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
REPLAYED_PAGE = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>replayed</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="t">Rollout</h1>
<lf-options id="approach" choose>
  <lf-option id="opt-shim"><strong>Shim the old schema</strong> Fastest to ship.</lf-option>
  <lf-option id="opt-stage"><strong>Migrate in stages</strong> Table by table.</lf-option>
</lf-options>
<lf-board id="work">
  <lf-column id="col-doing" label="Doing">{IMPORTER_CARD}</lf-column>
  <lf-column id="col-done" label="Done"><lf-card id="card-notes"><strong>Draft the notes</strong></lf-card></lf-column>
</lf-board>
</main>
</body>
</html>
"""


# A page's key is minted per page; fixed here so a test can build a URL for a
# server it did not start.
TOKEN = "test-page-key"


@pytest.fixture
def serve(tmp_path, monkeypatch):
    """Publish HTML as v1 of a fresh page directory and serve it, as the real
    server does — vendoring included, so the assets under test are this repo's."""

    def go(html, comments=0, anchored=()):
        monkeypatch.chdir(tmp_path)  # keep the project layer out of the overlay
        d = tmp_path / "page"
        assert CliRunner().invoke(interact.cli, ["page", "init", str(d)]).exit_code == 0
        (d / "versions" / "v1.html").write_text(html)
        shutil.copytree(EXAMPLE_MEDIA, d / "media", dirs_exist_ok=True)
        interact.append_event(
            d, {"kind": "note", "author": "claude", "version": 1, "text": "t"}
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
        go.page_dir = d  # for tests that publish a v2 or read the event log
        # The key rides in the URL exactly as it does in a handover, so the first
        # navigation of each browser context earns the cookie the rest of the
        # page's own fetches go out under.
        return f"http://127.0.0.1:{httpd.server_address[1]}/versions/v1.html?t={TOKEN}"

    servers = []
    yield go
    for httpd in servers:
        httpd.shutdown()


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

    `read` is what makes `round_trip` a statement about this gesture rather than about
    whichever poll happened to land last: a poll notes the posts already answered when it
    goes out, so what it can have told the page on arrival is those and no later ones. Two
    polls can be in flight at once — a post's own and the timer's — so the freshest reading
    stands rather than the last one to arrive, which is what the max is for.

    A trip that fails is over too, so `requestfailed` counts exactly where a response
    would. A post the server refuses and a poll a test aborts have both finished going
    round, and a wait that only counted successes would sit out the rest of its timeout on
    the strength of a request that is never coming back.

    Both readings are taken at the same moment the wrapper took them: it counted in
    `res.then(...)`, which is the fetch promise settling, and that is the trip this event
    reports. What the runtime then does about the answer is later than either, and it is
    the auto-retrying `expect` after the wait that covers it — as it always did.

    The count is the page's whole life, reloads included, where the init script started
    over at each navigation. That only ever waits longer: a reloaded page's sends are
    already answered, so the first poll after it carries `read` up to them, and a
    `round_trip` that used to return on a zeroed counter now returns on a real one."""

    def __init__(self, page):
        self.sends = 0  # events posted
        self.acked = 0  # posts the server has answered
        self.read = 0  # answered posts the newest state the page has read accounts for
        self.asked = 0  # state the page has gone out for
        self.heard = 0  # ... and been given
        self._asof = {}  # a poll in flight -> the posts already answered when it went out
        self._flying = (
            set()
        )  # event posts in the air, each counted once whichever way it ends
        page.on("request", self._out)
        page.on("response", lambda response: self._back(response.request))
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
        elif "/api/state" in request.url:
            self.asked += 1
            self._asof[request] = self.acked

    def _back(self, request):
        # Counted only while in the air, so a straggling report of a post the
        # navigation already settled can't count it twice.
        if "/api/event" in request.url:
            if request in self._flying:
                self._flying.discard(request)
                self.acked += 1
        elif "/api/state" in request.url:
            self.heard += 1
            self.read = max(self.read, self._asof.pop(request, 0))

    def _navigated(self, frame):
        if frame.parent_frame is not None:
            return
        while self._flying:
            self._flying.pop()
            self.acked += 1

    def __str__(self):
        return (
            f"sends={self.sends} acked={self.acked} read={self.read} "
            f"asked={self.asked} heard={self.heard}"
        )


def _traffic(page):
    """The watcher `open_page` hung on this page when it made it."""
    return page.lf_traffic


def _until(page, fact, wanted):
    """Block until `fact` holds of the page's traffic.

    The events the counters are built from arrive while the client is blocked inside a
    Playwright call, so this blocks on the next response and asks again — no polling
    interval to pick, and nothing added to the page.

    It wakes on responses alone, where the counters answer to failures too, so a fact that
    came true through a failed request waits for the next poll that is answered to be
    noticed. A page with every poll routed to `abort` has no such next, and a wait on one
    runs its timeout out and says so rather than passing.

    A wait that runs out says what it was watching, `wanted` naming the fact in the words
    of the caller that wanted it — required rather than defaulted, so the next wait written
    here cannot quietly go back to saying nothing. Playwright's own message names the event
    it blocked on ("response") and nothing about the page, while the counters that answer
    it are already in hand, so the failure carries them from both ends of the wait: a fact
    stuck while polls keep arriving reads differently from a page that has stopped talking
    at all. Raised from the timeout rather than in place of it, the budget it ran out of
    being the one fact this message hasn't got."""
    if fact(_traffic(page)):
        return
    began = str(_traffic(page))
    try:
        page.wait_for_event("response", predicate=lambda _: fact(_traffic(page)))
    except PlaywrightTimeout as ran_out:
        raise AssertionError(
            f"the page never {wanted}: the wait began on {began} and gave up on "
            f"{_traffic(page)}"
        ) from ran_out


# A gesture that sends is not over when its response lands. The runtime answers a post by
# polling, and what the page does about the gesture arrives with that poll rather than with
# the post, so a read taken on the post is a read from before the gesture had an effect —
# passing or failing by where the round trip happened to be. That is the flake CLAUDE.md
# calls worse than an outright failure, and it hid the sign-off regression on about half
# the runs meant to prove the press sweep catches it.
#
# So the wait is the round trip itself, watched rather than timed. Holding for the poll
# interval instead would state a number the runtime is free to change, and would still
# be a guess on a loaded machine — while charging every gesture two seconds for a trip
# that takes ten milliseconds.
def round_trip(page):
    """Wait for what this page has sent to have come back to it."""
    _until(page, lambda t: t.read >= t.sends, "heard back what it sent")


# The other direction of the same trip. Nothing a test writes into the page directory
# announces itself — a declared status, a bumped heartbeat, an appended event all reach
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


# A poll a test stops is cancelled rather than failed. The page cannot tell the two
# apart — both reject the fetch the runtime awaits and leave it on the same `catch` —
# and `requestfailed` fires for either, so the trip still counts as over and every wait
# built on `Traffic` is unchanged. The console can tell them apart, which is what the
# reason is chosen for: tests/CLAUDE.md, "A test cannot assert over noise it makes
# itself". A send the network refuses is the other act, and
# test_a_decision_the_server_never_took_goes_back_to_pending aborts plainly for it —
# there the failure is the subject, and the entry it leaves is what the test asserts.
def refuse(route):
    """Stop this request with nothing for the page's console to report."""
    route.abort("aborted")


def test_a_reload_mid_flight_never_wedges_round_trip(browser, serve):
    """A navigation ends a trip the browser reports for neither kind, and the
    counters must say so or every later wait on this page runs its timeout out.

    Accept-all is how a real sweep gets here: it answers its asks one awaited
    trip at a time, so a reload after the press lands mid-cascade and kills an
    /api/event POST that then produces no `response` and no `requestfailed`.
    The route's delay holds a post in the air so the navigation reliably lands
    on one; the assertion is Traffic's books balancing, and then `round_trip`
    returning on a page whose only unfinished trip ended at the reload."""
    gallery = next(p for p in EXAMPLES if p.stem == "gallery")
    url = serve(gallery.read_text())
    # The console is not the subject here: a reload mid-post leaves Chrome's own
    # "Failed to load resource" behind, which is the navigation working.
    page, _ = open_page(browser, url)
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")

    def slow(route):
        if "/api/event" in route.request.url:
            time.sleep(0.5)
        route.continue_()

    page.route("**/api/event", slow)
    page.locator(".lf-answer-all").first.click()
    page.wait_for_event(
        "request", predicate=lambda r: "/api/event" in r.url, timeout=5000
    )
    page.unroute("**/api/event")
    page.goto(url, wait_until="networkidle")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    t = _traffic(page)
    assert t.acked >= t.sends, (
        f"a trip the navigation ended was never counted: sends={t.sends} "
        f"acked={t.acked}"
    )
    round_trip(page)


def open_page(
    browser,
    url,
    *,
    pin=False,
    init_script=None,
    wait_until="networkidle",
    context=None,
    upgraded=True,
):
    """A page with its console errors collected, done becoming itself.

    `pin` asks for the version the URL names rather than the newest, and is a keyword
    because the URL a handover carries already has a query holding the page's key: a
    test appending its own `?pin` overwrote that key and got a page that never loaded.

    `upgraded` is the page's own two stamps for having finished, and it takes both
    because the page is two halves. `lf-upgraded` is the document's: widgets upgraded,
    the anchor pass run, and with it the Comment button able to answer a selection at
    all. Waiting on the banner instead says only that the runtime's module evaluated,
    which happens long before — so a test that reads without an auto-retrying wait is
    racing the upgrade, and on a loaded machine loses. The passage sweep lost it on the
    gallery, the heaviest page here: its first selection raised no button, and what it
    reported was a passage it had not tested rather than one that failed.

    `lf-applied` is the log's half, written at the end of every replay pass, so its
    presence is the page saying a poll has landed and been rendered in full. The runtime
    starts that first poll in the same breath as it stamps the document and never awaits
    it, so a page can be done becoming itself while still knowing nothing of what the
    reader has decided or which version is newest. This machine closes that gap during
    `networkidle` and a dockerised Linux runner did not, which is how it surfaced — as
    three tests losing a keypress, out of the twenty-two that were standing on it. So the
    wait is here, where every page is opened, and not in the three that noticed.

    False is for the one test whose subject is that interval, which holds the registry
    fetch open and so never earns the stamp."""
    page = (
        context.new_page()
        if context
        else browser.new_page(
            viewport={"width": 1200, "height": 900}, color_scheme="light"
        )
    )
    # Before the first navigation, so the count is of everything this page ever asked for.
    page.lf_traffic = Traffic(page)
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
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
    page.goto(url, wait_until=wait_until)
    page.wait_for_function(
        "() => document.body.dataset.lfUpgraded === '1'"
        " && document.body.dataset.lfApplied !== undefined"
        if upgraded
        else "() => document.querySelector('.lf-banner') !== null"
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
    starts that poll, never awaiting it, so a refusal puts replay on the far side of both
    the stamp and networkidle — where a slow machine would have put it — deterministically
    and in a second."""

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
    the transition the margin write just armed is visible to the very first read, a
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
    the browser and not about the page: the runtime's own resize listener may not have
    run yet, so syncLayout's layout — the margin, the covering sheet, and with it which
    region a half-page key moves — can still be the old window's. A test that reads
    layout on that frame reads the width it just left, and only on a machine loaded
    enough to fit the read in first, which is the shape of every wait this suite has
    had to learn (`tests/CLAUDE.md`, "A wait consumes a fact the system states").

    The fact the page states here is the event reaching its listeners. The runtime
    registered its own when it loaded, so one added now runs after it on the same
    event, and a count of those is the page saying it has caught up. What syncLayout
    then wrote is a separate question, and a test whose subject is the new layout still
    waits for the piece of it that it is about.

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
    older than this. A press rather than the `=` key, since the press is the control;
    the tests about the key press the key."""
    page.locator(".lf-version").click()
    press = (
        page.locator(".lf-version-diff").last
        if version is None
        else page.locator(f'.lf-version-diff[data-lf-version="{version}"]')
    )
    press.click()


CUSTOM_WIDGET_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>custom widget</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
</head>
<body>
<main>
<h1 id="title">Project vocabulary</h1>
<lf-callout id="custom-note">
  <strong>Heads up</strong> This widget came from the project layer.
</lf-callout>
</main>
<script type="module" src="/leaf.js"></script>
</body>
</html>
"""


def test_a_scaffolded_project_widget_loads_through_the_real_layer(
    browser, serve, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        interact.cli, ["customize", "widget", "lf-callout", "--upgrade"]
    )
    assert result.exit_code == 0, result.output

    url = serve(CUSTOM_WIDGET_PAGE)
    page, errors = open_page(browser, url)
    widget = page.locator("#custom-note")
    expect(widget).to_have_attribute("data-lf-done", "1")
    assert widget.evaluate(
        "(el) => ({display: getComputedStyle(el).display, "
        "border: getComputedStyle(el).borderTopWidth})"
    ) == {"display": "block", "border": "1px"}
    assert errors == []
    page.close()


def test_the_render_gate_rejects_an_upgrade_that_defines_no_element(
    browser, serve, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        interact.cli, ["customize", "widget", "lf-callout", "--upgrade"]
    )
    assert result.exit_code == 0, result.output
    module = tmp_path / ".leaf" / "widgets" / "lf-callout.js"
    module.write_text("// Valid JavaScript, but no custom-element definition.\n")

    failures = interact.render_version(browser, serve(CUSTOM_WIDGET_PAGE))

    assert any(
        "upgraded widgets did not define their elements: <lf-callout>" in failure
        for failure in failures
    )


def test_the_render_gate_catches_a_lying_verbatim_and_an_undeclared_shadow_root(
    browser, serve, tmp_path, monkeypatch
):
    """Bug-back for two module contracts the gate enforces: an entry that says
    x-verbatim while the module renders other words in the body's stead (quotes
    would strand on words the screen no longer shows), and a module attaching a
    shadow root its entry doesn't declare (the passage walk crosses only the
    declared ones, so an undeclared root's words anchor astray)."""
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        interact.cli, ["customize", "widget", "lf-callout", "--upgrade"]
    )
    assert result.exit_code == 0, result.output
    module = tmp_path / ".leaf" / "widgets" / "lf-callout.js"
    module.write_text(
        'import { once } from "/leaf.js";\n'
        "customElements.define(\n"
        '  "lf-callout",\n'
        "  class extends HTMLElement {\n"
        "    connectedCallback() {\n"
        "      if (!once(this)) return;\n"
        '      this.textContent = "Entirely different words.";\n'
        '      const stage = document.createElement("div");\n'
        "      this.append(stage);\n"
        '      stage.attachShadow({ mode: "open" }).textContent = "shadow words";\n'
        "    }\n"
        "  },\n"
        ");\n"
    )

    failures = interact.render_version(browser, serve(CUSTOM_WIDGET_PAGE))

    assert any("x-verbatim" in f for f in failures), failures
    assert any("shadow roots the registry doesn't declare" in f for f in failures), (
        failures
    )


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_example_renders(browser, serve, example):
    """Every shipped example loads clean and lays out, in both color schemes: no
    fail-soft error box, no console error, every visible widget occupies real
    space, no sideways scroll, no words on screen a selection can't reach. A
    widget that upgrades into a 1x1 box, or a heading painted by a pseudo-element,
    is the shape of failure a static lint cannot see. The invariants live in
    interact.render_version — the pass `version check --render` runs on agent-authored
    pages — so this sweep also proves the gate a user's page goes through."""
    assert interact.render_version(browser, serve(example.read_text())) == []


# Every cell one unbreakable token, so no amount of wrapping gets this table
# inside the column and the third of the theme's three cases is the one on trial.
WIDE_TABLE_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>wide</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="t">Sessions</h1>
<p id="p">One row, and more of it than the measure holds.</p>
<table id="sessions">
<thead><tr>{heads}</tr></thead>
<tbody><tr>{cells}</tr></tbody>
</table>
</main>
</body>
</html>
""".format(
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


def test_a_table_too_wide_to_wrap_scrolls_inside_the_column(browser, serve):
    """The theme's answer for a table with more in it than the column holds. Its
    columns hold what is in them, so it takes the measure only when it needs to
    and wraps its cells past that; when even wrapping can't fit it scrolls inside
    itself — like pre, like lf-board — rather than out into the margin
    where a suggestion's controls hang. `width: 100%` had no third case: the
    table spilled, and at this viewport the window is wide enough that nothing
    scrolled to say so."""
    url = serve(WIDE_TABLE_PAGE)
    page, errors = open_page(browser, url)
    measured = page.locator("#sessions").evaluate(
        """(t) => {
        const main = t.closest('main'), pad = parseFloat(getComputedStyle(main).paddingRight);
        const column = main.getBoundingClientRect().right - pad;
        return { past: Math.round(t.getBoundingClientRect().right - column),
                 scrolls: Math.round(t.scrollWidth - t.clientWidth),
                 sideways: document.body.scrollWidth - document.body.clientWidth };
    }"""
    )
    # Where the width went, then that there was width to go anywhere: a table
    # narrow enough to fit satisfies the first of these while proving nothing,
    # and it is the second that says this one was never such a table.
    assert measured["past"] <= 0
    assert measured["scrolls"] > 0, "this table fits, so it proves nothing"
    assert measured["sideways"] == 0
    assert errors == []
    page.close()
    assert interact.render_version(browser, url) == []


def test_the_render_gate_reports_content_set_past_the_column(browser, serve):
    """The reading neither of the gate's older ones can give. The window is the
    wider of the two boxes — 1200px against a 720px column — so content can stand
    out in the margin with the body still not scrolling sideways, and the
    static lint reads pinned pixels, which a vw width is not. The failure names
    the element and how far out it is, because "something overflows" sends its
    reader back to the browser to find out what."""
    failures = interact.render_version(browser, serve(SPILLING_PAGE))

    assert [
        f
        for f in failures
        if "<div id=too-wide> is set" in f and "px past the column" in f
    ]
    assert not [f for f in failures if "scrolls sideways" in f], (
        "the window absorbed it, which is what leaves this reading the only one that sees it"
    )


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


def test_the_render_gate_reports_code_the_reader_cannot_tell_from_its_block(
    browser, serve
):
    """Colouring code takes the runtime writing a role and the theme answering it, and
    the two meet only in the browser — so a stylesheet that stops answering, or answers
    too faintly, is a page of flat code and no error anywhere. Both failures are one
    question asked of the drawn page: can the reader tell this run of characters from
    the code around it.

    Each goes back as CSS and the gate is watched to fail, the third of them for the
    reading the other two can't distinguish: a role is fine on the block and unreadable
    on the tint one line wears, which a gate taking one colour per role never reaches,
    because the clean line comes first.

    The clean page is asserted to carry the roles first, because a block the tokenizer
    found nothing in passes this gate while proving nothing about it — which is the
    vacuous half of every reading here."""
    page, errors = open_page(browser, serve(COLORED_CODE_PAGE))
    roles = page.evaluate(
        "() => [...new Set([...document.querySelectorAll('[data-lf-syn]')]"
        ".map(s => s.dataset.lfSyn))].sort()"
    )
    page.close()
    assert errors == []
    assert "cm" in roles and len(roles) > 1, (
        f"this block came out {roles}, so it says nothing about a role going unread"
    )
    assert interact.render_version(browser, serve(COLORED_CODE_PAGE)) == []

    unanswered = interact.render_version(browser, serve(UNANSWERED_CODE_PAGE))
    assert [
        f
        for f in unanswered
        if f.startswith("[light] code marked cm is the ink of the code around it")
    ], unanswered

    faint = interact.render_version(browser, serve(FAINT_CODE_PAGE))
    assert [
        f for f in faint if f.startswith("[light] code marked cm reads at 3.3:1")
    ], faint
    assert not [f for f in faint if "code marked st" in f], (
        "only the role the style touched is unread, so the rest name the reading "
        "rather than the rule"
    )

    tinted = interact.render_version(browser, serve(TINTED_LINE_PAGE))
    assert [
        f for f in tinted if f.startswith("[light] code marked st reads at 1.6:1")
    ], (
        "the reading is of the surface each span is actually set on, not of one "
        f"block colour taken once per role — {tinted}"
    )

    page, errors = open_page(browser, serve(SHADOW_CODE_PAGE))
    where = page.evaluate(
        "() => ({ doc: document.querySelectorAll('[data-lf-syn]').length,"
        " shadow: [...document.querySelectorAll('*')].filter(e => e.shadowRoot)"
        ".flatMap(e => [...e.shadowRoot.querySelectorAll('[data-lf-syn=cm]')]).length })"
    )
    page.close()
    assert errors == []
    assert where == {"doc": 0, "shadow": 1}, (
        "this page has to put its only comment inside a shadow root, or the gate "
        f"passing it says nothing about the boundary — {where}"
    )
    shadowed = interact.render_version(browser, serve(SHADOW_CODE_PAGE))
    assert [
        f for f in shadowed if f.startswith("[light] code marked cm reads at 3.1:1")
    ], (
        "a widget that renders the page's words into a shadow root renders code the "
        f"reader still has to read — {shadowed}"
    )
    assert interact.render_version(browser, serve(FLAT_SHADOW_PAGE)) == [], (
        "with the box's own surface flattened, what is behind the comment is the "
        "page's paper — which is above the host, and reached by climbing out of the "
        "root rather than stopping where parentElement runs out"
    )


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
# One reading, named once, so the settle loop and the assertion cannot measure differently.
DEFINE_BOXES = """() => { window.__lfBoxes = () => window.__lfNeighbours.map(
    (n) => window.__lfOnScreen(n)
      ? [n.offsetLeft, n.offsetTop, n.offsetWidth, n.offsetHeight] : null); }"""
SETTLE_MS = 50  # a few frames: enough for a transition to finish
SETTLED = """(hold) => {
  const now = JSON.stringify(window.__lfBoxes());
  if (now !== window.__lfSettle) {
    window.__lfSettle = now;
    window.__lfSince = performance.now();
    return false;
  }
  return performance.now() - window.__lfSince > hold;
}"""


@pytest.mark.parametrize(
    ("review_meta", "shown", "absent", "kind", "tooltip"),
    [
        pytest.param(
            "",
            ".lf-end-leaf",
            ".lf-signoff",
            "close",
            "End this comments-only leaf",
            id="comments-only",
        ),
        pytest.param(
            '<meta name="lf-review" content="sign-off">',
            ".lf-signoff",
            ".lf-end-leaf",
            "done",
            "Approve this work; the page stays open for follow-up",
            id="sign-off",
        ),
    ],
)
def test_the_page_ask_chooses_its_terminal_event(
    browser, serve, review_meta, shown, absent, kind, tooltip
):
    """Ending comments is neutral; approving exists only where the page asks for it.

    Drive the shipped browser through the real POST door, since a button that merely
    looks right says nothing about the event the agent's loop receives.
    """
    html = LONG_PAGE.replace("<title>long</title>", f"<title>long</title>{review_meta}")
    page, errors = open_page(browser, serve(html))
    button = page.locator(shown)
    expect(button).to_be_visible()
    expect(button).to_have_attribute("title", tooltip)
    assert page.locator(absent).count() == 0

    button.click()
    round_trip(page)
    event = interact.read_events(serve.page_dir)[-1]
    assert (event["kind"], event["author"], event["version"]) == (kind, "user", 1)
    assert ("text" in event) is (kind == "done")
    expect(button).to_be_disabled()
    assert errors == []
    page.close()


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


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_a_press_leaves_its_neighbours_where_they_were(browser, serve, example):
    """A press may change the page; it may not move the controls next to the one pressed.

    A user works by pointing, and the line a control stands on is where their next
    gesture is already aimed. What a press changes below it is content — a tab shows a
    different panel, a fold opens, a suggestion resolves, and the page under it moves
    because the user asked it to. What must not move is the row itself, because
    nothing was asked of it and it is the one thing the user is still using.

    Three shipped controls broke this rule, each by changing a metric to say something:
    a selected tab set in 600 weight, since a bolder label is a wider one, so the strip
    reshuffled under the pointer that had just pressed it; the sign-off button, whose
    "✓ Approved" is 12px narrower than "✓ Looks good", sliding the version chooser and
    the Comments button right; and a row-form pick mark, which took the room for the
    word it says on being pressed and dragged that row's § reference 54px left. None of
    them shows in a screenshot of either state, because every strip and every row lays
    out perfectly well on its own; it is the two states together that say anything.

    Two of the three are fixed by holding the widest word's room from the start. That
    room is measured at load rather than stated, because a number read once out of a
    browser covers the face it was read in and no other: the pick column's stood at 68px
    and went 2px short the first time this ran on Linux, whose system sans sets "your
    pick" wider than macOS's. This is what said so, and it says how late a stated number
    is caught — a platform late, and only where there is a second platform to run on.

    Driven over the corpus rather than per widget: a control this sweep has never heard
    of joins it by being pressable, which is the only property it reads.

    One press per page, because a press is a gesture made on the page as published and
    the state an earlier one leaves changes what a later one proves. Pressing straight
    down the document hid the sign-off button's 12px for exactly that reason: Comments
    comes first in the banner, and with the panel open the row is crowded enough that
    the status text takes up the slack instead of the buttons — a real regression,
    silently masked by the sweep's own previous gesture."""
    url = serve(example.read_text())
    page, errors = open_page(browser, url)
    total = page.locator(PRESS).count()
    pressed, dirty = 0, False
    for i in range(total):
        if dirty:  # only a press dirties the page, and most of these indices skip
            # Reloading is not on its own a reset: the panel remembers whether it was
            # open (localStorage) and the reading position and drafts ride in
            # sessionStorage, all of them deliberately. Left standing they decide what
            # the next press proves — an open panel crowds the banner enough that the
            # status text takes up a shrinking button's slack instead of the buttons, so
            # the sign-off regression this test was written for passed or failed
            # according to how many times the sweep had toggled Comments.
            page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
            page.goto(url, wait_until="networkidle")
            # The upgrade stamp, which the reload has to earn again: half these controls
            # are the runtime's own, so a list read before it has injected them is a short
            # list — and a short list skips by index rather than failing, which is how this
            # sweep quietly stopped pressing the sign-off button between one run and the
            # next.
            page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
            dirty = False
            assert page.locator(PRESS).count() == total, (
                f"{example.name} has a different set of controls after a reload, so the "
                "indices this sweep walks name different things on either side of one"
            )
        page.evaluate(DEFINE_BOXES)
        control = page.locator(PRESS).nth(i)
        # A control the user can't press has no gesture to disturb anything. Both
        # spellings, because a span press can only ever wear the attribute.
        if not control.is_visible() or not control.is_enabled():
            continue
        if control.get_attribute("aria-disabled") == "true":
            continue
        label = control.evaluate(
            "(el) => el.tagName.toLowerCase() + ' '"
            "        + JSON.stringify((el.textContent || '').trim().slice(0, 24))"
        )
        before = control.evaluate(NEIGHBOURHOOD, NEIGHBOUR)
        if not before["names"]:
            continue
        control.click()
        pressed, dirty = pressed + 1, True
        # The press's own effect is synchronous; what follows it is the round trip the
        # press started and whatever its answer repaints, which is as much part of
        # pressing as the frame before it. A press that sent nothing is already round
        # tripped, so both kinds take the same short hold.
        round_trip(page)
        page.evaluate("() => { window.__lfSettle = null; window.__lfSince = null; }")
        page.wait_for_function(SETTLED, arg=SETTLE_MS)
        moved = displaced(before, page.evaluate("() => window.__lfBoxes()"))
        assert not moved, (
            f"pressing {label} in {example.name} moved the controls beside it:\n  "
            + "\n  ".join(moved)
        )
    assert pressed, f"{example.name} pressed nothing, so it asserts nothing"
    assert errors == []
    page.close()


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
# The promise itself, read where the user reads it. The item a click would take wears
# the outline the composer's own passage wears, so the same query answers before the press
# and after it, and the two answers agreeing is the promise being kept.
OUTLINED = """() => document.querySelector(".lf-mark-el.lf-pending")?.id ?? null"""
# What the arm says about the next press, in the one property that is on screen before
# the outline is read. Asked of body, where the aim declares it and from where it is
# inherited by everything on the page that doesn't state a cursor of its own.
AIM_CURSOR = """() => getComputedStyle(document.body).cursor"""
# All of them, for the one state that outlines two elements at once: a draft standing on
# its anchor while the ⌥ aim says where a press would move it.
OUTLINED_ALL = """() =>
  [...document.querySelectorAll(".lf-mark-el.lf-pending")].map((el) => el.id).sort()"""
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
PAGE_MARKUP = """() => [...document.body.children]
    .filter((n) => !n.classList.contains("lf-chrome"))
    .map((n) => n.outerHTML).join("").replaceAll(' class=""', "")"""


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_an_aimed_press_does_only_what_the_outline_promised(browser, serve, example):
    """⌥-click takes the item under the pointer, and that is the whole of what it does.

    Holding ⌥ outlines what a click would take, which is a promise about the next press.
    The runtime used to read that press on the way back up, after every handler out on the
    page had already had it, so the press kept the promise and did something else besides:
    ⌥-clicking an option card opened the composer *and* picked the option, sending Claude a
    decision the user never made, while ⌥-clicking a tab's name aimed at the widget and
    switched the panel under it. Neither shows in the composer, which opens either way.

    So both halves are asserted together — the composer opens on the item that was
    outlined, and the page is exactly as it was, in its markup and in where its focus sits
    — over the corpus rather than over a case, because every widget that takes a press had
    this and none of them was ever told."""
    url = serve(example.read_text())
    page, errors = open_page(browser, url)
    targets = aim_targets(serve.page_dir)
    total = page.locator(targets).count()
    pressed = aimed = 0
    for i in range(total):
        # A control inside a fold or behind an unopened tab is nowhere a user can aim,
        # which is the press sweep's reading of the same question, and a point the banner
        # or a neighbour covers is not this target's press at all.
        target = page.locator(targets).nth(i)
        if not target.is_visible():
            continue
        # A wrapper with no box of its own — a display: contents suggestion — is
        # nowhere a user can aim (AIM_POINT finds no point in it either), and
        # scroll_into_view can wait on its stability forever when it stands inside
        # a table box (a specimen). Its slots are their own targets.
        if not target.evaluate("el => el.getClientRects().length"):
            continue
        target.scroll_into_view_if_needed()
        point = target.evaluate(AIM_POINT)
        if not point:
            continue
        label = target.evaluate(NAMED)
        before = page.evaluate(PAGE_MARKUP)
        page.mouse.move(*point)
        page.keyboard.down("Alt")
        promised = page.evaluate(OUTLINED)
        # The cursor is the other half of the same promise, and it is derived from the
        # same value the outline is: the hand where a press takes something, the arrow
        # where it takes nothing. Read off body, which is where the aim declares it —
        # a widget's own control still states its resting cursor, and does so whether or
        # not the key is down.
        assert page.evaluate(AIM_CURSOR) == ("pointer" if promised else "default"), (
            f"holding ⌥ over {label} in {example.name} outlined {promised} and pointed "
            f"a {page.evaluate(AIM_CURSOR)} cursor at it"
        )
        page.mouse.click(*point)
        page.keyboard.up("Alt")
        composer = page.locator(".lf-composer")
        if promised is None:
            # Nothing outlined is nothing to aim at — no item encloses this point — and an
            # armed press then acts on nothing rather than falling back to the page. A
            # suggestion's ✓ Accept is where that matters: its row hangs in the page's own
            # column, outside the element it decides, so nothing is above it to aim at and
            # a press let through would send Claude a decision.
            expect(composer).to_be_hidden()
        else:
            expect(composer).to_be_visible()
            assert page.evaluate(OUTLINED) == promised, (
                f"⌥-clicking {label} in {example.name} outlined {promised} and commented "
                f"on {page.evaluate(OUTLINED)}"
            )
            # Put the composer away before reading the page back: its own passage wears
            # the outline, which is the one mark an aim is supposed to leave.
            page.keyboard.press("Escape")
            expect(composer).to_be_hidden()
            aimed += 1
        assert page.evaluate(PAGE_MARKUP) == before, (
            f"⌥-clicking {label} in {example.name} changed the page, so a press the aim "
            "had taken reached a widget as well"
        )
        assert not page.evaluate(FOCUS_IN_PAGE), (
            f"⌥-clicking {label} in {example.name} left the focus on the page, so the "
            "press reached the control under it"
        )
        pressed += 1
    assert pressed, f"{example.name} pressed nothing, so it asserts nothing"
    # And that the outline is still painted at all: a preview that stopped appearing would
    # leave every press above asserting only that nothing happened, which is the shape of
    # vacuous pass this sweep is most exposed to.
    assert aimed, f"{example.name} outlined nothing, so no press was held to a promise"
    # The other half of "did nothing else", and the half the markup cannot show: a widget
    # that acts tells Claude so, and a decision the user never made is worse in the log
    # than on the page. The wait is the page's own sends coming back, so a stray one is in
    # the log to be read rather than still in flight.
    round_trip(page)
    assert [
        e for e in interact.read_events(serve.page_dir) if e["kind"] == "action"
    ] == []
    assert errors == []
    page.close()


def test_a_key_still_reaches_its_control_after_an_aimed_press(browser, serve):
    """The aim holds its claim until the next press starts, and a key is not one.

    `offer` supplies the keys a span doesn't come with by calling click(), so a control
    worked from the keyboard sends a click with no press behind it. Taken for the aim's
    own, it goes nowhere at all: the user presses Enter on a pick mark and nothing is
    picked, on a page where the last thing they did with the mouse was aim."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    heading = page.locator("#t")
    heading.hover()
    page.keyboard.down("Alt")
    heading.click()
    page.keyboard.up("Alt")
    composer = page.locator(".lf-composer")
    expect(composer).to_be_visible()  # the press was the aim's, so its claim now stands
    page.keyboard.press("Escape")
    expect(composer).to_be_hidden()

    page.locator("#opt-shim .lf-pick").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#approach > lf-option[chosen]")).to_have_count(1)
    round_trip(page)
    assert [
        e["action"] for e in interact.read_events(serve.page_dir) if "action" in e
    ] == ["choose"]
    assert errors == []
    page.close()


def test_the_aim_still_promises_while_a_composer_is_open(browser, serve):
    """An armed press with the box up re-anchors it, so the aim must still say where.

    claimPress acts whether or not a composer stands open, and openComposer carries the
    typed text onto the new anchor — so the aim standing down on composerOpen, as it did
    from its first commit, left exactly one press made blind: the one that moves a
    draft. Holding ⌥ over a second item paints its outline beside the draft's own mark;
    two at once is the true state — where the draft stands, and where a press would
    move it — and the press then does what the second outline promised."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    heading = page.locator("#t")
    heading.hover()
    page.keyboard.down("Alt")
    heading.click()
    page.keyboard.up("Alt")
    composer = page.locator(".lf-composer")
    expect(composer).to_be_visible()
    composer.locator("textarea").fill("carried words")

    card = page.locator("#card-notes")
    card.hover()
    page.keyboard.down("Alt")
    promised = page.evaluate(OUTLINED_ALL)
    assert promised == ["card-notes", "t"], (
        f"holding ⌥ over a card with a draft open on the heading promised {promised}, "
        "so the press that would move the draft is blind"
    )
    card.click()
    page.keyboard.up("Alt")
    expect(composer).to_be_visible()
    expect(composer.locator("textarea")).to_have_value("carried words")
    assert page.evaluate(OUTLINED_ALL) == ["card-notes"], (
        "the press re-anchored the draft, so only its new anchor should stand outlined"
    )
    round_trip(page)
    assert [
        e for e in interact.read_events(serve.page_dir) if e["kind"] == "action"
    ] == []
    assert errors == []
    page.close()


def test_a_reload_under_a_held_aim_rearms_on_the_first_move(browser, serve):
    """The arm survives what the keydown cannot.

    `aiming` is armed by an Alt keydown, and a page reloaded under a held key — the
    poll following a new version does exactly this — never hears one, while claimPress
    reads live modifier state: every press on the new page was claimed and none could
    be promised. Mouse events carry that same live state, so the first move re-derives
    the arm; this drives that move rather than a keydown the reload already ate."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    heading = page.locator("#t")
    heading.hover()
    page.keyboard.down("Alt")
    expect(page.locator(".lf-mark-el.lf-pending")).to_have_id("t")
    page.reload()
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    expect(page.locator(".lf-mark-el.lf-pending")).to_have_count(0)  # the latch is gone
    heading.hover()  # the first move under the still-held key
    expect(page.locator(".lf-mark-el.lf-pending")).to_have_id("t")
    page.keyboard.up("Alt")
    assert errors == []
    page.close()


def test_a_scroll_under_a_held_aim_moves_the_promise_with_the_page(browser, serve):
    """What a press would take can change with no mouse event to say so.

    Only the mousemove used to re-ask the aim, so scrolling under a held key left the
    outline on the item that had been under the pointer while a press took the one now
    there — the paint answering an old page, the claim the current one. The scroll
    listener re-asks; this scrolls the page under a parked pointer and requires the
    promise to answer for where the page now stands."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.mouse.move(600, 300)
    page.keyboard.down("Alt")
    first = page.evaluate(OUTLINED)
    assert first, "nothing outlined under the parked pointer, so nothing is being aimed"
    # Three whole paragraphs of scroll, measured off the page: the paragraphs are
    # identical, so the pointer's offset into the outlined one becomes the same offset
    # into the one three later, never the margin between two. body is the page's
    # scroller, and scrollBy fires the same scroll events a wheel does.
    page.evaluate(
        """() => document.body.scrollBy(0, 3 *
          (document.getElementById("p3").getBoundingClientRect().top -
           document.getElementById("p2").getBoundingClientRect().top))"""
    )
    page.wait_for_function(
        """(first) => {
      const el = document.querySelector(".lf-mark-el.lf-pending");
      const at = document.elementFromPoint(600, 300)?.closest("[id]:not(.lf-ui)");
      return Boolean(el) && el === at && el.id !== first;
    }""",
        arg=first,
    )
    page.keyboard.up("Alt")
    assert errors == []
    page.close()


def test_a_replay_under_a_held_aim_repaints_the_promise(browser, serve):
    """A pass that runs paints the truth, whatever ran it.

    A replay of another tab's action moves content and repaints the marks where they
    now belong — and the aim used to ride that pass as an answer latched from the last
    mouse event, so the pass itself painted a promise about a card no longer there.
    The aimed item is derived inside the pass now, and the events only decide when a
    pass is worth running. Nothing here moves the mouse after the arm: the page moves
    instead, and the outline must follow or clear."""
    url = serve(REPLAYED_PAGE)
    page, errors = open_page(browser, url)
    spot = page.locator("#card-importer").evaluate(
        "el => { const r = el.getBoundingClientRect();"
        " return [r.left + r.width / 2, r.top + 8]; }"
    )
    page.mouse.move(*spot)
    page.keyboard.down("Alt")
    expect(page.locator(".lf-mark-el.lf-pending")).to_have_id("card-importer")
    interact.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "work",
            "action": "move",
            "detail": {"card": "card-importer", "to": "col-done", "index": 0},
        },
    )
    told(page)
    expect(page.locator("#col-done #card-importer")).to_have_count(1)
    page.wait_for_function(
        """([x, y]) => {
      const el = document.querySelector(".lf-mark-el.lf-pending");
      const at = document.elementFromPoint(x, y)?.closest("[id]:not(.lf-ui)") ?? null;
      return el === at && el?.id !== "card-importer";
    }""",
        arg=spot,
    )
    page.keyboard.up("Alt")
    assert errors == []
    page.close()


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


def test_a_marked_element_wears_the_same_stroke_on_every_side(browser, serve):
    """The mark is drawn in the one band of an element nobody else paints in.

    Both sides of an element's edge belong to somebody. Outside it, the mark is at
    the mercy of whatever encloses the element — a board is a scroller, so a mark
    drawn outside a column flush against its padding box was clipped down to the one
    vertical line that fell in the gutter. Inside it, the mark is at the mercy of
    what the element paints over itself: an outline is painted before positioned
    descendants, so a choose group's cells, which are relative and carry a
    background, wipe out whatever of it reaches past the group's own border.

    Neither failure moves anything, so no geometry read finds either — and both
    reach the reader as an uneven box rather than as a missing one, which is how
    this arrived: 2px two pixels in came out a hairline on a group's top and sides
    and stayed 2px along its bottom, where the last cell stops short, and what was
    reported was that the box was thicker at the bottom than the top.

    One page carries both shapes, because a fix for either alone passes half of
    this: the group is the element that paints over its own mark, the column the
    element something else clips.

    The colour is asserted here rather than assumed by the measurement, since the
    scans have to be told what to look for and taking that off the element makes the
    test blind to the one thing it is measuring in.

    The viewport is an odd number of pixels wide so that the horizontal scans are asked
    a real question. The page column is centred, so an even window puts every box on a
    whole x and both side scans then measure from exactly the padding they were handed —
    which is the one value `mark_edges` used to assume for all four sides, so half of
    what it now derives would never have run against a number that differed."""
    context = browser.new_context(
        viewport={"width": 1201, "height": 900},
        color_scheme="light",
        device_scale_factor=2,
    )
    url = serve(REPLAYED_PAGE)
    for ident in ("approach", "col-doing"):
        interact.append_event(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "version": 1,
                "text": "Say more about this.",
                "anchor": {"section": ident},
            },
        )
    page, errors = open_page(browser, url, context=context)
    expect(page.locator("#approach.lf-mark-el")).to_have_count(1)
    expect(page.locator("#col-doing.lf-mark-el")).to_have_count(1)
    ink = token_colour(page, "--mark-ink")
    for ident in ("approach", "col-doing"):
        painted = page.evaluate(
            "(id) => getComputedStyle(document.getElementById(id)).outlineColor", ident
        )
        assert painted == ink, (
            f"the mark on #{ident} is painted {painted}, not the comment layer's own "
            f"--mark-ink ({ink})"
        )
        edges = mark_edges(page, ident, tuple(int(n) for n in re.findall(r"\d+", ink)))
        widths = {side: sorted(seen) for side, seen in edges.items()}
        assert all(len(seen) == 1 for seen in edges.values()), (
            f"the mark on #{ident} changes width along a side: {widths}"
        )
        stroke = {next(iter(seen)) for seen in edges.values()}
        assert 0 not in stroke, f"the mark on #{ident} is missing from a side: {widths}"
        assert len(stroke) == 1, (
            f"the mark on #{ident} is not the same stroke on every side: {widths}"
        )
    assert errors == []
    page.close()
    context.close()


def test_the_chrome_keeps_its_presses_while_the_page_is_armed(browser, serve):
    """What ⌥ arms is the page, and the line around it is the chrome's container.

    An aim that reached in there would take the panel, the composer and the banner away
    from a user who happens to be holding the key — and there is nothing in the layer
    to aim at anyway, since an anchor names an element of the page."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    comments = page.locator(".lf-comments")
    comments.hover()
    page.keyboard.down("Alt")
    comments.click()
    page.keyboard.up("Alt")
    panel_settled(page)
    expect(page.locator(".lf-panel")).to_be_visible()
    expect(page.locator(".lf-composer")).to_be_hidden()
    assert errors == []
    page.close()


def test_the_armed_cursor_says_whether_a_press_would_take_anything(browser, serve):
    """The chord's cost is that it is invisible, and the cursor pays part of it.

    Holding ⌥ used to draw a plain arrow over the whole page: it said "not a text
    selection" and nothing else, which leaves the one question the outline can't answer
    for a reader who hasn't looked yet — would this click do anything at all? An armed
    press takes the item under it and acts on nothing where there is none (claimPress),
    so the hand and the arrow are those two states, and the hand is exactly as good as
    the outline beside it because both are read off the same value.

    Read where the reader's pointer is rather than off body, since the aim declares it
    on body and everything on the page inherits it — the promise is only kept if it
    arrives at the glyphs. The margin beside the column is the page's own gap: no
    element there carries an id, so an armed press has nothing to take.

    `auto` is the resting state, and it is the whole point of the arrow: unarmed, the
    browser decides from what is under the pointer and draws an I-beam over words, so
    naming a cursor at all is the runtime saying those words are not a selection now."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    at_pointer = """([x, y]) =>
        getComputedStyle(document.elementFromPoint(x, y)).cursor"""
    on_item = page.locator("#p2").evaluate(
        "el => { const r = el.getBoundingClientRect();"
        " return [r.left + 20, r.top + r.height / 2]; }"
    )
    # Beside the column, level with the same paragraph: body's own margin, which the
    # centred 720px column leaves on a 1200px viewport.
    in_gap = [40, on_item[1]]
    assert page.evaluate(at_pointer, on_item) == "auto", (
        "an unarmed page already named a cursor, so the arm has nothing left to say"
    )

    page.mouse.move(*on_item)
    page.keyboard.down("Alt")
    expect(page.locator(".lf-mark-el.lf-pending")).to_have_id("p2")
    assert page.evaluate(at_pointer, on_item) == "pointer", (
        "the aim outlined the paragraph and the cursor declined to promise the press"
    )

    page.mouse.move(*in_gap)
    expect(page.locator(".lf-mark-el.lf-pending")).to_have_count(0)
    assert page.evaluate(at_pointer, in_gap) == "default", (
        "the aim had nothing to take and the hand promised a press anyway"
    )

    # Back on the item, so the arm coming off is read from the state that promises most.
    page.mouse.move(*on_item)
    expect(page.locator(".lf-mark-el.lf-pending")).to_have_id("p2")
    page.keyboard.up("Alt")
    expect(page.locator(".lf-mark-el.lf-pending")).to_have_count(0)
    assert page.evaluate(at_pointer, on_item) == "auto", (
        "the key came up and the page went on offering the aim's press"
    )
    assert errors == []
    page.close()


def test_the_poll_leaves_the_banner_where_it_was(browser, serve):
    """The other half of the same rule, for the changes nobody asked for.

    A press has a line — the row the pressed control stands on, where the next gesture
    is already aimed — and below it the page is content and may move. News arriving on
    the poll has no gesture at all, so there is no line to draw: the user was
    somewhere else entirely, and every control in the chrome is an address they are
    holding. The document may still change under them, because a fact arriving is what
    they are here to see; the address it arrives at may not.

    The banner is where all of it lands, and it is packed to the right against a spacer,
    which decides who pays. A control that grows moves itself and everything to its
    *left*; everything to its right keeps its place. So `Comments (9)` becoming
    `Comments (10)` — a comment posted from the terminal while the user reads —
    slid the version chooser 6px left, and the ✓ Accept all a second tab's decision puts
    away took the New-version chip with it.

    Driven by writing the events a real one would leave, since that is what the page
    reads either way, and there is no other way to reach this half: every gesture the
    press sweep above can make is one the user made, and none of these are."""
    # Three pending suggestions, so the ✓ Accept all count has somewhere to go before it
    # runs out; sign-off asked, so the row is the full one; nine comments already, so the
    # tenth crosses a digit; and pinned, so a v2 landing leaves the page where it is and
    # offers the chip rather than following it.
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html, comments=9)
    d = serve.page_dir
    page, errors = open_page(browser, url, pin=True)
    comments = ".lf-banner .lf-comments"
    accept_all = '.lf-banner [title^="Accept every"]'
    page.wait_for_function(
        f"() => document.querySelector('{comments}').textContent === 'Comments (9)'"
    )

    def publish_v2():
        (d / "versions" / "v2.html").write_text(html)
        interact.append_event(
            d, {"kind": "note", "author": "claude", "version": 2, "text": "two"}
        )

    # The same events a second tab's presses would have posted, which is the only way one
    # user's browser hears about another's decisions.
    def decide(*widgets):
        for widget in widgets:
            interact.append_event(
                d,
                {
                    "kind": "action",
                    "author": "user",
                    "version": 1,
                    "widget": widget,
                    "action": "accept",
                    "detail": {},
                },
            )

    for what, drive, arrived in [
        (
            "a tenth comment arrives",
            lambda: interact.append_event(
                d,
                {"kind": "comment", "author": "user", "version": 1, "text": "A tenth."},
            ),
            f"() => document.querySelector('{comments}').textContent === 'Comments (10)'",
        ),
        (
            "a new version is published",
            publish_v2,
            (
                "() => document.querySelector('.lf-latest-chip')"
                ".checkVisibility({visibilityProperty: true})"
            ),
        ),
        (
            "another tab decides two of the three pending suggestions",
            lambda: decide("sug-refill", "sug-thistle"),
            (
                f"() => document.querySelector('{accept_all}')"
                ".textContent === '\\u2713 Accept all (1)'"
            ),
        ),
        (
            "another tab decides the last one",
            lambda: decide("sug-in-card"),
            # Gone, asked the way it is now gone: a control that has stood on this row keeps
            # its room, so its box is exactly what must not have changed here.
            (
                f"() => !document.querySelector('{accept_all}')"
                ".checkVisibility({visibilityProperty: true})"
            ),
        ),
    ]:
        page.evaluate(DEFINE_BOXES)
        before = page.evaluate(BANNER_WATCH, NEIGHBOUR)
        assert len(before["names"]) >= 4, (
            f"before {what} the banner was showing only {before['names']}, which is "
            "fewer controls than it always has — this step asserts almost nothing"
        )
        drive()
        page.wait_for_function(arrived)
        page.evaluate("() => { window.__lfSettle = null; window.__lfSince = null; }")
        page.wait_for_function(SETTLED, arg=SETTLE_MS)
        moved = displaced(before, page.evaluate("() => window.__lfBoxes()"))
        assert not moved, f"{what} and the banner moved:\n  " + "\n  ".join(moved)

    # A reservation is a promise the row can keep only while it has the room, and a row
    # out of room takes it from whatever will give. Every control up there is a .lf-btn,
    # floored at its own words by nowrap, so none of them is what gives: what does is the
    # status text and the chip, which is where the spacer's slack was — both left of
    # everything else on the row, so what they give up moves nothing. The chooser was the
    # exception while it was a <select> stating a width against unbounded notes: it was
    # the one control that could give, so it did, dropping under the width it states and
    # putting every arrival above back in play on any window narrow enough. It says the
    # version alone now, so it is floored like the rest and this list covers the whole row.
    holds_its_width = (
        "() => ['.lf-version', '.lf-comments', '.lf-signoff', '.lf-answer-all', '.lf-asks']"
        ".map((s) => document.querySelector('.lf-banner ' + s).offsetWidth)"
    )
    wide = page.evaluate(holds_its_width)
    resized(page, 900, 900)
    # Out of room, and something has visibly given: no spacer left, and the chip showing
    # less than it holds. Without both, a window that still had slack would assert nothing.
    page.wait_for_function(
        "() => { const chip = document.querySelector('.lf-latest-chip');"
        "        return document.querySelector('.lf-spacer').offsetWidth === 0"
        "               && chip.offsetWidth < chip.scrollWidth; }"
    )
    assert page.evaluate(holds_its_width) == wide, (
        "a banner with no room left took it out of the controls that hold their width, "
        "which is what leaves them free to move on the next thing that arrives"
    )
    assert errors == []
    page.close()


@pytest.fixture
def live_leaf(tmp_path, monkeypatch):
    """Stands up a live leaf for the banner's panel to find: published, served by
    a real handler, and written down under the state home the way `server run` writes
    it — which is the whole of how one page learns another exists. Each claims to be
    working, freshly, so its row has a judged state to show. A factory rather than one
    fixture, because a board is a list and a walk down it needs somewhere to walk to."""
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
        httpd = interact.LeafHTTPServer(
            ("127.0.0.1", 0), interact.handler_for(d, TOKEN)
        )
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        servers.append(httpd)
        port = httpd.server_address[1]
        # Held, not merely written: the exclusive lock on the record is what
        # says a server is up, so a neighbour this fixture stands up holds one
        # exactly as `server run` does.
        record = open(d / "server.json", "a+b")  # noqa: SIM115 - held, see above
        fcntl.flock(record, fcntl.LOCK_EX | fcntl.LOCK_NB)
        record.write(
            interact.json_bytes(
                {
                    "port": port,
                    "pid": os.getpid(),
                    "url": f"http://127.0.0.1:{port}/?t={TOKEN}",
                }
            )
        )
        record.flush()
        held.append(record)
        return f"http://127.0.0.1:{port}", d

    yield go
    for httpd in servers:
        httpd.shutdown()
    for record in held:
        record.close()


@pytest.fixture
def other_leaf(live_leaf):
    return live_leaf("other", "The other leaf")


def test_the_banner_opens_a_panel_of_the_machines_leaves(browser, serve, other_leaf):
    """The leaves panel, end to end: the banner counts the machine's live pages,
    this one included, a press slides out a left board headed by this page's own
    marked, unlinked row, each neighbour is a link named by its title and saying what
    that page is doing — the same judgment its own banner would show, from the same facts — and a
    link opens that page in a tab of its own, leaving this one where it was, panel
    standing. Esc is the panel's rung on the ladder. On a machine serving nothing
    else the button never appears, which every other test here shows for free."""
    other_url, _ = other_leaf
    page, errors = open_page(browser, serve(LONG_PAGE))
    btn = page.locator(".lf-others")
    expect(btn).to_have_text("All leaves (2)")
    btn.click()
    others_panel = page.locator(".lf-others-panel")
    expect(others_panel).to_be_visible()
    # This page heads the list, marked and never a link: the panel reads as the
    # whole machine, and this page is where the reader already is.
    self_row = others_panel.locator(".lf-others-self")
    expect(self_row.locator(".lf-pill")).to_have_text("this page")
    expect(self_row.locator(".lf-others-title")).to_have_text("long")
    link = others_panel.locator("a.lf-others-row")
    expect(link.locator(".lf-others-title")).to_have_text("The other leaf")
    # The fixture's page claims working with a fresh ts and nothing contradicts it,
    # so the row says so — dot and words both the banner's own vocabulary.
    expect(link.locator(".lf-others-line")).to_have_text("Working — running the suite")
    expect(link.locator(".lf-dot")).to_have_class(re.compile(r"\bworking\b"))
    with page.context.expect_page() as opened:
        link.click()
    # The other server's own redirect lands the new tab on its newest published
    # version, authorized by the key the link carried.
    expect(opened.value).to_have_url(f"{other_url}/versions/v1.html")
    # The press left this tab alone, board still standing.
    expect(others_panel).to_be_visible()
    page.keyboard.press("Escape")
    expect(others_panel).not_to_be_visible()
    expect(btn).to_be_visible()  # closing the panel keeps the standing button
    expect(btn).to_have_text("All leaves (2)")  # and the count
    # The count's reservation, swept here because this is the one test that ever
    # renders the button — every other page here runs under an isolated state home, so
    # neither the press sweep nor the poll test can reach it. The widest label
    # below a thousand must not move the control.
    before, widest = page.evaluate(
        """() => { const b = document.querySelector('.lf-others');
                   const before = b.offsetWidth;
                   b.textContent = 'All leaves (999)';
                   return [before, b.offsetWidth]; }"""
    )
    assert widest == before, (
        f"'All leaves (999)' grew the button {before}px -> {widest}px: its "
        "reserve list no longer names the widest label renderOthers writes"
    )
    assert errors == []
    page.close()


def test_a_panel_row_follows_its_pages_status_live(
    browser, serve, other_leaf, dead_pid
):
    """The panel is a status board, not a snapshot: a neighbour's state changing on
    disk repaints its row at the next poll, in place — and a neighbour whose claimant
    has exited reads as unheld, the computed fact its own banner would state, not the
    claim its status file still makes."""
    _, other_dir = other_leaf
    page, errors = open_page(browser, serve(LONG_PAGE))
    # The key is live once the list has arrived, which the button's count states.
    expect(page.locator(".lf-others")).to_have_text("All leaves (2)")
    page.keyboard.press("o")  # the key opens the panel like the button does
    row = page.locator("a.lf-others-row")
    expect(row.locator(".lf-others-line")).to_have_text("Working — running the suite")
    interact.write_json(
        other_dir / "status.json",
        {"state": "working", "detail": "recording the demo", "ts": interact.now_iso()},
    )
    told(page)
    expect(row.locator(".lf-others-line")).to_have_text("Working — recording the demo")
    # A neighbour waiting on its own reader says so in this seat's shorter words, and
    # in the same term its banner uses: one word per state across the product, or a
    # user reading both surfaces has to work out whether they mean the same thing.
    # Its own watcher has to be live for that, which is what the neighbour's heartbeat
    # is — judged from the same evidence its banner judges itself on.
    interact.write_json(
        other_dir / "status.json",
        {"state": "waiting", "detail": "", "ts": interact.now_iso()},
    )
    with live_watcher(other_dir, page):
        expect(row.locator(".lf-others-line")).to_have_text("Awaits")
        # And what it is waiting for, because the panel is where a reader picks which
        # page to go to: the row that says a page needs them carries the ask, the way
        # the working row above carries what its agent is doing. Its own tooltip too —
        # the line ellipsizes at the panel's width and the row's tooltip holds the page
        # title, so without one the ask is what a narrow hover cannot recover.
        interact.write_json(
            other_dir / "status.json",
            {
                "state": "waiting",
                "detail": "pick a storage engine",
                "ts": interact.now_iso(),
            },
        )
        told(page)
        line = row.locator(".lf-others-line")
        expect(line).to_have_text("Awaits — pick a storage engine")
        expect(line).to_have_attribute("title", "Awaits — pick a storage engine")
    # The claim still says waiting; its claimant is gone. The row reports what the
    # directory can prove, exactly as the neighbour's own banner would.
    interact.write_json(
        other_dir / "session.json",
        {"id": "s", "host": "claude-code", "pid": dead_pid, "agent": "Claude"},
    )
    told(page)
    expect(row.locator(".lf-others-line")).to_have_text("Unheld")
    expect(row.locator(".lf-dot")).not_to_have_class(re.compile(r"\bworking\b"))
    assert errors == []
    page.close()


def test_a_closed_leaf_clears_itself_off_the_board(browser, serve, other_leaf):
    """A closed leaf leaves the board on the poll that says so. Its server stays
    up — a standing one for good — so the row would otherwise stand forever and the
    count a reader glances at to find who needs them would become a tally of
    everything that has ever run here. This page's own row never drops — a reader
    looking at a closed page is still looking at it — so a board with nothing live
    left on it still says where the reader is, and the count says (1) for it."""
    _, other_dir = other_leaf
    page, errors = open_page(browser, serve(LONG_PAGE))
    btn = page.locator(".lf-others")
    expect(btn).to_have_text("All leaves (2)")
    page.keyboard.press("o")
    rows = page.locator("a.lf-others-row")
    expect(rows).to_have_count(1)
    interact.write_json(
        other_dir / "status.json",
        {"state": "idle", "detail": "", "ts": interact.now_iso()},
    )
    told(page)
    expect(rows).to_have_count(0)
    expect(btn).to_have_text("All leaves (1)")
    expect(page.locator(".lf-others-self .lf-others-title")).to_have_text("long")
    # Nothing live left to open: the button stands while the panel does and stands
    # down with it, which is the count's other half.
    page.keyboard.press("Escape")
    told(page)
    expect(btn).not_to_be_visible()
    assert errors == []
    page.close()


def test_the_leaves_board_takes_the_keyboard(browser, serve, live_leaf):
    """The board is a list, and a reader walks it without reaching for the mouse: o
    opens it and lands on the first neighbour, up and down step between them and clamp
    at the ends, Enter opens the focused one in its own tab, and Esc hands focus back
    to the button that opened it. The key line names o before it is pressed and the
    board's own keys while focus is inside it — the promise and the press being one
    scene — and the "?" reference carries the same rows."""
    live_leaf("second", "A second leaf")
    other_url, _ = live_leaf("other", "The other leaf")
    page, errors = open_page(browser, serve(LONG_PAGE))
    btn = page.locator(".lf-others")
    expect(btn).to_have_text("All leaves (3)")
    keyline = page.locator(".lf-keyline")
    # A shortcut no surface names is a shortcut nobody finds: the line carries o for
    # exactly as long as there is a board to open.
    expect(keyline).to_contain_text("leaves")
    page.keyboard.press("o")
    rows = page.locator("a.lf-others-row")
    # Titles order the board, so the walk has a stated first row to start from.
    expect(rows.first.locator(".lf-others-title")).to_have_text("A second leaf")
    expect(rows.first).to_be_focused()
    expect(keyline).to_contain_text("walk the leaves")
    expect(keyline).to_contain_text("open it in a tab")
    page.keyboard.press("ArrowDown")
    expect(rows.nth(1)).to_be_focused()
    page.keyboard.press("ArrowDown")  # clamped at the end, never wrapped to the top
    expect(rows.nth(1)).to_be_focused()
    page.keyboard.press("ArrowUp")
    expect(rows.first).to_be_focused()
    # Enter is the browser's own on a link, which is why the row is one.
    page.keyboard.press("ArrowDown")
    with page.context.expect_page() as opened:
        page.keyboard.press("Enter")
    expect(opened.value).to_have_url(f"{other_url}/versions/v1.html")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-others-panel")).not_to_be_visible()
    # Closing while focus is inside would drop the reader on the body; it lands on
    # the one control that reopens what just closed.
    expect(btn).to_be_focused()
    page.keyboard.press("?")
    help_el = page.locator(".lf-help")
    expect(help_el).to_contain_text("In the leaves panel")
    expect(help_el).to_contain_text("walk the leaves")
    assert errors == []
    page.close()


def test_esc_in_the_comment_panel_stays_the_panels_while_the_board_stands(
    browser, serve, other_leaf
):
    """With both panels standing, Esc takes the leaves board first — but only
    while focus stands outside the comment panel. A reader backing out of the
    general box is standing on the panel's list, and their next Esc used to close
    the board on the far side of the screen instead: the key left the work it was
    unwinding, and the reader watching the right edge saw nothing happen. The rung
    asks where focus is, not which things are open, and there is one definition of
    it for the thread, the list and the page scenes alike."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=1))
    expect(page.locator(".lf-others")).to_have_text("All leaves (2)")
    page.keyboard.press("o")  # the board first, then the panel over it
    page.keyboard.press("c")
    expect(page.locator(".lf-general textarea")).to_be_focused()
    page.keyboard.press("Escape")  # back out of the box, onto the panel's list
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(page.locator(".lf-keyline")).to_contain_text("close comments")
    page.keyboard.press("Escape")  # the panel the reader stands in, not the board
    expect(page.locator(".lf-panel")).to_be_hidden()
    expect(page.locator(".lf-others-panel")).to_be_visible()
    # Focus lands on the panel's reopening control, outside both panels, so the
    # ladder's next rung is the board's — the glance closes last.
    expect(page.locator(".lf-comments")).to_be_focused()
    expect(page.locator(".lf-keyline")).to_contain_text("close leaves")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-others-panel")).not_to_be_visible()
    assert errors == []
    page.close()


def test_a_walk_down_the_board_stops_clear_of_the_key_line(browser, serve, live_leaf):
    """The board is the page's other scroll region and the key line stands over its
    bottom-left corner, so the board reserves the line's room — for the walk, which
    scrolls no further than it must, and for the wheel, which runs to the end. Both
    are asserted because they take their room from different places, and the walk's
    clearance without one is only however far the browser happens to overshoot: a
    fact about row height rather than about the line standing there."""
    names = [f"Leaf {i}" for i in range(6)]
    for i, title in enumerate(names):
        live_leaf(f"n{i}", title)
    page, errors = open_page(browser, serve(LONG_PAGE))
    expect(page.locator(".lf-others")).to_have_text(f"All leaves ({len(names) + 1})")
    # Short enough that the rows overflow the board, which is the only shape in which
    # the reservation is the difference between a clear last row and a covered one.
    resized(page, 900, 320)
    page.keyboard.press("o")
    rows = page.locator("a.lf-others-row")
    for _ in names:
        page.keyboard.press("ArrowDown")
    expect(rows.last).to_be_focused()
    board = page.locator(".lf-others-panel")
    assert page.evaluate(
        "() => { const b = document.querySelector('.lf-others-panel');"
        "        return b.scrollHeight > b.clientHeight; }"
    ), (
        "the board never overflowed, so the walk had nothing to scroll and proves nothing"
    )
    last = rows.last.bounding_box()
    line = page.locator(".lf-keyline").bounding_box()
    assert last["y"] + last["height"] <= line["y"], (
        f"the walk parked the last row at {last} under the key line at {line}"
    )
    # And a reader who scrolls the board to its end by hand lands in the same place:
    # scroll-padding answers the walk, the padding under it answers the wheel.
    board.evaluate("(b) => b.scrollTo({top: b.scrollHeight})")
    last = rows.last.bounding_box()
    assert last["y"] + last["height"] <= line["y"], (
        f"scrolled to its end the board put its last row at {last}, under the key "
        f"line at {line}"
    )
    assert errors == []
    page.close()


# A run with nothing to break on, in the three places a page puts one: a metric's headline,
# where the box is a fixed 138px and the value is whatever the number turned out to be;
# ordinary prose, which is where a page about code keeps its paths; and a tree, whose module
# writes the name and its badges with no whitespace between them at all.
UNBREAKABLE_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>unbreakable</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_a_run_with_nothing_to_break_on_stays_inside_the_box_holding_it(browser, serve):
    """Text that cannot wrap does not stop at the edge of its box; it paints straight on
    over whatever the layout put beside it, and nothing about the boxes says so — every
    rect is exactly where it should be. A twelve-character metric value ran 287px out of a
    138px card, and a phone's 372px column is narrower than half the paths this product's
    prose is made of.

    Told it may break a word, the browser will also break one that was never meant to come
    apart: the tree's module spaces its badges by margin and writes no whitespace between
    them, so a line is one word to the breaker, and it split a two-character badge down the
    middle and drew half the pill on each line. Read at a phone's width, where the column
    has the least to give and each of the three is at its worst."""
    page, errors = open_page(browser, serve(UNBREAKABLE_PAGE))
    resized(page, 420, 900)
    inside = """(id) => {
                  const el = document.getElementById(id);
                  const inner = el.querySelector("[data-lf-said='value']") ?? el;
                  const range = document.createRange();
                  range.selectNodeContents(inner);
                  const style = getComputedStyle(el);
                  return range.getBoundingClientRect().right -
                         (el.getBoundingClientRect().right - parseFloat(style.paddingRight));
                }"""
    assert page.evaluate(inside, "m-token") <= 0, (
        "a metric's value paints outside its card"
    )
    assert page.evaluate(inside, "p-token") <= 0, (
        "a path in prose paints outside the column"
    )
    torn = """() => [...document.querySelectorAll('.lf-tree-badge')]
                      .map((b) => b.getClientRects().length)"""
    assert page.evaluate(torn) == [1, 1], "a badge is one pill, and it was drawn as two"
    assert errors == []
    page.close()


# One line past any phone column, so the box a diff renders in has to scroll and the
# rule is the one on trial rather than the fit.
WIDE_DIFF_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>wide diff</title>
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="t">A diff wider than the column</h1>
<lf-diff id="wide-diff"><pre>
diff --git a/client/offline/merge.ts b/client/offline/merge.ts
--- a/client/offline/merge.ts
+++ b/client/offline/merge.ts
@@ -18,2 +18,2 @@ export function merge(base: Doc, mine: Edit[], theirs: Edit[]): Doc {
-  return apply(base, [...theirs, ...mine]);
+  const clash = theirs.find((t) =&gt; t.field === edit.field &amp;&amp; t.at &gt; edit.at);
</pre></lf-diff>
</main>
</body>
</html>
"""


def test_a_scroll_box_inside_a_widgets_shadow_tree_takes_the_keyboard(browser, serve):
    """Anything a mouse can scroll, a keyboard can reach — including the box a widget
    renders inside its own shadow tree. `reachScrollers` walks the tree it is handed,
    and `querySelectorAll` stops dead at a shadow boundary, so a diff was the one
    scrolling box on a page that a keyboard user had no way into: no tab stop of its
    own, and unlike a board no control inside to borrow one from. The axe sweep says
    so too, and only while some example's diff happens to carry a line this long; this
    is the same rule asked of the widget rather than of the corpus."""
    page, errors = open_page(browser, serve(WIDE_DIFF_PAGE))
    resized(page, 420, 900)
    measured = page.locator("#wide-diff").evaluate(
        """(d) => {
        const pre = d.shadowRoot.querySelector('pre');
        return { scrolls: Math.round(pre.scrollWidth - pre.clientWidth),
                 tab: pre.tabIndex };
    }"""
    )
    # The reach, then that there was anything to reach: a diff narrow enough to fit
    # takes no tab stop and is right not to, which would pass the first assertion
    # while saying nothing about the rule.
    assert measured["scrolls"] > 0, "this diff fits, so it proves nothing"
    assert measured["tab"] == 0, "a diff that scrolls is unreachable from the keyboard"
    assert errors == []
    page.close()


# The same diff, arriving the other way a widget reaches a reader: on a reply, into a
# column narrower than any page's.
PANEL_DIFF_MARKUP = WIDE_DIFF_PAGE[
    WIDE_DIFF_PAGE.index("<lf-diff") : WIDE_DIFF_PAGE.index("</lf-diff>")
    + len("</lf-diff>")
].replace('id="wide-diff"', 'id="rp-diff"')


def test_a_scroll_box_in_a_panel_reply_takes_the_keyboard(browser, serve):
    """The panel holds the same scroll boxes the page does — a reply carries whatever
    widget markup the gate allows — and its column is the narrower of the two, so a box
    that scrolls anywhere scrolls here.

    The sweep that was supposed to cover this stood where each message body is built,
    and needed two things it did not have: that body is not in the document yet, where
    `getComputedStyle` answers "" for every property, and the widget in it has not
    rendered, where the look a scroll box has arrives with the class its module sets on
    the way out. It read an empty overflow off everything it walked and had tagged
    nothing since it was written, which reads as coverage and is the only reason it
    lasted.

    The reply arrives while the panel is already open, because that is the case with
    exactly one reconcile in it. A diff renders asynchronously, so a sweep run where the
    panel inserts its nodes walks a host whose shadow root is still null, and the panel
    does not reconcile on a timer to fix it later: `renderPanel` runs on an open, on a
    fold finishing, and on a new event. Seeding the reply before the page loads gives
    two reconciles and hides all of that."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    interact.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-diff",
            "author": "user",
            "version": 1,
            "text": "What does the change look like?",
        },
    )
    page, errors = open_page(browser, url)
    page.get_by_role("button", name="Comments", exact=False).click()
    page.wait_for_selector(".lf-thread")  # the panel is open and reconciled once
    interact.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-diff",
            "version": 1,
            "text": "The one line that decides it:",
            "markup": PANEL_DIFF_MARKUP,
        },
    )
    page.wait_for_function(
        """() => {
        const d = document.querySelector('#rp-diff');
        const pre = d && d.shadowRoot && d.shadowRoot.querySelector('pre');
        return Boolean(pre) && pre.tabIndex === 0;
    }"""
    )
    scrolls = page.locator("#rp-diff").evaluate(
        "(d) => Math.round(d.shadowRoot.querySelector('pre').scrollWidth"
        " - d.shadowRoot.querySelector('pre').clientWidth)"
    )
    assert scrolls > 0, "this diff fits the panel, so it proves nothing"
    assert errors == []
    page.close()


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


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
@pytest.mark.parametrize("color_scheme", ["light", "dark"])
@pytest.mark.parametrize("width", [1200, 420])
def test_examples_have_no_serious_wcag_a_or_aa_violations(
    browser, serve, example, color_scheme, width
):
    """Axe covers semantic failures the render gate cannot see: an unnamed control,
    an invalid role relationship, or a contrast failure can occupy a perfectly good
    box and still shut a user out. Keep the scope to WCAG A/AA and actionable
    serious/critical findings; layout and accessibility-tree snapshots belong to
    specific regressions, not a corpus baseline that changes with every restyle.

    A phone's width because what a box does there is a different question and not a
    smaller one: the column is 372px, so a block that had room at a desk starts
    scrolling, and a scrolling box with no way into it from the keyboard is a user
    reading half of every line of code. Nothing at 1200 says a word about it."""
    page, errors = open_page(browser, serve(example.read_text()))
    resized(page, width, 900)
    page.emulate_media(color_scheme=color_scheme)
    violations, report = serious_axe_violations(page)
    assert violations == [], report
    assert errors == []
    page.close()


def test_the_gate_passes_a_page_that_carries_a_comment(browser, serve):
    """The gate refuses words under `.lf-ui` inside a widget, because a widget reaching for
    that marker is how a user ends up unable to comment on a heading they can see. The
    line saying how many comments are on a passage wears the same marker and sits wherever
    the passage does — inside the widget, when that is where the comment was made. Unless
    the gate knows the difference, one comment on an option is a page nobody can hand over,
    and every page the sweep above renders is a page with no comments on it.

    The pass hunting words drawn on other words has to know the same difference, and knows
    it the same way — by whose words these are. That line is clipped to nothing and
    checkVisibility answers for display, visibility and opacity, so it reads as drawn, and
    its characters fall down the document through the paragraphs under the passage. Holding
    it out is the only thing keeping this page clean, so the reading is taken twice: once
    as the gate runs it, and once with the line no longer held out, where it has to
    report."""
    # The last option, because the unheld half below needs the line to land on words:
    # the note is the holder's last child, so its characters fall from the end of the
    # option's own prose, and from a mid-group option they fall through the whitespace
    # tails of the shorter cells below and are spent before any paragraph. From the
    # group's last option they cross straight into #p, whose full-width lines have a
    # word at any x the option's prose can end on.
    url = serve(INLINE_PAGE, anchored=[("opt-b", "quietly puts one back")])
    page, errors = open_page(browser, url)
    # Vacuous otherwise: the gate has to be looking at a page that has the line on it.
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-mark-note').length === 1"
    )
    # The same reading with the line no longer held out, taken while the page is up.
    # Named out of the selector rather than cut from it, so the reading stays this
    # reading however the classes it holds out are ordered or added to.
    unheld = interact.COVERED_WORDS.replace(".lf-mark-note", ".lf-holds-nothing")
    reported = page.evaluate(unheld)
    assert errors == []
    page.close()
    assert interact.render_version(browser, url) == []
    assert unheld != interact.COVERED_WORDS, (
        "the pass no longer holds the line out by name"
    )
    assert any("1 comment" in found for found in reported), (
        "the line falls on nobody, so a gate that never looked would pass this too"
    )


def test_the_gate_passes_a_page_whose_collapsed_cards_lie_on_each_other(browser, serve):
    """Words drawn on other words is a question about the screen, and a collapse is the
    page being asked to take words off it. The cards behind a settled row wear
    hidden="until-found" so find-in-page still reaches them, which is content-visibility
    rather than display, and checkVisibility answers for neither: they read as drawn, and
    each reports the box it last laid out in, so all three land on one another. That is
    the collapse working, and COVERED_WORDS says why it is held out.

    On a fresh load whether they report at all is a coin, which is no basis for a test.
    Opening the row and closing it again settles it: the cards lay out for real, and the
    boxes they keep afterwards are that layout."""
    url = serve(SETTLED_PAGE)
    page, errors = open_page(browser, url)
    row = page.locator("#transport .lf-settled")
    card = page.locator("#transport #opt-lax")

    row.click()
    expect(card).to_be_visible()
    row.click()
    expect(card).to_be_hidden()

    # The gate's own reading, taken here rather than left to render_version: that opens a
    # fresh page, which is the coin again, and this page is the one holding the layout the
    # cards kept. Then the same reading with the collapse no longer held out — named out
    # of the selector rather than cut from it, so this stays the gate's reading however
    # the things it holds out are ordered or added to.
    unheld = interact.COVERED_WORDS.replace("[hidden]", "[lf-holds-nothing]")
    held, reported = page.evaluate(interact.COVERED_WORDS), page.evaluate(unheld)
    assert errors == []
    assert held == []
    assert unheld != interact.COVERED_WORDS, (
        "the pass no longer holds collapsed content out by name"
    )
    assert any("opt-" in found for found in reported), (
        "the cards fell on nobody, so a gate that never looked would pass this too"
    )
    page.close()
    assert interact.render_version(browser, url) == []


# Chips whose words are a price and nothing else, which is two or three characters and
# about 30px. Nothing else on the page is unusual, so the chips are the only thing on it
# that a floor written for widgets laying out a region could catch.
SHORT_CHIP_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>chips</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="t">Feeder extras</h1>
<p id="p">The bracket order goes in on Friday and there is room in it.</p>
<lf-options id="extras" choose multiple>
<lf-option id="x-tray"><lf-chip>£9</lf-chip>
<strong>Seed tray</strong> Catches the spill under the south pair.
</lf-option>
<lf-option id="x-dome"><lf-chip tone="ok">£15</lf-chip>
<strong>Weather dome</strong> Keeps the seed dry through a wet week.
</lf-option>
</lf-options>
</main>
</body>
</html>
"""


def test_the_gate_measures_an_inline_widget_by_its_words(browser, serve):
    """A chip is set among the words around it, so its box is the words in it and there is
    no width it was ever going to reach. Held to the floor written for a widget that lays
    out a region, a chip saying `£9` reads as a collapse, and the gate refuses a page with
    nothing wrong with it — for a price, which is the shortest thing an author is likely to
    put in one.

    The floor a chip does keep is the height, since a line of words is a line tall under
    any layout. Both halves are asserted, because a floor deleted outright passes the
    first on its own."""
    url = serve(SHORT_CHIP_PAGE)
    page, errors = open_page(browser, url)
    widths = page.locator("lf-chip").evaluate_all(
        "els => els.map(el => Math.round(el.getBoundingClientRect().width))"
    )
    assert errors == []
    assert widths and max(widths) < 40, (
        f"these chips are {widths}px, so they clear the floor and prove nothing"
    )

    # Flattened, the same chips are a collapse and the gate says so — the reading the
    # declaration narrows rather than switches off.
    page.add_style_tag(
        content="lf-chip { display: block; height: 2px; overflow: hidden; }"
    )
    flattened = page.evaluate(interact.TINY_BOXES)
    page.close()
    assert [box for box in flattened if box["tag"] == "lf-chip"], (
        "a chip with no height left reports nothing, so the floor is gone rather than declared"
    )
    assert interact.render_version(browser, url) == []


def test_check_render_refuses_what_only_a_browser_can_see(serve):
    """`version check --render` end to end, as the agent runs it: the static lint
    passes both versions, and only the one that renders clean may reach a user.
    The broken version is deliberately unpublished — refusing it before
    `version publish` exposes it is the gate's whole job, so the preview server
    has to expose what no user-facing server would."""
    serve(LONG_PAGE)
    d = serve.page_dir

    def gate(*args):
        return subprocess.run(
            [
                sys.executable,
                str(interact.__file__),
                "version",
                "check",
                str(d),
                "--render",
                *args,
            ],
            capture_output=True,
            text=True,
            check=False,  # both exit codes are the subject
        )

    ok = gate()
    assert ok.returncode == 0, ok.stderr
    assert "renders clean" in ok.stdout

    # A vw width slips the static lint (which counts only px) and overflows only
    # in a layout engine.
    (d / "versions" / "v2.html").write_text(
        LONG_PAGE.replace("</main>", "<div style='width:150vw'>wide</div>\n</main>")
    )
    broken = gate("--version", "2")
    assert broken.returncode == 1
    assert "scrolls sideways" in broken.stderr


@pytest.mark.nightly  # the shim's `--render` resolves a Playwright from the index
def test_an_installed_payload_passes_its_real_browser_gate(tmp_path):
    """Exercise the copied artifact a host installs, never an import from this checkout."""
    root = Path(__file__).parent.parent
    installed = tmp_path / "host" / "plugins" / "leaf"
    shutil.copytree(root / "plugins" / "leaf", installed)
    launcher = installed / "bin" / "leaf"
    elsewhere = tmp_path / "unrelated-project"
    elsewhere.mkdir()
    page_dir = tmp_path / "state" / "page"

    init = subprocess.run(
        [launcher, "page", "init", page_dir],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert init.returncode == 0, init.stderr
    (page_dir / "versions" / "v1.html").write_text(
        (root / "examples" / "release-notes.html").read_text()
    )
    shutil.copytree(EXAMPLE_MEDIA, page_dir / "media", dirs_exist_ok=True)
    publish = subprocess.run(
        [
            launcher,
            "version",
            "publish",
            page_dir,
            "--version",
            "1",
            "--text",
            "installed-payload smoke",
        ],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert publish.returncode == 0, publish.stderr

    rendered = subprocess.run(
        [launcher, "version", "check", page_dir, "--render"],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert rendered.returncode == 0, rendered.stderr
    assert "renders clean" in rendered.stdout


# A page that says one of its words on screen only. The rule is the page's own, which is
# the point: the gate asks what the printed page still says, not who took the words away.
PRINT_LOSS_PAGE = CARRIED_PAGE.replace(
    "</head>",
    "<style>@media print { #lede, #c-bearer { display: none } }</style></head>",
)


def test_render_reports_a_word_the_printed_page_loses(browser, serve):
    """A user prints the page, or saves it to PDF for someone who wasn't in the
    loop, and whatever the screen said had better still be there. Ways it isn't, all
    silent: a control that is a statement as well as a thing to press (the pick mark,
    which is the only place a group says which option it carries) and a rule that
    hides page content in print, inside a widget or in plain prose. The gate reads
    the page in both media and reports what the second one drops.

    A control declared an offer is exempt, since paper has nothing to press: the same
    page's pick mark reads "chosen" and goes unreported either way."""
    assert interact.render_version(browser, serve(CARRIED_PAGE)) == [], (
        "a page whose print rendering keeps its words has nothing to report"
    )

    lost = interact.render_version(browser, serve(PRINT_LOSS_PAGE))
    assert [f for f in lost if f.startswith("[print]")] == [
        (
            '[print] <p id=lede> drops "Where the decision stands, for the recor", '
            "which it says on screen"
        ),
        '[print] <lf-option id=c-bearer> drops "Bearer header", which it says on screen',
        (
            '[print] <lf-option id=c-bearer> drops "Suits the mobile client;\\n  '
            'puts the id w", which it says on screen'
        ),
    ], lost


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


def test_a_shot_shows_one_frame_and_flips_between_them(browser, serve):
    """The comparison lf-shot makes is a flip: two registered frames in one grid cell,
    one of them showing. What the gate covers on the way past is the rest of the
    widget's bargain — the captions naming each frame are the page's words and stay
    selectable, the radios are chrome and take no space in the user's reading, and
    a printed copy keeps both frames and both captions."""
    url = serve(SHOT_PAGE)
    for name, data in SHOTS.items():
        (serve.page_dir / "media").mkdir(exist_ok=True)
        (serve.page_dir / SHOT_SRC[name].lstrip("/")).write_bytes(data)
    assert interact.render_version(browser, url) == []

    page, errors = open_page(browser, url)
    assert shown_frames(page) == ["before"]
    page.get_by_role("radio", name="after").check()
    expect(page.locator('.lf-shotframe[data-lf-state="after"]')).to_be_visible()
    assert shown_frames(page) == ["after"]
    assert errors == []
    page.close()


def test_a_shot_still_flips_with_every_script_removed(browser, serve, tmp_path):
    """Which is the whole reason the control is a radio group. A copy is the rendered
    DOM with the scripts dropped and every press a handler answered taken out with
    them — the upgrade has already run, so the frames are there, and this switch
    survives that pass because the browser is what works it. A slider would have
    frozen at whatever the reader left it on; `:has(:checked)` is CSS, and the browser
    owns a radio's state.

    Through `version export` rather than a copy the test makes itself, which is what
    puts the widget's bargain in front of the code that could break it: a hand-rolled
    one dropped the script tags and nothing else, so it went on passing however the
    real export treated a control.

    The bug this pins was real: setting `checked` as a property left no attribute to
    serialize, so the copy opened with neither frame chosen and both of them stacked
    in the one cell."""
    url = serve(SHOT_PAGE)
    for name, data in SHOTS.items():
        (serve.page_dir / "media").mkdir(exist_ok=True)
        (serve.page_dir / SHOT_SRC[name].lstrip("/")).write_bytes(data)

    standalone = tmp_path / "standalone.html"
    standalone.write_text(interact.export_page(browser, url, serve.page_dir))
    loose = browser.new_page(viewport={"width": 1200, "height": 900})
    loose.goto(standalone.as_uri(), wait_until="load")
    assert loose.evaluate("document.querySelectorAll('script').length") == 0
    assert shown_frames(loose) == ["before"]
    loose.get_by_role("radio", name="after").check()
    assert shown_frames(loose) == ["after"]
    loose.close()


def test_a_shot_refuses_a_pair_shot_at_two_widths(browser, serve):
    """Both frames render at the frame's width, so a pair captured at two viewports is
    scaled by two different factors and every line in it lands somewhere new — the flip
    then reports that the whole page changed, convincingly and with nothing on screen
    to say otherwise. The one failure worth an error box rather than a caveat."""
    narrow = solid_png(400, 300, (235, 215, 205))
    page_html = SHOT_PAGE.replace(
        SHOT_SRC["after"], f"/media/{hashlib.sha256(narrow).hexdigest()[:16]}.png"
    )
    url = serve(page_html)
    (serve.page_dir / "media").mkdir(exist_ok=True)
    (serve.page_dir / SHOT_SRC["before"].lstrip("/")).write_bytes(SHOTS["before"])
    (
        serve.page_dir / "media" / f"{hashlib.sha256(narrow).hexdigest()[:16]}.png"
    ).write_bytes(narrow)

    assert [
        f
        for f in interact.render_version(browser, url)
        if "600px" in f and "400px" in f
    ], "the gate has to hear about a mismatch, since nobody else will"


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


def test_render_reports_words_a_widget_puts_out_of_reach(browser, serve):
    """The user's half of the gate. A user selected a draft's heading, tried to
    comment on it, and got nothing back — twice, months apart, on the same page. The
    heading was the page's word in a row its author had marked as the runtime's, and
    `.lf-ui` is a look rather than a permission, so the class alone can't be the answer:
    the declaration goes on the label (relabel), and an undeclared word under chrome is
    reported here.

    The second one no marker can fix, which is why it reads differently: a word inside a
    form control is unselectable in every engine, so a widget that reaches for <button>
    has put its label somewhere the user cannot go. `offer` builds a press as a span
    for exactly this reason, and this is what says so when a widget doesn't use it."""
    assert interact.render_version(browser, serve(CARRIED_PAGE)) == [], (
        "the same page without the two mistakes has nothing to report"
    )
    found = interact.render_version(browser, serve(OUT_OF_REACH_PAGE))
    assert sorted({f.split("] ", 1)[1] for f in found}) == [
        (
            '<lf-option id=c-lax> puts "Session cookies" under .lf-ui, where no comment '
            "can reach it"
        ),
        (
            '<lf-option id=c-lax> says "Lax, host-only" inside a form control, where no '
            "selection can reach it"
        ),
    ], found


UNPARSABLE_DIAGRAM = LONG_PAGE.replace(
    "</main>",
    "<lf-diagram id='d-broken'><pre>\nflowchart LR\n  A[Start --&gt; B{{{ ]]] broken\n</pre></lf-diagram>\n</main>",
)


@pytest.mark.nightly  # the shim's `--render` resolves a Playwright from the index
def test_the_shim_runs_the_gate_from_anywhere(serve, tmp_path):
    """`leaf` is what the skill hands an agent, so the shim's own resolution
    is load-bearing: it finds the script from its location rather than the cwd,
    and on `--render` it supplies the Playwright the PEP 723 header deliberately
    omits. Running it from an unrelated directory exercises both.

    The version under it carries a mermaid body that doesn't parse — a shape the
    static lint cannot reach, since it validates the element and never the
    notation inside it. The widget fails soft and the browser half is what sees
    the error box, which is why the gate is worth its couple of seconds."""
    serve(UNPARSABLE_DIAGRAM)
    d = serve.page_dir
    assert CliRunner().invoke(interact.cli, ["version", "check", str(d)]).exit_code == 0

    shim = Path(__file__).parent.parent / "plugins" / "leaf" / "bin" / "leaf"
    run = subprocess.run(
        [str(shim), "version", "check", str(d), "--render"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 1, run.stdout + run.stderr
    # "needs Playwright" here would mean the shim dispatched the plain `uv run`.
    assert "failed soft" in run.stderr and "Parse error" in run.stderr


def test_page_and_panel_scroll_in_separate_regions(browser, serve):
    """The document scrolls its own column, not the viewport. If it scrolled the
    viewport, its scrollbar would be drawn at the window's right edge — over the
    panel, in the same pixels as the thread list's own — and the two thumbs would
    stack. The regions must not share an edge."""
    page, _ = open_page(browser, serve(LONG_PAGE, comments=12))
    page.get_by_role("button", name="Comments", exact=False).click()
    panel_settled(page)

    geom = page.evaluate("""() => {
        const box = el => el.getBoundingClientRect();
        const body = document.body, threads = document.querySelector('.lf-threads');
        return { viewportScrolls: document.documentElement.scrollHeight > document.documentElement.clientHeight,
                 bodyScrolls: body.scrollHeight > body.clientHeight,
                 threadsScroll: threads.scrollHeight > threads.clientHeight,
                 bodyRight: box(body).right, threadsLeft: box(threads).left };
    }""")

    assert not geom["viewportScrolls"], (
        "the viewport is scrolling the document, so its scrollbar is drawn at the "
        "window's right edge — on top of the panel"
    )
    assert geom["bodyScrolls"] and geom["threadsScroll"], (
        "both regions must overflow for this test to mean anything"
    )
    assert geom["bodyRight"] <= geom["threadsLeft"], (
        f"scroll regions overlap: the page ends at {geom['bodyRight']}px, "
        f"the thread list starts at {geom['threadsLeft']}px"
    )
    page.close()


def test_covering_panel_takes_the_page_scroll_with_it(browser, serve):
    """Under 720px the panel covers the page instead of squeezing it, and the
    covered page gives up scrolling with its width: a wheel moves the sheet's
    thread list and never the page behind it. The page still follows navigation —
    a quote click positions it behind the sheet — and closing hands scrolling
    back right there. The resize path reaches the same states, since the layout's
    one writer runs from resize too."""
    page, _ = open_page(
        browser, serve(LONG_PAGE, comments=12, anchored=[("p40", "Paragraph 40.")])
    )
    resized(page, 500, 600)

    # A reading position first, so surviving the sheet is observable.
    page.mouse.move(120, 300)
    page.mouse.wheel(0, 600)
    page.wait_for_function("() => document.body.scrollTop > 0")
    before = page.evaluate("() => document.body.scrollTop")

    page.locator(".lf-comments").click()
    panel_settled(page)

    # One wheel over the page's visible sliver, one over the sheet. Waiting on the
    # second proves both were processed — input stays in order — so the first
    # having moved nothing is a real outcome rather than a race.
    page.mouse.move(60, 300)
    page.mouse.wheel(0, 400)
    page.mouse.move(400, 300)
    page.mouse.wheel(0, 400)
    page.wait_for_function("() => document.querySelector('.lf-threads').scrollTop > 0")
    assert page.evaluate("() => document.body.scrollTop") == before, (
        "the page scrolled behind the covering sheet"
    )

    # Navigation still positions the page: a quote click scrolls its passage into
    # view under the lock, so the sheet closes onto the passage it talked about.
    page.locator(".lf-quote", has_text="Paragraph 40").click()
    # Arrived where it was aimed, which is the only thing about this the page states. The
    # click scrolls twice — instantly, to bring the passage's own box into view, then
    # smoothly to centre the painted range — and the browser fires a scrollend for each,
    # so the first statement it makes comes 232px short of the rest position. "On screen"
    # is true there too, and so is stillness sampled between the two, which reads exactly
    # as it does after both (tests/CLAUDE.md, "A wait consumes a fact the system states");
    # the hold that used to cover the gap was a duration guessed at. Centring is what the
    # runtime aimed for, so the mark reaching the middle is arrival, and a glide that
    # approaches it passes through no earlier position that could be taken for one.
    page.wait_for_function(
        """() => { const m = [...CSS.highlights.get('lf-mark')][0].getClientRects()[0];
                   return Math.abs(m.top + m.height / 2 - innerHeight / 2) < 1; }"""
    )
    at_mark = page.evaluate("() => document.body.scrollTop")
    assert at_mark != before
    mark_top = page.evaluate(
        "() => document.getElementById('p40').getBoundingClientRect().top"
    )

    # Closing hands scrolling back, right where navigation left the page — measured on
    # the passage, not the number: unlocking returns the scrollbar, whose width reflows
    # the text where scrollbars are classic, and Chrome's scroll anchoring then nudges
    # scrollTop a pixel to keep the visible content put. The passage staying put is the
    # promise; the number is one rendering of it.
    page.get_by_role("button", name="Close comments").click()
    panel_settled(page, open=False)
    page.wait_for_function(
        """(top) => Math.abs(document.getElementById('p40').getBoundingClientRect().top - top) < 2""",
        arg=mark_top,
    )
    page.mouse.move(120, 300)
    page.mouse.wheel(0, 200)
    page.wait_for_function(f"() => document.body.scrollTop > {at_mark}")

    # The resize path: narrowing onto an open panel locks, widening unlocks.
    page.locator(".lf-comments").click()
    panel_settled(page)
    resized(page, 1000, 600)
    page.wait_for_function(
        "() => getComputedStyle(document.body).overflowY !== 'hidden' && document.body.style.marginRight !== ''"
    )
    resized(page, 500, 600)
    page.wait_for_function(
        "() => getComputedStyle(document.body).overflowY === 'hidden' && document.body.style.marginRight === ''"
    )
    page.close()


def test_covering_panel_keeps_toasts_on_screen_and_clear_of_the_footer(browser, serve):
    """A covering panel has no beside-panel space for a toast: on a viewport no
    wider than the sheet, the wide layout's panel-width offset puts the whole
    message past the left edge. The toast stays inside that sheet instead, above
    its persistent composer even when that composer grows under a live toast,
    then returns beside it at the first width where the panel stops covering."""
    page, _ = open_page(browser, serve(LONG_PAGE))
    resized(page, 320, 600)
    page.locator(".lf-comments").click()
    page.locator(".lf-general textarea").fill("The unsent comment stays here.")

    message = (
        "Couldn't send this detailed comment to Claude — the complete draft "
        "is still here and ready to retry."
    )
    page.evaluate(
        """async message => {
            const {toast} = await import("/leaf.js");
            toast(message);
        }""",
        message,
    )
    expect(page.locator(".lf-toast")).to_have_text(message)

    def geometry():
        return page.evaluate("""() => {
            const rect = selector => {
                const r = document.querySelector(selector).getBoundingClientRect();
                return {left: r.left, top: r.top, right: r.right, bottom: r.bottom};
            };
            return {
                width: innerWidth,
                height: innerHeight,
                panel: rect(".lf-panel"),
                footer: rect(".lf-general"),
                toast: rect(".lf-toast"),
            };
        }""")

    narrow = geometry()
    assert (
        narrow["toast"]["left"] >= 17
        and narrow["toast"]["right"] <= narrow["width"] - 17
    ), f"the toast left the covering viewport: {narrow}"
    assert narrow["toast"]["bottom"] <= narrow["footer"]["top"] - 17, (
        f"the toast covered the panel's persistent composer: {narrow}"
    )

    resized(page, 841, 600)
    page.wait_for_function("""() => {
        const toast = document.querySelector(".lf-toast").getBoundingClientRect();
        const panel = document.querySelector(".lf-panel").getBoundingClientRect();
        return Math.abs(toast.right - (panel.left - 18)) < 1
            && Math.abs(toast.bottom - (innerHeight - 18)) < 1;
    }""")

    wide = geometry()
    assert wide["toast"]["left"] >= 0, (
        f"the long toast left the viewport beside the wide panel: {wide}"
    )
    assert abs(wide["toast"]["right"] - (wide["panel"]["left"] - 18)) < 1, (
        f"the wide toast no longer sits beside the panel: {wide}"
    )
    assert abs(wide["toast"]["bottom"] - (wide["height"] - 18)) < 1, (
        f"the wide toast no longer sits in its original bottom corner: {wide}"
    )

    resized(page, 320, 600)
    page.wait_for_function("""() => {
        const toast = document.querySelector(".lf-toast").getBoundingClientRect();
        const footer = document.querySelector(".lf-general").getBoundingClientRect();
        return toast.left >= 17 && toast.right <= innerWidth - 17
            && toast.bottom <= footer.top - 17;
    }""")
    before_growth = geometry()
    page.locator(".lf-general textarea").fill(
        "The whole unsent comment stays here.\n" * 4
    )
    page.wait_for_function(
        """beforeTop => {
            const toast = document.querySelector(".lf-toast").getBoundingClientRect();
            const footer = document.querySelector(".lf-general").getBoundingClientRect();
            return footer.top < beforeTop - 1
                && toast.bottom <= footer.top - 17;
        }""",
        arg=before_growth["footer"]["top"],
    )
    expanded = geometry()
    assert expanded["footer"]["top"] < before_growth["footer"]["top"] - 1, (
        f"the composer did not grow under the already-visible toast: "
        f"{before_growth=}, {expanded=}"
    )
    assert expanded["toast"]["bottom"] <= expanded["footer"]["top"] - 17, (
        f"the growing composer rose through an already-visible toast: {expanded}"
    )
    page.close()


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


def test_a_sent_comment_is_revealed_in_the_panel(browser, serve):
    """A send is the one gesture that produces a thread, so it gets the same answer a
    click on a page mark does: the panel scrolls the new thread into its scrollport.
    On a list long enough to scroll, the old rebuild appended the comment below the
    fold and put the scroll back where it was — the user's own words landed out of
    sight, silently. Both send routes then end in the composer the words left, where
    the rebuild sent a button click's focus somewhere else than ⌘⏎'s."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=12))
    page.locator(".lf-comments").click()
    panel_settled(page)
    assert page.evaluate(
        "() => { const t = document.querySelector('.lf-threads');"
        "        return t.scrollTop === 0 && t.scrollHeight > t.clientHeight; }"
    ), "this list starts revealed or doesn't scroll, so it proves nothing"

    box = page.locator(".lf-general textarea")
    box.fill("Where did my words go?")
    page.locator(".lf-general button").click()  # the route that used to drop focus
    round_trip(page)
    sent = interact.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["text"]) == ("comment", "Where did my words go?")
    in_threads_scrollport(page, f'.lf-thread[data-id="{sent["id"]}"]')
    assert page.evaluate("() => document.querySelector('.lf-threads').scrollTop") > 0, (
        "the new thread was in view without scrolling, so the reveal proved nothing"
    )
    expect(box).to_be_focused()
    expect(box).to_have_value("")

    box.fill("And the second thought lands the same way.")
    page.keyboard.press("ControlOrMeta+Enter")  # the other route, same destination
    round_trip(page)
    second = interact.read_events(serve.page_dir)[-1]
    in_threads_scrollport(page, f'.lf-thread[data-id="{second["id"]}"]')
    expect(box).to_be_focused()
    assert errors == []
    page.close()


def test_an_arriving_reply_leaves_the_list_where_the_reader_put_it(browser, serve):
    """News has no gesture behind it, so it may move nothing the reader is looking at.
    The hard case is a reply landing in a thread above the fold: the list grows over
    the reader's head, and what must hold still is the thread in front of them — their
    place as a box on screen, not as a scrollTop the browser's own scroll anchoring is
    free to adjust. The old rebuild restored the offset and let the content slide under
    it."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=12))
    page.locator(".lf-comments").click()
    panel_settled(page)
    held = page.evaluate("""() => {
        const box = document.querySelector('.lf-threads');
        box.scrollTop = 400;
        const b = box.getBoundingClientRect();
        window.__held = [...box.querySelectorAll(':scope > .lf-thread')]
            .find(n => n.getBoundingClientRect().top >= b.top);
        return { top: window.__held.getBoundingClientRect().top,
                 scrolled: box.scrollTop > 0 };
    }""")
    assert held["scrolled"], "the list doesn't scroll, so nothing here can move"

    first = next(
        e for e in interact.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    reply = interact.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Claude",
            "version": 1,
            "parent": first["id"],
            "text": "News, not a gesture.",
        },
    )
    told(page)
    expect(page.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_have_count(1)
    after = page.evaluate(
        "() => ({ connected: window.__held.isConnected,"
        "          top: window.__held.getBoundingClientRect().top })"
    )
    assert after["connected"], "the held thread was replaced, so its box says nothing"
    assert abs(after["top"] - held["top"]) < 1, (
        f"the arriving reply moved the thread the reader was on: {held} -> {after}"
    )
    assert errors == []
    page.close()


def test_an_arrival_interrupts_nothing_the_user_holds(browser, serve):
    """The nodes themselves survive the poll: the thread being typed in is the same
    element afterwards, still focused, caret where the typing left it — even when the
    arrival lands inside that very thread, right above the reply box. The rebuild
    could only approximate this by saving and restoring focus and caret by hand, and
    the two send routes proved the restore had holes."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=3))
    page.locator(".lf-comments").click()
    panel_settled(page)
    ta = page.locator(".lf-threads > .lf-thread").first.locator("textarea")
    ta.click()
    ta.type("half a thought")
    page.evaluate("""() => {
        document.activeElement.setSelectionRange(4, 4);
        window.__probe = document.activeElement.closest('.lf-thread');
    }""")

    first = next(
        e for e in interact.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    reply = interact.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Claude",
            "version": 1,
            "parent": first["id"],
            "text": "Landing right above the box being typed in.",
        },
    )
    told(page)
    expect(page.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_have_count(1)
    assert page.evaluate("""() => {
        const ta = document.activeElement;
        return ta.tagName === 'TEXTAREA'
            && ta.closest('.lf-thread') === window.__probe
            && window.__probe === document.querySelector('.lf-threads > .lf-thread')
            && ta.value === 'half a thought'
            && ta.selectionStart === 4 && ta.selectionEnd === 4;
    }"""), "the poll replaced or disturbed the node the user was typing into"
    assert errors == []
    page.close()


def test_resolving_an_early_thread_renumbers_the_rest_in_place(browser, serve):
    """A thread can move, not just appear: resolving the first one sends it to the
    resolved disclosure and renumbers every thread after it — the reply box's armed
    chip and its placeholder address together, on nodes that are kept rather than
    remade. The
    disclosure itself is kept too, so the user's open toggle survives the next
    resolution instead of snapping shut on every arrival, which is what the rebuild
    did."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=3))
    page.locator(".lf-comments").click()
    panel_settled(page)
    c1, c2, c3 = [
        e["id"] for e in interact.read_events(serve.page_dir) if e["kind"] == "comment"
    ]
    expect(
        page.locator(f'.lf-thread[data-id="{c2}"] .lf-compose > .lf-address')
    ).to_have_text("2")
    page.evaluate(
        """(id) => { window.__second = document.querySelector(`.lf-thread[data-id="${id}"]`); }""",
        c2,
    )

    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    round_trip(page)
    # The resolved node took the pressed button with it; focus lands on the thread
    # that now holds its place rather than falling to body.
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    expect(page.locator(f'.lf-details .lf-thread[data-id="{c1}"]')).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{c1}"] textarea')).to_have_count(0)
    expect(page.locator(".lf-comments")).to_have_text("Comments (2)")
    # The survivors renumber without being remade: same node, new address, and the
    # address its placeholder speaks moved with the badge.
    expect(
        page.locator(f'.lf-thread[data-id="{c2}"] .lf-compose > .lf-address')
    ).to_have_text("1")
    expect(page.locator(f'.lf-thread[data-id="{c2}"] textarea')).to_have_attribute(
        "placeholder", "Reply · g 1"
    )
    assert page.evaluate(
        """(id) => window.__second === document.querySelector(`.lf-thread[data-id="${id}"]`)""",
        c2,
    ), "renumbering rebuilt the surviving thread"

    page.locator(".lf-details summary").click()
    expect(page.locator(".lf-details[open]")).to_have_count(1)
    # A thread leaving mid-list puts every survivor one place forward. Standing still
    # there is the reconcile's own duty, not the browser's: a survivor reinserted at
    # its new place is the same element and passes any identity probe, but reinsertion
    # drops the caret typing in it.
    ta3 = page.locator(f'.lf-thread[data-id="{c3}"] textarea')
    ta3.click()
    ta3.type("held mid-sentence")
    page.evaluate("() => document.activeElement.setSelectionRange(4, 4)")
    interact.append_event(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": c2}
    )
    told(page)
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (2)")
    expect(page.locator(".lf-details[open]")).to_have_count(1)
    expect(ta3).to_be_focused()
    assert page.evaluate(
        "() => document.activeElement.value === 'held mid-sentence'"
        "   && document.activeElement.selectionStart === 4"
    ), "the thread after the one that resolved was reinserted under the typing"
    assert errors == []
    page.close()


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


def test_a_resolved_thread_gives_its_room_back_as_motion(browser, serve):
    """Resolving a thread empties its place in the list over a fifth of a second,
    not in the frame of the press.

    The node used to go the moment the log settled it: the ✓ Resolve the user had
    just pressed took itself off the page, and every thread under it arrived
    somewhere else with no path between the two — the same pair of failures the
    suggestion's decided slot was already fixed for, in the panel this time. So the
    thread stays where it stood, states on the pressed control what was done to it,
    and folds; the disclosure gets it when the fold is over.

    What the log says is true from that first frame regardless — Comments counts down
    and Resolved counts up while the pixels catch up — and a thread on its way out is
    out of the keys' reach from the same frame, so j/k and the g addresses walk what
    is left rather than a corpse that is about to go. Its own reply box gives up the
    address with them: the box under it has just taken that digit, and two boxes
    offering g 1 is a key line promising a press that lands on one of them.

    Held at its first frame rather than sampled mid-flight, the way the suggestion's
    own fold is read: mid-flight is a race with the clock that passes on a fast
    machine whatever the code does, where the held frame is the fold's opening state
    for as long as the assertions need it."""
    page, errors = open_page(
        browser, serve(LONG_PAGE, comments=3), init_script=HOLD_MOTION
    )
    page.locator(".lf-comments").click()
    panel_settled(page)
    c1, c2, c3 = [
        e["id"] for e in interact.read_events(serve.page_dir) if e["kind"] == "comment"
    ]
    first = page.locator(f'.lf-thread[data-id="{c1}"]').bounding_box()
    stood = page.locator(f'.lf-thread[data-id="{c2}"]').bounding_box()
    # The room the first thread holds, the gap under it included, which is what its
    # neighbour rises by once the fold has given it back.
    room = stood["y"] - first["y"]

    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    round_trip(page)
    expect(page.locator(f'[data-id="{c1}"] .lf-resolve')).to_have_text("✓ Resolved")
    held = page.evaluate(LIST_STATE)
    assert held["standing"] == [c1, c2, c3], (
        "the resolved thread gave up its place in the frame it was resolved in, so "
        f"the list stood as {held['standing']} with the fold still to play"
    )
    assert held["walkable"] == [c2, c3], (
        "a thread on its way out is still walkable by j/k and addressable by g, so a "
        f"key can land on room that is about to go: the list offered {held['walkable']}"
    )
    assert page.evaluate("() => window.__lfHeld.length") == 1, (
        "the room went back without motion carrying it"
    )
    now = page.locator(f'.lf-thread[data-id="{c2}"]').bounding_box()
    assert now == stood, (
        f"the thread below stood at {stood} and reads {now} in the frame the outcome "
        "was stated, so the fold started from somewhere other than the box the reader "
        "was looking at"
    )
    expect(page.locator(".lf-comments")).to_have_text("Comments (2)")
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    # The address the fold gave up, read where a reader reads it.
    expect(page.locator(f'[data-id="{c1}"] textarea')).to_have_attribute(
        "placeholder", "Reply"
    )
    expect(page.locator(f'.lf-thread[data-id="{c2}"] textarea')).to_have_attribute(
        "placeholder", "Reply · g 1"
    )

    # Half way down, the outcome is still on screen. A fold from the bottom takes the
    # thread's last line first, and the actions row is that line, so a word left in
    # flow is legible for the frame before the box swallows it and no longer — which
    # is a flash, not a statement. It rides the closing edge instead, and what says so
    # is its box being inside the box the fold has left.
    page.evaluate("() => window.__lfHeld.forEach((m) => (m.currentTime = 110))")
    clip, says = page.evaluate(
        """(id) => {
          const going = document.querySelector(`[data-id="${id}"]`);
          const row = going.querySelector(".lf-thread-actions");
          return [going.getBoundingClientRect(), row.getBoundingClientRect()];
        }""",
        c1,
    )
    assert says["top"] < clip["bottom"] and clip["top"] < says["bottom"], (
        f"the outcome sat at {says['top']:.0f}–{says['bottom']:.0f} with the fold "
        f"clipped to {clip['top']:.0f}–{clip['bottom']:.0f}, so the word the press "
        "left was already under the clip half way through"
    )

    # And the far end: the thread lands in the disclosure, once, and the room it held
    # has gone back to the threads under it.
    page.evaluate("() => window.__lfHeld.forEach((m) => m.finish())")
    expect(page.locator(f'.lf-details .lf-thread[data-id="{c1}"]')).to_have_count(1)
    expect(page.locator(f'[data-id="{c1}"]')).to_have_count(1)
    risen = page.locator(f'.lf-thread[data-id="{c2}"]').bounding_box()
    assert stood["y"] - risen["y"] == pytest.approx(room, abs=1), (
        f"the thread below rose {stood['y'] - risen['y']:.1f}px where the resolved "
        f"thread held {room:.1f}px"
    )
    assert errors == []
    page.close()


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


def test_the_fold_never_paints_a_frame_that_undoes_the_last(browser, serve):
    """A fold is a sequence, and every other check here reads a state.

    The gap that leaves is a frame that puts back what the frames before it took:
    a Web Animations effect stops applying at the end of its own interval, so
    anything holding the collapsed box open — a removal that slips a frame past
    the finish, a fill the helper stopped stating — paints the whole thread back
    at full height and full opacity for a frame before it goes. Held frames can't
    see it; each one is correct on its own. This watches the real fold at real
    speed and asks the only question a sequence can be wrong about, which is
    whether any frame is taller than the one before it.

    It is also what the first recording of this fold got wrong, in the other
    direction: sampled at exactly the duration, an animation is already past its
    own interval and reads as the element it never was."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=3))
    page.locator(".lf-comments").click()
    panel_settled(page)
    c1 = next(
        e["id"] for e in interact.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    # Watching from before the press, so the frames it holds still are in the record
    # alongside the ones that move.
    page.evaluate(FRAME_BY_FRAME, f'.lf-threads > [data-id="{c1}"]')
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    # The node leaving the list is the fold's end and the browser's own statement, so
    # the wait is that rather than the sampler's flag: what runs in the page is the
    # record, which nothing out here can take, and not the wait, which is already
    # answered from outside.
    page.wait_for_selector(f'.lf-threads > [data-id="{c1}"]', state="detached")
    seen = page.evaluate("() => window.__seen")

    grew = [
        (i, seen[i - 1], seen[i]) for i in range(1, len(seen)) if seen[i] > seen[i - 1]
    ]
    assert not grew, (
        "the fold painted a frame taller than the one before it: "
        + ", ".join(f"frame {i} went {was:.0f}px → {now:.0f}px" for i, was, now in grew)
    )
    # And it folded rather than vanishing between two samples, which would pass the
    # line above by having nothing to compare.
    assert any(0 < h < seen[0] for h in seen), (
        f"no frame caught the fold part way down (heights: {seen}), so a thread that "
        "went in one frame would read the same as one that folded"
    )
    assert errors == []
    page.close()


def test_a_reader_who_asked_for_less_motion_gets_the_resolved_thread_at_once(
    browser, serve
):
    """The fold is a courtesy to the eye, and an eye that asked for stillness is owed
    the outcome instead — the bargain the suggestion's own fold already makes, asked
    again here because the thread's is the path with somewhere to be left stranded:
    the node stays in the list until its fold ends, so a fold that never starts is a
    node that has to reach the disclosure by the same render that declined to play
    one."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        color_scheme="light",
        reduced_motion="reduce",
    )
    try:
        page, errors = open_page(
            browser,
            serve(LONG_PAGE, comments=2),
            context=context,
            init_script=HOLD_MOTION,
        )
        page.locator(".lf-comments").click()
        panel_settled(page)
        c1, c2 = [
            e["id"]
            for e in interact.read_events(serve.page_dir)
            if e["kind"] == "comment"
        ]
        page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
        expect(page.locator(f'.lf-details .lf-thread[data-id="{c1}"]')).to_have_count(1)
        assert page.evaluate("() => window.__lfHeld.length") == 0, (
            "a reader who asked for less motion was given a fold to sit through"
        )
        assert page.evaluate(LIST_STATE) == {"standing": [c2], "walkable": [c2]}, (
            "the thread that declined its fold was left standing in the list"
        )
        assert errors == []
    finally:
        context.close()


def test_a_coined_class_cannot_reach_the_chromes_rules(browser, serve):
    """The chrome's private rules live in one @scope block rooted at the runtime's
    own container, so whatever name a widget or a page coins, it matches none of
    them: lf-tabs once marked itself lf-live — the chrome's name for its
    visually-hidden live region — and every tabbed page clipped to a pixel. An
    element in the page wearing every scoped class at once must render exactly as
    its unclassed twin, and the classes styled at document level must be exactly
    the shared vocabulary a widget wears on purpose."""
    page, _ = open_page(
        browser,
        serve(
            '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>t</title>'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; '
            "img-src 'self' data:; style-src 'self' 'unsafe-inline'\">"
            '<link rel="stylesheet" href="/theme.css">'
            '<script type="module" src="/leaf.js"></script></head>'
            "<body><main><h1>t</h1><section id=s><p>words</p></section></main></body></html>"
        ),
    )
    surface = page.evaluate("""() => {
        const sheet = [...document.styleSheets].find(
            s => { try { return [...s.cssRules].some(r => r instanceof CSSScopeRule); }
                   catch { return false; } });
        const classes = sel => [...(sel || "").matchAll(/\\.([A-Za-z0-9_-]+)/g)].map(m => m[1]);
        const scoped = new Set(), global_ = new Set();
        const collect = (rules, into) => { for (const r of rules) {
            if (r instanceof CSSScopeRule) collect(r.cssRules, scoped);
            else if (r.selectorText) classes(r.selectorText).forEach(c => into.add(c));
            else if (r.cssRules) collect(r.cssRules, into); } };
        collect(sheet.cssRules, global_);
        const probe = document.createElement("div"), plain = document.createElement("div");
        // Minus the shared vocabulary: a word document level dresses on purpose
        // (lf-address, worn on a reply box and on an option's corner alike) is named
        // by the scoped rule that says when to paint it, and it would answer this
        // question with the reach it was given rather than with a leak.
        probe.className = [...scoped].filter(c => !global_.has(c)).join(" ");
        probe.textContent = plain.textContent = "probe";
        document.getElementById("s").append(plain, probe);
        const cs = el => { const c = getComputedStyle(el), out = {};
                           for (const p of c) out[p] = c.getPropertyValue(p); return out; };
        const a = cs(probe), b = cs(plain);
        return { scoped: [...scoped], global: [...global_],
                 moved: Object.keys(a).filter(p => a[p] !== b[p]) };
    }""")
    assert "lf-live" in surface["scoped"] and len(surface["scoped"]) > 20, (
        "the @scope block is missing or nearly empty — the chrome has lost its rules"
    )
    assert surface["moved"] == [], (
        f"scoped chrome rules reached an element in the page: {surface['moved']}"
    )
    # Every one of these is worn by something the runtime puts inside the page rather than
    # inside its own container, which is exactly why a scoped rule could not reach it —
    # except the last, which is worn by nothing and is here for the other half of the
    # sentence. lf-copy is the medium `version export` marks on the root, and the runtime
    # names it under a negation to withhold the live page's scroller from a file that has
    # no panel to scroll beside; a rule that dresses no element can leak onto none, and
    # what the pin is for is the day one of these stops being either kind.
    assert {c for c in surface["global"] if c.startswith("lf-")} == {
        "lf-copy",
        "lf-ui",
        "lf-btn",
        "lf-pill",
        "lf-address",
        "lf-over-mark",
        "lf-mark-el",
        "lf-pending",
        "lf-ins-block",
        "lf-mark-note",
        "lf-aiming",
        "lf-over-item",
        "lf-quiet",
    }, (
        "the document-level class surface changed: widen the shared vocabulary on purpose"
    )
    page.close()


def test_the_runtime_does_not_replace_a_pages_keyframes(browser, serve):
    """Keyframe names ignore @scope, so the runtime's private animation must be
    globally unique enough to leave a page's own animation alone. The page coins the
    old generic name on purpose; sampling its midpoint makes a collision deterministic
    rather than asking where a running animation happened to be when the test looked."""
    page, errors = open_page(
        browser,
        serve(
            '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>t</title>'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; '
            "img-src 'self' data:; style-src 'self' 'unsafe-inline'\">"
            '<link rel="stylesheet" href="/theme.css"><style>'
            "@keyframes lf-pulse { from { transform: translateX(0px); } "
            "to { transform: translateX(40px); } }"
            "#page-pulse { animation: lf-pulse 10s linear infinite; }"
            '</style><script type="module" src="/leaf.js"></script></head>'
            '<body><main><h1>t</h1><p id="page-pulse">Page-owned motion.</p></main></body></html>'
        ),
    )
    sampled = page.evaluate("""() => {
        const pageAnimation = document.getElementById("page-pulse").getAnimations()[0];
        pageAnimation.pause();
        pageAnimation.currentTime = pageAnimation.effect.getTiming().duration / 2;
        const transform = getComputedStyle(document.getElementById("page-pulse")).transform;

        const dot = document.querySelector(".lf-dot");
        dot.classList.add("working");
        const runtimeAnimation = dot.getAnimations()[0];
        return {
            pageDistance: transform === "none" ? null : new DOMMatrix(transform).m41,
            runtimeName: runtimeAnimation?.animationName ?? null,
        };
    }""")
    assert sampled["pageDistance"] == pytest.approx(20), (
        f"the runtime replaced the page's lf-pulse keyframes: {sampled}"
    )
    assert sampled["runtimeName"] and sampled["runtimeName"] != "lf-pulse", (
        f"the chrome lost its own private pulse animation: {sampled}"
    )
    assert errors == []
    page.close()


STACKED_OPTIONS_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>stacked options</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_substantial_options_stack_and_align_their_facts(browser, serve):
    """A titled option is a full-width card and the cards stack, terse or
    substantial alike. The grid this replaced laid terse options across at
    ~13rem, and its geometry moved with the count — a fourth option orphaned
    under the first row, every cell as tall as the row's longest argument —
    where a page whose options held real argument grew a comparison table and
    an "in detail" section outside the widget it decides in. Stacked, the
    comparison stays inside the group: every option's `.facts` list docks right
    at one fixed width, so scalars align down the page like that table's column.

    The chip band is the one part no form places, and the reason is that its words
    are the author's: an attribute pair the theme knew the names of could be
    pinned to two corners and reserved room for, and `chips` can be any length at
    all. So it goes in flow ahead of the title, where a card gives it the width it
    has and it wraps inside that rather than over the card's edge."""
    page, errors = open_page(browser, serve(STACKED_OPTIONS_PAGE))
    assert errors == []

    sd = page.locator("#st-sd").bounding_box()
    pi = page.locator("#st-pi").bounding_box()
    group = page.locator("#stacked").bounding_box()
    assert sd["y"] + sd["height"] <= pi["y"], "substantial options must stack"
    assert sd["width"] > group["width"] * 0.95, (
        "a stacked option takes the whole column"
    )

    rails = [
        page.locator(f"#{i} > dl.facts").bounding_box() for i in ("st-sd", "st-pi")
    ]
    for rail, card in zip(rails, (sd, pi)):
        assert rail["x"] > card["x"] + card["width"] / 2, "the facts rail docks right"
    assert abs(rails[0]["x"] - rails[1]["x"]) < 1, "rails align down the group"

    title = page.locator("#st-sd > strong").bounding_box()
    chips = page.locator("#st-sd > lf-chip")
    expect(chips).to_have_text(["effort: low", "risk: high"])
    # `tone` is the author's judgement about one answer, so it lands on the chip that
    # declares it and nowhere else — the arrangement this replaced tinted whichever chip
    # happened to be called risk, which is the theme holding an opinion about a word.
    tints = chips.evaluate_all(
        "els => els.map(el => getComputedStyle(el).backgroundColor)"
    )
    wanted = page.evaluate(
        """() => ['--chip', '--danger-tint'].map(name => {
            const probe = document.createElement('div');
            probe.style.backgroundColor = `var(${name})`;
            document.body.append(probe);
            const paint = getComputedStyle(probe).backgroundColor;
            probe.remove();
            return paint;
        })"""
    )
    assert tints == wanted, (
        f"an untoned chip is neutral and a toned one takes the theme's own tint: "
        f"{tints} vs {wanted}"
    )
    band = [chips.nth(i).bounding_box() for i in range(2)]
    for chip in band:
        assert chip["y"] + chip["height"] <= title["y"] + 1, (
            "the chips read before the title"
        )
    assert abs(band[0]["x"] - title["x"]) < 1, "and start where the title does"
    assert band[0]["x"] + band[0]["width"] <= band[1]["x"], (
        "in the author's order, not overlapping"
    )

    paper = page.locator("#t-paper").bounding_box()
    gps = page.locator("#t-gps").bounding_box()
    terse = page.locator("#terse").bounding_box()
    assert paper["y"] + paper["height"] <= gps["y"], "terse options stack too"
    assert gps["width"] > terse["width"] * 0.95, "a terse card takes the whole column"

    # lf-compare is the same shape without the decision, and follows it for block
    # content; an exhibition is looked across, so its terse form keeps the grid —
    # the one side-by-side layout left, asserted here or nowhere.
    cedar = page.locator("#cv-cedar").bounding_box()
    pine = page.locator("#cv-pine").bounding_box()
    assert cedar["y"] + cedar["height"] <= pine["y"], "substantial variants stack too"
    rail = page.locator("#cv-cedar > dl.facts").bounding_box()
    assert rail["x"] > cedar["x"] + cedar["width"] / 2, "a variant's facts dock right"
    oiled = page.locator("#cv-oiled").bounding_box()
    bare = page.locator("#cv-bare").bounding_box()
    assert abs(oiled["y"] - bare["y"]) < 1, "terse variants keep the side-by-side grid"
    assert oiled["x"] + oiled["width"] <= bare["x"], "terse variants share the row"

    # More chips than fit on a line wrap along the band rather than over the card's edge.
    # The pair this replaced could not: each was an absolutely-positioned box sized to
    # room the theme had reserved by knowing both words in advance. A full-width card
    # outgrows the band at the desktop column, so the narrow window is where the wrap
    # is still reachable. Last, because the width moves every box read above.
    page.set_viewport_size({"width": 400, "height": 900})
    gps = page.locator("#t-gps").bounding_box()
    long_chips = page.locator("#t-gps > lf-chip")
    expect(long_chips).to_have_count(3)
    wrapped = [long_chips.nth(i).bounding_box() for i in range(3)]
    assert wrapped[-1]["y"] > wrapped[0]["y"], (
        "a band too wide for its card takes a second line"
    )
    for chip in wrapped:
        assert chip["x"] + chip["width"] <= gps["x"] + gps["width"], (
            "no chip the author wrote may cross the card's edge"
        )
    page.close()


def test_a_row_too_narrow_to_dock_a_rail_stacks_it_instead(browser, serve):
    """The rail is a comparison column, and it is worth its 10rem only while what it
    stands beside is still an argument. Out of a row narrower than about 30rem it is not:
    the case gets three or four words to the line and the row reads as a rail with some
    text jammed down its left. So the row is asked, and not the window — how much width a
    row has is a fact about the row, and a page gives 168px up to the margin the
    moment it carries a change to decide, which no viewport query knows about."""
    page = browser.new_page(
        viewport={"width": 460, "height": 900}, color_scheme="light"
    )
    page.goto(serve(STACKED_OPTIONS_PAGE), wait_until="networkidle")
    rail = page.locator("#st-sd > dl.facts").bounding_box()
    prose = page.locator("#st-sd > p").bounding_box()
    card = page.locator("#st-sd").bounding_box()
    assert rail["width"] > card["width"] * 0.8, (
        "the rail still docks in a row this narrow"
    )
    assert rail["y"] + rail["height"] <= prose["y"], "the case has to clear the rail"
    page.close()


def test_settled_options_collapse_without_going_out_of_reach(browser, serve):
    """A settled decision reads as one line and the cards behind it stop spending
    the page's height — but they are hidden, not gone, so everything that used to
    reach them still does: the disclosure opens them, and a comment anchored in
    one opens the group on its way to the passage. A collapse a comment can't see
    through is worse than no collapse at all, because the thread still lists the
    quote and clicking it lands nowhere.

    The line itself is in reach too, which is the harder half: while the group is
    collapsed it is the only place the decision is stated, and it is written into a
    disclosure — chrome, and a control. And naming the card there means the page now
    says the card's lede twice, so the third part asks the one thing that buys: a
    comment made on the card lands on the card."""
    page, errors = open_page(
        browser, serve(SETTLED_PAGE, anchored=[("opt-strict", "arrives logged out")])
    )
    group = page.locator("#transport")
    height = "el => Math.round(el.getBoundingClientRect().height)"

    assert errors == []
    collapsed = group.evaluate(height)
    assert page.locator("#transport lf-option:visible").count() == 0
    row = page.locator("#transport .lf-settled")
    assert row.inner_text().startswith("Settled: Lax cookie")
    assert row.get_attribute("aria-expanded") == "false"

    row.click()
    opened = group.evaluate(height)
    assert page.locator("#transport lf-option:visible").count() == 3
    assert opened > collapsed * 3, (
        f"collapsing saved {opened - collapsed}px of {opened}px — a settled group "
        f"that still costs most of its open height isn't a sweep"
    )

    row.click()  # closed again, so the reveal below has something to open

    # While it is closed the row is the decision's only visible statement, so the part of
    # it naming the card has to be quotable — and a drag across it must not toggle the
    # disclosure it lives in, which is the mouseup of that drag.
    title = page.locator("#transport .lf-settled [data-lf-said]")
    box = title.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    assert (
        page.evaluate("() => getSelection().toString()").strip()
        == "Settled: Lax cookie"
    )
    expect(page.locator("#opt-strict")).to_be_hidden()
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert composer_quote(page)["text"].strip("“”") == "Settled: Lax cookie"
    page.keyboard.press("Escape")

    # The row names the chosen card, so the page now says "Lax cookie" twice and both
    # copies are quotable. A comment on the card's own lede has to land on the card —
    # the row comes first in document order, which is where a search on the quote alone
    # would put it.
    #
    # Dropping the selection first is the user's own next move: a press that lands
    # inside a live selection is that selection's, so the row would not open under it.
    page.locator("#lede").click()
    row.click()
    expect(
        page.locator("#opt-lax")
    ).to_be_visible()  # until-found keeps a box either way
    lede = page.locator("#opt-lax > strong")
    box = lede.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    page.locator(".lf-composer textarea").fill("which copy is this on?")
    page.get_by_role("button", name="Comment", exact=True).click()
    # Two, not one: this page arrived carrying a mark, so waiting for any at all is a
    # wait that was over before the gesture started.
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 2")
    # Both marks on the page: the one this fixture arrived carrying, and the new one.
    assert sorted(
        page.evaluate(
            "() => [...CSS.highlights.get('lf-mark')].map(r => "
            "r.startContainer.parentElement.closest('[id]').id)"
        )
    ) == ["opt-lax", "opt-strict"], (
        "the comment landed on the summary line rather than the card it was made on"
    )
    row.click()  # closed again, so the reveal below has something to open

    # Sending opened the panel, so the thread is already listed. Its quote is on a card
    # the collapse is hiding, and following it has to bring the card back.
    page.locator(".lf-panel .lf-quote", has_text="arrives logged out").click()
    assert page.locator("#opt-strict").is_visible(), (
        "clicking a thread's quote must open the group holding it"
    )
    page.close()


def test_a_printed_page_says_which_option_carries_the_pick(browser, serve):
    """Print drops the runtime's own layer as one thing, and the controls a widget
    injects with it: on paper there is nothing to press. The pick's mark is a control
    and a statement at once, though, so dropping it takes the statement too — and a
    settled group loses its summary row the same way, leaving a printed decision
    stated in the ok ring alone, a colour greyscale drops.

    So on paper a choose group renders as one that was never choosable: the marks
    offering a pick go, the one on the card carrying it stays and says so, and the
    strip of room the marks need is reserved where a mark shows rather than on
    every card. Which of the two a mark is saying is the label's own declaration
    (relabel), so paper needs no rule naming this widget — the same reason a tab
    strip goes while each panel's label comes back."""
    page, errors = open_page(browser, serve(SETTLED_PAGE))
    row = page.locator("#transport .lf-settled")
    expect(row).to_contain_text("Settled: Lax cookie")
    expect(page.locator(".lf-banner")).to_be_visible()

    # The strip the mark sits in: what the card's bottom padding holds over its own
    # base, so the measure follows the theme's spacing instead of pinning a number.
    strip = """el => parseFloat(getComputedStyle(el).paddingBottom) -
                     parseFloat(getComputedStyle(el).paddingLeft)"""
    pick = page.locator("#opt-lax .lf-pick")
    page.emulate_media(media="print")
    expect(
        page.locator(".lf-banner")
    ).to_be_hidden()  # the whole layer, by its own root
    expect(
        row
    ).to_be_hidden()  # the disclosure is a screen affordance; paper has the cards
    expect(pick).to_be_visible()
    expect(pick).to_have_text("chosen")
    expect(page.locator("#opt-strict .lf-pick")).to_be_hidden()
    assert page.locator("#opt-strict").evaluate(strip) == 0, (
        "a card whose mark can't print is holding room for it — an empty strip "
        "under a card the printed page says nothing about"
    )

    page.emulate_media(media="screen")
    row.click()
    expect(page.locator("#opt-strict")).to_be_visible()
    assert page.locator("#opt-strict").evaluate(strip) > 0, (
        "on screen the pick can still land here, and the card has to already hold "
        "the room or picking it moves the box"
    )
    assert errors == []
    page.close()


def test_a_pick_the_page_only_reports_can_still_be_pointed_at(browser, serve):
    """A group with no `choose` still says which option the document carries, and
    that word is a thing to say rather than a thing to work. So it goes the way
    every other word the page says goes: past the gate that hunts words on screen
    no selection can reach, and under a drag that raises the Comment button.

    It shipped the other way round. The mark is one element in two shapes — a
    press where there is a pick to make, an inert span where there isn't — and the
    inert one wore the press's `.lf-ui`, which anchoring skipped, so a user
    could read "chosen" and not point at it. Every shipped example declares
    `choose`, so the render suite never rendered the inert shape and nothing said
    so. The press was out of reach for longer and for a different reason, which
    test_a_pick_offered_can_be_pointed_at_too covers.

    Quotable is half a pair, so the other half is here too: the diff parses the
    base version unupgraded, where no mark exists at all, and must not read this
    one as a change nobody wrote."""
    url = serve(CARRIED_PAGE)
    assert interact.render_version(browser, url) == []

    page, errors = open_page(browser, url)
    mark = page.locator("#c-lax .lf-pick")
    assert mark.get_attribute("role") is None, "nothing to press means no button role"
    box = mark.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    assert page.evaluate("() => getSelection().toString()").strip() == "chosen", (
        "a drag across the mark selected nothing — the state is painted, not said"
    )

    page.locator(".lf-fab").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'block'"
    )
    assert composer_quote(page)["text"].strip("“”") == "chosen"
    page.locator(".lf-composer textarea").fill("say which version chose it")
    page.get_by_role("button", name="Comment", exact=True).click()
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert painted(page, "lf-mark") == "chosen"

    # A second version rewording the option nobody picked. The mark is written by
    # the runtime and stands in no version file, so the anchor on it has to be
    # found again in the page the user now has — and read as no change,
    # since the base version this diff loads has no mark in it at all.
    d = serve.page_dir
    (d / "versions" / "v2.html").write_text(
        CARRIED_PAGE.replace("Suits the mobile client", "Suits the mobile client best")
    )
    interact.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "two"}
    )
    page.wait_for_url("**/v2.html")
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    expect(page.locator(".lf-thread .lf-quote.detached")).to_have_count(0)

    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map(e => e.id)"
    ) == ["c-bearer"], "the diff read the mark as text the base version lacked"
    assert errors == []
    page.close()


def test_a_pick_offered_can_be_pointed_at_too(browser, serve):
    """The same words on the other shape of mark, in a group that takes a pick. This
    one was out of reach for a reason no marker could fix: the mark was a <button>,
    and no engine starts a pointer selection inside a form control, so "chosen" was on
    screen and unselectable however it was declared. A press is a span wearing the role
    now, which is what makes the drag below possible at all.

    Two things then have to hold at once. The drag has to select rather than pick — its
    mouseup lands on the very control it crossed — and the mark has to stay pressable,
    or the fix has traded a word nobody can quote for a decision nobody can make."""
    page, errors = open_page(browser, serve(SETTLED_PAGE))
    page.locator(
        "#transport .lf-settled"
    ).click()  # open the group; the cards are hidden
    mark = page.locator("#opt-lax .lf-pick")
    expect(mark).to_have_text("chosen")

    # Where the theme puts it: one line along the card's own bottom edge, in the same
    # place whichever word it carries. Pinned because the mark now declares itself the
    # page speaking, and the marker it declares with is the one the theme's chip band is
    # selected by — matched bare, the mark came out a pill at the head of the card and
    # every assertion here still passed.
    #
    # The same place, not the same box. An offer says nothing, so the mark on a card
    # nobody has picked is a held space and the picked one grows a word into it. What the
    # matching box used to stand for — that a pick shifts nothing — is asked of the card
    # itself further down, which is the fact rather than a proxy that happened to imply it.
    seat = """el => { const r = el.getBoundingClientRect();
                      const card = el.closest('lf-option').getBoundingClientRect();
                      return [Math.round(card.bottom - r.bottom),
                              Math.round(r.left - card.left)]; }"""
    assert mark.evaluate(seat) == page.locator("#opt-strict .lf-pick").evaluate(seat)
    up, over = mark.evaluate(seat)
    assert mark.bounding_box()["height"] < 24 and up < 16 and over < 20, (
        f"the mark is not a one-line caption on the card's bottom-left: {[up, over]}"
    )

    box = mark.bounding_box()
    y = box["y"] + box["height"] / 2
    # Right to left: the ✓ ring is not text.
    select(page, (box["x"] + box["width"] - 2, y), (box["x"] + 2, y))
    assert page.evaluate("() => getSelection().toString()").strip() == "chosen"
    expect(page.locator("#transport > lf-option[chosen]")).to_have_count(1)
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert composer_quote(page)["text"].strip("“”") == "chosen"
    page.keyboard.press("Escape")

    # Still a control: clicking the card that holds the pick clears it, and the keyboard
    # reaches the mark and works it the way the <button> did.
    page.evaluate("() => getSelection().removeAllRanges()")
    strict = page.locator("#opt-strict")
    strict.click()
    expect(page.locator("#opt-strict[chosen]")).to_have_count(1)

    # And the card it lands on is the same box after the pick as before it: the room a
    # picked mark's word needs is held on every card in the group, so the word grows into
    # space already reserved. That is the fact the matching mark boxes above used to stand
    # in for, and the one the user feels — a card that resized under the pointer takes
    # the next gesture's aim with it.
    #
    # Measured across an empty group rather than across a swap. Moving the pick from one
    # card to another gives the strip back exactly as fast as it takes it — and in the
    # days the group was a grid, the row stood as tall as its tallest cell either way —
    # so a swap can hold still with the reservation deleted. Clearing the pick first is
    # what makes the room actually go missing.
    box = """el => { const r = el.getBoundingClientRect();
                     return [Math.round(r.width), Math.round(r.height)]; }"""
    strict.click()  # clicking the pick clears it, so now the group holds no answer
    expect(page.locator("#transport > lf-option[chosen]")).to_have_count(0)
    empty = strict.evaluate(box)
    strict.click()
    expect(page.locator("#opt-strict[chosen]")).to_have_count(1)
    assert strict.evaluate(box) == empty, (
        f"answering the group resized the card it was answered on: {empty} -> "
        f"{strict.evaluate(box)}"
    )
    page.locator("#opt-bearer .lf-pick").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#opt-bearer[chosen]")).to_have_count(1)

    # And the pair the quotable half always comes with. This mark is the one element on
    # any page wearing the chrome class and the page-speaking marker at once, so it is the
    # only case where the anchor pass's reading and the diff's can come apart: the base
    # version is parsed unupgraded and has no mark in it at all. Read as text, the card
    # carrying the pick lights up as changed on every revision.
    #
    # v2 rewords a third card, so the card the diff should mark and the card wearing the
    # mark are different ones — with the pick on the reworded card there is nothing to
    # see, which is how this passed while reading the mark as text.
    d = serve.page_dir
    (d / "versions" / "v2.html").write_text(
        SETTLED_PAGE.replace("arrives logged out", "arrives logged out every time")
    )
    interact.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "two"}
    )
    page.wait_for_url("**/v2.html")
    expect(page.locator("#opt-bearer[chosen]")).to_have_count(
        1
    )  # replay carried the pick
    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map(e => e.id)"
    ) == ["opt-strict"], "the diff read a pick mark as text the base version lacked"
    assert errors == []
    page.close()


def test_a_card_group_taking_a_pick_reads_as_one_control(browser, serve):
    """The offer is the group's, made once, rather than a word written on every member.

    A card group under `choose` draws the border and its options become cells inside it,
    sharing hairlines: a set of alternatives at one size is what says a decision is
    waiting, so no option has to caption itself "choose". What the theme deletes is only
    the offer — a picked mark still says where the pick sits, which is the page's only
    statement of that and the one paper keeps.

    Pinned because the rules making the group one control are ranked against the ones
    making each option a card, and losing that race leaves a page that looks exactly as it
    did while saying nothing about being answerable — which reads as a feature nobody
    wired up rather than as a fault. The mark is measured against its own ring for the
    same reason: "no word" is the claim, and a mark exactly as wide as the dot it draws
    is the only way to make it without naming a font size."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    edge = """el => { const s = getComputedStyle(el);
                      return s.borderTopStyle === 'none' ? 0 : parseFloat(s.borderTopWidth); }"""
    assert page.locator("#approach").evaluate(edge) > 0, (
        "the group draws no edge of its own, so nothing says the set is one thing"
    )
    assert page.locator("#opt-shim").evaluate(edge) == 0, (
        "an option still draws its own border, so the group reads as cards standing apart"
    )

    mark = page.locator("#opt-shim .lf-pick")
    box = """el => [Math.round(el.getBoundingClientRect().width),
                    Math.round(parseFloat(getComputedStyle(el, '::before').width)),
                    getComputedStyle(el, '::before').visibility]"""
    width, ring, drawn = mark.evaluate(box)
    assert width == ring, (
        f"the resting mark carries more than its ring: {width} vs {ring}"
    )
    assert drawn == "hidden", "the ring is drawn on a card the group already speaks for"

    # And a reader arriving by keyboard can see where they landed. With the mark drawing
    # nothing, a ring on it would ring an empty box at the card's foot, so it goes on the
    # cell — what the press acts on, and what the reader is standing on. Reached by Tab
    # rather than focus(), because :focus-visible is a fact about how focus arrived and a
    # programmatic call is not the keyboard. Read as a style rather than a width, because
    # `outline: none` leaves outline-width computing to the initial `medium`: a box drawing
    # no ring at all still reports 3px.
    mark.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    ring_on = """el => { const on = el.closest('lf-option');
                      const drawn = (e) => { const s = getComputedStyle(e);
                          return s.outlineStyle === 'none' ? 0 : parseFloat(s.outlineWidth); };
                      return [on.id, on.matches(':has(> .lf-pick:focus-visible)'),
                              drawn(on), drawn(el)]; }"""
    on, held, card_ring, mark_ring = mark.evaluate(ring_on)
    assert (on, held) == ("opt-shim", True), (
        f"Tab did not land on the mark: {on} {held}"
    )
    assert card_ring > 0 and mark_ring == 0, (
        f"the focus ring is on the wrong box: card {card_ring}, mark {mark_ring}"
    )

    page.locator("#opt-shim").click()
    expect(mark).to_have_text("your pick")
    width, ring, drawn = mark.evaluate(box)
    assert width > ring and drawn == "visible", (
        f"the picked mark states the pick in no width at all: {width} vs {ring}, {drawn}"
    )

    # The copy medium: scripts are dropped, so the pick cannot be made and the group must
    # not go on saying one is waiting. The cards come apart and their rings come back, which
    # is the same page paper gets, and both get it by never being handed the offer.
    page.evaluate("() => document.documentElement.classList.add('lf-copy')")
    assert page.locator("#approach").evaluate(edge) == 0, (
        "a copy still draws the group as a control it has no way to work"
    )
    assert page.locator("#opt-stage").evaluate(edge) > 0, (
        "the cards did not come back apart in a copy"
    )
    assert page.locator("#opt-stage .lf-pick").evaluate(box)[2] == "visible", (
        "no ring and no container leaves a copy saying nothing about a pick at all"
    )
    assert errors == []
    page.close()


def test_a_quoted_widget_exhibits_without_taking_input(browser, serve):
    """A specimen is a mention, not a use. The exhibited widgets render at full
    fidelity — that is the whole point of showing one — but wire nothing that
    would carry the reader's edits back, so an example decision can't be
    answered and an example board can't be dragged. The unquoted copies on the
    same page are the control: they prove the affordances are missing because
    the specimen suppressed them, not because the upgrade failed.

    Presentation and view state are not input, so they still run: a quoted
    settled group collapses like any other."""
    page, errors = open_page(browser, serve(SPECIMEN_PAGE))
    assert errors == []
    assert page.locator(".lf-error").count() == 0

    # The exhibit rendered: the gutter's caption, and cards with real size. The label is
    # the page's own word, so the runtime says it as text a user can quote; only the
    # "quoted · " in front of it is the theme's, and only that is still pseudo-content.
    label = page.locator('#spec > [data-lf-said="label"]')
    assert label.text_content() == "a decision"
    assert (
        label.evaluate("el => getComputedStyle(el, '::before').content")
        == '"quoted · "'
    )
    assert page.locator("#quoted-group lf-option").count() == 2
    assert (
        page.locator("#quoted-group lf-option").first.evaluate(
            "el => Math.round(el.getBoundingClientRect().height)"
        )
        > 20
    )

    # …but takes nothing back. Nothing pressable: no grips, and no mark wearing
    # the button role — an unpicked quoted card carries no mark at all, exactly as
    # a group that never declared `choose`. A click chooses nothing either (the
    # choose path sets `chosen` before it sends, so a pick would show here).
    assert page.locator('#quoted-group .lf-pick[role="button"]').count() == 0
    assert page.locator("#quoted-board .lf-grip").count() == 0
    # Nor a box for words: an exhibited question takes no answer of either kind, and
    # a box is the one that would have looked answerable.
    assert page.locator("#quoted-group .lf-say").count() == 0
    page.locator("#q-shim").click()
    assert page.locator("#quoted-group lf-option[chosen]").count() == 0

    # The document's own state still reads: the settled group's authored pick
    # wears its mark, with nothing to press.
    assert page.locator("#quoted-settled .lf-pick:not([role])").count() == 1

    # A quoted suggestion shows what a pending change looks like — both slots
    # marked — and grows nothing to settle it with, so it is also not the
    # banner's to count or Accept all's to decide.
    assert page.locator("#quoted-suggestion lf-old").is_visible()
    assert page.locator("[data-lf-for='quoted-suggestion']").count() == 0
    expect(page.get_by_role("button", name="Accept all (1)")).to_be_visible()

    # The control: the same markup unquoted wires all of it.
    assert page.locator('#live-group .lf-pick[role="button"]').count() == 2
    assert page.locator("#live-board .lf-grip").count() == 1
    assert page.locator("[data-lf-for='live-suggestion']").count() == 1

    # Nor the room for one. A quoted card stands at the height of a card in a
    # group that never declared `choose`, because that is what it is; reserving
    # the mark strip would leave every exhibit trailing 32px of space that,
    # quoted, nothing can ever fill.
    pad = "el => getComputedStyle(el).paddingBottom"
    assert page.locator("#q-shim").evaluate(pad) != page.locator("#l-shim").evaluate(
        pad
    )

    # View state still runs inside a specimen: the settled group collapsed.
    assert page.locator("#quoted-settled lf-option:visible").count() == 0
    page.locator("#quoted-settled .lf-settled").click()
    assert page.locator("#quoted-settled lf-option:visible").count() == 2

    # The exception, once that group is open: the card the document marks does
    # carry a mark, so it keeps the strip a live pick would.
    assert page.locator("#q-lax").evaluate(pad) == page.locator("#l-shim").evaluate(pad)
    page.close()


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
ASK_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>ask</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def sent_events(page_dir):
    return [
        json.loads(line)
        for line in (page_dir / "comments.jsonl").read_text().splitlines()
    ]


def test_a_group_of_bare_labels_reads_as_a_question_about_the_page(browser, serve):
    """Which form a group takes is a fact about its options rather than an attribute
    saying so, and the whole of that fact is whether an option leads with a title. So
    one page carries both and neither knows about the other: the labels lay out as
    compact rows and the titled pair as full-width cards stacked down the page.

    Two things the lint cannot see. A resting mark shows no word in either form, because
    an offer states nothing a reader could disagree with — and what a *picked* mark says
    has to survive that, since it is the page's only statement of where the pick sits.
    What differs is the dot: a row draws one and a single-pick card does not. A card
    gives it up because the state has the whole cell to live in, while a row's is a
    column at the line's end with room reserved for it by name, so a row that stopped
    drawing there would end in a blank the width of the word it isn't saying. Both are
    asked here, since either could be the theme forgetting a rule rather than each form
    answering for itself. (What a card under `multiple` does instead is the next test's:
    that one is arity's, not the form's.) And a row's name is
    what the author wrote in it: the mark that lands inside the row once it is picked is
    the page speaking (`says`) and must stay out of the row's own name (`wrote`), or a
    question answered reads its answer back as part of what was asked."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    assert errors == []

    # One row per option in both forms: a single column with no template stated, so
    # the joined control below is a list whatever the options hold. The display is
    # asserted with the track count because "none".split(" ") is also one entry — a
    # group that lost `display: grid` entirely (and the hairline gaps with it) would
    # answer 1 as convincingly as the single-column control does.
    tracks = """el => { const s = getComputedStyle(el);
                        return [s.display, s.gridTemplateColumns.split(' ').length]; }"""
    assert page.locator("#jobs").evaluate(tracks) == ["grid", 1]
    assert page.locator("#bracket").evaluate(tracks) == ["grid", 1]

    # Under `choose` the group is one control in every form, and the list was the form
    # that went without: rows draw no border, no fill and no rule between them, so at
    # rest the only thing that ever drew a row's own box was the hover wash — which
    # arrives after the reader has already had to guess where to aim. The group's edge
    # and the cells' hairlines are what a reader sees before committing the pointer, and
    # they are the same two rules a card group has always had.
    edge = """el => { const s = getComputedStyle(el);
                      return s.borderTopStyle === 'none' ? 0 : parseFloat(s.borderTopWidth); }"""
    hairline = "el => getComputedStyle(el).boxShadow"
    assert page.locator("#jobs").evaluate(edge) > 0, (
        "a list offering a pick draws no edge, so nothing says the rows are answerable"
    )
    assert page.locator("#job-mounts").evaluate(hairline) != "none", (
        "a row draws no box of its own, so its bounds show only under the pointer"
    )
    # And the shape is the offer, so a list that asks nothing wears none of it.
    assert page.locator("#ordered").evaluate(edge) == 0, (
        "a list with no pick to take was drawn as a control anyway"
    )
    assert page.locator("#ord-mounts").evaluate(hairline) == "none", (
        "a row nobody can press draws cell edges anyway"
    )

    # The block a row is about, reachable as a link and written as the id it names —
    # the same way the comment panel writes an element anchor.
    ref = page.locator("#job-mounts .lf-ref")
    expect(ref).to_have_text("§ sec-mounts")
    assert ref.get_attribute("href") == "#sec-mounts"
    assert page.locator("#job-camera .lf-ref").count() == 0

    # No open mark says its word, in either form. The dot is where they part: a row's is
    # drawn and a single-pick card's is not, which is each form answering for the room it
    # reserved rather than one rule going missing. (Arity moves this too, which is why the
    # card side is read off `#bracket` rather than off the `multiple` card group beside it.)
    hidden = "el => getComputedStyle(el).fontSize"
    dot = "el => getComputedStyle(el, '::before').visibility"
    assert page.locator("#job-mounts .lf-pick").evaluate(hidden) == "0px"
    assert page.locator("#br-steel .lf-pick").evaluate(hidden) == "0px"
    assert page.locator("#job-mounts .lf-pick").evaluate(dot) == "visible"
    assert page.locator("#br-steel .lf-pick").evaluate(dot) == "hidden"

    page.locator("#job-heater").click()
    expect(page.locator("#job-heater[chosen]")).to_have_count(1)
    expect(page.locator("#job-heater .lf-pick")).to_have_text("your pick")
    assert page.locator("#job-heater .lf-pick").evaluate(hidden) != "0px"
    # The row's name, as the mark reports it back: what the author wrote, and not the
    # word the mark itself just added to the line. A chip is in it — authored markup,
    # the page's words about this option — and the mark's own "your pick" is not, which
    # is the whole of the distinction: a question answered must not read its own answer
    # back as part of what was asked, and nothing else the author wrote is the answer.
    assert (
        page.locator("#job-heater .lf-pick").get_attribute("aria-label")
        == "your pick: reversible Heat the bird bath — option 2 of 3"
    )
    page.close()


def test_a_group_says_how_many_of_it_the_reader_may_take(browser, serve):
    """How many a group takes is the one thing about it a reader has to know before
    pressing anything, and for a while the page said it nowhere. A `multiple` group drew
    the identical circles a single-pick group draws — the shape every platform uses for
    "one of these" — so the two questions were pixel-for-pixel the same and the only
    thing that distinguished them was the author remembering to say so in prose. A reader
    who took the marks at their word would pick once and expect the next click to replace
    it.

    So the mark carries the arity, in both of the registers one control has: its corner
    is round for one and square for any, and its word is "choose one" or "choose any" for
    a reader who gets no corner. The corner is read as a fraction of the mark's own box,
    because the two are computed in different units (a circle is stated as a percentage of
    a box whose size is stated in px) and the question is the shape rather than either
    number. What is pinned is that they differ and that the single-pick one is a full
    round — a threshold between them would be this design's 3px corner written down a
    second time, free to disagree with it.

    Arity is not the form, which is why the contrast is card against card. Both of the
    rules here were the list form's once, on the reading that a `multiple` group is a
    list of slots; `multiple` is orthogonal to which form a group takes, so a titled
    group asking "which of these" inherited neither and offered the reader nothing to
    count. Hence the second half: an unticked box is a fact about that option, not the
    group's offer said again, so it draws under `multiple` where a single-pick card —
    whose state has the whole cell to live in — gives it up.

    And the shape is paint inside a box that does not change, so neither arity is a
    pixel wider than the other and every room already reserved still covers."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    corner = """el => { const s = getComputedStyle(el, '::before');
                        const r = s.borderTopLeftRadius;
                        return r.endsWith('%') ? parseFloat(r) / 100
                                               : parseFloat(r) / parseFloat(s.width); }"""
    one = page.locator("#br-steel .lf-pick").evaluate(corner)
    many = page.locator("#tl-clamp .lf-pick").evaluate(corner)
    assert one == 0.5, "a group taking one option draws something other than a circle"
    assert many < one, (
        "a group taking more than one draws the circle that means 'one of these', so "
        "nothing on the page says the reader may take a second"
    )
    # Not the list form's rule wearing a card's clothes: the row group agrees with the
    # card group it shares an arity with, against the card group it shares a form with.
    assert page.locator("#job-mounts .lf-pick").evaluate(corner) == many

    # An unticked slot is that option's own state under `multiple`, so the box draws with
    # nothing in it — the reader counts what is left to take. A single-pick card has no
    # such second question and keeps giving its box up.
    dot = "el => getComputedStyle(el, '::before').visibility"
    assert page.locator("#tl-clamp .lf-pick").evaluate(dot) == "visible", (
        "a card group asking 'which of these' draws no empty boxes, so the reader has "
        "nothing to count and no sign a second pick is on offer"
    )
    assert page.locator("#br-steel .lf-pick").evaluate(dot) == "hidden"

    # Paint, not metrics: the mark's box is the same in both arities, which is what lets
    # the row form's reserved column and the card's reserved strip stand unchanged.
    box = "el => { const b = el.getBoundingClientRect(); return [b.width, b.height]; }"
    assert page.locator("#tl-clamp .lf-pick").evaluate(box) == page.locator(
        "#br-steel .lf-pick"
    ).evaluate(box), "the shape that says arity took room from the option beside it"

    # The same statement for a reader who gets no shape. A corner is paint, so all a
    # screen reader has of a mark is its word, and while that word was "choose" in both
    # arities the pixels above were the page's only account of how many it takes — which
    # is to say, no account at all for anyone listening. Read off the offer rather than
    # the pick: the offer is the state the reader is in while the question is still open,
    # which is when knowing costs them a wasted press.
    named = "el => el.getAttribute('aria-label')"
    assert (
        page.locator("#br-steel .lf-pick").evaluate(named)
        == "choose one: Steel — option 1 of 2"
    )
    assert (
        page.locator("#tl-clamp .lf-pick").evaluate(named)
        == "choose any: Bar clamp — option 1 of 2"
    )
    assert errors == []
    page.close()


NESTED_ASK_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>nested</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_a_question_inside_an_option_keeps_its_own_arity(browser, serve):
    """An option's content model is prose, so a question nests inside another question's
    option — the theme's argument-row form lists `lf-options` among the block content it
    lays out. The arity a mark wears has to be its own group's, and the shape that says so
    is one an enclosing group could hand down: written as an inherited value, "which of
    these" on the outside would have made "which one" on the inside draw squares, and the
    reader would be told they may take both of two answers that replace each other.

    So each group reaches only as far as the options it owns. This is what stops that
    being an argument: a descendant selector here would pass every other test on this
    page and fail only where two questions stand inside one another."""
    page, errors = open_page(browser, serve(NESTED_ASK_PAGE))
    corner = """el => { const s = getComputedStyle(el, '::before');
                        const r = s.borderTopLeftRadius;
                        return r.endsWith('%') ? parseFloat(r) / 100
                                               : parseFloat(r) / parseFloat(s.width); }"""
    assert page.locator("#in-now .lf-pick").evaluate(corner) == 0.5, (
        "a single-pick question took the arity of the question it is nested in, so it "
        "offers a set where only one answer will stand"
    )
    # And the outer group's own marks are unaffected by the group standing inside one of
    # its options: the mark on #out-drill is the outer question's, not the inner one's.
    assert page.locator("#out-drill > .lf-pick").evaluate(corner) < 0.5
    assert page.locator("#out-keys > .lf-pick").evaluate(corner) < 0.5
    assert errors == []
    page.close()


# An option arguing its case with the evidence inside it, which is the whole reason the
# card is more than a label. Three things to work stand in one option, one per vocabulary
# the guard reads: a widget's own control (the shot's radios, injected through `offer`), a
# widget's own words (the draft's body, which is deliberately not chrome and so is reached
# only by being inside a widget the option contains), and an element HTML calls
# interactive that no widget put there (the disclosure). A page holding one of the three
# would leave the other two to a guard that had never been asked about them.
INLINE_CASE_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>inline case</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_working_the_evidence_in_an_option_is_not_a_pick(browser, serve):
    """The group takes the pick on the whole option, and the case the reader decides on
    is argued inside the option. So the two gestures land in the same box, and the
    evidence has to win the ones aimed at it: flipping the shot chose that option, and
    the flip being a label press meant it chose the option and cleared it again — two
    decisions in the log, no state on the page to show for either, and nothing the reader
    could have seen. The disclosure and the draft chose it outright.

    Each gesture is read against its own effect rather than against the absence of a
    pick, because a click that never arrived would satisfy the absence: the frame flips,
    the disclosure opens, the editor takes the draft's place, and only then is the
    question still open. The log is asked once at the end, since the failure that costs
    the most puts a decision there while leaving the page looking untouched."""
    page, errors = open_page(browser, serve(INLINE_CASE_PAGE))
    option = page.locator("#ro-column")
    picked = "el => el.hasAttribute('chosen')"

    page.locator("#ro-shot .lf-shotpick label", has_text="after").click()
    expect(page.locator("#ro-shot input[value='after']")).to_be_checked()
    assert not option.evaluate(picked), "flipping the shot answered the question"

    page.locator("#ro-numbers summary").click()
    expect(page.locator("#ro-numbers")).to_have_attribute("open", "")
    assert not option.evaluate(picked), "opening the disclosure answered the question"

    page.locator("#ro-note .lf-draft-body").dblclick()
    expect(page.locator("#ro-note textarea")).to_be_visible()
    assert not option.evaluate(picked), (
        "opening the draft's editor answered the question"
    )

    assert [e for e in sent_events(serve.page_dir) if e["kind"] == "action"] == [], (
        "the reader working the evidence sent Claude a decision they never made"
    )

    # And the option's own words still answer it, which is what the card is for.
    page.locator("#ro-column-p").click()
    expect(page.locator("#ro-column > .lf-pick")).to_have_text("your pick")
    round_trip(page)
    assert [
        e["detail"]["options"]
        for e in sent_events(serve.page_dir)
        if e["kind"] == "action"
    ] == [["ro-column"]]
    assert errors == []
    page.close()


def test_every_row_hangs_its_mark_at_the_same_column(browser, serve):
    """A row's dot is both the list's statement that it takes a pick and the target of
    the press that makes one, and it says the first of those by standing in a column
    with the others. Twice it did not. Laid out as flex items the row's free space had to
    be handed to whichever part of the apparatus came first, so the column was a fact
    about the `for` reference and a row with no block to name parked its mark wherever
    its label ended. And a chip an option says (`risk`) went in last of all, past the
    mark that ends the line. `#jobs` carries both against rows that carry neither, which
    is where either reads worst — rows lined up and one hanging mid-sentence — and a
    group of rows naming nothing is what the shipped examples haven't got, which is why
    the form shipped the first way.

    Each mark is read against the end of its own row rather than against its
    neighbours', so the column and its place are one reading: the rows are all one
    width, and a mark that is not at its line's end is not in the column either."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    ends = """() => [...document.querySelectorAll('#jobs > lf-option')].map(o => {
                const style = getComputedStyle(o);
                const inset = parseFloat(style.paddingRight) + parseFloat(style.borderSpacing);
                const m = o.querySelector('.lf-pick').getBoundingClientRect();
                return m.right - (o.getBoundingClientRect().right - inset);
              })"""
    assert page.evaluate(ends) == [0, 0, 0], (
        "a row's mark hangs where its label happened to end, or behind something the row "
        "said after it, so the group offers the reader no column of dots to aim down"
    )
    assert errors == []
    page.close()


def test_a_row_label_keeps_the_spacing_it_was_written_with(browser, serve):
    """A row is a line of prose with apparatus after it, and the prose is the author's:
    what it says between two words is a space, and the page owes them that space and no
    other. Laid out as flex items it owed them whatever the row's own `gap` was, because
    every stretch of a label became an item of its own and a flex item's edge whitespace
    is trimmed — `Replace the <code>M8</code> mounts` came out with 8px either side of
    the code and without the space that was written there, and zeroing the gap took the
    space away without giving it back. So the room between the last word and the code it
    runs into is read against the space itself: that the space is on the screen at all,
    and that nothing else is standing in for it."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    room = """() => {
                const code = document.querySelector('#job-mounts code');
                const text = code.previousSibling;   // "Replace the "
                const range = (from, to) => {
                  const r = document.createRange();
                  r.setStart(text, from); r.setEnd(text, to);
                  return r.getBoundingClientRect();
                };
                const word = range(0, text.data.length - 1);
                const space = range(text.data.length - 1, text.data.length);
                return [space.width, code.getBoundingClientRect().left - word.right];
              }"""
    space, gap = page.evaluate(room)
    assert space > 1, "the space the label was written with is not on the screen"
    assert abs(gap - space) < 0.5, (
        f"{gap}px of room where the label asked for {space}px"
    )
    assert errors == []
    page.close()


def test_a_row_holds_its_mark_still_under_its_own_press(browser, serve):
    """The mark is what the press is aimed at, so it is the last thing on the page that
    may move when the press lands — and the word it gains is exactly what would move it.
    The room for that word is held from the start, which is what keeps the § reference
    beside it still; the dot inside had no such guarantee, because it was centred in a
    box whose height was the word's, so a mark that gained one lifted its own dot 3.4px
    out from under the pointer that had just pressed it. Out of flow, over the row's own
    height, the dot stands where it stood."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    mark = page.locator("#job-heater .lf-pick")
    box = "el => JSON.stringify(el.getBoundingClientRect())"
    before = mark.evaluate(box)
    page.locator("#job-heater").click()
    expect(mark).to_have_text("your pick")
    assert mark.evaluate(box) == before, "the press moved the mark it landed on"
    assert errors == []
    page.close()


def test_a_chip_an_option_says_stands_with_the_rest_of_its_words(browser, serve):
    """A chip is the page's words and the apparatus after it is the module's, so the
    reader — and the file's reading of that same version — find the chip inside the
    row's own words rather than past the mark that ends the line.

    The rule was written against an attribute rendered by `x-says`, where the edge a
    pseudo-element would have taken stops being the element's own words the moment a
    module injects chrome, and appending put the page's words on the far side of it.
    A chip is authored markup now, written before the title, so it cannot land there by
    construction — which is the stronger form of the same guarantee, and this holds the
    outcome rather than the mechanism that used to threaten it."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    chip = page.locator("#job-heater > lf-chip")
    expect(chip).to_have_text("reversible")
    expect(page.locator("#job-heater > .lf-pick:last-child")).to_have_count(1)
    ref = page.locator("#job-heater .lf-ref").bounding_box()
    assert chip.bounding_box()["x"] < ref["x"], (
        "the chip stands before the row's apparatus"
    )
    assert errors == []
    page.close()


CHIP_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>chips</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="h">Short facts</h1>
<p id="intro">The store is <span class="tag">experimental</span> for now.</p>
<lf-options id="picks" choose>
  <lf-option id="p-keep"><lf-chip>reversible</lf-chip><strong>Keep the store</strong></lf-option>
</lf-options>
<lf-tasks id="plan">
  <lf-task id="t-camera" status="active" owner="finch"><strong>Mount the camera</strong></lf-task>
</lf-tasks>
</main>
</body>
</html>
"""


def test_one_pill_holds_every_short_fact(browser, serve):
    """The three writers of a chip, on one page: an author's inline label, a facet of a
    decision, and the row a task builds from its own attributes.

    They stated the pill three times and agreed on every number but one, which is the
    kind of agreement nobody is keeping: the inline label alone padded itself top and
    bottom, so it stood four pixels taller than the chips in a band while matching them
    everywhere else. One rule states the pill now and each wearer adds only where it
    sits, which is why this reads the rendered box rather than the declarations — a
    wearer is free to restate, and the box is what a reader compares."""
    page, errors = open_page(browser, serve(CHIP_PAGE))
    face = """el => { const s = getComputedStyle(el);
        return Object.fromEntries(["font-family", "font-size", "line-height",
            "padding", "border-radius", "background-color", "color"]
            .map(p => [p, s.getPropertyValue(p)])); }"""
    worn = {
        where: (page.locator(sel).evaluate(face), page.locator(sel).bounding_box())
        for where, sel in [
            ("in prose", "#intro > .tag"),
            ("on a decision", "#p-keep > lf-chip"),
            ("in a task's row", "#t-camera .lf-chips > span"),
        ]
    }
    ((first, (look, box)), *rest) = worn.items()
    for where, (other, other_box) in rest:
        assert other == look, (
            f"the chip {where} is drawn unlike the one {first}:\n  "
            + "\n  ".join(
                f"{k}: {other[k]!r} vs {look[k]!r}" for k in look if other[k] != look[k]
            )
        )
        assert other_box["height"] == box["height"], (
            f"the chip {where} stands {other_box['height']}px against "
            f"{box['height']}px {first}"
        )
    assert errors == []
    page.close()


PAINTED_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>painted</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_what_a_widget_paints_it_says_to_a_reader_listening(browser, serve):
    """A tint is a fact to whoever can see it and nothing at all to whoever can't. A
    task's marker, an event's kind band and the ring on the recommended option each
    carried their whole meaning in colour, so a reader listening was handed every word
    around the fact and never the fact: done sounded exactly like blocked, and the
    page's own recommendation — the one thing a decision page is most for — was
    invisible to the reader with the least other way to find it.

    Declared (x-paints) rather than written into each module, which is what lets it
    reach the two widgets here that have no module at all, and read as the value or, for
    a flag carrying none, the attribute's own name. Said in text, because that is the
    one thing every screen reader announces in every mode — and therefore clipped to
    nothing, holding no room, and out of the selection, since a word the eye can't see
    is a word the clipboard has no business carrying."""
    page, errors = open_page(browser, serve(PAINTED_PAGE))
    for sel, word in (
        ("#e-dark", "failure"),
        ("#p-stage", "recommended"),
        ("#t-baffles", "blocked"),
    ):
        assert word in page.locator(sel).aria_snapshot(), (
            f"{sel} paints `{word}` and says nothing of it to a reader listening"
        )
    # The option that isn't recommended says nothing: the pass speaks a fact the page
    # holds, never one it merely has an attribute for.
    assert "recommended" not in page.locator("#p-once").aria_snapshot()

    room = page.locator(".lf-quiet").evaluate_all(
        """els => els.map(el => { const r = el.getBoundingClientRect();
             return [el.textContent, r.width, r.height,
                     getComputedStyle(el).userSelect]; })"""
    )
    assert len(room) == 3, f"one quiet word per painted fact, got {room}"
    for word, width, height, select in room:
        assert width <= 1 and height <= 1, f"`{word}` is painting {width}x{height}"
        assert select == "none", f"`{word}` would come away in a copy of the page"
    # And the browser agrees: a selection drawn across the whole event carries the
    # words the page shows and not the one it only says.
    spoken = page.evaluate(
        """() => { const el = document.getElementById("e-dark");
             const r = document.createRange(); r.selectNodeContents(el);
             getSelection().removeAllRanges(); getSelection().addRange(r);
             return getSelection().toString(); }"""
    )
    assert "went dark" in spoken and "failure" not in spoken, spoken
    assert errors == []
    page.close()


def test_a_pick_states_the_whole_set(browser, serve):
    """`multiple` is the difference between "which of these" and "which one", and the
    action is the same shape either way: every picked option, absolutely, so replay is
    idempotent and a second tab converges rather than drifting. Without `multiple` the
    set a click toggles from is empty, which is what makes a pick replace instead of
    join — one rule, not two code paths."""
    page, errors = open_page(browser, serve(ASK_PAGE))

    page.locator("#job-mounts").click()
    expect(page.locator("#jobs > lf-option[chosen]")).to_have_count(1)
    page.locator("#job-camera").click()
    expect(page.locator("#jobs > lf-option[chosen]")).to_have_count(2)
    page.locator("#job-mounts").click()
    expect(page.locator("#jobs > lf-option[chosen]")).to_have_count(1)

    # The single-pick group beside it replaces rather than joining, and clicking the
    # pick again empties it.
    page.locator("#br-steel").click()
    expect(page.locator("#bracket > lf-option[chosen]")).to_have_count(1)
    page.locator("#br-cedar").click()
    expect(page.locator("#br-cedar[chosen]")).to_have_count(1)
    expect(page.locator("#br-steel[chosen]")).to_have_count(0)
    page.locator("#br-cedar").click()
    expect(page.locator("#bracket > lf-option[chosen]")).to_have_count(0)

    # A pick paints its own click before the post answers, so the DOM leads the log;
    # the trip counter says when everything sent has been read back.
    round_trip(page)
    picks = [
        (e["widget"], e["detail"])
        for e in sent_events(serve.page_dir)
        if e.get("action") == "choose"
    ]
    assert picks == [
        ("jobs", {"options": ["job-mounts"]}),
        ("jobs", {"options": ["job-mounts", "job-camera"]}),
        ("jobs", {"options": ["job-camera"]}),
        ("bracket", {"options": ["br-steel"]}),
        ("bracket", {"options": ["br-cedar"]}),
        ("bracket", {"options": []}),
    ]
    assert errors == []
    page.close()


def test_a_send_waits_for_the_send_before_it(browser, serve):
    """The log's order is the order the user acted in, and two requests in flight are
    not: the server answers each on a thread of its own, so a pick made a moment after
    another can be appended before it. That is the drift the test below is about,
    arriving through the log this time rather than through a poll — and arriving where
    nothing heals it, since replay states a widget whole and every later reading of the
    page is of the log it left.

    It reached CI before it was ever seen here, on the test above: two clicks three
    lines apart landed reversed on a loaded runner, twice, while two dozen runs of that
    same sequence in the dockerised Linux suite never once managed it. So the race is
    stated rather than run for. The first send is stopped in the wire and the second
    click made while it is still there, which is the whole of a loaded machine's
    contribution; what the page does about that click is the instrument, since it paints
    a pick before it sends and so has already done whatever it was going to do about
    sending by the time the paint is readable.

    Both halves are asserted and only one of them is the gate. One request in the wire
    is a fact about this page on every run, so it is what goes red the moment the queue
    does; the log's order after the release is the outcome the queue is for, and on its
    own it would be the same coin the runner tossed — a second send already appended
    beats the release, and one still in flight doesn't."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    held = []

    def hold(route):
        # The first send is stopped where the server cannot take it, and everything
        # after it goes through — so with the queue gone the second pick reaches the log
        # first, and releasing the first pick appends it on top of the newer one.
        if held:
            route.continue_()
        else:
            held.append(route)

    page.route("**/api/event", hold)
    page.locator("#br-steel").click()
    _until(page, lambda t: t.sends >= 1, "sent the pick it was clicked for")
    page.locator("#br-cedar").click()
    expect(page.locator("#br-cedar[chosen]")).to_have_count(1)
    assert _traffic(page).sends == 1, (
        "a second send went out over the first, so which of the two the server appends "
        "first is the machine's answer rather than the reader's"
    )

    held[0].continue_()
    round_trip(page)
    assert [
        e["detail"]["options"]
        for e in sent_events(serve.page_dir)
        if e.get("action") == "choose"
    ] == [["br-steel"], ["br-cedar"]]
    assert errors == []
    page.close()


def test_an_answer_carrying_an_older_pick_cannot_undo_a_newer_one(browser, serve):
    """Replay states a widget whole, so the order is what it owes: an action applied
    after the gesture that superseded it hands the reader their older state back, and
    the gesture after that computes from what it painted and sends a decision they
    never made. Applying each action once says nothing about *when* — a pick recorded
    before a click can still be replayed after it, which is what a loaded machine does
    to this page's own polls.

    So the instrument is that answer, stated from outside: every poll is served the log
    truncated to what the page may see, and the one that lands while the second pick is
    still in flight carries only the first — a poll snapshotted between the two picks,
    arriving after both, where a slow machine would have put it. Which poll that is
    cannot be timed from here, so the answers are gated on the page's own traffic. After
    it every poll is refused, so nothing heals what that answer did and the third pick
    reads the page the answer left.

    Another tab's pick on the group beside it rides the same answer, and is what says
    the batch was replayed at all: a trip is over when its response lands, which is
    before the page has done anything about it, so without that edge both the count
    below and the third click would be about a page nothing had happened to yet."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    d = serve.page_dir
    # The log, and how much of it the page is shown. Seq 1 is the note it opened on,
    # 2 the other tab's pick, 3 this tab's first — so an answer capped at 3 is one
    # snapshotted between this tab's two picks, and one capped at 1 keeps the page
    # from seeing either until then.
    OPENED_ON, THROUGH_THE_FIRST_PICK = 1, 3
    interact.append_event(
        d,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "bracket",
            "action": "choose",
            "detail": {"options": ["br-cedar"]},
        },
    )

    served = []  # what each answer was capped at, and so the record that one was

    def answer(route):
        # On posts answered rather than posts sent: the page asks for state the moment
        # one comes back, so the first poll after the second answer is the one that
        # pick's own send is still open across — which is the whole of the race.
        if _traffic(page).acked < 2:
            cap = OPENED_ON
        elif THROUGH_THE_FIRST_PICK not in served:
            cap = THROUGH_THE_FIRST_PICK
        else:
            refuse(route)
            return
        served.append(cap)
        state = route.fetch().json()
        state["events"] = [e for e in state["events"] if e["seq"] <= cap]
        route.fulfill(json=state)

    page.route("**/api/state*", answer)

    page.locator("#job-mounts").click()
    round_trip(page)
    page.locator("#job-camera").click()
    round_trip(page)
    expect(page.locator("#br-cedar[chosen]")).to_have_count(1)
    # Nothing else here says the answers were the ones the test wrote: served at full
    # length they carry the second pick too, and the page converges either way — so the
    # day this route stops matching, the test goes quiet rather than red.
    assert THROUGH_THE_FIRST_PICK in served, f"the log was never held back: {served}"
    expect(page.locator("#jobs > lf-option[chosen]")).to_have_count(2)

    # The page is deaf from here, so half of a round trip is never coming back: what
    # says the log holds this pick is the post's own answer, the server having appended
    # before it. Counted from before the click, so the picks already answered can't
    # satisfy it.
    answered = _traffic(page).acked
    page.locator("#job-heater").click()
    _until(page, lambda t: t.acked > answered, "had this click's send answered")
    assert [
        e["detail"]["options"] for e in sent_events(d) if e.get("widget") == "jobs"
    ] == [
        ["job-mounts"],
        ["job-mounts", "job-camera"],
        ["job-mounts", "job-camera", "job-heater"],
    ]
    assert errors == []
    page.close()


def test_the_box_for_words_reaches_the_log_as_a_comment_on_the_question(browser, serve):
    """A question can always be answered off its own menu, and without a box that answer
    costs the reader a hunt for some passage to select. What they type is an ordinary
    comment anchored on the group — one store, and everything the comment layer already
    guarantees — so the assertion is where the words land and what the page does after:
    the box empties, and the group wears the mark that says a comment is on it.

    It rides `wireInput` like every other composer, so the send button states whether
    there is anything to send — through aria-disabled, since a widget's press is a span
    and has no `disabled` to set. That one is invisible until it is wrong: the button
    looked live while the guard behind it refused."""
    page, errors = open_page(browser, serve(ASK_PAGE))

    box = page.locator("#jobs .lf-say textarea")
    send = page.locator("#jobs .lf-say [role='button']")
    assert send.get_attribute("aria-disabled") == "true"
    box.fill("Neither, really — do the camera and tell me what it costs.")
    assert send.get_attribute("aria-disabled") == "false"
    send.click()

    expect(page.locator("#jobs.lf-mark-el")).to_have_count(1)
    expect(box).to_have_value("")
    assert send.get_attribute("aria-disabled") == "true"

    said = [e for e in sent_events(serve.page_dir) if e["kind"] == "comment"]
    assert [(e["anchor"], e["text"]) for e in said] == [
        (
            {"section": "jobs"},
            "Neither, really — do the camera and tell me what it costs.",
        )
    ]
    assert errors == []
    page.close()


SETTLED_ASK_PAGE = ASK_PAGE.replace(
    '<lf-options id="jobs" choose multiple>',
    '<lf-options id="jobs" choose multiple settled>',
)


def test_the_box_is_offered_only_where_something_can_answer_it(browser, serve):
    """A textarea and a Send button with no handler behind them invite the reader to
    type into a page that cannot send it, which is the worst of the three media to be
    wrong in — it looks live. So the box is withheld rather than undone: the offer is
    made once in the live page, and a copy, a printout and a retired question each get
    the page without it by never being handed it.

    The collapse is the same rule at a different scale. A settled group's box goes
    behind the disclosure with its options, because the question is retired until the
    reader opens it again — and `display: flex` on the class would otherwise outrank
    the hidden attribute and leave a box floating under a collapsed group.

    What the options go behind is `hidden="until-found"`, which is find-in-page's to
    reopen and so collapses the box with content-visibility rather than by removing it.
    That is containment, and containment passes over a table box without a word — a
    question row states its layout as a table, so a settled group of them stayed on
    screen under a shut disclosure, reading as one that had never collapsed."""
    page, errors = open_page(browser, serve(SETTLED_ASK_PAGE))
    assert errors == []

    box = page.locator("#jobs .lf-say")
    rows = page.locator("#jobs > lf-option")
    expect(box).to_be_hidden()
    assert rows.evaluate_all(
        "els => els.map(e => e.getBoundingClientRect().height)"
    ) == [0, 0, 0]
    page.locator("#jobs .lf-settled").click()
    expect(box).to_be_visible()
    assert all(
        rows.evaluate_all("els => els.map(e => e.getBoundingClientRect().height > 0)")
    )

    # The copy medium: the same DOM with the affordance never handed to it.
    page.evaluate("() => document.documentElement.classList.add('lf-copy')")
    expect(box).to_be_hidden()
    page.close()


def test_the_specimen_gutter_is_painted_in_both_schemes(browser, serve):
    """The gutter is the whole marking, and it is the one part of a specimen with
    a color of its own: a token the dark block forgot would leave the bar
    transparent and the quoting silently gone. Nothing else catches that — not even
    the sweep that now drives a specimen through render_version in both palettes,
    since a transparent border is not an error, resizes no box, and leaves every
    word selectable."""
    url = serve(SPECIMEN_PAGE)
    for scheme in ("light", "dark"):
        page = browser.new_page(color_scheme=scheme)
        page.goto(url, wait_until="networkidle")
        gutter = page.locator("#spec").evaluate(
            "el => getComputedStyle(el).borderLeftColor"
        )
        assert gutter not in ("rgba(0, 0, 0, 0)", "transparent"), f"[{scheme}] {gutter}"
        page.close()


def test_the_specimen_gutter_starts_where_the_exhibit_does(browser, serve):
    """The gutter marks what is quoted, and the "quoted ·" note over it is the
    theme's word *about* the quoted region rather than a word in it — so the bar
    stands beside the exhibit and beside nothing else. It opened at the note
    instead, which drew the marking around a line the page never said.

    Geometry can't answer this. The element's own rect is the table wrapper's and
    takes in the caption, while the bar is painted on the table box inside it,
    which nothing in the DOM is a handle on — so a rect comparison passes exactly
    as well with the note back inside the marking. The pixels in the bar's own
    column are the reading: a run of the border's colour from the foot of the
    specimen up, whose top edge is where the marking begins, and which has to land
    in the gap between the note and the exhibit."""
    from PIL import Image  # a dev dependency already, for the demo recorder

    page, errors = open_page(browser, serve(SPECIMEN_PAGE))
    assert errors == []
    box = page.locator("#spec").bounding_box()
    note = page.locator('#spec > [data-lf-said="label"]').bounding_box()
    exhibit = page.locator("#quoted-group").bounding_box()
    border = page.locator("#spec").evaluate(
        "el => getComputedStyle(el).borderLeftColor"
    )
    ink = tuple(int(n) for n in re.findall(r"\d+", border)[:3])

    # A column one pixel wide inside the 3px bar, from the specimen's top down past
    # where the exhibit starts. Read from the bottom up and stopped at the first
    # pixel that isn't the bar's, so a glyph of the note's that happens to
    # antialias through this colour is not a bar the run can reach.
    #
    # The clip's top is floored first and the reading counts from the floored value,
    # because a clip is asked for in CSS pixels and Chrome truncates the rect before
    # it scales — a pixel of unmodelled bias, against a gap of four.
    scale = page.evaluate("() => devicePixelRatio")
    clip = {
        "x": box["x"] + 1,
        "y": math.floor(box["y"]),
        "width": 1,
        "height": math.ceil(exhibit["y"] - box["y"]) + 20,
    }
    on_screen = page.evaluate(
        "([y, h]) => y >= 0 && y + h <= innerHeight", [clip["y"], clip["height"]]
    )
    assert on_screen, (
        f"#spec is not wholly on screen ({clip}): a screenshot clip is the "
        f"viewport's, so the scan below would read a truncated image"
    )
    strip = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
    assert strip.height == clip["height"] * scale, (
        f"the clip asked for {clip['height']} CSS px at dpr {scale} and came back "
        f"{strip.height} device px: the arithmetic below no longer locates its edge"
    )
    rows = [strip.getpixel((0, y)) for y in range(strip.height)]
    painted = 0
    while painted < len(rows) and all(
        abs(a - b) <= 6 for a, b in zip(rows[-1 - painted], ink)
    ):
        painted += 1
    assert painted, f"no gutter painted in the column beside the exhibit: {rows[-1]}"

    # One bracket rather than two assertions: the bar's top edge stands in the gap,
    # a note inside the marking pushing it up out of the gap and a marking that
    # starts after what it marks pushing it down out of the other end.
    top = clip["y"] + (len(rows) - painted) / scale
    assert note["y"] + note["height"] <= top + 1 <= exhibit["y"] + 1, (
        f"the gutter starts at {top}, outside the gap between the note "
        f"(to {note['y'] + note['height']}) and the exhibit (from {exhibit['y']}): "
        f"the marking takes in the note, or begins after what it marks"
    )
    page.close()


def test_a_specimen_holds_a_wide_exhibit_inside_the_column(browser, serve):
    """An exhibit wider than the column scrolls inside its own box, as it does
    anywhere else on the page. What makes that true here is one declaration —
    a table sizes to its content, so without `table-layout: fixed` the specimen
    grows to the board's width and hands the document a sideways scrollbar, taking
    the comment layer's anchoring off screen with it.

    Read at a viewport narrow enough for the board to want more room than the
    column has; at the render sweep's own 1200px the board fits and nothing here
    can fail."""
    page, errors = open_page(browser, serve(SPECIMEN_PAGE))
    assert errors == []
    resized(page, 380, 900)
    wide = page.evaluate(
        "() => [document.documentElement.scrollWidth,"
        " document.documentElement.clientWidth,"
        " Math.round(document.getElementById('spec').getBoundingClientRect().width),"
        " document.getElementById('quoted-board').scrollWidth]"
    )
    document, column, specimen, board = wide
    assert board > column, (
        f"the board is {board}px in a {column}px column: it has to want more room "
        f"than the column has, or nothing below is being tested"
    )
    assert specimen <= column, f"the specimen is {specimen}px in a {column}px column"
    assert document == column, (
        f"the document scrolls sideways ({document}px against {column}px): the "
        f"exhibit widened the specimen instead of scrolling inside it"
    )
    page.close()


def test_a_specimen_in_a_reply_is_quoted_there_too(browser, serve):
    """The panel is where a live question actually gets put — Claude's replies
    carry widget markup — so it is also where a quoted one has to stay quoted.
    One reply holds both: the question wires up and its pick reaches the log,
    the exhibit beside it does neither, and the gutter marking it renders in the
    panel's narrower column as it does in the document. The theme's specimen
    rules and quoted()'s closest() both have to reach outside <main>, and
    nothing else in the suite renders a specimen there."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    interact.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-ask",
            "author": "user",
            "version": 1,
            "text": "What would the alternative look like?",
        },
    )
    interact.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-ask",
            "version": 1,
            "text": SPECIMEN_TEXT,
            "markup": SPECIMEN_MARKUP,
        },
    )
    page, errors = open_page(browser, url)
    page.get_by_role("button", name="Comments", exact=False).click()
    page.wait_for_selector(
        '#rp-live .lf-pick[role="button"]'
    )  # the reply's widgets upgraded
    assert errors == []

    # The gutter renders in the panel: the specimen rules aren't scoped to the
    # document's column, and neither is the label — which reaches the panel only
    # because renderSaid runs over a reply's markup too, where no custom element
    # upgrade would have carried it.
    label = page.locator('#rp-spec > [data-lf-said="label"]')
    assert label.text_content() == "the April thread"
    assert (
        label.evaluate("el => getComputedStyle(el, '::before').content")
        == '"quoted · "'
    )
    gutter = page.locator("#rp-spec").evaluate(
        "el => [getComputedStyle(el).borderLeftWidth,"
        " getComputedStyle(el).borderLeftColor]"
    )
    assert gutter[0] != "0px" and gutter[1] not in (
        "rgba(0, 0, 0, 0)",
        "transparent",
    ), f"the panel's specimen carries no gutter: {gutter}"
    assert (
        page.locator("#rp-quoted lf-option").count() == 2
    )  # and the exhibit is all there

    # The exhibit takes the click first, so anything it sends would reach the log
    # ahead of the live group's pick — then the live group takes its own.
    assert page.locator('#rp-quoted .lf-pick[role="button"]').count() == 0
    page.locator("#rp-memory").click()
    page.locator("#rp-stage").click()

    # Waiting on the log for *an* action would settle for the live group's and never see
    # a second one the exhibit had no business sending. The page's own count is the whole
    # of what it sent, so this waits out an exhibit's stray post too.
    round_trip(page)
    actions = [e for e in interact.read_events(d) if e["kind"] == "action"]
    assert [(e["widget"], e["detail"]) for e in actions] == [
        ("rp-live", {"options": ["rp-stage"]})
    ]
    assert page.locator("#rp-quoted lf-option[chosen]").count() == 0
    page.close()


TABLE_REPLY = """The ceilings, unchanged:

| Plan | A minute | Burst | Counted against | Reference |
| --- | --- | --- | --- | --- |
| Free | 60 | 120 | the token | GW-LIMITS-FREE-2026 |
| Enterprise | 6,000 | 12,000 | the token, per environment | GW-LIMITS-ENTERPRISE-2026 |

Taken from https://example.com/gateway/limits/reference/by-plan/current/table
"""


def test_a_table_in_a_reply_keeps_its_figures_whole(browser, serve):
    """A reply is Markdown, so it can hold a table, and the panel is 420px wide.
    Prose there breaks anywhere — the thing a reply overflows on is a URL no wrap
    can help — and a table caught the same rule: "12,000" came out as "12,0" over
    "00", in the column of figures the table was written to compare. Both halves
    are asserted together, since turning the breaking off everywhere reads the
    same in a cell and is the actual regression to fear."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    interact.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-ask",
            "author": "user",
            "version": 1,
            "text": "What are the ceilings?",
        },
    )
    interact.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-ask",
            "version": 1,
            "text": TABLE_REPLY,
        },
    )
    page, errors = open_page(browser, url)
    page.get_by_role("button", name="Comments", exact=False).click()
    page.wait_for_selector(".lf-msg-body table")

    # One client rect is one line: the figure is drawn as a single run, the URL
    # in the same reply as several.
    lines = """(el) => { const r = document.createRange();
                         r.selectNodeContents(el); return r.getClientRects().length; }"""
    assert page.get_by_role("cell", name="12,000").evaluate(lines) == 1
    assert page.locator(".lf-msg.claude .lf-msg-body a").evaluate(lines) > 1
    # And the room the cells stopped giving up went where the theme puts it.
    assert (
        page.locator(".lf-msg.claude .lf-msg-body table").evaluate(
            "(t) => t.scrollWidth - t.clientWidth"
        )
        > 0
    )
    assert (
        page.locator(".lf-msg.claude .lf-msg-body").evaluate(
            "(b) => b.scrollWidth - b.clientWidth"
        )
        == 0
    )
    assert errors == []
    page.close()


def test_a_board_says_which_column_each_card_is_in(browser, serve):
    """Which column a card sits in is the one fact about it that isn't in its own
    text, and columns are three boxes side by side — geometry, which the
    accessibility tree doesn't carry. Flat, this board was six text runs and two
    Move buttons in a row: no boundary between the columns, and no button saying
    where its card was.

    Both halves are asserted from the tree itself rather than from the attributes
    behind it, because that is where they can be wrong: the column heading is CSS
    generated content, so the name reaching the tree once (as the list's) rather
    than twice depends on its alt text. Then a card moves, and the assertion is
    the second snapshot — a name set where the move happens goes stale on
    whichever path forgets to restate its location or durable pending state."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    board = page.locator("#sprint")

    assert board.aria_snapshot() == (
        '- list "Todo":\n'
        "  - listitem:\n"
        "    - strong: Heated perch\n"
        "    - 'button \"Move: Heated perch — Todo\"': ⠿\n"
        "  - listitem:\n"
        "    - strong: Squirrel baffle\n"
        "    - 'button \"Move: Squirrel baffle — Todo\"': ⠿\n"
        '- list "Done"'  # empty, and still announced: it is a drop target
    )

    # Grab the second card and push it into the next column, the keyboard's path.
    board.get_by_role("button", name="Move: Squirrel baffle — Todo").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    page.wait_for_selector("#col-done #card-baffle")
    expect(
        board.get_by_role(
            "button",
            name="Move: Squirrel baffle — Done — awaiting next version",
            exact=True,
        )
    ).to_be_visible()

    assert board.aria_snapshot() == (
        '- list "Todo":\n'
        "  - listitem:\n"
        "    - strong: Heated perch\n"
        "    - 'button \"Move: Heated perch — Todo\"': ⠿\n"
        '- list "Done":\n'
        "  - listitem:\n"
        "    - strong: Squirrel baffle\n"
        "    - 'button \"Move: Squirrel baffle — Done — awaiting next version\"': ⠿"
    )
    assert errors == []
    page.close()


def test_composer_grows_with_its_text_without_script(browser, serve):
    """The comment box fits its content, caps, and shrinks back — and no script
    touches its height. That last part is the point: sizing a textarea from JS
    means shrinking it to re-measure on every keystroke, and a box briefly too
    small for its own text flashes a scrollbar."""
    page, _ = open_page(browser, serve(LONG_PAGE))
    page.get_by_role("button", name="Comments", exact=False).click()
    box = page.locator(".lf-general textarea")

    page.evaluate("""() => {
        const ta = document.querySelector('.lf-general textarea');
        window.__styled = 0;
        new MutationObserver(() => window.__styled++)
            .observe(ta, { attributes: true, attributeFilter: ['style'] });
    }""")

    def state():
        return box.evaluate("""ta => ({ h: Math.round(ta.getBoundingClientRect().height),
                                        scrollable: ta.scrollHeight > ta.clientHeight })""")

    empty = state()
    box.type("A comment long enough to wrap onto a second line and then a third.")
    grown = state()
    box.fill("x " * 900)  # far past the ceiling
    capped = state()
    box.fill("short again")
    shrunk = state()

    assert grown["h"] > empty["h"], "the box must grow with its content"
    assert not grown["scrollable"], "a box that fits its text must not be scrollable"
    # The ceiling is 50vh — the viewport's share, not a count of lines — measured
    # here in the suite's 900px-tall window.
    assert capped["h"] == 450, f"the box must stop at its ceiling, got {capped['h']}px"
    assert capped["scrollable"], (
        "past the ceiling the scrollbar is real and belongs there"
    )
    assert shrunk["h"] == empty["h"], "and it must shrink back"
    assert page.evaluate("window.__styled") == 0, "nothing may size the box from script"
    page.close()


# Two pending changes a line apart, and a third inside a widget that positions
# its own contents — the case where `left: 100%` resolves against the card rather
# than the column, and drops the controls back into the text, unless the row is
# the column's own child.
SUGGESTION_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>suggestions</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_suggestion_controls_stay_out_of_the_column(browser, serve):
    """Suggestion chrome hangs in the page margin, so the prose keeps the full column
    and reads as it will once the change is settled. The row is the column's own
    child and takes its line from an anchor inside the change, so how deep the
    change sits costs it nothing: one inside a card — a positioned ancestor, which
    `left: 100%` used to resolve against, dropping the row back into the text —
    hangs in the rail beside its card like any other. What is left is a
    measurement no lint can make: a window with no margin to hold the row docks it
    into flow, under the block it decides rather than overlapping the page.

    The margin the row hangs in is reserved, not left over, and the posture that
    proves it is the one a user reads in: with the comment panel open, a
    centred column left too little beside it and every row docked — above the
    change it decides, which reads as the paragraph before's."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    assert errors == []
    column = page.locator("main").evaluate("el => el.getBoundingClientRect().right")
    room = page.evaluate("() => document.body.getBoundingClientRect().right")
    box = "el => el.getBoundingClientRect()"

    margin_rows = page.locator(
        "[data-lf-for='sug-refill'], [data-lf-for='sug-thistle']"
    )
    assert margin_rows.count() == 2
    for i in range(2):
        assert margin_rows.nth(i).evaluate(box)["left"] > column, (
            "a control row overlapping the column re-wraps the prose it reviews"
        )
    # Two changes a line apart, so the rows would collide at their natural offsets.
    first, second = (margin_rows.nth(i).evaluate(box) for i in range(2))
    assert first["bottom"] <= second["top"], "control rows must not stack on each other"

    # The card is positioned and the change is three elements down inside it, and
    # the row still hangs in the rail on the line that change starts — which is
    # what the anchor buys, and what a static position never could.
    in_card = page.locator("[data-lf-for='sug-in-card']").evaluate(box)
    assert in_card["left"] > column and in_card["right"] <= room, (
        "a change inside a widget is still a change the user decides in the margin"
    )
    assert (
        abs(in_card["top"] - page.locator("#sug-in-card lf-old").evaluate(box)["top"])
        <= 4
    ), "the row must hang on the change's own line, not on the block it follows"

    # The panel takes the right of the window, and the rail survives it: the rows
    # keep their line, clear of the column on one side and of the panel on the
    # other. Measured after the layout has moved, since opening the panel resizes
    # the page and the rows re-place on the frame after that.
    page.get_by_role("button", name="Comments", exact=False).click()
    panel_settled(page)
    page.wait_for_function(
        "() => [...document.querySelectorAll("
        "'[data-lf-for=sug-refill], [data-lf-for=sug-thistle]')]"
        ".every(r => !r.classList.contains('lf-docked'))"
    )
    narrowed = page.locator("main").evaluate("el => el.getBoundingClientRect().right")
    room = page.evaluate("() => document.body.getBoundingClientRect().right")
    for i in range(2):
        rect = margin_rows.nth(i).evaluate(box)
        assert rect["left"] > narrowed and rect["right"] <= room, (
            "with the panel open the row must still hang between column and panel"
        )

    # No margin anywhere: every row docks, and nothing spills sideways. Docked is
    # the same box in flow where the row was hoisted to, so it reads as a control
    # line under the block holding the change and never as the one before's.
    page.get_by_role("button", name="Close comments").click()
    resized(page, 820, 900)
    page.wait_for_function(
        "() => [...document.querySelectorAll('.lf-sug-actions')]"
        ".every(r => r.classList.contains('lf-docked'))"
    )
    assert page.evaluate("() => document.body.scrollWidth <= document.body.clientWidth")
    for widget, block in [("sug-refill", "#replace"), ("sug-in-card", "#feeders")]:
        assert (
            page.locator(f"[data-lf-for='{widget}']").evaluate(box)["top"]
            >= page.locator(block).evaluate(box)["bottom"]
        ), "a docked row belongs under the block whose change it decides"
    page.close()


def test_a_moved_change_takes_its_controls_with_it(browser, serve):
    """The row is the column's child, not the change's, so the subtree a card
    travels in no longer carries it: a card dragged to another column, or moved by
    the replay of someone else's drag, leaves and re-enters the document with its
    row unhooked. Re-connection has to hang it again, or the user loses the
    only way to decide a change that is still plainly pending on the page. Replayed
    rather than dragged, because that is the same move with no gesture in the way."""
    url = serve(SUGGESTION_PAGE)
    interact.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "feeders",
            "action": "move",
            "detail": {"card": "card-heater", "to": "col-done", "index": 0},
        },
    )
    page, errors = open_page(browser, url)
    expect(page.locator("#col-done #card-heater")).to_be_visible()
    box = "el => el.getBoundingClientRect()"
    row = page.locator("[data-lf-for='sug-in-card']")
    expect(row).to_be_visible()
    change = page.locator("#sug-in-card lf-old").evaluate(box)
    assert abs(row.evaluate(box)["top"] - change["top"]) <= 4, (
        "the row must find the moved change's line again, not the one it left"
    )
    row.locator(".lf-sug-accept").click()
    expect(page.locator("#sug-in-card lf-old")).to_be_hidden()
    assert errors == []
    page.close()


# A change the reader hasn't opened yet. The row hangs off an anchor in the
# change, and a collapsed container reports its content's last rendered geometry
# rather than nothing at all — so a row that trusted a measurement would hang in
# the margin deciding a change nobody can see.
def test_a_terse_compare_keeps_its_side_by_side_grid(browser, serve):
    """An exhibition is looked across where a decision is read down: terse variants
    share a row while block content stacks the group. Which children count as block
    is the phrasing-set inversion, and its one hazard is an inline widget — a
    chip-led pair must not stack, which is why the stylesheet's list carries the
    registry's x-inline tags and this reads the shipped page to prove the grid
    actually held."""
    page, errors = open_page(
        browser,
        serve(
            (Path(__file__).parent.parent / "examples/design-decision.html").read_text()
        ),
    )
    top = "el => el.getBoundingClientRect().top"
    assert page.locator("#var-session-cookie").evaluate(top) == page.locator(
        "#var-fallback-cookie"
    ).evaluate(top), "chip-led terse variants must share a row"
    assert page.locator("#var-payments-regime").evaluate(top) != page.locator(
        "#var-sessions-regime"
    ).evaluate(top), "block-content variants must stack"
    assert errors == []
    page.close()


def test_a_block_change_emphasizes_the_words_that_moved(browser, serve):
    """A replacement's slots paint whole — which is all a dead copy keeps — and on
    the live page the words that differ deepen through the highlight registry, so
    the reader isn't left to eyeball-diff two paragraphs. Deciding clears the
    emphasis with the slot it retires: the survivor is plain prose."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    inside = """(id) => Object.fromEntries(['lf-sug-del', 'lf-sug-ins'].map(name =>
        [name, [...(CSS.highlights.get(name) ?? [])]
            .filter(r => document.getElementById(id).contains(r.startContainer))
            .length]))"""
    refill = page.evaluate(inside, "sug-refill")
    assert refill["lf-sug-del"] >= 1 and refill["lf-sug-ins"] >= 1, (
        "an edited sentence must emphasize the words that moved, on both sides"
    )

    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    assert page.evaluate(inside, "sug-refill") == {
        "lf-sug-del": 0,
        "lf-sug-ins": 0,
    }, "deciding must clear the emphasis with the slot it retires"
    assert errors == []
    page.close()


SWAP_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>swap</title>
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="h">Feeder notes</h1>
<p id="swapped">Plans changed.
  <lf-suggestion id="sug-swap">
    <lf-old>Refill every feeder each morning.</lf-old>
    <lf-new>The cameras watch seed levels overnight instead.</lf-new>
  </lf-suggestion></p>
</main>
</body>
</html>
"""


def test_a_whole_swap_paints_no_emphasis(browser, serve):
    """An alignment that shares almost nothing is a replacement, not an edit, and
    emphasis over everything says nothing — the similarity gate every mature diff
    view applies. The whole-slot tints already say a swap is on offer."""
    page, errors = open_page(browser, serve(SWAP_PAGE))
    total = page.evaluate(
        "() => (CSS.highlights.get('lf-sug-del')?.size ?? 0)"
        " + (CSS.highlights.get('lf-sug-ins')?.size ?? 0)"
    )
    assert total == 0, "unrelated old and new text must not be word-marked"
    assert errors == []
    page.close()


COLLAPSED_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>collapsed</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_a_row_waits_for_the_change_it_decides_to_be_on_screen(browser, serve):
    """A change inside a collapsed container has no line for its row to hang on,
    and an anchor that isn't rendered is no anchor at all: the row falls back to
    the block it was hoisted to and hangs there in the margin, offering to decide
    something the reader can't see. It waits instead, and arrives on the change's
    own line the moment the container opens — a real click on the summary, because
    opening it is the reader's gesture and the reflow it causes is the point."""
    page, errors = open_page(browser, serve(COLLAPSED_PAGE))
    waiting = page.locator("[data-lf-for='sug-boxes']")
    expect(page.locator("[data-lf-for='sug-now']")).to_be_visible()
    expect(waiting).to_be_hidden()

    page.locator("#sum").click()
    expect(waiting).to_be_visible()
    box = "el => el.getBoundingClientRect()"
    row = waiting.evaluate(box)
    assert row["left"] > page.locator("main").evaluate(box)["right"], (
        "the row must arrive in the margin, not over the prose that just opened"
    )
    assert (
        abs(row["top"] - page.locator("#sug-boxes lf-new").evaluate(box)["top"]) <= 4
    ), "and on the line of the change it decides"
    assert errors == []
    page.close()


def test_the_ask_walk_lands_on_a_suggestion_the_reveal_just_opened(browser, serve):
    """Stepping the asks opens the closed <details> a change waits inside and
    focuses that change's control in the same task. The row un-waits on the
    runtime's reveal signal rather than at the observer's next frame: settled
    asynchronously, focus() fell on a display:none control and stayed where it
    was — on the previous ask's Accept — while the announce said otherwise, so
    Enter was aimed at a decision the reader had already seen."""
    page, errors = open_page(browser, serve(COLLAPSED_PAGE))
    page.keyboard.press("a")
    expect(page.locator("[data-lf-for='sug-now'] .lf-sug-accept")).to_be_focused()
    page.keyboard.press("a")
    expect(page.locator("#later")).to_have_attribute("open", "")
    expect(page.locator("[data-lf-for='sug-boxes'] .lf-sug-accept")).to_be_focused()
    assert errors == []
    page.close()


def test_the_rail_survives_every_script_being_removed(browser, serve, tmp_path):
    """A standalone copy of a leaf page is its rendered DOM with the script tags
    dropped, and the pass that placed these rows is script. It doesn't have to run
    again: the row is a child of <main> in the serialized markup, and `left: 100%`
    against the column with `top: anchor(top)` against the change re-solve wherever
    the copy is opened and at whatever width. Including the change inside the card,
    whose positioned ancestor is exactly what a placement done in script would have
    had to correct for — and could not, with no script left to run."""
    page, _ = open_page(browser, serve(SUGGESTION_PAGE))
    page.evaluate("() => document.querySelectorAll('script').forEach(s => s.remove())")
    baked = page.evaluate("() => document.documentElement.outerHTML").replace(
        '<link rel="stylesheet" href="/theme.css">',
        "<style>" + (serve.page_dir / "theme.css").read_text() + "</style>",
    )
    page.close()

    standalone = tmp_path / "standalone.html"
    standalone.write_text(baked)
    loose = browser.new_page(viewport={"width": 1500, "height": 900})
    loose.goto(standalone.as_uri(), wait_until="load")
    assert loose.evaluate("document.querySelectorAll('script').length") == 0
    box = "el => el.getBoundingClientRect()"
    column = loose.locator("main").evaluate(box)["right"]
    for widget in ("sug-refill", "sug-in-card"):
        row = loose.locator(f"[data-lf-for='{widget}']").evaluate(box)
        assert row["left"] > column, f"{widget}'s row lost the rail without its script"
        assert (
            abs(row["top"] - loose.locator(f"#{widget} lf-old").evaluate(box)["top"])
            <= 4
        ), f"{widget}'s row lost its change's line without its script"
    loose.close()


def test_accepting_a_suggestion_settles_it_and_reaches_claude(browser, serve):
    """Accepting collapses the change to the proposal as ordinary prose — no
    tint, no strike — because the live view is the version plus the user's
    actions, and the honoring version only has to catch up.
    The outcome has to reach the log too: what the user sees settle and what
    Claude is told must be the same event.

    What stays is the row, saying what was done there. It used to clear itself in
    the same frame as the press, leaving a corner toast as the only evidence that
    anything had happened — and clearing a control is the one thing a press may not
    do to the line it was made on. Now the control the user pressed states the
    outcome where it stood and stops offering; its pair keeps its room and gives up
    only its ink, so nothing on the row is anywhere new."""
    page, _errors = open_page(browser, serve(SUGGESTION_PAGE))
    row = page.locator("[data-lf-for='sug-refill']")
    accept = row.locator(".lf-sug-accept")
    reject = row.locator(".lf-sug-reject")
    assert accept.get_attribute("aria-label").startswith(
        "Accept the suggested change: Refill a feeder when"
    ), "the button names the proposal, not the text being replaced"
    # Inside the row rather than on the page: the row is positioned, so a button's
    # offset box is its place on that row, and an inline change that reflows the
    # paragraph it sits in carries the whole row with it legitimately. What must not
    # move is one control against the other.
    box = "el => [el.offsetLeft, el.offsetTop, el.offsetWidth, el.offsetHeight]"
    before = [accept.evaluate(box), reject.evaluate(box)]
    # innerText throughout: what these assert is the visible word, and innerText is the
    # rendered text where textContent is the markup's.
    expect(accept).to_have_text("✓ Accept", use_inner_text=True)

    # A strike and two tints say which words are going and which are proposed, and say
    # it in no text at all: a reader listening got the sentence twice, the two readings
    # contradicting each other, with nothing to say either was a change.
    assert "deletion" in page.locator("#sug-refill lf-old").aria_snapshot()
    assert "insertion" in page.locator("#sug-refill lf-new").aria_snapshot()

    accept.click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    expect(page.locator("#sug-refill lf-new")).to_be_visible()
    expect(accept).to_have_text("✓ Accepted", use_inner_text=True)
    assert accept.get_attribute("aria-label").startswith(
        "Accepted the suggested change: Refill a feeder when"
    ), "the record still offers the press it has already taken"
    assert accept.get_attribute("aria-disabled") == "true"
    assert [accept.evaluate(box), reject.evaluate(box)] == before, (
        "the row rearranged as it was decided, on the one line a press must leave alone"
    )
    assert reject.evaluate("el => getComputedStyle(el).visibility") == "hidden", (
        "the decision left both halves of the offer standing"
    )
    settled = page.locator("#sug-refill lf-new").evaluate(
        "el => getComputedStyle(el).textDecorationLine + ' ' + getComputedStyle(el).backgroundColor"
    )
    # And the word goes with the marks, the settled slot being ordinary prose now:
    # a reader listening is told about a change while there is one to decide.
    assert "insertion" not in page.locator("#sug-refill lf-new").aria_snapshot()
    assert "line-through" not in settled and "rgba(0, 0, 0, 0)" in settled, (
        f"settled text still wears a pending mark: {settled}"
    )
    # The banner's count follows the page: three pending, one decided.
    expect(page.get_by_role("button", name="Accept all (2)")).to_be_visible()

    page.wait_for_function(
        "() => fetch('/api/state').then(r => r.json())"
        ".then(s => s.events.some(e => e.kind === 'action' && e.action === 'accept'))"
    )
    logged = [e for e in interact.read_events(serve.page_dir) if e["kind"] == "action"]
    assert [(e["widget"], e["action"], e["author"]) for e in logged] == [
        ("sug-refill", "accept", "user")
    ]
    page.close()


SHORT_SUGGESTION = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>short suggestion</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="t">Short</h1>
<section id="s">
<lf-suggestion id="sug">
  <lf-old><p id="was">Retry twice.</p></lf-old>
  <lf-new><p id="now">Retry three times.</p></lf-new>
</lf-suggestion>
<p id="after">The backoff is unchanged either way.</p>
</section>
</main>
</body>
</html>
"""


@pytest.mark.parametrize(
    "outcome,verb", [("accept", "Accepted"), ("reject", "Rejected")]
)
def test_a_widget_naming_its_own_words_does_not_read_the_runtimes(
    browser, serve, outcome, verb
):
    """The line saying a block carries a comment goes in the block, and a block inside a
    widget is still a block — so `textContent` on a widget's own slot now returns the
    author's words with the runtime's appended. A suggestion labels itself from that slot,
    and offered to accept “Retry three times. 1 comment”. It reads the slot the way the
    page is read instead, which is what `says` is for — read before deciding, because a
    reject retires the very slot the label comes from, and a retired slot says nothing:
    the toast then named the widget's id instead of the words the user judged. Short
    on purpose: the label cuts at 48 characters, which hid this on every shipped example."""
    url = serve(SHORT_SUGGESTION, anchored=[("now", "Retry three times")])
    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Vacuous otherwise: the line has to be inside the slot the label is read from.
    assert page.locator("lf-new #now > .lf-mark-note").count() == 1
    page.locator(f"[data-lf-for='sug'] .lf-sug-{outcome}").click()
    expect(page.locator(".lf-toast")).to_have_text(
        f"{verb} “Retry three times.” — sent to Claude"
    )
    assert errors == []
    page.close()


# Every animation the page starts, held at time zero so a test can read it rather than
# race it. The runtime's own chrome runs CSS animations, which this never sees; what it
# catches is a widget's WAAPI motion, started synchronously inside the gesture that
# causes it. Installed before anything runs, so the first frame is already held.
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


def test_a_decided_change_folds_away_rather_than_vanishing(browser, serve):
    """A decision may move the page; it may not teleport it.

    A block change is a struck old paragraph stacked over a tinted new one, and
    accepting used to drop the old one with `display: none` in the frame of the press —
    179 measured pixels out of the middle of the shipped design page, with everything
    below jumping up under the pointer that had just pressed. The rule this layer
    already carries is that a change the user asked for may move the page and must do
    it as motion, because motion is the form the eye can follow to where the sentence
    went.

    Held at its first frame rather than sampled mid-flight, which would be a race with
    the clock and would pass on a fast machine either way: the fold is read where it
    starts (the slot's own height, not zero), stepped to the middle, and then let go, so
    what the test proves is the shape of the motion and not how long the run took.

    An inline change is the test below: it has nothing to follow, and folding one would
    be the harm rather than the fix."""
    page, errors = open_page(browser, serve(SHORT_SUGGESTION), init_script=HOLD_MOTION)
    old = page.locator("#sug lf-old")
    after = page.locator("#after")
    tall = old.evaluate("el => el.getBoundingClientRect().height")
    assert tall > 0
    below = after.evaluate("el => el.getBoundingClientRect().top")

    page.locator("[data-lf-for='sug'] .lf-sug-accept").click()
    # The state is true from the first frame — the log carries it, the banner counts it,
    # a second tab converging reads it — while the pixels are still catching up.
    assert page.locator("#sug[data-lf-state='accept']").count() == 1
    held = page.evaluate(
        """() => window.__lfHeld.map((m) => [m.effect.target.tagName.toLowerCase(),
                                             m.effect.getTiming().duration])"""
    )
    assert [t for t, _ in held] == ["lf-old"], (
        f"the retired slot went without motion to follow: {held}"
    )
    at = "() => document.querySelector('#sug lf-old').getBoundingClientRect().height"
    assert page.evaluate(at) == pytest.approx(tall, abs=1), (
        "the fold begins somewhere other than where the paragraph was standing"
    )
    page.evaluate(
        "() => { const m = window.__lfHeld[0];"
        "        m.currentTime = m.effect.getTiming().duration / 2; }"
    )
    middle = page.evaluate(at)
    assert 0 < middle < tall, f"the fold's midpoint is not between its ends: {middle}"

    page.evaluate("() => window.__lfHeld[0].play()")
    expect(old).to_be_hidden()
    assert after.evaluate("el => el.getBoundingClientRect().top") < below, (
        "the page never gave back the room the retired paragraph was holding"
    )
    assert errors == []
    page.close()


def test_an_inline_change_is_swapped_rather_than_folded(browser, serve):
    """The other half of the rule above, and the half where folding would be the harm.

    A height to animate means a `display: block` held over the slot for the duration, so
    a few words swapped mid-sentence would open a paragraph break and close it again —
    motion answering a change that moved nothing. The shipped inline corpus is the case,
    and what it asserts is that nothing was started at all."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE), init_script=HOLD_MOTION)
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    assert page.evaluate("() => window.__lfHeld.length") == 0, (
        "a few words swapped inside a line were given a fold, and a block box to do it in"
    )
    assert errors == []
    page.close()


def test_a_reader_who_asked_for_less_motion_gets_the_collapse_at_once(browser, serve):
    """The fold is a courtesy to the eye, and an eye that asked for stillness is owed
    the outcome instead — the same bargain the board's own FLIP makes.

    Asked of the context rather than of the page, because the runtime reads the
    preference once as it loads: emulating it afterwards changes what the media query
    would answer and not what the module already recorded."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        color_scheme="light",
        reduced_motion="reduce",
    )
    try:
        page, errors = open_page(
            browser, serve(SHORT_SUGGESTION), context=context, init_script=HOLD_MOTION
        )
        page.locator("[data-lf-for='sug'] .lf-sug-accept").click()
        expect(page.locator("#sug lf-old")).to_be_hidden()
        assert page.evaluate("() => window.__lfHeld.length") == 0, (
            "a reader who asked for less motion was given a fold to sit through"
        )
        assert errors == []
    finally:
        context.close()


def test_accept_all_decides_every_pending_suggestion(browser, serve):
    """The banner's button is a shortcut for the user who has read the page
    and wants all of it, so it has to reach the ones their eye didn't: the
    suggestion inside a widget, whose controls dock in flow rather than hang in
    the margin. Each is decided individually, so the log records what was
    consented to one change at a time rather than one blanket yes."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    page.get_by_role("button", name="Accept all (3)").click()

    for widget in ("sug-refill", "sug-thistle", "sug-in-card"):
        expect(page.locator(f"#{widget} lf-new")).to_be_visible()
        # Waited for, not read once: each is decided by its own round trip, so the
        # last of them is still in flight when the first has settled.
        expect(page.locator(f"[data-lf-for='{widget}'] .lf-sug-accept")).to_have_text(
            "✓ Accepted", use_inner_text=True
        )
    for widget in (
        "sug-refill",
        "sug-in-card",
    ):  # the two that replace rather than insert
        expect(page.locator(f"#{widget} lf-old")).to_be_hidden()
    # Nothing left to accept, so the button says nothing rather than saying zero.
    expect(page.get_by_role("button", name=re.compile("Accept all"))).to_be_hidden()

    # Every one of those settled optimistically — the page shows a decision before the
    # server has taken it, which is the next test's whole subject — so the page reading
    # done is not the log holding it, and the last of the three is still in flight here.
    round_trip(page)
    logged = [e for e in interact.read_events(serve.page_dir) if e["kind"] == "action"]
    assert [(e["widget"], e["action"]) for e in logged] == [
        ("sug-refill", "accept"),
        ("sug-thistle", "accept"),
        ("sug-in-card", "accept"),
    ]
    assert errors == []
    page.close()


def test_a_key_gives_every_blanket_answer_the_banner_offers(browser, serve):
    """A is the banner's blanket answers in a press — the same controls, so the log
    records each decision one at a time exactly as a click does. Neither the key nor
    its legend names a verb: which verbs a page offers is the registry's answer
    (x-awaits.all), so the reference states the words the banner is writing at the
    moment it is opened. A sentence written into the table would have said "accept" in
    core, and gone on saying it for the second widget to declare a verb of its own.

    The shift is part of the key rather than decoration: caps lock turns a press of a
    into an uppercase one, and a is the walk through these one at a time, so the reader
    who wanted the next question would have settled every change on the page — a
    decision being the end of the matter."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    help_el = page.locator(".lf-help")

    page.keyboard.press("?")
    expect(help_el).to_contain_text("Accept all 3 waiting on you")
    page.keyboard.press("Escape")

    # A decision taken on its own control leaves two, and the legend says two: it is
    # read when the reference opens rather than held from when the table was written.
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(page.get_by_role("button", name="Accept all (2)")).to_be_visible()
    page.keyboard.press("?")
    expect(help_el).to_contain_text("Accept all 2 waiting on you")
    page.keyboard.press("Escape")

    # An unshifted uppercase press is what caps lock sends, and the dispatcher refuses
    # it: dispatched at the protocol level, which is the only place that press exists.
    cdp = page.context.new_cdp_session(page)
    for kind in ("keyDown", "keyUp"):
        cdp.send(
            "Input.dispatchKeyEvent",
            {
                "type": kind,
                "key": "A",
                "code": "KeyA",
                "windowsVirtualKeyCode": 65,
                "text": "A" if kind == "keyDown" else "",
            },
        )
    told(page)
    expect(page.get_by_role("button", name="Accept all (2)")).to_be_visible()

    page.keyboard.press("Shift+A")
    for widget in ("sug-thistle", "sug-in-card"):
        expect(page.locator(f"[data-lf-for='{widget}'] .lf-sug-accept")).to_have_text(
            "✓ Accepted", use_inner_text=True
        )
    # Nothing left to answer, so the control goes and the key goes with it.
    expect(page.get_by_role("button", name=re.compile("Accept all"))).to_be_hidden()
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    expect(help_el).not_to_contain_text("Accept all")

    round_trip(page)
    logged = [e for e in interact.read_events(serve.page_dir) if e["kind"] == "action"]
    assert [(e["widget"], e["action"]) for e in logged] == [
        ("sug-refill", "accept"),
        ("sug-thistle", "accept"),
        ("sug-in-card", "accept"),
    ], "the key's decisions have to reach the log one at a time, like the button's"
    assert errors == []
    page.close()


def test_a_decision_the_server_never_took_goes_back_to_pending(browser, serve):
    """The page settles a decision before the server has taken it, so the user
    sees their own click land. That optimism is only honest if a send that fails
    puts it back: a suggestion that reads as settled while the log has nothing is
    a change the next version won't carry and the user won't know to repeat."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    page.route("**/api/event", lambda route: route.abort())
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()

    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    assert page.locator("#sug-refill").get_attribute("data-lf-state") is None
    # The row is the record of a decision, so a decision that was never taken must not
    # be standing in it: both controls offering again, neither of them past tense.
    accept = page.locator("[data-lf-for='sug-refill'] .lf-sug-accept")
    reject = page.locator("[data-lf-for='sug-refill'] .lf-sug-reject")
    expect(accept).to_have_text("✓ Accept", use_inner_text=True)
    expect(reject).to_be_visible()
    assert accept.get_attribute("aria-disabled") == "false"
    # And the page's own count is derived from that, so it comes back too.
    expect(page.get_by_role("button", name="Accept all (3)")).to_be_visible()
    expect(page.locator(".lf-toast")).to_contain_text("Couldn't send")
    assert [
        e for e in interact.read_events(serve.page_dir) if e["kind"] == "action"
    ] == []

    # The retry is a second click, not a reload: the widget is pending again.
    page.unroute("**/api/event")
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    # The refused POST is the one thing the console may carry, and it is this
    # test's own doing — anything else means the page broke on the way back to
    # pending.
    assert errors == ["Failed to load resource: net::ERR_FAILED"]
    page.close()


def test_a_decision_travels_between_tabs_and_the_log_has_the_last_word(browser, serve):
    """Two windows on one page are two views of one log, not two documents. A
    decision taken in either arrives in the other by the same replay that keeps a
    reload's drag, and the record it leaves in the margin has to arrive with it: the
    tab that receives one settles it without the click that settled the tab that sent
    it, and a row still offering the press is a window disagreeing with the log about
    what has already been decided. Where the two disagree, the later entry in the log
    is what both end on."""
    url = serve(SUGGESTION_PAGE)
    first, first_errors = open_page(browser, url)
    second, second_errors = open_page(browser, url)

    # A tab that did not click has only its own poll to learn from.
    first.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    told(second)
    expect(second.locator("#sug-refill lf-old")).to_be_hidden()
    expect(second.locator("#sug-refill lf-new")).to_be_visible()
    # Nothing left to decide, and the row says which way it went — written by the
    # replay here rather than by a press, which is the only place that path is driven.
    accepted = second.locator("[data-lf-for='sug-refill'] .lf-sug-accept")
    expect(accepted).to_have_text("✓ Accepted", use_inner_text=True)
    assert accepted.get_attribute("aria-disabled") == "true"
    expect(second.locator("[data-lf-for='sug-refill'] .lf-sug-reject")).to_be_hidden()
    expect(second.get_by_role("button", name="Accept all (2)")).to_be_visible()

    # Now the race the controls make possible: a window cut off from the log still
    # shows both buttons, so the user can decide the other way there. Two
    # decisions on one change, and the log's order — not either tab's belief —
    # settles it for both once the cut-off one catches up.
    third, third_errors = open_page(browser, url)
    third.route("**/api/state", refuse)
    first.locator("[data-lf-for='sug-thistle'] .lf-sug-accept").click()
    # In the log before the reject is clicked, so which one is later is this test's
    # to decide rather than the network's.
    told(second)
    expect(second.get_by_role("button", name="Accept all (1)")).to_be_visible()
    third.locator("[data-lf-for='sug-thistle'] .lf-sug-reject").click()
    third.unroute("**/api/state")
    # The reject went out over a live channel, so every tab has to read it back —
    # the cut-off one included, which is where it stops being its own local click.
    for tab in (first, second, third):
        told(tab)
        expect(tab.locator("#sug-thistle lf-new")).to_be_hidden()
    assert first_errors == [] and second_errors == [] and third_errors == []
    for tab in (first, second, third):
        tab.close()


# Every shape the ask predicate has to tell apart, on one page: four things the page is
# waiting on the reader for, and, beneath them, one of each way of not being one. The
# four are in document order, because that is the order the walk below must take them in.
ASKS_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>asks</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="h">What is still open</h1>
<lf-options id="live-question" choose>
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
</main>
</body>
</html>
"""
ASKS_IN_ORDER = ["live-question", "sug-refill", "t-baffles", "t-bath"]


def test_the_banner_counts_what_the_page_is_still_asking(browser, serve):
    """One list, collected from what the registry declares rather than from any tag.

    The count used to be a query for `lf-suggestion:not([data-lf-state])`: perfect for
    suggestions, and silently nothing for every other thing a page waits on. What
    makes an instance an ask is now the entry's own attribute condition, and what
    makes it answered is the state x-state already declares — so this page's four are
    a question with no pick, a change nobody has decided, and the two tasks whose
    status says they are waiting.

    The rest of the page is every way of not being one, and each was a way of getting
    it wrong: a group whose pick the version already carries (`chosen`, with nothing in
    the log — a fold-only reading counts it as open on every shipped example), one the
    author has settled, one that takes no picks at all, an exhibited decision inside a
    lf-specimen, and a milestone at `blocked`, which is the same word on a widget whose
    entry does not declare it."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    asks = page.locator(".lf-asks")
    expect(asks).to_have_text("Asks (4)")
    # The blanket answer counts the same list, narrowed to the one kind that declares
    # a verb for it, so the two numbers cannot describe different sets.
    expect(page.locator(".lf-answer-all")).to_have_text("✓ Accept all (1)")

    # Answering one takes it out. A pick is state the page itself carries, so the
    # count follows the click; the suggestion's outcome is in the log alone, so that
    # one follows the round trip.
    page.locator("#lq-token").click()
    expect(asks).to_have_text("Asks (3)")
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(asks).to_have_text("Asks (2)")
    expect(page.locator(".lf-answer-all")).to_be_hidden()

    # And clearing the pick asks again: an empty answer is no answer, which only a
    # reading of what the page carries can say.
    page.locator("#lq-token").click()
    expect(asks).to_have_text("Asks (3)")
    assert errors == []
    page.close()


def test_a_key_walks_the_page_s_open_asks(browser, serve):
    """j/k step the open threads; `a` steps the things the page is asking, and the
    two lists are the same kind of thing to walk. It wraps rather than clamping,
    because an ask leaves the list as soon as it is answered — forward is the
    direction with somewhere to go, and one key that stopped at the last one would
    strand the reader there.

    The landing is marked on the ask and focused on the control that answers it, so
    the reader can see what they were brought to and Tab straight into working it —
    which is also the only landing available on a suggestion, whose element is
    display: contents and can hold no focus of its own."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    walked = []
    for _ in range(len(ASKS_IN_ORDER) + 1):  # one press past the end: it wraps
        page.keyboard.press("a")
        # Exactly one, so the mark says where this press put them rather than where an
        # earlier one did — and asserting it is also the wait for this press to land.
        expect(page.locator("[data-lf-ask]")).to_have_count(1)
        walked.append(
            page.evaluate(
                "() => [document.querySelector('[data-lf-ask]').id,"
                "       document.activeElement.tagName.toLowerCase()"
                "       + ' ' + document.activeElement.className]"
            )
        )
    assert walked == [
        ["live-question", "span lf-pick lf-ui"],  # the question: its first pick mark
        ["sug-refill", "span lf-pill lf-sug-accept lf-ui"],  # ✓ Accept, in the margin
        ["t-baffles", "lf-task "],  # a task holds no control, so it takes focus itself
        ["t-bath", "lf-task "],
        ["live-question", "span lf-pick lf-ui"],
    ], f"the walk landed somewhere else: {walked}"

    # The overlay and the key line offer it because there is something to reach.
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_contain_text("waiting on you for")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-keyline")).to_contain_text("asks")

    # An answered ask leaves the walk: from the question, the next press used to reach
    # the suggestion and now reaches what follows it.
    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(page.locator(".lf-asks")).to_have_text("Asks (3)")
    page.keyboard.press("a")
    expect(page.locator("#t-baffles")).to_be_focused()
    assert errors == []
    page.close()


# One target of ordinary height and one taller than any viewport, both far enough down
# that arriving at either is a real scroll.
TRAVEL_PAGE = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>travel</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_travelling_to_an_element_lands_where_it_was_aimed(browser, serve):
    """Clicking a quoteless thread's § label brings its element to the middle — the
    one promise every caller of that travel makes, the `a` key's landing included.

    It was 27px short of the middle in every one of them, and invisibly so: the
    scroller declares `scroll-padding-top` to keep a native fragment jump clear of
    the banner, and scrollIntoView's own "center" measures against the padded box
    rather than the viewport. So the arithmetic is the painted-range branch's, which
    never went through scrollIntoView and never drifted.

    A section taller than the viewport is the case centring cannot serve at all:
    put its middle in the middle and the heading the reader was sent to is above
    the top edge. It takes the banner clearance instead — read from the same
    declaration, so the number lives in one place — and the reader starts at the
    start."""
    url = serve(TRAVEL_PAGE)
    thread = {
        section: interact.append_event(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "version": 1,
                "text": f"About {section}.",
                "anchor": {"section": section},
            },
        )["id"]
        for section in ("flow", "long-part")
    }
    page, errors = open_page(browser, url)
    page.get_by_role("button", name="Comments", exact=False).click()
    quote = lambda section: page.locator(
        f'.lf-thread[data-id="{thread[section]}"] .lf-quote'
    )

    # Centred: the destination the travel computed, which a glide toward it passes
    # through no earlier position that could be mistaken for.
    quote("flow").click()
    page.wait_for_function(
        """() => { const r = document.getElementById('flow').getBoundingClientRect();
                   return r.height > 0
                       && Math.abs(r.top + r.height / 2 - innerHeight / 2) < 2; }"""
    )

    quote("long-part").click()
    page.wait_for_function(
        """() => { const r = document.getElementById('long-part').getBoundingClientRect();
                   const clear = parseFloat(getComputedStyle(document.body).scrollPaddingTop);
                   return r.height > innerHeight && Math.abs(r.top - clear) < 2; }"""
    )
    assert errors == []
    page.close()


def test_an_ask_joins_the_walk_by_being_declared(browser, serve):
    """The list is never closed, and this is the test of it: a widget core has never
    heard of joins the count, the walk and the overlay by its registry entry alone,
    and the one that carried the whole feature leaves by losing its own.

    Driven by rewriting the page's vendored registry, because that is exactly what a
    project layer does — a page can add a widget to its own vocabulary, and nothing in
    the runtime, the banner or the key may need teaching about it."""
    url = serve(ASKS_PAGE)
    registry = json.loads((serve.page_dir / "registry.json").read_text())
    registry["lf-milestone"]["x-awaits"] = {"when": {"status": ["active", "blocked"]}}
    del registry["lf-suggestion"]["x-awaits"]
    (serve.page_dir / "registry.json").write_text(json.dumps(registry))

    page, errors = open_page(browser, url)
    # Four, minus the suggestion that stopped declaring, plus the two milestones that
    # started — and no code anywhere knows any of those three tags.
    expect(page.locator(".lf-asks")).to_have_text("Asks (5)")
    # The blanket answer went with the declaration that named its verb.
    expect(page.locator(".lf-answer-all")).to_have_count(0)
    for expected in ["live-question", "t-baffles", "t-bath", "m-build", "m-install"]:
        page.keyboard.press("a")
        expect(page.locator(f"#{expected}")).to_have_attribute("data-lf-ask", "1")
    assert errors == []
    page.close()


# One parent over two leaves, so a status report has to move both the marker and
# the parent's computed done-fraction — the state a stylesheet cannot recount.
REPORT_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>reports</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="h">The feeders</h1>
<lf-tasks id="plan">
  <lf-task id="t-feeders" status="active" owner="wren"><strong>Rebuild the feeders</strong>
    <lf-task id="t-mounts" status="done"><strong>Replace the mounts</strong></lf-task>
    <lf-task id="t-parser" status="active"><strong>Fit squirrel baffles</strong></lf-task>
  </lf-task>
</lf-tasks>
</main>
</body>
</html>
"""


def test_a_workers_report_paints_live_and_ends_at_the_version_that_answers_it(
    browser, serve
):
    """The agent channel, end to end in the browser: a `leaf report` reaches
    the open page on the next poll and paints as provisional news — the status
    attribute moves, the parent's done-fraction recounts, the element wears
    data-lf-reported rather than the user's pending mark, and a task reported
    into `review` joins the asks the banner counts. Then the version that
    answers the report by id takes the page back: replay skips a report the
    note named, so the overruling version's own state is what renders, with no
    provisional mark left on it. Last, the diff against the base version reads
    the base's state as the reader saw it — report included — so the overrule
    marks as a change even though the two files spell the same status."""
    url = serve(REPORT_PAGE)
    d = serve.page_dir
    page, errors = open_page(browser, url)
    fraction = page.locator("#t-feeders > .lf-chips")
    expect(fraction).to_contain_text("1/2 done")
    expect(page.locator(".lf-asks")).to_be_hidden()  # nothing waits on the reader

    sent = CliRunner().invoke(
        interact.cli, ["report", str(d), "t-parser", "status", "status=review"]
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    task = page.locator("#t-parser")
    expect(task).to_have_attribute("status", "review")
    expect(task).to_have_attribute("data-lf-reported", "1")
    expect(task).not_to_have_attribute("data-lf-pending", "1")
    # The marker is paint, so the word beside it (x-paints) has to move with the
    # attribute or a reader listening is told what the page said a poll ago.
    assert "review" in task.aria_snapshot()
    # A task at review is a standing ask however the status got there.
    expect(page.locator(".lf-asks")).to_have_text("Asks (1)")

    # A second report supersedes the first — absolute values fold — and the
    # fraction chip recounts across the tree.
    sent = CliRunner().invoke(
        interact.cli, ["report", str(d), "t-parser", "status", "status=done"]
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    expect(task).to_have_attribute("status", "done")
    said = task.aria_snapshot()
    assert "done" in said and "review" not in said, said
    expect(fraction).to_contain_text("2/2 done")
    expect(page.locator(".lf-asks")).to_be_hidden()

    # The overruling version: its markup keeps `active` and names the reports on
    # the note (publish resolves the ids from `overruled`), so replay stops them
    # and the document speaks again.
    (d / "versions" / "v2.html").write_text(
        REPORT_PAGE.replace(
            '<lf-task id="t-parser" status="active">',
            '<lf-task id="t-parser" status="active" overruled>',
        )
    )
    published = CliRunner().invoke(
        interact.cli,
        ["version", "publish", str(d), "--version", "2", "--text", "not done yet"],
    )
    assert published.exit_code == 0, published.output
    assert len(interact.read_events(d)[-1]["reports"]) == 2
    page.wait_for_url("**/versions/v2.html")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    task = page.locator("#t-parser")
    expect(task).to_have_attribute("status", "active")
    expect(task).not_to_have_attribute("data-lf-reported", "1")
    expect(page.locator("#t-feeders > .lf-chips")).to_contain_text("1/2 done")

    # The diff's state half, mirror-image: v1's markup also said `active`, but
    # the reader last saw v1 wearing the report's `done`, so the overrule is a
    # change since the base — the report-layered base facet is what says so.
    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map(e => e.id)"
    ) == ["t-parser"]
    assert errors == []
    page.close()


def test_render_reports_markup_the_log_replays_over(browser, serve):
    """The static gate refuses a version that rewords what a decision rests on,
    but `chosen`, a card's column, and their kind say nothing a text diff can
    see — a version asserting them against the log used to lose silently, replay
    painting the user's state back over the author's intent. The render gate
    reports exactly that: an id the author changed since the previous version
    and replay then wrote. Silence (carrying the old markup forward) and honor
    (authoring the decided state) both stay clean, because silence changes no
    id and honor makes the replay a no-op."""
    url = serve(REPLAYED_PAGE)
    d = serve.page_dir
    for widget, action, detail in [
        ("approach", "choose", {"options": ["opt-shim"]}),
        ("work", "move", {"card": "card-importer", "to": "col-done", "index": 0}),
    ]:
        interact.append_event(
            d,
            {
                "kind": "action",
                "author": "user",
                "version": 1,
                "widget": widget,
                "action": action,
                "detail": detail,
            },
        )

    def publish(n, html):
        (d / "versions" / f"v{n}.html").write_text(html)
        interact.append_event(
            d, {"kind": "note", "author": "claude", "version": n, "text": "t"}
        )
        return url.replace("v1.html", f"v{n}.html")

    # v2 says nothing about either decision; both stand, and nothing is reported.
    assert interact.render_version(browser, publish(2, REPLAYED_PAGE)) == []

    # v3 honors both: the pick authored, the card in its dragged-to column.
    honored = REPLAYED_PAGE.replace('id="opt-shim"', 'id="opt-shim" chosen')
    honored = honored.replace(IMPORTER_CARD, "").replace(
        'label="Done">', f'label="Done">{IMPORTER_CARD}'
    )
    assert interact.render_version(browser, publish(3, honored)) == []

    # v4 asserts the other option and re-authors the card into Doing: both
    # widgets changed since v3 and replay overrides both — the author must hear.
    contradicted = REPLAYED_PAGE.replace('id="opt-stage"', 'id="opt-stage" chosen')
    failures = interact.render_version(browser, publish(4, contradicted))
    assert len(failures) == 2, failures
    assert any("id=approach" in f and "opt-stage" in f for f in failures), failures
    assert any("id=work" in f and "card-importer" in f for f in failures), failures


def test_replay_signatures_distinguish_widget_state_from_runtime_paint(browser, serve):
    """A widget may use the runtime's namespace for state without making that state
    runtime paint. Replaying a suggestion changes only data-lf-state on its authored
    element, so the replay record must name it; data-lf-pending on the same element is
    the runtime's own annotation and must not change the signature."""
    url = serve(SUGGESTION_PAGE)
    interact.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "sug-refill",
            "action": "accept",
            "detail": {},
        },
    )
    page, errors = open_page(browser, url)
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "accept")
    page.wait_for_function(
        "() => (document.body.dataset.lfReplayWrote ?? '').split(' ').includes('sug-refill')"
    )

    signatures = page.evaluate("""async () => {
        const { shallowSigs } = await import("/leaf.js");
        const widget = document.getElementById("sug-refill");
        const read = () => shallowSigs(document.body).get(widget.id);
        const decided = read();
        widget.setAttribute("data-lf-pending", "probe");
        const painted = read();
        widget.removeAttribute("data-lf-state");
        const undecided = read();
        return { decided, painted, undecided };
    }""")
    assert signatures["decided"] == signatures["painted"], (
        "runtime-owned pending paint became authored state in the replay signature"
    )
    assert signatures["decided"] != signatures["undecided"], (
        "widget-owned data-lf-state disappeared with the runtime's private attributes"
    )
    assert errors == []
    page.close()


def test_a_moved_card_wears_its_pending_state_until_honored(browser, serve):
    """A move outlives its toast: the card the user moved stays visibly
    marked as recorded-but-unwritten and its grip says so, in the tab that moved
    it and in a fresh replay alike, because the runtime compares the page's state
    against the version's own snapshot rather than remembering who wrote what.
    The card the move displaced stays unmarked — the log named one card, not its
    neighbours. The honoring version says the state itself, so on it the
    disagreement and both renderings are gone."""
    url = serve(REPLAYED_PAGE)
    page, errors = open_page(browser, url)

    # The keyboard gesture takes the same #send path as a drag. The sender's own
    # replay is a no-op, which is exactly the case the version snapshot covers.
    page.get_by_role("button", name="Move: Wire the importer — Doing").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    expect(page.locator("#card-importer")).to_have_attribute("data-lf-pending", "1")
    expect(page.locator("#card-notes")).not_to_have_attribute("data-lf-pending", "1")
    expect(
        page.get_by_role(
            "button",
            name="Move: Wire the importer — Done — awaiting next version",
            exact=True,
        )
    ).to_be_visible()

    # A fresh tab reads the same fact from replay alone, and paints both its
    # visible outline and its durable spoken state.
    second, second_errors = open_page(browser, url)
    expect(second.locator("#card-importer")).to_have_attribute("data-lf-pending", "1")
    expect(
        second.get_by_role(
            "button",
            name="Move: Wire the importer — Done — awaiting next version",
            exact=True,
        )
    ).to_be_visible()
    assert (
        second.locator("#card-importer").evaluate(
            "el => getComputedStyle(el).outlineStyle"
        )
        == "solid"
    )

    # The honoring version authors the card where the user put it; replay
    # no-ops against it and the mark has nothing left to say.
    d = serve.page_dir
    honored = REPLAYED_PAGE.replace(IMPORTER_CARD, "").replace(
        'label="Done">', f'label="Done">{IMPORTER_CARD}'
    )
    (d / "versions" / "v2.html").write_text(honored)
    interact.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "t"}
    )
    third, third_errors = open_page(browser, url.replace("v1.html", "v2.html"))
    expect(third.locator("#col-done #card-importer")).to_be_visible()
    # Absence only counts once replay has decided every action.
    third.wait_for_function("() => document.body.dataset.lfApplied === '1'")
    expect(third.locator("#card-importer")).not_to_have_attribute(
        "data-lf-pending", "1"
    )
    expect(
        third.get_by_role("button", name="Move: Wire the importer — Done", exact=True)
    ).to_be_visible()

    assert errors == [] and second_errors == [] and third_errors == []
    for tab in (page, second, third):
        tab.close()


def test_a_pending_suggestion_can_be_discussed_instead_of_decided(browser, serve):
    """✓ and ✗ are the visible affordances, but a proposal a user half-agrees
    with wants a sentence, not a verdict: the proposed words are ordinary page
    text, so selecting them and commenting works like anywhere else. Then the
    decision they eventually take has to reach the thread — rejecting retires the
    text the comment was made on, and a comment pointing into markup nobody can
    see has to read as detached rather than as a live mark that jumps nowhere."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    page.evaluate("""() => {
        const r = document.createRange();
        r.selectNodeContents(document.querySelector('#sug-refill lf-new'));
        getSelection().removeAllRanges();
        getSelection().addRange(r);
        document.body.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
    }""")
    page.wait_for_selector(".lf-fab", state="visible")
    page.locator(".lf-fab").click()
    page.wait_for_selector(".lf-composer", state="visible")
    quoted = composer_quote(page)["text"]
    assert quoted.strip("“”") == "Refill a feeder when its camera shows it half-empty."
    page.locator(".lf-composer textarea").fill("Half-empty by whose reading?")
    page.locator(".lf-composer").get_by_role("button", name="Comment").click()

    thread = page.locator(".lf-thread .lf-quote").first
    expect(thread).to_be_visible()
    expect(thread).not_to_have_class(re.compile(r"\bdetached\b"))
    assert (
        painted(page, "lf-mark")
        == "Refill a feeder when its camera shows it half-empty."
    )

    page.locator("[data-lf-for='sug-refill'] .lf-sug-reject").click()
    expect(thread).to_have_class(re.compile(r"\bdetached\b"))
    assert painted(page, "lf-mark") == "", (
        "a mark stayed painted on text the user's own decision removed"
    )
    assert errors == []
    page.close()


def test_a_decision_already_in_the_log_retires_its_slot_at_load(browser, serve):
    """The test above takes the decision in front of the user, on a page that has
    been up long enough for everything to have arrived. Here the log holds it before
    the page opens, which is what puts the anchor pass's skip list on the clock: the
    registry names the slot a decision retires (x-retired-when), and the registry
    arrives over the network, after the module that reads it has evaluated. Replay
    settles the suggestion on the first poll, so the pass that runs with it has to be
    skipping lf-old already — or the page opens with a live mark on words the user
    accepted away."""
    url = serve(
        SUGGESTION_PAGE, anchored=[("replace", "Refill every feeder each morning.")]
    )
    interact.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "sug-refill",
            "action": "accept",
            "detail": {},
        },
    )
    page, errors = open_page(browser, url)
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    expect(page.locator(".lf-thread .lf-quote").first).to_have_class(
        re.compile(r"\bdetached\b")
    )
    assert painted(page, "lf-mark") == "", (
        "the first pass anchored inside a slot the user's decision had retired"
    )
    assert errors == []
    page.close()


# A suggestion whose losing slot holds a widget. lf-old takes prose, and prose takes
# widgets, so the mark on a chosen option can sit inside the half a decision removes.
# `choose`, because that is the shape that bites: a group offering a pick renders the
# mark as a press, which wears the chrome class *and* declares its word the page's.
RETIRED_WIDGET_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>retired</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_a_label_in_a_retired_slot_leaves_the_page_with_the_slot(browser, serve):
    """A decided suggestion's losing slot is off the page, and a label inside it goes
    too. The label is the one thing that reads back over chrome — a pick mark says
    "chosen" and declares those words the page's, which is what lets a user point at
    it anywhere else — so the rule has to stop at the slot: a marker that outranks a look
    must not outrank a decision, or a quote lands in the half the user removed."""
    url = serve(RETIRED_WIDGET_PAGE, anchored=[("sug-swap", "chosen")])
    interact.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "sug-swap",
            "action": "accept",
            "detail": {},
        },
    )
    page, errors = open_page(browser, url)
    expect(page.locator("#sug-swap lf-old")).to_be_hidden()
    assert (
        page.locator("#old-lax .lf-pick").evaluate("el => el.textContent") == "chosen"
    ), "fixture is not exercising the case — the mark the slot hides never rendered"
    expect(page.locator(".lf-thread .lf-quote").first).to_have_class(
        re.compile(r"\bdetached\b")
    )
    assert painted(page, "lf-mark") == "", (
        "a quote matched inside the half the user accepted away, because the "
        "label there declared itself the page speaking"
    )
    assert errors == []
    page.close()


def test_a_decision_that_empties_its_widget_detaches_the_element_anchor(browser, serve):
    """An element anchor asks whether its section is still on the user's page,
    and for a suggestion that settles to nothing — an insertion refused — the
    markup's presence is the wrong answer: the thread read as attached while its
    outline drew nothing. Pending, the wrapper is a thing to point at; refused, the
    thread detaches like any passage the decision removed."""
    url = serve(SUGGESTION_PAGE)
    interact.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "version": 1,
            "text": "Is thistle worth a feeder?",
            "anchor": {"section": "sug-thistle"},
        },
    )
    page, errors = open_page(browser, url)
    thread = page.locator(".lf-thread .lf-quote").first
    expect(thread).not_to_have_class(re.compile(r"\bdetached\b"))
    expect(page.locator("#sug-thistle")).to_have_class(re.compile(r"\blf-mark-el\b"))

    page.locator("[data-lf-for='sug-thistle'] .lf-sug-reject").click()
    expect(thread).to_have_class(re.compile(r"\bdetached\b"))
    expect(page.locator("#sug-thistle")).not_to_have_class(
        re.compile(r"\blf-mark-el\b")
    )
    assert errors == []
    page.close()


MARKDOWN_REPLY = """Two things, then the fix — details in https://example.com/notes:

- the poll drops a response **behind** the one already rendered
- `lastEventSeq` is what it compares, a Vec<T> of them

```python
def resolve(a, b):
    return a if a.seq > b.seq else b
```

> which one wins?
"""


def test_a_reply_renders_the_markdown_it_was_written_in(browser, serve):
    """A message's text is Markdown, rendered here by the page's own vendored layer —
    the wire carries the log's words and nothing else. Every raw tag renders as the
    characters it was written in: prose says Vec<T>, and swallowing it into an element
    would lose the words in front of the user with nothing saying so. What the
    panel adds is the page's own dress: the theme's element rules are at document level
    and reach in, a fenced block colors from the tokenizer a version's <pre><code>
    uses, and a bare URL arrives as the link the user will want to follow."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    interact.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-ask",
            "author": "user",
            "version": 1,
            "text": "which one wins?",
        },
    )
    interact.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-ask",
            "version": 1,
            "text": MARKDOWN_REPLY,
        },
    )
    page, errors = open_page(browser, url)
    page.get_by_role("button", name="Comments", exact=False).click()
    body = page.locator(".lf-msg.claude .lf-msg-body")
    expect(body.locator("li")).to_have_count(2)
    expect(body.locator("strong")).to_have_text("behind")
    expect(body.locator("blockquote")).to_have_text("which one wins?")
    expect(body.locator('pre code [data-lf-syn="kw"]').first).to_have_text("def")
    expect(body.locator('a[href="https://example.com/notes"]')).to_have_count(1)
    # The paragraph's asterisks are gone from the words, not merely hidden, and the
    # raw tag's characters are still among them: what the user can select is what
    # the message says.
    text = body.inner_text()
    assert "**" not in text and "Vec<T>" in text
    assert errors == []
    page.close()


REF_PAGE = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>refs</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_a_message_reference_travels_or_says_it_cant(browser, serve):
    """A message can point at the page with a fragment link, and the platform is what
    carries the reader: collapsed content wears hidden="until-found", so the jump
    fires beforematch and the tab holding the target opens itself. That half is
    pinned here rather than implemented — a runtime that starts intercepting these
    presses has to keep doing it, reveal included.

    The half the browser has no answer for is an id this version hasn't got, which
    needs nobody to have erred: a comment outlives the version it was written on.
    Unmarked it reads live, moves nothing, and leaves a fragment nobody holds in the
    URL for the next load to honor. So it wears the detached face a stranded quote
    wears and its press is refused — asserted from a real press, since that refusal
    is the whole of what the runtime does here."""
    url = serve(REF_PAGE)
    interact.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-ref",
            "author": "user",
            "version": 1,
            "text": "See [the bath](#p-bath), not [the old note](#gone).",
        },
    )
    page, errors = open_page(browser, url)
    page.get_by_role("button", name="Comments", exact=False).click()

    live = page.locator('.lf-msg-body a[href="#p-bath"]')
    expect(live).to_have_attribute("title", "Jump to § p-bath")
    # Collapsed behind the inactive tab until the jump asks for it, which is the
    # platform half: hidden="until-found" answers a fragment navigation.
    hidden = re.compile(".*")
    expect(page.locator("#tab-bath")).to_have_attribute("hidden", hidden)
    live.click()
    expect(page.locator("#tab-bath")).not_to_have_attribute("hidden", hidden)
    page.wait_for_function(
        """() => { const r = document.getElementById('p-bath').getBoundingClientRect();
                   return r.height > 0 && r.top >= 0 && r.bottom <= innerHeight; }"""
    )

    # The other half of a link: opened in its own tab it is an arrival, which the
    # browser answers before any widget has upgraded — so the runtime is what aims it
    # (landArrival). Nothing of this tab travels with it; the new one starts empty.
    # Which chord opens that tab is the platform's answer rather than one this suite
    # holds — ⌘ where it was written, ⌃ where CI runs it — so the press names the
    # gesture and lets Playwright spell it. Named outright, the Linux press opened
    # nothing at all and the wait for the tab ran its full 30s before saying so.
    with page.context.expect_page() as opened:
        live.click(modifiers=["ControlOrMeta"])
    tab = opened.value
    tab.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    tab.wait_for_function(
        """() => { const r = document.getElementById('p-bath').getBoundingClientRect();
                   return r.height > 0 && r.top >= 0 && r.bottom <= innerHeight; }"""
    )
    tab.close()

    dead = page.locator('.lf-msg-body a[href="#gone"]')
    expect(dead).to_have_class("detached")
    expect(dead).to_have_attribute("aria-disabled", "true")
    expect(dead).to_have_attribute(
        "title", "§ gone isn't in the version you're viewing"
    )
    # force, because locator.click refuses aria-disabled controls and that refusal is
    # the state under test. Nothing will happen, so there is no fact to consume: the
    # press is the edge, and the hash the browser would write is synchronous with it.
    at = page.evaluate("() => document.body.scrollTop")
    was = page.url  # the live jump left its own fragment, as a fragment jump does
    dead.click(force=True)
    assert page.url == was, page.url
    assert page.evaluate("() => document.body.scrollTop") == at
    assert errors == []
    page.close()


def test_an_arrival_lands_where_the_url_aimed(browser, serve):
    """A URL naming an element is answered once the page is done becoming itself.

    The browser answers it at parse time, when no widget has upgraded and nothing is
    collapsed yet — so the tab holding the target is still open, the document is
    still its unupgraded height, and both facts stop being true a moment later. The
    same staleness is why scroll restoration is manual; the fragment was the half of
    that takeover never written.

    Then the ranking, which is the browser's own. Arriving somewhere named is what a
    fragment is for, and the reading position this tab kept — of whatever it last
    left this page at — must not paint over it. Returning is the other way round: on
    a reload the fragment is left over from a reference followed earlier, and the
    reader's own position is the answer."""
    url = serve(REF_PAGE)
    hidden = re.compile(".*")
    onscreen = """(id) => { const r = document.getElementById(id).getBoundingClientRect();
                            return r.height > 0 && r.top >= 0 && r.bottom <= innerHeight; }"""

    # A fresh tab: nothing saved, nothing to outrank. The target is behind a tab that
    # does not exist until the upgrade runs, which is after the browser has jumped.
    page, errors = open_page(browser, f"{url}#p-bath")
    expect(page.locator("#tab-bath")).not_to_have_attribute("hidden", hidden)
    page.wait_for_function(onscreen, arg="p-bath")

    # Read to the end and leave: the position is written down on the way out and the
    # tab keeps it. Coming back at a named place is what the ranking is for — that
    # position is real and recent, and still not what this URL asked for.
    page.evaluate("() => document.body.scrollTo({top: 1e6, behavior: 'instant'})")
    page.goto("about:blank")
    page.goto(f"{url}#p-bath")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    page.wait_for_function(onscreen, arg="p-bath")

    # The reader moves on, so the fragment is stale by the reload that carries it. The
    # bath tab stays open across that reload and says nothing about this — a tab
    # remembers its own panel, the same way the position is remembered here.
    page.evaluate("() => document.body.scrollTo({top: 1e6, behavior: 'instant'})")
    page.reload()
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    page.wait_for_function(onscreen, arg="tail-end")
    assert errors == []
    page.close()


def test_a_suggestion_shows_the_characters_it_proposes(browser, serve):
    """A suggestion's words are bound for the page verbatim, so the panel shows them
    as typed. Rendering them would promise the user an italic where the next
    version carries the asterisks they wrote."""
    url = serve(REPLY_HOST_PAGE)
    interact.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "s1",
            "author": "user",
            "version": 1,
            "suggestion": True,
            "text": "Retry up to *five* times.",
        },
    )
    page, errors = open_page(browser, url)
    page.get_by_role("button", name="Comments", exact=False).click()
    body = page.locator(".lf-msg-body.lf-suggest-body")
    expect(body).to_have_text("Retry up to *five* times.")
    expect(body.locator("em")).to_have_count(0)
    assert errors == []
    page.close()


def test_a_reply_widget_replays_its_action_when_the_page_loads(browser, serve):
    """A widget inside a reply exists only once the panel has rendered the log,
    which is later than everything on the page — so the replay runs at the end of
    a poll, after that render, and an action naming a widget it doesn't find is
    one no version will ever hold (an honored suggestion, whose id the honoring
    version dropped) rather than one to look for again on the next poll."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    interact.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-ask",
            "author": "user",
            "version": 1,
            "text": "Which of these?",
        },
    )
    interact.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-ask",
            "version": 1,
            "text": SPECIMEN_TEXT,
            "markup": SPECIMEN_MARKUP,
        },
    )
    interact.append_event(
        d,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "rp-live",
            "action": "choose",
            "detail": {"options": ["rp-shim"]},
        },
    )
    page, errors = open_page(browser, url)
    page.get_by_role("button", name="Comments", exact=False).click()
    expect(page.locator("#rp-shim")).to_have_attribute("chosen", "")
    assert page.locator("#rp-live lf-option[chosen]").count() == 1
    assert errors == []
    page.close()


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


def test_a_thread_question_asks_until_answered(browser, serve):
    """A question in a thread is one of the page's asks — a request to the reader
    wherever it stands — and `a` opens the panel to reach it. A single-answer group
    is answered by its pick, as on the page; a `multiple` group's toggles each
    reach the agent live, so only its Done press closes it, as an `answer` action
    the ask stands until (x-awaits.until). The thread's own reply box is the words'
    home, so the group brings no box of its own — and an armed g leader keeps its
    digits even from a mark, because the chord promised a thread."""
    url = serve(REPLY_HOST_PAGE)
    for event in THREAD_ASKS:
        interact.append_event(serve.page_dir, event)
    page, errors = open_page(browser, url)
    asks = page.locator(".lf-asks")
    expect(asks).to_have_text("Asks (2)")

    page.keyboard.press("a")
    expect(page.locator(".lf-panel")).to_be_visible()
    expect(page.locator("#tq-one .lf-pick").first).to_be_focused()
    expect(page.locator(".lf-thread .lf-say")).to_have_count(0)

    page.locator("#tq-redis").click()
    expect(asks).to_have_text("Asks (1)")

    page.locator("#tq-logs").click()
    expect(page.locator("#tq-logs")).to_have_attribute("chosen", "")
    expect(asks).to_have_text("Asks (1)")
    page.locator("#tq-set .lf-done").click()
    expect(asks).to_be_hidden()
    expect(page.locator("#tq-set")).to_have_attribute("answered", "")
    round_trip(page)
    actions = [e for e in interact.read_events(serve.page_dir) if e["kind"] == "action"]
    assert actions[-1]["widget"] == "tq-set" and actions[-1]["action"] == "answer"
    assert actions[-1]["detail"] == {}

    # The chord's promise holds from a mark: g then 1 reaches the first thread's
    # reply box, and no pick is sent for the digit.
    page.locator("#tq-one .lf-pick").first.focus()
    page.keyboard.press("g")
    page.keyboard.press("1")
    expect(page.locator(".lf-thread textarea").first).to_be_focused()
    sent = [e for e in interact.read_events(serve.page_dir) if e["kind"] == "action"]
    assert sent[-1]["action"] == "answer", "the leader's digit must not pick"
    assert errors == []
    page.close()


def test_keys_answer_a_question_from_its_marks(browser, serve):
    """From a mark — where `a` lands — ↑/↓ walk the options clamping at the ends, a
    digit picks outright, and each option wears its digit only while a mark holds
    keyboard focus, so nothing appears on a page nobody is answering."""
    page, errors = open_page(browser, serve(ASKS_PAGE))
    nums = page.locator("#live-question .lf-address")
    expect(nums.first).to_be_hidden()

    page.keyboard.press("a")
    marks = page.locator("#live-question .lf-pick")
    expect(marks.first).to_be_focused()
    expect(nums.first).to_be_visible()
    expect(nums.nth(1)).to_have_text("2")

    page.keyboard.press("ArrowDown")
    expect(marks.nth(1)).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(marks.nth(1)).to_be_focused()

    page.keyboard.press("1")
    expect(page.locator("#lq-keep")).to_have_attribute("chosen", "")
    round_trip(page)
    acts = [e for e in interact.read_events(serve.page_dir) if e["kind"] == "action"]
    assert acts[-1]["widget"] == "live-question"
    assert acts[-1]["detail"] == {"options": ["lq-keep"]}
    assert errors == []
    page.close()


ADDRESS_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>addresses</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""

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
# straight into the answer. `a` scrolls to the ask it steps to, the body is the scroller,
# and a page whose content sits on fractional pixels settles that scroll across a frame —
# so the chip's offset came back a pixel out on about half of the runs, on whichever row
# the frame happened to fall between. Nothing had moved by then except the window, which is
# the one thing this measurement is not about.
INSIDE_ITS_OPTION = """el => {
    const chip = el.getBoundingClientRect();
    const opt = el.parentElement.getBoundingClientRect();
    const pad = getComputedStyle(el.parentElement);
    const above = parseFloat(pad.paddingTop), below = parseFloat(pad.paddingBottom);
    const words = opt.y + above + (opt.height - above - below) / 2;
    return {x: chip.x - opt.x, y: chip.y - opt.y, past: chip.bottom - opt.bottom,
            level: (chip.y + chip.height / 2) - words};
}"""


def test_a_questions_digits_are_drawn_whole(browser, serve):
    """An address arrives into room its option is already holding, and lands on nothing.

    Every earlier placement borrowed that room instead, and each borrow showed. On the
    cell's outer corner the chip was half outside a group that clips itself, so no
    address the product drew had ever been whole — seven of its seventeen pixels gone,
    and in a bare-label group the first digit was a sliver.
    Out in the page margin beside the group it was whole and it was in the neighbouring
    card's prose, because a middle column's margin is another cell. Neither showed up
    as a failure: a clipped element still reports its whole box and still answers
    `to_be_visible`, and a chip drawn over words breaks no rule anybody had written.

    So the cell holds a column for it, and this asks the two questions that column
    answers — does any ancestor cut it, is it on anybody's words — in both forms,
    stepped through with the key that reaches them, since the room inside a cell is
    exactly what differed: cards padded clear of their corners, rows with none to
    spare.

    How far down the column it stands is each form's own answer, so each is asked for the
    fact it states rather than for one number covering both. A card's digit rides at the
    head of that column, beside the title rather than over it; a row's is centred on the
    row. Pinned as one 8px it was level with a 15px row, and the day the row went to the
    page's own 17px it was two pixels too high with the gate still green — because what
    the gate read was the number the theme stated, and the claim beside it, that a row's
    digit is level with its words, was checked by nothing."""
    page, errors = open_page(browser, serve(ADDRESS_PAGE))
    for options, sitting in [
        (["c-heater", "c-cable", "c-hand"], "in the corner"),
        (["r-now", "r-later"], "centred"),
    ]:
        page.keyboard.press("a")
        for id_ in options:
            chip = page.locator(f"#{id_} > .lf-address")
            expect(chip).to_be_visible()
            cut = chip.evaluate(CLIPPED_BY)
            assert cut is None, f"{id_}'s digit is cut: {cut}"
            # Never on the hairline the outer corner would have shared with the cells
            # around it: the column the option reserves starts 6px in, in both forms.
            sits = chip.evaluate(INSIDE_ITS_OPTION)
            assert round(sits["x"]) == 6, (
                f"{id_}'s digit sits {sits['x']} in from its option's left edge"
            )
            if sitting == "in the corner":
                assert round(sits["y"]) == 8, (
                    f"{id_}'s digit sits {sits['y']} down from its option's top, not in "
                    "the corner of the column its card reserves"
                )
            else:
                assert abs(sits["level"]) <= 0.5, (
                    f"{id_}'s digit is {sits['level']}px off the middle of its row's own "
                    "words"
                )
            assert sits["past"] <= 0, (
                f"{id_}'s digit hangs past its own option and onto the next"
            )
            # Asked of the words rather than of the numbers, because the numbers are
            # only right for as long as the column the theme reserves is.
            on = chip.evaluate(OVER_WORDS, id_)
            assert on is None, f"{id_}'s digit is drawn over the words “{on}”"
    assert errors == []
    page.close()


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
    element, so there is nothing for a locator to click."""
    box = page.evaluate(
        """([name, index]) => {
        const r = [...CSS.highlights.get(name)][index].getClientRects()[0];
        return {x: r.left + r.width / 2, y: r.top + r.height / 2};
    }""",
        [name, index],
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


def test_composer_marks_the_passage_instead_of_quoting_it(browser, serve):
    """The passage stays visible while its comment is written. Focus moves into the
    composer the moment it opens, which drops the browser's own selection, so the
    runtime paints the anchor itself, and repaints it after every pass that redraws
    the posted threads' marks around it — otherwise a comment arriving mid-sentence
    would leave the reader's passage stranded across stale text nodes. It comes down
    with the box, and the whole time it never touches the document.

    And because the mark says which passage the box is on, the box doesn't say it too:
    the quote inside it stays out of sight while the page is marking the passage."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)

    page.locator("#p").click(
        click_count=3
    )  # a real selection, spanning the inline tags
    page.locator(".lf-fab").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'block'"
    )

    passage = " ".join(page.locator("#p").inner_text().split())
    quote = composer_quote(page)
    assert pending_text(page) == passage, (
        f"the page marks {pending_text(page)!r}, but the composer is anchored to {quote['text']!r}"
    )
    assert not quote["shown"], (
        f"the passage is marked on the page and the composer prints it as well: {quote['text']!r}"
    )
    # Out of sight, not gone: it is what the box's description resolves to, and a screen
    # reader hears nothing from a painted mark.
    assert quote["text"] == f"“{passage}”", (
        f"the composer's description of its passage says {quote['text']!r}"
    )
    assert (
        page.evaluate(
            "() => document.querySelector('.lf-composer textarea').getAttribute('aria-describedby')"
        )
        == "lf-composer-quote"
    ), "nothing announces what the box is anchored to"
    # Carrying that description costs the node an id, which is what makes it the one piece
    # of injected chrome that could answer "which section of the document is this in" with
    # itself. The reading position rides on that answer, so a reload would scroll to the
    # comment box instead of to the page.
    assert (
        page.evaluate(
            "() => document.getElementById('lf-composer-quote')"
            ".closest('[id]:not(.lf-ui)')?.id ?? null"
        )
        is None
    ), "the composer's own quote offers itself as a landmark in the document"

    # A comment landing from elsewhere re-runs the anchor pass, which splits the text
    # nodes the painted range is pinned to. The reader is mid-sentence; their passage
    # can neither blink out nor come back covering the wrong words.
    page.request.post(
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "version": 1,
            "text": "arriving mid-sentence",
            "anchor": {"section": "p", "quote": "bold text"},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert pending_text(page) == passage, (
        "a poll landing while the composer is open disturbed the passage"
    )

    page.get_by_role("button", name="Cancel").click()
    assert pending_text(page) == "", "the highlight outlived its composer"

    # A passage with the runtime's own chrome inside it paints around the chrome, the way
    # the search reads around it — one range per segment, not one spanning the lot.
    # Across both options, so a Choose button falls in the middle of the passage rather
    # than after it — where a single range spanning the whole thing would swallow it.
    chrome = page.locator("#opts .lf-ui").first.text_content().strip()
    assert chrome, "this assertion needs the widget to have rendered chrome inside it"
    page.evaluate("""() => {
        const r = document.createRange();
        r.selectNodeContents(document.querySelector('#opts'));
        const s = getSelection(); s.removeAllRanges(); s.addRange(r);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
    }""")
    page.locator(".lf-fab").click()
    page.wait_for_function("() => CSS.highlights.get('lf-pending')")
    assert chrome not in pending_text(page), (
        f"the highlight painted the widget's own {chrome!r} control along with the passage"
    )
    page.get_by_role("button", name="Cancel").click()

    # A diagram has no text to quote, so its anchor is the element and its mark is an
    # outline. That one the anchor pass really does take down, so it has to be redrawn.
    page.locator("#fig svg").click()
    page.locator(".lf-fab").click()
    page.locator("#fig.lf-mark-el.lf-pending").wait_for()
    assert not composer_quote(page)["shown"], (
        "the outline is on the figure and the composer names its section as well"
    )
    page.request.post(
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={"kind": "comment", "version": 1, "text": "and another"},
    )
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 2")
    assert page.locator("#fig.lf-mark-el.lf-pending").count() == 1, (
        "a poll landing while the composer is open dropped the outline"
    )

    # Both classes have to go, asserted apart: leaving .lf-mark-el behind repaints the
    # figure in the posted mark's own ink, pointer cursor and all, over no thread to open.
    page.get_by_role("button", name="Cancel").click()
    assert page.locator("#fig.lf-pending").count() == 0, (
        "the outline outlived its composer"
    )
    assert page.locator("#fig.lf-mark-el").count() == 0, (
        "the figure kept a thread's outline over no thread"
    )

    # A drag across the caption ends with the click's target inside the figure, but the
    # selection is what the reader picked: the one decider ranks the quote above the
    # element anchor, so the composer carries the caption's words rather than § fig.
    cap = page.locator("#fig figcaption").bounding_box()
    y = cap["y"] + cap["height"] / 2
    select(page, (cap["x"] + 2, y), (cap["x"] + cap["width"] - 2, y))
    page.locator(".lf-fab").click()
    page.wait_for_function("() => CSS.highlights.get('lf-pending')")
    assert "specimen" in pending_text(page), (
        "the click's visual find outranked the selection the drag made"
    )
    assert page.locator("#fig.lf-pending").count() == 0, (
        "the figure got the element outline over a live selection"
    )
    page.get_by_role("button", name="Cancel").click()
    assert errors == []
    page.close()


NOTED_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>noted</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="t">Noted</h1>
<p id="p1">The first passage under discussion, with words
enough for two separate remarks to land in it.</p>
<p id="p2">A short second passage.</p>
<figure id="fig"><svg viewBox="0 0 120 40" width="120" height="40" role="img"
aria-label="specimen"><rect x="2" y="2" width="116" height="36" fill="none"
stroke="currentColor"></rect></svg><figcaption>A figure, for element anchors.</figcaption></figure>
</main>
</body>
</html>
"""


def test_a_commented_block_says_so_to_a_screen_reader(browser, serve):
    """A mark is painted, not wrapped, so it builds no accessibility node and a passage
    carrying a comment reads exactly like one that doesn't. No ARIA relation reaches a
    block that isn't focusable, so the pass says it in the one thing every screen reader
    announces — text — counting up per block, riding in on a sent comment's round trip,
    and leaving with its thread. Having put words on the page, it then has to keep them
    out of the document's own: out of a selection, out of the next quote, and out of the
    mutations a screen reader rebuilds its buffer on."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir

    def comment(anchor, text):
        return interact.append_event(
            d,
            {
                "kind": "comment",
                "author": "user",
                "version": 1,
                "text": text,
                "anchor": anchor,
            },
        )["id"]

    c1 = comment({"quote": "first passage"}, "Sharpen this.")
    c2 = comment({"quote": "two separate remarks"}, "Second thought.")
    comment({"section": "fig"}, "The figure too.")
    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Two threads on one block count up, and leave one line rather than two.
    assert "2 comments" in page.locator("#p1").aria_snapshot(), (
        "a screen reader reading the block hears nothing about the comments on it"
    )
    assert page.locator("#p1 .lf-mark-note").count() == 1, "one block, one line"
    # Hidden means hidden from the eye, not the tree: a line that paints is the runtime
    # writing visible prose into the author's paragraph.
    assert page.locator("#p1 .lf-mark-note").evaluate(
        "el => { const r = el.getBoundingClientRect(); return r.width <= 1 && r.height <= 1; }"
    ), "the hidden line is painting on screen"
    note = page.locator("#p1 .lf-mark-note")
    expect(note).to_have_role("button")
    note.focus()
    expect(note).to_be_focused()
    assert note.evaluate("el => el.getBoundingClientRect().width > 1"), (
        "the comment path stayed invisible when a keyboard reader reached it"
    )
    note.press("Enter")
    expect(page.locator(f'.lf-thread[data-id="{c1}"]')).to_be_focused()
    page.keyboard.press("j")
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()

    # Once the first thread resolves, the same control enters the next one.
    interact.append_event(d, {"kind": "resolve", "author": "user", "parent": c1})
    told(page)
    expect(note).to_have_text("1 comment")
    note.press("Enter")
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()
    # An element anchor has no text to paint, and the element it names holds the line.
    assert "1 comment" in page.locator("#fig").aria_snapshot()

    # A pass that finds nothing to change must change nothing: a screen reader rebuilds
    # its buffer on every mutation, and this pass runs on every poll. A comment on no
    # passage at all is what proves a pass ran without touching the block's count.
    page.evaluate("""() => {
        window.__churn = 0;
        new MutationObserver(rs => (window.__churn += rs.length))
            .observe(document.getElementById('p1'),
                     {childList: true, characterData: true, subtree: true});
    }""")
    comment({}, "On the page as a whole.")
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 4")
    assert page.evaluate("() => window.__churn") == 0, (
        "a poll that changed nothing still rewrote the block, so a screen reader re-reads it"
    )

    # The line belongs to the runtime, not the document: a user dragging across it
    # neither copies it nor quotes it.
    page.locator("#p1").click(click_count=3)
    assert "comment" not in page.evaluate("() => getSelection().toString()"), (
        "the hidden line came along in the user's own selection"
    )
    page.locator(".lf-fab").click()
    assert "comment" not in composer_quote(page)["text"], (
        "the hidden line came along in the quote the comment would store"
    )
    page.get_by_role("button", name="Cancel").click()

    # The gesture's own comment reaches the line once the send's round trip lands.
    box = page.locator("#p2").bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    page.locator(".lf-fab").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'block'"
    )
    page.locator(".lf-composer textarea").fill("Too short.")
    page.get_by_role("button", name="Comment", exact=True).click()
    expect(page.locator("#p2 .lf-mark-note")).to_have_count(1)
    c4 = [e for e in interact.read_events(d) if e.get("kind") == "comment"][-1]["id"]

    # A resolved thread takes its line with it: the pass owns what it wrote.
    interact.append_event(d, {"kind": "resolve", "author": "user", "parent": c4})
    told(page)
    expect(page.locator("#p2 .lf-mark-note")).to_have_count(0)
    assert "1 comment" in page.locator("#p1").aria_snapshot()

    # A passage crossing two blocks says so in both: a reader landing on either block
    # hears about the comment, the way the paint reaches both.
    comment({"quote": "to land in it. A short second"}, "Crosses the boundary.")
    told(page)
    expect(page.locator("#p2 .lf-mark-note")).to_have_count(1)
    assert "2 comments" in page.locator("#p1").aria_snapshot()
    assert "1 comment" in page.locator("#p2").aria_snapshot()
    assert errors == []
    page.close()


def test_the_leader_key_addresses_reply_boxes(browser, serve):
    """A reply box's send shortcut is focus-scoped, so only the focused box claims it:
    unfocused, the placeholder carries the box's own address — g plus the digit the
    armed window paints on the box as a chip — and that sequence reaches the box from
    anywhere outside a typing context. Inside one, g and digits are just letters; a
    non-digit after g disarms the leader and keeps its ordinary meaning."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir

    def comment(anchor, text):
        return interact.append_event(
            d,
            {
                "kind": "comment",
                "author": "user",
                "version": 1,
                "text": text,
                "anchor": anchor,
            },
        )["id"]

    c1 = comment({"quote": "first passage"}, "Sharpen this.")
    c2 = comment({"quote": "two separate remarks"}, "Second thought.")
    c3 = comment({"section": "fig"}, "The figure too.")
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 3")

    # g then a digit lands in that thread's reply box, opening the panel on the way.
    page.keyboard.press("g")
    page.keyboard.press("2")
    ta2 = page.locator(f'.lf-thread[data-id="{c2}"] textarea')
    expect(ta2).to_be_focused()
    # The focused box claims the send keys; an unfocused one its own address, which
    # the armed window paints on the box as a chip.
    expect(ta2).to_have_attribute("placeholder", re.compile(r"Reply · (⌘⏎|Ctrl\+⏎)$"))
    ta1 = page.locator(f'.lf-thread[data-id="{c1}"] textarea')
    expect(ta1).to_have_attribute("placeholder", "Reply · g 1")
    expect(
        page.locator(f'.lf-thread[data-id="{c1}"] .lf-compose > .lf-address')
    ).to_have_text("1")

    # A digit with no leader is nothing: Esc backs out to the thread, and 3 stays put.
    page.keyboard.press("Escape")
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()
    page.keyboard.press("3")
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()

    # The chip is the armed window's paint, worn on the box the digit lands in:
    # hidden at rest (the placeholder speaks the standing address), visible while
    # armed, gone when Esc takes the window down.
    chip1 = page.locator(f'.lf-thread[data-id="{c1}"] .lf-compose > .lf-address')
    expect(chip1).to_be_hidden()
    page.keyboard.press("g")
    expect(chip1).to_be_visible()
    page.keyboard.press("Escape")
    expect(chip1).to_be_hidden()
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()

    # A non-digit disarms the leader and keeps its ordinary meaning: g j is a thread step.
    page.keyboard.press("g")
    page.keyboard.press("j")
    expect(page.locator(f'.lf-thread[data-id="{c3}"]')).to_be_focused()

    # Typing contexts are untouched: in a box, g and 1 are text, and focus stays put.
    page.keyboard.press("Enter")
    ta3 = page.locator(f'.lf-thread[data-id="{c3}"] textarea')
    expect(ta3).to_be_focused()
    page.keyboard.type("g1")
    expect(ta3).to_have_value("g1")
    expect(ta3).to_be_focused()
    assert errors == []
    page.close()


def test_the_key_line_says_what_a_press_will_do(browser, serve):
    """The key line renders the same scene() escapeKey() runs, so what Esc promises
    is what Esc then does, rung by rung: general box → the list → the panel closed.
    And the armed chord is on screen with the panel closed — where the old corner
    badges, display:none inside it, said nothing at all."""
    url = serve(NOTED_PAGE)
    interact.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "version": 1,
            "text": "One thread.",
            "anchor": {"quote": "first passage"},
        },
    )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")
    line = page.locator(".lf-keyline")

    # Page scope: the standing verbs, thread rows only over threads, and no esc
    # chip — there is nothing to back out of.
    expect(line).to_contain_text("comment")
    expect(line).to_contain_text("threads")
    expect(line).to_contain_text("keys")
    expect(line).not_to_contain_text("esc")

    # Armed with the panel closed: the pending chord and its way out are on screen,
    # and the digit chip counts the one thread there is rather than promising nine.
    page.keyboard.press("g")
    expect(line).to_contain_text("reply to thread")
    expect(line).to_contain_text("1")
    expect(line).not_to_contain_text("1–9")
    expect(line).to_contain_text("cancel")
    page.keyboard.press("Escape")
    expect(line).not_to_contain_text("reply to thread")

    # c opens the panel into the general box: the line says send, and where Esc goes.
    page.keyboard.press("c")
    expect(line).to_contain_text("send")
    expect(line).to_contain_text("back to list")
    # A send key on an empty box is answered, not swallowed — silence reads as a
    # send that happened.
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator(".lf-toast")).to_contain_text("Nothing to send")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(line).to_contain_text("close comments")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()
    expect(line).not_to_contain_text("close comments")
    # Focus doesn't fall to body: it lands on the control that reopens the panel.
    expect(page.locator(".lf-comments")).to_be_focused()

    # The fast rung: j reopens onto a thread, and Esc from it is one press out.
    # Every rung earns a press here because Esc is the only keyboard collapse.
    page.keyboard.press("j")
    expect(page.locator(".lf-thread")).to_be_focused()
    expect(line).to_contain_text("close comments")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()
    assert errors == []
    page.close()


def test_c_reaches_the_general_box_while_the_panel_stands_open(browser, serve):
    """c goes to the general box from any state. It doubled as the panel's
    collapse once, which left the box with no shortcut exactly while the panel
    stood open: the press that promised "comment" answered "close".
    Collapse is the ladder's — Esc from the list closes the panel, the rung the
    key-line test walks — so both stay reachable without one key meaning two
    things."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    page.keyboard.press("c")  # closed: opens the panel into the box
    expect(page.locator(".lf-general textarea")).to_be_focused()
    page.keyboard.press("Escape")  # back out to the list, focus outside any box
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("c")  # open: still the box, never the collapse
    expect(page.locator(".lf-general textarea")).to_be_focused()
    expect(page.locator(".lf-panel")).to_have_class(re.compile("open"))
    assert errors == []
    page.close()


def test_escape_backs_out_from_a_control_nothing_is_typed_into(browser, serve):
    """Letters stand down on any editable — a select's letters jump its options —
    but the ladder asks what the press would take from the control, and only
    typed text has an Escape of its own. The banner's version chooser swallowed
    the rung, so the panel could not be closed by key right after the user worked
    it; the fix's first attempt was a two-item denylist, which an authored slider
    walked straight past. The chooser is a button now and no longer editable at
    all, so what holds the rule is the page's own controls — which is where it
    always mattered, a page being free to author any of them."""
    html = NOTED_PAGE.replace(
        "</main>",
        '<input id="zoom" type="range">'
        '<select id="pick"><option>one</option><option>two</option></select></main>',
    )
    page, errors = open_page(browser, serve(html))
    # The mouse opens between rounds because c is shadowed on the very controls
    # under test: their letters are the control's own.
    for control in ("#zoom", "#pick"):
        page.get_by_role("button", name=re.compile("^Comments")).click()
        expect(page.locator(".lf-panel")).to_be_visible()
        page.locator(control).focus()
        expect(page.locator(".lf-keyline")).to_contain_text("close comments")
        page.keyboard.press("Escape")
        expect(page.locator(".lf-panel")).to_be_hidden()
    assert errors == []
    page.close()


# c's three destinations on one page: prose to select, a visual to click (no words to
# quote, so it anchors on the element), and the page itself with neither in hand.
TARGETS_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>targets</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="t">Targets</h1>
<p id="prose">A paragraph with enough words in it to select by dragging across, which
is what raises the button the key then presses.</p>
<figure id="fig"><svg viewBox="0 0 240 60" width="240" height="60" role="img"
aria-label="specimen"><rect x="2" y="2" width="236" height="56" fill="none"
stroke="currentColor"></rect></svg><figcaption>A specimen.</figcaption></figure>
</main>
</body>
</html>
"""


def test_the_key_line_names_what_this_press_will_comment_on(browser, serve, other_leaf):
    """A key's word is the meaning it has now, not one wide enough to cover every
    meaning it could have. c opens a box on the selection, on the item a click raised
    the 💬 on, or on the page, and all three read "comment" — true of the key and
    silent about the press, so a reader with a paragraph selected and one with nothing
    selected were told the same thing about two different boxes. Both surfaces read the
    row where they paint it, so both say which box this press opens; o is the same
    defect and says show or hide rather than both."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    line = page.locator(".lf-keyline")
    help_el = page.locator(".lf-help")

    # Nothing in hand: the box c opens is the page's.
    expect(line).to_contain_text("comment on the page")
    page.keyboard.press("?")
    expect(help_el).to_contain_text("Comment on the page")
    page.keyboard.press("Escape")

    # A selection under the hand moves the word, on the gesture that raises the button
    # — the anchor the line names and the one the press takes are the same one. Dragged
    # rather than select_text()'d, which sets the selection through the injected script
    # and fires neither mouseup nor keyup: the button would never rise, and the press
    # under test would be answered by a state no gesture produced.
    box = page.locator("#prose").bounding_box()
    select(
        page,
        (box["x"] + 1, box["y"] + 4),
        (box["x"] + box["width"] - 1, box["y"] + box["height"] - 4),
        steps=12,
    )
    expect(page.locator(".lf-fab")).to_be_visible()
    expect(line).to_contain_text("comment on the selection")
    page.keyboard.press("?")
    expect(help_el).to_contain_text("Comment on the selection")
    page.keyboard.press("Escape")
    # And the press does what the word said: a composer carrying that passage, which
    # is what makes the suggestion row (a replacement for quoted words) offered at all.
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer .lf-suggest-row")).to_be_visible()
    page.keyboard.press("Escape")

    # A visual has no words to quote, so the press lands on the element — and the word
    # is the item's own, the way the panel names one.
    page.locator("#fig svg").click()
    expect(line).to_contain_text("comment on the figure")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer .lf-suggest-row")).to_be_hidden()
    page.keyboard.press("Escape")

    # o names the direction of its own toggle. Opened from the banner, because opening
    # it by key lands focus inside the board, and the line is then the board's own scope
    # rather than the page's — the o row is only on screen while the page's is.
    expect(line).to_contain_text("show leaves")
    page.get_by_role("button", name=re.compile("^All leaves")).click()
    expect(page.locator(".lf-others-panel")).to_have_class(re.compile("open"))
    expect(line).to_contain_text("hide leaves")
    page.keyboard.press("o")
    expect(page.locator(".lf-others-panel")).not_to_have_class(re.compile("open"))
    expect(line).to_contain_text("show leaves")
    assert errors == []
    page.close()


def test_a_key_on_screen_is_a_key_that_works(browser, serve):
    """Every surface naming a key promises the press does something now. One table
    kept the words from drifting and not the surfaces: the key line asked `when`,
    the ? overlay didn't, and two shortcuts held their liveness where no surface
    could ask — the diff in its own run, the version pair in stepVersion — so the
    overlay offered g 1–9 with no thread to reply to, and the diff on a first version
    with nothing to diff. Liveness is one declaration, and the dispatcher, the line,
    and the overlay all ask it."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir
    page, errors = open_page(browser, url)
    help_el = page.locator(".lf-help")

    # No open threads, one version: the reference names only what a press would do.
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    # Nothing is selected, so c's own row says the box it would open — the word is the
    # press's, not the key's (see the row's neighbour test below).
    expect(help_el).to_contain_text("Comment on the page")
    expect(help_el).not_to_contain_text("Reply to the nth")
    expect(help_el).not_to_contain_text("Next / previous open thread")
    expect(help_el).not_to_contain_text("On a focused thread")
    expect(help_el).not_to_contain_text("Older / newer version")
    expect(help_el).not_to_contain_text("Highlight changes")
    expect(help_el).not_to_contain_text("waiting on you for")
    # The chooser is the one version key a first version has: its menu holds this
    # version and what it changed, where the pair that steps between versions has
    # nowhere to go and the menu's own keys have nothing to walk.
    expect(help_el).to_contain_text("The versions, and what each one changed")
    expect(help_el).not_to_contain_text("In the versions menu")
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()

    # The dispatcher asks the same declaration: k used to open an empty panel
    # while j, when-gated, did nothing.
    page.keyboard.press("j")
    page.keyboard.press("k")
    expect(page.locator(".lf-panel")).to_be_hidden()
    line = page.locator(".lf-keyline")
    expect(line).not_to_contain_text("threads")

    # Threads arrive, and the next open holds the rows they make live — the g
    # range counting the two there are, not the nine there could be.
    for text in ["A thread.", "Another."]:
        interact.append_event(
            d, {"kind": "comment", "author": "user", "version": 1, "text": text}
        )
    told(page)
    expect(page.locator(".lf-thread")).to_have_count(2)
    # The key line repaints on the same render that made them live — no focus
    # change to lean on, so the repaint is the thread render's own.
    expect(line).to_contain_text("threads")
    page.keyboard.press("?")
    expect(help_el).to_contain_text("g 1–2")
    expect(help_el).to_contain_text("Next / previous open thread")
    expect(help_el).to_contain_text("On a focused thread")
    expect(help_el).not_to_contain_text("Older / newer version")
    page.keyboard.press("Escape")

    # A v2 lands and the unpinned page follows it; on v2 the version keys are
    # live, and v has a previous version to diff against.
    (d / "versions" / "v2.html").write_text(NOTED_PAGE)
    interact.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "two"}
    )
    page.wait_for_url("**/versions/v2.html*")
    expect(page.locator('.lf-version-diff[data-lf-version="1"]')).to_have_count(1)
    page.keyboard.press("?")
    expect(help_el).to_contain_text("Older / newer version")
    expect(help_el).to_contain_text("Highlight changes since the previous version")
    expect(help_el).to_contain_text("g 1–2")
    page.keyboard.press("Escape")

    # The diff key is a toggle, and its row stays live over a standing comparison
    # precisely so the press can end one — so over a marked-up page the reference has to
    # say the half of the run this press would take, not the half that already happened.
    page.keyboard.press("=")
    expect(page.locator(".lf-version")).to_have_class(re.compile(r"\bon\b"))
    page.keyboard.press("?")
    expect(help_el).to_contain_text("Stop highlighting changes")
    expect(help_el).not_to_contain_text("Highlight changes since the previous version")
    page.keyboard.press("Escape")
    page.keyboard.press("=")
    expect(page.locator(".lf-version")).not_to_have_class(re.compile(r"\bon\b"))

    # A resolved thread stays focusable after the last open one is gone, and the
    # scene branch that restates the j/k row over it asks the same liveness.
    page.keyboard.press("c")
    for n in [1, 2]:
        page.locator(".lf-threads > .lf-thread").first.get_by_role(
            "button", name="Resolve"
        ).click()
        expect(page.locator(".lf-details summary")).to_have_text(f"Resolved ({n})")
    page.locator(".lf-details summary").click()
    resolved = page.locator(".lf-details .lf-thread").first
    resolved.click()
    expect(resolved).to_be_focused()
    expect(line).to_contain_text("close comments")
    expect(line).not_to_contain_text("threads")
    assert errors == []
    page.close()


def test_the_resolve_key_resolves_the_focused_thread(browser, serve):
    """r resolves the thread j/k landed on, through the button's own press, so
    focus lands where the button already sends it — on the thread that takes the
    resolved one's place. The promise is scoped the way it is worded: the key
    line offers resolve only over an open focused thread, the overlay row
    carries the scope in its words, and on a focused resolved thread the press
    acts on nothing — a run that reached for "the first open thread" instead of
    the focused one would resolve a thread the user never aimed at."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir

    def comment(text):
        return interact.append_event(
            d, {"kind": "comment", "author": "user", "version": 1, "text": text}
        )["id"]

    c1 = comment("First thought.")
    c2 = comment("Second thought.")
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 2")
    line = page.locator(".lf-keyline")

    # At page scope nothing promises r — its target is the focused thread, and
    # none is — while the overlay teaches the capability, scope in its words.
    expect(line).not_to_contain_text("resolve")
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_contain_text("On a focused thread: resolve it")
    page.keyboard.press("Escape")

    # j lands on the first thread and the line offers resolve; r takes it, and
    # focus lands on the thread now holding the resolved one's place, so j/k
    # and a second r walk on from there.
    page.keyboard.press("j")
    expect(page.locator(f'.lf-thread[data-id="{c1}"]')).to_be_focused()
    expect(line).to_contain_text("resolve")
    page.keyboard.press("r")
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()
    expect(line).to_contain_text("resolve")

    # A focused resolved thread promises nothing, and the press acts on nothing.
    page.locator(".lf-details summary").click()
    resolved = page.locator(f'.lf-details .lf-thread[data-id="{c1}"]')
    resolved.click()
    expect(resolved).to_be_focused()
    expect(line).not_to_contain_text("resolve")
    page.keyboard.press("r")
    # The absence is read after a poll the test forces, so a resolve the press
    # had wrongly posted would have landed by now.
    comment("Third thought.")
    told(page)
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    expect(page.locator(f'.lf-threads > .lf-thread[data-id="{c2}"]')).to_have_count(1)
    assert errors == []
    page.close()


def test_escape_on_a_declaring_control_does_exactly_what_it_says(browser, serve):
    """keyHint's contract: a control that declares its own Esc row consumes the
    press, so one press is one action. The draft editor's Esc used to be two — the
    edit cancelled and the runtime's ladder closed the panel behind it — and the
    cancel discarded the user's words against the never-lose-text norm. Now the
    editor closes keeping the edit, the panel stands, and a grabbed card's Esc
    cancels the move and nothing else."""
    html = BOARD_PAGE.replace(
        "</main>", '<lf-draft id="plan"><pre>Ship it.</pre></lf-draft></main>'
    )
    url = serve(html)
    interact.append_event(
        serve.page_dir,
        {"kind": "comment", "author": "user", "version": 1, "text": "A thread."},
    )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")
    page.keyboard.press("c")  # panel open, so the old second action would show
    expect(page.locator(".lf-panel")).to_be_visible()

    page.locator("lf-draft .lf-draft-pencil").click()
    ta = page.locator("lf-draft textarea")
    expect(ta).to_be_focused()
    ta.fill("Ship it — but louder.")
    page.keyboard.press("Escape")
    expect(ta).to_have_count(0)  # the editor closed…
    expect(page.locator(".lf-panel")).to_be_visible()  # …and only the editor
    # The edit was set aside, not discarded: reopening resumes it.
    page.locator("lf-draft .lf-draft-pencil").click()
    expect(page.locator("lf-draft textarea")).to_have_value("Ship it — but louder.")
    page.keyboard.press("Escape")

    # A grabbed card: Esc cancels the move, and the panel it would have closed stands.
    grip = page.locator("#card-heater .lf-grip")
    grip.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-keyline")).to_contain_text("cancel the move")
    # The contract's flip side: the leader refuses to arm over a control that has
    # claimed Escape, or one press would have two owners — the grip consuming it,
    # the chord promising its cancel.
    page.keyboard.press("g")
    expect(page.locator(".lf-keyline")).not_to_contain_text("reply to thread")
    expect(page.locator(".lf-keyline")).to_contain_text("cancel the move")
    page.keyboard.press("Escape")
    # The grab is over (an uncancelled one would also leave the card in Todo),
    # the line is back to the resting grip, and the panel the ladder would have
    # closed stands.
    expect(page.locator(".lf-lift")).to_have_count(0)
    expect(page.locator(".lf-keyline")).to_contain_text("grab the card")
    expect(page.locator("#col-todo #card-heater")).to_have_count(1)
    expect(page.locator(".lf-panel")).to_be_visible()
    assert errors == []
    page.close()


def test_the_composer_never_stands_on_its_own_mark(browser, serve):
    """The mark is the only thing naming the passage the box is about, so a box covering
    all of it is a box about nothing. That is not hypothetical: a restored draft reappears
    just under the banner, and the reading position puts the passage it was made on back
    where it was — which, for a passage that was near the top of a narrow column, is
    exactly there. The box has to move off it.

    Not off every pixel of it. The box has always covered the tail of a long passage and
    that reads fine; what may not happen is every rect hidden at once."""
    filler = "\n".join(
        f"<p id='f{i}'>Filler {i}. " + "Words. " * 20 + "</p>" for i in range(30)
    )
    url = serve(SETTLED_PAGE.replace("</main>", filler + "\n</main>"))
    page, errors = open_page(browser, url)

    page.locator(".lf-settled").click()  # open the settled group, as a reader would
    page.wait_for_selector("#opt-strict:visible")
    # A card in the middle column, scrolled just under the banner: narrower than the 320px
    # box and centred on it, which is the geometry the box can swallow whole.
    page.evaluate("""() => {
        const r = document.querySelector('#opt-strict').getBoundingClientRect();
        document.body.scrollBy({top: r.top - 60, behavior: 'instant'});
    }""")
    page.locator("#opt-strict").click(click_count=3)
    page.locator(".lf-fab").click()
    page.locator(".lf-composer textarea").fill("what did the trial actually show?")
    assert mark_shows_beside_composer(page), (
        "the box covered the passage it just opened on"
    )

    page.reload()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'block'"
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-pending')?.size ?? 0) > 0")
    assert mark_shows_beside_composer(page), (
        "the restored box came back on top of its own mark, and with the mark hidden "
        "nothing on screen says what the draft is about"
    )
    assert not composer_quote(page)["shown"], (
        "the mark is showing and the composer prints the passage as well"
    )
    assert errors == []
    page.close()


def test_the_composer_scrolls_with_the_passage_it_is_about(browser, serve):
    """The box points at a passage, so it lives in the document's coordinate space and
    scrolling moves the two together. It was viewport-fixed once: the page scrolled
    under a box that stayed put, and an ⌥-click's composer drifted off the diagram it
    was opened on and sat over whatever arrived beneath it.

    Both readings and the scroll happen in one synchronous evaluate — writing
    scrollTop reflows before the very next read — so there is no trip here to wait
    on."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.locator("#p30").scroll_into_view_if_needed()
    page.locator("#p30").click(click_count=3)
    page.wait_for_selector(".lf-fab", state="visible")
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    moved = page.evaluate("""() => {
        const top = (el) => el.getBoundingClientRect().top;
        const composer = document.querySelector('.lf-composer');
        const passage = document.getElementById('p30');
        const before = { composer: top(composer), passage: top(passage) };
        document.body.scrollTop += 240;
        return { composer: top(composer) - before.composer,
                 passage: top(passage) - before.passage };
    }""")
    assert moved["passage"] < 0, "the scroll must actually have moved the page"
    assert moved["composer"] == moved["passage"], (
        f"the box parted from its passage: the page moved {-moved['passage']}px "
        f"and the composer {-moved['composer']}px"
    )
    assert errors == []
    page.close()


def test_the_composer_stands_in_the_margin_beside_the_passage(browser, serve):
    """Where the column leaves room, the box goes into the margin rather than onto the
    page: a 320px card over a 720px column stands on somebody's words wherever it
    lands, and the margin holds none by construction. The passage and its neighbours
    stay fully readable while the user writes about them.

    The window is wide enough for that room to be there wherever this runs. What the
    placement asks is whether the box and its two 8px gaps fit beside the column in
    body's client box, and that box is the window less whatever the platform spends on
    a scrollbar — nothing under macOS's overlay ones, 15px of gutter on the Linux
    runner. 1440 made the question exact rather than true: the margin fitted the box
    with nothing at all to spare where this was written, and fell 15px short where it
    ran, so a placement doing precisely what it should read as a bug."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    resized(page, 1600, 900)
    page.locator("#p30").scroll_into_view_if_needed()
    page.locator("#p30").click(click_count=3)
    page.wait_for_selector(".lf-fab", state="visible")
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    standing = page.evaluate("""() => {
        const box = document.querySelector('.lf-composer').getBoundingClientRect();
        const column = document.querySelector('main').getBoundingClientRect();
        const touching = [...document.querySelectorAll('main p, main h1')]
            .filter(el => el.checkVisibility())
            .filter(el => { const r = el.getBoundingClientRect();
                            return r.left < box.right && box.left < r.right
                                && r.top < box.bottom && box.top < r.bottom; })
            .map(el => el.id || el.tagName);
        return { left: box.left, columnRight: column.right, touching };
    }""")
    assert standing["left"] >= standing["columnRight"], (
        f"the box opened at {standing['left']}px, inside the column ending at "
        f"{standing['columnRight']}px, with a margin free to its right"
    )
    assert standing["touching"] == [], (
        f"the box stands on the page's own text: {standing['touching']}"
    )
    assert errors == []
    page.close()


def test_a_float_the_panel_displaces_hands_the_page_no_sideways_scroll(browser, serve):
    """A float is an absolute child of body, so one standing past body's client box is
    sideways-scrollable overflow. Placement clamps inside the box of that moment, and
    the box then changes: the panel takes its strip, and a composer placed in a wide
    window's margin overhung the narrowed page — the document panned 328px left under
    a trackpad, with the composer standing on the panel that had displaced it. The
    floats are placed again when layout reshapes, after the margin's own transition,
    so the invariant is read with an auto-retrying wait rather than a one-shot read
    racing the transitionend handler."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    # The margin placement below is this test's precondition, so the window is the one
    # its own test states the width for.
    resized(page, 1600, 900)
    page.locator("#p30").scroll_into_view_if_needed()
    page.locator("#p30").click(click_count=3)
    page.wait_for_selector(".lf-fab", state="visible")
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    page.locator(".lf-composer textarea").fill("held open across the panel opening")
    assert page.evaluate(
        "() => document.querySelector('.lf-composer').getBoundingClientRect().left"
        "   >= document.querySelector('main').getBoundingClientRect().right"
    ), "the margin placement is the precondition — nothing strands a column-placed box"
    # A press on the banner's own button: standDown keeps a composer holding text.
    page.get_by_role("button", name="Comments", exact=False).click()
    panel_settled(page)
    page.wait_for_function("""() => {
        const box = document.querySelector('.lf-composer').getBoundingClientRect();
        return document.body.scrollWidth - document.body.clientWidth === 0
            && box.right <= document.body.clientWidth;
    }""")
    expect(page.locator(".lf-composer")).to_be_visible()
    assert errors == []
    page.close()


def test_a_draft_that_outlives_its_passage_still_says_what_it_was_about(browser, serve):
    """A draft survives the version it was written against — the user opens the new
    one with unsent text — and the passage it was about may not have. The mark is what
    normally says which passage the box is on, so where there is no passage left to mark
    the quote is the only record there is, and it comes back: dashed and muted, the same
    detached treatment the panel gives a thread this version dropped."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)

    page.locator("#p").click(click_count=3)
    page.locator(".lf-fab").click()
    page.locator(".lf-composer textarea").fill(
        "half-written when the version turned over"
    )
    passage = " ".join(page.locator("#p").inner_text().split())
    assert not composer_quote(page)["shown"], "the passage is right here, and marked"

    # Claude ships a version that rewrites the passage out. The page holds still — a
    # draft is mid-composition — and offers the new version as a chip, which the
    # user takes.
    d = serve.page_dir
    (d / "versions" / "v2.html").write_text(
        INLINE_PAGE.replace(
            "A paragraph carrying <strong>bold text</strong> and <em>emphasis</em> inside it,\n"
            "so that a selection across the middle of it lands in more than one text node.",
            "Rewritten, with nothing left of the sentence the draft was about.",
        )
    )
    interact.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "two"}
    )
    told(page)
    expect(page.locator(".lf-latest-chip")).to_be_visible()
    page.get_by_role("button", name="New version available", exact=False).click()
    page.wait_for_url("**/v2.html")
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'block'"
    )

    assert page.locator(".lf-composer textarea").input_value() == (
        "half-written when the version turned over"
    ), "the draft didn't survive the version it was written against"
    assert pending_text(page) == "", (
        "v2 rewrote the passage and the page marked it anyway"
    )
    quote = composer_quote(page)
    assert quote["shown"], (
        "nothing on screen says what the draft is about — no mark, and no quote either"
    )
    assert quote["text"] == f"“{passage}”", f"the quote says {quote['text']!r}"
    assert page.locator(".lf-composer .lf-quote.detached").count() == 1, (
        "the stranded quote reads as one that still points somewhere"
    )

    # A stranded quote is the last copy of that passage anywhere on the page, so it is text
    # a user selects to keep. The anchor pass reruns on every arriving comment, and a
    # rewritten node takes the selection with it.
    page.evaluate("""() => {
        const q = document.getElementById('lf-composer-quote');
        const r = document.createRange();
        r.setStart(q.firstChild, 1);
        r.setEnd(q.firstChild, 20);
        const s = getSelection(); s.removeAllRanges(); s.addRange(r);
    }""")
    held = page.evaluate("() => getSelection().toString()")
    assert len(held) == 19, (
        f"this assertion needs a selection to survive; it made {held!r}"
    )
    page.request.post(
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={"kind": "comment", "version": 2, "text": "arriving from another tab"},
    )
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")
    assert page.evaluate("() => getSelection().toString()") == held, (
        "the anchor pass rewrote the stranded quote and took the reader's selection with it"
    )
    assert errors == []
    page.close()


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_every_passage_in_a_real_page_can_be_quoted(browser, serve, example):
    """Anchoring has to work on the pages people actually write, not on a fixture built
    to suit it. Every failure here has been a place where what the reader selects and
    what the search reads come apart — an uppercased header, a widget's own chrome, the
    stylesheet a rendered diagram carries — and a hand-built page has none of them. So
    this drags across every pair of adjacent blocks in every shipped example, which is
    the shape a real selection takes, and asks for the highlight the composer promises.

    "Every" includes the words a widget renders into a control, which is why the filter
    below is the runtime's own rule rather than a test for the chrome class: while it was
    the class, the sweep that proves every passage is quotable structurally could not see
    the passages that weren't. It reaches six tab names, two column headings and a settled
    group's summary line in the gallery alone."""
    page, errors = open_page(browser, serve(example.read_text()))
    result = page.evaluate("""async () => {
        const tick = () => new Promise(r => setTimeout(r, 0));
        const composer = document.querySelector('.lf-composer');
        const fab = document.querySelector('.lf-fab');
        // A reader reaches everything eventually — opens the details, clicks through to
        // the other tab — so everything is in scope, not just what the page opens on.
        document.querySelectorAll('details').forEach(d => (d.open = true));
        document.querySelectorAll('[hidden]').forEach(e => e.removeAttribute('hidden'));
        // Declared labels are in scope, and the filter is the runtime's own rule rather
        // than the class: a tab's name and a settled row's title are words the page says
        // from inside chrome, which is exactly the shape a filter on .lf-ui cannot see.
        const speaks = el => {
            const near = el.closest('.lf-ui, [data-lf-said]');
            return !near || near.matches('[data-lf-said]');
        };
        const blocks = [...document.querySelectorAll('p,li,h1,h2,h3,td,th,blockquote,'
            + 'figcaption,summary,lf-option,lf-variant,lf-milestone,lf-metric,[data-lf-said]')]
          .filter(b => speaks(b) && b.checkVisibility()
                    && b.textContent.trim().length > 12);
        const missed = [], skipped = [], astray = [];
        for (let i = 0; i < blocks.length; i++) {
            // Each block alone, then reaching into the next one — a drag rarely stops
            // tidily on a boundary, and spanning two blocks is where the joins show.
            for (const end of [blocks[i], blocks[i + 1]].filter(Boolean)) {
                const range = document.createRange();
                range.setStart(blocks[i], 0);
                range.setEnd(end, end.childNodes.length);
                const sel = getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
                document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                await tick();
                // Counted, not shrugged off: a selection the button declines to offer is
                // a passage silently outside this sweep, and the sweep is the coverage.
                if (fab.style.display !== 'block') {
                    skipped.push(range.toString().replace(/\\s+/g, ' ').trim().slice(0, 70));
                    continue;
                }
                fab.click();
                await tick();
                const painted = CSS.highlights.get('lf-pending');
                // The captured quote, read off the node whether or not the reader can
                // see it: the composer shows it only where the page has no mark to give,
                // which is the very case this loop is counting.
                const quoted = document.getElementById('lf-composer-quote').textContent;
                if (!painted || ![...painted].map(r => r.toString()).join('').trim())
                    missed.push(quoted.slice(0, 70));
                // Inside what was selected, not merely somewhere: a matcher that finds
                // the right words in the wrong place paints, and paints a lie.
                //
                // A mark can now land inside a widget's shadow tree (x-shadow), and two
                // ranges in different trees cannot be compared at all — comparing them
                // throws rather than answering. So the question crosses the way the
                // runtime's own does: the tree renders where its host stands, so a mark
                // inside one is inside the selection exactly when the host is.
                else if ([...painted].some(p => {
                        const root = range.commonAncestorContainer.getRootNode();
                        if (p.startContainer.getRootNode() === root)
                            return p.compareBoundaryPoints(Range.START_TO_START, range) < 0
                                || p.compareBoundaryPoints(Range.END_TO_END, range) > 0;
                        let n = p.startContainer;
                        while (n && n.getRootNode() !== root) n = n.getRootNode().host;
                        return !n || !range.intersectsNode(n);
                    }))
                    astray.push(quoted.slice(0, 70));
                composer.style.display = 'none';
                sel.removeAllRanges();
            }
        }
        return {missed, skipped, astray};
    }""")
    assert result["missed"] == [], (
        f"{len(result['missed'])} passages in {example.stem} quote text the page "
        f"can't find: {result['missed']}"
    )
    assert result["skipped"] == [], (
        f"{len(result['skipped'])} passages in {example.stem} raised no Comment button, "
        f"so this sweep never tested them: {result['skipped']}"
    )
    assert result["astray"] == [], (
        f"{len(result['astray'])} passages in {example.stem} painted outside what was "
        f"selected: {result['astray']}"
    )
    assert errors == []
    page.close()


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_every_x_says_attribute_reaches_the_page_as_text(browser, serve, example):
    """The other half of what interact.UNREACHABLE_WORDS asks of a page — that half is
    in the gate, because a page-local widget is where a heading goes out of reach and the
    gate is what a user's page passes through; test_example_renders drives it over
    these same examples.

    What the gate can't ask is whether the words arrived at all: it works from the
    rendered page, where an attribute that reaches nobody looks exactly like an attribute
    with nothing to say. The registry knows the difference, so this reads x-says back and
    asks each declaration to be somewhere in its element's text — a metric with no number
    is a worse failure than one whose number can't be selected, and the only pass that
    would notice is this one."""
    page, errors = open_page(browser, serve(example.read_text()))
    unsaid = page.evaluate("""async () => {
        const out = [];
        const reg = await (await fetch('/registry.json')).json();
        for (const [tag, entry] of Object.entries(reg))
            for (const attr of Object.keys(entry['x-says'] ?? {}))
                for (const el of document.querySelectorAll(tag)) {
                    const value = el.getAttribute(attr);
                    if (value !== null && !el.textContent.includes(value))
                        out.push(`<${tag}${el.id ? ' id=' + el.id : ''}> never says `
                                 + `${attr}="${value}"`);
                }
        return out;
    }""")
    assert unsaid == [], (
        f"{example.stem} declares attributes as x-says that never reach the page as "
        f"text: {unsaid}"
    )
    assert errors == []
    page.close()


def test_a_widgets_attribute_takes_a_comment_like_any_other_passage(browser, serve):
    """The gesture itself, on the words a widget renders from an attribute: drag across
    a column's heading and the same button, quote, and mark come up as for a paragraph,
    and the comment is still anchored a version later. A real drag, because the whole
    class of bug here is text that looks selectable and isn't — a synthetic Range would
    select what no pointer can.

    Then the other half of the pair, which the same spans decide: the version diff reads
    a block's *authored* text, and the base version it compares against is parsed
    unupgraded, where these spans don't exist. Drop their data-lf-gen and every widget
    holding a said attribute lights up as changed on every revision — a failure that
    looks like a busy page rather than like a bug."""
    page, errors = open_page(browser, serve(SAID_PAGE))

    heading = page.locator('lf-column#col-now > [data-lf-said="label"]')
    box = heading.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))

    # The theme uppercases a column heading, so the selection reads back as the reader
    # sees it and the quote as the document holds it — the asymmetry that makes
    # selectionAnchor read the text nodes rather than the selection's own toString().
    assert page.evaluate("() => getSelection().toString()").strip() == "IN FLIGHT", (
        "a drag across the heading selected nothing — it is painted, not said"
    )
    page.locator(".lf-fab").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'block'"
    )
    quoted = composer_quote(page)["text"]
    assert quoted.strip("“”") == "In flight"
    page.locator(".lf-composer textarea").fill("this column's name is wrong")
    page.get_by_role("button", name="Comment", exact=True).click()
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    thread = page.locator(".lf-thread .lf-quote").first
    assert thread.text_content().strip().strip("“”") == "In flight"

    # A second version reworking one card's prose and nothing else. The page follows it,
    # and the anchor is on a word only the runtime puts there, so it has to be found
    # again in the version the user now has.
    d = serve.page_dir
    (d / "versions" / "v2.html").write_text(
        SAID_PAGE.replace("Waiting on the importer.", "Unblocked; starting Thursday.")
    )
    interact.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "two"}
    )
    page.wait_for_url("**/v2.html")
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert page.locator(".lf-thread .lf-quote.detached").count() == 0, (
        "the comment came loose from the heading when the version turned over"
    )

    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map(e => e.id)"
    ) == ["c-backfill"], "the diff read the runtime's own spans as text the base lacked"
    assert errors == []
    page.close()


FENCED_CAPTURE_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>fenced capture</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_browser_and_file_captures_stop_at_the_same_widget_fences(browser, serve):
    """Module-only words may sit between authored parts, but they cannot give the
    browser more context than the version file can confirm."""
    page, errors = open_page(browser, serve(FENCED_CAPTURE_PAGE))
    expect(page.locator("#gate-milestone .lf-chips")).to_have_count(1)
    registry = json.loads((serve.page_dir / "registry.json").read_text())
    cases = [
        ("#gate-milestone strong", "Build feeders", "gate-milestone"),
        ("#gate-milestone", "Two classic models.", "gate-milestone"),
        ("#after-milestone", "Ready next.", "after-milestone"),
        # One chip out of a band of them: authored markup, so both readings hold it
        # for the same reason they hold the title beside it.
        ("#fence-option > lf-chip", "effort: low", "fence-option"),
    ]

    for index, (selector, quote, section) in enumerate(cases, 1):
        expected_anchor = interact.capture_anchor(
            FENCED_CAPTURE_PAGE, registry, quote, section
        )
        selected = page.evaluate(
            """([selector, quote]) => {
                const root = document.querySelector(selector);
                const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
                let node;
                while ((node = walker.nextNode())) {
                    const at = node.data.indexOf(quote);
                    if (at === -1) continue;
                    const range = document.createRange();
                    range.setStart(node, at);
                    range.setEnd(node, at + quote.length);
                    const selection = getSelection();
                    selection.removeAllRanges();
                    selection.addRange(range);
                    return selection.toString();
                }
                return null;
            }""",
            [selector, quote],
        )
        assert selected == quote
        page.dispatch_event("body", "mouseup")
        expect(page.locator(".lf-fab")).to_be_visible()
        page.locator(".lf-fab").click()
        page.locator(".lf-composer textarea").fill(f"fence {index}")
        page.get_by_role("button", name="Comment", exact=True).click()
        expect(page.locator(".lf-thread")).to_have_count(index)
        actual_anchor = [
            event["anchor"]
            for event in interact.read_events(serve.page_dir)
            if event["kind"] == "comment"
        ][-1]
        assert actual_anchor == expected_anchor, (
            f"{selector} captured {actual_anchor}, file captured {expected_anchor}"
        )

    assert errors == []
    page.close()


# A label a widget renders into a control it also built. The tab strip is the case with
# nowhere else to say it: once the strip exists the panel heading stands down, so the
# button is the panel's only name. Every word here is distinct, so a quote can only
# anchor where it was picked, and the panels are long enough that a drag across one of
# these labels is an ordinary drag.
CONTROL_LABEL_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>labels</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_a_widgets_label_takes_a_comment_inside_the_control_it_labels(browser, serve):
    """The other half of the pair above: a word the page says that the widget renders
    into a control. A tab's name is the case with nowhere else to go — the panel heading
    the theme paints stands down the moment the strip exists — so if the strip's button
    can't be quoted, the user can read the tab's name and never point at it.

    That is what a user hit, twice, on a draft's heading: the words were the page's
    and the row holding them was marked as the runtime's. `.lf-ui` is a look, and
    anchoring's question is whose words these are — so the label answers it where it is
    written (relabel), and the nearest answer wins over the box around it.

    A real drag, because the whole class of bug is text that looks selectable and
    isn't. Then the republish, because an anchor on a widget's word has to survive a
    version turning over the way one on a paragraph does."""
    page, errors = open_page(browser, serve(CONTROL_LABEL_PAGE))

    tab = page.get_by_role("tab", name="Heated bird bath")
    box = tab.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 6, y), (box["x"] + box["width"] - 6, y))

    assert (
        page.evaluate("() => getSelection().toString()").strip() == "Heated bird bath"
    ), "a drag across the tab's name selected nothing"
    # The drag ended on a button, and the button still switches tabs — but this mouseup
    # was a selection's, not a press, so the reader is still looking at what they were
    # reading when they reached for the name.
    expect(page.locator("#p-feeders")).to_be_visible()

    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert composer_quote(page)["text"].strip("“”") == "Heated bird bath"
    page.locator(".lf-composer textarea").fill("call it the bath, not the bird bath")
    page.get_by_role("button", name="Comment", exact=True).click()
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    thread = page.locator(".lf-thread .lf-quote").first
    assert thread.text_content().strip().strip("“”") == "Heated bird bath"

    # A second version reworking the other panel's prose and nothing else: the name the
    # comment is on is still there, so the comment is still on it.
    d = serve.page_dir
    (d / "versions" / "v2.html").write_text(
        CONTROL_LABEL_PAGE.replace(
            "the south pair waits on brackets", "the brackets arrived"
        )
    )
    interact.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "two"}
    )
    page.wait_for_url("**/v2.html")
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert page.locator(".lf-thread .lf-quote.detached").count() == 0, (
        "the comment came loose from the tab's name when the version turned over"
    )
    assert errors == []
    page.close()


def test_a_selection_around_a_control_does_not_deaden_it(browser, serve):
    """The other side of the guard above, and the one that cost more. A user reads
    the sentence a suggestion sits in, drags across it, and then presses Accept — a
    fresh press, long after that drag's own mouseup.

    Asking whether the live selection *contains* the control is a question about the
    DOM, and a suggestion's row is the column's own child in flow between the block
    holding the change and the next one: a drag across both runs straight over it. So
    Accept did nothing, and kept doing nothing, because a press that refuses a drag
    never collapses the selection that deadened it either. The keyboard still worked,
    which is the shape of a bug nobody reports — it looks like a slip of the mouse.

    Both decisions the product exists to collect go through a press, so this asserts the
    pointer and then the keyboard, with the selection standing throughout."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    # Across the two paragraphs, so the row deciding the first is inside the selection.
    start = page.locator("#replace").bounding_box()
    end = page.locator("#insert").bounding_box()
    select(
        page,
        (start["x"] + 4, start["y"] + 6),
        (end["x"] + end["width"] - 6, end["y"] + end["height"] - 6),
        steps=16,
    )
    assert page.evaluate(
        "() => getSelection().containsNode(document.querySelector("
        "'[data-lf-for=sug-refill] .lf-sug-reject'), true)"
    ), "the selection doesn't reach the control, so this run tests nothing"

    page.locator("[data-lf-for='sug-refill'] .lf-sug-reject").click()
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "reject")
    assert page.evaluate("() => !getSelection().isCollapsed"), (
        "the press cleared the selection, so the keyboard half below is untested"
    )
    page.locator("[data-lf-for='sug-in-card'] .lf-sug-accept").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#sug-in-card")).to_have_attribute("data-lf-state", "accept")
    assert errors == []
    page.close()


def test_the_comment_button_stands_on_no_control(browser, serve):
    """And the other way the same press is lost: not deadened but covered. A selection
    fills its lines, so the button placed beside it goes out to the column's right edge —
    into the margin, on the line the change starts, which is exactly where the row
    deciding that change hangs. The user's own gesture put the 💬 over the Accept
    they made it to reach, and the press did the one thing worse than nothing: it hit the
    button and opened a composer, because a press on the 💬 is not the outside click that
    dismisses it.

    Asserted through the hit test rather than the rectangles, since what matters is which
    element the press would reach — and then by making the press, which is the whole
    claim."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    box = page.locator("#replace").bounding_box()
    select(
        page,
        (box["x"] + 4, box["y"] + 6),
        (box["x"] + box["width"] - 8, box["y"] + box["height"] - 6),
        steps=16,
    )
    expect(page.locator(".lf-fab")).to_be_visible()

    under = page.evaluate("""() => [...document.querySelectorAll("[data-lf-offer]")]
        .filter(c => !c.closest(".lf-chrome"))
        .filter(c => { const b = c.getBoundingClientRect();
                       const top = document.elementFromPoint((b.left + b.right) / 2,
                                                            (b.top + b.bottom) / 2);
                       return top && !c.contains(top) && top.closest(".lf-chrome"); })
        .map(c => c.className)""")
    assert under == [], f"floating chrome is standing on controls: {under}"

    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "accept")
    expect(
        page.locator(".lf-composer")
    ).to_be_hidden()  # the press decided, it didn't compose
    assert errors == []
    page.close()


def test_the_margin_offers_one_kind_of_press(browser, serve):
    """The 💬 and a change's ✓ Accept stand in the same margin, sometimes on the same
    line — the test above is that collision — so they have to read as one thing.

    They did not. The button was the chrome's own idiom (a solid accent rectangle at
    the chrome's size, and, through a cascade nobody meant, set in the page's serif
    three points larger than every other control in the layer) beside two hairline
    pills, which put two idioms four centimetres apart in the one place a reader
    compares them. Where a control stands decides which it wears: in the runtime's
    furniture a press is a .lf-btn and looks like one, and out in the margin it is a
    marginal mark.

    Pinned by reading both off one page. The pill is one statement now (.lf-pill, in
    the runtime's document-level vocabulary), but either wearer can still restate a
    property in its own rules — the fab's scoped block and the suggestion's state
    rules both layer over it — and this is what says such a restatement kept the
    family. The shadow is the one property allowed to differ, and it is the
    difference that is real: only one of them floats over the page's own words rather
    than standing in the empty rail."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    box = page.locator("#replace").bounding_box()
    select(
        page,
        (box["x"] + 4, box["y"] + 6),
        (box["x"] + box["width"] - 8, box["y"] + box["height"] - 6),
        steps=16,
    )
    expect(page.locator(".lf-fab")).to_be_visible()
    # The drag ends where the button is raised, so the pointer is on it: both are read
    # at rest, since a hover state read against a resting one compares nothing.
    page.mouse.move(4, 4)

    family = """el => { const s = getComputedStyle(el);
        return Object.fromEntries(["font-family", "font-size", "line-height",
            "border-radius", "border-top-width", "border-top-style", "padding",
            "background-color", "color"].map(p => [p, s.getPropertyValue(p)])); }"""
    raised = page.locator(".lf-fab").evaluate(family)
    resident = page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").evaluate(
        family
    )
    assert raised == resident, (
        "the margin's two presses are drawn differently:\n  "
        + "\n  ".join(
            f"{k}: {raised[k]!r} vs {resident[k]!r}"
            for k in raised
            if raised[k] != resident[k]
        )
    )
    assert "system-ui" in raised["font-family"], (
        f"the margin's presses speak in the document's voice: {raised['font-family']}"
    )
    assert (
        page.locator(".lf-fab").evaluate("el => getComputedStyle(el).boxShadow")
        != "none"
    ), "the one press that floats over the page says nothing about it"
    assert errors == []
    page.close()


def test_one_chip_says_every_keyboard_address(browser, serve):
    """A digit that reaches something is drawn one way, on both sides of the scope line.

    The panel's reply box wears the address the g leader answers and an option wears the
    one a pick answers, and this page shows them at once — a question asked inside a
    thread, so the two chips stand a couple of centimetres apart in the same panel. They
    were two hand-matched copies of a dozen declarations, one in the chrome's stylesheet
    and one in the theme, with nothing to say if either moved; the look is .lf-address in
    the runtime's document-level vocabulary now, and each wearer states only where its
    chip sits and when it shows.

    Which is why the look is what this compares and placement is not: the reply box's
    chip hangs off its own corner, and an option's is anchored from outside the group
    that would otherwise clip it (see test_a_questions_digits_are_drawn_whole). Same
    chip, two boxes to hang it from."""
    url = serve(REPLY_HOST_PAGE)
    for event in THREAD_ASKS:
        interact.append_event(serve.page_dir, event)
    page, errors = open_page(browser, url)

    # `a` opens the panel on the first ask and lands on its mark, which is what paints
    # that group's digits; g then arms the leader, which paints the reply boxes'.
    page.keyboard.press("a")
    picked = page.locator("#tq-one .lf-address").first
    expect(picked).to_be_visible()
    page.keyboard.press("g")
    addressed = page.locator(".lf-thread .lf-compose > .lf-address").first
    expect(addressed).to_be_visible()

    face = """el => { const s = getComputedStyle(el);
        return Object.fromEntries(["width", "height", "border-top-width",
            "border-top-style", "border-top-color", "border-radius", "background-color",
            "color", "font-size", "line-height", "text-align", "z-index"]
            .map(p => [p, s.getPropertyValue(p)])); }"""
    on_page, in_panel = picked.evaluate(face), addressed.evaluate(face)
    assert on_page == in_panel, (
        "the two keyboard addresses are drawn differently:\n  "
        + "\n  ".join(
            f"{k}: {on_page[k]!r} vs {in_panel[k]!r}"
            for k in on_page
            if on_page[k] != in_panel[k]
        )
    )
    assert errors == []
    page.close()


def test_the_composer_opens_where_the_button_stood(browser, serve):
    """Stepping the button aside is undone if what it opens goes back. The button carries
    the anchor it was raised on, and it used to carry the position it was *asked for*
    alongside — the same point for as long as nothing moved it, and a different one from
    the moment something did. So the 💬 cleared the row and the composer it opened landed
    back on top of it."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    box = page.locator("#replace").bounding_box()
    select(
        page,
        (box["x"] + 4, box["y"] + 6),
        (box["x"] + box["width"] - 8, box["y"] + box["height"] - 6),
        steps=16,
    )
    expect(page.locator(".lf-fab")).to_be_visible()
    stood = page.locator(".lf-fab").evaluate("el => el.getBoundingClientRect().top")
    # It moved, or this run would hold whether or not the position were carried along.
    assert stood > page.locator("[data-lf-for='sug-refill']").evaluate(
        "el => el.getBoundingClientRect().bottom"
    ), "the button never stepped aside, so where it stood proves nothing"

    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    opened = page.locator(".lf-composer").evaluate(
        "el => el.getBoundingClientRect().top"
    )
    assert abs(opened - stood) <= 1, (
        f"the composer opened at {opened}, where the button was asked for, not {stood}"
    )
    assert errors == []
    page.close()


def test_a_drag_released_mid_word_selects_whole_words(browser, serve):
    """A drag stops where the hand stopped: four glyphs into "paragraph", four short
    of the end of "carrying". The reader meant the words, and the quote the capture
    would otherwise store — "graph carr" — reads as a typo in the panel and in every
    reply that quotes it back. So the pointer path grows a selection out to word
    boundaries, outward only: an end resting in space or against punctuation is
    already where the reader put it, so "it," gains its 't' and not its comma, and a
    word split across inline markup — here by splitText, which also leaves the empty
    text node that puts two EDGEs flush in the indexed reading — still grows whole.

    What the pointer path must not do is here too. A keyboard selection is never
    grown — shift-arrow is the reader being precise — so the key release that raises
    the button leaves a mid-word selection exactly as made, and so does the right
    button, whose release precedes the context menu Copy lives in. A right-to-left
    drag keeps its direction, asked of boundary points rather than node order because
    a selection ending on the element holding its own start both precedes and
    contains it. And machine-placed words never glue to the author's, on either
    side of the declaration line: an undeclared generated span is a fenced cell in
    the reading, and a declared label — a specimen's, rendered flush before its
    words inside a list item, where both share the one block — is the seam itself.

    The reads await one queued step first, the same tick the mouseup handler defers
    its own work behind, so each one sees the selection after the snap rather than
    racing it."""
    page, errors = open_page(
        browser,
        serve(
            INLINE_PAGE.replace(
                '<p id="p">',
                '<ul><li><lf-specimen id="spec" label="mono">glyphs set close'
                '</lf-specimen></li></ul>\n<p id="p">',
            )
        ),
    )
    page.locator("#p").scroll_into_view_if_needed()
    # The point one pixel inside a character's own box, so a press there puts the
    # boundary at the character's left edge — mid-word when the character is.
    mid = """(args) => {
        const walk = document.createTreeWalker(
            document.querySelector(args.root), NodeFilter.SHOW_TEXT);
        for (let n = walk.nextNode(); n; n = walk.nextNode()) {
            const at = n.data.indexOf(args.word);
            if (at < 0) continue;
            const r = document.createRange();
            r.setStart(n, at + args.into);
            r.setEnd(n, at + args.into + 1);
            const box = r.getBoundingClientRect();
            return [box.left + 1, box.top + box.height / 2];
        }
    }"""
    settled = (
        "async () => { await new Promise(r => setTimeout(r, 0));"
        " return getSelection().toString(); }"
    )

    def spot(root, word, into):
        return page.evaluate(mid, {"root": root, "word": word, "into": into})

    select(page, spot("#p", "paragraph", 4), spot("#p", "carrying", 4))
    assert page.evaluate(settled) == "paragraph carrying"
    expect(page.locator(".lf-fab")).to_be_visible()

    select(page, spot("#p", "inside", 2), spot("#p", "it,", 1))
    assert page.evaluate(settled) == "inside it"

    # The same words dragged right to left: snapped the same, and still facing
    # backward, or the shift-click that extends it next extends the wrong end. The
    # click first is the reader's own move — a press inside the standing selection
    # would drag its text, not start a new one.
    page.locator("#t").click()
    select(page, spot("#p", "it,", 1), spot("#p", "inside", 2))
    assert page.evaluate(settled) == "inside it"
    assert page.evaluate(
        "() => { const s = getSelection();"
        " return s.anchorNode === s.focusNode ? s.anchorOffset > s.focusOffset"
        " : Boolean(s.anchorNode.compareDocumentPosition(s.focusNode)"
        " & Node.DOCUMENT_POSITION_PRECEDING); }"
    ), "a right-to-left drag came out of the snap facing forward"

    page.evaluate("""() => {
        const n = document.querySelector('#p').firstChild;
        const at = n.data.indexOf('paragraph') + 2;
        getSelection().setBaseAndExtent(n, at, n, at + 5);
    }""")
    page.keyboard.press("Shift")
    assert page.evaluate(settled) == "ragra"
    where = spot("#p", "paragraph", 4)
    page.mouse.click(where[0], where[1], button="right")
    assert page.evaluate(settled) == "ragra"

    forward_kept = page.evaluate("""async () => {
        const p = document.querySelector('#p2');
        const at = p.firstChild.data.indexOf('neighbouring') + 3;
        getSelection().setBaseAndExtent(p.firstChild, at, p, p.childNodes.length);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        await new Promise(r => setTimeout(r, 0));
        const s = getSelection();
        const r = s.getRangeAt(0);
        return s.anchorNode === r.startContainer && s.anchorOffset === r.startOffset;
    }""")
    assert forward_kept, "a forward selection ending on an element came out backward"

    page.evaluate("""() => {
        const n = document.querySelector('#p').firstChild;
        const at = n.data.indexOf('paragraph') + 4;
        n.splitText(at);
        n.splitText(at); // at the new node's own end, so the second piece is empty
    }""")
    select(page, spot("#p", "graph", 1), spot("#p", "carrying", 4))
    assert page.evaluate(settled) == "paragraph carrying"

    page.evaluate("""() => {
        const p2 = document.querySelector('#p2');
        const rest = p2.firstChild.splitText(p2.firstChild.data.indexOf(' between'));
        const span = document.createElement('span');
        span.setAttribute('data-lf-gen', '');
        span.textContent = 'flagged';
        p2.insertBefore(span, rest); // flush: the page now reads "boundaryflagged"
    }""")
    select(page, spot("#p2", "flagged", 3), spot("#p2", "them", 1))
    assert page.evaluate(settled) == "flagged between them"

    # The declared label: rendered by the real pass, flush before the specimen's own
    # words, unfenced because the registry models it — so the reading holds
    # "monoglyphs", and only the seam keeps a drag into "glyphs" from taking "mono".
    select(page, spot("lf-specimen", "glyphs", 3), spot("lf-specimen", "close", 3))
    assert page.evaluate(settled) == "glyphs set close"
    assert errors == []
    page.close()


def test_a_quote_finds_its_passage_whatever_its_whitespace(browser, serve):
    """The same passage gets written down several ways. The page holds it with the
    author's line wraps; a selection renders it with a break where two blocks abut and
    none where one wrapped; older versions of this runtime stored a third form again.
    All of them name the same words, so all of them have to find them — otherwise a
    comment made last month hangs off a passage the page insists isn't there."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)
    passage = "bold text and emphasis inside it"
    forms = {
        "as the page holds it": passage,
        "wrapped where a source line ended": passage.replace(" and ", "\nand "),
        "broken where a block ended": passage.replace(" and ", "\n\nand\n"),
        "spaced out by an editor": passage.replace(" ", "   "),
        # Reaching across the boundary between two blocks, which the reader sees as a
        # line break, the source writes as a newline, and a rendering may write as neither.
        "spanning two blocks": "more than one text node. A neighbouring block",
    }
    for name, quote in forms.items():
        page.request.post(
            url.rsplit("/versions/", 1)[0] + "/api/event",
            data={
                "kind": "comment",
                "version": 1,
                "text": name,
                "anchor": {"section": None, "quote": quote},
            },
        )
    page.get_by_role("button", name="Comments", exact=False).click()
    page.wait_for_function(
        f"() => document.querySelectorAll('.lf-thread').length === {len(forms)}"
    )
    stranded = page.locator(".lf-panel .lf-quote.detached").all_text_contents()
    assert stranded == [], f"quotes naming a passage that is right there: {stranded}"

    # The elasticity runs one way only. A quote is free to have gaps the page lacks; a
    # page's gaps are word boundaries, and a quote that runs across one is naming
    # something the page doesn't say — "never" must not find the tail of "on every".
    page.request.post(
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "version": 1,
            "text": "words the page never runs together",
            "anchor": {"section": None, "quote": "boldtext"},
        },
    )
    page.wait_for_function(
        f"() => document.querySelectorAll('.lf-thread').length === {len(forms) + 1}"
    )
    assert page.locator(".lf-panel .lf-quote.detached").count() == 1, (
        "a quote gluing two of the page's words together still found a passage"
    )

    # Nor may a gap close up onto a compound the page writes as one word. "set up" and
    # "setup" are different words, and the page has both — the anchor has to land on the
    # one that was dragged, and it is stored, so landing wrong is permanent.
    landed = page.evaluate("""async () => {
        const p = document.querySelector('#compound');
        const at = p.firstChild.data.indexOf('set up');
        const r = document.createRange();
        r.setStart(p.firstChild, at); r.setEnd(p.firstChild, at + 6);
        const s = getSelection(); s.removeAllRanges(); s.addRange(r);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        await new Promise(x => setTimeout(x, 30));
        document.querySelector('.lf-fab').click();
        await new Promise(x => setTimeout(x, 30));
        const painted = [...(CSS.highlights.get('lf-pending') ?? [])][0];
        return painted && painted.compareBoundaryPoints(Range.START_TO_START, r) === 0;
    }""")
    assert landed, "'set up' anchored onto 'setup', an earlier and different word"
    assert errors == []
    page.close()


def test_the_captured_quote_is_prose_a_file_can_hold(browser, serve):
    """A quote is read back as prose — seeded into the suggestion box, printed in the
    panel, emitted into a Markdown blockquote by `leaf transcript` — and written to a
    UTF-8 file on the way. Source text is neither: it carries the author's line wraps,
    which break a blockquote open, and cutting it to length by UTF-16 unit can halve a
    character, which no UTF-8 file can hold. The server refuses that write and the
    reader is told it is offline, with no way to ever send the comment."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)

    def compose_on(block):
        page.locator(block).click(click_count=3)
        page.locator(".lf-fab").click()
        page.wait_for_function(
            "() => document.querySelector('.lf-composer').style.display === 'block'"
        )

    # Read off the composer's description of its own anchor, which is the captured quote
    # verbatim — the string that goes on to the panel, the file, and the export.
    compose_on("#p")  # authored across two source lines
    wrapped = composer_quote(page)["text"]
    assert "\n" not in wrapped, f"the quote carries the source's line wrap: {wrapped!r}"
    page.get_by_role("button", name="Cancel").click()

    # Measured in the page: a lone surrogate does not survive the trip out to the test
    # runner, which replaces it, so asking out here would always come back clean.
    # Iterating by code point, a character cut in half is left as a single unit in the
    # surrogate range; an intact one comes through as the pair it is.
    compose_on("#cap")
    assert not page.evaluate("""() => [...document.getElementById('lf-composer-quote').textContent]
        .some(c => c.length === 1 && c.charCodeAt(0) >= 0xd800 && c.charCodeAt(0) <= 0xdfff)"""), (
        "the 400-character cap split a character in half"
    )

    # And the round trip that proves it: the server has to accept the quote and write it
    # to a UTF-8 file. A half character fails there, reported to the reader as an offline
    # server, and no retry can ever succeed.
    page.locator(".lf-composer textarea").fill("a comment on the capped passage")
    page.locator(".lf-composer").get_by_role("button", name="Comment").click()
    page.wait_for_function("""() => document.querySelectorAll('.lf-thread').length === 1
        || document.querySelector('.lf-toast').classList.contains('show')""")
    assert page.locator(".lf-thread").count() == 1, (
        f"the comment never posted — the page says {page.locator('.lf-toast').text_content()!r}"
    )
    assert errors == []
    page.close()


def test_an_open_composer_does_not_eat_the_next_click(browser, serve):
    """Clicks keep working while a composer is open. The composer comes down on the
    document's mousedown, and anything that rewrites the page's marks there swaps out
    the node under the pointer between press and release — which is a click the
    browser never dispatches at all. So a thread's highlight stops opening its thread,
    and a link inside a highlighted passage stops navigating. Real button presses,
    because a synthetic click event sails straight past the gap it lives in."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)
    page.request.post(
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "version": 1,
            "text": "on the passage",
            "anchor": {"section": "p", "quote": "bold text"},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    # Open a composer on other text and type nothing, so the next mousedown outside it
    # is the one that takes it down.
    page.locator("#q").click(click_count=3)
    page.locator(".lf-fab").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'block'"
    )

    page.mouse.click(*mark_point(page, "lf-mark"))
    panel_settled(page)

    # And the composer's own mark belongs to no thread, so it opens nothing. Its first
    # range runs up to the posted one, so this lands on the draft and nothing else.
    page.get_by_role("button", name="Close comments").click()
    page.locator("#p").click(click_count=3)
    page.locator(".lf-fab").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'block'"
    )
    page.mouse.click(*mark_point(page, "lf-pending"))
    assert not page.locator(".lf-panel").evaluate(
        "el => el.classList.contains('open')"
    ), (
        "clicking the composer's own highlight opened the panel, but it belongs to no thread"
    )
    assert errors == []
    page.close()


def test_a_click_on_a_mark_decides_once(browser, serve):
    """Opening the panel reflows the document, so anything that hit-tests the page after
    the panel opens is testing geometry that has already moved. When two handlers each
    asked where the pointer was, the second missed the mark the first had just opened and
    raised the comment button on top of it — and the element anchor that left behind reads
    as composition in progress, which is what stops a page following new versions. The
    panel starts shut here because a panel already open is the case with no reflow."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)
    # A quote inside the figure's caption: a painted range, so opening the panel reflows the
    # text out from under the pointer. An element anchor wouldn't show it — a figure still
    # covers the same point after the column narrows.
    page.request.post(
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "version": 1,
            "text": "on the caption",
            "anchor": {"section": "fig", "quote": "A specimen, for element anchors."},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    if page.locator(".lf-panel.open").count():
        page.get_by_role("button", name="Close comments").click()
        panel_settled(page, open=False)

    page.locator("#fig").scroll_into_view_if_needed()
    spot = page.evaluate("""() => { const r = [...CSS.highlights.get('lf-mark')][0].getClientRects()[0];
                                    return {x: r.left + r.width / 2, y: r.top + r.height / 2}; }""")
    page.mouse.click(spot["x"], spot["y"])
    panel_settled(page)
    expect(
        page.locator(".lf-fab"),
        "the click opened the thread and then offered to comment on it as well",
    ).not_to_be_visible()

    # The harm that outlives the stray button: a page mid-composition stays put.
    d = serve.page_dir
    (d / "versions" / "v2.html").write_text(
        INLINE_PAGE.replace('<h1 id="t">Inline</h1>', '<h1 id="t">Inline II</h1>')
    )
    interact.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "two"}
    )
    page.wait_for_url("**/v2.html")
    assert errors == []
    page.close()


CODE_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>code</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_code_is_colored_without_a_word_moving(browser, serve):
    """Colouring is spans, and the anchor pass is what spans break: the version file holds
    one run of characters where the DOM now holds a dozen nodes. A <span> is no text block,
    so both readings collapse to the same string — which is what lets the runtime color a
    block the file knows nothing about, and what keeps `leaf comment` able to quote
    into one.

    One pass serves both shapes a page has for code, lf-code's `language` and a plain
    <pre><code class="language-*">, and neither guesses: a lf-code with no `language` stays
    the color of its own ink. The quote below is written the way `leaf comment`
    writes one — against the file — and spans a token boundary on its way back."""
    url = serve(CODE_PAGE)
    page, errors = open_page(browser, url)
    page.wait_for_function(
        "() => document.querySelector('lf-code.lf-rendered') !== null"
    )

    roles = page.evaluate("""() => {
      const at = sel => [...document.querySelectorAll(sel + ' [data-lf-syn]')]
        .map(e => [e.dataset.lfSyn, e.textContent]);
      return { widget: at('#walk-code'), plain: at('#walk pre > code'),
               undeclared: at('#plain-code') };
    }""")
    assert ["kw", "def"] in roles["widget"] and ["fn", "bucket_key"] in roles["widget"]
    assert {r for r, _ in roles["widget"]} >= {"kw", "st", "fn"}, roles["widget"]
    assert ["cm", "# apply the migration, then run the marked suite"] in roles["plain"]
    assert roles["undeclared"] == [], (
        f"a lf-code with no language was colored anyway: {roles['undeclared']}"
    )

    # The words each block holds, unchanged by the spans: what the file says is what the
    # page says, which is the whole reason a quote written against one lands in the other.
    # The widget numbers lines, so its own newline is the join; the note it docks at line 2
    # is prose and sits outside the code.
    assert page.evaluate(
        "() => document.querySelector('#walk pre > code').textContent"
    ) == (
        "# apply the migration, then run the marked suite\ncd gateway && alembic upgrade head"
    )
    # Read the way the runtime reads it: everything generated set aside. The highlighted
    # line carries a word of the layer's own (below), and a reading that counted it would
    # be claiming the file holds a word no version of it ever will.
    assert page.evaluate(
        "() => [...document.querySelectorAll('#walk-code .lf-code-line')]"
        ".map(l => [...l.childNodes].filter(n => !(n.nodeType === 1 && n.dataset.lfGen))"
        ".map(n => n.textContent).join('')).join('')"
    ) == (
        "def bucket_key(request):\n    if request.token:\n"
        '        return f"tok:{request.token.id}"\n    return "anon"\n'
    )

    # `hi` is a background tint and says which line the note beside it is about. Nothing
    # of that reaches a reader listening, who gets the block entire with no idea which of
    # it was pointed at — and the numbers can't tell them, being a CSS counter painted
    # into no text node so that a copy of the block is source and not a listing. So the
    # highlighted line says so itself, once, where it is true.
    lines = page.locator("#walk-code .lf-code-line")
    assert "highlighted" in lines.nth(1).aria_snapshot()
    assert page.locator("#walk-code .lf-quiet").count() == 1, (
        "the tinted line is the one that says it, and it says it once"
    )

    # A quote across a token boundary — "upgrade" is plain, "head" is a keyword span.
    page.request.post(
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "version": 1,
            "text": "does prod want --sql here?",
            "anchor": {
                "section": "walk",
                "quote": "alembic upgrade head",
                "prefix": "on, then run the marked suite cd gateway &&",
                "suffix": "",
            },
        },
    )
    page.get_by_role("button", name="Comments", exact=False).click()
    # Posted to the server rather than through the page, so the page hears about it
    # when its next poll asks.
    told(page)
    expect(page.locator(".lf-thread")).to_have_count(1)
    expect(page.locator(".lf-panel .lf-quote.detached")).to_have_count(0)
    # The mark is a painted range, so what it covers is read back off CSS.highlights
    # rather than off the DOM.
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    marked = page.evaluate("""() => [...CSS.highlights.get('lf-mark').values()]
                                     .map(r => r.toString()).join("")""")
    assert marked == "alembic upgrade head", f"the mark landed on {marked!r}"
    assert errors == []
    page.close()


def test_every_language_returns_the_source_it_was_given(browser, serve):
    """`syntax` promises the tokens partition the source exactly, and lf-code's line
    numbers, `hi`, and every note's `at` are counted off that partition — so a tokenizer
    that dropped a character would slide all three with nothing on screen saying so. The
    promise is checked at the boundary and the check throws; this drives every language
    the registry offers through the real module, including each one against another
    language's source, which is where a lexer meets input it was never written for.

    It is also what a version bump of the vendored bundle has to survive."""
    url = serve(CODE_PAGE)
    page, errors = open_page(browser, url)
    langs = interact.load_registry(serve.page_dir)["$languages"]["names"]
    samples = [
        'def f(x):\n    """doc\n    <b>&amp;</b>\n    """\n    return f"{x!r}"  # ok\n',
        '# c\ncd x && ls -la | grep "a b" > /dev/null\n',
        '{"a": [1, 2, {"b": null}], "c": "<>&"}\n',
        "@@ -1 +1 @@\n-a <b>\n+c &d\n",
        "SELECT * FROM t WHERE a = 'x''y'; -- note\n",
        '<!doctype html>\n<a href="x?a=1&b=2">t &amp; u</a>\n',
    ]
    bad = page.evaluate(
        """async ([langs, samples]) => {
          const { syntax } = await import('/leaf.js');
          const bad = [];
          for (const lang of langs)
            for (const src of samples) {
              try {
                const tokens = await syntax(src, lang);
                const back = tokens.map(t => t.text).join('');
                if (back !== src) bad.push([lang, src, back]);
              } catch (e) { bad.push([lang, src, String(e)]); }
            }
          return bad;
        }""",
        [langs, samples],
    )
    assert bad == [], f"the tokenizer changed the source: {bad}"
    assert errors == []
    page.close()


# A diff of three files, one per thing the colouring has to get right: a Python file
# whose second hunk moves a docstring across lines and whose two sides disagree about
# what is open, a yaml file (the grammar that reads a leading `-` as a sequence bullet
# and a leading `+` as a string, so the prefix column has to be off before it looks),
# and a file whose extension names no language at all.
DIFF_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>diff</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_a_diff_is_colored_by_each_files_own_path(browser, serve):
    """A diff is the page's most code-dense shape and it sits beside lf-code on the pages
    that carry both, so leaving it plain said the evidence was not code. It has no `language`
    to read — a unified diff spans files — so each file's path is what says what it holds,
    and a path naming nothing leaves that file the colour of its own ink.

    Three things that were each wrong in a draft of this. The +/−/space column is the
    diff's word about a line and not the file's: yaml lexes a leading `-` as a sequence
    bullet and a leading `+` as a string, so a prefix left on restates the widget's own
    signal in the wrong ink. A hunk is tokenized one side at a time, because read straight
    through it interleaves two versions that never coexisted. And each side is tokenized
    whole, because a docstring spans lines — coloured a line at a time, the prose inside
    one comes back as code."""
    page, errors = open_page(browser, serve(DIFF_PAGE))
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )

    # Through the shadow root, because that is where lf-diff renders (x-shadow): its
    # lines are in the composed tree the reader sees and in no querySelectorAll over the
    # document. Reaching for them by hand here is the test paying the same crossing the
    # runtime pays in textNodesUnder.
    files = page.evaluate("""() => [...document.querySelector('#patch').shadowRoot
      .querySelectorAll('details')].map(d => ({
      path: d.querySelector('summary code').textContent,
      lines: [...d.querySelectorAll('pre > span')].map(l => ({
        kind: l.className,
        text: l.textContent,
        // Whether the line opens inside a syntax span — which is where the +/− column
        // would have gone if it had been handed to the tokenizer along with the source.
        signInSpan: l.firstChild?.nodeType === Node.ELEMENT_NODE,
        roles: [...l.querySelectorAll('[data-lf-syn]')].map(s => [s.dataset.lfSyn, s.textContent]),
      })),
    }))""")
    by_path = {f["path"]: f["lines"] for f in files}
    assert set(by_path) == {
        "gateway/limits.py",
        "gateway/config.yaml",
        "deploy/Dockerfile",
    }

    py = by_path["gateway/limits.py"]
    assert any(["kw", "if"] in line["roles"] for line in py), py
    assert {r for line in py for r, _ in line["roles"]} >= {"kw", "st", "fn"}

    # The docstring the second hunk rewrites: every line of it is string, on both sides.
    # Colouring line by line instead, `and` inside the prose came back a keyword.
    doc = [l for l in py if "Called on logout" in l["text"]]
    assert len(doc) == 2, [l["text"] for l in py]
    for line in doc:
        assert [r for r, _ in line["roles"]] == ["st"], line

    # yaml, the grammar that would have eaten the prefix: with the column left on, the
    # `-` came back a bullet in keyword ink and the `+` a string. No span opens a line
    # here, and the key is still an attr — so the prefix came off before the lexer looked.
    yml = [l for l in by_path["gateway/config.yaml"] if l["kind"] in ("add", "del")]
    assert len(yml) == 2
    for line in yml:
        assert not line["signInSpan"], line
        assert ["ty", "burst:"] in line["roles"], line

    # `\\ No newline at end of file` is git remarking on the line above, not a line of
    # the file. Shown, because the diff says it, but its own kind — read as context it
    # would go into both reconstructed sides as source the file never held.
    note = [l for l in py if l["kind"] == "note"]
    assert [l["text"] for l in note] == ["\\ No newline at end of file\n"], py
    assert note[0]["roles"] == [], note

    # No extension the table names: plain, the way a lf-code with no `language` is.
    assert all(l["roles"] == [] for l in by_path["deploy/Dockerfile"]), by_path[
        "deploy/Dockerfile"
    ]

    # Every displayed source line still reads exactly as authored, sign column and all.
    # File headers are metadata already represented by the summary, so the widget drops
    # them instead of leaving hidden text in the DOM for anchoring to find.
    assert [l["text"] for l in by_path["gateway/config.yaml"]] == [
        "@@ -4,6 +4,6 @@ ratelimit:\n",
        "-  burst: 20\n",
        "+  burst: 40\n",
        "   window: 60\n",
    ]
    assert errors == []
    page.close()


def test_two_comments_on_one_element_both_stay_anchored(browser, serve):
    """A figure can carry more than one thread. When the page's record of what it drew was
    keyed by the mark, the second comment overwrote the first, and the panel told the
    reader the first one's passage wasn't in this version — while it sat outlined on
    screen for the second."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)
    for text in ("first on the figure", "second on the figure"):
        page.request.post(
            url.rsplit("/versions/", 1)[0] + "/api/event",
            data={
                "kind": "comment",
                "version": 1,
                "text": text,
                "anchor": {"section": "fig"},
            },
        )
    page.get_by_role("button", name="Comments", exact=False).click()
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 2")
    stranded = page.locator(".lf-panel .lf-quote.detached").all_text_contents()
    assert stranded == [], f"outlined on screen, reported missing: {stranded}"
    assert errors == []
    page.close()


def test_the_pointer_stops_claiming_a_mark_it_scrolled_past(browser, serve):
    """The hover is a function of where the pointer is and where the text is, and scrolling
    moves the second without touching the first. A wrapped <mark> got this from :hover; a
    painted range has to be asked again, so everything that moves the page asks."""
    url = serve(LONG_PAGE)
    page, errors = open_page(browser, url)
    page.request.post(
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "version": 1,
            "text": "up top",
            "anchor": {"section": "p0", "quote": "Paragraph 0."},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    spot = page.evaluate("""() => { const r = [...CSS.highlights.get('lf-mark')][0].getClientRects()[0];
                                    return {x: r.left + r.width / 2, y: r.top + r.height / 2}; }""")
    page.mouse.move(spot["x"], spot["y"])
    page.wait_for_function("() => document.body.classList.contains('lf-over-mark')")
    page.evaluate("() => document.body.scrollBy({top: 900, behavior: 'instant'})")
    page.wait_for_function(
        "() => !document.body.classList.contains('lf-over-mark')"
        " && (CSS.highlights.get('lf-mark-hover')?.size ?? 0) === 0"
    )
    assert errors == []
    page.close()


# A page that says the same thing twice *within one section*, which is the only case a
# quote alone cannot place — scoping to a section already separates copies that live under
# different ids. A unified diff is the case that matters and the reason the section can't
# help: it holds the changed line on both sides, under one id, so the two occurrences are a
# bug and its fix, and landing on the wrong one inverts what the comment means.
TWICE_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>twice</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_a_repeated_passage_anchors_where_it_was_picked(browser, serve):
    """A quote names text, not a place. Where one section says the same thing twice, the
    words on either side are what tell the copies apart — so an anchor carries them, and
    the occurrence whose neighbours match wins. Driven through the real button, because
    the context is captured from the live selection and nowhere else."""
    page, errors = open_page(browser, serve(TWICE_PAGE))
    landed = page.evaluate("""async () => {
        const paras = [...document.querySelectorAll('#repeat p')];
        const p = paras.at(-1);
        const phrase = 'The version stamp never lands.';
        const at = p.firstChild.data.indexOf(phrase);
        if (at === -1) return 'phrase missing';
        const want = document.createRange();
        want.setStart(p.firstChild, at); want.setEnd(p.firstChild, at + phrase.length);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        await new Promise(r => setTimeout(r, 40));
        const fab = document.querySelector('.lf-fab');
        if (fab.style.display !== 'block') return 'no button';
        fab.click();
        await new Promise(r => setTimeout(r, 40));
        const painted = [...(CSS.highlights.get('lf-pending') ?? [])][0];
        if (!painted) return 'no mark';
        return painted.compareBoundaryPoints(Range.START_TO_START, want) === 0;
    }""")
    assert landed is True, (
        f"the second copy was picked, the mark went elsewhere ({landed})"
    )
    assert errors == []
    page.close()


DRIFT_V1 = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>drift</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="t">Drift</h1>
<section id="drift">
<p>Cache warmup runs first. {phrase}. Retries are capped at three.</p>
<p>Queue drain runs first. {phrase}. Retries are capped at four.</p>
</section>
</main>
</body>
</html>
""".replace("{phrase}", "The version stamp never lands")
# v2 rewrites the words on both sides of the *commented* copy and leaves the other alone,
# so the untouched copy is now the better match for the context the comment stored.
DRIFT_V2 = DRIFT_V1.replace(
    "Cache warmup runs first.", "Cache warmup is gone now."
).replace("lands. Retries are capped at three.", "lands. Backoff is capped at three.")


def test_an_ambiguous_revised_passage_detaches_instead_of_guessing(browser, serve):
    """Context tells two copies apart; it must not relocate a comment when the page moves
    on. If a later version rewrites the words beside the anchored copy, that copy confirms
    almost nothing while another copy remains. Neither is now identifiable: document
    order is not evidence, so the comment detaches visibly instead of moving to words it
    was never made on."""
    url = serve(DRIFT_V1)
    page, errors = open_page(browser, url)
    landed = page.evaluate("""async () => {
        const p = document.querySelectorAll('#drift p')[0];
        const phrase = 'The version stamp never lands';
        const at = p.firstChild.data.indexOf(phrase);
        const want = document.createRange();
        want.setStart(p.firstChild, at); want.setEnd(p.firstChild, at + phrase.length);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        await new Promise(r => setTimeout(r, 40));
        const fab = document.querySelector('.lf-fab');
        if (fab.style.display !== 'block') return 'no button';
        fab.click();
        await new Promise(r => setTimeout(r, 40));
        document.querySelector('.lf-composer textarea').value = 'is this idempotent?';
        document.querySelector('.lf-composer textarea')
            .dispatchEvent(new Event('input', {bubbles: true}));
        document.querySelector('.lf-composer button.primary').click();
        return true;
    }""")
    assert landed is True, f"couldn't post the comment ({landed})"
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    d = serve.page_dir
    (d / "versions" / "v2.html").write_text(DRIFT_V2)
    interact.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "revised"}
    )
    page.wait_for_url("**/v2.html")
    expect(page.locator(".lf-thread .lf-quote.detached")).to_have_count(1)
    assert page.evaluate("() => CSS.highlights.get('lf-mark')?.size ?? 0") == 0
    expect(page.locator(".lf-thread .lf-quote")).to_have_attribute(
        "title", re.compile("can't be identified")
    )
    assert errors == []
    page.close()


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
ASTRAL_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>astral</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="t">Astral</h1>
<section id="astral">
<p>Ordinary prose ahead of the first copy here. {phrase} and a tail.</p>
<p>A divider paragraph between the copies.</p>
<p>{run}{phrase} and a tail.</p>
</section>
</main>
</body>
</html>
""".replace("{run}", "".join(m + PAD for m in MARKERS)).replace(
    "{phrase}", "TARGET PHRASE"
)


def test_a_passage_among_padded_emoji_confirms_its_neighbours(browser, serve):
    """A stored context is counted in code points; the comparison counts code units; and an
    astral character is two of the second for one of the first. Ask the page for the first
    number and the window comes up short of what was written down — and short is fatal,
    because a passage confirms its neighbours in full or not at all. The anchor would fall
    back to naming the first copy on that page for good, silently. No shipped example holds
    an astral character, so only a fixture can hold this."""
    page, errors = open_page(browser, serve(ASTRAL_PAGE))
    landed = page.evaluate("""async () => {
        const skip = '.lf-ui, script, style';
        const w = document.createTreeWalker(document.getElementById('astral'),
            NodeFilter.SHOW_TEXT,
            {acceptNode: n => n.parentElement?.closest(skip)
                ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT});
        const phrase = 'TARGET PHRASE';
        const hits = [];
        for (let n = w.nextNode(); n; n = w.nextNode()) {
            let i = n.data.indexOf(phrase);
            while (i !== -1) { hits.push({node: n, at: i}); i = n.data.indexOf(phrase, i + 1); }
        }
        if (hits.length !== 2) return `fixture holds ${hits.length} copies, wanted 2`;
        const h = hits[1];   // the copy among the emoji
        const want = document.createRange();
        want.setStart(h.node, h.at); want.setEnd(h.node, h.at + phrase.length);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        await new Promise(r => setTimeout(r, 60));
        const fab = document.querySelector('.lf-fab');
        if (fab.style.display !== 'block') return 'no button';
        fab.click();
        await new Promise(r => setTimeout(r, 60));
        const painted = [...(CSS.highlights.get('lf-pending') ?? [])][0];
        if (!painted) return 'no mark';
        return painted.compareBoundaryPoints(Range.START_TO_START, want) === 0;
    }""")
    assert landed is True, (
        f"the emoji copy was picked, the mark went elsewhere ({landed})"
    )
    assert errors == []
    page.close()


# Two copies of one phrase behind an identical lead, the second closing its section. The
# words that tell them apart are the next section's, which only a capture reading past the
# section edge can store.
EDGE_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>edge</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="t">Edge</h1>
<section id="edge">
<p>First pass: when the deploy fails again in the night, the run is retried until it lands. Nothing else moves.</p>
<p>Second pass: when the deploy fails again in the night, the run is retried until it lands.</p>
</section>
<section id="tail">
<p>Rollout resumes once the queue drains completely.</p>
</section>
</main>
</body>
</html>
"""


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


@pytest.mark.parametrize(
    "html", [EDGE_PAGE, TAIL_PAGE], ids=["closes-its-section", "ends-the-document"]
)
def test_a_repeated_passage_at_an_edge_anchors_where_it_was_picked(
    browser, serve, html
):
    """A passage closing its section used to store a suffix clipped at the section's
    edge — one character, a bar the identical copy above it also cleared, so the mark
    painted there while the user was still composing. The neighbours now come from
    the whole document and the section only filters where the search may land, so the
    closing copy is told apart by the words of the section after it.

    Where the document itself ends there is no second side to store, and an empty one is
    not an absent constraint: it says nothing followed the passage anywhere, which is true
    of exactly one occurrence. Refusing to read it that way left the same wrong mark."""
    page, errors = open_page(browser, serve(html))
    landed = page.evaluate("""async () => {
        const p = document.querySelectorAll('#edge p')[1];
        // Through the full stop, so that with the section below removed the passage is the
        // last thing the document says and its stored suffix comes out empty.
        const phrase = 'the run is retried until it lands.';
        const at = p.firstChild.data.indexOf(phrase);
        if (at === -1) return 'phrase missing';
        const want = document.createRange();
        want.setStart(p.firstChild, at); want.setEnd(p.firstChild, at + phrase.length);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        await new Promise(r => setTimeout(r, 60));
        const fab = document.querySelector('.lf-fab');
        if (fab.style.display !== 'block') return 'no button';
        fab.click();
        await new Promise(r => setTimeout(r, 60));
        const painted = [...(CSS.highlights.get('lf-pending') ?? [])][0];
        if (!painted) return 'no mark';
        if (painted.compareBoundaryPoints(Range.START_TO_START, want) === 0) return true;
        return painted.startContainer.parentElement.textContent.slice(0, 40);
    }""")
    assert landed is True, (
        f"the closing copy was picked, the mark went elsewhere ({landed})"
    )
    assert errors == []
    page.close()


def test_an_anchor_stored_under_the_section_clipped_capture_still_resolves(
    browser, serve
):
    """The bar is however much was stored. An anchor from an older log carries context
    clipped at its section's edge; it confirms at that shorter bar exactly as it did when
    it was written, so nothing already in a log detaches when the capture reaches
    further."""
    url = serve(EDGE_PAGE)
    interact.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "version": 1,
            "text": "old bar",
            "anchor": {
                "section": "edge",
                "quote": "the run is retried until it lands",
                "prefix": "ails again in the night,",
                "suffix": ". Nothing else moves.",
            },
        },
    )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    where = page.evaluate("""() => {
        const r = [...CSS.highlights.get('lf-mark')][0];
        return r.startContainer.parentElement.textContent.slice(0, 11);
    }""")
    assert where == "First pass:", (
        f"an old anchor's thin bar changed where it lands: {where!r}"
    )
    assert errors == []
    page.close()


def test_an_ambiguous_one_sided_anchor_from_an_older_capture_detaches(browser, serve):
    """A capture that stopped at the section root wrote no prefix at all for a passage
    opening its section. Read the way the search now reads an empty side — nothing preceded
    this passage anywhere on the page — that claim is false wherever the section wasn't
    first, so no occurrence confirms it. With two quote candidates left, the passage is
    ambiguous and detaches rather than using document order."""
    url = serve(EDGE_PAGE)
    # A suffix that fits the second copy and nothing else, stored with no prefix beside it.
    interact.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "version": 1,
            "text": "older anchor",
            "anchor": {
                "section": "edge",
                "quote": "the run is retried until it lands",
                "suffix": ". Rollout resumes",
            },
        },
    )
    page, errors = open_page(browser, url)
    expect(page.locator(".lf-thread .lf-quote.detached")).to_have_count(1)
    assert page.evaluate("() => CSS.highlights.get('lf-mark')?.size ?? 0") == 0
    assert errors == []
    page.close()


# A passage longer than the search's pattern, twice over, so the pattern's own lead
# matches both copies and only their neighbours tell them apart. Prose rather than
# filler, because the walk that confirms the rest of a quote steps word by word.
LONG_PASSAGE = "Note: the migration replays on every deploy because the version stamp never lands, and the guard reads a column the writer never fills, and the whole batch runs again from the top on each release, and the counters disagree with the log and with each other, and the retry budget is spent before anyone looks at it, and the operator reads the dashboard at noon and files the incident, and the fix ships behind a flag nobody remembers to turn on, and the runbook still names a host that was retired last spring."
TWO_COPIES_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>long passages</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="t">Long passages</h1>
<section id="copies">
<p>Ahead of the first copy sits this line.</p>
<p id="first">{passage}</p>
<p>Between the copies sits this other line.</p>
<p id="second">{passage}</p>
</section>
</main>
</body>
</html>
""".replace("{passage}", LONG_PASSAGE)


def test_a_passage_longer_than_the_pattern_is_anchored_whole(browser, serve):
    """A quote is the passage, so what is stored is what the page marks and what the
    comment is on. It used to be cut at four hundred characters: a reader who selected
    a paragraph got a comment on its opening and a highlight that shrank to match, on
    most of the paragraphs a leaf page holds, and nothing said so. Storing the
    whole of it is only affordable because the bound moved to the search's pattern,
    which is what could not take a long passage — so this drags one past that bound and
    asks the mark, the log and the panel the same question, on the second of two
    identical copies, which is also the case where the lead alone cannot answer it."""
    url = serve(TWO_COPIES_PAGE)
    page, errors = open_page(browser, url)
    passage = page.locator("#second")
    picked = page.evaluate("() => document.querySelector('#second').textContent.length")
    assert picked > 400, "the fixture no longer outruns the pattern's own lead"

    # The whole paragraph, dragged: from its first glyph to its last.
    box = passage.bounding_box()
    select(
        page,
        (box["x"] + 1, box["y"] + 4),
        (box["x"] + box["width"] - 1, box["y"] + box["height"] - 4),
        steps=12,
    )
    expect(page.locator(".lf-fab")).to_be_visible()
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()

    # The mark under the open composer is the selection, both ends of it — and on the
    # copy the reader dragged, which only the stored neighbours can decide.
    on_the_selection = page.evaluate("""() => {
        const words = document.querySelector('#second').firstChild;
        const want = document.createRange();
        want.setStart(words, 0);
        want.setEnd(words, words.data.length);
        const painted = [...(CSS.highlights.get('lf-pending') ?? [])];
        if (!painted.length) return 'no mark';
        return [
          painted[0].compareBoundaryPoints(Range.START_TO_START, want) === 0,
          painted.at(-1).compareBoundaryPoints(Range.END_TO_END, want) === 0,
          painted.map((r) => r.toString()).join('').length,
        ];
    }""")
    assert on_the_selection == [True, True, picked], (
        f"the mark is not the passage that was dragged ({on_the_selection}, "
        f"wanted [True, True, {picked}])"
    )

    # And the anchor that posts says the same thing, since the mark is drawn from it.
    page.locator(".lf-composer textarea").fill("The whole of it.")
    page.locator(".lf-composer button.primary").click()
    round_trip(page)
    expect(page.locator(".lf-thread")).to_have_count(1)
    expect(page.locator(".lf-thread .lf-quote")).not_to_have_class(
        re.compile("detached")
    )
    anchor = [
        e["anchor"] for e in interact.read_events(serve.page_dir) if e.get("anchor")
    ][-1]
    assert len(anchor["quote"]) == picked, (
        f"the log holds {len(anchor['quote'])} characters of a {picked}-character "
        "passage"
    )
    assert anchor["prefix"].endswith("this other line."), (
        f"the neighbour naming which copy was picked is {anchor['prefix']!r}"
    )
    assert errors == []
    page.close()


# Prose past the pattern's own ceiling. One expression with a term per character stops
# compiling somewhere past ten thousand of them — measured on the gallery: 1.3ms at four
# hundred characters, 11.6ms at five thousand, a SyntaxError at twelve — and the throw
# would land inside the pass that draws every mark on the page, not just this one's. A
# reader reaches it in one keystroke, so the guard is a page long enough to prove it.
CEILING_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>everything</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="t">Everything</h1>
{paras}
</main>
</body>
</html>
""".format(
    paras="\n".join(
        f"<p>Paragraph {i} of the record. "
        + f"The deploy replays and the guard reads a column the writer never fills, "
        f"so the whole batch runs again from the top on release {i}. " * 3 + "</p>"
        for i in range(40)
    )
)


def test_a_selection_of_the_whole_page_still_finds_its_passage(browser, serve):
    """Select-all and comment. The quote is then the page, which is past what a search
    built from the whole of one can compile at all — and a throw there is not a missing
    mark but every mark, since one pass draws them. The bound is the pattern's, so the
    lead finds the candidates and the rest of the quote is walked from each; what this
    asks is that the passage is still found, on the pass that runs after the send as
    much as on the one under the composer."""
    url = serve(CEILING_PAGE)
    page, errors = open_page(browser, url)
    prose = page.evaluate("() => document.querySelector('main').textContent.length")
    assert prose > 12000, f"the fixture holds {prose} characters, under the ceiling"

    page.keyboard.press("ControlOrMeta+a")
    expect(page.locator(".lf-fab")).to_be_visible()
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    painted = page.evaluate(
        "() => [...(CSS.highlights.get('lf-pending') ?? [])]"
        ".map((r) => r.toString()).join('').length"
    )
    assert painted > 12000, f"the mark under the composer covers {painted} characters"

    page.locator(".lf-composer textarea").fill("All of it.")
    page.locator(".lf-composer button.primary").click()
    round_trip(page)
    expect(page.locator(".lf-thread")).to_have_count(1)
    # The posted anchor resolves on the ordinary pass too, which is the one that would
    # have thrown: a detached quote here is the search having failed to find the page
    # inside the page.
    expect(page.locator(".lf-thread .lf-quote")).not_to_have_class(
        re.compile("detached")
    )
    assert errors == []
    page.close()


# A passage that opens its section stores no prefix — note there is no whitespace between
# the section tag and the paragraph, which is what makes the copy's leading context empty
# rather than short. Both copies carry the identical tail, so a suffix on its own is a bar
# the other copy clears just as well.
THIN_V1 = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>thin</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="t">Thin</h1>
<section id="thin"><p>{phrase}. Retries are capped at three.</p>
<p>An unrelated middle paragraph.</p>
<p>Queue drain runs first. {phrase}. Retries are capped at three.</p>
</section>
</main>
</body>
</html>
""".replace("{phrase}", "The version stamp never lands")
# Only the commented copy's tail changes, so the untouched copy is now the better match for
# the one neighbour the comment stored.
THIN_V2 = THIN_V1.replace(
    "lands. Retries are capped at three.</p>\n<p>An unrelated",
    "lands. Backoff is capped at three.</p>\n<p>An unrelated",
)


def test_one_neighbour_is_not_enough_to_identify_a_revised_comment(browser, serve):
    """Context may place a comment only where both of a passage's neighbours are still
    there. A passage at the edge of its section has just one, and one is a bar another copy
    clears — so a revision that rewrites the commented copy's only neighbour would hand the
    comment to a copy it was never made on, silently, a version after anyone was looking.
    The cost of refusing is visible instead: the thread detaches until a later version
    makes its passage unique again."""
    url = serve(THIN_V1)
    page, errors = open_page(browser, url)
    posted = page.evaluate("""async () => {
        const p = document.querySelectorAll('#thin p')[0];
        const phrase = 'The version stamp never lands';
        const at = p.firstChild.data.indexOf(phrase);
        const want = document.createRange();
        want.setStart(p.firstChild, at); want.setEnd(p.firstChild, at + phrase.length);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        await new Promise(r => setTimeout(r, 40));
        const fab = document.querySelector('.lf-fab');
        if (fab.style.display !== 'block') return 'no button';
        fab.click();
        await new Promise(r => setTimeout(r, 40));
        const box = document.querySelector('.lf-composer textarea');
        box.value = 'does this hold?';
        box.dispatchEvent(new Event('input', {bubbles: true}));
        document.querySelector('.lf-composer button.primary').click();
        return true;
    }""")
    assert posted is True, f"couldn't post the comment ({posted})"
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    d = serve.page_dir
    (d / "versions" / "v2.html").write_text(THIN_V2)
    interact.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "revised"}
    )
    page.wait_for_url("**/v2.html")
    expect(page.locator(".lf-thread .lf-quote.detached")).to_have_count(1)
    assert page.evaluate("() => CSS.highlights.get('lf-mark')?.size ?? 0") == 0
    assert errors == []
    page.close()


def test_the_picker_runs_in_number_order_past_v9(browser, serve):
    """A version stays an integer from the server through runtime state; only the
    picker and URL boundary render its file name. Order the versions by those names
    instead and v10 lands between v1 and v2: the picker reads out of sequence,
    the diff offers the wrong base, and a reader on the newest version is told a
    newer one is waiting."""
    url = serve(INLINE_PAGE)
    for n in range(2, 11):
        _publish(serve.page_dir, n, INLINE_PAGE, f"cut {n}")
    page, errors = open_page(browser, url.replace("v1.html", "v10.html"))

    # The menu is built whether or not it is open, so the order is readable without
    # a press — and the press is not what this test is about.
    rows = page.locator(".lf-version-menu .lf-version-row .lf-version-num")
    expect(rows).to_have_count(10)
    assert [t.split(" ")[0] for t in rows.all_text_contents()] == [
        f"v{n}" for n in range(1, 11)
    ]
    expect(rows.last).to_have_text("v10 (latest)")
    # The bases a diff can run against are every version older than this one, so the
    # last press in the menu is v9 — and it is the one the page's own = reaches for,
    # which is the reading of "the version before this" that the ordering decides.
    presses = page.locator(".lf-version-diff")
    expect(presses).to_have_count(9)
    expect(presses.last).to_have_attribute("data-lf-version", "9")
    page.keyboard.press("=")
    expect(page.locator(".lf-version")).to_have_attribute(
        "title", re.compile(r"changed since v9 ")
    )
    # Nothing is newer than v10, so no chip offers one.
    expect(page.locator(".lf-latest-chip")).to_be_hidden()
    assert errors == []
    page.close()

    # Pinned to the oldest, the chip naming the newest is the runtime's one place
    # that spells a version out in a sentence.
    page, errors = open_page(browser, url, pin=True)
    expect(page.locator(".lf-latest-chip")).to_have_text(
        "New version available → open v10"
    )
    assert errors == []
    page.close()


def test_the_version_menu_is_worked_by_pointer_and_key(browser, serve):
    """The chooser is a press and a menu rather than a select, which buys the notes
    somewhere they can be read whole and costs the platform's own popup: opening,
    closing, and the keys between. A select came with all of that, so what this
    asserts is the part that had to be written back — the press toggles rather than
    only opens, focus lands on the version being read so the walk starts where the
    reader is, ↑/↓ clamp at the ends, Escape hands focus back to the press it came
    from, and a click anywhere else closes without navigating.

    The note is the reason the menu exists at all: a select's closed label is its
    selected option's whole text, so the note had to be on the bar or nowhere, and on
    the bar it ellipsized. Here it wraps."""
    long_note = (
        "a note far too long to have ever fitted on the bar, which is the whole "
        "reason the notes moved off it and into a list that can give them a line each"
    )
    url = serve(INLINE_PAGE)
    _publish(serve.page_dir, 2, INLINE_PAGE, long_note)
    _publish(serve.page_dir, 3, INLINE_PAGE, "third")
    # Pinned to v2, so there is a version either side of the one being read.
    page, errors = open_page(browser, url.replace("v1.html", "v2.html"), pin=True)

    btn = page.locator(".lf-version")
    menu = page.locator(".lf-version-menu")
    expect(btn).to_have_text("v2 ▾")
    expect(btn).to_have_attribute("aria-expanded", "false")
    expect(menu).to_be_hidden()

    btn.click()
    expect(menu).to_be_visible()
    expect(btn).to_have_attribute("aria-expanded", "true")
    # The walk starts on the version being read, not at the top of the list.
    expect(page.locator('.lf-version-row[data-lf-version="2"]')).to_be_focused()
    # The note is the whole note, on its own lines under the version it belongs to.
    expect(
        page.locator('.lf-version-row[data-lf-version="2"] .lf-version-note')
    ).to_have_text(long_note)
    assert page.evaluate(
        "() => { const n = document.querySelector("
        "'.lf-version-row[data-lf-version=\"2\"] .lf-version-note');"
        "  return n.getBoundingClientRect().height > "
        "         parseFloat(getComputedStyle(n).fontSize) * 1.6; }"
    ), "the note that a select could not hold is on one line here too"

    # The corpus axe pass walks every example with this menu shut, so the role
    # relationship it declares open — a menu owning menuitems, named — is checked
    # nowhere else. A select carried all of that from the platform and this does not.
    result = Axe().run(
        page,
        options={
            "runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a"]},
            "resultTypes": ["violations"],
        },
    )
    assert [
        v["id"]
        for v in result.response["violations"]
        if v["impact"] in {"serious", "critical"}
    ] == []

    # The keys are one declaration, so the "?" reference names them too — a page with
    # a second version is the first that has a list to walk.
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_contain_text("In the versions menu")
    expect(page.locator(".lf-help")).to_contain_text("walk the versions")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-help")).not_to_have_class(re.compile("open"))
    expect(menu).to_be_visible()

    page.locator('.lf-version-row[data-lf-version="2"]').focus()
    page.keyboard.press("ArrowDown")
    expect(page.locator('.lf-version-row[data-lf-version="3"]')).to_be_focused()
    page.keyboard.press("ArrowDown")  # clamped: the last row keeps the focus
    expect(page.locator('.lf-version-row[data-lf-version="3"]')).to_be_focused()
    page.keyboard.press("ArrowUp")
    page.keyboard.press("ArrowUp")
    expect(page.locator('.lf-version-row[data-lf-version="1"]')).to_be_focused()
    page.keyboard.press("ArrowUp")  # clamped at the other end too
    expect(page.locator('.lf-version-row[data-lf-version="1"]')).to_be_focused()

    # Escape closes and hands focus back to the press, so the next Tab carries on
    # from the banner rather than from the top of the document.
    page.keyboard.press("Escape")
    expect(menu).to_be_hidden()
    expect(btn).to_be_focused()

    # v opens it from anywhere on the page, the way o opens the leaves board, and
    # lands on the version being read so the walk above is the next press rather than a
    # Tab-hunt across the banner. This menu is the only place the notes are, so what
    # each version changed is reachable by keyboard through this key or not at all.
    page.keyboard.press("v")
    expect(menu).to_be_visible()
    expect(page.locator('.lf-version-row[data-lf-version="2"]')).to_be_focused()
    # Inside the menu the letter is the menu's own — the newest version, tested where
    # it navigates — so Escape is what closes this.
    page.keyboard.press("Escape")
    expect(menu).to_be_hidden()
    expect(btn).to_be_focused()

    # A second press is a close, not a re-open: without that the outside-click
    # handler and the toggle would both run and the menu could never stand.
    btn.click()
    expect(menu).to_be_visible()
    btn.click()
    expect(menu).to_be_hidden()

    # A click on the page closes it and leaves the reader where they were.
    btn.click()
    expect(menu).to_be_visible()
    # A point in the page's left margin: outside the column, and well clear of a menu
    # that hangs from the right of the bar over whatever the column has at the top.
    page.mouse.click(30, 700)
    expect(menu).to_be_hidden()
    assert "/versions/v2.html" in page.url, "closing the menu navigated"

    # Choosing a row is the navigation, and the newest is the one that unpins.
    btn.click()
    page.locator('.lf-version-row[data-lf-version="3"]').click()
    page.wait_for_url(lambda u: u.endswith("/versions/v3.html"))
    assert errors == []
    page.close()


def test_a_version_published_under_an_open_menu_reaches_it(browser, serve):
    """The list is rebuilt rather than reconciled, and an open menu defers the
    rebuild so a version landing mid-walk can't take the focused row away. What
    that defers has to survive the deferral: the key saying the list is current
    was consumed before the deferral was checked, so a version published while
    the menu stood marked the change handled and never wrote the row. The menu
    then sat one version short for as long as nothing else was published — and
    the poll it needed had already been and gone, so nothing was coming."""
    url = serve(INLINE_PAGE)
    _publish(serve.page_dir, 2, INLINE_PAGE, "two")
    page, errors = open_page(browser, url, pin=True)
    menu = page.locator(".lf-version-menu")
    expect(page.locator(".lf-version-row")).to_have_count(2)

    page.locator(".lf-version").click()
    expect(menu).to_be_visible()
    _publish(serve.page_dir, 3, INLINE_PAGE, "three")
    told(page)  # the poll that carries it has been and gone
    # Deferred, so the walk the reader is in the middle of is undisturbed.
    expect(page.locator(".lf-version-row")).to_have_count(2)

    page.keyboard.press("Escape")
    expect(menu).to_be_hidden()
    # And it arrives on the next poll rather than waiting on a fourth version.
    expect(page.locator(".lf-version-row")).to_have_count(3)
    expect(page.locator(".lf-version-row").last).to_contain_text("v3 (latest)")
    assert errors == []
    page.close()


def test_the_newest_version_is_the_chooser_key_twice(browser, serve):
    """A pinned page stays where the reader put it and offers the newest as a chip. The
    keyboard reaches that chip's destination through the chooser rather than past it: v
    opens the menu and the letter again takes the newest version, by that row's own
    press, so the key leaves through the door the pointer uses and the pin lifts with it.

    Which is the newest row, not the row the walk stands on — that one is Enter's, and a
    reader who has walked away from where they started must still be able to say "the
    current state" in one press. And the second press carries no liveness of its own,
    which is the point of spelling the move this way: the menu always has a newest row,
    so the motion holds wherever the reader is — including on the page already reading
    that row, where a key of the page's own would have had to stand down and every
    surface say so."""
    url = serve(INLINE_PAGE)
    _publish(serve.page_dir, 2, INLINE_PAGE, "two")
    _publish(serve.page_dir, 3, INLINE_PAGE, "three")
    page, errors = open_page(browser, url, pin=True)
    menu = page.locator(".lf-version-menu")
    help_el = page.locator(".lf-help")
    expect(page.locator(".lf-latest-chip")).to_be_visible()

    # The menu's keys are one declaration, so the reference names this one beside the
    # walk it saves.
    page.keyboard.press("?")
    expect(help_el).to_contain_text("open the newest version")
    page.keyboard.press("Escape")

    # The first press opens and goes nowhere. A whole poll passes before the reading,
    # which is far longer than a navigation would take to start.
    page.keyboard.press("v")
    expect(menu).to_be_visible()
    told(page)
    assert page.url.endswith("pin"), "the press that opens the menu navigated"

    # Walk off the version being read, so the row under the focus is not the newest and
    # not the one this press takes.
    page.keyboard.press("ArrowDown")
    expect(page.locator('.lf-version-row[data-lf-version="2"]')).to_be_focused()
    page.keyboard.press("v")
    # No query: the newest version is the one that unpins, whichever route reaches it.
    page.wait_for_url(lambda u: u.endswith("/versions/v3.html"))
    # The rebuilt list is what says the page arriving here has heard from the server.
    # A hidden chip does not: that is also how the banner stands before the first poll,
    # so an assertion on it alone would read the same on a page that had heard nothing —
    # and the reference below is written by that same poll.
    expect(page.locator(".lf-version-row")).to_have_count(3)
    expect(page.locator(".lf-latest-chip")).to_be_hidden()

    # And it is still offered here, with the chip gone: opening the newest version is
    # what the press does on the page already reading it, so no surface stands it down.
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    expect(help_el).to_contain_text("open the newest version")
    assert errors == []
    page.close()


def test_the_menu_compares_with_any_version_older_than_this_one(browser, serve):
    """A page that ships a version whenever the work moves leaves its reader behind by
    more than one, and "what changed since the previous version" is then the wrong
    question: what they want marked is everything since they last looked. The base was
    the previous version for exactly as long as it was a control's own label — one
    button can name one version — so the menu is where it stops being one, and every row
    older than this one offers itself.

    The rest is what the reader can tell afterwards: the closed control says a
    comparison is standing, and reopening says which one, on the rows it spans."""
    v2 = INLINE_PAGE.replace("A neighbouring block", "A neighbouring passage")
    v3 = v2.replace("The setup is in the runbook", "The setup is in the handbook")
    url = serve(INLINE_PAGE)
    _publish(serve.page_dir, 2, v2, "reworded the neighbour")
    _publish(serve.page_dir, 3, v3, "reworded the compound")
    page, errors = open_page(browser, url.replace("v1.html", "v3.html"))

    # The previous version: the one change this version made.
    compare_with(page, 2)
    expect(page.locator(".lf-ins-block")).to_have_count(1)
    expect(page.locator("#compound")).to_have_class(re.compile(r"\blf-ins-block\b"))

    # Two versions back, which no single-label control could have offered: both.
    compare_with(page, 1)
    expect(page.locator(".lf-ins-block")).to_have_count(2)
    expect(page.locator("#p2")).to_have_class(re.compile(r"\blf-ins-block\b"))

    # What the closed chooser says about it — a word, not the accent alone, since a
    # reader in a stretch that changed nothing has only this to read it back off.
    expect(page.locator(".lf-version")).to_have_text("Δ v3 ▾")
    page.locator(".lf-version").click()
    expect(page.locator('.lf-version-diff[data-lf-version="1"]')).to_have_attribute(
        "aria-checked", "true"
    )
    expect(page.locator('.lf-version-diff[data-lf-version="2"]')).to_have_attribute(
        "aria-checked", "false"
    )
    # And the span it covers, which is what a base three versions back makes worth
    # saying: the rail runs from it to the version being read.
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-version-row.lf-compared')]"
        ".map(r => r.dataset.lfVersion)"
    ) == ["1", "2", "3"]

    # Pressing the standing base again is the way off, and it takes the marks and the
    # word with it.
    page.locator('.lf-version-diff[data-lf-version="1"]').click()
    expect(page.locator(".lf-ins-block")).to_have_count(0)
    expect(page.locator(".lf-version")).to_have_text("v3 ▾")

    # From the keyboard the press is a Tab off the row it belongs to, which is what
    # puts the walk's own landing spot next to it: the menu takes no key for this,
    # since the row it opens on is the version being read and that is the one row with
    # nothing to compare against.
    page.locator(".lf-version").click()
    page.locator('.lf-version-row[data-lf-version="1"]').focus()
    page.keyboard.press("Tab")
    expect(page.locator('.lf-version-diff[data-lf-version="1"]')).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-ins-block")).to_have_count(2)

    # The page's own = is the way off a comparison whatever it is against, which is why
    # the key stays live under one; with nothing standing it takes the previous
    # version, as it always did.
    page.keyboard.press("=")
    expect(page.locator(".lf-ins-block")).to_have_count(0)
    page.keyboard.press("=")
    expect(page.locator(".lf-ins-block")).to_have_count(1)
    assert errors == []
    page.close()


def test_a_diff_anchors_to_the_side_it_was_read_on(browser, serve):
    """The case this exists for, and the one a section cannot narrow: a diff carries the
    same line added and removed under a single id, so the user commenting on the fix
    had their comment marked against the bug — stored that way, and shown to Claude that
    way in the next round.

    The passage is picked out of the rendered widget, where syntax colour has cut the
    line into spans: `return` is a keyword and ` request.path` is the text after it, so
    the selection starts in one node and ends in another. That is the ordinary shape of a
    passage in a coloured block, and the anchor knows nothing about it — a span is no text
    block, so both readings still collapse to the same run of characters."""
    page, errors = open_page(browser, serve(TWICE_PAGE))
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    landed = page.evaluate("""async () => {
        const skip = '.lf-ui, script, style';
        // Rooted at the shadow root: lf-diff renders in one (x-shadow), so the lines
        // this drags across are in the composed tree and not under the host element.
        const w = document.createTreeWalker(document.getElementById('patch').shadowRoot,
            NodeFilter.SHOW_TEXT,
            {acceptNode: n => n.parentElement?.closest(skip)
                ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT});
        // One flat run over the widget's text nodes, and where each node started in it,
        // so a phrase is found whether or not a token boundary falls inside it.
        const nodes = [], starts = [];
        let flat = '';
        for (let n = w.nextNode(); n; n = w.nextNode()) {
            starts.push(flat.length); nodes.push(n); flat += n.data;
        }
        const phrase = 'return request.path';
        const hits = [];
        for (let i = flat.indexOf(phrase); i !== -1; i = flat.indexOf(phrase, i + 1)) hits.push(i);
        if (hits.length < 2) return `only ${hits.length} occurrence(s) — fixture broken`;
        const at = (offset) => {
            const i = starts.findLastIndex((s) => s <= offset);
            return [nodes[i], offset - starts[i]];
        };
        const start = hits.at(-1);   // the added line: the later of the pair
        const want = document.createRange();
        want.setStart(...at(start)); want.setEnd(...at(start + phrase.length));
        if (want.startContainer === want.endContainer)
            return 'the phrase sat in one node — colour never split it, so this proves nothing';
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        await new Promise(r => setTimeout(r, 40));
        const fab = document.querySelector('.lf-fab');
        if (fab.style.display !== 'block') return 'no button';
        fab.click();
        await new Promise(r => setTimeout(r, 40));
        const painted = [...(CSS.highlights.get('lf-pending') ?? [])][0];
        if (!painted) return 'no mark';
        return painted.compareBoundaryPoints(Range.START_TO_START, want) === 0;
    }""")
    assert landed is True, (
        f"the added line was picked, the mark went elsewhere ({landed})"
    )
    assert errors == []
    page.close()


def test_an_id_staged_into_a_shadow_tree_is_still_the_pages_id(browser, serve):
    """Every question the runtime asks by id goes through one lookup, and a widget that
    stages its authored children carries their ids into its shadow tree with them. While
    that lookup was the document's alone the answer came back null and each caller quietly
    did nothing — here, an anchor stored and a mark never painted, with no error to find.

    Staged by hand because the one shipped x-shadow widget builds its tree out of parsed
    data and mints no ids, so nothing reaches this yet; what the next one does is exactly
    this move. The clearing sweep is the other half — a mark the repaint cannot reach is
    a mark that outlives its reason — so the second comment has to take the first's place
    rather than stand beside it."""
    page, errors = open_page(browser, serve(TWICE_PAGE))
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    page.evaluate(
        "() => document.getElementById('patch').shadowRoot"
        ".querySelector('pre').id = 'row'"
    )
    # Through a locator: the paint lands on the poll that follows the write rather than
    # with it, so a read taken straight after passes on a quiet machine and fails on a
    # busy one. `#row` reaches into the open tree the way the runtime now has to.
    row = page.locator("#row")
    marked = re.compile(r"\blf-mark-el\b")
    d = serve.page_dir
    interact.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-staged",
            "author": "user",
            "version": 1,
            "text": "About the staged line.",
            "anchor": {"section": "row"},
        },
    )
    told(page)
    expect(row).to_have_class(marked)
    expect(row).to_contain_text("1 comment")

    # Resolved, so the next repaint has nothing to say here: the count line has to go,
    # and it can only go if the sweep that clears it enters the tree that holds it.
    interact.append_event(
        d, {"kind": "resolve", "author": "user", "parent": "c-staged"}
    )
    told(page)
    expect(row).not_to_have_class(marked)
    expect(row).not_to_contain_text("comment")
    assert not errors, errors
    page.close()


# The journey's page: a passage to comment on, a board to drag, and a draft to
# edit. In v2 the commented paragraph moves below the notes heading — same text,
# new position — so the anchor has to re-find its passage rather than replay a
# location. The draft's source lines are indented like any other child content;
# the widget owes the user the text without them.
SENTENCE = "The version stamp never lands, so migration 0041 replays on every deploy."
DRAFT_TEXT = "Run the migration before deploying.\nIt is online."
DRAFT_EDITED = "Run the migration before deploying. It takes about a minute."
JOURNEY_SCAFFOLD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>journey</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""
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


def test_page_round_trip(browser, serve):
    """The loop the product is, driven through the real UI: select a passage and
    comment on it, drag a card to another column, rewrite a draft in place, then
    follow the next version and find the comment still anchored to its
    (relocated) passage and the draft still wearing the user's words. The
    final assertion is the event log — the trail Claude reads — down to the
    anchor's quote, the move's placement, and the edit's text."""
    page, errors = open_page(browser, serve(JOURNEY_V1))

    # Select the passage from the keyboard's path: a real Range, then the keyup
    # the runtime watches for keyboard selections, then the c binding — which
    # runs the same the fab's own click as the floating button's click.
    page.evaluate("""() => {
        const r = document.createRange();
        r.selectNodeContents(document.getElementById('intro'));
        getSelection().removeAllRanges();
        getSelection().addRange(r);
        document.body.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
    }""")
    page.wait_for_selector(
        ".lf-fab", state="visible"
    )  # the selection raised the button
    page.keyboard.press("c")
    page.wait_for_selector(".lf-composer", state="visible")
    page.locator(".lf-composer textarea").fill("Is 0041 idempotent?")
    page.locator(".lf-composer").get_by_role("button", name="Comment").click()
    page.wait_for_selector(".lf-thread")
    # The anchor pass painted the passage — a range in the highlight registry, not an
    # element, so there is no selector for it.
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Posting opened the panel, and the page is sliding into the width that leaves for
    # it. Measuring a column mid-slide aims the drag below at where it was, not where
    # it is going, and the drop lands outside the column it was meant for.
    panel_settled(page)

    # Drag the card between columns through the pointer path — the seam where
    # the vendored SortableJS meets the runtime, which is where drags break.
    grip = page.locator("#card-x .lf-grip").bounding_box()
    dest = page.locator("#col-done").bounding_box()
    page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
    page.mouse.down()
    page.mouse.move(
        dest["x"] + dest["width"] / 2, dest["y"] + dest["height"] / 2, steps=15
    )
    page.mouse.up()
    page.wait_for_selector("#col-done #card-x")  # the drop reparented the card

    # Rewrite the draft through its fast path: double-click opens the text in
    # place (winning over the word-selection the gesture makes — no comment
    # button contests it), Save sends the whole new body. The text must have
    # arrived without the source's indentation.
    draft = page.locator("#draft-ops")
    assert draft.locator(".lf-draft-body").inner_text() == DRAFT_TEXT
    draft.locator(".lf-draft-body").dblclick()
    draft.locator("textarea").fill(DRAFT_EDITED)
    draft.get_by_role("button", name="Save").click()
    page.wait_for_function(
        "t => document.querySelector('#draft-ops .lf-draft-body').textContent === t",
        arg=DRAFT_EDITED,
    )

    # Every gesture above must be in the log before v2's note lands, or the trail below
    # would interleave. The page posted them, so the page is what says they are all in:
    # polling the file for one of them would be a second reading of the same trip, and a
    # narrower one — it can only ever ask after the send it happens to name.
    d = serve.page_dir
    round_trip(page)

    # Claude ships v2 with the passage moved; the page follows on its next poll.
    (d / "versions" / "v2.html").write_text(JOURNEY_V2)
    interact.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "moved"}
    )
    page.wait_for_url("**/v2.html")
    # The anchor pass runs at render: a mark now means the quote was re-found in
    # its new position; no mark within the wait means the anchor lost it.
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert not page.evaluate(
        "document.querySelector('.lf-thread .lf-quote').classList.contains('detached')"
    ), "the passage moved and the comment lost it"
    # v2's markup carries the original draft text — Claude hasn't honored the
    # edit — so the user's words must arrive by replay, not visibly revert.
    page.wait_for_function(
        "t => document.querySelector('#draft-ops .lf-draft-body').textContent === t",
        arg=DRAFT_EDITED,
    )

    assert errors == []
    # The trail those gestures left, exactly — kinds, authorship (the server
    # stamps browser events `user`), the anchor, and the move's placement.
    events = [
        json.loads(line) for line in (d / "comments.jsonl").read_text().splitlines()
    ]
    assert [(e["kind"], e["author"], e["version"]) for e in events] == [
        ("note", "claude", 1),
        ("comment", "user", 1),
        ("action", "user", 1),
        ("action", "user", 1),
        ("note", "claude", 2),
    ]
    # The board after the paragraph is module-rendered and therefore an opaque
    # passage cell. Context stops at that shared browser/file fence.
    assert events[1]["anchor"] == {
        "section": "intro",
        "quote": SENTENCE,
        "prefix": "Journey",
    }
    assert events[1]["text"] == "Is 0041 idempotent?"
    assert {k: events[2][k] for k in ("widget", "action", "detail")} == {
        "widget": "board",
        "action": "move",
        "detail": {"card": "card-x", "to": "col-done", "index": 0},
    }
    assert {k: events[3][k] for k in ("widget", "action", "detail")} == {
        "widget": "draft-ops",
        "action": "edit",
        "detail": {"text": DRAFT_EDITED},
    }
    page.close()


def test_a_comment_inside_a_widget_stays_out_of_what_the_widget_reads(browser, serve):
    """The line that tells a screen reader a block carries a comment is chrome, and chrome
    inside a widget's own content is chrome in the user's text: lf-draft seeds the
    editor they type into from its body div, so a line left in there arrives in the
    textarea and posts with the edit. It goes on the block the passage sits in, or on the
    element the anchor names — never on the inline run or body div in between."""
    url = serve(
        JOURNEY_V1, anchored=[("draft-ops", "Run the migration before deploying.")]
    )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert page.locator("#draft-ops > .lf-mark-note").count() == 1, (
        "the line landed inside the draft's body rather than beside it"
    )
    page.locator("#draft-ops .lf-draft-body").dblclick()
    assert page.locator("#draft-ops textarea").input_value() == DRAFT_TEXT, (
        "the user's editor opened on text the runtime had written into"
    )
    assert errors == []
    page.close()


def test_double_clicking_a_draft_leaves_every_word_where_it_was(browser, serve):
    """Two halves of one gesture, both of them invisible to a static lint.

    The box: reading and editing are the same box, so the words a user
    double-clicked are still under the pointer when the editor opens. They were
    not — the runtime's general textarea rule wraps text in padding and a border
    and floors it at 64px, which moved the first character 9px right and 6px down
    and stretched a two-line draft — and text that jumps out from under a
    double-click is the user's aim thrown away.

    The gesture: the word the browser would select is selected by the second
    mousedown and painted before dblclick arrives, so the handler that cleared it
    afterwards ran a frame late and the user saw a flash. That frame is
    timing, and no assertion here reaches it; what is assertable is the outcome
    on either side of it. Nothing on the page ends up selected, and the word the
    gesture named opens selected in the box — which is what a double-click means
    everywhere else, and what cancelling the default rather than undoing it is
    for.

    The block around them counts too: the whole draft has to keep its shape, or a
    gesture aimed at one word is answered by everything under it moving. Cancel and
    Save join a row the draft always has rather than arriving as one, which is worth
    a measurement because the row is invisible in the diff that matters — both views
    lay out fine on their own, and only the two together say whether the box moved.

    And the swap is the screen's, which is why the widget writes none of it: paper
    drops the box with the other offers, so a draft mid-edit printed as an empty
    frame for as long as the module hid the body itself."""
    page, errors = open_page(browser, serve(JOURNEY_V1))
    metrics = """(sel) => {
      const el = document.querySelector('#draft-ops ' + sel), s = getComputedStyle(el);
      const b = el.getBoundingClientRect();
      return [b.x + parseFloat(s.paddingLeft) + parseFloat(s.borderLeftWidth),
              b.y + parseFloat(s.paddingTop) + parseFloat(s.borderTopWidth), b.width, b.height];
    }"""
    read = page.evaluate(metrics, ".lf-draft-body")
    host = page.locator("#draft-ops").bounding_box()
    # A 4px band above the box, and the box's own top-left corner. The band is where
    # the answer to "did the frame move" lives and no measurement of geometry can
    # reach it: an outset ring is paint, so every rect stayed exactly as asserted
    # below while the frame the user sees grew 2px on every side, corners
    # rounding wider to match. Bytes, not pixels — the same encoder over the same
    # content gives the same file, so identical files are identical paint.
    band = {
        "x": host["x"] - 4,
        "y": host["y"] - 4,
        "width": host["width"] + 8,
        "height": 4,
    }
    inside = {"x": host["x"], "y": host["y"], "width": 40, "height": 40}
    outside_before = page.screenshot(clip=band)
    inside_before = page.screenshot(clip=inside)

    # Aimed at where the browser actually drew the word, not at an offset from the
    # box's edge. A pixel count is a fact about one font: 60px into this line was
    # "migration" while the theme set drafts in 16px system-ui, and lands in "the"
    # now that it sets them in 17px Charter — so the test read as "the editor opens
    # on the wrong word" when nothing about the gesture had changed.
    spot = page.evaluate(
        """(word) => {
            const body = document.querySelector('#draft-ops .lf-draft-body');
            const node = document.createTreeWalker(body, NodeFilter.SHOW_TEXT).nextNode();
            const at = node.data.indexOf(word);
            const r = document.createRange();
            r.setStart(node, at); r.setEnd(node, at + word.length);
            const b = r.getBoundingClientRect();
            return [b.x + b.width / 2, b.y + b.height / 2];
        }""",
        "migration",
    )
    page.mouse.dblclick(*spot)
    editor = page.locator("#draft-ops textarea")
    expect(editor).to_be_focused()
    assert page.screenshot(clip=band) == outside_before, (
        "opening the editor painted outside the box the draft already occupied"
    )
    assert page.screenshot(clip=inside) != inside_before, (
        "the open editor is indistinguishable from the read view at the box's edge"
    )
    assert page.evaluate(metrics, "textarea") == read, (
        "the editor's text sits somewhere the read view's text did not"
    )
    assert page.locator("#draft-ops").bounding_box() == host, (
        "the draft changed shape under the pointer when the editor opened"
    )
    assert (
        page.evaluate(
            "() => getSelection().rangeCount > 0 && "
            "getSelection().containsNode(document.querySelector('#draft-ops .lf-draft-body'), true)"
        )
        is False
    ), "the gesture left the page's own words selected under the open editor"
    selected = page.evaluate(
        "() => { const t = document.querySelector('#draft-ops textarea');"
        "        return t.value.slice(t.selectionStart, t.selectionEnd); }"
    )
    assert selected == "migration", (
        f"the box opened on {selected!r} rather than the word clicked"
    )

    # Closing states both properties in reverse, and the focus half is a question
    # only because the ✎ is CSS-hidden for as long as the editor is there: #close
    # reaches for it the instant the editor goes, so a style that hadn't caught up
    # would drop a keyboard user back at the top of the page.
    page.keyboard.press("Escape")
    expect(page.locator("#draft-ops .lf-draft-pencil")).to_be_focused()
    assert page.locator("#draft-ops").bounding_box() == host, (
        "the draft came back from an edit a different shape than it went in"
    )

    # Reopened through the other door, because print is where the box has to be
    # gone and its words still there — and print emulation blurs the textarea it
    # hides, so an editor opened before this point is no longer one Escape closes.
    page.locator("#draft-ops .lf-draft-pencil").click()
    expect(page.locator("#draft-ops textarea")).to_be_visible()
    page.emulate_media(media="print")
    assert page.locator("#draft-ops").inner_text() == DRAFT_TEXT, (
        "the printed page lost the draft's words to a box paper hasn't got"
    )
    page.emulate_media(media="screen")
    assert errors == []
    page.close()


def test_a_foreign_edit_waits_for_a_live_draft_and_replays_in_order(browser, serve):
    """Replay never replaces words while the user is typing them.

    Deferring one edit must also hold later edits for that draft: otherwise the
    later absolute value lands first and the deferred earlier value overwrites it
    when the box closes. An unrelated board move proves the poll saw the same
    batch while the editor was open, without making the test depend on time.
    """
    page, errors = open_page(browser, serve(JOURNEY_V1))
    draft = page.locator("#draft-ops")
    draft.locator(".lf-draft-body").dblclick()
    editor = draft.locator("textarea")
    editor.fill("Local unsent words.")

    d = serve.page_dir
    for text in ("Foreign first edit.", "Foreign committed words."):
        interact.append_event(
            d,
            {
                "kind": "action",
                "author": "user",
                "version": 1,
                "widget": "draft-ops",
                "action": "edit",
                "detail": {"text": text},
            },
        )
    interact.append_event(
        d,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "board",
            "action": "move",
            "detail": {"card": "card-x", "to": "col-done", "index": 0},
        },
    )

    told(page)
    expect(page.locator("#col-done #card-x")).to_have_count(1)
    expect(editor).to_have_value("Local unsent words.")
    expect(draft.locator(".lf-draft-history")).to_have_count(0)

    page.keyboard.press("Escape")
    told(page)
    expect(draft.locator(".lf-draft-body")).to_have_text("Foreign committed words.")
    expect(draft.locator(".lf-draft-history > summary")).to_have_text(
        "Changes · 2 edits"
    )
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "3")
    assert errors == []
    page.close()


def test_an_empty_draft_survives_reload_and_blocks_a_version_switch(browser, serve):
    """Empty text is a real replacement, not the absence of a saved draft. Deleting
    the whole body must survive reload, keep the current version under the active
    editor, and arrive in the log as an ordinary absolute edit."""
    url = serve(JOURNEY_V1)
    page, errors = open_page(browser, url)
    draft = page.locator("#draft-ops")
    draft.locator(".lf-draft-body").dblclick()
    draft.locator("textarea").fill("")
    assert (
        page.evaluate(
            """() => JSON.parse(
          sessionStorage.getItem('lf-draft:edit:draft-ops')
        ).text"""
        )
        == ""
    )

    d = serve.page_dir
    (d / "versions" / "v2.html").write_text(JOURNEY_V2)
    interact.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "v2"}
    )
    told(page)
    expect(page.locator(".lf-latest-chip")).to_be_visible()
    assert "/v1.html" in page.url, "an empty live edit was mistaken for no composition"

    page.reload(wait_until="networkidle")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    expect(draft.locator("textarea")).to_be_visible()
    expect(draft.locator("textarea")).to_have_value("")

    page.evaluate(
        """() => {
          window.lfActualFetch = window.fetch.bind(window);
          window.lfFailDraft = true;
          window.fetch = (input, init) => {
            const event = String(input).endsWith('/api/event') && init?.body
              ? JSON.parse(init.body) : null;
            if (window.lfFailDraft &&
                event?.kind === 'action' && event.action === 'edit')
              return Promise.resolve(new Response('offline', {status: 503}));
            return window.lfActualFetch(input, init);
          };
        }"""
    )
    draft.get_by_role("button", name="Save").click()
    expect(draft.locator("textarea")).to_be_focused()
    expect(draft.locator("textarea")).to_have_value("")
    assert (
        page.evaluate(
            """() => JSON.parse(
          sessionStorage.getItem('lf-draft:edit:draft-ops')
        ).text"""
        )
        == ""
    )

    page.evaluate("window.lfFailDraft = false")
    draft.get_by_role("button", name="Save").click()
    page.wait_for_url("**/v2.html")
    expect(page.locator("#draft-ops .lf-draft-body")).to_have_text("")
    page.wait_for_function(
        "() => sessionStorage.getItem('lf-draft:edit:draft-ops') === null"
    )
    events = [
        json.loads(line)
        for line in (d / "comments.jsonl").read_text().splitlines()
        if '"kind": "action"' in line
    ]
    assert events[-1]["action"] == "edit"
    assert events[-1]["detail"] == {"text": ""}
    assert errors == []
    page.close()


def test_a_draft_send_owns_the_editor_until_its_response(browser, serve):
    """A second gesture cannot overtake an earlier request or let that request clear
    newer unsent text. Hold the first POST in the browser: while it owns the draft,
    every edit door stays closed and the exact body remains recoverable."""
    page, errors = open_page(browser, serve(JOURNEY_V1))
    page.evaluate(
        """() => {
          const actualFetch = window.fetch.bind(window);
          let held = true;
          window.fetch = (input, init) => {
            const event = String(input).endsWith('/api/event') && init?.body
              ? JSON.parse(init.body) : null;
            if (held && event?.kind === 'action' && event.action === 'edit') {
              return new Promise((resolve, reject) => {
                window.releaseDraftSend = () => {
                  held = false;
                  actualFetch(input, init).then(resolve, reject);
                };
              });
            }
            return actualFetch(input, init);
          };
        }"""
    )
    draft = page.locator("#draft-ops")
    sent = "The first save still owns this body."
    draft.locator(".lf-draft-body").dblclick()
    draft.locator("textarea").fill(sent)
    draft.get_by_role("button", name="Save").click()
    expect(draft).to_have_attribute("aria-busy", "true")
    assert (
        page.evaluate(
            """() => JSON.parse(
          sessionStorage.getItem('lf-draft:edit:draft-ops')
        ).text"""
        )
        == sent
    )

    draft.locator(".lf-draft-pencil").click()
    expect(draft.locator("textarea")).to_have_count(0)
    expect(page.locator(".lf-toast")).to_contain_text("Wait for the current edit")

    page.evaluate("window.releaseDraftSend()")
    page.wait_for_function(
        """() => !document.getElementById('draft-ops').hasAttribute('aria-busy')
          && sessionStorage.getItem('lf-draft:edit:draft-ops') === null"""
    )
    events = [
        json.loads(line)
        for line in (serve.page_dir / "comments.jsonl").read_text().splitlines()
        if '"kind": "action"' in line
    ]
    assert [event["detail"]["text"] for event in events] == [sent]

    draft.locator(".lf-draft-pencil").click()
    expect(draft.locator("textarea")).to_be_focused()
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_unsent_draft_recovery_belongs_to_its_tab(browser, serve):
    """Recorded edits converge through the log; unsent words do not. Two pages in
    one BrowserContext are real same-origin tabs, unlike Browser.new_page's isolated
    contexts. A send and a Cancel in one must leave the other's newer empty edit
    recoverable through a reload."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, color_scheme="light"
    )
    try:
        url = serve(JOURNEY_V1)
        first, first_errors = open_page(browser, url, context=context)
        second, second_errors = open_page(browser, url, context=context)
        first_draft = first.locator("#draft-ops")
        second_draft = second.locator("#draft-ops")

        sent = "The first tab submits this body."
        first_draft.locator(".lf-draft-body").dblclick()
        first_draft.locator("textarea").fill(sent)
        second_draft.locator(".lf-draft-body").dblclick()
        second_draft.locator("textarea").fill("")

        first_draft.get_by_role("button", name="Save").click()
        # The history summary arrives with the poll that answers the save, not with the
        # save, so asserting straight after the click spends expect's own budget on the
        # trip — which is a pass on a fast machine and a red on a loaded one, saying
        # nothing either way about the page.
        round_trip(first)
        expect(first_draft.locator(".lf-draft-history > summary")).to_have_text(
            "Changes · 1 edit"
        )
        expect(second_draft.locator("textarea")).to_have_value("")
        assert (
            second.evaluate(
                """() => JSON.parse(
              sessionStorage.getItem('lf-draft:edit:draft-ops')
            ).text"""
            )
            == ""
        )

        first_draft.locator(".lf-draft-body").dblclick()
        first_draft.locator("textarea").fill("This tab discards these words.")
        first.keyboard.press("Escape")
        assert (
            second.evaluate(
                """() => JSON.parse(
              sessionStorage.getItem('lf-draft:edit:draft-ops')
            ).text"""
            )
            == ""
        )

        second.reload(wait_until="networkidle")
        second.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
        expect(second_draft.locator("textarea")).to_be_visible()
        expect(second_draft.locator("textarea")).to_have_value("")
        events = [
            json.loads(line)
            for line in (serve.page_dir / "comments.jsonl").read_text().splitlines()
            if '"kind": "action"' in line
        ]
        assert [event["detail"]["text"] for event in events] == [sent]
        assert first_errors == []
        assert second_errors == []
    finally:
        context.close()


def test_text_alignment_is_lossless_and_keeps_a_shared_spine(browser, serve):
    """The draft renderer is allowed to choose where an ambiguous repeated word
    aligns, but never to lose or invent a character. The two projections are the
    contract: same+delete is the old text, same+insert the new one. Unicode,
    whitespace and repetition are where a character or regex diff quietly breaks."""
    page, errors = open_page(browser, serve(JOURNEY_V1))
    cases = [
        ("", ""),
        ("one line", "one longer line"),
        ("first\nsecond  line", "first\nsecond line\nthird"),
        ("l’écran est prêt 😀", "l’écran était prêt 🟢"),
        ("迁移完成。再次迁移。", "迁移完成。回滚完成。"),
        ("Retry once. Retry once. Then stop.", "Retry once. Retry twice. Then stop."),
        (
            "shared " + " ".join(f"old-{i}" for i in range(2500)) + " ending",
            "shared " + " ".join(f"new-{i}" for i in range(2500)) + " ending",
        ),
    ]
    aligned = page.evaluate(
        """async (pairs) => {
          const {alignText} = await import('/leaf.js');
          return pairs.map(([before, after]) => alignText(before, after));
        }""",
        cases,
    )
    for (before, after), runs in zip(cases, aligned):
        assert "".join(run["text"] for run in runs if run["kind"] != "insert") == before
        assert "".join(run["text"] for run in runs if run["kind"] != "delete") == after
        assert all(a["kind"] != b["kind"] for a, b in itertools.pairwise(runs))

    repeated = aligned[-2]
    assert "".join(r["text"] for r in repeated if r["kind"] == "delete") == "once"
    assert "".join(r["text"] for r in repeated if r["kind"] == "insert") == "twice"
    assert "Then stop." in "".join(r["text"] for r in repeated if r["kind"] == "same")
    assert [run["kind"] for run in aligned[-1]] == ["same", "delete", "insert", "same"]
    assert errors == []
    page.close()


def test_a_draft_explains_its_change_and_restores_history_as_an_edit(browser, serve):
    """One disclosure answers both deferred draft asks. It compares this version's
    authored body with the standing body, retains every absolute edit in log order,
    and walks back by posting another ordinary edit. A second tab proves restore is
    durable replay rather than local history state; copy mode proves the generated
    controls do not survive without their handlers."""
    page, errors = open_page(browser, serve(JOURNEY_V1))
    draft = page.locator("#draft-ops")
    edits = [
        "Run the migration before deploying. It takes one minute.",
        "Run the migration after the backup. It takes two minutes.",
    ]
    for index, text in enumerate(edits, 1):
        draft.locator(".lf-draft-body").dblclick()
        draft.locator("textarea").fill(text)
        draft.get_by_role("button", name="Save").click()
        round_trip(page)  # the history is drawn from the log, not the box
        expect(draft.locator(".lf-draft-history > summary")).to_have_text(
            f"Changes · {index} {'edit' if index == 1 else 'edits'}"
        )

    draft.locator(".lf-draft-history > summary").click()
    current_deleted = "".join(draft.locator(".lf-draft-current del").all_inner_texts())
    current_inserted = "".join(draft.locator(".lf-draft-current ins").all_inner_texts())
    assert "before" in current_deleted and "deploying" in current_deleted
    assert "afterthebackup" in re.sub(r"\s+", "", current_inserted)
    labels = draft.locator(".lf-draft-revision-head strong").all_inner_texts()
    assert labels == ["Version text", "Edit 1 · v1", "Edit 2 · v1"]
    # Adjacent recorded edits are aligned too, rather than rendered as two unrelated
    # snapshots. The first has no knowable predecessor on a later pinned version.
    second_delta = draft.locator(".lf-draft-revisions > li").nth(2)
    second_deleted = "".join(second_delta.locator("del").all_inner_texts())
    second_inserted = "".join(second_delta.locator("ins").all_inner_texts())
    assert "before" in second_deleted and "deploying" in second_deleted
    assert "afterthebackup" in re.sub(r"\s+", "", second_inserted)

    page.evaluate("document.documentElement.classList.add('lf-copy')")
    expect(draft.locator(".lf-draft-history")).not_to_be_visible()
    expect(draft.locator(".lf-draft-controls")).not_to_be_visible()
    expect(draft.locator(".lf-draft-body")).to_be_visible()
    page.evaluate("document.documentElement.classList.remove('lf-copy')")

    draft.get_by_role("button", name="Restore edit 1 · v1").focus()
    page.keyboard.press("Enter")
    round_trip(page)
    expect(draft.locator(".lf-draft-body")).to_have_text(edits[0])
    expect(draft.locator(".lf-draft-history > summary")).to_have_text(
        "Changes · 3 edits"
    )
    expect(draft.locator(".lf-draft-history > summary")).to_be_focused()
    expect(draft).to_have_attribute("data-lf-pending", "1")

    events = [
        json.loads(line)
        for line in (serve.page_dir / "comments.jsonl").read_text().splitlines()
        if '"kind": "action"' in line
    ]
    assert [event["detail"]["text"] for event in events] == [
        edits[0],
        edits[1],
        edits[0],
    ]
    assert [event["action"] for event in events] == ["edit", "edit", "edit"]

    sequence = page.evaluate(
        """async () => {
          const {actionSequence} = await import('/leaf.js');
          const widget = document.getElementById('draft-ops');
          const first = actionSequence(widget, 'edit');
          first[0].detail.text = 'A widget must not mutate the runtime log.';
          return actionSequence(widget, 'edit')
            .map(event => [event.seq, event.detail.text]);
        }"""
    )
    assert [text for _, text in sequence] == [edits[0], edits[1], edits[0]]
    assert [seq for seq, _ in sequence] == sorted(seq for seq, _ in sequence)

    other, other_errors = open_page(browser, page.url)
    expect(other.locator("#draft-ops .lf-draft-body")).to_have_text(edits[0])
    expect(other.locator("#draft-ops .lf-draft-history > summary")).to_have_text(
        "Changes · 3 edits"
    )
    assert errors == []
    assert other_errors == []
    other.close()
    page.close()


def test_action_history_is_bounded_by_the_pinned_version(browser, serve):
    """A historical page cannot narrate an edit that had not happened yet. The
    helper owns the same version boundary replay does, so every future widget that
    consumes a sequence gets this right without copying the filter."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    for version, text in ((1, "First recorded body."), (2, "Second recorded body.")):
        if version == 2:
            (d / "versions" / "v2.html").write_text(JOURNEY_V2)
            interact.append_event(
                d, {"kind": "note", "author": "claude", "version": 2, "text": "v2"}
            )
        interact.append_event(
            d,
            {
                "kind": "action",
                "author": "user",
                "version": version,
                "widget": "draft-ops",
                "action": "edit",
                "detail": {"text": text},
            },
        )

    old, old_errors = open_page(browser, url, pin=True)
    expect(old.locator("#draft-ops .lf-draft-history > summary")).to_have_text(
        "Changes · 1 edit"
    )
    old_sequence = old.evaluate(
        """async () => (await import('/leaf.js'))
          .actionSequence(document.getElementById('draft-ops'), 'edit')
          .map(event => event.version)"""
    )
    assert old_sequence == [1]

    latest, latest_errors = open_page(
        browser, url.replace("v1.html", "v2.html"), pin=True
    )
    expect(latest.locator("#draft-ops .lf-draft-history > summary")).to_have_text(
        "Changes · 2 edits"
    )
    latest_sequence = latest.evaluate(
        """async () => (await import('/leaf.js'))
          .actionSequence(document.getElementById('draft-ops'), 'edit')
          .map(event => event.version)"""
    )
    assert latest_sequence == [1, 2]
    assert old_errors == []
    assert latest_errors == []
    old.close()
    latest.close()


def test_an_acknowledged_decision_still_survives_the_next_version(browser, serve):
    """The round trip above, differing in one fact: the agent has acknowledged the
    actions before v2 publishes. That is the ordinary case — the agent writes a
    version *because* it was handed the user's edits — and it used to be the
    one that lost them: replay stopped at the handoff cursor, on the premise
    that a version written after seeing an action encodes it. Nothing checks that
    premise, so a version that quietly omits the state re-emitted the widget as
    untouched and the user's work vanished with no error anywhere.

    Acknowledgement is not assent. Only the next version's markup can say what the
    agent did with an edit, and until it says otherwise the log is what the user
    did."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    interact.append_event(
        d,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "board",
            "action": "move",
            "detail": {"card": "card-x", "to": "col-done", "index": 0},
        },
    )
    interact.append_event(
        d,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"text": DRAFT_EDITED},
        },
    )
    # The highest user event reached context, so everything so far is ours to answer.
    interact.cmd_ack(d, interact.read_events(d)[-1]["seq"])
    # And the agent answers with a version that carries neither — the page generator
    # emitting its own idea of the board and the draft, as one did for five
    # versions running.
    (d / "versions" / "v2.html").write_text(JOURNEY_V2)
    interact.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "v2"}
    )

    page, errors = open_page(browser, url.replace("v1.html", "v2.html"))
    page.wait_for_function(
        "t => document.querySelector('#draft-ops .lf-draft-body').textContent === t",
        arg=DRAFT_EDITED,
    )
    expect(page.locator("#col-done #card-x")).to_have_count(1)
    assert errors == []
    page.close()


def test_a_comment_written_on_an_edited_draft_lands_on_their_words(browser, serve):
    """`leaf comment` reads the version file plus the log; the user's tab reads
    the DOM replay builds from the same two. An edited draft is where those readings
    used to drift — the file holds words the page stopped showing — so write the anchor
    blind, on the user's own words, and prove the page paints it. The words the edit
    replaced are refused at the CLI, naming the edit, because posted they would detach
    in front of the user."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    interact.append_event(
        d,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"text": DRAFT_EDITED},
        },
    )
    refused = CliRunner().invoke(
        interact.cli,
        ["comment", str(d), "--quote", "It is online.", "--text", "x"],
    )
    assert refused.exit_code != 0 and "rewrote § draft-ops" in refused.output
    written = CliRunner().invoke(
        interact.cli,
        [
            "comment",
            str(d),
            "--quote",
            "It takes about a minute.",
            "--text",
            "Measured where?",
        ],
        catch_exceptions=False,
    )
    assert written.exit_code == 0, written.output

    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    thread = page.locator(".lf-thread .lf-quote").first
    expect(thread).not_to_have_class(re.compile(r"\bdetached\b"))
    assert painted(page, "lf-mark") == "It takes about a minute."
    assert errors == []
    page.close()


# The two presses this asks about, on one page: a draft's ✎ (a thing to do) and a pick
# mark (a thing to do that becomes a thing the page says once it is pressed).
KEYS_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>keys</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="h">Session store</h1>
<lf-options id="opts" choose>
  <lf-option id="opt-keep"><strong>Keep the store</strong> Sessions stay where they are.</lf-option>
  <lf-option id="opt-token"><strong>Signed tokens</strong> No store at all.</lf-option>
</lf-options>
<lf-draft id="draft-ops"><pre>
    Run the migration before deploying.
</pre></lf-draft>
</main>
</body>
</html>
"""


def test_a_press_takes_the_keys_a_button_came_with(browser, serve):
    """A press is a span wearing role="button" (`offer`), so Enter and Space are the
    runtime's to supply — and it supplies them once, for every widget, which is why this
    is one test rather than a leg in each widget's own. What it has to get right is the
    two things a real <button> did for free.

    Activation: the ✎ on a draft is the door a keyboard user uses, and if a span
    swallowed Enter there would be no way in at all.

    And once per press however long the key is held. A real button fired on keyup; a
    keydown listener hears the key repeat, and a mark that toggles per repeat posts a
    `choose` per repeat — a stuck key filling the log with decisions the user never
    made. Repeats are dispatched rather than driven, because no automation holds a key
    down; what the browser delivers is exactly this event with `repeat` set."""
    page, errors = open_page(browser, serve(KEYS_PAGE))

    page.locator("#draft-ops .lf-draft-pencil").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#draft-ops textarea")).to_be_focused()
    page.keyboard.press("Escape")

    mark = page.locator("#opts .lf-pick").first
    mark.focus()
    page.keyboard.press(" ")
    expect(page.locator("#opts > lf-option[chosen]")).to_have_count(1)
    chosen = page.locator("#opts > lf-option[chosen]").get_attribute("id")
    mark.evaluate("""el => {
        for (let i = 0; i < 5; i++)
            el.dispatchEvent(new KeyboardEvent('keydown',
                {key: ' ', repeat: true, bubbles: true, cancelable: true}));
    }""")
    expect(page.locator(f"#{chosen}[chosen]")).to_have_count(1)
    # The mark paints its own press before the post answers, so the DOM leads the log:
    # read the file straight after and the first press's event may not be in it yet,
    # which reads exactly like a press that sent nothing. A press that sent nothing
    # satisfies this too, which is what makes it the right wait for both assertions —
    # the repeats below must add none of their own.
    round_trip(page)
    sent = [
        json.loads(line)
        for line in (serve.page_dir / "comments.jsonl").read_text().splitlines()
    ]
    assert [e for e in sent if e.get("action") == "choose"] != [], (
        "the first press sent nothing, so the repeats below had nothing to duplicate"
    )
    assert len([e for e in sent if e.get("action") == "choose"]) == 1, (
        "a held key sent one decision per repeat"
    )
    assert errors == []
    page.close()


def test_global_shortcuts_leave_browser_navigation_keys_alone(browser, serve):
    """The document-level dispatcher owns a few single-character shortcuts, not the
    keyboard. In particular, Space, arrows, Home/End, and PageUp/PageDown must reach
    the browser when focus is in the authored page rather than a widget control.

    Observe `defaultPrevented` on real key events instead of asserting that Chrome
    happened to scroll: scrolling depends on viewport and focus geometry, while
    canceling the event is the runtime decision under test. `?` is the positive
    control proving this observer sees a key the dispatcher intentionally consumes."""
    page, errors = open_page(browser, serve(KEYS_PAGE))
    keys = [
        " ",
        "ArrowUp",
        "ArrowDown",
        "ArrowLeft",
        "ArrowRight",
        "Home",
        "End",
        "PageUp",
        "PageDown",
        "?",
    ]
    page.evaluate(
        """keys => {
          const pageContent = document.querySelector("main");
          pageContent.tabIndex = -1;
          pageContent.focus();
          window.lfObservedKeys = {};
          document.addEventListener("keydown", event => {
            if (keys.includes(event.key))
              window.lfObservedKeys[event.key] = event.defaultPrevented;
          });
        }""",
        keys,
    )
    for key in keys:
        page.keyboard.press(key)

    observed = page.evaluate("() => window.lfObservedKeys")
    assert observed.pop("?") is True, (
        "the positive-control shortcut was not consumed, so the probe did not "
        "observe the runtime dispatcher"
    )
    assert observed == dict.fromkeys(keys[:-1], False)
    assert errors == []
    page.close()


def test_repeated_half_page_keys_add_up(browser, serve):
    """The runtime's own pair, beside the browser's above: d and u step half a page, and
    a reader who presses twice inside one glide has to land a whole one. scrollBy
    measures from where the glide has got to rather than from where it is going, so two
    presses covered 461px of a 900px page and the half in between went past unread —
    with nothing on screen to say it had been skipped. The destination is carried
    instead, and clamped, so pressing on at the foot banks no debt for u to press back
    through.

    The second press is timed against the first glide rather than fired after it. An
    overlap that merely happens to occur is one that stops occurring on a loaded
    machine, and this test would then sail past the bug it exists for."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    half = page.evaluate("() => document.body.clientHeight / 2")
    assert page.evaluate(
        "() => document.body.scrollHeight > document.body.clientHeight * 3"
    ), "the page is too short for these steps to be told apart"
    page.evaluate("""() => {
        window.lfScrollEnds = 0;
        document.body.addEventListener('scrollend', () => window.lfScrollEnds++);
    }""")

    def landed(act):
        """Where the scroller came to rest after `act`. A scroll states its own end, so
        that is what this waits on: a duration would be a guess, and stillness sampled
        before the glide starts reads exactly like stillness after it.

        Not moving at all is one of the outcomes under test — a destination run past the
        foot spends a press paying itself back — and a scroll that never happens states
        no end, so the wait is bounded and hands the position to the assertion instead.
        A press that moves nothing then reads as the wrong number, which says what
        happened; thirty seconds of silence and a timeout do not."""
        ends = page.evaluate("() => window.lfScrollEnds")
        act()
        try:
            page.wait_for_function(
                "n => window.lfScrollEnds > n", arg=ends, timeout=5000
            )
        except PlaywrightTimeout:
            pass
        return page.evaluate("() => document.body.scrollTop")

    page.keyboard.press("d")
    # Early in the glide, so the second press cannot arrive after the first has landed
    # however slow the round trip turns out to be.
    page.wait_for_function(
        "h => document.body.scrollTop > 0 && document.body.scrollTop < h / 2", arg=half
    )
    assert landed(lambda: page.keyboard.press("d")) == pytest.approx(half * 2, abs=1), (
        "the second press measured from the glide in flight, so the two together moved "
        "less than the page they promised"
    )
    assert landed(lambda: page.keyboard.press("u")) == pytest.approx(half, abs=1)

    foot = landed(
        lambda: page.evaluate(
            "() => document.body.scrollTop = document.body.scrollHeight"
        )
    )
    for _ in range(4):
        page.keyboard.press("d")  # nothing left to move, and nothing banked either
    assert landed(lambda: page.keyboard.press("u")) == pytest.approx(
        foot - half, abs=1
    ), (
        "presses at the foot of the page ran the destination past it, and u spent "
        "itself paying that back"
    )
    assert errors == []
    page.close()


def test_the_half_page_keys_move_the_region_the_reader_is_scrolling(browser, serve):
    """Two scroll regions, so d has to pick the one the reader is looking at. Beside the
    page the panel is a column of its own and the keys are the document's. Under the
    breakpoint the sheet covers the page and the page hands scrolling over with it — one
    gesture moves one region, and while the sheet is up that region is its thread list.
    A key is no different from a wheel there: a page scrolling behind the sheet shows
    the user nothing, so the key reads as dead, and the document is somewhere else
    when the sheet closes."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=12))
    page.get_by_role("button", name="Comments", exact=False).click()
    panel_settled(page)
    assert page.evaluate(
        "() => { const t = document.querySelector('.lf-threads');"
        " return t.scrollHeight > t.clientHeight; }"
    ), "the thread list does not overflow, so it could not be seen to scroll below"

    page.evaluate("""() => {
        window.lfScrollEnds = 0;
        for (const box of [document.body, document.querySelector('.lf-threads')])
            box.addEventListener('scrollend', () => window.lfScrollEnds++);
    }""")

    def offsets():
        return page.evaluate(
            "() => [document.body.scrollTop,"
            " document.querySelector('.lf-threads').scrollTop]"
        )

    def press_d():
        """Both offsets before and after a d that has come to rest. It waits on
        whichever region answers, so the wrong one answering is two numbers to compare
        rather than half a minute of silence and a timeout — and on the glide's end
        rather than its first frame, since a document still moving when the sheet
        arrives would carry the rest of that move into the phase below."""
        was = offsets()
        page.evaluate("() => window.lfScrollEnds = 0")
        page.keyboard.press("d")
        page.wait_for_function("() => window.lfScrollEnds > 0")
        return was, offsets()

    (page_was, threads_was), (page_now, threads_now) = press_d()
    assert threads_now == threads_was, "the panel took a key aimed at the document"
    assert page_now > page_was, "the document did not move for a key of its own"

    resized(page, 500, 600)
    panel_settled(page)
    (page_was, threads_was), (page_now, threads_now) = press_d()
    assert page_now == page_was, (
        "the page moved behind the covering sheet, where the user cannot see it"
    )
    assert threads_now > threads_was, "the sheet did not move for the key it now owns"
    assert errors == []
    page.close()


def test_the_version_diff_answers_a_key_beside_the_version_pair(browser, serve):
    """The diff held v while the chooser — the control actually wearing the version
    number — had no key at all, so v went to the chooser and the diff took =, beside
    [ and ], the other keys about which version this is. Pressed rather than read off
    the table: a key bound to nothing looks the same in the ? overlay as one that
    works, which is how a rebinding would go unnoticed on the side it left."""
    url = serve(LONG_PAGE)
    _publish(
        serve.page_dir,
        2,
        LONG_PAGE.replace("Paragraph 3.", "Paragraph three."),
        "reworded a paragraph",
    )
    page, errors = open_page(browser, url.replace("v1.html", "v2.html"))
    page.keyboard.press("=")
    expect(page.locator("#p3")).to_have_class(re.compile(r"lf-ins-block"))
    # And the key it left does the chooser's job now rather than both.
    page.keyboard.press("v")
    expect(page.locator(".lf-version-menu")).to_be_visible()
    assert errors == []
    page.close()


def test_a_page_the_suite_opens_has_read_the_log(browser, serve):
    """`open_page` promises a page that has finished becoming itself, and the log is half
    of what that means. The instrument is a refusal of the first `/api/state`. Replay then
    lands on the 2s retry, past both the document's stamp and networkidle, which is where
    a loaded Linux runner put it — so this press meets the same page those runs handed the
    test above, on any machine and in a second.

    Only a press can state it. A read lives through the interval, since `expect` re-asks
    for five seconds and the retry lands in two; a keystroke into a page that has no
    versions yet is gone, and the diff never opens."""
    url = serve(LONG_PAGE)
    _publish(
        serve.page_dir,
        2,
        LONG_PAGE.replace("Paragraph 3.", "Paragraph three."),
        "reworded a paragraph",
    )
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, color_scheme="light"
    )
    polls = itertools.count()
    context.route(
        "**/api/state*",
        lambda route: refuse(route) if next(polls) == 0 else route.continue_(),
    )
    try:
        page, errors = open_page(
            browser, url.replace("v1.html", "v2.html"), context=context
        )
        page.keyboard.press("=")
        expect(page.locator("#p3")).to_have_class(re.compile(r"lf-ins-block"))
        assert errors == []
    finally:
        context.close()


def test_restating_a_widget_is_how_a_version_takes_the_pen_back(browser, serve):
    """The other end of the rule above. Since the log outranks the markup, a
    version cannot revise a draft the user has rewritten — replay would paint
    their words straight back over it, and Claude's correction would reach nobody.
    `restated` is the one way markup wins: it retracts what came before it, so
    the new words render and the user sees the widget marked as one whose
    decision this version undid.

    It costs a word, where losing a decision used to cost nothing, which is the
    whole asymmetry: the failure that stays silent is now the one that needs
    saying out loud."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    interact.append_event(
        d,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"text": DRAFT_EDITED},
        },
    )
    corrected = "Run the migration after deploying — it needs the new column."
    _publish(
        d,
        2,
        _draft_says(JOURNEY_V2, corrected, " restated"),
        "0041 needs the column; rewrote the draft",
    )

    page, errors = open_page(browser, url.replace("v1.html", "v2.html"))
    body = page.locator("#draft-ops .lf-draft-body")
    expect(body).to_have_text(corrected)
    # And the user is told, rather than left to notice: their edit is gone,
    # which without a mark reads exactly like a draft they never touched. Told in
    # words as well as in ink — the mark is an outline, which is the whole of what a
    # reader listening was getting, and this is the one paint on the page that says
    # something was taken away from them.
    expect(page.locator("#draft-ops[data-lf-restated]")).to_have_count(1)
    assert "rewritten since your decision" in page.locator("#draft-ops").aria_snapshot()
    assert errors == []
    page.close()


def test_a_retraction_outlives_the_version_that_made_it(browser, serve):
    """`restated` belongs to the version that rewrote the words, and to no other:
    v3 has nothing to declare, because it is not the one taking anything back.

    So the retraction cannot live in the markup, or v3's silence would read as
    "carry the decision" and hand the user's edit straight back — the same
    resurrection the branch removed, one version later and just as quiet.
    Publishing records it in the log instead, where it is a fact with a version
    on it and every later version inherits it for free."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    interact.append_event(
        d,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"text": DRAFT_EDITED},
        },
    )
    corrected = "Run the migration after deploying — it needs the new column."
    _publish(d, 2, _draft_says(JOURNEY_V2, corrected, " restated"), "rewrote the draft")
    # v3 keeps v2's words and says nothing about the retraction, because
    # saying it again would be claiming to undo a decision already undone.
    _publish(d, 3, _draft_says(JOURNEY_V2, corrected), "unrelated copy edits")

    page, errors = open_page(browser, url.replace("v1.html", "v3.html"))
    expect(page.locator("#draft-ops .lf-draft-body")).to_have_text(corrected)
    assert errors == []
    page.close()

    # And the careful author who carries the attribute forward anyway — the habit
    # this whole design exists to break — is told which version already did it.
    (d / "versions" / "v4.html").write_text(
        _draft_says(JOURNEY_V2, corrected, " restated")
    )
    result = CliRunner().invoke(
        interact.cli,
        ["version", "publish", str(d), "--version", "4", "--text", "again"],
    )
    assert result.exit_code != 0
    assert "v2 already took that back" in result.output


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


def test_a_decision_not_yet_honored_wears_the_pending_mark(browser, serve):
    """One pass, every widget alike: a decided-and-unhonored state wears
    data-lf-pending, driven by the registry's x-state rather than remembered per
    widget — choose had its mark, edit its tint, and move had nothing, which is
    how a dragged card's fate stayed invisible once the toast faded. The mark
    clears the moment a version carries the decision, and the diff stays quiet
    about an honored move: the user's own drag is not news to them."""
    page, errors = open_page(browser, serve(JOURNEY_V1))

    # A real drag — the pointer path, where the gesture gate and the poll meet.
    grip = page.locator("#card-x .lf-grip").bounding_box()
    dest = page.locator("#col-done").bounding_box()
    page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
    page.mouse.down()
    page.mouse.move(
        dest["x"] + dest["width"] / 2, dest["y"] + dest["height"] / 2, steps=15
    )
    page.mouse.up()
    expect(page.locator("#card-x[data-lf-pending]")).to_have_count(1)

    draft = page.locator("#draft-ops")
    draft.locator(".lf-draft-body").dblclick()
    draft.locator("textarea").fill(DRAFT_EDITED)
    draft.get_by_role("button", name="Save").click()
    expect(page.locator("#draft-ops[data-lf-pending]")).to_have_count(1)

    # Both actions must be in the log before the honoring version publishes, and the
    # page is what says so: it sent them, and counts what has come back.
    d = serve.page_dir
    round_trip(page)

    _publish(
        d,
        2,
        _card_done(_draft_says(JOURNEY_V2, DRAFT_EDITED)),
        "honors the move and the edit",
    )
    page.wait_for_url("**/v2.html")
    page.wait_for_function("() => document.querySelector('.lf-banner') !== null")
    # A poll has run once the status text resolves, so the pending pass has too.
    page.wait_for_function(
        "() => !document.querySelector('.lf-status-text').textContent.startsWith('Connecting')"
    )
    expect(page.locator("[data-lf-pending]")).to_have_count(0)

    # The diff's state half is quiet about the honored move: base state is the
    # base markup plus the fold as of it, which already has the card in Done.
    compare_with(page)
    page.wait_for_function(
        "() => document.querySelector('.lf-banner .lf-btn.on') !== null"
    )
    assert not page.evaluate(
        "document.getElementById('card-x').classList.contains('lf-ins-block')"
    ), "the user's own honored drag marked as a change"
    assert errors == []
    page.close()


def test_the_diff_marks_a_card_the_author_relocated(browser, serve):
    """A pure state change has no text of its own, so the content diff was blind
    to it: a card in a new column read as nothing changed. The state half
    compares declared facets, so the author moving a card between versions —
    with no user action behind it — marks the card itself. The card alone:
    an id'd element nested inside it rode along rather than changing columns,
    and marking it too would double-tint one move."""
    noted = _CARD.replace(
        "</lf-card>", '<p id="card-x-note">A nested aside.</p></lf-card>'
    )
    v1 = JOURNEY_V1.replace(_CARD, noted)
    url = serve(v1)
    d = serve.page_dir
    _publish(
        d, 2, _card_done(JOURNEY_V1).replace(_CARD, noted), "moved the card to Done"
    )
    page, errors = open_page(browser, url.replace("v1.html", "v2.html"))
    compare_with(page)
    page.wait_for_function(
        "() => document.getElementById('card-x').classList.contains('lf-ins-block')"
    )
    assert not page.evaluate(
        "document.getElementById('card-x-note').classList.contains('lf-ins-block')"
    ), "the card's passenger marked as its own move"
    assert errors == []
    page.close()


SUGGEST_BLOCK = (
    '<lf-suggestion id="sug-fix" resolves="c1">'
    '<lf-old><p id="old-claim">It is not online.</p></lf-old>'
    "<lf-new><p>It takes a minute of downtime.</p></lf-new>"
    "</lf-suggestion>"
)


def test_accepting_a_suggestion_resolves_its_thread_in_one_event(browser, serve):
    """Accepting answers the thread the change was written for, and the answer
    rides the accept itself — the wrapper holding the `resolves` mapping is
    retired by the honoring version, and a second POST could fail alone, leaving
    the outcome and the resolution disagreeing with no repair path. One event,
    read by both thread builders."""
    url = serve(
        JOURNEY_V1.replace('<h2 id="notes">', SUGGEST_BLOCK + '<h2 id="notes">')
    )
    d = serve.page_dir
    interact.append_event(
        d,
        {
            "kind": "comment",
            "id": "c1",
            "author": "user",
            "version": 1,
            "text": "does this take downtime?",
        },
    )
    page, errors = open_page(browser, url)
    page.get_by_role("button", name=re.compile("^Accept the suggested change")).click()
    page.get_by_role("button", name=re.compile("^Comments")).click()
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    events = [
        json.loads(line) for line in (d / "comments.jsonl").read_text().splitlines()
    ]
    accept = next(e for e in events if e.get("kind") == "action")
    assert accept["action"] == "accept" and accept["detail"] == {"resolves": "c1"}
    assert not any(e.get("kind") == "resolve" for e in events)
    assert errors == []
    page.close()


def test_chrome_is_safe_during_the_registry_fetch(browser, serve):
    """The chrome is wired before the asynchronous registry fetch completes.
    That interval is real state, not a missing-registry fallback: general
    Comments remains usable, but an anchored comment waits until upgrades have
    made the page's final words. The explicit gate proves each assertion runs on
    the intended side of the fetch rather than racing a timer."""
    gate_registry = """
      const nativeFetch = window.fetch.bind(window);
      window.lfRegistryGate = new Promise(resolve => window.lfReleaseRegistry = resolve);
      window.fetch = (...args) => {
        const input = args[0];
        const url = typeof input === 'string' ? input : input.url;
        if (new URL(url, location.href).pathname === '/registry.json') {
          window.lfRegistryBlocked = true;
          return window.lfRegistryGate.then(() => nativeFetch(...args));
        }
        return nativeFetch(...args);
      };
    """
    html = JOURNEY_V1.replace(
        '<h2 id="notes">',
        """
<lf-milestones>
  <lf-milestone id="gate-milestone" status="active" tags="wood,solar">
    <strong>Build feeders</strong> Two classic models.
  </lf-milestone>
</lf-milestones>
<h2 id="notes">""",
    )
    page, errors = open_page(
        browser,
        serve(html, anchored=[("intro", SENTENCE)]),
        init_script=gate_registry,
        wait_until="domcontentloaded",
        # The held registry is this test's subject, so the upgrade stamp never lands and
        # waiting for it would hang out a whole timeout.
        upgraded=False,
    )
    page.wait_for_function("() => window.lfRegistryBlocked === true")
    expect(page.locator("#gate-milestone .lf-chips")).to_have_count(0)
    expect(page.locator("#draft-ops .lf-draft-body")).to_have_count(0)

    page.get_by_role("button", name=re.compile("^Comments")).click()
    expect(page.locator(".lf-panel")).to_have_class(re.compile("open"))
    page.locator(".lf-general textarea").fill("General comment during startup")
    page.locator(".lf-general").get_by_role("button", name="Send").click()
    expect(page.locator(".lf-thread")).to_have_count(2)
    assert page.evaluate("() => CSS.highlights.get('lf-mark')?.size ?? 0") == 0

    page.locator("#gate-milestone").select_text()
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_hidden()

    page.evaluate("window.lfReleaseRegistry()")
    expect(page.locator("#gate-milestone .lf-chips")).to_have_count(1)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    expect(page.locator(".lf-fab")).to_be_visible()
    page.locator(".lf-fab").click()
    page.locator(".lf-composer textarea").fill("Still anchored?")
    page.locator(".lf-composer").get_by_role("button", name="Comment").click()

    expect(page.locator(".lf-thread")).to_have_count(3)
    expect(page.locator(".lf-thread .lf-quote.detached")).to_have_count(0)
    assert errors == []
    page.close()


def test_overlapping_polls_never_move_the_log_backwards(browser, serve):
    """A post-triggered poll and the timer can overlap. The append-only event
    sequence makes an older response unambiguously stale."""
    delay_second_state = """
      const nativeFetch = window.fetch.bind(window);
      let stateCalls = 0;
      window.fetch = async (...args) => {
        const input = args[0];
        const url = typeof input === 'string' ? input : input.url;
        const response = await nativeFetch(...args);
        if (new URL(url, location.href).pathname !== '/api/state') return response;
        stateCalls += 1;
        if (stateCalls !== 2) return response;
        const body = await response.text();
        window.lfDelayedPollCaptured = true;
        await new Promise(resolve => setTimeout(resolve, 3000));
        window.lfDelayedPollReleased = true;
        return new Response(body, {
          status: response.status,
          statusText: response.statusText,
          headers: response.headers,
        });
      };
    """
    # open_page's traffic watcher goes on outside this, so what it counts as answered is
    # what the page was handed — the held poll included, which is the whole subject here.
    page, errors = open_page(browser, serve(JOURNEY_V1), init_script=delay_second_state)
    page.get_by_role("button", name=re.compile("^Comments")).click()
    page.locator(".lf-general textarea").fill("Starts the slow poll")
    page.locator(".lf-general button").click()
    page.wait_for_function("() => window.lfDelayedPollCaptured === true")

    interact.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "newest-snapshot",
            "author": "user",
            "version": 1,
            "text": "Newest snapshot stays rendered",
        },
    )
    # A later poll overtakes the held one and renders the newest log.
    told(page)
    expect(
        page.locator(".lf-thread", has_text="Newest snapshot stays rendered")
    ).to_have_count(1)
    # Then the stale answer arrives. One more poll after it is what proves the page
    # handled it and kept the thread, rather than being asked before it ever landed.
    page.wait_for_function("() => window.lfDelayedPollReleased === true")
    told(page)
    expect(
        page.locator(".lf-thread", has_text="Newest snapshot stays rendered")
    ).to_have_count(1)
    assert errors == []
    page.close()


def test_the_help_overlay_answers_to_one_owner(browser, serve):
    """Open or closed is state with one writer now — it was three writers and
    two classList read-backs, the exact shape the first norm forbids. Exact
    registrations deduplicate without making display text a lossy identity."""
    html = JOURNEY_V1.replace(
        "</main>",
        '<lf-draft id="draft-second"><pre>A second editable draft.</pre></lf-draft></main>',
    )
    page, errors = open_page(browser, serve(html))
    page.evaluate(
        """async () => {
          const { keyHelp } = await import('/leaf.js');
          keyHelp('On a draft', [['F2', 'a project widget using the same heading']]);
        }"""
    )
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_be_visible()
    expect(page.locator(".lf-help h3", has_text="On a draft")).to_have_count(2)
    expect(
        page.locator(".lf-help", has_text="a project widget using the same heading")
    ).to_be_visible()
    # Help is a scope: the table stands down behind it, so c must not work the
    # panel under the sheet.
    page.keyboard.press("c")
    expect(page.locator(".lf-panel")).to_be_hidden()
    expect(page.locator(".lf-help")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-help")).to_be_hidden()
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_be_visible()
    page.mouse.click(300, 600)
    expect(page.locator(".lf-help")).to_be_hidden()
    assert errors == []
    page.close()


@pytest.fixture(scope="module")
def dead_pid():
    """A pid that is certainly not running, for a page whose session has exited."""
    spent = subprocess.Popen([sys.executable, "-c", ""])
    spent.wait()
    return spent.pid


@contextmanager
def live_watcher(page_dir, page):
    """Bump heartbeat.json for the duration of the block, as `leaf wait` does.

    Both ends wait for the poll that carries them, so the assertions on either side
    read a page that has already been told a watcher arrived or left. The first beat
    is written here rather than in the thread, so that wait cannot outrun it."""
    stop = threading.Event()

    def pump():
        while not stop.wait(0.5):
            interact.write_json(page_dir / "heartbeat.json", {"t": time.time()})

    interact.write_json(page_dir / "heartbeat.json", {"t": time.time()})
    threading.Thread(target=pump, daemon=True).start()
    told(page)
    try:
        yield
    finally:
        stop.set()
        (page_dir / "heartbeat.json").unlink(missing_ok=True)
    # Outside the finally: a block that raised has its own failure to report, and
    # nothing after it to wait for.
    told(page)


def test_banner_reports_whether_anyone_is_attending(browser, serve, tmp_path, dead_pid):
    """The banner may claim no more than the page directory can prove. A watch that
    has stopped must read differently from a watch with nothing to report, because
    otherwise the user's only way to tell them apart is to ask.

    And a page nothing is behind must read differently from either, without reading as
    a fault: a standing page spends the night that way, so the words are the plain
    computed fact and the dot is not the amber it wears for a session falling behind."""
    page, _ = open_page(browser, serve(LONG_PAGE, comments=1))
    d = tmp_path / "page"
    # The banner's own dot: the leaves panel mirrors this page as a row, so a
    # bare .lf-dot resolves to that row's copy too.
    text, dot = page.locator(".lf-status-text"), page.locator(".lf-banner .lf-dot")
    UNHELD = (
        "No session holds this page. 1 update waiting."
        " It picks up again when a session does."
    )

    def declare(
        state,
        detail="",
        *,
        agent="Claude",
        handoff=False,
        quiet_for=0,
        session_pid=None,
        claimed=True,
    ):
        ts = datetime.now().astimezone() - timedelta(seconds=quiet_for)
        status = {
            "state": state,
            "detail": detail,
            "ts": ts.isoformat(timespec="seconds"),
        }
        if handoff:
            status["handoff"] = True
        if claimed:
            interact.write_json(
                d / "session.json",
                {
                    "id": "s",
                    "pid": session_pid or os.getpid(),
                    "agent": agent,
                    "ts": "t",
                },
            )
        else:
            (d / "session.json").unlink(missing_ok=True)
        interact.write_json(d / "status.json", status)
        told(page)

    declare("working", "revising the plan")
    expect(text).to_have_text(
        re.compile(r"^Claude is working — revising the plan \(.+\)$")
    )
    expect(dot).to_have_class(re.compile(r"\bworking\b"))

    declare("waiting")
    with live_watcher(d, page):
        expect(text).to_have_text("Claude awaits — select text to comment")
        expect(dot).to_have_class(re.compile(r"\blistening\b"))

        # A working claim gone quiet under a live watcher lands in this same branch,
        # and its detail says what the agent was doing — the wrong half of the loop to
        # read out after "awaits", so only a waiting claim's detail speaks here.
        declare("working", "revising the plan", quiet_for=20 * 60)
        expect(text).to_have_text("Claude awaits — select text to comment")

        # What the page wants back, in the agent's words, where the reader arrives.
        # The whole line is the tooltip too: it is the first thing on the row to be
        # clipped, and a narrow window must not be why the ask goes unread.
        declare("waiting", "pick a storage engine")
        expect(text).to_have_text("Claude awaits — pick a storage engine")
        expect(text).to_have_attribute("title", "Claude awaits — pick a storage engine")

    # No watcher, but Claude checked in moments ago, so it is between turns.
    declare("waiting")
    expect(text).to_have_text(
        "Claude isn't watching right now. 1 update waiting. It picks them up next turn."
    )

    # The failure the whole mechanism exists for: `leaf wait` printed, set this
    # status, and Claude never came back. The handoff mark is what dates it.
    declare("working", "picking up 1 update", handoff=True, quiet_for=20 * 60)
    expect(text).to_have_text(
        "Claude last checked in 20m ago. 1 update waiting. Nudge it in the terminal."
    )
    expect(dot).to_have_class(re.compile(r"\baway\b"))

    # Claude's own status gets a far longer rope: the same silence is just a long turn.
    declare("working", "running the migration", quiet_for=10 * 60)
    expect(text).to_have_text(re.compile(r"^Claude is working — running the migration"))

    # A dead session needs no timeout at all — the owning pid is simply gone, so the
    # claim it left has nothing behind it however lately it was written.
    declare("working", "running the migration", session_pid=dead_pid)
    expect(text).to_have_text(UNHELD)
    # Grey, not the amber a session falling behind wears: nobody is on the line, which
    # is a page's arrangement rather than something for the user to chase.
    expect(dot).to_have_class(re.compile(r"^lf-dot\s*$"))

    # Nothing ever claimed the page — a server started outside an agent host. There is
    # no pid to ask after, so a claim made moments ago is evidence and still stands.
    declare("working", "running the migration", claimed=False)
    expect(text).to_have_text(re.compile(r"^Claude is working — running the migration"))

    # Once that claim goes quiet there is nothing left holding the page, and an hour of
    # silence on a page that stands for weeks is not a fault to report.
    declare("working", "running the migration", quiet_for=60 * 60, claimed=False)
    expect(text).to_have_text(UNHELD)

    declare("working", "revising the plan", agent="Codex")
    expect(text).to_have_text(re.compile(r"^Codex is working — revising the plan"))

    declare("idle")
    expect(text).to_have_text("Leaf closed")
    page.close()


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


def test_the_tab_wears_what_the_banner_says(browser, serve, tmp_path, dead_pid):
    """The judgment's third seat, and the only one a reader with six leaves open in a
    row of tabs can see without opening any. The mark is the vendored icon.svg and the
    runtime paints the element it declares in whatever colour the dot is wearing, so the
    tab and the banner are one fact read twice: a palette written out again for the tab
    would be free to drift from the theme the day a project overrode a token, and drift
    silently, since a tab nobody is watching closely is exactly the case this is for.

    What a copy does with all of it is the export section's
    (test_a_copy_wears_the_mark_and_claims_no_session)."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    d = tmp_path / "page"

    def tone(want, why):
        try:
            return page.wait_for_function(TAB_TONE, arg=want).json_value()
        except PlaywrightTimeout:
            # The console with it: a mark the runtime refuses reads here as a tab with
            # no tone on it, and the reason it refused is the only thing that says why.
            found = page.evaluate(TAB_AND_DOT, want)
            pytest.fail(
                f"the tab never said {why} as the banner does: {found} {errors}"
            )

    def declare(state, **status):
        interact.write_json(
            d / "status.json",
            {"state": state, "ts": interact.now_iso(), **status},
        )
        told(page)

    # `page init` leaves a fresh working claim, so the tab arrives already saying so.
    working = tone("working", "working")
    declare("waiting")
    with live_watcher(d, page):
        awaits = tone("listening", "awaits")
    # The distinctness is the half agreement alone can't prove: a tab painted once and
    # never again agrees with a dot that never moved either, and the two states a reader
    # is choosing between — this page wants me, that one is busy — are exactly the pair
    # that would collapse.
    assert awaits != working, (
        f"a page awaiting its reader wears the same tab as one that is working ({awaits})"
    )

    # The claimant is gone, so nothing is behind the page: grey in the banner, and grey
    # in the tab, which is the whole of what the reader can see of it from a tab strip.
    interact.write_json(
        d / "session.json", {"id": "s", "pid": dead_pid, "agent": "Claude", "ts": "t"}
    )
    unheld = tone("", "unheld")
    assert unheld not in (working, awaits), (
        f"a page nothing holds wears a tab claiming a session ({unheld})"
    )

    # And the mark itself is an image the browser will render, which is the one thing
    # a string comparison above cannot say: an SVG this file mangles decodes to nothing
    # and shows as a blank tab, with no error anywhere to find it by.
    drawn = page.evaluate("""() => new Promise((done) => {
        const img = new Image();
        img.onload = () => done(img.naturalWidth);
        img.onerror = () => done(0);
        img.src = document.querySelector('link[rel=icon]').getAttribute('href');
    })""")
    assert drawn > 0, "the tab's mark is not an image the browser can decode"
    assert errors == []
    page.close()


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


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_an_anchor_written_from_the_file_lands_on_the_page(browser, serve, example):
    """The claim `leaf comment` makes is that a quote read out of the version file
    names the same passage in the browser. Checked on the pages people actually write,
    because the ways it can fail are all theirs: a diagram that renders to a picture, an
    attribute the runtime turns into text, two paragraphs whose join is a space in one
    reading and nothing in the other."""
    html = example.read_text()
    url = serve(html)
    d = serve.page_dir
    anchors = written_anchors(d, html)
    assert len(anchors) >= 10, (
        f"only {len(anchors)} anchors over {example.stem}; sweep too thin"
    )
    for i, (_, anchor) in enumerate(anchors):
        interact.append_event(
            d,
            {
                "kind": "comment",
                "author": "claude",
                "version": 1,
                "id": f"written{i}",
                "anchor": anchor,
                "text": f"note {i}",
            },
        )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    # The runtime's own record of which threads it found a home for.
    detached = page.eval_on_selector_all(
        ".lf-thread .lf-quote.detached", "els => els.map(e => e.textContent)"
    )
    assert detached == [], (
        f"{len(detached)} anchors resolved to nothing in {example.stem}: {detached}"
    )
    # And that the homes are the right ones. Painted in thread order, one range per
    # segment, so the passages concatenate: whitespace aside, because a quote's is
    # elastic to the search by design — a block boundary is a space in the file's
    # reading and no character at all in the page's.
    painted = re.sub(
        r"\s",
        "",
        page.evaluate(
            "() => [...CSS.highlights.get('lf-mark')].map(r => r.toString()).join('')"
        ),
    )
    wanted = re.sub(r"\s", "", "".join(quote for quote, _ in anchors))
    assert painted == wanted, f"anchors in {example.stem} painted text they don't name"
    assert errors == []
    page.close()


TWIN_V1 = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>twin</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<h1 id="t">Twin</h1>
<section id="twin">
<p id="p-original">Cache warmup runs first. The version stamp never lands. Retries are capped at three.</p>
</section>
</main>
</body>
</html>
"""
# A copy the anchor was not made on, added above it — so first-match now finds the wrong
# one, and only the neighbours the capture stored say which was meant.
TWIN_V2 = TWIN_V1.replace(
    '<p id="p-original">',
    '<p id="p-added">Queue drain runs first. The version stamp never lands. Retries are capped at four.</p>\n'
    '<p id="p-original">',
)


def test_a_written_anchor_keeps_its_copy_when_the_page_grows_another(browser, serve):
    """A quote unique when it was written is not unique forever. The neighbours a written
    anchor stores are what hold it on the passage it was made about — without them the
    search takes the first copy, and a comment ends up on words nobody wrote it about."""
    url = serve(TWIN_V1)
    d = serve.page_dir
    result = CliRunner().invoke(
        interact.cli,
        [
            "comment",
            str(d),
            "--quote",
            "The version stamp never lands",
            "--text",
            "capped where?",
        ],
    )
    assert result.exit_code == 0, result.output
    anchor = json.loads(result.output)["anchor"]
    assert anchor["prefix"] and anchor["suffix"], (
        f"nothing stored to tell copies apart: {anchor}"
    )

    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    (d / "versions" / "v2.html").write_text(TWIN_V2)
    interact.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "a twin"}
    )
    page.wait_for_url("**/v2.html")
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    where = page.evaluate(
        "() => [...CSS.highlights.get('lf-mark')][0].startContainer.parentElement.id"
    )
    assert where == "p-original", f"the new copy took the comment ({where})"
    assert errors == []
    page.close()


def test_a_written_comment_keeps_its_originating_agent(browser, serve, monkeypatch):
    """An agent's side of a thread is the user's side with the author flipped.
    Its label belongs to the message — the poster's own environment stamps it as
    the comment is written — so another host claiming the page later cannot
    rewrite who said it."""
    url = serve(TWIN_V1)
    d = serve.page_dir
    monkeypatch.setenv("LEAF_SESSION_ID", "codex")
    monkeypatch.setenv("LEAF_AGENT", "Codex")
    assert (
        CliRunner()
        .invoke(
            interact.cli,
            [
                "comment",
                str(d),
                "--quote",
                "Retries are capped at three",
                "--text",
                "is three right?",
            ],
        )
        .exit_code
        == 0
    )
    interact.write_json(
        d / "session.json",
        {"id": "claude", "pid": os.getpid(), "agent": "Claude", "ts": "t"},
    )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    toggle = page.locator(".lf-comments")
    expect(toggle).to_have_text(
        "Comments (1)"
    )  # counted as open, like any other thread
    toggle.click()
    thread = page.locator(".lf-thread").first
    expect(thread.locator(".lf-msg.claude .lf-msg-head b")).to_have_text("Codex")
    expect(thread.locator(".lf-quote")).to_have_text("“Retries are capped at three”")

    thread.locator("textarea").fill("three is the retry budget, not a guess")
    thread.get_by_role("button", name="Reply").click()
    expect(page.locator(".lf-msg.user")).to_have_count(1)
    page.locator(".lf-thread").first.get_by_role("button", name="Resolve").click()
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")

    kinds = [(e["kind"], e.get("author")) for e in interact.read_events(d)]
    assert ("comment", "claude") in kinds
    assert ("reply", "user") in kinds and ("resolve", "user") in kinds
    assert errors == []
    page.close()


def test_a_reply_toast_keeps_its_originating_agent(browser, serve):
    url = serve(TWIN_V1)
    d = serve.page_dir
    root = interact.append_event(
        d,
        {
            "kind": "comment",
            "author": "user",
            "version": 1,
            "text": "which host answers?",
        },
    )
    interact.write_json(
        d / "session.json",
        {"id": "claude", "pid": os.getpid(), "agent": "Claude", "ts": "t"},
    )
    page, errors = open_page(browser, url)
    expect(page.locator(".lf-comments")).to_have_text("Comments (1)")

    interact.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Codex",
            "parent": root["id"],
            "text": "this one does",
        },
    )
    told(page)
    expect(page.locator(".lf-toast")).to_have_text("Codex replied — open Comments")
    assert errors == []
    page.close()


PICTURE_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>pictures</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_a_widget_declaring_it_renders_a_picture_takes_a_click(browser, serve):
    """A rendering has no text of the page's in it to select, so the click anchors on the
    whole element. Which widgets those are is theirs to declare (x-visual): the runtime
    names none of them, so a widget added to the vocabulary is clickable on the strength
    of its entry — the failure this rules out is the quiet one, where a consumer taught
    one widget by name keeps working on that widget and does nothing for the next."""
    url = serve(PICTURE_PAGE)
    registry = json.loads((serve.page_dir / "registry.json").read_text())
    assert registry["lf-diagram"]["x-visual"], "this test needs the shipped declaration"
    registry["lf-tree"]["x-visual"] = True  # a widget the runtime has never heard of
    (serve.page_dir / "registry.json").write_text(json.dumps(registry))
    page, errors = open_page(browser, url)

    # The inner svg is mermaid's, carrying a generated id; the anchor belongs to the
    # widget that holds it, which is the element the page gave a name.
    page.locator("#flow svg").click()
    page.locator(".lf-fab").click()
    page.locator("#flow.lf-mark-el.lf-pending").wait_for()
    assert not composer_quote(page)["shown"], "a picture has no words to quote back"
    page.get_by_role("button", name="Cancel").click()

    page.locator("#tree").click()
    page.locator(".lf-fab").click()
    page.locator("#tree.lf-mark-el.lf-pending").wait_for()
    page.get_by_role("button", name="Cancel").click()

    # And a paragraph is still text: the click reaches no picture and raises nothing.
    page.locator("#p").click()
    expect(
        page.locator(".lf-fab"), "a click on prose was read as a click on a picture"
    ).not_to_be_visible()
    assert errors == []
    page.close()


# Wide on purpose: six nodes across lays out near 1150px against the column's 672.
WIDE_DIAGRAM_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>wide diagram</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
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
</main>
</body>
</html>
"""


def test_a_diagram_follows_the_scheme_it_is_read_in(browser, serve):
    """The SVG's principal surfaces are written back as var() over the tokens they
    were seeded from (retheme), so a scheme flip repaints them with the rest of the
    page and a copy exported in a light browser opens honestly for a dark reader —
    each used to keep the palette it was rendered under, a light slab in a dark
    page. Only colors mermaid derives from the seeds itself stay frozen, and no
    principal surface is one."""
    page, errors = open_page(browser, serve(WIDE_DIAGRAM_PAGE))
    node = page.locator("#flow svg .node rect").first
    expect(node).to_be_visible()
    fill = "el => getComputedStyle(el).fill"
    light = node.evaluate(fill)
    page.emulate_media(color_scheme="dark")
    assert node.evaluate(fill) != light, (
        "a diagram's node surface must follow the page's scheme"
    )
    assert errors == []
    page.close()


def test_a_wide_diagram_keeps_its_size_and_scrolls_its_own_box(browser, serve):
    """Mermaid fits a diagram to its holder by scaling the whole drawing down, glyphs
    included — this flowchart rendered at 63% in the column, its 16px labels
    effectively 10px and unreadable. The module strips that: the drawing keeps the
    size mermaid laid it out at, the widget's own box scrolls sideways — the theme's
    answer for a wide table — and the document itself grows no sideways scroll."""
    page, errors = open_page(browser, serve(WIDE_DIAGRAM_PAGE))
    sizes = page.evaluate("""() => {
        const holder = document.getElementById('flow');
        const svg = holder.querySelector('svg');
        return { drawn: svg.getBoundingClientRect().width,
                 natural: svg.viewBox.baseVal.width,
                 box: holder.clientWidth,
                 scrolls: holder.scrollWidth > holder.clientWidth,
                 sideways: document.body.scrollWidth - document.body.clientWidth };
    }""")
    assert sizes["natural"] > sizes["box"], (
        "the fixture must lay out wider than the column, or this proves nothing"
    )
    assert round(sizes["drawn"]) == round(sizes["natural"]), (
        f"the drawing was scaled to fit: natural {sizes['natural']}px, "
        f"drawn {sizes['drawn']}px"
    )
    assert sizes["scrolls"], "a drawing wider than its box must scroll inside it"
    assert sizes["sideways"] == 0, "the page itself must not scroll sideways"
    assert errors == []
    page.close()


def test_the_handed_over_url_opens_the_latest_version(browser, serve):
    """The URL `server run` prints is the page root carrying the key, so every handover
    arrives through the redirect to the latest version rather than at a version file.
    Two things have to hold across that hop and only a real browser can say so: the
    cookie is set on the redirect and sent on the request it redirects to, and it is
    still sent once the page is polling — the runtime's own fetches are relative, and a
    `SameSite` cookie the browser withheld from them would leave the page open and
    frozen with no console error to show for it."""
    url = serve(INLINE_PAGE)
    root = url.rsplit("/versions/", 1)[0] + f"/?t={TOKEN}"

    page, errors = open_page(browser, root)

    expect(page).to_have_url(url.rsplit("?", 1)[0])
    expect(page.locator(".lf-banner")).to_be_visible()
    # The poll is the page's own fetch, relative and query-less: it answers only if the
    # cookie rode along.
    assert page.evaluate("() => fetch('/api/state').then(r => r.status)") == 200

    # The version switcher and the latest chip leave the document by assigning
    # location.href, which is a fresh top-level navigation carrying no query. A cookie
    # the browser withheld from it would land the user on a refusal.
    page.evaluate("() => { location.href = '/' }")
    page.wait_for_url(url.rsplit("?", 1)[0])
    expect(page.locator(".lf-banner")).to_be_visible()

    assert errors == []
    page.close()


def test_a_page_refuses_a_browser_that_never_had_the_link(browser, serve):
    url = serve(INLINE_PAGE)

    page = browser.new_page()
    page.goto(url.rsplit("?", 1)[0], wait_until="load")

    assert interact.NO_KEY in page.locator("body").inner_text()
    page.close()


# ---------- export: the page as one file ----------


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_an_exported_example_stands_on_its_own(example, browser, serve, tmp_path):
    """Every shipped example copied to a file and opened from disk, which is the whole
    contract: no server answers, so anything still reaching for one is a hole, and the
    console is where a hole says so. Driven over the corpus rather than one page because
    what a copy loses is per-widget — the gallery alone would pass while the widget only
    it lacks was the broken one.

    A copy over-promising is the other half of that, and it went unread for as long as
    there was nothing here asking. Tab into an exported decision page landed on a pick
    mark, which summoned the keyboard address for a key that answers nothing, into a row
    holding no column for it; a board's ten grips each opened a grab cursor; twenty
    options lit under a pointer that could not pick one. So the copy is asked what it
    still offers, in the three registers an offer is made in — a widget's chrome still
    holding a tab stop or a role, a control standing there with nothing left behind it,
    and a hand or a grab under the pointer — and every question is put to the markers
    rather than to any widget."""
    url = serve(example.read_text())
    out = tmp_path / "standalone.html"
    out.write_text(interact.export_page(browser, url, serve.page_dir))

    errors = []
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("requestfailed", lambda r: errors.append(f"unfetched {r.url}"))
    page.goto(out.as_uri(), wait_until="load")
    state = page.evaluate("""() => ({
        scripts: document.querySelectorAll('script').length,
        chrome: document.querySelectorAll('.lf-chrome').length,
        toServer: [...document.querySelectorAll('[src^="/"], [href^="/"]')]
            .map(e => e.getAttribute('src') ?? e.getAttribute('href')),
        links: document.querySelectorAll('link[rel="stylesheet"]').length,
        column: getComputedStyle(document.querySelector('main')).maxWidth,
        // A page carrying a change to decide gives up a rail of its own width for the
        // controls to hang in, and a copy has no controls to hang there — so the column
        // centres in all of the page, the way paper's does. Read as the two margins
        // rather than off body's padding, since what a reader sees is the column
        // sitting off to one side; and measured against body rather than the window,
        // whose width counts a scrollbar on the platforms that reserve room for one.
        margins: ((m, b) => [Math.round(m.left - b.left), Math.round(b.right - m.right)])(
            document.querySelector('main').getBoundingClientRect(),
            document.body.getBoundingClientRect()),
        unshown: [...document.querySelectorAll('main *')]
            .filter(el => el.textContent.trim() && !el.checkVisibility()
                          // A disclosure the reader can still work, a control's own
                          // label, and an element with no box by design are all fine;
                          // what is not is the page's words with nothing to reveal them.
                          && !el.closest('details, [data-lf-offer], .lf-ui, style, script')
                          && getComputedStyle(el).display !== 'contents')
            .map(el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')),
        // A press a widget injected is a tab stop wearing an interactive role, and the
        // handler that answered both went with the scripts. Asked of the chrome marker
        // and of any role at all, never of a role by name: offer writes role="button"
        // and a widget keeping an ARIA pattern writes over it (lf-tabs' presses say
        // "tab"), so a list of roles here would be a list that stops at the ones it was
        // taught. The twelfth widget is covered by having used offer.
        //
        // The role a control the browser drives wears is the copy telling the truth —
        // lf-shot's radiogroup names radios that still flip its frames — so the role
        // half stands down for one of the platform's own controls. The tab stop's half
        // does not: offer writes that on presses of its own making and on nothing else.
        pressable: [...document.querySelectorAll('[data-lf-offer][tabindex]'),
                    ...[...document.querySelectorAll('[data-lf-offer][role]')]
                        .filter(el => !el.querySelector(
                            'input, select, textarea, a[href], button'))]
            .map(el => el.className || el.tagName.toLowerCase()),
        // The claim a disarmed attribute leaves standing, since a control nothing can
        // work is still a control on the page. What a copy may show of a widget's
        // chrome is one the browser works itself and a label the page speaks through
        // (data-lf-said); the rest belonged to a runtime the file has not got, so a
        // mark reading "choose one" invites a reader who cannot answer it.
        inert: [...document.querySelectorAll('[data-lf-offer]:not([data-lf-said])')]
            .filter(el => el.checkVisibility() && el.textContent.trim()
                          && !el.matches(':has(input, select, textarea, a[href], button)')
                          && !el.closest('label, summary, a[href]'))
            .map(el => (el.className || el.tagName.toLowerCase()) + ': '
                       + el.textContent.trim().replace(/\\s+/g, ' ').slice(0, 24)),
        // The same claim in paint. A hand or a grab says a gesture lands here, and in a
        // copy one lands nowhere the browser isn't the thing acting: a label's radio, a
        // link, a disclosure. The exemptions are the platform's own controls, so no
        // widget is named here either.
        offering: [...document.querySelectorAll('main *')]
            .filter(el => el.checkVisibility()
                          && ['pointer', 'grab'].includes(getComputedStyle(el).cursor)
                          && !el.closest('a[href], label, summary, input, select, textarea'))
            .map(el => el.tagName.toLowerCase() + '.'
                       + String(el.className?.baseVal ?? el.className ?? '')),
    })""")
    # The gate's own reading, on the medium that most needs it: a copy is laid out by
    # rules no other medium runs, and the last two ways one went out wrong were both a
    # widget's words landing on the page's.
    covered = page.evaluate(interact.COVERED_WORDS)
    # The other direction of every question above: not what the copy still offers,
    # but what it under-delivers. BAKE is a remover, and until this ran the only
    # gates on it asked whether it removed enough — a wide diagram lost its scroll
    # stop in every copy, and no sweep read one. 420, because that is the width
    # where boxes start scrolling, and a scrolling box with no way in from the
    # keyboard is the exact class that slipped.
    resized(page, 420, 900)
    axe_violations, axe_report = serious_axe_violations(page)
    page.close()

    assert state["scripts"] == 0, "a copy with no server behind it keeps no script"
    assert state["chrome"] == 0, (
        "the runtime's layer came along — a comment box that swallows what you type"
    )
    assert state["toServer"] == [], "the copy still points at a server that isn't there"
    assert state["links"] == 0, "a stylesheet link survived, pointing at nothing"
    assert state["column"] != "none", "the theme didn't inline; the copy opens unstyled"
    assert state["margins"][0] == state["margins"][1], (
        "the copy's column sits off to one side of a page it has all of: a rail still "
        f"held open for controls the file hasn't got — {state['margins']}"
    )
    assert state["unshown"] == [], (
        "the copy says less than the page did: content sitting behind a control that "
        f"needed a handler, and nothing in a file can press one — {state['unshown']}"
    )
    assert state["pressable"] == [], (
        "the copy offers a press nothing can take: Tab reaches it, a screen reader calls "
        f"it a button, and no handler is left to answer either — {state['pressable']}"
    )
    assert state["inert"] == [], (
        "the copy still shows a control the file has nothing to work with, which asks "
        f"the reader for something they cannot give: {state['inert']}"
    )
    assert state["offering"] == [], (
        "the copy draws a hand over a gesture it cannot take — the pointer promises "
        f"something the file has no script to do: {state['offering']}"
    )
    assert covered == [], f"the copy draws its own words over each other: {covered}"
    assert axe_violations == [], axe_report
    assert errors == [], f"{example.stem} needs a server to render: {errors}"


def test_a_copy_carries_a_workers_standing_report(browser, serve, tmp_path):
    """The copy is the page as replay left it, and a report is replay's other channel —
    none of the corpus can say so, because an example is one version with an empty log.

    The gap the wait covers is real and narrow: the runtime stamps `lf-upgraded` in the
    same breath as it *starts* the first poll, never awaiting it, so the stamp export
    opens on is no promise that anything in the log has been painted. Ordinarily the
    poll goes out during load and export's own `networkidle` waits it out, which is why
    the page arrives painted however the wait is written and why the count being wrong
    stayed invisible. Refusing that first poll is the whole of the difference — replay's
    only chance is then the 2s retry, on the far side of both the stamp and networkidle,
    which is exactly where a loaded machine would have put it. Counting actions alone
    leaves nothing to wait for on a log holding one report, and the copy goes out blank.

    The refusal is served to export's own page rather than the copy's, through the
    stand-in `primed` supplies."""
    url = serve(REPORT_PAGE)
    sent = CliRunner().invoke(
        interact.cli,
        ["report", str(serve.page_dir), "t-parser", "status", "status=done"],
    )
    assert sent.exit_code == 0, sent.output

    def refuse_the_first_poll(page):
        polls = itertools.count()
        page.route(
            "**/api/state*",
            lambda route: refuse(route) if next(polls) == 0 else route.continue_(),
        )

    out = tmp_path / "standalone.html"
    out.write_text(
        interact.export_page(
            primed(browser, refuse_the_first_poll), url, serve.page_dir
        )
    )

    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    expect(page.locator("#t-parser")).to_have_attribute("status", "done")
    expect(page.locator("#t-feeders > .lf-chips")).to_contain_text("2/2 done")
    page.close()


def test_a_copy_wears_the_mark_and_claims_no_session(browser, serve, tmp_path):
    """A copy keeps the mark and drops the status painted on it. The live page was
    exported under a working claim — `page init` leaves one — so the tone it was wearing
    is a session that does not exist behind a file, which is the same lie the chrome is
    dropped for. Nothing else on the tab is worth losing over it: the mark still says
    which product wrote the file, and it is inlined, so it survives the copy leaving the
    machine that served it (test_an_exported_example_stands_on_its_own is what says no
    link here still points at a server)."""
    url = serve(LONG_PAGE)
    out = tmp_path / "standalone.html"
    out.write_text(interact.export_page(browser, url, serve.page_dir))

    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    # The tone is a stylesheet the runtime appends to the mark, so what says the copy is
    # wearing none is the mark carrying only the one its file was written with.
    icon = page.evaluate("""() => {
        const el = document.querySelector('link[rel=icon]');
        const prefix = 'data:image/svg+xml,';
        const href = el.getAttribute('href');
        if (!href.startsWith(prefix)) return { inlined: false };
        const svg = new DOMParser()
            .parseFromString(decodeURIComponent(href.slice(prefix.length)), 'image/svg+xml')
            .documentElement;
        return {
            inlined: true,
            rest: el.getAttribute('data-lf-rest'),
            toned: svg.querySelectorAll('style').length,
            mark: Boolean(svg.querySelector('.lf-tone')),
        };
    }""")
    page.close()

    assert icon["inlined"], "the copy's tab icon is not a mark the file carries itself"
    assert icon["mark"], "the copy lost the mark rather than the status painted on it"
    assert icon["toned"] == 1, (
        "the copy's tab wears a tone it was exported under, claiming a session no file "
        f"has — {icon['toned']} stylesheets on a mark authored with one"
    )
    assert icon["rest"] is None, "the handover attribute rode along into the copy"
