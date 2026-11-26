"""Threads drawn in the page's own flow, on a seat or a diff line: what arriving turns,
settlement and new patches do to their reply box and to the reading around them."""

import re

import pytest
from interact_support import ROOT, append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATION_PAGE, live_url, panel_comment
from render_cases_navigation import source_revision
from render_harness import (
    EXAMPLE_PACKAGES,
    FAKE_RECOGNITION,
    PANEL,
    RELEASE_FOCUS,
    consume_browser_errors,
    expect_preview_words,
    leaf_page,
    open_page,
    reported_browser_errors,
    resized,
    round_trip,
    scroll_settled,
    sending,
    stored_drafts,
    told,
    write,
)

from browser.drafts import choose_comment_target
from browser.threads import (
    PANEL_REPLY,
    SEAT_DIFF,
    SEAT_FILLER,
    SEAT_WORDS,
    THIRTY_LINES,
    append_agent_reply,
    append_user_reply,
    clear_of_the_panel,
    long_diff_thread,
    open_panel_thread,
    paste,
    seated_page,
    summarize_thread,
    to_window_foot,
)
from leaf.log import event_log as events_model
from leaf.records import page_data as page_data_model
from leaf.source.render_checks import rendered, wait_until_ready
from leaf_dev.browser import PANEL_THREAD, choose_threads_in_panel

pytestmark = pytest.mark.shifts_unsurveyed

# A widget showing one case at a time of the run its `source` binds, from a package
# of the suite's own. Each case is a datum that keeps its identity across new values
# (`data-lf-identity`), and the shown case seats the threads on it.
RECORDS = ROOT / "tests/fixtures/packages/records"
RECORDS_RUN = {
    "cases": [
        {"id": "status-column", "title": "Run list status"},
        {"id": "detail-link", "title": "Run detail link"},
        {"id": "desktop-navigation", "title": "Desktop navigation"},
    ]
}
REVIEW = '<lf-test-review id="review" source="run"></lf-test-review>'


def records_page(serve):
    """A page whose `review` shows the cases of the run."""
    url = live_url(
        serve(leaf_page("Cases", REVIEW), packages=(*EXAMPLE_PACKAGES, RECORDS))
    )
    page_data_model.cmd_data_set(serve.page_dir, "run", RECORDS_RUN)
    return url


def test_a_widget_seats_the_thread_about_itself_and_none_inside_it(browser, serve):
    """A widget is offered the thread anchored to its element and nothing inside it,
    and the comment box that starts one. A thread on a passage of its words points
    into the widget rather than standing in the place it offers, so it keeps its margin
    entry, and so does the thread on a widget that returns no outlet."""
    url = serve(
        leaf_page(
            "seats",
            '<h1 id="h">Three jobs</h1><lf-test-plan id="hub" label="Before the frost">'
            '<lf-test-task id="jobs" status="active" talk><strong>Which jobs are '
            "worth starting?</strong> The mounts came down in January.</lf-test-task>"
            '<lf-test-task id="quiet" status="active"><strong>Stain the fence</strong>'
            "</lf-test-task></lf-test-plan>",
        )
    )

    def comment(anchor, text):
        return append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": text,
                "anchor": anchor,
            },
        )["id"]

    own = comment({"section": "jobs"}, "About the whole task.")
    passage = comment(
        {"section": "jobs", "quote": "The mounts came down in January."},
        "About these words.",
    )
    unseated = comment({"section": "quiet"}, "About a task that seats nothing.")
    page = open_page(browser, url)
    resized(page, 1440, 900)
    seat = page.locator("#jobs > .lf-test-threads")
    expect(seat.locator(".lf-page-thread")).to_have_count(1)
    expect(seat.locator(f'.lf-page-thread[data-lf-thread="{own}"]')).to_be_visible()
    for elsewhere in (passage, unseated):
        drawn = page.locator(f'.lf-page-thread[data-lf-thread="{elsewhere}"]')
        expect(drawn).to_have_count(0)
    for target in ("jobs", "quiet"):
        marker = page.locator(f'[data-lf-margin-for="{target}"] .lf-margin-marker')
        expect(marker).to_have_count(1)

    # The task's Comment control opens the box in its seat, under the thread there.
    page.locator("#jobs > .lf-test-comment").click()
    expect(seat.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator("#quiet > .lf-test-comment")).to_have_count(0)


