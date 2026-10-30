"""Undo, refusal, outbox, and reconciliation tests."""

import json
import math
import re
from datetime import UTC, datetime, timedelta

import pytest
from interact_support import (
    add_test_widget,
    append_carried_log_record,
    append_command,
    refused_on,
)
from playwright.sync_api import expect
from render_cases_interaction import (
    HOLD_MOTION,
    SUGGESTION_PAGE,
    live_url,
)
from render_cases_layout import (
    unfolded_button,
)
from render_cases_navigation import (
    NESTED_SUGGESTION,
    UNDO_PAGE,
    actions,
    composer_quote,
    mark_shows_beside_composer,
    pending_text,
)
from render_harness import (
    AVAILABLE_COMMANDS,
    BOARD_PAGE,
    EXAMPLE_PACKAGES,
    INLINE_PAGE,
    LONG_PAGE,
    PANEL_THREAD,
    RELEASE_FOCUS,
    REPLAYED_PAGE,
    SETTLED_PAGE,
    CutOff,
    Traffic,
    _traffic,
    available_commands,
    consume_browser_errors,
    draft_control,
    expect_obligations_answered,
    expect_panel_offers,
    expect_panel_says,
    holding,
    http_error_console,
    is_problem,
    leaf_page,
    navigate,
    nudge,
    open_page,
    open_threads,
    page_comment,
    pane_scroll_behavior,
    panel_control,
    panel_settled,
    primed,
    refuse,
    reported_browser_errors,
    resized,
    root_overflow,
    round_trip,
    said,
    scroll_settled,
    sending,
    stamp_page,
    suggestion_control,
    take_browser_errors,
    told,
    undo,
    wait_for_check_api,
    wait_for_revision,
    write,
)

from browser.test_render_application_boundary import long_thread
from browser.threads import open_panel_thread
from leaf import event_log as events_model
from leaf import schema as schema_model
from leaf.registry.contract import RANK
from leaf.render_checks import rendered
from leaf.render_gate.scheme import console_finding
from leaf_dev.browser import threads_tab

DRAG_HELD = "async () => (await window.__lfCheckApi()).dragHeld()"

pytestmark = pytest.mark.shifts_unsurveyed


def fail_reading_commit(page, reading, fault):
    """Fail one required reading stamp after its accepted state has been published.

    A widget's explicit fail-soft view is valid presentation; this required commit
    has no such fallback. Match the reading so unrelated responses cannot spend the
    fault, and restore the native method before throwing so a later read can recover.
    """
    page.evaluate(
        """({reading, fault}) => {
          const body = document.body;
          const setAttribute = body.setAttribute;
          body.setAttribute = function(name, value) {
            if (name === 'data-lf-reading' && value === reading) {
              body.setAttribute = setAttribute;
              throw new Error(fault);
            }
            return setAttribute.call(this, name, value);
          };
        }""",
        {"reading": reading, "fault": fault},
    )


def undo_offered(page, offered=True):
    """Wait until the dispatcher would, or would not, take `z` for Undo where focus
    stands: the reading the leaf's menu greys its Undo row by."""
    page.evaluate(AVAILABLE_COMMANDS)
    page.wait_for_function(
        "offered => (window.__lfAvailableCommands()['history.undo']?.includes('z')"
        " ?? false) === offered",
        arg=offered,
    )


def test_a_refused_message_cannot_present_before_its_thread_reconciles(
    serve, held_events
):
    """The rejection publication owes new chrome, even without any widget renderer."""
    browser, held = held_events
    page = open_page(browser, serve(INLINE_PAGE))
    field = page_comment(page)
    write(field, "A message the server will refuse")
    field.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the optimistic message")
    expect(page.locator(PANEL_THREAD)).to_contain_text(
        "A message the server will refuse"
    )
    # Observe the instant after the immutable rejection publishes and seals, before
    # its queued imperative application. A later settled read cannot see an overclaim.
    page.evaluate("""async () => {
      const {watchSemantic, readApplication, readApplicationPresentation, applicationPresented} =
        await window.__lfCheckApi();
      let previous = readApplication().effective.thread.all.length;
      watchSemantic(root => {
          const count = root.effective.thread.all.length;
          if (previous > 0 && count === 0) queueMicrotask(() => {
            window.rejectionPresentation = {
              ...readApplicationPresentation(), presented: applicationPresented(),
            };
          });
          previous = count;
        });
    }""")
    held.pop().fulfill(
        status=200, json={"ok": False, "final": True, "error": "refused"}
    )
    round_trip(page)
    page.wait_for_function("window.rejectionPresentation !== undefined")
    reading = page.evaluate("window.rejectionPresentation")
    assert reading["sealed"] is True, reading
    assert reading["presented"] is False, reading
    assert "thread" in reading["pending"], reading
    expect(page.locator(PANEL_THREAD)).to_have_count(0)


def test_z_takes_back_the_thread_the_user_just_resolved(browser, serve):
    """The gesture with no reverse in front of the user: resolving a thread moves the
    user on from it, so putting it back by hand means finding it under Resolved and
    pressing Reopen. What `z` writes is a withdrawal
    naming the resolve — not a second settlement, which would read as the user
    deciding to reopen a thread they had only meant not to close."""
    page = open_page(browser, serve(LONG_PAGE, comments=3))
    comments = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    comment = comments[0]
    # The user has done nothing, so there is nothing to take back — a thread the
    # agent closed with `leaf thread resolve` is not theirs to reopen by pressing undo.
    append_carried_log_record(
        serve.page_dir,
        {"kind": "resolve", "author": "agent", "agent": "A", "parent": comments[1]},
    )
    told(page)
    undo_offered(page, offered=False)

    open_panel_thread(page, comment)
    page.locator(".lf-fp-settle").click()
    round_trip(page)

    undo(page)
    # Back among the open threads: the user's own and the third, the agent's closed.
    expect(threads_tab(page).locator(".lf-fp-count")).to_have_text("2")
    log = events_model.read_events(serve.page_dir)
    assert log[-1] == {
        **log[-1],
        "kind": "undo",
        "author": "user",
        "undoes": next(
            e["id"] for e in log if e["kind"] == "resolve" and e["author"] == "user"
        ),
    }
    assert [e["kind"] for e in log if e["kind"] == "unresolve"] == []
    # The undo is not itself a gesture to take back, so the offer goes with it.
    undo_offered(page, offered=False)


def test_z_waits_for_an_unanswered_thread_resolution(browser, serve):
    """Resolve and reopen are undoable gestures too. While a second resolve is in
    the outbox, undo cannot name the older resolve still visible in the log."""
    page = open_page(browser, serve(LONG_PAGE, comments=3))
    comment_ids = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    open_panel_thread(page, comment_ids[0])
    page.locator(".lf-fp-settle").click()
    round_trip(page)
    undo_offered(page)

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    sent = _traffic(page).sends
    # Resolving the thread open from Threads moves the user on to the next one.
    expect(page.locator(PANEL_THREAD)).to_have_attribute("data-thread", comment_ids[1])
    page.locator(".lf-fp-settle").click()
    holding(page, held, 1, "the second resolution")
    undo_offered(page, offered=False)
    page.keyboard.press("z")
    assert _traffic(page).sends == sent + 1

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    undo(page)
    assert [
        event["kind"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] in {"resolve", "undo"} and event["author"] == "user"
    ] == ["resolve", "resolve", "undo"]


def test_z_stops_at_a_newer_gesture_it_cannot_take_back(browser, serve):
    """`z` takes back the user's newest gesture or nothing. A reply sent after a
    resolve cannot be unsaid, so the resolve behind it is no longer the last change
    the user made, and the press reopens nothing."""
    page = open_page(browser, serve(LONG_PAGE, comments=3))
    first, second = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ][:2]
    open_panel_thread(page, first)
    page.locator(".lf-fp-settle").click()
    round_trip(page)
    undo_offered(page)

    append_carried_log_record(
        serve.page_dir,
        {"kind": "reply", "author": "user", "parent": second, "text": "And this?"},
    )
    told(page)
    undo_offered(page, offered=False)
    page.keyboard.press("z")
    told(page)
    assert [
        event["kind"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "undo"
    ] == []


def test_z_names_what_it_takes_and_how_long_ago_in_a_fresh_tab(browser, serve):
    """A page opened weeks after the user's last gesture still says what `z` would
    take back, read from the log rather than from the tab that made it: the leaf's
    menu names the thread they resolved and how long ago, and so does the undo's
    notice. An action is named in its own document's words, under the name the page
    gives its widget."""
    url = serve(UNDO_PAGE, comments=1)
    [comment] = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "thread_title",
            "author": "agent",
            "thread": comment,
            "title": "Rollout safety",
        },
    )
    weeks_ago = datetime.now(UTC) - timedelta(days=21)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "resolve",
            "author": "user",
            "parent": comment,
            "ts": weeks_ago.isoformat(),
        },
    )
    page = open_page(browser, url)
    # The row's words may be cut, so it says the age at its end and is whole on hover.
    row = panel_control(page, "command:history.undo")
    expect(row.locator(".lf-fp-label")).to_have_text("Undo: resolved “Rollout safety”")
    expect(row.locator(".lf-fp-value")).to_have_text("21d ago")
    resolved = "resolved “Rollout safety” · 21d ago"
    expect(row).to_have_attribute("title", f"Undo: {resolved}")
    # The thread is out of view, so the first press shows it (Show, then take).
    row.click()
    expect(page.locator(".lf-live")).to_have_text(f"Press again to undo: {resolved}")
    with sending(page, "the withdrawal"):
        panel_control(page, "command:history.undo").click()
    expect(page.locator(".lf-live")).to_have_text(f"Undid: {resolved}")

    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "picks",
            "action": "choose",
            "detail": {"value": ["opt-a"]},
        },
    )
    told(page)
    expect(panel_control(page, "command:history.undo")).to_have_attribute(
        "title",
        "Undo: chose “Keep the mounts” in “Should we keep the mounts?” · just now",
    )


def _undos(page_dir):
    return [
        e["undoes"] for e in events_model.read_events(page_dir) if e["kind"] == "undo"
    ]


def _old_resolve_below_the_fold(serve, *, picked_up=False):
    """A page whose user resolved a thread on its 56th paragraph three weeks ago, in
    another tab, with the agent's pickup of it when `picked_up`. Returns the page's
    URL, the thread's id and the resolve's."""
    url = serve(LONG_PAGE, anchored=(("p55", "Paragraph 55."),))
    [comment] = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "thread_title",
            "author": "agent",
            "thread": comment,
            "title": "Feeder",
        },
    )
    resolve = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "resolve",
            "author": "user",
            "parent": comment,
            "ts": (datetime.now(UTC) - timedelta(days=21)).isoformat(),
        },
    )
    if picked_up:
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "pickup",
                "author": "page",
                "attention": False,
                "events": [resolve["id"]],
                "phase": "opened",
                "session": "show-then-take",
                "turn": "turn-1",
            },
        )
    return url, comment, resolve["id"]


def _shown(page, thread):
    """The thread's transcript, open and in the window."""
    expect(
        page.locator(
            f'.lf-page-thread[data-thread="{thread}"][data-lf-part="transcript"]'
        )
    ).to_be_in_viewport()


ARMED = "Press again to undo: resolved “Feeder” · 21d ago"


def test_z_shows_an_old_resolve_out_of_view_before_taking_it(browser, serve):
    """A thread resolved weeks ago below the fold is reopened only once the user has
    seen it: the first `z` opens the thread and says that the next press takes it back,
    writing nothing; the second press withdraws the resolve."""
    url, thread, resolve = _old_resolve_below_the_fold(serve)
    page = open_page(browser, url)
    undo_offered(page)
    page.keyboard.press("z")
    expect(page.locator(".lf-live")).to_have_text(ARMED)
    _shown(page, thread)
    told(page)
    assert _undos(serve.page_dir) == []

    with sending(page, "the withdrawal"):
        page.keyboard.press("z")
    assert _undos(serve.page_dir) == [resolve]
    expect(page.locator(".lf-live")).to_have_text("Undid: resolved “Feeder” · 21d ago")


def test_a_quick_second_z_waits_for_the_first_to_show_its_gesture(browser, serve):
    """Two presses of `z` in one task, before the first has opened what it shows, take
    nothing back: the second press arrives before the gesture reached the screen, so
    it shows again rather than withdrawing what the user never saw."""
    url, _thread, _resolve = _old_resolve_below_the_fold(serve)
    page = open_page(browser, url)
    undo_offered(page)
    page.evaluate(
        """() => {
          for (let i = 0; i < 2; i++)
            document.activeElement.dispatchEvent(
              new KeyboardEvent("keydown", { key: "z", code: "KeyZ", bubbles: true }),
            );
        }"""
    )
    expect(page.locator(".lf-live")).to_have_text(ARMED)
    told(page)
    assert _undos(serve.page_dir) == []


