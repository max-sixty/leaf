"""End-to-end journey and durable draft tests."""

import base64
import itertools
import json
import re

import pytest
from click.testing import CliRunner
from interact_support import append_command
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import session as session_model
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from render_support import (
    ASK_PAGE,
    BOTH_STAMPS,
    DRAFT_EDITED,
    DRAFT_TEXT,
    EXAMPLE_MEDIA,
    JOURNEY_V1,
    JOURNEY_V2,
    KEYS_PAGE,
    LONG_PAGE,
    NOTED_PAGE,
    SCROLL_SETTLED,
    SEATED_QUESTION_PAGE,
    SENTENCE,
    SMOOTH_LONG_PAGE,
    STORED_DRAFT_SETTLED,
    STORED_DRAFT_TEXT,
    CutOff,
    _publish,
    _traffic,
    _until,
    compare_with,
    compose,
    composer_quote,
    held_stale,
    hold_selection,
    holding,
    in_threads_scrollport,
    live_url,
    open_page,
    painted,
    panel_settled,
    pending_text,
    refuse,
    resized,
    round_trip,
    sending,
    sent_events,
    shortcut_bar_text,
    stamp_version_file,
    ticked,
    told,
    wait_for_revision,
)

pytestmark = pytest.mark.nightly


def select_words(page, passage):
    """Triple-click a passage's words, which is not the same point as its box.

    Playwright aims at the element's centre, and a short paragraph in a wide column is
    mostly empty there. The response bar the reader already opened on a neighbouring
    passage stands in that empty half — it is placed to keep its own target clear, not
    the page — so a gesture aimed at the centre lands on the field instead of on the
    words and never reaches the passage. The words are where a reader aims, so the
    click goes to the start of the first line the passage draws."""
    locator = page.locator(passage)
    locator.scroll_into_view_if_needed()
    x, y = locator.evaluate(
        """element => {
          const range = element.ownerDocument.createRange();
          range.selectNodeContents(element);
          const [line] = range.getClientRects();
          const box = element.getBoundingClientRect();
          if (!line) return [box.width / 2, box.height / 2];
          return [
            line.left + Math.min(24, line.width / 2) - box.left,
            line.top + line.height / 2 - box.top,
          ];
        }"""
    )
    locator.click(click_count=3, position={"x": x, "y": y})


@pytest.mark.parametrize("box", ["general", "reply", "composer"])
def test_a_single_space_is_message_content_in_every_composer(browser, serve, box):
    """The shared field and both drawing-aware variants admit the smallest message."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=box == "reply"))
    if box == "composer":
        select_words(page, "#p0")
        expect(page.locator(".lf-fab-input")).to_be_visible()
        page.keyboard.press("c")
        surface = page.locator(".lf-composer")
    else:
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        surface = (
            page.locator(".lf-general")
            if box == "general"
            else page.locator(".lf-threads > .lf-thread").first
        )

    field = surface.locator("textarea")
    send = surface.locator(".lf-compose-submit")
    field.fill(" ")
    expect(send).to_have_attribute("aria-disabled", "false")
    with sending(page, f"the {box} message"):
        send.click()

    message = [
        event
        for event in sent_events(serve.page_dir)
        if event["kind"] in {"comment", "reply"}
    ][-1]
    assert message["text"] == " "
    assert errors == []
    page.close()


def draft_controls(page, draft_id="draft-ops"):
    return page.locator(f".lf-draft-controls[data-lf-for='{draft_id}']")


def cancel_draft(page, draft_id="draft-ops"):
    """Cancel stands beside Save throughout an engaged draft edit."""
    controls = draft_controls(page, draft_id)
    item = controls.locator("xpath=..")
    item.locator(":scope > .lf-margin-options").get_by_role(
        "button", name="Cancel", exact=True
    ).click()


def test_page_round_trip(browser, serve):
    """The loop the product is, driven through the real UI: select a passage and
    comment on it, drag a card to another column, rewrite a draft in place, then
    follow the next version and find the comment still anchored to its
    (relocated) passage and the draft still wearing the user's words. The
    final assertion is the event log — the trail Claude reads — down to the
    anchor's quote, the move's placement, and the edit's text."""
    page, errors = open_page(browser, live_url(serve(JOURNEY_V1)))
    page.evaluate("window.__leafJourneyDocument = 'held'")

    # Select the passage from the keyboard's path: a real Range, then the keyup
    # the runtime watches for keyboard selections. Comment explicitly enters its field.
    page.evaluate("""() => {
        const r = document.createRange();
        r.selectNodeContents(document.getElementById('intro'));
        getSelection().removeAllRanges();
        getSelection().addRange(r);
        document.body.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
    }""")
    page.wait_for_selector(
        ".lf-fab-input", state="visible"
    )  # the selection raised the button
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    page.keyboard.press("c")
    expect(page.locator(".lf-fab-input")).to_be_focused()
    page.wait_for_selector(".lf-composer", state="visible")
    page.locator(".lf-composer textarea").fill("Is 0041 idempotent?")
    page.keyboard.press("ControlOrMeta+Enter")
    page.wait_for_selector(".lf-margin-thread")
    # The anchor pass painted the passage — a range in the highlight registry, not an
    # element, so there is no selector for it.
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Put the new comment's card away before reaching for the board. A sent comment
    # leaves its thread standing in the page margin, and the board is a wide widget
    # whose columns run out into that same band, so the card lands over the column this
    # drag is aimed at and takes the pointer. A reader sees the card and dismisses it;
    # a test that skipped the dismissal would be dragging under a sheet, which is a
    # scene about the margin rather than the seam below.
    page.keyboard.press("Escape")
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
    draft.locator("textarea").fill(DRAFT_EDITED)
    draft_controls(page).get_by_role("button", name="Save").click()
    page.wait_for_function(
        "t => document.querySelector('#draft-ops .lf-draft-body').textContent === t",
        arg=DRAFT_EDITED,
    )

    # Every gesture above must be in the log before v2's note lands, or the trail below
    # would interleave. The page posted them, so the page is what says they are all in:
    # polling the file for one of them would be a second reading of the same trip, and a
    # narrower one — it can only ever ask after the send it happens to name.
    d = serve.page_dir
    round_trip(page)

    # Claude ships v2 with the passage moved; the page follows on its next poll.
    (d / ".fixture-versions" / "v2.html").write_text(JOURNEY_V2)
    stamp_version_file(d, 2, "moved")
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")
    assert page.evaluate("window.__leafJourneyDocument") == "held", (
        "the live journey navigated instead of activating its authored version"
    )
    assert "/versions/" not in page.url
    # The anchor pass runs at render: a mark now means the quote was re-found in
    # its new position; no mark within the wait means the anchor lost it.
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert not page.evaluate(
        "document.querySelector('.lf-thread .lf-quote').classList.contains('detached')"
    ), "the passage moved and the comment lost it"
    # v2's markup carries the original draft text — Claude hasn't honored the
    # edit — so the user's words must arrive by replay, not visibly revert.
    page.wait_for_function(
        "t => document.querySelector('#draft-ops .lf-draft-body').textContent === t",
        arg=DRAFT_EDITED,
    )

    assert errors == []
    # The trail those gestures left, exactly — kinds, authorship (the server
    # stamps browser events `user`), the anchor, and the move's placement.
    events = [
        json.loads(line) for line in (d / "events.jsonl").read_text().splitlines()
    ]
    assert [(e["kind"], e["author"], e["revision"]) for e in events] == [
        ("note", "claude", 1),
        ("comment", "user", 1),
        ("action", "user", 1),
        ("action", "user", 1),
        ("note", "claude", 2),
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
        "detail": {"card": "card-x", "to": "col-done", "index": 0},
    }
    assert {k: events[3][k] for k in ("widget", "action", "detail")} == {
        "widget": "draft-ops",
        "action": "edit",
        "detail": {"text": DRAFT_EDITED},
    }
    page.close()


@pytest.mark.parametrize("section", ["draft-ops", None])
def test_a_comment_inside_a_widget_stays_out_of_what_the_widget_reads(
    browser, serve, section
):
    """The line that tells a screen reader a block carries a comment is chrome, and chrome
    inside a widget's own content is chrome in the user's text: lf-draft seeds the
    editor they type into from its body div, so a line left in there arrives in the
    textarea and posts with the edit. It goes on the block the passage sits in, or on the
    element the anchor names — never on the inline run or body div in between."""
    url = serve(JOURNEY_V1, anchored=[(section, "Run the migration before deploying.")])
    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert page.locator("#draft-ops > .lf-mark-note").count() == 1, (
        "the line landed inside the draft's body rather than beside it"
    )
    page.locator("#draft-ops .lf-draft-body").dblclick()
    assert page.locator("#draft-ops textarea").input_value() == DRAFT_TEXT, (
        "the user's editor opened on text the runtime had written into"
    )
    assert errors == []
    page.close()


@pytest.mark.parametrize("section", ["draft-ops", None])
def test_a_reaction_inside_a_widget_keeps_its_authored_seat(browser, serve, section):
    """A passage's generated body is not the owner of the reaction's margin control."""
    url = serve(JOURNEY_V1)
    events_model.append_event(
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
    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-react')?.size ?? 0) > 0")
    expect(page.locator('.lf-reacts[data-lf-for="draft-ops"]')).to_have_count(1)
    page.locator("#draft-ops .lf-draft-body").dblclick()
    assert page.locator("#draft-ops textarea").input_value() == DRAFT_TEXT
    assert errors == []
    page.close()


def test_double_clicking_a_draft_leaves_every_word_where_it_was(browser, serve):
    """Two halves of one gesture, both of them invisible to a static lint.

    The box: reading and editing are the same box, so the words a user
    double-clicked are still under the pointer when the editor opens. They were
    not — the runtime's general textarea rule wraps text in padding and a border
    and floors it at 64px, which moved the first character 9px right and 6px down
    and stretched a two-line draft — and text that jumps out from under a
    double-click is the user's aim thrown away.

    The gesture: a double press on a draft is two presses on two different boxes now.
    The first opens the editor with a collapsed caret where it landed, so there is no
    page selection to flash; the second lands in the textarea that first press put
    there, where selecting a word is the browser's own behaviour in any text field.
    What is assertable is the outcome on either side of that. Nothing on the page ends
    up selected, and the word the gesture named opens selected in the box — which is
    what a double-click means everywhere else, and is true here because the box is a
    real text field rather than because the widget reimplemented word boundaries.

    The block around them counts too: the whole draft has to keep its shape, or a
    gesture aimed at one word is answered by everything under it moving. Cancel and
    Save join a row the draft always has rather than arriving as one, which is worth
    a measurement because the row is invisible in the diff that matters — both views
    lay out fine on their own, and only the two together say whether the box moved.

    And the swap is the screen's, which is why the widget writes none of it: paper
    drops the box with the other offers, so a draft mid-edit printed as an empty
    frame for as long as the module hid the body itself."""
    page, errors = open_page(browser, serve(JOURNEY_V1))
    metrics = """(sel) => {
      const el = document.querySelector('#draft-ops ' + sel), s = getComputedStyle(el);
      const b = el.getBoundingClientRect();
      return [b.x + parseFloat(s.paddingLeft) + parseFloat(s.borderLeftWidth),
              b.y + parseFloat(s.paddingTop) + parseFloat(s.borderTopWidth), b.width, b.height];
    }"""
    read = page.evaluate(metrics, ".lf-draft-body")
    host = page.locator("#draft-ops").bounding_box()
    # A 4px band above the box, and the box's own top-left corner. The band is where
    # the answer to "did the frame move" lives and no measurement of geometry can
    # reach it: an outset ring is paint, so every rect stayed exactly as asserted
    # below while the frame the user sees grew 2px on every side, corners
    # rounding wider to match. Bytes, not pixels — the same encoder over the same
    # content gives the same file, so identical files are identical paint.
    band = {
        "x": host["x"] - 4,
        "y": host["y"] - 4,
        "width": host["width"] + 8,
        "height": 4,
    }
    inside = {"x": host["x"], "y": host["y"], "width": 40, "height": 40}
    outside_before = page.screenshot(clip=band)
    inside_before = page.screenshot(clip=inside)

    # Aimed at where the browser actually drew the word, not at an offset from the
    # box's edge. A pixel count is a fact about one font: 60px into this line was
    # "migration" while the theme set drafts in 16px system-ui, and lands in "the"
    # now that it sets them in 17px Charter — so the test read as "the editor opens
    # on the wrong word" when nothing about the gesture had changed.
    spot = page.evaluate(
        """(word) => {
            const body = document.querySelector('#draft-ops .lf-draft-body');
            const node = document.createTreeWalker(body, NodeFilter.SHOW_TEXT).nextNode();
            const at = node.data.indexOf(word);
            const r = document.createRange();
            r.setStart(node, at); r.setEnd(node, at + word.length);
            const b = r.getBoundingClientRect();
            return [b.x + b.width / 2, b.y + b.height / 2];
        }""",
        "migration",
    )
    page.mouse.dblclick(*spot)
    editor = page.locator("#draft-ops textarea")
    expect(editor).to_be_focused()
    pencil = draft_controls(page).locator(".lf-draft-pencil")
    assert page.screenshot(clip=band) == outside_before, (
        "opening the editor painted outside the box the draft already occupied"
    )
    assert page.screenshot(clip=inside) != inside_before, (
        "the open editor is indistinguishable from the read view at the box's edge"
    )
    assert page.evaluate(metrics, "textarea") == read, (
        "the editor's text sits somewhere the read view's text did not"
    )
    assert page.locator("#draft-ops").bounding_box() == host, (
        "the draft changed shape under the pointer when the editor opened"
    )
    assert (
        page.evaluate(
            "() => getSelection().rangeCount > 0 && "
            "getSelection().containsNode(document.querySelector('#draft-ops .lf-draft-body'), true)"
        )
        is False
    ), "the gesture left the page's own words selected under the open editor"
    selected = page.evaluate(
        "() => { const t = document.querySelector('#draft-ops textarea');"
        "        return t.value.slice(t.selectionStart, t.selectionEnd); }"
    )
    assert selected == "migration", (
        f"the box opened on {selected!r} rather than the word clicked"
    )

    # Closing states both properties in reverse, and the focus half is a question
    # only because the ✎ is CSS-hidden for as long as the editor is there: #close
    # reaches for it the instant the editor goes, so a style that hadn't caught up
    # would drop a keyboard user back at the top of the page.
    page.keyboard.press("Escape")
    expect(pencil).to_be_focused()
    expect(pencil).to_have_attribute("aria-expanded", "false")
    assert page.locator("#draft-ops").bounding_box() == host, (
        "the draft came back from an edit a different shape than it went in"
    )

    # Reopened through the other door, because print is where the box has to be
    # gone and its words still there — and print emulation blurs the textarea it
    # hides, so an editor opened before this point is no longer one Escape closes.
    draft_controls(page).locator(".lf-draft-pencil").click()
    expect(page.locator("#draft-ops textarea")).to_be_visible()
    page.emulate_media(media="print")
    assert page.locator("#draft-ops").inner_text() == DRAFT_TEXT, (
        "the printed page lost the draft's words to a box paper hasn't got"
    )
    page.emulate_media(media="screen")
    assert errors == []
    page.close()


def test_a_foreign_edit_waits_for_a_live_draft_and_replays_in_order(browser, serve):
    """Replay never replaces words while the user is typing them.

    Deferring one edit must also hold later edits for that draft: otherwise the
    later absolute value lands first and the deferred earlier value overwrites it
    when the box closes. An unrelated board move proves the poll saw the same
    batch while the editor was open, without making the test depend on time.
    """
    page, errors = open_page(browser, serve(JOURNEY_V1))
    draft = page.locator("#draft-ops")
    draft.locator(".lf-draft-body").dblclick()
    editor = draft.locator("textarea")
    editor.fill("Local unsent words.")

    d = serve.page_dir
    for text in ("Foreign first edit.", "Foreign committed words."):
        append_command(
            d,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "draft-ops",
                "action": "edit",
                "detail": {"text": text},
            },
        )
    append_command(
        d,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "board",
            "action": "move",
            "detail": {"card": "card-x", "to": "col-done", "index": 0},
        },
    )

    told(page)
    expect(page.locator("#col-done #card-x")).to_have_count(1)
    expect(editor).to_have_value("Local unsent words.")
    expect(draft.locator(".lf-draft-history")).to_have_count(0)

    page.route("**/api/state*", refuse)
    page.keyboard.press("Escape")
    ticked(page)
    expect(draft.locator(".lf-draft-body")).to_have_text("Foreign committed words.")
    expect(draft.locator(".lf-draft-history > summary")).to_have_text(
        "Changes · 2 edits"
    )
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "3")
    assert errors == []
    page.close()