@pytest.mark.watch_shifts
def test_a_resolution_from_elsewhere_moves_nothing_after_a_diff_thread(browser, serve):
    """A diff line's thread resolved elsewhere stays open behind its notice.

    Resolving folds the thread into its outlet's Resolved disclosure, which would lift
    the paragraph after the diff under the reader."""
    url = serve(
        leaf_page(
            "inline diff thread",
            '<h1 id="title">Review</h1><lf-diff id="patch" source="review-patch">'
            '</lf-diff><p id="after">Reading the paragraph after the diff.</p>',
        )
    )
    page_data_model.cmd_data_set(
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
    thread = page.locator(f'lf-diff .lf-page-thread[data-lf-thread="{root}"]')
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
    notice = thread.get_by_role("button", name="1 new", exact=True)
    expect(notice).to_be_visible()
    expect_preview_words(notice, "Resolved")
    rendered(page)
    assert after.bounding_box() == before
    notice.click()
    expect(thread).to_have_attribute("data-lf-resolved", "true")
    expect(thread).to_be_hidden()
    expect(page.locator("lf-diff .lf-resolved-summary")).to_have_text(
        "Resolved · Keep this check beside the changed line"
    )


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
    thread = page.locator(f'lf-diff .lf-page-thread[data-lf-thread="{root}"]')
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
    notice = thread.get_by_role("button", name="1 new", exact=True)
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
    thread = page.locator(f'lf-diff .lf-page-thread[data-lf-thread="{root}"]')
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
        f'lf-diff .lf-page-thread[data-lf-thread="{root}"] .lf-msg[data-lf-author=agent]'
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
                f'source="review-patch"></lf-diff>{SEAT_FILLER}',
            ).replace("<body>", f'<body data-annotations="{annotations}">', 1)
        )
        page_data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF)
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
    """A diff draws its threads in its own shadow tree. A landing whose climb stopped at
    that root would never meet the page's scroller and would read a thread taller than
    the window as one that fits, so the growth reveal would move nothing."""
    url, root = seated_thread(serve, "diff", 12)
    page = open_page(browser, url)
    thread = page.locator(f'.lf-page-thread[data-lf-thread="{root}"]')
    box = thread.locator(":scope > .lf-thread-reply leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "First line")
    to_window_foot(page, box, 60)
    paste(page, THIRTY_LINES)
    assert clear_of_the_panel(
        page, thread.locator(":scope > .lf-thread-reply .lf-compose-submit")
    )


@pytest.mark.parametrize(
    ("kind", "engine"),
    [("task", "browser"), ("bounded", "browser"), ("task", "firefox_browser")],
)
def test_an_agent_turn_arriving_holds_still_the_page_box_being_typed_in(
    request, serve, kind, engine
):
    """A new turn going in above the reply box the user is typing in must not push it,
    caret and all, below the fold. The user in a thread reads its news as it comes, as
    in a chat: the turn draws at once and the box stands where it was, what stood above
    it moving up by the turn, in a bounded block as on the page, and in Firefox, whose
    scroll anchoring differs from Chromium's."""
    messages = 3
    url, root = seated_thread(serve, kind, messages)
    page = open_page(request.getfixturevalue(engine), url)
    thread = page.locator(f'.lf-page-thread[data-lf-thread="{root}"]')
    box = thread.locator(":scope > .lf-thread-reply leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "Half a thought")
    to_window_foot(page, box, 50)
    before = box.evaluate("box => box.getBoundingClientRect().top")
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
    expect(thread.locator(".lf-thread-news")).to_have_count(0)
    expect(box).to_be_focused()
    assert box.evaluate("box => box.getBoundingClientRect().top") == pytest.approx(
        before, abs=1
    )


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize("first", ["above", "on screen"])
def test_an_edit_above_the_paragraph_read_holds_it_with_the_reply_box_scrolled_away(
    request, serve, first, engine
):
    """The user writes in a thread's reply box, scrolls up out of it to read an earlier
    message's second paragraph, and an edit from another tab grows that message's first
    paragraph. A redraw that replaced every paragraph of the message, the node the
    browser's scroll anchoring held among them, would move the paragraph they read down
    by what it grew, since neither engine anchors again on a node that replaces its
    anchor; the redraw keeps the paragraphs the edit leaves, so with the first paragraph
    above the window anchoring holds the one read. With the first on screen, anchoring
    holds that paragraph, the growth inside it, and the seat holds nothing, its focus
    out of view; the reading's hold keeps what stands at the reading line."""
    url, host = seated_page(serve, "task")
    # Words that repeat nowhere else, so the line at the reading edge names one place
    # whatever width wraps it.
    second = "The second paragraph, being read. " + " ".join(
        f"Sentence {n} of the paragraph being read wraps with the rest."
        for n in range(9)
    )
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Opening remark.\n\n" + second,
            "anchor": {"section": host[1:]},
        },
    )["id"]
    for n in range(8):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "agent": "Codex",
                "parent": root,
                "revision": 1,
                "text": f"Message {n + 2}. " + SEAT_WORDS * 2,
            },
        )
    page = open_page(request.getfixturevalue(engine), url)
    resized(page, 1440, 900)
    thread = page.locator(f'.lf-page-thread[data-lf-thread="{root}"]')
    box = thread.locator(":scope > .lf-thread-reply leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "Half a thought")
    # The edit reveals its caret in the editor's next frame (annotations/editor-view.js), so the
    # scroll away waits for it: made before it, the reveal brings the box back.
    rendered(page)
    read = thread.locator(".lf-msg p", has_text="The second paragraph")
    page.evaluate(
        """([node, at]) => document.scrollingElement.scrollBy({
          top: node.getBoundingClientRect().top - at, behavior: 'instant'})""",
        [read.element_handle(), 150 if first == "on screen" else -60],
    )
    scroll_settled(page)
    expect(box).to_be_focused()
    expect(box).not_to_be_in_viewport()
    before = read.evaluate("p => p.getBoundingClientRect().top")
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "user",
            "message": root,
            "text": "Opening remark, grown by an edit in another tab. "
            + SEAT_WORDS * 3
            + "\n\n"
            + second,
        },
    )
    told(page)
    expect(thread.locator(".lf-msg").first).to_contain_text("grown by an edit")
    rendered(page)
    expect(box).to_be_focused()
    assert read.evaluate("p => p.getBoundingClientRect().top") == pytest.approx(
        before, abs=1
    )


