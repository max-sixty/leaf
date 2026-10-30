"""Walking threads with `t`, the Threads panel's keyboard, thread cards' focus and
names, and resolving with `r`."""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pytest
from interact_support import append_carried_log_record, element_declaration
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, SEATED_OBLIGATION_PAGE, panel_comment
from render_cases_layout import overlapped_words, ring_faults, rings_drawn
from render_cases_navigation import NOTED_PAGE, compose
from render_harness import (
    INLINE_PAGE,
    LONG_PAGE,
    PANEL_THREAD,
    command_reference_rows,
    comment_note,
    holding,
    leaf_page,
    open_page,
    opened_tab,
    panel_field,
    panel_settled,
    panel_view,
    primed,
    resized,
    round_trip,
    scroll_settled,
    sending,
    wait_for_check_api,
    write,
)

from browser.navigation import READING_REGIONS_PAGE
from browser.threads import open_panel_thread
from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("return_route", ["walk", "passage"])
def test_a_thread_trip_takes_over_an_outgoing_trip_before_its_first_frame(
    browser, serve, return_route
):
    """Returning to a still-visible thread cancels native travel away from it."""
    page = open_page(
        browser,
        serve(LONG_PAGE, anchored=[("p3", "Paragraph 3."), ("p41", "Paragraph 41.")]),
    )
    nearby = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    card = page.locator(f'.lf-margin-preview [data-thread="{nearby}"]')
    page.keyboard.press("t")
    expect(card).to_be_focused()
    page.evaluate(
        """async route => {
      const {executeCommand} = await window.__lfCheckApi();
      const paragraph = document.querySelector('#p3');
      const range = document.createRange();
      range.selectNodeContents(paragraph);
      const line = range.getClientRects()[0];
      const scrollTo = Element.prototype.scrollTo;
      Element.prototype.scrollTo = function(options) {
        const result = scrollTo.call(this, options);
        if (this === document.scrollingElement && options.behavior === 'smooth') {
          Element.prototype.scrollTo = scrollTo;
          window.returnSubject = document.querySelector('#p3').getBoundingClientRect().toJSON();
          queueMicrotask(() => {
            if (route === 'walk') executeCommand('thread.previous');
            else paragraph.dispatchEvent(new MouseEvent('click', {
              bubbles: true, button: 0, clientX: line.left + 8, clientY: line.top + 8,
            }));
          });
        }
        return result;
      };
    }""",
        return_route,
    )
    page.keyboard.press("t")
    page.wait_for_function("window.returnSubject !== undefined")
    expect(card).to_be_focused()
    scroll_settled(page)
    before = page.evaluate("returnSubject")
    assert 0 <= before["top"] < before["bottom"] <= page.viewport_size["height"]
    target = page.locator("#p3").bounding_box()
    assert (
        0
        <= target["y"]
        < target["y"] + target["height"]
        <= page.viewport_size["height"]
    )
    expect(page.locator(".lf-margin-preview")).to_be_in_viewport()


def test_the_thread_panel_and_a_page_thread_carry_names(browser, serve):
    """Threads opens in the panel, the region named Leaf, under its title, and a thread
    card on the page is where a send or a walk can stand the user. Both were once
    unnamed, so a screen reader arriving on either heard only "dialog" or "group"."""
    page = open_page(browser, serve(READING_REGIONS_PAGE))
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    region = page.get_by_role("region", name="Leaf", exact=True)
    expect(region.locator(panel_view("threads"))).to_be_focused()
    expect(region.locator(".lf-fp-title")).to_have_text("Threads")
    page.keyboard.press("Escape")

    page.keyboard.press("/")
    page.keyboard.type("Left start")
    page.keyboard.press("Enter")
    page.keyboard.press("c")
    page.keyboard.type("Is this landmark stable?")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-page-thread")).to_have_accessible_name(
        "Thread, Is this landmark stable?"
    )


# Each placement once and each direction once.
@pytest.mark.parametrize(
    ("width", "from_below"),
    [
        pytest.param(1440, False, id="beside-down"),
        pytest.param(390, True, id="above-or-below-up"),
    ],
)
def test_an_offscreen_thread_card_arrives_with_its_anchor(
    browser, serve, from_below, width
):
    """A distant card arrives with its anchor and retraces the same attachment on return."""
    context = "".join(f"<p>Reading context {i}.</p>" for i in range(40))
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Thread arrival",
                f"<h1>Thread arrival</h1>{context}"
                '<p id="destination">The distant passage to review.</p>'
                f"{context}",
            ),
            anchored=[("destination", "The distant passage")],
        ),
    )
    resized(page, width, 900)
    page.evaluate(
        """below => {
          scrollTo({top: below ? document.scrollingElement.scrollHeight : 0,
            behavior: 'instant'});
          window.arrivalFrames = [];
          window.sampleArrival = true;
          const sample = () => {
            const card = document.querySelector('.lf-margin-preview');
            if (card?.checkVisibility()) {
              const box = card.getBoundingClientRect();
              const target = document.querySelector('#destination').getBoundingClientRect();
              window.arrivalFrames.push({top: box.top, bottom: box.bottom,
                height: box.height, targetTop: target.top, targetBottom: target.bottom,
                head: 0,
                foot: innerHeight});
            }
            if (window.sampleArrival) requestAnimationFrame(sample);
          };
          requestAnimationFrame(sample);
        }""",
        from_below,
    )
    page.keyboard.press("t")
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_focused()
    scroll_settled(page)
    frames = page.evaluate(
        "() => { window.sampleArrival = false; return arrivalFrames; }"
    )
    distant = [
        frame
        for frame in frames
        if frame["targetBottom"] < frame["head"] - frame["height"]
        or frame["targetTop"] > frame["foot"] + frame["height"]
    ]
    assert distant, "the journey must observe the card before its passage approaches"
    assert all(
        frame["bottom"] <= frame["head"] + 1 or frame["top"] >= frame["foot"] - 1
        for frame in distant
    ), f"the card appeared ahead of its distant anchor: {distant[:3]}"
    expect(page.locator("#destination")).to_be_in_viewport()
    expect(page.locator(".lf-margin-preview")).to_be_in_viewport()

    # Retrace representative offscreen, edge-adjacent and central positions. The
    # investigation's dense sweep is unnecessary in the recurring suite: these
    # stops exercise both page attachment and viewport pinning on each placement.
    target_top = page.locator("#destination").evaluate(
        "node => node.getBoundingClientRect().top + scrollY"
    )
    positions = [target_top - top for top in [-300, 100, 450, 800, 1200]]
    outward = []
    for returning, stops in [(False, positions), (True, reversed(positions))]:
        for position in stops:
            page.evaluate("top => scrollTo({top, behavior: 'instant'})", position)
            rendered(page)
            reading = page.locator(".lf-margin-preview").evaluate(
                """node => {
                  const box = node.getBoundingClientRect();
                  return {box: [box.x, box.y, box.width, box.height],
                    plane: node.dataset.lfPlane, scroll: scrollY};
                }"""
            )
            if returning:
                previous = outward.pop()
                assert reading["scroll"] == previous["scroll"]
                assert reading["box"] == pytest.approx(previous["box"], abs=0.5)
                assert reading["plane"] == previous["plane"]
            else:
                outward.append(reading)
        if not returning:
            assert {reading["plane"] for reading in outward} == {"page", "window"}
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_focused()


