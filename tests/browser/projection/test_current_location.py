"""The current location (the ring, Escape, navigation, the obligation walk) and the presses,
obligations, controls and drafts they keep across a revision."""

import re

import pytest
from interact_support import append_carried_log_record, declare_on_page
from playwright.sync_api import expect
from render_cases_interaction import (
    LIVE_KEYS_APPARATUS,
    LIVE_KEYS_APPARATUS_REWRITTEN,
    LIVE_KEYS_OBLIGATION_REWRITTEN,
    LIVE_KEYS_OBLIGATION_WITHDRAWN,
    LIVE_KEYS_V1,
    LIVE_KEYS_V2,
    LIVE_KEYS_V3,
    OBLIGATIONS_IN_ORDER,
    OBLIGATIONS_PAGE,
    RING,
    answered_comment,
    live_url,
)
from render_cases_layout import token_colour
from render_cases_navigation import address_code, go_to_address
from render_harness import (
    active_digit_bindings,
    draft_control,
    expect_obligations_answered,
    expect_panel_offers,
    leaf_page,
    open_page,
    panel_field,
    panel_settled,
    resized,
    round_trip,
    scroll_settled,
    sending,
    stamp_page,
    suggestion_control,
    take_browser_errors,
    told,
    wait_for_revision,
    write,
)

from browser.threads import PANEL_REPLY, open_panel_thread, thread_row
from leaf.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_presses_a_user_is_mid_way_through_survive_the_page_following(
    browser, serve
):
    """A revision arriving under a user mid-press keeps their next press live.

    Two kinds of pending input meet an activation. A sequence is the runtime's: bare `g`
    names the visible targets, and the chips are read off whichever document is current,
    so the window holds through the revision and the hints land on the new page — minus
    the hint for a link the revision took away, which is the honest reading. The user's
    current location is the document's: the obligation's actions remain live over a focused pick mark,
    and a revision that leaves that widget's markup alone leaves the mark itself alone,
    so the digit still picks and the panel's field acknowledges it. One revision arrives
    as a draft and the next as a stamped version, since both bring the page to the user
    by the same door."""
    version_url = serve(LIVE_KEYS_V1)
    page = open_page(browser, live_url(version_url))
    chips = page.locator(".lf-go-to-hint")
    link_chips = page.locator('.lf-go-to-hint[data-lf-go-to-kind="Link"]')

    page.keyboard.press("g")
    expect(link_chips).to_have_count(3)
    (serve.page_dir / "index.html").write_text(LIVE_KEYS_V2)
    told(page)
    expect(page).to_have_title("Live keys second")
    expect(link_chips).to_have_count(2)
    # The sequence followed the new document: its address reaches the new page.
    page.keyboard.type(address_code(page, "Link", "lk-link-three"))
    expect(page.locator("#lk-para")).to_be_focused()
    expect(chips).to_have_count(0)

    mark = page.locator("#lk-one .lf-pick")
    mark.focus()
    expect(mark).to_be_focused()
    assert active_digit_bindings(page) == "1–3"
    # A stamped version this time, which is the other way a page moves under a user.
    # Its announcement arrives immediately; the panel may queue it behind the
    # earlier draft notice, so the field need not change before the next press.
    stamp_page(serve.page_dir, LIVE_KEYS_V3, "third")
    told(page)
    expect(page).to_have_title("Live keys third")
    expect(page.locator(".lf-live")).to_have_text("Updated to v2")
    assert page.locator(".lf-toast").count() == 0
    # The same mark, still holding the focus the user put on it: the revision rewrote
    # nothing in this widget, so nothing replaced it.
    expect(page.locator("#lk-one .lf-pick")).to_be_focused()
    assert active_digit_bindings(page) == "1–3", (
        "the revision took the user's keys down"
    )
    page.keyboard.press("2")
    expect(page.locator("#lk-two")).to_have_attribute("chosen", "")
    expect(page.locator(".lf-live")).to_have_text("Chose “Two”")
    round_trip(page)


def test_a_revision_that_restates_an_obligation_preserves_the_users_location_in_it(
    browser, serve
):
    """The obligation a user is working survives the revision that rewrites it.

    A patch keeps every node the revision did not rewrite, so an untouched control is
    still holding the focus the user put on it. The question they are answering is the
    one thing a revision is most likely to rewrite, and rewriting it replaced every node
    inside — which used to drop the user onto `body` in the same breath as "Updated
    to …". An obligation is named by a declared id rather than by a control's shape, so the
    current location is a lookup: the user is put back on the obligation, or on the control that
    answers it, according to which of the two they held. A revision that withdraws the
    obligation has nowhere to put them back, which the tests below cover along with the user
    who was holding one of its controls.
    """
    version_url = serve(LIVE_KEYS_V1)
    page = open_page(browser, live_url(version_url))
    decision = page.locator("#lk-decision")

    page.keyboard.press("m")
    expect(decision).to_be_focused()
    (serve.page_dir / "index.html").write_text(LIVE_KEYS_OBLIGATION_REWRITTEN)
    told(page)
    expect(page).to_have_title("Live keys rewritten")
    expect(panel_field(page)).to_have_attribute(
        "placeholder", re.compile("^Updated to Draft after v1")
    )
    expect(decision).to_be_focused()
    # The current location, not a bare tab stop: the obligation's own action routes are live over the user
    # again, and the third option the revision brought is among them.
    assert active_digit_bindings(page) == "1–4"
    page.keyboard.press("3")
    expect(page.locator("#lk-three")).to_have_attribute("chosen", "")


