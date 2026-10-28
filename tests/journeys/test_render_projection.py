"""Live version, report, replay, and projection tests."""

import json
import re
import threading

import pytest
from click.testing import CliRunner
from interact_support import (
    ROOT,
    add_test_widget,
    append_carried_log_record,
    append_command,
    running_http_server,
    trial_family,
)
from playwright.sync_api import expect
from render_cases_interaction import (
    ACTIONS_IN_FORCE,
    COMMAND_HUB_EXAMPLE,
    IN_FORCE_PAGE,
    RELATIVE_WIDGET_MODULE,
    RELATIVE_WIDGET_PAGE,
    THREAD_OBLIGATIONS,
    TWO_HOLDER_PAGE,
    TWO_HOLDER_SPARE_PAGE,
    drifting_widget,
    live_url,
)
from render_cases_navigation import (
    painted,
    source_revision,
)
from render_harness import (
    EXAMPLE_PACKAGES,
    IMPORTER_CARD,
    PANEL_THREAD,
    REPLAYED_PAGE,
    REPLY_HOST_PAGE,
    TOKEN,
    consume_browser_errors,
    example_media,
    expect_obligations_answered,
    holding,
    leaf_page,
    names,
    open_page,
    page_registry,
    panel_field,
    panel_view,
    resized,
    root_overflow,
    round_trip,
    sending,
    stamp_page,
    ticked,
    told,
)

from leaf import cli as cli_model
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import hosting as hosting_model
from leaf import http as http_model
from leaf import render_checks as render_checks_model
from leaf import structure as structure_model
from leaf.page_snapshot import capture_page_snapshot
from leaf.registry import storage as registry_storage
from leaf.render_checks import rendered
from leaf.render_gate import version as render_gate_model
from leaf.render_gate.preview import preview_server

pytestmark = pytest.mark.shifts_unsurveyed

from browser.threads import open_panel_thread

from journeys import first_thread_quote