# Each activation once and each surface once.
@pytest.mark.parametrize(
    ("activation", "surface"), [("click", "margin"), ("Enter", "panel")]
)
def test_a_reply_link_moves_the_thread_walk_to_its_destination(
    browser, serve, surface, activation
):
    """Following a reference makes its destination the user's reading position.

    The source message's caret must not remain the thread walk's starting point.
    Pointer and native keyboard links share that arrival with Go-to hints, from either
    thread surface.
    """
    url = serve(
        leaf_page(
            "a reply reference",
            """
<h1>Reference navigation</h1>
<p id="source">The original passage has a discussion.</p>
<p id="source-next">The next discussion before following the reference.</p>
<div style="height: 1600px"></div>
<h2 id="arrival">The linked conclusion</h2>
<p id="destination-next">The next discussion after the conclusion.</p>
<div style="height: 900px"></div>
""",
        ),
        anchored=[
            ("source", "original passage"),
            ("source-next", "next discussion before"),
            ("destination-next", "next discussion after"),
        ],
    )
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": roots[0],
            "revision": 1,
            "text": "Consider this reference.\n\n[Read the conclusion](#arrival).",
        },
    )
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1600, 900)
    if surface == "panel":
        source = open_panel_thread(page, roots[0])
    else:
        page.keyboard.press("t")
        source = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-thread="{roots[0]}"]'
        )
        expect(source).to_be_focused()

    message = source.locator(".lf-msg.agent")
    message.get_by_text("Consider this reference.", exact=True).click()
    assert message.evaluate("el => el.contains(getSelection()?.focusNode)")
    link = message.get_by_role("link", name="Read the conclusion")
    if activation == "click":
        link.click()
    else:
        for _ in range(20):
            page.keyboard.press("Tab")
            rendered(page)
            if link.evaluate("el => el.matches(':focus')"):
                break
        expect(link).to_be_focused()
        assert link.evaluate("el => el.matches(':focus-visible')")
        page.keyboard.press("Enter")
    page.wait_for_url(re.compile(r"#arrival$"))
    expect(page.locator("#arrival")).to_be_focused()
    expect(page.locator("#arrival")).to_be_in_viewport()
    page.go_back()
    if surface == "margin":
        # The card closed as the link left it, so Back returns the user to its passage.
        wait_for_check_api(page, "api => api.walkOrigin().place?.id === 'source'")
    else:
        # The panel's thread stays open, so Back returns the user to the link in it,
        # and the walk goes on from that thread.
        expect(link).to_be_focused()
    page.go_forward()
    expect(page.locator("#arrival")).to_be_focused()
    page.keyboard.press("t")
    next_thread = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-thread="{roots[2]}"]'
    )
    expect(next_thread).to_be_focused()


def test_a_tap_on_a_reply_link_to_a_missing_section_says_why(browser, serve):
    """A reply's link to a section the shown version lacks goes nowhere, and its title
    says why only to a resting pointer. A tap on it says why as an error."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Where did it go?", {"section": "how-cap"})
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": "It moved; [see the old section](#removed-section).",
        },
    )
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, url, context=context)
    view = open_panel_thread(page, root)
    link = view.get_by_role("link", name="see the old section")
    expect(link).to_have_attribute("aria-disabled", "true")
    link.tap(force=True)  # Playwright taps no aria-disabled control by itself.
    expect(panel_field(page)).to_have_attribute("data-says", "error")
    expect(panel_field(page)).to_have_attribute(
        "placeholder", "§ removed-section isn't in the version shown"
    )
    assert not page.url.endswith("#removed-section")


@pytest.mark.parametrize("shadow", [False, True], ids=["light", "shadow"])
def test_the_thread_walk_starts_at_a_fresh_fragment_reading(browser, serve, shadow):
    """A fresh fragment has no focused target or caret, but still names a reading place."""
    destination = '<h2 id="destination">The linked destination begins here.</h2>'
    layer_registry = None
    layer_widgets = None
    if shadow:
        destination = (
            '<lf-shadow-reading id="destination">'
            "The linked destination begins here.</lf-shadow-reading>"
        )
        declaration = element_declaration("lf-shadow-reading", upgrade=True)
        declaration["x-shadow"] = True
        layer_registry = {"lf-shadow-reading": declaration}
        layer_widgets = {
            "lf-shadow-reading.js": """
