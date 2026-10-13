"""Comment marks, Go-to addresses, and keyboard navigation tests."""

import io
import re

import pytest
from interact_support import append_carried_log_record
from leaf import event_log as events_model
from leaf import server as server_model
from leaf.render_checks import rendered, wait_until_ready
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import (
    ASKS_PAGE,
    PANEL_PAGE,
    WORKSHOP_THREAD_EVENTS,
    WORKSHOP_THREADS_PAGE,
    answered_comment,
    live_url,
    panel_comment,
)
from render_cases_layout import (
    page_at_rest,
)
from render_cases_navigation import (
    ADDRESSED_PAGE,
    CHIPS,
    _publish,
    address_code,
    address_codes,
    go_to_address,
)
from render_harness import (
    CORPUS_SOURCES,
    EXAMPLES,
    INLINE_PAGE,
    LONG_PAGE,
    RELEASE_FOCUS,
    ROOT,
    command_reference_rows,
    expect_asks_answered,
    expect_comment_notes,
    leaf_page,
    navigate,
    open_page,
    opened_tab,
    pane_posture,
    panel_settled,
    resized,
    round_trip,
    scroll_settled,
    sending,
    shortcut_bar_text,
    told,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_navigation import (
    EXPANDED,
    KEY_LINE_HINTS,
    QUICK_KEYS_PAGE,
    READING_REGIONS_PAGE,
    STANDING,
    color_cue_markup,
)


def test_a_let_go_keeps_the_user_in_the_pane_they_read(browser, serve):
    """A let-go lands on what the user is reading in the page region they last acted
    in. Opening Threads over a pane once replaced that region with the panel's list, so
    closing it landed on the workspace header; and a pane showing no words where it
    stood (a figure, a spacer) had no block to land on, so the user was dropped on the
    body and the pane forgotten. Either way `d` and `u` stopped moving the pane.

    A pane that flows inside a scrolling workspace body keeps answering after it scrolls
    out of the window, which a test of the pane's own visibility must not mistake for a
    closed surface."""
    tops = """() => ['left-reading', 'right-reading'].map((id) =>
      document.querySelector(`#${id} > :not(header, footer)`).scrollTop)"""
    reading = """async () => (await window.__lfRuntimeImport(
      '/runtime/reading-regions.js')).userReadingRegion()?.host.id ?? null"""
    page = open_page(browser, serve(READING_REGIONS_PAGE))
    resized(page, 1440, 900)
    pane_posture(page, page.locator("#left-reading"), "bounded")

    page.locator("#right-head").focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    assert page.evaluate(reading) == "right-reading"
    page.keyboard.press("d")
    page.wait_for_function(f"() => ({tops})()[1] > 0")

    page.locator("#left-reading > :not(header, footer)").evaluate(
        "body => body.scrollTop = 400"
    )
    page.locator("#left-head").focus()
    page.keyboard.press("Escape")
    assert page.evaluate(reading) == "left-reading"
    page.keyboard.press("u")
    page.wait_for_function(f"() => ({tops})()[0] < 400")

    flowing = READING_REGIONS_PAGE.replace(
        '<lf-pane id="left-reading"', '<section><lf-pane id="left-reading"'
    ).replace("    </lf-pane>\n  </div>", "    </lf-pane></section>\n  </div>")
    assert flowing.count("</section>") == 1
    page = open_page(browser, serve(flowing))
    resized(page, 1440, 900)
    split = page.locator("#reading-split")
    page.locator("#left-start").click()
    for _ in range(12):
        page.keyboard.press("d")
        page.wait_for_timeout(200)
    assert (
        split.evaluate("box => box.scrollHeight - box.clientHeight - box.scrollTop") < 2
    )
    # The pane it remembers has scrolled out of view, so a landing reads the body
    # carrying it, which shows the other pane, rather than going back for the first.
    bottom = split.evaluate("box => box.scrollTop")
    page.keyboard.press("g")
    page.keyboard.press("p")
    page.keyboard.press("Tab")
    expect(page.locator("#right-subject")).to_be_focused()
    assert split.evaluate("box => box.scrollTop") == bottom


def test_reading_keys_scroll_drawers_without_moving_the_document(
    browser, serve, live_leaf
):
    """Drawer reading follows its list in covering and beside postures, including
    focus in its header; neither end spills scrolling into the document."""
    live_leaf("second", "A second leaf")
    page = open_page(browser, serve(ASKS_PAGE))
    for width in (390, 1280):
        resized(page, width, 700)
        for key, selector in (
            ("Shift+l", ".lf-others-panel"),
            ("Shift+q", ".lf-queue-panel"),
        ):
            page.keyboard.press("g")
            page.keyboard.press(key)
            panel = page.locator(selector)
            expect(panel).to_be_visible()
            box = panel.locator(".lf-drawer-list")
            # Make the real drawer overflow without starting dozens of neighboring
            # page servers. Its normal rows and navigation remain in place.
            box.evaluate(
                "box => { const filler = document.createElement('div'); "
                "filler.style.height = '2200px'; box.append(filler); }"
            )
            assert box.evaluate("box => box.scrollHeight > box.clientHeight")
            panel.get_by_role("button", name=re.compile("^Close ")).focus()
            # A drawer opening beside the page narrows it, and the page keeps its
            # reading place on the frame after that layout: read it once it rests.
            rendered(page)
            document_position = page.evaluate("document.scrollingElement.scrollTop")
            for down, up in (("d", "u"), ("j", "k")):
                box.evaluate("box => box.scrollTop = 0")
                page.keyboard.press(down)
                page.wait_for_function(
                    "selector => document.querySelector(selector).scrollTop > 0",
                    arg=selector + " .lf-drawer-list",
                )
                scroll_settled(page, selector + " .lf-drawer-list")
                before = box.evaluate("box => box.scrollTop")
                page.keyboard.press(up)
                page.wait_for_function(
                    "({selector, before}) => document.querySelector(selector).scrollTop < before",
                    arg={"selector": selector + " .lf-drawer-list", "before": before},
                )
                scroll_settled(page, selector + " .lf-drawer-list")
                box.evaluate("box => box.scrollTop = box.scrollHeight")
                page.keyboard.press(down)
                scroll_settled(page, selector + " .lf-drawer-list")
                assert (
                    page.evaluate("document.scrollingElement.scrollTop")
                    == document_position
                )
            page.keyboard.press("Escape")
            expect(panel).to_be_hidden()


def test_a_comment_box_moves_home_when_a_panel_comes_to_cover_its_seat(browser, serve):
    """The panels dominate what focus reaches (Max, 2026-10-06). A comment box whose
    seat the Threads panel comes to stand over moves to its home in the panel's foot,
    keeping its words, rather than staying hidden under the panel."""
    walkthrough = next(p for p in EXAMPLES if p.stem == "pr-walkthrough")
    page = open_page(browser, serve(walkthrough))
    resized(page, 1440, 900)
    panel = page.get_by_role("dialog", name="Threads", exact=True)
    opener = page.locator("#pr-exact-patch .lf-diff-file-comment").first
    opener.scroll_into_view_if_needed()
    opener.click()
    page.keyboard.type("draft words")
    box = page.locator("leaf-text.lf-fab-input")
    expect(page.locator("#pr-exact-patch leaf-text.lf-fab-input")).to_be_focused()
    page.locator(".lf-threads-toggle").click()
    # The dialog envelope draws nothing (#2613); its Threads panel is what shows.
    expect(panel).to_have_attribute("open", "")
    expect(panel.locator(".lf-thread-panel")).to_be_visible()
    page_at_rest(page)
    edge = page.locator(".lf-thread-panel > .lf-edge").bounding_box()
    middle = edge["y"] + edge["height"] / 2
    page.mouse.move(edge["x"] + edge["width"] / 2, middle)
    page.mouse.down()
    # Slowly, so the box moves home and back toward its seat on frames between.
    page.mouse.move(440, middle, steps=30)
    page.mouse.up()
    page_at_rest(page)
    assert page.locator("#pr-exact-patch leaf-text.lf-fab-input").count() == 0
    assert box.evaluate("box => box.value") == "draft words"
    assert box.evaluate(
        "box => box.getBoundingClientRect().right <="
        " document.querySelector('.lf-thread-panel').getBoundingClientRect().left"
    )


def test_review_queue_decisions_replay_and_reach_the_next_revision_from_the_keyboard(
    browser, serve
):
    example = next(e for e in CORPUS_SOURCES if e.stem == "review-queue")

    seeded = serve(example)
    first = seeded.replace("/versions/v2.html", "/versions/v1.html")
    page = open_page(browser, first)
    expect_asks_answered(page, "2/2")
    expect(page.locator("#review-cache-auto")).to_have_attribute("chosen", "")
    expect(page.locator("#review-billing-legacy")).to_have_attribute("chosen", "")
    page.close()

    newest = serve(example, seed_log=False)
    first = newest.replace("/versions/v2.html", "/versions/v1.html")
    page = open_page(browser, first)
    expect_asks_answered(page, "0/2")
    expect(page.locator("#review-cache-auto")).not_to_have_attribute("chosen", "")
    expect(page.locator("#review-billing-legacy")).not_to_have_attribute("chosen", "")
    expect(page.locator("#review-cache")).to_contain_text(
        "A failed copy leaves the old keys authoritative"
    )
    expect(page.locator("#review-billing-difference h4")).to_have_text(
        "Open difference"
    )
    footer = page.locator("#review-detail > footer")
    expect(footer).to_contain_text("This revision asks two release-blocking questions")
    expect(footer).to_contain_text(
        "submitted answers are incorporated in the next revision"
    )

    page.keyboard.press("q")
    expect(page.locator("#review-cache-decision")).to_be_focused()
    with sending(page, "the cache rollback decision"):
        page.keyboard.press("1")
    expect(page.locator("#review-cache-auto")).to_have_attribute("chosen", "")

    page.keyboard.press("q")
    expect(page.locator("#review-billing-decision")).to_be_focused()
    with sending(page, "the billing reconciliation decision"):
        page.keyboard.press("1")
    expect_asks_answered(page, "2/2")
    expect(footer).to_contain_text("This revision asks two release-blocking questions")

    page.goto(live_url(newest))
    rendered(page)
    expect(page.locator(".lf-version")).to_have_text("Showing v2")
    expect(page.locator("#review-cache-auto")).to_have_attribute("chosen", "")
    expect(page.locator("#review-billing-legacy")).to_have_attribute("chosen", "")
    expect(page.locator("#review-cache")).to_contain_text(
        "returns readers to the old keys automatically"
    )
    expect(page.locator("#review-billing-difference h4")).to_have_text(
        "Legacy difference stays on its reporting path"
    )
    expect(page.locator("#review-detail > footer")).to_contain_text(
        "This revision incorporates both answers"
    )
    # The revision settles both questions; the ask inventory retains answers
    # after an authored revision settles their sources (`asks.py`).
    expect_asks_answered(page, "2/2")

    actions = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert [event["detail"]["value"] for event in actions] == [
        ["review-cache-auto"],
        ["review-billing-legacy"],
    ]


def test_each_comparison_result_keeps_its_own_comment_destination(browser, serve):
    """Each policy owns a separate anchor and pane-local return route."""
    example = next(e for e in CORPUS_SOURCES if e.stem == "current-proposed-comparison")
    page = open_page(
        browser,
        serve(
            example,
            anchored=[
                (
                    "comparison-current-behavior",
                    "starts its own credential refresh",
                ),
                (
                    "comparison-proposed-behavior",
                    "Other calls in that tab wait for it",
                ),
            ],
        ),
    )
    resized(page, 1600, 700)
    # Open Threads first: the panel narrows the page, and the panes' reflow is not the
    # travel under test.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    pane_posture(page, page.locator("#comparison-current"), "bounded")
    current = page.locator("#comparison-current > :not(header, footer)")
    proposed = page.locator("#comparison-proposed > :not(header, footer)")
    expect(page.locator(".lf-mark-note")).to_have_count(2)
    expect_comment_notes(page, "#comparison-current", 1)
    expect_comment_notes(page, "#comparison-proposed", 1)
    initial_scrolls = page.evaluate("""() => {
        const panes = ["comparison-current", "comparison-proposed"].map(id =>
            document.querySelector(`#${id} > :not(header, footer)`));
        for (const pane of panes) pane.scrollTop = pane.scrollHeight;
        return panes.map(pane => pane.scrollTop);
    }""")
    assert min(initial_scrolls) > 0

    page.locator(".lf-thread", has_text="starts its own credential refresh").locator(
        ".lf-thread-summary"
    ).click()
    page.locator(".lf-thread", has_text="starts its own credential refresh").locator(
        ".lf-quote"
    ).click()
    expect(page.locator("#comparison-current-behavior")).to_be_in_viewport()
    scroll_settled(page, "#comparison-current > :not(header, footer)")
    current_after_current = current.evaluate("el => el.scrollTop")
    proposed_after_current = proposed.evaluate("el => el.scrollTop")
    assert current_after_current < initial_scrolls[0]
    assert proposed_after_current == initial_scrolls[1]

    page.locator(".lf-thread", has_text="Other calls in that tab wait for it").locator(
        ".lf-thread-summary"
    ).click()
    page.locator(".lf-thread", has_text="Other calls in that tab wait for it").locator(
        ".lf-quote"
    ).click()
    expect(page.locator("#comparison-proposed-behavior")).to_be_in_viewport()
    scroll_settled(page, "#comparison-proposed > :not(header, footer)")
    assert proposed.evaluate("el => el.scrollTop") < proposed_after_current
    assert current.evaluate("el => el.scrollTop") == current_after_current


def test_comparison_choice_replays_and_is_applied_by_the_next_revision(browser, serve):
    """One v1 choice remains authoritative in the v2 policy and rollout."""
    example = next(e for e in CORPUS_SOURCES if e.stem == "current-proposed-comparison")

    seeded = serve(example)
    first = seeded.replace("/versions/v2.html", "/versions/v1.html")
    page = open_page(browser, first)
    expect_asks_answered(page, "1/1")
    expect(page.locator("#comparison-policy-shared")).to_have_attribute("chosen", "")
    page.close()

    newest = serve(example, seed_log=False)
    first = newest.replace("/versions/v2.html", "/versions/v1.html")
    page = open_page(browser, first)
    expect_asks_answered(page, "0/1")
    expect(page.locator("#comparison-policy-shared")).not_to_have_attribute(
        "chosen", ""
    )

    page.keyboard.press("q")
    expect(page.locator("#comparison-policy-decision")).to_be_focused()
    with sending(page, "the authentication retry policy decision"):
        page.keyboard.press("2")
    expect(page.locator("#comparison-policy-shared")).to_have_attribute("chosen", "")

    page.goto(live_url(newest))
    rendered(page)
    expect(page.locator(".lf-version")).to_have_text("Showing v2")
    expect(page.locator("#comparison-policy-shared")).to_have_attribute("chosen", "")
    expect(page.locator("#comparison-proposed > header")).to_contain_text("selected")
    expect(page.locator("#comparison-rollout")).to_contain_text(
        "enables shared refreshes for web clients"
    )
    expect(page.locator("#comparison-policy")).to_have_attribute("settled", "")
    # The Ask reading keeps an Ask the user answered after a later version settles it
    # (`asks.py`, the retained answered inventory).
    expect_asks_answered(page, "1/1")

    actions = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert [event["detail"]["value"] for event in actions] == [
        ["comparison-policy-shared"]
    ]


@pytest.mark.parametrize("viewport", [(1440, 900), (390, 844)])
def test_pr_walkthrough_navigation_starts_the_review_at_every_width(
    browser, serve, viewport
):
    """Contents must be available before the reader works through this long review.

    The former sidebar placed the outline after the complete PR facts and history;
    when the tracks stacked, it also came after the entire article. The authored
    reading order now puts navigation first and supporting evidence in the article.
    """
    source = next(example for example in EXAMPLES if example.stem == "pr-walkthrough")
    url = serve(source)
    width, height = viewport
    context = browser.new_context(
        viewport={"width": width, "height": height},
        has_touch=width < 500,
        is_mobile=width < 500,
    )
    page = open_page(browser, url, context=context)
    page.evaluate("() => document.fonts.ready")
    navigation = page.locator("#pr-contents")
    first = navigation.get_by_role("link", name="Review finding", exact=True)
    expect(first).to_be_in_viewport()
    if width < 500:
        assert (
            page.locator("#pr-contents-panel").bounding_box()["y"]
            < (page.locator("#pr-body").bounding_box()["y"])
        )

    # A real pointer press leaves the reader at a later section, with its heading
    # visible rather than under page chrome. On desktop the same outline persists.
    change = navigation.get_by_role("link", name="Change surface", exact=True)
    expect(change).to_be_in_viewport()
    change.click()
    expect(page).to_have_url(re.compile(r"#pr-change-surface$"))
    heading = page.locator("#pr-change-surface > h2")
    expect(heading).to_be_in_viewport()
    scroll_settled(page)
    assert (
        heading.bounding_box()["y"]
        >= page.locator(".lf-banner").bounding_box()["height"]
    )
    if width > 500:
        expect(first).to_be_in_viewport()

    # Begin again at the opening, and take the native tab order to another route.
    navigate(page, url)
    page.evaluate(RELEASE_FOCUS)
    invariant = navigation.get_by_role("link", name="Review invariants", exact=True)
    for _ in range(30):
        page.keyboard.press("Tab")
        if invariant.evaluate("node => node.matches(':focus')"):
            break
    expect(invariant).to_be_focused()
    assert invariant.evaluate("node => node.matches(':focus-visible')")
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"#pr-invariants$"))
    expect(page.locator("#pr-invariants > h2")).to_be_in_viewport()
    scroll_settled(page)
    if width > 500:
        expect(first).to_be_in_viewport()


