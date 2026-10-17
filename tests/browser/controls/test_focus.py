"""Where keyboard focus goes and returns: scroll boxes' Tab stops, keyboard scrolling,
hand-back as layers close, focus kept through moves, and the frame audit."""

import re

import pytest
from interact_support import append_carried_log_record
from leaf import event_log as events_model
from leaf.render_checks import rendered
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_cases_layout import (
    PANEL_DIFF_MARKUP,
    WIDE_DIFF_PAGE,
    serious_axe_violations,
)
from render_cases_navigation import DIFF_PAGE
from render_cases_widgets import SCROLLED, WIDE_DIAGRAM_PAGE
from render_harness import (
    LONG_PAGE,
    REPLY_HOST_PAGE,
    expect_comment_notes,
    held_frames,
    holding,
    leaf_page,
    open_page,
    panel_settled,
    resized,
    round_trip,
    scroll_settled,
    shown,
    told,
    write,
)

from browser.threads import open_panel_thread

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_keyboard_reference_is_a_modal_tab_loop_and_returns_to_its_door(
    browser, serve
):
    """A dialog-shaped command reference behaves like a dialog for the native Tab walk."""
    page = open_page(browser, serve(LONG_PAGE))
    door = page.locator(".lf-fp-threads")
    door.focus()
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    assert reference.evaluate("el => el.matches(':modal')"), (
        "the command reference looked modal but left the page interactive behind it"
    )
    stops = reference.locator("input, button, [tabindex]:not([tabindex='-1'])")
    assert stops.count() >= 2, "the reference had no meaningful native Tab loop"
    for _ in range(stops.count() + 2):
        page.keyboard.press("Tab")
        assert reference.evaluate(
            "el => el.contains(document.activeElement)"
            "   || document.activeElement === document.body"
        ), "Tab escaped the command reference onto the suspended page"
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()
    expect(door).to_be_focused()


