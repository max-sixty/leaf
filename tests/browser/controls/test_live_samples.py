"""Live samples a page or an agent's reply runs: full view and its Tab walk, and reading
keys passing from a sample to its page."""

import pytest
from click.testing import CliRunner
from interact_support import response_reference
from playwright.sync_api import expect
from render_cases_interaction import panel_comment
from render_cases_layout import current_location_ring
from render_harness import (
    Traffic,
    leaf_page,
    open_page,
    rendered,
    resized,
    sending,
    take_browser_errors,
)

from browser.controls import (
    LIVE_SAMPLES_PAGE,
)
from browser.threads import open_panel_thread
from leaf import cli as cli_model
from leaf import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


# The focus ring's colour, as the page computes it.
ACCENT = """() => {
  const probe = document.body.appendChild(document.createElement("i"));
  probe.style.color = "var(--accent)";
  const color = getComputedStyle(probe).color;
  probe.remove();
  return color;
}"""


def test_the_gutter_shows_while_keys_go_to_the_sample(browser, serve):
    """A press into the sample's page takes the user's keys there as a Tab does, though
    the containing page hears no focus event, and the gutter says so until they leave.
    Only the Tab rings the frame, as it would any control."""
    page = open_page(browser, serve(LIVE_SAMPLES_PAGE))
    sample = page.locator("#first-practice")
    sample.evaluate("async sample => { await sample.ready; }")
    gutter = sample.locator(".lf-sample-exhibit")
    resting = gutter.evaluate("el => getComputedStyle(el).borderLeftColor")
    accent = page.evaluate(ACCENT)
    assert resting != accent
    frame = sample.locator("iframe")
    child = frame.element_handle().content_frame()

    child.locator("#child-heading").click()
    expect(gutter).to_have_css("border-left-color", accent)
    rendered(page)
    assert current_location_ring(page) is None
    page.locator("#host-heading").click()
    expect(gutter).to_have_css("border-left-color", resting)

    sample.get_by_role("button", name="Full view", exact=True).focus()
    page.keyboard.press("Tab")
    expect(gutter).to_have_css("border-left-color", accent)
    rendered(page)
    assert current_location_ring(page)
    child.locator("#child-heading").click()
    rendered(page)
    assert current_location_ring(page) is None
    expect(gutter).to_have_css("border-left-color", accent)
    page.keyboard.press("Tab")
    rendered(page)
    assert current_location_ring(page)
    page.keyboard.press("Shift+Tab")
    expect(sample.get_by_role("button", name="Full view", exact=True)).to_be_focused()
    expect(gutter).to_have_css("border-left-color", resting)


def test_tab_walks_into_and_out_of_a_full_view_sample(browser, serve):
    """Full view is modal and holds its frame, and Tab is the browser's there: it walks
    into the child's controls, on out of the frame, and round to the view's own controls,
    never onto the page beneath."""
    page = open_page(browser, serve(LIVE_SAMPLES_PAGE))
    sample = page.locator("#first-practice")
    frame = sample.locator("iframe")
    child = frame.element_handle().content_frame()
    gutter = sample.locator(".lf-sample-exhibit")
    accent = page.evaluate(ACCENT)
    sample.get_by_role("button", name="Full view", exact=True).click()
    view = sample.locator("dialog.lf-sample-view")
    expect(
        sample.get_by_role("button", name="Return to page", exact=True)
    ).to_be_focused()

    # Where focus stands in the containing page: in the view, on its frame, or out at
    # the browser's own interface.
    current_location = """view => {
      let at = document.activeElement;
      while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
      if (at === document.body) return "browser";
      if (!view.contains(at)) return "page";
      return at.localName === "iframe" ? "frame" : "view";
    }"""
    entered = left = False
    for _ in range(40):
        page.keyboard.press("Tab")
        at = view.evaluate(current_location)
        assert at != "page", "Tab left Full view for the page beneath"
        if at == "frame" and child.evaluate("() => document.hasFocus()"):
            expect(gutter).to_have_css("border-left-color", accent)
            rendered(page)
            assert current_location_ring(page)
        entered |= at == "frame" and child.evaluate("() => document.hasFocus()")
        if entered and at == "view":
            left = True
            break
    assert entered, "Tab never entered the sample's own page"
    assert left, "Tab never came back out of the sample to the view's controls"

    # Back on the page, Tab past the child's last stop goes on to the page's next stop.
    page.keyboard.press("Escape")
    expect(sample.get_by_role("button", name="Full view", exact=True)).to_be_focused()
    child.evaluate(
        """async () => {
          const { tabStops } = await window.__lfCheckApi();
          tabStops(document.body).at(-1).focus();
        }"""
    )
    expect(frame).to_be_focused()
    page.keyboard.press("Tab")
    expect(frame).not_to_be_focused()


