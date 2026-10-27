"""What waits on the user: the `m` queue, the panel's On me count and its On view,
tallies, and the to-dos the user ends."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import live_url, panel_comment
from render_cases_layout import toggle_queue
from render_harness import (
    PANEL,
    available_commands,
    holding,
    leaf_page,
    open_page,
    panel_settled,
    panel_view,
    resized,
    round_trip,
    scroll_settled,
    sending,
    stamp_page,
    wait_for_revision,
    write,
)

from browser.navigation import expect_walk_position, walk_position
from leaf import event_log as events_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


# What waits on the user, as On me counts it (floating-panel.js, `onUserCount`): the
# queue's own reading, since a gesture's next step can stand in the marks' place.
ON_ME = """async () => {
  const {readQueues} = await window.__lfWidgetApi();
  window.__lfOnMe = () => {
    const queues = readQueues();
    return queues.phase === "ready" ? queues.on_user.length : null;
  };
}"""


def expect_on_me(page, count):
    """Wait until On me counts `count` obligations waiting on the user."""
    page.evaluate(ON_ME)
    page.wait_for_function("count => window.__lfOnMe() === count", arg=count)


def x_ends(page):
    """Whether `x` ends something at the current location: a to-do on them."""
    return any("x" in keys for keys in available_commands(page).values())


QUEUE_PAGE = leaf_page(
    "What waits on you",
    '<h1 id="h">Release</h1><p id="cadence">We publish a build every week.</p>'
    '<lf-ask id="channel-ask"><h2>Which channel first?</h2>'
    '<lf-options id="channel" choose><lf-option id="beta">Beta first</lf-option>'
    '<lf-option id="both">Both at once</lf-option></lf-options></lf-ask>'
    '<p id="notes">Release notes come from merged titles.</p>',
)


def test_m_keeps_its_position_at_a_chrome_stop_without_a_page_target(browser, serve):
    source = leaf_page(
        "Chrome queue stops",
        "<h1>Release</h1><p>Review the release.</p>",
    )
    url = serve(source)
    comment = append_carried_log_record(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "Ready?"},
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Agent",
            "parent": comment["id"],
            "responds": comment["id"],
            "revision": 1,
            "text": "Which channel?",
            "obligation": True,
        },
    )
    page = open_page(browser, url)
    page.evaluate("getSelection().removeAllRanges()")
    page.keyboard.press("m")
    rendered(page)
    assert page.evaluate(
        "id => document.activeElement.closest('[data-thread]')?.dataset.thread === id",
        comment["id"],
    )
    position = walk_position(page)
    assert position is not None
    assert position["text"] == "1 of 1 waiting on me · Reply"


def test_m_walks_what_waits_on_you_and_on_me_counts_it(browser, serve):
    """`m` stops, in page order, at a thread whose question waits on the user as well
    as at an open obligation, and passes a thread waiting on the agent; `t` still walks both
    threads. The panel's On me mark counts what waits on the user. A reply the user
    sends takes its thread off that count and out of the walk once the server has read
    the reply."""
    url = serve(QUEUE_PAGE)
    d = serve.page_dir
    asked = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Weekly?",
            "anchor": {"section": "cadence"},
        },
    )
    question = append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Agent",
            "parent": asked["id"],
            "responds": asked["id"],
            "revision": 1,
            "text": "Weekly or daily?",
            "obligation": True,
        },
    )
    owed = append_carried_log_record(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Tighten this.",
            "anchor": {"section": "notes"},
        },
    )
    page = open_page(browser, url)

    def counts(you):
        expect_on_me(page, you)

    counts(2)

    thread = page.locator(f'.lf-page-thread[data-thread="{asked["id"]}"]')
    message = thread.locator(f'.lf-msg[data-event="{question["id"]}"]')
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 2 waiting on me · Reply")
    expect(message).to_be_focused()
    page.keyboard.press("m")
    expect_walk_position(page, "2 of 2 waiting on me · Options")
    expect(page.locator("#channel-ask")).to_be_focused()
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 2 waiting on me · Reply")
    expect(message).to_be_focused()
    page.keyboard.press("Shift+m")
    expect_walk_position(page, "2 of 2 waiting on me · Options")
    expect(page.locator("#channel-ask")).to_be_focused()
    page.keyboard.press("Shift+m")
    expect_walk_position(page, "1 of 2 waiting on me · Reply")
    expect(message).to_be_focused()

    page.keyboard.press("Enter")
    box = thread.locator("leaf-text")
    write(box, "Weekly.")
    # The reply is the agent's to answer in the turn it is sent; which question it
    # answers is the server's reading, which takes the thread off the user's count.
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the reply")
    counts(2)
    page.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(page)
    counts(1)
    page.locator("#h").click()
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 1 waiting on me · Options")
    page.locator("#h").click()
    page.keyboard.press("t")
    expect_walk_position(page, "Thread 1 of 2")

    # A follow-up in a thread the agent already owes is still one answer owed: the
    # server owes a thread one answer, to its latest move, so the count holds while the
    # follow-up is in flight and after.
    page.keyboard.press("t")
    expect_walk_position(page, "Thread 2 of 2")
    notes = page.locator(f'.lf-page-thread[data-thread="{owed["id"]}"]')
    expect(notes).to_be_focused()
    page.keyboard.press("Enter")
    write(notes.locator("leaf-text"), "And the second line.")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the follow-up")
    counts(1)
    page.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(page)
    counts(1)


def test_a_tally_counts_its_regions_obligations_and_walks_them(browser, serve):
    """An `lf-tally` counts the obligations its region holds, by the rule a queue row's mark
    reads, and leaves out one outside it. Its Next on me is `m` within the region: a
    press keeps the user located where they are and steps on, coming round at the end,
    and the walk announces its place among the region's obligations. Reached by Shift+Tab from
    an obligation, through the queue's own rows, Enter counts from that obligation, so the keyboard
    steps on too. An answer leaves the count once the log admits it; with none left the
    tally says so and Next on me is disabled. One the user commented on is the agent's
    turn, which the tally names instead of calling it the user's to answer."""

    def item(key, label):
        return (
            f'<lf-tab id="t-{key}" label="{label}"><lf-ask id="{key}-decision">'
            f'<h2>Pick the {key}</h2><lf-options id="{key}" choose>'
            f'<lf-option id="{key}-a">Alpha</lf-option>'
            f'<lf-option id="{key}-b">Beta</lf-option></lf-options></lf-ask></lf-tab>'
        )

    page = open_page(
        browser,
        serve(
            leaf_page(
                "A tallied queue",
                '<header><h1>Queue</h1><p><lf-tally id="left" for="queue" next>'
                "</lf-tally></p></header>"
                '<lf-ask id="outside-decision"><h2>Outside</h2>'
                '<lf-options id="outside" choose><lf-option id="outside-a">Out</lf-option>'
                "</lf-options></lf-ask>"
                '<lf-tabs id="queue" list="side">'
                + item("first", "First")
                + item("second", "Second")
                + "</lf-tabs>",
            )
        ),
    )
    words = page.locator("#left .lf-tally-words")
    button = page.locator("#left").get_by_role("button", name="Next on me")
    first, second = page.locator("#first-decision"), page.locator("#second-decision")
    expect(words).to_have_text("2 left to answer")
    box = page.locator("#left").bounding_box()

    # The row opens the obligation the user reads. Enter its obligation before deciding: the
    # strip itself precedes every panel in DOM order, but is not the walk's origin.
    page.get_by_role("tab", name="Second", exact=True).click()
    page.keyboard.press("Shift+m")
    expect(second).to_be_focused()
    page.get_by_role("tab", name="Second", exact=True).click()
    page.keyboard.press("m")
    expect(second).to_be_focused()
    with sending(page, "the second item's answer by digit"):
        page.keyboard.press("1")
    round_trip(page)
    expect(words).to_have_text("1 left to answer")
    answer = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event["kind"] == "action"
    )
    assert answer["widget"] == "second"
    button.click()
    expect(first).to_be_focused()
    # Next put the answer out of view in its tab, so the first press shows it there
    # and the second takes it back.
    page.keyboard.press("z")
    expect(page.locator("#second")).to_be_focused()
    with sending(page, "undo the second item's answer after Next"):
        page.keyboard.press("z")
    round_trip(page)
    expect(words).to_have_text("2 left to answer")
    assert events_model.read_events(serve.page_dir)[-1]["undoes"] == answer["id"]
    # Leave the next press at the region's start, as on initial arrival.
    page.get_by_role("tab", name="First", exact=True).click()

    def back_to_the_tally():
        for _ in range(30):
            if button.evaluate("button => button === document.activeElement"):
                return
            page.keyboard.press("Shift+Tab")
        raise AssertionError("Shift+Tab never reached Next on me")

    button.click()
    expect(first).to_be_focused()
    expect_walk_position(page, "1 of 2 waiting on me here · Options")
    button.click()
    expect(second).to_be_focused()
    expect_walk_position(page, "2 of 2 waiting on me here · Options")
    back_to_the_tally()
    page.keyboard.press("Enter")
    expect(first).to_be_focused()
    back_to_the_tally()
    page.keyboard.press("Enter")
    expect(second).to_be_focused()

    with sending(page, "the answer to the second decision"):
        page.locator("#second-decision .lf-pick").first.click()
    round_trip(page)
    expect(words).to_have_text("1 left to answer")
    button.click()
    expect(first).to_be_focused()
    with sending(page, "the answer to the first decision"):
        page.locator("#first-decision .lf-pick").first.click()
    round_trip(page)
    expect(words).to_have_text("All 2 answered")
    expect(button).to_be_disabled()
    expect(page.locator("#left")).to_have_attribute("data-lf-done", "")
    with sending(page, "undo the first decision's answer"):
        page.keyboard.press("z")
    round_trip(page)
    expect(words).to_have_text("1 left to answer")
    expect(button).to_be_enabled()
    expect(page.locator("#left")).not_to_have_attribute("data-lf-done", "")
    # A comment on the open obligation hands it to the agent until a reply: the tally and
    # the item's row say so rather than calling it the user's to answer, beside a
    # disabled Next on me.
    panel_comment(serve.page_dir, "Why Alpha?", {"section": "first-decision"})
    expect(words).to_have_text("1 on Claude")
    expect(page.locator("#queue .lf-tab-answer").first).to_have_text("On Claude")
    expect(button).to_be_disabled()
    expect(page.locator("#left")).not_to_have_attribute("data-lf-done", "")
    assert page.locator("#left").bounding_box() == box


