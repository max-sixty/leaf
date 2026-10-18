"""The On panel: the rows that name each open and answered Ask, their identity, order
and repaints, and the drawer that holds them."""

from datetime import datetime, timedelta

import pytest
from interact_support import append_carried_log_record
from leaf import render_checks as render_checks_model
from leaf.render_checks import wait_until_ready
from playwright.sync_api import expect
from render_cases_interaction import (
    ALL_ITEMS_IN_ORDER,
    ITEM_WITH_CONTEXT_PAGE,
    ITEMS_PAGE,
    CHANGE_SHAPES_PAGE,
    QUEUE_ROW_SAYS,
)
from render_cases_layout import banner_control
from render_harness import (
    LONG_PAGE,
    REPLY_HOST_PAGE,
    active_digit_bindings,
    expect_items_answered,
    holding,
    leaf_page,
    open_page,
    post_event,
    refuse,
    resized,
    root_overflow,
    round_trip,
    said,
    suggestion_control,
    take_browser_errors,
    ticked,
)

from browser.widgets import (
    observe_live_region,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_on_panel_names_an_item_a_message_carries(browser, serve):
    """A decision carried by a reply is a decision, and the On panel has to name it in its words.

    The page holds none of its own, so the one row here is the question Claude put in
    the thread — the AskUserQuestion shape, which reaches a user through the
    panel and through the On panel and nowhere else. It is read here exactly as a group
    on the page is read: the decision's own words, its label first, run together and cut at
    the row's cap. `startswith` for that reason — the cut is the panel's business and
    this is about which words reach it, which is the whole of what the row asserts for
    a page-borne ask two tests below.

    It read `rp-decision` before, and then read the label alone: a veto on chrome threw the
    reading away, and lifting it left the panel over the widget standing in for the
    widget's own chrome, so only a declared label got out. The reading is rooted at the
    ask now, so the layer above it is nobody's apparatus and the words underneath are
    the widget's own."""
    url = serve(REPLY_HOST_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-which",
            "author": "user",
            "revision": 1,
            "text": "Either would do. Which are you leaning towards?",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-which",
            "revision": 1,
            "text": "The second, but the cost lands on you either way:",
            "markup": (
                '<lf-ask id="rp-decision-region"><h3>Which should I write up first?</h3>'
                '<lf-options id="rp-decision" choose>'
                '<lf-option id="rp-now">The migration</lf-option>'
                '<lf-option id="rp-later">The rollback</lf-option>'
                "</lf-options></lf-ask>"
            ),
        },
    )
    page = open_page(browser, url)
    resized(page, 1200, 900)

    banner_control(page, ".lf-queue").click()
    expect(page.locator(".lf-queue-panel")).to_be_visible()
    # The Ask is the user's one item; the comment the reply carried it in is still owed
    # an answer, which is the agent's.
    rows = [row for row in page.evaluate(QUEUE_ROW_SAYS) if row["list"] == "you"]
    assert len(rows) == 1, rows
    assert rows[0]["at"] == "widget:rp-decision", rows
    assert rows[0]["title"].startswith("Which should I write up first?"), rows


def test_a_change_says_which_of_the_three_it_is(browser, serve):
    """An On panel row names its Ask by kind and then by the decision's own opening words,
    and for a change those opening words are whichever half comes first — the current
    text, where there is one. So a deletion arrived in the list under the words it was
    proposing to remove, with nothing to tell it from the insertion above it, which was
    proposing to add its own. Three shapes, one tag, one word for all of them.

    The tag is the right word wherever one tag is one kind of thing, which is every
    other widget here, so the fix is not to teach the On panel about suggestions: the
    entry declares that this tag's word comes from its module (x-word), and the module
    reads it off the slots it holds. The group below is in this page to hold the other
    half of that — a widget declaring nothing still gets its tag, and would go on
    getting it if the declaration were dropped."""
    page = open_page(browser, serve(CHANGE_SHAPES_PAGE))
    resized(page, 1200, 900)

    banner_control(page, ".lf-queue").click()
    expect(page.locator(".lf-queue-panel")).to_be_visible()
    rows = [row for row in page.evaluate(QUEUE_ROW_SAYS) if row["kind"] == "item"]

    assert {r["at"]: r["word"] for r in rows} == {
        "widget:sug-rewrite": "Rewrite",
        "widget:sug-insert": "Insertion",
        "widget:sug-delete": "Deletion",
        "widget:shapes-q": "Options",
    }
    # The words beside the kind are still the element's own, and the two changes that
    # keep a current paragraph still open on it — the reading did not move, only what
    # is said about it.
    said = {r["at"]: r["title"] for r in rows}
    assert said["widget:sug-delete"].startswith("Retries are logged"), said
    assert said["widget:sug-insert"].startswith("Parked jobs"), said


