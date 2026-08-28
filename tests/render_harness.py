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

import itertools
import json
import math
import os
import shutil
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from click.testing import CliRunner
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import host as host_model
from leaf import hosting as hosting_model
from leaf import http as http_model
from leaf import render_checks as render_checks_model
from leaf import render_gate as render_gate_model
from leaf import revisioning as revisioning_model
from leaf import service as service_model
from leaf import structure as structure_model
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect

pytestmark = pytest.mark.nightly

ROOT = Path(__file__).parent.parent
COMMAND_HUB_PACKAGE = ROOT / "examples" / "packages" / "command-hub"
EXAMPLE_PACKAGES = json.loads((ROOT / "examples" / "layer.json").read_text())
EXAMPLES = sorted((ROOT / "examples").glob("*.html"))
assert EXAMPLES, "no examples found — parametrizing over an empty list tests nothing"
# The inputs scripts/gallery.py composes. The gallery is a generated presentation of
# these pages, not an eleventh author source; tests that exercise authored content use
# this set while tests of the gallery's own rendering or export keep EXAMPLES.
SOURCE_EXAMPLES = tuple(p for p in EXAMPLES if p.stem != "gallery")
assert SOURCE_EXAMPLES and len(SOURCE_EXAMPLES) + 1 == len(EXAMPLES), (
    "expected exactly one generated gallery beside the source examples"
)
# The bytes an example names but cannot hold: a lf-shot's pair, content-addressed
# exactly as `leaf page media` names it in a real page directory. examples/CLAUDE.md
# lists every publisher that has to lay this beside the markup, this one among them.
EXAMPLE_MEDIA = ROOT / "examples" / "media"


def leaf_page(title: str, body: str, *, head: str = "") -> str:
    """A complete page carrying the presentation boundary every fixture shares."""
    extra_head = f"{head}\n" if head else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta http-equiv="Content-Security-Policy" content="{structure_model.PAGE_CSP}">
