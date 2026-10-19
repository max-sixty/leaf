"""Moving to and between threads by keyboard and pointer: the current thread's mark, the
walks and addresses that reach a thread, where a press lands the list, and leaving or
re-entering a reply."""

import io
import re

import pytest
from interact_support import append_carried_log_record
from leaf import event_log as events_model
from leaf.render_checks import rendered
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import (
    HOLD_MOTION,
    PANEL_PAGE,
    THREAD_DIFF_PAGE,
    live_url,
    panel_comment,
)
from render_cases_layout import (
    COVERED_TOP,
    in_threads_scrollport,
    page_at_rest,
    ring_faults,
    ring_rule,
    rings_drawn,
    token_colour,
)
from render_harness import (
    LONG_PAGE,
    leaf_page,
    open_page,
    panel_settled,
    resized,
    round_trip,
    scroll_settled,
    sending,
    shortcut_bar_text,
    take_browser_errors,
    told,
    write,
)

from browser.threads import (
    IN_LANDING_BAND,
    LANDING_WORDS,
    OPEN_TITLE,
    clear_of_the_bar,
    focus_panel_thread,
    open_threads_list,
    reply_by_keyboard,
    seed_panel_threads,
    standing_thread,
    thread_mark_fault,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_opening_a_thread_leaves_its_title_where_the_user_pressed_it(browser, serve):
    """The list's named disclosure closes the card that was open, and when that card is
    above the one being opened every title below it comes up by its whole open height.
    The user pressed a title, so the title is what must stay put: let it travel and the
    thread they just opened is somewhere else, and from the first visible row it leaves
    the scrollport entirely — the panel answers a press with the middle of a message and
    no title over it. Native anchoring holds whichever node it picked, which is the
    pressed card only when it happened to pick it, so the list holds the card itself.

    Press with a real pointer: the hold reads the card under it, and that is the route
    the geometry breaks on."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    above, target = roots[10:12]
    page.locator(f'.lf-thread[data-id="{above}"] > .lf-thread-summary').click()
    rendered(page)
    page.locator(f'.lf-thread[data-id="{target}"]').evaluate(
        "el => el.scrollIntoView({behavior: 'instant', block: 'center'})"
    )
    rendered(page)
    scroll = page.locator(".lf-threads").evaluate(
        "el => ({at: el.scrollTop, max: el.scrollHeight - el.clientHeight})"
    )
    assert 0 < scroll["at"] < scroll["max"], (
        f"the pressed title is at a scroll limit, so the list has no room to hold it "
        f"and the reading below would be about the limit instead: {scroll}"
    )

    title = page.locator(f'.lf-thread[data-id="{target}"] > .lf-thread-summary')
    before = title.evaluate("el => el.getBoundingClientRect().top")
    # The room has to close above the title, or nothing below it moves and this reading
    # would pass on a list that never held anything.
    above_box = page.locator(f'.lf-thread[data-id="{above}"]').evaluate(
        "el => el.getBoundingClientRect().toJSON()"
    )
    assert above_box["bottom"] <= before, (
        f"the open card is not above the title being pressed, so closing it takes no "
        f"room out from under it: {above_box} against {before:.1f}px"
    )
    opened = above_box["height"]
    box = title.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    expect(page.locator(f'.lf-thread[data-id="{target}"][open]')).to_have_count(1)
    rendered(page)

    closed = page.locator(f'.lf-thread[data-id="{above}"]').evaluate(
        "el => el.getBoundingClientRect().height"
    )
    assert opened - closed > 100, (
        f"the card above gave back {opened - closed:.0f}px, which is too little room "
        f"for this reading to say anything about holding the title still"
    )
    after = title.evaluate("el => el.getBoundingClientRect().top")
    # A few pixels are the browser's own: pressing a title focuses it, and a focus at
    # the list's edge is revealed by the list's scroll-padding.
    assert after == pytest.approx(before, abs=8), (
        f"opening the thread carried its title from {before:.1f}px to {after:.1f}px, "
        f"{opened - closed:.0f}px of room having closed above it"
    )
    in_threads_scrollport(page, f'.lf-thread[data-id="{target}"] > .lf-thread-summary')


def test_back_returns_from_a_thread_the_walk_travelled_to(browser, serve):
    """A journey of trips to threads somewhere else leaves one history entry however
    far it goes, so Back returns to the place the user was reading before it and
    Forward to where it ended. Reading somewhere else ends the journey: the next trip
    records that place."""
    filler = "".join(f"<p>Filler paragraph {n}.</p>" for n in range(60))
    url = serve(
        leaf_page(
            "Back from a thread",
            "<h1>Back from a thread</h1>"
            "<section id=near><p>The first question sits at the top.</p></section>"
            f"<section id=above>{filler}</section>"
            "<section id=also><p>A second question sits halfway down.</p></section>"
            f"<section id=below>{filler}</section>",
        )
    )
    for section in ("near", "also"):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "anchor": {"section": section},
                "text": f"A question about {section}.",
            },
        )
    page = open_page(browser, url)
    page.evaluate("document.scrollingElement.scrollTo({top: 1e6, behavior: 'instant'})")
    reading = page.evaluate("document.scrollingElement.scrollTop")
    assert reading > 2000
    entries = page.evaluate("history.length")

    page.keyboard.press("Shift+t")
    page.wait_for_function("() => document.activeElement?.closest('[data-thread]')")
    scroll_settled(page)
    landed = page.evaluate("document.scrollingElement.scrollTop")
    assert landed < reading - 1000
    assert page.evaluate("history.length") == entries + 1

    first = page.evaluate(
        "document.activeElement.closest('[data-thread]').dataset.thread"
    )
    page.keyboard.press("Shift+t")
    page.wait_for_function(
        "first => document.activeElement?.closest('[data-thread]')?.dataset.thread"
        " !== first",
        arg=first,
    )
    scroll_settled(page)
    walked = page.evaluate("document.scrollingElement.scrollTop")
    assert walked < landed - 1000
    assert page.evaluate("history.length") == entries + 1

    page.go_back()
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2", arg=reading
    )
    page.go_forward()
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2",
        arg=walked,
    )

    page.evaluate("document.scrollingElement.scrollTo({top: 1e6, behavior: 'instant'})")
    elsewhere = page.evaluate("document.scrollingElement.scrollTop")
    assert elsewhere > walked + 1000
    # Either thread is somewhere else from here; which one Shift+t lands on depends
    # on whether the walk's card survived the traversal, and the claim does not.
    page.keyboard.press("Shift+t")
    page.wait_for_function(
        "top => document.scrollingElement.scrollTop < top - 1000", arg=elsewhere
    )
    scroll_settled(page)
    assert page.evaluate("history.length") == entries + 2
    page.go_back()
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2",
        arg=elsewhere,
    )


def test_the_arrows_and_t_walk_one_list_of_threads(browser, serve):
    """The arrows, `t` and the position they report count the same threads: every card
    the user can step onto, one kept in the list as news from elsewhere included, and
    not a card folding out, which is room about to go. Counted by the arrows alone, a
    fold made `Home` say "1 of 4" where `t` walked three threads, and the arrows'
    position left out the "shown" a narrowed list's `t` says."""
    page = open_page(browser, serve(LONG_PAGE, comments=4), init_script=HOLD_MOTION)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    kept, folding, third, fourth = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    card = lambda id: page.locator(f'.lf-threads > [data-id="{id}"]')
    card(kept).locator(".lf-thread-summary").click()
    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": kept},
    )
    told(page)
    expect(card(kept).locator(".lf-thread-news")).to_be_visible()
    card(folding).locator(".lf-thread-summary").click()
    card(folding).locator(".lf-resolve").click()
    round_trip(page)
    assert page.evaluate("() => window.__lfHeld.length") == 1
    expect(card(kept)).to_be_visible()

    position = page.locator(".lf-walk-position")
    for key, at, label in [
        ("Home", kept, "Thread 1 of 3"),
        ("t", third, "Thread 2 of 3"),
        ("t", fourth, "Thread 3 of 3"),
        ("ArrowUp", third, "Thread 2 of 3"),
        ("ArrowUp", kept, "Thread 1 of 3"),
        ("End", fourth, "Thread 3 of 3"),
        ("Shift+T", third, "Thread 2 of 3"),
    ]:
        page.keyboard.press(key)
        expect(card(at).locator(":scope > .lf-thread-summary")).to_be_focused()
        expect(position).to_have_text(label)

    # A narrowed list says so in both walks' positions, `n`/`N` walking a search.
    page.get_by_role("searchbox", name="Find in threads").fill("Comment")
    page.keyboard.press("Enter")
    expect(card(third).locator(":scope > .lf-thread-summary")).to_be_focused()
    expect(position).to_have_text("Thread 1 of 2 shown")
    for key, at, label in [
        ("ArrowDown", fourth, "Thread 2 of 2 shown"),
        ("Shift+N", third, "Thread 1 of 2 shown"),
        ("End", fourth, "Thread 2 of 2 shown"),
    ]:
        page.keyboard.press(key)
        expect(card(at).locator(":scope > .lf-thread-summary")).to_be_focused()
        expect(position).to_have_text(label)


