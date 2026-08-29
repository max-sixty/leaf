"""Modifier aiming and design-mode browser tests."""

import io
import math
import re

import pytest
from leaf import event_log as events_model
from leaf import schema as schema_model
from leaf.validation import compatibility as validation_model
from playwright.sync_api import expect
from render_support import (
    AIM_CURSOR,
    AIM_PAINT_PAGE,
    AIM_POINT,
    AIM_SEAM,
    AIM_SEAM_PAGE,
    AIMED,
    BOTH_STAMPS,
    COMMAND_HUB_PACKAGE,
    CORNER_PAGE,
    DRAFT_MARK,
    EDGES,
    EXAMPLES,
    FOCUS_IN_PAGE,
    LEGEND_TRUE,
    LONG_PAGE,
    NAMED,
    PAGE_MARKUP,
    PART_DIAGRAM_PAGE,
    PART_DIAGRAM_V2,
    PICTURE_PAGE,
    REPLAYED_PAGE,
    SPECIMEN_PAGE,
    aim_targets,
    draw_edge,
    geometry,
    leaf_page,
    live_url,
    open_page,
    panel_settled,
    resized,
    round_trip,
    select,
    stamp_version_file,
    told,
)

pytestmark = pytest.mark.nightly


# One page for each reason an aimed press can still reach the page underneath it. The
# capture itself is layer-wide, so another example containing the same click or
# mousedown mechanism repeats the reading. These required paths are non-vacuity floors:
# a representative that loses the feature which earned its place fails rather than
# quietly shrinking the causal corpus.
AIM_PRESS_CASES = (
    (
        next(p for p in EXAMPLES if p.stem == "parallel-workstreams"),
        frozenset({"option click", "tab click"}),
    ),
    (
        next(p for p in EXAMPLES if p.stem == "ship-review"),
        frozenset({"draft mousedown", "standing mark", "suggestion no-item control"}),
    ),
)


def test_the_catalog_sidenote_can_be_aimed_whole(browser, serve):
    """The sidenote authors copy carries the identity its advertised aim needs.

    A handwritten fixture would prove the runtime and leave the catalog free to
    regress to an id-less note that renders normally but gives Alt nothing to outline.
    Drive that example itself through the whole gesture, from outline to anchored
    composer."""
    registry = validation_model.incoming_registry(
        [
            schema_model.ASSETS,
            schema_model.DEFAULT_PACKAGE,
            COMMAND_HUB_PACKAGE,
        ]
    )
    sidenote = registry["$idioms"]["aside.sidenote"]["example"]
    html = LONG_PAGE.replace(
        '<h1 id="t">Long</h1>', f'<h1 id="t">Long</h1>\n{sidenote}'
    )
    page, errors = open_page(browser, serve(html))
    note = page.locator("#logout-frequency")

    note.hover()
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "logout-frequency")
    note.click()
    page.keyboard.up("Alt")

    # The press raises the compact bar on the note — the comment icon, then the reaction
    # ellipsis — and the comment icon opens the composer on the whole note.
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(DRAFT_MARK) == "logout-frequency"
    assert errors == []
    page.close()


def test_the_aim_reads_the_pointer_where_the_press_is_dispatched_from(browser, serve):
    """The outline and the press ask one question of one point, down to the sub-pixel.

    The two readings of "what is under the pointer" come from different doors: the
    outline hit-tests the pointer record the runtime keeps, and the press takes the
    target the browser resolved for it. `mousemove` carries the pointer's place rounded
    to a whole pixel, so a record kept from one is an answer about a place the pointer is
    not — and within a pixel of a seam that place is a different item. It cost a corpus
    page a promise: ⌥ over a choose group outlined the option above the seam and the
    press commented on the one below it, which is the composer opening on an item the
    reader was never shown.

    So the aim is put within a quarter pixel of a seam, where the true point and its
    rounded twin name different items. Which of the two the true point is over depends on
    where in the pixel the seam fell, so the item the aim is held to is read off the point
    rather than named here; what is asserted first is that the two readings differ at all,
    since a seam that fell on a whole pixel would leave this proving that two agreeing
    readings agree."""
    page, errors = open_page(browser, serve(AIM_SEAM_PAGE))
    seam = page.evaluate(AIM_SEAM, ["seam-upper", "seam-lower"])
    assert seam and {seam["at"], seam["rounded"]} == {"seam-upper", "seam-lower"}, (
        "the fixture no longer straddles a seam — the aim point and the whole pixel it "
        "rounds to are not on the two items either side of it, so nothing here is under "
        f"test: {seam}"
    )

    page.mouse.move(seam["x"], seam["y"])
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", seam["at"])
    page.mouse.click(seam["x"], seam["y"])
    page.keyboard.up("Alt")

    # The press raises the bar on the item the aim held; Comment on it is the composer.
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(DRAFT_MARK) == seam["at"]
    assert errors == []
    page.close()


def test_an_aimed_first_press_records_its_pointer_before_claiming_it(browser, serve):
    """A press can be the first pointer event, and capture still reads its position.

    Aim claims pointerdown during capture and stops the gesture before it reaches the
    page. The shared position recorder therefore has to run earlier in that same phase:
    a bubble listener never sees this event, and aim would ask about the stale initial
    point instead of the paragraph the browser dispatched the press to.
    """
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.locator("#p2").evaluate(
        """target => {
          const box = target.getBoundingClientRect();
          const init = {
            bubbles: true,
            clientX: box.left + box.width / 2,
            clientY: box.top + box.height / 2,
            altKey: true,
          };
          target.dispatchEvent(new PointerEvent("pointerdown", init));
          target.dispatchEvent(new MouseEvent("mousedown", init));
          target.dispatchEvent(new PointerEvent("pointerup", init));
          target.dispatchEvent(new MouseEvent("mouseup", init));
          target.dispatchEvent(new MouseEvent("click", {...init, detail: 1}));
        }"""
    )

    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(DRAFT_MARK) == "p2"
    assert errors == []
    page.close()