def test_a_press_on_the_pages_words_is_a_newer_word_than_a_waiting_hold(browser, serve):
    """A hold hands focus back only if the user has not moved on since it began. With no
    stop on body, a press on the page's words takes focus off the control and puts it
    nowhere, with no focusin to count, so a hold still waiting pulled the user back
    from the words they had chosen."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "hold",
                '<h1 id="t">Hold</h1><details id="d"><summary>More</summary>'
                "<p>Inside.</p></details><p id='words'>Words to press.</p>",
            )
        ),
    )
    page.keyboard.press("Tab")
    page.locator("#d > summary").focus()
    page.evaluate(
        """async () => {
          const { holdFocus } = await window.__lfWidgetApi();
          window.__restore = holdFocus(document.querySelector('main'));
        }"""
    )
    page.locator("#words").click()
    assert page.evaluate("() => document.activeElement === document.body")
    assert page.evaluate("() => window.__restore()") is False
    assert page.evaluate("() => document.activeElement === document.body")
    # Nor is the control the user left the place a later change drops them from: a
    # rebuild removing it, read after the press, holds nothing to hand them back to.
    assert (
        page.evaluate(
            """async () => {
          const { holdFocus } = await window.__lfWidgetApi();
          const details = document.querySelector('#d');
          details.remove();
          return holdFocus(details) !== null;
        }"""
        )
        is False
    )


def test_a_page_nobody_has_touched_scrolls_from_the_keyboard(browser, serve):
    """A fresh page gives ordinary keyboard scrolling to the browser's root scrollport.

    Space, PageDown, and arrows work before a user has clicked anywhere. Leaf still
    places focus on body so there is a stable page location to return to after chrome,
    but scrolling no longer depends on teaching the browser about a non-root box.

    All three keys, because they are one fact about which box the browser is scrolling
    rather than three rows in a table — a fix that reached only the key this test named
    would read as a working page here and a dead one to the user. The somewhere is
    asserted as well as the scrolling, and `body` is where focus sits by default: what
    that pins is the page itself as the place to stand, rather than a box built to hold
    the user, which would have a ring to draw and a Tab stop to spend."""
    page = open_page(browser, serve(LONG_PAGE))
    assert page.evaluate("() => document.activeElement === document.body")
    assert (
        page.evaluate("() => getComputedStyle(document.body).outlineStyle") == "none"
    ), "the page wears a focus ring before the user has pressed anything"

    for key in ("Space", "PageDown", "ArrowDown"):
        # Programmatic, so the page is still one nobody has put themselves in: a click
        # to get back to the top would be the very thing this test says is not needed.
        page.evaluate("() => { document.scrollingElement.scrollTop = 0; }")
        page.keyboard.press(key)
        try:
            page.wait_for_function(SCROLLED)
        except PlaywrightTimeout:
            # The console with it: the press can move nothing because the runtime
            # threw, and this names what it said.
            pytest.fail(
                f"{key} moved nothing on a page nobody had clicked in:\n"
                + shown(page.lf_errors)
            )
        # And then the rest of the glide, so the next key's reset lands on a scroll
        # that is over rather than on one still on its way somewhere.
        scroll_settled(page)


def test_esc_hands_the_page_back_after_it_has_closed_the_last_panel(browser, serve):
    """Putting Threads away hands the user back the page, however they opened it.

    Opened with the pointer, the view takes focus; opened from the keyboard, its first
    row does. Either way Escape lands on the page rather than on the mark that opened
    it: a focused button there would own the user's next Space, so the view they had
    just dismissed would come back and nothing would say why.

    The scroll is what the landing has to hand back. Root scrolling is native now, but a
    focused button still owns Space; focus therefore returns to the page rather than
    merely blurring to nowhere."""
    page = open_page(browser, serve(LONG_PAGE, comments=1))
    toggle = page.locator(".lf-fp-threads")
    panel = page.locator('.lf-fp-view[data-view="threads"]')
    ringed = """() => getComputedStyle(document.querySelector('.lf-fp-threads'))
      .outlineStyle !== 'none'"""
    top = "() => document.scrollingElement.scrollTop"
    on_body = "() => document.activeElement === document.body"

    # A user reading: native Space still pages through the document from body.
    page.keyboard.press("Space")
    page.wait_for_function(SCROLLED)
    scroll_settled(page)
    was = page.evaluate(top)

    # Opened with the pointer, the view the user asked for holds the focus.
    toggle.click()
    expect(panel).to_be_visible()
    expect(panel).to_be_focused()

    # Closed with the key, the user is back on the page: nothing rings, and Space is
    # the page's again rather than the button's.
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate(on_body)
    assert not page.evaluate(ringed)
    # And body wears no ring of its own, which is the thing a focus does that a blur
    # cannot: the user has to be somewhere, and the somewhere must not be drawn.
    assert (
        page.evaluate("() => getComputedStyle(document.body).outlineStyle") == "none"
    ), "landing on the page drew a ring around it"
    page.keyboard.press("Space")
    expect(panel).to_be_hidden()
    page.wait_for_function(
        "(was) => document.scrollingElement.scrollTop > was", arg=was
    )
    scroll_settled(page)

    # Opened from the keyboard, and left the same way one opened by pointer is: the
    # view's parent is the document, so Escape lands the user there rather than on
    # the mark that reopens it.
    toggle.focus()
    assert page.evaluate(ringed), "the control the user is standing on says nothing"
    page.keyboard.press("Enter")
    expect(panel).to_be_visible()
    expect(panel.locator(".lf-fp-thread").first).to_be_focused()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate(on_body)

    # And Space is the page's again.
    page.keyboard.press("Escape")
    assert page.evaluate(on_body)
    assert not page.evaluate(ringed)


def test_a_scroll_box_inside_a_widgets_shadow_tree_takes_the_keyboard(browser, serve):
    """Anything a mouse can scroll, a keyboard can reach — including the box a widget
    renders inside its own shadow tree. `reachScrollers` walks the tree it is handed,
    and `querySelectorAll` stops dead at a shadow boundary, so a diff was the one
    scrolling box on a page that a keyboard user had no way into: no tab stop of its
    own, and unlike a board no control inside to borrow one from. The axe sweep says
    so too, and only while some example's diff happens to carry a line this long; this
    is the same rule asked of the widget rather than of the corpus."""
    page = open_page(browser, serve(WIDE_DIFF_PAGE))
    resized(page, 420, 900)
    measured = page.locator("#wide-diff").evaluate(
        """(d) => {
        const viewport = d.shadowRoot.querySelector('code[data-code]');
        return { scrolls: Math.round(viewport.scrollWidth - viewport.clientWidth),
                 tab: viewport.tabIndex };
    }"""
    )
    # The reach, then that there was anything to reach: a diff narrow enough to fit
    # takes no tab stop and is right not to, which would pass the first assertion
    # while saying nothing about the rule.
    assert measured["scrolls"] > 0, "this diff fits, so it proves nothing"
    assert measured["tab"] == 0, "a diff that scrolls is unreachable from the keyboard"
    page.close()

    page = open_page(browser, serve(DIFF_PAGE))
    resized(page, 1200, 900)
    fitted = page.locator("#patch").evaluate(
        """(d) => [...d.shadowRoot.querySelectorAll('code[data-code]')].map(viewport => ({
          scrolls: Math.round(viewport.scrollWidth - viewport.clientWidth),
          tab: viewport.tabIndex,
        }))"""
    )
    assert fitted and all(item["scrolls"] == 0 for item in fitted), fitted
    assert all(item["tab"] == -1 for item in fitted), (
        "a diff that fits added a keyboard stop with nowhere to scroll"
    )


def test_a_hidden_control_does_not_take_a_scroll_boxes_keyboard_route(browser, serve):
    markup = leaf_page(
        "Hidden control in scroll box",
        '<h1>Review</h1><a id="before" href="#scroll">Read code</a>'
        '<div id="scroll" style="width:220px; overflow-x:auto; white-space:nowrap">'
        '<button style="visibility:hidden">Unavailable</button>'
        "<span>alpha_function_name = compute_the_overly_long_value(first_argument, second_argument)</span>"
        "</div>",
    )
    page = open_page(browser, serve(markup))
    box = page.locator("#scroll")
    assert box.evaluate("el => el.scrollWidth > el.clientWidth")
    expect(box).to_have_attribute("tabindex", "0")
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    expect(box).to_be_focused()
    assert box.evaluate("el => el.matches(':focus-visible')")


def test_a_comment_on_a_scrolling_box_leaves_its_tab_stop_alone(browser, serve):
    """A box already holding a control of its own needs no stop of the sweep's: the
    user reaches what is out of sight through the control. A comment on the box adds
    no control to it, so one comment on a flowchart wider than the window leaves the
    keyboard its way to the half of the graph hanging off the right of it.

    Read with the comment on and off the same box, because the assertion says nothing
    unless the box would otherwise have the stop."""
    url = serve(WIDE_DIAGRAM_PAGE)
    page = open_page(browser, url)
    resized(page, 760, 900)
    diagram = page.locator("#flow")
    assert diagram.evaluate("el => el.scrollWidth > el.clientWidth"), (
        "this diagram fits its room, so it proves nothing"
    )
    expect(diagram).to_have_attribute("tabindex", "0")
    expect_comment_notes(page, "#flow", 0)

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "on-the-flow",
            "author": "user",
            "revision": 1,
            "text": "Where does the fallback go?",
            "anchor": {"section": "flow"},
        },
    )
    told(page)
    expect_comment_notes(page, "#flow", 1)
    expect(diagram).to_have_attribute("tabindex", "0")


def test_a_scroll_box_in_a_panel_reply_takes_the_keyboard(browser, serve):
    """The panel holds the same scroll boxes the page does — a reply carries whatever
    widget markup the gate allows — and its column is the narrower of the two, so a box
    that scrolls anywhere scrolls here.

    The sweep that was supposed to cover this stood where each message body is built,
    and needed two things it did not have: that body is not in the document yet, where
    `getComputedStyle` answers "" for every property, and the widget in it has not
    rendered, where the look a scroll box has arrives with the class its module sets on
    the way out. It read an empty overflow off everything it walked and had tagged
    nothing since it was written, which reads as coverage and is the only reason it
    lasted.

    The reply arrives while the panel is already open, because that is the case with
    exactly one reconcile in it. A diff renders asynchronously, so a sweep run where the
    panel inserts its nodes walks a host whose shadow root is still null, and the panel
    does not reconcile on a timer to fix it later: `renderPanel` runs on an open, on a
    fold finishing, and on a new event. Seeding the reply before the page loads gives
    two reconciles and hides all of that."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    append_carried_log_record(
        d,
        {
            "kind": "comment",
            "id": "c-diff",
            "author": "user",
            "revision": 1,
            "text": "What does the change look like?",
        },
    )
    page = open_page(browser, url)
    open_panel_thread(page, "c-diff")  # the thread is open and reconciled once
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-diff",
            "revision": 1,
            "text": "The one line that decides it:",
            "markup": PANEL_DIFF_MARKUP,
        },
    )
    told(page)
    page.wait_for_function(
        """() => {
        const d = document.querySelector('#rp-diff');
        const viewport = d && d.shadowRoot
          && d.shadowRoot.querySelector('code[data-code]');
        return Boolean(viewport) && viewport.tabIndex === 0;
    }"""
    )
    scrolls = page.locator("#rp-diff").evaluate(
        "(d) => { const viewport = d.shadowRoot.querySelector('code[data-code]');"
        " return Math.round(viewport.scrollWidth - viewport.clientWidth); }"
    )
    assert scrolls > 0, "this diff fits the panel, so it proves nothing"


