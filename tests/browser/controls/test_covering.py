"""The thread panel and auxiliary surfaces over the page: covering, inertness, the
scrim, separate scrolling, fixed chrome under a sheet, and where selection stops."""

import re

import pytest
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import live_url, panel_comment
from render_cases_layout import ONE_ASK, banner_control, toggle_queue
from render_cases_navigation import ADDRESSED_PAGE
from render_harness import (
    LONG_PAGE,
    SHELL_BOX,
    leaf_page,
    open_page,
    panel_settled,
    resized,
    select,
    stamp_page,
    told,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_selection_that_reaches_the_layer_stops_at_the_page(browser, serve):
    """A drag out of a paragraph takes the passage, not the page and the panel with it.

    The layer is fixed and stands after the document in it, so one range crossing into
    anything selectable in the chrome runs through everything between. Three surfaces
    said user-select: none and the rest did not, so a drag rightwards out of a paragraph
    that overshot the open thread panel's left edge by five pixels took 14,472 characters
    instead of the 67 aimed at, and pressing `c` put the whole page — the passage, every
    widget under it, and the panel's own furniture — into the composer's quote and into
    the field's accessible name.

    The apparatus is answered at the layer's root now, so this asserts the statement
    rather than the three surfaces: everything in here is unselectable except the words
    somebody said, which are a reply and the passage it is about, and those stay
    copyable.
    """
    # Anchored, so the thread carries both of the things a user may want out of the
    # panel: the passage it is about and the reply somebody wrote under it.
    url = serve(LONG_PAGE, anchored=[("p40", "Paragraph 40.")])
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-thread-summary").click()
    expect(page.locator(".lf-thread")).to_have_count(1)

    aim = page.evaluate(
        """() => {
          const para = [...document.querySelectorAll('p')].find((el) => {
            const r = el.getBoundingClientRect();
            return r.width > 200 && r.top > 140 && r.bottom < innerHeight - 60;
          });
          const r = para.getBoundingClientRect();
          return {start: [r.left + 40, r.top + 8],
                  edge: document.querySelector('.lf-thread-panel').getBoundingClientRect().left,
                  words: para.textContent,
                  whole: document.body.textContent.length};
        }"""
    )
    # Five pixels past the edge: the overshoot a user gives a drag they meant to end at
    # the end of a line, which at the covering width lands mid-line on every paragraph.
    select(page, aim["start"], (aim["edge"] + 5, aim["start"][1]))
    took = page.evaluate("() => getSelection().toString()")
    assert took and took in aim["words"], (
        f"the drag took {len(took)} characters from outside the paragraph it started in, "
        f"out of {aim['whole']} in the document: {took[:80]!r}…{took[-80:]!r}"
    )

    # The statement, rather than the surfaces that happened to carry it: apparatus is
    # unselectable, and what a user may copy says so for itself.
    open_layer = page.evaluate(
        """() => {
          const said = '.lf-quote, .lf-msg-body';
          return [...document.querySelector('.lf-chrome').querySelectorAll('*')]
            .filter((el) => getComputedStyle(el).webkitUserSelect !== 'none')
            .filter((el) => !el.closest(said))
            .map((el) => (el.className || el.tagName).toString().trim().split(/\\s+/)[0]);
        }"""
    )
    assert open_layer == [], (
        f"chrome surfaces outside a reply and its passage stayed selectable: {open_layer}"
    )
    copyable = page.evaluate(
        """() => {
          const out = {};
          for (const [name, sel] of [
            ['quote', '.lf-thread-panel.open .lf-thread .lf-quote'],
            ['reply', '.lf-thread-panel.open .lf-thread .lf-msg-body'],
          ]) {
            const range = document.createRange();
            range.selectNodeContents(document.querySelector(sel));
            const selection = getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            out[name] = selection.toString().trim().length;
            selection.removeAllRanges();
          }
          return out;
        }"""
    )
    assert copyable["quote"] and copyable["reply"], (
        f"the panel stopped a user copying the words somebody said: {copyable}"
    )


def test_a_covering_auxiliary_surface_keeps_a_replacement_document_inert(
    browser, serve
):
    """A live version can update main without reopening the covering auxiliary surface.

    The modal boundary remains authoritative while the document changes, so the page
    cannot become a pointer or keyboard target while the sheet still claims modal
    semantics. Closing restores the updated document.
    """
    source = LONG_PAGE.replace('<h1 id="t">Long</h1>', f'<h1 id="t">Long</h1>{ONE_ASK}')
    url = serve(source)
    page = open_page(browser, live_url(url))
    resized(page, 500, 640)
    toggle_queue(page)
    assert bool(page.locator("dialog:modal").count())

    revised = source.replace(
        '<h1 id="t">Long</h1>', '<h1 id="t">Long after replacement</h1>'
    )
    stamp_page(serve.page_dir, revised, "replace the document")
    told(page)
    expect(page.locator("#t")).to_have_text("Long after replacement")

    state = page.evaluate(
        """() => ({
          covered: Boolean(document.querySelector('.lf-auxiliary-envelope:modal')),
          modal: document.querySelector('.lf-queue-panel').closest('dialog').matches(':modal'),
          focusInside: document.querySelector('.lf-queue-panel').contains(document.activeElement),
        })"""
    )
    assert state == {
        "covered": True,
        "modal": True,
        "focusInside": True,
    }, f"the updated document escaped its covering auxiliary surface: {state}"

    page.get_by_role("button", name="Close the On panel").click()
    expect(page.locator(".lf-queue-panel")).not_to_have_class(re.compile(r"\bopen\b"))
    assert not bool(page.locator("dialog:modal").count())


def test_the_shared_auxiliary_scrim_marks_and_dismisses_a_covering_surface(
    browser, serve, other_leaf
):
    """A covering auxiliary surface stands above a scrim covering every inert surface."""
    page = open_page(browser, serve(LONG_PAGE))
    resized(page, 1200, 700)
    scrim = page.locator(".lf-auxiliary-scrim")
    expect(scrim).to_be_hidden()

    leaves_door = banner_control(page, ".lf-others")
    leaves_door.click()
    leaves = page.locator(".lf-others-panel")
    expect(leaves).to_have_class(re.compile(r"\bopen\b"))
    expect(scrim).to_be_visible()
    assert bool(page.locator("dialog:modal").count())
    scrim_reading = page.evaluate(
        """() => {
          const scrim = document.querySelector('.lf-auxiliary-scrim');
          const banner = document.querySelector('.lf-banner');
          const bannerBox = banner.getBoundingClientRect();
          const scrimBox = scrim.getBoundingClientRect();
          const surface = document.querySelector('.lf-others-panel');
          const drawer = document.querySelector('.lf-others-panel').getBoundingClientRect();
          const point = {x: Math.max(drawer.right + 20, innerWidth * .75), y: innerHeight / 2};
          const bannerPoint = {
            x: bannerBox.left + bannerBox.width / 2,
            y: bannerBox.top + bannerBox.height / 2,
          };
          return {
            color: getComputedStyle(scrim).backgroundColor,
            point,
            hit: document.elementFromPoint(point.x, point.y) === scrim,
            top: scrimBox.top,
            coversBanner: scrimBox.top <= bannerBox.top && scrimBox.bottom >= bannerBox.bottom,
            bannerHit: document.elementFromPoint(bannerPoint.x, bannerPoint.y) === scrim,
            bannerLayer: Number(getComputedStyle(banner).zIndex),
            scrimLayer: Number(getComputedStyle(scrim).zIndex),
            surfaceLayer: Number(getComputedStyle(surface).zIndex),
          };
        }"""
    )
    assert scrim_reading["color"] != "rgba(0, 0, 0, 0)", scrim_reading
    assert scrim_reading["hit"], scrim_reading
    assert scrim_reading["top"] == 0, scrim_reading
    assert scrim_reading["coversBanner"], scrim_reading
    assert scrim_reading["bannerHit"], scrim_reading
    assert (
        scrim_reading["surfaceLayer"]
        > scrim_reading["scrimLayer"]
        > scrim_reading["bannerLayer"]
    ), scrim_reading
    page.mouse.click(scrim_reading["point"]["x"], scrim_reading["point"]["y"])
    expect(leaves).not_to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator(".lf-banner-more")).to_be_focused()
    expect(scrim).to_be_hidden()
    assert not bool(page.locator("dialog:modal").count())

    # Threads stands over the page at every width. Where it leaves a usable page beside
    # it, there is no scrim and that page stays live; where what it leaves is a sliver —
    # a 430px phone leaves ten pixels — it covers the page.
    threads_door = page.locator(".lf-threads-toggle")
    threads_door.click()
    panel_settled(page)
    for width in (1200, 760):
        resized(page, width, 700)
        panel_settled(page)
        expect(scrim).to_be_hidden()
        assert not bool(page.locator("dialog:modal").count())
    resized(page, 430, 700)
    panel_settled(page)
    expect(scrim).to_be_visible()
    assert bool(page.locator("dialog:modal").count())
    resized(page, 1200, 700)
    panel_settled(page)
    page.get_by_role("button", name="Close threads").click()
    panel_settled(page, open=False)
    expect(threads_door).to_be_focused()


