"""Standalone export tests."""

import importlib.util
import itertools
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from click.testing import CliRunner
from interact_support import install_payload
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import exporting as exporting_model
from leaf import hosting as hosting_model
from leaf import render_checks as render_checks_model
from leaf import server as server_model
from leaf.render_gate import browser as browser_model
from playwright.sync_api import expect
from render_support import (
    LONG_PAGE,
    PAGE_FIXTURES,
    REPORT_PAGE,
    leaf_page,
    live_url,
    open_page,
    primed,
    refuse,
    resized,
    serious_axe_violations,
    watched,
)

pytestmark = pytest.mark.nightly

ROOT = Path(__file__).parent.parent


@pytest.fixture
def preview_slot(tmp_path):
    slot = f"pytest-{os.getpid()}-{tmp_path.name}"
    page = ROOT / ".tmp" / "previews" / slot
    yield slot, page
    if server_model.running_server(page):
        hosting_model.cmd_stop(page)
    shutil.rmtree(page, ignore_errors=True)


def test_interrupting_a_live_preview_exits_without_a_traceback(preview_slot, spawn):
    """Ctrl-C reaches the foreground server directly and produces only its abort."""
    slot, page = preview_slot
    preview = spawn(
        [
            sys.executable,
            str(ROOT / "scripts" / "preview.py"),
            "design-decision",
            "--slot",
            slot,
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        text=True,
    )

    deadline = time.monotonic() + 90
    while not server_model.running_server(page):
        if preview.poll() is not None:
            output, _ = preview.communicate()
            pytest.fail(f"preview exited before serving:\n{output}")
        if time.monotonic() > deadline:
            pytest.fail("preview did not start serving within 90 seconds")
        time.sleep(0.05)

    os.killpg(preview.pid, signal.SIGINT)
    output, _ = preview.communicate(timeout=10)

    assert preview.returncode == 1, output
    assert output.endswith("Aborted!\n")
    assert "Traceback" not in output


def test_a_leaf_failure_exits_the_preview_without_a_wrapper_traceback(
    tmp_path, preview_slot
):
    """The child command's diagnostic is the preview command's whole error."""
    source = tmp_path / "invalid.html"
    source.write_text("<p>outside the document</p>", encoding="utf-8")
    slot, _ = preview_slot
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "preview.py"),
            "--source",
            str(source),
            "--slot",
            slot,
            "--background",
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=90,
    )

    assert result.returncode == 1, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "refusing to stamp index.html:" in result.stderr
    assert "Traceback" not in result.stdout + result.stderr


