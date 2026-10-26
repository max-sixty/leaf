"""Comment marks painted on the page, the cues that tie them to their thread cards, and
the notes that tell a screen reader of them."""

import io
import re

import pytest
from interact_support import append_carried_log_record
from PIL import Image, ImageChops
from playwright.sync_api import expect
from render_cases_interaction import HOLD_MOTION, live_url
from render_cases_layout import page_at_rest
from render_cases_navigation import (
    COMMENTED_LIST_PAGE,
    DIFF_PAGE,
    NOTED_PAGE,
    composer_quote,
    current_location_mark,
    mark_point,
    painted,
    pending_text,
    wait_current_location,
    wait_for_pending_mark,
)
from render_harness import (
    INLINE_PAGE,
    PANEL,
    accessible_details,
    comment_note,
    expect_comment_notes,
    open_page,
    post_event,
    select,
    selection_field,
    sending,
    stamp_page,
    told,
    write,
)

from browser.navigation import (
    color_cue_markup,
)
from leaf import event_log as events_model

pytestmark = pytest.mark.shifts_unsurveyed


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_color_cues_fade_to_the_live_surface(request, serve, engine):
    """Transient paint fades smoothly and returns to current hover or theme fill."""
    page = open_page(request.getfixturevalue(engine), serve(color_cue_markup()))
    page.emulate_media(reduced_motion="no-preference")
    page.evaluate("() => {" + HOLD_MOTION + "}")
    page.keyboard.press("m")
    expect(page.locator("#ask-first")).to_be_focused()
    page.keyboard.press("m")
    expect(page.locator("#ask-second")).to_be_focused()
    cue_target = page.locator('#views [aria-controls="second"] .lf-tab-name')
    colours = cue_target.evaluate(
        """async node => {
          const cue = node.getAnimations()[0];
          if (!cue) throw new Error('the gesture has no color cue');
          cue.pause();
          const duration = cue.effect.getComputedTiming().endTime;
          const colours = [];
          for (const fraction of [0, .25, .5, .75, .99]) {
            cue.currentTime = duration * fraction;
            await new Promise(requestAnimationFrame);
            colours.push(getComputedStyle(node).backgroundColor);
          }
          return colours;
        }"""
    )
    assert len(set(colours)) >= 4, colours
    page.emulate_media(color_scheme="dark")
    fills = cue_target.evaluate(
        """async node => {
          const cue = node.getAnimations()[0];
          cue.effect.updateTiming({fill: 'forwards'});
          cue.currentTime = cue.effect.getComputedTiming().endTime;
          await new Promise(requestAnimationFrame);
          const end = getComputedStyle(node).backgroundColor;
          cue.cancel();
          await new Promise(requestAnimationFrame);
          return {end, rest: getComputedStyle(node).backgroundColor};
        }"""
    )
    assert fills["end"] == fills["rest"], fills


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_highlight_paint_reaches_nested_syntax_in_the_widgets_theme(
    request, serve, engine
):
    """Native ranges paint nested syntax with the widget's local palette.

    Root-only highlight selectors lose this paint in Firefox, which accepts
    the rules but does not inherit highlight styles into descendants.
    """
    page = open_page(request.getfixturevalue(engine), serve(DIFF_PAGE))
    widget = page.locator("#patch")
    row = widget.locator("[data-line]").first
    expect(row.locator("span").first).to_be_visible()
    row.scroll_into_view_if_needed()
    widget.evaluate("""host => {
      host.style.setProperty('--mark', 'light-dark(rgb(250, 160, 180), rgb(90, 50, 120))');
      host.style.setProperty('--mark-ink', 'light-dark(rgb(120, 0, 40), rgb(250, 200, 230))');
    }""")
    backgrounds = []
    for scheme in ("light", "dark"):
        page.emulate_media(color_scheme=scheme)
        paint = row.evaluate("""row => {
          const names = ['lf-mark', 'lf-mark-hover', 'lf-mark-here',
            'lf-pending', 'lf-react', 'lf-version-insert'];
          const token = row.querySelector('span');
          const read = (node, name) => {
            const style = getComputedStyle(node, `::highlight(${name})`);
            return {background: style.backgroundColor, decoration: style.textDecoration};
          };
          return Object.fromEntries(names.map(name => [name, read(token, name)]));
        }""")
        for name, style in paint.items():
            assert style["background"] != "rgba(0, 0, 0, 0)", (scheme, name, style)
            if name != "lf-version-insert":
                assert "underline" in style["decoration"], (scheme, name, style)
        backgrounds.append(paint["lf-mark"]["background"])
        page.evaluate("CSS.highlights.delete('lf-mark')")
        quiet = Image.open(io.BytesIO(row.screenshot())).convert("RGB")
        row.evaluate("""row => {
          const range = new Range();
          range.selectNodeContents(row);
          CSS.highlights.set('lf-mark', new Highlight(range));
        }""")
        marked = Image.open(io.BytesIO(row.screenshot())).convert("RGB")
        assert ImageChops.difference(quiet, marked).getbbox(), (
            f"{engine} painted no highlight over nested syntax in {scheme}"
        )
        page.evaluate("CSS.highlights.delete('lf-mark')")
    assert backgrounds == ["rgb(250, 160, 180)", "rgb(90, 50, 120)"]