def test_visual_review_guides_one_typed_still_run(browser, serve):
    authored = leaf_page(
        "visual review run",
        """
<h1 id="title">Visual review</h1>
<p id="claim">The candidate makes run status visible without changing navigation.</p>
<lf-visual-review id="visual-run" source="docs-run"></lf-visual-review>
""",
    )
    media = {
        "/media/051bee487bfb5d13.png": (
            example_media() / "051bee487bfb5d13.png"
        ).read_bytes(),
        "/media/a99a1b63048502d0.png": (
            example_media() / "a99a1b63048502d0.png"
        ).read_bytes(),
        "/media/3cf0e3efe80c6b01.png": (
            example_media() / "3cf0e3efe80c6b01.png"
        ).read_bytes(),
    }
    url = live_url(serve(authored, packages=("visual-review",), media=media))
    capture = {
        "observedAt": "2026-09-10T10:30:00-07:00",
        "browser": "Chrome",
        "browserVersion": "140.0.7339.80",
        "viewport": {"width": 900, "height": 373},
        "deviceScaleFactor": 2,
        "colorScheme": "light",
        "locale": "en-US",
        "timezone": "America/Los_Angeles",
    }
    record = {
        "title": "Docs navigation · candidate 7b921ac",
        "base": {"revision": "4c118aa", "url": "https://base.example/rev/"},
        "candidate": {
            "revision": "7b921ac",
            "url": "https://candidate.example/rev",
        },
        "cases": [
            {
                "id": "run-list",
                "title": "Run list status",
                "path": "/runs?owner=max",
                "action": "Open the run list.",
                "result": "Each row exposes its current status.",
                "classification": "changed",
                "capture": capture,
                "focus": {"x": 120, "y": 80, "width": 640, "height": 220},
                "before": "/media/051bee487bfb5d13.png",
                "after": "/media/a99a1b63048502d0.png",
                "traceUrl": "https://trace.example/runs/17",
            },
            {
                "id": "run-detail",
                "title": "Run detail navigation",
                "path": "/runs/17",
                "action": "Open the first run.",
                "result": "The detail link and surrounding layout stay stable.",
                "classification": "clean",
                "capture": capture,
                "before": "/media/051bee487bfb5d13.png",
                "after": "/media/a99a1b63048502d0.png",
            },
        ],
    }
    data_model.cmd_data_set(serve.page_dir, "docs-run", record)
    source = serve.page_dir / "index.html"
    source.write_text(
        source.read_text().replace(
            "</main>",
            '<lf-visual-review id="visual-pinned" source="docs-run-reviewed">'
            "</lf-visual-review></main>",
        )
    )
    # The pinned run is a second source that nothing rewrites.
    data_model.cmd_data_set(serve.page_dir, "docs-run-reviewed", record)
    page = open_page(browser, url)
    case_thread = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 2,
            "text": "Keep this note beside the run-list evidence.",
            "anchor": {
                "section": "visual-run",
                "datum": "run-list",
                "source": "docs-run",
                "source_revision": source_revision(serve.page_dir, "docs-run"),
            },
        },
    )
    told(page)
    widget = page.locator("#visual-run")
    cases = widget.locator(".lf-vr-case")
    first = cases.filter(has=page.locator(".lf-vr-title", has_text="Run list"))
    second = cases.filter(has=page.locator(".lf-vr-title", has_text="Run detail"))

    expect(widget.locator(".lf-vr-heading h2")).to_have_text(record["title"])
    expect(widget.locator(".lf-vr-case-button")).to_have_count(2)
    expect(first).to_be_visible()
    expect(second).to_be_hidden()
    expect(first).to_have_attribute("data-lf-projection", "visual-run")
    origin = first.evaluate("node => JSON.parse(node.dataset.lfOrigin)")
    assert origin["source"] == "docs-run"
    assert origin["path"] == ["cases", 0]
    expect(first.locator("lf-shot img")).to_have_count(2)
    expect(
        first.locator(f'.lf-page-thread[data-thread="{case_thread["id"]}"]')
    ).to_have_count(1)
    first.get_by_role("button", name="Capture details").click()
    for label, href in (
        ("Open before page", "https://base.example/rev/runs?owner=max"),
        ("Open after page", "https://candidate.example/rev/runs?owner=max"),
        ("Capture trace", "https://trace.example/runs/17"),
    ):
        expect(first.get_by_role("link", name=label)).to_have_attribute("href", href)
    expect(first.locator(".lf-vr-provenance")).to_contain_text("Chrome 140.0.7339.80")
    expect(first.locator(".lf-vr-provenance")).to_contain_text(
        "120, 80 · 640 × 220 CSS px"
    )
    page.keyboard.press("Escape")
    first.get_by_role("button", name="Image options").click()
    first.get_by_role("checkbox", name="Full frame").check()
    first.get_by_role("button", name="100%", exact=True).click()
    rendered(page)
    width = first.locator("lf-shot img").first.evaluate(
        "node => node.getBoundingClientRect().width"
    )
    assert width == pytest.approx(900, abs=1), "Actual size is captured CSS pixels"
    with sending(page, "approve the first visual case"):
        first.get_by_role("checkbox", name="Looks right").check()
    expect(widget.locator(".lf-vr-progress")).to_contain_text("1 of 2")
    widget.locator(".lf-vr-case-button").nth(1).click()
    expect(first).to_be_hidden()
    expect(second).to_be_visible()
    second.get_by_role("button", name="Slider").click()

    inserted = record["cases"][1] | {"id": "run-middle", "title": "Inserted run case"}
    changed = record | {
        "base": {"revision": record["base"]["revision"]},
        "cases": [
            record["cases"][0],
            inserted,
            record["cases"][1]
            | {
                "result": "The detail route remains stable after the rerun.",
                "capture": capture | {"observedAt": "2026-10-08T10:00:00-07:00"},
            },
        ],
    }
    original = second.element_handle()
    data_model.cmd_data_set(serve.page_dir, "docs-run", changed)
    told(page)
    expect(second.locator(".lf-vr-result")).to_have_text(
        "The detail route remains stable after the rerun."
    )
    assert original.evaluate(
        "node => node === document.querySelector('.lf-vr-case[data-lf-datum=\"run-detail\"]')"
    )
    expect(second).to_be_visible()
    expect(second.get_by_role("button", name="Slider")).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(
        first.get_by_role("checkbox", name="Looks right", include_hidden=True)
    ).to_be_checked()
    expect(
        page.locator("#visual-pinned .lf-vr-result").filter(
            has_text=record["cases"][1]["result"]
        )
    ).to_have_count(1)
    second.get_by_role("button", name="Capture details").click()
    expect(second.locator(".lf-vr-provenance")).to_contain_text(
        "2026-10-08T10:00:00-07:00"
    )
    expect(second.get_by_role("link", name="Open before page")).to_have_count(0)
    expect(second.get_by_role("link", name="Open after page")).to_have_attribute(
        "href", "https://candidate.example/rev/runs/17"
    )
    page.keyboard.press("Escape")
    resized(page, 390, 900)
    assert root_overflow(page) == 0

    widget.locator(".lf-vr-case-button").first.click()
    invalid_focus = changed | {
        "cases": [
            changed["cases"][0]
            | {
                "focus": {"x": 120, "y": 300, "width": 640, "height": 220},
            },
            *changed["cases"][1:],
        ]
    }
    data_model.cmd_data_set(serve.page_dir, "docs-run", invalid_focus)
    told(page)
    error = "focus 120,300 640×220 CSS px falls outside its captured images"
    expect(first.locator(".lf-error")).to_contain_text(error)
    consume_browser_errors(page, error)
    unequal_pair = changed | {
        "cases": [
            changed["cases"][0]
            | {
                "focus": {"x": 20, "y": 80, "width": 300, "height": 150},
                "after": "/media/3cf0e3efe80c6b01.png",
            },
            *changed["cases"][1:],
        ]
    }
    data_model.cmd_data_set(serve.page_dir, "docs-run", unequal_pair)
    told(page)
    error = "before is 1800px wide and after is 780px"
    expect(first.locator(".lf-error")).to_contain_text(error)
    consume_browser_errors(page, error)
    data_model.cmd_data_set(serve.page_dir, "docs-run", changed)
    told(page)
    expect(first.locator(".lf-error")).to_have_count(0)
    expect(first.locator("lf-shot img")).to_have_count(2)
    with sending(page, "withdraw the approval"):
        first.get_by_role("checkbox", name="Looks right").uncheck()
    expect(first.get_by_role("checkbox", name="Looks right")).not_to_be_checked()


