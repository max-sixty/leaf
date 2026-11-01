"""Which keyboard scope answers a key, and how Escape unwinds the layers in front of the
user."""

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATIONS_PAGE, panel_comment
from render_cases_layout import (
    SHOT_SRC,
    SHOTS,
    current_location_ring,
    ring_faults,
    ring_rule,
    rings_drawn,
)
from render_cases_navigation import (
    ADDRESSED_PAGE,
    BINDING_BADGE_PAGE,
    CONTROL_LABEL_PAGE,
    DISCLOSED_PAGE,
    NOTED_PAGE,
    _publish,
    mark_point,
)
from render_cases_widgets import WHERE_I_STAND_PAGE
from render_harness import (
    BOARD_PAGE,
    INLINE_PAGE,
    LONG_PAGE,
    PANEL,
    PANEL_THREAD,
    available_commands,
    consume_browser_errors,
    draft_control,
    hold_selection,
    is_problem,
    leaf_page,
    open_page,
    open_threads,
    open_versions,
    panel_control,
    panel_field,
    panel_settled,
    panel_view,
    resized,
    round_trip,
    select_words,
    told,
    write,
)

from browser.navigation import offered_routes
from browser.threads import open_panel_thread
from browser.threads.test_rewrites import _rewrite_surface
from leaf import event_log as events_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def offered(page):
    """Every key the dispatcher would answer at the current location."""
    return {key for keys in available_commands(page).values() for key in keys}


def test_a_walked_thread_leaves_through_what_holds_it(browser, serve):
    """Escape removes the user's current layer of thread or disclosure.

    From the page, `t` opens the margin's thread view to reach the thread. However
    many threads the walk then visits, one Escape takes the view down and lets the
    user go beside the element the thread is about. It never hands back the heading
    the walk left, since Escape unwinds the hierarchy rather than the travel, nor the
    rail control the view hung from, which the pointer's close lands on because the
    pointer pressed it.

    A thread open in the panel leaves through the panel's own way out, which puts its
    view away.
    """
    url = serve(
        INLINE_PAGE, anchored=[("p", "bold text"), ("p2", "neighbouring block")]
    )
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    # An agent's comment asks by construction, so one thread waits on the user, which
    # is what gives the panel's `w` narrowing something to narrow to. It shares the second
    # passage, so the walk's first two landings stay the user's own threads in order.
    asked = panel_comment(
        serve.page_dir,
        "Is this the passage you meant?",
        {"section": "p2", "quote": "neighbouring block"},
        "agent",
    )
    page = open_page(browser, url)
    page.set_viewport_size({"width": 1200, "height": 844})
    preview = page.locator(".lf-margin-preview")
    # The view holds one thread at a time, so the walk's landings are told apart by id.
    threads = [
        page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
        for root in roots
    ]

    # From the page: the walk is lateral, and its way out is beside the thread's element.
    page.keyboard.press("t")
    expect(threads[0]).to_be_focused()
    page.keyboard.press("t")
    expect(threads[1]).to_be_focused()
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")
    assert not page.evaluate(
        "() => document.activeElement.closest('.lf-margin-projection')"
    )
    # Letting go leaves the user beside the thread rather than anywhere else, so the
    # walk takes them back into it, the one they left of the two on that passage.
    page.keyboard.press("t")
    expect(threads[1]).to_be_focused()
    page.keyboard.press("t")
    agents = preview.locator(f'.lf-page-thread[data-thread="{asked}"]')
    expect(agents).to_be_focused()
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()
    page.keyboard.press("t")
    expect(agents).to_be_focused()
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()

    # From a heading the user was located on, the same way out: the landing is beside
    # the element the thread is about rather than the heading the walk left.
    heading = page.locator("main h2").first
    heading.evaluate("el => { el.tabIndex = -1; el.focus(); }")
    expect(heading).to_be_focused()
    page.keyboard.press("t")
    expect(threads[0]).to_be_focused()
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()
    # Beside the element, the user is at the thread without being in it, so the walk
    # goes back into that thread, and on from it with the next press.
    page.keyboard.press("t")
    expect(threads[0]).to_be_focused()
    page.keyboard.press("t")
    expect(threads[1]).to_be_focused()
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")

    # In the panel, leave the editor, then the thread with the panel.
    view = open_panel_thread(page, roots[0])
    view.focus()
    page.keyboard.press("c")
    expect(panel_field(page)).to_be_focused()
    page.keyboard.press("Escape")
    expect(view).to_be_focused()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    # A pointer opening leaves through the same panel surface, from a message in it.
    view = open_panel_thread(page, roots[0])
    view.locator(".lf-msg").first.click()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate("() => document.activeElement === document.body")


def test_the_thread_walk_goes_on_from_the_place_the_panel_holds(browser, serve):
    """Stepping into the panel from a thread keeps the user in that thread on the page,
    so `t` pressed in On me goes on to the next thread rather than back into it."""
    url = serve(
        INLINE_PAGE, anchored=[("p", "bold text"), ("p2", "neighbouring block")]
    )
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    panel_comment(
        serve.page_dir,
        "Is this the passage you meant?",
        {"section": "p2", "quote": "neighbouring block"},
        "agent",
    )
    page = open_page(browser, url)
    threads = [
        page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
        for root in roots
    ]
    page.keyboard.press("t")
    expect(threads[0]).to_be_focused()
    panel_control(page, "queue").click()
    panel_settled(page, view="queue")
    page.keyboard.press("t")
    expect(threads[1]).to_be_focused()


def test_a_layer_is_left_the_same_way_however_it_was_reached(browser, serve):
    """Escape reads what stands in front of the user, not how they got there.

    The panel and the margin's thread view each have one way out, and a click, a
    keyboard activation of the same control and a walk that arrived from somewhere else
    all take it in one press. It ends on the page, beside the element a card's thread is
    about: the Threads mark, the margin marker and the page mark are Leaf's own
    controls rather than places the user was reading, so none of them is a landing, and
    a user who reached one by Tab or by pointer is owed no return to it.
    """
    url = serve(
        INLINE_PAGE, anchored=[("p", "bold text"), ("p2", "neighbouring block")]
    )
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    page = open_page(browser, url)
    page.set_viewport_size({"width": 1200, "height": 844})
    on_body = "() => document.activeElement === document.body"
    preview = page.locator(".lf-margin-preview")
    toggle = page.locator(".lf-fp-on-user")
    marker = page.locator('[data-lf-margin-for="p"] > .lf-margin-marker')
    threads = [
        page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{root}"]')
        for root in roots
    ]

    # On me by pointer: out with the panel's view.
    toggle.click()
    panel_settled(page, view="queue")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate(on_body)

    def out():
        """One press takes the card down and lets the user go beside its element."""
        page.keyboard.press("Escape")
        expect(preview).to_be_hidden()
        assert page.evaluate(on_body)

    # A margin marker by pointer, a walk on to the next thread, and out beside the
    # element that thread is about: the marker the card hangs from is not a landing.
    marker.click()
    expect(preview).to_be_visible()
    expect(threads[0]).to_be_focused()
    rendered(page)
    # The pointer route keeps keyboard standing without showing a keyboard ring.
    assert (
        preview.locator(".lf-margin-preview-card").evaluate(
            "node => getComputedStyle(node).outlineStyle"
        )
        == "none"
    )
    page.keyboard.press("t")
    expect(threads[1]).to_be_focused()
    out()

    # The mark on the page is the same door and the same way out.
    page.mouse.click(*mark_point(page, "lf-mark"))
    expect(preview).to_be_visible()
    expect(threads[0]).to_be_focused()
    out()

    # And from the keyboard, focused on the marker itself: the same way out, to the
    # same place. The marker is Leaf's own control beside the words it marks, so it is
    # where the user came from rather than where they are put back.
    marker.focus()
    page.keyboard.press("Enter")
    expect(preview).to_be_visible()
    expect(threads[0]).to_be_focused()
    out()

    toggle.focus()
    page.keyboard.press("Enter")
    panel_settled(page, view="queue")
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate(on_body)


def test_a_view_reached_from_another_view_leaves_both_of_them_shut(browser, serve):
    """The surface a user was already in does not come back when the next one goes.

    `g T` from On me puts Threads up in its place, and the one Escape that takes
    Threads off lands on the page rather than reopening the view the user came from.
    Nothing records that they were in it, and the descent Escape matches is the one that
    the state in front of them describes: Threads over the page.
    """
    html = ADDRESSED_PAGE.replace(
        "</main>",
        """
        <lf-ask id="second-ask">
          <h2>A second question</h2>
          <lf-options id="second-options" choose>
            <lf-option id="second-one">First answer</lf-option>
            <lf-option id="second-two">Second answer</lf-option>
          </lf-options>
        </lf-ask>
        </main>
        """,
    )
    url = serve(html)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "A thread",
        },
    )
    page = open_page(browser, url)
    resized(page, 1280, 800)

    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    row = page.locator(".lf-fp-on-item[data-key*='\"widget:second-options\"']")
    expect(row).to_be_visible()
    row.focus()
    expect(row).to_be_focused()

    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    threads = page.locator(panel_view("threads"))
    page.wait_for_function(
        "view => view.contains(document.activeElement)", arg=threads.element_handle()
    )
    page.keyboard.press("Escape")

    panel_settled(page, open=False)
    assert page.evaluate("() => document.activeElement === document.body")


