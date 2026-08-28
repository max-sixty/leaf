"""Selection, passage, syntax, and version-navigation tests."""

import json
import re

import pytest
from axe_playwright_python.sync_playwright import Axe
from leaf import events as events_model
from leaf import passages as passages_model
from leaf import registry as registry_model
from playwright.sync_api import expect
from render_support import (
    AIM_SEAM,
    AIM_SEAM_PAGE,
    ASTRAL_PAGE,
    CEILING_PAGE,
    CHIPS,
    CODE_PAGE,
    CONTROL_LABEL_PAGE,
    DIFF_PAGE,
    DRIFT_V1,
    DRIFT_V2,
    EDGE_PAGE,
    EXAMPLES,
    FENCED_CAPTURE_PAGE,
    INLINE_PAGE,
    LONG_PAGE,
    NATIVE_CONTROL_PAGE,
    REPLY_HOST_PAGE,
    SAID_PAGE,
    SHOT_SRC,
    SHOTS,
    SOURCE_EXAMPLES,
    SUGGESTION_PAGE,
    TAIL_PAGE,
    THIN_V1,
    THIN_V2,
    THREAD_ASKS,
    TWICE_PAGE,
    TWO_COPIES_PAGE,
    _publish,
    _traffic,
    compare_with,
    composer_quote,
    key_line,
    live_url,
    mark_point,
    open_page,
    panel_settled,
    post_event,
    round_trip,
    select,
    stamp_version_file,
    ticked,
    told,
    wait_for_revision,
)

pytestmark = pytest.mark.nightly


def test_the_banner_stands_where_it_says_it_does(browser, serve):
    """The document reserves exactly the head covered by the painted banner.

    A missing reservation puts the first block under the banner. A mismatched reservation
    also makes anchored browser scrolls stop above or below the visible page.
    """
    url = serve(LONG_PAGE)
    page, errors = open_page(browser, url)
    stated, drawn = page.evaluate(
        """() => [
            parseFloat(getComputedStyle(document.body, '::before').height),
            document.querySelector('.lf-banner')?.getBoundingClientRect().bottom ?? null,
        ]"""
    )
    page.close()

    assert stated > 0, (
        f"the banner reserves {stated}px, so the page's first block is no longer held "
        "clear of its painted chrome"
    )
    assert drawn == stated, (
        f"the banner is drawn to {drawn}px but the page reserves {stated}px, so the "
        "first block and anchored scrolls land against different edges"
    )
    assert errors == [], errors


@pytest.mark.parametrize("example", SOURCE_EXAMPLES, ids=lambda p: p.stem)
def test_every_passage_in_a_real_page_can_be_quoted(browser, serve, example):
    """Anchoring has to work on the pages people actually write, not on a fixture built
    to suit it. Every failure here has been a place where what the reader selects and
    what the search reads come apart — an uppercased header, a widget's own chrome, the
    stylesheet a rendered diagram carries — and a hand-built page has none of them. So
    this drags across every pair of adjacent blocks in every source example, which is
    the shape a real selection takes, and asks for the highlight the composer promises.

    The generated gallery is not another authored input: scripts/gallery.py derives a
    tab from each source `<main>` and a separate test rejects any drift. Repeating every
    source passage inside that composition used to be most of this sweep's runtime. Tab
    labels and hidden-panel navigation have focused gesture tests, so the source corpus
    retains the content variations while those tests retain the gallery's mechanism.

    "Every" includes the words a widget renders into a control, which is why the filter
    below is the runtime's own rule rather than a test for the chrome class: while it was
    the class, the sweep that proves every passage is quotable structurally could not see
    the passages that weren't. Across the source corpus it reaches attribute-rendered
    headings, settled summaries, and the tab names in parallel-workstreams."""
    page, errors = open_page(browser, serve(example))
    result = page.evaluate("""async () => {
        const tick = () => new Promise(r => setTimeout(r, 0));
        const composer = document.querySelector('.lf-composer');
        const fab = document.querySelector('.lf-fab');
        // A reader reaches everything eventually — opens the details, clicks through to
        // the other tab — so everything is in scope, not just what the page opens on.
        document.querySelectorAll('details').forEach(d => (d.open = true));
        document.querySelectorAll('[hidden]').forEach(e => e.removeAttribute('hidden'));
        // Declared labels are in scope, and the filter is the runtime's own rule rather
        // than the class: a tab's name and a settled row's title are words the page says
        // from inside chrome, which is exactly the shape a filter on .lf-ui cannot see.
        const speaks = el => {
            const near = el.closest('.lf-ui, [data-lf-said]');
            return !near || near.matches('[data-lf-said]');
        };
        const blocks = [...document.querySelectorAll('p,li,h1,h2,h3,td,th,blockquote,'
            + 'figcaption,summary,lf-option,lf-variant,lf-milestone,lf-metric,[data-lf-said]')]
          .filter(b => speaks(b) && b.checkVisibility()
                    && b.textContent.trim().length > 12);
        const missed = [], skipped = [], astray = [];
        for (let i = 0; i < blocks.length; i++) {
            // Each block alone, then reaching into the next one — a drag rarely stops
            // tidily on a boundary, and spanning two blocks is where the joins show.
            for (const end of [blocks[i], blocks[i + 1]].filter(Boolean)) {
                const range = document.createRange();
                range.setStart(blocks[i], 0);
                range.setEnd(end, end.childNodes.length);
                const sel = getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
                document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                await tick();
                // Counted, not shrugged off: a selection the button declines to offer is
                // a passage silently outside this sweep, and the sweep is the coverage.
                if (fab.style.display !== 'block') {
                    skipped.push(range.toString().replace(/\\s+/g, ' ').trim().slice(0, 70));
                    continue;
                }
                fab.click();
                await tick();
                const painted = CSS.highlights.get('lf-pending');
                // The captured quote, read off the node whether or not the reader can
                // see it: the composer shows it only where the page has no mark to give,
                // which is the very case this loop is counting.
                const quoted = document.getElementById('lf-composer-quote').textContent;
                if (!painted || ![...painted].map(r => r.toString()).join('').trim())
                    missed.push(quoted.slice(0, 70));
                // Inside what was selected, not merely somewhere: a matcher that finds
                // the right words in the wrong place paints, and paints a lie.
                //
                // A mark can now land inside a widget's shadow tree (x-shadow), and two
                // ranges in different trees cannot be compared at all — comparing them
                // throws rather than answering. So the question crosses the way the
                // runtime's own does: the tree renders where its host stands, so a mark
                // inside one is inside the selection exactly when the host is.
                else if ([...painted].some(p => {
                        const root = range.commonAncestorContainer.getRootNode();
                        if (p.startContainer.getRootNode() === root)
                            return p.compareBoundaryPoints(Range.START_TO_START, range) < 0
                                || p.compareBoundaryPoints(Range.END_TO_END, range) > 0;
                        let n = p.startContainer;
                        while (n && n.getRootNode() !== root) n = n.getRootNode().host;
                        return !n || !range.intersectsNode(n);
                    }))
                    astray.push(quoted.slice(0, 70));
                composer.style.display = 'none';
                sel.removeAllRanges();
            }
        }
        return {missed, skipped, astray};
    }""")
    assert result["missed"] == [], (
        f"{len(result['missed'])} passages in {example.stem} quote text the page "
        f"can't find: {result['missed']}"
    )
    assert result["skipped"] == [], (
        f"{len(result['skipped'])} passages in {example.stem} raised no Comment button, "
        f"so this sweep never tested them: {result['skipped']}"
    )
    assert result["astray"] == [], (
        f"{len(result['astray'])} passages in {example.stem} painted outside what was "
        f"selected: {result['astray']}"
    )
    assert errors == []
    page.close()


def test_a_widgets_attribute_takes_a_comment_like_any_other_passage(browser, serve):
    """The gesture itself, on the words a widget renders from an attribute: drag across
    a column's heading and the same button, quote, and mark come up as for a paragraph,
    and the comment is still anchored a version later. A real drag, because the whole
    class of bug here is text that looks selectable and isn't — a synthetic Range would
    select what no pointer can.

    Then the other half of the pair, which the same spans decide: the version diff reads
    a block's *authored* text, and the base version it compares against is parsed
    unupgraded, where these spans don't exist. Drop their data-lf-gen and every widget
    holding a said attribute lights up as changed on every revision — a failure that
    looks like a busy page rather than like a bug."""
    page, errors = open_page(browser, live_url(serve(SAID_PAGE)))

    heading = page.locator('lf-column#col-now > [data-lf-said="label"]')
    box = heading.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))

    # The theme uppercases a column heading, so the selection reads back as the reader
    # sees it and the quote as the document holds it — the asymmetry that makes
    # selectionAnchor read the text nodes rather than the selection's own toString().
    assert page.evaluate("() => getSelection().toString()").strip() == "IN FLIGHT", (
        "a drag across the heading selected nothing — it is painted, not said"
    )
    page.locator(".lf-fab").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'block'"
    )
    quoted = composer_quote(page)["text"]
    assert quoted.strip("“”") == "In flight"
    page.locator(".lf-composer textarea").fill("this column's name is wrong")
    page.get_by_role("button", name="Comment", exact=True).click()
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    thread = page.locator(".lf-thread .lf-quote").first
    assert thread.text_content().strip().strip("“”") == "In flight"

    # A second version reworking one card's prose and nothing else. The page follows it,
    # and the anchor is on a word only the runtime puts there, so it has to be found
    # again in the version the user now has.
    d = serve.page_dir
    (d / "versions" / "v2.html").write_text(
        SAID_PAGE.replace("Waiting on the importer.", "Unblocked; starting Thursday.")
    )
    stamp_version_file(d, 2, "two")
    wait_for_revision(page, 2)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert page.locator(".lf-thread .lf-quote.detached").count() == 0, (
        "the comment came loose from the heading when the version turned over"
    )

    compare_with(page)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-ins-block').length > 0"
    )
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-ins-block')].map(e => e.id)"
    ) == ["c-backfill"], "the diff read the runtime's own spans as text the base lacked"
    assert errors == []
    page.close()


def test_browser_and_file_captures_stop_at_the_same_widget_fences(browser, serve):
    """Module-only words may sit between authored parts, but they cannot give the
    browser more context than the version file can confirm."""
    page, errors = open_page(browser, serve(FENCED_CAPTURE_PAGE))
    expect(page.locator("#gate-milestone .lf-chips")).to_have_count(1)
    registry = json.loads((serve.page_dir / "registry.json").read_text())
    cases = [
        ("#gate-milestone strong", "Build feeders", "gate-milestone"),
        ("#gate-milestone", "Two classic models.", "gate-milestone"),
        ("#after-milestone", "Ready next.", "after-milestone"),
        # One chip out of a band of them: authored markup, so both readings hold it
        # for the same reason they hold the title beside it.
        ("#fence-option > lf-chip", "effort: low", "fence-option"),
    ]

    for index, (selector, quote, section) in enumerate(cases, 1):
        expected_anchor = passages_model.capture_anchor(
            FENCED_CAPTURE_PAGE, registry, quote, section
        )
        selected = page.evaluate(
            """([selector, quote]) => {
                const root = document.querySelector(selector);
                const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
                let node;
                while ((node = walker.nextNode())) {
                    const at = node.data.indexOf(quote);
                    if (at === -1) continue;
                    const range = document.createRange();
                    range.setStart(node, at);
                    range.setEnd(node, at + quote.length);
                    const selection = getSelection();
                    selection.removeAllRanges();
                    selection.addRange(range);
                    return selection.toString();
                }
                return null;
            }""",
            [selector, quote],
        )
        assert selected == quote
        page.dispatch_event("body", "mouseup")
        expect(page.locator(".lf-fab")).to_be_visible()
        page.locator(".lf-fab").click()
        page.locator(".lf-composer textarea").fill(f"fence {index}")
        page.get_by_role("button", name="Comment", exact=True).click()
        expect(page.locator(".lf-thread")).to_have_count(index)
        actual_anchor = [
            event["anchor"]
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "comment"
        ][-1]
        assert actual_anchor == expected_anchor, (
            f"{selector} captured {actual_anchor}, file captured {expected_anchor}"
        )

    assert errors == []
    page.close()


def test_workstream_tabs_share_one_collaboration_layer(browser, serve):
    """A focused stream may hide the earlier context, never its collaboration state.

    The shipped example opens on the narrow work in hand. A comment and an ask in
    inactive panels still stand in the page's one Comments list and one Asks tray,
    and either global surface opens the panel it points into. Switching panels is
    reading the page, so it leaves the event log untouched."""
    example = next(p for p in EXAMPLES if p.stem == "parallel-workstreams")
    quote = "The feed has been stable since the battery swap; one open follow-up on storage."
    url = serve(example, anchored=[("camera-note", quote)])
    page, errors = open_page(browser, live_url(url))

    implementation = page.get_by_role("tab", name="Bracket installation")
    vision = page.get_by_role("tab", name="Vision")
    evidence = page.get_by_role("tab", name="Field evidence")
    expect(implementation).to_have_attribute("aria-selected", "true")

    before = events_model.read_events(serve.page_dir)
    sent = _traffic(page).sends
    vision.click()
    implementation.click()
    assert _traffic(page).sends == sent, "switching workstreams sent an event"
    assert events_model.read_events(serve.page_dir) == before

    page.locator(".lf-comments").click()
    # This test's own comment, plus whatever the example ships a log for. Counted
    # rather than fixed at one, because the number is a fact about the corpus and
    # not about tabs: the day this example seeds a thread, a `1` here reds a test
    # that has nothing to say about seeds.
    expect(page.locator(".lf-thread")).to_have_count(
        len([e for e in before if e["kind"] == "comment"])
    )
    comment = page.locator(".lf-thread .lf-quote", has_text="The feed has been stable")
    expect(comment).to_contain_text(quote)
    comment.click()
    expect(evidence).to_have_attribute("aria-selected", "true")

    page.get_by_role("button", name="Close comments").click()
    asks = page.locator(".lf-asks")
    expect(asks).to_have_text("Asks (2)")
    asks.click()
    # The row names the broader Ask's opening context now, while the options inside it
    # still take focus and own the choice.
    hidden_ask = page.locator('.lf-asks-row[data-lf-at="bath-heat-ask"]')
    expect(hidden_ask).to_have_count(1)
    expect(hidden_ask).to_contain_text("The winter habitat keeps food")
    hidden_ask.click()
    expect(vision).to_have_attribute("aria-selected", "true")
    expect(page.locator("#bath-heat .lf-pick").first).to_be_focused()

    assert _traffic(page).sends == sent
    assert events_model.read_events(serve.page_dir) == before
    assert errors == []
    page.close()


def test_a_widgets_label_takes_a_comment_inside_the_control_it_labels(browser, serve):
    """The other half of the pair above: a word the page says that the widget renders
    into a control. A tab's name is the case with nowhere else to go — the panel heading
    the theme paints stands down the moment the strip exists — so if the strip's button
    can't be quoted, the user can read the tab's name and never point at it.

    That is what a user hit, twice, on a draft's heading: the words were the page's
    and the row holding them was marked as the runtime's. `.lf-ui` is a look, and
    anchoring's question is whose words these are — so the label answers it where it is
    written (relabel), and the nearest answer wins over the box around it.

    A real drag, because the whole class of bug is text that looks selectable and
    isn't. Then the republish, because an anchor on a widget's word has to survive a
    version turning over the way one on a paragraph does."""
    page, errors = open_page(browser, live_url(serve(CONTROL_LABEL_PAGE)))

    tab = page.get_by_role("tab", name="Heated bird bath")
    box = tab.bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 6, y), (box["x"] + box["width"] - 6, y))

    assert (
        page.evaluate("() => getSelection().toString()").strip() == "Heated bird bath"
    ), "a drag across the tab's name selected nothing"
    # The drag ended on a button, and the button still switches tabs — but this mouseup
    # was a selection's, not a press, so the reader is still looking at what they were
    # reading when they reached for the name.
    expect(page.locator("#p-feeders")).to_be_visible()

    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    assert composer_quote(page)["text"].strip("“”") == "Heated bird bath"
    page.locator(".lf-composer textarea").fill("call it the bath, not the bird bath")
    page.get_by_role("button", name="Comment", exact=True).click()
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    thread = page.locator(".lf-thread .lf-quote").first
    assert thread.text_content().strip().strip("“”") == "Heated bird bath"

    # A second version reworking the other panel's prose and nothing else: the name the
    # comment is on is still there, so the comment is still on it.
    d = serve.page_dir
    (d / "versions" / "v2.html").write_text(
        CONTROL_LABEL_PAGE.replace(
            "the south pair waits on brackets", "the brackets arrived"
        )
    )
    stamp_version_file(d, 2, "two")
    wait_for_revision(page, 2)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    assert page.locator(".lf-thread .lf-quote.detached").count() == 0, (
        "the comment came loose from the tab's name when the version turned over"
    )
    assert errors == []
    page.close()