def test_the_pr_walkthrough_exercises_an_inline_diff_thread(browser, serve):
    """The diff package's worked page carries a real line thread through both seats."""
    source = next(example for example in EXAMPLES if example.stem == "pr-walkthrough")
    url = live_url(serve(source))
    page = open_page(browser, url)
    diff = page.locator("#pr-exact-patch")
    details = diff.locator(".lf-diff-file > details").first
    details.evaluate("element => { element.open = true; }")
    target = details.locator("[data-line-type='change-addition'][data-lf-datum]").first
    root = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Keep this review note beside the line that changes it.",
            "anchor": {
                "section": "pr-exact-patch",
                "datum": target.get_attribute("data-lf-datum"),
                "source": target.get_attribute("data-lf-source"),
                "source_revision": target.get_attribute("data-lf-source-revision"),
            },
        },
    )
    told(page)
    thread = diff.locator(f'.lf-page-thread[data-thread="{root["id"]}"]')
    expect(thread).to_contain_text(
        "Keep this review note beside the line that changes it."
    )
    send = thread.locator(".lf-compose-submit")
    expect(send).to_be_disabled()
    expect(thread.locator(".lf-compose-field > button:visible")).to_have_count(1)
    markers = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    baseline = markers.count()

    details.evaluate("element => { element.open = false; }")
    expect(thread).to_have_count(0)
    expect(markers).to_have_count(baseline + 1)
    details.evaluate("element => { element.open = true; }")
    expect(thread).to_have_count(1)
    expect(markers).to_have_count(baseline)

    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()

    # A thread the margin projects, standing before the diff in page order: the walk
    # opens the margin's view to reach it and then steps on to the diff's own seat,
    # closing that view on the way. The walk moves the user laterally rather than down
    # a level, so Escape lets go of the thread they ended on and lands them in the page
    # where they now are — not back at the heading the walk started from, which is
    # off screen by then.
    prose = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "And one on the prose above the patch.",
            "anchor": {"section": "pr-scale-intro", "quote": "Risk is concentrated"},
        },
    )
    told(page)
    heading = page.locator("main h2").first
    heading.evaluate("el => { el.tabIndex = -1; el.focus(); }")
    expect(heading).to_be_focused()
    page.keyboard.press("t")
    expect(
        page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{prose["id"]}"]')
    ).to_be_focused()
    page.keyboard.press("t")
    expect(thread).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")


def test_thread_navigation_lands_after_resizing_an_open_reply(browser, serve):
    """A fixed card cannot reveal itself by scrolling its already-visible passage away."""
    page = open_page(
        browser,
        live_url(serve(WORKSHOP_THREADS_PAGE, events=WORKSHOP_THREAD_EVENTS)),
    )
    resized(page, 1280, 720)
    card = page.locator(".lf-margin-preview")
    thread = card.get_by_role("group", name="Thread, Is lunch provided", exact=False)
    # The walk reaches the lunch thread wherever the walk's order puts it.
    for _ in range(3):
        page.keyboard.press("t")
        scroll_settled(page)
        if thread.count() and thread.evaluate("el => el === document.activeElement"):
            break
    expect(thread).to_be_focused()
    page.keyboard.press("t")
    expect(
        card.get_by_role("group", name="Thread, Workshop room photo")
    ).to_be_focused()
    scroll_settled(page)
    page.keyboard.press("Enter")
    expect(page.get_by_role("textbox", name="Reply", exact=True)).to_be_focused()
    resized(page, 390, 844)
    scroll_settled(page)
    page.keyboard.press("Escape")
    page.keyboard.press("Shift+t")
    expect(thread).to_be_focused()
    scroll_settled(page)
    expect(thread).to_be_in_viewport(ratio=1)
    page.keyboard.press("c")
    reply = page.get_by_role("textbox", name="Reply", exact=True)
    expect(reply).to_be_focused()
    scroll_settled(page)
    expect(reply).to_be_in_viewport(ratio=1)


