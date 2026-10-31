"""Where keyboard focus goes and returns: scroll boxes' Tab stops, keyboard scrolling,
hand-back as layers close, focus kept through moves, and the frame audit."""

import re

import pytest
from interact_support import append_carried_log_record
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
    RELEASE_FOCUS,
    REPLY_HOST_PAGE,
    expect_comment_notes,
    held_frames,
    holding,
    leaf_page,
    open_page,
    panel_settled,
    panel_view,
    resized,
    round_trip,
    scroll_settled,
    shown,
    told,
    write,
)

from browser.threads import open_panel_thread
from leaf import event_log as events_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_keyboard_reference_is_a_modal_tab_loop_and_returns_to_its_door(
    browser, serve
):
    """A dialog-shaped command reference behaves like a dialog for the native Tab walk."""
    page = open_page(browser, serve(LONG_PAGE))
    door = page.locator(".lf-fp-on-user")
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


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_tab_from_the_pages_last_control_reaches_the_panels_leaf(
    engine, request, serve
):
    """The chrome's foreground is an empty box holding the panel and the overlays, so a
    Tab never stops on it. Firefox gave the open dialog a Tab stop of its own, which
    drew nothing between the page's last control and the leaf."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(leaf_page("Tab order", '<p>Words <button id="last">Last</button></p>')),
    )
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("Tab")
    expect(page.locator("#last")).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.locator(".lf-fp-leaf")).to_be_focused()


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
    """Putting On me away hands the user back the page, however they opened it.

    Opened with the pointer, the view takes focus; opened from the keyboard, its first
    row does. Either way Escape lands on the page rather than on the mark that opened
    it: a focused button there would own the user's next Space, so the view they had
    just dismissed would come back and nothing would say why.

    The scroll is what the landing has to hand back. Root scrolling is native now, but a
    focused button still owns Space; focus therefore returns to the page rather than
    merely blurring to nowhere."""
    page = open_page(browser, serve(LONG_PAGE, comments=1))
    toggle = page.locator(".lf-fp-on-user")
    panel = page.locator(panel_view("queue"))
    ringed = """() => getComputedStyle(document.querySelector('.lf-fp-on-user'))
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
    assert page.evaluate(ringed), "the control the user is located on says nothing"
    page.keyboard.press("Enter")
    expect(panel).to_be_visible()
    # Opened by a key, the user stands in the view, on its first row where it has one.
    page.wait_for_function(
        "view => document.querySelector(view)?.contains(document.activeElement)",
        arg=panel_view("queue"),
    )
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


def test_scroll_surfaces_added_after_upgrade_gain_keyboard_reach(browser, serve):
    page = open_page(browser, serve(leaf_page("Late scroll", "<h1>Late scroll</h1>")))
    page.evaluate(
        """() => {
          const authored = document.createElement('div');
          authored.id = 'late-authored';
          authored.className = 'scroll';
          authored.style.cssText = 'width:220px;overflow-x:auto;white-space:nowrap';
          authored.textContent = 'a'.repeat(500);
          const native = document.createElement('pre');
          native.id = 'late-native';
          native.style.width = '220px';
          native.textContent = 'b'.repeat(500);
          document.querySelector('main').append(authored, native);
        }"""
    )
    for selector in ("#late-authored", "#late-native"):
        surface = page.locator(selector)
        expect(surface).to_have_attribute("data-lf-more-after", "")
        measured = surface.evaluate(
            "el => ({scrolls: el.scrollWidth > el.clientWidth, tab: el.tabIndex})"
        )
        assert measured == {"scrolls": True, "tab": 0}, (selector, measured)