@pytest.mark.parametrize(
    ("example", "required_paths"),
    AIM_PRESS_CASES,
    ids=[case[0].stem for case in AIM_PRESS_CASES],
)
def test_an_aimed_press_does_only_what_the_outline_promised(
    browser, serve, example, required_paths
):
    """⌥-click takes the item under the pointer, and that is the whole of what it does.

    Holding ⌥ outlines what a click would take, which is a promise about the next press.
    The runtime used to read that press on the way back up, after every handler out on the
    page had already had it, so the press kept the promise and did something else besides:
    ⌥-clicking an option card opened the composer *and* picked the option, sending Claude a
    decision the user never made, while ⌥-clicking a tab's name aimed at the widget and
    switched the panel under it. Neither shows in the composer, which opens either way.

    So both halves are asserted together — the composer opens on the item that was
    outlined, and the page is exactly as it was, in its markup and in where its focus
    sits. The capture mechanism is layer-wide; these pages are retained for the distinct
    downstream paths they put under it rather than for every repetition of those paths.
    `required_paths` keeps that causal selection honest when an example changes.
    """
    url = serve(example)
    page, errors = open_page(browser, url)
    # What the log already held. A shipped seed can carry a decision the reader made
    # before this page was opened, and what an aim may not do is add one of its own —
    # so the reading below is against this rather than against nothing.
    standing = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "action"
    ]
    targets = aim_targets(serve.page_dir)
    total = page.locator(targets).count()
    pressed = aimed = 0
    reached_paths = set()
    for i in range(total):
        # A control inside a fold or behind an unopened tab is nowhere a user can aim,
        # which is the press sweep's reading of the same question, and a point the banner
        # or a neighbour covers is not this target's press at all.
        target = page.locator(targets).nth(i)
        if not target.is_visible():
            continue
        # A wrapper with no box of its own — one a page's style leaves
        # display: contents — is nowhere a user can aim (AIM_POINT finds no point
        # in it either), and
        # scroll_into_view can wait on its stability forever when it stands inside
        # a table box (a specimen). Its slots are their own targets.
        if not target.evaluate("el => el.getClientRects().length"):
            continue
        target.scroll_into_view_if_needed()
        point = target.evaluate(AIM_POINT)
        if not point:
            continue
        target_paths = set(
            target.evaluate(
                """el => [
                  [el.matches('[role=tab]'), 'tab click'],
                  [el.matches('.lf-pick') || !!el.closest('lf-option'), 'option click'],
                  [el.matches('lf-draft') || !!el.closest('lf-draft'),
                   'draft mousedown'],
                  [el.matches('.lf-sug-actions') || !!el.closest('.lf-sug-actions'),
                   'suggestion control'],
                ].filter(([reached]) => reached).map(([, name]) => name)"""
            )
        )
        reached_paths.update(target_paths - {"suggestion control"})
        label = target.evaluate(NAMED)
        before = page.evaluate(PAGE_MARKUP)
        page.mouse.move(*point)
        page.keyboard.down("Alt")
        promised = page.evaluate(AIMED)
        # The cursor is the other half of the same promise, and it is derived from the
        # same value the outline is: the hand where a press takes something, the arrow
        # where it takes nothing. Read off body, which is where the aim declares it —
        # a widget's own control still states its resting cursor, and does so whether or
        # not the key is down.
        assert page.evaluate(AIM_CURSOR) == ("pointer" if promised else "default"), (
            f"holding ⌥ over {label} in {example.name} promised {promised} and pointed "
            f"a {page.evaluate(AIM_CURSOR)} cursor at it"
        )
        page.mouse.click(*point)
        page.keyboard.up("Alt")
        composer = page.locator(".lf-composer")
        bar = page.locator(".lf-fab-bar")
        if promised is None:
            if "suggestion control" in target_paths:
                reached_paths.add("suggestion no-item control")
            # Nothing outlined is nothing to aim at — no item encloses this point — and an
            # armed press then acts on nothing rather than falling back to the page. A
            # suggestion's ✓ Accept is where that matters: its row hangs in the page's own
            # column, outside the element it decides, so nothing is above it to aim at and
            # a press let through would send Claude a decision.
            expect(bar).to_be_hidden()
            expect(composer).to_be_hidden()
        else:
            # The press raises the bar on the item; Comment on it is the composer.
            expect(bar).to_be_visible()
            page.locator(".lf-fab").click()
            expect(composer).to_be_visible()
            mark = page.evaluate(DRAFT_MARK)
            # A box a standing thread already outlines keeps the posted colour and takes
            # no pending class of its own: the draft claims whichever boxes are still
            # free (paintAnchors), so aiming at an element the log already marks keeps
            # the promise and paints nothing new. The other half of the press is read
            # either way — where the composer opened on something else, that element
            # wears the pending mark and this reads it there.
            if mark is None and page.locator(f"#{promised}.lf-mark-el").count():
                mark = promised
                reached_paths.add("standing mark")
            assert mark == promised, (
                f"⌥-clicking {label} in {example.name} promised {promised} and "
                f"commented on {mark}"
            )
            # And the promise is kept where the reader can see it kept. An outline needs
            # a box, and an item that draws none — every suggestion is display: contents —
            # would take the mark to 0x0 at the document's origin, showing nothing. The
            # composer places itself off this same record, so it would go to the top of
            # the window along with it, beside a passage it is no longer beside.
            unshown = page.evaluate(
                """() => [...document.querySelectorAll('.lf-mark-el.lf-pending')]
                   .filter(e => { const b = e.getBoundingClientRect();
                                  return !(b.width && b.height); })
                   .map(e => e.tagName.toLowerCase())"""
            )
            assert not unshown, (
                f"⌥-clicking {label} in {example.name} outlined {unshown}, which draws "
                "no box, so the promise is invisible and the composer stands off a rect "
                "at the top of the document"
            )
            # Put the composer away before reading the page back: its own passage wears
            # the outline, which is the one mark an aim is supposed to leave.
            page.keyboard.press("Escape")
            expect(composer).to_be_hidden()
            aimed += 1
        assert page.evaluate(PAGE_MARKUP) == before, (
            f"⌥-clicking {label} in {example.name} changed the page, so a press the aim "
            "had taken reached a widget as well"
        )
        assert not page.evaluate(FOCUS_IN_PAGE), (
            f"⌥-clicking {label} in {example.name} left the focus on the page, so the "
            "press reached the control under it"
        )
        pressed += 1
    assert pressed, f"{example.name} pressed nothing, so it asserts nothing"
    # And that the outline is still painted at all: a preview that stopped appearing would
    # leave every press above asserting only that nothing happened, which is the shape of
    # vacuous pass this sweep is most exposed to.
    assert aimed, f"{example.name} outlined nothing, so no press was held to a promise"
    assert reached_paths >= required_paths, (
        f"{example.name} no longer exercises the paths that earned its place in the "
        f"aim corpus: missing {sorted(required_paths - reached_paths)}, reached "
        f"{sorted(reached_paths)}"
    )
    # The other half of "did nothing else", and the half the markup cannot show: a widget
    # that acts tells Claude so, and a decision the user never made is worse in the log
    # than on the page. The wait is the page's own sends coming back, so a stray one is in
    # the log to be read rather than still in flight.
    round_trip(page)
    assert [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "action"
    ] == standing, (
        f"⌥-clicking through {example.name} left a decision in the log that the aim "
        "never promised"
    )
    assert errors == []
    page.close()


