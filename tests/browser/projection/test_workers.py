"""Worker reports, rosters, worktree evidence, version comparisons and the command hub's
goals and tasks, as the live page shows them."""

import json
import re
from datetime import datetime, timedelta
from itertools import pairwise

import pytest
from click.testing import CliRunner
from interact_support import (
    COMMAND_HUB_PACKAGE,
    append_carried_log_record,
    append_command,
)
from playwright.sync_api import expect
from render_cases_interaction import (
    COMMAND_HUB_EXAMPLE,
    COMMAND_HUB_PAGE,
    REPORT_PAGE,
    ROSTER_PAGE,
    backdate_note,
    live_url,
    stale_report,
)
from render_cases_navigation import source_revision
from render_harness import (
    compare_with,
    draft_control,
    holding,
    leaf_page,
    open_page,
    panel_field,
    panel_menu,
    refuse,
    sending,
    stamp_page,
    ticked,
    told,
    wait_for_revision,
    write,
)

from leaf import cli as cli_model
from leaf import data as data_model
from leaf import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_workers_report_paints_live_and_ends_at_the_version_that_answers_it(
    browser, serve
):
    """The agent channel, end to end in the browser: a `leaf page report`
    reaches the open page on the next poll and paints as provisional news — the status
    attribute moves, the parent's done-fraction recounts, and Page Map identifies a
    Reported state rather than the user's change. Task status remains work
    state and never creates a user request. Then the version that answers the report
    by id takes the page back: replay skips a report the note named, so the overruling
    version's own state is what renders, with no provisional mark left on it. Last, the
    diff against the base version reads the base's state as the user saw it — report
    included — so the overrule marks as a change even though the two files spell the
    same status."""
    url = serve(REPORT_PAGE)
    d = serve.page_dir
    page = open_page(browser, live_url(url))
    fraction = page.locator("#t-feeders > .work-progress")
    expect(fraction).to_contain_text("1/2 done")
    # Nothing waits on the user.
    expect(page.locator(".lf-fp-on-user")).to_have_attribute("aria-label", "On me")

    sent = CliRunner().invoke(
        cli_model.cli,
        ["page", "report", str(d), "t-parser", "status", "value=review"],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    task = page.locator("#t-parser")
    expect(task).to_have_attribute("status", "review")
    expect(task).to_have_attribute("data-lf-reported", "1")
    expect(task).not_to_have_attribute("data-lf-user-override", "1")
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    report_reading = page.get_by_role(
        "button", name=re.compile(r"^Open reported state: Reported state")
    )
    expect(report_reading).to_be_visible()
    page.keyboard.press("Escape")
    assert task.evaluate("el => getComputedStyle(el).outlineStyle") == "none"
    # The visible status line follows the reported attribute, so a user listening
    # hears the current state too.
    assert "review" in task.aria_snapshot()
    expect(page.locator(".lf-fp-on-user")).to_have_attribute("aria-label", "On me")

    # A second report supersedes the first — absolute values fold — and the
    # progress fraction recounts across the tree.
    sent = CliRunner().invoke(
        cli_model.cli,
        ["page", "report", str(d), "t-parser", "status", "value=done"],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    expect(task).to_have_attribute("status", "done")
    said = task.aria_snapshot()
    assert "done" in said and "review" not in said, said
    expect(fraction).to_contain_text("2/2 done")
    expect(page.locator(".lf-fp-on-user")).to_have_attribute("aria-label", "On me")

    # The overruling version: its markup keeps `active` and publishes typed report
    # settlements resolved from `overruled`, so replay stops them
    # and the document speaks again.
    v2 = REPORT_PAGE.replace(
        '<lf-test-task id="t-parser" status="active">',
        '<lf-test-task id="t-parser" status="active" overruled>',
    )
    stamp_page(d, v2, "not done yet")
    assert len(events_model.read_events(d)[-1]["settles"]) == 2
    wait_for_revision(page, 2)
    task = page.locator("#t-parser")
    expect(task).to_have_attribute("status", "active")
    expect(task).not_to_have_attribute("data-lf-reported", "1")
    expect(page.locator("#t-feeders > .work-progress")).to_contain_text("1/2 done")

    # The diff's state half, mirror-image: v1's markup also said `active`, but
    # the user last saw v1 wearing the report's `done`, so the overrule is a
    # change since the base — the report-layered base state is what says so.
    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map(e => e.id)"
    ) == ["t-parser"]


def test_a_comparison_retries_when_the_live_projection_advances(browser, serve):
    """The mapped revision and its state must describe the DOM in one reading.

    Hold the first projected base after the server has answered it, advance the open
    page with a report, and then deliver that stale base. The comparison asks again at
    the new sequence before painting; otherwise it marks the task as changed even though
    the same report stands on both the base and current documents.
    """
    url = serve(REPORT_PAGE)
    d = serve.page_dir
    stamp_page(
        d,
        REPORT_PAGE.replace("</main>", '<p id="new-copy">A new prose line.</p></main>'),
        "added prose",
    )
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    held = []
    requests = []

    def hold_first_view(route):
        requests.append(route.request.url)
        if not held:
            held.append([route, None, False])
        else:
            route.continue_()

    page.route("**/api/view*", hold_first_view)
    try:
        with page.expect_request("**/api/view*"):
            compare_with(page, 1)
        holding(page, held, 1, "the first comparison view")
        assert held, "the first comparison view was not held"
        held[0][1] = held[0][0].fetch()

        append_command(
            d,
            {
                "kind": "report",
                "author": "agent",
                "revision": 1,
                "widget": "t-parser",
                "action": "status",
                "detail": {"value": "done"},
            },
        )
        told(page)
        expect(page.locator("#t-parser")).to_have_attribute("status", "done")

        with page.expect_request("**/api/view*"):
            held[0][0].fulfill(response=held[0][1])
            held[0][2] = True
        holding(page, requests, 2, "the retried comparison view")
        assert len(requests) >= 2, "the stale comparison view was not retried"
        expect(page.locator("#new-copy")).to_have_class(re.compile(r"lf-ins-block"))
        expect(page.locator("#t-parser")).not_to_have_class(re.compile(r"lf-ins-block"))
        versions = panel_menu(page, "versions")
        expect(versions.locator(".lf-fp-version[data-current]")).to_contain_text("v2")
        expect(
            versions.get_by_role("button", name=re.compile(r"^Compare with v1\b"))
        ).to_have_attribute("aria-pressed", "true")
        page.keyboard.press("Escape")
    finally:
        if held and not held[0][2]:
            held[0][0].fulfill(response=held[0][1])
        page.unroute("**/api/view*")


def test_a_comparison_reaches_a_version_stamped_before_a_re_vendor(browser, serve):
    """A revision keeps the layer it captured, and comparing to it is not a re-vendor.

    `/api/view` and an immutable document are stamped with the captured generation of
    the revision they name, so after a re-vendor the base of a comparison legitimately
    answers for a layer the live page is no longer on. Running that answer through the
    delivery gate reads it as the page being re-vendored underneath the user, which it
    is not: the page refuses its own comparison, and the user is told the server is
    updating.
    """
    url = serve(REPORT_PAGE)
    d = serve.page_dir
    # The whole premise is that this second init really re-vendors. Were it ever refused,
    # the base of the comparison would not be foreign and the case would pass against the
    # runtime it exists to pin.
    revendored = CliRunner().invoke(
        cli_model.cli, ["page", "init", str(d)], catch_exceptions=False
    )
    assert revendored.exit_code == 0, revendored.output
    stamp_page(
        d,
        REPORT_PAGE.replace("</main>", '<p id="new-copy">A new prose line.</p></main>'),
        "added prose",
    )
    page = open_page(browser, url.replace("v1.html", "v2.html"))

    compare_with(page, 1)

    expect(page.locator("#new-copy")).to_have_class(re.compile(r"lf-ins-block"))
    expect(panel_field(page)).not_to_have_attribute(
        "placeholder", re.compile("Waiting for the server to finish updating")
    )


def test_a_rosters_row_says_when_the_log_last_heard_from_that_worker(browser, serve):
    """The half of a roster no version can write down. A report in force states what
    each worker is doing; only the log knows when it last said so, and a page that keeps
    a fleet is at its least trustworthy exactly when the user has been away longest.
    So the row renders elapsed time from the newest report and re-renders on every poll.

    Then the case the line exists for: a claim of work nobody has refreshed. It is
    called out in words rather than in the tint alone, on the rope the page's status
    already gives its one agent (quietSince), and only against a claim — an idle worker
    that has said nothing all day is idle, which is what it said."""
    url = serve(ROSTER_PAGE)
    d = serve.page_dir
    page = open_page(browser, live_url(url))
    wren, finch = page.locator("#ag-wren"), page.locator("#ag-finch")
    # Before any worker has spoken, the row dates from the version that asserted it —
    # not from nothing, which would leave a fleet dead since last night reading exactly
    # like one published a minute ago.
    expect(wren.locator(".lf-heard")).to_contain_text("last heard")
    # The state is a word this module writes rather than paint the runtime speaks, so
    # a user listening gets it from the row itself.
    assert "working" in wren.aria_snapshot()

    sent = CliRunner().invoke(
        cli_model.cli,
        # A state the markup does not already hold, or there is no news to paint: a
        # report saying what the page says is blessed silence, not provisional state.
        [
            "page",
            "report",
            str(d),
            "ag-wren",
            "state",
            "value=waiting",
            "text=rebasing onto main",
        ],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    expect(wren.locator(".lf-doing")).to_have_text("rebasing onto main")
    expect(wren).not_to_have_attribute("doing", "rebasing onto main")
    expect(wren).to_have_attribute("data-lf-reported", "1")
    expect(wren.locator(".lf-heard")).to_have_text("last heard just now")
    expect(wren.locator(".lf-cold")).to_have_count(0)

    stale_report(d, "ag-wren", "still rebasing", 3)
    told(page)
    expect(wren.locator(".lf-doing")).to_have_text("still rebasing")
    expect(wren.locator(".lf-heard")).to_have_text("last heard 3h ago")
    expect(wren.locator(".lf-cold")).to_have_text("quiet")

    # The same silence against no claim of work says nothing beyond its own age.
    stale_report(d, "ag-finch", "nothing", 3, state="idle")
    told(page)
    expect(finch.locator(".lf-doing")).to_have_text("nothing")
    expect(finch.locator(".lf-heard")).to_have_text("last heard 3h ago")
    expect(finch.locator(".lf-cold")).to_have_count(0)

    # And it survives the version that answers the report, which is the case the whole
    # line exists for and the one an earlier build could never reach. Publishing absorbs
    # a report by id, so a roster reading reports in force blanked every row at every
    # publish — and the user most needs this exactly where that left nothing: a worker
    # that claimed work, had the claim written into the document, and then died. The
    # provisional mark goes, because the document speaks again; the log's memory of who
    # last said anything does not, because no version can speak for that.
    stamp_page(d, ROSTER_PAGE, "absorbing")
    wait_for_revision(page, 2)
    wren = page.locator("#ag-wren")
    expect(wren).not_to_have_attribute("data-lf-reported", "1")
    expect(wren.locator(".lf-doing")).to_have_count(0)
    expect(wren.locator(".lf-heard")).to_have_text("last heard 3h ago")
    expect(wren.locator(".lf-cold")).to_have_text("quiet")


def test_the_report_feed_reads_reports_by_typed_target(browser, serve):
    """Worker reports reach widgets through one typed reading. The work the agent has
    in hand is no report: it is the workflows' Working stage and the tasks' starts."""
    page = open_page(browser, live_url(serve(ROSTER_PAGE)))
    d = serve.page_dir
    # Event ids and authored element ids belong to different identity spaces. Give
    # the thread and widget the same spelling so only the typed target can separate
    # their reports; a bare id or target lookup by store would merge them.
    thread = append_carried_log_record(
        d,
        {
            "id": "ag-wren",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "ag-wren"},
            "text": "Can you check this worker's mount price?",
        },
    )
    told(page)

    report = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "report",
            str(d),
            "ag-wren",
            "state",
            "value=working",
            "text=checking the mount prices",
        ],
    )
    assert report.exit_code == 0, report.output
    started = CliRunner().invoke(
        cli_model.cli,
        [
            "task",
            "start",
            str(d),
            thread["id"],
            "--text",
            "checking the user's question",
        ],
    )
    assert started.exit_code == 0, started.output
    told(page)

    reports = page.evaluate(
        "async () => (await window.__lfWidgetApi()).reportSequence()"
    )
    by_source = {report["source"]: report for report in reports}
    assert set(by_source) == {"report"}
    assert by_source["report"] == {
        "id": by_source["report"]["id"],
        "target": {"kind": "widget", "id": "ag-wren"},
        "source": "report",
        "action": "state",
        "detail": {"value": "working", "text": "checking the mount prices"},
        "text": "checking the mount prices",
        "ts": by_source["report"]["ts"],
        "revision": 1,
        "seq": by_source["report"]["seq"],
        "agent": "Claude",
        "session": by_source["report"]["session"],
        "disposition": "effective",
    }
    assert by_source["report"]["session"]
    targeted = page.evaluate(
        """async () => {
            const feed = await window.__lfWidgetApi();
            return {
                widget: feed.reportSequence(document.querySelector('#ag-wren')),
                thread: feed.reportSequence({kind: 'thread', id: 'ag-wren'}),
                bare: (() => {
                    try { feed.reportSequence('ag-wren'); }
                    catch (error) { return `${error.name}: ${error.message}`; }
                })(),
            };
        }"""
    )
    assert [report["source"] for report in targeted["widget"]] == ["report"]
    assert targeted["thread"] == []
    assert targeted["bare"].startswith("TypeError: report target must be")
    expect(page.locator("#ag-wren .lf-doing")).to_have_text("checking the mount prices")

    # A version note settles the report.
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": thread["id"],
            "revision": 1,
            "text": "The mount price is in the attached quote.",
        },
    )
    stamp_page(d, ROSTER_PAGE, "recorded")
    wait_for_revision(page, 2)

    reports = page.evaluate(
        "async () => (await window.__lfWidgetApi()).reportSequence()"
    )
    by_source = {report["source"]: report for report in reports}
    assert by_source["report"]["disposition"] == "settled"
    expect(page.locator("#ag-wren .lf-doing")).to_have_count(0)