def test_z_takes_a_gesture_in_view_the_agent_has_not_picked_up_at_once(browser, serve):
    """A choice in front of the user, made in another tab and not yet handed to the
    agent, is taken back by one press, as before."""
    url = serve(UNDO_PAGE)
    choice = append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "picks",
            "action": "choose",
            "detail": {"value": ["opt-a"]},
        },
    )
    page = open_page(browser, url)
    undo_offered(page)
    with sending(page, "the withdrawal"):
        page.keyboard.press("z")
    assert _undos(serve.page_dir) == [choice["id"]]


def test_z_shows_a_gesture_the_agent_picked_up_even_in_view(browser, serve):
    """The agent may already have acted on a gesture it picked up, so `z` shows it
    first wherever it stands: the choice in view is travelled to and outlined, as a
    link to it would, and only the second press takes it back."""
    url = serve(UNDO_PAGE)
    choice = append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "picks",
            "action": "choose",
            "detail": {"value": ["opt-a"]},
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "pickup",
            "author": "page",
            "attention": False,
            "events": [choice["id"]],
            "phase": "opened",
            "session": "show-then-take",
            "turn": "turn-1",
        },
    )
    page = open_page(browser, url)
    undo_offered(page)
    page.keyboard.press("z")
    expect(page.locator(".lf-live")).to_have_text(
        "Press again to undo: chose “Keep the mounts” in “Should we keep the mounts?”"
        " · just now"
    )
    expect(page.locator("#picks")).to_be_focused()
    told(page)
    assert _undos(serve.page_dir) == []
    with sending(page, "the withdrawal"):
        page.keyboard.press("z")
    assert _undos(serve.page_dir) == [choice["id"]]


FAR_CHOICE_PAGE = leaf_page(
    "undo-far",
    """
<h1 id="h">Far</h1>
{paras}
<lf-ask id="picks-decision"><h2>Should we keep the mounts?</h2>
<lf-options id="picks" choose>
  <lf-option id="opt-a">Keep the mounts</lf-option>
  <lf-option id="opt-b" chosen>Replace the mounts</lf-option>
</lf-options></lf-ask>
""",
).format(
    paras="\n".join(
        f"<p id='p{i}'>Paragraph {i}. " + "Filler. " * 20 + "</p>" for i in range(40)
    )
)


def test_another_key_or_a_scroll_away_puts_the_shown_gesture_back_to_showing(
    browser, serve
):
    """The second press takes the gesture back only while the user is still on what
    the first showed: another key, or scrolling it out of view, means the next `z`
    shows it again. A modifier alone, or scrolling with it still in view, keeps it."""
    url = serve(FAR_CHOICE_PAGE)
    choice = append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "picks",
            "action": "choose",
            "detail": {"value": ["opt-a"]},
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "pickup",
            "author": "page",
            "attention": False,
            "events": [choice["id"]],
            "phase": "opened",
            "session": "show-then-take",
            "turn": "turn-1",
        },
    )
    page = open_page(browser, url)
    undo_offered(page)
    picks = page.locator("#picks")
    expect(picks).not_to_be_in_viewport()

    def pressed_without_taking():
        page.keyboard.press("z")
        expect(picks).to_be_in_viewport()
        # A scroll clears the arm only once the arm has seen what the press showed: its
        # travel finished and the next pass read it in view. The user is on it from
        # then, so a scroll before it would be one no user could make.
        page.wait_for_function("() => !navigation.transition")
        rendered(page)
        told(page)
        assert _undos(serve.page_dir) == []

    pressed_without_taking()
    page.keyboard.press("Shift")
    page.keyboard.press("j")
    # `j` was another key, so this press shows the choice again.
    pressed_without_taking()

    page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    scroll_settled(page)
    expect(picks).not_to_be_in_viewport()
    # The arm reads the scroll in the pass after the window moves.
    rendered(page)
    pressed_without_taking()

    page.mouse.move(400, 300)
    page.mouse.wheel(0, -20)
    scroll_settled(page)
    expect(picks).to_be_in_viewport()
    with sending(page, "the withdrawal"):
        page.keyboard.press("z")
    assert _undos(serve.page_dir) == [choice["id"]]


def test_a_quick_second_z_waits_for_a_fragments_trip(browser, serve):
    """A widget is shown by travelling to it as a fragment, which scrolls after the
    press returns: a second `z` before the choice is in view shows it again rather
    than taking back what the user has not seen."""
    url = serve(FAR_CHOICE_PAGE)
    choice = append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "picks",
            "action": "choose",
            "detail": {"value": ["opt-a"]},
        },
    )
    page = open_page(browser, url)
    undo_offered(page)
    expect(page.locator("#picks")).not_to_be_in_viewport()
    page.evaluate(
        """async () => {
          const z = () =>
            document.activeElement.dispatchEvent(
              new KeyboardEvent("keydown", { key: "z", code: "KeyZ", bubbles: true }),
            );
          z();
          await Promise.resolve();
          await Promise.resolve();
          z();
        }"""
    )
    told(page)
    assert _undos(serve.page_dir) == []
    expect(page.locator("#picks")).to_be_in_viewport()
    with sending(page, "the withdrawal"):
        page.keyboard.press("z")
    assert _undos(serve.page_dir) == [choice["id"]]


def test_the_menus_undo_shows_then_takes_too(browser, serve):
    """A finger's way to Undo is the leaf's menu row, and it goes the same two steps:
    the first press opens the thread, and pressing the row again takes it back, the
    presses on the leaf to reach it keeping what the first one showed."""
    url, thread, resolve = _old_resolve_below_the_fold(serve)
    page = open_page(browser, url)
    panel_control(page, "command:history.undo").click()
    expect(page.locator(".lf-live")).to_have_text(ARMED)
    _shown(page, thread)
    told(page)
    assert _undos(serve.page_dir) == []
    with sending(page, "the withdrawal"):
        panel_control(page, "command:history.undo").click()
    assert _undos(serve.page_dir) == [resolve]


def test_the_undo_rows_age_follows_the_clock_while_the_page_stays_open(browser, serve):
    """The age Undo's row says, at its end and whole in its hover, is read where the
    menu paints, so a page left open keeps it true: a gesture made just now reads
    minutes old once minutes pass, with no new reading of the log."""
    url = serve(UNDO_PAGE, comments=1)
    [comment] = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "resolve",
            "author": "user",
            "parent": comment,
            "ts": datetime.now(UTC).isoformat(),
        },
    )
    page = open_page(primed(browser, lambda page: page.clock.install()), url)
    row = panel_control(page, "command:history.undo")
    expect(row.locator(".lf-fp-value")).to_have_text("just now")
    # Install before navigation so the page's interval belongs to the controlled clock.
    # A paused clock fires no later timer, so only that tick can move the age.
    page.clock.pause_at(datetime.now(UTC) + timedelta(minutes=5))
    expect(row.locator(".lf-fp-value")).to_have_text("5m ago")
    expect(row).to_have_attribute("title", re.compile(r" · 5m ago$"))


def test_z_puts_a_card_back_where_the_version_had_it(browser, serve):
    """A withdrawal leaves the log holding one gesture and one word taking it back,
    and the page derives the rest. What it derives here is the placement this
    version's markup arrived showing, read before replay first touched the page —
    column *and* index, which is why a position record names the detail field
    carrying the order. Compared, a column is the whole comparison; stated, it puts
    a card back on the right list in the wrong place.

    The card is told where it goes rather than the board being rebuilt around it,
    because that state can be stated: the user watches it travel back, and the
    grip they were located on is still under their hands."""
    page = open_page(browser, live_url(serve(BOARD_PAGE)))
    grip = page.locator("#card-baffle .lf-grip")
    grip.focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    round_trip(page)
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)

    undo(page)
    expect(page.locator("#col-todo #card-baffle")).to_have_count(1)
    # Second of the two, as the version wrote it — not merely back on the list.
    assert page.eval_on_selector_all(
        "#col-todo > lf-card", "e => e.map(c => c.id)"
    ) == [
        "card-heater",
        "card-baffle",
    ]
    expect(grip).to_be_focused()
    log = events_model.read_events(serve.page_dir)
    (moved,) = actions(serve.page_dir)
    rank = moved["detail"].pop("rank")
    assert moved["detail"] == {"unit": "card-baffle", "value": "col-done"}
    assert re.fullmatch(RANK, rank)
    assert [(e["kind"], e.get("undoes")) for e in log if e["kind"] == "undo"] == [
        ("undo", moved["id"])
    ]


def test_z_reaches_the_gestures_made_on_the_version_being_read(browser, serve):
    """Where a unit has no earlier action, the state a move is taken back to is what
    this version's markup arrived showing — and a version written around the
    decision shows the decision. So on v2 the authored placement of a card moved on
    v1 is where the move put it, and a press offered there would paint nothing at
    all. The thread is not scoped this way and must not be: a thread outlives
    the version it was opened on, which is why resolve carries no version."""
    page = open_page(browser, live_url(serve(BOARD_PAGE)))
    page.locator("#card-baffle .lf-grip").focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Enter")
    round_trip(page)
    undo_offered(page)

    d = serve.page_dir
    carried = BOARD_PAGE.replace(
        '<lf-card id="card-baffle"><strong>Squirrel baffle</strong></lf-card>\n', ""
    ).replace(
        '<lf-column id="col-done" label="Done">',
        '<lf-column id="col-done" label="Done">'
        '<lf-card id="card-baffle"><strong>Squirrel baffle</strong></lf-card>',
    )
    stamp_page(d, carried, "carried")
    wait_for_revision(page, 2)
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    undo_offered(page, offered=False)
    page.keyboard.press("z")
    told(page)
    # An undo posts no action, so counting actions says nothing about whether the
    # press was refused — it stays at one either way, which is the assertion passing
    # in exactly the failure the test is named for. The log holding no withdrawal is
    # what says it, and the card still being where the move put it is what that means
    # on the page.
    assert [e["kind"] for e in events_model.read_events(d) if e["kind"] == "undo"] == []
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)


def test_z_waits_for_the_gesture_the_log_has_not_taken(browser, serve):
    """The walk finds the last thing the user did by reading the log, so while the
    page holds a gesture the log has not taken it would name the gesture *before*
    that one — and take the wrong thing back, with the card they had just moved
    left where it was. A machine quick enough closes that window before the next
    press can land in it, so the send is stopped in the wire and the press made
    while it is still there."""
    page = open_page(browser, serve(BOARD_PAGE))
    move = ["Enter", "ArrowRight", "Enter"]
    page.locator("#card-heater .lf-grip").focus()
    for key in move:
        page.keyboard.press(key)
    round_trip(page)
    undo_offered(page)

    held = []

    def hold(route):
        # The first send only: what follows has to reach the server, or the press
        # this test is about would be held too and prove nothing.
        if held:
            route.continue_()
        else:
            held.append(route)

    page.route("**/api/event", hold)
    page.locator("#card-baffle .lf-grip").focus()
    for key in move:
        page.keyboard.press(key)
    holding(page, held, 1, "the move it was asked for")
    undo_offered(page, offered=False)
    page.keyboard.press("z")
    assert _traffic(page).sends == 2, (
        "the press took back a gesture read off a log missing the one before it"
    )

    held[0].continue_()
    round_trip(page)
    undo(page)
    # The newest move, which is the one the user would have meant — and the older
    # one still stands, where taking back the wrong gesture would have reversed it.
    expect(page.locator("#col-todo #card-baffle")).to_have_count(1)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)


def test_an_action_response_accounts_for_its_gesture_without_a_follow_up_poll(
    browser, serve
):
    """The event response is state through the event it accepted. Even when every
    later GET is unavailable, the page can take undo immediately and the press names
    the newest gesture rather than the stale one before it."""
    page = open_page(browser, serve(BOARD_PAGE))
    move = ["Enter", "ArrowRight", "Enter"]
    page.locator("#card-heater .lf-grip").focus()
    for key in move:
        page.keyboard.press(key)
    round_trip(page)
    page.wait_for_function("() => document.body.dataset.lfApplied === '1'")

    page.route("**/api/state*", refuse)
    page.locator("#card-baffle .lf-grip").focus()
    for key in move:
        page.keyboard.press(key)
    round_trip(page)
    # `round_trip` proves delivery, not that the page has applied the state carried by
    # the response. With GETs cut off, coverage reaching two can only come from this
    # POST response; it also puts the outbox release and its key repaint behind us.
    page.wait_for_function("() => document.body.dataset.lfApplied === '2'")

    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    # The withdrawal entering the wire is the durable edge that proves the press worked.
    with sending(page, "the withdrawal"):
        page.keyboard.press("z")
    page.wait_for_function("() => document.body.dataset.lfApplied === '3'")
    expect(page.locator("#col-todo #card-baffle")).to_have_count(1)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)