def test_the_render_gate_reports_a_server_that_stops_answering(
    browser, tmp_path, monkeypatch
):
    """A read that never comes back is a sentence, not a hang.

    Every document the gate reads used to be fetched inside the page, and
    `page.evaluate` sends the driver no timeout at all — measured, an evaluate
    awaiting a fetch that never answers is still running at 200s. So a server that
    accepted a request and then went quiet left `page check --render` running with
    nothing printed, which is the one failure a user cannot tell from slowness: the
    gate stopping is loud, and the gate never stopping looks like a slow machine.

    Stall the gate's second read of this version, after its first read delivered the
    page. Stalling that first read would wedge navigation instead and report the
    banner the gate never saw. The deadline is shortened here because the number is
    not the subject, the bound is.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(render_gate_model, "SERVED_TIMEOUT_MS", 1500)
    d = tmp_path / "page"
    assert CliRunner().invoke(cli_model.cli, ["page", "init", str(d)]).exit_code == 0
    for _ in (1, 2):
        stamp_page(d, REPLY_HOST_PAGE, "t")

    delivered = threading.Event()
    asked = threading.Event()
    release = threading.Event()

    class Stalls(http_model.PageEndpoint):
        """Delivers the document, then accepts and drops the gate's file read."""

        def _get(self):
            if self.path.startswith("/versions/v2.html"):
                if not delivered.is_set():
                    delivered.set()
                elif not asked.is_set():
                    asked.set()
                    release.wait()
                    return None
                else:
                    # The next render attempt begins after the bounded read timed out.
                    release.set()
            return super()._get()

    httpd = hosting_model.LeafHTTPServer(
        ("127.0.0.1", 0), http_model.page_endpoint(d, TOKEN, endpoint=Stalls)
    )
    with running_http_server(httpd):
        try:
            failures = render_gate_model.render_version(
                browser,
                f"http://127.0.0.1:{httpd.server_address[1]}/versions/v2.html?t={TOKEN}",
            ).failures
        finally:
            release.set()

    assert asked.is_set(), "nothing ever asked for the stalled file, so nothing stalled"
    assert failures and all(f.code == "server-stopped" for f in failures), (
        f"a wedged server has to come back as a failure, and this came back as {failures}"
    )


def test_render_allows_authored_state_the_log_replays_over(browser, serve):
    """A revision may change its baseline while the recorded decision still paints.

    Historical state is a complete-state fold, not permission to edit. Placement
    belongs to the new authored container when its contents change.
    """
    url = serve(REPLAYED_PAGE)
    d = serve.page_dir
    for widget, action, detail in [
        ("approach", "choose", {"value": ["opt-shim"]}),
        ("work", "move", {"unit": "card-importer", "value": "col-done", "rank": "0i"}),
    ]:
        append_command(
            d,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": widget,
                "action": action,
                "detail": detail,
            },
        )

    # v2 changes the baseline pick and the card's column order. Rendering remains
    # valid: the user's choice paints over the baseline; the new order is authored.
    # A version that honors either decision, or says nothing of one, is the weaker
    # case of the same rule.
    contradicted = REPLAYED_PAGE.replace(
        'id="opt-stage"', 'id="opt-stage" chosen'
    ).replace(IMPORTER_CARD, "")
    contradicted = contradicted.replace(
        "</lf-card></lf-column>", f"</lf-card>{IMPORTER_CARD}</lf-column>"
    )
    document = structure_model.SourceDocument(contradicted)
    snapshot = capture_page_snapshot(
        d, document, files_model.latest_revision(d) + 1, url="/"
    )
    with preview_server(d, snapshot) as at:
        assert render_gate_model.render_version(browser, at).failures == []
    stamp_page(d, contradicted, "t")
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    expect(page.locator("#opt-shim")).to_have_attribute("chosen", "")
    expect(page.locator("#opt-stage")).not_to_have_attribute("chosen", "")


