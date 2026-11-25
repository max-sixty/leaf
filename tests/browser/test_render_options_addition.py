"""Added-option presentation and replay tests."""

import re

import pytest
from interact_support import append_carried_log_record, stamp
from playwright.sync_api import expect
from render_cases_interaction import (
    OBLIGATION_PAGE,
    OBLIGATION_WITH_CONTEXT_PAGE,
    live_url,
)
from render_harness import (
    RELEASE_FOCUS,
    consume_browser_errors,
    expect_obligations_answered,
    holding,
    http_error_console,
    open_page,
    open_threads,
    rendered,
    round_trip,
    select,
    sending,
    shown,
    stored_draft_text,
    told,
    undo,
    write,
)

from leaf import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


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
    write(first.locator("#jobs > .lf-another textarea"), text)

    expect(second.locator("#jobs > .lf-another")).to_have_count(1)
    expect(second.locator("#jobs > .lf-another textarea")).to_have_js_property(
        "value", text
    )


def test_the_add_field_previews_the_option_it_will_make(browser, serve):
    """The user writes on the same line and in the same font as the options."""
    page = open_page(browser, serve(OBLIGATION_PAGE))
    option = page.locator("#job-camera")
    form = page.locator("#jobs > .lf-another")
    field = form.get_by_role("textbox", name="Another option", exact=True)

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
    card_field = page.locator("#bracket > .lf-another textarea")
    assert same_face(card_field.evaluate(typography), card_words.evaluate(typography))
    assert abs(card_field.bounding_box()["x"] - card_words.bounding_box()["x"]) < 0.5


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
    expect(page.locator("#storage-options .lf-page-thread")).to_have_count(0)

    # Enter is not navigation from a checkbox. It neither chooses the option nor enters
    # the add field; the field is an ordinary later stop in the Tab order.
    page.keyboard.press("Enter")
    expect(mark).to_be_focused()
    expect(page.locator("#storage-options > .lf-another textarea")).not_to_be_focused()
    expect(page.locator("#storage-options > lf-option[selected]")).to_have_count(0)

    # Located on the obligation shows its discussion beside it, so c enters the reply
    # instead of adding an answer or opening another comment box.
    reply = page.locator(".lf-margin-preview .lf-page-thread leaf-text")
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    expect(page.locator(".lf-composer")).to_be_hidden()
    expect(page.locator("#storage-options > .lf-another textarea")).not_to_be_focused()
    page.keyboard.press("Escape")
    expect(reply).not_to_be_focused()
    expect(page.locator("#storage-options > lf-option[selected]")).to_have_count(0)


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
    field.press("Enter", no_wait_after=True)
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
    has changed. A pick that wrote over the generation a send owns, while the added
    option was in the wire, would leave its answer settling nothing and the words it had
    already carried into an option in the box for good. A sent generation is not the
    box's to write — the same mask that empties the box keeps the pick out of
    it.
    """
    browser, held = held_events
    page = open_page(browser, serve(OBLIGATION_PAGE))
    form = page.locator("#jobs > .lf-another")
    field = form.get_by_role("textbox", name="Another option", exact=True)
    words = "Insulate the camera battery"
    write(field, words)
    field.press("Enter", no_wait_after=True)
    holding(page, held, 1, "the added option")

    # The queue holds this second action behind the first, so the pick's own paint, not
    # another held route, is what says the gesture was taken while the send was open.
    page.locator("#job-heater").click()
    expect(page.locator("#job-heater")).to_have_attribute("selected", "")
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
    expect(added).to_have_attribute("selected", "")
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
    expect(added).to_have_attribute("selected", "")


def test_an_arrival_cannot_hide_an_obligation_draft(browser, serve):
    """An exact-section thread cannot take an unsent option's field.

    The draft remains part of the decision and still becomes a real option. The thread
    stays separate: adding the option sends an action, not a second comment.
    """
    page = open_page(browser, serve(OBLIGATION_PAGE))
    d = serve.page_dir
    first = page.locator("#jobs > .lf-another textarea")
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
    expect(page.locator("#jobs .lf-page-thread")).to_have_count(0)
    expect(first).to_be_visible()
    expect(first).to_have_js_property("value", draft)

    first.press("Enter")
    round_trip(page)
    added = page.locator("#jobs > lf-option[data-lf-added]")
    expect(added).to_contain_text(draft)
    expect(added).to_have_attribute("selected", "")
    roots = [e for e in events_model.read_events(d) if e["kind"] == "comment"]
    assert [(e["anchor"], e["text"]) for e in roots] == [
        ({"section": "jobs"}, "A separate note on this question."),
    ]
    action = next(e for e in events_model.read_events(d) if e["kind"] == "action")
    assert action["detail"] == {"option": added.get_attribute("id"), "text": draft}
    open_threads(page)
    expect(
        page.locator(f'.lf-fp-thread[data-lf-key="{external["id"]}"]')
    ).to_have_count(1)


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
    expect(page.locator("#br-steel")).to_have_attribute("selected", "")
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
    field.tap()
    page.keyboard.type("Ask the neighbours first")
    page.keyboard.press("Enter")
    added = page.locator("#bracket > lf-option[data-lf-added]")
    expect(added).to_have_attribute("selected", "")
    expect(added).to_contain_text("Ask the neighbours first")
    expect(field).to_have_js_property("value", "")


def test_a_closed_group_answers_only_from_its_options(browser, serve):
    """`closed` leaves out the field for an unlisted answer, so a page that draws its
    own choice ends at its own options, holding no room for the field; the listed
    options still answer."""
    page = open_page(
        browser, serve(OBLIGATION_PAGE.replace('id="jobs"', 'id="jobs" closed'))
    )

    expect(page.locator("#jobs > lf-option").first).to_be_visible()
    expect(page.locator("#jobs > .lf-another")).to_have_count(0)
    expect(page.locator("#jobs > lf-options-done")).to_be_visible()
    below_last_cell = page.locator("#jobs").evaluate(
        """group => group.getBoundingClientRect().bottom - Math.max(
          ...[...group.children].map((cell) => cell.getBoundingClientRect().bottom))"""
    )
    assert below_last_cell <= 2, below_last_cell
    # Nor does it keep the field's number: Done takes the one after the last option.
    page.keyboard.press("m")
    expect(page.locator("#jobs > lf-options-done .lf-key-badge")).to_have_text("4")


def test_firefox_s_copy_of_a_group_builds_no_add_field(firefox_browser, serve):
    """Firefox, asked for the contents of a selection a drag carried through the add
    field's shadow root, copies the Document itself and upgrades and connects the
    widgets it copies there before it throws. A highlighter extension asks that of every
    selection the user makes. The copy stays markup: a copied group that set up would
    build its add field there, whose style sheet that document refuses, and the page
    would report the refusal to the agent.

    Firefox copies the Document only where the field's editor, an editable node, has
    built; past the textarea an unvisited field holds, it clones the range alone. So
    the user visits the field before the drag."""
    page = open_page(firefox_browser, serve(OBLIGATION_PAGE))
    field = page.locator("#bracket > .lf-another textarea")
    field.focus()
    rendered(page)
    page.evaluate(RELEASE_FOCUS)
    # The extension's reading of the selection, which it makes as the drag ends.
    page.evaluate("""() => {
      window.copies = [];
      document.addEventListener("mouseup", () => {
        try {
          getSelection().getRangeAt(0).cloneContents();
          copies.push("cloned");
        } catch (error) {
          copies.push(error.name);
        }
      });
    }""")
    page.locator("#bracket-decision").scroll_into_view_if_needed()
    # From inside an option's words to over the field, where Firefox has moved the
    # selection into the field's shadow root by the time the drag ends.
    start = page.locator("#br-steel").evaluate("""option => {
      const text = [...option.childNodes].find((node) => node.data?.includes("drop-in"));
      const range = document.createRange();
      range.setStart(text, text.data.indexOf("drop-in"));
      range.setEnd(text, text.data.indexOf("drop-in") + 1);
      const box = range.getBoundingClientRect();
      return [box.x, box.y + box.height / 2];
    }""")
    box = field.bounding_box()
    select(page, start, (box["x"] + 230, box["y"] + box["height"] / 2), steps=15)
    # The throw says Firefox still copies the Document, so the drag reached the copy this
    # guards.
    page.wait_for_function("copies.length")
    assert page.evaluate("copies") == ["HierarchyRequestError"], (
        "Firefox now clones the range alone: drop `inWindowDocument` from "
        "lib/once.js and lib/leaf-element.js, and this test"
    )
    rendered(page)


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

    expect(page.locator("#jobs .lf-page-thread")).to_have_count(0)
    added = page.locator("#jobs > .lf-another")
    assert added.count() == 1, (
        f"the add-option cell was not rendered: {shown(page.lf_errors)}; "
        f"group={page.locator('#jobs').inner_html()}"
    )
    field = added.get_by_role("textbox", name="Another option", exact=True)
    expect(field).to_have_attribute("placeholder", "Add another option…")
    write(field, "Insulate the camera battery")
    with sending(page, "the added option"):
        page.keyboard.press("Enter")
    # Enter adds the option and the user goes on in the field.
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "")
    expect_obligations_answered(page, "0/3")

    new_option = page.locator("#jobs > lf-option[data-lf-added]")
    assert new_option.count() == 1, (
        f"the added option did not stand: {shown(page.lf_errors)}; events={events_model.read_events(d)}; "
        f"group={page.locator('#jobs').inner_html()}"
    )
    expect(new_option).to_contain_text("Insulate the camera battery")
    expect(new_option).to_have_attribute("selected", "")
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
    expect(page.locator("#job-heater")).to_have_attribute("selected", "")
    expect(new_option).to_have_attribute("selected", "")

    page.reload(wait_until="load")
    page.wait_for_function(
        "() => document.body.getAttribute('data-lf-presented') === '1'"
    )
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_count(1)
    expect(page.locator("#job-heater")).to_have_attribute("selected", "")

    undo(page)
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_attribute(
        "selected", ""
    )
    undo(page)
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_count(1)
    expect(page.locator("#jobs > lf-option[selected]")).to_have_count(0)
    undo(page)
    expect(page.locator("#jobs > lf-option[data-lf-added]")).to_have_count(0)