<link rel="stylesheet" href="/theme.css">
{extra_head}<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>{body}</main>
</body>
</html>
"""


def stamp_page(
    page_dir: Path, html: str, text: str, *, completes: tuple[str, ...] = ()
) -> dict:
    """Save HTML as the next revision and stamp that exact source."""
    order = max(files_model.list_revisions(page_dir), default=0) + 1
    source = html.replace("</body>", f"<!-- test revision {order} -->\n</body>")
    (page_dir / "index.html").write_text(source, encoding="utf-8")
    complete_args = [arg for widget in completes for arg in ("--completes", widget)]
    result = CliRunner().invoke(
        cli_model.cli,
        ["version", "stamp", str(page_dir), "--text", text, *complete_args],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def stamp_version_file(page_dir: Path, version: int, text: str) -> dict:
    """Migrate a fixture-authored vN file through the real stamp boundary."""
    path = files_model.version_path(page_dir, version)
    html = path.read_text(encoding="utf-8")
    path.unlink()
    note = stamp_page(page_dir, html, text)
    assert note["version"] == version
    return note


def wait_for_revision(page, revision: int) -> None:
    """Wait until a live tab has installed one complete immutable revision."""
    page.wait_for_function(
        "revision => document.querySelector('meta[name=lf-revision][data-lf-runtime]')"
        "?.content === String(revision)",
        arg=revision,
    )


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
    path = service_model.claim_path(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    files_model.write_json(path, record)
    return record


@pytest.fixture
def serve(tmp_path, monkeypatch, clone_initialized_page):
    """Publish HTML as v1 of a fresh page directory and serve it, as the real
    server does — vendoring included, so the assets under test are this repo's.

    Handed an example's path rather than its markup, it also lays in the three
    things that example ships beside itself: the media it names, external data,
    and the event log, where it has one. The log for the same reason `test_examples_pass_check`
    reads one — a page is what its markup and its standing log make together, and
    a corpus that reads only the markup is reading half of it. A thread and any
    widget a message carries exist nowhere else, so without this every sweep is
    green over a page the reader never gets.

    Each call gets its own directory, reached through `serve.page_dir`. Sharing one
    meant a test that serves two examples in a single body re-initialised over the
    first and appended the second's events to a log already holding the first's,
    which reads as a page rather than failing."""

    def go(
        source,
        comments=0,
        anchored=(),
        media=None,
        events=(),
        layer_registry=None,
        layer_widgets=None,
    ):
        monkeypatch.chdir(tmp_path)  # keep the project layer out of the overlay
        project = tmp_path / ".leaf"
        if layer_registry is not None or layer_widgets:
            project.mkdir(exist_ok=True)
            if layer_registry is not None:
                (project / "registry.json").write_text(json.dumps(layer_registry))
            for name, module in (layer_widgets or {}).items():
                path = project / "widgets" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(module)
        example = source if isinstance(source, Path) else None
        packages = link_example_packages(tmp_path)
        selection_args = [arg for name in packages for arg in ("--package", name)]
        d = tmp_path / f"page{len(servers)}"

        def initialize(target):
            initialized = CliRunner().invoke(
                cli_model.cli,
                ["page", "init", *selection_args, str(target)],
            )
            assert initialized.exit_code == 0, initialized.output

        if project.exists() or host_model.config_home().exists():
            initialize(d)
        else:
            clone_initialized_page("examples", d, initialize)
        html = example.read_text() if example else source
        (d / "index.html").write_text(html)
        parsed = structure_model._StructParser()
        parsed.feed(html)
        parsed.close()
        for reference in parsed.media_refs:
            fixture_media = EXAMPLE_MEDIA / reference.removeprefix("/media/")
            if fixture_media.is_file():
                (d / "media").mkdir(exist_ok=True)
                shutil.copy2(fixture_media, d / "media" / fixture_media.name)
        for name, data in (media or {}).items():
            path = d / name.lstrip("/")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for event in events:
            events_model.append_event(d, event)
        activated = revisioning_model.activate_source(d, events_model.read_events(d))
        assert activated.error is None and activated.revision == 1, activated.error
        (d / "versions" / "v1.html").write_text(html)
        events_model.append_event(
            d,
            {
                "kind": "note",
                "author": "claude",
                "version": 1,
                "revision": 1,
                "text": "t",
            },
        )
        if example and (data_seed := example.with_suffix(".data.json")).exists():
            for name, value in json.loads(
                data_seed.read_text(encoding="utf-8")
            ).items():
                data_model.cmd_data_set(d, name, value)
        # After the note, so v1's announcement stays the log's first line and the
        # exchange reads in the order it happened, which is preview.py's ordering.
        # (The site build writes the seed alone and announces its versions
        # elsewhere, so it has no note to come after.) Split on the writer's own
        # separator, never splitlines(), whose wider class reads a U+2028 inside a
        # comment's text as a break.
        if example and (seed := example.with_suffix(".jsonl")).exists():
            for line in seed.read_text(encoding="utf-8").split("\n"):
                if line.strip():
                    events_model.append_event(d, json.loads(line))
            # A seed is history rather than news, so the page opens acknowledged
            # through it — the state every other publisher of a seeded example
            # serves. Left at nought the banner tells the reader their own comment
            # is queued for somebody, which is an arrival regression this corpus
            # would have manufactured for itself. Read back for the seq rather than
            # counted, because a seq is what the log's reader assigns and an append
            # hands back no such number.
            files_model.write_json(
                d / "cursor.json", {"seq": events_model.read_events(d)[-1]["seq"]}
            )
        for i in range(comments):
            events_model.append_event(
                d,
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": f"Comment {i}. " + "Long enough to wrap. " * 4,
                },
            )
        for section, quote in anchored:
            events_model.append_event(
                d,
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "About this bit.",
                    "anchor": {"section": section, "quote": quote},
                },
            )
        httpd = hosting_model.LeafHTTPServer(
            ("127.0.0.1", 0), http_model.handler_for(d, TOKEN)
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
    return render_gate_model.served(page, page.url, "/registry.json").json()


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
        self._answered = set()  # requests whose one response has entered the counters
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
        if request in self._answered:
            return
        self._answered.add(request)
        self._back(request)
        self._responses.append(response)

    def settle_response(self, response):
        """Account for the exact response a causal wait just consumed.

        Playwright resolves `wait_for_event("response")` independently of ordinary
        response listeners. Under load the waiter can resume first; explicitly entering
        that response here closes the ordering without polling or sleeping. `_responded`
        deduplicates the later listener whichever one wins.
        """
        self._responded(response)
        self.settle()

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
    interval to pick, and nothing added to the page. The response returned by that wait
    is entered into Traffic directly because Playwright does not order the waiter after
    ordinary response listeners; the delivery fact therefore changes before this caller
    asks again.

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
            response = page.wait_for_event("response", timeout=remaining)
            page.lf_traffic.settle_response(response)
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
# the page when it next reads — so an assertion made straight after the write is waiting
# on whatever budget expect() happens to carry. Timed, that wait takes 1.8 to 2.3 of the
# default five seconds, and it takes them every time.
#
# So ask the page what it holds. The server names each state it serves with a reading
# and the runtime paints the one it has completely applied, so "has this page taken in
# what I just wrote" is one comparison and names no transport. Counting answered
# requests said the same thing only while a fixed interval made them the same thing:
# the page now asks when its news stream says the page has moved, so a count of asks
# started here reaches the answer that carries the news only by luck of the ordering.
#
# The wanted reading is re-read each round rather than fixed at entry, because the page
# is allowed to move past it — a work claim ages, a neighbour writes — and a wait pinned
# to a reading the page has already overtaken would sit out its whole deadline.
def _server_reading(page):
    """What the server would answer with now, asked without disturbing the page.

    Through the context's request API rather than the page: it carries the same cookie,
    and it is not seen by page routes or by the traffic watcher, so a test that stubs or
    counts /api/state sees exactly what it did before this call existed.
    """
    origin = urlsplit(page.url)
    answer = page.request.get(f"{origin.scheme}://{origin.netloc}/api/state")
    assert answer.ok, f"the server would not say what it holds: {answer.status}"
    return answer.json()["reading"]


def told(page):
    """Wait until the page has taken in everything the server now holds."""
    deadline = time.monotonic() + 30
    began = None
    while True:
        want = _server_reading(page)
        if began is None:
            began = want
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(
                f"the page never took in what the server holds: waiting for {began}, "
                f"the page last applied "
                f"{page.evaluate('() => document.body.dataset.lfReading')}"
            )
        try:
            page.wait_for_function(
                "want => document.body.dataset.lfReading === want",
                arg=want,
                timeout=min(500, remaining * 1000),
                polling=50,
            )
            return
        except PlaywrightTimeout:
            # Either the page has not caught up yet or the revision moved under this
            # wait. Both are answered by asking again with what the server holds now.
            continue


def nudge(page_dir):
    """Give the page a reason to ask, changing nothing it shows.

    The page asks for state when its news stream says the page has moved, and the
    stream reads file stamps. A test that wants the page's next ask — to park it, or to
    watch it refused — used to wait for the poll's timer; now it moves a stamp the state
    does not read. The versions directory's own clock is one: a state reads the files
    in it and never the directory's time.
    """
    os.utime(page_dir / "versions")


def ticked(page):
    """Wait for the page's next re-application of what it holds, by whichever door.

    The poll used to supply this, so a test that wanted the page's next local pass —
    a deferred correction applied once an editor closed — waited for the next request.
    The pass is the heartbeat now, or a read, or a POST's answer, and none of them
    marks the wire for it; `lf-actions` is what every one dispatches when it has run,
    and the listener is put on before the wait so a pass already past cannot answer.
    """
    page.evaluate(
        """() => {
          window.__lfTicked = false;
          document.addEventListener('lf-actions', () => { window.__lfTicked = true; },
                                    { once: true });
        }"""
    )
    page.wait_for_function("() => window.__lfTicked")


def author_test_widget(root: Path, tag: str, *, upgrade: bool = False) -> Path:
    """Author one small widget in the project package for browser fixtures."""
    package = root / ".leaf"
    created = CliRunner().invoke(cli_model.cli, ["package", "init", str(package)])
    assert created.exit_code == 0, created.output
    registry_path = package / "registry.json"
    registry = json.loads(registry_path.read_text())
    entry = {
        "description": f"A <{tag}> test block.",
        "type": "object",
        "properties": {"id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "prose",
        "x-upgrade": upgrade,
        "x-example": f'<{tag} id="{tag.removeprefix("lf-")}-example">Example</{tag}>',
    }
    if upgrade:
        entry["x-verbatim"] = True
    registry[tag] = entry
    registry_path.write_text(json.dumps(registry, indent=2))
    with (package / "theme.css").open("a") as theme:
        theme.write(
            f"\n{tag} {{\n"
            "  display: block;\n"
            "  margin: var(--sp-3) 0;\n"
            "  padding: var(--sp-3);\n"
            "  border: 1px solid var(--rule);\n"
            "  border-radius: var(--r);\n"
            "  background: var(--card);\n"
            "  --lf-frame: 1;\n"
            "}\n"
        )
    if upgrade:
        (package / "widgets" / f"{tag}.js").write_text(
            'import { once } from "/runtime/widget-api.js";\n\n'
            "customElements.define(\n"
            f'  "{tag}",\n'
            "  class extends HTMLElement {\n"
            "    connectedCallback() {\n"
            "      if (!once(this)) return;\n"
            "    }\n"
            "  },\n"
            ");\n"
        )
    return package


def link_example_packages(root: Path) -> list[str]:
    """Expose the corpus packages at their recorded project-relative paths."""
    for name in EXAMPLE_PACKAGES:
        relative = Path(name)
        package = root / relative
        package.parent.mkdir(parents=True, exist_ok=True)
        if not package.exists():
            package.symlink_to(ROOT / relative, target_is_directory=True)
    return EXAMPLE_PACKAGES


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


# A request a test stops is cancelled rather than failed. The page cannot tell the two
# apart — both reject the fetch the runtime awaits and leave it on the same `catch`.
# The console can tell them apart, which is what the reason is chosen for:
# tests/CLAUDE.md, "A test cannot assert over noise it makes itself". A refused event
# request remains unresolved, deliberately: the outbox keeps its attempt and retries.
def refuse(route):
    """Stop this request with nothing for the page's console to report."""
    route.abort("aborted")