def test_a_selection_around_a_control_does_not_deaden_it(browser, serve):
    """The other side of the guard above, and the one that cost more. A user reads
    the sentence a suggestion sits in, drags across it, and then presses Accept — a
    fresh press, long after that drag's own mouseup.

    Asking whether the live selection *contains* the control is a question about the
    DOM, and a suggestion's row is the column's own child in flow between the block
    holding the change and the next one: a drag across both runs straight over it. So
    Accept did nothing, and kept doing nothing, because a press that refuses a drag
    never collapses the selection that deadened it either. The keyboard still worked,
    which is the shape of a bug nobody reports — it looks like a slip of the mouse.

    Both decisions the product exists to collect go through a press, so this asserts the
    pointer and then the keyboard, with the selection standing throughout."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    # Across the two paragraphs, so the row deciding the first is inside the selection.
    start = page.locator("#replace").bounding_box()
    end = page.locator("#insert").bounding_box()
    select(
        page,
        (start["x"] + 4, start["y"] + 6),
        (end["x"] + end["width"] - 6, end["y"] + end["height"] - 6),
        steps=16,
    )
    assert page.evaluate(
        "() => getSelection().containsNode(document.querySelector("
        "'[data-lf-for=sug-refill] .lf-sug-reject'), true)"
    ), "the selection doesn't reach the control, so this run tests nothing"

    page.locator("[data-lf-for='sug-refill'] .lf-sug-reject").click()
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "reject")
    assert page.evaluate("() => !getSelection().isCollapsed"), (
        "the press cleared the selection, so the keyboard half below is untested"
    )
    page.locator("[data-lf-for='sug-in-card'] .lf-sug-accept").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#sug-in-card")).to_have_attribute("data-lf-state", "accept")
    assert errors == []
    page.close()


def test_the_comment_button_stands_on_no_control(browser, serve):
    """And the other way the same press is lost: not deadened but covered. A selection
    fills its lines, so the button placed beside it goes out to the column's right edge —
    into the margin, on the line the change starts, which is exactly where the row
    deciding that change hangs. The user's own gesture put the 💬 over the Accept
    they made it to reach, and the press did the one thing worse than nothing: it hit the
    button and opened a composer, because a press on the 💬 is not the outside click that
    dismisses it.

    Asserted through the hit test rather than the rectangles, since what matters is which
    element the press would reach — and then by making the press, which is the whole
    claim."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    box = page.locator("#replace").bounding_box()
    select(
        page,
        (box["x"] + 4, box["y"] + 6),
        (box["x"] + box["width"] - 8, box["y"] + box["height"] - 6),
        steps=16,
    )
    expect(page.locator(".lf-fab")).to_be_visible()

    under = page.evaluate("""() => [...document.querySelectorAll("[data-lf-offer]")]
        .filter(c => !c.closest(".lf-chrome"))
        .filter(c => { const b = c.getBoundingClientRect();
                       const top = document.elementFromPoint((b.left + b.right) / 2,
                                                            (b.top + b.bottom) / 2);
                       return top && !c.contains(top) && top.closest(".lf-chrome"); })
        .map(c => c.className)""")
    assert under == [], f"floating chrome is standing on controls: {under}"

    page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").click()
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "accept")
    expect(
        page.locator(".lf-composer")
    ).to_be_hidden()  # the press decided, it didn't compose
    assert errors == []
    page.close()


def test_the_margin_offers_one_kind_of_press(browser, serve):
    """The 💬 and a change's ✓ Accept stand in the same margin, sometimes on the same
    line — the test above is that collision — so they have to read as one thing.

    They did not. The button was the chrome's own idiom (a solid accent rectangle at
    the chrome's size, and, through a cascade nobody meant, set in the page's serif
    three points larger than every other control in the layer) beside two hairline
    pills, which put two idioms four centimetres apart in the one place a reader
    compares them. Where a control stands decides which it wears: in the runtime's
    furniture a press is a .lf-btn and looks like one, and out in the margin it is a
    marginal mark.

    Pinned by reading both off one page. The pill is one statement now (.lf-pill, in
    the runtime's document-level vocabulary), but either wearer can still restate a
    property in its own rules — the fab's scoped block and the suggestion's state
    rules both layer over it — and this is what says such a restatement kept the
    family. The shadow is the one property allowed to differ, and it is the
    difference that is real: only one of them floats over the page's own words rather
    than standing in the empty rail."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    box = page.locator("#replace").bounding_box()
    select(
        page,
        (box["x"] + 4, box["y"] + 6),
        (box["x"] + box["width"] - 8, box["y"] + box["height"] - 6),
        steps=16,
    )
    expect(page.locator(".lf-fab")).to_be_visible()
    # The drag ends where the button is raised, so the pointer is on it: both are read
    # at rest, since a hover state read against a resting one compares nothing.
    page.mouse.move(4, 4)

    family = """el => { const s = getComputedStyle(el);
        return Object.fromEntries(["font-family", "font-size", "line-height",
            "border-radius", "border-top-width", "border-top-style", "padding",
            "background-color", "color"].map(p => [p, s.getPropertyValue(p)])); }"""
    raised = page.locator(".lf-fab").evaluate(family)
    resident = page.locator("[data-lf-for='sug-refill'] .lf-sug-accept").evaluate(
        family
    )
    assert raised == resident, (
        "the margin's two presses are drawn differently:\n  "
        + "\n  ".join(
            f"{k}: {raised[k]!r} vs {resident[k]!r}"
            for k in raised
            if raised[k] != resident[k]
        )
    )
    assert "system-ui" in raised["font-family"], (
        f"the margin's presses speak in the document's voice: {raised['font-family']}"
    )
    assert (
        page.locator(".lf-fab").evaluate("el => getComputedStyle(el).boxShadow")
        != "none"
    ), "the one press that floats over the page says nothing about it"
    assert errors == []
    page.close()


def test_one_chip_says_every_keyboard_address(browser, serve):
    """A digit that reaches something is drawn one way, on both sides of the scope line.

    The g chord's chips answer its digits and an option wears the one a pick answers, and
    this page shows them at once — a question asked inside a thread, so the two chips
    stand a couple of centimetres apart in the same panel. They were two hand-matched
    copies of a dozen declarations, one in the chrome's stylesheet and one in the theme,
    with nothing to say if either moved; the look is .lf-address in the runtime's
    document-level vocabulary now, and each wearer states only where its chip sits and
    when it shows.

    Which is why the look is what this compares and placement is not: the chord's chips
    are placed from the viewport in a layer of their own, and an option's is anchored
    from outside the group that would otherwise clip it (see
    test_a_questions_digits_are_drawn_whole). Same chip, two boxes to hang it from.

    Width is the third kind, and it is content: a chip is as wide as the keys it carries,
    and these two carry different numbers of them — a pick answers one digit, the chord
    carries the whole motion it is halfway through. So the shared minimum and padding are
    compared and the result of them is not, and the difference is asserted in the
    direction it has to run.
    The face is compared because it is the half a letter made load-bearing: in the
    document's sans a lowercase l is a bare stroke, and the chord's second link wore what
    read as 12."""
    url = serve(REPLY_HOST_PAGE)
    for event in THREAD_ASKS:
        events_model.append_event(serve.page_dir, event)
    page, errors = open_page(browser, url)

    # `n` opens the panel on the first ask and lands on its mark, which is what paints
    # that group's digits; g c then aims the chord at the comments, which paints theirs.
    page.keyboard.press("n")
    picked = page.locator("#tq-one .lf-address").first
    expect(picked).to_be_visible()
    page.keyboard.press("g")
    page.keyboard.press("c")
    addressed = page.locator(CHIPS).first
    expect(addressed).to_be_visible()

    # Both faces resolved and read inside one turn. The chord's layer is rebuilt on every
    # repaint — and an armed window repaints on every scroll frame — so an element held
    # across a round trip can be detached by the time it is asked, and a detached node
    # answers every property with the empty string. Read one at a time this passed alone
    # and failed under the parallel suite, which is the load that opens the window.
    faces = """() => {
        const read = el => { const s = getComputedStyle(el);
            return Object.fromEntries(["min-width", "height", "padding", "box-sizing",
                "border-top-width", "border-top-style", "border-top-color",
                "border-radius", "background-color", "color", "font-family", "font-size",
                "line-height", "text-align", "z-index"]
                .map(p => [p, s.getPropertyValue(p)])); };
        return [read(document.querySelector('#tq-one .lf-address')),
                read(document.querySelector('.lf-addresses > .lf-address'))]; }"""
    on_page, in_panel = page.evaluate(faces)
    assert on_page == in_panel, (
        "the two keyboard addresses are drawn differently:\n  "
        + "\n  ".join(
            f"{k}: {on_page[k]!r} vs {in_panel[k]!r}"
            for k in on_page
            if on_page[k] != in_panel[k]
        )
    )
    # A key chip is set the way every other key chip on the product is: the reader meeting
    # the same key on the line and on the page reads one glyph for it, and the two rules
    # that dress the two — one inside the chrome's scope, one outside it, so they cannot be
    # one rule — agree on the shape by hand. Asserted rather than asserted-in-a-comment.
    line_chip = page.evaluate(
        """() => { const el = document.querySelector('.lf-keyline kbd');
             const s = getComputedStyle(el);
             return {"font-family": s.fontFamily, "border-radius": s.borderRadius}; }"""
    )
    assert "mono" in on_page["font-family"], (
        f"a keyboard address is not set in the key face: {on_page['font-family']}"
    )
    for key in line_chip:
        assert line_chip[key] == on_page[key], (
            f"the line and the page dress a key differently — {key}: "
            f"{line_chip[key]!r} vs {on_page[key]!r}"
        )

    # And what each is wide enough for is its own keys. The pick's one digit comes out at
    # the shared floor exactly, which is the half a compared `min-width` cannot prove: a
    # wearer restating `width: 19px` on its own copy would raise nothing and pass every
    # property above. The chord's leader, letter and digit come out past it. Both are read
    # from the rendered box, since the widths are the key face's answer and not the
    # stylesheet's.
    floor = float(on_page["min-width"].removesuffix("px"))
    widths = page.evaluate(
        """() => ['#tq-one .lf-address', '.lf-addresses > .lf-address']
                   .map(sel => document.querySelector(sel)
                                 .getBoundingClientRect().width)"""
    )
    assert widths[0] == floor, (
        f"a one-key chip is not at the shared minimum the rule states: {widths[0]} vs "
        f"{floor} — a wearer has restated a width of its own"
    )
    assert widths[0] < widths[1], (
        f"the chord's whole-address chip is not wider than a pick's one-key chip: {widths}"
    )
    assert errors == []
    page.close()


def test_the_composer_opens_where_the_button_stood(browser, serve):
    """Stepping the button aside is undone if what it opens goes back. The button carries
    the anchor it was raised on, and it used to carry the position it was *asked for*
    alongside — the same point for as long as nothing moved it, and a different one from
    the moment something did. So the 💬 cleared the row and the composer it opened landed
    back on top of it."""
    page, errors = open_page(browser, serve(SUGGESTION_PAGE))
    box = page.locator("#replace").bounding_box()
    select(
        page,
        (box["x"] + 4, box["y"] + 6),
        (box["x"] + box["width"] - 8, box["y"] + box["height"] - 6),
        steps=16,
    )
    expect(page.locator(".lf-fab")).to_be_visible()
    stood = page.locator(".lf-fab").evaluate("el => el.getBoundingClientRect().top")
    # It moved, or this run would hold whether or not the position were carried along.
    assert stood > page.locator("[data-lf-for='sug-refill']").evaluate(
        "el => el.getBoundingClientRect().bottom"
    ), "the button never stepped aside, so where it stood proves nothing"

    page.locator(".lf-fab").click()
    expect(page.locator(".lf-composer")).to_be_visible()
    opened = page.locator(".lf-composer").evaluate(
        "el => el.getBoundingClientRect().top"
    )
    assert abs(opened - stood) <= 1, (
        f"the composer opened at {opened}, where the button was asked for, not {stood}"
    )
    assert errors == []
    page.close()


def test_a_drag_released_mid_word_hugs_words_and_sentences(browser, serve):
    """A drag stops where the hand stopped: four glyphs into "paragraph", four short
    of the end of "carrying". The reader meant the words, and the quote the capture
    would otherwise store — "graph carr" — reads as a typo in the panel and in every
    reply that quotes it back. So the pointer path grows a selection out to word
    boundaries, outward only: an end resting in space or against punctuation is
    already where the reader put it, so "it," gains its 't' and not its comma, and a
    word split across inline markup — here by splitText, which also leaves the empty
    text node that puts two EDGEs flush in the indexed reading — still grows whole.

    What the pointer path must not do is here too. A keyboard selection is never
    grown — shift-arrow is the reader being precise — so the key release that raises
    the button leaves a mid-word selection exactly as made, and so does the right
    button, whose release precedes the context menu Copy lives in. A right-to-left
    drag keeps its direction, asked of boundary points rather than node order because
    a selection ending on the element holding its own start both precedes and
    contains it. And machine-placed words never glue to the author's, on either
    side of the declaration line: an undeclared generated span is a fenced cell in
    the reading, and a declared label — a specimen's, rendered flush before its
    words inside a list item, where both share the one block — is the seam itself.

    A sentence follows the same rule at its two meaningful edges. A drag that already
    reaches its opening and closing words grows over the punctuation around them, but
    two words from its middle remain those two words. Sentence edges take only adjacent
    punctuation, so status glyphs outside an opening quote remain outside. The whole
    drag must stay in one rendered block; matching endpoints around a nested paragraph
    do not make the intervening blocks one sentence.

    The reads await one queued step first, the same tick the mouseup handler defers
    its own work behind, so each one sees the selection after the snap rather than
    racing it."""
    page, errors = open_page(
        browser,
        serve(
            INLINE_PAGE.replace(
                '<p id="p">',
                '<ul><li><lf-specimen id="spec" label="mono">glyphs set close'
                "</lf-specimen></li></ul>\n"
                '<p id="sentence">🔴 🟢 “<strong>Opening</strong> words stay '
                "<em>together</em>.” 🔴 🟢 Next sentence.</p>\n"
                '<ul><li id="nested">“Opening words<p>Nested block.</p>'
                'closing together.”</li></ul>\n<p id="p">',
            )
        ),
    )
    page.locator("#p").scroll_into_view_if_needed()
    # The point one pixel inside a character's own box, so a press there puts the
    # boundary at the character's left edge — mid-word when the character is.
    mid = """(args) => {
        const walk = document.createTreeWalker(
            document.querySelector(args.root), NodeFilter.SHOW_TEXT);
        for (let n = walk.nextNode(); n; n = walk.nextNode()) {
            const at = n.data.indexOf(args.word);
            if (at < 0) continue;
            const r = document.createRange();
            r.setStart(n, at + args.into);
            r.setEnd(n, at + args.into + 1);
            const box = r.getBoundingClientRect();
            return [box.left + 1, box.top + box.height / 2];
        }
    }"""
    settled = (
        "async () => { await new Promise(r => setTimeout(r, 0));"
        " return getSelection().toString(); }"
    )

    def spot(root, word, into):
        return page.evaluate(mid, {"root": root, "word": word, "into": into})

    select(
        page,
        spot("#sentence", "Opening", 3),
        spot("#sentence", "together", 4),
    )
    assert page.evaluate(settled) == "“Opening words stay together.”"

    sentence_box = page.locator("#sentence").bounding_box()
    page.mouse.click(sentence_box["x"] - 40, sentence_box["y"] + 4)
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    page.locator("#sentence").scroll_into_view_if_needed()
    select(page, spot("#sentence", "words", 2), spot("#sentence", "stay", 2))
    assert page.evaluate(settled) == "words stay"

    page.mouse.click(sentence_box["x"] - 40, sentence_box["y"] + 4)
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    page.locator("#nested").scroll_into_view_if_needed()
    select(page, spot("#nested", "Opening", 3), spot("#nested", "together", 4))
    assert " ".join(page.evaluate(settled).split()) == (
        "Opening words Nested block. closing together"
    )

    nested_box = page.locator("#nested").bounding_box()
    page.mouse.click(nested_box["x"] - 40, nested_box["y"] + 4)
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    page.locator("#p").scroll_into_view_if_needed()
    select(page, spot("#p", "paragraph", 4), spot("#p", "carrying", 4))
    assert page.evaluate(settled) == "paragraph carrying"
    expect(page.locator(".lf-fab")).to_be_visible()

    # The bar the selection raised stands above it, over the line the next drag starts
    # on; a press in the margin beside the paragraph is the reader's own move that
    # takes it down, and moves nothing else. Read back before the drag, because the
    # bar comes down in the press's own handler and the drag must not race it.
    beside = page.locator("#p").bounding_box()
    page.mouse.click(beside["x"] - 40, beside["y"] + 4)
    expect(page.locator(".lf-fab-bar")).to_be_hidden()
    assert page.evaluate(settled) == ""
    select(page, spot("#p", "inside", 2), spot("#p", "it,", 1))
    assert page.evaluate(settled) == "inside it"

    # The same words dragged right to left: snapped the same, and still facing
    # backward, or the shift-click that extends it next extends the wrong end. The
    # click first is the reader's own move — a press inside the standing selection
    # would drag its text, not start a new one.
    page.locator("#t").click()
    select(page, spot("#p", "it,", 1), spot("#p", "inside", 2))
    assert page.evaluate(settled) == "inside it"
    assert page.evaluate(
        "() => { const s = getSelection();"
        " return s.anchorNode === s.focusNode ? s.anchorOffset > s.focusOffset"
        " : Boolean(s.anchorNode.compareDocumentPosition(s.focusNode)"
        " & Node.DOCUMENT_POSITION_PRECEDING); }"
    ), "a right-to-left drag came out of the snap facing forward"

    page.evaluate("""() => {
        const n = document.querySelector('#p').firstChild;
        const at = n.data.indexOf('paragraph') + 2;
        getSelection().setBaseAndExtent(n, at, n, at + 5);
    }""")
    page.keyboard.press("Shift")
    assert page.evaluate(settled) == "ragra"
    where = spot("#p", "paragraph", 4)
    page.mouse.click(where[0], where[1], button="right")
    assert page.evaluate(settled) == "ragra"

    forward_kept = page.evaluate("""async () => {
        const p = document.querySelector('#p2');
        const at = p.firstChild.data.indexOf('neighbouring') + 3;
        getSelection().setBaseAndExtent(p.firstChild, at, p, p.childNodes.length);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        await new Promise(r => setTimeout(r, 0));
        const s = getSelection();
        const r = s.getRangeAt(0);
        return s.anchorNode === r.startContainer && s.anchorOffset === r.startOffset;
    }""")
    assert forward_kept, "a forward selection ending on an element came out backward"

    page.evaluate("""() => {
        const n = document.querySelector('#p').firstChild;
        const at = n.data.indexOf('paragraph') + 4;
        n.splitText(at);
        n.splitText(at); // at the new node's own end, so the second piece is empty
    }""")
    select(page, spot("#p", "graph", 1), spot("#p", "carrying", 4))
    assert page.evaluate(settled) == "paragraph carrying"

    page.evaluate("""() => {
        const p2 = document.querySelector('#p2');
        const rest = p2.firstChild.splitText(p2.firstChild.data.indexOf(' between'));
        const span = document.createElement('span');
        span.setAttribute('data-lf-gen', '');
        span.textContent = 'flagged';
        p2.insertBefore(span, rest); // flush: the page now reads "boundaryflagged"
    }""")
    select(page, spot("#p2", "flagged", 3), spot("#p2", "them", 1))
    assert page.evaluate(settled) == "flagged between them"

    # The declared label: rendered by the real pass, flush before the specimen's own
    # words, unfenced because the registry models it — so the reading holds
    # "monoglyphs", and only the seam keeps a drag into "glyphs" from taking "mono".
    select(page, spot("lf-specimen", "glyphs", 3), spot("lf-specimen", "close", 3))
    assert page.evaluate(settled) == "glyphs set close"
    assert errors == []
    page.close()


def test_a_quote_finds_its_passage_whatever_its_whitespace(browser, serve):
    """The same passage gets written down several ways. The page holds it with the
    author's line wraps; a selection renders it with a break where two blocks abut and
    none where one wrapped; older versions of this runtime stored a third form again.
    All of them name the same words, so all of them have to find them — otherwise a
    comment made last month hangs off a passage the page insists isn't there."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, live_url(url))
    passage = "bold text and emphasis inside it"
    forms = {
        "as the page holds it": passage,
        "wrapped where a source line ended": passage.replace(" and ", "\nand "),
        "broken where a block ended": passage.replace(" and ", "\n\nand\n"),
        "spaced out by an editor": passage.replace(" ", "   "),
        # Reaching across the boundary between two blocks, which the reader sees as a
        # line break, the source writes as a newline, and a rendering may write as neither.
        "spanning two blocks": "more than one text node. A neighbouring block",
    }
    for name, quote in forms.items():
        post_event(
            page,
            url.rsplit("/versions/", 1)[0] + "/api/event",
            data={
                "kind": "comment",
                "revision": 1,
                "text": name,
                "anchor": {"section": None, "quote": quote},
            },
        )
    page.locator(".lf-comments").click()
    page.wait_for_function(
        f"() => document.querySelectorAll('.lf-thread').length === {len(forms)}"
    )
    stranded = page.locator(".lf-panel .lf-quote.detached").all_text_contents()
    assert stranded == [], f"quotes naming a passage that is right there: {stranded}"

    # The elasticity runs one way only. A quote is free to have gaps the page lacks; a
    # page's gaps are word boundaries, and a quote that runs across one is naming
    # something the page doesn't say — "never" must not find the tail of "on every".
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "words the page never runs together",
            "anchor": {"section": None, "quote": "boldtext"},
        },
    )
    page.wait_for_function(
        f"() => document.querySelectorAll('.lf-thread').length === {len(forms) + 1}"
    )
    assert page.locator(".lf-panel .lf-quote.detached").count() == 1, (
        "a quote gluing two of the page's words together still found a passage"
    )

    # Nor may a gap close up onto a compound the page writes as one word. "set up" and
    # "setup" are different words, and the page has both — the anchor has to land on the
    # one that was dragged, and it is stored, so landing wrong is permanent.
    landed = page.evaluate("""async () => {
        const p = document.querySelector('#compound');
        const at = p.firstChild.data.indexOf('set up');
        const r = document.createRange();
        r.setStart(p.firstChild, at); r.setEnd(p.firstChild, at + 6);
        const s = getSelection(); s.removeAllRanges(); s.addRange(r);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        await new Promise(x => setTimeout(x, 30));
        document.querySelector('.lf-fab').click();
        await new Promise(x => setTimeout(x, 30));
        const painted = [...(CSS.highlights.get('lf-pending') ?? [])][0];
        return painted && painted.compareBoundaryPoints(Range.START_TO_START, r) === 0;
    }""")
    assert landed, "'set up' anchored onto 'setup', an earlier and different word"
    assert errors == []
    page.close()