@pytest.mark.parametrize("holding", ["defer", "preparation"])
def test_report_narration_and_coverage_wait_for_the_widgets_own_presentation(
    browser, serve, holding
):
    """Report prose, coverage, and clocks consume the widget's canonical proof.

    A local editing hold and an asynchronous preparation are distinct owners of
    completion. Each holds only its widget; report narration cannot jump ahead by
    inferring that the coordinate was committed because its DOM node still exists.
    """
    page = open_page(browser, serve(ROSTER_PAGE))
    d = serve.page_dir
    row = page.locator("#ag-wren")
    first = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "report",
            str(d),
            "ag-wren",
            "state",
            "value=working",
            "text=first report",
        ],
    )
    assert first.exit_code == 0, first.output
    told(page)
    expect(row.locator(".lf-doing")).to_have_text("first report")
    page.evaluate(
        """async holding => {
          const api = await window.__lfWidgetApi();
          const {clockValue} = await window.__lfWidgetApi();
          const {readApplicationPresentation} = await window.__lfCheckApi();
          const owner = document.getElementById('ag-wren');
          window.__proofClock = 0;
          window.__proofReads = [];
          customElements.define('lf-report-proof', class extends api.LeafElement {
            render() {
              if (!this.whenReady(() => api.reportsPresented(owner))) return api.noChange;
              clockValue(() => window.__proofClock);
              window.__proofReads.push(api.reportSequence(owner).map(report => report.text));
              return api.noChange;
            }
          });
          window.__proofWatching = document.createElement('lf-report-proof');
          document.body.append(window.__proofWatching);
          await window.__proofWatching.updateComplete;
          window.__proofTick = () => { window.__proofClock += 1; };
          window.__proofPending = () => {
            const proof = readApplicationPresentation();
            return api.reportSequence(owner).some(report => report.text === 'held report') &&
              proof.pending.some(region => region.startsWith('widget:ag-wren:')) &&
              !proof.pending.includes('projection:chrome');
          };
          // The watcher gets its first clock reading before the held publication.
          await Promise.resolve();
          const other = api.widgetController(document.getElementById('ag-finch'));
          other.present(new Promise(resolve => { window.__proofOtherResume = resolve; }));
          window.__proofOtherPending = () =>
            readApplicationPresentation().pending.includes('widget:ag-finch:preparation');
          const controller = api.widgetController(owner);
          if (holding === 'defer') {
            window.__proofResume = controller.defer();
          } else {
            let resolve;
            controller.present(new Promise(done => { resolve = done; }));
            window.__proofResume = resolve;
          }
        }""",
        holding,
    )
    if holding == "preparation":
        # A same-epoch reopen has no semantic notification. The next clock paint
        # must still check proof rather than bypassing its readiness guard.
        reads = page.evaluate("window.__proofReads.length")
        page.evaluate(
            "window.__proofWatching.requestUpdate(); window.__proofWatching.performUpdate()"
        )
        assert page.evaluate("window.__proofReads.length") == reads
        page.evaluate("window.__proofTick()")
        ticked(page)
        assert page.evaluate("window.__proofReads.length") == reads
    second = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "report",
            str(d),
            "ag-wren",
            "state",
            "value=idle",
            "text=held report",
        ],
    )
    assert second.exit_code == 0, second.output
    page.wait_for_function("window.__proofPending()")
    page.evaluate("window.__proofTick()")
    ticked(page)
    assert not page.evaluate(
        "window.__proofReads.some(read => read.includes('held report'))"
    )
    expect(row.locator(".lf-doing")).to_have_text("first report")
    expect(page.locator("body")).not_to_have_attribute("data-lf-applied", "2")
    if holding == "defer":
        expect(row).to_have_attribute("state", "working")
    page.evaluate("window.__proofResume()")
    expect(row).to_have_attribute("state", "idle")
    expect(row.locator(".lf-doing")).to_have_text("held report")
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "2")
    assert page.evaluate("window.__proofOtherPending()"), (
        "an unrelated widget's preparation must not block the report or coverage"
    )
    page.evaluate("window.__proofOtherResume()")