def test_a_restated_obligation_returns_a_user_to_the_question_not_to_a_control(
    browser, serve
):
    """A user inside the obligation comes back to its opening, never to a guessed control.

    Which control they were holding is not a thing the obligation can answer: the controls are
    the widget's, most carry no id, and the first one that answers the obligation is the
    walk's landing rule rather than a restore. Handing that back is the failure
    version.js names — a user holding the second option would be given the first, and
    their next press would choose it. The obligation's opening holds a lent tab stop rather
    than a decision, so the digits still reach the option they meant and Space decides
    nothing. Where the revision withdraws the question there is nothing to come back to,
    and `body` is the honest answer.
    """
    version_url = serve(LIVE_KEYS_V1)
    page = open_page(browser, live_url(version_url))
    mark = page.locator("#lk-two .lf-pick")
    mark.focus()
    expect(mark).to_be_focused()

    (serve.page_dir / "index.html").write_text(LIVE_KEYS_OBLIGATION_REWRITTEN)
    told(page)
    expect(page).to_have_title("Live keys rewritten")
    expect(page.locator("#lk-decision")).to_be_focused()
    # The press they had lined up decides nothing on its own, and the option they were
    # holding is still the one their own digit reaches.
    page.keyboard.press("Space")
    expect(page.locator("lf-option[chosen]")).to_have_count(0)
    page.keyboard.press("2")
    expect(page.locator("#lk-two")).to_have_attribute("chosen", "")


def test_a_revision_gives_back_the_apparatus_the_user_was_working_with(browser, serve):
    """What the author named survives the widget the revision replaced whole.

    A patch keeps the nodes a revision did not rewrite, and a widget is never one of
    them: a controller owns its children, so restating the question replaces the field
    the user was writing in, the box they had opened and the box they had scrolled.
    None of that is in the log, so no projection puts it back. The authored id is what
    makes it recoverable — the same identity the patch matches nodes on — so the carry
    is a lookup, and an element the author left unnamed still keeps nothing.
    """
    version_url = serve(LIVE_KEYS_APPARATUS)
    page = open_page(browser, live_url(version_url))
    note = page.locator("#lk-note")
    note.click()
    note.type("half a thought")
    page.locator("#lk-why").evaluate("el => { el.open = true; }")
    page.locator("#lk-evidence").evaluate("el => { el.scrollTop = 40; }")
    # Put the caret back inside the words rather than at their end, so a restore that
    # merely refills the field is not mistaken for one that puts the user back in it.
    note.evaluate("el => el.setSelectionRange(4, 4)")
    expect(note).to_be_focused()

    (serve.page_dir / "index.html").write_text(LIVE_KEYS_APPARATUS_REWRITTEN)
    told(page)
    expect(page).to_have_title("Live keys rewritten")
    # The widget did go whole: the heading is the revision's.
    expect(page.locator("#lk-decision h2")).to_have_text(
        "Which one, now the costs are in?"
    )
    expect(page.locator("#lk-note")).to_have_value("half a thought")
    expect(page.locator("#lk-note")).to_be_focused()
    assert page.locator("#lk-note").evaluate("el => el.selectionStart") == 4
    assert page.locator("#lk-why").evaluate("el => el.open") is True
    assert page.locator("#lk-evidence").evaluate("el => el.scrollTop") == 40
    # Located in the obligation is where the user already is, so the obligation restore has nothing
    # to do and does not pull them out of the field onto the question.
    assert page.locator("#lk-note").evaluate("el => el === document.activeElement")


def test_a_revision_gives_values_to_controls_the_user_never_touched(browser, serve):
    """An untouched control is the author's to set, whatever kind of control it is.

    A tick the author gave no value of its own answers `"on"`, and a range answers its
    midpoint, both against a `defaultValue` the author left empty. Ask the platform's
    default and every such control reads as user state on the way out, and arrives
    written over whatever the next revision authored. The authored node answers the same
    way the live one does, so asking it instead finds nothing to carry.

    The other side of that: a control the user did move is theirs, whatever its kind.
    The authored range still reads its midpoint, so a range the user dragged disagrees
    with it and crosses into the widget the revision replaced. A rule keyed on the kind
    of control instead — words carry, the rest do not — keeps the untouched tick and
    range from crossing only by leaving every range behind, the user's drag included.

    A disclosure has no `defaultOpen` to answer with, so the state the carry reads off
    the live box is the author's own until the user moves it: reading the box alone
    would carry the outgoing revision's shut over an arriving revision that opens it.
    The baseline is the authored markup of the revision the user is reading, so an
    untouched box is left to the arriving revision.
    """
    moved = (
        ' <label for="lk-moved">How far</label>'
        ' <input id="lk-moved" name="lk-moved" type="range"></p>'
    )
    unvalued = (
        '<p><label for="lk-tick">Also</label>'
        ' <input id="lk-tick" name="lk-tick" type="checkbox">'
        ' <label for="lk-dial">How much</label>'
        ' <input id="lk-dial" name="lk-dial" type="range"></p>'
    )
    valued = unvalued.replace('type="checkbox"', 'type="checkbox" value="yes"').replace(
        'type="range"', 'type="range" value="80"'
    )
    unvalued = unvalued.replace("</p>", moved)
    valued = valued.replace("</p>", moved)
    first = LIVE_KEYS_APPARATUS.replace(
        '<details id="lk-why">', unvalued + '<details id="lk-why">'
    )
    second = LIVE_KEYS_APPARATUS_REWRITTEN.replace(
        '<details id="lk-why">', valued + '<details id="lk-why" open>'
    )

    version_url = serve(first)
    page = open_page(browser, live_url(version_url))
    # The platform's own answers, set against the empty default the author wrote.
    assert page.locator("#lk-tick").evaluate("el => [el.value, el.defaultValue]") == [
        "on",
        "",
    ]
    assert page.locator("#lk-dial").evaluate("el => [el.value, el.defaultValue]") == [
        "50",
        "",
    ]
    # The user works the field and one range, and leaves the other two alone.
    note = page.locator("#lk-note")
    note.click()
    note.type("half a thought")
    page.locator("#lk-moved").fill("17")
    assert page.locator("#lk-moved").evaluate("el => el.value") == "17"
    assert page.locator("#lk-why").evaluate("el => el.open") is False

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Live keys rewritten")
    # The widget did go whole, so the carry is what decides these controls.
    expect(page.locator("#lk-decision h2")).to_have_text(
        "Which one, now the costs are in?"
    )
    assert page.locator("#lk-tick").evaluate("el => el.value") == "yes"
    assert page.locator("#lk-dial").evaluate("el => el.value") == "80"
    # While the field whose value is the user's own words still crosses, and the range
    # the user moved.
    expect(page.locator("#lk-note")).to_have_value("half a thought")
    assert page.locator("#lk-moved").evaluate("el => el.value") == "17"
    assert page.locator("#lk-why").evaluate("el => el.open") is True