def test_the_captured_quote_is_prose_a_file_can_hold(browser, serve):
    """A quote is read back as prose — seeded into the suggestion box, printed in the
    panel, emitted into a Markdown blockquote by `leaf transcript` — and written to a
    UTF-8 file on the way. Source text is neither: it carries the author's line wraps,
    which break a blockquote open, and cutting it to length by UTF-16 unit can halve a
    character, which no UTF-8 file can hold. The server refuses that write and the
    reader is told it is offline, with no way to ever send the comment."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)

    def compose_on(block):
        page.locator(block).click(click_count=3)
        page.locator(".lf-fab").click()
        page.wait_for_function(
            "() => document.querySelector('.lf-composer').style.display === 'block'"
        )

    # Read off the composer's description of its own anchor, which is the captured quote
    # verbatim — the string that goes on to the panel, the file, and the export.
    compose_on("#p")  # authored across two source lines
    wrapped = composer_quote(page)["text"]
    assert "\n" not in wrapped, f"the quote carries the source's line wrap: {wrapped!r}"
    page.get_by_role("button", name="Cancel").click()

    # Measured in the page: a lone surrogate does not survive the trip out to the test
    # runner, which replaces it, so asking out here would always come back clean.
    # Iterating by code point, a character cut in half is left as a single unit in the
    # surrogate range; an intact one comes through as the pair it is.
    compose_on("#cap")
    assert not page.evaluate("""() => [...document.getElementById('lf-composer-quote').textContent]
        .some(c => c.length === 1 && c.charCodeAt(0) >= 0xd800 && c.charCodeAt(0) <= 0xdfff)"""), (
        "the 400-character cap split a character in half"
    )

    # And the round trip that proves it: the server has to accept the quote and write it
    # to a UTF-8 file. A half character fails there, reported to the reader as an offline
    # server, and no retry can ever succeed.
    page.locator(".lf-composer textarea").fill("a comment on the capped passage")
    page.locator(".lf-composer").get_by_role("button", name="Comment").click()
    page.wait_for_function("""() => document.querySelectorAll('.lf-thread').length === 1
        || document.querySelector('.lf-toast').classList.contains('show')""")
    assert page.locator(".lf-thread").count() == 1, (
        f"the comment never posted — the page says {page.locator('.lf-toast').text_content()!r}"
    )
    assert errors == []
    page.close()


def test_an_open_composer_does_not_eat_the_next_click(browser, serve):
    """Clicks keep working while a composer is open. The composer comes down on the
    document's mousedown, and anything that rewrites the page's marks there swaps out
    the node under the pointer between press and release — which is a click the
    browser never dispatches at all. So a thread's highlight stops opening its thread,
    and a link inside a highlighted passage stops navigating. Real button presses,
    because a synthetic click event sails straight past the gap it lives in."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, live_url(url))
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "on the passage",
            "anchor": {"section": "p", "quote": "bold text"},
        },
    )
    told(page)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    # Open a composer on other text and type nothing, so the next mousedown outside it
    # is the one that takes it down.
    page.locator("#q").click(click_count=3)
    page.locator(".lf-fab").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'block'"
    )

    # The click that selected #q also scrolled it into view. Bring the other passage
    # back before deriving a viewport coordinate from its range; a negative-y
    # Mouse.click is no user gesture and can only prove that nothing was hit.
    page.locator("#p").scroll_into_view_if_needed()
    page.mouse.click(*mark_point(page, "lf-mark"))
    panel_settled(page)

    # And the composer's own mark belongs to no thread, so it opens nothing. Its first
    # range runs up to the posted one, so this lands on the draft and nothing else.
    page.get_by_role("button", name="Close comments").click()
    page.locator("#p").click(click_count=3)
    page.locator(".lf-fab").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'block'"
    )
    page.mouse.click(*mark_point(page, "lf-pending"))
    assert not page.locator(".lf-panel").evaluate(
        "el => el.classList.contains('open')"
    ), (
        "clicking the composer's own highlight opened the panel, but it belongs to no thread"
    )
    assert errors == []
    page.close()


def test_a_click_on_a_mark_decides_once(browser, serve):
    """Opening the panel reflows the document, so anything that hit-tests the page after
    the panel opens is testing geometry that has already moved. When two handlers each
    asked where the pointer was, the second missed the mark the first had just opened and
    raised the comment button on top of it — and the element anchor that left behind reads
    as composition in progress, which is what stops a page following new versions. The
    panel starts shut here because a panel already open is the case with no reflow."""
    version_url = serve(INLINE_PAGE)
    url = live_url(version_url)
    page, errors = open_page(browser, url)
    # A quote inside the figure's caption: a painted range, so opening the panel reflows the
    # text out from under the pointer. An element anchor wouldn't show it — a figure still
    # covers the same point after the column narrows.
    post_event(
        page,
        version_url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "on the caption",
            "anchor": {"section": "fig", "quote": "A specimen, for element anchors."},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    if page.locator(".lf-panel.open").count():
        page.get_by_role("button", name="Close comments").click()
        panel_settled(page, open=False)

    page.locator("#fig").scroll_into_view_if_needed()
    spot = page.evaluate("""() => { const r = [...CSS.highlights.get('lf-mark')][0].getClientRects()[0];
                                    return {x: r.left + r.width / 2, y: r.top + r.height / 2}; }""")
    page.mouse.click(spot["x"], spot["y"])
    panel_settled(page)
    expect(
        page.locator(".lf-fab"),
        "the click opened the thread and then offered to comment on it as well",
    ).not_to_be_visible()

    # The harm that outlives the stray button: a page mid-composition stays put.
    d = serve.page_dir
    (d / "versions" / "v2.html").write_text(
        INLINE_PAGE.replace('<h1 id="t">Inline</h1>', '<h1 id="t">Inline II</h1>')
    )
    stamp_version_file(d, 2, "two")
    wait_for_revision(page, 2)
    assert errors == []
    page.close()


def test_code_is_colored_without_a_word_moving(browser, serve):
    """Colouring is spans, and the anchor pass is what spans break: the version file holds
    one run of characters where the DOM now holds a dozen nodes. A <span> is no text block,
    so both readings collapse to the same string — which is what lets the runtime color a
    block the file knows nothing about, and what keeps `leaf comment` able to quote
    into one.

    One pass serves both shapes a page has for code, lf-code's `language` and a plain
    <pre><code class="language-*">, and neither guesses: a lf-code with no `language` stays
    the color of its own ink. The quote below is written the way `leaf comment`
    writes one — against the file — and spans a token boundary on its way back."""
    url = serve(CODE_PAGE)
    page, errors = open_page(browser, url)
    page.wait_for_function(
        "() => document.querySelector('lf-code.lf-rendered') !== null"
    )

    roles = page.evaluate("""() => {
      const at = sel => [...document.querySelectorAll(sel + ' [data-lf-syn]')]
        .map(e => [e.dataset.lfSyn, e.textContent]);
      return { widget: at('#walk-code'), plain: at('#walk pre > code'),
               undeclared: at('#plain-code') };
    }""")
    assert ["kw", "def"] in roles["widget"] and ["fn", "bucket_key"] in roles["widget"]
    assert {r for r, _ in roles["widget"]} >= {"kw", "st", "fn"}, roles["widget"]
    assert ["cm", "# apply the migration, then run the marked suite"] in roles["plain"]
    assert roles["undeclared"] == [], (
        f"a lf-code with no language was colored anyway: {roles['undeclared']}"
    )

    # The words each block holds, unchanged by the spans: what the file says is what the
    # page says, which is the whole reason a quote written against one lands in the other.
    # The widget numbers lines, so its own newline is the join; the note it docks at line 2
    # is prose and sits outside the code.
    assert page.evaluate(
        "() => document.querySelector('#walk pre > code').textContent"
    ) == (
        "# apply the migration, then run the marked suite\ncd gateway && alembic upgrade head"
    )
    # Read the way the runtime reads it: everything generated set aside. The highlighted
    # line carries a word of the layer's own (below), and a reading that counted it would
    # be claiming the file holds a word no version of it ever will.
    assert page.evaluate(
        "() => [...document.querySelectorAll('#walk-code .lf-code-line')]"
        ".map(l => [...l.childNodes].filter(n => !(n.nodeType === 1 && n.dataset.lfGen))"
        ".map(n => n.textContent).join('')).join('')"
    ) == (
        "def bucket_key(request):\n    if request.token:\n"
        '        return f"tok:{request.token.id}"\n    return "anon"\n'
    )

    # `hi` is a background tint and says which line the note beside it is about. Nothing
    # of that reaches a reader listening, who gets the block entire with no idea which of
    # it was pointed at — and the numbers can't tell them, being a CSS counter painted
    # into no text node so that a copy of the block is source and not a listing. So the
    # highlighted line says so itself, once, where it is true.
    lines = page.locator("#walk-code .lf-code-line")
    assert "highlighted" in lines.nth(1).aria_snapshot()
    assert page.locator("#walk-code .lf-quiet").count() == 1, (
        "the tinted line is the one that says it, and it says it once"
    )

    # A quote across a token boundary — "upgrade" is plain, "head" is a keyword span.
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "does prod want --sql here?",
            "anchor": {
                "section": "walk",
                "quote": "alembic upgrade head",
                "prefix": "on, then run the marked suite cd gateway &&",
                "suffix": "",
            },
        },
    )
    page.locator(".lf-comments").click()
    # Posted to the server rather than through the page, so the page hears about it
    # when its next poll asks.
    told(page)
    expect(page.locator(".lf-thread")).to_have_count(1)
    expect(page.locator(".lf-panel .lf-quote.detached")).to_have_count(0)
    # The mark is a painted range, so what it covers is read back off CSS.highlights
    # rather than off the DOM.
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    marked = page.evaluate("""() => [...CSS.highlights.get('lf-mark').values()]
                                     .map(r => r.toString()).join("")""")
    assert marked == "alembic upgrade head", f"the mark landed on {marked!r}"
    assert errors == []
    page.close()


