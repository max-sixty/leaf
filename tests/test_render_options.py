"""Options, specimens, and decision presentation tests."""

import io
import json
import math
import re

import pytest
from click.testing import CliRunner
from interact_support import append_command
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import schema as schema_model
from leaf import service as service_model
from leaf import session as session_model
from leaf.render_gate import version as render_gate_model
from playwright.sync_api import expect
from render_support import (
    ASK_PAGE,
    ASK_SHAPES_PAGE,
    ASK_WITH_CONTEXT_PAGE,
    CARRIED_PAGE,
    CHIP_PAGE,
    EXAMPLES,
    EXHIBIT_EXTENT,
    INLINE_CASE_PAGE,
    NESTED_ASK_PAGE,
    PAINTED_PAGE,
    REPLAYED_PAGE,
    REPLY_HOST_PAGE,
    SETTLED_ASK_PAGE,
    SETTLED_PAGE,
    SPECIMEN_EXAMPLES,
    SPECIMEN_MARKUP,
    SPECIMEN_PAGE,
    SPECIMEN_TEXT,
    STACKED_OPTIONS_PAGE,
    TABLE_REPLY,
    TWICE_PAGE,
    _traffic,
    _until,
    compare_with,
    flip_point,
    hold_selection,
    holding,
    key_line,
    leaf_page,
    live_url,
    open_page,
    resized,
    round_trip,
    sent_events,
    stamp_page,
    stamp_version_file,
    told,
    wait_for_revision,
)

pytestmark = pytest.mark.nightly


def test_the_runtime_does_not_replace_a_pages_keyframes(browser, serve):
    """Keyframe names ignore @scope, so the runtime's private animation must be
    globally unique enough to leave a page's own animation alone. The page coins the
    old generic name on purpose; sampling its midpoint makes a collision deterministic
    rather than asking where a running animation happened to be when the test looked."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "t",
                '<h1>t</h1><p id="page-pulse">Page-owned motion.</p>',
                head="<style>"
                "@keyframes lf-pulse { from { transform: translateX(0px); } "
                "to { transform: translateX(40px); } }"
                "#page-pulse { animation: lf-pulse 10s linear infinite; }"
                "</style>",
            )
        ),
    )
    sampled = page.evaluate("""() => {
        const pageAnimation = document.getElementById("page-pulse").getAnimations()[0];
        pageAnimation.pause();
        pageAnimation.currentTime = pageAnimation.effect.getTiming().duration / 2;
        const transform = getComputedStyle(document.getElementById("page-pulse")).transform;

        const dot = document.querySelector(".lf-dot");
        dot.classList.add("working");
        const runtimeAnimation = dot.getAnimations()[0];
        return {
            pageDistance: transform === "none" ? null : new DOMMatrix(transform).m41,
            runtimeName: runtimeAnimation?.animationName ?? null,
        };
    }""")
    assert sampled["pageDistance"] == pytest.approx(20), (
        f"the runtime replaced the page's lf-pulse keyframes: {sampled}"
    )
    assert sampled["runtimeName"] and sampled["runtimeName"] != "lf-pulse", (
        f"the chrome lost its own private pulse animation: {sampled}"
    )
    assert errors == []
    page.close()


def test_substantial_options_stack_and_align_their_facts(browser, serve):
    """A titled option is a full-width card and the cards stack, terse or
    substantial alike. The grid this replaced laid terse options across at
    ~13rem, and its geometry moved with the count — a fourth option orphaned
    under the first row, every cell as tall as the row's longest argument —
    where a page whose options held real argument grew a comparison table and
    an "in detail" section outside the widget it decides in. Stacked, the
    comparison stays inside the group: every option's `.facts` list docks right
    at one fixed width, so scalars align down the page like that table's column.

    The chip band is the one part no form places, and the reason is that its words
    are the author's: an attribute pair the theme knew the names of could be
    pinned to two corners and reserved room for, and `chips` can be any length at
    all. So it goes in flow ahead of the title, where a card gives it the width it
    has and it wraps inside that rather than over the card's edge."""
    page, errors = open_page(browser, serve(STACKED_OPTIONS_PAGE))
    assert errors == []

    sd = page.locator("#st-sd").bounding_box()
    pi = page.locator("#st-pi").bounding_box()
    group = page.locator("#stacked").bounding_box()
    assert sd["y"] + sd["height"] <= pi["y"], "substantial options must stack"
    assert sd["width"] > group["width"] * 0.95, (
        "a stacked option takes the whole column"
    )

    rails = [
        page.locator(f"#{i} > dl.facts").bounding_box() for i in ("st-sd", "st-pi")
    ]
    for rail, card in zip(rails, (sd, pi)):
        assert rail["x"] > card["x"] + card["width"] / 2, "the facts rail docks right"
    assert abs(rails[0]["x"] - rails[1]["x"]) < 1, "rails align down the group"

    title = page.locator("#st-sd > strong").bounding_box()
    chips = page.locator("#st-sd > lf-chip")
    expect(chips).to_have_text(["effort: low", "risk: high"])
    # `tone` is the author's judgement about one answer, so it lands on the chip that
    # declares it and nowhere else — the arrangement this replaced tinted whichever chip
    # happened to be called risk, which is the theme holding an opinion about a word.
    tints = chips.evaluate_all(
        "els => els.map(el => getComputedStyle(el).backgroundColor)"
    )
    wanted = page.evaluate(
        """() => ['--chip', '--danger-tint'].map(name => {
            const probe = document.createElement('div');
            probe.style.backgroundColor = `var(${name})`;
            document.body.append(probe);
            const paint = getComputedStyle(probe).backgroundColor;
            probe.remove();
            return paint;
        })"""
    )
    assert tints == wanted, (
        f"an untoned chip is neutral and a toned one takes the theme's own tint: "
        f"{tints} vs {wanted}"
    )
    band = [chips.nth(i).bounding_box() for i in range(2)]
    for chip in band:
        assert chip["y"] + chip["height"] <= title["y"] + 1, (
            "the chips read before the title"
        )
    assert abs(band[0]["x"] - title["x"]) < 1, "and start where the title does"
    assert band[0]["x"] + band[0]["width"] <= band[1]["x"], (
        "in the author's order, not overlapping"
    )

    paper = page.locator("#t-paper").bounding_box()
    gps = page.locator("#t-gps").bounding_box()
    terse = page.locator("#terse").bounding_box()
    assert paper["y"] + paper["height"] <= gps["y"], "terse options stack too"
    assert gps["width"] > terse["width"] * 0.95, "a terse card takes the whole column"

    # lf-compare is the same shape without the decision, and follows it for block
    # content; an exhibition is looked across, so its terse form keeps the grid.
    cedar = page.locator("#cv-cedar").bounding_box()
    pine = page.locator("#cv-pine").bounding_box()
    assert cedar["y"] + cedar["height"] <= pine["y"], "substantial variants stack too"
    rail = page.locator("#cv-cedar > dl.facts").bounding_box()
    assert rail["x"] > cedar["x"] + cedar["width"] / 2, "a variant's facts dock right"
    oiled = page.locator("#cv-oiled").bounding_box()
    bare = page.locator("#cv-bare").bounding_box()
    assert abs(oiled["y"] - bare["y"]) < 1, "terse variants keep the side-by-side grid"
    assert oiled["x"] + oiled["width"] <= bare["x"], "terse variants share the row"

    # Crowd the generated selection state's opening band at phone width. Its room is
    # held before the pick and excludes every line rather than hanging off whichever
    # chip comes last, so wrapping metadata cannot enter the pill's corner.
    page.set_viewport_size({"width": 390, "height": 900})
    page.locator("#st-sd > strong").evaluate(
        """title => {
            for (const text of ['recommended', 'owner: platform', 'phase: design']) {
                const chip = document.createElement('lf-chip');
                chip.textContent = text;
                title.before(chip);
            }
        }"""
    )
    card_before = page.locator("#st-sd").bounding_box()
    page.locator("#st-sd").click()
    state = page.locator("#st-sd > .lf-pick")
    expect(state).to_have_text("selected")
    assert page.locator("#st-sd").bounding_box() == card_before
    state_box = state.bounding_box()
    for chip in [chips.nth(i).bounding_box() for i in range(5)]:
        separate = (
            chip["x"] + chip["width"] <= state_box["x"]
            or state_box["x"] + state_box["width"] <= chip["x"]
            or chip["y"] + chip["height"] <= state_box["y"]
            or state_box["y"] + state_box["height"] <= chip["y"]
        )
        assert separate, "the selected header state covers an authored chip"

    # More chips than fit on a line wrap along the band rather than over the card's edge.
    # The pair this replaced could not: each was an absolutely-positioned box sized to
    # room the theme had reserved by knowing both words in advance. A full-width card
    # outgrows the band at the desktop column, so the narrow window is where the wrap
    # is still reachable. Last, because the width moves every box read above.
    page.set_viewport_size({"width": 400, "height": 900})
    gps = page.locator("#t-gps").bounding_box()
    long_chips = page.locator("#t-gps > lf-chip")
    expect(long_chips).to_have_count(3)
    wrapped = [long_chips.nth(i).bounding_box() for i in range(3)]
    assert wrapped[-1]["y"] > wrapped[0]["y"], (
        "a band too wide for its card takes a second line"
    )
    for chip in wrapped:
        assert chip["x"] + chip["width"] <= gps["x"] + gps["width"], (
            "no chip the author wrote may cross the card's edge"
        )
    page.close()


def test_a_terse_variant_is_the_height_of_its_own_words(browser, serve):
    """A group of five comes out three across and two under them, so the last row has
    room to spare. A cell may not take its height from that row: stretch is the grid's
    default and it drew a one-sentence variant as tall as the six-line one beside it,
    190px of blank under a single line, which reads as a card whose words never arrived.

    The widths are the other half of the same reading, because the room stays only while
    nothing grows into it — a wrapped flex line and a column count read off the child
    count both give the last row a cell width the first row hasn't got.

    So the two are measured against each other, and each row's own tallest is asserted
    first: two cells of one height prove nothing about stretch unless something in their
    rows was taller."""
    page, errors = open_page(browser, serve(STACKED_OPTIONS_PAGE))
    assert errors == []
    boxes = {
        name: page.locator(f"#{name}").bounding_box()
        for name in ("cv-oak", "cv-ash", "cv-elm", "cv-yew", "cv-fir")
    }
    rows = {}
    for name, box in boxes.items():
        rows.setdefault(round(box["y"]), []).append(name)
    assert [len(row) for row in rows.values()] == [
        3,
        2,
    ], f"five terse variants come out three across at this width: {rows}"
    widths = [box["width"] for box in boxes.values()]
    assert max(widths) - min(widths) < 1, (
        f"a cell is one width whichever row it falls on: {widths}"
    )
    tall, short = boxes["cv-ash"]["height"], boxes["cv-oak"]["height"]
    assert tall > short + 60, (
        f"cv-oak says one word and cv-ash six lines, so nothing but the row can be "
        f"setting a height they share: {short} vs {tall}"
    )
    assert boxes["cv-fir"]["height"] > boxes["cv-yew"]["height"] + 10, (
        "the second row the same, cv-fir taking two lines to cv-yew's one"
    )
    for name in ("cv-elm", "cv-yew"):
        assert abs(boxes[name]["height"] - short) < 1, (
            f"{name} says as much as cv-oak and is the same box: "
            f"{boxes[name]['height']} vs {short}"
        )
    page.close()


def test_a_row_too_narrow_to_dock_a_rail_stacks_it_instead(browser, serve):
    """The rail is a comparison column, and it is worth its 10rem only while what it
    stands beside is still an argument. Out of a row narrower than about 30rem it is not:
    the case gets three or four words to the line and the row reads as a rail with some
    text jammed down its left. So the row is asked, and not the window — how much width a
    row has is a fact about the row, and a page gives 168px up to the margin the
    moment it carries a change to decide, which no viewport query knows about."""
    page = browser.new_page(
        viewport={"width": 460, "height": 900}, color_scheme="light"
    )
    page.goto(serve(STACKED_OPTIONS_PAGE), wait_until="load")
    rail = page.locator("#st-sd > dl.facts").bounding_box()
    prose = page.locator("#st-sd > p").bounding_box()
    card = page.locator("#st-sd").bounding_box()
    assert rail["width"] > card["width"] * 0.8, (
        "the rail still docks in a row this narrow"
    )
    assert rail["y"] + rail["height"] <= prose["y"], "the case has to clear the rail"
    page.close()


def test_a_pick_the_page_only_reports_can_still_be_pointed_at(browser, serve):
    """An authored pick without a live control is a check with an accessible name.

    The selected state does not introduce a visible status caption or new page words,
    and the generated fallback remains outside the diff's authored-text reading.
    """
    url = serve(CARRIED_PAGE)
    assert render_gate_model.render_version(browser, url) == []

    page, errors = open_page(browser, live_url(url))
    mark = page.locator("#c-lax .lf-pick")
    assert mark.get_attribute("role") == "img"
    assert mark.get_attribute("aria-label") == "selected: Lax cookie"
    assert mark.evaluate("el => getComputedStyle(el).fontSize") == "0px"
    assert mark.evaluate("el => getComputedStyle(el, '::before').content") == '"✓"'

    # The generated check is not authored text, so rewording another option marks only
    # that option in the version comparison.
    d = serve.page_dir
    (d / ".fixture-versions" / "v2.html").write_text(
        CARRIED_PAGE.replace("Suits the mobile client", "Suits the mobile client best")
    )
    stamp_version_file(d, 2, "two")
    wait_for_revision(page, 2)
    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map(e => e.id)"
    ) == ["c-bearer"], "the diff read the mark as text the base version lacked"
    assert errors == []
    page.close()


