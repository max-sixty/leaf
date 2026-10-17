"""Where an open margin thread card stands beside its target, and how it holds still
through news, presses, reflows and scrolls, panes included."""

import re
from datetime import datetime, timedelta

import pytest
from leaf import thread as thread_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import ASK_PAGE, PANEL_PAGE, panel_comment
from render_cases_layout import banner_control
from render_harness import (
    EXAMPLES,
    ROOT,
    holding,
    leaf_page,
    margins_laid_out,
    open_page,
    panel_settled,
    resized,
    scroll_settled,
    scroll_writes,
    select,
    sending,
    ticked,
    told,
    write,
)

from browser.margin import (
    ACTION_ON_ASK,
    COMMENT_ON_ASK,
    LONG_THREAD_ROOT,
    PARAGRAPH_ON_ASK,
    WORDS_RIGHT,
    leave_card_by_its_target,
    resized_shell,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_thread_card_is_unseen_until_its_first_placement_lands(browser, serve):
    """An unplaced card is unseen; switching and closing retire its pending work."""
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    held = []
    context.route("**/vendor/floating-ui.esm.js", lambda route: held.append(route))
    page = open_page(
        browser,
        serve(
            ASK_PAGE,
            events=[
                COMMENT_ON_ASK,
                {
                    **COMMENT_ON_ASK,
                    "text": "Check the tools separately.",
                    "anchor": {"section": "tools"},
                },
            ],
        ),
        context=context,
        upgraded=False,
    )
    preview = page.locator(".lf-margin-preview")
    try:
        holding(page, held, 1, "the positioning module")
        first = page.locator('[data-lf-margin-for="bracket"] .lf-margin-marker')
        second = page.locator('[data-lf-margin-for="tools"] .lf-margin-marker')
        first.click()
        expect(preview).not_to_have_attribute("hidden", "")
        expect(preview).to_have_css("opacity", "0")
        expect(preview).to_have_css("pointer-events", "none")

        second.click()
        expect(preview).to_contain_text("Check the tools separately.")
        page.keyboard.press("Escape")
        expect(preview).to_be_hidden()
        page.locator(".lf-threads-toggle").focus()

        held.pop(0).continue_()
        rendered(page)
        expect(preview).to_be_hidden()
        expect(page.locator(".lf-threads-toggle")).to_be_focused()
        expect(preview).not_to_have_attribute("data-lf-thread-placement")

        first.click()
        expect(preview).to_have_attribute("data-lf-thread-placement", re.compile(r".+"))
        expect(preview).to_have_css("opacity", "1")
        expect(preview).to_have_css("pointer-events", "auto")
    finally:
        for route in held:
            route.continue_()
        context.unroute_all(behavior="wait")


@pytest.mark.parametrize("width", [1440, 2400])
def test_a_margin_card_clears_its_row_without_sacrificing_message_width(
    browser, serve, width
):
    """Only a full-width message leaves the margin row clear; a narrower message
    uses the row's space and reaches the visible edge."""
    page = open_page(browser, serve(ASK_PAGE, events=[PARAGRAPH_ON_ASK]))
    resized(page, width, 900)
    page.locator('.lf-margin-marker[data-lf-kinds="comment"]').click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_have_attribute("data-lf-thread-placement", re.compile(r".+"))
    rendered(page)
    geometry = page.evaluate(
        """() => {
          const controls = document.querySelector('[data-lf-kinds="comment"]')
            .closest('[data-lf-margin-for]').getBoundingClientRect();
          const card = document.querySelector('.lf-margin-preview');
          const box = card.getBoundingClientRect();
          return {controlsRight: controls.right, cardLeft: box.left,
                  cardRight: box.right, viewport: innerWidth,
                  preferred: parseFloat(getComputedStyle(card)
                    .getPropertyValue('--thread-card'))};
        }"""
    )
    past = (
        geometry["viewport"] - 8 - (geometry["controlsRight"] + 8)
        >= geometry["preferred"]
    )
    assert past == (width == 2400), geometry
    assert geometry["cardLeft"] == pytest.approx(
        (geometry["controlsRight"] if past else page.evaluate(WORDS_RIGHT)) + 8,
        abs=0.5,
    ), geometry
    assert geometry["cardRight"] == pytest.approx(
        geometry["viewport"] - 8
        if geometry["viewport"] - 8 - geometry["cardLeft"] < 592
        else geometry["cardLeft"] + 592,
        abs=0.5,
    ), geometry


PICK_UNDER_A_CARD = leaf_page(
    "Pick under a card",
    """
<h1 id="title">Pick under a card</h1>
<lf-ask id="ask">
  <h3>What should a phone's one-row banner hold?</h3>
  <lf-options id="choice" choose>
    <lf-option id="row"><strong>Status in words</strong> The status keeps its words
    on the row, cut short with an ellipsis where the sentence runs long.</lf-option>
    <lf-option id="two"><strong>Keep two rows</strong> The status keeps its
    sentence.</lf-option>
  </lf-options>
</lf-ask>
""",
)


def test_a_pick_under_an_open_card_leaves_the_card_where_it_stands(browser, serve):
    """The pick's receipt stands on the option group, whose top is level with the first
    option's, and it was seated above the option's thread row, pushing that row and the
    card standing on it down under the reader."""
    root = {**LONG_THREAD_ROOT, "anchor": {"section": "row"}}
    page = open_page(browser, serve(PICK_UNDER_A_CARD, events=[root]))
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1400, 900)
    thread = page.locator('[data-lf-margin-for="row"]')
    thread.locator(".lf-margin-marker").click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    rendered(page)
    where = "node => node.getBoundingClientRect().toJSON()"
    card, row = preview.evaluate(where), thread.evaluate(where)
    with sending(page, "the pick"):
        page.locator("#row").click(position={"x": 20, "y": 10})
    expect(
        page.locator('[data-lf-margin-for="choice"] .lf-margin-marker')
    ).to_have_attribute("aria-label", re.compile(r"^Sent\b"))
    for _ in range(2):
        rendered(page)
        assert preview.evaluate(where) == card
        assert thread.evaluate(where) == row
        # A later pass, which any repaint of the margin brings, moves nothing either.
        margins_laid_out(page)