def test_every_language_returns_the_source_it_was_given(browser, serve):
    """`syntax` promises the tokens partition the source exactly, and lf-code's line
    numbers, `hi`, and every note's `at` are counted off that partition — so a tokenizer
    that dropped a character would slide all three with nothing on screen saying so. The
    promise is checked at the boundary and the check throws; this drives every language
    the registry offers through the real module, including each one against another
    language's source, which is where a lexer meets input it was never written for.

    It is also what a version bump of the vendored bundle has to survive."""
    url = serve(CODE_PAGE)
    page, errors = open_page(browser, url)
    langs = registry_model.load_registry(serve.page_dir)["$languages"]["names"]
    samples = [
        'def f(x):\n    """doc\n    <b>&amp;</b>\n    """\n    return f"{x!r}"  # ok\n',
        '# c\ncd x && ls -la | grep "a b" > /dev/null\n',
        '{"a": [1, 2, {"b": null}], "c": "<>&"}\n',
        "@@ -1 +1 @@\n-a <b>\n+c &d\n",
        "SELECT * FROM t WHERE a = 'x''y'; -- note\n",
        '<!doctype html>\n<a href="x?a=1&b=2">t &amp; u</a>\n',
    ]
    bad = page.evaluate(
        """async ([langs, samples]) => {
          const { syntax } = await import('/runtime/syntax.js');
          const bad = [];
          for (const lang of langs)
            for (const src of samples) {
              try {
                const tokens = await syntax(src, lang);
                const back = tokens.map(t => t.text).join('');
                if (back !== src) bad.push([lang, src, back]);
              } catch (e) { bad.push([lang, src, String(e)]); }
            }
          return bad;
        }""",
        [langs, samples],
    )
    assert bad == [], f"the tokenizer changed the source: {bad}"

    pierre_bad = page.evaluate(
        """async (langs) => {
          const { parsePatchFiles, preloadDiffHTML } =
            await import('/vendor/pierre-diffs.esm.js');
          const source = [
            'diff --git a/example.txt b/example.txt',
            '--- a/example.txt',
            '+++ b/example.txt',
            '@@ -1 +1 @@',
            '-old',
            '+new',
          ].join('\\n');
          const bad = [];
          for (const lang of langs) {
            try {
              const file = parsePatchFiles(source, undefined, true)[0].files[0];
              file.lang = lang;
              const html = await preloadDiffHTML({
                fileDiff: file,
                options: {theme: {light: 'github-light', dark: 'github-dark'}},
              });
              if (!html.includes('new')) bad.push([lang, 'rendered no source']);
            } catch (error) {
              bad.push([lang, String(error)]);
            }
          }
          return bad;
        }""",
        langs,
    )
    assert pierre_bad == [], f"Pierre lacks a declared language: {pierre_bad}"
    assert errors == []
    page.close()


def test_a_diff_is_colored_by_each_files_own_path(browser, serve):
    """Pierre renders each file in its own language without changing copyable source.

    A unified diff has no one language, so the file path chooses it and an unknown path
    stays plain. The indicator column is presentation, not source: it must be absent from
    both syntax input and selection text. Pierre still tokenizes each reconstructed side
    as a whole, so a Python string spanning changed lines remains a string."""
    page, errors = open_page(browser, serve(DIFF_PAGE))
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )

    # Through the declared shadow root, where the static Pierre DOM remains visible to
    # Leaf's passage reader and to a standalone export.
    files = page.evaluate("""() => [...document.querySelector('#patch').shadowRoot
      .querySelectorAll('details')].map(d => {
      const path = d.querySelector('.lf-diff-path');
      const stat = d.querySelector('.lf-diff-stat');
      return {
        path: path.textContent,
        statGenerated: stat.dataset.lfGen === '1',
        summaryAligned: Math.abs(path.getBoundingClientRect().top
          - stat.getBoundingClientRect().top) < 1,
        lines: [...d.querySelectorAll('[data-line]')].map(l => ({
          kind: l.dataset.lineType,
          text: l.textContent,
          indicator: getComputedStyle(l, '::before').content,
          indicatorSelect: getComputedStyle(l, '::before').userSelect,
          roles: [...l.querySelectorAll('[data-lf-syn]')]
            .map(s => [s.dataset.lfSyn, s.textContent]),
        })),
        separators: [...d.querySelectorAll('[data-separator]')].map(s => ({
          text: s.textContent.trim(),
          chrome: s.classList.contains('lf-ui'),
        })),
      };
    })""")
    by_path = {f["path"]: f["lines"] for f in files}
    assert set(by_path) == {
        "gateway/limits.py",
        "gateway/config.yaml",
        "deploy/Dockerfile",
    }
    assert all(file["summaryAligned"] for file in files), (
        "a file path and its change counts split across summary rows"
    )
    assert all(file["statGenerated"] for file in files), (
        "derived change counts should be said but not read as authored words"
    )
    separators = [separator for file in files for separator in file["separators"]]
    assert separators, "the fixture exercised no Pierre hunk separator"
    assert all(separator["chrome"] for separator in separators), separators

    reading = page.evaluate("""async () => {
      const { says, textNodesUnder, wrote } = await import('/runtime/widget-api.js');
      const diff = document.querySelector('#patch');
      const shadow = diff.shadowRoot;
      const segments = textNodesUnder(document)
        .filter(({node}) => node.getRootNode() === shadow);
      const reference = document.createElement('pre');
      reference.textContent = 'literal evidence';
      document.querySelector('main').append(reference);
      const rendered = shadow.querySelector('pre[data-diff]');
      const statText = shadow.querySelector('.lf-diff-stat').textContent;
      const leafFont = getComputedStyle(reference).fontFamily;
      const leafBackground = getComputedStyle(reference).backgroundColor;
      reference.remove();
      return {
        segmentCount: segments.length,
        saysPath: says(document).includes('gateway/limits.py'),
        wrotePath: wrote(document).includes('gateway/limits.py'),
        saysStat: says(document).includes(statText),
        wroteStat: wrote(document).includes(statText),
        hiddenNumbers: segments
          .filter(({node}) => node.parentElement?.closest('[data-line-number-content]'))
          .map(({node}) => node.data),
        separatorText: segments
          .filter(({node}) => node.parentElement?.closest('[data-separator]'))
          .map(({node}) => node.data),
        coreSheets: shadow.querySelectorAll('style[data-core-css]').length,
        themeSheets: shadow.querySelectorAll('style[data-theme-css]').length,
        font: getComputedStyle(rendered).fontFamily,
        background: getComputedStyle(rendered).backgroundColor,
        leafFont,
        leafBackground,
      };
    }""")
    assert reading["segmentCount"] > 0, "the passage assertion read no diff text"
    assert reading["saysPath"] and reading["wrotePath"], reading
    assert reading["saysStat"] and not reading["wroteStat"], reading
    assert reading["hiddenNumbers"] == [], (
        f"hidden line numbers entered the page reading: {reading}"
    )
    assert reading["separatorText"] == [], (
        f"Pierre separator chrome entered the page reading: {reading}"
    )
    assert (reading["coreSheets"], reading["themeSheets"]) == (1, 1), reading
    assert reading["font"] == reading["leafFont"], reading
    assert reading["background"] == reading["leafBackground"], reading

    py = by_path["gateway/limits.py"]
    assert any(["kw", "if"] in line["roles"] for line in py), py
    assert {r for line in py for r, _ in line["roles"]} >= {"kw", "st", "fn"}

    # The docstring the second hunk rewrites: every line of it is string on both sides.
    doc = [line for line in py if "Called on logout" in line["text"]]
    assert len(doc) == 2, [line["text"] for line in py]
    for line in doc:
        assert {r for r, _ in line["roles"]} == {"st"}, line
        assert "".join(t for _, t in line["roles"]) == line["text"], line

    # The yaml key keeps its key role rather than tokenizing the deleted line as a list
    # item or the added line as an arbitrary string.
    yml = [
        line
        for line in by_path["gateway/config.yaml"]
        if line["kind"] in ("change-addition", "change-deletion")
    ]
    assert len(yml) == 2
    for line in yml:
        assert any(role == "ty" and "burst" in text for role, text in line["roles"]), (
            line
        )
    assert {
        (line["kind"], line["indicator"], line["indicatorSelect"]) for line in yml
    } == {
        ("change-addition", '"+"', "none"),
        ("change-deletion", '"-"', "none"),
    }, "changed lines need visible indicators that selection leaves behind"

    # `\\ No newline at end of file` is diff metadata, not selectable source.
    assert not any("No newline at end of file" in line["text"] for line in py)

    # No extension the table names: plain, the way a lf-code with no `language` is.
    assert all(line["roles"] == [] for line in by_path["deploy/Dockerfile"]), by_path[
        "deploy/Dockerfile"
    ]

    # The visible indicator is generated presentation, so the DOM and a full-line
    # selection still contain exact source. File headers are metadata already represented
    # by the summary, so the widget drops them instead of leaving hidden anchor text.
    assert [line["text"] for line in by_path["gateway/config.yaml"]] == [
        "  burst: 20",
        "  burst: 40",
        "  window: 60",
    ]
    selected = page.evaluate("""() => {
      const lines = document.querySelector('#patch').shadowRoot.querySelectorAll('[data-line]');
      const line = [...lines].find(l => l.dataset.lineType === 'change-addition'
        && l.textContent.includes('burst'));
      const range = document.createRange();
      range.selectNodeContents(line);
      const selection = getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      return selection.toString();
    }""")
    assert selected == "  burst: 40"
    assert errors == []
    page.close()


def test_a_changed_diff_line_marks_the_words_that_moved(browser, serve):
    """Pierre owns changed-line pairing; Leaf preserves its useful visual hierarchy.

    A changed line gets a full semantic background and a brighter inline span where
    Pierre can identify the changed words. The spans must preserve both source text and
    Leaf's syntax roles, and a file with no declared language still gets the same diff
    treatment without gaining invented syntax colour.
    """
    page, errors = open_page(browser, serve(DIFF_PAGE))
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )

    files = page.evaluate("""() => [...document.querySelector('#patch').shadowRoot
      .querySelectorAll('details')].map(d => ({
      path: d.querySelector('.lf-diff-path').textContent,
      lines: [...d.querySelectorAll('[data-line]')].map(line => ({
        kind: line.dataset.lineType,
        text: line.textContent,
        marks: [...line.querySelectorAll('[data-diff-span]')].map(span => span.textContent),
        inked: [...line.querySelectorAll('[data-diff-span] [data-lf-syn]')]
          .map(span => [span.dataset.lfSyn, span.textContent]),
        linePaint: getComputedStyle(line).backgroundColor,
        prePaint: getComputedStyle(line.closest('pre')).backgroundColor,
        markPaint: [...line.querySelectorAll('[data-diff-span]')].map(span => {
          const style = getComputedStyle(span);
          return [style.backgroundColor, style.textDecorationLine];
        }),
      })),
    }))""")
    by_path = {file["path"]: file["lines"] for file in files}
    assert set(by_path) == {
        "gateway/limits.py",
        "gateway/config.yaml",
        "deploy/Dockerfile",
    }

    def changed(path, kind, text):
        return next(
            line
            for line in by_path[path]
            if line["kind"] == kind and text in line["text"]
        )

    before = changed("gateway/config.yaml", "change-deletion", "burst: 20")
    after = changed("gateway/config.yaml", "change-addition", "burst: 40")
    assert before["marks"] and any("20" in mark for mark in before["marks"])
    assert after["marks"] and any("40" in mark for mark in after["marks"])
    assert ["nu", "20"] in before["inked"]
    assert ["nu", "40"] in after["inked"]

    changed_lines = [
        line
        for lines in by_path.values()
        for line in lines
        if line["kind"] in ("change-addition", "change-deletion")
    ]
    assert changed_lines
    assert all(line["linePaint"] != line["prePaint"] for line in changed_lines)
    assert before["linePaint"] != after["linePaint"], (
        "additions and deletions need distinct semantic fills"
    )

    inline_paint = [paint for line in changed_lines for paint in line["markPaint"]]
    assert inline_paint
    assert all(background != "rgba(0, 0, 0, 0)" for background, _ in inline_paint)
    assert {decoration for _, decoration in inline_paint} == {"none"}
    assert all(
        background != line["linePaint"]
        for line in changed_lines
        for background, _ in line["markPaint"]
    ), "inline changes need a stronger fill than their changed line"

    # Pierre's inline comparison is language-independent. Dockerfile is intentionally
    # plain in Leaf's registry, but the edited dependency is still called out.
    docker_before = changed("deploy/Dockerfile", "change-deletion", "requirements.txt")
    docker_after = changed("deploy/Dockerfile", "change-addition", "--no-cache-dir")
    assert docker_before["marks"] or docker_after["marks"]
    assert not any(line["inked"] for line in by_path["deploy/Dockerfile"])

    # The generated indicators never prefix the rendered source on any file.
    assert all(
        not line["text"].startswith(("+", "-"))
        for lines in by_path.values()
        for line in lines
    )

    assert errors == []
    page.close()


def test_a_diff_keeps_source_markup_inert(browser, serve):
    """Pierre returns HTML, but the diff remains data rather than a markup door."""
    page, errors = open_page(browser, serve(DIFF_PAGE))
    result = page.evaluate("""async () => {
      const payload = '<img src=x onerror=globalThis.__lfDiffPwned=1>';
      const host = document.createElement('lf-diff');
      host.id = 'inert-diff';
      const pre = document.createElement('pre');
      pre.textContent = [
        'diff --git a/example.html b/example.html',
        '--- a/example.html',
        '+++ b/example.html',
        '@@ -1 +1 @@',
        '-old',
        '+' + payload,
      ].join('\\n');
      host.append(pre);
      document.querySelector('main').append(host);
      await new Promise((resolve, reject) => {
        const limit = setTimeout(() => reject(new Error('diff did not render')), 2000);
        const ready = () => {
          if (!host.classList.contains('lf-rendered')) return requestAnimationFrame(ready);
          clearTimeout(limit);
          resolve();
        };
        ready();
      });
      const added = [...host.shadowRoot.querySelectorAll('[data-line]')]
        .find(line => line.dataset.lineType === 'change-addition');
      return {
        text: added.textContent,
        images: host.shadowRoot.querySelectorAll('img').length,
        handlers: host.shadowRoot.querySelectorAll('[onerror]').length,
        executed: globalThis.__lfDiffPwned === 1,
      };
    }""")
    assert result == {
        "text": "<img src=x onerror=globalThis.__lfDiffPwned=1>",
        "images": 0,
        "handlers": 0,
        "executed": False,
    }
    assert errors == []
    page.close()