# A classic scrollbar, which the headless shell hides unless both its flag is dropped
# and the page styles one, here through a constructed sheet.
CLASSIC_SCROLLBAR = """
  document.addEventListener('DOMContentLoaded', () => {
    const sheet = new CSSStyleSheet();
    sheet.replaceSync('::-webkit-scrollbar { width: 15px; }');
    document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
  });
"""


@pytest.mark.parametrize(("width", "covers"), [(730, True), (745, False)])
def test_threads_covering_a_page_holds_while_its_lock_takes_the_scrollbar(
    scrollbar_browser, serve, width, covers
):
    """The covering boundary locks the root's scroll, and a classic scrollbar leaves
    with the lock, widening the root's client box by the bar. Threads covers the page
    where it leaves less than a usable page (320px) beside it, and the window it asks
    that of counts the bar, so the answer is the same on both sides of the lock. At
    745px a reading of the client box would find 310px beside the default panel with
    the bar and 325px without it, so its answer would turn on whether the lock was
    already held (measured: it covered, and held the lock that made its own reading
    wrong). 730px covers on either reading. Each width is read across several syncs (a
    window resize runs one), and holds the one answer."""
    context = scrollbar_browser.new_context(viewport={"width": width, "height": 700})
    page = open_page(
        scrollbar_browser,
        serve(LONG_PAGE, comments=2),
        context=context,
        init_script=CLASSIC_SCROLLBAR,
    )
    bar = page.evaluate("() => innerWidth - document.documentElement.clientWidth")
    assert bar == 15, f"the page drew no classic scrollbar, so nothing is proved: {bar}"
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    readings = []
    for _ in range(4):
        page.evaluate("() => dispatchEvent(new Event('resize'))")
        rendered(page)
        readings.append(
            page.evaluate(
                """() => ({
                  modal: document.querySelector('.lf-thread-panel')
                    .closest('dialog').matches(':modal'),
                  covered: Boolean(document.querySelector('.lf-auxiliary-envelope:modal')),
                  locked: getComputedStyle(document.scrollingElement).overflowY
                    === 'hidden',
                })"""
            )
        )
    held = {"modal": covers, "covered": covers, "locked": covers}
    assert readings == [held] * 4, (
        f"the covering boundary at {width}px did not hold one answer across its "
        f"lock: {readings}"
    )


