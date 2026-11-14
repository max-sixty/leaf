"""Selection, passage, syntax, and version-travel tests."""

import json
import re
from html import escape
from pathlib import Path

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record, response_reference, wait_for
from journeys import (
    detached_threads,
    listed_threads,
)
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
    SUGGESTION_PAGE,
    THREAD_OBLIGATIONS,
    live_url,
)
from render_cases_layout import (
    AIM_SEAM,
    AIM_SEAM_PAGE,
    MARK,
    SHOT_SRC,
    SHOTS,
)
from render_cases_navigation import (
    ADDRESSED_PAGE,
    ASTRAL_PAGE,
    CEILING_PAGE,
    CHIPS,
    CODE_PAGE,
    CONTROL_LABEL_PAGE,
    DIFF_PAGE,
    DRIFT_V1,
    DRIFT_V2,
    EDGE_PAGE,
    FENCED_CAPTURE_PAGE,
    NATIVE_CONTROL_PAGE,
    TAIL_PAGE,
    THIN_V1,
    THIN_V2,
    TWICE_PAGE,
    TWO_COPIES_PAGE,
    _publish,
    address_code,
    composer_quote,
    mark_point,
    pending_text,
    source_revision,
    wait_for_pending_mark,
)
from render_harness import (
    INLINE_PAGE,
    LONG_PAGE,
    PANEL,
    SAID_PAGE,
    _traffic,
    compare_with,
    consume_browser_errors,
    expect_open_threads,
    expect_panel_says,
    hold_selection,
    holding,
    http_error_console,
    leaf_page,
    long_press,
    open_page,
    panel_menu,
    panel_settled,
    post_event,
    preview_parts,
    resized,
    restyle_counts,
    scroll_settled,
    select,
    selection_field,
    sending,
    stamp_page,
    told,
    wait_for_revision,
    write,
)

from browser.threads import open_panel_thread
from leaf import anchor_capture as anchor_capture_model
from leaf import cli as cli_model
from leaf import data as data_model
from leaf import event_log as events_model
from leaf import structure as structure_model
from leaf.registry import storage as registry_storage
from leaf.render_checks import rendered
from leaf_dev.browser import PANEL_THREAD
from leaf_dev.example_data import named_source, patch_manifest

pytestmark = pytest.mark.shifts_unsurveyed


def comment_ids(page_dir):
    """The ids of the page's comments, in the order the log holds them."""
    return [
        e["id"] for e in events_model.read_events(page_dir) if e["kind"] == "comment"
    ]


def thread_head(page, thread_id):
    """Open the thread in the panel, once the page reads it, and return the head of
    its view, which names what the thread is about: the quoted words and a label of
    where they stand."""
    page.evaluate(
        "async () => { window.__lfThreadsApi = await window.__lfWidgetApi(); }"
    )
    page.wait_for_function(
        "id => window.__lfThreadsApi.readThreads().threads.some((t) => t.id === id)",
        arg=thread_id,
    )
    open_panel_thread(page, thread_id)
    return page.locator(".lf-thread-quote-head")


def show_on_page(page, *, key=False):
    """Take the open thread's way back to its words, Show on page, by pointer or key."""
    door = page.locator(".lf-fp-aux").get_by_role(
        "button", name="Show on page", exact=True
    )
    if key:
        door.focus()
        page.keyboard.press("Enter")
    else:
        door.click()


def stranded_quotes(page):
    """The quote of each thread the page reads whose passage it finds nowhere, read in
    the panel's view of every thread, which is put away again."""
    ids = page.evaluate(
        "async () => (await window.__lfWidgetApi()).readThreads().threads"
        ".map((thread) => thread.id)"
    )
    stranded = []
    for thread_id in ids:
        quote = thread_head(page, thread_id)
        if quote.count() and quote.get_attribute("data-lf-detached") is not None:
            stranded.append(quote.inner_text())
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    return stranded


def open_selected_comment(page):
    """Press the panel's field, which offers the completed selection."""
    field = selection_field(page)
    expect(field).to_be_visible()
    field.click()


def selected_comment_marks_chosen_start(page, chosen):
    """The explicit Comment gesture paints the range selected before focus moved."""
    open_selected_comment(page)
    rendered(page)
    return chosen.evaluate(
        """range => {
          const painted = [...(CSS.highlights.get('lf-pending') ?? [])][0];
          return painted?.compareBoundaryPoints(Range.START_TO_START, range) === 0;
        }"""
    )


def test_a_comment_box_follows_its_passage_and_resume_returns_the_writer(
    browser, serve
):
    """Resume writing recovers the same native field and words with its passage."""
    source = named_source("triage-board")
    page = open_page(browser, serve(source))
    resized(page, 1280, 500)
    box = page.locator("#triage-lede").bounding_box()
    y = box["y"] + 10
    select(page, (box["x"] + 2, y), (box["x"] + 200, y))
    page.locator(".lf-fab-input").click()
    field = page.locator(".lf-composer leaf-text")
    expect(field).to_be_focused()
    bar = page.locator(".lf-fab-bar")
    page.mouse.wheel(0, 3000)
    page.wait_for_function(
        "() => document.querySelector('#triage-lede').getBoundingClientRect().bottom < 0"
    )
    rendered(page)
    expect(field).to_be_focused()
    expect(bar).to_have_attribute("data-lf-plane", "page")
    away = bar.bounding_box()
    assert away["y"] + away["height"] < 0, away
    page.keyboard.type("x")
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("i")
    expect(field).to_be_focused()
    page.wait_for_function(
        """() => {
          const bar = document.querySelector('.lf-fab-bar').getBoundingClientRect();
          return bar.top >= 0 && bar.bottom <= innerHeight;
        }"""
    )
    expect(bar).to_be_visible()
    expect(field).to_have_js_property("value", "x")
    assert page.locator("#triage-lede").evaluate(
        "node => { const r = node.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight; }"
    )


def test_a_widgets_attribute_takes_a_comment_like_any_other_passage(browser, serve):
    """The gesture itself, on the words a widget renders from an attribute: drag across
    a column's heading and the same button, quote, and mark come up as for a paragraph,
    and the comment is still anchored a version later. A real drag, because the whole
    class of bug here is text that looks selectable and isn't — a synthetic Range would
    select what no pointer can.

    Then the other half of the pair, which the same spans decide: the version diff reads
    a block's *authored* text, and the base version it compares against is parsed
    unupgraded, where these spans don't exist. Drop their data-lf-gen and every widget
    holding a said attribute lights up as changed on every revision — a failure that
    looks like a busy page rather than like a bug."""
    page = open_page(browser, live_url(serve(SAID_PAGE)))

    heading = page.locator('lf-column#col-now > [data-lf-said="label"]')
    box = heading.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))

    # Focusing the immediate field collapses the browser Selection; the durable pending
    # paint proves the drag selected the words the widget actually says. The release
    # queues the capture rather than performing it, so the paint is what says the gesture
    # has been read — reading the highlight straight off the mouseup reads the frame
    # before it and reports every drag as a drag that selected nothing.
    wait_for_pending_mark(page)
    assert pending_text(page).strip() == "In flight", (
        "a drag across the heading selected nothing — it is painted, not said"
    )
    page.locator(".lf-fab-input").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').hasAttribute('data-lf-open')"
    )
    quoted = composer_quote(page)["text"]
    assert quoted.strip("“”") == "In flight"
    write(page.locator(".lf-composer leaf-text"), "this column's name is wrong")
    with sending(page, "the comment on the card's column name"):
        page.keyboard.press("ControlOrMeta+Enter")
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    quote = thread_head(page, comment_ids(serve.page_dir)[-1]).locator(
        ".lf-thread-quote"
    )
    assert quote.text_content().strip() == "In flight"

    # A second version reworking one card's prose and nothing else. The page follows it,
    # and the anchor is on a word only the runtime puts there, so it has to be found
    # again in the version the user now has.
    d = serve.page_dir
    stamp_page(
        d,
        SAID_PAGE.replace("Waiting on the importer.", "Unblocked; starting Thursday."),
        "two",
    )
    wait_for_revision(page, 2)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert stranded_quotes(page) == [], (
        "the comment came loose from the heading when the version turned over"
    )

    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map(e => e.id)"
    ) == ["c-backfill"], "the diff read the runtime's own spans as text the base lacked"


@pytest.mark.parametrize("revision", [2, 3])
def test_browser_and_file_captures_stop_at_the_same_widget_fences(
    browser, serve, revision
):
    """Module-only words may sit between authored parts, but they cannot give the
    browser more context than the mapped revision can confirm.

    Two revisions of the served document: one that changed only the title, so every
    widget is the one the page was served with, and one that rewrote the milestone
    itself, so that widget arrives alone into the page and its fence is read off the
    arriving root rather than off a page it is not yet in.
    """
    page = open_page(browser, live_url(serve(FENCED_CAPTURE_PAGE)))
    source = FENCED_CAPTURE_PAGE
    if revision == 2:
        source = FENCED_CAPTURE_PAGE.replace("</title>", " revised</title>")
    else:
        source = FENCED_CAPTURE_PAGE.replace("week-1", "week-2")
    stamp_page(serve.page_dir, source, "Refresh the document")
    wait_for_revision(page, 2)
    expect(page.locator('#gate-milestone [data-lf-said="label"]')).to_have_count(1)
    registry = registry_storage.read_page_registry(serve.page_dir).registry
    cases = [
        ("#gate-milestone strong", "Build feeders", "gate-milestone"),
        ("#gate-milestone", "Two classic models.", "gate-milestone"),
        ("#after-milestone", "Ready next.", "after-milestone"),
        # One chip out of a band of them: authored markup, so both readings hold it
        # for the same reason they hold the title beside it.
        ("#fence-option > small.tag", "effort: low", "fence-option"),
    ]

    for index, (selector, quote, section) in enumerate(cases, 1):
        expected_anchor = anchor_capture_model.capture_anchor(
            structure_model.SourceDocument(source),
            registry,
            quote,
            section,
        )
        selected = page.evaluate(
            """([selector, quote]) => {
                const root = document.querySelector(selector);
                const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
                let node;
                while ((node = walker.nextNode())) {
                    const at = node.data.indexOf(quote);
                    if (at === -1) continue;
                    const range = document.createRange();
                    range.setStart(node, at);
                    range.setEnd(node, at + quote.length);
                    const selection = getSelection();
                    selection.removeAllRanges();
                    selection.addRange(range);
                    return selection.toString();
                }
                return null;
            }""",
            [selector, quote],
        )
        assert selected == quote
        page.dispatch_event("body", "mouseup")
        open_selected_comment(page)
        # The field is one element for the page's whole life, so "it is on screen"
        # says only that some composer is open. This release states the passage the
        # field took, and the field describes itself by it, so a release the field
        # never answered fails here naming the passage left selected.
        expect(page.locator("#lf-composer-quote")).to_have_text(f"“{quote}”")
        page.locator(".lf-fab-input").click()
        write(page.locator(".lf-composer leaf-text"), f"fence {index}")
        # The panel renders the card from state, which can carry the append before
        # this page's own post comes back. Behind the card alone the log read below
        # answers with the comment before this one, or with nothing at all. The
        # same answer settles the draft, so this case's composer is down before the
        # next case asks for one.
        with sending(page, f"the fence {index} comment"):
            page.keyboard.press("ControlOrMeta+Enter")
        expect_open_threads(page, index)
        actual_anchor = [
            event["anchor"]
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "comment"
        ][-1]
        assert actual_anchor == expected_anchor, (
            f"{selector} captured {actual_anchor}, file captured {expected_anchor}"
        )
        # Put the card the send opened away before selecting the next passage. The
        # thread stands in the page margin over this narrow document, so the case after
        # it would reach for a composer under that card and press the card instead. The
        # send landed on the card; leave it for the passage, then let go of both.
        page.keyboard.press("Escape")
        page.keyboard.press("Escape")
        expect(page.locator(".lf-margin-preview")).to_be_hidden()


# One sentence two quoted threads discuss, which the agent's next revision rewrites.
REVISED_QUOTES_PAGE = leaf_page(
    "revised quotes",
    """
<h1 id="title">Rollout</h1>
<p id="revised-quotes">The first draft uses an early estimate for the rollout.</p>
""",
)


def test_a_revision_preserves_every_open_quoted_thread(browser, serve):
    """A served revision keeps two discussions beside their revised subject."""
    url = live_url(serve(REVISED_QUOTES_PAGE))
    roots = []
    for quote in ("first draft", "early estimate"):
        result = CliRunner().invoke(
            cli_model.cli,
            [
                "thread",
                "create",
                str(serve.page_dir),
                "--section",
                "revised-quotes",
                "--quote",
                quote,
                "--text",
                "Discuss the release wording.",
            ],
        )
        assert result.exit_code == 0, result.output
        roots.append(json.loads(result.output))
    page = open_page(browser, url)
    for root in roots:
        expect(thread_head(page, root["id"]).locator(".lf-thread-quote")).to_have_text(
            root["anchor"]["quote"]
        )
    source = (serve.page_dir / "index.html").read_text()
    updated = source.replace(
        "The first draft uses an early estimate",
        "The revised plan uses the current forecast",
    )
    note = stamp_page(serve.page_dir, updated, "Refined the rollout wording.")
    wait_for_revision(page, note["revision"])
    expect(page.locator("#revised-quotes")).to_have_text(
        "The revised plan uses the current forecast for the rollout."
    )
    for root in roots:
        quote = thread_head(page, root["id"])
        expect(quote).to_contain_text(root["anchor"]["quote"])
        expect(quote.locator(".lf-anchor-status")).to_have_text("Changed")
        expect(quote).not_to_have_attribute("data-lf-detached", "")
        expect(page.locator(f"{PANEL_THREAD} .lf-msg")).to_have_count(1)
    moves = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "reanchor"
    ]
    assert {event["thread"] for event in moves} == {root["id"] for root in roots}
    assert all(event["anchor"] == {"section": "revised-quotes"} for event in moves)


SIDEBAR_TRACK_PAGE = leaf_page(
    "sidebar track quotes",
    """<header><h1>Release review</h1></header>
<aside id="track"><div class="layout-track">
  <section id="verdict"><h2>Verdict</h2><p>Approve, with two follow-ups.</p></section>
  <section id="owners"><h2>Owners</h2><p>The payments on-call runs the cutover.</p></section>
</div></aside>
<div id="body"><p>The canary held its error rate at every step.</p></div>""",
    layout="sidebar",
)


def test_browser_and_file_captures_agree_on_a_sidebar_tracks_blocks(browser, serve):
    """Quotes inside one sidebar block and across two agree between the browser
    and authored file. Native layout keeps the original track children in place;
    comments still resolve to the same section and passage on either reading."""
    page = open_page(browser, live_url(serve(SIDEBAR_TRACK_PAGE)))
    resized(page, 1440, 900)
    expect(page.locator("#track > .layout-track > #owners")).to_have_count(1)
    track = page.locator("#track").bounding_box()
    body = page.locator("#body").bounding_box()
    assert track["x"] + track["width"] <= body["x"], (track, body)
    registry = registry_storage.read_page_registry(serve.page_dir).registry
    cases = [
        ("#owners p", "payments on-call", "owners", "#owners p", "payments on-call"),
        ("#verdict p", "two follow-ups.", "track", "#owners h2", "Owners"),
    ]
    for index, (start, start_words, section, end, end_words) in enumerate(cases, 1):
        selected = page.evaluate(
            """([start, startWords, end, endWords]) => {
                const text = (selector) => document.querySelector(selector).firstChild;
                const range = document.createRange();
                range.setStart(text(start), text(start).data.indexOf(startWords));
                const last = text(end);
                range.setEnd(last, last.data.indexOf(endWords) + endWords.length);
                getSelection().removeAllRanges();
                getSelection().addRange(range);
                return getSelection().toString();
            }""",
            [start, start_words, end, end_words],
        )
        page.dispatch_event("body", "mouseup")
        open_selected_comment(page)
        page.locator(".lf-fab-input").click()
        write(page.locator(".lf-composer leaf-text"), f"track {index}")
        with sending(page, f"the track {index} comment"):
            page.keyboard.press("ControlOrMeta+Enter")
        expect_open_threads(page, index)
        captured = [
            event["anchor"]
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "comment"
        ][-1]
        expected = anchor_capture_model.capture_anchor(
            structure_model.SourceDocument(SIDEBAR_TRACK_PAGE),
            registry,
            captured["quote"],
            section,
        )
        assert captured == expected, (selected, captured, expected)
        page.keyboard.press("Escape")
        page.keyboard.press("Escape")
        expect(page.locator(".lf-margin-preview")).to_be_hidden()
    assert stranded_quotes(page) == []


def test_quotes_cross_preserving_containers_and_remain_attached(browser, serve):
    """Neither a pane nor the obligation inside it turns visible prose into separate
    quotation islands."""
    content = """<div id="split">
      <lf-pane id="decision-pane" label="Decision"><lf-ask id="decision">
        <h2 id="question">Which plan should lead?</h2>
        <lf-options id="plans" choose>
          <lf-option id="steady">Keep the steady plan.</lf-option>
          <lf-option id="fast">Try the faster plan.</lf-option>
        </lf-options>
      </lf-ask></lf-pane>
      <lf-pane id="evidence-pane" label="Evidence"><p>Supporting evidence.</p></lf-pane>
    </div>"""
    markup = leaf_page(
        "Shared quotation",
        '<h1>Release review</h1><section id="review">'
        f'<p id="context">Release context.</p>{content}</section>',
    )
    url = live_url(serve(markup))
    page = open_page(browser, url)
    quote = "Release context. Which plan should lead?"
    registry = registry_storage.read_page_registry(serve.page_dir).registry
    expected = anchor_capture_model.capture_anchor(
        structure_model.SourceDocument(markup), registry, quote, "review"
    )
    page.evaluate(
        """() => {
          const start = document.querySelector('#context').firstChild;
          const end = document.querySelector('#question').firstChild;
          const range = document.createRange();
          range.setStart(start, 0);
          range.setEnd(end, end.length);
          getSelection().removeAllRanges();
          getSelection().addRange(range);
        }"""
    )
    page.dispatch_event("body", "mouseup")
    open_selected_comment(page)
    expect(page.locator("#lf-composer-quote")).to_have_text(f"“{quote}”")
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "Keep the question with its context.")
    with sending(page, "the comment across preserving containers"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect_open_threads(page, 1)
    actual = [
        event["anchor"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ][-1]
    assert actual == expected
    page.reload()
    held = thread_head(page, comment_ids(serve.page_dir)[-1])
    expect(held.locator(".lf-thread-quote")).to_have_text(quote)
    expect(held).not_to_have_attribute("data-lf-detached", "")


def test_monitoring_regions_share_one_collaboration_layer(browser, serve):
    """Independent release regions still contribute one Threads reading.

    The shipped example gives moving evidence its own scroll and keeps current release
    state ahead of it. A check comment still returns to its region without creating an
    event merely because the user navigated there."""
    example = named_source("live-progress")
    quote = "1,998 / 1,999 rows"
    url = serve(example, anchored=[("lp-check-finance", quote)])
    page = open_page(browser, live_url(url))

    before = events_model.read_events(serve.page_dir)
    sent = _traffic(page).sends

    expect_open_threads(page, len([e for e in before if e["kind"] == "comment"]))
    [thread_id] = [
        e["id"]
        for e in before
        if e["kind"] == "comment" and (e.get("anchor") or {}).get("quote") == quote
    ]
    expect(thread_head(page, thread_id)).to_contain_text(quote)
    show_on_page(page)
    expect(page.locator("#lp-check-finance")).to_be_in_viewport()
    # The panel stood over the region the comment is about, so the trip cleared it.
    panel_settled(page, open=False)

    assert _traffic(page).sends == sent
    assert events_model.read_events(serve.page_dir) == before


def test_a_widgets_label_takes_a_comment_inside_the_control_it_labels(browser, serve):
    """The other half of the pair above: a word the page says that the widget renders
    into a control. A tab's name is the case with nowhere else to go — the panel heading
    the theme paints stands down the moment the strip exists — so if the strip's button
    can't be quoted, the user can read the tab's name and never point at it.

    That is what a user hit, twice, on a draft's heading: the words were the page's
    and the row holding them was marked as the runtime's. `.lf-ui` is a look, and
    anchoring's question is whose words these are — so the label answers it where it is
    written (relabel), and the nearest answer wins over the box around it.

    A real drag, because the whole class of bug is text that looks selectable and
    isn't. Then the republish, because an anchor on a widget's word has to survive a
    version turning over the way one on a paragraph does."""
    page = open_page(browser, live_url(serve(CONTROL_LABEL_PAGE)))

    tab = page.get_by_role("tab", name="Heated bird bath")
    box = tab.locator("[data-lf-said]").bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 6, y), (box["x"] + box["width"] - 6, y))

    wait_for_pending_mark(page)
    assert pending_text(page).strip() == "Heated bird bath", (
        "a drag across the tab's name selected nothing"
    )
    # The drag ended on a button, and the button still switches tabs — but this mouseup
    # was a selection's, not a press, so the user is still looking at what they were
    # reading when they reached for the name.
    expect(page.locator("#p-feeders")).to_be_visible()

    page.locator(".lf-fab-input").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert composer_quote(page)["text"].strip("“”") == "Heated bird bath"
    write(page.locator(".lf-composer leaf-text"), "call it the bath, not the bird bath")
    with sending(page, "the comment on the tab's name"):
        page.keyboard.press("ControlOrMeta+Enter")
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    quote = thread_head(page, comment_ids(d := serve.page_dir)[-1]).locator(
        ".lf-thread-quote"
    )
    assert quote.text_content().strip() == "Heated bird bath"

    # A second version reworking the other panel's prose and nothing else: the name the
    # comment is on is still there, so the comment is still on it.
    stamp_page(
        d,
        CONTROL_LABEL_PAGE.replace(
            "the south pair waits on brackets", "the brackets arrived"
        ),
        "two",
    )
    wait_for_revision(page, 2)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert stranded_quotes(page) == [], (
        "the comment came loose from the tab's name when the version turned over"
    )


def test_a_selection_around_a_targets_buttons_does_not_deaden_them(browser, serve):
    """A drag around a target offers Comment without deadening its margin entries.

    The browser's native selection remains available while an exposed pointer action
    and a direct keyboard action both work."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    # Keep the margin actions exposed beside the response field: its overlay is allowed
    # to cover nearby content, while a native selection must never intercept a press.
    resized(page, 930, 900)
    # Across the two paragraphs, so the row deciding the first is inside the selection.
    start = page.locator("#replace").bounding_box()
    end = page.locator("#insert").bounding_box()
    select(
        page,
        (start["x"] + 4, start["y"] + 6),
        (end["x"] + end["width"] - 6, end["y"] + end["height"] - 6),
        steps=16,
    )
    expect(page.locator(".lf-fab-input")).to_be_visible()
    quote = composer_quote(page)
    assert quote["shown"] and "Refill" in quote["text"]
    assert "Refill" in page.evaluate("getSelection().toString()")
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    assert not page.evaluate("getSelection().isCollapsed")

    item = page.locator("[data-lf-margin-for='sug-refill']")
    expect(item.locator(":scope > .lf-margin-more")).to_be_hidden()
    item.get_by_role("button", name=re.compile(r"Reject")).click()
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "reject")
    page.locator(
        "[data-lf-margin-for='sug-in-card'] [data-lf-margin-entry-key=accept]"
    ).focus()
    page.keyboard.press("Enter")
    expect(page.locator("#sug-in-card")).to_have_attribute("data-lf-state", "accept")


def test_the_comment_button_stands_on_no_control(browser, serve):
    """The immediate comment field must not cover an authored control in the margin.

    Check the controls' corners as well as their centres, then make the press. The hit
    test proves what receives the pointer; the click proves that the decision, rather
    than the floating response UI, handles it."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    # Wide enough that the suggestion's row stands in the rail, beside the column the
    # comment bar opens over: the room beside a column holds the rail from about 960px.
    resized(page, 1000, 900)
    box = page.locator("#replace").bounding_box()
    select(
        page,
        (box["x"] + 4, box["y"] + 6),
        (box["x"] + box["width"] - 8, box["y"] + box["height"] - 6),
        steps=16,
    )
    expect(page.locator(".lf-fab-input")).to_be_visible()
    rendered(page)  # selection placement reaches the frame before hit testing
    assert (
        page.locator("[data-lf-margin-for='sug-refill']").evaluate(
            "el => el.getBoundingClientRect().left"
        )
        >= box["x"] + box["width"]
    ), "the control must hang beside the selected paragraph"

    # A box that takes no pointer cannot be covered for the pointer.
    under = page.evaluate("""() => [...document.querySelectorAll("[data-lf-offer]")]
        .filter(c => (!c.closest(".lf-chrome") || c.closest(".lf-margin-cluster"))
                     && c.checkVisibility()
                     && getComputedStyle(c).pointerEvents !== "none")
        .filter(c => { const b = c.getBoundingClientRect();
                       const xs = [b.left + 4, (b.left + b.right) / 2, b.right - 4];
                       const ys = [b.top + 4, (b.top + b.bottom) / 2, b.bottom - 4];
                       return xs.some(x => ys.some(y => {
                         const top = document.elementFromPoint(x, y);
                         // A round control's corner is its own cluster, not a cover.
                         const own = c.closest(".lf-margin-cluster") ?? c;
                         return top && !own.contains(top) && top.closest(".lf-chrome"); })); })
        .map(c => c.className)""")
    assert under == [], f"floating chrome is standing on controls: {under}"

    page.locator(
        "[data-lf-margin-for='sug-refill'] [data-lf-margin-entry-key=accept]"
    ).click()
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "accept")
    expect(
        page.locator(".lf-composer")
    ).to_be_hidden()  # the press decided, it didn't compose
    assert page.evaluate("getSelection().isCollapsed")


def test_a_suggestion_decided_by_its_address_dismisses_a_current_selection(
    browser, serve
):
    """A decision replaces the selection instead of reopening its Comment field. A
    press on the control is `test_the_comment_button_stands_on_no_control`; this
    decides it through its go-to address."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    # This width leaves the suggestion's actions exposed beside the selected passage.
    # Generated hints deliberately omit controls covered by the response overlay.
    resized(page, 930, 900)
    box = page.locator("#replace").bounding_box()
    select(
        page,
        (box["x"] + 4, box["y"] + 6),
        (box["x"] + box["width"] - 8, box["y"] + box["height"] - 6),
        steps=16,
    )
    expect(page.locator(".lf-composer")).to_be_visible()
    assert not page.evaluate("getSelection().isCollapsed")

    page.keyboard.press("g")
    page.keyboard.type(address_code(page, "Margin entry", "sug-refill", "accept"))

    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "accept")
    expect(page.locator(".lf-composer")).to_be_hidden()
    assert page.evaluate("getSelection().isCollapsed")


def test_focusing_a_selected_comment_field_keeps_its_captured_passage(browser, serve):
    """The field survives the native selection collapse caused by entering it."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    box = page.locator("#replace").bounding_box()
    select(
        page,
        (box["x"] + 4, box["y"] + 6),
        (box["x"] + box["width"] - 8, box["y"] + box["height"] - 6),
        steps=16,
    )
    field = page.locator(".lf-fab-input")
    expect(field).to_be_visible()
    field.focus()
    expect(field).to_be_focused()
    assert page.evaluate("getSelection().isCollapsed")
    expect(page.locator(".lf-composer")).to_be_visible()
    write(page.locator(".lf-composer leaf-text"), "Keep this note")
    page.locator(
        "[data-lf-margin-for='sug-refill'] [data-lf-margin-entry-key=accept]"
    ).focus()
    page.locator("#replace").select_text()
    page.evaluate("getSelection().removeAllRanges()")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer leaf-text")).to_have_js_property(
        "value", "Keep this note"
    )