def test_the_on_me_control_opens_open_and_answered_items(browser, serve):
    """The banner's On me control lists every open Ask under On me, in document
    order, and every answered one under Done with its current answer, so the user can
    review and revise. A twelfth widget joins by declaring x-awaits.

    A closed panel holds no rows at all. That is not tidiness: they are the open
    panel's rendering, the banner's counts are the closed panel's, and a hidden list of
    buttons is a set of controls no user can press — which the press sweep sees as
    the page's control set changing under it."""
    page = open_page(browser, serve(ITEMS_PAGE))
    # Wide enough that the panel on the right leaves the answers it lists beside it.
    resized(page, 1920, 900)
    panel = page.locator(".lf-queue-panel")
    expect(panel).to_be_hidden()
    assert page.evaluate(QUEUE_ROW_SAYS) == [], "a closed panel holds no rows"

    control = banner_control(page, ".lf-queue")
    control.focus()
    page.keyboard.press("Enter")
    expect(panel).to_be_visible()
    rows = page.evaluate(QUEUE_ROW_SAYS)
    assert [(r["at"], r["list"]) for r in rows] == [
        *(
            (at, "you")
            for at in [
                "widget:live-question",
                "widget:sug-refill",
                "widget:t-baffles-review",
                "widget:t-bath-choice",
            ]
        ),
        ("widget:honored", "done"),
    ]
    for row in rows:
        assert row["kind"] == "item", row
        assert row["word"] == (
            "Rewrite" if row["at"] == "widget:sug-refill" else "Options"
        ), row
        if row["list"] == "you":
            assert row["w"] > 100 and row["h"] > 20, f"{row['at']}'s row has no size"

    # The Ask leads with its authored heading rather than the first option's answer.
    said = {r["at"]: r for r in rows}
    assert said["widget:live-question"]["title"].startswith(
        "Where should sessions live?"
    ), said
    assert said["widget:t-baffles-review"]["title"].startswith(
        "Are the baffles ready?"
    ), said
    assert said["widget:honored"]["where"].startswith("Answered: Two-tier gates"), said

    # Answered, and the row moves to Done as the route back, saying its current answer.
    # The pick is a move the agent now owes a reply, which is its row and not the Ask's.
    page.locator("#lq-token").click()
    expect_items_answered(page, "2/5")
    expect(page.locator("button.lf-queue-row[data-lf-kind='ask']")).to_have_count(5)
    answered = {r["at"]: r for r in page.evaluate(QUEUE_ROW_SAYS)}
    assert answered["widget:live-question"]["list"] == "done", answered
    assert answered["widget:live-question"]["where"].startswith(
        "Answered: Signed tokens"
    ), answered

    page.locator("[data-lf-margin-for='sug-refill'] .lf-sug-accept").click()
    round_trip(page)
    suggestion = next(
        row for row in page.evaluate(QUEUE_ROW_SAYS) if row["at"] == "widget:sug-refill"
    )
    assert suggestion["list"] == "done", suggestion
    assert suggestion["where"].startswith("Answered: Accepted"), suggestion

    # And closing takes the rest with it, for the reason the docstring gives: a panel
    # that is down is not a list, so it holds nothing to reach and nothing to press.
    banner_control(page, ".lf-queue").focus()
    page.keyboard.press("Enter")
    expect(panel).to_be_hidden()
    assert page.evaluate(QUEUE_ROW_SAYS) == [], "a closed panel keeps its rows"