def test_an_aim_on_a_seam_promises_and_takes_the_same_item(browser, serve):
    """One reading, at the one place the pointer is.

    The cells of a joined group butt, so two of them share an edge with no gap between,
    and a pointer resting on it is inside both by the width of a rounding. The outline
    and the press each used to hit-test that point for themselves — elementFromPoint
    against the browser's own dispatch — and nothing makes two hit tests tie-break a
    shared edge alike. What a reader got was one option outlined and the next one
    commented on.

    The sweep over the corpus reaches this case only where the page happens to put a
    seam under the point it picks, which is a fact about font metrics: the same aim was
    a cell's interior on one platform and a seam on another, and the corpus said the
    promise was kept for a year on the machine where it was. So the seam is aimed at
    here rather than waited for, and the assertion is the platform-independent half —
    whichever way each reading rounds, both answer the same item."""
    page, errors = open_page(browser, serve(SPECIMEN_PAGE))
    edge = page.evaluate(
        """() => {
            const above = document.querySelector('#l-shim').getBoundingClientRect();
            const below = document.querySelector('#l-stage').getBoundingClientRect();
            return {y: above.bottom, apart: Math.abs(below.top - above.bottom),
                    x: above.left + above.width / 2};
        }"""
    )
    assert edge["apart"] < 0.5, (
        f"the cells stand {edge['apart']}px apart, so this aims at a gap and not at the "
        "seam the two readings can differ over"
    )
    page.mouse.move(edge["x"], edge["y"])
    page.keyboard.down("Alt")
    promised = page.evaluate(AIMED)
    assert promised in ("l-shim", "l-stage"), (
        f"the aim promised {promised} on the seam between the two cells, so the reading "
        "under test never happened"
    )
    page.mouse.click(edge["x"], edge["y"])
    page.keyboard.up("Alt")
    # The press raises the bar on what it took, and Comment is the way from there into
    # the composer — the same route a selection takes.
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(DRAFT_MARK) == promised, (
        f"the outline promised {promised} on the seam and the press commented on "
        f"{page.evaluate(DRAFT_MARK)}"
    )
    assert errors == []
    page.close()


def test_a_key_still_reaches_its_control_after_an_aimed_press(browser, serve):
    """The aim holds its claim until the next press starts, and a key is not one.

    The option scope works its selection toggle by calling click(), so a control worked
    from the keyboard sends a click with no press behind it. Taken for the aim's own, it
    goes nowhere at all: the user presses Space on a pick mark and nothing is
    picked, on a page where the last thing they did with the mouse was aim."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    heading = page.locator("#t")
    heading.hover()
    page.keyboard.down("Alt")
    heading.click()
    page.keyboard.up("Alt")
    expect(page.locator(".lf-fab-bar")).to_be_visible()  # the press was the aim's
    page.locator(".lf-fab").click()
    composer = page.locator(".lf-composer")
    expect(composer).to_be_visible()
    page.keyboard.press("Escape")
    expect(composer).to_be_hidden()

    page.locator("#opt-shim .lf-pick").focus()
    page.keyboard.press(" ")
    expect(page.locator("#approach > lf-option[chosen]")).to_have_count(1)
    round_trip(page)
    assert [
        e["action"] for e in events_model.read_events(serve.page_dir) if "action" in e
    ] == ["choose"]
    assert errors == []
    page.close()


def test_the_aim_still_promises_while_a_composer_is_open(browser, serve):
    """An armed press with the box up re-anchors it, so the aim must still say where.

    claimPress acts whether or not a composer stands open, and openComposer carries the
    typed text onto the new anchor — so the aim standing down on composerOpen, as it did
    from its first commit, left exactly one press made blind: the one that moves a
    draft. Holding ⌥ over a second item raises its box beside the draft's own mark;
    two at once is the true state — where the draft stands, and where a press would
    move it — and the press then does what the box promised."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    heading = page.locator("#t")
    heading.hover()
    page.keyboard.down("Alt")
    heading.click()
    page.keyboard.up("Alt")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.locator(".lf-fab").click()
    composer = page.locator(".lf-composer")
    expect(composer).to_be_visible()
    composer.locator("textarea").fill("carried words")

    card = page.locator("#card-notes")
    card.hover()
    page.keyboard.down("Alt")
    promised = [page.evaluate(AIMED), page.evaluate(DRAFT_MARK)]
    assert promised == ["card-notes", "t"], (
        f"holding ⌥ over a card with a draft open on the heading showed {promised} as "
        "[aim, draft], so the press that would move the draft is blind"
    )
    card.click()
    page.keyboard.up("Alt")
    # The bar comes up on the card over the open box; its Comment moves the box.
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    page.locator(".lf-fab").click()
    expect(composer).to_be_visible()
    expect(composer.locator("textarea")).to_have_value("carried words")
    assert [page.evaluate(AIMED), page.evaluate(DRAFT_MARK)] == [
        None,
        "card-notes",
    ], "the press re-anchored the draft, so its new anchor alone should stand marked"
    round_trip(page)
    assert [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ] == []
    assert errors == []
    page.close()