def test_the_render_gate_applies_every_action_in_force_a_second_time(
    browser, serve, tmp_path, monkeypatch
):
    """Absoluteness is what makes a fold a fold, and it is the one thing about a widget
    module no reading of a rendered page can see: a relative implementation renders
    perfectly and costs the user their gesture later, on the poll that replays it. So
    the gate applies each action in force again and asks what moved, and the page's
    composed vocabulary has nothing to do — a card placed where it already is, a pick set to
    what it already holds, a body assigned the words it already reads.

    The corpus cannot say this on its own: `test_page_fixture_renders` serves every page
    under a log holding one note, so the fold is empty there and the reading passes
    without applying anything. This page is the log the examples haven't got, and the
    floor is that the state in force covers every verb the registry declares — a verb
    added without an event here fails rather than going unexercised.

    Beside that clean vocabulary stands the bug-back for the module contract's first
    state rule, and for both readings the gate takes of it: a project widget that steps
    its count from the count it reads and appends its caption to the caption it reads,
    right once and wrong every time after. Its findings name the widget, both verbs, and
    what moved, and they are the only findings. Two verbs on one unit exercise the two
    readings that catch different things: the count is markup, so `shallowSigs` sees
    it; the caption is text, which that signature excludes on purpose, so only the
    verb's declared record form reaches it."""
    monkeypatch.chdir(tmp_path)
    add_test_widget(tmp_path / ".leaf", "lf-tally", upgrade=True)
    registry_path = tmp_path / ".leaf" / "registry.json"
    declarations = json.loads(registry_path.read_text())
    declarations["lf-tally"]["properties"]["count"] = {
        "type": "string",
        "pattern": "^[0-9]+$",
    }
    declarations["lf-tally"].setdefault("required", []).append("count")
    declarations["lf-tally"]["x-content"] = "data"
    declarations["lf-tally"]["x-example"] = (
        '<lf-tally id="tally-example" count="0"><pre>Nothing yet.</pre></lf-tally>'
    )
    # The registry holds a widget-unit verb to the attribute a version retracts a
    # decision with, so a state channel arrives with its way out of one.
    declarations["lf-tally"]["properties"]["restated"] = {"type": "boolean"}
    declarations["lf-tally"]["x-state"] = {
        "step": {
            "unit": "widget",
            "record": {"kind": "value", "attr": "count"},
        },
        "caption": {
            "unit": "widget",
            "record": {"kind": "body"},
        },
    }
    registry_path.write_text(json.dumps(declarations, indent=2))
    (tmp_path / ".leaf" / "widgets" / "lf-tally.js").write_text(RELATIVE_WIDGET_MODULE)
    tallies = RELATIVE_WIDGET_PAGE[
        RELATIVE_WIDGET_PAGE.index(
            '<lf-tally id="tally-fitted"'
        ) : RELATIVE_WIDGET_PAGE.rindex("</lf-tally>") + len("</lf-tally>")
    ]
    url = serve(
        IN_FORCE_PAGE.replace("</main>", tallies + "</main>"),
        packages=(*EXAMPLE_PACKAGES, ROOT / "tests/fixtures/packages/work", "./.leaf"),
    )
    relative_actions = [
        ("tally-fitted", "step", {"value": "3"}),
        ("tally-fitted", "caption", {"value": "Two greys at the north feeder."}),
    ]
    for widget, action, detail in [*ACTIONS_IN_FORCE, *relative_actions]:
        append_command(
            serve.page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": widget,
                "action": action,
                "detail": detail,
            },
        )
    # The agent channel through its own door, which is the only way a report is
    # written: both channels replay, so both rest on the same contract. A roster row
    # carries recorded state and a generated clause under one verb, so re-applying has
    # to leave both where they stand. Splitting the clause into another verb would make
    # the two reports compete for one fold key.
    for widget, verb, fields in [
        ("ab-baffles", "status", ["value=done"]),
        ("ab-wren", "state", ["value=blocked", "text=waiting on the fixture"]),
    ]:
        sent = CliRunner().invoke(
            cli_model.cli,
            ["page", "report", str(serve.page_dir), widget, verb, *fields],
        )
        assert sent.exit_code == 0, sent.output

    page = open_page(browser, url)
    in_force_ids = sorted(
        {widget for widget, _action, _detail in [*ACTIONS_IN_FORCE, *relative_actions]}
        | {"ab-baffles", "ab-wren"}
    )
    in_force = page.evaluate(
        """async ids => {
          const {widgetController} = await window.__lfWidgetApi();
          return ids.flatMap(id => {
            const widget = document.getElementById(id);
            const state = widgetController(widget).read().state;
            return Object.entries(state).flatMap(([verb, value]) =>
              (value.units ? Object.values(value.units) : [value])
                .filter(({action}) => action)
                .map(({action}) => [widget.id, widget.localName, verb, action]));
          });
        }""",
        in_force_ids,
    )
    page.close()
    registry = registry_storage.load_registry(serve.page_dir)
    declared = {
        (tag, verb)
        for tag, entry in registry.items()
        if tag.startswith("lf-")
        for verb in entry.get("x-state", {})
    }
    assert {(tag, verb) for _id, tag, _key, verb in in_force} == declared, (
        "the gate applies the state in force, so a declared verb missing from it is a "
        f"verb nothing here re-applies: page holds {in_force}, registry declares "
        f"{sorted(declared)}"
    )
    assert {
        (key, action) for widget, _tag, key, action in in_force if widget == "ab-pick"
    } == {("choose", "choose"), ("answer", "answer"), ("add", "add")}
    failures = render_gate_model.render_version(browser, url).failures
    assert [
        (f.scheme, f.at, f.values["changed"])
        for f in failures
        if f.code == "relative-render"
    ] == [
        ("light", "<lf-tally id=tally-fitted>", ["tally-fitted", "body text"]),
        ("light", "<lf-tally id=tally-seen>", ["body text"]),
    ], failures
    # The relative widget's appended caption is its own fault in other readings too;
    # the current vocabulary beside it leaves the gate nothing to say.
    assert all(names(f, "lf-tally") for f in failures), failures