def test_named_live_previews_serve_one_source_in_independent_runtime_slots(
    browser, tmp_path
):
    """A developer can hold one fixture still while two vendored runtimes serve it.

    The named pages and their background services are the public evidence. If the
    script falls back to its single default directory, the second run stops and
    replaces the first; if it ignores the shared source, the planted heading is
    absent from one or both URLs.
    """
    source = tmp_path / "shared-preview.html"
    source.write_text(
        (ROOT / "examples" / "design-decision.html")
        .read_text(encoding="utf-8")
        .replace("Where sessions live", "Shared runtime comparison", 1),
        encoding="utf-8",
    )
    prefix = f"pytest-{os.getpid()}-{tmp_path.name}"
    installed = install_payload(tmp_path / "other-runtime")
    runtime_marker = "/* preview runtime marker */"
    installed_runtime = installed / "skills" / "leaf" / "assets" / "leaf.js"
    installed_runtime.write_text(
        installed_runtime.read_text(encoding="utf-8") + f"\n{runtime_marker}\n",
        encoding="utf-8",
    )
    slots = [f"{prefix}-before", f"{prefix}-after"]
    runtimes = [ROOT, installed]
    pages = [ROOT / ".tmp" / "previews" / slot for slot in slots]
    urls = []
    try:
        for slot, runtime in zip(slots, runtimes, strict=True):
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "preview.py"),
                    "--source",
                    str(source),
                    "--runtime",
                    str(runtime),
                    "--slot",
                    slot,
                    "--background",
                ],
                cwd=ROOT,
                capture_output=True,
                check=False,
                text=True,
                timeout=90,
            )
            assert result.returncode == 0, (
                f"slot {slot}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
            output = result.stdout.splitlines()
            assert output[:2] == [
                "prepared shared-preview (1 version)",
                "",
            ]
            assert "initialized" not in result.stdout
            assert "stamped" not in result.stdout
            urls.append(output[-1])

        assert urls[0] != urls[1]
        assert all(
            page.joinpath("index.html").read_text() == source.read_text()
            for page in pages
        )
        assert runtime_marker not in pages[0].joinpath("leaf.js").read_text()
        assert runtime_marker in pages[1].joinpath("leaf.js").read_text()

        for url, runtime in zip(urls, runtimes, strict=True):
            page = browser.new_page(viewport={"width": 1200, "height": 900})
            errors = watched(page)
            page.goto(url, wait_until="load")
            expect(page.locator(".lf-preview")).to_contain_text(
                f"Preview · {runtime.name}"
            )
            expect(
                page.get_by_role("heading", name="Shared runtime comparison")
            ).to_be_visible()
            assert errors == []
            page.close()
    finally:
        for page, runtime in zip(pages, runtimes, strict=True):
            subprocess.run(
                [str(runtime / "bin" / "leaf"), "server", "stop", str(page)],
                cwd=runtime,
                check=False,
                capture_output=True,
                text=True,
            )
            shutil.rmtree(page, ignore_errors=True)


# ---------- export: the page as one file ----------


def test_the_example_preview_command_exports_a_file_that_opens_on_its_own(
    browser,
):
    """The handoff command names one file whose drawn page needs no live server."""
    out = ROOT / ".tmp" / "example-pr-walkthrough.html"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "preview.py"),
            "pr-walkthrough",
            "--export",
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert result.stdout.splitlines()[-1] == str(out.resolve())

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.on("requestfailed", lambda request: errors.append(f"unfetched {request.url}"))
    page.goto(out.as_uri(), wait_until="load")
    source = (ROOT / "examples" / "pr-walkthrough.html").read_text(encoding="utf-8")
    title = re.search(r"<h1>(.*?)</h1>", source, re.DOTALL).group(1).strip()
    expect(page.get_by_role("heading", name=title)).to_be_visible()
    assert page.locator("script").count() == 0
    assert page.locator('link[rel="stylesheet"]').count() == 0
    assert page.locator("style").count() > 0
    assert errors == []
    page.close()


def test_exporting_an_example_leaves_the_live_preview_untouched(
    monkeypatch, page_dir, standing_server
):
    """A static handoff can be made while its interactive proof stays live."""
    live_source = (page_dir / "index.html").read_bytes()
    live_server = standing_server(page_dir)
    spec = importlib.util.spec_from_file_location(
        "leaf_preview_script", ROOT / "scripts" / "preview.py"
    )
    assert spec and spec.loader
    preview = importlib.util.module_from_spec(spec)
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec.loader.exec_module(preview)
    monkeypatch.setattr(preview, "PAGE", page_dir)
    monkeypatch.setattr(sys, "argv", ["preview.py", "pr-walkthrough", "--export"])

    try:
        preview.main()
        assert live_server.poll() is None
        assert (page_dir / "index.html").read_bytes() == live_source
    finally:
        CliRunner().invoke(cli_model.cli, ["server", "stop", str(page_dir)])
        live_server.wait(timeout=5)


def test_a_broken_probe_module_stops_export_with_a_named_error(browser, serve):
    """Export reports its instrumentation boundary instead of leaking a traceback."""

    def break_probe(page):
        page.route(
            "**/_leaf/render-checks/index.js",
            lambda route: route.fulfill(
                status=200,
                content_type="text/javascript; charset=utf-8",
                body='import { missingForTest } from "/runtime/widget-api.js";',
            ),
        )

    url = serve(LONG_PAGE)
    root_url = url.replace("/versions/v1.html", "/")
    with pytest.raises(
        SystemExit,
        match=r"v1\.html could not load its browser probe module",
    ):
        exporting_model.export_page(
            primed(browser, break_probe), root_url, serve.page_dir, "v1.html"
        )