@pytest.mark.parametrize("idle_setup", ["at_rest", "layout_clamp"])
def test_a_todo_on_you_ends_at_its_done_where_m_lands_and_in_the_panel(
    browser, serve, idle_setup
):
    """A task the agent put on the user ends at their Done. Where `m` lands on it, `x`
    is Done; its card in On me carries a Done button. Either leaves the user's queue
    in the turn it is pressed, and writes the user's `todo_end`; the obligation beside them
    has no Done, since its widget answers it."""
    url = serve(QUEUE_PAGE)
    d = serve.page_dir

    def put_on_user(subject, title):
        return append_carried_log_record(
            d,
            {
                "kind": "todo",
                "author": "agent",
                "agent": "Agent",
                "session": "queue-done",
                "owner": "user",
                "subject": subject,
                "title": title,
            },
        )

    notes = put_on_user({"kind": "element", "id": "notes"}, "Check the notes")
    whole = put_on_user({"kind": "page"}, "Read it through")
    page = open_page(browser, url)
    resized(page, 1280, 900)
    expect_on_me(page, 3)
    assert not x_ends(page), "the viewport alone selects no task to finish"
    if idle_setup == "layout_clamp":
        page.evaluate("""() => {
          const tail = document.createElement('div');
          tail.id = 'temporary-tail';
          tail.style.height = '3000px';
          document.querySelector('main').append(tail);
          window.scrollTo({top: 1000, behavior: 'instant'});
        }""")
        scroll_settled(page)
        page.evaluate("document.querySelector('#temporary-tail').remove()")
        scroll_settled(page)
        assert page.evaluate("scrollY") == 0

    # The page as a whole is arrived at its head, which comes first.
    page.locator("#cadence").click()
    page.evaluate("""() => {
      document.addEventListener('keydown', function read(event) {
        if (event.key.toLowerCase() !== 'm') return;
        document.removeEventListener('keydown', read, true);
        requestAnimationFrame(() => {
          window.todoAtFirstFrame = document.activeElement.id;
        });
      }, true);
    }""")
    page.keyboard.press("Shift+m")
    expect_walk_position(page, "1 of 3 waiting on me · To-do")
    expect(page.locator("#h")).to_be_focused()
    assert page.evaluate("todoAtFirstFrame") == "h", (
        "an idle arrival paints in its first frame"
    )
    assert x_ends(page), "the page's head as current location selects the page task"
    page.keyboard.press("m")
    expect_walk_position(page, "2 of 3 waiting on me · Options")
    assert not x_ends(page)
    page.keyboard.press("m")
    expect_walk_position(page, "3 of 3 waiting on me · To-do")
    expect(page.locator("#notes")).to_be_focused()
    assert x_ends(page)

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("x")
    holding(page, held, 1, "the Done")
    expect_on_me(page, 2)
    page.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(page)
    expect_on_me(page, 2)
    end = events_model.read_events(d)[-1]
    assert (end["kind"], end["author"], end["todo"], end["outcome"]) == (
        "todo_end",
        "user",
        notes["id"],
        "done",
    )
    # Done is a gesture like any other: `z` puts the task back on the user.
    page.keyboard.press("z")
    expect_on_me(page, 3)
    round_trip(page)
    assert events_model.read_events(d)[-1]["undoes"] == end["id"]
    expect_on_me(page, 3)
    with sending(page, "the Done again"):
        page.keyboard.press("x")
    expect_on_me(page, 2)

    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    you = page.locator('.lf-fp-on-item[data-list="you"]')
    expect(you).to_have_count(2)
    finish = you.get_by_role("button", name="Done", exact=True)
    expect(finish).to_have_count(1)
    expect(you.filter(has_text="Read it through")).to_have_count(1)
    finish.focus()
    with sending(page, "the panel's Done"):
        page.keyboard.press("Enter")
    expect(you).to_have_count(1)
    expect_on_me(page, 1)
    assert events_model.read_events(d)[-1]["todo"] == whole["id"]