def test_a_live_card_pick_uses_header_state_and_remains_pressable(browser, serve):
    """A completed Ask keeps the same live-card state when reopened for review."""
    page, errors = open_page(browser, live_url(serve(SETTLED_PAGE)))
    page.locator("#transport .lf-settled").click()
    mark = page.locator("#opt-lax .lf-pick")
    assert mark.get_attribute("aria-checked") == "true"
    assert mark.get_attribute("aria-label") == "selected: Lax cookie — option 1 of 3"
    assert mark.evaluate("el => getComputedStyle(el).fontSize") != "0px"
    expect(mark).to_have_text("selected")
    assert mark.evaluate("el => getComputedStyle(el, '::before').content") == '"✓"'

    strict = page.locator("#opt-strict")
    size = "el => [Math.round(el.getBoundingClientRect().width), Math.round(el.getBoundingClientRect().height)]"
    before = strict.evaluate(size)
    strict.click()
    expect(strict).to_have_attribute("chosen", "")
    assert strict.evaluate(size) == before

    page.locator("#opt-bearer .lf-pick").focus()
    page.keyboard.press(" ")
    expect(page.locator("#opt-bearer")).to_have_attribute("chosen", "")
    round_trip(page)
    assert errors == []
    page.close()


def test_a_selected_question_keeps_one_action_context_while_tab_reaches_its_field(
    browser, serve
):
    """The Ask owns its numbered actions wherever focus stands inside it.

    Tab traverses the real controls without replacing that action map. Another option is
    a shared text box rather than an action hidden behind Enter on an option mark.
    """
    url = serve(ASK_WITH_CONTEXT_PAGE)
    page, errors = open_page(browser, url)

    page.keyboard.press("a")
    mark = page.locator("#storage-evict .lf-pick")
    line = key_line(page)
    assert "Drop the oldest documents / Pause offline editing" in line, line
    option_hints = page.locator("#storage-options > lf-option > .lf-address")
    expect(option_hints).to_have_text(["1", "2"])
    expect(option_hints.first).to_be_visible()
    write_hint = page.locator("#storage-options > .lf-another > .lf-address")
    box = page.locator("#storage-options > .lf-another textarea")
    expect(write_hint).to_have_count(0)

    # Enter has no invented meaning on the Ask or an option mark. Tab enters the real
    # controls, while the same Ask-owned numbers and addresses remain standing there.
    page.keyboard.press("Enter")
    expect(page.locator("#storage-decision")).to_be_focused()
    page.keyboard.press("Tab")
    expect(mark).to_be_focused()
    expect(mark).to_have_attribute("role", "checkbox")
    expect(mark).to_have_attribute("aria-checked", "false")
    expect(
        page.locator("#storage-options > lf-option > .lf-address[data-lf-ask-address]")
    ).to_have_text(["1", "2"])
    assert key_line(page) == line
    page.keyboard.press("Enter")
    expect(mark).to_be_focused()
    expect(box).not_to_be_focused()
    expect(page.locator("#storage-options > lf-option[chosen]")).to_have_count(0)

    # The controls remain in document order: the other mark, then the text box. It keeps
    # native newlines on both forms of Enter and exposes the shared submit chord.
    page.keyboard.press("Tab")
    expect(page.locator("#storage-stop .lf-pick")).to_be_focused()
    page.keyboard.press("Tab")
    expect(box).to_be_focused()
    box.fill("Keep both layers")
    page.keyboard.press("Enter")
    page.keyboard.type("Keep them together")
    page.keyboard.press("Shift+Enter")
    page.keyboard.type("Preserve both histories")
    expect(box).to_have_value(
        "Keep both layers\nKeep them together\nPreserve both histories"
    )
    expect(box).to_have_attribute("aria-keyshortcuts", "Meta+Enter Control+Enter")
    expect(page.locator("#storage-options > lf-option[data-lf-added]")).to_have_count(0)
    assert "add option" in key_line(page)
    page.keyboard.press("ControlOrMeta+Enter")
    added = page.locator("#storage-options > lf-option[data-lf-added]")
    expect(added).to_contain_text("Keep both layers")
    expect(added).to_have_css("white-space", "pre-wrap")
    assert errors == []
    page.close()

    page, errors = open_page(browser, serve(ASK_WITH_CONTEXT_PAGE))
    page.keyboard.press("a")
    page.keyboard.press("Tab")
    mark = page.locator("#storage-evict .lf-pick")
    expect(mark).to_be_focused()
    page.keyboard.press("2")
    expect(page.locator("#storage-stop")).to_have_attribute("chosen", "")
    chosen = page.locator("#storage-stop .lf-pick")
    # The digit acts within the Ask without turning address selection into focus
    # navigation; the reader remains on the control they tabbed to.
    expect(mark).to_be_focused()
    expect(chosen).to_have_attribute("role", "checkbox")
    expect(chosen).to_have_attribute("aria-checked", "true")
    expect(page.locator("#storage-options > .lf-another textarea")).not_to_be_focused()
    assert errors == []
    page.close()

    # Native focus scrolling reads the fixed key line as part of the root scrollport's
    # unavailable foot. At phone width the field otherwise lands underneath that line:
    # geometrically in the viewport, but neither visible nor operable as the next stop.
    page, errors = open_page(browser, serve(ASK_WITH_CONTEXT_PAGE))
    resized(page, 390, 844)
    page.keyboard.press("a")
    for _ in range(3):
        page.keyboard.press("Tab")
    box = page.locator("#storage-options > .lf-another textarea")
    expect(box).to_be_focused()
    clearance = page.evaluate(
        """() => document.querySelector('.lf-keyline').getBoundingClientRect().top
          - document.querySelector('#storage-options > .lf-another')
            .getBoundingClientRect().bottom"""
    )
    assert clearance >= 20, f"the key line covers the add field by {-clearance}px"
    assert errors == []
    page.close()