def test_one_supplied_attempt_cannot_name_two_queued_actions(browser, serve):
    """Attempt identity includes the gesture it names. Reusing a token while its
    first action is still in the outbox must refuse the second locally; accounting
    the first by token alone would otherwise resolve both callers with the first
    event and silently discard the second payload before it reached the server."""
    page = open_page(browser, serve(BOARD_PAGE))
    outcome = page.evaluate(
        """async () => {
          const {widgetController} = await window.__lfWidgetApi();
          const board = document.querySelector('#sprint');
          const controller = widgetController(board);
          const attempt = 'one-attempt-two-actions';
          const first = controller.dispatch({
            kind: 'action', verb: 'move', attempt,
            detail: {unit: 'card-heater', value: 'col-done', rank: '0i'},
          });
          const second = controller.dispatch({
            kind: 'action', verb: 'move', attempt,
            detail: {unit: 'card-baffle', value: 'col-done', rank: '0i'},
          });
          return Promise.all([first?.delivery ?? null, second?.delivery ?? null]);
        }"""
    )
    round_trip(page)

    assert outcome[0]["detail"]["unit"] == "card-heater"
    assert outcome[1] is None
    assert [event["detail"]["unit"] for event in actions(serve.page_dir)] == [
        "card-heater"
    ]
    assert _traffic(page).sends == 1
    expect_panel_says(page, "is already in use")


def test_an_accepted_event_is_not_retried_when_its_state_cannot_render(
    browser, serve, request
):
    """Acceptance and presentation are separate outcomes. A failed response commit
    cannot be repaired by re-posting its accepted attempt, so semantic truth advances,
    while replay and undo remain held until a later response proves presentation."""
    page = open_page(browser, serve(SUGGESTION_PAGE))

    def close_page():
        if page.is_closed():
            return
        # A failed assertion can leave the deliberately parked state read unresolved.
        # Cancellation belongs to the browser fixture's context close; waiting here
        # would wait for a response only the rest of the test can release.
        page.unroute_all(behavior="ignoreErrors")

    request.addfinalizer(close_page)
    older = []
    lifted = False

    def hold_older_state(route):
        if lifted:
            route.continue_()
        elif older:
            refuse(route)
        else:
            older.append(route)

    page.route("**/api/state*", hold_older_state)
    with page.expect_request("**/api/state"):
        nudge(serve.page_dir)
    holding(page, older, 1, "the older state read")
    assert len(older) == 1
    old_route = older[0]
    old_state = old_route.fetch().json()

    suggestion_control(page, "sug-refill", "accept").click()
    round_trip(page)
    undo_offered(page)

    requests = []
    first_attempt = []
    refused = []

    def break_first_state(route):
        event = route.request.post_data_json
        if "attempt" not in event:
            route.continue_()
            return
        requests.append(event)
        if event.get("widget") == "sug-in-card" and not refused:
            refused.append(event["attempt"])
            route.fulfill(
                status=400,
                json={
                    "ok": False,
                    "attempt": event["attempt"],
                    "error": "refused before append",
                    "final": True,
                },
            )
            return
        response = route.fetch()
        answer = response.json()
        if not first_attempt:
            first_attempt.append(event["attempt"])
            # An optional widget's fail-soft view is valid presentation. Fail the
            # required reading commit after adoption instead, so the accepted attempt
            # cannot retire from the outbox until a later reading commits.
            fail_reading_commit(
                page, answer["state"]["reading"], "injected accepted-state commit fault"
            )
        route.fulfill(status=response.status, json=answer)

    page.route("**/api/event", break_first_state)
    # The injected commit fault is reported once, whichever operation carries it.
    with page.expect_console_message(
        lambda message: (
            message.type == "error"
            and "injected accepted-state commit fault" in message.text
        )
    ) as reported:
        suggestion_control(page, "sug-thistle", "accept").click()
    expect(page.locator("#sug-thistle")).not_to_have_attribute("aria-busy", "true")
    expect(page.locator("#sug-thistle")).to_have_attribute("data-lf-state", "accept")

    old_route.fulfill(json=old_state)
    page.title()  # let the stale response run before reading the undo surface

    # The caller knows the send succeeded and the semantic root contains it. The stale
    # response must not release the hold because the accepted view never completed
    # presentation.
    assert first_attempt[0] not in _traffic(page).pending
    undo_offered(page, offered=False)
    sent = _traffic(page).sends
    page.keyboard.press("z")
    assert _traffic(page).sends == sent
    # The local margin entry shares the keyboard's guard; it cannot post around an
    # accepted event whose authoritative state is still incomplete.
    first_item = page.locator('[data-lf-margin-for="sug-refill"]')
    first_item.get_by_role("button", name=re.compile(r"^Undo accepting")).click()
    expect_panel_says(page, "Wait for the current change to finish before undoing")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "accept")
    assert _traffic(page).sends == sent

    # A later refusal is another asynchronous reconciliation wake-up. It may not release
    # either hold merely because its delivery completed.
    suggestion_control(page, "sug-in-card", "accept").click()
    round_trip(page)
    expect(page.locator("#sug-in-card")).not_to_have_attribute(
        "data-lf-state", "accept"
    )
    undo_offered(page, offered=False)

    # A complete poll proves presentation of the older acceptance and refused correction.
    # The re-offered action can then send under a fresh attempt, whose valid answer
    # includes both accepted gestures and makes the newest one safe to undo.
    lifted = True
    told(page)
    undo_offered(page)
    suggestion_control(page, "sug-in-card", "accept").click()
    round_trip(page)

    assert [request["attempt"] for request in requests].count(first_attempt[0]) == 1
    assert len(refused) == 1
    assert [
        (event["widget"], event["detail"].get("outcome", event["action"]))
        for event in actions(serve.page_dir)
    ] == [
        ("sug-refill", "accept"),
        ("sug-thistle", "accept"),
        ("sug-in-card", "accept"),
    ]

    undo(page)
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "accept")
    expect(page.locator("#sug-thistle")).to_have_attribute("data-lf-state", "accept")
    expect(page.locator("#sug-in-card")).not_to_have_attribute(
        "data-lf-state", "accept"
    )
    expect(page.locator("#sug-in-card lf-old")).to_be_visible()
    # This test transforms event responses with route.fetch(). A news-triggered POST
    # can enter that handler after the last assertion; closing its context then disposes
    # the APIResponse while the handler is still reading it, and Playwright reports that
    # callback's `Response has been disposed` from the next test's browser call. Remove
    # the routes and wait for any handler already running before their owning page goes.
    page.unroute_all(behavior="wait")
    # The expectation can receive the console event before the fixture's separate
    # collector receives its callback. Let that same event reach the collector.
    for _ in range(200):
        if console_finding(reported.value) in page.lf_errors:
            break
        page.wait_for_timeout(25)
    errors = take_browser_errors(page)
    assert [
        error for error in errors if not is_problem(error, http_error_console(400))
    ] == [console_finding(reported.value)], errors


def test_a_failed_background_presentation_keeps_the_new_undo_authority(browser, serve):
    """A timer response publishes accepted events before presenting their views.
    If the required reading commit fails, z still reads the accepted
    history instead of rolling semantic authority back to the older gesture."""
    page = open_page(browser, serve(BOARD_PAGE))
    heater = page.locator("#card-heater .lf-grip")
    heater.focus()
    for key in ["Enter", "ArrowRight", "Enter"]:
        page.keyboard.press(key)
    round_trip(page)
    first = actions(serve.page_dir)[0]

    failed_reads = []

    def fail_first_commit(route):
        if failed_reads:
            refuse(route)
            return
        response = route.fetch()
        state = response.json()
        fail_reading_commit(page, state["reading"], "injected background commit fault")
        failed_reads.append(True)
        route.fulfill(status=response.status, json=state)

    # The route before the append: the page is told of an append as it lands and
    # asks at once, so a route registered after it is a route the read has passed.
    page.route("**/api/state*", fail_first_commit)
    with (
        page.expect_console_message(
            lambda message: (
                message.type == "error"
                and "injected background commit fault" in message.text
            )
        ) as reported,
        page.expect_request("**/api/state*"),
    ):
        second = append_command(
            serve.page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "sprint",
                "action": "move",
                "detail": {"unit": "card-baffle", "value": "col-done", "rank": "0i"},
            },
        )

    round_trip(page)
    commit = page.evaluate("""async () => {
      const root = (await window.__lfCheckApi()).readApplication();
      return {accepted: root.authoritative.reading, committed: document.body.dataset.lfReading};
    }""")
    assert commit["committed"] != commit["accepted"], commit
    undo_offered(page)
    with page.expect_response(
        lambda response: (
            "/api/event" in response.url
            and (response.request.post_data_json or {}).get("kind") == "undo"
        )
    ):
        page.keyboard.press("z")
    logged_undo = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event["kind"] == "undo"
    )
    assert logged_undo["undoes"] == second["id"]
    assert logged_undo["undoes"] != first["id"]
    expect(page.locator("#col-done #card-heater")).to_have_count(1)
    expect(page.locator("#col-todo #card-baffle")).to_have_count(1)
    assert take_browser_errors(page) == [console_finding(reported.value)]


def test_a_newer_queued_action_survives_an_older_refusal(browser, serve):
    """A later absolute action on the same widget is already painted while an older
    send waits. Refusing the older action must preserve that outbox overlay, including
    while an accepted intermediate answer is older than the newest local gesture. The
    queued state is not a result, so it mints no page-map record before acceptance."""
    page = open_page(browser, serve(BOARD_PAGE))
    page.locator("#card-heater .lf-grip").focus()
    for key in ["Enter", "ArrowRight", "Enter"]:
        page.keyboard.press(key)
    round_trip(page)

    page.route("**/api/state*", refuse)
    held = []

    page.route("**/api/event", lambda route: held.append(route))
    baffle = page.locator("#card-baffle .lf-grip")
    with page.expect_request("**/api/event"):
        baffle.focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    holding(page, held, 1, "the first queued action")
    expect(
        page.locator('[data-lf-margin-for="card-baffle"] [data-lf-behavior="status"]')
    ).to_have_count(0)
    assert len(held) == 1
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)

    # Reorder the same card twice while its move waits. Each action is queued locally
    # and describes its placement whole; the newest says Done, before the heater.
    baffle.focus()
    for key in ["Enter", "ArrowDown", "Enter"]:
        page.keyboard.press(key)
    assert page.eval_on_selector_all(
        "#col-done > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-heater", "card-baffle"]
    assert _traffic(page).sends == 2
    baffle.focus()
    for key in ["Enter", "ArrowUp", "Enter"]:
        page.keyboard.press(key)
    assert page.eval_on_selector_all(
        "#col-done > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-baffle", "card-heater"]
    assert (
        _traffic(page).sends == 2
    )  # the later two actions are queued, not on the wire

    first_attempt = held[0].request.post_data_json["attempt"]
    with page.expect_request(
        lambda request: (
            "/api/event" in request.url
            and request.post_data_json.get("attempt") != first_attempt
        )
    ) as second_request:
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": first_attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    holding(page, held, 2, "the second queued action")
    assert len(held) == 2
    second_attempt = second_request.value.post_data_json["attempt"]
    with page.expect_request(
        lambda request: (
            "/api/event" in request.url
            and request.post_data_json.get("attempt")
            not in {first_attempt, second_attempt}
        )
    ):
        held[1].continue_()
    holding(page, held, 3, "the third queued action")
    assert len(held) == 3

    # The accepted second response states "after heater", but the third gesture is
    # still unresolved and already painted "before heater". The older refusal and
    # intermediate answer may disturb neither half of that local placement.
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    assert page.eval_on_selector_all(
        "#col-done > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-baffle", "card-heater"]

    held[2].continue_()
    page.unroute("**/api/event")
    round_trip(page)

    heater, below, above = (event["detail"] for event in actions(serve.page_dir))
    assert [(d["unit"], d["value"]) for d in (heater, below, above)] == [
        ("card-heater", "col-done"),
        ("card-baffle", "col-done"),
        ("card-baffle", "col-done"),
    ]
    # Each queued send ranks the baffle on the side of the heater the user put it.
    assert above["rank"] < heater["rank"] < below["rank"]
    assert page.eval_on_selector_all(
        "#col-done > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-baffle", "card-heater"]

    undo(page)
    assert page.eval_on_selector_all(
        "#col-done > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-heater", "card-baffle"]
    consume_browser_errors(page, http_error_console(400))


def test_refused_recorded_actions_restore_from_the_log_and_surviving_outbox(
    browser, serve
):
    """Rollback snapshots compose the wrong state: B captures optimistic A, so if
    both are refused, B's snapshot resurrects A. The runtime instead removes each
    action from one overlay and derives the widget from the log plus what survives."""
    page = open_page(browser, serve(BOARD_PAGE))
    page.locator("#card-heater .lf-grip").focus()
    for key in ["Enter", "ArrowRight", "Enter"]:
        page.keyboard.press(key)
    round_trip(page)

    page.route("**/api/state*", refuse)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    baffle = page.locator("#card-baffle .lf-grip")
    with page.expect_request("**/api/event"):
        baffle.focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    baffle.focus()
    for key in ["Enter", "ArrowDown", "Enter"]:
        page.keyboard.press(key)
    baffle.focus()
    for key in ["Enter", "ArrowUp", "Enter"]:
        page.keyboard.press(key)
    assert (
        _traffic(page).sends == 2
    )  # the later two actions are queued, not on the wire

    for at in range(3):
        attempt = held[at].request.post_data_json["attempt"]
        if at < 2:
            with page.expect_request(
                lambda request, attempt=attempt: (
                    "/api/event" in request.url
                    and request.post_data_json.get("attempt") != attempt
                )
            ):
                held[at].fulfill(
                    status=400,
                    json={
                        "ok": False,
                        "attempt": attempt,
                        "error": "refused before append",
                        "final": True,
                    },
                )
            holding(page, held, at + 2, "the next queued action")
        else:
            with page.expect_response(lambda response: "/api/event" in response.url):
                held[at].fulfill(
                    status=400,
                    json={
                        "ok": False,
                        "attempt": attempt,
                        "error": "refused before append",
                        "final": True,
                    },
                )
        if at < 2:
            assert len(held) == at + 2
            assert page.eval_on_selector_all(
                "#col-done > lf-card", "cards => cards.map(card => card.id)"
            ) == ["card-baffle", "card-heater"]

    round_trip(page)
    expect(page.locator("#col-todo #card-baffle")).to_have_count(1)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)
    assert [event["detail"]["unit"] for event in actions(serve.page_dir)] == [
        "card-heater"
    ]
    consume_browser_errors(page, http_error_console(400))


