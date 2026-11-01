"""Threads drawn in the page's own flow, on a seat or a diff line: what arriving turns,
settlement and new patches do to their reply box and to the reading around them."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATION_PAGE, panel_comment
from render_cases_navigation import source_revision
from render_harness import (
    PANEL,
    PANEL_THREAD,
    RELEASE_FOCUS,
    consume_browser_errors,
    http_error_console,
    leaf_page,
    open_page,
    reported_browser_errors,
    resized,
    round_trip,
    scroll_settled,
    sending,
    told,
    write,
)

from browser.threads import (
    PANEL_REPLY,
    SEAT_DIFF,
    SEAT_FILLER,
    SEAT_WORDS,
    THIRTY_LINES,
    append_agent_reply,
    clear_of_the_panel,
    long_diff_thread,
    open_panel_thread,
    paste,
    seated_page,
    to_window_foot,
)
from leaf import data as data_model
from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.watch_shifts
def test_a_resolution_from_elsewhere_moves_nothing_after_a_diff_thread(browser, serve):
    """A diff line's thread resolved elsewhere stays open behind its notice.

    Resolving folds the thread into its outlet's Resolved disclosure, which would lift
    the paragraph after the diff under the reader."""
    url = serve(
        leaf_page(
            "inline diff thread",
            '<h1 id="title">Review</h1><lf-diff id="patch" source="review-patch">'
            '<pre></pre></lf-diff><p id="after">Reading the paragraph after the diff.</p>',
        )
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n"
        '-return "old"\n+return "new"\n',
    )
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep this check beside the changed line.",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )["id"]
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "text": "The guard now covers the replacement path.",
        },
    )
    page = open_page(browser, url)
    resized(page, 1920, 900)
    thread = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    after = page.locator("#after")
    expect(thread).to_be_visible()
    rendered(page)
    page.wait_for_function(
        "at => performance.now() - at > 500", arg=page.evaluate("performance.now()")
    )
    before = after.bounding_box()
    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    notice = thread.get_by_role("button", name="Resolved", exact=True)
    expect(notice).to_be_visible()
    rendered(page)
    assert after.bounding_box() == before
    notice.click()
    expect(thread).to_have_attribute("data-resolved", "true")
    expect(thread).to_be_hidden()
    expect(page.locator("lf-diff .lf-resolved-summary")).to_have_text("Resolved · 1")


@pytest.mark.parametrize("foot", ["above the window", "under the file header"])
def test_diff_news_waits_only_where_its_growth_would_be_seen(browser, serve, foot):
    """A diff thread's new reply waits only where its growth would move what is seen.

    A reply grows the thread at its last message's foot. With that foot above the
    window, scroll anchoring takes the growth into what was scrolled past, so the reply
    shows at once. With it under the diff's stuck file header, which reaches lower than
    the landing band the page anchors in, the growth would push down the lines below
    the header, so the reply waits behind its notice, and shows once a scroll carries
    the thread above the window. Either way the line the user reads stays put."""
    url, root = long_diff_thread(serve)
    page = open_page(browser, url)
    resized(page, 1280, 800)
    thread = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    expect(thread).to_be_visible()
    header = page.locator("lf-diff .lf-diff-file > details > summary")
    read = page.locator("lf-diff [data-line]").filter(has_text="line 30")

    last = thread.locator(".lf-msg").last

    def stand(node, below_top):
        """Scroll `node`'s foot to `below_top` px below the window's top, where no
        chrome stands, and return the root's landing band top."""
        return node.evaluate(
            """(node, offset) => {
              scrollBy({top: node.getBoundingClientRect().bottom - offset,
                behavior: 'instant'});
              const root = getComputedStyle(document.documentElement);
              return {landing: parseFloat(root.scrollPaddingTop)};
            }""",
            below_top,
        )

    chrome = stand(last, -8 if foot == "above the window" else 24)
    rendered(page)
    box = last.bounding_box()
    foot_at = box["y"] + box["height"]
    if foot == "under the file header":
        header_box = header.bounding_box()
        header_foot = header_box["y"] + header_box["height"]
        assert chrome["landing"] < foot_at < header_foot, (chrome, foot_at, header_foot)
    else:
        assert foot_at < 0, (chrome, foot_at)
    # Chrome reports no shift within 500ms of input, so the news lands after it.
    page.wait_for_function(
        "at => performance.now() - at > 500", arg=page.evaluate("performance.now()")
    )
    before = read.bounding_box()
    append_agent_reply(
        serve.page_dir, root, "The guard now covers the replacement path."
    )
    told(page)
    rendered(page)
    notice = thread.get_by_role("button", name="1 new reply", exact=True)
    messages = thread.locator(".lf-msg")
    if foot == "above the window":
        expect(messages).to_have_count(2)
        expect(notice).to_have_count(0)
    else:
        expect(notice).to_have_count(1)
        expect(messages).to_have_count(1)
    assert read.bounding_box() == before

    if foot == "under the file header":
        # Released once growth anywhere in the thread would move nothing seen.
        stand(thread, -8)
        expect(messages).to_have_count(2)
        expect(notice).to_have_count(0)