def test_a_card_group_taking_a_pick_reads_as_one_control(browser, serve):
    """The offer is the group's, made once, rather than a word written on every member.

    A card group under `choose` draws the border and its options become cells inside it,
    sharing hairlines: a set of alternatives at one size is what says a decision is
    waiting. Each card's generated mark stands in the state slot at its opening edge
    as an empty ring — the same slot the pick turns it into a compact header state
    in — because a reader who has not hovered sees none of the frame's other
    promises: a blind drive read three cards, found nothing that looked like a
    control, and chose only after a hover happened to shade one. Selection also
    keeps the quiet cell tint.

    Pinned because the rules making the group one control are ranked against the ones
    making each option a card, and losing that race leaves a page that looks exactly as it
    did while saying nothing about being answerable — which reads as a feature nobody
    wired up rather than as a fault. The header state is measured before and after the
    pick because an absolute badge without reserved room can cover authored chips, and a
    badge whose room appears only once chosen moves the argument under the pointer."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    edge = """el => { const s = getComputedStyle(el);
                      return s.borderTopStyle === 'none' ? 0 : parseFloat(s.borderTopWidth); }"""
    assert page.locator("#approach").evaluate(edge) > 0, (
        "the group draws no edge of its own, so nothing says the set is one thing"
    )
    assert page.locator("#opt-shim").evaluate(edge) == 0, (
        "an option still draws its own border, so the group reads as cards standing apart"
    )
    # The hairline belongs to the upper neighbour, so a child that floats inside the
    # group on a margin of its own — the thread question's Done press — is never
    # handed a recolored top edge.
    below = """el => { const s = getComputedStyle(el);
                       return s.borderBottomStyle === 'none' ? 0 : parseFloat(s.borderBottomWidth); }"""
    assert page.locator("#opt-shim").evaluate(below) == 1, (
        "the cells share no hairline, so the set reads as one box rather than as cells"
    )
    # The group's last child is the cell the module appends for the reader's own
    # option, so the last authored option still draws its line — against that cell,
    # not the group's border.
    assert page.locator("#approach > :last-child").evaluate(below) == 0, (
        "the group's last child draws a line against the group's own border"
    )

    option = page.locator("#opt-shim")
    mark = option.locator(":scope > .lf-pick")
    ring = mark.evaluate(
        """el => { const s = getComputedStyle(el, '::before');
                  const box = el.getBoundingClientRect(), card = el.parentElement.getBoundingClientRect();
                  return {visibility: s.visibility, width: parseFloat(s.width),
                          atOpeningEdge: box.right <= card.right && box.top - card.top < 24}; }"""
    )
    assert ring["visibility"] == "visible" and ring["width"] > 0, (
        f"an untaken card draws no ring: {ring}"
    )
    assert ring["atOpeningEdge"], f"the ring is not in the card's state slot: {ring}"

    # And a reader arriving by keyboard can see the exact row they landed on. The
    # permanent group frame stays put, the Ask's external location band stands
    # down, and one inset ring belongs to the active row. Reached by Tab rather than
    # focus(), because :focus-visible is a fact about how focus arrived.
    # Read as a style rather than a width, because `outline: none` leaves
    # outline-width computing to the initial `medium`: a box drawing no ring at all
    # still reports 3px.
    mark.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    expect(page.locator("#approach-decision[data-lf-ask]")).to_have_count(1)
    ring_on = """el => { const on = el.closest('lf-option');
                      const drawn = (e) => { const s = getComputedStyle(e);
                          return s.outlineStyle === 'none' ? 0 : parseFloat(s.outlineWidth); };
                          return [on.id, on.matches(':has(> .lf-pick:focus-visible)'),
                                  drawn(on.closest('lf-ask')), drawn(on), drawn(el),
                              getComputedStyle(on).backgroundColor
                                !== getComputedStyle(on.nextElementSibling).backgroundColor]; }"""
    on, held, decision_ring, card_ring, mark_ring, washed = mark.evaluate(ring_on)
    assert (on, held) == (
        "opt-shim",
        True,
    ), f"Tab did not land on the mark: {on} {held}"
    assert decision_ring == 0 and card_ring > 0 and mark_ring == 0, (
        f"the focus ring is on the wrong box: decision {decision_ring}, card {card_ring}, "
        f"mark {mark_ring}"
    )
    assert washed, "nothing says which cell the keyboard is on"
    address = option.locator(":scope > .lf-address")
    expect(address).to_be_visible()
    assert mark.evaluate("el => getComputedStyle(el).opacity") == "0"
    assert (
        abs(
            address.bounding_box()["x"]
            + address.bounding_box()["width"]
            - mark.bounding_box()["x"]
            - mark.bounding_box()["width"]
        )
        < 0.5
    ), "the keyboard address does not replace the card's header state slot"

    page.evaluate("() => document.activeElement.blur()")
    before = option.bounding_box()
    option.click()
    expect(mark).to_have_text("selected")
    assert mark.evaluate("el => getComputedStyle(el).fontSize") != "0px"
    assert option.bounding_box() == before, "the selected header state resized its card"

    state = mark.bounding_box()
    title_end = option.locator(":scope > strong").evaluate(
        """el => { const range = document.createRange();
                    range.selectNodeContents(el);
                    return Math.max(...[...range.getClientRects()].map(r => r.right)); }"""
    )
    assert state["x"] >= title_end, "the generated header state covers the option title"
    assert state["x"] + state["width"] <= before["x"] + before["width"], (
        "the generated header state hangs outside the card"
    )

    # The copy medium: scripts are dropped, so the pick cannot be made and the group must
    # not go on saying one is waiting. The cards come apart and their rings come back, which
    # is the same page paper gets, and both get it by never being handed the offer.
    page.evaluate("() => document.documentElement.classList.add('lf-copy')")
    assert page.locator("#approach").evaluate(edge) == 0, (
        "a copy still draws the group as a control it has no way to work"
    )
    assert page.locator("#opt-stage").evaluate(edge) > 0, (
        "the cards did not come back apart in a copy"
    )
    assert (
        page.locator("#opt-shim").evaluate(
            "el => getComputedStyle(el, '::after').content"
        )
        == '"✓"'
    )
    assert errors == []
    page.close()


@pytest.mark.parametrize(
    ("ask", "group", "question"),
    [
        ("cards-decision", "cards", "Where should a session live?"),
        ("rows-decision", "rows", "Which jobs are worth starting?"),
        ("done-decision", "done", "How do parallel sessions merge?"),
    ],
)
def test_an_ask_leads_with_one_authored_heading(browser, serve, ask, group, question):
    """The question is document content above the answers, never generated group chrome."""
    page, errors = open_page(browser, serve(ASK_SHAPES_PAGE))
    heading = page.locator(f"#{ask} > :is(h1, h2, h3, h4, h5, h6)")
    expect(heading).to_have_count(1)
    expect(heading).to_have_text(question)
    expect(page.locator(f"#{group} > [data-lf-said='label']")).to_have_count(0)
    assert heading.evaluate("el => el.getBoundingClientRect().bottom") < page.locator(
        f"#{group}"
    ).evaluate("el => el.getBoundingClientRect().top"), (
        "the answer control stands before its authored question"
    )
    assert errors == []
    page.close()


@pytest.mark.parametrize("group", ["cards", "rows"])
def test_every_cell_of_a_joined_control_butts_and_opens_where_its_neighbours_do(
    browser, serve, group
):
    """Read over every cell, not only the question that sent us looking.

    A group under `choose` is one control: cells sharing edges, divided by a hairline
    instead of a gap. Two things follow for every one of them, and the question was
    simply the child that had neither. The line is the whole of what separates a cell
    from the next, so a margin beside it is a second way to say what the line already
    says and draws a rule floating in a band of nothing. And each cell holds its words
    off the frame at the column the group reserves, so a cell that opens on the frame
    hangs out of the column its own neighbours share.

    Here rather than in the render gate, on the line tests/CLAUDE.md draws: a property
    caused by a particular page belongs to the gate, which must report it to that page's
    author, and one identical for every valid page belongs to the suite. A joined
    control is leaf's own theme — no authored page can make it wrong. A reading in the
    gate had to find the control by fingerprint (a frame, a clip, a stacked pair), and
    that fingerprint is worn by a board column, a framed scroller, an authored row-gap
    and a framed `<details>`, none of which is wrong; it also never saw the same defect
    written as `border-top` on the lower cell. Asked here, of the widget itself, both
    forms are visible and nothing correct is accused.

    Every child, because which kinds a group holds is not this test's to know: the
    authored options are the author's, the option the reader writes is the module's,
    the question and the Done press are the runtime's, and each arrived carrying the
    spacing it wears standing alone."""
    page, errors = open_page(browser, serve(ASK_SHAPES_PAGE))
    cells = page.locator(f"#{group}").evaluate(
        r"""el => {
             const px = (v) => parseFloat(v) || 0;
             const kids = [...el.children].filter((c) => c.checkVisibility());
             return kids.map((c, i) => {
               const s = getComputedStyle(c);
               const r = c.getBoundingClientRect();
               const next = kids[i + 1];
               // The ground the reader sees under the cell, which is not the same as
               // what the cell declares: a cell that paints nothing shows the group's
               // own, and that is how an unpicked option is filled.
               const clear = (v) => !v || v === 'transparent'
                        || /rgba\(0,\s*0,\s*0,\s*0\)/.test(v);
               return {
                 what: c.tagName.toLowerCase() + (c.dataset.lfSaid
                        ? `[${c.dataset.lfSaid}]` : (c.className ? '.' + c.className.trim().split(/\s+/)[0] : '')),
                 opens: px(s.paddingInlineStart) + px(s.borderInlineStartWidth),
                 ground: clear(s.backgroundColor)
                   ? getComputedStyle(el).backgroundColor : s.backgroundColor,
                 picked: c.hasAttribute('chosen'),
                 gap: next
                   ? Math.round((next.getBoundingClientRect().top - r.bottom) * 10) / 10
                   : null,
               };
             });
           }"""
    )
    assert len(cells) > 2, f"a control of {len(cells)} cells proves little: {cells}"

    apart = [c for c in cells if c["gap"] is not None and c["gap"] > 0.5]
    assert not apart, (
        f"cells of #{group} stand apart from the line that joins them: {apart}"
    )

    bare = [c for c in cells if c["opens"] < 0.5]
    assert not bare, (
        f"cells of #{group} open on the frame while their neighbours hold off it: "
        f"{bare}"
    )

    # And they open at one column, which is the half a reader sees first: the question
    # hung a whole address column left of the words it was a question about. Every cell,
    # the reader's own among them: that cell holds the option they write when none of the
    # authored ones is the answer, so a cell drawn short of the column starts the one box
    # the group takes words in outside the run of boxes the group is. Its own 12px did
    # exactly that, and this line excused it as apparatus. What is compared is the cell,
    # not the caret: a text box holds its words off its own frame, which is the box's and
    # no business of the group's.
    words = {c["opens"] for c in cells}
    assert len(words) == 1, (
        f"#{group}'s cells open at {sorted(words)}, so the question, its answers and "
        "the option the reader writes read as more than one column"
    )

    # And the reader's own option is filled the way an option nobody has picked is
    # filled, which is the other half of what says it is one of the answers. A pick
    # colours the cell that holds it and nothing else does, so any other ground here is
    # a state the group hasn't got: the cell wore --field, a tinted band that in this
    # theme means a detail or a note, and a band under the answers is a footer whatever
    # else is written in it.
    open_option = next(
        c["ground"] for c in cells if c["what"] == "lf-option" and not c["picked"]
    )
    reader = next(c for c in cells if "lf-another" in c["what"])
    assert reader["ground"] == open_option, (
        f"#{group}'s reader-written option stands on {reader['ground']} where an "
        f"unpicked option stands on {open_option}, so it reads as apparatus under the "
        "answers rather than as one of them"
    )
    assert errors == []
    page.close()


def test_a_quoted_widget_exhibits_without_taking_input(browser, serve):
    """A specimen is a mention, not a use. The exhibited widgets render at full
    fidelity — that is the whole point of showing one — but wire nothing that
    would carry the reader's edits back, so an example decision can't be
    answered and an example board can't be dragged. The unquoted copies on the
    same page are the control: they prove the affordances are missing because
    the specimen suppressed them, not because the upgrade failed.

    Presentation and view state are not input, so they still run: a quoted
    settled group collapses like any other."""
    page, errors = open_page(browser, serve(SPECIMEN_PAGE))
    assert errors == []
    assert page.locator(".lf-error").count() == 0

    # The exhibit rendered: the gutter's caption, and cards with real size. The label is
    # the page's own word, so the runtime says it as text a user can quote; only the
    # "quoted · " in front of it is the theme's, and only that is still pseudo-content.
    label = page.locator('#spec > [data-lf-said="label"]')
    assert label.text_content() == "a decision"
    assert (
        label.evaluate("el => getComputedStyle(el, '::before').content")
        == '"quoted · "'
    )
    assert page.locator("#quoted-group lf-option").count() == 2
    assert (
        page.locator("#quoted-group lf-option").first.evaluate(
            "el => Math.round(el.getBoundingClientRect().height)"
        )
        > 20
    )

    # …but takes nothing back. Nothing selectable: no grips, and no mark wearing
    # the checkbox role — an unpicked quoted card carries no mark at all, exactly as
    # a group that never declared `choose`. A click chooses nothing either (the
    # choose path sets `chosen` before it sends, so a pick would show here).
    assert page.locator('#quoted-group .lf-pick[role="checkbox"]').count() == 0
    assert page.locator("#quoted-board .lf-grip").count() == 0
    # Nor a cell to write another option in: an exhibited question takes no answer of
    # either kind, and a box is the one that would have looked answerable.
    assert page.locator("#quoted-group .lf-another").count() == 0
    page.locator("#q-shim").click()
    assert page.locator("#quoted-group lf-option[chosen]").count() == 0

    # The document's own state still reads: the settled group's authored pick
    # wears its mark, with nothing to press.
    assert page.locator('#quoted-settled .lf-pick[role="img"]').count() == 1

    # A quoted suggestion shows what a pending change looks like — both slots
    # marked — and grows nothing to settle it with, so it is also not the
    # banner's to count or Accept all's to decide.
    assert page.locator("#quoted-suggestion lf-old").is_visible()
    assert page.locator("[data-lf-for='quoted-suggestion']").count() == 0
    expect(page.get_by_role("button", name="Accept all (1)")).to_be_visible()

    # The control: the same markup unquoted wires all of it.
    assert page.locator('#live-group .lf-pick[role="checkbox"]').count() == 2
    assert page.locator("#live-board .lf-grip").count() == 1
    assert page.locator("[data-lf-for='live-suggestion']").count() == 1

    # Nor the room for one. A quoted card stands at the height of a live titled card:
    # neither carries the old footer strip, and the live card's header state is out of
    # flow. Reserving that strip would leave every exhibit trailing empty space.
    pad = "el => getComputedStyle(el).paddingBottom"
    assert page.locator("#q-shim").evaluate(pad) == page.locator("#l-shim").evaluate(
        pad
    )

    # Nor in paint or live-state layout, which is the theme's own half of the promise
    # rather than the module's. The hand, joined box, and reserved header slot are all
    # withheld by affordance rules excluding what stands inside a painted exhibit
    # (data-lf-exhibit), so a rule that lost its exclusion shows here while every handler
    # stays unwired. The live pair is the control — without it a theme that had stopped
    # drawing the offer at all would read exactly like one that withholds it.
    offer = """el => { const cs = getComputedStyle(el);
        const stateRoom = getComputedStyle(el, '::before');
        return { cursor: cs.cursor, box: cs.borderTopWidth,
                 stateRoom: stateRoom.content === 'none' ? 0 : stateRoom.width }; }"""
    quoted_card, live_card = (
        page.locator(sel).evaluate(offer) for sel in ("#q-shim", "#l-shim")
    )
    frame = "el => getComputedStyle(el).borderTopWidth"
    quoted_box, live_box = (
        page.locator(sel).evaluate(frame) for sel in ("#quoted-group", "#live-group")
    )
    assert live_card["cursor"] == "pointer" and live_box != "0px", (
        "the live group makes no offer either, so the exhibit's missing one says "
        f"nothing: card {live_card}, group {live_box}"
    )
    assert quoted_card["cursor"] != "pointer", (
        f"a quoted card invites the pointer: {quoted_card['cursor']}"
    )
    assert quoted_box == "0px", (
        f"the exhibit is drawn as a control to answer: {quoted_box} border"
    )
    # The live card reserves one header slot for either its chosen state or keyboard
    # address. An exhibit can grow neither, so its title keeps that room.
    assert quoted_card["stateRoom"] == 0 and live_card["stateRoom"] == "80px", (
        "the exhibit reserves the live card's header state slot: "
        f"{quoted_card['stateRoom']} vs {live_card['stateRoom']}"
    )

    # And under the pointer. A live choose group is a joined control, and a cell that rose
    # would pull away from the hairlines holding the group together, so what both forms
    # answer a pointer with here is the joined group's wash — the card's lift belongs to a
    # group that has come apart again, which is the settled pair at the end of this test.
    # Both forms anyway, and the second is not the first repeated: a row has a wash rule of
    # its own with its own exclusion, outranked by the joined group's wherever that one
    # applies, so it is the quoted read that answers for it. Withdraw its exclusion and the
    # quoted row takes --chip where it wore nothing.
    #
    # The live twin goes first, and is both the control and the edge the quoted read is
    # anchored on. Its rest value is read while the pointer is on the other one, and the
    # exhibit's while the pointer is on the live one — an absence has no edge of its own,
    # so each is read across the gesture that would have produced it.
    prop = "background-color"
    css = f"el => getComputedStyle(el).getPropertyValue({prop!r})"
    for quiet, live, form in (
        ("#q-shim", "#l-shim", "card"),
        ("#q-row-keep", "#l-row-keep", "row"),
    ):
        live_rest = page.locator(live).evaluate(css)
        page.locator(live).hover()
        expect(page.locator(live)).not_to_have_css(prop, live_rest)
        quiet_rest = page.locator(quiet).evaluate(css)
        page.locator(quiet).hover()
        expect(page.locator(live)).to_have_css(prop, live_rest)
        assert page.locator(quiet).evaluate(css) == quiet_rest, (
            f"a quoted {form} answers the pointer: "
            f"{page.locator(quiet).evaluate(css)} against {quiet_rest} at rest"
        )

    # View state still runs inside a specimen: the settled group collapsed.
    assert page.locator("#quoted-settled lf-option:visible").count() == 0
    page.locator("#quoted-settled .lf-settled").click()
    assert page.locator("#quoted-settled lf-option:visible").count() == 3

    # The exception, once that group is open: the card the document marks carries its
    # inert check below the prose. It needs the strip a live header state no longer does.
    assert page.locator("#q-lax").evaluate(pad) != page.locator("#l-shim").evaluate(pad)

    # And the lift, which needs both groups open to reach: a settled group comes apart
    # again when the reader opens it, and loose cards answer the pointer by rising where
    # joined cells answer with a wash. Read here rather than with the other two because
    # opening the quoted group is what the lines above are about.
    #
    # Both card states, because the lift has one rule for an ordinary card and another
    # for the one the document records as chosen. Both carry the specimen exclusion.
    page.locator("#live-settled .lf-settled").click()
    # Both folds have to be over before a card's box-shadow means anything. Opening a
    # group brings its rings in on the same transition the lift uses, so a rest value
    # sampled while that runs is the accent part-way to itself — and the later wait for
    # the pointer to have left then waits on a frame that existed once. Asked of the two
    # groups rather than the document, whose own chrome is never quiet for long.
    page.wait_for_function(
        """() => ['#live-settled', '#quoted-settled'].every(
            sel => document.querySelector(sel)
                .getAnimations({subtree: true}).length === 0)"""
    )
    shadow = "el => getComputedStyle(el).boxShadow"
    for quiet, live, card in (
        ("#q-bearer", "#l-bearer", "plain"),
        ("#q-lax", "#l-lax", "chosen"),
    ):
        live_rest = page.locator(live).evaluate(shadow)
        page.locator(live).hover()
        expect(page.locator(live)).not_to_have_css("box-shadow", live_rest)
        quiet_rest = page.locator(quiet).evaluate(shadow)
        page.locator(quiet).hover()
        expect(page.locator(live)).to_have_css("box-shadow", live_rest)
        assert page.locator(quiet).evaluate(shadow) == quiet_rest, (
            f"a quoted {card} card lifts under the pointer: "
            f"{page.locator(quiet).evaluate(shadow)} against {quiet_rest} at rest"
        )
    page.close()


def test_one_band_says_where_the_reader_is_standing(browser, serve):
    """The reader's band is drawn once, on the exact option row being worked.

    The Ask retains its semantic location marker, but its exterior outline would
    look like a second group border and vanish as state changes. The active row carries
    keyboard location instead; the group's permanent frame does not change."""
    page, errors = open_page(browser, serve(ASK_WITH_CONTEXT_PAGE))
    mark = page.locator("#storage-evict .lf-pick")
    mark.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    expect(page.locator("#storage-decision[data-lf-ask]")).to_have_count(1)
    drawn = """el => { const s = getComputedStyle(el);
                       return s.outlineStyle === 'none' ? 0 : parseFloat(s.outlineWidth); }"""
    assert page.locator("#storage-decision").evaluate(drawn) == 0
    group = page.locator("#storage-options")
    assert group.evaluate(
        "el => el.matches(':has(> lf-option > .lf-pick:focus-visible)')"
    ), "the keyboard is not on the group's own mark, so this reads nothing"
    assert group.evaluate(drawn) == 0
    assert page.locator("#storage-evict").evaluate(drawn) > 0, (
        "the focused option row draws no keyboard band"
    )
    assert (
        group.evaluate("el => parseFloat(getComputedStyle(el).borderTopWidth)") > 0
    ), "moving focus removed the group's permanent frame"
    assert errors == []
    page.close()


