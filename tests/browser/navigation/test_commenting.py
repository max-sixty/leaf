"""Commenting with `c`: what a comment lands on, where its box opens, and how its keys
type and send."""

import json
import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import (
    PANEL_PAGE,
    SEATED_OBLIGATION_LAYER,
    SEATED_OBLIGATION_WIDGETS,
    panel_comment,
)
from render_cases_navigation import DISCLOSED_PAGE, NOTED_PAGE, TARGETS_PAGE, _publish
from render_cases_widgets import SQUEEZED_BOARD_PAGE, WHERE_I_STAND_PAGE
from render_harness import (
    INLINE_PAGE,
    RELEASE_FOCUS,
    ROOT,
    draft_control,
    expect_obligations_answered,
    leaf_page,
    open_page,
    open_versions,
    page_comment,
    panel_control,
    panel_field,
    panel_settled,
    panel_view,
    refuse,
    resized,
    round_trip,
    scroll_settled,
    select,
    sending,
    suggestion_control,
    told,
    write,
)

from browser.threads import open_panel_thread
from leaf import event_log as events_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_reactionless_other_responses_can_turn_the_compact_field_into_a_suggestion(
    browser, serve
):
    """A reactionless layer keeps Suggest in the compact response fallback."""
    registry = json.loads((ROOT / "packages/default/registry.json").read_text())
    tokens = {name: None for name in registry["$reactions"]["tokens"]}
    page = open_page(
        browser,
        serve(INLINE_PAGE, layer_registry={"$reactions": {"tokens": tokens}}),
    )
    page.locator("#p").click(click_count=3)
    box = page.locator(".lf-fab-input")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(box).not_to_be_focused()
    expect(box).to_have_attribute("placeholder", "Comment… c")
    page.keyboard.press("c")
    expect(box).to_be_focused()
    expect(box).to_have_attribute("placeholder", re.compile(r"^Comment… .*⏎$"))
    send = page.locator(
        ".lf-composer > leaf-composition-field > .lf-compose-field > .lf-compose-submit"
    )
    expect(send.locator('svg[data-lf-icon="send"]')).to_have_count(1)
    expect(page.locator(".lf-composer-row")).to_have_count(0)
    field_box = box.bounding_box()
    action = page.locator(".lf-compose-field").get_by_role(
        "button", name="Other responses", exact=True
    )
    send_box = action.bounding_box()
    assert (
        field_box["x"]
        < send_box["x"]
        < send_box["x"] + send_box["width"]
        < (field_box["x"] + field_box["width"])
    )
    assert (
        field_box["y"]
        < send_box["y"]
        < send_box["y"] + send_box["height"]
        < (field_box["y"] + field_box["height"])
    )
    expect(send).to_have_attribute("aria-label", "Comment")

    page.keyboard.press("Tab")
    choices = page.locator(".lf-fab-bar")
    suggest = choices.locator(".lf-fab-suggest")
    expect(choices).to_be_visible()
    expect(suggest).to_be_focused()

    page.keyboard.press("Enter")
    expect(box).to_be_focused()
    expect(box).to_have_attribute("placeholder", re.compile(r"^Replacement text .*⏎$"))
    expect(send).to_have_attribute("aria-label", "Suggest")
    assert "A paragraph carrying bold text and emphasis inside it" in box.evaluate(
        "box => box.value"
    )
    rendered(page)
    expect(box).to_have_attribute("placeholder", re.compile(r"^Replacement text .*⏎$"))