def test_the_floating_response_bar_has_one_compact_face(browser, serve):
    """The input-first field and the other responses it unfolds read as one floating
    surface.

    The field is longer because it accepts words, but its type, border, colour, and
    elevation belong to the same compact family as the presses beneath it. Its radius
    stays finite so it can grow into a multiline field without becoming a capsule."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    box = page.locator("#replace").bounding_box()
    select(
        page,
        (box["x"] + 4, box["y"] + 6),
        (box["x"] + box["width"] - 8, box["y"] + box["height"] - 6),
        steps=16,
    )
    expect(page.locator(".lf-fab-input")).to_be_visible()
    # The drag ends where the bar is raised, so the pointer is on it: both are read
    # at rest, since a hover state read against a resting one compares nothing.
    page.mouse.move(4, 4)

    # The slotted shortcut hint keeps the text field's quiet placeholder ink.
    # Typography shared with sent messages must not turn an empty hint into prose.
    hint_ink = """hint => [getComputedStyle(hint).color,
        getComputedStyle(hint.querySelector('kbd')).color]"""
    hint = page.locator(".lf-fab-input .lf-compose-placeholder")
    expect(hint).to_be_visible()
    assert len(set(hint.evaluate(hint_ink))) == 1

    # The editor's frame is drawn by the moving surface. Compare that paint with
    # the button's own border and fill, rather than the transparent editor's CSS.
    family = r"""el => {
        const s = getComputedStyle(el);
        const ground = el.closest('.lf-fab-bar').querySelector('.lf-fab-ground');
        const field = el.matches('.lf-fab-input');
        const ring = field && getComputedStyle(ground.querySelector('.lf-box-ring'));
        const fill = field && getComputedStyle(ground.querySelector('.lf-box-fill'));
        const inset = style => Number.parseFloat(/^inset\(([^ ]+)/.exec(style.clipPath)[1]);
        return {
            font: s.fontFamily,
            size: s.fontSize,
            border: field ? inset(fill) - inset(ring) : Number.parseFloat(s.borderTopWidth),
            ink: field ? ring.backgroundColor : s.borderTopColor,
            face: field ? fill.backgroundColor : s.backgroundColor,
        };
    }"""
    rendered(page)
    raised = page.locator(".lf-fab-input").evaluate(family)
    page.keyboard.press("e")
    expect(page.locator(".lf-fab-bar .lf-fab-suggest")).to_be_visible()
    rendered(page)
    adjacent = page.locator(".lf-fab-bar .lf-fab-suggest").evaluate(family)
    assert raised == adjacent, (
        "the floating field and its other responses are drawn differently:\n  "
        + "\n  ".join(
            f"{k}: {raised[k]!r} vs {adjacent[k]!r}"
            for k in raised
            if raised[k] != adjacent[k]
        )
    )
    assert "system-ui" in raised["font"], (
        f"the response bar is set in the document's font: {raised['font']}"
    )
    assert (
        page.locator(".lf-fab-ground").evaluate("el => getComputedStyle(el).filter")
        != "none"
    ), "the field that floats over the page says nothing about its elevation"
    page.locator(".lf-fab-input").click()
    assert len(set(hint.evaluate(hint_ink))) == 1


# One rendered key face: the geometry a physical press claims wherever Leaf draws it, and
# the emphasis it wears there. A repaint can replace a whole layer between browser
# round trips, so every face named in one call is read in one task: a handle resolved in an
# earlier round trip can be detached by the time it is measured, and a detached element has
# no computed style at all.
FACE = """el => { const s = getComputedStyle(el); return {
  key: Object.fromEntries(
    ["min-width", "height", "padding", "box-sizing", "border-top-width",
     "border-top-style", "border-radius", "font-family", "font-size", "line-height",
     "text-align"].map(p => [p, s.getPropertyValue(p)])),
  emphasis: {border: s.borderTopColor, ground: s.backgroundColor, ink: s.color},
}; }"""


def faces(page, *selectors):
    return page.evaluate(
        f"selectors => selectors.map(sel => ({FACE})(document.querySelector(sel)))",
        list(selectors),
    )


def test_one_key_keeps_one_keyboard_face_across_the_page(browser, serve):
    """One physical press keeps its geometry wherever Leaf presents it."""
    url = serve(ADDRESSED_PAGE)
    for event in THREAD_OBLIGATIONS:
        append_carried_log_record(serve.page_dir, event)
    page = open_page(browser, url)

    # Focus inside the first thread's obligation, open in the panel, paints that group's
    # predictable digits once a keyboard gesture has asked for a paint. The sequence is a
    # nearer keyboard layer and takes the digits back while it stands, so each face is
    # read from the one moment its own layer renders it rather than from a single frame
    # that cannot hold both.
    open_panel_thread(page, "c-which")
    item = f"{PANEL_THREAD} #tq-one"
    page.locator(f"{item} .lf-pick").first.focus()
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowUp")
    picked = page.locator(f"{item} .lf-key-badge").first
    expect(picked).to_be_visible()
    option = faces(page, f"{item} .lf-key-badge")[0]
    page.keyboard.press("g")
    sequence_step = page.locator(CHIPS).first.locator("kbd").last
    expect(sequence_step).to_be_visible()
    assert sequence_step.get_attribute("data-lf-sequence-step-state") == "neutral"
    [sequence] = faces(page, f"{CHIPS} kbd:last-child")

    # The option's binding badge and the sequence's letter keep one physical key face. Both are
    # ordinary available bindings, so geometry and emphasis stay the same.
    assert option["key"] == sequence["key"], (
        "one physical key has two geometries:\n  "
        + "\n  ".join(
            f"{k}: {option['key'][k]!r} vs {sequence['key'][k]!r}"
            for k in option["key"]
            if option["key"][k] != sequence["key"][k]
        )
    )
    assert "mono" in option["key"]["font-family"]
    assert option["emphasis"] == sequence["emphasis"]

    # Target picker uses letters rather than digits, but it names the same physical
    # keys. Closing the Go-to sequence and opening selection must not reveal a fourth face.
    page.keyboard.press("Escape")
    expect(page.locator(".lf-go-to-hints .lf-go-to-hint")).to_have_count(0)
    page.keyboard.press("s")
    # With the go-to surface gone, compare an available selection key with the option
    # and sequence's neutral state.
    selection_key = '.lf-target-picker-hints .lf-target-picker-hint kbd[data-lf-sequence-step-state="neutral"]'
    hint = page.locator(selection_key).first
    expect(hint).to_be_visible()
    # A repaint can replace the hint layer between browser round trips. Read
    # the one rendered face in one task so geometry and emphasis cannot come from two
    # successive hint elements.
    hint_face = faces(page, selection_key)[0]
    assert hint_face["key"] == option["key"]
    assert hint_face["emphasis"] == option["emphasis"]


def test_a_drag_that_overshoots_the_layer_is_not_a_passage(browser, serve):
    """A hand that runs past the right edge of the document lands in the layer, and the
    browser extends its selection through everything in between — a paragraph and a
    pointer a few words along came back as a 14,387-character quote, a mark over 22,140
    of them, and a field whose accessible name read the whole page out. The layer
    answering `user-select: none` keeps most of it out of reach, and a user must still
    be able to copy what somebody said, so a thread's own quoted words remain a landing
    place: that is where this drag ends.

    What the user meant is what the drag had inside the document before it crossed out,
    and the release puts that back. Where it had nothing yet, nothing is offered — and
    either way the browser's own selection is left where it is, because it is the
    user's to copy.

    Only a pointer drag is asked this. Select-all lands its far end past the page's last
    words by definition and still means the document, which
    `test_a_selection_of_the_whole_page_still_finds_its_passage` holds. The chrome half of
    this — which of the layer's words a selection may reach at all — is
    `controls/test_covering.py::test_a_selection_that_reaches_the_layer_stops_at_the_page`.
    """
    # Distinct words let the restored passage resolve after the drag. Repeated filler
    # gives this page many indistinguishable anchors, so no pending mark can paint.
    unique_page = leaf_page(
        "long",
        "<h1 id='t'>Long</h1>{paras}",
    ).format(
        paras="\n".join(
            f"<p id='p{i}'>Paragraph {i}. "
            + " ".join(f"Word{8 * i + j:03d}." for j in range(8))
            + "</p>"
            for i in range(60)
        )
    )
    quoted = "Paragraph 3. Word024. Word025. Word026."
    page = open_page(browser, serve(unique_page, anchored=(("p3", quoted),)))
    resized(page, 1400, 900)
    card = thread_head(page, comment_ids(serve.page_dir)[-1]).locator(
        ".lf-thread-quote"
    )
    expect(card).to_be_visible()
    into = card.bounding_box()
    # A paragraph level with the thread's quoted words, so the overshoot is sideways:
    # a drag that also travels down the page selects what it crossed, and would be
    # measuring the page's own length rather than the edge this is about.
    para = page.evaluate(
        """(y) => {
          const p = [...document.querySelectorAll('main p')]
            .filter((el) => el.checkVisibility())
            .map((el) => ({ el, box: el.getBoundingClientRect() }))
            .sort((a, b) => Math.abs(a.box.top - y) - Math.abs(b.box.top - y))[0];
          return { left: p.box.left, top: p.box.top, height: p.box.height };
        }""",
        into["y"],
    )
    line = para["top"] + para["height"] / 2
    # Two moves with a turn between them: the first covers words inside the document and
    # is the passage this release has to come back to, and the browser only says a
    # selection changed on a turn of its own.
    hold_selection(page, (para["left"] + 4, line), (para["left"] + 190, line), steps=12)
    # The selection saying it covers something is the fact this read wants, and the drag
    # is still held, so there is no composer to wait on yet.
    page.wait_for_function("() => getSelection().toString().length > 0")
    # Selectionchange can still be queued after the last mouse move. Give that event
    # its turn so the gesture remembers this endpoint before it leaves the document.
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(resolve))")
    covered = page.evaluate("() => getSelection().toString()")
    page.mouse.move(into["x"] + 40, into["y"] + into["height"] / 2, steps=20)
    page.mouse.up()
    # The release restores the remembered range and raises the composer on it, so the box
    # shown and its passage painted are the two facts the three readings below are
    # taken from. Waiting out `deferSelectionUpdate`'s timer instead would read a composer
    # that may not be there yet and report it as a missing box.
    expect(page.locator(".lf-fab-input")).to_be_visible()
    wait_for_pending_mark(page)

    assert covered, "the drag selected nothing inside the document to come back to"
    quote = composer_quote(page)["text"].strip("“”")
    assert len(quote) < 2 * len(covered), (
        f"the drag out of the document stored {len(quote)} characters as its passage"
    )
    document_words = page.evaluate("() => document.querySelector('main').textContent")
    assert quote and quote in " ".join(document_words.split()), (
        f"the composer quotes something the document does not hold: {quote!r}"
    )
    # The three readings of one passage: what the box says it is about, what the page
    # paints, and what the field is called. A capture that ran past the document moved
    # all three together, so any one of them alone would pass on a page it had ruined.
    assert pending_text(page).replace(" ", "") == quote.replace(" ", ""), (
        f"the mark and the quote disagree: {pending_text(page)!r} against {quote!r}"
    )
    assert quote in page.locator(".lf-fab-input").get_attribute("aria-label")


def test_the_captured_quote_is_prose_a_file_can_hold(browser, serve):
    """A quote is read back as prose — seeded into the suggestion box, printed in the
    panel — and written to a UTF-8 file on the way. Source text is neither: it carries
    the author's line wraps, which break the prose, and cutting it to length by UTF-16 unit can halve a
    character, which no UTF-8 file can hold. The server refuses that write and the
    user is told it is offline, with no way to ever send the comment."""
    url = serve(INLINE_PAGE)
    page = open_page(browser, url)

    def compose_on(block):
        page.locator(block).click(click_count=3)
        page.locator(".lf-fab-input").click()
        page.wait_for_function(
            "() => document.querySelector('.lf-composer').hasAttribute('data-lf-open')"
        )

    # Read off the composer's description of its own anchor, which is the captured quote
    # verbatim — the string that goes on to the panel, the file, and the export.
    compose_on("#p")  # authored across two source lines
    wrapped = composer_quote(page)["text"]
    assert "\n" not in wrapped, f"the quote carries the source's line wrap: {wrapped!r}"
    page.keyboard.press("Escape")

    # Measured in the page: a lone surrogate does not survive the trip out to the test
    # runner, which replaces it, so asking out here would always come back clean.
    # Iterating by code point, a character cut in half is left as a single unit in the
    # surrogate range; an intact one comes through as the pair it is.
    compose_on("#cap")
    assert not page.evaluate("""() => [...document.getElementById('lf-composer-quote').textContent]
        .some(c => c.length === 1 && c.charCodeAt(0) >= 0xd800 && c.charCodeAt(0) <= 0xdfff)"""), (
        "the 400-character cap split a character in half"
    )

    # And the round trip that proves it: the server has to accept the quote and write it
    # to a UTF-8 file. A half character fails there, reported to the user as an offline
    # server, and no retry can ever succeed.
    #
    # So the card alone is not the fact to wait on: it is painted the turn the comment is
    # sent, under an identity the response replaces. `sending` cannot stand in for that
    # identity here — the refusal this test guards against is a request failure the
    # outbox retries rather than settles, so its trip would sit out its whole deadline
    # instead of reporting what the user was told.
    #
    # The composer prints the quote inside quotation marks; what it captured is what
    # lies within them, and that is what the file has to come back holding.
    captured = composer_quote(page)["text"].strip("\u201c\u201d")
    write(page.locator(".lf-composer leaf-text"), "a comment on the capped passage")
    page.keyboard.press("ControlOrMeta+Enter")
    wait_for(
        lambda: comment_ids(serve.page_dir),
        bool,
        failure="the comment never posted",
    )

    # And the file behind that answer, read back through Python's UTF-8 decoder, which is
    # the user a half character has no bytes for.
    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [comment["anchor"]["quote"] for comment in comments] == [captured]


def test_an_open_composer_does_not_eat_the_next_click(browser, serve):
    """Clicks keep working while a composer is open. The composer comes down on the
    document's mousedown, and anything that rewrites the page's marks there swaps out
    the node under the pointer between press and release — which is a click the
    browser never dispatches at all. So a thread's highlight stops opening its thread,
    and a link inside a highlighted passage stops navigating. Real button presses,
    because a synthetic click event sails straight past the gap it lives in."""
    url = serve(INLINE_PAGE)
    page = open_page(browser, live_url(url))
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "on the passage",
            "anchor": {"section": "p", "quote": "bold text"},
        },
    )
    told(page)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    # Open a composer on other text and type nothing, so the next mousedown outside it
    # is the one that takes it down.
    page.locator("#q").click(click_count=3)
    page.locator(".lf-fab-input").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').hasAttribute('data-lf-open')"
    )

    # The click that selected #q also scrolled it into view. Bring the other passage
    # back before deriving a viewport coordinate from its range; a negative-y
    # Mouse.click is no user gesture and can only prove that nothing was hit.
    page.locator("#p").scroll_into_view_if_needed()
    page.mouse.click(*mark_point(page, "lf-mark"))
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(PANEL)).not_to_have_attribute("data-lf-open", re.compile("."))

    # And the composer's own mark belongs to no thread, so it opens nothing. Its first
    # range runs up to the posted one, so this lands on the draft and nothing else.
    page.locator(".lf-margin-preview-close").click()
    page.locator("#p").click(click_count=3)
    page.locator(".lf-fab-input").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').hasAttribute('data-lf-open')"
    )
    page.mouse.click(*mark_point(page, "lf-pending"))
    rendered(page)
    assert page.locator(PANEL).get_attribute("data-lf-open") is None, (
        "clicking the composer's own highlight opened the panel, but it belongs to no thread"
    )


def test_a_click_on_a_mark_decides_once(browser, serve):
    """Opening a thread surface rewrites page-attached chrome, so anything that hit-tests
    the page afterward is testing geometry that may already have moved. When two handlers
    each asked where the pointer was, the second missed the mark the first had just opened and
    raised the response bar on top of it — and the element anchor that left behind reads
    as composition in progress, which is what stops a page following new versions. The
    panel starts shut here because a panel already open is the case with no reflow."""
    version_url = serve(INLINE_PAGE)
    url = live_url(version_url)
    page = open_page(browser, url)
    # A quote inside the figure's caption: a painted range, so opening the panel reflows the
    # text out from under the pointer. An element anchor wouldn't show it — a figure still
    # covers the same point after the column narrows.
    post_event(
        page,
        version_url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "on the caption",
            "anchor": {"section": "fig", "quote": "A sample, for element anchors."},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    page.locator("#fig").scroll_into_view_if_needed()
    spot = page.evaluate("""() => { const r = [...CSS.highlights.get('lf-mark')][0].getClientRects()[0];
                                    return {x: r.left + r.width / 2, y: r.top + r.height / 2}; }""")
    page.mouse.click(spot["x"], spot["y"])
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(PANEL)).not_to_have_attribute("data-lf-open", re.compile("."))
    expect(
        page.locator(".lf-fab-input"),
        "the click opened the thread and then offered to comment on it as well",
    ).not_to_be_visible()

    # The harm that outlives the stray button: a page mid-composition stays put.
    d = serve.page_dir
    stamp_page(
        d,
        INLINE_PAGE.replace('<h1 id="t">Inline</h1>', '<h1 id="t">Inline II</h1>'),
        "two",
    )
    wait_for_revision(page, 2)


def test_code_copy_enter_leaves_nested_links_usable(browser, serve):
    # The clipped source sits beyond the near observer's 600px scroll margin
    # (geometry.js, `nearObserver`), so the synchronous first reading and the
    # observer's first record agree it stays out of layout. A nearer source enters
    # layout on that record, before or after presentation as load decides.
    url = live_url(
        serve(
            leaf_page(
                "Code link",
                '<h1 id="destination">Destination</h1>'
                '<pre id="source"><code>See <a id="code-link" href="#destination">details</a></code></pre>'
                '<div id="scroller" style="height:80px;overflow:auto">'
                '<div style="height:1000px"></div>'
                '<pre id="clipped"><code>Below the inner viewport.</code></pre></div>',
            )
        )
    )
    page = open_page(
        browser,
        url,
        init_script="""new MutationObserver(() => {
          if (window.copyAtPresentation !== undefined ||
              !document.body?.hasAttribute('data-lf-presented')) return;
          window.copyAtPresentation = [...document.querySelectorAll('.lf-code-copy')]
            .filter(node => node.getClientRects().length).length;
        }).observe(document, {subtree:true, attributes:true,
          attributeFilter:['data-lf-presented']});""",
    )
    expect(page.locator(".lf-chrome .lf-code-copy")).to_have_count(2)
    page.locator("#source").hover()
    page.locator(".lf-chrome .lf-code-copy").first.get_by_role("button").hover()
    assert (
        page.locator(".lf-chrome .lf-code-copy").evaluate_all(
            "nodes => nodes.filter(node => getComputedStyle(node).opacity === '1').length"
        )
        == 1
    ), "hovering one Copy control must not reveal the other blocks' controls"
    page.mouse.move(2, 300)

    assert page.evaluate("window.copyAtPresentation") == 1
    page.evaluate(
        "window.detachedCodeSource = document.querySelector('#source'); detachedCodeSource.remove()"
    )
    expect(page.locator(".lf-chrome .lf-code-copy")).to_have_count(1)
    page.evaluate("document.querySelector('main').append(detachedCodeSource)")
    expect(page.locator(".lf-chrome .lf-code-copy")).to_have_count(2)
    page.locator("#source").focus()
    page.keyboard.press("Tab")
    expect(page.locator("#code-link")).to_be_focused()
    # A link inside the block keeps its Enter from the block's Copy.
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"#destination$"))


def test_code_copy_keeps_its_source_container_active(browser, serve):
    source = leaf_page(
        "Copy in card",
        '<div id="card"><p id="actions">Actions</p>'
        '<pre id="source"><code>echo hello</code></pre></div>'
        '<button id="outside">Outside</button>',
    ).replace(
        "</head>",
        "<style>#card:not(:hover, :focus-within, :has([data-lf-control-active])) "
        "#actions { visibility: hidden; }</style></head>",
    )
    page = open_page(browser, live_url(serve(source)))
    card = page.locator("#card")
    actions = page.locator("#actions")
    pre = page.locator("#source")
    copy = page.locator(".lf-chrome .lf-code-copy").get_by_role("button")

    expect(actions).to_be_hidden()
    pre.hover()
    expect(actions).to_be_visible()
    copy.hover()
    expect(pre).to_have_attribute("data-lf-control-active", "")
    expect(actions).to_be_visible()
    assert not card.evaluate("node => node.matches(':hover')")

    page.mouse.move(2, 300)
    expect(pre).not_to_have_attribute("data-lf-control-active", "")
    expect(actions).to_be_hidden()
    pre.hover()
    copy.focus()
    page.mouse.move(2, 300)
    expect(pre).to_have_attribute("data-lf-control-active", "")
    expect(actions).to_be_visible()
    page.locator("#outside").focus()
    expect(pre).not_to_have_attribute("data-lf-control-active", "")
    expect(actions).to_be_hidden()


def test_tapping_code_copy_keeps_its_source_container_active(browser, serve):
    source = leaf_page(
        "Touch copy in card",
        '<div id="card"><p id="actions">Actions</p>'
        '<pre id="source"><code>echo hello</code></pre></div>'
        '<button id="outside">Outside</button>',
    ).replace(
        "</head>",
        "<style>#card:not(:focus-within, :has([data-lf-control-active])) "
        "#actions { visibility: hidden; }</style></head>",
    )
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, live_url(serve(source)), context=context)
    pre = page.locator("#source")
    actions = page.locator("#actions")
    pre.tap(position={"x": 30, "y": 20})
    expect(actions).to_be_visible()
    page.locator(".lf-chrome .lf-code-copy").get_by_role("button").tap()
    expect(pre).to_have_attribute("data-lf-control-active", "")
    expect(actions).to_be_visible()
    page.locator("#outside").tap()
    expect(pre).not_to_have_attribute("data-lf-control-active", "")
    expect(actions).to_be_hidden()


def test_code_copy_is_a_mark_whatever_its_block_s_line(browser, serve):
    """Copy is a mark, one size on every block, compact or tall, and its reach keeps
    the aim floor."""
    url = live_url(
        serve(
            leaf_page(
                "Code copy marks",
                '<pre id="compact" style="font-size:12.5px;line-height:19px;'
                'padding:7px 10px"><code>echo hello</code></pre>'
                '<pre id="tall" style="line-height:40px"><code>echo tall</code></pre>',
            )
        )
    )
    page = open_page(browser, url)
    mark = page.evaluate(
        "parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--mark-size'))"
    )
    floor = page.evaluate(
        "parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--aim-floor'))"
    )
    for index, block in enumerate(("#compact", "#tall")):
        page.locator(block).hover()
        face = page.locator(".lf-chrome .lf-code-copy").nth(index).get_by_role("button")
        expect(face).to_be_visible()
        box = face.evaluate("el => el.getBoundingClientRect().toJSON()")
        assert (box["width"], box["height"]) == (mark, mark), block
        assert (
            face.evaluate("el => parseFloat(getComputedStyle(el, '::after').height)")
            >= floor
        ), block


def test_code_copy_reads_sources_before_positioning_many_controls(browser, serve):
    blocks = "".join(
        f"<p>Example {i}</p><pre><code>code {i}</code></pre>" for i in range(60)
    )
    url = live_url(serve(leaf_page("Many code blocks", blocks)))
    page = open_page(
        browser,
        url,
        init_script="""(() => {
          const events = window.copyPlacementEvents = [];
          const rect = Element.prototype.getBoundingClientRect;
          Element.prototype.getBoundingClientRect = function (...args) {
            if (this.localName === 'pre' && this.querySelector(':scope > code'))
              events.push('read');
            return rect.apply(this, args);
          };
          Object.defineProperty(CSSStyleDeclaration.prototype, 'anchorName', {
            configurable: true,
            get() { return this.getPropertyValue('anchor-name'); },
            set(value) {
              if (value?.startsWith('--lf-a')) events.push('write');
              this.setProperty('anchor-name', value);
            },
          });
        })()""",
    )
    expect(page.locator(".lf-chrome .lf-code-copy")).to_have_count(60)
    events = page.evaluate("window.copyPlacementEvents")
    assert events.count("read") >= 60
    assert "write" in events
    assert events.index("write") >= 60

    # Opening unrelated chrome must not restyle every code control. Compare the
    # browser's invalidated-element count at two populations, independent of time.
    def restyled_on_chrome_insertion():
        restyled = restyle_counts(
            page,
            lambda: page.evaluate("""() => {
              const chrome = document.querySelector('.lf-chrome');
              const probe = document.createElement('div');
              chrome.append(probe);
              void probe.offsetWidth;
              probe.remove();
              void chrome.offsetWidth;
            }"""),
        )
        assert restyled, "the chrome insertion must exercise style invalidation"
        return sum(restyled)

    rendered(page)
    many = restyled_on_chrome_insertion()
    page.locator("main pre").evaluate_all(
        "nodes => nodes.slice(1).forEach(node => node.remove())"
    )
    expect(page.locator(".lf-chrome .lf-code-copy")).to_have_count(1)
    rendered(page)
    one = restyled_on_chrome_insertion()
    assert many <= one, {"60 controls": many, "1 control": one}


def test_hidden_code_arrivals_do_not_read_skipped_blocks(browser, serve):
    """Arriving code must leave the browser's skipped subtrees unmeasured. A block
    revealed later gets its copy control, names its Copy key and copies on Enter."""
    page = open_page(
        browser,
        serve(leaf_page("Hidden arrivals", '<h1>Arrivals</h1><div id="slots"></div>')),
    )
    page.evaluate("""() => {
      window.hiddenCodeReads = [];
      const rect = Element.prototype.getBoundingClientRect;
      Element.prototype.getBoundingClientRect = function (...args) {
        if (this.matches('pre[data-hidden-probe]')) hiddenCodeReads.push('rect');
        return rect.apply(this, args);
      };
      const computed = window.getComputedStyle;
      window.getComputedStyle = function (node, ...args) {
        if (node.matches('pre[data-hidden-probe]')) hiddenCodeReads.push('style');
        return computed.call(this, node, ...args);
      };
      document.querySelector('#slots').innerHTML =
        '<section hidden="until-found"><pre data-hidden-probe><code>tab</code></pre></section>' +
        '<details><summary>Code</summary><pre data-hidden-probe><code>details</code></pre></details>';
    }""")
    rendered(page)
    assert page.evaluate("hiddenCodeReads") == []
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.locator("#slots section").evaluate("node => node.removeAttribute('hidden')")
    expect(page.locator(".lf-code-copy")).to_have_count(1)
    page.locator("#slots summary").click()
    expect(page.locator(".lf-code-copy")).to_have_count(2)
    # The revealed block names its Copy key once its control has drawn its button.
    expect(page.locator("#slots details pre")).to_have_attribute(
        "aria-keyshortcuts", re.compile(r"\bEnter\b")
    )
    page.keyboard.press("Tab")
    expect(page.locator("#slots details pre")).to_be_focused()
    page.keyboard.press("Enter")
    expect(
        page.locator(".lf-code-copy").nth(1).get_by_role("button")
    ).to_have_accessible_name("Code copied")
    assert page.evaluate("navigator.clipboard.readText()") == "details"


@pytest.mark.parametrize("holder", ["disclosure", "tab"])
def test_code_copy_leaves_the_window_with_its_hidden_source(browser, serve, holder):
    """Hidden and distant sources take no anchored control layout; Copy still works."""
    source = '<pre id="source"><code>copy this source</code></pre>' + "".join(
        f"<pre><code>example {index}</code></pre>" for index in range(99)
    )
    contents = (
        "<details><summary>Code</summary>" + source + "</details>"
        if holder == "disclosure"
        else '<lf-tabs id="views"><lf-tab id="overview" label="Overview">'
        '<p id="intro">Overview</p></lf-tab><lf-tab id="code" label="Code">'
        + source
        + "</lf-tab></lf-tabs>"
    )
    url = live_url(
        serve(leaf_page("Hidden code", '<h1 id="title">Hidden code</h1>' + contents))
    )
    page = open_page(browser, url)
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    controls = page.locator(".lf-chrome .lf-code-copy")
    control = controls.first
    expect(page.locator("#source")).to_be_hidden()
    assert (
        controls.evaluate_all(
            "nodes => nodes.filter(node => node.getClientRects().length).length"
        )
        == 0
    )

    opener = (
        page.locator("main summary")
        if holder == "disclosure"
        else page.get_by_role("tab", name="Code", exact=True)
    )
    closer = (
        opener
        if holder == "disclosure"
        else page.get_by_role("tab", name="Overview", exact=True)
    )
    opener.click()
    rendered(page)
    expect(page.locator("#source")).to_be_visible()
    expect(controls).to_have_count(100)
    expect(control).to_be_in_viewport()
    assert (
        0
        < controls.evaluate_all(
            "nodes => nodes.filter(node => node.getClientRects().length).length"
        )
        < 100
    )
    button = control.get_by_role("button")
    page.locator("#source").hover()
    button.click()
    expect(button).to_have_accessible_name("Code copied")
    assert page.evaluate("navigator.clipboard.readText()") == "copy this source"

    closer.click()
    rendered(page)
    expect(page.locator("#source")).to_be_hidden()
    expect(control).not_to_be_in_viewport()
    # A source opened once retains an old layout inside its skipped subtree.
    # Resize while it is hidden, then reveal it at the new width.
    resized(page, 1440, 900)
    opener.click()
    rendered(page)
    expect(control).to_be_in_viewport()
    expect(button).to_have_accessible_name("Copy code")
    page.evaluate("navigator.clipboard.writeText('cleared')")
    page.locator("#source").hover()
    button.click()
    expect(button).to_have_accessible_name("Code copied")
    assert page.evaluate("navigator.clipboard.readText()") == "copy this source"


def test_resizing_closed_code_sections_does_not_lay_out_each_hidden_section(
    browser, serve
):
    """Previously viewed code stays skipped when its disclosure closes and the window
    resizes. Reading every block's header cuts used to force one layout per hidden
    section; never-opened sections conceal that cost because they have no old layout."""
    sections = "".join(
        f"<details open><summary>Example {i}</summary>"
        f"<div><pre><code>code {i}</code></pre></div></details>"
        for i in range(20)
    )
    page = open_page(browser, serve(leaf_page("Closed code sections", sections)))
    controls = page.locator(".lf-chrome .lf-code-copy")
    expect(controls).to_have_count(20)
    for summary in page.locator("main summary").all():
        summary.click()
    rendered(page)
    expect(page.locator("main details[open]")).to_have_count(0)

    browser.start_tracing(
        page=page,
        categories=[
            "devtools.timeline",
            "disabled-by-default-devtools.timeline",
            "disabled-by-default-devtools.timeline.stack",
        ],
    )
    try:
        resized(page, 1440, 900)
        rendered(page)
        # Establish that this browser records JavaScript layout stacks at all.
        # The fixed-position probe takes no room in the document.
        page.evaluate("""() => {
          const probe = document.createElement('div');
          probe.style.position = 'fixed';
          document.body.append(probe);
          probe.getBoundingClientRect();
          probe.remove();
        }""")
    finally:
        trace = json.loads(browser.stop_tracing())
    layouts = [
        event
        for event in trace["traceEvents"]
        if event["name"] == "Layout" and event["ph"] == "X"
    ]
    assert any(event["args"]["beginData"].get("stackTrace") for event in layouts)
    # Count only layout forced by the controls' cut reading, rather than comparing
    # whole-page totals that include the browser's viewport and observer work.
    forced = [
        event
        for event in layouts
        if any(
            frame["functionName"] == "headerLevels"
            for frame in event["args"]["beginData"].get("stackTrace", [])
        )
    ]
    assert not forced, {"hidden-section layouts": len(forced), "first": forced[0]}


def test_code_copy_releases_only_its_own_scroll_stop(browser, serve):
    source = "wide-source-" * 30
    markup = f'<pre id="source"><code>{source}</code></pre>'
    page = open_page(
        browser,
        live_url(serve(leaf_page("Code stop", markup))),
    )
    pre = page.locator("#source")
    control = page.locator(".lf-chrome .lf-code-copy")
    expect(control).to_have_count(1)
    assert pre.evaluate("el => el.scrollWidth > el.clientWidth")
    pre.evaluate("(el, text) => el.replaceChildren(text)", source)
    expect(control).to_have_count(0)
    assert pre.evaluate("el => el.scrollWidth > el.clientWidth")
    expect(pre).to_have_attribute("tabindex", "0")


def test_a_box_off_the_reading_face_keeps_its_own_tables_code_and_comments(
    browser, serve
):
    """Content with its own design inside a themed page sits in a box that turns the
    reading face off (`package-themes.md`, "Personal themes"). Its full-width table
    stays a native table, its code keeps the spans and colours its author gave it with
    no clearance under the block, a plain block there stays uncoloured, and a comment
    still anchors on a word inside it. The code block outside keeps the face."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Face off",
                '<section id="embedded" style="--lf-reading-face: initial">'
                '<table id="own-table" style="width:100%">'
                "<tr><td>Short</td><td>Columns</td></tr></table>"
                '<pre id="own-pre"><code class="language-yaml">'
                '<span id="own-token" style="color:rgb(160, 20, 80)">key</span>: value'
                "</code></pre>"
                '<pre id="plain-pre"><code class="language-yaml">key: value</code></pre>'
                "</section>"
                '<pre id="leaf-pre"><code class="language-yaml">key: value</code></pre>',
            ),
            anchored=[("own-token", "key")],
        ),
    )
    expect(page.locator("#leaf-pre code")).to_have_attribute("data-lf-syntax", "yaml")
    table = page.locator("#own-table")
    assert table.evaluate("el => getComputedStyle(el).display") == "table"
    token = page.locator("#own-token")
    assert token.evaluate("el => getComputedStyle(el).color") == "rgb(160, 20, 80)"
    own = page.locator("#own-pre")
    assert own.evaluate("el => getComputedStyle(el, '::after').content") == "none"
    assert page.locator("#own-pre code").get_attribute("data-lf-syntax") is None
    assert page.locator("#plain-pre code").get_attribute("data-lf-syntax") is None
    assert page.evaluate(
        """() => [...(CSS.highlights.get('lf-mark') ?? [])].some((range) =>
          range.intersectsNode(document.querySelector('#own-token').firstChild))"""
    )