def test_a_pick_keeps_the_group_frame_visually_stable(browser, serve):
    """Pending state does not become a transient second border around options.

    The projection still carries `data-lf-reader-override`; the selected row's check and tint
    show the choice while the group's permanent frame stays visually unchanged.
    """
    page, errors = open_page(browser, serve(SPECIMEN_PAGE))
    group = page.locator("#live-group")
    frame = "el => [getComputedStyle(el).border, getComputedStyle(el).outlineStyle]"
    before = group.evaluate(frame)
    mark = page.locator("#l-stage .lf-pick")
    mark.click()
    expect(group).to_have_attribute("data-lf-reader-override", "1")
    expect(page.locator("#l-stage")).to_have_attribute("chosen", "")
    assert group.evaluate(frame) == before
    assert errors == []
    page.close()


def test_a_group_of_bare_labels_reads_as_a_question_about_the_page(browser, serve):
    """Which form a group takes is a fact about its options rather than an attribute
    saying so, and the whole of that fact is whether an option leads with a title. So
    one page carries both and neither knows about the other: the labels lay out as
    compact rows and the titled pair as full-width cards stacked down the page.

    Two things the lint cannot see. A resting mark shows no word in either form, because
    an offer states nothing a reader could disagree with. The forms differ in how they
    make that offer visible: a compact row needs its leading mark to declare its target,
    while a titled single-choice card is already one framed, divided, hoverable target
    and keeps the corner quiet until it has state to report. A picked row keeps the
    compact check; a picked card turns the same generated control into a header status.
    (`multiple` keeps boxes in both forms, because that shape is what says several
    answers may stand.) A row's name is
    what the author wrote in it: the mark that lands inside the row once it is picked is
    the page speaking (`says`) and must stay out of the row's own name (`wrote`), or a
    question answered reads its answer back as part of what was asked."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    assert errors == []

    # One row per option in both forms: a single column with no template stated, so
    # the joined control below is a list whatever the options hold. The display is
    # asserted with the track count because "none".split(" ") is also one entry — a
    # group that lost `display: grid` entirely (and the hairline gaps with it) would
    # answer 1 as convincingly as the single-column control does.
    tracks = """el => { const s = getComputedStyle(el);
                        return [s.display, s.gridTemplateColumns.split(' ').length]; }"""
    assert page.locator("#jobs").evaluate(tracks) == ["grid", 1]
    assert page.locator("#bracket").evaluate(tracks) == ["grid", 1]

    # Under `choose` the group is one control in every form, and the list was the form
    # that went without: rows draw no border, no fill and no rule between them, so at
    # rest the only thing that ever drew a row's own box was the hover wash — which
    # arrives after the reader has already had to guess where to aim. The group's edge
    # and the cells' hairlines are what a reader sees before committing the pointer, and
    # they are the same two rules a card group has always had.
    #
    # The hairline is read as the border it is drawn as. It was read off the cell's
    # box-shadow, which is where a row's status stripe rode and not where any line
    # between two rows has ever been: the assertion passed on a transparent stripe and
    # would have passed on a group with no line between its rows at all.
    edge = """el => { const s = getComputedStyle(el);
                      return s.borderTopStyle === 'none' ? 0 : parseFloat(s.borderTopWidth); }"""
    hairline = """el => { const s = getComputedStyle(el);
                          return s.borderBottomStyle === 'none'
                                   ? 0 : parseFloat(s.borderBottomWidth); }"""
    assert page.locator("#jobs").evaluate(edge) > 0, (
        "a list offering a pick draws no edge, so nothing says the rows are answerable"
    )
    assert page.locator("#job-mounts").evaluate(hairline) > 0, (
        "a row draws no box of its own, so its bounds show only under the pointer"
    )
    # And the shape is the offer, so a list that asks nothing wears none of it.
    assert page.locator("#ordered").evaluate(edge) == 0, (
        "a list with no pick to take was drawn as a control anyway"
    )
    assert page.locator("#ord-mounts").evaluate(hairline) == 0, (
        "a row nobody can press draws cell edges anyway"
    )

    # The block a row is about, reachable as a link and written as the id it names —
    # the same way the thread panel writes an element anchor.
    ref = page.locator("#job-mounts .lf-ref")
    expect(ref).to_have_text("§ sec-mounts")
    assert ref.get_attribute("href") == "#sec-mounts"
    assert page.locator("#job-camera .lf-ref").count() == 0

    # No open mark says its word in either form. The compact row draws its target; the
    # titled single-choice card leaves its state slot quiet until picked. The controls
    # still share one accessible contract, while their paint follows the amount of
    # structure their form already supplies.
    hidden = "el => getComputedStyle(el).fontSize"
    dot = "el => getComputedStyle(el, '::before').visibility"
    assert page.locator("#job-mounts .lf-pick").evaluate(hidden) == "0px"
    assert page.locator("#br-steel .lf-pick").evaluate(hidden) == "0px"
    assert page.locator("#job-mounts .lf-pick").evaluate(dot) == "visible"
    assert page.locator("#br-steel .lf-pick").evaluate(dot) == "visible"

    page.locator("#br-steel").click()
    expect(page.locator("#br-steel .lf-pick")).to_have_text("selected")
    assert page.locator("#br-steel .lf-pick").evaluate(hidden) != "0px"

    page.locator("#job-heater").click()
    expect(page.locator("#job-heater[chosen]")).to_have_count(1)
    expect(page.locator("#job-heater .lf-pick")).to_have_text("selected")
    assert page.locator("#job-heater .lf-pick").evaluate(hidden) == "0px"
    # The control's accessible name carries the state and the authored option label;
    # no visible status caption is added to the row.
    assert (
        page.locator("#job-heater .lf-pick").get_attribute("aria-label")
        == "selected: reversible Heat the bird bath — option 2 of 3"
    )
    page.close()


def test_a_group_says_how_many_of_it_the_reader_may_take(browser, serve):
    """How many a group takes is the one thing about it a reader has to know before
    pressing anything, and for a while the page said it nowhere. A `multiple` group drew
    the identical circles a single-pick group draws — the shape every platform uses for
    "one of these" — so the two questions were pixel-for-pixel the same and the only
    thing that distinguished them was the author remembering to say so in prose. A reader
    who took the marks at their word would pick once and expect the next click to replace
    it.

    So the mark carries the arity, in both of the registers one control has: its corner
    is round for one and square for any, and its word is "choose one" or "choose any" for
    a reader who gets no corner. The corner is read as a fraction of the mark's own box,
    because the two are computed in different units (a circle is stated as a percentage of
    a box whose size is stated in px) and the question is the shape rather than either
    number. What is pinned is that they differ and that the single-pick one is a full
    round — a threshold between them would be this design's 3px corner written down a
    second time, free to disagree with it.

    Arity is not the form, which is why the contrast is card against card. `multiple`
    is orthogonal to whether the options are titled, so a titled group asking "which of
    these" still needs empty squares the reader can count. A single-choice titled group
    can leave its radio unpainted because the joined card structure already makes each
    answer a target; the missing circle is therefore a statement about form and arity
    together, not a forgotten selector.

    And the shape is paint inside a box that does not change, so neither arity is a
    pixel wider than the other and every room already reserved still covers."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    corner = """el => { const s = getComputedStyle(el, '::before');
                        const r = s.borderTopLeftRadius;
                        return r.endsWith('%') ? parseFloat(r) / 100
                                               : parseFloat(r) / parseFloat(s.width); }"""
    one = page.locator("#br-steel .lf-pick").evaluate(corner)
    many = page.locator("#tl-clamp .lf-pick").evaluate(corner)
    assert one == 0.5, "a group taking one option draws something other than a circle"
    assert many < one, (
        "a group taking more than one draws the circle that means 'one of these', so "
        "nothing on the page says the reader may take a second"
    )
    # Not the list form's rule wearing a card's clothes: the row group agrees with the
    # card group it shares an arity with, against the card group it shares a form with.
    assert page.locator("#job-mounts .lf-pick").evaluate(corner) == many

    # A card taking several answers keeps every empty square: each is that option's own
    # state and together they say how many remain available. A titled card taking one
    # answer keeps the same semantic control but leaves its circle unpainted at rest; its
    # group frame, divisions, pointer and aim wash already state where the answer can go.
    dot = "el => getComputedStyle(el, '::before').visibility"
    assert page.locator("#tl-clamp .lf-pick").evaluate(dot) == "visible", (
        "a card group asking 'which of these' draws no empty boxes, so the reader has "
        "nothing to count and no sign a second pick is on offer"
    )
    assert page.locator("#br-steel .lf-pick").evaluate(dot) == "visible", (
        "a single-choice titled card hides its empty ring, so a reader who has not "
        "hovered sees nothing on it that looks like a control"
    )

    # Paint, not metrics: the open controls occupy the same header slot in both arities.
    # The single-choice ring is hidden, not removed, so keyboard focus and a later state
    # use the same coordinate without moving the card.
    box = "el => { const b = el.getBoundingClientRect(); return [b.width, b.height]; }"
    assert page.locator("#tl-clamp .lf-pick").evaluate(box) == page.locator(
        "#br-steel .lf-pick"
    ).evaluate(box), "the shape that says arity took room from the option beside it"

    # The same statement for a reader who gets no shape. A corner is paint, so all a
    # screen reader has of a mark is its word, and while that word was "choose" in both
    # arities the pixels above were the page's only account of how many it takes — which
    # is to say, no account at all for anyone listening. Read off the offer rather than
    # the pick: the offer is the state the reader is in while the question is still open,
    # which is when knowing costs them a wasted press.
    named = "el => el.getAttribute('aria-label')"
    assert (
        page.locator("#br-steel .lf-pick").evaluate(named)
        == "choose one: Steel — option 1 of 2"
    )
    assert (
        page.locator("#tl-clamp .lf-pick").evaluate(named)
        == "choose any: Bar clamp — option 1 of 2"
    )
    assert errors == []
    page.close()


def test_only_addressed_cards_yield_their_header_state_to_the_ask(browser, serve):
    """An Ask address replaces only the state control on the card that owns it.

    A package may contribute more actions than the nine contextual number bindings.
    The remaining cards still need their checkboxes: hiding every sibling as soon as
    one address exists erases both the unaddressed action and the group's multiple-choice
    arity from those cards.
    """
    options = "".join(
        f'<lf-option id="route-{index}"><strong>Route {index}</strong>'
        f"<p>Technical argument {index}.</p></lf-option>"
        for index in range(1, 11)
    )
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "ten routes",
                '<h1 id="h">Ten routes</h1>'
                '<lf-ask id="routes-decision"><h2>Which routes survive?</h2>'
                f'<lf-options id="routes" choose multiple>{options}</lf-options>'
                "</lf-ask>",
            )
        ),
    )
    resized(page, 900, 1200)

    page.keyboard.press("a")
    expect(
        page.locator("#routes > lf-option > .lf-address[data-lf-ask-address]")
    ).to_have_count(9)
    opacity = "el => getComputedStyle(el).opacity"
    for index in range(1, 10):
        assert page.locator(f"#route-{index} > .lf-pick").evaluate(opacity) == "0"
    assert page.locator("#route-10 > .lf-pick").evaluate(opacity) == "1", (
        "the unaddressed tenth action lost its visible checkbox to a sibling's address"
    )

    assert errors == []
    page.close()


def test_a_question_inside_an_option_keeps_its_own_arity(browser, serve):
    """An option's content model is prose, so a question nests inside another question's
    option — the theme's argument-row form lists `lf-options` among the block content it
    lays out. The arity a mark wears has to be its own group's, and the shape that says so
    is one an enclosing group could hand down: written as an inherited value, "which of
    these" on the outside would have made "which one" on the inside draw squares, and the
    reader would be told they may take both of two answers that replace each other.

    So each group reaches only as far as the options it owns. This is what stops that
    being an argument: a descendant selector here would pass every other test on this
    page and fail only where two questions stand inside one another."""
    page, errors = open_page(browser, serve(NESTED_ASK_PAGE))
    corner = """el => { const s = getComputedStyle(el, '::before');
                        const r = s.borderTopLeftRadius;
                        return r.endsWith('%') ? parseFloat(r) / 100
                                               : parseFloat(r) / parseFloat(s.width); }"""
    assert page.locator("#in-now .lf-pick").evaluate(corner) == 0.5, (
        "a single-pick question took the arity of the question it is nested in, so it "
        "offers a set where only one answer will stand"
    )
    # And the outer group's own marks are unaffected by the group standing inside one of
    # its options: the mark on #out-drill is the outer question's, not the inner one's.
    assert page.locator("#out-drill > .lf-pick").evaluate(corner) < 0.5
    assert page.locator("#out-keys > .lf-pick").evaluate(corner) < 0.5
    assert errors == []
    page.close()


def test_a_nested_questions_commands_belong_only_to_their_own_ask(browser, serve):
    """An Ask projects commands from its answer source, but containment alone does
    not confer ownership: a second Ask may stand inside an option as evidence.

    The outer Ask must therefore expose only its two choices. Otherwise both numbered
    command sets collide when the reader navigates there, and the inner question either
    breaks the key line or lends its answers to the wrong Ask.
    """
    page, errors = open_page(browser, serve(NESTED_ASK_PAGE))
    page.keyboard.press("a")

    expect(page.locator("#outer-decision")).to_be_focused()
    outer_hints = page.locator("#outer > lf-option > .lf-address")
    expect(outer_hints).to_have_text(["1", "2"])
    expect(outer_hints.first).to_be_visible()
    expect(page.locator("#inner > lf-option > .lf-address").first).to_be_hidden()

    page.keyboard.press("2")
    expect(page.locator("#out-keys")).to_have_attribute("chosen", "")
    expect(page.locator("#inner > lf-option[chosen]")).to_have_count(0)
    assert errors == []
    page.close()


def test_a_nested_questions_pick_is_not_part_of_its_outers_record(browser, serve):
    """Attribute records are sets owned by one recorded widget. A chosen option in a
    nested question must not enter the outer question's authored facet, or an outer log
    choice that exactly matches its markup is falsely painted as awaiting the author."""
    nested_choices = NESTED_ASK_PAGE.replace(
        '<lf-option id="out-drill">', '<lf-option id="out-drill" chosen>'
    ).replace('<lf-option id="in-now">', '<lf-option id="in-now" chosen>')
    url = serve(nested_choices)
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "outer",
            "action": "choose",
            "detail": {"options": ["out-drill"]},
        },
    )

    page, errors = open_page(browser, url)
    expect(page.locator("#outer")).not_to_have_attribute("data-lf-reader-override", "1")
    expect(page.locator("#inner")).not_to_have_attribute("data-lf-reader-override", "1")
    expect(page.locator("#out-drill")).to_have_attribute("chosen", "")
    expect(page.locator("#in-now")).to_have_attribute("chosen", "")
    assert errors == []
    page.close()


def test_working_the_evidence_in_an_option_is_not_a_pick(browser, serve):
    """The group takes the pick on the whole option, and the case the reader decides on
    is argued inside the option. So the two gestures land in the same box, and the
    evidence has to win the ones aimed at it: flipping the shot chose that option, and
    the flip being a label press meant it chose the option and cleared it again — two
    decisions in the log, no state on the page to show for either, and nothing the reader
    could have seen. The disclosure and the draft chose it outright.

    Each gesture is read against its own effect rather than against the absence of a
    pick, because a click that never arrived would satisfy the absence: the frame flips,
    the disclosure opens, the editor takes the draft's place, and only then is the
    question still open. The log is asked once at the end, since the failure that costs
    the most puts a decision there while leaving the page looking untouched."""
    page, errors = open_page(browser, serve(INLINE_CASE_PAGE))
    option = page.locator("#ro-column")
    picked = "el => el.hasAttribute('chosen')"

    page.mouse.click(*flip_point(page, "#ro-shot"))
    expect(page.locator("#ro-shot input[type=checkbox]")).to_be_checked()
    assert not option.evaluate(picked), "flipping the shot answered the question"

    page.locator("#ro-numbers summary").click()
    expect(page.locator("#ro-numbers")).to_have_attribute("open", "")
    assert not option.evaluate(picked), "opening the disclosure answered the question"

    page.locator("#ro-note .lf-draft-body").dblclick()
    expect(page.locator("#ro-note textarea")).to_be_visible()
    assert not option.evaluate(picked), (
        "opening the draft's editor answered the question"
    )

    words = page.locator("#ro-column-p")
    # The expanded editor can leave this paragraph geometrically in the viewport but
    # underneath the fixed key line. Centre the actual selection target before deriving
    # viewport coordinates; scroll_into_view_if_needed cannot see that occlusion.
    words.evaluate("el => el.scrollIntoView({block: 'center'})")
    start, end = words.evaluate("""el => {
        const text = el.firstChild;
        const point = (offset, edge) => {
            const range = document.createRange();
            range.setStart(text, offset);
            range.setEnd(text, offset + 1);
            const box = range.getBoundingClientRect();
            return [edge === 'start' ? box.left + 1 : box.right - 1,
                    box.top + box.height / 2];
        };
        const first = text.data.indexOf('failure');
        const last = text.data.indexOf('costing') + 'costing'.length - 1;
        return [point(first, 'start'), point(last, 'end')];
    }""")
    hold_selection(page, start, end)
    assert page.evaluate("() => getSelection().toString()") == (
        "failure reads off the list instead of costing"
    )
    page.mouse.up()
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(page.locator(".lf-fab-input")).not_to_be_focused()
    assert not option.evaluate(picked), "selecting the option's evidence answered it"

    assert [e for e in sent_events(serve.page_dir) if e["kind"] == "action"] == [], (
        "the reader working the evidence sent Claude a decision they never made"
    )

    # And the option's own words still answer it, which is what the card is for.
    page.keyboard.press("Escape")
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    page.locator("#ro-column-p").click()
    expect(page.locator("#ro-column > .lf-pick")).to_have_text("selected")
    round_trip(page)
    assert [
        e["detail"]["options"]
        for e in sent_events(serve.page_dir)
        if e["kind"] == "action"
    ] == [["ro-column"]]
    assert errors == []
    page.close()


def test_every_row_hangs_its_mark_at_the_same_column(browser, serve):
    """A row's dot is both the list's statement that it takes a pick and the target of
    the press that makes one, and it says the first of those by standing in a column
    with the others. Twice it did not. Laid out as flex items the row's free space had to
    be handed to whichever part of the apparatus came first, so the column was a fact
    about the `for` reference and a row with no block to name parked its mark wherever
    its label ended. And a chip an option says (`risk`) went in last of all, past the
    mark. `#jobs` carries both against rows that carry neither, which is where either
    reads worst — rows lined up and one hanging mid-sentence — and a group of rows naming
    nothing is what the shipped examples haven't got, which is why the form shipped the
    first way.

    The column is the row's leading edge, which is a change from the line's end and the
    reason is distance rather than alignment: both ends give a straight column, and the
    trailing one put it as far from the words it answers for as the row is wide — ~620px
    in a full-width group, so reading a row and reading whether it was taken were two
    separate looks. It is also the side a card's mark has always stood on, so the widget
    now asks its question one way in both forms.

    The mark stands out of flow in a column the group reserves, not in a cell of the
    row's own table, and that is what makes the column a column: a cell takes its width
    from what its row happens to hold, so a row naming no block comes out eight pixels off
    its neighbours and carries whatever stands beside it along. At the line's end that
    raggedness was the marks'; at the line's start it would be the labels', which is the
    edge the reader actually runs their eye down."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    # Where the ring is painted, and where the row's first authored word is, both against
    # the group. Read as a pair because either alone can be satisfied by the wrong thing:
    # a constant column proves nothing if it is past the words, and being left of the
    # words proves nothing if each row picks its own place.
    read = """() => {
                const group = document.querySelector('#jobs').getBoundingClientRect();
                return [...document.querySelectorAll('#jobs > lf-option')].map((o) => {
                  const mark = o.querySelector(':scope > .lf-pick');
                  const walk = document.createTreeWalker(o, NodeFilter.SHOW_TEXT);
                  let node = walk.nextNode();
                  while (node && (!node.data.trim()
                         || node.parentElement.closest('[data-lf-gen]')))
                    node = walk.nextNode();
                  const range = document.createRange();
                  range.setStart(node, 0); range.setEnd(node, 1);
                  return [Math.round(mark.getBoundingClientRect().left - group.left),
                          Math.round(range.getBoundingClientRect().left - group.left)];
                });
              }"""
    seen = page.evaluate(read)
    columns = {mark for mark, _word in seen}
    assert len(columns) == 1, (
        f"a row's mark hangs where its own row put it rather than in one column the "
        f"reader can aim down: {seen}"
    )
    assert all(mark < word for mark, word in seen), (
        f"a row's mark stands past the words it answers for: {seen}"
    )
    assert errors == []
    page.close()