def test_an_empty_thread_list_wears_its_ring_whole(browser, serve):
    """The list holds focus itself only while it shows no thread (a list showing one
    hands focus to that thread's title). It then wears the inset ring on its frame,
    whole along both edges, down to the panel's floor, over the list's own ground."""
    # Whether the ring stands whole is geometry, the same in either scheme.
    color_scheme = "light"
    url = serve(PANEL_PAGE)
    context = browser.new_context(
        viewport={"width": 459, "height": 856},
        color_scheme=color_scheme,
        reduced_motion="reduce",
    )
    page = open_page(browser, url, context=context)
    page.evaluate("() => document.activeElement?.blur()")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)

    threads = page.locator(".lf-threads")
    expect(page.locator(".lf-threads > .lf-empty")).to_be_visible()
    expect(threads).to_be_focused()
    paint = threads.evaluate(
        """el => {
              const list = getComputedStyle(el);
              const frame = el.parentElement;
              const current = getComputedStyle(frame, '::after');
              const listBox = el.getBoundingClientRect();
              const ringBox = frame.getBoundingClientRect();
              const panel = frame.closest('.lf-thread-panel');
              const floor = panel.getBoundingClientRect().bottom
                - parseFloat(getComputedStyle(panel).borderBottomWidth);
              return {
                listOutline: list.outlineStyle,
                outline: current.outlineStyle,
                width: current.outlineWidth,
                offset: current.outlineOffset,
                ground: [list.backgroundColor, list.backgroundImage],
                sameBox: ['left', 'top', 'right', 'bottom'].every(
                  edge => ringBox[edge] === listBox[edge]
                ),
                reachesFloor: ringBox.bottom === floor,
              };
            }"""
    )
    assert paint["listOutline"] == "none"
    assert paint["outline"] == "solid"
    assert paint["width"] == "2px"
    assert paint["offset"] == "-2px"
    assert ".lf-threads-frame" in ring_rule(
        page.locator(".lf-threads-frame"), pseudo="after"
    )
    assert paint["sameBox"]
    assert paint["reachesFloor"], (
        "the focused list ended above the panel's floor and left an ownerless strip "
        "under its contour"
    )

    # The first and last device row inside the list's own box. An element clip is
    # taken from a rect that need not land on device pixels — the list's top is
    # 247.67 at this width — so its outermost row is the panel's paint, not the ring.
    edges = threads.evaluate(
        """el => { const b = el.getBoundingClientRect();
              return [Math.ceil(b.left), Math.floor(b.right),
                      Math.ceil(b.top), Math.floor(b.bottom) - 1]; }"""
    )
    shot = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
    accent = tuple(int(n) for n in re.findall(r"\d+", token_colour(page, "--accent")))
    left, right, first, last = edges
    for y in (first, last):
        assert {shot.getpixel((x, y)) for x in range(left, right)} == {accent}, (
            f"the ring is broken across row {y}"
        )

    # Focus is the only difference: the find box takes it, the ring goes, and the
    # ground under it is the one the focused list stood on.
    page.keyboard.press("/")
    expect(page.get_by_role("searchbox", name="Find in threads")).to_be_focused()
    assert (
        threads.evaluate(
            "el => getComputedStyle(el.parentElement, '::after').outlineStyle"
        )
        == "none"
    )
    assert paint["ground"] == threads.evaluate(
        "el => [getComputedStyle(el).backgroundColor, "
        "getComputedStyle(el).backgroundImage]"
    )