def test_composer_marks_the_passage_instead_of_quoting_it(browser, serve):
    """The passage stays visible while its comment is written. Focus moves into the
    composer the moment it opens, which drops the browser's own selection, so the
    runtime paints the anchor itself, and repaints it after every pass that redraws
    the posted threads' marks around it — otherwise a comment arriving mid-sentence
    would leave the user's passage stranded across stale text nodes. It comes down
    with the box, and the whole time it never touches the document.

    And because the mark says which passage the box is on, the box doesn't say it too:
    the quote inside it stays out of sight while the page is marking the passage."""
    url = serve(INLINE_PAGE)
    page = open_page(browser, url)

    page.locator("#p").click(
        click_count=3
    )  # a real selection, spanning the inline tags
    page.keyboard.press("c")
    page.locator(".lf-fab-input").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').hasAttribute('data-lf-open')"
    )

    passage = " ".join(page.locator("#p").inner_text().split())
    quote = composer_quote(page)
    assert pending_text(page) == passage, (
        f"the page marks {pending_text(page)!r}, but the composer is anchored to {quote['text']!r}"
    )
    assert not quote["shown"], (
        f"the passage is marked on the page and the composer prints it as well: {quote['text']!r}"
    )
    # Out of sight, not gone: it is what the box's description resolves to, and a screen
    # reader hears nothing from a painted mark.
    assert quote["text"] == f"“{passage}”", (
        f"the composer's description of its passage says {quote['text']!r}"
    )
    assert (
        page.evaluate(
            "() => document.querySelector('.lf-composer leaf-text').getAttribute('aria-describedby')"
        )
        == "lf-composer-quote"
    ), "nothing announces what the box is anchored to"
    # Carrying that description costs the node an id, which is what makes it the one piece
    # of injected chrome that could answer "which section of the document is this in" with
    # itself. The reading position rides on that answer, so a reload would scroll to the
    # comment box instead of to the page.
    assert (
        page.evaluate(
            "() => document.getElementById('lf-composer-quote')"
            ".closest('[id]:not(.lf-ui)')?.id ?? null"
        )
        is None
    ), "the composer's own quote offers itself as a landmark in the document"

    # A comment landing from elsewhere re-runs the anchor pass, which splits the text
    # nodes the painted range is pinned to. The user is mid-sentence; their passage
    # can neither blink out nor come back covering the wrong words.
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "arriving mid-sentence",
            "anchor": {"section": "p", "quote": "bold text"},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert pending_text(page) == passage, (
        "a poll landing while the composer is open disturbed the passage"
    )

    page.keyboard.press("Escape")
    assert pending_text(page) == "", "the highlight outlived its composer"

    # A selection across two options crosses their passage fence, so the composer
    # shows its detached quote. The widget's own control is not part of that quote.
    chrome = page.locator("#opts .lf-pick").first.text_content().strip()
    assert chrome, "this assertion needs the widget to have rendered chrome inside it"
    page.evaluate("""() => {
        const r = document.createRange();
        r.selectNodeContents(document.querySelector('#opts'));
        const s = getSelection(); s.removeAllRanges(); s.addRange(r);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
    }""")
    selection_field(page).click()
    page.locator(".lf-fab-input").click()
    quote = composer_quote(page)
    assert quote["shown"], "a selection across option cells cannot paint one passage"
    assert "Keep the store" in quote["text"]
    assert "Signed tokens" in quote["text"]
    assert chrome not in quote["text"], (
        f"the detached quote included the widget's own {chrome!r} control"
    )
    assert pending_text(page) == ""
    page.keyboard.press("Escape")

    # A diagram has no text to quote, so its anchor is the element and its mark is an
    # outline. That one the anchor pass really does take down, so it has to be redrawn.
    page.locator("#fig svg").click(modifiers=["Alt"])
    page.locator(".lf-fab-input").click()
    page.locator("#fig.lf-mark-el.lf-pending").wait_for()
    assert not composer_quote(page)["shown"], (
        "the outline is on the figure and the composer names its section as well"
    )
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={"kind": "comment", "revision": 1, "text": "and another"},
    )
    told(page)
    assert page.locator("#fig.lf-mark-el.lf-pending").count() == 1, (
        "a poll landing while the composer is open dropped the outline"
    )

    # Both classes have to go, asserted apart: leaving .lf-mark-el behind repaints the
    # figure in the posted mark's own ink, pointer cursor and all, over no thread to open.
    page.keyboard.press("Escape")
    assert page.locator("#fig.lf-pending").count() == 0, (
        "the mark outlived its composer"
    )
    assert page.locator("#fig.lf-mark-el").count() == 0, (
        "the figure kept a thread's mark over no thread"
    )

    # A drag across the caption remains a native selection, so the composer carries the
    # caption's words rather than the enclosing figure's element anchor.
    cap = page.locator("#fig figcaption").bounding_box()
    y = cap["y"] + cap["height"] / 2
    select(page, (cap["x"] + 2, y), (cap["x"] + cap["width"] - 2, y))
    page.locator(".lf-fab-input").click()
    wait_for_pending_mark(page)
    assert "sample" in pending_text(page), (
        "the visual containing the drag replaced its selected passage"
    )
    assert page.locator("#fig.lf-pending").count() == 0, (
        "the figure got the element mark over a live selection"
    )
    page.keyboard.press("Escape")