def test_a_row_arriving_takes_the_room_below_the_markers_already_seated(browser, serve):
    """A pick's receipt is news to the thread marker beside the options: it lands in the
    room below that marker rather than seating itself first, from the top, and pushing
    the marker out from beside the option the user may press next."""
    root = {**LONG_THREAD_ROOT, "anchor": {"section": "row"}}
    page = open_page(browser, serve(PICK_UNDER_A_CARD, events=[root]))
    resized(page, 1400, 900)
    rendered(page)
    thread = page.locator('[data-lf-margin-for="row"]')
    where = "node => node.getBoundingClientRect().toJSON()"
    row = thread.evaluate(where)
    with sending(page, "the pick"):
        page.locator("#two").click(position={"x": 20, "y": 10})
    receipt = page.locator('[data-lf-margin-for="choice"]')
    expect(receipt.locator(".lf-margin-marker")).to_have_attribute(
        "aria-label", re.compile(r"^Sent\b")
    )
    rendered(page)
    assert thread.evaluate(where) == row
    assert receipt.evaluate(where)["top"] >= row["bottom"]
    stands = receipt.evaluate(where)
    # A later pass, which any repaint of the margin brings, moves neither, and nor does
    # the receipt being held where it stands.
    receipt.locator(".lf-margin-marker").hover()
    margins_laid_out(page)
    rendered(page)
    assert thread.evaluate(where) == row
    assert receipt.evaluate(where) == stands


@pytest.mark.watch_shifts
def test_an_open_card_takes_news_without_moving_its_controls(browser, serve):
    """The card keeps the width it opened at, so a longer step wraps inside it rather
    than carrying Resolve, Close and Send sideways. Read idle, a step shows at once and
    the card grows down past its reply row. While the user writes, a step and an
    answer wait behind the thread's notice, as a held reply does in a seat, so nothing
    moves. Pressing the notice shows them under the press: the head row stays and
    the card grows down, keeping the draft's words."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Make the banner quieter", {"section": "h-how"}
    )
    address = {"to": root, "for": root}
    thread_model.post_reply(
        serve.page_dir, address, "Reading the banner's styles.", ephemeral=True
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-margin-marker").first.click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    words = preview.locator(".lf-thread-working-words")
    expect(words).to_have_text("Reading the banner's styles")
    rendered(page)
    controls = {
        name: preview.get_by_role("button", name=name, exact=True)
        for name in ("Resolve thread", "Dismiss thread view")
    }
    opened = preview.bounding_box()
    boxes = {name: control.bounding_box() for name, control in controls.items()}

    long_step = (
        "Comparing the lighter weight against every banner the gallery shows, at each "
        "width the panel takes, before and after the change."
    )
    thread_model.post_reply(serve.page_dir, address, long_step, ephemeral=True)
    told(page)
    expect(words).to_contain_text("before and after the change")
    rendered(page)
    grown = preview.bounding_box()
    assert grown["width"] == pytest.approx(opened["width"], abs=0.5), (opened, grown)
    assert grown["y"] == pytest.approx(opened["y"], abs=0.5), (opened, grown)
    assert grown["height"] > opened["height"]
    for name, control in controls.items():
        assert control.bounding_box() == pytest.approx(boxes[name], abs=0.5), name

    editor = preview.locator("leaf-text")
    preview.get_by_role("textbox", name="Reply", exact=True).click()
    page.keyboard.type("Also check the dark scheme")
    rendered(page)
    writing = preview.bounding_box()
    send = preview.locator(".lf-thread-reply .lf-compose-submit")
    pinned = {name: control.bounding_box() for name, control in controls.items()}
    pinned["Send"] = send.bounding_box()
    pinned["editor"] = editor.bounding_box()

    thread_model.post_reply(
        serve.page_dir,
        address,
        "Measuring the status line's contrast in both schemes, against the paper and "
        "against the banner's own ground.",
        ephemeral=True,
    )
    told(page)
    notice = preview.locator(".lf-thread-notice-news")
    expect(notice).to_have_text("1 new update")
    expect(words).to_contain_text("before and after the change")
    thread_model.post_reply(
        serve.page_dir,
        address,
        "Done: the banner's status line is one weight lighter, and its title sets in "
        "the muted ink, so the banner reads as chrome rather than as the page's first "
        "heading in both schemes.",
    )
    told(page)
    expect(notice).to_contain_text("new reply")
    # It reads whole in the head row, before the card's actions.
    expect(
        preview.locator(".lf-margin-thread-controls .lf-thread-news")
    ).to_be_visible()
    assert notice.evaluate("node => node.scrollWidth <= node.clientWidth")
    rendered(page)
    assert preview.bounding_box() == pytest.approx(writing, abs=0.5)
    held = {name: control.bounding_box() for name, control in controls.items()}
    held["Send"] = send.bounding_box()
    held["editor"] = editor.bounding_box()
    for name, box in pinned.items():
        assert held[name] == pytest.approx(box, abs=0.5), name

    notice.click()
    expect(preview).to_contain_text("one weight lighter")
    assert editor.evaluate("box => box.value") == "Also check the dark scheme"
    rendered(page)
    for name, control in controls.items():
        assert control.bounding_box() == pytest.approx(held[name], abs=0.5), name
    assert editor.bounding_box()["y"] > held["editor"]["y"] + 20


# Each visible message head's time against what could cut it: its own box, the
# metadata it stands in and the head.
TIMES_WHOLE = """card => [...card.querySelectorAll('.lf-msg-head')]
  .filter((head) => head.checkVisibility())
  .map((head) => {
    const time = head.querySelector('time');
    const right = time.getBoundingClientRect().right;
    return {
      text: time.textContent,
      whole: time.scrollWidth <= time.clientWidth &&
        right <= time.parentElement.getBoundingClientRect().right + 0.5 &&
        right <= head.getBoundingClientRect().right + 0.5,
    };
  })"""


def test_a_card_s_head_row_cuts_the_name_before_the_time(browser, serve):
    """A card at its narrowest, with Previous and Next for its target's two threads,
    holding news while the user writes: the notice reads whole beside the actions, the
    message head's time stays whole, and the name gives up the room, with an ellipsis."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Make the banner quieter", {"section": "h-how"}
    )
    panel_comment(serve.page_dir, "Keep the logo where it is", {"section": "h-how"})
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-margin-marker").first.click()
    preview = page.locator(".lf-margin-preview")
    expect(preview.get_by_text("Make the banner quieter")).to_be_visible()
    preview.get_by_role("textbox", name="Reply", exact=True).click()
    page.keyboard.type("Also check the dark scheme")
    rendered(page)
    thread_model.post_reply(
        serve.page_dir,
        {"to": root, "for": root},
        "The status line can drop one weight.",
    )
    thread_model.post_reply(
        serve.page_dir, {"to": root}, "And the title the muted ink."
    )
    told(page)
    notice = preview.locator(".lf-margin-thread-controls .lf-thread-news")
    expect(notice).to_have_text("2 new replies")
    rendered(page)
    assert notice.evaluate("node => node.scrollWidth <= node.clientWidth")
    card = preview.locator(f'.lf-page-thread[data-thread="{root}"]')
    times = card.evaluate(TIMES_WHOLE)
    assert times and all(time["whole"] for time in times), times
    name = card.locator(".lf-msg-head b").first
    assert name.evaluate("node => node.scrollWidth > node.clientWidth")
    assert name.evaluate("node => getComputedStyle(node).textOverflow") == "ellipsis"