def test_a_widget_that_renames_its_role_keeps_the_press_offer_gave_it(browser, serve):
    """A selectable tab's press is the strip's own row, declared beside the
    arrows and Home/End that walk it, and it is the only thing that consumes Space —
    which is otherwise the page's scroll.

    That row is what a page-wide control scope used to supply, and the scope was the wrong
    place for it: read off the role it stopped seeing tabs, so Enter did nothing and Space
    threw the user down the page from a control that looked like it had answered; read
    off the tabindex it claimed every focus target `offer` builds and led with a press over
    a thread that answers nothing. Declared where the strip is, the press
    cannot be lost to a rename or promised where nothing runs it, and the word on the line
    is the strip's own — it names the tab rather than the control.

    Asserted from the state where the press is the only way back: the tab strip is walked
    with arrows, so a focused tab is usually the selected one. Revealing the *other* panel
    leaves focus on a tab that is not selected, which is exactly when Enter has work to
    do."""
    page = open_page(browser, serve(CONTROL_LABEL_PAGE))
    tabs = page.locator("#projects .lf-tab-btn")
    expect(tabs).to_have_count(2)

    def reveal_other():
        # Reveal the other panel without moving focus: each press must select a
        # different tab, rather than merely reaffirm the already selected one.
        page.evaluate(
            """async () => {
              const {reveal} = await window.__lfCheckApi();
              const {retainUserIntent} = await window.__lfWidgetApi();
              reveal(document.querySelector('#tab-bath'), retainUserIntent());
            }"""
        )
        rendered(page)
        expect(tabs.first).to_be_focused()
        expect(tabs.nth(1)).to_have_attribute("aria-selected", "true")

    tabs.first.focus()
    reveal_other()

    # The line names the press, and the press re-selects the tab the user is located on.
    page.keyboard.press("Enter")
    expect(tabs.first).to_have_attribute("aria-selected", "true")

    # And Space is consumed rather than scrolling the page out from under the press.
    reveal_other()
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press(" ")
    expect(tabs.first).to_have_attribute("aria-selected", "true")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before, (
        "Space scrolled the page instead of working the control it was promised on"
    )


def test_the_arrows_say_which_way_the_section_under_the_user_goes(browser, serve):
    """⏎ and space toggle a disclosure; → opens it and ← closes it. A direction and not a
    second toggle, which is the whole of what they add: → over a section already open
    leaves it open, where a toggle would have shut it. Only the direction with somewhere
    to go is bound, so the dispatcher offers ← over an open section and → over a shut
    one and every key it offers is a key that works — and each press that must change nothing
    follows one that changed something, since a box nobody has touched passes that
    assertion however dead the scope is.

    Both spellings of a folded section, because a user located on one cannot see which
    it is: the platform's <details>, and a settled option group, which is a span the
    widget wrote `aria-expanded` onto. One scope answers for both, and the press goes
    through the element's own click either way, so the keyboard leaves the page in the
    state the pointer would have left it in.

    The word follows either spelling within the press, not within the poll. Neither
    reports itself — an aria-expanded write fires no event at all — so what the
    dispatcher offers for the key under the user's finger rests on the attribute watch
    rather than on the two-second poll behind it. Both readings of it are taken once:
    an assertion that retries cannot tell the watch from a poll that lands inside its
    budget, and the first version of this test went green with the watch broken.

    Shift+← is the last thing this holds to: a summary's words are the page's, and
    extending a selection through them must not shut the section they are in."""
    page = open_page(browser, serve(DISCLOSED_PAGE))

    dsc = page.locator("#dsc")
    head = page.locator("#dsc-head")
    # The user tabs to the section's summary.
    for _ in range(40):
        page.keyboard.press("Tab")
        if head.evaluate("head => head === document.activeElement"):
            break
    else:
        raise AssertionError("Tab never reached the section's summary")
    expect(dsc).not_to_have_attribute("open", "")
    assert "ArrowRight" in offered(page) and "ArrowLeft" not in offered(page)

    page.keyboard.press("ArrowRight")
    expect(dsc).to_have_attribute("open", "")
    # The press does not move the user off what they pressed it on, so the next one
    # lands on the same section.
    expect(head).to_be_focused()
    said = offered(page)
    assert "ArrowLeft" in said and "ArrowRight" not in said, said

    # A direction and not a toggle, which is the one thing ⏎ cannot say: this press
    # follows one that is proven live, so a scope answering nothing at all could not pass
    # it, and a toggle bound to the arrows would have shut the section here.
    page.keyboard.press("ArrowRight")
    expect(dsc).to_have_attribute("open", "")
    # Shift+← is a user extending a selection through the summary's own words. A named
    # key asks for its modifiers exactly, so it is not this row's binding.
    page.keyboard.press("Shift+ArrowLeft")
    expect(dsc).to_have_attribute("open", "")

    page.keyboard.press("ArrowLeft")
    expect(dsc).not_to_have_attribute("open", "")
    page.keyboard.press("ArrowLeft")
    expect(dsc).not_to_have_attribute("open", "")

    # And the platform's own pair still toggles, once each: the row owns its whole binding
    # set, so the runtime makes the press the browser was going to make.
    page.keyboard.press("Enter")
    expect(dsc).to_have_attribute("open", "")
    page.keyboard.press(" ")
    expect(dsc).not_to_have_attribute("open", "")

    # The other spelling, which keeps its state in ARIA's own attribute rather than in
    # `open`, and whose press is the widget's own handler rather than the platform's.
    row = page.locator("#settled .lf-settled")
    row.focus()
    expect(row).to_have_attribute("aria-expanded", "false")
    assert "ArrowRight" in offered(page)
    page.keyboard.press("ArrowRight")
    expect(row).to_have_attribute("aria-expanded", "true")
    expect(page.locator("#st-keep")).to_be_visible()
    # Nothing reports this one at all — an aria-expanded write fires no event anywhere —
    # so read once: the word is the attribute watch's answer by the time the press
    # returns, or it is the poll's two seconds later, and only an assertion that refuses
    # to retry can tell those apart.
    said = offered(page)
    assert "ArrowLeft" in said and "ArrowRight" not in said, said
    # The dispatcher is one of two surfaces naming this row's keys, and the other is read by
    # somebody who cannot see the first. A row whose bindings answer from its own state
    # has to repaint both when the state moves, and only the line had a watch: the
    # attribute kept whichever way the row was set when the scope was declared, so
    # it went on promising the arrow that no longer moves this section and withholding
    # the one that does.
    #
    # Read once for the reason the line is, and by the same clock: the heartbeat repaints
    # scopes too, so a retrying assertion goes green on the tick that lands inside its
    # budget and the fix it is meant to hold has nothing to fail against.
    assert row.get_attribute("aria-keyshortcuts") == "Enter Space ArrowLeft"
    page.keyboard.press("ArrowRight")
    expect(row).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("ArrowLeft")
    expect(row).to_have_attribute("aria-expanded", "false")
    expect(page.locator("#st-keep")).to_be_hidden()
    rendered(page)
    assert row.get_attribute("aria-keyshortcuts") == "Enter Space ArrowRight"
    # Enter and Space toggle it once each. The span presses as a button does, and the
    # disclosure's row runs the same press here, which must replace the span's own as
    # it replaces a native button's, rather than toggle it back.
    page.keyboard.press("Enter")
    expect(row).to_have_attribute("aria-expanded", "true")
    page.keyboard.press(" ")
    expect(row).to_have_attribute("aria-expanded", "false")

    # A disclosure in a message, where the disclosure scope does not reach: thread markup
    # is a second document beside the version, and the arrows are the page's. A diff,
    # because what is being asked is what a widget's own row names — a widget re-wording
    # this press reads its bindings from DISCLOSE, which answers for where the element
    # stands as well as which way it is set, so the row cannot offer a key that
    # nothing there runs. The platform's pair still works it, so what differs is the
    # offer rather than the capability.
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-diff",
            "author": "agent",
            "revision": 1,
            "text": "The patch, for the record.",
            "markup": '<lf-diff id="msg-diff"><pre>'
            "diff --git a/gateway/limits.py b/gateway/limits.py\n"
            "--- a/gateway/limits.py\n"
            "+++ b/gateway/limits.py\n"
            "@@ -38,2 +38,2 @@ class Limiter:\n"
            "     def bucket_key(self, request):\n"
            "-        return request.remote_addr\n"
            "+        return request.token.id\n"
            "</pre></lf-diff>",
        },
    )
    told(page)
    # Opened, because the current location is where focus is and a shut panel has nowhere to
    # stand: without this the summary took no focus, the user was still on the page's own
    # row, and the line went on describing that one — an assertion that would have passed
    # for the wrong reason had the two been in the same state.
    open_panel_thread(page, "c-diff")
    staged = page.locator("#msg-diff summary").first
    expect(staged).to_be_visible()
    staged.focus()
    expect(staged).to_be_focused()
    # Every live row rather than the two hints that fit: the panel's own rows win the line
    # where the user is located in it, and what is asked here is what the register
    # answers, not which two chips got the room.
    said = offered(page)
    assert "ArrowLeft" not in said and "ArrowRight" not in said, said
    # And the press, which is the half that would matter if no surface said anything: the
    # arrow is the page's here and moves nothing, where the platform's pair still folds it.
    opened_now = staged.evaluate("el => el.parentElement.open")
    page.keyboard.press("ArrowLeft")
    assert staged.evaluate("el => el.parentElement.open") is opened_now
    page.keyboard.press("Enter")
    assert staged.evaluate("el => el.parentElement.open") is not opened_now


def test_a_native_modal_escapes_inherited_inertness_for_its_commands(browser, serve):
    """Native modal entry admits its real controls even inside an inert author region.

    Explicit inertness on the control itself still excludes its command. Modal ancestry
    is a browser boundary, so an inert-ancestor heuristic cannot override it.
    """
    page = open_page(browser, serve(LONG_PAGE))
    page.evaluate("""async () => {
      const {commandsChanged} = await window.__lfWidgetApi();
      const region = document.createElement('section');
      region.inert = true;
      const dialog = document.createElement('dialog');
      dialog.id = 'escaped-native-modal';
      const button = document.createElement('button');
      button.id = 'escaped-modal-control';
      button.textContent = 'Run the modal command';
      button.lfCommands = { title: 'Inside the native modal', rows: [{id:'test.inert-modal', keys:['v'],
        title:'Run the modal command',
        run:() => { button.dataset.runs = String(Number(button.dataset.runs || 0) + 1); }}] };
      commandsChanged(button);
      dialog.append(button);
      region.append(dialog);
      document.querySelector('main').append(region);
      dialog.showModal();
      button.focus();
    }""")
    dialog = page.locator("#escaped-native-modal")
    control = page.locator("#escaped-modal-control")
    assert dialog.evaluate("dialog => dialog.matches(':modal')")
    expect(control).to_be_focused()
    page.keyboard.press("v")
    expect(control).to_have_attribute("data-runs", "1")
    control.evaluate("button => { button.inert = true; }")
    rendered(page)
    page.keyboard.press("v")
    assert control.get_attribute("data-runs") == "1"
    dialog.evaluate("dialog => dialog.close()")


