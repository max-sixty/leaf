"""Modifier aiming and design-mode browser tests."""

import re

import pytest
from interact_support import (
    append_carried_log_record,
    wait_for,
)
from playwright.sync_api import expect
from render_cases_interaction import (
    SUGGESTION_PAGE,
    live_url,
)
from render_cases_layout import (
    AIM_CURSOR,
    AIM_POINT,
    AIMED,
    DRAFT_MARK,
    FOCUS_IN_PAGE,
    NAMED,
    PAGE_MARKUP,
    aim_targets,
)
from render_cases_widgets import (
    TYPED_PARTS_PAGE,
    TYPED_PARTS_V2,
)
from render_harness import (
    expect_comment_notes,
    leaf_page,
    open_page,
    resized,
    round_trip,
    sending,
    stamp_page,
    told,
    wait_for_revision,
    write,
)

from leaf import event_log as events_model
from leaf.render_checks import rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_aim import (
    AIM_PRESS_CASES,
    COMPOSER_ATTACHMENT_PAGE,
    _draft_in_view,
    _open_attachment_draft,
    open_compact_comment,
)
from browser.threads import open_panel_thread


@pytest.mark.parametrize("placement, at", [("bottom-start", 0.15), ("top-start", 0.5)])
def test_typing_moves_the_comment_box_and_leaves_the_page_still(
    browser, serve, placement, at
):
    """A box under or over its passage that outgrows the room on its side moves inside
    the window, across the passage if it must, and the page stays where the user put it.
    The user reported the page scrolling under their keys as the box grew (the box then
    asked the page to make room for each new line)."""
    words = "The reviewer weighs each claim against the evidence offered so far. " * 3
    paragraphs = "".join(f'<p id="p{n}">{words}</p>' for n in range(30))
    page = open_page(browser, serve(leaf_page("Typing room", paragraphs)))
    resized(page, 900, 700)
    passage = page.locator("#p12")
    passage.evaluate(
        f"""node => scrollBy({{
          top: node.getBoundingClientRect().top - innerHeight * {at},
          behavior: 'instant'
        }})"""
    )
    rendered(page)
    passage.click(modifiers=["Alt"], position={"x": 40, "y": 10})
    field = open_compact_comment(page)
    bar = page.locator(".lf-fab-bar")
    assert bar.get_attribute("data-lf-placement") == placement
    window = page.evaluate(
        """async () => {
          const {top, bottom} = (await window.__lfWidgetApi())
            .shownWindow({gap: 8});
          return {top, bottom, scroll: scrollY};
        }"""
    )
    start = bar.bounding_box()
    lines = [f"Line {n} of a comment that keeps growing" for n in range(22)]
    for line in lines:
        page.keyboard.type(line)
        page.keyboard.press("Shift+Enter")
        rendered(page)
        box = bar.bounding_box()
        assert page.evaluate("scrollY") == window["scroll"], (line, box)
        assert box["y"] >= window["top"] - 0.5, (line, box, window)
        assert box["y"] + box["height"] <= window["bottom"] + 0.5, (line, box, window)
    expect(field).to_have_js_property("value", "\n".join(lines) + "\n")
    assert bar.get_attribute("data-lf-placement") == placement
    grown = bar.bounding_box()
    # Grown past the room its side showed, so it moved rather than the page.
    room = (
        window["bottom"] - start["y"]
        if placement == "bottom-start"
        else start["y"] + start["height"] - window["top"]
    )
    assert grown["height"] > room, (start, grown, window)