def test_a_revision_that_rewrites_a_draft_leaves_the_user_where_they_stand(
    browser, serve
):
    """A draft's open editor comes back with it, and does not take the user with it.

    The draft reads an open editor's words back from its own store whenever it
    connects — which a revision rewriting the draft makes it do. Getting the words back
    is right. The editor taking the focus is not, when the user had left the editor
    open and gone to stand on something else: the revision is news, and news with no
    gesture behind it moves nobody.
    """
    draft = '<lf-draft id="plan"><pre>Ship it.</pre></lf-draft>'
    first = LIVE_KEYS_V1.replace('<p id="lk-para">', draft + '\n<p id="lk-para">')
    second = first.replace(
        "<title>Live keys first</title>", "<title>Live keys rewritten</title>"
    ).replace("<pre>Ship it.</pre>", "<pre>Ship it on Friday.</pre>")

    page = open_page(browser, live_url(serve(first)))
    draft_control(page, "edit", "plan").click()
    editor = page.locator("lf-draft leaf-text")
    expect(editor).to_be_focused()
    write(editor, "Ship it, but louder.")
    # The user leaves the editor open and goes to stand on the question instead.
    pick = page.locator("#lk-one .lf-pick")
    pick.focus()
    expect(pick).to_be_focused()

    (serve.page_dir / "index.html").write_text(second)
    told(page)
    expect(page).to_have_title("Live keys rewritten")
    # The rewritten draft has connected and read its edit back: the words are kept.
    expect(editor).to_have_js_property("value", "Ship it, but louder.")
    expect(pick).to_be_focused()


def test_the_replacing_install_gives_back_the_same_apparatus(browser, serve):
    """A revision that opens a fresh document carries the same named state across.

    Nothing of the old document survives here, so every record in the handoff names
    something the user would otherwise have lost — there is no held node to skip. The
    user was told the same "Updated to …" either way and cannot tell the two installs
    apart, so neither may answer differently.
    """
    module = """<script type="module">
customElements.define('page-counter', class extends HTMLElement {
  connectedCallback() { this.textContent = 'count 0'; }
});
</script>"""
    first = LIVE_KEYS_APPARATUS.replace("</head>", module + "</head>")
    second = LIVE_KEYS_APPARATUS_REWRITTEN.replace(
        "</head>", module.replace("count 0", "count 10") + "</head>"
    )
    page = open_page(browser, live_url(serve(first)))
    note = page.locator("#lk-note")
    note.click()
    note.type("half a thought")
    page.locator("#lk-why").evaluate("el => { el.open = true; }")
    page.locator("#lk-evidence").evaluate("el => { el.scrollTop = 40; }")
    original_document = page.evaluate("performance.timeOrigin")

    (serve.page_dir / "index.html").write_text(second)
    told(page)

    expect(page).to_have_title("Live keys rewritten")
    assert page.evaluate("performance.timeOrigin") != original_document, (
        "the revision was patched in, so this proves nothing about the other install"
    )
    expect(page.locator("#lk-note")).to_have_value("half a thought")
    expect(page.locator("#lk-note")).to_be_focused()
    assert page.locator("#lk-why").evaluate("el => el.open") is True
    assert page.locator("#lk-evidence").evaluate("el => el.scrollTop") == 40


