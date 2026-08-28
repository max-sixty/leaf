"""Comment-panel ordering, narrowing, and thread-motion tests."""

import re

import pytest
from leaf import conversation as conversation_model
from leaf import event_log as events_model
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_support import (
    COVERED_TOP,
    EDGES,
    FRAME_BY_FRAME,
    HOLD_MOTION,
    LIST_RUNS,
    LIST_STATE,
    LONG_PAGE,
    PANEL_PAGE,
    RENDERED,
    draw_edge,
    edge_settled,
    in_threads_scrollport,
    leaf_page,
    open_page,
    panel_comment,
    panel_settled,
    resized,
    ring_faults,
    rings_drawn,
    round_trip,
    standing_ring,
    told,
    undo,
)

pytestmark = pytest.mark.nightly


def test_a_sent_comment_is_revealed_in_the_panel(browser, serve):
    """A send is the one gesture that produces a thread, so it gets the same answer a
    click on a page mark does: the panel scrolls the new thread into its scrollport.
    On a list long enough to scroll, the old rebuild appended the comment below the
    fold and put the scroll back where it was — the user's own words landed out of
    sight, silently. Both send routes then end in the composer the words left, where
    the rebuild sent a button click's focus somewhere else than ⌘⏎'s."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=12))
    page.locator(".lf-comments").click()
    panel_settled(page)
    assert page.evaluate(
        "() => { const t = document.querySelector('.lf-threads');"
        "        return t.scrollTop === 0 && t.scrollHeight > t.clientHeight; }"
    ), "this list starts revealed or doesn't scroll, so it proves nothing"

    box = page.locator(".lf-general textarea")
    box.fill("Where did my words go?")
    page.locator(".lf-general button").click()  # the route that used to drop focus
    round_trip(page)
    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["text"]) == ("comment", "Where did my words go?")
    in_threads_scrollport(page, f'.lf-thread[data-id="{sent["id"]}"]')
    assert page.evaluate("() => document.querySelector('.lf-threads').scrollTop") > 0, (
        "the new thread was in view without scrolling, so the reveal proved nothing"
    )
    expect(box).to_be_focused()
    expect(box).to_have_value("")

    box.fill("And the second thought lands the same way.")
    page.keyboard.press("ControlOrMeta+Enter")  # the other route, same destination
    round_trip(page)
    second = events_model.read_events(serve.page_dir)[-1]
    in_threads_scrollport(page, f'.lf-thread[data-id="{second["id"]}"]')
    expect(box).to_be_focused()
    assert errors == []
    page.close()


def test_an_arriving_reply_leaves_the_list_where_the_reader_put_it(browser, serve):
    """News has no gesture behind it, so it may move nothing the reader is looking at.
    The hard case is a reply landing in a thread above the fold: the list grows over
    the reader's head, and what must hold still is the thread in front of them — their
    place as a box on screen, not as a scrollTop the browser's own scroll anchoring is
    free to adjust. The old rebuild restored the offset and let the content slide under
    it."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=12))
    page.locator(".lf-comments").click()
    panel_settled(page)
    held = page.evaluate("""() => {
        const box = document.querySelector('.lf-threads');
        box.scrollTop = 400;
        const b = box.getBoundingClientRect();
        window.__held = [...box.querySelectorAll(':scope > .lf-thread')]
            .find(n => n.getBoundingClientRect().top >= b.top);
        return { top: window.__held.getBoundingClientRect().top,
                 scrolled: box.scrollTop > 0 };
    }""")
    assert held["scrolled"], "the list doesn't scroll, so nothing here can move"

    first = next(
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    reply = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Claude",
            "revision": 1,
            "parent": first["id"],
            "text": "News, not a gesture.",
        },
    )
    told(page)
    expect(page.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_have_count(1)
    after = page.evaluate(
        "() => ({ connected: window.__held.isConnected,"
        "          top: window.__held.getBoundingClientRect().top })"
    )
    assert after["connected"], "the held thread was replaced, so its box says nothing"
    assert abs(after["top"] - held["top"]) < 1, (
        f"the arriving reply moved the thread the reader was on: {held} -> {after}"
    )
    assert errors == []
    page.close()


def test_an_arrival_interrupts_nothing_the_user_holds(browser, serve):
    """The nodes themselves survive the poll: the thread being typed in is the same
    element afterwards, still focused, caret where the typing left it — even when the
    arrival lands inside that very thread, right above the reply box. The rebuild
    could only approximate this by saving and restoring focus and caret by hand, and
    the two send routes proved the restore had holes."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=3))
    page.locator(".lf-comments").click()
    panel_settled(page)
    ta = page.locator(".lf-threads > .lf-thread").first.locator("textarea")
    ta.click()
    ta.type("half a thought")
    page.evaluate("""() => {
        document.activeElement.setSelectionRange(4, 4);
        window.__probe = document.activeElement.closest('.lf-thread');
    }""")

    first = next(
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    reply = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Claude",
            "revision": 1,
            "parent": first["id"],
            "text": "Landing right above the box being typed in.",
        },
    )
    told(page)
    expect(page.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_have_count(1)
    assert page.evaluate("""() => {
        const ta = document.activeElement;
        return ta.tagName === 'TEXTAREA'
            && ta.closest('.lf-thread') === window.__probe
            && window.__probe === document.querySelector('.lf-threads > .lf-thread')
            && ta.value === 'half a thought'
            && ta.selectionStart === 4 && ta.selectionEnd === 4;
    }"""), "the poll replaced or disturbed the node the user was typing into"
    assert errors == []
    page.close()


@pytest.mark.parametrize("width", [320, 800])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_thread_gives_its_reply_the_full_row_and_its_actions_the_next(
    browser, serve, width, scheme
):
    """Reply names the field, while Send and Resolve share the action row beneath it.

    Growing the field moves both actions down together without changing either action's
    horizontal place. The same geometry holds in the panel's narrowest useful window and
    with room beside the page, in both palettes."""
    context = browser.new_context(
        viewport={"width": width, "height": 720}, color_scheme=scheme
    )
    try:
        page, errors = open_page(browser, serve(LONG_PAGE, comments=1), context=context)
        page.locator(".lf-comments").click()
        panel_settled(page)
        thread = page.locator(".lf-threads > .lf-thread")
        compose = thread.locator(".lf-compose")
        textarea = compose.locator("textarea")
        send = thread.get_by_role("button", name="Send", exact=True)
        resolve = thread.get_by_role("button", name="Resolve", exact=True)
        expect(send).to_be_visible()
        expect(resolve).to_be_visible()

        def geometry():
            return thread.evaluate(
                """thread => {
                  const rect = sel => {
                    const r = thread.querySelector(sel).getBoundingClientRect();
                    return {x: r.x, y: r.y, width: r.width, height: r.height,
                            right: r.right, bottom: r.bottom};
                  };
                  return {compose: rect('.lf-compose'),
                          textarea: rect('.lf-compose textarea'),
                          actions: rect('.lf-thread-actions'),
                          send: rect('.lf-thread-send'), resolve: rect('.lf-resolve'),
                          overflow: thread.scrollWidth - thread.clientWidth};
                }"""
            )

        short = geometry()
        assert short["textarea"]["x"] == pytest.approx(short["compose"]["x"], abs=1)
        assert short["textarea"]["right"] == pytest.approx(
            short["compose"]["right"], abs=1
        )
        assert short["actions"]["y"] >= short["textarea"]["bottom"]
        assert short["send"]["y"] == pytest.approx(short["resolve"]["y"], abs=1)
        assert short["send"]["x"] < short["resolve"]["x"]
        assert short["resolve"]["right"] == pytest.approx(
            short["actions"]["right"], abs=1
        )
        assert short["overflow"] == 0

        textarea.focus()
        focused = geometry()
        for control in ("send", "resolve"):
            assert focused[control] == short[control], (
                f"[{width}px {scheme}] focusing the reply moved {control}: "
                f"{short[control]} -> {focused[control]}"
            )

        textarea.fill("First line.\nSecond line.\nThird line.\nFourth line.")
        grown = geometry()
        assert grown["actions"]["y"] >= grown["textarea"]["bottom"]
        assert grown["send"]["y"] == pytest.approx(grown["resolve"]["y"], abs=1)
        for control in ("send", "resolve"):
            assert grown[control]["x"] == pytest.approx(short[control]["x"], abs=1)
            assert grown[control]["width"] == pytest.approx(
                short[control]["width"], abs=1
            )
        assert grown["send"]["y"] - short["send"]["y"] == pytest.approx(
            grown["resolve"]["y"] - short["resolve"]["y"], abs=1
        )
        assert grown["send"]["y"] > short["send"]["y"]
        assert grown["overflow"] == 0
        assert errors == []
    finally:
        context.close()


def test_resolving_an_early_thread_renumbers_the_rest_in_place(browser, serve):
    """A thread can move, not just appear: resolving the first one sends it to the
    resolved disclosure and renumbers every thread after it — the address its reply
    box speaks moving with it, on nodes that are kept rather than remade. The
    disclosure itself is kept too, so the user's open toggle survives the next
    resolution instead of snapping shut on every arrival, which is what the rebuild
    did."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=3))
    page.locator(".lf-comments").click()
    panel_settled(page)
    c1, c2, c3 = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    expect(page.locator(f'.lf-thread[data-id="{c2}"] textarea')).to_have_attribute(
        "placeholder", "Reply · g c 2"
    )
    page.evaluate(
        """(id) => { window.__second = document.querySelector(`.lf-thread[data-id="${id}"]`); }""",
        c2,
    )

    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    round_trip(page)
    # The resolved node took the pressed button with it; focus lands on the thread
    # that now holds its place rather than falling to body.
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    expect(page.locator(f'.lf-details .lf-thread[data-id="{c1}"]')).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{c1}"] textarea')).to_have_count(0)
    expect(page.locator(".lf-comments")).to_have_text("Comments (2)")
    # The survivors renumber without being remade: same node, new address, and the
    # address its placeholder speaks moved with it.
    expect(page.locator(f'.lf-thread[data-id="{c2}"] textarea')).to_have_attribute(
        "placeholder", "Reply · g c 1"
    )
    assert page.evaluate(
        """(id) => window.__second === document.querySelector(`.lf-thread[data-id="${id}"]`)""",
        c2,
    ), "renumbering rebuilt the surviving thread"

    page.locator(".lf-details summary").click()
    expect(page.locator(".lf-details[open]")).to_have_count(1)
    # A thread leaving mid-list puts every survivor one place forward. Standing still
    # there is the reconcile's own duty, not the browser's: a survivor reinserted at
    # its new place is the same element and passes any identity probe, but reinsertion
    # drops the caret typing in it.
    ta3 = page.locator(f'.lf-thread[data-id="{c3}"] textarea')
    ta3.click()
    ta3.type("held mid-sentence")
    page.evaluate("() => document.activeElement.setSelectionRange(4, 4)")
    events_model.append_event(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": c2}
    )
    told(page)
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (2)")
    expect(page.locator(".lf-details[open]")).to_have_count(1)
    expect(ta3).to_be_focused()
    assert page.evaluate(
        "() => document.activeElement.value === 'held mid-sentence'"
        "   && document.activeElement.selectionStart === 4"
    ), "the thread after the one that resolved was reinserted under the typing"
    assert errors == []
    page.close()


def test_the_panel_reads_the_conversation_in_the_pages_own_order(browser, serve):
    """The list is the page's order, not the log's. A reader walking a long
    conversation walks it the way they walk the prose it is about, and every other
    reading of these threads already does: the marks down the page, the j/k walk, the
    g c digits. So the threads are written here in the reverse of the page's order and
    the panel is asked for its own, which is only the page's if something sorted it.

    A thread with nowhere in the page to be — a comment about the whole of it — comes
    after the ones that have somewhere, under its own heading, rather than at the
    moment it happened to be written."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    whole = panel_comment(d, "The middle third is too long.")
    merge = panel_comment(d, "Answer this one first.", {"section": "merge-both"})
    cap = panel_comment(d, "Is forty enough?", {"section": "how-cap"})
    lede = panel_comment(d, "Six weeks reads long.", {"section": "lede"})

    page, errors = open_page(browser, url)
    page.locator(".lf-comments").click()
    panel_settled(page)
    assert page.evaluate(LIST_RUNS) == [
        "§ Shipping offline editing",
        lede,
        "§ How it works",
        cap,
        "§ The merge rule",
        merge,
        "§ About the page as a whole",
        whole,
    ], "the panel is not reading in the page's order"

    # The addresses and the walk are the same order, because both read the list itself.
    expect(page.locator(f'.lf-thread[data-id="{lede}"] textarea')).to_have_attribute(
        "placeholder", "Reply · g c 1"
    )
    page.locator("body").click()
    page.keyboard.press("j")
    expect(page.locator(f'.lf-thread[data-id="{lede}"]')).to_be_focused()
    page.keyboard.press("j")
    expect(page.locator(f'.lf-thread[data-id="{cap}"]')).to_be_focused()
    assert errors == []
    page.close()


def test_a_page_with_no_headings_gets_the_order_and_no_landmarks(browser, serve):
    """The order is the page's whether or not the page has an outline; the landmarks are
    the outline's. A page its author wrote no headings into gets the first without the
    second, rather than one line reading "Above the first heading" over the whole list —
    a landmark naming a landmark the page hasn't got."""
    url = serve(
        leaf_page(
            "bare",
            """
<p id="one">The first paragraph, with nothing above it.</p>
<p id="two">The second paragraph, with nothing above it either.</p>
""",
        )
    )
    d = serve.page_dir
    second = panel_comment(d, "On the second.", {"section": "two"})
    first = panel_comment(d, "On the first.", {"section": "one"})

    page, errors = open_page(browser, url)
    page.locator(".lf-comments").click()
    panel_settled(page)
    assert page.evaluate(LIST_RUNS) == [
        first,
        second,
    ], "a page with no outline did not get the page's order, or was given a landmark"
    expect(page.locator(".lf-group")).to_have_count(0)
    assert errors == []
    page.close()


def test_a_thread_on_words_a_widget_renders_stands_where_the_widget_does(
    browser, serve
):
    """A widget may render the page's words into a declared shadow tree, and a passage
    inside one is placed inside that tree. Asked to compare it with an element of the
    document, `compareDocumentPosition` answers "disconnected" in an order of its own
    choosing, and `contains` answers no across the same boundary — so the thread would
    sort and group by something the reader has never seen.

    The host is the element the page holds, and where the page holds it is where those
    words are. So the thread reads after the paragraphs above the widget and under the
    heading the widget itself is under."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    lede = panel_comment(d, "Six weeks reads long.", {"section": "lede"})
    patch = panel_comment(
        d, "Twelve is arbitrary.", {"quote": "the ceiling doubles per approval"}
    )
    both = panel_comment(d, "Answer this one first.", {"section": "merge-both"})

    page, errors = open_page(browser, url)
    page.locator(".lf-comments").click()
    panel_settled(page)
    # The passage really is inside the widget's shadow tree, so the reading under test is
    # the cross-tree one rather than an ordinary document comparison.
    assert page.evaluate(
        """() => {
             const root = document.getElementById('how-patch').shadowRoot;
             return Boolean(root) && [...(CSS.highlights.get('lf-mark') ?? [])]
               .some((r) => root.contains(r.startContainer));
           }"""
    ), "the fixture's passage is not marked inside a shadow tree"
    assert page.evaluate(LIST_RUNS) == [
        "§ Shipping offline editing",
        lede,
        "§ How it works",
        patch,
        "§ The merge rule",
        both,
    ], "the thread on the widget's words does not stand where the widget does"
    assert errors == []
    page.close()


def test_a_run_of_threads_says_which_part_of_the_page_it_is_about(browser, serve):
    """A heading over each run, and it stays on screen while the run scrolls past it —
    which is the whole of what it is for. A list four thousand pixels long is scrolled
    past its landmarks inside one gesture, so a heading that scrolled away with its own
    threads would answer "where am I" only at the moment the reader already knew.

    Pressing one takes the reader to that part of the page, the move a thread's quote
    makes for one passage made here for the section it is in."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(6):
        panel_comment(d, f"On the merge rule, {i}.", {"section": "merge-both"})
    panel_comment(d, "On the lede.", {"section": "lede"})

    page, errors = open_page(browser, url)
    resized(page, 1280, 800)
    page.locator(".lf-comments").click()
    panel_settled(page)
    heading = page.locator(".lf-group[data-group]", has_text="The merge rule")
    expect(heading).to_have_count(1)

    # Scroll the run's own threads up past the top of the list, and the heading is still
    # there — pinned at the top edge rather than gone with them. Opaque, because what it
    # covers is the thread passing underneath it.
    page.evaluate(
        """() => { const box = document.querySelector('.lf-threads');
                   box.scrollTop = box.scrollHeight; }"""
    )
    page.wait_for_function(
        """() => { const box = document.querySelector('.lf-threads');
                   return box.scrollTop + box.clientHeight >= box.scrollHeight - 1; }"""
    )
    assert page.evaluate(
        """() => {
             const box = document.querySelector('.lf-threads').getBoundingClientRect();
             const head = [...document.querySelectorAll('.lf-group')]
               .find((n) => n.textContent === 'The merge rule');
             const first = document.querySelector('.lf-threads > .lf-thread')
               .getBoundingClientRect();
             const paint = getComputedStyle(head).backgroundColor;
             const r = head.getBoundingClientRect();
             return { pinned: r.top <= box.top + 1 && r.bottom > box.top + 8,
                      scrolledPast: first.top < box.top,
                      opaque: !/rgba\\(.*, 0\\)$/.test(paint) };
           }"""
    ) == {
        "pinned": True,
        "scrolledPast": True,
        "opaque": True,
    }, "the run's heading did not stay over the run"

    heading.click()
    page.wait_for_function(
        """() => { const r = document.getElementById('h-merge').getBoundingClientRect();
                   return Math.abs(r.top + r.height / 2 - innerHeight / 2) < 2; }"""
    )
    assert errors == []
    page.close()


def test_finding_narrows_the_list_and_says_how_much_of_it_is_left(browser, serve):
    """A search box is what every panel with a long list has, and the trap every one of
    them has too: the list goes quiet about the threads it is hiding. So the head says
    how much of the conversation is in front of the reader for as long as a narrowing
    stands, and a thread asked for by name — a mark on the page, a send that landed —
    lets the narrowing go rather than declining to appear.

    The narrowing reads the words, the part of the page, and nothing else: the count in
    the banner is the log's and does not move."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    lede = panel_comment(d, "Six weeks reads long.", {"section": "lede"})
    cap = panel_comment(d, "Is forty megabytes enough?", {"section": "how-cap"})
    merge = panel_comment(d, "Answer this one first.", {"section": "merge-both"})

    page, errors = open_page(browser, url)
    # Searching a list is a press on that list, so the key is the panel's: out on the
    # prose it does nothing, and `c` is the whole route in — it stands the reader on the
    # list, which is where the panel's own keys are live. Read against the same press
    # landing two lines below, which is what makes the silence a rule.
    #
    # A plain paragraph rather than the body's own middle, which is a widget on this
    # page: `c` goes to the box belonging to whatever the reader is standing in, so a
    # press made from the diff opens the composer on the diff and never reaches the panel
    # at all. Standing on prose is what "out on the prose" was always describing — and an
    # uncommented one, a click on a mark opening the thread it carries, which would be the
    # panel arriving ahead of the press that is meant to open it.
    page.locator("#how-store").click()
    page.keyboard.press("/")
    expect(page.locator(".lf-panel")).not_to_be_visible()
    page.keyboard.press("c")
    panel_settled(page)
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("/")
    expect(page.locator(".lf-find-box")).to_be_focused()

    page.keyboard.type("megabytes")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{cap}"]')).to_have_count(1)
    expect(page.locator(".lf-panel-head span")).to_have_text("Showing 1 of 3")
    # The page's own count is the log's and says so throughout.
    expect(page.locator(".lf-comments")).to_have_text("Comments (3)")

    # The part of the page a thread is on is one of its words: a reader looking for the
    # merge rule finds the thread under that heading without its message saying so.
    page.fill(".lf-find-box", "merge rule")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{merge}"]')).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{lede}"]')).to_have_count(0)

    # Asked for a thread the narrowing hides, the panel shows it rather than nothing:
    # the press came from the page, where no narrowing was ever visible.
    page.locator("#lede").click()
    expect(page.locator(f'.lf-thread[data-id="{lede}"]')).to_have_count(1)
    expect(page.locator(".lf-find-box")).to_have_value("")
    expect(page.locator(".lf-panel-head span")).to_have_text("Comments")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(3)

    # Escape spends one rung on the narrowing and the next on the box, rather than
    # both on one press: the reader can see which of the two they are backing out of.
    page.locator(".lf-find-box").click()
    page.keyboard.type("megabytes")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(1)
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(3)
    expect(page.locator(".lf-find-box")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    assert errors == []
    page.close()


def test_the_panel_can_show_only_what_is_waiting_on_the_reader(browser, serve):
    """Which threads the reader still owes an answer to is a question the log already
    answers: an agent comment asks by construction, and a reply may declare another
    ask. So the panel reads the log rather than keeping a record of what this reader
    has read — nothing to go stale in a second tab, and nothing to remember across a
    reload.

    The count is the whole page's; the list is the ones it names."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    mine = panel_comment(d, "Six weeks reads long.", {"section": "lede"})
    theirs = panel_comment(d, "Is forty enough?", {"section": "how-cap"}, "claude")

    page, errors = open_page(browser, url)
    # The key belongs to the panel, not to the page: a list the reader is not looking at
    # is not a thing to narrow. Out on the prose the line never offers it and the press
    # does nothing — read against the same press landing a few lines below, which is what
    # makes the silence a rule rather than a page that happened not to react.
    #
    # A plain paragraph rather than the body's own middle, which is a widget here: `c`
    # below goes to the box belonging to whatever the reader is standing in, and a press
    # made from the diff would open the composer on the diff rather than reach the panel
    # at all. Uncommented, too: a click on a mark opens the thread it carries.
    page.locator("#how-store").click()
    expect(page.locator(".lf-keyline")).not_to_contain_text("waiting on you")
    page.keyboard.press("w")
    expect(page.locator(".lf-panel")).not_to_be_visible()

    # `c` stands the reader on the list, where the key is live and the line says so.
    # The control names it, off the row, so the two cannot come to spell it differently.
    page.keyboard.press("c")
    panel_settled(page)
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(page.locator(".lf-needs")).to_have_text("Waiting on you (1)")
    expect(page.locator(".lf-needs")).to_have_attribute("title", re.compile(r"\(w\)$"))
    expect(page.locator(".lf-keyline")).to_contain_text("waiting on you")
    # A second `c` is the general box, and there `w` is a character like any other —
    # the typing scope claims what types one, so the row stands down and the line drops
    # it. Escape backs out onto the list and it is live again. Both directions, because
    # a key that were live in the box would type nothing and read as a dead keyboard.
    page.keyboard.press("c")
    expect(page.locator(".lf-general textarea")).to_be_focused()
    expect(page.locator(".lf-keyline")).not_to_contain_text("waiting on you")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(page.locator(".lf-keyline")).to_contain_text("waiting on you")
    page.keyboard.press("w")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{theirs}"]')).to_have_count(1)
    expect(page.locator(".lf-panel-head span")).to_have_text("Showing 1 of 2")
    expect(page.locator(".lf-needs")).to_have_attribute("aria-pressed", "true")

    # Answering the agent's comment takes it out of the reader's list and hands the
    # next word to the agent.
    reply = page.locator(f'.lf-thread[data-id="{theirs}"] textarea')
    reply.click()
    reply.type("Forty is plenty.")
    page.locator(f'.lf-thread[data-id="{theirs}"] .lf-thread-send').click()
    round_trip(page)
    expect(page.locator(".lf-needs")).to_have_text("Waiting on you")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(0)
    expect(page.locator(".lf-empty")).to_have_text("Nothing is waiting on you.")
    # The reader was standing in the thread that just left. Focus lands on the list
    # rather than falling to body, where the next Space would scroll the page behind
    # the panel instead of the list in front of them.
    expect(page.locator(".lf-threads")).to_be_focused()

    # Escape unwinds the narrowing before it closes the panel, from wherever the reader
    # is standing: a list that is not the whole conversation is a layer they put on.
    expect(page.locator(".lf-keyline")).to_contain_text("show all")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(2)
    expect(page.locator(f'.lf-thread[data-id="{mine}"]')).to_have_count(1)
    expect(page.locator(".lf-panel-head span")).to_have_text("Comments")
    assert errors == []
    page.close()


def test_an_agent_reply_says_when_the_reader_owes_an_answer(browser, serve):
    """An open thread and a request to its reader are different facts. A complete
    answer stays available for follow-up without entering the waiting list; a reply
    carrying an explicit prose ask enters it until the reader answers. A widget ask
    needs no duplicate flag: its own standing projection enters and leaves the list."""
    url = serve(PANEL_PAGE)
    answered = panel_comment(serve.page_dir, "Why forty?", {"section": "how-cap"})
    asked = panel_comment(serve.page_dir, "What remains?", {"section": "how-store"})
    conversation_model.cmd_reply(
        serve.page_dir,
        answered,
        "Forty is what the slowest supported device can hold.",
        None,
    )
    conversation_model.cmd_reply(
        serve.page_dir,
        asked,
        "One choice remains. Which store should own the result?",
        None,
        awaits=True,
    )
    page, errors = open_page(
        browser,
        url,
        init_script="""(() => {
          const counts = window.__replyListeners = {drafts: 0, flights: 0};
          const add = Document.prototype.addEventListener;
          Document.prototype.addEventListener = function(type, ...args) {
            if (this === document && type === "lf-drafts") counts.drafts += 1;
            if (this === document && type === "lf-reply-flight") counts.flights += 1;
            return add.call(this, type, ...args);
          };
          const define = customElements.define.bind(customElements);
          customElements.define = (name, ctor, options) => {
            if (name === "lf-options") {
              const connected = ctor.prototype.connectedCallback;
              ctor.prototype.connectedCallback = function() {
                if (this.id === "backend") {
                  const message = this.closest(".lf-msg");
                  window.__backendContext ??= {
                    message: Boolean(message),
                    thread: this.closest(".lf-thread")?.dataset.id ?? null,
                    saidAt: message?.querySelector("time")?.dateTime ?? null,
                  };
                }
                return connected?.call(this);
              };
            }
            return define(name, ctor, options);
          };
        })()""",
    )
    page.locator(".lf-comments").click()
    panel_settled(page)
    expect(page.locator(".lf-needs")).to_have_text("Waiting on you (1)")
    expect(page.locator(".lf-thread")).to_have_count(2)

    page.locator(".lf-needs").click()
    expect(page.locator(".lf-thread")).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{asked}"]')).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{answered}"]')).to_have_count(0)

    listeners = page.evaluate("() => ({...window.__replyListeners})")
    find = page.locator(".lf-find-box")
    for key in ("r", "e", "Backspace", "Backspace"):
        find.press(key)
    assert page.evaluate("() => ({...window.__replyListeners})") == listeners, (
        "reconciling a hidden thread registered another reply-box listener"
    )
    expect(find).to_have_value("")

    # The completed thread is absent under the narrowing. A later structured ask must
    # still be projected before the filter decides whether to admit that thread, or the
    # question can never render itself into the list that would discover it.
    widget_reply = conversation_model.cmd_reply(
        serve.page_dir,
        answered,
        "Choose the backend here.",
        '<lf-options id="backend" choose>'
        '<lf-option id="backend-sqlite"><strong>SQLite</strong></lf-option>'
        '<lf-option id="backend-postgres"><strong>Postgres</strong></lf-option>'
        "</lf-options>",
    )
    told(page)
    expect(page.locator(".lf-needs")).to_have_text("Waiting on you (2)")
    expect(page.locator(f'.lf-thread[data-id="{answered}"]')).to_have_count(1)
    assert page.evaluate("() => window.__backendContext") == {
        "message": True,
        "thread": answered,
        "saidAt": widget_reply["ts"],
    }

    page.locator("#backend-sqlite").click()
    round_trip(page)
    expect(page.locator(".lf-needs")).to_have_text("Waiting on you (1)")
    expect(page.locator(f'.lf-thread[data-id="{answered}"]')).to_have_count(0)

    reply = page.locator(f'.lf-thread[data-id="{asked}"] textarea')
    reply.fill("SQLite should own it.")
    page.locator(f'.lf-thread[data-id="{asked}"] .lf-thread-send').click()
    round_trip(page)
    expect(page.locator(".lf-needs")).to_have_text("Waiting on you")
    expect(page.locator(".lf-thread")).to_have_count(0)
    assert errors == []
    page.close()