def put_todo_on_user(page_dir, subject, title):
    """Open a to-do on the user, as `leaf task open --on user` does."""
    return append_carried_log_record(
        page_dir,
        {
            "kind": "todo",
            "author": "agent",
            "agent": "Agent",
            "session": "queue-words",
            "owner": "user",
            "subject": subject,
            "title": title,
        },
    )


def todo_field(page):
    """The page's field, whose empty words name the to-do the user stands on."""
    return page.locator(".lf-fp-field leaf-text")


def row_done(page):
    """The Done at the end of the panel's row, for the to-do the user stands on."""
    return page.locator('.lf-fp-exit[aria-label="Done"]')


def test_a_todo_on_you_says_its_words_where_you_land_on_it(browser, serve):
    """A to-do's subject carries an On me mark named by its title before anything takes
    the user there, and wherever `m` or Show lands them on it, the panel's empty field
    names it and the row's end offers its Done. A to-do on the page as a whole stands at
    the page's heading, which its own words say nothing about."""
    url = serve(QUEUE_PAGE)
    whole = "Confirm the page-level build works"
    notes = "Try the notes command"
    put_todo_on_user(serve.page_dir, {"kind": "page"}, whole)
    put_todo_on_user(serve.page_dir, {"kind": "element", "id": "notes"}, notes)
    page = open_page(browser, url)
    resized(page, 1440, 900)
    expect_on_me(page, 3)
    for item, title in (("h", whole), ("notes", notes)):
        marker = page.locator(
            f'[data-lf-margin-for="{item}"] .lf-margin-marker[data-lf-kinds~="on-me"]'
        )
        expect(marker).to_have_attribute("aria-label", re.compile(re.escape(title)))
    expect(row_done(page)).to_have_count(0)

    page.locator("#cadence").click()
    page.keyboard.press("Shift+m")
    expect(page.locator("#h")).to_be_focused()
    expect(todo_field(page)).to_have_attribute(
        "placeholder", re.compile(f"^To-do · {re.escape(whole)}")
    )
    expect(row_done(page)).to_be_visible()

    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    page.locator('.lf-fp-on-item[data-list="you"]').filter(has_text=notes).get_by_role(
        "button", name="Show"
    ).click()
    panel_settled(page, open=False)
    expect(page.locator("#notes")).to_be_focused()
    expect(todo_field(page)).to_have_attribute(
        "placeholder", re.compile(f"^To-do · {re.escape(notes)}")
    )
    expect(row_done(page)).to_be_visible()

    # A mode entered there is the stance the row's end leaves.
    page.keyboard.press("w")
    expect(page.locator('.lf-fp-exit[aria-label="Exit Draw mode"]')).to_be_visible()
    expect(row_done(page)).to_have_count(0)
    page.keyboard.press("w")
    expect(row_done(page)).to_be_visible()