def test_a_reload_under_a_held_aim_rearms_on_the_first_move(browser, serve):
    """The arm survives what the keydown cannot.

    `aiming` is armed by an Alt keydown, and a page reloaded under a held key — the
    poll following a new version does exactly this — never hears one, while claimPress
    reads live modifier state: every press on the new page was claimed and none could
    be promised. Mouse events carry that same live state, so the first move re-derives
    the arm; this drives that move rather than a keydown the reload already ate."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    heading = page.locator("#t")
    heading.hover()
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "t")
    page.reload()
    page.wait_for_function(BOTH_STAMPS)
    expect(page.locator(".lf-aim[data-for]")).to_have_count(0)  # the latch is gone
    heading.hover()  # the first move under the still-held key
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "t")
    page.keyboard.up("Alt")
    assert errors == []
    page.close()


def test_design_mode_comments_on_what_a_press_lands_on_and_nothing_else(browser, serve):
    """A press in design mode is a comment about the layer, and that is all it does.

    The mode is the ⌥ aim generalized: a press on a widget names the widget rather than
    working it, so a pick mark can be pointed at without picking. The comment posts
    with `about: "layer"`, which is how the agent tells "this control looks wrong" from
    a remark about the words — nothing about the anchor alone says which. Both halves
    are asserted: the log's event, and the page exactly as it was."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    option = page.locator("#opt-shim")
    before = page.evaluate(PAGE_MARKUP)
    page.keyboard.press("i")
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))

    # The mode shows what is on the page rather than waiting for the pointer: a legend
    # box on every item, and on every item but a widget's parts its name — the group
    # is named, its options wear the hairline alone and are named under the pointer.
    def box_of(element_id):
        return page.locator(f'.lf-legend-box[data-for="{element_id}"]')

    expect(box_of("t")).to_be_visible()
    assert set(
        page.eval_on_selector_all(".lf-legend-box", "bs => bs.map(b => b.dataset.for)")
    ) == set(page.eval_on_selector_all("main [id]", "es => es.map(e => e.id)"))
    expect(box_of("approach").locator(".lf-legend-tag")).to_have_text(
        "lf-options · approach"
    )
    expect(box_of("t").locator(".lf-legend-tag")).to_have_text("heading · t")
    expect(box_of("opt-shim").locator(".lf-legend-tag")).to_have_count(0)
    page.wait_for_function(LEGEND_TRUE)
    # Hovering names the target — the tag and the id a fix is written against — and
    # draws the aim's own box on it, the promise about the next press.
    option.hover()
    expect(page.locator(".lf-inspect")).to_have_text("lf-option · opt-shim")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "opt-shim")
    option.click()
    composer = page.locator(".lf-composer")
    expect(composer).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_have_text(
        "layer · lf-option · opt-shim"
    )
    # The press did nothing to the page: not a pick, not a focus, nothing in the markup
    # but the composer's own outline on the element it is about.
    expect(page.locator("#approach > lf-option[chosen]")).to_have_count(0)
    assert (
        page.evaluate(PAGE_MARKUP).replace(' class="lf-mark-el lf-pending"', "")
        == before
    )
    assert not page.evaluate(FOCUS_IN_PAGE)
    page.locator(".lf-composer textarea").fill("the ring reads too heavy")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    events = events_model.read_events(serve.page_dir)
    posted = [e for e in events if e["kind"] == "comment"]
    assert [(e["about"], e["anchor"]) for e in posted] == [
        ("layer", {"section": "opt-shim"})
    ]
    assert [e for e in events if e["kind"] == "action"] == []
    # The panel names the thread the same way the composer named the box, and the send
    # lands typing in that thread's reply box.
    expect(page.locator(".lf-thread .lf-quote")).to_have_text(
        "layer · lf-option · opt-shim"
    )
    expect(page.locator(".lf-thread textarea")).to_be_focused()
    # Escape backs out one rung at a time — the box, then the mode.
    page.keyboard.press("Escape")
    expect(page.locator(".lf-thread")).to_be_focused()
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))
    page.keyboard.press("Escape")
    expect(page.locator("body")).not_to_have_class(re.compile(r"\blf-design\b"))
    expect(page.locator(".lf-inspect")).to_be_hidden()
    expect(page.locator(".lf-legend-box")).to_have_count(0)
    assert errors == []
    page.close()


def test_design_mode_names_every_platform_control_from_the_shared_boundary(
    browser, serve
):
    """Design mode names and captures controls from the runtime's full platform list.

    A slider nested in an ordinary section has no widget tag or native element name to
    put it on a smaller selector. Its ARIA role must still become the named design part.
    """
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "design controls",
                '<h1>Controls</h1><section id="volume">'
                '<span role="slider" tabindex="0" aria-label="Volume" '
                'aria-valuemin="0" aria-valuemax="100" aria-valuenow="50">50</span>'
                "</section>",
            )
        ),
    )
    page.keyboard.press("i")
    slider = page.get_by_role("slider", name="Volume")
    slider.hover()
    expect(page.locator(".lf-inspect")).to_have_text("Volume · section · volume")
    slider.click()
    expect(page.locator("#lf-composer-quote")).to_have_text(
        "layer · Volume · section · volume"
    )
    assert errors == []
    page.close()