def test_a_passage_selection_keeps_native_copy_and_context_menu(browser, serve):
    """Leaf may offer a response without taking the browser's selection gestures."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        permissions=["clipboard-read", "clipboard-write"],
    )
    page = open_page(browser, serve(INLINE_PAGE), context=context)
    paragraph = page.locator("#p")
    paragraph.click(click_count=3)
    expect(page.locator(".lf-fab-bar")).to_be_visible()

    selected = page.evaluate("() => getSelection().toString()")
    assert "A paragraph carrying" in selected
    is_mac = page.evaluate(
        "() => /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)"
    )
    page.keyboard.press("Meta+c" if is_mac else "Control+c")
    assert page.evaluate("() => navigator.clipboard.readText()") == selected

    page.evaluate(
        """() => {
              window.lfContextMenu = null;
              document.addEventListener('contextmenu', event => {
                setTimeout(() => {
                  window.lfContextMenu = {
                    prevented: event.defaultPrevented,
                    selection: getSelection().toString(),
                  };
                });
              }, {capture: true, once: true});
            }"""
    )
    paragraph.click(button="right")
    page.wait_for_function("() => window.lfContextMenu !== null")
    assert page.evaluate("() => window.lfContextMenu") == {
        "prevented": False,
        "selection": selected,
    }


def test_comment_enters_the_selected_passage_s_field_and_takes_its_letters(
    browser, serve
):
    """Comment enters a selected passage's field, where letters and `?` are words."""
    page = open_page(browser, serve(TARGETS_PAGE))
    help_el = page.locator(".lf-command-reference")

    # Nothing in hand: the reference names the page comment `c` enters directly.
    page.keyboard.press("?")
    expect(help_el).to_contain_text("Comment on the page")
    page.keyboard.press("Escape")

    # A real selection keeps the browser selection until Comment explicitly enters its
    # field. Once there, letters and `?` belong to the comment rather than falling through
    # to page shortcuts.
    box = page.locator("#prose").bounding_box()
    select(
        page,
        (box["x"] + 1, box["y"] + 4),
        (box["x"] + box["width"] - 1, box["y"] + box["height"] - 4),
        steps=12,
    )
    field = page.locator(".lf-fab-input")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(field).not_to_be_focused()
    page.keyboard.press("c")
    expect(field).to_be_focused()
    page.keyboard.type("?")
    expect(field).to_have_js_property("value", "?")
    page.keyboard.press("Escape")

    # An explicit visual target follows the same contract, but its accessible field name
    # identifies the item rather than a quoted passage.
    page.locator("#fig svg").click(modifiers=["Alt"])
    expect(field).to_be_focused()
    expect(field).to_have_attribute("aria-label", re.compile("figure"))
    page.keyboard.press("Escape")


def test_typing_in_a_selected_comment_wins_over_page_shortcuts(browser, serve):
    """Once Comment focuses a selected passage's field, shortcut letters are text."""
    url = serve(TARGETS_PAGE)
    _publish(serve.page_dir, 2, TARGETS_PAGE, "two")
    page = open_page(browser, url)

    box = page.locator("#prose").bounding_box()
    select(
        page,
        (box["x"] + 1, box["y"] + 4),
        (box["x"] + box["width"] - 1, box["y"] + box["height"] - 4),
        steps=12,
    )
    fab = page.locator(".lf-fab-input")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(fab).not_to_be_focused()
    page.keyboard.press("c")
    expect(fab).to_be_focused()
    page.keyboard.press("c")
    expect(fab).to_have_js_property("value", "c")
    page.keyboard.press("Escape")
    page.evaluate(RELEASE_FOCUS)

    open_versions(page)
    expect(page.locator(".lf-fp-menu")).to_have_attribute("data-level", "versions")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")

    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()


def test_submit_shortcuts_activate_the_controls_that_promise_the_action(browser, serve):
    """The composer sends with Enter; the draft saves with its advertised Mod+Enter."""
    html = TARGETS_PAGE.replace(
        "</main>", '<lf-draft id="plan"><pre>Ship it.</pre></lf-draft></main>'
    )
    page = open_page(browser, serve(html))

    box = page.locator("#prose").bounding_box()
    select(
        page,
        (box["x"] + 1, box["y"] + 4),
        (box["x"] + box["width"] - 1, box["y"] + box["height"] - 4),
        steps=12,
    )
    composer = page.locator(".lf-composer")
    field = page.locator(".lf-fab-input")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(field).not_to_be_focused()
    page.keyboard.press("c")
    expect(field).to_be_focused()
    write(field, "Send through the compact control.")
    page.keyboard.press("Shift+Enter")
    expect(field).to_have_js_property("value", "Send through the compact control.\n")
    expect(field).to_have_attribute(
        "aria-keyshortcuts", "Enter Meta+Enter Control+Enter Tab"
    )
    with sending(page, "the composer shortcut"):
        page.keyboard.press("Enter")
    expect(composer).to_be_hidden()
    # The send left the user on the new thread's card. Leave it for its passage, then
    # let go of both before opening the draft below.
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()

    draft_control(page, "edit", "plan").click()
    editor = page.locator("#plan leaf-text")
    write(editor, "Save through the visible control.")
    page.keyboard.press("Shift+Enter")
    page.keyboard.type("Keep the second line.")
    expect(editor).to_have_js_property(
        "value", "Save through the visible control.\nKeep the second line."
    )
    expect(editor).to_have_attribute(
        "aria-keyshortcuts", "Meta+Enter Control+Enter Escape"
    )
    with sending(page, "the draft shortcut"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator("#plan .lf-draft-body")).to_contain_text(
        "Keep the second line."
    )

    round_trip(page)