def test_growth_is_seen_only_below_where_scroll_anchoring_holds(browser, serve):
    """Scroll anchoring keeps still the first box in the root's landing band, which
    starts a gap below the window's top. A paragraph ending in that gap grows into what was
    scrolled past, so growth after it is not seen; one ending below the band's top
    pushes down what follows it, so growth after it is."""
    paragraphs = "".join(
        f'<p id="p{number}">Paragraph {number} of the reading.</p>'
        for number in range(60)
    )
    page = open_page(browser, serve(leaf_page("anchoring gap", paragraphs)))
    resized(page, 1280, 800)
    readings = page.evaluate(
        """async () => {
          const {growthAfterIsSeen} = await window.__lfCheckApi();
          const landing = parseFloat(
            getComputedStyle(document.documentElement).scrollPaddingTop);
          const frame = () => new Promise(requestAnimationFrame);
          const read = async (foot) => {
            const grown = document.getElementById('p20');
            const next = document.getElementById('p21');
            scrollBy({top: grown.getBoundingClientRect().bottom - foot,
              behavior: 'instant'});
            await frame();
            const seen = growthAfterIsSeen(grown);
            const before = next.getBoundingClientRect().top;
            grown.style.paddingBottom = '40px';
            await frame();
            const moved = next.getBoundingClientRect().top - before;
            grown.style.paddingBottom = '';
            await frame();
            return {foot, seen, moved};
          };
          // No chrome stands over the page's head.
          const head = 0;
          return {head, landing,
            gap: await read((head + landing) / 2),
            band: await read(landing + 6)};
        }"""
    )
    assert readings["head"] < readings["landing"], readings
    assert readings["gap"] == {**readings["gap"], "seen": False}, readings
    assert abs(readings["gap"]["moved"]) < 1, readings
    assert readings["band"] == {**readings["band"], "seen": True}, readings
    assert readings["band"]["moved"] > 30, readings


def test_an_agent_settling_a_diff_thread_above_the_screen_moves_nothing_below(
    browser, serve
):
    """A diff thread folds into its outlet's Resolved disclosure when the agent
    resolves it and comes back out when it reopens it. Above the screen, either change
    is scroll anchoring's to absorb, so the line the user reads stays put, though each
    also changes what the outlet holds."""
    url, root = long_diff_thread(serve)
    page = open_page(browser, url)
    resized(page, 1280, 800)
    thread = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    expect(thread).to_be_visible()
    read = page.locator("lf-diff [data-line]").filter(has_text="line 30")
    thread.evaluate(
        "node => scrollBy({top: node.getBoundingClientRect().bottom + 100,"
        " behavior: 'instant'})"
    )
    rendered(page)
    before = read.bounding_box()["y"]
    for kind, opened in [("resolve", False), ("unresolve", True)]:
        append_carried_log_record(
            serve.page_dir,
            {"kind": kind, "author": "agent", "agent": "Codex", "parent": root},
        )
        told(page)
        rendered(page)
        expect(thread).to_be_visible() if opened else expect(thread).to_be_hidden()
        # Anchoring lands the scroll on a device pixel, so the line may settle a
        # fraction of one from where it stood.
        assert read.bounding_box()["y"] == pytest.approx(before, abs=0.5), kind


