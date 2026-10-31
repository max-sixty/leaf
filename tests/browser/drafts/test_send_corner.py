"""Send's corner under a mouse: a composer's words run the whole line, and Send stands
in the corner they leave free (response.css; text-field.js, `:state(corner-taken)`;
input.js, `data-send-pointed` and `data-send-armed`)."""

import pytest
from playwright.sync_api import expect
from render_harness import open_page, sending

from browser.margin import LONG_THREAD_PAGE, LONG_THREAD_ROOT
from leaf.render_checks import rendered

# How long the pointer rests on Send before it takes a press (input.js, `SEND_DWELL`).
SEND_DWELL = 150

# The field's shadow root is closed, so the reading keeps each one as it is attached.
# Each fade Send starts is kept too, as whether the words held its corner then.
KEEP_ROOTS = """(() => {
  const attach = Element.prototype.attachShadow;
  window.__lfRoots = new WeakMap();
  Element.prototype.attachShadow = function (init) {
    const root = attach.call(this, init);
    if (this.localName === 'leaf-text') window.__lfRoots.set(this, root);
    return root;
  };
  window.__lfSendFades = [];
  addEventListener('transitionrun', event => {
    const send = event.target;
    if (!send.matches('.lf-compose-submit') || event.propertyName !== 'opacity') return;
    const words = send.parentElement.querySelector(':scope > leaf-text');
    window.__lfSendFades.push(words.matches(':state(corner-taken)'));
  }, true);
})()"""

# Send as the user meets it, beside the last row of the field's words: whether it shows,
# whether a press at its middle reaches it, the size of its disc, and where that row
# stands and ends.
CORNER = """field => {
  const send = field.querySelector(':scope > .lf-compose-submit');
  const words = field.querySelector(':scope > leaf-text');
  const box = send.getBoundingClientRect();
  const middle = [box.left + box.width / 2, box.top + box.height / 2];
  const lines = window.__lfRoots.get(words).querySelectorAll('.cm-line');
  const text = document.createRange();
  text.selectNodeContents(lines[lines.length - 1]);
  const row = [...text.getClientRects()].filter(rect => rect.width).at(-1);
  return {
    taken: words.matches(':state(corner-taken)'),
    shown: getComputedStyle(send).opacity === '1',
    presses: send.contains(document.elementFromPoint(...middle)),
    middle,
    disc: parseFloat(getComputedStyle(send, '::before').blockSize),
    line: parseFloat(getComputedStyle(words).lineHeight),
    rowEnd: row?.right ?? 0,
    rowMiddle: row ? (row.top + row.bottom) / 2 : 0,
    sendStart: box.left,
    value: words.value,
  };
}"""

SENTENCE = (
    "Name the runner in the step itself, since the manifest the supervisor reads is "
    "written later and a reviewer reading this list cannot see it yet"
)


