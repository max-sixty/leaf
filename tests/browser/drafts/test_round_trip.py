"""The loop between user and agent across versions: comments and edits reaching the
agent, decisions surviving the next version, and the action history."""

import itertools
import re

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record, append_command
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_cases_navigation import (
    DRAFT_EDITED,
    DRAFT_TEXT,
    JOURNEY_V1,
    JOURNEY_V2,
    SENTENCE,
    painted,
)
from render_harness import (
    draft_control,
    expect_comment_notes,
    open_page,
    panel_menu,
    round_trip,
    selection_field,
    stamp_page,
    told,
    write,
)

from browser.threads import open_panel_thread
from leaf import cli as cli_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import service as service_model

pytestmark = pytest.mark.shifts_unsurveyed


def test_page_round_trip(browser, serve):
    """The loop the product is, driven through the real UI: select a passage and
    comment on it, drag a card to another column, rewrite a draft in place, then
    follow the next version and find the comment still anchored to its
    (relocated) passage and the draft still wearing the user's words. The
    final assertion is the event log — the trail Claude reads — down to the
    anchor's quote, the move's placement, and the edit's text."""
    page = open_page(browser, live_url(serve(JOURNEY_V1)))
    # The browser selects the exact passage; Comment explicitly enters its field.
    page.locator("#intro").evaluate("""p => {
        const range = document.createRange();
        range.selectNodeContents(p);
        getSelection().removeAllRanges();
        getSelection().addRange(range);
    }""")
    expect(selection_field(page)).to_be_visible()
    page.keyboard.press("c")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    page.wait_for_selector(".lf-composer", state="visible")
    write(page.locator(".lf-composer leaf-text"), "Is 0041 idempotent?")
    page.keyboard.press("ControlOrMeta+Enter")
    page.wait_for_selector(".lf-margin-thread")
    # The anchor pass painted the passage — a range in the highlight registry, not an
    # element, so there is no selector for it.
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Put the new comment's card away before reaching for the board. A sent comment
    # leaves its thread shown in the page margin, and the board is a wide widget
    # whose columns run out into that same band, so the card lands over the column this
    # drag is aimed at and takes the pointer. A user sees the card and dismisses it;
    # a test that skipped the dismissal would be dragging under a sheet, which is a
    # scene about the margin rather than the seam below.
    expect(page.locator(".lf-margin-preview .lf-page-thread")).to_be_focused()
    page.keyboard.press("Escape")  # from the sent card to its passage
    page.keyboard.press("Escape")  # off the passage, dismissing its card
    expect(page.locator(".lf-margin-thread")).to_be_hidden()
    # Drag the card between columns through the pointer path — the seam where
    # the vendored SortableJS meets the runtime, which is where drags break.
    grip = page.locator("#card-x .lf-grip").bounding_box()
    dest = page.locator("#col-done").bounding_box()
    page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
    page.mouse.down()
    page.mouse.move(
        dest["x"] + dest["width"] / 2, dest["y"] + dest["height"] / 2, steps=15
    )
    page.mouse.up()
    page.wait_for_selector("#col-done #card-x")  # the drop reparented the card

    # Rewrite the draft through its own door: a press opens the text in place, Save
    # sends the whole new body. The text must have arrived without the source's
    # indentation.
    draft = page.locator("#draft-ops")
    assert draft.locator(".lf-draft-body").inner_text() == DRAFT_TEXT
    draft.locator(".lf-draft-body").dblclick()
    write(draft.locator("leaf-text"), DRAFT_EDITED)
    draft_control(page, "save", "draft-ops").click()
    expect(draft.locator(".lf-draft-body")).to_have_text(DRAFT_EDITED)

    # Every gesture above must be in the log before v2's note lands, or the trail below
    # would interleave. The page posted them, so the page is what says they are all in:
    # polling the file for one of them would be a second reading of the same trip, and a
    # narrower one — it can only ever ask after the send it happens to name.
    d = serve.page_dir
    round_trip(page)

    # Claude ships v2 with the passage moved; the page follows on its next poll.
    stamp_page(d, JOURNEY_V2, "moved")
    told(page)
    expect(
        panel_menu(page).locator('.lf-fp-item[data-row="versions"]')
    ).to_contain_text("v2")
    page.locator(".lf-fp-leaf").click()
    assert "/versions/" not in page.url
    # The anchor pass runs at render: a mark now means the quote was re-found in
    # its new position; no mark within the wait means the anchor lost it.
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # The passage moved; the comment's quote still names words the page holds.
    comment = next(
        e["id"] for e in events_model.read_events(d) if e["kind"] == "comment"
    )
    quote = open_panel_thread(page, comment).locator(".lf-fp-quote")
    expect(quote).not_to_have_class(re.compile(r"\bdetached\b"))
    # v2's markup carries the original draft text — Claude hasn't honored the
    # edit — so the user's words must arrive by replay, not visibly revert.
    expect(draft.locator(".lf-draft-body")).to_have_text(DRAFT_EDITED)

    # The trail those gestures left, exactly — kinds, authorship (the server
    # stamps browser events `user`), the anchor, and the move's placement.
    events = events_model.read_events(d)
    assert [(e["kind"], e["author"], e["revision"]) for e in events] == [
        ("note", "agent", 1),
        ("comment", "user", 1),
        ("action", "user", 1),
        ("action", "user", 1),
        ("note", "agent", 2),
    ]
    # The board after the paragraph is module-rendered and therefore an opaque
    # passage cell. Context stops at that shared browser/file fence.
    assert events[1]["anchor"] == {
        "section": "intro",
        "quote": SENTENCE,
        "prefix": "Journey",
    }
    assert events[1]["text"] == "Is 0041 idempotent?"
    assert {k: events[2][k] for k in ("widget", "action", "detail")} == {
        "widget": "board",
        "action": "move",
        "detail": {"unit": "card-x", "value": "col-done", "rank": "i"},
    }
    assert {k: events[3][k] for k in ("widget", "action", "detail")} == {
        "widget": "draft-ops",
        "action": "edit",
        "detail": {"value": DRAFT_EDITED},
    }