def test_an_empty_draft_survives_reload_and_blocks_a_version_switch(browser, serve):
    """Empty text is a real replacement, not the absence of a saved draft. Deleting
    the whole body must hold a live editor on its version, survive reload, and arrive
    in the log as an ordinary absolute edit."""
    url = serve(JOURNEY_V1)
    page, errors = open_page(browser, live_url(url))
    draft = page.locator("#draft-ops")
    draft.locator(".lf-draft-body").dblclick()
    draft.locator("textarea").fill("")
    assert page.evaluate(STORED_DRAFT_TEXT, "edit:draft-ops") == ""

    d = serve.page_dir
    (d / ".fixture-versions" / "v2.html").write_text(JOURNEY_V2)
    stamp_version_file(d, 2, "v2")
    told(page)
    expect(page.locator(".lf-latest-chip")).to_be_visible()
    assert "/versions/" not in page.url

    page.reload(wait_until="load")
    page.wait_for_function(BOTH_STAMPS)
    expect(draft.locator("textarea")).to_be_visible()
    expect(draft.locator("textarea")).to_have_value("")

    page.evaluate(
        """() => {
          window.lfActualFetch = window.fetch.bind(window);
          window.lfFailDraft = true;
          window.fetch = (input, init) => {
            const event = String(input).endsWith('/api/event') && init?.body
              ? JSON.parse(init.body) : null;
            if (window.lfFailDraft &&
                event?.kind === 'action' && event.action === 'edit')
              return Promise.resolve(new Response('offline', {status: 503}));
            return window.lfActualFetch(input, init);
          };
        }"""
    )
    draft_controls(page).get_by_role("button", name="Save").click()
    # A 503 cannot say whether the server appended before its answer was lost. Keep
    # the one saved gesture visibly pending and its draft recoverable; reopening the
    # editor would invite a second gesture while this attempt is still retrying.
    expect(draft).to_have_attribute("aria-busy", "true")
    expect(draft.locator("textarea")).to_have_count(0)
    expect(draft.locator(".lf-draft-body")).to_have_text("")
    assert page.evaluate(STORED_DRAFT_TEXT, "edit:draft-ops") == ""

    page.evaluate("window.lfFailDraft = false")
    wait_for_revision(page, 2)
    expect(page.locator("#draft-ops .lf-draft-body")).to_have_text("")
    page.wait_for_function(STORED_DRAFT_SETTLED, arg="edit:draft-ops")
    events = [
        json.loads(line)
        for line in (d / "events.jsonl").read_text().splitlines()
        if '"kind": "action"' in line
    ]
    assert events[-1]["action"] == "edit"
    assert events[-1]["detail"] == {"text": ""}
    assert errors == []
    page.close()


def test_a_draft_send_owns_the_editor_until_its_response(browser, serve):
    """A second gesture cannot overtake an earlier request or let that request clear
    newer unsent text. Hold the first POST in the browser: while it owns the draft,
    every edit door stays closed and the exact body remains recoverable."""
    page, errors = open_page(browser, serve(JOURNEY_V1))
    page.evaluate(
        """() => {
          const actualFetch = window.fetch.bind(window);
          let held = true;
          window.fetch = (input, init) => {
            const event = String(input).endsWith('/api/event') && init?.body
              ? JSON.parse(init.body) : null;
            if (held && event?.kind === 'action' && event.action === 'edit') {
              return new Promise((resolve, reject) => {
                window.releaseDraftSend = () => {
                  held = false;
                  actualFetch(input, init).then(resolve, reject);
                };
              });
            }
            return actualFetch(input, init);
          };
        }"""
    )
    draft = page.locator("#draft-ops")
    sent = "The first save still owns this body."
    draft.locator(".lf-draft-body").dblclick()
    draft.locator("textarea").fill(sent)
    draft_controls(page).get_by_role("button", name="Save").click()
    expect(draft).to_have_attribute("aria-busy", "true")
    assert page.evaluate(STORED_DRAFT_TEXT, "edit:draft-ops") == sent

    expect(draft_controls(page).locator(".lf-draft-pencil")).to_be_disabled()
    draft_controls(page).locator(".lf-draft-pencil").evaluate(
        "button => button.click()"
    )
    expect(draft.locator("textarea")).to_have_count(0)
    expect(page.locator(".lf-notice")).to_contain_text("Wait for the current edit")

    page.evaluate("window.releaseDraftSend()")
    page.wait_for_function(
        """ctx => !document.getElementById('draft-ops').hasAttribute('aria-busy')
          && JSON.parse(localStorage.getItem('lf-draft:' + ctx))?.settled === true""",
        arg="edit:draft-ops",
    )
    events = [
        json.loads(line)
        for line in (serve.page_dir / "events.jsonl").read_text().splitlines()
        if '"kind": "action"' in line
    ]
    assert [event["detail"]["text"] for event in events] == [sent]

    draft_controls(page).locator(".lf-draft-pencil").click()
    expect(draft.locator("textarea")).to_be_focused()
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_a_draft_wait_only_paints_after_the_shared_busy_delay(browser, serve):
    """The layer leaves a short send unpainted, then makes a long wait visible."""
    page, errors = open_page(browser, serve(JOURNEY_V1))
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    draft = page.locator("#draft-ops")
    draft.locator(".lf-draft-body").dblclick()
    draft.locator("textarea").fill("A send held long enough to need progress paint.")

    # Sample on the CSS animation's own clock rather than racing wall time across a
    # Playwright round trip. The host is the surface without a margin entry that owns aria-busy.
    frames = page.evaluate(
        """async () => {
          const el = document.getElementById('draft-ops');
          const out = [];
          let stop = false;
          const tick = () => {
            const painted = Number(getComputedStyle(el).opacity);
            const busy = el.getAnimations().find(
              animation => animation.animationName === 'lf-runtime-4f3c2a8d-working'
            );
            out.push([
              busy ? Number(busy.currentTime) : null,
              busy ? busy.playState : null,
              painted,
            ]);
            if (!stop) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
          document.querySelector(
            '[data-lf-for="draft-ops"] [aria-label="Save"]'
          ).click();
          await new Promise(resolve => setTimeout(resolve, 700));
          stop = true;
          return out;
        }"""
    )
    holding(page, held, 1, "the draft edit")

    early = [
        opacity
        for elapsed, _state, opacity in frames
        if elapsed is None or elapsed < 150
    ]
    late = [opacity for _elapsed, state, opacity in frames if state == "finished"]
    assert early and set(early) == {1}, f"a short draft wait painted busy: {early}"
    assert late and set(late) == {0.5}, f"a long draft wait stayed unpainted: {late}"
    expect(draft).to_have_attribute("aria-busy", "true")

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(draft).not_to_have_attribute("aria-busy", "true")
    assert errors == []
    page.close()


def test_a_refused_draft_keeps_text_and_offers_retry_without_a_details_pane(
    browser, serve
):
    """Failure is an editable state, with Retry and Cancel at the same target."""
    page, errors = open_page(browser, serve(JOURNEY_V1))
    draft = page.locator("#draft-ops")
    draft.locator(".lf-draft-body").dblclick()
    editor = draft.locator("textarea")
    editor.fill("Keep these unsent words.")
    page.route(
        "**/api/event",
        lambda route: route.fulfill(
            status=400,
            json={"ok": False, "final": True, "error": "refused before append"},
        ),
    )
    draft_controls(page).get_by_role("button", name="Save", exact=True).click()
    item = page.locator('[data-lf-margin-for="draft-ops"]')
    expect(item.locator(".lf-margin-receipt")).to_have_text("Failed")
    expect(item).to_have_attribute("data-lf-state", "failed")
    expect(editor).to_have_value("Keep these unsent words.")
    expect(item.get_by_role("button", name="Retry", exact=True)).to_be_visible()
    expect(item.get_by_role("button", name="Cancel", exact=True)).to_be_visible()
    expect(item.locator(".lf-margin-more")).to_be_hidden()
    expect(page.locator(".lf-margin-preview")).to_be_hidden()

    editor.fill("Keep the revised unsent words.")
    expect(item.locator(".lf-margin-receipt")).to_have_count(0)
    expect(item).to_have_attribute("data-lf-state", "engaged")
    item.get_by_role("button", name="Save", exact=True).click()
    expect(item.locator(".lf-margin-receipt")).to_have_text("Failed")
    page.unroute("**/api/event")
    item.get_by_role("button", name="Retry", exact=True).click()
    round_trip(page)
    expect(editor).to_have_count(0)
    expect(draft.locator(".lf-draft-body")).to_have_text(
        "Keep the revised unsent words."
    )
    edits = [
        event for event in sent_events(serve.page_dir) if event.get("action") == "edit"
    ]
    assert [event["detail"] for event in edits] == [
        {"text": "Keep the revised unsent words."}
    ]
    assert errors and all("400" in error for error in errors)
    page.close()


def test_one_draft_edit_is_what_every_tab_of_the_page_shows(browser, serve, one_reader):
    """An edit is one set of words wherever the reader typed them, and the two halves
    of that fail in opposite directions. A keystroke has to reach the box the other tab
    has open, or two tabs hold two halves of one thought and whichever is closed takes
    its half with it. A settlement has to empty the other box, rather than leave it
    holding words the log already has — standing over a body replay is about to paint.

    A closed box stays closed for a keystroke made elsewhere: news arriving has no
    gesture behind it, and the words are there at the next opening either way."""
    url = serve(JOURNEY_V1)
    first, first_errors = open_page(browser, url, context=one_reader)
    second, second_errors = open_page(browser, url, context=one_reader)
    first_draft = first.locator("#draft-ops")
    second_draft = second.locator("#draft-ops")

    edited = "Run the migration after the backup."
    first_draft.locator(".lf-draft-body").dblclick()
    second_draft.locator(".lf-draft-body").dblclick()
    first_draft.locator("textarea").fill(edited)
    expect(second_draft.locator("textarea")).to_have_value(edited)

    draft_controls(first).get_by_role("button", name="Save").click()
    round_trip(first)
    expect(second_draft.locator("textarea")).to_have_count(0)
    # The body the other tab is left looking at is the log's, which is what closing the
    # box in front of it was for: renderState defers while an editor stands open.
    expect(second_draft.locator(".lf-draft-body")).to_have_text(edited)
    assert second.evaluate(STORED_DRAFT_SETTLED, "edit:draft-ops")

    # A second edit, with only the first tab's box open. The store's value arriving is
    # the fact to consume before reading an absence: the storage event carrying it is
    # the same task that would have opened a box here.
    discarded = "This tab discards these words."
    first_draft.locator(".lf-draft-body").dblclick()
    first_draft.locator("textarea").fill(discarded)
    second.wait_for_function(
        """text => JSON.parse(
          localStorage.getItem('lf-draft:edit:draft-ops')
        )?.text === text""",
        arg=discarded,
    )
    assert second_draft.locator("textarea").count() == 0, (
        "the second tab opened an editor for a keystroke nobody made there"
    )
    cancel_draft(first)
    second.wait_for_function(STORED_DRAFT_SETTLED, arg="edit:draft-ops")
    second_draft.locator(".lf-draft-body").dblclick()
    expect(second_draft.locator("textarea")).to_have_value(edited)

    events = [
        json.loads(line)
        for line in (serve.page_dir / "events.jsonl").read_text().splitlines()
        if '"kind": "action"' in line
    ]
    assert [event["detail"]["text"] for event in events] == [edited]
    assert first_errors == []
    assert second_errors == []


def test_one_shared_draft_edit_appends_one_action_across_tabs(
    browser, serve, one_reader
):
    """The widget's local busy flag is not the shared edit's ownership boundary."""
    url = serve(JOURNEY_V1)
    first, first_errors = open_page(browser, url, context=one_reader)
    second, second_errors = open_page(browser, url, context=one_reader)
    first_draft = first.locator("#draft-ops")
    second_draft = second.locator("#draft-ops")
    first_draft.locator(".lf-draft-body").dblclick()
    second_draft.locator(".lf-draft-body").dblclick()
    text = "One absolute edit from the shared draft generation."
    first_draft.locator("textarea").fill(text)
    expect(second_draft.locator("textarea")).to_have_value(text)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    draft_controls(first).get_by_role("button", name="Save").click()
    holding(first, held, 1, "the first draft edit")
    draft_controls(second).get_by_role("button", name="Save").click()
    round_trip(second)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    edits = [
        event
        for event in sent_events(serve.page_dir)
        if event["kind"] == "action" and event["action"] == "edit"
    ]
    assert [event["detail"]["text"] for event in edits] == [text]
    assert edits[0]["attempt"]
    assert _traffic(first).sends == _traffic(second).sends == 1
    expect(second_draft.locator("textarea")).to_have_count(0)
    assert second.evaluate(STORED_DRAFT_SETTLED, "edit:draft-ops")
    assert first_errors == []
    assert second_errors == []


def test_one_shared_added_option_has_one_action_payload_across_tabs(
    browser, serve, one_reader
):
    """A draft attempt owns its action detail as well as its visible words.

    The two views deliberately start from different projected selections. Both can
    submit the one shared add-option generation, so deriving its absolute choice from
    each tab's DOM would reuse one attempt for two conflicting payloads.
    """
    url = serve(ASK_PAGE)
    first, first_errors = open_page(browser, url, context=one_reader)
    second, second_errors = open_page(browser, url, context=one_reader)

    # Model a tab whose latest projection has not reached its neighbour yet. The draft
    # is born here, so this selection is the state the generation records.
    first.locator("#job-mounts").evaluate("el => el.setAttribute('chosen', '')")
    text = "Use a heated camera sleeve"
    first.locator("#jobs > .lf-another textarea").fill(text)
    expect(second.locator("#jobs > .lf-another textarea")).to_have_value(text)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first.locator("#jobs > .lf-another").get_by_role(
        "button", name="Add option", exact=True
    ).click()
    holding(first, held, 1, "the first added option")

    second.locator("#jobs > .lf-another").get_by_role(
        "button", name="Add option", exact=True
    ).click()
    round_trip(second)
    held_detail = held[0].request.post_data_json["detail"]
    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)

    additions = [
        event
        for event in sent_events(serve.page_dir)
        if event.get("kind") == "action"
        and event.get("widget") == "jobs"
        and event.get("detail", {}).get("additions")
    ]
    assert len(additions) == 1
    assert additions[0]["detail"] == held_detail
    assert _traffic(first).sends == _traffic(second).sends == 1
    assert first_errors == []
    assert second_errors == []


def test_a_comment_being_typed_reaches_the_pages_other_tabs(browser, serve, one_reader):
    """The general box and a thread's reply box are each one draft with a view in every
    tab. Both directions of the loop are here: words typed in one tab arrive in the
    other's box live, and a send there empties it — the distinction the store's own
    vocabulary carries, an emptied box being a value and a settled draft a tombstone.
    The Send button is read with the value, since a mirrored draft the box cannot send
    is words arriving dead."""
    url = serve(LONG_PAGE, comments=1)
    first, first_errors = open_page(browser, url, context=one_reader)
    second, second_errors = open_page(browser, url, context=one_reader)
    for page in (first, second):
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)

    typed = "The page is missing the migration step."
    first.locator(".lf-general textarea").fill(typed)
    expect(second.locator(".lf-general textarea")).to_have_value(typed)
    expect(second.locator(".lf-general button")).to_have_attribute(
        "aria-disabled", "false"
    )

    # The tab doing the typing is the one tab the store says nothing to, which is what
    # leaves the caret where the reader put it: writing .value on a focused box sends
    # the caret to the end of it, and a reader typing into the middle of a sentence
    # would watch every keystroke jump there.
    first.locator(".lf-general textarea").click()
    first.keyboard.press("Home")
    first.keyboard.type("Late: ")
    expect(second.locator(".lf-general textarea")).to_have_value("Late: " + typed)
    assert (
        first.locator(".lf-general textarea").evaluate("ta => ta.selectionStart") == 6
    ), "the caret moved in the tab that did the typing"
    typed = "Late: " + typed

    reply = "Typed into the reply box of the other tab."
    second.locator(".lf-thread textarea").first.fill(reply)
    expect(first.locator(".lf-thread textarea").first).to_have_value(reply)
    second.locator(".lf-thread").first.get_by_role(
        "button", name="Send", exact=True
    ).click()
    round_trip(second)
    expect(first.locator(".lf-thread textarea").first).to_have_value("")

    first.locator(".lf-general button").click()
    round_trip(first)
    expect(second.locator(".lf-general textarea")).to_have_value("")
    expect(second.locator(".lf-general button")).to_have_attribute(
        "aria-disabled", "true"
    )
    said = [e["text"] for e in events_model.read_events(serve.page_dir) if "text" in e]
    assert said[-2:] == [reply, typed]
    assert first_errors == []
    assert second_errors == []


