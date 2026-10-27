"""Added-option presentation and replay tests."""

import base64
import re

import pytest
from browser_sources import browser_function
from interact_support import append_carried_log_record, stamp
from playwright.sync_api import expect
from render_cases_interaction import (
    OBLIGATION_PAGE,
    OBLIGATION_WITH_CONTEXT_PAGE,
    live_url,
)
from render_cases_layout import (
    button_radius,
    glyph_action_face,
    token_colour,
)
from render_harness import (
    EXAMPLES,
    consume_browser_errors,
    example_media,
    expect_error_waits_in_menu,
    expect_obligations_answered,
    holding,
    http_error_console,
    open_page,
    open_threads,
    round_trip,
    sending,
    shown,
    stored_draft_text,
    told,
    undo,
    write,
)

from leaf import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed

AIM_RECT = browser_function("aims.js", "aimRect")


def test_an_add_field_reconnects_to_its_shared_draft(browser, serve, one_user):
    """Moving the widget restores draft delivery without duplicating its form."""
    url = serve(OBLIGATION_PAGE)
    first = open_page(browser, url, context=one_user)
    second = open_page(browser, url, context=one_user)

    second.evaluate("""() => {
        const group = document.getElementById("jobs");
        group.remove();
        document.querySelector("main").append(group);
    }""")
    text = "A shared answer after the question moves."
    write(first.locator("#jobs > .lf-another leaf-text"), text)

    expect(second.locator("#jobs > .lf-another")).to_have_count(1)
    expect(second.locator("#jobs > .lf-another leaf-text")).to_have_js_property(
        "value", text
    )


