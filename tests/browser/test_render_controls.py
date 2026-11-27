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

from leaf.source.render_checks import rendered, wait_until_ready
from leaf_dev.example_data import named_source

pytestmark = pytest.mark.shifts_unsurveyed


def _whole_and_apart(*marks):
    """Whether each mark shows whole, a dot round and a count holding its digits, and
    no two marks' boxes overlap."""
    for mark in marks:
        assert mark.evaluate(
            """mark => {
              const box = mark.getBoundingClientRect();
              return mark.textContent
                ? mark.scrollWidth <= mark.clientWidth
                : Math.abs(box.width - box.height) < 0.1;
            }"""
        ), mark
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
    """Every badge on a control stays whole beside the others, a two-digit count among
    them: a margin entry's count and unread dot, in the rail and as a pin, and the
    leaf's count, news and error, which are wider together than the leaf, clear inside
    the panel in its row and on the folded tile's outline, in either direction
    (`.lf-badges`, controls.css)."""
    source = leaf_page(
        "Badges",
        '<p id="answered">Twelve answers wait here.</p><p id="asked">One question.</p>',
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
    asked = {**answer, "author": "user", "anchor": {"section": "asked"}}
    del asked["agent"]
    questions = [
        event
        for n in range(12)
        for event in (
            {**asked, "id": f"q{n}", "text": f"Which comes {n}th?"},
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "revision": 1,
                "parent": f"q{n}",
                "responds": f"q{n}",
                "obligation": True,
                "text": "The hatch or the window?",
            },
        )
    ]
    answers = [{**answer, "text": f"Answer {n}."} for n in range(12)]
    page = open_page(browser, serve(source, events=[*answers, *questions]))
    entry = page.locator('[data-lf-margin-for="answered"]')
    for width, place in ((1440, "rail"), (700, "pin")):
        resized(page, width, 900)
        expect(entry).to_have_attribute("data-lf-place", place)
        badges = entry.locator(".lf-margin-marker > .lf-badges")
        expect(badges.locator(".lf-badge-count")).to_have_text("12")
        expect(badges.locator(".lf-unread-dot")).to_be_visible()
        assert _whole_and_apart(
            badges.locator(".lf-badge-count"), badges.locator(".lf-unread-dot")
        )

    resized(page, 1440, 900)
    # Two errors, so one waits unseen in the menu while the row's field says the other.
    page.evaluate(
        """async () => {
          const api = await window.__lfCheckApi();
          api.raiseError('Not saved');
          api.raiseError('Not sent');
        }"""
    )
    leaf = page.locator(".lf-fp-leaf > .lf-badges")
    marks = [
        leaf.locator(name)
        for name in (".lf-fp-badge", ".lf-fp-news-dot", ".lf-fp-error-dot")
    ]
    for rest in ("row", "mark"):
        if rest == "mark":
            page.keyboard.press(".")
        expect(page.locator(".lf-floating-panel")).to_have_attribute(
            "data-lf-rest", rest
        )
        # The fold's motion starts in the frame after the press.
        rendered(page)
        panel_settled(page, open=False)
        for mark in marks:
            expect(mark).to_be_visible()
        assert _whole_and_apart(*marks)
        stands = page.evaluate(_BADGE_STANDING, [m.element_handle() for m in marks])
        if rest == "row":
            # In the row the panel's card clips what crosses its edge, so each badge
            # stands clear inside it, whichever end of the row the leaf stands at.
            assert all(clear >= 4 - 0.5 for clear in stands["clear"]), stands
        else:
            # Folded, each badge is centred on the tile's outline: one at a corner on
            # its curve, one beside it on the straight edge.
            assert all(abs(off) <= 1 for off in stands["outline"]), stands


# How each of the leaf's badges stands against the panel's card: how far its box
# stands inside the card's edges (`clear`), and how far the centre of its end, a
# circle the badge's height across, stands from the card's outline, a rectangle
# with rounded corners (`outline`, positive outside).
_BADGE_STANDING = """marks => {
  const card = document.querySelector('.lf-fp-card');
  const k = card.getBoundingClientRect();
  const r = parseFloat(getComputedStyle(card).borderTopLeftRadius);
  const outline = (x, y) => {
    const qx = Math.abs(x - (k.left + k.right) / 2) - (k.width / 2 - r);
    const qy = Math.abs(y - (k.top + k.bottom) / 2) - (k.height / 2 - r);
    return Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) + Math.min(Math.max(qx, qy), 0) - r;
  };
  const clear = [], centres = [];
  for (const mark of marks) {
    const b = mark.getBoundingClientRect();
    clear.push(Math.min(b.left - k.left, k.right - b.right, b.top - k.top, k.bottom - b.bottom));
    const cap = b.height / 2;
    const x = b.right - cap < (k.left + k.right) / 2 ? b.left + cap : b.right - cap;
    centres.push(outline(x, b.top + cap));
  }
  return { clear, outline: centres };
}"""