def test_a_refused_position_reconciles_the_logged_order_of_sibling_units(
    browser, serve
):
    """A position unit shares an ordered container with its siblings. Restoring only
    the refused card's authored index can overwrite a different card's logged reorder;
    reconciliation must fold the board whole in action order."""
    page = open_page(browser, serve(BOARD_PAGE), init_script=HOLD_MOTION)
    baffle = page.locator("#card-baffle .lf-grip")
    baffle.focus()
    for key in ["Enter", "ArrowUp", "Enter"]:
        page.keyboard.press(key)
    round_trip(page)
    assert page.eval_on_selector_all(
        "#col-todo > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-baffle", "card-heater"]
    page.evaluate(
        "() => { for (const a of window.__lfHeld) a.cancel(); window.__lfHeld = []; }"
    )

    page.route("**/api/state*", refuse)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        page.locator("#card-heater .lf-grip").focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    holding(page, held, 1, "the refused card move")
    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    round_trip(page)

    assert page.eval_on_selector_all(
        "#col-todo > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-baffle", "card-heater"]
    assert [event["detail"]["unit"] for event in actions(serve.page_dir)] == [
        "card-baffle"
    ]
    motions = page.evaluate(
        """() => window.__lfHeld.map(animation => ({
          target: animation.effect.target.id,
          state: animation.playState,
        }))"""
    )
    assert motions and motions[0] == {
        "target": "card-heater",
        "state": "idle",
    }, "the optimistic move was not the cancelled animation positive control"
    active = [motion["target"] for motion in motions if motion["state"] != "idle"]
    assert len(motions) <= 3 and len(active) == len(set(active)), (
        "reconstruction exposed synthetic authored/log placements as gestures: "
        f"{motions}"
    )
    consume_browser_errors(page, http_error_console(400))


def test_a_refused_position_restores_the_complete_sibling_order(browser, serve):
    """Authored indices are one container composition, not per-card snapshots. A
    refused move must derive the complete order from authored siblings and surviving
    winners before moving nodes; the rejected DOM cannot supply that order."""
    three_cards = BOARD_PAGE.replace(
        '<lf-card id="card-baffle"><strong>Squirrel baffle</strong></lf-card>',
        '<lf-card id="card-baffle"><strong>Squirrel baffle</strong></lf-card>\n'
        '    <lf-card id="card-third"><strong>Third card</strong></lf-card>',
    )
    url = serve(three_cards)
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sprint",
            "action": "move",
            "detail": {"unit": "card-heater", "value": "col-todo", "rank": "k"},
        },
    )
    page = open_page(browser, url)
    cards = "cards => cards.map(card => card.id)"
    assert page.eval_on_selector_all("#col-todo > lf-card", cards) == [
        "card-baffle",
        "card-third",
        "card-heater",
    ]

    page.route("**/api/state*", refuse)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        page.evaluate(
            """() => { void window.__lfWidgetApi().then(({widgetController}) => {
              const widget = document.querySelector('#sprint');
              const detail = {unit: 'card-baffle', value: 'col-todo', rank: 's'};
              document.getElementById(detail.value).append(document.getElementById(detail.unit));
              widgetController(widget).dispatch({kind: 'action', verb: 'move', detail});
            }); }"""
        )
    expect(page.locator("#col-todo > lf-card")).to_have_count(3)
    assert page.eval_on_selector_all("#col-todo > lf-card", cards) == [
        "card-third",
        "card-heater",
        "card-baffle",
    ]

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    round_trip(page)
    assert page.eval_on_selector_all("#col-todo > lf-card", cards) == [
        "card-baffle",
        "card-third",
        "card-heater",
    ]
    assert [event["detail"]["unit"] for event in actions(serve.page_dir)] == [
        "card-heater"
    ]
    consume_browser_errors(page, http_error_console(400))


def test_an_outer_refusal_preserves_a_different_nested_widgets_state(
    browser, serve, tmp_path, monkeypatch
):
    """A recorded container owns only its nearest stateful parts. Projecting a
    project's outer board must not capture cards owned by a nested shipped board merely
    because both record positions within lf-column."""
    monkeypatch.chdir(tmp_path)
    add_test_widget(tmp_path / ".leaf", "lf-outer-board", upgrade=True)
    registry_path = tmp_path / ".leaf" / "registry.json"
    declarations = json.loads(registry_path.read_text())
    outer = declarations["lf-outer-board"]
    outer["properties"]["restated"] = {"type": "boolean"}
    outer["x-content"] = "members"
    outer["x-example"] = (
        '<lf-outer-board id="x-outer"><lf-column id="x-col" label="Todo">'
        '<lf-card id="x-card"><strong>Card</strong></lf-card></lf-column>'
        "</lf-outer-board>"
    )
    outer["x-state"] = {
        "move": {
            "unit": "unit",
            "record": {
                "kind": "position",
                "within": "lf-column",
            },
        }
    }
    standard = json.loads((schema_model.DEFAULT_PACKAGE / "registry.json").read_text())
    declarations["lf-column"] = standard["lf-column"]
    declarations["lf-column"]["x-owners"].append("lf-outer-board")
    registry_path.write_text(json.dumps(declarations))
    (tmp_path / ".leaf" / "widgets" / "lf-outer-board.js").write_text(
        """import { LeafElement } from "/runtime/widget-api.js";
customElements.define("lf-outer-board", class extends LeafElement {
  render() {
    for (const [id, order] of Object.entries(this.state.move.value)) {
      const column = document.getElementById(id);
      for (const id of order) {
        const card = document.getElementById(id);
        if (card.parentElement !== column) column.append(card);
      }
    }
  }
});
"""
    )
    nested = leaf_page(
        "nested owners",
        """
<h1 id="h">Nested owners</h1>
<lf-outer-board id="outer">
  <lf-column id="outer-todo" label="Todo"><lf-card id="outer-card"><strong>Outer</strong>
    <lf-board id="inner"><lf-column id="inner-todo" label="Todo">
      <lf-card id="inner-card"><strong>Inner</strong></lf-card></lf-column>
      <lf-column id="inner-done" label="Done"></lf-column></lf-board>
  </lf-card></lf-column><lf-column id="outer-done" label="Done"></lf-column>
</lf-outer-board>""",
    )
    page = open_page(browser, serve(nested, packages=(*EXAMPLE_PACKAGES, "./.leaf")))
    page.route("**/api/state*", refuse)
    held = []
    page.route("**/api/event", lambda route: held.append(route))

    with page.expect_request("**/api/event"):
        page.evaluate(
            """() => { void window.__lfWidgetApi().then(({widgetController}) => {
              const widget = document.querySelector('#outer');
              const detail = {unit: 'outer-card', value: 'outer-done', rank: '0i'};
              document.getElementById(detail.value).append(document.getElementById(detail.unit));
              widgetController(widget).dispatch({kind: 'action', verb: 'move', detail});
            }); }"""
        )
    holding(page, held, 1, "the outer-board move")
    page.evaluate(
        """() => { void window.__lfWidgetApi().then(({widgetController}) => {
          const widget = document.querySelector('#inner');
          const detail = {unit: 'inner-card', value: 'inner-done', rank: '0i'};
          document.getElementById(detail.value).append(document.getElementById(detail.unit));
          widgetController(widget).dispatch({kind: 'action', verb: 'move', detail});
        }); }"""
    )
    expect(page.locator("#inner-done #inner-card")).to_have_count(1)

    outer_attempt = held[0].request.post_data_json["attempt"]
    with page.expect_request(
        lambda request: (
            "/api/event" in request.url
            and request.post_data_json.get("attempt") != outer_attempt
        )
    ):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": outer_attempt,
                "error": "refused before append",
                "final": True,
            },
        )

    expect(page.locator("#outer-todo > #outer-card")).to_have_count(1)
    expect(page.locator("#inner-done #inner-card")).to_have_count(1)
    held[1].continue_()
    page.unroute("**/api/event")
    round_trip(page)

    expect(page.locator("#inner-done #inner-card")).to_have_count(1)
    assert [
        (event["widget"], event["detail"]["unit"]) for event in actions(serve.page_dir)
    ] == [("inner", "inner-card")]
    consume_browser_errors(page, http_error_console(400))


def test_refusal_does_not_overlay_an_accepted_attempt_already_in_the_log(
    browser, serve
):
    """Acceptance may be known while a failed commit keeps the outbox hold. If
    later log events arrive before another refusal, the retained accepted attempt is
    replayed at its log sequence—not overlaid again as though it were newest."""
    page = open_page(browser, serve(BOARD_PAGE))

    def hold_read_state(route):
        if lifted:
            route.continue_()
            return
        if failed_reads or held_reads:
            refuse(route)
            return
        held_reads.append(route)

    def fail_event_commit(route):
        if route.request.post_data_json.get("kind") != "action":
            route.continue_()
            return
        response = route.fetch()
        answer = response.json()
        fail_reading_commit(
            page, answer["state"]["reading"], "injected chronology event commit fault"
        )
        route.fulfill(status=response.status, json=answer)

    failed_reads = []
    held_reads = []
    lifted = False
    page.route("**/api/state*", hold_read_state)
    page.route("**/api/event", fail_event_commit)
    heater = page.locator("#card-heater .lf-grip")
    # The event answer fails its required commit. The read the append prompts
    # is held meanwhile, so this report can only be the answer's.
    with page.expect_console_message(
        lambda message: (
            message.type == "error"
            and "injected chronology event commit fault" in message.text
        )
    ) as event_failure:
        heater.focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    round_trip(page)
    retained = page.evaluate("""async () => {
      const root = (await window.__lfCheckApi()).readApplication();
      return root.unresolved.filter(entry => entry.event.kind === 'action');
    }""")
    assert len(retained) == 1, retained
    assert retained[0]["admitted"]["id"] == actions(serve.page_dir)[0]["id"]
    # Fail that read's required commit too, here rather than on a later timer.
    holding(page, held_reads, 1, "the read the move's append prompts")
    held = held_reads.pop()
    response = held.fetch()
    state = response.json()
    fail_reading_commit(page, state["reading"], "injected chronology read commit fault")
    failed_reads.append(True)
    with page.expect_console_message(
        lambda message: (
            message.type == "error"
            and "injected chronology read commit fault" in message.text
        )
    ) as read_failure:
        held.fulfill(status=response.status, json=state)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)
    page.unroute("**/api/event")

    with page.expect_request("**/api/state*"):
        append_command(
            serve.page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "sprint",
                "action": "move",
                "detail": {"unit": "card-baffle", "value": "col-done", "rank": "0i"},
            },
        )

    refused = []

    def refuse_move(route):
        body = route.request.post_data_json or {}
        if body.get("kind") != "action":
            route.continue_()
            return
        attempt = body["attempt"]
        refused.append(attempt)
        route.fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )

    page.route("**/api/event", refuse_move)
    with page.expect_response(
        lambda response: (
            "/api/event" in response.url
            and (response.request.post_data_json or {}).get("kind") == "action"
        )
    ):
        heater.focus()
        for key in ["Enter", "ArrowLeft", "Enter"]:
            page.keyboard.press(key)
    assert len(refused) == 1
    # Neither failed commit retires the accepted attempt. The accepted
    # baffle move remains held until a complete read can place it in chronology.
    expect(page.locator("#col-done #card-baffle")).to_have_count(0)
    lifted = True
    with page.expect_response(
        lambda response: "/api/state" in response.url and response.ok
    ):
        nudge(serve.page_dir)
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)

    assert page.eval_on_selector_all(
        "#col-done > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-baffle", "card-heater"]
    assert [event["detail"]["unit"] for event in actions(serve.page_dir)] == [
        "card-heater",
        "card-baffle",
    ]
    errors = consume_browser_errors(
        page,
        "injected chronology event commit fault",
        "injected chronology read commit fault",
        http_error_console(400),
    )
    assert [
        error for error in errors if not is_problem(error, http_error_console(400))
    ] == [
        console_finding(event_failure.value),
        console_finding(read_failure.value),
    ], errors


