"""Walking threads with `t`, the Threads panel's keyboard, thread cards' focus and
names, and resolving with `r`."""

import re

import pytest
from interact_support import append_carried_log_record, element_declaration
from leaf import event_log as events_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, SEATED_ASK_PAGE, panel_comment
from render_cases_layout import in_threads_scrollport, ring_faults, rings_drawn
from render_cases_navigation import NOTED_PAGE
from render_harness import (
    INLINE_PAGE,
    LONG_PAGE,
    command_reference_rows,
    comment_note,
    leaf_page,
    open_page,
    panel_settled,
    resized,
    round_trip,
    scroll_settled,
    sending,
    shortcut_bar_text,
    write,
)

from browser.navigation import (
    EXPANDED,
    READING_REGIONS_PAGE,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_thread_panel_and_a_page_thread_carry_names(browser, serve):
    """The Threads panel is a dialog, beside the page or covering it, and a thread card
    on the page is where a send or a walk can stand the user. Both were unnamed, so a
    screen reader arriving on either heard only "dialog" or "group"."""
    page = open_page(browser, serve(READING_REGIONS_PAGE))
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    dialog = page.get_by_role("dialog", name="Threads", exact=True)
    expect(dialog).to_have_attribute("open", "")
    expect(dialog.locator(".lf-thread-panel")).to_be_visible()
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
                head: document.querySelector('.lf-banner').getBoundingClientRect().bottom,
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
        page.locator(".lf-threads-toggle").click()
        panel_settled(page, True)
        source = page.locator(f'.lf-threads > .lf-thread[data-id="{roots[0]}"]')
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
    page.wait_for_function("""async () => {
      const {walkOrigin} = await window.__lfCheckApi();
      return walkOrigin().place?.id === 'source';
    }""")
    page.go_forward()
    expect(page.locator("#arrival")).to_be_focused()
    page.keyboard.press("t")
    if surface == "panel":
        next_thread = page.locator(
            f'.lf-threads > .lf-thread[data-id="{roots[2]}"] > .lf-thread-summary'
        )
    else:
        next_thread = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-thread="{roots[2]}"]'
        )
    expect(next_thread).to_be_focused()


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
    """A caret in a passage a thread is on is at that thread without standing on it, so
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


def test_the_arrows_walk_the_thread_titles_in_the_threads_panel(browser, serve):
    """From a thread's title in the Threads panel the arrows step between the visible
    titles, and Home and End go to the ends, as they walk the On panel's rows.
    Inside an open thread they are not the list's: from a message the arrows leave the
    titles alone."""
    page = open_page(browser, serve(LONG_PAGE, comments=3))
    resized(page, 1280, 900)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, True)
    titles = page.locator(".lf-thread-panel .lf-thread-summary")
    expect(titles).to_have_count(3)
    position = page.locator(".lf-walk-position")

    titles.first.focus()
    expect(titles.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(titles.nth(1)).to_be_focused()
    expect(position).to_have_text("Thread 2 of 3")
    page.keyboard.press("End")
    expect(titles.nth(2)).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(titles.nth(2)).to_be_focused()
    expect(position).to_have_attribute("data-lf-boundary", "")
    page.keyboard.press("Home")
    expect(titles.first).to_be_focused()
    page.keyboard.press("ArrowUp")
    expect(titles.first).to_be_focused()

    # A message in the open thread: the same keys move no title.
    thread = page.locator(EXPANDED)
    expect(thread).to_have_count(1)
    message = thread.locator(".lf-msg").first
    message.focus()
    expect(message).to_be_focused()
    page.keyboard.press("ArrowDown")
    page.keyboard.press("End")
    rendered(page)
    expect(message).to_be_focused()


def test_a_thread_walk_starts_one_page_trip_and_reveals_its_nested_passage(
    browser, serve
):
    """The range travel has two jobs: reveal a passage inside its nested scrollports,
    then centre it vertically in the document. `scrollIntoView` also moved the document,
    jumping it to the nearest edge synchronously before the intended smooth centred trip
    began. Both local axes must remain immediate, while the page makes only one move."""
    lead = "".join(
        f"<p>Reading context before the passage, line {i}.</p>" for i in range(32)
    )
    tail = "".join(
        f"<p>Reading context after the passage, line {i}.</p>" for i in range(20)
    )
    source = leaf_page(
        "one thread trip",
        f"""
