"""Walking threads with `t`, the Threads panel's keyboard, thread cards' focus and
names, and resolving with `r`."""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pytest
from interact_support import append_carried_log_record, element_declaration
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, SEATED_OBLIGATION_PAGE, panel_comment
from render_cases_layout import overlapped_words, ring_faults, ring_rule, rings_drawn
from render_cases_navigation import NOTED_PAGE, compose
from render_harness import (
    INLINE_PAGE,
    LONG_PAGE,
    before_landing_frame,
    command_reference_rows,
    comment_note,
    holding,
    leaf_page,
    open_page,
    open_threads,
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
    without_end_room,
    write,
)

from browser.navigation import READING_REGIONS_PAGE, expect_walk_position
from browser.threads import open_panel_thread
from leaf.log import event_log as events_model
from leaf.source.render_checks import rendered, wait_until_ready
from leaf_dev.browser import PANEL_THREAD, choose_threads_in_panel

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("return_route", ["walk", "passage"])
def test_a_thread_trip_takes_over_an_outgoing_trip_before_its_first_frame(
    browser, serve, return_route
):
    """Returning to a still-visible thread cancels the trip away from it."""
    page = open_page(
        browser,
        serve(LONG_PAGE, anchored=[("p3", "Paragraph 3."), ("p41", "Paragraph 41.")]),
    )
    nearby = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    card = page.locator(f'.lf-margin-preview [data-lf-thread="{nearby}"]')
    page.keyboard.press("t")
    expect(card).to_be_focused()
    before_landing_frame(
        page,
        """window.__lfCheckApi().then(({executeCommand}) => {
      const paragraph = document.querySelector('#p3');
      const range = document.createRange();
      range.selectNodeContents(paragraph);
      const line = range.getClientRects()[0];
      return route => {
        window.returnSubject = paragraph.getBoundingClientRect().toJSON();
        queueMicrotask(() => {
          if (route === 'walk') executeCommand('thread.previous');
          else paragraph.dispatchEvent(new MouseEvent('click', {
            bubbles: true, button: 0, clientX: line.left + 8, clientY: line.top + 8,
          }));
        });
      };
    })""",
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
    card on the page is where a send or a walk can stand the user. Were either unnamed,
    a screen reader arriving on it would hear only "dialog" or "group"."""
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


# Each direction once. A window too narrow for the rail opens threads in the
# floating panel, never a card.
@pytest.mark.parametrize("from_below", [False, True], ids=["down", "up"])
def test_an_offscreen_thread_card_arrives_with_its_anchor(browser, serve, from_below):
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
    resized(page, 1440, 900)
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
    thread surface. The walk goes on in the place the user chose for threads: a card
    after a thread read in its card, and the panel once they chose the panel.
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
            f'.lf-margin-preview .lf-page-thread[data-lf-thread="{roots[0]}"]'
        )
        expect(source).to_be_focused()

    message = source.locator(".lf-msg[data-lf-author=agent]")
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
        f'{PANEL_THREAD}[data-lf-thread="{roots[2]}"]'
        if surface == "panel"
        else f'.lf-margin-preview .lf-page-thread[data-lf-thread="{roots[2]}"]'
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
    # It reads as going nowhere too: muted, its underline dashed.
    expect(link).to_have_css("text-decoration-style", "dashed")
    link.tap(force=True)  # Playwright taps no aria-disabled control by itself.
    expect(panel_field(page)).to_have_attribute("data-lf-says", "error")
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
        declaration["shadow"] = True
        layer_registry = {"lf-shadow-reading": declaration}
        layer_widgets = {
            "lf-shadow-reading.js": """
import { shadowStage } from "/runtime/widget-api.js";
import { once } from "/runtime/lib/once.js";
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
        page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{roots[1]}"]')
    ).to_be_focused()


def test_the_thread_walk_opens_the_thread_on_the_passage_the_caret_is_in(
    browser, serve, subtests
):
    """A caret in a passage a thread is on is at that thread without making it the current location, so
    either direction of the walk opens it, as `m` arrives at an item holding the caret.
    Each direction starts from a passage of its own, since the Escape between them leaves
    the user beside the thread the first opened."""
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
    for key, passage, root in (
        ("t", "#here", roots[1]),
        ("Shift+t", "#after", roots[2]),
    ):
        with subtests.test(key=key):
            page.evaluate(
                "passage => getSelection().collapse("
                "document.querySelector(passage).firstChild, 30)",
                passage,
            )
            page.keyboard.press(key)
            expect(
                page.locator(
                    f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]'
                )
            ).to_be_focused()
        page.keyboard.press("Escape")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_caret_in_an_age_is_where_the_thread_walk_starts(engine, request, serve):
    """A caret in an age's drawn words, which a shadow root holds, is in the age in either
    engine, so the walk opens the thread on the age's paragraph as it would from the
    paragraph's own words. The caret goes there as caret browsing walks it, by the
    engine's own caret movement (`Selection.modify`)."""
    url = serve(
        leaf_page(
            "a caret in an age",
            """
<h1>Caret walk</h1>
<p id="before">The earlier discussion comes first.</p>
<p id="here">The import ran <lf-age datetime="2026-11-20T02:10:00Z">20 Nov</lf-age>,
which this discussion is about.</p>
<p id="after">The later discussion comes last.</p>
""",
        ),
        anchored=[
            ("before", "earlier discussion"),
            ("here", "this discussion"),
            ("after", "later discussion"),
        ],
    )
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    page = open_page(request.getfixturevalue(engine), url)
    assert page.evaluate(
        """() => {
          const age = document.querySelector('#here lf-age');
          const words = age.previousSibling;
          getSelection().collapse(words, words.length);
          getSelection().modify('move', 'forward', 'character');
          getSelection().modify('move', 'forward', 'character');
          const [caret] = getSelection().getComposedRanges({ shadowRoots: [age.shadowRoot] });
          return caret.startContainer.getRootNode() === age.shadowRoot;
        }"""
    )
    page.keyboard.press("t")
    expect(
        page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{roots[1]}"]')
    ).to_be_focused()


