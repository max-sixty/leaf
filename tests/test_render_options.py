"""Options, specimens, and decision presentation tests."""

import io
import json
import math
import re
from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner
from leaf import cli as cli_model
from leaf import events as events_model
from leaf import files as files_model
from leaf import render_checks as render_checks_model
from leaf import rendering as rendering_model
from leaf import schema as schema_model
from playwright.sync_api import expect
from render_support import (
    ASK_PAGE,
    ASK_WITH_CONTEXT_PAGE,
    ASKED_PAGE,
    CARRIED_PAGE,
    CHIP_PAGE,
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
    composer_quote,
    flip_point,
    leaf_page,
    open_page,
    page_registry,
    painted,
    panel_settled,
    resized,
    round_trip,
    select,
    sent_events,
    told,
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
    page.goto(serve(STACKED_OPTIONS_PAGE), wait_until="networkidle")
    rail = page.locator("#st-sd > dl.facts").bounding_box()
    prose = page.locator("#st-sd > p").bounding_box()
    card = page.locator("#st-sd").bounding_box()
    assert rail["width"] > card["width"] * 0.8, (
        "the rail still docks in a row this narrow"
    )
    assert rail["y"] + rail["height"] <= prose["y"], "the case has to clear the rail"
    page.close()


def test_settled_options_collapse_without_going_out_of_reach(browser, serve):
    """A settled decision reads as one line and the cards behind it stop spending
    the page's height — but they are hidden, not gone, so everything that used to
    reach them still does: the disclosure opens them, and a comment anchored in
    one opens the group on its way to the passage. A collapse a comment can't see
    through is worse than no collapse at all, because the thread still lists the
    quote and clicking it lands nowhere.

    The line itself is in reach too, which is the harder half: while the group is
    collapsed it is the only place the decision is stated, and it is written into a
    disclosure — chrome, and a control. And naming the card there means the page now
    says the card's lede twice, so the third part asks the one thing that buys: a
    comment made on the card lands on the card.

    Which way the disclosure stands is the row's own expanded state and nothing
    besides: the group's markup is the author's, and opening a settled decision is
    reading rather than editing, so no version and no log has a word to say about
    it."""
    page, errors = open_page(
        browser, serve(SETTLED_PAGE, anchored=[("opt-strict", "arrives logged out")])
    )
    group = page.locator("#transport")
    height = "el => Math.round(el.getBoundingClientRect().height)"

    assert errors == []
    collapsed = group.evaluate(height)
    assert page.locator("#transport lf-option:visible").count() == 0
    row = page.locator("#transport .lf-settled")
    assert row.inner_text().startswith("Settled: Lax cookie")
    assert row.get_attribute("aria-expanded") == "false"

    row.click()
    opened = group.evaluate(height)
    assert page.locator("#transport lf-option:visible").count() == 3
    assert opened > collapsed * 3, (
        f"collapsing saved {opened - collapsed}px of {opened}px — a settled group "
        f"that still costs most of its open height isn't a sweep"
    )
    # Open is the row's own expanded state and nothing else. The group wore an `open`
    # attribute here too, in a namespace its entry closes, which no version carries and
    # no consumer reads — while shallowSigs, whose exclusion list is exactly what no
    # version can assert, counted it as state the author had written. The render gate
    # asks the same of every example and cannot reach this moment: a group arrives
    # closed, and nothing it does opens one.
    assert row.get_attribute("aria-expanded") == "true"
    assert (
        page.evaluate(render_checks_model.UNDECLARED_ATTRS, page_registry(page)) == []
    ), "opening the group left an attribute on a widget its entry never declared"

    row.click()  # closed again, so the reveal below has something to open

    # While it is closed the row is the decision's only visible statement, so the part of
    # it naming the card has to be quotable — and a drag across it must not toggle the
    # disclosure it lives in, which is the mouseup of that drag.
    title = page.locator("#transport .lf-settled [data-lf-said]")
    box = title.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    assert (
        page.evaluate("() => getSelection().toString()").strip()
        == "Settled: Lax cookie"
    )
    expect(page.locator("#opt-strict")).to_be_hidden()
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert composer_quote(page)["text"].strip("“”") == "Settled: Lax cookie"
    page.keyboard.press("Escape")

    # The row names the chosen card, so the page now says "Lax cookie" twice and both
    # copies are quotable. A comment on the card's own lede has to land on the card —
    # the row comes first in document order, which is where a search on the quote alone
    # would put it.
    #
    # Dropping the selection first is the user's own next move: a press that lands
    # inside a live selection is that selection's, so the row would not open under it.
    page.locator("#lede").click()
    row.click()
    expect(
        page.locator("#opt-lax")
    ).to_be_visible()  # until-found keeps a box either way
    lede = page.locator("#opt-lax > strong")
    box = lede.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    page.locator(".lf-composer textarea").fill("which copy is this on?")
    page.get_by_role("button", name="Comment", exact=True).click()
    # Two, not one: this page arrived carrying a mark, so waiting for any at all is a
    # wait that was over before the gesture started.
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 2")
    # Both marks on the page: the one this fixture arrived carrying, and the new one.
    assert sorted(
        page.evaluate(
            "() => [...CSS.highlights.get('lf-mark')].map(r => "
            "r.startContainer.parentElement.closest('[id]').id)"
        )
    ) == [
        "opt-lax",
        "opt-strict",
    ], "the comment landed on the summary line rather than the card it was made on"
    row.click()  # closed again, so the reveal below has something to open

    # Sending opened the panel, so the thread is already listed. Its quote is on a card
    # the collapse is hiding, and following it has to bring the card back.
    page.locator(".lf-panel .lf-quote", has_text="arrives logged out").click()
    assert page.locator("#opt-strict").is_visible(), (
        "clicking a thread's quote must open the group holding it"
    )
    page.close()


def test_a_printed_page_says_which_option_carries_the_pick(browser, serve):
    """Print drops the runtime's own layer as one thing, and the controls a widget
    injects with it: on paper there is nothing to press. The pick's mark is a control
    and a statement at once, though, so dropping it takes the statement too — and a
    settled group loses its summary row the same way, leaving a printed decision
    stated in the ok ring alone, a colour greyscale drops.

    So on paper a choose group renders as one that was never choosable: the marks
    offering a pick go, the one on the card carrying it stays and says so, and the
    strip of room the marks need is reserved where a mark shows rather than on
    every card. Which of the two a mark is saying is the label's own declaration
    (relabel), so paper needs no rule naming this widget — the same reason a tab
    strip goes while each panel's label comes back."""
    page, errors = open_page(browser, serve(SETTLED_PAGE))
    row = page.locator("#transport .lf-settled")
    expect(row).to_contain_text("Settled: Lax cookie")
    expect(page.locator(".lf-banner")).to_be_visible()

    # The strip the mark sits in: what the card's bottom padding holds over its own
    # base, so the measure follows the theme's spacing instead of pinning a number.
    # Read against the top, which is the card's own padding on every side the group
    # has not claimed. The leading side is claimed — a choose group reserves the
    # keyboard address column there, `settled` included — so a base taken from it was
    # the width of that column, and the strip came out as the two numbers' difference.
    strip = """el => parseFloat(getComputedStyle(el).paddingBottom) -
                     parseFloat(getComputedStyle(el).paddingTop)"""
    pick = page.locator("#opt-lax .lf-pick")
    page.emulate_media(media="print")
    expect(
        page.locator(".lf-banner")
    ).to_be_hidden()  # the whole layer, by its own root
    expect(
        row
    ).to_be_hidden()  # the disclosure is a screen affordance; paper has the cards
    expect(pick).to_be_visible()
    expect(pick).to_have_text("chosen")
    expect(page.locator("#opt-strict .lf-pick")).to_be_hidden()
    assert page.locator("#opt-strict").evaluate(strip) == 0, (
        "a card whose mark can't print is holding room for it — an empty strip "
        "under a card the printed page says nothing about"
    )

    page.emulate_media(media="screen")
    row.click()
    expect(page.locator("#opt-strict")).to_be_visible()
    assert page.locator("#opt-strict").evaluate(strip) > 0, (
        "on screen the pick can still land here, and the card has to already hold "
        "the room or picking it moves the box"
    )
    assert errors == []
    page.close()


def test_a_pick_the_page_only_reports_can_still_be_pointed_at(browser, serve):
    """A group with no `choose` still says which option the document carries, and
    that word is a thing to say rather than a thing to work. So it goes the way
    every other word the page says goes: past the gate that hunts words on screen
    no selection can reach, and under a drag that raises the Comment button.

    It shipped the other way round. The mark is one element in two shapes — a
    press where there is a pick to make, an inert span where there isn't — and the
    inert one wore the press's `.lf-ui`, which anchoring skipped, so a user
    could read "chosen" and not point at it. Every shipped example declares
    `choose`, so the render suite never rendered the inert shape and nothing said
    so. The press was out of reach for longer and for a different reason, which
    test_a_pick_offered_can_be_pointed_at_too covers.

    Quotable is half a pair, so the other half is here too: the diff parses the
    base version unupgraded, where no mark exists at all, and must not read this
    one as a change nobody wrote."""
    url = serve(CARRIED_PAGE)
    assert rendering_model.render_version(browser, url) == []

    page, errors = open_page(browser, url)
    mark = page.locator("#c-lax .lf-pick")
    assert mark.get_attribute("role") is None, "nothing to press means no button role"
    box = mark.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    assert page.evaluate("() => getSelection().toString()").strip() == "chosen", (
        "a drag across the mark selected nothing — the state is painted, not said"
    )

    page.locator(".lf-fab").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'block'"
    )
    assert composer_quote(page)["text"].strip("“”") == "chosen"
    page.locator(".lf-composer textarea").fill("say which version chose it")
    page.get_by_role("button", name="Comment", exact=True).click()
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert painted(page, "lf-mark") == "chosen"

    # A second version rewording the option nobody picked. The mark is written by
    # the runtime and stands in no version file, so the anchor on it has to be
    # found again in the page the user now has — and read as no change,
    # since the base version this diff loads has no mark in it at all.
    d = serve.page_dir
    (d / "versions" / "v2.html").write_text(
        CARRIED_PAGE.replace("Suits the mobile client", "Suits the mobile client best")
    )
    events_model.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "two"}
    )
    page.wait_for_url("**/v2.html")
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    expect(page.locator(".lf-thread .lf-quote.detached")).to_have_count(0)

    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map(e => e.id)"
    ) == ["c-bearer"], "the diff read the mark as text the base version lacked"
    assert errors == []
    page.close()