def test_a_general_comment_appends_one_event_across_tabs(browser, serve, one_reader):
    """Both tabs may POST the shared generation; its attempt appends it once."""
    url = serve(LONG_PAGE)
    first, first_errors = open_page(browser, url, context=one_reader)
    second, second_errors = open_page(browser, url, context=one_reader)
    for page in (first, second):
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
    raw = "One general comment, however many tabs show its draft."
    first.locator(".lf-general textarea").fill(raw)
    expect(second.locator(".lf-general textarea")).to_have_value(raw)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first.locator(".lf-general button").click()
    holding(first, held, 1, "the first general send")
    second.locator(".lf-general button").click()
    round_trip(second)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    roots = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]
    assert roots[0]["attempt"]
    assert _traffic(first).sends == _traffic(second).sends == 1
    assert first_errors == []
    assert second_errors == []


def test_a_held_general_send_preserves_a_newer_exact_draft(browser, serve):
    """An earlier response settles only the general generation it posted."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    box = page.locator(".lf-general textarea")
    old = "The general comment already in flight."
    newer = "  The newer general thought keeps its spaces.  "
    box.fill(old)
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator(".lf-general button").click()
    holding(page, held, 1, "the older general send")
    box.fill(newer)

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(box).to_have_value(newer)
    assert page.evaluate(STORED_DRAFT_TEXT, "general") == newer
    roots = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [old]
    assert errors == []
    page.close()


def test_a_sent_comment_stands_in_the_panel_before_the_log_answers(browser, serve):
    """The words move from the box into the conversation in the gesture that sends them.

    Held rather than raced: the window is one request's flight, and what these
    assertions describe lasts exactly that long. The marked node is what the release is
    read by. A card drawn again under the server's id would look the same and pass every
    assertion about words on a screen, so the mark is the only thing that can tell an
    adopted card from an identical replacement — and the difference is a reader's place
    in the one they were already standing in.
    """
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    box = page.locator(".lf-general textarea")
    words = "The comment the reader can already see."
    box.fill(words)
    before = page.locator(".lf-threads > .lf-thread").count()
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.locator(".lf-general button").click()
    holding(page, held, 1, "the general send")

    pending = page.locator('.lf-thread[data-id^="pending:"]')
    expect(pending).to_have_count(1)
    expect(pending.locator(".lf-msg")).to_contain_text(words)
    expect(pending.locator(".lf-msg")).to_have_attribute("aria-busy", "true")
    expect(box).to_have_value("")
    assert not [
        event for event in sent_events(serve.page_dir) if event.get("text") == words
    ]
    page.evaluate(
        """() => {
          const card = document.querySelector('.lf-thread[data-id^="pending:"]');
          card.dataset.probe = "kept";
        }"""
    )

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(before + 1)
    expect(pending).to_have_count(0)
    kept = page.locator('.lf-thread[data-probe="kept"]')
    expect(kept).to_have_count(1)
    expect(kept.locator(".lf-msg")).not_to_have_attribute("aria-busy", "true")
    roots = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [words]
    assert errors == []
    page.close()


def test_a_refused_selection_comment_leaves_the_words_on_their_passage(
    held_events, serve
):
    """The composer goes down with the send, so a refusal has to put the words back in
    the store rather than in whatever box was on screen — the one they were typed in has
    gone with the thread they went to."""
    browser, held = held_events
    page, errors = open_page(browser, serve(LONG_PAGE))
    words = "The selection comment the server will refuse."
    compose(page, "#p3", words)
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the selection comment")

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    expect(page.locator(".lf-notice")).to_contain_text("Couldn't send")

    # Their passage still holds their draft, so opening it again finds the words.
    compose(page, "#p3")
    expect(page.locator(".lf-composer textarea")).to_have_value(words)
    assert not [
        event for event in sent_events(serve.page_dir) if event.get("text") == words
    ]
    assert errors and all("400" in error for error in errors)
    page.close()


def test_a_reply_behind_a_refused_parent_is_withdrawn_rather_than_sent(
    held_events, serve
):
    """A gesture against a message the log refused has nothing left to be about. It
    never reaches the wire under a name only this page used, and its own words go back
    to the box they were written in."""
    browser, held = held_events
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-general textarea").fill("The parent the server will refuse.")
    page.locator(".lf-general button").click()
    holding(page, held, 1, "the parent send")

    card = page.locator('.lf-thread[data-id^="pending:"]')
    expect(card).to_have_count(1)
    words = "A reply behind a parent that never lands."
    card.locator("textarea").first.fill(words)
    card.get_by_role("button", name="Send", exact=True).click()

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    round_trip(page)
    expect(card).to_have_count(0)
    assert not [
        route for route in held if "pending:" in (route.request.post_data or "")
    ], "a gesture reached the wire naming a thread the log never took"
    # The reply's draft keys by its thread's stable name, which is the parent's attempt.
    assert page.evaluate(STORED_DRAFT_TEXT, f"reply:{attempt}") == words
    assert errors and all("400" in error for error in errors)
    page.close()


def test_a_sent_reply_stands_in_its_thread_before_the_log_answers(held_events, serve):
    """A reply joins the conversation it answers without waiting for the round trip."""
    browser, held = held_events
    page, errors = open_page(browser, serve(LONG_PAGE, comments=2))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread_id = page.locator(".lf-threads > .lf-thread").first.get_attribute("data-id")
    thread = page.locator(f'.lf-thread[data-id="{thread_id}"]')
    words = "The reply the reader can already see."
    thread.locator("textarea").fill(words)
    before = thread.locator(".lf-msg").count()

    thread.get_by_role("button", name="Send", exact=True).click()
    holding(page, held, 1, "the reply send")

    expect(thread.locator(".lf-msg")).to_have_count(before + 1)
    expect(thread.locator(".lf-msg").last).to_contain_text(words)
    expect(thread.locator(".lf-msg").last).to_have_attribute("aria-busy", "true")
    expect(thread.locator("textarea")).to_have_value("")

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(thread.locator(".lf-msg")).to_have_count(before + 1)
    expect(thread.locator(".lf-msg").last).not_to_have_attribute("aria-busy", "true")
    replies = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "reply"
    ]
    assert [event["text"] for event in replies] == [words]
    assert errors == []
    page.close()


def test_a_refused_comment_takes_its_message_back_and_returns_the_words(
    held_events, serve
):
    """A refusal leaves nothing standing and the words back where they were written."""
    browser, held = held_events
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    box = page.locator(".lf-general textarea")
    words = "The comment the server will refuse."
    box.fill(words)
    before = page.locator(".lf-threads > .lf-thread").count()
    page.locator(".lf-general button").click()
    holding(page, held, 1, "the general send")
    expect(page.locator('.lf-thread[data-id^="pending:"]')).to_have_count(1)

    attempt = held[0].request.post_data_json["attempt"]
    with page.expect_response(lambda response: "/api/event" in response.url):
        held.pop(0).fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": attempt,
                "error": "refused before append",
                "final": True,
            },
        )
    expect(page.locator('.lf-thread[data-id^="pending:"]')).to_have_count(0)
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(before)
    expect(box).to_have_value(words)
    expect(page.locator(".lf-notice")).to_contain_text("Couldn't send")
    assert page.evaluate(STORED_DRAFT_TEXT, "general") == words
    assert not [
        event for event in sent_events(serve.page_dir) if event.get("text") == words
    ]
    assert errors and all("400" in error for error in errors)
    page.close()


@pytest.mark.parametrize("box", ["seat", "general"])
def test_every_message_send_says_so_to_a_reader_listening(held_events, serve, box):
    """A send whose result the reader cannot see still reaches them.

    The message standing in the conversation is the whole acknowledgement for a reader
    looking at it, which is why no box writes a success notice for it. But neither the
    seat nor the panel's list is a live region, so for a reader listening to the page
    that send would pass in silence. `post` says it once, where a gesture is first known
    to be a message, which is what covers every box that sends one.
    """
    browser, held = held_events
    page, errors = open_page(browser, serve(SEATED_QUESTION_PAGE))
    live = page.locator(".lf-live")
    if box == "seat":
        seat = page.locator("#jobs > .lf-conversation > .lf-say")
        field = seat.locator("textarea")
        press = seat.get_by_role("button", name="Send", exact=True)
    else:
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
        field = page.locator(".lf-general textarea")
        press = page.locator(".lf-general").get_by_role(
            "button", name="Send", exact=True
        )
    field.fill("A remark whose arrival nothing else will say.")
    press.click()
    # Held: the gesture is the only thing that can have written the region, and the
    # words are said before the log has answered rather than because it did.
    holding(page, held, 1, "the send")
    expect(live).to_have_text("Message sent")

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    assert errors == []
    page.close()


def test_a_first_answer_leaves_a_later_sends_words_masked(held_events, serve):
    """One box, two sends: answering the first must not hand back the second's words.

    A send empties the box it was written in and masks that generation, so this
    document stops showing words it is now showing in the thread. The answer lifts that
    mask — and lifting whichever mask happens to be standing, rather than the one this
    send put there, lifts a later send's: words the reader is already watching as a
    pending reply go back on offer while that reply is still in flight. The outbox
    delivers in order, so the first answer always lands while the second send is
    unanswered. That makes the window ordinary rather than rare.
    """
    browser, held = held_events
    url = serve(SEATED_QUESTION_PAGE)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Which job comes first?",
        },
    )
    page, errors = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread")
    reply = thread.locator("textarea")
    send = thread.get_by_role("button", name="Send", exact=True)

    first = "The reply already on its way."
    reply.fill(first)
    send.click()
    holding(page, held, 1, "the first reply send")
    expect(reply).to_have_value("")

    second = "The reply the reader is watching."
    reply.fill(second)
    send.click()
    expect(reply).to_have_value("")
    # Both stand, in the order they were written. A card gains messages by insertion,
    # and a receipt acknowledging an earlier one sits between them.
    expect(thread.locator(".lf-msg").last).to_contain_text(second)
    expect(thread.locator(".lf-msg").nth(-2)).to_contain_text(first)

    held.pop(0).continue_()
    holding(page, held, 1, "the second reply send, once the first is answered")

    # What a widget asks of a draft box, through the public helper surface. The boxes
    # alone would not say this: nothing repaints one when a mask is lifted, so the
    # offer stands unseen until some view of this thread is next built and reads it.
    standing = page.evaluate(
        """async (ctx) => {
          const api = await import('/runtime/widget-api.js');
          return api.loadDraft(ctx);
        }""",
        f"reply:{root['id']}",
    )
    assert standing is None, "the second send's words were offered back while in flight"
    expect(reply).to_have_value("")
    expect(page.locator("#jobs .lf-conversation-thread textarea")).to_have_value("")

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    spoken = thread.locator(".lf-msg").all_inner_texts()
    assert [
        words for words in (first, second) if not any(words in s for s in spoken)
    ] == []
    assert errors == []
    page.close()


@pytest.mark.parametrize("same_thread", [False, True])
def test_a_held_reply_send_leaves_a_later_reply_box_focused(
    held_events, serve, same_thread
):
    """A later draft keeps its focus and remains visible when a reply arrives.

    The long sent message tests reflow above a draft in the same card; the distant
    card tests a reader who has moved to another conversation.
    """
    browser, held = held_events
    page, errors = open_page(browser, serve(LONG_PAGE, comments=8))
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads > .lf-thread")
    first_id = threads.nth(0).get_attribute("data-id")
    later_id = first_id if same_thread else threads.last.get_attribute("data-id")
    first = page.locator(f'.lf-thread[data-id="{first_id}"] textarea')
    later = page.locator(f'.lf-thread[data-id="{later_id}"] textarea')
    first.fill("\n\n".join(["The first reply is in flight."] * 15))

    page.locator(f'.lf-thread[data-id="{first_id}"]').get_by_role(
        "button", name="Send", exact=True
    ).click()
    holding(page, held, 1, "the first reply send")

    later.click()
    newer = "The later reply keeps the reader here.\n" * (14 if same_thread else 1)
    later.fill(newer)
    expect(later).to_be_focused()
    in_threads_scrollport(page, f'.lf-thread[data-id="{later_id}"] textarea')

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(
        page.locator(f'.lf-thread[data-id="{first_id}"] .lf-msg').last
    ).to_contain_text("The first reply is in flight.")
    expect(later).to_be_focused()
    expect(later).to_have_value(newer)
    in_threads_scrollport(page, f'.lf-thread[data-id="{later_id}"] textarea')
    assert errors == []
    page.close()


@pytest.mark.parametrize("continue_inline", [False, True])
def test_a_held_reply_send_leaves_the_panel_closed(held_events, serve, continue_inline):
    """Closing Threads during delivery is later than sending the reply."""
    browser, held = held_events
    url = serve(SEATED_QUESTION_PAGE)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Which job comes first?",
        },
    )
    page, errors = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    toggle = page.locator(".lf-threads-toggle")
    toggle.click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread")
    reply = thread.locator("textarea")
    reply.fill("Send this while I return to reading.")
    thread.get_by_role("button", name="Send", exact=True).click()
    holding(page, held, 1, "the reply send")

    toggle.click()
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    expect(toggle).to_be_focused()
    inline = page.locator(
        f'#jobs .lf-conversation-thread[data-thread="{root["id"]}"] textarea'
    )
    newer = "Continue this reply beside the question."
    if continue_inline:
        inline.fill(newer)
        inline.evaluate("box => box.setSelectionRange(9, 9)")
        expect(reply).to_have_value(newer)
    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(reply).to_have_value(newer if continue_inline else "")
    expect(thread.locator(".lf-msg").last).to_contain_text(
        "Send this while I return to reading."
    )
    expect(page.locator(".lf-thread-panel")).not_to_be_visible()
    if continue_inline:
        expect(inline).to_be_focused()
        expect(inline).to_have_value(newer)
        assert inline.evaluate("box => box.selectionStart") == 9
    else:
        expect(toggle).to_be_focused()
    assert errors == []
    page.close()


def test_a_held_reply_send_preserves_a_later_scroll(held_events, serve):
    """A wheel can move the reading place while leaving the old reply focused."""
    browser, held = held_events
    page, errors = open_page(browser, serve(LONG_PAGE, comments=12))
    page.emulate_media(reduced_motion="reduce")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-threads > .lf-thread")
    first = threads.first
    later = threads.last
    reply = first.locator("textarea")
    reply.fill("A reply whose delivery is slow.")
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the reply send")

    bounds = page.locator(".lf-threads").bounding_box()
    page.mouse.move(
        bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
    )
    page.mouse.wheel(0, 3500)
    expect(later).to_be_in_viewport()
    expect(reply).to_be_focused()
    before = later.evaluate("node => node.getBoundingClientRect().top")

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(reply).to_have_value("")
    expect(first.locator(".lf-msg").last).to_contain_text(
        "A reply whose delivery is slow."
    )
    expect(later).to_be_in_viewport()
    assert later.evaluate("node => node.getBoundingClientRect().top") == pytest.approx(
        before, abs=1
    )
    expect(reply).to_be_focused()
    assert errors == []
    page.close()


def test_a_held_comment_send_leaves_a_later_reply_box_focused(browser, serve):
    """Opening a reply while a new comment is in flight is a later gesture. The
    comment still appears, but its arrival must not move focus into its new thread."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=2))
    select_words(page, "#p3")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    page.locator(".lf-composer textarea").fill("The earlier comment in flight.")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the comment send")

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    # Another thread than the one in flight: that one's card is in this list too now,
    # standing for the comment while the log answers for it.
    later_id = page.locator(
        '.lf-threads > .lf-thread:not([data-id^="pending:"])'
    ).first.get_attribute("data-id")
    later = page.locator(f'.lf-thread[data-id="{later_id}"] textarea')
    later.fill("The later reply keeps the reader here.")
    later.evaluate("ta => ta.setSelectionRange(9, 9)")
    expect(later).to_be_focused()

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(3)
    expect(later).to_be_focused()
    expect(later).to_have_value("The later reply keeps the reader here.")
    assert later.evaluate("ta => ta.selectionStart") == 9
    assert errors == []
    page.close()


