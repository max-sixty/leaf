"""Added-option presentation and replay tests."""

import base64
import re

import pytest
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_cases_interaction import (
    ASK_PAGE,
    ASK_WITH_CONTEXT_PAGE,
    sent_events,
)
from render_cases_layout import (
    button_radius,
    token_colour,
)
from render_harness import (
    EXAMPLE_MEDIA,
    STORED_DRAFT_TEXT,
    consume_browser_errors,
    holding,
    open_page,
    round_trip,
    sending,
    told,
    undo,
)

pytestmark = pytest.mark.nightly


def test_an_add_field_reconnects_to_its_shared_draft(browser, serve, one_reader):
    """Moving the widget restores draft delivery without duplicating its form."""
    url = serve(ASK_PAGE)
    first = open_page(browser, url, context=one_reader)
    second = open_page(browser, url, context=one_reader)

    second.evaluate("""() => {
        const group = document.getElementById("jobs");
        group.remove();
        document.querySelector("main").append(group);
    }""")
    text = "A shared answer after the question moves."
    first.locator("#jobs > .lf-another textarea").fill(text)

    expect(second.locator("#jobs > .lf-another")).to_have_count(1)
    expect(second.locator("#jobs > .lf-another textarea")).to_have_value(text)
    first.close()
    second.close()


def test_the_add_field_previews_the_option_it_will_make(browser, serve):
    """The reader writes on the same line and in the same voice as the options.

    The trailing action stays out of an empty row, then submits on the shared margin entry
    corner rather than borrowing the selection mark's circle. It remains a full-sized
    pointer target aligned with the last line as the textarea grows.
    """
    page = open_page(browser, serve(ASK_PAGE))
    option = page.locator("#job-camera")
    form = page.locator("#jobs > .lf-another")
    field = form.get_by_role("textbox", name="Another option", exact=True)
    add = form.get_by_role("button", name="Add option", exact=True, include_hidden=True)

    typography = """el => { const s = getComputedStyle(el);
                             return [s.fontFamily, s.fontSize, s.lineHeight]; }"""
    assert field.evaluate(typography) == option.evaluate(typography)
    option_text_x = option.evaluate(
        """el => {
             const text = [...el.childNodes].find(
               n => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
             const range = document.createRange();
             range.selectNodeContents(text);
             return range.getBoundingClientRect().x;
           }"""
    )
    assert abs(field.bounding_box()["x"] - option_text_x) < 0.5
    inner_height = """el => { const s = getComputedStyle(el);
                               return el.getBoundingClientRect().height
                                 - parseFloat(s.borderTopWidth)
                                 - parseFloat(s.borderBottomWidth); }"""
    assert abs(form.evaluate(inner_height) - option.evaluate(inner_height)) < 0.5

    card_words = page.locator("#br-steel > strong")
    card_field = page.locator("#bracket > .lf-another textarea")
    assert card_field.evaluate(typography) == card_words.evaluate(typography)
    assert abs(card_field.bounding_box()["x"] - card_words.bounding_box()["x"]) < 0.5

    expect(add).to_have_text("")
    expect(add.locator('svg[data-lf-icon="add"]')).to_have_count(1)
    expect(add).to_be_hidden()
    expect(add).to_have_attribute("aria-disabled", "true")
    empty_field_box = field.bounding_box()
    field.fill("Portrait sketch")
    expect(add).to_be_visible()
    expect(add).to_have_attribute("aria-disabled", "false")
    expect(add).to_have_css("opacity", "1")
    aim_floor = page.locator("html").evaluate(
        "el => parseFloat(getComputedStyle(el).getPropertyValue('--aim-floor'))"
    )
    form_box = form.bounding_box()
    field_box = field.bounding_box()
    assert field_box == empty_field_box
    add_box = add.bounding_box()
    assert add_box["width"] >= aim_floor
    assert add_box["height"] >= aim_floor
    assert 0 < form_box["y"] + form_box["height"] - add_box["y"] - add_box["height"] < 8
    field.fill("First line\nSecond line\nThird line")
    grown_form_box = form.bounding_box()
    grown_field_box = field.bounding_box()
    grown_add_box = add.bounding_box()
    assert grown_field_box["height"] > field_box["height"]
    assert (
        0
        < grown_form_box["y"]
        + grown_form_box["height"]
        - grown_add_box["y"]
        - grown_add_box["height"]
        < 8
    )
    face = add.evaluate(
        """el => {
          const button = getComputedStyle(el);
          const fill = getComputedStyle(el, '::before');
          return {
            button: button.backgroundColor,
            glyph: button.color,
            fill: fill.backgroundColor,
            fillWidth: fill.width,
            radius: fill.borderRadius,
          };
        }"""
    )
    circle_radius = page.locator("#br-steel .lf-pick").evaluate(
        "el => getComputedStyle(el, '::before').borderRadius"
    )
    assert circle_radius == "50%"
    assert face["button"] == "rgba(0, 0, 0, 0)"
    assert face["radius"] == button_radius(page)
    assert face["radius"] != circle_radius
    # This press is the composer's glyph action, so it wears that face: the accent as its
    # own ink, over a disc that stays clear until the pointer is on it. The mark therefore
    # reads against the page rather than against a disc, and it is the ink that says the
    # press is live — the disc says the same thing in both states and cannot.
    assert face["fill"] == face["button"] == "rgba(0, 0, 0, 0)"
    assert face["glyph"] == token_colour(page, "--accent")
    page.keyboard.press("Tab")
    expect(add).to_be_focused()

    page.locator("html").evaluate("el => el.style.setProperty('--aim-floor', '44px')")
    form_box = form.bounding_box()
    add_box = add.bounding_box()
    assert form_box["height"] >= 44
    assert add_box["y"] >= form_box["y"]
    assert add_box["y"] + add_box["height"] <= form_box["y"] + form_box["height"]
    # A coarse pointer widens what the reader may hit, not what the page draws: the press
    # keeps painting nothing of its own, so the disc stays the size it was rather than
    # becoming a square as wide as its target.
    coarse = add.evaluate(
        """el => ({
             button: getComputedStyle(el).backgroundColor,
             fillWidth: getComputedStyle(el, '::before').width,
           })"""
    )
    assert add_box["width"] >= 44
    assert coarse["button"] == "rgba(0, 0, 0, 0)"
    assert coarse["fillWidth"] == face["fillWidth"]