def test_touch_return_keeps_newlines_until_the_user_taps_submit(browser, serve):
    html = TARGETS_PAGE.replace(
        "</main>", '<lf-draft id="plan"><pre>Ship it.</pre></lf-draft></main>'
    )
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    page = open_page(browser, serve(html), context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches")

    field = page_comment(page)
    write(field, "First paragraph")
    field.press("Enter")
    field.type("Second paragraph")
    expect(field).to_have_js_property("value", "First paragraph\nSecond paragraph")
    expect(field).to_have_attribute("aria-keyshortcuts", "Meta+Enter Control+Enter")
    expect(field).to_be_visible()
    with sending(page, "the touch comment"):
        field.locator("xpath=..").locator(".lf-compose-submit").click()

    draft_control(page, "edit", "plan").click()
    editor = page.locator("#plan leaf-text")
    write(editor, "First paragraph")
    editor.press("Enter")
    editor.type("Second paragraph")
    expect(editor).to_have_js_property("value", "First paragraph\nSecond paragraph")
    expect(editor).to_have_attribute(
        "aria-keyshortcuts", "Meta+Enter Control+Enter Escape"
    )
    with sending(page, "the touch draft"):
        draft_control(page, "save", "plan").click()
    expect(page.locator("#plan .lf-draft-body")).to_contain_text("Second paragraph")


def test_c_comments_on_what_the_user_is_located_in(browser, serve):
    """Focus supplies an element anchor. `c` once read the 💬 alone, so a user
    working from the keys had two destinations where explicit pointer targeting had
    three: an item, a quote, or the whole page. A
    focused link put them on an option and the box that opened still said "Comment on the
    page" — the ⌥ aim's "the item under the pointer" with no twin for the cursor.

    Where they are located is the unanswered decision first, because that is what the page
    has already told them: markHere rings the whole obligation when m/M lands on its control.
    Below a decision it is the innermost item, which is the aim's own reading — so a focused
    link speaks for the paragraph holding it, no id of its own being what an anchor needs.

    One box either way: `commentOnTarget` writes `{section: item.id}`, which is the anchor a
    widget's own thread seat collects, so a remark made here lands in that seat's
    thread rather than beside it. Reaching for the seat directly instead was five
    questions — escaping an author's id, whether the box can take focus, which box when
    the seat holds several, what design mode files, where the user already stood — for
    a focus landing.

    The control is the same press from the same page with the user located nowhere in
    it, where `c` opens the page-comment box rather than this item's composer. Without it a
    green here would follow just as well from a composer that opened on everything.

    Focus is dropped between the phases rather than backed out of, because each press
    lands the user in a box and the typing scope owns the letter there."""
    page = open_page(browser, serve(WHERE_I_STAND_PAGE))
    comment = page.locator('.lf-fp-field leaf-text[name="comment"]')

    def drop():
        if (
            page.locator(".lf-composer[data-lf-open]").count()
            or page.locator('.lf-fp-field leaf-text[name="comment"]:focus').count()
        ):
            page.keyboard.press("Escape")
        page.evaluate("() => document.activeElement?.blur()")

    # Located nowhere in the page: the page itself is the contextual target.
    page.keyboard.press("c")
    expect(comment).to_be_focused()
    drop()

    # A decision: the composer opens on the question rather than on the option the
    # walk happens to stand the user on, and rather than on the page.
    page.keyboard.press("m")
    expect(page.locator("#shape-decision")).to_have_attribute("data-lf-obligation", "1")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer")).to_contain_text("question · Which material?")
    drop()

    # A settled group: not a decision at all, and the thread seat it still holds is
    # inside `hidden="until-found"`, so a press that reached into the seat focused a box
    # that cannot take focus and did nothing at all. Named by the question holding it
    # rather than by "options", which the composer standing open from the phase above
    # already says — an assertion true before the press is no assertion about the press.
    page.locator("#settled .lf-settled").focus()
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_contain_text("Should we keep it?")
    drop()

    # A decision with no seat: focus on its action names the rewrite, and the composer
    # anchors there rather than on the page.
    rendered(page)
    rewrite_action = suggestion_control(page, "sug-window", "accept")
    rewrite_action.focus()
    expect(rewrite_action).to_be_focused()
    expect(page.locator("#sug-window")).to_have_attribute("data-lf-obligation", "1")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer")).to_contain_text("rewrite")
    drop()

    # A link inside a question, open and settled: the same markup, and the same answer.
    # Located in a decision is not working one — a user who focused a link has named
    # something more particular than the question around it, and answering the question
    # there both overrode what they named and made the reply turn on whether that question
    # happened to be open. The settled one is the contrast that shows it was the openness
    # doing it: it always said "option", and the open one used to say "options".
    for expected_id in ("sh-steel", "st-keep"):
        drop()
        rendered(page)
        if expected_id == "st-keep":
            settled = page.locator("#settled .lf-settled")
            settled.click()
            expect(settled).to_have_attribute("aria-expanded", "true")
        link = page.locator(f"#{expected_id} a")
        link.focus()
        expect(link).to_be_focused()
        page.keyboard.press("c")
        expect(page.locator(".lf-composer")).to_be_visible()
        assert page.evaluate(
            "() => document.querySelector('.lf-composer blockquote')?.textContent ?? ''"
        ).startswith("§ option · "), "the box named the question, not the option"
        drop()

    # Below any item, the innermost item: the paragraph the focused link sits in.
    rendered(page)
    passage_link = page.locator("#p1 a")
    passage_link.focus()
    expect(passage_link).to_be_focused()
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_contain_text("paragraph")


def test_the_ring_holds_on_a_seat_the_agent_has_still_to_answer(browser, serve):
    """Where the user is located and what the user still owes are two facts, and a
    widget whose seat holds a thread waiting on the agent is where they part. Its seat holds the words
    the user just wrote, its answer is unmade and its controls are live, and it has left
    On me because the next word there is the agent's — but the user
    is located in it all the same, and it is still the question they are working.

    Read off the user's list, both the ring and `c` went with the count: the moment the
    remark was sent the ring left from under the user, and `c` fell through from the
    thread they had started to whichever item their focus happened to rest in. That
    starts a second thread rather than continuing the first, so the next line of a
    remark landed somewhere the first line was not. The agent's reply moved both back.
    Nothing the user did moved either, which is the whole of the complaint; the reply
    phase here is what says the ring has stopped tracking the count rather than merely
    tracking it late. `c` names the user's own thread throughout, because its target,
    the widget, lies within the obligation the user holds (`commentDestination`), and the
    press lands in that thread's reply box.

    A picked group is the control on the other side. It is answered, so it is off both
    readings and must stay off: the switch is about a seat the user is mid-sentence in,
    not about reopening what a pick has closed.

    The seat and the obligation are the project widget SEATED_OBLIGATION_ENTRY declares, for the
    reason test_a_seat_thread_leaves_the_pick_it_is_about_live gives."""
    url = serve(
        leaf_page(
            "mid-sentence",
            """
<h1 id="t">Mid-sentence</h1>
<lf-ask id="shape-decision"><h2>Galvanised steel for the frame?</h2>
<lf-verdict id="shape" asks>Drop-in, and it needs no sealing.</lf-verdict></lf-ask>
<lf-ask id="picked-decision"><h2>Should we keep it?</h2>
<lf-options id="picked" choose>
  <lf-option id="pk-keep" chosen><strong>Keep it</strong> Settled by a pick.</lf-option>
  <lf-option id="pk-drop"><strong>Drop it</strong> The alternative.</lf-option>
</lf-options></lf-ask>
<p id="p2">A passage carrying
<lf-suggestion id="sug-window">
  <lf-old>Refill every feeder each morning.</lf-old>
  <lf-new>Refill when the camera shows it half-empty.</lf-new>
</lf-suggestion></p>
""",
        ),
        layer_registry=SEATED_OBLIGATION_LAYER,
        layer_widgets=SEATED_OBLIGATION_WIDGETS,
    )
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Steel, unless the sealing is quick?",
            "anchor": {"section": "shape"},
        },
    )

    page = open_page(browser, url)

    # The completion count includes every active obligation: the authored pick is complete;
    # the seated obligation and suggestion are not.
    expect_obligations_answered(page, "1/3")
    # In On me the seated obligation is the agent's: the comment in its seat is owed a reply,
    # which stands for it, so it is neither the user's obligation nor done.
    panel_control(page, "queue").click()
    panel_settled(page, view="queue")

    def card(source):
        return page.locator(f".lf-fp-on-item[data-key*='\"widget:{source}\"']")

    expect(card("shape")).to_have_count(0)
    expect(card("sug-window")).to_have_count(1)
    # The picked group has left the user's list for its Done.
    expect(card("picked")).to_have_attribute("data-list", "done")
    page.locator(".lf-fp-filters button").nth(1).click()
    agent_rows = page.locator('.lf-fp-on-item[data-list="agent"]')
    expect(agent_rows).to_have_count(1)
    expect(agent_rows).to_contain_text("Steel, unless the sealing is quick?")
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)

    # And with it shut, which is every other reading below.
    page.locator("#shape .lf-settle").focus()
    expect(page.locator("#shape-decision")).to_have_attribute("data-lf-obligation", "1")
    # The count is completion, not the open walk's position, so focus leaves it stable.
    expect_obligations_answered(page, "1/3")

    # Answering hands the question back, and the count moves while the ring does not.
    # Focus is not touched again from here, so the ring read below is the one painted
    # above: blurring and coming back would re-derive it and repeat the phase instead of
    # measuring that it stayed through the news.
    #
    # The source is the user's again once the thread in its answer control has
    # been answered.
    roots = [e["id"] for e in events_model.read_events(d) if e.get("kind") == "comment"]
    for root in roots:
        append_carried_log_record(
            d,
            {
                "kind": "reply",
                "author": "agent",
                "revision": 1,
                "parent": root,
                "text": "Sealing is an afternoon.",
            },
        )
    told(page)
    # Back on the user's open list, the same obligation is still incomplete, so the
    # completion count remains stable.
    expect_obligations_answered(page, "1/3")
    expect(page.locator("#shape .lf-settle")).to_be_focused()
    expect(page.locator("#shape-decision")).to_have_attribute("data-lf-obligation", "1")

    # And the press means that thread, so the next line joins the one the first line
    # opened rather than starting another on the obligation or the widget. Whichever surface
    # draws the thread is the destination's choice; which thread it is is this test's.
    page.keyboard.press("c")
    page.wait_for_function(
        """root => {
          let at = document.activeElement;
          while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
          return at?.matches('.lf-thread-reply leaf-text')
            && at.closest('.lf-page-thread')?.dataset.thread === root;
        }""",
        arg=roots[0],
    )
    expect(page.locator(".lf-fab-input")).to_be_hidden()
    page.evaluate("() => document.activeElement?.blur()")

    # The picked group is the control on the other side: answered, so off both readings,
    # and the switch leaves it there. Read after the repaint, because `markHere` paints
    # inside the shared repaint frame — an absence read in the same round trip as the focus is
    # the frame before the paint, and stays green while a ring lands here a frame later.
    page.locator("#picked .lf-pick").first.focus()
    rendered(page)
    assert page.locator("[data-lf-obligation]").count() == 0, (
        "an answered group wears the ring the switch was not about"
    )