REPLY_SAMPLE = """<lf-sample id="reply-practice" label="Practice in a reply">
  <template id="reply-practice-source" data-sample>
    <h1 id="reply-child-heading">Practice from a reply</h1>
    <lf-ask id="reply-child-ask"><h2>Which approach?</h2>
      <lf-options id="reply-child-options" choose>
        <lf-option id="reply-child-a">First approach</lf-option>
        <lf-option id="reply-child-b">Second approach</lf-option>
      </lf-options>
    </lf-ask>
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
            "--text",
            "Try it here:",
            "--markup",
            REPLY_SAMPLE,
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


def test_reading_keys_page_on_from_a_sample_to_its_page(browser, serve):
    """d/u in a sample whose own page is spent move the containing page, as the
    wheel does; in Full view the modal keeps them inside."""
    filler = "".join(
        f'<p id="line-{i}">Line {i} of a long child page.</p>' for i in range(60)
    )
    source = leaf_page(
        "Sample reading keys",
        f"""
<h1>Sample reading keys</h1>
<div style="height: 300px"></div>
<lf-sample id="block" label="A block sample">
  <template id="block-page" data-sample>
    <p id="child-text">A short child page.</p>
  </template>
</lf-sample>
<lf-sample id="window" label="A window sample" window>
  <template id="window-page" data-sample>{filler}</template>
</lf-sample>
<div style="height: 2400px"></div>
""",
    )
    page = open_page(browser, serve(source))
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1200, 800)
    block = page.locator("#block")
    block.evaluate("async sample => { await sample.ready; }")
    child = block.locator("iframe").element_handle().content_frame()
    assert child.evaluate("() => document.scrollingElement.scrollHeight <= innerHeight")
    child.locator("#child-text").click()
    page.keyboard.press("d")
    expect(page.locator(":root")).not_to_have_js_property("scrollTop", 0)
    below = page.evaluate("scrollY")
    page.keyboard.press("u")
    page.wait_for_function("below => scrollY < below", arg=below)

    window = page.locator("#window")
    window.evaluate("async sample => { await sample.ready; }")
    window.get_by_role("button", name="Full view", exact=True).click()
    inside = window.locator("iframe").element_handle().content_frame()
    inside.locator("#line-59").click()
    inside.evaluate("() => scrollTo(0, document.scrollingElement.scrollHeight)")
    at = page.evaluate("scrollY")
    page.keyboard.press("d")
    page.wait_for_timeout(300)
    assert page.evaluate("scrollY") == at


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
        <lf-options id="delivery" choose>
          <lf-option id="standard">Standard</lf-option>
          <lf-option id="express">Express</lf-option>
        </lf-options>
      </lf-sample>
      <lf-sample id="quoted" label="Quoted choices">
        <lf-options id="quoted-delivery" choose>
          <lf-option id="quoted-standard">Standard</lf-option>
        </lf-options>
      </lf-sample>
    """,
            )
        ),
    )
    sample = page.locator("#working")
    # A working sample's note is its label alone; a quoted one opens with "quoted".
    prefix = """sample => getComputedStyle(
      sample.querySelector(':scope > [data-lf-said="label"]'), '::before'
    ).content"""
    assert sample.evaluate(prefix) == '""'
    assert page.locator("#quoted").evaluate(prefix) == '"quoted · "'
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