def test_accounting_an_action_projects_newer_same_widget_news_before_release(
    browser, serve
):
    """A complete poll can account for held A while also carrying newer B. Replay
    skips the widget under A's outbox hold; releasing A must project A+B before that
    hold disappears, or the page offers its next gesture against stale optimistic A."""
    page = open_page(browser, serve(BOARD_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    heater = page.locator("#card-heater .lf-grip")
    with page.expect_request("**/api/event"):
        heater.focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    holding(page, held, 1, "the accounted action")
    assert len(held) == 1
    # Reads held until B is appended, so one complete state carries A and B: the
    # stream would otherwise have the page read A alone in the time B takes.
    cut = CutOff().hold(page)
    older_answer = held[0].fetch()  # the server appends A; its response stays held
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sprint",
            "action": "move",
            "detail": {"unit": "card-baffle", "value": "col-done", "rank": "0i"},
        },
    )
    cut.restore()
    told(page)  # a complete state accounts A and projects A+B before release
    assert page.eval_on_selector_all(
        "#col-done > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-baffle", "card-heater"]
    undo_offered(page)
    cut.cut()

    with page.expect_response(lambda response: "/api/event" in response.url):
        held[0].fulfill(response=older_answer)
    page.title()  # let the stale response settle before reading the page again

    assert page.eval_on_selector_all(
        "#col-done > lf-card", "cards => cards.map(card => card.id)"
    ) == ["card-baffle", "card-heater"]
    undo_offered(page)
    assert [event["detail"]["unit"] for event in actions(serve.page_dir)] == [
        "card-heater",
        "card-baffle",
    ]


def test_accounting_an_action_also_applies_the_undo_that_arrived_with_it(
    browser, serve
):
    """A complete read may first reveal both optimistic A and another tab's undo of A.
    The outbox entry is no longer a hold against that same read: the withdrawal must
    restore authored state before accounting releases A, or the sender keeps showing a
    gesture the log and every fresh page have already taken back."""
    page = open_page(browser, serve(BOARD_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    heater = page.locator("#card-heater .lf-grip")
    with page.expect_request("**/api/event"):
        heater.focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    holding(page, held, 1, "the action later undone")
    assert len(held) == 1
    # Reads held until the undo is appended, so the first complete read reveals both.
    cut = CutOff().hold(page)
    accepted_answer = held[0].fetch()
    attempt = held[0].request.post_data_json["attempt"]
    accepted = next(
        event
        for event in accepted_answer.json()["state"]["events"]
        if event.get("attempt") == attempt
    )
    append_carried_log_record(
        serve.page_dir,
        {"kind": "undo", "author": "user", "undoes": accepted["id"]},
    )

    cut.restore()
    told(page)
    cut.cut()
    expect(page.locator("#col-todo #card-heater")).to_have_count(1)
    expect(page.locator("#col-done #card-heater")).to_have_count(0)
    undo_offered(page, offered=False)
    held[0].fulfill(response=accepted_answer)
    page.unroute("**/api/event")


@pytest.mark.parametrize(
    "source,control",
    [
        (BOARD_PAGE, "#card-heater .lf-grip"),
        (
            SUGGESTION_PAGE,
            (
                '[data-lf-margin-entry-owner="suggestion:sug-refill"]'
                '[data-lf-margin-entry-key="accept"]:visible'
            ),
        ),
    ],
)
def test_widget_actions_wait_for_the_first_complete_read(
    browser, serve, source, control
):
    """A widget cannot decide from authored state alone while history is unavailable."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.lf_traffic = Traffic(page)
    cut = CutOff().hold(page)
    page.goto(serve(source), wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    page.wait_for_function(
        "() => document.body.getAttribute('data-lf-presented') === '1'"
    )
    action = page.locator(control)
    expect(action).to_have_attribute("aria-disabled", "true")

    cut.restore()
    told(page)
    expect(action).not_to_have_attribute("aria-disabled", "true")


def test_a_complete_read_does_not_repaint_an_already_undone_settlement(browser, serve):
    """An optimistic record-less decision still yields to the next complete read.
    If that read contains both the decision and its undo, replay leaves authored markup
    in place. The send continuation must not repaint the withdrawn decision after that
    authoritative read has released it. The live region can retain the admitted
    decision's announcement, so read the suggestion and undo offer themselves.

    A decision waits for the page's first complete read (module-authoring.md,
    "Startup and presentation"), so that read is let through and every later one is
    held until the undo is in the log."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.lf_traffic = Traffic(page)
    cut = CutOff(lets_through=1).hold(page)
    page.goto(serve(SUGGESTION_PAGE), wait_until="load")
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
    page.wait_for_function(
        "() => document.body.getAttribute('data-lf-presented') === '1'"
    )
    accept = suggestion_control(page, "sug-refill", "accept")
    expect(accept).not_to_have_attribute("aria-disabled", "true")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        accept.click()
    holding(page, held, 1, "the suggestion settlement")
    accepted_answer = held[0].fetch()
    attempt = held[0].request.post_data_json["attempt"]
    accepted = next(
        event
        for event in accepted_answer.json()["state"]["events"]
        if event.get("attempt") == attempt
    )
    append_carried_log_record(
        serve.page_dir,
        {"kind": "undo", "author": "user", "undoes": accepted["id"]},
    )

    cut.restore()
    told(page)
    cut.cut()
    expect(page.locator("#sug-refill")).not_to_have_attribute("aria-busy", "true")
    expect(page.locator("#sug-refill")).not_to_have_attribute("data-lf-state", "accept")
    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    undo_offered(page, offered=False)
    held[0].fulfill(response=accepted_answer)
    round_trip(page)
    rendered(page)
    assert page.locator("#sug-refill").get_attribute("data-lf-state") != "accept"
    assert page.locator("#sug-refill lf-old").is_visible()
    undo_offered(page, offered=False)
    page.unroute("**/api/event")


def test_an_older_settlement_cannot_repaint_over_a_newer_decision(browser, serve):
    """A later record-less action on the same declared unit supersedes the first.
    When one complete read accounts the held accept and also replays another tab's
    reject, the older send's answer must not paint accept over that chronology. The
    press announced the accept when it was made, so what the page says isn't read."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        suggestion_control(page, "sug-refill", "accept").click()
    holding(page, held, 1, "the accepted suggestion")
    # Append the accept while its browser response remains held, with the page's
    # reads held too, so one complete read accounts the accept and replays the reject.
    cut = CutOff().hold(page)
    accepted_answer = held[0].fetch()
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-refill",
            "action": "decide",
            "detail": {"outcome": "reject"},
        },
    )

    cut.restore()
    told(page)
    cut.cut()
    expect(page.locator("#sug-refill")).not_to_have_attribute("aria-busy", "true")
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "reject")
    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    expect(page.locator("#sug-refill lf-new")).to_be_hidden()
    assert [
        (event["widget"], event["detail"].get("outcome", event["action"]))
        for event in actions(serve.page_dir)
    ] == [
        ("sug-refill", "accept"),
        ("sug-refill", "reject"),
    ]
    held[0].fulfill(response=accepted_answer)
    round_trip(page)
    rendered(page)
    assert page.locator("#sug-refill").get_attribute("data-lf-state") == "reject"
    assert page.locator("#sug-refill lf-new").is_hidden()
    page.unroute("**/api/event")


def test_a_server_that_cannot_take_a_gesture_yet_says_so_and_keeps_it(browser, serve):
    """`503` is a wait the user is told about, not an answer the page could not read.

    leaf.page's edge refuses every event with `503` and a plain-text body for the
    minutes a container image takes to reach a user's allocation, and the outbox has
    always retried through it. What it said meanwhile came from the JSON decode that
    body fails, which reports the page failing to read an answer the server never sent.
    """
    page = open_page(browser, serve(BOARD_PAGE))
    starting = {"rollout": True}
    refused = []

    def still_starting(route):
        if not starting["rollout"]:
            route.continue_()
            return
        refused.append(route.request.post_data_json["attempt"])
        route.fulfill(
            status=503,
            body="this release is still starting",
            headers={"Retry-After": "5", "Content-Type": "text/plain;charset=UTF-8"},
        )

    page.route("**/api/event", still_starting)
    page.locator("#card-baffle .lf-grip").focus()
    for key in ["Enter", "ArrowRight", "Enter"]:
        page.keyboard.press(key)
    holding(page, refused, 2, "the move the rollout would not take")
    expect_panel_says(page, "Not through yet")
    # The same gesture throughout: a refusal that admits nothing cannot mint a second.
    assert len(set(refused)) == 1

    starting["rollout"] = False
    round_trip(page)
    page.unroute("**/api/event")
    assert [event["detail"]["unit"] for event in actions(serve.page_dir)] == [
        "card-baffle"
    ]
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    consume_browser_errors(page, http_error_console(503))


def test_poll_proven_acceptance_advances_past_a_hung_post_response(browser, serve):
    """A complete read containing an attempt is authoritative delivery evidence. Once
    it accounts for A, the ordered outbox may send queued B even if A's original browser
    response never finishes; the server append A was already observed before B starts."""
    page = open_page(browser, serve(BOARD_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    with page.expect_request("**/api/event"):
        page.locator("#card-baffle .lf-grip").focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    holding(page, held, 1, "the first ordered action")
    assert len(held) == 1
    first_attempt = held[0].request.post_data_json["attempt"]

    # B, queued behind A: the outbox is ordered, and A has not been answered.
    page.locator("#card-heater .lf-grip").focus()
    for key in ["Enter", "ArrowRight", "Enter"]:
        page.keyboard.press(key)
    with page.expect_request(
        lambda request: (
            "/api/event" in request.url
            and request.post_data_json.get("attempt") != first_attempt
        )
    ):
        # Append A on the server and leave its browser response unresolved. The
        # stream tells the page the log moved, the read that prompts accounts for A,
        # and B goes out — within the stream's look, so the listener has to be armed
        # before the append rather than after it.
        first_answer = held[0].fetch()
    holding(page, held, 2, "the second ordered action")

    assert len(held) == 2
    held[0].fulfill(response=first_answer)  # cleanup after B has proved release
    with page.expect_response(
        lambda response: (
            "/api/event" in response.url
            and response.request.post_data_json.get("attempt") != first_attempt
        )
    ):
        held[1].continue_()
    page.unroute("**/api/event")

    assert [event["detail"]["unit"] for event in actions(serve.page_dir)] == [
        "card-baffle",
        "card-heater",
    ]
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)


def test_a_refused_action_waits_for_a_live_gesture_before_reconciling(browser, serve):
    """A board grab owns its captured origin until release. A refusal arriving under
    that grab must remain in the outbox, then reconcile after Escape, or the cancel can
    resurrect the move the server refused."""
    page = open_page(browser, serve(BOARD_PAGE))
    page.route("**/api/state*", refuse)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    baffle = page.locator("#card-baffle .lf-grip")
    with page.expect_request("**/api/event"):
        baffle.focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    holding(page, held, 1, "the refused action")

    baffle.focus()
    page.keyboard.press("Enter")
    wait_for_check_api(page, "(api) => api.dragHeld()")
    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    round_trip(page)

    # The live gesture still owns the DOM; its origin must not move under it.
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    expect(page.locator('[data-lf-behavior="status"]')).to_have_count(0)
    page.keyboard.press("Escape")
    expect(page.locator("#col-todo #card-baffle")).to_have_count(1)
    assert actions(serve.page_dir) == []
    consume_browser_errors(page, http_error_console(400))


def test_a_lost_accepted_response_keeps_later_gestures_in_order(browser, serve):
    """The outbox retries an accepted gesture whose response was lost before it
    sends the next gesture. Both arrive once, in the order the user made them."""
    page = open_page(browser, serve(BOARD_PAGE))
    requests = []
    accepted = []

    def lose_first_answer(route):
        requests.append(route.request.post_data_json)
        if len(requests) == 1:
            accepted.append(route.fetch().status)
            refuse(route)
        else:
            route.continue_()

    page.route("**/api/state*", refuse)
    page.route("**/api/event", lose_first_answer)
    with page.expect_event(
        "requestfailed", predicate=lambda request: "/api/event" in request.url
    ):
        page.locator("#card-baffle .lf-grip").focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)

    first_attempt = requests[0]["attempt"]
    with page.expect_request(
        lambda request: (
            "/api/event" in request.url
            and request.post_data_json.get("attempt") != first_attempt
        )
    ):
        page.locator("#card-heater .lf-grip").focus()
        for key in ["Enter", "ArrowRight", "Enter"]:
            page.keyboard.press(key)
    round_trip(page)

    assert accepted == [200]
    assert [request["detail"]["unit"] for request in requests] == [
        "card-baffle",
        "card-baffle",
        "card-heater",
    ]
    assert requests[0]["attempt"] == requests[1]["attempt"]
    assert requests[2]["attempt"] != first_attempt
    assert [event["detail"]["unit"] for event in actions(serve.page_dir)] == [
        "card-baffle",
        "card-heater",
    ]
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)

    undo(page)
    expect(page.locator("#col-done #card-baffle")).to_have_count(1)
    expect(page.locator("#col-todo #card-heater")).to_have_count(1)


def test_a_refused_draft_keeps_newer_authoritative_words_under_its_editor(
    browser, serve
):
    """The centralized projector runs before a refused send resolves. A draft caller
    may reopen the unsent text, but must not restore its stale pre-send body over a newer
    remote edit the projector just applied and marked complete."""
    page = open_page(browser, serve(UNDO_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    draft = page.locator("#note-cli")
    with page.expect_request("**/api/event"):
        draft_control(page, "edit", "note-cli").click()
        write(draft.locator("leaf-text"), "Local C")
        page.keyboard.press("Meta+Enter")
    holding(page, held, 1, "the refused draft")
    expect(draft.locator(".lf-draft-body")).to_have_text("Local C")

    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "note-cli",
            "action": "edit",
            "detail": {"value": "Remote B"},
        },
    )
    told(page)
    expect(draft.locator(".lf-draft-body")).to_have_text("Local C")
    page.route("**/api/state*", refuse)

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held[0].fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    round_trip(page)

    expect(draft.locator("leaf-text")).to_have_js_property("value", "Local C")
    expect(draft.locator(".lf-draft-body")).to_have_text("Remote B")
    page.keyboard.press("Escape")
    expect(draft.locator("leaf-text")).to_have_count(0)
    expect(draft.locator(".lf-draft-body")).to_have_text("Remote B")
    assert [event["detail"]["value"] for event in actions(serve.page_dir)] == [
        "Remote B"
    ]
    consume_browser_errors(page, http_error_console(400))


def test_a_draft_commit_stages_before_deferred_projection_retries(browser, serve):
    """Closing a deferred editor must let its commit stage before replay runs.

    A remote edit received while the editor is open defers the authoritative projection.
    Commit closes the editor before it enters the outbox; the close notification therefore
    has to wait one microtask, or replay paints the remote words over the new optimistic
    body before the outbox can install its local winner.
    """
    page = open_page(browser, serve(UNDO_PAGE))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    draft = page.locator("#note-cli")
    draft_control(page, "edit", "note-cli").click()
    write(draft.locator("leaf-text"), "Local C")

    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "note-cli",
            "action": "edit",
            "detail": {"value": "Remote B"},
        },
    )
    told(page)
    expect(draft.locator("leaf-text")).to_have_js_property("value", "Local C")

    page.keyboard.press("Meta+Enter")
    holding(page, held, 1, "the draft commit")
    expect(draft.locator(".lf-draft-body")).to_have_text("Local C")
    assert len(held) == 1

    held[0].continue_()
    round_trip(page)
    expect(draft.locator(".lf-draft-body")).to_have_text("Local C")
    assert [event["detail"]["value"] for event in actions(serve.page_dir)] == [
        "Remote B",
        "Local C",
    ]


def test_z_walks_back_through_gestures_rather_than_toggling_one(browser, serve):
    """The walk steps past what it has already taken and reaches the gesture before
    it — the edit here, whose authored text comes back with its paragraphs, where
    the state a comparison reads is collapsed. That is what withdrawing buys over
    stating a counter-gesture: a second press would otherwise land on a statement
    the first press had just made and put the user back where they started."""
    page = open_page(browser, serve(UNDO_PAGE))
    body = page.locator("lf-draft .lf-draft-body")
    authored = body.inner_text()
    assert "\n\n" in authored

    draft_control(page, "edit", "note-cli").click()
    write(page.locator("lf-draft leaf-text"), "Rewritten.")
    page.keyboard.press("Meta+Enter")
    round_trip(page)
    expect(body).to_have_text("Rewritten.")
    page.locator("#opt-a").click()
    round_trip(page)
    expect(page.locator("lf-option[chosen]")).to_have_attribute("id", "opt-a")

    undo(page)
    expect(page.locator("lf-option[chosen]")).to_have_attribute("id", "opt-b")
    undo(page)
    # The arrival first, read the way every assertion after a trip reads it, and then
    # the reading a retry cannot make: `to_have_text` collapses the blank line, which
    # is the very thing the authored text is here to bring back.
    expect(body).to_have_text(authored)
    assert body.inner_text() == authored
    # Two gestures and two words taking them back, newest first: nothing in the log
    # claims the user chose opt-b or typed the authored draft, because they did
    # neither — the page derived both from what still stands.
    log = events_model.read_events(serve.page_dir)
    edit, choose = actions(serve.page_dir)
    assert [(e["action"], e["detail"]) for e in (edit, choose)] == [
        ("edit", {"value": "Rewritten."}),
        ("choose", {"value": ["opt-a"]}),
    ]
    assert [e["undoes"] for e in log if e["kind"] == "undo"] == [
        choose["id"],
        edit["id"],
    ]


@pytest.mark.parametrize(
    "refusal_first", [True, False], ids=["refusal-first", "poll-first"]
)
def test_an_undo_reveals_the_prior_winner_before_its_send_finishes(
    browser, serve, refusal_first
):
    """Optimistic withdrawal re-folds the coordinate instead of deleting its current
    value. Another tab can withdraw that same action before this send reaches the
    server: the refusal must carry its truth, even while all polls remain held.
    """
    page = open_page(browser, serve(UNDO_PAGE))
    page.locator("#opt-a").click()
    round_trip(page)
    page.locator("#opt-b").click()
    round_trip(page)
    expect(page.locator("lf-option[chosen]")).to_have_attribute("id", "opt-b")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    cut = CutOff().hold(page)
    with page.expect_request("**/api/event"):
        page.keyboard.press("z")
    expect(page.locator("lf-option[chosen]")).to_have_attribute("id", "opt-a")
    holding(page, held, 1, "the optimistic withdrawal")
    other_undo = append_command(
        serve.page_dir,
        {"kind": "undo", "author": "user", "undoes": actions(serve.page_dir)[-1]["id"]},
    )
    response = held[0].fetch()
    refusal = response.json()
    assert response.status == 400 and refused_on(refusal).code == "withdrawn-gesture"
    assert other_undo in refusal["state"]["events"]
    if not refusal_first:
        cut.restore()
        told(page)
        cut.cut()
        assert (
            page.evaluate("""async () => {
          const {readApplication} = await window.__lfCheckApi();
          return readApplication().authoritative.taken;
        }""")
            > refusal["state"]["taken"]
        )
    page.evaluate("""async () => {
      const {watchSemantic} = await window.__lfCheckApi();
      const widget = document.querySelector('#opt-a').closest('lf-options').id;
      window.refusalValues = [];
      watchSemantic(root => {
        window.refusalValues.push(root.effective.widgets.get(widget).state.choose.value);
      });
    }""")
    held[0].fulfill(response=response)
    page.unroute("**/api/event")
    round_trip(page)

    expect(page.locator("lf-option[chosen]")).to_have_attribute("id", "opt-a")
    values = page.evaluate("window.refusalValues")
    assert len(values) > 1 and all(value == ["opt-a"] for value in values), values
    consume_browser_errors(page, http_error_console(400))
    cut.restore()


def test_z_returns_a_recordless_decision_to_undecided(browser, serve):
    """Withdrawing an accept renders the null decision. The same suggestion
    regains its old passage and decision controls without replacing its subtree."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    old = page.locator("#sug-refill lf-old")
    accept = suggestion_control(page, "sug-refill", "accept")
    expect(old).to_be_visible()
    expect_obligations_answered(page, "0/3")

    accept.click()
    round_trip(page)
    expect(old).to_be_hidden()
    expect_obligations_answered(page, "1/3")

    undo(page)
    # Pending again, in every reading of it: the retired half is back on the page,
    # the control offers the decision rather than recording it, and the page
    # counts the question among the ones still waiting on the user.
    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    expect(suggestion_control(page, "sug-refill", "accept")).to_have_attribute(
        "aria-label", re.compile(r"^Accept the suggested change")
    )
    expect_obligations_answered(page, "0/3")
    assert suggestion_control(page, "sug-refill", "accept").count() == 1, (
        "undo left more than one Accept record for the same suggestion"
    )
    (accepted,) = actions(serve.page_dir)
    assert accepted["detail"] == {"outcome": "accept"}
    assert [
        e["undoes"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "undo"
    ] == [accepted["id"]]


def test_undo_preserves_the_place_and_restores_passage_marks(browser, serve):
    """Undo restores a suggestion's passages and their anchored comment marks, and returns focus to the available decision control."""
    url = serve(SUGGESTION_PAGE)
    page = open_page(browser, url)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "this one matters",
            "anchor": {"quote": "Refill every feeder each morning."},
        },
    )
    # Parenthesised, because `??` binds looser than a comparison: written
    # `size ?? 0 === 0` the predicate is `size ?? true`, which is 0 — falsy — exactly
    # when the assertion is meant to hold, and the wait runs its timeout out on a
    # page that is doing the right thing.
    marks = "() => (CSS.highlights.get('lf-mark')?.size ?? 0)"
    page.wait_for_function(f"{marks} > 0")

    accept = suggestion_control(page, "sug-refill", "accept")
    accept.click()
    round_trip(page)
    # The sentence left the page with the decision, so the mark goes with it.
    page.wait_for_function(f"{marks} === 0")
    expect(suggestion_control(page, "sug-refill", "undo")).to_be_focused()

    undo(page)
    page.wait_for_function(f"{marks} === 1")
    expect(suggestion_control(page, "sug-refill", "accept")).to_be_focused()


