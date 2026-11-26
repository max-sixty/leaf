"""How a thread folds earlier messages under an agent summary, reveals pending
progress, and hides progress once an answer completes it."""

import re

import pytest
from interact_support import append_carried_log_record, append_command
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, SEATED_OBLIGATION_PAGE, panel_comment
from render_harness import (
    expect_preview_words,
    open_page,
    resized,
    sending,
    told,
)

from browser.threads import (
    append_agent_reply,
    append_user_reply,
    open_panel_thread,
    summarize_thread,
)
from leaf.agents import thread as thread_model
from leaf.log import event_log as events_model
from leaf.source.render_checks import rendered
from leaf_dev.browser import open_on_me

pytestmark = pytest.mark.shifts_unsurveyed


def show_held_news(card):
    """Show what the card holds behind its notice, by a press that leaves focus where
    the user is located."""
    notice = card.locator(".lf-thread-news")
    expect(notice).to_be_visible()
    notice.evaluate("node => node.click()")
    expect(notice).to_have_count(0)


def open_margin_card(page, root):
    """Open the margin card of the passage thread `root`, by its marker, and return it."""
    page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker').click()
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]')
    expect(card).to_be_visible()
    return card


@pytest.mark.parametrize("resolved", [False, True])
def test_a_seated_reply_draws_its_widget_in_place(browser, serve, resolved):
    """A thread a widget seats on the page draws a reply's widget in place, where the
    user answers it, even in a long thread or in the Resolved state."""
    url = serve(SEATED_OBLIGATION_PAGE)
    root = panel_comment(
        serve.page_dir, "Which job should come first?", {"section": "jobs"}
    )
    reply = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Choose the first job.\n\n"
        '<lf-group id="first-job-decision" label="Which job first?">\n<h3 id="first-job-decision-h">Which job first?</h3>'
        '<lf-options id="first-job">'
        '<lf-option id="mounts">Put the mounts back</lf-option>'
        '<lf-option id="camera">Install the camera</lf-option>'
        "</lf-options></lf-group>",
    )
    for i in range(8):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent" if i % 2 else "user",
                "parent": root,
                "revision": 1,
                "text": f"Follow-up {i}. " + "This exchange needs its context. " * 5,
            },
        )
    if resolved:
        append_carried_log_record(
            serve.page_dir, {"kind": "resolve", "author": "user", "parent": root}
        )
    page = open_page(browser, url)
    if resolved:
        page.locator(".lf-resolved-summary").click()
    message = page.locator(f'#jobs .lf-msg[data-lf-event="{reply["id"]}"]')
    expect(message.locator("#first-job")).to_be_visible()
    with sending(page, "the first job"):
        message.locator("#mounts").click()
    expect(page.locator("#mounts [role=checkbox]")).to_be_checked()


def test_a_seated_reply_lends_its_widget_to_the_panel_and_takes_it_back(browser, serve):
    """A reply's widget stands in one drawing at a time: the panel's view of the thread
    takes it from the seat while it shows the thread, the seat's body keeps the reply's
    words with nothing in the widget's place, and going back gives the widget to the
    seat. The body is read alone, since the seat's message also draws its reactions."""
    url = serve(SEATED_OBLIGATION_PAGE)
    root = panel_comment(
        serve.page_dir, "Which job should come first?", {"section": "jobs"}
    )
    reply = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Choose the first job.\n\n"
        '<lf-group id="first-job-decision" label="Which job first?">\n<h3 id="first-job-decision-h">Which job first?</h3>'
        '<lf-options id="first-job">'
        '<lf-option id="mounts">Put the mounts back</lf-option>'
        '<lf-option id="camera">Install the camera</lf-option>'
        "</lf-options></lf-group>",
    )
    page = open_page(browser, url)
    seated = page.locator(f'#jobs .lf-msg[data-lf-event="{reply["id"]}"]')
    expect(seated.locator("#first-job")).to_be_visible()
    view = open_panel_thread(page, root)
    expect(view.locator("#first-job")).to_be_visible()
    expect(seated.locator(":scope > .lf-msg-body")).to_have_text(
        re.compile(r"^\s*Choose the first job\.\s*$")
    )
    page.locator(".lf-fp-back").click()
    expect(seated.locator("#first-job")).to_be_visible()


