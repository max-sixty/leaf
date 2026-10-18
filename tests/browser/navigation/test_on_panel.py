"""What waits on the user: the `m` queue, the banner's counts, the On panel's lists,
tallies, and the to-dos the user ends."""

import re

import pytest
from interact_support import append_carried_log_record
from leaf import event_log as events_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import QUEUE_ROW_SAYS, live_url
from render_cases_layout import banner_control
from render_harness import (
    holding,
    leaf_page,
    open_page,
    resized,
    round_trip,
    sending,
    shortcut_bar_text,
    stamp_page,
    wait_for_revision,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed


QUEUE_PAGE = leaf_page(
    "What waits on you",
    '<h1 id="h">Release</h1><p id="cadence">We publish a build every week.</p>'
    '<lf-ask id="channel-ask"><h2>Which channel first?</h2>'
    '<lf-options id="channel" choose><lf-option id="beta">Beta first</lf-option>'
    '<lf-option id="both">Both at once</lf-option></lf-options></lf-ask>'
    '<p id="notes">Release notes come from merged titles.</p>',
)


def test_m_walks_what_waits_on_you_and_the_banner_counts_both_queues(browser, serve):
    """`m` stops, in page order, at a thread whose question waits on the user as well
    as at an open item, and passes a thread waiting on the agent; `t` still walks both
    threads. The banner counts what waits on each side, the user's On me on their
    door beside Threads and the agent's On count beside the status. A reply the user sends
    joins the agent's count as it is sent, and its thread leaves the user's count and
    the walk once the server has read the reply."""
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
    append_carried_log_record(
        d,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Agent",
            "parent": asked["id"],
            "responds": asked["id"],
            "revision": 1,
            "text": "One question:",
            "markup": '<lf-ask id="cadence-question">Weekly or daily?</lf-ask>',
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
    status = page.locator(".lf-status-queues")
    on_me = page.locator(".lf-queue")

    def counts(you, agent):
        expect(on_me).to_have_text(f"On me: {you}")
        expect(on_me).to_have_attribute("aria-label", f"On me: {you}")
        expect(status).to_have_text(f"On Agent: {agent}")

    counts(2, 1)
    expect(page.locator(".lf-status-button")).to_have_attribute(
        "title", re.compile(r" Waiting on me: 2 asks\. .*: 1 reply\.$")
    )

    position = page.locator(".lf-walk-position")
    thread = page.locator(f'.lf-page-thread[data-thread="{asked["id"]}"]')
    page.keyboard.press("m")
    expect(position).to_have_text("1 of 2 waiting on me · Question")
    expect(thread).to_be_focused()
    page.keyboard.press("m")
    expect(position).to_have_text("2 of 2 waiting on me · Options")
    expect(page.locator("#channel-ask")).to_be_focused()
    page.keyboard.press("m")
    expect(position).to_have_text("1 of 2 waiting on me · Question")
    expect(position).to_have_attribute("data-lf-boundary", "")
    expect(thread).to_be_focused()
    page.keyboard.press("Shift+m")
    expect(position).to_have_text("2 of 2 waiting on me · Options")
    expect(page.locator("#channel-ask")).to_be_focused()
    page.keyboard.press("Shift+m")
    expect(position).to_have_text("1 of 2 waiting on me · Question")
    expect(thread).to_be_focused()

    page.keyboard.press("Enter")
    box = thread.locator("leaf-text")
    write(box, "Weekly.")
    # The reply is the agent's to answer in the turn it is sent; which question it
    # answers is the server's reading, which takes the thread off the user's count.
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the reply")
    counts(2, 2)
    page.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(page)
    counts(1, 2)
    page.locator("#h").click()
    page.keyboard.press("m")
    expect(position).to_have_text("1 of 1 waiting on me · Options")
    page.locator("#h").click()
    page.keyboard.press("t")
    expect(position).to_have_text("Thread 1 of 2")

    # A follow-up in a thread the agent already owes is still one answer owed: the
    # server owes a thread one answer, to its latest move, so the count holds while the
    # follow-up is in flight and after.
    page.keyboard.press("t")
    expect(position).to_have_text("Thread 2 of 2")
    notes = page.locator(f'.lf-page-thread[data-thread="{owed["id"]}"]')
    expect(notes).to_be_focused()
    page.keyboard.press("Enter")
    write(notes.locator("leaf-text"), "And the second line.")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the follow-up")
    counts(1, 2)
    page.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(page)
    counts(1, 2)


def test_the_on_panel_shows_each_list_with_its_own_done(browser, serve):
    """The On panel is two tabs, the lists the `m` walk and the banner's counts read,
    and the open tab is its title. Each list shows its open items, then folds its own
    Done: what left that list. Here the agent's Done holds a to-do it ended and the
    replies it sent, and the user's fills as they answer. The agent's opening comment
    carries a question widget. The agent's count opens the agent's
    list, and every other way in opens the user's. A row arrives where `m` would. A
    reply the user sends joins the agent's list as it is sent, and its thread leaves the
    user's for the user's Done once the server has read the reply. A door pressed while
    the panel shows the other list turns it to the door's list."""
    url = serve(QUEUE_PAGE)
    d = serve.page_dir

    def said(author, **event):
        agent = (
            {"agent": "Agent", "session": "queue-panel"} if author == "agent" else {}
        )
        return append_carried_log_record(
            d, {"author": author, "revision": 1, **agent, **event}
        )

    asked = said(
        "agent",
        kind="comment",
        text="Weekly?",
        anchor={"section": "cadence"},
        markup='<lf-ask id="cadence-question">Weekly?</lf-ask>',
    )
    said("user", kind="comment", text="Tighten this.", anchor={"section": "notes"})
    rebuild = said(
        "user", kind="comment", text="Rebuild them.", anchor={"section": "notes"}
    )
    said(
        "agent",
        kind="reply",
        parent=rebuild["id"],
        responds=rebuild["id"],
        text="Rebuilding them.",
        todo="Rebuild the notes",
    )
    retitle = said("user", kind="comment", text="Retitle it.", anchor={"section": "h"})
    ended = said(
        "agent",
        kind="reply",
        parent=retitle["id"],
        responds=retitle["id"],
        text="Retitling it.",
        todo="Retitle the release",
    )
    said(
        "agent",
        kind="todo_end",
        todo=ended["id"],
        outcome="done",
        detail="Retitled in this version",
    )
    page = open_page(browser, url)
    resized(page, 1280, 900)
    panel = page.locator(".lf-queue-panel")
    tabs = panel.locator(".lf-queue-tab")

    # The user's On me stands on its door beside Threads, and the agent's On count
    # beside the status is a door too, to the agent's list: a press opens what they
    # count and another takes it down, and closing it from inside hands focus back.
    expect(page.locator(".lf-queue")).to_have_text("On me: 2")
    counts = page.locator(".lf-status-queues")
    expect(counts).to_have_text("On Agent: 2")
    counts.click()
    expect(panel).to_be_visible()
    expect(panel).to_have_accessible_name("On Agent")
    expect(tabs.nth(1)).to_have_attribute("aria-pressed", "true")
    expect(counts).to_have_attribute("aria-expanded", "true")
    counts.click()
    expect(panel).to_be_hidden()
    expect(counts).to_have_attribute("aria-expanded", "false")
    counts.click()
    expect(panel).to_be_visible()
    rows = page.evaluate(QUEUE_ROW_SAYS)
    assert [(row["list"], row["word"], row["title"]) for row in rows[:2]] == [
        ("agent", "Reply", "Tighten this."),
        ("agent", "To-do", "Rebuild the notes"),
    ], rows
    # Its Done holds what left it: the to-do it ended and the replies it sent, each
    # under its own words, newest first.
    assert sorted((row["list"], row["word"], row["title"]) for row in rows[2:]) == [
        ("done", "Reply", "Rebuilding them."),
        ("done", "Reply", "Retitling it."),
        ("done", "To-do", "Retitle the release"),
    ], rows
    assert all(row["where"].startswith(("Done", "Sent")) for row in rows[2:]), rows
    expect(page.locator(".lf-queue-done > summary")).to_have_text("Done · 3")
    # The On me door turns the open panel to the user's list rather than closing it,
    # and the agent's count turns it back.
    page.locator(".lf-queue").click()
    expect(panel).to_have_accessible_name("On me")
    expect(tabs.first).to_have_attribute("aria-pressed", "true")
    counts.click()
    expect(panel).to_have_accessible_name("On Agent")
    # The dialog the panel stands in takes the list's name as it turns, and `g`
    # offers Shift+M as the turn to On me rather than a close.
    expect(page.get_by_role("dialog", name="On Agent")).to_have_count(1)
    page.keyboard.press("g")
    expect(page.locator(".lf-shortcut-bar")).not_to_contain_text("close On panel")
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Close the On panel").click()
    expect(panel).to_be_hidden()
    expect(counts).to_be_focused()

    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    expect(panel).to_be_visible()
    expect(panel).to_have_accessible_name("On me")
    expect(tabs).to_have_text(["On me · 2", "On Agent · 2"])
    rows = page.evaluate(QUEUE_ROW_SAYS)
    # The widget names its row, even when a reply in its thread answers it.
    assert [(row["list"], row["word"], row["title"]) for row in rows] == [
        ("you", "Options", "Which channel first?"),
        ("you", "Question", "Weekly?"),
    ], rows
    assert rows[1]["where"].startswith("§ Release"), rows
    # Nothing has left the user's list yet, so it has no Done.
    expect(page.locator(".lf-queue-done")).to_have_count(0)

    # The first row holds the focus, and the next is the thread whose question waits on
    # the user: Enter arrives where `m` would.
    expect(page.locator("button.lf-queue-row").first).to_be_focused()
    position = page.locator(".lf-walk-position")
    page.keyboard.press("End")
    expect(position).to_have_text("Item 2 of 2")
    page.keyboard.press("Home")
    expect(position).to_have_text("Item 1 of 2")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    thread = page.locator(f'.lf-page-thread[data-thread="{asked["id"]}"]')
    expect(thread).to_be_focused()
    expect(panel).to_be_visible()

    page.keyboard.press("Enter")
    write(thread.locator("leaf-text"), "Weekly.")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the reply")
    you = panel.locator("[data-lf-queue='you'] .lf-queue-row")
    expect(tabs).to_have_text(["On me · 2", "On Agent · 3"])
    expect(you).to_have_count(2)
    page.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(page)
    expect(you).to_have_count(1)

    # The answered question joins the user's Done, which stays folded until opened, and
    # a done row arrives at its thread too. The thread's card stands over the panel's
    # head, so the keyboard opens the fold and activates the covered controls.
    summary = page.locator(".lf-queue-done > summary")
    expect(summary).to_have_text("Done · 1")
    summary.focus()
    page.keyboard.press("Enter")
    done = page.locator(".lf-queue-done .lf-queue-row")
    expect(done).to_have_text([re.compile("Weekly\\?")])
    tabs.nth(1).press("Enter")
    expect(page.locator(".lf-queue-done > summary")).to_have_text("Done · 3")
    done.filter(has_text="Retitle the release").press("Enter")
    expect(
        page.locator(f'.lf-page-thread[data-thread="{retitle["id"]}"]')
    ).to_be_focused()


TWO_DECISIONS_PAGE = leaf_page(
    "Two decisions",
    "<h1>Two decisions</h1>"
    '<lf-ask id="first-decision"><h2>Pick the first</h2>'
    '<lf-options id="first" choose>'
    '<lf-option id="first-a">Alpha</lf-option>'
    '<lf-option id="first-b">Beta</lf-option></lf-options></lf-ask>'
    '<lf-ask id="second-decision"><h2>Pick the second</h2>'
    '<lf-options id="second" choose>'
    '<lf-option id="second-a">Gamma</lf-option>'
    '<lf-option id="second-b">Delta</lf-option></lf-options></lf-ask>',
)


def test_the_on_panels_next_on_me_walks_as_m_does(browser, serve):
    """The panel's head offers Next on me while something waits on the user, and a
    press on it is `m`: the next item in page order, announced as the walk announces it.
    Once nothing waits, the button goes, while the panel stays for what is done."""
    page = open_page(browser, serve(TWO_DECISIONS_PAGE))
    resized(page, 1280, 900)
    panel = page.locator(".lf-queue-panel")
    position = page.locator(".lf-walk-position")
    banner_control(page, ".lf-queue").click()
    expect(panel).to_have_class(re.compile(r"\bopen\b"))
    button = panel.get_by_role("button", name="Next on me", exact=True)
    expect(button).to_be_visible()
    # It stands in the panel's head just before its close.
    assert (
        button.evaluate("el => el.nextElementSibling?.getAttribute('aria-label')")
        == "Close the On panel"
    )
    expect(button).to_have_attribute("title", "Next on me (m)")

    button.click()
    expect(page.locator("#first-decision")).to_be_focused()
    expect(position).to_have_text("1 of 2 waiting on me · Options")
    # The control: `m` from the first question steps to the second, and back.
    page.keyboard.press("m")
    expect(page.locator("#second-decision")).to_be_focused()
    page.keyboard.press("Shift+m")
    expect(page.locator("#first-decision")).to_be_focused()
    # The button steps on from where the user stands, as `m` did.
    button.click()
    expect(page.locator("#second-decision")).to_be_focused()
    expect(position).to_have_text("2 of 2 waiting on me · Options")

    # Answer both; the button leaves with the last question, and the panel stands on.
    for decision in ("#second-decision", "#first-decision"):
        with sending(page, f"the answer to {decision}"):
            page.locator(f"{decision} .lf-pick").first.click()
    round_trip(page)
    expect(panel.locator("[data-lf-queue='you'] .lf-queue-row")).to_have_count(0)
    expect(panel).to_have_class(re.compile(r"\bopen\b"))
    expect(button).to_be_hidden()


def test_a_tally_counts_its_regions_items_and_walks_them(browser, serve):
    """An `lf-tally` counts the items its region holds, by the rule a queue row's mark
    reads, and leaves out one outside it. Its Next on me is `m` within the region: a
    press keeps the user standing where they are and steps on, coming round at the end,
    and the walk announces its place among the region's asks. Reached by Shift+Tab from
    an item, through the queue's own rows, Enter counts from that item, so the keyboard
    steps on too. An answer leaves the count once the log admits it; with none left the
    tally says so and Next on me is disabled."""

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
    position = page.locator(".lf-walk-position")
    first, second = page.locator("#first-decision"), page.locator("#second-decision")
    expect(words).to_have_text("2 of 2 to answer")
    box = page.locator("#left").bounding_box()

    # The row opens the item the user reads. Enter its item before deciding: the
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
    expect(words).to_have_text("1 of 2 to answer")
    answer = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event["kind"] == "action"
    )
    assert answer["widget"] == "second"
    button.click()
    expect(first).to_be_focused()
    with sending(page, "undo the second item's answer after Next"):
        page.keyboard.press("z")
    round_trip(page)
    expect(words).to_have_text("2 of 2 to answer")
    assert events_model.read_events(serve.page_dir)[-1]["undoes"] == answer["id"]
    expect(first).to_be_focused()
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
    expect(position).to_have_text("1 of 2 waiting on me here · Options")
    button.click()
    expect(second).to_be_focused()
    expect(position).to_have_text("2 of 2 waiting on me here · Options")
    back_to_the_tally()
    page.keyboard.press("Enter")
    expect(first).to_be_focused()
    back_to_the_tally()
    page.keyboard.press("Enter")
    expect(second).to_be_focused()

    with sending(page, "the answer to the second decision"):
        page.locator("#second-decision .lf-pick").first.click()
    round_trip(page)
    expect(words).to_have_text("1 of 2 to answer")
    button.click()
    expect(first).to_be_focused()
    with sending(page, "the answer to the first decision"):
        page.locator("#first-decision .lf-pick").first.click()
    round_trip(page)
    expect(words).to_have_text("All 2 answered")
    expect(button).to_be_disabled()
    assert page.locator("#left").bounding_box() == box


def test_a_todo_on_you_ends_at_its_done_where_m_lands_and_in_the_panel(browser, serve):
    """A task the agent put on the user ends at their Done. Where `m` lands on it, `x`
    is Done; its On panel row carries a Done button. Either leaves the user's queue
    in the turn it is pressed, and writes the user's `todo_end`; the item beside them
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
    counts = page.locator(".lf-queue")
    expect(counts).to_have_text("On me: 3")

    position = page.locator(".lf-walk-position")
    # The page as a whole is arrived at its head, which comes first.
    page.locator("#cadence").click()
    page.keyboard.press("Shift+m")
    expect(position).to_have_text("1 of 3 waiting on me · To-do")
    expect(page.locator("#h")).to_be_focused()
    page.keyboard.press("m")
    expect(position).to_have_text("2 of 3 waiting on me · Options")
    assert "x\ndone" not in shortcut_bar_text(page)
    page.keyboard.press("m")
    expect(position).to_have_text("3 of 3 waiting on me · To-do")
    expect(page.locator("#notes")).to_be_focused()
    assert "x\ndone" in shortcut_bar_text(page)

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("x")
    holding(page, held, 1, "the Done")
    expect(counts).to_have_text("On me: 2")
    page.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(page)
    expect(counts).to_have_text("On me: 2")
    end = events_model.read_events(d)[-1]
    assert (end["kind"], end["author"], end["todo"], end["outcome"]) == (
        "todo_end",
        "user",
        notes["id"],
        "done",
    )
    # Done is a gesture like any other: `z` puts the task back on the user.
    page.keyboard.press("z")
    expect(counts).to_have_text("On me: 3")
    round_trip(page)
    assert events_model.read_events(d)[-1]["undoes"] == end["id"]
    expect(counts).to_have_text("On me: 3")
    with sending(page, "the Done again"):
        page.keyboard.press("x")
    expect(counts).to_have_text("On me: 2")

    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel = page.locator(".lf-queue-panel")
    expect(panel).to_be_visible()
    you = panel.locator("[data-lf-queue='you']")
    expect(you.locator(".lf-queue-row")).to_have_count(2)
    expect(you.locator(".lf-queue-finish")).to_have_count(1)
    row = you.locator(".lf-queue-row", has_text="Read it through")
    expect(row).to_contain_text("Whole page")
    expect(row.locator(".lf-queue-kind")).to_have_text("To-do")
    row.focus()
    page.keyboard.press("Tab")
    expect(you.locator(".lf-queue-finish")).to_be_focused()
    with sending(page, "the panel's Done"):
        page.keyboard.press("Enter")
    expect(you.locator(".lf-queue-row")).to_have_count(1)
    expect(counts).to_have_text("On me: 1")
    expect(page.locator(".lf-queue-done > summary")).to_have_text("Done · 2")
    assert events_model.read_events(d)[-1]["todo"] == whole["id"]


def test_a_finger_ends_a_todo_on_you_from_the_banner_row(browser, serve):
    """Under a finger, `x` is a step on the banner's row while the user stands on a
    task Done ends, as an On panel row's tap leaves them."""
    url = serve(QUEUE_PAGE)
    task = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "todo",
            "author": "agent",
            "agent": "Agent",
            "session": "queue-done",
            "owner": "user",
            "subject": {"kind": "element", "id": "notes"},
            "title": "Check the notes",
        },
    )
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, url, context=context)
    row = page.locator(".lf-banner-actions")
    done = row.get_by_role("button", name="Done", exact=True)
    expect(done).to_have_count(0)
    page.get_by_role("button", name="More page controls, items on me").tap()
    page.locator(".lf-banner-menu > .lf-queue").tap()
    panel = page.locator(".lf-queue-panel")
    panel.locator(".lf-queue-row", has_text="Check the notes").tap()
    expect(page.locator("#notes")).to_be_focused()
    expect(done).to_be_visible()
    with sending(page, "the Done step"):
        done.tap()
    expect(page.locator(".lf-queue")).to_have_text("On me: 1")
    assert events_model.read_events(serve.page_dir)[-1]["todo"] == task["id"]
    expect(done).to_have_count(0)