def test_two_todos_on_one_element_are_one_stop_ended_in_turn(browser, serve):
    """`m` reaches an element holding two to-dos once. The user there is on the first,
    which `x` ends, and then on the second, so the field names each in turn."""
    url = serve(QUEUE_PAGE)
    first = put_todo_on_user(
        serve.page_dir, {"kind": "element", "id": "notes"}, "Check the notes"
    )
    put_todo_on_user(serve.page_dir, {"kind": "element", "id": "notes"}, "Fix a title")
    page = open_page(browser, url)
    expect_on_me(page, 3)
    page.locator("#cadence").click()
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 2 waiting on me · Options")
    page.keyboard.press("m")
    expect_walk_position(page, "2 of 2 waiting on me · To-do")
    expect(page.locator("#notes")).to_be_focused()
    expect(todo_field(page)).to_have_attribute(
        "placeholder", re.compile("^To-do · Check the notes")
    )
    with sending(page, "the first Done"):
        page.keyboard.press("x")
    assert events_model.read_events(serve.page_dir)[-1]["todo"] == first["id"]
    expect(todo_field(page)).to_have_attribute(
        "placeholder", re.compile("^To-do · Fix a title")
    )
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 2 waiting on me · Options")


def test_a_finger_ends_a_todo_on_you_where_show_lands(browser, serve):
    """Under a finger, the to-do an On card's Show leaves the user on ends from the Done
    at the end of the panel's row, without going back into On me."""
    url = serve(QUEUE_PAGE)
    task = put_todo_on_user(
        serve.page_dir, {"kind": "element", "id": "notes"}, "Check the notes"
    )
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, url, context=context)
    page.locator(".lf-fp-on-user").tap()
    panel_settled(page, view="queue")
    card = page.locator(".lf-fp-on-item", has_text="Check the notes")
    card.get_by_role("button", name="Show", exact=True).tap()
    expect(page.locator("#notes")).to_be_focused()
    expect(todo_field(page)).to_have_attribute(
        "placeholder", re.compile("^To-do · Check the notes")
    )
    with sending(page, "the row's Done"):
        row_done(page).tap()
    expect_on_me(page, 1)
    assert events_model.read_events(serve.page_dir)[-1]["todo"] == task["id"]
    expect(row_done(page)).to_have_count(0)