def test_a_dialog_shown_as_a_popover_stands_as_a_popover(browser, serve):
    """A dialog opened with `showPopover` is a popover layer, and the page behind it stays live.

    Chromium reports it `:popover-open` and not `:modal`. Read as modal, it would make the
    dispatcher drop the page's key scopes behind it."""
    page = open_page(browser, serve(LONG_PAGE))
    kinds = page.evaluate("""() => {
      const layers = document[Symbol.for('leaf.nativeLayers')];
      const asPopover = document.createElement('dialog');
      asPopover.popover = 'manual';
      asPopover.textContent = 'A dialog shown as a popover';
      const asModal = document.createElement('dialog');
      asModal.textContent = 'A dialog shown modally';
      document.querySelector('main').append(asPopover, asModal);
      asPopover.showPopover();
      const popover = layers().map((layer) => layer.kind);
      asPopover.hidePopover();
      asModal.showModal();
      const modal = layers().map((layer) => layer.kind);
      asModal.close();
      return {popover, modal};
    }""")
    assert kinds == {"popover": ["popover"], "modal": ["modal"]}


def test_a_text_box_keeps_its_keys_from_the_widget_around_it(browser, serve):
    """A widget scope may contain a text box, but its bare keys still type there.

    The focused element's own rows remain nearer so a draft can keep its specific Escape
    and a wired composer can send with Mod+Enter. The text-entry scope then claims the
    characters and editing keys before an ancestor widget can see them."""
    url = serve(NOTED_PAGE)
    _publish(serve.page_dir, 2, NOTED_PAGE, "two")
    page = open_page(browser, url)
    page.evaluate(
        """async () => {
          const { commandsChanged } = await window.__lfWidgetApi();
          const host = document.createElement('section');
          host.id = 'key-owning-widget';
          const box = document.createElement('textarea');
          host.append(box);
          document.querySelector('main').append(host);
          host.lfCommands = { title: 'Around a text box', rows: [
            {id: 'test.widget',
             keys: ['a', 'Enter', 'Shift+ArrowLeft', 'Mod+z', 'Escape'],
             title: 'Work the widget', line: 'work widget',
             run: (binding) => host.dataset.fired = binding},
          ] };
          commandsChanged(host);
          box.focus();
        }"""
    )

    page.keyboard.press("a")
    page.keyboard.press("Enter")
    expect(page.locator("#key-owning-widget textarea")).to_have_value("a\n")
    assert page.locator("#key-owning-widget").get_attribute("data-fired") is None
    page.keyboard.press("Shift+ArrowLeft")
    page.keyboard.press("Control+z")
    assert page.locator("#key-owning-widget").get_attribute("data-fired") is None

    # The widget ancestor remains nearer for keys the text-entry shield does not
    # claim; only editing stays native.
    page.keyboard.press("Escape")
    expect(page.locator("#key-owning-widget")).to_have_attribute("data-fired", "Escape")


def test_radio_and_slider_keys_stay_with_the_control_inside_a_modal(browser, serve):
    """Control navigation cannot also fire a containing widget's command."""
    page = open_page(browser, serve(NOTED_PAGE))
    page.evaluate(
        """async () => {
          const { commandsChanged } = await window.__lfWidgetApi();
          const dialog = document.createElement('dialog');
          dialog.id = 'control-key-owner';
          dialog.innerHTML = '<label>First<input type="radio" name="choice" value="one" checked></label>' +
            '<label>Second<input type="radio" name="choice" value="two"></label>' +
            '<label>Amount<input type="range" min="0" max="100" value="50"></label>';
          document.querySelector('main').append(dialog);
          dialog.lfCommands = { title: 'Around native controls', rows: [{id: 'test.ancestor',
            keys: ['ArrowDown', 'Shift+ArrowRight', 'Home'],
            title: 'Work the widget', line: 'work widget',
            run: (binding) => dialog.dataset.fired = binding}] };
          commandsChanged(dialog);
          dialog.showModal();
        }"""
    )
    host = page.locator("#control-key-owner")
    first = host.get_by_role("radio", name="First")
    first.focus()
    page.keyboard.press("ArrowDown")
    expect(host.get_by_role("radio", name="Second")).to_be_checked()
    slider = host.get_by_role("slider", name="Amount")
    slider.focus()
    page.keyboard.press("Shift+ArrowRight")
    expect(slider).to_have_value("51")
    page.keyboard.press("Home")
    expect(slider).to_have_value("0")
    expect(host).not_to_have_attribute("data-fired")
    page.evaluate(
        """async () => {
          const { commandsChanged } = await window.__lfWidgetApi();
          const slider = document.querySelector('#control-key-owner input[type="range"]');
          slider.lfCommands = { title: 'Exact control', rows: [{id: 'test.control', keys: ['ArrowDown'],
            title: 'Work this control', line: 'work control',
            run: () => slider.value = 75}] };
          commandsChanged(slider);
        }"""
    )
    page.keyboard.press("ArrowDown")
    expect(slider).to_have_value("75")
    expect(host).not_to_have_attribute("data-fired")


@pytest.mark.parametrize("shadow", [False, True])
def test_shared_image_viewer_survives_its_source_popover_removal(
    browser, serve, shadow
):
    """A shared chrome dialog keeps its style and returns home when its seat leaves."""
    page = open_page(
        browser,
        serve(NOTED_PAGE, media={SHOT_SRC[key]: data for key, data in SHOTS.items()}),
    )
    # Native layer lifetime must not depend on the optional image renderer's cleanup.
    held = []
    page.route("**/vendor/photoswipe.esm.js", lambda route: held.append(route))
    page.evaluate(
        """async ({shadow, image}) => {
          const {shadowStage} = await window.__lfWidgetApi();
          const host = document.createElement('section');
          host.id = 'image-options-owner';
          const opener = document.createElement('button');
          opener.textContent = 'Image options';
          const popover = document.createElement('div');
          popover.id = 'image-options';
          popover.popover = 'auto';
          const original = document.createElement('a');
          original.className = 'lf-media-open';
          original.href = image;
          original.dataset.lfMediaUrl = image;
          original.textContent = 'Open original';
          const another = original.cloneNode(true);
          another.textContent = 'Open another image';
          popover.append(original);
          opener.popoverTargetElement = popover;
          document.querySelector('main').append(host, another);
          if (shadow) shadowStage(host, [opener, popover]);
          else host.append(opener, popover);
        }""",
        {"shadow": shadow, "image": SHOT_SRC["before"]},
    )
    page.get_by_role("button", name="Image options", exact=True).click()
    original = page.get_by_role("link", name="Open original", exact=True)
    original.click()
    viewer = page.get_by_role("dialog", name="Image preview", exact=True)
    expect(viewer).to_be_visible()
    expect(page.locator("#image-options")).to_be_visible()
    assert viewer.evaluate("node => getComputedStyle(node).display") == "grid"
    assert viewer.bounding_box()["width"] == page.viewport_size["width"]
    page.keyboard.press("Escape")
    expect(viewer).to_be_hidden()
    expect(original).to_be_focused()
    original.click()
    expect(viewer).to_be_visible()
    retained = viewer.element_handle()
    page.locator("#image-options-owner").evaluate("node => node.remove()")
    page.wait_for_function("node => node.isConnected && !node.open", arg=retained)
    page.get_by_role("link", name="Open another image", exact=True).click()
    expect(viewer).to_be_visible()
    assert viewer.evaluate("(node, previous) => node === previous", retained)
    page.keyboard.press("Escape")
    expect(page.get_by_role("link", name="Open another image")).to_be_focused()
    for route in held:
        route.continue_()
    page.unroute("**/vendor/photoswipe.esm.js")