@pytest.mark.parametrize("disclosure", ["closed", "open"])
def test_a_reopening_waits_where_the_reopened_thread_would_stand(
    browser, serve, disclosure
):
    """A diff thread in its outlet's Resolved disclosure reopens ahead of the open
    threads that came after it, not where the disclosure stands. With the disclosure
    below the window, closed or open, and a later open thread on screen, an agent's
    reply that reopened the earlier thread pushed the open one down under the reader.
    It waits, and the disclosure's summary says so."""
    url, first = long_diff_thread(serve)
    append_carried_log_record(
        serve.page_dir, {"kind": "resolve", "author": "user", "parent": first}
    )
    later = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "And keep the old name working.",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": source_revision(serve.page_dir, "review-patch"),
            },
        },
    )["id"]
    for turn in range(8):
        append_agent_reply(
            serve.page_dir, later, f"Step {turn}: " + "the alias stays. " * 12
        )
    page = open_page(browser, url)
    resized(page, 1280, 800)
    open_thread = page.locator(f'lf-diff .lf-page-thread[data-thread="{later}"]')
    summary = page.locator("lf-diff .lf-resolved-summary")
    expect(summary).to_have_text("Resolved · 1")
    if disclosure == "open":
        summary.click()
        expect(
            page.locator(f'lf-diff .lf-page-thread[data-thread="{first}"]')
        ).to_be_visible()
    open_thread.evaluate(
        "node => scrollBy({top: node.getBoundingClientRect().top - 200,"
        " behavior: 'instant'})"
    )
    rendered(page)
    assert summary.bounding_box()["y"] > 800
    page.wait_for_function(
        "at => performance.now() - at > 600", arg=page.evaluate("performance.now()")
    )
    before = open_thread.bounding_box()["y"]
    append_agent_reply(serve.page_dir, first, "The check now covers both paths.")
    told(page)
    rendered(page)
    expect(summary).to_have_text("Resolved · 1 · Reopened · 1 new reply")
    # The news is Leaf's, in its face, as the thread's own held news is.
    expect(summary.locator('[data-voice="leaf"]')).to_have_text(
        "Reopened · 1 new reply"
    )
    assert open_thread.bounding_box()["y"] == pytest.approx(before, abs=0.5)


def test_a_reaction_list_closes_once_its_trigger_is_out_of_sight(browser, serve):
    """An open reaction list hangs from its trigger, so it closes once none of the
    trigger is in front of the user: scrolled out of the window."""
    url, root = long_diff_thread(serve)
    append_agent_reply(
        serve.page_dir, root, "The guard now covers the replacement path."
    )
    page = open_page(browser, url)
    resized(page, 1280, 800)
    message = page.locator(
        f'lf-diff .lf-page-thread[data-thread="{root}"] .lf-msg.agent'
    )
    message.hover()
    trigger = message.locator(".lf-react-trigger")
    trigger.click()
    strip = message.locator(":scope > .lf-react-strip")
    expect(strip.locator(".lf-react-palette:popover-open")).to_have_count(1)
    trigger.evaluate(
        """trigger => scrollBy({top: trigger.getBoundingClientRect().bottom + 4,
          behavior: 'instant'})"""
    )
    box = trigger.bounding_box()
    assert box["y"] + box["height"] < 0, box
    expect(strip.locator(".lf-react-palette:popover-open")).to_have_count(0)
    expect(page.locator(".lf-react-palette:popover-open")).to_have_count(0)


def watch_blurs(box):
    """Count the times the editor `box` loses focus from now on, wherever it moves:
    a move that keeps the user in it fires none (`blurs`)."""
    box.evaluate(
        "box => { box.lfBlurs = 0; box.addEventListener('blur', () => box.lfBlurs++); }"
    )


def blurs(box):
    return box.evaluate("box => box.lfBlurs")


def seated_thread(
    serve, kind, messages, annotations="overlay", line='["app.py","new",1]'
):
    """A thread of `messages` turns on a page seat (`task`, `verdict`) or on a diff
    `line` (`diff`, drawn inside the widget's shadow tree), and the page's URL. A diff
    page draws its margin as `annotations` says."""
    if kind == "diff":
        url = serve(
            leaf_page(
                "diff",
                f'<h1 id="title">Review</h1>{SEAT_FILLER}<lf-diff id="patch" '
                f'source="review-patch"><pre></pre></lf-diff>{SEAT_FILLER}',
            ).replace("<body>", f'<body data-annotations="{annotations}">', 1)
        )
        data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF)
        anchor = {
            "section": "patch",
            "datum": line,
            "source": "review-patch",
            "source_revision": source_revision(serve.page_dir, "review-patch"),
        }
    else:
        url, host = seated_page(serve, kind)
        anchor = {"section": host[1:]}
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Opening remark. " + SEAT_WORDS,
            "anchor": anchor,
        },
    )["id"]
    for n in range(messages - 1):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent" if n % 2 == 0 else "user",
                "agent": "Codex",
                "parent": root,
                "revision": 1,
                "text": f"Message {n + 2}. " + SEAT_WORDS,
            },
        )
    return url, root


def focus_clear_of_the_panel(page):
    """Whether the focused node, through open shadow roots, shows in the window, above
    the floating panel where it spans the node's columns."""
    return page.evaluate(
        """() => {
          let node = document.activeElement;
          while (node?.shadowRoot?.activeElement) node = node.shadowRoot.activeElement;
          const box = node.getBoundingClientRect();
          const b = document.querySelector('.lf-fp-card')?.getBoundingClientRect();
          const covers = b && b.left < box.right && box.left < b.right;
          const foot = covers ? b.top : innerHeight;
          return box.height > 0 && box.bottom > 0 && box.top < foot;
        }"""
    )