def test_resolving_a_long_page_thread_by_its_button_leaves_the_page_still(
    browser, serve
):
    """The pressed Resolve leaves with the state it changed, and the thread folds into
    its seat's Resolved disclosure, taking the focus to the disclosure's summary. A
    landing on the thread that took it back would make the nearest edge of a thread
    taller than the window a jump to its head."""
    kind = "verdict"
    url, root = seated_thread(serve, kind, 12)
    page = open_page(browser, url)
    thread = page.locator(f'.lf-page-thread[data-lf-thread="{root}"]')
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
    comes back out when reopened. With nothing landing it either way, the summary the
    user was located on would go above the window, and the reopened thread with it."""
    url, root = seated_thread(serve, "diff", 12)
    page = open_page(browser, url)
    thread = page.locator(f'.lf-page-thread[data-lf-thread="{root}"]')
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
    thread = page.locator(f'.lf-page-thread[data-lf-thread="{root}"]')
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
    and holding the box there would move what they were reading. A box shown inside a
    bounded block the page has scrolled away is off screen too, or the growth the
    block cannot take is handed to the page under the reader."""
    messages = 1 if kind == "bounded-short" else 3
    url, root = seated_thread(serve, kind, messages)
    page = open_page(browser, url)
    thread = page.locator(f'.lf-page-thread[data-lf-thread="{root}"]')
    box = thread.locator(":scope > .lf-thread-reply leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "Half a thought")
    rendered(page)
    page.evaluate(
        """node => document.scrollingElement.scrollBy({
          top: node.getBoundingClientRect().top - innerHeight - 400,
          behavior: 'instant'})""",
        thread.element_handle(),
    )
    scroll_settled(page)
    expect(box).to_be_focused()
    assert box.bounding_box()["y"] > page.evaluate("innerHeight")
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
    names the patch it was written on, and the reply box the user was typing in goes
    with it, where focus falling to the page would let the next letters run page
    commands. The
    user follows the thread to its margin card, typing on in the same editor at the
    same caret, with its undo history, and no task between the two finds them on
    the page."""
    url, root = seated_thread(serve, "diff", 2, annotations)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    inline = page.locator(f'lf-diff .lf-page-thread[data-lf-thread="{root}"]')
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
    page_data_model.cmd_data_set(
        serve.page_dir, "review-patch", SEAT_DIFF + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    expect(inline).to_have_count(0)
    # A page drawing no margin puts the thread up in the panel, its reply in the
    # panel's field; an overlay margin in its card.
    if annotations == "page":
        expect(page.locator(f'{PANEL_THREAD}[data-lf-thread="{root}"]')).to_be_visible()
        reply = page.locator(PANEL_REPLY)
    else:
        card = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]'
        )
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
    margin card, and the thread takes its seat on the diff line again. A card closing
    under the user that landed them on the banner would leave the next letters running
    page commands. They go on in the same editor on the diff line, at the same caret, with
    its undo history."""
    url, root = seated_thread(serve, "diff", 2)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    inline = page.locator(f'lf-diff .lf-page-thread[data-lf-thread="{root}"]')
    box = inline.locator(":scope > .lf-thread-reply leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "Half a thought")
    page_data_model.cmd_data_set(
        serve.page_dir, "review-patch", SEAT_DIFF + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]')
    reply = card.locator(":scope > .lf-thread-reply leaf-text")
    expect(reply).to_be_focused()
    page.keyboard.type(" more")
    reply.evaluate("box => box.setSelectionRange(4, 4)")
    watch_blurs(reply)
    page_data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF)
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


def test_a_reply_dictated_on_the_diff_keeps_listening_as_its_thread_moves(
    browser, serve
):
    """The user dictates a reply on the diff line, and the patch moves the thread to
    its margin card and back. Dictation that followed the editor's view would stop on
    each move. It goes on with the editor, still listening, and writes what it
    hears into the same box wherever the thread stands."""
    url, root = seated_thread(serve, "diff", 2)
    page = open_page(browser, url, init_script=FAKE_RECOGNITION)
    resized(page, 1440, 900)
    inline = page.locator(f'lf-diff .lf-page-thread[data-lf-thread="{root}"]')
    row = inline.locator(":scope > .lf-thread-reply")
    row.scroll_into_view_if_needed()
    row.locator("leaf-text").focus()
    row.locator(".lf-compose-dictate").click()
    page.wait_for_function("() => window.lfRecognizers.length === 1")
    heard = """words => window.lfRecognizers[0].onresult({
      results: [[{ transcript: words }]],
    })"""
    page.evaluate(heard, "Half a")
    page_data_model.cmd_data_set(
        serve.page_dir, "review-patch", SEAT_DIFF + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]')
    reply = card.locator(":scope > .lf-thread-reply leaf-text")
    expect(reply).to_be_focused()
    page.evaluate(heard, "Half a thought")
    expect(reply).to_have_js_property("value", "Half a thought")
    page_data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF)
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
    editing session goes on: a diff line drawing a fresh editor would hold only
    the words, while the hidden card kept the one with the undo history. The diff line
    takes that editor."""
    url, root = seated_thread(serve, "diff", 2)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    inline = page.locator(f'lf-diff .lf-page-thread[data-lf-thread="{root}"]')
    box = inline.locator(":scope > .lf-thread-reply leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "Half a thought")
    page_data_model.cmd_data_set(
        serve.page_dir, "review-patch", SEAT_DIFF + "@@ -9 +9 @@\n-old = 1\n+new = 1\n"
    )
    told(page)
    shown = page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]')
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
    page_data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF)
    told(page)
    expect(shown).to_be_hidden()
    expect(box).to_have_js_property("value", "Half a thought more")
    box.focus()
    page.keyboard.press("ControlOrMeta+z")
    expect(box).to_have_js_property("value", "Half a thought")


def test_a_rewrite_written_in_a_diff_seat_comes_back_there_with_the_panel_chosen(
    browser, serve
):
    """A rewrite of the user's message, written in the seat a diff line gives its
    thread, comes back in that seat after a reload though the user chose the panel for
    threads: the seat shows the thread, so the rewrite's return fills its editor there
    rather than opening the thread where the choice says."""
    url, root = seated_thread(serve, "diff", 2)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    choose_threads_in_panel(page)
    inline = page.locator(f'lf-diff .lf-page-thread[data-lf-thread="{root}"]')
    words = inline.locator(".lf-msg .lf-msg-text").first
    words.scroll_into_view_if_needed()
    words.dblclick()
    editor = inline.locator(".lf-msg-editor leaf-text")
    expect(editor).to_be_focused()
    page.keyboard.press("ControlOrMeta+End")
    page.keyboard.type(" Twice.")
    written = editor.evaluate("editor => editor.value")
    assert written.endswith(" Twice.")
    page.wait_for_function("navigation.transition === null")
    page.reload()
    wait_until_ready(page)
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", written)
    expect(page.locator(PANEL_THREAD)).to_have_count(0)


def test_a_rewrite_of_a_folded_message_in_a_diff_seat_comes_back_there(browser, serve):
    """A rewrite of the user's message, written in a diff line's seat after they opened
    the summary folding it, comes back in that seat after a reload though the user
    chose the panel for threads and the seat draws the summary folded again: the seat
    shows the thread, so the rewrite opens its fold rather than moving to the panel."""
    url, root = seated_thread(serve, "diff", 1)
    asked = append_agent_reply(serve.page_dir, root, "Which file goes first?")
    mine = append_user_reply(serve.page_dir, root, "The config, then.")
    last = append_agent_reply(serve.page_dir, root, "The config goes first.")
    append_user_reply(serve.page_dir, root, "Keep the latest in view.")
    summarize_thread(serve.page_dir, asked["id"], last["id"], "The config first.")
    page = open_page(browser, url)
    resized(page, 1440, 900)
    choose_threads_in_panel(page)
    inline = page.locator(f'lf-diff .lf-page-thread[data-lf-thread="{root}"]')
    toggle = inline.locator(".lf-summary-expand")
    toggle.scroll_into_view_if_needed()
    toggle.click()
    words = inline.locator(f'.lf-msg[data-lf-event="{mine["id"]}"] .lf-msg-text')
    words.dblclick()
    editor = inline.locator(".lf-msg-editor leaf-text")
    expect(editor).to_be_focused()
    page.keyboard.press("ControlOrMeta+End")
    page.keyboard.type(" Twice.")
    written = editor.evaluate("editor => editor.value")
    assert written.endswith(" Twice.")
    page.wait_for_function("navigation.transition === null")
    page.reload()
    wait_until_ready(page)
    expect(editor).to_be_focused()
    expect(editor).to_have_js_property("value", written)
    expect(page.locator(PANEL_THREAD)).to_have_count(0)


def test_resume_writing_a_reply_its_seat_still_draws_leaves_a_way_back(browser, serve):
    """Resume writing takes the user from where they read to the reply they left in a
    diff line's seat, though the seat stayed drawn all the while, and Back takes them
    back to where they read, as every trip Resume writing makes does (records/drafts.js,
    `createWritingResume`)."""
    url, root = seated_thread(serve, "diff", 2)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    page.evaluate("location.hash = '#title'")
    page.wait_for_function("navigation.transition === null")
    inline = page.locator(f'lf-diff .lf-page-thread[data-lf-thread="{root}"]')
    box = inline.locator(":scope > .lf-thread-reply leaf-text")
    box.scroll_into_view_if_needed()
    write(box, "Half a thought")
    end = page.locator("p", has_text="Filler paragraph 39").last
    end.scroll_into_view_if_needed()
    end.click()
    expect(box).not_to_be_focused()
    scroll_settled(page)
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(box).to_be_focused()
    expect(end).not_to_be_in_viewport()
    page.wait_for_function("navigation.transition === null")
    page.go_back()
    expect(end).to_be_in_viewport()
    expect(box).not_to_be_focused()


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
    inline = page.locator(f'lf-diff .lf-page-thread[data-lf-thread="{root}"]')
    page_data_model.cmd_data_set(
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
        # `told` waits only for the state, and the margin row it brought stays hidden,
        # so unfocusable, until layout places it (annotation-theme.css).
        expect(marker).to_be_visible()
        marker.focus()
        expect(marker).to_be_focused()
    page_data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF)
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
    thread = page.locator(f'.lf-page-thread[data-lf-thread="{root}"]')
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
        # The entry names the card's thread, so the reload opens it again, in the panel,
        # since the page draws a resolved thread nowhere.
        open_panel_thread(page, root)
        settle = page.locator(".lf-fp-thread-controls :is(.lf-resolve, .lf-reopen)")
        expect(settle).to_have_accessible_name("✓ Resolved by Codex · Reopen")
        with sending(page, "reopen the thread with the saved reply"):
            settle.click()
        round_trip(page)
        # Reopened, the thread goes back beside its passage, its reply with it.
        card_reply = page.locator(
            f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]'
            " > .lf-thread-reply leaf-text"
        )
        expect(card_reply).to_have_js_property("value", "Half a thought")
        return
    if finish == "clear":
        page.keyboard.press("ControlOrMeta+a")
        page.keyboard.press("Backspace")
        rendered(page)
        expect(box).to_be_visible()
        expect(box).to_be_focused()
        expect(box).to_have_js_property("value", "")
        assert box.evaluate("box => [box.selectionStart, box.selectionEnd]") == [0, 0]
        # A seat in the flow holds the resolution behind its notice while the thread is
        # on screen.
        notice = thread.locator(".lf-thread-news")
        expect(notice).to_have_text("1 new")
        expect_preview_words(notice, "Resolved")
        expect(thread).to_have_attribute("data-lf-resolved", "false")
        return
    page.keyboard.type(" tr")
    expect(box).to_have_js_property("value", "Half tr a thought")
    expect(page.locator(PANEL)).not_to_have_attribute("data-lf-open", re.compile("."))
    with sending(page, "the reply"):
        thread.get_by_role("button", name="Send", exact=True).click()
    told(page)
    expect(thread).to_have_attribute("data-lf-resolved", "false")
    expect(thread.locator(".lf-msg", has_text="Half tr a thought")).to_be_visible()


def test_an_agent_resolving_the_thread_the_user_is_on_waits_behind_its_notice(
    browser, serve
):
    """News in the thread the user stands on shows at once, but its resolution would
    fold the thread into the seat's closed Resolved disclosure and take them to its
    summary, out of the thread they were in. With nothing written in its box, the
    thread stays open with the user on it and "1 new" saying the resolution waits, and
    pressing the notice shows it, folding the thread into Resolved."""
    url, root = seated_thread(serve, "task", 2)
    page = open_page(browser, url)
    thread = page.locator(f'.lf-page-thread[data-lf-thread="{root}"]')
    thread.scroll_into_view_if_needed()
    thread.focus()
    expect(thread).to_be_focused()
    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "Codex", "parent": root},
    )
    told(page)
    notice = thread.get_by_role("button", name="1 new", exact=True)
    expect_preview_words(notice, "Resolved")
    rendered(page)
    expect(thread).to_have_attribute("data-lf-resolved", "false")
    expect(thread).to_be_visible()
    expect(thread).to_be_focused()

    notice.click()
    expect(page.locator(".lf-resolved-summary")).to_contain_text(
        "Resolved · Opening remark."
    )
    expect(thread).to_have_attribute("data-lf-resolved", "true")
    expect(thread).to_be_hidden()


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
    """The file's next patch describes another file, so its error box takes the place
    of the lines it had."""
    page_data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        _seat_manifest(SEAT_DIFF.replace("app.py", "other.py")),
    )
    told(page)
    expect(page.locator("lf-diff .lf-error")).to_contain_text(
        "does not contain that one file"
    )
    consume_browser_errors(page, '<lf-diff id="patch"> failed: ')


def _refused_patch(serve, page):
    page_data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF + SEAT_DIFF)
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
        lambda serve, page: page_data_model.cmd_data_clear(
            serve.page_dir, "review-patch"
        ),
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
    """The same drop one surface over: the comment box a diff seats on a line would go
    with the rebuilt diff, leaving the user on the page. The draft stays about
    the patch it was written on, so the composer returns beside the diff and the user
    goes on typing in it at the same caret. That holds wherever the line goes: drawn
    anew, dropped with its file, behind its file's or the whole patch's failure, or
    with a source cleared."""
    url = serve(
        leaf_page(
            "diff",
            f'<h1 id="title">Review</h1>{SEAT_FILLER}<lf-diff id="patch" '
            f'source="review-patch"></lf-diff>{SEAT_FILLER}',
        )
    )
    page_data_model.cmd_data_set(
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
        page_data_model.cmd_data_set(serve.page_dir, "review-patch", change)
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


def _files_manifest(*paths):
    """A manifest of `SEAT_DIFF`'s one change made to each of `paths`, in that order."""
    return {
        "files": [
            {"path": path, "patch": SEAT_DIFF.replace("app.py", path)} for path in paths
        ]
    }


