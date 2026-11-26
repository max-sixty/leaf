"""Live samples a page or an agent's reply runs: full view and its Tab walk, and reading
keys passing from a sample to its page."""

import pytest
from click.testing import CliRunner
from interact_support import response_reference
from playwright.sync_api import expect
from render_cases_interaction import panel_comment
from render_harness import (
    Traffic,
    leaf_page,
    open_page,
    sending,
    take_browser_errors,
)

from browser.threads import open_panel_thread
from leaf.commands import cli as cli_model
from leaf.log import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


# The focus ring's colour, as the page computes it.
RING_INK = """() => {
  const probe = document.body.appendChild(document.createElement("i"));
  probe.style.color = "var(--lf-ok)";
  const color = getComputedStyle(probe).color;
  probe.remove();
  return color;
}"""


REPLY_SAMPLE = """<lf-sample id="reply-practice" label="Practice in a reply">
  <template id="reply-practice-source" data-sample>
    <h1 id="reply-child-heading">Practice from a reply</h1>
    <lf-group id="reply-child-ask" label="Which approach?"><h2 id="reply-child-ask-h">Which approach?</h2>
      <lf-options id="reply-child-options">
        <lf-option id="reply-child-a">First approach</lf-option>
        <lf-option id="reply-child-b">Second approach</lf-option>
      </lf-options>
    </lf-group>
  </template>
</lf-sample>"""


def test_an_agent_reply_runs_its_live_sample_in_the_thread(browser, serve):
    """A live sample an agent posts in a reply is a page the user operates in the
    thread: its template is the message's, and its gestures reach only its own log."""
    url = serve(leaf_page("Reply host", '<h1 id="host">Session store</h1>'))
    question = panel_comment(serve.page_dir, "What would the alternative look like?")
    replied = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(serve.page_dir, question),
            "--title",
            "Alternative sample",
            "--text",
            "Try it here:" + "\n\n" + (REPLY_SAMPLE),
        ],
    )
    assert replied.exit_code == 0, replied.output
    page = open_page(browser, url)
    sample = open_panel_thread(page, question).locator("#reply-practice")
    sample.evaluate("async sample => await sample.ready")
    child = sample.locator("iframe").element_handle().content_frame()
    child.lf_traffic = Traffic(child)
    expect(child.locator("#reply-child-heading")).to_have_text("Practice from a reply")
    with sending(child, "the sample choice"):
        child.locator("#reply-child-b .lf-pick").click()
    expect(child.locator("#reply-child-b .lf-pick")).to_have_attribute(
        "aria-checked", "true"
    )
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert take_browser_errors(page) == []


def test_inline_sample_choices_use_parent_state_and_undo(browser, serve):
    """Interactive content is the page's; a quoted sibling still takes no input."""
    from render_harness import undo

    page = open_page(
        browser,
        serve(
            leaf_page(
                "Inline samples",
                """
      <h1>Delivery</h1>
      <lf-sample id="working" interactive label="Working choices">
        <lf-options id="delivery">
          <lf-option id="standard">Standard</lf-option>
          <lf-option id="express">Express</lf-option>
        </lf-options>
      </lf-sample>
      <lf-sample id="quoted" label="Quoted choices">
        <lf-options id="quoted-delivery">
          <lf-option id="quoted-standard">Standard</lf-option>
        </lf-options>
      </lf-sample>
    """,
            )
        ),
    )
    sample = page.locator("#working")
    # A working sample wears no note; a quoted one says "quoted".
    note = "sample => getComputedStyle(sample, '::before').content"
    assert sample.evaluate(note) == "none"
    assert page.locator("#quoted").evaluate(note) == '"quoted"'
    expect(sample.locator("iframe")).to_have_count(0)
    expect(page.locator("#quoted").get_by_role("checkbox")).to_have_count(0)
    choice = sample.locator("#express").get_by_role("checkbox")
    with sending(page, "inline choice"):
        choice.click()
    expect(choice).to_have_attribute("aria-checked", "true")
    assert any(
        event.get("kind") == "action" and event.get("widget") == "delivery"
        for event in events_model.read_events(serve.page_dir)
    )
    undo(page)
    expect(choice).to_have_attribute("aria-checked", "false")
