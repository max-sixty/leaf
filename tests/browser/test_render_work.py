"""Public work projections keep task identity apart from page-owned dashboards."""

import pytest
from click.testing import CliRunner
from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import COMMAND_HUB_EXAMPLE, live_url
from render_harness import (
    open_page,
    page_registry,
    sending,
    stamp_page,
    told,
    wait_for_revision,
    write,
)

from browser.threads import open_panel_thread
from leaf import cli as cli_model
from leaf.event_log import read_events
from leaf.passages import page_passages, section_span
from leaf.render_checks import wait_until_ready
from leaf.structure import SourceDocument

pytestmark = pytest.mark.shifts_unsurveyed


def reading(page, scope):
    return page.evaluate(
        """async id => {
          const {readWork} = await window.__lfWidgetApi();
          const view = readWork(document.getElementById(id));
          return {done: view.done, leaves: view.leaves.map(row => row.element.id),
            stopped: view.stopped.map(row => row.element.id),
            goals: view.goals.map(row => [row.element.id, row.state, row.title]),
            workers: view.workers.map(row => ({id: row.element.id, state: row.state,
              remit: row.remit?.id, assignment: row.assignment?.id ?? null}))};
        }""",
        scope,
    )


def test_public_work_roles_preserve_scope_remit_and_reports(browser, serve):
    source = leaf_page(
        "independent work",
        """<lf-test-plan id="outer" label="Outer work">
          <lf-test-task id="area" status="active"><strong>Area</strong>
            <lf-test-task id="leaf" status="active"><strong>Leaf work</strong></lf-test-task>
            <lf-test-worker id="worker" state="working" on="leaf"><strong>Worker</strong></lf-test-worker>
            <lf-test-plan id="inner" label="Inner work">
              <lf-test-task id="private" status="done"><strong>Private work</strong></lf-test-task>
            </lf-test-plan>
          </lf-test-task>
          <lf-test-task id="other" status="blocked"><strong>Other work</strong></lf-test-task>
        </lf-test-plan>""",
    )
    page = open_page(browser, live_url(serve(source)))
    initial = reading(page, "outer")
    assert initial["leaves"] == ["leaf", "other"]
    assert initial["stopped"] == ["other"]
    expect(page.locator("#other > .work-state")).to_have_text("blocked")
    expect(page.locator("#other > .lf-quiet")).to_have_count(0)
    assert initial["workers"] == [
        {"id": "worker", "state": "working", "remit": "area", "assignment": "leaf"}
    ]
    # A layout wrapper carries no task or worker meaning. The public projection
    # follows declared ancestry, retaining the same assignments and progress.
    page.evaluate("""() => {
      for (const id of ['leaf', 'worker']) {
        const node = document.getElementById(id);
        const section = document.createElement('section');
        node.before(section);
        section.append(node);
      }
    }""")
    assert reading(page, "outer") == initial
    assert reading(page, "inner")["leaves"] == ["private"]
    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "report", str(serve.page_dir), "leaf", "status", "value=done"],
    )
    assert result.exit_code == 0, result.output
    told(page)
    assert reading(page, "outer")["done"] == 1
    assert ["leaf", "done", "Leaf work"] in reading(page, "outer")["goals"]


def test_a_page_owned_goal_joins_the_public_projection(browser, serve):
    schema = {
        "description": "A local milestone.",
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "phase": {"enum": ["blocked", "done"]},
            "overruled": {"type": "boolean"},
        },
        "required": ["id", "phase"],
        "additionalProperties": False,
        "x-content": "markup",
        "x-owners": ["lf-test-plan"],
        "x-upgrade": True,
        "x-state": {
            "phase": {
                "writer": "agent",
                "unit": "widget",
                "record": {"kind": "value", "attr": "phase"},
            }
        },
    }
    declarations = {
        "lf-project-milestone": schema,
        "$work": {
            "widgets": {
                "lf-project-milestone": {
                    "role": "goal",
                    "state": "phase",
                    "done": ["done"],
                    "stopped": ["blocked"],
                }
            }
        },
    }
    module = """import {LeafElement, keeps} from "/runtime/widget-api.js";
customElements.define("lf-project-milestone", class extends LeafElement {
  render() { keeps(this, "phase", this.state.phase.value); }
});"""
    source = leaf_page(
        "local work role",
        '<lf-test-plan id="plan"><lf-project-milestone id="local" phase="blocked"><strong>Local milestone</strong></lf-project-milestone></lf-test-plan>',
    )
    page = open_page(
        browser,
        live_url(
            serve(
                source,
                layer_registry=declarations,
                layer_widgets={"lf-project-milestone.js": module},
            )
        ),
    )
    view = reading(page, "plan")
    assert view["stopped"] == ["local"]
    assert view["goals"] == [["local", "blocked", "Local milestone"]]


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
          const {says} = await window.__lfWidgetApi();
          const {anchorForRange, resolveAnchor} = await window.__lfCheckApi();
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
          const {resolveAnchor} = await window.__lfCheckApi();
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
    # Each thread's view quotes what it was about, the one whose words the revision
    # took away detached.
    for comment, said, detached in (
        (blocked, "“blocked”", True),
        (active, "“active”", False),
    ):
        quote = open_panel_thread(page, comment["id"]).locator(".lf-quote")
        expect(quote).to_have_text(said)
        assert ("detached" in quote.get_attribute("class").split()) is detached
    assert [
        event for event in read_events(serve.page_dir) if event["kind"] == "comment"
    ] == [blocked, active]
    assert not [
        event for event in read_events(serve.page_dir) if event["kind"] == "reanchor"
    ]