@pytest.mark.parametrize("later_selection", [False, True])
def test_a_comment_hidden_by_narrowing_is_revealed_in_the_open_panel(
    browser, serve, later_selection
):
    """A new comment widens the panel's filter without taking a later selection."""
    page, errors = open_page(browser, serve(NOTED_PAGE, comments=1))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator(".lf-find-box").fill("Comment 0")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(1)

    select_words(page, "#p1")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    page.locator(".lf-composer textarea").fill(
        "This comment starts outside the filter."
    )
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the filtered comment send")
    if later_selection:
        select_words(page, "#p2")
        expect(page.locator(".lf-fab-input")).to_be_visible()
        assert pending_text(page) == "A short second passage."

    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)

    sent = next(
        event
        for event in reversed(events_model.read_events(serve.page_dir))
        if event.get("text") == "This comment starts outside the filter."
    )
    expect(page.locator(".lf-thread-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    expect(page.locator(".lf-find-box")).to_have_value("")
    thread = page.locator(f'.lf-thread[data-id="{sent["id"]}"]')
    expect(thread).to_contain_text(sent["text"])
    if later_selection:
        assert pending_text(page) == "A short second passage."
        expect(page.locator(".lf-fab-input")).to_be_visible()
        expect(page.locator(".lf-fab-input")).not_to_be_focused()
        assert composer_quote(page)["text"].strip("“”") == "A short second passage."
    else:
        expect(thread.locator("textarea")).to_be_focused()
    assert errors == []
    page.close()


def test_an_untouched_inline_reply_follows_but_an_emptied_draft_holds(browser, serve):
    """Focus handed to a new reply is not itself a draft; an edit to empty is."""
    page, errors = open_page(browser, live_url(serve(NOTED_PAGE)))
    resized(page, 1440, 900)
    select_words(page, "#p1")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    page.locator(".lf-composer textarea").fill("Follow this discussion.")
    # The comment's own send in the wire before the log names it. Without that the read
    # below answers with the note the page opened on, and the reply this test is about is
    # looked for under an id no thread wears.
    with sending(page, "the comment the reply follows"):
        page.keyboard.press("ControlOrMeta+Enter")

    sent = events_model.read_events(serve.page_dir)[-1]
    reply = page.locator(
        f'.lf-margin-thread .lf-conversation-thread[data-thread="{sent["id"]}"] textarea'
    )
    expect(reply).to_be_focused()

    d = serve.page_dir
    v2 = NOTED_PAGE.replace(
        "A short second passage.", "A revised short second passage."
    )
    (d / ".fixture-versions" / "v2.html").write_text(v2)
    stamp_version_file(d, 2, "v2")
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")

    reply.fill("A thought I changed my mind about.")
    reply.fill("")
    # A thread's reply draft is keyed by the name the log's answer does not change —
    # the attempt the reader's own comment opened it with (conversation/model.js).
    assert page.evaluate(STORED_DRAFT_TEXT, f"reply:{sent['attempt']}") == ""
    v3 = v2.replace(
        "A revised short second passage.", "A twice-revised short second passage."
    )
    (d / ".fixture-versions" / "v3.html").write_text(v3)
    stamp_version_file(d, 3, "v3")
    told(page)
    expect(page.locator(".lf-latest-chip")).to_be_visible()
    expect(page.locator(".lf-version")).to_contain_text("v2")
    expect(reply).to_have_value("")
    expect(reply).to_be_focused()
    assert errors == []
    page.close()


def test_a_held_comment_send_leaves_the_passage_picked_out_behind_it(
    held_events, serve
):
    """A comment's send must not take a newer passage selection with its focus handoff.

    The newer selection remains native and keeps its response field available while the
    earlier send becomes a thread behind it.

    Held rather than raced: the window is one request's flight, and a machine quick
    enough closes it before the next gesture. A loaded CI runner is not, and it said so
    as a 💬 that never came up for the passage picked out after a send."""
    browser, held = held_events
    page, errors = open_page(browser, serve(NOTED_PAGE))
    select_words(page, "#p1")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    page.locator(".lf-fab-input").click()
    page.locator(".lf-composer textarea").fill("The first remark.")

    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the comment send")

    # The reader picks out their next passage while the first send is still in the wire.
    select_words(page, "#p2")
    expect(page.locator(".lf-fab-input")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_have_value("")
    expect(page.locator(".lf-fab-input")).not_to_be_focused()

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator(".lf-thread")).to_have_count(1)

    # The send landed behind them and left the passage picked out. Read as the reader's
    # own next gesture rather than as the button's rendering: the button is a state that
    # only a fresh decision repaints, so it stands wherever the last one left it — while
    # the key that comments on a selection reads the live one, and answers the general
    # box where there is none.
    assert pending_text(page) == "A short second passage.", (
        "the send's landing lost the passage the reader had picked out"
    )
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert composer_quote(page)["text"].strip("“”") == "A short second passage."
    assert errors == []
    page.close()


def test_a_held_comment_send_leaves_a_later_keyboard_comment_open(held_events, serve):
    """The Comment opened with `s` is later than a comment already in flight."""
    browser, held = held_events
    page, errors = open_page(browser, serve(NOTED_PAGE))
    compose(page, "#p1", "The first remark.")

    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the comment send")

    # Leave the sending field, then use the keyboard Comment path on p2.
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fab-input")).to_be_hidden()
    page.keyboard.press("s")
    expect(page.locator(".lf-target-hint")).not_to_have_count(0)
    target_code = page.evaluate(
        """() => {
          const top = document.querySelector('#p2').getBoundingClientRect().top;
          return [...document.querySelectorAll('.lf-target-hint')]
            .sort((a, b) => Math.abs(a.getBoundingClientRect().top - top)
                          - Math.abs(b.getBoundingClientRect().top - top))[0]
            .dataset.lfTarget;
        }"""
    )
    page.keyboard.type(target_code)
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator("#p2")).to_have_class(
        re.compile(r"\blf-mark-el\b.*\blf-pending\b")
    )
    expect(page.locator(".lf-fab-bar")).to_have_attribute(
        "aria-label", re.compile(r"^Respond to paragraph")
    )

    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)

    expect(page.locator(".lf-thread")).to_have_count(1)
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator("#p2")).to_have_class(
        re.compile(r"\blf-mark-el\b.*\blf-pending\b")
    )
    expect(page.locator(".lf-fab-bar")).to_have_attribute(
        "aria-label", re.compile(r"^Respond to paragraph")
    )
    assert composer_quote(page)["text"].endswith("A short second passage.")
    assert errors == []
    page.close()


def test_an_unsent_comment_stays_with_its_passage_when_another_is_selected(
    browser, serve
):
    """Opening fields is automatic, so selecting a new passage is not re-anchoring.

    Each passage keeps its own durable draft: the newly selected passage starts empty,
    and returning to the original passage restores the words written about it."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    field = page.locator(".lf-fab-input")
    original = "These words belong to the first passage."

    select_words(page, "#p1")
    expect(field).to_be_visible()
    expect(field).not_to_be_focused()
    field.fill(original)

    select_words(page, "#p2")
    expect(field).to_have_value("")
    expect(field).not_to_be_focused()
    assert (
        page.evaluate(
            """() => Object.keys(localStorage)
          .filter(key => key.startsWith('lf-draft:composer:')).length"""
        )
        == 1
    )

    select_words(page, "#p1")
    expect(field).to_have_value(original)
    expect(field).not_to_be_focused()
    assert errors == []
    page.close()


def test_failed_settlement_keeps_the_base_for_a_chained_nondurable_edit(
    browser, serve, one_reader
):
    """A failed tombstone does not make the next local edit descend from thin air."""
    url = serve(LONG_PAGE)
    shared, shared_errors = open_page(browser, url, context=one_reader)
    local, local_errors = open_page(browser, url, context=one_reader)
    for page in (shared, local):
        page.locator(".lf-threads-toggle").click()
        panel_settled(page)
    predecessor = "The durable predecessor that this local branch replaces."
    first = "The first nondurable comment on that branch."
    second = "The chained nondurable comment keeps the same base."
    shared.locator(".lf-general textarea").fill(predecessor)
    expect(local.locator(".lf-general textarea")).to_have_value(predecessor)
    local.evaluate(
        """([first, second]) => {
          const set = Storage.prototype.setItem;
          let secondFailed = false;
          window.lfBranchAttempt = null;
          Storage.prototype.setItem = function (key, value) {
            if (key === 'lf-draft:general') {
              const record = JSON.parse(value);
              if (record.text === first) {
                window.lfBranchAttempt = record.attempt;
                throw new DOMException('full', 'QuotaExceededError');
              }
              if (record.settled && record.attempt === window.lfBranchAttempt)
                throw new DOMException('full', 'QuotaExceededError');
              if (record.text === second && !secondFailed) {
                secondFailed = true;
                throw new DOMException('full', 'QuotaExceededError');
              }
            }
            return set.call(this, key, value);
          };
        }""",
        [first, second],
    )

    local.locator(".lf-general textarea").fill(first)
    local.locator(".lf-general button").click()
    round_trip(local)
    expect(local.locator(".lf-general textarea")).to_have_value("")
    local.locator(".lf-general textarea").fill(second)
    expect(local.locator(".lf-general button")).to_have_attribute(
        "aria-disabled", "false"
    )
    local.locator(".lf-general button").click()
    _until(local, lambda traffic: traffic.sends == 2, "sent the chained generation")
    round_trip(local)

    comments = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "comment"
    ]
    assert [event["text"] for event in comments] == [first, second]
    assert len({event["attempt"] for event in comments}) == 2
    # The tombstone is written where the send reads its own response, one step behind the
    # response itself: `round_trip` watches the browser's trip, and the page settles the
    # generation in the continuation after it — so the log holds the send before the store
    # holds its settlement. Read the store on the fact the page states, the way the tabs
    # below do; a plain read is the same assertion made a step early, and a loaded runner
    # lands in that step, which is what CI read here as an unsettled chain.
    local.wait_for_function(STORED_DRAFT_SETTLED, arg="general")
    assert shared_errors == []
    assert local_errors == []


def test_a_stale_question_first_message_cannot_append_across_tabs(
    browser, serve, one_reader
):
    """A stale visible generation refreshes the shared tombstone before POST.

    The second tab's storage repaint is then deliberately suppressed. Its textarea
    remains stale after the first send stored its tombstone, so a second real press
    proves that readable absence is settlement rather than permission to trust the
    old in-memory value.
    """
    url = serve(SEATED_QUESTION_PAGE)
    first, first_errors = open_page(browser, url, context=one_reader)
    second, second_errors = open_page(
        browser,
        url,
        context=one_reader,
        init_script="""addEventListener('storage', event => {
          if (event.key !== 'lf-draft:say:jobs') return;
          try {
            if (JSON.parse(event.newValue)?.settled)
              event.stopImmediatePropagation();
          } catch {}
        }, true);""",
    )
    first_say = first.locator("#jobs > .lf-conversation > .lf-say")
    second_say = second.locator("#jobs > .lf-conversation > .lf-say")
    raw = "  Keep one exact first answer.  "
    first_say.locator("textarea").fill(raw)
    expect(second_say.locator("textarea")).to_have_value(raw)
    # The init-script capture listener beats the runtime's listener for settlement,
    # leaving the old value on screen after the other tab stores its tombstone.
    cut = CutOff().hold(second)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first_say.get_by_role("button", name="Send", exact=True).click()
    holding(first, held, 1, "the first answer")

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    first.wait_for_function(STORED_DRAFT_SETTLED, arg="say:jobs")
    expect(second_say.locator("textarea")).to_have_value(raw)
    assert second.evaluate(STORED_DRAFT_SETTLED, "say:jobs")
    second_send = second_say.get_by_role("button", name="Send", exact=True)
    expect(second_send).to_have_attribute("aria-disabled", "false")
    second_send.click()
    expect(second_say.locator("textarea")).to_have_value("")
    cut.restore()

    roots = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "comment"
    ]
    assert [(event["anchor"], event["text"]) for event in roots] == [
        ({"section": "jobs"}, raw)
    ]
    assert _traffic(first).sends + _traffic(second).sends == 1
    assert first_errors == []
    assert second_errors == []


def test_a_question_reply_appends_one_event_across_tabs(browser, serve, one_reader):
    """Both inline views may POST the shared reply; its attempt appends it once."""
    url = serve(SEATED_QUESTION_PAGE)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Which job should come first?",
        },
    )
    first, first_errors = open_page(browser, url, context=one_reader)
    second, second_errors = open_page(browser, url, context=one_reader)
    selector = (
        f"#jobs > .lf-conversation > .lf-conversation-thread"
        f'[data-thread="{root["id"]}"]'
    )
    first_thread = first.locator(selector)
    second_thread = second.locator(selector)
    raw = "  The camera, then the mounting work.  "
    first_thread.locator("textarea").fill(raw)
    expect(second_thread.locator("textarea")).to_have_value(raw)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first_thread.get_by_role("button", name="Send", exact=True).click()
    holding(first, held, 1, "the first reply")
    second_thread.get_by_role("button", name="Send", exact=True).click()
    round_trip(second)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    replies = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "reply"
    ]
    assert [(event["parent"], event["text"]) for event in replies] == [
        (root["id"], raw)
    ]
    assert _traffic(first).sends == _traffic(second).sends == 1
    assert first_errors == []
    assert second_errors == []


def test_a_held_conversation_send_cannot_clear_a_newer_raw_draft(
    browser, serve, one_reader
):
    """Settlement compares raw words, so an older POST cannot erase a later edit."""
    url = serve(SEATED_QUESTION_PAGE)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "What should the order be?",
        },
    )
    first, first_errors = open_page(browser, url, context=one_reader)
    second, second_errors = open_page(browser, url, context=one_reader)
    first.locator(".lf-threads-toggle").click()
    panel_settled(first)
    inline = first.locator(
        f'#jobs .lf-conversation-thread[data-thread="{root["id"]}"] textarea'
    )
    panel = first.locator(f'.lf-thread[data-id="{root["id"]}"]')
    second_inline = second.locator(
        f'#jobs .lf-conversation-thread[data-thread="{root["id"]}"] textarea'
    )
    sent_raw = "  Send this part first.  "
    newer_raw = "  A later thought stays raw.  "
    inline.fill(sent_raw)
    expect(panel.locator("textarea")).to_have_value(sent_raw)
    expect(second_inline).to_have_value(sent_raw)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    panel.get_by_role("button", name="Send", exact=True).click()
    holding(first, held, 1, "the older reply")
    second_inline.fill(newer_raw)
    expect(inline).to_have_value(newer_raw)
    expect(panel.locator("textarea")).to_have_value(newer_raw)

    held[0].continue_()
    first.unroute("**/api/event")
    round_trip(first)
    expect(inline).to_have_value(newer_raw)
    expect(panel.locator("textarea")).to_have_value(newer_raw)
    expect(second_inline).to_have_value(newer_raw)
    # This root was appended by the agent, so it carries no attempt and its reply draft
    # keys by the id, which for such a thread never changes either.
    assert first.evaluate(STORED_DRAFT_TEXT, f"reply:{root['id']}") == newer_raw
    replies = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "reply"
    ]
    assert [event["text"] for event in replies] == [sent_raw]
    assert first_errors == []
    assert second_errors == []


def test_a_failed_concurrent_question_send_keeps_the_accepted_attempt(
    browser, serve, one_reader
):
    """One request may lose its answer while another tab gets the same attempt
    accepted. The first tab adopts that durable outcome instead of reporting failure
    or offering the words as a second message."""
    url = serve(SEATED_QUESTION_PAGE)
    first, first_errors = open_page(browser, url, context=one_reader)
    second, second_errors = open_page(browser, url, context=one_reader)
    first_say = first.locator("#jobs > .lf-conversation > .lf-say")
    second_say = second.locator("#jobs > .lf-conversation > .lf-say")
    raw = "  Retry this exact answer.  "
    first_say.locator("textarea").fill(raw)
    expect(second_say.locator("textarea")).to_have_value(raw)

    held = []
    first.route("**/api/event", lambda route: held.append(route))
    first_say.get_by_role("button", name="Send", exact=True).click()
    holding(first, held, 1, "the failing answer")
    second_say.get_by_role("button", name="Send", exact=True).click()
    round_trip(second)

    refuse(held[0])
    first.unroute("**/api/event")
    round_trip(first)
    # The words standing in the seat's own conversation are what says the send landed;
    # a notice saying so beside them would be the same acknowledgement twice.
    expect(first.locator("#jobs > .lf-conversation")).to_contain_text(raw.strip())
    roots = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]
    # Asked of the words rather than of the box: a seat that can hold keeps its composer
    # standing after every root (renderConversations), so an empty one is what says the
    # tab adopted the durable outcome instead of holding the words for a second send.
    expect(first_say.locator("textarea")).to_have_value("")
    expect(second_say.locator("textarea")).to_have_value("")
    assert first_errors == []
    assert second_errors == []


@pytest.mark.parametrize("newer", [None, "A newer thought must survive."])
def test_a_late_refusal_cannot_restore_an_attempt_another_tab_settled(
    browser, serve, one_reader, newer
):
    """A final answer belongs to one execution; the accepted log owns the draft."""
    url = serve(SEATED_QUESTION_PAGE)
    first, first_errors = open_page(browser, url, context=one_reader)
    second, second_errors = open_page(browser, url, context=one_reader)
    first_say = first.locator("#jobs > .lf-conversation > .lf-say")
    second_say = second.locator("#jobs > .lf-conversation > .lf-say")
    raw = "The shared generation one tab will accept."
    first_say.locator("textarea").fill(raw)
    expect(second_say.locator("textarea")).to_have_value(raw)

    held_event = []
    held_state = []
    first.route("**/api/event", lambda route: held_event.append(route))
    first.route("**/api/state*", lambda route: held_state.append(route))
    try:
        first_say.get_by_role("button", name="Send", exact=True).click()
        holding(first, held_event, 1, "the first tab's answer")
        attempt = held_event[0].request.post_data_json["attempt"]

        second_say.get_by_role("button", name="Send", exact=True).click()
        round_trip(second)
        expect(first_say.locator("textarea")).to_have_value("")
        first.wait_for_function(STORED_DRAFT_SETTLED, arg="say:jobs")
        holding(first, held_state, 1, "the accepted attempt's state read")
        if newer is not None:
            first_say.locator("textarea").fill(newer)

        with first.expect_response(
            lambda response: "/api/event" in response.url
        ) as refused:
            held_event.pop(0).fulfill(
                status=400,
                json={
                    "ok": False,
                    "final": True,
                    "attempt": attempt,
                    "error": "the earlier execution was refused",
                },
            )
        expect(first.locator(".lf-notice")).to_contain_text("Couldn't send")
        expected_error = f"400 {refused.value.url}"
        first_errors.remove(expected_error)
        first_errors.remove(
            "Failed to load resource: the server responded with a status of 400 "
            "(Bad Request)"
        )
        expect(first_say.locator("textarea")).to_have_value(newer or "")

        held_state.pop(0).continue_()
        first.unroute("**/api/state*")
        round_trip(first)
        expect(first_say.locator("textarea")).to_have_value(newer or "")
        assert first_errors == []
        assert second_errors == []
    finally:
        for route in held_event + held_state:
            refuse(route)
        first.unroute_all(behavior="wait")


def test_a_question_can_send_when_draft_storage_refuses_writes(browser, serve):
    """Persistence failure costs recovery, not the live textarea's Send action."""
    page, errors = open_page(
        browser,
        serve(SEATED_QUESTION_PAGE),
        init_script="""Storage.prototype.setItem = function () {
          throw new DOMException('blocked', 'SecurityError');
        };""",
    )
    say = page.locator("#jobs > .lf-conversation > .lf-say")
    raw = "  Send even though this draft cannot persist.  "
    say.locator("textarea").fill(raw)
    say.get_by_role("button", name="Send", exact=True).click()
    _until(page, lambda t: t.sends == 1, "sent the live unpersisted answer")
    round_trip(page)
    roots = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]
    assert errors == []
    page.close()