def test_c_in_a_thread_reaches_that_threads_own_box(browser, serve):
    """The panel's open list is the one part of the chrome that holds a thread of
    its own, so a press meaning "say something about this" belongs to that box rather
    than to the page the panel stands over. `threadBox` states the same rule from
    the other side when it declines to seat a widget standing inside a thread, and the
    obligations and the `m`/`M` walk include the ones an agent sent — without this the same
    question answered one way on the page and another in the panel.

    A resolved thread is the case that has to be asked separately, and the reason this
    test exists at all: it is built by the same `threadNode` and wears the same class,
    under the Resolved state, where it keeps a tab stop and a Reopen button. Reading
    the class alone put the user in a thread whose reply box is not there, and the press
    died on the null with the general box never reached. Whether there is a box is what
    tells them apart — `currentLocationThread` asks for one rather than for the class — so
    the resolved thread falls through to the general box, which is the honest answer for a
    thread with no box of its own to offer."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    live = panel_comment(d, "Six weeks reads long.", {"section": "lede"})
    gone = panel_comment(d, "Settled already.", {"section": "how-cap"})
    append_carried_log_record(d, {"kind": "resolve", "author": "user", "parent": gone})

    page = open_page(browser, url)

    # Located in the thread open in the panel, it means that thread's reply box.
    view = open_panel_thread(page, live)
    view.focus()
    expect(view).to_be_focused()
    page.evaluate("scrollTo(0, document.scrollingElement.scrollHeight)")
    scroll_settled(page)
    before_scroll = page.evaluate("scrollY")
    assert before_scroll > 0, "the page must be away from the thread's passage"
    page.keyboard.press("c")
    expect(panel_field(page)).to_be_focused()
    expect(panel_field(page)).to_have_attribute("name", "reply")
    scroll_settled(page)
    assert page.evaluate("scrollY") == before_scroll

    # And Esc gives that press back: the thread, then the panel. In the panel the old
    # class-only reading and the new climb agree, so this is the consistency half rather
    # than the gate — test_c_in_a_seated_thread_reaches_the_thread_it_is_in is what
    # actually goes red if the climb regresses, the page being where they diverge.
    page.keyboard.press("Escape")
    expect(view).to_be_focused()
    page.evaluate("() => document.activeElement?.blur()")

    # A resolved thread has no box, so the press falls through to the general box, in
    # the page comment card, rather than reaching for one that is not there. What matters is that the thread is not
    # named, which is the phase above's answer and would be the wrong one here.
    open_panel_thread(page, gone).focus()
    page.keyboard.press("c")
    expect(page.locator('.lf-fp-field leaf-text[name="comment"]')).to_be_focused()


def test_c_in_a_seated_thread_reaches_the_thread_it_is_in(browser, serve):
    """The page side of the same question. A widget that seats its own thread
    (`x-thread-seat`) holds one thread per exchange, each with its own box, and the
    user can stand in any of them — so "say something about this" means the box of the
    thread they are in, exactly as it does in the panel. One reading answers both, because
    a rule for the panel and a different one for the page is two answers to one question:
    read off the panel's class alone, the page side sent every thread on a seat to the
    oldest one's box.

    Two threads, and the user in the second: with one there is no wrong answer to give,
    so the pair is what makes the assertion mean anything. The first phase is the control
    — a decision beside the seat, where focusing the widget opens the composer on that
    widget, so a green below is the current location being read and not every press landing in a
    thread.

    The agent has answered both remarks, so each thread here is a whole exchange. Nothing
    in this test turns on that: the press reads where the user is located rather than
    the user's list, so the seat answers the same way before a reply and after one."""
    url = serve(
        leaf_page(
            "seated",
            """
<h1 id="t">Seated</h1>
<lf-ask id="shape-decision"><h2>Which material?</h2>
<lf-options id="shape" choose>
  <lf-option id="sh-steel"><strong>Steel</strong> Galvanised, drop-in.</lf-option>
  <lf-option id="sh-cedar"><strong>Cedar</strong> Cheap; needs sealing.</lf-option>
</lf-options></lf-ask>
<lf-test-plan id="hub" label="The rail">
  <lf-test-task id="fitting" status="active" talk><strong>Who fits the rail?</strong>
  Either crew can take it, and neither has said which week.</lf-test-task>
</lf-test-plan>
""",
        )
    )
    d = serve.page_dir
    said = []
    for text in ("First remark.", "Second remark."):
        append_carried_log_record(
            d,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": text,
                "anchor": {"section": "fitting"},
            },
        )
        said.append(events_model.read_events(d)[-1]["id"])
        append_carried_log_record(
            d,
            {
                "kind": "reply",
                "author": "agent",
                "revision": 1,
                "parent": said[-1],
                "text": "Noted.",
            },
        )

    page = open_page(browser, url)
    threads = page.locator(".lf-page-thread")
    expect(threads).to_have_count(2)

    # The control: focusing a widget that seats nothing, so the press has no thread
    # to prefer and opens the composer on the widget itself.
    page.locator("#shape .lf-pick").first.focus()
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    page.keyboard.press("Escape")
    page.evaluate("() => document.activeElement?.blur()")

    # Located in the second thread, the press means that thread's box.
    second = page.locator(f'.lf-page-thread[data-thread="{said[1]}"]')
    second.focus()
    page.keyboard.press("c")
    expect(second.locator("> .lf-thread-reply leaf-text")).to_be_focused()

    # And Esc hands back the press that got them there, which is the keyboard-is-a-stack
    # rule read on the page rather than in the panel. The box asked for `.lf-thread` and
    # the panel alone, so out here the rung fell through to the page's own "let go": one
    # press in from the thread, one press out to body, with the thread they had been
    # located in two feet away and no key back to it. Both ends read one climb now, so
    # the word going in ("comment on the thread") and the word coming out are about the
    # same element.
    page.keyboard.press("Escape")
    expect(second).to_be_focused()
    # One rung, not two: the page's own way out is the press after this one.
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")