def test_a_pick_offered_can_be_pointed_at_too(browser, serve):
    """The same words on the other shape of mark, in a group that takes a pick. This
    one was out of reach for a reason no marker could fix: the mark was a <button>,
    and no engine starts a pointer selection inside a form control, so "chosen" was on
    screen and unselectable however it was declared. A press is a span wearing the role
    now, which is what makes the drag below possible at all.

    Two things then have to hold at once. The drag has to select rather than pick — its
    mouseup lands on the very control it crossed — and the mark has to stay pressable,
    or the fix has traded a word nobody can quote for a decision nobody can make."""
    page, errors = open_page(browser, serve(SETTLED_PAGE))
    page.locator(
        "#transport .lf-settled"
    ).click()  # open the group; the cards are hidden
    mark = page.locator("#opt-lax .lf-pick")
    expect(mark).to_have_text("chosen")

    # Where the theme puts it: one line along the card's own bottom edge, in the same
    # place whichever word it carries. Pinned because the mark now declares itself the
    # page speaking, and the marker it declares with is the one the theme's chip band is
    # selected by — matched bare, the mark came out a pill at the head of the card and
    # every assertion here still passed.
    #
    # The same place, not the same box. An offer says nothing, so the mark on a card
    # nobody has picked is a held space and the picked one grows a word into it. What the
    # matching box used to stand for — that a pick shifts nothing — is asked of the card
    # itself further down, which is the fact rather than a proxy that happened to imply it.
    seat = """el => { const r = el.getBoundingClientRect();
                      const card = el.closest('lf-option').getBoundingClientRect();
                      return [Math.round(card.bottom - r.bottom),
                              Math.round(r.left - card.left)]; }"""
    assert mark.evaluate(seat) == page.locator("#opt-strict .lf-pick").evaluate(seat)
    up, over = mark.evaluate(seat)
    assert mark.bounding_box()["height"] < 24 and up < 16 and over < 20, (
        f"the mark is not a one-line caption on the card's bottom-left: {[up, over]}"
    )

    box = mark.bounding_box()
    y = box["y"] + box["height"] / 2
    # Right to left: the ✓ ring is not text.
    select(page, (box["x"] + box["width"] - 2, y), (box["x"] + 2, y))
    assert page.evaluate("() => getSelection().toString()").strip() == "chosen"
    expect(page.locator("#transport > lf-option[chosen]")).to_have_count(1)
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert composer_quote(page)["text"].strip("“”") == "chosen"
    page.keyboard.press("Escape")

    # Still a control: clicking the card that holds the pick clears it, and the keyboard
    # reaches the mark and works it the way the <button> did.
    page.evaluate("() => getSelection().removeAllRanges()")
    strict = page.locator("#opt-strict")
    strict.click()
    expect(page.locator("#opt-strict[chosen]")).to_have_count(1)

    # And the card it lands on is the same box after the pick as before it: the room a
    # picked mark's word needs is held on every card in the group, so the word grows into
    # space already reserved. That is the fact the matching mark boxes above used to stand
    # in for, and the one the user feels — a card that resized under the pointer takes
    # the next gesture's aim with it.
    #
    # Measured across an empty group rather than across a swap. Moving the pick from one
    # card to another gives the strip back exactly as fast as it takes it — and in the
    # days the group was a grid, the row stood as tall as its tallest cell either way —
    # so a swap can hold still with the reservation deleted. Clearing the pick first is
    # what makes the room actually go missing.
    box = """el => { const r = el.getBoundingClientRect();
                     return [Math.round(r.width), Math.round(r.height)]; }"""
    strict.click()  # clicking the pick clears it, so now the group holds no answer
    expect(page.locator("#transport > lf-option[chosen]")).to_have_count(0)
    empty = strict.evaluate(box)
    strict.click()
    expect(page.locator("#opt-strict[chosen]")).to_have_count(1)
    assert strict.evaluate(box) == empty, (
        f"answering the group resized the card it was answered on: {empty} -> "
        f"{strict.evaluate(box)}"
    )
    page.locator("#opt-bearer .lf-pick").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#opt-bearer[chosen]")).to_have_count(1)

    # And the pair the quotable half always comes with. This mark is the one element on
    # any page wearing the chrome class and the page-speaking marker at once, so it is the
    # only case where the anchor pass's reading and the diff's can come apart: the base
    # version is parsed unupgraded and has no mark in it at all. Read as text, the card
    # carrying the pick lights up as changed on every revision.
    #
    # v2 rewords a third card, so the card the diff should mark and the card wearing the
    # mark are different ones — with the pick on the reworded card there is nothing to
    # see, which is how this passed while reading the mark as text.
    d = serve.page_dir
    (d / "versions" / "v2.html").write_text(
        SETTLED_PAGE.replace("arrives logged out", "arrives logged out every time")
    )
    events_model.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "two"}
    )
    page.wait_for_url("**/v2.html")
    expect(page.locator("#opt-bearer[chosen]")).to_have_count(
        1
    )  # replay carried the pick
    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map(e => e.id)"
    ) == ["opt-strict"], "the diff read a pick mark as text the base version lacked"
    assert errors == []
    page.close()