def test_a_closed_sender_cannot_append_its_accepted_attempt_twice(
    browser, serve, one_reader
):
    """The log returns the accepted attempt when its first sender cannot settle it.

    Both tabs are held stale, and each refusal states one half of that sentence. The
    wrapper below closes the send path — the POST lands, the runtime never hears the
    answer — and the poll is the other way the same tab settles a draft
    (settleAcceptedDrafts), so a sender left polling can still tombstone the shared
    generation out from under the replacement. It did: within a poll of the server
    taking the answer, first's own next poll read the attempt back out of the log and
    settled it, second's box emptied, and the send this test is about had nothing left
    to send — sends=0, the failure landing either on `sendDraft` refusing a settled
    record or on Playwright refusing a Send the box had already disabled, depending on
    which side of the click the storage event fell. The race was one poll interval
    against Playwright's own click, which is a gap only a loaded machine loses.

    Second's refusal is the older half and states the same fact from its own side: the
    replacement must not learn the attempt is in the log before it sends, or it would
    correctly decline to. Both go through `held_stale` rather than a live `page.route`,
    which reaches no poll already in the wire."""
    url = serve(SEATED_QUESTION_PAGE)
    first, _ = open_page(browser, url, context=held_stale(one_reader))
    second_held = held_stale(one_reader)
    second, second_errors = open_page(browser, url, context=second_held)
    raw = "One answer survives its sender closing."
    first_say = first.locator("#jobs > .lf-conversation > .lf-say")
    second_say = second.locator("#jobs > .lf-conversation > .lf-say")
    first_say.locator("textarea").fill(raw)
    expect(second_say.locator("textarea")).to_have_value(raw)
    first.evaluate(
        """() => {
          const actualFetch = window.fetch.bind(window);
          window.fetch = (input, init) => {
            const sent = actualFetch(input, init);
            if (!String(input).endsWith('/api/event')) return sent;
            return sent.then(() => {
              window.lfAcceptedAttempt = true;
              return new Promise(() => {});
            });
          };
        }"""
    )
    first_say.get_by_role("button", name="Send", exact=True).click()
    _until(first, lambda t: t.sends == 1, "sent the first answer to the server")
    first.wait_for_function("() => window.lfAcceptedAttempt === true")
    second_say.get_by_role("button", name="Send", exact=True).click()
    _until(second, lambda t: t.acked == 1, "received the accepted attempt")

    first.close()
    second_held.restore()
    told(second)
    roots = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "comment"
    ]
    assert len(roots) == 1
    assert roots[0]["text"] == raw
    assert roots[0]["attempt"]
    assert second_errors == []


def test_an_older_settlement_cannot_erase_a_newer_failed_write(
    browser, serve, one_reader
):
    """A nondurable local generation outranks storage news about its predecessor."""
    url = serve(SEATED_QUESTION_PAGE)
    other, other_errors = open_page(browser, url, context=one_reader)
    old = "The older persisted answer."
    other_say = other.locator("#jobs > .lf-conversation > .lf-say")
    other_say.locator("textarea").fill(old)

    local, local_errors = open_page(
        browser,
        url,
        context=one_reader,
        init_script="""Storage.prototype.setItem = function () {
          throw new DOMException('full', 'QuotaExceededError');
        };""",
    )
    local_say = local.locator("#jobs > .lf-conversation > .lf-say")
    expect(local_say.locator("textarea")).to_have_value(old)
    newer = "The newer local answer whose write failed."
    local_say.locator("textarea").fill("A first nondurable edit on the same branch.")
    local_say.locator("textarea").fill(newer)
    expect(other_say.locator("textarea")).to_have_value(old)

    other_say.get_by_role("button", name="Send", exact=True).click()
    round_trip(other)
    other.wait_for_function(STORED_DRAFT_SETTLED, arg="say:jobs")
    expect(local_say.locator("textarea")).to_have_value(newer)

    local_say.get_by_role("button", name="Send", exact=True).click()
    _until(local, lambda t: t.sends == 1, "sent the nondurable newer answer")
    round_trip(local)
    roots = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [old, newer]
    assert len({event["attempt"] for event in roots}) == 2
    assert other_errors == []
    assert local_errors == []


def test_an_accepted_nondurable_branch_cannot_tombstone_a_newer_shared_generation(
    browser, serve, one_reader
):
    """A held older send reconciles its base before writing settlement."""
    url = serve(SEATED_QUESTION_PAGE)
    older, older_errors = open_page(
        browser,
        url,
        context=one_reader,
        init_script="""(() => {
          const set = Storage.prototype.setItem;
          let refuse = true;
          Storage.prototype.setItem = function (key, value) {
            if (refuse && key === 'lf-draft:say:jobs') {
              refuse = false;
              throw new DOMException('full', 'QuotaExceededError');
            }
            return set.call(this, key, value);
          };
          addEventListener('storage', event => {
            if (event.key === 'lf-draft:say:jobs') event.stopImmediatePropagation();
          }, true);
        })();""",
    )
    newer_tab, newer_errors = open_page(browser, url, context=one_reader)
    older_say = older.locator("#jobs > .lf-conversation > .lf-say")
    newer_say = newer_tab.locator("#jobs > .lf-conversation > .lf-say")
    old = "The older nondurable answer already in flight."
    newer = "The newer durable answer survives the older response."
    older_say.locator("textarea").fill(old)

    held = []
    older.route("**/api/event", lambda route: held.append(route))
    older_say.get_by_role("button", name="Send", exact=True).click()
    holding(older, held, 1, "the nondurable send")
    newer_say.locator("textarea").fill(newer)
    assert newer_tab.evaluate(STORED_DRAFT_TEXT, "say:jobs") == newer
    newer_tab.close()

    held[0].continue_()
    older.unroute("**/api/event")
    round_trip(older)
    restored = older.locator("#jobs > .lf-conversation > .lf-say textarea")
    expect(restored).to_have_value(newer)
    assert older.evaluate(STORED_DRAFT_TEXT, "say:jobs") == newer
    roots = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [old]
    assert older_errors == []
    assert newer_errors == []


def test_a_nondurable_branch_yields_to_unrelated_live_storage_news(
    browser, serve, one_reader
):
    """Only news from a branch's base may be replaced by that local branch."""
    url = serve(SEATED_QUESTION_PAGE)
    local, local_errors = open_page(
        browser,
        url,
        context=one_reader,
        init_script="""(() => {
          const set = Storage.prototype.setItem;
          let refuse = true;
          Storage.prototype.setItem = function (key, value) {
            if (refuse && key === 'lf-draft:say:jobs') {
              refuse = false;
              throw new DOMException('full', 'QuotaExceededError');
            }
            return set.call(this, key, value);
          };
          window.lfDraftNews = 0;
          addEventListener('storage', event => {
            if (event.key === 'lf-draft:say:jobs') window.lfDraftNews += 1;
          }, true);
        })();""",
    )
    shared, shared_errors = open_page(browser, url, context=one_reader)
    local_say = local.locator("#jobs > .lf-conversation > .lf-say")
    shared_say = shared.locator("#jobs > .lf-conversation > .lf-say")
    old = "The local write failed before shared storage changed."
    newer = "The later durable generation owns the reader now."
    local_say.locator("textarea").fill(old)
    shared_say.locator("textarea").fill(newer)
    local.wait_for_function("() => window.lfDraftNews > 0")

    expect(local_say.locator("textarea")).to_have_value(newer)
    expect(shared_say.locator("textarea")).to_have_value(newer)
    assert local.evaluate(STORED_DRAFT_TEXT, "say:jobs") == newer
    assert local_errors == []
    assert shared_errors == []


def test_a_delayed_storage_event_cannot_send_a_stale_durable_generation(
    browser, serve, one_reader
):
    """Send refreshes shared storage instead of trusting a stale durable cache."""
    url = serve(SEATED_QUESTION_PAGE)
    stale, stale_errors = open_page(
        browser,
        url,
        context=held_stale(one_reader),
        init_script="""addEventListener('storage', event => {
          if (event.key === 'lf-draft:say:jobs') event.stopImmediatePropagation();
        }, true);""",
    )
    current, current_errors = open_page(browser, url, context=one_reader)
    stale_say = stale.locator("#jobs > .lf-conversation > .lf-say")
    current_say = current.locator("#jobs > .lf-conversation > .lf-say")
    old = "The stale tab's older generation."
    newer = "The newer shared generation."
    stale_say.locator("textarea").fill(old)
    expect(current_say.locator("textarea")).to_have_value(old)
    current_say.locator("textarea").fill(newer)
    expect(stale_say.locator("textarea")).to_have_value(old)
    assert stale.evaluate(STORED_DRAFT_TEXT, "say:jobs") == newer

    stale_say.get_by_role("button", name="Send", exact=True).click()
    assert _traffic(stale).sends == 0
    expect(stale_say.locator("textarea")).to_have_value(newer)
    expect(current_say.locator("textarea")).to_have_value(newer)
    assert [
        event for event in sent_events(serve.page_dir) if event["kind"] == "comment"
    ] == []
    assert stale_errors == []
    assert current_errors == []


def test_a_stale_cancel_cannot_settle_a_newer_durable_generation(
    browser, serve, one_reader
):
    """Cancel refreshes ownership before writing the shared tombstone."""
    url = serve(JOURNEY_V1)
    stale, stale_errors = open_page(
        browser,
        url,
        context=held_stale(one_reader),
        init_script="""addEventListener('storage', event => {
          if (event.key === 'lf-draft:edit:draft-ops')
            event.stopImmediatePropagation();
        }, true);""",
    )
    current, current_errors = open_page(browser, url, context=one_reader)
    stale_draft = stale.locator("#draft-ops")
    current_draft = current.locator("#draft-ops")
    stale_draft.locator(".lf-draft-body").dblclick()
    current_draft.locator(".lf-draft-body").dblclick()
    old = "The older edit visible in the stale tab."
    newer = "The newer edit now owned by shared storage."
    stale_draft.locator("textarea").fill(old)
    expect(current_draft.locator("textarea")).to_have_value(old)
    current_draft.locator("textarea").fill(newer)
    expect(stale_draft.locator("textarea")).to_have_value(old)
    assert stale.evaluate(STORED_DRAFT_TEXT, "edit:draft-ops") == newer

    cancel_draft(stale)
    expect(current_draft.locator("textarea")).to_have_value(newer)
    assert current.evaluate(STORED_DRAFT_TEXT, "edit:draft-ops") == newer
    stale_draft.locator(".lf-draft-body").dblclick()
    expect(stale_draft.locator("textarea")).to_have_value(newer)
    assert stale_errors == []
    assert current_errors == []