def test_a_browser_too_old_to_copy_a_page_is_refused_by_its_own_version(
    browser, tmp_path
):
    """`bake()` ends in `root.getHTML({ serializableShadowRoots: true })`, which
    Chromium grew in 125. The render gate never bakes, so an older browser passes
    `--render` and then dies inside the probe with `root.getHTML is not a function` —
    which the export reports as a probe module it could not load, sending the reader
    to Leaf's own instrumentation rather than to the browser their host handed over.
    Asking the browser's age before the page is opened replaces that with one
    sentence naming the floor and the version.

    The old browser is a reading rather than an install, because what is under test
    is which sentence a host gets and every browser this suite can reach is younger
    than the floor. The suite's own is the control: a floor that refused it would
    turn every export in the corpus into that sentence, so the check that it does not
    is what keeps the refusal from being free."""

    class Old:
        version = "122.0.6261.128"

    with pytest.raises(
        SystemExit,
        match=r"v1\.html needs Chromium 125 or later to copy, and this browser is "
        r"122\.0\.6261\.128",
    ):
        exporting_model.export_page(Old(), "http://unused", tmp_path, "v1.html")

    assert browser_model.below_export_floor(browser) is None


def test_a_table_of_contents_keeps_native_links_in_a_static_copy(
    browser, serve, tmp_path
):
    """A table of contents is navigation rather than a live decision. Its generated
    links and targets stay in a standalone copy, where the browser can follow them
    without the runtime that supplied the smoother live-page journey."""
    source = leaf_page(
        "contents export",
        """
<h1>Migration plan</h1>
<lf-toc id="contents"></lf-toc>
<h2>Prepare</h2><p>Take a snapshot.</p>
<h2 style="margin-top: 110vh">Verify</h2><p>Compare the totals.</p>
""",
    )
    url = serve(source)
    out = tmp_path / "contents-copy.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.goto(out.as_uri(), wait_until="load")
    links = page.get_by_role("navigation", name="On this page").get_by_role("link")
    expect(links).to_have_count(2)
    href = links.nth(1).get_attribute("href")
    assert href and href.startswith("#lf-contents-section-")

    links.nth(1).click()
    expect(page.locator(":target")).to_have_attribute("id", href[1:])
    assert page.locator("script").count() == 0
    assert errors == []
    page.close()


def test_a_gloss_keeps_its_explanation_in_static_media(browser, serve, tmp_path):
    """Hover is only the live page's presentation. Print and a standalone export have
    no script or pointer contract, so the author-written x-says tip becomes visible
    inline and its now-inert raised mark leaves with the rest of the offers."""
    source = leaf_page(
        "gloss export",
        """
<h1>Rollout</h1>
<p>Start with a <lf-gloss tip="A thin path through the real system."
  >walking skeleton</lf-gloss> before parallelizing.</p>
""",
    )
    url = serve(source)

    live = browser.new_page(viewport={"width": 1200, "height": 900})
    live.goto(url, wait_until="load")
    live.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    tip = live.locator(".lf-gloss-popover")
    expect(tip).to_be_hidden()
    live.emulate_media(media="print")
    expect(tip).to_be_visible()
    assert tip.evaluate("el => getComputedStyle(el).position") == "static"
    live.close()

    out = tmp_path / "gloss-copy.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    copy = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(copy)
    copy.goto(out.as_uri(), wait_until="load")
    expect(copy.locator(".lf-gloss-popover")).to_be_visible()
    expect(copy.locator(".lf-gloss-mark")).to_have_count(0)
    expect(copy.locator("lf-gloss")).to_contain_text(
        "walking skeletonA thin path through the real system."
    )
    assert errors == []
    copy.close()


def test_an_export_drops_a_live_widget_work_claim(browser, serve, tmp_path):
    """A local receipt is live runtime chrome even though its seat is in the page.
    A standalone copy has no agent behind it, so preserving the rendered sentence
    would turn a provisional claim into a frozen lie."""
    work_page = leaf_page(
        "work export",
        """
<h1 id="h">Rollout</h1>
<lf-board id="rollout"><lf-column id="now" label="Now">
  <lf-card id="rollout-card"><strong>Ship the rollout</strong> Check the shard.</lf-card>
</lf-column></lf-board>
""",
    )
    url = serve(work_page)
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "status",
            str(serve.page_dir),
            "working",
            "checking the shard",
            "--on",
            "rollout-card",
        ],
    )
    assert result.exit_code == 0, result.output

    out = tmp_path / "work-copy.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    page = browser.new_page()
    errors = watched(page)
    page.goto(out.as_uri(), wait_until="load")

    expect(page.locator(".lf-receipt")).to_have_count(0)
    expect(page.locator("#rollout-card")).not_to_contain_text("checking the shard")
    assert errors == []
    page.close()


