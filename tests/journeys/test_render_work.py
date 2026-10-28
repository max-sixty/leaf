"""Public work projections keep task identity apart from page-owned dashboards."""

import json
import re
from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner
from playwright.sync_api import expect
from render_cases_interaction import COMMAND_HUB_EXAMPLE, live_url
from render_harness import (
    open_page,
    refuse,
    ticked,
    told,
)

from leaf import cli as cli_model
from leaf import data as data_model
from leaf.event_log import read_events

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