def test_a_diff_thread_reply_grown_by_a_paste_keeps_its_send_above_the_panel(
    browser, serve
):
    """A diff draws its threads in its own shadow tree. The landing's climb stopped at
    that root, never met the page's scroller, and read a thread taller than the window
    as one that fits, so the growth reveal moved nothing."""
    url, root = seated_thread(serve, "diff", 12)
    page = open_page(browser, url)
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    box = thread.locator(":scope > .lf-thread-reply leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "First line")
    to_window_foot(page, box, 60)
    paste(page, THIRTY_LINES)
    assert clear_of_the_panel(
        page, thread.locator(":scope > .lf-thread-reply .lf-compose-submit")
    )


@pytest.mark.parametrize("kind", ["task", "bounded"])
def test_an_agent_turn_arriving_holds_still_the_page_box_being_typed_in(
    browser, serve, kind
):
    """The new turn went in above the reply box the user was typing in and pushed it,
    caret and all, below the fold. News moves no control under the user's hands: the
    turn waits behind the thread's notice, since the thread's foot is on screen, and
    the box stands where it was, in a bounded block as on the page."""
    messages = 1 if kind == "bounded-short" else 3
    url, root = seated_thread(serve, kind, messages)
    page = open_page(browser, url)
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    box = thread.locator(":scope > .lf-thread-reply leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "Half a thought")
    to_window_foot(page, box, 50)
    before = box.evaluate("box => box.getBoundingClientRect().top")
    page_before = page.evaluate("() => document.scrollingElement.scrollTop")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "responds": root,
            "revision": 1,
            "text": "The agent's answer. " + SEAT_WORDS,
        },
    )
    told(page)
    expect(thread.get_by_role("button", name="1 new reply")).to_be_visible()
    rendered(page)
    expect(thread.locator(".lf-msg")).to_have_count(messages)
    expect(box).to_be_focused()
    assert box.evaluate("box => box.getBoundingClientRect().top") == pytest.approx(
        before, abs=1
    )
    page_after = page.evaluate("() => document.scrollingElement.scrollTop")
    assert page_after == pytest.approx(page_before, abs=1)


def test_resolving_a_long_page_thread_by_its_button_leaves_the_page_still(
    browser, serve
):
    """The pressed Resolve leaves with the state it changed, and the thread folds into
    its seat's Resolved disclosure, taking the focus to the disclosure's summary. It
    took it back with a landing on the thread: the nearest edge of a thread taller than
    the window was a 700px jump to its head."""
    kind = "verdict"
    url, root = seated_thread(serve, kind, 12)
    page = open_page(browser, url)
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    resolve = thread.locator(".lf-resolve")
    resolve.scroll_into_view_if_needed()
    to_window_foot(page, resolve, 120)
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    box = resolve.bounding_box()
    with sending(page, "the resolve"):
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    rendered(page)
    scroll_settled(page)
    expect(page.locator(".lf-resolved-summary")).to_be_focused()
    after = page.evaluate("() => document.scrollingElement.scrollTop")
    assert abs(after - before) < 10, f"the page jumped {after - before}px"


def test_settling_a_long_diff_thread_by_key_keeps_it_in_view(browser, serve):
    """A diff thread folds into its outlet's Resolved disclosure when resolved and
    comes back out when reopened, and nothing landed it either way: the summary the
    user was located on went above the window, and the reopened thread with it."""
    url, root = seated_thread(serve, "diff", 12)
    page = open_page(browser, url)
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    box = thread.locator(":scope > .lf-thread-reply leaf-text")
    box.scroll_into_view_if_needed()
    to_window_foot(page, box, 60)
    box.focus()
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    with sending(page, "the resolve"):
        page.keyboard.press("r")
    rendered(page)
    scroll_settled(page)
    assert focus_clear_of_the_panel(page), "the resolved thread left the window"
    expect(page.locator("lf-diff .lf-resolved-summary")).to_be_focused()
    page.keyboard.press("Enter")
    thread.focus()
    with sending(page, "the reopen"):
        page.keyboard.press("r")
    rendered(page)
    scroll_settled(page)
    assert focus_clear_of_the_panel(page), "the reopened thread left the window"


def test_r_settles_the_thread_seated_under_the_diff_line_the_user_stands_on(
    browser, serve
):
    """A line and the thread the diff seats under it are one place, as an element and
    the thread its card shows are, so `r` on the line `]` lands on settles that
    thread. The user stays on the line."""
    url, root = seated_thread(serve, "diff", 1, line='["app.py","old",1]')
    page = open_page(browser, url)
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    expect(thread).to_be_visible()
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("Tab")  # The file's comment control.
    page.keyboard.press("Tab")  # Its disclosure, also on a single-file diff.
    expect(page.locator("lf-diff summary")).to_be_focused()
    page.keyboard.press("]")
    line = page.locator('lf-diff div[data-lf-line=\'["app.py","old",1]\']')
    expect(line).to_be_focused()
    with sending(page, "the resolve"):
        page.keyboard.press("r")
    rendered(page)
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "resolve"
    expect(line).to_be_focused()