import { once, shadowStage } from "/runtime/widget-api.js";
customElements.define("lf-shadow-reading", class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    const paragraph = document.createElement("p");
    paragraph.textContent = this.textContent.trim();
    shadowStage(this, [paragraph]);
  }
});
"""
        }
    url = serve(
        leaf_page(
            "a fresh fragment reading",
            f"""
<h1>Reference navigation</h1>
<p id="source">The source discussion is before the destination.</p>
<div style="height: 1600px"></div>
{destination}
<p id="later">The next discussion is after the destination.</p>
<div style="height: 900px"></div>
""",
            head="<style>lf-shadow-reading {display: block}</style>",
        ),
        anchored=[
            ("source", "source discussion"),
            ("later", "next discussion"),
        ],
        layer_registry=layer_registry,
        layer_widgets=layer_widgets,
    )
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    page = open_page(browser, f"{url}#destination")
    expect(page.locator("#destination")).to_be_in_viewport()
    assert page.evaluate(
        "() => document.activeElement === document.body && getSelection().focusNode === null"
    )
    assert (
        page.evaluate(
            """async () => {
          const { readingBlock } = await window.__lfCheckApi();
          return readingBlock().getRootNode() instanceof ShadowRoot;
        }"""
        )
        == shadow
    )

    page.keyboard.press("t")
    expect(
        page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{roots[1]}"]')
    ).to_be_focused()


@pytest.mark.parametrize("key", ["t", "Shift+t"])
def test_the_thread_walk_opens_the_thread_on_the_passage_the_caret_is_in(
    browser, serve, key
):
    """A caret in a passage a thread is on is at that thread without making it the current location, so
    either direction of the walk opens it, as `m` arrives at an item holding the caret."""
    url = serve(
        leaf_page(
            "a caret on a thread",
            """
<h1>Caret walk</h1>
<p id="before">The earlier discussion comes first.</p>
<p id="here">The caret stands in this discussion.</p>
<p id="after">The later discussion comes last.</p>
""",
        ),
        anchored=[
            ("before", "earlier discussion"),
            ("here", "caret stands"),
            ("after", "later discussion"),
        ],
    )
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    page = open_page(browser, url)
    page.evaluate(
        "() => getSelection().collapse(document.querySelector('#here').firstChild, 30)"
    )
    page.keyboard.press(key)
    expect(
        page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{roots[1]}"]')
    ).to_be_focused()


@pytest.mark.parametrize("key", ["t", "Shift+t"])
def test_thread_walks_start_at_the_selected_tabs_panel(browser, serve, key):
    """Both directions measure from the open panel, not the preceding tab strip."""
    url = serve(
        leaf_page(
            "Discussions in tabs",
            '<h1>Discussions</h1><section id="wrap"><p>Intro words</p>'
            '<lf-tabs id="tabs" list="side">'
            + "".join(
                f'<lf-tab id="panel-{name.lower()}" label="{name}">'
                f'<p id="{name}">{name} discussion</p></lf-tab>'
                for name in ("First", "Second", "Third")
            )
            + "</lf-tabs></section>",
        ),
        anchored=[
            ("wrap", "Intro words"),
            *((name, f"{name} discussion") for name in ("First", "Second", "Third")),
        ],
    )
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    page = open_page(browser, url)
    page.get_by_role("tab", name="Second", exact=True).click()
    page.keyboard.press(key)
    expect(
        page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{roots[2]}"]')
    ).to_be_focused()


def test_a_thread_walk_starts_one_page_trip_and_reveals_its_nested_passage(
    browser, serve
):
    """The range travel has two jobs: reveal a passage inside its nested scrollports,
    then centre it vertically in the document. `scrollIntoView` also moved the document,
    jumping it to the nearest edge synchronously before the intended smooth centred navigation step
    began. Both local axes must remain immediate, while the page makes only one move."""
    lead = "".join(
        f"<p>Reading context before the passage, line {i}.</p>" for i in range(32)
    )
    tail = "".join(
        f"<p>Reading context after the passage, line {i}.</p>" for i in range(20)
    )
    source = leaf_page(
        "one thread navigation step",
        f"""
<h1>One thread navigation step</h1>
{lead}
<div id="local">
  {"".join(f"<p>Local context line {i}.</p>" for i in range(16))}
  <pre id="rail"><code>{"prefix " * 80}Far-side passage to review.</code></pre>