NESTED_TODOS_PAGE = leaf_page(
    "Nested tasks",
    '<section id="plan"><h2>Plan</h2>'
    '<p id="step">Ship it on Tuesday, after the backfill.</p></section>'
    '<p id="tail">Nothing else is planned.</p>',
)


def test_x_ends_the_innermost_todo_the_user_stands_on(browser, serve):
    """Located on a task inside another, `x` ends the inner one: a task on a section
    inside the page, with no heading for the page's own task to stand at, and a task
    on a paragraph inside that section."""
    url = serve(NESTED_TODOS_PAGE)
    d = serve.page_dir

    def put_on_user(subject, title):
        return append_carried_log_record(
            d,
            {
                "kind": "todo",
                "author": "agent",
                "agent": "Agent",
                "session": "nested-tasks",
                "owner": "user",
                "subject": subject,
                "title": title,
            },
        )

    put_on_user({"kind": "page"}, "Read it through")
    plan = put_on_user({"kind": "element", "id": "plan"}, "Check the plan")
    step = put_on_user({"kind": "element", "id": "step"}, "Check the step")
    page = open_page(browser, url)
    expect_on_me(page, 3)

    # The step stands inside the plan, which stands inside the page's `main`.
    page.locator("#step").click()
    with sending(page, "the step's Done"):
        page.keyboard.press("x")
    expect_on_me(page, 2)
    assert events_model.read_events(d)[-1]["todo"] == step["id"]

    page.locator("#step").click()
    with sending(page, "the plan's Done"):
        page.keyboard.press("x")
    expect_on_me(page, 1)
    assert events_model.read_events(d)[-1]["todo"] == plan["id"]

    # Off every section, nothing the user is located on is the page's own task, which `m`
    # arrives at its head.
    page.locator("#tail").click()
    assert not x_ends(page)
    page.keyboard.press("Shift+m")
    expect_walk_position(page, "1 of 1 waiting on me · To-do")
    assert x_ends(page)


