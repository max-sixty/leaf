"""Shared fixtures and assertions for the browser integration modules.

check is static — it parses the file and validates the vocabulary. Everything
downstream of that (a widget's upgrade, the theme's CSS, the runtime's injected
chrome) meets for the first time in the browser, and the failures that live
there are invisible to a linter. This suite drives the shipped examples and
developer feature gallery through Playwright's pinned Chromium headless shell and
asserts the handful of things that were each, at some point, wrong:

  - a widget that upgrades into a box of no size (lf-tabs marked itself with a
    class the runtime's chrome had already claimed for its visually-hidden live
    region, so every tabbed page rendered blank below the lede);
  - the document and the thread panel scrolling in one region, which stacks two
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

import base64
import difflib
import hashlib
import io
import itertools
import json
import math
import os
import re
import shutil
import subprocess
import time
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, cast
from urllib.parse import parse_qsl, urlencode, urlsplit

import pytest
from browser_sources import browser_function
from click.testing import CliRunner
from interact_support import (
    STATED_TIMEOUT,
    append_carried_log_record,
    declare_work,
    package_path,
    publish,
    record_claim,
    wait_for,
    write_record,
)
from model_folds import leaf_page
from PIL import Image
from playwright.sync_api import BrowserContext, Frame, Page, expect
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from leaf import cli as cli_model
from leaf import files as files_model
from leaf import hosting as hosting_model
from leaf import leases as leases_model
from leaf import presence as presence_model
from leaf import render_checks as render_checks_model
from leaf import schema as schema_model
from leaf import state as cleanup_model
from leaf import structure as structure_model
from leaf.findings import Finding, placed
from leaf.render_checks import one_frame, rendered, wait_until_ready
from leaf.render_gate import scheme as render_gate_model
from leaf_dev import browser as dev_browser
from leaf_dev.browser import ON_ME_MARK, scroll_settled, slow_cpu, threads_tab
from leaf_dev.example_data import regression_sources
from leaf_dev.page_fixtures import (
    example_media,
    prepare_page,
    read_fixture,
    record_run_context,
)
from leaf_dev.thread_snapshot_plugin import (
    image_snapshot,  # noqa: F401 — fixture for comparisons and explicit captures
)

ROOT = Path(__file__).parent.parent
WRITE_WATCH_SOURCE = Path(__file__).with_name("write_watch.js")
SHIFT_WATCH_SOURCE = Path(__file__).with_name("shift_watch.js")
WORDS_WATCH_SOURCE = Path(__file__).with_name("words_watch.js")
INPUT_WORK_WATCH_SOURCE = Path(__file__).with_name("input_work_watch.js")
SWAP_WATCH_SOURCE = Path(__file__).with_name("swap_watch.js")
WATCH_PLATFORM_SOURCE = Path(__file__).with_name("watch_platform.js")


def rendering_job_binding_source():
    """Bind generic input scopes to the runtime's synchronous job lifecycle seam."""
    return """Object.defineProperty(HTMLScriptElement.prototype, 'lfObserveQueuedWork', {
      configurable: true,
      set(observe) {
        Object.defineProperty(this, 'lfObserveQueuedWork', {
          value: observe, writable: true, enumerable: true, configurable: true,
        });
        const captured = new WeakMap(), entered = new WeakMap();
        observe((phase, job) => {
          if (phase === 'enqueue') captured.set(job, lfInputWork.captureScope());
          else if (phase === 'run') entered.set(job, captured.get(job)());
          else if (phase === 'finish') {
            entered.get(job)();
            entered.delete(job);
            captured.delete(job);
          } else if (phase === 'cancel') captured.delete(job);
        });
      },
    });"""


def document_port_binding_source():
    """Enroll only endpoints their owner declares as private document channels."""
    return """(() => {
      const ports = new WeakMap();
      Object.defineProperty(HTMLScriptElement.prototype, 'lfDocumentPort', {
        configurable: true,
        get() { return ports.get(this); },
        set(port) {
          ports.set(this, port);
          lfInputWork.observeDocumentPort(port);
        },
      });
    })();"""


@cache
def shift_watch_source():
    """Bind the sensor to the runtime's control, clipping, and scroll-space readings."""
    controls = subprocess.check_output(
        [
            "node",
            "--import",
            "./tests/runtime/dom.mjs",
            "--input-type=module",
            "--eval",
            (
                'import { WORKS, PRESSES, CARET_KEYS } from "./browser/runtime/control-selectors.js";'
                'import { clippingAxes } from "./browser/runtime/rect.js";'
                'import { elementAxes, scrollAxes } from "./browser/runtime/element-frame.js";'
                'import { shadowHost, upFrom, renderedParent } from "./browser/runtime/shadow.js";'
                "process.stdout.write(JSON.stringify([WORKS,PRESSES,CARET_KEYS,...[clippingAxes,shadowHost,upFrom,renderedParent,elementAxes,scrollAxes].map(fn=>fn.toString())]));"
            ),
        ],
        cwd=ROOT,
        text=True,
        timeout=STATED_TIMEOUT,
    )
    (
        interactive,
        presses,
        caret_keys,
        clipping,
        host,
        parent,
        rendered_parent,
        element_axes,
        axes,
    ) = json.loads(controls)
    return (
        WATCH_PLATFORM_SOURCE.read_text()
        + "\n"
        + "const nativePerformance = window.lfWatchPlatform.performance;\n"
        + "const nativeFrame = callback => window.lfWatchPlatform.frame(callback);\n"
        + "const nativeTask = (callback, ...args) => window.lfWatchPlatform.later(callback, ...args);\n"
        + f"((interactive, pressControls, caretKeys, clippingAxes) => {{\n"
        f"const shadowHost = {host};\nconst upFrom = {parent};\n"
        f"const renderedParent = {rendered_parent};\nconst elementAxes = {element_axes};\nconst scrollAxes = {axes};\n"
        f"{SHIFT_WATCH_SOURCE.read_text()}\n}})({json.dumps(interactive)}, {json.dumps(presses)}, {json.dumps(caret_keys)}, {clipping});"
    )


EXAMPLE_PACKAGES = json.loads((ROOT / "examples" / "layer.json").read_text())
EXAMPLES = sorted(p for p in (ROOT / "examples").glob("*.html") if p.stem != "corpus")
assert EXAMPLES, "no examples found — parametrizing over an empty list tests nothing"
FEATURE_GALLERY = ROOT / "examples" / "developer" / "feature-gallery.html"
assert FEATURE_GALLERY.is_file(), "the developer feature gallery is missing"
DEVELOPER_PAGES = tuple(sorted((ROOT / "examples" / "developer").glob("*.html")))
# The inputs `leaf-dev corpus` composes. The corpus is a generated presentation of
# the public pages plus the feature gallery, not another author source. Every authored-
# content sweep uses this source set, while public-site tests read the top-level glob.
PUBLIC_EXAMPLES = tuple(EXAMPLES)
CORPUS_SOURCES = (*PUBLIC_EXAMPLES, *regression_sources(), *DEVELOPER_PAGES)

PASSAGE_SOURCES = (
    FEATURE_GALLERY,
    ROOT / "examples" / "pr-walkthrough.html",
    ROOT / "examples" / "ship-review.html",
    ROOT / "examples" / "developer" / "visual-review-gallery.html",
)

ANCHOR_SOURCES = (
    FEATURE_GALLERY,
    ROOT / "examples" / "pr-walkthrough.html",
    ROOT / "examples" / "ship-review.html",
)


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
        ["page", "stamp", str(page_dir), "--text", text, *complete_args],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def wait_for_revision(page, revision: int) -> None:
    """Wait until a live tab has installed and applied one immutable revision."""
    page.wait_for_function(
        "revision => document.querySelector('meta[name=lf-revision][data-lf-runtime]')"
        "?.content === String(revision)",
        arg=revision,
    )
    # Navigation installs the marker before the fresh runtime reads authoritative state.
    # The marker answers which source is installed; the reading answers whether that
    # source and the server state that selected it became one complete browser view.
    told(page)


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
<lf-ask id="opts-decision"><h2>How should sessions work?</h2>
<lf-options id="opts" choose>
  <lf-option id="opt-a"><strong>Keep the store</strong> Sessions stay where they are,
  which costs a replica and buys revocation for free.</lf-option>
  <lf-option id="opt-b"><strong>Signed tokens</strong> No store at all, until revocation
  quietly puts one back.</lf-option>
</lf-options></lf-ask>
<p id="p">A paragraph carrying <strong>bold text</strong> and <em>emphasis</em> inside it,
so that a selection across the middle of it lands in more than one text node.</p>
<p id="p2">A neighbouring block, so a selection reaching across the boundary between
them has a break in what the user sees and none in what the document holds.</p>
<p id="compound">The setup is in the runbook and the rollback is one flag. When the
shadow index is ready we set up the comparison job and roll back the old one.</p>
<p id="cap">{long}&#128512;</p>
{filler}
<p id="q">A passage far enough down the page that a composer opened on it leaves the
first paragraph uncovered, which is what lets a test click a highlight up there.</p>
<figure id="fig"><svg viewBox="0 0 120 40" width="120" height="40" role="img"
aria-label="sample"><rect x="2" y="2" width="116" height="36" fill="none"
stroke="currentColor"></rect></svg><figcaption>A sample, for element anchors.</figcaption></figure>
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
<lf-ask id="transport-decision"><h2>How should sessions travel?</h2>
<lf-options id="transport" choose settled>
  <lf-option id="opt-lax" chosen><strong>Lax cookie</strong> Host-only, set by the auth
  origin, nothing for a script to read.</lf-option>
  <lf-option id="opt-strict"><strong>Strict cookie</strong> Tighter, but a session
  started from an emailed link arrives logged out.</lf-option>
  <lf-option id="opt-bearer"><strong>Bearer header</strong> Suits the mobile client;
  puts the id where every script can read it.</lf-option>
</lf-options></lf-ask>
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
<div class="layout-tiles" id="numbers">
  <dl id="m-open" class="metric"><dt>Open sessions</dt><dd><strong>1,204</strong> <small>+18%</small></dd></dl>