@pytest.mark.parametrize(
    "reply_paragraphs",
    # Either side of the card's fit, and a reply that does not fit at all.
    [0, 10, 18],
    ids=["short", "near-fit", "long"],
)
def test_pressing_a_page_mark_stands_in_the_thread_it_opens(
    browser, serve, reply_paragraphs
):
    """Pointer and keyboard arrival open one compact thread card. Enter or c
    enters its reply, and Escape returns through each layer. The Page Map fallback
    remains live at the same time: declaration order cannot move it ahead of the causal
    frame. The page mark follows both focus modes. A long reply needs no other landing
    than the card's."""
    url = serve(
        INLINE_PAGE, anchored=[("p", "bold text"), ("p2", "neighbouring block")]
    )
    if reply_paragraphs:
        root = next(
            event["id"]
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "comment"
        )
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "agent",
                "parent": root,
                "revision": 1,
                "text": "\n\n".join(
                    f"Consideration {i}: the response needs room for its explanation."
                    for i in range(reply_paragraphs)
                ),
            },
        )
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    first_id, second_id = (
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    thread = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-thread="{first_id}"]'
    )
    second = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-thread="{second_id}"]'
    )
    reply = thread.locator("leaf-text")

    page.mouse.click(*mark_point(page, "lf-mark"))
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(PANEL)).not_to_have_attribute("data-open", re.compile("."))

    expect(thread).to_be_focused()
    expect(reply).to_be_visible()
    wait_current_location(page, "bold text")
    page.keyboard.press("Enter")
    expect(reply).to_be_focused()
    expect(reply).to_be_visible()
    page.keyboard.type("t")
    expect(reply).to_have_js_property("value", "t")
    expect(reply).to_be_focused()
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    page.keyboard.press("Escape")  # onto the element the thread is about
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    comment_note(page, "#p").press("Enter")
    expect(thread).to_be_focused()
    # The note reopened this view without a navigation step, so the Page Map rung is the way out.
    # A sequence armed afterward is an inner interaction; Escape cancels it first.
    page.keyboard.press("g")
    expect(page.locator("body")).to_have_attribute("data-lf-go-to-active", "")
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("c")
    expect(reply).to_be_focused()
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")  # onto the element the thread is about
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    comment_note(page, "#p").press("Enter")
    expect(thread).to_be_focused()
    page.keyboard.press("t")
    expect(second).to_be_focused()
    wait_current_location(page, "neighbouring block")
    page.keyboard.press("Enter")
    expect(second.locator("leaf-text")).to_be_focused()
    page.keyboard.press("Escape")
    expect(second).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")  # onto the element the thread is about
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    # Enter the known source before testing the directional walk. After Escape,
    # that walk starts from the visible passage rather than a saved card cursor.
    comment_note(page, "#p").press("Enter")
    expect(thread).to_be_focused()
    page.keyboard.press("t")
    expect(second).to_be_focused()
    page.keyboard.press("Shift+t")
    expect(thread).to_be_focused()
    page.keyboard.press("Enter")
    expect(reply).to_be_focused()
    expect(reply).to_be_visible()


