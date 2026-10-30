"""The document's shared, semantic margin map."""

import re

import pytest
from click.testing import CliRunner
from interact_support import (
    append_carried_log_record,
)
from playwright.sync_api import expect
from render_cases_interaction import (
    OBLIGATION_PAGE,
)
from render_cases_layout import (
    toggle_queue,
)
from render_harness import (
    LONG_PAGE,
    PANEL_THREAD,
    draft_control,
    margins_laid_out,
    navigate,
    open_page,
    resized,
    sending,
    ticked,
    told,
    write,
)

from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed

from browser.margin import (
    ACTION_ON_OBLIGATION,
    CARD_AND_REPLY,
    COMMENT_ON_OBLIGATION,
    DRAFTING_CARD,
    LONG_THREAD_ROOT,
    MARGIN_ACTIONS_PAGE,
    MARGIN_EDITOR_ROOTS,
    WORDS_RIGHT,
    _focused_editor_caret,
    drafting_in_a_short_card,
    open_long_thread,
    resized_shell,
    send_anchored_comment,
)
from render_harness import comment_note, example_media, leaf_page

MARGIN_ACTIONS_EVENTS = (
    {
        "kind": "comment",
        "author": "agent",
        "revision": 1,
        "text": "Which space is easier to find?",
        "anchor": {"section": "s-crowded"},
    },
    {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "token": "prioritize",
        "anchor": {"section": "s-crowded"},
    },
)


# Each suggestion's pin, folded or not, where its controls stand on the page, and where
# its words end.
SUGGESTION_PINS = """(ids) => ids.map((id) => {
  const row = document.querySelector(`[data-lf-margin-for="${id}"]`);
  const end = [...document.getElementById(id).getClientRects()].at(-1);
  return [id, row.hasAttribute('data-lf-folded'),
    [...row.querySelectorAll('.lf-margin-entry')].filter((e) => e.checkVisibility())
      .map((e) => { const b = e.getBoundingClientRect();
        return [e.getAttribute('data-lf-margin-entry-key'), b.left, b.top + scrollY]; }),
    end.right];
})"""


# An obligation in the middle of a long page, so its margin host can be scrolled out from under
# a parked pointer and back.
OBLIGATION_IN_LONG_PAGE = LONG_PAGE.replace(
    "<p id='p20'>",
    """<lf-ask id="route-ask"><h2>Which route should the walk follow?</h2>
<lf-options id="route" choose>
  <lf-option id="route-garden">Through the garden</lf-option>
  <lf-option id="route-river">Along the river</lf-option>
</lf-options></lf-ask>
<p id='p20'>""",
    1,
)


# Two threaded passages with room above and below to scroll them: one paragraph in the
# right cell of a two-up pair, as a before-and-after comparison sets it, so its words end
# short of the column and leave room on their left; and a suggestion whose cluster a
# thread and two reactions in force crowd.
THREAD_CARD_PAGE = leaf_page(
    "Thread cards",
    """
<h1 id="t">Workshop agenda</h1>
{before}
<div id="title-pair">
  <section id="title-before">
    <p class="eyebrow">Before · untitled</p>
    <p id="thread-pending"><strong>An untitled thread.</strong> The workshop schedule
    leaves lunch open. The agent asked without naming the thread, so its row reads the
    question itself until the agent gives it a short name.</p>
  </section>
  <section id="title-after">
    <p class="eyebrow">After · title assigned</p>
    <p id="thread-text"><strong>An existing thread.</strong> The sample agenda has room
    for one more topic. Its speech-bubble control is green, and hovering it shows “On
    you” under the label. The image question still needs an answer even though the
    agent added a later progress message. Open the control and reply: the control turns
    blue as the thread comes back to the agent.</p>
  </section>
</div>
{between}
<p id="crowded-line"><strong>Combine roles.</strong> Use the
  <lf-suggestion id="crowded"><lf-old>courtyard</lf-old><lf-new>covered terrace</lf-new></lf-suggestion>
  for the practice session. “Accept” and “Reject” act immediately; “Thread” and “⋯”
  disclose more; a reaction mark stands only while its reaction does.</p>
{after}
""",
    head="""<style>
#title-pair {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 14rem), 1fr));
  gap: var(--sp-4);
  margin-block: var(--sp-4);
  max-width: 54rem;
}}
</style>""",
).format(
    **{
        part: "\n".join(
            f"<p id='{part}-{i}'>{part.title()} {i}. " + "Filler. " * 30 + "</p>"
            for i in range(count)
        )
        for part, count in (("before", 8), ("between", 4), ("after", 10))
    }
)


