"The document's shared, semantic margin map."

import re

import pytest
from interact_support import (
    append_carried_log_record,
)
from journeys.test_render_margin import (
    MARGIN_ACTIONS_EVENTS,
    OBLIGATION_IN_LONG_PAGE,
    SUGGESTION_PINS,
    THREAD_CARD_PAGE,
    _open_thread,
    _seed_card_threads,
)
from playwright.sync_api import expect
from render_cases_navigation import (
    go_to_address,
)
from render_harness import (
    LONG_PAGE,
    RELEASE_FOCUS,
    margins_laid_out,
    open_page,
    pane_scroll_behavior,
    resized,
    sending,
    write,
)

from browser.margin import (
    CARD_AND_REPLY,
    MARGIN_ACTIONS_PAGE,
    PANE_PIN_PAGE,
    WORDS_RIGHT,
    _comment_on,
    _focused_editor_caret,
    _unfold,
    _unfold_suggestion_undo,
)
from leaf import render_checks as render_checks_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_an_unchanged_compact_margin_keeps_the_user_at_the_document_end(browser, serve):
    """Re-laying the pins of a compact page cannot pull a user back from the bottom:
    they stand over the page, so the document's height is the page's own. The last
    paragraphs carry them, so a pin laid out in flow would lengthen the document."""
    url = serve(LONG_PAGE)
    for i in range(48, 60):
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "agent",
                "revision": 1,
                "text": f"A note on paragraph {i}.",
                "anchor": {"section": f"p{i}"},
            },
        )
    page = open_page(browser, url)
    resized(page, 700, 500)
    margins_laid_out(page)
    assert page.locator('.lf-margin-cluster[data-lf-place="pin"]').count() >= 10

    position = page.evaluate(
        """async () => {
          const frame = () => new Promise(resolve => requestAnimationFrame(resolve));
          window.scrollTo(0, document.documentElement.scrollHeight);
          await frame();
          const reading = () => ({
            y: window.scrollY,
            end: document.documentElement.scrollHeight - window.innerHeight,
          });
          const before = reading();
          const laidOut = new Promise(resolve =>
            document.addEventListener('lf-margin-layout', resolve, {once: true})
          );
          window.dispatchEvent(new Event('resize'));
          await laidOut;
          await frame();
          return {before, after: reading()};
        }"""
    )

    assert position["before"]["y"] == position["before"]["end"]
    assert position["after"] == position["before"]


def test_a_settled_page_with_a_reaction_in_force_stops_rendering_its_margin(
    browser, serve
):
    """A page standing still with a reaction in its margin renders no margin per frame.

    A margin render ends in `paintKeys`, which ends in the shared repaint, and that
    repaint runs chrome layout. Anything chrome layout did that restated a reaction
    seat's offer would close a cycle — chrome layout, margin render, paint, chrome
    layout — and the gallery once ran a whole margin render every frame with nothing
    dispatched and nothing on the page moving: ~350ms of main thread per frame, long
    enough that every Playwright read of that page waited on it.

    The reaction seat is asserted first, because it is the ingredient that cycle needed:
    a page with no seat passes this without saying anything. The heartbeat is the one
    render a settled page is allowed here, and it comes every two seconds, so at most
    one of these frames can carry it.
    """
    page = open_page(browser, serve(MARGIN_ACTIONS_PAGE, events=MARGIN_ACTIONS_EVENTS))
    resized(page, 1280, 900)
    margins_laid_out(page)
    assert page.locator(".lf-react-mark").count() >= 1

    layouts = page.evaluate(
        """async frames => {
          const frame = () => new Promise(resolve => requestAnimationFrame(resolve));
          for (let i = 0; i < 10; i++) await frame();
          let seen = 0;
          const count = () => { seen += 1; };
          document.addEventListener('lf-margin-layout', count);
          for (let i = 0; i < frames; i++) await frame();
          document.removeEventListener('lf-margin-layout', count);
          return seen;
        }""",
        30,
    )

    assert layouts <= 1, layouts