<h1>One thread trip</h1>
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
        f"the thread walk jumped the page before its smooth trip began: {immediate}"
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
          return Math.abs((rect.top + rect.bottom) / 2 - innerHeight / 2) < 2;
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

    The card's being up decides the reply destination. When it is gone, the banner's
    page-comment control advertises `c` and creates its editor when pressed. The box's
    placeholder is the runtime's own record of the hint, even while it is not drawn.
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
        expect(badged).to_have_count(0)
        expect(page.locator(".lf-page-comment")).to_have_attribute(
            "title", "Comment on the page (c)"
        )
        page.keyboard.press("c")
        rendered(page)
        expect(page.locator(".lf-page-comment-card leaf-text")).to_be_focused()
        return

    expect(card).to_be_visible()
    expect(badged).to_have_count(1)
    box = badged.element_handle()
    assert box.evaluate("box => Boolean(box.closest('.lf-margin-preview'))")
    expect(badged.locator(".lf-compose-placeholder > .lf-key-badge")).to_be_visible()
    page.keyboard.press("c")
    rendered(page)
    assert box.evaluate("box => box === document.activeElement")


@pytest.mark.parametrize("side", ["note", "marker"])
def test_threads_answers_c_in_the_thread_it_expanded_for_a_target(browser, serve, side):
    """With Threads open, the list's expanded thread plays the margin card's part.

    Arriving at a commented element by the keyboard expands its thread in the list, and
    standing there is standing at that thread: its reply box wears `c`, `c` lands in
    it, and the walk goes on from it. Every side of the target answers alike, so the
    arrival is made from the target's comment note and from its margin marker.
    """
    url = serve(
        INLINE_PAGE, anchored=[("p", "bold text"), ("p2", "neighbouring block")]
    )
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    page = open_page(browser, url)
    page.set_viewport_size({"width": 1600, "height": 900})
    page.locator(".lf-threads-toggle").click()
    panel_settled(page, True)
    listed = [
        page.locator(f'.lf-threads > .lf-thread[data-id="{root}"]') for root in roots
    ]
    line = page.locator(".lf-shortcut-bar")

    # The list opens with the first thread expanded, so the second target is the one
    # whose arrival has to move it.
    expect(listed[1]).not_to_have_attribute("open", "")
    page.keyboard.press("Tab")  # keyboard modality, so the focus below is visible
    if side == "note":
        comment_note(page, "#p2").focus()
    else:
        page.locator('[data-lf-margin-for="p2"] .lf-margin-marker').focus()
    expect(listed[1]).to_have_attribute("open", "")
    reply = listed[1].locator("leaf-text")
    expect(reply).to_have_attribute("placeholder", "Reply c")
    expect(line).to_contain_text("comment on the thread")
    page.keyboard.press("c")
    expect(reply).to_be_focused()

    page.keyboard.press("Escape")
    expect(listed[1].locator(":scope > .lf-thread-summary")).to_be_focused()
    comment_note(page, "#p").focus()
    expect(listed[0]).to_have_attribute("open", "")
    page.keyboard.press("t")
    expect(listed[1].locator(":scope > .lf-thread-summary")).to_be_focused()


LIST_ROUTES = {
    "go to Threads": ["g", "Shift+t"],
    "walk to a title": ["g", "Shift+t", "t"],
}


# Each route once and each width once.
@pytest.mark.parametrize(
    ("route", "width"),
    [
        pytest.param(LIST_ROUTES["go to Threads"], 1600, id="go to Threads-1600"),
        pytest.param(LIST_ROUTES["walk to a title"], 420, id="walk to a title-420"),
    ],
)
def test_the_threads_list_hands_focus_to_the_thread_it_shows_open(
    browser, serve, route, width
):
    """Focus given to the list lands on its open thread, so every key answers for it.

    The open card fills the list, and the list's own ring once drew round it while
    `c` wrote in the page box and Escape, `r` and the shading treated the stop as the
    whole panel. The list keeps focus itself only while it shows no thread
    (`test_c_comments_and_g_t_navigates_to_threads`). From the thread, Escape is the
    panel's own: it closes.

    At 420px the panel covers the page, which drops the page's own `c` unless it
    declares itself covering.
    """
    page = open_page(
        browser,
        serve(INLINE_PAGE, anchored=[("p", "bold text"), ("p2", "neighbouring block")]),
    )
    page.set_viewport_size({"width": width, "height": 900})
    for step in route:
        page.keyboard.press(step)
        rendered(page)

    card = page.locator(EXPANDED)
    expect(card).to_have_count(1)
    expect(card.locator(":scope > .lf-thread-summary")).to_be_focused()
    reply = card.locator("leaf-text")
    if width > 420:  # the narrow line and boxes draw no key badges
        expect(page.locator("leaf-text[placeholder$=' c']")).to_have_count(1)
        expect(reply).to_have_attribute("placeholder", "Reply c")
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    panel_settled(page, False)