def test_forced_colors_keep_current_thread_regions_distinct(browser, serve):
    """High contrast keeps the current region visible from a keyboard arrival, a
    pointer arrival, and the reply box."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    panel_comment(d, "The current card.", {"section": "lede"})
    panel_comment(d, "Its resting peer.", {"section": "how-store"})
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, forced_colors="active"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.evaluate("() => document.activeElement?.blur()")
    # The named address toggles the panel it names, so from a panel opened by its
    # visible control the first completion closes it and the second is the arrival.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, open=False)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)
    current = page.locator(".lf-thread").filter(has_text="The current card.")
    peer = page.locator(".lf-thread").filter(has_text="Its resting peer.")
    title = current.locator(":scope > .lf-thread-summary")
    expect(title).to_be_focused()
    assert title.evaluate("el => el.matches(':focus-visible')")
    assert title.evaluate("el => getComputedStyle(el).outlineStyle") != "none"
    assert current.evaluate("el => getComputedStyle(el).borderColor") != peer.evaluate(
        "el => getComputedStyle(el).borderColor"
    )
    page.evaluate("() => document.activeElement?.blur()")
    box = current.bounding_box()
    assert box
    page.mouse.click(box["x"] + 6, box["y"] + 6)
    expect(current.locator(".lf-thread-summary")).to_be_focused()
    assert current.evaluate("el => el.matches(':focus-within')")
    assert not current.evaluate("el => el.matches(':focus-visible')")
    assert current.evaluate("el => getComputedStyle(el).borderColor") != peer.evaluate(
        "el => getComputedStyle(el).borderColor"
    )
    reply = current.locator("leaf-text")
    reply.click()
    expect(reply).to_be_focused()
    assert current.evaluate("el => getComputedStyle(el).borderColor") != peer.evaluate(
        "el => getComputedStyle(el).borderColor"
    )


def test_go_page_returns_without_unwinding_the_panel(browser, serve):
    """Leaving a panel beside the document to compare a comment is not backing out:
    the panel and its narrowing stay exactly as the user left them, while focus goes
    to the page. The address starts from the found comment after Enter leaves the find
    box, whose ordinary Escape still owns one rung of the panel stack."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    panel_comment(d, "The capacity needs another look.", {"section": "how-cap"})
    panel_comment(d, "The storage rule is settled.", {"section": "how-store"})

    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    find = page.get_by_role("searchbox", name="Find in threads")
    find.focus()
    page.keyboard.type("capacity")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)
    page.keyboard.press("Enter")
    expect(
        page.locator(".lf-threads > .lf-thread:not([hidden]) > .lf-thread-summary")
    ).to_be_focused()

    page.keyboard.press("g")
    page.keyboard.press("p")
    assert page.evaluate("() => document.activeElement === document.body"), (
        "g p left the user in the panel"
    )
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    expect(find).to_have_value("capacity")
    expect(page.locator(".lf-threads > .lf-thread:not([hidden])")).to_have_count(1)