def test_the_page_marks_the_comment_the_user_is_located_in(browser, serve):
    """A user sent from a comment to its passage lands among every other mark on the
    page, all of them painted alike. The page says which one they asked for too: the
    thread holding the focus paints its own passage apart from the rest for as long as
    the user remains in that thread.

    Read off the focus rather than off the travel, so it answers where the user *is*.
    The walk moves it, a reply box keeps it — being located in a comment keeps that location
    while writing back — and leaving the thread takes it down, rather than leaving a
    page wearing "you are here" about a comment nobody is in."""
    url = serve(INLINE_PAGE)
    page = open_page(browser, url)
    api = url.rsplit("/versions/", 1)[0] + "/api/event"
    for anchor, text in (
        ({"section": "p", "quote": "bold text"}, "on the first"),
        ({"section": "p2", "quote": "neighbouring block"}, "on the second"),
        ({"section": "fig"}, "on the figure"),
    ):
        post_event(
            page,
            api,
            data={"kind": "comment", "revision": 1, "text": text, "anchor": anchor},
        )
    roots = [
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 2")
    page.locator("#fig.lf-mark-el").wait_for()

    assert current_location_mark(page) == {
        "text": "",
        "elements": [],
    }, "a page nobody has opened a comment on is already saying the user is in one"

    page.keyboard.press("t")
    wait_current_location(page, "bold text")

    # The four readings of a marked passage have to stay in this order, or one of them
    # stops being visible where they overlap: the posted mark, the hover over it, the
    # current comment's own ink, and above all three the draft the user is writing.
    # Asked with the pointer actually resting on the current-location mark, because that is the
    # overlap the order exists for and because nothing registers the hover until a mouse
    # has been over a passage. A higher highlight supplies only the properties it states,
    # so this is what lets one mark say "clickable" and "you are here" at once.
    # Opening the inline card moves the document to the passage; settle it before
    # reading pointer geometry.
    page_at_rest(page)
    page.mouse.move(*mark_point(page, "lf-mark-here"))
    page.wait_for_function("() => (CSS.highlights.get('lf-mark-hover')?.size ?? 0) > 0")
    ranks = page.evaluate(
        """() => ['lf-mark', 'lf-mark-hover', 'lf-mark-here', 'lf-pending']
            .map(n => CSS.highlights.get(n)?.priority ?? null)"""
    )
    assert all(r is not None for r in ranks) and ranks == sorted(set(ranks)), (
        f"the marks' paint order is not strictly increasing: {ranks}"
    )
    assert current_location_mark(page)["text"] == "bold text", (
        "the pointer resting on the current-location mark took its own ink away"
    )

    page.keyboard.press("t")
    wait_current_location(page, "neighbouring block")

    # A passage with no words to paint says the same thing with the outline it already
    # wears, so the two kinds of anchor answer one question and not two.
    page.keyboard.press("t")
    wait_current_location(page, "", ["fig"])
    # Past the last comment the walk comes round to the first, and back again.
    first = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-thread="{roots[0]}"]'
    )
    page.keyboard.press("t")
    expect(first).to_be_focused()
    wait_current_location(page, "bold text")
    page.keyboard.press("Shift+t")
    expect(
        page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{roots[2]}"]')
    ).to_be_focused()
    wait_current_location(page, "", ["fig"])
    page.keyboard.press("Shift+t")
    wait_current_location(page, "neighbouring block")
    page.keyboard.press("Shift+t")
    expect(first).to_be_focused()
    wait_current_location(page, "bold text")

    # Located in a comment while writing back to it is still located in it: the reply
    # box is inside the thread, and knowing which passage it is on is worth most there.
    first.locator("leaf-text").focus()
    wait_current_location(page, "bold text")

    # And leaving the thread takes it down. A mark that outlived the user's attention
    # would be a page insisting on a comment nobody is in.
    page.evaluate("() => document.activeElement.blur()")
    wait_current_location(page, "")
    assert painted(page, "lf-mark") != "", (
        "the posted marks went down with the current one"
    )


