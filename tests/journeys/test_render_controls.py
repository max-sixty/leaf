"""Control stability, browser shell, accessibility, and ring tests."""

import re
import socket
from urllib.parse import parse_qs, urlsplit

import pytest
from interact_support import (
    append_carried_log_record,
    declare_work,
    record_claim,
    wait_for,
    working,
)
from leaf import event_log as events_model
from leaf import hosting as hosting_model
from leaf import presence as presence_model
from leaf import state as cleanup_model
from leaf.render_checks import rendered, wait_until_ready
from leaf.schema import SERVICE_FILE
from playwright.sync_api import expect
from render_cases_interaction import (
    SUGGESTION_PAGE,
    live_url,
    panel_comment,
)
from render_cases_layout import (
    BANNER_ORDER,
    DEFINE_BOXES,
    MANY_ASKS_PAGE,
    NEIGHBOUR,
    NEIGHBOURHOOD,
    RING_NAMES,
    SHOT_SRC,
    SHOTS,
    banner_control,
    displaced,
    overlapped_words,
    page_at_rest,
    ring_faults,
    rings_drawn,
    serious_axe_violations,
    standing_ring,
    token_colour,
)
from render_cases_navigation import (
    ADDRESSED_PAGE,
    _publish,
)
from render_harness import (
    BOARD_PAGE,
    EXAMPLES,
    FEATURE_GALLERY,
    LONG_PAGE,
    RELEASE_FOCUS,
    ROOT,
    CutOff,
    Traffic,
    _traffic,
    _until,
    any_draft_control,
    held_frames,
    holding,
    leaf_page,
    open_page,
    open_versions,
    opened_tab,
    page_comment,
    panel_settled,
    resized,
    root_overflow,
    round_trip,
    said,
    scroll_settled,
    sending,
    stamp_page,
    take_browser_errors,
    told,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_controls import (
    AIM_BOXES,
    AIM_PAGE,
    AIM_SURFACES,
    CONTROL_ARCHETYPES,
    CONTROL_STABILITY_PAGE,
    LIVE_SAMPLE_PAGE,
    LIVE_SAMPLES_PAGE,
    RING_CASES,
    RING_CHROME,
    RING_EXAMPLE_FILES,
    RING_EXAMPLES,
    RING_FOCUS_START,
    RING_REMOTE_CARRIER,
    RING_SCOPE_OPENER,
    RING_SCOPE_SURFACE,
    RING_SCOPE_WIDTH,
    RING_SCOPES_STARTING_WITHOUT_PANEL,
    RING_VIEWPORT,
    SAMPLE_STARTUP_FAILURE,
    SEEN_STOP,
    STATUS_FIT,
    WEBSITE_LINE,
    _each_aim_surface,
    _sample_containment_page,
    _tab_stops_without_indication,
    _touch_drag,
    fail_sample_startup,
    offered,
)


# The phone, whose settings sit behind their disclosure; the width changes nothing else.
@pytest.mark.parametrize("width", [390])
def test_merge_film_play_continues_from_the_displayed_moment(browser, serve, width):
    source = next(path for path in EXAMPLES if path.name == "wt-merge.html")
    page = open_page(browser, serve(source))
    resized(page, width, 900)
    play = page.locator(".film-play")
    slider = page.locator(".film-scrub")
    # Read the first painted frame within the trusted click, before playback advances.
    play.evaluate(
        "button => button.addEventListener('click', () => {"
        "window.firstPlayPosition = document.querySelector('.film-scrub').value;"
        "})"
    )
    arrival = slider.input_value()
    assert float(arrival) > 0
    play.click()
    assert page.evaluate("window.firstPlayPosition") == arrival
    play.click()

    page.reload()
    wait_until_ready(page)
    if width < 560:
        page.locator(".film-settings summary").click()
    page.locator("input[name=film-flag-moved]").uncheck()
    play.evaluate(
        "button => button.addEventListener('click', () => {"
        "window.firstPlayPosition = document.querySelector('.film-scrub').value;"
        "})"
    )
    changed = slider.input_value()
    play.click()
    assert page.evaluate("window.firstPlayPosition") == changed
    play.click()
    slider.focus()
    page.keyboard.press("End")
    expect(play).to_have_text("Replay")
    play.click()
    assert page.evaluate("window.firstPlayPosition") == "0"
    play.click()


def test_live_sample_full_view_keeps_the_child_and_returns_after_inner_escape(
    browser, serve
):
    """Viewport inspection retains practice state and contains focus until return."""
    page = open_page(browser, serve(LIVE_SAMPLES_PAGE))
    sample = page.locator("#first-practice")
    child = sample.locator("iframe").element_handle().content_frame()
    child.lf_traffic = Traffic(child)
    child_url = child.url
    parent_before = events_model.read_events(serve.page_dir)
    full = sample.get_by_role("button", name="Full view", exact=True)
    sample.get_by_role("button", name="Reset", exact=True).focus()
    page.keyboard.press("Tab")
    expect(full).to_be_focused()
    next_top = page.locator("#second-practice").bounding_box()["y"]
    parent_scroll = page.evaluate("scrollY")
    page.keyboard.press("Enter")
    back = sample.get_by_role("button", name="Return to page", exact=True)
    expect(back).to_be_focused()
    expect(sample.get_by_role("dialog", name="First practice")).to_be_visible()
    assert abs(page.locator("#second-practice").bounding_box()["y"] - next_top) <= 1
    assert page.evaluate("scrollY") == parent_scroll
    assert (
        sample.locator("iframe").bounding_box()["height"]
        > page.viewport_size["height"] * 0.8
    )
    with sending(child, "the full view choice"):
        child.locator("#child-a .lf-pick").click()
    draft = page_comment(child)
    write(draft, "Keep this draft through Full view.")
    back.click()
    expect(full).to_be_focused()
    assert child.url == child_url
    expect(child.locator("#child-a .lf-pick")).to_have_attribute("aria-checked", "true")
    expect(draft).to_have_js_property("value", "Keep this draft through Full view.")

    full.click()
    resized(page, 390, 720)
    expect(back).to_be_in_viewport()
    assert root_overflow(page) <= 1
    child.locator(".lf-threads-toggle").click()
    page.keyboard.press("Escape")
    expect(child.locator(".lf-threads-toggle")).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(back).to_be_visible()
    page.keyboard.press("Escape")
    expect(full).to_be_focused()
    assert child.url == child_url
    expect(draft).to_have_js_property("value", "Keep this draft through Full view.")
    assert events_model.read_events(serve.page_dir) == parent_before
    expect(
        page.locator("#second-practice")
        .frame_locator("iframe")
        .locator("#child-a .lf-pick")
    ).to_have_attribute("aria-checked", "false")

    full.click()
    sample.get_by_role("button", name="Reset", exact=True).click()
    sample.evaluate("sample => sample.ready")
    expect(back).to_be_visible()
    expect(
        sample.frame_locator("iframe").locator("#child-a .lf-pick")
    ).to_have_attribute("aria-checked", "false")
    back.press("Escape")
    expect(full).to_be_focused()

    full.click()
    sample.evaluate("""sample => {
      const parent = sample.parentNode;
      const next = sample.nextSibling;
      sample.remove();
      parent.insertBefore(sample, next);
    }""")
    expect(full).to_be_visible()
    assert sample.locator("dialog").evaluate("view => !view.matches(':modal')")


def test_a_live_revision_mounts_and_resets_its_new_sample(browser, serve):
    """An arriving sample allocates from its own revision before that revision paints."""
    page = open_page(browser, live_url(serve(LIVE_SAMPLE_PAGE)))
    addition = """
<lf-sample id="arriving-practice" label="New practice">
  <template id="arriving-source" data-sample>
    <h1 id="arrival-heading">Practice added in the revision</h1>
  </template>
</lf-sample>
"""
    revised = LIVE_SAMPLE_PAGE.replace("</main>", addition + "</main>")
    with page.expect_request("**/api/samples") as allocation:
        _publish(serve.page_dir, 2, revised, "Add another practice page.")
    sample = page.locator("#arriving-practice")
    expect(sample.frame_locator("iframe").locator("#arrival-heading")).to_have_text(
        "Practice added in the revision"
    )
    wait_until_ready(page)
    child_url = sample.locator("iframe").get_attribute("src")

    # A later revision keeps this exact node and its template. Reset must retain
    # the source coordinate it arrived with rather than borrow the newer reading.
    _publish(
        serve.page_dir,
        3,
        revised.replace("Practice without changing this page", "Practice together"),
        "Revise the surrounding explanation.",
    )
    expect(page.locator("#host-heading")).to_have_text("Practice together")
    wait_until_ready(page)
    reset = sample.get_by_role("button", name="Reset", exact=True)
    with page.expect_request("**/api/samples") as replacement:
        reset.click()
    assert replacement.value.header_value("Leaf-View-Revision") == (
        allocation.value.header_value("Leaf-View-Revision")
    )
    expect(sample.locator("iframe")).not_to_have_attribute("src", child_url)
    expect(sample.frame_locator("iframe").locator("#arrival-heading")).to_have_text(
        "Practice added in the revision"
    )
    wait_until_ready(page)


def test_thread_panel_gallery_shows_independent_live_views(browser, serve):
    """Child pages hold independent panel and anchored views across sample Reset."""
    gallery = FEATURE_GALLERY.parent / "thread-panel-gallery.html"
    page = open_page(browser, serve(gallery))
    views = {
        "overview": page.frame_locator("#overview-sample iframe"),
        "you": page.frame_locator("#on-you-sample iframe"),
        "resolved": page.frame_locator("#resolved-sample iframe"),
        "summary": page.frame_locator("#summary-sample iframe"),
    }
    for name in ("overview", "resolved", "summary"):
        frame = views[name]
        expect(frame.locator(".lf-thread-panel")).to_be_visible()
        topic = frame.locator(".lf-thread[open] .lf-thread-topic")
        expect(topic).to_be_visible()
        assert topic.evaluate("element => element.getBoundingClientRect().width") > 40

    expect(views["overview"].locator(".lf-thread:not([hidden])")).to_have_count(3)
    expect(
        views["overview"].locator(".lf-thread:not([open]) .lf-thread-topic").first
    ).to_be_visible()
    anchored = views["you"].locator(".lf-margin-preview")
    expect(anchored).to_be_visible()
    expect(anchored).to_have_attribute(
        "aria-label", "Thread for Agenda and room photo."
    )
    expect(anchored.locator(".lf-msg")).to_have_count(3)
    expect(anchored.locator("leaf-text")).to_be_visible()
    expect(views["resolved"].locator(".lf-thread-view-summary")).to_have_text(
        "1 resolved thread"
    )
    expect(
        views["summary"].locator('.lf-thread[data-id="c1a39980"]')
    ).to_have_attribute("open", "")
    expect(views["summary"].locator(".lf-thread[open] .lf-thread-topic")).to_have_text(
        "Afternoon workshop"
    )

    views["overview"].get_by_role("button", name="Close threads").click()
    expect(views["overview"].locator(".lf-thread-panel")).to_be_hidden()
    expect(anchored).to_be_visible()
    reset = page.locator("#overview-sample").get_by_role(
        "button", name="Reset", exact=True
    )
    reset.click()
    expect(reset).to_be_enabled()
    expect(views["overview"].locator(".lf-thread-panel")).to_be_visible()
    expect(views["overview"].locator(".lf-thread:not([hidden])")).to_have_count(3)
    reset.focus()
    expect(reset).to_be_focused()
    assert (
        page.locator("#on-you-sample").evaluate(
            "sample => sample.showThread('98850286')"
        )
        is True
    )
    expect(reset).to_be_focused()
    expect(anchored).to_be_visible()

    # Parent view commands change presentation without borrowing child focus.
    views["you"].locator(".lf-threads-toggle").click()
    child_find = views["you"].get_by_role("searchbox", name="Find in threads")
    child_find.click()
    expect(child_find).to_be_focused()
    assert (
        page.locator("#on-you-sample").evaluate(
            "sample => sample.showThread('98850286', {surface: 'panel'})"
        )
        is True
    )
    expect(child_find).to_be_focused()

    expect(views["you"].locator(".lf-thread-panel")).to_be_visible()
    expect(views["you"].locator(".lf-thread-view-summary")).to_have_text(
        "1 open thread"
    )
    expect(views["you"].locator('.lf-thread[data-id="98850286"]')).to_be_visible()


def test_sample_fixture_history_presents_before_ready_and_returns_on_reset(
    browser, serve
):
    """Shared authored history starts independent windows before host controls run."""
    source = leaf_page(
        "History study",
        """
        <h1>History study</h1><output id="arrivals">0</output>
        <lf-sample id="first-history" label="first treatment" window>
          <template id="first-history-page" data-sample data-sample-events="history">
            <h1>Weekend service</h1><p id="timetable">Trains run hourly.</p>
          </template>
        </lf-sample>
        <lf-sample id="second-history" label="second treatment" window>
          <template id="second-history-page" data-sample data-sample-events="history">
            <h1>Weekend service</h1><p id="timetable">Trains run hourly.</p>
          </template>
        </lf-sample>
        """,
        head="""
        <script id="history" type="application/json">
          [{"id":"question","kind":"comment","anchor":{"section":"timetable"},
            "text":"Does Sunday keep this timetable?"},
           {"kind":"reply","author":"agent","parent":"question",
            "text":"Yes, both weekend days use the same hourly service."}]
        </script>
        <script type="module">
          let arrivals = 0;
          document.addEventListener('lf-sample-ready', async event => {
            const sample = event.detail.sample;
            await sample.showThread('question', {surface: 'panel'});
            document.querySelector('#arrivals').textContent = String(++arrivals);
          });
        </script>
        """,
    )
    page = open_page(browser, serve(source))
    expect(page.locator("#arrivals")).to_have_text("2")
    parent_before = events_model.read_events(serve.page_dir)
    first = page.frame_locator("#first-history iframe")
    other = page.frame_locator("#second-history iframe")
    expect(first.locator(".lf-thread")).to_have_count(1)
    expect(other.locator(".lf-thread")).to_have_count(1)
    expect(first.locator(".lf-thread-panel")).to_be_visible()
    first.locator('.lf-thread[data-id="question"] .lf-thread-summary').click()
    first.locator('.lf-thread[data-id="question"] .lf-resolve').click()
    expect(first.locator('.lf-thread[data-id="question"]')).to_have_attribute(
        "data-resolved", "true"
    )
    other_events = page.request.get(
        other.locator("body").evaluate("new URL('api/state', document.baseURI).href")
    ).json()["events"]
    assert [event["kind"] for event in other_events if event["kind"] != "read"] == [
        "comment",
        "reply",
    ]
    assert events_model.read_events(serve.page_dir) == parent_before
    page.locator("#first-history").get_by_role(
        "button", name="Reset", exact=True
    ).click()
    expect(page.locator("#arrivals")).to_have_text("3")
    expect(first.locator(".lf-thread-panel")).to_be_visible()
    state = page.request.get(
        first.locator("body").evaluate("new URL('api/state', document.baseURI).href")
    ).json()
    assert [event["kind"] for event in state["events"] if event["kind"] != "read"] == [
        "comment",
        "reply",
    ]
    assert state["events"][1]["parent"] == "question"
    assert events_model.read_events(serve.page_dir) == parent_before


def test_sample_host_view_changes_leave_its_scroll_and_keyboard_position(
    browser, serve
):
    """Page, panel and Reset arrive inside a child without moving its host reader."""
    page = open_page(browser, serve(_sample_containment_page()))
    resized(page, 1000, 720)
    sample = page.locator("#practice")
    sample.evaluate("async sample => { await sample.ready; }")
    frame = sample.locator("iframe")
    completed = 0
    for position in ("offscreen", "partial"):
        page.evaluate(
            """position => {
              const frame = document.querySelector('#practice iframe');
              scrollTo({top: position === 'offscreen' ? 0
                : scrollY + frame.getBoundingClientRect().top - 350,
                behavior: 'instant'});
            }""",
            position,
        )
        box = frame.bounding_box()
        if position == "offscreen":
            assert box["y"] > 720
        else:
            assert 0 < box["y"] < 720 < box["y"] + box["height"]
        for button_id, panel_open in (
            ("show-page", False),
            ("show-panel", True),
            ("reset-child", True),
        ):
            button = page.locator(f"#{button_id}")
            button.scroll_into_view_if_needed()
            before = page.evaluate("scrollY")
            button.click()
            completed += 1
            expect(page.locator("#completed")).to_have_text(str(completed))
            child = frame.element_handle().content_frame()
            expect(button).to_be_focused()
            assert page.evaluate("scrollY") == before
            panel = child.locator(".lf-thread-panel")
            if panel_open:
                expect(panel).to_be_visible()
                expect(
                    child.locator('.lf-thread[data-id="question"]')
                ).to_have_attribute("open", "")
            else:
                expect(panel).to_be_hidden()
                expect(
                    child.locator(".lf-margin-preview, .lf-page-thread").get_by_text(
                        "Can you check the destination?", exact=True
                    )
                ).to_be_visible()


def test_sample_child_passage_and_reply_gestures_scroll_only_the_child(browser, serve):
    """Child navigation reveals nested reading regions; disclosure and typing stay local."""
    page = open_page(browser, serve(_sample_containment_page()))
    resized(page, 1000, 720)
    sample = page.locator("#practice")
    sample.evaluate("async sample => { await sample.ready; }")
    page.locator("#show-panel").click()
    expect(page.locator("#completed")).to_have_text("1")
    frame = sample.locator("iframe")
    page.evaluate(
        """() => scrollTo({top: scrollY +
          document.querySelector('#practice iframe').getBoundingClientRect().top - 150,
          behavior: 'instant'})"""
    )
    child = frame.element_handle().content_frame()
    quote = child.locator(".lf-quote", has_text="Nested landing target.")
    quote.scroll_into_view_if_needed()
    before = page.evaluate("scrollY")
    root_before = child.evaluate("scrollY")
    quote.click()
    panel_settled(child, open=False)
    scroll_settled(child)
    landing = child.evaluate(
        """() => {
          const target = document.querySelector('#destination').getBoundingClientRect();
          const pane = document.querySelector('#nested-reading').getBoundingClientRect();
          return {target:target.toJSON(), pane:pane.toJSON(), height:innerHeight,
            nested:document.querySelector('#nested-reading').scrollTop, root:scrollY};
        }"""
    )
    assert landing["target"]["top"] >= max(0, landing["pane"]["top"]) - 1, landing
    assert (
        landing["target"]["bottom"]
        <= min(landing["height"], landing["pane"]["bottom"]) + 1
    ), landing
    assert child.evaluate("scrollY") > root_before
    assert child.locator("#nested-reading").evaluate("box => box.scrollTop") > 0
    assert page.evaluate("scrollY") == before

    # A real child disclosure keeps its focused toggle in its own conversation.
    page.locator("#show-panel").click()
    expect(page.locator("#completed")).to_have_text("2")
    expand = child.get_by_role("button", name="Show 1 progress message", exact=True)
    expand.scroll_into_view_if_needed()
    before = page.evaluate("scrollY")
    thread_scroll_before = child.locator(".lf-threads").evaluate("box => box.scrollTop")
    expand.focus()
    expand.press("Enter")
    collapse = child.get_by_role("button", name="Hide 1 progress message", exact=True)
    expect(collapse).to_be_focused()
    expect(collapse).to_be_in_viewport()
    rendered(child)
    assert (
        child.locator(".lf-threads").evaluate("box => box.scrollTop")
        > thread_scroll_before
    )
    assert page.evaluate("scrollY") == before

    editor = child.locator('.lf-thread[data-id="question"] leaf-text')
    editor.scroll_into_view_if_needed()
    before = page.evaluate("scrollY")
    words = "\n".join(f"Line {i} of the reply" for i in range(30))
    write(editor, words)
    expect(editor).to_have_js_property("value", words)
    child.wait_for_function(
        """() => document.querySelector(
          '.lf-thread[data-id="question"] leaf-text').scrollTop > 0"""
    )
    rendered(child)
    expect(editor).to_be_focused()
    assert page.evaluate("scrollY") == before


def test_sample_reset_keeps_the_keyboard_position_while_loading(browser, serve):
    """Reset keeps its stop through loading and failure, without reclaiming focus."""
    source = leaf_page(
        "Practice reset",
        """
<h1>Practice reset</h1>
<button id="continue-reading" type="button">Continue reading</button>
<lf-sample id="practice" label="Practice page">
  <template id="practice-source" data-sample><p>Start again here.</p></template>
</lf-sample>
""",
    )
    source = source.replace("</template>", SAMPLE_STARTUP_FAILURE + "</template>")
    page = open_page(browser, serve(source))
    sample = page.locator("#practice")
    reset = sample.get_by_role("button", name="Reset", exact=True)
    onward = page.locator("#continue-reading")
    expect(reset).to_be_enabled()
    held = []
    navigation = re.compile(r"/api/samples/[^/]+/$")
    page.route(
        navigation,
        lambda route: (
            held.append(route)
            if route.request.is_navigation_request()
            else route.continue_()
        ),
    )
    onward.focus()
    onward.press("Tab")
    expect(reset).to_be_focused()
    assert reset.evaluate("button => button.matches(':focus-visible')")
    scroll_before = page.evaluate("scrollY")

    reset.press("Enter")
    holding(page, held, 1, "the replacement practice page")
    expect(reset).to_be_disabled()
    expect(reset).to_be_focused()
    reset.press("Space")
    reset.press("Enter")
    rendered(page)
    assert len(held) == 1
    expect(reset).to_be_focused()
    assert page.evaluate("scrollY") == scroll_before

    # Completion must leave a newer keyboard destination alone.
    reset.press("Shift+Tab")
    expect(onward).to_be_focused()
    held[0].continue_()
    expect(reset).to_be_enabled()
    expect(onward).to_be_focused()

    onward.press("Tab")
    reset.press("Space")
    holding(page, held, 2, "the failed replacement practice page")
    expect(reset).to_be_focused()
    fail_sample_startup(held[1])
    expect(sample.get_by_role("status")).to_have_text("Practice could not start")
    expect(reset).to_be_enabled()
    expect(reset).to_be_focused()
    assert page.evaluate("scrollY") == scroll_before

    page.unroute(navigation)
    reset.press("Enter")
    expect(reset).to_be_enabled()
    expect(reset).to_be_focused()
    expect(
        sample.frame_locator("iframe").get_by_text("Start again here.")
    ).to_be_visible()


def test_live_samples_keep_real_gestures_and_drafts_inside_the_child(browser, serve):
    """A sample is a full page: its choices and comments reach only its own log."""
    page = open_page(browser, serve(LIVE_SAMPLES_PAGE))
    parent_before = events_model.read_events(serve.page_dir)
    first = page.locator("#first-practice")
    second = page.locator("#second-practice")
    reset = first.get_by_role("button", name="Reset", exact=True)
    expect(reset).to_be_enabled()
    expect(second.get_by_role("button", name="Reset", exact=True)).to_be_enabled()
    # The host's controls stand with its label, outside the indented child page.
    controls = first.locator(".lf-sample-controls").bounding_box()
    frame = first.locator("iframe").bounding_box()
    assert abs(controls["x"] - first.bounding_box()["x"]) < 1
    assert controls["x"] < frame["x"]
    assert controls["y"] + controls["height"] <= frame["y"]
    child = first.locator("iframe").element_handle().content_frame()
    other = second.locator("iframe").element_handle().content_frame()
    child.lf_traffic = Traffic(child)
    child_url = urlsplit(child.url)._replace(fragment="").geturl()
    assert child.url != other.url
    # A child's startup does not take focus from the page it arrives in.
    assert page.evaluate("document.activeElement.tagName") != "IFRAME"
    # Each frame takes its page's height, so the containing page scrolls it whole:
    # the child's viewport ends where its page does.
    for practice in (child, other):
        assert practice.evaluate(
            "Math.abs(document.querySelector('main').getBoundingClientRect().bottom"
            " - innerHeight) <= 1"
        )

    # The first click lands on the child's control; there is no entry step.
    with sending(child, "the sample choice"):
        child.locator("#child-a .lf-pick").click()
    expect(child.locator("#child-a .lf-pick")).to_have_attribute("aria-checked", "true")
    expect(other.locator("#child-a .lf-pick")).to_have_attribute(
        "aria-checked", "false"
    )

    draft = page_comment(child)
    write(draft, "Keep this draft while I resize the page.")
    width_before = child.evaluate("innerWidth")
    page.set_viewport_size({"width": 720, "height": 900})
    child.wait_for_function("before => innerWidth < before", arg=width_before)
    expect(draft).to_have_js_property(
        "value", "Keep this draft while I resize the page."
    )
    expect(draft).to_be_focused()
    assert urlsplit(child.url)._replace(fragment="").geturl() == child_url
    with sending(child, "the sample comment"):
        draft.press("ControlOrMeta+Enter")
    child.locator(".lf-threads-toggle").click()
    expect(
        child.locator(".lf-thread").filter(has_text="Keep this draft")
    ).to_be_visible()
    child.get_by_role("button", name="Close threads").click()
    state_response = page.request.get(child_url + "api/state")
    assert state_response.ok, state_response.text()
    state = state_response.json()
    assert [event["kind"] for event in state["events"]] == ["action", "comment"]
    assert state["events"][-1]["text"] == "Keep this draft while I resize the page."
    assert (
        page.request.get(
            other.evaluate("new URL('api/state', document.baseURI).href")
        ).json()["events"]
        == []
    )
    assert events_model.read_events(serve.page_dir) == parent_before

    write(page_comment(child), "Discard this unsent practice draft on reset.")
    page.evaluate("""() => {
        localStorage.setItem('parent-draft', 'retain');
        sessionStorage.setItem('parent-tab', 'retain');
    }""")
    parent_storage = page.evaluate(
        "[Object.keys(localStorage), Object.keys(sessionStorage)]"
    )
    write(page_comment(other), "Keep the other sample's draft.")
    reset.scroll_into_view_if_needed()
    reset_scroll = page.evaluate("scrollY")
    reset.click()
    expect(reset).to_be_enabled()
    expect(reset).to_be_focused()
    assert page.evaluate("scrollY") == reset_scroll
    reset_child = first.locator("iframe").element_handle().content_frame()
    assert reset_child.url != child_url
    expect(reset_child.locator("#child-a .lf-pick")).to_have_attribute(
        "aria-checked", "false"
    )
    expect(reset_child.locator(".lf-thread")).to_have_count(0)
    expect(page_comment(reset_child)).to_have_js_property("value", "")
    assert page.request.get(child_url + "api/state").status == 404
    assert events_model.read_events(serve.page_dir) == parent_before
    assert (
        page.evaluate("[Object.keys(localStorage), Object.keys(sessionStorage)]")
        == parent_storage
    )
    assert page.evaluate(
        "localStorage.getItem('parent-draft') === 'retain' && "
        "sessionStorage.getItem('parent-tab') === 'retain'"
    )
    expect(other.locator(".lf-general leaf-text")).to_have_js_property(
        "value", "Keep the other sample's draft."
    )


def test_a_window_sample_is_a_whole_leaf_window_that_scrolls_inside(browser, serve):
    """A window sample presents its opening view, keeps full chrome, and scrolls inside."""
    filler = "".join(
        f'<p id="filler-{i}">Line {i} of a long page.</p>' for i in range(60)
    )
    source = leaf_page(
        "window sample",
        f"""
<h1>Window sample</h1>
<lf-sample id="window-sample" label="a whole window" window>
  <template id="window-page" data-sample>
    <script type="module">history.replaceState(null, "", "#first-view");</script>
    <h1>Child</h1>
    <lf-tabs id="child-views">
      <lf-tab id="first-view" label="Long view">{filler}</lf-tab>
      <lf-tab id="second-view" label="Short view"><p>Another view.</p></lf-tab>
    </lf-tabs>
  </template>
</lf-sample>
""",
    )
    page = open_page(browser, serve(source))
    sample = page.locator("#window-sample")
    reading = sample.evaluate("async sample => await sample.ready")
    child_frame = sample.locator("iframe").element_handle().content_frame()
    child = child_frame.evaluate(
        """() => ({
          block: document.documentElement.hasAttribute('data-lf-sample-block'),
          bar: getComputedStyle(document.querySelector('.lf-shortcut-bar')).display,
          page: document.documentElement.scrollHeight,
        })"""
    )
    assert reading["block"] == child["block"]
    assert not child["block"]
    assert child["bar"] != "none"
    frame = sample.locator("iframe")
    assert frame.bounding_box()["height"] < child["page"] / 2
    child_frame = frame.element_handle().content_frame()
    assert child_frame.url.endswith("/#first-view")
    expect(child_frame.get_by_role("tab", name="Long view")).to_have_attribute(
        "aria-selected", "true"
    )

    box = frame.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    content = page.frame_locator("#window-sample iframe").locator(":root")
    scroll_before = content.evaluate("root => root.scrollTop")
    page.mouse.wheel(0, 300)
    expect(content).to_have_js_property("scrollTop", scroll_before + 300)
    assert frame.bounding_box()["height"] == box["height"]

    sample.get_by_role("button", name="Full view", exact=True).click()
    assert frame.bounding_box()["height"] > page.viewport_size["height"] * 0.8
    sample.get_by_role("button", name="Return to page", exact=True).click()
    assert child_frame.evaluate("scrollY") == scroll_before + 300
    assert frame.bounding_box()["height"] == box["height"]

    # A fragment set during startup must not prevent Reset or reload from presenting.
    reset = sample.get_by_role("button", name="Reset", exact=True)
    old_url = child_frame.url
    reset.click()
    expect(reset).to_be_enabled()
    child_frame = frame.element_handle().content_frame()
    assert child_frame.url != old_url
    assert child_frame.url.endswith("/#first-view")
    expect(child_frame.get_by_role("tab", name="Long view")).to_have_attribute(
        "aria-selected", "true"
    )
    page.reload()
    wait_until_ready(page)
    expect(reset).to_be_enabled()
    child_frame = frame.element_handle().content_frame()
    assert child_frame.url.endswith("/#first-view")
    expect(child_frame.get_by_role("tab", name="Long view")).to_have_attribute(
        "aria-selected", "true"
    )


@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
def test_sample_editor_focus_preserves_outer_scroll_and_the_caret(
    request, serve, engine
):
    """The editor owns focus policy even when its dependency's browser policy differs."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(
            leaf_page(
                "Editor focus containment",
                """
<h1>Containing page</h1><div style="height:1400px"></div>
<lf-sample id="practice" label="Editor practice" window>
  <template id="practice-source" data-sample>
    <h1>Practice page</h1><button id="entry">Enter practice</button>
        <script type="module">
          import {focusDestination} from '/runtime/widget-api.js';
          window.placeEditor = () => focusDestination(document.querySelector('#editor'), 'move');
        </script>
  </template>
</lf-sample>
""",
            )
        ),
    )
    sample = page.locator("#practice")
    sample.evaluate("async sample => await sample.ready")
    child = sample.locator("iframe").element_handle().content_frame()
    child.evaluate("""async () => {
      const editor = document.createElement('leaf-text');
      editor.id = 'editor';
      editor.value = 'Words stay here';
      document.querySelector('main').append(editor);
      editor.setSelectionRange(6, 10);
    }""")
    child.locator("#entry").click()
    page.evaluate("scrollTo(0, 0)")
    scroll_settled(page)
    assert child.evaluate("document.hasFocus()")
    for _ in range(3):
        child.evaluate("placeEditor()")
        scroll_settled(page)
        assert page.evaluate("scrollY") == 0
        expect(child.locator("#editor")).to_be_focused()
        child.locator("#entry").click()
        page.evaluate("scrollTo(0, 0)")
        scroll_settled(page)
    child.evaluate("placeEditor()")
    # Real editing proves the arrival used the retained caret, not the browser's
    # initial caret. The browser may reveal its context for this deliberate input.
    page.keyboard.insert_text("remain")
    expect(child.locator("#editor")).to_have_js_property("value", "Words remain here")


def test_sample_browser_boundary_contains_focus_scroll_and_parent_access(
    browser, serve
):
    """Leaf navigation stays local without changing authored native browser APIs."""
    filler = "".join(f"<p>Child passage {number}.</p>" for number in range(40))
    source = leaf_page(
        "Isolated sample",
        f"""
<h1>Review page</h1><button id="outer-control">Choose a conversation</button>
<div style="height:800px"></div>
<lf-sample id="isolated-practice" label="Isolated practice" window>
  <template id="isolated-source" data-sample>
    <h1>Practice page</h1><button id="child-control">Practice action</button>
    {filler}
    <div id="inner-scroll" tabindex="0" style="height:160px;overflow:auto">
      <div style="height:600px"></div><button id="deep-control">Nested action</button>
    </div>
    <svg><a id="svg-control" href="#child-control" tabindex="0"><text y="20">SVG action</text></a></svg>
    <dialog id="practice-modal"><input></dialog>
    <dialog id="practice-inner-modal"><input></dialog>
    <div id="practice-popover" popover><input></div>
    <iframe title="Authored embedded page" srcdoc="<p>Embedded content is allowed</p>"></iframe>
    <script type="module">
      import {{ closeNativeLayer, focusDestination, scrollIntoView, showNativeLayer }} from '/runtime/widget-api.js';
      window.leafNavigation = {{ closeNativeLayer, focusDestination, scrollIntoView, showNativeLayer }};
      for (const input of document.querySelectorAll('dialog input, [popover] input'))
        input.autofocus = true;
      window.leafFocusEvents = [];
      document.addEventListener('focusin', event => leafFocusEvents.push(event.target.id), true);
      window.addEventListener('message', event => {{
        if (event.data === 'close-child-modal') {{
          closeNativeLayer(document.querySelector('#practice-inner-modal'));
          closeNativeLayer(document.querySelector('#practice-modal'));
          parent.postMessage({{type: 'closed-child-modal', focused: document.hasFocus()}}, '*');
          return;
        }}
        if (event.data !== 'attempt-child-focus') return;
        leafFocusEvents.length = 0;
        document.dispatchEvent(new PointerEvent('pointerdown', {{bubbles: true}}));
        scrollIntoView(document.querySelector('#deep-control'));
        focusDestination(document.querySelector('#deep-control'), 'move');
        focusDestination(document.querySelector('#svg-control'), 'move');
        const dialog = document.querySelector('#practice-modal');
        for (const modal of [true, false]) {{
          showNativeLayer(dialog, {{modal}});
          closeNativeLayer(dialog);
        }}
        const popover = document.querySelector('#practice-popover');
        showNativeLayer(popover);
        closeNativeLayer(popover);
        parent.postMessage({{
          type: 'attempted-child-focus', focused: document.hasFocus(),
          activated: navigator.userActivation.hasBeenActive, focusEvents: leafFocusEvents,
        }}, '*');
      }});
    </script>
  </template>
</lf-sample>
""",
    )
    page = open_page(browser, serve(source))
    sample = page.locator("#isolated-practice")
    sample.evaluate("async sample => await sample.ready")
    child = sample.locator("iframe").element_handle().content_frame()
    assert child.evaluate(
        """() => {
          try { parent.document; return false; }
          catch (error) { return error.name === 'SecurityError'; }
        }"""
    )
    assert sample.locator("iframe").evaluate("frame => frame.contentDocument === null")
    # External data uses native CORS with the child's opaque origin, never the
    # containing page's authenticated relay. The route stands in for a remote API.
    remote = "https://cors.example.invalid/sample.json"
    external_requests = []

    def cors_response(route):
        external_requests.append(route.request.headers)
        route.fulfill(
            headers={"Access-Control-Allow-Origin": "*"},
            json={"reading": "external data"},
        )

    page.route(remote, cors_response)
    assert child.evaluate("async url => (await fetch(url)).json()", remote) == {
        "reading": "external data"
    }
    assert len(external_requests) == 1
    assert external_requests[0]["origin"] == "null"
    assert "cookie" not in external_requests[0]
    page.unroute(remote)
    # Scripts and nested embeds are still admitted; native methods are untouched.
    assert child.evaluate("""() =>
      [HTMLElement.prototype.focus, Element.prototype.scrollIntoView]
        .every(method => Function.prototype.toString.call(method).includes('[native code]'))
    """)
    expect(child.locator('iframe[title="Authored embedded page"]')).to_have_count(1)
    outer = page.locator("#outer-control")
    outer.click()
    scroll_settled(page)
    before = page.evaluate("scrollY")
    page.evaluate("""() => {
      window.outerTransitions = [];
      for (const type of ['focusin', 'scroll'])
        document.addEventListener(type, event => outerTransitions.push(type), true);
    }""")
    child.evaluate("""() => {
      const {closeNativeLayer, focusDestination, scrollIntoView, showNativeLayer} = window.leafNavigation;
      leafFocusEvents.length = 0;
      focusDestination(document.querySelector('#child-control'), 'move');
      scrollIntoView(document.querySelector('#deep-control'));
      focusDestination(document.querySelector('#deep-control'), 'move');
      focusDestination(document.querySelector('#svg-control'), 'move');
      const dialog = document.querySelector('#practice-modal');
      showNativeLayer(dialog);
      closeNativeLayer(dialog);
      const popover = document.querySelector('#practice-popover');
      showNativeLayer(popover);
      closeNativeLayer(popover);
    }""")
    page.evaluate(
        "async () => { await new Promise(requestAnimationFrame); await new Promise(requestAnimationFrame); }"
    )
    expect(outer).to_be_focused()
    assert page.evaluate("scrollY") == before
    assert page.evaluate("outerTransitions") == []
    assert child.evaluate("leafFocusEvents") == []
    assert child.evaluate("scrollY") > 0
    assert child.locator("#inner-scroll").evaluate("node => node.scrollTop") > 0

    # A deliberate pointer entry gets real child focus and ordinary local keys.
    sample.scroll_into_view_if_needed()
    child.locator("#child-control").click()
    expect(child.locator("#child-control")).to_be_focused()
    page.keyboard.press("Escape")
    expect(child.locator("#child-control")).not_to_be_focused()
    page.keyboard.press("Escape")
    expect(sample).to_be_focused()

    # Previous user entry cannot let later script calls take ownership back.
    outer.click()
    page.evaluate(
        "async () => { await new Promise(requestAnimationFrame); await new Promise(requestAnimationFrame); }"
    )
    before = page.evaluate("scrollY")
    page.evaluate("outerTransitions.length = 0")
    assert page.evaluate("""() => new Promise(resolve => {
      window.addEventListener('message', function report(event) {
        if (event.data?.type !== 'attempted-child-focus') return;
        window.removeEventListener('message', report);
        resolve({focused: event.data.focused, activated: event.data.activated, focusEvents: event.data.focusEvents});
      });
      document.querySelector('#isolated-practice iframe').contentWindow
        .postMessage('attempt-child-focus', '*');
    })""") == {"focused": False, "activated": True, "focusEvents": []}
    page.evaluate(
        "async () => { await new Promise(requestAnimationFrame); await new Promise(requestAnimationFrame); }"
    )
    expect(outer).to_be_focused()
    assert page.evaluate("scrollY") == before
    assert page.evaluate("outerTransitions") == []

    # Native close remembers a previous focus target even after the parent has
    # reclaimed input. A return into another modal also escapes ancestor inertness.
    sample.scroll_into_view_if_needed()
    child.locator("#child-control").click()
    child.evaluate("""() => {
      const {focusDestination, showNativeLayer} = leafNavigation;
      for (const id of ['practice-modal', 'practice-inner-modal']) {
        const dialog = document.getElementById(id);
        showNativeLayer(dialog);
        focusDestination(dialog.querySelector('input'), 'move');
      }
    }""")
    expect(child.locator("#practice-inner-modal input")).to_be_focused()
    outer.click()
    scroll_settled(page)
    before = page.evaluate("scrollY")
    page.evaluate("outerTransitions.length = 0")
    child.evaluate("leafFocusEvents.length = 0")
    assert (
        page.evaluate("""() => new Promise(resolve => {
      window.addEventListener('message', function report(event) {
        if (event.data?.type !== 'closed-child-modal') return;
        window.removeEventListener('message', report);
        resolve(event.data.focused);
      });
      document.querySelector('#isolated-practice iframe').contentWindow
        .postMessage('close-child-modal', '*');
    })""")
        is False
    )
    expect(outer).to_be_focused()
    assert page.evaluate("scrollY") == before
    assert page.evaluate("outerTransitions") == []
    assert child.evaluate("leafFocusEvents") == []
    expect(
        child.locator("#practice-modal[open], #practice-inner-modal[open]")
    ).to_have_count(0)

    # A child-owned close preserves its ordinary opener return without native
    # scrolling, and a layer opened from nowhere releases its hidden editor.
    sample.scroll_into_view_if_needed()
    child.locator("#child-control").click()
    scroll_settled(page)
    before = page.evaluate("scrollY")
    child.evaluate("""() => {
      const {closeNativeLayer, focusDestination, showNativeLayer} = leafNavigation;
      const popover = document.querySelector('#practice-popover');
      showNativeLayer(popover);
      focusDestination(popover.querySelector('input'), 'move');
      closeNativeLayer(popover);
    }""")
    expect(child.locator("#child-control")).to_be_focused()
    assert page.evaluate("scrollY") == before
    child.evaluate("""() => {
      const {closeNativeLayer, focusDestination, showNativeLayer} = leafNavigation;
      focusDestination(document.body, 'move');
      document.body.blur();
      const popover = document.querySelector('#practice-popover');
      showNativeLayer(popover);
      focusDestination(popover.querySelector('input'), 'move');
      closeNativeLayer(popover);
    }""")
    assert child.evaluate("document.activeElement === document.body")
    assert page.evaluate("scrollY") == before


def test_live_samples_retire_before_navigation_and_coalesce_reset(browser, serve):
    """A held replacement navigation cannot keep a released child alive."""
    page = open_page(browser, serve(LIVE_SAMPLE_PAGE))
    page.evaluate("""async () => {
        const {mountSample} = await window.__lfRuntimeImport('/runtime/sample.js');
        window.practiceFrame = document.createElement('iframe');
        document.body.append(practiceFrame);
        window.practiceHost = mountSample(practiceFrame, {template: 'first-source'});
        await practiceHost.ready;
    }""")
    previous = page.evaluate(
        "new URL(practiceFrame.src).origin + new URL(practiceFrame.src).pathname"
    )
    held = []
    released = []
    page.route(re.compile(r"/api/samples/[^/]+/$"), lambda route: held.append(route))
    page.on(
        "request",
        lambda request: (
            released.append(request.url)
            if request.url.endswith("/api/release")
            else None
        ),
    )
    page.evaluate("""() => {
        window.oldPracticeWindow = practiceFrame.contentWindow;
        const first = practiceHost.reset();
        const second = practiceHost.reset();
        window.samePracticeReset = first === second;
        window.practiceResult = Promise.allSettled([first, second]);
    }""")
    holding(page, held, 1, "the replacement sample document")
    assert page.evaluate("samePracticeReset && oldPracticeWindow.closed")
    assert page.request.get(previous + "api/state").status == 404
    replacement = held[0].request.url
    page.evaluate("practiceHost.destroy()")
    assert page.evaluate(
        "practiceResult.then(results => results.map(r => r.reason.name))"
    ) == ["AbortError", "AbortError"]
    assert page.evaluate(
        "practiceFrame.isConnected && !practiceFrame.hasAttribute('src')"
    )
    assert page.request.get(replacement + "api/state").status == 404
    assert released.count(previous + "api/release") == 1
    assert released.count(replacement + "api/release") == 1
    held[0].abort()
    page.unroute(re.compile(r"/api/samples/[^/]+/$"))

    # A failed presentation is retired too; Reset can then start a healthy child.
    page.route(re.compile(r"/api/samples/[^/]+/$"), fail_sample_startup)
    assert (
        page.evaluate("""async () => {
        const {mountSample} = await window.__lfRuntimeImport('/runtime/sample.js');
        window.practiceHost = mountSample(practiceFrame, {template: 'first-source'});
        return practiceHost.ready.catch(error => error.message);
    }""")
        == "Practice could not start"
    )
    assert page.evaluate("!practiceFrame.hasAttribute('src')")
    page.unroute(re.compile(r"/api/samples/[^/]+/$"))
    page.evaluate("practiceHost.reset().then(() => {})")
    replacement_frame = page.locator("iframe").last.element_handle().content_frame()
    expect(replacement_frame.locator("body[data-lf-presented]")).to_be_attached()
    page.evaluate("practiceHost.destroy()")


def test_live_samples_release_pending_allocations_and_can_reconnect(browser, serve):
    """Destroy releases every startup phase; a detached widget can reconnect."""
    page = open_page(browser, serve(LIVE_SAMPLE_PAGE))
    sample = page.locator("#first-practice")
    reset = sample.get_by_role("button", name="Reset", exact=True)
    expect(reset).to_be_enabled()
    sample.get_by_role("button", name="Full view", exact=True).click()
    previous = (
        urlsplit(sample.locator("iframe").get_attribute("src"))
        ._replace(fragment="")
        .geturl()
    )
    page.evaluate("""() => {
        window.detachedPractice = document.querySelector('#first-practice');
        detachedPractice.remove();
    }""")
    page.wait_for_function(
        "!detachedPractice.querySelector('iframe').hasAttribute('src')"
    )
    page.evaluate("document.querySelector('main').append(detachedPractice)")
    expect(reset).to_be_enabled()
    expect(sample.get_by_role("button", name="Full view", exact=True)).to_be_visible()
    assert sample.locator("iframe").get_attribute("src") != previous
    assert page.request.get(previous + "api/state").status == 404

    held = []
    page.route("**/api/samples", lambda route: held.append(route))
    page.evaluate("""async () => {
        const {mountSample} = await window.__lfRuntimeImport('/runtime/sample.js');
        window.pendingFrame = document.createElement('iframe');
        document.body.append(pendingFrame);
        window.pendingHost = mountSample(pendingFrame, {template: 'first-source'});
        window.pendingResult = pendingHost.ready.catch(error => error.name);
    }""")
    holding(page, held, 1, "the child allocation")
    page.evaluate("() => { window.pendingDestroy = pendingHost.destroy(); }")
    response = held[0].fetch()
    allocated = response.json()["url"]
    held[0].fulfill(response=response)
    page.evaluate("pendingDestroy")
    assert page.evaluate("pendingResult") == "AbortError"
    allocated_url = page.evaluate("url => new URL(url, location.href).href", allocated)
    assert page.request.get(allocated_url + "api/state").status == 404
    page.unroute("**/api/samples")

    held.clear()
    page.route(re.compile(r"/api/samples/[^/]+/$"), lambda route: held.append(route))
    page.evaluate("""async () => {
        const {mountSample} = await window.__lfRuntimeImport('/runtime/sample.js');
        window.pendingHost = mountSample(pendingFrame, {template: 'first-source'});
        window.pendingResult = pendingHost.ready.catch(error => error.name);
    }""")
    holding(page, held, 1, "a child detached before its document arrives")
    held_release = []
    page.route("**/api/release", lambda route: held_release.append(route))
    page.evaluate("pendingFrame.remove()")
    assert page.evaluate("pendingResult") == "AbortError"
    holding(page, held_release, 1, "the detached child's allocation release")
    assert page.request.get(held[0].request.url + "api/state").status == 200
    held_release[0].continue_()
    page.evaluate("pendingHost.destroy()")
    assert page.request.get(held[0].request.url + "api/state").status == 404
    held[0].abort()
    page.unroute("**/api/release")

    # A destroyed queue entry cannot wait for unrelated children to load. It is
    # removed without consuming the next slot a surviving queued child needs.
    held.clear()
    page.evaluate("""async () => {
        const {mountSample} = await window.__lfRuntimeImport('/runtime/sample.js');
        window.pendingResults = [];
        window.pendingHosts = Array.from({length: 5}, (_, index) => {
            const frame = document.createElement('iframe');
            document.body.append(frame);
            const host = mountSample(frame, {template: 'first-source'});
            host.ready.then(
                () => { pendingResults[index] = 'ready'; },
                error => { pendingResults[index] = error.name; });
            return host;
        });
    }""")
    holding(page, held, 3, "three occupied sample admission slots")
    page.evaluate("""() => {
        window.queuedDestroyDone = false;
        pendingHosts[3].destroy().then(() => { queuedDestroyDone = true; });
    }""")
    page.wait_for_function("queuedDestroyDone && pendingResults[3] === 'AbortError'")
    assert len(held) == 3
    page.evaluate("() => { void pendingHosts[0].destroy(); }")
    holding(page, held, 4, "the surviving queued sample's admission")
    page.evaluate("""() => {
        window.allPendingDestroyed = false;
        Promise.all(pendingHosts.map(host => host.destroy()))
            .then(() => { allPendingDestroyed = true; });
    }""")
    page.wait_for_function("allPendingDestroyed")
    assert page.evaluate("pendingResults") == ["AbortError"] * 5
    for route in held:
        assert page.request.get(route.request.url + "api/state").status == 404
        route.abort()


def test_slow_sample_state_does_not_hold_up_other_child_loads(browser, serve):
    """A child waiting for state releases its load slot for the next sample."""
    page = open_page(browser, serve(LIVE_SAMPLE_PAGE))
    held = []
    page.route(
        re.compile(r"/api/samples/[^/]+/api/state$"),
        lambda route: held.append(route),
    )
    page.evaluate("""async () => {
      const {mountSample} = await window.__lfRuntimeImport('/runtime/sample.js');
      window.practiceHosts = Array.from({length: 4}, () => {
        const frame = document.createElement('iframe');
        document.body.append(frame);
        return mountSample(frame, {template: 'first-source'});
      });
    }""")
    holding(page, held, 4, "four sample state reads")
    for route in held:
        route.continue_()
    page.evaluate("Promise.all(practiceHosts.map(host => host.ready))")
    page.evaluate("Promise.all(practiceHosts.map(host => host.destroy()))")


def test_live_samples_preserve_optimistic_refusal_and_child_escape(browser, serve):
    """Delivery rollback and nested Escape remain the ordinary child's behavior."""
    page = open_page(browser, serve(LIVE_SAMPLE_PAGE))
    sample = page.locator("#first-practice")
    expect(sample.get_by_role("button", name="Reset", exact=True)).to_be_enabled()
    child = sample.locator("iframe").element_handle().content_frame()
    child.lf_traffic = Traffic(child)
    held = []
    event_url = child.evaluate("new URL('api/event', document.baseURI).href")
    page.route(event_url, lambda route: held.append(route))
    choice = child.locator("#child-a .lf-pick")
    choice.click()
    holding(page, held, 1, "the child's held choice")
    expect(choice).to_have_attribute("aria-checked", "true")
    held[0].fulfill(
        json={
            "ok": False,
            "attempt": held[0].request.post_data_json["attempt"],
            "error": "This practice choice was refused.",
            "final": True,
        }
    )
    round_trip(child)
    expect(choice).to_have_attribute("aria-checked", "false")
    assert (
        page.request.get(
            child.evaluate("new URL('api/state', document.baseURI).href")
        ).json()["events"]
        == []
    )
    page.unroute(event_url)

    child.locator(".lf-threads-toggle").click()
    expect(child.locator(".lf-threads-toggle")).to_have_attribute(
        "aria-expanded", "true"
    )
    page.keyboard.press("Escape")
    expect(child.locator(".lf-threads-toggle")).to_have_attribute(
        "aria-expanded", "false"
    )
    page.keyboard.press("Escape")
    expect(sample).to_be_focused()


def test_the_responsive_action_row_keeps_primary_actions_in_reach(browser, serve):
    """Fixed primary and menu seats keep every destination reachable at any width."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    page = open_page(browser, url)

    # Each control reserves its widest words in the face it wears in each band. A phone
    # wears Threads as an icon and its count, with Approval behind More, and the desk
    # takes its reservations back on return.
    button_widths = (
        "() => ['.lf-threads-toggle', '.lf-signoff'].map(selector => {"
        " const el = document.querySelector(selector); const style = getComputedStyle(el);"
        " return el.offsetWidth - parseFloat(style.paddingLeft)"
        " - parseFloat(style.paddingRight); })"
    )
    resized(page, 1200, 844)
    wide_widths = page.evaluate(button_widths)
    resized(page, 320, 844)
    resized(page, 1200, 844)
    assert page.evaluate(button_widths) == pytest.approx(wide_widths, abs=1), (
        "button reservations did not return to their wide measurements after the "
        "covering row was left"
    )

    def assert_primary_reach(width):
        resized(page, width, 844)
        # A phone's one row holds the status, Threads and More; Approval leads More.
        primary = ".lf-signoff" if width > 480 else ".lf-banner-more"
        boxes = page.evaluate(
            """(primary) => Object.fromEntries(
              ['.lf-banner-status', '.lf-threads-toggle', primary].map(selector => {
                const r = document.querySelector(selector).getBoundingClientRect();
                return [selector, {left: r.left, right: r.right, width: r.width,
                                   top: r.top, bottom: r.bottom, height: r.height}];
              }))""",
            primary,
        )
        for selector, box in boxes.items():
            assert box["width"] > 0 and box["height"] > 0, (
                f"{selector} collapsed at {width}px: {box}"
            )
            assert box["left"] >= 0 and box["right"] <= width, (
                f"{selector} is outside the first {width}px view: {box}"
            )
        # The narrow face a phone held upright wears: forty-pixel controls.
        if width <= 480:
            assert boxes[".lf-threads-toggle"]["height"] >= 40
            assert boxes[".lf-banner-more"]["height"] >= 40
        assert root_overflow(page) == 0, (
            "the banner made the page itself scroll sideways"
        )
        # Nothing hangs off the fixed primary row's own edge at any width.
        assert page.evaluate(
            "() => { const actions = document.querySelector('.lf-banner-actions');"
            "        return actions.scrollWidth <= actions.clientWidth + 1; }"
        ), f"the row at {width}px still hid a control off its own edge"

    for width in (320, 390, 768, 900, 1200):
        assert_primary_reach(width)

    # The keyboard walks the row it can see, Threads and More, and Approval is the first
    # control More opens to.
    resized(page, 320, 844)
    actions = page.locator(".lf-banner-actions")
    actions.evaluate("el => { el.tabIndex = -1; el.focus(); }")
    walk = []
    for _ in range(6):
        page.keyboard.press("Tab")
        here = page.evaluate(
            """() => {
              const el = document.activeElement;
              return el && el.closest('.lf-banner-actions') ? el.className : null;
            }"""
        )
        if here is None:
            break
        walk.append(here.split(" ").pop())
    assert walk[:2] == [
        "lf-threads-toggle",
        "lf-banner-more",
    ], f"a Tab walk across the phone row missed the reading loop: {walk}"
    page.locator(".lf-banner-more").focus()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-banner-menu > :visible").first).to_have_class(
        re.compile(r"\blf-signoff\b")
    )
    page.keyboard.press("Escape")
    ring_room = """el => {
      const toolbar = el.parentElement.getBoundingClientRect();
      const button = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      const outset = parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset);
      return {top: button.top - outset - toolbar.top,
              left: button.left - outset - toolbar.left,
              right: toolbar.right - button.right - outset,
              bottom: toolbar.bottom - button.bottom - outset};
    }"""
    room = page.locator(".lf-threads-toggle").evaluate(ring_room)
    assert all(space >= -0.01 for space in room.values()), (
        f"the phone row clipped its focused control's ring: {room}"
    )

    # Every secondary contribution stays behind the door in registration order. The
    # identities do not matter to the layout contract; register them through the toolbar's
    # internal contribution boundary, just as asynchronous Ask and Page Map owners do.
    page.evaluate(
        """async () => {
          const toolbar = await window.__lfRuntimeImport('/runtime/banner-toolbar.js');
          for (let i = 0; i < 7; i++) {
            const button = document.createElement('button');
            button.className = 'lf-ui lf-btn lf-secondary-destination';
            button.textContent = `Secondary destination ${i + 1}`;
            toolbar.registerBannerControl({
              key: `test-secondary-${i}`,
              control: button,
              rank: toolbar.BANNER_CONTROL_RANK.blanket + (i + 1) / 10,
              row: { label: button.textContent, group: "page" },
            });
          }
        }"""
    )
    behind = {}
    for width in (768, 900, 1600):
        assert_primary_reach(width)
        behind[width] = page.locator(".lf-banner-menu > *").count()
        expect(page.locator(".lf-banner-more")).to_be_visible()
    assert len(set(behind.values())) == 1, (
        f"secondary controls changed seats with viewport width: {behind}"
    )
    # Take the synthetic controls away. The Leaf version remains deliberately behind
    # the door at every width. The toolbar retains
    # each registered native island in one Lit root; hiding one changes its presentation,
    # not its identity or connection to the document.
    page.evaluate(
        """async () => {
          const toolbar = await window.__lfRuntimeImport('/runtime/banner-toolbar.js');
          for (const control of document.querySelectorAll('.lf-secondary-destination'))
            toolbar.showBannerControl(control, false);
        }"""
    )
    resized(page, 1600, 844)
    expect(page.locator(".lf-banner-more")).to_be_visible()
    # Open the door and read what stands behind it rather than counting the menu's
    # markup: the toolbar keeps a control registered for another device in that list with
    # no presence, so inventory and what the user meets are different readings.
    page.locator(".lf-banner-more").click()
    expect(page.locator(".lf-banner-menu")).to_be_visible()
    expect(page.locator(".lf-banner-menu > .lf-version")).to_be_visible()
    expect(page.locator(".lf-banner-menu > .lf-banner-copy")).to_be_visible()
    expect(page.locator(".lf-banner-menu > .lf-share")).to_be_visible()
    # More also holds page commands; their number can grow without making the
    # retired synthetic destinations reachable again.
    expect(page.locator(".lf-banner-menu > .lf-secondary-destination")).to_have_count(7)
    expect(
        page.locator(".lf-banner-menu > .lf-secondary-destination:visible")
    ).to_have_count(0)
    page.keyboard.press("Escape")
    expect(page.locator(".lf-banner-menu")).to_be_hidden()
    expect(page.locator(".lf-banner-more")).to_be_visible()

    # The covering Threads panel locks the page behind it, and the row is no longer a
    # side door around that lock: a wheel over it reaches the document scrollport, which
    # the covering sheet has already stopped.
    resized(page, 320, 844)
    page.locator(".lf-threads-toggle").click()
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    locked = actions.evaluate(
        """actions => {
          document.scrollingElement.scrollTop = 400;
          const before = document.scrollingElement.scrollTop;
          const event = new WheelEvent('wheel', {
            bubbles: true, cancelable: true, deltaY: 120
          });
          actions.dispatchEvent(event);
          return {before, after: document.scrollingElement.scrollTop,
                  overflow: getComputedStyle(document.scrollingElement).overflowY,
                  scrolled: actions.scrollLeft};
        }"""
    )
    assert locked == {
        "before": 400,
        "after": 400,
        "overflow": "hidden",
        "scrolled": 0,
    }, f"the action row bypassed the covering panel's page lock: {locked}"
    page.get_by_role("button", name="Close threads").click()
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    page.close()

    # A pinned page keeps Latest in its menu seat before it first has news. The door says the page has
    # been replaced while it holds that one, because news nobody can see is not news.
    pinned = open_page(browser, url, pin=True)
    resized(pinned, 320, 844)
    expect(pinned.locator(".lf-latest-chip")).to_be_hidden()
    assert pinned.locator(".lf-latest-chip").evaluate("el => el.offsetWidth") == 0
    # A control the page has taken away is taken away wherever it stands. The row's own
    # rules state display for its box, and a rule that states it without excluding the
    # hidden ones puts an absent destination back between the user and a real one.
    expect(pinned.locator(".lf-page-map-toggle")).to_be_hidden()
    assert pinned.locator(".lf-page-map-toggle").evaluate("el => el.offsetWidth") == 0
    # The page asks for sign-off, so on a phone More's dot may already stand for the
    # approval behind it; its name says which news the dot carries.
    expect(pinned.locator(".lf-banner-more")).not_to_have_attribute(
        "aria-label", re.compile(", new")
    )
    stamp_page(serve.page_dir, html, "two")
    expect(pinned.locator(".lf-latest-chip")).to_have_class(
        re.compile(r"lf-news-shown")
    )
    seen = pinned.evaluate(
        """() => {
          const chip = document.querySelector('.lf-latest-chip');
          const door = document.querySelector('.lf-banner-more');
          return {onTheRow: chip.checkVisibility({visibilityProperty: true}),
                  behindTheDoor: door.hasAttribute('data-lf-news')
                    && door.getAttribute('aria-label').includes(', new'),
                  doorName: door.getAttribute('aria-label'),
                  shown: chip.offsetWidth, needed: chip.scrollWidth};
        }"""
    )
    assert not seen["onTheRow"] and seen["behindTheDoor"], (
        f"the phone banner took its page news out of the user's sight: {seen}"
    )
    positions = pinned.evaluate(
        """async () => {
          const toolbar = await window.__lfRuntimeImport('/runtime/banner-toolbar.js');
          const chip = document.querySelector('.lf-latest-chip');
          const threads = document.querySelector('.lf-threads-toggle');
          const door = document.querySelector('.lf-banner-more');
          const x = () => threads.getBoundingClientRect().x;
          const shown = x();
          toolbar.showNews(chip, false);
          await Promise.resolve();
          const quiet = {
            x: x(), door: door.checkVisibility(),
            news: door.getAttribute('aria-label').includes(', new'),
          };
          toolbar.showNews(chip, true);
          await Promise.resolve();
          return {shown, quiet, returned: x()};
        }"""
    )
    assert positions["quiet"]["door"] and not positions["quiet"]["news"], positions
    assert positions["quiet"]["x"] == pytest.approx(positions["shown"], abs=0.01)
    assert positions["returned"] == pytest.approx(positions["shown"], abs=0.01)
    pinned.locator(".lf-banner-more").click()
    expect(pinned.locator(".lf-banner-menu")).to_be_visible()
    chip_size = pinned.locator(".lf-latest-chip").evaluate(
        "el => ({shown: el.offsetWidth, needed: el.scrollWidth})"
    )
    assert chip_size["shown"] >= chip_size["needed"], (
        f"the phone menu news control clipped its words: {chip_size}"
    )
    pinned.keyboard.press("Escape")
    resized(pinned, 1200, 844)
    pinned.locator(".lf-banner-more").click()
    news_size = pinned.locator(".lf-latest-chip").evaluate(
        "el => ({shown: el.offsetWidth, needed: el.scrollWidth})"
    )
    assert news_size["shown"] >= news_size["needed"], (
        f"the desktop menu news control clipped its words: {news_size}"
    )


def test_banner_status_is_compact_with_accessible_details(browser, serve, other_leaf):
    """Compact status preserves full detail through keyboard and pointer disclosure."""
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    stamp_page(serve.page_dir, html, "two")
    panel_comment(serve.page_dir, "Is this ready?", author="agent")
    page = open_page(browser, url)
    resized(page, 1280, 900)
    # The complete real action set, wherever the fold has put each of them: what this is
    # about is the pressure that set puts on the sentence beside it.
    on_the_row = page.evaluate(BANNER_ORDER)
    for wanted in ("All pages", "Questions", "Accept all", "v1", "Approve version"):
        assert any(wanted in name for name in on_the_row), (
            f"{wanted} was not on the row, so the fixture is short of the crowding this "
            f"test is about: {on_the_row}"
        )

    detail = (
        "Checking the whole page and its open threads before recording every update. "
        * 4
    )
    working(serve.page_dir, detail)
    told(page)
    expect(page.locator(".lf-status-detail")).to_contain_text(detail.strip())
    door = page.locator(".lf-status-button")
    explanation = page.locator(".lf-status-detail")
    page.evaluate("scrollTo(0, document.documentElement.scrollHeight)")
    door.focus()
    page.keyboard.press("Enter")
    expect(explanation).to_be_visible()
    expect(explanation).to_be_focused()
    boxes = explanation.evaluate(
        "detail => ({detail: detail.getBoundingClientRect().top, "
        "banner: document.querySelector('.lf-banner').getBoundingClientRect().bottom})"
    )
    assert boxes["detail"] == pytest.approx(boxes["banner"] + 8, abs=2), boxes
    detail_text = page.evaluate(
        """() => {
          const detail = document.querySelector('.lf-status-detail');
          window.__lfStatusNodes = {
            button: document.querySelector('.lf-status-button'),
            detail,
            dot: document.querySelector('.lf-banner .lf-dot'),
            text: [...detail.childNodes].find(
              (node) => node.nodeType === Node.TEXT_NODE && node.data.trim(),
            ),
          };
          return window.__lfStatusNodes.text.data;
        }"""
    )
    working(serve.page_dir, detail)
    told(page)
    survived = page.evaluate(
        """() => ({
          button: window.__lfStatusNodes.button === document.querySelector('.lf-status-button'),
          detail: window.__lfStatusNodes.detail === document.querySelector('.lf-status-detail'),
          dot: window.__lfStatusNodes.dot === document.querySelector('.lf-banner .lf-dot'),
          focused: document.activeElement === window.__lfStatusNodes.detail,
          open: window.__lfStatusNodes.detail.matches(':popover-open'),
          text: window.__lfStatusNodes.text.parentNode === window.__lfStatusNodes.detail
            ? window.__lfStatusNodes.text.data
            : null,
        })"""
    )
    assert survived == {
        "button": True,
        "detail": True,
        "dot": True,
        "focused": True,
        "open": True,
        "text": detail_text,
    }, (
        "an unchanged status poll disturbed the native disclosure or rebuilt its "
        f"unchanged detail: {survived}"
    )

    # The global command reference follows native modal entry: the contextual auto
    # popover closes, while later status presentation leaves the modal itself alone.
    page.keyboard.press("?")
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    expect(explanation).to_be_hidden()
    working(serve.page_dir, detail)
    told(page)
    expect(reference).to_be_visible()
    expect(explanation).to_be_hidden()
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-shortcut-bar")).to_have_attribute(
        "data-lf-expanded", "false"
    )
    for width in (1280, 841, 390):
        resized(page, width, 900)
        read = page.evaluate(STATUS_FIT)
        assert read["across"]["shown"] > 0, read
        assert read["down"]["shown"] == pytest.approx(read["lineHeight"], abs=1), read
        assert read["down"]["shown"] == read["down"]["needed"], read
        assert read["ellipsis"] == "ellipsis", read
        assert read["text"] == f"Agent working — {detail}", read
        assert detail.strip() in read["title"], read
        assert read["actions"]["shown"] >= read["actions"]["needed"], read
        expect(door).to_have_attribute("aria-describedby", "lf-status-detail")
        door.focus()
        page.keyboard.press("Enter")
        expect(explanation).to_be_visible()
        expect(explanation).to_be_focused()
        expect(explanation).to_contain_text(detail.strip())
        box = explanation.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= width, box
        page.keyboard.press("Escape")
        expect(explanation).to_be_hidden()
        expect(door).to_be_focused()
        page.keyboard.press("Space")
        expect(explanation).to_be_visible()
        page.keyboard.press("Escape")
        door.click()
        expect(explanation).to_be_visible()
        page.mouse.click(100, 600)
        expect(explanation).to_be_hidden()
    resized(page, 1280, 900)

    # Above the floor the sentence, the queue counts and the fixed primary controls
    # consume the row exactly.
    room = page.evaluate(
        """() => {
          const banner = document.querySelector('.lf-banner');
          const style = getComputedStyle(banner);
          const inner = banner.clientWidth
            - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
          const items = [...banner.children].filter((node) => node.checkVisibility());
          return {inner, names: items.map((node) => node.className),
                  widths: items.map((node) => node.getBoundingClientRect().width),
                  gap: parseFloat(style.columnGap)};
        }"""
    )
    assert "lf-status-queues" in room["names"], room
    assert sum(room["widths"]) + room["gap"] * (len(room["widths"]) - 1) == (
        pytest.approx(room["inner"], abs=1)
    ), f"the banner left room standing between its status and its controls: {room}"

    # The fixed primary run keeps complete words and secondary actions remain in More.
    resized(page, 1024, 900)
    crowded = page.evaluate(
        """() => {
          const actions = document.querySelector('.lf-banner-actions');
          const menu = document.querySelector('.lf-banner-menu');
          const more = document.querySelector('.lf-banner-more');
          const words = (control) => ({
            name: (control.getAttribute('aria-label') || control.textContent).trim(),
            shown: control.clientWidth, needed: control.scrollWidth});
          return {
            row: [...actions.children]
              .filter(c => c !== more && c.getClientRects().length).map(words),
            secondary: menu.children.length};
        }"""
    )
    assert crowded["secondary"], (
        f"the fixture registered no secondary controls: {crowded}"
    )
    clipped = [c for c in crowded["row"] if c["shown"] < c["needed"]]
    assert not clipped, f"the crowded row compressed the controls it kept: {clipped}"
    assert root_overflow(page) == 0, "the crowded row widened the document"

    # The open panel and a version popup can overlap broadly. Once native focus leaves the
    # transient menu, it closes before painting over the next keyboard destination.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-filter-toggle").click()
    open_versions(page)
    menu = page.locator(".lf-version-menu")
    expect(menu).to_be_visible()
    selected_state = page.get_by_role("button", name=re.compile(r"^Open(?: \(|$)"))
    expect(selected_state).to_have_attribute("aria-pressed", "true")
    reached_state = False
    for _ in range(20):
        if selected_state.evaluate("el => el.matches(':focus-within')"):
            reached_state = True
            break
        page.keyboard.press("Tab")
    assert reached_state, "native Tab never reached the selected thread-status toggle"
    expect(selected_state).to_be_focused()
    expect(menu).to_be_hidden()
    page.locator(".lf-threads-toggle").click()
    panel_settled(page, open=False)
    page.close()

    # A control that settles its own decisions disappears while it still owns focus. Hand
    # the user to the next standing control instead of silently dropping them on body.
    page = open_page(browser, url.replace("/v1.html", "/v2.html"), pin=True)
    resized(page, 1200, 900)
    stamp_page(serve.page_dir, html, "three")
    expect(page.locator(".lf-latest-chip")).to_have_class(re.compile(r"lf-news-shown"))
    answer_all = banner_control(page, ".lf-answer-all")
    # The blanket answer decides its decisions one at a time, so the press owes one round
    # trip per decision the control counts. Read that number off the control's own face
    # rather than writing the fixture's arithmetic out here.
    owed = int(re.search(r"\((\d+)\)", answer_all.text_content()).group(1))
    assert owed > 1, (
        f"the fixture left the blanket answer a single trip, not a sequence: {owed}"
    )
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    answer_all.focus()
    page.keyboard.press("Enter")
    holding(page, held, 1, "the blanket answer")
    expect(answer_all).to_have_attribute("aria-disabled", "true")
    expect(answer_all).to_be_focused()
    answer_all.dispatch_event("click")
    assert _traffic(page).sends == 1, "one blanket-answer press became two event runs"
    held[0].continue_()
    page.unroute("**/api/event")
    # Released, the press spends a whole trip on each remaining decision, so the last is
    # still in flight when the first has settled. Say so here rather than letting the
    # hide assertion absorb the transport: its budget is one repaint's worth, three
    # sequential trips outlast it on a loaded machine, and the red then reads as a
    # control that never went instead of a wait that was never stated.
    # `test_accept_all_decides_every_pending_suggestion` stages the same sequence through
    # each widget's own settle; this test is about where focus lands, so it names the
    # outbox instead.
    _until(
        page,
        lambda traffic: traffic.sends == owed and not traffic.pending,
        f"settled every one of the {owed} answers the blanket press owed",
    )
    expect(answer_all).to_be_hidden()
    landed = page.evaluate(
        """() => {
          const el = document.activeElement;
          return el && el.closest('.lf-banner-actions, .lf-banner-menu')
            ? el.className : (el && el.tagName);
        }"""
    )
    assert "lf-btn" in (landed or ""), (
        f"the focus transfer left the user on {landed!r} rather than on a control"
    )


def test_share_copies_access_after_a_bare_reload(browser, serve):
    """The copied address opens the viewed version and passage in a fresh browser."""
    url = serve(LONG_PAGE)
    page = open_page(browser, url + "&view=reading#p30")
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    expect(page).not_to_have_url(re.compile(r"[?&]t="))
    page.reload()
    wait_until_ready(page)
    page.get_by_role("button", name="More page controls", exact=True).click()
    share = page.locator(".lf-share > summary")
    for _ in range(15):
        if share.evaluate("element => element === document.activeElement"):
            break
        page.keyboard.press("Tab")
    expect(share).to_be_focused()
    page.keyboard.press("Enter")
    link = page.get_by_role("textbox", name="Share link", exact=True)
    expect(link).to_have_value(re.compile(r"[?&]t="))
    page.keyboard.press("Tab")
    expect(link).to_be_focused()
    page.keyboard.press("Tab")
    copy = page.get_by_role("button", name="Copy link", exact=True)
    expect(copy).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-notice")).to_have_text("Link copied")
    copied = page.evaluate("navigator.clipboard.readText()")
    assert parse_qs(urlsplit(copied).query) == {
        "t": parse_qs(urlsplit(url).query)["t"],
        "view": ["reading"],
    }
    assert urlsplit(copied).path == urlsplit(url).path
    assert urlsplit(copied).fragment == "p30"
    expect(copy).to_be_focused()
    page.keyboard.press("Escape")
    expect(
        page.get_by_role("button", name="More page controls", exact=True)
    ).to_be_focused()
    with browser.new_context() as context:
        recipient = open_page(browser, copied, context=context)
        expect(recipient.locator("#p30")).to_be_in_viewport()
        expect(recipient).not_to_have_url(re.compile(r"[?&]t="))
    resized(page, 390, 844)
    page.get_by_role("button", name=re.compile(r"^More page controls")).click()
    page.evaluate("navigator.clipboard.writeText('before sharing')")
    share.click()
    # The copy button ignores a press during its second of success feedback, which a
    # quick journey reaches before the first copy's feedback ends.
    expect(page.locator(".lf-share .lf-banner-copy")).to_have_js_property(
        "isCopying", False
    )
    copy.click()
    # The first copy's notice can still stand, so the clipboard says when this one
    # has landed.
    wait_for(
        lambda: page.evaluate("navigator.clipboard.readText()"),
        lambda text: text == copied,
        failure="the second copy never reached the clipboard",
    )
    expect(page.locator(".lf-notice")).to_have_text("Link copied")
    # Plain HTTP outside loopback has no clipboard API; the link remains usable.
    page.add_init_script(
        "Object.defineProperty(navigator, 'clipboard', {value: undefined})"
    )
    page.reload()
    wait_until_ready(page)
    page.get_by_role("button", name=re.compile(r"^More page controls")).click()
    share.click()
    expect(link).to_have_value(copied)
    expect(copy).to_be_hidden()


def test_preview_diagnostics_keep_their_fixed_banner_overflow_seat(browser, serve):
    """Developer diagnostics stay behind More at every width."""
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    # A long checkout name proves secondary words can grow without taking row space.
    url = serve(
        html,
        preview={
            "kind": "example",
            "example": "feature-gallery",
            "checkout": "leaf.status-floor-and-selection",
            "commit": "c79736ebfcc7",
            "dirty": True,
            "interaction": "author",
            "started": "2026-09-06T12:00:00+00:00",
        },
    )
    panel_comment(serve.page_dir, "Is this ready?", author="agent")
    page = open_page(browser, url)
    expect(page.locator(".lf-preview")).to_have_count(1)

    for width in (320, 841, 1024, 1440):
        resized(page, width, 900)
        standing = page.evaluate(
            """() => {
              const chip = document.querySelector('.lf-preview');
              const menu = document.querySelector('.lf-banner-menu');
              return {inStatus: Boolean(chip.closest('.lf-banner-status')),
                      parent: chip.parentElement.className,
                      inMenu: menu.contains(chip),
                      onRow: chip.getClientRects().length > 0,
                      shown: chip.clientWidth, needed: chip.scrollWidth};
            }"""
        )
        assert not standing["inStatus"], (
            f"at {width} the preview chip stood inside the status box: {standing}"
        )
        assert standing["inMenu"] and not standing["onRow"], (
            f"at {width} preview diagnostics left the banner overflow: {standing}"
        )
    expect(page.locator(".lf-banner-menu .lf-preview")).to_have_count(1)
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.get_by_role("button", name="More page controls", exact=True).click()
    copy = page.get_by_role("button", name="Copy preview diagnostics", exact=True)
    copy.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-notice")).to_have_text("Copied preview diagnostics")
    copied = page.evaluate("() => navigator.clipboard.readText()")
    assert copied.startswith("Leaf preview\nexample: feature-gallery\n")
    assert "checkout: leaf.status-floor-and-selection" in copied
    assert "t=" not in copied
    expect(copy).to_be_focused()
    page.close()

    # A published page uses the same one-line status and complete hover text.
    site = open_page(
        browser,
        serve(
            leaf_page("Website example", "<h1>Website example</h1>"),
            website_publication={
                "kind": "example",
                "agent": "Leaf guide",
                "install_url": "/#install",
            },
        ),
    )
    resized(site, 900, 900)
    expect(site.locator(".lf-status-text")).to_have_text(WEBSITE_LINE)
    read = site.evaluate(STATUS_FIT)
    assert read["down"]["shown"] == pytest.approx(read["lineHeight"], abs=1), read
    assert read["title"] == WEBSITE_LINE, read
    for width in (900, 390):
        resized(site, width, 900)
        examples = site.get_by_role("link", name="Other examples")
        expect(examples).to_be_visible()
        expect(examples).to_have_attribute("href", "/examples/")
        install = site.get_by_role("link", name="Install Leaf")
        for link in (examples, install):
            expect(link).to_be_visible()
            bounds = link.bounding_box()
            assert 0 <= bounds["x"] < bounds["x"] + bounds["width"] <= width, bounds
            assert link.evaluate("el => el.clientWidth === el.scrollWidth")
            link.focus()
            expect(link).to_be_focused()


def test_a_phone_banner_keeps_fixed_primary_and_menu_seats(browser, serve, other_leaf):
    """A phone's banner is one row, the status, Threads and More, and every other
    control, Approval first, is one keyboard-reachable menu behind More, which wears a
    dot while approval is open."""
    html = SUGGESTION_PAGE.replace(
        "<title>suggestions</title>",
        '<title>suggestions</title>\n<meta name="lf-review" content="sign-off">',
    )
    url = serve(html)
    panel_comment(serve.page_dir, "Is this ready?", author="agent")
    page = open_page(browser, url)
    resized(page, 390, 800)

    toolbar = page.evaluate(
        """() => {
          const actions = document.querySelector('.lf-banner-actions');
          return {shown: actions.clientWidth, needed: actions.scrollWidth};
        }"""
    )
    assert toolbar["shown"] == toolbar["needed"], (
        f"the phone row still hid controls off its own edge: {toolbar}"
    )
    assert root_overflow(page) == 0, (
        "the phone banner made the page itself scroll sideways"
    )
    more = page.locator(".lf-banner-more")
    expect(more).to_be_visible()
    secondary = page.locator(".lf-banner-menu .lf-btn")
    assert secondary.count() > 0, "the fixture has no secondary menu to walk"
    # The row keeps Threads, its icon and count, and the door; everything else is
    # behind it, led by Approval. The suggestions hold approval, so More wears no dot
    # for it (test_more_wears_a_dot_while_a_press_would_approve).
    expect(page.locator(".lf-banner-actions > :visible")).to_have_count(2)
    expect(page.locator(".lf-banner-actions > .lf-threads-toggle")).to_be_visible()
    expect(page.locator(".lf-threads-toggle .lf-threads-icon")).to_be_visible()
    expect(page.locator(".lf-threads-toggle .lf-threads-label")).to_be_hidden()
    count = page.locator(".lf-threads-toggle").evaluate(
        "control => getComputedStyle(control, '::before').content"
    )
    assert re.fullmatch(r'"\d+"', count), count
    expect(page.locator(".lf-banner-menu > .lf-btn").first).to_have_class(
        re.compile(r"\blf-signoff\b")
    )
    expect(more).not_to_have_attribute("aria-label", re.compile("approval"))
    assert page.locator(".lf-banner").bounding_box()["height"] == pytest.approx(
        52, abs=0.5
    )
    # Every secondary control, from the keyboard, through that one door. The press is the
    # popover's own invoker, so the menu opens and puts the user on its first control
    # without anything here focusing it for them.
    page.evaluate(RELEASE_FOCUS)
    threads = page.locator(".lf-threads-toggle")
    for _ in range(20):
        page.keyboard.press("Tab")
        if threads.evaluate("control => control === document.activeElement"):
            break
    expect(threads).to_be_focused()
    page.keyboard.press("Tab")
    expect(more).to_be_focused()
    assert more.evaluate("control => control.matches(':focus-visible')")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-banner-menu")).to_be_visible()
    want = secondary.evaluate_all(
        """els => els.filter(el => el.checkVisibility() && !el.disabled)
                     .map(el => (el.getAttribute('aria-label') || el.textContent).trim())"""
    )
    assert len(want) >= 2, f"only {want} stand in More, which walks nothing"
    menu = page.locator(".lf-banner-menu").bounding_box()
    assert menu["x"] >= 0 and menu["x"] + menu["width"] <= 390, menu
    assert menu["width"] <= 390 - 16, menu
    bulk = page.locator(".lf-banner-menu > .lf-answer-all:visible")
    assert bulk.count() > 0
    for control in bulk.all():
        assert control.bounding_box()["width"] >= menu["width"] - 24
    assert root_overflow(page) == 0
    # The suggestions hold approval, so More opens on the control after it, and
    # Shift+Tab reaches Approval and the reason it refuses a press.
    approval = page.locator(".lf-banner-menu > .lf-signoff")
    expect(approval).to_have_attribute("aria-disabled", "true")
    page.keyboard.press("Shift+Tab")
    expect(approval).to_be_focused()
    expect(approval).to_have_attribute("aria-description", re.compile(r"\S"))
    page.keyboard.press("Tab")
    want.remove("Approve version")
    reached = []
    for _ in range(len(want) * 3):
        here = page.evaluate(
            """() => {
              const el = document.activeElement;
              if (!el || !el.closest('.lf-banner-menu')) return null;
              return (el.getAttribute('aria-label') || el.textContent).trim();
            }"""
        )
        if here is None:
            break
        if here not in reached:
            reached.append(here)
        if len(reached) == len(want):
            break
        page.keyboard.press("Tab")
    assert reached == want, (
        f"a Tab walk through the phone banner's menu reached {reached}, not {want}"
    )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-banner-menu")).to_be_hidden()
    expect(more).to_be_focused()

    # Crossing the phone width reseats the refused Approval, a Tab stop like any
    # other, and focus goes with it: to the door while More is shut, and to Approval
    # itself wherever it stands visible.
    refused = page.locator(".lf-signoff")
    resized(page, 1200, 800)
    refused.focus()
    resized(page, 390, 800)
    expect(more).to_be_focused()
    page.keyboard.press("Enter")
    refused.focus()
    resized(page, 1200, 800)
    expect(page.locator(".lf-banner-actions > .lf-signoff")).to_be_visible()
    expect(refused).to_be_focused()


def test_coarse_pointer_resize_reach_stays_reachable_without_trapping_scroll(
    browser, serve
):
    """A touch edge is a reachable local grip, not a scroll-blocking invisible wall."""
    context = browser.new_context(
        viewport={"width": 390, "height": 800}, has_touch=True
    )
    page = open_page(browser, serve(MANY_ASKS_PAGE, comments=30), context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches")
    cdp = context.new_cdp_session(page)

    def edge_geometry(region, edge):
        return page.evaluate(
            """([regionSelector, edgeSelector]) => {
                  const regionEl = document.querySelector(regionSelector);
                  const edgeEl = document.querySelector(edgeSelector);
                  const region = regionEl.getBoundingClientRect();
                  const edge = edgeEl.getBoundingClientRect();
                  const before = getComputedStyle(edgeEl, '::before');
                  const side = edgeEl.dataset.lfSide;
                  const lineWidth = parseFloat(before.width);
                  const lineCenter = side === 'right'
                    ? edge.left + parseFloat(before.left) + lineWidth / 2
                    : edge.right - parseFloat(before.right) - lineWidth / 2;
                  const seamCenter = side === 'right'
                    ? region.left + regionEl.clientLeft / 2
                    : region.right - parseFloat(getComputedStyle(regionEl).borderRightWidth) / 2;
                  const contentEdge = side === 'right'
                    ? region.left + regionEl.clientLeft
                    : region.right - parseFloat(getComputedStyle(regionEl).borderRightWidth);
                  return {region: {left: region.left, right: region.right},
                          edge: {left: edge.left, right: edge.right,
                                 top: edge.top, bottom: edge.bottom,
                                 width: edge.width, height: edge.height,
                                 hidden: edgeEl.hidden,
                                 min: Number(edgeEl.getAttribute('aria-valuemin')),
                                 max: Number(edgeEl.getAttribute('aria-valuemax')),
                                 now: Number(edgeEl.getAttribute('aria-valuenow'))},
                          contentEdge, lineCenter, seamCenter,
                          lineOpacity: Number(before.opacity),
                          viewport: document.documentElement.clientWidth};
                }""",
            [region, edge],
        )

    def swipe(x, y, *, dx=0, dy=-140):
        _touch_drag(cdp, x, y, dx=dx, dy=dy)

    def drag(edge, dx):
        x = round((edge["left"] + edge["right"]) / 2)
        y = round((edge["top"] + edge["bottom"]) / 2)
        _touch_drag(cdp, x, y, dx=dx, steps=1)
        rendered(page)

    # At the product's 320px floor the comment sheet has no possible width to move
    # through, so it offers no inert separator. A user standing on the grip lands on
    # its surviving close control before it disappears. The Questions panel stands on
    # the same edge at the same floor, so its grip is gone there too.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    comments_edge = page.locator(".lf-thread-panel > .lf-edge")
    comments_edge.focus()
    expect(comments_edge).to_be_focused()
    resized(page, 320, 800)
    assert comments_edge.evaluate("edge => edge.hidden")
    expect(page.get_by_role("button", name="Close threads")).to_be_focused()
    assert comments_edge.get_attribute("aria-valuemin") == comments_edge.get_attribute(
        "aria-valuemax"
    )
    threads = page.locator(".lf-threads")
    threads.evaluate("box => { box.scrollTop = 0; }")
    expect(page.locator(".lf-thread-filter-toggle")).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(page.locator(".lf-thread-filter-toggle")).to_be_visible()
    width_before = page.evaluate(
        "() => getComputedStyle(document.documentElement)"
        ".getPropertyValue('--lf-thread-panel-width')"
    )
    threads_box = threads.bounding_box()
    swipe(
        threads_box["x"] + threads_box["width"] / 2,
        threads_box["y"] + min(80, threads_box["height"] / 2),
    )
    page.wait_for_function("() => document.querySelector('.lf-threads').scrollTop > 0")
    assert (
        page.evaluate(
            "() => getComputedStyle(document.documentElement)"
            ".getPropertyValue('--lf-thread-panel-width')"
        )
        == width_before
    )

    page.get_by_role("button", name="Close threads").click()
    panel_settled(page, open=False)
    banner_control(page, ".lf-queue").click()
    panel_settled(page, open=False)
    expect(page.locator(".lf-queue-panel")).to_have_class(re.compile(r"\bopen\b"))
    page_at_rest(page)
    narrow_decisions = edge_geometry(".lf-queue-panel", ".lf-queue-panel > .lf-edge")
    assert narrow_decisions["edge"]["hidden"], narrow_decisions
    page.keyboard.press("Escape")
    expect(page.locator(".lf-queue-panel")).not_to_have_class(re.compile(r"\bopen\b"))

    # Exercise both panels the right edge holds, in different layout postures. A swipe
    # beside the visible grip scrolls its list without moving the boundary; a horizontal
    # drag on the grip does move it and releases the sizing posture.
    for (
        name,
        width,
        open_button,
        region_selector,
        edge_selector,
        list_selector,
        dx,
    ) in (
        (
            "comments",
            390,
            ".lf-threads-toggle",
            ".lf-thread-panel",
            ".lf-thread-panel > .lf-edge",
            ".lf-threads",
            48,
        ),
        (
            "asks",
            900,
            ".lf-queue",
            ".lf-queue-panel",
            ".lf-queue-panel > .lf-edge",
            ".lf-queue-panel .lf-drawer-list",
            36,
        ),
    ):
        resized(page, width, 800)
        if open_button == ".lf-queue":
            banner_control(page, open_button).click()
        else:
            page.locator(open_button).click()
        if name == "comments":
            panel_settled(page)
        else:
            panel_settled(page, open=False)
            expect(page.locator(region_selector)).to_have_class(re.compile(r"\bopen\b"))
            page_at_rest(page)
        reading = edge_geometry(region_selector, edge_selector)
        edge = reading["edge"]
        assert edge["width"] >= 43.9 and edge["height"] >= 43.9, reading
        assert edge["left"] >= -0.1
        assert edge["right"] <= reading["viewport"] + 0.1
        assert edge["left"] >= reading["contentEdge"] - 0.1, reading
        assert abs(reading["lineCenter"] - reading["seamCenter"]) <= 0.6, (
            f"the {name} grip's line left the panel seam: {reading}"
        )
        assert reading["lineOpacity"] > 0, f"the {name} touch grip was invisible"
        edge_control = page.locator(edge_selector)
        edge_control.evaluate("edge => edge.blur()")
        # Every thread title Tab reaches opens its thread, so the walk crosses each
        # thread's own controls on the way to the grip.
        for _ in range(400):
            page.keyboard.press("Tab")
            if edge_control.evaluate("edge => document.activeElement === edge"):
                break
        else:
            raise AssertionError(f"the keyboard never reached the {name} touch grip")
        standing = standing_ring(page)
        assert standing and not standing["cuts"] and not standing["covers"], (
            f"the {name} touch grip drew a clipped focus ring: {standing}"
        )
        mid_x = (edge["left"] + edge["right"]) / 2
        mid_y = (edge["top"] + edge["bottom"]) / 2
        assert page.evaluate(
            "([x, y]) => document.elementFromPoint(x, y)?.classList"
            ".contains('lf-edge')",
            [mid_x, mid_y],
        )
        assert not page.evaluate(
            "([x, y]) => document.elementFromPoint(x, y)?.classList"
            ".contains('lf-edge')",
            [mid_x, edge["top"] - 24],
        ), f"the {name} touch edge still trapped the whole sheet height"

        scroll_box = page.locator(list_selector)
        scroll_box.evaluate("box => { box.scrollTop = 0; }")
        assert scroll_box.evaluate("box => box.scrollHeight > box.clientHeight"), (
            f"the {name} list has no scroll range to exercise"
        )
        before = edge["now"]
        swipe(mid_x, edge["top"] - 24)
        page.wait_for_function(
            "selector => document.querySelector(selector).scrollTop > 0",
            arg=list_selector,
        )
        assert int(page.locator(edge_selector).get_attribute("aria-valuenow")) == before

        drag(edge, dx)
        after = int(page.locator(edge_selector).get_attribute("aria-valuenow"))
        assert edge["min"] <= after <= edge["max"]
        assert after < before, (
            f"the {name} grip did not narrow its region: {before} → {after}"
        )


@pytest.mark.parametrize(
    "archetype", CONTROL_ARCHETYPES, ids=lambda archetype: archetype["name"]
)
def test_each_control_archetype_holds_its_neighbours_still(browser, serve, archetype):
    """Each row mechanism holds its other controls still across its causal transition."""
    # The synthetic page composes every mechanism a page can author, and carries the
    # standing comment the margin entry's row is made of. An archetype naming another
    # source is one whose causal state cannot coexist with that composed page, or whose
    # mechanism lives only in a shipped gallery or under a page-wide opt-in.
    source = archetype.get("source")
    page = open_page(
        browser,
        serve(source)
        if source
        else serve(
            CONTROL_STABILITY_PAGE,
            media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
            events=[
                {
                    "kind": "comment",
                    "author": "user",
                    "revision": 1,
                    "text": "Does the narrower proof still cover every control?",
                    "anchor": {"section": "stable-suggestion"},
                }
            ],
        ),
    )
    page_at_rest(page)
    if disclosure := archetype.get("open"):
        page.locator(disclosure).click()
    page.evaluate(DEFINE_BOXES)
    control = page.locator(archetype["target"])
    expect(control).to_be_visible()
    # Playwright's click may scroll its target into view. Finish that navigation
    # before holding the positions the press itself must preserve.
    control.scroll_into_view_if_needed()
    page_at_rest(page)
    before = control.evaluate(NEIGHBOURHOOD, NEIGHBOUR)
    assert before["names"], f"{archetype['name']} has no neighbouring control to hold"

    if option := archetype.get("option"):
        control.click()
        page.get_by_role("option", name=option, exact=False).click()
    else:
        control.click()
    round_trip(page)
    page_at_rest(page)
    after = page.evaluate("() => window.__lfBoxes()")
    assert any(box is not None for box in after), (
        f"{archetype['name']} leaves no neighbouring control to measure after its press"
    )
    moved = displaced(before, after)
    assert not moved, (
        f"pressing the {archetype['name']} control moved its neighbours:\n  "
        + "\n  ".join(moved)
    )


def test_a_phone_shows_a_notice_in_the_banner_s_status_words(browser, serve):
    """A phone's one place for brief news is the banner's status words: the notice
    stands over them while it lasts and they return when it fades. The status press
    keeps its own name meanwhile, since the live region has said the notice, and the
    bottom status, which says it elsewhere, stays down."""
    context = browser.new_context(
        viewport={"width": 390, "height": 800}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(BOARD_PAGE), context=context)
    words = page.locator(".lf-status-text")
    notice = page.locator(".lf-banner .lf-status-notice")
    press = page.locator(".lf-status-button")
    expect(notice).to_be_hidden()
    name = press.evaluate("press => press.innerText")
    before = press.bounding_box()

    board = page.locator("#sprint")
    board.get_by_role("button", name="Move: Squirrel baffle — Todo").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    expect(notice).to_have_text("Moved to Done — sent")
    expect(notice).to_be_visible()
    expect(words).to_have_css("opacity", "0")
    expect(page.locator(".lf-bottom-status")).to_be_hidden()
    expect(page.locator(".lf-live")).to_have_text("Moved to Done — sent")
    expect(press).to_have_accessible_name(name)
    assert press.bounding_box()["x"] == pytest.approx(before["x"], abs=0.5)

    expect(notice).to_be_hidden()
    expect(words).to_have_css("opacity", "1")

    # Once the gesture's acknowledgement has faded, background news owns its own
    # rendering. A shorter successor keeps the same first-line seat and press.
    page.evaluate("""async () => {
      window.noticeOwner = await window.__lfRuntimeImport('/runtime/notifications.js');
      noticeOwner.notice('A shared draft sent to the agent', {background: true});
    }""")
    expect(notice).to_have_text("A shared draft sent to the agent")
    expect(notice).to_be_visible()
    rendered(page)
    fragments = """node => {
      const range = document.createRange();
      range.selectNodeContents(node);
      return [...range.getClientRects()].map(rect => ({x: rect.x, y: rect.y}));
    }"""
    long_lines = notice.evaluate(fragments)
    assert len(long_lines) == 2, long_lines
    press_before = press.bounding_box()
    page.evaluate("""() => {
      noticeOwner.notice('New conversation sent', {background: true});
    }""")
    expect(notice).to_have_text("New conversation sent")
    rendered(page)
    short_lines = notice.evaluate(fragments)
    assert len(short_lines) == 1, short_lines
    assert short_lines[0] == pytest.approx(long_lines[0], abs=0.5), (
        long_lines,
        short_lines,
    )
    press_after = press.bounding_box()
    # The sentence may grow rightward; its leading edge and vertical aim stay put.
    for edge in ("x", "y", "height"):
        assert press_after[edge] == pytest.approx(press_before[edge], abs=0.5), (
            press_before,
            press_after,
        )


def test_a_recorded_move_is_acknowledged_in_the_status_and_nowhere_else(browser, serve):
    """The page has one place for brief news. A gesture's acknowledgement used to arrive
    as both a banner count and a toast in the opposite corner. The bottom status says it
    now: "Moved to Done — sent" stands in for the line's own words while it lasts, the
    live region hears the same sentence, and the line's words return when it fades.

    The notice is status text, which takes no press, so it wears the status's own card
    ground and hairline in ink. It was a filled accent pill, which read as a primary
    button."""
    page = open_page(browser, serve(BOARD_PAGE))
    board = page.locator("#sprint")
    status = page.locator(".lf-status-text")
    notice = page.locator(".lf-bottom-status .lf-notice")
    expect(status).to_be_visible()
    expect(notice).to_be_hidden()

    board.get_by_role("button", name="Move: Squirrel baffle — Todo").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    expect(notice).to_have_text("Moved to Done — sent")
    expect(notice).to_be_visible()
    face = page.locator(".lf-bottom-status").evaluate(
        "box => { const s = getComputedStyle(box);"
        " return {ink: s.color, ground: s.backgroundColor, edge: s.borderTopColor}; }"
    )
    assert face == {
        "ink": token_colour(page, "--ink"),
        "ground": token_colour(page, "--card"),
        "edge": token_colour(page, "--rule"),
    }, f"the notice is not quiet status text: {face}"
    expect(status).to_be_visible()
    expect(page.locator(".lf-live")).to_have_text("Moved to Done — sent")
    assert page.locator(".lf-toast").count() == 0, "a second surface says the news"
    round_trip(page)

    # The line's own words come back once the notice has had its moment.
    expect(status).to_be_visible()
    expect(notice).to_be_hidden()


def test_the_banner_opens_a_panel_of_the_machines_leaves(
    browser, serve, other_leaf, one_user, tmp_path
):
    """The leaves panel, end to end: the banner counts the machine's live pages,
    this one included, a press slides out a left drawer headed by this page's own
    marked, unlinked row, each neighbour is a link named by its title and saying what
    that page is doing — the same judgment its own banner would show, from the same facts — and a
    link opens that page in a tab of its own, leaving this one where it was, panel
    standing. Esc is the panel's rung on the ladder. On a machine serving nothing
    else the button never appears, which every other test here shows for free."""
    other_url, _ = other_leaf
    url = serve(LONG_PAGE)
    # This page has a session behind it too, so its own row can say the same thing a
    # neighbour's does.
    record_claim(
        serve.page_dir,
        id="s-self",
        cwd=str(tmp_path / "self-work"),
    )
    page = open_page(browser, url, context=one_user)
    btn = page.locator(".lf-others")
    expect(btn).to_have_text("All pages (2)")
    banner_control(page, ".lf-others").click()
    others_panel = page.locator(".lf-others-panel")
    expect(others_panel).to_be_visible()
    # This page heads the list, marked and never a link: the panel reads as the
    # whole machine, and this page is where the user already is.
    self_row = others_panel.locator(".lf-others-self")
    expect(self_row.get_by_text("this page", exact=True)).to_be_visible()
    expect(self_row.locator(".lf-others-title")).to_have_text("long")
    link = others_panel.locator("a.lf-others-row")
    expect(link.locator(".lf-others-title")).to_have_text("The other leaf")
    expect(link.locator(":scope > .lf-external-mark")).to_be_hidden()
    # The fixture's page claims working with a fresh ts and nothing contradicts it,
    # so the row says so — dot and words both the banner's own vocabulary.
    expect(link.locator(".lf-others-line")).to_have_text("Working — running the suite")
    expect(link.locator(".lf-dot")).to_have_class(re.compile(r"\bworking\b"))
    for row in (self_row, link):
        lefts = row.evaluate("""node => [
          node.querySelector('.lf-others-title').getBoundingClientRect().left,
          node.querySelector('.lf-others-line').getBoundingClientRect().left,
        ]""")
        assert lefts[0] == pytest.approx(lefts[1], abs=0.5), lefts
    # Every row is cut to the panel's width, so the hover holds the whole account.
    # This page's own row carries the work behind it, which is what tells two rows
    # apart when their titles are alike. Neighbors publish the same compact account.
    expect(self_row).to_have_attribute(
        "title", re.compile(rf"^long\n{re.escape(str(tmp_path / 'self-work'))}\n")
    )
    expect(link).to_have_attribute(
        "title",
        f"The other leaf\n{tmp_path / 'other-work'}\nWorking — running the suite",
    )
    destination = link.get_attribute("href")
    # The new tab keeps the other page's live root, authorized by the key its link
    # carried, rather than being redirected onto one stamped version.
    assert destination is not None and destination.startswith(f"{other_url}/?t=")
    tab = opened_tab(page, destination, link.click)
    # The arrival leaves the key in the cookie and the bare address in the tab.
    expect(tab).to_have_url(f"{other_url}/")
    tab.close()
    # The press left this tab alone, drawer still standing.
    expect(others_panel).to_be_visible()
    page.keyboard.press("Escape")
    expect(others_panel).not_to_be_visible()
    expect(btn).to_be_hidden()  # closing the panel keeps the button in its fixed menu
    expect(btn).to_have_text("All pages (2)")  # and the count


def test_a_leaves_update_is_presented_before_the_page_calls_it_current(
    browser, serve, other_leaf, live_leaf
):
    """One held Leaves face keeps its complete prior view behind current readiness."""
    _, other_dir = other_leaf
    _, closing_dir = live_leaf("closing", "The closing leaf")
    page = open_page(browser, serve(LONG_PAGE))
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    btn = page.locator(".lf-others")
    rows = page.locator("a.lf-others-row")
    row = rows.filter(has_text="The other leaf")
    expect(btn).to_have_text("All pages (3)")
    expect(rows).to_have_count(2)
    row.focus()
    before = page.evaluate(
        """async () => {
          const face = document.querySelector('lf-leaves-banner-face');
          const presentation = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js'
          );
          const schedule = face.scheduleUpdate.bind(face);
          let release;
          const held = new Promise(resolve => { release = resolve; });
          let armed = true;
          face.scheduleUpdate = () => {
            if (!armed) return schedule();
            armed = false;
            return held.then(schedule);
          };
          window.releaseLeavesPaint = release;
          window.leavesRowBefore = document.activeElement;
          window.leavesButtonBefore = document.querySelector('.lf-others');
          window.leavesPresentation = presentation;
          const reading = presentation.readApplicationPresentation();
          return {
            semanticEpoch: reading.semanticEpoch,
            presentedEpoch: reading.presentedEpoch,
          };
        }"""
    )
    declare_work(other_dir, "recording the demo")
    cleanup_model.write_json(
        closing_dir / "status.json",
        {"state": "idle", "detail": "", "ts": cleanup_model.now_iso()},
    )
    told(
        page,
        until=lambda state: (
            {
                row["title"]: (row["activity"]["kind"], row["activity"]["detail"])
                for row in state["others"]
            }
            == {"The other leaf": ("working", "recording the demo")}
        ),
    )
    held = page.evaluate(
        """() => {
          window.leavesReady = false;
          leavesPresentation.whenApplicationPresented().then(() => {
            window.leavesReady = true;
          });
          const reading = leavesPresentation.readApplicationPresentation();
          return {
            pending: reading.pending,
            semanticEpoch: reading.semanticEpoch,
            presentedEpoch: reading.presentedEpoch,
            ready: leavesReady,
            label: leavesButtonBefore.textContent,
            rows: document.querySelectorAll('a.lf-others-row').length,
          };
        }"""
    )
    assert held == {
        "pending": ["leaves"],
        "semanticEpoch": before["semanticEpoch"],
        "presentedEpoch": before["presentedEpoch"],
        "ready": False,
        "label": "All pages (3)",
        "rows": 2,
    }
    page.evaluate("releaseLeavesPaint()")
    page.wait_for_function("window.leavesReady")
    expect(btn).to_have_text("All pages (2)")
    expect(rows).to_have_count(1)
    expect(row.locator(".lf-others-line")).to_have_text("Working — recording the demo")
    assert page.evaluate(
        """() => {
          const reading = leavesPresentation.readApplicationPresentation();
          return {
            sameButton: leavesButtonBefore === document.querySelector('.lf-others'),
            sameRow: leavesRowBefore === document.querySelector('a.lf-others-row'),
            focused: document.activeElement === leavesRowBefore,
            semanticEpoch: reading.semanticEpoch,
            presentedEpoch: reading.presentedEpoch,
          };
        }"""
    ) == {
        "sameButton": True,
        "sameRow": True,
        "focused": True,
        "semanticEpoch": before["semanticEpoch"],
        "presentedEpoch": before["presentedEpoch"],
    }


def test_leaves_keep_focus_through_reordering_and_choose_a_neighbour_on_removal(
    browser, serve, live_leaf, one_user
):
    """Keyed rows preserve a surviving link and hand a removed link to its neighbour."""
    second_url, _ = live_leaf("second", "Middle leaf")
    _, other_dir = live_leaf("other", "The other leaf")
    page = open_page(browser, serve(LONG_PAGE), context=one_user)
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    rows = page.locator("a.lf-others-row")
    expect(rows).to_have_count(2)
    rows.nth(1).focus()
    page.evaluate("window.focusedLeaf = document.activeElement")

    live_leaf("first", "A first leaf")
    told(page)
    expect(rows).to_have_count(3)
    expect(rows.nth(2).locator(".lf-others-title")).to_have_text("The other leaf")
    assert page.evaluate(
        "focusedLeaf === document.activeElement && focusedLeaf.isConnected"
    )

    cleanup_model.write_json(
        other_dir / "status.json",
        {"state": "idle", "detail": "", "ts": cleanup_model.now_iso()},
    )
    told(page)
    expect(rows).to_have_count(2)
    expect(rows.nth(1).locator(".lf-others-title")).to_have_text("Middle leaf")
    expect(rows.nth(1)).to_be_focused()
    page.keyboard.press("ArrowUp")
    expect(rows.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(rows.nth(1)).to_be_focused()
    destination = rows.nth(1).get_attribute("href")
    assert destination is not None and destination.startswith(f"{second_url}/?t=")
    opened_tab(page, destination, lambda: page.keyboard.press("Enter"))


def test_a_leaf_served_at_a_new_address_keeps_its_row_and_focus(
    browser, serve, other_leaf, one_user
):
    """A row is the page it names, and its link is wherever that page is served now. A
    neighbour whose server restarts on another port keeps its row and the focus on it,
    and Enter opens the page at the new address. Keyed by address, the restart read as
    one page leaving and another arriving: the focused link was removed and focus fell
    back to the drawer."""
    old_url, other_dir = other_leaf
    page = open_page(browser, serve(LONG_PAGE), context=one_user)
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    row = page.locator("a.lf-others-row")
    expect(row).to_have_count(1)
    row.focus()
    page.evaluate("window.focusedLeaf = document.activeElement")

    # The page hears nothing from the old server stopping until the new one has
    # published its row, so its next reading moves the neighbour from one address to
    # the other.
    reads = CutOff().hold(page)
    _until(
        page,
        lambda traffic: traffic.asked == traffic.heard,
        "heard every state read it asked before the cut",
    )
    # The recovery a taken port's refusal names: with the service record deleted, the
    # restarted server derives its address again, and binds past the port still taken.
    hosting_model.cmd_stop(other_dir)
    (other_dir / SERVICE_FILE).unlink()
    with socket.create_server(("127.0.0.1", urlsplit(old_url).port)):
        new_url = hosting_model.start_server(
            other_dir, standing=True, harness=None
        ).url.split("?")[0]
    assert urlsplit(new_url).port != urlsplit(old_url).port
    wait_for(
        lambda: [entry["url"] for entry in presence_model.other_leaves(serve.page_dir)],
        lambda urls: [url.split("?")[0] for url in urls] == [new_url],
        failure="the restarted neighbour never published its row",
    )
    reads.restore()
    told(
        page,
        until=lambda state: (
            [entry["url"].split("?")[0] for entry in state["others"]] == [new_url]
        ),
    )

    destination = row.get_attribute("href")
    assert destination is not None and destination.startswith(f"{new_url}?t=")
    assert page.evaluate(
        "focusedLeaf === document.activeElement && focusedLeaf.isConnected"
    ), "the restarted page's row lost its node or its focus"
    opened_tab(page, destination, lambda: page.keyboard.press("Enter"))


def test_a_failed_leaves_restore_keeps_application_presentation_pending(
    browser, serve, other_leaf, live_leaf
):
    """A list that cannot paint either a candidate or its fallback is not presented."""
    _, closing_dir = live_leaf("closing", "The closing leaf")
    page = open_page(browser, serve(LONG_PAGE))
    page.evaluate(
        """() => {
          const list = document.querySelector('lf-leaves-list');
          const render = list.render.bind(list);
          let failures = 2;
          list.render = () => {
            if (failures-- > 0) throw new Error('deliberate leaves failure');
            return render();
          };
        }"""
    )
    cleanup_model.write_json(
        closing_dir / "status.json",
        {"state": "idle", "detail": "", "ts": cleanup_model.now_iso()},
    )
    told(
        page,
        until=lambda state: all(
            row["title"] != "The closing leaf" for row in state["others"]
        ),
    )
    page.wait_for_function(
        """async () => {
          const presentation = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js'
          );
          return presentation.readApplicationPresentation().pending.includes('leaves');
        }"""
    )
    assert [said(error) for error in take_browser_errors(page)] == [
        (
            "leaf: Presentation failed: Leaves presentation and retention failed: "
            "deliberate leaves failure; deliberate leaves failure"
        )
    ]

    # A later complete reading replaces the failed ticket and opens readiness again.
    told(page)
    page.wait_for_function(
        """async () => {
          const presentation = await window.__lfRuntimeImport(
            '/runtime/semantic-state.js'
          );
          return !presentation.readApplicationPresentation().pending.includes('leaves');
        }"""
    )


def test_the_leaves_drawer_takes_the_keyboard(browser, serve, live_leaf, one_user):
    """The drawer is a list, and a user walks it without reaching for the mouse: g L
    opens it and lands on the first neighbour, up and down step between them and clamp
    at the ends, Home and End reach the ends, Enter opens the focused one in its own tab, and Esc gives that press
    back — the user is returned to the reading place they pressed `g L` from, not left
    holding the button that names the drawer. The go-to menu names the panel, and the shortcut bar names
    the drawer's own keys once focus is inside it — the promise and the press being one
    scene — and the "?" reference carries the same rows."""
    live_leaf("second", "A second leaf")
    other_url, _ = live_leaf("other", "The other leaf")
    page = open_page(browser, serve(LONG_PAGE), context=one_user)
    btn = page.locator(".lf-others")
    expect(page.locator(".lf-others-panel")).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown Home End"
    )
    expect(page.locator("a.lf-others-row").first).to_have_attribute(
        "aria-keyshortcuts", "Enter"
    )
    expect(btn).to_have_text("All pages (3)")
    shortcut_bar = page.locator(".lf-shortcut-bar")
    # The go-to menu carries the panel only while there is another leaf to show.
    page.keyboard.press("g")
    expect(shortcut_bar).to_contain_text("Pages drawer")
    page.keyboard.press("Shift+l")
    rows = page.locator("a.lf-others-row")
    # Titles order the drawer, so the walk has a stated first row to start from.
    expect(rows.first.locator(".lf-others-title")).to_have_text("A second leaf")
    expect(rows.first).to_be_focused()
    expect(shortcut_bar).to_contain_text("walk the pages")
    expect(shortcut_bar).to_contain_text("open it in a tab")
    page.keyboard.press("ArrowUp")
    expect(rows.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(rows.nth(1)).to_be_focused()
    page.keyboard.press("ArrowDown")  # clamped at the end, never wrapped to the top
    expect(rows.nth(1)).to_be_focused()
    page.keyboard.press("ArrowUp")
    expect(rows.first).to_be_focused()
    page.keyboard.press("End")
    expect(rows.nth(1)).to_be_focused()
    page.keyboard.press("Home")
    expect(rows.first).to_be_focused()
    # Enter is the browser's own on a link, which is why the row is one.
    page.keyboard.press("ArrowDown")
    destination = rows.nth(1).get_attribute("href")
    assert destination is not None and destination.startswith(f"{other_url}/?t=")
    tab = opened_tab(page, destination, lambda: page.keyboard.press("Enter"))
    expect(tab).to_have_url(f"{other_url}/")
    tab.close()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-others-panel")).not_to_be_visible()
    # One press in, one Escape out, and what the Escape gives back is exactly what the
    # press took: the reading place `g L` was pressed from. Landing on the drawer's own
    # button instead would leave a user who never touched it holding a control, one
    # press from reopening what they had just put down.
    assert page.evaluate("() => document.activeElement === document.body")
    page.keyboard.press("?")
    page.keyboard.press("?")
    help_el = page.locator(".lf-command-reference")
    expect(help_el).to_contain_text("In the pages drawer")
    expect(help_el).to_contain_text("Previous page")
    expect(help_el).to_contain_text("Next page")
    expect(help_el).to_contain_text("First page")
    expect(help_el).to_contain_text("Last page")


@pytest.mark.parametrize("width", [500, 1200])
def test_auxiliary_surfaces_replace_each_other_and_name_the_open_one(
    browser, serve, other_leaf, width
):
    """Threads and drawers are alternate auxiliary surfaces at every width.

    The open auxiliary surface keeps its semantic expanded state and also wears the banner's
    active face. Its peers return to rest as it takes their place, so the tint names
    exactly the auxiliary surface the user can see rather than merely the last one pressed.
    A surface beside the page can be replaced directly; a covering surface is modal and
    must close before its banner peers become available again.
    """
    page = open_page(browser, serve(MANY_ASKS_PAGE))
    resized(page, width, 700)
    asks = page.locator(".lf-queue-panel")
    comments = page.locator(".lf-thread-panel")
    controls = {
        "leaves": page.locator(".lf-others"),
        "asks": page.locator(".lf-queue"),
        "threads": page.locator(".lf-threads-toggle"),
    }

    def face(control):
        return control.evaluate(
            """el => { const style = getComputedStyle(el); return [
              style.borderColor, style.color, style.backgroundColor
            ]; }"""
        )

    active = [
        "rgba(0, 0, 0, 0)",
        token_colour(page, "--accent"),
        token_colour(page, "--chip"),
    ]
    resting = {name: face(control) for name, control in controls.items()}
    for control in controls.values():
        expect(control).to_have_class(re.compile(r"\blf-auxiliary-toggle\b"))
    expect(
        page.locator(
            ".lf-version.lf-auxiliary-toggle, .lf-banner-more.lf-auxiliary-toggle"
        )
    ).to_have_count(0)

    def expect_open(name):
        page.mouse.move(0, page.viewport_size["height"] - 1)
        for peer, control in controls.items():
            expect(control).to_have_attribute(
                "aria-expanded", "true" if peer == name else "false"
            )
            assert face(control) == (active if peer == name else resting[peer])

    banner_control(page, ".lf-queue").click()
    expect(asks).to_have_class(re.compile(r"\bopen\b"))
    expect_open("asks")
    if bool(page.locator("dialog:modal").count()):
        page.keyboard.press("Escape")
        expect(asks).not_to_have_class(re.compile(r"\bopen\b"))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(asks).not_to_have_class(re.compile(r"\bopen\b"))
    expect_open("threads")

    if bool(page.locator("dialog:modal").count()):
        page.keyboard.press("Escape")
        panel_settled(page, open=False)
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(page.locator(".lf-others-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect_open("leaves")

    page.keyboard.press("Escape")
    expect(page.locator(".lf-others-panel")).not_to_have_class(re.compile(r"\bopen\b"))
    banner_control(page, ".lf-queue").click()
    panel_settled(page, open=False)
    expect(asks).to_have_class(re.compile(r"\bopen\b"))
    expect(comments).not_to_have_class(re.compile(r"\bopen\b"))
    expect_open("asks")


@pytest.mark.watch_shifts
def test_a_newer_wheel_supersedes_a_panel_resize_landing(browser, serve):
    """A focused title belongs to the reader's newer scroll while resize waits.

    Native scroll keeps focus on the title. Hold the actual frame handoff so the
    resize starts with that title visible and the wheel moves it away before the
    correction runs; wheel-before-resize exercises a different ownership order.
    """
    page = open_page(browser, serve(LONG_PAGE, comments=24))
    resized(page, 1000, 640)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads")
    card = threads.locator(".lf-thread").nth(5)
    title = card.locator(":scope > .lf-thread-summary")
    title.click()
    rendered(page)
    expect(title).to_be_focused()
    with held_frames(page):
        page.evaluate(
            "addEventListener('resize', () => { window.panelResizeObserved = true; }, "
            "{once: true})"
        )
        page.set_viewport_size({"width": 1100, "height": 640})
        page.wait_for_function("window.panelResizeObserved === true", polling=50)
        box = threads.bounding_box()
        assert box
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        start = threads.evaluate("node => node.scrollTop")
        page.mouse.wheel(0, 2000)
        page.wait_for_function(
            "start => document.querySelector('.lf-threads').scrollTop > start + 20",
            arg=start,
            polling=50,
        )
        away = threads.evaluate("node => node.scrollTop")
        assert title.evaluate(
            "node => node.getBoundingClientRect().bottom < "
            "node.closest('.lf-threads').getBoundingClientRect().top"
        ), "the native wheel did not move the focused title out of view"
        expect(title).to_be_focused()
    rendered(page)
    assert threads.evaluate("node => node.scrollTop") == pytest.approx(away, abs=1)
    expect(title).to_be_focused()


def test_covering_threads_keeps_the_user_inside(browser, serve):
    """A covering Threads sheet is the one place the user can work until it closes.

    The same open panel leaves the page beside it live on a wide window and covers it
    where it leaves too little of a narrow one. Crossing that line must not rebuild the
    thread: the exact thread in focus and the list's reading place survive both
    directions.
    While it covers, Tab, the Leaf reading keys, native paging, and the wheel all stay in
    the panel; none can move to or scroll the covered document. Closing gives a keyboard
    entrant their prior page focus and unchanged document reading back.
    """
    page = open_page(browser, serve(LONG_PAGE, comments=24))
    resized(page, 1000, 640)
    page.evaluate("() => document.scrollingElement.scrollTop = 240")
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    assert not page.locator(".lf-thread-panel").evaluate(
        "panel => panel.closest('dialog').matches(':modal')"
    )

    threads = page.locator(".lf-threads")

    def reading_place():
        """The list keeps the focused summary in its usable reading band.

        Thread rows reflow at the narrower width, so the same thread can have a
        different numeric offset while remaining the user's reading place. An open
        thread's title is a sticky header that pins on the list's own top edge, past
        the scroll padding, and draws its ring inside itself, so its band starts at
        that edge.
        """
        held = threads.evaluate(
            "el => ({at: el.scrollTop, limit: el.scrollHeight - el.clientHeight})"
        )
        assert 0 < held["at"] < held["limit"], (
            f"the list holds no reading place clear of its limit: {held}"
        )
        shown = thread.locator(":scope > .lf-thread-summary").evaluate(
            "el => { const summary = el.getBoundingClientRect(); "
            "const list = el.closest('.lf-threads'); "
            "const box = list.getBoundingClientRect(); "
            "const style = getComputedStyle(list); "
            "return {top: summary.top, bottom: summary.bottom, "
            "bandTop: box.top + list.clientTop, "
            "bandBottom: box.bottom - parseFloat(style.scrollPaddingBottom)}; }"
        )
        assert (
            shown["top"] >= shown["bandTop"] - 1
            and shown["bottom"] <= shown["bandBottom"] + 1
        ), f"the focused summary left the list's reading band: {shown}"

    thread = threads.locator(".lf-thread").nth(5)
    identity = thread.get_attribute("data-id")
    assert identity, "the fixture established no thread to stand on"
    thread.locator(":scope > .lf-thread-summary").focus()
    thread.evaluate("el => el.scrollIntoView({block: 'start'})")
    reading_place()

    resized(page, 400, 640)
    panel_settled(page)
    assert bool(page.locator("dialog:modal").count())
    assert page.locator(".lf-thread-panel").evaluate(
        "panel => panel.closest('dialog').matches(':modal')"
    )
    expect(
        page.locator(f'.lf-thread[data-id="{identity}"] > .lf-thread-summary')
    ).to_be_focused()
    reading_place()

    # Focus persists when the reader wheels away. A later resize must keep the
    # place they chose instead of pulling the focused title back into view.
    box = threads.bounding_box()
    assert box
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, 2000)
    scroll_settled(page, scroller=".lf-threads")
    away = thread.locator(":scope > .lf-thread-summary").evaluate(
        "el => el.getBoundingClientRect().bottom < "
        "el.closest('.lf-threads').getBoundingClientRect().top"
    )
    assert away, "the wheel did not move the focused title above the list"
    resized(page, 1000, 640)
    panel_settled(page)
    assert thread.locator(":scope > .lf-thread-summary").evaluate(
        "el => el.getBoundingClientRect().bottom < "
        "el.closest('.lf-threads').getBoundingClientRect().top"
    ), "resizing pulled the reader back to the focused title"
    resized(page, 400, 640)
    panel_settled(page)

    # A complete pass through more stops than this panel holds goes out to the browser's
    # own interface and comes back round to the panel, never behind it.
    focus_stops = page.locator(
        ".lf-thread-panel button:visible, .lf-thread-panel input:visible, "
        ".lf-thread-panel leaf-text:visible, .lf-thread-panel [tabindex='0']:visible, "
        ".lf-thread-panel .lf-thread-summary:visible"
    )
    assert focus_stops.count() > 8, (
        "the panel has too few stops to expose a focus escape"
    )
    # The last stop is behind its thread's summary, which is where this pass starts:
    # a focused thread shows controls a resting one keeps out of the count.
    focus_stops.last.focus()
    edge = page.locator(".lf-thread-panel > .lf-edge")
    wrapped = False
    for _ in range(focus_stops.count() + 3):
        page.keyboard.press("Tab")
        assert page.evaluate(
            "() => document.activeElement === document.body"
            "   || document.querySelector('.lf-thread-panel').contains(document.activeElement)"
        ), "Tab reached a control behind the covering Threads panel"
        wrapped = wrapped or edge.evaluate("el => el === document.activeElement")
    assert wrapped, "Tab never came back round to the panel's first stop"

    page.locator(".lf-thread-filter-toggle").click()
    open_filter = page.locator('[data-filter-value="open"]')
    open_filter.focus()
    resized(page, 1000, 640)
    panel_settled(page)
    expect(open_filter).to_be_focused()
    assert not page.locator(".lf-thread-panel").evaluate(
        "panel => panel.closest('dialog').matches(':modal')"
    )
    resized(page, 400, 640)
    panel_settled(page)
    expect(open_filter).to_be_focused()
    assert page.locator(".lf-thread-panel").evaluate(
        "panel => panel.closest('dialog').matches(':modal')"
    )

    # What a covered document must not do is move under these gestures, so each one is
    # read against the position the document was in when the gesture started. Comparing
    # against a reading taken before the panel opened would assert something else: that
    # nothing ever moves the scroller. Crossing the beside line does move it — the strip
    # reflows the page, and the browser's scroll anchoring adjusts the scroller to keep
    # the user on their words — so a raw offset is the wrong thing to hold equal.
    threads.evaluate("el => el.scrollTop = 0")
    page.locator(".lf-threads").focus()
    covered_at = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press("d")
    page.wait_for_function("() => document.querySelector('.lf-threads').scrollTop > 0")
    after_key = threads.evaluate("el => el.scrollTop")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == covered_at

    page.keyboard.press("PageDown")
    page.wait_for_function(
        "at => document.querySelector('.lf-threads').scrollTop > at", arg=after_key
    )
    after_page = threads.evaluate("el => el.scrollTop")
    box = threads.bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, 300)
    page.wait_for_function(
        "at => document.querySelector('.lf-threads').scrollTop > at", arg=after_page
    )
    scroll_settled(page, scroller=".lf-threads")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == covered_at

    # Focus already inside the auxiliary surface is not a reason to move it at either crossing.
    thread = page.locator(f'.lf-thread[data-id="{identity}"]')
    summary = thread.locator(":scope > .lf-thread-summary")
    summary.focus()
    reading_place()
    resized(page, 1000, 640)
    panel_settled(page)
    assert not bool(page.locator("dialog:modal").count())
    expect(summary).to_be_focused()
    assert not page.locator(".lf-thread-panel").evaluate(
        "panel => panel.closest('dialog').matches(':modal')"
    )
    reading_place()
    resized(page, 400, 640)
    panel_settled(page)
    expect(summary).to_be_focused()
    assert page.locator(".lf-thread-panel").evaluate(
        "panel => panel.closest('dialog').matches(':modal')"
    )
    reading_place()

    # A panel thread has no release of its own: Escape from it is the panel's, and with
    # nothing narrowed that closes the sheet.
    closing_at = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press("Escape")
    # A covering sheet holds no strip, so the document it uncovers is laid out exactly as
    # it was and the reading place needs no carry across the close.
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")
    assert not bool(page.locator("dialog:modal").count())
    assert page.evaluate("() => document.scrollingElement.scrollTop") == closing_at


def test_a_covering_drawer_uses_the_same_auxiliary_modality_boundary(browser, serve):
    """The Questions panel gets the covering auxiliary surface contract rather than a drawer-specific
    focus trap. Its exact Ask and reading place survive both responsive crossings, its
    reading keys move its own list, and closing returns to its door without moving the
    document behind it."""
    page = open_page(browser, serve(MANY_ASKS_PAGE))
    resized(page, 500, 640)
    page.evaluate("() => document.scrollingElement.scrollTop = 180")
    document_at = page.evaluate("() => document.scrollingElement.scrollTop")
    banner_control(page, ".lf-queue").click()
    drawer = page.locator(".lf-queue-panel")
    expect(drawer).to_have_class(re.compile(r"\bopen\b"))
    assert bool(page.locator("dialog:modal").count())
    assert drawer.evaluate("surface => surface.closest('dialog').matches(':modal')")

    rows = drawer.locator(".lf-queue-row")
    row = rows.nth(8)
    row.focus()
    row.evaluate("el => el.scrollIntoView({block: 'start'})")
    identity = row.get_attribute("data-lf-at")
    list_box = drawer.locator(".lf-drawer-list")
    list_at = list_box.evaluate("el => el.scrollTop")
    assert identity and list_at > 0, "the fixture established no Ask reading place"

    for _ in range(rows.count() + 3):
        page.keyboard.press("Tab")
        assert drawer.evaluate("el => el.contains(document.activeElement)"), (
            "Tab reached a control behind the covering Questions panel"
        )

    list_box.evaluate("el => el.scrollTop = 0")
    rows.first.focus()
    page.keyboard.press("d")
    page.wait_for_function(
        "() => document.querySelector('.lf-queue-panel .lf-drawer-list').scrollTop > 0"
    )
    scroll_settled(page, scroller=".lf-queue-panel .lf-drawer-list")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == document_at

    row = drawer.locator(f'.lf-queue-row[data-lf-at="{identity}"]')
    row.focus()
    list_at = list_box.evaluate("el => el.scrollTop")
    resized(page, 900, 640)
    assert not bool(page.locator("dialog:modal").count())
    expect(row).to_be_focused()
    assert not drawer.evaluate("surface => surface.closest('dialog').matches(':modal')")
    assert list_box.evaluate("el => el.scrollTop") == pytest.approx(list_at, abs=1)
    resized(page, 500, 640)
    assert bool(page.locator("dialog:modal").count())
    expect(row).to_be_focused()
    assert drawer.evaluate("surface => surface.closest('dialog').matches(':modal')")

    page.keyboard.press("Escape")
    expect(drawer).not_to_have_class(re.compile(r"\bopen\b"))
    assert page.evaluate("() => document.activeElement === document.body")
    assert not bool(page.locator("dialog:modal").count())
    assert page.evaluate("() => document.scrollingElement.scrollTop") == document_at


def test_covering_drawers_have_a_pointer_route_back_to_their_banner_controls(
    browser, serve, other_leaf
):
    """Each drawer can be dismissed from inside the modal surface by pointer.

    Pointer entry starts in the list rather than on its dismissal furniture. The banner
    controls are inert while a drawer covers the document, so they cannot be the only
    pointer route out. Closing either drawer returns focus to the control that opened it,
    ready to reopen the same drawer: the Questions door on the banner's row, and More for
    Leaves, folded behind it.
    """
    page = open_page(browser, serve(MANY_ASKS_PAGE))
    resized(page, 500, 640)
    expect(page.locator(".lf-others")).to_have_text("All pages (2)")
    assert page.locator(".lf-others").evaluate(
        "el => Boolean(el.closest('.lf-banner-menu'))"
    ), "the fixture did not fold Pages behind the banner menu"

    for selector, panel, name, first_destination, door_back in (
        (".lf-queue", ".lf-queue-panel", "questions", ".lf-queue-row", ".lf-queue"),
        (
            ".lf-others",
            ".lf-others-panel",
            "pages",
            "a.lf-others-row",
            ".lf-banner-more",
        ),
    ):
        door = banner_control(page, selector)
        door.click()
        drawer = page.locator(panel)
        expect(drawer).to_have_class(re.compile(r"\bopen\b"))
        assert bool(page.locator("dialog:modal").count())
        expect(page.locator(".lf-banner-menu")).not_to_be_visible()
        expect(drawer.locator(first_destination).first).to_be_focused()

        page.get_by_role("button", name=f"Close {name}").click()
        expect(drawer).not_to_have_class(re.compile(r"\bopen\b"))
        expect(page.locator(door_back)).to_be_focused()
        assert not bool(page.locator("dialog:modal").count())


def test_a_keyboard_auxiliary_entry_survives_covering_to_beside(browser, serve):
    """Auxiliary placement does not retire a live return; closing its surface does. The
    Questions panel is the surface that crosses between covering and beside."""
    page = open_page(browser, serve(MANY_ASKS_PAGE))
    resized(page, 500, 640)
    origin = page.locator("main .lf-pick").first
    origin.focus()
    drawer = page.locator(".lf-queue-panel")
    opened = re.compile(r"\bopen\b")

    page.keyboard.press("g")
    page.keyboard.press("Shift+q")
    expect(drawer).to_have_class(opened)
    assert bool(page.locator("dialog:modal").count())

    resized(page, 1000, 640)
    assert not bool(page.locator("dialog:modal").count())
    expect(drawer).to_have_class(opened)

    page.keyboard.press("Escape")
    expect(drawer).not_to_have_class(opened)
    # The surface's parent is the document, so that is the landing whichever width it
    # was left at and whatever the user was standing on before they asked for it.
    assert page.evaluate("() => document.activeElement === document.body")

    page.keyboard.press("g")
    page.keyboard.press("Shift+q")
    page.get_by_role("button", name="Close questions").click()
    expect(drawer).not_to_have_class(opened)
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body"), (
        "closing the auxiliary surface left its keyboard return frame live"
    )


def test_a_walk_down_the_drawer_stops_clear_of_the_shortcut_bar_text(
    browser, serve, live_leaf
):
    """The drawer is the page's other scroll region and the shortcut bar stands over its
    bottom-left corner, so the drawer reserves the line's room — for the walk, which
    scrolls no further than it must, and for the wheel, which runs to the end. Both
    are asserted because they take their room from different places, and the walk's
    clearance without one is only however far the browser happens to overshoot: a
    fact about row height rather than about the line standing there."""
    names = [f"Leaf {i}" for i in range(6)]
    for i, title in enumerate(names):
        live_leaf(f"n{i}", title)
    page = open_page(browser, serve(LONG_PAGE))
    expect(page.locator(".lf-others")).to_have_text(f"All pages ({len(names) + 1})")
    # Short enough that the rows overflow the drawer, which is the only shape in which
    # the reservation is the difference between a clear last row and a covered one.
    resized(page, 900, 320)
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    rows = page.locator("a.lf-others-row")
    for _ in names:
        page.keyboard.press("ArrowDown")
    expect(rows.last).to_be_focused()
    drawer = page.locator(".lf-others-panel .lf-drawer-list")
    assert page.evaluate(
        "() => { const b = document.querySelector('.lf-others-panel .lf-drawer-list');"
        "        return b.scrollHeight > b.clientHeight; }"
    ), (
        "the drawer never overflowed, so the walk had nothing to scroll and proves nothing"
    )
    last = rows.last.bounding_box()
    line = page.locator(".lf-shortcut-bar").bounding_box()
    assert last["y"] + last["height"] <= line["y"], (
        f"the walk parked the last row at {last} under the shortcut bar at {line}"
    )
    # And a user who scrolls the drawer to its end by hand lands in the same place:
    # scroll-padding answers the walk, the padding under it answers the wheel.
    drawer.evaluate("(b) => b.scrollTo({top: b.scrollHeight})")
    last = rows.last.bounding_box()
    assert last["y"] + last["height"] <= line["y"], (
        f"scrolled to its end the drawer put its last row at {last}, under the key "
        f"line at {line}"
    )


def test_a_walk_down_the_queue_stops_clear_of_the_shortcut_bar_text(browser, serve):
    """A covering Questions panel keeps the last row above the shortcut bar.

    Beside a live page the bar ends at the panel's edge, so only the covering
    posture exercises the clearance shared with the Pages drawer."""
    page = open_page(browser, serve(MANY_ASKS_PAGE))
    resized(page, 480, 420)
    banner_control(page, ".lf-queue").click()
    rows = page.locator("button.lf-queue-row")
    expect(rows).to_have_count(24)
    rows.first.focus()
    page.keyboard.press("ArrowUp")
    expect(rows.first).to_be_focused()
    for _ in range(24):
        page.keyboard.press("ArrowDown")
    expect(rows.last).to_be_focused()
    # Home and End are the same walk's ends, and End parks the last row where the
    # stepping walk did.
    page.keyboard.press("Home")
    expect(rows.first).to_be_focused()
    page.keyboard.press("End")
    expect(rows.last).to_be_focused()
    drawer = page.locator(".lf-queue-panel .lf-drawer-list")
    assert page.evaluate(
        "() => { const b = document.querySelector('.lf-queue-panel .lf-drawer-list');"
        "        return b.scrollHeight > b.clientHeight; }"
    ), (
        "the drawer never overflowed, so the walk had nothing to scroll and proves nothing"
    )
    last = rows.last.bounding_box()
    line = page.locator(".lf-shortcut-bar").bounding_box()
    assert last["y"] + last["height"] <= line["y"], (
        f"the walk parked the last row at {last} under the shortcut bar at {line}"
    )
    # And a user who scrolls the drawer to its end by hand lands in the same place:
    # scroll-padding answers the walk, the padding under it answers the wheel.
    drawer.evaluate("(b) => b.scrollTo({top: b.scrollHeight})")
    last = rows.last.bounding_box()
    assert last["y"] + last["height"] <= line["y"], (
        f"scrolled to its end the drawer put its last row at {last}, under the key "
        f"line at {line}"
    )


def test_the_feature_gallery_has_no_serious_wcag_a_or_aa_violations(browser, serve):
    """Axe covers semantic failures the render gate cannot see: an unnamed control,
    an invalid role relationship, or a contrast failure can occupy a perfectly good
    box and still shut a user out. Keep the scope to WCAG A/AA and actionable
    serious/critical findings; layout and accessibility-tree snapshots belong to
    specific regressions, not a baseline that changes with every restyle. The feature
    gallery is the authored page with the broadest real UI. The specialist package
    pages get one 420px Axe reading in the exported corpus; focused tests own the live
    chrome surfaces this page does not open.

    A phone's width because what a box does there is a different question and not a
    smaller one: the column is 372px, so a block that had room at a desk starts
    scrolling, and a scrolling box with no way into it from the keyboard is a user
    reading half of every line of code. Nothing at 1200 says a word about it."""
    page = open_page(browser, serve(FEATURE_GALLERY))
    findings = []
    for color_scheme in ("light", "dark"):
        page.emulate_media(color_scheme=color_scheme)
        for width in (1200, 420):
            resized(page, width, 900)
            violations, report = serious_axe_violations(page)
            if violations:
                findings.append(f"[{width}px {color_scheme}]\n{report}")
            if unread := overlapped_words(page):
                findings.append(
                    f"[{width}px {color_scheme}] no contrast read under a box that paints "
                    "nothing: " + ", ".join(unread)
                )

    assert findings == [], "\n\n".join(findings)


# Each scheme and each width once: a contrast failure belongs to a scheme and a
# scrolling box to a width, and neither has been seen to need the other.
@pytest.mark.parametrize(("width", "color_scheme"), [(1200, "light"), (420, "dark")])
def test_the_chrome_a_key_opens_has_no_serious_violations(
    browser, serve, other_leaf, color_scheme, width
):
    """The feature-gallery sweep above reads broad authored UI with the chrome shut: it
    never presses a key, so the thread panel, the page comment card, the drawers, the versions
    menu, the command reference and the sequence's chips are surfaces four readings pass
    straight over. A `role="list"` whose children were not all list items shipped
    through it, green every time.

    One page because the chrome is the same on every document. What varies here is which
    of the chrome's own surfaces is standing — and the scheme and the
    width, which are the two axes that sweep carries and this one has to carry too. Dropped,
    they cost this test the dark palette entirely: the token these very sweeps caught was
    left failing on the dark half, because nothing here ever rendered it.

    Each surface is opened by its own key, which is also the assertion that it can be, and
    each is proved standing before axe reads it — a sweep over a surface that never opened
    is a green that means nothing, which is the shape `tests/AGENTS.md` names."""
    url = serve(ADDRESSED_PAGE, comments=1)
    stamp_page(serve.page_dir, ADDRESSED_PAGE, "two")
    page = open_page(browser, url)
    resized(page, width, 900)
    page.emulate_media(color_scheme=color_scheme)
    expect(page.locator(".lf-others")).to_have_text("All pages (2)")

    def sweep(where):
        violations, report = serious_axe_violations(page)
        assert violations == [], f"{where}: {report}"

    sweep("the page as it arrives")

    # The panel, and then the thread its list shows open — which is where `g T` lands
    # the user; `c` there enters that thread's reply box.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    shown = page.locator(".lf-threads > .lf-thread:not([hidden])[open]")
    expect(shown.locator(":scope > .lf-thread-summary")).to_be_focused()
    # Read mid-slide, the panel's words stand past the window's edge, where axe reads no
    # contrast for them and the sweep passes them unread.
    panel_settled(page)
    sweep("standing on the open thread")
    page.keyboard.press("c")
    expect(shown.locator("leaf-text")).to_be_focused()
    sweep("standing in a reply box")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()

    # The page comment card, which `c` opens with nothing on the page to comment on.
    page.keyboard.press("c")
    expect(page.locator(".lf-page-comment-card .lf-general leaf-text")).to_be_focused()
    sweep("standing in the page comment card")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-page-comment-card")).to_be_hidden()

    # A drawer on the far edge, which the sweep above never opens either. Waited out rather
    # than pressed past: the close is animated, so the next surface would otherwise be read
    # with this one still sliding away behind it.
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(page.locator(".lf-others-panel")).to_have_class(re.compile("open"))
    sweep("standing in the pages drawer")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-others-panel")).not_to_have_class(re.compile("open"))

    # The versions menu, including the first-version case browser Escape now dismisses.
    open_versions(page)
    expect(page.locator(".lf-version-menu")).to_be_visible()
    sweep("in the versions menu")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-version-menu")).not_to_be_visible()

    # The command reference, which is a dialog and owes the most of any of them.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_be_visible()
    search = page.locator(".lf-command-reference-search input")
    assert search.evaluate(
        "input => input.ariaControlsElements?.[0] === document.querySelector('.lf-command-reference-results')"
    )
    # The editor is inside Web Awesome's shadow root while its grid is outside it.
    # Chromium exposes the element-reference relationship to assistive technology;
    # axe reads only an aria-controls IDREF attribute, which cannot name across roots.
    cdp = page.context.new_cdp_session(page)
    try:
        nodes = cdp.send("Accessibility.getFullAXTree")["nodes"]
    finally:
        cdp.detach()
    combobox = next(
        node
        for node in nodes
        if node.get("role", {}).get("value") == "combobox"
        and node.get("name", {}).get("value") == "Search commands"
    )
    assert any(
        prop["name"] == "controls"
        and [related.get("idref") for related in prop["value"].get("relatedNodes", [])]
        == ["lf-command-reference-results"]
        for prop in combobox["properties"]
    )
    violations, report = serious_axe_violations(page)
    violations = [
        violation
        for violation in violations
        if not (
            violation["id"] == "aria-required-attr"
            and len(violation["nodes"]) == 1
            and violation["nodes"][0]["target"]
            == [[".lf-command-reference-search", "#input"]]
            and [check.get("data") for check in violation["nodes"][0]["any"]]
            == [["aria-controls"]]
        )
    ]
    assert violations == [], f"in the command reference: {report}"
    page.keyboard.press("Escape")
    expect(page.locator(".lf-command-reference")).to_be_hidden()
    page_at_rest(page)

    # And the sequence's generated target hints, painted over the visible page rather than
    # inserted into it.
    page.keyboard.press("g")
    expect(page.locator(".lf-go-to-hints .lf-go-to-hint").first).to_be_visible()
    sweep("with the visible-target sequence armed")
    page.keyboard.press("Escape")


def test_the_stop_reading_names_a_control_with_nothing_drawn_on_it(browser, serve):
    """The stop reading distinguishes a real ring from a missing one.

    Reach a control by Tab, verify its real indication, then remove that indication. The
    thread-list pseudo-element supplies the distinct case where another box carries the
    focused stop's ring.
    """
    url = serve(LONG_PAGE, comments=2)
    page = open_page(browser, url)
    page.evaluate(RING_FOCUS_START)
    for _ in range(60):
        page.keyboard.press("Tab")
        if page.evaluate(
            "() => Boolean(document.activeElement?.matches('.lf-threads-toggle'))"
        ):
            break
    else:
        raise AssertionError("Tab never reached the banner's comments button")
    rendered(page)

    assert page.evaluate(SEEN_STOP) is None, (
        "a banner button wearing the layer's own ring reads as a stop nothing draws, so "
        "the sample floor cannot trust this reading"
    )

    page.evaluate("""() => {
        const style = document.createElement('style');
        style.id = 'lf-ring-negative-control';
        style.textContent =
          '.lf-threads-toggle:focus { outline: none !important;'
          + ' box-shadow: none !important; }';
        document.head.append(style);
    }""")
    rendered(page)
    lost = page.evaluate(SEEN_STOP)
    assert lost and "lf-threads-toggle" in lost, (
        "the ring was taken off a focused control and the reading still called it seen "
        f"({lost}), so the sample floor cannot report a missing indication"
    )

    # The thread list's ring is a later-painted pseudo-element because its scrolling
    # contents can cover an outline on the list itself. Prove that paint is part of the
    # reading, then take it away without moving focus and require the list to be reported.
    # The list keeps focus itself only while it shows no thread, so this half stands on
    # a page with none.
    page = open_page(browser, serve(LONG_PAGE))
    page.evaluate(RING_FOCUS_START)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    expect(page.locator(".lf-threads")).to_be_focused()
    assert page.evaluate(SEEN_STOP) is None
    page.evaluate("""() => {
        const style = document.createElement('style');
        style.textContent = '.lf-threads-frame::after { outline: none !important; }';
        document.head.append(style);
    }""")
    lost = page.evaluate(SEEN_STOP)
    assert lost and "lf-threads" in lost, (
        "the list's ring was removed and the reading still called its keyboard "
        f"landing seen ({lost})"
    )

    # A tab's label carries focus inside its larger click target. Removing that child
    # ring must still report the focused tab, rather than crediting selection's fill.
    page = open_page(browser, serve(ROOT / "tests/fixtures/pages/root-tabs.html"))
    page.keyboard.press("Tab")
    page.locator(".lf-tab-btn").first.focus()
    assert page.evaluate(SEEN_STOP) is None
    name = page.locator(".lf-tab-name").first
    for property, value in (
        ("display", "none"),
        ("visibility", "hidden"),
        ("opacity", "0"),
    ):
        name.evaluate(
            "(node, [property, value]) => node.style.setProperty(property, value)",
            [property, value],
        )
        lost = page.evaluate(SEEN_STOP)
        assert lost and "lf-tab-btn" in lost, (property, lost)
        name.evaluate(
            "(node, property) => node.style.removeProperty(property)", property
        )
    page.add_style_tag(
        content=".lf-tab-btn > .lf-tab-name { outline: none !important; }"
    )
    lost = page.evaluate(SEEN_STOP)
    assert lost and "lf-tab-btn" in lost, lost


def test_each_sampled_focus_ring_is_shown_whole_in_its_surface(
    browser, serve, live_leaf
):
    """Where the keyboard stands in each surface a key opens, the user sees its ring
    whole: not cut by a box that clips it, and not under a neighbour. And every stop
    in each selected page's ordinary Tab order shows keyboard focus at all, read by
    walking it once on arrival.

    `RING_CASES` walks the layer's surfaces by their real keys and stands on a sample in
    each; every ring drawn there is measured, not only the sample's. Which rings get a
    sample is the cases' choice rather than a census of the layer's rules, so a new ring
    needs no sample of its own; what every ring rule must do is name the ring it draws.
    A second version and a neighbouring leaf provide the two runtime states authored
    examples cannot carry themselves.
    """

    def open_containing_thread(target):
        # The accordion keeps a message's controls connected while closed. Enter through
        # its real title before asking a sample inside it to take keyboard focus.
        thread_id = target.evaluate(
            "node => node.matches('.lf-thread-summary') ? null : "
            "node.closest('.lf-thread')?.dataset.id"
        )
        if thread_id:
            card = target.page.locator(f'.lf-thread[data-id="{thread_id}"]')
            if card.get_attribute("open") is None:
                card.locator(":scope > .lf-thread-summary").click()

    live_leaf("other", "The other leaf")
    # No ring moves under the default motion setting, so a settled sample reads the
    # value its rule declares. The reduced-motion case has a focused test above.
    faults, seen_faults = [], set()
    unseen = set()
    unnamed, unnamed_rules = set(), set()
    opened = set()
    stops = 0
    unindicated = []
    assert not (missing := set(RING_EXAMPLES) - set(RING_EXAMPLE_FILES)), (
        "the ring cases name examples that no longer exist: "
        + ", ".join(sorted(missing))
    )
    for name in RING_EXAMPLES:
        example = RING_EXAMPLE_FILES[name]
        # Serving the path lays in the example's shipped log and message widgets.
        # The chrome's page also carries a passage's thread, which the Page Map lists.
        anchored = [("triage-lede", "Migration 0041")] if name == RING_CHROME else ()
        url = serve(example, comments=2, anchored=anchored)
        if name == RING_CHROME:
            current_version = int(re.search(r"/v(\d+)\.html", url).group(1))
            next_version = current_version + 1
            _publish(
                serve.page_dir,
                next_version,
                example.read_text(),
                "Same page, said twice.",
            )
            url = url.replace(f"/v{current_version}.html", f"/v{next_version}.html")
        page = open_page(browser, url)
        unindicated += _tab_stops_without_indication(page, example.stem)
        if name == "wt-merge":
            # The shipped steps now contain buttons, so the scrollable body needs no
            # stop of its own. Make this ring specimen prose-only; it still overflows
            # and must then lend the body a keyboard stop and its pane ring.
            resized(page, 1200, 600)
            page.locator("#merge-steps-pane button").evaluate_all(
                "buttons => buttons.forEach(button => "
                "button.replaceWith(document.createTextNode(button.textContent)))"
            )
            page.evaluate(
                """async () => {
                  const { reachScrollers } = await window.__lfRuntimeImport(
                    '/runtime/reach.js'
                  );
                  reachScrollers(document.body);
                }"""
            )
            expect(page.locator('#merge-steps-pane > [tabindex="0"]')).to_have_count(1)
        if name == "release-notes":
            # Ordinary element marks need a focusable sample for their conditional ring.
            page.locator("main p").first.evaluate(
                "node => { node.classList.add('lf-mark-el'); node.tabIndex = 0; }"
            )
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        # Settled choices are user view state, so expose their focusable controls.
        for row in page.locator("lf-options[settled] > .lf-settled").all():
            if row.is_visible():
                row.click()
        page_at_rest(page)

        for scope, keys, cases in RING_CASES:
            if (samples := cases.get(name)) is None:
                continue
            # The posture the scope's own surface stands in, read after the panel below
            # has settled and put back afterwards, so the next scope reads the page this
            # one was handed. Before the panel, the room a floor is measured against is
            # the room the panel was still taking.
            posture = RING_SCOPE_WIDTH.get(scope)
            # Three rungs, because a scope can be three deep: a drawer, menu, or narrowing
            # over the panel, then the panel, then the page. The panel is reopened below,
            # so every scope starts from the same page.
            for _ in range(3):
                page.keyboard.press("Escape")
            # A draft editor and captured source are conditional chrome: Tab can stand
            # on them only after their explicit doors have opened. Do that after the
            # scope reset, whose Escape presses would otherwise put the draft away.
            if scope in {"a settled decision", "a settled option"}:
                settled = page.locator("#comparison-policy[settled] > .lf-settled")
                expect(settled).to_be_visible()
                if settled.get_attribute("aria-expanded") != "true":
                    settled.click()
            if scope == "the page":
                pencil = any_draft_control(page, "edit").first
                if pencil.count() and pencil.is_visible():
                    pencil.click()
                # A source can sit behind nested disclosures. Open each visible ancestor
                # in document order so the innermost source becomes a real Tab stop.
                for source in page.locator("details:has(lf-text-document)").all():
                    if source.is_visible() and not source.get_attribute("open"):
                        source.locator(":scope > summary").click()
            page.evaluate(RING_FOCUS_START)
            # Threads and a target's own Thread card are one surface offered two ways:
            # with the panel standing, a thread margin entry sends the user there instead of
            # building the card. The scopes listed above need the panel shut either to expose
            # their own page surface or to exercise the panel's entry route itself.
            if scope in RING_SCOPES_STARTING_WITHOUT_PANEL:
                if page.locator(".lf-thread-panel.open").count():
                    page.get_by_role("button", name="Close threads", exact=True).click()
                    panel_settled(page, open=False)
                    page.evaluate(RING_FOCUS_START)
            elif not page.locator(".lf-thread-panel.open").count():
                page.locator(".lf-threads-toggle").click()
                panel_settled(page)
            if scope == "the page":
                # Escape restores the panel's default lifecycle view. Select Resolved
                # after that reset so the page cases include each closed thread's
                # Reopen control; narrower scopes keep open threads available for their
                # own conditional controls, such as a reply's reaction palette.
                page.locator(".lf-thread-filter-toggle").click()
                resolved = page.locator('[data-filter-value="resolved"]')
                if (
                    resolved.is_enabled()
                    and resolved.get_attribute("aria-checked") != "true"
                ):
                    resolved.click()
                page.evaluate(RING_FOCUS_START)
            if posture:
                resized(page, posture, RING_VIEWPORT[1])
                page_at_rest(page)
            if scope == "page status":
                # Native Enter opens the explanation and places focus on its scroller;
                # it is deliberately outside sequential Tab order while closed.
                page.locator(".lf-status-button").focus()
                page.locator(".lf-status-button").press("Enter")
                expect(page.locator(".lf-status-detail")).to_be_focused()
            if opener := RING_SCOPE_OPENER.get(scope):
                control = (
                    banner_control(page, opener)
                    if opener in {".lf-queue", ".lf-page-map-toggle"}
                    else page.locator(opener).first
                )
                open_containing_thread(control)
                control.click()
            for key in keys:
                page.keyboard.press(key)
                rendered(page)
            if scope == "a landed diff line":
                # Opening a collapsed file and loading its hunk finish after the key
                # handler returns. Read the ring once the walk has actually landed.
                expect(
                    page.locator("#pr-exact-patch [data-content] > [data-line]:focus")
                ).to_have_count(1)
            page_at_rest(page)
            surface, offers = RING_SCOPE_SURFACE.get(scope, (None, None))
            if surface and (offers is None or offered(page, offers)):
                assert page.locator(surface).count() == 1, (
                    f"{RING_SCOPE_OPENER.get(scope, ' '.join(keys))} did not open "
                    f"{scope} on {example.stem}, which "
                    "offers it"
                )
                opened.add(scope)

            where = f"in {scope} of {example.stem}"
            for selector, expected in samples:
                expected = {expected} if isinstance(expected, str) else set(expected)
                if selector:
                    target = page.locator(selector).first
                    # A sample can stand inside a container that is closed on arrival —
                    # the gallery holds its sections in tabs, and only one panel is open.
                    # Nothing inside a hidden panel is focusable, so the ring would read
                    # as undrawn for a control that paints it perfectly well. Ask the
                    # runtime's own disclosure route, so the surface a sample needs is
                    # derived from where it sits rather than from a page's tab order.
                    # `reveal` takes the intent its caller's gesture retained, and
                    # has no default (runtime/user-intent.js). This arrangement is
                    # not a user's delayed work that a later input may supersede —
                    # it is the test saying what the page must show next — so the
                    # intent it hands over is the one that always holds.
                    target.evaluate(
                        """async node => {
                          const elements = await window.__lfRuntimeImport(
                            '/runtime/widget-elements.js'
                          );
                          await elements.reveal(node, () => true);
                        }"""
                    )
                    rendered(page)
                    open_containing_thread(target)
                    page.keyboard.press("Tab")
                    target.focus()
                    # A note on the details shelf is reached from the element that
                    # names it (details-shelf.js), never by Tab, and is focused here as
                    # a screen reader moving to it would focus it.
                    assert target.evaluate(
                        "node => node.tabIndex >= 0"
                        " || node.closest('.lf-details-shelf') !== null"
                    ), f"{selector} {where} is not in sequential keyboard navigation"
                    expect(target).to_be_focused()
                    # A text field's focus is always visible, as a textarea's is, but
                    # Chrome gives `:focus-visible` to the node inside a delegating
                    # host and never to the host; its rings read `:focus`.
                    assert target.evaluate(
                        "node => node.matches(':focus-visible, leaf-text:focus')"
                    ), f"{selector} {where} did not inherit keyboard-visible focus"
                    page_at_rest(page)
                    if (lost := page.evaluate(SEEN_STOP)) is not None:
                        unseen.add(f"{where}: {lost}")
                for ring_name in expected & RING_REMOTE_CARRIER.keys():
                    carrier_selector = RING_REMOTE_CARRIER[ring_name]
                    page.locator(carrier_selector).evaluate(
                        "node => node.setAttribute('data-lf-ring-sample', '')"
                    )
                drawn = rings_drawn(page)
                page.locator("[data-lf-ring-sample]").evaluate_all(
                    "nodes => nodes.forEach(node => "
                    "node.removeAttribute('data-lf-ring-sample'))"
                )
                lit = [ring for ring in drawn if ring["here"]]
                unnamed.update(ring["who"] for ring in lit if not ring["ring"])
                found = expected & {ring["ring"] for ring in lit if ring["sample"]}
                # One standing defect is one finding, not one per stop: a ring worn by
                # something the sample is not moving — a decision's mark, a thread's element
                # mark — is read again at every stop it survives.
                for fault in ring_faults(drawn, where):
                    if fault not in seen_faults:
                        seen_faults.add(fault)
                        faults.append(fault)
                stops += 1
                assert found == expected, (
                    f"{selector or scope} {where} did not exhibit "
                    + ", ".join(sorted(expected - found))
                )
            if posture:
                for _ in range(3):
                    page.keyboard.press("Escape")
                resized(page, *RING_VIEWPORT)
                page_at_rest(page)

        unnamed_rules.update(
            said
            for declared in page.evaluate(RING_NAMES)
            if not declared["name"]
            for said in declared["said"]
        )
        page.close()

    assert not unindicated, "keyboard stops with no visible indication: " + "; ".join(
        unindicated
    )
    assert not unseen, (
        "a sample stood on a control and nothing on screen said where the keyboard was, "
        "so a user arriving by Tab has no way to tell: "
        f"{sorted(unseen)}"
    )
    # Across the causal cases, because a scope can be dead on a page with nothing to put
    # in it. What cannot happen is a scope no selected example ever opens or exercises: then its
    # keys are unread and everything below is silent about the controls behind them.
    expected_surfaces = {
        scope for scope, _keys, _cases in RING_CASES if scope in RING_SCOPE_SURFACE
    }
    missing = expected_surfaces - opened
    assert not missing, "no selected example reached " + ", ".join(sorted(missing))
    assert not faults, "\n  ".join(
        [f"{len(faults)} faults over {stops} samples:"] + faults
    )
    # Every ring is named by the rule that draws it, said from both sides: the scan reads
    # a rule no sample paints, and the sweep reads a ring drawn without the layer's token.
    # The samples above, and every reading that credits a ring an ancestor wears, rest on
    # the name.
    assert not unnamed_rules, (
        f"{len(unnamed_rules)} rules draw the focus ring and name none of them — "
        "declare --lf-focus-ring in the rule that draws the ring:\n  "
        + "\n  ".join(sorted(unnamed_rules))
    )
    assert not unnamed, (
        "the corpus paints a focus ring on boxes no rule named, so no reading can say "
        "which rule drew it: " + ", ".join(sorted(unnamed))
    )


@pytest.mark.parametrize("touch", (False, True))
def test_every_control_the_layer_offers_is_a_box_the_user_can_hit(
    browser, serve, touch
):
    """A press the user cannot land on is a capability the page does not have.

    Measured before --aim-floor existed, at 1200x900: a thread's Reopen and the panel's
    reaction chips stood at 20 and 22 pixels tall, the banner's page preview at 23, and a
    version's Compare, a command in the reference, and a quote at around twelve by seven.
    Three controls reached the coarse-pointer block and the rest reached neither floor,
    so the same presses were small under a finger too.

    The sweep names no control. What makes a box an aim is that the runtime built it or
    stands in the runtime's own layer, and that the page under the pointer says a press
    lands there — so the next control the layer grows is held to this without anybody
    adding it to a list. Both pointers are asked, from the one token that states the
    floor, because a control comfortable under one and not the other is the fault this is
    about rather than a lesser version of it.

    The surfaces have to be opened for any of it to mean anything: seven of the eight
    controls at issue exist only inside a panel, a menu, a resolved thread or the
    reference, and a sweep of the page at rest would report a clean layer while every one
    of them was still six pixels tall. AIM_SURFACES is that assertion.
    """
    context = (
        browser.new_context(viewport={"width": 1200, "height": 900}, has_touch=True)
        if touch
        else None
    )
    # A preview record, because the badge it puts in the banner is one of the aims and
    # exists on no page that was not served by the preview script. The comment anchored
    # on a quote puts a quote in its thread.
    served = serve(
        AIM_PAGE,
        comments=2,
        anchored=[("aim-lead", "first view")],
        preview={
            "kind": "example",
            "example": "corpus",
            "checkout": "fb77",
            "interaction": "user",
            "started": "2026-08-31T12:00:00+00:00",
        },
    )
    # An agent's answer on a thread the walk leaves open carries a reaction strip,
    # whose chips are aims. The walk resolves the first thread.
    second = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ][1]
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": second,
            "text": "An answer to react to.",
        },
    )
    # A second version, published the way a page gets one and read from, so the versions
    # menu has an earlier version to compare against and Compare exists to be aimed at.
    _publish(serve.page_dir, 2, AIM_PAGE, "Same page, said twice.")
    page = open_page(browser, served.replace("/v1.html", "/v2.html"), context=context)
    floor = 44 if touch else 24
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches") == touch, (
        "the fixture did not reach the pointer medium this run is about, so the floor "
        "below is the other one's"
    )
    small, stood = [], set()
    for _ in _each_aim_surface(page, serve.page_dir):
        page_at_rest(page)
        small += page.evaluate(AIM_BOXES, floor)
        stood |= {s for s in AIM_SURFACES if page.locator(s).count()}
    assert not (missed := set(AIM_SURFACES) - stood), (
        f"the walk never stood {', '.join(sorted(missed))} up, so a clean answer would "
        f"be about a layer with those controls missing rather than about their size"
    )
    assert not small, (
        f"{len(set(small))} of the layer's controls are under the {floor}px floor a "
        f"{'coarse' if touch else 'fine'} pointer asks for:\n  "
        + "\n  ".join(sorted(set(small)))
    )