@pytest.mark.parametrize(
    ("case_name", "example", "required_paths"),
    AIM_PRESS_CASES,
    ids=[case[0] for case in AIM_PRESS_CASES],
)
def test_an_aimed_press_does_only_what_the_outline_promised(
    browser, serve, case_name, example, required_paths
):
    """⌥-click takes the addressable element under the pointer, and that is the whole of what it does.

    Holding ⌥ outlines what a click would take, which is a promise about the next press.
    The runtime used to read that press on the way back up, after every handler out on the
    page had already had it, so the press kept the promise and did something else besides:
    ⌥-clicking an option card opened the composer *and* picked the option, sending Claude a
    decision the user never made, while ⌥-clicking a tab's name aimed at the widget and
    switched the panel under it. Neither shows in the composer, which opens either way.

    So both halves are asserted together — the composer opens on the item that was
    outlined, the press does not focus the control beneath it, and the page's markup
    is as it was after the composer closes. The capture mechanism is layer-wide;
    these pages stand for their distinct downstream paths rather than every repetition
    of those paths.
    `required_paths` keeps that causal selection honest when an example changes.
    """
    url = serve(example)
    if case_name == "ship-review":
        # The native section replaced the task widget that used to carry this mark.
        # Seed one on a remaining widget so the aim still crosses an existing mark.
        append_carried_log_record(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "anchor": {"section": "off-workaround-review"},
                "text": "Keep the upstream dependency visible.",
            },
        )
    page = open_page(browser, url)
    # What the log already held. A shipped seed can carry a decision the user made
    # before this page was opened, and what an aim may not do is add one of its own —
    # so the reading below is against this rather than against nothing.
    seeded = [
        e["id"]
        for e in events_model.read_events(serve.page_dir)
        if e["kind"] == "action"
    ]
    # A suggestion's ✓/✗ stands in the margin layer, which is chrome and no aim target,
    # but a press there is one the page answers, so the sweep takes it as well.
    targets = (
        f"{aim_targets(serve.page_dir)}, "
        ".lf-margin-cluster :is(.lf-sug-accept, .lf-sug-reject)"
    )
    total = page.locator(targets).count()
    pressed = aimed = 0
    reached_paths = set()
    for i in range(total):
        # A control inside a fold or behind an unopened tab is nowhere a user can aim,
        # which is the press sweep's reading of the same question, and a point the panel
        # or a neighbour covers is not this target's press at all.
        target = page.locator(targets).nth(i)
        if not target.is_visible():
            continue
        # A wrapper with no box of its own — one a page's style leaves
        # display: contents — is nowhere a user can aim (AIM_POINT finds no point
        # in it either), and
        # scroll_into_view can wait on its stability forever when it stands inside
        # a table box (a sample). Its slots are their own targets.
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
                  [el.matches('.lf-sug-accept, .lf-sug-reject'),
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
            f"holding ⌥ over {label} in {case_name} promised {promised} and pointed "
            f"a {page.evaluate(AIM_CURSOR)} cursor at it"
        )
        # An element an existing thread already marks, read before the press marks it
        # as the draft's too.
        already_marked = bool(
            promised and page.locator(f"#{promised}.lf-mark-el").count()
        )
        page.mouse.click(*point)
        page.keyboard.up("Alt")
        assert not page.evaluate(FOCUS_IN_PAGE), (
            f"⌥-clicking {label} in {case_name} focused the control under the aim"
        )
        composer = page.locator(".lf-composer")
        bar = page.locator(".lf-fab-bar")
        if "suggestion control" in target_paths and promised:
            # A suggestion's ✓ Accept stands in the margin layer over the page, and a
            # press let through there would send Claude a decision. The aim takes it as
            # a press on the change it stands by, which the markup reading below holds.
            reached_paths.add("suggestion margin control")
        if promised is None:
            # Nothing outlined is nothing to aim at — no item encloses this point — and an
            # armed press then acts on nothing rather than falling back to the page.
            expect(bar).to_be_hidden()
            expect(composer).to_be_hidden()
        else:
            # The sequence promised Comment, so the press focuses its compact field.
            open_compact_comment(page)
            mark = page.evaluate(DRAFT_MARK)
            # An existing thread draws nothing on its element at rest, so a draft on an
            # element the log already marks wears the pending contour like any other.
            if already_marked:
                reached_paths.add("existing mark")
            assert mark == promised, (
                f"⌥-clicking {label} in {case_name} promised {promised} and "
                f"commented on {mark}"
            )
            # And the promise is kept where the user can see it kept. An outline needs
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
                f"⌥-clicking {label} in {case_name} outlined {unshown}, which draws "
                "no box, so the promise is invisible and the composer stands off a rect "
                "at the top of the document"
            )
            # Put the composer away before reading the page back: its own passage wears
            # the outline, which is the one mark an aim is supposed to leave.
            page.keyboard.press("Escape")
            expect(composer).to_be_hidden()
            # Closing the composer may hand focus back to its page subject. Release
            # that focus before comparing markup, which can carry focus-only badges.
            page.evaluate("() => document.activeElement.blur()")
            rendered(page)
            aimed += 1
        assert page.evaluate(PAGE_MARKUP) == before, (
            f"⌥-clicking {label} in {case_name} changed the page, so a press the aim "
            "had taken reached a widget as well"
        )
        pressed += 1
    assert pressed, f"{case_name} pressed nothing, so it asserts nothing"
    # And that the outline is still painted at all: a preview that stopped appearing would
    # leave every press above asserting only that nothing happened, which is the shape of
    # vacuous pass this sweep is most exposed to.
    assert aimed, f"{case_name} outlined nothing, so no press was held to a promise"
    assert reached_paths >= required_paths, (
        f"{case_name} no longer exercises the paths that earned its place in the "
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
    ] == seeded, (
        f"⌥-clicking through {case_name} left a decision in the log that the aim "
        "never promised"
    )