@pytest.mark.parametrize("enters", ["c", "Enter"])
def test_the_thread_walk_stops_at_each_unsent_comment(browser, serve, enters):
    """A comment the user began and put away is a stop of the thread walk, in the page's
    order among the open threads, as Threads lists the two together, a comment about a
    passage of a paragraph holding a thread included. The walk opens the comment's box
    on its words and stands the user on the box, not in it, so the next `t` walks on and
    puts the box away, and `c` or Enter puts the caret after the words. While the user
    stands on the box it keeps its resting edge, so it doesn't look like one they type
    in, and wears `c` as a key chip, since its words cover the placeholder that says
    `c`."""
    url = serve(
        leaf_page(
            "drafts in the walk",
            """
<h1>Drafts in the walk</h1>
<p id="first">The first paragraph takes a comment on the whole of it.</p>
<p id="second">The second paragraph holds the open thread and a comment on a passage.</p>
""",
        ),
        anchored=[("second", "open thread")],
    )
    page = open_page(browser, url)
    field = page.locator(".lf-fab-input")
    box = page.locator("#lf-composer .lf-compose-field")
    page.locator("#first").click(modifiers=["Alt"])
    write(field, "About the first.")
    page.keyboard.press("Escape")
    page.evaluate(
        """() => {
          const text = document.getElementById('second').firstChild;
          const at = text.data.indexOf('a passage');
          getSelection().setBaseAndExtent(text, at, text, at + 'a passage'.length);
        }"""
    )
    page.keyboard.press("c")
    write(field, "About the passage.")
    page.keyboard.press("Escape")
    # A press on the page starts the walk from what the window shows.
    page.locator("h1").click()

    page.keyboard.press("t")
    expect(box).to_be_focused()
    expect(field).to_have_js_property("value", "About the first.")
    expect_walk_position(page, "1 of 3 threads and drafts")
    page.keyboard.press("t")
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_focused()
    expect(page.locator(".lf-composer[data-lf-open]")).to_have_count(0)
    page.keyboard.press("t")
    expect(box).to_be_focused()
    expect(field).to_have_js_property("value", "About the passage.")
    chip = page.locator(".lf-command-binding-badges .lf-command-binding-badge")
    expect(chip.filter(has_text="c")).to_be_visible()
    assert ring_rule(box) == ""
    assert ring_rule(box, "after") == ""
    page.keyboard.press(enters)
    expect(chip).to_have_count(0)
    expect(field).to_be_focused()
    assert ring_rule(box, "after")
    expect(field).to_have_js_property("value", "About the passage.")
    expect(field).to_have_js_property("selectionStart", len("About the passage."))


def test_a_thread_stop_wears_c_on_a_reply_box_holding_words(browser, serve):
    """A thread card the walk stands on whose reply box holds a draft wears `c` as a chip
    on that box's corner, since the draft's words cover the placeholder that says `c`
    in an empty box. `c` puts the caret after the words, and the chip goes."""
    url = serve(
        leaf_page(
            "a reply draft",
            '<h1>A reply draft</h1><p id="said">The thread on this paragraph waits.</p>',
        ),
        anchored=[("said", "thread on this paragraph")],
    )
    page = open_page(browser, url)
    card = page.locator(".lf-margin-preview .lf-page-thread")
    reply = card.locator("leaf-text")
    chip = page.locator(".lf-command-binding-badges .lf-command-binding-badge")
    page.locator("h1").click()
    page.keyboard.press("t")
    expect(card).to_be_focused()
    expect(chip).to_have_count(0)
    page.keyboard.press("c")
    write(reply, "Left unsent.")
    page.keyboard.press("Escape")
    page.locator("h1").click()

    page.keyboard.press("t")
    expect(card).to_be_focused()
    expect(chip.filter(has_text="c")).to_be_visible()
    frame = card.locator(".lf-compose-field").bounding_box()
    at = chip.bounding_box()
    assert frame and at
    assert abs(at["x"] + at["width"] / 2 - frame["x"]) < 2
    assert abs(at["y"] + at["height"] / 2 - frame["y"]) < 2
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("selectionStart", len("Left unsent."))
    expect(chip).to_have_count(0)


def test_the_thread_walk_reaches_a_resolved_thread_holding_an_unsent_reply(
    browser, serve
):
    """A thread resolved with a reply still unsent is a stop of the walk, which opens it
    where the reply's words wait, so `t` reaches every draft Threads lists."""
    url = serve(
        leaf_page(
            "a resolved thread with a reply",
            '<h1>Resolved</h1><p id="said">The thread on this paragraph is resolved.</p>',
        ),
        anchored=[("said", "thread on this paragraph")],
    )
    page = open_page(browser, url)
    page.locator('[data-lf-margin-for="said"] .lf-margin-marker').click()
    reply = page.locator(".lf-margin-preview .lf-page-thread leaf-text")
    write(reply, "A reply left unsent.")
    page.locator(".lf-margin-preview .lf-resolve").click()
    page.locator("h1").click()

    page.keyboard.press("t")
    expect(page.locator(PANEL_THREAD)).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("leaf-text:focus")).to_have_js_property(
        "value", "A reply left unsent."
    )