def test_the_draft_send_press_holds_the_row_s_inline_end(browser, serve):
    """Both presentations of the group end the draft row where every text box ends.

    A binding badge is off screen until a reader asks for bindings, so a layout that
    gives it the row's edge and seats the press inside it reads, for almost the whole of
    a page's life, as a send button that missed the corner. The badge waits inside the
    press instead, in room the draft's own trailing padding already holds, so asking for
    bindings still moves nothing.
    """
    page = open_page(browser, serve(ASK_PAGE))
    # The second Ask carries the card presentation, which is where the row's trailing
    # room is contested: its options wear their binding badges at the corner, so the
    # draft's badge is the one that had the edge.
    page.keyboard.press("a")
    page.keyboard.press("a")
    expect(page.locator("#bracket > .lf-another > .lf-key-badge")).to_be_visible()
    shown = page.locator("#bracket > .lf-another").evaluate(
        """el => {
             const press = el.querySelector('.lf-compose-submit').getBoundingClientRect();
             const mark = el.querySelector('.lf-key-badge').getBoundingClientRect();
             return {inside: press.left - mark.right, right: press.right};
           }"""
    )
    assert shown["inside"] > 0, shown

    page.keyboard.press("Escape")
    gaps = {}
    for group in ("#jobs", "#bracket"):
        row = page.locator(f"{group} > .lf-another")
        row.locator("textarea").fill("Something the author missed")
        expect(row.locator(".lf-compose-submit")).to_be_visible()
        gaps[group] = row.evaluate(
            """el => {
                 const style = getComputedStyle(el);
                 const inner = el.getBoundingClientRect().right
                   - parseFloat(style.borderRightWidth);
                 const press = el.querySelector('.lf-compose-submit');
                 return {
                   end: inner - press.getBoundingClientRect().right,
                   right: press.getBoundingClientRect().right,
                 };
               }"""
        )
    assert abs(gaps["#jobs"]["end"] - gaps["#bracket"]["end"]) < 0.5, gaps
    assert 0 <= gaps["#bracket"]["end"] < 8, gaps
    # Writing in the row and putting the bindings away leave the press where the badge
    # found it: the room is held whether or not anything is standing in it.
    assert abs(gaps["#bracket"]["right"] - shown["right"]) < 0.5, (gaps, shown)


def test_an_option_mark_keeps_addition_and_clarification_as_separate_routes(
    browser, serve
):
    """The add form stays in Tab order while c opens a clarification thread."""
    url = serve(ASK_WITH_CONTEXT_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "revision": 1,
            "anchor": {"section": "storage-options"},
            "text": "Archive them locally or remotely?",
        },
    )

    page = open_page(browser, url)
    mark = page.locator("#storage-evict .lf-pick")
    mark.focus()
    expect(mark).to_be_focused()
    expect(page.locator("#storage-options > .lf-conversation")).to_have_count(0)

    # Enter is not navigation from a checkbox. It neither chooses the option nor enters
    # the add field; the field is an ordinary later stop in the Tab order.
    page.keyboard.press("Enter")
    expect(mark).to_be_focused()
    expect(page.locator("#storage-options > .lf-another textarea")).not_to_be_focused()
    expect(page.locator("#storage-options > lf-option[chosen]")).to_have_count(0)

    # c keeps its page-wide meaning: it comments on the focused option rather than adding
    # an answer. Its own Escape restores the same mark.
    page.keyboard.press("c")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator("#storage-options > .lf-another textarea")).not_to_be_focused()
    page.keyboard.press("Escape")
    expect(mark).to_be_focused()