def test_a_thread_walk_card_leaves_and_returns_with_its_anchor(browser, serve):
    """A contextual thread has one side, and leaves and returns with its anchor."""
    page = open_page(
        browser,
        live_url(serve(WORKSHOP_THREADS_PAGE, events=WORKSHOP_THREAD_EVENTS)),
    )
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1440, 900)

    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("t")
    card = page.locator(".lf-margin-preview")
    # Whichever thread the walk reaches first; the page's order decides that.
    expect(card.locator(".lf-page-thread")).to_be_focused()
    walked = card.locator(".lf-page-thread").get_attribute("data-thread")
    owner = page.locator(
        '.lf-margin-marker[data-lf-kinds~="comment"]'
        '[aria-controls="lf-margin-preview"][aria-expanded="true"]:not([hidden])'
    ).locator("xpath=..")
    expect(owner).to_be_visible()
    expect(card).to_have_attribute("data-lf-thread-placement", "right")

    initial = owner.bounding_box()
    assert initial["y"] + initial["height"] > 50
    assert initial["y"] < 900
    page.evaluate("distance => scrollBy(0, distance)", min(160, initial["y"] - 80))
    page.wait_for_function(
        """() => {
          const owner = document.querySelector(
            '.lf-margin-marker[data-lf-kinds~="comment"]' +
            '[aria-controls="lf-margin-preview"][aria-expanded="true"]:not([hidden])'
          )?.parentElement?.getBoundingClientRect();
          return owner && owner.bottom > 50 && owner.top < innerHeight;
        }"""
    )
    expect(card).to_be_visible()
    expect(card).to_have_attribute("data-lf-thread-placement", "right")

    # Scrolled away, the card leaves with its anchor rather than closing, and scrolled
    # back it stands where it stood, with the user still in it.
    rendered(page)
    placed = card.evaluate("node => node.getBoundingClientRect().top")
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    page.evaluate("() => scrollTo(0, document.scrollingElement.scrollHeight)")
    rendered(page)
    assert card.evaluate(
        "node => node.getBoundingClientRect().bottom"
        " <= document.querySelector('.lf-banner').getBoundingClientRect().bottom"
    )
    page.evaluate("top => scrollTo(0, top)", before)
    rendered(page)
    assert card.evaluate("node => node.getBoundingClientRect().top") == pytest.approx(
        placed, abs=0.5
    )
    expect(card.locator(f'.lf-page-thread[data-thread="{walked}"]')).to_be_focused()
    # A press the page answers leaves the window where the user put it: `g G` carries the
    # card away, and `g` then opens Go-to over the page's foot rather than bringing the
    # card back and mapping the window around it.
    page.keyboard.press("g")
    page.keyboard.press("Shift+g")
    rendered(page)
    foot = page.evaluate("() => document.scrollingElement.scrollTop")
    assert card.evaluate(
        "node => node.getBoundingClientRect().bottom"
        " <= document.querySelector('.lf-banner').getBoundingClientRect().bottom"
    )
    page.keyboard.press("g")
    expect(page.locator("body")).to_have_attribute("data-lf-go-to-active", "")
    rendered(page)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == foot
    # Every key is Go-to's while it stands, one it has no use for included: that key
    # takes Go-to down and keeps the page where it is.
    page.keyboard.press("F2")
    expect(page.locator("body")).not_to_have_attribute("data-lf-go-to-active", "")
    rendered(page)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == foot
    # A turn arriving in the card is news, not a move of the user's: it stays away.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": walked,
            "revision": 1,
            "text": "A turn arriving while the card is away.",
        },
    )
    told(page)
    expect(card).to_contain_text("A turn arriving while the card is away.")
    rendered(page)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == foot
    shown = """() => {
      const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
      const head = document.querySelector('.lf-banner').getBoundingClientRect().bottom;
      return card.top >= head && card.bottom <= innerHeight;
    }"""
    # A page command that lands in a card scrolled away brings its cluster, and the
    # card, back.
    page.keyboard.press("c")
    reply = card.get_by_role("textbox", name="Reply", exact=True)
    expect(reply).to_be_focused()
    page.wait_for_function(shown)
    # So does moving on from one of its controls to the next, as the browser reveals
    # the control a Tab reaches.
    page.evaluate("() => scrollTo(0, document.scrollingElement.scrollHeight)")
    rendered(page)
    assert not page.evaluate(shown)
    page.keyboard.press("Tab")
    expect(reply).not_to_be_focused()
    assert page.evaluate(
        "() => document.activeElement.closest('.lf-margin-preview') !== null"
    )
    page.wait_for_function(shown)
    # A card the page has carried half under the banner, Reply with it, is as unseen
    # there as one scrolled off: a landing in it brings it back all the same.
    reply.evaluate(
        """async (box) => {
          const head = document.querySelector('.lf-banner').getBoundingClientRect().bottom;
          const frame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
          while (box.getBoundingClientRect().top >= head) {
            scrollBy(0, 10);
            await frame();
          }
        }"""
    )
    rendered(page)
    assert page.evaluate(
        "() => document.querySelector('.lf-margin-preview').getBoundingClientRect().bottom"
        " > document.querySelector('.lf-banner').getBoundingClientRect().bottom"
    )
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    page.wait_for_function(shown)


def test_an_external_link_says_and_opens_where_it_goes(
    browser, serve, other_leaf, one_user
):
    other_url, _ = other_leaf
    destination = f"{other_url}/?t={server_model.host_key()}"
    url = serve(
        leaf_page(
            "external link",
            f"""
<h1 id="top">Links</h1>
<p>Read the <a id="external" href="{destination}" aria-label="other leaf documentation"
  aria-describedby="source-note">other leaf</a>.</p>
<span id="source-note" hidden>curated source</span>
<p>Return to <a id="fragment" href="#top">the heading</a>.</p>
<svg viewBox="0 0 40 20" aria-label="map"><a id="svg-external" href="{destination}">
  <text x="0" y="15">map</text>
</a></svg>
""",
        )
    )
    page = open_page(browser, url, context=one_user)
    external = page.locator("#external")
    mark = external.locator(":scope > .lf-external-mark")

    expect(external).to_have_attribute("target", "_blank")
    expect(external).to_have_attribute("rel", re.compile(r"(?:^| )noopener(?: |$)"))
    expect(external).to_have_accessible_name("other leaf documentation")
    expect(external).to_have_accessible_description("curated source opens in a new tab")
    # The treatment stands inside the link, so the paragraph ends where it was written.
    expect(page.locator("#external ~ *")).to_have_count(0)
    expect(mark).to_be_visible()
    assert mark.evaluate("node => node.localName") == "svg"
    expect(mark.locator(":scope > path")).to_have_count(1)
    expect(mark).to_have_attribute("aria-hidden", "true")
    expect(page.locator("#fragment > .lf-external-mark")).to_have_count(0)
    expect(page.locator("#fragment")).not_to_have_attribute("target", "_blank")
    expect(page.locator("#svg-external > .lf-external-mark")).to_have_count(0)
    expect(page.locator("#svg-external")).not_to_have_attribute("target", "_blank")

    tab = opened_tab(page, destination, external.click)
    expect(tab).to_have_url(f"{other_url}/")
    expect(page).to_have_url(url.split("?", 1)[0])


def test_an_addressed_link_leaves_the_user_at_its_destination(
    browser, serve, other_leaf, one_user
):
    """A generated link hint completes the trip it names.

    A fragment lands focus on its target, so the user does not remain at the place they
    left. An external link keeps its new-tab behavior and names that context change even
    though the sequence activates the link without first moving focus through it."""
    other_url, _ = other_leaf
    destination = f"{other_url}/?t={server_model.host_key()}"
    page = open_page(
        browser,
        serve(
            leaf_page(
                "addressed links",
                f"""
<h1>Addressed links</h1>
<p><a id="internal" href="#arrival">Read the conclusion</a>.</p>
<p><a id="external" href="{destination}" aria-label="Leaf guide">Open the guide</a>.</p>
<div style="height: 1600px"></div>
<h2 id="arrival">Conclusion</h2>
<p>The internal trip ends here.</p>
""",
            )
        ),
        context=one_user,
    )

    go_to_address(page, "Link", "internal")
    page.wait_for_url(re.compile(r"#arrival$"))
    expect(page.locator("#arrival")).to_be_focused()
    expect(page.locator("#arrival")).to_be_in_viewport()
    page.evaluate(
        "() => document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})"
    )

    page.keyboard.press("g")
    external_code = address_code(page, "Link", "external")
    tab = opened_tab(page, destination, lambda: page.keyboard.type(external_code))
    expect(tab).to_have_url(f"{other_url}/")
    expect(page.locator(".lf-live")).to_have_text("Opened Leaf guide in a new tab")


# The banner's cue; Firefox's paused tab cue is test_color_cues_fade_to_the_live_surface's.
@pytest.mark.parametrize("target", ["banner"])
def test_firefox_paints_a_natural_color_cue(firefox_browser, serve, target):
    """Observe the ordinary compositor path without pausing or reading its styles."""
    page = open_page(firefox_browser, serve(color_cue_markup()))
    page.emulate_media(reduced_motion="no-preference")
    if target == "tab":
        page.keyboard.press("q")
        expect(page.locator("#ask-first")).to_be_focused()
        selector = '#views [aria-controls="second"] .lf-tab-name'
    else:
        page.keyboard.press("c")
        box = page.locator(".lf-page-comment-card leaf-text")
        expect(box).to_be_focused()
        write(box, "Review both choices.")
        selector = ".lf-threads-toggle"
    page.evaluate(
        """selector => {
          window.__colorCue = {point: null, error: null};
          const node = document.querySelector(selector);
          const observe = () => {
            const cue = node.getAnimations()[0];
            if (!cue) { requestAnimationFrame(observe); return; }
            cue.finished.then(() => {
              const box = node.getBoundingClientRect();
              window.__colorCue.point = [box.left + 3, box.top + box.height / 2];
            }, error => { window.__colorCue.error = String(error); });
          };
          requestAnimationFrame(observe);
        }""",
        selector,
    )
    frames = []
    with page.screencast.start(
        on_frame=lambda frame: frames.append(frame),
        quality=100,
        size=page.viewport_size,
    ):
        page.keyboard.press("q" if target == "tab" else "Enter")
        page.wait_for_function(
            "() => window.__colorCue.point || window.__colorCue.error"
        )
        result = page.evaluate("() => window.__colorCue")
        assert result["error"] is None, result
        point = result["point"]
    colours = [
        Image.open(io.BytesIO(frame["data"]))
        .convert("RGB")
        .getpixel(tuple(round(coordinate) for coordinate in point))
        for frame in frames
    ]
    # Yellow to the light surface must paint intermediate colors, not a discrete
    # color change that paused animation/style reads could conceal in Firefox.
    blues = {blue for red, _green, blue in colours if red > 245 and 205 < blue < 240}
    assert len(blues) >= 3 and max(blues) - min(blues) >= 12, colours


def test_the_thread_walk_stays_inline_until_threads_is_opened(browser, serve):
    """t/T use page-local threads without moving the walk position."""
    page = open_page(
        browser,
        serve(INLINE_PAGE, anchored=[("p", "bold text"), ("p2", "neighbouring block")]),
    )
    page.set_viewport_size({"width": 1200, "height": 844})
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]

    # The readout takes no pointer, so the probe lends it one to hit-test it and takes it
    # back: the test's own write, outside what the page is held to (`lfUnwatched`).
    def position_is_front():
        return page.evaluate(
            """() => lfUnwatched(() => {
              const readout = document.querySelector('.lf-walk-position');
              const box = readout.getBoundingClientRect();
              readout.style.pointerEvents = 'auto';
              const front = document.elementFromPoint(
                (box.left + box.right) / 2,
                (box.top + box.bottom) / 2,
              ) === readout;
              readout.style.removeProperty('pointer-events');
              return front;
            })"""
        )

    # A panel search belongs to the panel. Closing it keeps that search for the next
    # visit, but must not silently remove a visible page thread from the inline walk.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page, True)
    page.get_by_role("searchbox", name="Find in threads").fill("neighbouring block")
    expect(page.locator(f'.lf-thread[data-id="{roots[0]}"]')).to_be_hidden()
    expect(page.locator(f'.lf-thread[data-id="{roots[1]}"]')).to_be_visible()
    position = page.locator(".lf-walk-position")
    page.locator(".lf-threads").focus()
    page.keyboard.press("n")
    expect(
        page.locator(f'.lf-thread[data-id="{roots[1]}"] > .lf-thread-summary')
    ).to_be_focused()
    expect(position).to_have_text("Thread 1 of 1 shown")
    expect(position.locator("xpath=parent::*")).to_have_class(
        re.compile("lf-bottom-status")
    )
    expect(position.locator("xpath=ancestor::*[@id='lf-shortcut-bar']")).to_have_count(
        0
    )
    panel_status = page.evaluate(
        """() => ({
          statusRight: document.querySelector('.lf-bottom-status').getBoundingClientRect().right,
          panelLeft: document.querySelector('.lf-thread-panel').getBoundingClientRect().left,
        })"""
    )
    assert panel_status["statusRight"] < panel_status["panelLeft"], panel_status
    assert position_is_front(), "the open Threads panel painted over its walk position"
    page.locator(".lf-threads-toggle").click()
    panel_settled(page, False)
    expect(position).to_be_hidden()

    page.evaluate(
        "async () => (await window.__lfRuntimeImport('/runtime/notifications.js'))"
        ".notice('Agent replied — open Threads', {background: true})"
    )
    expect(page.locator(".lf-notice")).to_be_visible()
    page.keyboard.press("t")
    first = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-thread="{roots[0]}"]'
    )
    expect(first).to_be_focused()
    # The walk position takes the notice's place at one instant. Both are chrome, which
    # the repaint after the press paints, so the reading waits for that frame.
    page.wait_for_function(
        """() => document.querySelector('.lf-walk-position').checkVisibility()
          && !document.querySelector('.lf-notice').checkVisibility()"""
    )
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    expect(position).to_have_text("Thread 1 of 2")
    expect(position).to_have_attribute("aria-hidden", "true")
    expect(position.locator("xpath=parent::*")).to_have_class(
        re.compile("lf-bottom-status")
    )
    assert position_is_front(), "the margin thread painted over its walk position"

    # The rail falling leaves the card up beside the marker's pin; the walk goes on from
    # there once the user has let the thread go.
    resized(page, 600, 844)
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")  # onto the passage, the card beside it
    page.keyboard.press("Escape")  # letting go of the passage takes the card
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    page.keyboard.press("t")
    expect(first).to_be_focused()
    expect(position).to_have_text("Thread 1 of 2")
    page.keyboard.press("t")
    second = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-thread="{roots[1]}"]'
    )
    expect(second).to_be_focused()
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    expect(position).to_have_text("Thread 2 of 2")
    expect(second.locator(".lf-msg").first).to_be_visible()
    preview_room = page.evaluate(
        """() => ({
          previewTop: document.querySelector('.lf-margin-preview').getBoundingClientRect().top,
          previewBottom: document.querySelector('.lf-margin-preview').getBoundingClientRect().bottom,
          bannerBottom: document.querySelector('.lf-banner').getBoundingClientRect().bottom,
          statusTop: document.querySelector('.lf-bottom-status').getBoundingClientRect().top,
        })"""
    )
    assert preview_room["previewTop"] >= preview_room["bannerBottom"] + 7, preview_room
    assert preview_room["previewBottom"] <= preview_room["statusTop"], preview_room

    status = page.locator(".lf-bottom-status")
    ordinary = status.evaluate("node => getComputedStyle(node).color")
    # Past the last thread the walk comes round to the first, and the position says so.
    page.keyboard.press("t")
    expect(first).to_be_focused()
    expect(position).to_have_text("Thread 1 of 2")
    expect(position).to_have_attribute("data-lf-boundary", "")
    assert status.evaluate("node => getComputedStyle(node).color") != ordinary
    expect(position).not_to_have_attribute("data-lf-boundary", "")

    page.keyboard.press("Shift+t")
    expect(second).to_be_focused()
    expect(position).to_have_text("Thread 2 of 2")
    expect(position).to_have_attribute("data-lf-boundary", "")

    page.keyboard.press("Shift+t")
    expect(first).to_be_focused()
    expect(position).to_have_text("Thread 1 of 2")
    expect(position).not_to_have_attribute("data-lf-boundary", "")

    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    found = page.locator(f'.lf-thread[data-id="{roots[1]}"] > .lf-thread-summary')
    expect(found).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(page.get_by_role("searchbox", name="Find in threads")).to_have_value(
        "neighbouring block"
    )

    # The panel keeps its narrowing; Escape clears it before leaving the panel.
    page.keyboard.press("Escape")
    expect(page.locator(f'.lf-thread[data-id="{roots[0]}"]')).to_be_visible()
    expect(found).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")