def test_a_thread_the_agent_closed_names_who_closed_it(browser, serve):
    """Either side can close a thread and the reader watches only one of them happen.
    Their own press folds the thread under their hand and leaves the outcome on the
    control they pressed, so the disclosure it lands in needs to say nothing more. An
    agent's resolve arrives on a poll with no gesture behind it, and that thread says
    who closed it — in the row the control stood in, at the end it stood at."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=2))
    page.locator(".lf-comments").click()
    panel_settled(page)
    c1, c2 = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]

    events_model.append_event(
        serve.page_dir,
        {"kind": "resolve", "author": "claude", "agent": "Indexer", "parent": c1},
    )
    told(page)
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    expect(
        page.locator(f'.lf-details .lf-thread[data-id="{c1}"] .lf-resolved-by')
    ).to_have_text("✓ Resolved by Indexer")

    page.locator(f'.lf-thread[data-id="{c2}"] .lf-resolve').click()
    round_trip(page)
    # The disclosure holding the node is what says the fold is over, so the line's
    # absence is read from a thread that has arrived rather than one still on its way.
    expect(page.locator(f'.lf-details .lf-thread[data-id="{c2}"]')).to_have_count(1)
    expect(
        page.locator(f'.lf-details .lf-thread[data-id="{c2}"] .lf-resolved-by')
    ).to_have_count(0)
    assert errors == []
    page.close()


def test_a_resolved_thread_can_be_reopened(browser, serve):
    """Reopening is a logged transition: the thread returns to the open list with
    its reply and resolve controls, and the disclosure leaves when it is empty."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=18))
    page.locator(".lf-comments").click()
    panel_settled(page)
    comment = next(
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    )

    page.locator(f'.lf-thread[data-id="{comment}"] .lf-resolve').click()
    round_trip(page)
    # The round trip starts the fold; the disclosure holding the thread finishes it.
    expect(page.locator(f'.lf-details .lf-thread[data-id="{comment}"]')).to_have_count(
        1
    )
    page.locator(".lf-details summary").click()
    page.locator(f'.lf-details .lf-thread[data-id="{comment}"] .lf-reopen').click()
    round_trip(page)

    reopened = page.locator(f'.lf-threads > .lf-thread[data-id="{comment}"]')
    expect(reopened).to_be_in_viewport()
    expect(reopened).to_be_focused()
    expect(reopened.locator("textarea")).to_have_count(1)
    expect(reopened.locator(".lf-resolve")).to_have_count(1)
    expect(page.locator(".lf-details")).to_have_count(0)
    expect(page.locator(".lf-comments")).to_have_text("Comments (18)")
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "unresolve"
    assert errors == []
    page.close()