def test_the_accessibility_audit_reads_exposed_frames_and_their_names(browser, serve):
    """Hidden documents are absent; exposed documents and frame names are audited."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Frame audit",
                """<h1>Frame audit</h1>
<iframe id="hidden-frame" title="Hidden practice" hidden srcdoc="<button></button>"></iframe>
<iframe title="Hidden from assistive technology" aria-hidden="true" tabindex="-1"
  srcdoc="<button></button>"></iframe>
<iframe id="shown-frame" title="Visible practice"
  srcdoc="<html lang='en'><title>Practice</title><body><main><h1>Practice</h1>
    <button></button></main></body></html>"></iframe>
""",
            )
        ),
    )
    shown = page.locator("#shown-frame")
    child = shown.element_handle().content_frame()
    child.evaluate("""async () => {
      const frame = document.createElement('iframe');
      frame.id = 'nested-frame';
      frame.title = 'Nested practice';
      frame.srcdoc = `<html lang="en"><title>Nested practice</title><body><main>
        <h1>Nested practice</h1><button></button></main></body></html>`;
      const loaded = new Promise(resolve => frame.addEventListener('load', resolve, {once:true}));
      document.body.append(frame);
      await loaded;
    }""")
    page.evaluate("""async () => {
      const host = document.createElement('div');
      host.setAttribute('aria-hidden', 'true');
      const frame = document.createElement('iframe');
      frame.title = 'Hidden shadow practice';
      frame.srcdoc = '<button></button>';
      host.attachShadow({mode: 'open'}).append(frame);
      document.body.append(host);
      await new Promise(resolve => frame.addEventListener('load', resolve, {once: true}));
    }""")
    violations, _ = serious_axe_violations(page)
    assert [violation["id"] for violation in violations] == [
        "button-name",
        "button-name",
    ], "both exposed documents must be audited"

    child.locator("button").evaluate("button => button.textContent = 'Continue'")
    child.frame_locator("#nested-frame").locator("button").evaluate(
        "button => button.textContent = 'Continue'"
    )
    shown.evaluate("frame => frame.removeAttribute('title')")
    violations, _ = serious_axe_violations(page)
    assert [violation["id"] for violation in violations] == ["frame-title"]

    shown.evaluate("frame => frame.title = 'Visible practice'")
    violations, report = serious_axe_violations(page)
    assert violations == [], report


DISCLOSURE_TABLE_PAGE = leaf_page(
    "disclosure in a wide table",
    '<h1 id="t">Sessions</h1>\n<table id="sessions"><tbody><tr>'
    '<td><details id="more"><summary>More</summary><p>Detail.</p></details></td>'
    + "".join(f"<td>value_number_{i}</td>" for i in range(12))
    + "</tr></tbody></table>",
)


def test_a_disclosure_is_a_scrolling_box_s_own_stop(browser, serve):
    """A box holding a control of its own is reached through that control, and a
    disclosure's `summary` is one: Tab stands on it, and moving along the box from
    there scrolls it. Counted as nothing, it gave the table a second stop of the
    sweep's in front of the one it already had."""
    page = open_page(browser, serve(DISCLOSURE_TABLE_PAGE))
    resized(page, 420, 900)
    table = page.locator("#sessions")
    assert table.evaluate("t => t.scrollWidth > t.clientWidth"), (
        "this table fits, so it proves nothing"
    )
    expect(table).not_to_have_attribute("tabindex", "0")
    assert page.locator("#more > summary").evaluate("s => s.tabIndex") == 0