def test_design_mode_reaches_the_chrome_and_names_the_control(browser, serve):
    """The banner, the panel, a control on either: what no comment could reach before.

    The anchor pass passes over the runtime's own layer, so a remark about the Comments
    button had nowhere to land. In design mode the press on it is a comment on it —
    anchored on the part the runtime named (`lf-banner`), naming the control the press
    landed on — and the button does not do what it does: the panel stays closed."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    page.keyboard.press("i")
    comments = page.locator(".lf-banner .lf-comments")
    said = comments.inner_text()  # "Comments (0)" — the control's word is what it shows
    comments.hover()
    expect(page.locator(".lf-inspect")).to_have_text(f"{said} · banner")
    comments.click()
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_have_text(f"layer · {said} · banner")
    expect(page.locator(".lf-panel")).to_be_hidden()
    page.locator(".lf-composer textarea").fill("reads dim against the wash")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    posted = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "comment"
    ]
    assert [(e["about"], e["anchor"]) for e in posted] == [
        ("layer", {"section": "lf-banner", "part": said})
    ]
    # The thread's mark is the outline an element anchor wears, on the chrome too.
    expect(page.locator("#lf-banner")).to_have_class(re.compile(r"\blf-mark-el\b"))
    page.keyboard.press("Escape")

    # And the comment panel, which is the case where the aim's own geometry had nothing to
    # say. A fixed box is not clipped by the page's scroller, and body is that scroller
    # narrowed to the column standing beside the panel — so the panel measured through its
    # ancestors came back wholly clipped away, and a mode whose row promises a click on the
    # chrome drew nothing over the chrome. Wide enough for the panel to stand beside the
    # page, which is where body and the panel part company.
    resized(page, 1280, 800)
    page.locator(".lf-banner .lf-comments").click()
    expect(page.locator(".lf-panel")).to_be_visible()
    page.wait_for_function(
        "() => document.querySelector('.lf-panel').getBoundingClientRect().left"
        " >= document.body.clientWidth"
    )
    page.keyboard.press("i")
    box = page.locator(".lf-panel").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + 30)
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "lf-comments")
    assert page.evaluate(
        """() => {
             const aim = document.querySelector('.lf-aim').getBoundingClientRect();
             const panel = document.querySelector('.lf-panel').getBoundingClientRect();
             return Math.abs(aim.width - panel.width) < 3
                 && Math.abs(aim.left - panel.left) < 3;
           }"""
    ), "the aim's box does not stand on the panel it names"
    assert errors == []
    page.close()


def test_design_mode_takes_an_edge_rather_than_drawing_it(browser, serve):
    """The mode promises that a press comments on what it lands on and does nothing else,
    and a region's edge is the piece of chrome whose press moves the page rather than the
    page's content. A drag on it under the mode leaves the region where it was and opens a
    composer naming the edge, which is what a reader remarking on it has to be able to do.

    Neither half is anything the edge knows: the mode takes the press above the runtime's
    own handler, and the name comes of the platform's word for what the press landed on.
    So this is a reading of whether a new control joins the mode by being one — which is
    what it would stop doing the day an edge answered a press for itself. One edge is the
    whole reading, both being one handler (`drawnEdge`); what the second edge could break
    here it would break for the first too."""
    edge = EDGES[0]
    page, errors = open_page(browser, serve(LONG_PAGE, comments=1))
    resized(page, 1280, 800)
    page.locator(".lf-comments").click()
    panel_settled(page)
    standing = geometry(page, edge)
    page.keyboard.press("i")
    draw_edge(page, edge, 160)
    held = geometry(page, edge)
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_have_text(
        "layer · Comment panel width · comments"
    )
    page.close()

    assert held["width"] == standing["width"], (
        f"the mode moved the edge it was asked to comment on: {standing} then {held}"
    )
    assert held["chosen"] is None, (
        f"a press the mode took was still recorded as the reader's width: {held}"
    )
    assert errors == []


def test_design_mode_leaves_prose_to_the_selection(browser, serve):
    """Words are still the way to point at words: a drag on prose selects, and the
    comment it raises is about the layer; a plain click on prose comments on the block.

    The mode takes presses on widgets, controls and the chrome at the press, ahead of the
    page. Prose it leaves to the browser, or "this heading is too small" would have no
    way to quote the heading."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    page.keyboard.press("i")
    heading = page.locator("#t")
    box = heading.bounding_box()
    select(
        page,
        (box["x"] + 2, box["y"] + box["height"] / 2),
        (box["x"] + box["width"] - 2, box["y"] + box["height"] / 2),
    )
    fab = page.locator(".lf-fab")
    expect(fab).to_be_visible()
    fab.click()
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_have_text(
        "layer · heading · t · “Rollout”"
    )
    page.keyboard.press("Escape")  # the composer, draft kept; the mode still stands
    expect(page.locator(".lf-composer")).to_be_hidden()
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))
    heading.click(position={"x": 4, "y": 4})
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_have_text("layer · heading · t")
    assert errors == []
    page.close()


def test_design_mode_survives_the_reload_a_new_version_brings(browser, serve):
    """A version landing mid-batch reloads the document, and a reader put out of the
    mode by news they never asked for is a mode error the page made — so the mode is
    this tab's working state, kept the way the panel's open state is."""
    page, errors = open_page(browser, serve(REPLAYED_PAGE))
    page.keyboard.press("i")
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))
    page.reload()
    page.wait_for_function(BOTH_STAMPS)
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))
    expect(page.locator('.lf-legend-box[data-for="approach"]')).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("body")).not_to_have_class(re.compile(r"\blf-design\b"))
    page.reload()
    page.wait_for_function(BOTH_STAMPS)
    expect(page.locator("body")).not_to_have_class(re.compile(r"\blf-design\b"))
    assert errors == []
    page.close()