def test_a_held_suggestion_delivery_does_not_reclaim_focus(held_events, serve):
    """The replacement keeps the press's place immediately, not after delivery.

    Once the user moves elsewhere, the eventual admission cannot pull them back to the
    Undo control that replaced the decision they pressed.
    """
    browser, held = held_events
    page = open_page(browser, serve(SUGGESTION_PAGE))

    suggestion_control(page, "sug-refill", "accept").click()
    holding(page, held, 1, "the accepted suggestion")
    expect(suggestion_control(page, "sug-refill", "undo")).to_be_focused()

    elsewhere = page.locator(".lf-fp-on-user")
    elsewhere.focus()
    held.pop(0).continue_()
    round_trip(page)
    expect(elsewhere).to_be_focused()


def test_undo_leaves_a_user_located_elsewhere_where_they_are(browser, serve):
    """Undo from elsewhere changes the decision without moving the user's focus."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    suggestion_control(page, "sug-refill", "accept").click()
    round_trip(page)
    page.evaluate(RELEASE_FOCUS)

    undo(page)
    expect(page.locator("#sug-refill lf-old")).to_be_visible()
    assert page.evaluate("() => document.activeElement === document.body")


def test_a_withdrawal_waits_for_a_widget_that_cannot_take_it_yet(browser, serve):
    """The withdrawal pass has to keep the discipline the replay loop keeps, because
    it is replay: a widget the page has painted ahead of the log gets the next poll
    rather than being written over. `lf-draft` says so outright — it defers its
    presentation while an editor stands, so the user's unsent words are not yanked
    out from under them — and a pass that drops that answer and marks the withdrawal
    answered leaves the tab holding the withdrawn text for the rest of its life, with
    the user-origin reading cleared because the fold agrees the edit is gone. A reload
    would show the authored words; this tab never would again."""
    url = serve(UNDO_PAGE)
    one = open_page(browser, url)
    two = open_page(browser, url)
    body = "lf-draft .lf-draft-body"
    authored = one.locator(body).inner_text()

    draft_control(one, "edit", "note-cli").click()
    write(one.locator("lf-draft leaf-text"), "Rewritten.")
    one.keyboard.press("Meta+Enter")
    round_trip(one)
    expect(two.locator(body)).to_have_text("Rewritten.")

    # The second tab is now holding words of its own, so the log may not write over it.
    draft_control(two, "edit", "note-cli").click()
    expect(two.locator("lf-draft leaf-text")).to_be_focused()
    undo(one)
    expect(one.locator(body)).to_have_text(authored)

    # The withdrawal has to reach the second tab *while* its editor stands — heard
    # after the box closes, it applies on the way past and says nothing about the
    # hold. told() consumes the poll that carries it.
    told(two)
    expect(two.locator(body)).to_have_text("Rewritten.")

    # Let go, and the withdrawal it could not take yet lands from the editor's close.
    two.keyboard.press("Escape")
    expect(two.locator("lf-draft leaf-text")).to_have_count(0)
    assert two.locator(body).inner_text() == authored


def test_a_withdrawal_is_heard_by_a_tab_reading_a_later_version(browser, serve):
    """Which version a gesture was made against decides whether `z` is *offered*, and
    says nothing about whether an undo must be *heard*. A tab holding an older version
    can still take back its gesture — `?pin` is a URL a user keeps, and a tab
    mid-composition holds its version too — so its undo reaches a tab that has moved
    on, and that tab applied the action being withdrawn (replay takes every action up
    to the version it reads).

    Refusing to hear it there leaves the newer tab showing a gesture the log no longer
    holds, and only until someone reloads it. A pick is the case: a later version may
    leave it to the log, where a later version writes a move in and places the card
    itself, so a move is no longer the user's to take back."""
    url = serve(REPLAYED_PAGE)
    pinned = open_page(browser, url + "&pin")
    moved_on = open_page(browser, live_url(url))

    pinned.locator("#opt-shim").click()
    round_trip(pinned)
    expect(moved_on.locator("lf-option[chosen]")).to_have_attribute("id", "opt-shim")

    stamp_page(serve.page_dir, REPLAYED_PAGE, "unchanged")
    wait_for_revision(moved_on, 2)
    expect(moved_on).not_to_have_url(re.compile("/versions/"))
    expect(pinned).to_have_url(re.compile("v1"))
    # Replay carries the v1 pick onto v2, so this tab is showing it.
    expect(moved_on.locator("lf-option[chosen]")).to_have_attribute("id", "opt-shim")

    undo(pinned)
    told(moved_on)
    told(moved_on)
    expect(moved_on.locator("lf-option[chosen]")).to_have_count(0)