def test_an_answered_items_words_are_its_widgets_semantic_state(browser, serve):
    """Each family names its answer from the state it was answered with.

    A draft says its current words, a playground the instruction it sent rather than
    whatever its controls show now, and an option the user added is named by the
    rendered words its `add` carried. A `multiple` group answered by Done with no pick
    of the user's names its authored choice."""
    url = serve(
        leaf_page(
            "answer words",
            """
<h1 id="h">Answers</h1>
<lf-ask id="note-ask"><h2>Is this release note right?</h2>
<lf-draft id="note" needed><pre>
Adds --dry-run to every mutating command.
</pre></lf-draft></lf-ask>
<lf-ask id="cache-ask"><h2>Which cache?</h2>
<lf-options id="cache" choose>
  <lf-option id="cache-none"><strong>No cache</strong> Read through.</lf-option>
</lf-options></lf-ask>
<lf-ask id="tags-ask"><h2>Which tags?</h2>
<lf-options id="tags" choose multiple>
  <lf-option id="tag-alpha" chosen><strong>Alpha</strong></lf-option>
  <lf-option id="tag-beta"><strong>Beta</strong></lf-option>
</lf-options></lf-ask>
<lf-ask id="tone-ask"><h2>Which notification?</h2>
<lf-playground id="tone">
  <lf-playground-control name="format" label="Format" kind="choice" value="banner">
    <lf-playground-choice value="banner" label="Banner"></lf-playground-choice>
    <lf-playground-choice value="strip" label="Strip"></lf-playground-choice>
  </lf-playground-control>
  <lf-playground-preview><p id="tone-preview">The notification.</p></lf-playground-preview>
  <lf-playground-output>Build the <lf-playground-value for="format"></lf-playground-value>
  notification.</lf-playground-output>
</lf-playground></lf-ask>
""",
        )
    )
    page = open_page(browser, url)
    door = url.rsplit("/versions/", 1)[0] + "/api/event"
    for widget, action, detail in [
        ("note", "edit", {"value": "Adds --dry-run to every command."}),
        ("cache", "add", {"option": "cache-redis", "text": "**Redis** in front"}),
        ("cache", "choose", {"value": ["cache-redis"]}),
        ("tags", "answer", {}),
        (
            "tone",
            "choose",
            {"values": {"format": "strip"}, "instruction": "Build the strip one."},
        ),
    ]:
        posted = post_event(
            page,
            door,
            data={
                "kind": "action",
                "revision": 1,
                "widget": widget,
                "action": action,
                "detail": detail,
            },
        )
        assert posted.ok, posted.text()
    expect_items_answered(page, "4/4")
    banner_control(page, ".lf-queue").click()
    output = page.locator("#tone lf-playground-output")
    expect(output).to_contain_text("strip")
    page.locator("#tone").get_by_role("radio", name="Banner").click()
    expect(output).to_contain_text("banner")
    answers = {
        "widget:note": "Adds --dry-run to every command.",
        "widget:cache": "Redis in front",
        "widget:tags": "Alpha",
        "widget:tone": "Build the strip one.",
    }
    for at, words in answers.items():
        expect(
            page.locator(f'.lf-queue-row[data-lf-at="{at}"] .lf-queue-where')
        ).to_contain_text(f"Answered: {words}")


def test_item_rows_keep_identity_and_publisher_order_when_the_live_dom_moves(
    browser, serve
):
    """A keyed row follows the published document, not later presentation DOM edits."""
    page = open_page(browser, serve(ITEMS_PAGE))
    banner_control(page, ".lf-queue").click()
    rows = page.locator("button.lf-queue-row")
    expect(rows).to_have_count(len(ALL_ITEMS_IN_ORDER))

    page.evaluate(
        """async () => {
          const {readApplicationPresentation} = await window.__lfCheckApi();
          window.__lfReadItemPresentation = readApplicationPresentation;
          const rows = [...document.querySelectorAll('button.lf-queue-row')];
          window.__lfItemRows = new Map(rows.map(row => [row.dataset.lfAt, row]));
          const honored = document.querySelector('#honored-decision');
          document.querySelector('#live-question-decision').before(honored);
          window.__lfItemRows.get('widget:sug-refill').focus();
          document.dispatchEvent(new Event('lf-presentation'));
        }"""
    )
    page.wait_for_function("__lfReadItemPresentation().pending.length === 0")
    assert rows.evaluate_all("items => items.map(item => item.dataset.lfAt)") == [
        "widget:live-question",
        "widget:sug-refill",
        "widget:t-baffles-review",
        "widget:t-bath-choice",
        "widget:honored",
    ]
    assert rows.evaluate_all(
        "items => items.every(item => window.__lfItemRows.get(item.dataset.lfAt) === item)"
    )
    expect(
        page.locator('.lf-queue-row[data-lf-at="widget:sug-refill"]')
    ).to_be_focused()

    # Removing a presentation node does not rewrite the application inventory. The
    # route and its keyed row remain exactly as they were published.
    page.evaluate(
        """() => {
          document.querySelector('#sug-refill').remove();
          document.dispatchEvent(new Event('lf-presentation'));
        }"""
    )
    page.wait_for_function("__lfReadItemPresentation().pending.length === 0")
    expect(
        page.locator('.lf-queue-row[data-lf-at="widget:sug-refill"]')
    ).to_be_focused()
    assert rows.evaluate_all("items => items.map(item => item.dataset.lfAt)") == [
        "widget:live-question",
        "widget:sug-refill",
        "widget:t-baffles-review",
        "widget:t-bath-choice",
        "widget:honored",
    ]
    assert rows.evaluate_all(
        "items => items.every(item => window.__lfItemRows.get(item.dataset.lfAt) === item)"
    )

    # A row still resolves its current presentation node at activation, but its ordinal
    # comes from the same immutable publication as the route.
    page.evaluate(
        """() => document.querySelector('main').append(
          document.querySelector('#honored-decision'))"""
    )
    observe_live_region(page)
    page.locator(".lf-queue-done > summary").click()
    page.locator('.lf-queue-row[data-lf-at="widget:honored"]').click()
    expect(page.locator("#honored-decision")).to_be_focused()
    expect(page.locator(".lf-live")).to_have_text("Options 1 of 1 done")
    assert "Options 1 of 1 done" in page.evaluate("window.__lfLiveRegionChanges")