@pytest.mark.watch_shifts
def test_a_card_above_its_target_holds_news_it_would_grow_up_for(browser, serve):
    """A card standing above what it is about holds its foot, so a step would carry
    its head row and messages up: the step waits behind the thread's notice even with
    no draft, and shows when the user presses it."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Make the banner quieter", {"section": "m19"})
    address = {"to": root, "for": root}
    thread_model.post_reply(
        serve.page_dir, address, "Reading the banner's styles.", ephemeral=True
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.evaluate("scrollTo(0, document.scrollingElement.scrollHeight)")
    page.locator(".lf-margin-marker").first.click()
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_have_attribute("data-lf-thread-placement", "above")
    rendered(page)
    opened = preview.bounding_box()
    thread_model.post_reply(
        serve.page_dir,
        address,
        "Comparing the lighter weight against every banner the gallery shows, at each "
        "width the panel takes, before and after the change.",
        ephemeral=True,
    )
    told(page)
    notice = preview.locator(".lf-thread-notice-news")
    expect(notice).to_have_text("1 new update")
    rendered(page)
    assert preview.bounding_box() == pytest.approx(opened, abs=0.5)
    notice.click()
    expect(preview.locator(".lf-thread-working-words")).to_contain_text("the change")


@pytest.mark.watch_shifts
@pytest.mark.parametrize("how", ["press", "key"])
def test_a_press_in_the_card_keeps_the_pressed_spot_still(browser, serve, how):
    """What a press shows grows the card from where the user pressed, as a seat on
    the page grows: opening an answer's progress, by pointer or key, grows the card up
    past the disclosure, which stays where it was pressed. The hold ends with that
    input, so a draft typed next grows the card down from its head row."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Make the banner quieter", {"section": "h-how"}
    )
    address = {"to": root, "for": root}
    for words in ("Comparing the banner.", "Checking both schemes.", "Measuring."):
        thread_model.post_reply(serve.page_dir, address, words, ephemeral=True)
    thread_model.post_reply(serve.page_dir, address, "Done: the banner is quieter.")
    page = open_page(browser, url)
    resized(page, 1200, 900)
    page.locator(".lf-margin-marker").first.click()
    preview = page.locator(".lf-margin-preview")
    disclosure = preview.locator(".lf-summary-expand")
    expect(disclosure).to_have_text("Show 3 progress messages")
    rendered(page)
    pressed = disclosure.bounding_box()
    compact = preview.bounding_box()

    if how == "key":
        disclosure.focus()
        page.keyboard.press("Enter")
    else:
        disclosure.click()
    expect(disclosure).to_have_text("Hide 3 progress messages")
    expect(preview).to_contain_text("Checking both schemes")
    rendered(page)
    after = disclosure.bounding_box()
    assert (after["x"], after["y"]) == pytest.approx(
        (pressed["x"], pressed["y"]), abs=0.5
    )

    expanded = preview.bounding_box()
    assert expanded["height"] > compact["height"]
    if how == "key":
        page.keyboard.press("Enter")
    else:
        disclosure.click()
    expect(disclosure).to_have_text("Show 3 progress messages")
    rendered(page)
    assert preview.bounding_box()["height"] == pytest.approx(compact["height"], abs=0.5)
    expect(disclosure).to_be_focused()
    collapsed = disclosure.bounding_box()
    assert (collapsed["x"], collapsed["y"]) == pytest.approx(
        (after["x"], after["y"]), abs=0.5
    )

    close = preview.get_by_role("button", name="Dismiss thread view", exact=True)
    head = close.bounding_box()
    preview.get_by_role("textbox", name="Reply", exact=True).click()
    page.keyboard.type("Also check the dark scheme, " * 6, delay=0)
    rendered(page)
    assert close.bounding_box() == pytest.approx(head, abs=0.5)

    if how == "press":
        age = preview.locator(".lf-msg-meta time").last
        timestamp = datetime.fromisoformat(age.get_attribute("datetime"))
        page.clock.set_fixed_time(timestamp + timedelta(seconds=30))
        ticked(page)
        expect(age).to_have_text("just now")
        before_tick = disclosure.bounding_box()
        page.clock.set_fixed_time(timestamp + timedelta(seconds=60))
        ticked(page)
        expect(age).to_have_text("1m ago")
        rendered(page)
        assert disclosure.bounding_box()["x"] == pytest.approx(
            before_tick["x"], abs=0.5
        )