def test_the_thread_walk_reaches_a_thread_in_view_ahead_of_the_first_paragraph(
    browser, serve
):
    """With nothing focused the walk starts from what the window shows, so `t` at the top
    of a page opening with a question of options alone opens the thread on those
    options, not the one on the paragraph below them that is the first the page
    reads."""
    url = serve(
        leaf_page(
            "a thread on options alone",
            """
<lf-group id="ask" label="Which route?"><lf-options id="routes">
  <lf-option id="routes-left">Take the left route</lf-option>
  <lf-option id="routes-right">Take the right route</lf-option>
</lf-options></lf-group>
<p id="later">The later discussion follows the question.</p>
""",
        ),
        anchored=[("routes-left", "left route"), ("later", "later discussion")],
    )
    first = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    page = open_page(browser, url)
    page.keyboard.press("t")
    expect(
        page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{first}"]')
    ).to_be_focused()


def test_thread_walks_start_at_the_selected_tabs_panel(browser, serve, subtests):
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
    for key in ("t", "Shift+t"):
        with subtests.test(key=key):
            page.get_by_role("tab", name="Second", exact=True).click()
            page.keyboard.press(key)
            expect(
                page.locator(
                    f'.lf-margin-preview .lf-page-thread[data-lf-thread="{roots[2]}"]'
                )
            ).to_be_focused()
        page.keyboard.press("Escape")


def test_a_thread_walk_starts_one_page_trip_and_reveals_its_nested_passage(
    browser, serve
):
    """The range travel has two jobs: reveal a passage inside its nested scrollports,
    then centre it vertically in the document. `scrollIntoView` also moved the document,
    jumping it to the nearest edge in the press's own task before the smooth centred
    navigation step began. Both local axes must move in that task, while the page waits
    for its glide (dom/scrolling.js, `glideTo`), whose frames carry it to the centre in one
    trip: each one further down, never turning back."""
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
  <pre id="rail" style="white-space: pre"><code>{"prefix " * 80}Far-side passage to review.</code></pre>
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
        serve(source, anchored=[("local", "Far-side passage")]),
    )
    page.evaluate(
        """() => {
          document.scrollingElement.scrollTo({top: 0, behavior: 'instant'});
          document.querySelector('#rail').scrollLeft = 0;
          window.lfPageTrip = [];
          window.lfAfterPress = null;
          document.addEventListener('scroll', (event) => {
            if (event.target === document)
              window.lfPageTrip.push(document.scrollingElement.scrollTop);
          }, {capture: true});
          // Nothing is focused, so the key is aimed at the page itself, and the
          // runtime answers it in its capture listener on the document. Registered
          // after that one, this reads the press's task once the walk has.
          document.addEventListener('keydown', () => {
            window.lfAfterPress = {
              page: document.scrollingElement.scrollTop,
              rail: document.querySelector('#rail').scrollLeft,
              local: document.querySelector('#local').scrollTop,
              localXFits: document.querySelector('#local').scrollWidth
                <= document.querySelector('#local').clientWidth,
            };
          }, {capture: true});
        }"""
    )

    page.keyboard.press("t")
    page.wait_for_function("() => window.lfAfterPress !== null")
    immediate = page.evaluate("() => window.lfAfterPress")
    assert immediate["page"] == 0, (
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
    # The root's landing band at the window's foot, over the floating panel's cover.
    foot = page.evaluate(
        "async () => (await window.__lfWidgetApi()).landingInsets("
        "document.scrollingElement).bottom"
    )
    page.wait_for_function(
        """foot => {
          const range = [...(CSS.highlights.get('lf-mark-here') ?? [])][0];
          if (!range) return false;
          const rect = range.getBoundingClientRect();
          // The middle of the room the page shows, between the window's head and the
          // panel at its foot.
          const style = getComputedStyle(document.scrollingElement);
          const top = parseFloat(style.scrollPaddingTop);
          const bottom = innerHeight - foot;
          return Math.abs((rect.top + rect.bottom) / 2 - (top + bottom) / 2) < 2;
        }""",
        arg=foot,
    )
    trip = page.evaluate("() => window.lfPageTrip")
    assert trip and trip == sorted(trip), (
        f"the page made more than one trip to the passage: {trip}"
    )
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_focused()


# Ways to arrive at, move within, and step back from a thread's margin card. `@mark` is a
# keyboard arrival on the first passage's mark; `@marker` is a press on its margin marker.
CARD_ROUTES = {
    "walk": (["t"], True),
    "walk, close the card": (["t", "Escape"], False),
    "walk on, close the card": (["t", "t", "Escape"], False),
    "walk, Tab within the card": (["t", "Tab"], True),
    "walk, go to the page": (["t", "g", "p"], True),
    "reply, back to the thread": (["t", "c", "Escape"], True),
    "arrive at the mark": (["@mark"], True),
    "arrive at the mark, step back": (["@mark", "Escape"], True),
    "press the marker, back to the thread": (["@marker", "Escape"], True),
}


def test_c_lands_where_its_badge_is_and_in_the_card_on_screen(browser, serve, subtests):
    """A card's reply wears `c`; closing the card hands `c` to the page comment.

    While On Me lists anything the panel's row offers Next On Me rather than `c`, so
    once the card closes no box wears `c`, and `c` still enters the page comment.

    Escape from a reply returns to its thread; Escape from the thread closes the card.
    The badge and the press must agree in both states. The box's placeholder is the
    runtime's own record of the hint, even while it is not drawn. Each route writes
    nothing and two Escapes take the page back to no card, so the routes share one page.
    """
    page = open_page(
        browser,
        serve(INLINE_PAGE, anchored=[("p", "bold text"), ("p2", "neighbouring block")]),
    )
    page.set_viewport_size({"width": 1600, "height": 900})
    badged = page.locator("leaf-text[placeholder$=' c']")
    card = page.locator(".lf-margin-preview")

    for name, (route, card_open) in CARD_ROUTES.items():
        with subtests.test(route=name):
            for step in route:
                if step == "@mark":
                    # Keyboard modality, so the focus below is visible.
                    page.keyboard.press("Tab")
                    comment_note(page, "#p").focus()
                elif step == "@marker":
                    page.locator(
                        '.lf-margin-marker[data-lf-kinds="comment"]'
                    ).first.click()
                else:
                    page.keyboard.press(step)
                rendered(page)

            if card_open:
                expect(card).to_be_visible()
                expect(badged).to_have_count(1)
                box = badged.element_handle()
                assert box.evaluate("box => Boolean(box.closest('.lf-margin-preview'))")
                expect(
                    badged.locator(".lf-compose-placeholder > .lf-key-badge")
                ).to_be_visible()
                page.keyboard.press("c")
                rendered(page)
                assert box.evaluate("box => box === document.activeElement")
            else:
                expect(card).to_be_hidden()
                expect(badged).to_have_count(0)
                page.keyboard.press("c")
                rendered(page)
                expect(
                    page.locator('.lf-fp-field leaf-text[name="comment"]')
                ).to_be_focused()
        page.keyboard.press("Escape")
        page.keyboard.press("Escape")
        expect(card).to_be_hidden()


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
            # A margin card on a wide window; the panel's thread on a phone.
            current_location = page.locator(
                f"{PANEL_THREAD}, .lf-margin-preview .lf-page-thread"
            )
            expect(current_location).to_be_focused()
            # The second of the two threads, so the first row is not the answer.
            stood_in = current_location.get_attribute("data-lf-thread")
        page.keyboard.press("g")
        page.keyboard.press("Shift+t")
        # From the page the view stands on its first row; from a page thread, on that
        # thread's row.
        expect(
            threads.locator(f'.lf-fp-thread[data-lf-key="{stood_in}"]')
            if from_thread
            else threads.locator(".lf-fp-thread").first
        ).to_be_focused()
        page.keyboard.press("Escape")
        panel_settled(page, open=False)
        assert page.evaluate("document.activeElement === document.body")

    # g T puts away the Threads it opened, as Escape does.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(threads).to_be_visible()
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, open=False)