def test_a_control_tab_skips_leaves_a_scrolling_box_its_own_stop(browser, serve):
    """A control inside a shadow tree whose host is out of the order is one Tab never
    reaches, so a scrolling box holding only that is still the sweep's to give a stop;
    with the host in the order, its control is the box's own."""
    page = open_page(browser, serve(DISCLOSURE_TABLE_PAGE))
    resized(page, 420, 900)
    # A box a script builds is swept when its builder asks, as a module's would be.
    boxes = page.evaluate(
        """async () => {
          const {reachScrollers} = await window.__lfCheckApi();
          const ids = ["out", "in"].map((order) => {
          const box = document.createElement("div");
          box.id = `box-${order}`;
          box.style.cssText = "width:200px;overflow-x:auto;white-space:nowrap";
          const host = document.createElement("span");
          if (order === "out") host.setAttribute("tabindex", "-1");
          host.attachShadow({mode: "open"}).innerHTML = "<button>Inside</button>";
          box.append(host, "x".repeat(400));
          document.querySelector("main").append(box);
          return box.id;
          });
          reachScrollers(document.querySelector("main"));
          return ids;
        }"""
    )
    out, inside = (page.locator(f"#{box}") for box in boxes)
    expect(out).to_have_attribute("tabindex", "0")
    expect(inside).not_to_have_attribute("tabindex", "0")