def test_an_m_step_newer_focus_cancels_at_a_thread_claims_no_arrival(browser, serve):
    """`m` arriving at a thread with the panel shut opens it on the page, and the
    opening can wait on the page. Focus the user moves meanwhile cancels the arrival:
    focus stays where they put it and the walk says nothing about the thread."""
    url = serve(QUEUE_PAGE)
    asked = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Weekly?",
            "anchor": {"section": "cadence"},
        },
    )
    question = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Agent",
            "parent": asked["id"],
            "responds": asked["id"],
            "revision": 1,
            "text": "Weekly or daily?",
            "obligation": True,
        },
    )
    page = open_page(browser, url)
    page.evaluate(
        """() => {
          const held = new Promise(resolve => { window.releaseThreadReveal = resolve; });
          held.then(() => { window.threadRevealSettled = true; });
          document.body.addEventListener('lf-reveal', event => {
            event.detail.present(held);
            window.threadRevealStarted = true;
          }, {once: true});
        }"""
    )

    page.keyboard.press("m")
    page.wait_for_function("window.threadRevealStarted === true")
    page.locator(".lf-fp-on-user").focus()
    expect(page.locator(".lf-fp-on-user")).to_be_focused()
    page.evaluate("releaseThreadReveal()")
    page.wait_for_function("window.threadRevealSettled === true")
    rendered(page)

    expect(page.locator(".lf-fp-on-user")).to_be_focused()
    assert walk_position(page) is None
    # The control: the same press left alone arrives and says where.
    page.locator("#h").click()
    page.keyboard.press("m")
    expect_walk_position(page, "1 of 2 waiting on me · Reply")
    expect(page.locator(f'.lf-msg[data-event="{question["id"]}"]')).to_be_focused()


@pytest.mark.parametrize("width", [1200, 390])
def test_a_completed_obligation_stays_reachable_through_on_me(browser, serve, width):
    """An answered obligation stays in On me under Done, which closes and reopens through its
    routes."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "One decision",
                '<h1>One decision</h1><lf-ask id="only-decision"><h2>Pick one</h2>'
                '<lf-options id="only" choose>'
                '<lf-option id="first">First</lf-option>'
                '<lf-option id="second">Second</lf-option></lf-options></lf-ask>',
            )
        ),
    )

    resized(page, width, 844)
    page.keyboard.press("m")
    expect(page.locator("#only-decision")).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.locator("#only .lf-pick").first).to_be_focused()
    page.keyboard.press("1")
    round_trip(page)

    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    done = page.locator('.lf-fp-on-item[data-list="done"]')
    expect(done).to_have_count(1)
    expect(done).to_contain_text("Pick one")
    expect(page.locator('.lf-fp-on-item[data-list="you"]')).to_have_count(0)

    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, open=False)

    # With nothing left on the user, On me opens on its Done.
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    expect(done).to_have_count(1)


def test_a_completed_obligation_keeps_its_answer_in_the_on_panel(browser, serve):
    """Finishing a page preserves the On panel's route back through the answer."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "One decision",
                '<h1>One decision</h1><lf-ask id="only-decision"><h2>Pick one</h2>'
                '<lf-options id="only" choose>'
                '<lf-option id="first">First</lf-option>'
                '<lf-option id="second">Second</lf-option></lf-options></lf-ask>',
            )
        ),
    )
    # `m` travels to the obligation and Tab steps onto a mark, whose digit answers it. Tab
    # rather than the digit straight off the arrival, because where an arrival lands is
    # not this test's subject and it should not go red when that moves.
    page.keyboard.press("m")
    page.keyboard.press("Tab")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("1")
    holding(page, held, 1, "the option answer")
    pending = page.evaluate(
        """async () => {
          const {readObligations} = await window.__lfWidgetApi();
          const reading = readObligations();
          const item = reading.all.find(q => q.id === 'widget:only');
          return {
            value: item.answer.value,
            status: item.status,
            unanswered: reading.unanswered.some(q => q.id === item.id),
          };
        }"""
    )
    assert pending == {"value": ["first"], "status": "open", "unanswered": True}
    page.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(page)
    toggle_queue(page)
    done = page.locator('.lf-fp-on-item[data-list="done"]')
    expect(done).to_have_count(1)
    expect(done).to_contain_text("First")

    reading = page.evaluate(
        """async () => {
          const {readObligations} = await window.__lfWidgetApi();
          const item = readObligations().all.find(q => q.id === 'widget:only');
          return {
            id: item.id,
            source: item.source,
            prompt: item.prompt,
            value: item.answer.value,
            status: item.status,
          };
        }"""
    )
    assert reading == {
        "id": "widget:only",
        "source": {"kind": "widget", "id": "only", "tag": "lf-options"},
        "prompt": {"text": "Pick one", "target": "only-decision"},
        "value": ["first"],
        "status": "answered",
    }
    page.locator("h1").focus()
    assert page.evaluate(
        """async () => {
          const {obligationActions} = await window.__lfWidgetApi();
          return obligationActions.open('widget:only');
        }"""
    )
    expect(page.locator("#only-decision")).to_be_focused()