def test_the_add_field_previews_the_option_it_will_make(browser, serve):
    """The user writes on the same line and in the same voice as the options.

    The trailing action stays out of an empty row, then submits on the shared margin entry
    corner rather than borrowing the selection mark's circle. It remains a full-sized
    pointer target aligned with the field, which keeps pasted line breaks on one line.
    """
    page = open_page(browser, serve(OBLIGATION_PAGE))
    option = page.locator("#job-camera")
    form = page.locator("#jobs > .lf-another")
    field = form.get_by_role("textbox", name="Another option", exact=True)
    add = form.get_by_role(
        "button", name="Add and select option", exact=True, include_hidden=True
    )

    # The field reads the option's line as a resolved length, which keeps only layout
    # precision (1/64px), so the line heights agree to that.
    typography = """el => { const s = getComputedStyle(el);
                             return [s.fontFamily, s.fontSize, parseFloat(s.lineHeight)]; }"""

    def same_face(a, b):
        return a[:2] == b[:2] and a[2] == pytest.approx(b[2], abs=1 / 64)

    assert same_face(field.evaluate(typography), option.evaluate(typography))
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
    card_field = page.locator("#bracket > .lf-another leaf-text")
    assert same_face(card_field.evaluate(typography), card_words.evaluate(typography))
    assert abs(card_field.bounding_box()["x"] - card_words.bounding_box()["x"]) < 0.5

    expect(add).to_have_text("")
    expect(add.locator('svg[data-lf-icon="add"]')).to_have_count(1)
    expect(add).to_be_hidden()
    expect(add).to_have_attribute("aria-disabled", "true")
    empty_field_box = field.bounding_box()
    write(field, "Portrait sketch")
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
    add_aim = add.evaluate(AIM_RECT)
    assert add_aim["width"] >= aim_floor
    assert add_aim["height"] >= aim_floor
    assert add_box["y"] + add_box["height"] / 2 == pytest.approx(
        field_box["y"] + field_box["height"] / 2, abs=0.5
    )
    assert 0 < form_box["y"] + form_box["height"] - add_box["y"] - add_box["height"] < 8
    write(field, "First line\nSecond line\nThird line")
    expect(field).to_have_js_property("value", "First line Second line Third line")
    pasted_form_box = form.bounding_box()
    pasted_field_box = field.bounding_box()
    pasted_add_box = add.bounding_box()
    assert pasted_field_box["height"] == field_box["height"]
    assert (
        0
        < pasted_form_box["y"]
        + pasted_form_box["height"]
        - pasted_add_box["y"]
        - pasted_add_box["height"]
        < 8
    )
    face = glyph_action_face(add)
    circle_radius = page.locator("#br-steel .lf-pick").evaluate(
        "el => getComputedStyle(el, '::before').borderRadius"
    )
    assert circle_radius == "50%"
    assert face["press"] == "rgba(0, 0, 0, 0)"
    assert face["disc"] == "rgba(0, 0, 0, 0)"
    assert face["discRadius"] == button_radius(page)
    assert face["discRadius"] != circle_radius
    # The mark is the accent itself rather than the ink every injected control takes
    # from the shared face. Both rules are the theme's, and this one wins by coming
    # after it; when the face was stated in the adopted sheet instead, it outranked
    # this rule and drew the mark near black.
    assert face["glyph"] == token_colour(page, "--accent")
    assert face["glyph"] != token_colour(page, "--ink")
    # The disc is clear until the pointer is on it, and it is the whole of what rises:
    # the press still paints nothing of its own, at the size it holds at rest. The
    # pointer leaves again so the coarse reading below is of a press at rest too.
    add.hover()
    hovered = glyph_action_face(add)
    assert hovered["press"] == "rgba(0, 0, 0, 0)"
    assert hovered["disc"] == token_colour(page, "--accent-tint")
    assert hovered["discWidth"] == face["discWidth"]
    page.mouse.move(0, 0)
    page.keyboard.press("Tab")
    expect(add).to_be_focused()

    page.locator("html").evaluate("el => el.style.setProperty('--aim-floor', '44px')")
    form_box = form.bounding_box()
    add_aim = add.evaluate(AIM_RECT)
    assert form_box["height"] >= 44
    assert add_aim["y"] >= form_box["y"]
    assert add_aim["y"] + add_aim["height"] <= form_box["y"] + form_box["height"]
    # A coarse pointer widens what the user may hit, not what the page draws: the press
    # keeps painting nothing of its own, so the disc stays the size it was rather than
    # becoming a square as wide as its target.
    coarse = glyph_action_face(add)
    assert add_aim["width"] >= 44
    assert add_aim["height"] >= 44
    assert coarse["press"] == "rgba(0, 0, 0, 0)"
    assert coarse["discWidth"] == face["discWidth"]

    # A one-line touch target must stay in its own row rather than covering the
    # option above it. It shares the text line's centre even with the larger target.
    write(field, "Portrait sketch")
    form_box = form.bounding_box()
    field_box = field.bounding_box()
    add_box = add.bounding_box()
    add_aim = add.evaluate(AIM_RECT)
    assert add_aim["y"] >= form_box["y"]
    assert add_aim["y"] + add_aim["height"] <= form_box["y"] + form_box["height"]
    assert add_box["y"] + add_box["height"] / 2 == pytest.approx(
        field_box["y"] + field_box["height"] / 2, abs=0.5
    )


def test_an_option_mark_keeps_addition_and_clarification_as_separate_routes(
    browser, serve
):
    """The add form stays in Tab order while c enters the visible thread."""
    url = serve(OBLIGATION_WITH_CONTEXT_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "revision": 1,
            "anchor": {"section": "storage-options"},
            "text": "Archive them locally or remotely?",
        },
    )

    page = open_page(browser, url)
    mark = page.locator("#storage-evict .lf-pick")
    mark.focus()
    expect(mark).to_be_focused()
    expect(page.locator("#storage-options > .lf-thread-seat")).to_have_count(0)

    # Enter is not navigation from a checkbox. It neither chooses the option nor enters
    # the add field; the field is an ordinary later stop in the Tab order.
    page.keyboard.press("Enter")
    expect(mark).to_be_focused()
    expect(page.locator("#storage-options > .lf-another leaf-text")).not_to_be_focused()
    expect(page.locator("#storage-options > lf-option[chosen]")).to_have_count(0)

    # Located on the obligation shows its discussion beside it, so c enters the reply
    # instead of adding an answer or opening another comment box.
    reply = page.locator(".lf-margin-preview .lf-page-thread leaf-text")
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    expect(page.locator(".lf-composer")).to_be_hidden()
    expect(page.locator("#storage-options > .lf-another leaf-text")).not_to_be_focused()
    page.keyboard.press("Escape")
    expect(reply).not_to_be_focused()
    expect(page.locator("#storage-options > lf-option[chosen]")).to_have_count(0)