def test_native_top_layers_bound_the_keyboard_stack(browser, serve):
    """Native layer ownership blocks ancestors and survives nesting and light dismiss."""
    url = serve(NOTED_PAGE)
    _publish(serve.page_dir, 2, NOTED_PAGE, "two")
    page = open_page(browser, url)
    page.evaluate(
        """async () => {
          const { showNativeLayer, commandsChanged } = await window.__lfWidgetApi();
          const { shadowStage } = await window.__lfWidgetApi();
          const host = document.createElement('section');
          host.id = 'around-native-layer';
          const dialog = document.createElement('dialog');
          dialog.id = 'nested-modal';
          const shadowHost = document.createElement('div');
          const trigger = document.createElement('button');
          trigger.textContent = 'Open nested popover';
          const popover = document.createElement('div');
          popover.id = 'shadow-popover';
          popover.popover = 'auto';
          popover.textContent = 'Nested popover';
          const shared = document.createElement('dialog');
          shared.id = 'shared-modal';
          shared.textContent = 'A shared inspection surface';
          document.body.append(shared);
          const inspect = document.createElement('button');
          inspect.textContent = 'Inspect from popover';
          inspect.onclick = () => showNativeLayer(shared, {source: inspect});
          popover.append(inspect);
          trigger.popoverTargetElement = popover;
          shadowStage(shadowHost, [trigger, popover]);
          dialog.append(shadowHost);
          host.append(dialog);
          document.querySelector('main').append(host);
          host.lfCommands = { title: 'Around a native layer', rows: [
            {id: 'test.outer-escape', keys: ['Escape'], title: 'Work the outer widget',
             line: 'work outer', run: () => { host.dataset.fired = 'Escape'; }},
          ] };
          commandsChanged(host);
          const opener = document.createElement('button');
          opener.id = 'open-native-layer';
          opener.textContent = 'Open the modal';
          opener.onclick = () => {
            dialog.showModal();
            trigger.focus();
            trigger.click();
          };
          host.prepend(opener);
        }"""
    )
    # The user opens the modal, whose first control opens the popover inside it.
    page.locator("#open-native-layer").click()
    modal = page.locator("#nested-modal")
    popover = page.locator("#shadow-popover")
    expect(modal).to_be_visible()
    expect(popover).to_be_visible()

    # A shared modal joins its source popover across the shadow boundary for one
    # opening, so closing it leaves the source controls and outer modal in hand.
    inspect = popover.get_by_role("button", name="Inspect from popover")
    inspect.click()
    shared = page.locator("#shared-modal")
    expect(shared).to_be_visible()
    expect(popover).to_be_visible()
    page.keyboard.press("Escape")
    expect(shared).to_be_hidden()
    expect(popover).to_be_visible()
    expect(modal).to_be_visible()
    expect(inspect).to_be_focused()
    page.wait_for_function(
        "node => node.parentElement === document.body", arg=shared.element_handle()
    )

    # The global reference applies the same native modal rule across a shadow boundary:
    # the contextual auto popover closes and is not reconstructed afterwards.
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    expect(popover).to_be_hidden()
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()
    expect(popover).to_be_hidden()

    # Reopened over the same modal, so the stack order below is read on the scene that
    # rule describes rather than on what the reference left behind.
    page.locator("#nested-modal").get_by_role(
        "button", name="Open nested popover"
    ).click()
    expect(popover).to_be_visible()

    # The popover is nonmodal, but the modal below it remains a hard floor. A page
    # command and the widget ancestor outside the dialog are both unreachable.
    page.keyboard.press("l")
    expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode", "")
    page.keyboard.press("Escape")
    expect(popover).to_be_hidden()
    expect(modal).to_be_visible()
    assert page.locator("#around-native-layer").get_attribute("data-fired") is None
    page.keyboard.press("Escape")
    expect(modal).to_be_hidden()
    assert page.locator("#around-native-layer").get_attribute("data-fired") is None

    # Native focusing steps may synchronously open a newer modal. Recording the first
    # opening before those steps preserves that order, while an idempotent call on the
    # older dialog does not move it back to the top. The modals close in a later task:
    # opened and closed in one, they would be a write that changes nothing.
    assert page.evaluate(
        """async () => {
          const { nativeLayers } = await window.__lfCheckApi();
          const first = document.createElement('dialog');
          const second = document.createElement('dialog');
          const focus = document.createElement('button');
          focus.autofocus = true;
          focus.textContent = 'Focus opens the second modal';
          first.append(focus);
          document.body.append(first, second);
          focus.addEventListener('focus', () => second.showModal(), {once: true});
          first.showModal();
          const nested = nativeLayers().at(-1)?.root === second;
          first.showModal();
          const idempotent = nativeLayers().at(-1)?.root === second;
          window.__lfOrderedModals = [second, first];
          return nested && idempotent;
        }"""
    )
    page.evaluate(
        "() => { for (const modal of window.__lfOrderedModals) modal.close(); }"
    )

    # Modal entry dismisses a light-DOM auto popover and pruning retires its stack entry.
    open_versions(page)
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_be_visible()
    expect(page.locator(".lf-fp-menu")).to_be_hidden()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fp-menu")).to_be_hidden()
    assert page.evaluate(
        """async () => {
          const { nativeLayers } = await window.__lfCheckApi();
          const menu = document.querySelector('.lf-fp-menu');
          return nativeLayers().every((layer) => layer.root !== menu);
        }"""
    )

    # A closed inner layer is retired rather than mistaken for one covered by the older
    # modal now visible beneath it, so the outer layer is the top of the stack again. The
    # inner one closes in a later task than it opened in, as a user closes it.
    page.evaluate(
        """() => {
          const outer = document.createElement('dialog');
          const inner = document.createElement('dialog');
          document.body.append(outer, inner);
          outer.showModal();
          inner.showModal();
          window.__lfNestedModals = {outer, inner};
        }"""
    )
    assert page.evaluate(
        """async () => {
          const { nativeLayers } = await window.__lfCheckApi();
          const {outer, inner} = window.__lfNestedModals;
          inner.close();
          const restored = nativeLayers().at(-1)?.root === outer;
          outer.close();
          outer.remove();
          inner.remove();
          return restored;
        }"""
    )

    # A popover closed and reopened in one task, with no read in between, starts a fresh
    # entry rather than keeping its place. The popover sits in a shadow root nobody
    # staged, so only the patched method declares it.
    assert page.evaluate(
        """async () => {
          const { nativeLayers } = await window.__lfCheckApi();
          const host = document.createElement('div');
          const popover = document.createElement('div');
          popover.popover = 'auto';
          popover.textContent = 'Reopened popover';
          host.attachShadow({mode: 'open'}).append(popover);
          document.body.append(host);
          popover.showPopover();
          const declared = nativeLayers().at(-1)?.root === popover;
          popover.hidePopover();
          const retired = nativeLayers().every((layer) => layer.root !== popover);
          popover.showPopover();
          const fresh = nativeLayers().at(-1)?.root === popover;
          popover.hidePopover();
          host.remove();
          return declared && retired && fresh;
        }"""
    )


def test_a_scope_cannot_give_one_live_key_two_meanings(browser, serve):
    """An ambiguous row set is refused at the scope's first paint, gated or not.

    A declaration's shape is still refused where it is written, but what its rows mean
    is read only once every module has evaluated, so the ambiguity surfaces at that
    paint and takes the scope down with it. Reusing a key in mutually exclusive states
    remains valid; a card grip relies on that to make Enter and Space mean grab before
    the move and drop during it."""
    page = open_page(browser, serve(NOTED_PAGE))
    answers = page.evaluate(
        """async () => {
          const { commandsChanged } = await window.__lfWidgetApi();
          const {commandDeclarationsWithin, renderingState} = await window.__lfCheckApi();
          const registeredOn = element => commandDeclarationsWithin(element)
            .some(({source}) => source === element);
          const settled = () => new Promise((resolve, reject) => {
            const timeout = setTimeout(
              () => reject(new Error('Shortcut rendering did not settle within 30 seconds')),
              30000);
            const check = () => {
              if (Object.values(renderingState()).every(Boolean)) {
                clearTimeout(timeout);
                resolve();
              } else requestAnimationFrame(check);
            };
            requestAnimationFrame(check);
          });
          // Read after all repaint work has settled; the second paint finds the
          // refused scope gone rather than refusing it again.
          const painted = async (button) => {
            commandsChanged(document.body);
            await settled();
            return button.getAttribute('aria-keyshortcuts');
          };
          const firstPaint = async (id, rows, when) => {
            const button = document.createElement('button');
            button.id = id;
            document.querySelector('main').append(button);
            let declaration = 'declared';
            try {
              button.lfCommands = { title: id, rows: rows, when: when };
              commandsChanged(button);
            } catch (error) {
              declaration = error.message;
            }
            const declared = button.getAttribute('aria-keyshortcuts');
            const first = await painted(button);
            const registered = registeredOn(button);
            const second = await painted(button);
            button.remove();
            return {declaration, declared, first, registered, second};
          };
          const atTheFrame = async (id, rows) => {
            const button = document.createElement('button');
            button.id = id;
            document.querySelector('main').append(button);
            button.lfCommands = { title: id, rows: rows };
            commandsChanged(button);
            const declared = button.getAttribute('aria-keyshortcuts');
            await settled();
            const framed = button.getAttribute('aria-keyshortcuts');
            button.remove();
            return {declared, framed};
          };
          // Declared twice before any paint: the first declaration ambiguous, the second
          // sound. Only the frame reads the superseded one, so this is the case a repaint
          // call cannot reach.
          const redeclaredAtTheFrame = async (id, first, second) => {
            const button = document.createElement('button');
            button.id = id;
            document.querySelector('main').append(button);
            button.lfCommands = { title: id, rows: first };
            commandsChanged(button);
            button.lfCommands = { title: id, rows: second };
            commandsChanged(button);
            await settled();
            const framed = button.getAttribute('aria-keyshortcuts');
            const registered = registeredOn(button);
            button.remove();
            return {framed, registered};
          };
          return {
            ambiguous: await firstPaint('ambiguous', [
              {id: 'test.first', keys: ['F2'], title: 'First meaning', line: 'first', run: () => {}},
              {id: 'test.second', keys: ['F2'], title: 'Second meaning', line: 'second', run: () => {}},
            ]),
            ambiguousContext: await firstPaint('ambiguous-context', [
              {id: 'test.context-first', contextKeys: ['1'], title: 'First contextual meaning', run: () => {}},
              {id: 'test.context-second', contextKeys: ['1'], title: 'Second contextual meaning', run: () => {}},
            ]),
            gatedAmbiguous: await firstPaint('gated-ambiguous', [
              {id: 'test.gated-first', keys: ['F4'], title: 'First gated meaning', line: 'first', run: () => {}},
              {id: 'test.gated-second', keys: ['F4'], title: 'Second gated meaning', line: 'second', run: () => {}},
            ], () => true),
            exclusive: await firstPaint('exclusive', [
              {id: 'test.first-state', keys: ['F2'], title: 'First state', line: 'first',
               when: () => true, run: () => {}},
              {id: 'test.second-state', keys: ['F2'], title: 'Second state', line: 'second',
               when: () => false, run: () => {}},
            ]),
            atFrame: await atTheFrame('frame-painted', [
              {id: 'test.frame-painted', keys: ['F7'], title: 'Painted at the frame',
               line: 'frame', run: () => {}},
            ]),
            redeclared: await redeclaredAtTheFrame('redeclared', [
              {id: 'test.stale-first', keys: ['F9'], title: 'First stale meaning',
               line: 'first', run: () => {}},
              {id: 'test.stale-second', keys: ['F9'], title: 'Second stale meaning',
               line: 'second', run: () => {}},
            ], [
              {id: 'test.replacing', keys: ['F9'], title: 'The declaration that stands',
               line: 'stands', run: () => {}},
            ]),
          };
        }"""
    )
    for name in ("ambiguous", "gatedAmbiguous", "ambiguousContext"):
        assert answers[name] == {
            "declaration": "declared",
            "declared": None,
            "first": None,
            "registered": False,
            "second": None,
        }, answers
    refusals = consume_browser_errors(page, "two live meanings for")
    for binding in ("F2", "F4", "1"):
        assert any(
            is_problem(error, f"meanings for {binding}") for error in refusals
        ), refusals
    assert answers["exclusive"] == {
        "declaration": "declared",
        "declared": None,
        "first": "F2",
        "registered": True,
        "second": "F2",
    }, answers
    # Nobody repaints the register for this one. The repaint frame the declaration itself
    # asks for is the first paint, so the projection lands there without a state change.
    assert answers["atFrame"] == {"declared": None, "framed": "F7"}, answers
    # The superseded declaration is owed no reading: read at the frame, its refusal
    # would have retracted the one that replaced it.
    assert answers["redeclared"] == {"framed": "F9", "registered": True}, answers

    # Help merges instances with the same title for presentation. Repeated keys there
    # belong to separate focus locations, so they are not a conflict in either scope.
    page.evaluate(
        """async () => {
          const { commandsChanged } = await window.__lfWidgetApi();
          let first;
          for (const label of ['First', 'Second']) {
            const button = document.createElement('button');
            button.textContent = label;
            document.querySelector('main').append(button);
            if (!first) first = button;
            button.lfCommands = { title: 'Repeated controls', rows: [
              {id: 'test.repeated', keys: ['F3'], title: () => `Work ${label}`,
               line: 'work', run: () => button.dataset.fired = '1'},
              ...(label === 'Second' ? [{
                id: 'test.second-only', keys: ['F6'], title: 'Work only the second',
                line: 'second only', reach: 'on the second control',
                run: () => button.dataset.secondFired = '1',
              }] : []),
            ] };
            commandsChanged(button);
          }
          first.focus();
        }"""
    )
    page.keyboard.press("?")
    expect(page.get_by_role("dialog", name="Command reference")).to_be_visible()
    search = page.get_by_role("combobox", name="Search commands")
    search.fill("work only the second")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-command-reference-meta")).to_have_text(
        "Available on the second control"
    )
    search.fill("work first")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.get_by_role("button", name="First", exact=True)).to_have_attribute(
        "data-fired", "1"
    )
    expect(page.get_by_role("button", name="Second", exact=True)).not_to_have_attribute(
        "data-fired", "1"
    )