def test_a_worker_that_has_never_reported_dates_from_its_version(browser, serve):
    """The direction a freshness line must never fail in. A row nobody has reported on
    is not of unknown age: its words were asserted when the version landed, and are
    exactly that old. Rendering nothing there was the first build's answer, and it hides
    the case the user is most exposed to — a fleet published at six in the evening,
    every worker dead by seven, read at eight the next morning. Every row claims work,
    and with no report behind any of them there is no elapsed line to contradict it and
    no call-out: a dead fleet drawn exactly like a fresh one, on a page whose status's
    whole design is that a claim nobody revises must not be repeated as fact."""
    url = serve(ROSTER_PAGE)
    d = serve.page_dir
    page = open_page(browser, url)
    siskin = page.locator("#ag-siskin")
    expect(siskin.locator(".lf-heard")).to_have_text("last heard just now")
    expect(siskin.locator(".lf-cold")).to_have_count(0)

    backdate_note(d, 1, 3)
    told(page)
    expect(siskin.locator(".lf-heard")).to_have_text("last heard 3h ago")
    expect(siskin.locator(".lf-cold")).to_have_text("quiet")
    # An idle worker is not called out for the same silence: it claimed nothing.
    expect(page.locator("#ag-finch .lf-heard")).to_have_text("last heard 3h ago")
    expect(page.locator("#ag-finch .lf-cold")).to_have_count(0)