def test_a_diff_rejects_incomplete_hunks(browser, serve):
    """Missing or wrong hunk ranges must fail instead of hiding review evidence."""
    page, errors = open_page(browser, serve(DIFF_PAGE))
    result = page.evaluate("""async () => {
      const settle = async (id, lines) => {
        const host = document.createElement('lf-diff');
        host.id = id;
        const pre = document.createElement('pre');
        pre.textContent = lines.join('\\n');
        host.append(pre);
        document.querySelector('main').append(host);
        await new Promise((resolve, reject) => {
          const limit = setTimeout(() => reject(new Error('diff did not settle')), 2000);
          const ready = () => {
            if (!host.querySelector('.lf-error') && !host.shadowRoot)
              return requestAnimationFrame(ready);
            clearTimeout(limit);
            resolve();
          };
          ready();
        });
        return {
          rendered: host.classList.contains('lf-rendered'),
          error: host.querySelector('.lf-error')?.firstChild?.textContent ?? null,
          source: host.querySelector('.lf-error pre')?.textContent ?? null,
        };
      };
      return Promise.all([
        settle('wrong-count-diff', [
          'diff --git a/example.js b/example.js',
          '--- a/example.js',
          '+++ b/example.js',
          '@@ -1 +1 @@',
          '-old',
          '+new',
          '+silently-lost',
        ]),
        settle('missing-hunk-diff', [
          'diff --git a/example.js b/example.js',
          '--- a/example.js',
          '+++ b/example.js',
          '-old',
          '+new',
        ]),
        settle('mixed-binary-diff', [
          'diff --git a/app.js b/app.js',
          '--- a/app.js',
          '+++ b/app.js',
          '@@ -1 +1 @@',
          '-const value = 1;',
          '+const value = 2;',
          'diff --git a/logo.png b/logo.png',
          'index 1234567..89abcde 100644',
          'Binary files a/logo.png and b/logo.png differ',
        ]),
        settle('empty-added-diff', [
          'diff --git a/empty.txt b/empty.txt',
          'new file mode 100644',
          'index 0000000..e69de29',
        ]),
        settle('empty-deleted-diff', [
          'diff --git a/empty.txt b/empty.txt',
          'deleted file mode 100644',
          'index e69de29..0000000',
        ]),
        settle('copy-diff', [
          'diff --git a/source.js b/copied.js',
          'similarity index 100%',
          'copy from source.js',
          'copy to copied.js',
        ]),
        settle('rename-and-mode-diff', [
          'diff --git a/old.js b/new.js',
          'old mode 100644',
          'new mode 100755',
          'similarity index 100%',
          'rename from old.js',
          'rename to new.js',
        ]),
        settle('rename-with-missing-hunk-diff', [
          'diff --git a/old.js b/new.js',
          'similarity index 100%',
          'rename from old.js',
          'rename to new.js',
          '--- a/old.js',
          '+++ b/new.js',
          '-before',
          '+after',
        ]),
        settle('similarity-only-diff', [
          'diff --git a/old.js b/new.js',
          'similarity index 100%',
        ]),
        settle('empty-rename-paths-diff', [
          'diff --git a/old.js b/new.js',
          'similarity index 100%',
          'rename from ',
          'rename to ',
        ]),
        settle('contradictory-rename-paths-diff', [
          'diff --git a/header-old.js b/header-new.js',
          'similarity index 100%',
          'rename from body-old.js',
          'rename to body-new.js',
        ]),
      ]);
    }""")
    assert result == [
        {
            "rendered": False,
            "error": (
                "<lf-diff> failed: parsePatchContent: hunk has more lines than expected"
            ),
            "source": (
                "diff --git a/example.js b/example.js\n"
                "--- a/example.js\n"
                "+++ b/example.js\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                "+new\n"
                "+silently-lost"
            ),
        },
        {
            "rendered": False,
            "error": (
                "<lf-diff> failed: unsupported hunkless diff for example.js "
                "(only path-only renames may omit @@ hunks; binary, mode-only, "
                "and empty added/deleted entries belong in prose; changed files "
                "need textual @@ hunks)"
            ),
            "source": (
                "diff --git a/example.js b/example.js\n"
                "--- a/example.js\n"
                "+++ b/example.js\n"
                "-old\n"
                "+new"
            ),
        },
        {
            "rendered": False,
            "error": (
                "<lf-diff> failed: unsupported hunkless diff for logo.png "
                "(only path-only renames may omit @@ hunks; binary, mode-only, "
                "and empty added/deleted entries belong in prose; changed files "
                "need textual @@ hunks)"
            ),
            "source": (
                "diff --git a/app.js b/app.js\n"
                "--- a/app.js\n"
                "+++ b/app.js\n"
                "@@ -1 +1 @@\n"
                "-const value = 1;\n"
                "+const value = 2;\n"
                "diff --git a/logo.png b/logo.png\n"
                "index 1234567..89abcde 100644\n"
                "Binary files a/logo.png and b/logo.png differ"
            ),
        },
        {
            "rendered": False,
            "error": (
                "<lf-diff> failed: unsupported hunkless diff for empty.txt "
                "(only path-only renames may omit @@ hunks; binary, mode-only, "
                "and empty added/deleted entries belong in prose; changed files "
                "need textual @@ hunks)"
            ),
            "source": (
                "diff --git a/empty.txt b/empty.txt\n"
                "new file mode 100644\n"
                "index 0000000..e69de29"
            ),
        },
        {
            "rendered": False,
            "error": (
                "<lf-diff> failed: unsupported hunkless diff for empty.txt "
                "(only path-only renames may omit @@ hunks; binary, mode-only, "
                "and empty added/deleted entries belong in prose; changed files "
                "need textual @@ hunks)"
            ),
            "source": (
                "diff --git a/empty.txt b/empty.txt\n"
                "deleted file mode 100644\n"
                "index e69de29..0000000"
            ),
        },
        {
            "rendered": False,
            "error": (
                "<lf-diff> failed: unsupported copy diff (copy entries belong in prose; "
                "omit copy metadata and use textual @@ hunks for an edited destination)"
            ),
            "source": (
                "diff --git a/source.js b/copied.js\n"
                "similarity index 100%\n"
                "copy from source.js\n"
                "copy to copied.js"
            ),
        },
        {
            "rendered": False,
            "error": (
                "<lf-diff> failed: unsupported hunkless rename (only an exact "
                "path-only block with diff --git, similarity index 100%, rename "
                "from, and rename to lines may omit textual @@ hunks)"
            ),
            "source": (
                "diff --git a/old.js b/new.js\n"
                "old mode 100644\n"
                "new mode 100755\n"
                "similarity index 100%\n"
                "rename from old.js\n"
                "rename to new.js"
            ),
        },
        {
            "rendered": False,
            "error": (
                "<lf-diff> failed: unsupported hunkless rename (only an exact "
                "path-only block with diff --git, similarity index 100%, rename "
                "from, and rename to lines may omit textual @@ hunks)"
            ),
            "source": (
                "diff --git a/old.js b/new.js\n"
                "similarity index 100%\n"
                "rename from old.js\n"
                "rename to new.js\n"
                "--- a/old.js\n"
                "+++ b/new.js\n"
                "-before\n"
                "+after"
            ),
        },
        {
            "rendered": False,
            "error": (
                "<lf-diff> failed: unsupported hunkless rename (only an exact "
                "path-only block with diff --git, similarity index 100%, rename "
                "from, and rename to lines may omit textual @@ hunks)"
            ),
            "source": ("diff --git a/old.js b/new.js\nsimilarity index 100%"),
        },
        {
            "rendered": False,
            "error": (
                "<lf-diff> failed: unsupported hunkless rename (only an exact "
                "path-only block with diff --git, similarity index 100%, rename "
                "from, and rename to lines may omit textual @@ hunks)"
            ),
            "source": (
                "diff --git a/old.js b/new.js\n"
                "similarity index 100%\n"
                "rename from \n"
                "rename to "
            ),
        },
        {
            "rendered": False,
            "error": (
                "<lf-diff> failed: unsupported hunkless rename (only an exact "
                "path-only block with diff --git, similarity index 100%, rename "
                "from, and rename to lines may omit textual @@ hunks)"
            ),
            "source": (
                "diff --git a/header-old.js b/header-new.js\n"
                "similarity index 100%\n"
                "rename from body-old.js\n"
                "rename to body-new.js"
            ),
        },
    ]
    assert errors == []
    page.close()


def test_a_diff_shows_a_path_only_rename_without_an_empty_disclosure(browser, serve):
    """A path-only rename remains evidence without an invented textual hunk."""
    page, errors = open_page(browser, serve(DIFF_PAGE))
    result = page.evaluate("""async () => {
      const host = document.createElement('lf-diff');
      host.id = 'mixed-rename-diff';
      const pre = document.createElement('pre');
      pre.textContent = [
        'diff --git a/app.js b/app.js',
        '--- a/app.js',
        '+++ b/app.js',
        '@@ -1 +1 @@',
        '-const value = 1;',
        '+const value = 2;',
        'diff --git a/old-name.js b/new-name.js',
        'similarity index 100%',
        'rename from old-name.js',
        'rename to new-name.js',
        'diff --git "a/old\\\\tname.js" "b/new\\\\tname.js"',
        'similarity index 100%',
        'rename from "old\\\\tname.js"',
        'rename to "new\\\\tname.js"',
      ].join('\\n');
      host.append(pre);
      document.querySelector('main').append(host);
      await new Promise((resolve, reject) => {
        const limit = setTimeout(() => reject(new Error('diff did not settle')), 2000);
        const ready = () => {
          if (!host.querySelector('.lf-error') && !host.shadowRoot)
            return requestAnimationFrame(ready);
          clearTimeout(limit);
          resolve();
        };
        ready();
      });
      const shadow = host.shadowRoot;
      const renames = [...(shadow?.querySelectorAll('.lf-diff-rename') ?? [])];
      const rename = renames[0];
      const quotedRename = renames[1];
      const { says, wrote } = await import('/runtime/widget-api.js');
      return {
        rendered: host.classList.contains('lf-rendered'),
        error: host.querySelector('.lf-error')?.firstChild?.textContent ?? null,
        details: shadow?.querySelectorAll('details').length ?? 0,
        diffs: shadow?.querySelectorAll('pre[data-diff]').length ?? 0,
        renameCount: renames.length,
        from: rename?.querySelector('.lf-diff-before')?.textContent ?? null,
        to: rename?.querySelector('.lf-diff-after')?.textContent ?? null,
        stat: rename?.querySelector('.lf-diff-stat')?.textContent ?? null,
        generated: rename?.dataset.lfGen === '1',
        saidOverride: rename?.hasAttribute('data-lf-said') ?? null,
        quotedFrom:
          quotedRename?.querySelector('.lf-diff-before')?.textContent ?? null,
        quotedTo: quotedRename?.querySelector('.lf-diff-after')?.textContent ?? null,
        lines: [...(shadow?.querySelectorAll('[data-line]') ?? [])]
          .map(line => line.textContent),
        saysRename: says(document).includes('old-name.js → new-name.js'),
        wroteRename: wrote(document).includes('old-name.js → new-name.js'),
      };
    }""")
    assert result == {
        "rendered": True,
        "error": None,
        "details": 1,
        "diffs": 1,
        "renameCount": 2,
        "from": "old-name.js",
        "to": "new-name.js",
        "stat": "renamed",
        "generated": True,
        "saidOverride": False,
        "quotedFrom": '"old\\tname.js"',
        "quotedTo": '"new\\tname.js"',
        "lines": ["const value = 1;", "const value = 2;"],
        "saysRename": True,
        "wroteRename": False,
    }
    assert errors == []
    page.close()


def test_a_diff_preserves_a_final_empty_context_line(browser, serve):
    """The documented entity for an empty context line survives wrapper cleanup."""
    page, errors = open_page(browser, serve(DIFF_PAGE))
    result = page.evaluate("""async () => {
      const host = document.createElement('lf-diff');
      host.id = 'final-empty-context-diff';
      const pre = document.createElement('pre');
      pre.innerHTML = [
        'diff --git a/example.txt b/example.txt',
        '--- a/example.txt',
        '+++ b/example.txt',
        '@@ -1,2 +1,2 @@',
        ' visible',
        '&#32;',
        '',
      ].join('\\n');
      const authored = pre.textContent;
      host.append(pre);
      document.querySelector('main').append(host);
      await new Promise((resolve, reject) => {
        const limit = setTimeout(() => reject(new Error('diff did not settle')), 2000);
        const ready = () => {
          if (!host.querySelector('.lf-error') && !host.shadowRoot)
            return requestAnimationFrame(ready);
          clearTimeout(limit);
          resolve();
        };
        ready();
      });
      return {
        authoredTail: authored.slice(-3),
        rendered: host.classList.contains('lf-rendered'),
        error: host.querySelector('.lf-error')?.firstChild?.textContent ?? null,
        lines: [...(host.shadowRoot?.querySelectorAll('[data-line]') ?? [])]
          .map(line => line.textContent),
      };
    }""")
    assert result == {
        "authoredTail": "\n \n",
        "rendered": True,
        "error": None,
        "lines": ["visible", ""],
    }
    assert errors == []
    page.close()


def test_a_widgets_native_control_names_the_press_the_platform_makes(browser, serve):
    """A key on screen is a key that works, and its inversion costs just as much: the
    press is real, the reader can make it, and no surface says so.

    The runtime's control scope matches a tab stop of its own making, which is what
    `offer` writes on the spans it builds. A control the widget takes from the platform
    brings its own, so it matched nothing — and the widget's own declaration is what
    names both the key and the word, the key being the platform's fact about that
    control and the word being what the press does here.

    The two differ in what they answer, and saying so is the point: a <summary> is
    button-like and takes both keys, while a checkbox takes Space alone, Enter being
    the form's key and a leaf page having no form. Neither row binds a `run`: the
    checkbox's press is the platform's, and the summary's is the disclosure scope's,
    which has to reach a staged control the same way this declaration does. A row
    consuming a press it does not make would be the same lie from the other side.

    The staged control is the one the register could not reach at all.
    `document.activeElement` retargets to the host, so the scope walk started at the
    widget and never saw the control the reader was standing on."""
    url = serve(
        NATIVE_CONTROL_PAGE,
        media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
    )
    page, errors = open_page(browser, url)
    line = page.locator(".lf-keyline")

    box = page.locator("lf-shot input[type=checkbox]")
    box.scroll_into_view_if_needed()
    box.focus()
    expect(line).to_contain_text("show after")
    page.keyboard.press(" ")
    expect(box).to_be_checked()
    # The word is read where it is painted, so it names the frame this press brings up
    # rather than covering both with one that is never wrong and never says anything.
    expect(line).to_contain_text("show before")
    # Enter is not on the row and not the control's: it must leave the box alone.
    page.keyboard.press("Enter")
    expect(box).to_be_checked()

    summary = page.locator("lf-diff summary").first
    details = page.locator("lf-diff details").first
    summary.scroll_into_view_if_needed()
    summary.focus()
    assert details.evaluate("el => el.open"), "the fixture's disclosure starts open"
    expect(line).to_contain_text("hide this file")
    page.keyboard.press("Enter")
    expect(line).to_contain_text("show this file")
    assert not details.evaluate("el => el.open")

    # The row also names an arrow, which no browser answers, so unlike the pair above it is
    # only ever as good as the scope that runs it — and that scope has to find a staged
    # disclosure the same way this declaration had to reach a staged control. Read off the
    # document alone it finds none here, the page's only <details> being the ones the
    # widget put in a shadow root. The press is what says so, not the chip: this widget's
    # own row is the nearer of the two naming these keys, so it prints them either way.
    expect(line).to_contain_text("⏎ / space / →")
    page.keyboard.press("ArrowRight")
    assert details.evaluate("el => el.open")
    # And the word turns over inside the press, read once so a poll cannot answer for it.
    # A toggle from a staged root is not composed, so no document listener hears it: this
    # is the watch `shadowStage` hands each root, and without it the line sat on "show
    # this file" until the next poll two seconds later.
    said = key_line(page)
    assert "⏎ / space / ←" in said, said
    assert "hide this file" in said, said

    # Neither control is handed a letter by any platform, so the page's own keyboard
    # stands behind both of them.
    expect(line).to_contain_text("comment")
    assert errors == []
    page.close()