def test_the_render_gate_reads_a_page_that_has_finished_arriving(
    browser, serve, tmp_path, monkeypatch
):
    """A page finishes twice, and the second ending arrives moving.

    `lf-upgraded` is the first: every widget upgraded, the geometry final. The first
    read starts earlier but its answer cannot apply before that boundary, so a gate
    reading there can still read the authored page — here, a widget standing 120px
    out of place with its words over the paragraphs below it.
    `lf-applied` is the second, and the frame it lands in is the first frame of the
    move it describes: a read that brings nothing presents the authored page
    deliberately, so the replay after it crosses the presentation boundary and moves
    rather than teleports.

    Both windows are load-shaped — a busy server, a few hundred milliseconds — which
    is how this page passed at a desk and reported words drawn over words under a
    full suite. Holding the action back until the page's first read has answered, and
    the gate's own read until the action is in, makes the window the same every run:
    the page reads as broken for about three seconds, and the gate must have nothing
    to say about it. Either wait on its own leaves this failing."""
    # For the page directory and its vendored layer; this test serves it itself.
    serve(
        drifting_widget(tmp_path, monkeypatch), packages=(*EXAMPLE_PACKAGES, "./.leaf")
    )
    landed = []
    # The action is in the log and the gate may read it. Both halves of the window are
    # this one fact, so the hold below and the append are the same statement made twice.
    arrived = threading.Event()
    expired = []
    settle = {
        "kind": "action",
        "author": "user",
        "revision": 1,
        "widget": "drift-note",
        "action": "settle",
        "detail": {"value": "0"},
    }

    class TheLogArrivesLate(http_model.PageEndpoint):
        """The action reaches the log between the page's first read and the gate's.

        A page whose first read brings nothing is presented on the authored markup
        deliberately, so the replay that follows is past the presentation boundary
        and moves rather than teleports. The page's read is told from the gate's own
        reading of the same document by the Referer a page fetch carries and an
        APIRequestContext does not: the action goes in behind the page's read, and
        the gate's is held until it has, so the gate always sees a log with the action
        in it and always has a caught-up stamp to wait for.

        Holding it is the whole arrangement rather than a margin. The page stamps
        itself upgraded without awaiting its first read, so the gate is free to reach
        `/api/state` while that read is still in flight — and under a busy server it
        does, whereupon it counts an empty log, waits for nothing, and reads the page
        mid-move. That is this test's own failure and not the gate's."""

        def _get(self):
            state_read = self.path.startswith("/api/state")
            page_read = state_read and self.headers.get("Referer")
            # Bounded, and inside the gate's own deadline for a served document: a
            # runtime that stopped reading state at startup is named by the assertion
            # below rather than by a gate whose server appeared to stop answering.
            held_for = render_checks_model.SERVED_TIMEOUT_MS / 2000
            if state_read and not page_read and not arrived.wait(held_for):
                expired.append(self.path)
            answer = super()._get()
            if page_read and not landed:
                landed.append(self.headers["Referer"])
                append_command(serve.page_dir, settle)
                arrived.set()
            return answer

    httpd = hosting_model.LeafHTTPServer(
        ("127.0.0.1", 0),
        http_model.page_endpoint(serve.page_dir, TOKEN, endpoint=TheLogArrivesLate),
    )
    with running_http_server(httpd):
        late = f"http://127.0.0.1:{httpd.server_address[1]}/versions/v1.html?t={TOKEN}"
        failures = render_gate_model.render_version(browser, late).failures
    # The window first, because the gate's verdict on a window that never opened says
    # nothing: an empty log is a page with nothing to replay and nothing to report.
    assert landed and "/versions/v1.html" in landed[0], (
        "the action never went in behind the page's first read, so the window this "
        f"rests on never opened: {landed}"
    )
    assert not expired, (
        "the gate's read was released by the 10s bound rather than by the append, so "
        f"it read a log with nothing in it to wait for: {expired}"
    )
    assert failures == []


def test_a_moved_card_identifies_its_user_origin_across_tabs(browser, serve):
    """A move outlives its notice: the card the user moved stays explicitly
    identified as overriding authored placement in the tab that moved it and in a fresh
    replay alike, because the runtime compares the page's state against the version's
    own snapshot rather than remembering who wrote what. The runtime's quiet word and
    Page Map row carry that origin while the grip names the move and its destination.
    The card the move displaced stays unmarked — the log named one card, not its
    neighbours. The honoring version says the state itself, so on it the
    disagreement and both renderings are gone."""
    url = serve(REPLAYED_PAGE)
    page = open_page(browser, url)

    # The keyboard gesture takes the same #send path as a drag. The sender's own
    # replay is a no-op, which is exactly the case the version snapshot covers.
    page.get_by_role("button", name="Move: Wire the importer — Doing").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    expect(page.locator("#card-importer")).to_have_attribute(
        "data-lf-user-override", "1"
    )
    expect(page.locator("#card-notes")).not_to_have_attribute(
        "data-lf-user-override", "1"
    )
    expect(
        page.get_by_role(
            "button",
            name="Move: Wire the importer — Done",
            exact=True,
        )
    ).to_be_visible()

    # A fresh tab reads the same fact from replay alone, and paints both its Page Map
    # reading and its durable spoken state.
    second = open_page(browser, url)
    expect(second.locator("#card-importer")).to_have_attribute(
        "data-lf-user-override", "1"
    )
    expect(second.locator("#card-importer > .lf-quiet")).to_have_text("my change")
    expect(
        second.get_by_role(
            "button",
            name="Move: Wire the importer — Done",
            exact=True,
        )
    ).to_be_visible()
    # The Page Map names the move once: while the agent owes it an answer, under the
    # row saying the move was sent, which is the user's change as much as its own row.
    second.keyboard.press("g")
    second.keyboard.press("Shift+p")
    expect(
        second.get_by_role("button", name=re.compile(r"^Open saved: Saved"))
    ).to_be_visible()
    expect(
        second.get_by_role("button", name=re.compile(r"^Open my change"))
    ).to_have_count(0)
    second.keyboard.press("Escape")
    assert (
        second.locator("#card-importer").evaluate(
            "el => getComputedStyle(el).outlineStyle"
        )
        == "none"
    )
    second.evaluate("""() => {
        window.__originWrites = [];
        new MutationObserver(records => {
            window.__originWrites.push(...records.map(record => record.target.id));
        }).observe(document.getElementById('work'), {
            subtree: true, attributes: true, attributeFilter: ['data-lf-user-override'],
        });
    }""")
    ticked(second)
    assert second.evaluate("() => window.__originWrites") == [], (
        "an unchanged heartbeat rewrote the origin marks and woke the board's "
        "card-name observer"
    )

    # The honoring version authors the card where the user put it; replay
    # no-ops against it and the mark has nothing left to say.
    d = serve.page_dir
    honored = REPLAYED_PAGE.replace(IMPORTER_CARD, "").replace(
        'label="Done">', f'label="Done">{IMPORTER_CARD}'
    )
    stamp_page(d, honored, "t")
    third = open_page(browser, url.replace("v1.html", "v2.html"))
    expect(third.locator("#col-done #card-importer")).to_be_visible()
    # Absence only counts once replay has decided every action.
    third.wait_for_function("() => document.body.dataset.lfApplied === '1'")
    expect(third.locator("#card-importer")).not_to_have_attribute(
        "data-lf-user-override", "1"
    )
    expect(third.locator("#card-importer > .lf-quiet")).to_have_count(0)
    expect(
        third.get_by_role("button", name="Move: Wire the importer — Done", exact=True)
    ).to_be_visible()