def test_on_me_says_when_a_revision_removes_its_last_obligation(browser, serve):
    """An empty On me list says the panel rendered, rather than looking broken."""
    source = leaf_page(
        "One decision",
        '<h1>One decision</h1><lf-ask id="only-decision"><h2>Pick one</h2>'
        '<lf-options id="only" choose>'
        '<lf-option id="first">First</lf-option>'
        '<lf-option id="second">Second</lf-option></lf-options></lf-ask>',
    )
    url = serve(source)
    page = open_page(browser, live_url(url))
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    cards = page.locator('.lf-fp-on-item[data-list="you"]')
    expect(cards).to_have_count(1)
    note = page.locator(f"{panel_view('queue')} .lf-fp-empty")
    expect(note).to_have_count(0)

    stamp_page(
        serve.page_dir,
        leaf_page("No decisions", "<h1>No decisions remain</h1>"),
        "remove the last obligation",
    )
    wait_for_revision(page, 2)
    expect(cards).to_have_count(0)
    expect(page.locator(PANEL)).to_have_attribute("data-open", "queue")
    expect(note).to_be_visible()
    expect(note).to_have_text("Nothing waiting on me.")
    # The agent's tab says the same of its list.
    page.locator(".lf-fp-filters button").nth(1).click()
    expect(page.locator(".lf-fp-view:not([data-leaving]) .lf-fp-empty")).to_have_text(
        re.compile(r"Nothing waiting on \S+\.")
    )


def test_m_lands_what_it_reaches_above_the_open_on_me_view(browser, serve):
    """With On me open, `m` lands a suggestion the view would cover above the view,
    since every landing clears the panel's whole box rather than its row alone
    (theme.css, `--lf-panel-reach`). The suggestion ends a paragraph whose start the
    arrival aligns, as the feature gallery's "A pencil is useful too." does; the asks
    after it fill the list, so the view stands most of the window tall."""
    filler = "".join(f"<p>Paragraph {n} of the release notes.</p>" for n in range(30))
    asks = "".join(
        f'<lf-ask id="ask-{n}"><h2>Question {n}</h2><lf-options id="pick-{n}" choose>'
        f'<lf-option id="yes-{n}">Yes</lf-option><lf-option id="no-{n}">No</lf-option>'
        "</lf-options></lf-ask>"
        for n in range(10)
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Suggestions",
                f"<h1>Suggestions</h1>{filler}"
                '<p id="forms">'
                + "".join(f"Line {n} of the packing list.<br>" for n in range(8))
                + 'Bring a notebook.<lf-suggestion id="insert"><lf-new> A pencil is '
                "useful too.</lf-new></lf-suggestion></p>"
                f"{filler}{asks}",
            )
        ),
    )
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    card = page.locator(".lf-fp-card")
    suggestion = page.locator("#insert")
    page.keyboard.press("m")
    expect(suggestion).to_be_focused()
    scroll_settled(page)
    box = suggestion.bounding_box()
    assert box["y"] >= 0
    assert box["y"] + box["height"] <= card.bounding_box()["y"]