@pytest.mark.parametrize("start", ["generated", "authored"])
def test_replacing_document_yields_to_input_before_runtime_loads(browser, serve, start):
    """The fresh page belongs to its reader before its module graph arrives: the
    field the reader clicks keeps its focus and the words typed into it."""
    html = leaf_page(
        "Arrival",
        '<h1>Arrival</h1><lf-activity id="feed"></lf-activity>'
        '<section id="notes"><h2>Notes</h2>'
        '<input id="first" type="text" aria-label="First">'
        '<input id="second" type="text" aria-label="Second"></section>',
    )
    page = open_page(browser, live_url(serve(html)))
    first = page.locator(
        "#feed .lf-activity-news" if start == "generated" else "#first"
    )
    first.focus()
    expect(first).to_be_focused()
    original_document = page.evaluate("performance.timeOrigin")
    blocked = []
    page.route("**/leaf.js", lambda route: blocked.append(route))
    stamp_page(
        serve.page_dir,
        html.replace("</head>", '<script type="module">void 0;</script></head>'),
        "Replace executable inputs",
    )
    page.wait_for_function(
        "old => performance.timeOrigin !== old", arg=original_document
    )
    page.wait_for_function("document.readyState !== 'loading'")
    assert blocked, "the runtime module must still be withheld"
    second = page.locator("#second")
    second.click()
    page.keyboard.type("Keep this input")
    expect(second).to_be_focused()
    page.unroute("**/leaf.js")
    for route in blocked:
        route.continue_()
    wait_for_revision(page, 2)
    wait_until_ready(page)
    expect(second).to_be_focused()
    expect(second).to_have_value("Keep this input")


def test_replacing_document_keeps_typing_while_presentation_is_held(browser, serve):
    """An authored field receives real keys before the fresh state answer arrives."""
    module = '<script type="module">void 0;</script>'
    first = LIVE_KEYS_APPARATUS.replace("</head>", module + "</head>")
    second = LIVE_KEYS_APPARATUS_REWRITTEN.replace(
        "</head>", module.replace("void 0", "void 1") + "</head>"
    )
    page = open_page(browser, live_url(serve(first)))
    note = page.locator("#lk-note")
    note.click()
    note.type("half a thought")
    original_document = page.evaluate("performance.timeOrigin")
    replaced = False
    blocked = []

    def navigated(frame):
        nonlocal replaced
        if frame == page.main_frame:
            replaced = True

    def state_answer(route):
        if replaced:
            blocked.append(route)
        else:
            route.continue_()

    page.on("framenavigated", navigated)
    page.route("**/api/state*", state_answer)
    (serve.page_dir / "index.html").write_text(second)
    # Deliberately test the startup interval: final readiness is held at the HTTP
    # boundary, while the replacement owes the field its focus and native keys.
    page.wait_for_function(
        "old => performance.timeOrigin !== old", arg=original_document
    )
    expect(page).to_have_title("Live keys rewritten")
    expect(note).to_be_focused()
    assert page.locator("body").get_attribute("data-lf-presented") is None
    page.keyboard.type(" continued")
    expect(note).to_have_value("half a thought continued")
    assert blocked
    page.unroute("**/api/state*", state_answer)
    for route in blocked:
        route.continue_()
    wait_until_ready(page)
    expect(note).to_have_value("half a thought continued")
    expect(note).to_be_focused()


def test_a_withdrawn_obligation_leaves_the_user_on_the_page(browser, serve):
    """A revision that takes the question away has nowhere to put the user back."""
    version_url = serve(LIVE_KEYS_V1)
    page = open_page(browser, live_url(version_url))
    mark = page.locator("#lk-two .lf-pick")
    mark.focus()
    expect(mark).to_be_focused()

    (serve.page_dir / "index.html").write_text(LIVE_KEYS_OBLIGATION_WITHDRAWN)
    told(page)
    expect(page).to_have_title("Live keys without it")
    expect(page.locator("body")).to_be_focused()


def test_a_user_working_an_obligation_keeps_it_across_a_replacing_document(
    browser, serve
):
    """The fresh-document install hands back the same current location the patch does.

    A revision whose executable identity differs cannot be patched in, so the user
    arrives in a new document where nothing they held exists. They were told the same
    "Updated to …" either way and cannot tell the two installs apart, so the obligation rides
    across in the one-use handoff beside their reading position.
    """
    module = """<script type="module">
customElements.define('page-counter', class extends HTMLElement {
  connectedCallback() { this.textContent = 'count 0'; }
});
</script>"""
    first = LIVE_KEYS_V1.replace("</head>", module + "</head>")
    second = LIVE_KEYS_OBLIGATION_REWRITTEN.replace(
        "</head>", module.replace("count 0", "count 10") + "</head>"
    )
    page = open_page(browser, live_url(serve(first)))
    page.keyboard.press("m")
    expect(page.locator("#lk-decision")).to_be_focused()
    original_document = page.evaluate("performance.timeOrigin")

    (serve.page_dir / "index.html").write_text(second)
    told(page)

    expect(page).to_have_title("Live keys rewritten")
    assert page.evaluate("performance.timeOrigin") != original_document, (
        "the revision was patched in, so this proves nothing about the other install"
    )
    expect(page.locator("#lk-decision")).to_be_focused()
    assert active_digit_bindings(page) == "1–4"