@pytest.mark.parametrize(
    "change", ["files-reordered", "file-dropped", "source-cleared"]
)
def test_a_comment_being_written_on_a_diff_file_stays_the_same_editor_across_a_new_patch(
    browser, serve, change
):
    """The comment box chosen onto a file's row with `s` stands in that file's outlet.
    A diff's file is pinned to the patch the user saw, as its lines are (it marks no
    `data-lf-identity`), so a new patch returns the box beside the diff, whether it
    moves the file, drops it or clears the source. It is the same editor throughout:
    it never blurs, keeps its words, selection and focus, brings its undo history, and
    takes the user's next keys."""
    url = serve(
        leaf_page(
            "diff",
            f'<h1 id="title">Review</h1>{SEAT_FILLER}<lf-diff id="patch" '
            f'source="review-patch"></lf-diff>{SEAT_FILLER}',
        )
    )
    page_data_model.cmd_data_set(
        serve.page_dir, "review-patch", _files_manifest("app.py", "lib.py")
    )
    page = open_page(browser, url)
    choose_comment_target(page, 'lf-diff [data-lf-datum=\'["lib.py","file"]\']')
    box = page.locator(".lf-fab-input")
    seated = page.locator(
        'lf-diff .lf-diff-file-thread-outlet[data-lf-thread-datum=\'["lib.py","file"]\']'
    )
    expect(seated.locator(".lf-fab-input")).to_be_focused()
    page.keyboard.type("Keep this draft")
    page.keyboard.press("Shift+ArrowLeft")
    selection = box.evaluate("node => [node.selectionStart, node.selectionEnd]")
    watch_blurs(box)
    if change == "source-cleared":
        page_data_model.cmd_data_clear(serve.page_dir, "review-patch")
    else:
        paths = ("lib.py", "app.py") if change == "files-reordered" else ("app.py",)
        page_data_model.cmd_data_set(
            serve.page_dir, "review-patch", _files_manifest(*paths)
        )
    told(page)
    expect(seated).to_have_count(0)
    expect(box).to_be_focused()
    expect(box).to_be_in_viewport()
    expect(box).to_have_js_property("value", "Keep this draft")
    assert box.evaluate("node => [node.selectionStart, node.selectionEnd]") == selection
    assert blurs(box) == 0
    # Nothing was typed after the patch, so an undo that changes the words reaches
    # back past the move: the editor kept is the one typed into.
    page.keyboard.press("ControlOrMeta+z")
    expect(box).not_to_have_js_property("value", "Keep this draft")
    undone, start, end = box.evaluate(
        "node => [node.value, node.selectionStart, node.selectionEnd]"
    )
    page.keyboard.type(" a thought")
    expect(box).to_have_js_property(
        "value", f"{undone[:start]} a thought{undone[end:]}"
    )