def test_the_shipped_long_thread_keeps_the_margin_and_its_height(browser, serve):
    """The shipped exchange stands beside its controls, and crosses them before it shrinks."""
    example = next(page for page in EXAMPLES if page.stem == "ship-review")
    page = open_page(browser, serve(example))
    page.emulate_media(reduced_motion="reduce")
    resized_shell(page, 1920, 900)
    marker = page.locator('[data-lf-margin-for="off-t-resync"] > .lf-margin-marker')
    expect(marker).to_have_count(1)
    expect(marker.locator("..")).to_have_attribute(
        "aria-label", re.compile(r"Page actions for section · iOS reconnect stall")
    )
    marker.evaluate(
        "marker => scrollBy(0, marker.getBoundingClientRect().top - innerHeight + 52)"
    )

    marker.click()
    preview = page.locator(".lf-margin-preview")
    thread = page.locator(".lf-margin-thread", has_text="One reconnect in forty")
    expect(preview).to_be_visible()
    expect(preview).to_have_attribute("aria-label", "Thread for iOS reconnect stall")
    expect(thread.locator(".lf-msg.user").first).to_be_visible()
    expect(thread.get_by_role("button", name="Open interactive reply")).to_have_count(1)
    expect(thread.locator(".lf-page-thread")).to_be_focused()
    geometry = marker.evaluate(
        """markerNode => {
          const main = document.querySelector('main').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          const controls = markerNode.closest('[data-lf-margin-for]').getBoundingClientRect();
          const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
          const reply = document.querySelector('.lf-margin-thread .lf-thread-reply')
            .getBoundingClientRect();
          const cardStyle = getComputedStyle(document.querySelector('.lf-margin-preview'));
          return {bannerBottom: banner.bottom, mainLeft: main.left,
                  mainRight: main.right, controlsRight: controls.right,
                  controlsTop: controls.top, controlsBottom: controls.bottom,
                  cardLeft: card.left, cardRight: card.right, cardTop: card.top,
                  cardBottom: card.bottom, cardWidth: card.width,
                  viewportRight: document.documentElement.clientWidth,
                  borderLeft: cardStyle.borderLeftWidth,
                  borderRight: cardStyle.borderRightWidth,
                  replyTop: reply.top, replyBottom: reply.bottom,
                  panelOpen: document.querySelector('.lf-thread-panel').classList.contains('open')};
        }"""
    )
    assert geometry["cardLeft"] >= page.evaluate(WORDS_RIGHT) + 7.5, geometry
    assert geometry["cardRight"] <= geometry["viewportRight"] - 7, geometry
    assert geometry["cardWidth"] >= 379, geometry
    assert geometry["cardTop"] >= geometry["bannerBottom"] + 7, geometry
    assert geometry["cardBottom"] <= 892, geometry
    assert geometry["replyTop"] >= geometry["cardTop"], geometry
    assert geometry["replyBottom"] <= geometry["cardBottom"], geometry
    assert geometry["borderLeft"] == geometry["borderRight"] == "1px", geometry
    assert not geometry["panelOpen"], geometry

    words = thread.locator(".lf-msg-body").first
    words_box = words.bounding_box()
    page.mouse.move(words_box["x"] + 1, words_box["y"] + 10)
    page.mouse.down()
    page.mouse.move(words_box["x"] + 180, words_box["y"] + 10, steps=10)
    page.mouse.up()
    selected = page.evaluate("getSelection().toString()")
    assert len(selected) > 10 and selected in words.inner_text(), selected

    thread.get_by_role("textbox", name="Reply", exact=True).click()
    send = preview.locator(".lf-compose-field > button:visible")
    send.focus()
    page.evaluate("() => dispatchEvent(new Event('resize'))")
    expect(send).to_be_focused()

    resized_shell(page, 1920, 480)
    # Containment is measured while the attached passage is in view; a card
    # follows its passage when that passage leaves the viewport.
    target = page.locator("#off-t-resync")
    target.scroll_into_view_if_needed()
    expect(target).to_be_in_viewport()
    rendered(page)
    expect(send).to_be_focused()
    expect(preview).to_be_visible()
    capped = preview.evaluate(
        """card => {
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          const box = card.getBoundingClientRect();
          const list = card.querySelector('.lf-thread-transcript');
          return {bannerBottom: banner.bottom, top: box.top, bottom: box.bottom,
                  clientHeight: list.clientHeight, scrollHeight: list.scrollHeight};
        }"""
    )
    assert capped["top"] >= capped["bannerBottom"] + 7, capped
    assert capped["bottom"] <= 472.5, capped
    assert capped["scrollHeight"] > capped["clientHeight"], capped
    # The thread scrolls while its opening metadata and settlement remain usable.
    metadata = preview.locator(".lf-margin-thread-controls")
    resolve = preview.get_by_role("button", name="Resolve thread", exact=True)
    metadata_box = metadata.bounding_box()
    resolve_box = resolve.bounding_box()
    preview.locator(".lf-thread-transcript").evaluate(
        "node => { node.scrollTop = node.scrollHeight; }"
    )
    ticked(page)
    scrolled_metadata = metadata.bounding_box()
    scrolled_resolve = resolve.bounding_box()
    assert scrolled_metadata["y"] >= capped["top"], scrolled_metadata
    assert scrolled_resolve["y"] >= capped["top"], scrolled_resolve
    assert scrolled_resolve["y"] + scrolled_resolve["height"] <= capped["bottom"], (
        scrolled_resolve
    )
    assert scrolled_resolve["y"] - scrolled_metadata["y"] == pytest.approx(
        resolve_box["y"] - metadata_box["y"], abs=0.5
    )
    resized_shell(page, 1920, 900)

    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    expect(preview).to_be_hidden()
    expect(page.locator(".lf-queue-panel")).to_have_class(re.compile(r"\bopen\b"))
    # Exchanging one auxiliary surface for another is lateral, so the drawer's Escape
    # lands on the page and the card it displaced is not put back up.
    page.keyboard.press("Escape")
    expect(page.locator(".lf-queue-panel")).not_to_have_class(re.compile(r"\bopen\b"))
    expect(preview).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")
    marker.click()
    expect(preview).to_be_visible()
    expect(thread.locator(".lf-page-thread")).to_be_focused()

    open_full = thread.get_by_role("button", name="Open interactive reply")
    open_full.focus()
    expect(open_full).to_be_focused()
    page.keyboard.press("Enter")
    panel_settled(page)
    expect(preview).to_be_hidden()
    expect(page.locator(".lf-thread-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator("#off-slip")).to_be_in_viewport()
    expect(page.locator("#off-slip-chase [role=checkbox]")).to_be_checked()
    page.get_by_role("button", name="Close threads").click()
    panel_settled(page, open=False)
    marker.focus()
    page.keyboard.press("Enter")
    expect(preview).to_be_visible()
    expect(preview.locator(".lf-page-thread")).to_be_focused()

    resized_shell(page, 1436, 900)
    beside = page.evaluate(
        """() => {
          const main = document.querySelector('main').getBoundingClientRect();
          const marker = document.querySelector('[data-lf-kinds="comment"]')
          const controls = marker.closest('[data-lf-margin-for]').getBoundingClientRect();
          const cardNode = document.querySelector('.lf-margin-preview');
          const card = cardNode.getBoundingClientRect();
          const list = cardNode.querySelector('.lf-thread-transcript');
          return {mainLeft: main.left, mainRight: main.right,
                  controlsRight: controls.right, controlsTop: controls.top,
                  controlsBottom: controls.bottom, cardLeft: card.left,
                  cardRight: card.right, cardTop: card.top,
                  cardBottom: card.bottom, cardWidth: card.width,
                  clipped: list.scrollHeight - list.clientHeight,
                  shellWidth: document.body.getBoundingClientRect().width};
        }"""
    )
    # This shell leaves less than the card's minimum beside the wide cluster, and more
    # right of the words, so the card stands there, across the cluster, at its whole
    # height.
    assert beside["shellWidth"] - 8 - beside["controlsRight"] < 320, beside
    assert beside["cardLeft"] >= page.evaluate(WORDS_RIGHT) + 7.5, beside
    assert beside["cardRight"] == pytest.approx(beside["shellWidth"] - 8, abs=0.5), (
        beside
    )
    assert beside["cardWidth"] >= 319, beside
    assert beside["clipped"] <= 0, beside

    resized(page, 1471, 900)
    expect(preview).to_be_visible()
    expect(marker).to_have_attribute("aria-controls", "lf-margin-preview")
    expect(marker).to_have_attribute("aria-expanded", "true")
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    leave_card_by_its_target(page)
    marker.hover()
    expect(preview).to_be_hidden()
    marker.click()
    expect(preview).to_be_visible()
    expect(page.locator(".lf-thread-panel")).to_be_hidden()

    leave_card_by_its_target(page)
    resized(page, 1280, 600)
    marker.evaluate("node => scrollBy(0, node.getBoundingClientRect().top - 330)")
    marker.click()
    preview.get_by_role("textbox", name="Reply", exact=True).click()
    editor = preview.locator("leaf-text")
    draft = "\n".join(
        f"Line {n}: " + "The reply keeps its complete editor visible. " * 2
        for n in range(18)
    )
    write(editor, draft)
    for edge, caret in [("ArrowLeft", 0), ("ArrowRight", len(draft))]:
        editor.press("ControlOrMeta+a")
        editor.press(edge)
        expect(editor).to_have_js_property("value", draft)
        assert editor.evaluate("node => node.selectionStart") == caret
        page.wait_for_function("""() => {
          const list = document.querySelector('.lf-margin-preview .lf-page-thread').getBoundingClientRect();
          const editor = document.querySelector('.lf-margin-preview leaf-text').getBoundingClientRect();
          const send = document.querySelector('.lf-margin-preview .lf-compose-submit').getBoundingClientRect();
          return editor.top >= list.top - 1 && editor.bottom <= list.bottom + 1
            && send.top >= list.top && send.bottom <= list.bottom + 1;
        }""")


def test_crossing_to_the_small_screen_keeps_the_card_by_its_pin(browser, serve):
    """The rail falling changes where a marker stands, not whether it does: the marker
    becomes a pin and the card it opened stays up beside it."""
    page = open_page(browser, serve(ASK_PAGE, events=[ACTION_ON_ASK, COMMENT_ON_ASK]))
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_be_visible()

    resized(page, 390, 760)
    margins_laid_out(page)
    row = marker.locator("xpath=ancestor::*[@data-lf-margin-for][1]")
    expect(row).to_have_attribute("data-lf-place", "pin")
    expect(marker).to_be_visible()
    expect(banner_control(page, ".lf-page-map-toggle")).to_be_visible()
    expect(card).to_be_visible()


def test_a_reflow_that_moves_a_marker_carries_its_open_card(browser, serve):
    """The card beside a cluster's words follows it when the page moves under it.

    The margin geometry owner places a row at its target before the paint of a
    reflow — a diagram finishing, an image arriving, a disclosure opening above
    the marker. The card is placed by the layout pass that the column's change of size
    runs, a frame behind. The reflow here is a section growing, which is what every one
    of those cases is to the margin.
    """
    width = 1440
    page = open_page(browser, serve(ASK_PAGE, events=[COMMENT_ON_ASK]))
    resized(page, width, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')
    marker.evaluate(
        "node => node.scrollIntoView({block: 'center', behavior: 'instant'})"
    )
    marker.click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_be_visible()
    placement = """() => {
      const marker = document.querySelector('.lf-margin-marker[data-lf-kinds="comment"]');
      const controls = marker.closest('[data-lf-margin-for]');
      const card = document.querySelector('.lf-margin-preview');
      const m = controls.getBoundingClientRect();
      const c = card.getBoundingClientRect();
      const main = document.querySelector('main');
      const words = main.getBoundingClientRect().right
        - parseFloat(getComputedStyle(main).paddingRight);
      return {marker: m.top, clear: c.left >= words + 7.5, words,
              cardLeft: c.left, cardTop: c.top};
    }"""
    before = page.evaluate(placement)
    assert before["clear"], before

    page.evaluate(
        "() => { document.getElementById('sec-mounts').style.paddingBottom = '48px'; }"
    )
    page.wait_for_function(
        """was => document.querySelector('.lf-margin-marker[data-lf-kinds="comment"]')
                 .getBoundingClientRect().top > was + 40""",
        arg=before["marker"],
    )
    margins_laid_out(page)
    after = page.evaluate(placement)
    assert after["marker"] > before["marker"] + 40, (before, after)
    assert after["clear"], after
    assert after["cardTop"] - before["cardTop"] == pytest.approx(
        after["marker"] - before["marker"], abs=0.5
    ), (before, after)


@pytest.mark.parametrize("transform", ["translate(30px, 40px)", "scale(0.25)"])
def test_a_card_under_a_containing_block_stands_beside_its_cluster(
    browser, serve, transform
):
    """The card's rule is worked out in client coordinates, and Floating UI carries it
    into the card's positioning space. A transformed ancestor is a containing block for
    the fixed card, so a spot or a length written as a client one would be moved or
    scaled by the transform; carried across, the card stays where and as wide as the
    rule put it."""
    page = open_page(browser, serve(ASK_PAGE, events=[PARAGRAPH_ON_ASK]))
    resized(page, 1920, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')
    marker.evaluate(
        "node => node.scrollIntoView({block: 'center', behavior: 'instant'})"
    )
    marker.click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_have_attribute("data-lf-thread-placement", "right")
    offset = """() => {
      const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
      const controls = document.querySelector('.lf-margin-marker[data-lf-kinds="comment"]')
        .closest('[data-lf-margin-for]').getBoundingClientRect();
      return {left: card.left - controls.left, top: card.top - controls.top,
              width: card.width};
    }"""
    before = page.evaluate(offset)
    page.evaluate(
        """transform => {
          const card = document.querySelector('.lf-margin-preview');
          // A block the size of the window, as a transformed body would be.
          const block = document.createElement('div');
          block.style.cssText = 'position: fixed; inset: 0; pointer-events: none';
          block.style.transform = transform;
          card.before(block);
          block.append(card);
        }""",
        transform,
    )
    page.evaluate("() => dispatchEvent(new Event('resize'))")
    rendered(page)
    after = page.evaluate(offset)
    if transform == "scale(0.25)":
        # The card's lengths are its own, so its measure shrinks with the transform
        # while it stands where it did.
        measure = page.evaluate(
            "() => parseFloat(getComputedStyle(document.documentElement)"
            ".getPropertyValue('--thread-card'))"
        )
        before = {**before, "width": measure * 0.25}
    assert after == pytest.approx(before, abs=0.5), (before, after)


QUOTED_ON_ASK = {
    **COMMENT_ON_ASK,
    "anchor": {"section": "sec-mounts", "quote": "one came down in January"},
}


def test_a_focused_thread_covers_the_pages_choice_hints(browser, serve):
    """A fallback chip for a covered option stays behind the focused discussion."""
    page = open_page(
        browser, serve(ROOT / "tests/fixtures/pages/thread-choice-hints.html")
    )
    resized(page, 741, 838)
    page.keyboard.press("Tab")
    page.locator(".lf-margin-marker").first.focus()
    page.keyboard.press("Enter")
    card = page.locator(".lf-margin-preview .lf-page-thread")
    expect(card).to_be_focused()
    chip = page.locator(".lf-command-binding-badge").filter(has_text=re.compile("^2$"))
    expect(chip).to_have_count(1)
    rendered(page)
    paint = chip.evaluate(
        """chip => {
          const card = document.querySelector('.lf-margin-preview');
          const box = chip.getBoundingClientRect();
          const x = box.left + box.width / 2, y = box.top + box.height / 2;
          const frame = card.getBoundingClientRect();
          // The hint is normally pointer-transparent. Include it in the browser's
          // hit test to read its paint order against the thread without moving it.
          chip.style.pointerEvents = 'auto';
          const top = document.elementFromPoint(x, y);
          chip.style.removeProperty('pointer-events');
          return {
            overlaps: x > frame.left && x < frame.right &&
              y > frame.top && y < frame.bottom,
            covered: card.contains(top),
          };
        }"""
    )
    assert paint == {"overlaps": True, "covered": True}, paint
    # Reading the thread keeps the reply's own hint and keyboard route usable.
    expect(card.locator(".lf-compose-placeholder > .lf-key-badge")).to_have_text("c")
    page.keyboard.press("c")
    expect(card.locator("leaf-text")).to_be_focused()


def test_a_scroll_that_carries_the_card_writes_nothing(browser, serve):
    """A scroll the card rides with its cluster leaves the page's DOM as it was: the
    card, its target's trace, the marks, and the Ask's binding badges stand in the plane
    the scroll carries them with, and each owner on the scroll path writes only what
    changed. Chrome repaints the whole document for any write while a highlight holds a
    range, which a page with a quoted comment always has."""
    page = open_page(browser, serve(ASK_PAGE, events=[COMMENT_ON_ASK, QUOTED_ON_ASK]))
    resized(page, 1440, 600)
    marker = page.locator('[data-lf-margin-for="bracket"] .lf-margin-marker')
    marker.evaluate(
        "node => node.scrollIntoView({block: 'center', behavior: 'instant'})"
    )
    marker.click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_have_attribute("data-lf-plane", "page")
    offset = """() =>
      document.querySelector('.lf-margin-preview').getBoundingClientRect().top -
      document.querySelector('[data-lf-margin-for="bracket"]').getBoundingClientRect().top"""
    before = page.evaluate(offset)
    writes = scroll_writes(page, (-20, -20, 20, 20, 20))
    assert writes == [], writes
    assert page.evaluate(offset) == pytest.approx(before, abs=0.5)


@pytest.mark.parametrize("target", ["sec-mounts", "bracket"])
def test_a_card_beside_an_element_scrolled_past_its_top_waits_at_the_windows_top(
    browser, serve, target
):
    """Beside an element, a card stays level with some line of it. A scroll that takes
    the element's top past the window's, with the rest still showing, leaves the card
    held at the window's top, below the banner, in the window's plane, so the scroll
    writes nothing. Stood level with the element's clipped top instead, the card sat
    under the banner in the page's plane: the browser carried it with each scroll
    frame and the next placement pulled it back, and Shift+a up to an Ask with a
    thread shook its card. Once the element's foot passes the window's top, the card
    leaves with it. On an Ask's options, the binding badge the banner holds in stands
    in the window's plane too, for the same reason."""
    comment = {**COMMENT_ON_ASK, "anchor": {"section": target}}
    # Give the last Ask room to pass above the viewport before scroll reaches the
    # document's end; the fixture otherwise stops with #bracket still visible.
    source = ASK_PAGE.replace(
        "</main>", '<div style="height: 800px" aria-hidden="true"></div></main>'
    )
    page = open_page(browser, serve(source, events=[comment]))
    resized(page, 1440, 600)
    marker = page.locator(f'[data-lf-margin-for="{target}"] .lf-margin-marker')
    marker.evaluate(
        "node => node.scrollIntoView({block: 'center', behavior: 'instant'})"
    )
    marker.click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_have_attribute("data-lf-thread-placement", "right")
    reading = """async id => {
      const geometry = await window.__lfWidgetApi();
      const target = document.getElementById(id).getBoundingClientRect();
      return {
        card: document.querySelector('.lf-margin-preview').getBoundingClientRect().top,
        top: target.top, bottom: target.bottom,
        window: geometry.shownWindow({gap: 8}).top,
      };
    }"""

    def scroll_by(by):
        page.mouse.wheel(0, by)
        scroll_settled(page)
        rendered(page)
        return page.evaluate(reading, target)

    at = page.evaluate(reading, target)
    assert at["bottom"] - at["top"] > 60, at
    at = scroll_by(at["top"] - at["window"] + 20)
    expect(card).to_have_attribute("data-lf-plane", "window")
    assert at["card"] == pytest.approx(at["window"], abs=0.5), at
    writes = scroll_writes(page, (5, 5, -5, 5))
    assert writes == [], writes
    at = page.evaluate(reading, target)
    assert at["card"] == pytest.approx(at["window"], abs=0.5), at
    at = scroll_by(at["bottom"] - at["window"] + 20)
    assert at["bottom"] < at["window"], at
    expect(card).to_have_attribute("data-lf-plane", "page")
    assert at["card"] == pytest.approx(at["bottom"], abs=0.5), at


PANE_FILLER = "".join(
    f"<p>Filler paragraph {i} about the release.</p>" for i in range(12)
)


PANE_PAGE = leaf_page(
    "Release pane",
    f"""<div><h1>Release</h1>
<lf-pane id="evidence" label="Evidence"><div id="pane-body">
{PANE_FILLER}
<section id="pane-sec"><h2>Rollout</h2><p>One.</p><p>Two.</p><p>Three.</p><p>Four.</p>
</section>
{PANE_FILLER}
</div></lf-pane>
{PANE_FILLER}</div>""",
    head="<style>#pane-body { height: 420px; overflow: auto; }</style>",
    layout="sidebar",
)


def test_a_card_a_panes_edge_holds_stays_put_as_the_pane_scrolls(browser, serve):
    """A card under an element in a scrolling pane, held in by the pane's foot, stands
    in the pane's plane: it is anchored to the pane, which the pane's own scroll does not
    move, so that scroll writes nothing to the card. Read as the page's plane, the card
    was anchored to the element, carried up with each scroll frame, and placed back. A
    scroll of the page carries the pane and the card together, and keeps the card's
    side, which the pane's size holds rather than where the page shows it."""
    comment = {**COMMENT_ON_ASK, "anchor": {"section": "pane-sec"}}
    page = open_page(browser, serve(PANE_PAGE, events=[comment]))
    resized(page, 1440, 900)
    page.evaluate("() => document.getElementById('pane-sec').scrollIntoView()")
    page.locator('[data-lf-margin-for="pane-sec"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_have_attribute("data-lf-thread-placement", "below")
    reading = """() => ({
      card: document.querySelector('.lf-margin-preview').getBoundingClientRect().top,
      bottom: document.getElementById('pane-sec').getBoundingClientRect().bottom,
      foot: document.getElementById('pane-body').getBoundingClientRect().bottom,
    })"""
    at = page.evaluate(reading)
    page.evaluate(
        "by => document.getElementById('pane-body').scrollBy(0, by)",
        at["bottom"] - at["foot"] + 60,
    )
    rendered(page)
    expect(card).to_have_attribute("data-lf-plane", "region")
    before = page.evaluate(reading)
    writes = scroll_writes(
        page, (5, 5, -5, 5), scroller="document.getElementById('pane-body')"
    )
    assert not [
        w for w in writes if any("lf-margin-preview" in step for step in w["target"])
    ], writes
    assert page.evaluate(reading)["card"] == pytest.approx(before["card"], abs=0.5)
    before = page.evaluate(reading)
    writes = scroll_writes(page, (5, 5, -5, 5))
    assert not [
        w for w in writes if any("lf-margin-preview" in step for step in w["target"])
    ], writes
    expect(card).to_have_attribute("data-lf-thread-placement", "below")
    after = page.evaluate(reading)
    assert after["card"] - after["foot"] == pytest.approx(
        before["card"] - before["foot"], abs=0.5
    )


NESTED_PANE_PAGE = leaf_page(
    "Nested panes",
    f"""<div><h1>Release</h1>
<lf-pane id="evidence" label="Evidence"><div id="pane-body">
{PANE_FILLER}
<div id="inner" data-bound="start" style="height: 700px">
{PANE_FILLER}
<section id="pane-sec"><h2>Rollout</h2><p>One.</p><p>Two.</p><p>Three.</p><p>Four.</p>
</section>
{PANE_FILLER}{PANE_FILLER}
</div>
{PANE_FILLER}
</div></lf-pane></div>""",
    head="<style>#pane-body { height: 300px; overflow: auto; }</style>",
    layout="sidebar",
)


def test_a_card_an_outer_panes_edge_holds_stands_in_that_panes_plane(browser, serve):
    """Inside a bounded block that itself scrolls inside a pane, the edge holding the
    card in can be the outer pane's, which clips the inner block. The card is anchored
    to the box whose edge holds it, so the outer pane's scroll writes nothing to it."""
    comment = {**COMMENT_ON_ASK, "anchor": {"section": "pane-sec"}}
    page = open_page(browser, serve(NESTED_PANE_PAGE, events=[comment]))
    resized(page, 1440, 900)
    page.evaluate(
        """() => {
          const pane = document.getElementById('pane-body');
          const inner = document.getElementById('inner');
          const box = (node) => node.getBoundingClientRect();
          pane.scrollTop += box(inner).top - box(pane).top - 10;
          const sec = document.getElementById('pane-sec');
          inner.scrollTop += box(sec).top - box(inner).top - 20;
        }"""
    )
    rendered(page)
    page.locator('[data-lf-margin-for="pane-sec"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    expect(card).to_have_attribute("data-lf-thread-placement", "below")
    reading = """() => ({
      card: document.querySelector('.lf-margin-preview').getBoundingClientRect().top,
      bottom: document.getElementById('pane-sec').getBoundingClientRect().bottom,
      foot: document.getElementById('pane-body').getBoundingClientRect().bottom,
    })"""
    at = page.evaluate(reading)
    page.evaluate(
        "by => document.getElementById('inner').scrollBy(0, by)",
        at["bottom"] - at["foot"] + 60,
    )
    rendered(page)
    expect(card).to_have_attribute("data-lf-plane", "region")
    before = page.evaluate(reading)
    writes = scroll_writes(
        page, (5, 5, -5, 5), scroller="document.getElementById('pane-body')"
    )
    assert not [
        w for w in writes if any("lf-margin-preview" in step for step in w["target"])
    ], writes
    assert page.evaluate(reading)["card"] == pytest.approx(before["card"], abs=0.5)


def test_the_paint_over_a_target_in_panes_rides_each_panes_scroll(browser, serve):
    """The trace and the mark drawn over an element inside nested scrolling panes stand
    in frames cut to each pane's band, each carried by the scrolls around the pane holding
    it (target-paint-geometry.js, `paintStand`). A scroll of either pane writes nothing to
    them and leaves them over the element. Drawn in the document's plane from the
    element's box as the panes cut it, they were rewritten on every scroll step, a frame
    behind the words."""
    comment = {**COMMENT_ON_ASK, "anchor": {"section": "pane-sec"}}
    page = open_page(browser, serve(NESTED_PANE_PAGE, events=[comment]))
    resized(page, 1440, 900)
    page.evaluate(
        """() => {
          const pane = document.getElementById('pane-body');
          const inner = document.getElementById('inner');
          const box = (node) => node.getBoundingClientRect();
          pane.scrollTop += box(inner).top - box(pane).top - 10;
          const sec = document.getElementById('pane-sec');
          inner.scrollTop += box(sec).top - box(inner).top - 20;
        }"""
    )
    rendered(page)
    page.locator('[data-lf-margin-for="pane-sec"] .lf-margin-marker').click()
    for paint in (".lf-target-trace", ".lf-visual-mark-here"):
        expect(page.locator(paint)).to_be_visible()
    offsets = """() => {
      const target = document.getElementById('pane-sec').getBoundingClientRect();
      return ['.lf-target-trace', '.lf-visual-mark-here'].map((paint) => {
        const box = document.querySelector(paint).getBoundingClientRect();
        return [box.left - target.left, box.top - target.top, box.width, box.height];
      }).flat();
    }"""
    at = page.evaluate(offsets)
    for scroller in ("inner", "pane-body"):
        writes = scroll_writes(
            page,
            (5, 5, -5, 5),
            scroller=f"document.getElementById('{scroller}')",
        )
        painted = [
            w
            for w in writes
            if any(
                re.search(r"lf-(target-trace|visual-mark|paint)", step)
                for step in w["target"]
            )
        ]
        assert painted == [], (scroller, painted)
        assert page.evaluate(offsets) == pytest.approx(at, abs=0.5), scroller
    # Words arriving below the element lengthen what the inner block can scroll through,
    # and tell the paint nothing, which stays on the element, as does the scroll that
    # follows.
    page.evaluate(
        """() => document.getElementById('inner')
          .insertAdjacentHTML('beforeend', '<p>Arrived.</p>'.repeat(30))"""
    )
    rendered(page)
    assert page.evaluate(offsets) == pytest.approx(at, abs=0.5)
    scroll_writes(page, (5, 5), scroller="document.getElementById('inner')")
    assert page.evaluate(offsets) == pytest.approx(at, abs=0.5)


def test_a_scroll_that_carries_the_response_bar_writes_nothing(browser, serve):
    """The response bar a selection raises rides a scroll with its passage in the same
    plane, writing nothing, as the card does."""
    page = open_page(browser, serve(ASK_PAGE, events=[QUOTED_ON_ASK]))
    resized(page, 1440, 600)
    words = page.locator("#heater-p")
    words.evaluate(
        "node => node.scrollIntoView({block: 'center', behavior: 'instant'})"
    )
    box = words.bounding_box()
    y = box["y"] + 10
    select(page, (box["x"] + 2, y), (box["x"] + 120, y))
    bar = page.locator(".lf-fab-bar")
    expect(bar).to_be_visible()
    expect(bar).to_have_attribute("data-lf-plane", "page")
    offset = """() => document.querySelector('.lf-fab-bar').getBoundingClientRect().top -
      document.querySelector('#heater-p').getBoundingClientRect().top"""
    before = page.evaluate(offset)
    writes = scroll_writes(page, (-20, -20, 20, 20, 20))
    assert writes == [], writes
    assert page.evaluate(offset) == pytest.approx(before, abs=0.5)