def test_a_panel_thread_closes_with_the_panel_as_go_to_threads_does(browser, serve):
    """A thread with no page destination opens in Threads and Escape closes the panel."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "This thread has no page anchor.")
    second = panel_comment(serve.page_dir, "Another panel thread.")
    last = panel_comment(serve.page_dir, "The last panel thread.")
    page = open_page(browser, url)
    panel = page.locator(".lf-thread-panel")
    card = page.locator(f'.lf-thread[data-id="{root}"]')

    page.keyboard.press("t")
    expect(panel).to_be_visible()
    expect(card.locator(":scope > .lf-thread-summary")).to_be_focused()
    expect(card).to_have_attribute("open", "")
    page.keyboard.press("Escape")
    expect(panel).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")

    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(panel).to_be_visible()
    expect(card.locator(":scope > .lf-thread-summary")).to_be_focused()
    page.keyboard.press("Escape")
    expect(panel).to_be_hidden()

    # Escape and g T both close the panel from a thread, and g T comes back to that
    # thread, still open, so the walk and native Tab entry go on from it alike.
    def summary(thread):
        return page.locator(f'.lf-thread[data-id="{thread}"] > .lf-thread-summary')

    tab_landings = []
    for release in ("Escape", "go-to"):
        for next_key in ("t", "Shift+t", "Tab"):
            page.keyboard.press("g")
            page.keyboard.press("Shift+t")
            # Home stands on the first thread whichever one was left open.
            for key in ("Home", "t"):
                page.keyboard.press(key)
            expect(summary(second)).to_be_focused()
            if release == "Escape":
                page.keyboard.press("Escape")
            else:
                page.keyboard.press("g")
                page.keyboard.press("Shift+t")
            expect(panel).to_be_hidden()
            page.keyboard.press("g")
            page.keyboard.press("Shift+t")
            expect(summary(second)).to_be_focused()
            expect(page.locator(f'.lf-thread[data-id="{second}"]')).to_have_attribute(
                "open", ""
            )
            page.keyboard.press(next_key)
            if next_key == "Tab":
                tab_landings.append(page.evaluate_handle("document.activeElement"))
            else:
                expect(summary(last if next_key == "t" else root)).to_be_focused()
            page.get_by_role("button", name="Close threads", exact=True).click()
            expect(panel).to_be_hidden()
    assert page.evaluate(
        "([released, entered]) => released === entered && released !== document.body",
        tab_landings,
    ), "Tab must have the same destination after Escape and g T"


def test_inner_state_is_left_before_the_surface_around_it(browser, serve):
    """Narrowing and page standing unwind before their surrounding surfaces.

    A thread or Ask inside Threads leaves through the panel's own steps: its
    narrowing, then the panel.
    """
    url = serve(INLINE_PAGE, anchored=[("p", "bold text")])
    panel_comment(
        serve.page_dir,
        "Is this the passage you meant?",
        {"section": "p2", "quote": "neighbouring block"},
        "agent",
    )
    page = open_page(browser, url)
    page.set_viewport_size({"width": 1200, "height": 844})
    line = page.locator(".lf-shortcut-bar")

    # From a thread, Escape clears the panel's narrowing before closing it, without
    # adding a title-selection level.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, True)
    page.keyboard.press("w")
    # The active narrowing is what `w` offers to clear, at every level above it.
    expect(line).to_contain_text("clear waiting filter")
    while not page.evaluate("() => document.activeElement.closest('.lf-thread')"):
        page.keyboard.press("Tab")
    expect(line).to_contain_text("clear waiting filter")
    page.keyboard.press("Escape")
    expect(line).to_contain_text("waiting on me")
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()

    # A page Ask stood on while a drawer the keyboard opened stands beside the page.
    page = open_page(browser, serve(ASKS_PAGE))
    line = page.locator(".lf-shortcut-bar")
    page.keyboard.press("g")
    page.keyboard.press("Shift+q")
    expect(page.locator(".lf-queue-panel.open")).to_be_visible()
    ask = page.locator("#live-question-decision")
    ask.evaluate("el => { el.tabIndex = -1; el.focus(); }")
    expect(ask).to_be_focused()
    expect(line).to_contain_text("let go")
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")
    expect(page.locator(".lf-queue-panel.open")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-queue-panel.open")).to_have_count(0)

    # `q` from a heading into a thread's Ask, with the panel already beside the page:
    # Escape closes the panel, without returning to the heading.
    page = open_page(browser, serve(ROOT / "examples" / "ship-review.html"))
    line = page.locator(".lf-shortcut-bar")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page, True)
    heading = page.locator("main h2").first
    heading.evaluate("el => { el.tabIndex = -1; el.focus(); }")
    expect(heading).to_be_focused()
    page.keyboard.press("q")
    expect(page.locator(".lf-thread lf-ask[data-lf-ask]")).to_be_focused()
    expect(line).to_contain_text("close threads")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")


def test_target_mnemonics_filter_the_generated_map_without_renumbering_hints(
    browser, serve
):
    """Semantic prefixes narrow the current generated map instead of replacing it.

    A filtered map preserves the codes its members had in the complete map. Its chips
    show only those generated suffixes; the complete route remains in the shortcut bar.
    """
    url = serve(
        ADDRESSED_PAGE.replace(
            '<p id="dsc-body">',
            '<p id="dsc-body"><a id="revealed-link" href="#p2">Read next passage</a> ',
        )
    )
    thread = answered_comment(
        serve.page_dir, "A visible thread.", {"section": "opts-decision"}
    )
    page = open_page(browser, url)
    resized(page, 1280, 800)
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")

    page.keyboard.press("?")
    page.keyboard.press("?")
    goto = command_reference_rows(page, "Go to")
    filters = goto.locator('tr[data-lf-command^="navigation.target.filter."]')
    assert filters.evaluate_all(
        """rows => rows.map(row => ({
          command: row.dataset.lfCommand,
          keys: [...row.querySelectorAll('kbd')].map(key => key.textContent),
          action: row.querySelector('.lf-command-reference-command').textContent,
        }))"""
    ) == [
        {
            "command": "navigation.target.filter.margin-entries",
            "keys": ["g", "m"],
            "action": "Show only visible margin targets",
        },
        {
            "command": "navigation.target.filter.threads",
            "keys": ["g", "t"],
            "action": "Show only visible Thread controls",
        },
        {
            "command": "navigation.target.filter.hyperlinks",
            "keys": ["g", "h"],
            "action": "Show only visible hyperlinks",
        },
        {
            "command": "navigation.target.filter.folds",
            "keys": ["g", "f"],
            "action": "Show only visible folds",
        },
    ]
    expect(filters.locator(".lf-command-reference-description")).to_have_text(
        ["Filter visible targets by kind"] * 4
    )
    target_help = goto.locator('tr[data-lf-command="navigation.target"]')
    expect(target_help.locator("kbd")).to_have_text(["g", "letters"])
    expect(target_help).to_contain_text("Type a visible target's hint")
    expect(target_help).not_to_contain_text("filter first")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")

    page.keyboard.press("g")
    chips = page.locator(CHIPS)
    expect(chips.first).to_be_visible()
    initial_kinds = set(
        chips.evaluate_all("els => els.map(el => el.dataset.lfGoToKind)")
    )
    assert {"Link", "Fold", "Control"} <= initial_kinds, initial_kinds
    assert chips.evaluate_all(
        "els => els.every(el => el.textContent === el.dataset.lfHintCode)"
    ), "an inline hint repeated the sequence context"

    mixed = page.locator(
        f'{CHIPS}[data-lf-go-to-kind="Margin entry"]'
        '[data-lf-go-to-target="opts-decision"]'
    )
    expect(
        page.locator(f'{CHIPS}[data-lf-go-to-target="revealed-link"]')
    ).to_have_count(0)
    expect(mixed).to_have_count(2)
    mixed_codes = mixed.evaluate_all(
        "els => Object.fromEntries(els.map(el => "
        "[el.dataset.lfGoToMarginEntry, el.dataset.lfHintCode]))"
    )
    thread_code = mixed_codes["reading:threadList"]
    ask_key = next(key for key in mixed_codes if key != "reading:threadList")

    page.keyboard.press("m")
    filtered = page.locator(CHIPS)
    expect(filtered).to_have_count(2)
    assert address_codes(page) == list(mixed_codes.values())
    page.keyboard.press("Escape")
    shortcut_bar_text(page)

    page.keyboard.press("t")
    expect(filtered).to_have_count(1)
    assert address_codes(page) == [thread_code]
    target_route = page.locator(
        '.lf-shortcut-bar .lf-shortcut[data-lf-command-ids~="navigation.target"]'
    )
    assert target_route.locator("kbd").evaluate_all(
        "keys => keys.map(key => key.textContent)"
    ) == ["g", "t", "letters"]
    assert target_route.locator("kbd").evaluate_all(
        "keys => keys.map(key => key.dataset.lfSequenceStepState)"
    ) == ["pressed", "pressed", "neutral"]
    expect(target_route).not_to_contain_text("filter")

    page.keyboard.type(thread_code)
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    page.keyboard.press("Escape")

    # Reveal another target so rearming reads a different visible scene.
    page.locator("#dsc-head").click()
    expect(page.locator("#revealed-link")).to_be_visible()
    page.keyboard.press("g")
    shortcut_bar_text(page)
    expect(page.locator("body")).to_have_attribute("data-lf-go-to-active", "")
    expect(page.locator(CHIPS).first).to_be_visible()
    assert (
        set(
            page.locator(CHIPS).evaluate_all(
                "els => els.map(el => el.dataset.lfGoToKind)"
            )
        )
        == initial_kinds
    )

    # Navigation can change the visible scene. This new map assigns its own hints;
    # filtering must preserve this map's ask code rather than the earlier map's.
    expect(
        page.locator(f'{CHIPS}[data-lf-go-to-target="revealed-link"]')
    ).to_have_count(1)
    ask_code = address_code(page, "Margin entry", "opts-decision", ask_key)
    page.keyboard.type(ask_code)
    expect(page.locator("#opts-decision")).to_be_focused()
    expect(page.locator("#opts-decision")).to_have_attribute("data-lf-ask", "1")

    # Scroll past the links to give the hyperlinks filter no members. An empty
    # filter stays empty through resize; Escape restores the complete map.
    page.locator("#opt-a").click()
    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "user", "parent": thread},
    )
    round_trip(page)
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="ask"]')).to_have_count(0)
    page.locator("#opts-decision").evaluate(
        "node => document.scrollingElement.scrollTo(0, node.offsetTop)"
    )
    scroll_settled(page)
    for target in ("lk1", "lk2", "revealed-link"):
        expect(page.locator(f"#{target}")).not_to_be_in_viewport()
    page.evaluate("() => document.activeElement?.blur()")
    page.keyboard.press("g")
    page.keyboard.press("h")
    expect(page.locator(CHIPS)).to_have_count(0)
    expect(page.locator(".lf-live")).to_have_text("No visible hyperlinks.")
    status = page.locator(".lf-bottom-status")
    expect(status.locator(".lf-go-to-status")).to_have_text("No visible hyperlinks.")
    expect(status).to_be_visible()
    expect(page.locator(".lf-notice")).not_to_have_class(re.compile(r"\bshow\b"))
    page.evaluate(
        """async () => {
          window.__liveChanges = [];
          new MutationObserver(() => {
            const words = document.querySelector('.lf-live').textContent;
            if (words) window.__liveChanges.push(words);
          }).observe(document.querySelector('.lf-live'), {
            childList: true,
            subtree: true,
          });
          (await window.__lfRuntimeImport('/runtime/notifications.js'))
            .notice('Agent replied — open Threads', {background: true});
        }"""
    )
    expect(page.locator(".lf-live")).to_have_text("Agent replied — open Threads")
    assert page.evaluate(
        """() => ({
          context: document.querySelector('.lf-go-to-status').checkVisibility(),
          notice: document.querySelector('.lf-notice').checkVisibility(),
        })"""
    ) == {"context": True, "notice": False}
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press("d")
    expect(page.locator("body")).to_have_attribute("data-lf-go-to-active", "")
    expect(page.locator(".lf-live")).to_have_text(
        "No hint d. The current hints are unchanged."
    )
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before
    resized(page, 1200, 800)
    expect(status.locator(".lf-go-to-status")).to_have_text("No visible hyperlinks.")
    expect(status).to_be_visible()
    expect(page.locator(CHIPS)).to_have_count(0)
    page.keyboard.press("Escape")
    expect(page.locator(CHIPS).first).to_be_visible()
    expect(page.locator(".lf-notice")).to_have_class(re.compile(r"\bshow\b"))
    expect(page.locator(".lf-live")).to_have_text("All go-to targets.")
    page.wait_for_timeout(100)
    assert (
        page.evaluate(
            "() => window.__liveChanges.filter(words => "
            "words === 'Agent replied — open Threads').length"
        )
        == 1
    ), "showing deferred news announced it a second time"
    assert status.evaluate(
        "node => getComputedStyle(node).backgroundColor"
    ) != page.locator(".lf-shortcut-bar").evaluate(
        "node => getComputedStyle(node).backgroundColor"
    )

    # The ask route may scroll these hyperlinks out of the visible target map.
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    scroll_settled(page)
    for target in ("lk1", "lk2", "revealed-link"):
        expect(page.locator(f"#{target}")).to_be_in_viewport()
    page.keyboard.press("g")
    page.keyboard.press("h")
    links = page.locator(f'{CHIPS}[data-lf-go-to-kind="Link"]')
    expect(links).to_have_count(3)
    expect(page.locator(f'{CHIPS}:not([data-lf-go-to-kind="Link"])')).to_have_count(0)
    resized(page, 1180, 800)
    expect(links).to_have_count(3)
    expect(page.locator(f'{CHIPS}:not([data-lf-go-to-kind="Link"])')).to_have_count(0)
    page.keyboard.type(address_code(page, "Link", "lk2"))
    page.wait_for_url(re.compile(r"#p2$"))
    expect(page.locator("#p2")).to_be_focused()


def test_the_g_chord_reaches_named_surfaces_and_visible_targets(browser, serve):
    """Mnemonics reach global surfaces; generated hints reach the visible scene.

    The Threads panel, Questions panel, Page Map dialog, and page edges keep stable named
    routes. Margin entries,
    tabs, links, folds, and the presses a widget built instead share one viewport-local
    letter namespace."""
    url = serve(ADDRESSED_PAGE)
    d = serve.page_dir

    def comment(anchor, text):
        return append_carried_log_record(
            d,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": text,
                "anchor": anchor,
            },
        )["id"]

    comment({"quote": "passage under discussion"}, "Sharpen this.")
    comment({"quote": "two separate remarks"}, "Second thought.")
    c3 = comment({"section": "p2"}, "The short one too.")
    page = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 3")
    line = page.locator(".lf-shortcut-bar")

    # The page's own key is the letter alone: what it opens is a table, and a range on the
    # line here could only ever have counted one of the lists in it.
    expect(line).to_contain_text("go to")
    expect(line).not_to_contain_text("1–3")

    # Wide enough that the panel will stand beside the page rather than over it, which is
    # where a box in the fixed chrome and the page's flow part company: body is narrowed
    # as the page shell, the panel is fixed and is not inside it, and a chip placed by
    # walking the page's clips came back with the whole reply box clipped away.
    resized(page, 1280, 800)

    # The complete reference shows each command once, preferring an executable intrinsic
    # route over its contextual Go-to route. Keep identities across all sections so that
    # a command such as Align current item can be covered by its permanent page route.
    page.keyboard.press("?")
    page.keyboard.press("?")
    goto = command_reference_rows(page, "Go to")
    reference_commands = set(
        page.locator(".lf-command-reference tr[data-lf-command]").evaluate_all(
            "rows => rows.map(row => row.dataset.lfCommand)"
        )
    )
    alignment = page.locator(
        '.lf-command-reference tr[data-lf-command="reading.align.top"]'
    )
    expect(alignment).to_have_count(1)
    # Alignment has a page-level route even when no reading item stands while
    # the reference opens from chrome.
    expect(alignment.locator(".lf-binding-sequence > kbd")).to_have_text(["g", "z"])
    overlaps = goto.locator("tr[data-lf-command]").evaluate_all(
        """rows => rows.flatMap(row => {
          const [key, action] = row.querySelectorAll(':scope > td');
          const amount = key.firstElementChild.getBoundingClientRect().right
            - action.getBoundingClientRect().left;
          return amount > 0.5 ? [{command: row.dataset.lfCommand, amount}] : [];
        })"""
    )
    assert overlaps == [], f"a complete route overlaps its action: {overlaps}"
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")

    # Armed, the line names the available global routes and visible-target map. Every destination
    # keeps its complete route, with the leader painted as already pressed. A window wide
    # enough to hold every destination in the line's one row, so the comparison is of the
    # rows the sequence offers rather than of what a narrower one has room for.
    resized(page, 2560, 800)
    page.keyboard.press("g")
    shortcut_bar_text(page)
    live_commands = set(
        page.evaluate(
            """async () => {
              const {pageScopes} = await window.__lfRuntimeImport('runtime/keyboard/register.js');
              const {live, commandPresentations} = await window.__lfRuntimeImport('runtime/keyboard/bindings.js');
              const scope = pageScopes().find(scope => scope.rows?.some(
                row => row.id === 'navigation.target'));
              return scope.rows.filter(live).flatMap(row =>
                commandPresentations(row).map(({id}) => id));
            }"""
        )
    )
    assert live_commands, "the page must contribute live Go to commands"
    assert live_commands <= reference_commands, (
        f"live Go to commands missing from the complete reference: "
        f"{sorted(live_commands - reference_commands)}"
    )
    visible_sequence = line.locator(".lf-shortcut:not([hidden])")
    visible_commands = set(
        visible_sequence.evaluate_all(
            """hints => hints.flatMap(hint =>
              (hint.dataset.lfCommandIds || '').split(' ').filter(Boolean))"""
        )
    )
    assert visible_commands == live_commands, (
        "the armed line and live Go to register diverged: "
        f"line={sorted(visible_commands)}, register={sorted(live_commands)}"
    )
    for command, steps, states, words in [
        (
            "navigation.panel.threads",
            ["g", "T"],
            ["pressed", "neutral"],
            "Threads panel",
        ),
        (
            "navigation.drawer.queue",
            ["g", "Q"],
            ["pressed", "neutral"],
            "Questions panel",
        ),
        (
            "navigation.page-map",
            ["g", "M"],
            ["pressed", "neutral"],
            "Page Map dialog",
        ),
        (
            "navigation.target",
            ["g", "letters"],
            ["pressed", "neutral"],
            "visible target",
        ),
        (
            "navigation.target.filter.threads",
            ["g", "kind"],
            ["pressed", "neutral"],
            "filter by kind",
        ),
        (
            "navigation.page.top",
            ["g", "g / G"],
            ["pressed", "neutral"],
            "top / bottom",
        ),
        (
            "navigation.go-to.back",
            ["esc"],
            ["neutral"],
            "cancel",
        ),
    ]:
        hint = line.locator(
            f'.lf-shortcut:not([hidden])[data-lf-command-ids~="{command}"]'
        )
        expect(hint).to_have_count(1)
        sequence = hint.locator(".lf-binding-sequence")
        assert (
            sequence.evaluate(
                "el => [...el.querySelectorAll(':scope > kbd')].map(k => k.textContent)"
            )
            == steps
        )
        assert (
            sequence.evaluate(
                "el => [...el.querySelectorAll(':scope > kbd')].map(k => k.dataset.lfSequenceStepState)"
            )
            == states
        )
        expect(sequence).to_have_attribute(
            "aria-label", " then ".join(step.replace(" / ", " or ") for step in steps)
        )
        expect(hint).to_contain_text(words)
    assert "navigation.drawer.leaves" not in reference_commands

    # The visible More control and its registered `?` command are one route. An unmatched
    # key first disarms the sequence and keeps its ordinary meaning; a pointer press must
    # enter the same expanded bar rather than inspecting the still-armed stack and
    # skipping to the full reference.
    def disclosure_state():
        return page.evaluate(
            """() => ({
              help: document.querySelector('.lf-command-reference').open,
              expanded: document.querySelector('.lf-shortcut-bar').dataset.lfExpanded,
              pressed: document.querySelectorAll(
                '.lf-shortcut-bar kbd[data-lf-sequence-step-state="pressed"]'
              ).length,
              commands: [...document.querySelectorAll('.lf-shortcut-bar .lf-shortcut:not([hidden])')]
                .flatMap(hint => (hint.dataset.lfCommandIds || '').split(' ').filter(Boolean)),
            })"""
        )

    page.get_by_role("button", name="? more", exact=True).click()
    rendered(page)
    pointer_disclosure = disclosure_state()
    page.reload()
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 3")
    resized(page, 1280, 800)
    page.keyboard.press("g")
    page.keyboard.press("?")
    rendered(page)
    key_disclosure = disclosure_state()
    assert pointer_disclosure == key_disclosure, (
        "the visible More control and its ? binding diverged: "
        f"pointer={pointer_disclosure}, key={key_disclosure}"
    )
    page.keyboard.press("Escape")
    page.keyboard.press("g")

    for width in (1280, 420):
        resized(page, width, 800)
        rendered(page)
        # The page's room is the bottom bar's stated height, and the line keeps to it.
        room = page.evaluate(
            """() => {
              const probe = document.createElement('div');
              probe.style.cssText = 'position:fixed;visibility:hidden;height:var(--lf-bottom-bar-h)';
              document.body.append(probe);
              const band = probe.getBoundingClientRect().height;
              probe.remove();
              return {band, reserved: parseFloat(getComputedStyle(
                document.body).paddingBottom)};
            }"""
        )
        assert room["band"] > 0 and room["reserved"] == room["band"], room
        geometry = line.evaluate(
            """node => {
              const visible = [...node.querySelectorAll(".lf-shortcut, .lf-shortcut-more")]
                .filter(el => el.checkVisibility({visibilityProperty: true}));
              const tops = [];
              const tolerance = Math.min(...visible.map(el => el.offsetHeight)) / 2;
              for (const el of visible)
                if (tops.every(top => Math.abs(top - el.getBoundingClientRect().top) > tolerance))
                  tops.push(el.getBoundingClientRect().top);
              const box = node.getBoundingClientRect();
              return {
                rows: tops.length,
                clientWidth: node.clientWidth,
                scrollWidth: node.scrollWidth,
                clientHeight: node.clientHeight,
                scrollHeight: node.scrollHeight,
                left: box.left,
                right: box.right,
                viewport: innerWidth,
                height: box.height,
              };
            }"""
        )
        assert geometry["scrollWidth"] <= geometry["clientWidth"], geometry
        assert geometry["scrollHeight"] <= geometry["clientHeight"], geometry
        assert geometry["left"] >= 0 and geometry["right"] <= geometry["viewport"], (
            geometry
        )
        # The line is one row at every width: the destinations it has no room for leave
        # it from the end of the register's order, and the way out and More stay.
        assert geometry["rows"] == 1, geometry
        assert geometry["height"] == pytest.approx(room["band"], abs=0.5), geometry
        expect(
            line.locator('.lf-shortcut[data-lf-command-ids~="navigation.go-to.back"]')
        ).to_be_visible()
        expect(line.locator(".lf-shortcut-more")).to_be_visible()
        if width == 420:
            expect(
                line.locator('.lf-shortcut[data-lf-command-ids~="navigation.page.top"]')
            ).to_be_hidden()
    resized(page, 1280, 800)
    expect(page.locator(CHIPS).first).to_be_visible()
    # The chips are the eye's copy of the Go-to sequence; a user who cannot see them is told the
    # window opened and what it holds, off the same rows the line just drew.
    expect(page.locator(".lf-live")).to_contain_text("visible targets")
    expect(page.locator(".lf-live")).to_contain_text("type a hint")
    expect(page.locator(".lf-live")).to_contain_text("Shift+t Threads panel")

    # A panel mnemonic completes the sequence and leaves the user inside that panel, on
    # the thread it shows open, where its own scoped keys are immediately available.
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    expect(page.locator(f"{EXPANDED} > .lf-thread-summary")).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)
    expect(page.locator(f"{EXPANDED} leaf-text")).to_have_attribute(
        "placeholder", "Reply c"
    )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    assert page.evaluate("() => document.activeElement === document.body")

    # The Questions sequence follows the same contract: show the panel and land on its first
    # row.
    page.keyboard.press("g")
    page.keyboard.press("Shift+q")
    expect(page.locator(".lf-queue-panel")).to_be_visible()
    expect(page.locator(".lf-queue-row").first).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)

    # Replacing one auxiliary surface with another is lateral: Threads replaces Questions
    # while it stands, and the Escape out of Threads lands on the page rather than putting
    # the drawer back. The user reaches the drawer the way they reached it the first time.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-thread-panel")).to_be_visible()
    expect(page.locator(".lf-queue-panel")).not_to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    expect(page.locator(".lf-queue-panel")).not_to_be_visible()
    assert page.evaluate("() => document.activeElement === document.body")

    # Page Map stands over whatever the user already had. The drawer they reopen here
    # is beneath it rather than remembered by it, so closing the dialog leaves that drawer
    # exactly where it was.
    page.keyboard.press("g")
    page.keyboard.press("Shift+q")
    expect(page.locator(".lf-queue-panel")).to_be_visible()
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    sheet = page.get_by_role("dialog", name="Page Map", exact=True)
    expect(sheet).to_be_visible()
    expect(
        sheet.get_by_role(
            "searchbox", name="Find an action, status, or location in Page Map"
        )
    ).to_be_focused()
    # Its accessible name does not add a second visible caption above the placeholder.
    assert (
        sheet.locator(".lf-page-map-search").evaluate(
            "node => node.shadowRoot.querySelector('[part~=form-control-label]')"
            ".getBoundingClientRect().height"
        )
        <= 1
    )
    page.evaluate(
        """() => {
          window.__lfPageMapClosed = false;
          document.querySelector('dialog.lf-page-map-dialog').addEventListener(
            'close',
            () => { window.__lfPageMapClosed = true; },
            {once: true},
          );
        }"""
    )
    page.keyboard.press("Escape")
    page.wait_for_function("() => window.__lfPageMapClosed")
    expect(page.locator(".lf-queue-panel")).to_be_visible()

    page.keyboard.press("?")
    page.keyboard.press("?")
    queue_help = command_reference_rows(page, "In Questions")
    expect(queue_help.get_by_text("Previous item", exact=True)).to_have_count(1)
    expect(queue_help.get_by_text("Next item", exact=True)).to_have_count(1)
    expect(
        queue_help.get_by_text(re.compile(r"decision", re.IGNORECASE))
    ).to_have_count(0)
    page.keyboard.press("Escape")  # out of the reference
    page.keyboard.press("Escape")  # and the expanded shortcut bar it was opened from
    expect(page.locator(".lf-queue-panel")).to_be_visible()
    page.keyboard.press("Escape")  # the drawer they were standing in
    expect(page.locator(".lf-queue-panel")).not_to_be_visible()

    # Uppercase M opens the complete Page Map rather than the numbered prefix.
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    sheet = page.get_by_role("dialog", name="Page Map", exact=True)
    expect(sheet).to_be_visible()
    expect(sheet.locator(".lf-page-map-group")).to_have_count(3)
    expect(
        sheet.get_by_role(
            "searchbox", name="Find an action, status, or location in Page Map"
        )
    ).to_be_focused()
    page.keyboard.press("Escape")
    expect(sheet).to_be_hidden()

    # A visible Margin entry shares the generated target map. Activating the hint
    # opens the same thread preview as its marker.
    go_to_address(page, "Margin entry", "p1")
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-margin-thread .lf-page-thread")).to_be_focused()
    page.keyboard.press("Escape")  # onto the element the thread is about
    expect(page.locator("#p1")).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()

    # The hyperlinks, from the head of the page where both are on screen. A hint is centred on the
    # corner a member starts at, which for an inline that wraps is the corner of its first
    # line and not of its bounding box — those run the width of the column, so a digit
    # route's visible start rather than on the inline's wide union box.
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    page.keyboard.press("g")
    expect(page.locator(f'{CHIPS}[data-lf-go-to-kind="Link"]')).to_have_count(2)
    assert page.evaluate(
        """() => {
             const links = [...document.querySelectorAll('#refs a[href]')];
             const chips = links.map(link => document.querySelector(
               `.lf-go-to-hints .lf-go-to-hint[data-lf-go-to-target="${link.id}"]`));
             return {wrapped: links[0].getClientRects().length > 1,
                     on: chips.map((chip, i) => {
                       const c = chip.getBoundingClientRect();
                       const first = links[i].getClientRects()[0];
                       return Math.abs(c.left + c.width / 2 - first.left) < 2
                           && Math.abs(c.top + c.height / 2 - first.top) < 2;
                     })};
           }"""
    ) == {
        "wrapped": True,
        "on": [True, True],
    }, "a chip is not on the corner its link starts at"
    page.keyboard.press("Escape")

    # At the foot of the page neither hyperlink is visible, so neither receives a route.
    page.evaluate(
        "() => document.scrollingElement.scrollTo(0, document.scrollingElement.scrollHeight)"
    )
    page.keyboard.press("g")
    expect(page.locator(f'{CHIPS}[data-lf-go-to-kind="Link"]')).to_have_count(0)
    page.keyboard.press("Escape")

    # Resolved is panel chrome rather than an authored fold. Read of the document at
    # large, `f` must not offer a digit for the panel's own state selector.
    append_carried_log_record(d, {"kind": "resolve", "author": "user", "parent": c3})
    told(page)
    expect(page.locator('[data-filter-value="resolved"]')).to_have_text("Resolved (1)")
    expect(page.locator("details.lf-details")).to_have_count(0)
    page.keyboard.press("g")
    expect(page.locator(f'{CHIPS}[data-lf-go-to-kind="Fold"]')).to_have_count(0)
    page.keyboard.press("Escape")

    # The folds, and the one arrival that changes the page it arrives at. Every
    # other member is reached through a reveal that opens the collapsed boxes on the way;
    # here the box is the member, so that same reveal is the whole motion, and the user
    # who wanted a section open has it open having asked once.
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    page.keyboard.press("g")
    fold_code = address_code(page, "Fold", "dsc-head")
    assert page.evaluate(
        """() => {
             const c = document.querySelector(
               '.lf-go-to-hints .lf-go-to-hint[data-lf-go-to-target="dsc-head"]')
                        .getBoundingClientRect();
             const first = document.getElementById('dsc-head').getClientRects()[0];
             return Math.abs(c.left + c.width / 2 - first.left) < 2
                 && Math.abs(c.top + c.height / 2 - first.top) < 2;
           }"""
    ), "the chip is not on the corner the summary starts at"
    expect(page.locator("#dsc")).not_to_have_attribute("open", "")
    page.keyboard.type(fold_code)
    expect(page.locator("#dsc-head")).to_be_focused()
    expect(page.locator("#dsc")).to_have_attribute("open", "")

    # Standing there, the line says which way the next press goes and names every key that
    # goes that way: Space as well as Enter, where a link takes Enter alone and Space under
    # one is the page's own scroll, and the one arrow with somewhere to go. Both cells are
    # read where they are painted — a word fixed at declaration could say only one of the
    # two directions, and a binding set fixed there would name an arrow that does nothing.
    # What the arrows do is the test below this one; here they are what the line offers.
    opened, shut = r"⏎ / space / ←", r"⏎ / space / →"
    expect(line).to_contain_text(re.compile(opened + r"\s*close"))
    page.keyboard.press("Enter")
    expect(page.locator("#dsc")).not_to_have_attribute("open", "")
    # Read once rather than waited for. Opening a disclosure is the one change in what the
    # next press does that no writer in the runtime reports, so the word stood at "close"
    # until a poll came past — and an assertion that retries reads a stale line as an
    # eventually right one, going green on whichever poll happens to land inside its
    # budget. The attribute watch has answered by the time the press returns or nothing
    # has.
    said = shortcut_bar_text(page)
    assert re.search(shut + r"\s*open", said), said
    page.keyboard.press(" ")
    expect(page.locator("#dsc")).to_have_attribute("open", "")
    said = shortcut_bar_text(page)
    assert re.search(opened + r"\s*close", said), said

    # A press a widget built joins the same namespace, declared by the constructor that
    # made it rather than by an entry here. A pick spends no page letter of its own — the
    # register holds capabilities, and a control is a route to one — so before this the
    # only keyboard way to it was Tab. The arrival is the press, so the option is chosen.
    page.evaluate(
        """() => document.scrollingElement.scrollTo(
             0, document.getElementById('opts-decision').offsetTop - 80)"""
    )
    page.keyboard.press("g")
    controls = page.locator(f'{CHIPS}[data-lf-go-to-kind="Control"]')
    expect(controls).not_to_have_count(0)
    pick_code = page.evaluate(
        """() => {
             const mark = document.querySelector('#opt-a .lf-pick').getBoundingClientRect();
             const chip = [...document.querySelectorAll(
               '.lf-go-to-hints .lf-go-to-hint[data-lf-go-to-kind="Control"]')]
               .find(c => {
                 const r = c.getBoundingClientRect();
                 return Math.abs(r.left + r.width / 2 - mark.left) < 2
                     && Math.abs(r.top + r.height / 2 - mark.top) < 2;
               });
             return chip ? chip.dataset.lfHintCode : null;
           }"""
    )
    assert pick_code, "the pick mark the widget built got no Go-to hint"
    page.keyboard.type(pick_code)
    expect(page.locator("#opt-a")).to_have_attribute("chosen", "")

    # The two completions that take no digit: an edge of the page is one place, so the
    # second key completes the route — G glides to the bottom, g to the top.
    foot = page.evaluate(
        "() => document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight"
    )
    assert foot > 0, "the page must scroll for an edge to be a move at all"
    page.keyboard.press("g")
    expect(line).to_contain_text("top / bottom")
    # Shift spelled out: a bare press("G") synthesizes key "G" with no shift modifier,
    # which a real keyboard cannot do, and the dispatcher rightly reads it as g.
    page.keyboard.press("Shift+G")
    page.wait_for_function(
        "foot => Math.abs(document.scrollingElement.scrollTop - foot) < 1", arg=foot
    )
    page.keyboard.press("g")
    page.keyboard.press("g")
    page.wait_for_function("() => document.scrollingElement.scrollTop === 0")

    # A panel mnemonic completes the sequence directly wherever the user is on the page.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    open_card = page.locator(EXPANDED)
    expect(open_card.locator(":scope > .lf-thread-summary")).to_be_focused()

    # Typing contexts are untouched: in a box, the whole sequence is text.
    page.keyboard.press("c")
    reply = page.locator(
        f'.lf-thread[data-id="{open_card.get_attribute("data-id")}"] leaf-text'
    )
    expect(reply).to_be_focused()
    page.keyboard.type("gc1")
    expect(reply).to_have_js_property("value", "gc1")
    expect(reply).to_be_focused()


def test_the_g_chord_reaches_the_all_leaves_panel(browser, serve, live_leaf):
    """All pages is the second drawer destination and follows the same focus contract."""
    live_leaf("second", "A second leaf")
    page = open_page(browser, serve(ADDRESSED_PAGE))

    page.keyboard.press("g")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("Pages drawer")
    expect(
        page.locator(
            '.lf-go-to-hints [data-lf-go-to-command="navigation.drawer.leaves"]'
        )
    ).to_have_count(0)
    threads_hint = page.locator(
        '.lf-go-to-hints [data-lf-go-to-command="navigation.panel.threads"]'
    )
    expect(threads_hint).to_be_visible()
    # A live secondary-control label may change while the sequence stands. Its keyboard
    # destination remains operable even though the fixed More seat has no target overlay.
    live_leaf("third", "A third leaf")
    round_trip(page)
    expect(page.locator(".lf-others")).to_contain_text("All pages (3)")
    expect(threads_hint).to_be_visible()
    page.keyboard.press("Shift+l")

    expect(page.locator(".lf-others-panel")).to_be_visible()
    expect(page.locator("a.lf-others-row").first).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)


def test_clamped_leaf_lists_share_the_walk_position(browser, serve, live_leaf):
    """Leaf-owned lists use one ordinal and one boundary face."""
    live_leaf("second", "A second leaf")
    live_leaf("third", "A third leaf")
    page = open_page(browser, serve(ASKS_PAGE))
    position = page.locator(".lf-walk-position")

    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(page.locator("a.lf-others-row").first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(position).to_have_text("Page 2 of 2")
    leaves_boxes = page.evaluate(
        """() => {
          const drawer = document.querySelector('.lf-others-panel').getBoundingClientRect();
          const position = document.querySelector('.lf-walk-position').getBoundingClientRect();
          return {drawerRight: drawer.right, positionLeft: position.left};
        }"""
    )
    assert leaves_boxes["positionLeft"] >= leaves_boxes["drawerRight"] + 18, (
        leaves_boxes
    )
    page.keyboard.press("ArrowDown")
    expect(position).to_have_attribute("data-lf-boundary", "")

    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.press("Shift+q")
    rows = page.locator("button.lf-queue-row")
    expect(rows.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(position).to_have_text(re.compile(r"^Item 2 of \d+$"))
    page.keyboard.press("ArrowUp")
    expect(position).to_have_text(re.compile(r"^Item 1 of \d+$"))
    page.keyboard.press("ArrowUp")
    expect(position).to_have_attribute("data-lf-boundary", "")

    page.keyboard.press("Escape")
    markers = page.locator(".lf-margin-marker:visible")
    assert markers.count() > 1
    markers.first.focus()
    page.keyboard.press("ArrowDown")
    expect(position).to_have_text(re.compile(r"^Marker 2 of \d+$"))


def test_a_box_that_starts_scrolling_after_it_arrives_takes_a_stop(browser, serve):
    """A box that starts scrolling after the page loads is reachable, shows its edge
    mark, and starts the sticky-header slot again, as it does when the page loads with
    it scrolling: whether a shorter window, a narrower container, or a page script made
    it scroll, by a class it adds as it adapts to the box's size or by a box it inserts,
    and announced it with `layoutChanged`. A box the window grows out of scrolling gives
    all three back. The window's case asks its height, which no box's size follows. A
    table first drawn when its disclosure opens is read in the size delivery that draws
    it, and a script announcing from a size delivery is heard, both without a
    ResizeObserver loop. A column's sidebar the page loads seated in the margin, where
    the Layout makes it scroll, takes its stop as one the window widened into the
    margin does. A size container a page animates for as long as it plays holds back
    neither the others nor the page's settling, though a script announces it."""
    wide = '<div class="wide">A block held to nine hundred pixels wide.</div>'
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Late scrollers",
                '<div id="meter"></div>'
                f'<div id="by-window">{wide}</div>'
                f'<div id="holder"><div id="by-container">{wide}</div></div>'
                f'<div id="by-script">{wide}</div>'
                '<details id="more"><summary>More</summary><table id="drawn"><tbody>'
                "<tr><td>Cell</td></tr></tbody></table></details>",
                head="<style>.wide { width: 900px; }"
                "@media (height < 860px) { #by-window { overflow-x: auto; } }"
                "#holder { container-type: inline-size; width: 800px; }"
                "@container (width < 600px) { #by-container { overflow-x: auto; } }"
                "#by-script.scrolls, #by-insert { overflow-x: auto; }"
                "@keyframes pulse { from { width: 120px; } to { width: 160px; } }"
                "#meter { container-type: inline-size; block-size: 8px;"
                " animation: pulse 1s linear infinite; }</style>",
            )
        ),
    )
    resized(page, 1200, 900)
    names = ("window", "container", "script")
    boxes = {name: page.locator(f"#by-{name}") for name in names}
    for box in boxes.values():
        expect(box).not_to_have_attribute("data-lf-scrolls", "")

    resized(page, 1200, 800)
    page.evaluate(
        """async () => {
        document.getElementById('holder').style.width = '400px';
        const { layoutChanged } = await window.__lfRuntimeImport('/runtime/widget-api.js');
        const box = document.getElementById('by-script');
        new ResizeObserver((entries, observer) => {
            observer.disconnect();
            box.classList.add('scrolls');
            layoutChanged(box);
        }).observe(box);
        const inserted = document.createElement('div');
        inserted.id = 'by-insert';
        inserted.innerHTML = '<div class="wide">An inserted block.</div>';
        document.querySelector('main').append(inserted);
        layoutChanged(inserted);
        layoutChanged(document.getElementById('meter'));
    }"""
    )
    boxes["insert"] = page.locator("#by-insert")
    for box in boxes.values():
        expect(box).to_have_attribute("data-lf-more-after", "")
        expect(box).to_have_attribute("tabindex", "0")
        expect(box).to_have_attribute("data-lf-scrolls", "")

    resized(page, 1200, 900)
    window_box = boxes["window"]
    expect(window_box).not_to_have_attribute("data-lf-scrolls", "")
    expect(window_box).not_to_have_attribute("data-lf-more-after", "")
    expect(window_box).not_to_have_attribute("tabindex", "0")

    rendered(page)

    page.evaluate(
        "() => { document.getElementById('meter').style.animation = 'none'; }"
    )
    rendered(page)
    page.locator("#more > summary").click()
    expect(page.locator("#drawn")).to_have_attribute("data-lf-scrolls", "")

    entries = "".join(f"<li>Sidebar entry {n}</li>" for n in range(40))
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Seated sidebar",
                f'<aside class="sidebar" id="side"><ul>{entries}</ul></aside>'
                "<h1>Seated sidebar</h1>" + "<p>Filler.</p>" * 30,
            )
        ),
        context=browser.new_context(viewport={"width": 1600, "height": 900}),
    )
    expect(page.locator("main")).to_have_attribute(
        "data-lf-margin", re.compile("sidebar")
    )
    expect(page.locator("#side")).to_have_attribute("tabindex", "0")