def test_a_late_reply_to_a_resolved_thread_stays_above_its_reopen_footer(
    browser, serve
):
    """New messages reconcile before the resolved thread's persistent actions."""
    url = serve(LONG_PAGE, comments=1)
    root = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    events_model.append_event(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": root["id"]}
    )
    page, errors = open_page(browser, url)
    page.locator(".lf-comments").click()
    page.locator(".lf-details summary").click()
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "revision": 1,
            "parent": root["id"],
            "text": "This arrived after resolution.",
        },
    )
    told(page)

    thread = page.locator(f'.lf-details .lf-thread[data-id="{root["id"]}"]')
    expect(thread.locator(":scope > .lf-msg")).to_have_count(2)
    assert thread.locator(":scope > *").last.evaluate(
        "node => node.classList.contains('lf-thread-actions')"
    ), "the late reply landed below Reopen"
    assert errors == []
    page.close()


def test_a_resolved_thread_gives_its_room_back_as_motion(browser, serve):
    """Resolving a thread empties its place in the list over a fifth of a second,
    not in the frame of the press.

    The node used to go the moment the log settled it: the ✓ Resolve the user had
    just pressed took itself off the page, and every thread under it arrived
    somewhere else with no path between the two — the same pair of failures the
    suggestion's decided slot was already fixed for, in the panel this time. So the
    thread stays where it stood, states on the pressed control what was done to it,
    and folds; the disclosure gets it when the fold is over.

    What the log says is true from that first frame regardless — Comments counts down
    and Resolved counts up while the pixels catch up — and a thread on its way out is
    out of the keys' reach from the same frame, so j/k and the g addresses walk what
    is left rather than a corpse that is about to go. Its own reply box gives up the
    address with them: the box under it has just taken that digit, and two boxes
    offering g c 1 is a key line promising a press that lands on one of them.

    Held at its first frame rather than sampled mid-flight, the way the suggestion's
    own fold is read: mid-flight is a race with the clock that passes on a fast
    machine whatever the code does, where the held frame is the fold's opening state
    for as long as the assertions need it."""
    page, errors = open_page(
        browser, serve(LONG_PAGE, comments=3), init_script=HOLD_MOTION
    )
    page.locator(".lf-comments").click()
    panel_settled(page)
    c1, c2, c3 = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    first = page.locator(f'.lf-thread[data-id="{c1}"]').bounding_box()
    stood = page.locator(f'.lf-thread[data-id="{c2}"]').bounding_box()
    # The room the first thread holds, the gap under it included, which is what its
    # neighbour rises by once the fold has given it back.
    room = stood["y"] - first["y"]
    action_edge = page.locator(
        f'.lf-thread[data-id="{c1}"] .lf-thread-actions'
    ).evaluate("node => node.getBoundingClientRect().right")

    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    round_trip(page)
    expect(page.locator(f'[data-id="{c1}"] .lf-resolve')).to_have_text("✓ Resolved")
    expect(page.locator(f'[data-id="{c1}"] .lf-thread-send')).to_be_hidden()
    resolved_edge = page.locator(f'[data-id="{c1}"] .lf-resolve').evaluate(
        "node => node.getBoundingClientRect().right"
    )
    assert resolved_edge == pytest.approx(action_edge, abs=1), (
        "the held outcome left the action row's right edge"
    )
    held = page.evaluate(LIST_STATE)
    assert held["standing"] == [c1, c2, c3], (
        "the resolved thread gave up its place in the frame it was resolved in, so "
        f"the list stood as {held['standing']} with the fold still to play"
    )
    assert held["walkable"] == [c2, c3], (
        "a thread on its way out is still walkable by j/k and addressable by g, so a "
        f"key can land on room that is about to go: the list offered {held['walkable']}"
    )
    assert page.evaluate("() => window.__lfHeld.length") == 1, (
        "the room went back without motion carrying it"
    )
    now = page.locator(f'.lf-thread[data-id="{c2}"]').bounding_box()
    assert now == stood, (
        f"the thread below stood at {stood} and reads {now} in the frame the outcome "
        "was stated, so the fold started from somewhere other than the box the reader "
        "was looking at"
    )
    expect(page.locator(".lf-comments")).to_have_text("Comments (2)")
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    # The address the fold gave up, read where a reader reads it.
    expect(page.locator(f'[data-id="{c1}"] textarea')).to_have_attribute(
        "placeholder", "Reply"
    )
    expect(page.locator(f'.lf-thread[data-id="{c2}"] textarea')).to_have_attribute(
        "placeholder", "Reply · g c 1"
    )

    # Half way down, the outcome is still on screen. A fold from the bottom takes the
    # thread's last line first, and the actions row is that line, so a word left in
    # flow is legible for the frame before the box swallows it and no longer — which
    # is a flash, not a statement. It rides the closing edge instead, and what says so
    # is its box being inside the box the fold has left.
    page.evaluate("() => window.__lfHeld.forEach((m) => (m.currentTime = 110))")
    clip, says = page.evaluate(
        """(id) => {
          const going = document.querySelector(`[data-id="${id}"]`);
          const row = going.querySelector(".lf-thread-actions");
          return [going.getBoundingClientRect(), row.getBoundingClientRect()];
        }""",
        c1,
    )
    assert says["top"] < clip["bottom"] and clip["top"] < says["bottom"], (
        f"the outcome sat at {says['top']:.0f}–{says['bottom']:.0f} with the fold "
        f"clipped to {clip['top']:.0f}–{clip['bottom']:.0f}, so the word the press "
        "left was already under the clip half way through"
    )

    # And the far end: the thread lands in the disclosure, once, and the room it held
    # has gone back to the threads under it.
    page.evaluate("() => window.__lfHeld.forEach((m) => m.finish())")
    expect(page.locator(f'.lf-details .lf-thread[data-id="{c1}"]')).to_have_count(1)
    expect(page.locator(f'[data-id="{c1}"]')).to_have_count(1)
    risen = page.locator(f'.lf-thread[data-id="{c2}"]').bounding_box()
    assert stood["y"] - risen["y"] == pytest.approx(room, abs=1), (
        f"the thread below rose {stood['y'] - risen['y']:.1f}px where the resolved "
        f"thread held {room:.1f}px"
    )
    assert errors == []
    page.close()