def test_a_settled_third_party_holder_wears_the_layers_mark(
    browser, serve, tmp_path, monkeypatch
):
    """A settlement is the layer's rendering of the log's decision, never a module
    obligation: the trial's module is the product's starter, which only defines the
    element — a `LeafElement` with no `render()` of its own — and
    once its decision replays the holder wears
    data-lf-state, the retired slot is marked and hidden by the theme's one generic
    rule, and the quote anchored in it detaches instead of pointing at words the
    page's reading has dropped. The mark and the hide used to be each holder
    module's own duty, stated in the module contract and the key table and enforced
    nowhere, and the first family that forgot would have split the page's reading
    from the file's in silence. Later the layer painted them only through a
    controller the module subscribed to, which left the same duty under another
    name. The second half drives it all back out: the fold
    keeps the last surviving action per verb and unit, so a decision on an outcome
    that settles nothing displaces the one before it, and the mark, the marker and
    the hide follow it."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)
    module = (tmp_path / ".leaf" / "widgets" / "lf-trial.js").read_text()
    assert "render(" not in module, "the holder's module must leave the mark to Leaf"

    url = serve(
        TWO_HOLDER_PAGE,
        anchored=[("th-next", "warmed on the first request")],
        packages=(*EXAMPLE_PACKAGES, "./.leaf"),
    )
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "th-cache",
            "action": "decide",
            "detail": {"outcome": "shelve"},
        },
    )
    page = open_page(browser, url)
    expect(page.locator("#th-cache")).to_have_attribute("data-lf-state", "shelve")
    expect(page.locator("#th-cache lf-proposed")).to_be_hidden()
    expect(first_thread_quote(page, serve.page_dir)).to_have_class(
        re.compile(r"\bdetached\b")
    )
    assert painted(page, "lf-mark") == "", (
        "the quote matched inside a slot the logged decision retired: nothing wrote "
        "the settlement mark for a module that doesn't"
    )
    assert not any(
        event["kind"] == "reanchor"
        for event in events_model.read_events(serve.page_dir)
    ), (
        "reading an unchanged revision must not persist a temporary decision's detachment"
    )
    page.close()

    # The mark follows the fold out as well as in: the file's current state is the
    # last surviving action per verb and unit, so a decision on an outcome that
    # settles nothing displaces the one before it, and a mark left in place would
    # silence a slot the log has handed back.
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "th-cache",
            "action": "decide",
            "detail": {"outcome": "pause"},
        },
    )
    page = open_page(browser, url)
    assert page.locator("#th-cache").get_attribute("data-lf-state") is None
    expect(page.locator("#th-cache lf-proposed")).to_be_visible()
    expect(first_thread_quote(page, serve.page_dir)).not_to_have_class(
        re.compile(r"\bdetached\b")
    )
    assert painted(page, "lf-mark") != "", (
        "the displaced decision's slot is back on the page, so its quote must "
        "anchor again"
    )


def test_the_render_gate_holds_a_settled_slot_to_the_logs_decision(
    browser, serve, tmp_path, monkeypatch
):
    """Bug-back for the settlement reading, in both directions. The bare family first
    proves the gate accepts a holder that brings nothing of its own — the layer's
    default hide is the whole of its disappearance. Then two independent faults go in
    together. The one generic hide rule is stripped from the vendored theme, standing
    in for whatever re-shows a retired slot (a later layer's rule outranking the
    default, a module re-showing what it folded): the words stay on screen where the
    user can select what no comment can anchor to, and the gate must say so. And the
    vendored module marks every trial after the controller publishes: on the undecided
    spare that is a settlement the log never decided, styling as settled words the
    page still reads, and the gate must say that too. Both failures render perfectly, which
    is why each is put back deliberately."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)

    url = serve(TWO_HOLDER_SPARE_PAGE, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "th-cache",
            "action": "decide",
            "detail": {"outcome": "shelve"},
        },
    )
    assert render_gate_model.render_version(browser, url).failures == []

    hide = "  [data-lf-retired] {\n    display: none;\n  }"
    vendored = serve.page_dir / "theme.css"
    css = vendored.read_text()
    assert css.count(hide) == 1
    vendored.write_text(css.replace(hide, ""))
    module = serve.page_dir / "widgets" / "lf-trial.js"
    module.write_text(
        """\
import {keeps, LeafElement} from "/runtime/widget-api.js";
customElements.define("lf-trial", class extends LeafElement {
  #presented;
  render() {
    if (!this.reading.state) return;
    if (document.body.dataset.lfPresented === "1") {
      keeps(this, "data-lf-state", "shelve");
      return;
    }
    this.#presented ??= new MutationObserver(() => {
      if (document.body.dataset.lfPresented !== "1") return;
      this.#presented.disconnect();
      this.#presented = undefined;
      if (this.isConnected) keeps(this, "data-lf-state", "shelve");
    });
    this.#presented.observe(document.body, {
      attributes: true, attributeFilter: ["data-lf-presented"],
    });
  }
});
"""
    )
    stamp_page(
        serve.page_dir,
        (serve.page_dir / "index.html").read_text(),
        "capture the visible settled slot and the false settlement mark",
    )
    failures = render_gate_model.render_version(browser, live_url(url)).failures
    assert any(
        failure.code == "retired-slot"
        and failure.at == "<lf-trial id=th-cache>"
        and (failure.values["outcome"], failure.values["slot"])
        == ("shelve", "lf-proposed")
        for failure in failures
    ), failures
    assert any(
        failure.code == "settlement-mark"
        and failure.at == "<lf-trial id=th-spare>"
        and (failure.values["mark"], failure.values["outcome"]) == ("shelve", None)
        for failure in failures
    ), failures