def test_a_move_on_a_version_a_newer_one_replaced_is_refused_and_restored(
    browser, serve
):
    """A move's rank lies among the cards of the version it was made on. A tab still
    holding v1 after v2 added a card to the destination column sees its move refused
    in words meant for it, and the card back where it stood; the log keeps nothing."""
    url = serve(BOARD_PAGE)
    pinned = open_page(browser, url + "&pin")
    stamp_page(
        serve.page_dir,
        BOARD_PAGE.replace(
            '<lf-column id="col-done" label="Done"></lf-column>',
            '<lf-column id="col-done" label="Done">'
            '<lf-card id="card-feeder"><strong>Feeder</strong></lf-card></lf-column>',
        ),
        "v2",
    )
    expect(pinned).to_have_url(re.compile("v1"))

    pinned.locator("#card-baffle .lf-grip").focus()
    with pinned.expect_response(
        lambda response: "/api/event" in response.url and response.status == 400
    ) as refused:
        for key in ["Enter", "ArrowRight", "Enter"]:
            pinned.keyboard.press(key)
    assert refused.value.json()["error"] == (
        "The page changed while I moved this; move it again."
    )
    round_trip(pinned)
    expect(pinned.locator("#col-todo #card-baffle")).to_have_count(1)
    assert actions(serve.page_dir) == []
    consume_browser_errors(pinned, http_error_console(400))


def test_a_second_tab_takes_the_decision_back_too(browser, serve):
    """A second tab receives the withdrawal from the log, restores the pending suggestion, and lets the user decide again."""
    url = serve(SUGGESTION_PAGE)
    one = open_page(browser, url)
    two = open_page(browser, url)
    marks = """(id) => Object.fromEntries(['lf-sug-del', 'lf-sug-ins'].map(name =>
        [name, [...(CSS.highlights.get(name) ?? [])]
            .filter(r => document.getElementById(id).contains(r.startContainer))
            .length]))"""
    pending = one.evaluate(marks, "sug-refill")
    assert pending["lf-sug-del"] and pending["lf-sug-ins"]

    suggestion_control(one, "sug-refill", "accept").click()
    round_trip(one)
    expect(two.locator("#sug-refill lf-old")).to_be_hidden()

    undo(one)
    expect(two.locator("#sug-refill lf-old")).to_be_visible()
    expect_obligations_answered(two, "0/3")
    # Everything the change had when it was pending, including what the theme paints
    # from ranges the module registers — a rebuild that dropped those would leave a
    # proposal on the page with nothing marking what it changes.
    assert one.evaluate(marks, "sug-refill") == pending
    assert (
        one.evaluate(
            "() => document.querySelectorAll('[data-lf-user-override]').length"
        )
        == 0
    )

    unfolded_button(
        suggestion_control(two, "sug-refill", "reject", visible=False)
    ).click()
    round_trip(two)
    expect(one.locator("#sug-refill lf-new")).to_be_hidden()
    assert [
        e["detail"]["outcome"] if e["kind"] == "action" else e["kind"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] in ("action", "undo")
    ] == ["accept", "undo", "reject"]


def test_undo_preserves_the_independent_decision_inside_a_change(browser, serve):
    """Undoing an outer suggestion preserves the nested widget, its selected option, and the user's independent decision."""
    page = open_page(browser, serve(NESTED_SUGGESTION))
    original = page.locator("#sug-thistle lf-options").element_handle()
    page.locator("#blend-mixed").click()
    round_trip(page)
    expect(page.locator("lf-option[chosen]")).to_have_attribute("id", "blend-mixed")

    suggestion_control(page, "sug-thistle", "accept").click()
    round_trip(page)
    undo(page)

    expect(page.locator("#sug-thistle lf-old, #sug-thistle lf-new")).to_have_count(1)
    expect(suggestion_control(page, "sug-thistle", "accept")).to_have_attribute(
        "aria-label", re.compile(r"^Accept the suggested change")
    )
    assert original.evaluate(
        "node => node === document.querySelector('#sug-thistle lf-options')"
    )
    expect(page.locator("lf-option[chosen]")).to_have_attribute("id", "blend-mixed")


def test_a_withdrawn_decision_is_still_withdrawn_after_a_reload(browser, serve):
    """A page loaded after an undo renders the same undecided state as a page that received the withdrawal live."""
    url = serve(SUGGESTION_PAGE)
    page = open_page(browser, url)
    suggestion_control(page, "sug-refill", "accept").click()
    round_trip(page)
    undo(page)
    page.close()

    again = open_page(browser, url)
    expect(again.locator("#sug-refill lf-old")).to_be_visible()
    expect_obligations_answered(again, "0/3")


def test_the_composer_never_stands_on_its_own_mark(browser, serve):
    """The mark is the only thing naming the passage the box is about, so a box covering
    all of it is a box about nothing. That is not hypothetical: a restored draft reappears
    near the window's head, and the reading position puts the passage it was made on back
    where it was — which, for a passage that was near the top of a narrow column, is
    exactly there. The box has to move off it.

    Not off every pixel of it. The box has always covered the tail of a long passage and
    that reads fine; what may not happen is every rect hidden at once."""
    filler = "\n".join(
        f"<p id='f{i}'>Filler {i}. " + "Words. " * 20 + "</p>" for i in range(30)
    )
    url = serve(SETTLED_PAGE.replace("</main>", filler + "\n</main>"))
    page = open_page(browser, url)

    page.locator(".lf-settled").click()  # open the settled group, as a user would
    page.wait_for_selector("#opt-strict:visible")
    # A card in the middle column, scrolled near the window's head: narrower than the 320px
    # box and centred on it, which is the geometry the box can swallow whole.
    page.evaluate("""() => {
        const r = document.querySelector('#opt-strict').getBoundingClientRect();
        document.scrollingElement.scrollBy({top: r.top - 60, behavior: 'instant'});
    }""")
    page.locator("#opt-strict").click(click_count=3)
    page.locator(".lf-fab-input").click()
    write(page.locator(".lf-composer leaf-text"), "what did the trial actually show?")
    assert mark_shows_beside_composer(page), (
        "the box covered the passage it just opened on"
    )

    page.reload()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer')?.hasAttribute('data-lf-open')"
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-pending')?.size ?? 0) > 0")
    assert mark_shows_beside_composer(page), (
        "the restored box came back on top of its own mark, and with the mark hidden "
        "nothing on screen says what the draft is about"
    )
    assert not composer_quote(page)["shown"], (
        "the mark is showing and the composer prints the passage as well"
    )


def test_the_comment_field_follows_its_passage_out_of_view(browser, serve):
    """The same native field follows its passage, including beyond the window."""
    page = open_page(browser, serve(LONG_PAGE))
    page.locator("#p30").scroll_into_view_if_needed()
    page.locator("#p30").click(click_count=3)
    page.wait_for_selector(".lf-fab-input", state="visible")
    page.locator(".lf-fab-input").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    before = page.evaluate("""() => {
        const top = (el) => el.getBoundingClientRect().top;
        const composer = document.querySelector('.lf-fab-bar');
        const passage = document.getElementById('p30');
        const before = { composer: top(composer), passage: top(passage) };
        document.scrollingElement.scrollTop += 80;
        return before;
    }""")
    page.wait_for_function(
        """before => {
          const composer = document.querySelector('.lf-fab-bar').getBoundingClientRect().top;
          const passage = document.getElementById('p30').getBoundingClientRect().top;
          return passage < before.passage
            && composer - before.composer === passage - before.passage;
        }""",
        arg=before,
    )
    page.evaluate("document.scrollingElement.scrollTop += 2 * innerHeight")
    page.wait_for_function(
        "() => document.getElementById('p30').getBoundingClientRect().bottom < 0"
    )
    rendered(page)
    expect(page.locator(".lf-fab-bar")).to_have_attribute("data-lf-plane", "page")
    expect(page.locator(".lf-fab-input")).to_be_focused()


PANED_LONG_PAGE = leaf_page(
    "paned long",
    """<header><h1 id="t">Paned</h1></header>
<lf-pane id="reading" label="Reading"><div id="reading-body">{paras}</div></lf-pane>
""".format(
        paras="\n".join(
            f"<p id='p{i}'>Paragraph {i}. " + "Filler. " * 20 + "</p>"
            for i in range(60)
        )
    ),
    layout="workspace",
)


# The item field is the one that used to retire; the passage field rides the pane.
@pytest.mark.parametrize(
    ("target", "scroller"), [("item", "page"), ("passage", "pane")]
)
def test_a_comment_field_scrolled_away_and_back_is_still_there(
    browser, serve, target, scroller
):
    """Scrolling away from a comment and back returns to the field as the user left
    it: standing beside its target, with their words and their caret in it. Geometry
    says where the field stands, never whether: an item's field used to read "the
    target is off screen" as "the target is gone" and put the field away, words and
    all, the moment its item left the window. The field now follows out of view
    without retiring its draft; on return it stands beside the target."""
    page = open_page(
        browser, serve(LONG_PAGE if scroller == "page" else PANED_LONG_PAGE)
    )
    resized(page, 1440, 900)
    if scroller == "pane":
        pane_scroll_behavior(page, page.locator("#reading"), "bounded")
    paragraph = page.locator("#p30")
    paragraph.scroll_into_view_if_needed()
    if target == "passage":
        paragraph.click(click_count=3)
        page.locator(".lf-fab-input").click()
    else:
        paragraph.click(modifiers=["Alt"])
    field = page.locator(".lf-fab-input")
    write(field, "Half a thought")
    expect(field).to_be_focused()
    rendered(page)
    box = page.locator(".lf-fab-bar")
    # Where the field stands is read against its target: the scroll offset that brings
    # the target back is not the one read here once anything above it reflows, which
    # scroll anchoring then absorbs.
    beside = """box => box.getBoundingClientRect().top
      - document.getElementById('p30').getBoundingClientRect().top"""
    at = box.evaluate(beside)
    away = (
        "document.scrollingElement"
        if scroller == "page"
        else "document.getElementById('reading-body')"
    )
    start = page.evaluate(f"{away}.scrollTop")
    page.evaluate(f"{away}.scrollBy({{top: 2000, behavior: 'instant'}})")
    page.wait_for_function(
        "() => document.getElementById('p30').getBoundingClientRect().bottom < 0"
    )
    scroll_settled(page)
    rendered(page)
    expect(box).to_be_visible()
    expect(box).to_have_attribute("data-lf-plane", "page")
    away_box = box.bounding_box()
    assert away_box["y"] + away_box["height"] < 0, away_box
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "Half a thought")
    page.evaluate(f"{away}.scrollTo({{top: {start}, behavior: 'instant'}})")
    scroll_settled(page)
    rendered(page)
    expect(box).to_be_visible()
    expect(field).to_have_js_property("value", "Half a thought")
    expect(field).to_be_focused()
    assert box.evaluate(beside) == pytest.approx(at, abs=1), (
        "the field came back somewhere other than beside its target"
    )
    page.keyboard.type(" more")
    expect(field).to_have_js_property("value", "Half a thought more")


def test_a_comment_field_follows_when_its_pane_scrolls_past_the_target(browser, serve):
    """A bounded pane carries the field away while retaining its draft and caret."""
    page = open_page(browser, serve(PANED_LONG_PAGE))
    resized(page, 1440, 900)
    pane_scroll_behavior(page, page.locator("#reading"), "bounded")
    paragraph = page.locator("#p30")
    paragraph.scroll_into_view_if_needed()
    paragraph.click(modifiers=["Alt"])
    field = page.locator(".lf-fab-input")
    write(field, "Half a thought")
    box = page.locator(".lf-fab-bar")
    width = box.bounding_box()["width"]
    page.evaluate(
        "document.getElementById('reading-body')"
        ".scrollBy({top: 2000, behavior: 'instant'})"
    )
    scroll_settled(page, "#reading-body")
    rendered(page)
    expect(box).to_be_visible()
    expect(field).to_be_focused()
    expect(field).to_have_js_property("value", "Half a thought")
    expect(box).to_have_attribute("data-lf-plane", "page")
    away_box = box.bounding_box()
    assert away_box["y"] + away_box["height"] < 0, away_box
    assert box.bounding_box()["width"] == pytest.approx(width, abs=1)
    page.keyboard.type(" more")
    expect(field).to_have_js_property("value", "Half a thought more")