@pytest.mark.parametrize("kind", ["diff", "bounded-short"])
def test_a_turn_arriving_leaves_a_user_who_scrolled_away_from_their_box_reading(
    browser, serve, kind
):
    """The box a turn arrives above is held still only while it is on screen. A user
    who wheeled up to read the page with focus still in the box is reading the page,
    and holding the box there moved what they were reading. A box shown inside a
    bounded block the page has scrolled away is off screen too, or the growth the
    block cannot take is handed to the page under the reader."""
    messages = 1 if kind == "bounded-short" else 3
    url, root = seated_thread(serve, kind, messages)
    page = open_page(browser, url)
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    box = thread.locator(":scope > .lf-thread-reply leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "Half a thought")
    page.evaluate(
        """node => document.scrollingElement.scrollBy({
          top: node.getBoundingClientRect().top - innerHeight - 400,
          behavior: 'instant'})""",
        thread.element_handle(),
    )
    scroll_settled(page)
    expect(box).to_be_focused()
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Codex",
            "parent": root,
            "responds": root,
            "revision": 1,
            "text": "The agent's answer. " + SEAT_WORDS,
        },
    )
    told(page)
    expect(thread.locator(".lf-msg")).to_have_count(messages + 1)
    rendered(page)
    after = page.evaluate("() => document.scrollingElement.scrollTop")
    assert after == pytest.approx(before, abs=1), f"the page moved {after - before}px"