# One step of `handBack`, run as a layer closes with the user inside it: `layer` holds
# the button they stand on, and hiding it drops their focus. `shut` is a hidden button
# and `open` a shown one, both at the end of `main`.
HAND_BACK = """async (step) => {
  const {handBack} = await window.__lfWidgetApi();
  const frame = () => new Promise((done) => requestAnimationFrame(() => done()));
  const main = document.querySelector('main');
  const made = (tag, id, parent = main, hidden = false) => {
    document.getElementById(id)?.remove();
    const node = document.createElement(tag);
    node.id = id;
    node.textContent = id;
    node.hidden = hidden;
    parent.prepend(node);
    return node;
  };
  const open = made('button', 'open'), shut = made('button', 'shut', main, true);
  const layer = made('div', 'layer');
  made('button', 'inside', layer).focus();
  layer.hidden = true;
  if (step === 'first that lands') handBack(shut, open);
  if (step === 'nothing to land on') handBack(document.createElement('button'));
  if (step === 'body') handBack(document.body);
  if (step === 'shown by the next frame') {
    handBack(shut);
    shut.hidden = false;
  }
  if (step === 'user moved on') {
    handBack(shut);
    open.focus();
    shut.hidden = false;
  }
  if (step === 'user pressed another key') {
    handBack(shut);
    document.dispatchEvent(new KeyboardEvent('keydown', {key: 'x', bubbles: true}));
    shut.hidden = false;
  }
  if (step === 'user landed and let go') {
    handBack(shut);
    open.focus();
    open.blur();
    shut.hidden = false;
  }
  await frame();
  await frame();
  const at = document.activeElement;
  return at.id || at.localName;
}"""


def test_a_closing_layer_hands_the_user_back_to_the_first_place_that_takes_them(
    browser, serve
):
    """Every closer names where the user goes back to, most particular first, and
    `handBack` lands them on the first that takes focus. A place still in the document
    gets the next frame, for a close whose own paint still hides it, unless the user
    moved, let go after a landing, or pressed another key first. With nowhere to go
    the user is let go on the block they are reading, so their next Tab carries on
    from it: not from the closed layer, which is where the browser left them, and
    not from the top of the document, which is where focusing the body would. The
    body is nowhere, for an opener read while nothing held focus."""
    page = open_page(browser, serve(LONG_PAGE))
    landed = {
        step: page.evaluate(HAND_BACK, step)
        for step in [
            "first that lands",
            "shown by the next frame",
            "user moved on",
            "user pressed another key",
            "user landed and let go",
        ]
    }
    assert landed == {
        "first that lands": "open",
        "shown by the next frame": "shut",
        "user moved on": "open",
        "user pressed another key": "body",
        "user landed and let go": "body",
    }
    for step in ["nothing to land on", "body"]:
        assert page.evaluate(HAND_BACK, step) == "body"
        page.keyboard.press("Tab")
        assert page.evaluate(
            "() => !document.activeElement.matches('#open, #shut, .lf-skip')"
        ), f"{step}: the next Tab did not carry on from the block being read"