@pytest.mark.parametrize("gesture", ["keyboard", "pointer"])
def test_commenting_on_a_closed_disclosure_leaves_it_closed(browser, serve, gesture):
    """Comment on a visible summary preserves its place and keeps its contents closed."""
    page = open_page(browser, serve(DISCLOSED_PAGE))
    disclosure = page.locator("#dsc")
    summary = page.locator("#dsc-head")
    expect(disclosure).not_to_have_attribute("open", "")

    if gesture == "keyboard":
        summary.focus()
        page.keyboard.press("c")
    else:
        summary.click(modifiers=["Alt"])

    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(disclosure).not_to_have_attribute("open", "")


# A section past the window's foot and past its head, and a small clipped target; the
# nested scroller holds the one past the head and the clipped one.
@pytest.mark.parametrize(
    "target_height,top,nested",
    [
        (1400, 320, False),
        (1400, -500, True),
        (120, 780, False),
        (120, 780, True),
    ],
)
def test_opening_comment_preserves_the_visible_reading_position(
    browser, serve, nested, target_height, top
):
    """Opening an overlay on a visible target is not a navigation gesture.

    A target need not fit the window: a section can extend beyond either edge,
    and a small target can be clipped. The page and a nested reading scroller
    both retain their position through placement and the field's focus handoff.
    """
    content = (
        '<div style="height:1000px"></div>'
        f'<section id="target" tabindex="0" style="height:{target_height}px">'
        "<h2>A section to comment on</h2><p>Keep these words where they are.</p>"
        '</section><div style="height:1400px"></div>'
    )
    if nested:
        content = (
            f'<div id="reading" style="height:820px;overflow:auto">{content}</div>'
        )
    page = open_page(browser, serve(leaf_page("Comment without travel", content)))
    resized(page, 800, 900)
    page.evaluate(
        """({nested, top}) => {
          const target = document.querySelector('#target');
          target.focus({preventScroll: true});
          const box = nested ? document.querySelector('#reading') : document.scrollingElement;
          box.scrollTop += target.getBoundingClientRect().top - top;
        }""",
        {"nested": nested, "top": top},
    )
    scroll_settled(page)
    reading = """() => ({
      page: document.scrollingElement.scrollTop,
      pane: document.querySelector('#reading')?.scrollTop ?? 0,
      target: document.querySelector('#target').getBoundingClientRect().top,
    })"""
    before = page.evaluate(reading)
    page.keyboard.press("c")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    rendered(page)
    scroll_settled(page)
    assert page.evaluate(reading) == before