def test_go_page_is_inert_while_the_panel_covers_the_page(browser, serve):
    """A covering panel locks the page scroller, so focus cannot honestly return to
    that page while keeping the panel open. Escape closes the panel instead."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    panel_comment(d, "The capacity needs another look.", {"section": "how-cap"})

    context = browser.new_context(viewport={"width": 400, "height": 900})
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread:not([hidden])")
    focus_panel_thread(thread)

    page.keyboard.press("g")
    page.keyboard.press("p")
    expect(thread.locator(":scope > .lf-thread-summary")).to_be_focused()
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()


def test_the_address_sequence_places_a_focused_comment_at_either_list_edge(
    browser, serve
):
    """A focused thread is one addressable place with two useful placements. `g k`
    and `g j` move that card inside the panel without moving focus or the document,
    and the list's own scroll padding keeps the landing clear of its focus ring."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(32):
        panel_comment(d, f"Comment {i} about storage.", {"section": "how-store"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    box = page.locator(".lf-threads")
    target = page.locator(".lf-threads > .lf-thread:not([hidden])").nth(16)
    assert box.evaluate("el => el.scrollHeight > el.clientHeight"), (
        "the list does not scroll, so its edges are not distinct places"
    )
    focus_panel_thread(target)

    before_page = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press("g")
    expect(
        page.locator(
            ".lf-shortcut-bar .lf-shortcut:not([data-lf-off-line])",
            has_text="thread top / bottom",
        )
    ).to_have_count(1)
    page.keyboard.press("k")
    top = page.evaluate(
        """() => {
              const box = document.querySelector('.lf-threads');
              const thread = document.activeElement.closest('.lf-thread');
              const view = box.getBoundingClientRect();
              const card = thread.getBoundingClientRect();
              const clear = parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
              return {gap: card.top - view.top, clear};
            }"""
    )
    assert abs(top["gap"] - top["clear"]) < 2, (
        f"g k left the card {top['gap']:.1f}px from the list top; "
        f"the landable edge is {top['clear']:.1f}px"
    )
    expect(target.locator(":scope > .lf-thread-summary")).to_be_focused()

    page.keyboard.press("g")
    page.keyboard.press("j")
    bottom = page.evaluate(
        """() => {
              const box = document.querySelector('.lf-threads');
              const thread = document.activeElement.closest('.lf-thread');
              const view = box.getBoundingClientRect();
              const card = thread.getBoundingClientRect();
              const clear = parseFloat(getComputedStyle(box).scrollPaddingBottom) || 0;
              return {gap: view.bottom - card.bottom, clear};
            }"""
    )
    assert abs(bottom["gap"] - bottom["clear"]) < 2, (
        f"g j left the card {bottom['gap']:.1f}px from the list bottom; "
        f"the landable edge is {bottom['clear']:.1f}px"
    )
    expect(target.locator(":scope > .lf-thread-summary")).to_be_focused()
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before_page


# What the burial below is aiming at: how far the first card stands past the list's top
# edge, the edge that depth has to match, and the box the press is aimed into.
# `COVERED_TOP` answers the covered question afterwards, about the focused card.
UNDER_EDGE = """() => {
  const list = document.querySelector('.lf-threads');
  const card = list.querySelector('.lf-thread');
  const top = list.getBoundingClientRect().top + list.clientTop;
  return {
    covered: top - card.getBoundingClientRect().top,
    edge: parseFloat(getComputedStyle(card).borderTopWidth),
    box: card.getBoundingClientRect().toJSON(),
  };
}"""


# Scroll by hand until the list's top edge cuts the card by `want`. Bounded, so a list
# that never scrolls its first card away fails the precondition rather than spinning.
BURY = """(want) => {
  const list = document.querySelector('.lf-threads');
  const card = list.querySelector('.lf-thread');
  const covered = () => list.getBoundingClientRect().top + list.clientTop
    - card.getBoundingClientRect().top;
  for (let i = 0; i < 400 && covered() < want; i++) list.scrollTop += 1;
}"""


def test_a_comment_the_pointer_lands_on_comes_back_from_the_lists_edge(browser, serve):
    """The walk above never sees this, and that is the point of having it twice: t/T
    scroll their landing into the band the list declares unlandable. A click scrolls
    nothing. The user nudges the list, its top edge cuts the first card, and takes the
    first strip of the surface that distinguishes the current card.

    So the gesture here is a real press rather than a locator click, which would scroll
    the card into view for its own actionability check and quietly perform the fix it is
    meant to test. What is asserted is the same question the walk asks — where the
    control can be seen, so can the current paint that names it — and, beside it, that
    the card actually came out, since paint reported whole while the card is still
    buried would mean the reading rather than the landing had moved."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(8):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-summary").first.click()
    page.locator(".lf-threads").focus()

    # Bury the card by exactly its reserved edge, which is the user's own case: a
    # list nudged a dozen pixels cuts its first card at the top edge. The
    # depth is one pixel rather than a comfortable number on purpose: it leaves the
    # rest of the card visible while hiding the first strip of its current ground.
    page.evaluate(BURY, page.evaluate(UNDER_EDGE)["edge"])
    rendered(page)
    buried = page.evaluate(UNDER_EDGE)
    assert buried["edge"] <= buried["covered"] <= buried["edge"] + 1, (
        f"the list's edge cuts {buried['covered']}px of the first card and its "
        f"edge is {buried['edge']}px: the setup wanted the edge buried and the rest "
        "of the card showing, and this is neither"
    )

    # Just inside the card's own corner. Its middle is prose today and one layout
    # away from being the reply box or a button, and a press that lands on a control
    # inside the card would fail this for a reason that is not its subject.
    box = buried["box"]
    page.mouse.click(box["x"] + 6, box["y"] + 80)
    rendered(page)
    assert page.evaluate(
        "() => Boolean(document.activeElement?.closest('.lf-thread'))"
    ), "the press did not land the user on a thread"
    mark_fault = thread_mark_fault(standing_thread(page))
    assert not mark_fault, mark_fault
    assert not ring_faults(
        rings_drawn(page), "after a press on a card the list's edge cut"
    )
    # The panel's own reading of the same question, and the stronger form of it: a
    # hit test at the card's top edge rather than two rectangles subtracted, and it
    # declines outright if the press left the list.
    assert page.evaluate(COVERED_TOP) is None, (
        f"after the press the card is still past the list's top edge: "
        f"{page.evaluate(COVERED_TOP)}"
    )

    # The reply box receives the compact ring and the parent keeps its quiet current
    # ground. Reached by key this was never wrong, because landIn already lands the
    # thread around the box; a press into it went the way every other press did.
    page.evaluate(BURY, buried["edge"])
    rendered(page)
    under = page.evaluate(UNDER_EDGE)
    assert under["covered"] >= under["edge"], (
        f"the setup put the card back only {under['covered']}px under, which its "
        f"{under['edge']}px edge shows through"
    )
    reply = page.locator(".lf-threads > .lf-thread leaf-text").first
    reply_box = reply.bounding_box()
    page.mouse.click(
        reply_box["x"] + reply_box["width"] / 2,
        reply_box["y"] + reply_box["height"] / 2,
    )
    rendered(page)
    expect(reply).to_be_focused()
    assert page.evaluate(COVERED_TOP) is None, (
        "a press into the reply box left the current thread past the list's top edge: "
        f"{page.evaluate(COVERED_TOP)}"
    )


def test_a_press_on_the_comment_the_user_is_already_in_brings_it_back(browser, serve):
    """The same gesture as the test above, from the state the user is actually in when
    they make it: standing in a comment, the list carried a little, the card's top run
    gone past the list's top edge. They press the card to bring it back — and a press on the
    thread that already holds the focus moves no focus at all, so a landing hung off the
    focus event hears nothing and the user presses at a card that will not come.

    Which is why the press asks where the gesture left the user rather than which
    thread the focus moved to. The keyboard half of this was already answered — `T` at
    the top of the walk lands the thread it is already on — and this is the same shape
    one scope out."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(8):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    # Stand in the card first, then carry the list under it — which is the order the
    # user does it in, and the one where no later focus event is coming.
    first = page.locator(".lf-threads > .lf-thread:not([hidden])").first
    focus_panel_thread(first)
    rendered(page)
    page.evaluate(BURY, page.evaluate(UNDER_EDGE)["edge"])
    rendered(page)
    under = page.evaluate(UNDER_EDGE)
    assert under["covered"] >= under["edge"], (
        f"the list carried only {under['covered']}px past the list's top edge, which the "
        f"{under['edge']}px edge shows through — nothing here is cut yet"
    )
    assert page.evaluate(
        "() => Boolean(document.activeElement?.closest('.lf-thread'))"
    ), "the user is not standing in the card, so the press below moves focus"

    box = under["box"]
    page.mouse.click(box["x"] + 6, box["y"] + 80)
    rendered(page)
    assert page.evaluate(COVERED_TOP) is None, (
        "a press on the card the user was already standing in left it past the "
        f"list's top edge: {page.evaluate(COVERED_TOP)}"
    )
    assert not ring_faults(
        rings_drawn(page), "after a press on the card already standing in"
    )


def test_a_cancelled_panel_press_does_not_suppress_the_next_focus_landing(
    browser, serve
):
    """A touch scroll begins as a press and ends in ``pointercancel`` when the browser
    takes the gesture. Cancellation must not undo the scroll by landing the card, but it
    must end the provisional press: the next independent focus arrival still brings its
    thread back inside the list's top edge.

    Dispatch the pointer events directly so the browser does not add a mouse click or a
    default focus after the cancellation. An unrelated pointer first proves which gesture
    owns the hold; the matching cancellation and the focus after it then distinguish
    release-without-landing from both a stale hold and an ordinary pointer-up landing."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(8):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    first = page.locator(".lf-threads > .lf-thread:not([hidden])").first
    first.locator(":scope > .lf-thread-summary").evaluate(
        "el => el.focus({preventScroll: true})"
    )
    rendered(page)
    page.evaluate(BURY, 20)
    rendered(page)
    before = page.evaluate("() => document.querySelector('.lf-threads').scrollTop")
    assert page.evaluate(UNDER_EDGE)["covered"] >= 20, (
        "the setup did not put the first card past the list's top edge"
    )

    page.evaluate(
        """() => {
              const card = document.querySelector('.lf-threads > .lf-thread');
              card.dispatchEvent(new PointerEvent('pointerdown', {
                bubbles: true, isPrimary: true, pointerId: 7,
              }));
              dispatchEvent(new PointerEvent('pointercancel', {
                isPrimary: false, pointerId: 8,
              }));
            }"""
    )
    page.locator(".lf-threads").evaluate("el => el.focus({preventScroll: true})")
    first.locator(":scope > .lf-thread-summary").evaluate(
        "el => el.focus({preventScroll: true})"
    )
    rendered(page)
    assert page.evaluate(UNDER_EDGE)["covered"] >= 20, (
        "an unrelated pointer cancellation released the active panel gesture"
    )

    page.evaluate(
        """() => dispatchEvent(new PointerEvent('pointercancel', {
              isPrimary: true, pointerId: 7,
            }))"""
    )
    assert (
        page.evaluate("() => document.querySelector('.lf-threads').scrollTop") == before
    ), "cancelling a touch-scroll gesture landed the thread and undid the scroll"

    page.locator(".lf-threads").evaluate("el => el.focus({preventScroll: true})")
    first.locator(":scope > .lf-thread-summary").evaluate(
        "el => el.focus({preventScroll: true})"
    )
    rendered(page)
    assert page.evaluate(UNDER_EDGE)["covered"] <= 0, (
        "the cancelled press suppressed the next focus landing and left the card "
        f"{page.evaluate(UNDER_EDGE)['covered']}px past the list's top edge"
    )


def test_a_drag_across_a_quote_takes_its_words_and_not_its_passage(browser, serve):
    """The panel's quote is words and a press at once — it says which passage the comment
    is about, and pressing it travels the page there. So a user who drags across it to
    take the words gets the travel as well, and the page they were reading goes.

    `offer` has answered this for its own controls since a suggestion's Accept went dead
    under a selection that ran over it, and the answer is the same one: the selection's
    focus end is the character the button came up on, so a press that ended in these
    words was reaching for them. What is new is that the reading is now the reading and
    not that listener's own business, because the same gesture reaches two more things —
    a quote, which `offer` never made, and the list's own landing."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(8):
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-summary").first.click()
    page.locator(".lf-threads").focus()
    page.evaluate("() => { document.querySelector('.lf-threads').scrollTop = 0; }")
    # Keep the quoted passage outside the page's readable viewport. This test is the
    # drag/plain-press contrast: a readable destination deliberately stays put now,
    # so only an offscreen passage can prove the plain press still travels.
    page.evaluate(
        "() => document.scrollingElement.scrollTo(0, document.scrollingElement.scrollHeight)"
    )
    rendered(page)
    destination = page.evaluate(
        """() => {
              const target = document.querySelector('#merge-both').getBoundingClientRect();
              const banner = document.querySelector('.lf-banner').getBoundingClientRect();
              return {top: target.top, bottom: target.bottom,
                      banner: banner.bottom, height: innerHeight};
            }"""
    )
    assert (
        destination["bottom"] <= destination["banner"]
        or destination["top"] >= destination["height"]
    ), (
        f"the quoted passage is still readable, so a click need not travel: {destination}"
    )

    where = "() => document.scrollingElement.scrollTop"
    before = page.evaluate(where)
    quote = page.locator(".lf-threads > .lf-thread .lf-quote").first
    span = quote.bounding_box()
    page.mouse.move(span["x"] + 4, span["y"] + 6)
    page.mouse.down()
    page.mouse.move(span["x"] + span["width"] - 6, span["y"] + 6, steps=8)
    page.mouse.up()
    page_at_rest(page)

    drawn = page.evaluate("() => getSelection().toString()")
    assert len(drawn) > 8, (
        f"the drag took {drawn!r} of the quote, so this asserts nothing about one"
    )
    after = page.evaluate(where)
    assert after == before, (
        f"the page travelled from {before} to {after} while the user was taking "
        "the quote's words, so what they were reading went with it"
    )

    # The press itself still travels: what stood down is the drag, not the control.
    # The words go first, because a press inside a current selection is where the
    # platform holds it for a drag of its own — the user's next press is a press,
    # not the tail of the one before it.
    page.evaluate("() => getSelection().removeAllRanges()")
    quote.click()
    page_at_rest(page)
    assert page.evaluate(where) != before, (
        "a plain press on the quote no longer travels to its passage, so this took "
        "the control away rather than the drag"
    )


def test_a_drag_across_a_comments_words_leaves_the_list_where_it_was_read(
    browser, serve
):
    """The other half of landing a press, and the reason it waits for the press to end.
    Focus arrives on the way down, so a landing taken there scrolls the words out from
    under a pointer that is still selecting them — and the selection runs on to wherever
    they went, which measured about three times what the user had drawn.

    So the gesture is a real drag across a card near the top of the list, where any
    landing at all would move it, and the two things asserted are what the user has
    afterwards: the list where they were reading, and the words they actually dragged
    over. `offer` asks the same question of a click and reads the answer the same way —
    the selection's focus end is the character the button came up on."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(8):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-summary").first.click()
    page.locator(".lf-threads").focus()

    # Far enough past the list's top edge that a landing would be a visible jump, so the
    # drag below is asserting the absence of something this list would otherwise do.
    page.evaluate(BURY, 20)
    rendered(page)
    before = page.evaluate("() => document.querySelector('.lf-threads').scrollTop")
    # The message's own words, not the quote above them: a quote is a control that
    # jumps to the passage, so a drag ending on one has a second reason to scroll and
    # this would not be able to say which had moved the list.
    words = page.locator(".lf-threads > .lf-thread .lf-msg-body").first
    span = words.bounding_box()
    page.mouse.move(span["x"] + 4, span["y"] + span["height"] / 2)
    page.mouse.down()
    page.mouse.move(
        span["x"] + span["width"] - 4, span["y"] + span["height"] / 2, steps=8
    )
    page.mouse.up()
    rendered(page)

    after = page.evaluate("() => document.querySelector('.lf-threads').scrollTop")
    assert after == before, (
        f"the list moved from {before} to {after} under a drag, so the words the "
        "user was selecting went with it"
    )
    drawn = page.evaluate("() => getSelection().toString()")
    assert len(drawn) > 4, (
        f"the drag selected {drawn!r}, so this asserts nothing about a selection"
    )


def test_the_line_offers_the_thread_g_t_lands_on_its_own_keys(browser, serve):
    """The two contextual chips the line paints for a user `g T` brought into the panel
    have to be the thread's first local action and the exact way back: the line is two
    chips and the More control, so an unrelated row in front of these is a row instead
    of them.

    `g T` lands on the title of the thread the list shows open, so that thread's `r`
    leads, and Escape from a panel thread is the panel's own rung, which closes it. So
    an unrelated row in front of them here spends the slot the landing exists to fill.

    Read off `:not([hidden])`, because `renderShortcutBar` leaves every live row in the DOM and
    hides the ones outside the shortlist. `to_contain_text` on the line therefore
    answers about the register rather than about the user, and passes just as well
    when the chip is one nobody can see — which is why the rest of the panel's tests
    could not have caught this.

    The second press keeps a surface of its own: the box says the key in its own
    placeholder, which the last phase reads."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(3):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "text": "Which way round should this go?",
            "anchor": {"section": "how-store"},
        },
    )

    page = open_page(browser, url)
    page.evaluate("() => document.activeElement?.blur()")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(OPEN_TITLE)).to_be_focused()

    shown = page.locator(".lf-shortcut-bar .lf-shortcut:not([data-lf-off-line])")
    expect(shown).to_have_count(2)
    # The thread's own first key leads and the way out of the surface follows it, which
    # is what the line is for: the user can see the panel around them, and what they
    # came here to do is the press worth naming first.
    expect(shown.nth(0)).to_contain_text("resolve")
    expect(shown.nth(1)).to_contain_text("close threads")

    # And the press it displaced still works, from the placeholder that advertises it:
    # the reply box of the thread standing open. The badge inside the painted
    # placeholder is where the box states that key, and it stands only while the box is
    # hinted and empty, so reading it holds what the user can see rather than how the
    # hint's two parts happen to be joined.
    card = page.locator(".lf-threads > .lf-thread:not([hidden])[open]")
    advertised = card.locator(".lf-compose-placeholder kbd")
    expect(advertised).to_be_visible()
    expect(advertised).to_have_text("c")
    page.keyboard.press("c")
    expect(card.locator("leaf-text")).to_be_focused()