def test_code_colouring_keeps_each_blocks_words_and_annotations(
    browser, serve, subtests
):
    """Markdown fence labels select the same colors as their full language names.
    Annotations keep their nodes and text while tokens cross their boundaries. A second
    dressing pass that reaches a block whose tokens are still on their way leaves it to
    the pass in flight, so that pass colors the text the block holds when its tokens
    land: text rewritten meanwhile, as a live revision rewrites a block in place, must
    not be put back to what the first pass read."""
    sources = {
        "js": ("javascript", 'const value = "leaf"; // keep the source\n'),
        "sh": ("bash", 'leaf page check "$PAGE" --render\n'),
    }
    blocks = "".join(
        f'<pre id="{label}"><code class="language-{label}">{escape(source)}</code></pre>'
        for alias, (name, source) in sources.items()
        for label in (alias, name)
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Code colouring",
                blocks + '<pre id="marked"><code class="language-python">'
                '<span id="target"></span>de<mark id="annotation">f load(path):\n'
                '    return "rea</mark>d"</code></pre>'
                '<pre id="lines"><code class="language-python">'
                '<span class="line">def load(path):</span>\n'
                '<span class="line">    return "read"</span></code></pre>'
                '<pre id="breaks"><code class="language-python">'
                'def load(path):<br>    return "read"</code></pre>'
                '<pre id="later"><code class="language-python">x = 1</code></pre>',
            )
        ),
    )

    with subtests.test(case="language aliases"):
        for alias, (name, source) in sources.items():
            tokens = "el => [...el.querySelectorAll('[data-lf-syn]')].map(token => [token.textContent, getComputedStyle(token).color])"
            short = page.locator(f"#{alias} code")
            full = page.locator(f"#{name} code")
            expect(short).to_have_attribute("data-lf-syntax", name)
            assert short.text_content() == full.text_content() == source
            painted = short.evaluate(tokens)
            assert len({color for _, color in painted}) > 1
            assert painted == full.evaluate(tokens)

    with subtests.test(case="inline annotations"):
        marked = page.locator("#marked code")
        expect(marked).to_have_attribute("data-lf-syntax", "python")
        expect(page.locator("#annotation [data-lf-syn]").first).to_be_attached()
        expect(page.locator("#lines .line [data-lf-syn]").first).to_be_attached()
        expect(page.locator("#target")).to_be_empty()
        assert marked.text_content() == 'def load(path):\n    return "read"'
        # The string token crosses the mark's end, so both pieces keep its colour.
        assert marked.evaluate("""code => {
          const tokens = [...code.querySelectorAll('[data-lf-syn]')];
          return tokens.some(t => t.textContent === '"rea' && t.style.color === 'var(--syn-string)')
            && tokens.some(t => t.textContent === 'd"' && t.style.color === 'var(--syn-string)');
        }""")
        # A different language repaints Leaf's tokens inside the same annotations.
        assert page.evaluate("""async () => {
          const {highlightBlocks} = await window.__lfWidgetApi();
          const code = document.querySelector('#marked code');
          const mark = code.querySelector('mark');
          const target = code.querySelector('#target');
          const previous = [...code.querySelectorAll('[data-lf-syn]')];
          code.className = 'language-javascript';
          await highlightBlocks(code);
          const tokens = [...code.querySelectorAll('[data-lf-syn]')];
          await highlightBlocks(code);
          return code.querySelector('mark') === mark
            && code.querySelector('#target') === target
            && mark.textContent === 'f load(path):\\n    return "rea'
            && code.dataset.lfSyntax === 'javascript'
            && previous.some(t => !code.contains(t))
            && !code.querySelector('[data-lf-syn] [data-lf-syn]')
            && tokens.every(t => code.contains(t));
        }""")
        assert page.locator("#breaks [data-lf-syn]").count() == 0

    with subtests.test(case="a block rewritten while it is colored"):
        expect(page.locator("#later [data-lf-syn]").first).to_be_attached()
        text = page.evaluate(
            """async () => {
              const {highlightBlocks} = await window.__lfWidgetApi();
              const code = document.createElement('code');
              code.className = 'language-python';
              code.textContent = 'old = 1';
              document.querySelector('#later').after(
                Object.assign(document.createElement('pre'), {id: 'rewritten'}));
              document.querySelector('#rewritten').append(code);
              const first = highlightBlocks(code);
              code.textContent = 'new = 2';
              await Promise.all([first, highlightBlocks(code)]);
              return code.textContent;
            }"""
        )
        assert text == "new = 2"


@pytest.mark.watch_shifts
def test_code_is_colored_without_a_word_moving(browser, serve):
    """Colouring is spans, and the anchor pass is what spans break: the revision holds
    one run of characters where the DOM now holds a dozen nodes. A <span> is no text block,
    so both readings collapse to the same string — which is what lets the runtime color a
    block the file knows nothing about, and what keeps `leaf thread create` able to quote
    into one.

    One pass serves both shapes a page has for code, lf-code's `language` and a plain
    <pre><code class="language-*">, and neither guesses: a lf-code with no `language` stays
    the color of its own ink. The quote below is written the way `leaf thread create`
    writes one — against the file — and spans a token boundary on its way back."""
    url = serve(CODE_PAGE)
    page = open_page(browser, url)
    page.wait_for_function(
        "() => document.querySelector('lf-code.lf-rendered') !== null"
    )

    colors = page.evaluate("""() => {
      const at = sel => [...document.querySelectorAll(sel + ' [data-lf-syn]')]
        .map(e => [e.style.color, e.textContent, getComputedStyle(e).fontStyle]);
      return { widget: at('#walk-code'), plain: at('#walk pre > code'),
               undeclared: at('#plain-code') };
    }""")
    assert ["var(--syn-keyword)", "def", "normal"] in colors["widget"]
    assert ["var(--syn-name)", "bucket_key", "normal"] in colors["widget"]
    assert {color for color, _, _ in colors["widget"]} >= {
        "var(--syn-keyword)",
        "var(--syn-string)",
        "var(--syn-name)",
    }, colors["widget"]
    assert [
        "var(--syn-comment)",
        "# apply the migration, then run the marked suite",
        "italic",
    ] in colors["plain"]
    assert colors["undeclared"] == [], (
        f"a lf-code with no language was colored anyway: {colors['undeclared']}"
    )

    # The words each block holds, unchanged by the spans: what the file says is what the
    # page says, which is the whole reason a quote written against one lands in the other.
    # The widget numbers lines, so its own newline is the join; the note it docks at line 2
    # is prose and sits outside the code.
    assert page.evaluate(
        "() => document.querySelector('#walk pre > code').textContent"
    ) == (
        "# apply the migration, then run the marked suite\ncd gateway && alembic upgrade head"
    )
    # Read the way the runtime reads it: everything generated set aside. The highlighted
    # line carries a word of the layer's own (below), and a reading that counted it would
    # be claiming the file holds a word no version of it ever will.
    assert page.evaluate(
        "() => [...document.querySelectorAll('#walk-code .lf-code-line')]"
        ".map(l => [...l.childNodes].filter(n => !(n.nodeType === 1 && n.dataset.lfGen))"
        ".map(n => n.textContent).join('')).join('')"
    ) == (
        "def bucket_key(request):\n    if request.token:\n"
        '        return f"tok:{request.token.id}"\n    return "anon"\n'
    )

    # `hi` is a background tint and says which line the note beside it is about. Nothing
    # of that reaches a user listening, who gets the block entire with no idea which of
    # it was pointed at — and the numbers can't tell them, being a CSS counter painted
    # into no text node so that a copy of the block is source and not a listing. So the
    # highlighted line says so itself, once, where it is true.
    lines = page.locator("#walk-code .lf-code-line")
    assert "highlighted" in lines.nth(1).aria_snapshot()
    assert page.locator("#walk-code .lf-quiet").count() == 1, (
        "the tinted line is the one that says it, and it says it once"
    )

    appearance = page.evaluate(r"""() => {
      const channels = value => value.match(/[0-9.]+/g).slice(0, 3).map(Number);
      const block = document.querySelector('#walk-code pre');
      const line = document.querySelector('#walk-code .lf-code-line');
      const note = document.querySelector('#walk-code pre > lf-note');
      const noteStyle = getComputedStyle(note);
      const blockRect = block.getBoundingClientRect();
      const noteRect = note.getBoundingClientRect();
      return {
        page: channels(getComputedStyle(document.body).backgroundColor),
        block: channels(getComputedStyle(block).backgroundColor),
        gutter: channels(getComputedStyle(line, '::before').backgroundColor),
        note: channels(noteStyle.backgroundColor),
        noteBorderBlock: noteStyle.borderBlock,
        noteBorderLeftWidth: noteStyle.borderLeftWidth,
        noteRadius: noteStyle.borderRadius,
        noteFont: noteStyle.fontFamily,
        sansFont: getComputedStyle(document.documentElement)
          .getPropertyValue('--sans').trim().replace(/\s+/g, ' '),
        noteInset: {
          left: noteRect.left - blockRect.left,
          right: blockRect.right - noteRect.right,
        },
      };
    }""")
    assert appearance["block"] == [255, 255, 255], appearance
    assert all(
        channel > page_channel
        for channel, page_channel in zip(
            appearance["block"], appearance["page"], strict=True
        )
    ), f"the code canvas is not whiter than the document: {appearance}"
    assert appearance["gutter"] != appearance["block"], appearance
    assert appearance["note"] == appearance["block"], appearance
    assert appearance["noteBorderBlock"].startswith("1px solid"), appearance
    assert appearance["noteBorderLeftWidth"] == "0px", appearance
    assert appearance["noteRadius"] == "0px", appearance
    assert appearance["noteFont"] == appearance["sansFont"], appearance
    assert appearance["noteInset"] == {"left": 1, "right": 1}, appearance

    # A quote spans the command name and its argument tokens.
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "does prod want --sql here?",
            "anchor": {
                "section": "walk",
                "quote": "alembic upgrade head",
                "prefix": "on, then run the marked suite cd gateway &&",
                "suffix": "",
            },
        },
    )
    # Posted to the server rather than through the page, so the page hears about it
    # when its next poll asks.
    told(page)
    expect_open_threads(page, 1)
    assert stranded_quotes(page) == []
    # The mark is a painted range, so what it covers is read back off CSS.highlights
    # rather than off the DOM.
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    marked = page.evaluate("""() => [...CSS.highlights.get('lf-mark').values()]
                                     .map(r => r.toString()).join("")""")
    assert marked == "alembic upgrade head", f"the mark landed on {marked!r}"


def test_shell_commands_share_colors_in_plain_code_widgets_and_diffs(browser, serve):
    """Commands, flags and quoted variables use one grammar across all code surfaces.

    The file extension selects Bash in a diff; ordinary arguments and heredoc
    bodies stay distinct from executable command names, without changing source.

    A plain <pre><code class="language-…"> claims no vocabulary: what every Markdown
    renderer emits carries whatever word its author wrote. One outside $languages stays
    the ink of an uncolored block, with no console error to fail the page over it; the
    known word beside it is the control.

    And `syntax` promises the tokens partition the source exactly: lf-code's line
    numbers, `hi`, and every note's `at` are counted off that partition, so a tokenizer
    that dropped a character would slide all three with nothing on screen saying so.
    The promise is checked at the boundary and the check throws; every language the
    registry offers is driven through the real module, including each one against
    another language's source, which is where a lexer meets input it was never written
    for. It is also what a version bump of the vendored bundle has to survive."""
    source = 'leaf page check "$OUTPUT" --render && cat ./review # inspect\n'
    url = serve(
        leaf_page(
            "shell",
            f"""
<h1 id="t">Shell commands</h1>
<pre id="shell-plain"><code class="language-bash">{escape(source)}</code></pre>
<lf-code id="shell-widget" language="bash"><pre>{escape(source)}</pre></lf-code>
<lf-diff id="shell-diff"><pre>diff --git a/check.sh b/check.sh
--- a/check.sh
+++ b/check.sh
@@ -1 +1 @@
-leaf page check ./review
+{escape(source)}</pre></lf-diff>
<pre id="known"><code class="language-python">x = 1</code></pre>
<pre id="unknown"><code class="language-pythn">y = 2</code></pre>
""",
        )
    )
    page = open_page(browser, url)
    expect(page.locator("#known [data-lf-syn]").first).to_be_attached()
    assert page.locator("#unknown [data-lf-syn]").count() == 0
    assert page.locator("#unknown code").text_content() == "y = 2"
    reading = page.evaluate("""() => {
      const plain = document.querySelector('#shell-plain code');
      const widget = document.querySelector('#shell-widget');
      const diff = document.querySelector('#shell-diff').shadowRoot
        .querySelector('[data-line][data-line-type="change-addition"]');
      const colored = node => [...node.querySelectorAll('[data-lf-syn]')]
        .map(token => ({style: token.style.color, text: token.textContent,
          color: getComputedStyle(token).color,
          fontStyle: getComputedStyle(token).fontStyle}));
      return {plain: colored(plain), widget: colored(widget), diff: colored(diff),
        source: plain.textContent, diffSource: diff.textContent};
    }""")
    assert reading["source"] == source
    assert reading["diffSource"] == source.rstrip("\n")
    for surface in ("plain", "widget", "diff"):
        tokens = reading[surface]
        for color, text in (
            ("name", "leaf"),
            ("keyword", "--render"),
            ("type", "$OUTPUT"),
        ):
            assert any(
                token["style"] == f"var(--syn-{color})" and text in token["text"]
                for token in tokens
            ), (surface, color, text, tokens)
        assert any(
            token["style"] == "var(--syn-string)" and "page" in token["text"]
            for token in tokens
        )
        assert (
            "".join(
                token["text"]
                for token in tokens
                if token["style"] == "var(--syn-comment)"
                and token["fontStyle"] == "italic"
            ).strip()
            == "# inspect"
        ), (surface, tokens)
        assert {token["color"] for token in tokens} == {
            token["color"] for token in reading["plain"]
        }, (surface, tokens)

    # A palette override reaches the document and the diff's shadow tree directly,
    # without running the grammar or replacing any token nodes.
    inherited = page.evaluate("""() => lfUnwatched(() => {
      const roots = [document.querySelector('#shell-plain'),
        document.querySelector('#shell-widget'),
        document.querySelector('#shell-diff').shadowRoot];
      const tokens = roots.map(root => [...root.querySelectorAll('[data-lf-syn]')]
        .find(token => token.textContent === 'leaf'));
      const before = tokens.map(token => getComputedStyle(token).color);
      document.documentElement.style.setProperty('--syn-name', '#a12345');
      return {before, after: tokens.map(token => getComputedStyle(token).color),
        connected: tokens.every(token => token.isConnected)};
    })""")
    assert inherited["connected"], inherited
    assert inherited["after"] == ["rgb(161, 35, 69)"] * 3, inherited

    langs = registry_storage.load_registry(serve.page_dir)["$languages"]["names"]
    samples = [
        'def f(x):\n    """doc\n    <b>&amp;</b>\n    """\n    return f"{x!r}"  # ok\n',
        '# c\ncd x && ls -la | grep "a b" > /dev/null\n',
        'leaf page check "$OUTPUT" --render\r\n\r\n# tail\r\n',
        "\tleaf\rpage\r\ncheck ./review\n\n",
        "cat <<'EOF'\nleaf is literal text\nEOF\n",
        "",
        '{"a": [1, 2, {"b": null}], "c": "<>&"}\n',
        "@@ -1 +1 @@\n-a <b>\n+c &d\n",
        "TARGET_PICKER_SCOPE * FROM t WHERE a = 'x''y'; -- note\n",
        '<!doctype html>\n<a href="x?a=1&b=2">t &amp; u</a>\n',
    ]
    bad = page.evaluate(
        """async ([langs, samples]) => {
          const { syntax } = await window.__lfWidgetApi();
          const bad = [];
          for (const lang of langs)
            for (const src of samples) {
              try {
                const { tokens } = await syntax(src, lang);
                const back = tokens.map(t => t.text).join('');
                if (back !== src) bad.push([lang, src, back]);
              } catch (e) { bad.push([lang, src, String(e)]); }
            }
          return bad;
        }""",
        [langs, samples],
    )
    assert bad == [], f"the tokenizer changed the source: {bad}"

    pierre_bad = page.evaluate(
        """async (langs) => {
          const { parsePatchFiles } =
            await window.__lfVendorImport('pierre-parser.esm.js');
          const { DiffHunksRenderer, renderHTML } =
            await window.__lfVendorImport('pierre-diffs.esm.js');
          const { themeName } =
            await window.__lfVendorImport('syntax.esm.js');
          const source = [
            'diff --git a/example.txt b/example.txt',
            '--- a/example.txt',
            '+++ b/example.txt',
            '@@ -1 +1 @@',
            '-old',
            '+new',
          ].join('\\n');
          const bad = [];
          for (const lang of langs) {
            try {
              const file = parsePatchFiles(source, undefined, true)[0].files[0];
              file.lang = lang;
              const renderer = new DiffHunksRenderer({
                theme: themeName, diffStyle: 'unified', useTokenTransformer: false,
              });
              const rendered = await renderer.asyncRender(file);
              const html = renderHTML(rendered.unifiedContentAST);
              if (!html.includes('new')) bad.push([lang, 'rendered no source']);
            } catch (error) {
              bad.push([lang, String(error)]);
            }
          }
          return bad;
        }""",
        langs,
    )
    assert pierre_bad == [], f"Pierre lacks a declared language: {pierre_bad}"
    assert all(color != "rgb(161, 35, 69)" for color in inherited["before"]), inherited

    heredoc = page.evaluate("""async () => {
      const { syntax } = await window.__lfWidgetApi();
      return (await syntax("cat <<'EOF'\\nleaf is literal text\\nEOF\\n", 'bash')).tokens;
    }""")
    assert any(
        token["style"].get("color") == "var(--syn-string)"
        and "leaf is literal text" in token["text"]
        for token in heredoc
    )
    assert not any(
        token["style"].get("color") == "var(--syn-name)" and "leaf" in token["text"]
        for token in heredoc
    )


def test_a_diff_is_colored_by_each_files_own_path(browser, serve):
    """Pierre renders each file in its own language without changing copyable source.

    A unified diff has no one language, so the file path chooses it and an unknown path
    stays plain. Line-number and indicator columns are presentation, not source: both must
    be absent from syntax input and selection text. Pierre still tokenizes each
    reconstructed side as a whole, so a Python string spanning changed lines remains a
    string.

    Pierre owns changed-line pairing; Leaf preserves its useful visual hierarchy. A
    changed line gets a full semantic background and a brighter inline span where
    Pierre can identify the changed words. The spans must preserve both source text and
    the syntax theme, and a file with no declared language still gets the same diff
    treatment without gaining invented syntax colour."""
    page = open_page(browser, serve(DIFF_PAGE))
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )

    # Through the declared shadow root, where the static Pierre DOM remains visible to
    # Leaf's passage reader.
    files = page.evaluate("""() => [...document.querySelector('#patch').shadowRoot
      .querySelectorAll('details')].map(d => {
      const path = d.querySelector('.lf-diff-path');
      const stat = d.querySelector('.lf-diff-stat');
      return {
        path: path.textContent,
        statGenerated: stat.dataset.lfGen === '1',
        // A flex row draws no native marker, so it wears Leaf's, turned its own way.
        disclosure: (marker => marker.maskImage.includes('svg')
          && marker.rotate === (d.open ? '90deg' : 'none'))(
          getComputedStyle(d.querySelector('summary'), '::before')),
        summaryAligned: Math.abs(path.getBoundingClientRect().top
          - stat.getBoundingClientRect().top) < 1,
        lines: [...d.querySelectorAll('[data-line]')].map(l => ({
          kind: l.dataset.lineType,
          text: l.textContent,
          indicator: getComputedStyle(l, '::before').content,
          indicatorSelect: getComputedStyle(l, '::before').userSelect,
          colors: [...l.querySelectorAll('[data-lf-syn]')]
            .map(s => [s.style.color, s.textContent, getComputedStyle(s).fontStyle]),
        })),
        separators: [...d.querySelectorAll('[data-separator]')].map(s => ({
          text: s.textContent.trim(),
          chrome: s.classList.contains('lf-ui'),
        })),
        numbers: [...d.querySelectorAll('.lf-diff-line-comment')].map(n => ({
          text: n.textContent,
          chrome: n.classList.contains('lf-ui'),
          generated: n.dataset.lfGen === '1',
          label: n.getAttribute('aria-label'),
          userSelect: getComputedStyle(n).userSelect,
          face: [getComputedStyle(n).fontFamily, getComputedStyle(n).fontSize],
        })),
        code: [getComputedStyle(d.querySelector('code[data-code]')).fontFamily,
               getComputedStyle(d.querySelector('code[data-code]')).fontSize],
      };
    })""")
    by_path = {f["path"]: f["lines"] for f in files}
    assert set(by_path) == {
        "gateway/limits.py",
        "gateway/config.yaml",
        "deploy/Dockerfile",
    }
    assert all(file["summaryAligned"] for file in files), (
        "a file path and its change counts split across summary rows"
    )
    assert all(file["disclosure"] for file in files), (
        "a file summary lost the triangle that says whether it is open"
    )
    assert all(file["statGenerated"] for file in files), (
        "derived change counts should be said but not read as authored words"
    )
    separators = [separator for file in files for separator in file["separators"]]
    assert separators, "the fixture exercised no Pierre hunk separator"
    assert all(separator["chrome"] for separator in separators), separators
    numbers = [number for file in files for number in file["numbers"]]
    assert numbers, "the rendered diff has no visible line numbers"
    assert all(
        number["text"].isdigit()
        and number["chrome"]
        and number["generated"]
        and number["label"].startswith("Comment on ")
        and number["userSelect"] == "none"
        for number in numbers
    ), numbers
    # A line number wears `lf-ui` because `offer()` built it, and it takes its face from
    # the diff it counts: the control face stays out of the declared tree.
    assert all(
        number["face"] == file["code"] for file in files for number in file["numbers"]
    ), [(file["code"], file["numbers"][:1]) for file in files]

    reading = page.evaluate("""async () => {
      const { says, wrote } = await window.__lfWidgetApi();
      const { textNodesUnder } = await window.__lfCheckApi();
      const diff = document.querySelector('#patch');
      const shadow = diff.shadowRoot;
      const segments = textNodesUnder(document)
        .filter(({node}) => node.getRootNode() === shadow);
      const reference = document.createElement('pre');
      reference.textContent = 'literal evidence';
      document.querySelector('main').append(reference);
      const rendered = shadow.querySelector('code[data-code]');
      const statText = shadow.querySelector('.lf-diff-stat').textContent;
      const leafFont = getComputedStyle(reference).fontFamily;
      const leafFontSize = getComputedStyle(reference).fontSize;
      const leafLineHeight = getComputedStyle(reference).lineHeight;
      const leafBackground = getComputedStyle(reference).backgroundColor;
      const backgroundChannels = leafBackground.match(/[0-9.]+/g).slice(0, 3).map(Number);
      const pageBackground = getComputedStyle(document.body).backgroundColor;
      reference.remove();
      return {
        segmentCount: segments.length,
        saysPath: says(document).includes('gateway/limits.py'),
        wrotePath: wrote(document).includes('gateway/limits.py'),
        saysStat: says(document).includes(statText),
        wroteStat: wrote(document).includes(statText),
        lineNumberWords: segments
          .filter(({node}) => node.parentElement?.closest('.lf-diff-line-comment'))
          .map(({node}) => node.data),
        separatorText: segments
          .filter(({node}) => node.parentElement?.closest('[data-separator]'))
          .map(({node}) => node.data),
        font: getComputedStyle(rendered).fontFamily,
        fontSize: getComputedStyle(rendered).fontSize,
        lineHeight: getComputedStyle(rendered).lineHeight,
        background: getComputedStyle(rendered.parentElement).backgroundColor,
        leafFont,
        leafFontSize,
        leafLineHeight,
        leafBackground,
        backgroundIsWhite: backgroundChannels.every(channel => channel === 255),
        backgroundIsSeparateFromPage: leafBackground !== pageBackground,
      };
    }""")
    assert reading["segmentCount"] > 0, "the passage assertion read no diff text"
    # The parser supplies the visible file path; it was not written into the page.
    assert reading["saysPath"] and not reading["wrotePath"], reading
    assert reading["saysStat"] and not reading["wroteStat"], reading
    assert reading["lineNumberWords"] == [], (
        f"line number chrome entered the page reading: {reading}"
    )
    assert reading["separatorText"] == [], (
        f"Pierre separator chrome entered the page reading: {reading}"
    )
    assert reading["font"] == reading["leafFont"], reading
    assert reading["fontSize"] == reading["leafFontSize"] == "13.5px", reading
    assert reading["lineHeight"] == reading["leafLineHeight"] == "20px", reading
    assert reading["background"] == reading["leafBackground"], reading
    assert reading["backgroundIsWhite"], reading
    assert reading["backgroundIsSeparateFromPage"], reading

    py = by_path["gateway/limits.py"]
    assert any(
        ["var(--syn-keyword)", "if", "normal"] in line["colors"] for line in py
    ), py
    assert {color for line in py for color, _, _ in line["colors"]} >= {
        "var(--syn-keyword)",
        "var(--syn-string)",
        "var(--syn-name)",
    }

    # Docstrings keep the theme's comment color and italic style on both sides.
    doc = [line for line in py if "Called on logout" in line["text"]]
    assert len(doc) == 2, [line["text"] for line in py]
    for line in doc:
        assert {color for color, _, _ in line["colors"]} == {"var(--syn-comment)"}, line
        assert {style for _, _, style in line["colors"]} == {"italic"}, line
        assert "".join(text for _, text, _ in line["colors"]) == line["text"], line

    # The yaml key keeps its theme color rather than tokenizing the deleted line as a list
    # item or the added line as an arbitrary string.
    yml = [
        line
        for line in by_path["gateway/config.yaml"]
        if line["kind"] in ("change-addition", "change-deletion")
    ]
    assert len(yml) == 2
    for line in yml:
        assert any(
            color == "var(--syn-type)" and "burst" in text
            for color, text, _ in line["colors"]
        ), line
    assert {
        (line["kind"], line["indicator"], line["indicatorSelect"]) for line in yml
    } == {
        ("change-addition", '"+"', "none"),
        ("change-deletion", '"-"', "none"),
    }, "changed lines need visible indicators that selection leaves behind"

    # `\\ No newline at end of file` is diff metadata, not selectable source.
    assert not any("No newline at end of file" in line["text"] for line in py)

    # No extension the table names: plain, the way a lf-code with no `language` is.
    assert all(line["colors"] == [] for line in by_path["deploy/Dockerfile"]), by_path[
        "deploy/Dockerfile"
    ]

    # The visible indicator is generated presentation, so the DOM and a full-line
    # selection still contain exact source. File headers are metadata already represented
    # by the summary, so the widget drops them instead of leaving hidden anchor text.
    assert [line["text"] for line in by_path["gateway/config.yaml"]] == [
        "  burst: 20",
        "  burst: 40",
        "  window: 60",
    ]
    selected = page.evaluate("""() => {
      const lines = document.querySelector('#patch').shadowRoot.querySelectorAll('[data-line]');
      const line = [...lines].find(l => l.dataset.lineType === 'change-addition'
        && l.textContent.includes('burst'));
      const range = document.createRange();
      range.selectNodeContents(line);
      const selection = getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      return selection.toString();
    }""")
    assert selected == "  burst: 40"
    page.evaluate("getSelection().removeAllRanges()")

    # Native multi-line copying crosses the interleaved numbered controls. Only the
    # source belongs on the clipboard; generated indicators and buttons stay behind.
    page.locator("lf-diff [data-line]").filter(
        has_text="burst: 20"
    ).scroll_into_view_if_needed()
    ends = page.evaluate("""() => {
      const root = document.querySelector('#patch').shadowRoot;
      const lines = [...root.querySelectorAll('[data-line]')].filter(line =>
        line.closest('details').querySelector('.lf-diff-path').textContent === 'gateway/config.yaml');
      const range = document.createRange();
      range.selectNodeContents(lines[0]);
      const first = range.getBoundingClientRect();
      range.selectNodeContents(lines.at(-1));
      const last = range.getBoundingClientRect();
      return [[first.left, first.top + first.height / 2],
              [last.right, last.top + last.height / 2]];
    }""")
    select(page, *ends)
    copied = "  burst: 20\n  burst: 40\n  window: 60"
    assert page.evaluate("getSelection().toString()") == copied
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.keyboard.press("ControlOrMeta+C")
    assert page.evaluate("navigator.clipboard.readText()") == copied
    page.evaluate("getSelection().removeAllRanges()")

    files = page.evaluate("""() => [...document.querySelector('#patch').shadowRoot
      .querySelectorAll('details')].map(d => ({
      path: d.querySelector('.lf-diff-path').textContent,
      lines: [...d.querySelectorAll('[data-line]')].map(line => ({
        kind: line.dataset.lineType,
        text: line.textContent,
        marks: [...line.querySelectorAll('[data-diff-span]')].map(span => span.textContent),
        inked: [...line.querySelectorAll('[data-diff-span] [data-lf-syn]')]
          .map(span => [span.style.color, span.textContent]),
        linePaint: getComputedStyle(line.parentElement).backgroundColor,
        prePaint: getComputedStyle(line.closest('pre')).backgroundColor,
        markPaint: [...line.querySelectorAll('[data-diff-span]')].map(span => {
          const style = getComputedStyle(span);
          return [style.backgroundColor, style.textDecorationLine];
        }),
      })),
    }))""")
    by_path = {file["path"]: file["lines"] for file in files}
    assert set(by_path) == {
        "gateway/limits.py",
        "gateway/config.yaml",
        "deploy/Dockerfile",
    }

    def changed(path, kind, text):
        return next(
            line
            for line in by_path[path]
            if line["kind"] == kind and text in line["text"]
        )

    before = changed("gateway/config.yaml", "change-deletion", "burst: 20")
    after = changed("gateway/config.yaml", "change-addition", "burst: 40")
    assert before["marks"] and any("20" in mark for mark in before["marks"])
    assert after["marks"] and any("40" in mark for mark in after["marks"])
    assert ["var(--syn-number)", "20"] in before["inked"]
    assert ["var(--syn-number)", "40"] in after["inked"]

    changed_lines = [
        line
        for lines in by_path.values()
        for line in lines
        if line["kind"] in ("change-addition", "change-deletion")
    ]
    assert changed_lines
    assert all(line["linePaint"] != line["prePaint"] for line in changed_lines)
    assert before["linePaint"] != after["linePaint"], (
        "additions and deletions need distinct semantic fills"
    )

    inline_paint = [paint for line in changed_lines for paint in line["markPaint"]]
    assert inline_paint
    assert all(background != "rgba(0, 0, 0, 0)" for background, _ in inline_paint)
    assert {decoration for _, decoration in inline_paint} == {"none"}
    assert all(
        background != line["linePaint"]
        for line in changed_lines
        for background, _ in line["markPaint"]
    ), "inline changes need a stronger fill than their changed line"

    # Pierre's inline comparison is language-independent. Dockerfile is intentionally
    # plain in Leaf's registry, but the edited dependency is still called out.
    docker_before = changed("deploy/Dockerfile", "change-deletion", "requirements.txt")
    docker_after = changed("deploy/Dockerfile", "change-addition", "--no-cache-dir")
    assert docker_before["marks"] or docker_after["marks"]
    assert not any(line["inked"] for line in by_path["deploy/Dockerfile"])

    # The generated indicators never prefix the rendered source on any file.
    assert all(
        not line["text"].startswith(("+", "-"))
        for lines in by_path.values()
        for line in lines
    )

    # The same host then serves as a widget's shadow stage. Restaging retains a Lit
    # container and its editor while other nodes leave, and a passage spanning the
    # stage's children reads the stage as the host's section.
    result = page.evaluate(
        """async () => {
          const {html, render, shadowStage} = await window.__lfWidgetApi();
          const host = document.querySelector('lf-diff');
          const container = document.createElement('div');
          const input = document.createElement('input');
          input.value = 'draft reply';
          const paint = text => render(html`<p>${text}</p>${input}`, container);
          paint('Before restaging');
          const old = document.createElement('p');
          old.textContent = 'old reading';
          shadowStage(host, [old, document.createComment('old stage'), container]);
          input.focus();
          input.setSelectionRange(2, 5);
          const next = document.createElement('p');
          next.textContent = 'new reading';
          shadowStage(host, [next, container]);
          paint('After restaging');
          return {
            text: [...host.shadowRoot.childNodes]
              .filter(node => node.localName === 'p')
              .map(node => node.textContent),
            comments: [...host.shadowRoot.childNodes]
              .filter(node => node.nodeType === Node.COMMENT_NODE).length,
            rendered: container.querySelector('p').textContent,
            focused: host.shadowRoot.activeElement === input,
            value: input.value,
            selection: [input.selectionStart, input.selectionEnd],
          };
        }"""
    )
    assert result == {
        "text": ["new reading"],
        "comments": 0,
        "rendered": "After restaging",
        "focused": True,
        "value": "draft reply",
        "selection": [2, 5],
    }

    result = page.evaluate(
        """async () => {
          const {shadowStage} = await window.__lfWidgetApi();
          const {anchorForRange} = await window.__lfCheckApi();
          const host = document.querySelector('lf-diff');
          const first = document.createElement('p');
          first.textContent = 'first';
          const last = document.createElement('p');
          last.textContent = 'last';
          shadowStage(host, [first, last]);
          const range = document.createRange();
          range.setStart(first.firstChild, 0);
          range.setEnd(last.firstChild, last.firstChild.length);
          return anchorForRange(range);
        }"""
    )
    assert result["section"] == "patch"
    assert result["quote"] == "first last"