def test_the_legend_follows_the_page_it_is_a_reading_of(browser, serve):
    """A legend box kept from a previous reading is a claim about a page that has moved.

    Three of the doors that move it: the page scrolling (items come on screen with no
    box yet, and the boxes are drawn in document space), the panel opening (the column
    re-centres, every block reflows, and no scroll or replay says so — each item's own
    resize does), and the name under the pointer, which is drawn beside the box in the
    same space: it sat in viewport space once, with the scroll added on top, and stood a
    screen below its box on any page scrolled at all. The aim is one more of the
    chrome's promises over the same page, so the reflow doors repaint it too
    (pageShifted): it once kept its old coordinates through the panel's slide, a box
    and name floating half a panel to the right of the element they claimed."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.keyboard.press("i")
    page.wait_for_function(LEGEND_TRUE)
    page.locator("body").evaluate("b => { b.scrollTop = 1200; }")
    p = page.locator("#p20")
    expect(p).to_be_in_viewport()
    expect(page.locator('.lf-legend-box[data-for="p20"]')).to_be_visible()
    page.wait_for_function(LEGEND_TRUE)
    # The name floats where the box's tag stood, over the item's corner — on a scrolled
    # page as on a fresh one.
    p.hover()
    expect(page.locator(".lf-inspect")).to_have_text("paragraph · p20")
    box = page.locator(".lf-aim").bounding_box()
    name = page.locator(".lf-inspect").bounding_box()
    assert abs(name["y"] + name["height"] - box["y"]) < 4, (name, box)
    assert abs(name["x"] - box["x"]) < 4, (name, box)
    # The panel takes a strip from the page and every block moves; the legend moves
    # with them, off the resize each item reports. Opened by key: in the mode a press
    # on the Comments button is a comment about the button.
    page.keyboard.press("c")
    expect(page.locator(".lf-panel")).to_be_visible()
    page.wait_for_function(
        "() => document.body.getAnimations().every(a => a.playState !== 'running')"
    )
    page.wait_for_function(LEGEND_TRUE)
    # The legend's repaint above consumed the reflow's edge, and the aim was refreshed
    # in the same pageShifted, so one plain read is the settled answer: the pointer
    # still rests in p20, and the promise is about where p20 stands now.
    aim = page.evaluate(
        """() => {
      const b = document.querySelector('.lf-aim');
      const it = document.getElementById(b.dataset.for);
      const r = it.getBoundingClientRect();
      const bb = b.getBoundingClientRect();
      return { on: b.dataset.for, dx: bb.left - r.left, dy: bb.top - r.top };
    }"""
    )
    assert aim["on"] == "p20" and abs(aim["dx"]) < 2 and abs(aim["dy"]) < 2, aim
    assert errors == []
    page.close()


def test_two_names_at_one_corner_step_apart(browser, serve):
    """A block whose top-left corner is also its container's — the paragraph's margin
    collapses out of the section, exactly the shape a suggestion and the block it wraps
    make — wrote both tags onto one spot, and the longer peeked out past the shorter at
    both ends as fragments of a word nobody wrote. The later tag steps away by tag
    heights until it stands clear."""
    page, errors = open_page(browser, serve(CORNER_PAGE))
    page.keyboard.press("i")
    expect(
        page.locator('.lf-legend-box[data-for="wrap"] .lf-legend-tag')
    ).to_be_visible()
    expect(
        page.locator('.lf-legend-box[data-for="inner"] .lf-legend-tag')
    ).to_be_visible()
    clash = page.evaluate(
        """() => {
      const rs = [...document.querySelectorAll('.lf-legend-tag')]
        .map(t => t.getBoundingClientRect()).filter(r => r.width);
      for (let i = 0; i < rs.length; i++)
        for (let j = i + 1; j < rs.length; j++) {
          const a = rs[i], b = rs[j];
          if (a.left < b.right - 1 && b.left < a.right - 1 &&
              a.top < b.bottom - 1 && b.top < a.bottom - 1)
            return [a, b].map(r => [r.left, r.top, r.width, r.height]);
        }
      return null;
    }"""
    )
    assert clash is None, clash
    assert errors == []
    page.close()


def test_a_picture_is_one_item_however_many_ids_its_renderer_coined(browser, serve):
    """The aim over a diagram's node named the node — `root-1`, an id mermaid minted and
    the next render may not — where a plain click already anchored the widget. The
    entry says which (x-visual: the click's anchor is the widget rather than a generated
    part inside it), so the aim and the legend both stop at the widget."""
    page, errors = open_page(browser, serve(PICTURE_PAGE))
    node = page.locator("#flow svg g[id]").first
    expect(node).to_be_visible()
    node.hover()
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "flow")
    page.keyboard.up("Alt")
    page.keyboard.press("i")
    assert set(
        page.eval_on_selector_all(".lf-legend-box", "bs => bs.map(b => b.dataset.for)")
    ) == {"t", "p", "flow", "tree"}
    node.hover()
    expect(page.locator(".lf-inspect")).to_have_text("lf-diagram · flow")
    assert errors == []
    page.close()


def test_a_declared_flowchart_node_keeps_its_comment_across_renderings(browser, serve):
    """The authored Mermaid id, rather than its generated SVG id, is the anchor.

    An unlisted node is the control: it still takes the whole diagram. A listed node
    outlines only its current SVG group, while the diagram holds the accessible note
    and the panel place. Reloading makes Mermaid generate the SVG again and proves the
    stable token resolves to that new box.
    """
    page, errors = open_page(browser, live_url(serve(PART_DIAGRAM_PAGE)))
    diagram = page.locator("#flow")

    unlisted = diagram.locator('g[id^="flowchart-U-"]')
    unlisted.click()
    page.locator(".lf-fab").click()
    expect(diagram).to_have_class(re.compile(r"\blf-mark-el\b.*\blf-pending\b"))
    page.get_by_role("button", name="Cancel").click()

    start = diagram.locator('g[id^="flowchart-S-"]')
    start.click()
    page.locator(".lf-fab").click()
    expect(start).to_have_class(re.compile(r"\blf-mark-el\b.*\blf-pending\b"))
    expect(diagram).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    page.locator(".lf-composer textarea").fill("name the retry path here")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)

    posted = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["anchor"] for event in posted] == [
        {"section": "flow", "visual": "node:S"}
    ]
    expect(page.locator(".lf-thread .lf-quote")).to_have_text(
        "§ diagram · Start request"
    )
    expect(diagram.locator(":scope > .lf-mark-note")).to_have_count(1)
    expect(start).to_have_class(re.compile(r"\blf-mark-el\b"))

    (serve.page_dir / "versions" / "v2.html").write_text(PART_DIAGRAM_V2)
    stamp_version_file(serve.page_dir, 2, "reordered")
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")
    expect(diagram.locator('g[id^="flowchart-S-"]')).to_have_class(
        re.compile(r"\blf-mark-el\b")
    )
    expect(diagram).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    expect(diagram.locator(":scope > .lf-mark-note")).to_have_count(1)
    assert errors == []
    page.close()


def test_a_linked_flowchart_node_uses_the_item_aim_for_its_comment(browser, serve):
    """A link keeps plain navigation while Alt-click claims only the node comment."""
    page, errors = open_page(browser, serve(PART_DIAGRAM_PAGE))
    diagram = page.locator("#flow")
    handler = diagram.locator('g[id^="flowchart-H-"]')
    expect(handler.locator("xpath=ancestor::*[local-name()='a'][1]")).to_have_count(1)

    handler.click(modifiers=["Alt"])
    expect(handler).to_have_class(re.compile(r"\blf-mark-el\b.*\blf-pending\b"))
    expect(diagram).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    page.locator(".lf-composer textarea").fill("keep this linked step visible")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)

    posted = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["anchor"] for event in posted] == [
        {"section": "flow", "visual": "node:H"}
    ]
    assert errors == []
    page.close()


def test_design_mode_keeps_its_control_label_on_a_part_visual(browser, serve):
    """A design-control label is not reinterpreted as a semantic visual token."""
    page, errors = open_page(browser, serve(PART_DIAGRAM_PAGE))
    diagram = page.locator("#flow")
    handler = diagram.locator('g[id^="flowchart-H-"]')
    page.keyboard.press("i")
    handler.click()

    expect(page.locator("#lf-composer-quote")).to_have_text(
        "layer · Handle request · lf-diagram · flow"
    )
    page.locator(".lf-composer textarea").fill("the link needs a stronger affordance")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    posted = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [(event["about"], event["anchor"]) for event in posted] == [
        ("layer", {"section": "flow", "part": "Handle request"})
    ]
    expect(diagram).to_have_class(re.compile(r"\blf-mark-el\b"))
    expect(handler).not_to_have_class(re.compile(r"\blf-mark-el\b"))
    assert errors == []
    page.close()


def test_visual_parts_refuse_a_mermaid_type_the_adapter_cannot_address(browser, serve):
    """An unsupported promise is visible instead of producing detached anchors later."""
    unsupported = leaf_page(
        "unsupported diagram parts",
        """