@pytest.mark.parametrize("section", ["draft-ops", None])
def test_a_comment_inside_a_widget_stays_out_of_what_the_widget_reads(
    browser, serve, section
):
    """The note that tells a screen reader a block carries a comment is chrome, and chrome
    inside a widget's own content would be chrome in the user's text: lf-draft seeds the
    editor they type into from its body div, so words left in there would arrive in the
    leaf-text and post with the edit. The note stands in the chrome, and the block the
    passage sits in, or the element the anchor names, names it as its details. A
    reaction on the same words keeps the widget as its seat too: the passage's generated
    body is not the owner of the reaction's margin control."""
    url = serve(JOURNEY_V1, anchored=[(section, "Run the migration before deploying.")])
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "token": "keep",
            "anchor": {
                **({"section": section} if section else {}),
                "quote": "Run the migration before deploying.",
            },
        },
    )
    page = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    page.wait_for_function("() => (CSS.highlights.get('lf-react')?.size ?? 0) > 0")
    expect(
        page.locator(
            '[data-lf-margin-for="draft-ops"] '
            '[data-lf-margin-entry-owner="reactions"]'
            '[data-lf-margin-entry-key^="reaction:"]:visible'
        )
    ).to_have_count(1)
    expect_comment_notes(page, "#draft-ops", 1)
    # The thread's margin row, which stands by the passage it quotes, has the same seat
    # as its note: the widget, not the paragraph its Markdown body renders.
    expect(page.locator("[data-lf-margin-for]")).to_have_count(2)
    expect(
        page.locator("[data-lf-margin-for]:not([data-lf-margin-for=draft-ops])")
    ).to_have_count(0)
    page.locator("#draft-ops .lf-draft-body").dblclick()
    assert (
        page.locator("#draft-ops leaf-text").evaluate("el => el.value") == DRAFT_TEXT
    ), "the user's editor opened on text the runtime had written into"