RECEIPT_DRAFTS = leaf_page(
    "drafts",
    """
<h1 id="h">Two notes</h1>
<p id="p-settled">The invitation the author has written in already.</p>
<lf-draft id="d-settled"><pre>The sample workshop is in the green room.</pre></lf-draft>
<p id="p-open">The one still on its way.</p>
<lf-draft id="d-open"><pre>The sample workshop is in the blue room.</pre></lf-draft>
""",
)
SETTLED_EDIT = {
    "kind": "action",
    "author": "user",
    "revision": 1,
    "widget": "d-settled",
    "action": "edit",
    "detail": {"text": "The sample workshop is in the green room."},
}
OPEN_EDIT = {
    "kind": "action",
    "author": "user",
    "revision": 1,
    "widget": "d-open",
    "action": "edit",
    "detail": {"text": "The sample workshop is in the red room."},
}


def test_a_copy_keeps_a_settled_record_and_drops_a_move_still_in_flight(
    browser, serve, tmp_path
):
    """Both of these readings are receipts, and only one of them is news.

    `d-open` holds an edit the document has not caught up with, so its reading is the
    phase an agent is in — Picked up here — and a file has nothing standing behind that
    sentence. `d-settled` holds one the authored markup already states, which leaves the
    page map reading a decision this same file carries, with the decided text in it. That
    is the fact the rail is held open for and, for a widget contributing no receipt text
    of its own, the only margin record of the choice, so the copy keeps it.

    It keeps it as a word, and in one seat. What a copy must not carry out of a seat that
    was a Button's before the move was made is the promise: the status role the walk
    lands on, its tab stop, and the offer marker that said a widget built this box — and
    no widget did, which is why nothing is left here for the press pass to keep the way
    it keeps a control's page words. Where the word stands is the same question asked of
    layout: the draft's own Edit press had taken the resting seat and left the reading
    under `…`, and the ellipsis that opens a fold goes out with every other press."""
    url = serve(RECEIPT_DRAFTS, events=[SETTLED_EDIT, OPEN_EDIT])
    in_flight = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("widget") == "d-open"
    ][-1]
    events_model.append_event(
        serve.page_dir,
        {"kind": "pickup", "author": "page", "events": [in_flight["id"]]},
    )

    reading = ".lf-margin-marker[data-lf-behavior='receipt']"
    live = browser.new_page(viewport={"width": 1200, "height": 900})
    live.goto(url, wait_until="load")
    resized(live, 1200, 900)
    expect(
        live.locator(f"[data-lf-margin-for='d-settled'] {reading}")
    ).to_have_attribute("data-lf-standing", "")
    expect(
        live.locator(f"[data-lf-margin-for='d-open'] {reading}")
    ).not_to_have_attribute("data-lf-standing", "")
    standing = live.locator(f"[data-lf-margin-for='d-settled'] {reading}")
    assert standing.get_attribute("role") == "status", (
        "the live reading is not the status a copy has to disarm"
    )
    live.close()

    out = tmp_path / "standalone.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.goto(out.as_uri(), wait_until="load")

    carried = page.evaluate(
        """() => [...document.querySelectorAll('[data-lf-behavior="receipt"]')].map(
             row => ({
               target: row.closest('[data-lf-margin-for]')?.dataset.lfMarginFor,
               word: row.querySelector('.lf-margin-action-label').textContent,
               shown: row.checkVisibility(),
               folded: Boolean(row.closest('.lf-margin-options')),
               role: row.getAttribute('role'),
               tabindex: row.getAttribute('tabindex'),
               offer: row.getAttribute('data-lf-offer'),
             }))"""
    )
    # One seat, standing in the item. The live page had two — the marker, and the peer
    # the fold holds once a contributed control takes the resting one — and a copy can
    # open no fold, so the reading it keeps is the reading it can show.
    assert carried == [
        {
            "target": "d-settled",
            "word": "Outcome",
            "shown": True,
            "folded": False,
            "role": "img",
            "tabindex": None,
            "offer": None,
        }
    ], carried
    assert (
        page.evaluate(
            """() => [...document.querySelectorAll('main *')]
                 .filter(el => el.textContent.trim() === 'Picked up').length"""
        )
        == 0
    ), "the copy still says an agent picked up a move it cannot report on"
    assert errors == []
    page.close()