@pytest.mark.parametrize(
    ("resolved", "annotations"),
    # A page margin draws the card in the pass that takes the thread off the diff; an
    # overlay margin opens it afterwards, for the user carried there.
    [(False, "overlay"), (True, "overlay"), (False, "page")],
)
def test_a_reply_box_whose_thread_leaves_the_diff_takes_the_user_to_its_card(
    browser, serve, resolved, annotations
):
    """A new patch takes each thread off the diff to the margin, since its anchor
    names the patch it was written on, and the reply box the user was typing in went
    with it: focus fell to the page, and the next letters ran page commands. The
    user follows the thread to its margin card, typing on in the same editor at the
    same caret, with its undo history, and no task between the two finds them on
    the page."""
    url, root = seated_thread(serve, "diff", 2, annotations)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    inline = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    box = inline.locator(":scope > .lf-thread-reply leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "Half a thought")
    box.evaluate("box => box.setSelectionRange(4, 4)")
    if resolved:
        append_carried_log_record(
            serve.page_dir,
            {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
        )
        told(page)
        expect(box).to_be_focused()
    watch_blurs(box)
    # Whether the page, at any task after the box leaves, holds the user nowhere: a
    # key arriving then would run as a page command.
    page.evaluate(
        """() => {
          window.__strandedAt = [];
          document.addEventListener('focusout', () => setTimeout(() => {
            if (document.activeElement === document.body)
              window.__strandedAt.push(performance.now());
          }), true);
        }"""
    )
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", SEAT_DIFF + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    expect(inline).to_have_count(0)
    # A page drawing no margin puts the thread up in the panel, its reply in the
    # panel's field; an overlay margin in its card.
    if annotations == "page":
        expect(page.locator(f'{PANEL_THREAD}[data-thread="{root}"]')).to_be_visible()
        reply = page.locator(PANEL_REPLY)
    else:
        card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
        reply = card.locator(":scope > .lf-thread-reply leaf-text")
    expect(reply).to_be_focused()
    expect(reply).to_have_js_property("value", "Half a thought")
    assert reply.evaluate("box => [box.selectionStart, box.selectionEnd]") == [4, 4]
    assert page.evaluate("() => window.__strandedAt") == []
    # The user never left the editor on its way.
    assert blurs(reply) == 0
    page.keyboard.type(" tr")
    expect(reply).to_have_js_property("value", "Half tr a thought")
    expect(reply).to_be_focused()
    # The editor came with the thread, so undo walks back through what was typed on
    # the diff line too.
    page.keyboard.press("ControlOrMeta+z")
    expect(reply).to_have_js_property("value", "Half a thought")
    page.keyboard.press("ControlOrMeta+z")
    expect(reply).to_have_js_property("value", "")


def test_a_reply_box_whose_thread_returns_to_the_diff_takes_the_user_back(
    browser, serve
):
    """The patch a thread was written on comes back while the user types in its
    margin card, and the thread takes its seat on the diff line again. The card
    closing under the user landed them on the banner, so the next letters ran page
    commands. They go on in the same editor on the diff line, at the same caret, with
    its undo history."""
    url, root = seated_thread(serve, "diff", 2)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    inline = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    box = inline.locator(":scope > .lf-thread-reply leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "Half a thought")
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", SEAT_DIFF + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
    reply = card.locator(":scope > .lf-thread-reply leaf-text")
    expect(reply).to_be_focused()
    page.keyboard.type(" more")
    reply.evaluate("box => box.setSelectionRange(4, 4)")
    watch_blurs(reply)
    data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF)
    told(page)
    expect(card).to_be_hidden()
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", "Half a thought more")
    assert box.evaluate("box => [box.selectionStart, box.selectionEnd]") == [4, 4]
    # The user never left the editor on its way back.
    assert blurs(box) == 0
    page.keyboard.type(" tr")
    expect(box).to_have_js_property("value", "Half tr a thought more")
    expect(box).to_be_focused()
    # The same editor came back, so undo walks back through the card's typing too.
    page.keyboard.press("ControlOrMeta+z")
    expect(box).to_have_js_property("value", "Half a thought more")
    page.keyboard.press("ControlOrMeta+z")
    expect(box).to_have_js_property("value", "Half a thought")


# The browser's speech recognizer, replaced at its boundary as tests/runtime's
# dictation tests replace it: each instance records whether it was aborted, and a
# test hears words through its `onresult`.
FAKE_RECOGNITION = """
window.lfRecognizers = [];
window.SpeechRecognition = class {
  constructor() { this.aborted = false; window.lfRecognizers.push(this); }
  start() { setTimeout(() => this.onstart?.()); }
  stop() { setTimeout(() => this.onend?.()); }
  abort() { this.aborted = true; }
};
"""


def test_a_reply_dictated_on_the_diff_keeps_listening_as_its_thread_moves(
    browser, serve
):
    """The user dictates a reply on the diff line, and the patch moves the thread to
    its margin card and back. Leaf's dictation followed the editor's view and stopped
    on each move. It goes on with the editor, still listening, and writes what it
    hears into the same box wherever the thread stands."""
    url, root = seated_thread(serve, "diff", 2)
    page = open_page(browser, url, init_script=FAKE_RECOGNITION)
    resized(page, 1440, 900)
    inline = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    row = inline.locator(":scope > .lf-thread-reply")
    row.scroll_into_view_if_needed()
    row.locator("leaf-text").focus()
    row.locator(".lf-compose-dictate").click()
    page.wait_for_function("() => window.lfRecognizers.length === 1")
    heard = """words => window.lfRecognizers[0].onresult({
      results: [[{ transcript: words }]],
    })"""
    page.evaluate(heard, "Half a")
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", SEAT_DIFF + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
    reply = card.locator(":scope > .lf-thread-reply leaf-text")
    expect(reply).to_be_focused()
    page.evaluate(heard, "Half a thought")
    expect(reply).to_have_js_property("value", "Half a thought")
    data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF)
    told(page)
    box = row.locator("leaf-text")
    expect(box).to_be_focused()
    page.evaluate(heard, "Half a thought more")
    expect(box).to_have_js_property("value", "Half a thought more")
    assert page.evaluate("() => window.lfRecognizers.map(r => r.aborted)") == [False]


@pytest.mark.parametrize("card", ["open", "closed"])
def test_a_reply_box_left_by_tab_returns_to_the_diff_with_its_history(
    browser, serve, card
):
    """The user leaves the margin card's reply before the patch comes back: by Tab onto
    the margin (`open`), or by Shift+Tab to the card's Close and Enter (`closed`). Its
    editing session goes on: the diff line used to draw a fresh editor holding only
    the words, while the hidden card kept the one with the undo history. The diff line
    takes that editor."""
    url, root = seated_thread(serve, "diff", 2)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    inline = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    box = inline.locator(":scope > .lf-thread-reply leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "Half a thought")
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", SEAT_DIFF + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    shown = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
    reply = shown.locator(":scope > .lf-thread-reply leaf-text")
    expect(reply).to_be_focused()
    page.keyboard.type(" more")
    preview = page.locator(".lf-margin-preview")
    if card == "open":
        for _ in range(10):
            page.keyboard.press("Tab")
            if not preview.evaluate("card => card.contains(document.activeElement)"):
                break
    else:
        close = page.locator(".lf-margin-preview-close")
        for _ in range(10):
            page.keyboard.press("Shift+Tab")
            if close.evaluate("close => close.matches(':focus')"):
                break
        page.keyboard.press("Enter")
        expect(preview).to_be_hidden()
    expect(reply).not_to_be_focused()
    data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF)
    told(page)
    expect(shown).to_be_hidden()
    expect(box).to_have_js_property("value", "Half a thought more")
    box.focus()
    page.keyboard.press("ControlOrMeta+z")
    expect(box).to_have_js_property("value", "Half a thought")


@pytest.mark.parametrize("focus_route", ["close", "marker"])
def test_a_user_on_a_thread_returning_to_the_diff_goes_with_it(
    browser, serve, focus_route
):
    """The user focuses the margin card's Close, or on the thread's margin marker,
    when the patch comes back and the thread takes its seat on the diff line again.
    The node they focused goes with the margin's copy of the thread; they land on
    the thread where it now stands."""
    url, root = seated_thread(serve, "diff", 2)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    inline = page.locator(f'lf-diff .lf-page-thread[data-thread="{root}"]')
    data_model.cmd_data_set(
        serve.page_dir, "review-patch", SEAT_DIFF + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    expect(inline).to_have_count(0)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')
    if focus_route == "close":
        marker.click()
        close = page.locator(".lf-margin-preview-close")
        close.focus()
        expect(close).to_be_focused()
    else:
        marker.focus()
        expect(marker).to_be_focused()
    data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF)
    told(page)
    expect(inline).to_have_count(1)
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(inline).to_be_focused()


@pytest.mark.parametrize(
    ("kind", "finish"),
    # Each seat once, and each way the written reply ends.
    [
        ("task", "send"),
        ("bounded", "send"),
        ("bounded-short", "send"),
        ("diff", "clear"),
        ("margin", "reload"),
    ],
)
def test_a_thread_resolved_while_its_reply_is_written_keeps_the_user_on_it(
    browser, serve, kind, finish
):
    """A page seat retains its native editor, words and caret through settlement."""
    if kind == "margin":
        url = serve(OBLIGATION_PAGE)
        root = panel_comment(serve.page_dir, "Keep discussing", {"section": "bracket"})
    else:
        url, root = seated_thread(serve, kind, 2)
    page = open_page(browser, url)
    if kind == "margin":
        resized(page, 1440, 900)
        page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
    thread = page.locator(f'.lf-page-thread[data-thread="{root}"]')
    box = thread.locator(":scope > .lf-thread-reply leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "Half a thought")
    box.evaluate("box => box.setSelectionRange(4, 4)")
    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    rendered(page)
    expect(box).to_be_visible()
    expect(box).to_be_focused()
    expect(box).to_have_js_property("value", "Half a thought")
    assert box.evaluate("box => [box.selectionStart, box.selectionEnd]") == [4, 4]
    if finish == "reload":
        page.reload()
        wait_until_ready(page)
        # A resolved thread the page draws nowhere opens in the panel.
        open_panel_thread(page, root)
        settle = page.locator(".lf-fp-settle")
        expect(settle).to_have_accessible_name("Reopen")
        with sending(page, "reopen the thread with the saved reply"):
            settle.click()
        round_trip(page)
        expect(page.locator(PANEL_REPLY)).to_have_js_property("value", "Half a thought")
        return
    if finish == "clear":
        page.keyboard.press("ControlOrMeta+a")
        page.keyboard.press("Backspace")
        rendered(page)
        expect(box).to_be_visible()
        expect(box).to_be_focused()
        expect(box).to_have_js_property("value", "")
        assert box.evaluate("box => [box.selectionStart, box.selectionEnd]") == [0, 0]
        if kind == "margin":
            expect(thread).to_have_attribute("data-resolved", "true")
        else:
            # A seat in the flow holds the resolution behind its notice while the
            # thread is on screen.
            expect(thread.locator(".lf-thread-news")).to_contain_text("Resolved")
            expect(thread).to_have_attribute("data-resolved", "false")
        return
    page.keyboard.type(" tr")
    expect(box).to_have_js_property("value", "Half tr a thought")
    expect(page.locator(PANEL)).not_to_have_attribute("data-open", re.compile("."))
    with sending(page, "the reply"):
        thread.get_by_role("button", name="Send", exact=True).click()
    told(page)
    expect(thread).to_have_attribute("data-resolved", "false")
    expect(thread.locator(".lf-msg", has_text="Half tr a thought")).to_be_visible()


def _seat_manifest(patch):
    return {
        "files": [
            {
                "path": "app.py",
                "patch": patch,
            }
        ]
    }


def _refused_file(serve, page):
    """The file's next deferred patch fails to load, so its error box takes the place
    of the lines it had."""
    page.route(
        "**/api/deferred*",
        lambda route: route.fulfill(status=500, json={"error": "unavailable"}),
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        _seat_manifest(SEAT_DIFF.replace('+return "new"', '+return "newer"')),
    )
    told(page)
    expect(page.locator("lf-diff .lf-error")).to_contain_text("unavailable")
    consume_browser_errors(page, http_error_console(500))


def _refused_patch(serve, page):
    data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF + SEAT_DIFF)
    told(page)
    reported_browser_errors(
        page, 'leaf: <lf-diff id="patch"> failed: unified diff repeats file path app.py'
    )


@pytest.mark.parametrize(
    "change",
    [
        SEAT_DIFF + "@@ -9 +9 @@\n-old = 1\n+new = 1\n",
        SEAT_DIFF.replace('+return "new"', '+return "newer"'),
        SEAT_DIFF.replace("app.py", "other.py"),
        _refused_file,
        lambda serve, page: data_model.cmd_data_clear(serve.page_dir, "review-patch"),
        _refused_patch,
    ],
    ids=[
        "elsewhere",
        "on-the-line",
        "file-dropped",
        "file-refused",
        "source-cleared",
        "patch-refused",
    ],
)
def test_a_comment_being_written_on_a_diff_line_stays_in_hand_across_a_new_patch(
    browser, serve, change
):
    """The same drop one surface over: the comment box a diff seats on a line went
    with the rebuilt diff, and the user was left on the page. The draft stays about
    the patch it was written on, so the composer returns beside the diff and the user
    goes on typing in it at the same caret. That holds wherever the line goes: drawn
    anew, dropped with its file, behind its file's or the whole patch's failure, or
    with a source cleared."""
    url = serve(
        leaf_page(
            "diff",
            f'<h1 id="title">Review</h1>{SEAT_FILLER}<lf-diff id="patch" '
            f'source="review-patch"><pre></pre></lf-diff>{SEAT_FILLER}',
        )
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        _seat_manifest(SEAT_DIFF) if change is _refused_file else SEAT_DIFF,
    )
    page = open_page(browser, url)
    line = page.locator(
        'lf-diff [data-line-type="change-addition"][data-lf-datum=\'["app.py","new",1]\']'
    )
    line.scroll_into_view_if_needed()
    line.hover()
    page.get_by_role(
        "button", name="Comment on app.py · new line 1", exact=True
    ).click()
    box = page.locator(".lf-fab-input")
    expect(page.locator("lf-diff .lf-diff-thread-outlet .lf-fab-input")).to_be_focused()
    write(box, "Half a thought")
    box.evaluate("""box => {
      box.setSelectionRange(4, 4);
      window.blurs = 0;
      box.addEventListener('blur', () => window.blurs++);
    }""")
    if callable(change):
        change(serve, page)
    else:
        data_model.cmd_data_set(serve.page_dir, "review-patch", change)
    told(page)
    expect(page.locator("lf-diff .lf-diff-thread-outlet")).to_have_count(0)
    expect(box).to_be_focused()
    expect(box).to_be_in_viewport()
    expect(box).to_have_js_property("value", "Half a thought")
    assert box.evaluate("box => [box.selectionStart, box.selectionEnd]") == [4, 4]
    # The editor never leaves the document, so nothing has to put the user back.
    assert page.evaluate("window.blurs") == 0
    page.keyboard.type(" tr")
    expect(box).to_have_js_property("value", "Half tr a thought")
    expect(box).to_be_focused()


@pytest.mark.parametrize("native_move", [True, False])
def test_the_comment_box_keeps_the_user_typing_as_it_takes_its_seat_again(
    browser, serve, native_move
):
    """Folding a file through its summary hides the draft; reopening keeps its
    words available on the diff line, with and without native retained moves."""
    url = serve(
        leaf_page(
            "diff",
            f'<h1 id="title">Review</h1><lf-diff id="patch" source="review-patch">'
            f"<pre></pre></lf-diff>{SEAT_FILLER}",
        )
    )
    data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF)
    page = open_page(browser, url)
    if not native_move:
        page.evaluate("() => { Element.prototype.moveBefore = undefined; }")
    line = page.locator(
        'lf-diff [data-line-type="change-addition"][data-lf-datum=\'["app.py","new",1]\']'
    )
    comment = page.get_by_role(
        "button", name="Comment on app.py · new line 1", exact=True
    )
    line.hover()
    comment.click()
    seated = page.locator("lf-diff .lf-diff-thread-outlet .lf-fab-input")
    expect(seated).to_be_focused()
    box = page.locator(".lf-fab-input")
    write(box, "Half a thought")
    summary = page.locator("lf-diff .lf-diff-file > details > summary").first
    summary.click()
    expect(seated).to_have_count(0)
    expect(box).to_be_hidden()
    summary.click()
    line.hover()
    comment.click()
    expect(box).to_have_js_property("value", "Half a thought")
    expect(seated).to_be_focused()
    page.keyboard.type(" more")
    expect(seated).to_have_js_property("value", "Half a thought more")
