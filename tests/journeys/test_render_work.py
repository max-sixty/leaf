"""Public work projections keep task identity apart from page-owned dashboards."""

import json
import re
from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner
from leaf import cli as cli_model
from leaf import data as data_model
from leaf.event_log import read_events
from leaf.passages import page_passages, section_span
from leaf.render_checks import wait_until_ready
from leaf.structure import SourceDocument
from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import COMMAND_HUB_EXAMPLE, live_url
from render_harness import (
    open_page,
    page_registry,
    refuse,
    sending,
    stamp_page,
    ticked,
    told,
    wait_for_revision,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.watch_shifts
def test_atlas_report_waits_behind_a_stationary_refresh_control(browser, serve):
    page = open_page(browser, live_url(serve(COMMAND_HUB_EXAMPLE)))
    # The status is part of the summary's hit area, including at phone widths.
    # A native form output here consumes activation instead of opening details.
    page.locator("#w-1 .atlas-worker-state").click()
    expect(page.locator("#w-1 > details")).to_have_attribute("open", "")
    expect(page.locator("#ground-corpus > .atlas-task-state")).to_have_text("done")
    report = page.locator("#w-1 .atlas-worker-report")
    before = report.inner_text()
    report.scroll_into_view_if_needed()
    box = report.bounding_box()
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "report",
            str(serve.page_dir),
            "w-1",
            "state",
            "value=working",
            "text=" + "Expanded report. " * 50,
        ],
    )
    assert result.exit_code == 0, result.output
    told(page)
    expect(report).to_have_text(before)
    after = report.bounding_box()
    assert abs(after["y"] - box["y"]) < 1
    latest = page.get_by_role("button", name="Show latest", exact=True)
    expect(latest).to_be_enabled()
    latest.click()
    expect(report).to_contain_text("Expanded report.")
    expect(latest).to_be_disabled()
    heard = report.locator("time")
    event = next(
        row
        for row in reversed(read_events(serve.page_dir))
        if row["kind"] == "report" and row["widget"] == "w-1"
    )
    expect(heard).to_have_attribute("datetime", event["ts"])
    expect(heard).to_have_text("just now")
    tree = page.locator("#tree-w-1")
    tree.locator("summary").click()
    observed = tree.locator("time")
    expect(observed).to_have_attribute("datetime", "2026-08-21T11:42:00-07:00")
    expect(observed).to_have_text(re.compile(r"\d+d ago"))
    # A new datum is held while its evidence is being read. Revealing it must
    # also replace the shared clock subscription, even when the old age would
    # otherwise stay unchanged for another day.
    observed.scroll_into_view_if_needed()
    worktrees = json.loads(COMMAND_HUB_EXAMPLE.with_suffix(".data.json").read_text())[
        "atlas-worktrees"
    ]
    refreshed_at = datetime.now().astimezone().isoformat(timespec="seconds")
    worktrees["tree-w-1"]["observedAt"] = refreshed_at
    data_model.cmd_data_set(serve.page_dir, "atlas-worktrees", worktrees)
    told(page)
    expect(observed).to_have_text(re.compile(r"\d+d ago"))
    expect(latest).to_be_enabled()
    latest.click()
    expect(observed).to_have_text("just now")
    expect(observed).to_have_attribute("datetime", refreshed_at)

    # Finish the input rendering before advancing only the clock. Both newly
    # revealed ages advance while the native details stays open.
    page.evaluate("() => window.lfShiftsJudged()")
    page.route("**/api/state*", refuse)
    page.clock.set_fixed_time(datetime.now().astimezone() + timedelta(minutes=5))
    ticked(page)
    ticked(page)
    expect(heard).to_have_text("5m ago")
    expect(observed).to_have_text("5m ago")
    expect(tree.locator("details")).to_have_attribute("open", "")
    expect(heard).to_have_attribute("datetime", event["ts"])
    expect(observed).to_have_attribute("datetime", refreshed_at)
    # Also expose the report's ending during an idle age change: punctuation
    # after a variable-width age would move on screen without a new gesture.
    heard.scroll_into_view_if_needed()
    page.evaluate("() => window.lfShiftsJudged()")
    page.clock.set_fixed_time(datetime.now().astimezone() + timedelta(minutes=10))
    ticked(page)
    ticked(page)
    expect(heard).to_have_text("10m ago")
    expect(observed).to_have_text("10m ago")