def test_a_decision_undone_leaves_every_suggestion_pin_where_it_stood(browser, serve):
    """At 390px the three suggestions share one paragraph, so a
    decision reflows the words the others stand by, and their pins follow those words,
    folding where a pair loses its room. Undoing the decision puts the words back, and
    with them every pin: each stands where it stood, folded as it was, with the same
    controls. The words put back can shape up to two pixels narrower than they first
    did, with the same markup and style, so a pin may move by as much as its words'
    end did and no more."""
    page = open_page(browser, serve(MARGIN_ACTIONS_PAGE))
    resized(page, 390, 900)
    margins_laid_out(page)
    ids = ["s-replace", "s-insert", "s-delete"]
    before = page.evaluate(SUGGESTION_PINS, ids)
    for target, outcome in (
        ("s-replace", "accept"),
        ("s-insert", "reject"),
        ("s-delete", "accept"),
    ):
        item = page.locator(f'[data-lf-margin-for="{target}"]')
        _unfold(item)
        applied = int(page.locator("body").get_attribute("data-lf-applied"))
        with sending(page, f"{outcome} {target}"):
            item.get_by_role(
                "button", name=re.compile(f"^{outcome.title()} the ")
            ).click()
        expect(page.locator("body")).to_have_attribute(
            "data-lf-applied", str(applied + 1)
        )
        render_checks_model.wait_until_ready(page)
        if target == "s-insert":
            inserted = page.locator("#s-insert lf-new")
            expect(inserted).to_have_attribute("data-lf-retired", "")
            expect(inserted).to_be_hidden()
        margins_laid_out(page)
        undo_control = _unfold_suggestion_undo(page, target)
        applied += 1
        with sending(page, f"undo {target}"):
            undo_control.click()
        expect(page.locator("body")).to_have_attribute(
            "data-lf-applied", str(applied + 1)
        )
        render_checks_model.wait_until_ready(page)
        margins_laid_out(page)
        # The pin just pressed is held under the pointer; let it go so it folds back.
        page.mouse.move(0, 0)
        page.evaluate(RELEASE_FOCUS)
        rendered(page)
        margins_laid_out(page)
        for suggestion in ids:
            expect(page.locator(f"#{suggestion}")).to_be_visible()
        after = page.evaluate(SUGGESTION_PINS, ids)
        faces = [
            [(i, f, [k for k, *_ in e]) for i, f, e, _ in pins]
            for pins in (before, after)
        ]
        assert faces[0] == faces[1], (target, before, after)
        drift = max(
            abs(w0 - w1) for (*_, w0), (*_, w1) in zip(before, after, strict=True)
        )
        for (_, _, was, _), (_, _, now, _) in zip(before, after, strict=True):
            for (_, x0, y0), (_, x1, y1) in zip(was, now, strict=True):
                assert abs(x0 - x1) <= drift + 0.5 and abs(y0 - y1) < 0.5, (
                    target,
                    before,
                    after,
                )


def test_margin_target_pointer_ownership_ends_with_its_host(browser, serve):
    """Replacing a hovered margin host cannot transfer its pointer ownership."""
    page = open_page(browser, serve(MARGIN_ACTIONS_PAGE))
    resized(page, 1280, 720)
    margins_laid_out(page)
    target = page.locator("#s-replace")
    target.scroll_into_view_if_needed()
    host = page.locator('[data-lf-margin-for="s-replace"]')
    box = host.bounding_box()
    pointer = {
        "x": int(box["x"] + box["width"] / 2),
        "y": int(box["y"] + box["height"] / 2),
    }
    page.mouse.move(pointer["x"], pointer["y"])
    trace = page.locator('.lf-target-trace[data-for="s-replace"]')
    expect(trace).to_be_visible()

    suggestion = target.element_handle()
    old_host = host.element_handle()
    assert suggestion is not None and old_host is not None
    suggestion.evaluate("node => node.remove()")
    page.wait_for_function("old => !old.isConnected", arg=old_host)
    page.evaluate(
        "node => document.querySelector('#s-crowded').before(node)",
        suggestion,
    )
    page.wait_for_function(
        """({x, y}) => {
          const host = document.querySelector('[data-lf-margin-for="s-replace"]');
          const box = host?.getBoundingClientRect();
          return host?.isConnected && host.checkVisibility() && box &&
            box.bottom > 0 && box.top < innerHeight &&
            !(box.left < x && x < box.right && box.top < y && y < box.bottom);
        }""",
        arg=pointer,
    )
    assert page.evaluate(
        "old => document.querySelector('[data-lf-margin-for=\"s-replace\"]') !== old",
        old_host,
    )
    expect(
        trace,
        "the replacement host inherited pointer ownership from its disconnected peer",
    ).to_be_hidden()

    replacement = page.locator('[data-lf-margin-for="s-replace"]')
    replacement_box = replacement.bounding_box()
    page.mouse.move(
        int(replacement_box["x"] + replacement_box["width"] / 2),
        int(replacement_box["y"] + replacement_box["height"] / 2),
    )
    expect(trace).to_be_visible()