def test_pending_action_waits_for_the_item_list_paint_before_retiring(
    held_events, serve
):
    """Receipt settlement cannot retire optimism before the On panel row has painted it."""
    browser, held = held_events
    page = open_page(browser, serve(ITEM_WITH_CONTEXT_PAGE))
    banner_control(page, ".lf-queue").click()
    row = page.locator('button.lf-queue-row[data-lf-at="widget:storage-options"]')
    expect(row).to_have_count(1)
    expect(row).to_have_attribute("data-lf-kind", "item")
    expect(page.locator("[data-lf-queue='you'] .lf-queue-row")).to_have_count(1)
    page.evaluate(
        """async () => {
          const {readApplication, readApplicationPresentation} =
            await window.__lfCheckApi();
          window.__lfReadItemApplication = readApplication;
          window.__lfReadItemPresentation = readApplicationPresentation;
          const list = document.querySelector('lf-queue-list');
          const schedule = list.scheduleUpdate.bind(list);
          let release;
          const held = new Promise(resolve => { release = resolve; });
          window.__lfReleaseItemPaint = release;
          let next = true;
          list.scheduleUpdate = async () => {
            if (next) {
              next = false;
              await held;
            }
            return schedule();
          };
        }"""
    )

    page.locator("#storage-stop").click()
    holding(page, held, 1, "the held answer")
    held.pop(0).continue_()
    page.unroute("**/api/event")
    page.wait_for_function(
        "() => __lfReadItemApplication().unresolved.some("
        "entry => entry.state === 'accepted:logged')"
    )
    assert "queue" in page.evaluate("__lfReadItemPresentation().pending")
    assert page.evaluate("__lfReadItemApplication().unresolved.length") == 1
    expect(page.locator("[data-lf-queue='you'] .lf-queue-row")).to_have_count(1)

    page.evaluate("__lfReleaseItemPaint()")
    round_trip(page)
    page.wait_for_function("() => __lfReadItemApplication().unresolved.length === 0")
    expect(row.locator(".lf-queue-where")).to_contain_text(
        "Answered: Pause offline editing"
    )


