"""Send's corner under a mouse: a composer's words run the whole line, and Send stands
in the corner they leave free (response.css; text-field.js, `:state(corner-taken)`;
input.js, `data-lf-send-pointed` and `data-lf-send-armed`)."""

import pytest
from browser.margin import LONG_THREAD_PAGE, LONG_THREAD_ROOT
from playwright.sync_api import expect
from render_harness import open_page, sending

from leaf.source.render_checks import rendered
from leaf_dev.browser import text_field

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
# stands and where its last glyph ends. A space at a row's end hangs past the line, so
# it says nothing about where the line lets words run.
CORNER = """field => {
  const send = field.querySelector(':scope > .lf-compose-submit');
  const words = field.querySelector(':scope > leaf-text');
  const box = send.getBoundingClientRect();
  const middle = [box.left + box.width / 2, box.top + box.height / 2];
  const lines = window.__lfRoots.get(words).querySelectorAll('.cm-line');
  const text = document.createRange();
  text.selectNodeContents(lines[lines.length - 1]);
  const walk = document.createTreeWalker(lines[lines.length - 1], NodeFilter.SHOW_TEXT);
  for (let node; (node = walk.nextNode()); ) {
    const glyph = node.data.search(/\\S\\s*$/);
    if (glyph >= 0) text.setEnd(node, glyph + 1);
  }
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
    text_field(card, name="Reply", exact=True).click()
    return card.locator(".lf-thread-reply .lf-compose-field")


def _open_panel_field(page):
    page.locator(".lf-fp-field leaf-text").click()
    return page.locator(".lf-fp-field .lf-compose-field")


def _type_to_the_corner(page, field):
    """Type the sentence a character at a time until the last row's words run into
    Send's column, and return the reading there. The caret after the words counts
    toward the corner too, so in some faces it takes the corner a character or more
    before the words do; only words in the corner keep it once the caret goes."""
    for character in SENTENCE * 3:
        page.keyboard.type(character)
        rendered(page)
        reading = field.evaluate(CORNER)
        if reading["rowEnd"] > reading["sendStart"]:
            return reading
    raise AssertionError("three sentences never ran the words into Send's column")


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

    taken = _type_to_the_corner(page, field)
    assert taken["taken"] and not taken["shown"] and not taken["presses"], taken

    # The row leaves the corner free again, the words and the caret after them, and
    # Send fades back into it.
    erased = 0
    while field.evaluate(CORNER)["taken"]:
        page.keyboard.press("Backspace")
        rendered(page)
        erased += 1
    page.wait_for_function("() => __lfSendFades.includes(false)")
    page.keyboard.type(taken["value"][-erased:])
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


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_box_s_key_gives_way_to_words_that_reach_it(engine, request, serve):
    """A reply box holding words says the key that enters it just before Send, on Send's
    line, while the words' last row leaves that room free, and the key gives way once
    the row reaches it, as Send gives way to words that reach Send (response.css,
    `.lf-compose-key`; text-field.js, `:state(key-corner-taken)`). Send keeps its own
    corner: words that reach the key alone leave Send standing. The firefox case is the
    user's browser."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(LONG_THREAD_PAGE, events=[LONG_THREAD_ROOT]),
        init_script=KEEP_ROOTS,
    )
    card = page.locator(".lf-margin-preview .lf-page-thread")
    field = _open_card_reply(page)
    key = field.locator(":scope > .lf-compose-key")
    words = field.locator(":scope > leaf-text")

    def stand_on_the_card():
        page.locator("#title").click()
        page.keyboard.press("t")
        expect(card).to_be_focused()
        expect(key).to_have_text("c")
        rendered(page)
        return key.evaluate("key => getComputedStyle(key).opacity")

    page.keyboard.type("Short")
    assert stand_on_the_card() == "1"

    words.click()
    page.keyboard.press("ControlOrMeta+End")
    # The key's room before Send's corner, as the field reads it.
    room = words.evaluate(
        """w => { const s = getComputedStyle(w);
          return parseFloat(s.getPropertyValue('--lf-field-key-corner'))
            - parseFloat(s.getPropertyValue('--lf-field-corner')); }"""
    )
    assert room > 0
    for character in SENTENCE * 3:
        page.keyboard.type(character)
        rendered(page)
        reading = field.evaluate(CORNER)
        if reading["rowEnd"] > reading["sendStart"] - room:
            break
    else:
        raise AssertionError("three sentences never ran the words to the key")
    assert reading["rowEnd"] < reading["sendStart"], reading
    assert stand_on_the_card() == "0"
    assert words.evaluate("w => w.matches(':state(key-corner-taken)')")
    assert field.evaluate(CORNER)["shown"]


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
    """A line the user starts after the panel's last row frees the corner, and joining
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

    page.keyboard.press("Shift+Enter")
    _settled(page, field)
    split = field.evaluate(CORNER)
    assert split["shown"] and split["presses"], split

    page.keyboard.press("Backspace")
    _settled(page, field)
    joined = field.evaluate(CORNER)
    assert joined["rowEnd"] > joined["sendStart"], joined
    assert not joined["shown"] and not joined["presses"], joined