def test_the_browser_s_search_and_leaf_s_travel_open_a_closed_fold(
    browser, serve, subtests
):
    """A closed fold's messages are hidden until found, so the browser's own search
    reaches their words and opens the whole fold, which its toggle closes again; Leaf's
    travel to an element inside one opens it the same way. A link to a passage of text
    drives the browser's search here: it reveals a match by the same algorithm as
    find-in-page, which a test cannot press. Folded messages that were plain `hidden`
    would be skipped by the browser's search.

    A reply's markup, which stands in one drawing at a time, stays in a drawing that
    shows it rather than one that folds the reply away: here the panel, which outranks
    the page's seat but folds the reply under its summary, leaves it in the seat whose
    fold the user opened."""
    url = serve(SEATED_OBLIGATION_PAGE)
    root = panel_comment(serve.page_dir, "Which job first?", {"section": "jobs"})
    asked = append_agent_reply(
        serve.page_dir,
        root,
        "Here is what each job takes.",
        '<p id="folded-note">The mounts take an hour.</p>',
    )
    middle = append_user_reply(serve.page_dir, root, "The mounts, then.")
    last = append_agent_reply(serve.page_dir, root, "Mounts first.")
    append_user_reply(serve.page_dir, root, "Keep the latest visible.")
    summarize_thread(serve.page_dir, asked["id"], last["id"], "The mounts go first.")

    page = open_page(browser, url)
    seat = page.locator(f'#jobs .lf-page-thread[data-lf-thread="{root}"]')
    toggle = seat.locator(".lf-summary-expand")
    covered = [
        seat.locator(f'.lf-msg[data-lf-event="{message["id"]}"]')
        for message in (asked, middle, last)
    ]
    note = covered[0].locator("#folded-note")

    def closed():
        expect(toggle).to_have_attribute("aria-expanded", "false")
        for message in covered:
            expect(message).to_be_hidden()

    def opened():
        expect(toggle).to_have_attribute("aria-expanded", "true")
        expect(toggle).to_have_accessible_name("3 earlier messages")
        for message in covered:
            expect(message).to_be_visible()
        expect(note).to_be_in_viewport()

    # The page drops the key `url` carries, so the address it stands at is the one a
    # same-document navigation keeps; `url` would reload it.
    here = page.url
    page.evaluate("() => { window.stayed = true; }")
    closed()
    page.goto(f"{here}#:~:text=The%20mounts%20take%20an%20hour")
    opened()
    toggle.click()
    closed()

    page.goto(f"{here}#folded-note")
    opened()
    assert page.evaluate("() => window.stayed")

    with subtests.test("the panel leaves a folded reply's markup in the open seat"):
        view = open_panel_thread(page, root)
        expect(view.locator(f'.lf-msg[data-lf-event="{asked["id"]}"]')).to_be_hidden()
        expect(note).to_be_attached()