def test_a_diff_marks_changed_words_only_where_the_line_mostly_stayed(browser, serve):
    """A word mark locates an edit inside a line that otherwise stayed the same.

    Where most of a changed pair was rewritten, marks would cover most of both lines
    and point at nothing, so the pair stays a plain removed row above a plain added
    row, as delta's default `--max-line-distance` leaves it."""
    markup = leaf_page(
        "diff",
        """
<h1 id="t">Diff</h1>
<lf-diff id="patch"><pre>
diff --git a/notes.md b/notes.md
--- a/notes.md
+++ b/notes.md
@@ -1,4 +1,4 @@
 Release steps:
-1. Run the test suite.
-2. Tell the team the build is ready.
+1. Run the full test suite.
+2. Tag the commit and push the tag.
 3. Close the milestone.
</pre></lf-diff>
""",
    )
    page = open_page(browser, serve(markup))
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    marks = page.evaluate("""() => Object.fromEntries(
      [...document.querySelector('#patch').shadowRoot.querySelectorAll('[data-line]')]
        .filter(line => line.dataset.lineType.startsWith('change-'))
        .map(line => [line.textContent,
          [...line.querySelectorAll('[data-diff-span]')].map(span => span.textContent)]))""")
    assert marks == {
        "1. Run the test suite.": [],
        "2. Tell the team the build is ready.": [],
        "1. Run the full test suite.": ["full "],
        "2. Tag the commit and push the tag.": [],
    }


def test_a_diff_can_start_with_every_file_collapsed(browser, serve):
    """A large patch can defer every file body without losing native disclosure."""
    authored = DIFF_PAGE.replace(
        '<lf-diff id="patch"><pre>', '<lf-diff id="patch" collapsed><pre>'
    )
    page = open_page(browser, serve(authored))
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )

    details = page.locator("lf-diff details")
    expect(details).to_have_count(3)
    assert details.evaluate_all("items => items.every(item => !item.open)")
    # A closed file of a patch text renders only when it opens, as a manifest's does.
    lines = page.locator("lf-diff [data-line]")
    expect(lines).to_have_count(0)
    details.first.locator("summary").click()
    expect(details.first).to_have_attribute("open", "")
    expect(details.first.locator("[data-line]").first).to_be_visible()
    assert lines.count() == details.first.locator("[data-line]").count()


DIFF_PATCH_CASES = json.loads(
    (Path(__file__).parents[1] / "diff_patch_cases.json").read_text()
)["cases"]


# Diffs the table's rows do not reach, drawn beside them on the table's page: source
# markup Pierre must keep as data, path-only renames whose names are generated said
# words (quoted and byte-order-marked paths among them), and the documented entity for
# an empty final context line, which survives wrapper cleanup.
DIFF_INERT_SOURCE = """diff --git a/example.html b/example.html
--- a/example.html
+++ b/example.html
@@ -1 +1 @@
-old
+<img src=x onerror=globalThis.__lfDiffPwned=1>"""
DIFF_MIXED_RENAME_SOURCE = '''diff --git a/app.js b/app.js
--- a/app.js
+++ b/app.js
@@ -1 +1 @@
-const value = 1;
+const value = 2;
diff --git a/old-name.js b/new-name.js
similarity index 100%
rename from old-name.js
rename to new-name.js
diff --git "a/old\\tname.js" "b/new\\tname.js"
similarity index 100%
rename from "old\\tname.js"
rename to "new\\tname.js"
diff --git "a/\\357\\273\\277old.js" "b/\\357\\273\\277new.js"
similarity index 100%
rename from "\\357\\273\\277old.js"
rename to "\\357\\273\\277new.js"'''
DIFF_EMPTY_CONTEXT_MARKUP = """diff --git a/example.txt b/example.txt
--- a/example.txt
+++ b/example.txt
@@ -1,2 +1,2 @@
 visible
&#32;
"""


def test_staged_widget_controls_name_the_presses_their_owners_make(browser, serve):
    """A key on screen is a key that works, and its inversion costs just as much: the
    press is real, the user can make it, and no surface says so.

    A widget may still declare the meaning of an owned press when that meaning is worth
    naming in Leaf's command reference. The row describes the control's behavior without
    reimplementing it.

    The comparison handle's arrows and endpoints are the component's own keyboard
    pattern, while a <summary> answers Enter and Space itself and leaves its horizontal
    arrow to the disclosure scope. The component and browser rows bind no `run`; the
    summary's arrow does. A row consuming a press it does not make would be the same lie
    from the other side.

    The staged control is the one the register could not reach at all.
    `document.activeElement` retargets to the host, so the scope walk started at the
    widget and never saw the control the user was located on."""
    url = serve(
        NATIVE_CONTROL_PAGE,
        media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
    )
    page = open_page(browser, url)

    page.locator("lf-shot").get_by_role("radio", name="Slider", exact=True).click()
    comparison = page.locator("lf-shot wa-comparison")
    handle = comparison.get_by_role("scrollbar")
    handle.scroll_into_view_if_needed()
    handle.focus()
    page.keyboard.press("ArrowRight")
    expect(comparison).to_have_attribute("position", "51")
    page.keyboard.press("End")
    expect(comparison).to_have_attribute("position", "100")

    summary = page.locator("lf-diff summary").first
    details = page.locator("lf-diff details").first
    # Clear of the floating panel, where the user sees the control a key acts on.
    summary.evaluate("el => el.scrollIntoView({block: 'center'})")
    summary.focus()
    assert details.evaluate("el => el.open"), "the fixture's disclosure starts open"
    page.keyboard.press("Enter")
    assert not details.evaluate("el => el.open")
    # The line is one of two surfaces naming this row's keys, and a listener reads the
    # other. Both answer from the same DISCLOSE call, so both turn over on the toggle —
    # and the repaint that keeps them together is the document's disclosure watch rather
    # than anything this widget does, which is what leaves a widget free to declare a
    # disclosure row and nothing else. Read once, by the same clock as the line: the
    # heartbeat repaints scopes too, so a retrying read goes green on the tick inside its
    # budget whether or not the watch painted anything.
    rendered(page)
    assert summary.get_attribute("aria-keyshortcuts") == "Enter Space ArrowRight"

    # The row also names an arrow, which no browser answers, so unlike the pair above it is
    # only ever as good as the scope that runs it — and that scope has to find a staged
    # disclosure the same way this declaration had to reach a staged control. Read off the
    # document alone it finds none here, the page's only <details> being the ones the
    # widget put in a shadow root. The press is what says so, not the chip: this widget's
    # own row is the nearer of the two naming these keys, so it prints them either way.
    page.keyboard.press("ArrowRight")
    assert details.evaluate("el => el.open")
    # And the keys turn over inside the press, read once so a poll cannot answer for it.
    # A toggle from a staged root is not composed, so no document listener hears it: this
    # is the watch `shadowStage` hands each root.
    rendered(page)
    assert summary.get_attribute("aria-keyshortcuts") == "Enter Space ArrowLeft"


def test_a_tab_inside_a_shadow_tree_no_stage_watches_still_reaches_current_location(
    browser, serve
):
    """A component that makes its own shadow root, as a Web Awesome control does, moves
    focus between its own controls with no event reaching any root focus.js listens on.
    The current location is still read once the key's task ends, so every reader of it
    hears the move as the Tab it was."""
    page = open_page(browser, serve(DIFF_PAGE))
    page.evaluate(
        """async () => {
          const host = document.createElement("span");
          host.id = "own-root";
          host.attachShadow({ mode: "open" }).innerHTML =
            "<button id=one>one</button><button id=two>two</button>";
          document.querySelector("main").append(host);
          const { onCurrentLocation } = await window.__lfCheckApi();
          window.heard = [];
          onCurrentLocation((node, cause) => window.heard.push([node?.id ?? null, cause]));
          host.shadowRoot.getElementById("one").focus();
        }"""
    )
    page.wait_for_function("() => window.heard.some(([id]) => id === 'one')")
    page.keyboard.press("Tab")
    page.wait_for_function(
        "() => document.getElementById('own-root').shadowRoot.activeElement?.id === 'two'"
    )
    page.wait_for_function("() => window.heard.at(-1)?.[0] === 'two'")
    assert page.evaluate("() => window.heard.at(-1)") == ["two", "step"]


@pytest.mark.parametrize(
    "removed",
    [
        "layer",
        "reparent",
        "former-popover",
        "retained-root",
        "retained-immediate",
    ],
)
def test_internal_focus_moves_publish_before_old_markup_is_collected(
    browser, serve, removed
):
    """Entering a component subscribes focus to its later internal moves. The move
    publishes while both controls are alive; detached ancestry cannot recast its cause.
    """
    page = open_page(
        browser, serve(leaf_page("Focus lifetime", "<h1>Focus lifetime</h1>"))
    )
    page.evaluate(
        """async removed => {
          const host = document.createElement('div');
          host.id = 'own-root';
          host.attachShadow({mode: 'open'}).innerHTML =
            '<dialog open><button id="one">First</button></dialog>' +
            '<button id="two">Next</button>';
          document.querySelector('main').append(host);
          if (removed === 'former-popover') {
            const dialog = host.shadowRoot.querySelector('dialog');
            const layer = document.createElement('div');
            layer.popover = 'manual';
            layer.append(...dialog.children);
            dialog.replaceWith(layer);
            layer.showPopover();
          }
          const {onCurrentLocation} = await window.__lfCheckApi();
          window.heard = [];
          onCurrentLocation((node, cause) => window.heard.push([node?.id ?? null, cause]));
          host.shadowRoot.getElementById('one').focus();
        }""",
        removed,
    )
    page.wait_for_function("() => window.heard.at(-1)?.[0] === 'one'")
    if removed in {"retained-root", "retained-immediate"}:
        assert page.evaluate(
            """async removed => {
              const oldHost = document.getElementById('own-root');
              const oldRoot = oldHost.shadowRoot;
              const nextHost = document.createElement('div');
              const nextRoot = nextHost.attachShadow({mode: 'open'});
              oldHost.after(nextHost);
              const {move} = await window.__lfWidgetApi();
              const place = removed === 'retained-immediate' ? move : (parent, node) => parent.moveBefore(node, null);
              place(nextRoot, oldRoot.querySelector('dialog'), null);
              place(nextRoot, oldRoot.getElementById('two'), null);
              oldHost.id = '';
              nextHost.id = 'own-root';
              const preserved = nextRoot.activeElement === nextRoot.getElementById('one');
              if (removed === 'retained-immediate') nextRoot.getElementById('two').focus();
              return preserved;
            }""",
            removed,
        )
        rendered(page)
    page.evaluate(
        """removed => {
          const root = document.getElementById('own-root').shadowRoot;
          window.oldFocus = new WeakRef(root.getElementById('one'));
          // This internal move emits no event at the document. The focus owner
          // must hear it inside the root, while its departing node is still alive.
          root.getElementById('two').focus();
          const layer = root.querySelector('dialog, [popover]');
          if (removed === 'former-popover') window.detachedLayer = layer;
          else layer.open = false;
          layer.remove();
        }""",
        removed,
    )
    rendered(page)
    if removed == "reparent":
        page.evaluate(
            """() => {
              const layer = document.createElement('dialog');
              layer.open = true;
              layer.append(window.oldFocus.deref());
            }"""
        )
        rendered(page)
    elif removed == "former-popover":
        page.evaluate(
            "() => { window.detachedLayer.removeAttribute('popover'); window.detachedLayer = null; }"
        )
        rendered(page)
    assert page.evaluate("() => window.heard.at(-1)") == ["two", "move"]
    heard = page.evaluate("() => window.heard")
    cdp = page.context.new_cdp_session(page)
    try:
        cdp.send("HeapProfiler.collectGarbage")
    finally:
        cdp.detach()
    assert page.evaluate("() => window.oldFocus.deref() === undefined")
    page.keyboard.press("Shift")
    page.wait_for_function("() => window.heard.at(-1)?.[0] === 'two'")
    assert page.evaluate("() => window.heard") == heard


def test_first_entry_into_a_shadow_root_can_forward_focus(browser, serve, subtests):
    """A component's focus handler can forward its first arrival before focusin.
    The final control still publishes the placement's cause without another input.
    """
    page = open_page(browser, serve(leaf_page("Focus entry", "<h1>Focus entry</h1>")))
    page.evaluate(
        """async () => {
          const {onCurrentLocation} = await window.__lfCheckApi();
          onCurrentLocation((node, cause) => window.heard?.push([node?.id ?? null, cause]));
        }"""
    )
    # Each arrival enters a root of its own, whose forwarding handler has not run yet.
    for arrival in ("native", "return"):
        with subtests.test(arrival=arrival):
            page.evaluate(
                """async arrival => {
                  const host = document.createElement('div');
                  const root = host.attachShadow({mode: 'open'});
                  root.innerHTML = '<button id="one">First</button><button id="two">Next</button>';
                  document.querySelector('main').append(host);
                  const {focusDestination} = await window.__lfWidgetApi();
                  window.heard = [];
                  const one = root.getElementById('one');
                  one.addEventListener('focus', () => root.getElementById('two').focus(), {once: true});
                  if (arrival === 'return') focusDestination(one, 'return');
                  else one.focus();
                }""",
                arrival,
            )
            assert page.evaluate("() => window.heard") == [
                ["two", "return" if arrival == "return" else "move"]
            ]


def test_two_comments_on_one_element_both_stay_anchored(browser, serve):
    """A figure can carry more than one thread. When the page's record of what it drew was
    keyed by the mark, the second comment overwrote the first, and the thread told the
    user the first one's passage wasn't in this version — while it sat outlined on
    screen for the second."""
    url = serve(INLINE_PAGE)
    page = open_page(browser, url)
    for text in ("first on the figure", "second on the figure"):
        post_event(
            page,
            url.rsplit("/versions/", 1)[0] + "/api/event",
            data={
                "kind": "comment",
                "revision": 1,
                "text": text,
                "anchor": {"section": "fig"},
            },
        )
    told(page)
    expect_open_threads(page, 2)
    stranded = stranded_quotes(page)
    assert stranded == [], f"outlined on screen, reported missing: {stranded}"
    # The contour an open thread raises puts no paint over the figure's contents: the
    # figure draws it as its outline, outside itself at the region's gap.
    figure = page.locator("#fig")
    expect(figure).to_have_class(re.compile(r"\blf-mark-el\b"))
    figure.scroll_into_view_if_needed()
    figure.click()
    expect(figure).to_have_class(re.compile(r"\blf-projected-mark\b"))
    expect(figure).to_have_attribute("data-lf-mark", re.compile("."))
    look = figure.evaluate(MARK)
    region = page.evaluate(
        "() => parseFloat(getComputedStyle(document.documentElement)"
        ".getPropertyValue('--focus-region-gap'))"
    )
    assert look and look["style"] == "solid" and look["width"] > 0, look
    assert look["offset"] == region, (look, region)


FOCUSED_THREAD = "document.activeElement?.closest('.lf-page-thread')"


def thread_a_press_opened(page):
    """The thread a press on a mark landed in, or None if none ever took focus.

    The preview card the press opens places itself and only then hands over focus, from
    the placement promise `deferThreadPreviewFocus` waits on — so the thread arrives a
    frame after the press rather than inside it. This states that ordering rather than
    reading across it. It answers None rather than raising, so a caller still reports
    which thread opened instead of raising over the reading.
    """
    try:
        page.wait_for_function(f"() => {FOCUSED_THREAD} != null")
    except PlaywrightTimeout:
        return None
    return page.evaluate(f"() => {FOCUSED_THREAD}.innerText")


def test_a_press_on_a_mark_opens_the_thread_under_the_point(browser, serve):
    """The thread the pointer is over and the thread a press opens are one reading of one
    point.

    They came from two doors, though. The hover hit-tests the pointer record the runtime
    keeps, and the click read its own clientX and clientY — a `click` is a legacy mouse
    event, so those arrive rounded to a whole pixel, while markAt measures against
    getClientRects, whose edges are floats. Within a pixel of a mark's edge the two
    answer different threads: a quote lights up under the hand and the press on it opens
    the neighbour's thread, which is the same disagreement the aim carried and this
    is the surface it was left on.

    The seam fixture puts the pointer where the true point and its rounded twin are over
    different items, and a comment on each makes the disagreement a pair of cards rather
    than a hit and a miss — so what is asserted is which thread opened, not whether one
    did. Which item the true point is over follows where in the pixel the seam fell, so
    the expected card is read off the point rather than named here."""
    url = serve(AIM_SEAM_PAGE)
    for ident in ("seam-upper", "seam-lower"):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"About {ident}.",
                "anchor": {"section": ident},
            },
        )
    page = open_page(browser, url)
    expect_open_threads(page, 2)
    seam = page.evaluate(AIM_SEAM, ["seam-upper", "seam-lower"])
    assert seam and {seam["at"], seam["rounded"]} == {"seam-upper", "seam-lower"}, (
        "the fixture no longer straddles a seam — the point and the whole pixel it rounds "
        "to are not on the two marked elements either side of it, so a press that read either "
        f"of them would pass this: {seam}"
    )

    page.mouse.move(seam["x"], seam["y"])
    page.mouse.click(seam["x"], seam["y"])
    opened = thread_a_press_opened(page)
    assert opened and f"About {seam['at']}." in opened, (
        f"the hover promised the thread on {seam['at']}, and the press at the same point "
        f"opened: {opened}"
    )


MARKED_SENTENCE = (
    "First pass: when the deploy fails again in the night, the run is retried "
    "until it lands."
)


def mark_the_first_sentence(browser, serve):
    """`EDGE_PAGE` with its opening sentence commented on.

    The sentence's own tail is left unmarked, which is where the shift-click below starts
    so that only its extension reaches the painted words."""
    url = serve(EDGE_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "About the retry.",
            "anchor": {"section": "edge", "quote": MARKED_SENTENCE},
        },
    )
    page = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    return page


def marked_run(page):
    """The painted mark's first line, to aim a gesture inside."""
    return page.evaluate(
        """() => { const r = [...CSS.highlights.get('lf-mark')][0].getClientRects()[0];
                   return {left: r.left, right: r.right, y: r.top + r.height / 2}; }"""
    )


def words_in_hand(page):
    return page.evaluate(
        """() => {
          const sel = getSelection();
          return {
            selected: sel && !sel.isCollapsed ? sel.toString() : "",
            inPanel: Boolean(
              document.querySelector('.lf-floating-panel')?.contains(document.activeElement)
            ),
          };
        }"""
    )


def word_at(page, selector, word):
    """The middle of `word` inside `selector`'s own text, for a real press on it."""
    return page.evaluate(
        """([selector, word]) => {
          const words = document.querySelector(selector).firstChild;
          const at = words.data.indexOf(word);
          const want = document.createRange();
          want.setStart(words, at);
          want.setEnd(words, at + word.length);
          const r = want.getClientRects()[0];
          return {x: r.left + r.width / 2, y: r.top + r.height / 2};
        }""",
        [selector, word],
    )


def take_by_drag(page):
    run = marked_run(page)
    select(
        page,
        (run["left"] + 4, run["y"]),
        (run["left"] + (run["right"] - run["left"]) / 2, run["y"]),
        steps=10,
    )


def take_by_double_click(page):
    # A named word rather than the middle of the painted run: which character the midpoint
    # falls on is the font's business, and a double-click on the space between two words
    # takes nothing at all. Measured, it is a letter on this Mac's Charter and a space on
    # CI's Linux Chromium — so the run's geometry aims the drag, which only needs to end
    # among words, and never a gesture that has to land on one.
    #
    # The first click of the pair is a press by the door's own rule, and opens the mark's
    # thread; the second takes the word and is refused, and focus comes back to the page
    # with it. What the user is left holding is what this arm asserts.
    at = word_at(page, "#edge p", "deploy")
    page.mouse.dblclick(at["x"], at["y"])


def take_by_shift_click(page):
    # Start in the sentence's unmarked tail, then extend back into the mark, so the
    # click that reaches the door lands on painted words.
    tail = word_at(page, "#edge p", "Nothing")
    page.mouse.click(tail["x"], tail["y"])
    run = marked_run(page)
    page.keyboard.down("Shift")
    page.mouse.click(run["left"] + (run["right"] - run["left"]) / 2, run["y"])
    page.keyboard.up("Shift")


@pytest.mark.parametrize(
    "take",
    [take_by_drag, take_by_double_click, take_by_shift_click],
    ids=["drag", "double-click", "shift-click"],
)
def test_taking_words_inside_a_mark_keeps_them_and_a_press_still_opens_the_thread(
    browser, serve, take
):
    """Marked words are still words to comment on: every way of taking them leaves the
    user holding them, with the 💬 on what was taken and the page still under them.

    What the user ends up with, rather than where the gesture went on the way: a
    double-click's first click is a press by the door's own rule and opens the mark's
    thread, and only its second click takes a word. Measured, that excursion costs the
    user a focus round trip through the reply box and no movement of the reading column
    at all, and refusing it would mean holding every press on a mark for the length of the
    double-click interval — the ordinary gesture made sluggish for the rarer one. So each
    arm asserts the settled result, and the press below asserts that the mark still opens.

    A click ends a gesture that took words as surely as it ends a press, and the mark's
    door read every one of them as a press. The thread it opened took the user's focus,
    and a thread whose reply box takes it collapses the document's selection — so the
    words went, the 💬 with them, and marked passages became the one part of a page a user
    could not quote.

    All three gestures, because the first reading written for this covered only the drag:
    it asked how far the pointer had travelled, and a double-click's second press and a
    shift-click's extension both take words without moving it. Each arm then makes the
    press the mark is for, where the gesture's own words still stand selected — a reading
    taken off the current selection rather than off what the press changed refuses that
    press as a gesture of its own, and the mark stops opening at all."""
    page = mark_the_first_sentence(browser, serve)
    resized(page, 1920, 900)
    take(page)
    expect(page.locator(".lf-fab-input")).to_be_visible()
    wait_for_pending_mark(page)
    took = words_in_hand(page)
    assert took["selected"].strip(), (
        "the gesture took no words, so this says nothing about what the door did with them"
    )
    assert not took["inPanel"], "the gesture sent the user into the thread"
    assert pending_text(page) == took["selected"].strip(), (
        f"the 💬 is about {pending_text(page)!r} rather than the words that were taken"
    )

    page.mouse.click(*mark_point(page, "lf-mark"))
    opened = thread_a_press_opened(page)
    assert opened and "About the retry." in opened, opened


def test_pressing_the_current_element_mark_keeps_its_contour(browser, serve):
    """A pointer press briefly moves focus from an open thread to the page before its
    click lands back in the thread. Nothing that marks the current location may look
    deselected in that gap: not the element's contour, which the pointer on the page no
    longer raises, and not the margin entry's selection.

    So the current location holds across the whole press, every frame from mouse-down until after
    the click. The reaction beside the comment is the case that first showed the gap.
    """
    url = serve(INLINE_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "About the figure.",
            "anchor": {"section": "fig"},
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "token": "keep",
            "anchor": {"section": "fig"},
        },
    )
    page = open_page(browser, url)
    figure = page.locator("#fig")
    figure.scroll_into_view_if_needed()
    expect(figure).not_to_have_attribute("data-lf-mark", re.compile(".*"))

    look = """node => { const style = getComputedStyle(node); return {
      line: style.outlineStyle,
      drawn: parseFloat(style.outlineWidth) > 0,
    }; }"""

    box = figure.bounding_box()
    point = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.move(*point)
    page.mouse.click(*point)
    # The compact preview card reveals its reply box on request, so what a press lands on
    # is the thread itself; the paint under test is the same either way.
    assert thread_a_press_opened(page) is not None, "the press opened no thread"
    expect(figure).to_have_attribute("data-lf-mark", re.compile(r"\bhere\b"))
    selected = figure.evaluate(look)

    assert selected == {"line": "solid", "drawn": True}
    expect(page.locator("[data-lf-target-selected]")).to_have_count(1)

    # Every frame of the press and a few after it, read where the user sees them.
    page.evaluate(
        """() => {
          window.lfFrames = [];
          const sample = () => {
            window.lfFrames.push({
              contour: Boolean(document.querySelector(
                '#fig[data-lf-mark~="here"]')),
              entry: document.querySelectorAll('[data-lf-target-selected]').length,
            });
            if (window.lfFrames.length < 400) requestAnimationFrame(sample);
          };
          requestAnimationFrame(sample);
        }"""
    )
    page.mouse.move(*point)
    page.mouse.down()
    page.evaluate(
        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )
    page.mouse.up()
    page.evaluate(
        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )
    frames = page.evaluate("() => window.lfFrames.splice(0)")
    lost = [frame for frame in frames if not frame["contour"] or frame["entry"] != 1]
    assert not lost, (
        f"the current location blinked during the press: {lost} of {len(frames)} frames"
    )


def test_a_tap_on_a_quote_opens_its_thread(browser, serve):
    """A finger is a pointer that arrives already down, and the click it ends on has to
    answer for a position it never moved through.

    A tap dispatches no `pointermove` at all — `pointerdown`, then the compatibility
    mouse events and a `click` carrying `detail=1`. So the record a mouse keeps as it
    travels is still its start value under a finger, and a click reading it asks
    elementFromPoint at a point off the page: the quote under the finger opens nothing,
    which is a wider silence than the pixel the mouse door was about. The record is taken
    from `pointerdown` as well for that reason, and a tap's `pointerdown` carries the true
    fractional point, so the finger gets the same reading the mouse does rather than the
    rounded one its own click would have given.

    The context has a touchscreen because that is the only way to get a gesture with no
    pointermove in it: driving the same point with `page.mouse` records the position on
    the way in and passes whatever the click reads. The seam fixture is reused so the
    tap's own rounded twin is a different item, and a comment on each makes a wrong
    reading a visible thread rather than a miss."""
    url = serve(AIM_SEAM_PAGE)
    for ident in ("seam-upper", "seam-lower"):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"About {ident}.",
                "anchor": {"section": ident},
            },
        )
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, color_scheme="light", has_touch=True
    )
    page = open_page(browser, url, context=context)
    expect_open_threads(page, 2)
    seam = page.evaluate(AIM_SEAM, ["seam-upper", "seam-lower"])
    assert seam and {seam["at"], seam["rounded"]} == {"seam-upper", "seam-lower"}, (
        "the fixture no longer straddles a seam — the point and the whole pixel it rounds "
        "to are not on the two marked elements either side of it, so a tap that read either "
        f"of them would pass this: {seam}"
    )

    page.touchscreen.tap(seam["x"], seam["y"])
    opened = thread_a_press_opened(page)
    assert opened and f"About {seam['at']}." in opened, (
        f"a tap on the quote for {seam['at']} opened: {opened}"
    )


def test_the_pointer_stops_claiming_a_mark_it_scrolled_past(browser, serve):
    """The hover is a function of where the pointer is and where the text is, and scrolling
    moves the second without touching the first. A wrapped <mark> got this from :hover; a
    painted range has to be asked again, so everything that moves the page asks."""
    url = serve(LONG_PAGE)
    page = open_page(browser, url)
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "up top",
            "anchor": {"section": "p0", "quote": "Paragraph 0."},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    spot = page.evaluate("""() => { const r = [...CSS.highlights.get('lf-mark')][0].getClientRects()[0];
                                    return {x: r.left + r.width / 2, y: r.top + r.height / 2}; }""")
    page.mouse.move(spot["x"], spot["y"])
    hand = "({x, y}) => getComputedStyle(document.elementFromPoint(x, y)).cursor"
    page.wait_for_function(f"(spot) => ({hand})(spot) === 'pointer'", arg=spot)
    page.evaluate(
        "() => document.scrollingElement.scrollBy({top: 900, behavior: 'instant'})"
    )
    page.wait_for_function(
        f"(spot) => ({hand})(spot) !== 'pointer'"
        " && (CSS.highlights.get('lf-mark-hover')?.size ?? 0) === 0",
        arg=spot,
    )


def test_an_ambiguous_revised_passage_keeps_its_section_until_the_agent_moves_it(
    browser, serve
):
    """Context tells two copies apart; it must not relocate a comment when the page moves
    on. If a later version rewrites the words beside the anchored copy, that copy confirms
    almost nothing while another copy remains. Neither is now identifiable: document
    order is not evidence, so the thread falls back to its section. An anchored agent reply
    then names the revised passage explicitly, and the complete thread moves there."""
    url = serve(DRIFT_V1)
    page = open_page(browser, live_url(url))
    landed = page.evaluate("""() => {
        const p = document.querySelectorAll('#drift p')[0];
        const phrase = 'The version stamp never lands';
        const at = p.firstChild.data.indexOf(phrase);
        const want = document.createRange();
        want.setStart(p.firstChild, at); want.setEnd(p.firstChild, at + phrase.length);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        return true;
    }""")
    assert landed is True, f"couldn't post the comment ({landed})"
    open_selected_comment(page)
    fab = page.locator(".lf-fab-input")
    expect(fab).to_be_visible()
    fab.focus()
    write(page.locator(".lf-composer leaf-text"), "is this idempotent?")
    with sending(page, "the comment on the ambiguous passage"):
        page.locator(".lf-composer button.lf-compose-submit").click()
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    # Sending leaves the user on the card, ready to read or reply again.
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_focused()
    expect(page.locator(".lf-margin-preview leaf-text")).not_to_be_focused()

    d = serve.page_dir
    stamp_page(d, DRIFT_V2, "revised")
    wait_for_revision(page, 2)
    assert stranded_quotes(page) == []
    assert page.evaluate("() => CSS.highlights.get('lf-mark')?.size ?? 0") == 0
    [transition] = [
        event for event in events_model.read_events(d) if event["kind"] == "reanchor"
    ]
    assert transition["anchor"] == {"section": "drift"}

    [root] = [
        event for event in events_model.read_events(d) if event["kind"] == "comment"
    ]
    revised_passage = "Cache warmup is gone now. The version stamp never lands."
    moved = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(d, root["id"]),
            "--section",
            "drift",
            "--quote",
            revised_passage,
            "--text",
            "I revised this passage and moved the thread onto it.",
        ],
    )
    assert moved.exit_code == 0, moved.output
    reply = json.loads(moved.output)
    assert reply["revision"] == 2 and reply["anchor"]["quote"] == revised_passage
    told(page)

    quote = thread_head(page, root["id"])
    expect(quote).not_to_have_attribute("data-lf-detached", "")
    expect(quote).to_contain_text(revised_passage)
    painted = page.evaluate(
        "() => [...(CSS.highlights.get('lf-mark') ?? [])]"
        ".map(range => range.toString()).join('')"
    )
    assert revised_passage in painted
    [stored_root, stored_reply] = [
        event
        for event in events_model.read_events(d)
        if event["kind"] in {"comment", "reply"}
    ]
    assert stored_root["anchor"] != stored_reply["anchor"]