</div>
{tail}
""",
        head=(
            "<style>#local { max-height: 240px; overflow-y: auto; "
            "overflow-x: clip; }</style>"
        ),
    )
    page = open_page(
        browser,
        serve(source, anchored=[("far", "Far-side passage")]),
    )
    page.evaluate(
        """() => {
          document.scrollingElement.scrollTo({top: 0, behavior: 'instant'});
          document.querySelector('#rail').scrollLeft = 0;
          window.lfFirstPageScroll = null;
          document.addEventListener('scroll', (event) => {
            if (event.target === document && window.lfFirstPageScroll === null)
              window.lfFirstPageScroll = document.scrollingElement.scrollTop;
          }, {capture: true});
        }"""
    )

    page.keyboard.press("t")
    page.wait_for_function("() => window.lfFirstPageScroll !== null")
    immediate = page.evaluate(
        """() => ({
          firstPage: window.lfFirstPageScroll,
          rail: document.querySelector('#rail').scrollLeft,
          local: document.querySelector('#local').scrollTop,
          localXFits: document.querySelector('#local').scrollWidth
            <= document.querySelector('#local').clientWidth,
        })"""
    )
    assert immediate["firstPage"] < 100, (
        f"the thread walk jumped the page before its smooth navigation step began: {immediate}"
    )
    assert immediate["rail"] > 0, (
        f"the passage stayed beyond its own horizontal scroller: {immediate}"
    )
    assert immediate["local"] > 0, (
        f"the passage stayed beyond its own vertical scroller: {immediate}"
    )
    assert immediate["localXFits"], (
        f"the vertical scrollport also overflowed sideways: {immediate}"
    )
    page.wait_for_function(
        """() => {
          const range = [...(CSS.highlights.get('lf-mark-here') ?? [])][0];
          if (!range) return false;
          const rect = range.getBoundingClientRect();
          // The middle of the room the page shows, between the window's head and the
          // panel at its foot, which the root's scroll padding states.
          const style = getComputedStyle(document.scrollingElement);
          const top = parseFloat(style.scrollPaddingTop);
          const bottom = innerHeight - parseFloat(style.scrollPaddingBottom);
          return Math.abs((rect.top + rect.bottom) / 2 - (top + bottom) / 2) < 2;
        }"""
    )
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_focused()


# Ways to arrive at, move within, and step back from a thread's margin card. `@mark` is a
# keyboard arrival on the first passage's mark; `@marker` is a press on its margin marker.
CARD_ROUTES = {
    "walk": ["t"],
    "walk, back to its element": ["t", "Escape"],
    "walk, let go": ["t", "Escape", "Escape"],
    "walk on, back to its element": ["t", "t", "Escape"],
    "walk, Tab within the card": ["t", "Tab"],
    "walk, go to the page": ["t", "g", "p"],
    "reply, back out to its element": ["t", "c", "Escape", "Escape"],
    "arrive at the mark": ["@mark"],
    "arrive at the mark, step back": ["@mark", "Escape"],
    "press the marker": ["@marker"],
}


@pytest.mark.parametrize("route", CARD_ROUTES.values(), ids=CARD_ROUTES.keys())
def test_c_lands_where_its_badge_is_and_in_the_card_on_screen(browser, serve, route):
    """A card's reply wears `c`; after letting go, the page control opens its box.

    The card's being up decides the reply destination. When it is gone, `c` stands in
    the panel's page comment. The box's placeholder is the runtime's own record of the
    hint, even while it is not drawn.
    """
    page = open_page(
        browser,
        serve(INLINE_PAGE, anchored=[("p", "bold text"), ("p2", "neighbouring block")]),
    )
    page.set_viewport_size({"width": 1600, "height": 900})
    for step in route:
        if step == "@mark":
            page.keyboard.press(
                "Tab"
            )  # keyboard modality, so the focus below is visible
            comment_note(page, "#p").focus()
        elif step == "@marker":
            page.locator('.lf-margin-marker[data-lf-kinds="comment"]').first.click()
        else:
            page.keyboard.press(step)
        rendered(page)

    badged = page.locator("leaf-text[placeholder$=' c']")
    card = page.locator(".lf-margin-preview")
    if route == CARD_ROUTES["walk, let go"]:
        expect(card).to_be_hidden()
        # The panel's page comment wears `c` now.
        expect(badged).to_have_count(1)
        expect(badged).to_have_attribute("name", "comment")
        page.keyboard.press("c")
        rendered(page)
        expect(page.locator('.lf-fp-field leaf-text[name="comment"]')).to_be_focused()
        return

    expect(card).to_be_visible()
    expect(badged).to_have_count(1)
    box = badged.element_handle()
    assert box.evaluate("box => Boolean(box.closest('.lf-margin-preview'))")
    expect(badged.locator(".lf-compose-placeholder > .lf-key-badge")).to_be_visible()
    page.keyboard.press("c")
    rendered(page)
    assert box.evaluate("box => box === document.activeElement")


@pytest.mark.parametrize("width", [1200, 600])
def test_go_to_threads_lands_on_threads_from_a_page_thread(browser, serve, width):
    """g T has one destination regardless of the selected page thread: Threads, in the
    panel, focused on the row of the thread the user last visited where there is one, and
    Escape puts it away onto the page."""
    page = open_page(
        browser,
        serve(INLINE_PAGE, anchored=[("p", "bold text"), ("p2", "neighbouring block")]),
    )
    resized(page, width, 844)
    threads = page.locator(panel_view("threads"))
    for from_thread in (False, True):
        if from_thread:
            page.keyboard.press("t")
            page.keyboard.press("t")
            current_location = page.locator(".lf-margin-preview .lf-page-thread")
            expect(current_location).to_be_focused()
            # The second of the two threads, so the first row is not the answer.
            stood_in = current_location.get_attribute("data-thread")
        page.keyboard.press("g")
        page.keyboard.press("Shift+t")
        # From the page the view takes focus; from a page thread, that thread's row.
        expect(
            threads.locator(f'.lf-fp-thread[data-key="{stood_in}"]')
            if from_thread
            else threads
        ).to_be_focused()
        page.keyboard.press("Escape")
        panel_settled(page, open=False)
        assert page.evaluate("document.activeElement === document.body")


def test_a_thread_walk_shows_one_thread_at_a_time(browser, serve):
    """A walk shows the thread it lands on and no other, so `c` and the walk's position
    have one thread to mean. From a thread open in the panel, `t` to a thread about a
    passage opens its card and puts the panel's view away; from that card, `t` to a
    thread about the whole page opens it in the panel and closes the card. Both once
    stayed open, and the panel said "Thread 2 of 2" under the thread the user had
    left."""
    url = serve(INLINE_PAGE)
    first = panel_comment(
        serve.page_dir, "About the bold text.", {"section": "p", "quote": "bold text"}
    )
    second = panel_comment(
        serve.page_dir,
        "About the neighbour.",
        {"section": "p2", "quote": "neighbouring block"},
    )
    general = panel_comment(serve.page_dir, "About the whole page.")
    page = open_page(browser, url)
    view = open_panel_thread(page, first)
    # The caret leaves the reply for the view, where the thread's keys answer.
    page.keyboard.press("Escape")
    expect(view).to_be_focused()

    page.keyboard.press("t")
    card = page.locator(".lf-margin-preview")
    expect(card.locator(f'.lf-page-thread[data-thread="{second}"]')).to_be_focused()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)

    page.keyboard.press("t")
    expect(page.locator(f'{PANEL_THREAD}[data-thread="{general}"]')).to_be_focused()
    expect(card).to_be_hidden()


def test_an_inline_thread_rings_its_card_for_keyboard_focus(browser, serve):
    """Keyboard arrival rings the thread; its reply shows a cue by either input route."""
    page = open_page(
        browser,
        serve(INLINE_PAGE, anchored=[("p", "bold text")]),
    )
    thread = page.locator(".lf-margin-preview .lf-page-thread")
    preview = page.locator(".lf-margin-preview")
    # The preview root owns placement; its face carries the complete card's ring.
    face = preview.locator(".lf-margin-preview-card")
    paint = """el => {
      const s = getComputedStyle(el);
      return {
        outline: s.outlineStyle, offset: s.outlineOffset,
        background: s.backgroundColor, shadow: s.boxShadow,
      };
    }"""

    page.locator('.lf-margin-marker[data-lf-kinds="comment"]').first.click()
    expect(thread).to_be_focused()
    pointer = face.evaluate(paint)
    assert pointer["outline"] == "none"
    drawn = rings_drawn(page)
    assert not any(ring["sample"] for ring in drawn), drawn
    assert not ring_faults(drawn, "the thread opened by pointer")

    page.keyboard.press("Escape")
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    current = face.evaluate(paint)
    assert current["outline"] == "solid"
    assert current["offset"] == "-2px"
    assert current["background"] == pointer["background"]
    drawn = rings_drawn(page)
    assert any(ring["sample"] for ring in drawn), drawn
    assert not ring_faults(drawn, "the thread reached by keyboard")

    page.keyboard.press("Enter")
    reply = thread.locator("leaf-text")
    expect(reply).to_be_focused()
    writing = face.evaluate(paint)
    assert writing["outline"] == "none"
    assert writing["background"] == pointer["background"]
    drawn = rings_drawn(page)
    assert len(drawn) == 1, drawn
    assert ".lf-compose-field" in drawn[0]["rule"] and drawn[0]["sample"], drawn
    assert not ring_faults(drawn, "the focused reply box")

    # The reply delegates focus into its shadow tree. Pointer arrival preserves the
    # same field ring, without returning it to the enclosing card.
    thread.click(position={"x": 3, "y": 3})
    expect(thread).to_be_focused()
    reply.click()
    expect(reply).to_be_focused()
    pointer_reply = rings_drawn(page)
    assert len(pointer_reply) == 1, pointer_reply
    assert pointer_reply[0]["rule"] == drawn[0]["rule"]
    assert pointer_reply[0]["sample"], pointer_reply
    assert not ring_faults(pointer_reply, "the reply box focused by pointer")


def test_forced_colors_keep_inline_thread_focus_visible(browser, serve):
    """The system focus outline replaces the surface paint high contrast removes."""
    url = serve(SEATED_OBLIGATION_PAGE)
    root = panel_comment(
        serve.page_dir, "Which job should come first?", {"section": "jobs"}
    )
    context = browser.new_context(forced_colors="active")
    page = open_page(
        browser,
        url,
        context=context,
    )
    thread = page.locator(f'#jobs .lf-page-thread[data-thread="{root}"]')

    reply = thread.locator("leaf-text")
    reply.click()
    expect(reply).to_be_focused()
    assert thread.evaluate("el => el.matches(':focus-within')")
    focus = thread.evaluate(
        """el => { const s = getComputedStyle(el); return {
              style: s.outlineStyle, width: s.outlineWidth,
              offset: s.outlineOffset, shadow: s.boxShadow,
            }; }"""
    )
    assert focus == {
        "style": "solid",
        "width": "2px",
        "offset": "-2px",
        "shadow": "none",
    }


def test_inline_thread_surface_has_room_without_focus_reflow(browser, serve):
    """Thread controls and complete messages keep their room when the reply is focused."""
    url = serve(SEATED_OBLIGATION_PAGE)
    panel_comment(serve.page_dir, "First job note", {"section": "jobs"})
    root = panel_comment(
        serve.page_dir, "Which job should come first?", {"section": "jobs"}
    )
    page = open_page(browser, url)
    thread = page.locator(f'#jobs .lf-page-thread[data-thread="{root}"]')
    expect(page.locator("#jobs .lf-page-thread")).to_have_count(2)

    resting = thread.evaluate(
        "el => ({width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height})"
    )
    reply = thread.locator("leaf-text")
    reply.click()
    expect(reply).to_be_focused()
    focused = thread.evaluate(
        "el => ({width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height})"
    )
    assert focused == resting, (
        "the current surface changed the inline thread's geometry"
    )

    frame = thread.evaluate(
        """el => { const s = getComputedStyle(el); return {
          padding: [s.paddingTop, s.paddingRight, s.paddingBottom, s.paddingLeft],
          borderTop: s.borderTopWidth,
        }; }"""
    )
    assert len(set(frame["padding"])) == 1, (
        f"a later inline thread inherited an asymmetric current edge: {frame}"
    )
    assert frame["borderTop"] == "0px", (
        f"a sibling separator remained inside the current region: {frame}"
    )

    separator = thread.evaluate(
        """el => { const s = getComputedStyle(el, '::before'); return {
          content: s.content, borderTop: s.borderTopWidth,
        }; }"""
    )
    assert separator == {
        "content": '""',
        "borderTop": "1px",
    }, f"the gap between inline threads lost its separator: {separator}"

    resolve = thread.locator(":scope .lf-thread-meta-actions > .lf-resolve")
    expect(resolve).to_have_css("position", "relative")
    placement = thread.evaluate(
        """el => {
          const own = el.getBoundingClientRect();
          const inset = parseFloat(getComputedStyle(el).paddingTop);
          const actions = el.querySelector(
            ':scope .lf-thread-meta-actions'
          ).getBoundingClientRect();
          const control = el.querySelector(
            ':scope .lf-thread-meta-actions > .lf-resolve'
          ).getBoundingClientRect();
          const controls = el.querySelector(
            ':scope > .lf-thread-content > .lf-thread-controls'
          ).getBoundingClientRect();
          const headNode = el.querySelector(
            ':scope .lf-msg > .lf-msg-head'
          );
          const head = headNode.getBoundingClientRect();
          const author = headNode.querySelector('b').getBoundingClientRect();
          const bodyNode = el.querySelector(
            ':scope .lf-msg > .lf-msg-body'
          );
          const body = bodyNode.getBoundingClientRect();
          return {actionsTop: actions.top, actionsBottom: actions.bottom,
                  controlTop: control.top, expectedTop: own.top + inset,
                  controlBottom: control.bottom, controlsTop: controls.top,
                  controlsBottom: controls.bottom, headTop: head.top,
                  headBottom: head.bottom, headRight: head.right,
                  controlLeft: control.left, controlsLeft: controls.left,
                  authorBottom: author.bottom,
                  bodyTop: body.top,
                  bodyMargin: parseFloat(getComputedStyle(bodyNode).marginTop)};
        }"""
    )
    assert placement["controlTop"] == pytest.approx(placement["controlsTop"], abs=1)
    assert placement["actionsTop"] == pytest.approx(placement["controlTop"], abs=1)
    assert placement["actionsBottom"] == pytest.approx(
        placement["controlBottom"], abs=1
    )
    assert placement["controlBottom"] <= placement["controlsBottom"]
    assert placement["headTop"] == pytest.approx(placement["controlsTop"], abs=1)
    assert placement["headRight"] <= placement["controlLeft"], placement
    # The controls' box stands past the header's words, not over them: axe reads what
    # covers words by geometry, so a box spanning the line, however transparent, leaves
    # the author and time with no contrast reading (`overlapped_words`).
    assert placement["headRight"] <= placement["controlsLeft"], placement
    assert overlapped_words(page) == []
    assert placement["bodyTop"] - placement["headBottom"] == pytest.approx(
        placement["bodyMargin"], abs=1
    ), f"the first inline message has extra space below its author: {placement}"

    clearances = thread.evaluate(
        """el => {
          const root = el.getBoundingClientRect();
          return [...el.children]
            .filter(child => child.getClientRects().length && getComputedStyle(child).display !== 'none')
            .flatMap(child => {
              const box = child.getBoundingClientRect();
              return [box.left - root.left, root.right - box.right,
                      box.top - root.top, root.bottom - box.bottom];
            });
        }"""
    )
    assert clearances and min(clearances) >= 3, (
        f"the current surface landed on inline thread content: {clearances}"
    )


def test_submitting_a_reply_reveals_its_new_message(browser, serve):
    """A send lands the new message in the open thread's view, whole where it fits and
    its end where it does not, and leaves the user in the reply."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Where should this explanation go?")
    page = open_page(browser, url)
    resized(page, 800, 520)
    view = open_panel_thread(page, root)
    box = panel_field(page)
    write(box, "First point. " * 5 + "\n\nSecond point. " * 4)
    box.press("Enter")
    round_trip(page)
    message = view.locator(".lf-msg.user").last
    expect(message).to_contain_text("Second point.")
    page.wait_for_function(
        """([view, message]) => {
          const band = view.getBoundingClientRect();
          const box = message.getBoundingClientRect();
          return box.top >= band.top - 1 && box.bottom <= band.bottom + 1;
        }""",
        arg=[view.element_handle(), message.element_handle()],
    )
    expect(panel_field(page)).to_be_focused()

    write(box, "Long reply. " * 90)
    box.press("Enter")
    round_trip(page)
    long_message = view.locator(".lf-msg.user").last
    expect(long_message).to_contain_text("Long reply.")
    page.wait_for_function(
        """([view, message]) => {
          const band = view.getBoundingClientRect();
          const box = message.getBoundingClientRect();
          return box.height > band.height && box.bottom <= band.bottom + 1
            && box.bottom > band.top;
        }""",
        arg=[view.element_handle(), long_message.element_handle()],
    )
    expect(panel_field(page)).to_be_focused()