def test_on_me_opens_the_fold_over_a_message_it_lists(browser, serve):
    """A summary folds messages that still ask something of the user as it folds any
    others, so the thread shows the summary alone. On Me still lists what they ask, and
    its Show lands on the asking message, opening the fold around it."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Is forty megabytes enough?", {"section": "s-how"}
    )
    asked = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root,
            "responds": root,
            "revision": 1,
            "obligation": True,
            "text": "It holds a week of edits. Try a week offline and tell me.",
        },
    )
    corrected = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root,
            "revision": 1,
            "obligation": True,
            "text": "A correction: it holds three days, not a week.",
        },
    )
    summarize_thread(
        serve.page_dir,
        asked["id"],
        corrected["id"],
        "Forty megabytes holds three days of edits; try three days offline.",
    )
    page = open_page(browser, url)
    page.locator('[data-lf-margin-for="s-how"] .lf-margin-marker').click()
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]')
    toggle = card.locator(".lf-summary-expand")
    message = card.locator(f'.lf-msg[data-lf-event="{asked["id"]}"]')
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(message).to_be_hidden()

    open_on_me(page).locator(".lf-fp-on-item").first.get_by_role(
        "button", name="Show", exact=True
    ).click()
    expect(message).to_be_focused()
    expect(message).to_be_visible()
    expect(toggle).to_have_attribute("aria-expanded", "true")


@pytest.mark.parametrize(
    "text", ["It holds three days of edits.", ""], ids=["prose", "bare-fold"]
)
def test_reading_a_summary_reads_the_messages_it_folds(browser, serve, text):
    """The agent folded the messages for the user to read the fold instead, so once
    the fold has been on screen whole, whatever it says of them, they count as read in
    the versions it folds, and nothing offers to open the fold as unread."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Is forty megabytes enough?", {"section": "s-how"}
    )
    answer = append_agent_reply(serve.page_dir, root, "It holds a week of edits.")
    correction = append_agent_reply(serve.page_dir, root, "A correction: three days.")
    summarize_thread(serve.page_dir, answer["id"], correction["id"], text)
    page = open_page(browser, url)
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]')
    with sending(page, "the summary read"):
        page.locator('[data-lf-margin-for="s-how"] .lf-margin-marker').click()
        expect(card.locator(".lf-summary-expand")).to_be_visible()
    marked = {
        (item["message"], item["version"])
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "read"
        for item in event["messages"]
    }
    assert marked == {
        (answer["id"], answer["id"]),
        (correction["id"], correction["id"]),
    }
    expect(card.locator(".lf-summary-expand")).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(page.locator(".lf-next-unread:visible")).to_have_count(0)


def test_a_summary_folds_originals_and_reveals_them(browser, serve):
    """A checkpoint shortens only its admitted range and remains a route to originals.

    The messages before and after the range are controls: hiding either would mean the
    presentation collapsed by position rather than by the summary's declared ids.
    """
    url = serve(SEATED_OBLIGATION_PAGE)
    root = panel_comment(
        serve.page_dir, "Keep the opening question visible.", {"section": "jobs"}
    )
    first = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "The first job establishes the dependency.",
    )
    middle = append_user_reply(
        serve.page_dir, root, "Does that still hold for the camera?"
    )
    last = append_agent_reply(
        serve.page_dir,
        root,
        "Yes. The measured result supports it.",
        "<p>The measured result is 18 minutes.</p>",
    )
    latest = append_user_reply(
        serve.page_dir, root, "Then keep the latest exception visible."
    )
    summary = summarize_thread(
        serve.page_dir,
        first["id"],
        last["id"],
        "Checkpoint digest: the **dependency** remains and the measurement took "
        "`18 minutes`.",
    )

    page = open_page(browser, url)
    card = page.locator(f'#jobs .lf-page-thread[data-lf-thread="{root}"]')
    checkpoint = card.locator(
        f'.lf-thread-checkpoint[data-lf-summary-id="{summary["id"]}"]'
    )
    expand = checkpoint.locator(".lf-summary-expand")
    expect(expand).to_have_attribute("aria-expanded", "false")
    expect(expand).to_have_accessible_name("3 earlier messages")
    expect(checkpoint.locator(".lf-summary-label")).to_have_count(0)
    expect(checkpoint.locator(".lf-summary-text")).to_have_text(
        "Checkpoint digest: the dependency remains and the measurement took 18 minutes."
    )
    expect(checkpoint.locator(".lf-summary-text strong")).to_have_text("dependency")
    expect(checkpoint.locator(".lf-summary-text code")).to_have_text("18 minutes")
    assert (
        checkpoint.locator(".lf-summary-text").evaluate(
            "node => getComputedStyle(node).fontStyle"
        )
        == "normal"
    )
    assert (
        checkpoint.locator(".lf-summary-text code").evaluate(
            "node => getComputedStyle(node).fontStyle"
        )
        == "normal"
    )
    expect(card.locator(f'.lf-msg[data-lf-event="{root}"]')).to_be_visible()
    expect(card.locator(f'.lf-msg[data-lf-event="{latest["id"]}"]')).to_be_visible()
    for message in (first, middle, last):
        expect(card.locator(f'.lf-msg[data-lf-event="{message["id"]}"]')).to_be_hidden()

    expand.focus()
    page.keyboard.press("Enter")
    expect(expand).to_have_attribute("aria-expanded", "true")
    for message in (first, middle, last):
        expect(
            card.locator(f'.lf-msg[data-lf-event="{message["id"]}"]')
        ).to_be_visible()
    expect(expand).to_have_accessible_name("3 earlier messages")
    expand.focus()
    page.keyboard.press("Enter")
    expect(expand).to_have_attribute("aria-expanded", "false")
    expect(card.locator(f'.lf-msg[data-lf-event="{last["id"]}"]')).to_be_hidden()

    # The open fold shows a reply's markup in place.
    card.get_by_role("button", name="3 earlier messages", exact=True).click()
    expect(card.locator(f'.lf-msg[data-lf-event="{last["id"]}"]')).to_contain_text(
        "The measured result is 18 minutes."
    )