def test_the_add_field_hands_its_words_to_the_option_it_drew(held_events, serve):
    """The user's answer stands on screen once, as the option the press drew.

    The press paints that option before the log has answered, so the words have moved and
    the box they came from is empty in that same turn; a user who saw both would read
    their own answer as still unsent. The generation is open rather than settled, and
    the refusal shows the difference. It takes the option away and gives the words back,
    out of a record that never left the store.
    """
    browser, held = held_events
    page = open_page(browser, serve(OBLIGATION_PAGE))
    form = page.locator("#jobs > .lf-another")
    field = form.get_by_role("textbox", name="Another option", exact=True)
    words = "Insulate the camera battery"
    write(field, words)
    form.get_by_role("button", name="Add and select option", exact=True).click(
        no_wait_after=True
    )
    holding(page, held, 1, "the added option")

    added = page.locator("#jobs > lf-option[data-lf-added]")
    expect(added).to_have_count(1)
    expect(added).to_contain_text(words)
    expect(field).to_have_js_property("value", "")
    assert stored_draft_text(page, "option:jobs") == words

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
    expect(field).to_have_js_property("value", words)
    assert stored_draft_text(page, "option:jobs") == words
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("kind") == "action" and event.get("widget") == "jobs"
    ]
    consume_browser_errors(page, http_error_console(400))


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
    page = open_page(browser, serve(OBLIGATION_PAGE))
    form = page.locator("#jobs > .lf-another")
    field = form.get_by_role("textbox", name="Another option", exact=True)
    words = "Insulate the camera battery"
    write(field, words)
    form.get_by_role("button", name="Add and select option", exact=True).click(
        no_wait_after=True
    )
    holding(page, held, 1, "the added option")

    # The queue holds this second action behind the first, so the pick's own paint, not
    # another held route, is what says the gesture was taken while the send was open.
    page.locator("#job-heater").click()
    expect(page.locator("#job-heater")).to_have_attribute("chosen", "")
    expect(field).to_have_js_property("value", "")

    while held:
        held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(field).to_have_js_property("value", "")
    assert stored_draft_text(page, "option:jobs") is None
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_count(1)