def test_a_card_group_taking_a_pick_reads_as_one_control(browser, serve):
    """The offer is the group's, made once, rather than a word written on every member.

    A card group under `choose` draws the border and its options become cells inside it,
    sharing hairlines: a set of alternatives at one size is what says a decision is
    waiting, so no option has to caption itself "choose". What the theme deletes is only
    the offer — a picked mark still says where the pick sits, which is the page's only
    statement of that and the one paper keeps.

    Pinned because the rules making the group one control are ranked against the ones
    making each option a card, and losing that race leaves a page that looks exactly as it
    did while saying nothing about being answerable — which reads as a feature nobody
    wired up rather than as a fault. The mark is measured against its own ring for the
    same reason: "no word" is the claim, and a mark exactly as wide as the dot it draws
    is the only way to make it without naming a font size."""
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

    mark = page.locator("#opt-shim .lf-pick")
    box = """el => [Math.round(el.getBoundingClientRect().width),
                    Math.round(parseFloat(getComputedStyle(el, '::before').width)),
                    getComputedStyle(el, '::before').visibility]"""
    width, ring, drawn = mark.evaluate(box)
    assert width == ring, (
        f"the resting mark carries more than its ring: {width} vs {ring}"
    )
    assert drawn == "hidden", "the ring is drawn on a card the group already speaks for"

    # And a reader arriving by keyboard can see where they landed. One control, one
    # ring: keyboard focus rings the group, in the same stroke and band as the ask
    # mark, so `n` landing here — which paints the mark and focuses the first pick in
    # one move — draws one ring rather than nesting two. The focused cell wore its own
    # inset ring once, and the first option of every group the walk reached read as
    # singled out. Which cell holds the keyboard is the wash, the paint the pointer's
    # hover already wears. Reached by Tab rather than focus(), because :focus-visible
    # is a fact about how focus arrived and a programmatic call is not the keyboard.
    # Read as a style rather than a width, because `outline: none` leaves
    # outline-width computing to the initial `medium`: a box drawing no ring at all
    # still reports 3px.
    mark.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    ring_on = """el => { const on = el.closest('lf-option');
                      const drawn = (e) => { const s = getComputedStyle(e);
                          return s.outlineStyle === 'none' ? 0 : parseFloat(s.outlineWidth); };
                      return [on.id, on.matches(':has(> .lf-pick:focus-visible)'),
                              drawn(on.parentElement), drawn(on), drawn(el),
                              getComputedStyle(on).backgroundColor
                                !== getComputedStyle(on.nextElementSibling).backgroundColor]; }"""
    on, held, group_ring, card_ring, mark_ring, washed = mark.evaluate(ring_on)
    assert (on, held) == (
        "opt-shim",
        True,
    ), f"Tab did not land on the mark: {on} {held}"
    assert group_ring > 0 and card_ring == 0 and mark_ring == 0, (
        f"the focus ring is on the wrong box: group {group_ring}, card {card_ring}, "
        f"mark {mark_ring}"
    )
    assert washed, "nothing says which cell the keyboard is on"
    # The ask mark is the same ring in the same band (--here-ring), so the landing
    # that paints the mark and hands over the focus in one move says "you are here"
    # once — the two facts resolve to identical paint on the same element, and an
    # element can only wear one outline. Driven with the walk's own key, so what is
    # measured is the landing the reader gets rather than a state the test staged.
    ring = "el => [getComputedStyle(el).outline, getComputedStyle(el).outlineOffset]"
    focused = page.locator("#approach").evaluate(ring)
    page.keyboard.press("n")
    expect(page.locator("#approach[data-lf-ask]")).to_have_count(1)
    assert page.locator("#approach").evaluate(ring) == focused, (
        "the walk's landing draws a different ring than the focus it hands over"
    )

    page.locator("#opt-shim").click()
    expect(mark).to_have_text("your pick")
    width, ring, drawn = mark.evaluate(box)
    assert width > ring and drawn == "visible", (
        f"the picked mark states the pick in no width at all: {width} vs {ring}, {drawn}"
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
    assert page.locator("#opt-stage .lf-pick").evaluate(box)[2] == "visible", (
        "no ring and no container leaves a copy saying nothing about a pick at all"
    )
    assert errors == []
    page.close()


@pytest.mark.parametrize("group", ["cards", "rows"])
def test_the_question_a_joined_group_asks_stands_with_its_answers(
    browser, serve, group
):
    """The question opens where the answers open, and clears the frame around them.

    A group under `choose` is one control and its members are cells of it, each holding
    its words off the drawn edge and opening at the address column the group reserves.
    The question is a cell too. It was not treated as one: the block naming the cells
    named the two kinds it expected — the authored options and the cell the reader
    writes their own in — and the
    question is written by the runtime from `x-says`, so it arrived as a third kind with
    no rule to meet it. What shipped was a question set hard into the frame's top-left
    corner, a full address column to the left of every word it was a question about,
    with a band of dead ground under the hairline below it.

    Both forms, because which one a group takes is a fact about its options and neither
    states its own answer to this. And read as a column rather than as a number: what
    makes a question and its alternatives one reading is that they open at the same
    place, whatever that place is."""
    page, errors = open_page(browser, serve(ASKED_PAGE))
    said = page.locator(f"#{group} > [data-lf-said='label']")
    expect(said).to_have_count(1)

    edges = """el => { const r = el.getBoundingClientRect();
                       const s = getComputedStyle(el);
                       return {left: r.left + parseFloat(s.paddingLeft),
                               top: r.top + parseFloat(s.paddingTop),
                               bottom: r.bottom}; }"""
    frame = page.locator(f"#{group}").evaluate(
        """el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
                   return {left: r.left + parseFloat(s.borderLeftWidth),
                           top: r.top + parseFloat(s.borderTopWidth)}; }"""
    )
    question = said.evaluate(edges)
    answer = page.locator(f"#{group} > lf-option").first.evaluate(edges)

    assert abs(question["left"] - answer["left"]) < 1, (
        f"the question opens at {question['left']:.0f} and its answers at "
        f"{answer['left']:.0f}, so they read as two columns rather than one"
    )
    assert question["left"] - frame["left"] > 4, (
        "the question's words stand against the frame the group draws"
    )
    assert question["top"] - frame["top"] > 4, (
        "the question's words stand against the top of the frame the group draws"
    )

    # The hairline under the question is the whole of what separates it from the first
    # answer, so there is nothing between them: the 8px it wears leading an unjoined
    # group is a second way to say what the line already says, and it reads as a rule
    # floating in a band of nothing.
    gap = (
        page.locator(f"#{group} > lf-option").first.evaluate(
            "el => el.getBoundingClientRect().top"
        )
        - question["bottom"]
    )
    assert gap < 0.5, f"the seam under the question floats {gap:.0f}px above the answer"

    # The theme writes the question twice — the pseudo is what a page carrying no script
    # is drawn from, and the joined control is drawn there too — so both writings answer
    # this the same way or the two renderings disagree about where the question sits.
    assert page.locator(f"#{group}").evaluate(
        "el => getComputedStyle(el, '::before').padding"
    ) == said.evaluate("el => getComputedStyle(el).padding"), (
        "the scriptless rendering of the question is inset differently from the one the "
        "runtime writes"
    )
    assert errors == []
    page.close()


def test_a_settled_group_asks_its_question_above_the_answer(browser, serve):
    """A question leads, including where the group has already been answered.

    Collapsed, a settled group is one line naming what was chosen, and the question is
    the only thing on the page that says what was being chosen between. Rendered under
    that line it read as an afterthought with nothing beneath it — and a reader met the
    answer before learning there had been a question.

    The placement is the runtime's, not the theme's: a settled group lays its members out
    in normal flow, so DOM order is the only order there is, and the disclosure is built
    during the upgrade, before the `x-says` pass runs. That pass steps past generated
    chrome to keep the page's words beside the page's other words — which is right at the
    trailing edge, where chrome stands next to the last of them, and wrong at the leading
    edge, where a module puts one there to speak for the whole element."""
    url = serve(ASKED_PAGE)
    # The same widget, same markup, in the other place a group can stand. Which of the
    # two writers gets there first is reversed in here — the panel renders a message's
    # words into a detached body before any element connects, where the page upgrades
    # first and renders words after — so this is the reading that says the order does
    # not depend on that.
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "version": 1,
            "text": "And settled in here.",
            "markup": '<lf-options id="th-done" choose settled label="Where, again?">'
            '<lf-option id="th-redis" chosen><strong>Redis</strong></lf-option>'
            '<lf-option id="th-pg"><strong>Postgres</strong></lf-option>'
            "</lf-options>",
        },
    )
    page, errors = open_page(browser, url)
    page.keyboard.press("c")
    expect(page.locator(".lf-panel")).to_be_visible()

    top = "el => el.getBoundingClientRect().top"
    for group in ("done", "th-done"):
        expect(page.locator(f"#{group} .lf-settled")).to_have_count(1)
        question = page.locator(f"#{group} > [data-lf-said='label']").evaluate(top)
        summary = page.locator(f"#{group} .lf-settled").evaluate(top)
        assert question < summary, (
            f"#{group}'s question is drawn at {question:.0f} and its answer at "
            f"{summary:.0f}, so the group states what it settled before what it asked"
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
    page, errors = open_page(browser, serve(ASKED_PAGE))
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
    reader = next(c for c in cells if "lf-conversation" in c["what"])
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

    # …but takes nothing back. Nothing pressable: no grips, and no mark wearing
    # the button role — an unpicked quoted card carries no mark at all, exactly as
    # a group that never declared `choose`. A click chooses nothing either (the
    # choose path sets `chosen` before it sends, so a pick would show here).
    assert page.locator('#quoted-group .lf-pick[role="button"]').count() == 0
    assert page.locator("#quoted-board .lf-grip").count() == 0
    # Nor a cell to write another option in: an exhibited question takes no answer of
    # either kind, and a box is the one that would have looked answerable.
    assert page.locator("#quoted-group .lf-say").count() == 0
    page.locator("#q-shim").click()
    assert page.locator("#quoted-group lf-option[chosen]").count() == 0

    # The document's own state still reads: the settled group's authored pick
    # wears its mark, with nothing to press.
    assert page.locator("#quoted-settled .lf-pick:not([role])").count() == 1

    # A quoted suggestion shows what a pending change looks like — both slots
    # marked — and grows nothing to settle it with, so it is also not the
    # banner's to count or Accept all's to decide.
    assert page.locator("#quoted-suggestion lf-old").is_visible()
    assert page.locator("[data-lf-for='quoted-suggestion']").count() == 0
    expect(page.get_by_role("button", name="Accept all (1)")).to_be_visible()

    # The control: the same markup unquoted wires all of it.
    assert page.locator('#live-group .lf-pick[role="button"]').count() == 2
    assert page.locator("#live-board .lf-grip").count() == 1
    assert page.locator("[data-lf-for='live-suggestion']").count() == 1

    # Nor the room for one. A quoted card stands at the height of a card in a
    # group that never declared `choose`, because that is what it is; reserving
    # the mark strip would leave every exhibit trailing 32px of space that,
    # quoted, nothing can ever fill.
    pad = "el => getComputedStyle(el).paddingBottom"
    assert page.locator("#q-shim").evaluate(pad) != page.locator("#l-shim").evaluate(
        pad
    )

    # Nor in paint, which is the theme's own half of the promise rather than the
    # module's. Three offers a page makes standing still: the hand a card wears, the
    # joined box a group of them is drawn as, and the rail each card gives up to a
    # keyboard address. All three are withheld by the affordance rules excluding what
    # stands inside a painted exhibit (data-lf-exhibit), so a rule that lost its
    # exclusion shows here while every handler stays unwired. The live pair is the
    # control — without it a theme that had stopped drawing the offer at all would
    # read exactly like one that withholds it from the exhibit.
    offer = """el => { const cs = getComputedStyle(el);
        return { cursor: cs.cursor, box: cs.borderTopWidth, rail: cs.paddingLeft }; }"""
    quoted_card, live_card = (
        page.locator(sel).evaluate(offer) for sel in ("#q-shim", "#l-shim")
    )
    quoted_box, live_box = (
        page.locator(sel).evaluate(offer) for sel in ("#quoted-group", "#live-group")
    )
    assert live_card["cursor"] == "pointer" and live_box["box"] != "0px", (
        "the live group makes no offer either, so the exhibit's missing one says "
        f"nothing: card {live_card}, group {live_box}"
    )
    assert quoted_card["cursor"] != "pointer", (
        f"a quoted card invites the pointer: {quoted_card['cursor']}"
    )
    assert quoted_box["box"] == "0px", (
        f"the exhibit is drawn as a control to answer: {quoted_box['box']} border"
    )
    # The rail is the third at-rest offer and the quietest: a live card gives up its
    # leading inches to the digit a keyboard pick answers by, and an exhibit takes no
    # keys, so room held there is room held for an address that can never arrive.
    assert quoted_card["rail"] != live_card["rail"], (
        f"the exhibit reserves the keyboard rail a live card does: {quoted_card['rail']}"
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

    # The exception, once that group is open: the card the document marks does
    # carry a mark, so it keeps the strip a live pick would.
    assert page.locator("#q-lax").evaluate(pad) == page.locator("#l-shim").evaluate(pad)

    # And the lift, which needs both groups open to reach: a settled group comes apart
    # again when the reader opens it, and loose cards answer the pointer by rising where
    # joined cells answer with a wash. Read here rather than with the other two because
    # opening the quoted group is what the lines above are about.
    #
    # Three cards, because the lift is three rules and each states the ring it layers
    # over — a plain card, the one the document recommends, and the one it records as
    # chosen. They differ by one attribute in the selector and carry the same exclusion,
    # so the pair that lost one would be the pair nothing here hovered.
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
        ("#q-signed", "#l-signed", "recommended"),
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


def test_the_pointer_does_not_take_a_cells_status_with_it(browser, serve):
    """A cell says its status in a bar beside its words, and the aim is a wash: two
    facts about the same box, so both are true at once and the pointer arriving changes
    only its own.

    Which the two forms of the same statement did not manage while they shared the one
    property. The cell's status rode a box-shadow, so did a loose card's ring, the
    card's hover put a lift there, and the rules that restated the ring under the lift
    carried the status attribute — one class column, enough to outrank the cell's own
    paint in a group the card rules were never meant to reach. What a reader got for
    pointing at the option the page recommends was the status gone, a 1px ring in its
    place with the group's clip cutting away its side runs, and a drop shadow inside a
    box with no room to cast one.

    So the card's channels are separate (--lf-ring, --lf-lift), the cell's bar is drawn
    where neither reaches, and the two forms are alternatives rather than layers
    (--lf-joined): a cell is never handed the dressing it would have to undo. Read on
    the recommended cell and its plain neighbour, since "unchanged" is also what a cell
    with nothing to say returns.

    The bar's own place is held too. It stands in the column the group reserves for a
    keyboard address, clear of the leading edge, because the ask around a control wears
    the reader's band three pixels outside that edge and a second accent bar just inside
    it cannot be told from the first."""
    page, errors = open_page(browser, serve(SPECIMEN_PAGE))
    page.wait_for_function(
        """() => document.querySelector('#live-group')
                 .getAnimations({subtree: true}).length === 0"""
    )
    paint = """el => { const s = getComputedStyle(el), bar = getComputedStyle(el, '::before');
                       return [bar.backgroundColor,
                               [parseFloat(bar.left), parseFloat(bar.width)],
                               s.borderTopStyle === 'none'
                                 ? 0 : parseFloat(s.borderTopWidth),
                               parseFloat(s.borderTopLeftRadius),
                               s.backgroundColor]; }"""
    marked, plain = page.locator("#l-stage"), page.locator("#l-shim")
    stripe, (left, width), border, radius, fill = marked.evaluate(paint)
    assert (border, radius) == (0, 0), (
        f"a cell of a joined group wears a card's border and corner: {border}, {radius}"
    )
    assert stripe != plain.evaluate(paint)[0], (
        "the recommended cell and its plain neighbour carry the same paint, so this "
        "reads nothing about the recommendation"
    )
    # The column as the cell spends it, rather than the token's own text: the term is a
    # calc over the chip's box, so `getPropertyValue` answers with the expression and a
    # number read off it is NaN — which compares false against everything and reports a
    # bar in the wrong place as convincingly as a real one.
    column = marked.evaluate(
        "el => parseFloat(getComputedStyle(el).paddingInlineStart)"
    )
    assert 0 < left and left + width < column, (
        f"the bar at {left}…{left + width} does not stand inside the {column}px the "
        "group reserves, so it is back on the edge the reader's band runs down"
    )
    marked.hover()
    expect(marked).not_to_have_css("background-color", fill)
    assert marked.evaluate(paint)[:4] == [stripe, [left, width], 0, 0], (
        f"the pointer took the recommendation with it: {marked.evaluate(paint)} "
        f"against {[stripe, [left, width], border, radius]} at rest"
    )

    # The column holds two things, and the other one arrives only for the keyboard. Both
    # terms of the column follow the type — the chip's box does by declaration
    # (--lf-key-box), and the bar hangs off the column's trailing edge — so this is what
    # says the column is still the sum of what stands in it. A package redeclaring the
    # ladder is the case: written as a number, the column stayed the size the chip was
    # when somebody measured it, and the chip grew into the bar's three pixels.
    page.mouse.move(0, 0)
    mark = page.locator("#l-stage .lf-pick").first
    mark.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    chip = page.locator("#l-stage .lf-address")
    expect(chip).to_be_visible()
    ends = chip.evaluate(
        """el => el.getBoundingClientRect().right
                 - el.closest('lf-option').getBoundingClientRect().left"""
    )
    assert ends < left, (
        f"the keyboard address runs to {ends} and the status bar opens at {left}, so "
        "the column is holding one of them in the other's room"
    )
    assert errors == []
    page.close()


def test_a_marked_card_keeps_the_shadow_its_status_is_drawn_in(browser, serve):
    """A card says its status in a box-shadow channel and the runtime paints its marks
    in an outline, so a card the reader has anchored a comment to says both at once.

    They collided over a name. The channel is `--lf-ring`; a rule naming which here ring
    it draws reached for the same word, and `.lf-mark-el.lf-mark-here` outranks the
    card's own rule by a class column — so the moment a mark landed on a card, the name
    it wrote was what `box-shadow: var(--lf-ring), var(--lf-lift)` resolved to. An
    identifier is no shadow, the whole declaration went invalid at computed-value time,
    and the card lost its recommendation ring and its lift together while the reader was
    pointing at it. Nothing was wrong on screen anywhere else, and no reading asked.

    So the two are spelled apart (`--lf-here-ring`), and this is what says they still
    are. The mark classes are applied directly because they are the mechanism: they are
    what `markHere` paints on an element a focused thread is anchored to.

    Read on all three card rules, since each states the ring it layers over and a
    rename that missed one would leave the other two clean."""
    page, errors = open_page(browser, serve(SPECIMEN_PAGE))
    page.locator("#live-settled .lf-settled").click()
    page.wait_for_function(
        """() => document.querySelector('#live-settled')
                 .getAnimations({subtree: true}).length === 0"""
    )
    read = """el => {
        const cs = getComputedStyle(el);
        return [cs.boxShadow,
                cs.getPropertyValue('--lf-ring').trim(),
                cs.getPropertyValue('--lf-here-ring').trim()];
    }"""
    mark = "el => el.classList.add('lf-mark-el', 'lf-mark-here')"
    for card, which in (
        ("#l-bearer", "plain"),
        ("#l-signed", "recommended"),
        ("#l-lax", "chosen"),
    ):
        rest, channel, _ = page.locator(card).evaluate(read)
        assert rest != "none", (
            f"a {which} card draws no shadow at rest, so this reads nothing about one"
        )
        page.locator(card).evaluate(mark)
        marked, channel_now, name = page.locator(card).evaluate(read)
        # Non-vacuity: the mark rule has to have reached this box, or the comparison
        # below is one box against itself.
        assert name == "element-mark", (
            f"the mark left {name!r} on the {which} card rather than its ring's name, "
            "so the rule this is written against never applied and the shadow was "
            "never at risk"
        )
        assert (marked, channel_now) == (rest, channel), (
            f"marking the {which} card moved its shadow: {marked} in channel "
            f"{channel_now!r}, against {rest} in {channel!r} before"
        )
    assert errors == []
    page.close()


def test_one_band_says_where_the_reader_is_standing(browser, serve):
    """The reader's band is drawn once, on the outermost box that claims it.

    A joined group is focused as one control and draws the band itself, which is the
    same band and the same stroke the ask it stands in wears. Where the ask is the
    group — most questions — the two are one element and one ring. Where an author has
    written the region out, so the heading and the premise arrive with the control, the
    ask is a box around the group and the two rings nested: one around a paragraph of
    context, another a few pixels inside it, saying the same thing at two sizes.

    So the group's is the one that stands down. Its half of the fact — which control,
    and which cell of it — is already said by the washed cell and the address chips,
    while the ask's ring is what the walk aims at and what the arrival scrolls to."""
    page, errors = open_page(browser, serve(ASK_WITH_CONTEXT_PAGE))
    mark = page.locator("#storage-evict .lf-pick")
    mark.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    expect(page.locator("#storage-ask[data-lf-ask]")).to_have_count(1)
    drawn = """el => { const s = getComputedStyle(el);
                       return s.outlineStyle === 'none' ? 0 : parseFloat(s.outlineWidth); }"""
    assert page.locator("#storage-ask").evaluate(drawn) > 0, (
        "the ask the reader is standing in draws no band, so nothing says where they are"
    )
    group = page.locator("#storage-options")
    assert group.evaluate(
        "el => el.matches(':has(> lf-option > .lf-pick:focus-visible)')"
    ), "the keyboard is not on the group's own mark, so this reads nothing"
    assert group.evaluate(drawn) == 0, (
        "the group draws the reader's band inside the ask already wearing it"
    )
    assert errors == []
    page.close()


def test_a_pick_does_not_bury_the_news_that_it_is_unrecorded(browser, serve):
    """An element wears one outline, so the group's own band gives way to the log's.

    Answering closes the ask, and what the group wears next is the news that the
    decision stands in replay and not yet in the page's own words. That ring and the
    band saying the keyboard is here are the same property on the same box, and the
    band was winning: a reader who picked by keyboard saw their pick reported as
    recorded until they tabbed away, which is the one moment the ring has nothing to
    add and the one moment it was drawn.

    Read as paint rather than as a rule, and against a probe wearing the state and
    nothing else, so a theme that recolours the news moves both sides together."""
    page, errors = open_page(browser, serve(SPECIMEN_PAGE))
    mark = page.locator("#l-stage .lf-pick")
    mark.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    page.keyboard.press("Enter")
    expect(page.locator("#live-group[data-lf-pending]")).to_have_count(1)
    assert page.locator("#l-stage").evaluate(
        "el => el.matches(':has(> .lf-pick:focus-visible)')"
    ), "the keyboard left the mark, so the two bands never met"
    news = page.evaluate("""() => {
        const probe = document.createElement('div');
        probe.setAttribute('data-lf-pending', '1');
        document.body.append(probe);
        const seen = getComputedStyle(probe).outlineColor;
        probe.remove();
        return seen;
    }""")
    expect(page.locator("#live-group")).to_have_css("outline-color", news)
    assert errors == []
    page.close()


def test_a_group_of_bare_labels_reads_as_a_question_about_the_page(browser, serve):
    """Which form a group takes is a fact about its options rather than an attribute
    saying so, and the whole of that fact is whether an option leads with a title. So
    one page carries both and neither knows about the other: the labels lay out as
    compact rows and the titled pair as full-width cards stacked down the page.

    Two things the lint cannot see. A resting mark shows no word in either form, because
    an offer states nothing a reader could disagree with — and what a *picked* mark says
    has to survive that, since it is the page's only statement of where the pick sits.
    What differs is the dot: a row draws one and a single-pick card does not. A card
    gives it up because the state has the whole cell to live in, while a row's is a
    column at the line's end with room reserved for it by name, so a row that stopped
    drawing there would end in a blank the width of the word it isn't saying. Both are
    asked here, since either could be the theme forgetting a rule rather than each form
    answering for itself. (What a card under `multiple` does instead is the next test's:
    that one is arity's, not the form's.) And a row's name is
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
    # the same way the comment panel writes an element anchor.
    ref = page.locator("#job-mounts .lf-ref")
    expect(ref).to_have_text("§ sec-mounts")
    assert ref.get_attribute("href") == "#sec-mounts"
    assert page.locator("#job-camera .lf-ref").count() == 0

    # No open mark says its word, in either form. The dot is where they part: a row's is
    # drawn and a single-pick card's is not, which is each form answering for the room it
    # reserved rather than one rule going missing. (Arity moves this too, which is why the
    # card side is read off `#bracket` rather than off the `multiple` card group beside it.)
    hidden = "el => getComputedStyle(el).fontSize"
    dot = "el => getComputedStyle(el, '::before').visibility"
    assert page.locator("#job-mounts .lf-pick").evaluate(hidden) == "0px"
    assert page.locator("#br-steel .lf-pick").evaluate(hidden) == "0px"
    assert page.locator("#job-mounts .lf-pick").evaluate(dot) == "visible"
    assert page.locator("#br-steel .lf-pick").evaluate(dot) == "hidden"

    page.locator("#job-heater").click()
    expect(page.locator("#job-heater[chosen]")).to_have_count(1)
    expect(page.locator("#job-heater .lf-pick")).to_have_text("your pick")
    assert page.locator("#job-heater .lf-pick").evaluate(hidden) != "0px"
    # The row's name, as the mark reports it back: what the author wrote, and not the
    # word the mark itself just added to the line. A chip is in it — authored markup,
    # the page's words about this option — and the mark's own "your pick" is not, which
    # is the whole of the distinction: a question answered must not read its own answer
    # back as part of what was asked, and nothing else the author wrote is the answer.
    assert (
        page.locator("#job-heater .lf-pick").get_attribute("aria-label")
        == "your pick: reversible Heat the bird bath — option 2 of 3"
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

    Arity is not the form, which is why the contrast is card against card. Both of the
    rules here were the list form's once, on the reading that a `multiple` group is a
    list of slots; `multiple` is orthogonal to which form a group takes, so a titled
    group asking "which of these" inherited neither and offered the reader nothing to
    count. Hence the second half: an unticked box is a fact about that option, not the
    group's offer said again, so it draws under `multiple` where a single-pick card —
    whose state has the whole cell to live in — gives it up.

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

    # An unticked slot is that option's own state under `multiple`, so the box draws with
    # nothing in it — the reader counts what is left to take. A single-pick card has no
    # such second question and keeps giving its box up.
    dot = "el => getComputedStyle(el, '::before').visibility"
    assert page.locator("#tl-clamp .lf-pick").evaluate(dot) == "visible", (
        "a card group asking 'which of these' draws no empty boxes, so the reader has "
        "nothing to count and no sign a second pick is on offer"
    )
    assert page.locator("#br-steel .lf-pick").evaluate(dot) == "hidden"

    # Paint, not metrics: the mark's box is the same in both arities, which is what lets
    # the row form's reserved column and the card's reserved strip stand unchanged.
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


def test_a_nested_questions_pick_is_not_part_of_its_outers_record(browser, serve):
    """Attribute records are sets owned by one recorded widget. A chosen option in a
    nested question must not enter the outer question's authored facet, or an outer log
    choice that exactly matches its markup is falsely painted as awaiting the author."""
    nested_choices = NESTED_ASK_PAGE.replace(
        '<lf-option id="out-drill">', '<lf-option id="out-drill" chosen>'
    ).replace('<lf-option id="in-now">', '<lf-option id="in-now" chosen>')
    url = serve(nested_choices)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "outer",
            "action": "choose",
            "detail": {"options": ["out-drill"]},
        },
    )

    page, errors = open_page(browser, url)
    expect(page.locator("#outer")).not_to_have_attribute("data-lf-pending", "1")
    expect(page.locator("#inner")).not_to_have_attribute("data-lf-pending", "1")
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

    assert [e for e in sent_events(serve.page_dir) if e["kind"] == "action"] == [], (
        "the reader working the evidence sent Claude a decision they never made"
    )

    # And the option's own words still answer it, which is what the card is for.
    page.locator("#ro-column-p").click()
    expect(page.locator("#ro-column > .lf-pick")).to_have_text("your pick")
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
    mark that ends the line. `#jobs` carries both against rows that carry neither, which
    is where either reads worst — rows lined up and one hanging mid-sentence — and a
    group of rows naming nothing is what the shipped examples haven't got, which is why
    the form shipped the first way.

    Each mark is read against the end of its own row rather than against its
    neighbours', so the column and its place are one reading: the rows are all one
    width, and a mark that is not at its line's end is not in the column either."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    ends = """() => [...document.querySelectorAll('#jobs > lf-option')].map(o => {
                const style = getComputedStyle(o);
                const inset = parseFloat(style.paddingRight) + parseFloat(style.borderSpacing);
                const m = o.querySelector('.lf-pick').getBoundingClientRect();
                return m.right - (o.getBoundingClientRect().right - inset);
              })"""
    assert page.evaluate(ends) == [0, 0, 0], (
        "a row's mark hangs where its label happened to end, or behind something the row "
        "said after it, so the group offers the reader no column of dots to aim down"
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
    expect(mark).to_have_text("your pick")
    assert mark.evaluate(box) == before, "the press moved the mark it landed on"
    assert errors == []
    page.close()


def test_a_chip_an_option_says_stands_with_the_rest_of_its_words(browser, serve):
    """A chip is the page's words and the apparatus after it is the module's, so the
    reader — and the file's reading of that same version — find the chip inside the
    row's own words rather than past the mark that ends the line.

    The rule was written against an attribute rendered by `x-says`, where the edge a
    pseudo-element would have taken stops being the element's own words the moment a
    module injects chrome, and appending put the page's words on the far side of it.
    A chip is authored markup now, written before the title, so it cannot land there by
    construction — which is the stronger form of the same guarantee, and this holds the
    outcome rather than the mechanism that used to threaten it."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    chip = page.locator("#job-heater > lf-chip")
    expect(chip).to_have_text("reversible")
    expect(page.locator("#job-heater > .lf-pick:last-child")).to_have_count(1)
    ref = page.locator("#job-heater .lf-ref").bounding_box()
    assert chip.bounding_box()["x"] < ref["x"], (
        "the chip stands before the row's apparatus"
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
    task's marker, an event's kind band and the ring on the recommended option each
    carried their whole meaning in colour, so a reader listening was handed every word
    around the fact and never the fact: done sounded exactly like blocked, and the
    page's own recommendation — the one thing a decision page is most for — was
    invisible to the reader with the least other way to find it.

    Declared (x-paints) rather than written into each module, which is what lets it
    reach the two widgets here that have no module at all, and read as the value or, for
    a flag carrying none, the attribute's own name. Said in text, because that is the
    one thing every screen reader announces in every mode — and therefore clipped to
    nothing, holding no room, and out of the selection, since a word the eye can't see
    is a word the clipboard has no business carrying."""
    page, errors = open_page(browser, serve(PAINTED_PAGE))
    for sel, word in (
        ("#e-dark", "failure"),
        ("#p-stage", "recommended"),
        ("#t-baffles", "blocked"),
    ):
        assert word in page.locator(sel).aria_snapshot(), (
            f"{sel} paints `{word}` and says nothing of it to a reader listening"
        )
    # The option that isn't recommended says nothing: the pass speaks a fact the page
    # holds, never one it merely has an attribute for.
    assert "recommended" not in page.locator("#p-once").aria_snapshot()

    room = page.locator(".lf-quiet").evaluate_all(
        """els => els.map(el => { const r = el.getBoundingClientRect();
             return [el.textContent, r.width, r.height,
                     getComputedStyle(el).userSelect]; })"""
    )
    assert len(room) == 3, f"one quiet word per painted fact, got {room}"
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
    _until(page, lambda t: t.sends >= 1, "sent the pick it was clicked for")
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


def test_an_agent_question_opens_another_thread_without_returning_the_ask(
    browser, serve
):
    """The proposed option remains with the agent while a separate thread asks.

    That clarification is owned by Comments' reader-facing queue; it is not also a
    page Ask, because the page's Ask is still the proposal the agent must incorporate.
    """
    url = serve(ASK_PAGE)
    page, errors = open_page(browser, url)
    asks = page.locator(".lf-asks")
    expect(asks).to_have_text("Asks (3)")
    asks.click()
    rows = page.locator("button.lf-asks-row")
    expect(rows).to_have_count(3)

    conversation = page.locator("#jobs > .lf-conversation")
    conversation.locator(".lf-say textarea").fill("Neither — do the camera first.")
    conversation.locator(".lf-say [role='button']").click()
    round_trip(page)
    expect(asks).to_have_text("Asks (2)")
    expect(rows).to_have_count(2)
    assert page.locator('.lf-asks-row[data-lf-at="jobs"]').count() == 0, (
        "the walk still steps to a question the reader has handed to the agent"
    )

    root = next(e for e in sent_events(serve.page_dir) if e["kind"] == "comment")
    assert root["response"] == {"kind": "version", "verb": "choose"}
    clarification = events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "version": 1,
            "anchor": {"section": "jobs"},
            "text": "The camera costs us the mounts this month. Still first?",
        },
    )
    told(page)
    expect(asks).to_have_text("Asks (2)")
    expect(page.locator('.lf-asks-row[data-lf-at="jobs"]')).to_have_count(0)
    expect(
        conversation.locator(
            f'.lf-conversation-thread[data-thread="{root["id"]}"] textarea'
        )
    ).to_have_count(0)
    expect(
        conversation.locator(
            f'.lf-conversation-thread[data-thread="{clarification["id"]}"] textarea'
        )
    ).to_have_count(1)
    assert errors == []
    page.close()


def test_a_question_owns_one_thread_in_the_page_and_panel(browser, serve):
    """The option a reader writes starts one log thread and becomes its page view.

    The page seat stays textual while Comments keeps the interactive conversation.
    Resolution removes the panel box but not the words, and a later version retaining
    the question sees the same whole-log conversation."""
    url = serve(ASK_PAGE)
    page, errors = open_page(browser, url)
    d = serve.page_dir

    conversation = page.locator("#jobs > .lf-conversation")
    box = conversation.locator(".lf-say textarea")
    send = conversation.locator(".lf-say [role='button']")
    # What the box is for, in both registers a reader has: the words on screen and the
    # name read aloud, saying the same thing. It names what the cell supplies rather
    # than the act of typing into it — a box under a menu that invites the reader to
    # say something invites an aside, when what it takes is the option nobody listed.
    assert box.get_attribute("placeholder") == "Another option"
    assert box.get_attribute("aria-label") == "Another option"
    assert send.get_attribute("aria-disabled") == "true"
    first_text = "Neither, really — do the camera and tell me what it costs."
    box.fill(first_text)
    assert send.get_attribute("aria-disabled") == "false"
    send.click()

    expect(page.locator("#jobs.lf-mark-el")).to_have_count(1)
    expect(conversation.locator(".lf-conversation-msg.user")).to_have_text(
        re.compile(re.escape(first_text))
    )
    expect(conversation.locator(":scope > .lf-say")).to_have_count(0)

    said = [e for e in sent_events(d) if e["kind"] == "comment"]
    assert [(e["anchor"], e["text"]) for e in said] == [
        ({"section": "jobs"}, first_text)
    ]
    root = said[0]
    assert root["response"] == {"kind": "version", "verb": "choose"}

    page.locator(".lf-comments").click()
    panel_settled(page)
    panel_thread = page.locator(f'.lf-thread[data-id="{root["id"]}"]')
    expect(panel_thread.locator(".lf-msg.user .lf-msg-body")).to_have_text(first_text)

    expect(conversation.locator("textarea")).to_have_count(0)
    panel_reply = panel_thread.locator("textarea")
    reply_text = "The camera first; include the mounting cost."
    panel_reply.fill(reply_text)
    panel_thread.get_by_role("button", name="Send", exact=True).click()
    round_trip(page)
    expect(panel_reply).to_have_value("")
    replies = [e for e in sent_events(d) if e["kind"] == "reply"]
    assert [(e["parent"], e["text"]) for e in replies] == [(root["id"], reply_text)]
    expect(conversation.locator(".lf-conversation-msg")).to_have_count(2)
    expect(panel_thread.locator(".lf-msg")).to_have_count(2)
    expect(conversation.locator("textarea")).to_have_count(0)

    panel_thread.get_by_role("button", name="Resolve", exact=True).click()
    expect(conversation.locator(".lf-conversation-resolved")).to_have_text("✓ Resolved")
    expect(conversation.locator("textarea")).to_have_count(0)
    expect(conversation).to_contain_text(first_text)
    expect(conversation).to_contain_text(reply_text)

    # Reopen is the same logged transition in either view; the inline projection
    # remains text-only. An agent close then carries attribution there, just as the
    # complete panel view does.
    expect(
        page.locator(f'.lf-details .lf-thread[data-id="{root["id"]}"]')
    ).to_have_count(1)
    page.locator(".lf-details summary").click()
    page.locator(f'.lf-details .lf-thread[data-id="{root["id"]}"] .lf-reopen').click()
    round_trip(page)
    expect(conversation.locator("textarea")).to_have_count(0)
    events_model.append_event(
        d,
        {
            "kind": "resolve",
            "author": "claude",
            "agent": "Indexer",
            "parent": root["id"],
        },
    )
    told(page)
    expect(conversation.locator(".lf-conversation-resolved")).to_have_text(
        "✓ Resolved by Indexer"
    )

    (d / "versions" / "v2.html").write_text(
        ASK_PAGE.replace('<h1 id="h">Three jobs</h1>', '<h1 id="h">Four jobs</h1>')
    )
    events_model.append_event(
        d, {"kind": "note", "author": "claude", "version": 2, "text": "Retitled"}
    )
    page.wait_for_url("**/versions/v2.html*")
    conversation = page.locator("#jobs > .lf-conversation")
    expect(conversation).to_contain_text(first_text)
    expect(conversation).to_contain_text(reply_text)
    expect(conversation.locator("textarea")).to_have_count(0)

    pinned, pinned_errors = open_page(browser, url, pin=True)
    expect(pinned).to_have_url(re.compile(r"/versions/v1\.html\?.*pin"))
    pinned_conversation = pinned.locator("#jobs > .lf-conversation")
    expect(pinned_conversation).to_contain_text(first_text)
    expect(pinned_conversation).to_contain_text(reply_text)
    expect(pinned_conversation.locator("textarea")).to_have_count(0)
    assert pinned_errors == []
    pinned.close()

    without_owner = re.sub(
        r'<lf-options id="jobs" choose multiple>.*?</lf-options>',
        '<p id="jobs-gone">This version no longer asks the jobs question.</p>',
        ASK_PAGE,
        count=1,
        flags=re.DOTALL,
    )
    (d / "versions" / "v3.html").write_text(without_owner)
    events_model.append_event(
        d,
        {"kind": "note", "author": "claude", "version": 3, "text": "Question removed"},
    )
    page.wait_for_url("**/versions/v3.html*")
    expect(page.locator("#jobs > .lf-conversation")).to_have_count(0)
    expect(page.locator(f'.lf-thread[data-id="{root["id"]}"]')).to_contain_text(
        reply_text
    )
    assert errors == []
    page.close()


def test_a_question_says_what_the_agent_is_doing_about_it(browser, serve):
    """A work line answers "is anyone on this", and the reader who asked from inside the
    widget's own box is the one least likely to open the panel to find out. One thread
    has one claim, so it is said at both of the thread's seats — the question's inline
    view and the panel's list are two renderings of one conversation, not a complete one
    and a lesser one.

    The word for a claim nobody is renewing comes with it. That reading is the banner's
    own, so a seat that showed the sentence and swallowed the silence would be telling
    the reader work is in hand on the strength of a claim the page has already stopped
    believing."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    d = serve.page_dir
    conversation = page.locator("#jobs > .lf-conversation")
    conversation.locator(".lf-say textarea").fill("Which of these is cheapest?")
    conversation.locator(".lf-say [role='button']").click()
    round_trip(page)
    held = next(e for e in events_model.read_events(d) if e["kind"] == "comment")["id"]
    work_line = conversation.locator(".lf-work-line")
    expect(work_line).to_have_count(0)

    def claim(claim_ts):
        files_model.write_json(
            d / "status.json",
            {
                "state": "working",
                "detail": "pricing the camera",
                "ts": events_model.now_iso(),
                "work": [
                    {
                        "subject": {"kind": "thread", "id": held},
                        "detail": "pricing the camera",
                        "ts": claim_ts,
                        "after": next(
                            e["seq"]
                            for e in events_model.read_events(d)
                            if e["id"] == held
                        ),
                    }
                ],
            },
        )
        told(page)

    claim(events_model.now_iso())
    expect(work_line).to_have_text(
        re.compile(r"^Claude is on this — pricing the camera\s*just now$")
    )
    page.evaluate(
        "() => { window.heldWorkLine = document.querySelector('.lf-work-line') }"
    )
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "author": "user",
            "version": 1,
            "text": "An unrelated page-level comment.",
        },
    )
    told(page)
    assert page.evaluate(
        "() => window.heldWorkLine === document.querySelector('.lf-work-line')"
    ), "an unrelated event replaced and re-announced an unchanged local work line"
    # Drawn, not merely present: the runtime's own sheet is scoped to .lf-chrome and
    # cannot reach a box in the page, so this seat's rule is the page theme's own and
    # a text assertion alone would pass over a line nobody can see.
    expect(work_line).to_be_visible()
    expect(work_line).not_to_contain_text("quiet")

    # The same silence the banner reads, at this seat: forty minutes with nothing
    # renewing the claim, while the page's own claim above it is as fresh as ever.
    claim(
        (datetime.now().astimezone() - timedelta(minutes=40)).isoformat(
            timespec="seconds"
        )
    )
    expect(work_line).to_contain_text("quiet")
    expect(work_line.locator("time")).to_have_text("40m ago")

    # Answering is what ends it, here as in the panel: nothing deletes a local record.
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "agent": "Claude",
            "parent": held,
            "text": "The camera is £40 less installed.",
        },
    )
    told(page)
    expect(work_line).to_have_count(0)
    assert errors == []
    page.close()