</div>
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
SAMPLE_PAGE = leaf_page(
    "sample",
    """
<h1 id="h">What a decision looks like</h1>
<lf-sample id="spec" label="a decision">
  <lf-options id="quoted-group" choose>
    <lf-option id="q-shim"><strong>Shim the old schema</strong> Fastest to ship.</lf-option>
    <lf-option id="q-stage" ><strong>Migrate in stages</strong> Table by table.</lf-option>
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
    <lf-option id="q-signed" ><strong>Signed token</strong> No store.</lf-option>
  </lf-options>
  <p id="q-prose">Refill rules:
    <lf-suggestion id="quoted-suggestion">
      <lf-old>Refill every feeder each morning.</lf-old>
      <lf-new>Refill when the camera shows it half-empty.</lf-new>
    </lf-suggestion></p>
</lf-sample>
<lf-ask id="live-group-decision"><h2>How should the schema migrate?</h2>
<lf-options id="live-group" choose>
  <lf-option id="l-shim"><strong>Shim the old schema</strong> Fastest to ship.</lf-option>
  <lf-option id="l-stage" ><strong>Migrate in stages</strong> Table by table.</lf-option>
</lf-options></lf-ask>
<lf-ask id="live-rows-decision"><h2>What should happen to the nightly job?</h2>
<lf-options id="live-rows" choose>
  <lf-option id="l-row-keep">Keep the nightly job</lf-option>
  <lf-option id="l-row-drop">Drop it and poll on demand</lf-option>
</lf-options></lf-ask>
<lf-ask id="live-settled-decision"><h2>How should sessions travel?</h2>
<lf-options id="live-settled" choose settled>
  <lf-option id="l-lax" chosen><strong>Lax cookie</strong> Host-only.</lf-option>
  <lf-option id="l-bearer"><strong>Bearer header</strong> Suits mobile.</lf-option>
  <lf-option id="l-signed" ><strong>Signed token</strong> No store.</lf-option>
</lf-options></lf-ask>
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
# `text` and the widgets ride `markup`, as `leaf thread reply` writes them.
SAMPLE_TEXT = (
    "Two shapes for the same question — first the one I'd ship, then, for the "
    "record, the framing it replaces:"
)
SAMPLE_MARKUP = """<lf-ask id="rp-live-decision"><h3>How should the schema migrate?</h3>
<lf-options id="rp-live" choose>
  <lf-option id="rp-shim"><strong>Shim the old schema</strong> Fastest to ship.</lf-option>
  <lf-option id="rp-stage" ><strong>Migrate in stages</strong> Table by table.</lf-option>
</lf-options></lf-ask>
<lf-sample id="rp-spec" label="the April thread">
  <lf-options id="rp-quoted" choose>
    <lf-option id="rp-memory"><strong>App memory</strong> Nothing to build.</lf-option>
    <lf-option id="rp-sticky"><strong>Sticky sessions</strong> Until an instance recycles.</lf-option>
  </lf-options>
</lf-sample>
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
<lf-ask id="approach-decision"><h2>How should the schema migrate?</h2>
<lf-options id="approach" choose>
  <lf-option id="opt-shim"><strong>Shim the old schema</strong> Fastest to ship.</lf-option>
  <lf-option id="opt-stage"><strong>Migrate in stages</strong> Table by table.</lf-option>
</lf-options></lf-ask>
<lf-board id="work">
  <lf-column id="col-doing" label="Doing">{IMPORTER_CARD}</lf-column>
  <lf-column id="col-done" label="Done"><lf-card id="card-notes"><strong>Draft the notes</strong></lf-card></lf-column>
</lf-board>
""",
)


# A page's key is minted per page; fixed here so a test can build a URL for a
# server it did not start.
TOKEN = "test-page-key"


@pytest.fixture
def serve(tmp_path, monkeypatch, initialized_page, request):
    """Publish HTML as the newest version of a fresh page directory and serve it,
    as the real server does — vendoring included, so the assets under test are this
    repo's. Markup is one version; an example is every version it ships, stamped
    oldest first, so a revised one arrives with a picker, a base to compare against
    and a thread opened before the revision.

    Handed an example's path rather than its markup, it also lays in the three
    things that example ships beside itself: the media it names, external data,
    and the event log, where it has one. The log for the same reason
    `test_page_fixtures_pass_check` reads one — a page is what its markup and its
    current log make together, and a corpus that reads only the markup is reading
    half of it. A thread and any widget a message carries exist nowhere else, so
    without this every sweep is green over a page the user never gets.

    Explicit checkout packages may be passed as Paths; the fixture selects them
    relative to its working directory, independently of the checkout and HOME.

    `seed_log=False` leaves an example's log out while still laying in its media, for a
    test that appends those events itself. `layer_registry` and `layer_widgets` add a
    project package, a registry and its widget modules, for a reading the layer makes
    from declarations, so the test does not depend on which shipped tag declares them.

    Each call gets its own directory, reached through `serve.page_dir`. Sharing one
    meant a test that serves two examples in a single body re-initialised over the
    first and appended the second's events to a log already holding the first's,
    which reads as a page rather than failing."""

    class Serving(Protocol):
        httpd: object
        servers: list
        page_dir: Path

        def __call__(self, *args, **kwargs) -> str: ...

    def go(
        source,
        comments=0,
        anchored=(),
        media=None,
        events=(),
        layer_registry=None,
        layer_widgets=None,
        packages=None,
        preview=None,
        website_publication=None,
        seed_log=True,
        page_files=None,
    ):
        monkeypatch.chdir(tmp_path)  # resolve explicitly selected fixture packages
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
        fixture = read_fixture(example) if example else None
        selected_packages = (
            fixture.packages
            if fixture is not None and packages is None
            else (
                *EXAMPLE_PACKAGES,
                ROOT / "tests/fixtures/packages/work",
            )
            if packages is None
            else packages
        )
        if layer_registry is not None or layer_widgets:
            selected_packages = (*selected_packages, "./.leaf")
        selected_packages = tuple(
            package_path(item) if isinstance(item, Path) else item
            for item in selected_packages
        )
        d = tmp_path / f"page{len(servers)}"

        def run_leaf(*args, input_text=None):
            result = CliRunner().invoke(cli_model.cli, list(args), input=input_text)
            assert result.exit_code == 0, result.output

        def prepare(target):
            assert fixture is not None
            prepare_page(
                target,
                fixture,
                run_leaf,
                initialize=False,
                seed_log=seed_log,
                final_status=None,
                current_note="t",
                earlier_note="t",
            )

        # An example is a shape of its own, versions stamped and log seeded, since
        # preparing one stamps every version it ships: seconds per page, paid once
        # per worker rather than once per test.
        if fixture is not None:
            assert example is not None
            template = ((example.resolve(), seed_log), prepare)
        else:
            template = None
        initialized_page(
            d,
            selected_packages,
            template,
        )
        if fixture:
            # The page pool can lend a copy hours after it stamped the template.
            # Its current publication is new to this test, so keep the timestamp
            # used by worker freshness readings new too. Earlier notes and seeded
            # history retain their fixture times.
            log = d / "events.jsonl"
            lines = log.read_text(encoding="utf-8").splitlines()
            for index in range(len(lines) - 1, -1, -1):
                event = json.loads(lines[index])
                if event["kind"] == "note":
                    event["ts"] = datetime.now(UTC).isoformat(timespec="seconds")
                    lines[index] = json.dumps(event, separators=(",", ":"))
                    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    break
        if not fixture:
            html = source
            (d / "index.html").write_text(html)
            references = structure_model.SourceDocument(html).authoring.media_refs
            for reference in references:
                fixture_media = example_media() / reference.removeprefix("/media/")
                if fixture_media.is_file():
                    (d / "media").mkdir(exist_ok=True)
                    shutil.copy2(fixture_media, d / "media" / fixture_media.name)
        record_run_context(
            d,
            purpose="test",
            run=tmp_path,
            authored_source=example,
            test=request.node.nodeid,
        )
        for name, content in (page_files or {}).items():
            path = d / "page" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        for name, data in (media or {}).items():
            path = d / name.lstrip("/")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for event in events:
            append_carried_log_record(d, event)
        if fixture is None:
            assert publish(d, "t")["revision"] == 1
        for i in range(comments):
            append_carried_log_record(
                d,
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": f"Comment {i}. " + "Long enough to wrap. " * 4,
                },
            )
        for section, quote in anchored:
            append_carried_log_record(
                d,
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "About this bit.",
                    "anchor": {"section": section, "quote": quote},
                },
            )
        if preview is not None:
            write_record(d / schema_model.PREVIEW_FILE, preview)
        server = hosting_model.TemporaryPageServer(
            d,
            token=TOKEN,
            page_options={"publication": website_publication},
        ).start()
        servers.append(server)
        serving.httpd = server.httpd
        serving.servers = servers
        serving.page_dir = d  # for tests that publish a v2 or read the event log
        # The key rides in the URL exactly as it does in a handover, so the first
        # navigation of each browser context earns the cookie the rest of the
        # page's own fetches go out under.
        version = len(fixture.versions) if fixture else 1
        return f"{server.origin}/versions/v{version}.html?t={TOKEN}"

    serving = cast(Serving, go)
    servers = []
    yield serving
    for server in servers:
        server.close()


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


# What the page has sent and how much of it has come back, read off the ledger the
# runtime paints for exactly this user. The suite once counted the same numbers from
# outside, on the browser's own request and response events, so that nothing was put
# inside the thing under test; that watcher was a second representation of the outbox's
# lifecycle, and it needed a protocol of its own to keep step — a post a reload killed
# that no event reported, a waiter woken before the listeners that counted, a body read
# with no deadline. The runtime already states its readiness for this user
# (`lfReadiness`); delivery is one more fact it states rather than one the harness
# infers, and nothing is injected to obtain it.
class Traffic:
    """One page's trips to the server, as the runtime counts them.

    The runtime keeps the ledger (runtime/traffic.js) and paints it on the root
    element as `data-lf-traffic`; this reads it. `sends` counts attempts, so a retry is a
    second send. `pending` is the outbox's own list of attempts with
    no delivery outcome yet, so a failed request stays pending while the outbox retries
    it, and a definitive refusal or a response naming the accepted attempt clears it.
    That is delivery. Whether the page then applied the returned state is a separate
    product fact asserted on the surface that needs it.

    The count is the document's: a navigation starts it over with the page that carries
    it, and a page that has not booted reads as nothing sent."""

    KEYS = ("sends", "acked", "asked", "heard", "pending")

    def __init__(self, page):
        self.page = page

    def _raw(self):
        return self.page.evaluate(
            "() => document.documentElement.dataset.lfTraffic ?? null"
        )

    @classmethod
    def _parse(cls, raw):
        counts = json.loads(raw) if raw else {"pending": []}
        return SimpleNamespace(**{key: counts.get(key, 0) for key in cls.KEYS})

    def read(self):
        """The ledger as one reading, every field taken from the same paint."""
        return self._parse(self._raw())

    def __getattr__(self, name):
        if name in self.KEYS:
            return getattr(self.read(), name)
        raise AttributeError(name)

    @staticmethod
    def describe(reading):
        return (
            f"sends={reading.sends} acked={reading.acked} "
            f"pending={len(reading.pending)} asked={reading.asked} heard={reading.heard}"
        )

    def __str__(self):
        return self.describe(self.read())


def _traffic(page):
    """The ledger reader `open_page` hung on this page when it made it."""
    return page.lf_traffic


def _until(page, fact, wanted):
    """Block until `fact` holds of the page's traffic.

    The runtime repaints the ledger at each edge it counts, so this waits on the paint
    changing and asks the fact of each new reading — no polling interval to pick beyond
    the frame the browser paints on, and nothing added to the page for it. One read per
    round: the paint the fact was judged on is the one the wait watches for a change
    from, and the failure names the last reading rather than taking another past the
    deadline.

    A wait that runs out names the caller's wanted fact and prints its starting and
    final readings. The deadline is fixed when the wait begins, so a page that repaints
    forever cannot keep a false fact alive."""
    traffic = _traffic(page)
    began = None
    deadline = time.monotonic() + render_checks_model.SERVED_TIMEOUT_MS / 1000
    while True:
        raw = traffic._raw()
        reading = traffic._parse(raw)
        if began is None:
            began = traffic.describe(reading)
        if fact(reading):
            return
        remaining = int((deadline - time.monotonic()) * 1000)
        if remaining <= 0:
            raise AssertionError(
                f"the page never {wanted}: the wait began on {began} and gave up on "
                f"{traffic.describe(reading)}"
            )
        try:
            page.wait_for_function(
                "was => (document.documentElement.dataset.lfTraffic ?? null) !== was",
                arg=raw,
                timeout=remaining,
            )
        except PlaywrightTimeout:
            continue


# A browser trip is over when every post the page issued has ended and the outbox holds
# no attempt without an outcome. Each half misses what the other names. A gesture's
# request failure ends its post but not its delivery, because the outbox keeps the same
# attempt and retries; `acked` alone would return on that ambiguous edge. A post that
# skips the outbox — a bookkeeping event such as `read` (delivery.js), the page's own
# `error` report, a media upload (layer-client.js) — leaves `pending` empty while it is
# still on the wire; `pending` alone returns before the server has it. A test that
# holds requests on a route must release every one, that report included.
# Neither says whether the runtime then applied the response state; tests assert that
# on the affected page surface.
def heard_back(reading):
    """Whether one ledger reading says what the page sent has all come back."""
    return reading.acked == reading.sends and not reading.pending


def round_trip(page):
    """Wait for what this page has sent to have come back to it."""
    _until(page, heard_back, "heard back what it sent")


# A press or a click reaches the runtime inside the driver's call and posts behind it, so
# `round_trip` alone cannot wait for the gesture just made: a post the gesture has not
# issued yet is not pending, the trip is over before it begins, and the log read behind it
# answers with whatever stood last — the page's opening note, or the gesture before this
# one. The assertion then holds an event nobody made, and it holds it only on a machine
# slow enough to lose the race. Naming the gesture's own send first is the arrangement
# that closes the window; `_until` is what waits on it.
@contextmanager
def sending(page, what):
    """Enclose a gesture whose own event has to be in the wire before its trip is over.

    Waits for one further send to enter the wire, then for everything the page has sent
    to come back, so a log or state read behind the block is a read of this gesture.
    `what` names the send for the failure a wait that runs out raises. The ledger is the
    document's, so a gesture that navigates cannot be enclosed here: the count it would
    wait to grow starts over with the new document.
    """
    sends = _traffic(page).sends
    yield
    _until(page, lambda traffic: traffic.sends > sends, f"sent {what}")
    round_trip(page)


# The same arrangement for a test that holds the wire open with `page.route`, and the one
# place the ledger is the wrong fact to state it over. The runtime counts a send as it
# makes it, while the driver is handed the request over its own connection a beat later,
# so `traffic.sends == 1` is already true while the route list is still empty and the
# `held[0]` behind the wait raises IndexError on a machine loaded enough to lose that
# beat. The same gap opens on a list of the requests the handler let through: the send is
# counted before the route the handler would append even exists here. The list the test
# goes on to read is what the wait belongs over, and `_until` cannot carry it: its only
# wake-up is the ledger repainting, and a paused request paints nothing further, so a
# route that lands after the send's paint would wait out the whole deadline. The browser's
# own record already shows the send was made, so this repeats a driver call — the thing
# that dispatches the route here — until the list has it.
def holding(page, held, count, what):
    """Wait until `held` has collected `count` requests the route put there."""
    deadline = time.monotonic() + render_checks_model.SERVED_TIMEOUT_MS / 1000
    while len(held) < count:
        if time.monotonic() >= deadline:
            raise AssertionError(
                f"the route never took {what}: {len(held)} of {count} "
                f"dispatched into this process, on {_traffic(page)}"
            )
        page.wait_for_timeout(20)


@contextmanager
def held_frames(page):
    """Keep frame-dependent handoffs pending while real input supplies a newer intent."""
    page.evaluate(
        """() => {
          const frame = requestAnimationFrame.bind(window);
          const cancel = cancelAnimationFrame.bind(window);
          const held = new Map();
          let handle = 1e6;
          window.requestAnimationFrame = callback => {
            held.set(++handle, callback);
            return handle;
          };
          window.cancelAnimationFrame = handle => held.delete(handle);
          window.leafReleaseFrames = () => {
            window.requestAnimationFrame = frame;
            window.cancelAnimationFrame = cancel;
            for (const callback of held.values()) frame(callback);
            held.clear();
          };
        }"""
    )
    try:
        yield
    finally:
        page.evaluate("leafReleaseFrames()")


_NOTES_OF = """(holder) => {
    const root = document.querySelector(holder);
    const named = root ? [root, ...root.querySelectorAll('*')] : [];
    return [...new Set(named.flatMap((el) => el.ariaDetailsElements ?? []))]
        .filter((note) => note.matches('.lf-mark-note'));
}"""


def expect_comment_notes(page, holder, count):
    """Wait until the element `holder` (a selector) and the elements inside it name
    `count` comment notes as their details (anchor-note-view.js)."""
    page.wait_for_function(
        f"([holder, count]) => ({_NOTES_OF})(holder).length === count",
        arg=[holder, count],
    )


def comment_note(page, holder):
    """The first comment note the element `holder` (a selector), or one inside it, names
    as its details.

    A note stands in the chrome rather than in its block, so a block's own note is found
    through the relation a screen reader follows. The locator is resolved by position
    among the chrome's notes, so take it once the note stands and use it before another
    block's note goes."""
    page.wait_for_function(f"(holder) => ({_NOTES_OF})(holder).length > 0", arg=holder)
    index = page.evaluate(
        f"""(holder) => [...document.querySelectorAll('.lf-mark-note')]
            .indexOf(({_NOTES_OF})(holder)[0])""",
        holder,
    )
    return page.locator(".lf-mark-note").nth(index)


@contextmanager
def _accessibility(page):
    """Read nodes of the browser's accessibility tree, by selector or backend node:
    what a screen reader is given, not the DOM attributes that asked for it."""
    cdp = page.context.new_cdp_session(page)

    def ax(selector=None, **at):
        if selector is not None:
            root = cdp.send("DOM.getDocument")["root"]["nodeId"]
            at = cdp.send("DOM.querySelector", {"nodeId": root, "selector": selector})
        return cdp.send(
            "Accessibility.getPartialAXTree", {**at, "fetchRelatives": False}
        )["nodes"][0]

    try:
        yield ax
    finally:
        cdp.detach()


def accessible_details(page, selector):
    """The names of what the element `selector` names as its details."""
    with _accessibility(page) as ax:
        return [
            ax(backendNodeId=related["backendDOMNodeId"])["name"]["value"]
            for prop in ax(selector).get("properties", [])
            if prop["name"] == "details"
            for related in prop["value"].get("relatedNodes", [])
        ]


def plant_quiet_word(page, selector, holding):
    """Hang a word for a user listening (`.lf-quiet`, the shape a widget's quiet word
    takes) at the end of the first `selector` element whose text holds `holding`, and
    return it as a locator."""
    page.evaluate(
        """([selector, holding]) => {
          const holder = [...document.querySelectorAll(selector)]
            .find((el) => el.textContent.includes(holding));
          const word = Object.assign(document.createElement('span'), {
            id: 'planted-quiet', className: 'lf-ui lf-quiet', textContent: 'quiet word',
          });
          word.dataset.lfGen = '1';
          holder.append(word);
        }""",
        [selector, holding],
    )
    return page.locator("#planted-quiet")


# The other direction of the same trip. Nothing a test writes into the page directory
# announces itself — a declared status, a changed wait lease, an appended event all reach
# the page when it next reads — so an assertion made straight after the write is waiting
# on whatever budget expect() happens to carry. Timed, that wait takes 1.8 to 2.3 of the
# default five seconds, and it takes them every time.
#
# So ask the page whether it has caught up with what the server holds: its readiness
# reading answers that against an `/api/state` answer, and names no transport.
# Counting answered requests said the same thing only while a fixed interval made them
# the same thing: the page now asks when its freshness reading says the page has moved, so a
# count of obligations started here reaches the answer that carries the news only by luck of
# the ordering.
def told(page, *, until=None):
    """Wait until the page has taken in everything the server now holds.

    Call it after the test writes a version, event, status, or lease behind a live
    page, before reading that page. It asks only through the `state` stage: a test may
    write behind a page it is holding mid-gesture, where the rest of readiness waits on
    the gesture rather than the write. The server's answer is asked through the
    context's request API rather than the page: it carries the same cookie, and it is
    not seen by page routes or by the traffic watcher, so a test that stubs or counts
    /api/state sees exactly what it did before this call existed. `until` waits for
    a server fact another page publishes asynchronously before asking this page to
    adopt that answer."""
    origin = urlsplit(page.url)

    def read():
        answer = page.request.get(f"{origin.scheme}://{origin.netloc}/api/state")
        assert answer.ok, f"the server would not say what it holds: {answer.status}"
        return answer.json()

    # A neighboring leaf publishes its row on its own server's next maintenance
    # pass. A state answer from this page can still carry the previous row just
    # after a test writes that neighbor's status.
    state = (
        wait_for(read, until, failure="the server did not publish the expected state")
        if until is not None
        else read()
    )
    wait_until_ready(page, state, through="state")


def nudge(page_dir):
    """Give the page a reason to ask, changing nothing it shows.

    The page asks for state when its freshness reading says the page has moved, and the
    reading names file stamps. A test that wants the page's next obligation — to park it, or to
    watch it refused — used to wait for the poll's timer; now it moves the revisions
    directory stamp, which the state fingerprint reads without changing page content.
    """
    os.utime(page_dir / "revisions")


def ticked(page):
    """Wait for the shared clock and any deferred projection to finish a tick.

    This is independent of network reads and does not imply a state repaint.
    """
    page.evaluate(
        """() => {
          window.__lfTicked = false;
          document.addEventListener('lf-tick', () => { window.__lfTicked = true; },
                                    { once: true });
        }"""
    )
    page.wait_for_function("() => window.__lfTicked")


# `z` is the one press whose subject is read rather than pointed at, so the dispatcher
# holds it dead while the page holds a gesture no log read has accounted for — this
# press's own trip included (unrecordedGesture). Every other press acts on what is under
# the user and can be made the moment the paint is there; the paint arrives a turn
# before the trip it was made on is over, so a `z` made on it is a press the dispatcher
# refuses, and what the refusal leaves behind is the page an assertion on the un-undone
# state would find anyway. A test cannot tell that from an undo that did the wrong thing:
# it reads the no-op as the wrong answer, or waits its budget out and calls it a hang.
#
# So the press waits on the fact the page states rather than on the gesture before it
# having painted: the dispatcher's own reading of which commands a key reaches where the
# user is located (`available_commands`), the predicate (`live`) the leaf's menu also
# greys its Undo row by. Then the trip: the press's own send is not counted at the
# moment it is made, and a `round_trip` that reads the counters before the browser has
# reported the request is a wait on a page that has not started moving.
def undo(page):
    """Take the last gesture back, from the moment the dispatcher would take `z`."""
    page.evaluate(AVAILABLE_COMMANDS)
    page.wait_for_function(
        "() => window.__lfAvailableCommands()['history.undo']?.includes('z') ?? false"
    )
    with sending(page, "the withdrawal"):
        page.keyboard.press("z")


# Each command the dispatcher would run from the current location, by its id, with the
# keys that reach it there; a command no key reaches (one only a control presses) lists
# none. The dispatcher's own reading (keyboard/dispatch.js, `availableCommandRoutes`),
# which the leaf's menu greys its rows by too. Evaluating it also leaves the reading on
# the page as `window.__lfAvailableCommands`, synchronous, for `wait_for_function`, which
# takes an async predicate's promise as a truthy answer and returns at once.
AVAILABLE_COMMANDS = """async () => {
  const {availableCommandRoutes} = await window.__lfCheckApi();
  // A command can stand in more than one scope, such as a widget's own and the Ask's
  // digit for it, so the keys of every row with its id are the keys that reach it.
  window.__lfAvailableCommands = () => {
    const reached = {};
    for (const [row, keys] of availableCommandRoutes())
      reached[row.id] = [...new Set([...(reached[row.id] ?? []),
        ...[...keys].filter((key) => typeof key === 'string')])].sort();
    return reached;
  };
  return window.__lfAvailableCommands();
}"""


def available_commands(page):
    """What the dispatcher would run from the current location now, read once after
    every repaint the input so far queued: `{command id: [keys]}`.

    The bottom key line used to say this as hints; the panel says it nowhere but in a
    command's effect, so prefer pressing the key and asserting what it did. Read this
    where the subject is that a command is withheld, such as Undo while a gesture is
    unaccounted for."""
    rendered(page)
    return page.evaluate(AVAILABLE_COMMANDS)


def wait_for_check_api(page, predicate: str, arg=None, **kwargs):
    """Wait until `predicate(api, arg)`, a synchronous function of the runtime's check
    API (runtime/check-api.js), returns a truthy value, and return its handle.

    The API arrives by a dynamic import, so it is resolved first and left on the page:
    `wait_for_function` takes an async predicate's promise as a truthy answer."""
    page.evaluate("async () => { window.__lfCheck = await window.__lfCheckApi(); }")
    return page.wait_for_function(
        f"(arg) => ({predicate})(window.__lfCheck, arg)", arg=arg, **kwargs
    )


# A request a test stops is cancelled rather than failed. The page cannot tell the two
# apart — both reject the fetch the runtime awaits and leave it on the same `catch`.
# The console can tell them apart, which is what the reason is chosen for:
# tests/AGENTS.md, "Test-made noise". A refused event
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
# unrouted. Freshness is not a state read and is not refused; failed state reads retry
# on the two-second clock for as long as the route stands.
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


FIRST_PAINT = """() => performance
  .getEntriesByType('paint')
  .some(entry => entry.name === 'first-contentful-paint')"""


def displayed(page):
    """Wait for first contentful paint before measuring pre-runtime geometry.

    Visibility checks can force layout before a render-blocking stylesheet arrives;
    first contentful paint excludes that unstyled reading."""
    try:
        page.wait_for_function(FIRST_PAINT)
    except PlaywrightTimeout as error:
        raise AssertionError(
            f"{page.url} never reported a first contentful paint"
        ) from error


def draft_key(page, ctx: str) -> str:
    """The `localStorage` key the page's own draft store keeps the draft at `ctx`
    under, page scope included (`whereDraft`, runtime/drafts.js)."""
    return page.evaluate(
        """async ctx => (await window.__lfCheckApi())
          .whereDraft(ctx).key""",
        ctx,
    )


def stored_draft(page):
    """The page's own reader of stored drafts (`storedDraft`, runtime/drafts.js)."""
    return page.evaluate_handle(
        """async () => (await window.__lfCheckApi())
          .storedDraft"""
    )


def stored_draft_text(page, ctx: str) -> str | None:
    """The words storage holds for the draft at `ctx`, or None once it is settled or
    absent: what another tab or a reload would find, whatever this tab shows."""
    return page.evaluate(
        """([read, ctx]) => {
          const record = read(ctx);
          return record && !record.settled ? record.text : null;
        }""",
        [stored_draft(page), ctx],
    )


_STORED_DRAFT_SETTLED = "([read, ctx]) => read(ctx)?.settled === true"


def stored_draft_settled(page, ctx: str) -> bool:
    """Whether storage holds the draft at `ctx` as settled (its tombstone)."""
    return page.evaluate(_STORED_DRAFT_SETTLED, [stored_draft(page), ctx])


def until_draft_settled(page, ctx: str) -> None:
    """Wait until storage holds the draft at `ctx` as settled."""
    page.wait_for_function(_STORED_DRAFT_SETTLED, arg=[stored_draft(page), ctx])


_BROWSER_PROBLEM_LISTS = None
_TEST = None
_CPU_THROTTLE = None


def pytest_addoption(parser):
    parser.addoption(
        "--cpu-throttle",
        type=float,
        metavar="RATE",
        help="Slow the CPU of every Chromium page the browser fixtures open this many times",
    )


def pytest_configure(config):
    global _CPU_THROTTLE
    _CPU_THROTTLE = config.getoption("--cpu-throttle")


def watches_shifts(test):
    """Every test watches shifts but those in a module marked `shifts_unsurveyed`,
    which still await a survey, and of those the ones marked `watch_shifts` watch too.

    This selection does not lift the watcher's first-presentation exemption.
    """
    return (
        test.get_closest_marker("shifts_unsurveyed") is None
        or test.get_closest_marker("watch_shifts") is not None
    )


@contextmanager
def clean_browser(test=None):
    """Reject every browser problem a test did not explicitly consume.

    The function-scoped browser fixture owns this collector along with its contexts.
    A worker runs one test at a time, so one process-local collector covers pages made
    by `WatchedBrowser`, render helpers, and tests that navigate a page
    themselves. The fixture hands over its `test` node to select shift coverage
    (`watches_shifts`); every problem a watch reports reaches this collector. A test
    that failed or left problems leaves a picture of each page (`_picture_pages`).
    """
    global _BROWSER_PROBLEM_LISTS, _TEST
    assert _BROWSER_PROBLEM_LISTS is None, "browser problem collector already active"
    captured = []
    _BROWSER_PROBLEM_LISTS = captured
    _TEST = test
    try:
        yield
    finally:
        _BROWSER_PROBLEM_LISTS = None
        _TEST = None
    problems = [
        f"{getattr(page, 'url', '<browser page>')}: {problem}"
        for page, problem_list in captured
        for problem in problem_list
    ]
    if test is not None and (problems or getattr(test, "lf_failed", False)):
        _picture_pages(test, [page for page, _ in captured])
    assert not problems, "\n".join(problems)


def _picture_pages(test, pages):
    """Save what each page of a failing test shows under `.tmp/test-results/screens/`,
    which CI uploads with the junit results: an assertion names only what it read, and
    the picture shows the rest, such as a widget drawn without its styles. A page that
    can't answer leaves no picture, since the test's own failure is the one to report.
    The node id is cut to fit a file name, and its hash keeps cut names apart."""
    stem = re.sub(r"[^\w.-]+", "_", test.nodeid)[:150]
    name = f"{stem}-{hashlib.sha1(test.nodeid.encode()).hexdigest()[:8]}"
    for n, page in enumerate(pages):
        if page.is_closed():
            continue
        try:
            page.screenshot(
                path=ROOT / f".tmp/test-results/screens/{name}-{n}.png",
                timeout=render_checks_model.SERVED_TIMEOUT_MS,
            )
        except PlaywrightError:
            continue


def judge_watches():
    """Judge every layout shift each watched page makes, once the frames the test's
    last act changed have painted (`shift_watch.js`, `lfShiftsJudged`), then every
    loss of typed words so far (`words_watch.js`, `lfWordsJudged`), and then the swaps
    in the frame that lays out the last act (`swap_watch.js`, `lfSwapsJudged`).

    Chrome hands a frame's shifts to the observer only after it paints, so a test whose
    last act moves the page or takes words away would end before the report. Judgement
    waits for that evidence with a hang deadline; elapsed time cannot count as a
    completed paint. A detached frame has no further paint to judge; native frame
    lifetime, rather than protocol error text, releases its pending read. Scripts-disabled
    pages have no script-driven sensors to judge.
    `conftest.py` calls this as the test body returns, while the
    pages' servers still answer: a page left painting
    after its server is gone lets its failed fetches reach the console."""
    for page, _ in _BROWSER_PROBLEM_LISTS or ():
        if not page.is_closed() and page.lf_java_script_enabled:
            for frame in page.frames:
                try:
                    if not _reachable(frame):
                        continue
                    _judge_frame_watches(frame)
                except PlaywrightError:
                    # Enumeration owns no frame lifetime: a sample or its page can
                    # disappear across any subsequent protocol request. Native
                    # lifetime facts release it; every live-frame failure propagates.
                    if not frame.is_detached() and not page.is_closed():
                        raise


def _reachable(frame):
    """Whether Playwright holds a document in `frame` that can answer it.

    Playwright's Firefox loses some sample frames: it reports one at `about:blank`
    or at an earlier URL of its document, runs none of the suite's init scripts in
    it, and an evaluate there never returns. Such a frame has no watch to judge.
    Every frame in another engine, and every top-level document, is asked."""
    if (
        frame.parent_frame is None
        or frame.page.context.browser.browser_type.name != "firefox"
    ):
        return True
    try:
        frame.wait_for_function(
            "() => true", polling=100, timeout=render_checks_model.SERVED_TIMEOUT_MS
        )
    except PlaywrightTimeout:
        return False
    return True


def _judge_frame_watches(frame):
    """Drain a frame while its page owns it; the caller handles native detachment."""
    frame.evaluate(
        """() => {
            const judgement = window.lfWatchJudgement = { complete: false, error: null };
            Promise.resolve().then(async () => {
              await window.lfShiftsJudged?.();
              await window.lfWordsJudged?.();
              await window.lfSwapsJudged?.();
            }).then(() => { judgement.complete = true; },
              error => { judgement.error = error; });
        }"""
    )
    frame.wait_for_function(
        """() => {
            const judgement = window.lfWatchJudgement;
            if (judgement.error) throw judgement.error;
            return judgement.complete;
        }""",
        polling=10,
        timeout=render_checks_model.SERVED_TIMEOUT_MS,
    )
    frame.evaluate("delete window.lfWatchJudgement")


def watched(page, *, java_script_enabled=True):
    """Collect browser problems into one retained list per page, each a record
    (`leaf/findings.py`) a test reads by its fields.

    The browser's own reports, taken from Playwright's events as the render gate takes
    them: console warnings and errors, and uncaught exceptions.
    Window errors without exceptions join them, installed through the same
    `install_window_errors` helper the render gate uses, and so do the health
    sensors' findings, which each sensor hands over as a record through the
    `__leafWatchFinding` binding: DOM writes that change nothing (`write_watch.js`),
    layout shifts without input or that carry a field being typed in
    (`shift_watch.js`), typed words leaving the screen without a key or press
    (`words_watch.js`), and a row sized by the occupant that took a seat in it
    (`swap_watch.js`).
    Call before navigation so the init scripts take effect. With scripting disabled,
    retain native console and page errors but install no script-driven sensors and
    await none at judgement.
    Repeated calls return the existing list. `tests/AGENTS.md`, "Browser errors", owns consumption and cleanup policy."""
    assert _BROWSER_PROBLEM_LISTS is not None, (
        "watched pages need the function-scoped browser fixture"
    )
    if (existing := getattr(page, "lf_errors", None)) is not None:
        return existing
    errors = []
    _BROWSER_PROBLEM_LISTS.append((page, errors))
    page.lf_errors = errors
    page.lf_java_script_enabled = java_script_enabled

    def console_message(message):
        if (problem := render_gate_model.console_finding(message)) is not None:
            errors.append(problem)

    def window_error(error):
        # `navigate` takes the ResizeObserver notices of a navigation it is making;
        # any other notice, like every other error, reaches the fixture.
        problem = render_gate_model.window_finding(error)
        notices = getattr(page, "lf_resize_notices", None)
        if problem.code == "resize-loop" and notices is not None:
            notices.append(problem)
        else:
            errors.append(problem)

    page.on("console", console_message)
    render_gate_model.collect_page_exceptions(page, errors)
    if not java_script_enabled:
        return errors
    render_checks_model.install_window_errors(page, window_error)
    page.expose_binding(
        "__leafWatchFinding", lambda _source, found: errors.append(Finding.read(found))
    )
    # The watch reads the Layout Instability API, which only Chromium implements.
    shifts = page.context.browser.browser_type.name == "chromium" and (
        _TEST is None or watches_shifts(_TEST)
    )
    page.add_init_script(script=watch_sources(shifts))
    return errors


@cache
def watch_sources(shifts: bool) -> str:
    """Every sensor `watched` installs, as the one init script it registers.

    One script keeps them in the order they rely on: write tracking first, then cause
    tracking before the words and swap subscribers, then the shift watch, which
    installs after write_watch.js. Playwright does not promise an order between
    separately registered scripts, and each registration is a round trip to the
    browser for every page a test makes. Each sensor runs in a block of its own, so
    one that throws still reaches the page's error collector and the rest install,
    as they did as separate scripts."""
    sensors = [
        WRITE_WATCH_SOURCE.read_text(),
        *(
            source.read_text()
            for source in (
                WATCH_PLATFORM_SOURCE,
                INPUT_WORK_WATCH_SOURCE,
                WORDS_WATCH_SOURCE,
                SWAP_WATCH_SOURCE,
            )
        ),
        rendering_job_binding_source(),
        document_port_binding_source(),
        *([shift_watch_source()] if shifts else []),
        # Diagnostics join the captured graph through its compiled public entries.
        # Tests cannot name a private source path or load a second runtime from the
        # mutable layer.
        """(() => {
          const entry = path => {
            const boot = document.querySelector('script[data-lf-entry]').dataset.lfEntry;
            return import(new URL(path, new URL(boot, location.href)).href);
          };
          window.__lfWidgetApi = () => entry('runtime/widget-api.js');
          window.__lfCheckApi = () => entry('runtime/check-api.js');
          window.__lfOverlayApi = () => entry('runtime/annotation-overlay/check-api.js');
          window.__lfClientApi = () => entry('runtime/layer-client.js');
          window.__lfVendorImport = name => entry(`vendor/${name}`);
        })();""",
    ]
    return "\n".join(
        f"try {{\n{sensor}\n}} catch (error) {{ queueMicrotask(() => {{ throw error; }}); }}"
        for sensor in sensors
    )


@contextmanager
def restarting(page):
    """Enclose a span in which the test replaces the page's server or executable layer.

    A layer replacement reloads the document. WebKit reports even a caught fetch
    rejection from the departing document as a native page exception while its
    replacement is loading. A stopped server answers no fetch, and the words the
    failure arrives in depend on which fetch was in flight when it stopped: a bare
    `Failed to fetch`, a named module, a stack through the icon load, one of several
    `net::` codes. A reading written over
    those words needs a new member every time a fetch moves, and it ends up describing
    the noise this test makes.

    The test controls the span rather than the wording, so it reads the span. Complaints
    inside a block belong to the restart by construction and are dropped; outside every
    block the browser fixture still rejects any problem. Assert any diagnostic the test
    means to produce before leaving the block, because nothing said inside it survives.

    End the block on the assertion that proves the restart landed — the new heading, the
    new layer, the replacement server's answer — since that is what puts the interrupted
    fetches behind the discard. Current coordinator readiness waited for here is a settle
    rather than that proof: a page that never reloaded may still become ready again.
    """
    mark = len(page.lf_errors)
    yield
    wait_until_ready(page)
    del page.lf_errors[mark:]


def names(finding, *words):
    """Whether a render-gate finding names an element whose name holds one of
    `words`: the element it is about, or another it names in its values, such as the
    box that clips it. A probe's record (a dict) answers the same way."""
    if isinstance(finding, dict):
        at, values = finding.get("at", ""), finding
    else:
        at, values = finding.at, finding.values
    named = [at, *(value for value in values.values() if isinstance(value, str))]
    return any(word in name for name in named for word in words)


def take_browser_errors(page):
    """Return and consume problems a test intentionally caused on one page, as the
    fixture's records (`watched`)."""
    errors = page.lf_errors[:]
    page.lf_errors.clear()
    return errors


def http_error_console(status):
    """Chrome's diagnostic prefix for an HTTP error a test arranges.

    This names expected console text; response facts come from the response itself.
    """
    return f"Failed to load resource: the server responded with a status of {status}"


def said(problem):
    """The first line of what the page itself said in a browser problem: a console
    entry, an uncaught exception, or a window error. None for a health sensor's
    structured finding."""
    text = problem.values.get("text")
    return None if text is None else text.splitlines()[0]


_ABSENT = object()


def place_step_matches(actual, expected):
    """Match a watch's tag/id step and the classes an assertion names.

    Classes describe the node at observation time, not a complete identity: focus,
    rendering and other state can add classes. Keep the tag/id and every requested
    class, without depending on additional classes or their order. These are the
    watch's unescaped diagnostic steps, not arbitrary CSS selectors.
    """
    actual_name, *actual_classes = actual.split(".")
    expected_name, *expected_classes = expected.split(".")
    return actual_name == expected_name and set(expected_classes) <= set(actual_classes)


def is_problem(problem, expected):
    """Whether a browser problem is the one a test expects.

    A string is a fragment of what the page said (`said`), so stack locations cannot
    authorize a problem. A dict names the record as a probe returns one,
    `{code, at, ...values}`: its `code`, and each field the test cares about, match
    what was found, such as `{"code": "console-error", "url": "http://page/api/event"}`.
    Watch paths (`node`, `field`, `place`) keep every step and match the tag/id and
    requested classes via `place_step_matches`. Other fields compare by equality.
    A function of the record answers for itself, for another kind of reading."""
    if callable(expected):
        return expected(problem)
    if isinstance(expected, str):
        return (line := said(problem)) is not None and expected in line
    fields = dict(expected)
    if problem.code != fields.pop("code"):
        return False
    for name, value in fields.items():
        actual = problem.at if name == "at" else problem.values.get(name, _ABSENT)
        if name in {"node", "field", "place"} and isinstance(value, list):
            if not isinstance(actual, list) or len(actual) != len(value):
                return False
            if not all(
                place_step_matches(a, e) for a, e in zip(actual, value, strict=True)
            ):
                return False
        elif actual != value:
            return False
    return True


def shown(problems):
    """Browser problems in their words, for a failing assertion's message."""
    return "\n".join(map(str, problems))


def reported_browser_errors(page, *expected):
    """Wait for the complete report a fault draws, then consume it: one problem for
    each of `expected` (`is_problem`), in order.

    One exception is reported once, but one injected fault can raise several, and the
    later reports can be separated from the first by whatever the page does on the way.
    A list read at the moment the first word lands may be a report still arriving, so
    an equality assertion over it turns that gap into a race. This waits for the
    inventory the caller names before taking it, and a problem past that inventory
    still reaches the browser fixture's own reading.

    The wait is a Playwright call rather than a sleep, because the sync driver hands
    console messages to this process only while it is inside one."""
    assert expected, "expected browser problems cannot be empty"

    def complete(errors):
        return len(errors) == len(expected) and all(map(is_problem, errors, expected))

    deadline = time.monotonic() + render_checks_model.SERVED_TIMEOUT_MS / 1000
    while not complete(page.lf_errors) and time.monotonic() < deadline:
        page.wait_for_timeout(25)
    errors = take_browser_errors(page)
    assert complete(errors), shown(errors)
    return errors


def consume_browser_errors(page, *expected):
    """Consume the problems a test caused on one page, each of which must be one of
    `expected` (`is_problem`)."""
    assert expected, "expected browser problems cannot be empty"
    errors = take_browser_errors(page)
    assert errors and all(
        any(is_problem(error, wanted) for wanted in expected) for error in errors
    ), shown(errors)
    return errors


def navigate(page, url, *, wait_until="load", upgraded=True):
    """Navigate through a complete page handover, classifying the ResizeObserver
    notices raised during that navigation (`confirming_resize_notices`)."""

    def complete_navigation():
        page.goto(
            url,
            wait_until=wait_until,
            timeout=render_checks_model.HANDOVER_DEADLINE_MS,
        )
        if upgraded:
            wait_until_ready(page)
        else:
            page.wait_for_function(
                "() => document.querySelector('.lf-floating-panel') !== null",
                timeout=render_checks_model.HANDOVER_DEADLINE_MS,
            )
        # Let the rendering turn that earned the readiness stamp finish. A loop
        # notice is delivered by that turn, rather than by the DOM write alone.
        one_frame(page)

    confirming_resize_notices(page, complete_navigation)


def confirming_resize_notices(page, attempt, again=None):
    """Run `attempt`, classifying only the ResizeObserver notices it raises.

    A platform notice seen once under load is not a page fault; one that the
    confirming attempt, `again` or else `attempt` itself, repeats is, reported with the
    `confirmation` value `recurred`, as the render gate reports one. Everything else
    remains on the page from the attempt that reported it, and anything arriving after
    this helper returns remains strict.
    """
    errors = page.lf_errors

    def noticed(act):
        # A test that adjudicates the page's notices itself keeps its own list.
        outside = getattr(page, "lf_resize_notices", None)
        notices = page.lf_resize_notices = []
        try:
            act()
        except BaseException:
            errors.extend(notices)
            raise
        finally:
            page.lf_resize_notices = outside
        return notices

    notices = noticed(attempt)
    if not notices:
        return
    try:
        confirming_notices = noticed(again or attempt)
    except Exception:
        errors.extend(notice for notice in notices if notice not in errors)
        raise
    if confirming_notices:
        errors.append(confirming_notices[0].but(values={"confirmation": "recurred"}))


def active_digit_bindings(page):
    """Read reachable digits without inventing a page-owned aggregate obligation command.

    Widgets assign their contextual aliases. The dispatcher is the canonical reader of
    which declared keys can execute where focus stands, including native shadowing.
    """
    digits = sorted(
        {
            key
            for keys in available_commands(page).values()
            for key in keys
            if key in "123456789" and len(key) == 1
        }
    )
    if len(digits) > 1 and digits == [
        str(n) for n in range(int(digits[0]), int(digits[-1]) + 1)
    ]:
        return f"{digits[0]}–{digits[-1]}"
    return " ".join(digits)


def open_versions(page):
    """Open the Versions destination through its complete keyboard route."""
    page.keyboard.press("g")
    page.keyboard.press("Shift+v")


# The floating panel (runtime/floating-panel.js) is Leaf's one chrome: a row of the leaf,
# the field and the On me and Threads marks, with a view opened above it and the leaf's
# menu over the leaf. Its state stands on its host as attributes: `data-open` names the
# open view (threads, thread, queue, leaves), `data-menu` marks the menu open and
# `data-rest="mark"` the panel folded to the leaf.
PANEL = ".lf-floating-panel"


def panel_view(name: str) -> str:
    """The selector of the panel's `name` view (threads, thread, queue, leaves) that
    stands open. A view put away keeps its node, marked `data-leaving`, until its
    exit motion ends, so this never matches one: a selector that did would find two
    views mid-switch, or a view already on its way out."""
    return f'.lf-fp-view[data-view="{name}"]:not([data-leaving])'


# A view of one thread, which names the thread it shows by id in `data-thread`.
PANEL_THREAD = panel_view("thread")


def panel_field(page):
    """The editor standing in the panel's field now: the page comment's (`name` is
    `comment`) or, while a thread's view is open, that thread's reply (`reply`)."""
    return page.locator(".lf-fp-field leaf-text")


def panel_settled(page, open=True, view=None):
    """Wait for the floating panel to stand with a view open, or with none, its motion
    finished.

    `view` names the view that has to stand open (`threads`, `thread`, `queue`,
    `leaves`). The panel stands over the page, so opening or closing a view moves
    nothing else; its own clip and fade are the one motion, finished rather than waited
    out, for the reason `scroll_settled` gives a scroll: a test holding the clock still
    would otherwise wait forever. An occluded child gets no animation frames, so a
    native timer polls the same reading there."""
    page.wait_for_function(
        """([open, view]) => {
          const host = document.querySelector('.lf-floating-panel');
          const ground = document.querySelector('.lf-fp-ground');
          // A working indicator may keep animating while the panel has settled.
          const finite = (n) => n.getAnimations({subtree: true}).filter((move) =>
            Number.isFinite(move.effect?.getComputedTiming().endTime));
          const moving = [host, ground].flatMap(finite);
          for (const move of moving) move.finish();
          const shown = host.dataset.open ?? null;
          return (open ? shown !== null && (!view || shown === view) : shown === null)
            && !host.querySelector('.lf-fp-view[data-leaving]')
            && [host, ground].every((n) => !finite(n).length);
        }""",
        arg=[open, view],
        polling=render_checks_model.PROBE_POLL_MS,
    )


def press_visible(page, control, *, touch=False):
    """Press a control already in view without Playwright moving the page for it.

    Locator click/tap on Chromium 156 can scroll the document while preparing a
    visible fixed control. Coordinates exercise the user's visible route directly.
    A frame's bounding box is already in its owning page's coordinates; input
    goes through that page while the control stays scoped to its document.
    """
    expect(control).to_be_in_viewport()
    box = control.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page = page.page if isinstance(page, Frame) else page
    if touch:
        page.touchscreen.tap(x, y)
    else:
        page.mouse.click(x, y)


def open_threads(page):
    """Open the panel's Threads view by pointer, as a user reaches it
    (`leaf_dev.browser.open_threads`), and wait for its motion to end."""
    dev_browser.open_threads(page)
    panel_settled(page, view="threads")


def show_resolved(page):
    """Open Threads and unfold its resolved threads (`leaf_dev.browser.show_resolved`),
    returning their rows once the view's motion ends."""
    open_threads(page)
    rows = dev_browser.show_resolved(page)
    panel_settled(page, view="threads")
    return rows


# How many open threads the page's reading holds, the number the Threads tab says
# (thread/model.js, `threadCounts`): those not resolved, a bare reaction being no
# thread; null until the saved inventory has arrived. It leaves the reading as
# `window.__lfOpenThreads` for a wait to poll.
OPEN_THREAD_COUNT = """async () => {
  const { readThreads } = await window.__lfWidgetApi();
  const { threadCounts } = await window.__lfCheckApi();
  window.__lfOpenThreads = () => {
    const reading = readThreads();
    return reading.phase === "ready" ? threadCounts(reading.threads).open : null;
  };
  return window.__lfOpenThreads();
}"""


def expect_open_threads(page, count):
    """Wait until the page's reading holds `count` open threads (`OPEN_THREAD_COUNT`).

    The count stands on the Threads tab, behind a press on the On me mark, so this
    reads it without one, leaving focus, the open view and any card as they are; where
    the tab itself is the subject, read `threads_tab`'s `.lf-fp-count`."""
    page.evaluate(OPEN_THREAD_COUNT)
    try:
        page.wait_for_function(
            "(want) => window.__lfOpenThreads() === want",
            arg=count,
            polling=render_checks_model.PROBE_POLL_MS,
        )
    except PlaywrightTimeout as error:
        held = page.evaluate("() => window.__lfOpenThreads()")
        raise AssertionError(f"open threads read {held}, not {count}") from error


def expect_on_me(page, count):
    """Wait until the panel counts `count` items waiting on the user. The folded leaf's
    badge carries the count the On me mark does, whatever view stands open, where the
    mark gives its seat to the view's ✕, and whatever news its name goes on to say."""
    expect(page.locator(".lf-fp-badge")).to_have_text(str(count) if count else "")


def panel_menu(page, at=None):
    """Open the leaf's menu and return it, open at its root or at the list `at`
    names: a group (`navigate`, `annotate`, `about`) or `versions`.

    The menu holds the rows it opened with while it stands (floating-panel.js,
    `holdMenu`), a row news took away staying disabled and one news offered waiting for
    the next opening, so a reading of it is a reading of the moment it opened. A row's
    `data-row` is its key among the page's control rows (page-controls.js)."""
    host = page.locator(PANEL)
    leaf = page.locator(".lf-fp-leaf")
    menu = page.locator(".lf-fp-menu")
    if host.get_attribute("data-rest") == "mark":
        press_visible(page, leaf)
        expect(host).to_have_attribute("data-rest", "row")
    if host.get_attribute("data-menu") is None:
        press_visible(page, leaf)
        expect(host).to_have_attribute("data-menu", "")
    if menu.get_attribute("data-level") is not None:
        press_visible(page, menu.locator(".lf-fp-menu-back"))
        expect(menu).not_to_have_attribute("data-level", re.compile("."))
    if at is not None:
        door = "versions" if at == "versions" else f"group:{at}"
        press_visible(page, menu.locator(f'.lf-fp-item[data-row="{door}"]'))
        expect(menu).to_have_attribute(
            "data-level", "versions" if at == "versions" else "group"
        )
    return menu


def panel_control(page, key, at=None):
    """Return the panel's control for the page's control row `key`, opening the leaf's
    menu, and the list `at` names (`panel_menu`), where the row stands there.

    On me (`queue`) is the row's mark, standing while no view or stance does, and
    Threads (`threads`) the tab at the foot of On, which the mark opens to reach it
    (`leaf_dev.browser.threads_tab`). Every other row is the menu's, by its key:
    `versions`, `leaves` (All pages, under `navigate` where other pages are live),
    `latest`, `blanket:accept`, `command:<id>` for a page command such as
    `command:history.undo` or `command:draw.mode.enter` (under `annotate`). The way out
    of the current panel view is the `.lf-fp-exit` ✕ named by its `aria-label`,
    and the page comment is `page_comment`'s, offering selected words as
    `selection_field`'s."""
    if key == "queue":
        control = page.locator(ON_ME_MARK)
    elif key == "threads":
        control = threads_tab(page)
    else:
        control = panel_menu(page, at).locator(f'.lf-fp-item[data-row="{key}"]')
    expect(control).to_be_visible()
    return control


def expect_panel_offers(page, key, *, offered=True, at=None):
    """Read whether the leaf's menu offers the row `key`, enabled, in the list `at`
    names, then put the menu away.

    The menu holds what it opened with (`panel_menu`), so this reads one opening: wait
    first for the page state the row follows. The leaf keeps the focus its press gave
    it."""
    row = panel_menu(page, at).locator(f'.lf-fp-item[data-row="{key}"]:not(:disabled)')
    expect(row).to_have_count(1 if offered else 0)
    page.locator(".lf-fp-leaf").click()
    expect(page.locator(PANEL)).not_to_have_attribute("data-menu", "")


def selection_field(page):
    """Return the page comment's box in the panel's field while it offers the words
    selected on the page: its placeholder quotes them, and a press on it comments on
    them (floating-panel.js, `selectedWords`). Nothing matches while no words are
    offered, so the locator reads as hidden then."""
    return page.locator('.lf-fp-field leaf-text[name="comment"][data-says="selection"]')


def page_comment(page):
    """Return the page comment's box in the panel's field, focused.

    The field writes a page comment while no view stands open over it
    (floating-panel.js, `pageEditor`); a send opens the new thread's view there, the
    field becoming its reply, so this puts an open view away first, and unfolds a panel
    folded to the leaf."""
    host = page.locator(PANEL)
    if host.get_attribute("data-rest") == "mark":
        page.locator(".lf-fp-leaf").click()
        expect(host).to_have_attribute("data-rest", "row")
    if host.get_attribute("data-open") is not None:
        page.locator(".lf-fp-close").click()
        panel_settled(page, open=False)
    box = page.locator('.lf-fp-field leaf-text[name="comment"]')
    box.click()
    expect(box).to_be_focused()
    return box


# The words in the panel's one seat for what passes, such as a notice or a walk's
# position (floating-panel.js, `passing`): the leaf's peek while it shows one over an
# open view, else the line over the field while it stands, else an error standing
# over the field's words (composing/input.js), else the empty field's placeholder.
PANEL_SAYS = """() => {
  const peek = document.querySelector('.lf-fp-peek');
  if (peek?.hasAttribute('data-shown')) return peek.textContent.trim();
  const line = document.querySelector('.lf-fp-context');
  if (line && !line.hidden && line.textContent.trim()) return line.textContent.trim();
  const cover = document.querySelector('.lf-fp-field .lf-compose-error:not([hidden])');
  if (cover) return cover.textContent.trim();
  return document.querySelector('.lf-fp-field leaf-text')?.getAttribute('placeholder')
    ?? '';
}"""


def panel_says(page) -> str:
    """What the panel's seat for passing words says now (`PANEL_SAYS`)."""
    return page.evaluate(PANEL_SAYS)


def expect_panel_says(page, words, *, says=True):
    """Wait until the panel's seat for passing words says `words`, among others, or,
    with `says` false, until it no longer does."""
    try:
        page.wait_for_function(
            f"([words, says]) => ({PANEL_SAYS})().includes(words) === says",
            arg=[words, says],
        )
    except PlaywrightTimeout:
        said = page.locator(".lf-live").text_content()
        raise AssertionError(
            f"the panel says {panel_says(page)!r}, "
            f"{'not' if says else 'still'} {words!r} "
            f"(the live region last said {said!r})"
        ) from None


def expect_error_waits_in_menu(page, message):
    """Expect the newest error to say exactly `message` from the leaf's menu, under
    Errors, with the leaf's dot marking it unseen; the menu is put away again.

    That is where an error waits that the panel's field cannot say (errors.js): one
    about a box outside the panel, such as a passage's composer, or about nothing while
    the field holds words."""
    expect(page.locator(".lf-fp-error-dot")).to_be_visible()
    menu = panel_menu(page)
    menu.locator('.lf-fp-item[data-row="errors"]').click()
    expect(menu.locator(".lf-fp-error-words b").first).to_have_text(message)
    page.locator(".lf-fp-leaf").click()
    expect(page.locator(PANEL)).not_to_have_attribute("data-menu", "")


# How many of the page's active obligations are answered, as "answered/total": the publisher's
# own obligation reading, which the On panel's Done list and the `m` walk select from. Before
# the page has admitted a state answer the reading is empty, which is no count at all.
_OBLIGATIONS_ANSWERED = """async () => {
  const { readApplication } = await window.__lfCheckApi();
  window.__lfObligationsAnswered = () => {
    const application = readApplication();
    if (application.phase !== 'ready') return null;
    const items = application.effective.obligations;
    const all = items.all.filter(item => item.source.kind === "widget");
    const unanswered = items.unanswered.filter(item => item.source.kind === "widget");
    return `${all.length - unanswered.length}/${all.length}`;
  };
}"""


def expect_obligations_answered(page, answered: str) -> None:
    """Wait until the page's obligation reading holds `answered` ("answered/total").

    The deadline bounds a hang; on expiry the failure names the reading the page held.
    """
    page.evaluate(_OBLIGATIONS_ANSWERED)
    try:
        page.wait_for_function(
            "(want) => window.__lfObligationsAnswered() === want",
            arg=answered,
            timeout=render_checks_model.SERVED_TIMEOUT_MS,
        )
    except PlaywrightTimeout as error:
        held = page.evaluate("() => window.__lfObligationsAnswered()")
        raise AssertionError(
            f"answered obligations read {held}, not {answered}"
        ) from error


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
    """A page at a URL, with its document and log state applied before it is handed over.

    The readings — the problem list, the traffic ledger, the interception arm — come
    from the browser this asks for the page, so they are installed whether a test calls
    this or opens a page itself (`readable`, `WatchedBrowser`).

    `pin` asks for the version the URL names rather than the newest, and is a keyword
    because the URL a handover carries already has a query holding the page's key: a
    test appending its own `?pin` overwrote that key and got a page that never loaded.

    `upgraded` waits until the page states it is ready (`wait_until_ready`, whose
    stages are the runtime's `pageReadiness`).

    Navigation waits for `load`, so the stylesheet and media that determine layout have
    arrived. Network silence is not a readiness fact; the page's own readiness reading
    states that the document and its log finished applying and that their current
    presentation work has settled.

    `color_scheme` sets the medium before page modules evaluate. A supplied context owns
    its own medium instead, just as it owns the rest of its browser state.

    False is for the one test whose subject is the interval between them, which holds the
    registry fetch open and so never earns either. It waits on the panel instead, which
    says only that the runtime's module evaluated — long before the anchor pass has run,
    and so before the Comment button can answer a selection at all. A test that reads
    there without an auto-retrying wait is racing the upgrade and loses on a loaded
    machine: the passage sweep lost it on the corpus, the heaviest page here, and what
    it reported was a passage it had not tested rather than one that failed."""
    page = (
        context.new_page()
        if context
        else browser.new_page(
            viewport={"width": 1200, "height": 900}, color_scheme=color_scheme
        )
    )
    if init_script:
        page.add_init_script(init_script)
    if pin:
        url += ("&" if "?" in url else "?") + "pin"
    navigate(
        page,
        url,
        wait_until=wait_until,
        upgraded=upgraded,
    )
    return page


def opened_tab(page, destination, press):
    """Press once and return a controlled tab after Chromium opens `destination`.

    Playwright can permanently lose the Page for a target Chromium opened. The browser's
    CDP target list is the durable record of the platform action, so the helper waits there
    for one new page at the expected URL. It closes that target and navigates a controlled
    page in the same context for the arrival assertions. This keeps the product action
    observable without repeating a user gesture or leaking the target.

    `page` must belong to an explicitly created context such as `one_user`. Playwright
    refuses `context.new_page()` on the owner context created by `browser.new_page()`,
    which is what `open_page` uses when no context is passed.

    A handover link's target may already stand at the address the runtime leaves once
    it takes the key out of the address bar, so either spelling is the arrival.
    """
    parts = urlsplit(destination)
    query = parse_qsl(parts.query, keep_blank_values=True)
    keyless = parts._replace(
        query=urlencode([p for p in query if p[0] != "t"])
    ).geturl()
    browser_session = page.context.browser.new_browser_cdp_session()

    def page_targets():
        return {
            target["targetId"]: target["url"]
            for target in browser_session.send("Target.getTargets")["targetInfos"]
            if target["type"] == "page"
        }

    before = set(page_targets())
    opened = {}
    deadline = time.monotonic() + render_checks_model.SERVED_TIMEOUT_MS / 1000
    try:
        try:
            press()
        except PlaywrightTimeout as refused:
            raise AssertionError(
                "the press timed out before any tab could open: the subject refused "
                "the gesture"
            ) from refused

        while True:
            opened = {
                target_id: url
                for target_id, url in page_targets().items()
                if target_id not in before
            }
            if len(opened) > 1:
                raise AssertionError(
                    f"one press opened {len(opened)} page targets: "
                    f"{sorted(opened.values())}"
                )
            if len(opened) == 1 and set(opened.values()) <= {destination, keyless}:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(
                    f"Chromium did not open {destination!r} after one press; "
                    f"new page targets: {sorted(opened.values())}"
                )
            page.wait_for_timeout(min(20, remaining * 1000))

    finally:
        try:
            opened = {
                target_id: url
                for target_id, url in page_targets().items()
                if target_id not in before
            }
            for target_id in opened:
                closed = browser_session.send(
                    "Target.closeTarget", {"targetId": target_id}
                )
                assert closed["success"], (
                    f"Chromium did not close page target {target_id}"
                )
            if opened:
                close_deadline = (
                    time.monotonic() + render_checks_model.SERVED_TIMEOUT_MS / 1000
                )
                while set(opened) & set(page_targets()):
                    if time.monotonic() >= close_deadline:
                        raise AssertionError(
                            f"Chromium kept page targets after close: {sorted(opened)}"
                        )
                    page.wait_for_timeout(20)
        finally:
            browser_session.detach()

    # `page.context` is Playwright's own context, not the `WatchedContext` the fixture
    # handed over, so the tab this makes is readable only because it is made readable
    # here — and before the navigation, which is the only side of it an init script
    # reaches.
    tab = readable(
        page.context.new_page(), java_script_enabled=page.lf_java_script_enabled
    )
    tab.goto(destination)
    return tab


# Chromium arms request interception the first time a page is routed at all, and
# Playwright's acknowledgement of that registration outruns the arming: a request
# the page issues in the milliseconds after `page.route` returns reaches the server
# unintercepted, and Playwright reports no request for it either. A test holding a
# gesture's POST then watches the send land and the answer settle the draft while
# its own counters read nothing — the trip it is waiting for never happened on this
# side. It is the escape `held_events` was written around, and why that fixture
# routes from navigation onward.
#
# Interception is not free, though. While any route is set, Playwright pauses every
# request the page makes until its driver lets it go, and turns Chromium's HTTP cache
# off (`Fetch.enable` on `*` and `Network.setCacheDisabled`). Measured on a plain test
# page in October 2026, the arm added about 30 ms of CPU to each opening's 550, in the
# browser process and the driver. Most pages are never routed.
#
# So a page the suite makes arms itself when something first routes it or its
# context, on a pattern nothing else asks for, ahead of that first route. Before the
# page navigates, nothing is in flight to escape and the arm is in place before the
# first request, as `held_events` needs. After, the arm proves itself before the
# test's route is added: the page fetches a probe the arm answers, and a probe the
# arm missed escaped to the page server's quiet `favicon.ico` and is sent again. A
# route registered later then only adds a pattern to a list the browser is already
# consulting. The arm stays for the page's life, since interception comes back down
# when a route list empties and requests crossing that transition are lost just as
# silently; `unroute_all` takes it too, so the next route arms again.
ARM_PROBE = re.compile(r"/favicon\.ico\?lf-interception-armed=\d+$")
_route_page = Page.route
_route_context = BrowserContext.route
_unroute_all_page = Page.unroute_all


def _arm(page):
    """Turn interception on for a page the suite made, before its first route."""
    if getattr(page, "lf_armed", True):
        return
    page.lf_armed = True
    caught = set()

    def arm(route):
        caught.add(route.request.url)
        route.fulfill(status=204)

    _route_page(page, ARM_PROBE, arm)
    # A page that has not navigated has nothing in flight, and a document that is no
    # page server's has no quiet address to probe.
    if not page.url.startswith(("http://", "https://")):
        return
    deadline = time.monotonic() + render_checks_model.SERVED_TIMEOUT_MS / 1000
    for attempt in itertools.count():
        probe = page.evaluate(
            """attempt => {
              const probe = new URL(`/favicon.ico?lf-interception-armed=${attempt}`,
                location.href).href;
              return fetch(probe, { cache: "no-store" }).then(() => probe, () => probe);
            }""",
            attempt,
        )
        if probe in caught:
            return
        assert time.monotonic() < deadline, (
            f"request interception never caught a probe on {page.url}"
        )


def _arming_page(self, url, handler, **kwargs):
    __tracebackhide__ = True
    _arm(self)
    return _route_page(self, url, handler, **kwargs)


def _arming_context(self, url, handler, **kwargs):
    __tracebackhide__ = True
    # A page this context makes from here on starts with the context's route set, so
    # it arms as it is made (`readable`).
    self.lf_routed = True
    for page in self.pages:
        _arm(page)
    return _route_context(self, url, handler, **kwargs)


def _disarming(self, *args, **kwargs):
    __tracebackhide__ = True
    result = _unroute_all_page(self, *args, **kwargs)
    if hasattr(self, "lf_armed"):
        self.lf_armed = False
    return result


Page.route = _arming_page
BrowserContext.route = _arming_context
Page.unroute_all = _disarming

# A browser wait bounds a hang; it does not time the work it waits for (tests/AGENTS.md,
# "Functional results do not depend on execution speed"). One that names no deadline
# takes `SERVED_TIMEOUT_MS`, the bound on one probe or request: an `expect` assertion,
# whose own default is five seconds, and every page action, wait and expectation on a
# page `readable` prepares. A wait that spans a page handover names
# `HANDOVER_DEADLINE_MS`.
expect.set_options(timeout=render_checks_model.SERVED_TIMEOUT_MS)


def readable(page, *, java_script_enabled=True):
    """Install what the suite reads off a page, before the page navigates.

    The three readings are the same for every scripted page: the delivery ledger the traffic
    helpers consume, the arm that keeps a later route real (installed with the page's
    first route, `_arm`), and the problem list the
    browser fixture rejects at the end of the test. None of them can be installed
    afterwards — an init script has to precede the navigation it instruments, and a
    console entry from a page nobody was listening to is simply gone — so a page that
    reaches a test without them is a page whose errors that test does not check and
    whose routes it cannot rely on.

    They are therefore installed where a page is made rather than asked for by each
    test, which is what `WatchedBrowser` is for. A page that already carries them is
    left alone, since a second console listener would report every problem twice.
    A scripts-disabled context keeps the native error collector and shared deadlines;
    the script-driven readings are unavailable there.

    A run given `--cpu-throttle RATE` also slows each Chromium page here, before it
    navigates (`tests/AGENTS.md`, "Races").
    """
    if getattr(page, "lf_errors", None) is not None:
        return page
    if _CPU_THROTTLE and page.context.browser.browser_type.name == "chromium":
        slow_cpu(page, _CPU_THROTTLE)
    page.set_default_timeout(render_checks_model.SERVED_TIMEOUT_MS)
    page.lf_armed = False
    if getattr(page.context, "lf_routed", False):
        _arm(page)
    if java_script_enabled:
        page.lf_traffic = Traffic(page)
    watched(page, java_script_enabled=java_script_enabled)
    return page


class WatchedContext:
    """A context whose every page arrives readable.

    Every page here is one this asks for. A page the browser opens by itself — a
    popup, a `target=_blank` — arrives on the context's `page` event instead, and
    that is not a place these readings can be installed from: measured, a
    `page.route` inside that handler leaves the `add_init_script` after it without
    effect and says nothing, which is a page whose listeners are installed and whose
    init scripts are missing. `opened_tab` is how the suite meets a tab Chromium
    opened.
    """

    def __init__(self, context, *, java_script_enabled=True):
        self._context = context
        self._java_script_enabled = java_script_enabled

    def new_page(self, **kwargs):
        return readable(
            self._context.new_page(**kwargs),
            java_script_enabled=self._java_script_enabled,
        )

    def __getattr__(self, name):
        return getattr(self._context, name)

    def __enter__(self):
        self._context.__enter__()
        return self

    def __exit__(self, *exception):
        return self._context.__exit__(*exception)


class WatchedBrowser:
    """Wrap a browser so every test page is instrumented before navigation.

    `readable` installs the error collector, interception arm, and traffic reading.
    `unwatched` exposes the underlying browser for product gates that deliberately
    open faulty pages and report those faults themselves. Ordinary clean-page
    journeys use the wrapped browser. Fixture policy lives in `tests/AGENTS.md`,
    "Browser errors"."""

    def __init__(self, browser):
        self._browser = browser
        self.unwatched = browser

    def new_context(self, **kwargs):
        return WatchedContext(
            self._browser.new_context(**kwargs),
            java_script_enabled=kwargs.get("java_script_enabled", True),
        )

    def new_page(self, **kwargs):
        return readable(
            self._browser.new_page(**kwargs),
            java_script_enabled=kwargs.get("java_script_enabled", True),
        )

    def __getattr__(self, name):
        return getattr(self._browser, name)


def primed(browser, prepare):
    """Prepare each page before a product render call navigates it.

    The wrapper preserves the supplied browser's instrumentation and real version;
    contexts have no version and are used only by callers that do not need one.
    `prepare` installs external controls such as routes. Use `browser.unwatched`
    when the product call itself must report an intentionally faulty page."""

    def new_page(**kwargs):
        page = browser.new_page(**kwargs)
        prepare(page)
        return page

    return SimpleNamespace(new_page=new_page, version=getattr(browser, "version", ""))


@pytest.fixture
def held_events(browser):
    """Hold event requests from navigation onward, including the first POST.

    Interception installed after navigation can miss that first request. Tests
    release routes needed by their journey; context closure cancels any left held.
    Teardown does not resume them into a possibly stopped server."""
    held = []

    def prepare(page):
        page.route("**/api/event", lambda route: held.append(route))

    return primed(browser, prepare), held


@pytest.fixture
def one_user(browser):
    """A browser context two pages can share, which is what makes them tabs.

    `Browser.new_page` opens each page in a context of its own, so two of them are two
    users with no storage between them — and a draft lives in the user's store now,
    which is the whole of what these tests are about."""
    return browser.new_context(
        viewport={"width": 1200, "height": 900}, color_scheme="light"
    )


@pytest.fixture
def live_leaf(tmp_path, monkeypatch):
    """Stands up a live leaf for All pages to find: published, served by
    a real handler, and written down under the state home the way `server run` writes
    it — which is the whole of how one page learns another exists. Each claims to be
    working, freshly, so its row has a judged state to show. A factory rather than one
    fixture, because All pages is a list and a walk down it needs somewhere to walk to."""
    monkeypatch.chdir(tmp_path)  # keep the project layer out of the overlay
    served = []
    waiters = []

    def go(name, title):
        d = cleanup_model.state_home() / "pages" / name
        result = CliRunner().invoke(cli_model.cli, ["page", "init", str(d)])
        assert result.exit_code == 0, result.output
        stamp_page(
            d,
            LONG_PAGE.replace("<title>long</title>", f"<title>{title}</title>"),
            "t",
        )
        declare_work(d, "running the suite")
        # A live leaf has a session behind it, and what All pages says on hover about a
        # page is the work that session is doing it for — so the fixture's pages come
        # out of somewhere nameable rather than out of nowhere.
        record_claim(
            d,
            id=f"s-{name}",
            cwd=str(tmp_path / f"{name}-work"),
        )
        lease_path = leases_model.waiter_lease_path(d, f"s-{name}")
        assert lease_path is not None
        waiters.append(leases_model.take_wait_lease(lease_path))
        # Use the durable server's maintenance loop: the row remains canonical
        # even while no browser has visited this neighboring page.
        url = hosting_model.start_server(d, persistent=True, harness=None).url
        served.append(d)
        # The address is announced before the row producer starts. All pages can
        # discover this neighbour only after that producer publishes its first row.
        wait_for(
            lambda: presence_model.live_leaves({d.resolve()}),
            lambda leaves: len(leaves) == 1,
            failure=f"{name} never published its live neighbour row",
        )
        return url.split("?")[0].rstrip("/"), d

    yield go
    for directory in served:
        hosting_model.cmd_stop(directory)
    for waiter in waiters:
        leases_model.release_lease(waiter)


@pytest.fixture
def other_leaf(live_leaf):
    return live_leaf("other", "The other leaf")


def margins_laid_out(page):
    """Announce a layout change and wait for the margin's own placement delivery.

    The public widget invalidation runs the normal observer/scheduler path. Its
    native completion event proves placement occurred; no private solver is invoked.
    """
    page.evaluate(
        """async () => {
          const {layoutChanged} = await window.__lfWidgetApi();
          window.__lfMarginLaidOut = false;
          document.addEventListener('lf-margin-layout', () => {
            window.__lfMarginLaidOut = true;
          }, {once: true});
          layoutChanged(document.body);
        }"""
    )
    page.wait_for_function(
        "() => window.__lfMarginLaidOut",
        timeout=render_checks_model.SERVED_TIMEOUT_MS,
    )


def margin_entry(owner: str, key: str | None = None) -> str:
    """The selector for the margin entries a contribution registered under `owner`,
    narrowed to its entry `key` when one is given. A page script that must find the
    control itself takes this; a test otherwise takes `margin_control`."""
    selector = f'[data-lf-margin-entry-owner="{owner}"]'
    return selector if key is None else f'{selector}[data-lf-margin-entry-key="{key}"]'


def margin_control(scope, owner: str, key: str | None = None, *, visible=True):
    """A margin entry within `scope` (a page, frame, or locator) by its contribution's
    owner key and its own entry key; only the visible one unless `visible` is False."""
    return scope.locator(margin_entry(owner, key) + (":visible" if visible else ""))


# A content widget's contribution key is its module's own choice, and this is the
# suite's one spelling of `lf-suggestion`'s: `suggestion:<id>`.
def suggestion_owner(suggestion_id: str) -> str:
    return f"suggestion:{suggestion_id}"


def draft_control(scope, key: str, draft_id: str, *, visible=True):
    """A draft's local command button (edit, save, cancel or retry)."""
    action = "save" if key == "retry" else key
    return scope.locator(
        f'lf-draft[id="{draft_id}"] [data-lf-draft-action="{action}"]'
        + (":visible" if visible else "")
    )


def suggestion_control(scope, suggestion_id: str, key=None, *, visible=True):
    """The suggestion `suggestion_id`'s margin entry `key` (accept, reject, undo), or
    all of its entries."""
    return margin_control(scope, suggestion_owner(suggestion_id), key, visible=visible)


def any_owner_entry(kind: str, key: str | None = None) -> str:
    """The selector for a margin entry any `kind` widget (such as `suggestion`)
    registered, for a probe that plants one example on a page rather than tracking a
    particular id. `margin_entry` locates one owner exactly."""
    selector = f'[data-lf-margin-entry-owner^="{kind}:"]'
    return selector if key is None else f'{selector}[data-lf-margin-entry-key="{key}"]'


def any_draft_control(scope, key: str | None = None, *, visible=True):
    """Any draft's local control `key` on the page, for the same reason `any_owner_entry`
    exists rather than `draft_control`."""
    action = "save" if key == "retry" else key
    selector = "lf-draft [data-lf-draft-action]"
    if action is not None:
        selector += f'[data-lf-draft-action="{action}"]'
    return scope.locator(selector + (":visible" if visible else ""))


def any_suggestion_control(scope, key: str | None = None, *, visible=True):
    """Any suggestion's margin entry `key` on the page, or all of its entries."""
    return scope.locator(
        any_owner_entry("suggestion", key) + (":visible" if visible else "")
    )


def command_reference_rows(page, heading):
    """The rows of the command reference section titled `heading`."""
    heading_id = page.get_by_role("heading", name=heading, exact=True).get_attribute(
        "id"
    )
    return page.locator(f'[role=rowgroup][aria-labelledby="{heading_id}"]')


# The page shell's box on screen: where the document's room starts and ends. The runtime
# reads the same edge as `shellRight` (geometry.js). This is the suite's one spelling of it, read off the DOM
# rather than through that function, so a test comparing it with a region's box compares
# two independent readings. An expression, so a larger evaluate can embed it and take it in
# the same pass as what it is compared against.
SHELL_BOX = """(() => {
  const b = document.body;
  const left = b.getBoundingClientRect().left;
  return { left, right: left + b.clientWidth, width: b.clientWidth,
           centre: left + b.clientWidth / 2 };
})()"""


# Put the user nowhere, with the next Tab starting at the top of the document: the
# runtime's own let-go (focus.js, `releaseFocus`). Body holds no stop of its own, so
# `document.body.focus()` moves nothing on a page whose root does not scroll.
# Each field's closed shadow root, so a test can read inside it.
EDITOR_ROOTS = """
  window.editorRoots = new Map();
  const attach = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function(options) {
    const root = attach.call(this, options);
    if (this.localName === 'leaf-text') window.editorRoots.set(this, root);
    return root;
  };
"""


RELEASE_FOCUS = """async () =>
  (await window.__lfCheckApi()).releaseFocus()"""


def regions_side_by_side(regions: str, columns: str = "1fr 1fr") -> str:
    """The page's own stylesheet setting a workspace body's panes side by side, as a
    page writes it: a grid, which stacks where the workspace flows."""
    return f"""<style>
#{regions} {{ display: grid; grid-template-columns: {columns}; }}
@media (width < 720px) {{ #{regions} {{ grid-template-columns: 1fr; }} }}
</style>"""


def pane_scroll_behavior(page, pane, behavior):
    """Wait until a pane is `bounded` (its body scrolls) or in `flow` (it does not).

    The body is the pane's one element between its optional header and footer. Whether
    it scrolls is the stylesheet's answer to the workspace's size, and the same fact
    `regionScrollBehavior` reads, so this waits on the composed style rather than on any
    attribute a script would have to keep in step with it."""
    page.wait_for_function(
        """([node, behavior]) => {
          const body = [...node.children].find(c => !c.matches('header, footer'));
          const scrolls = /auto|scroll/.test(getComputedStyle(body).overflowY);
          return (scrolls ? 'bounded' : 'flow') === behavior;
        }""",
        arg=[pane.element_handle(), behavior],
    )


def fills_the_window(page, block, fills):
    """Wait until a block does, or does not, fill the window with the page at rest.

    A block that fills it is the whole page: its bottom edge is inside the window and the
    document has nothing to scroll, so the block's own panes carry what overflows. A
    flowing block runs past the window and the page scrolls it.
    """
    page.wait_for_function(
        """([node, fills]) => {
          const bottom = node.getBoundingClientRect().bottom;
          const page = document.scrollingElement;
          return (bottom <= innerHeight + 1
            && page.scrollHeight <= page.clientHeight + 1) === fills;
        }""",
        arg=[block.element_handle(), fills],
    )


# An async page expression for the top of the page scroller's landing band, below the
# chrome covering its top edge: where a reading place is measured from.
LANDING_TOP = "(await window.__lfCheckApi()).landingBand(document.scrollingElement).top"


def resized(page, width, height):
    """Resize and wait for the page's listeners and rendering update.

    `set_viewport_size` alone does not prove that resize listeners ran. The
    counter is installed after the runtime's listeners; `one_frame` then lets
    the document's scrolling area catch up before the caller measures it.
    Wait separately for any resulting motion whose geometry is under test.

    An unchanged viewport returns immediately because it emits no resize event."""
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
    one_frame(page)


@contextmanager
def compositor_trace(page, categories=()):
    """Record the frames Chrome's compositor draws while the block runs.

    Yields the trace's event list, complete once the block exits; its `Screenshot`
    events are the frames the window showed. Reading rectangles after a scroll forces
    layout and conceals a frame painted out of step, so a claim about what a scroll
    paints reads these frames instead. Waiting for the trace pumps CDP delivery
    without reading the page or forcing its layout."""
    cdp = page.context.new_cdp_session(page)
    events, complete = [], []
    cdp.on("Tracing.dataCollected", lambda data: events.extend(data["value"]))
    cdp.on("Tracing.tracingComplete", lambda _: complete.append(True))
    # Only the named categories: Chrome otherwise adds its default ones, whose forced
    # layout events alone, from the suite's own watchers, can outlast the wait.
    cdp.send(
        "Tracing.start",
        {
            "traceConfig": {
                "includedCategories": [
                    "disabled-by-default-devtools.screenshot",
                    *categories,
                ],
                "excludedCategories": ["*"],
            },
            "transferMode": "ReportEvents",
        },
    )
    yield events
    cdp.send("Tracing.end")
    wait_for(
        lambda: (cdp.send("Tracing.getCategories"), bool(complete))[1],
        bool,
        failure="Chrome never completed the compositor screenshot trace",
    )


def rgb_pixel(image: Image.Image, point) -> tuple[int, int, int]:
    """Read one RGB pixel; Pillow's mode-dependent return type cannot express RGB."""
    assert image.mode == "RGB"
    return cast(tuple[int, int, int], image.getpixel(point))


def rgb_pixels(image: Image.Image) -> Iterable[tuple[int, int, int]]:
    """Read an RGB image's pixels with its mode reflected in their channel type."""
    assert image.mode == "RGB"
    return cast(Iterable[tuple[int, int, int]], image.get_flattened_data())


def frame_image(event):
    """A compositor `Screenshot` trace event's frame, as an RGB image."""
    return Image.open(io.BytesIO(base64.b64decode(event["args"]["snapshot"]))).convert(
        "RGB"
    )


# A frame test paints its subject in this red and the surface that must follow it in
# this green, colours nothing else on the page uses.
SUBJECT_MARK = "#ff0044"
FOLLOWER_MARK = "#00cc44"


def marked_tops(image):
    """The topmost rows of `image` painted in `SUBJECT_MARK` and in `FOLLOWER_MARK`,
    each None where the frame shows none. Downsampled frames blend the marks' edges,
    so each matches a range around its colour."""
    pixels = image.load()
    subject, follower = [], []
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue = pixels[x, y]
            if red > 180 and green < 60 and blue < 130:
                subject.append(y)
            if green > 130 and red < 60 and blue < 130:
                follower.append(y)
    return (min(subject, default=None), min(follower, default=None))


def assert_follows_in_every_frame(page, scroller):
    """Wheel `scroller` down and back, under the pointer, and require every frame the
    compositor draws meanwhile to show the follower (`FOLLOWER_MARK`) at one offset from
    its subject (`SUBJECT_MARK`).

    A box the browser carries through the scroll paints in step with it. A scroll-driven
    layer carries the same motion but has painted a frame early or late on Linux under
    load, and reading rectangles after the scroll forces layout and hides that frame,
    so this reads the compositor's own frames."""
    width = page.viewport_size["width"]
    with compositor_trace(page) as events:
        for delta in (40, 40, -40, -40):
            page.mouse.wheel(0, delta)
            scroll_settled(page, scroller)
    readings = []
    for event in events:
        if event["name"] != "Screenshot":
            continue
        image = frame_image(event)
        scale = width / image.width
        subject, follower = marked_tops(image)
        assert subject is not None and follower is not None, readings
        readings.append((subject * scale, follower * scale, scale))
    assert len({subject for subject, _, _ in readings}) >= 3, (
        "the scroller never scrolled",
        readings,
    )
    offset = readings[0][1] - readings[0][0]
    # Chrome downsamples trace frames, so two samples allow the blended edges.
    assert all(
        abs(follower - subject - offset) <= 2 * scale
        for subject, follower, scale in readings
    ), readings


def root_overflow(page) -> float:
    """How far the page scrolls sideways, as the render gate reads it (`rootOverflow`):
    at the root scrollport the runtime scrolls. `body` is not that scroller, and a page
    that narrows it reads as overflowing where the window scrolls nothing."""
    return render_checks_model.evaluate_probe(page, "rootOverflow")


def wide_width(page) -> float:
    """The page's `--wide` in pixels: the theme derives it from the code size, and a
    page may restate it, so a width check reads it rather than copying the number."""
    return page.evaluate(
        "parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--wide'))"
    )


def painted_words(page, selector: str) -> list[dict]:
    """Where the words under `selector` are painted, as the render gate reads them
    (`paintedWords`): one `{left, top, right, bottom, text}` per run, each cut to what
    the boxes holding it show, so a word said only to a screen reader hides nothing."""
    return render_checks_model.evaluate_probe(page, "paintedWords", selector)


def hold_selection(page, start, end, steps=8, frame_the_press=False):
    """Drag a selection without releasing, pressing on a whole pixel.

    `frame_the_press` lets the frame the press itself schedules land before the drag
    begins, which is the ordering a loaded machine gives every drag and an idle one
    gives almost none. Without it a surface repainted inside the press is read as
    following the drag whenever the round trips outrun the frame, and as stale
    whenever they do not — a coin toss written as an assertion. State it wherever the
    read is of something the press repaints, so the drag is the only thing the read
    can be about.

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
    if frame_the_press:
        rendered(page)
    page.mouse.move(end[0], end[1], steps=steps)


def select(page, start, end, steps=8):
    """Drag and release a selection."""
    hold_selection(page, start, end, steps)
    page.mouse.up()


def select_words(page, passage):
    """Triple-click a passage's words, which is not the same point as its box.

    Playwright aims at the element's centre, and a short paragraph in a wide column is
    mostly empty there. The response bar the user already opened on a neighbouring
    passage stands in that empty half — it is placed to keep its own target clear, not
    the page — so a gesture aimed at the centre lands on the field instead of on the
    words and never reaches the passage. The words are where a user aims, so the
    click goes to the start of the first line the passage draws."""
    locator = page.locator(passage)
    locator.scroll_into_view_if_needed()
    x, y = locator.evaluate(
        """element => {
          const range = element.ownerDocument.createRange();
          range.selectNodeContents(element);
          const [line] = range.getClientRects();
          const box = element.getBoundingClientRect();
          if (!line) return [box.width / 2, box.height / 2];
          return [
            line.left + Math.min(24, line.width / 2) - box.left,
            line.top + line.height / 2 - box.top,
          ];
        }"""
    )
    locator.click(click_count=3, position={"x": x, "y": y})


def write(box, text):
    """Replace a text box's words the way typing them would, as `fill` does.

    `fill` refuses the runtime's text field: the node it would type into sits in the
    field's closed shadow root. This puts the user in the box through its own `focus()`,
    selects what it holds, and inserts the words as one input, which the field hears as
    the user's edit and announces with `input`. A native textarea takes it the same way.
    Read the words back with `to_have_js_property("value", ...)`."""
    expect(box).to_be_visible()
    box.focus()
    box.evaluate("box => box.select()")
    if text:
        box.page.keyboard.insert_text(text)
    elif box.evaluate("box => box.value"):
        box.page.keyboard.press("Delete")


def compare_with(page, version=None):
    """Mark what changed since a version, the way the page offers it.

    Versions in the leaf's menu lists each version with its Compare beside the note that
    says in words what it changed. With no version named it is the one before the
    version being read — the first Compare in the list, a row offering one only where it
    is older than this."""
    menu = panel_menu(page, "versions")
    press = (
        menu.locator(".lf-fp-compare").first
        if version is None
        else menu.get_by_role(
            "menuitem", name=re.compile(rf"^Compare with v{version}( |$)")
        )
    )
    press.click()


def scroll_writes(page, steps, scroller="document.scrollingElement"):
    """Scroll `scroller` (a page expression) by each of `steps`, waiting for every
    repaint a step queues, and return each DOM write the scroll caused, numbered by
    step. The pointer is moved off the page's controls first, so the scroll brings
    nothing new under it."""
    page.mouse.move(2, 300)
    rendered(page)
    page.evaluate("() => { window.lfWrites = []; window.lfWriteStep = null; }")
    start = page.evaluate(f"() => {scroller}.scrollTop")
    for index, step in enumerate(steps):
        page.evaluate(
            f"([index, step]) => {{ window.lfWriteStep = index; "
            f"{scroller}.scrollBy(0, step); }}",
            [index, step],
        )
        rendered(page)
    assert page.evaluate(f"() => {scroller}.scrollTop") == start + sum(steps), (
        "the scroll did not go where its steps lead"
    )
    return page.evaluate(
        "() => { const w = window.lfWrites; window.lfWrites = null; return w; }"
    )


# How many frames a gesture takes, whatever the host's frame rate.
GESTURE_FRAMES = 24

_GESTURE = """async ([scroller, by, sample, frames]) => {
  const box = eval(scroller);
  const read = sample ? eval(sample) : () => null;
  const start = box.scrollTop;
  const samples = [];
  let frame = 0;
  const {scrollGlides, watchScrollEnds} = await window.__lfCheckApi();
  scrollGlides(true);
  // A task posted from a frame callback runs once that frame has rendered.
  const rendered = () => new Promise((then) => {
    const {port1, port2} = new MessageChannel();
    port1.onmessage = then;
    port2.postMessage(null);
  });
  window.lfWrites = [];
  window.lfWriteStep = frame;
  while (frame < frames) {
    await new Promise(requestAnimationFrame);
    window.lfWriteStep = ++frame;
    box.scrollTo({top: start + Math.round(by * frame / frames), behavior: 'instant'});
    await rendered();
    samples.push({scrolled: box.scrollTop, read: read()});
  }
  const settled = new Promise((then) => {
    const stop = watchScrollEnds(() => { stop(); then(); });
  });
  scrollGlides(false);
  await settled;
  await new Promise(requestAnimationFrame);
  await rendered();
  return samples;
}"""


def gesture_writes(page, by, scroller="document.scrollingElement", sample=None):
    """Scroll `scroller` (a page expression) by `by` in one gesture of
    `GESTURE_FRAMES` frames, each moving it an equal share, and return each DOM write it
    caused, numbered by the frame it came in, with what its settle wrote under its last,
    and how many frames it took. The pointer is moved off the page's controls first, so
    the scroll brings nothing new under it. With `sample`, a page function, it also
    returns that function's reading beside how far the scroller had gone, on each frame.
    Both are read once the frame has rendered: a box anchored to scrolled content takes
    the frame's scroll at the frame's anchor recalculation, after its frame callbacks,
    so read in one it stands where the frame before drew it.

    The test drives the frames, rather than a smooth `scrollBy`, so a slow host draws
    as many as a fast one. The runtime settles on each write's own `scrollend`, and
    between frames further apart than `SETTLE_MS`, so the gesture holds it as the
    runtime's own frame-by-frame scrolls do (arrivals.js, `scrollGlides`) and lets it
    settle once, after the last frame."""
    page.mouse.move(2, 300)
    rendered(page)
    start = page.evaluate(f"() => {scroller}.scrollTop")
    samples = page.evaluate(_GESTURE, [scroller, by, sample, GESTURE_FRAMES])
    rendered(page)
    assert page.evaluate(f"() => {scroller}.scrollTop") == pytest.approx(
        start + by, abs=1
    ), "the scroll did not go where the gesture leads"
    writes = page.evaluate(
        "() => { const w = window.lfWrites; window.lfWrites = null; return w; }"
    )
    if sample:
        return writes, GESTURE_FRAMES, samples
    return writes, GESTURE_FRAMES


def scroll_followers(writes, frames=None):
    """The places a scroll writes on more than two of its `frames`, a gesture's frames
    or a pass's steps, and on more than a third of them, as findings.

    A position written from scroll events is written on every step, a frame behind the
    browser, which carries a box that CSS lays out (an anchor, a sticky offset, a scroll
    timeline) with the scroll itself. A state the scroll changes is written only where
    the scroll crosses it, and a scroll crosses more as it goes further, as a section
    shorter than a pass is current once each way for each of its two edges, or a tag
    steps clear of each neighbour crossing beside it, so the scroll is allowed a share
    of its frames. A write that changes nothing needs no reading here: the browser
    fixture fails it wherever it happens (`write_watch.js`)."""
    places = {}
    for w in writes:
        places.setdefault(w["key"], []).append(w)
    found = []
    for written in places.values():
        first = written[0]
        what = (
            f"{first['type']} {first['attribute'] or ''} on {placed(first['target'])}"
        )
        on = {w["step"] for w in written}
        if len(on) > max(2, (frames or 0) / 3):
            found.append(f"{what} follows the scroll, written on {len(on)} steps")
    return found


_BROWSER_STATE = browser_function("harness.js", "browserState")


def reader_state(page):
    """Accessible content, controls, and their rendered boxes, plus focus and caret.

    Compare two readings from the same journey, not a saved implementation snapshot.
    Accessibility owns names, roles, values, and control states; Playwright's boxes
    expose accessible element geometry, not every detail of painted text. Browser
    focus affordances and visible fields' source/selection are read separately.
    Hidden caches, wrapper classes, app-owned attributes, and equivalent styles are
    irrelevant.
    Node/listener retention belongs to `live_counts`, not this reading.
    """
    focused = page.locator(":focus")
    native = page.evaluate(_BROWSER_STATE)
    return [
        *page.locator("body").aria_snapshot(boxes=True).splitlines(),
        "focus: "
        + (focused.last.aria_snapshot(boxes=True) if focused.count() else "none"),
        *("field: " + json.dumps(field) for field in native["fields"]),
        *("keyboard stop: " + json.dumps(stop) for stop in native["stops"]),
    ]


def state_changes(before, after):
    """Differences between two reader_state readings, with enough context to act."""
    return [
        line
        for line in difflib.unified_diff(before, after, lineterm="", n=0)
        if not line.startswith(("---", "+++", "@@"))
    ]


def live_counts(page):
    """What the page's renderer holds after a full collection, as {what: count}: its DOM
    nodes, those in its documents, comments included, and every detached node something
    still retains, and its event listeners. A count that climbs across repetitions of one
    gesture is a leak whether what it counts piles up in the page or behind it."""
    session = page.context.new_cdp_session(page)
    try:
        session.send("HeapProfiler.collectGarbage")
        session.send("Performance.enable")
        metrics = session.send("Performance.getMetrics")["metrics"]
    finally:
        session.detach()
    counted = {"Nodes": "nodes", "JSEventListeners": "event listeners"}
    return {counted[m["name"]]: m["value"] for m in metrics if m["name"] in counted}


def still_page(browser, url, width=1200):
    """The page at `url` with reduced motion and a fixed wall-clock date.

    Age labels stay fixed; timers, rendering and observer delivery still run. Tests
    of timer behavior explicitly advance this context's controlled timer clock.
    """
    context = browser.new_context(
        viewport={"width": width, "height": 900}, reduced_motion="reduce"
    )
    context.clock.set_fixed_time(time.time())
    return open_page(browser, url, context=context)


# Two of the page's timer ticks (`TICK_MS`, state-feed.js), advanced explicitly so a
# slow machine still executes the callbacks the reading covers.
REST_SECONDS = 5


def left_alone(page):
    """Prepare a still_page and its Leaf frames for their reading: rendered, the focus
    released and the pointer off its controls, and arrival notices retired. Advance its
    controlled timer clock through every due callback while Date.now stays fixed.

    The leaf's peek also shows while the pointer rests on the leaf or the panel's
    field, or the focus on the leaf, as after a press on the panel, so both leave
    before the notices are waited out.
    """

    def prepare_children(parent):
        for frame in parent.child_frames:
            if frame.evaluate(
                "() => !!document.querySelector('script[data-lf-entry]')?.lfReadiness"
            ):
                wait_until_ready(frame)
                rendered(frame)
            prepare_children(frame)

    rendered(page)
    prepare_children(page.main_frame)
    page.evaluate(RELEASE_FOCUS)
    page.mouse.move(2, 300)
    deadline = time.monotonic() + render_checks_model.SERVED_TIMEOUT_MS / 1000
    # A passing notice stands in the panel's empty field, in the line over it once the
    # field is written in, or in the leaf's peek (notifications.js).
    notice = (
        ".lf-floating-panel :is([data-says='notice'], .lf-fp-context[data-notice],"
        " .lf-fp-peek[data-shown])"
    )
    while any(frame.locator(notice).count() for frame in page.frames):
        assert time.monotonic() < deadline, "the arrival notice never retired"
        # still_page fixes Date.now but its timer clock otherwise runs in real time.
        # Run every callback until the notice retires; fast_forward would skip ticks.
        page.clock.run_for(100)
    rendered(page)


# Armed in each of the page's documents: its writes (`write_watch.js`), the frames it asks
# for, counted where they are asked for, and each time the focus lands in it.
_REST_ARM = browser_function("harness.js", "armRest")
_REST_READ = browser_function("harness.js", "readRest")


def at_rest(page):
    """What the page does while nobody touches it, as findings: each place it writes,
    each frame it asks for, each time it moves the focus, and each animation it runs
    without end, in its own document and each one it frames, such as a live sample.

    It starts once the still_page is `left_alone` and advances the timer clock through
    `REST_SECONDS`, running each due callback. Frames are counted where they are asked
    for, so a loop that writes nothing but still wakes the page every frame is named too."""
    left_alone(page)
    frames = page.frames
    for frame in frames:
        frame.evaluate(_REST_ARM)
    page.clock.run_for(REST_SECONDS * 1000)
    findings = []
    for frame in frames:
        rest = frame.evaluate(_REST_READ)
        where = "" if frame == page.main_frame else f" in {urlsplit(frame.url).path}"
        places = {
            f"{w['type']} {w['attribute'] or ''} on {placed(w['target'])}"
            for w in rest["writes"]
        }
        findings += [
            *(f"{place} written at rest{where}" for place in sorted(places)),
            *(
                f"a frame asked for {site} ran {n} times at rest{where}"
                for site, n in rest["frames"].items()
            ),
            *(
                [f"the focus moved {rest['focus']} times at rest{where}"]
                if rest["focus"]
                else []
            ),
            *(f"{animation} runs without end{where}" for animation in rest["endless"]),
        ]
    return findings