@pytest.mark.parametrize("group", ["jobs", "bracket"])
def test_an_added_option_keeps_the_row_its_field_held(browser, serve, group):
    """The option the user writes lands in the row its field held, and stays there.

    Submitting resizes nothing, in the titled cards as in the compact rows: the
    field already wears the inset of the option it becomes. A later version leaves
    the option out of its markup, as the instructions ask, and the page keeps it
    after the authored options where the user put it, so no revision moves it.
    """
    page = open_page(browser, live_url(serve(OBLIGATION_PAGE)))
    form = page.locator(f"#{group} > .lf-another")
    field = form.get_by_role("textbox", name="Another option", exact=True)
    write(field, "Ask the neighbours first")
    # The row inside the hairline any cell but the last draws under itself.
    inner = """el => { const r = el.getBoundingClientRect();
                       const s = getComputedStyle(el);
                       return [r.y, r.height - parseFloat(s.borderBottomWidth)]; }"""
    row = form.evaluate(inner)
    page.keyboard.press("Enter")
    added = page.locator(f"#{group} > lf-option[data-lf-added]")
    expect(added).to_have_attribute("chosen", "")
    round_trip(page)
    assert added.evaluate(inner) == pytest.approx(row, abs=0.5)
    authored = page.locator(f"#{group} > lf-option:not([data-lf-added])").evaluate_all(
        "options => options.map(option => option.id)"
    )
    order = (
        f"() => [...document.querySelectorAll('#{group} > lf-option')].map(o => o.id)"
    )
    added_id = added.get_attribute("id")
    assert page.evaluate(order) == [*authored, added_id]

    (serve.page_dir / "index.html").write_text(
        OBLIGATION_PAGE.replace("Plastic, and one came", "Plastic, and the second came")
    )
    assert stamp(serve.page_dir, "Revised the mounts").exit_code == 0
    told(page)
    expect(page.locator("#mounts-p")).to_contain_text("the second came")
    assert page.evaluate(order) == [*authored, added_id]
    assert added.evaluate(inner) == pytest.approx(row, abs=0.5)
    expect(added).to_have_attribute("chosen", "")


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
    so a user who pasted a screenshot sees exactly what a user whose paste worked
    would see. The empty send in the same box already answers its own nothing out loud;
    this is the other way a box can go quiet on a gesture."""
    page = open_page(browser, serve(OBLIGATION_PAGE))
    uploads = []
    page.on(
        "request",
        lambda request: (
            uploads.append(request.url) if request.url.endswith("/api/media") else None
        ),
    )
    form = page.locator("#jobs > .lf-another")
    field = form.get_by_role("textbox", name="Another option", exact=True)
    pixels = (example_media() / "051bee487bfb5d13.png").read_bytes()
    field.evaluate(PASTE_IMAGE, base64.b64encode(pixels).decode())

    # The error is about the add field, so it stands over that field until the user's
    # first key or press there, and then waits in the leaf's menu.
    cover = form.locator(".lf-compose-error")
    expect(cover).to_have_text("Images can be added to comments, not options")
    expect(page.locator(".lf-fp-error-dot")).to_be_hidden()
    cover.click()
    expect(cover).to_be_hidden()
    expect(field).to_be_focused()
    expect_error_waits_in_menu(page, "Images can be added to comments, not options")
    expect(form.locator(".lf-composer-media")).to_be_hidden()
    expect(form.locator(".lf-composer-media img")).to_have_count(0)
    assert field.evaluate("box => box.value") == ""
    assert uploads == [], "a refused paste still uploaded its bytes"
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]


def test_an_arrival_cannot_hide_an_obligation_draft(browser, serve):
    """An exact-section thread cannot take an unsent option's field.

    The draft remains part of the decision and still becomes a real option. The thread
    stays separate: adding the option sends an action, not a second comment.
    """
    page = open_page(browser, serve(OBLIGATION_PAGE))
    d = serve.page_dir
    first = page.locator("#jobs > .lf-another leaf-text")
    draft = "Keep this answer even if another thread arrives first."
    write(first, draft)

    external = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Indexer",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "A separate note on this question.",
        },
    )
    told(page)
    expect(page.locator("#jobs > .lf-thread-seat")).to_have_count(0)
    expect(first).to_be_visible()
    expect(first).to_have_js_property("value", draft)

    page.locator("#jobs > .lf-another").get_by_role(
        "button", name="Add and select option", exact=True
    ).click()
    round_trip(page)
    added = page.locator("#jobs > lf-option[data-lf-added]")
    expect(added).to_contain_text(draft)
    expect(added).to_have_attribute("chosen", "")
    roots = [e for e in events_model.read_events(d) if e["kind"] == "comment"]
    assert [(e["anchor"], e["text"]) for e in roots] == [
        ({"section": "jobs"}, "A separate note on this question."),
    ]
    action = next(e for e in events_model.read_events(d) if e["kind"] == "action")
    assert action["detail"] == {"option": added.get_attribute("id"), "text": draft}
    open_threads(page)
    expect(page.locator(f'.lf-fp-thread[data-key="{external["id"]}"]')).to_have_count(1)


def test_on_a_phone_options_draw_no_keys_and_return_adds_a_written_one(browser, serve):
    """A phone has no keys to press, so a group the user is in draws no digits, while
    its controls keep their shortcuts for a keyboard someone attaches. Return on a
    phone's keyboard breaks a line in a comment, but an option's title is one line, so
    there it adds the option, and a line break pasted into it becomes a space."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, live_url(serve(OBLIGATION_PAGE)), context=context)
    page.locator("#br-steel").tap()
    round_trip(page)
    expect(page.locator("#br-steel")).to_have_attribute("chosen", "")
    faces = page.locator(
        ".lf-key-badge[data-lf-binding-badge], .lf-command-binding-badge"
    )
    expect(faces).to_have_count(0)
    expect(page.locator("#br-cedar .lf-pick")).to_have_attribute(
        "aria-keyshortcuts", re.compile(".")
    )

    field = page.locator("#bracket > .lf-another").get_by_role(
        "textbox", name="Another option", exact=True
    )
    expect(field).to_have_attribute("aria-multiline", "false")
    field.tap()
    page.keyboard.type("Ask the neighbours first")
    page.keyboard.press("Enter")
    added = page.locator("#bracket > lf-option[data-lf-added]")
    expect(added).to_have_attribute("chosen", "")
    expect(added).to_contain_text("Ask the neighbours first")
    expect(field).to_have_js_property("value", "")
    # Words with a line break, as a paste brings them, stay on the one line.
    field.tap()
    page.keyboard.insert_text("Ask the neighbours\nfirst")
    expect(field).to_have_js_property("value", "Ask the neighbours first")