def test_a_widget_without_a_thread_says_what_the_agent_is_doing(browser, serve):
    """A page widget is a first-class work subject even before anybody comments.

    The same typed claim uses the two declaration-backed seats: prose takes a generated
    child directly, while an item widget uses the conversation box its declaration and
    module already provide. Neither invents a comment thread. Unrelated versions leave
    both claims standing; a typed later-version settlement ends exactly the work it
    names, and a claim made on v2 does not leak backward into a pinned v1 tab.
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
    page, errors = open_page(browser, url)
    d = serve.page_dir

    def claim(subject, detail):
        result = CliRunner().invoke(
            cli_model.cli,
            ["status", str(d), "working", detail, "--on", subject],
        )
        assert result.exit_code == 0, result.output
        told(page)

    claim("card-migration", "checking the shard")
    claim("jobs", "pricing the alternatives")

    card_line = page.locator("#card-migration > .lf-work-line")
    question_line = page.locator("#jobs > .lf-conversation > .lf-work-line")
    expect(card_line).to_have_text(
        re.compile(r"^Claude is on this — checking the shard\s*just now$")
    )
    expect(question_line).to_have_text(
        re.compile(r"^Claude is on this — pricing the alternatives\s*just now$")
    )
    expect(card_line).to_be_visible()
    expect(question_line).to_be_visible()
    card_words, card_age = card_line.locator(
        ":scope > span, :scope > time"
    ).evaluate_all("els => els.map(el => el.getBoundingClientRect().bottom)")
    assert abs(card_words - card_age) <= 1, (
        "the age splits a wrapped card sentence instead of following its last line"
    )
    expect(page.locator(".lf-thread")).to_have_count(0)
    expect(page.locator(".lf-panel .lf-work-line")).to_have_count(0)
    expect(card_line).to_have_class(re.compile(r"\blf-ui\b"))
    assert card_line.get_attribute("data-lf-gen") == "1"
    assert question_line.evaluate("el => el === el.parentElement.firstElementChild"), (
        "the question's work line is not the first thing in its conversation seat"
    )

    # An unrelated version changes neither coordinate.
    (d / "versions" / "v2.html").write_text(work_page)
    unrelated = CliRunner().invoke(
        cli_model.cli,
        ["version", "publish", str(d), "--version", "2", "--text", "Elsewhere"],
    )
    assert unrelated.exit_code == 0, unrelated.output
    page.wait_for_url("**/versions/v2.html*")
    expect(card_line).to_have_count(1)
    expect(question_line).to_have_count(1)

    # A new claim belongs to v2. The pinned v1 page still shows the older question
    # claim, but not work whose subject was claimed against a page later than its own.
    claim("card-migration", "checking the fallback")
    expect(card_line).to_contain_text("checking the fallback")
    pinned, pinned_errors = open_page(browser, url, pin=True)
    expect(pinned.locator("#card-migration > .lf-work-line")).to_have_count(0)
    expect(pinned.locator("#jobs > .lf-conversation > .lf-work-line")).to_contain_text(
        "pricing the alternatives"
    )
    assert pinned_errors == []
    pinned.close()

    (d / "versions" / "v3.html").write_text(work_page)
    settled = CliRunner().invoke(
        cli_model.cli,
        [
            "version",
            "publish",
            str(d),
            "--version",
            "3",
            "--text",
            "Local work complete",
            "--completes",
            "card-migration",
            "--completes",
            "jobs",
        ],
    )
    assert settled.exit_code == 0, settled.output
    page.wait_for_url("**/versions/v3.html*")
    expect(page.locator(".lf-work-line")).to_have_count(0)
    assert errors == []
    page.close()


def test_local_work_chrome_does_not_take_its_holder_gesture(browser, serve, tmp_path):
    """A customization may deliberately give a container member a content seat.
    The runtime's generated line is still apparatus rather than that member's own
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

    work_line = page.locator("#job-mounts > .lf-work-line")
    expect(work_line).to_be_visible()
    work_line.click()
    page.wait_for_timeout(250)

    assert not any(
        e["kind"] == "action" for e in events_model.read_events(serve.page_dir)
    )
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
    work_line = page.locator("#shadow-card > .lf-work-line")
    expect(work_line).to_have_count(1)

    page.evaluate(
        """() => document.getElementById('patch').shadowRoot.append(
            document.getElementById('shadow-card'))"""
    )
    expect(work_line).to_have_count(1)

    (d / "versions" / "v2.html").write_text(work_page)
    settled = CliRunner().invoke(
        cli_model.cli,
        [
            "version",
            "publish",
            str(d),
            "--version",
            "2",
            "--text",
            "Shard checked",
            "--completes",
            "shadow-card",
        ],
    )
    assert settled.exit_code == 0, settled.output
    told(page)
    expect(work_line).to_have_count(0)
    assert errors == []
    page.close()