def test_escape_then_enter_round_trips_a_panel_reply(browser, serve):
    """Escape hands a reply back to its thread's title, and Enter there puts the user
    back in the box. The row answering Enter asked for a focused card root, which a
    panel thread's title is not, so the round trip stopped at the title."""
    url = serve(PANEL_PAGE)
    roots = seed_panel_threads(serve.page_dir, 3)
    page = open_page(browser, url)
    open_threads_list(page, 1200, 900)
    card = reply_by_keyboard(page, roots[1])
    page.keyboard.type("draft")
    page.keyboard.press("Escape")
    expect(card.locator(":scope > .lf-thread-summary")).to_be_focused()
    page.keyboard.press("Enter")
    expect(card.locator("leaf-text")).to_be_focused()
    expect(card.locator("leaf-text")).to_have_js_property("value", "draft")


def test_escape_from_a_seated_reply_send_returns_to_its_thread(browser, serve):
    """Escape leaves a reply's whole composition row, its Send control included, onto
    the thread the reply belongs to. On a thread seated in the page's flow the page's
    let-go answered Send first, since it deferred only to a box that takes letters, so
    the press dropped the user onto the page with the draft left behind."""
    url = serve(THREAD_DIFF_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Does the tray fit the north bracket?",
            "anchor": {"section": "cd-q"},
        },
    )
    page = open_page(browser, live_url(url))
    resized(page, 1200, 900)
    thread = page.locator("#cd-q .lf-page-thread")
    thread.focus()
    page.keyboard.press("c")
    box = thread.locator("leaf-text")
    expect(box).to_be_focused()
    page.keyboard.type("draft")
    page.keyboard.press("Tab")
    expect(thread.locator(".lf-thread-send")).to_be_focused()
    assert "back to thread" in shortcut_bar_text(page)
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    page.keyboard.press("Enter")
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", "draft")


