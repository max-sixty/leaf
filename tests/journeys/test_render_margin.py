"""The document's shared, semantic margin map."""

import re

import pytest
from click.testing import CliRunner
from interact_support import (
    append_carried_log_record,
)
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import render_checks as render_checks_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import (
    ASK_PAGE,
)
from render_cases_layout import (
    banner_control,
)
from render_cases_navigation import (
    go_to_address,
)
from render_harness import (
    LONG_PAGE,
    RELEASE_FOCUS,
    draft_control,
    margins_laid_out,
    navigate,
    open_page,
    pane_posture,
    panel_settled,
    resized,
    sending,
    ticked,
    told,
    write,
)

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_margin import (
    ACTION_ON_ASK,
    ASK_IN_LONG_PAGE,
    CARD_AND_REPLY,
    COMMENT_ON_ASK,
    DRAFTING_CARD,
    LONG_THREAD_ROOT,
    MARGIN_ACTIONS_EVENTS,
    MARGIN_ACTIONS_PAGE,
    MARGIN_EDITOR_ROOTS,
    PANE_PIN_PAGE,
    SUGGESTION_PINS,
    THREAD_CARD_GEOMETRY,
    THREAD_CARD_PAGE,
    WORDS_RIGHT,
    _comment_on,
    _focused_editor_caret,
    _open_thread,
    _seed_card_threads,
    _unfold,
    _unfold_suggestion_undo,
    drafting_in_a_short_card,
    open_long_thread,
    resized_shell,
    seeded_thread,
    send_anchored_comment,
)


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


# The rail and the narrowest pin; 700's pin takes the same Page Map route.
@pytest.mark.parametrize("width", [1440, 390])
def test_draft_and_page_map_reaction_actions_stay_reachable(browser, serve, width):
    """A draft's local Save and Cancel stay reachable while it is edited, and the save outlasts
    a reload; the Remove control of a reaction in force is reachable from the Page Map by keyboard
    and withdraws the reaction."""
    page = open_page(browser, serve(MARGIN_ACTIONS_PAGE, events=MARGIN_ACTIONS_EVENTS))
    resized(page, width, 900)
    draft_control(page, "edit", "d-draft").click()
    editor = page.locator("#d-draft leaf-text")
    body = "The workshop moved outdoors.\nBring a folding chair."
    write(editor, body)
    page.locator("#editing-guide").click()
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
    remove = dialog.get_by_role("button", name="Remove prioritize reaction", exact=True)
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


def test_margin_target_hover_requires_pointer_movement(browser, serve):
    """Page motion under a parked pointer cannot take ownership from the keyboard."""
    page = open_page(browser, serve(ASK_IN_LONG_PAGE))
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
        "the pointer starts inside the Ask margin host"
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
          const bottomChrome = [...document.querySelectorAll(
              '.lf-shortcut-bar, .lf-bottom-status')]
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
                    .getPropertyValue('--thread-card')),
                  bannerBottom: rect(document.querySelector('.lf-banner')).bottom};
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
    assert geometry["targetTop"] >= geometry["bannerBottom"], geometry
    assert geometry["targetBottom"] <= 900, geometry

    # The card's top edge stands a gap over its words' first line while the whole card
    # fits under it, as the comment box's does (comment-placement.js), and it holds at
    # the boundary's foot once the words scroll lower than that. Each scroll is read
    # after the frame the scroll listener places the card in.
    moved = page.evaluate(
        """async () => {
          const positions = () => {
            const card = document.querySelector('.lf-margin-preview').getBoundingClientRect();
            const foot = Math.min(...[...document.querySelectorAll(
              '.lf-shortcut-bar, .lf-bottom-status')].filter(node => node.checkVisibility())
              .map(node => node.getBoundingClientRect().top));
            return {
              card: card.top, cardBottom: card.bottom, foot,
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
          // Keep the first two positions below the banner's 8px boundary, so
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
            head: document.querySelector('.lf-banner').getBoundingClientRect().bottom,
          };
        }"""
    )
    assert gone["controls"] < gone["head"], gone
    assert gone["card"] == pytest.approx(gone["controls"], abs=0.5), gone


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