def test_a_keyboard_reaches_the_banners_done_step_under_a_finger(browser, serve):
    """A tablet with a keyboard has the banner's Done step and Tab both. Tab onto the
    step takes focus into Leaf's chrome, where the user stands on nothing, and the step
    stays for the task `m` landed on; Enter on it ends that task."""
    url = serve(NESTED_TODOS_PAGE)
    task = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "todo",
            "author": "agent",
            "agent": "Agent",
            "session": "queue-done",
            "owner": "user",
            "subject": {"kind": "element", "id": "plan"},
            "title": "Check the plan",
        },
    )
    context = browser.new_context(
        viewport={"width": 1024, "height": 768}, has_touch=True, is_mobile=True
    )
    page = open_page(browser, url, context=context)
    done = page.locator(".lf-banner-actions").get_by_role(
        "button", name="Done", exact=True
    )
    page.keyboard.press("m")
    expect(page.locator("#plan")).to_be_focused()
    expect(done).to_be_visible()
    for _ in range(12):
        page.keyboard.press("Shift+Tab")
        expect(done).to_be_visible()
        if done.evaluate("el => el === document.activeElement"):
            break
    expect(done).to_be_focused()
    with sending(page, "the Done step from the keyboard"):
        page.keyboard.press("Enter")
    assert events_model.read_events(serve.page_dir)[-1]["todo"] == task["id"]
    expect(done).to_have_count(0)