@pytest.mark.parametrize("owner", ["atlas", "private"])
def test_work_status_is_a_generated_browser_passage(browser, serve, owner):
    """Mutable generated status has exact browser anchors without authored context."""
    if owner == "atlas":
        plan, task = "lf-atlas-plan", "lf-atlas-task"
        package = COMMAND_HUB_EXAMPLE.parent / "command-hub.page"
        packages = (package, "diff")
    else:
        plan, task, packages = "lf-test-plan", "lf-test-task", None
    source = leaf_page(
        "Status words",
        f'<{plan} id="plan"><{task} id="goal" status="blocked">'
        f"<strong>Current goal</strong> Waiting on brackets.</{task}></{plan}>",
    )
    page = open_page(browser, live_url(serve(source, packages=packages)))

    def check_generated_status(markup, status, *, reported=False):
        registry = page_registry(page)
        file_reading = page_passages(SourceDocument(markup), registry)
        lo, hi = section_span(file_reading.owner, "goal")
        file_words = file_reading.text[lo:hi]
        assert status not in file_words, file_words
        line = page.locator('#goal > [data-lf-said="status"]')
        expect(line).to_have_count(1)
        expect(line).to_have_text(status)
        assert page.locator("#goal").aria_snapshot().count(status) == 1
        if reported:
            assert status not in page.locator("#goal > .lf-quiet").inner_text()
        else:
            expect(page.locator("#goal > .lf-quiet")).to_have_count(0)
        captured = line.evaluate("""async el => {
          const {says} = await window.__lfRuntimeImport('/runtime/passages.js');
          const {anchorForRange, resolveAnchor} = await window.__lfRuntimeImport('/runtime/anchor-resolution.js');
          const range = document.createRange(); range.selectNodeContents(el);
          const anchor = anchorForRange(range);
          const resolved = resolveAnchor(anchor);
          return {words: says(el), anchor, kind: resolved?.kind, exact: resolved?.exact};
        }""")
        assert captured == {
            "words": status,
            "anchor": {"section": "goal", "quote": status},
            "kind": "passage",
            "exact": True,
        }

    def comment_on_status(status):
        page.locator('#goal > [data-lf-said="status"]').evaluate("""el => {
          const range = document.createRange(); range.selectNodeContents(el);
          const selection = getSelection(); selection.removeAllRanges();
          selection.addRange(range);
          document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        }""")
        page.keyboard.press("c")
        write(page.locator(".lf-composer leaf-text"), f"Discuss {status} status")
        with sending(page, f"the comment on generated {status} status"):
            page.keyboard.press("ControlOrMeta+Enter")
        [comment] = [
            event
            for event in read_events(serve.page_dir)
            if event["kind"] == "comment"
            and event["text"] == f"Discuss {status} status"
        ]
        assert comment["anchor"] == {"section": "goal", "quote": status}
        page.keyboard.press("Escape")
        return comment

    def check_thread_quotes(comments):
        # Resolve the admitted historical coordinates, not a newly recaptured range.
        resolved = page.evaluate(
            """async anchors => {
          const {resolveAnchor} = await window.__lfRuntimeImport('/runtime/anchor-resolution.js');
          return anchors.map(anchor => {
            const found = resolveAnchor(anchor);
            return {quote: anchor.quote, exact: found?.exact ?? false};
          });
        }""",
            [comment["anchor"] for comment in comments],
        )
        assert resolved == [
            {
                "quote": comment["anchor"]["quote"],
                "exact": comment["anchor"]["quote"] == "active",
            }
            for comment in comments
        ]

    check_generated_status(source, "blocked")
    blocked = comment_on_status("blocked")
    reported = CliRunner().invoke(
        cli_model.cli,
        ["page", "report", str(serve.page_dir), "goal", "status", "value=active"],
    )
    assert reported.exit_code == 0, reported.output
    told(page)
    check_generated_status(source, "active", reported=True)
    active = comment_on_status("active")
    check_thread_quotes([blocked, active])
    revised = source.replace('status="blocked"', 'status="active"')
    revision = stamp_page(serve.page_dir, revised, "The goal is active")
    wait_for_revision(page, revision["revision"])
    check_generated_status(revised, "active")
    check_thread_quotes([blocked, active])
    page.reload()
    wait_until_ready(page)
    check_generated_status(revised, "active")
    check_thread_quotes([blocked, active])
    page.locator(".lf-threads-toggle").click()
    quotes = page.locator(".lf-thread-panel .lf-quote")
    expect(quotes).to_have_count(2)
    expect(page.locator(".lf-thread-panel .lf-quote.detached")).to_have_text(
        "“blocked”"
    )
    expect(page.locator(".lf-thread-panel .lf-quote:not(.detached)")).to_have_text(
        "“active”"
    )
    assert [
        event for event in read_events(serve.page_dir) if event["kind"] == "comment"
    ] == [blocked, active]
    assert not [
        event for event in read_events(serve.page_dir) if event["kind"] == "reanchor"
    ]