def test_a_removed_subject_keeps_its_thread_open_and_detached(browser, serve):
    """The author explicitly detaches a thread whose subject leaves the page. Its
    historical quote remains readable in Threads, but it has no page mark, margin row,
    or destination that could conflate it with surviving content."""
    url = serve(DRIFT_V1)
    page = open_page(browser, live_url(url))
    page.evaluate("""() => {
        const p = document.querySelector('#drift p');
        const phrase = 'The version stamp never lands';
        const at = p.firstChild.data.indexOf(phrase);
        const want = document.createRange();
        want.setStart(p.firstChild, at); want.setEnd(p.firstChild, at + phrase.length);
        const selection = getSelection();
        selection.removeAllRanges(); selection.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
    }""")
    open_selected_comment(page)
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").focus()
    write(page.locator(".lf-composer leaf-text"), "why is this section here?")
    with sending(page, "the comment on the section that leaves"):
        page.locator(".lf-composer button.lf-compose-submit").click()
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    d = serve.page_dir
    root = next(
        event for event in events_model.read_events(d) if event["kind"] == "comment"
    )
    replacement = DRIFT_V1.replace(
        '<section id="drift">\n'
        "<p>Cache warmup runs first. The version stamp never lands. Retries are capped at three.</p>\n"
        "<p>Queue drain runs first. The version stamp never lands. Retries are capped at four.</p>\n"
        "</section>",
        '<section id="current"><h2>Current work</h2><p>The old section was removed.</p></section>',
    )
    (d / "index.html").write_text(replacement)
    detached = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "reply",
            "--done",
            response_reference(d, root["id"]),
            "--detach",
            "--text",
            "I removed the section; this thread no longer has a page target.",
        ],
    )
    assert detached.exit_code == 0, detached.output
    wait_for_revision(page, 2)
    told(page)

    expect(page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')).to_have_count(0)
    assert page.evaluate("() => CSS.highlights.get('lf-mark')?.size ?? 0") == 0
    quote = thread_head(page, root["id"])
    expect(quote).to_contain_text("The version stamp never lands")
    expect(quote).to_have_attribute("data-lf-detached", "")
    expect(quote.locator(".lf-anchor-status")).to_have_text("Not in the latest version")
    # With nowhere on the page to go, the view offers no way there.
    expect(
        page.locator(".lf-fp-aux button:enabled[aria-label='Show on page']")
    ).to_have_count(0)


def test_a_passage_among_padded_emoji_confirms_its_neighbours(browser, serve):
    """A stored context is counted in code points; the comparison counts code units; and an
    astral character is two of the second for one of the first. Ask the page for the first
    number and the window comes up short of what was written down — and short is fatal,
    because a passage confirms its neighbours in full or not at all. The anchor would fall
    back to naming the first copy on that page for good, silently. No shipped example holds
    an astral character, so only a fixture can hold this."""
    page = open_page(browser, serve(ASTRAL_PAGE))
    chosen = page.evaluate_handle("""() => {
        const skip = '.lf-ui, script, style';
        const w = document.createTreeWalker(document.getElementById('astral'),
            NodeFilter.SHOW_TEXT,
            {acceptNode: n => n.parentElement?.closest(skip)
                ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT});
        const phrase = 'TARGET PHRASE';
        const hits = [];
        for (let n = w.nextNode(); n; n = w.nextNode()) {
            let i = n.data.indexOf(phrase);
            while (i !== -1) { hits.push({node: n, at: i}); i = n.data.indexOf(phrase, i + 1); }
        }
        if (hits.length !== 2) return `fixture holds ${hits.length} copies, wanted 2`;
        const h = hits[1];   // the copy among the emoji
        const want = document.createRange();
        want.setStart(h.node, h.at); want.setEnd(h.node, h.at + phrase.length);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        return want.cloneRange();
    }""")
    assert chosen.evaluate("range => range instanceof Range"), chosen.json_value()
    assert selected_comment_marks_chosen_start(page, chosen), (
        "the emoji copy was picked, but the comment mark went elsewhere"
    )


@pytest.mark.parametrize(
    "html", [EDGE_PAGE, TAIL_PAGE], ids=["closes-its-section", "ends-the-document"]
)
def test_a_repeated_passage_at_an_edge_anchors_where_it_was_picked(
    browser, serve, html
):
    """A passage closing its section used to store a suffix clipped at the section's
    edge — one character, a bar the identical copy above it also cleared, so the mark
    painted there while the user was still composing. The neighbours now come from
    the whole document and the section only filters where the search may land, so the
    closing copy is told apart by the words of the section after it.

    Where the document itself ends there is no second side to store, and an empty one is
    not an absent constraint: it says nothing followed the passage anywhere, which is true
    of exactly one occurrence. Refusing to read it that way left the same wrong mark."""
    page = open_page(browser, serve(html))
    chosen = page.evaluate_handle("""() => {
        const p = document.querySelectorAll('#edge p')[1];
        // Through the full stop, so that with the section below removed the passage is the
        // last thing the document says and its stored suffix comes out empty.
        const phrase = 'the run is retried until it lands.';
        const at = p.firstChild.data.indexOf(phrase);
        if (at === -1) return 'phrase missing';
        const want = document.createRange();
        want.setStart(p.firstChild, at); want.setEnd(p.firstChild, at + phrase.length);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        return want.cloneRange();
    }""")
    assert chosen.evaluate("range => range instanceof Range"), chosen.json_value()
    assert selected_comment_marks_chosen_start(page, chosen), (
        "the closing copy was picked, but the comment mark went elsewhere"
    )


def test_a_passage_longer_than_the_pattern_is_anchored_whole(browser, serve):
    """A quote is the passage, so what is stored is what the page marks and what the
    comment is on. It used to be cut at four hundred characters: a user who selected
    a paragraph got a comment on its opening and a highlight that shrank to match, on
    most of the paragraphs a leaf page holds, and nothing said so. Storing the
    whole of it is only affordable because the bound moved to the search's pattern,
    which is what could not take a long passage — so this drags one past that bound and
    asks the mark, the log and the panel the same question, on the second of two
    identical copies, which is also the case where the lead alone cannot answer it."""
    url = serve(TWO_COPIES_PAGE)
    page = open_page(browser, url)
    passage = page.locator("#second")
    picked = page.evaluate("() => document.querySelector('#second').textContent.length")
    assert picked > 400, "the fixture no longer outruns the pattern's own lead"

    # The whole paragraph, dragged: from its first glyph to its last.
    box = passage.bounding_box()
    select(
        page,
        (box["x"] + 1, box["y"] + 4),
        (box["x"] + box["width"] - 1, box["y"] + box["height"] - 4),
        steps=12,
    )
    expect(page.locator(".lf-fab-input")).to_be_visible()
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    expect(page.locator(".lf-composer")).to_be_visible()

    # The mark under the open composer is the selection, both ends of it — and on the
    # copy the user dragged, which only the stored neighbours can decide.
    on_the_selection = page.evaluate("""() => {
        const words = document.querySelector('#second').firstChild;
        const want = document.createRange();
        want.setStart(words, 0);
        want.setEnd(words, words.data.length);
        const painted = [...(CSS.highlights.get('lf-pending') ?? [])];
        if (!painted.length) return 'no mark';
        return [
          painted[0].compareBoundaryPoints(Range.START_TO_START, want) === 0,
          painted.at(-1).compareBoundaryPoints(Range.END_TO_END, want) === 0,
          painted.map((r) => r.toString()).join('').length,
        ];
    }""")
    assert on_the_selection == [True, True, picked], (
        f"the mark is not the passage that was dragged ({on_the_selection}, "
        f"wanted [True, True, {picked}])"
    )

    # And the anchor that posts says the same thing, since the mark is drawn from it.
    write(page.locator(".lf-composer leaf-text"), "The whole of it.")
    with sending(page, "the comment on the dragged passage"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect_open_threads(page, 1)
    assert stranded_quotes(page) == []
    anchor = [
        e["anchor"] for e in events_model.read_events(serve.page_dir) if e.get("anchor")
    ][-1]
    assert len(anchor["quote"]) == picked, (
        f"the log holds {len(anchor['quote'])} characters of a {picked}-character "
        "passage"
    )
    assert anchor["prefix"].endswith("this other line."), (
        f"the neighbour naming which copy was picked is {anchor['prefix']!r}"
    )


def test_a_selection_of_the_whole_page_still_finds_its_passage(browser, serve):
    """Select-all and comment. The quote is then the page, which is past what a search
    built from the whole of one can compile at all — and a throw there is not a missing
    mark but every mark, since one pass draws them. The bound is the pattern's, so the
    lead finds the candidates and the rest of the quote is walked from each; what this
    asks is that the passage is still found, on the pass that runs after the send as
    much as on the one under the composer."""
    url = serve(CEILING_PAGE)
    page = open_page(browser, url)
    prose = page.evaluate("() => document.querySelector('main').textContent.length")
    assert prose > 12000, f"the fixture holds {prose} characters, under the ceiling"

    page.keyboard.press("ControlOrMeta+a")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    expect(page.locator(".lf-composer")).to_be_visible()
    painted = page.evaluate(
        "() => [...(CSS.highlights.get('lf-pending') ?? [])]"
        ".map((r) => r.toString()).join('').length"
    )
    assert painted > 12000, f"the mark under the composer covers {painted} characters"

    write(page.locator(".lf-composer leaf-text"), "All of it.")
    with sending(page, "the comment on the whole page"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect_open_threads(page, 1)
    # The posted anchor resolves on the ordinary pass too, which is the one that would
    # have thrown: a detached quote here is the search having failed to find the page
    # inside the page.
    assert stranded_quotes(page) == []


def test_select_all_on_a_page_with_a_diff_leaves_the_page_responsive(browser, serve):
    """Select-all on a page holding an x-shadow widget. The composed selection spans
    <html>, past the words the page reads, and the capture once grew its neighbourhood
    forever from a position that reading lacked, pinning the tab. The press is bounded so
    that regression fails here rather than hanging the run."""
    page = open_page(browser, serve(TWICE_PAGE))
    page.locator("body").press("ControlOrMeta+a")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_contain_text(
        re.compile("Something else entirely.*request.headers", re.DOTALL)
    )


def test_one_neighbour_is_not_enough_to_identify_a_revised_comment(browser, serve):
    """Context may place a comment only where both of a passage's neighbours are still
    there. A passage at the edge of its section has just one, and one is a bar another copy
    clears — so a revision that rewrites the commented copy's only neighbour would hand the
    comment to a copy it was never made on, silently, a version after anyone was looking.
    The thread keeps its section until the agent chooses its replacement passage."""
    url = serve(THIN_V1)
    page = open_page(browser, live_url(url))
    selected = page.evaluate("""() => {
            const p = document.querySelectorAll('#thin p')[0];
            const phrase = 'The version stamp never lands';
            const at = p.firstChild.data.indexOf(phrase);
            const want = document.createRange();
            want.setStart(p.firstChild, at);
            want.setEnd(p.firstChild, at + phrase.length);
            const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
            document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
            return true;
        }""")
    assert selected is True, f"couldn't select the passage ({selected})"
    open_selected_comment(page)
    write(page.locator(".lf-composer leaf-text"), "does this hold?")
    with sending(page, "the comment on the passage with one neighbour"):
        page.locator(".lf-composer button.lf-compose-submit").click()
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    d = serve.page_dir
    stamp_page(d, THIN_V2, "revised")
    wait_for_revision(page, 2)
    assert stranded_quotes(page) == []
    assert page.evaluate("() => CSS.highlights.get('lf-mark')?.size ?? 0") == 0
    [transition] = [
        event for event in events_model.read_events(d) if event["kind"] == "reanchor"
    ]
    assert transition["anchor"] == {"section": "thin"}


def test_a_change_opens_what_it_replaced_in_a_card_over_it(browser, serve):
    """The other half of a comparison is what each change replaced, on request.

    The Change margin entry is a disclosure per change, a hunk of the block diff, which
    opens one card over the change: the words a block that kept its id lost, struck, and
    the words it gained, tinted, then the paragraph the change added, inserted whole.
    Rewritten sentences stay whole; a local edit is refined to its words. The card stands
    in the chrome, so the page under it does not move, the existing comments stay
    attached and selection still reads the current version alone.

    The authored pair supplies the contrasts: one rewritten paragraph with a surviving
    and a replaced sentence, and the new paragraph after it, which make one change; a
    rewritten heading and lede, another; and one new list item, the third."""
    example = named_source("log-retention")
    page = open_page(browser, serve(example))
    compare_with(page, 1)
    expect(page.locator("main .lf-ins-block")).to_have_count(5)

    # Nothing stands open until a user asks: the marks are the whole first reading.
    card = page.locator("#lf-change-card")
    expect(card).to_have_count(0)
    marks = "() => CSS.highlights.get('lf-mark')?.size ?? 0"
    assert page.evaluate(marks) == 2
    rewritten = page.locator(
        '[data-lf-margin-for="ret-cost-body"] [data-lf-kinds~="change"]'
    )
    expect(rewritten).to_have_attribute("aria-expanded", "false")
    expect(rewritten).to_have_attribute("aria-controls", "lf-change-card")
    # A disclosure says what it holds: what the change did, in blocks.
    assert preview_parts(rewritten)[1:2] == ["1 paragraph edited, 1 added since v1"]

    # Page Map carries the same account on each change's row, with the versions its
    # card compares, and both remain searchable away from the passage.
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    sheet = page.get_by_role("dialog", name="Page Map", exact=True)
    mapped = sheet.locator('[data-lf-map-item^="change:"]').filter(has_text="v1 → v2")
    expect(mapped).to_have_count(3)
    paragraph = mapped.filter(has_text="1 paragraph edited, 1 added · Two years")
    expect(paragraph).to_have_count(1)
    expect(paragraph.locator(".lf-page-map-action-context")).to_have_text("v1 → v2")
    expect(paragraph).to_have_attribute(
        "aria-label", re.compile(r"^Open change: .+, v1 → v2$")
    )
    page.keyboard.press("Escape")
    before = page.locator("#ret-cost-body").bounding_box()
    rewritten.click()

    # One card over the change; the page under it holds still.
    expect(card).to_be_visible()
    expect(rewritten).to_have_attribute("aria-expanded", "true")
    assert page.locator("#ret-cost-body").bounding_box() == before
    expect(card.locator(".lf-change-card-head")).to_have_text(
        "1 paragraph edited, 1 added · v1 → v2"
    )
    struck = card.locator("del")
    expect(struck).to_have_count(1)
    expect(struck).to_contain_text("Both questions were answered")
    expect(struck).not_to_contain_text("Two years of incident write-ups")
    inserted = card.locator("ins")
    expect(inserted).to_have_count(2)
    expect(inserted.first).to_contain_text("Aggregates supplied the rate")
    expect(inserted.first).not_to_contain_text("Two years of incident write-ups")
    # The paragraph the revision added in the same change reads after it, inserted whole.
    expect(inserted.last).to_contain_text("Keep 5xx request logs for 120 days")
    expect(
        page.locator('[data-lf-margin-for="ret-cost-keep"] [data-lf-kinds~="change"]')
    ).to_have_count(0)
    expect_panel_says(page, "1 paragraph edited, 1 added since v1 · showing the change")

    # One card at a time: a list item's change takes its place.
    step = page.locator(
        '[data-lf-margin-for="ret-steps-carve"] [data-lf-kinds~="change"]'
    )
    step.click()
    expect(card.locator(".lf-change-card-head")).to_have_text("1 item added · v1 → v2")
    expect(rewritten).to_have_attribute("aria-expanded", "false")
    expect(step).to_have_attribute("aria-expanded", "true")

    # The card is the runtime's own (.lf-ui), so the page's reading does not move under
    # it: both threads keep the passages they quote.
    assert stranded_quotes(page) == []
    assert page.evaluate(marks) == 2

    # Escape closes it, and stopping the comparison takes the marks.
    page.keyboard.press("Escape")
    expect(card).to_have_count(0)
    expect(step).to_have_attribute("aria-expanded", "false")
    compare_with(page, 1)
    expect(page.locator("main .lf-ins-block")).to_have_count(0)


def test_a_change_card_reads_across_elements_and_past_astral_text(
    browser, serve, subtests
):
    """A passage crossing element boundaries keeps one text reading, and astral text
    before an edit cannot shift its insertion and deletion runs."""
    first = leaf_page(
        "Version passages",
        """
        <h1>Review</h1>
        <aside id='note'>Careful<b>!</b> The old wording stood here.</aside>
        <p id='between'>An unchanged line keeps these two changes apart.</p>
        <p id='wording'>Weather 🌧: the old wording stood here.</p>
        <p id='tail'>Weather 🌧: this line keeps a trailing phrase.</p>
        """,
    )
    second = first.replace("old wording stood", "new wording stands").replace(
        " keeps a trailing phrase", ""
    )
    page = open_page(browser, live_url(serve(first)))
    stamp_page(serve.page_dir, second, "revise the note and the forecast")
    wait_for_revision(page, 2)
    compare_with(page, 1)
    card = page.locator("#lf-change-card")

    with subtests.test(case="across element boundaries"):
        change = page.locator('[data-lf-margin-for="note"] [data-lf-kinds~="change"]')
        change.click()
        expect(change).to_have_attribute("aria-expanded", "true")
        expect(card.locator("del")).to_have_count(2)
        assert card.locator("del").all_inner_texts() == ["old", "stood"]
        assert card.locator("ins").all_inner_texts() == ["new", "stands"]

    with subtests.test(case="past astral text"):
        wording = page.locator(
            '[data-lf-margin-for="wording"] [data-lf-kinds~="change"]'
        )
        wording.click()
        expect(wording).to_have_attribute("aria-expanded", "true")
        # The adjacent edits share one change, and its card holds both.
        expect(card.locator("del")).to_have_count(3)
        assert [text.strip() for text in card.locator("del").all_inner_texts()] == [
            "old",
            "stood",
            "keeps a trailing phrase",
        ]
        assert card.locator("ins").all_inner_texts() == ["new", "stands"]


def test_a_state_only_version_change_does_not_offer_an_empty_card(browser, serve):
    """A moved block remains marked without promising a card of words."""
    first = leaf_page(
        "Moved card",
        """
        <h1>Board</h1>
        <lf-board id='board'>
          <lf-column id='left' label='Left'>
            <lf-card id='card'><strong>Review</strong> Keep these words.</lf-card>
          </lf-column>
          <lf-column id='right' label='Right'></lf-column>
        </lf-board>
        """,
    )
    second = first.replace(
        "<lf-card id='card'><strong>Review</strong> Keep these words.</lf-card>\n"
        "          </lf-column>\n"
        "          <lf-column id='right' label='Right'></lf-column>",
        "</lf-column>\n"
        "          <lf-column id='right' label='Right'>\n"
        "            <lf-card id='card'><strong>Review</strong> Keep these words.</lf-card>\n"
        "          </lf-column>",
    )
    page = open_page(browser, live_url(serve(first)))
    d = serve.page_dir
    stamp_page(d, second, "move the card")
    wait_for_revision(page, 2)

    compare_with(page, 1)
    expect(page.locator("#card")).to_have_class(re.compile(r"\blf-ins-block\b"))
    change = page.locator('[data-lf-margin-for="card"] [data-lf-kinds~="change"]')
    expect(change).not_to_have_attribute("aria-expanded", re.compile(".*"))
    expect(change).not_to_have_attribute("aria-controls", re.compile(".*"))
    change.click()
    expect(page.locator("#lf-change-card")).to_have_count(0)
    expect_panel_says(page, "1 card changed since v1")


def test_version_comparison_distinguishes_authored_graphics_from_button_icons(
    browser, serve
):
    """Opaque graphics use the same authoredness boundary as compared prose."""
    first = leaf_page(
        "Graphics in a revision",
        """
        <h1>Route review</h1>
        <p id="route">The route crosses the park.</p>
        <lf-suggestion id="departure">
          <lf-old>Leave at nine.</lf-old><lf-new>Leave at ten.</lf-new>
        </lf-suggestion>
        <svg id="old-map" viewBox="0 0 20 20" width="40" height="40">
          <path d="M2 2L18 18" />
        </svg>
        <lf-decoration id="decoration"></lf-decoration>
        """,
    )
    second = first.replace("crosses the park", "follows the river").replace(
        "</main>",
        """<svg id="new-map" viewBox="0 0 20 20" width="40" height="40">
          <circle cx="10" cy="10" r="6" />
        </svg></main>""",
    )
    url = serve(
        first,
        layer_registry={
            "lf-decoration": {
                "description": "Generated prose and a graphic with its own marker.",
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
                "additionalProperties": False,
                "x-content": "markup",
                "x-example": '<lf-decoration id="decoration"></lf-decoration>',
            }
        },
        layer_widgets={
            "lf-decoration.js": """
                import {once} from '/runtime/widget-api.js';
                customElements.define('lf-decoration', class extends HTMLElement {
                  connectedCallback() {
                    if (!once(this)) return;
                    this.innerHTML = `
                      <p data-lf-gen>Generated caption.</p>
                      <svg id="decoration-icon" data-lf-gen viewBox="0 0 20 20"
                           width="40" height="40"><path d="M2 18L18 2" /></svg>`;
                  }
                });
            """
        },
    )
    _publish(serve.page_dir, 2, second, "New route and map")
    page = open_page(browser, url.replace("v1.html", "v2.html"))
    expect(page.locator("#decoration-icon[data-lf-gen]")).to_have_count(1)

    compare_with(page, 1)
    expect(page.locator("#route")).to_have_class(re.compile(r"\blf-ins-block\b"))
    assert page.eval_on_selector_all(
        ".lf-ins-block", "els => els.map(e => e.id).sort()"
    ) == ["new-map", "route"]


def clearance_page(browser, serve, rail=True):
    """One commented passage between spacers, and a way to stand its bottom edge
    `offset` pixels below the top of the panel's scroll padding at the foot. Without
    `rail`, the page gives its right margin to its own content (`data-rail="none"`)."""
    source = leaf_page(
        "Bottom clearance",
        """
<h1>Anchor travel</h1>
<div style="height: 900px" aria-hidden="true"></div>
<p id="destination">The passage remains readable above the bottom toolbar.</p>
<div style="height: 900px" aria-hidden="true"></div>
""",
    )
    if not rail:
        source = source.replace("<body>", '<body data-rail="none">')
    page = open_page(
        browser,
        serve(source, anchored=(("destination", "The passage remains readable"),)),
    )
    resized(page, 1000, 700)

    def place_bottom(offset):
        return page.evaluate(
            """offset => {
              const scroller = document.scrollingElement;
              const destination = document.getElementById('destination');
              const clear = parseFloat(getComputedStyle(scroller).scrollPaddingBottom);
              const before = destination.getBoundingClientRect();
              scroller.scrollBy(0, before.bottom - (innerHeight - clear + offset));
              const after = destination.getBoundingClientRect();
              return {clear, bottom: after.bottom, viewport: innerHeight,
                scroll: scroller.scrollTop};
            }""",
            offset,
        )

    return page, place_bottom


def test_thread_travel_keeps_its_passage_above_the_bottom_reading_clearance(
    browser, serve
):
    """Anchor travel treats the panel's scroll padding at the foot as covered space.

    A passage can be geometrically inside the viewport while its last line is under the
    panel. The control places it just above that band first, proving travel leaves
    a readable destination alone, then inside the band, where the same public thread walk
    must move it back into the usable reading area.
    """
    page, place_bottom = clearance_page(browser, serve)
    destination = page.locator("#destination")

    clear = place_bottom(-4)
    assert clear["clear"] > 0
    page.keyboard.press("t")
    expect(page.locator(".lf-page-thread")).to_be_focused()
    assert page.evaluate("() => document.scrollingElement.scrollTop") == pytest.approx(
        clear["scroll"], abs=1
    )

    covered = place_bottom(clear["clear"] / 2)
    assert covered["bottom"] <= covered["viewport"]
    assert covered["bottom"] > covered["viewport"] - covered["clear"]
    page.keyboard.press("t")
    page.wait_for_function(
        """() => {
          const clear = parseFloat(getComputedStyle(document.scrollingElement)
            .scrollPaddingBottom);
          return document.getElementById('destination').getBoundingClientRect().bottom
            <= innerHeight - clear + .5;
        }"""
    )
    assert page.evaluate("() => document.scrollingElement.scrollTop") != pytest.approx(
        covered["scroll"], abs=1
    )
    expect(destination).to_be_in_viewport()


def test_a_press_on_a_passage_opens_its_thread_where_it_stands(browser, serve):
    """The walk above travels for this geometry; a press on the same words does not,
    because the user's hand is already on them and the card fits beside them."""
    page, place_bottom = clearance_page(browser, serve)
    # 10px into the band keeps the line's middle, where the press lands, off the panel.
    covered = place_bottom(10)
    page.mouse.click(*mark_point(page, "lf-mark"))
    expect(page.locator(".lf-page-thread leaf-text")).to_be_focused()
    # A trip waits on the thread refresh before it decides to move, and that same
    # refresh is what writes this card's placement (`scrollToThread`, anchor-travel.js).
    # So the card standing where the pass put it is the edge a travel would have been
    # asked for behind; read the page's own position from there rather than from a hold
    # long enough to have covered the wait.
    expect(page.locator(".lf-margin-preview")).to_be_in_viewport(ratio=1)
    scroll_settled(page)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == pytest.approx(
        covered["scroll"], abs=1
    )


def test_a_pinned_row_opens_its_card_clear_of_the_passage(browser, serve):
    """On a page that keeps no rail, the thread's margin row stands as a pin on its
    block on a desktop's window too, and a card opens from it there. The card stands
    under or over the block, never over the very words the user pressed, and leaves
    once the passage does."""
    page, place_bottom = clearance_page(browser, serve, rail=False)
    resized(page, 1000, 800)
    expect(page.locator('[data-lf-margin-for="destination"]')).to_have_attribute(
        "data-lf-place", "pin"
    )
    place_bottom(-560)
    page.mouse.click(*mark_point(page, "lf-mark"))
    expect(page.locator(".lf-margin-preview .lf-page-thread leaf-text")).to_be_focused()
    boxes = page.evaluate(
        """() => {
          const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
          const words = [...CSS.highlights.get('lf-mark')][0].getBoundingClientRect();
          return {card: [card.top, card.bottom], words: [words.top, words.bottom]};
        }"""
    )
    card, words = boxes["card"], boxes["words"]
    assert card[1] <= words[0] or card[0] >= words[1], (
        f"the card spans {card[0]:.0f}\u2013{card[1]:.0f} over the pressed words at "
        f"{words[0]:.0f}\u2013{words[1]:.0f}"
    )
    # The same box decides where the card goes once its subject leaves: it leaves with
    # the pin, and so the passage.
    page.evaluate("() => document.scrollingElement.scrollBy(0, 900)")
    rendered(page)
    assert page.locator(".lf-margin-preview").evaluate(
        "card => card.getBoundingClientRect().bottom <= 0"
    )


def test_a_version_published_under_an_open_menu_reaches_it(browser, serve):
    """A version published while the Versions list stands open joins it in place, and
    the user stays on the row they stood on."""
    url = serve(INLINE_PAGE)
    _publish(serve.page_dir, 2, INLINE_PAGE, "two")
    page = open_page(browser, url, pin=True)
    rows = panel_menu(page, "versions").locator(".lf-fp-version")
    expect(rows).to_have_count(2)
    focused_row = rows.first.locator(".lf-fp-item")
    focused_row.focus()
    focused_row.evaluate("row => window.__lfFocusedVersionRow = row")
    _publish(serve.page_dir, 3, INLINE_PAGE, "three")
    told(page)  # the poll that carries it has been and gone
    expect(rows).to_have_count(3)
    expect(rows.first).to_contain_text("v3")
    assert page.evaluate(
        "() => document.activeElement === window.__lfFocusedVersionRow"
    )


def test_pending_comparison_moves_with_a_live_revision(browser, serve):
    """A live activation cancels the old request and restores its selected base."""
    v2 = INLINE_PAGE.replace("A neighbouring block", "A neighbouring passage")
    v3 = v2.replace("The setup is in the runbook", "The setup is in the handbook")
    url = serve(INLINE_PAGE)
    _publish(serve.page_dir, 2, v2, "reworded the neighbour")
    page = open_page(browser, live_url(url))
    wait_for_revision(page, 2)

    held = []
    requests = []
    view_request = re.compile(r"/api/view\?")

    def hold_first_view(route):
        requests.append(route.request.url)
        if not held:
            held.append(route)
        else:
            route.continue_()

    page.route(view_request, hold_first_view)
    released = False
    try:
        compare_with(page, 1)
        holding(page, held, 1, "the comparison view")

        _publish(serve.page_dir, 3, v3, "reworded the compound")
        wait_for_revision(page, 3)
        expect(page.locator("#compound")).to_have_class(re.compile(r"\blf-ins-block\b"))
        expect(page.locator(".lf-ins-block")).to_have_count(2)
        assert len(requests) >= 2, "the selected base was not restored after activation"

        # The canceled request can finish last without repainting the prior document.
        with page.expect_response(held[0].request.url):
            held[0].continue_()
        released = True
        rendered(page)
        expect(page.locator(".lf-ins-block")).to_have_count(2)
    finally:
        if held and not released:
            held[0].continue_()
        page.unroute(view_request)


def test_a_failed_comparison_clears_its_pending_choice_and_can_retry(browser, serve):
    """A failed replacement leaves no old marks and releases its selected base."""
    v2 = INLINE_PAGE.replace("A neighbouring block", "A neighbouring passage")
    v3 = v2.replace("The setup is in the runbook", "The setup is in the handbook")
    url = serve(INLINE_PAGE)
    _publish(serve.page_dir, 2, v2, "reworded the neighbour")
    _publish(serve.page_dir, 3, v3, "reworded the compound")
    page = open_page(browser, url.replace("v1.html", "v3.html"))
    compare_with(page, 1)
    expect(page.locator(".lf-ins-block")).to_have_count(2)

    held = []
    view_request = re.compile(r"/api/view\?")
    page.route(view_request, lambda route: held.append(route))
    compare_with(page, 2)
    holding(page, held, 1, "the replacement comparison")
    expect(page.locator(".lf-ins-block")).to_have_count(0)
    held[0].fulfill(status=500, json={"error": "comparison unavailable"})
    expect_panel_says(page, "Couldn't load v2")
    consume_browser_errors(page, http_error_console(500))
    page.unroute(view_request)

    menu = panel_menu(page, "versions")
    compare = menu.get_by_role("button", name="Compare with v2")
    expect(compare).to_have_attribute("aria-pressed", "false")
    # A pending choice left behind would treat this press as cancellation.
    compare.click()
    expect(page.locator(".lf-ins-block")).to_have_count(1)
    expect(page.locator("#compound")).to_have_class(re.compile(r"\blf-ins-block\b"))


def test_the_menu_compares_with_any_version_older_than_this_one(browser, serve):
    """A page that ships a version whenever the work moves leaves its user behind by
    more than one, and "what changed since the previous version" is then the wrong
    question: what they want marked is everything since they last looked. The base was
    the previous version for exactly as long as it was a control's own label — one
    button can name one version — so the menu is where it stops being one, and every row
    older than this one offers itself.

    The rest is what the user can tell afterwards: reopening says which comparison
    stands, and its Compare pressed again is the way off."""
    v2 = INLINE_PAGE.replace("A neighbouring block", "A neighbouring passage")
    v3 = v2.replace("The setup is in the runbook", "The setup is in the handbook")
    url = serve(INLINE_PAGE)
    _publish(serve.page_dir, 2, v2, "reworded the neighbour")
    _publish(serve.page_dir, 3, v3, "reworded the compound")
    page = open_page(browser, url.replace("v1.html", "v3.html"))

    # The previous version: the one change this version made.
    compare_with(page, 2)
    expect(page.locator(".lf-ins-block")).to_have_count(1)
    expect(page.locator("#compound")).to_have_class(re.compile(r"\blf-ins-block\b"))

    # Two versions back, which no single-label control could have offered: both.
    compare_with(page, 1)
    expect(page.locator(".lf-ins-block")).to_have_count(2)
    expect(page.locator("#p2")).to_have_class(re.compile(r"\blf-ins-block\b"))

    # Reopened, the list says which comparison stands.
    menu = panel_menu(page, "versions")
    expect(menu.get_by_role("button", name="Compare with v1")).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(menu.get_by_role("button", name="Compare with v2")).to_have_attribute(
        "aria-pressed", "false"
    )

    # Pressing the current base again is the way off, and clears the marks.
    menu.get_by_role("button", name="Compare with v1").click()
    expect(page.locator(".lf-ins-block")).to_have_count(0)

    # Compare is reachable by keyboard too: the walk stands on it after its version.
    menu = panel_menu(page, "versions")
    menu.locator(".lf-fp-version").filter(has_text="v1").locator(".lf-fp-item").focus()
    page.keyboard.press("ArrowDown")
    compare = menu.get_by_role("button", name="Compare with v1")
    expect(compare).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-ins-block")).to_have_count(2)


def test_a_diff_anchors_to_the_side_it_was_read_on(browser, serve):
    """The case this exists for, and the one a section cannot narrow: a diff carries the
    same line added and removed under a single id, so the user commenting on the fix
    had their comment marked against the bug — stored that way, and shown to Claude that
    way in the next round.

    The passage is picked out of the rendered widget, where syntax colour has cut the
    line into spans: `return` is a keyword and ` request.path` is the text after it, so
    the selection starts in one node and ends in another. That is the ordinary shape of a
    passage in a coloured block, and the anchor knows nothing about it — a span is no text
    block, so both readings still collapse to the same run of characters."""
    page = open_page(browser, serve(TWICE_PAGE))
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    chosen = page.evaluate_handle("""() => {
        const skip = '.lf-ui, script, style';
        // Rooted at the shadow root: lf-diff renders in one (x-shadow), so the lines
        // this drags across are in the composed tree and not under the host element.
        const w = document.createTreeWalker(document.getElementById('patch').shadowRoot,
            NodeFilter.SHOW_TEXT,
            {acceptNode: n => n.parentElement?.closest(skip)
                ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT});
        // One flat run over the widget's text nodes, and where each node started in it,
        // so a phrase is found whether or not a token boundary falls inside it.
        const nodes = [], starts = [];
        let flat = '';
        for (let n = w.nextNode(); n; n = w.nextNode()) {
            starts.push(flat.length); nodes.push(n); flat += n.data;
        }
        const phrase = 'return request.path';
        const hits = [];
        for (let i = flat.indexOf(phrase); i !== -1; i = flat.indexOf(phrase, i + 1)) hits.push(i);
        if (hits.length < 2) return `only ${hits.length} occurrence(s) — fixture broken`;
        const at = (offset) => {
            const i = starts.findLastIndex((s) => s <= offset);
            return [nodes[i], offset - starts[i]];
        };
        const start = hits.at(-1);   // the added line: the later of the pair
        const want = document.createRange();
        want.setStart(...at(start)); want.setEnd(...at(start + phrase.length));
        if (want.startContainer === want.endContainer)
            return 'the phrase sat in one node — colour never split it, so this proves nothing';
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        return want.cloneRange();
    }""")
    assert chosen.evaluate("range => range instanceof Range"), chosen.json_value()
    assert selected_comment_marks_chosen_start(page, chosen), (
        "the added line was picked, but the comment mark went elsewhere"
    )


def test_a_manifest_diff_can_comment_on_one_unloaded_file(browser, serve):
    """A file comment starts inline without fetching or opening its patch."""
    authored = leaf_page(
        "file comment",
        '<h1 id="title">Review</h1><lf-diff id="patch" source="review-patch" '
        "collapsed></lf-diff>",
    )
    url = serve(authored)
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        {
            "files": [
                {
                    "path": "app.py",
                    "patch": """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-old = True
+new = True
""",
                }
            ]
        },
    )
    revision = source_revision(serve.page_dir, "review-patch")
    page = open_page(browser, url)
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )

    details = page.locator("lf-diff details").first
    file_header = details.locator("summary")
    expect(details).not_to_have_attribute("open", "")
    expect(page.locator("lf-diff [data-line-type]")).to_have_count(0)
    expect(file_header).to_have_attribute("data-lf-datum", '["app.py","file"]')
    expect(file_header).to_have_attribute("data-lf-datum-label", "app.py · file")

    page.get_by_role("button", name="Comment on app.py", exact=True).click()
    expect(details).not_to_have_attribute("open", "")
    expect(page.locator("lf-diff [data-line-type]")).to_have_count(0)
    outlet = page.locator("lf-diff .lf-diff-file-thread-outlet")
    expect(outlet).to_have_count(1)
    expect(outlet.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator("#lf-composer-quote")).to_contain_text("§ app.py · file")
    write(page.locator(".lf-fab-input"), "Review this file as a whole.")
    with sending(page, "the comment on the unloaded file"):
        page.keyboard.press("ControlOrMeta+Enter")

    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [comment["anchor"] for comment in comments] == [
        {
            "section": "patch",
            "datum": '["app.py","file"]',
            "source": "review-patch",
            "source_revision": revision,
        }
    ]
    expect(outlet.locator(".lf-page-thread")).to_contain_text(
        "Review this file as a whole."
    )
    expect(outlet.locator(".lf-page-thread")).to_be_focused()
    expect(outlet.locator(".lf-page-thread leaf-text")).not_to_be_focused()
    expect(details).not_to_have_attribute("open", "")
    expect(page.locator("lf-diff [data-line-type]")).to_have_count(0)
    expect(thread_head(page, comments[0]["id"])).to_have_text("§ app.py · file")
    expect(page.locator(PANEL_THREAD)).to_contain_text("Review this file as a whole.")

    # A thread on a line of the file still unloaded is named as its drawn row would be,
    # not by the widget holding it.
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "Check the new line.",
            "anchor": {
                "section": "patch",
                "datum": '["app.py","new",1]',
                "source": "review-patch",
                "source_revision": revision,
            },
        },
    )
    told(page)
    expect_open_threads(page, 2)
    expect(page.locator("lf-diff [data-line-type]")).to_have_count(0)
    quotes = [
        thread_head(page, thread).inner_text() for thread in comment_ids(serve.page_dir)
    ]
    assert sorted(" ".join(quote.split()) for quote in quotes) == [
        "§ app.py · file",
        "§ app.py · new line 1",
    ]