def test_a_partially_shadowed_row_keeps_each_other_live_binding(browser, serve):
    """Shadowing is per binding, so one local `d` must not hide the page row's live `u`.

    Multi-key rows keep related commands compact, but presentation cannot treat that visual
    grouping as dispatch ownership. The effective row retains the unshadowed route, its own
    direction word, and the same command identity the reference exposes."""
    html = NOTED_PAGE.replace("</main>", '<div style="height: 2400px"></div></main>')
    page = open_page(browser, serve(html))
    page.evaluate(
        """async () => {
          const { commandsChanged } = await window.__lfWidgetApi();
          const target = document.createElement('button');
          target.id = 'local-down';
          target.textContent = 'Local down';
          document.querySelector('main').prepend(target);
          target.lfCommands = { title: 'On local down', rows: [{
            id: 'test.local-down', keys: ['d'], title: 'Local down', line: 'local down',
            run: () => { target.dataset.pressed = '1'; },
          }] };
          commandsChanged(target);
          target.focus();
        }"""
    )

    routes = offered_routes(page)
    assert routes["page.up"] == ["u"], routes
    assert "page.down" not in routes, routes

    before = page.evaluate("() => { scrollTo(0, 1000); return scrollY; }")
    assert before > 0
    page.keyboard.press("u")
    page.wait_for_function("before => scrollY < before", arg=before)
    assert page.locator("#local-down").get_attribute("data-pressed") is None


def test_a_focused_scope_owns_its_declared_key_while_the_command_is_unavailable(
    browser, serve
):
    """A dead inner declaration suppresses an outer command; undeclared keys fall out."""
    page = open_page(browser, serve(NOTED_PAGE))
    page.evaluate(
        """async () => {
          const { commandsChanged } = await window.__lfWidgetApi();
          const outer = document.createElement('div');
          outer.id = 'outer-scope';
          const inner = document.createElement('button');
          inner.textContent = 'Inner scope';
          outer.append(inner);
          document.querySelector('main').prepend(outer);
          outer.lfCommands = { title: 'Outer scope', rows: [
            { id: 'test.outer-f2', keys: ['F2'], title: 'Run outer F2',
              line: 'outer F2', run: () => { outer.dataset.f2 = '1'; } },
            { id: 'test.outer-f3', keys: ['F3'], title: 'Run outer F3',
              line: 'outer F3', run: () => { outer.dataset.f3 = '1'; } },
          ] };
          commandsChanged(outer);
          inner.lfCommands = { title: 'Inner scope', rows: [
            { id: 'test.inner-f2', keys: ['F2'], title: 'Run inner F2',
              line: 'inner F2', when: () => false,
              run: () => { inner.dataset.f2 = '1'; } },
          ] };
          commandsChanged(inner);
          inner.focus();
        }"""
    )

    prevented = page.get_by_role("button", name="Inner scope").evaluate(
        """inner => {
          const event = new KeyboardEvent(
            'keydown', {key: 'F2', bubbles: true, cancelable: true}
          );
          inner.dispatchEvent(event);
          return event.defaultPrevented;
        }"""
    )
    assert prevented is False
    assert page.locator("#outer-scope").get_attribute("data-f2") is None
    assert (
        page.get_by_role("button", name="Inner scope").get_attribute("data-f2") is None
    )
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference.get_by_role("button", name="Run outer F2")).to_have_attribute(
        "data-lf-available", "false"
    )
    expect(reference.get_by_role("button", name="Run outer F3")).to_have_attribute(
        "data-lf-available", "true"
    )
    page.keyboard.press("Escape")

    page.keyboard.press("F3")
    expect(page.locator("#outer-scope")).to_have_attribute("data-f3", "1")


def test_an_unavailable_inner_escape_keeps_the_next_unwind_reachable(browser, serve):
    """A dead local Escape cannot strand a live unwind in an outer scope."""
    page = open_page(browser, serve(NOTED_PAGE))
    page.evaluate(
        """async () => {
          const { commandsChanged } = await window.__lfWidgetApi();
          const outer = document.createElement('div');
          outer.id = 'outer-escape-scope';
          const inner = document.createElement('button');
          inner.textContent = 'Inner escape scope';
          outer.append(inner);
          document.querySelector('main').prepend(outer);
          outer.lfCommands = { title: 'Outer scope', rows: [
            { id: 'test.outer-escape', keys: ['Escape'], title: 'Leave outer scope',
              line: 'leave outer scope', run: () => { outer.dataset.escaped = '1'; } },
          ] };
          commandsChanged(outer);
          inner.lfCommands = { title: 'Inner scope', rows: [
            { id: 'test.inner-escape', keys: ['Escape'], title: 'Leave inner scope',
              line: 'leave inner scope', when: () => false,
              run: () => { inner.dataset.escaped = '1'; } },
          ] };
          commandsChanged(inner);
          inner.focus();
        }"""
    )

    page.keyboard.press("Escape")
    expect(page.locator("#outer-escape-scope")).to_have_attribute("data-escaped", "1")
    expect(page.get_by_role("button", name="Inner escape scope")).not_to_have_attribute(
        "data-escaped", "1"
    )


def test_native_controls_need_no_generic_space_binding(browser, serve):
    """The reference has no synthetic generic-control command. Specialized controls
    such as a board grip still declare the Space meaning that belongs to their widget."""
    page = open_page(browser, serve(BOARD_PAGE))
    page.keyboard.press("?")
    help_el = page.locator(".lf-command-reference")
    expect(help_el).not_to_contain_text("On a control")
    expect(help_el.get_by_role("row").filter(has_text="Grab the card")).to_contain_text(
        "space"
    )
    page.keyboard.press("Escape")

    # And the key does what the reference says it does.
    grip = page.locator("lf-board .lf-grip").first
    grip.focus()
    page.keyboard.press(" ")
    expect(page.locator(".lf-lift")).to_have_count(1)
    page.keyboard.press("Escape")
    expect(page.locator(".lf-lift")).to_have_count(0)


def test_holding_a_key_repeats_only_where_the_press_is_a_walk(
    browser, serve, live_leaf
):
    """A held key repeats keydown where a real button fires once. A walk wants that — t
    down threads, q down obligations, arrows down a panel view — and a press that toggles or
    navigates does not: a held `]` was a page navigation per repeat, and a held pick a
    `choose` per repeat, each of them one decision the user made once. So a row says
    whether it repeats and the default is no, where before only `offer`'s own listener
    had thought about it and the global table had not.

    No gesture Playwright makes carries the repeat flag, so the press is dispatched with
    it set. That is the event a held key sends and the handler under test is the one the
    page installed; the tap below it, dispatched the same way and answered, is what says
    so rather than leaving the held press to pass for want of reaching anything."""
    live_leaf("second", "A second leaf")
    page = open_page(browser, serve(OBLIGATIONS_PAGE, comments=3))
    press = """([key, repeat, shiftKey = false]) => document.dispatchEvent(
        new KeyboardEvent('keydown',
          {key, repeat, shiftKey, bubbles: true, cancelable: true}))"""

    page.keyboard.press("t")
    walked = page.locator(PANEL_THREAD)
    expect(walked).to_be_focused()
    first = walked.get_attribute("data-thread")
    page.evaluate(press, ["t", True])  # a walk repeats
    expect(walked).not_to_have_attribute("data-thread", first)
    expect(walked).to_be_focused()

    page.keyboard.press("m")
    expect(page.locator("#live-question-decision[data-lf-obligation]")).to_have_count(1)
    page.evaluate(press, ["m", True])  # the same grammar repeats for obligations
    expect(page.locator("#sug-refill[data-lf-obligation]")).to_have_count(1)

    leaves = page.locator(panel_view("leaves"))
    page.keyboard.press("g")
    page.evaluate(press, ["l", True, True])  # a panel destination does not repeat
    expect(leaves).to_be_hidden()
    page.evaluate(press, ["l", False, True])  # the same event, answered
    expect(leaves).to_be_visible()