def test_a_thread_walk_shows_one_thread_at_a_time(browser, serve):
    """A walk shows the thread it lands on and no other, so `c` and the walk's position
    have one thread to mean. From the thread about the whole page, open in the panel,
    `t` to a thread about a passage opens its card and puts the panel's view away; from
    a card, `t` to the thread about the whole page opens it in the panel and closes the
    card. Were both to stay open, the panel would say "Thread 2 of 2" under the thread
    the user had left."""
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
    view = open_panel_thread(page, general)
    # The caret leaves the reply for the view, where the thread's keys answer.
    page.keyboard.press("Escape")
    expect(view).to_be_focused()

    # The thread about the whole page stands after every passage's, so `t` comes round
    # to the first.
    page.keyboard.press("t")
    card = page.locator(".lf-margin-preview")
    expect(card.locator(f'.lf-page-thread[data-lf-thread="{first}"]')).to_be_focused()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)

    page.keyboard.press("t")
    expect(card.locator(f'.lf-page-thread[data-lf-thread="{second}"]')).to_be_focused()
    page.keyboard.press("t")
    expect(page.locator(f'{PANEL_THREAD}[data-lf-thread="{general}"]')).to_be_focused()
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
    expect(preview.locator("leaf-text")).to_be_focused()
    pointer = face.evaluate(paint)
    assert pointer["outline"] == "none"
    drawn = rings_drawn(page)
    assert [".lf-compose-field" in ring["rule"] for ring in drawn] == [True], drawn
    assert not ring_faults(drawn, "the thread opened by pointer")

    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
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
    assert face.evaluate(paint)["outline"] == "none"
    drawn_on_thread = rings_drawn(page)
    assert not any(ring["sample"] for ring in drawn_on_thread), drawn_on_thread
    reply.click()
    expect(reply).to_be_focused()
    pointer_reply = rings_drawn(page)
    assert len(pointer_reply) == 1, pointer_reply
    assert pointer_reply[0]["rule"] == drawn[0]["rule"]
    assert pointer_reply[0]["sample"], pointer_reply
    assert not ring_faults(pointer_reply, "the reply box focused by pointer")