def test_two_comments_on_one_element_both_stay_anchored(browser, serve):
    """A figure can carry more than one thread. When the page's record of what it drew was
    keyed by the mark, the second comment overwrote the first, and the panel told the
    reader the first one's passage wasn't in this version — while it sat outlined on
    screen for the second."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)
    for text in ("first on the figure", "second on the figure"):
        post_event(
            page,
            url.rsplit("/versions/", 1)[0] + "/api/event",
            data={
                "kind": "comment",
                "revision": 1,
                "text": text,
                "anchor": {"section": "fig"},
            },
        )
    page.locator(".lf-comments").click()
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 2")
    stranded = page.locator(".lf-panel .lf-quote.detached").all_text_contents()
    assert stranded == [], f"outlined on screen, reported missing: {stranded}"
    assert errors == []
    page.close()


def test_a_press_on_a_mark_opens_the_thread_the_hover_promised(browser, serve):
    """The card the pointer lights and the card a press opens are one reading of one point.

    They came from two doors, though. The hover hit-tests the pointer record the runtime
    keeps, and the click read its own clientX and clientY — a `click` is a legacy mouse
    event, so those arrive rounded to a whole pixel, while markAt measures against
    getClientRects, whose edges are floats. Within a pixel of a mark's edge the two
    answer different threads: a quote lights up under the hand and the press on it opens
    the neighbour's conversation, which is the same disagreement the aim carried and this
    is the surface it was left on.

    The seam fixture puts the pointer where the true point and its rounded twin are over
    different items, and a comment on each makes the disagreement a pair of cards rather
    than a hit and a miss — so what is asserted is which thread opened, not whether one
    did. Which item the true point is over follows where in the pixel the seam fell, so
    the expected card is read off the point rather than named here."""
    url = serve(AIM_SEAM_PAGE)
    for ident in ("seam-upper", "seam-lower"):
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"About {ident}.",
                "anchor": {"section": ident},
            },
        )
    page, errors = open_page(browser, url)
    expect(page.locator(".lf-thread")).to_have_count(2)
    seam = page.evaluate(AIM_SEAM, ["seam-upper", "seam-lower"])
    assert seam and {seam["at"], seam["rounded"]} == {"seam-upper", "seam-lower"}, (
        "the fixture no longer straddles a seam — the point and the whole pixel it rounds "
        "to are not on the two marked items either side of it, so a press that read either "
        f"of them would pass this: {seam}"
    )

    page.mouse.move(seam["x"], seam["y"])
    promised = page.locator(".lf-thread.lf-mark-hover")
    expect(promised).to_have_count(1)
    expect(promised).to_contain_text(f"About {seam['at']}.")

    page.mouse.click(seam["x"], seam["y"])
    opened = page.evaluate(
        "() => document.activeElement?.closest('.lf-thread')?.innerText ?? null"
    )
    assert opened and f"About {seam['at']}." in opened, (
        f"the hover promised the thread on {seam['at']}, and the press at the same point "
        f"opened: {opened}"
    )
    assert errors == []
    page.close()


def test_a_tap_on_a_quote_opens_its_thread(browser, serve):
    """A finger is a pointer that arrives already down, and the click it ends on has to
    answer for a position it never moved through.

    A tap dispatches no `pointermove` at all — `pointerdown`, then the compatibility
    mouse events and a `click` carrying `detail=1`. So the record a mouse keeps as it
    travels is still its start value under a finger, and a click reading it asks
    elementFromPoint at a point off the page: the quote under the finger opens nothing,
    which is a wider silence than the pixel the mouse door was about. The record is taken
    from `pointerdown` as well for that reason, and a tap's `pointerdown` carries the true
    fractional point, so the finger gets the same reading the mouse does rather than the
    rounded one its own click would have given.

    The context has a touchscreen because that is the only way to get a gesture with no
    pointermove in it: driving the same point with `page.mouse` records the position on
    the way in and passes whatever the click reads. The seam fixture is reused so the
    tap's own rounded twin is a different item, and a comment on each makes a wrong
    reading a visible thread rather than a miss."""
    url = serve(AIM_SEAM_PAGE)
    for ident in ("seam-upper", "seam-lower"):
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": f"About {ident}.",
                "anchor": {"section": ident},
            },
        )
    context = browser.new_context(
        viewport={"width": 1200, "height": 900}, color_scheme="light", has_touch=True
    )
    page, errors = open_page(browser, url, context=context)
    expect(page.locator(".lf-thread")).to_have_count(2)
    seam = page.evaluate(AIM_SEAM, ["seam-upper", "seam-lower"])
    assert seam and {seam["at"], seam["rounded"]} == {"seam-upper", "seam-lower"}, (
        "the fixture no longer straddles a seam — the point and the whole pixel it rounds "
        "to are not on the two marked items either side of it, so a tap that read either "
        f"of them would pass this: {seam}"
    )

    page.touchscreen.tap(seam["x"], seam["y"])
    opened = page.evaluate(
        "() => document.activeElement?.closest('.lf-thread')?.innerText ?? null"
    )
    assert opened and f"About {seam['at']}." in opened, (
        f"a tap on the quote for {seam['at']} opened: {opened}"
    )
    assert errors == []
    page.close()
    context.close()


def test_the_pointer_stops_claiming_a_mark_it_scrolled_past(browser, serve):
    """The hover is a function of where the pointer is and where the text is, and scrolling
    moves the second without touching the first. A wrapped <mark> got this from :hover; a
    painted range has to be asked again, so everything that moves the page asks."""
    url = serve(LONG_PAGE)
    page, errors = open_page(browser, url)
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "up top",
            "anchor": {"section": "p0", "quote": "Paragraph 0."},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    spot = page.evaluate("""() => { const r = [...CSS.highlights.get('lf-mark')][0].getClientRects()[0];
                                    return {x: r.left + r.width / 2, y: r.top + r.height / 2}; }""")
    page.mouse.move(spot["x"], spot["y"])
    page.wait_for_function("() => document.body.classList.contains('lf-over-mark')")
    page.evaluate("() => document.body.scrollBy({top: 900, behavior: 'instant'})")
    page.wait_for_function(
        "() => !document.body.classList.contains('lf-over-mark')"
        " && (CSS.highlights.get('lf-mark-hover')?.size ?? 0) === 0"
    )
    assert errors == []
    page.close()


def test_a_repeated_passage_anchors_where_it_was_picked(browser, serve):
    """A quote names text, not a place. Where one section says the same thing twice, the
    words on either side are what tell the copies apart — so an anchor carries them, and
    the occurrence whose neighbours match wins. Driven through the real button, because
    the context is captured from the live selection and nowhere else."""
    page, errors = open_page(browser, serve(TWICE_PAGE))
    landed = page.evaluate("""async () => {
        const paras = [...document.querySelectorAll('#repeat p')];
        const p = paras.at(-1);
        const phrase = 'The version stamp never lands.';
        const at = p.firstChild.data.indexOf(phrase);
        if (at === -1) return 'phrase missing';
        const want = document.createRange();
        want.setStart(p.firstChild, at); want.setEnd(p.firstChild, at + phrase.length);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        await new Promise(r => setTimeout(r, 40));
        const fab = document.querySelector('.lf-fab');
        if (fab.style.display !== 'block') return 'no button';
        fab.click();
        await new Promise(r => setTimeout(r, 40));
        const painted = [...(CSS.highlights.get('lf-pending') ?? [])][0];
        if (!painted) return 'no mark';
        return painted.compareBoundaryPoints(Range.START_TO_START, want) === 0;
    }""")
    assert landed is True, (
        f"the second copy was picked, the mark went elsewhere ({landed})"
    )
    assert errors == []
    page.close()


def test_an_ambiguous_revised_passage_detaches_instead_of_guessing(browser, serve):
    """Context tells two copies apart; it must not relocate a comment when the page moves
    on. If a later version rewrites the words beside the anchored copy, that copy confirms
    almost nothing while another copy remains. Neither is now identifiable: document
    order is not evidence, so the comment detaches visibly instead of moving to words it
    was never made on."""
    url = serve(DRIFT_V1)
    page, errors = open_page(browser, live_url(url))
    landed = page.evaluate("""async () => {
        const p = document.querySelectorAll('#drift p')[0];
        const phrase = 'The version stamp never lands';
        const at = p.firstChild.data.indexOf(phrase);
        const want = document.createRange();
        want.setStart(p.firstChild, at); want.setEnd(p.firstChild, at + phrase.length);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        await new Promise(r => setTimeout(r, 40));
        const fab = document.querySelector('.lf-fab');
        if (fab.style.display !== 'block') return 'no button';
        fab.click();
        await new Promise(r => setTimeout(r, 40));
        document.querySelector('.lf-composer textarea').value = 'is this idempotent?';
        document.querySelector('.lf-composer textarea')
            .dispatchEvent(new Event('input', {bubbles: true}));
        document.querySelector('.lf-composer button.primary').click();
        return true;
    }""")
    assert landed is True, f"couldn't post the comment ({landed})"
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    d = serve.page_dir
    (d / "versions" / "v2.html").write_text(DRIFT_V2)
    stamp_version_file(d, 2, "revised")
    wait_for_revision(page, 2)
    expect(page.locator(".lf-thread .lf-quote.detached")).to_have_count(1)
    assert page.evaluate("() => CSS.highlights.get('lf-mark')?.size ?? 0") == 0
    expect(page.locator(".lf-thread .lf-quote")).to_have_attribute(
        "title", re.compile("can't be identified")
    )
    assert errors == []
    page.close()


def test_a_passage_among_padded_emoji_confirms_its_neighbours(browser, serve):
    """A stored context is counted in code points; the comparison counts code units; and an
    astral character is two of the second for one of the first. Ask the page for the first
    number and the window comes up short of what was written down — and short is fatal,
    because a passage confirms its neighbours in full or not at all. The anchor would fall
    back to naming the first copy on that page for good, silently. No shipped example holds
    an astral character, so only a fixture can hold this."""
    page, errors = open_page(browser, serve(ASTRAL_PAGE))
    landed = page.evaluate("""async () => {
        const skip = '.lf-ui, script, style';
        const w = document.createTreeWalker(document.getElementById('astral'),
            NodeFilter.SHOW_TEXT,
            {acceptNode: n => n.parentElement?.closest(skip)
                ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT});
        const phrase = 'TARGET PHRASE';
        const hits = [];
        for (let n = w.nextNode(); n; n = w.nextNode()) {
            let i = n.data.indexOf(phrase);
            while (i !== -1) { hits.push({node: n, at: i}); i = n.data.indexOf(phrase, i + 1); }
        }
        if (hits.length !== 2) return `fixture holds ${hits.length} copies, wanted 2`;
        const h = hits[1];   // the copy among the emoji
        const want = document.createRange();
        want.setStart(h.node, h.at); want.setEnd(h.node, h.at + phrase.length);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        await new Promise(r => setTimeout(r, 60));
        const fab = document.querySelector('.lf-fab');
        if (fab.style.display !== 'block') return 'no button';
        fab.click();
        await new Promise(r => setTimeout(r, 60));
        const painted = [...(CSS.highlights.get('lf-pending') ?? [])][0];
        if (!painted) return 'no mark';
        return painted.compareBoundaryPoints(Range.START_TO_START, want) === 0;
    }""")
    assert landed is True, (
        f"the emoji copy was picked, the mark went elsewhere ({landed})"
    )
    assert errors == []
    page.close()


@pytest.mark.parametrize(
    "html", [EDGE_PAGE, TAIL_PAGE], ids=["closes-its-section", "ends-the-document"]
)
def test_a_repeated_passage_at_an_edge_anchors_where_it_was_picked(
    browser, serve, html
):
    """A passage closing its section used to store a suffix clipped at the section's
    edge — one character, a bar the identical copy above it also cleared, so the mark
    painted there while the user was still composing. The neighbours now come from
    the whole document and the section only filters where the search may land, so the
    closing copy is told apart by the words of the section after it.

    Where the document itself ends there is no second side to store, and an empty one is
    not an absent constraint: it says nothing followed the passage anywhere, which is true
    of exactly one occurrence. Refusing to read it that way left the same wrong mark."""
    page, errors = open_page(browser, serve(html))
    landed = page.evaluate("""async () => {
        const p = document.querySelectorAll('#edge p')[1];
        // Through the full stop, so that with the section below removed the passage is the
        // last thing the document says and its stored suffix comes out empty.
        const phrase = 'the run is retried until it lands.';
        const at = p.firstChild.data.indexOf(phrase);
        if (at === -1) return 'phrase missing';
        const want = document.createRange();
        want.setStart(p.firstChild, at); want.setEnd(p.firstChild, at + phrase.length);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        await new Promise(r => setTimeout(r, 60));
        const fab = document.querySelector('.lf-fab');
        if (fab.style.display !== 'block') return 'no button';
        fab.click();
        await new Promise(r => setTimeout(r, 60));
        const painted = [...(CSS.highlights.get('lf-pending') ?? [])][0];
        if (!painted) return 'no mark';
        if (painted.compareBoundaryPoints(Range.START_TO_START, want) === 0) return true;
        return painted.startContainer.parentElement.textContent.slice(0, 40);
    }""")
    assert landed is True, (
        f"the closing copy was picked, the mark went elsewhere ({landed})"
    )
    assert errors == []
    page.close()


def test_an_anchor_stored_under_the_section_clipped_capture_still_resolves(
    browser, serve
):
    """The bar is however much was stored. An anchor from an older log carries context
    clipped at its section's edge; it confirms at that shorter bar exactly as it did when
    it was written, so nothing already in a log detaches when the capture reaches
    further."""
    url = serve(EDGE_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "revision": 1,
            "text": "old bar",
            "anchor": {
                "section": "edge",
                "quote": "the run is retried until it lands",
                "prefix": "ails again in the night,",
                "suffix": ". Nothing else moves.",
            },
        },
    )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    where = page.evaluate("""() => {
        const r = [...CSS.highlights.get('lf-mark')][0];
        return r.startContainer.parentElement.textContent.slice(0, 11);
    }""")
    assert where == "First pass:", (
        f"an old anchor's thin bar changed where it lands: {where!r}"
    )
    assert errors == []
    page.close()


def test_an_ambiguous_one_sided_anchor_from_an_older_capture_detaches(browser, serve):
    """A capture that stopped at the section root wrote no prefix at all for a passage
    opening its section. Read the way the search now reads an empty side — nothing preceded
    this passage anywhere on the page — that claim is false wherever the section wasn't
    first, so no occurrence confirms it. With two quote candidates left, the passage is
    ambiguous and detaches rather than using document order."""
    url = serve(EDGE_PAGE)
    # A suffix that fits the second copy and nothing else, stored with no prefix beside it.
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "claude",
            "revision": 1,
            "text": "older anchor",
            "anchor": {
                "section": "edge",
                "quote": "the run is retried until it lands",
                "suffix": ". Rollout resumes",
            },
        },
    )
    page, errors = open_page(browser, url)
    expect(page.locator(".lf-thread .lf-quote.detached")).to_have_count(1)
    assert page.evaluate("() => CSS.highlights.get('lf-mark')?.size ?? 0") == 0
    assert errors == []
    page.close()


def test_a_passage_longer_than_the_pattern_is_anchored_whole(browser, serve):
    """A quote is the passage, so what is stored is what the page marks and what the
    comment is on. It used to be cut at four hundred characters: a reader who selected
    a paragraph got a comment on its opening and a highlight that shrank to match, on
    most of the paragraphs a leaf page holds, and nothing said so. Storing the
    whole of it is only affordable because the bound moved to the search's pattern,
    which is what could not take a long passage — so this drags one past that bound and
    asks the mark, the log and the panel the same question, on the second of two
    identical copies, which is also the case where the lead alone cannot answer it."""
    url = serve(TWO_COPIES_PAGE)
    page, errors = open_page(browser, url)
    passage = page.locator("#second")
    picked = page.evaluate("() => document.querySelector('#second').textContent.length")
    assert picked > 400, "the fixture no longer outruns the pattern's own lead"

    # The whole paragraph, dragged: from its first glyph to its last.
    box = passage.bounding_box()
    select(
        page,
        (box["x"] + 1, box["y"] + 4),
        (box["x"] + box["width"] - 1, box["y"] + box["height"] - 4),
        steps=12,
    )
    expect(page.locator(".lf-fab")).to_be_visible()
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()

    # The mark under the open composer is the selection, both ends of it — and on the
    # copy the reader dragged, which only the stored neighbours can decide.
    on_the_selection = page.evaluate("""() => {
        const words = document.querySelector('#second').firstChild;
        const want = document.createRange();
        want.setStart(words, 0);
        want.setEnd(words, words.data.length);
        const painted = [...(CSS.highlights.get('lf-pending') ?? [])];
        if (!painted.length) return 'no mark';
        return [
          painted[0].compareBoundaryPoints(Range.START_TO_START, want) === 0,
          painted.at(-1).compareBoundaryPoints(Range.END_TO_END, want) === 0,
          painted.map((r) => r.toString()).join('').length,
        ];
    }""")
    assert on_the_selection == [True, True, picked], (
        f"the mark is not the passage that was dragged ({on_the_selection}, "
        f"wanted [True, True, {picked}])"
    )

    # And the anchor that posts says the same thing, since the mark is drawn from it.
    page.locator(".lf-composer textarea").fill("The whole of it.")
    page.locator(".lf-composer button.primary").click()
    round_trip(page)
    expect(page.locator(".lf-thread")).to_have_count(1)
    expect(page.locator(".lf-thread .lf-quote")).not_to_have_class(
        re.compile("detached")
    )
    anchor = [
        e["anchor"] for e in events_model.read_events(serve.page_dir) if e.get("anchor")
    ][-1]
    assert len(anchor["quote"]) == picked, (
        f"the log holds {len(anchor['quote'])} characters of a {picked}-character "
        "passage"
    )
    assert anchor["prefix"].endswith("this other line."), (
        f"the neighbour naming which copy was picked is {anchor['prefix']!r}"
    )
    assert errors == []
    page.close()


def test_a_selection_of_the_whole_page_still_finds_its_passage(browser, serve):
    """Select-all and comment. The quote is then the page, which is past what a search
    built from the whole of one can compile at all — and a throw there is not a missing
    mark but every mark, since one pass draws them. The bound is the pattern's, so the
    lead finds the candidates and the rest of the quote is walked from each; what this
    asks is that the passage is still found, on the pass that runs after the send as
    much as on the one under the composer."""
    url = serve(CEILING_PAGE)
    page, errors = open_page(browser, url)
    prose = page.evaluate("() => document.querySelector('main').textContent.length")
    assert prose > 12000, f"the fixture holds {prose} characters, under the ceiling"

    page.keyboard.press("ControlOrMeta+a")
    expect(page.locator(".lf-fab")).to_be_visible()
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    painted = page.evaluate(
        "() => [...(CSS.highlights.get('lf-pending') ?? [])]"
        ".map((r) => r.toString()).join('').length"
    )
    assert painted > 12000, f"the mark under the composer covers {painted} characters"

    page.locator(".lf-composer textarea").fill("All of it.")
    page.locator(".lf-composer button.primary").click()
    round_trip(page)
    expect(page.locator(".lf-thread")).to_have_count(1)
    # The posted anchor resolves on the ordinary pass too, which is the one that would
    # have thrown: a detached quote here is the search having failed to find the page
    # inside the page.
    expect(page.locator(".lf-thread .lf-quote")).not_to_have_class(
        re.compile("detached")
    )
    assert errors == []
    page.close()


def test_one_neighbour_is_not_enough_to_identify_a_revised_comment(browser, serve):
    """Context may place a comment only where both of a passage's neighbours are still
    there. A passage at the edge of its section has just one, and one is a bar another copy
    clears — so a revision that rewrites the commented copy's only neighbour would hand the
    comment to a copy it was never made on, silently, a version after anyone was looking.
    The cost of refusing is visible instead: the thread detaches until a later version
    makes its passage unique again."""
    url = serve(THIN_V1)
    page, errors = open_page(browser, live_url(url))
    posted = page.evaluate("""async () => {
        const p = document.querySelectorAll('#thin p')[0];
        const phrase = 'The version stamp never lands';
        const at = p.firstChild.data.indexOf(phrase);
        const want = document.createRange();
        want.setStart(p.firstChild, at); want.setEnd(p.firstChild, at + phrase.length);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        await new Promise(r => setTimeout(r, 40));
        const fab = document.querySelector('.lf-fab');
        if (fab.style.display !== 'block') return 'no button';
        fab.click();
        await new Promise(r => setTimeout(r, 40));
        const box = document.querySelector('.lf-composer textarea');
        box.value = 'does this hold?';
        box.dispatchEvent(new Event('input', {bubbles: true}));
        document.querySelector('.lf-composer button.primary').click();
        return true;
    }""")
    assert posted is True, f"couldn't post the comment ({posted})"
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")

    d = serve.page_dir
    (d / "versions" / "v2.html").write_text(THIN_V2)
    stamp_version_file(d, 2, "revised")
    wait_for_revision(page, 2)
    expect(page.locator(".lf-thread .lf-quote.detached")).to_have_count(1)
    assert page.evaluate("() => CSS.highlights.get('lf-mark')?.size ?? 0") == 0
    assert errors == []
    page.close()


def test_the_picker_runs_in_number_order_past_v9(browser, serve):
    """A version stays an integer from the server through runtime state; only the
    picker and URL boundary render its file name. Order the versions by those names
    instead and v10 lands between v1 and v2: the picker reads out of sequence,
    the diff offers the wrong base, and a reader on the newest version is told a
    newer one is waiting."""
    url = serve(INLINE_PAGE)
    for n in range(2, 11):
        _publish(serve.page_dir, n, INLINE_PAGE, f"cut {n}")
    page, errors = open_page(browser, url.replace("v1.html", "v10.html"))

    # The menu is built whether or not it is open, so the order is readable without
    # a press — and the press is not what this test is about.
    rows = page.locator(".lf-version-menu .lf-version-row .lf-version-num")
    expect(rows).to_have_count(10)
    assert [t.split(" ")[0] for t in rows.all_text_contents()] == [
        f"v{n}" for n in range(1, 11)
    ]
    expect(rows.last).to_have_text("v10 (latest version)")
    # The bases a diff can run against are every version older than this one, so the
    # last press in the menu is v9 — which is what "the version before this" comes to
    # once the ordering has decided it.
    presses = page.locator(".lf-version-diff")
    expect(presses).to_have_count(9)
    expect(presses.last).to_have_attribute("data-lf-version", "9")
    compare_with(page)
    expect(page.locator(".lf-version")).to_have_attribute(
        "title", re.compile(r"changed since v9 ")
    )
    # Nothing is newer than v10, so no chip offers one.
    expect(page.locator(".lf-latest-chip")).to_be_hidden()
    assert errors == []
    page.close()

    # Pinned to the oldest, the chip naming the newest is the runtime's one place
    # that spells a version out in a sentence.
    page, errors = open_page(browser, url, pin=True)
    expect(page.locator(".lf-latest-chip")).to_have_text(
        "New page available → open v10"
    )
    assert errors == []
    page.close()


def test_the_menu_a_first_version_opens_is_a_menu_it_can_close(browser, serve):
    """A layer owes a way out over exactly the pages its way in is live on, and the
    menu's two were live over different ones. `v` opened it wherever there was a version
    at all; the mode binding its Escape stood only above one. So on the commonest page
    there is — a page with one version — `v` raised a menu no key could put down: the
    Escape chip read "back to the page", focus fell to body, and the menu stayed painted
    over the bar.

    Not fixed by taking the menu away, which is what the walk being empty invites. A
    first version's menu holds that version and the note saying what it changed, and that
    is the whole reason the chooser is a menu rather than a select — see
    test_a_key_on_screen_is_a_key_that_works, which asks for it by name. Two facts, so
    two predicates: `versionsOffered` for the layer and `versionsToWalk` for the rows.

    Asserted from both doors, the pointer's being the one that would have kept the trap,
    and the walk asserted absent so the fix cannot be "make everything live"."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, live_url(url))
    menu = page.locator(".lf-version-menu")
    line = page.locator(".lf-keyline")

    # One version: the menu opens, holds its one row, and Escape ends it.
    expect(line).to_contain_text("versions")
    page.keyboard.press("v")
    expect(menu).to_be_visible()
    expect(page.locator(".lf-version-row")).to_have_count(1)
    page.keyboard.press("Escape")
    expect(menu).not_to_be_visible()
    expect(page.locator(".lf-version")).to_be_focused()

    # The pointer's door reaches the same layer, and the same key ends it.
    page.locator(".lf-version").click()
    expect(menu).to_be_visible()
    page.keyboard.press("Escape")
    expect(menu).not_to_be_visible()

    # The way out is named while the reader is in it, and the walk — which has nowhere
    # to step — is not offered beside it.
    page.keyboard.press("v")
    expect(line).to_contain_text("close versions")
    expect(line).not_to_contain_text("walk — marking changes")
    page.keyboard.press("Escape")

    # The control: a second version, where the walk is live and the layer is unchanged.
    # The live root follows the new revision itself on its next poll — waited for rather
    # than forced with a reload, which raced that activation and lost the press to it
    # about one run in five.
    _publish(serve.page_dir, 2, INLINE_PAGE, "second")
    wait_for_revision(page, 2)
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-version-row').length > 1"
    )
    page.keyboard.press("v")
    expect(menu).to_be_visible()
    expect(line).to_contain_text("walk — marking changes")
    page.keyboard.press("Escape")
    expect(menu).not_to_be_visible()
    assert errors == []
    page.close()