def test_the_fold_never_paints_a_frame_that_undoes_the_last(browser, serve):
    """A fold is a sequence, and every other check here reads a state.

    The gap that leaves is a frame that puts back what the frames before it took:
    a Web Animations effect stops applying at the end of its own interval, so
    anything holding the collapsed box open — a removal that slips a frame past
    the finish, a fill the helper stopped stating — paints the whole thread back
    at full height and full opacity for a frame before it goes. Held frames can't
    see it; each one is correct on its own. This watches the real fold at real
    speed and asks the only question a sequence can be wrong about, which is
    whether any frame is taller than the one before it.

    It is also what the first recording of this fold got wrong, in the other
    direction: sampled at exactly the duration, an animation is already past its
    own interval and reads as the element it never was."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=3))
    page.locator(".lf-comments").click()
    panel_settled(page)
    c1 = next(
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    )
    # Watching from before the press, so the frames it holds still are in the record
    # alongside the ones that move.
    page.evaluate(FRAME_BY_FRAME, f'.lf-threads > [data-id="{c1}"]')
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    # The node leaving the list is the fold's end and the browser's own statement, so
    # the wait is that rather than the sampler's flag: what runs in the page is the
    # record, which nothing out here can take, and not the wait, which is already
    # answered from outside.
    page.wait_for_selector(f'.lf-threads > [data-id="{c1}"]', state="detached")
    seen = page.evaluate("() => window.__seen")

    grew = [
        (i, seen[i - 1], seen[i]) for i in range(1, len(seen)) if seen[i] > seen[i - 1]
    ]
    assert not grew, (
        "the fold painted a frame taller than the one before it: "
        + ", ".join(f"frame {i} went {was:.0f}px → {now:.0f}px" for i, was, now in grew)
    )
    # And it folded rather than vanishing between two samples, which would pass the
    # line above by having nothing to compare.
    assert any(0 < h < seen[0] for h in seen), (
        f"no frame caught the fold part way down (heights: {seen}), so a thread that "
        "went in one frame would read the same as one that folded"
    )
    assert errors == []
    page.close()


def test_a_reader_who_asked_for_less_motion_gets_the_resolved_thread_at_once(
    browser, serve
):
    """The fold is a courtesy to the eye, and an eye that asked for stillness is owed
    the outcome instead — the bargain the suggestion's own fold already makes, asked
    again here because the thread's is the path with somewhere to be left stranded:
    the node stays in the list until its fold ends, so a fold that never starts is a
    node that has to reach the disclosure by the same render that declined to play
    one."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        color_scheme="light",
        reduced_motion="reduce",
    )
    try:
        page, errors = open_page(
            browser,
            serve(LONG_PAGE, comments=2),
            context=context,
            init_script=HOLD_MOTION,
        )
        page.locator(".lf-comments").click()
        panel_settled(page)
        c1, c2 = [
            e["id"]
            for e in events_model.read_events(serve.page_dir)
            if e["kind"] == "comment"
        ]
        page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
        expect(page.locator(f'.lf-details .lf-thread[data-id="{c1}"]')).to_have_count(1)
        assert page.evaluate("() => window.__lfHeld.length") == 0, (
            "a reader who asked for less motion was given a fold to sit through"
        )
        assert page.evaluate(LIST_STATE) == {
            "standing": [c2],
            "walkable": [c2],
        }, "the thread that declined its fold was left standing in the list"
        assert errors == []
    finally:
        context.close()


def test_a_thread_reopened_mid_fold_folds_again_when_it_settles(browser, serve):
    """A fold is a claim about a node standing in the list, and the reader can take
    that node out from under it: `z` reopens the thread the fold is carrying away, and
    the render that puts the thread back drops the folding node. Held past that, the
    record would hand the spent node back the next time the thread settled — the fold
    would be over before it started, and what stood in the list for its duration would
    be the thread as it read before it reopened, one message short.

    Reachable in the product, not only here: resolve, `z` and resolve are three round
    trips through the real server in 78ms measured, against a fold of 220ms, so the
    window is the reader's typing speed and nothing else. Holding the motion is what
    makes it a state instead of a race — a paused animation never settles `finished`,
    so the record stays exactly as long as the assertions need it."""
    page, errors = open_page(
        browser, serve(LONG_PAGE, comments=3), init_script=HOLD_MOTION
    )
    page.locator(".lf-comments").click()
    panel_settled(page)
    c1 = next(
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    )
    thread = page.locator(f'.lf-threads > .lf-thread[data-id="{c1}"]')
    going = page.locator(f'.lf-threads > .lf-going[data-id="{c1}"]')

    before = page.evaluate("window.__lfHeld.length")
    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    round_trip(page)
    expect(going).to_have_count(1)
    folds = page.evaluate("window.__lfHeld.length")
    assert folds == before + 1, "the press drew something other than its one fold"

    undo(page)
    expect(thread).to_have_count(1)
    expect(going).to_have_count(0)
    # News the thread takes while it is open again, which the node the first fold was
    # carrying away has never held — so what folds the second time says which node it is.
    reply = events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Claude",
            "revision": 1,
            "parent": c1,
            "text": "Reopened, and answered.",
        },
    )
    told(page)
    expect(thread.locator(".lf-msg")).to_have_count(2)

    page.locator(f'.lf-thread[data-id="{c1}"] .lf-resolve').click()
    round_trip(page)
    expect(going.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_have_count(1)
    assert page.evaluate("window.__lfHeld.length") > folds, (
        "the second settlement drew no fold of its own"
    )

    # And the first fold runs out, which is the other half of two folds standing at
    # once: its node left the list when the thread reopened, and the record it must
    # not clear on its way is the live fold's. Cleared, the thread is pulled out of
    # the list in the middle of the motion carrying it away.
    page.evaluate(
        "async (i) => { const m = window.__lfHeld[i];"
        " m.play(); m.currentTime = m.effect.getComputedTiming().duration;"
        " await m.finished; }",
        before,
    )
    expect(going.locator(f'.lf-msg[data-mid="{reply["id"]}"]')).to_have_count(1)
    assert errors == []
    page.close()


def test_a_coined_class_cannot_reach_the_chromes_rules(browser, serve):
    """The chrome's private rules live in one @scope block rooted at the runtime's
    own container, so whatever name a widget or a page coins, it matches none of
    them: lf-tabs once marked itself lf-live — the chrome's name for its
    visually-hidden live region — and every tabbed page clipped to a pixel. An
    element in the page wearing every scoped class at once must render exactly as
    its unclassed twin, and the classes styled at document level must be exactly
    the shared vocabulary a widget wears on purpose."""
    page, _ = open_page(
        browser,
        serve(leaf_page("t", "<h1>t</h1><section id=s><p>words</p></section>")),
    )
    surface = page.evaluate("""() => {
        const sheet = [...document.styleSheets].find(
            s => { try { return [...s.cssRules].some(r => r instanceof CSSScopeRule); }
                   catch { return false; } });
        const classes = sel => [...(sel || "").matchAll(/\\.([A-Za-z0-9_-]+)/g)].map(m => m[1]);
        const scoped = new Set(), global_ = new Set();
        const collect = (rules, into) => { for (const r of rules) {
            if (r instanceof CSSScopeRule) collect(r.cssRules, scoped);
            else if (r.selectorText) classes(r.selectorText).forEach(c => into.add(c));
            else if (r.cssRules) collect(r.cssRules, into); } };
        collect(sheet.cssRules, global_);
        const probe = document.createElement("div"), plain = document.createElement("div");
        // Minus the shared vocabulary: a word document level dresses on purpose
        // (lf-address, worn by the chord's own layer and by an option's corner alike)
        // is named by the scoped rule that says when to paint it, and it would answer
        // this question with the reach it was given rather than with a leak.
        probe.className = [...scoped].filter(c => !global_.has(c)).join(" ");
        probe.textContent = plain.textContent = "probe";
        document.getElementById("s").append(plain, probe);
        const cs = el => { const c = getComputedStyle(el), out = {};
                           for (const p of c) out[p] = c.getPropertyValue(p); return out; };
        const a = cs(probe), b = cs(plain);
        return { scoped: [...scoped], global: [...global_],
                 moved: Object.keys(a).filter(p => a[p] !== b[p]) };
    }""")
    assert "lf-live" in surface["scoped"] and len(surface["scoped"]) > 20, (
        "the @scope block is missing or nearly empty — the chrome has lost its rules"
    )
    assert surface["moved"] == [], (
        f"scoped chrome rules reached an element in the page: {surface['moved']}"
    )
    # Every one of these is worn by something the runtime puts inside the page rather than
    # inside its own container — or, for lf-address, on both sides of that line at once,
    # which is the same reason: a scoped rule cannot reach the copy in the page. Except the
    # last, which is worn by nothing and is here for the other half of the sentence. lf-copy is the medium `version export` marks on the root, and the runtime
    # names it under a negation to withhold the live page's scroller from a file that has
    # no panel to scroll beside; a rule that dresses no element can leak onto none, and
    # what the pin is for is the day one of these stops being either kind.
    assert {c for c in surface["global"] if c.startswith("lf-")} == {
        "lf-copy",
        "lf-ui",
        # A native label can pass through an intermediate focus target. These project
        # the held control's focus until activation settles.
        "lf-focus",
        "lf-focus-visible",
        "lf-btn",
        "lf-pill",
        "lf-address",
        "lf-over-mark",
        "lf-mark-el",
        "lf-mark-hover",  # the same element mark, for the one the pointer indicates
        "lf-mark-here",  # the same element mark, for the comment the reader is in
        "lf-pending",
        "lf-ins-block",
        "lf-mark-note",
        "lf-aiming",
        "lf-design",  # design mode's arming, on body beside the aim's, for the cursor
        "lf-over-item",
        "lf-quiet",
        # A standing reaction's paint on the page: the element outline, the seat in the
        # margin and the glyph in it, and the wash a copy carries as a <mark>.
        "lf-react-el",
        "lf-reacts",
        "lf-react-mark",
        "lf-react",
        "lf-docked",  # a seat's measured fallback, the word a suggestion row docks under
        # Visual reactions add a quiet keyboard proxy beside the authored target and
        # an outline on the target while its shared action bar is standing.
        "lf-visual-actions",
        "lf-visual-action",
        "lf-action-target",
    }, (
        "the document-level class surface changed: widen the shared vocabulary on purpose"
    )
    page.close()


# A page long enough to hold a reading position worth losing, and a change to decide
# in each document, so every reading below has the same widget in both places.
REPLY_TRAVEL_PAGE = leaf_page(
    "travel",
    "<h1 id='tv-h'>Session store</h1>"
    + "".join(
        f"<p id='tv-p{n}'>Paragraph {n}. "
        + "Words enough to wrap the column. " * 8
        + "</p>"
        for n in range(40)
    ),
)

PAGE_CHANGE = (
    '<lf-suggestion id="tv-doc-sug">'
    '<lf-old><p id="tv-doc-old">Sessions live five minutes.</p></lf-old>'
    "<lf-new><p>Sessions live ninety seconds.</p></lf-new>"
    "</lf-suggestion>"
)
CHANGE_HEAD = "<h1 id='dc-h'>Session store</h1>"
CHANGE_PAGE = leaf_page("doc-change", CHANGE_HEAD + PAGE_CHANGE)
# The same page with the change taken out of it, for the arm that carries the change
# in a message instead: the two must differ in which document holds it and in nothing
# else.
BARE_PAGE = leaf_page("doc-change", CHANGE_HEAD)
REPLY_CHANGE = PAGE_CHANGE.replace("tv-doc-", "tv-msg-")

BOTH_BOXES = """() => ({
  page: document.body.scrollTop,
  panel: document.querySelector('.lf-threads').scrollTop,
})"""


def seed_reply(d, markup, anchor_id, chatter=0, after=0):
    """A conversation whose reply carries `markup`, with a thread anchored on it.

    `chatter` is what makes the panel a scroller of its own: a travel that lands by
    accident when the whole list already fits proves nothing about which box moved.
    `after` is what makes the middle of that list reachable — a widget in the last
    message can only be brought to the end of the scroll range, which `scrollIntoView`
    reaches on its own, so a centring assertion over one asserts nothing.
    """
    for n in range(chatter):
        events_model.append_event(
            d,
            {
                "kind": "comment",
                "id": f"tv-pad{n}",
                "author": "user",
                "revision": 1,
                "text": f"Aside {n}. " + "Long enough to wrap in the panel. " * 4,
            },
        )
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "tv-asked",
            "author": "user",
            "revision": 1,
            "text": "Which store?",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "tv-asked",
            "revision": 1,
            "text": "Depends what you want to keep:",
            "markup": markup,
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "tv-on-it",
            "author": "user",
            "revision": 1,
            "text": "Redis, and say why in the patch.",
            "anchor": {"section": anchor_id},
        },
    )
    for n in range(after):
        events_model.append_event(
            d,
            {
                "kind": "comment",
                "id": f"tv-later{n}",
                "author": "user",
                "revision": 1,
                "text": f"Later {n}. " + "Long enough to wrap in the panel. " * 4,
            },
        )