def test_text_alignment_keeps_every_character_and_action_history_is_read_only(
    browser, serve
):
    """The text aligner may choose where an ambiguous repeated word aligns, but never
    loses or invents a character: same+delete is the old text, same+insert the new one.
    Unicode, whitespace and repetition are where a character or regex diff quietly
    breaks. Every granularity, because the unit is the caller's and the contract is
    not: an inline version comparison starts with sentences and refines a local edit by
    word. Its words come from Intl.Segmenter, so it is read in the browser.

    A draft's saved edits reach a widget as its action history, in log order, and a
    widget cannot rewrite that history by mutating what it read."""
    url = serve(JOURNEY_V1)
    page = open_page(browser, url)
    cases = [
        ("", ""),
        ("one line", "one longer line"),
        ("first\nsecond  line", "first\nsecond line\nthird"),
        ("l’écran est prêt 😀", "l’écran était prêt 🟢"),
        ("迁移完成。再次迁移。", "迁移完成。回滚完成。"),
        ("Retry once. Retry once. Then stop.", "Retry once. Retry twice. Then stop."),
        (
            "shared " + " ".join(f"old-{i}" for i in range(2500)) + " ending",
            "shared " + " ".join(f"new-{i}" for i in range(2500)) + " ending",
        ),
    ]
    aligned, by_sentence, inline = page.evaluate(
        """async (pairs) => {
          const {alignInlineText, sentenceUnits} = await window.__lfCheckApi();
          const {alignText} = await window.__lfWidgetApi();
          return [
            pairs.map(([before, after]) => alignText(before, after)),
            pairs.map(([before, after]) => alignText(before, after, sentenceUnits)),
            pairs.map(([before, after]) => alignInlineText(before, after)),
          ];
        }""",
        cases,
    )
    for unit, walked in (
        ("word", aligned),
        ("sentence", by_sentence),
        ("inline", inline),
    ):
        for (before, after), runs in zip(cases, walked, strict=True):
            joined = "".join(run["text"] for run in runs if run["kind"] != "insert")
            assert joined == before, (unit, joined, before)
            joined = "".join(run["text"] for run in runs if run["kind"] != "delete")
            assert joined == after, (unit, joined, after)
            assert all(a["kind"] != b["kind"] for a, b in itertools.pairwise(runs)), (
                unit
            )

    repeated = aligned[-2]
    assert "".join(r["text"] for r in repeated if r["kind"] == "delete") == "once"
    assert "".join(r["text"] for r in repeated if r["kind"] == "insert") == "twice"
    assert "Then stop." in "".join(r["text"] for r in repeated if r["kind"] == "same")
    assert [run["kind"] for run in aligned[-1]] == ["delete", "insert"]

    local = page.evaluate(
        """async () => {
          const {alignInlineText} = await window.__lfCheckApi();
          return alignInlineText(
            'Each section names a feature and provides a live example.',
            'Each section names a feature and provides a live example, including focused replays of its motion.'
          );
        }"""
    )
    assert "".join(run["text"] for run in local if run["kind"] == "delete") == ""
    assert "".join(run["text"] for run in local if run["kind"] == "insert") == (
        ", including focused replays of its motion"
    )

    draft = page.locator("#draft-ops")
    edits = [
        "Run the migration before deploying. It takes one minute.",
        "Run the migration after the backup. It takes two minutes.",
    ]
    for text in edits:
        draft.locator(".lf-draft-body").dblclick()
        write(draft.locator("leaf-text"), text)
        draft_control(page, "save", "draft-ops").click()
        round_trip(page)
        expect(draft.locator(".lf-draft-body")).to_have_text(text)

    events = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action"
    ]
    assert [event["detail"]["value"] for event in events] == edits
    assert [event["action"] for event in events] == ["edit", "edit"]

    sequence = page.evaluate(
        """async () => {
          const {widgetController} = await window.__lfWidgetApi();
          const widget = document.getElementById('draft-ops');
          const controller = widgetController(widget);
          const first = controller.read().actions.edit.history;
          first[0].detail.value = 'A widget must not mutate the runtime log.';
          return controller.read().actions.edit.history
            .map(event => [event.seq, event.detail.value]);
        }"""
    )
    assert [text for _, text in sequence] == edits
    assert [seq for seq, _ in sequence] == sorted(seq for seq, _ in sequence)