def test_a_select_keeps_its_native_typeahead_letters(browser, serve):
    html = NOTED_PAGE.replace(
        "</main>",
        '<select id="pick"><option>dog</option><option>cat</option></select></main>',
    )
    page = open_page(browser, serve(html))

    pick = page.locator("#pick")
    pick.focus()
    page.keyboard.press("c")

    expect(pick).to_have_value("cat")
    expect(page.locator(".lf-composer")).to_be_hidden()


def test_escape_backs_out_from_a_control_nothing_is_typed_into(browser, serve):
    """A scope takes the keys it uses, so a control that has no Escape of its own
    leaves the rung standing behind it. The old banner's version picker swallowed it,
    so the panel could not be closed by key right after the user worked it; the
    fix's first attempt was a two-item denylist, which an authored slider walked
    straight past. The picker is a button now, so what holds the rule is the
    page's own controls — which is where it always mattered, a page being free to
    author any of them.

    A slider and a select answer here for the two sides of the claim. The slider
    types nothing, so the typing scope never stands over it at all; the select's
    letters jump its options, so it stands and takes them — and takes only them,
    which is what leaves this press to the page. Reaching the rung used to be a
    branch inside the typing scope's own row, restating another scope's word.

    Which rung the press reaches is the ladder's own business, and it unwinds from
    where the user is: located out on the page, the first thing they are in is
    the control they are located on, and the panel behind them is a layer they are
    not in. So the press takes two — and the panel closing on the second is the
    whole of what this test is about, the control having had every chance to
    swallow the first."""
    html = NOTED_PAGE.replace(
        "</main>",
        '<input id="zoom" type="range">'
        '<select id="pick"><option>one</option><option>two</option></select></main>',
    )
    page = open_page(browser, serve(html))
    # The mouse opens between rounds because c is the select's own letter, and the
    # press has to be made the same way on both to be comparing anything.
    for control in ("#zoom", "#pick"):
        open_threads(page)
        page.locator(control).focus()
        page.keyboard.press("Escape")
        assert page.evaluate("() => document.activeElement === document.body")
        page.keyboard.press("Escape")
        panel_settled(page, open=False)


# The browser's own back: a close watcher standing before any of the page's, which
# hears a close request only where the page holds none of its own.
BROWSER_BACK = """() => {
  window.browserBack = 0;
  new CloseWatcher().onclose = () => (window.browserBack += 1);
}"""


def back_gesture(page):
    """Make the close request Android's back gesture makes. An Escape keydown nothing
    cancels is the same request, so the page's listeners are kept from hearing it. The
    page makes its watcher in the repaint frame after what it closes opens, which a
    finger can't beat but a driver can, so the gesture waits out two frames first."""
    page.evaluate(
        """() => new Promise((resolve) => requestAnimationFrame(() =>
          requestAnimationFrame(() => {
            addEventListener('keydown', (event) => {
              if (event.key === 'Escape') event.stopImmediatePropagation();
            }, {capture: true, once: true});
            resolve();
          })))"""
    )
    page.keyboard.press("Escape")


def test_a_back_gesture_takes_the_step_escape_would(browser, serve):
    """Android's back gesture is a close request, so a finger that opened the page's
    menu or a view leaves it the way Escape does, one step a gesture. With nothing left
    to take, the page holds no watcher and the gesture is the browser's, which goes
    back in history. Before, the gesture closed nothing Leaf opened."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    page = open_page(browser, serve(INLINE_PAGE), context=context)
    page.evaluate(BROWSER_BACK)
    menu = page.locator(".lf-floating-panel[data-menu]")

    page.locator(".lf-fp-leaf").tap()
    expect(menu).to_be_attached()
    back_gesture(page)
    expect(menu).not_to_be_attached()

    open_threads(page)
    back_gesture(page)
    panel_settled(page, open=False)
    assert page.evaluate("window.browserBack") == 0

    back_gesture(page)
    page.wait_for_function("window.browserBack === 1")


def test_escape_takes_one_step_where_a_back_gesture_would_take_it(browser, serve):
    """The page's watcher stands while Escape has a step to take, and a press the
    dispatcher answers is spent before it reaches the watcher, so the key still takes
    one step: the view goes, the selection beside it stays for the next."""
    page = open_page(browser, serve(INLINE_PAGE))
    page.evaluate(BROWSER_BACK)
    select_words(page, "#p")
    open_threads(page)

    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    assert page.evaluate("getSelection().toString()")

    back_gesture(page)
    page.wait_for_function("!getSelection().toString() || window.browserBack")
    assert page.evaluate("window.browserBack") == 0
    back_gesture(page)
    page.wait_for_function("window.browserBack === 1")


def test_a_back_gesture_takes_a_step_inside_a_modal_before_the_modal(browser, serve):
    """A modal dialog opened over a view holds a newer watcher than the page's, so back
    closed the dialog where Escape took the step a command inside it declares. The
    page's watcher is made again above the dialog: back takes the inner step, the next
    closes the dialog as the browser does, and the one after that the view."""
    page = open_page(browser, serve(INLINE_PAGE))
    page.evaluate(BROWSER_BACK)
    open_threads(page)
    page.evaluate(
        """async () => {
          const { commandsChanged } = await window.__lfWidgetApi();
          const dialog = document.createElement('dialog');
          dialog.id = 'inner-step';
          const button = document.createElement('button');
          button.textContent = 'Inside';
          dialog.append(button);
          document.querySelector('main').append(dialog);
          button.lfCommands = { title: 'Inside the dialog', rows: [{id: 'test.inner', keys: ['Escape'],
            title: 'Take the inner step', when: () => !button.dataset.fired,
            run: () => (button.dataset.fired = 'Escape')}] };
          commandsChanged(button);
          dialog.showModal();
          button.focus();
        }"""
    )
    dialog = page.locator("#inner-step")

    back_gesture(page)
    expect(dialog.get_by_role("button", name="Inside")).to_have_attribute(
        "data-fired", "Escape"
    )
    expect(dialog).to_have_attribute("open", "")

    back_gesture(page)
    expect(dialog).not_to_have_attribute("open", "")
    panel_settled(page, view="threads")

    back_gesture(page)
    panel_settled(page, open=False)
    assert page.evaluate("window.browserBack") == 0


@pytest.mark.parametrize("owner", ["draft", "rewrite"])
def test_a_back_gesture_never_throws_away_unsent_words(browser, serve, owner):
    """Escape's step in an open draft editor or message rewrite is Discard, which
    nothing undoes, so back taking it lost an edit to one stray edge swipe. Back closes
    the editor as Escape does, and a changed one loses nothing: a draft saves its words,
    as a press away does, and a rewrite keeps them, a notice saying so, the message
    showing it holds them, and opening it again finding them. Back must still get the
    user out, rather than holding them in the editor."""
    # The browser's back stands before the page's watchers, as the open thread view
    # holds one before the rewrite opens.
    browser_back = f"({BROWSER_BACK})()"
    if owner == "draft":
        page = open_page(
            browser,
            serve(
                leaf_page(
                    "Back in a draft",
                    '<h1>Back in a draft</h1><lf-draft id="d"><pre>Saved words.'
                    "</pre></lf-draft>",
                )
            ),
            init_script=browser_back,
        )
        editor = page.locator("#d leaf-text")

        def open_editor():
            draft_control(page, "edit", "d").click()
    else:
        page, _, message = _rewrite_surface(
            browser, serve, "panel", init_script=browser_back
        )
        editor = message.locator(".lf-msg-editor leaf-text")
        kept = message.locator(".lf-msg-kept")

        def open_editor():
            message.locator(".lf-msg-text").dblclick()

    open_editor()
    expect(editor).to_be_focused()
    back_gesture(page)
    expect(editor).to_have_count(0)
    if owner == "rewrite":
        expect(kept).not_to_be_visible()

    open_editor()
    write(editor, "Unsent words.")
    page.evaluate(
        """() => document.addEventListener('lf-command-invoked',
          ({detail}) => (window.ranTitle = detail.title), {once: true})"""
    )
    back_gesture(page)
    expect(editor).to_have_count(0)
    # The interaction log names the step that ran, not Discard's.
    assert page.evaluate("window.ranTitle") == "keep"
    assert page.evaluate("window.browserBack") == 0

    if owner == "draft":
        round_trip(page)
        expect(page.locator("#d .lf-draft-body")).to_have_text(
            "Unsent words.", use_inner_text=True
        )
        edits = [
            event
            for event in events_model.read_events(serve.page_dir)
            if event.get("action") == "edit"
        ]
        assert [event["detail"]["value"] for event in edits] == ["Unsent words."]
        return

    expect(page.locator(".lf-live")).to_have_text("Edit kept")
    expect(kept).to_have_text("unsaved edit")
    # Beside the sign, on the control that reopens the words, not in a text box whose
    # caret would raise a phone's keyboard.
    expect(message.locator(".lf-msg-edit")).to_be_focused()

    open_editor()
    expect(editor).to_have_js_property("value", "Unsent words.")
    expect(kept).not_to_be_visible()
    page.keyboard.press("Escape")
    expect(editor).to_have_count(0)
    expect(kept).not_to_be_visible()


def test_a_margin_marker_backs_out_onto_the_page_like_the_toggle(browser, serve):
    """A margin marker is placed in the document beside the words it marks, outside
    `.lf-chrome`, and the current-location floor used to read that container to tell a
    destination from a control. So a marker reached by Tab wore the let-go of an obligation
    or a heading — "let go" — where the Threads toggle beside it, which is a control
    of the same current location, backs out onto the page. The floor asks `inUi` now, the one
    reading of which layer a node is in, and a marker gets the same word as the toggle.
    A folded cluster is the case: an unfolded one has the Page Map's own rung over it,
    which answered before either word."""
    url = serve(INLINE_PAGE, anchored=[("p", "bold text")])
    page = open_page(browser, url)
    page.set_viewport_size({"width": 1200, "height": 844})
    marker = page.locator('[data-lf-margin-for="p"] > .lf-margin-marker')
    expect(marker).to_be_visible()

    for control in (page.locator(".lf-fp-on-user"), marker):
        control.focus()
        expect(control).to_be_focused()
        page.keyboard.press("Escape")
        assert page.evaluate("() => document.activeElement === document.body")


def test_an_obligations_pick_stays_a_place_to_stand_after_the_answer(browser, serve):
    """A pick inside an obligation wears the chrome face, as a margin marker does, and is not
    a control of Leaf's for all that: it is inside a destination, so Escape lets go of
    it onto the page. The obligation is the obligations view's own reading rather than the ring's
    paint, which only the obligation the walk stands at wears, so the word does not change
    under an unmoved focus when Space answers the obligation and the ring comes off."""
    page = open_page(browser, serve(BINDING_BADGE_PAGE))
    pick = page.locator("#cards .lf-pick").first
    pick.focus()
    expect(pick).to_be_focused()

    page.keyboard.press("Space")
    expect(page.locator("#c-heater .lf-pick")).to_have_attribute("aria-checked", "true")
    assert page.evaluate(
        "() => document.activeElement.closest('#cards-decision') !== null"
    )
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")


def test_a_control_that_types_nothing_keeps_the_pages_keyboard(browser, serve):
    """A scope claims the keys it uses and leaves the rest in place. This one used to
    claim the lot: the typing scope stood wherever focus was in a form control, on the
    reading that a letter is a keystroke there — true of a text box, false of a radio, a
    checkbox and a slider, none of which the platform ever hands a letter. So a user
    focusing a screenshot's before/after switch lost c, the walks, the version keys and
    the reference itself, and the line went blank rather than wrong, which is how it
    reaches its author as "the keyboard stopped working".

    One key had already been rescued from that swallow by hand, in a branch inside the
    typing scope's own row. Every other key it took stayed taken, and that is what says the
    swallow was the wrong shape rather than one key short.

    The claim has to hold in both directions or it has bought nothing, so the control's
    own key is asserted beside the page's: a page whose keyboard stands over a radio must
    not be taking Space off it."""
    html = NOTED_PAGE.replace(
        "</main>",
        '<label><input id="flip" type="radio" name="frame"> after</label>'
        '<input id="note" type="text"></main>',
    )
    page = open_page(browser, serve(html))
    # Two page rows, because the claim is the whole keyboard rather than one key: `c`,
    # and the movement row. A scope that swallowed the page would take both, and the box
    # below is where both go.
    page.locator("#flip").focus()
    routes = offered_routes(page)
    assert {"comment.create", "page.down", "page.up"} <= routes.keys(), routes
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#flip")).to_be_focused()
    page.keyboard.press("Space")
    expect(page.locator("#flip")).to_be_checked()
    # The letter reaches the page, which is the whole claim; where it then goes is the
    # the current location's business — a user on the radio is focused on it, so the box that
    # opens is about it rather than about the page. Named in full, because "comment on
    # the" matches every destination this key has and would assert nothing about which.
    # The box names the radio by its label, as a screen reader does.
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer")).to_contain_text("control · after")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-composer")).to_be_hidden()
    expect(page.locator("#flip")).to_be_focused()

    # The box beside it, where every one of those letters is the user's. The line
    # names none of them, which is the same register saying so.
    page.locator("#note").focus()
    routes = offered_routes(page)
    assert not {"comment.create", "page.down"} & routes.keys(), routes
    page.keyboard.press("c")
    expect(page.locator("#note")).to_have_value("c")
    expect(page.locator(".lf-command-reference")).to_be_hidden()
    page.keyboard.press("?")
    expect(page.locator("#note")).to_have_value("c?")
    expect(page.locator(".lf-command-reference")).to_be_hidden()


def test_a_label_press_keeps_the_controls_current_keyboard_location(browser, serve):
    """Leaf treats a label's native activation as one keyboard location.

    Chromium moves focus through body between mousedown and native label activation.
    That intermediate state must not repaint focus-derived surfaces. The native click
    and text selection must still work."""
    html = leaf_page(
        "label focus",
        """