def test_a_comment_being_written_on_a_kept_datum_keeps_its_seat_as_its_data_reorders(
    browser, serve
):
    """A datum that keeps its identity across new values (`data-lf-identity`) keeps
    the comment box seated on it. A new value that reorders the data moves the datum
    with its outlet, and the box in it is the same editor: it never blurs, keeps its
    words, selection and focus, and brings its undo history."""
    page = open_page(browser, records_page(serve))
    first = RECORDS_RUN["cases"][0]["id"]
    case = page.locator(f'#review .test-case[data-lf-datum="{first}"]')
    choose_comment_target(page, f'#review .test-case[data-lf-datum="{first}"]')
    field = case.locator(".test-threads .lf-fab-input")
    expect(field).to_be_focused()
    page.keyboard.type("Keep this draft while the case order changes")
    page.keyboard.press("Shift+ArrowLeft")
    selection = field.evaluate("node => [node.selectionStart, node.selectionEnd]")
    watch_blurs(field)
    page_data_model.cmd_data_set(
        serve.page_dir, "run", {"cases": RECORDS_RUN["cases"][::-1]}
    )
    told(page)
    expect(page.locator("#review .test-case").last).to_have_attribute(
        "data-lf-datum", first
    )
    expect(field).to_be_focused()
    expect(field).to_have_js_property(
        "value", "Keep this draft while the case order changes"
    )
    assert (
        field.evaluate("node => [node.selectionStart, node.selectionEnd]") == selection
    )
    assert blurs(field) == 0
    # The editor kept is the one typed into, so its undo history came with it.
    page.keyboard.press("ControlOrMeta+z")
    expect(field).not_to_have_js_property(
        "value", "Keep this draft while the case order changes"
    )