def _open_card_reply(page):
    page.locator('[data-lf-margin-for="open"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    card.get_by_role("textbox", name="Reply", exact=True).click()
    return card.locator(".lf-thread-reply .lf-compose-field")


def _open_panel_field(page):
    page.locator(".lf-fp-field leaf-text").click()
    return page.locator(".lf-fp-field .lf-compose-field")


def _type_to_the_corner(page, field):
    """Type the sentence a character at a time until the last row reaches Send, and
    return the character that reached it."""
    for character in SENTENCE * 3:
        page.keyboard.type(character)
        rendered(page)
        if field.evaluate(CORNER)["taken"]:
            return character
    raise AssertionError("three sentences never reached Send's corner")


def _arrive(page, at):
    page.mouse.move(at[0] - 120, at[1])
    page.mouse.move(*at, steps=3)


@pytest.mark.parametrize(
    ("composer", "engine"),
    [
        ("card", "browser"),
        ("card", "firefox_browser"),
        ("panel", "browser"),
    ],
)
def test_send_leaves_the_corner_to_the_words_and_takes_a_press_after_a_rest(
    composer, engine, request, serve
):
    """The words run under Send's column, and Send stands in the corner until the row
    beside it reaches it, leaving at once and fading back as the row leaves it free.
    Then a press there is the words': a quick press places the
    caret, so a click on the last letters never sends. Pointing at the corner shows
    Send over the words at once, in a square no taller than the row, and it takes a
    press once the pointer has rested there; typing puts it away again. The firefox case
    is the user's browser, which follows nearly every move with a leave."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT]),
        init_script=KEEP_ROOTS,
    )
    field = (_open_card_reply if composer == "card" else _open_panel_field)(page)
    page.keyboard.type("Short")
    rendered(page)
    free = field.evaluate(CORNER)
    assert free["shown"] and free["presses"], free

    reached = _type_to_the_corner(page, field)
    taken = field.evaluate(CORNER)
    assert taken["rowEnd"] > taken["sendStart"], "the words stop short of Send's column"
    assert not taken["shown"] and not taken["presses"], taken

    # The row leaves the corner free again, and Send fades back into it.
    page.keyboard.press("Backspace")
    page.wait_for_function("() => __lfSendFades.includes(false)")
    page.keyboard.type(reached)
    rendered(page)
    assert field.evaluate(CORNER)["taken"]

    # A quick press: the pointer arrives and presses just short of the rest that arms
    # Send, on a paused clock, however slowly the driver delivers the moves.
    page.keyboard.press("ControlOrMeta+Home")
    page.clock.install()
    page.clock.pause_at(
        page.evaluate("() => new Date(Date.now() + 1000).toISOString()")
    )
    _arrive(page, taken["middle"])
    page.clock.run_for(SEND_DWELL - 1)
    pointed = field.evaluate(CORNER)
    assert pointed["shown"] and not pointed["presses"], pointed
    page.mouse.down()
    page.mouse.up()
    page.keyboard.type("Z")
    placed = field.evaluate(CORNER)
    assert placed["value"].index("Z") >= len(placed["value"]) - 4, placed["value"]
    assert not placed["shown"], "typing left Send over the words"

    # A rest: Send shows on arrival, and takes a press once the pointer has stayed.
    _arrive(page, taken["middle"])
    page.clock.run_for(SEND_DWELL)
    rested = field.evaluate(CORNER)
    assert rested["shown"] and rested["presses"], rested
    assert rested["disc"] <= rested["line"], rested
    assert rested["middle"][1] == pytest.approx(rested["rowMiddle"], abs=1), rested
    page.clock.resume()
    with sending(page, "the draft"):
        page.mouse.down()
        page.mouse.up()
    expect(field.locator(":scope > leaf-text")).to_have_js_property("value", "")
    # Only the corner coming free fades Send in: it leaves the words, and shows over
    # them for the pointer, at once.
    assert True not in page.evaluate("() => __lfSendFades")


def _settled(page, field):
    """Wait until the edit has drawn and the box's motion has carried the field's words
    to rest, with Send's fade finished."""
    rendered(page)
    page.wait_for_function(
        "field => !field.getAnimations({subtree: true}).length",
        arg=field.element_handle(),
    )


@pytest.mark.parametrize("engine", ["firefox_browser", "browser"])
def test_send_follows_the_corner_when_an_edit_adds_or_removes_a_line(
    engine, request, serve
):
    """A line the user breaks off the panel's last row frees the corner, and joining
    it back with Backspace fills it again. The panel's field grows and shrinks at its
    top, so its motion carries the words to their new rows after each edit, and once
    it ends Send shows beside the free corner and stays away from the words that reach
    it. The user's capture showed Send over the last row's final letters after a
    Backspace joined two lines, in Firefox. A card's reply grows at its foot, so its
    words don't travel."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT]),
        init_script=KEEP_ROOTS,
    )
    field = _open_panel_field(page)
    page.keyboard.type("A line above.")
    page.keyboard.press("Shift+Enter")
    _type_to_the_corner(page, field)
    # The words themselves, not only the caret after them, run into the corner.
    page.keyboard.type("xy")
    for _ in "xy":
        page.keyboard.press("ArrowLeft")

    page.keyboard.press("Shift+Enter")
    _settled(page, field)
    split = field.evaluate(CORNER)
    assert split["shown"] and split["presses"], split

    page.keyboard.press("Backspace")
    _settled(page, field)
    joined = field.evaluate(CORNER)
    assert joined["rowEnd"] > joined["sendStart"], joined
    assert not joined["shown"] and not joined["presses"], joined