<h1 id="frames">Choose a frame</h1>
<lf-ask id="first-question-decision"><h2>Which first frame?</h2>
<lf-options id="first-question" choose>
  <lf-option id="first-frame"><strong>First</strong>
    <label><input id="first" type="radio" name="first-frame">
      <span>first state</span></label>
  </lf-option>
  <lf-option id="neither-first-frame"><strong>Neither</strong></lf-option>
</lf-options></lf-ask>
<lf-ask id="frame-question-decision"><h2>Which next frame?</h2>
<lf-options id="frame-question" choose>
  <lf-option id="after-frame"><strong>After</strong>
    <div id="label-thread" tabindex="-1">
    <label id="frame-label"><input id="frame" type="radio" name="frame">
      <span>after state</span></label>
    </div>
  </lf-option>
  <lf-option id="before-frame"><strong>Before</strong></lf-option>
</lf-options></lf-ask>
""",
    )
    page = open_page(browser, serve(html, anchored=[("frames", "Choose a frame")]))
    # Arrange the runtime's shared thread surface around the native label. Its
    # focusable container exposes Chromium's intermediate focus during activation.
    page.locator("#label-thread").evaluate(
        "thread => thread.classList.add('lf-page-thread')"
    )
    first = page.locator("#first")
    control = page.locator("#frame")
    words = page.locator("#frame-label span")
    first.focus()
    current_location = offered_routes(page)
    expect(page.locator("#first-question-decision[data-lf-obligation]")).to_have_count(
        1
    )

    # A secondary contact does not drive native label activation, so it must not
    # start the logical transaction either.
    page.evaluate(
        """() => {
          const init = {bubbles: true, composed: true, pointerId: 98,
                        pointerType: 'touch', isPrimary: false, button: 0};
          document.querySelector('#frame-label').dispatchEvent(
            new PointerEvent('pointerdown', init)
          );
          document.activeElement.blur();
        }"""
    )
    page.evaluate(
        """() => dispatchEvent(new PointerEvent('pointerup', {
          bubbles: true, composed: true, pointerId: 98,
          pointerType: 'touch', isPrimary: false, button: 0
        }))"""
    )
    first.focus()
    assert offered_routes(page) == current_location
    rendered(page)
    assert current_location_ring(page)

    bounds = words.bounding_box()
    assert bounds is not None
    middle = (bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2)
    page.mouse.move(*middle)
    page.mouse.down()
    page.evaluate(
        """() => {
          const init = {bubbles: true, composed: true, pointerId: 99,
                        pointerType: 'touch', isPrimary: true, button: 0};
          document.body.dispatchEvent(new PointerEvent('pointerdown', init));
          dispatchEvent(new PointerEvent('pointerup', init));
        }"""
    )
    assert offered_routes(page) == current_location
    held_obligation = page.locator("#first-question-decision[data-lf-obligation]")
    expect(held_obligation).to_have_count(1)
    assert "[data-lf-obligation]" in ring_rule(held_obligation, pseudo="after")
    # Native label activation temporarily blurs the radio. Its logical input
    # destination remains in place until the label's click transfers focus. The
    # pointer press removes its keyboard cue without moving that location.
    assert not first.evaluate("control => control.matches(':focus')")
    assert current_location_ring(page) is None
    assert not ring_faults(rings_drawn(page), "while the label press holds focus")
    intermediate = page.locator("#label-thread")
    expect(intermediate).to_be_focused()
    # The platform temporarily focuses the enclosing thread, but the logical
    # destination remains the radio. Neither its ordinary pseudo-ring nor its
    # high-contrast focus-within outline may show that intermediate native focus.
    thread_paint = """thread => [getComputedStyle(thread).outlineStyle,
      getComputedStyle(thread, '::after').outlineStyle]"""
    assert intermediate.evaluate(thread_paint) == ["none", "none"]
    page.emulate_media(forced_colors="active")
    assert intermediate.evaluate(thread_paint) == ["none", "none"]
    assert current_location_ring(page) is None
    page.emulate_media(forced_colors="none")
    page.mouse.up()
    expect(control).to_be_checked()
    expect(control).to_be_focused()
    expect(page.locator("#frame-question-decision[data-lf-obligation]")).to_have_count(
        1
    )

    # The press has its own frame and the drag comes after it, so the line's only route
    # to the word is the selection the drag makes: the user is taking words out of a
    # label, and from the first glyph Escape clears that selection rather than letting
    # go of the control. Framed the other way round the press's frame painted the line
    # after the drag had already run, and the word arrived whether or not anything
    # followed the selection.
    hold_selection(
        page,
        (bounds["x"] + 2, middle[1]),
        (bounds["x"] + bounds["width"] - 2, middle[1]),
        steps=10,
        frame_the_press=True,
    )
    assert "after state" in page.evaluate("() => getSelection().toString()")
    page.mouse.up()

    control.focus()
    # Retained DOM moves keep native focus without another focusin. The canonical
    # focus-within paint must still leave the former parent and reach the new one.
    expect(control).to_be_focused()
    moved = page.evaluate("""() => {
      const control = document.querySelector('#frame');
      const newParent = document.querySelector('#first-frame');
      const events = [];
      control.addEventListener('focusin', event => events.push(event.type), {once: true});
      newParent.moveBefore(document.querySelector('#label-thread'), null);
      return {focused: document.activeElement === control, events};
    }""")
    assert moved == {"focused": True, "events": []}
    expect(page.locator("#after-frame[data-lf-focus-within]")).to_have_count(0)
    expect(page.locator("#first-frame[data-lf-focus-within]")).to_have_count(1)
    expect(control).to_be_focused()


def test_escape_on_a_declaring_control_does_exactly_what_it_says(browser, serve):
    """One press is one action: the rung is the innermost scope in reach that binds
    Escape, and the dispatcher runs that one and no other. The draft editor's Esc used
    to be two — the edit cancelled and the runtime's ladder closed the panel behind it.
    Each control kept that by hand once and the stack keeps it now, so this is the test
    that says the structure holds. The editor's Esc cancels the edit and nothing else,
    and a grabbed card's Esc cancels the move and leaves the open view standing."""
    html = BOARD_PAGE.replace(
        "</main>", '<lf-draft id="plan"><pre>Ship it.</pre></lf-draft></main>'
    )
    url = serve(html)
    append_carried_log_record(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "A thread."},
    )
    page = open_page(browser, url)
    resized(page, 1920, 900)

    draft_control(page, "edit", "plan").click()
    ta = page.locator("lf-draft leaf-text")
    expect(ta).to_be_focused()
    write(ta, "Ship it — but louder.")
    page.keyboard.press("Escape")
    expect(ta).to_have_count(0)  # the editor closed…
    expect(page.locator("lf-draft .lf-draft-body")).to_have_text("Ship it.")

    # A grabbed card: Esc cancels the move, and the view it would have closed stands.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, view="threads")
    grip = page.locator("#card-heater .lf-grip")
    grip.focus()
    page.keyboard.press("Enter")
    # The contract's flip side: the sequence refuses to arm over a control that has
    # claimed Escape, or one press would have two owners — the grip consuming it,
    # the sequence promising its cancel.
    page.keyboard.press("g")
    rendered(page)
    expect(page.locator("body")).not_to_have_attribute("data-lf-go-to-active", "")
    page.keyboard.press("Escape")
    # The grab is over (an uncancelled one would also leave the card in Todo), and
    # the view the ladder would have put away stands.
    expect(page.locator(".lf-lift")).to_have_count(0)
    expect(page.locator("#col-todo #card-heater")).to_have_count(1)
    expect(page.locator(PANEL)).to_have_attribute("data-open", "threads")