def test_a_walk_lands_on_a_thread_in_its_seat_in_view(browser, serve):
    """A walk to a thread an element seats lands on it there, not in a card beside the
    element showing the same thread, and in view: the element its seat makes taller
    than the window is no reason to take the thread back out of view."""
    url = serve(
        SEATED_OBLIGATION_PAGE.replace(
            "</main>",
            "".join(f"<p id='f{i}'>{'Words. ' * 120}</p>" for i in range(8))
            + "</main>",
        )
    )
    roots = [
        panel_comment(
            serve.page_dir,
            f"Thread {n}. " + "These jobs can share one visit. " * 4,
            {"section": "jobs"},
        )
        for n in range(6)
    ]
    page = open_page(browser, url)
    resized(page, 1280, 600)
    page.locator("#f6").click()
    page.keyboard.press("End")
    page.wait_for_function("() => scrollY > 1500")
    scroll_settled(page)
    page.keyboard.press("Shift+t")
    last = page.locator(f'#jobs .lf-page-thread[data-lf-thread="{roots[-1]}"]')
    expect(last).to_be_focused()
    scroll_settled(page)
    expect(last).to_be_in_viewport()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()


def test_forced_colors_keep_inline_thread_focus_visible(browser, serve):
    """A forced palette drops the shadow that frames a seated card, so the card keeps
    its frame as an outline on its edge, and the reply box focused in it still draws
    its own ring, on its `::after` over what the box holds (response.css)."""
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
    thread = page.locator(f'#jobs .lf-page-thread[data-lf-thread="{root}"]')

    reply = thread.locator("leaf-text")
    reply.click()
    expect(reply).to_be_focused()
    assert thread.evaluate("el => el.matches(':focus-within')")
    frame = thread.evaluate(
        """el => { const s = getComputedStyle(el); return {
              style: s.outlineStyle, width: s.outlineWidth,
              offset: s.outlineOffset, shadow: s.boxShadow,
            }; }"""
    )
    assert frame == {
        "style": "solid",
        "width": "1px",
        "offset": "0px",
        "shadow": "none",
    }
    ring = thread.locator(".lf-compose-field").evaluate(
        "el => { const s = getComputedStyle(el, '::after');"
        " return [s.outlineStyle, s.outlineWidth]; }"
    )
    assert ring == ["solid", "2px"], ring