def _dot_places(browser, serve, events, counted):
    """How far each control's dot stands from the left end of its badges' row, on a
    page whose controls show a count or none: the margin entry for `answered` in the
    rail and as a pin, and the folded leaf. Each reading finds the row and its dot in
    one call, since the runtime redraws an entry's badges."""
    source = leaf_page(
        "Dots", '<p id="answered">Answers wait here.</p><p id="asked">A question.</p>'
    )
    page = open_page(browser, serve(source, events=events))
    offset = """([row, dot]) => {
      const badges = document.querySelector(row);
      const left = badges.querySelector(dot).getBoundingClientRect().left;
      return Math.round(left - badges.getBoundingClientRect().left);
    }"""
    entry = page.locator('[data-lf-margin-for="answered"]')
    row = '[data-lf-margin-for="answered"] .lf-margin-marker > .lf-badges'
    places = {}
    for width, place in ((1440, "rail"), (700, "pin")):
        resized(page, width, 900)
        expect(entry).to_have_attribute("data-lf-place", place)
        expect(entry.locator(".lf-badge-count")).to_have_count(int(counted))
        places[place] = page.evaluate(offset, [row, ".lf-unread-dot"])

    resized(page, 1440, 900)
    page.keyboard.press(".")
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-lf-rest", "mark")
    panel_settled(page, open=False)
    expect(page.locator(".lf-fp-leaf .lf-fp-badge:visible")).to_have_count(int(counted))
    places["leaf"] = page.evaluate(
        offset, [".lf-fp-leaf > .lf-badges", ".lf-fp-news-dot"]
    )
    return places


def test_a_control_s_dot_keeps_its_corner_whether_a_count_shows(browser, serve):
    """A control's dot stands where it stood without a count once a count shows beside
    it: a margin entry's unread dot beside its count of threads, in the rail and as a
    pin, and the folded leaf's news dot beside its count of what is On me (`.lf-badges`,
    controls.css)."""
    answer = {
        "kind": "comment",
        "author": "agent",
        "agent": "Claude",
        "revision": 1,
        "text": "One answer.",
        "anchor": {"section": "answered"},
    }
    asked = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "id": "q",
        "text": "Which comes first?",
        "anchor": {"section": "asked"},
    }
    owed = {
        "kind": "reply",
        "author": "agent",
        "agent": "Claude",
        "revision": 1,
        "parent": "q",
        "responds": "q",
        "obligation": True,
        "text": "The hatch or the window?",
    }
    alone = _dot_places(browser, serve, [answer], counted=False)
    beside = _dot_places(
        browser,
        serve,
        [answer, {**answer, "text": "Another answer."}, asked, owed],
        counted=True,
    )
    assert beside == alone


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
    """Leaf navigation stays local, and a script's own focus and reveal calls still do
    what the browser's do."""
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
      import {{ focusDestination, scrollIntoView }} from '/runtime/widget-api.js';
      const {{ closeNativeLayer, showNativeLayer }} = await window.__lfCheckApi();
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
    # The practice script takes the runtime's layer calls after an await.
    child.wait_for_function("() => window.leafNavigation")
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
    # Scripts and nested embeds are still admitted, and a script's own focus call is the
    # browser's.
    assert child.evaluate(
        "() => Function.prototype.toString.call(HTMLElement.prototype.focus)"
        ".includes('[native code]')"
    )
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
    landed = child.evaluate("scrollY")
    assert landed > 0
    assert child.locator("#inner-scroll").evaluate("node => node.scrollTop") > 0

    # A script's own reveal still does what the browser's does. Leaf hears the call
    # (runtime/dom/arrivals.js) and doesn't contain it, so it shows its target in the sample
    # and, through the sample's frame, in the page around it.
    revealed = child.evaluate("""() => {
      document.querySelector('#child-control').scrollIntoView({behavior: 'instant'});
      return scrollY;
    }""")
    assert revealed < landed
    page.wait_for_function("before => scrollY > before", arg=before)
    scroll_settled(page)

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