def test_poll_settlement_cannot_tombstone_a_newer_durable_generation(
    browser, serve, one_reader
):
    """Log reconciliation settles only the generation still shared by storage."""
    url = serve(SEATED_QUESTION_PAGE)
    # The hold costs the most here, where the poll released at the end is the subject
    # rather than an interruption: an earlier poll reconciling this tab onto the newer
    # generation leaves settlement nothing older to be tempted by, so the assertions
    # below would pass while asking nothing rather than fail.
    stale_held = held_stale(one_reader)
    stale, stale_errors = open_page(
        browser,
        url,
        context=stale_held,
        init_script="""addEventListener('storage', event => {
          if (event.key === 'lf-draft:say:jobs') event.stopImmediatePropagation();
        }, true);""",
    )
    current, current_errors = open_page(browser, url, context=one_reader)
    stale_say = stale.locator("#jobs > .lf-conversation > .lf-say")
    current_say = current.locator("#jobs > .lf-conversation > .lf-say")
    old = "The accepted generation cached by the stale tab."
    newer = "The newer generation shared before settlement arrived."
    stale_say.locator("textarea").fill(old)
    expect(current_say.locator("textarea")).to_have_value(old)
    old_attempt = stale.evaluate(
        "() => JSON.parse(localStorage.getItem('lf-draft:say:jobs')).attempt"
    )
    current_say.locator("textarea").fill(newer)
    expect(stale_say.locator("textarea")).to_have_value(old)

    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": old,
            "attempt": old_attempt,
        },
    )
    # Settlement reconciles before it claims, so this poll adopts the newer generation
    # and leaves it standing. `held_stale`'s refusal is lifted here rather than earlier,
    # with the older attempt in the log and the older generation still cached, which is
    # the only arrangement that asks anything.
    stale_held.restore()
    told(stale)
    assert current.evaluate(STORED_DRAFT_TEXT, "say:jobs") == newer
    expect(stale_say.locator("textarea")).to_have_value(newer)
    expect(current_say.locator("textarea")).to_have_value(newer)
    assert stale_errors == []
    assert current_errors == []


def test_a_read_failure_cannot_make_a_successfully_written_draft_unsendable(
    browser, serve
):
    """The document cache owns its generation even when getItem later refuses it."""
    page, errors = open_page(
        browser,
        serve(SEATED_QUESTION_PAGE),
        init_script="""Storage.prototype.getItem = function () {
          throw new DOMException('blocked', 'SecurityError');
        };""",
    )
    raw = "A live value remains sendable when storage reads fail."
    say = page.locator("#jobs > .lf-conversation > .lf-say")
    say.locator("textarea").fill(raw)
    say.get_by_role("button", name="Send", exact=True).click()
    _until(page, lambda t: t.sends == 1, "sent the cached draft")
    round_trip(page)
    roots = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]
    assert errors == []
    page.close()


def test_a_remove_failure_cannot_resurrect_an_accepted_draft(
    browser, serve, one_reader
):
    """Settlement is a record and a log fact; draft cleanup never calls removeItem."""
    url = serve(SEATED_QUESTION_PAGE)
    first, first_errors = open_page(
        browser,
        url,
        context=one_reader,
        init_script="""Storage.prototype.removeItem = function () {
          throw new DOMException('blocked', 'SecurityError');
        };""",
    )
    raw = "A sent draft must not return."
    say = first.locator("#jobs > .lf-conversation > .lf-say")
    say.locator("textarea").fill(raw)
    say.get_by_role("button", name="Send", exact=True).click()
    round_trip(first)
    first.wait_for_function(STORED_DRAFT_SETTLED, arg="say:jobs")

    again, again_errors = open_page(browser, url, context=one_reader)
    # The composer is still standing — a seat that can hold keeps it — so the claim is
    # about what it opens with: a settled draft is words the next tab must not be handed.
    expect(again.locator("#jobs > .lf-conversation > .lf-say textarea")).to_have_value(
        ""
    )
    roots = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "comment"
    ]
    assert [event["text"] for event in roots] == [raw]
    assert first_errors == []
    assert again_errors == []


def test_an_intentional_later_identical_reply_gets_a_fresh_attempt(browser, serve):
    """Identity follows the edit generation, never content or a time window."""
    url = serve(SEATED_QUESTION_PAGE)
    root = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "anchor": {"section": "jobs"},
            "text": "Repeat the confirmation if it remains true.",
        },
    )
    page, errors = open_page(browser, url)
    thread = page.locator(f'#jobs .lf-conversation-thread[data-thread="{root["id"]}"]')
    text = "Still true."
    for _ in range(2):
        thread.locator("textarea").fill(text)
        thread.get_by_role("button", name="Send", exact=True).click()
        round_trip(page)
        expect(thread.locator("textarea")).to_have_value("")

    replies = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "reply"
    ]
    assert [event["text"] for event in replies] == [text, text]
    assert len({event["attempt"] for event in replies}) == 2
    assert errors == []
    page.close()


def test_an_unsent_draft_outlives_the_tab_it_was_typed_in(browser, serve, one_reader):
    """The one gesture the tab-local store lost a draft to, and it is the ordinary one:
    every round's reply hands the URL over again, so a page's tabs accumulate and the
    one holding a half-written sentence is as likely to be shut as any other."""
    url = serve(LONG_PAGE)
    page, errors = open_page(browser, url, context=one_reader)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    typed = "Half a thought, and then the tab went."
    page.locator(".lf-general textarea").fill(typed)
    assert errors == []
    page.close()

    again, again_errors = open_page(browser, url, context=one_reader)
    expect(again.locator(".lf-general textarea")).to_have_value(typed)
    assert again_errors == []