def test_design_mode_comments_on_a_margin_action_without_performing_it(browser, serve):
    """A hoisted target control remains a design target, not a live action.

    Margin actions stand beside the readable column rather than inside the widget they
    act on. Design mode still has to name the underlying widget and take the pointer
    press before the action starts; otherwise Accept sends while the composer opens
    nowhere.
    """
    page = open_page(browser, serve(SUGGESTION_PAGE))
    resized(page, 1440, 900)
    page.keyboard.press("l")
    accept = page.locator('[data-lf-margin-for="sug-refill"] .lf-sug-accept')
    expect(accept).to_be_visible()

    accept.hover()
    expect(page.locator(".lf-inspect")).to_have_text(
        re.compile(r"^Accept .* · lf-suggestion · sug-refill$")
    )
    accept.click()

    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator("#lf-composer-quote")).to_have_text(
        re.compile(r"^design · Accept .* · lf-suggestion · sug-refill$")
    )
    assert page.locator("#sug-refill").get_attribute("aria-busy") is None, (
        "the margin entry action started while Design mode was opening its comment"
    )
    round_trip(page)
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action" and event["widget"] == "sug-refill"
    ], "the margin entry action reached the durable log despite Design mode"
    page.close()

    # The same hoist exists inside frozen markup in a thread. Its target belongs
    # to that thread document, so the margin owner hands Design mode the exact
    # element rather than making it reconstruct ownership from a diagnostic id or path.
    url = serve(leaf_page("inline margin entry action", '<h1 id="h">Review</h1>'))
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-inline-margin",
            "author": "user",
            "revision": 1,
            "text": "Show me the proposed wording.",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-inline-margin",
            "revision": 1,
            "text": "Here is the change:",
            "markup": (
                '<lf-suggestion id="reply-suggestion">'
                "<lf-old>Keep the long label.</lf-old>"
                "<lf-new>Use the short label.</lf-new>"
                "</lf-suggestion>"
            ),
        },
    )
    page = open_page(browser, url)
    open_panel_thread(page, "c-inline-margin")
    # The thread opens with the caret in its reply; Escape stands on the thread.
    page.keyboard.press("Escape")
    page.keyboard.press("l")
    accept = page.locator('[data-lf-margin-for="reply-suggestion"] .lf-sug-accept')
    expect(accept).to_be_visible()

    accept.click()

    expect(page.locator("#lf-composer-quote")).to_have_text(
        re.compile(r"^design · Accept .* · lf-suggestion · reply-suggestion$")
    )
    round_trip(page)
    assert not [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "action" and event["widget"] == "reply-suggestion"
    ], "the inline margin entry action reached the durable log despite Design mode"