def test_a_title_taking_focus_opens_its_thread(browser, serve):
    """Focus on a collapsed title opens its thread, so the focused thread is always the
    open one and its reply box is the one carrying `c`. A title once held focus closed
    while another card stood open, and `c` wrote into a box nothing on screen named."""
    page = open_page(
        browser,
        serve(INLINE_PAGE, anchored=[("p", "bold text"), ("p2", "neighbouring block")]),
    )
    page.set_viewport_size({"width": 1600, "height": 900})
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    cards = page.locator(".lf-threads > .lf-thread")
    expect(cards.nth(0)).to_have_attribute("open", "")
    title = cards.nth(1).locator(":scope > .lf-thread-summary")
    title.focus()
    expect(cards.nth(1)).to_have_attribute("open", "")
    expect(cards.nth(0)).not_to_have_attribute("open", "")
    expect(page.locator(EXPANDED)).to_have_count(1)
    reply = cards.nth(1).locator("leaf-text")
    expect(reply).to_have_attribute("placeholder", "Reply c")
    page.keyboard.press("c")
    expect(reply).to_be_focused()


def test_threads_panel_keeps_one_visible_thread_open_through_resolution(browser, serve):
    url = serve(PANEL_PAGE)
    roots = [panel_comment(serve.page_dir, f"Thread {i}.") for i in range(3)]
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page, True)

    def card(index):
        return page.locator(f'.lf-threads > .lf-thread[data-id="{roots[index]}"]')

    expanded = page.locator(".lf-threads > .lf-thread:not([hidden])[open]")
    expect(expanded).to_have_count(1)
    expect(card(0)).to_have_attribute("open", "")

    card(1).locator(":scope > .lf-thread-summary").click()
    expect(expanded).to_have_count(1)
    expect(card(1)).to_have_attribute("open", "")
    card(1).locator(":scope > .lf-thread-summary").click()
    expect(expanded).to_have_count(1)
    expect(card(1)).to_have_attribute("open", "")
    card(1).locator(":scope > .lf-thread-summary").focus()
    page.keyboard.press("Space")
    expect(expanded).to_have_count(1)
    expect(card(1)).to_have_attribute("open", "")

    card(1).get_by_role("button", name="Resolve thread").click()
    round_trip(page)
    expect(expanded).to_have_count(1)
    expect(card(2)).to_have_attribute("open", "")
    expect(card(2).locator(":scope > .lf-thread-summary")).to_be_focused()

    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    expect(expanded).to_have_count(1)
    expect(card(1)).to_have_attribute("open", "")


@pytest.mark.parametrize("width", [1200, 600])
def test_go_to_threads_lands_on_the_open_thread_from_a_page_thread(
    browser, serve, width
):
    """g T has one destination regardless of the selected page thread.

    That destination is the title of the thread Threads shows open, the same thread
    whether the user stood on the page or walked to another page thread first.
    """
    page = open_page(
        browser,
        serve(INLINE_PAGE, anchored=[("p", "bold text"), ("p2", "neighbouring block")]),
    )
    resized(page, width, 844)
    panel = page.locator(".lf-thread-panel")
    landings = []
    for from_thread in (False, True):
        if from_thread:
            page.keyboard.press("t")
            page.keyboard.press("t")
            expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_focused()
        page.keyboard.press("g")
        page.keyboard.press("Shift+t")
        expect(panel).to_be_visible()
        expect(page.locator(f"{EXPANDED} > .lf-thread-summary")).to_be_focused()
        landings.append(page.locator(EXPANDED).get_attribute("data-id"))
        expect(page.locator(".lf-margin-preview")).to_be_hidden()
        page.keyboard.press("Escape")
        expect(panel).to_be_hidden()
        assert page.evaluate("document.activeElement === document.body")
    assert landings[0] == landings[1], landings

    # A pointer press on the door does carry the page thread it began beside.
    page.keyboard.press("t")
    page.keyboard.press("t")
    selected = page.locator(".lf-margin-preview .lf-page-thread").get_attribute(
        "data-thread"
    )
    page.locator(".lf-threads-toggle").click()
    expect(panel).to_be_visible()
    expect(
        page.locator(f'.lf-thread[data-id="{selected}"] > .lf-thread-summary')
    ).to_be_focused()