def test_a_thread_on_a_widget_in_a_reply_travels_in_the_panel_that_holds_it(
    browser, serve
):
    """Pressing a thread's quote label moves the reader to what it is about — in the
    box that box is in.

    An element anchor can now name a widget an agent sent, and such a widget is
    scrolled by the panel's own list and by nothing else. The travel was written with
    the document's scroller in it twice, once for the banner clearance it reads and
    once for the jump it makes, so the press spent its whole arithmetic on the page
    behind the panel: the reader lost their place in the document over a thread about
    something that was never in it. The panel arrived anyway, which is what made it
    quiet — the platform's own scrollIntoView moves every ancestor box, so the widget
    came into view, nudged to the nearest edge rather than centred, while the document
    slid under it.

    The document is the control: the same press on a thread about a paragraph must
    still move the page, or this only says that nothing scrolls."""
    url = serve(REPLY_TRAVEL_PAGE)
    seed_reply(
        serve.page_dir,
        '<lf-options id="tv-ask" choose label="Which store should I write up?">'
        '<lf-option id="tv-redis">Redis</lf-option>'
        '<lf-option id="tv-cookie">A signed cookie</lf-option>'
        "</lf-options>",
        "tv-ask",
        chatter=10,
        after=10,
    )
    # A second thread, on the document, whose travel is the one that must still move
    # the page. Written after the first so the panel holds both.
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "tv-on-page",
            "author": "user",
            "revision": 1,
            "text": "This one is about the page.",
            "anchor": {"section": "tv-p30"},
        },
    )
    # Reduced motion, so both travels jump and every reading below is taken straight
    # after the press. A glide would leave the document's own scroll still running
    # while the assertion that it never started reads its first frame.
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        color_scheme="light",
        reduced_motion="reduce",
    )
    page, errors = open_page(browser, url, context=context)
    page.locator(".lf-comments").click()
    panel_settled(page)

    page.evaluate("() => { document.body.scrollTop = 1200; }")
    page.evaluate("() => { document.querySelector('.lf-threads').scrollTop = 0; }")

    # Where the travel says it is taking the widget: centred in the list, or as near
    # as the list can come — a widget in the last message is past the middle of what
    # the box can show, and the end of the scroll range is the whole of the answer
    # there. The same arithmetic the travel uses, so this asserts where it went and
    # not merely that something moved.
    WHERE = """() => {
      const box = document.querySelector('.lf-threads');
      const view = box.getBoundingClientRect();
      const el = document.getElementById('tv-ask').getBoundingClientRect();
      const clear = parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
      return { at: el.top - view.top,
               want: Math.max((view.height - el.height) / 2, clear),
               atEnd: box.scrollTop >= box.scrollHeight - box.clientHeight - 1 };
    }"""
    thread = page.locator('.lf-thread[data-id="tv-on-it"] .lf-quote')
    thread.scroll_into_view_if_needed()
    before = page.evaluate(BOTH_BOXES)
    thread.click()
    # The exact destination is the completion fact: the target first comes into view,
    # then the region-local correction centres it.
    try:
        page.wait_for_function(
            f"() => {{ const w = ({WHERE})(); return Math.abs(w.at - w.want) < 2; }}"
        )
    except PlaywrightTimeout:
        seen = page.evaluate(WHERE)
        raise AssertionError(
            f"the widget stopped {seen['at']:.0f}px into the list where centring it "
            f"wanted {seen['want']:.0f}px — the travel never reached the box the "
            "widget is in"
        ) from None
    landed = page.evaluate(WHERE)
    after = page.evaluate(BOTH_BOXES)
    assert after["page"] == before["page"], (
        f"a thread about a widget in the panel moved the document "
        f"{before['page']}px → {after['page']}px; the reader's place in the page is "
        "not this thread's to spend"
    )
    assert after["panel"] != before["panel"], (
        "the panel did not move at all, so the page holding still says nothing"
    )
    assert not landed["atEnd"], (
        "the list is at the end of its range, which scrollIntoView reaches on its own "
        "— the seed must leave messages below the one carrying the widget, or the "
        "centring below is carried by the clamp"
    )
    assert abs(landed["at"] - landed["want"]) < 2, (
        f"the widget stopped {landed['at']:.0f}px into the list where centring it "
        f"wanted {landed['want']:.0f}px — brought into view by the platform rather "
        "than travelled to"
    )

    # The control: the page's own thread still moves the page.
    page.locator('.lf-thread[data-id="tv-on-page"] .lf-quote').click()
    page.wait_for_function(f"() => document.body.scrollTop !== {before['page']}")
    assert errors == []
    page.close()


def test_a_thread_about_a_fixed_part_of_the_layer_moves_neither_box(browser, serve):
    """A part that stands over both documents is in neither, and nothing travels to it.

    Design mode lets a reader comment on the layer's own parts, and several of them are
    `position: fixed` — the key line, the banner, the composer. Such a part is on screen
    already, and it is in no scroller's flow, so its rect answers to the viewport rather
    than to either region's scroll. `scrollerFor` says which of the two regions an
    element belongs to, which is the right question for a widget in a message and no
    question at all for one of these. Spent on it, the arithmetic reads a fixed rect as
    though it were a place in a scroller and moves that scroller by a number meaning
    nothing in it: measured, pressing a thread about the key line took the document
    370px away from where the reader had it, at every starting position.

    The control is a thread about the page, which must still travel."""
    url = serve(REPLY_TRAVEL_PAGE)
    d = serve.page_dir
    for n in range(14):
        events_model.append_event(
            d,
            {
                "kind": "comment",
                "id": f"fx-pad{n}",
                "author": "user",
                "revision": 1,
                "text": f"Aside {n}. " + "Long enough to wrap in the panel. " * 4,
            },
        )
    # The shape design mode writes about the layer: `about` says which, and the anchor
    # names the part the runtime gave an id.
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "fx-on-layer",
            "author": "user",
            "revision": 1,
            "about": "layer",
            "text": "The key line reads dim against the wash.",
            "anchor": {"section": "lf-keyline"},
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "fx-on-page",
            "author": "user",
            "revision": 1,
            "text": "And this one is about the page.",
            "anchor": {"section": "tv-p30"},
        },
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        color_scheme="light",
        reduced_motion="reduce",
    )
    page, errors = open_page(browser, url, context=context)
    page.locator(".lf-comments").click()
    panel_settled(page)
    # The key line only draws while it has something to say, which is what a held key
    # gives it. Held down, so the part is on screen for the press below.
    page.keyboard.down("Alt")
    expect(page.locator(".lf-keyline")).to_be_visible()

    page.evaluate("() => { document.body.scrollTop = 1200; }")
    # Where the reader is standing when they press: the thread on screen, which is
    # also what the driver's own scroll-into-view would arrange. Read after it, so the
    # baseline is the page as the press finds it rather than as the test left it.
    thread = page.locator('.lf-thread[data-id="fx-on-layer"] .lf-quote')
    thread.scroll_into_view_if_needed()
    before = page.evaluate(BOTH_BOXES)
    seen = """() => {
      const t = document.querySelector('.lf-thread[data-id="fx-on-layer"]');
      const view = document.querySelector('.lf-threads').getBoundingClientRect();
      return t ? t.getBoundingClientRect().top - view.top : null;
    }"""
    stood = page.evaluate(seen)
    thread.click()
    # Reduced motion makes both region-local scroll operations instant, so the read
    # directly after the press is the whole travel.
    after = page.evaluate(BOTH_BOXES)
    page.keyboard.up("Alt")

    assert after == before, (
        f"a thread about a fixed part of the layer moved something: {before} -> {after}"
    )
    assert page.evaluate(seen) == stood, (
        "the press moved the thread the reader pressed, which is the surface they were "
        "looking at"
    )

    # The control: a thread about the page still travels.
    page.locator('.lf-thread[data-id="fx-on-page"] .lf-quote').click()
    assert page.evaluate(BOTH_BOXES)["page"] != before["page"], (
        "a thread about a paragraph no longer moves the document, so the stillness "
        "above says only that nothing scrolls"
    )
    assert errors == []
    page.close()


def test_a_settlement_in_a_reply_leaves_its_own_anchor_on_the_page(browser, serve):
    """A decided change keeps whatever of itself is still showing, wherever it stands.

    `settledAway` asks whether a decision emptied an element: every child now a retired
    slot or the runtime's own apparatus, with no words of its own left. Asked about the
    page that test is right; asked about a change an agent sent in a reply it was asked
    the wrong way round, because the panel holding it is itself the runtime's apparatus
    and so every child of it answered yes. One accepted slot then emptied a change whose
    other half was on screen: the anchor a reader had put on it stopped resolving, the
    outline came off, and the thread stood detached beside the words it was about.

    The same change on the page is the control, and the two must agree."""
    for where, markup, wid in (
        ("the page", CHANGE_PAGE, "tv-doc-sug"),
        ("a reply", BARE_PAGE, "tv-msg-sug"),
    ):
        url = serve(markup)
        d = serve.page_dir
        if wid.startswith("tv-msg"):
            seed_reply(d, REPLY_CHANGE, wid)
        else:
            events_model.append_event(
                d,
                {
                    "kind": "comment",
                    "id": "tv-on-it",
                    "author": "user",
                    "revision": 1,
                    "text": "Why ninety?",
                    "anchor": {"section": wid},
                },
            )
        events_model.append_event(
            d,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": wid,
                "action": "accept",
                "detail": {},
            },
        )
        page, errors = open_page(browser, url)
        resized(page, 1280, 900)
        page.locator(".lf-comments").click()
        panel_settled(page)
        settled = page.evaluate(
            """(wid) => {
                 const el = document.getElementById(wid);
                 const quote = document.querySelector('.lf-thread[data-id="tv-on-it"] .lf-quote');
                 return { state: el?.dataset.lfState,
                          retired: [...(el?.querySelectorAll('[data-lf-retired]') ?? [])].length,
                          marked: Boolean(el?.classList.contains('lf-mark-el')),
                          detached: quote?.classList.contains('detached') };
               }""",
            wid,
        )
        assert settled["state"] == "accept" and settled["retired"] == 1, (
            f"{where}: the change did not settle, so nothing here is being read "
            f"({settled})"
        )
        assert not settled["detached"] and settled["marked"], (
            f"{where}: the accepted change took its own anchor off the page "
            f"({settled}) — its other half is still showing"
        )
        assert errors == []
        page.close()