def test_r_resolves_the_focused_thread_while_x_is_unbound(browser, serve):
    """A focused thread resolves on r while x remains unbound, and r reopens it."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir

    def comment(text):
        return append_carried_log_record(
            d, {"kind": "comment", "author": "user", "revision": 1, "text": text}
        )["id"]

    c1 = comment("First thought.")
    comment("Second thought.")
    page = open_page(browser, url)

    # The thread route is contextual: the complete reference teaches it before focus.
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_contain_text("In a thread")
    thread_section = command_reference_rows(page, "In a thread")
    expect(thread_section.get_by_text("Resolve", exact=True)).to_have_count(1)
    page.keyboard.press("Escape")

    # x has no command. r resolves the thread the walk stands on.
    page.keyboard.press("t")
    first = page.locator(f'{PANEL_THREAD}[data-thread="{c1}"]')
    expect(first).to_be_focused()
    page.keyboard.press("x")
    rendered(page)
    expect(first).to_be_visible()
    assert not any(
        event["kind"] == "resolve" for event in events_model.read_events(serve.page_dir)
    )
    with sending(page, "the resolve"):
        page.keyboard.press("r")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "resolve"

    # The same key reopens a focused resolved thread.
    open_panel_thread(page, c1).focus()
    expect(page.locator(".lf-fp-settle")).to_have_accessible_name("Reopen")
    with sending(page, "the reopen"):
        page.keyboard.press("r")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "unresolve"
    expect(page.locator(".lf-fp-settle")).to_have_accessible_name("Resolve thread")


def test_r_resolves_a_thread_from_wherever_the_user_stands_in_it(browser, serve):
    """r settles the thread holding focus, not only a focused card.

    A click on a thread's words focuses the message, so a card-only reach left the
    user's most common way in pressing a letter that did nothing. The Resolve button,
    a link in a reply, and the message each reach it; the reply box keeps the letter."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir
    threads = []
    for i in range(4):
        root = append_carried_log_record(
            d,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"Thought {i}.",
            },
        )["id"]
        append_carried_log_record(
            d,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "parent": root,
                "revision": 1,
                "text": f"Reply {i}, citing [a source](https://example.com/{i}).",
            },
        )
        threads.append(root)
    page = open_page(browser, url)

    def card(n):
        return open_panel_thread(page, threads[n])

    def resolved():
        return [
            event["parent"]
            for event in events_model.read_events(d)
            if event["kind"] == "resolve"
        ]

    # The reply box is in the thread too, and its typing claim stands first.
    view = card(0)
    box = panel_field(page)
    box.click()
    page.keyboard.press("r")
    expect(box).to_have_js_property("value", "r")
    write(box, "")
    page.keyboard.press("Escape")
    expect(view).to_be_focused()

    # A pointer on the reply's words stands the user on the part drawing them, not
    # the view.
    message = view.locator(".lf-primary-part", has_text="Reply 0")
    message.get_by_text("Reply 0", exact=False).first.click()
    expect(message).to_be_focused()
    with sending(page, "the resolve from a message"):
        page.keyboard.press("r")
    assert resolved() == [threads[0]]

    card(1).locator(".lf-msg a[href]").focus()
    with sending(page, "the resolve from a link"):
        page.keyboard.press("r")
    assert resolved() == threads[:2]

    card(2)
    page.locator(".lf-fp-settle").focus()
    with sending(page, "the resolve from its button"):
        page.keyboard.press("r")
    assert resolved() == threads[:3]