def test_previous_progress_messages_can_fold_without_summary_prose(browser, serve):
    """Progress stays available without a digest: the name the agent gave the range
    stands under the press that says what it folds, both whole on a narrow screen."""
    url = serve(SEATED_OBLIGATION_PAGE)
    root = panel_comment(
        serve.page_dir, "Please check the schedule.", {"section": "jobs"}
    )
    first = append_agent_reply(serve.page_dir, root, "Checking the dependency.")
    last = append_agent_reply(serve.page_dir, root, "Checking the camera.")
    answer = append_agent_reply(serve.page_dir, root, "The schedule works.")
    summary = summarize_thread(
        serve.page_dir, first["id"], last["id"], "", label="Previous progress messages"
    )

    page = open_page(browser, url)
    card = page.locator(f'#jobs .lf-page-thread[data-lf-thread="{root}"]')
    checkpoint = card.locator(
        f'.lf-thread-checkpoint[data-lf-summary-id="{summary["id"]}"]'
    )
    label = checkpoint.locator(".lf-summary-label")
    expand = checkpoint.get_by_role("button", name="2 earlier messages")
    expect(label).to_have_text("Previous progress messages")
    expect(checkpoint.locator(".lf-summary-text")).to_have_text(
        "Previous progress messages"
    )
    expect(card.locator(f'.lf-msg[data-lf-event="{answer["id"]}"]')).to_be_visible()
    expect(card.locator(f'.lf-msg[data-lf-event="{first["id"]}"]')).to_be_hidden()
    for width in (390, 320):
        resized(page, width, 900)
        expect(label).to_be_visible()
        label_box = label.bounding_box()
        control_box = expand.bounding_box()
        bounds = checkpoint.bounding_box()
        assert control_box["y"] + control_box["height"] <= label_box["y"] + 0.5, (
            label_box,
            control_box,
        )
        for box in (label_box, control_box):
            assert bounds["x"] <= box["x"]
            assert box["x"] + box["width"] <= bounds["x"] + bounds["width"]
        assert label.evaluate(
            "e => e.scrollWidth <= e.clientWidth && e.scrollHeight <= e.clientHeight"
        )
    expand.focus()
    page.keyboard.press("Enter")
    expect(card.locator(f'.lf-msg[data-lf-event="{first["id"]}"]')).to_be_visible()
    expect(card.locator(f'.lf-msg[data-lf-event="{last["id"]}"]')).to_be_visible()
    expect(expand).to_have_attribute("aria-expanded", "true")
    expand.click()
    expect(card.locator(f'.lf-msg[data-lf-event="{first["id"]}"]')).to_be_hidden()