def test_the_obligation_walk_keeps_its_place_when_a_version_lands(browser, serve):
    """A stamped version follows by navigation, and the user's place rides across.
    The passage they were reading did; where the walk had got to was a variable in a
    module the navigation threw away, so it did not, and the user was demoted without
    a word from the most exact reading of where they stand to the coarsest. Located on
    the third of four obligations when v2 landed, they pressed `m` and were handed the third
    again — after looking slightly back above that obligation, the block at the top of the
    window is somewhere they had already walked past.

    So the walk's place travels in the same record as the passage, and the press after
    the version lands is the press they would have made before it. The ring is not owed a
    record of its own: it is painted from the focus, and the activation hands the user
    back the control they were located on, so the obligation they were in wears it still."""
    url = serve(OBLIGATIONS_PAGE)
    d = serve.page_dir
    page = open_page(browser, live_url(url))
    # Short enough that an obligation in the middle of the window has page text above it,
    # which is the whole of what makes the coarse reading the wrong one.
    resized(page, 900, 400)

    for item in OBLIGATIONS_IN_ORDER[:3]:
        page.keyboard.press("m")
        expect(page.locator(f"#{item}")).to_have_attribute("data-lf-obligation", "1")
    scroll_settled(page)

    # Obligation travel now starts at the obligation's opening, which normally makes the coarse
    # reading agree with the saved landing. Look back just far enough to make the two
    # meanings diverge: the scroll position says the preceding change, while the walk's
    # exact record still says the third obligation.
    page.evaluate("""() => {
        const earlier = document.getElementById('refill-now').getBoundingClientRect();
        document.scrollingElement.scrollBy({top: earlier.bottom - 220, behavior: 'instant'});
    }""")

    stamp_page(d, OBLIGATIONS_PAGE, "two")
    wait_for_revision(page, 2)

    expect(page.locator("#t-baffles-decision")).to_have_attribute(
        "data-lf-obligation", "1"
    )
    expect(page.locator("[data-lf-obligation]")).to_have_count(1)
    # The condition the restore is for, stated rather than assumed: an earlier obligation's
    # own prose is on screen above the one the user was located on, so a walk reading
    # the page alone starts behind them and steps forward onto the obligation they just left.
    position = page.evaluate("""() => {
            const decision = document.getElementById('t-baffles-decision').getBoundingClientRect();
        const earlier = document.getElementById('refill-now').getBoundingClientRect();
        return {earlierBottom: earlier.bottom, decisionTop: decision.top,
                scrollTop: document.scrollingElement.scrollTop};
    }""")
    assert 42 < position["earlierBottom"] <= position["decisionTop"], position
    page.keyboard.press("m")
    expect(page.locator("#t-bath-decision")).to_have_attribute(
        "data-lf-obligation", "1"
    )


def test_a_bare_choice_hands_its_ring_to_the_row_the_user_tabs_to(browser, serve):
    """A choosing lf-options that is the decision itself, with no lf-ask round it,
    gives its location ring up to the row as one inside an ask does. It kept it: a
    Tab in drew the decision's ring at the region's gap and the row's inside the
    frame, two accent lines a few pixels apart for one fact."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Bare choice",
                """<h1 id="h">Bare choice</h1>
<lf-options id="ship" choose>
  <lf-option id="ship-monday"><strong>Ship Monday</strong></lf-option>
  <lf-option id="ship-thursday"><strong>Ship Thursday</strong></lf-option>