def test_a_row_label_keeps_the_spacing_it_was_written_with(browser, serve):
    """A row is a line of prose with apparatus after it, and the prose is the author's:
    what it says between two words is a space, and the page owes them that space and no
    other. Laid out as flex items it owed them whatever the row's own `gap` was, because
    every stretch of a label became an item of its own and a flex item's edge whitespace
    is trimmed — `Replace the <code>M8</code> mounts` came out with 8px either side of
    the code and without the space that was written there, and zeroing the gap took the
    space away without giving it back. So the room between the last word and the code it
    runs into is read against the space itself: that the space is on the screen at all,
    and that nothing else is standing in for it."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    room = """() => {
                const code = document.querySelector('#job-mounts code');
                const text = code.previousSibling;   // "Replace the "
                const range = (from, to) => {
                  const r = document.createRange();
                  r.setStart(text, from); r.setEnd(text, to);
                  return r.getBoundingClientRect();
                };
                const word = range(0, text.data.length - 1);
                const space = range(text.data.length - 1, text.data.length);
                return [space.width, code.getBoundingClientRect().left - word.right];
              }"""
    space, gap = page.evaluate(room)
    assert space > 1, "the space the label was written with is not on the screen"
    assert abs(gap - space) < 0.5, (
        f"{gap}px of room where the label asked for {space}px"
    )
    assert errors == []
    page.close()


def test_a_row_holds_its_mark_still_under_its_own_press(browser, serve):
    """The mark is what the press is aimed at, so it is the last thing on the page that
    may move when the press lands — and the word it gains is exactly what would move it.
    The room for that word is held from the start, which is what keeps the § reference
    beside it still; the dot inside had no such guarantee, because it was centred in a
    box whose height was the word's, so a mark that gained one lifted its own dot 3.4px
    out from under the pointer that had just pressed it. Out of flow, over the row's own
    height, the dot stands where it stood."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    mark = page.locator("#job-heater .lf-pick")
    box = "el => JSON.stringify(el.getBoundingClientRect())"
    before = mark.evaluate(box)
    page.locator("#job-heater").click()
    expect(mark).to_have_text("selected")
    assert mark.evaluate(box) == before, "the press moved the mark it landed on"
    assert errors == []
    page.close()