@pytest.mark.parametrize("new_composer", [False, True], ids=["control", "composer"])
def test_a_reaction_withdrawal_does_not_take_back_a_newer_place(
    browser, serve, new_composer
):
    """Taking a reaction back ends its response gesture before the log answers it."""
    source = leaf_page(
        "A later response",
        '<h1>Review</h1><section id="first"><h2>First passage</h2>'
        '<button id="first-control">First control</button></section>'
        '<div style="height:1500px"></div>'
        '<section id="later"><h2>Later passage</h2>'
        '<button id="later-control">Later control</button></section>'
        '<div style="height:1200px"></div>',
    )
    url = serve(source)
    append_carried_log_record(
        serve.page_dir,
        {
            "id": "reaction-in-force",
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "token": "keep",
            "anchor": {"section": "first-control"},
        },
    )
    page = open_page(browser, url)
    page.locator("#first-control").click()
    page.keyboard.press("e")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("1")
    holding(page, held, 1, "the reaction withdrawal")
    page.locator("#later-control").click()
    current = page.locator("#later-control")
    if new_composer:
        page.keyboard.press("c")
        current = page.locator(".lf-fab-input")
        write(current, "Keep this newer draft")
    expect(current).to_be_focused()
    before = page.evaluate("scrollY")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(current).to_be_visible()
    expect(current).to_be_focused()
    assert page.evaluate("scrollY") == before
    if new_composer:
        expect(current).to_have_js_property("value", "Keep this newer draft")
    withdrawn = events_model.read_events(serve.page_dir)[-1]
    assert (withdrawn["kind"], withdrawn["undoes"]) == (
        "undo",
        "reaction-in-force",
    )