def test_the_queue_clock_owns_held_paint_failure_and_retry(browser, serve):
    """Age changes owe a same-epoch ticket and retain their prior rows on failure."""
    url = serve(LONG_PAGE)
    task = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "todo",
            "author": "agent",
            "agent": "Agent",
            "session": "queue-clock",
            "owner": "agent",
            "subject": {"kind": "page"},
            "title": "Review the page",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "todo_end",
            "author": "agent",
            "agent": "Agent",
            "session": "queue-clock",
            "todo": task["id"],
            "outcome": "done",
        },
    )
    page = open_page(browser, url)
    banner_control(page, ".lf-queue").click()
    # The ended to-do is the agent's, in its list's Done.
    page.locator(".lf-queue-tab").nth(1).click()
    page.locator(".lf-queue-done > summary").click()
    row = page.locator("button.lf-queue-row")
    expect(row).to_have_count(1)
    expect(row).to_be_visible()
    expect(row.locator(".lf-queue-where")).to_contain_text("now")
    before = page.evaluate(
        """async () => {
          window.queuePresentation = await window.__lfCheckApi();
          const list = document.querySelector('lf-queue-list');
          window.queueClockRow = list.querySelector('.lf-queue-row');
          const schedule = list.scheduleUpdate.bind(list);
          let release;
          const held = new Promise(resolve => { release = resolve; });
          let armed = true;
          list.scheduleUpdate = async () => {
            if (armed) {
              armed = false;
              window.queueClockHeld = true;
              await held;
            }
            return schedule();
          };
          window.releaseQueueClock = release;
          window.queueClockHeld = false;
          return queuePresentation.readApplicationPresentation();
        }"""
    )
    # Move the browser's clock and let the real feed invalidate the mounted list.
    # Refused reads keep a later answer from recalibrating that clock to server time.
    page.route("**/api/state*", refuse)
    now = datetime.now().astimezone()
    page.clock.set_fixed_time(now + timedelta(minutes=1))
    page.wait_for_function("window.queueClockHeld")
    held = page.evaluate(
        """() => {
          window.queueClockReady = false;
          queuePresentation.whenApplicationPresented().then(() => {
            window.queueClockReady = true;
          });
          return queuePresentation.readApplicationPresentation();
        }"""
    )
    assert "queue" in held["pending"]
    assert held["semanticEpoch"] == before["semanticEpoch"]
    assert held["presentedEpoch"] == before["presentedEpoch"]
    page.wait_for_function("window.queueClockHeld")
    assert page.evaluate("queueClockReady") is False
    expect(row.locator(".lf-queue-where")).to_contain_text("now")
    # The next claim supersedes the held reading. Failing its paint must travel
    # through the same retained-list proof as a failed semantic publication.
    page.evaluate(
        """() => {
          const list = document.querySelector('lf-queue-list');
          const render = list.render.bind(list);
          list.render = () => {
            list.render = render;
            throw new Error('deliberate Queue clock failure');
          };
        }"""
    )
    page.clock.set_fixed_time(now + timedelta(minutes=2))
    ticked(page)
    page.evaluate("releaseQueueClock()")
    page.wait_for_function("queueClockReady")
    expect(row.locator(".lf-queue-where")).to_contain_text("now")
    assert row.evaluate("node => node === window.queueClockRow")
    assert [said(error) for error in take_browser_errors(page)] == [
        "leaf: Presentation failed: deliberate Queue clock failure"
    ]
    page.clock.set_fixed_time(now + timedelta(minutes=3))
    ticked(page)
    expect(row.locator(".lf-queue-where")).to_contain_text("3m")
    expect(row).to_be_visible()
    assert row.evaluate("node => node === window.queueClockRow")
    after = page.evaluate("queuePresentation.readApplicationPresentation()")
    assert after["semanticEpoch"] == before["semanticEpoch"]
    assert after["presentedEpoch"] == before["presentedEpoch"]
    assert after["pending"] == []


def test_failed_item_paints_report_once_and_retain_their_prior_faces(browser, serve):
    """A failed Queue list and a failed Lit face on the banner's bulk control, failing
    in the same publication, each report once and keep their earlier rows and controls
    usable."""
    page = open_page(browser, serve(ITEMS_PAGE))
    answer_all = page.locator(".lf-answer-all")
    expect_items_answered(page, "1/5")
    expect(answer_all).to_have_text("Accept all (1)")
    banner_control(page, ".lf-queue").click()
    rows = page.locator("button.lf-queue-row")
    expect(rows).to_have_count(len(ALL_ITEMS_IN_ORDER))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.evaluate(
        """async () => {
          const {readApplicationPresentation, whenApplicationPresented} =
            await window.__lfCheckApi();
          window.__lfReadItemPresentation = readApplicationPresentation;
          const list = document.querySelector('lf-queue-list');
          window.__lfItemRows = [...list.querySelectorAll('button.lf-queue-row')];
          window.__lfItemBulk = document.querySelector('.lf-answer-all');
          const bulkFace = window.__lfItemBulk.querySelector('lf-item-banner-face');
          for (const [face, name] of [[list, 'Queue list'], [bulkFace, 'Ask banner']]) {
            const render = face.render.bind(face);
            face.render = () => {
              face.render = render;
              throw new Error(`deliberate ${name} failure`);
            };
          }
          window.__lfItemListCurrentReady = false;
          window.__lfWaitForItemListCurrent = () =>
            void whenApplicationPresented().then(() => {
              window.__lfItemListCurrentReady = true;
            });
        }"""
    )
    page.locator("#lq-token").click()
    holding(page, held, 1, "the semantic answer")
    page.evaluate("__lfWaitForItemListCurrent()")
    page.wait_for_function("__lfItemListCurrentReady")
    assert page.evaluate("__lfReadItemPresentation().pending.length") == 0
    expect_items_answered(page, "1/5")
    expect(answer_all).to_have_text("Accept all (1)")
    expect(rows).to_have_count(len(ALL_ITEMS_IN_ORDER))
    assert rows.evaluate_all(
        "items => items.every((item, at) => item === window.__lfItemRows[at])"
    )
    assert answer_all.evaluate("control => control === window.__lfItemBulk")
    rows.first.click()
    expect(page.locator("#live-question-decision")).to_be_focused()
    assert sorted(said(error) for error in take_browser_errors(page)) == [
        "leaf: Presentation failed: deliberate Ask banner failure",
        "leaf: Presentation failed: deliberate Queue list failure",
    ]
    holding(page, held, 2, "the gesture and the page's report of its failure")
    for route in held:
        route.continue_()
    page.unroute("**/api/event")
    round_trip(page)