def test_leaving_a_long_threads_reply_keeps_the_list_where_it_was(browser, serve):
    """Escape out of the reply of a thread taller than the list focuses its title
    without landing it: the landing took the list to the thread's head, away from the
    turn the user was answering."""
    url = serve(PANEL_PAGE)
    root = seed_panel_threads(serve.page_dir, 4, long_index=2)[2]
    page = open_page(browser, url)
    open_threads_list(page, 1200, 900)
    card = reply_by_keyboard(page, root)
    # Reply entry preserves the turn being read. Arrange the tail explicitly so
    # this test proves Escape keeps that context rather than choosing it on entry.
    card.locator(".lf-msg").last.evaluate(
        "message => message.scrollIntoView({block: 'nearest', behavior: 'instant'})"
    )
    scroll_settled(page, ".lf-threads")
    assert card.locator(".lf-msg").last.evaluate(IN_LANDING_BAND)["inside"]
    before = page.locator(".lf-threads").evaluate("list => list.scrollTop")
    assert before > 0, "the reply landed without scrolling, so this proves nothing"
    page.keyboard.press("Escape")
    expect(card.locator(":scope > .lf-thread-summary")).to_be_focused()
    rendered(page)
    scroll_settled(page, ".lf-threads")
    assert page.locator(".lf-threads").evaluate("list => list.scrollTop") == before
    assert card.locator(".lf-msg").last.evaluate(IN_LANDING_BAND)["inside"]