def test_a_followed_link_arrives_as_a_fresh_load_of_it_does(browser, serve):
    """A link followed on the page and the same URL opened in a new tab are one
    destination, so they arrive alike: the worker's worktree sits in a disclosure
    the command hub keeps shut, and the browser's own jump landed on nothing where
    the fresh load revealed it. Back then returns the user to where they pressed,
    and Forward to the link's entry after the disclosure is shut again arrives
    there as well: the offset that entry was left at was read over the open
    disclosure, and restoring it over the shut one landed further down the page
    with the worktree still hidden."""
    url = live_url(serve(COMMAND_HUB_EXAMPLE))
    shown = """(id) => { const t = document.getElementById(id);
                         const r = t.getBoundingClientRect();
                         return t.checkVisibility() && r.top >= 0 && r.bottom <= innerHeight
                           && r.top < 150; }"""

    fresh = open_page(browser, f"{url}#tree-w-5")
    fresh.wait_for_function(shown, arg="tree-w-5")
    fresh.close()

    page = open_page(browser, url)
    assert not page.evaluate(shown, "tree-w-5")
    link = page.locator('a[href="#tree-w-5"]')
    link.scroll_into_view_if_needed()
    pressed_at = page.evaluate("() => document.scrollingElement.scrollTop")
    link.click()
    page.wait_for_function(shown, arg="tree-w-5")

    # Shut again and followed again: a press on a link to the fragment the page already
    # shows is still a trip there.
    page.locator("#w-5 > details > summary").click()
    expect(page.locator("#tree-w-5")).to_be_hidden()
    link.click()
    page.wait_for_function(shown, arg="tree-w-5")

    page.go_back()
    page.wait_for_function(
        "(at) => Math.abs(document.scrollingElement.scrollTop - at) <= 1",
        arg=pressed_at,
    )

    page.locator("#w-5 > details > summary").click()
    expect(page.locator("#tree-w-5")).to_be_hidden()
    page.go_forward()
    page.wait_for_function(shown, arg="tree-w-5")