def test_margin_target_hover_requires_pointer_movement(browser, serve):
    """Page motion under a parked pointer cannot take ownership from the keyboard."""
    page = open_page(browser, serve(OBLIGATION_IN_LONG_PAGE))
    resized(page, 1280, 720)
    page.locator("#route-ask").scroll_into_view_if_needed()
    go_to_address(page, "Margin entry", "route-ask")
    page.keyboard.press("Escape")
    margins_laid_out(page)
    host = page.locator('[data-lf-margin-for="route-ask"]')
    initial = host.bounding_box()
    pointer = {
        "x": int(initial["x"] + initial["width"] / 2),
        "y": int(initial["y"] + initial["height"] / 2),
    }
    scroll = page.evaluate("() => document.scrollingElement.scrollTop")
    page.evaluate("() => scrollBy({top: -150, behavior: 'instant'})")
    margins_laid_out(page)
    parked = host.bounding_box()
    assert not parked["y"] < pointer["y"] < parked["y"] + parked["height"], (
        "the pointer starts inside the obligation margin host"
    )
    page.mouse.move(pointer["x"], pointer["y"])

    page.evaluate("top => scrollTo({top, behavior: 'instant'})", scroll)

    page.wait_for_function(
        """({x, y}) => {
          const host = document.querySelector(
            '[data-lf-margin-for="route-ask"]'
          );
          const box = host?.getBoundingClientRect();
          return document.activeElement === document.body && box &&
            box.left < x && x < box.right && box.top < y && y < box.bottom;
        }""",
        arg=pointer,
    )
    trace = page.locator('.lf-target-trace[data-for="route-ask"]')
    expect(
        trace,
        "moving the margin under a stationary pointer claimed pointer ownership",
    ).to_be_hidden()

    page.mouse.move(pointer["x"] + 1, pointer["y"])
    expect(trace).to_be_visible()