</lf-options>""",
            )
        ),
    )
    choice = page.locator("#ship")
    page.keyboard.press("m")
    expect(choice).to_have_attribute("data-lf-obligation", "1")
    arrived = choice.evaluate(
        "el => { const s = getComputedStyle(el); return [s.outlineStyle, s.outlineOffset,"
        " getComputedStyle(document.documentElement).getPropertyValue('--focus-region-gap').trim()]; }"
    )
    assert arrived[0] == "solid" and arrived[1] == arrived[2], arrived

    page.keyboard.press("Tab")
    expect(page.locator("#ship-monday .lf-pick")).to_be_focused()
    assert choice.evaluate(RING)[0] == "none", (
        "the decision kept its ring round the row"
    )
    assert page.locator("#ship-monday").evaluate(RING)[0] == "solid"


def test_the_ring_says_where_the_user_is_located(browser, serve):
    """One ring, meaning one thing: this is where the user is located. It is painted
    from the focus, so every way into a decision paints it and leaving takes it off.

    The walk used to write it, and nothing ever took it off. So it said where the walk
    had left them rather than where they were: press `d`, click away, work in the panel
    for ten minutes, and a decision nobody was located in went on wearing "you are here" —
    while a user who had reached the same decision by Tab or by clicking one of its
    controls got no ring at all. The same place, marked or not by how they arrived.

    The chrome wears the same band, because a user who has backed out of the panel is
    located on a button and that is the same fact about them. It wore the browser's own
    ring there, in the browser's blue, a few inches from a decision ringed in the page's
    accent, with nothing saying the two rectangles meant one thing.

    A joined options control is the one shape that draws the band somewhere else: it is
    already a framed box, so a ring around the decision *and* one inside it would read as
    a second border that comes and goes, and while the user is in the control the exact
    row the keyboard is on carries the band alone. Which row, in the same band — one ring
    still meaning one thing. An arrival is the other side of that: it places the user on
    the decision rather than in the control, so there the decision's own ring is the one."""
    page = open_page(browser, serve(OBLIGATIONS_PAGE))
    question = page.locator("#live-question-decision")
    page.keyboard.press("m")
    expect(question).to_have_attribute("data-lf-obligation", "1")
    arrival_ring = question.evaluate(
        "ask => { const s = getComputedStyle(ask, '::after'); "
        "return [s.outlineStyle, s.outlineWidth, s.outlineColor]; }"
    )
    assert arrival_ring == [
        "solid",
        "2px",
        token_colour(page, "--accent"),
    ], f"the decision the walk stood the user on is not ringed: {arrival_ring}"

    # One press in, and the band moves to the row rather than doubling: the frame is the
    # control, and a ring around it as well would come and go with the question.
    page.keyboard.press("Tab")
    question_overlay_ring = question.evaluate(
        "ask => getComputedStyle(ask, '::after').outlineStyle"
    )
    assert question_overlay_ring == "none", (
        "the decision drew its own ring around a control that is already a frame: "
        f"{question_overlay_ring}"
    )
    row_ring = page.locator("#lq-keep").evaluate(RING)
    assert row_ring == [
        "solid",
        "2px",
        token_colour(page, "--accent"),
    ], f"the row the user is on is not ringed in the page's own band: {row_ring}"

    # A suggestion hangs its ✓ Accept out in the page margin, so a user working one has
    # two marks for one fact — the ring on the change, the focus band on the margin entry deciding
    # it — and they had better be one band. The margin entry's comes from the runtime's own
    # shared rule, which every press in that margin wears: the suggestion family spelled
    # its own once, which is a family stating a fact about a shape the runtime owns.
    #
    # Real presses verify the keyboard route as well as its focus treatment.
    page.keyboard.press("m")
    suggestion = page.locator("#sug-refill")
    expect(suggestion).to_have_attribute("data-lf-obligation", "1")
    accept = suggestion_control(page, "sug-refill", "accept")
    accept.focus()
    # Tab inside the margin reaches the same suggestion's ✗ Reject, rendered from the
    # same contribution in the options group. The user is still deciding this change,
    # so the ring stays on it. It did not: the secondary control stood nowhere, the band
    # came off the suggestion for as long as the user held that control, and returning
    # to ✓ Accept brought it back a frame later — which is also how the read below came
    # to be taken while nothing on the page was ringed at all.
    #
    # Read after the frame the focus move's repaint is coalesced into, so this states the
    # band the page settles on rather than whichever side of that frame the read lands on.
    page.keyboard.press("Tab")
    rendered(page)
    decision_ring = suggestion.evaluate(RING)
    assert decision_ring == row_ring, (
        "the decision lost its ring while the user held one of its own margin "
        f"controls: {decision_ring} against {row_ring}"
    )
    # Stable identity is the contribution owner plus entry key, independent of which
    # projection surface currently presents it.
    assert accept.count() == 1, (
        "the suggestion has more than one presented Accept control"
    )
    page.keyboard.press("Shift+Tab")
    expect(accept).to_be_focused()
    # A decision that is not a joined control wears the ring itself, and it is the band
    # the row above wore: the two shapes say one thing about the user.
    decision_ring = suggestion.evaluate(RING)
    assert decision_ring == row_ring, (
        "a decision and an options row are drawn in two different bands for the one "
        f"fact: {decision_ring} against {row_ring}"
    )
    assert accept.evaluate(RING) == decision_ring, (
        "the control in the margin is drawn in some other band than the decision it decides: "
        f"{accept.evaluate(RING)} against {decision_ring}"
    )

    # Located somewhere that asks nothing takes it off, rather than leaving it behind.
    page.locator("#h").click()
    expect(page.locator("[data-lf-obligation]")).to_have_count(0)

    # A pointer landing inside an open decision makes it the current location, though no walk brought
    # them there: the ring renders the focus rather than remembering a press.
    page.locator("#live-question .lf-another leaf-text").click()
    expect(question).to_have_attribute("data-lf-obligation", "1")

    # Answering takes it off with the focus still inside: the ring is for the question
    # the user is working, and an answered one is no longer a question.
    page.locator("#lq-token .lf-pick").click()
    expect_obligations_answered(page, "2/5")
    expect(page.locator("[data-lf-obligation]")).to_have_count(0)
    expect(page.locator("#lq-token .lf-pick")).to_be_focused()

    # The chrome's own control, which the user reaches by Tab or by the panel's own
    # keys rather than by backing out of the panel — a surface lands them on the page,
    # never on the control that reopens it. What is asserted here is the band the ring
    # is drawn in while they stand there.
    toggle = page.locator(".lf-fp-on-user")
    toggle.focus()
    # Return by keyboard to exercise the same focus band through sequential navigation.
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(toggle).to_be_focused()
    assert toggle.evaluate(RING) == decision_ring, (
        "the user located in the chrome is drawn in some other band than the "
        f"one a decision uses: {toggle.evaluate(RING)} against {decision_ring}"
    )


STORE_ASK_PAGE = leaf_page(
    "Session store",
    '<h1 id="h">Where sessions live</h1>'
    '<lf-ask id="store-ask"><h3>Which store should hold sessions?</h3>'
    '<lf-options id="store" choose>'
    '<lf-option id="store-redis">Redis</lf-option>'
    '<lf-option id="store-cookie">Signed cookie</lf-option>'
    '<lf-option id="store-db">The main database</lf-option>'
    "</lf-options></lf-ask>",
)


def seed_thread_about_the_ask(page_dir, root, *, resolved=False):
    """A thread on the ask the agent has answered, so the ask stays On me's."""
    append_carried_log_record(
        page_dir,
        {
            "kind": "comment",
            "id": root,
            "author": "user",
            "revision": 1,
            "text": f"A question about the store ({root})",
            "anchor": {"section": "store-ask"},
        },
    )
    append_carried_log_record(
        page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root,
            "responds": root,
            "revision": 1,
            "text": "An answer.",
        },
    )
    if resolved:
        append_carried_log_record(
            page_dir,
            {"kind": "resolve", "author": "user", "parent": root, "revision": 1},
        )