def _seed_card_threads(page_dir):
    """Seed THREAD_CARD_PAGE's two threads and the crowded cluster's reactions, and
    return the two threads' ids: the one on `#thread-text`, then the one on `#crowded`.

    The `#thread-text` thread is the gallery's, its question carrying the pasted room
    photo, so its transcript is as tall as a real one: a card whose height falls short
    clips it."""
    image = "051bee487bfb5d13.png"
    (page_dir / "media").mkdir(exist_ok=True)
    (page_dir / "media" / image).write_bytes((example_media() / image).read_bytes())

    def comment(event):
        return append_carried_log_record(
            page_dir, {"kind": "comment", "revision": 1, **event}
        )

    text = comment(
        {
            "author": "agent",
            "text": "I moved the practice exercise before lunch and left the rest of "
            "the agenda unchanged.",
            "anchor": {
                "section": "thread-text",
                "quote": "The sample agenda has room for one more topic.",
            },
        }
    )
    for reply, question in (
        (
            (
                "The pasted image stays inside this thread. Does this crop show "
                "enough of the room, or should I reshoot it wider?\n\n"
                f"![Pasted image](/media/{image})"
            ),
            True,
        ),
        (
            (
                "I also added the room number to the agenda. The image question "
                "above still needs your answer."
            ),
            False,
        ),
    ):
        append_carried_log_record(
            page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "parent": text["id"],
                "revision": 1,
                "text": reply,
                **({"obligation": True} if question else {}),
            },
        )
    crowded = comment(
        {
            "author": "agent",
            "text": "Which space is easier to find? This thread shares its target with "
            "the decision and reaction controls.",
            "anchor": {"section": "crowded"},
        }
    )
    for token in ("keep", "change"):
        comment({"author": "user", "token": token, "anchor": {"section": "crowded"}})
    return text["id"], crowded["id"]


def _open_thread(page, target, thread_id):
    """Enter a thread from its target's comment note."""
    page.locator(f"#{target}").scroll_into_view_if_needed()
    comment_note(page, f"#{target}").press("Enter")
    walked = page.locator(".lf-margin-preview .lf-page-thread")
    expect(walked).to_have_attribute("data-thread", thread_id)
    expect(walked).to_be_focused()
    rendered(page)


# Read the card alongside its target, control cluster, and available message width.
THREAD_CARD_GEOMETRY = """() => {
  const main = document.querySelector('main').getBoundingClientRect();
  const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
  const controls = document.querySelector('[data-lf-margin-for] [aria-expanded="true"]')
    .closest('[data-lf-margin-for]').getBoundingClientRect();
  const reply = document.querySelector('.lf-margin-thread leaf-text')
    .getBoundingClientRect();
  return {
    mainLeft: main.left, mainRight: main.right,
    wordsRight: main.right - parseFloat(getComputedStyle(document.querySelector('main'))
      .paddingRight),
    controlsLeft: controls.left, controlsRight: controls.right,
    controlsTop: controls.top,
    controlsBottom: controls.bottom,
    cardLeft: card.left, cardRight: card.right, cardTop: card.top,
    cardBottom: card.bottom, cardWidth: card.width,
    replyWidth: reply.width, innerWidth: window.innerWidth,
    minimum: parseFloat(getComputedStyle(document.querySelector('.lf-margin-preview'))
      .getPropertyValue('--thread-card-min')),
    preferred: parseFloat(getComputedStyle(document.querySelector('.lf-margin-preview'))
      .getPropertyValue('--thread-card')),
  };
}"""