def test_page_and_panel_scroll_in_separate_regions(browser, serve):
    """The browser root scrolls the document and the panel keeps its own scrollport.

    Body is the page shell rather than a third scroll region. The panel stands over the
    page and takes no room from it, so the shell keeps the window's width while native
    document scrolling remains rooted in html."""
    page = open_page(browser, serve(LONG_PAGE, comments=30))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    geom = page.evaluate(
        """() => {
        const box = el => el.getBoundingClientRect();
        const body = document.body, threads = document.querySelector('.lf-threads');
        return { rootIsScroller: document.scrollingElement === document.documentElement,
                 rootScrolls: document.scrollingElement.scrollHeight > document.scrollingElement.clientHeight,
                 bodyOverflow: getComputedStyle(body).overflowY,
                 threadsScroll: threads.scrollHeight > threads.clientHeight,
                 bodyRight: """
        + SHELL_BOX
        + """.right,
                 window: document.documentElement.clientWidth };
    }"""
    )

    assert geom["rootIsScroller"] and geom["rootScrolls"]
    assert geom["bodyOverflow"] == "visible", geom
    assert geom["threadsScroll"], "the panel did not establish its own scrollport"
    assert geom["bodyRight"] == pytest.approx(geom["window"], abs=1), (
        f"the page yielded room to the panel standing over it: {geom}"
    )