def test_a_completed_item_persists_and_its_done_row_can_revise_by_keyboard(
    browser, serve
):
    """Completion keeps the same concise route back through the existing action model:
    the On panel's Done row, reached and opened from the keyboard, arrives at the Ask."""
    page = open_page(browser, serve(ITEM_WITH_CONTEXT_PAGE))
    resized(page, 1200, 900)
    expect_items_answered(page, "0/1")

    page.locator("#storage-stop").click()
    round_trip(page)
    expect_items_answered(page, "1/1")

    page.reload(wait_until="load")
    wait_until_ready(page)
    expect_items_answered(page, "1/1")

    # With nothing on the user, the panel opens on its Done's door; Enter opens it and
    # the row below is the Ask's.
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    expect(page.locator(".lf-queue-done > summary")).to_be_focused()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowDown")
    row = page.locator(
        '.lf-queue-done .lf-queue-row[data-lf-at="widget:storage-options"]'
    )
    expect(row).to_be_focused()
    expect(row.locator(".lf-queue-where")).to_contain_text(
        "Answered: Pause offline editing"
    )

    page.keyboard.press("Enter")
    expect(page.locator("#storage-decision")).to_be_focused()
    assert active_digit_bindings(page) == "1–3"
    page.keyboard.press("1")
    round_trip(page)
    expect(page.locator("#storage-evict")).to_have_attribute("chosen", "")
    expect_items_answered(page, "1/1")
    expect(row.locator(".lf-queue-where")).to_contain_text(
        "Answered: Drop the oldest documents"
    )


def test_an_answered_boxless_item_reopens_on_its_visible_revision_control(
    browser, serve
):
    """An On panel row's arrival preserves Ask semantics when its source has no box to focus."""
    page = open_page(browser, serve(CHANGE_SHAPES_PAGE))
    resized(page, 560, 620)
    expect_items_answered(page, "0/4")

    page.locator("[data-lf-margin-for='sug-delete'] .lf-sug-accept").click()
    round_trip(page)
    expect(page.locator("#sug-delete")).to_be_hidden()
    expect_items_answered(page, "1/4")

    banner_control(page, ".lf-queue").click()
    row = page.locator('.lf-queue-row[data-lf-at="widget:sug-delete"]')
    expect(row.locator(".lf-queue-where")).to_contain_text("Answered: Accepted")
    page.locator(".lf-queue-done > summary").click()
    row.click()
    expect(page.locator(".lf-queue-panel")).to_be_hidden()
    undo = suggestion_control(page, "sug-delete", "undo", visible=False)
    expect(undo).to_be_focused()
    assert active_digit_bindings(page) == "1"

    page.keyboard.press("1")
    round_trip(page)
    expect(page.locator("#sug-delete")).to_be_visible()
    expect_items_answered(page, "0/4")


def test_a_drawer_the_user_left_open_comes_back_open(browser, serve):
    """Reloading is not resetting: a drawer someone stood up to watch stays stood, the
    rule the thread panel already keeps. Which makes the reload the one moment a
    drawer is put up by something other than a press, and that is where it broke — the
    restore ran while the module was still evaluating and filled the drawer from a
    reading of the page's active Asks declared further down the file, so the user who
    had left it open got a ReferenceError instead of a page.

    Nothing static could have caught it and neither could the render gate, which
    presses no keys and so never has a drawer to restore. It took a user with the
    drawer open pressing reload, which is what this now is."""
    page = open_page(browser, serve(ITEMS_PAGE))
    banner_control(page, ".lf-queue").click()
    drawer = page.locator(".lf-queue-panel")
    expect(drawer).to_be_visible()
    expect(page.locator("button.lf-queue-row")).to_have_count(len(ALL_ITEMS_IN_ORDER))

    page.reload(wait_until="load")
    wait_until_ready(page)
    expect(drawer).to_be_visible()
    expect(page.locator("button.lf-queue-row")).to_have_count(len(ALL_ITEMS_IN_ORDER))