def test_a_rosters_clock_keeps_moving_when_the_server_stops_answering(browser, serve):
    """A clock advances held state even without a new state response."""
    page = open_page(browser, serve(ROSTER_PAGE))
    page.route("**/api/state*", refuse)
    page.clock.set_fixed_time(datetime.now().astimezone() + timedelta(hours=3))
    expect(page.locator("#ag-wren .lf-heard")).to_have_text("last heard 3h ago")
    expect(page.locator("#ag-wren .lf-cold")).to_have_text("quiet")


def test_a_rosters_row_survives_the_polls_that_keep_it_fresh(browser, serve):
    """A row is a thing the user is invited to select and point at, and it is also
    the one widget with a reason to touch itself every two seconds. Those pull against
    each other, and the first build lost: the clock re-rendered the whole row, so the
    words under a pointer were a different node on every poll — a selection collapsing
    mid-drag, focus dropped off the reference beside it, a click that straddles the
    swap landing on nothing. It is "Paint; don't wrap" reached by rebuilding instead of
    by wrapping, and it fails the same way: nothing errors, the page just stops taking
    the gesture.

    So the clock touches one text node and the structure is rebuilt only when a
    report moves that row. Asserted as node identity rather than as a selection, because
    identity is the property the rendering owes and a selection is one thing that rests
    on it."""
    url = serve(ROSTER_PAGE)
    d = serve.page_dir
    page = open_page(browser, url)
    page.evaluate(
        "() => { window.__kept = [...document.querySelectorAll('#ag-wren .lf-doing,"
        " #ag-wren .lf-branch, #ag-wren .lf-state')].map(e => e.firstChild); }"
    )
    sent = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "report",
            str(d),
            "ag-finch",
            "state",
            "value=idle",
            "text=picking up",
        ],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    ticked(page)
    # wren heard nothing in the read or the tick after it, so nothing of wren's may
    # have moved.
    assert page.evaluate(
        "() => window.__kept.every((n, i) => n === [...document.querySelectorAll("
        "'#ag-wren .lf-doing, #ag-wren .lf-branch, #ag-wren .lf-state')][i]?.firstChild)"
    )
    # And a report for this row does rebuild it, or the row would never move at all.
    sent = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "report",
            str(d),
            "ag-wren",
            "state",
            "value=working",
            "text=on to the baffles",
        ],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    expect(page.locator("#ag-wren .lf-doing")).to_have_text("on to the baffles")