def test_a_hidden_control_does_not_take_a_scroll_boxes_keyboard_route(browser, serve):
    markup = leaf_page(
        "Hidden control in scroll box",
        '<h1>Review</h1><a id="before" href="#scroll">Read code</a>'
        '<div id="scroll" class="scroll" style="width:220px; overflow-x:auto; white-space:nowrap">'
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
          box.classList.add("scroll");
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


# Controls to Tab onto at a scroller's edge. Each wears its ring on a different box:
# the radio on itself, a playground choice on its face, a joined option group's pick on
# its row.
EDGE_CONTROLS = {
    "radio": '<p><label><input id="at" type="radio" name="r" checked> Pick</label></p>',
    "playground": (
        '<lf-playground id="pg"><lf-playground-control name="tone" label="Tone" kind="choice"'
        ' value="quiet"><lf-playground-choice value="quiet" label="Quiet">'
        '</lf-playground-choice><lf-playground-choice value="bold" label="Bold">'
        "</lf-playground-choice></lf-playground-control><lf-playground-preview>"
        "<p>Preview</p></lf-playground-preview><lf-playground-output>Use"
        ' <lf-playground-value for="tone"></lf-playground-value></lf-playground-output>'
        "</lf-playground>"
    ),
    "options": (
        '<lf-options id="op" choose><lf-option id="op-a">Alpha</lf-option>'
        '<lf-option id="op-b">Beta, the second choice</lf-option></lf-options>'
    ),
}
EDGE_TARGETS = {
    "radio": "#at",
    "playground": "#pg input:checked",
    "options": "#op-b .lf-pick",
    "table": "#wide td:nth-child(11) a",
}


def edges_page(control):
    entries = [f'<p><a href="#log-{i}">Entry {i}</a></p>' for i in range(60)]
    return leaf_page(
        "controls at scrollers' edges",
        '<h1 id="t">Edges</h1>\n<div id="log" data-bound="start">'
        + "".join(entries[:30])
        + EDGE_CONTROLS.get(control, "")
        + "".join(entries[30:])
        + '</div>\n<table id="wide"><tbody><tr>'
        + "".join(
            f'<td><a href="#cell-{i}">Cell&nbsp;link&nbsp;{i}</a></td>'
            for i in range(30)
        )
        + "</tr></tbody></table>",
    )


@pytest.mark.parametrize(
    ("control", "past", "key", "engine"),
    [
        *(
            pytest.param(
                control, past, key, engine, id=f"{control}-{name}-{key}-{engine}"
            )
            for control, past, name, key in [
                ("radio", 6, "past", "Tab"),
                ("radio", -2, "inside", "Tab"),
                ("options", 6, "past", "Tab"),
                ("options", 6, "past", "End"),
                ("table", 6, "past", "Tab"),
            ]
            for engine in ["browser", "firefox_browser"]
        ),
        # Firefox logs a warning of its own on any playground page.
        pytest.param(
            "playground", 6, "Tab", "browser", id="playground-past-Tab-browser"
        ),
    ],
)
def test_a_key_onto_a_control_at_a_scrollers_edge_shows_its_ring(
    request, serve, control, past, key, engine
):
    """The browser reveals a Tab's arrival only when it counts it out of view, Firefox
    when less than about a line of it shows and Chromium across only when none of it
    does, and neither it nor Leaf's landing knew a box that wears the control's ring.
    So a radio 6px past a bounded log's foot stayed cut in Firefox, and one 2px inside
    it kept its ring cut; a link 6px past a wide table's end stayed cut in both
    engines; and a joined option group's row and a playground choice's face, each
    wearing its control's ring, stayed cut in both, the face once its radio stood 7px
    inside, the row whether Tab or End reached it. `past` is how far beyond the edge
    the box wearing the ring stood before the key; each now shows its ring."""
    page = open_page(request.getfixturevalue(engine), serve(edges_page(control)))
    resized(page, 1280, 560)
    side = "right" if control == "table" else "bottom"
    target = page.locator(EDGE_TARGETS[control])
    # Which box wears the ring is the paint's answer: the nearest box out from the
    # control whose outline is the ring.
    target.evaluate("el => el.focus({preventScroll: true})")
    rendered(page)
    target.evaluate(
        """(el) => {
          const w = getComputedStyle(el).getPropertyValue('--focus-ring-w').trim();
          for (let n = el; n; n = n.parentElement) {
            const cs = getComputedStyle(n);
            if (cs.outlineStyle === 'solid' && cs.outlineWidth === w)
              return void (window.ringed = n);
          }
        }"""
    )
    if key == "Tab":
        page.keyboard.press("Shift+Tab")
    else:
        page.locator("#op-a .lf-pick").evaluate("el => el.focus({preventScroll: true})")
    page.evaluate(
        """([side, past]) => {
          const box = window.ringed.closest(side === 'bottom' ? '#log' : '#wide');
          const port = box.getBoundingClientRect();
          const at = window.ringed.getBoundingClientRect();
          if (side === 'bottom')
            box.scrollTop += at.bottom - (port.top + box.clientTop + box.clientHeight)
              - past;
          else
            box.scrollLeft += at.right - (port.left + box.clientLeft + box.clientWidth)
              - past;
        }""",
        [side, past],
    )
    scroll_settled(page)
    page.keyboard.press(key)
    expect(target).to_be_focused()
    rendered(page)
    read = page.evaluate(
        """(side) => {
          const el = window.ringed;
          const box = el.closest(side === 'bottom' ? '#log' : '#wide');
          const port = box.getBoundingClientRect();
          const at = el.getBoundingClientRect();
          const style = getComputedStyle(el);
          return {
            room: side === 'bottom'
              ? port.top + box.clientTop + box.clientHeight - at.bottom
              : port.left + box.clientLeft + box.clientWidth - at.right,
            ring: parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset),
          };
        }""",
        side,
    )
    assert read["room"] >= read["ring"], read


GROUPED_SIDE_LIST = leaf_page(
    "a grouped queue",
    '<header><h1>Queue</h1></header><lf-tabs id="queue" list="side">'
    + "".join(
        f'<lf-tab id="t-{n}" label="Ticket {n}" group="Group {n // 10}">'
        f"<p>Ticket {n}.</p></lf-tab>"
        for n in range(30)
    )
    + "</lf-tabs>",
    layout="workspace",
)

# Stands `el` `past` pixels beyond `edge` of the box `port` names around it.
PLACE_PAST_EDGE = """(el, [port, edge, past]) => {
  const box = el.closest(port);
  const top = box.getBoundingClientRect().top + box.clientTop;
  const at = el.getBoundingClientRect();
  box.scrollTop += edge === 'foot'
    ? at.bottom - (top + box.clientHeight) - past
    : at.top - top + past;
}"""

# How much shorter than the list's band the run from the group's label to the tab
# `el` would have to be to fit with 7px to spare: the shortfall of the tab's ring room
# at both ends.
RUN_SHORTFALL = """(el) => {
  const strip = el.closest('[role=tablist]');
  const run = document.createRange();
  run.setStartBefore(el.parentElement.querySelector(':scope > .lf-tab-group'));
  run.setEndAfter(el);
  const style = getComputedStyle(strip);
  const band = strip.clientHeight - (parseFloat(style.scrollPaddingTop) || 0)
    - (parseFloat(style.scrollPaddingBottom) || 0);
  return band - run.getBoundingClientRect().height - 7;
}"""

# How far `el` stands inside `edge` of that box, and how far its ring reaches past it.
ROOM_AT_EDGE = """(el, [port, edge]) => {
  const box = el.closest(port);
  const top = box.getBoundingClientRect().top + box.clientTop;
  const at = el.getBoundingClientRect();
  const style = getComputedStyle(el);
  return {
    room: edge === 'foot' ? top + box.clientHeight - at.bottom : at.top - top,
    ring: parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset),
  };
}"""


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
@pytest.mark.parametrize("walk", ["reference", "side list", "side list, long group"])
def test_a_walk_in_a_box_no_reading_region_moves_shows_the_ring(
    request, serve, walk, engine
):
    """A box no reading region moves revealed a walk's next item by its bare box: the
    command reference's results, a fixed dialog's list, and a side list's tabs, which a
    walk reveals bounded `within` the list. So Up onto a command past the results' head
    stood its button flush with the head, and Down onto a tab past the list's foot
    stood it flush with the foot, each ring cut there. The tab comes in with its
    group's label, as one range, where that fits; a group whose run fits the list but
    not with the tab's ring room comes in by the tab alone, since landing the run
    would leave the tab past the foot. Each now shows its ring."""
    page = open_page(
        request.getfixturevalue(engine),
        serve(LONG_PAGE if walk == "reference" else GROUPED_SIDE_LIST),
    )
    resized(page, 1280, 560)
    if walk == "reference":
        page.keyboard.press("?")
        items = page.locator(".lf-command-reference-command:visible")
        port, key, edge = ".lf-command-reference-results", "ArrowUp", "head"
        start, target = items.nth(9), items.nth(8)
    else:
        items = page.get_by_role("tab")
        port, key, edge = "[role=tablist]", "ArrowDown", "foot"
        last = 19 if walk == "side list, long group" else 15
        start, target = items.nth(last - 1), items.nth(last)
        if walk == "side list, long group":
            resized(page, 1280, 560 - round(target.evaluate(RUN_SHORTFALL)))
    start.evaluate("el => el.focus({preventScroll: true})")
    rendered(page)
    scroll_settled(page)
    target.evaluate(PLACE_PAST_EDGE, [port, edge, 6])
    scroll_settled(page)
    page.keyboard.press(key)
    expect(target).to_be_focused()
    rendered(page)
    read = target.evaluate(ROOM_AT_EDGE, [port, edge])
    assert read["room"] >= read["ring"], read
    if walk == "side list":
        # The run fits, so the group's label came in with the tab.
        assert target.evaluate(
            """(el) => el.parentElement.querySelector(':scope > .lf-tab-group')
              .getBoundingClientRect().top
              >= el.closest('[role=tablist]').getBoundingClientRect().top"""
        )


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
        assert page.evaluate("() => !document.activeElement.matches('#open, #shut')"), (
            f"{step}: the next Tab did not carry on from the block being read"
        )


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
                # The second press has to reach a page control clear of Comment's card.
                '<button id="later">Later control</button>'
                '<div style="height:180px"></div>'
                '<button id="origin">Original control</button>'
                '<div style="height:1000px"></div>',
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


def test_retained_moves_keep_native_editor_and_frame_state(browser, serve, subtests):
    """A reorder or a move to another parent keeps the user typing in the moved row,
    with no focus hold of the caller's, whether or not the browser has `moveBefore`;
    a native move also keeps the row's iframe document.

    Each case paints its own rows into its own pair of parents on one page. The cases
    without `moveBefore` delete it from the page, so they come last."""
    cases = [
        (native_move, renderer)
        for native_move in (True, False)
        for renderer in ("children", "lit")
    ]
    parents = "".join(
        f'<div id="rows-{index}"></div><div id="other-{index}"></div>'
        for index in range(len(cases))
    )
    page = open_page(
        browser,
        serve(leaf_page("Retained rows", f"<h1>Retained rows</h1>{parents}")),
    )
    for index, (native_move, renderer) in enumerate(cases):
        with subtests.test(native_move=native_move, renderer=renderer):
            page.evaluate(
                """async ([index, nativeMove, renderer]) => {
              const {render, repeat, setChildren: orderChildren, move} =
                await window.__lfWidgetApi();
              const rows = document.querySelector(`#rows-${index}`);
              if (!nativeMove) Element.prototype.moveBefore = undefined;
              const nodes = ['a', 'b', 'c'].map(id => {
                const row = document.createElement('div');
                row.dataset.row = id;
                row.innerHTML = `<input aria-label="${id}-${index}">
                  <iframe title="${id}-${index}" srcdoc="<p>Retained frame</p>"></iframe>`;
                return row;
              });
              const paint = nodes => renderer === 'lit'
                ? render(repeat(nodes, node => node.dataset.row, node => node), rows)
                : orderChildren(rows, nodes);
              paint(nodes);
              const editor = rows.querySelector('[data-row=c] input');
              editor.addEventListener('blur', () => window.blurs++);
              editor.addEventListener('keydown', event => {
                if (event.key === 'ArrowUp' && event.altKey) {
                  event.preventDefault();
                  paint([nodes[2], nodes[0], nodes[1]]);
                } else if (event.key === 'ArrowDown' && event.altKey) {
                  event.preventDefault();
                  const other = document.querySelector(`#other-${index}`);
                  if (renderer === 'lit') render(nodes[2], other);
                  else move(other, nodes[2], null);
                }
              });
            }""",
                [index, native_move, renderer],
            )
            editor = page.get_by_role("textbox", name=f"c-{index}", exact=True)
            editor.fill("unfinished words")
            editor.evaluate("node => node.setSelectionRange(3, 9, 'backward')")
            # Counted from here, once the last case's editor has given up the focus.
            page.evaluate("window.blurs = 0")
            frame = page.locator(f'iframe[title="c-{index}"]')
            expect(
                page.frame_locator(f'iframe[title="c-{index}"]').locator("p")
            ).to_have_text("Retained frame")
            frame.evaluate("node => window.heldDocument = node.contentDocument")
            for key, parent in [
                ("Alt+ArrowUp", f"#rows-{index}"),
                ("Alt+ArrowDown", f"#other-{index}"),
            ]:
                page.keyboard.press(key)
                expect(page.locator(f"{parent} > [data-row=c]")).to_have_count(1)
                if key == "Alt+ArrowUp":
                    expect(
                        page.locator(f"#rows-{index} > [data-row]").first
                    ).to_have_attribute("data-row", "c")
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


def test_an_empty_field_reads_the_same_before_and_after_its_editor_builds(
    browser, serve
):
    """An empty text field builds its editor only when the user arrives in it. The box
    drawn in its place was a textbox in Chromium's accessibility tree but not an
    editable one, and its value was empty where the editor's is a line break, so a
    screen reader could describe the field differently before the user arrived. Every
    named node the field gives the tree reads the same before Tab builds the editor and
    after, and the key typed on arrival lands in the field."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Empty field",
                "<h1>Empty field</h1><p id='hint'>Markdown works</p>"
                "<button id='before'>Before</button><div id='holder'></div>",
            )
        ),
    )
    page.evaluate("""() => {
      const field = document.createElement('leaf-text');
      field.setAttribute('aria-label', 'Reply');
      field.setAttribute('placeholder', 'Write a reply');
      field.setAttribute('aria-describedby', 'hint');
      document.querySelector('#holder').append(field);
    }""")
    cdp = page.context.new_cdp_session(page)

    def field_nodes():
        return sorted(
            (
                node["role"]["value"],
                node.get("description", {}).get("value") or "",
                node.get("value", {}).get("value") or "",
                sorted(
                    (prop["name"], prop["value"].get("value"))
                    for prop in node.get("properties", [])
                    if prop["name"] != "focused"
                ),
            )
            for node in cdp.send("Accessibility.getFullAXTree")["nodes"]
            if not node["ignored"] and node.get("name", {}).get("value") == "Reply"
        )

    before = field_nodes()
    field = page.locator("#holder leaf-text")
    page.locator("#before").focus()
    page.keyboard.press("Tab")
    page.keyboard.type("x")
    expect(field).to_be_focused()
    field.evaluate(
        "node => new Promise(resolve => node.value ? resolve() : "
        "node.addEventListener('input', resolve, {once: true}))"
    )
    assert field.evaluate("node => node.value") == "x"
    page.keyboard.press("Backspace")
    page.evaluate(RELEASE_FOCUS)
    assert field_nodes() == before