@pytest.mark.parametrize(
    ("width", "quote", "stays_open"),
    [
        (1000, "left-words", True),
        (1000, "right-words", False),
        (1920, "right-words", True),
    ],
)
def test_a_quote_closes_the_panel_only_when_its_passage_would_land_under_it(
    browser, serve, width, quote, stays_open
):
    """Pressing a card's quote promises to show its passage. The panel stands over the
    right of the page, so a passage at the right of the column lands under it at a
    desktop width: there the panel makes way. A passage clear of the panel lands with
    the panel still open beside it, as does the same right-hand passage in a window
    wide enough that the panel stands over empty margin."""
    source = leaf_page(
        "quote travel",
        "<h1>Quote travel</h1>"
        '<p id="left">Left words open this line.</p>'
        + "".join(f"<p>Filler {i}. " + "Words. " * 30 + "</p>" for i in range(20))
        + '<p id="right" style="text-align: right">Right words close this line.</p>'
        + "".join(f"<p>Tail {i}. " + "Words. " * 30 + "</p>" for i in range(20)),
    )
    words = {
        "left-words": ("left", "Left words"),
        "right-words": ("right", "Right words"),
    }
    section, text = words[quote]
    page = open_page(browser, serve(source, anchored=[(section, text)]))
    resized(page, width, 800)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(".lf-threads > .lf-thread").first
    card.locator(":scope > .lf-thread-summary").click()
    card.locator(".lf-quote").click()
    if stays_open:
        expect(page.locator(".lf-thread-panel")).to_be_visible()
    else:
        panel_settled(page, open=False)
    page.wait_for_function(
        """() => { const m = [...CSS.highlights.get('lf-mark')][0].getClientRects()[0];
                   return m.top >= 0 && m.bottom <= innerHeight; }"""
    )
    if stays_open:
        panel_left = page.locator(".lf-thread-panel").bounding_box()["x"]
        mark_right = page.evaluate(
            "() => [...CSS.highlights.get('lf-mark')][0].getBoundingClientRect().right"
        )
        assert mark_right <= panel_left, "the passage landed under the open panel"