def test_standing_again_on_a_long_threads_target_keeps_the_list(browser, serve):
    """With Threads open, arriving by keyboard at a target whose thread the list
    already has expanded, and partly in view, leaves the list where the user put it.
    The thread is taller than the list, so it can show no more of itself; the arrival
    took the list to its title, away from the turn the user had scrolled to."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Thread opening. " + LANDING_WORDS, {"section": "how-cap"}
    )
    for turn in range(1, 12):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent" if turn % 2 else "user",
                **({"agent": "Codex"} if turn % 2 else {}),
                "parent": root,
                "text": f"Turn {turn}. " + LANDING_WORDS,
            },
        )
    page = open_page(browser, url)
    open_threads_list(page, 1200, 900)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    listing = page.locator(".lf-threads")

    # Keyboard modality without Tab, whose own landing in the list would scroll it.
    def arrive(selector):
        page.keyboard.press("Shift")
        page.locator(selector).evaluate(
            "node => { if (node.getAttribute('tabindex') !== '-1') node.tabIndex = -1;"
            " node.focus(); }"
        )
        expect(page.locator(selector)).to_be_focused()
        rendered(page)
        scroll_settled(page, ".lf-threads")

    arrive("#how-cap")
    expect(card).to_have_attribute("open", "")
    listing.evaluate("list => { list.scrollTop += list.clientHeight / 2; }")
    scroll_settled(page, ".lf-threads")
    before = listing.evaluate("list => list.scrollTop")
    shown = card.evaluate(
        """card => {
          const list = card.closest('.lf-threads').getBoundingClientRect();
          const box = card.getBoundingClientRect();
          return box.top < list.top && box.bottom > list.top && box.height > list.height;
        }"""
    )
    assert shown, "the thread is not a tall one partly in view, so this proves nothing"
    arrive("#how-store")
    arrive("#how-cap")
    expect(card).to_have_attribute("open", "")
    assert listing.evaluate("list => list.scrollTop") == before


def test_reopening_a_touch_panel_keeps_its_reading_position_and_draft(browser, serve):
    """A modal panel returns to the turn being read; an explicit thread walk lands.

    Reopening forwarded focus through the retained list as a fresh navigation and
    carried an earlier reading to the latest turn, despite keeping the draft node.
    """
    url = serve(PANEL_PAGE)
    root = seed_panel_threads(serve.page_dir, 1, long_index=0)[0]
    context = browser.new_context(
        has_touch=True,
        viewport={"width": 390, "height": 740},
        reduced_motion="reduce",
    )
    page = open_page(browser, url, context=context)
    toggle = page.locator(".lf-threads-toggle")
    toggle.tap()
    panel_settled(page)
    panel = page.locator(".lf-thread-panel")
    envelope = page.locator(".lf-auxiliary-envelope")
    assert envelope.evaluate("el => el.matches(':modal')")
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    if card.get_attribute("open") is None:
        card.locator(":scope > .lf-thread-summary").tap()
    earlier = card.get_by_role(
        "button", name=re.compile(r"^Show \d+ earlier messages$")
    )
    if earlier.is_visible():
        earlier.tap()
    field = card.locator(".lf-thread-reply leaf-text")
    field.tap()
    draft = "\n".join(f"Draft line {n}" for n in range(20))
    page.keyboard.insert_text(draft)
    expect(field).to_have_js_property("value", draft)
    retained = field.element_handle()
    caret = field.evaluate("el => [el.selectionStart, el.selectionEnd]")
    rendered(page)
    listing = page.locator(".lf-threads")
    limit = listing.evaluate("el => el.scrollHeight - el.clientHeight")
    assert limit > listing.evaluate("el => el.clientHeight")
    port = listing.bounding_box()
    touch = context.new_cdp_session(page)
    touch.send(
        "Input.synthesizeScrollGesture",
        {
            "x": port["x"] + port["width"] * 0.7,
            "y": port["y"] + min(80, port["height"] / 4),
            "yDistance": limit + 100,
            "gestureSourceType": "touch",
            "speed": 10000,
        },
    )
    scroll_settled(page, ".lf-threads")
    before = listing.evaluate("el => el.scrollTop")
    assert before < limit - 100, "the touch gesture must reveal an earlier turn"
    panel.get_by_role("button", name="Close threads", exact=True).tap()
    panel_settled(page, open=False)
    assert not envelope.evaluate("el => el.matches(':modal')")
    toggle.tap()
    panel_settled(page)
    rendered(page)
    scroll_settled(page, ".lf-threads")
    assert envelope.evaluate("el => el.matches(':modal')")
    assert listing.evaluate("el => el.scrollTop") == before
    assert field.evaluate("(el, retained) => el === retained", retained)
    expect(field).to_have_js_property("value", draft)
    assert field.evaluate("el => [el.selectionStart, el.selectionEnd]") == caret
    page.keyboard.press("t")
    page.wait_for_function(
        "before => document.querySelector('.lf-threads').scrollTop > before", arg=before
    )
    scroll_settled(page, ".lf-threads")
    assert card.locator(".lf-msg").last.evaluate(IN_LANDING_BAND)["inside"]


@pytest.mark.parametrize("view", ["panel", "margin"])
def test_entering_a_reply_keeps_the_thread_reading_position(browser, serve, view):
    """A reply already on screen keeps the earlier turn the user is reading."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Opening turn. " + LANDING_WORDS, {"section": "how-store"}
    )
    for turn in range(12):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "parent": root,
                "text": f"Turn {turn}. " + LANDING_WORDS,
            },
        )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    if view == "panel":
        open_threads_list(page, 1200, 900)
        card = reply_by_keyboard(page, root)
        reading = page.locator(".lf-threads")
        page.keyboard.type("A reply in progress.")
        page.keyboard.press("Escape")
        expect(card.locator(":scope > .lf-thread-summary")).to_be_focused()
        reading.evaluate("list => { list.scrollTop = 100; }")
        latest = card.locator(".lf-msg").last
    else:
        page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
        card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
        page.keyboard.press("c")
        expect(card.locator("leaf-text")).to_be_focused()
        page.keyboard.type("A reply in progress.")
        page.keyboard.press("Escape")
        expect(card).to_be_focused()
        reading = card.locator(":scope > .lf-thread-transcript")
        reading.evaluate("transcript => { transcript.scrollTop = 0; }")
        latest = card.locator(".lf-msg").last
    reading_selector = (
        ".lf-threads"
        if view == "panel"
        else f'.lf-margin-preview .lf-page-thread[data-thread="{root}"] > .lf-thread-transcript'
    )

    rendered(page)
    scroll_settled(page)
    scroll_settled(page, reading_selector)
    assert reading.evaluate("box => box.scrollHeight > box.clientHeight")
    assert (
        latest.bounding_box()["y"]
        >= reading.bounding_box()["y"] + reading.bounding_box()["height"]
    )
    reply = card.locator("leaf-text")
    assert clear_of_the_bar(page, reply)
    if view == "panel":
        assert reply.evaluate(IN_LANDING_BAND)["inside"]
    before = [page.evaluate("scrollY"), reading.evaluate("box => box.scrollTop")]
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    rendered(page)
    scroll_settled(page)
    scroll_settled(page, reading_selector)
    assert [
        page.evaluate("scrollY"),
        reading.evaluate("box => box.scrollTop"),
    ] == before