@pytest.mark.parametrize(
    "newer_control", [False, True], ids=["arrival", "newer-control"]
)
def test_a_reference_command_finishes_its_gesture_before_a_newer_control(
    browser, serve, newer_control
):
    """Modal close and command dispatch share one gesture, before another input arrives."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Reference arrival",
                '<h1>Review</h1><div style="height:1200px"></div>'
                '<button id="origin">Original control</button>'
                '<button id="later">Later control</button><div style="height:1000px"></div>',
            )
        ),
    )
    page.locator("#origin").click()
    page.keyboard.press("?")
    search = page.get_by_role("combobox", name="Search commands")
    search.fill("comment on the control")
    command = page.get_by_role("button", name="Comment on the control", exact=True)
    expect(command).to_be_visible()
    expect(command).to_have_attribute("data-lf-available", "true")
    with held_frames(page):
        box = command.bounding_box()
        assert box is not None
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        expect(page.locator(".lf-command-reference")).to_be_hidden()
        if newer_control:
            box = page.locator("#later").bounding_box()
            assert box is not None
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            expect(page.locator("#later")).to_be_focused()
        before = page.evaluate("scrollY")
    rendered(page)
    if newer_control:
        expect(page.locator("#later")).to_be_focused()
    else:
        expect(page.locator(".lf-fab-input")).to_be_focused()
        expect(page.locator("#origin")).to_have_class(re.compile("lf-projected-mark"))
    assert page.evaluate("scrollY") == before


@pytest.mark.parametrize("native_move", [True, False])
@pytest.mark.parametrize("renderer", ["children", "lit"])
def test_retained_moves_keep_native_editor_and_frame_state(
    browser, serve, native_move, renderer
):
    """A reorder or a move to another parent keeps the user typing in the moved row,
    with no focus hold of the caller's, whether or not the browser has `moveBefore`;
    a native move also keeps the row's iframe document."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Retained rows",
                '<h1>Retained rows</h1><div id="rows"></div><div id="other"></div>',
            )
        ),
    )
    page.evaluate(
        """async ([nativeMove, renderer]) => {
      const {render, repeat} = await window.__lfWidgetApi();
      const {setChildren: orderChildren} = await window.__lfWidgetApi();
      const {move} = await window.__lfWidgetApi();
      const rows = document.querySelector('#rows');
      if (!nativeMove) Element.prototype.moveBefore = undefined;
      const nodes = ['a', 'b', 'c'].map(id => {
        const row = document.createElement('div');
        row.dataset.row = id;
        row.innerHTML = `<input aria-label="${id}">
          <iframe title="${id}" srcdoc="<p>Retained frame</p>"></iframe>`;
        return row;
      });
      const paint = nodes => renderer === 'lit'
        ? render(repeat(nodes, node => node.dataset.row, node => node), rows)
        : orderChildren(rows, nodes);
      paint(nodes);
      const editor = rows.querySelector('[data-row=c] input');
      window.blurs = 0;
      editor.addEventListener('blur', () => window.blurs++);
      editor.addEventListener('keydown', event => {
        if (event.key === 'ArrowUp' && event.altKey) {
          event.preventDefault();
          paint([nodes[2], nodes[0], nodes[1]]);
        } else if (event.key === 'ArrowDown' && event.altKey) {
          event.preventDefault();
          const other = document.querySelector('#other');
          if (renderer === 'lit') render(nodes[2], other);
          else move(other, nodes[2], null);
        }
      });
    }""",
        [native_move, renderer],
    )
    editor = page.get_by_role("textbox", name="c", exact=True)
    editor.fill("unfinished words")
    editor.evaluate("node => node.setSelectionRange(3, 9, 'backward')")
    frame = page.locator("[data-row=c] iframe")
    expect(page.frame_locator("[data-row=c] iframe").locator("p")).to_have_text(
        "Retained frame"
    )
    frame.evaluate("node => window.heldDocument = node.contentDocument")
    for key, parent in [("Alt+ArrowUp", "#rows"), ("Alt+ArrowDown", "#other")]:
        page.keyboard.press(key)
        expect(page.locator(f"{parent} > [data-row=c]")).to_have_count(1)
        if key == "Alt+ArrowUp":
            expect(page.locator("#rows > [data-row]").first).to_have_attribute(
                "data-row", "c"
            )
        expect(editor).to_be_focused()
        expect(editor).to_have_value("unfinished words")
        assert editor.evaluate(
            "node => [node.selectionStart, node.selectionEnd, node.selectionDirection]"
        ) == [3, 9, "backward"]
        if native_move:
            assert page.evaluate("window.blurs") == 0
            assert frame.evaluate(
                "node => node.contentDocument === window.heldDocument"
            )
        else:
            assert page.evaluate("window.blurs") > 0


def test_unfocused_editor_move_leaves_later_selection_alone(browser, serve):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Editor caret",
                "<h1>Editor caret</h1><div id='first'></div><div id='second'></div>",
            )
        ),
    )
    page.evaluate("""() => new Promise(resolve => {
      const field = document.createElement('leaf-text');
      field.value = 'Intentional selection';
      document.querySelector('#first').append(field);
      document.addEventListener('selectionchange', () => queueMicrotask(resolve), {once: true});
      field.focus();
      field.setSelectionRange(4, 4);
    })""")
    held = page.evaluate("""() => {
      const field = document.querySelector('#first leaf-text');
      field.blur();
      const unfocused = !field.matches(':focus');
      document.querySelector('#second').moveBefore(field, null);
      return [field.selectionStart, unfocused];
    }""")
    assert held == [4, True]
    editor = page.locator("#second leaf-text")
    page.evaluate("""() => new Promise(resolve => {
      document.addEventListener('selectionchange', () => queueMicrotask(resolve), {once: true});
      const field = document.querySelector('#second leaf-text');
      field.focus();
      field.setSelectionRange(9, 9);
    })""")
    expect(editor).to_be_focused()
    assert editor.evaluate("node => [node.selectionStart, node.selectionEnd]") == [9, 9]