def test_a_thread_uses_a_free_margin_and_tracks_its_source(browser, serve):
    """A readable free margin outranks an overlay and follows the selected cluster."""
    url = serve(THREAD_CARD_PAGE)
    text_thread, _ = _seed_card_threads(serve.page_dir)
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    resized(page, 2672, 900)
    page.evaluate(RELEASE_FOCUS)
    _open_thread(page, "thread-text", text_thread)
    expect(page.locator("#thread-text")).to_be_in_viewport()
    expect(page.locator(".lf-margin-preview")).to_be_visible()

    geometry = page.evaluate(
        """() => {
          const cardNode = document.querySelector('.lf-margin-preview');
          const controlsNode = document.querySelector(
            '[data-lf-margin-for="thread-text"]');
          const rect = node => node.getBoundingClientRect();
          const card = rect(cardNode);
          const controls = rect(controlsNode);
          const target = rect(document.querySelector('#thread-text'));
          const overlaps = (one, other) => one.left < other.right
            && other.left < one.right && one.top < other.bottom
            && other.top < one.bottom;
          const coveredControls = [...document.querySelectorAll('[data-lf-margin-for]')]
            .filter(node => node !== controlsNode && node.checkVisibility())
            .map(rect)
            .filter(other => other.width && other.height && overlaps(card, other)).length;
          return {placement: cardNode.dataset.lfThreadPlacement,
                  controlsRight: controls.right, targetRight: target.right,
                  controlsTop: controls.top, cardLeft: card.left,
                  cardTop: card.top, cardWidth: card.width, coveredControls,
                  targetTop: target.top, targetBottom: target.bottom,
                  preferred: parseFloat(getComputedStyle(cardNode)
                    .getPropertyValue('--thread-card'))};
        }"""
    )
    # With room for its whole measure, the card clears both its words and its cluster,
    # which here is a pin standing on the block the thread is about and reaching past it.
    assert geometry["placement"] == "right", geometry
    assert (
        geometry["cardLeft"]
        >= max(geometry["controlsRight"], geometry["targetRight"]) + 8 - 0.5
    ), geometry
    assert geometry["cardWidth"] == pytest.approx(geometry["preferred"], abs=0.5), (
        geometry
    )
    assert geometry["coveredControls"] == 0, geometry
    assert geometry["targetTop"] >= 0, geometry
    assert geometry["targetBottom"] <= 900, geometry

    # The card's top edge stands a gap over its words' first line while the whole card
    # fits under it, as the comment box's does (comment-placement.js), and it holds at
    # the window's foot once the words scroll lower than that. The panel stands beside
    # this margin, so it takes none of the card's height. Each scroll is read
    # after the frame the scroll listener places the card in.
    moved = page.evaluate(
        """async () => {
          const positions = () => {
            const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
            const panel = document.querySelector('.lf-fp-card').getBoundingClientRect();
            return {
              card: card.top, cardBottom: card.bottom, foot: innerHeight,
              besidePanel: card.left >= panel.right || card.right <= panel.left,
              // The words the thread quotes start the paragraph's first line.
              controls: (() => {
                const range = document.createRange();
                range.selectNodeContents(document.querySelector('#thread-text'));
                return range.getClientRects()[0].top - 8;
              })(),
              scrollY,
            };
          };
          const placed = () => new Promise(resolve => requestAnimationFrame(
            () => requestAnimationFrame(resolve)));
          // Keep the first two positions below the window's 8px boundary, so
          // these readings exercise following the words rather than clamping.
          scrollBy(0, 180);
          await placed();
          const high = positions();
          scrollBy(0, 40);
          await placed();
          const higher = positions();
          scrollBy(0, -450);
          await placed();
          const low = positions();
          return {high, higher, low};
        }"""
    )
    assert moved["high"]["card"] == pytest.approx(moved["high"]["controls"], abs=0.5)
    assert moved["higher"]["scrollY"] - moved["high"]["scrollY"] >= 39
    assert moved["higher"]["card"] - moved["higher"]["controls"] == pytest.approx(
        moved["high"]["card"] - moved["high"]["controls"], abs=0.5
    ), moved
    assert moved["low"]["controls"] > moved["low"]["card"], moved
    assert moved["low"]["besidePanel"], moved
    assert moved["low"]["cardBottom"] == pytest.approx(
        moved["low"]["foot"] - 8, abs=0.5
    ), moved
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    # Scrolled a window further, the words have left over the top, and the card leaves
    # with them, its top on their line.
    page.evaluate("scrollBy(0, innerHeight)")
    rendered(page)
    gone = page.evaluate(
        """() => {
          const range = document.createRange();
          range.selectNodeContents(document.querySelector('#thread-text'));
          return {
            card: document.querySelector('.lf-margin-preview').getBoundingClientRect().top,
            controls: range.getClientRects()[0].top,
          };
        }"""
    )
    assert gone["controls"] < 0, gone
    assert gone["card"] == pytest.approx(gone["controls"], abs=0.5), gone