def test_a_comment_being_written_on_a_kept_datum_keeps_its_seat_under_the_panel_s_row(
    browser, serve
):
    """News leaves the comment box the user is typing in seated in its datum's
    outlet while the outlet's foot stands under the floating panel's row and the field
    stands clear of the row."""
    url = serve(
        leaf_page(
            "Cases mid-page",
            f"<h1>Review the cases</h1>{SEAT_FILLER}<section>{REVIEW}</section>"
            f"{SEAT_FILLER}",
        ),
        packages=(*EXAMPLE_PACKAGES, RECORDS),
    )
    page_data_model.cmd_data_set(serve.page_dir, "run", RECORDS_RUN)
    page = open_page(browser, url)
    resized(page, 390, 760)
    case = page.locator("#review .test-case:not([hidden])")
    choose_comment_target(page, "#review .test-case:not([hidden])")
    field = case.locator(".test-threads .lf-fab-input")
    expect(field).to_be_focused()
    page.keyboard.type("Keep the return route")
    rendered(page)
    places = """(field, panel) => {
      const outlet = field.closest('.test-threads').getBoundingClientRect();
      const row = document.querySelector(panel).getBoundingClientRect();
      return {field: field.getBoundingClientRect().bottom,
        outlet: outlet.bottom, row: row.top};
    }"""
    at = field.evaluate(places, PANEL)
    # The row's top falls midway between the field's foot and the outlet's.
    gap = (at["outlet"] - at["field"]) / 2
    page.mouse.move(195, 300)
    before = page.evaluate("scrollY")
    page.mouse.wheel(0, at["outlet"] - at["row"] - gap)
    page.wait_for_function("y => scrollY !== y", arg=before)
    scroll_settled(page)
    at = field.evaluate(places, PANEL)
    assert at["field"] <= at["row"] < at["outlet"], at
    case.locator(".test-threads").evaluate(
        """outlet => {
          window.lfSeatLeft = 0;
          new MutationObserver((records) => {
            for (const record of records)
              for (const node of record.removedNodes)
                if (node.classList?.contains('lf-fab-bar')) window.lfSeatLeft++;
          }).observe(outlet, {childList: true});
        }"""
    )
    title = "The run list keeps its return route"
    page_data_model.cmd_data_set(
        serve.page_dir,
        "run",
        {
            "cases": [
                RECORDS_RUN["cases"][0] | {"title": title},
                *RECORDS_RUN["cases"][1:],
            ]
        },
    )
    told(page)
    expect(case.locator("h3")).to_have_text(title)
    rendered(page)
    assert page.evaluate("window.lfSeatLeft") == 0, "the comment box left its seat"
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "Keep the return route")


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
            f"</lf-diff>{SEAT_FILLER}",
        )
    )
    page_data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF)
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


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_thread_on_a_diff_line_follows_its_file_to_the_margin_and_back(
    request, serve, engine
):
    """A diff seats a thread on a line only while the line's file is open. Folding the
    file changes no data, so the diff says that what it holds moved (`lf-layout`) and
    Leaf asks it for its seats again: the thread goes to the margin, where the user
    still reaches it, and takes its seat on the line again as the file opens. A thread
    left seated would stand inside the closed file, with no entry in the margin."""
    url, root = seated_thread(serve, "diff", 2)
    page = open_page(request.getfixturevalue(engine), url)
    resized(page, 1440, 900)
    inline = page.locator(f'lf-diff .lf-page-thread[data-lf-thread="{root}"]')
    entry = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    expect(inline).to_be_visible()
    expect(entry).to_have_count(0)
    summary = page.locator("lf-diff .lf-diff-file > details > summary").first
    summary.click()
    expect(inline).to_have_count(0)
    expect(entry).to_have_count(1)
    summary.click()
    expect(inline).to_be_visible()
    expect(entry).to_have_count(0)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize("written", ["comment", "reply"])