def test_action_history_is_bounded_by_the_pinned_version(browser, serve):
    """A historical page cannot narrate an edit that had not happened yet. The
    helper owns the same version boundary replay does, so every future widget that
    consumes a sequence gets this right without copying the filter."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    for version, text in ((1, "First recorded body."), (2, "Second recorded body.")):
        if version == 2:
            stamp_page(d, JOURNEY_V2, "v2")
        append_command(
            d,
            {
                "kind": "action",
                "author": "user",
                "revision": version,
                "widget": "draft-ops",
                "action": "edit",
                "detail": {"value": text},
            },
        )

    old = open_page(browser, url, pin=True)
    expect(old.locator("#draft-ops .lf-draft-body")).to_have_text(
        "First recorded body."
    )
    old_sequence = old.evaluate(
        """async () => (await window.__lfWidgetApi())
          .widgetController(document.getElementById('draft-ops')).read().actions.edit.history
          .map(event => event.revision)"""
    )
    assert old_sequence == [1]

    latest = open_page(browser, url.replace("v1.html", "v2.html"), pin=True)
    expect(latest.locator("#draft-ops .lf-draft-body")).to_have_text(
        "Second recorded body."
    )
    latest_sequence = latest.evaluate(
        """async () => (await window.__lfWidgetApi())
          .widgetController(document.getElementById('draft-ops')).read().actions.edit.history
          .map(event => event.revision)"""
    )
    assert latest_sequence == [1, 2]


def test_an_acknowledged_decision_still_survives_the_next_version(browser, serve):
    """The round trip above, differing in one fact: the agent has acknowledged the
    actions before v2 publishes. That is the ordinary case — the agent writes a
    version *because* it was handed the user's edits — and it used to be the
    one that lost them: replay stopped at the handoff cursor, on the premise
    that a version written after seeing an action encodes it. Nothing checks that
    premise, so a version that quietly omits the state re-emitted the widget as
    untouched and the user's work vanished with no error anywhere.

    Acknowledgement is not assent. Only the next version's markup can say what the
    agent did with an edit, and until it says otherwise the log is what the user
    did."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "board",
            "action": "move",
            "detail": {"unit": "card-x", "value": "col-done", "rank": "0i"},
        },
    )
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"value": DRAFT_EDITED},
        },
    )
    # The highest user event reached context, so everything so far is ours to answer.
    with service_model.PageTransaction(d) as transaction:
        batch = {"events": transaction.events}
        with delivery_model.receive_batch(
            transaction, batch, session_id=None
        ) as events:
            delivery_model.record_pickup(transaction, events)
    # And the agent answers with a version that carries neither — the page generator
    # emitting its own idea of the board and the draft, as one did for five
    # versions running.
    stamp_page(d, JOURNEY_V2, "v2")

    page = open_page(browser, url.replace("v1.html", "v2.html"))
    expect(page.locator("#draft-ops .lf-draft-body")).to_have_attribute(
        "data-lf-source-words", DRAFT_EDITED
    )
    expect(page.locator("#col-done #card-x")).to_have_count(1)


def test_a_comment_written_on_an_edited_draft_lands_on_their_words(browser, serve):
    """`leaf thread create` reads the mapped revision plus the log; the user's tab reads
    the DOM replay builds from the same two. An edited draft is where those readings
    used to drift — the file holds words the page stopped showing — so write the anchor
    blind, on the user's own words, and prove the page paints it. The words the edit
    replaced are refused at the CLI, because posted they would detach in front of the
    user."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "draft-ops",
            "action": "edit",
            "detail": {"value": DRAFT_EDITED},
        },
    )
    refused = CliRunner().invoke(
        cli_model.cli,
        ["thread", "create", str(d), "--quote", "It is online.", "--text", "x"],
    )
    assert refused.exit_code != 0 and "doesn't say" in refused.output
    written = CliRunner().invoke(
        cli_model.cli,
        [
            "thread",
            "create",
            str(d),
            "--quote",
            "It takes about a minute.",
            "--text",
            "Measured where?",
        ],
        catch_exceptions=False,
    )
    assert written.exit_code == 0, written.output

    page = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    comment = next(
        e["id"] for e in events_model.read_events(d) if e["kind"] == "comment"
    )
    quote = open_panel_thread(page, comment).locator(".lf-fp-quote")
    expect(quote).not_to_have_class(re.compile(r"\bdetached\b"))
    assert painted(page, "lf-mark") == "It takes about a minute."