def test_ephemeral_progress_hides_when_its_held_completion_is_revealed(browser, serve):
    """A step the user wrote after stands above their reply beside the agent's next
    step, and revealing a held answer ends both. A fresh reading shows the same
    transcript without a disclosure."""
    url = serve(SEATED_OBLIGATION_PAGE)
    root = panel_comment(serve.page_dir, "Check the schedule.", {"section": "jobs"})
    thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Checking the camera.",
        ephemeral=True,
    )
    intervening = append_command(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "user",
            "parent": root,
            "text": "Check the mount too.",
        },
    )
    owed = intervening["id"]
    folded = thread_model.post_reply(
        serve.page_dir,
        {"responds": owed},
        "Checking the mount.",
        ephemeral=True,
    )

    def show(page):
        resized(page, 390, 844)
        return page.locator(f'#jobs .lf-page-thread[data-lf-thread="{root}"]')

    page = open_page(browser, url)
    card = show(page)
    identity = "data-lf-event"
    original = card.locator(f'.lf-msg[{identity}="{folded["id"]}"]')
    expect(original).to_be_hidden()
    faces = card.locator(".lf-thread-working")
    expect(faces).to_have_count(2)
    expect(faces.first).to_contain_text("Checking the camera")
    expect(faces.last).to_contain_text("Checking the mount")
    expect(faces.get_by_role("button")).to_have_count(0)

    answer = thread_model.post_reply(
        serve.page_dir, {"responds": owed}, "The schedule works."
    )
    told(page)
    card.get_by_role("button", name="1 new", exact=True).click()
    expect(card.locator(f'.lf-msg[{identity}="{answer["id"]}"]')).to_be_visible()
    expect(card.locator(".lf-thread-checkpoint")).to_have_count(0)
    expect(card.locator(".lf-thread-working")).to_have_count(0)
    expect(original).to_be_hidden()

    fresh = open_page(browser, url)
    fresh_card = show(fresh)
    expect(
        fresh_card.locator(f'.lf-msg[data-lf-event="{answer["id"]}"]')
    ).to_be_visible()
    expect(fresh_card.locator(".lf-thread-checkpoint")).to_have_count(0)
    expect(fresh_card.locator(".lf-thread-working")).to_have_count(0)
    expect(fresh_card.get_by_text("Check the mount too.", exact=True)).to_be_visible()