AGENT_SUGGESTION = leaf_page(
    "agreed",
    """
<h1 id="h">One rewrite</h1>
<p id="replace">The camera survey found two dead zones.
  <lf-suggestion id="sug-refill">
    <lf-old>Refill every feeder each morning.</lf-old>
    <lf-new>Refill a feeder when its camera shows it half-empty.</lf-new>
  </lf-suggestion></p>
""",
)
AGENT_ACCEPT = {
    "kind": "action",
    "author": "agent",
    "revision": 1,
    "widget": "sug-refill",
    "action": "accept",
    "detail": {},
}


def test_a_copy_stands_its_kept_record_where_each_medium_can_show_it(
    browser, serve, tmp_path
):
    """The other seat a standing record can be sitting in, and the two mediums that
    draw no rail for it.

    An agent decided this suggestion, so there is nothing for the reader to take back:
    the widget contributes no shown control, and the page map's own marker carries the
    reading. That is the seat the test above never reaches — a draft's Edit press takes
    the resting seat and leaves the reading in the fold, which is where the copy finds
    it there.

    So the copy's record stops being a marker. The class is the rail's seat rather than
    the reading's, and both rules that stop drawing the rail name it — the 900px floor
    and print — so a record left wearing it is a fact the file states on a wide screen
    and drops on a narrow one or on paper, while the same record kept in a fold stands
    in all three. The spoken name goes with the class: it is the walk's address, which
    counts the page map's entries and measures how far down the exporter's own window
    the target sat, and a file has neither. The reading's own word takes its place,
    because the span holding that word cannot: the runtime's stylesheet rides into the
    file and keeps the span for a hover a file has no other use for, so a record left
    to it would stand there saying nothing at all.

    Where it stands is the second half, and it is one question for both seats. A file
    cannot dock: the packing pass measured the rail at the width the page was exported
    at and left with the scripts. Below the floor and on paper the absolute seat it
    measured is off the page box — 115px past an 800px window, and away on a sheet
    narrower than the export — so the item takes the docked shape there instead."""
    url = serve(AGENT_SUGGESTION, events=[AGENT_ACCEPT])
    reading = ".lf-margin-action[data-lf-behavior='receipt']"
    item = '[data-lf-margin-for="sug-refill"]'
    live, live_errors = open_page(browser, live_url(url))
    resized(live, 1200, 900)
    standing = live.locator(f"{item} {reading}")
    expect(standing).to_have_class(re.compile(r"\blf-margin-marker\b"))
    expect(standing).to_have_attribute("data-lf-standing", "")
    expect(standing).to_have_attribute("aria-label", re.compile(r"^Outcome, 1 of 1, "))
    assert live.locator(f"{item} .lf-margin-reading-option").count() == 0, (
        "the widget contributed a shown control, so this is the seat the test above has"
    )
    assert live_errors == []
    live.close()

    out = tmp_path / "standalone.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    # The exported file, read at the width it was taken at and at one narrower than the
    # rail's own floor, on screen and on paper. Each answer is the record's box against
    # the page's: a seat outside it is a fact the medium does not carry.
    for width in (1200, 800):
        page = browser.new_page(viewport={"width": width, "height": 900})
        errors = watched(page)
        page.goto(out.as_uri(), wait_until="load")
        for medium in ("screen", "print"):
            page.emulate_media(media=medium)
            assert page.evaluate(
                """() => [...document.querySelectorAll('.lf-margin-action')].map(el => ({
                     marker: el.matches('.lf-margin-marker'),
                     word: el.querySelector('.lf-margin-action-label').textContent,
                     shown: el.checkVisibility(),
                     named: el.getAttribute('aria-label'),
                     role: el.getAttribute('role'),
                     within: el.getBoundingClientRect().right
                       <= document.documentElement.getBoundingClientRect().right,
                     overflow: document.documentElement.scrollWidth > innerWidth,
                   }))"""
            ) == [
                {
                    "marker": False,
                    "word": "Outcome",
                    "shown": True,
                    "named": "Outcome",
                    "role": "img",
                    "within": True,
                    "overflow": False,
                }
            ], f"{width}px, {medium}"
        assert errors == []
        page.close()