def test_accordion_keyboard_travel_keeps_drafts_and_respects_narrowing(browser, serve):
    """Native focus order and thread travel keep retained threads and drafts."""
    url = serve(PANEL_PAGE)
    first = panel_comment(
        serve.page_dir, "Check the cap first.", {"section": "how-cap"}
    )
    second = panel_comment(
        serve.page_dir, "Check the merge next.", {"section": "merge-both"}
    )
    page = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{first}"]')
    other = page.locator(f'.lf-thread[data-id="{second}"]')
    header = card.locator(".lf-thread-summary")
    expect(card).to_have_attribute("open", "")
    expect(other).not_to_have_attribute("open", "")
    header.focus()
    page.keyboard.press("Tab")
    assert page.evaluate(
        "() => document.querySelector('.lf-threads').contains(document.activeElement)"
    ), "native focus order left the thread list"
    other.locator(".lf-thread-summary").focus()
    page.keyboard.press("Enter")
    expect(other).to_have_attribute("open", "")
    expect(card).not_to_have_attribute("open", "")
    header.focus()
    page.keyboard.press("Enter")
    expect(card).to_have_attribute("open", "")
    page.keyboard.press("Tab")
    assert page.evaluate(
        "id => document.activeElement.closest('.lf-thread')?.dataset.id === id", first
    ), "native focus order skipped the open thread"
    # A thread in the panel unwinds the panel itself, not its own disclosure.
    header.focus()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    expect(card).to_have_attribute("open", "")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    # Panel controls similarly unwind the panel, not the unrelated disclosure.
    page.get_by_role("button", name="View", exact=True).focus()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    expect(card).to_have_attribute("open", "")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    header.focus()
    page.keyboard.press("Space")
    expect(card).to_have_attribute("open", "")
    expect(other).not_to_have_attribute("open", "")
    page.keyboard.press("Tab")
    assert page.evaluate(
        "id => document.activeElement.closest('.lf-thread')?.dataset.id === id", first
    ), "native focus order skipped the open thread"
    header.focus()
    page.keyboard.press("c")
    editor = card.get_by_role("textbox", name="Reply", exact=True)
    expect(editor).to_be_focused()
    write(editor, "Keep this unfinished answer.")
    page.keyboard.press("Home")
    expect(editor).to_be_focused()
    page.keyboard.press("Escape")
    expect(card.locator(":scope > .lf-thread-summary")).to_be_focused()
    page.keyboard.press("t")
    expect(other).to_have_attribute("open", "")
    expect(card).not_to_have_attribute("open", "")
    page.keyboard.press("Shift+t")
    expect(editor).to_be_visible()
    expect(editor).to_have_js_property("value", "Keep this unfinished answer.")
    search = page.get_by_role("searchbox", name="Find in threads")
    search.fill("merge next")
    expect(other).to_be_visible()
    expect(card).to_be_hidden()
    page.locator(".lf-threads").focus()
    page.keyboard.press("n")
    expect(other).to_have_attribute("open", "")
    expect(other.locator(":scope > .lf-thread-summary")).to_be_focused()
    page.keyboard.press("n")
    expect(other.locator(":scope > .lf-thread-summary")).to_be_focused()
    search.fill("")
    header.click()
    expect(editor).to_have_js_property("value", "Keep this unfinished answer.")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    header.focus()
    page.keyboard.press("c")
    expect(editor).to_be_focused()
    with sending(page, "send the retained accordion draft"):
        page.keyboard.press("ControlOrMeta+Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["parent"], sent["text"]) == (
        "reply",
        first,
        "Keep this unfinished answer.",
    )
    assert not take_browser_errors(page)


def test_a_click_survives_an_element_whose_id_shadows_a_dom_method(browser, serve):
    """A click's composed path ends at the document and the window, and an element with
    `id="matches"` puts itself at `window.matches`, where a reader of that path expects
    Element's method. A handoff page with a "matches" section threw on every click."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "named access",
                '<h1 id="title">Pairs</h1><h2 id="matches">A pair that matches</h2>'
                "<p id='body'>Words to click.</p>",
            )
        ),
    )
    page.locator("#matches").click()
    page.locator("#body").click()


def test_unused_panel_space_is_neutral_but_keeps_the_thread_context(browser, serve):
    """Thread paint follows its content; spare panel room still navigates that thread."""
    color_scheme = "light"
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "A short discussion.", {"section": "lede"})
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, color_scheme=color_scheme
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-thread[open]")
    reply = thread.locator("leaf-text")
    write(reply, "Keep my draft.")
    geometry = thread.evaluate(
        """el => {
          const content = el.querySelector('.lf-thread-content').getBoundingClientRect();
          const reply = el.querySelector('.lf-thread-reply').getBoundingClientRect();
          const box = el.getBoundingClientRect();
          const list = el.parentElement.getBoundingClientRect();
          return {x: Math.floor(box.left + box.width / 2),
                  y: Math.floor((box.bottom + list.bottom) / 2),
                  surfaceY: Math.floor(content.top + 4),
                  freeHeight: list.bottom - box.bottom,
                  replyGap: reply.top - content.bottom};
        }"""
    )
    assert geometry["freeHeight"] > 20, geometry
    assert 0 <= geometry["replyGap"] <= 20, geometry
    # Read actual pixels: both the wrapper and a focus-within ancestor can paint it.
    shot = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
    x, y = geometry["x"], geometry["y"]
    assert shot.getpixel((x, y)) != shot.getpixel((x, geometry["surfaceY"])), (
        "unused panel space wears the thread's content surface"
    )
    page.mouse.click(x, y)
    expect(thread.locator(".lf-thread-summary")).to_be_focused()
    assert reply.evaluate("el => el.value") == "Keep my draft."
    page.keyboard.press("c")
    expect(reply).to_be_focused()