<h1 id="t">Exchange</h1>
<lf-diagram id="exchange" parts="node:A"><pre>
sequenceDiagram
  A->>B: Request
</pre></lf-diagram>
""",
    )
    page, _ = open_page(browser, serve(unsupported))

    expect(page.locator("#exchange .lf-error")).to_contain_text(
        "commentable flowchart nodes not found: node:A"
    )
    page.close()


def test_a_scroll_under_a_held_aim_moves_the_promise_with_the_page(browser, serve):
    """What a press would take can change with no mouse event to say so.

    Only a pointer move used to re-ask the aim, so scrolling under a held key left the
    outline on the item that had been under the pointer while a press took the one now
    there — the paint answering an old page, the claim the current one. The scroll
    listener re-asks; this scrolls the page under a parked pointer and requires the
    promise to answer for where the page now stands."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.mouse.move(600, 300)
    page.keyboard.down("Alt")
    first = page.evaluate(AIMED)
    assert first, "nothing promised under the parked pointer, so nothing is being aimed"
    # Three whole paragraphs of scroll, measured off the page: the paragraphs are
    # identical, so the pointer's offset into the outlined one becomes the same offset
    # into the one three later, never the margin between two. body is the page's
    # scroller, and scrollBy fires the same scroll events a wheel does.
    page.evaluate(
        """() => document.body.scrollBy(0, 3 *
          (document.getElementById("p3").getBoundingClientRect().top -
           document.getElementById("p2").getBoundingClientRect().top))"""
    )
    page.wait_for_function(
        """(first) => {
      const promised = document.querySelector(".lf-aim")?.getAttribute("data-for");
      const at = document.elementFromPoint(600, 300)?.closest("[id]:not(.lf-ui)");
      return Boolean(promised) && promised === at?.id && promised !== first;
    }""",
        arg=first,
    )
    page.keyboard.up("Alt")
    assert errors == []
    page.close()


def test_a_replay_under_a_held_aim_repaints_the_promise(browser, serve):
    """A pass that runs paints the truth, whatever ran it.

    A replay of another tab's action moves content and repaints the marks where they
    now belong — and the aim used to ride that pass as an answer latched from the last
    mouse event, so the pass itself painted a promise about a card no longer there.
    The aimed item is derived inside the pass now, and the events only decide when a
    pass is worth running. Nothing here moves the mouse after the arm: the page moves
    instead, and the box must follow or clear."""
    url = serve(REPLAYED_PAGE)
    page, errors = open_page(browser, url)
    spot = page.locator("#card-importer").evaluate(
        "el => { const r = el.getBoundingClientRect();"
        " return [r.left + r.width / 2, r.top + 8]; }"
    )
    page.mouse.move(*spot)
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "card-importer")
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "work",
            "action": "move",
            "detail": {"card": "card-importer", "to": "col-done", "index": 0},
        },
    )
    told(page)
    expect(page.locator("#col-done #card-importer")).to_have_count(1)
    page.wait_for_function(
        """([x, y]) => {
      const promised =
        document.querySelector(".lf-aim")?.getAttribute("data-for") ?? null;
      const at = document.elementFromPoint(x, y)?.closest("[id]:not(.lf-ui)") ?? null;
      return promised === (at?.id ?? null) && promised !== "card-importer";
    }""",
        arg=spot,
    )
    page.keyboard.up("Alt")
    assert errors == []
    page.close()