@pytest.mark.parametrize("engine", ["browser", "webkit_browser"])
def test_a_summary_folds_its_messages_where_they_stand(request, serve, engine):
    """A summary arriving over messages the user is reading, closed and opened again,
    leaves them where they stand: a frame in one keeps the document it loaded, and
    words the user selected in another stay selected. Moving a message would reload its
    frame in WebKit, which lacks `moveBefore`, and lose the selection in every engine.
    The checkpoint groups its messages for assistive technology by `aria-owns`, since
    it doesn't contain them. Its toggle takes a press while those words stay selected.
    Standing on that toggle, the user is in the thread, so their rewrite of a folded
    message draws at once, and the summary stands over it."""
    url = serve(SEATED_OBLIGATION_PAGE)
    root = panel_comment(serve.page_dir, "Which job first?", {"section": "jobs"})
    framed = append_agent_reply(
        serve.page_dir,
        root,
        "Here is the plan.",
        '<iframe title="Plan" srcdoc="<p>The plan</p>"></iframe>',
    )
    worded = append_agent_reply(serve.page_dir, root, "The mounts take an hour.")
    edited = append_user_reply(serve.page_dir, root, "The camera takes two.")
    append_user_reply(serve.page_dir, root, "Keep the latest visible.")

    page = open_page(request.getfixturevalue(engine), url)
    card = page.locator(f'#jobs .lf-page-thread[data-lf-thread="{root}"]')
    frame = card.locator(f'.lf-msg[data-lf-event="{framed["id"]}"] iframe')
    expect(frame).to_be_attached()
    frame.evaluate("""frame => new Promise(loaded => {
      const settle = () => {
        frame.contentWindow.lfKept = true;
        window.lfFrameLoads = 0;
        frame.addEventListener("load", () => window.lfFrameLoads++);
        loaded();
      };
      if (frame.contentDocument?.readyState === "complete") settle();
      else frame.addEventListener("load", settle, {once: true});
    })""")
    words = card.locator(f'.lf-msg[data-lf-event="{worded["id"]}"] .lf-msg-text')
    words.evaluate("""node => {
      const range = document.createRange();
      range.selectNodeContents(node);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
    }""")

    def kept():
        assert frame.evaluate(
            "frame => [frame.contentWindow.lfKept, window.lfFrameLoads]"
        ) == [True, 0]

    summary = summarize_thread(
        serve.page_dir, framed["id"], edited["id"], "Mounts first, then the camera."
    )
    told(page)
    show_held_news(card)
    checkpoint = card.locator(f'[data-lf-summary-id="{summary["id"]}"]')
    toggle = checkpoint.locator(".lf-summary-expand")
    expect(toggle).to_have_attribute("aria-expanded", "true")
    kept()
    selected = page.evaluate("getSelection().toString()")
    assert selected.strip() == "The mounts take an hour."
    covered = [
        card.locator(f'.lf-msg[data-lf-event="{message["id"]}"]')
        for message in (framed, worded, edited)
    ]
    owned = checkpoint.evaluate("node => node.getAttribute('aria-owns').split(' ')")
    assert owned == [message.evaluate("node => node.id") for message in covered]

    # A press, with those words still selected, folds and unfolds them: were the guard
    # that takes a drag ending on a control for the selection's mouseup to ask the whole
    # card, a selection anywhere in it would deaden the toggle. Opening and closing
    # leave the toggle under the user's aim: a thread landing that brought the thread's
    # head back into view would lift the toggle.
    toggle.scroll_into_view_if_needed()
    stood = toggle.evaluate("node => node.getBoundingClientRect().top")
    toggle.click()
    for message in covered:
        expect(message).to_be_hidden()
    rendered(page)
    assert toggle.evaluate("node => node.getBoundingClientRect().top") == stood
    toggle.click()
    expect(covered[0]).to_be_visible()
    rendered(page)
    assert toggle.evaluate("node => node.getBoundingClientRect().top") == stood
    kept()

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "edit",
            "author": "user",
            "message": edited["id"],
            "text": "The camera takes three.",
        },
    )
    told(page)
    expect(covered[2]).to_contain_text("The camera takes three.")
    expect(checkpoint).to_have_count(1)
    expect(card.locator(".lf-thread-news")).to_have_count(0)
    kept()