def test_the_mark_ramp_ranks_posted_pointed_and_current_location(browser, serve):
    """Three things a mark can be — posted, indicated, stood in — are three steps of one
    wash, ranked apart from the page's own ground, so a hand resting where it just
    clicked never lights the two alike."""
    url = serve(INLINE_PAGE)
    page = open_page(browser, url)
    api = url.rsplit("/versions/", 1)[0] + "/api/event"
    post_event(
        page,
        api,
        data={
            "kind": "comment",
            "revision": 1,
            "text": "on the first",
            "anchor": {"section": "p", "quote": "bold text"},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 1")

    # Measured as composited pixels rather than as declarations, because a rule full of
    # var() and color-mix reads back non-empty whatever it resolves to, and two alphas of
    # one hue is exactly the pair a string comparison calls different and the eye does
    # not. So the wash is painted over the page's own ground and the result compared in
    # Lab: ordering by distance from that ground, which holds in both colour schemes
    # because the wash is darker than the page in one and lighter in the other, and a
    # floor under each step, because ordering alone passes a middle set one alpha unit
    # from its neighbour. The floor is 4, against a just noticeable difference near 2.3
    # and the palette's own 6.4 and 6.5 in light, 7.4 and 7.2 in dark.
    ramp = page.evaluate("""() => {
        const declared = (name) =>
            getComputedStyle(document.getElementById('p'), `::highlight(${name})`)
                .backgroundColor;
        const paper = getComputedStyle(document.body).backgroundColor;
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = 1;
        const ctx = canvas.getContext('2d', {willReadFrequently: true});
        const over = (css) => {
            ctx.fillStyle = paper; ctx.fillRect(0, 0, 1, 1);
            if (css !== null) { ctx.fillStyle = css; ctx.fillRect(0, 0, 1, 1); }
            return [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3);
        };
        const lab = (px) => {
            const [r, g, b] = px.map(v => {
                const c = v / 255;
                return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
            });
            const f = (t) => t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116;
            const x = f((r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047);
            const y = f(r * 0.2126 + g * 0.7152 + b * 0.0722);
            const z = f((r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883);
            return [116 * y - 16, 500 * (x - y), 200 * (y - z)];
        };
        const de = (a, b) => Math.hypot(...lab(a).map((v, i) => v - lab(b)[i]));
        const ground = over(null);
        const steps = {};
        for (const [step, name] of [['posted', 'lf-mark'], ['pointed', 'lf-mark-hover'],
                                    ['currentLocation', 'lf-mark-here']]) {
            steps[step] = over(declared(name));
        }
        return {
            fromGround: Object.fromEntries(
                Object.entries(steps).map(([k, v]) => [k, +de(v, ground).toFixed(2)])),
            apart: {
                'posted→pointed': +de(steps.posted, steps.pointed).toFixed(2),
                'pointed→current-location': +de(steps.pointed, steps.currentLocation).toFixed(2),
            },
        };
    }""")
    order = ramp["fromGround"]
    assert order["posted"] < order["pointed"] < order["currentLocation"], (
        "the three things a mark can be are not three steps away from the page's own"
        f" ground, so the wash does not rank them: {order}"
    )
    assert min(ramp["apart"].values()) >= 4, (
        "two steps of the mark ramp are too close for a user to tell apart without one"
        f" of the other beside it: {ramp['apart']}"
    )


def test_a_commented_block_says_so_to_a_screen_user(browser, serve):
    """A mark is painted, not wrapped, so it builds no accessibility node and a passage
    carrying a comment reads exactly like one that doesn't. So each commented block names
    a note as its details, ARIA's relation for an annotation: a button in the chrome
    saying how many comments the block carries, counting up per block, riding in on a
    sent comment's round trip, and leaving with its thread. The note is the runtime's, so
    it stays out of the document: out of a selection, out of the next quote, and out of
    the mutations a screen reader rebuilds its buffer on."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir

    def comment(anchor, text):
        return append_carried_log_record(
            d,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": text,
                "anchor": anchor,
            },
        )["id"]

    c1 = comment({"quote": "first passage"}, "Sharpen this.")
    c2 = comment({"quote": "two separate remarks"}, "Second thought.")
    comment({"section": "fig"}, "The figure too.")
    page = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Two threads on one block count up, and leave one note rather than two.
    expect_comment_notes(page, "#p1", 1)
    # The block is named by its words, cut short as every chrome name is.
    named = "2 comments on § paragraph · The first passage under discussion, with words enough for…"
    assert accessible_details(page, "#p1") == [named], (
        "a screen reader reading the block is told nothing about the comments on it"
    )
    note = comment_note(page, "#p1")
    # Hidden means hidden from the eye, not the tree.
    assert note.evaluate(
        "el => { const r = el.getBoundingClientRect(); return r.width <= 1 && r.height <= 1; }"
    ), "the resting note is painting on screen"
    assert note.evaluate("el => getComputedStyle(el).opacity") == "0"
    assert note.evaluate("el => el.tabIndex") == -1, (
        "the note is a Tab stop in the chrome, after the whole page"
    )
    page.evaluate("""() => {
        window.__lfNote = document.getElementById('p1').ariaDetailsElements[0];
    }""")
    inline1 = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{c1}"]')
    inline2 = page.locator(f'.lf-margin-preview .lf-page-thread[data-thread="{c2}"]')
    expect(note).to_have_role("button")
    # Focused with the keyboard's modality, as a screen reader moving to it focuses it,
    # the note shows and enters the first thread, and the walk goes on from there.
    page.keyboard.press("Tab")
    note.focus()
    expect(note).to_be_focused()
    assert note.evaluate("el => el.getBoundingClientRect().width > 1"), (
        "the comment path stayed invisible when a keyboard user reached it"
    )
    assert note.evaluate("el => getComputedStyle(el).opacity") == "1"
    note.press("Enter")
    expect(inline1).to_be_focused()
    expect(page.locator(PANEL)).not_to_have_attribute("data-open", re.compile("."))
    page.keyboard.press("t")
    expect(inline2).to_be_focused()

    # Once the first thread resolves, the same control enters the next one.
    append_carried_log_record(d, {"kind": "resolve", "author": "user", "parent": c1})
    note.focus()
    told(page)
    expect(note).to_have_text("1 comment")
    expect(note).to_be_focused()
    assert page.evaluate("""() =>
        window.__lfNote === document.getElementById('p1').ariaDetailsElements[0]
    """), "a count change replaced the note"
    note.press("Enter")
    expect(inline2).to_be_focused()
    # An element anchor has no text to paint, and the element it names carries the note.
    assert any(
        detail.startswith("1 comment on § figure")
        for detail in accessible_details(page, "#fig")
    ), "the figure's comment note is missing from its accessible details"

    # A pass that finds nothing to change must change nothing: a screen reader rebuilds
    # its buffer on every mutation, and this pass runs on every poll. A comment on no
    # passage at all is what proves a pass ran without touching the block's count.
    page.evaluate("""() => {
        window.__churn = 0;
        new MutationObserver(rs => (window.__churn += rs.length))
            .observe(document.getElementById('p1'), {childList: true,
                     characterData: true, attributes: true, subtree: true});
    }""")
    comment({}, "On the page as a whole.")
    told(page)
    assert page.evaluate("() => window.__churn") == 0, (
        "a poll that changed nothing still rewrote the block, so a screen reader re-reads it"
    )

    # The note belongs to the runtime, not the document: a user dragging across the
    # block neither copies it nor quotes it.
    page.locator("#p1").click(click_count=3)
    assert "comment" not in page.evaluate("() => getSelection().toString()"), (
        "the note came along in the user's own selection"
    )
    page.locator(".lf-fab-input").click()
    assert "comment" not in composer_quote(page)["text"], (
        "the note came along in the quote the comment would store"
    )
    page.keyboard.press("Escape")

    # The gesture's own comment reaches the note once the send's round trip lands.
    box = page.locator("#p2").bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    page.locator(".lf-fab-input").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').hasAttribute('data-lf-open')"
    )
    write(page.locator(".lf-composer leaf-text"), "Too short.")
    with sending(page, "the comment on the second passage"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect_comment_notes(page, "#p2", 1)
    c4 = [e for e in events_model.read_events(d) if e.get("kind") == "comment"][-1][
        "id"
    ]

    # A resolved thread takes its note with it, and gives the block back its own
    # attributes: the pass owns what it wrote.
    append_carried_log_record(d, {"kind": "resolve", "author": "user", "parent": c4})
    told(page)
    expect_comment_notes(page, "#p2", 0)
    expect(page.locator("#p2")).not_to_have_attribute("aria-details", re.compile(".*"))
    assert accessible_details(page, "#p1")[0].startswith("1 comment on ")

    # A passage crossing two blocks says so in both: a user landing on either block
    # hears about the comment, the way the paint reaches both.
    comment({"quote": "to land in it. A short second"}, "Crosses the boundary.")
    told(page)
    expect_comment_notes(page, "#p2", 1)
    assert accessible_details(page, "#p1")[0].startswith("2 comments on ")
    assert accessible_details(page, "#p2")[0].startswith("1 comment on ")


def test_a_revision_keeps_a_block_naming_its_comment_note(browser, serve):
    """A revision that keeps a commented block and changes its own `aria-details` writes
    the new source's value over the block's name for its note. The next pass names the
    note again after the source's own details, and the note's release keeps the source's
    value rather than the one the block had when the comment arrived."""
    url = serve(NOTED_PAGE, anchored=[("p1", "first passage")])
    page = open_page(browser, live_url(url))
    expect_comment_notes(page, "#p1", 1)
    source = (serve.page_dir / "index.html").read_text(encoding="utf-8")
    stamp_page(
        serve.page_dir,
        source.replace('<p id="p1">', '<p id="p1" aria-details="p2">'),
        "Point the first passage at the second",
    )
    told(page)
    expect(page.locator("#p2")).to_be_attached()
    page.wait_for_function(
        """() => document.getElementById('p1').ariaDetailsElements
            ?.map((el) => el.id || el.textContent).join('|') === 'p2|1 comment'"""
    )


def test_a_comment_leaves_its_block_as_the_page_wrote_it(browser, serve):
    """Nothing Leaf draws moves the page's content (assets/AGENTS.md, "Space and
    scrolling"), and the page's own rules read a block's structure: here the last item
    of a list takes a wide bottom margin. A comment on the list adds no child to it, so
    the rule keeps matching and the paragraph after the list stays where it stood."""
    url = serve(COMMENTED_LIST_PAGE)
    page = open_page(browser, url)
    read = """() => ({
        children: [...document.getElementById('list').children].map(el => el.id),
        after: document.getElementById('after').getBoundingClientRect().top,
    })"""
    before = page.evaluate(read)
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Is this list complete?",
            "anchor": {"section": "list"},
        },
    )
    told(page)
    expect_comment_notes(page, "#list", 1)
    assert page.evaluate(read) == before
