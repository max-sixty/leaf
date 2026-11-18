"Control stability, browser shell, accessibility, and ring tests."

import pytest
from journeys.test_render_controls import (
    LIVE_SAMPLE_PAGE,
)
from playwright.sync_api import expect
from render_harness import (
    Traffic,
    holding,
    leaf_page,
    open_page,
    open_threads,
    panel_settled,
    resized,
    round_trip,
    scroll_settled,
)

from leaf.render_checks import wait_until_ready
from leaf_dev.example_data import named_source

pytestmark = pytest.mark.shifts_unsurveyed


def _apart(*marks):
    """Whether no two of the marks' boxes overlap."""
    boxes = [mark.bounding_box() for mark in marks]
    return all(
        a["x"] + a["width"] <= b["x"]
        or b["x"] + b["width"] <= a["x"]
        or a["y"] + a["height"] <= b["y"]
        or b["y"] + b["height"] <= a["y"]
        for i, a in enumerate(boxes)
        for b in boxes[i + 1 :]
    )


@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_a_control_s_badges_stand_apart_whichever_show(browser, serve, direction):
    """Every badge on a control stays whole beside the others: a margin entry's unread
    dot and count, in the rail and as a pin, and the folded leaf's count, news and
    error, in either direction (`.lf-badges`, controls.css)."""
    source = leaf_page(
        "Badges",
        '<p id="answered">Two answers wait here.</p><p id="asked">One question.</p>',
    )
    if direction == "rtl":
        source = source.replace('<html lang="en">', '<html lang="en" dir="rtl">')
    answer = {
        "kind": "comment",
        "author": "agent",
        "agent": "Claude",
        "revision": 1,
        "text": "One answer.",
        "anchor": {"section": "answered"},
    }
    asked = {**answer, "author": "user", "id": "q", "text": "Which first?"}
    del asked["agent"]
    page = open_page(
        browser,
        serve(
            source,
            events=[
                answer,
                {**answer, "text": "Another answer."},
                {**asked, "anchor": {"section": "asked"}},
                {
                    "kind": "reply",
                    "author": "agent",
                    "agent": "Claude",
                    "revision": 1,
                    "parent": "q",
                    "responds": "q",
                    "obligation": True,
                    "text": "The hatch or the window?",
                },
            ],
        ),
    )
    entry = page.locator('[data-lf-margin-for="answered"]')
    for width, place in ((1440, "rail"), (700, "pin")):
        resized(page, width, 900)
        expect(entry).to_have_attribute("data-lf-place", place)
        badges = entry.locator(".lf-margin-marker > .lf-badges")
        expect(badges.locator(".lf-margin-count")).to_have_text("2")
        expect(badges.locator(".lf-unread-dot")).to_be_visible()
        assert _apart(
            badges.locator(".lf-margin-count"), badges.locator(".lf-unread-dot")
        )

    resized(page, 1440, 900)
    page.keyboard.press(".")
    page.evaluate("async () => (await window.__lfWidgetApi()).raiseError('Not saved')")
    leaf = page.locator(".lf-fp-leaf > .lf-badges")
    marks = [leaf.locator(name) for name in (".lf-fp-badge", ".lf-fp-news-dot")]
    marks.append(leaf.locator(".lf-fp-error-dot"))
    for mark in marks:
        expect(mark).to_be_visible()
    assert _apart(*marks)


@pytest.mark.parametrize("width", [390])
def test_merge_film_play_continues_from_the_displayed_moment(browser, serve, width):
    source = named_source("wt-merge")
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