def test_a_declared_box_takes_its_comment_on_every_type_that_carries_an_id(
    browser, serve
):
    """`parts` follows the ids the renderer carries, not one diagram type.

    State names, sequence participants, class names, and ER entities are written in the
    source the way a flowchart node is, so each addresses a box across a re-render. A
    composite state and a box inside it each take their own comment. An entity's box
    holds its whole attribute table, so the thread label stays the source name. A later
    version then inserts a state above the anchored one and rebuilds the SVG while the
    authored token remains stable.
    """
    page = open_page(browser, live_url(serve(TYPED_PARTS_PAGE)))

    expected_parts = {
        "life": {"Queued", "Working", "Fetch", "Build", "Done"},
        "shape": {"RUNNER", "JOB"},
        "path": {"A", "B"},
        "exchange": {"User", "Server"},
        "model": {"Job", "Runner"},
    }
    assert page.locator("lf-diagram[parts]").evaluate_all("""diagrams =>
      Object.fromEntries(diagrams.map(diagram => [diagram.id,
        [...diagram.visualParts.keys()].sort()]))
    """) == {
        diagram: sorted(f"node:{name}" for name in parts)
        for diagram, parts in expected_parts.items()
    }

    def aim(target, **press):
        target.click(modifiers=["Alt"], **press)
        open_compact_comment(page)

    state = page.locator('#life g[data-id="Queued"]')
    aim(state)
    expect(page.locator("#lf-composer-quote")).to_have_text("§ diagram · Queued")
    write(page.locator(".lf-composer leaf-text"), "how long does it sit here")
    with sending(page, "the state comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect_comment_notes(page, "#life", 1)

    # A box inside the composite state, declared in its own right.
    aim(page.locator('#life g[data-id="Build"]'))
    expect(page.locator("#lf-composer-quote")).to_have_text("§ diagram · Build")
    page.keyboard.press("Escape")

    aim(page.locator('#life g[data-id="Working"]'), position={"x": 6, "y": 6})
    expect(page.locator("#lf-composer-quote")).to_have_text("§ diagram · Working")
    page.keyboard.press("Escape")

    entity = page.locator('#shape g[data-id="RUNNER"]')
    aim(entity)
    expect(page.locator("#lf-composer-quote")).to_have_text("§ diagram · RUNNER")
    write(page.locator(".lf-composer leaf-text"), "one runner or many")
    with sending(page, "the entity comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect_comment_notes(page, "#shape", 1)

    # A node's label is the words the box shows.
    aim(page.locator('#path g[data-id="A"]'))
    expect(page.locator("#lf-composer-quote")).to_have_text(
        "§ diagram · Bold and plain"
    )
    write(page.locator(".lf-composer leaf-text"), "explain this step")
    with sending(page, "the flowchart comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect_comment_notes(page, "#path", 1)

    aim(page.locator('#exchange g[data-id="User"]:not(.pele-actor-footer)'))
    expect(page.locator("#lf-composer-quote")).to_have_text("§ diagram · User")
    write(page.locator(".lf-composer leaf-text"), "who starts the exchange")
    with sending(page, "the participant comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect_comment_notes(page, "#exchange", 1)

    aim(page.locator('#model g[data-id="Job"]'))
    expect(page.locator("#lf-composer-quote")).to_have_text("§ diagram · Job")
    write(page.locator(".lf-composer leaf-text"), "which job owns this")
    with sending(page, "the class comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    expect_comment_notes(page, "#model", 1)

    posted = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    assert [event["anchor"] for event in posted] == [
        {"section": "life", "visual": "node:Queued"},
        {"section": "shape", "visual": "node:RUNNER"},
        {"section": "path", "visual": "node:A"},
        {"section": "exchange", "visual": "node:User"},
        {"section": "model", "visual": "node:Job"},
    ]
    expect(state).to_have_class(re.compile(r"\blf-mark-el\b"))
    expect(entity).to_have_class(re.compile(r"\blf-mark-el\b"))
    expect(page.locator("#life")).not_to_have_class(re.compile(r"\blf-mark-el\b"))

    # v2 rebuilds the SVG around an inserted state. The mark follows the authored token
    # to the replacement box rather than retaining a detached renderer node.
    state.evaluate("el => { window.lfOldQueued = el; }")
    stamp_page(serve.page_dir, TYPED_PARTS_V2, "one state earlier")
    told(page)
    wait_for_revision(page, 2)
    assert page.evaluate("() => !window.lfOldQueued.isConnected")
    expect(state).to_have_class(re.compile(r"\blf-mark-el\b"))

    page.reload()
    wait_until_ready(page)
    for diagram, name in (
        ("life", "Queued"),
        ("shape", "RUNNER"),
        ("path", "A"),
        ("exchange", "User"),
        ("model", "Job"),
    ):
        expect(
            page.locator(f'#{diagram} g[data-id="{name}"]:not(.pele-actor-footer)')
        ).to_have_class(re.compile(r"\blf-mark-el\b"))
        expect_comment_notes(page, f"#{diagram}", 1)


@pytest.mark.parametrize("reply", [False, True])
def test_open_draft_retains_words_when_responsive_layout_hides_its_target(
    browser, serve, reply
):
    url = serve(COMPOSER_ATTACHMENT_PAGE)
    for target in ("#ordinary", "#bg-contents a"):
        page, words = _open_attachment_draft(browser, url, target)
        field = page.locator(".lf-fab-input")
        if reply:
            with sending(page, "the responsive-target comment"):
                page.keyboard.press("ControlOrMeta+Enter")
            preview = page.locator(".lf-margin-preview")
            expect(preview).to_be_visible()
            rendered(page)
            page.keyboard.press("c")
            field = preview.locator("leaf-text").first
            expect(field).to_be_focused()
            words = "A reply about " + target
            write(field, words)
            rendered(page)
            field.evaluate("el => { window.lfTypedIn = el; }")
        assert _draft_in_view(page, words, field)
        for width in (480, 1200):
            resized(page, width, 900)
            rendered(page)
            expect(field).to_have_js_property("value", words)
            if target == "#bg-contents a" and width == 480:
                # Authored CSS hides the sidebar at this width. The editor retains
                # its native node and draft until the page gives the target room.
                expect(page.locator(target).first).not_to_be_visible()
                expect(field).not_to_be_visible()
                assert not _draft_in_view(page, words, field)
            else:
                if not reply:
                    expect(page.locator(".lf-fab-bar")).to_have_attribute(
                        "data-lf-plane", "page"
                    )
                else:
                    # The thread shows once: the floating panel, which took it while the
                    # page drew its target nowhere, gives it back to the card, and the
                    # user goes on in the editor they typed in, with its caret and undo
                    # history.
                    expect(
                        page.locator(".lf-fp-view:not([data-leaving])")
                    ).to_have_count(0)
                    assert field.evaluate("el => el === window.lfTypedIn")
                assert _draft_in_view(page, words, field)


def test_resume_reveals_an_open_draft_when_its_existing_subject_hides(browser, serve):
    url = serve(COMPOSER_ATTACHMENT_PAGE)
    cases = (
        (
            "disclosure",
            "#detail-word",
            "document.getElementById('disclosure').open=false",
        ),
        (
            "inactive-tab",
            "#tab-word",
            """async () => {
              const {reveal} = await window.__lfCheckApi();
              const {retainUserIntent} = await window.__lfWidgetApi();
              reveal(document.getElementById('other-view'), retainUserIntent());
            }""",
        ),
        (
            "offscreen",
            "#offscreen-word",
            "scrollTo(0,document.documentElement.scrollHeight)",
        ),
    )
    results = []
    for name, target, hide in cases:
        page, words = _open_attachment_draft(browser, url, target)
        page.evaluate(hide)
        rendered(page)
        expect(page.locator(".lf-fab-input")).to_have_js_property("value", words)
        page.keyboard.press("Escape")
        page.keyboard.press("g")
        page.keyboard.press("i")
        expect(page.locator(".lf-fab-input")).to_be_focused()
        results.append((name, "resumed", _draft_in_view(page, words)))
        wait_for(
            lambda page=page, words=words: _draft_in_view(page, words),
            bool,
            failure=f"Resume did not reveal {name}",
        )
        results[-1] = (name, "resumed", _draft_in_view(page, words))
        assert page.locator(".lf-fab-bar").get_attribute("data-lf-plane") == "page"
    assert all((result for name, phase, result in results)), results