def test_an_inline_thread_rings_its_card_for_pointer_and_keyboard_focus(browser, serve):
    """Either arrival rings the thread; entering its reply gives the ring to the field."""
    page = open_page(
        browser,
        serve(INLINE_PAGE, anchored=[("p", "bold text")]),
    )
    thread = page.locator(".lf-margin-preview .lf-page-thread")
    preview = page.locator(".lf-margin-preview")
    # The margin preview carries its thread's ring around the complete floating card.
    paint = """el => {
      const s = getComputedStyle(el);
      const after = getComputedStyle(el, '::after');
      const ring = after.content !== 'none' && after.outlineStyle !== 'none' ? after : s;
      return {
        outline: ring.outlineStyle, offset: ring.outlineOffset,
        background: s.backgroundColor, shadow: s.boxShadow,
      };
    }"""

    page.locator('.lf-margin-marker[data-lf-kinds="comment"]').first.click()
    expect(thread).to_be_focused()
    pointer = preview.evaluate(paint)
    assert pointer["outline"] == "solid"
    assert pointer["offset"] == "-2px"
    drawn = rings_drawn(page)
    assert any(ring["sample"] for ring in drawn), drawn
    assert not ring_faults(drawn, "the thread opened by pointer")

    page.keyboard.press("Escape")
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    current = preview.evaluate(paint)
    assert current == pointer

    page.keyboard.press("Enter")
    reply = thread.locator("leaf-text")
    expect(reply).to_be_focused()
    writing = preview.evaluate(paint)
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
    url = serve(SEATED_ASK_PAGE)
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
    url = serve(SEATED_ASK_PAGE)
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
                  controlLeft: control.left,
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
    """A send lands the new message in the list's band with the reply area under it,
    and leaves the user on the thread's title."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Where should this explanation go?")
    page = open_page(browser, url)
    resized(page, 800, 520)
    page.locator(".lf-threads-toggle").click()
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    thread.locator(".lf-thread-summary").click()
    box = thread.locator(":scope > .lf-thread-reply leaf-text")
    write(box, "First point. " * 5 + "\n\nSecond point. " * 4)
    box.press("Enter")
    round_trip(page)
    message = thread.locator(".lf-msg.user").last
    expect(message).to_contain_text("Second point.")
    scroll_settled(page, ".lf-threads")
    shown = message.evaluate(
        """node => {
          const list = document.querySelector('.lf-threads').getBoundingClientRect();
          const message = node.getBoundingClientRect();
          const style = getComputedStyle(document.querySelector('.lf-threads'));
          const top = list.top + parseFloat(style.scrollPaddingTop || 0);
          const ringRoom = parseFloat(style.getPropertyValue('--focus-ring-w'))
            + parseFloat(style.getPropertyValue('--focus-ring-gap'));
          return {top: message.top, bottom: message.bottom, bandTop: top,
                  textTop: top - ringRoom, bandBottom: list.bottom};
        }"""
    )
    assert shown["bottom"] - shown["top"] < shown["bandBottom"] - shown["bandTop"]
    # The reserved ring room protects focusable controls; a posted message has no ring.
    assert shown["top"] >= shown["textTop"] - 1, shown
    assert shown["bottom"] <= shown["bandBottom"] + 1, shown
    expect(thread.locator(".lf-thread-summary")).to_be_focused()
    in_threads_scrollport(
        page, f'.lf-thread[data-id="{root}"] .lf-thread-reply leaf-text'
    )

    write(box, "Long reply. " * 90)
    thread.locator(":scope > .lf-thread-reply .lf-thread-send").click()
    round_trip(page)
    long_message = thread.locator(".lf-msg.user").last
    expect(long_message).to_contain_text("Long reply.")
    scroll_settled(page, ".lf-threads")
    long_reading = long_message.evaluate(
        """node => {
          const list = document.querySelector('.lf-threads');
          const band = list.getBoundingClientRect();
          const top = band.top + parseFloat(getComputedStyle(list).scrollPaddingTop || 0);
          const message = node.getBoundingClientRect();
          return {top: message.top, bottom: message.bottom, height: message.height,
                  bandTop: top, bandBottom: band.bottom, room: band.bottom - top};
        }"""
    )
    assert long_reading["height"] > long_reading["room"]
    assert long_reading["bottom"] <= long_reading["bandBottom"] + 1
    assert long_reading["bottom"] > long_reading["bandTop"]
    expect(thread.locator(".lf-thread-summary")).to_be_focused()
    in_threads_scrollport(
        page, f'.lf-thread[data-id="{root}"] .lf-compose-field > button:not([hidden])'
    )


def test_r_resolves_the_focused_thread_while_x_is_unbound(browser, serve):
    """A focused thread resolves on r while x remains unbound.

    The visible Resolve and Reopen controls retain their native keyboard routes."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir

    def comment(text):
        return append_carried_log_record(
            d, {"kind": "comment", "author": "user", "revision": 1, "text": text}
        )["id"]

    c1 = comment("First thought.")
    c2 = comment("Second thought.")
    page = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 2")
    line = page.locator(".lf-shortcut-bar")

    # The thread route is contextual: the complete reference teaches it before focus,
    # while the short line offers it only after the user stands in a thread.
    expect(line).not_to_contain_text("resolve")
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_contain_text("In a thread")
    thread_section = command_reference_rows(page, "In a thread")
    expect(thread_section.get_by_text("Resolve it", exact=True)).to_have_count(1)
    page.keyboard.press("Escape")

    # x has no command. r resolves the thread, with the button's existing
    # landing taking focus to the next thread.
    page.keyboard.press("t")
    first = page.locator(f'.lf-thread[data-id="{c1}"]')
    expect(first.locator(":scope > .lf-thread-summary")).to_be_focused()
    expect(line).to_contain_text("resolve")
    page.keyboard.press("x")
    expect(first).to_be_visible()
    assert not any(
        event["kind"] == "resolve" for event in events_model.read_events(serve.page_dir)
    )
    page.keyboard.press("r")
    round_trip(page)
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")
    expect(
        page.locator(f'.lf-thread[data-id="{c2}"] > .lf-thread-summary')
    ).to_be_focused()

    # The same key reopens a focused resolved thread.
    page.locator(".lf-thread-filter-toggle").click()
    page.locator('[data-filter-value="resolved"]').click()
    resolved = page.locator(f'.lf-thread[data-id="{c1}"]:not([hidden])')
    resolved.locator(":scope > .lf-thread-summary").focus()
    expect(line).to_contain_text("reopen")
    page.keyboard.press("r")
    round_trip(page)
    reopened = page.locator(f'.lf-threads > .lf-thread[data-id="{c1}"]')
    expect(reopened.locator(":scope > .lf-thread-reply leaf-text")).to_be_focused()
    expect(line).to_contain_text("back to thread")
    page.keyboard.press("Escape")
    expect(reopened.locator(":scope > .lf-thread-summary")).to_be_focused()
    expect(line).to_contain_text("comment on the thread")


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
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    def card(n):
        return page.locator(f'.lf-thread[data-id="{threads[n]}"]')

    def resolved():
        return [
            event["parent"]
            for event in events_model.read_events(d)
            if event["kind"] == "resolve"
        ]

    # The reply box is in the thread too, and its typing claim stands first.
    card(0).locator(".lf-thread-summary").click()
    box = card(0).locator(":scope > .lf-thread-reply leaf-text")
    box.click()
    page.keyboard.press("r")
    expect(box).to_have_js_property("value", "r")
    write(box, "")
    page.keyboard.press("Escape")
    expect(card(0).locator(":scope > .lf-thread-summary")).to_be_focused()

    # A pointer on the reply's words stands the user on the message, not the card.
    message = card(0).locator(".lf-msg.agent")
    message.locator(".lf-msg-head").click()
    expect(message).to_be_focused()
    assert "resolve" in shortcut_bar_text(page)
    with sending(page, "the resolve from a message"):
        page.keyboard.press("r")
    assert resolved() == [threads[0]]
    expect(card(1).locator(":scope > .lf-thread-summary")).to_be_focused()

    card(1).locator(".lf-msg a[href]").focus()
    with sending(page, "the resolve from a link"):
        page.keyboard.press("r")
    assert resolved() == threads[:2]

    card(2).locator(":scope > .lf-thread-summary").click()
    card(2).get_by_role("button", name="Resolve").focus()
    with sending(page, "the resolve from its button"):
        page.keyboard.press("r")
    assert resolved() == threads[:3]