def test_the_comment_field_stands_in_the_margin_beside_the_passage(browser, serve):
    """Where the column leaves room, the field goes into the margin rather than onto
    somebody's words. The passage and its neighbours stay fully readable while the
    user writes about them.

    The window is wide enough for that room to be there wherever this runs. What the
    placement asks is whether the box and its two 8px gaps fit beside the column in
    body's client box, and that box is the window less whatever the platform spends on
    a scrollbar — nothing under macOS's overlay ones, 15px of gutter on the Linux
    runner. 1440 made the question exact rather than true: the margin fitted the box
    with nothing at all to spare where this was written, and fell 15px short where it
    ran, so a placement doing precisely what it should read as a bug."""
    page = open_page(browser, serve(LONG_PAGE))
    resized(page, 1600, 900)
    page.locator("#p30").scroll_into_view_if_needed()
    page.locator("#p30").click(click_count=3)
    page.wait_for_selector(".lf-fab-input", state="visible")
    page.locator(".lf-fab-input").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    placed = page.evaluate("""() => {
        const box = document.querySelector('.lf-fab-bar').getBoundingClientRect();
        const touching = [...document.querySelectorAll('main p, main h1')]
            .filter(el => el.checkVisibility())
            .filter(el => {
                const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
                for (let node = walk.nextNode(); node; node = walk.nextNode()) {
                    const range = document.createRange();
                    range.selectNodeContents(node);
                    if ([...range.getClientRects()].some(r =>
                        r.left < box.right && box.left < r.right
                        && r.top < box.bottom && box.top < r.bottom)) return true;
                }
                return false;
            })
            .map(el => el.id || el.tagName);
        return { touching };
    }""")
    assert placed["touching"] == [], (
        f"the box stands on the page's own text: {placed['touching']}"
    )


def test_opening_the_panel_stands_down_the_field_without_losing_its_draft(
    browser, serve
):
    """Opening Threads in the panel stands the compact field down, so its old absolute
    position cannot be left standing over the page. The words remain the passage's
    draft and return when the user selects that passage again."""
    page = open_page(browser, serve(LONG_PAGE))
    # Start with enough room for the field beside the passage; opening the panel then
    # changes the body's available right edge around that float.
    resized(page, 1600, 900)
    page.locator("#p30").scroll_into_view_if_needed()
    page.locator("#p30").click(click_count=3)
    page.wait_for_selector(".lf-fab-input", state="visible")
    page.locator(".lf-fab-input").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    write(page.locator(".lf-composer leaf-text"), "held open across the panel opening")
    # Opening the panel's Threads takes focus into the panel.
    open_threads(page)
    expect(page.locator(".lf-composer")).to_be_hidden()
    assert root_overflow(page) == 0

    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    page.locator("#p30").click(click_count=3)
    expect(page.locator(".lf-fab-input")).to_be_visible()
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    expect(page.locator(".lf-fab-input")).to_have_js_property(
        "value", "held open across the panel opening"
    )


def test_a_pointer_drag_stops_the_line_offering_the_press_it_refuses(browser, serve):
    """A held drag is half of the `z` liveness the runtime declares, and a pointer
    drag is a whole gesture rather than a frame: the focus paint lands on the
    mousedown, `fallbackTolerance` fires the drag's start after it, and on a quiet
    board nothing repaints between the pick-up and the drop. So unpainted, the line
    goes on offering `undo` for as long as the user holds the card, over a press the
    dispatcher is already refusing. The drop is the same gap read backwards: a card
    put down where it was picked up puts the hand down and returns before #send, so
    there is no send downstream to paint in its place."""
    url = serve(BOARD_PAGE)
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sprint",
            "action": "move",
            "detail": {"unit": "card-heater", "value": "col-done", "rank": "0i"},
        },
    )
    page = open_page(browser, url)
    expect(page.locator("#col-done #card-heater")).to_have_count(1)
    grip = page.locator("#card-heater .lf-grip")
    grip.focus()
    # A box measured across replay's FLIP is a box the card has already left: the press
    # lands on the grip at that instant and the pointer is somewhere else by the
    # mousemove after it, so the drag never starts.
    page.wait_for_function(
        "() => document.getElementById('card-heater').getAnimations().length === 0"
    )
    assert "z" in available_commands(page).get("history.undo", [])
    sent = _traffic(page).sends

    # The mousedown lands on an already-focused control and fires no focusin, so the
    # paint under test is the only one that could clear the offer. Held inside the
    # column it has to itself, the card reorders nothing and onEnd returns before #send.
    box = grip.bounding_box()
    start = (
        math.floor(box["x"] + box["width"] / 2),
        math.floor(box["y"] + box["height"] / 2),
    )
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(start[0], start[1] + 24, steps=8)  # past fallbackTolerance
    wait_for_check_api(
        page, "(api) => api.dragHeld()"
    )  # the gesture is live in the page
    # Read once, on the frame the paint coalesces to, rather than through `expect`:
    # a heartbeat two seconds out repaints the line whatever this drag did, so an
    # assertion that re-decisions passes on the poll and says nothing about the edge.
    assert "z" not in available_commands(page).get("history.undo", []), (
        "the line offered a press the dispatcher refuses for the length of a drag"
    )

    page.mouse.up()
    assert not page.evaluate(DRAG_HELD)
    assert "z" in available_commands(page).get("history.undo", []), (
        "the drop that sent nothing left the line refusing a press that is live"
    )
    assert _traffic(page).sends == sent, "the drop that moved nothing sent a move"
    expect(page.locator("#col-done #card-heater")).to_have_count(1)


def _serve_preparing_thread(serve, page=SUGGESTION_PAGE):
    return serve(
        page,
        layer_registry={
            "lf-preparation": {
                "description": "A reply whose presentation waits for its content.",
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
                "additionalProperties": False,
                "x-content": "markup",
                "x-upgrade": True,
                "x-example": '<lf-preparation id="example"><p>Ready</p></lf-preparation>',
            }
        },
        layer_widgets={
            "lf-preparation.js": """
import {once, widgetController} from '/runtime/widget-api.js';
customElements.define('lf-preparation', class extends HTMLElement {
  connectedCallback() {
    if (!once(this)) return;
    widgetController(this).present(fetch('/preparation-content').then(() => {
      this.dataset.ready = 'yes';
    }));
  }
});
"""
        },
    )


def test_undo_waits_while_the_candidate_is_applying_then_reads_accepted_truth(
    browser, serve
):
    """Undo waits during application, then reads accepted truth after a paint fault."""
    url = _serve_preparing_thread(serve)
    page = open_page(browser, url)
    suggestion_control(page, "sug-refill", "accept").click()
    round_trip(page)
    long_thread(serve.page_dir, "question", "Please add the supporting detail.")
    told(page)
    open_panel_thread(page, "question")
    before = page.locator("body").get_attribute("data-lf-reading")
    held_states = []
    page.route("**/api/state*", lambda route: held_states.append(route))
    preparations = []
    page.route("**/preparation-content", lambda route: preparations.append(route))
    posts = []

    def record_post(route):
        posts.append(route.request.post_data_json)
        route.continue_()

    page.route("**/api/event", record_post)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "revision": 1,
            "parent": "question",
            "text": "Here is the detail.",
            "markup": '<lf-preparation id="detail"><p>Supporting detail</p></lf-preparation>',
        },
    )
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-thistle",
            "action": "decide",
            "detail": {"outcome": "accept"},
        },
    )
    holding(page, held_states, 1, "candidate read")
    candidate = held_states[0].fetch().json()
    head = candidate["browser"]["views"]["1"]["undo"][0]
    assert head["event"]["widget"] == "sug-thistle"
    # Picked up, so `z` shows the suggestion first wherever the layout leaves it.
    head["picked_up"] = True
    with page.expect_request("**/preparation-content"):
        held_states.pop(0).fulfill(json=candidate)
    holding(page, preparations, 1, "thread preparation")
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("z")
    page.title()
    assert not [event for event in posts if event.get("kind") == "undo"]

    # Fail the completed candidate's readiness stamp once. This is a required DOM
    # write after the preparation await, so accepted truth is already published even
    # though the presentation proof cannot advance.
    fail_reading_commit(page, candidate["reading"], "injected candidate commit fault")
    with page.expect_console_message(
        lambda message: "injected candidate commit fault" in message.text
    ):
        preparations[0].fulfill(status=204)
    expect(page.locator("body")).to_have_attribute("data-lf-reading", before)
    expect(page.locator("#sug-thistle")).to_have_attribute("data-lf-state", "accept")
    assert not [event for event in posts if event.get("kind") == "undo"]

    # The agent picked the gesture up, so the first press shows it.
    page.keyboard.press("z")
    expect(page.locator("#sug-thistle")).to_be_focused()
    assert not [event for event in posts if event.get("kind") == "undo"]
    undo(page)
    expect(page.locator("#sug-thistle")).not_to_have_attribute(
        "data-lf-state", "accept"
    )
    undo_posts = [event for event in posts if event.get("kind") == "undo"]
    assert [event["undoes"] for event in undo_posts] == [
        candidate["browser"]["views"]["1"]["undo"][0]["event"]["id"]
    ]
    page.unroute("**/api/state*")
    for route in held_states:
        route.continue_()
    reported_browser_errors(
        page,
        "leaf: State presentation failed: injected candidate commit fault",
    )


def test_an_optimistic_presentation_fault_does_not_change_delivery_result(
    browser, serve
):
    """A local optimistic paint fault cannot turn an accepted send into a refusal."""
    page = open_page(browser, serve(SUGGESTION_PAGE))
    page.route("**/api/state*", refuse)
    # The fault is raised by the first write the optimistic paint makes: the suggestion's
    # settled state, which only that paint changes before the log answers.
    page.evaluate(
        """() => {
          const target = document.getElementById('sug-refill');
          const setAttribute = target.setAttribute;
          target.setAttribute = function(name, value) {
            if (name === 'data-lf-state') {
              target.setAttribute = setAttribute;
              throw new Error('injected optimistic presentation fault');
            }
            return setAttribute.call(this, name, value);
          };
        }"""
    )

    with page.expect_request(
        lambda request: (
            "/api/event" in request.url
            and request.post_data_json.get("kind") == "action"
            and request.post_data_json.get("widget") == "sug-refill"
        ),
    ):
        suggestion_control(page, "sug-refill", "accept").click()
    round_trip(page)

    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "accept")
    undo = suggestion_control(page, "sug-refill", "undo")
    expect(undo).to_be_enabled()
    assert [event["detail"]["outcome"] for event in actions(serve.page_dir)] == [
        "accept"
    ]
    # One fault, one report, from the widget paint that raised it. The gesture's own
    # promise carries the same rejection for a caller that restores a draft from it, and
    # accounts for it no second time.
    errors = take_browser_errors(page)
    assert [said(error) for error in errors] == [
        'leaf: <lf-suggestion id="sug-refill"> failed: injected optimistic presentation fault'
    ], errors


def test_a_draft_that_outlives_its_passage_returns_with_that_passage(browser, serve):
    """A draft survives the version it was written against even when that version's
    replacement removes its passage. The editor stays available without attaching to
    the rewritten words, and the draft returns to its passage when that version does."""
    url = serve(INLINE_PAGE)
    page = open_page(browser, url)

    page.locator("#p").click(click_count=3)
    page.locator(".lf-fab-input").click()
    write(
        page.locator(".lf-composer leaf-text"),
        "half-written when the version turned over",
    )
    passage = " ".join(page.locator("#p").inner_text().split())
    assert not composer_quote(page)["shown"], "the passage is right here, and marked"

    # Claude ships a version that rewrites the passage out. The page holds still — a
    # draft is mid-composition — and offers the new version in the leaf's menu, which
    # the user takes.
    d = serve.page_dir
    rewritten = INLINE_PAGE.replace(
        "A paragraph carrying <strong>bold text</strong> and <em>emphasis</em> inside it,\n"
        "so that a selection across the middle of it lands in more than one text node.",
        "Rewritten, with nothing left of the sentence the draft was about.",
    )
    stamp_page(d, rewritten, "two")
    told(page)
    expect_panel_offers(page, "latest")
    panel_control(page, "latest").click()
    wait_for_revision(page, 2)
    expect(page).not_to_have_url(re.compile("/versions/"))
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_have_js_property(
        "value", "half-written when the version turned over"
    )
    expect(page.locator("#lf-composer-quote")).to_have_text(f"“{passage}”")
    assert pending_text(page) == "", (
        "v2 rewrote the passage and the page marked it anyway"
    )

    # Through the page's own readiness rather than the paragraph's arrival in markup:
    # the restore of an open draft is part of presenting the page, and a gesture made
    # before that is a gesture the user could not have made.
    navigate(page, url)
    page.locator("#p").click(click_count=3)
    expect(page.locator("#lf-composer-quote")).to_have_text(f"“{passage}”")
    expect(page.locator(".lf-fab-input")).to_have_js_property(
        "value", "half-written when the version turned over"
    )
    # The words come back; the user's keyboard does not go with them.
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    quote = composer_quote(page)
    assert quote["text"] == f"“{passage}”", f"the quote says {quote['text']!r}"