NESTED_TODOS_PAGE = leaf_page(
    "Nested tasks",
    '<section id="plan"><h2>Plan</h2>'
    '<p id="step">Ship it on Tuesday, after the backfill.</p></section>'
    '<p id="tail">Nothing else is planned.</p>',
)


def test_x_ends_the_innermost_todo_the_user_stands_on(browser, serve):
    """Standing on a task inside another, `x` ends the inner one: a task on a section
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
    counts = page.locator(".lf-queue")
    expect(counts).to_have_text("On me: 3")
    position = page.locator(".lf-walk-position")

    # The step stands inside the plan, which stands inside the page's `main`.
    page.locator("#step").click()
    with sending(page, "the step's Done"):
        page.keyboard.press("x")
    expect(counts).to_have_text("On me: 2")
    assert events_model.read_events(d)[-1]["todo"] == step["id"]

    page.locator("#step").click()
    with sending(page, "the plan's Done"):
        page.keyboard.press("x")
    expect(counts).to_have_text("On me: 1")
    assert events_model.read_events(d)[-1]["todo"] == plan["id"]

    # Off every section, nothing the user stands on is the page's own task, which `m`
    # arrives at its head.
    page.locator("#tail").click()
    assert "x\ndone" not in shortcut_bar_text(page)
    page.keyboard.press("Shift+m")
    expect(position).to_have_text("1 of 1 waiting on me · To-do")
    assert "x\ndone" in shortcut_bar_text(page)


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
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Agent",
            "parent": asked["id"],
            "responds": asked["id"],
            "revision": 1,
            "text": "One question:",
            "markup": '<lf-ask id="cadence-question">Weekly or daily?</lf-ask>',
        },
    )
    page = open_page(browser, url)
    position = page.locator(".lf-walk-position")
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
    page.locator(".lf-threads-toggle").focus()
    expect(page.locator(".lf-threads-toggle")).to_be_focused()
    page.evaluate("releaseThreadReveal()")
    page.wait_for_function("window.threadRevealSettled === true")
    rendered(page)

    expect(page.locator(".lf-threads-toggle")).to_be_focused()
    assert not position.text_content()
    # The control: the same press left alone arrives and says where.
    page.locator("#h").click()
    page.keyboard.press("m")
    expect(position).to_have_text("1 of 2 waiting on me · Question")
    expect(
        page.locator(f'.lf-page-thread[data-thread="{asked["id"]}"]')
    ).to_be_focused()


@pytest.mark.parametrize("width", [1200, 390])
def test_a_completed_item_stays_reachable_through_the_on_panel(browser, serve, width):
    """An answered item stays in the On panel under Done, which closes and reopens
    through its routes."""
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

    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    expect(page.locator("button.lf-queue-row")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#only-decision")).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.locator("#only .lf-pick").first).to_be_focused()
    page.keyboard.press("1")
    round_trip(page)
    if width == 390:
        expect(page.locator(".lf-queue-panel")).not_to_have_class(
            re.compile(r"\bopen\b")
        )
        page.keyboard.press("g")
        page.keyboard.press("Shift+m")
    expect(page.locator("button.lf-queue-row[data-lf-kind='widget']")).to_have_count(1)
    expect(page.locator(".lf-queue-done .lf-queue-where")).to_contain_text(
        "Answered: First"
    )
    expect(page.locator(".lf-queue-panel")).to_have_class(re.compile(r"\bopen\b"))

    page.keyboard.press("g")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("close On panel")
    page.keyboard.press("Shift+m")
    expect(page.locator(".lf-queue-panel")).to_be_hidden()

    # With nothing left on the user, the panel opens on its Done's door.
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    expect(page.locator(".lf-queue-done > summary")).to_be_focused()


def test_a_completed_item_keeps_its_answer_in_the_on_panel(browser, serve):
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
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    expect(page.locator("button.lf-queue-row")).to_have_count(1)
    # Enter travels to the item and Tab steps onto a mark, whose digit answers it. Tab
    # rather than the digit straight off the arrival, because where an arrival lands is
    # not this test's subject and it should not go red when that moves.
    page.keyboard.press("Enter")
    page.keyboard.press("Tab")
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("1")
    holding(page, held, 1, "the option answer")
    pending = page.evaluate(
        """async () => {
          const {readItems} = await window.__lfWidgetApi();
          const reading = readItems();
          const ask = reading.all.find(q => q.id === 'widget:only');
          return {
            value: ask.answer.value,
            status: ask.status,
            unanswered: reading.unanswered.some(q => q.id === ask.id),
          };
        }"""
    )
    assert pending == {"value": ["first"], "status": "open", "unanswered": True}
    page.unroute("**/api/event")
    for route in held:
        route.continue_()
    round_trip(page)
    expect(page.locator("button.lf-queue-row[data-lf-kind='widget']")).to_have_count(1)
    expect(page.locator(".lf-queue-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator(".lf-queue-done .lf-queue-where")).to_contain_text(
        "Answered: First"
    )

    reading = page.evaluate(
        """async () => {
          const {readItems} = await window.__lfWidgetApi();
          const ask = readItems().all.find(q => q.id === 'widget:only');
          return {
            id: ask.id,
            source: ask.source,
            prompt: ask.prompt,
            value: ask.answer.value,
            status: ask.status,
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
          const {itemActions} = await window.__lfWidgetApi();
          return itemActions.open('widget:only');
        }"""
    )
    expect(page.locator("#only-decision")).to_be_focused()


def test_on_me_says_when_a_revision_removes_its_last_item(browser, serve):
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
    expect(page.locator("button.lf-queue-row")).to_have_count(1)
    note = page.locator(".lf-queue-panel [data-lf-queue='you'] .lf-queue-empty")
    expect(note).to_have_count(0)

    stamp_page(
        serve.page_dir,
        leaf_page("No decisions", "<h1>No decisions remain</h1>"),
        "remove the last ask",
    )
    wait_for_revision(page, 2)
    expect(page.locator("button.lf-queue-row")).to_have_count(0)
    expect(page.locator(".lf-queue-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(note).to_be_visible()
    expect(note).to_have_text("Nothing waiting on me.")
    # The agent's tab says the same of its list.
    page.locator(".lf-queue-tab", has_text="On ").nth(1).click()
    expect(
        page.locator(".lf-queue-panel [data-lf-queue='agent'] .lf-queue-empty")
    ).to_have_text(re.compile(r"^Nothing waiting on \S+\.$"))