def test_a_mark_in_the_layer_promises_no_press_the_layer_will_not_take(browser, serve):
    """An outline in the chrome says which element, and stops there.

    An element anchor wears its outline wherever its element stands, the layer's own
    parts included — that is what lets a design comment about the banner point at the
    banner. What the outline may not do there is offer the hand: `markAt` refuses a
    press inside the chrome on purpose, because what the chrome holds keeps its own
    presses. The Comments button opens the panel and an option takes a pick; neither
    of them opens a thread. So the pointer stood over a marked question an agent had
    asked, promising a click nothing took.

    The page's own mark is the control, and it keeps the hand it has always had."""
    url = serve(REPLY_TRAVEL_PAGE)
    seed_reply(
        serve.page_dir,
        '<lf-options id="tv-ask" choose label="Which store should I write up?">'
        '<lf-option id="tv-redis">Redis</lf-option>'
        "</lf-options>",
        "tv-ask",
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "tv-on-page",
            "author": "user",
            "revision": 1,
            "text": "About the page.",
            "anchor": {"section": "tv-p3"},
        },
    )
    page, errors = open_page(browser, url)
    resized(page, 1280, 900)
    page.locator(".lf-comments").click()
    panel_settled(page)

    marks = page.evaluate(
        """() => [...document.querySelectorAll('.lf-mark-el')].map((el) => ({
             id: el.id, chrome: Boolean(el.closest('.lf-chrome')),
             cursor: getComputedStyle(el).cursor,
           }))"""
    )
    inside = [m for m in marks if m["chrome"]]
    outside = [m for m in marks if not m["chrome"]]
    assert inside and outside, (
        f"this needs a mark in each document to compare; got {marks}"
    )
    assert all(m["cursor"] == "pointer" for m in outside), (
        f"the page's own mark lost its hand, so the reading below is about nothing: "
        f"{outside}"
    )
    assert all(m["cursor"] != "pointer" for m in inside), (
        f"a mark in the layer offers the hand and no press is taken there: {inside}"
    )
    # And the other half of the sentence, since a cursor is only a promise about a
    # press: the press itself, on the marked widget's own words, reaching no thread.
    opened = page.evaluate(
        "() => document.querySelector('.lf-thread[data-id=\"tv-on-it\"]')?.className"
    )
    page.locator("#tv-ask").click(position={"x": 4, "y": 4})
    assert (
        page.evaluate(
            "() => document.querySelector('.lf-thread[data-id=\"tv-on-it\"]')"
            "?.className"
        )
        == opened
    ), "a press on a mark in the layer reached its thread after all"
    assert errors == []
    page.close()


def test_a_control_in_a_reply_holds_its_room_and_leaves_the_page_s_rail_alone(
    browser, serve
):
    """A change sent in a reply measures itself when it is drawn, and states nothing
    about the page's margin.

    Two numbers come off a suggestion's row of controls at upgrade: each control's
    floor, so the line a press is made on holds still when "Accept" becomes
    "Accepted", and — once, for the whole page — the rail the document leaves at its
    right edge for those rows to stand in. Both were taken off a row inside a comment
    panel nobody had opened, where the box is zero: the controls floored at nothing,
    and the page's rail was stated as bare margin and never restated, by a row that is
    not in the page's margin at all.

    The page's own change is the control for the first number and the author of the
    second."""
    reply_url = serve(REPLY_TRAVEL_PAGE)
    seed_reply(serve.page_dir, REPLY_CHANGE, "tv-msg-sug")
    page, errors = open_page(browser, reply_url)
    resized(page, 1280, 900)

    rail = "() => getComputedStyle(document.documentElement).getPropertyValue('--rail')"
    assert page.evaluate(rail).strip() == "", (
        "a row standing in the panel stated the page's rail; the page has no change "
        "of its own and wants no margin for one"
    )
    page.locator(".lf-comments").click()
    panel_settled(page)
    # Again now the row has a box: the guard's whole subject is a row that measures,
    # and read only while the panel was shut this said nothing about it.
    assert page.evaluate(rail).strip() == "", (
        "a row standing in the panel stated the page's rail once it had a box of "
        "its own to state it from"
    )
    floors = (
        "() => [...document.querySelectorAll('.lf-sug-actions [role=button]')]"
        ".map((b) => b.style.minWidth)"
    )
    in_reply = page.evaluate(floors)
    assert in_reply and all(f for f in in_reply), (
        f"a control in a reply holds no room for the word its press writes: {in_reply}"
    )
    assert errors == []
    page.close()

    # The same controls on the page, whose numbers these have to be.
    page, errors = open_page(browser, serve(CHANGE_PAGE))
    resized(page, 1280, 900)
    on_page = page.evaluate(floors)
    assert in_reply == on_page, (
        f"the same control measures {in_reply} in a reply and {on_page} on the page"
    )
    assert page.evaluate(rail).strip(), (
        "the page's own row states no rail, so the absence read above says nothing"
    )
    assert errors == []
    page.close()


def test_a_boxless_widget_in_a_reply_still_shows_the_parts_it_paints(
    browser, serve, tmp_path, monkeypatch
):
    """A wrapper that generates no box shows as what its contents paint — in either
    document.

    `shownParts` falls back to an element's children when the element itself has no
    box, which is what a mark hangs on and what an ask's ring hangs on. It kept the
    runtime's own apparatus out of that fallback by asking whether each child was
    under the runtime's chrome, and a widget an agent sent in a reply is: the panel
    over it answers for every child, so the fallback filtered all of them away and the
    widget showed as nothing at all. Bounded at the widget, the panel above it is no
    longer its own apparatus and the parts come back.

    `display: contents` on a widget is a project's line to write — the shipped
    vocabulary has none today, and `shownParts` exists because any layer can — so a
    project theme is what puts one here. The page's own copy is the control."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".leaf").mkdir(exist_ok=True)
    (tmp_path / ".leaf" / "theme.css").write_text(
        "/* a project styling a wrapper away, which is any layer's to do */\n"
        "lf-options { display: contents }\n"
    )
    url = serve(REPLY_TRAVEL_PAGE)
    # A group reporting rather than asking: the joined control the layer draws for
    # `choose` states its own display at a weight a project's bare tag rule does not
    # reach, and the subject here is a boxless wrapper rather than a cascade fight.
    seed_reply(
        serve.page_dir,
        '<lf-options id="tv-ask">'
        '<lf-option id="tv-redis" chosen>Redis</lf-option>'
        "</lf-options>",
        "tv-ask",
    )
    page, errors = open_page(browser, url)
    resized(page, 1280, 900)
    page.locator(".lf-comments").click()
    panel_settled(page)
    parts = page.evaluate(
        """async () => {
             const { shownParts } = await import('/runtime/widget-api.js');
             const el = document.getElementById('tv-ask');
             return { boxless: el.getBoundingClientRect().height === 0,
                      display: getComputedStyle(el).display,
                      parts: shownParts(el).map((p) => p.id || p.localName) };
           }"""
    )
    assert parts["boxless"], (
        f"the widget draws as {parts['display']!r}, so it has a box of its own and "
        "the fallback below was never reached — the project layer's rule lost to one "
        "the shipped theme states at a weight a bare tag selector cannot reach"
    )
    assert parts["parts"], (
        "a widget an agent sent shows as nothing: no box of its own, and every part "
        "its contents paint read as the panel's apparatus"
    )
    assert errors == []
    page.close()


def test_a_panel_reads_a_log_that_lost_the_message_a_reply_answers(browser, serve):
    """The browser walks the same relation as `build_threads`, and tore the same way.

    A crash tears one line and `read_events` keeps reading past it, so the events the
    server hands the browser can hold a reply whose message is gone. The panel is built
    by walking replies onto their parents, and the walk threw where the parent was
    missing — taking down not the thread but the whole reconcile, on a page whose log
    had already been read successfully by the side that wrote it."""
    url = serve(REPLY_TRAVEL_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "tv-lost",
            "author": "user",
            "revision": 1,
            "text": "the question nobody can read any more",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "id": "tv-kept",
            "author": "claude",
            "parent": "tv-lost",
            "revision": 1,
            "text": "the answer that survived it",
        },
    )
    log = d / "comments.jsonl"
    lines = log.read_text(encoding="utf-8").split("\n")
    torn = next(i for i, line in enumerate(lines) if '"id": "tv-lost"' in line)
    lines[torn] = lines[torn][: len(lines[torn]) // 2]
    log.write_text("\n".join(lines), encoding="utf-8")

    page, errors = open_page(browser, url)
    resized(page, 1280, 900)
    page.locator(".lf-comments").click()
    panel_settled(page)
    expect(page.locator(".lf-thread")).to_have_count(1)
    expect(page.locator(".lf-thread")).to_contain_text("the answer that survived it")
    assert errors == []
    page.close()


def test_no_ring_the_panel_draws_on_a_walk_down_its_list_is_cut_or_covered(
    browser, serve
):
    """Where the reader is standing has to be visible from wherever they walked to it,
    and the two ways it stops being visible are geometry rather than anything about the
    control: a scroll region that never said how much of its own edge it cannot land on,
    and a neighbour painting over the pixels the ring is in. Both had the panel's thread
    list, in both directions — walking down cut the ring at the bottom, walking up cut it
    at the top and slid it under the find row, and the first thread of every run had its
    top edge painted over by the heading above it, which is what a reader sees as a card
    with three sides.

    So this walks the list the way a reader does and asks the invariant at every landing,
    rather than naming the collisions one at a time. A rule stated once is a rule a new
    control inherits; a list of known collisions is a thing to keep adding to.

    Reduced motion, so a landing is a jump: what is asserted is where a walk ends, and
    the runtime reads the preference at load to decide between a glide and a jump."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    # A run per section and enough threads to make the list scroll, which is the whole
    # of what the cut half needs: a list that fits in the panel has no edge to fall off.
    for i in range(4):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})
        panel_comment(d, f"About the whole page, {i}.")

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    try:
        page, errors = open_page(browser, url, context=context)
        page.locator(".lf-comments").click()
        panel_settled(page)
        threads = page.locator(".lf-threads > .lf-thread").count()
        assert threads == 16, (
            f"the fixture built {threads} threads, not the 16 it needs"
        )
        assert page.evaluate(
            "() => { const l = document.querySelector('.lf-threads');"
            " return l.scrollHeight > l.clientHeight; }"
        ), "the list does not scroll, so nothing here can be cut by its edge"

        # The walk keys, not Tab: a thread is tabindex -1 and j/k are how a reader
        # reaches one. Every landing on the way down and again on the way up, because
        # the two directions align opposite edges of the box with the scrollport and
        # only one of them was ever wrong at a time.
        # Standing nowhere, said rather than clicked for: `c` goes to the box belonging to
        # whatever the reader is standing in, and a click on the body lands wherever the
        # middle of the document happens to be — which on this page is a diff, whose `pre`
        # takes focus. The press then opened that widget's composer and the walk below
        # typed its keys into the box, which is exactly what the non-vacuity check at the
        # end caught: thirty-two landings asserted, none of them on a thread.
        page.evaluate("() => document.activeElement?.blur()")
        page.keyboard.press("c")
        expect(page.locator(".lf-threads")).to_be_focused()
        walked, faults = 0, []
        for key in ("j",) * threads + ("k",) * threads:
            page.keyboard.press(key)
            page.evaluate(RENDERED)
            walked += 1
            faults += ring_faults(
                rings_drawn(page), f"after {walked} presses of the walk"
            )
            under = page.evaluate(COVERED_TOP)
            if under:
                faults.append(
                    f"after {walked} presses, the thread landed under a run "
                    f"heading: {under}"
                )
        assert not faults, "\n  ".join(
            [f"{len(faults)} of {walked} landings:"] + faults
        )

        # Non-vacuity: the walk has to have been on threads inside the scrolling list,
        # drawing rings, or the loop above asserted nothing at every step.
        assert standing_ring(page), "the walk ends on nothing wearing a ring"
        assert standing_ring(page)["scrolled"], (
            "the walk ends outside a scroll region, so the cut half proved nothing"
        )

        # The list's own controls, which j and k never reach: Reply and Resolve inside a
        # card draw their rings outside themselves, as does a run heading, which is a
        # button. They are what the room reserved at this list's edges is for — the
        # threads' own rings being inset, nothing else spends it — so without this pass
        # half of that scroll-padding is unheld. Tab scrolls each stop into view itself,
        # which is the gesture that puts one against an edge.
        page.locator(".lf-threads").focus()
        # Counted off the list rather than floored at a number somebody picked: a
        # walk that reaches eight of thirty-five controls passes a floor of eight
        # while three quarters of the room this list reserves goes unheld, and says
        # nothing about which quarter.
        tabbable = page.eval_on_selector_all(
            ".lf-threads *",
            "els => els.filter((e) => e.tabIndex >= 0).length",
        )
        assert tabbable, "the list holds no control to tab to"
        stops = 0
        for _ in range(tabbable + 5):
            page.keyboard.press("Tab")
            page.evaluate(RENDERED)
            if not page.evaluate(
                "() => document.querySelector('.lf-threads')"
                ".contains(document.activeElement)"
            ):
                break
            stops += 1
            faults += ring_faults(
                rings_drawn(page), f"tabbing to stop {stops} inside the list"
            )
        assert stops == tabbable, (
            f"the walk stood on {stops} of the list's {tabbable} controls, so the room "
            "it reserves at its edges is only partly held by this"
        )
        assert not faults, "\n  ".join([f"{len(faults)} faults:"] + faults)

        assert errors == []
        page.close()
    finally:
        context.close()