def test_a_forced_inline_thread_keeps_its_control_reachable_on_a_crowded_cluster(
    browser, serve
):
    """A walked thread on a crowded cluster keeps its measure by standing over the
    cluster, clear of its words, rather than dropping under it."""
    url = serve(THREAD_CARD_PAGE)
    text_thread, crowded_thread = _seed_card_threads(serve.page_dir)
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1838, 900)
    page.evaluate(RELEASE_FOCUS)

    _open_thread(page, "thread-text", text_thread)
    _open_thread(page, "crowded", crowded_thread)

    crowded = page.locator('[data-lf-margin-for="crowded"]')
    expect(page.locator("#crowded")).to_be_in_viewport()
    thread = crowded.locator('.lf-margin-reading-option[data-lf-kinds="comment"]')
    expect(thread).to_be_visible()
    expect(thread).to_have_attribute("aria-expanded", "true")
    geometry = crowded.evaluate(
        """cluster => {
          const controls = cluster.getBoundingClientRect();
          const cardNode = document.querySelector('.lf-margin-preview');
          const card = cardNode.getBoundingClientRect();
          const overlaps = (one, other) => one.left < other.right
            && other.left < one.right && one.top < other.bottom
            && other.top < one.bottom;
          const coveredControls = [...document.querySelectorAll('[data-lf-margin-for]')]
            .filter(node => node.checkVisibility())
            .map(node => node.getBoundingClientRect())
            .filter(other => other.width && other.height && overlaps(card, other)).length;
          const bottomChrome = [...document.querySelectorAll('.lf-fp-card')]
            .filter(node => node.checkVisibility())
            .map(node => node.getBoundingClientRect());
          const words = document.querySelector('#crowded').getBoundingClientRect();
          return {placement: cardNode.dataset.lfThreadPlacement,
                  controlsLeft: controls.left, controlsRight: controls.right,
                  wordsRight: words.right, cardLeft: card.left, cardRight: card.right,
                  cardWidth: card.width, viewport: innerWidth,
                  preferred: parseFloat(getComputedStyle(cardNode)
                    .getPropertyValue('--thread-card')),
                  bottomChrome: bottomChrome.length,
                  coveredBottomChrome: bottomChrome.filter(box => overlaps(card, box)).length};
        }"""
    )
    # The rail beside this cluster is short of the card's minimum; the room right of the
    # words is not, so the card takes its measure there, beside the words and across
    # the cluster, where the comment box would stand (comment-placement.js).
    assert geometry["viewport"] - 8 - (geometry["controlsRight"] + 8) < 320, geometry
    assert geometry["placement"] == "right", geometry
    assert geometry["cardWidth"] == pytest.approx(geometry["preferred"], abs=0.5), (
        geometry
    )
    assert geometry["cardLeft"] == pytest.approx(geometry["wordsRight"] + 8, abs=0.5), (
        geometry
    )
    assert geometry["cardLeft"] < geometry["controlsLeft"], geometry
    assert geometry["cardRight"] <= geometry["viewport"] - 7.5, geometry
    assert geometry["bottomChrome"] > 0, geometry
    assert geometry["coveredBottomChrome"] == 0, geometry
    reply = page.locator(".lf-margin-preview leaf-text")
    page.locator(".lf-margin-preview").get_by_role(
        "textbox", name="Reply", exact=True
    ).click()
    write(reply, "The covered terrace is easier to find.")
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(reply).to_have_js_property("value", "The covered terrace is easier to find.")


def test_a_thread_in_a_short_rail_stands_on_the_side_with_room(browser, serve):
    """A rail short of the card's minimum puts the card on the side of its words that
    holds it, here the left, as it would the comment box (comment-placement.js), at its
    full height and level with the words."""
    url = serve(THREAD_CARD_PAGE)
    text_thread, _ = _seed_card_threads(serve.page_dir)
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1024, 900)
    page.evaluate(RELEASE_FOCUS)
    _open_thread(page, "thread-text", text_thread)
    geometry = page.evaluate(
        """() => {
          const cardNode = document.querySelector('.lf-margin-preview');
          const card = cardNode.getBoundingClientRect();
          const words = document.querySelector('#thread-text').getBoundingClientRect();
          const style = getComputedStyle(cardNode);
          const list = cardNode.querySelector('.lf-thread-transcript');
          return {placement: cardNode.dataset.lfThreadPlacement,
                  cardLeft: card.left, cardRight: card.right, cardWidth: card.width,
                  clipped: list.scrollHeight - list.clientHeight,
                  wordsLeft: words.left, viewport: innerWidth,
                  minimum: parseFloat(style.getPropertyValue('--thread-card-min'))};
        }"""
    )
    words = page.evaluate(WORDS_RIGHT)
    assert geometry["viewport"] - 8 - (words + 8) < geometry["minimum"], geometry
    assert geometry["wordsLeft"] - 16 >= geometry["minimum"], geometry
    assert geometry["placement"] == "left", geometry
    assert geometry["cardRight"] == pytest.approx(geometry["wordsLeft"] - 8, abs=0.5), (
        geometry
    )
    assert geometry["cardLeft"] >= 7.5, geometry
    assert geometry["cardWidth"] >= geometry["minimum"] - 0.5, geometry
    assert geometry["clipped"] <= 0, geometry