@pytest.mark.parametrize("entry", ["walk", "option", "aim"])
def test_comment_escape_returns_to_its_authored_parent(browser, serve, entry):
    """Closing a comment removes one layer: composer, then its authored subject.
    The same obligation is the parent when walking, focusing an option, or aiming at
    its heading; entry history cannot change its Escape route."""
    page = open_page(browser, serve(WHERE_I_STAND_PAGE))
    item = page.locator("#shape-decision")
    if entry == "walk":
        page.keyboard.press("m")
        expect(item).to_be_focused()
        page.keyboard.press("c")
    elif entry == "option":
        item.locator(".lf-pick").first.focus()
        page.keyboard.press("c")
    else:
        item.locator("h2").click(modifiers=["Alt"])
    expect(page.locator(".lf-composer")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-composer")).to_be_hidden()
    expect(item).to_be_focused()
    page.keyboard.press("Escape")
    assert page.evaluate("document.activeElement === document.body")


def test_a_page_element_named_host_leaves_the_keyboard_climb_at_the_document(
    browser, serve
):
    """A document names its `<form name="host">` as `document.host`. The climb that
    measures how far a scope's root stands above the focused control took any `host` it
    met for a shadow host, so past the document it walked back into the page and around
    again, for good, as soon as the open panel's Escape step stood outside the focus."""
    page = open_page(
        browser,
        serve(
            leaf_page("Named host", '<form name="host"></form><p>Words to read.</p>')
        ),
    )
    assert page.evaluate("document.host instanceof HTMLFormElement")
    open_threads(page)
    page.keyboard.press("Escape")
    panel_settled(page, open=False)


def test_a_command_button_owns_activation_and_the_native_form_default(browser, serve):
    """A command's pointer/native-key press and shortcut perform one semantic result."""
    page = open_page(browser, serve(NOTED_PAGE))
    page.evaluate(
        """async () => {
          const {commandsChanged} = await window.__lfWidgetApi();
          const form = document.createElement('form');
          const button = document.createElement('button');
          button.id = 'command-form-button';
          button.textContent = 'Apply command';
          form.append(button);
          document.querySelector('main').prepend(form);
          window.commandForm = {runs: 0, submits: 0, available: true,
            invalidate: () => commandsChanged(form)};
          form.addEventListener('submit', event => {
            event.preventDefault();
            window.commandForm.submits++;
          });
          form.lfCommands = { title: 'In the command form', rows: [{
            id: 'test.apply-form', keys: ['x'], title: 'Apply command', control: button,
            when: () => window.commandForm.available,
            run: () => window.commandForm.runs++,
          }] };
          commandsChanged(form);
        }"""
    )
    button = page.locator("#command-form-button")
    rendered(page)
    expect(button).not_to_have_attribute("aria-keyshortcuts")
    page.keyboard.press("x")
    assert page.evaluate("() => commandForm.runs") == 0
    button.click()
    page.keyboard.press("Enter")
    page.keyboard.press("Space")
    page.keyboard.press("x")
    assert page.evaluate("() => [commandForm.runs, commandForm.submits]") == [4, 0]
    expect(button).to_have_attribute("aria-keyshortcuts", "x")
    page.evaluate("() => {commandForm.available = false; commandForm.invalidate();}")
    expect(button).to_be_disabled()
    page.keyboard.press("x")
    assert page.evaluate("() => [commandForm.runs, commandForm.submits]") == [4, 0]
    page.evaluate("() => {commandForm.available = true; commandForm.invalidate();}")
    expect(button).to_be_enabled()
    button.click()
    assert page.evaluate("() => [commandForm.runs, commandForm.submits]") == [5, 0]
    # The platform exempts the first legend in a disabled fieldset. Command-owned
    # disabled output must follow that constraint without trapping its previous paint.
    page.evaluate(
        """() => {
          const fieldset = document.createElement('fieldset');
          fieldset.disabled = true;
          const legend = document.createElement('legend');
          fieldset.append(legend, document.querySelector('#command-form-button'));
          document.querySelector('form').append(fieldset);
          commandForm.legend = legend;
          commandForm.invalidate();
        }"""
    )
    expect(button).to_be_disabled()
    page.evaluate(
        """() => {
          commandForm.legend.append(document.querySelector('#command-form-button'));
          commandForm.invalidate();
        }"""
    )
    expect(button).to_be_enabled()
    button.click()
    assert page.evaluate("() => [commandForm.runs, commandForm.submits]") == [6, 0]
    page.evaluate(
        """async () => {
          const {commandsChanged} = await window.__lfWidgetApi();
          document.querySelector('fieldset').disabled = false;
          const one = document.querySelector('#command-form-button');
          const two = document.createElement('button');
          two.id = 'command-form-second';
          two.textContent = 'Second route';
          one.form.append(two);
          commandForm.routes = [];
          commandForm.firstRouteAvailable = false;
          one.form.lfCommands = { title: 'Routed form', rows: [{
            id: 'test.form-routes', keys: ['1', '2'], title: 'Apply route', control: one,
            routes: [{id: 'test.form-one', title: 'First', binding: '1',
              when: () => commandForm.firstRouteAvailable},
              {id: 'test.form-two', title: 'Second', binding: '2', control: two}],
            run: binding => commandForm.routes.push(binding),
          }] };
          commandsChanged(one.form);
          commandForm.invalidate();
        }"""
    )
    second = page.locator("#command-form-second")
    expect(button).to_be_disabled()
    second.click()
    page.keyboard.press("1")
    page.keyboard.press("2")
    assert page.evaluate("() => commandForm.routes") == ["2", "2"]
    # A stale enabled native seat still consumes the command's form default when
    # genuine ARIA availability refuses its activation.
    page.evaluate(
        """() => {
          const one = document.querySelector('#command-form-button');
          one.disabled = false;
          one.click();
        }"""
    )
    assert page.evaluate("() => [commandForm.routes, commandForm.submits]") == [
        ["2", "2"],
        0,
    ]


def test_native_layer_transitions_change_state_without_rewriting_reflected_attributes(
    browser,
):
    """Native focus guards change eligibility even when inert returns to its start.

    Opening and closing include popovers and modal roots inside closed shadow trees.
    Only actual native transitions credit their participating eligibility roots.
    """
    page = browser.new_page()
    page.goto(
        "data:text/html,<!doctype html><body><div id=unrelated></div>"
        "<div id=shadow-host></div><dialog id=native-transition-probe>"
        "<div id=native-popover popover=manual><input autofocus></div></dialog>"
    )
    page.evaluate("""() => {
      window.dialog = document.querySelector('#native-transition-probe');
      window.popover = document.querySelector('#native-popover');
      window.shadowModal = document.createElement('dialog');
      shadowModal.id = 'shadow-modal';
      document.querySelector('#shadow-host').attachShadow({mode:'closed'}).append(shadowModal);
      window.guard = (roots, change) => {
        for (const root of roots) root.inert = true;
        try { change(); }
        finally { for (const root of roots) root.inert = false; }
      };
      dialog.show();
    }""")
    # Separate mutation checkpoints ensure an opening's eligibility credit cannot
    # hide a missing close guard, especially for the modal in the closed shadow tree.
    for transition in [
        "() => guard([dialog], () => { dialog.close(); dialog.showModal(); })",
        "() => guard([shadowModal], () => shadowModal.showModal())",
        "() => guard([document.documentElement, dialog, shadowModal], () => shadowModal.close())",
        "() => guard([popover], () => popover.showPopover())",
        "() => guard([document.documentElement, dialog], () => popover.hidePopover())",
    ]:
        page.evaluate(transition)
    assert page.evaluate("""() => ({
      modal: dialog.matches(':modal'), shadow: shadowModal.open,
      popover: popover.matches(':popover-open'),
      inert: [document.documentElement, dialog, shadowModal, popover].some(node => node.inert),
    })""") == {"modal": True, "shadow": False, "popover": False, "inert": False}
    assert page.lf_errors == []

    page.evaluate("""() => {
      dialog.setAttribute('open', '');
      guard([dialog], () => {});
      guard([shadowModal, document.documentElement], () => shadowModal.close());
      guard([document.querySelector('#unrelated'), popover], () => popover.showPopover());
    }""")
    page.evaluate("() => guard([popover], () => popover.showPopover())")
    failures = consume_browser_errors(page, {"code": "unchanged-write"})
    assert {(error.values["what"], *error.values["node"]) for error in failures} == {
        ("open", "dialog#native-transition-probe"),
        ("inert", "dialog#native-transition-probe"),
        ("inert", "dialog#shadow-modal", "#shadow-root", "div#shadow-host"),
        ("inert", "html"),
        ("inert", "div#unrelated"),
        ("inert", "div#native-popover"),
    }, failures
    page.evaluate("() => { popover.hidePopover(); dialog.close(); }")
