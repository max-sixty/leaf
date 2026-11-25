"""Worker reports, rosters, worktree evidence, version comparisons and the command hub's
goals and tasks, as the live page shows them."""

import re
from datetime import datetime, timedelta
from itertools import pairwise

import pytest
from click.testing import CliRunner
from interact_support import (
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
    comparison_view,
    draft_control,
    holding,
    leaf_page,
    open_page,
    panel_field,
    panel_menu,
    press_draft_control,
    refuse,
    sending,
    stamp_page,
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
    attribute moves, and Page Map identifies a
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
    # Nothing waits on the user.
    expect(page.locator(".lf-fp-leaf")).to_have_attribute(
        "aria-label", re.compile(r"^Page menu · ")
    )

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
    expect(page.locator(".lf-fp-leaf")).to_have_attribute(
        "aria-label", re.compile(r"^Page menu · ")
    )

    # A second report supersedes the first: absolute values fold.
    sent = CliRunner().invoke(
        cli_model.cli,
        ["page", "report", str(d), "t-parser", "status", "value=done"],
    )
    assert sent.exit_code == 0, sent.output
    told(page)
    expect(task).to_have_attribute("status", "done")
    said = task.aria_snapshot()
    assert "done" in said and "review" not in said, said
    expect(page.locator(".lf-fp-leaf")).to_have_attribute(
        "aria-label", re.compile(r"^Page menu · ")
    )

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

    page.route(comparison_view, hold_first_view)
    try:
        with page.expect_request(lambda request: comparison_view(request.url)):
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

        with page.expect_request(lambda request: comparison_view(request.url)):
            held[0][0].fulfill(response=held[0][1])
            held[0][2] = True
        holding(page, requests, 2, "the retried comparison view")
        assert len(requests) >= 2, "the stale comparison view was not retried"
        expect(page.locator("#new-copy")).to_have_class(re.compile(r"lf-ins-block"))
        expect(page.locator("#t-parser")).not_to_have_class(re.compile(r"lf-ins-block"))
        versions = panel_menu(page, "versions")
        expect(versions.locator(".lf-fp-version[data-lf-current]")).to_contain_text(
            "v2"
        )
        expect(
            versions.get_by_role("button", name=re.compile(r"\bCompare with v1\b"))
        ).to_have_attribute("aria-pressed", "true")
        page.keyboard.press("Escape")
    finally:
        if held and not held[0][2]:
            held[0][0].fulfill(response=held[0][1])
        page.unroute(comparison_view)


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
    """The half of a roster no version can write down. The report in force, the
    worker's `state`, says what each worker is doing; only the log knows when it last
    said so, and a page that keeps a fleet is at its least trustworthy exactly when the
    user has been away longest. So the row renders elapsed time from the newest report
    row in the page's history, which the server sends again on every poll.

    Then the case the line exists for: a claim of work nobody has refreshed. The
    fixture calls it out in words rather than in the tint alone, and only against a
    claim — an idle worker that has said nothing all day is idle, which is what it said.

    The direction a freshness line must never fail in: a row nobody has reported on is
    not of unknown age. Its words were asserted when the version landed, and are exactly
    that old. Rendering nothing there was the first build's answer, and it hides the case
    the user is most exposed to — a fleet published at six in the evening, every worker
    dead by seven, read at eight the next morning: a dead fleet drawn exactly like a
    fresh one, on a page whose status's whole design is that a claim nobody revises must
    not be repeated as fact. And the clock advances the age even with no new state
    response."""
    url = serve(ROSTER_PAGE)
    d = serve.page_dir
    page = open_page(browser, live_url(url))
    wren, finch = page.locator("#ag-wren"), page.locator("#ag-finch")
    siskin = page.locator("#ag-siskin")
    # Before any worker has spoken, the row dates from the version that asserted it —
    # not from nothing, which would leave a fleet dead since last night reading exactly
    # like one published a minute ago.
    expect(wren.locator(".lf-heard")).to_contain_text("last heard")
    # The state is a word this module writes rather than paint the runtime speaks, so
    # a user listening gets it from the row itself.
    assert "working" in wren.aria_snapshot()
    expect(siskin.locator(".lf-heard")).to_have_text("last heard just now")
    expect(siskin.locator(".lf-cold")).to_have_count(0)

    backdate_note(d, 1, 3)
    told(page)
    expect(siskin.locator(".lf-heard")).to_have_text("last heard 3h ago")
    expect(siskin.locator(".lf-cold")).to_have_text("quiet")
    # An idle worker is not called out for the same silence: it claimed nothing.
    expect(finch.locator(".lf-heard")).to_have_text("last heard 3h ago")
    expect(finch.locator(".lf-cold")).to_have_count(0)

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
    expect(siskin.locator(".lf-cold")).to_have_count(0)

    page.route("**/api/state*", refuse)
    page.clock.set_fixed_time(datetime.now().astimezone() + timedelta(hours=3))
    expect(wren.locator(".lf-heard")).to_have_text("last heard 6h ago")


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


def test_command_goal_can_pause_after_an_ordinary_thread_started(browser, serve):
    """A normal note does not consume the goal's stronger pause door. The user
    can start a later held thread, whose root remains the one atomic hold fact."""
    page = open_page(browser, serve(COMMAND_HUB_EXAMPLE))
    d = serve.page_dir
    goal = page.locator("#goal-parser")
    comment = goal.locator(":scope > .atlas-task-comment")
    seat = goal.locator(":scope > .atlas-task-threads")
    box = seat.locator(".lf-fab-input")
    comment.click()
    write(box, "Keep parsing; this is only a note.")
    with sending(page, "the note"):
        page.keyboard.press("Enter")

    # The box gave way to the note's thread, and the row offers it again.
    comment.click()
    write(box, "Finish the hunk, then park.")
    with sending(page, "the held send"):
        seat.get_by_role("button", name="Send & pause", exact=True).click()

    roots = [
        event for event in events_model.read_events(d) if event["kind"] == "comment"
    ]
    assert [(event["text"], event.get("holds")) for event in roots] == [
        ("Keep parsing; this is only a note.", None),
        ("Finish the hunk, then park.", "goal-parser"),
    ]


def test_task_hierarchy_is_accessible_through_reports_and_revisions(browser, serve):
    """The listening reader gets the same parents as the visible task nesting.

    Read Chrome's native accessibility tree: Playwright's DOM-based name calculator
    does not yet read ariaLabelledByElements, although Chrome exposes those names to
    assistive technology. A report repaints row metadata; a revision changes titles.
    Neither may flatten the groups or retain the previous title as their name.
    """
    path = [
        "One clean shadow week",
        "Replace the XML parser",
        "Declarations and entities",
        "CDATA edge cases",
    ]
    leaf_id = "parser-cdata"
    page = open_page(browser, live_url(serve(COMMAND_HUB_EXAMPLE)))
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
    changed = COMMAND_HUB_PAGE.replace(path[-1], "Verify the final corpus").replace(
        path[0], "Ready for the shadow week"
    )
    changed_path = ["Ready for the shadow week", *path[1:-1], "Verify the final corpus"]
    stamp_page(serve.page_dir, changed, "Clarify the plan's current titles")
    wait_for_revision(page, 2)
    groups = hierarchy(changed_path)
    assert path[-1] not in groups
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
        press_draft_control(page, "save", "ledger-cargo")

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