def test_named_go_to_addresses_toggle_their_auxiliary_surfaces(
    browser, serve, live_leaf
):
    """One auxiliary selection survives reload and retains its native modal posture."""
    live_leaf("second", "A second leaf")
    page = open_page(browser, serve(ASKS_PAGE, comments=1))

    # A surface beside the page and one covering it; the Questions panel stands beside
    # it as Threads does.
    for key, command, name, surface, control, covering in (
        (
            "Shift+t",
            "navigation.panel.threads",
            "Threads panel",
            ".lf-thread-panel",
            ".lf-threads-toggle",
            False,
        ),
        (
            "Shift+l",
            "navigation.drawer.leaves",
            "Pages drawer",
            ".lf-others-panel",
            ".lf-others",
            True,
        ),
    ):
        page.keyboard.press("g")
        page.keyboard.press(key)
        expect(page.locator(surface)).to_be_visible()
        assert bool(page.locator("dialog:modal").count()) is covering

        navigate(page, page.url)
        expect(page.locator(surface)).to_be_visible()
        assert bool(page.locator("dialog:modal").count()) is covering

        page.keyboard.press("g")
        expect(page.locator("body")).to_have_attribute("data-lf-go-to-active", "")
        close_hint = page.locator(
            f'.lf-shortcut-bar .lf-shortcut[data-lf-command-ids~="{command}"]'
        )
        expect(close_hint).to_be_visible()
        expect(close_hint).to_contain_text(f"close {name}")
        page.keyboard.press(key)
        expect(page.locator(surface)).to_be_hidden()
        expect(page.locator(control)).to_have_attribute("aria-expanded", "false")
        navigate(page, page.url)
        expect(page.locator("body")).not_to_have_attribute(
            "data-lf-auxiliary-surface", re.compile(".+")
        )
        assert not bool(page.locator("dialog:modal").count())