FOLDED_SUGGESTION = leaf_page(
    "agreed, out of sight",
    """
<h1 id="h">One rewrite</h1>
<details id="survey"><summary>The camera survey</summary>
<p id="replace">The camera survey found two dead zones.
  <lf-suggestion id="sug-refill">
    <lf-old>Refill every feeder each morning.</lf-old>
    <lf-new>Refill a feeder when its camera shows it half-empty.</lf-new>
  </lf-suggestion></p>
</details>
""",
)
# The row the copy keeps and the live page's own row for the same target: the paragraph's
# item, holding the suggestion's `Accepted` receipt. Read on both runtimes so the copy's
# reading is asserted against the page it is a copy of rather than on its own.
WITHHELD_BESIDE_ITS_FOLD = """() => {
  const item = document.querySelector('[data-lf-margin-for="replace"]');
  return {
    waiting: item.matches('.lf-waiting'),
    shown: item.checkVisibility(),
    open: document.getElementById('survey').open,
    passage: document.getElementById('replace').checkVisibility(),
  };
}"""


def test_a_copy_withholds_the_record_for_a_passage_it_is_still_folding_away(
    browser, serve, tmp_path
):
    """The record above stands because its target does. This one's does not.

    The packing pass says so on the live page: a row whose anchor is not shown is left
    `lf-waiting`, and a shut fold is the ordinary way a target goes unshown while the
    reading for it is real. The class travels into the file with the row, so the file
    is the same reading — a record for words the reader has to open the fold to reach,
    and nothing in a copy opens it.

    Which makes the two facts one question. The shape a copy takes below the rail's
    floor and on paper is a rule about rows that stand; a rule that reached these too
    would be the only thing standing them, because `display: flex` is what it answers
    `lf-waiting`'s `display: none` with.

    On paper the reason reads differently and the answer is the same, so the medium is
    named on both sides here. Print unfolds a shut disclosure through
    `::details-content`, which is why the passage is on the sheet while `open` is still
    false — and the row is still the one the packing pass withheld, measured on screen
    before any media rule and carrying that reading into the file unchanged. The live
    page reads exactly that way in print, which is the assertion above the copy's:
    whether a withheld row should stand where paper unfolds its target is a question
    about `.lf-margin-item.lf-waiting` in both runtimes, and a copy answering it alone
    would state on paper a fact the page it is a copy of does not."""
    url = serve(FOLDED_SUGGESTION, events=[AGENT_ACCEPT])
    live, live_errors = open_page(browser, live_url(url))
    resized(live, 1200, 900)
    item = live.locator('[data-lf-margin-for="sug-refill"]')
    expect(item).to_have_class(re.compile(r"\blf-waiting\b"))
    live.emulate_media(media="print")
    assert live.evaluate(WITHHELD_BESIDE_ITS_FOLD) == {
        "waiting": True,
        "shown": False,
        "open": False,
        "passage": True,
    }
    assert live_errors == []
    live.close()

    out = tmp_path / "standalone.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    for width in (1200, 800):
        page = browser.new_page(viewport={"width": width, "height": 900})
        errors = watched(page)
        page.goto(out.as_uri(), wait_until="load")
        expect(page.locator(".lf-margin-item")).to_have_count(1)
        for medium in ("screen", "print"):
            page.emulate_media(media=medium)
            assert page.evaluate(WITHHELD_BESIDE_ITS_FOLD) == {
                "waiting": True,
                "shown": False,
                "open": False,
                "passage": medium == "print",
            }, f"{width}px, {medium}"
        assert errors == []
        page.close()