# The rail and the narrowest pin; 700's pin takes the same Page Map route.
@pytest.mark.parametrize("width", [1440, 390])
def test_draft_and_page_map_reaction_actions_stay_reachable(browser, serve, width):
    """A draft's local Save and Cancel stay reachable while it is edited, and the save outlasts
    a reload; the Undo control of a reaction in force is reachable from the Page Map by keyboard
    and withdraws the reaction."""
    page = open_page(browser, serve(MARGIN_ACTIONS_PAGE, events=MARGIN_ACTIONS_EVENTS))
    resized(page, width, 900)
    draft_control(page, "edit", "d-draft").click()
    editor = page.locator("#d-draft leaf-text")
    body = "The workshop moved outdoors.\nBring a folding chair."
    write(editor, body)
    expect(draft_control(page, "save", "d-draft")).to_be_visible()
    expect(draft_control(page, "cancel", "d-draft")).to_be_visible()
    with sending(page, "save the draft"):
        draft_control(page, "save", "d-draft").click()
    expect(page.locator("#d-draft .lf-draft-body")).to_have_text(
        body, use_inner_text=True
    )
    navigate(page, page.url)
    expect(page.locator("#d-draft .lf-draft-body")).to_have_text(
        body, use_inner_text=True
    )

    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    reaction = next(
        event
        for event in events_model.read_events(serve.page_dir)
        if event.get("token") == "prioritize"
    )
    reaction_actions = dialog.locator(
        '[data-lf-margin-entry-owner="reactions"]'
        f'[data-lf-margin-entry-key="reaction:{reaction["id"]}:open"]'
    )
    expect(reaction_actions).to_have_attribute(
        "aria-label", "prioritize reaction actions"
    )
    reaction_actions.click()
    expect(dialog).to_be_visible()
    remove = dialog.get_by_role("button", name="Undo prioritize reaction", exact=True)
    expect(remove).to_be_focused()
    page.keyboard.press("Escape")
    expect(remove).to_be_hidden()
    expect(reaction_actions).to_be_focused()
    expect(dialog).to_be_visible()
    reaction_actions.click()
    expect(remove).to_be_focused()
    with sending(page, "the withdrawal of the Page Map reaction"):
        remove.click()
    expect(dialog).to_be_hidden()
    expect(
        page.locator(
            f'[data-lf-margin-for="s-crowded"] [data-event="{reaction["id"]}"]'
        )
    ).to_have_count(0)
    last = events_model.read_events(serve.page_dir)[-1]
    assert (last["kind"], last["undoes"]) == ("undo", reaction["id"])