def test_the_version_menu_is_worked_by_pointer_and_key(browser, serve):
    """The chooser is a press and a menu rather than a select, which buys the notes
    somewhere they can be read whole and costs the platform's own popup: opening,
    closing, and the keys between. A select came with all of that, so what this
    asserts is the part that had to be written back — the press toggles rather than
    only opens, focus lands on the version being read so the walk starts where the
    reader is, ↑/↓ clamp at the ends, Escape hands focus back to the press it came
    from, and a click anywhere else closes without navigating.

    The note is the reason the menu exists at all: a select's closed label is its
    selected option's whole text, so the note had to be on the bar or nowhere, and on
    the bar it ellipsized. Here it wraps."""
    long_note = (
        "a note far too long to have ever fitted on the bar, which is the whole "
        "reason the notes moved off it and into a list that can give them a line each"
    )
    url = serve(INLINE_PAGE)
    _publish(serve.page_dir, 2, INLINE_PAGE, long_note)
    _publish(serve.page_dir, 3, INLINE_PAGE, "third")
    # Pinned to v2, so there is a version either side of the one being read.
    page, errors = open_page(browser, url.replace("v1.html", "v2.html"), pin=True)

    btn = page.locator(".lf-version")
    menu = page.locator(".lf-version-menu")
    expect(btn).to_have_text("v2 ▾")
    expect(btn).to_have_attribute("aria-expanded", "false")
    expect(menu).to_be_hidden()

    btn.click()
    expect(menu).to_be_visible()
    expect(btn).to_have_attribute("aria-expanded", "true")
    # The walk starts on the version being read, not at the top of the list.
    expect(page.locator('.lf-version-row[data-lf-version="2"]')).to_be_focused()
    # The note is the whole note, on its own lines under the version it belongs to.
    expect(
        page.locator('.lf-version-row[data-lf-version="2"] .lf-version-note')
    ).to_have_text(long_note)
    assert page.evaluate(
        "() => { const n = document.querySelector("
        "'.lf-version-row[data-lf-version=\"2\"] .lf-version-note');"
        "  return n.getBoundingClientRect().height > "
        "         parseFloat(getComputedStyle(n).fontSize) * 1.6; }"
    ), "the note that a select could not hold is on one line here too"

    # The corpus axe pass walks every example with this menu shut, so the role
    # relationship it declares open — a menu owning menuitems, named — is checked
    # nowhere else. A select carried all of that from the platform and this does not.
    result = Axe().run(
        page,
        options={
            "runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a"]},
            "resultTypes": ["violations"],
        },
    )
    assert [
        v["id"]
        for v in result.response["violations"]
        if v["impact"] in {"serious", "critical"}
    ] == []

    # The keys are one declaration, so the "?" reference names them too — a page with
    # a second version is the first that has a list to walk.
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_contain_text("In the versions menu")
    expect(page.locator(".lf-help")).to_contain_text("Walk the versions")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-help")).not_to_have_class(re.compile("open"))
    expect(menu).to_be_visible()

    page.locator('.lf-version-row[data-lf-version="2"]').focus()
    page.keyboard.press("ArrowDown")
    expect(page.locator('.lf-version-row[data-lf-version="3"]')).to_be_focused()
    page.keyboard.press("ArrowDown")  # clamped: the last row keeps the focus
    expect(page.locator('.lf-version-row[data-lf-version="3"]')).to_be_focused()
    page.keyboard.press("ArrowUp")
    page.keyboard.press("ArrowUp")
    expect(page.locator('.lf-version-row[data-lf-version="1"]')).to_be_focused()
    page.keyboard.press("ArrowUp")  # clamped at the other end too
    expect(page.locator('.lf-version-row[data-lf-version="1"]')).to_be_focused()
    # The comparison the row it landed on states, which the reopen below reads: the base is
    # settled when the chooser says so, and the base's document is a fetch away, so a test
    # that closed the menu on the press alone would ask where the walk stands from a loaded
    # machine and be told the version being read.
    expect(btn).to_have_text("Δ v2 ▾")

    # Escape closes and hands focus back to the press, so the next Tab carries on
    # from the banner rather than from the top of the document.
    page.keyboard.press("Escape")
    expect(menu).to_be_hidden()
    expect(btn).to_be_focused()

    # v opens it from anywhere on the page, the way l opens the leaves tray, and lands
    # where the walk should carry on from, so that walk is the next press rather than a
    # Tab-hunt across the banner. This menu is the only place the notes are, so what each
    # version changed is reachable by keyboard through this key or not at all.
    #
    # Which row that is, is the comparison's: the walk above marked from v1, so the base
    # is v1 and the row carrying it is where an open lands. Landing on the version being
    # read would put the focus and the base on different rows, and the reader's next arrow
    # press would then move the base off the version they marked from — the whole reason
    # the two are one thing (showVersionMenu).
    page.keyboard.press("v")
    expect(menu).to_be_visible()
    expect(page.locator('.lf-version-row[data-lf-version="1"]')).to_be_focused()
    expect(btn).to_have_text("Δ v2 ▾")
    # And walking back down to the version being read is the way off it, which is the row
    # an open lands on with nothing standing.
    page.keyboard.press("ArrowDown")
    expect(btn).to_have_text("v2 ▾")
    # Inside the menu the letter is the menu's own — the newest version, tested where
    # it navigates — so Escape is what closes this.
    page.keyboard.press("Escape")
    expect(menu).to_be_hidden()
    expect(btn).to_be_focused()
    page.keyboard.press("v")
    expect(page.locator('.lf-version-row[data-lf-version="2"]')).to_be_focused()
    page.keyboard.press("Escape")

    # A second press is a close, not a re-open: without that the outside-click
    # handler and the toggle would both run and the menu could never stand.
    btn.click()
    expect(menu).to_be_visible()
    btn.click()
    expect(menu).to_be_hidden()

    # A click on the page closes it and leaves the reader where they were.
    btn.click()
    expect(menu).to_be_visible()
    # A point in the page's left margin: outside the column, and well clear of a menu
    # that hangs from the right of the bar over whatever the column has at the top.
    page.mouse.click(30, 700)
    expect(menu).to_be_hidden()
    assert "/versions/v2.html" in page.url, "closing the menu navigated"

    # Choosing a row is exact historical navigation, including for the newest stamp.
    btn.click()
    page.locator('.lf-version-row[data-lf-version="3"]').click()
    page.wait_for_url(re.compile(r"/versions/v3\.html\?pin=$"))
    assert errors == []
    page.close()


def test_the_versions_menu_suspends_the_pages_own_keys(browser, serve):
    """A mode standing over the page takes the page's keys. The chord and the reference
    always did and this menu did not, so mid-walk `d` scrolled a page the reader had
    stopped looking at and `c` opened the composer under the list. None of it failed
    loudly: each press did exactly what it promises, somewhere the reader was not — and
    the key line went on offering all of them, which is what made the offer the bug rather
    than the press.

    A claim is not the blanket it replaced, so the exemption is asserted beside it: the
    reference is the one key a mode keeps, being the key that says what the mode's own keys
    are, and a reader who has just opened something unfamiliar is the reader who wants it.

    Which presses are asserted is decided by what a suspended one leaves to read. A key
    the mode swallows moves nothing, and nothing is what an assertion made too early reads
    on a key that worked — so the presses here are the two whose effect is a class and a
    focus move in the same task as the keydown (`j` and `c`, both of which would raise the
    panel and one of which would take the focus out of the menu). `d` lands a glide later,
    where "not yet" and "never" read alike; the line is where it is held, off the same
    claim the dispatcher reads."""
    url = serve(LONG_PAGE, comments=2)
    _publish(
        serve.page_dir,
        2,
        LONG_PAGE.replace("Paragraph 3.", "Paragraph three."),
        "reworded a paragraph",
    )
    page, errors = open_page(browser, url.replace("v1.html", "v2.html"))
    menu = page.locator(".lf-version-menu")
    panel = page.locator(".lf-panel")
    line = page.locator(".lf-keyline")
    # Every one of them live on the page, which is what makes the suspension below the
    # mode's rather than the rows' own liveness.
    for word in ["comment", "threads", "half a page", "versions"]:
        expect(line).to_contain_text(word)

    page.keyboard.press("v")
    expect(menu).to_be_visible()
    row = page.locator('.lf-version-row[data-lf-version="2"]')
    expect(row).to_be_focused()
    # The line narrows to the menu's own keys with the page's gone from it, which is the
    # same claim the dispatcher reads — one statement, both surfaces.
    expect(line).to_contain_text("walk — marking changes")
    expect(line).to_contain_text("close versions")
    for word in ["comment", "threads", "half a page", "design mode"]:
        expect(line).not_to_contain_text(word)

    # The exemption: still one press to the reference, which still lists the mode standing
    # over the page, and Escape there leaves the menu where it was — with the reader on the
    # row they left, since a scope is where focus is and the overlay takes the focus. Landing
    # on the body instead put the walk it had just described out of reach, which is a poor
    # thing for the one key a mode keeps to do.
    expect(line).to_contain_text("more")
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_be_visible()
    expect(page.locator(".lf-help")).to_contain_text("In the versions menu")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-help")).not_to_have_class(re.compile("open"))
    expect(menu).to_be_visible()
    expect(row).to_be_focused()
    expect(line).to_contain_text("walk — marking changes")

    page.keyboard.press("j")  # would raise the panel and walk focus out of the menu
    page.keyboard.press("c")  # would raise it and put focus in its box
    expect(panel).to_be_hidden()
    expect(row).to_be_focused()
    expect(menu).to_be_visible(), "a page key closed the menu it was suspended by"

    # And with the mode down the same key reaches the page, so what stopped it was the menu
    # standing over the page rather than the key being broken.
    page.keyboard.press("Escape")
    expect(menu).to_be_hidden()
    page.keyboard.press("j")
    expect(panel).to_be_visible()
    expect(page.locator(".lf-thread").first).to_be_focused()
    assert errors == []
    page.close()