def thread_url(url, name, fragment=""):
    parts = urlsplit(url)
    query = [*parse_qsl(parts.query), ("thread", name)]
    return urlunsplit(parts._replace(query=urlencode(query), fragment=fragment))


def thread_page(serve):
    filler = "".join(f"<p>Reading context {n}.</p>" for n in range(40))
    return serve(
        leaf_page(
            "Thread links",
            '<h1 id="start">Thread links</h1>'
            '<a href="?thread=general1">Open the page discussion</a>'
            '<input aria-label="Your notes">'
            f'{filler}<p id="target">The distant passage.</p>'
            f'<a href="#start">Back to the heading</a>{filler}',
        ),
        events=[
            {
                "kind": "comment",
                "id": "anchor01",
                "author": "user",
                "revision": 1,
                "anchor": {"section": "target"},
                "text": "About the distant passage.",
            },
            {
                "kind": "comment",
                "id": "general1",
                "author": "user",
                "revision": 1,
                "text": "About the whole page.",
            },
        ],
    )


def linked_thread(page, name):
    return page.locator(
        f':is(.lf-page-thread:not([data-lf-part]), .lf-fp-view)[data-thread="{name}"]'
    )


@pytest.mark.parametrize("name", ["anchor01", "general1"])
def test_thread_url_opens_its_canonical_surface_on_arrival(browser, serve, name):
    page = open_page(browser, thread_url(thread_page(serve), name))
    thread = linked_thread(page, name)
    expect(thread).to_be_focused()
    expect(thread).to_be_in_viewport()
    scroll_settled(page)
    if name == "anchor01":
        expect(page.locator("#target")).to_be_in_viewport()
    entries = page.evaluate("history.length")
    page.reload()
    wait_until_ready(page)
    expect(thread).to_be_focused()
    assert page.evaluate("history.length") == entries
    if name == "anchor01":
        # Leaving the passage puts its card away. Back reveals that thread again.
        link = page.get_by_role("link", name="Back to the heading")
        link.click()
        expect(page.locator("#start")).to_be_in_viewport()
        expect(thread).not_to_be_visible()
        page.go_back()
        expect(thread).to_be_visible()
        expect(page.locator("#target")).to_be_in_viewport()
    else:
        # A primary reader stays shown while the user reads elsewhere on the page.
        # Returning to its URL must keep that reading position as well.
        page.locator("#target").scroll_into_view_if_needed()
        scroll_settled(page)
        reading_offset = page.evaluate("scrollY")
        page.evaluate("location.hash = 'start'")
        expect(page.locator("#start")).to_be_in_viewport()
        page.go_back()
        expect(page.locator("#target")).to_be_in_viewport()
        assert page.evaluate("scrollY") == pytest.approx(reading_offset, abs=1)