def test_inline_thread_surface_has_room_without_focus_reflow(browser, serve):
    """Thread controls and complete messages keep their room when the reply is focused."""
    url = serve(SEATED_OBLIGATION_PAGE)
    panel_comment(serve.page_dir, "First job note", {"section": "jobs"})
    root = panel_comment(
        serve.page_dir, "Which job should come first?", {"section": "jobs"}
    )
    page = open_page(browser, url)
    thread = page.locator(f'#jobs .lf-page-thread[data-lf-thread="{root}"]')
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

    # Seated threads are framed cards a gap apart, not rules between bare threads.
    apart = thread.evaluate(
        """el => { const s = getComputedStyle(el);
          const before = getComputedStyle(el, '::before');
          const previous = el.previousElementSibling.getBoundingClientRect();
          return {gap: el.getBoundingClientRect().top - previous.bottom,
                  frame: s.boxShadow !== 'none', rule: before.content}; }"""
    )
    assert apart["gap"] > 0 and apart["frame"], apart
    assert apart["rule"] == "none", apart

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

    # The reply box runs to the card's sides and foot, inside its hairline; the
    # thread's controls and messages keep their room inside its padding.
    reply_row = thread.locator(":scope > .lf-thread-reply").evaluate(
        """row => { const box = row.getBoundingClientRect();
          const card = row.parentElement.getBoundingClientRect();
          return [box.left - card.left, card.right - box.right, card.bottom - box.bottom]; }"""
    )
    assert reply_row == [1, 1, 1], reply_row
    clearances = thread.evaluate(
        """el => {
          const root = el.getBoundingClientRect();
          return [...el.children]
            .filter(child => child.getClientRects().length && getComputedStyle(child).display !== 'none'
              && !child.matches('.lf-thread-reply'))
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
    its end where it does not, and leaves the user on the view."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Where should this explanation go?")
    page = open_page(browser, url)
    resized(page, 800, 520)
    view = open_panel_thread(page, root)
    box = panel_field(page)
    write(box, "First point. " * 5 + "\n\nSecond point. " * 4)
    box.press("Enter")
    round_trip(page)
    message = view.locator(".lf-msg[data-lf-author=user]").last
    expect(message).to_contain_text("Second point.")
    page.wait_for_function(
        """([view, message]) => {
          const band = view.getBoundingClientRect();
          const box = message.getBoundingClientRect();
          return box.top >= band.top - 1 && box.bottom <= band.bottom + 1;
        }""",
        arg=[view.element_handle(), message.element_handle()],
    )
    expect(view).to_be_focused()

    write(box, "Long reply. " * 90)
    box.press("Enter")
    round_trip(page)
    long_message = view.locator(".lf-msg[data-lf-author=user]").last
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
    expect(view).to_be_focused()


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
    first = page.locator(f'{PANEL_THREAD}[data-lf-thread="{c1}"]')
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
    expect(
        page.locator(".lf-fp-thread-controls :is(.lf-resolve, .lf-reopen)")
    ).to_have_accessible_name("Reopen")
    with sending(page, "the reopen"):
        page.keyboard.press("r")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "unresolve"
    expect(
        page.locator(".lf-fp-thread-controls :is(.lf-resolve, .lf-reopen)")
    ).to_have_accessible_name("Resolve thread")


def test_r_resolves_a_thread_from_wherever_the_user_stands_in_it(browser, serve):
    """r settles the thread holding focus, not only a focused card.

    A click on a thread's words focuses the message, so a card-only reach would leave
    the user's most common way in pressing a letter that did nothing. The Resolve button,
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

    # A pointer on the reply's words stands the user on the thread drawing them, not
    # the view.
    message = view.locator(".lf-page-thread", has_text="Reply 0")
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
    page.locator(".lf-fp-thread-controls :is(.lf-resolve, .lf-reopen)").focus()
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
        f":is(.lf-page-thread:not([data-lf-kind], .lf-fp-view *), .lf-fp-view)"
        f'[data-lf-thread="{name}"]'
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
    # A reload is a return: the thread opens again where the browser restored the page,
    # with the user in it.
    expect(thread).to_be_focused()
    assert page.evaluate("history.length") == entries
    if name == "anchor01":
        # Leaving the passage puts its card away, renaming the entry, so Back returns
        # to the link the user left by with no thread open, as they left it.
        link = page.get_by_role("link", name="Back to the heading")
        link.click()
        expect(page.locator("#start")).to_be_in_viewport()
        expect(thread).not_to_be_visible()
        page.go_back()
        expect(link).to_be_focused()
        expect(thread).not_to_be_visible()
        assert "thread" not in dict(parse_qsl(urlsplit(page.url).query))
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


def test_t_after_a_reload_goes_on_from_the_thread_it_reopened(browser, serve):
    """A reload opens the card its entry names again, with the user in it and the page
    where the browser restored it, so the first `t` after it goes on to the next
    thread, a Back step, rather than landing on the card already open."""
    url = serve(LONG_PAGE, anchored=[("p3", "Paragraph 3."), ("p41", "Paragraph 41.")])
    page = open_page(browser, url)
    card = page.locator(".lf-margin-preview .lf-page-thread")
    page.keyboard.press("t")
    expect(card).to_be_focused()
    first = card.get_attribute("data-lf-thread") or ""
    page.keyboard.press("t")
    expect(card).not_to_have_attribute("data-lf-thread", first)
    second = card.get_attribute("data-lf-thread") or ""
    # The reload restores the offset the walk's landing reached, not one mid-glide.
    scroll_settled(page)
    read_to = page.evaluate("scrollY")
    page.reload()
    wait_until_ready(page)
    expect(card).to_have_attribute("data-lf-thread", second)
    expect(card).to_be_focused()
    assert page.evaluate("scrollY") == pytest.approx(read_to, abs=2)
    entries = page.evaluate("history.length")
    page.keyboard.press("t")
    expect(card).to_have_attribute("data-lf-thread", first)
    expect(card).to_be_focused()
    page.wait_for_function("navigation.transition === null")
    assert page.evaluate("history.length") == entries + 1


def test_back_to_a_hidden_fragment_opens_the_thread_its_entry_names(browser, serve):
    """Back to an entry naming a thread and a fragment the page has hidden since reveals
    the fragment, which puts away the panel's view standing over it, and opens the
    thread the entry names again after, as the page then stands."""
    filler = "".join(f"<p>Reading context {n}.</p>" for n in range(40))
    url = serve(
        leaf_page(
            "Hidden fragment",
            '<h1 id="top">Hidden fragment</h1><p id="middle">The middle.</p>'
            f'{filler}<details id="more" open><summary>More</summary>'
            '<p id="foot">The foot.</p></details>',
        )
    )
    root = panel_comment(serve.page_dir, "About the whole page.")
    for n in range(3):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "parent": root,
                "revision": 1,
                "text": f"Reply {n}. " + "More of the explanation. " * 12,
            },
        )
    page = open_page(browser, thread_url(url, root, "foot"))
    thread = page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')
    expect(thread).to_be_visible()
    # To another entry with the thread still open, by no press that would put it away.
    page.evaluate("location.hash = 'middle'")
    expect(page.locator("#middle")).to_be_focused()
    expect(thread).to_be_visible()
    page.evaluate("document.getElementById('more').open = false")
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    expect(page.locator("#foot")).to_be_visible()
    expect(thread).to_be_visible()
    page.wait_for_function("navigation.transition === null")
    query = dict(parse_qsl(urlsplit(page.url).query))
    assert query.get("thread") == root
    assert urlsplit(page.url).fragment == "foot"