def test_widget_work_keeps_its_style_in_a_declared_shadow_tree(browser, serve):
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
    work_line = page.locator("#shadow-card > .lf-work-line")
    expect(work_line).to_have_css("display", "flex")

    page.evaluate(
        """() => document.getElementById('patch').shadowRoot.append(
            document.getElementById('shadow-card'))"""
    )
    expect(work_line).to_have_css("display", "flex")
    expect(work_line).to_have_css("border-left-style", "dashed")
    assert errors == []
    page.close()


def test_an_arrival_cannot_hide_a_question_draft(browser, serve):
    """An exact-section root arriving from elsewhere cannot take unsent words' box.

    The draft remains beside the arrived thread and can still start its own ordinary
    thread. Once that send succeeds, the first-message box gives way to the two textual
    thread views."""
    page, errors = open_page(browser, serve(ASK_PAGE))
    d = serve.page_dir
    conversation = page.locator("#jobs > .lf-conversation")
    first = conversation.locator(":scope > .lf-say textarea")
    draft = "Keep this answer even if another thread arrives first."
    first.fill(draft)

    external = events_model.append_event(
        d,
        {
            "kind": "comment",
            "author": "claude",
            "agent": "Indexer",
            "version": 1,
            "anchor": {"section": "jobs"},
            "text": "A separate note on this question.",
        },
    )
    told(page)
    expect(
        conversation.locator(f'.lf-conversation-thread[data-thread="{external["id"]}"]')
    ).to_be_visible()
    expect(first).to_be_visible()
    expect(first).to_have_value(draft)

    conversation.locator(":scope > .lf-say").get_by_role(
        "button", name="Send", exact=True
    ).click()
    round_trip(page)
    expect(conversation.locator(":scope > .lf-say")).to_have_count(0)
    roots = [e for e in sent_events(d) if e["kind"] == "comment"]
    assert [(e["anchor"], e["text"]) for e in roots] == [
        ({"section": "jobs"}, "A separate note on this question."),
        ({"section": "jobs"}, draft),
    ]
    expect(conversation.locator(".lf-conversation-thread")).to_have_count(2)
    assert errors == []
    page.close()