def test_go_page_returns_without_unwinding_the_panel(browser, serve):
    """Leaving a panel beside the document to compare a comment is not backing out:
    the panel and its narrowing stay exactly as the reader left them, while focus goes
    to the page. The address starts from the found comment after Enter leaves the find
    box, whose ordinary Escape still owns one rung of the panel stack."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    panel_comment(d, "The capacity needs another look.", {"section": "how-cap"})
    panel_comment(d, "The storage rule is settled.", {"section": "how-store"})

    page, errors = open_page(browser, url)
    page.locator(".lf-comments").click()
    panel_settled(page)
    find = page.locator(".lf-find-box")
    find.focus()
    page.keyboard.type("capacity")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(1)
    page.keyboard.press("Enter")
    expect(page.locator(".lf-threads > .lf-thread")).to_be_focused()

    page.keyboard.press("g")
    page.keyboard.press("p")
    assert page.evaluate("() => document.activeElement === document.body"), (
        "g p left the reader in the panel"
    )
    expect(page.locator(".lf-panel")).to_be_visible()
    expect(find).to_have_value("capacity")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(1)
    assert errors == []
    page.close()


def test_go_page_is_inert_while_the_panel_covers_the_page(browser, serve):
    """A covering panel locks the page scroller, so focus cannot honestly return to
    that page while keeping the panel open. Its ordinary Escape rung remains the one
    route back and closes the covering panel."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    panel_comment(d, "The capacity needs another look.", {"section": "how-cap"})

    context = browser.new_context(viewport={"width": 800, "height": 900})
    try:
        page, errors = open_page(browser, url, context=context)
        page.locator(".lf-comments").click()
        panel_settled(page)
        thread = page.locator(".lf-threads > .lf-thread")
        thread.focus()

        page.keyboard.press("g")
        page.keyboard.press("p")
        expect(thread).to_be_focused()
        expect(page.locator(".lf-panel")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.locator(".lf-panel")).to_be_hidden()
        assert errors == []
        page.close()
    finally:
        context.close()


def test_the_address_chord_places_a_focused_comment_at_either_list_edge(browser, serve):
    """A focused comment is one addressable place with two useful placements. `g t`
    and `g b` move that card inside the panel without moving focus or the document,
    and the list's own scroll padding keeps the landing clear of its pinned heading
    and focus ring."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(16):
        panel_comment(d, f"Comment {i} about storage.", {"section": "how-store"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    try:
        page, errors = open_page(browser, url, context=context)
        page.locator(".lf-comments").click()
        panel_settled(page)
        box = page.locator(".lf-threads")
        target = page.locator(".lf-threads > .lf-thread").nth(8)
        assert box.evaluate("el => el.scrollHeight > el.clientHeight"), (
            "the list does not scroll, so its edges are not distinct places"
        )
        target.evaluate("el => el.focus({preventScroll: true})")

        before_page = page.evaluate("() => document.body.scrollTop")
        page.keyboard.press("g")
        expect(
            page.locator(
                ".lf-keyline .lf-key:not([hidden])",
                has_text="comment top / bottom",
            )
        ).to_have_count(1)
        page.keyboard.press("t")
        top = page.evaluate(
            """() => {
              const box = document.querySelector('.lf-threads');
              const thread = document.activeElement;
              const view = box.getBoundingClientRect();
              const card = thread.getBoundingClientRect();
              const clear = parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
              return {gap: card.top - view.top, clear};
            }"""
        )
        assert abs(top["gap"] - top["clear"]) < 2, (
            f"g t left the card {top['gap']:.1f}px from the list top; "
            f"the landable edge is {top['clear']:.1f}px"
        )
        expect(target).to_be_focused()

        page.keyboard.press("g")
        page.keyboard.press("b")
        bottom = page.evaluate(
            """() => {
              const box = document.querySelector('.lf-threads');
              const thread = document.activeElement;
              const view = box.getBoundingClientRect();
              const card = thread.getBoundingClientRect();
              const clear = parseFloat(getComputedStyle(box).scrollPaddingBottom) || 0;
              return {gap: view.bottom - card.bottom, clear};
            }"""
        )
        assert abs(bottom["gap"] - bottom["clear"]) < 2, (
            f"g b left the card {bottom['gap']:.1f}px from the list bottom; "
            f"the landable edge is {bottom['clear']:.1f}px"
        )
        expect(target).to_be_focused()
        assert page.evaluate("() => document.body.scrollTop") == before_page
        assert errors == []
        page.close()
    finally:
        context.close()


# What the burial below is aiming at: how deep the heading stands over the first card,
# the ring that depth has to match, and the box the press is aimed into. `COVERED_TOP`
# answers the covered question afterwards, by hit test and about the focused card.
UNDER_HEADING = """() => {
  const list = document.querySelector('.lf-threads');
  const card = list.querySelector('.lf-thread');
  const head = list.querySelector('.lf-pinned');
  return {
    covered: head.getBoundingClientRect().bottom - card.getBoundingClientRect().top,
    ring: parseFloat(getComputedStyle(card).getPropertyValue('--here-ring-w')),
    box: card.getBoundingClientRect().toJSON(),
  };
}"""

# Scroll by hand until the heading stands over the card by `want`. A pixel at a time,
# because the heading moves under the gesture: it travels with the flow until it pins,
# and only what it gains after that lands on the card. Bounded, so a list that never
# covers its first card fails the precondition rather than spinning.
BURY = """(want) => {
  const list = document.querySelector('.lf-threads');
  const card = list.querySelector('.lf-thread');
  const head = list.querySelector('.lf-pinned');
  const covered = () =>
    head.getBoundingClientRect().bottom - card.getBoundingClientRect().top;
  for (let i = 0; i < 400 && covered() < want; i++) list.scrollTop += 1;
}"""


def test_a_comment_the_pointer_lands_on_comes_out_from_under_the_run_heading(
    browser, serve
):
    """The walk above never sees this, and that is the point of having it twice: j/k
    scroll their landing into the band the list declares unlandable, so the keyboard
    cannot put a thread anywhere its ring is cut. A click scrolls nothing. The reader
    nudges the list a dozen pixels, the run heading pins over the first card of its run,
    and the two pixels it takes are the whole of that card's inset ring — a card with
    three sides, reported twice by the reader and never by the suite.

    So the gesture here is a real press rather than a locator click, which would scroll
    the card into view for its own actionability check and quietly perform the fix it is
    meant to test. What is asserted is the same question the walk asks — where the
    control can be seen, so can the ring that names it — and, beside it, that the card
    actually came out, since a ring reported whole while the card is still buried would
    mean the reading rather than the landing had moved."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(4):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    try:
        page, errors = open_page(browser, url, context=context)
        page.locator(".lf-comments").click()
        panel_settled(page)

        # Bury the card by exactly its ring, which is the reader's own case: a list nudged
        # a dozen pixels puts the first card of a run a couple of pixels under the
        # heading, and a couple of pixels is the whole of an inset ring. The depth is the
        # ring's width rather than a comfortable number on purpose. Deeper, and the card
        # itself is under the heading, which `RING_FAULTS` excuses by design — a control
        # standing under something is a fact about where it was put. What is left when the
        # card is otherwise in full view is the claim this file makes: where the control
        # can be seen, so can the ring that names it.
        page.evaluate(BURY, page.evaluate(UNDER_HEADING)["ring"])
        page.evaluate(RENDERED)
        buried = page.evaluate(UNDER_HEADING)
        assert buried["ring"] <= buried["covered"] <= buried["ring"] + 1, (
            f"the heading stands over {buried['covered']}px of the first card and its "
            f"ring is {buried['ring']}px: the setup wanted the ring buried and the rest "
            "of the card showing, and this is neither"
        )

        # Just inside the card's own corner. Its middle is prose today and one layout
        # away from being the reply box or a button, and a press that lands on a control
        # inside the card would fail this for a reason that is not its subject.
        box = buried["box"]
        page.mouse.click(box["x"] + 6, box["y"] + 6)
        page.evaluate(RENDERED)
        assert page.evaluate(
            "() => document.activeElement?.classList.contains('lf-thread')"
        ), "the press did not land the reader on a thread, so nothing wore a ring"
        assert standing_ring(page), "the thread it landed on draws no ring"
        assert not ring_faults(
            rings_drawn(page), "after a press on a card under the run heading"
        )
        # The panel's own reading of the same question, and the stronger form of it: a
        # hit test at the card's top edge rather than two rectangles subtracted, and it
        # declines outright if the press left the list.
        assert page.evaluate(COVERED_TOP) is None, (
            f"after the press the card is still under a heading: "
            f"{page.evaluate(COVERED_TOP)}"
        )

        # The reply box is the same card and the same ring — it is drawn for the whole
        # thread, so writing in the box is standing in the thread. Reached by key this
        # was never wrong, because landIn already lands the thread around the box; a
        # press into it went the way every other press did.
        page.evaluate(BURY, buried["ring"])
        page.evaluate(RENDERED)
        under = page.evaluate(UNDER_HEADING)
        assert under["covered"] >= under["ring"], (
            f"the setup put the card back only {under['covered']}px under, which its "
            f"{under['ring']}px ring shows through"
        )
        reply = page.locator(".lf-threads > .lf-thread textarea").first
        reply_box = reply.bounding_box()
        page.mouse.click(
            reply_box["x"] + reply_box["width"] / 2,
            reply_box["y"] + reply_box["height"] / 2,
        )
        page.evaluate(RENDERED)
        expect(reply).to_be_focused()
        assert page.evaluate(COVERED_TOP) is None, (
            "a press into the reply box left the thread's own ring under the heading: "
            f"{page.evaluate(COVERED_TOP)}"
        )

        assert errors == []
        page.close()
    finally:
        context.close()