def test_a_recounted_fraction_holds_the_width_it_had(browser, serve):
    """A number the page rewrites unasked must not resize as it does.

    The done-fraction is the page's most-moved quantity: a worker reports a leaf
    and the parent recounts, on a poll, with nothing the user did to account
    for the shift. It is apparatus, so it is set in the sans — and the sans gives
    each digit its own width where the serif carrying the prose gives them all
    one, which is why the figures are stated for the apparatus voice and not for
    the page. The chip is a filled pill, so its own box is what a user watches
    twitch; where apparatus leads something else, that something moves with it —
    a metric's delta sits directly after the value it follows.

    Measured across the recount rather than a redraw, per tests/AGENTS.md: the
    transition has to be one the figures actually decide. "1/2 done" to
    "2/2 done" stands 1.61px apart with proportional figures and identical with
    tabular, so deleting the declaration fails this. "0/3 done" to "3/3 done"
    would have been the vacuous choice — those two measure 0.03px apart either
    way, and the check would pass with the rule gone.
    """
    url = serve(REPORT_PAGE)
    d = serve.page_dir
    page = open_page(browser, url)
    # The fraction is the last chip its parent builds, after owner and when.
    fraction = page.locator("#t-feeders > .work-progress").last
    expect(fraction).to_have_text("1/2 done")
    before = fraction.bounding_box()["width"]

    sent = CliRunner().invoke(
        cli_model.cli,
        ["page", "report", str(d), "t-parser", "status", "value=done"],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    # The recount is the edge; the geometry is read once behind it.
    expect(fraction).to_have_text("2/2 done")
    after = fraction.bounding_box()["width"]

    assert abs(before - after) < 0.05, (
        f"the fraction resized as it recounted, {before}px to {after}px — a box "
        "the user was given no gesture to explain"
    )


def test_worktree_identity_does_not_follow_the_missing_evidence_placeholder(
    browser, serve
):
    source = leaf_page(
        "worktree identity",
        '<lf-test-roster id="team"><lf-test-worker id="worker" state="working">'
        '<strong>Worker</strong><lf-test-tree id="proof" source="atlas-worktrees">'
        "</lf-test-tree></lf-test-worker></lf-test-roster>",
    )
    url = serve(source)
    record = {
        "branch": "proof",
        "base": "main",
        "head": "abc123",
        "ahead": 1,
        "behind": 0,
        "additions": 3,
        "deletions": 1,
        "commits": 1,
        "tests": "passing",
        "observedAt": "2026-09-25T10:00:00-07:00",
    }
    data_model.cmd_data_set(serve.page_dir, "atlas-worktrees", {"proof": record})
    page = open_page(browser, url)
    datum = page.locator('#proof > [data-lf-datum="proof"]')
    seen = source_revision(serve.page_dir, "atlas-worktrees")
    anchor = {
        "section": "proof",
        "datum": "proof",
        "source": "atlas-worktrees",
        "source_revision": seen,
        "identity": "proof",
    }

    def status():
        return page.evaluate(
            """anchor => window.__lfCheckApi()
              .then(({resolveAnchor}) => resolveAnchor(anchor)?.status)""",
            anchor,
        )

    expect(datum).to_have_attribute("data-lf-identity", "proof")
    assert status() == "exact"
    data_model.cmd_data_set(serve.page_dir, "atlas-worktrees", {})
    expect(datum).not_to_have_attribute("data-lf-identity")
    assert status() == "outdated"
    data_model.cmd_data_set(
        serve.page_dir, "atlas-worktrees", {"proof": {**record, "head": "def456"}}
    )
    expect(datum).to_have_attribute("data-lf-identity", "proof")
    assert status() == "exact"


def test_native_worktree_disclosure_owns_keyboard_and_touch(browser, serve):
    source = leaf_page(
        "native evidence",
        '<lf-test-roster id="team"><lf-test-worker id="worker" state="working"><strong>Worker</strong><lf-test-tree id="proof" source="facts"></lf-test-tree></lf-test-worker></lf-test-roster>',
    )
    page = open_page(browser, serve(source))
    summary = page.locator("#proof summary")
    summary.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#proof details")).to_have_attribute("open", "")
    page.keyboard.press(" ")
    expect(page.locator("#proof details")).not_to_have_attribute("open")
    summary.click()
    expect(page.locator("#proof details")).to_have_attribute("open", "")


def test_command_goal_can_pause_after_an_ordinary_thread_started(browser, serve):
    """A normal note does not consume the goal's stronger pause door. The user
    can start a later held thread, whose root remains the one atomic hold fact."""
    page = open_page(browser, serve(COMMAND_HUB_EXAMPLE))
    d = serve.page_dir
    goal = page.locator("#goal-parser")
    seat = goal.locator(":scope > .lf-thread-seat")
    first = seat.locator(":scope > .lf-say")
    write(first.get_by_role("textbox"), "Keep parsing; this is only a note.")
    with sending(page, "the note"):
        first.get_by_role("button", name="Send", exact=True).click()

    expect(first).to_be_visible()
    write(first.get_by_role("textbox"), "Finish the hunk, then park.")
    with sending(page, "the held send"):
        first.get_by_role("button", name="Send & pause", exact=True).click()

    expect(goal).to_have_attribute("data-lf-held")
    roots = [
        event for event in events_model.read_events(d) if event["kind"] == "comment"
    ]
    assert [(event["text"], event.get("holds")) for event in roots] == [
        ("Keep parsing; this is only a note.", None),
        ("Finish the hunk, then park.", "goal-parser"),
    ]


def test_command_goal_thread_follows_its_declaration_not_talk(
    browser, serve, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    registry = json.loads((COMMAND_HUB_PACKAGE / "registry.json").read_text())
    task = registry["lf-test-task"]
    task["properties"]["consult"] = {"type": "boolean"}
    task["x-thread-seat"] = {
        "when": {"consult": [True]},
        "hold": "pause",
    }
    command = leaf_page(
        "custom goal",
        """<lf-test-plan id="hub">
  <lf-test-task id="goal" status="active" consult><strong>Custom goal</strong></lf-test-task>
</lf-test-plan>""",
    )
    url = serve(command, layer_registry={"lf-test-task": task})
    page = open_page(browser, url)
    seat = page.locator("#goal > .lf-thread-seat")
    expect(seat.get_by_role("textbox", name="Say something here")).to_be_visible()
    expect(seat.get_by_role("button", name="pause", exact=True)).to_be_visible()


@pytest.mark.parametrize(
    ("markup", "path", "leaf_id"),
    [
        (
            COMMAND_HUB_PAGE,
            [
                "One clean shadow week",
                "Replace the XML parser",
                "Declarations and entities",
                "CDATA edge cases",
            ],
            "parser-cdata",
        ),
        (
            REPORT_PAGE,
            ["Tasks", "Rebuild the feeders", "Fit squirrel baffles"],
            "t-parser",
        ),
    ],
)
def test_task_hierarchy_is_accessible_through_reports_and_revisions(
    browser, serve, markup, path, leaf_id
):
    """The listening reader gets the same parents as the visible task nesting.

    Read Chrome's native accessibility tree: Playwright's DOM-based name calculator
    does not yet read ariaLabelledByElements, although Chrome exposes those names to
    assistive technology. A report repaints row metadata; a revision changes titles.
    Neither may flatten the groups or retain the previous title as their name.
    """
    page = open_page(
        browser,
        live_url(serve(COMMAND_HUB_EXAMPLE if markup == COMMAND_HUB_PAGE else markup)),
    )
    session = page.context.new_cdp_session(page)

    def hierarchy(expected):
        nodes = session.send("Accessibility.getFullAXTree")["nodes"]
        by_id = {node["nodeId"]: node for node in nodes}
        groups = {
            node.get("name", {}).get("value"): node
            for node in nodes
            if node.get("role", {}).get("value") == "group"
        }
        assert all(name in groups for name in expected), groups.keys()
        for parent, child in pairwise(expected):
            ancestor = by_id[groups[child]["parentId"]]
            while ancestor.get("role", {}).get("value") != "group":
                ancestor = by_id[ancestor["parentId"]]
            assert ancestor["nodeId"] == groups[parent]["nodeId"]
        return groups

    hierarchy(path)
    sent = CliRunner().invoke(
        cli_model.cli,
        ["page", "report", str(serve.page_dir), leaf_id, "status", "value=done"],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    leaf = page.locator(f"#{leaf_id}")
    expect(leaf).to_have_attribute("status", "done")
    hierarchy(path)
    assert "done" in leaf.aria_snapshot()

    # Naming references the title node, so a revision's replacement title is what
    # the group says. The command root also reads its current label after patching.
    changed = markup.replace(path[-1], "Verify the final corpus")
    changed_path = [*path[:-1], "Verify the final corpus"]
    if markup == COMMAND_HUB_PAGE:
        changed = changed.replace(path[0], "Ready for the shadow week")
        changed_path[0] = "Ready for the shadow week"
    stamp_page(serve.page_dir, changed, "Clarify the plan's current titles")
    wait_for_revision(page, 2)
    groups = hierarchy(changed_path)
    assert path[-1] not in groups
    if markup == COMMAND_HUB_PAGE:
        assert path[0] not in groups
        summary = page.locator("#w-1 > details > summary")
        summary.click()
        expect(page.locator("#w-1 > details")).to_have_attribute("open", "")
        hierarchy(changed_path)


def test_atlas_input_is_trimmed_before_it_enters_the_record(browser, serve):
    """The replica cargo is visible in the real editor before Save. Trimming it
    changes the one payload that enters the log, leaves a receipt naming the input,
    and releases that input row without claiming the dependent work completed."""
    url = serve(COMMAND_HUB_EXAMPLE)
    d = serve.page_dir
    page = open_page(browser, url)
    draft = page.locator("#ledger-cargo")
    draft_control(page, "edit", "ledger-cargo").click()
    editor = draft.locator("leaf-text")
    write(
        editor,
        "ledger_id,customer_name,billing_email,amount\n7,Alice,a@example.test,42",
    )
    assert not [
        event
        for event in events_model.read_events(d)
        if event.get("widget") == "ledger-cargo"
    ]
    write(
        editor,
        "ledger_id,customer_name,billing_email,amount\n7,[redacted],[redacted],42",
    )
    with sending(page, "the saved edit"):
        draft_control(page, "save", "ledger-cargo").click()

    edit = next(
        event
        for event in reversed(events_model.read_events(d))
        if event.get("widget") == "ledger-cargo"
    )
    assert "Alice" not in edit["detail"]["value"]
    assert "a@example.test" not in edit["detail"]["value"]
    assert edit["detail"]["value"].count("[redacted]") == 2
    page.locator("#atlas-record .lf-activity-news").click()
    saved = page.locator("#atlas-record .lf-activity-row").first
    expect(saved).to_contain_text("Me edited")
    expect(saved.locator('a[href="#ledger-cargo"]')).to_have_count(1)
    expect(page.locator('[data-atlas-count="stopped"]')).to_have_text("4")
    expect(page.locator("#ledger-variance")).to_have_attribute("status", "planned")