def test_agent_status_leaves_the_margin_transcript_where_the_user_scrolled_it(
    browser, serve
):
    """A state read places the card, and placing the card moves nothing inside it.

    The user is located in the reply while reading partway up the transcript, then at its
    end, and the agent's working and waiting statuses arrive meanwhile. Scroll
    anchoring is off on the transcript. It can restore a place a placement disturbed
    within one task: the headless shell restored it in every run, while headed Chrome
    scrolled by a real gesture kept the disturbed place. With it off, the reading is
    what the placement itself did.
    """
    page, preview, transcript = open_long_thread(browser, serve)
    transcript.evaluate("list => list.style.overflowAnchor = 'none'")
    preview.get_by_role("textbox", name="Reply", exact=True).click()
    expect(preview.locator("leaf-text")).to_be_focused()
    place = "list => [list.scrollTop, list.scrollHeight - list.clientHeight]"
    settled = (
        "() => new Promise(resolve => "
        "requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )

    def statuses():
        for name, command in (
            (
                "working",
                ["task", "start", str(serve.page_dir), "c" * 32, "--text", "Reading"],
            ),
            ("waiting", ["page", "open", str(serve.page_dir)]),
        ):
            result = CliRunner().invoke(cli_model.cli, command)
            assert result.exit_code == 0, result.output
            told(page)
            page.evaluate(settled)
            ticked(page)
            yield name, transcript.evaluate(place)

    partway = transcript.evaluate(place)
    assert 0 < partway[0] < partway[1] - 20, partway
    assert {name: offset for name, (offset, _) in statuses()} == {
        "working": partway[0],
        "waiting": partway[0],
    }

    transcript.hover()
    page.mouse.wheel(0, partway[1])
    page.wait_for_function(
        "list => list.scrollTop >= list.scrollHeight - list.clientHeight - 1",
        arg=transcript.element_handle(),
    )
    end = transcript.evaluate(place)
    assert {name: offset for name, (offset, _) in statuses()} == {
        "working": end[0],
        "waiting": end[0],
    }


@pytest.mark.parametrize("wrapping", [False, True])
def test_an_inline_thread_keeps_one_readable_card_across_page_claims(
    browser, serve, wrapping
):
    """An accepted comment preserves its editor frame, wrapping and reply, using
    the marker strip where clearing it would narrow the message."""
    sidebar_page = OBLIGATION_PAGE.replace(
        '<main class="layout-column">',
        '<main class="layout-sidebar"><aside><div class="layout-track">Page reference</div></aside>'
        '<div class="layout-column">',
        1,
    ).replace("</main>", "</div></main>", 1)
    page = open_page(
        browser,
        serve(sidebar_page, events=[COMMENT_ON_OBLIGATION]),
        init_script=MARGIN_EDITOR_ROOTS,
    )
    resized(page, 1200, 900)
    # The editor measures terminal spaces; sent Markdown does not paint them.
    text = (
        ("Check the January failure mode before accepting this design. " * 3).rstrip()
        if wrapping
        else "Check the January failure mode."
    )
    editor_start, narrow_lines = send_anchored_comment(page, text)
    assert narrow_lines > 1 if wrapping else narrow_lines == 1
    page.locator(".lf-margin-thread").get_by_role(
        "textbox", name="Reply", exact=True
    ).click()

    narrow = page.evaluate(THREAD_CARD_GEOMETRY)
    assert narrow["innerWidth"] - 8 - (narrow["wordsRight"] + 8) < narrow["minimum"], (
        narrow
    )
    assert narrow["minimum"] <= narrow["cardWidth"] <= narrow["preferred"], narrow
    assert narrow["replyWidth"] >= 160, narrow
    # The sent thread retains the comment frame's width and inline start.
    # Its control cluster remains clear when the card takes the lower route.
    assert narrow["cardLeft"] == pytest.approx(editor_start, abs=0.5), narrow
    assert narrow["cardLeft"] < narrow["mainRight"], narrow
    # Clear of its words under or over them, the card leaves its cluster uncovered.
    assert (
        narrow["cardBottom"] <= narrow["controlsTop"]
        or narrow["cardTop"] >= narrow["controlsBottom"]
        or narrow["cardRight"] <= narrow["controlsLeft"]
        or narrow["cardLeft"] >= narrow["controlsRight"]
    ), narrow

    page.close()

    page = open_page(
        browser,
        serve(OBLIGATION_PAGE, events=[COMMENT_ON_OBLIGATION]),
        init_script=MARGIN_EDITOR_ROOTS,
    )
    resized(page, 1920, 900)
    editor_start, wide_lines = send_anchored_comment(page, text)
    assert wide_lines > 1 if wrapping else wide_lines == 1
    page.locator(".lf-margin-thread").get_by_role(
        "textbox", name="Reply", exact=True
    ).click()

    # At this width clearing the controls would narrow the message. Both the
    # editor and its sent card use that space, retaining the editor's frame.
    wide = page.evaluate(THREAD_CARD_GEOMETRY)
    assert wide["minimum"] <= wide["cardWidth"] <= wide["preferred"], wide
    assert wide["replyWidth"] >= 160, wide
    assert wide["cardLeft"] == pytest.approx(editor_start, abs=0.5), wide
    assert wide["cardLeft"] == pytest.approx(wide["wordsRight"] + 8, abs=0.5), wide
    assert wide["cardLeft"] < wide["controlsRight"], wide


def test_margin_card_holds_its_top_as_a_turn_arrives_and_as_a_reply_wraps(
    browser, serve
):
    """Reading, a turn arriving extends the card downward. Drafting, so does each wrap
    of the reply: the thread being answered and the reply's first line stay where the
    user reads them, and Send moves down a line per wrap until the window's foot.
    After that the card grows up from the window's foot, its transcript unscrolled,
    until it fills the window, and then the editor scrolls internally."""
    page = open_page(browser, serve(OBLIGATION_PAGE, events=[COMMENT_ON_OBLIGATION]))
    resized(page, 1920, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds="comment"]')
    marker.evaluate("node => scrollBy(0, node.getBoundingClientRect().top - 160)")
    marker.click()
    preview = page.locator(".lf-margin-preview")
    initial = preview.evaluate(
        "node => ({top: node.getBoundingClientRect().top, height: node.getBoundingClientRect().height})"
    )
    root = events_model.read_events(serve.page_dir)[0]
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": root["id"],
            "responds": root["id"],
            "text": "The two jobs can share a single visit.",
        },
    )
    told(page)
    expect(preview).to_contain_text("The two jobs can share a single visit.")
    reading = preview.evaluate(
        "node => ({top: node.getBoundingClientRect().top, height: node.getBoundingClientRect().height})"
    )
    assert reading["top"] == pytest.approx(initial["top"], abs=0.5), (initial, reading)
    assert reading["height"] > initial["height"] + 10, (initial, reading)
    editor = preview.locator("leaf-text")
    preview.get_by_role("textbox", name="Reply", exact=True).click()
    expect(editor).to_be_focused()
    rendered(page)
    before = page.evaluate(CARD_AND_REPLY)
    assert before["placement"] == "right", before
    assert before["cardTop"] == pytest.approx(initial["top"], abs=0.5), before

    # Word by word until the reply has wrapped twice, reading every keystroke's result.
    readings = [before]
    words = iter(("the words keep coming as the user writes " * 12).split())
    while len({round(r["editorBottom"] - r["editorTop"]) for r in readings}) < 3:
        page.keyboard.type(next(words) + " ")
        rendered(page)
        readings.append(page.evaluate(CARD_AND_REPLY))
    for now in readings:
        for edge in ("cardTop", "turn", "editorTop"):
            assert now[edge] == pytest.approx(before[edge], abs=0.5), (
                edge,
                before,
                now,
            )
        assert now["scrolled"] == 0, now
    wrapped = readings[-1]
    for edge in ("editorBottom", "cardBottom", "send"):
        assert wrapped[edge] > before[edge] + 30, (edge, before, wrapped)

    # A draft with no room left under the card grows it up from the window's foot,
    # keeping the turn it answers in view, until the card fills the window; then the
    # editor scrolls.
    write(editor, "\n".join(f"Line {n}" for n in range(60)))
    rendered(page)
    tall = page.evaluate(CARD_AND_REPLY)
    assert tall["cardBottom"] == pytest.approx(tall["foot"], abs=1), tall
    assert tall["cardTop"] == pytest.approx(tall["head"], abs=1), tall
    assert tall["turn"] - tall["cardTop"] == pytest.approx(
        before["turn"] - before["cardTop"], abs=0.5
    ), (before, tall)
    assert editor.evaluate("box => box.scrollHeight > box.clientHeight")
    caret = _focused_editor_caret(page)
    assert caret["selection"] == caret["length"], caret
    assert caret["caretTop"] >= caret["boxTop"], caret

    # A short draft brings the card back to its top.
    write(editor, "Sent")
    rendered(page)
    short = page.evaluate(CARD_AND_REPLY)
    assert short["cardTop"] == pytest.approx(before["cardTop"], abs=0.5), short
    send = preview.get_by_role("button", name="Send", exact=True)
    # rendered() settles Leaf's preparation, while the shrinking draft can still
    # animate. click() waits for a stable Send; measure the same landing it presses.
    page.wait_for_function(
        """() => !document.querySelector('.lf-margin-preview')
            .getAnimations({subtree: true}).some(animation =>
                animation.playState === 'running' &&
                animation.effect.getComputedTiming().iterations !== Infinity)"""
    )
    pressed = send.evaluate("button => button.getBoundingClientRect().top")
    with sending(page, "the reply"):
        send.click()
    expect(preview).to_contain_text("Sent")
    # The send leaves the user on the card, holding it under the pressed Send.
    # An answer arriving then extends it downward,
    # holding its top, as a turn arriving while the user reads does.
    rendered(page)
    expect(preview.locator(".lf-page-thread")).to_be_focused()
    expect(preview).to_be_visible()
    assert preview.locator(".lf-compose-field > button:visible").evaluate(
        "button => button.getBoundingClientRect().top"
    ) == pytest.approx(pressed, abs=0.5)
    sent = page.evaluate(CARD_AND_REPLY)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": root["id"],
            "responds": root["id"],
            "text": "Noted.",
        },
    )
    told(page)
    expect(preview).to_contain_text("Noted.")
    rendered(page)
    answered = page.evaluate(CARD_AND_REPLY)
    assert answered["cardTop"] == pytest.approx(sent["cardTop"], abs=0.5), (
        sent,
        answered,
    )
    # Keep the complete send-and-answer journey exercised before the known Linux
    # native-caret boundary failure collected while the tall draft was focused.
    assert caret["caretBottom"] <= caret["boxBottom"], caret