def test_a_chip_an_option_says_stands_with_the_rest_of_its_words(browser, serve):
    """A chip is the page's words and the apparatus around it is the module's, so the
    reader — and the file's reading of that same version — find the chip inside the
    row's own words rather than out among the row's machinery.

    The rule was written against an attribute rendered by `x-says`, where the edge a
    pseudo-element would have taken stops being the element's own words the moment a
    module injects chrome, and appending put the page's words on the far side of it.
    A chip is authored markup now, written before the title, so it cannot land there by
    construction — which is the stronger form of the same guarantee, and this holds the
    outcome rather than the mechanism that used to threaten it.

    The mark leads the row and the `for` reference ends it, so the words are what stands
    between them, and the chip is read against both edges rather than against whichever
    one the apparatus happened to be on."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    chip = page.locator("#job-heater > lf-chip")
    expect(chip).to_have_text("reversible")
    ref = page.locator("#job-heater .lf-ref").bounding_box()
    mark = page.locator("#job-heater > .lf-pick").bounding_box()
    assert mark["x"] < chip.bounding_box()["x"] < ref["x"], (
        "the chip stands outside the row's own words rather than among them"
    )
    assert errors == []
    page.close()


def test_one_pill_holds_every_short_fact(browser, serve):
    """The three writers of a chip, on one page: an author's inline label, a facet of a
    decision, and the row a task builds from its own attributes.

    They stated the pill three times and agreed on every number but one, which is the
    kind of agreement nobody is keeping: the inline label alone padded itself top and
    bottom, so it stood four pixels taller than the chips in a band while matching them
    everywhere else. One rule states the pill now and each wearer adds only where it
    sits, which is why this reads the rendered box rather than the declarations — a
    wearer is free to restate, and the box is what a reader compares."""
    page, errors = open_page(browser, serve(CHIP_PAGE))
    face = """el => { const s = getComputedStyle(el);
        return Object.fromEntries(["font-family", "font-size", "line-height",
            "padding", "border-radius", "background-color", "color"]
            .map(p => [p, s.getPropertyValue(p)])); }"""
    worn = {
        where: (page.locator(sel).evaluate(face), page.locator(sel).bounding_box())
        for where, sel in [
            ("in prose", "#intro > .tag"),
            ("on a decision", "#p-keep > lf-chip"),
            ("in a task's row", "#t-camera .lf-chips > span"),
        ]
    }
    ((first, (look, box)), *rest) = worn.items()
    for where, (other, other_box) in rest:
        assert other == look, (
            f"the chip {where} is drawn unlike the one {first}:\n  "
            + "\n  ".join(
                f"{k}: {other[k]!r} vs {look[k]!r}" for k in look if other[k] != look[k]
            )
        )
        assert other_box["height"] == box["height"], (
            f"the chip {where} stands {other_box['height']}px against "
            f"{box['height']}px {first}"
        )
    assert errors == []
    page.close()


def test_what_a_widget_paints_it_says_to_a_reader_listening(browser, serve):
    """A tint is a fact to whoever can see it and nothing at all to whoever can't. A
    task's marker and an event's kind band each carried their whole meaning in colour,
    so a reader listening was handed every word around the fact and never the fact:
    done sounded exactly like blocked.

    Declared (x-paints) rather than written into each module, which is what lets it
    reach the two widgets here that have no module at all, and read as the value or, for
    a flag carrying none, the attribute's own name. Said in text, because that is the
    one thing every screen reader announces in every mode — and therefore clipped to
    nothing, holding no room, and out of the selection, since a word the eye can't see
    is a word the clipboard has no business carrying."""
    page, errors = open_page(browser, serve(PAINTED_PAGE))
    for sel, word in (
        ("#e-dark", "failure"),
        ("#t-baffles", "blocked"),
    ):
        assert word in page.locator(sel).aria_snapshot(), (
            f"{sel} paints `{word}` and says nothing of it to a reader listening"
        )
    room = page.locator(".lf-quiet").evaluate_all(
        """els => els.map(el => { const r = el.getBoundingClientRect();
             return [el.textContent, r.width, r.height,
                     getComputedStyle(el).userSelect]; })"""
    )
    assert len(room) == 2, f"one quiet word per painted fact, got {room}"
    for word, width, height, select_mode in room:
        assert width <= 1 and height <= 1, f"`{word}` is painting {width}x{height}"
        assert select_mode == "none", f"`{word}` would come away in a copy of the page"
    # And the browser agrees: a selection drawn across the whole event carries the
    # words the page shows and not the one it only says.
    spoken = page.evaluate(
        """() => { const el = document.getElementById("e-dark");
             const r = document.createRange(); r.selectNodeContents(el);
             getSelection().removeAllRanges(); getSelection().addRange(r);
             return getSelection().toString(); }"""
    )
    assert "went dark" in spoken and "failure" not in spoken, spoken
    assert errors == []
    page.close()


def test_a_pick_states_the_whole_set(browser, serve):
    """`multiple` is the difference between "which of these" and "which one", and the
    action is the same shape either way: every picked option, absolutely, so replay is
    idempotent and a second tab converges rather than drifting. Without `multiple` the
    set a click toggles from is empty, which is what makes a pick replace instead of
    join — one rule, not two code paths."""
    page, errors = open_page(browser, serve(ASK_PAGE))

    page.locator("#job-mounts").click()
    expect(page.locator("#jobs > lf-option[chosen]")).to_have_count(1)
    page.locator("#job-camera").click()
    expect(page.locator("#jobs > lf-option[chosen]")).to_have_count(2)
    page.locator("#job-mounts").click()
    expect(page.locator("#jobs > lf-option[chosen]")).to_have_count(1)

    # The single-pick group beside it replaces rather than joining, and clicking the
    # pick again empties it.
    page.locator("#br-steel").click()
    expect(page.locator("#bracket > lf-option[chosen]")).to_have_count(1)
    page.locator("#br-cedar").click()
    expect(page.locator("#br-cedar[chosen]")).to_have_count(1)
    expect(page.locator("#br-steel[chosen]")).to_have_count(0)
    page.locator("#br-cedar").click()
    expect(page.locator("#bracket > lf-option[chosen]")).to_have_count(0)

    # A pick paints its own click before the post answers, so the DOM leads the log;
    # the trip counter says when everything sent has been read back.
    round_trip(page)
    picks = [
        (e["widget"], e["detail"])
        for e in sent_events(serve.page_dir)
        if e.get("action") == "choose"
    ]
    assert picks == [
        ("jobs", {"options": ["job-mounts"]}),
        ("jobs", {"options": ["job-mounts", "job-camera"]}),
        ("jobs", {"options": ["job-camera"]}),
        ("bracket", {"options": ["br-steel"]}),
        ("bracket", {"options": ["br-cedar"]}),
        ("bracket", {"options": []}),
    ]
    expect(
        page.locator('[data-lf-margin-for="bracket-decision"] .lf-margin-marker')
    ).to_have_attribute("data-lf-kinds", "ask")
    assert errors == []
    page.close()


def test_a_widget_move_reuses_one_target_button_until_the_page_honors_it(
    browser, serve
):
    """A widget needs no x-work declaration to acknowledge the reader's move.

    The owner's existing page-edge Button keeps its DOM identity while durable transport
    acceptance advances Sent to Picked up and a real claim makes it Active. Once authored
    markup records the choice and completes the claim, the Button disappears; the widget
    carries the chosen state itself.
    """
    url = serve(ASK_PAGE)
    page, errors = open_page(browser, live_url(url))
    d = serve.page_dir

    page.locator("#job-mounts").click()
    round_trip(page)
    action = next(
        event
        for event in reversed(sent_events(d))
        if event.get("widget") == "jobs" and event.get("action") == "choose"
    )
    logged_action = next(
        event for event in events_model.read_events(d) if event["id"] == action["id"]
    )
    receipt = page.locator('[data-lf-margin-for="jobs"] > .lf-margin-marker')
    expect(receipt).to_have_attribute("data-lf-kinds", "sent")
    expect(receipt.locator(".lf-margin-button-icon")).to_have_attribute(
        "data-lf-icon", "sent"
    )
    expect(receipt).to_have_attribute("aria-label", re.compile(r"^Sent, "))
    expect(page.locator("#jobs > .lf-receipt")).to_have_count(0)
    receipt.evaluate("node => { node.dataset.identityProbe = 'kept' }")

    with service_model.PageTransaction(d) as transaction:
        session_model.record_pickup(transaction, [logged_action])
    session_model.cmd_ack(d, logged_action["seq"])
    told(page)
    expect(receipt).to_have_attribute("data-lf-kinds", "pickup")
    expect(receipt).to_have_attribute("aria-label", re.compile(r"^Picked up, "))
    expect(receipt).to_have_attribute("data-identity-probe", "kept")

    active = CliRunner().invoke(
        cli_model.cli,
        ["status", str(d), "working", "checking the mounts", "--on", "jobs"],
    )
    assert active.exit_code == 0, active.output
    told(page)
    expect(receipt).to_have_attribute("data-lf-kinds", "activity")
    expect(receipt.locator(".lf-margin-button-icon")).to_have_attribute(
        "data-lf-icon", "activity"
    )
    expect(receipt).to_have_attribute("aria-label", re.compile("checking the mounts"))
    expect(receipt).to_have_attribute("data-identity-probe", "kept")

    # The receipt admitted this claim without an x-work declaration. Its page-edge
    # Target Button is still a local seat, so an unrelated revision cannot wedge the
    # authoring loop merely because the widget has no content or conversation seat.
    unrelated = ASK_PAGE.replace(
        '<h1 id="h">Three jobs</h1>', '<h1 id="h">Three jobs, checked</h1>'
    )
    stamp_page(d, unrelated, "Checked the surrounding plan")
    wait_for_revision(page, 2)
    expect(receipt.locator(".lf-margin-button-icon")).to_have_attribute(
        "data-lf-icon", "activity"
    )
    expect(receipt).to_have_attribute("aria-label", re.compile("checking the mounts"))
    expect(receipt).to_have_attribute("data-identity-probe", "kept")

    honored = ASK_PAGE.replace(
        '<lf-option id="job-mounts"', '<lf-option id="job-mounts" chosen'
    )
    stamp_page(d, honored, "Honor the mounts choice", completes=("jobs",))
    wait_for_revision(page, 3)
    expect(page.locator('[data-lf-margin-for="jobs"]')).to_have_count(0)
    expect(page.locator("#job-mounts[chosen]")).to_have_count(1)
    assert errors == []
    page.close()


def test_a_send_waits_for_the_send_before_it(browser, serve):
    """The log's order is the order the user acted in, and two requests in flight are
    not: the server answers each on a thread of its own, so a pick made a moment after
    another can be appended before it. That is the drift the test below is about,
    arriving through the log this time rather than through a poll — and arriving where
    nothing heals it, since replay states a widget whole and every later reading of the
    page is of the log it left.

    It reached CI before it was ever seen here, on the test above: two clicks three
    lines apart landed reversed on a loaded runner, twice, while two dozen runs of that
    same sequence in the dockerised Linux suite never once managed it. So the race is
    stated rather than run for. The first send is stopped in the wire and the second
    click made while it is still there, which is the whole of a loaded machine's
    contribution; what the page does about that click is the instrument, since it paints
    a pick before it sends and so has already done whatever it was going to do about
    sending by the time the paint is readable.

    Both halves are asserted and only one of them is the gate. One request in the wire
    is a fact about this page on every run, so it is what goes red the moment the queue
    does; the log's order after the release is the outcome the queue is for, and on its
    own it would be the same coin the runner tossed — a second send already appended
    beats the release, and one still in flight doesn't."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    held = []

    def hold(route):
        # The first send is stopped where the server cannot take it, and everything
        # after it goes through — so with the queue gone the second pick reaches the log
        # first, and releasing the first pick appends it on top of the newer one.
        if held:
            route.continue_()
        else:
            held.append(route)

    page.route("**/api/event", hold)
    page.locator("#br-steel").click()
    holding(page, held, 1, "the pick it was clicked for")
    page.locator("#br-cedar").click()
    expect(page.locator("#br-cedar[chosen]")).to_have_count(1)
    assert _traffic(page).sends == 1, (
        "a second send went out over the first, so which of the two the server appends "
        "first is the machine's answer rather than the reader's"
    )

    held[0].continue_()
    _until(page, lambda traffic: traffic.sends == 2, "sent the queued second pick")
    round_trip(page)
    assert [
        e["detail"]["options"]
        for e in sent_events(serve.page_dir)
        if e.get("action") == "choose"
    ] == [["br-steel"], ["br-cedar"]]
    assert errors == []
    page.close()