def test_covering_panel_takes_the_page_scroll_with_it(browser, serve):
    """Where the panel leaves no usable page it covers the page, and the covered page gives
    up scrolling: a wheel moves the sheet's thread list and never the page behind it. A
    quote is a promise to show a passage, so pressing one dismisses the covering sheet
    and lands on visible paper. The resize path reaches the same states, the posture
    being the panel's width against the window's and the panel stating only that it is
    open."""
    page = open_page(
        browser, serve(LONG_PAGE, comments=12, anchored=[("p40", "Paragraph 40.")])
    )
    resized(page, 400, 600)

    # A reading position first, so surviving the sheet is observable.
    page.mouse.move(120, 300)
    page.mouse.wheel(0, 600)
    page.wait_for_function("() => document.scrollingElement.scrollTop > 0")
    before = page.evaluate("() => document.scrollingElement.scrollTop")

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)

    # Two wheels over the sheet, one where it stands over the banner's row and one over
    # its list. Waiting on the second proves both were processed — input stays in order —
    # so the page having moved nothing is a real outcome rather than a race.
    page.mouse.move(60, 20)
    page.mouse.wheel(0, 400)
    page.mouse.move(300, 300)
    page.mouse.wheel(0, 400)
    page.wait_for_function("() => document.querySelector('.lf-threads').scrollTop > 0")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before, (
        "the page scrolled behind the covering sheet"
    )

    # Navigation closes the covering auxiliary surface before it positions the page. Doing the
    # same scroll behind the lock produces the right numbers and the wrong product: the
    # promised passage remains invisible.
    #
    # The document says where it came to rest as it comes to rest there, which is the
    # only thing that separates arriving from still travelling: the glide below reaches
    # its destination a frame or more before the browser calls it over, and a wheel sent
    # inside that window cancels the animation instead of scrolling — the user's notch
    # is spent stopping a glide that had already stopped moving.
    page.evaluate("""() => {
        window.lfRestedAt = null;
        addEventListener("scrollend", event => {
            if (event.target === document)
                window.lfRestedAt = document.scrollingElement.scrollTop;
        });
    }""")
    quote = page.locator(".lf-quote", has_text="Paragraph 40")
    thread_id = quote.evaluate("quote => quote.closest('.lf-thread').dataset.id")
    page.locator(f'.lf-thread[data-id="{thread_id}"] .lf-thread-summary').click()
    quote.click()
    panel_settled(page, open=False)
    # Arrived where it was aimed, which is the only thing about this the page states. A
    # text-passage destination reveals nested scrollports without writing the document,
    # then makes one smooth document glide to centre the painted range in the landable
    # space between the banner and shortcut bar. Centring is what
    # the runtime aimed for, so the mark reaching the middle is arrival, and a glide that
    # approaches it passes through no earlier position that could be taken for one.
    page.wait_for_function(
        """() => { const m = [...CSS.highlights.get('lf-mark')][0].getClientRects()[0];
                   const style = getComputedStyle(document.scrollingElement);
                   const top = parseFloat(style.scrollPaddingTop);
                   const bottom = innerHeight - parseFloat(style.scrollPaddingBottom);
                   return Math.abs(m.top + m.height / 2 - (top + bottom) / 2) < 1; }"""
    )
    # Centred, and the glide that centred it over: scrollend names the document's final
    # resting position rather than a sampled frame near it.
    page.wait_for_function(
        "() => window.lfRestedAt === document.scrollingElement.scrollTop"
    )
    at_mark = page.evaluate("() => document.scrollingElement.scrollTop")
    assert at_mark != before

    # Scrolling belongs to the visible page again immediately after that navigation.
    page.mouse.move(120, 300)
    page.mouse.wheel(0, 200)
    page.wait_for_function(f"() => document.scrollingElement.scrollTop > {at_mark}")

    # The resize path: narrowing onto an open panel locks, widening unlocks, and neither
    # takes room from the page.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    resized(page, 1000, 600)
    page.wait_for_function(
        "() => getComputedStyle(document.scrollingElement).overflowY !== 'hidden'"
        " && getComputedStyle(document.body).borderRightWidth === '0px'"
    )
    resized(page, 400, 600)
    page.wait_for_function(
        "() => getComputedStyle(document.scrollingElement).overflowY === 'hidden'"
        " && getComputedStyle(document.body).borderRightWidth === '0px'"
    )