def test_a_second_margin_reply_grows_below_the_first_line(browser, serve):
    """A new draft grows downward, then shares the bounded card with its transcript."""
    page, preview, editor = drafting_in_a_short_card(browser, serve, 1000, 600)
    preview.locator(".lf-thread-reply .lf-compose-submit").click()
    rendered(page)
    editor.click()
    rendered(page)
    before = preview.evaluate(DRAFTING_CARD)
    editor.type("A new draft.")
    editor.press("Shift+Enter")
    rendered(page)
    after = preview.evaluate(DRAFTING_CARD)
    assert after["side"] == before["side"]
    assert after["editorFoot"] > before["editorFoot"], (before, after)
    assert after["editorTop"] == pytest.approx(before["editorTop"], abs=0.5), (
        before,
        after,
    )
    page.keyboard.insert_text("a long new draft " * 20)
    rendered(page)
    bounded = page.evaluate(CARD_AND_REPLY)
    assert bounded["placement"] == before["side"]
    assert bounded["cardBottom"] == pytest.approx(bounded["foot"], abs=0.5), bounded
    assert bounded["turn"] < bounded["editorTop"] < after["editorTop"], bounded
    assert bounded["editorBottom"] <= bounded["cardBottom"], bounded
    assert bounded["editorTop"] <= bounded["send"] <= bounded["cardBottom"], bounded
    assert editor.evaluate("box => box.scrollHeight > box.clientHeight")
    expect(editor).to_be_focused()
    editor.press("ControlOrMeta+End")
    rendered(page)
    caret = _focused_editor_caret(page)
    assert caret["caretTop"] >= caret["boxTop"], caret
    assert caret["caretBottom"] <= caret["boxBottom"], caret