def test_a_thread_beside_its_words_takes_the_room_to_the_visible_edge(browser, serve):
    """A middle-width margin gives marker clearance to the message's width."""
    url = serve(THREAD_CARD_PAGE)
    text_thread, _ = _seed_card_threads(serve.page_dir)
    page = open_page(browser, url)
    page.emulate_media(reduced_motion="reduce")
    resized(page, 1600, 900)
    page.evaluate(RELEASE_FOCUS)
    _open_thread(page, "thread-text", text_thread)
    geometry = page.evaluate(
        """() => {
          const cardNode = document.querySelector('.lf-margin-preview');
          const list = cardNode.querySelector('.lf-thread-transcript');
          const card = cardNode.getBoundingClientRect();
          const words = document.querySelector('#thread-text').getBoundingClientRect();
          const pin = document.querySelector('[data-lf-margin-for="thread-text"]')
            .getBoundingClientRect();
          const style = getComputedStyle(cardNode);
          return {placement: cardNode.dataset.lfThreadPlacement,
                  cardLeft: card.left, cardRight: card.right, cardWidth: card.width,
                  wordsRight: words.right, pinRight: pin.right, viewport: innerWidth,
                  minimum: parseFloat(style.getPropertyValue('--thread-card-min')),
                  preferred: parseFloat(style.getPropertyValue('--thread-card')),
                  clipped: list.scrollHeight - list.clientHeight};
        }"""
    )
    room_past_pin = geometry["viewport"] - 8 - (geometry["pinRight"] + 8)
    assert geometry["wordsRight"] < geometry["pinRight"], geometry
    assert geometry["minimum"] <= room_past_pin < geometry["preferred"], geometry
    assert geometry["placement"] == "right", geometry
    assert geometry["cardLeft"] == pytest.approx(geometry["wordsRight"] + 8, abs=0.5), (
        geometry
    )
    # A compact marker can end inside the gap beside the words, especially with
    # Linux's narrower fonts. Width priority removes the marker's clearance; it
    # need not cover that marker's painted pixels.
    assert geometry["cardWidth"] > room_past_pin, geometry
    assert geometry["cardRight"] == pytest.approx(geometry["viewport"] - 8, abs=0.5), (
        geometry
    )
    assert geometry["minimum"] <= geometry["cardWidth"] < geometry["preferred"], (
        geometry
    )
    assert geometry["clipped"] <= 0, geometry


@pytest.mark.parametrize(
    ("size", "route"),
    [((1440, 900), "paste"), ((1000, 700), "paste"), ((1440, 600), "typing")],
)
def test_drafting_in_a_pane_keeps_the_card_and_reply_top_when_its_room_runs_out(
    browser, serve, size, route
):
    """A bounded pane supplies the drafting room just as the window does. Growing
    past that room scrolls the editor without carrying the card or its first line."""
    page = open_page(browser, serve(PANE_PIN_PAGE, events=[_comment_on("pane-top")]))
    resized(page, *size)
    pane_scroll_behavior(page, page.locator("#pin-pane"), "bounded")
    page.locator('[data-lf-margin-for="pane-top"] .lf-margin-marker').click()
    card = page.locator(".lf-margin-preview")
    editor = card.get_by_role("textbox", name="Reply", exact=True)
    editor.click()
    rendered(page)
    before = page.evaluate(CARD_AND_REPLY)

    def stays():
        after = page.evaluate(CARD_AND_REPLY)
        for edge in ("cardTop", "turn", "editorTop"):
            assert after[edge] == pytest.approx(before[edge], abs=0.5), (before, after)

    if route == "paste":
        page.keyboard.insert_text(
            "\n".join(f"Line {n}: Keep the export per tenant." for n in range(40))
        )
        rendered(page)
        stays()
    else:
        # Each line goes in as one input, so the draft grows a line at a time without
        # paying for a key per character.
        for n in range(40):
            page.keyboard.insert_text(f"Line {n}: Keep the export per tenant.")
            if n < 39:
                editor.press("Shift+Enter")
            rendered(page)
            stays()
    assert editor.evaluate("box => box.scrollHeight > box.clientHeight")
    caret = _focused_editor_caret(page)
    assert caret["selection"] == caret["length"], caret
    assert caret["caretTop"] >= caret["boxTop"], caret
    assert caret["caretBottom"] <= caret["boxBottom"], caret
    page.keyboard.type(" End")
    rendered(page)
    stays()
    caret = _focused_editor_caret(page)
    assert caret["selection"] == caret["length"], caret
    assert caret["caretTop"] >= caret["boxTop"], caret
    assert caret["caretBottom"] <= caret["boxBottom"], caret