def test_a_press_on_the_comment_the_reader_is_already_in_brings_it_back(browser, serve):
    """The same gesture as the test above, from the state the reader is actually in when
    they make it: standing in a comment, the list carried a little, the card's top run
    gone under the heading. They press the card to bring it back — and a press on the
    thread that already holds the focus moves no focus at all, so a landing hung off the
    focus event hears nothing and the reader presses at a card that will not come.

    Which is why the press asks where the gesture left the reader rather than which
    thread the focus moved to. The keyboard half of this was already answered — `k` at
    the top of the walk lands the thread it is already on — and this is the same shape
    one scope out."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(4):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    try:
        page, errors = open_page(browser, url, context=context)
        page.locator(".lf-comments").click()
        panel_settled(page)

        # Stand in the card first, then carry the list under it — which is the order the
        # reader does it in, and the one where no later focus event is coming.
        first = page.locator(".lf-threads > .lf-thread").first
        first.focus()
        page.evaluate(RENDERED)
        page.evaluate(BURY, page.evaluate(UNDER_HEADING)["ring"])
        page.evaluate(RENDERED)
        under = page.evaluate(UNDER_HEADING)
        assert under["covered"] >= under["ring"], (
            f"the list carried only {under['covered']}px under the heading, which the "
            f"{under['ring']}px ring shows through — nothing here is cut yet"
        )
        assert page.evaluate(
            "() => document.activeElement?.classList.contains('lf-thread')"
        ), "the reader is not standing in the card, so the press below moves focus"

        box = under["box"]
        page.mouse.click(box["x"] + 6, box["y"] + 6)
        page.evaluate(RENDERED)
        assert page.evaluate(COVERED_TOP) is None, (
            "a press on the card the reader was already standing in left it under the "
            f"heading: {page.evaluate(COVERED_TOP)}"
        )
        assert not ring_faults(
            rings_drawn(page), "after a press on the card already standing in"
        )

        assert errors == []
        page.close()
    finally:
        context.close()


def test_a_cancelled_panel_press_does_not_suppress_the_next_focus_landing(
    browser, serve
):
    """A touch scroll begins as a press and ends in ``pointercancel`` when the browser
    takes the gesture. Cancellation must not undo the scroll by landing the card, but it
    must end the provisional press: the next independent focus arrival still brings its
    thread out from under the run heading.

    Dispatch the pointer events directly so the browser does not add a mouse click or a
    default focus after the cancellation. An unrelated pointer first proves which gesture
    owns the hold; the matching cancellation and the focus after it then distinguish
    release-without-landing from both a stale hold and an ordinary pointer-up landing."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(4):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    try:
        page, errors = open_page(browser, url, context=context)
        page.locator(".lf-comments").click()
        panel_settled(page)

        first = page.locator(".lf-threads > .lf-thread").first
        first.evaluate("el => el.focus({preventScroll: true})")
        page.evaluate(RENDERED)
        page.evaluate(BURY, 20)
        page.evaluate(RENDERED)
        before = page.evaluate("() => document.querySelector('.lf-threads').scrollTop")
        assert (
            page.evaluate(UNDER_HEADING)["covered"] >= 20
        ), "the setup did not put the first card under its heading"

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
        first.evaluate("el => el.focus({preventScroll: true})")
        page.evaluate(RENDERED)
        assert (
            page.evaluate(COVERED_TOP) is not None
        ), "an unrelated pointer cancellation released the active panel gesture"

        page.evaluate(
            """() => dispatchEvent(new PointerEvent('pointercancel', {
              isPrimary: true, pointerId: 7,
            }))"""
        )
        assert (
            page.evaluate("() => document.querySelector('.lf-threads').scrollTop")
            == before
        ), "cancelling a touch-scroll gesture landed the thread and undid the scroll"

        page.locator(".lf-threads").evaluate("el => el.focus({preventScroll: true})")
        first.evaluate("el => el.focus({preventScroll: true})")
        page.evaluate(RENDERED)
        assert page.evaluate(COVERED_TOP) is None, (
            "the cancelled press suppressed the next focus landing and left the card "
            f"under its heading: {page.evaluate(COVERED_TOP)}"
        )

        assert errors == []
        page.close()
    finally:
        context.close()


def test_a_drag_across_a_quote_takes_its_words_and_not_its_passage(browser, serve):
    """The panel's quote is words and a press at once — it says which passage the comment
    is about, and pressing it travels the page there. So a reader who drags across it to
    take the words gets the travel as well, and the page they were reading goes.

    `offer` has answered this for its own controls since a suggestion's Accept went dead
    under a selection that ran over it, and the answer is the same one: the selection's
    focus end is the character the button came up on, so a press that ended in these
    words was reaching for them. What is new is that the reading is now the reading and
    not that listener's own business, because the same gesture reaches two more things —
    a quote, which `offer` never made, and the list's own landing."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(4):
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    try:
        page, errors = open_page(browser, url, context=context)
        page.locator(".lf-comments").click()
        panel_settled(page)
        page.evaluate("() => { document.querySelector('.lf-threads').scrollTop = 0; }")
        page.evaluate(RENDERED)

        where = "() => document.body.scrollTop"
        before = page.evaluate(where)
        quote = page.locator(".lf-threads > .lf-thread .lf-quote").first
        span = quote.bounding_box()
        page.mouse.move(span["x"] + 4, span["y"] + 6)
        page.mouse.down()
        page.mouse.move(span["x"] + span["width"] - 6, span["y"] + 6, steps=8)
        page.mouse.up()
        page.evaluate(RENDERED)
        page.wait_for_timeout(400)  # the travel is a glide, so let one finish if it ran

        drawn = page.evaluate("() => getSelection().toString()")
        assert len(drawn) > 8, (
            f"the drag took {drawn!r} of the quote, so this asserts nothing about one"
        )
        after = page.evaluate(where)
        assert after == before, (
            f"the page travelled from {before} to {after} while the reader was taking "
            "the quote's words, so what they were reading went with it"
        )

        # The press itself still travels: what stood down is the drag, not the control.
        # The words go first, because a press inside a standing selection is where the
        # platform holds it for a drag of its own — the reader's next press is a press,
        # not the tail of the one before it.
        page.evaluate("() => getSelection().removeAllRanges()")
        quote.click()
        page.evaluate(RENDERED)
        page.wait_for_timeout(400)
        assert page.evaluate(where) != before, (
            "a plain press on the quote no longer travels to its passage, so this took "
            "the control away rather than the drag"
        )

        assert errors == []
        page.close()
    finally:
        context.close()


def test_a_drag_across_a_comments_words_leaves_the_list_where_it_was_read(
    browser, serve
):
    """The other half of landing a press, and the reason it waits for the press to end.
    Focus arrives on the way down, so a landing taken there scrolls the words out from
    under a pointer that is still selecting them — and the selection runs on to wherever
    they went, which measured about three times what the reader had drawn.

    So the gesture is a real drag across a card near the top of the list, where any
    landing at all would move it, and the two things asserted are what the reader has
    afterwards: the list where they were reading, and the words they actually dragged
    over. `offer` asks the same question of a click and reads the answer the same way —
    the selection's focus end is the character the button came up on."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(4):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
        panel_comment(d, f"About the store, {i}.", {"section": "how-store"})
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})

    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, reduced_motion="reduce"
    )
    try:
        page, errors = open_page(browser, url, context=context)
        page.locator(".lf-comments").click()
        panel_settled(page)

        # Far enough under the heading that a landing would be a visible jump, so the
        # drag below is asserting the absence of something this list would otherwise do.
        page.evaluate(BURY, 20)
        page.evaluate(RENDERED)
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
        page.evaluate(RENDERED)

        after = page.evaluate("() => document.querySelector('.lf-threads').scrollTop")
        assert after == before, (
            f"the list moved from {before} to {after} under a drag, so the words the "
            "reader was selecting went with it"
        )
        drawn = page.evaluate("() => getSelection().toString()")
        assert len(drawn) > 4, (
            f"the drag selected {drawn!r}, so this asserts nothing about a selection"
        )

        assert errors == []
        page.close()
    finally:
        context.close()


def test_the_room_a_run_heading_takes_follows_the_reader_drawing_the_panel(
    browser, serve
):
    """How much of the list's top a stuck heading covers is a measurement, because a long
    heading wraps — and how long is long is the list's width, which is the reader's to
    set. They set it by dragging the panel's edge, and a drag posts no event, so the
    reconcile that takes this measurement never comes. The number went on reserving room
    for the one line the heading had at the width it was written at, and the threads a
    walk landed on went back under the heading, which is the whole of what the number
    exists to prevent.

    A heading long enough to wrap at the narrow end and not at the wide one is what makes
    the drag a single factor: the same list, the same log, one gesture between the two
    readings."""
    url = serve(
        PANEL_PAGE.replace(
            '<h2 id="h-merge">The merge rule</h2>',
            '<h2 id="h-merge">The merge rule, and every case two offline editors '
            "can put it in</h2>",
        )
    )
    d = serve.page_dir
    for i in range(4):
        panel_comment(d, f"About the merge, {i}.", {"section": "merge-both"})
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})

    context = browser.new_context(
        viewport={"width": 1400, "height": 900}, reduced_motion="reduce"
    )
    try:
        page, errors = open_page(browser, url, context=context)
        edge = next(e for e in EDGES if e.name == "comments")
        page.locator(".lf-comments").click()
        panel_settled(page)
        room = (
            "() => getComputedStyle(document.querySelector('.lf-threads'))"
            ".getPropertyValue('--lf-head-room')"
        )
        tallest = """() => Math.max(0, ...[...document.querySelectorAll(
             '.lf-threads .lf-pinned')].map((h) => Math.round(
               h.getBoundingClientRect().height)))"""
        assert page.evaluate(room) == f"{page.evaluate(tallest)}px"

        # Narrow it until the long heading wraps. The gesture is the reader's own.
        draw_edge(page, edge, -(edge.wide - 320))
        edge_settled(page, edge)
        assert page.evaluate(tallest) > 38, (
            "no heading wrapped at the narrow end, so the drag changed nothing to notice"
        )
        assert page.evaluate(room) == f"{page.evaluate(tallest)}px", (
            "the room a heading takes was measured at a width the reader has left"
        )

        # And the walk lands clear of it, which is what the number is for. Standing
        # nowhere first, said rather than clicked: `c` opens the box belonging to
        # whatever the reader is standing in, and a click on the body lands wherever the
        # middle of the document happens to be — here a diff, whose `pre` takes focus, so
        # the press opened that widget's composer and the sixteen keys below were typed
        # into it as characters. COVERED_TOP answers null for a focus outside the list,
        # so every one of those landings agreed with the invariant by never being asked.
        page.evaluate("() => document.activeElement?.blur()")
        page.keyboard.press("c")
        expect(page.locator(".lf-threads")).to_be_focused()
        faults = []
        for key in ("j",) * 8 + ("k",) * 8:
            page.keyboard.press(key)
            page.evaluate(RENDERED)
            under = page.evaluate(COVERED_TOP)
            if under:
                faults.append(under)
        assert not faults, "\n  ".join(["landed under a run heading:"] + faults)
        # Non-vacuity, kept beside the loop it is about: the walk has to have ended on a
        # thread inside the list, or the loop asked its question sixteen times of a focus
        # COVERED_TOP declines to answer for.
        assert page.evaluate(
            "() => Boolean(document.activeElement?.closest?.('.lf-threads > .lf-thread'))"
        ), "the walk ends outside the list, so the landings proved nothing"
        assert errors == []
        page.close()
    finally:
        context.close()


def test_the_line_offers_the_list_its_own_keys_rather_than_the_way_deeper_in(
    browser, serve
):
    """The two chips the line paints are what a reader standing on the list is offered,
    and they have to be the keys that act on the list.

    `c` brought them here so that `w` and `/` would be live — the general box is where
    the typing scope claims every letter, which is the whole reason the press stops at
    the list. This is the one focus position where those two rows can hold a chip at
    all: inside a thread `THREAD` is nearer, inside a box `TYPING` claims the letters,
    and outside the panel this scope is not standing. So a row in front of them here
    spends the slot the landing exists to fill, which is what the panel's own `c` did
    until it was moved to the end of the scope.

    Read off `:not([hidden])`, because `renderLine` leaves every live row in the DOM and
    hides the ones it has no room to paint. `to_contain_text` on the line therefore
    answers about the register rather than about the reader, and passes just as well
    when the chip is one nobody can see — which is why the rest of the panel's tests
    could not have caught this.

    The second press keeps a surface of its own: the box says the key in its own
    placeholder, which the last phase reads."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    for i in range(3):
        panel_comment(d, f"About the lede, {i}.", {"section": "lede"})
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "author": "claude",
            "revision": 1,
            "text": "Which way round should this go?",
            "anchor": {"section": "how-store"},
        },
    )

    page, errors = open_page(browser, url)
    page.evaluate("() => document.activeElement?.blur()")
    page.keyboard.press("c")
    expect(page.locator(".lf-threads")).to_be_focused()

    shown = page.locator(".lf-keyline .lf-key:not([hidden])")
    expect(shown).to_have_count(2)
    # The list's own key leads: something is waiting, so `w` is live and nearest.
    expect(shown.nth(0)).to_contain_text("waiting on you")
    expect(shown.nth(1)).to_contain_text("close comments")

    # And the press it displaced still works, from the placeholder that advertises it.
    expect(page.locator(".lf-general textarea")).to_have_attribute(
        "placeholder", re.compile(r"·\s*c$")
    )
    page.keyboard.press("c")
    expect(page.locator(".lf-general textarea")).to_be_focused()

    assert errors == []
    page.close()
