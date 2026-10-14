"""Public work projections keep task identity apart from page-owned dashboards."""

import pytest
from click.testing import CliRunner
from leaf import cli as cli_model
from model_folds import leaf_page
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    open_page,
    told,
)

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
    module = """import {keeps, once, widgetController} from "/runtime/widget-api.js";
customElements.define("lf-project-milestone", class extends HTMLElement {
  #controller = widgetController(this);
  connectedCallback() { if (once(this)) this.#controller.subscribe(() => {}); }
  renderState(state) { keeps(this, "phase", state.phase.value); }
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