def test_a_drawer_sliding_out_takes_no_focus(browser, serve):
    """A drawer on its way out is already gone to the user: closing it from its door
    leaves none of its rows reachable while it slides away, and reopening it brings them
    back. Threads taking its place on the shared right edge is a swap with no slide, so
    the rows are gone at once."""
    page = open_page(browser, serve(ITEMS_PAGE))
    resized(page, 1200, 900)
    banner_control(page, ".lf-queue").click()
    expect(page.locator(".lf-queue-panel")).to_be_visible()
    render_checks_model.wait_for_probe(page, "pageSettled")
    # The drawer's own slide in has ended, so any animation read below is the swap's.
    page.wait_for_function(
        "() => document.querySelector('.lf-queue-panel').getAnimations().length === 0"
    )
    swapped = page.evaluate(
        """() => {
          document.querySelector('.lf-threads-toggle').click();
          const drawer = document.querySelector('.lf-queue-panel');
          const threads = document.querySelector('.lf-thread-panel');
          return { shown: drawer.checkVisibility(),
                   sliding: [drawer, threads].map((node) => node.getAnimations().length) };
        }"""
    )
    assert swapped == {"shown": False, "sliding": [0, 0]}, swapped
    expect(page.locator(".lf-thread-panel")).to_be_visible()

    banner_control(page, ".lf-queue").click()
    expect(page.locator(".lf-queue-panel")).to_be_visible()
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    render_checks_model.wait_for_probe(page, "pageSettled")
    leaving = page.evaluate(
        """() => {
          document.querySelector('.lf-queue').click();
          const drawer = document.querySelector('.lf-queue-panel');
          const row = drawer.querySelector('button.lf-queue-row');
          row.focus();
          return { shown: drawer.checkVisibility(), inert: drawer.inert,
                   focused: document.activeElement === row };
        }"""
    )
    assert leaving == {"shown": True, "inert": True, "focused": False}, leaving
    expect(page.locator(".lf-queue-panel")).to_be_hidden()

    banner_control(page, ".lf-queue").click()
    row = page.locator("button.lf-queue-row").first
    row.focus()
    expect(row).to_be_focused()


def test_a_drawer_standing_over_most_of_an_item_clears_for_it(browser, serve):
    """The drawer stands over the page, so an Ask its row sends the user to may be under it.
    Drawn wide but still leaving a usable page, the drawer stays live and stands over most of
    the column; pressing a row then clears the drawer, as travel clears any surface hiding
    its destination, rather than landing the user on a decision they cannot see. Beside
    a drawer at its default width the same press keeps the drawer up."""
    page = open_page(browser, serve(ITEMS_PAGE))
    resized(page, 1440, 900)
    drawer = page.locator(".lf-queue-panel")
    row = page.locator("button.lf-queue-row[data-lf-at='widget:t-bath-choice']")
    covering = page.locator("html[data-lf-covering-surface]")

    banner_control(page, ".lf-queue").click()
    expect(drawer).to_be_visible()
    row.click()
    expect(page.locator("#t-bath-decision")).to_be_focused()
    expect(drawer).to_be_visible()

    # The edge is the panel's left one, so the arrow away from the right widens it.
    edge = page.locator(".lf-queue-panel > .lf-edge")
    edge.focus()
    for _ in range(21):
        page.keyboard.press("ArrowLeft")
    width = drawer.evaluate("el => el.getBoundingClientRect().width")
    assert 1440 - width >= 320 and width > 360 + 360, width
    expect(covering).to_have_count(0)
    row.click()
    expect(drawer).to_be_hidden()
    expect(page.locator("#t-bath-decision")).to_be_focused()


def test_a_row_stands_the_user_on_the_item_it_names(browser, serve):
    """Pressing a row uses the same arrival as the Ask walk. It scrolls there, rings the
    Ask, and stands the user on its opening context; its controls are the next Tab
    stops, while the numeric action map is already available for direct revision.

    The ring lands in two places for one reason: the decision on the page and its row on the
    drawer are two surfaces showing where the user is standing, painted from the one
    reading of it (markHere), so neither can say something the other doesn't."""
    page = open_page(browser, serve(ITEMS_PAGE))
    # Narrow enough that the drawer covers the page. A destination selected from a covering
    # sheet must dismiss the sheet; otherwise all the focus and scrolling below happen
    # correctly behind an opaque surface.
    resized(page, 560, 620)
    banner_control(page, ".lf-queue").click()
    expect(page.locator(".lf-queue-panel")).to_be_visible()

    # The last of the four, which a short window leaves well off screen.
    on_screen = """() => {
      const r = document.querySelector('#t-bath-decision').getBoundingClientRect();
      return r.top >= 0 && r.bottom <= innerHeight;
    }"""
    assert not page.evaluate(on_screen), (
        "the fixture must start with #t-bath-decision off screen"
    )

    page.locator("button.lf-queue-row[data-lf-at='widget:t-bath-choice']").click()
    expect(page.locator(".lf-queue-panel")).to_be_hidden()
    page.wait_for_function(on_screen)
    expect(page.locator("#t-bath-decision")).to_be_focused()
    expect(page.locator("#t-bath-decision")).to_have_attribute("data-lf-item", "1")
    page.keyboard.press("Tab")
    expect(page.locator("#t-bath-decision .lf-pick").first).to_be_focused()
    # The covering drawer has gone, so its projected rows go with it. The page carries the
    # one standing mark rather than leaving a second, hidden authority in the closed drawer.
    marked = page.evaluate(
        """() => [...document.querySelectorAll('[data-lf-item]')]
             .map((e) => e.id || e.getAttribute('data-lf-at'))"""
    )
    assert sorted(set(marked)) == ["t-bath-decision"], marked


