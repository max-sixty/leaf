"""Comment-panel ordering, narrowing, and thread-motion tests."""

import re

import pytest
from conftest import interact
from playwright.sync_api import expect
from render_support import (
    FRAME_BY_FRAME,
    HOLD_MOTION,
    LIST_RUNS,
    LIST_STATE,
    LONG_PAGE,
    PANEL_PAGE,
    in_threads_scrollport,
    leaf_page,
    open_page,
    panel_comment,
    panel_settled,
    resized,
    round_trip,
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
    sent = interact.read_events(serve.page_dir)[-1]
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
    second = interact.read_events(serve.page_dir)[-1]
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
        e for e in interact.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    reply = interact.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Claude",
            "version": 1,
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
        e for e in interact.read_events(serve.page_dir) if e["kind"] == "comment"
    )
    reply = interact.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Claude",
            "version": 1,
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
        e["id"] for e in interact.read_events(serve.page_dir) if e["kind"] == "comment"
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
    interact.append_event(
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
    assert page.evaluate(LIST_RUNS) == [first, second], (
        "a page with no outline did not get the page's order, or was given a landmark"
    )
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
    ) == {"pinned": True, "scrolledPast": True, "opaque": True}, (
        "the run's heading did not stay over the run"
    )

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
    # prose it does nothing, and `c` then Escape is the route in. Read against the same
    # press landing two lines below, which is what makes the silence a rule.
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
    page.keyboard.press("Escape")  # out of the general box, onto the list
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
    answers: the agent spoke last. So the panel asks it rather than keeping a record of
    what this reader has read — nothing to go stale in a second tab, and nothing to
    remember across a reload.

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

    # `c` puts the reader in the panel, in its general box — where `w` is a character
    # like any other, the typing scope claiming what types one. Escape backs out onto the
    # list, and there the key is live and the line says so. The control names it, off the
    # row, so the two cannot come to spell it differently.
    page.keyboard.press("c")
    panel_settled(page)
    expect(page.locator(".lf-needs")).to_have_text("Waiting on you (1)")
    expect(page.locator(".lf-needs")).to_have_attribute("title", re.compile(r"\(w\)$"))
    expect(page.locator(".lf-keyline")).not_to_contain_text("waiting on you")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(page.locator(".lf-keyline")).to_contain_text("waiting on you")
    page.keyboard.press("w")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(1)
    expect(page.locator(f'.lf-thread[data-id="{theirs}"]')).to_have_count(1)
    expect(page.locator(".lf-panel-head span")).to_have_text("Showing 1 of 2")
    expect(page.locator(".lf-needs")).to_have_attribute("aria-pressed", "true")

    # Answering it takes it out of the list it is filtered to, because the fact the
    # filter reads is who spoke last and the reader has now spoken.
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
        e["id"] for e in interact.read_events(serve.page_dir) if e["kind"] == "comment"
    ]

    interact.append_event(
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
        e["id"] for e in interact.read_events(serve.page_dir) if e["kind"] == "comment"
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
    assert interact.read_events(serve.page_dir)[-1]["kind"] == "unresolve"
    assert errors == []
    page.close()


def test_a_late_reply_to_a_resolved_thread_stays_above_its_reopen_footer(
    browser, serve
):
    """New messages reconcile before the resolved thread's persistent actions."""
    url = serve(LONG_PAGE, comments=1)
    root = next(
        event
        for event in interact.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    interact.append_event(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": root["id"]}
    )
    page, errors = open_page(browser, url)
    page.locator(".lf-comments").click()
    page.locator(".lf-details summary").click()
    interact.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "version": 1,
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
        e["id"] for e in interact.read_events(serve.page_dir) if e["kind"] == "comment"
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
        e["id"] for e in interact.read_events(serve.page_dir) if e["kind"] == "comment"
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
            for e in interact.read_events(serve.page_dir)
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
        e["id"] for e in interact.read_events(serve.page_dir) if e["kind"] == "comment"
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
    reply = interact.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Claude",
            "version": 1,
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
    assert (
        {c for c in surface["global"] if c.startswith("lf-")}
        == {
            "lf-copy",
            "lf-ui",
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
            "lf-arrived",  # the arrival's clock, on the blocks the standing mark is painted over
            "lf-over-item",
            "lf-quiet",
        }
    ), (
        "the document-level class surface changed: widen the shared vocabulary on purpose"
    )
    page.close()