def test_reference_accepts_native_popover_dismissal_across_modal_entry(browser, serve):
    """The global modal dismisses contextual auto popovers rather than rebuilding them."""
    url = serve(LONG_PAGE, comments=2)
    _publish(serve.page_dir, 2, LONG_PAGE, "two")
    page = open_page(browser, url)
    resized(page, 1000, 800)
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page)

    thread = page.locator(".lf-thread").first.locator(":scope > .lf-thread-summary")
    thread.focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+v")
    versions = page.locator(".lf-version-menu")
    expect(versions).to_be_visible()
    page.keyboard.press("?")
    expect(versions).to_be_visible()
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    expect(versions).to_be_hidden()
    contextual_versions = reference.locator('[data-lf-command^="version.open-v"]')
    assert contextual_versions.count() > 0
    # Number keys delegate to native version rows. Once the modal dismisses the
    # menu, the reference still names those routes but offers no action for them.
    expect(contextual_versions.first).to_contain_text("Open v")
    expect(
        reference.locator(
            '.lf-command-reference-command[data-lf-command^="version.open-v"]'
        )
    ).to_have_count(0)
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()
    expect(versions).to_be_hidden()
    expect(thread).to_be_focused()

    page.keyboard.press("g")
    page.keyboard.press("Shift+v")
    expect(versions).to_be_visible()
    page.keyboard.press("?")
    expect(versions).to_be_visible()
    page.keyboard.press("?")
    expect(reference).to_be_visible()

    search = reference.get_by_role("combobox", name="Search commands")
    search.fill("thread")
    page.keyboard.press("ArrowDown")
    search.evaluate(
        "node => { node.setSelectionRange(1, 3); window.heldReferenceSearch = node; }"
    )
    held_search = search.evaluate(
        "node => [node.value, node.selectionStart, node.selectionEnd, node.ariaActiveDescendantElement?.id]"
    )
    resized(page, 400, 800)
    panel_settled(page)
    expect(reference).to_be_visible()
    expect(search).to_be_focused()
    assert search.evaluate("node => node === window.heldReferenceSearch")
    assert (
        search.evaluate(
            "node => [node.value, node.selectionStart, node.selectionEnd, node.ariaActiveDescendantElement?.id]"
        )
        == held_search
    )
    assert search.evaluate(
        "node => { const box = node.getBoundingClientRect(); return node.getRootNode().elementFromPoint(box.x + box.width / 2, box.y + box.height / 2) === node; }"
    )
    # Every Escape from here lands the user while the panel covers the page, which is
    # inert under it, so the panel is what can take them. The platform also hands a
    # popover's focus back to whoever held it when the popover showed; that arrives at the
    # same place and hides whether Leaf landed them at all. Throttling takes the courtesy
    # away, so these assertions read Leaf's own landing — a saturated CI runner took
    # it away about one run in three, which is how this was found. It has to span the
    # presses rather than sit on the last one: the state the final press lands from is
    # built by the ones before it, and throttling only that press does not reproduce. The
    # rate is the measured one: at 20 the whole case takes about four seconds, where a
    # gentler 6 takes seventeen, because the courtesy sometimes still arrives and the
    # waits below sit through it.
    page.context.new_cdp_session(page).send(
        "Emulation.setCPUThrottlingRate", {"rate": 20}
    )
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()
    expect(versions).to_be_hidden()
    panel = page.locator("#lf-threads")
    assert panel.evaluate("panel => panel.contains(document.activeElement)")
    assert bool(page.locator("dialog:modal").count())
    # The stale row the reference displaced cannot take focus back, and where the user
    # lands instead is not settled: sometimes the card they stood on, sometimes the
    # covering panel's list. The card returns to the panel; the panel returns to the
    # page. The versions menu's keys are gone either way.
    rendered(page)
    hints = {hint["commands"] for hint in page.evaluate(KEY_LINE_HINTS)}
    assert {"navigation.back", "navigation.release"} & hints, hints
    assert not any(command.startswith("version.") for command in hints), hints

    # The same platform rule applies to a popover opened over the established boundary.
    page.keyboard.press("g")
    page.keyboard.press("Shift+v")
    expect(versions).to_be_visible()
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(reference).to_be_visible()
    expect(versions).to_be_hidden()
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()
    expect(versions).to_be_hidden()
    assert panel.evaluate("panel => panel.contains(document.activeElement)")