def test_a_drag_across_a_written_diff_line_is_the_passage_c_comments_on(browser, serve):
    """A diff written into the page rather than bound to data, and a real drag rather
    than a range handed to the selection: Chrome keeps the document's selection in the
    light DOM, so a drag wholly inside the diff's shadow tree reports both its ends at
    the host, and `isCollapsed` says nothing is selected while the words are painted
    selected. Read that way, no Comment field rose over the drag and `c` opened a comment
    on the page with no passage at all. The passage is the composed range the user drew,
    so the comment carries those words at the diff line's exact coordinate."""
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        "@@ -1,2 +1,2 @@\n def route(request):\n"
        '-    return f"legacy:{request.token.id}"\n'
        '+    return f"tok:{request.token.id}"\n'
    )
    url = serve(
        leaf_page(
            "written diff",
            '<h1 id="title">Review</h1>'
            f'<lf-diff id="patch"><pre>{escape(patch)}</pre></lf-diff>',
        )
    )
    page = open_page(browser, url)
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    line = page.locator('lf-diff [data-line][data-line-type="change-addition"]')
    # Where the phrase's first and last glyphs stand, so the drag starts and ends on them.
    ends = line.evaluate(
        """line => {
          const walker = document.createTreeWalker(line, NodeFilter.SHOW_TEXT);
          const nodes = [], starts = [];
          let flat = '';
          for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            starts.push(flat.length); nodes.push(node); flat += node.data;
          }
          const glyph = offset => {
            const index = starts.findLastIndex(value => value <= offset);
            const range = document.createRange();
            range.setStart(nodes[index], offset - starts[index]);
            range.setEnd(nodes[index], offset - starts[index] + 1);
            return range.getBoundingClientRect();
          };
          const phrase = 'request.token.id';
          const start = flat.indexOf(phrase);
          const first = glyph(start), last = glyph(start + phrase.length - 1);
          return { x0: first.left + 1, x1: last.right - 1,
                   y: (first.top + first.bottom) / 2 };
        }"""
    )
    page.mouse.move(ends["x0"], ends["y"])
    page.mouse.down()
    page.mouse.move(ends["x1"], ends["y"], steps=6)
    page.mouse.up()
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.keyboard.press("c")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator("#lf-composer-quote")).to_contain_text("“request.token.id”")
    write(page.locator(".lf-fab-input"), "Review this expression.")
    with sending(page, "the comment on the dragged expression"):
        page.keyboard.press("ControlOrMeta+Enter")
    [comment] = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert comment["anchor"]["section"] == "patch", comment
    assert comment["anchor"]["quote"] == "request.token.id", comment
    assert comment["anchor"]["datum"] == '["app.py","new",2]', comment


@pytest.mark.parametrize("arrived", ["", "#title"], ids=["plain", "fragment"])
def test_back_returns_from_a_thread_a_widget_surface_holds(browser, serve, arrived):
    """A thread the diff seats is a trip like any other: Back returns to where the
    user was reading, although the surface scrolls itself into view as it takes
    focus. The entry Back returns to may carry the fragment the page was opened at,
    and Back still returns to the reading, not to the element the fragment names."""
    filler = "".join(f"<p>Filler paragraph {n}.</p>" for n in range(120))
    url = serve(
        leaf_page(
            "Back from a diff thread",
            '<h1 id="title">Review</h1><lf-diff id="patch" source="review-patch">'
            f"</lf-diff><section id=far>{filler}</section>",
        )
    )
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-return "old"
+return "new"
""",
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
                "data_revision": 1,
            },
        },
    )["id"]
    page = open_page(browser, url + arrived)
    page.evaluate("document.scrollingElement.scrollTo({top: 1e6, behavior: 'instant'})")
    reading = page.evaluate("document.scrollingElement.scrollTop")
    assert reading > 2000
    entries = page.evaluate("history.length")

    page.keyboard.press("t")
    expect(
        page.locator(f'lf-diff .lf-page-thread[data-lf-thread="{root}"]')
    ).to_be_focused()
    # Card focus precedes the smooth scroll; observe arrival before settling it.
    expect(
        page.locator(f'lf-diff .lf-page-thread[data-lf-thread="{root}"]')
    ).to_be_in_viewport()
    scroll_settled(page)
    assert page.evaluate("document.scrollingElement.scrollTop") < reading - 1000
    assert page.evaluate("history.length") == entries + 1

    page.go_back()
    page.wait_for_function(
        "top => Math.abs(document.scrollingElement.scrollTop - top) <= 2", arg=reading
    )


def test_a_datum_comment_reveals_its_shadow_host_and_outer_tab(browser, serve):
    """Comment travel crosses the composed tree before asking containers to reveal.

    The datum itself lives in lf-diff's shadow root while the widget lives in an
    inactive authored tab. Opening only ancestors inside the root leaves the target
    without geometry; the reveal walk must cross through the host to reach lf-tab.
    """
    authored = leaf_page(
        "shadow datum reveal",
        """
<h1 id="title">Review</h1>
<lf-tabs id="views">
  <lf-tab id="overview" label="Overview"><p>Start here.</p></lf-tab>
  <lf-tab id="patch-tab" label="Patch">
    <lf-diff id="patch" source="review-patch"></lf-diff>
  </lf-tab>
</lf-tabs>
""",
    )
    url = serve(authored)
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-return "old"
+return "new"
""",
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Review the new value.",
            "anchor": {"section": "patch", "datum": '["app.py","new",1]'},
        },
    )
    page = open_page(browser, url)
    patch_tab = page.locator("#patch-tab")
    expect(patch_tab).to_have_attribute("hidden", re.compile(".*"))
    quote = thread_head(page, comment_ids(serve.page_dir)[0])
    expect(quote).not_to_have_attribute("data-lf-detached", "")

    show_on_page(page)

    expect(patch_tab).not_to_have_attribute("hidden", re.compile(".*"))
    added = page.locator(
        "lf-diff [data-line-type='change-addition']"
        '[data-lf-datum=\'["app.py","new",1]\']'
    )
    expect(added).to_be_in_viewport()
    expect(added).to_have_class(re.compile(r"\blf-mark-here\b"))


# Two files in one manifest, each rendered only when it is opened.
TWO_FILE_MANIFEST = {
    "files": [
        {
            "path": "first.py",
            "patch": """diff --git a/first.py b/first.py
--- a/first.py
+++ b/first.py
@@ -1 +1 @@
-return "old first"
+return "new first"
""",
        },
        {
            "path": "second.py",
            "patch": """diff --git a/second.py b/second.py
--- a/second.py
+++ b/second.py
@@ -1 +1 @@
-return "old second"
+return "new second"
""",
        },
    ]
}

# Hold the second file's textual rendering. Its complete Git evidence is already
# checked before either closed row is shown.
HOLD_SECOND_FILE = """
          customElements.whenDefined('lf-diff').then(() => {
            const prototype = customElements.get('lf-diff').prototype;
            const prepare = prototype.prepareEntry;
            prototype.prepareEntry = async function(...args) {
              if (args[0].path === 'second.py' && !window.__leafReleaseSecond)
                await new Promise(resolve => { window.__leafReleaseSecond = resolve; });
              return prepare.apply(this, args);
            };
          });
"""


@pytest.mark.parametrize(
    ("activation", "superseded"),
    [("mouse", False), ("keyboard", False), ("mouse", True)],
)
def test_a_collapsed_diff_renders_only_opened_files_and_hydrates_comment_travel(
    browser, serve, activation, superseded
):
    """A collapsed manifest is the startup surface, not a hidden fully-rendered patch.

    All file evidence is checked first; opening one file renders only that file. An existing line thread on a
    different unopened file remains attached at its disclosure; pressing its quote
    renders that file before ordinary exact-line navigation resumes. The press is the
    thread's Show on page, in the panel.
    """
    authored = leaf_page(
        "collapsed diff",
        '<h1 id="title">Review</h1><lf-diff id="patch" source="review-patch" '
        "collapsed></lf-diff>",
    )
    url = serve(authored)
    data_model.cmd_data_set(
        serve.page_dir,
        "review-patch",
        TWO_FILE_MANIFEST,
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Review the second value.",
            "anchor": {"section": "patch", "datum": '["second.py","new",1]'},
        },
    )
    page = open_page(
        browser,
        url,
        init_script=HOLD_SECOND_FILE,
    )

    expect(page.locator("lf-diff details")).to_have_count(2)
    expect(page.locator("lf-diff [data-line]")).to_have_count(0)
    expect(page.locator("lf-diff .lf-diff-thread-outlet")).to_have_count(0)
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')).to_have_count(1)

    page.locator("lf-diff summary").first.click()
    expect(
        page.locator('lf-diff [data-lf-datum=\'["first.py","new",1]\']')
    ).to_have_count(1)
    expect(
        page.locator('lf-diff [data-lf-datum=\'["second.py","new",1]\']')
    ).to_have_count(0)

    if activation == "keyboard":
        resized(page, 400, 900)
    [thread] = comment_ids(serve.page_dir)
    quote = thread_head(page, thread)
    expect(quote).not_to_have_attribute("data-lf-detached", "")
    show_on_page(page, key=activation == "keyboard")
    page.wait_for_function("typeof window.__leafReleaseSecond === 'function'")
    search = page.locator("lf-diff .lf-diff-search input")
    if superseded:
        search.click()
        expect(search).to_be_focused()
    page.evaluate("window.__leafReleaseSecond()")
    second = page.locator('lf-diff [data-lf-datum=\'["second.py","new",1]\']')
    expect(second).to_be_in_viewport()
    expect(page.locator("lf-diff .lf-diff-thread-outlet")).to_have_count(1)
    reply = page.locator("lf-diff .lf-diff-thread-outlet leaf-text")
    # The travel lands the user in the thread beside its line.

    def landed():
        page.wait_for_function(
            """() => {
              const chain = [];
              for (let at = document.activeElement; at; at = at.shadowRoot?.activeElement)
                chain.push(at);
              return chain.some((node) =>
                node.closest?.('.lf-diff-thread-outlet .lf-page-thread'));
            }"""
        )

    if superseded:
        expect(search).to_be_focused()
        thread_head(page, thread)
        show_on_page(page)
    landed()
    expect(second).to_have_class(re.compile(r"\blf-mark-here\b"))
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')).to_have_count(0)

    # Closing an already-loaded file removes its outlet too. Both return gestures
    # must rebuild that outlet before transferring keyboard focus to its thread.
    details = page.locator("lf-diff .lf-diff-file > details").nth(1)
    details.evaluate("element => { element.open = false; }")
    expect(reply).to_have_count(0)
    thread_head(page, thread)
    show_on_page(page, key=True)
    landed()


def test_a_hunk_step_waiting_on_a_file_leaves_a_user_who_moved_on(browser, serve):
    """`]` into a file still loading lands only while the user is where they pressed it.

    The step opens the next file and waits for its textual rendering. A user who presses
    somewhere else in that wait has moved on, and the landing the step owed is dropped
    rather than dragging them back into the diff when the file arrives.
    """
    url = serve(
        leaf_page(
            "collapsed diff",
            '<h1 id="title">Review</h1><lf-diff id="patch" source="review-patch" '
            "collapsed></lf-diff>",
        )
    )
    data_model.cmd_data_set(serve.page_dir, "review-patch", TWO_FILE_MANIFEST)
    page = open_page(browser, url, init_script=HOLD_SECOND_FILE)
    page.locator("lf-diff summary").first.click()
    first = page.locator('lf-diff [data-lf-datum=\'["first.py","new",1]\']')
    expect(first).to_have_count(1)
    page.locator("lf-diff").evaluate("node => { node.tabIndex = -1; node.focus(); }")
    page.keyboard.press("]")
    expect_panel_says(page, "Hunk 1 of 1")

    page.keyboard.press("]")
    page.wait_for_function("typeof window.__leafReleaseSecond === 'function'")
    page.locator("#title").click()
    page.evaluate("window.__leafReleaseSecond()")
    expect(
        page.locator('lf-diff [data-lf-datum=\'["second.py","new",1]\']')
    ).to_have_count(1)
    page.evaluate(
        "() => new Promise(resolve => requestAnimationFrame(() =>"
        " requestAnimationFrame(resolve)))"
    )
    assert page.evaluate("() => document.activeElement === document.body"), (
        "the step landed in the file after the user had pressed elsewhere"
    )


def test_a_diff_tracks_each_write_of_its_source(browser, serve):
    """A source write is an identity, not its second-resolution modification time.

    Replacing a manifest inside the same second discards its prior files.
    """
    authored = leaf_page(
        "changing diff",
        '<h1 id="title">Review</h1><lf-diff id="patch" source="review-patch" '
        "collapsed></lf-diff>",
    )
    url = serve(authored)

    def manifest(path, old, new):
        return {
            "files": [
                {
                    "path": path,
                    "patch": f"""diff --git a/{path} b/{path}
--- a/{path}
+++ b/{path}
@@ -1 +1 @@
-return {old!r}
+return {new!r}
""",
                }
            ]
        }

    data_model.cmd_data_set(
        serve.page_dir, "review-patch", manifest("first.py", "old", "first")
    )
    page = open_page(browser, url)
    expect(page.locator("lf-diff summary")).to_contain_text("first.py")

    data_model.cmd_data_set(
        serve.page_dir, "review-patch", manifest("second.py", "old", "second")
    )
    told(page)
    summary = page.locator("lf-diff summary")
    expect(summary).to_contain_text("second.py")
    expect(summary).not_to_contain_text("first.py")
    summary.click()
    expect(
        page.locator('lf-diff [data-lf-datum=\'["second.py","new",1]\']')
    ).to_have_count(1)


def test_passage_at_either_shadow_host_edge_excludes_its_words(browser, serve):
    page = open_page(browser, serve(PANEL_PAGE))
    quotes = page.evaluate(
        """async () => {
          const {anchorForRange} = await window.__lfCheckApi();
          const paragraph = document.querySelector('#how-cap').firstChild;
          const diff = document.querySelector('#how-patch');
          const range = document.createRange();
          range.setStart(paragraph, 0);
          range.setEnd(diff, 0);
          const before = anchorForRange(range).quote;
          const afterParagraph = document.querySelector('#merge-both').firstChild;
          // An empty light DOM has just offset zero, before its shadow words.
          // Put the trailing endpoint outside the host to exclude those words.
          range.setStartAfter(diff);
          range.setEnd(afterParagraph, afterParagraph.length);
          return [before, anchorForRange(range).quote];
        }"""
    )
    assert quotes == [
        "The store is capped at forty megabytes a workspace.",
        "The merge rule Two people editing one document offline is the case to answer.",
    ]


def test_an_id_staged_into_a_shadow_tree_is_still_the_pages_id(browser, serve):
    """Every question the runtime asks by id goes through one lookup, and a widget that
    stages its authored children carries their ids into its shadow tree with them. While
    that lookup was the document's alone the answer came back null and each caller quietly
    did nothing — here, an anchor stored and a mark never painted, with no error to find.

    Staged by hand because the one shipped x-shadow widget builds its tree out of parsed
    data and mints no ids, so nothing reaches this yet; what the next one does is exactly
    this move. The clearing sweep is the other half — a mark the repaint cannot reach is
    a mark that outlives its reason — so the second comment has to take the first's place
    rather than stand beside it."""
    page = open_page(browser, serve(TWICE_PAGE))
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    page.evaluate(
        "() => document.getElementById('patch').shadowRoot"
        ".querySelector('pre').id = 'row'"
    )
    # Through a locator: the paint lands on the poll that follows the write rather than
    # with it, so a read taken straight after passes on a quiet machine and fails on a
    # busy one. `#row` reaches into the open tree the way the runtime now has to.
    row = page.locator("#row")
    marked = re.compile(r"\blf-mark-el\b")
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-staged",
            "author": "user",
            "revision": 1,
            "text": "About the staged line.",
            "anchor": {"section": "row"},
        },
    )
    told(page)
    expect(row).to_have_class(marked)
    notes = """(count) => {
        const row = document.getElementById('patch').shadowRoot.getElementById('row');
        return (row.ariaDetailsElements ?? []).length === count;
    }"""
    page.wait_for_function(notes, arg=1)
    assert row.evaluate("el => el.ariaDetailsElements[0].textContent") == "1 comment"

    # Resolved, so the next repaint has nothing to say here: the count has to go, and
    # it can only go if the sweep that clears it reaches the tree that holds the row.
    append_carried_log_record(
        d, {"kind": "resolve", "author": "user", "parent": "c-staged"}
    )
    told(page)
    expect(row).not_to_have_class(marked)
    page.wait_for_function(notes, arg=0)


# Each source and each posture once: the source decides what loads, the posture what fits.
@pytest.mark.parametrize(("manifest", "mobile"), [(False, True), (True, False)])
def test_a_diff_shows_native_file_metadata_without_empty_disclosures(
    browser, serve, manifest, mobile
):
    """Inline and bound evidence preserve native operations at reading widths."""
    source = """diff --git a/app.js b/app.js
old mode 100644
new mode 100755
--- a/app.js
+++ b/app.js
@@ -1 +1 @@
-const value = 1;
+const value = 2;
diff --git a/old-name.js b/new-name.js
similarity index 100%
rename from old-name.js
rename to new-name.js
diff --git "a/old\\tname.js" "b/new\\tname.js"
similarity index 100%
rename from "old\\tname.js"
rename to "new\\tname.js"
diff --git "a/\\357\\273\\277old.js" "b/\\357\\273\\277new.js"
similarity index 100%
rename from "\\357\\273\\277old.js"
rename to "\\357\\273\\277new.js"
diff --git a/mode.sh b/mode.sh
old mode 100644
new mode 100755
diff --git a/binary.dat b/binary.dat
index 1111111..2222222 100644
Binary files a/binary.dat and b/binary.dat differ
diff --git a/original.js b/copy.js
similarity index 100%
copy from original.js
copy to copy.js
diff --git a/original.js b/edited-copy.js
similarity index 75%
copy from original.js
copy to edited-copy.js
--- a/original.js
+++ b/edited-copy.js
@@ -1 +1 @@
-const original = 1;
+const copied = 2;
diff --git a/added-empty b/added-empty
new file mode 100644
index 0000000..e69de29
diff --git a/deleted-empty b/deleted-empty
deleted file mode 100644
index e69de29..0000000
diff --git a/type-change b/type-change
deleted file mode 100644
--- a/type-change
+++ /dev/null
@@ -1 +0,0 @@
-before
diff --git a/type-change b/type-change
new file mode 120000
--- /dev/null
+++ b/type-change
@@ -0,0 +1 @@
+target
\\ No newline at end of file
diff --git a/reverse-type b/reverse-type
deleted file mode 120000
--- a/reverse-type
+++ /dev/null
@@ -1 +0,0 @@
-target
\\ No newline at end of file
diff --git a/reverse-type b/reverse-type
new file mode 100644
--- /dev/null
+++ b/reverse-type
@@ -0,0 +1 @@
+after
diff --git a/same-type-text b/same-type-text
deleted file mode 100644
--- a/same-type-text
+++ /dev/null
@@ -1 +0,0 @@
-target
\\ No newline at end of file
diff --git a/same-type-text b/same-type-text
new file mode 120000
--- /dev/null
+++ b/same-type-text
@@ -0,0 +1 @@
+target
\\ No newline at end of file
diff --git a/binary-type b/binary-type
deleted file mode 100644
index ac46f4c6762c926aeadd5b94702c2041e45f63c9..0000000000000000000000000000000000000000
GIT binary patch
literal 0
HcmV?d00001

literal 9
Qcmd1LNnuFJ$xq?}01v?e=>Px#

diff --git a/binary-type b/binary-type
new file mode 120000
--- /dev/null
+++ b/binary-type
@@ -0,0 +1 @@
+binary-target
\\ No newline at end of file"""
    authored = leaf_page(
        "Native Git changes",
        '<h1 id="changes">Changes</h1><lf-diff id="mixed-rename-diff"'
        + (' source="native-patch">' if manifest else f"><pre>{escape(source)}</pre>")
        + "</lf-diff>",
    )
    url = serve(authored)
    if manifest:
        data_model.cmd_data_set(serve.page_dir, "native-patch", patch_manifest(source))
    context = browser.new_context(
        viewport={"width": 390 if mobile else 1280, "height": 900}, has_touch=mobile
    )
    page = open_page(browser, url, context=context)
    result = page.evaluate("""async () => {
      const host = document.querySelector('#mixed-rename-diff');
      const shadow = host.shadowRoot;
      const renames = [...(shadow?.querySelectorAll('.lf-diff-metadata') ?? [])];
      const rename = renames[0];
      const quotedRename = renames[1];
      const bomRename = renames[2];
      const { says, wrote } = await window.__lfWidgetApi();
      return {
        rendered: host.classList.contains('lf-rendered'),
        error: host.shadowRoot?.querySelector('.lf-error')?.firstChild?.textContent ?? null,
        details: shadow?.querySelectorAll('details').length ?? 0,
        diffs: shadow?.querySelectorAll('pre').length ?? 0,
        renameCount: renames.length,
        evidence: [...shadow.querySelectorAll(".lf-diff-evidence")].map(node => node.textContent),
        metadata: renames.slice(3).map(node => node.querySelector('.lf-diff-stat').textContent),
        copied: [...shadow.querySelectorAll('summary')].find(node => node.textContent.includes('edited-copy.js'))?.textContent.includes('copied'),
        overflow: shadow.host.scrollWidth > shadow.host.clientWidth,
        pathsVisible: [...shadow.querySelectorAll('summary .lf-diff-base')].every(node => node.getBoundingClientRect().width > 1),
        metadataLines: renames.reduce((total, node) => total + node.querySelectorAll('[data-line]').length, 0),
        from: rename?.querySelector('.lf-diff-source-path')?.textContent ?? null,
        to: rename?.querySelector('.lf-diff-destination-path')?.textContent ?? null,
        stat: rename?.querySelector('.lf-diff-stat')?.textContent ?? null,
        generated: rename?.dataset.lfGen === '1',
        saidOverride: rename?.hasAttribute('data-lf-said') ?? null,
        quotedFrom:
          quotedRename?.querySelector('.lf-diff-source-path')?.textContent ?? null,
        quotedTo: quotedRename?.querySelector('.lf-diff-destination-path')?.textContent ?? null,
        bomFrom: bomRename?.querySelector('.lf-diff-source-path')?.textContent ?? null,
        bomTo: bomRename?.querySelector('.lf-diff-destination-path')?.textContent ?? null,
        lines: [...(shadow?.querySelectorAll('[data-line]') ?? [])]
          .map(line => line.textContent),
        saysRename: says(document).includes('old-name.js → new-name.js'),
        wroteRename: wrote(document).includes('old-name.js → new-name.js'),
      };
    }""")
    assert result == {
        "rendered": True,
        "error": None,
        "details": 6,
        "diffs": 6,
        "renameCount": 8,
        "evidence": [
            "mode 100644 → 100755",
            "mode 100644 → 120000",
            "mode 120000 → 100644",
            "mode 100644 → 120000",
            "binary content · mode 100644 → 120000",
        ],
        "metadata": [
            "mode 100644 → 100755",
            "binary content",
            "copied",
            "added",
            "deleted",
        ],
        "copied": True,
        "overflow": False,
        "pathsVisible": True,
        "metadataLines": 0,
        "from": "old-name.js",
        "to": "new-name.js",
        "stat": "renamed",
        "generated": True,
        "saidOverride": False,
        "quotedFrom": "old\tname.js",
        "quotedTo": "new\tname.js",
        "bomFrom": "\ufeffold.js",
        "bomTo": "\ufeffnew.js",
        "lines": [
            "const value = 1;",
            "const value = 2;",
            "const original = 1;",
            "const copied = 2;",
            "before",
            "target",
            "target",
            "after",
            "target",
            "target",
            "binary-target",
        ],
        "saysRename": True,
        "wroteRename": False,
    }

    for path, side, text in [
        ("type-change", "old", "before"),
        ("type-change", "new", "target"),
        ("reverse-type", "old", "target"),
        ("reverse-type", "new", "after"),
        ("same-type-text", "old", "target"),
        ("same-type-text", "new", "target"),
    ]:
        key = json.dumps([path, side, 1], separators=(",", ":"))
        line = page.locator(f"lf-diff [data-lf-datum='{key}']")
        expect(line).to_have_text(text)
        expect(line).to_have_attribute("data-lf-datum-label", f"{path} · {side} line 1")
        comment = page.get_by_role(
            "button", name=f"Comment on {path} · {side} line 1", exact=True
        )
        if mobile:
            comment.tap()
        else:
            line.hover()
            comment.click()
        outlet = page.locator(
            f"lf-diff .lf-diff-thread-outlet[data-lf-thread-datum='{key}']"
        )
        expect(outlet.locator(".lf-fab-input")).to_be_focused()
        page.keyboard.press("Escape")
        assert (
            page.locator("lf-diff").evaluate(
                "(diff, key) => diff.lfDataDatum(JSON.stringify(key)).textContent.trim()",
                [path, "source", side, 1],
            )
            == text
        )
        expect(
            page.locator(f'lf-diff [data-lf-datum=\'["{path}","file"]\']')
        ).to_have_count(1)