def test_target_picker_comments_on_a_clipped_card_without_moving_the_board(
    browser, serve
):
    """A visible sliver is enough to target a card and place a comment overlay.

    Choosing either a whole card or a clipped card's visible sliver preserves the
    board's position; the response box fits the room already on screen.
    """
    # Narrow boards stack; this crowded, wider board still scrolls sideways.
    url = serve(SQUEEZED_BOARD_PAGE)
    context = browser.new_context(
        viewport={"width": 720, "height": 844}, has_touch=True
    )

    def choose(page, selector):
        page.keyboard.press("s")
        expect(page.locator(".lf-target-picker-hint")).not_to_have_count(0)
        code = page.evaluate(
            """selector => {
              const target = document.querySelector(selector).getBoundingClientRect();
              return [...document.querySelectorAll('.lf-target-picker-hint')]
                .sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return Math.hypot(ar.left - target.left, ar.top - target.top)
                    - Math.hypot(br.left - target.left, br.top - target.top);
                })[0].dataset.lfHintCode;
            }""",
            selector,
        )
        page.keyboard.type(code)
        expect(page.locator(".lf-fab-input")).to_be_focused()

    def board_reading(page, selector):
        return page.evaluate(
            """selector => {
              const board = document.querySelector('#crowd');
              const view = board.getBoundingClientRect();
              const card = document.querySelector(selector).getBoundingClientRect();
              return {
                scrollLeft: board.scrollLeft,
                visible: Math.max(
                  0,
                  Math.min(card.right, view.right, innerWidth)
                    - Math.max(card.left, view.left, 0),
                ),
                width: card.width,
              };
            }""",
            selector,
        )

    page = open_page(browser, url, context=context)
    before = board_reading(page, "#sq-card-0")
    assert before["visible"] == pytest.approx(before["width"], abs=1), before
    choose(page, "#sq-card-0")
    assert board_reading(page, "#sq-card-0")["scrollLeft"] == before["scrollLeft"]
    page.close()

    page = open_page(browser, url, context=context)
    page.evaluate(
        """() => {
          const board = document.querySelector('#crowd');
          const card = document.querySelector('#sq-card-3');
          board.scrollLeft += card.getBoundingClientRect().left
            - board.getBoundingClientRect().right + 24;
        }"""
    )
    scroll_settled(page)
    before = board_reading(page, "#sq-card-3")
    assert 0 < before["visible"] < before["width"] / 4, before
    choose(page, "#sq-card-3")
    after = board_reading(page, "#sq-card-3")
    assert after == before
    expect(page.locator(".lf-fab-input")).to_have_attribute(
        "aria-label", re.compile("Perch 3")
    )