def test_a_covering_sheet_cannot_move_the_background_shortcut_bar(browser, serve):
    """Composer growth leaves inert chrome fixed while live status keeps its room.

    The covering panel and shortcut bar can occupy the same viewport pixels, but they are
    not peers: modality puts the panel above the scrim and makes the bar inert background.
    Treating their rectangles as a collision made every newline in a composer inside the
    panel lift the unrelated bar by one line. A thread walk shows no position over that
    panel and takes no room from its list. Over a live page, the live bar yields the
    panel's actual width."""
    context = browser.new_context(
        viewport={"width": 400, "height": 900}, reduced_motion="reduce"
    )
    page = open_page(browser, serve(ADDRESSED_PAGE, comments=6), context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread").first
    thread.locator(":scope > .lf-thread-summary").focus()
    page.keyboard.press("c")
    field = thread.locator("leaf-text")
    expect(field).to_be_focused()
    write(field, "One line")
    rendered(page)

    def boxes():
        return page.evaluate("""() => {
            const rect = node => {
                const r = node.getBoundingClientRect();
                return {left: r.left, right: r.right, top: r.top, bottom: r.bottom,
                        height: r.height};
            };
            const list = document.querySelector(".lf-threads");
            const style = getComputedStyle(list);
            const standing = document.activeElement?.closest(".lf-thread");
            const bar = document.querySelector(".lf-shortcut-bar");
            const box = bar.getBoundingClientRect();
            const hit = document.elementFromPoint((box.left + box.right) / 2,
                                                 box.bottom - 1);
            return {shortcut_bar: rect(document.querySelector(".lf-shortcut-bar")),
                    panel: rect(document.querySelector(".lf-thread-panel")),
                    composer: rect(document.activeElement.closest("leaf-text")
                                   ?? document.body),
                    standingTitle: standing ? rect(document.activeElement) : null,
                    lineCovered: Boolean(document.querySelector("dialog:modal")) &&
                                 Boolean(bar.closest("[inert]")) && !bar.contains(hit),
                    viewportHeight: innerHeight,
                    listPad: parseFloat(style.paddingBottom),
                    listScrollPad: parseFloat(style.scrollPaddingBottom)};
        }""")

    one_line = boxes()
    assert one_line["lineCovered"], one_line
    assert page.evaluate("""() => {
      const held = document.activeElement;
      document.querySelector('.lf-shortcut-bar button').focus();
      return document.activeElement === held;
    }"""), "the suspended bar took focus from the foreground editor"
    assert one_line["shortcut_bar"]["right"] > one_line["panel"]["left"], (
        f"the fixture no longer exercises the overlapping lanes: {one_line}"
    )
    assert one_line["shortcut_bar"]["top"] < one_line["panel"]["bottom"], (
        f"the fixture no longer exercises the vertical overlap: {one_line}"
    )
    assert abs(one_line["shortcut_bar"]["bottom"] - one_line["viewportHeight"]) < 1, (
        one_line
    )

    write(field, "One line\nSecond line\nThird line")
    rendered(page)
    multiline = boxes()
    assert multiline["composer"]["height"] > one_line["composer"]["height"], (
        f"the composer did not grow: {one_line}, {multiline}"
    )
    assert multiline["shortcut_bar"] == one_line["shortcut_bar"], (
        f"growing the foreground composer moved the background shortcut bar: "
        f"{one_line}, {multiline}"
    )
    assert multiline["listPad"] < 20 and multiline["listScrollPad"] < 20, multiline

    # A thread walk over the panel puts no position over its list. Reach the last
    # thread through the real keyboard route: the list keeps its whole height.
    field.evaluate("field => field.blur()")
    page.locator(".lf-threads").focus()
    for _ in range(6):
        page.keyboard.press("t")
        rendered(page)
    expect(page.locator(".lf-bottom-status")).to_be_hidden()
    walked = boxes()
    assert walked["listPad"] < 20 and walked["listScrollPad"] < 20, walked
    assert walked["standingTitle"], walked

    # Over a live page, the bar is live page chrome and stops at the panel's edge.
    resized(page, 1200, 900)
    beside = boxes()
    assert not beside["lineCovered"], beside
    assert beside["shortcut_bar"]["right"] <= beside["panel"]["left"] + 1, (
        f"the line crossed into the panel standing over the page: {beside}"
    )


def test_covering_feedback_clears_the_reply_at_every_reading_position(browser, serve):
    """Feedback keeps one seat above a reply whether that reply is in view or not."""
    url = serve(LONG_PAGE)
    root = panel_comment(serve.page_dir, "Read this before replying. " * 80)
    context = browser.new_context(
        viewport={"width": 400, "height": 700}, reduced_motion="reduce"
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    card = page.locator(f'.lf-thread[data-id="{root}"]')
    write(card.locator("leaf-text"), "One line\nSecond line\nThird line")
    listing = page.locator(".lf-threads")
    listing.focus()
    assert listing.evaluate("n => n.scrollHeight > n.clientHeight")
    page.evaluate(
        "async () => (await window.__lfWidgetApi()).notice('Saved this reply', {announce:false})"
    )
    status = page.locator(".lf-bottom-status")
    expect(status).to_be_visible()
    places = []
    for end in (False, True):
        listing.evaluate("(n,end) => {n.scrollTop = end ? n.scrollHeight : 0}", end)
        rendered(page)
        places.append(status.bounding_box())
    assert places[0] == places[1], "scrolling the reply into view moved its feedback"
    assert (
        places[-1]["y"] + places[-1]["height"]
        < card.locator(".lf-thread-reply").bounding_box()["y"]
    )