def test_a_row_the_platform_activates_names_both_of_its_keys(browser, serve):
    """A `<button>` is activated by Enter and by Space, and a row that says so by hand can
    say half of it. This one did: the version menu's row carries no `run` — the platform
    does the activating, and clicking behind it would be a second activation — so its keys
    are a description of what the browser will do, and the description read `⏎` while the
    control answered both. Nothing failed; the page under-promised a key that worked, which
    is the register's own failure wearing its quietest form.

    So the pair is one exported fact (`PRESS`) and the four rows that named it by hand read
    it: the runtime's control scope, a card grip in both its states, and this row. A link is
    what keeps that fact honest rather than growing into "controls answer two keys" — Enter
    follows an `<a>` and Space scrolls the page, so the leaves tray binds Enter alone and is
    right to."""
    url = serve(INLINE_PAGE)
    _publish(serve.page_dir, 2, INLINE_PAGE, "second")

    # A comparison checkbox is the menu's internal Tab stop rather than part of its
    # arrow-key row walk. Reaching it must not be mistaken for leaving the popup.
    compared, compared_errors = open_page(browser, url.replace("/v1.html", "/v2.html"))
    compared.keyboard.press("v")
    compared.locator('.lf-version-row[data-lf-version="1"]').focus()
    compared.keyboard.press("Tab")
    comparison = compared.locator('.lf-version-diff[data-lf-version="1"]')
    expect(comparison).to_be_focused()
    expect(compared.locator(".lf-version-menu")).to_be_visible()
    expect(compared.locator(".lf-keyline")).not_to_contain_text("leave versions")
    compared.keyboard.press("?")
    expect(compared.locator(".lf-help")).not_to_contain_text("Leave the versions menu")
    compared.keyboard.press("Escape")
    expect(comparison).to_be_focused()

    # Holding Tab sends repeated keydowns after the first stop. The boundary action must
    # repeat too: leaving the browser's focus move native does not mean leaving the menu
    # painted over the control that move reaches.
    compared.locator('.lf-version-row[data-lf-version="1"]').focus()
    compared.keyboard.down("Tab")
    expect(compared.locator('.lf-version-diff[data-lf-version="1"]')).to_be_focused()
    compared.keyboard.down("Tab")
    expect(compared.locator('.lf-version-row[data-lf-version="2"]')).to_be_focused()
    compared.keyboard.down("Tab")
    compared.keyboard.up("Tab")
    expect(compared.locator(".lf-version-menu")).to_be_hidden()
    expect(compared.locator(".lf-version")).to_have_attribute("aria-expanded", "false")

    compared.keyboard.press("v")
    compared.locator('.lf-version-row[data-lf-version="2"]').focus()
    compared.keyboard.down("Shift")
    compared.keyboard.down("Tab")
    expect(comparison).to_be_focused()
    compared.keyboard.down("Tab")
    expect(compared.locator('.lf-version-row[data-lf-version="1"]')).to_be_focused()
    compared.keyboard.down("Tab")
    compared.keyboard.up("Tab")
    compared.keyboard.up("Shift")
    expect(compared.locator(".lf-version-menu")).to_be_hidden()
    expect(compared.locator(".lf-version")).to_have_attribute("aria-expanded", "false")
    assert compared_errors == []
    compared.close()

    page, errors = open_page(browser, url, pin=True)

    page.keyboard.press("v")
    expect(page.locator(".lf-version-menu")).to_be_visible()
    # Both keys on both surfaces, off the one declaration.
    expect(page.locator(".lf-keyline")).to_contain_text("⏎ / space")
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_contain_text("⏎ / space")
    expect(page.locator(".lf-help")).to_contain_text("Open that version")
    page.keyboard.press("Escape")

    # And the key the row had been leaving unnamed does what the row now says it does.
    page.locator('.lf-version-row[data-lf-version="2"]').focus()
    page.keyboard.press("Space")
    page.wait_for_url(re.compile(r"/versions/v2\.html\?pin=$"))
    assert errors == []
    page.close()


def test_a_version_published_under_an_open_menu_reaches_it(browser, serve):
    """The list is rebuilt rather than reconciled, and an open menu defers the
    rebuild so a version landing mid-walk can't take the focused row away. What
    that defers has to survive the deferral: the key saying the list is current
    was consumed before the deferral was checked, so a version published while
    the menu stood marked the change handled and never wrote the row. The menu
    then sat one version short for as long as nothing else was published — and
    the poll it needed had already been and gone, so nothing was coming."""
    url = serve(INLINE_PAGE)
    _publish(serve.page_dir, 2, INLINE_PAGE, "two")
    page, errors = open_page(browser, url, pin=True)
    menu = page.locator(".lf-version-menu")
    expect(page.locator(".lf-version-row")).to_have_count(2)

    page.locator(".lf-version").click()
    expect(menu).to_be_visible()
    _publish(serve.page_dir, 3, INLINE_PAGE, "three")
    told(page)  # the poll that carries it has been and gone
    # Deferred, so the walk the reader is in the middle of is undisturbed.
    expect(page.locator(".lf-version-row")).to_have_count(2)

    page.keyboard.press("Escape")
    expect(menu).to_be_hidden()
    # And it arrives on the next poll rather than waiting on a fourth version.
    expect(page.locator(".lf-version-row")).to_have_count(3)
    expect(page.locator(".lf-version-row").last).to_contain_text("v3 (latest version)")
    assert errors == []
    page.close()


def test_the_current_page_is_the_chooser_key_twice(browser, serve):
    """A pinned version stays where the reader put it and offers the current page as a chip. The
    keyboard reaches that chip's destination through the chooser rather than past it: v
    opens the menu and the letter again takes the live page, by that row's own press, so
    the key leaves through the door the pointer uses and the historical URL stays exact.

    Which is the newest row, not the row the walk stands on — that one is Enter's, and a
    reader who has walked away from where they started must still be able to say "the
    current state" in one press. And the second press carries no liveness of its own,
    which is the point of spelling the move this way: the menu always has a current row,
    so the motion holds wherever the reader is — including on the page already reading
    that row, where a key of the page's own would have had to stand down and every
    surface say so."""
    url = serve(INLINE_PAGE)
    _publish(serve.page_dir, 2, INLINE_PAGE, "two")
    _publish(serve.page_dir, 3, INLINE_PAGE, "three")
    page, errors = open_page(browser, url, pin=True)
    menu = page.locator(".lf-version-menu")
    help_el = page.locator(".lf-help")
    expect(page.locator(".lf-latest-chip")).to_be_visible()

    # The menu's keys are one declaration, so the reference names this one beside the
    # walk it saves.
    page.keyboard.press("?")
    expect(help_el).to_contain_text("Open the current page")
    page.keyboard.press("Escape")

    # The first press opens and goes nowhere. A whole tick passes before the reading,
    # which is far longer than a navigation would take to start.
    page.keyboard.press("v")
    expect(menu).to_be_visible()
    ticked(page)
    assert page.url.endswith("pin"), "the press that opens the menu navigated"

    # Walk off the version being read, so the row under the focus is not the current one and
    # not the one this press takes.
    page.keyboard.press("ArrowDown")
    expect(page.locator('.lf-version-row[data-lf-version="2"]')).to_be_focused()
    page.keyboard.press("v")
    page.wait_for_url(re.compile(r"/$"))
    # The rebuilt list is what says the page arriving here has heard from the server.
    # A hidden chip does not: that is also how the banner stands before the first poll,
    # so an assertion on it alone would read the same on a page that had heard nothing —
    # and the reference below is written by that same poll.
    expect(page.locator(".lf-version-row")).to_have_count(3)
    expect(page.locator(".lf-latest-chip")).to_be_hidden()

    # And it is still offered here, with the chip gone: opening the current page is
    # what the press does on the page already reading it, so no surface stands it down.
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    expect(help_el).to_contain_text("Open the current page")
    assert errors == []
    page.close()


def test_the_menu_compares_with_any_version_older_than_this_one(browser, serve):
    """A page that ships a version whenever the work moves leaves its reader behind by
    more than one, and "what changed since the previous version" is then the wrong
    question: what they want marked is everything since they last looked. The base was
    the previous version for exactly as long as it was a control's own label — one
    button can name one version — so the menu is where it stops being one, and every row
    older than this one offers itself.

    The rest is what the reader can tell afterwards: the closed control says a
    comparison is standing, and reopening says which one, on the rows it spans.

    From the keyboard the base is the row the walk stands on, so the marks follow the
    walk: the note says in words what a version changed and the page says it in the
    passages, without the reader leaving the list to find out. That is also the whole of
    the way off, the page having no key for a comparison. It costs nothing to find,
    because the two ends of the walk are the two versions the reader already has in mind:
    an open lands on the standing base, and stepping down ends on the version being read,
    which is comparable with nothing."""
    v2 = INLINE_PAGE.replace("A neighbouring block", "A neighbouring passage")
    v3 = v2.replace("The setup is in the runbook", "The setup is in the handbook")
    url = serve(INLINE_PAGE)
    _publish(serve.page_dir, 2, v2, "reworded the neighbour")
    _publish(serve.page_dir, 3, v3, "reworded the compound")
    page, errors = open_page(browser, url.replace("v1.html", "v3.html"))

    # The previous version: the one change this version made.
    compare_with(page, 2)
    expect(page.locator(".lf-ins-block")).to_have_count(1)
    expect(page.locator("#compound")).to_have_class(re.compile(r"\blf-ins-block\b"))

    # Two versions back, which no single-label control could have offered: both.
    compare_with(page, 1)
    expect(page.locator(".lf-ins-block")).to_have_count(2)
    expect(page.locator("#p2")).to_have_class(re.compile(r"\blf-ins-block\b"))

    # What the closed chooser says about it — a word, not the accent alone, since a
    # reader in a stretch that changed nothing has only this to read it back off.
    expect(page.locator(".lf-version")).to_have_text("Δ v3 ▾")
    page.locator(".lf-version").click()
    expect(page.locator('.lf-version-diff[data-lf-version="1"]')).to_have_attribute(
        "aria-checked", "true"
    )
    expect(page.locator('.lf-version-diff[data-lf-version="2"]')).to_have_attribute(
        "aria-checked", "false"
    )
    # And the span it covers, which is what a base three versions back makes worth
    # saying: the rail runs from it to the version being read.
    assert page.evaluate(
        "() => [...document.querySelectorAll('.lf-version-row.lf-compared')]"
        ".map(r => r.dataset.lfVersion)"
    ) == ["1", "2", "3"]

    # Pressing the standing base again is the way off, and it takes the marks and the
    # word with it.
    page.locator('.lf-version-diff[data-lf-version="1"]').click()
    expect(page.locator(".lf-ins-block")).to_have_count(0)
    expect(page.locator(".lf-version")).to_have_text("v3 ▾")

    # A Δ is still reachable by keyboard, a Tab off the row it belongs to, and still the
    # toggle the pointer presses.
    page.locator(".lf-version").click()
    page.locator('.lf-version-row[data-lf-version="1"]').focus()
    page.keyboard.press("Tab")
    expect(page.locator('.lf-version-diff[data-lf-version="1"]')).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-ins-block")).to_have_count(2)

    # And the keyboard's way off, which is the walk: an open lands on the base the marks
    # came from rather than on the version being read, so the reader starts at one end of
    # the span the rail draws and steps down it to the other, where nothing is older to
    # compare against. Landing on the version being read instead would put the base a
    # press away from moving under them.
    page.keyboard.press("v")
    expect(page.locator('.lf-version-row[data-lf-version="1"]')).to_be_focused()
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    expect(page.locator('.lf-version-row[data-lf-version="3"]')).to_be_focused()
    expect(page.locator(".lf-ins-block")).to_have_count(0)
    page.keyboard.press("Escape")

    # And the walk, which is the same series of comparisons made by standing on the rows
    # rather than by naming a base: each step marks what changed since the row it lands
    # on, and the list stays up while the page marks behind it — the reader is reading
    # the note and the passages together.
    menu = page.locator(".lf-version-menu")
    page.keyboard.press("v")
    expect(page.locator('.lf-version-row[data-lf-version="3"]')).to_be_focused()
    expect(page.locator(".lf-ins-block")).to_have_count(0)

    page.keyboard.press("ArrowUp")
    expect(page.locator("#compound")).to_have_class(re.compile(r"\blf-ins-block\b"))
    expect(page.locator(".lf-ins-block")).to_have_count(1)
    expect(menu).to_be_visible()

    page.keyboard.press("ArrowUp")
    expect(page.locator(".lf-ins-block")).to_have_count(2)
    expect(page.locator("#p2")).to_have_class(re.compile(r"\blf-ins-block\b"))
    expect(page.locator(".lf-version")).to_have_text("Δ v3 ▾")

    # Back down, one version at a time: the earlier base's marks go with it rather than
    # standing beside the new one's, which is what a comparison being one base means.
    page.keyboard.press("ArrowDown")
    expect(page.locator(".lf-ins-block")).to_have_count(1)
    expect(page.locator("#compound")).to_have_class(re.compile(r"\blf-ins-block\b"))

    # And down onto the version being read, which is no comparison — the way off, on the
    # row an open lands on when nothing is standing.
    page.keyboard.press("ArrowDown")
    expect(page.locator(".lf-ins-block")).to_have_count(0)
    expect(page.locator(".lf-version")).to_have_text("v3 ▾")
    expect(menu).to_be_visible()
    assert errors == []
    page.close()


def test_a_diff_anchors_to_the_side_it_was_read_on(browser, serve):
    """The case this exists for, and the one a section cannot narrow: a diff carries the
    same line added and removed under a single id, so the user commenting on the fix
    had their comment marked against the bug — stored that way, and shown to Claude that
    way in the next round.

    The passage is picked out of the rendered widget, where syntax colour has cut the
    line into spans: `return` is a keyword and ` request.path` is the text after it, so
    the selection starts in one node and ends in another. That is the ordinary shape of a
    passage in a coloured block, and the anchor knows nothing about it — a span is no text
    block, so both readings still collapse to the same run of characters."""
    page, errors = open_page(browser, serve(TWICE_PAGE))
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    landed = page.evaluate("""async () => {
        const skip = '.lf-ui, script, style';
        // Rooted at the shadow root: lf-diff renders in one (x-shadow), so the lines
        // this drags across are in the composed tree and not under the host element.
        const w = document.createTreeWalker(document.getElementById('patch').shadowRoot,
            NodeFilter.SHOW_TEXT,
            {acceptNode: n => n.parentElement?.closest(skip)
                ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT});
        // One flat run over the widget's text nodes, and where each node started in it,
        // so a phrase is found whether or not a token boundary falls inside it.
        const nodes = [], starts = [];
        let flat = '';
        for (let n = w.nextNode(); n; n = w.nextNode()) {
            starts.push(flat.length); nodes.push(n); flat += n.data;
        }
        const phrase = 'return request.path';
        const hits = [];
        for (let i = flat.indexOf(phrase); i !== -1; i = flat.indexOf(phrase, i + 1)) hits.push(i);
        if (hits.length < 2) return `only ${hits.length} occurrence(s) — fixture broken`;
        const at = (offset) => {
            const i = starts.findLastIndex((s) => s <= offset);
            return [nodes[i], offset - starts[i]];
        };
        const start = hits.at(-1);   // the added line: the later of the pair
        const want = document.createRange();
        want.setStart(...at(start)); want.setEnd(...at(start + phrase.length));
        if (want.startContainer === want.endContainer)
            return 'the phrase sat in one node — colour never split it, so this proves nothing';
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(want);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
        await new Promise(r => setTimeout(r, 40));
        const fab = document.querySelector('.lf-fab');
        if (fab.style.display !== 'block') return 'no button';
        fab.click();
        await new Promise(r => setTimeout(r, 40));
        const painted = [...(CSS.highlights.get('lf-pending') ?? [])][0];
        if (!painted) return 'no mark';
        return painted.compareBoundaryPoints(Range.START_TO_START, want) === 0;
    }""")
    assert landed is True, (
        f"the added line was picked, the mark went elsewhere ({landed})"
    )
    assert errors == []
    page.close()


def test_an_id_staged_into_a_shadow_tree_is_still_the_pages_id(browser, serve):
    """Every question the runtime asks by id goes through one lookup, and a widget that
    stages its authored children carries their ids into its shadow tree with them. While
    that lookup was the document's alone the answer came back null and each caller quietly
    did nothing — here, an anchor stored and a mark never painted, with no error to find.

    Staged by hand because the one shipped x-shadow widget builds its tree out of parsed
    data and mints no ids, so nothing reaches this yet; what the next one does is exactly
    this move. The clearing sweep is the other half — a mark the repaint cannot reach is
    a mark that outlives its reason — so the second comment has to take the first's place
    rather than stand beside it."""
    page, errors = open_page(browser, serve(TWICE_PAGE))
    page.wait_for_function(
        "() => document.querySelector('lf-diff.lf-rendered') !== null"
    )
    page.evaluate(
        "() => document.getElementById('patch').shadowRoot"
        ".querySelector('pre').id = 'row'"
    )
    # Through a locator: the paint lands on the poll that follows the write rather than
    # with it, so a read taken straight after passes on a quiet machine and fails on a
    # busy one. `#row` reaches into the open tree the way the runtime now has to.
    row = page.locator("#row")
    marked = re.compile(r"\blf-mark-el\b")
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "id": "c-staged",
            "author": "user",
            "revision": 1,
            "text": "About the staged line.",
            "anchor": {"section": "row"},
        },
    )
    told(page)
    expect(row).to_have_class(marked)
    expect(row).to_contain_text("1 comment")

    # Resolved, so the next repaint has nothing to say here: the count line has to go,
    # and it can only go if the sweep that clears it enters the tree that holds it.
    events_model.append_event(
        d, {"kind": "resolve", "author": "user", "parent": "c-staged"}
    )
    told(page)
    expect(row).not_to_have_class(marked)
    expect(row).not_to_contain_text("comment")
    assert not errors, errors
    page.close()