# A tab a test holds stale is stale only while nothing reaches it: every state
# application reconciles the draft store against shared storage before it settles
# anything (settleAcceptedDrafts), so a stale view the assertions take their time
# reaching is a race a loaded runner loses. Refusing the state reads states it — but
# only from before the page exists. `page.route` reaches no request already in the
# wire, and a read reconciles when its response lands rather than when its request
# went out, so a refusal registered on a live page leaves whatever is outstanding free
# to arrive later, against storage the test has moved in the meantime. Registered
# through `primed`, the route is on the page before it navigates and no read is ever
# unrouted. The stream the page hears news on is not a state read and is not refused;
# what it prompts is, every two seconds, for as long as the route stands.
#
# The first is let through because `open_page` waits for the page's readiness facts,
# including `lf-applied`, which rides on it — and that same wait is what leaves nothing
# outstanding when the page is handed over. Where the tab has to hear the log again,
# the test lifts the refusal itself.
class CutOff:
    """A page's state reads, stopped from outside it until the test says it can hear again."""

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

    # Preserve the initial-read count when cutting the page off again.
    def cut(self):
        self._live = False


def held_stale(context):
    """A context whose next page is refused every state read after the one that stamps it."""
    cut = CutOff(lets_through=1)
    stale = primed(context, cut.hold)
    stale.restore = cut.restore
    return stale