def test_c_travels_to_an_item_its_own_scroller_has_taken_away(browser, serve):
    """What the press asks is whether the item is in front of the user, and only the
    page shows that. An item's own box is the box it would have — unclipped — so a card
    carried out of a board's sideways scroller still reports one inside the window, and a
    gate reading that called it visible and opened the box on something entirely off
    screen. `shownRect` is the reading the ⌥ aim's own paint takes, and this press is its
    keyboard twin: the two decide "in front of the user" alike or they are not twins.

    The control is the same board with the scroller left alone, where the card is really
    in front of the user and nothing moves — the pointer's answer on the same card. A
    test with only the scrolled case would pass just as well on a press that always
    travelled, which is the behaviour this replaced."""
    url = serve(
        leaf_page(
            "carried",
            """
<h1 id="t">Carried</h1>
<lf-board id="b">
"""
            + "\n".join(
                f'<lf-column id="col{i}" label="Column {i}">'
                f'<lf-card id="card{i}">Card {i} with a '
                f'<a href="https://example.invalid/{i}">link {i}</a> inside it.</lf-card>'
                "</lf-column>"
                for i in range(8)
            )
            + """
</lf-board>
""",
        )
    )
    seen = """() => {
      const r = document.querySelector('#card0').getBoundingClientRect();
      const b = document.querySelector('#b').getBoundingClientRect();
      return {
        left: Math.round(r.left),
        onScreen: r.right > 0 && r.left < innerWidth,
        visible: Math.max(0, Math.min(r.right, b.right, innerWidth)
          - Math.max(r.left, b.left, 0)),
        width: r.width,
      };
    }"""

    # The control: nothing scrolled, so the card is in front of the user and stays put.
    page = open_page(browser, url)
    page.locator("#card0 a").focus()
    was = page.evaluate(seen)
    assert was["onScreen"], "the control needs the card visible to begin with"
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(seen)["left"] == was["left"], (
        "the page moved under a user who could already see the card"
    )
    page.close()

    # The same standing with only the board's next-item cue left in view. The
    # sliver still supplies an attachment, so opening Comment preserves the board.
    page = open_page(browser, url)
    page.locator("#card0 a").focus()
    page.evaluate(
        """() => {
          const card = document.querySelector('#card0');
          document.querySelector('#b').scrollLeft = card.getBoundingClientRect().width - 7;
        }"""
    )
    was = page.evaluate(seen)
    assert 0 < was["visible"] < was["width"] / 4, was
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    now = page.evaluate(seen)
    assert now == was
    page.close()

    # Carried out of its own scroller after the user stood on it — focus first, because
    # focusing a card is itself a scroll and would undo the carrying it is meant to survive.
    page = open_page(browser, url)
    page.locator("#card0 a").focus()
    page.evaluate(
        "() => { const b = document.querySelector('#b'); b.scrollLeft = b.scrollWidth; }"
    )
    assert not page.evaluate(seen)["onScreen"], (
        "the board did not carry the card off screen, so this proves nothing"
    )
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(seen)["onScreen"], (
        "the box opened on a card the board had carried out of sight"
    )