def test_continued_margin_draft_grows_below_its_first_line_after_agent_reply(
    browser, serve
):
    """News holds the reply row. Typing grows below its first line until the card
    reaches the window's foot, then the editor scrolls within that room."""
    page, preview, editor = drafting_in_a_short_card(browser, serve, 1000, 600)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "parent": LONG_THREAD_ROOT["id"],
            "responds": LONG_THREAD_ROOT["id"],
            "text": "An agent answer arriving while the user types. " * 6,
        },
    )
    told(page)
    rendered(page)
    before = preview.evaluate(DRAFTING_CARD)
    editor.press("Shift+Enter")
    rendered(page)
    after = preview.evaluate(DRAFTING_CARD)
    assert after["side"] == before["side"]
    assert after["editorFoot"] > before["editorFoot"], (before, after)
    assert after["editorTop"] == pytest.approx(before["editorTop"], abs=0.5), (
        before,
        after,
    )
    page.keyboard.insert_text(" a long continuing draft " * 20)
    rendered(page)
    bounded = page.evaluate(CARD_AND_REPLY)
    assert bounded["placement"] == before["side"]
    assert bounded["cardBottom"] == pytest.approx(bounded["foot"], abs=0.5), bounded
    assert bounded["turn"] < bounded["editorTop"], bounded
    assert bounded["editorTop"] == pytest.approx(after["editorTop"], abs=0.5), bounded
    assert bounded["editorBottom"] <= bounded["cardBottom"], bounded
    assert bounded["editorTop"] <= bounded["send"] <= bounded["cardBottom"], bounded
    assert editor.evaluate("box => box.scrollHeight > box.clientHeight")
    expect(editor).to_be_focused()