# The page's three readiness facts: `lf-upgraded` is the document's — widgets upgraded
# and the anchor pass run — `lf-applied` is the log's, written at the end of every replay
# pass, and `lf-presented` says a deliberately shown waiting surface has completed its
# minimum dwell. Applied state is not yet a completed page while that surface stands.
# The runtime stamps the document in the same breath as it starts that first read and
# never awaits it, so a page can be done becoming itself while knowing nothing of what
# the reader has decided or which version is newest.
#
# One predicate, because it was spelled out in eleven places and only the one that
# noticed ever grew the second half. `open_page` took it when a loaded Linux runner
# dropped three keypresses into pages with nothing yet to answer them; every navigation a
# test makes for itself kept waiting on the document alone. What that leaves out is not a nicety of
# the log: the version chooser and the live-pages button are drawn from a read's answer
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

    The script is installed by `render_checks.install_window_errors`, which
    `render_version` lays in for the same
    reason: one implementation with two callers is what keeps `version check --render`
    and this suite holding the same invariants, and a channel read on one side only is
    that drift in its quietest form.

    Must be called before the page navigates, the init script being what carries it."""
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    render_checks_model.install_window_errors(page)
    return errors


def navigate(page, errors, url, *, wait_until="load", ready=BOTH_STAMPS):
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
        notices = [
            error for error in fresh if render_gate_model.resize_observer_error(error)
        ]
        errors.extend(
            error
            for error in fresh
            if not render_gate_model.resize_observer_error(error)
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
        errors.append(render_gate_model.recurring_resize_observer_error("navigation"))


def key_line(page):
    """What the key line says, once the runtime has had its frame to say it.

    `paintHere` coalesces to a `requestAnimationFrame`, so a read taken in the same
    round-trip as the press that caused it is a read of the frame before. Two frames,
    because the repaint's own rAF may be queued behind this one's.

    Read once and never retried, which is the point of it: a disclosure's word is either
    what the watch painted within the press or what the two-second heartbeat paints
    later, and an assertion that retries goes green on whichever tick lands inside its
    budget —
    reading a stale line as an eventually right one.
    """
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
    )
    return page.locator(".lf-keyline").inner_text()


def open_page(
    browser,
    url,
    *,
    pin=False,
    init_script=None,
    wait_until="load",
    context=None,
    upgraded=True,
    color_scheme="light",
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

    `color_scheme` sets the medium before page modules evaluate. A supplied context owns
    its own medium instead, just as it owns the rest of its browser state.

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
            viewport={"width": 1200, "height": 900}, color_scheme=color_scheme
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


def opened_tab(page, press, tries=3, each=10_000):
    """The tab a press opens, pressed again when the harness loses the one Chromium made.

    Chromium makes the tab every time. After a press whose tab never arrives,
    `Target.getTargets` holds a second page target in this browser context — attached,
    loaded, titled, sitting at the href the press named — while `context.pages` still
    holds one, and it stays that way for the life of the page: the targets pile up press
    after press and Playwright reports none of them. So `expect_page` spends its whole
    timeout waiting on a tab that already exists, and the test reads as though the press
    had opened nothing.

    A driver that loses the handle is not a page state a route can arrange, and there is
    no second channel to reach an unreported tab through, so the press is made again
    rather than waited on longer. This is instrument repair, not tolerance for a flaky
    subject: the press itself is deterministic — the loss reaches every chord, though not
    at one rate: 3, 10 and 1 of 60 presses lost for ⌃-click, ⌃⇧-click and ⇧-click on a
    loaded machine — so a runtime that stopped leaving a real href for the platform to act
    on opens no tab for any of the tries, and the last one says which wait went unanswered.

    A press whose tab is lost still leaves that tab loaded and listening to its server, and no
    caller can close what it was never handed. A test that closes the tab it receives is
    closing only the try that was reported; the rest stand until context teardown. That is
    the standing cost of the repeat, not a leak to chase.

    A press that refuses outright — an anchor hidden, covered, or disabled, the shape a
    runtime regression takes — raises its own timeout from inside the wait, and Playwright's
    `EventContextManager.__exit__` cancels the wait and lets it through. Repeating that
    press would be exactly the tolerance this helper is not, so it is caught where it is
    raised and named as the subject's refusal.
    """
    for attempt in range(tries):
        try:
            with page.context.expect_page(timeout=each) as opened:
                try:
                    press()
                except PlaywrightTimeout as refused:
                    raise AssertionError(
                        "the press timed out before any tab could open: the subject "
                        "refused the gesture, which is not the loss this repeats for"
                    ) from refused
            return opened.value
        except PlaywrightTimeout as lost:
            if attempt == tries - 1:
                raise AssertionError(
                    f"no tab after {tries} presses waiting {each}ms each: either the "
                    "press stopped leaving a real href, or Chromium holds a target "
                    "Playwright never reported"
                ) from lost


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
    starts that read, never awaiting it, so a refusal puts replay on the far side of the
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