def test_the_box_is_offered_only_where_something_can_answer_it(browser, serve):
    """A textarea and a Send button with no handler behind them invite the reader to
    type into a page that cannot send it, which is the worst of the three media to be
    wrong in — it looks live. So the box is withheld rather than undone: the offer is
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

    box = page.locator("#jobs .lf-say")
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
        page.goto(url, wait_until="networkidle")
        gutter = page.locator("#spec").evaluate(
            "el => getComputedStyle(el).borderLeftColor"
        )
        assert gutter not in ("rgba(0, 0, 0, 0)", "transparent"), f"[{scheme}] {gutter}"
        page.close()


@pytest.mark.parametrize(
    "html",
    [SPECIMEN_PAGE, *(p.read_text() for p in SPECIMEN_EXAMPLES)],
    ids=["fixture", *(p.stem for p in SPECIMEN_EXAMPLES)],
)
def test_the_gutter_runs_beside_the_exhibit_and_no_further(html, browser, serve):
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

    page, errors = open_page(browser, serve(html))
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
            # failed on the gallery, where the same delta is thousands of pixels.
            page.evaluate(
                """([id, edge]) => {
                    const r = document.getElementById(id).getBoundingClientRect();
                    document.body.scrollBy({
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
    resized(page, 380, 900)
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
            "id": "c-ask",
            "author": "user",
            "version": 1,
            "text": "What would the alternative look like?",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-ask",
            "version": 1,
            "text": SPECIMEN_TEXT,
            "markup": SPECIMEN_MARKUP,
        },
    )
    page, errors = open_page(browser, url)
    page.locator(".lf-comments").click()
    page.wait_for_selector(
        '#rp-live .lf-pick[role="button"]'
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
    assert page.locator('#rp-quoted .lf-pick[role="button"]').count() == 0
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
            "id": "c-ask",
            "author": "user",
            "version": 1,
            "text": "What are the ceilings?",
        },
    )
    events_model.append_event(
        d,
        {
            "kind": "reply",
            "author": "claude",
            "parent": "c-ask",
            "version": 1,
            "text": TABLE_REPLY,
        },
    )
    page, errors = open_page(browser, url)
    page.locator(".lf-comments").click()
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