def test_a_thread_about_an_ask_stands_at_the_ask_from_the_panel(browser, serve):
    """Open and resolved panel threads stand at their ask: its ring stays on and
    digits answer it from the view. Opening either thread focuses its reply; Escape
    leaves the reply for the view. A digit typed in the reply stays reply text.
    """
    url = serve(STORE_ASK_PAGE)
    seed_thread_about_the_ask(serve.page_dir, "t-done", resolved=True)
    seed_thread_about_the_ask(serve.page_dir, "t-open")
    page = open_page(browser, url)
    ask = page.locator("#store-ask")

    view = open_panel_thread(page, "t-done")
    expect(page.locator(PANEL_REPLY)).to_be_focused()
    expect(ask).to_have_attribute("data-lf-obligation", "1")
    page.keyboard.press("Escape")
    expect(view).to_be_focused()
    expect(ask).to_have_attribute("data-lf-obligation", "1")
    page.keyboard.press("2")
    expect(page.locator("#store-cookie")).to_have_attribute("chosen", "")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    view = open_panel_thread(page, "t-open")
    reply = page.locator(PANEL_REPLY)
    expect(reply).to_be_focused()
    expect(ask).to_have_attribute("data-lf-obligation", "1")
    page.keyboard.type("3")
    expect(reply).to_have_js_property("value", "3")
    expect(page.locator("#store-db")).not_to_have_attribute("chosen", "")
    page.keyboard.press("Escape")
    expect(view).to_be_focused()
    rendered(page)
    page.keyboard.press("3")
    expect(page.locator("#store-db")).to_have_attribute("chosen", "")


def test_a_thread_opened_in_the_panel_by_the_keyboard_opens_no_card_beside_it(
    browser, serve
):
    """A thread the keyboard opens from Threads shows in the panel alone, and Escape
    from its reply leaves it so. Its view stands at the ask the thread is about, and the
    margin read the keyboard arriving there as an arrival at the ask, so it opened the
    thread's card beside the ask as well: the same thread twice, the card left standing
    after the panel closed."""
    url = serve(STORE_ASK_PAGE)
    seed_thread_about_the_ask(serve.page_dir, "t-open")
    page = open_page(browser, url)
    resized(page, 1400, 900)
    card = page.locator(".lf-margin-preview")

    row = thread_row(page, "t-open")
    row.focus()
    page.keyboard.press("Enter")
    panel_settled(page, view="thread")
    expect(page.locator(PANEL_REPLY)).to_be_focused()
    expect(page.locator("#store-ask")).to_have_attribute("data-lf-obligation", "1")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-view[data-thread='t-open']")).to_be_focused()
    rendered(page)
    expect(card).to_be_hidden()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    expect(card).to_be_hidden()