def test_an_answer_carrying_an_older_pick_cannot_undo_a_newer_one(browser, serve):
    """The first POST's state contains only the first pick, but it may arrive after a
    second local pick. Replay leaves the outbox's widget alone, so that older snapshot
    cannot erase the newer gesture or corrupt the absolute state it later sends."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    d = serve.page_dir
    held = []
    sent_behind = []

    def hold_answers(route):
        # The first pick is stopped in the wire and released below, so the state its
        # answer carries — that pick and nothing else, the second never having been
        # sent behind it — reaches the page after the second pick is painted. Held
        # rather than fetched here: a handler that goes to the server itself is still
        # inside that call while the clicks below run, and the release would reach for
        # a route the list hasn't got (tests/CLAUDE.md, on releasing a hold).
        if held:
            sent_behind.append(route)
            route.continue_()
        else:
            held.append(route)

    page.route("**/api/event", hold_answers)
    with page.expect_request("**/api/event"):
        page.locator("#job-mounts").click()
    page.wait_for_timeout(0)
    assert len(held) == 1
    page.locator("#job-camera").click()
    expect(page.locator("#jobs > lf-option[chosen]")).to_have_count(2)
    assert _traffic(page).sends == 1, (
        "the second pick went out over the first, so the answer released below is not "
        "the older one this test is about"
    )

    held[0].continue_()
    _until(page, lambda traffic: traffic.sends == 2, "sent the second queued pick")
    expect(page.locator("#jobs > lf-option[chosen]")).to_have_count(2)

    page.unroute("**/api/event")
    round_trip(page)
    assert len(sent_behind) == 1
    page.locator("#job-heater").click()
    round_trip(page)
    assert [
        e["detail"]["options"] for e in sent_events(d) if e.get("widget") == "jobs"
    ] == [
        ["job-mounts"],
        ["job-mounts", "job-camera"],
        ["job-mounts", "job-camera", "job-heater"],
    ]
    assert errors == []
    page.close()


def test_a_widget_without_a_thread_says_what_the_agent_is_doing(browser, serve):
    """A page widget is a first-class work subject even before anybody comments.

    A board card declares a local work seat and receives its page-edge Button without
    inventing a comment thread. An options group deliberately has no such seat: adding
    an option changes decision state, and any discussion starts as a separate thread
    once that option exists. Unrelated versions leave the board claim standing, while
    a claim made on v2 does not leak backward into a pinned v1 tab.
    """
    work_page = ASK_PAGE.replace(
        '<h1 id="h">Three jobs</h1>',
        '<h1 id="h">Three jobs</h1>\n'
        '<lf-board id="work-board"><lf-column id="work-now" label="In flight">\n'
        '  <lf-card id="card-migration"><strong>Run the migration</strong> '
        "Check the shard before cutover.</lf-card>\n"
        '</lf-column><lf-column id="work-next" label="Next"></lf-column>\n'
        '<lf-column id="work-done" label="Done"></lf-column></lf-board>',
    )
    url = serve(work_page)
    page, errors = open_page(browser, live_url(url))
    d = serve.page_dir

    def claim(subject, detail):
        result = CliRunner().invoke(
            cli_model.cli,
            ["status", str(d), "working", detail, "--on", subject],
        )
        assert result.exit_code == 0, result.output
        told(page)

    claim("card-migration", "checking the shard")
    unsupported = CliRunner().invoke(
        cli_model.cli,
        ["status", str(d), "working", "pricing the alternatives", "--on", "jobs"],
    )
    assert unsupported.exit_code != 0
    assert "no local work seat" in unsupported.output

    card_button = page.locator(
        '[data-lf-margin-for="card-migration"] > .lf-margin-marker'
    )
    expect(card_button).to_have_attribute("data-lf-kinds", "activity")
    expect(card_button.locator(".lf-margin-button-icon")).to_have_attribute(
        "data-lf-icon", "activity"
    )
    expect(card_button).to_have_attribute(
        "aria-label", re.compile("checking the shard")
    )
    card_button.click()
    expect(page.locator(".lf-live")).to_contain_text("checking the shard")
    expect(page.locator(".lf-thread")).to_have_count(0)
    expect(page.locator(".lf-panel .lf-receipt")).to_have_count(0)
    expect(page.locator("#card-migration > .lf-receipt")).to_have_count(0)
    expect(card_button).to_have_class(re.compile(r"\blf-margin-button\b"))

    # An unrelated version leaves the card coordinate standing.
    stamp_page(d, work_page, "Elsewhere")
    wait_for_revision(page, 2)
    expect(card_button).to_have_count(1)

    # A new claim belongs to v2 and does not appear in a pinned v1 page.
    claim("card-migration", "checking the fallback")
    expect(card_button).to_have_attribute(
        "aria-label", re.compile("checking the fallback")
    )
    pinned, pinned_errors = open_page(browser, url, pin=True)
    expect(
        pinned.locator('[data-lf-margin-for="card-migration"] > .lf-margin-marker')
    ).to_have_count(0)
    assert pinned_errors == []
    pinned.close()

    stamp_page(
        d,
        work_page,
        "Local work complete",
        completes=("card-migration",),
    )
    wait_for_revision(page, 3)
    expect(page.locator(".lf-receipt")).to_have_count(0)
    assert errors == []
    page.close()


def test_local_work_chrome_does_not_take_its_holder_gesture(browser, serve, tmp_path):
    """A customization may deliberately give a container member a content seat.
    The runtime's generated Button is still apparatus rather than that member's own
    gesture: clicking status about an option must not choose the option."""
    option = json.loads((schema_model.DEFAULT_PACKAGE / "registry.json").read_text())[
        "lf-option"
    ]
    option["x-work"] = {"seat": "content"}
    layer = tmp_path / ".leaf"
    layer.mkdir()
    (layer / "registry.json").write_text(json.dumps({"lf-option": option}))

    page, errors = open_page(browser, serve(ASK_PAGE))
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "status",
            str(serve.page_dir),
            "working",
            "checking the mount",
            "--on",
            "job-mounts",
        ],
    )
    assert result.exit_code == 0, result.output
    told(page)

    work_button = page.locator('[data-lf-margin-for="job-mounts"] > .lf-margin-marker')
    expect(work_button).to_have_attribute("data-lf-kinds", "activity")
    work_button.click()

    # A press that does nothing states no fact to wait on, so the control is the same
    # gesture where it is supposed to work: pick the neighbouring option and let its
    # send settle. One outbox in gesture order means a pick the receipt had taken
    # would already stand ahead of this one, so the whole log can be read once.
    page.locator("#job-heater").click()
    round_trip(page)

    picks = [
        (e["widget"], e["detail"])
        for e in sent_events(serve.page_dir)
        if e["kind"] == "action"
    ]
    assert picks == [("jobs", {"options": ["job-heater"]})], picks
    expect(page.locator("#job-mounts")).not_to_have_attribute("chosen", "")
    assert errors == []
    page.close()


def test_settled_widget_work_leaves_a_declared_shadow_tree(browser, serve):
    """A typed widget claim follows an id through declared shadow roots, so its
    settlement must reach the same tree. This stages an authored prose widget the way
    a future x-shadow vocabulary member may: the lookup already promises to find it
    there, and the cleanup cannot leave the provisional line behind after the server
    projects the claim away."""
    work_page = TWICE_PAGE.replace(
        '<lf-diff id="patch">',
        '<lf-board id="shadow-work"><lf-column id="shadow-now" label="Now">\n'
        '  <lf-card id="shadow-card"><strong>Check the shard</strong></lf-card>\n'
        '</lf-column></lf-board>\n<lf-diff id="patch">',
    )
    url = serve(work_page)
    page, errors = open_page(browser, url, pin=True)
    d = serve.page_dir

    claimed = CliRunner().invoke(
        cli_model.cli,
        ["status", str(d), "working", "checking the shard", "--on", "shadow-card"],
    )
    assert claimed.exit_code == 0, claimed.output
    told(page)
    work_button = page.locator('[data-lf-margin-for="shadow-card"] > .lf-margin-marker')
    expect(work_button).to_have_attribute("data-lf-kinds", "activity")

    page.evaluate(
        """() => document.getElementById('patch').shadowRoot.append(
            document.getElementById('shadow-card'))"""
    )
    expect(work_button).to_have_count(1)

    settled = stamp_page(
        d,
        work_page,
        "Shard checked",
        completes=("shadow-card",),
    )
    assert settled["version"] == 2
    told(page)
    expect(work_button).to_have_count(0)
    assert errors == []
    page.close()


def test_widget_work_keeps_its_button_style_in_a_declared_shadow_tree(browser, serve):
    """The same declaration-backed seat may be staged into an x-shadow widget;
    crossing that supported boundary must not turn the shared local line back into an
    unstyled block."""
    work_page = TWICE_PAGE.replace(
        '<lf-diff id="patch">',
        '<lf-board id="shadow-work"><lf-column id="shadow-now" label="Now">\n'
        '  <lf-card id="shadow-card"><strong>Check the shard</strong></lf-card>\n'
        '</lf-column></lf-board>\n<lf-diff id="patch">',
    )
    url = serve(work_page)
    page, errors = open_page(browser, url, pin=True)
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "status",
            str(serve.page_dir),
            "working",
            "checking the shard",
            "--on",
            "shadow-card",
        ],
    )
    assert result.exit_code == 0, result.output
    told(page)
    work_button = page.locator('[data-lf-margin-for="shadow-card"] > .lf-margin-marker')
    expect(work_button).to_have_css("display", "flex")

    page.evaluate(
        """() => document.getElementById('patch').shadowRoot.append(
            document.getElementById('shadow-card'))"""
    )
    expect(work_button).to_have_css("display", "flex")
    expect(work_button).to_have_css("border-radius", "50%")
    expect(work_button).to_have_css("height", "32px")
    assert errors == []
    page.close()


def test_the_box_is_offered_only_where_something_can_answer_it(browser, serve):
    """An option field with no handler would invite input the page cannot accept.

    So the field is withheld rather than undone: the offer is
    made once in the live page, and a copy, a printout and a retired question each get
    the page without it by never being handed it.

    The collapse is the same rule at a different scale. A settled group's box goes
    behind the disclosure with its options, because the question is retired until the
    reader opens it again — and `display: flex` on the class would otherwise outrank
    the hidden attribute and leave a box floating under a collapsed group.

    What the options go behind is `hidden="until-found"`, which is find-in-page's to
    reopen and so collapses the box with content-visibility rather than by removing it.
    That is containment, and containment passes over a table box without a word — a
    question row states its layout as a table, so a settled group of them stayed on
    screen under a shut disclosure, reading as one that had never collapsed."""
    page, errors = open_page(browser, serve(SETTLED_ASK_PAGE))
    assert errors == []

    box = page.locator("#jobs .lf-another")
    rows = page.locator("#jobs > lf-option")
    expect(box).to_be_hidden()
    assert rows.evaluate_all(
        "els => els.map(e => e.getBoundingClientRect().height)"
    ) == [0, 0, 0]
    page.locator("#jobs .lf-settled").click()
    expect(box).to_be_visible()
    assert all(
        rows.evaluate_all("els => els.map(e => e.getBoundingClientRect().height > 0)")
    )

    # The copy medium: the same DOM with the affordance never handed to it.
    page.evaluate("() => document.documentElement.classList.add('lf-copy')")
    expect(box).to_be_hidden()
    page.close()


def test_the_specimen_gutter_is_painted_in_both_schemes(browser, serve):
    """The gutter is the whole marking, and it is the one part of a specimen with
    a color of its own: a token the dark block forgot would leave the bar
    transparent and the quoting silently gone. Nothing else catches that — not even
    the sweep that now drives a specimen through render_version in both palettes,
    since a transparent border is not an error, resizes no box, and leaves every
    word selectable."""
    url = serve(SPECIMEN_PAGE)
    for scheme in ("light", "dark"):
        page = browser.new_page(color_scheme=scheme)
        page.goto(url, wait_until="load")
        gutter = page.locator("#spec").evaluate(
            "el => getComputedStyle(el).borderLeftColor"
        )
        assert gutter not in ("rgba(0, 0, 0, 0)", "transparent"), f"[{scheme}] {gutter}"
        page.close()


@pytest.mark.parametrize(
    "source",
    [SPECIMEN_PAGE, *SPECIMEN_EXAMPLES],
    ids=["fixture", *(p.stem for p in SPECIMEN_EXAMPLES)],
)
def test_the_gutter_runs_beside_the_exhibit_and_no_further(source, browser, serve):
    """The gutter marks what is quoted and nothing else, at both ends, and two separate
    things had to be true for that. The "quoted ·" note over the bar is the theme's word
    *about* the region rather than a word in it, and the bar opened at the note, drawing
    the marking around a line the page never said. And a table cell is a margin barrier,
    so the room the exhibit's outermost blocks reserve against neighbours they haven't
    got could not collapse out and was painted as bar instead — sixteen pixels of it
    over the first card and under the last, on every specimen shipped.

    Geometry can't answer the top. The element's own rect is the table wrapper's and
    takes in the caption, while the bar is painted on the table box inside it, which
    nothing in the DOM is a handle on — so a rect comparison passes exactly as well
    with the note back inside the marking. The pixels in the bar's own column are the
    reading, and each edge is read in a strip of its own with that edge brought to the
    middle of the window: a clip is the viewport's, so one strip over the whole bar
    would cap the sweep at the tallest exhibit a window can hold.

    Driven over every specimen in the corpus rather than the fixture alone, because
    what the theme can reach is the specimen's direct children and what it cannot is
    whichever widget hands its boxes to the flow instead. That gap is invisible in the
    stylesheet and shows only as a bar longer than what it marks, so the corpus is
    where the next one gets caught."""
    from PIL import Image  # a dev dependency already, for the demo recorder

    # The examples by path, so each is served with the data its markup selects; their
    # conversations are left off, since the bar is drawn around what the markup exhibits.
    page, errors = open_page(browser, serve(source, seed_log=False))
    assert errors == []
    scale = page.evaluate("() => devicePixelRatio")
    # Rendered, not merely present. A specimen inside a tab panel the page is not
    # showing sits in skipped content, which still reports its last laid-out rect — a
    # position the page cannot be scrolled to, since the room it names is not in the
    # document's height. `checkVisibility` is the question `lf-suggestion` already asks
    # for the same reason.
    specimens = page.locator("lf-specimen").evaluate_all(
        "els => els.filter(e => e.checkVisibility()).map(e => e.id)"
    )
    if not specimens:
        owners = page.locator("#corpus > lf-tab:has(lf-specimen)")
        assert owners.count(), (
            "this page declares a specimen but no visible exhibit or corpus panel owns it"
        )
        label = owners.first.get_attribute("label")
        page.get_by_role("tab", name=label, exact=True).click()
        specimens = page.locator("lf-specimen").evaluate_all(
            "els => els.filter(e => e.checkVisibility()).map(e => e.id)"
        )
    assert specimens, "this page shows no specimen: the reading below asserts nothing"

    for spec in specimens:
        ink = tuple(
            int(n)
            for n in re.findall(
                r"\d+",
                page.locator(f"#{spec}").evaluate(
                    "el => getComputedStyle(el).borderLeftColor"
                ),
            )[:3]
        )
        found = {}
        for edge in ("top", "bottom"):
            # `instant`, because the page asks for smooth scrolling and a read taken
            # while one is still gliding is of wherever it had got to — which passes on
            # a short page, where the glide is over before the next call lands, and
            # failed on the corpus, where the same delta is thousands of pixels.
            page.evaluate(
                """([id, edge]) => {
                    const r = document.getElementById(id).getBoundingClientRect();
                    document.scrollingElement.scrollBy({
                        top: (edge === 'top' ? r.top : r.bottom) - innerHeight / 2,
                        behavior: 'instant',
                    });
                }""",
                [spec, edge],
            )
            box = page.locator(f"#{spec}").bounding_box()
            exhibit = page.evaluate(EXHIBIT_EXTENT, spec)

            # A column one pixel wide inside the 3px bar, running from outside the
            # marking to well inside it, and read from the inside out: stopping at the
            # first pixel that isn't the bar's keeps a glyph of the note's that happens
            # to antialias through this colour from being a bar the run can reach.
            #
            # The clip's top is floored first and the reading counts from the floored
            # value, because a clip is asked for in CSS pixels and Chrome truncates the
            # rect before it scales — a pixel of unmodelled bias, against a gap of four.
            REACH = 40  # far enough inside the bar to start in it, and to give a number
            near, far = (
                (box["y"], exhibit["top"] + REACH)
                if edge == "top"
                else (exhibit["bottom"] - REACH, box["y"] + box["height"] + REACH)
            )
            clip = {
                "x": box["x"] + 1,
                "y": math.floor(near),
                "width": 1,
                "height": math.ceil(far) - math.floor(near),
            }
            on_screen = page.evaluate(
                "([y, h]) => y >= 0 && y + h <= innerHeight",
                [clip["y"], clip["height"]],
            )
            assert on_screen, (
                f"#{spec}'s {edge} strip is not wholly on screen ({clip}): a "
                f"screenshot clip is the viewport's, so the scan would read a "
                f"truncated image"
            )
            strip = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
            assert strip.height == clip["height"] * scale, (
                f"the clip asked for {clip['height']} CSS px at dpr {scale} and came "
                f"back {strip.height} device px: the arithmetic below no longer "
                f"locates its edge"
            )
            rows = [strip.getpixel((0, y)) for y in range(strip.height)]
            if edge == "bottom":
                rows.reverse()  # both edges read from the far end of the strip inward
            painted = 0
            while painted < len(rows) and all(
                abs(a - b) <= 6 for a, b in zip(rows[-1 - painted], ink)
            ):
                painted += 1
            assert painted, (
                f"#{spec}: no gutter painted in the column beside the exhibit at the "
                f"{edge} ({rows[-1]}) — the bar is unpainted, or it is more than "
                f"{REACH}px away from the exhibit it marks"
            )
            found[edge] = (
                clip["y"] + (len(rows) - painted) / scale
                if edge == "top"
                else clip["y"] + painted / scale
            )
            found[f"{edge}-exhibit"] = exhibit[edge]
            if edge == "top":
                found["note"] = exhibit["note"]

        assert abs(found["top"] - found["top-exhibit"]) <= 1, (
            f"#{spec}'s marking begins at {found['top']} and the exhibit at "
            f"{found['top-exhibit']}: the bar runs beside something the page did not "
            f"say, or begins after what it marks"
        )
        assert abs(found["bottom"] - found["bottom-exhibit"]) <= 1, (
            f"#{spec}'s marking ends at {found['bottom']} and the exhibit at "
            f"{found['bottom-exhibit']}: the bar outlives what it marks — most likely "
            f"a trailing margin inside a child that generates no box, which the "
            f"theme's rule for the specimen's last child cannot reach"
        )
        if found["note"] is not None:
            assert found["note"] <= found["top"] + 1, (
                f"#{spec}'s marking begins at {found['top']}, above the foot of the "
                f"note at {found['note']}: the marking takes in a line the page never "
                f"said"
            )
    page.close()


def test_a_specimen_holds_a_wide_exhibit_inside_the_column(browser, serve):
    """An exhibit wider than the column scrolls inside its own box, as it does
    anywhere else on the page. What makes that true here is one declaration —
    a table sizes to its content, so without `table-layout: fixed` the specimen
    grows to the board's width and hands the document a sideways scrollbar, taking
    the comment layer's anchoring off screen with it.

    Read at a viewport narrow enough for the board to want more room than the
    column has; at the render sweep's own 1200px the board fits and nothing here
    can fail."""
    page, errors = open_page(browser, serve(SPECIMEN_PAGE))
    assert errors == []
    page.evaluate(
        """() => document.addEventListener('lf-margin-layout', () => {
          window.lfMarginLayoutWidth = innerWidth;
        })"""
    )
    resized(page, 380, 900)
    page.wait_for_function("() => window.lfMarginLayoutWidth === 380")
    wide = page.evaluate(
        "() => [document.documentElement.scrollWidth,"
        " document.documentElement.clientWidth,"
        " Math.round(document.getElementById('spec').getBoundingClientRect().width),"
        " document.getElementById('quoted-board').scrollWidth]"
    )
    document, column, specimen, board = wide
    assert board > column, (
        f"the board is {board}px in a {column}px column: it has to want more room "
        f"than the column has, or nothing below is being tested"
    )
    assert specimen <= column, f"the specimen is {specimen}px in a {column}px column"
    assert document == column, (
        f"the document scrolls sideways ({document}px against {column}px): the "
        f"exhibit widened the specimen instead of scrolling inside it"
    )
    page.close()


def test_a_specimen_in_a_reply_is_quoted_there_too(browser, serve):
    """The panel is where a live question actually gets put — Claude's replies
    carry widget markup — so it is also where a quoted one has to stay quoted.
    One reply holds both: the question wires up and its pick reaches the log,
    the exhibit beside it does neither, and the gutter marking it renders in the
    panel's narrower column as it does in the document. The theme's specimen
    rules and quoted()'s closest() both have to reach outside <main>, and
    nothing else in the suite renders a specimen there."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-decision",
            "author": "user",
            "revision": 1,
            "text": "What would the alternative look like?",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-decision",
            "revision": 1,
            "text": SPECIMEN_TEXT,
            "markup": SPECIMEN_MARKUP,
        },
    )
    page, errors = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    page.wait_for_selector(
        '#rp-live .lf-pick[role="checkbox"]'
    )  # the reply's widgets upgraded
    assert errors == []

    # The gutter renders in the panel: the specimen rules aren't scoped to the
    # document's column, and neither is the label — which reaches the panel only
    # because renderSaid runs over a reply's markup too, where no custom element
    # upgrade would have carried it.
    label = page.locator('#rp-spec > [data-lf-said="label"]')
    assert label.text_content() == "the April thread"
    assert (
        label.evaluate("el => getComputedStyle(el, '::before').content")
        == '"quoted · "'
    )
    gutter = page.locator("#rp-spec").evaluate(
        "el => [getComputedStyle(el).borderLeftWidth,"
        " getComputedStyle(el).borderLeftColor]"
    )
    assert gutter[0] != "0px" and gutter[1] not in (
        "rgba(0, 0, 0, 0)",
        "transparent",
    ), f"the panel's specimen carries no gutter: {gutter}"
    assert (
        page.locator("#rp-quoted lf-option").count() == 2
    )  # and the exhibit is all there

    # The exhibit takes the click first, so anything it sends would reach the log
    # ahead of the live group's pick — then the live group takes its own.
    assert page.locator('#rp-quoted .lf-pick[role="checkbox"]').count() == 0
    # And no hand over it, which is what the marker being painted anywhere buys: the
    # affordance rules ask whether an element stands inside [data-lf-exhibit], and the
    # runtime paints that on a widget wherever it renders. Painted in the document
    # alone, this exhibit would offer the pick the live question above it offers.
    hand = "el => getComputedStyle(el).cursor"
    assert page.locator("#rp-stage").evaluate(hand) == "pointer", (
        "the reply's live question shows no hand either, so the exhibit's missing "
        "one is not the quoting"
    )
    assert page.locator("#rp-memory").evaluate(hand) != "pointer"
    page.locator("#rp-memory").click()
    page.locator("#rp-stage").click()

    # Waiting on the log for *an* action would settle for the live group's and never see
    # a second one the exhibit had no business sending. The page's own count is the whole
    # of what it sent, so this waits out an exhibit's stray post too.
    round_trip(page)
    actions = [e for e in events_model.read_events(d) if e["kind"] == "action"]
    assert [(e["widget"], e["detail"]) for e in actions] == [
        ("rp-live", {"options": ["rp-stage"]})
    ]
    receipt = page.locator(
        f'#rp-live > .lf-receipt[data-receipt-id="{actions[0]["id"]}"]'
    )
    expect(receipt).to_contain_text("✓ Sent")
    with service_model.PageTransaction(d) as transaction:
        session_model.record_pickup(transaction, actions)
    told(page)
    expect(receipt).to_contain_text("✓ Picked up")
    assert page.locator("#rp-quoted lf-option[chosen]").count() == 0
    page.close()