def test_following_a_thread_url_uses_native_history(browser, serve):
    page = open_page(browser, thread_page(serve))
    entries = page.evaluate("history.length")
    page.get_by_role("link", name="Open the page discussion").click()
    wait_until_ready(page)
    expect(linked_thread(page, "general1")).to_be_focused()
    assert page.evaluate("history.length") == entries + 1
    page.go_back()
    wait_until_ready(page)
    assert "thread=" not in page.url
    page.go_forward()
    wait_until_ready(page)
    expect(linked_thread(page, "general1")).to_be_focused()
    assert page.evaluate("history.length") == entries + 1


def test_authored_fragment_takes_precedence_over_thread_query(browser, serve):
    page = open_page(browser, thread_url(thread_page(serve), "general1", "target"))
    expect(page.locator("#target")).to_be_in_viewport()
    expect(page.locator('.lf-page-thread[data-thread="general1"]')).to_have_count(0)


def test_unknown_thread_url_reports_the_missing_destination(browser, serve):
    page = open_page(browser, thread_url(thread_page(serve), "missing1"))
    expect(page.locator(".lf-live")).to_contain_text("Thread missing1 is unavailable")
    expect(page.locator(".lf-page-thread")).to_have_count(0)


def test_thread_url_takes_priority_over_automatic_draft_recovery(browser, serve):
    url = thread_page(serve)
    page = open_page(browser, url)
    compose(page, "#target", "Keep this unsent comment")
    page.goto(thread_url(url, "general1"))
    wait_until_ready(page)
    expect(linked_thread(page, "general1")).to_be_focused()
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-fab-input")).to_have_js_property(
        "value", "Keep this unsent comment"
    )