def test_a_block_leaving_the_viewport_keeps_its_focused_comment(browser, serve):
    """A block scrolling out of view gives the viewport its draft before it loses focus."""
    source = named_source("live-progress")
    page = open_page(browser, serve(source))
    resized(page, 700, 850)
    page.evaluate("""() => {
        const range = document.createRange();
        range.selectNodeContents(document.querySelector('#lp-k-checks'));
        getSelection().removeAllRanges();
        getSelection().addRange(range);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
    }""")
    field = page.locator(".lf-fab-input")
    page.keyboard.press("c")
    expect(field).to_be_visible()
    expect(field).to_be_focused()
    label = field.get_attribute("aria-label")
    assert label and label.startswith("Comment on “checks passing 4 of 5")
    draft = "Why does the remaining check need a decision?"
    write(field, draft)
    resized(page, 420, 850)
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", draft)

    # Native End on macOS scrolls the page even from a text box. A smooth scroll can
    # cross this narrow band in one frame or several; put that actual geometry on screen
    # directly so the test cannot miss the point where the region no longer fits a field.
    page.locator("#lp-status").evaluate(
        "region => window.scrollTo(0, scrollY + region.getBoundingClientRect().bottom - 20)"
    )
    rendered(page)
    assert page.locator("#lp-status").evaluate(
        "region => Math.abs(region.getBoundingClientRect().bottom - 20) < 1"
    )
    expect(field).to_be_visible()
    expect(field).to_be_focused()
    expect(field).to_have_attribute("aria-label", label)
    page.keyboard.type(" What must Finance decide?")
    expect(field).to_have_js_property("value", draft + " What must Finance decide?")


def test_a_revised_example_travels_between_its_own_versions(browser, serve):
    """The corpus's own reading of version travel, on the one example that was revised.

    Every other version fixture publishes a second version out of one markup string,
    which is a page nobody wrote: the two documents differ by whatever the fixture
    edited, and what a user would see marked is whatever that edit happened to be.
    The shipped example is an authored pair — a proposal and the version that answered
    a comment on it — so what the comparison marks here is what a revision is: the
    paragraph rewritten around the sentence the user quoted, the paragraph and
    step it grew, and the title and lede updated to state the exception. Everything
    the revision left alone stays unmarked, including the
    section the other thread stands on, and both threads stay attached because both
    quotes survived.

    That is also this file's floor for the corpus. The example sweeps serve the newest
    version and never press anything, so with no reading here the picker could offer
    a list nobody walks and a Compare control nobody presses on every page in examples/."""
    example = named_source("log-retention")
    page = open_page(browser, serve(example))

    # Served at the newest version, with the earlier one under Versions.
    versions = panel_menu(page, "versions")
    expect(
        versions.locator(".lf-fp-version[data-lf-current] .lf-fp-item")
    ).to_contain_text("v2")
    expect(versions.locator(".lf-fp-version")).to_have_count(2)
    page.locator(".lf-fp-leaf").click()

    compare_with(page, 1)
    expect(page.locator("main .lf-ins-block")).to_have_count(5)
    marked = page.eval_on_selector_all(
        "main .lf-ins-block", "els => els.map(e => e.id).sort()"
    )
    assert marked == [
        "ret-cost-body",
        "ret-cost-keep",
        "ret-lede",
        "ret-steps-carve",
        "ret-title",
    ], marked
    # A Change margin entry's press says what it reached, in the notice slot: its target is
    # usually on screen already, so the scroll moves nothing and a press that only spoke
    # to the live region was, to a sighted user, a press that did nothing. What the
    # press also discloses is the next test's; this one holds it to naming its target.
    page.locator(
        '.lf-margin-entry:has(svg[data-lf-icon="change"]):visible'
    ).first.click()
    expect_panel_says(page, "2 blocks edited since v1")

    # The threads the log opened, both still on their passages: one on a block the
    # revision rewrote, one on a block it never touched.
    listed = listed_threads(page)
    assert len(listed) == 2, listed
    assert detached_threads(page, listed) == set()
    painted = re.sub(
        r"\s",
        "",
        page.evaluate(
            "() => [...CSS.highlights.get('lf-mark')].map(r => r.toString()).join('')"
        ),
    )
    for quote in (
        "Two years of incident write-ups name a log older than six weeks exactly twice.",
        (
            "Across eighteen months of query history, 90% of reads touch logs less than "
            "a week old and 95% stay within 42 days."
        ),
    ):
        assert re.sub(r"\s", "", quote) in painted, painted[:160]

    # And the older document is a real destination, not just a row: choosing it pins
    # the user to the virtual version address the picker named.
    panel_menu(page, "versions").locator(
        ".lf-fp-version:not([data-lf-current]) > .lf-fp-item"
    ).click()
    page.wait_for_url(re.compile(r"/versions/v1\.html"))
    expect(
        panel_menu(page, "versions").locator(
            ".lf-fp-version[data-lf-current] .lf-fp-item"
        )
    ).to_contain_text("v1")
    page.locator(".lf-fp-leaf").click()
    expect(page.locator("#ret-cost-keep")).to_have_count(0)