def test_the_add_field_says_its_whole_hint_on_a_phone(browser, serve):
    """The add field keeps room at its end for the Add press and the obligation's key, so on a
    phone the words before that room are few: alert-review's card group at 360px cut
    "Another option — add to select" to "Another option — ad…", which lost the verb.
    The hint says the same in words that fit, and the room it keeps is measured here
    rather than restated."""
    example = next(p for p in EXAMPLES if p.stem == "alert-review")
    context = browser.new_context(
        viewport={"width": 360, "height": 740}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, serve(example), context=context)
    field = page.locator(".lf-another leaf-text").first
    field.scroll_into_view_if_needed()
    fit = field.evaluate("""field => {
      const style = getComputedStyle(field);
      const room = field.clientWidth - parseFloat(style.paddingInlineStart)
        - parseFloat(style.paddingInlineEnd)
        - parseFloat(style.getPropertyValue('--lf-field-end-room'));
      const pen = document.createElement('canvas').getContext('2d');
      pen.font = style.font;
      return {room, words: pen.measureText(field.getAttribute('placeholder')).width};
    }""")
    assert fit["words"] <= fit["room"], fit


def test_another_option_becomes_a_real_option_without_starting_a_thread(browser, serve):
    """The answer the author missed joins the control as a row of its own.

    It is not a comment with a special response contract: the user has supplied an
    answer, not opened a thread. The `add` stands on its own coordinate, so a
    later ordinary pick and a reload keep the option, and each undo takes back one
    gesture: the later pick, then the option's pick, then the option itself.
    """
    url = serve(OBLIGATION_PAGE)
    page = open_page(browser, url)
    d = serve.page_dir

    expect(page.locator("#jobs > .lf-thread-seat")).to_have_count(0)
    added = page.locator("#jobs > .lf-another")
    assert added.count() == 1, (
        f"the add-option cell was not rendered: {shown(page.lf_errors)}; "
        f"group={page.locator('#jobs').inner_html()}"
    )
    field = added.get_by_role("textbox", name="Another option", exact=True)
    expect(field).to_have_attribute("placeholder", "Add another option")
    write(field, "Insulate the camera battery")
    add = added.get_by_role("button", name="Add and select option", exact=True)
    add.focus()
    with sending(page, "the added option"):
        page.keyboard.press("Enter")
    # Pressing Add is Enter pressed in the field: the user goes on in the field.
    expect(field).to_be_focused()
    expect(added.locator(".lf-compose-submit")).to_have_attribute(
        "aria-disabled", "true"
    )
    expect_obligations_answered(page, "0/3")

    new_option = page.locator("#jobs > lf-option[data-lf-added]")
    assert new_option.count() == 1, (
        f"the added option did not stand: {shown(page.lf_errors)}; events={events_model.read_events(d)}; "
        f"group={page.locator('#jobs').inner_html()}"
    )
    expect(new_option).to_contain_text("Insulate the camera battery")
    expect(new_option).to_have_attribute("chosen", "")
    identity = new_option.get_attribute("id")
    moves = [
        (event["action"], event["detail"])
        for event in events_model.read_events(d)
        if event.get("kind") == "action" and event.get("widget") == "jobs"
    ]
    assert moves == [
        ("add", {"option": identity, "text": "Insulate the camera battery"}),
        ("choose", {"value": [identity]}),
    ]
    assert not [
        event for event in events_model.read_events(d) if event["kind"] == "comment"
    ]

    page.locator("#job-heater").click()
    round_trip(page)
    expect(page.locator("#job-heater")).to_have_attribute("chosen", "")
    expect(new_option).to_have_attribute("chosen", "")

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
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_count(1)
    expect(page.locator("#jobs > lf-option[chosen]")).to_have_count(0)
    undo(page)
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_count(0)