def test_agent_status_leaves_the_margin_transcript_where_the_user_scrolled_it(
    browser, serve
):
    """A state read places the card, and placing the card moves nothing inside it.

    The user stands in the reply while reading partway up the transcript, then at its
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
            ("working", ["task", "start", str(serve.page_dir), "c" * 32, "Reading"]),
            ("waiting", ["status", str(serve.page_dir), "waiting"]),
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


def test_standing_on_a_commented_element_opens_its_thread_in_threads(browser, serve):
    """With Threads open, the panel's one expanded thread is the element's card.

    Arriving at a commented element by keyboard expands that element's thread in the
    list, brings it into the list's view, and leaves the user on the element, with no
    margin card beside it. A thread of that element already expanded is where the user
    is on it, perhaps mid-reply, so it stays. A pointer that lands on an element asked
    for nothing there, and the list stays as it is.
    """
    page = open_page(browser, serve(ASK_PAGE))
    resized(page, 1440, 380)
    first = seeded_thread(page, serve.page_dir, "#mounts-p")
    second = seeded_thread(page, serve.page_dir, "#heater-p")
    third = seeded_thread(page, serve.page_dir, "#mounts-p")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    threads = page.locator(".lf-thread-panel")
    expanded = threads.locator(".lf-thread[open]")
    # Its title whole in the list's view: the thread the list shows is the one it names.
    in_view = """thread => {
      const list = thread.closest('leaf-thread-list').getBoundingClientRect();
      const box = thread.querySelector(':scope > .lf-thread-summary')
        .getBoundingClientRect();
      return box.top >= list.top && box.bottom <= list.bottom;
    }"""

    def card(sent):
        return threads.locator(f'.lf-thread[data-id="{sent["id"]}"]')

    # Keyboard modality without Tab, whose own landing in the list would scroll it. A
    # second arrival leaves the stop the first lent, which a restated value would rewrite.
    def arrive(selector):
        page.keyboard.press("Shift")
        page.locator(selector).evaluate(
            "node => { if (node.getAttribute('tabindex') !== '-1') node.tabIndex = -1;"
            " node.focus(); }"
        )
        expect(page.locator(selector)).to_be_focused()
        assert page.locator(selector).evaluate("node => node.matches(':focus-visible')")

    for passage, sent in (("#heater-p", second), ("#mounts-p", first)):
        # Out of the list's view first, so the arrival has to bring it back.
        card(sent).evaluate(
            """thread => {
              const list = thread.closest('leaf-thread-list');
              list.scrollTop = thread.offsetTop > list.scrollHeight / 2
                ? 0 : list.scrollHeight;
            }"""
        )
        assert not card(sent).evaluate(in_view)
        arrive(passage)
        expect(expanded).to_have_attribute("data-id", sent["id"])
        expect(page.locator(passage)).to_be_focused()
        expect(page.locator(".lf-margin-preview")).to_be_hidden()
        page.wait_for_function(
            f"() => ({in_view})(document.querySelector("
            f"'.lf-thread-panel .lf-thread[data-id=\"{sent['id']}\"]'))"
        )

    # The user opens the element's other thread; arriving back at the element keeps it.
    card(third).locator(":scope > .lf-thread-summary").click()
    expect(expanded).to_have_attribute("data-id", third["id"])
    arrive("#mounts-p")
    expect(expanded).to_have_attribute("data-id", third["id"])

    # A pointer on the other element focuses it without keyboard arrival.
    page.locator("#heater-p").click()
    expect(page.locator("#heater-p")).to_be_focused()
    assert not page.locator("#heater-p").evaluate(
        "node => node.matches(':focus-visible')"
    )
    expect(expanded).to_have_attribute("data-id", third["id"])


@pytest.mark.parametrize("wrapping", [False, True])
def test_an_inline_thread_keeps_one_readable_card_across_page_claims(
    browser, serve, wrapping
):
    """An accepted comment preserves its editor frame, wrapping and reply, using
    the marker strip where clearing it would narrow the message."""
    sidebar_page = ASK_PAGE.replace(
        '<main class="layout-column">',
        '<main class="layout-column"><aside class="sidebar">Page reference</aside>',
        1,
    )
    page = open_page(
        browser,
        serve(sidebar_page, events=[COMMENT_ON_ASK]),
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
        serve(ASK_PAGE, events=[COMMENT_ON_ASK]),
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
    After that the editor scrolls internally, keeping the card and its first line still."""
    page = open_page(browser, serve(ASK_PAGE, events=[COMMENT_ON_ASK]))
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

    # A draft with no room left under the card scrolls inside its editor, holding
    # the card and the editor's top where the user began writing.
    write(editor, "\n".join(f"Line {n}" for n in range(60)))
    rendered(page)
    tall = page.evaluate(CARD_AND_REPLY)
    assert tall["cardBottom"] == pytest.approx(tall["foot"], abs=1), tall
    for edge in ("cardTop", "turn", "editorTop"):
        assert tall[edge] == pytest.approx(before[edge], abs=0.5), (before, tall)
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
    reaches the window's foot, then the editor takes room upward and scrolls within it."""
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
    assert bounded["turn"] < bounded["editorTop"] < after["editorTop"], bounded
    assert bounded["editorBottom"] <= bounded["cardBottom"], bounded
    assert bounded["editorTop"] <= bounded["send"] <= bounded["cardBottom"], bounded
    assert editor.evaluate("box => box.scrollHeight > box.clientHeight")
    expect(editor).to_be_focused()


def test_the_thread_card_survives_drawers_and_authored_sidebars(browser, serve):
    """The Questions panel or an authored sidebar does not turn the contextual card into
    the Threads panel. The Questions panel stands on the right edge, over the rail at a
    desk's width, so the window is wide enough to leave the marker clear of it."""
    page = open_page(browser, serve(ASK_PAGE, events=[ACTION_ON_ASK, COMMENT_ON_ASK]))
    resized(page, 2100, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.click()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)

    banner_control(page, ".lf-queue").click()
    expect(page.locator("body")).to_have_attribute("data-lf-auxiliary-surface", "queue")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    marker.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
    marker.click()
    banner_control(page, ".lf-queue").click()
    expect(page.locator("body")).not_to_have_attribute(
        "data-lf-auxiliary-surface", "queue"
    )
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    marker.click()
    expect(page.locator(".lf-margin-thread")).to_have_count(1)
    expect(page.locator(".lf-margin-preview")).to_be_visible()

    page.close()

    sidebar_page = ASK_PAGE.replace(
        '<main class="layout-column">',
        '<main class="layout-column"><aside class="sidebar">Page reference</aside>',
        1,
    )
    page = open_page(
        browser,
        serve(sidebar_page, events=[ACTION_ON_ASK, COMMENT_ON_ASK]),
    )
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.click()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-thread-panel")).to_be_hidden()
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
    pane_posture(page, page.locator("#pin-pane"), "bounded")
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