def test_a_box_written_in_a_widget_taken_off_the_page_keeps_its_words_and_the_user(
    request, serve, engine, written
):
    """A script takes the whole diff off the page while the user writes in a box seated
    in it: the comment box on one of its lines, or the reply box of a thread seated
    there. A widget releases a node it removes itself (`threadSurface(…).release`), but
    nothing tells a widget it is about to go, so Leaf returns the editor as it sees the
    widget leave: the comment box to the page's own place for it, the reply to its
    thread's view in the panel. Either way the user goes on typing in it at the same
    caret, the task after the removal already finds them there rather than on the
    page, where the next letters would run page commands, and the server holds the
    words as the draft another tab or a reload finds."""
    if written == "comment":
        url = serve(
            leaf_page(
                "diff",
                f'<h1 id="title">Review</h1>{SEAT_FILLER}<lf-diff id="patch" '
                f'source="review-patch"></lf-diff>{SEAT_FILLER}',
            )
        )
        page_data_model.cmd_data_set(serve.page_dir, "review-patch", SEAT_DIFF)
        page = open_page(request.getfixturevalue(engine), url)
        resized(page, 1440, 900)
        line = page.locator(
            'lf-diff [data-line-type="change-addition"][data-lf-datum=\''
            '["app.py","new",1]\']'
        )
        line.scroll_into_view_if_needed()
        line.hover()
        page.get_by_role(
            "button", name="Comment on app.py · new line 1", exact=True
        ).click()
        box = page.locator("lf-diff .lf-diff-thread-outlet .lf-fab-input")
        returned = page.locator(".lf-fab-input")
    else:
        url, root = seated_thread(serve, "diff", 2)
        page = open_page(request.getfixturevalue(engine), url)
        resized(page, 1440, 900)
        box = page.locator(
            f'lf-diff .lf-page-thread[data-lf-thread="{root}"] '
            "> .lf-thread-reply leaf-text"
        )
        box.scroll_into_view_if_needed()
        returned = page.locator(PANEL_REPLY)
    write(box, "Half a thought")
    box.evaluate("box => box.setSelectionRange(4, 4)")
    expect(box).to_be_focused()
    # The removal takes the editor out of the document, and focus with it. The next
    # task is the first in which a key could arrive.
    left = page.evaluate(
        """() => {
          document.querySelector('#patch').remove();
          const onThePage = () => document.activeElement === document.body;
          const dropped = onThePage();
          return new Promise((resolve) =>
            setTimeout(() => resolve({dropped, stranded: onThePage()})));
        }"""
    )
    assert left == {"dropped": True, "stranded": False}
    expect(page.locator("lf-diff")).to_have_count(0)
    expect(returned).to_be_focused()
    expect(returned).to_have_js_property("value", "Half a thought")
    assert returned.evaluate("box => [box.selectionStart, box.selectionEnd]") == [4, 4]
    page.keyboard.type(" tr")
    expect(returned).to_have_js_property("value", "Half tr a thought")
    expect(returned).to_be_focused()
    assert [draft["text"] for draft in stored_drafts(page).values()] == [
        "Half tr a thought"
    ]