@pytest.mark.parametrize("page_fixture", PAGE_FIXTURES, ids=lambda p: p.stem)
def test_an_exported_page_fixture_stands_on_its_own(
    page_fixture, browser, serve, tmp_path
):
    """Every shipped example and the developer gallery is copied to a file and opened
    from disk. No server answers, so anything still reaching for one is a hole, and the
    console is where a hole says so. Every page fixture runs because what a copy loses
    is per-widget — the corpus alone would pass while a widget it lacks was broken.

    A copy over-promising is the other half of that, and it went unread for as long as
    there was nothing here asking. Tab into an exported decision page landed on a pick
    mark, which summoned the keyboard address for a key that answers nothing, into a row
    holding no column for it; a board's ten grips each opened a grab cursor; twenty
    options lit under a pointer that could not pick one. So the copy is asked what it
    still offers, in the three registers an offer is made in — a widget's chrome still
    holding a tab stop or a role, a control standing there with nothing left behind it,
    and a hand or a grab under the pointer — and every question is put to the markers
    rather than to any widget."""
    url = serve(page_fixture)
    out = tmp_path / "standalone.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))

    page = browser.new_page(viewport={"width": 1200, "height": 900}, bypass_csp=True)
    errors = watched(page)
    page.on("requestfailed", lambda r: errors.append(f"unfetched {r.url}"))
    render_checks_model.prepare_standalone_probes(page)
    page.goto(out.as_uri(), wait_until="load")
    state = page.evaluate("""() => ({
        scripts: document.querySelectorAll('script').length,
        chrome: document.querySelectorAll('.lf-chrome').length,
        toServer: [...document.querySelectorAll('[src^="/"], [href^="/"]')]
            .map(e => e.getAttribute('src') ?? e.getAttribute('href')),
        links: document.querySelectorAll('link[rel="stylesheet"]').length,
        column: getComputedStyle(document.querySelector('main')).maxWidth,
        // A page gives up a CSS shell claim for what it hangs in the margin, and
        // a copy keeps only the strips whose residents came with it: a suggestion's
        // controls are gone from a file that can decide nothing, and its rail with them,
        // while sidenotes are the page's own words and stand in a copy exactly as they
        // stand on screen. So the reading is not that the column is centred — a page
        // carrying notes is deliberately not — but that no strip is held open for
        // nothing. Resolve the shell's custom-property lengths through a probe, then
        // ask whether anything is actually standing in each claimed band.
        //
        // The bands stand against the column's own edges and not against the page's.
        // A strip is what main gives up beside itself and the shift then re-centres
        // what is left, so on a window wider than the column plus its strips the
        // leftover room sits outside both — and a reading taken from body's edges
        // asks about that leftover instead, which is nobody's claim and always empty.
        //
        // And it is put to the residents that make the claim rather than to everything
        // under main. A widget asking for width is drawn past the column by design and
        // lands in the band beside it while claiming nothing, so a reading satisfied by
        // any overlap at all answered for a board or a diagram on three of the five
        // copies that hold a strip: the strip could have been held open for nothing and
        // the band still read as occupied. The claimants are the ones the cascade names
        // — aside.sidebar writes --strip-l, while aside.sidenote and the living
        // margin's items write --claim-note, --claim-rail, and --claim-map. A copy
        // carries no .lf-chrome, read above, and a project layer's own --lf-claim-right
        // furniture is outside the corpus this runs over.
        empty: ((main) => {
            const box = main.getBoundingClientRect();
            const length = (name) => {
                const probe = document.createElement('i');
                probe.style.cssText = `position:fixed;visibility:hidden;height:0;padding:0;border:0;width:var(${name})`;
                main.append(probe);
                const width = probe.getBoundingClientRect().width;
                probe.remove();
                return width;
            };
            const left = length('--strip-l'), right = length('--strip-r');
            const residents = 'aside.sidebar, aside.sidenote, .lf-margin-item';
            const held = (lo, hi) => hi - lo > 1
                && ![...document.querySelectorAll(residents)]
                .some(el => { const r = el.getBoundingClientRect();
                              return el.checkVisibility() && r.width > 1
                                     && r.left < hi - 1 && r.right > lo + 1; });
            return [
                held(box.left - left, box.left) && 'left',
                held(box.right, box.right + right) && 'right',
            ].filter(Boolean);
        })(document.querySelector('main')),
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
        // lf-shot's label still flips its frames, its checkbox still takes the keyboard —
        // so the role half stands down for one of the platform's own controls. The tab
        // stop's half does not: offer writes that on presses of its own making and on
        // nothing else.
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
                              // A label may name a native control outside its offered
                              // wrapper. `label.control` is the platform's resolved
                              // association, so this is just as live as a descendant.
                              && ![...el.querySelectorAll('label')]
                                  .some(label => label.control)
                              && !el.closest('label, summary, a[href]'))
            .map(el => (el.className || el.tagName.toLowerCase()) + ': '
                       + el.textContent.trim().replace(/\\s+/g, ' ').slice(0, 24)),
        // The same claim in paint. A hand or a grab says a gesture lands here, and in a
        // copy one lands nowhere the browser isn't the thing acting: a label's checkbox, a
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
    covered = render_checks_model.evaluate_probe(page, "coveredWords")
    assert render_checks_model.evaluate_probe(page, "coveredWords") == covered
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
    assert state["empty"] == [], (
        "the copy holds a strip of its own width open with nothing standing in it, so "
        "the column sits off to one side of a page it has all of — a rail reserved for "
        f"something the file hasn't got: {state['empty']}"
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
    assert errors == [], f"{page_fixture.stem} needs a server to render: {errors}"


def test_a_copy_carries_a_workers_standing_report(browser, serve, tmp_path):
    """The copy is the page as replay left it, and a report is replay's other channel —
    none of the corpus can say so, because an example is one version with an empty log.

    The gap the wait covers is real and narrow: the first read starts beside widget
    startup, but the runtime can stamp `lf-upgraded` while that read is still unanswered,
    so the stamp export opens on is no promise that anything in the log has been painted.
    Ordinarily the answer is ready by then, which is why the page arrives painted however
    the wait is written and why the count being wrong stayed invisible. Refusing that
    first read is the whole difference — replay is left to the state reads on the far side of
    the stamp: the one the news stream prompts as it opens, and the 2s tick behind it,
    which is exactly where a loaded machine would have put it. Counting actions alone
    leaves nothing to wait for on a log holding one report, and the copy goes out blank.

    The refusal is served to export's own page rather than the copy's, through the
    stand-in `primed` supplies."""
    url = serve(REPORT_PAGE)
    sent = CliRunner().invoke(
        cli_model.cli,
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
        exporting_model.export_page(
            primed(browser, refuse_the_first_poll), url, serve.page_dir, "v1.html"
        )
    )

    page = browser.new_page()
    page.goto(out.as_uri(), wait_until="load")
    expect(page.locator("#t-parser")).to_have_attribute("status", "done")
    expect(page.locator("#t-feeders > .lf-chips")).to_contain_text("2/2 done")
    page.close()


def test_a_copy_carries_none_of_the_exporters_own_window(browser, serve, tmp_path):
    """A live page measures the window it is in and states the numbers inline on the
    root: the room a wide widget may take, the width the margin strips are sized
    against, where each edge stands. An inline value outranks every rule a stylesheet
    could write, so a copy keeping one is laid out against the width the exporter's
    headless window happened to have, on a file whose whole point is being opened
    somewhere else.

    What separates those from the rail is not where they are written but whether the
    copy still has the thing they measure. The panel and the tray leave with the chrome;
    the room is a reading of a window nobody will open this file in. A suggestion's rail
    is the width of a control a decided change keeps, and
    `test_a_copy_keeps_the_rail_a_decided_change_left` is what says so — a sweep of every
    inline custom property on the root takes it and puts the exported board off the left
    of the page. So this asks for the named ones and asks the rail's own test for the
    rail.

    The live half is the non-vacuity: unless this page really states them, a copy that
    carries none says nothing at all."""
    url = serve(LONG_PAGE, comments=2)

    inline_custom = """() => {
        const inline = document.documentElement.style;
        const found = {};
        for (let i = 0; i < inline.length; i++)
            if (inline[i].startsWith('--'))
                found[inline[i]] = inline.getPropertyValue(inline[i]);
        return found;
    }"""
    session = ("--lf-panel-w", "--lf-tray-w")

    live = browser.new_page(viewport={"width": 1200, "height": 900})
    live.goto(url, wait_until="load")
    live.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    live.locator(".lf-threads-toggle").click()
    live.wait_for_timeout(600)
    measured = live.evaluate(inline_custom)
    live.close()
    stated = [name for name in session if name in measured]
    assert stated, (
        "the live page states none of the window measurements this is about "
        f"({measured}), so a copy carrying none of them proves nothing"
    )

    out = tmp_path / "standalone.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))
    copy = browser.new_page()
    copy.goto(out.as_uri(), wait_until="load")
    carried = copy.evaluate(inline_custom)
    copy.close()

    assert not [name for name in session if name in carried], (
        "the copy is laid out against the exporter's own window rather than the "
        f"reader's: {carried}"
    )


def test_a_copy_wears_the_mark_and_claims_no_session(browser, serve, tmp_path):
    """A copy keeps the mark and drops the status painted on it. The live page was
    exported under a working claim — `page init` leaves one — so the tone it was wearing
    is a session that does not exist behind a file, which is the same lie the chrome is
    dropped for. Nothing else on the tab is worth losing over it: the mark still says
    which product wrote the file, and it is inlined, so it survives the copy leaving the
    machine that served it (test_an_exported_page_fixture_stands_on_its_own is what says no
    link here still points at a server)."""
    url = serve(LONG_PAGE)
    out = tmp_path / "standalone.html"
    out.write_text(exporting_model.export_page(browser, url, serve.page_dir, "v1.html"))

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