LATE_STAGE = {
    "description": "A project widget that stages its authored children when asked.",
    "type": "object",
    "properties": {"id": {"type": "string"}},
    "required": ["id"],
    "additionalProperties": False,
    "x-content": "markup",
    "x-shadow": True,
    "x-example": '<lf-late-stage id="example"><p>Words.</p></lf-late-stage>',
}
LATE_STAGE_MODULE = """
import {shadowStage} from '/runtime/widget-api.js';
customElements.define('lf-late-stage', class extends HTMLElement {
  stage() { shadowStage(this, [...this.childNodes]); }
});
"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_passage_staged_into_a_new_shadow_tree_keeps_its_mark(engine, request, serve):
    """A widget that moves its authored words into a declared shadow tree after the
    page painted their mark takes the mark along: the move collapses the mark's live
    range onto the host, so the new tree's words are read again and their mark
    painted at once, with its hand under the pointer, and no other repaint behind it."""
    url = serve(
        leaf_page(
            "Late stage",
            '<lf-late-stage id="late"><p id="inside">The words that hold a marked '
            "passage inside the widget.</p></lf-late-stage><p>After.</p>",
        ),
        layer_registry={"lf-late-stage": LATE_STAGE},
        layer_widgets={"lf-late-stage.js": LATE_STAGE_MODULE},
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "text": "Which passage?",
            "anchor": {"section": "inside", "quote": "a marked passage"},
        },
    )
    page = open_page(request.getfixturevalue(engine), url)
    marked = "() => [...(CSS.highlights.get('lf-mark') ?? [])].map(String)"
    page.wait_for_function(f"() => ({marked})().includes('a marked passage')")
    page.evaluate("() => document.getElementById('late').stage()")
    page.wait_for_function(f"() => ({marked})().includes('a marked passage')")
    box = page.evaluate(
        """() => {
          const text = document.getElementById('late').shadowRoot
            .getElementById('inside').firstChild;
          const at = text.data.indexOf('a marked passage');
          const range = document.createRange();
          range.setStart(text, at);
          range.setEnd(text, at + 3);
          return range.getBoundingClientRect().toJSON();
        }"""
    )
    page.mouse.move(box["left"] - 20, box["top"] - 20)
    page.mouse.move(box["left"] + 4, box["top"] + box["height"] / 2, steps=3)
    expect(page.locator("[data-lf-over-mark]")).to_have_count(1)


def test_a_presentation_that_changes_no_mark_builds_none(browser, serve):
    """The anchor paint builds a thread's marks, the index the pointer is found in and
    the highlight painting them only for a presentation that changes a mark: ten that
    change none build nothing (anchor-paint.js, `paint`)."""
    url = serve(leaf_page("Kept", '<p id="kept">Words a thread is about.</p>'))
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "About these?",
            "anchor": {"section": "kept", "quote": "a thread"},
        },
    )
    page = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) === 1")
    built = page.evaluate(
        """async () => {
          const api = await window.__lfCheckApi();
          const own = CSS.highlights.set.bind(CSS.highlights);
          let built = 0;
          CSS.highlights.set = (name, value) => {
            if (name === 'lf-mark') built++;
            return own(name, value);
          };
          for (let n = 0; n < 10; n++) {
            api.presentDocument();
            await api.whenDocumentPresented();
          }
          CSS.highlights.set = own;
          return built;
        }"""
    )
    assert built == 0, built


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_revision_that_moves_marked_words_moves_where_their_mark_is_found(
    engine, request, serve
):
    """A revision that writes words ahead of a marked phrase in its paragraph moves the
    phrase along its text, and its mark with it: the pointer finds the mark where it is
    now drawn, by the hand, the preview and a press, and nothing at the words that now
    stand where the phrase stood."""

    def page_with(prefix):
        return leaf_page(
            "Moved",
            f'<p id="moved">{prefix}Words before the marked phrase and after it.</p>'
            + "<p>More.</p>" * 4,
        )

    url = serve(page_with(""))
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "About the phrase?",
            "anchor": {"section": "moved", "quote": "marked phrase"},
        },
    )
    page = open_page(request.getfixturevalue(engine), live_url(url))
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) === 1")
    words = """(at) => {
      const text = document.getElementById('moved').firstChild;
      const range = document.createRange();
      range.setStart(text, at);
      range.setEnd(text, at + 3);
      return range.getBoundingClientRect().toJSON();
    }"""
    stood = page.evaluate(
        "() => document.getElementById('moved').textContent.indexOf('marked')"
    )
    _publish(
        serve.page_dir,
        2,
        page_with("An entirely new prefix has been inserted. "),
        "two",
    )
    told(page)
    expect(page.locator("#moved")).to_contain_text("An entirely new prefix")
    stands = page.evaluate(
        "() => document.getElementById('moved').textContent.indexOf('marked')"
    )
    assert stands > stood
    old = page.evaluate(words, stood)
    page.mouse.move(old["left"] - 30, old["top"] - 30)
    page.mouse.move(old["left"] + 4, old["top"] + old["height"] / 2, steps=2)
    page.wait_for_timeout(300)
    expect(page.locator("[data-lf-over-mark]")).to_have_count(0)
    now = page.evaluate(words, stands)
    page.mouse.move(now["left"] + 4, now["top"] + now["height"] / 2, steps=2)
    expect(page.locator("[data-lf-over-mark]")).to_have_count(1)
    expect(page.locator("#lf-preview .lf-preview-word")).to_have_text(
        "About the phrase?"
    )
    page.mouse.click(now["left"] + 4, now["top"] + now["height"] / 2)
    expect(page.locator(".lf-margin-preview:not([hidden])")).to_be_visible()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_words_a_script_writes_ahead_of_a_mark_move_where_it_is_found(
    engine, request, serve
):
    """A script that writes words ahead of a marked phrase in its text node, with no
    revision and nothing presented after it, moves the phrase's mark with its words, and
    the pointer finds the mark where it is now drawn, by the hand and the preview, and a
    press there opens the thread's card at once and keeps it open, as every reader of the
    passage reads where its words now stand; nothing answers at the words that now stand
    where the phrase stood."""
    url = serve(
        leaf_page(
            "Script",
            '<p id="moved">Words before the marked phrase and after it.</p>'
            + "<p>More.</p>" * 4,
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "About the phrase?",
            "anchor": {"section": "moved", "quote": "marked phrase"},
        },
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) === 1")
    at = "() => document.getElementById('moved').textContent.indexOf('marked')"
    stood = page.evaluate(at)
    words = """(at) => {
      const text = document.getElementById('moved').firstChild;
      const range = document.createRange();
      range.setStart(text, at);
      range.setEnd(text, at + 3);
      return range.getBoundingClientRect().toJSON();
    }"""
    # The pointer rests on the phrase first, so the marks have been found where they
    # stood before the words move.
    before = page.evaluate(words, stood)
    page.mouse.move(before["left"] - 30, before["top"] - 30)
    page.mouse.move(before["left"] + 4, before["top"] + before["height"] / 2, steps=2)
    expect(page.locator("[data-lf-over-mark]")).to_have_count(1)
    page.mouse.move(2, 2)
    page.evaluate(
        "() => document.getElementById('moved').firstChild"
        ".insertData(0, 'A script wrote these words first. ')"
    )
    stands = page.evaluate(at)
    assert stands > stood
    old = page.evaluate(words, stood)
    page.mouse.move(old["left"] - 30, old["top"] - 30)
    page.mouse.move(old["left"] + 4, old["top"] + old["height"] / 2, steps=2)
    page.wait_for_timeout(300)
    # Read once: a later presentation would find the marks again and hide the fault.
    assert not page.evaluate(
        "() => document.querySelector('[data-lf-over-mark]') !== null"
    )
    page.mouse.click(old["left"] + 4, old["top"] + old["height"] / 2)
    page.wait_for_timeout(300)
    expect(page.locator(".lf-margin-preview:not([hidden])")).to_have_count(0)
    now = page.evaluate(words, stands)
    page.mouse.move(now["left"] + 4, now["top"] + now["height"] / 2, steps=2)
    expect(page.locator("[data-lf-over-mark]")).to_have_count(1)
    expect(page.locator("#lf-preview .lf-preview-word")).to_have_text(
        "About the phrase?"
    )
    page.mouse.click(now["left"] + 4, now["top"] + now["height"] / 2)
    card = page.locator(".lf-margin-preview:not([hidden])")
    expect(card).to_be_visible()
    page.wait_for_timeout(500)
    expect(card).to_be_visible()
    expect(card.locator(".lf-page-thread")).to_contain_text("About the phrase?")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_words_a_split_carries_into_a_new_text_node_keep_their_mark(
    engine, request, serve
):
    """A script that splits a marked phrase's text node between its words carries the
    rest of the phrase, and its mark, into a new text node: the pointer finds the mark
    on the words in either node, by the hand and the preview."""
    url = serve(
        leaf_page(
            "Split",
            '<p id="split">Words before the marked phrase and after it.</p>'
            + "<p>More.</p>" * 4,
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "About the phrase?",
            "anchor": {"section": "split", "quote": "marked phrase"},
        },
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) === 1")
    page.evaluate(
        """() => {
          const text = document.getElementById('split').firstChild;
          text.splitText(text.data.indexOf('phrase'));
        }"""
    )
    for word in ("marked", "phrase"):
        box = page.evaluate(
            """(word) => {
              const p = document.getElementById('split');
              const text = [...p.childNodes].find((node) => node.data.includes(word));
              const range = document.createRange();
              range.setStart(text, text.data.indexOf(word) + 1);
              range.setEnd(text, text.data.indexOf(word) + 3);
              return range.getBoundingClientRect().toJSON();
            }""",
            word,
        )
        page.mouse.move(2, 2)
        page.wait_for_timeout(300)
        assert not page.evaluate(
            "() => document.querySelector('[data-lf-over-mark]') !== null"
        )
        page.mouse.move(box["left"] + 2, box["top"] + box["height"] / 2, steps=2)
        page.wait_for_timeout(300)
        # Read once: a later presentation would find the marks again and hide the fault.
        assert page.evaluate(
            "() => document.querySelector('[data-lf-over-mark]') !== null"
        ), word
        expect(page.locator("#lf-preview .lf-preview-word")).to_have_text(
            "About the phrase?"
        )


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_search_match_running_into_a_shadow_stage_shows_its_start(
    engine, request, serve
):
    """A page search's match that starts in the page's words and runs on into a declared
    shadow stage standing most of a window below them is brought into sight by where its
    words start, as a thread is travelled to, rather than by where they end."""
    url = serve(
        leaf_page(
            "Across",
            "<p>Before.</p>"
            * 40
            + '<div id="both"><p id="first">The match starts here</p>'
            '<lf-late-stage id="late" style="display: block; margin-block-start: 420px">'
            '<p id="second">and ends inside the stage.</p></lf-late-stage></div>'
            + "<p>After.</p>"
            * 40,
        ),
        layer_registry={"lf-late-stage": VERBATIM_STAGE},
        layer_widgets={"lf-late-stage.js": STAGED_ON_CONNECT},
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.set_viewport_size({"width": 900, "height": 600})
    page.keyboard.press("/")
    # The whole query at once, as a paste: typed, its first word alone finds the
    # paragraph's words and brings them into sight before the match crosses the root.
    page.get_by_role("searchbox", name="Search page text").fill(
        "match starts here and ends inside"
    )
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")
    page.wait_for_timeout(300)
    start = page.evaluate(
        """() => {
          const text = document.getElementById('first').firstChild;
          const range = document.createRange();
          range.setStart(text, 4);
          range.setEnd(text, 9);
          return range.getBoundingClientRect().toJSON();
        }"""
    )
    assert 0 <= start["top"] and start["bottom"] <= 600, start


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_the_comment_box_comes_back_to_where_its_passage_starts(engine, request, serve):
    """The comment box of a draft on a passage that runs from the page's words into a
    declared shadow stage standing most of a window below them comes back, from a page
    scrolled away, to where the passage's words start, as a search's match and a thread
    are travelled to, rather than to where they end."""
    url = serve(
        leaf_page(
            "Across",
            "<p>Before.</p>"
            * 40
            + '<div id="both"><p id="first">The match starts here</p>'
            '<lf-late-stage id="late" style="display: block; margin-block-start: 420px">'
            '<p id="second">and ends inside the stage.</p></lf-late-stage></div>'
            + "<p>After.</p>"
            * 40,
        ),
        layer_registry={"lf-late-stage": VERBATIM_STAGE},
        layer_widgets={"lf-late-stage.js": STAGED_ON_CONNECT},
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.set_viewport_size({"width": 900, "height": 600})
    # A draft written on the passage, which the page opens again as it loads.
    page.evaluate(
        """async () => {
          const boot = document.querySelector('script[data-lf-entry]').dataset.lfEntry;
          const load = (path) => import(new URL(path, new URL(boot, location.href)).href);
          const {saveDraft} = await load('runtime/drafts.js');
          const {DRAFT_FORMAT} = await load('runtime/kernel-facts.js');
          const {anchorKey} = await load('runtime/anchor-coordinate.js');
          const anchor = {section: 'both', quote: 'match starts here and ends inside'};
          saveDraft('composer:' + anchorKey(anchor), 'My draft words', {
            format: DRAFT_FORMAT, anchor, revision: 1, suggest: false, about: null,
            drawing: null, touched: Date.now(),
          });
        }"""
    )
    page.reload()
    expect(page.locator(".lf-composer")).to_be_visible()
    page.evaluate("() => scrollTo(0, 0)")
    page.evaluate(
        """async () => {
          const api = await window.__lfCheckApi();
          api.bringBackSurfaceOf(document.querySelector('.lf-fab-bar'), 'instant');
        }"""
    )
    page.wait_for_timeout(300)
    start = page.evaluate(
        """() => {
          const text = document.getElementById('first').firstChild;
          const range = document.createRange();
          range.setStart(text, 4);
          range.setEnd(text, 9);
          return range.getBoundingClientRect().toJSON();
        }"""
    )
    assert 0 <= start["top"] and start["bottom"] <= 600, start


# A paragraph whose marked phrase follows other words in its text node, after an
# element of its own words, so a change can leave the phrase's text node standing
# after another text node in the paragraph.
CHANGED = (
    '<p id="changed"><em>Lead words</em> Prefix words before the marked phrase '
    "and after it.</p>" + "<p>More.</p>" * 4
)
# The phrase's place: the box of its first three characters, wherever its text node is.
PHRASE_AT = """(words) => {
  const p = document.getElementById('changed');
  const walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
  for (let text = walker.nextNode(); text; text = walker.nextNode()) {
    const at = text.data.indexOf(words);
    if (at < 0) continue;
    const range = document.createRange();
    range.setStart(text, at);
    range.setEnd(text, at + 3);
    return range.getBoundingClientRect().toJSON();
  }
  return null;
}"""


def _changed_page(request, engine, serve):
    url = serve(leaf_page("Changed", CHANGED))
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "About the phrase?",
            "anchor": {"section": "changed", "quote": "marked phrase"},
        },
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) === 1")
    return page


def _rest_on(page, box):
    """Rest the pointer on a box, from away, and read the hand once: a later
    presentation would find the marks again and hide a fault."""
    page.mouse.move(2, 2)
    page.wait_for_timeout(200)
    page.mouse.move(box["left"] - 20, box["top"] - 20)
    page.mouse.move(box["left"] + 4, box["top"] + box["height"] / 2, steps=2)
    page.wait_for_timeout(300)
    return page.evaluate("() => document.querySelector('[data-lf-over-mark]') !== null")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_mark_whose_text_node_lost_the_words_before_it_is_still_found(
    engine, request, serve
):
    """A script that splits a marked phrase's text node just before the phrase and then
    removes the words before it leaves the phrase standing in a text node of its own
    after the paragraph's first words: the pointer finds its mark there, by the hand
    and the preview, and a press opens its thread."""
    page = _changed_page(request, engine, serve)
    page.evaluate(
        """() => {
          const p = document.getElementById('changed');
          const text = p.childNodes[1];
          text.splitText(text.data.indexOf('marked'));
          text.remove();
        }"""
    )
    box = page.evaluate(PHRASE_AT, "marked")
    assert _rest_on(page, box)
    expect(page.locator("#lf-preview .lf-preview-word")).to_have_text(
        "About the phrase?"
    )
    page.mouse.click(box["left"] + 4, box["top"] + box["height"] / 2)
    expect(page.locator(".lf-margin-preview:not([hidden])")).to_be_visible()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_mark_whose_text_node_a_script_replaced_is_found_in_the_new_one(
    engine, request, serve
):
    """A script that replaces a marked phrase's text node with a new one holding the same
    phrase takes the phrase's mark to the new node, where the pointer finds it, by the
    hand and the preview, and a press opens its thread."""
    page = _changed_page(request, engine, serve)
    page.evaluate(
        """() => {
          const p = document.getElementById('changed');
          const text = p.childNodes[1];
          p.replaceChild(document.createTextNode(text.data + ' Then more.'), text);
        }"""
    )
    page.wait_for_function(
        "() => [...(CSS.highlights.get('lf-mark') ?? [])].map(String).join()"
        " === 'marked phrase'"
    )
    box = page.evaluate(PHRASE_AT, "marked")
    assert _rest_on(page, box)
    expect(page.locator("#lf-preview .lf-preview-word")).to_have_text(
        "About the phrase?"
    )
    page.mouse.click(box["left"] + 4, box["top"] + box["height"] / 2)
    expect(page.locator(".lf-margin-preview:not([hidden])")).to_be_visible()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_mark_whose_words_a_script_broke_up_is_marked_no_more(engine, request, serve):
    """A script that writes other words into a marked phrase leaves no passage the
    thread's quote names, so the phrase's words are marked no more, the hand stands
    nowhere on them, and a press there opens nothing, as reading the page again finds."""
    page = _changed_page(request, engine, serve)
    page.evaluate(
        """() => {
          const text = document.getElementById('changed').childNodes[1];
          text.insertData(text.data.indexOf('phrase'), 'unrelated ');
        }"""
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) === 0")
    box = page.evaluate(PHRASE_AT, "marked")
    assert not _rest_on(page, box)
    page.mouse.click(box["left"] + 4, box["top"] + box["height"] / 2)
    page.wait_for_timeout(300)
    expect(page.locator(".lf-margin-preview:not([hidden])")).to_have_count(0)


MARKED = "() => [...(CSS.highlights.get('lf-mark') ?? [])].map(String).join('|')"


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_mark_whose_words_a_script_puts_back_is_marked_again(engine, request, serve):
    """A script that writes other words into a marked phrase and, in a later task, takes
    them out again leaves the phrase as the thread's quote names it, so once the
    pointer asks where the marks stand, the phrase is marked again, where the pointer
    finds it, as reading the page again finds."""
    page = _changed_page(request, engine, serve)
    page.evaluate(
        """() => {
          const text = document.getElementById('changed').childNodes[1];
          text.insertData(text.data.indexOf('phrase'), 'unrelated ');
        }"""
    )
    page.wait_for_function(f"() => ({MARKED})() === ''")
    page.evaluate(
        """() => {
          const text = document.getElementById('changed').childNodes[1];
          text.deleteData(text.data.indexOf('unrelated '), 'unrelated '.length);
        }"""
    )
    box = page.evaluate(PHRASE_AT, "marked")
    _rest_on(page, box)
    page.wait_for_function(f"() => ({MARKED})() === 'marked phrase'")
    assert _rest_on(page, box)
    expect(page.locator("#lf-preview .lf-preview-word")).to_have_text(
        "About the phrase?"
    )


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_marked_phrase_a_script_writes_again_is_marked_no_more(
    engine, request, serve
):
    """A script that writes a marked phrase a second time in its section, where nothing
    the thread kept around the phrase tells the two apart, leaves its quote naming no
    one passage: the pointer finds no mark on the first, and once it has asked, the
    first is marked no more, as reading the page again finds."""
    page = _changed_page(request, engine, serve)
    page.evaluate(
        """() => {
          const again = document.createElement('em');
          again.textContent = 'The marked phrase again.';
          document.getElementById('changed').append(again);
        }"""
    )
    assert not _rest_on(page, page.evaluate(PHRASE_AT, "marked"))
    page.wait_for_function(f"() => ({MARKED})() === ''")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_words_a_script_puts_inside_a_passage_s_shadow_stage_unmark_it(
    engine, request, serve
):
    """A script that writes a word at the start of a declared shadow stage a marked
    passage runs into from the page's words before it puts that word inside the
    passage, which its thread's quote no longer names: the pointer finds no mark on the
    page's piece, and once it has asked, neither piece is marked, as reading the page
    again finds."""
    url = serve(
        leaf_page(
            "Across a root",
            '<div id="both"><p>The first line of the passage ends here.</p>'
            '<lf-late-stage id="late"><p>Its second line stands inside the widget.</p>'
            "</lf-late-stage></div>" + "<p>After.</p>" * 4,
        ),
        layer_registry={"lf-late-stage": VERBATIM_STAGE},
        layer_widgets={"lf-late-stage.js": STAGED_ON_CONNECT},
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Across the root?",
            "anchor": {
                "section": "both",
                "quote": "passage ends here. Its second line",
            },
        },
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.wait_for_function(f"() => ({MARKED})().split('|').length === 2")
    page.evaluate(
        """() => document.getElementById('late').shadowRoot.querySelector('p')
          .prepend('Inserted ')"""
    )
    line = page.evaluate(
        """() => {
          const text = document.querySelector('#both > p').firstChild;
          const at = text.data.indexOf('passage ends');
          const range = document.createRange();
          range.setStart(text, at);
          range.setEnd(text, at + 3);
          return range.getBoundingClientRect().toJSON();
        }"""
    )
    assert not _rest_on(page, line)
    page.wait_for_function(f"() => ({MARKED})() === ''")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_passage_a_script_makes_editable_inside_is_marked_no_more(
    engine, request, serve
):
    """A script that makes an element inside a marked passage editable puts an edge of
    the passage's words at either end of it, which a quote does not run across, so the
    pointer finds no mark on the passage, and once it has asked, the passage is marked
    no more, as reading the page again finds."""
    url = serve(
        leaf_page(
            "Editable",
            '<p id="edit">The passage <span id="inner">runs through</span> this '
            "span.</p>" + "<p>More.</p>" * 4,
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Through it?",
            "anchor": {"section": "edit", "quote": "passage runs through this"},
        },
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.wait_for_function(f"() => ({MARKED})() === 'passage |runs through| this'")
    page.evaluate(
        "() => { document.getElementById('inner').contentEditable = 'true'; }"
    )
    word = page.evaluate(
        """() => {
          const range = document.createRange();
          range.setStart(document.getElementById('edit').firstChild, 4);
          range.setEnd(document.getElementById('edit').firstChild, 7);
          return range.getBoundingClientRect().toJSON();
        }"""
    )
    assert not _rest_on(page, word)
    page.wait_for_function(f"() => ({MARKED})() === ''")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_the_thread_walk_reads_threads_where_a_script_left_them(engine, request, serve):
    """A script that takes a marked passage's words out and, in a later task, puts them
    back, while the pointer stays away, leaves the threads where they were: the thread
    walk from the page's top opens the first in reading order, as reading the page
    again finds."""
    url = serve(
        leaf_page(
            "Reading order",
            '<div id="all"><h1>Reading order</h1><p id="beta">Beta marked words.</p>'
            '<p id="alpha">Alpha marked words.</p></div>',
        )
    )
    for name in ("Alpha", "Beta"):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"{name} discussion",
                "anchor": {"section": "all", "quote": f"{name} marked words"},
            },
        )
    page = open_page(request.getfixturevalue(engine), url)
    page.wait_for_function(f"() => ({MARKED})().split('|').length === 2")
    page.mouse.move(1, 1)
    alpha = "() => document.querySelector('#alpha').firstChild"
    page.evaluate(f"() => {{ ({alpha})().data = 'Other words.'; }}")
    page.wait_for_timeout(150)
    assert page.evaluate(MARKED) == "Beta marked words"
    page.evaluate(f"() => {{ ({alpha})().data = 'Alpha marked words.'; }}")
    page.wait_for_timeout(150)
    page.keyboard.press("t")
    expect(page.locator(".lf-margin-preview:not([hidden])")).to_contain_text(
        "Beta discussion"
    )


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_press_in_the_task_a_script_repeats_a_marked_phrase_opens_nothing(
    engine, request, serve
):
    """A press on a marked phrase in the task in which a script wrote the phrase a second
    time, where nothing tells the two apart, finds no thread there; once the copy is
    gone again, the same press opens the thread: a press reads the page as the script
    left it."""
    page = _changed_page(request, engine, serve)
    press = """(again) => {
      const changed = document.getElementById('changed');
      const text = [...changed.childNodes]
        .find((node) => node.nodeType === Node.TEXT_NODE && node.data.includes('marked'));
      const range = document.createRange();
      range.setStart(text, text.data.indexOf('marked'));
      range.setEnd(text, text.data.indexOf('marked') + 3);
      const box = range.getBoundingClientRect();
      const [x, y] = [box.left + 4, box.top + box.height / 2];
      if (again)
        changed.append(Object.assign(document.createElement('em'),
          {textContent: 'The marked phrase again.'}));
      document.elementFromPoint(x, y).dispatchEvent(
        new MouseEvent('click', {bubbles: true, clientX: x, clientY: y, detail: 1}));
    }"""
    card = page.locator(".lf-margin-preview:not([hidden])")
    box = page.evaluate(PHRASE_AT, "marked")
    assert _rest_on(page, box)
    page.evaluate(press, True)
    page.wait_for_timeout(400)
    # Read once: a later presentation reads the page again and would hide the fault.
    assert card.count() == 0
    page.evaluate("() => document.querySelector('#changed em:last-child').remove()")
    _rest_on(page, box)
    page.wait_for_function(f"() => ({MARKED})() === 'marked phrase'")
    assert _rest_on(page, box)
    page.evaluate(press, False)
    expect(card).to_be_visible()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_quote_follows_its_section_s_id_to_another_element(engine, request, serve):
    """A script that swaps two elements' ids moves the section a thread's quote is
    scoped to, so the quote stands where the section now holds it: the pointer finds the
    mark on the element that now bears the id and none on the one that bore it, as
    reading the page again finds."""
    url = serve(
        leaf_page(
            "Swapped ids",
            '<p id="a">First shared phrase.</p><p id="b">Second shared phrase.</p>'
            + "<p>More.</p>" * 4,
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Which phrase?",
            "anchor": {"section": "a", "quote": "shared phrase"},
        },
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.wait_for_function(f"() => ({MARKED})() === 'shared phrase'")
    page.evaluate(
        """() => {
          const [first, second] = [document.getElementById('a'), document.getElementById('b')];
          first.id = 'b';
          second.id = 'a';
        }"""
    )
    phrase = """(id) => {
      const text = document.getElementById(id).firstChild;
      const range = document.createRange();
      range.setStart(text, text.data.indexOf('shared'));
      range.setEnd(text, text.data.indexOf('shared') + 3);
      return range.getBoundingClientRect().toJSON();
    }"""
    assert _rest_on(page, page.evaluate(phrase, "a"))
    assert not _rest_on(page, page.evaluate(phrase, "b"))
    marked = """() => [...CSS.highlights.get('lf-mark')]
      .map((range) => range.startContainer.parentElement.id).join()"""
    page.wait_for_function(f"() => ({marked})() === 'a'")


PENDING = "() => [...(CSS.highlights.get('lf-pending') ?? [])].map(String).join('|')"


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_draft_s_passage_keeps_its_mark_when_a_script_rewrites_around_it(
    engine, request, serve
):
    """A script that rewrites a paragraph while the user comments on a sentence in it,
    keeping the sentence, keeps the draft's mark on the sentence, on a page that holds
    no thread yet: the draft's passage stands where its words still are."""
    url = serve(
        leaf_page(
            "Draft placement",
            '<p id="words">A marked phrase belongs here.</p>' + "<p>More.</p>" * 3,
        )
    )
    page = open_page(request.getfixturevalue(engine), url)
    box = page.locator("#words").bounding_box()
    page.mouse.click(box["x"] + 25, box["y"] + box["height"] / 2, click_count=3)
    page.keyboard.press("c")
    page.wait_for_function(f"() => ({PENDING})().includes('A marked phrase')")
    before = page.evaluate(PENDING)
    page.evaluate(
        """() => {
          document.getElementById('words').textContent =
            'Prefix A marked phrase belongs here.';
        }"""
    )
    page.wait_for_timeout(300)
    # Read once: a later presentation reads the draft again and would hide the fault.
    assert page.evaluate(PENDING) == before


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_section_staged_again_in_a_new_widget_keeps_its_thread(
    engine, request, serve
):
    """A script that stages a section in a new widget's shadow tree and then puts the
    widget in place of the one whose shadow tree held the section moves the section's
    thread to the new one: the pointer finds the thread's mark on the new section, as
    reading the page again finds."""
    url = serve(
        leaf_page(
            "Staged again",
            '<lf-late-stage id="late"><p id="inner">The staged section.</p>'
            "</lf-late-stage>" + "<p>After.</p>" * 4,
        ),
        layer_registry={"lf-late-stage": LATE_STAGE},
        layer_widgets={"lf-late-stage.js": LATE_STAGE_MODULE},
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "About the section?",
            "anchor": {"section": "inner"},
        },
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.evaluate("() => document.getElementById('late').stage()")
    inner = "() => document.getElementById('late').shadowRoot.getElementById('inner')"
    page.wait_for_function(f"() => ({inner})()?.classList.contains('lf-mark-el')")
    page.evaluate(
        """async () => {
          const host = document.createElement('lf-late-stage');
          host.innerHTML = '<p id="inner">The staged section.</p>';
          host.stage();
          await new Promise(requestAnimationFrame);
          host.id = 'late';
          document.getElementById('late').replaceWith(host);
        }"""
    )
    box = page.evaluate(f"() => ({inner})().getBoundingClientRect().toJSON()")
    assert _rest_on(page, box)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_words_a_script_sets_in_elements_of_their_own_keep_their_thread(
    engine, request, serve
):
    """A script that sets a marked phrase's two words in inline elements of their own,
    with nothing between them, leaves the thread on them: where two inline elements
    meet is a place a word may end, so the quote "one two" still names them, the pointer
    finds the mark there, and the file's reading finds them too
    (tests/quote_cases.json)."""
    url = serve(
        leaf_page(
            "Run together",
            '<p id="pair">Before one two after.</p>' + "<p>More.</p>" * 4,
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "About these?",
            "anchor": {"section": "pair", "quote": "one two"},
        },
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.wait_for_function(f"() => ({MARKED})() === 'one two'")
    page.evaluate(
        """() => {
          document.getElementById('pair').innerHTML =
            'Before <span>one</span><span>two</span> after.';
        }"""
    )
    box = page.locator("#pair span").first.bounding_box()
    assert _rest_on(page, {"left": box["x"], "top": box["y"], "height": box["height"]})
    page.wait_for_function(f"() => ({MARKED})().replace(/[|\\s]/g, '') === 'onetwo'")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_page_search_finds_words_two_spans_run_together_outside_a_text_block(
    engine, request, serve
):
    """Page search finds the one word two spans side by side show, where they stand in
    no text block, as the page shows it and the browser's own find finds it."""
    url = serve(
        leaf_page(
            "Run together",
            '<div id="joined"><span>alpha</span><span>beta</span></div>'
            + "<p>More.</p>" * 4,
        )
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.keyboard.press("/")
    page.get_by_role("searchbox", name="Search page text").fill("alphabeta")
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_page_search_finds_words_an_output_runs_into(engine, request, serve):
    """Page search finds the one word an `<output>` and the words beside it show, with
    nothing between them, as the page draws it and the browser's own find finds it."""
    url = serve(
        leaf_page(
            "Output",
            '<div id="joined">alpha<output>beta</output>gamma</div>'
            + "<p>More.</p>" * 4,
        )
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.keyboard.press("/")
    page.get_by_role("searchbox", name="Search page text").fill("alphabetagamma")
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")


def test_page_search_passes_a_long_run_of_whitespace_its_next_word_does_not_follow(
    browser, serve
):
    """A query's words stand apart by any run of whitespace, so a long run after its
    first word that the next word doesn't follow is one more place that doesn't match:
    page search finds the copy further on, where a search that tried every split of the
    run held the tab."""
    url = serve(leaf_page("Runs", f"<p>card{' ' * 80}x</p><p>card It opens</p>"))
    page = open_page(browser, url)
    page.keyboard.press("/")
    page.get_by_role("searchbox", name="Search page text").fill("card It opens")
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_page_search_reads_two_staged_widgets_side_by_side_apart(
    engine, request, serve
):
    """Two widgets side by side, each staging its words in a shadow tree, read apart, as
    they did before they staged and as the file's reading reads them: page search
    finds their words with a space between them."""
    url = serve(
        leaf_page(
            "Two stages",
            '<div id="pair"><lf-late-stage id="one"><span>alpha</span></lf-late-stage>'
            '<lf-late-stage id="two"><span>beta</span></lf-late-stage></div>'
            + "<p>More.</p>"
            * 4,
        ),
        layer_registry={"lf-late-stage": VERBATIM_STAGE},
        layer_widgets={"lf-late-stage.js": STAGED_ON_CONNECT},
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.wait_for_function("() => document.getElementById('two')?.shadowRoot")
    page.keyboard.press("/")
    page.get_by_role("searchbox", name="Search page text").fill("alpha beta")
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize(
    ("markup", "words"),
    [
        (
            '<div id="row" style="display: flex; gap: 8px"><strong>Status</strong>'
            "<span>Ready</span></div>",
            "Status Ready",
        ),
        (
            '<lf-options id="pick"><lf-option id="drop"><small class="tag ok">'
            "recommended</small><strong>Drop the oldest documents</strong> Editing "
            'continues.</lf-option><lf-option id="pause"><strong>Pause editing'
            "</strong> Nothing leaves.</lf-option></lf-options>",
            "recommended Drop",
        ),
    ],
    ids=["flex row", "option chip"],
)
def test_page_search_finds_words_css_draws_apart_with_nothing_between_them(
    engine, markup, words, request, serve
):
    """Two inline elements with nothing between them read as one word or as two, since
    only the page's CSS says which: a flex row's label and value, or an option's chip
    and title, are found with a space between them, as they show."""
    url = serve(leaf_page("Apart by CSS", markup + "<p>More.</p>" * 4))
    page = open_page(request.getfixturevalue(engine), url)
    page.keyboard.press("/")
    page.get_by_role("searchbox", name="Search page text").fill(words)
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_page_search_finds_a_shipped_options_chip_and_title_apart(
    engine, request, serve
):
    """The default package's lf-ask example, as shipped, puts a chip and the option's
    title it stands beside apart, as the theme draws them: page search finds
    "recommended Drop"."""
    registry = json.loads(
        (Path(__file__).parents[2] / "packages/default/registry.json").read_text()
    )
    url = serve(leaf_page("Ask", registry["lf-ask"]["x-example"]))
    page = open_page(request.getfixturevalue(engine), url)
    page.keyboard.press("/")
    page.get_by_role("searchbox", name="Search page text").fill("recommended Drop")
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize(
    ("source", "words"),
    [("extending", "window The workspace"), ("how-it-works", "there The quote")],
)
def test_page_search_reads_a_docs_captions_title_apart_from_its_text(
    engine, source, words, request, serve
):
    """A figure caption in the product docs draws its title on a line of its own above
    its text, and page search finds the title's last word and the text's first apart."""
    page = open_page(request.getfixturevalue(engine), serve(named_source(source)))
    page.keyboard.press("/")
    page.get_by_role("searchbox", name="Search page text").fill(words)
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_page_search_finds_the_words_a_slot_outside_a_shadow_tree_holds(
    engine, request, serve
):
    """A `<slot>` in no shadow tree is an ordinary element, which draws its children, so
    page search finds its words among the words beside it, as the file reads them."""
    url = serve(
        leaf_page(
            "Light slot",
            '<p id="slotted">alpha<slot>beta</slot>gamma</p>' + "<p>More.</p>" * 4,
        )
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.keyboard.press("/")
    page.get_by_role("searchbox", name="Search page text").fill("alphabetagamma")
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_page_search_reads_a_said_label_apart_from_its_elements_words(
    engine, request, serve
):
    """A declared `x-says` label, drawn as its element's caption, reads apart from the
    words the element holds, as the file's reading reads it: page search finds the two
    with a space between them."""
    url = serve(
        leaf_page(
            "Said label",
            '<div id="pair"><lf-said-label id="said" label="Head">body words'
            "</lf-said-label></div>" + "<p>More.</p>" * 4,
        ),
        layer_registry={
            "lf-said-label": {
                "description": "Words with a label the runtime says before them.",
                "type": "object",
                "properties": {"id": {"type": "string"}, "label": {"type": "string"}},
                "required": ["id"],
                "additionalProperties": False,
                "x-content": "markup",
                "x-says": {"label": "before"},
                "x-example": '<lf-said-label id="example" label="Head">Words.'
                "</lf-said-label>",
            }
        },
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.wait_for_function("() => document.querySelector('#said > [data-lf-said]')")
    page.keyboard.press("/")
    page.get_by_role("searchbox", name="Search page text").fill("Head body")
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")


# A thread's quote inside a staged widget, scoped to the element around the widget.
STAGED_QUOTE = (
    '<div id="around"><p>Before the widget.</p><lf-late-stage id="late">'
    '<p id="inside">Words inside the stage hold the passage.</p></lf-late-stage></div>'
    + "<p>After.</p>"
    * 4
)
# A widget staged alike, filled while it stands apart, then put in the first one's place
# in a later task, so nothing the filling did reads the page after the swap.
STAGE_AGAIN = """async () => {
  const host = document.createElement('lf-late-stage');
  host.innerHTML = '<p id="inside">Words inside the stage hold the passage.</p>';
  host.stage();
  await new Promise(requestAnimationFrame);
  await new Promise(requestAnimationFrame);
  host.id = 'late';
  document.getElementById('late').replaceWith(host);
}"""
# Each range a highlight paints: its words, and whether they still stand in the page.
PAINTED = """(name) => [...(CSS.highlights.get(name) ?? [])]
  .map((range) => [String(range), range.startContainer.isConnected])"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_mark_in_a_widget_staged_again_moves_to_the_new_stage(engine, request, serve):
    """A script that replaces a widget whose shadow stage holds a marked passage with one
    staged alike, the passage's section being the element around the widget, moves the
    mark to the new stage's words at once, before anything asks where it stands."""
    url = serve(
        leaf_page("Staged mark", STAGED_QUOTE),
        layer_registry={"lf-late-stage": VERBATIM_STAGE},
        layer_widgets={"lf-late-stage.js": LATE_STAGE_MODULE},
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Inside?",
            "anchor": {"section": "around", "quote": "inside the stage hold"},
        },
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.mouse.move(1, 1)
    page.evaluate("() => document.getElementById('late').stage()")
    page.wait_for_function(f"() => ({MARKED})() === 'inside the stage hold'")
    page.evaluate(STAGE_AGAIN)
    page.wait_for_timeout(300)
    # Read once: a reader asking would settle placement and hide the fault.
    assert page.evaluate(PAINTED, "lf-mark") == [["inside the stage hold", True]]


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_draft_in_a_widget_staged_again_moves_to_the_new_stage(
    engine, request, serve
):
    """A script that replaces a widget whose shadow stage holds the passage a user is
    commenting on with one staged alike moves the draft's mark to the new stage's words
    at once, before anything asks where it stands."""
    url = serve(
        leaf_page("Staged draft", STAGED_QUOTE),
        layer_registry={"lf-late-stage": VERBATIM_STAGE},
        layer_widgets={"lf-late-stage.js": LATE_STAGE_MODULE},
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.evaluate("() => document.getElementById('late').stage()")
    page.evaluate(
        """() => {
          const text = document.getElementById('late').shadowRoot
            .getElementById('inside').firstChild;
          const at = text.data.indexOf('inside the stage hold');
          getSelection().setBaseAndExtent(text, at, text, at + 'inside the stage hold'.length);
        }"""
    )
    page.keyboard.press("c")
    page.wait_for_function(f"() => ({PAINTED})('lf-pending').length > 0")
    page.mouse.move(1, 1)
    words = page.evaluate(PAINTED, "lf-pending")
    page.evaluate(STAGE_AGAIN)
    page.wait_for_timeout(300)
    assert page.evaluate(PAINTED, "lf-pending") == words


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_search_match_whose_end_shows_is_brought_to_its_start(engine, request, serve):
    """A page search's match whose end stands in the window while its start stands
    above it, as one running from the page's words into a declared shadow stage far
    below them, is brought into sight by where its words start."""
    url = serve(
        leaf_page(
            "Across",
            "<p>Before.</p>"
            * 40
            + '<div id="both"><p id="first">The match starts here</p>'
            '<lf-late-stage id="late" style="display: block; margin-block-start: 760px">'
            '<p id="second">and ends inside the stage.</p></lf-late-stage></div>'
            + "<p>After.</p>"
            * 40,
        ),
        layer_registry={"lf-late-stage": VERBATIM_STAGE},
        layer_widgets={"lf-late-stage.js": STAGED_ON_CONNECT},
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.set_viewport_size({"width": 900, "height": 600})
    page.evaluate(
        """() => {
          const late = document.getElementById('late').shadowRoot.getElementById('second');
          scrollBy(0, late.getBoundingClientRect().top - 280);
        }"""
    )
    page.keyboard.press("/")
    page.get_by_role("searchbox", name="Search page text").fill(
        "match starts here and ends inside"
    )
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")
    page.wait_for_timeout(300)
    start = page.evaluate(
        """() => {
          const text = document.getElementById('first').firstChild;
          const range = document.createRange();
          range.setStart(text, 4);
          range.setEnd(text, 9);
          return range.getBoundingClientRect().toJSON();
        }"""
    )
    assert 0 <= start["top"] and start["bottom"] <= 600, start


# A page of four documents in tabs, the first open, each holding "needle" once.
def _needles_in_tabs(serve):
    tabs = "".join(
        f'<lf-tab id="t{i}" label="Doc {i}">'
        f'<lf-text-document id="d{i}" label="doc-{i}.md">'
        f"<pre>A line before.\nneedle {i}\nA line after.\n</pre></lf-text-document></lf-tab>"
        for i in range(4)
    )
    return serve(
        leaf_page("Closed tabs", f'<lf-tabs id="docs" list="side">{tabs}</lf-tabs>')
    )


# The page's clock run fast, so each slice of a page search takes one step.
FAST_CLOCK = """() => {
  const now = performance.now.bind(performance);
  let ahead = 0;
  performance.now = () => now() + (ahead += 20);
}"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_walk_through_search_matches_in_closed_tabs_reaches_each_in_turn(
    engine, request, serve
):
    """Tab walks a search's matches in order across documents in closed tabs. Bringing a
    match into sight opens its tab, which changes the page, so the next step searches
    again; it stands where it stood before stepping, however few matches each of the
    search's slices takes (`FAST_CLOCK`)."""
    page = open_page(request.getfixturevalue(engine), _needles_in_tabs(serve))
    page.keyboard.press("/")
    page.get_by_role("searchbox", name="Search page text").fill("needle")
    status = page.locator(".lf-page-search-status")
    expect(status).to_have_text("1 of 4")
    page.evaluate(FAST_CLOCK)
    for key, position in (("Tab", 2), ("Tab", 3), ("Tab", 4), ("Shift+Tab", 3)):
        page.keyboard.press(key)
        expect(status).to_have_text(re.compile(rf"^{position} of "))
        expect(page.get_by_role("tab", name=f"Doc {position - 1}")).to_have_attribute(
            "aria-selected", "true"
        )
    # Enter selects the match, and `n` goes on from it.
    selected = (
        "(id) => getSelection().anchorNode?.parentElement?.closest('lf-text-document')"
        "?.id === id && String(getSelection()) === 'needle'"
    )
    page.keyboard.press("Enter")
    page.wait_for_function(selected, arg="d2")
    page.keyboard.press("n")
    page.wait_for_function(selected, arg="d3")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_step_back_past_the_first_search_match_stays_while_the_search_runs(
    engine, request, serve
):
    """While a page search still runs, Shift+Tab from its first match would come round to
    a last match the search hasn't found; it stays and says the search is still running,
    rather than holding the page until the search ends, and Tab still goes on to the
    next. Each slice takes one step (`FAST_CLOCK`), and the page's zero-delay timers are
    held, so the search stands unfinished until they run."""
    page = open_page(request.getfixturevalue(engine), _needles_in_tabs(serve))
    page.keyboard.press("/")
    page.evaluate(FAST_CLOCK)
    page.evaluate(
        """() => {
          const run = (window.__run = window.setTimeout);
          window.__held = [];
          window.setTimeout = (f, ms, ...rest) =>
            ms ? run(f, ms, ...rest) : (window.__held.push(() => f(...rest)), 0);
        }"""
    )
    page.get_by_role("searchbox", name="Search page text").fill("needle")
    status = page.locator(".lf-page-search-status")
    # Run the held slices until the search lands on the first match.
    page.evaluate(
        """() => {
          const status = document.querySelector(".lf-page-search-status");
          while (!/ of /.test(status.textContent) && window.__held.length)
            window.__held.shift()();
        }"""
    )
    expect(status).to_have_text("1 of 1")
    page.keyboard.press("Shift+Tab")
    expect(status).to_have_text("1 of 1")
    expect(page.locator(".lf-live")).to_have_text("Searching")
    expect(page.get_by_role("tab", name="Doc 0")).to_have_attribute(
        "aria-selected", "true"
    )
    page.keyboard.press("Tab")
    expect(status).to_have_text("2 of 2")
    page.evaluate(
        """() => {
          window.setTimeout = window.__run;
          for (const run of window.__held.splice(0)) run();
        }"""
    )
    expect(status).to_have_text("2 of 4")


def test_a_step_back_after_the_page_changed_keeps_the_match_it_stood_on(browser, serve):
    """After Enter closes the search and the page changes, Shift+n searches again from
    the match it selected. While that search still runs, a step back from the first
    match stays and says "Searching", and the search's first slice landing on the first
    match in the window moves nothing: once the search ends, Shift+n comes round from
    the first match to the last. The page's zero-delay timers are held so the search
    stands unfinished, and its first slice takes a dozen steps (`__steps`)."""
    lines = "\n".join(f"Line {n}." for n in range(60))
    documents = "".join(
        f'<lf-text-document id="d{i}" label="doc-{i}.md">'
        f"<pre>needle {i}\n{lines}\n</pre></lf-text-document>"
        for i in range(10)
    )
    page = open_page(browser, serve(leaf_page("Documents", documents)))
    page.keyboard.press("/")
    page.get_by_role("searchbox", name="Search page text").fill("needle")
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 10")
    page.keyboard.press("Enter")
    selected = (
        "(id) => getSelection().anchorNode?.parentElement?.closest('lf-text-document')"
        "?.id === id && String(getSelection()) === 'needle'"
    )
    page.wait_for_function(selected, arg="d0")
    page.evaluate(
        """() => {
          document.getElementById("d1").scrollIntoView({ block: "start" });
          const now = performance.now.bind(performance);
          performance.now = () =>
            window.__steps === undefined || window.__steps-- > 0 ? now() : now() + 1e9;
          const run = (window.__run = window.setTimeout);
          window.__held = [];
          window.setTimeout = (f, ms, ...rest) =>
            ms ? run(f, ms, ...rest) : (window.__held.push(() => f(...rest)), 0);
          const note = document.createElement("p");
          note.textContent = "A paragraph the agent added.";
          document.querySelector("main").append(note);
          window.__steps = 12;
        }"""
    )
    page.keyboard.press("Shift+n")
    expect(page.locator(".lf-live")).to_have_text("Searching")
    page.evaluate(
        """() => {
          window.setTimeout = window.__run;
          delete window.__steps;
          for (const run of window.__held.splice(0)) run();
        }"""
    )
    page.keyboard.press("Shift+n")
    page.wait_for_function(selected, arg="d9")


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_travel_to_a_thread_on_a_tall_passage_shows_where_it_starts(
    engine, request, serve
):
    """The thread walk to a thread whose passage is taller than the window, from a place
    where only the passage's middle shows, brings its start into sight."""
    words = " ".join(f"Sentence {n} of the long passage runs on." for n in range(400))
    url = serve(
        leaf_page(
            "Tall",
            "<p>Before.</p>" * 10 + f'<p id="tall">{words}</p>' + "<p>After.</p>" * 10,
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "About all of it?",
            "anchor": {"section": "tall", "quote": words},
        },
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.set_viewport_size({"width": 1200, "height": 500})
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) === 1")
    page.evaluate(
        """() => {
          const tall = document.getElementById('tall').getBoundingClientRect();
          scrollBy(0, tall.top + tall.height / 2 - 250);
        }"""
    )
    page.keyboard.press("t")
    page.wait_for_timeout(600)
    start = page.evaluate(
        """() => {
          const text = document.getElementById('tall').firstChild;
          const range = document.createRange();
          range.setStart(text, 0);
          range.setEnd(text, 8);
          return range.getBoundingClientRect().toJSON();
        }"""
    )
    assert 0 <= start["top"] and start["bottom"] <= 500, start


@pytest.mark.parametrize(
    ("before", "words", "quote"),
    [
        (
            680,
            '<p style="writing-mode: vertical-rl; height: 400px; width: 120px">A '
            "passage whose words run down several columns before they reach the end, "
            "with a further sentence to fill them.</p>",
            "A passage whose words run down several columns before they reach the end,"
            " with a further sentence to fill them.",
        ),
        (
            680,
            '<p style="writing-mode: vertical-rl; height: 400px; width: 120px">'
            "<span>A</span> passage whose words run down several columns before they "
            "reach the end, with a further sentence to fill them.</p>",
            "A passage whose words run down several columns before they reach the end,"
            " with a further sentence to fill them.",
        ),
        (
            1600,
            '<p><span style="display: none">Hidden beginning </span>Visible passage '
            "ending for the reader.</p>",
            "Hidden beginning Visible passage ending for the reader.",
        ),
    ],
    ids=["vertical", "vertical-across-nodes", "hidden-start"],
)
@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_travel_to_a_thread_shows_the_first_line_its_passage_draws(
    engine, before, words, quote, request, serve
):
    """The thread walk brings into sight the first line its passage draws: in vertical
    writing, the whole of its first column, though its first word already shows and
    though the column runs across text nodes, and where its first words draw no box,
    the line its first drawn words stand on."""
    url = serve(
        leaf_page(
            "First line",
            f'<p style="height: {before}px">Before.</p>'
            f'<section id="target">{words}</section>'
            '<p style="height: 1600px">After.</p>',
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "About this?",
            "anchor": {"section": "target", "quote": quote},
        },
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.set_viewport_size({"width": 1200, "height": 900})
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 1")
    page.keyboard.press("t")
    page.wait_for_timeout(600)
    box = page.locator("#target p").bounding_box()
    assert 0 <= box["y"] and box["y"] + box["height"] <= 900, box


# A widget whose words read as the page's prose (`x-verbatim`), staged in a declared
# shadow tree as it connects.
VERBATIM_STAGE = {**LATE_STAGE, "x-verbatim": True}
STAGED_ON_CONNECT = """
import {shadowStage} from '/runtime/widget-api.js';
customElements.define('lf-late-stage', class extends HTMLElement {
  connectedCallback() { shadowStage(this, [...this.childNodes]); }
});
"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_passage_running_into_a_shadow_tree_previews_by_the_line_pointed_at(
    engine, request, serve
):
    """A passage that runs from the page's words into a declared shadow tree is drawn in
    its segments' own lines, since one range can't cross a root: its preview stands by
    the line the pointer rests on, in the page's words, rather than where a range
    across the root collapsed, at the passage's end inside the shadow tree."""
    url = serve(
        leaf_page(
            "Across a root",
            '<div id="both"><p>The first line of the passage ends here.</p>'
            '<lf-late-stage id="late"><p>Its second line stands inside the widget.</p>'
            "</lf-late-stage></div>" + "<p>After.</p>" * 12,
        ),
        layer_registry={"lf-late-stage": VERBATIM_STAGE},
        layer_widgets={"lf-late-stage.js": STAGED_ON_CONNECT},
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Across the root?",
            "anchor": {
                "section": "both",
                "quote": "passage ends here. Its second line",
            },
        },
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) === 2")
    line = page.evaluate(
        """() => {
          const text = document.querySelector('#both > p').firstChild;
          const at = text.data.indexOf('passage ends');
          const range = document.createRange();
          range.setStart(text, at);
          range.setEnd(text, at + 'passage ends'.length);
          return range.getBoundingClientRect().toJSON();
        }"""
    )
    page.mouse.move(line["left"] - 30, line["top"] - 30)
    page.mouse.move(line["left"] + 6, line["top"] + line["height"] / 2, steps=3)
    tip = page.locator("#lf-preview")
    expect(tip.locator(".lf-preview-word")).to_have_text("Across the root?")
    box = tip.bounding_box()
    below = 0 <= box["y"] - line["bottom"] <= 12
    above = 0 <= line["top"] - (box["y"] + box["height"]) <= 12
    assert below or above, (box, line)
    assert abs(box["x"] - line["left"]) <= 12, (box, line)


@pytest.mark.parametrize("staged", [False, True], ids=["page", "shadow"])
@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_search_match_across_blocks_marks_and_selects_each_piece(
    engine, staged, request, serve
):
    """A page search's match that runs from one paragraph into the next, in the page's
    tree or into a declared shadow stage, stands a mark over each piece's words, clipped
    by that piece's own block, and landing on it selects every piece."""
    second = '<p id="second">passage inside the stage.</p>'
    url = serve(
        leaf_page(
            "Across",
            '<div id="both"><p id="first">Words before shadow</p>'
            + (
                f'<lf-late-stage id="late">{second}</lf-late-stage>'
                if staged
                else second
            )
            + "</div>"
            + "<p>After.</p>" * 6,
        ),
        layer_registry={"lf-late-stage": VERBATIM_STAGE},
        layer_widgets={"lf-late-stage.js": STAGED_ON_CONNECT},
    )
    page = open_page(request.getfixturevalue(engine), url)
    page.keyboard.press("/")
    page.keyboard.type("before shadow passage inside")
    expect(page.locator(".lf-page-search-status")).to_have_text("1 of 1")
    # The input draws the count at once, but the marks in the next repaint frame;
    # until then they stand where an earlier query's frame put them.
    rendered(page)
    boxes = page.evaluate(
        """() => {
          const late = document.getElementById('late');
          const second = (late?.shadowRoot ?? document).getElementById('second');
          const blocks = [document.getElementById('first'), second]
            .map((block) => block.getBoundingClientRect());
          const marks = [...document.querySelectorAll('.lf-page-search-match')]
            .map((mark) => mark.getBoundingClientRect())
            .filter((box) => box.width && box.height);
          return blocks.map((block) => marks.filter((box) =>
            box.top >= block.top - 1 && box.bottom <= block.bottom + 1).length);
        }"""
    )
    assert boxes[0] >= 1 and boxes[1] >= 1, boxes
    page.keyboard.press("Enter")
    selected = page.evaluate(
        """() => {
          const late = document.getElementById('late');
          const roots = late?.shadowRoot ? [late.shadowRoot] : [];
          const [range] = getSelection().getComposedRanges({shadowRoots: roots});
          return range && [range.startContainer.parentElement.id, range.startOffset,
            range.endContainer.parentElement.id, range.endOffset];
        }"""
    )
    assert selected == ["first", 6, "second", 14], selected


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_an_element_s_mark_is_under_the_pointer_only_over_the_element(
    engine, request, serve
):
    """A thread on an element is under the pointer wherever the platform's hit test puts
    the pointer inside that element, as over an image, which holds no text to find, and
    nowhere past it, as beside a marked word at a line's end, where the nearest
    character is still the word's. The mark under the pointer for a press is the one
    that previews: the image's thread to a pointer resting on it, and in Chromium to a
    finger holding it."""
    box = (
        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' "
        "height='80'%3E%3Crect width='160' height='80' fill='%23a55'/%3E%3C/svg%3E"
    )
    url = serve(
        leaf_page(
            "Element marks",
            f'<p id="holder"><img id="pic" alt="A red box" src="{box}" width="160" '
            'height="80"> beside words.</p>'
            '<p id="line">A short line ending in <strong id="bold">bold</strong></p>',
        )
    )
    for section in ("pic", "bold"):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"About {section}?",
                "anchor": {"section": section},
            },
        )
    browser = request.getfixturevalue(engine)
    page = open_page(browser, url)
    said = page.locator("#lf-preview .lf-preview-word")
    pic = page.locator("#pic").bounding_box()
    bold = page.locator("#bold").bounding_box()
    middle = bold["y"] + bold["height"] / 2
    page.mouse.move(pic["x"] + 40, pic["y"] + 40)
    page.mouse.move(pic["x"] + 60, pic["y"] + 50, steps=2)
    expect(page.locator("[data-lf-over-mark]")).to_have_count(1)
    expect(said).to_have_text("About pic?")
    page.mouse.move(bold["x"] + bold["width"] + 35, middle, steps=2)
    expect(page.locator("[data-lf-over-mark]")).to_have_count(0)
    expect(page.locator("#lf-preview")).to_be_hidden()
    page.mouse.move(bold["x"] + bold["width"] / 2, middle, steps=2)
    expect(page.locator("[data-lf-over-mark]")).to_have_count(1)
    expect(said).to_have_text("About bold?")
    if engine != "browser":
        return
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, has_touch=True
    )
    touched = open_page(browser, url, context=context)
    held = touched.locator("#pic").bounding_box()
    point = {"x": held["x"] + 60, "y": held["y"] + 50}
    cdp = context.new_cdp_session(touched)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [point]})
    long_press(touched, point)
    expect(touched.locator("#lf-preview .lf-preview-word")).to_have_text("About pic?")
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