def test_the_on_panel_covers_the_page_only_where_it_leaves_no_usable_page(
    browser, serve
):
    """An On panel row is a way around this page, so pressing one sends the user into the
    document, and the page beside the drawer stays live for it. Where the drawer would leave
    less than a usable page beside it, it covers instead — the rule the panel follows,
    asked of the room the drawer leaves rather than of the window, so a narrow window and a
    drawer drawn wide on a wide one come to the same answer, and a user who has learned one
    edge has learned the other. Either way the drawer stands over the page and moves none
    of it."""
    page = open_page(browser, serve(ITEMS_PAGE))
    geometry = """() => ({
      column: Math.round(document.querySelector('main').getBoundingClientRect().left),
      drawer: Math.round(
        document.querySelector('.lf-queue-panel').getBoundingClientRect().left),
    })"""

    resized(page, 1200, 800)
    closed = page.evaluate(geometry)
    banner_control(page, ".lf-queue").click()
    expect(page.locator(".lf-queue-panel")).to_be_visible()
    covering = page.locator("html[data-lf-covering-surface='lf-queue']")
    expect(covering).to_have_count(0)
    wide = page.evaluate(geometry)
    assert wide["column"] == closed["column"], "the drawer moved the column"
    assert root_overflow(page) == 0, "the page scrolls sideways with the drawer up"

    # At 610 the default 420px panel would leave 190, short of a usable page.
    resized(page, 610, 800)
    expect(covering).to_have_count(1)
    assert root_overflow(page) == 0
    resized(page, 1200, 800)
    expect(covering).to_have_count(0)

    # Drawn wide enough on a wide window, the strip is more than the page can give,
    # so the drawer covers. One step back and the page has its usable width again.
    edge = page.locator(".lf-queue-panel > .lf-edge")
    edge.focus()
    for _ in range(40):
        if covering.count():
            break
        page.keyboard.press("ArrowLeft")
    expect(covering).to_have_count(1)
    left = page.evaluate(
        """() => innerWidth
             - document.querySelector('.lf-queue-panel').getBoundingClientRect().width"""
    )
    assert left < 320, f"the drawer covered with {left}px of page beside it"
    page.keyboard.press("ArrowRight")
    expect(covering).to_have_count(0)
    assert page.evaluate(geometry)["column"] == closed["column"]


def test_one_drawer_stands_at_a_time(browser, serve, other_leaf):
    """The On panel on the right and Leaves on the left are both auxiliary surfaces, so
    opening either closes the other. Which one is up
    is one fact in one place: a boolean per drawer would be one guarantee written twice,
    and the two would first disagree the day a third surface opened one without closing
    the other — leaving two drawers over one edge with the lower unreachable.

    Escape names whichever is up rather than saying "close the drawer" over two of
    them, which is the rung the user is actually holding.

    The `other_leaf` fixture is the whole reason the leaves drawer has anything to show:
    a drawer of one — the page the user is already on — is not worth a control, so
    without a neighbour `g L` is unavailable and there is no second drawer to be exclusive
    with."""
    page = open_page(browser, serve(ITEMS_PAGE))
    decisions, leaves = (
        page.locator(".lf-queue-panel"),
        page.locator(".lf-others-panel"),
    )

    banner_control(page, ".lf-queue").click()
    expect(decisions).to_be_visible()
    expect(leaves).to_be_hidden()

    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(leaves).to_be_visible()
    expect(decisions).to_be_hidden()

    # Leaves is a modal covering workspace, so its scrim correctly makes the page and
    # banner inert. The global destination remains the route from one drawer to the other.
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    expect(decisions).to_be_visible()
    expect(leaves).to_be_hidden()

    # Exchanging one covering drawer for another is lateral, so one Escape closes the
    # drawer open and lands the user on the page; the drawer it replaced is not put
    # back, and they reach it the way they reached it the first time.
    page.keyboard.press("Escape")
    expect(decisions).to_be_hidden()
    expect(leaves).to_be_hidden()