def test_the_thread_card_survives_the_on_view_and_authored_sidebars(browser, serve):
    """The On view or an authored sidebar does not turn the contextual card into a
    thread view in the panel."""
    page = open_page(
        browser,
        serve(OBLIGATION_PAGE, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION]),
    )
    resized(page, 2100, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.click()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)

    toggle_queue(page)
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    # The press on the marker puts On me away and opens the card, not a thread view.
    marker.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
    marker.click()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    marker.click()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(page.locator(".lf-margin-preview")).to_be_visible()

    page.close()

    sidebar_page = OBLIGATION_PAGE.replace(
        '<main class="layout-column">',
        '<main class="layout-sidebar"><aside><div class="layout-track">Page reference</div></aside>'
        '<div class="layout-column">',
        1,
    ).replace("</main>", "</div></main>", 1)
    page = open_page(
        browser,
        serve(sidebar_page, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION]),
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(PANEL_THREAD)).to_have_count(0)
    marker.click()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    resized_shell(page, 1472, 900)
    marker.click()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    # Reading the card's box needs the placement, which the reopened card takes a frame
    # to measure. Reopening clears the placement attribute but keeps the inline left and
    # top of the previous open, so visibility alone would read the card at the position
    # it held before the shell widened.
    expect(page.locator(".lf-margin-preview")).to_have_attribute(
        "data-lf-thread-placement", re.compile(r".+")
    )
    composition = page.evaluate(
        """() => {
          const main = document.querySelector('main').getBoundingClientRect();
          const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
          const controls = document.querySelector('[aria-expanded="true"]')
            .closest('[data-lf-margin-for]').getBoundingClientRect();
          return {mainWidth: main.width - 48, mainLeft: main.left,
                  mainRight: main.right, controlsRight: controls.right,
                  controlsTop: controls.top,
                  controlsBottom: controls.bottom, cardLeft: card.left,
                  cardRight: card.right, cardTop: card.top,
                  cardBottom: card.bottom, cardWidth: card.width,
                  shellWidth: document.body.getBoundingClientRect().width};
        }"""
    )
    assert composition["mainWidth"] >= 639.5, composition
    assert composition["cardLeft"] >= page.evaluate(WORDS_RIGHT) + 7.5, composition
    assert composition["cardRight"] <= composition["shellWidth"] + 0.5, composition
    assert composition["cardWidth"] >= 319, composition


def test_a_pin_unfolds_from_the_seat_it_was_pressed_in(browser, serve):
    """Unfolding a pin's options widens it, and a pin seated afresh at that width could
    move the control under the press: at 390px a reaction pin reseated 24px to the
    right as it unfolded. The pin the user holds keeps its seat and grows leftward."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    keep = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "token": "keep",
        "anchor": {"section": "editing-guide"},
    }
    page = open_page(
        browser, serve(MARGIN_ACTIONS_PAGE, events=[keep]), context=context
    )
    margins_laid_out(page)
    reaction = page.get_by_role("button", name="keep reaction actions", exact=True)
    cluster = page.locator(".lf-margin-cluster").filter(has=reaction)
    expect(cluster).to_have_attribute("data-lf-place", "pin")
    reaction.scroll_into_view_if_needed()
    margins_laid_out(page)
    before = cluster.bounding_box()
    reaction.tap()
    expect(reaction).to_have_attribute("aria-expanded", "true")
    margins_laid_out(page)
    after = cluster.bounding_box()
    assert after["width"] > before["width"], (before, after)
    assert after["x"] + after["width"] == pytest.approx(
        before["x"] + before["width"], abs=1
    ), (before, after)
    assert after["y"] == pytest.approx(before["y"], abs=1), (before, after)


# A paste grows the draft past its room at once, typing line by line; each room the
# pane can give the card is read once.