def test_input_during_startup_cancels_thread_url_arrival(browser, serve):
    held = []
    page = open_page(
        primed(
            browser,
            lambda page: page.route("**/api/state*", lambda route: held.append(route)),
        ),
        thread_url(thread_page(serve), "general1"),
        upgraded=False,
    )
    holding(page, held, 1, "initial state")
    page.get_by_role("textbox", name="Your notes").fill("Keep my place")
    page.unroute("**/api/state*")
    for route in held:
        route.continue_()
    wait_until_ready(page)
    expect(page.get_by_role("textbox", name="Your notes")).to_be_focused()
    expect(page.locator('.lf-page-thread[data-thread="general1"]')).to_have_count(0)


def test_thread_url_reveals_a_tab_despite_its_generated_display_fragment(
    browser, one_user, serve
):
    url = serve(
        leaf_page(
            "Tabbed thread",
            '<h1 id="start">Tabbed thread</h1>'
            '<lf-tabs id="views"><lf-tab id="first" label="First"><p>First view.</p>'
            '</lf-tab><lf-tab id="second" label="Second">'
            '<p id="target">The discussed passage.</p>'
            '<a href="#start">Return to the heading</a></lf-tab></lf-tabs>',
        ),
        events=[
            {
                "kind": "comment",
                "id": "anchor01",
                "author": "user",
                "revision": 1,
                "anchor": {"section": "target"},
                "text": "About the second view.",
            },
            {
                "kind": "reply",
                "id": "answer01",
                "parent": "anchor01",
                "author": "agent",
                "agent": "Codex",
                "revision": 1,
                "text": "The answer.",
            },
        ],
    )
    page = open_page(browser, thread_url(url, "answer01"), context=one_user)
    expect(linked_thread(page, "anchor01")).to_be_focused()
    expect(page.locator("#target")).to_be_in_viewport()
    assert page.evaluate("history.length") == 2
    assert urlsplit(page.url).fragment == ""
    page.reload()
    wait_until_ready(page)
    expect(linked_thread(page, "anchor01")).to_be_focused()
    page.emulate_media(reduced_motion="no-preference")
    page.evaluate(
        """() => {
          const preview = document.querySelector('.lf-margin-preview');
          preview.addEventListener('transitionrun', function hold(event) {
            if (event.propertyName !== 'opacity' || !preview.inert) return;
            for (const animation of preview.getAnimations()) animation.pause();
            preview.removeEventListener('transitionrun', hold);
          });
        }"""
    )
    page.get_by_role("tab", name="First", exact=True).click()
    expect(page.locator("#first")).to_be_visible()
    assert urlsplit(page.url).fragment == "first"
    page.wait_for_function(
        """() => {
          const preview = document.querySelector('.lf-margin-preview');
          return preview.inert && preview.getAnimations().some(a => a.playState === 'paused');
        }"""
    )
    page.go_back()
    wait_until_ready(page)
    assert page.locator("#second").is_visible()
    expect(linked_thread(page, "anchor01")).to_be_visible()
    assert urlsplit(page.url).fragment == ""
    # Opening an authored fragment link in a new document inherits the query,
    # just as Copy Link or Open in New Tab does.
    heading_url = page.get_by_role("link", name="Return to the heading").evaluate(
        "link => link.href"
    )
    assert "t" not in dict(parse_qsl(urlsplit(page.url).query))
    heading_tab = opened_tab(
        page,
        heading_url,
        lambda: page.get_by_role("link", name="Return to the heading").click(
            button="middle"
        ),
    )
    wait_until_ready(heading_tab)
    expect(heading_tab.locator("#start")).to_be_in_viewport()
    expect(linked_thread(heading_tab, "anchor01")).to_have_count(0)