def test_a_summary_gathering_the_message_the_user_is_on_keeps_them_on_it(
    browser, serve
):
    """A checkpoint arriving over the message the user is located in opens around it.

    The message stays where it stood, now under the checkpoint, and the user stays on a
    link in it rather than dropping to the page. The summary waits behind the thread's
    notice until the user shows it."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Start with the measured constraint.", {"section": "how-store"}
    )
    first = append_agent_reply(serve.page_dir, root, "The constraint still applies.")
    held = append_agent_reply(
        serve.page_dir,
        root,
        "It holds for [the camera](https://example.com/camera) too.",
    )
    append_agent_reply(serve.page_dir, root, "The later result remains visible.")

    page = open_page(browser, url)
    resized(page, 1440, 600)
    card = open_margin_card(page, root)
    link = card.locator(f'.lf-msg[data-lf-event="{held["id"]}"] a')
    link.focus()
    expect(link).to_be_focused()

    summary = summarize_thread(
        serve.page_dir, first["id"], held["id"], "The constraint was confirmed."
    )
    told(page)
    show_held_news(card)
    expect(card.locator(f'[data-lf-summary-id="{summary["id"]}"]')).to_be_visible()
    expect(
        card.locator(
            f'.lf-msg[data-lf-event="{held["id"]}"][data-lf-summary="{summary["id"]}"]'
        )
    ).to_be_visible()
    expect(link).to_be_focused()


@pytest.mark.parametrize(
    ("width", "touch", "count"), [(1440, False, 2), (1400, True, 10)]
)
def test_a_root_summary_keeps_thread_actions_outside_its_fold(
    browser, serve, width, touch, count
):
    """A checkpoint may cover the root turn without hiding thread actions.

    It stands under the actions at the card's width, its press whole on one line, with
    a mouse and under a finger.
    A summary that replaces the checkpoint waits behind the card's notice while the
    user reads it, and drawn once they show it, leaves them on Resolve."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Start with the measured constraint.", {"section": "how-store"}
    )
    reply = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "The constraint still applies.",
    )
    end = reply["id"]
    for number in range(count - 2):
        end = append_agent_reply(serve.page_dir, root, f"Earlier detail {number}.")[
            "id"
        ]
    append_agent_reply(serve.page_dir, root, "The later result remains visible.")
    summary = summarize_thread(
        serve.page_dir, root, end, "The constraint was confirmed."
    )
    context = browser.new_context(
        viewport={"width": width, "height": 600}, has_touch=touch, is_mobile=touch
    )
    page = open_page(browser, url, context=context)
    resized(page, width, 600)

    def activate(control):
        control.tap() if touch else control.click()

    activate(page.locator('[data-lf-margin-for="how-store"] .lf-margin-marker'))
    card = page.locator(f'.lf-margin-preview .lf-page-thread[data-lf-thread="{root}"]')
    checkpoint = card.locator(f'[data-lf-summary-id="{summary["id"]}"]')
    expect(card.get_by_role("button", name="Resolve thread")).to_be_visible()
    alignment = card.evaluate("""card => {
      const region = card.querySelector('.lf-summary-checkpoint').getBoundingClientRect();
      const press = card.querySelector('.lf-summary-expand');
      const words = press.querySelector('[data-lf-room] > span');
      const actions = card.querySelector('.lf-margin-thread-controls').getBoundingClientRect();
      return {regionTop: region.top, actionsBottom: actions.bottom,
        regionWidth: region.width, actionsLeft: actions.left - region.left,
        pressLines: words.getBoundingClientRect().height
          / parseFloat(getComputedStyle(press).lineHeight),
        pressRight: press.getBoundingClientRect().right, regionRight: region.right};
    }""")
    assert alignment["regionTop"] >= alignment["actionsBottom"] - 0.5, alignment
    assert alignment["actionsLeft"] < alignment["regionWidth"], alignment
    assert alignment["pressLines"] <= 1.1, alignment
    assert alignment["pressRight"] <= alignment["regionRight"], alignment
    expect(card.get_by_role("button", name="Close thread")).to_have_count(0)
    root_message = card.locator(
        f'.lf-msg[data-lf-event="{root}"][data-lf-summary="{summary["id"]}"]'
    )
    expect(root_message.locator(":scope > .lf-msg-head")).to_be_hidden()
    expect(root_message.locator(":scope > .lf-msg-body")).to_be_hidden()
    activate(checkpoint.locator(".lf-summary-expand"))
    expect(root_message.locator(":scope > .lf-msg-head")).to_be_visible()
    expect(root_message.locator(":scope > .lf-msg-body")).to_be_visible()
    expect(card.get_by_role("button", name="Resolve thread")).to_be_visible()
    activate(checkpoint.locator(".lf-summary-expand"))
    resolve = card.get_by_role("button", name="Resolve thread")
    resolve.focus()

    summarize_thread(serve.page_dir, root, end, "The constraint was confirmed again.")
    told(page)
    expect_preview_words(
        card.get_by_role("button", name="1 new", exact=True), "1 summary changed"
    )
    expect(checkpoint).to_have_count(1)
    expect(resolve).to_be_focused()

    card.locator(".lf-thread-news").evaluate("node => node.click()")
    expect(checkpoint).to_have_count(0)
    expect(resolve).to_be_focused()

    with sending(page, "resolve after the root summary is replaced"):
        activate(resolve)
    expect(card).to_be_hidden()