def test_a_draft_the_chrome_stands_down_says_so_and_keeps_an_address(browser, serve):
    """A press on the banner takes the composer off screen and keeps the words, and for
    a long time that was the whole of it: the bar went, the mark went, no notice and no
    dialog said anything, and the only way back was returning to that version and
    reselecting that exact passage. Words a reader cannot find again are words they have
    lost, whatever localStorage still holds.

    So the moment says what became of them and names the address that answers — and the
    address is offered only while there is a draft standing to go to, which is the half
    that keeps the sentence honest."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    kept = "Half a sentence, and then the banner."

    # Nothing written, nothing to return to: the sequence does not offer the destination.
    page.keyboard.press("g")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("Threads panel")
    assert "your draft" not in shortcut_bar_text(page)
    page.keyboard.press("Escape")

    compose(page, "#p3", kept)
    assert pending_text(page), "the open box left its own passage unmarked"

    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-composer")).to_be_hidden()
    assert pending_text(page) == "", "a box off screen left its passage marked"
    notice = page.locator(".lf-notice")
    expect(notice).to_have_class(re.compile(r"\bshow\b"))
    assert notice.inner_text() == "Draft kept — g D returns to it"

    page.keyboard.press("g")
    assert "your draft" in shortcut_bar_text(page)
    page.keyboard.press("Shift+d")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_be_focused()
    expect(page.locator(".lf-fab-input")).to_have_value(kept)
    assert pending_text(page), "the box came back on nothing"
    assert errors == []
    page.close()


def test_a_pasted_image_is_a_whole_draft_and_leaves_with_the_send_that_took_it(
    browser, serve
):
    """An image and no words is a draft, and the textarea is the one place it does not
    show: the box keeps the Markdown and the shelf shows the thumbnail. So a reading
    that asks the textarea whether anything is in here answers "empty" about a box the
    reader can see holds a picture, and the two directions fail in opposite ways — the
    kept notice never appears for a picture put away, and it appears for a picture that
    has just been sent, over a box with nothing left in it.

    Both directions here, and the box the reader opens next, because a shelf that
    outlived its send is an image that rides into the next passage's draft."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    image_markdown = "![Pasted image](/media/051bee487bfb5d13.png)"
    compose(page, "#p3")
    pixels = (EXAMPLE_MEDIA / "051bee487bfb5d13.png").read_bytes()
    with page.expect_response(lambda response: response.url.endswith("/api/media")):
        page.locator(".lf-fab-input").evaluate(
            """(textarea, encoded) => {
              const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
              const transfer = new DataTransfer();
              transfer.items.add(new File([bytes], 'pasted.png', {type: 'image/png'}));
              textarea.dispatchEvent(new ClipboardEvent('paste', {
                bubbles: true,
                cancelable: true,
                clipboardData: transfer,
              }));
            }""",
            base64.b64encode(pixels).decode(),
        )
    shelf = page.locator(".lf-composer .lf-composer-media")
    expect(shelf.locator("img")).to_be_visible()

    # Put away: the picture is words enough to keep, and to be told about.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-composer")).to_be_hidden()
    notice = page.locator(".lf-notice")
    assert notice.inner_text() == "Draft kept — g D returns to it"
    page.keyboard.press("g")
    assert "your draft" in shortcut_bar_text(page)
    page.keyboard.press("Shift+d")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-fab-input")).to_have_value("")
    expect(shelf.locator("img")).to_be_visible()

    # Sent: the box is empty because the send emptied it, and says nothing about drafts.
    # Every word the status line says through the send, not the one left standing at the
    # end of it: a wrong sentence four seconds long is one the reader reads.
    page.evaluate("""() => {
      const el = document.querySelector('.lf-notice');
      window.__said = [];
      new MutationObserver(() => window.__said.push(el.textContent)).observe(el, {
        childList: true,
        characterData: true,
        subtree: true,
      });
    }""")
    with sending(page, "the image-only comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator(".lf-composer")).to_be_hidden()
    assert events_model.read_events(serve.page_dir)[-1]["text"] == image_markdown
    assert page.evaluate("window.__said") == []

    # And the next passage's box opens on nothing, shelf included.
    typed = "A second comment, and no image with it."
    compose(page, "#p5", typed)
    expect(shelf).to_be_hidden()
    with sending(page, "the second comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    assert events_model.read_events(serve.page_dir)[-1]["text"] == typed
    assert errors == []
    page.close()


def test_a_held_selection_comment_preserves_a_newer_exact_draft(held_events, serve):
    """A selection send owns one composer generation, not the passage.

    The send takes its own words with it — they stand in the thread it drew before the
    log has answered — and the composer opened again on that passage holds a generation
    of its own, which the older answer must not settle."""
    browser, held = held_events
    page, errors = open_page(browser, serve(LONG_PAGE))
    old = "The selected passage needs this first comment."
    newer = "  A newer selection comment remains in the composer.  "
    compose(page, "#p3", old)
    page.keyboard.press("ControlOrMeta+Enter")
    holding(page, held, 1, "the selection comment")
    expect(page.locator("[data-attempt]").first).to_contain_text(old)

    compose(page, "#p3", newer)
    box = page.locator(".lf-composer textarea")
    held.pop(0).continue_()
    page.unroute("**/api/event")
    round_trip(page)
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(box).to_have_value(newer)
    comments = [
        event for event in sent_events(serve.page_dir) if event["kind"] == "comment"
    ]
    assert [event["text"] for event in comments] == [old]
    assert comments[0]["attempt"]
    assert errors == []
    page.close()


def test_two_passages_hold_two_composer_drafts(browser, serve, one_reader):
    """One key for the composer was enough while a draft died with its tab; shared, it
    is a draft on one passage overwriting the words being typed on another. The key is
    the anchor, so the two coexist — and the record says when it was touched, which is
    what a tab arriving to both of them reopens on."""
    url = serve(LONG_PAGE)
    first, first_errors = open_page(browser, url, context=one_reader)
    second, second_errors = open_page(browser, url, context=one_reader)

    early = "This paragraph buries the point."
    late = "And this one repeats it."
    compose(first, "#p3", early)
    compose(second, "#p9", late)
    expect(first.locator(".lf-composer textarea")).to_have_value(early)
    expect(second.locator(".lf-composer textarea")).to_have_value(late)

    # A tab arriving now: one composer, on the passage touched last.
    third, third_errors = open_page(browser, url, context=one_reader)
    expect(third.locator(".lf-composer textarea")).to_have_value(late)
    assert first_errors == []
    assert second_errors == []
    assert third_errors == []


def test_a_composer_on_one_passage_is_one_box_in_every_tab(browser, serve, one_reader):
    """The composer is a box and a piece of chrome at once, so a second tab owes it
    more than the words. An emptied box is a box the reader is still holding open and
    must stay up; a settled one has nothing left to be open about and goes down, or the
    other tab is left offering to send words the log already carries.

    The mirrored value is read for its height as well, because a box that took another
    tab's words and did not grow to them is one whose text is out of sight — the shape
    of bug a script sizing the box on `input` alone would reintroduce."""
    url = serve(LONG_PAGE)
    first, first_errors = open_page(browser, url, context=one_reader)
    second, second_errors = open_page(browser, url, context=one_reader)

    opened = "This paragraph buries the point."
    compose(first, "#p3", opened)
    compose(second, "#p3")
    expect(second.locator(".lf-composer textarea")).to_have_value(opened)
    height = "ta => Math.round(ta.getBoundingClientRect().height)"
    compact_height = second.locator(".lf-composer textarea").evaluate(height)

    grown = opened + "\n\n" + "And the one after it says the same thing again. " * 4
    first.locator(".lf-composer textarea").fill(grown)
    expect(second.locator(".lf-composer textarea")).to_have_value(grown)
    assert first.locator(".lf-composer textarea").evaluate(height) > compact_height
    assert second.locator(".lf-composer textarea").evaluate(height) == first.locator(
        ".lf-composer textarea"
    ).evaluate(height), (
        "a box grown from another tab's keystrokes must be laid out like a typed one"
    )

    # Emptying is an edit and not a settlement: the box stays up, holding nothing.
    first.locator(".lf-composer textarea").fill("")
    expect(second.locator(".lf-composer textarea")).to_have_value("")
    expect(second.locator(".lf-composer")).to_be_visible()
    assert second.locator(".lf-composer textarea").evaluate(height) == compact_height

    sent = "The point is buried, and the paragraph after it repeats it."
    first.locator(".lf-composer textarea").fill(sent)
    first.keyboard.press("ControlOrMeta+Enter")
    round_trip(first)
    expect(second.locator(".lf-composer")).to_be_hidden()
    said = [
        e["text"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "comment"
    ]
    assert said == [sent], "one box, and so one comment however many tabs showed it"
    assert first_errors == []
    assert second_errors == []


def test_text_alignment_is_lossless_and_keeps_a_shared_spine(browser, serve):
    """The draft renderer is allowed to choose where an ambiguous repeated word
    aligns, but never to lose or invent a character. The two projections are the
    contract: same+delete is the old text, same+insert the new one. Unicode,
    whitespace and repetition are where a character or regex diff quietly breaks.

    Both granularities, because the unit is the caller's and the contract is not: a
    draft's history aligns by word, while an inline version comparison starts with
    sentences and refines a local edit by word. Neither may drop or invent a character."""
    page, errors = open_page(browser, serve(JOURNEY_V1))
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
          const {alignInlineText, alignText, sentenceUnits} =
            await import('/runtime/text-alignment.js');
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
        for (before, after), runs in zip(cases, walked):
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
    assert [run["kind"] for run in aligned[-1]] == ["same", "delete", "insert", "same"]

    local = page.evaluate(
        """async () => {
          const {alignInlineText} = await import('/runtime/text-alignment.js');
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
    assert errors == []
    page.close()


def test_a_draft_explains_its_change_and_restores_history_as_an_edit(browser, serve):
    """One disclosure answers both deferred draft decisions. It compares this version's
    authored body with the standing body, retains every absolute edit in log order,
    and walks back by posting another ordinary edit. A second tab proves restore is
    durable replay rather than local history state; copy mode proves the generated
    controls do not survive without their handlers."""
    page, errors = open_page(browser, serve(JOURNEY_V1))
    draft = page.locator("#draft-ops")
    edits = [
        "Run the migration before deploying. It takes one minute.",
        "Run the migration after the backup. It takes two minutes.",
    ]
    for index, text in enumerate(edits, 1):
        draft.locator(".lf-draft-body").dblclick()
        draft.locator("textarea").fill(text)
        draft_controls(page).get_by_role("button", name="Save").click()
        round_trip(page)  # the history is drawn from the log, not the box
        expect(draft.locator(".lf-draft-history > summary")).to_have_text(
            f"Changes · {index} {'edit' if index == 1 else 'edits'}"
        )

    # The disclosure is the platform's to work and the register says so, naming the
    # press where the reader is standing on it and reading which way it goes off the
    # state they can already see.
    history = draft.locator(".lf-draft-history > summary")
    history.focus()
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("show the history")
    history.click()
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("hide the history")

    current_deleted = "".join(draft.locator(".lf-draft-current del").all_inner_texts())
    current_inserted = "".join(draft.locator(".lf-draft-current ins").all_inner_texts())
    assert "before" in current_deleted and "deploying" in current_deleted
    assert "afterthebackup" in re.sub(r"\s+", "", current_inserted)
    labels = draft.locator(".lf-draft-revision-head strong").all_inner_texts()
    assert labels == ["Version text", "Edit 1 · v1", "Edit 2 · v1"]
    # Adjacent recorded edits are aligned too, rather than rendered as two unrelated
    # snapshots. The first has no knowable predecessor on a later pinned version.
    second_delta = draft.locator(".lf-draft-revisions > li").nth(2)
    second_deleted = "".join(second_delta.locator("del").all_inner_texts())
    second_inserted = "".join(second_delta.locator("ins").all_inner_texts())
    assert "before" in second_deleted and "deploying" in second_deleted
    assert "afterthebackup" in re.sub(r"\s+", "", second_inserted)

    page.evaluate("document.documentElement.classList.add('lf-copy')")
    expect(draft.locator(".lf-draft-history")).not_to_be_visible()
    expect(draft.locator(".lf-draft-controls")).not_to_be_visible()
    expect(draft.locator(".lf-draft-body")).to_be_visible()
    page.evaluate("document.documentElement.classList.remove('lf-copy')")

    draft.get_by_role("button", name="Restore edit 1 · v1").focus()
    page.keyboard.press("Enter")
    round_trip(page)
    expect(draft.locator(".lf-draft-body")).to_have_text(edits[0])
    expect(draft.locator(".lf-draft-history > summary")).to_have_text(
        "Changes · 3 edits"
    )
    expect(draft.locator(".lf-draft-history > summary")).to_be_focused()
    expect(draft).to_have_attribute("data-lf-reader-override", "1")

    events = [
        json.loads(line)
        for line in (serve.page_dir / "events.jsonl").read_text().splitlines()
        if '"kind": "action"' in line
    ]
    assert [event["detail"]["text"] for event in events] == [
        edits[0],
        edits[1],
        edits[0],
    ]
    assert [event["action"] for event in events] == ["edit", "edit", "edit"]

    sequence = page.evaluate(
        """async () => {
          const {actionSequence} = await import('/runtime/widget-api.js');
          const widget = document.getElementById('draft-ops');
          const first = actionSequence(widget, 'edit');
          first[0].detail.text = 'A widget must not mutate the runtime log.';
          return actionSequence(widget, 'edit')
            .map(event => [event.seq, event.detail.text]);
        }"""
    )
    assert [text for _, text in sequence] == [edits[0], edits[1], edits[0]]
    assert [seq for seq, _ in sequence] == sorted(seq for seq, _ in sequence)

    other, other_errors = open_page(browser, page.url)
    expect(other.locator("#draft-ops .lf-draft-body")).to_have_text(edits[0])
    expect(other.locator("#draft-ops .lf-draft-history > summary")).to_have_text(
        "Changes · 3 edits"
    )
    assert errors == []
    assert other_errors == []
    other.close()
    page.close()


def test_action_history_is_bounded_by_the_pinned_version(browser, serve):
    """A historical page cannot narrate an edit that had not happened yet. The
    helper owns the same version boundary replay does, so every future widget that
    consumes a sequence gets this right without copying the filter."""
    url = serve(JOURNEY_V1)
    d = serve.page_dir
    for version, text in ((1, "First recorded body."), (2, "Second recorded body.")):
        if version == 2:
            (d / ".fixture-versions" / "v2.html").write_text(JOURNEY_V2)
            stamp_version_file(d, 2, "v2")
        append_command(
            d,
            {
                "kind": "action",
                "author": "user",
                "revision": version,
                "widget": "draft-ops",
                "action": "edit",
                "detail": {"text": text},
            },
        )

    old, old_errors = open_page(browser, url, pin=True)
    expect(old.locator("#draft-ops .lf-draft-history > summary")).to_have_text(
        "Changes · 1 edit"
    )
    old_sequence = old.evaluate(
        """async () => (await import('/runtime/widget-api.js'))
          .actionSequence(document.getElementById('draft-ops'), 'edit')
          .map(event => event.revision)"""
    )
    assert old_sequence == [1]

    latest, latest_errors = open_page(
        browser, url.replace("v1.html", "v2.html"), pin=True
    )
    expect(latest.locator("#draft-ops .lf-draft-history > summary")).to_have_text(
        "Changes · 2 edits"
    )
    latest_sequence = latest.evaluate(
        """async () => (await import('/runtime/widget-api.js'))
          .actionSequence(document.getElementById('draft-ops'), 'edit')
          .map(event => event.revision)"""
    )
    assert latest_sequence == [1, 2]
    assert old_errors == []
    assert latest_errors == []
    old.close()
    latest.close()


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
            "detail": {"card": "card-x", "to": "col-done", "index": 0},
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
            "detail": {"text": DRAFT_EDITED},
        },
    )
    # The highest user event reached context, so everything so far is ours to answer.
    session_model.cmd_ack(d, events_model.read_events(d)[-1]["seq"])
    # And the agent answers with a version that carries neither — the page generator
    # emitting its own idea of the board and the draft, as one did for five
    # versions running.
    (d / ".fixture-versions" / "v2.html").write_text(JOURNEY_V2)
    stamp_version_file(d, 2, "v2")

    page, errors = open_page(browser, url.replace("v1.html", "v2.html"))
    page.wait_for_function(
        "t => document.querySelector('#draft-ops .lf-draft-body').textContent === t",
        arg=DRAFT_EDITED,
    )
    expect(page.locator("#col-done #card-x")).to_have_count(1)
    assert errors == []
    page.close()


def test_a_comment_written_on_an_edited_draft_lands_on_their_words(browser, serve):
    """`leaf comment` reads the mapped revision plus the log; the user's tab reads
    the DOM replay builds from the same two. An edited draft is where those readings
    used to drift — the file holds words the page stopped showing — so write the anchor
    blind, on the user's own words, and prove the page paints it. The words the edit
    replaced are refused at the CLI, naming the edit, because posted they would detach
    in front of the user."""
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
            "detail": {"text": DRAFT_EDITED},
        },
    )
    refused = CliRunner().invoke(
        cli_model.cli,
        ["comment", str(d), "--quote", "It is online.", "--text", "x"],
    )
    assert refused.exit_code != 0 and "rewrote § draft-ops" in refused.output
    written = CliRunner().invoke(
        cli_model.cli,
        [
            "comment",
            str(d),
            "--quote",
            "It takes about a minute.",
            "--text",
            "Measured where?",
        ],
        catch_exceptions=False,
    )
    assert written.exit_code == 0, written.output

    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    thread = page.locator(".lf-thread .lf-quote").first
    expect(thread).not_to_have_class(re.compile(r"\bdetached\b"))
    assert painted(page, "lf-mark") == "It takes about a minute."
    assert errors == []
    page.close()


def test_registered_control_keys_activate_once(browser, serve):
    """A native draft button activates without a Leaf key binding. The selectable option
    mark is the explicit exception and owns its Space row.

    Activation happens once per press however long the key is held. A keydown listener
    hears repeats, and a mark that toggles per repeat posts a `choose` for each one. Repeats
    are dispatched rather than driven because no automation holds a key down; the browser
    delivers this event with `repeat` set."""
    page, errors = open_page(browser, serve(KEYS_PAGE))

    pencil = draft_controls(page).locator(".lf-draft-pencil")
    assert pencil.evaluate("el => el.localName") == "button"
    expect(pencil).to_have_attribute("type", "button")
    pencil.focus()
    page.keyboard.press("Enter")
    editor = page.locator("#draft-ops textarea")
    expect(editor).to_be_focused()
    focus_paint = page.locator("#draft-ops").evaluate(
        """host => {
          const editor = host.querySelector('textarea');
          const hs = getComputedStyle(host), es = getComputedStyle(editor);
          return {
            host: {outline: hs.outlineStyle, width: parseFloat(hs.outlineWidth)},
            editor: {outline: es.outlineStyle, shadow: es.boxShadow,
                     ring: es.getPropertyValue('--lf-here-ring').trim()},
          };
        }"""
    )
    assert focus_paint["host"]["outline"] != "none"
    assert focus_paint["host"]["width"] >= 2
    assert focus_paint["editor"] == {
        "outline": "none",
        "shadow": "none",
        "ring": "none",
    }, "the draft's one editing surface acquired a second focus box"
    page.emulate_media(forced_colors="active")
    forced = page.locator("#draft-ops").evaluate(
        """host => {
          const editor = host.querySelector('textarea');
          return {
            host: getComputedStyle(host).outlineStyle,
            editor: getComputedStyle(editor).outlineStyle,
          };
        }"""
    )
    assert forced == {"host": "solid", "editor": "none"}
    page.emulate_media(forced_colors="none")
    page.keyboard.press("Escape")

    mark = page.locator("#opts .lf-pick").first
    mark.focus()
    page.keyboard.press(" ")
    expect(page.locator("#opts > lf-option[chosen]")).to_have_count(1)
    chosen = page.locator("#opts > lf-option[chosen]").get_attribute("id")
    mark.evaluate("""el => {
        for (let i = 0; i < 5; i++)
            el.dispatchEvent(new KeyboardEvent('keydown',
                {key: ' ', repeat: true, bubbles: true, cancelable: true}));
    }""")
    expect(page.locator(f"#{chosen}[chosen]")).to_have_count(1)
    # The mark paints its own press before the post answers, so the DOM leads the log:
    # read the file straight after and the first press's event may not be in it yet,
    # which reads exactly like a press that sent nothing. A press that sent nothing
    # satisfies this too, which is what makes it the right wait for both assertions —
    # the repeats below must add none of their own.
    round_trip(page)
    sent = [
        json.loads(line)
        for line in (serve.page_dir / "events.jsonl").read_text().splitlines()
    ]
    assert [e for e in sent if e.get("action") == "choose"] != [], (
        "the first press sent nothing, so the repeats below had nothing to duplicate"
    )
    assert len([e for e in sent if e.get("action") == "choose"]) == 1, (
        "a held key sent one decision per repeat"
    )
    assert errors == []
    page.close()


def test_global_shortcuts_leave_other_browser_navigation_keys_alone(browser, serve):
    """The document-level dispatcher owns a few character key shortcuts, not the
    keyboard. Space, arrows, Home/End, and PageUp/PageDown must still reach the browser
    when focus is in the authored page
    rather than a widget control.

    Observe `defaultPrevented` on real key events instead of asserting that Chrome
    happened to scroll: scrolling depends on viewport and focus geometry, while
    canceling the event is the runtime decision under test. `?` is the positive
    control proving this observer sees a key the dispatcher intentionally consumes."""
    page, errors = open_page(browser, serve(KEYS_PAGE))
    keys = [
        " ",
        "ArrowUp",
        "ArrowDown",
        "ArrowLeft",
        "ArrowRight",
        "Home",
        "End",
        "PageUp",
        "PageDown",
        "?",
    ]
    page.evaluate(
        """keys => {
          const pageContent = document.querySelector("main");
          pageContent.tabIndex = -1;
          pageContent.focus();
          window.lfObservedKeys = {};
          document.addEventListener("keydown", event => {
            if (keys.includes(event.key))
              window.lfObservedKeys[event.key] = event.defaultPrevented;
          });
        }""",
        keys,
    )
    for key in keys:
        page.keyboard.press(key)

    observed = page.evaluate("() => window.lfObservedKeys")
    assert observed.pop("?") is True, (
        "the positive-control shortcut was not consumed, so the probe did not "
        "observe the runtime dispatcher"
    )
    assert observed == dict.fromkeys(keys[:-1], False)
    assert errors == []
    page.close()


def test_the_browser_pages_the_document_with_space(browser, serve):
    """Space and Shift+Space are ordinary browser paging keys on authored content.

    Leaf does not prescribe a distance or animation. The browser chooses both; the
    contract here is simply that the document moves down and then back up without the
    runtime canceling either key."""
    page, errors = open_page(browser, serve(SMOOTH_LONG_PAGE))
    page.locator("body").focus()

    def press_and_settle(key):
        page.evaluate("""() => {
          window.__lfScrollEnded = false;
          addEventListener('scrollend', () => { window.__lfScrollEnded = true; },
                           {once: true});
        }""")
        page.keyboard.press(key)
        page.wait_for_function("() => window.__lfScrollEnded")
        return page.evaluate("() => document.scrollingElement.scrollTop")

    down = press_and_settle("Space")
    assert down > 0, "the browser did not page the document down"
    up = press_and_settle("Shift+Space")
    assert up < down, "the browser did not page the document back up"
    assert errors == []
    page.close()


@pytest.mark.parametrize(("down", "up"), [("d", "u"), ("j", "k")])
def test_the_reading_keys_accumulate_and_reverse(browser, serve, down, up):
    """d/u move 60% of the visible page; j/k take small steps through the same glide.
    The page sets scroll-behavior: smooth on the box, as an authored page may —
    a step whose writes ride that rule instead of stating `instant` never lands.

    Every phase waits on its destination, never on scrollend or a timer: the glide
    writes a frame at a time and Chrome answers each write with a scrollend, so
    "scrolling ended" is a fact about a frame, while the destination is the one
    position a glide approaching it never passes through early. A wrong step then
    reads as the wrong number, which says what happened.

    The second press follows the first with no wait between them, landing inside the
    first glide, so presses have to add up from the goal rather than from wherever
    the glide has got to. Taking the box mid-glide — programmatically, because the
    cancel reads positions and any hand looks the same to it, and this one lands at
    a number the assertion can hold — must stand the step down: the next press
    measures from where the reader left the box, not from the goal it dropped, and a
    glide that ignored the taking presses on to that goal and fails both reads.
    Pressing on at the foot moves nothing and banks nothing, so u from there
    is one step back."""
    page, errors = open_page(browser, serve(SMOOTH_LONG_PAGE))
    step = (
        60
        if down == "j"
        else page.evaluate(
            "() => (document.scrollingElement.clientHeight"
            " - parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop)) * 0.6"
        )
    )
    assert page.evaluate(
        "() => document.scrollingElement.scrollHeight > document.scrollingElement.clientHeight * 3"
    ), "the page is too short for these steps to be told apart"
    # A callback's frame timestamp may predate performance.now() in the key handler.
    # Make that browser timing deterministic: a negative first fraction used to write
    # above the page, get clamped to zero, then cancel the glide as if the reader moved.
    page.evaluate(
        """down => {
      const raf = requestAnimationFrame;
      let stale = false;
      addEventListener('keydown', event => {
        if (event.key === down) stale = true;
      }, {capture: true});
      window.requestAnimationFrame = callback => {
        const firstAfterPress = stale;
        stale = false;
        return raf(now => callback(firstAfterPress ? -1 : now));
      };
    }""",
        down,
    )

    def rests_at(act, expected):
        """Position after `act`, awaited at `expected` and handed to the assertion:
        the bounded wait consumes the arrival, and the assert is what speaks when
        the step went somewhere else instead."""
        act()
        try:
            page.wait_for_function(
                "e => Math.abs(document.scrollingElement.scrollTop - e) < 1",
                arg=expected,
                timeout=5000,
            )
        except PlaywrightTimeout:
            pass
        return page.evaluate("() => document.scrollingElement.scrollTop")

    assert rests_at(lambda: page.keyboard.press(down), step) == pytest.approx(
        step, abs=1
    )

    def twice():
        page.keyboard.down(down)
        page.keyboard.down(down)  # a held key emits a repeated keydown
        page.keyboard.up(down)

    assert rests_at(twice, step * 3) == pytest.approx(step * 3, abs=1), (
        "the second press measured from the glide in flight, so the two together "
        "moved less than their full distance"
    )
    assert rests_at(lambda: page.keyboard.press(up), step * 2) == pytest.approx(
        step * 2, abs=1
    )

    def taken():
        page.keyboard.press(down)
        page.evaluate(
            "() => document.scrollingElement.scrollTo({top: 400, behavior: 'instant'})"
        )

    assert rests_at(taken, 400) == pytest.approx(400, abs=1), (
        "the glide pressed on to its goal after the reader took the box"
    )
    assert rests_at(lambda: page.keyboard.press(down), 400 + step) == pytest.approx(
        400 + step, abs=1
    ), (
        "the press after the reader took the box measured from the goal the taking "
        "had cancelled rather than from where they left it"
    )

    foot = page.evaluate(
        "() => document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight"
    )
    assert rests_at(
        lambda: page.evaluate(
            "() => document.scrollingElement.scrollTo({top: 1e9, behavior: 'instant'})"
        ),
        foot,
    ) == pytest.approx(foot, abs=1)
    for _ in range(4):
        page.keyboard.press(down)  # nothing left to move, and nothing banked either
    assert rests_at(lambda: page.keyboard.press(up), foot - step) == pytest.approx(
        foot - step, abs=1
    ), (
        "presses at the foot of the page ran the destination past it, and reversing spent "
        "itself paying that back"
    )
    assert errors == []
    page.close()


def test_the_reading_page_step_never_paints_behind_where_it_started(browser, serve):
    """The step's own frames, read at real speed from the middle of the page where the
    box clamps nothing: d may not paint the page above where the press found it. A rAF
    tick carries its frame's own start, so a press handled inside a frame already under
    way is stamped after the tick it schedules, and an ease reading that as elapsed time
    walks back out through its own start (stepReading says the rest). At the ends of the box
    that write is one the box clamps, and what the clamp does to the press is a resting
    position the test above reads; in the middle every write lands, the glide arrives
    exactly where it promised, and the reader is thrown up to most of a page the wrong
    way on the route — which no resting position can see.

    Whether a press loses that race is the platform's to say, so the window is stated
    rather than run for: a throttled CPU is a longer frame, and a longer frame is a wider
    gap between its start and the press dispatched inside it. Unfloored, this machine
    flicked on one press in ten at its own speed and on eight in ten throttled, where a
    floored clock flicks on none of either. The injection buys the record, not the wait,
    which is still the destination's."""
    page, errors = open_page(browser, serve(SMOOTH_LONG_PAGE))
    page.context.new_cdp_session(page).send(
        "Emulation.setCPUThrottlingRate", {"rate": 20}
    )
    step = page.evaluate(
        "() => (document.scrollingElement.clientHeight"
        " - parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop)) * 0.6"
    )
    start = round(step * 2)
    page.evaluate("""() => {
        window.lfFrames = [];
        const sample = () => {
            window.lfFrames.push(document.scrollingElement.scrollTop);
            requestAnimationFrame(sample);
        };
        requestAnimationFrame(sample);
    }""")
    for _ in range(5):
        page.evaluate(
            "at => document.scrollingElement.scrollTo({top: at, behavior: 'instant'})",
            start,
        )
        page.wait_for_function(
            "at => document.scrollingElement.scrollTop === at", arg=start
        )
        page.evaluate("() => (window.lfFrames = [])")
        page.keyboard.press("d")
        page.wait_for_function(
            "e => Math.abs(document.scrollingElement.scrollTop - e) < 1",
            arg=start + step,
        )
        assert min(page.evaluate("() => window.lfFrames")) >= start - 1, (
            "the step painted the page above where the press found it"
        )
    assert errors == []
    page.close()


@pytest.mark.parametrize(("down", "up"), [("d", "u"), ("j", "k")])
def test_the_reading_keys_jump_under_reduced_motion(browser, serve, down, up):
    """Both reading distances jump immediately under reduced motion."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        color_scheme="light",
        reduced_motion="reduce",
    )
    page, errors = open_page(browser, serve(SMOOTH_LONG_PAGE), context=context)
    step = (
        60
        if down == "j"
        else page.evaluate(
            "() => (document.scrollingElement.clientHeight"
            " - parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop)) * 0.6"
        )
    )
    page.keyboard.press(down)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == pytest.approx(
        step, abs=1
    ), "the step had not reached its destination when the press returned"
    page.keyboard.press(up)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == pytest.approx(
        0, abs=1
    )
    assert errors == []
    page.close()
    context.close()


def test_the_reading_page_keys_move_the_region_the_reader_is_scrolling(browser, serve):
    """Two scroll regions, so d has to pick the one the reader is looking at. Beside the
    page the panel is a column of its own and the keys are the document's. Under the
    breakpoint the sheet covers the page and the page hands scrolling over with it — one
    gesture moves one region, and while the sheet is up that region is its thread list.
    A key is no different from a wheel there: a page scrolling behind the sheet shows
    the user nothing, so the key reads as dead, and the document is somewhere else
    when the sheet closes."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=12))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    # Put the reader on the page before asking which reading region the page gesture chooses.
    page.locator("body").focus()
    assert page.evaluate(
        "() => { const t = document.querySelector('.lf-threads');"
        " return t.scrollHeight > t.clientHeight; }"
    ), "the thread list does not overflow, so it could not be seen to scroll below"

    def offsets():
        return page.evaluate(
            "() => [document.scrollingElement.scrollTop,"
            " document.querySelector('.lf-threads').scrollTop]"
        )

    def press_down():
        """Both offsets once a region answers the press — the glide's first write is
        already the answer to which region moved, and movement is the fact waited on
        because movement is the question. Scrollend was the wait here while a press
        could die outright, which read as the platform withholding the event; it
        withholds nothing, answering the step's frame-at-a-time writes seven times to
        the press on Linux, and a press that moves no region states neither fact.
        Waiting on whichever region speaks makes the wrong one answering two numbers
        to compare rather than half a minute of silence and a timeout."""
        was = offsets()
        page.keyboard.press("d")
        page.wait_for_function(
            "w => { const t = document.querySelector('.lf-threads');"
            " return document.scrollingElement.scrollTop !== w[0] || t.scrollTop !== w[1]; }",
            arg=was,
        )
        return was, offsets()

    (page_was, threads_was), (page_now, threads_now) = press_down()
    assert threads_now == threads_was, "the panel took a key aimed at the document"
    assert page_now > page_was, "the document did not move for a key of its own"
    page.evaluate(
        "() => { window.__lfScroll = document.scrollingElement.scrollTop;"
        " window.__lfScrollSince = performance.now(); }"
    )
    page.wait_for_function(SCROLL_SETTLED, arg=50)

    resized(page, 500, 600)
    panel_settled(page)
    (page_was, threads_was), (page_now, threads_now) = press_down()
    assert page_now == page_was, (
        "the page moved behind the covering sheet, where the user cannot see it"
    )
    assert threads_now > threads_was, "the sheet did not move for the key it now owns"
    assert errors == []
    page.close()


def test_the_reading_page_keys_follow_the_reader_into_the_panel(browser, serve):
    """Which region the keys move is where the reader is standing, and covering is only
    one of the two ways they come to be standing in the list. Beside the page — the wide
    window, where the panel takes a strip of its own — a reader working down a long
    conversation presses d and the page behind them steps instead, which is the same
    nothing the covering case was written to prevent: the region they are reading does
    not move, and the document is somewhere else when they look back at it.

    One factor separates the two halves here. The window, the layout, the panel and the
    list are the same at both presses; only where the focus stands changes. So the first
    press is the control that says the layout is beside — the reader stands on the page,
    outside the panel, and the document is theirs to step — and the second is the subject.
    The address sequence then supplies the neighboring
    contrast: focus changes which region d/u page through, but `g g` still names the
    document's edge while both regions have somewhere observable to move."""
    page, errors = open_page(browser, serve(LONG_PAGE, comments=12))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    page.locator("body").focus()
    assert page.evaluate(
        "() => { const t = document.querySelector('.lf-threads');"
        " return t.scrollHeight > t.clientHeight; }"
    ), "the thread list does not overflow, so it could not be seen to scroll below"

    def offsets():
        return page.evaluate(
            "() => [document.scrollingElement.scrollTop,"
            " document.querySelector('.lf-threads').scrollTop]"
        )

    # The control, and the wait that makes the subject's baseline a resting one: the
    # document's own step is a glide, and the position it is going to is the one place
    # it does not pass through early (the reading-page test says the rest).
    step = page.evaluate(
        "() => (document.scrollingElement.clientHeight"
        " - parseFloat(getComputedStyle(document.scrollingElement).scrollPaddingTop)) * 0.6"
    )
    page_was, threads_was = offsets()
    page.keyboard.press("d")
    page.wait_for_function(
        "e => Math.abs(document.scrollingElement.scrollTop - e) < 1",
        arg=step,
        timeout=5000,
    )
    page_now, threads_now = offsets()
    assert page_now > page_was, (
        "the document did not move for a key pressed from outside the panel, so the "
        "panel is not beside the page here and the case below is not the one named"
    )
    assert threads_now == threads_was, "the panel took a key aimed at the document"

    # Into the panel, standing on its list rather than in a box — `g T`'s landing,
    # which travels nothing, so the baseline below is the one the control left. The
    # address toggles the panel it names, so from the standing one the first completion
    # closes it and the second is the arrival.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    panel_settled(page, open=False)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()

    page_was, threads_was = offsets()
    page.keyboard.press("d")
    page.wait_for_function(
        "w => { const t = document.querySelector('.lf-threads');"
        " return document.scrollingElement.scrollTop !== w[0] || t.scrollTop !== w[1]; }",
        arg=[page_was, threads_was],
    )
    thread_step = page.locator(".lf-threads").evaluate(
        "t => (t.clientHeight - parseFloat(getComputedStyle(t).scrollPaddingTop)) * 0.6"
    )
    page.wait_for_function(
        "w => { const t = document.querySelector('.lf-threads');"
        " return Math.abs(t.scrollTop - w[0]) < 1"
        " || Math.abs(document.scrollingElement.scrollTop - w[1]) >= 1; }",
        arg=[thread_step, page_was],
        timeout=5000,
    )
    page_now, threads_now = offsets()
    assert threads_now > threads_was, (
        "the list the reader is standing in did not move for the key they pressed"
    )
    assert page_now == pytest.approx(page_was, abs=1), (
        "the page stepped behind a reader who was working down the comment list"
    )

    # Both regions now stand away from their top edge. A correct g g returns the page;
    # the shared-scroller regression returns the panel instead. Wait for either answer so
    # the failure reports both offsets rather than timing out while expecting only one.
    assert page_now > 0 and threads_now > 0
    page.keyboard.press("g")
    page.keyboard.press("g")
    page.wait_for_function(
        "() => { const t = document.querySelector('.lf-threads');"
        " return document.scrollingElement.scrollTop < 1 || t.scrollTop < 1; }",
        timeout=5000,
    )
    edge_page, edge_threads = offsets()
    assert edge_page == pytest.approx(0, abs=1), (
        f"g g left the page at {edge_page} and moved the panel to {edge_threads}"
    )
    assert edge_threads == pytest.approx(threads_now, abs=1), (
        f"g g moved the panel from {threads_now} to {edge_threads}"
    )
    assert errors == []
    page.close()


def test_the_page_has_one_door_to_a_comparison(browser, serve):
    """`=` marked what changed since the previous version from anywhere on the page, and
    the case for it was that it named no version — "since the last one I saw" is a
    question a reader has without opening anything. Naming no version is also naming
    nothing to check, and the two are not the same question: on a page that ships a
    version whenever the work moves, a reader back after a week got v(n-1) and no way to
    see that they had. So the door is the menu, where every base says which one it is.

    Pressed rather than read off the table, on both sides: a key bound to nothing looks
    exactly like one that works in the shortcut reference dialog, which is how the removal would go
    unnoticed here and the marks would go unnoticed on the page."""
    url = serve(LONG_PAGE)
    _publish(
        serve.page_dir,
        2,
        LONG_PAGE.replace("Paragraph 3.", "Paragraph three."),
        "reworded a paragraph",
    )
    page, errors = open_page(browser, url.replace("v1.html", "v2.html"))
    line = page.locator(".lf-shortcut-bar")
    # The door is a go-to destination rather than a bare letter, so the line names it
    # once the sequence is armed. The word that must not be anywhere is read behind that
    # arrival, so the absence is taken off a line the press has already repainted.
    page.keyboard.press("g")
    expect(line).to_contain_text("versions")
    expect(line).not_to_contain_text("mark changes")
    page.keyboard.press("Escape")
    page.keyboard.press("=")
    expect(page.locator(".lf-version-menu")).to_be_hidden()
    expect(page.locator(".lf-ins-block")).to_have_count(0)
    page.keyboard.press("g")
    expect(line).to_contain_text("versions")
    page.keyboard.press("Shift+v")
    expect(page.locator(".lf-version-menu")).to_be_visible()
    page.keyboard.press("Escape")

    # The door, and it marks the same passage the key used to.
    compare_with(page)
    expect(page.locator("#p3")).to_have_class(re.compile(r"lf-ins-block"))
    assert errors == []
    page.close()


def test_the_draft_box_is_its_own_door(browser, serve):
    """A draft is the one block on a page whose whole purpose is that the reader rewrites
    it, and until now the only thing that said so was a pencil in the margin 45px away.
    The block itself ignored a press. The gesture that did open it in place was a
    double-click, which is a thing you have to already know.

    So the box is the door, and the caret lands where the press did. Which is a door that
    has to be opened carefully, because the same words are the page's words: a reader
    drawing across them to quote them ends that drag with a mouseup inside the box, and
    opening on it would throw the selection away at the moment it was finished. That is
    the question `reachedForWords` answers for every other press on the page's own words,
    asked here rather than answered again. The drag runs through the harness's own
    `hold_selection`, which floors the press - a fractional start point loses the
    selection outright, and an empty one would read exactly like the door swallowing it -
    and the words are read while the drag is still held, because the runtime re-seats the
    selection on a timer after the release and a read in that gap comes back empty.

    And the door is exactly the box - not the chrome inside it. `offer` writes its marker
    on everything a widget builds, controls row and edit box included, and only names a
    kind for the things to press; the guard reads that, so a press on the row does not
    reopen the editor and the row does not wear a hand it has no use for."""
    page, errors = open_page(browser, serve(JOURNEY_V1))
    draft = page.locator("#draft-ops")
    body = draft.locator(".lf-draft-body")
    expect(body).to_have_text(DRAFT_TEXT)

    # A drag across the words takes the words. Read as the selection the reader is left
    # holding, which is the thing the door would have destroyed.
    box = body.bounding_box()
    line = box["y"] + 8
    hold_selection(page, (box["x"] + 2, line), (box["x"] + box["width"] - 2, line))
    held = page.evaluate("() => getSelection().toString()")
    assert held.strip() != "", (
        f"the drag selected nothing, so this says nothing about the door: {held!r}"
    )
    page.mouse.up()
    expect(draft.locator("textarea")).to_have_count(0)

    # A press opens it, with the caret where the press landed rather than at the top.
    page.evaluate("() => getSelection().removeAllRanges()")
    at = page.evaluate(
        """(word) => {
            const node = document.createTreeWalker(
              document.querySelector('#draft-ops .lf-draft-body'),
              NodeFilter.SHOW_TEXT).nextNode();
            const start = node.data.indexOf(word);
            const range = document.createRange();
            range.setStart(node, start); range.setEnd(node, start + word.length);
            const r = range.getBoundingClientRect();
            return [r.x + r.width / 2, r.y + r.height / 2, start, word.length];
        }""",
        "migration",
    )
    page.mouse.click(at[0], at[1])
    editor = draft.locator("textarea")
    expect(editor).to_be_focused()
    caret = page.evaluate(
        "() => { const t = document.querySelector('#draft-ops textarea');"
        "        return [t.selectionStart, t.selectionEnd]; }"
    )
    assert caret[0] == caret[1], (
        f"one press selected a range rather than placing a caret: {caret}"
    )
    assert at[2] <= caret[0] <= at[2] + at[3], (
        f"the box opened with the caret at {caret[0]}, not in the word pressed "
        f"({at[2]}..{at[2] + at[3]})"
    )

    # The chrome inside the box is not the door, and does not dress as one. The controls
    # row and the edit box are both things `offer` built and neither names a kind.
    inside = page.evaluate(
        """() => [...document.querySelectorAll('#draft-ops [data-lf-offer=""]')]
             .map((el) => [el.localName, getComputedStyle(el).cursor])"""
    )
    assert inside, "the draft built no generated chrome, so this proves nothing"
    assert all(cursor != "pointer" for _tag, cursor in inside), (
        f"generated chrome inside the draft dresses as a press: {inside}"
    )

    # And the pencil is still there, still the keyboard's way in.
    page.keyboard.press("Escape")
    pencil = draft_controls(page).locator(".lf-draft-pencil")
    expect(pencil).to_be_focused()
    pencil.click()
    expect(draft.locator("textarea")).to_be_visible()
    assert errors == []
    page.close()