def test_a_thread_obligation_waits_until_answered(browser, serve):
    """A question in a thread is one of the page's obligations — an obligation for the user
        wherever it stands — and `m` reaches it. A single-answer group
    is answered by its pick, as on the page; a `multiple` group's toggles each
    reach the agent live, so only its Done press closes it, as an `answer` action
    x-awaits.answered names for a `multiple` group. The thread's own reply box is the words'
        home, so the group brings no box of its own. `g T` leaves option-digit scope for
    Threads, while `t` reaches a particular thread and `c` reaches its reply box.

    The answer is said once, when the log takes it. The log is where it is recorded,
    and the group's own markup stays the author's: a module writes there only where the
    registry declares the attribute as a record form, which a thread verb can never
    have, no version being able to carry a thread's markup."""
    url = serve(REPLY_HOST_PAGE)
    for event in THREAD_OBLIGATIONS:
        append_carried_log_record(serve.page_dir, event)
    page = open_page(browser, url)
    expect_obligations_answered(page, "0/2")

    page.keyboard.press("m")
    one = page.locator(f'{PANEL_THREAD}[data-thread="c-which"]')
    expect(one).to_be_visible()
    # The arrival stands on the question's own region; its picks are the next Tab stops.
    expect(page.locator("#tq-one-decision")).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.locator("#tq-one .lf-pick").first).to_be_focused()
    expect(one.locator(".lf-say")).to_have_count(0)
    reply = panel_field(page)
    page.keyboard.press("Enter")
    expect(reply).to_be_focused()
    expect(reply).to_have_attribute("name", "reply")
    expect(page.locator("#tq-one > lf-option[chosen]")).to_have_count(0)
    # The box hands the user back to the thread it belongs to, which is the
    # container it is part of rather than the pick they pressed Enter from.
    page.keyboard.press("Escape")
    expect(one).to_be_focused()

    page.locator("#tq-redis").click()
    expect_obligations_answered(page, "1/2")

    open_panel_thread(page, "c-any")
    expect(page.locator("#tq-set .lf-done")).to_be_visible()

    # The group's hairline stands between the cells, so the Done press keeps its own
    # frame whole. Drawn on the press instead, the divider recolored its top edge and
    # left the seam above it to nothing.
    assert page.locator("#tq-set .lf-done").evaluate(
        """el => { const s = getComputedStyle(el);
                   return s.borderTopColor === s.borderBottomColor
                       && s.borderTopWidth === s.borderBottomWidth; }"""
    ), "the group's divider recolors the Done press's own frame"

    # And it butts that hairline, like every other cell of the control. This is the one
    # place the reading is asked at all: the joined-cell readings in the render gate see
    # a served version, and a thread group lives in the panel the runtime builds, so the
    # gate never reaches it. The press was written as a control floating inside the
    # group on a margin of its own, and the theme comment said so — but the group is a
    # grid and had been stretching it to the full column all along, so what the 8px
    # actually drew was a hairline with dead ground under it, on every thread the agent
    # asked a set question in.
    seam = page.locator("#tq-set").evaluate(
        """el => { const done = el.querySelector('.lf-done');
                   const last = done.parentElement.previousElementSibling;
                   const a = last.getBoundingClientRect();
                   const b = done.getBoundingClientRect();
                   return {gap: Math.round((b.top - a.bottom) * 10) / 10,
                           stretched: Math.abs(a.width - b.width) < 1}; }"""
    )
    assert seam["stretched"], (
        "the Done press no longer fills the column, so what follows is about a shape "
        "this test no longer describes"
    )
    # The hairline is the group's ground in a 1px gap; more is dead ground.
    assert seam["gap"] < 1.5, (
        f"the hairline above the Done press floats {seam['gap']}px above it"
    )

    page.locator("#tq-logs").click()
    expect(page.locator("#tq-logs")).to_have_attribute("chosen", "")
    expect_obligations_answered(page, "1/2")
    with sending(page, "the answer"):
        page.locator("#tq-set .lf-done").click()
    expect_obligations_answered(page, "2/2")
    expect(page.locator("#tq-set .lf-done")).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".lf-live")).to_have_text("Marked answered")
    # Said once, by the log's answer. An `answered` attribute on the group said it
    # again in the author's namespace, where the entry admits nothing undeclared and no
    # version could ever have carried a record of a thread verb — invisible to every
    # consumer but shallowSigs, which reads what no version can assert as state one
    # authored.
    assert (
        render_checks_model.evaluate_probe(page, "undeclaredAttrs", page_registry(page))
        == []
    ), "the Done press left an attribute on a widget its entry never declared"
    actions = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert actions[-1]["widget"] == "tq-set" and actions[-1]["action"] == "answer"
    assert actions[-1]["detail"] == {}

    # And a second tab reads it off the log, which is the only place it is written.
    # A user who made no gesture gets the same pressed press and the same closed
    # decision — replay is what puts it there, and the one representation is what replay
    # writes, so there is nothing for a version or a markup copy to fall behind. A
    # message's widgets draw where its thread is open, so the tab opens it to look.
    other = open_page(browser, url)
    expect_obligations_answered(other, "2/2")
    open_panel_thread(other, "c-any")
    expect(other.locator("#tq-set .lf-done")).to_have_attribute("aria-pressed", "true")
    assert (
        render_checks_model.evaluate_probe(
            other, "undeclaredAttrs", page_registry(other)
        )
        == []
    ), "replaying the answer left an attribute the entry never declared"
    other.close()

    # Taking back a recordless chrome answer rebuilds its authored controls at once —
    # the withdrawal is the user's own gesture on their own widget. The selection is
    # another verb, so it survives that rebuild. Whether the decision is open again is
    # the log's reading, so the count moves when the withdrawal reaches it and not while
    # it is held at the wire. In particular, the surviving `choose` action cannot answer
    # a `multiple` set, whose x-awaits.answered condition is an `answer` in force.
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        page.keyboard.press("z")
    expect(page.locator("#tq-set .lf-done")).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#tq-logs")).to_have_attribute("chosen", "")
    expect(page.locator("#tq-set-decision > h3")).to_have_text("Which extras apply?")
    expect_obligations_answered(page, "2/2")
    holding(page, held, 1, "the thread answer's withdrawal")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect_obligations_answered(page, "1/2")

    # The sequence's promise holds from a mark: g T leaves the option's digit scope and
    # reaches Threads. A stray digit there neither travels nor picks; t then c makes the
    # repeatable category walk and the thread-local reply route explicit. The Threads
    # view stands in the thread's place, so the log says whether the digit picked.
    open_panel_thread(page, "c-which")
    page.locator("#tq-one .lf-pick").first.focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    threads = page.locator(panel_view("threads"))
    expect(threads).to_be_visible()
    page.keyboard.press("1")
    expect(threads).to_be_visible()
    page.keyboard.press("t")
    page.keyboard.press("c")
    expect(panel_field(page)).to_be_focused()
    expect(panel_field(page)).to_have_attribute("name", "reply")
    sent = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert sent[-1]["action"] == "answer", "the sequence's digit must not pick"