def test_another_option_becomes_a_real_option_without_starting_a_thread(browser, serve):
    """The answer the author missed joins the control and travels as selection state.

    It is not a comment with a special response contract: the reader has supplied an
    answer, not opened a conversation. The standing action carries every generated
    option so a later ordinary pick and a reload retain the same set of alternatives.
    """
    url = serve(ASK_PAGE)
    page = open_page(browser, url)
    d = serve.page_dir

    expect(page.locator("#jobs > .lf-conversation")).to_have_count(0)
    added = page.locator("#jobs > .lf-another")
    assert added.count() == 1, (
        f"the add-option cell was not rendered: {page.lf_errors}; "
        f"group={page.locator('#jobs').inner_html()}"
    )
    field = added.get_by_role("textbox", name="Another option", exact=True)
    field.fill("Insulate the camera battery")
    add = added.get_by_role("button", name="Add option", exact=True)
    add.focus()
    with sending(page, "the added option"):
        page.keyboard.press("Enter")
    expect(field).to_be_focused()

    new_option = page.locator("#jobs > lf-option[data-lf-added]")
    assert new_option.count() == 1, (
        f"the added option did not stand: {page.lf_errors}; events={sent_events(d)}; "
        f"group={page.locator('#jobs').inner_html()}"
    )
    expect(new_option).to_contain_text("Insulate the camera battery")
    expect(new_option).to_have_attribute("chosen", "")
    event = [
        event
        for event in sent_events(d)
        if event.get("kind") == "action" and event.get("widget") == "jobs"
    ][-1]
    assert event["action"] == "choose"
    assert event["detail"] == {
        "options": [new_option.get_attribute("id")],
        "additions": {new_option.get_attribute("id"): "Insulate the camera battery"},
    }
    assert event["generated"] == [new_option.get_attribute("id")]
    assert not [event for event in sent_events(d) if event["kind"] == "comment"]

    page.locator("#job-heater").click()
    round_trip(page)
    latest = [
        event
        for event in sent_events(d)
        if event.get("kind") == "action" and event.get("widget") == "jobs"
    ][-1]
    assert latest["detail"]["additions"] == event["detail"]["additions"]
    assert latest["generated"] == event["generated"]

    page.reload(wait_until="load")
    page.wait_for_function(
        "() => document.body.getAttribute('data-lf-presented') === '1'"
    )
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_count(1)
    expect(page.locator("#job-heater")).to_have_attribute("chosen", "")

    undo(page)
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_attribute(
        "chosen", ""
    )
    undo(page)
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_count(0)
    expect(page.locator("#jobs > lf-option[chosen]")).to_have_count(0)


def test_the_add_field_hands_its_words_to_the_option_it_drew(held_events, serve):
    """The reader's answer stands on screen once, as the option the press drew.

    The press paints that option before the log has answered, so the words have moved and
    the box they came from is empty in that same turn; a reader who saw both would read
    their own answer as still unsent. The generation is standing rather than settled, and
    the refusal shows the difference. It takes the option away and gives the words back,
    out of a record that never left the store.
    """
    browser, held = held_events
    page = open_page(browser, serve(ASK_PAGE))
    form = page.locator("#jobs > .lf-another")
    field = form.get_by_role("textbox", name="Another option", exact=True)
    words = "Insulate the camera battery"
    field.fill(words)
    form.get_by_role("button", name="Add option", exact=True).click(no_wait_after=True)
    holding(page, held, 1, "the added option")

    added = page.locator("#jobs > lf-option[data-lf-added]")
    expect(added).to_have_count(1)
    expect(added).to_contain_text(words)
    expect(field).to_have_value("")
    assert page.evaluate(STORED_DRAFT_TEXT, "option:jobs") == words

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    expect(added).to_have_count(0)
    expect(field).to_have_value(words)
    assert page.evaluate(STORED_DRAFT_TEXT, "option:jobs") == words
    assert not [
        event
        for event in sent_events(serve.page_dir)
        if event.get("kind") == "action" and event.get("widget") == "jobs"
    ]
    consume_browser_errors(page, "400")