@pytest.mark.parametrize(
    "anchor",
    [None, {"section": "gone", "quote": "Words a revision removed."}],
    ids=["about the page", "passage removed"],
)
def test_a_threads_row_and_resolve_s_move_on_are_back_steps(browser, serve, anchor):
    """A press on a row of Threads lands the user in a thread they weren't in, a Back
    step as every other route's is, and so does Resolve moving them on from it to the
    next thread; Back returns to the thread they resolved. A thread with no passage on
    the page opens in the panel with nothing to land beside it, about the whole page or
    about words a revision removed, and its view alone makes the step."""
    url = serve(LONG_PAGE)
    threads = [
        panel_comment(serve.page_dir, "First question?", anchor),
        panel_comment(serve.page_dir, "Second question?", anchor),
    ]
    page = open_page(browser, url)
    open_threads(page)
    view = page.locator(PANEL_THREAD)
    rows = page.locator(".lf-fp-thread")
    expect(rows).to_have_count(2)
    page.wait_for_function("navigation.transition === null")
    entries = page.evaluate("history.length")
    rows.first.click()
    expect(view).to_be_visible()
    opened = view.get_attribute("data-lf-thread")
    assert opened in threads
    page.wait_for_function("navigation.transition === null")
    assert page.evaluate("history.length") == entries + 1
    with sending(page, "the resolve that moves on"):
        page.locator(".lf-fp-thread-controls .lf-resolve").click()
    expect(view).not_to_have_attribute("data-lf-thread", opened or "")
    page.wait_for_function("navigation.transition === null")
    assert page.evaluate("history.length") == entries + 2
    page.go_back()
    expect(view).to_have_attribute("data-lf-thread", opened or "")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_back_from_a_thread_opened_from_threads_returns_to_its_row(
    request, serve, engine
):
    """Back from a thread a press on a row of Threads opened in the panel, as one about a
    passage opens for a user who chose the panel for threads, returns to Threads, on
    that row, as the view's own way back does, rather than closing the panel; Forward
    opens the thread again. The entry keeps the list and its row across a reload of the
    document, which forgets the panel's views, so the thread the reload opens again
    still gives way to Threads on Back, and after Escape put the thread away, when Back
    has no thread to put away."""
    url = serve(LONG_PAGE)
    for n, text in enumerate(("First question?", "Second question?", "Third?"), 1):
        panel_comment(
            serve.page_dir, text, {"section": f"p{n}", "quote": f"Paragraph {n}."}
        )
    page = open_page(request.getfixturevalue(engine), url)
    choose_threads_in_panel(page)
    open_threads(page)
    rows = page.locator(".lf-fp-thread")
    expect(rows).to_have_count(3)
    pressed = rows.nth(1)
    key = pressed.get_attribute("data-lf-key")
    pressed.click()
    opened = page.locator(PANEL_THREAD).get_attribute("data-lf-thread") or ""
    thread = linked_thread(page, opened)
    expect(thread).to_be_visible()
    page.wait_for_function("navigation.transition === null")

    row = page.locator(f'.lf-fp-thread[data-lf-key="{key}"]')
    for reload in (True, False):
        if reload:
            page.reload()
            wait_until_ready(page)
            expect(thread).to_be_visible()
        page.go_back()
        expect(page.locator(panel_view("threads"))).to_be_visible()
        expect(row).to_be_focused()
        expect(thread).to_be_hidden()
        page.wait_for_function("navigation.transition === null")
        page.go_forward()
        expect(thread).to_be_visible()
        page.wait_for_function("navigation.transition === null")

    # Escape puts the thread away where the user stands, so Back has no thread to put
    # away, and the entry's own record names the row.
    page.keyboard.press("Escape")
    if thread.is_visible():
        page.keyboard.press("Escape")
    expect(thread).to_be_hidden()
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    expect(page.locator(panel_view("threads"))).to_be_visible()
    expect(row).to_be_focused()


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
    # Forward into the document is a return, so the thread opens in place.
    expect(linked_thread(page, "general1")).to_be_focused()
    assert page.evaluate("history.length") == entries + 1


def test_a_thread_url_with_a_fragment_lands_there_with_the_thread_open(browser, serve):
    """The fragment places the page, and the thread the URL names opens beside it
    without moving it, so a reload of an entry that showed both shows both again."""
    page = open_page(browser, thread_url(thread_page(serve), "general1", "target"))
    expect(linked_thread(page, "general1")).to_be_visible()
    expect(page.locator("#target")).to_be_in_viewport()


def test_a_message_s_copied_link_opens_its_thread_on_that_message(browser, serve):
    """A message's Copy link copies the page's address naming that message, without
    the fragment the address held, and the link opens the thread on the message; `y`
    on the thread's Resolve, which the panel draws apart from its messages, copies the
    thread's own link."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Where does this end?")
    reply = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root,
            "revision": 1,
            "text": "At the last paragraph.",
        },
    )["id"]
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = open_page(browser, thread_url(url, root, "p59"), context=context)
    thread = page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')
    message = thread.locator(f'.lf-msg[data-lf-event="{reply}"]')
    message.hover()
    message.locator(".lf-msg-link").click()
    expect(message.locator(".lf-msg-link")).to_have_js_property("status", "success")
    copied = page.evaluate("navigator.clipboard.readText()")
    # The address as the page holds it, naming the reply in place of the thread.
    link, here = urlsplit(copied), urlsplit(page.url)
    assert here.fragment == "p59"
    assert (link.path, dict(parse_qsl(link.query)), link.fragment) == (
        here.path,
        {**dict(parse_qsl(here.query)), "thread": reply},
        "",
    )
    page.locator(".lf-fp-thread-controls .lf-resolve").focus()
    page.keyboard.press("y")
    page.wait_for_function(
        "copied => navigator.clipboard.readText().then((now) => now !== copied)",
        arg=copied,
    )
    assert page.evaluate("navigator.clipboard.readText()") == copied.replace(
        reply, root
    )

    followed = open_page(browser, copied, context=context)
    expect(
        followed.locator(f'{PANEL_THREAD} .lf-msg[data-lf-event="{reply}"]')
    ).to_be_focused()


def test_a_finger_copies_a_reply_s_link(browser, serve):
    """Under a finger, where the address names only the thread, a reply offers its Copy
    link, though not its Copy, whose words a finger selects instead. The opening
    message offers neither, its link being the thread's, which the address names."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Where does this end?")
    reply = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root,
            "revision": 1,
            "text": "At the last paragraph.",
        },
    )["id"]
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        has_touch=True,
        is_mobile=True,
        permissions=["clipboard-read", "clipboard-write"],
    )
    page = open_page(browser, thread_url(url, root), context=context)
    message = page.locator(f'{PANEL_THREAD} .lf-msg[data-lf-event="{reply}"]')
    expect(message.locator(".lf-msg-copy")).to_be_hidden()
    opening = page.locator(f'{PANEL_THREAD} .lf-msg[data-lf-event="{root}"]')
    expect(opening.locator(".lf-msg-link")).to_be_hidden()
    message.locator(".lf-msg-link").tap()
    expect(message.locator(".lf-msg-link")).to_have_js_property("status", "success")
    copied = urlsplit(page.evaluate("navigator.clipboard.readText()"))
    assert dict(parse_qsl(copied.query))["thread"] == reply