def test_the_aims_box_is_what_the_page_shows_of_the_item(browser, serve):
    """The promise paints in the chrome's layer, and claims what the page shows.

    The aim used to wear the mark's hairline, and the mark's band is one pixel at the
    border edge — the one band of an element nobody else paints in, and exactly where a
    widget draws a border of its own. Over an accented option, whose border is
    already the accent, arming changed nothing a reader could see, and what was
    reported was no box at all. So the aim paints in the layer above the page, which no
    widget can reach; the pixel diff here is armed against unarmed with the pointer
    held still, so the widget's own hover wash is in both frames and the difference is
    the promise alone.

    A layer no widget can paint over is also one no ancestor's clip can reach, so the
    second half holds the box to the page's own showing of the item: a row's table box
    runs on under its group's overflow: hidden, and a box drawn from the raw rect
    would claim pixels the page has refused, over whatever stands in them."""
    from PIL import Image, ImageChops  # a dev dependency already, for the demo recorder

    page, errors = open_page(browser, serve(AIM_PAINT_PAGE))
    card = page.locator("#card-star")
    card.hover()
    # The wash and the lift a card answers the pointer with are transitions, and a
    # frame taken mid-glide would bill the arm for pixels the hover was still moving.
    page.wait_for_function(
        """() => document.getElementById("card-star")
                 .getAnimations({subtree: true}).length === 0"""
    )
    box = card.bounding_box()
    clip = {"x": math.floor(box["x"]), "y": math.floor(box["y"])}
    clip |= {"width": math.floor(box["width"]), "height": math.floor(box["height"])}
    quiet = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "card-star")
    armed = Image.open(io.BytesIO(page.screenshot(clip=clip))).convert("RGB")
    assert quiet.size == armed.size
    geometry = page.evaluate("""() => {
        const item = document.getElementById("card-star").getBoundingClientRect();
        const box = document.querySelector(".lf-aim").getBoundingClientRect();
        return [box.left - item.left, box.top - item.top,
                box.width - item.width, box.height - item.height].map(Math.abs);
    }""")
    assert max(geometry) < 1, f"the box missed the card it promises by {geometry}"
    pixels = zip(*[iter(ImageChops.difference(quiet, armed).tobytes())] * 3)
    changed = sum(max(p) >= 6 for p in pixels) / (armed.size[0] * armed.size[1])
    assert changed > 0.5, (
        f"arming changed {changed:.0%} of the card's pixels — the promise is not "
        "something a reader can see over the widget's own paint"
    )

    row = page.locator("#row-ship")
    row.hover()
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "row-ship")
    edges = page.evaluate("""() => {
        const group = document.getElementById("rows").getBoundingClientRect();
        const row = document.getElementById("row-ship").getBoundingClientRect();
        const box = document.querySelector(".lf-aim").getBoundingClientRect();
        return { box: box.right, shown: Math.min(row.right, group.right),
                 raw: row.right };
    }""")
    assert abs(edges["box"] - edges["shown"]) < 1, (
        f"the box ends at {edges['box']} where the page shows the row to "
        f"{edges['shown']} (its unclipped box runs to {edges['raw']}): a clip the "
        "page enforces went unhonoured"
    )
    page.keyboard.up("Alt")
    assert errors == []
    page.close()


def test_the_chrome_keeps_its_presses_while_the_page_is_armed(browser, serve):
    """What ⌥ arms is the page, and the line around it is the chrome's container.

    An aim that reached in there would take the panel, the composer and the banner away
    from a user who happens to be holding the key — and there is nothing in the layer
    to aim at anyway, since an anchor names an element of the page."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    comments = page.locator(".lf-comments")
    comments.hover()
    page.keyboard.down("Alt")
    comments.click()
    page.keyboard.up("Alt")
    panel_settled(page)
    expect(page.locator(".lf-panel")).to_be_visible()
    expect(page.locator(".lf-composer")).to_be_hidden()
    assert errors == []
    page.close()


def test_the_armed_cursor_says_whether_a_press_would_take_anything(browser, serve):
    """The chord's cost is that it is invisible, and the cursor pays part of it.

    Holding ⌥ used to draw a plain arrow over the whole page: it said "not a text
    selection" and nothing else, which leaves the one question the outline can't answer
    for a reader who hasn't looked yet — would this click do anything at all? An armed
    press takes the item under it and acts on nothing where there is none (claimPress),
    so the hand and the arrow are those two states, and the hand is exactly as good as
    the outline beside it because both are read off the same value.

    Read where the reader's pointer is rather than off body, since the aim declares it
    on body and everything on the page inherits it — the promise is only kept if it
    arrives at the glyphs. The margin beside the column is the page's own gap: no
    element there carries an id, so an armed press has nothing to take.

    `auto` is the resting state, and it is the whole point of the arrow: unarmed, the
    browser decides from what is under the pointer and draws an I-beam over words, so
    naming a cursor at all is the runtime saying those words are not a selection now."""
    page, errors = open_page(browser, serve(LONG_PAGE))
    at_pointer = """([x, y]) =>
        getComputedStyle(document.elementFromPoint(x, y)).cursor"""
    on_item = page.locator("#p2").evaluate(
        "el => { const r = el.getBoundingClientRect();"
        " return [r.left + 20, r.top + r.height / 2]; }"
    )
    # Beside the column, level with the same paragraph: body's own margin, which the
    # centred 720px column leaves on a 1200px viewport.
    in_gap = [40, on_item[1]]
    assert page.evaluate(at_pointer, on_item) == "auto", (
        "an unarmed page already named a cursor, so the arm has nothing left to say"
    )

    page.mouse.move(*on_item)
    page.keyboard.down("Alt")
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "p2")
    assert page.evaluate(at_pointer, on_item) == "pointer", (
        "the aim boxed the paragraph and the cursor declined to promise the press"
    )

    page.mouse.move(*in_gap)
    expect(page.locator(".lf-aim[data-for]")).to_have_count(0)
    assert page.evaluate(at_pointer, in_gap) == "default", (
        "the aim had nothing to take and the hand promised a press anyway"
    )

    # Back on the item, so the arm coming off is read from the state that promises most.
    page.mouse.move(*on_item)
    expect(page.locator(".lf-aim")).to_have_attribute("data-for", "p2")
    page.keyboard.up("Alt")
    expect(page.locator(".lf-aim[data-for]")).to_have_count(0)
    assert page.evaluate(at_pointer, on_item) == "auto", (
        "the key came up and the page went on offering the aim's press"
    )
    assert errors == []
    page.close()
