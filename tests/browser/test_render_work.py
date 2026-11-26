"""Public work projections keep task identity apart from page-owned dashboards."""

import pytest
from click.testing import CliRunner
from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    open_page,
    told,
)

from leaf.commands import cli as cli_model

pytestmark = pytest.mark.shifts_unsurveyed


def reading(page, scope):
    return page.evaluate(
        """async id => {
          const {readWork} = await window.__lfWidgetApi();
          const view = readWork(document.getElementById(id));
          return {done: view.done, leaves: view.leaves.map(row => row.element.id),
            stopped: view.stopped.map(row => row.element.id),
            goals: view.goals.map(row => [row.element.id, row.state, row.title]),
            progress: Object.fromEntries(view.goals.map(row =>
              [row.element.id, row.leaves.map(leaf => leaf.id)])),
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
            <lf-test-task id="leaf" label="Leaf work" status="active"><strong>Leaf work</strong></lf-test-task>
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
    assert initial["progress"] == {
        "area": ["leaf"],
        "leaf": ["leaf"],
        "other": ["other"],
    }
    assert reading(page, "inner")["leaves"] == ["private"]
    # A goal inside another role is still its goal's work, but not its child: the
    # goal that holds it becomes a leaf too.
    page.evaluate("""() => {
      const leaf = document.getElementById('leaf');
      const home = leaf.parentElement;
      document.getElementById('worker').append(leaf);
      window.__lfLeafHome = home;
    }""")
    moved = reading(page, "outer")
    assert moved["leaves"] == ["area", "leaf", "other"]
    assert moved["progress"]["area"] == ["leaf"]
    page.evaluate("() => window.__lfLeafHome.append(document.getElementById('leaf'))")
    assert reading(page, "outer") == initial
    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "report", str(serve.page_dir), "leaf", "status", "value=done"],
    )
    assert result.exit_code == 0, result.output
    told(page)
    assert reading(page, "outer")["done"] == 1
    assert ["leaf", "done", "Leaf work"] in reading(page, "outer")["goals"]
    # Any element of a scope reads the scope's work, and a goal outside every scope
    # reads the page's, which no scope's goals join.
    assert reading(page, "worker") == reading(page, "outer")
    page.evaluate(
        "() => document.getElementById('outer').after(document.getElementById('other'))"
    )
    assert reading(page, "other")["leaves"] == ["other"]


def test_a_page_owned_goal_joins_the_public_projection(browser, serve):
    schema = {
        "description": "A local milestone.",
        "attributes": {
            "properties": {
                "label": {"type": "string"},
                "phase": {"enum": ["blocked", "done"]},
            },
            "required": ["id", "phase"],
        },
        "content": "markup",
        "owners": ["lf-test-plan"],
        "verbs": {
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
    module = """import { LeafElement } from "/runtime/lib/leaf-element.js";
import { keeps } from "/runtime/lib/keeps.js";
customElements.define("lf-project-milestone", class extends LeafElement {
  render() { keeps(this, "phase", this.state.phase.value); }
});"""
    source = leaf_page(
        "local work role",
        '<lf-test-plan id="plan"><lf-project-milestone id="local" label="Local milestone" phase="blocked"><strong>Local milestone</strong></lf-project-milestone></lf-test-plan>',
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