@pytest.mark.parametrize("reply_visible", [True, False])
def test_c_enters_a_seated_reply_without_revealing_the_thread_heading(
    browser, serve, reply_visible
):
    """A visible reply keeps its place; an off-screen reply is revealed on entry."""
    url = serve(
        leaf_page(
            "Reply without travel",
            '<div style="height:1000px"></div>'
            '<lf-test-plan id="hub" label="A task">'
            '<lf-test-task id="fitting" status="active" talk>A task to discuss.</lf-test-task>'
            '</lf-test-plan><div style="height:1400px"></div>',
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "A short thread beside the task.",
            "anchor": {"section": "fitting"},
        },
    )
    page = open_page(browser, url)
    resized(page, 800, 900)
    thread = page.locator(".lf-page-thread")
    reply = thread.locator("leaf-text")
    expect(reply).to_be_visible()
    thread.evaluate(
        """(thread, visible) => {
          thread.focus({preventScroll: true});
          const reply = thread.querySelector('leaf-text').getBoundingClientRect();
          scrollBy(0, reply.top - (visible ? 110 : 1000));
        }""",
        reply_visible,
    )
    scroll_settled(page)
    before = page.evaluate("scrollY")
    if reply_visible:
        assert thread.bounding_box()["y"] < 42
        assert reply.bounding_box()["y"] >= 100
    else:
        assert reply.bounding_box()["y"] >= 900
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    scroll_settled(page)
    if reply_visible:
        assert page.evaluate("scrollY") == before
    else:
        box = reply.bounding_box()
        assert 42 <= box["y"] and box["y"] + box["height"] <= 900