def test_a_later_summary_replaces_its_overlap(browser, serve):
    """The browser follows the canonical summary fold as the transcript changes.

    Each change to the fold of a card the user is reading waits behind its notice, with
    the words it would change; shown, a summary opens around the messages being read."""
    url = serve(PANEL_PAGE)
    root = panel_comment(
        serve.page_dir, "Start with the measured constraint.", {"section": "how-store"}
    )
    first = thread_model.post_reply(
        serve.page_dir, {"responds": root}, "The first constraint."
    )
    second = append_user_reply(serve.page_dir, root, "The second constraint.")
    third = append_agent_reply(serve.page_dir, root, "The third constraint.")
    old = summarize_thread(
        serve.page_dir,
        first["id"],
        second["id"],
        "Two constraints were established.",
    )
    page = open_page(browser, url)
    card = open_margin_card(page, root)
    old_checkpoint = card.locator(f'[data-lf-summary-id="{old["id"]}"]')
    expect(old_checkpoint).to_be_visible()
    # The user is located on the summary they opened: a message takes no focus in a card.
    opened = old_checkpoint.locator(".lf-summary-expand")
    opened.click()
    expect(opened).to_be_focused()
    selected_message = card.locator(f'.lf-msg[data-lf-event="{second["id"]}"]')

    replacement = summarize_thread(
        serve.page_dir,
        first["id"],
        third["id"],
        "All three constraints now form one decision.",
    )
    told(page)
    notice = card.get_by_role("button", name="1 new", exact=True)
    expect_preview_words(notice, "1 summary changed")
    expect(old_checkpoint).to_be_visible()
    expect(opened).to_be_focused()
    notice.click()
    expect(card.locator(f'[data-lf-summary-id="{old["id"]}"]')).to_have_count(0)
    checkpoint = card.locator(f'[data-lf-summary-id="{replacement["id"]}"]')
    expect(checkpoint.locator(".lf-summary-expand")).to_have_attribute(
        "aria-expanded", "true"
    )
    expect(selected_message).to_be_visible()
    expect(checkpoint.locator(".lf-summary-text")).to_have_text(
        "All three constraints now form one decision."
    )


def test_expanding_a_summary_keeps_completed_progress_hidden(browser, serve):
    """A summary can cover progress and its answer without resurrecting the progress
    when the user asks to read the original exchange."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Check the schedule.")
    progress = thread_model.post_reply(
        serve.page_dir,
        {"responds": root},
        "Checking the camera.",
        ephemeral=True,
    )
    asked = append_user_reply(serve.page_dir, root, "And the mount?")
    summarize_thread(
        serve.page_dir, progress["id"], asked["id"], "Checking both parts."
    )
    answer = thread_model.post_reply(
        serve.page_dir, {"responds": asked["id"]}, "The schedule works."
    )
    page = open_page(browser, url)
    thread = open_panel_thread(page, root)
    expect(thread.locator(".lf-summary-text")).to_have_text("Checking both parts.")
    thread.locator(".lf-summary-expand").click()
    expect(thread.locator(f'.lf-msg[data-lf-event="{answer["id"]}"]')).to_be_visible()
    expect(thread.locator(f'.lf-msg[data-lf-event="{asked["id"]}"]')).to_be_visible()
    expect(thread.locator(f'.lf-msg[data-lf-event="{progress["id"]}"]')).to_be_hidden()
    expect(thread.locator(".lf-thread-working")).to_have_count(0)