def test_a_table_in_a_reply_keeps_its_figures_whole(browser, serve):
    """A reply is Markdown, so it can hold a table, and the panel is 420px wide.
    Prose there breaks anywhere — the thing a reply overflows on is a URL no wrap
    can help — and a table caught the same rule: "12,000" came out as "12,0" over
    "00", in the column of figures the table was written to compare. Both halves
    are asserted together, since turning the breaking off everywhere reads the
    same in a cell and is the actual regression to fear."""
    url = serve(REPLY_HOST_PAGE)
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-decision",
            "author": "user",
            "revision": 1,
            "text": "What are the ceilings?",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-decision",
            "revision": 1,
            "text": TABLE_REPLY,
        },
    )
    page, errors = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    page.wait_for_selector(".lf-msg-body table")

    # One client rect is one line: the figure is drawn as a single run, the URL
    # in the same reply as several.
    lines = """(el) => { const r = document.createRange();
                         r.selectNodeContents(el); return r.getClientRects().length; }"""
    assert page.get_by_role("cell", name="12,000").evaluate(lines) == 1
    assert page.locator(".lf-msg.claude .lf-msg-body a").evaluate(lines) > 1
    # And the room the cells stopped giving up went where the theme puts it.
    assert (
        page.locator(".lf-msg.claude .lf-msg-body table").evaluate(
            "(t) => t.scrollWidth - t.clientWidth"
        )
        > 0
    )
    assert (
        page.locator(".lf-msg.claude .lf-msg-body").evaluate(
            "(b) => b.scrollWidth - b.clientWidth"
        )
        == 0
    )
    assert errors == []
    page.close()


def test_a_thread_questions_done_press_wears_its_address_and_one_receipt(
    browser, serve
):
    """Done is a cell of the joined control, and the reader's newest move is its receipt.

    The Ask projection writes each option's key into the address slot the row keeps
    for it; Done kept none, so its chip was hung at the button's corner, half outside
    the group's frame — a stray `4` a blind drive could not place. And a tick followed
    by Done are two coordinates, each of which minted a receipt: "✓ Sent · just now"
    twice under one question. The newer move supersedes the older for what the reader
    is owed."""
    page, errors = open_page(
        browser, serve(next(p for p in EXAMPLES if p.stem == "ship-review"))
    )
    page.locator(".lf-threads-toggle").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-panel').classList.contains('open')"
    )
    question = page.locator(".lf-panel lf-options[choose]").first
    question.locator("lf-option:not([chosen]) > .lf-pick").first.click()
    round_trip(page)
    done = question.locator(".lf-done")
    done.focus()
    chip = done.locator(":scope > .lf-address")
    expect(chip).to_be_visible()
    frame = question.bounding_box()
    box = chip.bounding_box()
    assert (
        frame["x"] <= box["x"]
        and box["x"] + box["width"] <= frame["x"] + frame["width"]
    ), f"Done's address chip {box} stands outside the group {frame}"
    expect(page.locator(".lf-ask-addresses .lf-ask-address")).to_have_count(0)
    done.click()
    round_trip(page)
    receipts = question.locator(".lf-receipt")
    expect(receipts).to_have_count(1)
    expect(receipts).to_contain_text("Sent")
    assert errors == []
    page.close()