def test_c_comments_and_g_t_navigates_to_threads(browser, serve):
    """c is contextual comment; g T is the one route into the Threads list."""
    page = open_page(browser, serve(NOTED_PAGE))
    comment = page.locator('.lf-fp-field leaf-text[name="comment"]')
    page.keyboard.press("c")  # page: straight into the panel's page comment
    expect(comment).to_be_focused()
    # One level down, one press out, and Threads never opened.
    page.keyboard.press("Escape")
    expect(comment).not_to_be_focused()
    panel_settled(page, open=False)

    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    threads = page.locator(panel_view("threads"))
    expect(threads).to_be_focused()
    # An empty list holds nothing to comment on, so `c` opens the page comment.
    page.keyboard.press("c")
    expect(comment).to_be_focused()


def test_the_panels_own_c_answers_a_page_whose_log_has_not_arrived(browser, serve):
    """A page whose first poll cannot reach the server is a page the user still writes
    on: `c` opens the page comment, and the panel says only that a comment will not
    send yet. What it has not got is a thread list, so narrowing by what awaits the
    user is dead. Find remains available as the panel's empty search, and the panel's
    scope used to take `c` down with the missing list, so `c` is pressed from the empty
    list too.

    Offline rather than mid-load, because it is the state that stays: a loading page
    answers a moment later, and a page whose server has stopped is where a user sits."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.route("**/api/state*", refuse)
    page.goto(serve(NOTED_PAGE), wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    comment = page.locator('.lf-fp-field leaf-text[name="comment"]')
    expect(page.locator(".lf-fp-leaf")).to_have_attribute(
        "aria-label", re.compile("Lost the connection")
    )

    page.keyboard.press("c")
    expect(comment).to_be_focused()
    page.keyboard.press("Escape")
    expect(comment).not_to_be_focused()
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(panel_view("threads"))).to_be_focused()

    # The missing list leaves the panel's own search: a search over nothing still
    # belongs to the view in front of the page.
    expect(page.get_by_role("button", name="Find a thread or message")).to_be_visible()
    page.keyboard.press("c")
    expect(comment).to_be_focused()
