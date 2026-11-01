"Control stability, browser shell, accessibility, and ring tests."

import re
import socket
from urllib.parse import urlsplit

import pytest
from interact_support import (
    record_claim,
    wait_for,
)
from journeys.test_render_controls import (
    LEAVES,
    LIVE_SAMPLE_PAGE,
    _sample_containment_page,
    fail_sample_startup,
)
from playwright.sync_api import expect
from render_cases_interaction import (
    live_url,
)
from render_cases_navigation import (
    _publish,
)
from render_harness import (
    EXAMPLES,
    LONG_PAGE,
    PANEL_THREAD,
    CutOff,
    Traffic,
    _until,
    holding,
    leaf_page,
    open_page,
    open_threads,
    opened_tab,
    page_comment,
    panel_settled,
    resized,
    round_trip,
    scroll_settled,
    sending,
    told,
    write,
)

from browser.controls import (
    LIVE_SAMPLES_PAGE,
    SAMPLE_STARTUP_FAILURE,
)
from leaf import event_log as events_model
from leaf import hosting as hosting_model
from leaf import presence as presence_model
from leaf.render_checks import rendered, wait_until_ready
from leaf.schema import SERVICE_FILE

pytestmark = pytest.mark.shifts_unsurveyed


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
    for frame in (first, other):
        expect(frame.locator(f'{PANEL_THREAD}[data-thread="question"]')).to_be_visible()
    first_state = first.locator("body").evaluate(
        "new URL('api/state', document.baseURI).href"
    )
    first.locator(".lf-fp-head .lf-fp-settle").click()
    wait_for(
        lambda: [e["kind"] for e in page.request.get(first_state).json()["events"]],
        lambda kinds: "resolve" in kinds,
        failure="the first sample's Resolve never reached its own log",
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
    expect(first.locator(f'{PANEL_THREAD}[data-thread="question"]')).to_be_visible()
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
            if panel_open:
                expect(
                    child.locator(f'{PANEL_THREAD}[data-thread="question"]')
                ).to_be_visible()
            else:
                expect(
                    child.locator(".lf-margin-preview").get_by_text(
                        "Can you check the destination?", exact=True
                    )
                ).to_be_visible()
                # The page draws it, so the panel's view of it goes: it shows once.
                expect(child.locator(PANEL_THREAD)).to_have_count(0)


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
    # the child's viewport ends where its page does, the room the page keeps at its
    # foot for the panel's row included.
    for practice in (child, other):
        assert practice.evaluate(
            "Math.abs(document.body.getBoundingClientRect().bottom - innerHeight) <= 1"
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
    # The send opens the new thread's view, as the field's page comment does.
    expect(child.locator(PANEL_THREAD)).to_contain_text("Keep this draft")
    child.locator(".lf-fp-close").click()
    panel_settled(child, open=False)
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
    # The child's panel stands at the foot of its frame, which the host scrolls to.
    second.evaluate(
        "sample => sample.scrollIntoView({block: 'end', behavior: 'instant'})"
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
    expect(other.locator('.lf-fp-field leaf-text[name="comment"]')).to_have_js_property(
        "value", "Keep the other sample's draft."
    )


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
          panel: getComputedStyle(document.querySelector('.lf-floating-panel')).display,
          page: document.documentElement.scrollHeight,
        })"""
    )
    assert reading["block"] == child["block"]
    assert not child["block"]
    assert child["panel"] != "none"
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
    expect(content).to_have_js_property("scrollTop", scroll_before + 300)
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


def test_live_samples_retire_before_navigation_and_coalesce_reset(browser, serve):
    """A held replacement navigation cannot keep a released child alive."""
    page = open_page(browser, serve(LIVE_SAMPLE_PAGE))
    page.evaluate("""async () => {
        const {mountSample} = await window.__lfWidgetApi();
        window.practiceFrame = document.createElement('iframe');
        document.body.append(practiceFrame);
        window.practiceHost = await mountSample(practiceFrame, {template: 'first-source'});
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
        const {mountSample} = await window.__lfWidgetApi();
        window.practiceHost = await mountSample(practiceFrame, {template: 'first-source'});
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


def test_slow_sample_state_does_not_hold_up_other_child_loads(browser, serve):
    """A child waiting for state releases its load slot for the next sample."""
    page = open_page(browser, serve(LIVE_SAMPLE_PAGE))
    held = []
    page.route(
        re.compile(r"/api/samples/[^/]+/api/state$"),
        lambda route: held.append(route),
    )
    page.evaluate("""async () => {
      const {mountSample} = await window.__lfWidgetApi();
      window.practiceHosts = await Promise.all(Array.from({length: 4}, () => {
        const frame = document.createElement('iframe');
        document.body.append(frame);
        return mountSample(frame, {template: 'first-source'});
      }));
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

    open_threads(child)
    page.keyboard.press("Escape")
    panel_settled(child, open=False)
    page.keyboard.press("Escape")
    expect(sample).to_be_focused()


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
        const {mountSample} = await window.__lfWidgetApi();
        window.pendingFrame = document.createElement('iframe');
        document.body.append(pendingFrame);
        window.pendingHost = await mountSample(pendingFrame, {template: 'first-source'});
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
        const {mountSample} = await window.__lfWidgetApi();
        window.pendingHost = await mountSample(pendingFrame, {template: 'first-source'});
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
        const {mountSample} = await window.__lfWidgetApi();
        window.pendingResults = [];
        window.pendingHosts = await Promise.all(Array.from({length: 5}, async (_, index) => {
            const frame = document.createElement('iframe');
            document.body.append(frame);
            const host = await mountSample(frame, {template: 'first-source'});
            host.ready.then(
                () => { pendingResults[index] = 'ready'; },
                error => { pendingResults[index] = error.name; });
            return host;
        }));
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


def test_all_pages_opens_a_neighbour_in_a_tab_of_its_own(
    browser, serve, other_leaf, one_user, tmp_path
):
    """A neighbour's row in All pages opens that page in a tab of its own, at its live
    root, leaving this one where it was, All pages open. This page's own row carries the
    work behind it, which is what tells two rows apart when their titles are alike."""
    other_url, _ = other_leaf
    url = serve(LONG_PAGE)
    record_claim(
        serve.page_dir,
        id="s-self",
        cwd=str(tmp_path / "self-work"),
    )
    page = open_page(browser, url, context=one_user)
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    panel_settled(page, view="leaves")
    pages = page.locator(LEAVES)
    self_row = pages.locator(".lf-fp-page:not([href])")
    expect(self_row).to_have_attribute(
        "title", re.compile(rf"^long\n{re.escape(str(tmp_path / 'self-work'))}\n")
    )
    link = pages.locator("a.lf-fp-page", has_text="The other leaf")
    destination = link.get_attribute("href")
    # The new tab keeps the other page's live root, authorized by the key its link
    # carried, rather than being redirected onto one stamped version.
    assert destination is not None and destination.startswith(f"{other_url}/?t=")
    tab = opened_tab(page, destination, link.click)
    # The arrival leaves the key in the cookie and the bare address in the tab.
    expect(tab).to_have_url(f"{other_url}/")
    tab.close()
    expect(pages).to_be_visible()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)


def test_all_pages_takes_the_keyboard(browser, serve, live_leaf, one_user):
    """All pages is a list, and a user walks it without reaching for the mouse: g L
    opens it, up and down step between its links and clamp at the ends, Home and End
    reach the ends, Enter opens the focused one in its own tab, and Esc gives that press
    back — the user is returned to the reading place they pressed `g L` from."""
    live_leaf("second", "A second leaf")
    other_url, _ = live_leaf("other", "The other leaf")
    page = open_page(browser, serve(LONG_PAGE), context=one_user)
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    panel_settled(page, view="leaves")
    rows = page.locator(f"{LEAVES} a.lf-fp-page")
    # Titles order the list, so the walk has a stated first row to start from.
    expect(rows.first.locator(".lf-fp-label")).to_have_text("A second leaf")
    page.keyboard.press("ArrowDown")
    expect(rows.first).to_be_focused()
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
    panel_settled(page, open=False)
    # One press in, one Escape out, and what the Escape gives back is exactly what the
    # press took: the reading place `g L` was pressed from.
    assert page.evaluate("() => document.activeElement === document.body")


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
    panel_settled(page, view="leaves")
    row = page.locator(f"{LEAVES} a.lf-fp-page")
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
            other_dir, persistent=True, harness=None
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