def test_a_pick_made_while_an_option_is_in_flight_cannot_strand_it(held_events, serve):
    """A pick made while the send is open leaves the sent generation alone.

    Every pick rewrites the add field's draft, because the choice that draft would submit
    has changed. A pick made while the added option was in the wire used to write over
    the generation that send owned, so its answer settled nothing and the words it had
    already carried into an option stayed in the box for good. A sent generation is no
    longer the box's to write — the same mask that empties the box keeps the pick out of
    it.
    """
    browser, held = held_events
    page = open_page(browser, serve(ASK_PAGE))
    form = page.locator("#jobs > .lf-another")
    field = form.get_by_role("textbox", name="Another option", exact=True)
    words = "Insulate the camera battery"
    field.fill(words)
    form.get_by_role("button", name="Add option", exact=True).click(no_wait_after=True)
    holding(page, held, 1, "the added option")

    # The queue holds this second action behind the first, so the pick's own paint, not
    # another held route, is what says the gesture was taken while the send was open.
    page.locator("#job-heater").click()
    expect(page.locator("#job-heater")).to_have_attribute("chosen", "")
    expect(field).to_have_value("")

    while held:
        held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(field).to_have_value("")
    assert page.evaluate(STORED_DRAFT_TEXT, "option:jobs") is None
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_count(1)


PASTE_IMAGE = """(textarea, encoded) => {
  const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
  const transfer = new DataTransfer();
  transfer.items.add(new File([bytes], 'pasted.png', {type: 'image/png'}));
  textarea.dispatchEvent(new ClipboardEvent('paste', {
    bubbles: true,
    cancelable: true,
    clipboardData: transfer,
  }));
}"""


def test_the_add_field_says_why_it_will_not_take_a_pasted_image(browser, serve):
    """A box that will not take a picture says so, rather than swallowing the paste.

    An option is the text of an option, so this field declines images as the composer
    declines them while a suggestion stands. What it may not do is decline them in
    silence: the shelf never appears, the words never change, and nothing is uploaded,
    so a reader who pasted a screenshot sees exactly what a reader whose paste worked
    would see. The empty send in the same box already answers its own nothing out loud;
    this is the other way a box can go quiet on a gesture."""
    page = open_page(browser, serve(ASK_PAGE))
    uploads = []
    page.on(
        "request",
        lambda request: (
            uploads.append(request.url) if request.url.endswith("/api/media") else None
        ),
    )
    form = page.locator("#jobs > .lf-another")
    field = form.get_by_role("textbox", name="Another option", exact=True)
    pixels = (EXAMPLE_MEDIA / "051bee487bfb5d13.png").read_bytes()
    field.evaluate(PASTE_IMAGE, base64.b64encode(pixels).decode())

    notice = page.locator(".lf-notice")
    expect(notice).to_have_class(re.compile(r"\bshow\b"))
    assert notice.inner_text() == "Images can be added to comments, not options"
    expect(form.locator(".lf-composer-media")).to_be_hidden()
    expect(form.locator(".lf-composer-media img")).to_have_count(0)
    assert field.input_value() == ""
    assert uploads == [], "a refused paste still uploaded its bytes"
    assert not [
        event for event in sent_events(serve.page_dir) if event["kind"] == "action"
    ]


def test_an_arrival_cannot_hide_a_question_draft(browser, serve):
    """An exact-section thread cannot take an unsent option's field.

    The draft remains part of the decision and still becomes a real option. The thread
    stays separate: adding the option sends an action, not a second comment.
    """
    page = open_page(browser, serve(ASK_PAGE))
    d = serve.page_dir
    first = page.locator("#jobs > .lf-another textarea")
    draft = "Keep this answer even if another thread arrives first."
    first.fill(draft)

    external = events_model.append_event(
        d,
        {
            "kind": "comment",
            "author": "claude",
            "agent": "Indexer",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "A separate note on this question.",
        },
    )
    told(page)
    expect(page.locator("#jobs > .lf-conversation")).to_have_count(0)
    expect(first).to_be_visible()
    expect(first).to_have_value(draft)

    page.locator("#jobs > .lf-another").get_by_role(
        "button", name="Add option", exact=True
    ).click()
    round_trip(page)
    added = page.locator("#jobs > lf-option[data-lf-added]")
    expect(added).to_contain_text(draft)
    expect(added).to_have_attribute("chosen", "")
    roots = [e for e in sent_events(d) if e["kind"] == "comment"]
    assert [(e["anchor"], e["text"]) for e in roots] == [
        ({"section": "jobs"}, "A separate note on this question."),
    ]
    action = next(e for e in sent_events(d) if e["kind"] == "action")
    assert action["detail"]["additions"] == {added.get_attribute("id"): draft}
    assert action["generated"] == [added.get_attribute("id")]
    page.locator(".lf-threads-toggle").click()
    expect(page.locator(f'.lf-thread[data-id="{external["id"]}"]')).to_have_count(1)