def test_a_link_to_a_folded_message_opens_its_fold(browser, serve):
    """A link naming a message a summary folds opens the fold and lands on it."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Where does this end?")
    said = [
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Claude",
                "parent": root,
                "revision": 1,
                "text": f"Step {n}.",
            },
        )["id"]
        for n in range(3)
    ]
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "summary",
            "author": "agent",
            "agent": "Claude",
            "thread": root,
            "from": said[0],
            "through": said[1],
            "text": "The first two steps.",
        },
    )
    page = open_page(browser, thread_url(url, said[0]))
    expect(
        page.locator(f'{PANEL_THREAD} .lf-msg[data-lf-event="{said[0]}"]')
    ).to_be_focused()


@pytest.mark.parametrize(
    "named",
    [
        {"author": "user", "emoji": "👍"},
        {"author": "agent", "agent": "Claude", "text": "Reading.", "ephemeral": True},
    ],
    ids=["reaction", "progress"],
)
def test_a_link_naming_a_message_drawn_without_a_row_opens_its_thread(
    browser, serve, named
):
    """A link naming a reaction, a chip on the message it answers, or a step of the
    agent's work, which the thread draws as a face, opens the thread as its own link
    does."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Where does this end?", author="agent")
    event = append_carried_log_record(
        serve.page_dir, {"kind": "reply", "parent": root, "revision": 1, **named}
    )["id"]
    page = open_page(browser, thread_url(url, event))
    expect(page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')).to_be_focused()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_back_and_forward_show_the_thread_each_entry_names(request, serve, engine):
    """An entry's `?thread=` names the thread view standing open on it, renamed as views
    open and close where the user stands. A link followed out of a thread a URL opened
    puts the view away and leaves an entry naming no thread; Back returns to the
    thread, with the user on the link they left by and the page where it was, and
    Forward to the link's target with the view put away again. Escape puts the view
    away by renaming the entry, never by a traversal."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Where does this end?")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root,
            "revision": 1,
            "text": "See [the last paragraph](#p59).",
        },
    )
    page = open_page(request.getfixturevalue(engine), thread_url(url, root))
    # The last paragraph ends a page with no room below it, so the view stands over it.
    without_end_room(page)
    thread = page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')
    expect(thread).to_be_focused()

    def query():
        return dict(parse_qsl(urlsplit(page.url).query))

    start = page.evaluate("navigation.currentEntry.index")
    link = thread.get_by_role("link", name="the last paragraph")
    link.click()
    expect(page.locator("#p59")).to_be_focused()
    expect(thread).to_be_hidden()
    page.wait_for_url(lambda now: "thread" not in dict(parse_qsl(urlsplit(now).query)))
    entries = page.evaluate("navigation.entries().length")

    page.go_back()
    expect(link).to_be_focused()
    assert query()["thread"] == root
    page.wait_for_function("scrollY === 0")
    page.go_forward()
    expect(thread).to_be_hidden()
    expect(page.locator("#p59")).to_be_in_viewport()
    assert "thread" not in query()
    expect(page.locator("#p59")).to_be_focused()

    page.go_back()
    expect(link).to_be_focused()
    page.keyboard.press("Escape")
    expect(thread).to_be_hidden()
    page.wait_for_url(lambda now: "thread" not in dict(parse_qsl(urlsplit(now).query)))
    assert page.evaluate("navigation.entries().length") == entries
    assert page.evaluate("navigation.currentEntry.index") == start


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
    expect(page.locator('.lf-page-thread[data-lf-thread="general1"]')).to_have_count(0)


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
    expect(
        linked_thread(page, "anchor01").locator('.lf-msg[data-lf-event="answer01"]')
    ).to_be_focused()
    expect(page.locator("#target")).to_be_in_viewport()
    assert page.evaluate("history.length") == 2
    # The tab set names the view it opened beside the thread, and the entry keeps both:
    # the thread by the reply the link named, or by its own id where the tab set's
    # rename came before the thread stood open and the entry was named again after.
    assert urlsplit(page.url).fragment == "second"
    assert dict(parse_qsl(urlsplit(page.url).query))["thread"] in (
        "answer01",
        "anchor01",
    )
    page.reload()
    wait_until_ready(page)
    expect(linked_thread(page, "anchor01")).to_be_visible()
    # A press on the other tab puts the card away, so the entry it leaves names no
    # thread, and Back returns to the tab with the card put away.
    page.get_by_role("tab", name="First", exact=True).click()
    expect(page.locator("#first")).to_be_visible()
    assert urlsplit(page.url).fragment == "first"
    page.go_back()
    wait_until_ready(page)
    expect(page.locator("#target")).to_be_visible()
    expect(linked_thread(page, "anchor01")).to_be_hidden()
    assert urlsplit(page.url).fragment == "second"
    assert "thread" not in dict(parse_qsl(urlsplit(page.url).query))
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