def test_a_finger_opening_a_thread_about_an_ask_stands_in_its_view(browser, serve):
    """A finger opening a thread reads it first, so no keyboard rises: the view holds
    focus rather than the reply, and the ask it is about wears the ring. The view held
    nothing under a finger, so the ask stayed dark there."""
    url = serve(STORE_ASK_PAGE)
    seed_thread_about_the_ask(serve.page_dir, "t-open")
    context = browser.new_context(
        viewport={"width": 1280, "height": 800}, has_touch=True
    )
    page = open_page(browser, url, context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches")
    view = open_panel_thread(page, "t-open")
    expect(view).to_be_focused()
    expect(page.locator("#store-ask")).to_have_attribute("data-lf-obligation", "1")


def test_an_on_me_card_represents_its_ask(browser, serve):
    """On me's card for an ask represents the ask, as an On row did: focusing the
    card rings the ask, and its digits answer it there."""
    page = open_page(browser, serve(STORE_ASK_PAGE))
    page.locator(".lf-fp-on-user").click()
    panel_settled(page, view="queue")
    card = page.locator(""".lf-fp-on-item[data-key='["widget","widget:store"]']""")
    card.focus()
    expect(page.locator("#store-ask")).to_have_attribute("data-lf-obligation", "1")
    page.keyboard.press("2")
    expect(page.locator("#store-cookie")).to_have_attribute("chosen", "")


def test_escape_lets_go_of_the_obligation_the_users_current_location_names(
    browser, serve
):
    """Escape closes the command reference, then lets go of the obligation and focuses body.
    The next obligation walk reads the visible page place, returning to the first obligation before
    advancing. Letting go also works on a page with no scroll range and after a Page
    Map action leaves focus in a margin cluster."""
    url = serve(OBLIGATIONS_PAGE)
    # A third action puts the suggestion's cluster beyond its two resting controls.
    answered_comment(
        serve.page_dir,
        "Check this wording before accepting it.",
        {"section": "sug-refill"},
    )
    page = open_page(browser, url)
    page.keyboard.press("m")
    expect(page.locator("#live-question-decision[data-lf-obligation]")).to_have_count(1)
    # The reference says the press in its own words. It said "Back out one layer" for
    # every rung, which was true while every rung took a layer of chrome off the page:
    # making a decision current is the user holding something, with no layer over the
    # page at all.
    page.keyboard.press("?")
    expect(
        page.locator(
            '.lf-command-reference [role=row][data-lf-command="navigation.release"]'
        )
    ).to_contain_text("Let go")
    page.keyboard.press("Escape")  # the reference's own rung, which hands focus back
    expect(page.locator(".lf-command-reference")).not_to_have_class(re.compile("open"))
    expect(page.locator("#live-question-decision[data-lf-obligation]")).to_have_count(1)

    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator("[data-lf-obligation]")).to_have_count(0)
    assert page.evaluate("() => document.activeElement === document.body")

    # The directional walk reads the user's current visible place after Escape.
    # Reenter the first obligation from there, then move to the next one.
    page.keyboard.press("m")
    expect(page.locator("#live-question-decision")).to_be_focused()
    # The suggestion's thread comes up beside it, hung from its own entry, which the
    # cluster unfolds to show for as long as the card stands there.
    page.keyboard.press("m")
    expect(page.locator("#sug-refill[data-lf-obligation]")).to_have_count(1)
    walked_item = page.locator('[data-lf-margin-for="sug-refill"]')
    expect(page.locator(".lf-margin-preview")).to_contain_text("Check this wording")
    expect(walked_item.locator(":scope > .lf-margin-options")).to_be_visible()

    # A walk out of an unfolded cluster folds the old destination while suppressing
    # only the new destination's Tab-style arrival. The two halves share one native
    # focus transition, whose focusout and focusin both fire inside focus().
    page.keyboard.press("m")
    expect(page.locator("#t-baffles-decision[data-lf-obligation]")).to_have_count(1)
    expect(walked_item.locator(":scope > .lf-margin-more")).to_be_visible()
    expect(walked_item.locator(":scope > .lf-margin-options")).to_be_hidden()

    # A window tall enough to hold the whole page, so the root has no scroll range and the
    # browser will not focus body as a scrolling affordance.
    resized(page, 1200, 2400)
    assert not page.evaluate(
        "() => document.scrollingElement.scrollHeight > document.scrollingElement.clientHeight"
    ), "the page still scrolls, so this proves nothing about a short one"
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body"), (
        "letting go left the user holding the control on a page that fits the window"
    )

    # A generated Page Map hint arrives the way the walk does and then presses the exact
    # Accept margin entry it names. What unfolds there is that press's own result rather than
    # the arrival's, and the ladder still owes one Escape to let go of where the press
    # left the user.
    with sending(page, "the addressed suggestion's acceptance"):
        go_to_address(page, "Margin entry", "sug-refill", "accept")
    expect(page.locator("#sug-refill lf-new")).to_be_visible()
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    assert page.evaluate(
        """() => Boolean(document.activeElement.closest(
             '[data-lf-margin-for="sug-refill"]'))"""
    ), "the address left the user outside the cluster it pressed"
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")


def test_the_obligation_walk_follows_registry_declarations(browser, serve):
    """Removing an open-request declaration removes that widget from every obligation
    surface without changing the runtime, panel, or keyboard walk."""
    url = serve(OBLIGATIONS_PAGE)

    def undeclare(registry):
        del registry["lf-suggestion"]["x-awaits"]
        del registry["lf-suggestion"]["properties"]["resolves"]

    declare_on_page(serve.page_dir, undeclare)
    stamp_page(
        serve.page_dir,
        (serve.page_dir / "index.html").read_text(),
        "capture the declaration change",
    )

    page = open_page(browser, live_url(url))
    expect_obligations_answered(page, "1/4")
    # The blanket answer went with the declaration that named its verb.
    expect_panel_offers(page, "blanket:accept", offered=False)
    for expected in [
        "live-question-decision",
        "t-baffles-decision",
        "t-bath-decision",
    ]:
        page.keyboard.press("m")
        expect(page.locator(f"#{expected}")).to_have_attribute(
            "data-lf-obligation", "1"
        )


def test_live_revision_drafts_wait_for_the_complete_controller_publication(
    browser, serve
):
    """Replacement drafts recover only after the arriving document is complete."""
    first = leaf_page(
        "Drafts first",
        """<h1>Drafts</h1>
<lf-draft id="revised-draft"><pre>
    The first revision's existing body.
</pre></lf-draft>""",
    )
    second = leaf_page(
        "Drafts second",
        """<h1>Drafts</h1>
<lf-draft id="revised-draft"><pre>
    The second revision's replacement body.
</pre></lf-draft>
<lf-draft id="arriving-draft"><pre>
    The second revision's newly inserted body.
</pre></lf-draft>""",
    )
    page = open_page(browser, live_url(serve(first)))
    revised = page.locator("#revised-draft")
    expect(revised.locator(".lf-draft-body")).to_have_text(
        "The first revision's existing body."
    )
    revised.locator(".lf-draft-body").click()
    editor = revised.locator("leaf-text")
    write(editor, "The user's unsent replacement.\n")
    # The editor stays open with the focus elsewhere; a press away would save it.
    editor.blur()
    expect(editor).not_to_be_focused()
    assert take_browser_errors(page) == []

    stamp_page(serve.page_dir, second, "replace and insert drafts")
    wait_for_revision(page, 2)

    expect(revised.locator(".lf-draft-body")).to_have_text(
        "The second revision's replacement body."
    )
    expect(page.locator("#arriving-draft .lf-draft-body")).to_have_text(
        "The second revision's newly inserted body."
    )
    expect(revised.locator("leaf-text")).to_have_js_property(
        "value", "The user's unsent replacement.\n"
    )
    assert take_browser_errors(page) == []