def test_a_user_at_the_top_of_the_document_is_one_press_from_the_chrome(browser, serve):
    """The runtime's layer follows `main`, so reaching it by Tab meant reaching it last.

    Document order is right for reading — the page is what the user came for — and it
    is the whole tab order too, so on a page of any length the banner, the panel and the
    shortcut bar stood behind every link, fold and control the author wrote. A keyboard user
    arriving at the top of the document had no way to the layer that is not the page.

    The press is what is asserted rather than the link's presence: a skip link that is in
    the DOM and does not land anybody is the failure this is about, one step later.

    On the PR walkthrough, which opens on its contents links, because a page of plain
    paragraphs would put the chrome one Tab away on its own and this would pass with
    the link taken out.
    """
    example = next(e for e in EXAMPLES if e.stem == "pr-walkthrough")
    page = open_page(browser, serve(example))
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("Tab")
    standing = page.evaluate(STANDING)
    assert standing["isFirstStop"], (
        f"the first Tab from the top of the document landed on {standing['name']}, so "
        f"the layer is still behind the whole page"
    )
    assert standing["top"] >= 0, (
        f"the skip link takes focus and is not on screen: {standing}"
    )
    page.keyboard.press("Enter")
    landed = page.evaluate(STANDING)
    assert landed["inChrome"], (
        f"the skip link's press left the user on {landed['name']}, outside the layer "
        f"it names"
    )


def test_quick_shortcuts_can_be_disabled_without_withdrawing_commands(browser, serve):
    """One persistent policy covers page keys, contextual digits and their hints."""
    page = open_page(browser, serve(QUICK_KEYS_PAGE))
    reference = page.locator(".lf-command-reference")
    setting = page.get_by_role("checkbox", name="Quick keyboard shortcuts", exact=True)
    note = page.locator("#shortcut-note")
    button = page.locator("#shortcut-focus-note")
    sample = page.locator("#local-shortcuts")

    def settings():
        page.locator(".lf-banner-more").click()
        page.get_by_role("button", name="Keyboard shortcuts", exact=True).click()
        expect(reference).to_be_visible()

    sample.focus()
    expect(button).to_have_attribute("aria-keyshortcuts", "1")
    page.keyboard.press("1")
    expect(note).to_be_focused()
    page.keyboard.type("c ? 1 T")
    expect(note).to_have_value("c ? 1 T")
    settings()
    expect(setting).to_be_checked()
    expect(setting).to_have_accessible_description(
        "Use letters, numbers and symbols for Leaf actions."
    )
    # The preference itself is reachable by Tab and native Space.
    page.get_by_role("combobox", name="Search commands").press("Shift+Tab")
    expect(setting).to_be_focused()
    setting.press("Space")
    expect(setting).not_to_be_checked()
    comment = reference.locator('tr[data-lf-command="comment.create"]')
    expect(comment.locator("kbd")).to_have_count(0)
    # Turning a binding off leaves its command actionable in the reference.
    page.get_by_role("combobox", name="Search commands").fill("Comment on the page")
    comment.get_by_role("button", name="Comment on the page", exact=True).click()
    field = page.get_by_role("textbox", name="Comment on the page", exact=True)
    expect(field).to_be_focused()
    page.keyboard.type("Sent with quick shortcuts off")
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator(".lf-page-comment-card")).to_be_hidden()
    # Send closes the card onto the row's visible Comment control.
    expect(page.locator(".lf-banner .lf-page-comment")).to_be_focused()
    told(page)
    assert any(
        event.get("text") == "Sent with quick shortcuts off"
        for event in events_model.read_events(serve.page_dir)
    )
    rendered(page)

    sample.focus()
    expect(button).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))
    for key in ("1", "c", "?", "Shift+t", "g", "Shift+t"):
        page.keyboard.press(key)
    rendered(page)
    expect(sample).to_be_focused()
    expect(reference).to_be_hidden()
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("go to")
    expect(button).not_to_have_attribute("title", re.compile(r"\(1\)"))
    settings()
    page.get_by_role("combobox", name="Search commands").fill("Select element")
    reference.locator('tr[data-lf-command="target.picker.open"]').get_by_role(
        "button"
    ).click()
    rendered(page)
    expect(page.locator(".lf-target-picker-hint")).to_have_count(0)
    expect(page.locator(".lf-live")).not_to_contain_text("type one of")
    page.keyboard.press("a")
    expect(page.locator(".lf-fab-input")).to_be_hidden()
    page.keyboard.press("Tab")
    expect(page.locator(".lf-live")).to_contain_text("Press Enter to choose")
    expect(page.locator(".lf-live")).not_to_contain_text("Hint ")
    native_target = page.locator('[data-lf-hint-native="Enter"]')
    expect(native_target).to_be_visible()
    expect(native_target).not_to_have_attribute("data-lf-hint-code")
    expect(native_target.locator("kbd")).to_have_text("⏎")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(native_target).to_have_count(0)
    page.keyboard.press("Escape")
    rendered(page)
    street = page.locator("#map-street")
    trail = page.locator("#map-trail")
    street.locator(".lf-pick").focus()
    expect(page.locator("#map")).not_to_have_attribute(
        "aria-keyshortcuts", re.compile(r"(?:^| )1(?: |$)")
    )
    page.keyboard.press("1")
    rendered(page)
    expect(street).not_to_have_attribute("chosen", "")
    street.locator(".lf-pick").focus()
    page.keyboard.press("ArrowDown")
    expect(trail.locator(".lf-pick")).to_be_focused()
    page.keyboard.press("Space")
    expect(trail).to_have_attribute("chosen", "")
    button.focus()
    button.press("Enter")
    expect(note).to_be_focused()
    note.press("End")
    page.keyboard.type(" native")
    expect(note).to_have_value("c ? 1 T native")

    page.reload()
    wait_until_ready(page)
    sample.focus()
    page.keyboard.press("1")
    rendered(page)
    expect(sample).to_be_focused()
    settings()
    expect(setting).not_to_be_checked()
    setting.check()
    page.keyboard.press("Escape")
    street.locator(".lf-pick").focus()
    expect(page.locator("#map")).to_have_attribute(
        "aria-keyshortcuts", re.compile(r"(?:^| )1(?: |$)")
    )
    page.keyboard.press("1")
    expect(street).to_have_attribute("chosen", "")
    sample.focus()
    expect(button).to_have_attribute("aria-keyshortcuts", "1")
    page.keyboard.press("1")
    expect(note).to_be_focused()

    settings()
    page.get_by_role("combobox", name="Search commands").fill("Select element")
    reference.locator('tr[data-lf-command="target.picker.open"]').get_by_role(
        "button"
    ).click()
    expect(page.locator(".lf-target-picker-hint").first).to_be_visible()
    page.keyboard.press("Escape")
