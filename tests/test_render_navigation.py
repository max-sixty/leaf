"""Comment marks, addresses, and keyboard navigation tests."""

import re

import pytest
from leaf import data as data_model
from leaf import event_log as events_model
from playwright.sync_api import expect
from render_support import (
    ADDRESS_PAGE,
    ADDRESSED_PAGE,
    BOARD_PAGE,
    CHIPS,
    CLIPPED_BY,
    CONTROL_LABEL_PAGE,
    CROWDED_PAGE,
    DECISIONS_PAGE,
    DISCLOSED_PAGE,
    EXAMPLES,
    FEATURE_GALLERY,
    FOOTED_PAGE,
    INLINE_PAGE,
    INSIDE_ITS_OPTION,
    LONG_PAGE,
    NOTED_PAGE,
    OVER_WORDS,
    PANEL_PAGE,
    RENDERED,
    ROOT,
    SEATED_ASK_LAYER,
    SEATED_ASK_WIDGETS,
    TARGETS_PAGE,
    TOKEN,
    WHERE_I_STAND_PAGE,
    _publish,
    card_body,
    composer_quote,
    expect_address_steps,
    hold_selection,
    in_threads_scrollport,
    key_line,
    leaf_page,
    live_url,
    mark_point,
    open_page,
    open_versions,
    opened_tab,
    page_at_rest,
    painted,
    panel_comment,
    panel_settled,
    pending_text,
    post_event,
    refuse,
    resized,
    round_trip,
    select,
    stamp_page,
    stamp_version_file,
    standing_mark,
    told,
    wait_for_pending_mark,
    wait_for_revision,
    wait_hovered,
    wait_standing,
    watched,
)

pytestmark = pytest.mark.nightly


def test_the_feature_gallery_exercises_the_injected_core_surfaces(
    browser, serve, live_leaf
):
    """Core chrome is a gallery journey, not merely present around its specimens."""
    live_leaf("second", "A second Leaf page")
    page, errors = open_page(browser, serve(FEATURE_GALLERY))
    resized(page, 1600, 900)

    expect(
        page.get_by_role(
            "heading",
            name="Asks: decisions and answers",
            exact=True,
        )
    ).to_be_visible()
    guide = page.locator("#bg-core-controls-guide")
    for surface in (
        "status line",
        "Threads",
        "version picker",
        "Map",
        "keyboard reference",
        "All leaves",
    ):
        expect(guide).to_contain_text(surface)
    expect(page.locator(".lf-banner-status")).not_to_be_empty()

    page.locator(".lf-decisions").click()
    asks = page.locator("button.lf-decisions-row")
    expect(asks).to_have_count(7)
    expect(asks.first.locator(".lf-decisions-kind")).to_have_text("ask")
    expect(asks.first.locator(".lf-decisions-says")).to_contain_text(
        "Which map should the sample team carry?"
    )
    asks.first.click()
    expect(page.locator("#bg-choice-ask")).to_be_focused()
    page.locator(".lf-decisions").click()

    page.locator(".lf-threads-toggle").click()
    expect(page.locator(".lf-panel")).to_be_visible()
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(2)
    expect(page.locator(".lf-details .lf-thread")).to_have_count(1)
    page.locator(".lf-threads-toggle").click()

    page.locator(".lf-version").click()
    expect(page.locator(".lf-version-menu .lf-version-row")).to_have_count(2)
    page.keyboard.press("Escape")

    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.get_by_role("dialog", name="Keyboard reference")).to_be_visible()
    page.keyboard.press("Escape")

    page.locator(".lf-others").click()
    expect(page.locator(".lf-others-panel")).to_be_visible()
    expect(page.locator("a.lf-others-row")).to_contain_text("A second Leaf page")
    page.keyboard.press("Escape")

    resized(page, 390, 900)
    page.evaluate("scrollTo(0, 0)")
    expect(page.locator("#bg-sidebar")).to_be_hidden()
    expect(
        page.get_by_role(
            "heading",
            name="Asks: decisions and answers",
            exact=True,
        )
    ).to_be_in_viewport()
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    expect(page.get_by_role("dialog", name="Page map", exact=True)).to_be_visible()
    assert errors == []
    page.close()


def test_the_feature_gallery_headings_are_stable_preview_destinations(browser, serve):
    """A preview can name its subject directly instead of asking the reader to find it."""
    root = live_url(serve(FEATURE_GALLERY))
    destination = "#bg-quoted-and-visual-heading"
    page, errors = open_page(browser, root + destination)

    links = page.get_by_role("navigation", name="On this page").get_by_role("link")
    targets = links.evaluate_all(
        """links => links.map(link => {
          const href = link.getAttribute('href');
          const target = document.getElementById(decodeURIComponent(href.slice(1)));
          return {href, tag: target?.localName || null,
                  generated: target?.dataset.lfGen === '1'};
        })"""
    )
    assert targets and all(
        target["tag"] in {"h1", "h2", "h3", "h4", "h5", "h6"}
        and not target["generated"]
        for target in targets
    ), targets
    assert len({target["href"] for target in targets}) == len(targets), targets

    target = page.locator(destination)
    expect(page).to_have_url(root + destination)
    expect(page.locator(":target")).to_have_attribute("id", destination[1:])
    expect(target).to_be_in_viewport()
    assert errors == []
    page.close()


def test_the_feature_gallery_exercises_core_reader_workflows(browser, serve):
    """Sign-off, layer comments, and request outcomes are real gallery journeys."""
    page, errors = open_page(browser, live_url(serve(FEATURE_GALLERY)))
    resized(page, 1280, 900)

    approve = page.locator(".lf-signoff")
    expect(approve).to_have_text("Approve version")
    approve.click()
    round_trip(page)
    expect(approve).to_have_text("✓ Version approved")
    page.keyboard.press("z")
    round_trip(page)
    expect(approve).to_have_text("Approve version")

    option = page.locator("#bg-choice-street")
    option_box = option.bounding_box()
    assert option_box is not None
    page.keyboard.press("i")
    expect(page.locator("body")).to_have_class(re.compile(r"\blf-design\b"))
    page.mouse.click(
        option_box["x"] + option_box["width"] / 2,
        option_box["y"] + option_box["height"] / 2,
    )
    expect(page.locator("#lf-composer-quote")).to_have_text(
        "layer · lf-option · bg-choice-street"
    )
    expect(option).not_to_have_attribute("chosen", "")
    page.locator(".lf-composer textarea").fill("The sample option needs less padding.")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    design_comment = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment" and event.get("about") == "layer"
    ][-1]
    assert design_comment["anchor"] == {"section": "bg-choice-street"}
    page.locator("body").focus()
    page.keyboard.press("Escape")
    expect(page.locator("body")).not_to_have_class(re.compile(r"\blf-design\b"))

    ready = page.locator("#bg-request-live")
    restart = ready.get_by_role("button", name="Restart the sample worker", exact=True)

    restart.click()
    round_trip(page)
    request = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "request" and event["widget"] == "bg-request-live"
    ][-1]
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "receipt",
            "author": "claude",
            "request": request["id"],
            "status": "failed",
            "text": "The sample branch is protected by another review",
        },
    )
    told(page)
    expect(ready).to_contain_text(
        "restart failed · The sample branch is protected by another review"
    )
    expect(restart).to_be_enabled()

    restart.click()
    round_trip(page)
    retried = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "request" and event["widget"] == "bg-request-live"
    ][-1]
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "receipt",
            "author": "claude",
            "request": retried["id"],
            "status": "succeeded",
            "text": "Restarted the sample worker",
        },
    )
    told(page)
    expect(ready).to_contain_text("restart succeeded · Restarted the sample worker")
    expect(restart).to_be_disabled()

    def reject(route):
        route.fulfill(
            status=400,
            json={"ok": False, "error": "gallery transport refusal", "final": True},
        )

    page.route("**/api/event", reject)
    change = page.locator('[data-lf-margin-for="bg-replace"]')
    change.get_by_role(
        "button", name=re.compile(r"^Accept the suggested change")
    ).click()
    retry = change.get_by_role("button", name="Retry", exact=True)
    expect(retry).to_be_visible()
    expect(change.get_by_role("button", name="Cancel", exact=True)).to_be_visible()
    expect(change).to_contain_text("Failed")
    change.get_by_role("button", name="Cancel", exact=True).click()
    expect(retry).to_have_count(0)

    assert errors and all("400" in error for error in errors)
    page.close()


def test_the_feature_gallery_exercises_live_and_snapshotted_external_data(
    browser, serve
):
    """One captured source supplies a following view, a snapshot, and provenance."""
    page, errors = open_page(browser, live_url(serve(FEATURE_GALLERY)))
    live = page.locator("#bg-source-live")
    frozen = page.locator("#bg-source-snapshot")
    original = (
        '[route]\nname = "covered terrace"\ndistance_km = 1.8\nstatus = "sample"\n'
    )

    expect(live.locator("code")).to_have_text(original)
    expect(frozen.locator("code")).to_have_text(original)
    expect(frozen.locator("figcaption")).to_have_text(
        "feature-gallery-source.toml at sample-1 · lines 1–4 · snapshot 1"
    )

    changed = '[route]\nname = "river path"\ndistance_km = 2.1\nstatus = "updated"\n'
    data_model.cmd_data_set(serve.page_dir, "gallery-source", changed)
    expect(live.locator("code")).to_have_text(changed)
    expect(frozen.locator("code")).to_have_text(original)
    expect(page.locator("#bg-measurement-guide")).to_contain_text(
        "measurement is behind its source"
    )

    assert errors == []
    page.close()


def test_an_external_link_says_and_opens_where_it_goes(browser, serve, other_leaf):
    other_url, _ = other_leaf
    destination = f"{other_url}/?t={TOKEN}"
    url = serve(
        leaf_page(
            "external link",
            f"""
<h1 id="top">Links</h1>
<p>Read the <a id="external" href="{destination}" aria-label="other leaf documentation"
  aria-describedby="source-note">other leaf</a>.</p>
<span id="source-note" hidden>curated source</span>
<p>Return to <a id="fragment" href="#top">the heading</a>.</p>
<svg viewBox="0 0 40 20" aria-label="map"><a id="svg-external" href="{destination}">
  <text x="0" y="15">map</text>
</a></svg>
""",
        )
    )
    page, errors = open_page(browser, url)
    external = page.locator("#external")
    mark = external.locator(":scope > .lf-external-mark")

    expect(external).to_have_attribute("target", "_blank")
    expect(external).to_have_attribute("rel", re.compile(r"(?:^| )noopener(?: |$)"))
    expect(external).to_have_accessible_name("other leaf documentation")
    expect(external).to_have_accessible_description("curated source opens in a new tab")
    expect(page.locator("#external + .lf-external-note")).to_be_hidden()
    expect(mark).to_be_visible()
    assert mark.evaluate("node => node.localName") == "svg"
    expect(mark.locator(":scope > path")).to_have_count(1)
    expect(mark).to_have_attribute("aria-hidden", "true")
    expect(page.locator("#fragment > .lf-external-mark")).to_have_count(0)
    expect(page.locator("#fragment")).not_to_have_attribute("target", "_blank")
    expect(page.locator("#svg-external > .lf-external-mark")).to_have_count(0)
    expect(page.locator("#svg-external")).not_to_have_attribute("target", "_blank")

    tab = opened_tab(page, external.click)
    expect(tab).to_have_url(destination)
    expect(page).to_have_url(url)
    tab.close()
    assert errors == []
    page.close()


def test_an_addressed_link_leaves_the_reader_at_its_destination(
    browser, serve, other_leaf
):
    """A numbered link address completes the trip it names.

    A fragment lands focus on its target, so the reader does not remain at the place they
    left. An external link keeps its new-tab behavior and names that context change even
    though the chord activates the link without first moving focus through it."""
    other_url, _ = other_leaf
    destination = f"{other_url}/?t={TOKEN}"
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "addressed links",
                f"""
<h1>Addressed links</h1>
<p><a id="internal" href="#arrival">Read the conclusion</a>.</p>
<p><a id="external" href="{destination}" aria-label="Leaf guide">Open the guide</a>.</p>
<h2 id="arrival">Conclusion</h2>
<p>The internal trip ends here.</p>
""",
            )
        ),
    )

    page.keyboard.press("g")
    page.keyboard.press("h")
    page.keyboard.press("1")
    page.wait_for_url(re.compile(r"#arrival$"))
    expect(page.locator("#arrival")).to_be_focused()

    page.keyboard.press("g")
    page.keyboard.press("h")
    tab = opened_tab(page, lambda: page.keyboard.press("2"))
    expect(tab).to_have_url(destination)
    expect(page.locator(".lf-live")).to_have_text("Opened Leaf guide in a new tab")
    tab.close()
    assert errors == []
    page.close()


def test_an_inline_tab_keeps_its_panel_inside_one_visible_boundary(browser, serve):
    """The strip reads as an index inside the one frame that bounds its workstream.

    The selected name becomes one compact paper face; the tab around it does not grow a
    second frame inside the shared surface. The strip's closing rule keeps the index
    distinct from the panel, whose enclosing frame still answers how far that
    workstream runs.
    """
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "bounded tabs",
                """
<h1 id="heading">Parallel work</h1>
<p id="shared">This context belongs to every workstream.</p>
<lf-tabs id="workstreams">
  <lf-tab id="implementation" label="Implementation">
    <section id="implementation-section">
      <h2 id="implementation-heading">Build the narrow path</h2>
      <p id="implementation-end">This closing line still belongs to Implementation.</p>
    </section>
  </lf-tab>
  <lf-tab id="research" label="Research">
    <section id="research-section">
      <h2 id="research-heading">Test the broad premise</h2>
      <p id="research-end">This closing line still belongs to Research.</p>
    </section>
  </lf-tab>
</lf-tabs>
<section id="next-section"><h2 id="next-heading">Whole-page conclusion</h2></section>
""",
            )
        ),
    )
    boundary = page.evaluate(
        """() => {
          const tabs = document.querySelector('#workstreams');
          const strip = tabs.querySelector('.lf-tabstrip');
          const panel = tabs.querySelector('lf-tab:not([hidden])');
          const selected = strip.querySelector('[aria-selected="true"]');
          const inactive = strip.querySelector('[aria-selected="false"]');
          const opening = panel.querySelector('h2');
          const closing = panel.querySelector('p:last-child');
          const next = document.querySelector('#next-section');
          const box = element => {
            const rect = element.getBoundingClientRect();
            return {left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom};
          };
          const style = (element, pseudo) => getComputedStyle(element, pseudo);
          const face = tab => {
            const tabStyle = style(tab);
            const label = tab.querySelector('[data-lf-said]');
            const labelStyle = style(label);
            const markStyle = style(label, '::before');
            return {
              ground: tabStyle.backgroundColor,
              border: ['Top', 'Right', 'Bottom', 'Left'].map(
                edge => parseFloat(tabStyle[`border${edge}Width`])),
              shadow: tabStyle.boxShadow,
              tabDecoration: tabStyle.textDecorationLine,
              labelGround: labelStyle.backgroundColor,
              labelInk: labelStyle.color,
              labelDecoration: labelStyle.textDecorationLine,
              labelPadding: ['Top', 'Right', 'Bottom', 'Left'].map(
                edge => parseFloat(labelStyle[`padding${edge}`])),
              beforeContent: markStyle.content,
            };
          };
          return {
            tabs: box(tabs), strip: box(strip), panel: box(panel),
            opening: box(opening), closing: box(closing), next: box(next),
            frame: {
              top: parseFloat(style(tabs).borderTopWidth),
              right: parseFloat(style(tabs).borderRightWidth),
              bottom: parseFloat(style(tabs).borderBottomWidth),
              left: parseFloat(style(tabs).borderLeftWidth),
              color: style(tabs).borderTopColor,
              ground: style(tabs).backgroundColor,
            },
            divider: {
              width: parseFloat(style(strip).borderBottomWidth),
              color: style(strip).borderBottomColor,
            },
            palette: {
              ink: style(document.body).color,
            },
            selected: face(selected),
            inactive: face(inactive),
          };
        }"""
    )

    frame_edges = tuple(
        boundary["frame"][edge] for edge in ("top", "right", "bottom", "left")
    )
    assert min(frame_edges) > 0, (
        f"the tab surface has an open edge: {boundary['frame']}"
    )
    assert boundary["frame"]["color"] != "rgba(0, 0, 0, 0)", boundary
    assert boundary["divider"]["width"] > 0, boundary
    assert boundary["divider"]["color"] != "rgba(0, 0, 0, 0)", boundary
    assert boundary["selected"]["ground"] == "rgba(0, 0, 0, 0)", boundary
    assert boundary["inactive"]["ground"] == boundary["selected"]["ground"], boundary
    assert max(boundary["selected"]["border"]) == 0, boundary
    assert max(boundary["inactive"]["border"]) == 0, boundary
    assert boundary["selected"]["shadow"] == "none", boundary
    assert boundary["inactive"]["shadow"] == "none", boundary
    assert boundary["selected"]["tabDecoration"] == "none", boundary
    assert boundary["selected"]["labelGround"] == boundary["frame"]["ground"], boundary
    assert boundary["inactive"]["labelGround"] == "rgba(0, 0, 0, 0)", boundary
    assert boundary["selected"]["labelInk"] == boundary["palette"]["ink"], boundary
    assert (
        boundary["selected"]["labelPadding"] == boundary["inactive"]["labelPadding"]
    ), boundary
    assert boundary["selected"]["labelDecoration"] == "none", boundary
    assert boundary["inactive"]["labelDecoration"] == "none", boundary
    assert boundary["selected"]["beforeContent"] == "none", boundary
    assert boundary["inactive"]["beforeContent"] == "none", boundary
    assert boundary["opening"]["top"] - boundary["strip"]["bottom"] >= 16, boundary
    assert boundary["opening"]["left"] - boundary["tabs"]["left"] >= 16, boundary
    assert boundary["tabs"]["right"] - boundary["opening"]["right"] >= 16, boundary
    assert boundary["tabs"]["bottom"] - boundary["closing"]["bottom"] >= 16, boundary
    assert boundary["next"]["top"] > boundary["tabs"]["bottom"], boundary

    selected = page.locator('#workstreams [aria-selected="true"]')
    selected.focus()
    focus = selected.evaluate(
        """element => {
          const style = getComputedStyle(element);
          return {width: parseFloat(style.outlineWidth), style: style.outlineStyle};
        }"""
    )
    assert focus["width"] > 0 and focus["style"] != "none", focus
    assert errors == []
    page.close()


def test_keys_answer_a_question_from_its_marks(browser, serve):
    """The Ask's digits stay live while a mark adds only its control-local keys.

    One Tab enters the marks, where ↑/↓ walk the options and clamp at the ends.
    Moving focus does not replace the Ask's numeric action context with a widget copy.
    """
    page, errors = open_page(browser, serve(DECISIONS_PAGE))
    nums = page.locator("#live-question > lf-option > .lf-address")
    expect(nums.first).to_be_hidden()

    page.keyboard.press("a")
    marks = page.locator("#live-question .lf-pick")
    # The arrival stands on the decision, which wears its options' digits; the marks
    # are the next Tab stops.
    expect(
        page.locator("#live-question > lf-option > .lf-address[data-lf-ask-address]")
    ).to_have_text(["1", "2"])
    page.keyboard.press("Tab")
    expect(marks.first).to_be_focused()
    expect(
        page.locator("#live-question > lf-option > .lf-address[data-lf-ask-address]")
    ).to_have_text(["1", "2"])
    expect(nums.first).to_be_visible()
    expect(nums.nth(1)).to_have_text("2")
    assert marks.first.get_attribute("aria-keyshortcuts") == (
        "ArrowUp ArrowDown Space 1"
    )
    assert marks.nth(1).get_attribute("aria-keyshortcuts") == (
        "ArrowUp ArrowDown Space 2"
    )

    page.keyboard.press("ArrowUp")
    expect(marks.first).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(marks.nth(1)).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(marks.nth(1)).to_be_focused()

    page.keyboard.press("1")
    expect(page.locator("#lq-keep")).to_have_attribute("chosen", "")
    round_trip(page)
    acts = [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "action"
    ]
    assert acts[-1]["widget"] == "live-question"
    assert acts[-1]["detail"] == {"options": ["lq-keep"]}
    assert errors == []
    page.close()


def test_a_questions_digits_are_drawn_whole(browser, serve):
    """An address arrives into room its option is already holding, and lands on nothing.

    Every earlier placement borrowed that room instead, and each borrow showed. On the
    cell's outer corner the chip was half outside a group that clips itself, so no
    address the product drew had ever been whole — seven of its seventeen pixels gone,
    and in a bare-label group the first digit was a sliver.
    Out in the page margin beside the group it was whole and it was in the neighbouring
    card's prose, because a middle column's margin is another cell. Neither showed up
    as a failure: a clipped element still reports its whole box and still answers
    `to_be_visible`, and a chip drawn over words breaks no rule anybody had written.

    So the cell holds a column for it, and this asks the two questions that column
    answers — does any ancestor cut it, is it on anybody's words — in both forms,
    stepped through with the key that reaches them, since the room inside a cell is
    exactly what differed: cards padded clear of their corners, rows with none to
    spare.

    How far down the column it stands is each form's own answer, so each is asked for the
    fact it states rather than for one number covering both. A card's digit rides at the
    head of that column, beside the title rather than over it; a row's is centred on the
    row. Pinned as one 8px it was level with a 15px row, and the day the row went to the
    page's own 17px it was two pixels too high with the gate still green — because what
    the gate read was the number the theme stated, and the claim beside it, that a row's
    digit is level with its words, was checked by nothing.

    How far in it stands is the whole group's, and it is asked as the relation it is: the
    gutter reads cell edge, digit, then prose, so the digit is measured against those two
    neighbours and against the other form's seat. Pinned as the number the gutter came to,
    the reading broke twice over a neighbour it was never about — once when a status rule
    took the head of the column and the digit moved along behind it, and again when that
    rule left and it moved back."""
    page, errors = open_page(browser, serve(ADDRESS_PAGE))
    seats = {}
    for options, sitting in [
        (["c-heater", "c-cable", "c-hand"], "in the corner"),
        (["r-now", "r-later"], "centred"),
    ]:
        page.keyboard.press("a")
        # The arrival stands on the decision; the digits are drawn once a mark holds the
        # focus, one Tab in.
        page.keyboard.press("Tab")
        for id_ in options:
            chip = page.locator(f"#{id_} > .lf-address")
            expect(chip).to_be_visible()
            cut = chip.evaluate(CLIPPED_BY)
            assert cut is None, f"{id_}'s digit is cut: {cut}"
            # Never on the hairline the outer corner would have shared with the cells
            # around it, and never in either neighbour's room: the option's gutter opens
            # at the cell's own start, and its words open at the column the option pads
            # to. Read the row form here as well as the cards above; both reserve
            # address, then prose in the same leading gutter.
            sits = chip.evaluate(INSIDE_ITS_OPTION)
            assert 0 < sits["x"] < sits["ends"] < sits["opens"], (
                f"{id_}'s digit runs {sits['x']}…{sits['ends']} in a gutter that starts "
                f"at its cell's own edge and whose words open at {sits['opens']}, so the "
                "gutter is holding one of the two in the other's room"
            )
            seats.setdefault(round(sits["x"], 1), []).append(id_)
            if sitting == "in the corner":
                assert round(sits["y"]) == 8, (
                    f"{id_}'s digit sits {sits['y']} down from its option's top, not in "
                    "the corner of the column its card reserves"
                )
            else:
                assert abs(sits["level"]) <= 0.5, (
                    f"{id_}'s digit is {sits['level']}px off the middle of its row's own "
                    "words"
                )
            assert sits["past"] <= 0, (
                f"{id_}'s digit hangs past its own option and onto the next"
            )
            # Asked of the words rather than of the numbers, because the numbers are
            # only right for as long as the column the theme reserves is.
            on = chip.evaluate(OVER_WORDS, id_)
            assert on is None, f"{id_}'s digit is drawn over the words “{on}”"
    # One column, in both forms: a card's cell and a row's are the two shapes whose room
    # differed, and a seat each would read as a straight rail down neither.
    assert len(seats) == 1, f"the digits stand at more than one column: {seats}"
    assert errors == []
    page.close()


def test_composer_marks_the_passage_instead_of_quoting_it(browser, serve):
    """The passage stays visible while its comment is written. Focus moves into the
    composer the moment it opens, which drops the browser's own selection, so the
    runtime paints the anchor itself, and repaints it after every pass that redraws
    the posted threads' marks around it — otherwise a comment arriving mid-sentence
    would leave the reader's passage stranded across stale text nodes. It comes down
    with the box, and the whole time it never touches the document.

    And because the mark says which passage the box is on, the box doesn't say it too:
    the quote inside it stays out of sight while the page is marking the passage."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)

    page.locator("#p").click(
        click_count=3
    )  # a real selection, spanning the inline tags
    page.locator(".lf-fab-input").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'contents'"
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
            "() => document.querySelector('.lf-composer textarea').getAttribute('aria-describedby')"
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
    # nodes the painted range is pinned to. The reader is mid-sentence; their passage
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

    # A passage with the runtime's own chrome inside it paints around the chrome, the way
    # the search reads around it — one range per segment, not one spanning the lot.
    # Across both options, so a Choose button falls in the middle of the passage rather
    # than after it — where a single range spanning the whole thing would swallow it.
    chrome = page.locator("#opts .lf-pick").first.text_content().strip()
    assert chrome, "this assertion needs the widget to have rendered chrome inside it"
    page.evaluate("""() => {
        const r = document.createRange();
        r.selectNodeContents(document.querySelector('#opts'));
        const s = getSelection(); s.removeAllRanges(); s.addRange(r);
        document.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
    }""")
    page.locator(".lf-fab-input").click()
    wait_for_pending_mark(page)
    assert chrome not in pending_text(page), (
        f"the highlight painted the widget's own {chrome!r} control along with the passage"
    )
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
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 2")
    assert page.locator("#fig.lf-mark-el.lf-pending").count() == 1, (
        "a poll landing while the composer is open dropped the outline"
    )

    # Both classes have to go, asserted apart: leaving .lf-mark-el behind repaints the
    # figure in the posted mark's own ink, pointer cursor and all, over no thread to open.
    page.keyboard.press("Escape")
    assert page.locator("#fig.lf-pending").count() == 0, (
        "the outline outlived its composer"
    )
    assert page.locator("#fig.lf-mark-el").count() == 0, (
        "the figure kept a thread's outline over no thread"
    )

    # A drag across the caption remains a native selection, so the composer carries the
    # caption's words rather than the enclosing figure's element anchor.
    cap = page.locator("#fig figcaption").bounding_box()
    y = cap["y"] + cap["height"] / 2
    select(page, (cap["x"] + 2, y), (cap["x"] + cap["width"] - 2, y))
    page.locator(".lf-fab-input").click()
    wait_for_pending_mark(page)
    assert "specimen" in pending_text(page), (
        "the visual containing the drag replaced its selected passage"
    )
    assert page.locator("#fig.lf-pending").count() == 0, (
        "the figure got the element outline over a live selection"
    )
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_the_pointer_over_a_page_mark_lights_its_comment_quote(browser, serve):
    """The page and panel are reciprocal views of a thread. Resting on a card lights
    its passage; resting on that passage must identify the bounded quote naming it too.
    Filling the card instead turns a long conversation into a viewport-sized wash. The
    signal follows the pointer from one thread to the next and leaves with it."""
    url = serve(
        INLINE_PAGE,
        anchored=[("p", "bold text"), ("p2", "neighbouring block")],
    )
    comments = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ]
    first_id, second_id = (comment["id"] for comment in comments)
    page, errors = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    first = page.locator(f'.lf-thread[data-id="{first_id}"]')
    second = page.locator(f'.lf-thread[data-id="{second_id}"]')
    first_quote = first.locator(":scope > .lf-quote")
    resting = first.evaluate("element => getComputedStyle(element).backgroundColor")
    quote_resting = first_quote.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
    page.mouse.move(*mark_point(page, "lf-mark", 0))
    expect(first).to_have_class(re.compile(r"\blf-mark-hover\b"))
    expect(second).not_to_have_class(re.compile(r"\blf-mark-hover\b"))
    assert (
        first.evaluate("element => getComputedStyle(element).backgroundColor")
        == resting
    ), "pointing at a passage washed the whole thread card instead of its quote"
    quote_lit = first_quote.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
    assert quote_lit != quote_resting, (
        f"the page named the quote in class but its paint stayed {quote_resting!r}"
    )
    assert first_quote.bounding_box()["height"] < first.bounding_box()["height"]

    page.mouse.move(*mark_point(page, "lf-mark", 1))
    expect(first).not_to_have_class(re.compile(r"\blf-mark-hover\b"))
    expect(second).to_have_class(re.compile(r"\blf-mark-hover\b"))

    page.mouse.move(2, 2)
    expect(page.locator(".lf-thread.lf-mark-hover")).to_have_count(0)

    # A narrowing can put a different card under a hand that has not moved. The list
    # reconcile is therefore one of the hover's inputs, just like page geometry.
    page.mouse.move(*card_body(page, "About this bit."))
    wait_hovered(page, "bold text")
    page.fill(".lf-find-box", "neighbouring block")
    expect(page.locator(".lf-threads > .lf-thread")).to_have_count(1)
    expect(second).to_have_class(re.compile(r"\blf-mark-hover\b"))
    wait_hovered(page, "neighbouring block")
    assert errors == []
    page.close()


def test_a_page_mark_does_not_wash_a_long_thread_card(browser, serve):
    """The reciprocal cue stays at the quote when its conversation is taller than the
    list. A short-card case proves selector routing but cannot reproduce the full-panel
    slab that made direct navigation visually ambiguous."""
    url = serve(INLINE_PAGE, anchored=[("p", "bold text")])
    root = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "claude",
            "parent": root,
            "revision": 1,
            "text": "\n\n".join(
                f"Consideration {i}: this thread needs its full context."
                for i in range(18)
            ),
        },
    )
    page, errors = open_page(browser, url)
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(f'.lf-thread[data-id="{root}"]')
    quote = thread.locator(":scope > .lf-quote")
    card_resting = thread.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
    quote_resting = quote.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
    assert (
        thread.bounding_box()["height"]
        > page.locator(".lf-threads").bounding_box()["height"]
    ), "the card fits in the list, so this does not reproduce the large wash"

    page.mouse.move(*mark_point(page, "lf-mark"))
    expect(thread).to_have_class(re.compile(r"\blf-mark-hover\b"))
    assert (
        thread.evaluate("element => getComputedStyle(element).backgroundColor")
        == card_resting
    )
    assert (
        quote.evaluate("element => getComputedStyle(element).backgroundColor")
        != quote_resting
    )
    assert (
        quote.bounding_box()["height"]
        < page.locator(".lf-threads").bounding_box()["height"]
    )
    assert errors == []
    page.close()


def test_a_thread_walk_starts_one_page_trip_and_reveals_its_nested_passage(
    browser, serve
):
    """The range travel has two jobs: reveal a passage inside its nested scrollports,
    then centre it vertically in the document. `scrollIntoView` also moved the document,
    jumping it to the nearest edge synchronously before the intended smooth centred trip
    began. Both local axes must remain immediate, while the page makes only one move."""
    lead = "".join(
        f"<p>Reading context before the passage, line {i}.</p>" for i in range(32)
    )
    tail = "".join(
        f"<p>Reading context after the passage, line {i}.</p>" for i in range(20)
    )
    source = leaf_page(
        "one thread trip",
        f"""
<h1>One thread trip</h1>
{lead}
<div id="local">
  {"".join(f"<p>Local context line {i}.</p>" for i in range(16))}
  <pre id="rail"><code>{"prefix " * 80}Far-side passage to review.</code></pre>
</div>
{tail}
""",
        head=(
            "<style>#local { max-height: 240px; overflow-y: auto; "
            "overflow-x: clip; }</style>"
        ),
    )
    page, errors = open_page(
        browser,
        serve(source, anchored=[("far", "Far-side passage")]),
    )
    page.evaluate(
        """() => {
          document.scrollingElement.scrollTo({top: 0, behavior: 'instant'});
          document.querySelector('#rail').scrollLeft = 0;
          window.lfFirstPageScroll = null;
          document.addEventListener('scroll', (event) => {
            if (event.target === document && window.lfFirstPageScroll === null)
              window.lfFirstPageScroll = document.scrollingElement.scrollTop;
          }, {capture: true});
        }"""
    )

    page.keyboard.press("t")
    page.wait_for_function("() => window.lfFirstPageScroll !== null")
    immediate = page.evaluate(
        """() => ({
          firstPage: window.lfFirstPageScroll,
          rail: document.querySelector('#rail').scrollLeft,
          local: document.querySelector('#local').scrollTop,
          localXFits: document.querySelector('#local').scrollWidth
            <= document.querySelector('#local').clientWidth,
        })"""
    )
    assert immediate["firstPage"] < 100, (
        f"the thread walk jumped the page before its smooth trip began: {immediate}"
    )
    assert immediate["rail"] > 0, (
        f"the passage stayed beyond its own horizontal scroller: {immediate}"
    )
    assert immediate["local"] > 0, (
        f"the passage stayed beyond its own vertical scroller: {immediate}"
    )
    assert immediate["localXFits"], (
        f"the vertical scrollport also overflowed sideways: {immediate}"
    )
    page.wait_for_function(
        """() => {
          const range = [...(CSS.highlights.get('lf-mark-here') ?? [])][0];
          if (!range) return false;
          const rect = range.getBoundingClientRect();
          return Math.abs((rect.top + rect.bottom) / 2 - innerHeight / 2) < 2;
        }"""
    )
    expect(page.locator(".lf-thread")).to_be_focused()
    assert errors == []
    page.close()


@pytest.mark.parametrize("long_thread", [False, True], ids=["short", "long"])
def test_pressing_a_page_mark_stands_in_the_thread_it_opens(
    browser, serve, long_thread
):
    """Opening a thread by pointer is ready for a reply. Escape explicitly leaves
    typing; only then does t navigate. The page mark follows both focus modes."""
    url = serve(
        INLINE_PAGE, anchored=[("p", "bold text"), ("p2", "neighbouring block")]
    )
    if long_thread:
        root = next(
            event["id"]
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "comment"
        )
        events_model.append_event(
            serve.page_dir,
            {
                "kind": "reply",
                "author": "claude",
                "parent": root,
                "revision": 1,
                "text": "\n\n".join(
                    f"Consideration {i}: the response needs room for its explanation."
                    for i in range(18)
                ),
            },
        )
    page, errors = open_page(browser, url)
    threads = page.locator(".lf-threads > .lf-thread")
    thread = threads.first
    reply = thread.locator(":scope > .lf-compose textarea")

    page.mouse.click(*mark_point(page, "lf-mark"))
    panel_settled(page)

    expect(reply).to_be_focused()
    if long_thread:
        expect(thread).not_to_have_class(re.compile(r"\bflash\b"))
        expect(thread.locator(":scope > .lf-compose")).to_have_class(
            re.compile(r"\bflash\b")
        )
    in_threads_scrollport(page, ".lf-threads > .lf-thread:first-of-type .lf-compose")
    if long_thread:
        page.wait_for_function(
            """() => {
              const list = document.querySelector('.lf-threads');
              const thread = list.querySelector('.lf-thread:first-of-type');
              const compose = thread.querySelector(':scope > .lf-compose');
              const view = list.getBoundingClientRect();
              const target = compose.getBoundingClientRect();
              const clear = parseFloat(getComputedStyle(list).scrollPaddingTop) || 0;
              const start = view.top + clear;
              const blocks = [...thread.querySelectorAll(
                ':scope > .lf-msg, :scope > .lf-msg .lf-msg-body > *, ' +
                ':scope > .lf-msg .lf-msg-text > *'), compose];
              return target.bottom <= view.bottom && blocks.some((block) =>
                Math.abs(block.getBoundingClientRect().top - start) < 2);
            }"""
        )
        landing = page.evaluate(
            """() => {
              const list = document.querySelector('.lf-threads');
              const thread = list.querySelector('.lf-thread:first-of-type');
              const compose = thread.querySelector(':scope > .lf-compose');
              const view = list.getBoundingClientRect();
              const target = compose.getBoundingClientRect();
              const clear = parseFloat(getComputedStyle(list).scrollPaddingTop) || 0;
              const start = view.top + clear;
              const head = list.querySelector('.lf-pinned').getBoundingClientRect();
              const blocks = [...thread.querySelectorAll(
                ':scope > .lf-msg, :scope > .lf-msg .lf-msg-body > *, ' +
                ':scope > .lf-msg .lf-msg-text > *'), compose]
                .map((block) => ({
                  name: block.className || block.tagName,
                  top: block.getBoundingClientRect().top,
                }));
              const lines = [];
              const walker = document.createTreeWalker(thread, NodeFilter.SHOW_TEXT);
              for (let text; text = walker.nextNode();) {
                if (!text.data.trim()) continue;
                for (let i = 0; i < text.length; i++) {
                  const range = document.createRange();
                  range.setStart(text, i);
                  range.setEnd(text, Math.min(i + 1, text.length));
                  const line = range.getBoundingClientRect();
                  if (line.width && line.top < head.bottom && line.bottom > head.bottom)
                    lines.push(line.toJSON());
                }
              }
              return {target: target.toJSON(), listBottom: view.bottom, start, blocks,
                      crossedLines: lines};
            }"""
        )
        assert landing["target"]["bottom"] <= landing["listBottom"]
        assert any(
            block["top"] == pytest.approx(landing["start"], abs=2)
            for block in landing["blocks"]
        ), f"the long arrival cut through a content block: {landing}"
        assert not landing["crossedLines"], (
            f"the pinned heading cut through a text line: {landing}"
        )
    wait_standing(page, "bold text")
    assert "back to thread" in key_line(page)
    page.keyboard.press("t")
    expect(reply).to_have_value("t")
    expect(reply).to_be_focused()
    page.keyboard.press("Escape")
    expect(thread).to_be_focused()
    assert "reply" in key_line(page)
    page.keyboard.press("t")
    expect(threads.nth(1)).to_be_focused()
    wait_standing(page, "neighbouring block")
    page.keyboard.press("Enter")
    expect(threads.nth(1).locator(":scope > .lf-compose textarea")).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("Shift+t")
    expect(thread).to_be_focused()
    page.keyboard.press("Enter")
    expect(reply).to_be_focused()
    in_threads_scrollport(page, ".lf-threads > .lf-thread:first-of-type .lf-compose")
    assert errors == []
    page.close()


def test_the_page_marks_the_comment_the_reader_is_standing_in(browser, serve):
    """A reader sent from a comment to its passage lands among every other mark on the
    page, all of them painted alike, and the panel is the only surface saying which one
    they asked for. The page says it too: the thread holding the focus paints its own
    passage apart from the rest for as long as the reader remains in that thread.

    Read off the focus rather than off the travel, so it answers where the reader *is*.
    The walk moves it, a reply box keeps it — standing in a comment is standing in it
    while writing back — and leaving the panel takes it down, rather than leaving a page
    wearing "you are here" about a comment nobody is in."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)
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
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 2")
    page.locator("#fig.lf-mark-el").wait_for()

    assert standing_mark(page) == {
        "text": "",
        "elements": [],
    }, "a page nobody has opened a comment on is already saying the reader is in one"

    page.keyboard.press("t")
    wait_standing(page, "bold text")

    # The four readings of a marked passage have to stay in this order, or one of them
    # stops being visible where they overlap: the posted mark, the hover over it, the
    # standing comment's own ink, and above all three the draft the reader is writing.
    # Asked with the pointer actually resting on the standing mark, because that is the
    # overlap the order exists for and because nothing registers the hover until a mouse
    # has been over a passage. A higher highlight supplies only the properties it states,
    # so this is what lets one mark say "clickable" and "you are here" at once.
    # Opening the panel moves the document; settle it before reading pointer geometry.
    panel_settled(page)
    page.mouse.move(*mark_point(page, "lf-mark-here"))
    page.wait_for_function("() => (CSS.highlights.get('lf-mark-hover')?.size ?? 0) > 0")
    ranks = page.evaluate(
        """() => ['lf-mark', 'lf-mark-hover', 'lf-mark-here', 'lf-pending']
            .map(n => CSS.highlights.get(n)?.priority ?? null)"""
    )
    assert all(r is not None for r in ranks) and ranks == sorted(set(ranks)), (
        f"the marks' paint order is not strictly increasing: {ranks}"
    )
    assert standing_mark(page)["text"] == "bold text", (
        "the pointer resting on the standing mark took its own ink away"
    )

    page.keyboard.press("t")
    wait_standing(page, "neighbouring block")

    # A passage with no words to paint says the same thing with the outline it already
    # wears, so the two kinds of anchor answer one question and not two.
    page.keyboard.press("t")
    wait_standing(page, "", ["fig"])
    page.keyboard.press("t")
    expect(page.locator(".lf-thread").last).to_be_focused()
    wait_standing(page, "", ["fig"])
    page.keyboard.press("Shift+t")
    wait_standing(page, "neighbouring block")
    page.keyboard.press("Shift+t")
    wait_standing(page, "bold text")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-thread").first).to_be_focused()
    wait_standing(page, "bold text")

    # Standing in a comment while writing back to it is still standing in it: the reply
    # box is inside the thread, and knowing which passage it is on is worth most there.
    page.locator(".lf-threads > .lf-thread").first.locator("textarea").focus()
    wait_standing(page, "bold text")

    # And leaving the panel takes it down. A mark that outlived the reader's attention
    # would be a page insisting on a comment nobody is in.
    page.evaluate("() => document.activeElement.blur()")
    wait_standing(page, "")
    assert painted(page, "lf-mark") != "", (
        "the posted marks went down with the standing one"
    )
    assert errors == []
    page.close()


def test_a_hovered_thread_rebinds_to_a_replaced_anchor(browser, serve):
    """A live version replaces the authored nodes but keeps the thread and its anchor.
    With the pointer parked on that card, the semantic hover id does not change; its
    Range still must move from the detached v1 text node onto the connected v2 one."""
    url = serve(INLINE_PAGE, anchored=[("p", "bold text")])
    page, errors = open_page(browser, live_url(url))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    point = card_body(page, "About this bit.")
    page.mouse.move(*point)
    wait_hovered(page, "bold text")
    page.evaluate(
        "() => { window.__lfOldHoverNode = "
        "[...CSS.highlights.get('lf-mark-hover')][0].startContainer; }"
    )
    # Keep the same live card under the pointer throughout the swap. This isolates the
    # anchor pass's record replacement from the view transition's temporary snapshots.
    page.evaluate("() => { document.startViewTransition = undefined; }")

    v2 = INLINE_PAGE.replace(
        "<strong>bold text</strong>", '<span data-v2="true">bold text</span>'
    )
    _publish(serve.page_dir, 2, v2, "kept the passage while replacing its markup")
    told(page)
    expect(page.locator(".lf-version")).to_contain_text("v2")
    page.wait_for_selector('[data-v2="true"]')
    wait_hovered(page, "bold text")
    state = page.evaluate("""() => {
        const range = [...CSS.highlights.get('lf-mark-hover')][0];
        return {
            oldConnected: window.__lfOldHoverNode.isConnected,
            text: range?.toString() ?? null,
            rebound: Boolean(range && range.startContainer !== window.__lfOldHoverNode),
            connected: Boolean(range?.startContainer.isConnected),
            card: document.querySelector('.lf-thread')?.classList.contains('lf-mark-hover'),
        };
    }""")
    assert state == {
        "oldConnected": False,
        "text": "bold text",
        "rebound": True,
        "connected": True,
        "card": True,
    }, f"the parked hover did not move from the detached v1 anchor to v2: {state}"
    expect(page.locator(".lf-thread")).to_have_class(re.compile(r"\blf-mark-hover\b"))
    assert errors == []
    page.close()


def test_the_pointer_over_a_comment_lights_the_passage_it_is_about(browser, serve):
    """A reader scanning a full panel asks the same thing of every card — which of these
    is about what — and pressing one to find out spends a travel they may not want. The
    pointer resting on the card answers it: a card is the thread's view in the list the
    way a mark is its view in the prose, so the same wash lights the same passage from
    either side. The standing mark answers the question for the comment the reader chose;
    this answers it for the one under their hand.

    Read in the frame that already answers the page's own hover, because the pointer is
    in one place and the two readings are one answer: markAt refuses a point that lands
    in the chrome, so a card's reading and a mark's cannot both name a thread, and a
    second writer to this highlight would be overwritten by whichever frame ran last.

    The cursor stays behind on the page. It is the promise that pressing here opens
    something, and over a card the press on offer is the card's own."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)
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
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 2")
    page.locator(".lf-threads-toggle").click()
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 3")

    assert painted(page, "lf-mark-hover") == "", (
        "a page whose pointer has touched nothing is already lighting a passage"
    )

    # Three things a mark can be — posted, indicated, stood in — are three steps of one
    # wash, and the middle one exists because this gesture puts the pointer over the panel
    # by construction: a hover sharing the standing wash left the two lit identically
    # whenever a hand rested where it had just clicked, with a 2px underline hue the only
    # thing between them.
    #
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
        const rules = [...document.styleSheets].flatMap(s => {
            try { return [...s.cssRules] } catch { return [] }
        });
        const probe = document.createElement('div');
        document.body.append(probe);
        const declared = (name) => {
            const r = rules.find(r => (r.selectorText ?? '') === `::highlight(${name})`);
            if (!r?.style?.backgroundColor) return null;
            probe.style.backgroundColor = r.style.backgroundColor;
            return getComputedStyle(probe).backgroundColor;
        };
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
                                    ['standing', 'lf-mark-here']]) {
            const css = declared(name);
            steps[step] = css === null ? null : over(css);
        }
        probe.remove();
        if (Object.values(steps).some(v => v === null)) return {missing: steps};
        return {
            fromGround: Object.fromEntries(
                Object.entries(steps).map(([k, v]) => [k, +de(v, ground).toFixed(2)])),
            apart: {
                'posted→pointed': +de(steps.posted, steps.pointed).toFixed(2),
                'pointed→standing': +de(steps.pointed, steps.standing).toFixed(2),
            },
        };
    }""")
    assert "missing" not in ramp, (
        f"a step of the mark ramp has no wash rule at all: {ramp['missing']}"
    )
    order = ramp["fromGround"]
    assert order["posted"] < order["pointed"] < order["standing"], (
        "the three things a mark can be are not three steps away from the page's own"
        f" ground, so the wash does not rank them: {order}"
    )
    assert min(ramp["apart"].values()) >= 4, (
        "two steps of the mark ramp are too close for a reader to tell apart without one"
        f" of the other beside it: {ramp['apart']}"
    )

    page.mouse.move(*card_body(page, "on the first"))
    wait_hovered(page, "bold text")
    # The wash is the page's, and the cursor is not: body wears lf-over-mark only while
    # the pointer is on the page's own mark, or every card in the panel would promise a
    # press the page does not make — the quote inside the card makes its own.
    assert not page.evaluate(
        "() => document.body.classList.contains('lf-over-mark')"
    ), "resting on a card told the page the pointer was on a mark"

    # It follows the pointer along the list, so a sweep down the panel reads out what
    # each comment is about in turn.
    page.mouse.move(*card_body(page, "on the second"))
    wait_hovered(page, "neighbouring block")

    # An element anchor answers too, in the property it has. ::highlight paints glyphs and
    # a box has none, so the wash lands on nothing there and the middle step is said in
    # the outline instead — the same rank, one weight up from the posted hairline. Without
    # it the pointer over an element-anchored card did nothing at all, which from the
    # panel reads as a broken hover rather than as a passage with no words.
    page.mouse.move(*card_body(page, "on the figure"))
    wait_hovered(page, "")
    hovered_el = page.locator("#fig")
    expect(hovered_el).to_have_class(re.compile(r"\blf-mark-hover\b"))
    assert (
        page.evaluate(
            "() => getComputedStyle(document.querySelector('#fig')).outlineWidth"
        )
        == "2px"
    ), "the pointer on an element-anchored card left its box unchanged"

    # Standing in one comment while pointing at another says both, because they answer
    # different questions and rank apart: the standing mark keeps its ink above the wash.
    page.locator(".lf-thread").filter(has_text="on the first").first.focus()
    wait_standing(page, "bold text")
    page.mouse.move(*card_body(page, "on the second"))
    wait_hovered(page, "neighbouring block")
    assert standing_mark(page)["text"] == "bold text", (
        "pointing at another comment's card took the standing comment's mark away"
    )

    # And the pointer leaving the panel puts it down, while what the page posted stays.
    page.mouse.move(2, 2)
    wait_hovered(page, "")
    assert painted(page, "lf-mark") != "", (
        "the posted marks went down with the pointer's"
    )
    assert errors == []
    page.close()


def test_closing_the_panel_puts_down_the_card_it_was_lighting(browser, serve):
    """The panel going away is the card going out from under the pointer, and the wash it
    was lighting has to go with it. Escape closes the panel from wherever the reader is
    standing, so the pointer never moves and nothing else asks the hover question again —
    the page is left washing a passage with no card, no pointer on it, and nothing on the
    screen that says why."""
    url = serve(INLINE_PAGE)
    page, errors = open_page(browser, url)
    post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "on the first",
            "anchor": {"section": "p", "quote": "bold text"},
        },
    )
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) >= 1")
    page.locator(".lf-threads-toggle").click()
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")

    page.mouse.move(*card_body(page, "on the first"))
    wait_hovered(page, "bold text")

    page.keyboard.press("Escape")
    page.wait_for_function("() => !document.body.hasAttribute('data-lf-panel')")
    wait_hovered(page, "")
    assert errors == []
    page.close()


def test_a_commented_block_says_so_to_a_screen_reader(browser, serve):
    """A mark is painted, not wrapped, so it builds no accessibility node and a passage
    carrying a comment reads exactly like one that doesn't. No ARIA relation reaches a
    block that isn't focusable, so the pass says it in the one thing every screen reader
    announces — text — counting up per block, riding in on a sent comment's round trip,
    and leaving with its thread. Having put words on the page, it then has to keep them
    out of the document's own: out of a selection, out of the next quote, and out of the
    mutations a screen reader rebuilds its buffer on."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir

    def comment(anchor, text):
        return events_model.append_event(
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
    page, errors = open_page(browser, url)
    page.wait_for_function("() => (CSS.highlights.get('lf-mark')?.size ?? 0) > 0")
    # Two threads on one block count up, and leave one line rather than two.
    assert "2 comments" in page.locator("#p1").aria_snapshot(), (
        "a screen reader reading the block hears nothing about the comments on it"
    )
    assert page.locator("#p1 .lf-mark-note").count() == 1, "one block, one line"
    # Hidden means hidden from the eye, not the tree: a line that paints is the runtime
    # writing visible prose into the author's paragraph.
    assert page.locator("#p1 .lf-mark-note").evaluate(
        "el => { const r = el.getBoundingClientRect(); return r.width <= 1 && r.height <= 1; }"
    ), "the hidden line is painting on screen"
    note = page.locator("#p1 .lf-mark-note")
    assert note.evaluate("el => getComputedStyle(el).opacity") == "0"
    expect(note).to_have_role("button")
    note.click()
    expect(page.locator(f'.lf-thread[data-id="{c1}"]')).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).not_to_have_class(re.compile(r"\bopen\b"))
    note.focus()
    expect(note).to_be_focused()
    assert note.evaluate("el => el.getBoundingClientRect().width > 1"), (
        "the comment path stayed invisible when a keyboard reader reached it"
    )
    assert note.evaluate("el => getComputedStyle(el).opacity") == "1"
    note.press("Enter")
    expect(page.locator(f'.lf-thread[data-id="{c1}"]')).to_be_focused()
    page.keyboard.press("t")
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()

    # Once the first thread resolves, the same control enters the next one.
    events_model.append_event(d, {"kind": "resolve", "author": "user", "parent": c1})
    told(page)
    expect(note).to_have_text("1 comment")
    note.press("Enter")
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()
    # An element anchor has no text to paint, and the element it names holds the line.
    assert "1 comment" in page.locator("#fig").aria_snapshot()

    # A pass that finds nothing to change must change nothing: a screen reader rebuilds
    # its buffer on every mutation, and this pass runs on every poll. A comment on no
    # passage at all is what proves a pass ran without touching the block's count.
    page.evaluate("""() => {
        window.__churn = 0;
        new MutationObserver(rs => (window.__churn += rs.length))
            .observe(document.getElementById('p1'),
                     {childList: true, characterData: true, subtree: true});
    }""")
    comment({}, "On the page as a whole.")
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 4")
    assert page.evaluate("() => window.__churn") == 0, (
        "a poll that changed nothing still rewrote the block, so a screen reader re-reads it"
    )

    # The line belongs to the runtime, not the document: a user dragging across it
    # neither copies it nor quotes it.
    page.locator("#p1").click(click_count=3)
    assert "comment" not in page.evaluate("() => getSelection().toString()"), (
        "the hidden line came along in the user's own selection"
    )
    page.locator(".lf-fab-input").click()
    assert "comment" not in composer_quote(page)["text"], (
        "the hidden line came along in the quote the comment would store"
    )
    page.keyboard.press("Escape")

    # The gesture's own comment reaches the line once the send's round trip lands.
    box = page.locator("#p2").bounding_box()
    y = box["y"] + box["height"] / 2
    select(page, (box["x"] + 2, y), (box["x"] + box["width"] - 2, y))
    page.locator(".lf-fab-input").click()
    page.wait_for_function(
        "() => document.querySelector('.lf-composer').style.display === 'contents'"
    )
    page.locator(".lf-composer textarea").fill("Too short.")
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator("#p2 .lf-mark-note")).to_have_count(1)
    c4 = [e for e in events_model.read_events(d) if e.get("kind") == "comment"][-1][
        "id"
    ]

    # A resolved thread takes its line with it: the pass owns what it wrote.
    events_model.append_event(d, {"kind": "resolve", "author": "user", "parent": c4})
    told(page)
    expect(page.locator("#p2 .lf-mark-note")).to_have_count(0)
    assert "1 comment" in page.locator("#p1").aria_snapshot()

    # A passage crossing two blocks says so in both: a reader landing on either block
    # hears about the comment, the way the paint reaches both.
    comment({"quote": "to land in it. A short second"}, "Crosses the boundary.")
    told(page)
    expect(page.locator("#p2 .lf-mark-note")).to_have_count(1)
    assert "2 comments" in page.locator("#p1").aria_snapshot()
    assert "1 comment" in page.locator("#p2").aria_snapshot()
    assert errors == []
    page.close()


def test_addresses_fit_the_visible_screen_before_collisions_are_removed(browser, serve):
    """Whole key sequences fit at viewport edges, including below the banner.

    The two left-edge links on the same line start far enough apart for their original
    chips to fit. Bringing the first chip on screen makes them collide.
    """
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "addresses at the edges",
                """
<h1 id="top">Addresses at the edges</h1>
<nav id="edges" aria-label="Edge links">
  <a id="left" href="#top">Left</a>
  <a id="right" href="#top">Right</a>
  <a id="bottom" href="#top">Bottom</a>
  <a id="below-banner" href="#top">Below the banner</a>
  <a id="under-banner" href="#top">Under the banner</a>
  <a id="crowded-left" href="#top">Crowded left</a>
  <a id="crowded-neighbor" href="#top">Crowded neighbor</a>
</nav>
""",
                head="""<style>
  #edges a { position: fixed; display: block; width: 1px; height: 20px;
    overflow: hidden; white-space: nowrap; }
  #left { left: 1px; top: 200px; }
  #right { left: calc(100vw - 1px); top: 280px; }
  #bottom { left: 70vw; top: calc(100vh - 1px); }
  #below-banner { left: 45vw; top: calc(var(--lf-banner-h) + 1px); }
  #under-banner { left: 60vw; top: calc(var(--lf-banner-h) - 8px); }
  #crowded-left { left: 1px; top: 400px; }
  #crowded-neighbor { left: 80px; top: 400px; }
</style>""",
            )
        ),
    )
    page.keyboard.press("g")
    page.keyboard.press("h")
    expect(page.locator(CHIPS).first).to_have_text("gh1")
    reading = page.evaluate(
        """() => ({
          width: document.documentElement.clientWidth,
          height: document.documentElement.clientHeight,
          banner: document.querySelector('.lf-banner').getBoundingClientRect().bottom,
          chips: [...document.querySelectorAll('.lf-chord-address')].map(chip => ({
            route: chip.textContent,
            ...chip.getBoundingClientRect().toJSON(),
          })),
        })"""
    )
    assert len(reading["chips"]) >= 6, reading
    for chip in reading["chips"]:
        assert 0 <= chip["left"] < chip["right"] <= reading["width"], reading
        assert reading["banner"] <= chip["top"] < chip["bottom"] <= reading["height"], (
            reading
        )
    assert [chip["route"] for chip in reading["chips"]] == [
        "gh1",
        "gh2",
        "gh3",
        "gh4",
        "gh5",
        "gh6",
    ], reading
    page.keyboard.press("6")
    expect(page.locator(CHIPS)).to_have_count(0)
    expect(page.locator("#top")).to_be_focused()
    assert errors == []
    page.close()


def test_no_address_is_drawn_on_top_of_another(browser, serve):
    """An address the reader can read is one no other address is sitting on.

    Chips sit above the corner their member starts at. Several links can start within
    one chip's width, as they do in a footnote run.

    Stacked, they do not read as two. The lower one shows an edge and the upper one's digit
    is the number the reader takes for the link underneath — so the promise is wrong rather
    than merely crowded, and the press goes somewhere else. The covered chip is taken down
    instead: its address still works, and the page has simply not said it, which is the
    answer already given for a member scrolled off screen.

    What is asserted is the property and not a count, because how many survive is the
    font's answer about how wide the keys are."""
    page, errors = open_page(browser, serve(CROWDED_PAGE))
    resized(page, 1280, 800)
    page.keyboard.press("g")
    # Something is on offer, or the rest of this proves nothing: four links and one fold,
    # of which the crowded ones are meant to lose their chips.
    expect(page.locator(CHIPS).first).to_be_visible()

    piles = page.evaluate(
        """() => {
             const boxes = [...document.querySelectorAll('.lf-addresses > .lf-address')]
               .map(chip => ({
                 keys: [...chip.querySelectorAll('kbd')].map(key => key.textContent),
                 r: chip.getBoundingClientRect(),
               }));
             const hit = (a, b) => a.left < b.right && b.left < a.right
                                && a.top < b.bottom && b.top < a.bottom;
             const found = [];
             for (let i = 0; i < boxes.length; i++)
               for (let j = i + 1; j < boxes.length; j++)
                 if (hit(boxes[i].r, boxes[j].r))
                   found.push(boxes[i].keys.join(' ') + ' under ' + boxes[j].keys.join(' '));
             return {found, drawn: boxes.map(b => b.keys)};
           }"""
    )
    assert piles["found"] == [], (
        f"addresses are drawn on top of each other: {piles['found']} "
        f"(drawn: {piles['drawn']})"
    )
    # And the page was crowded, or a clean sweep says nothing. Five members start within a
    # chip's width of each other here — three footnote markers, the link that is the whole
    # of a summary, and the summary itself — so all five surviving would mean the chips had
    # stopped colliding rather than that this pass had taken the collisions down. Two is
    # the fewest a pair can be checked between. The window between those two numbers is
    # what a chip growing or shrinking moves, which is the change that empties this test.
    drawn = piles["drawn"]
    assert 2 <= len(drawn) < 5, (
        f"the crowded page drew {len(drawn)} of its five addresses ({drawn}): the pass "
        f"either dropped nothing or left too few to have checked a pair"
    )
    # And the ones that survived still say what they reach: pressing the first visible
    # complete route follows that link, not the neighbour whose chip it might have worn.
    first = piles["drawn"][0]
    leader, letter, digit = first
    assert leader == "g"
    assert letter == "h", f"the first surviving route is not a hyperlink: {first}"
    page.keyboard.press(letter)
    page.keyboard.press(digit)
    fragment = {"1": "s1", "2": "s2", "3": "s3", "4": "s1"}[digit]
    page.wait_for_url(re.compile(rf"#{fragment}$"))
    assert errors == []
    page.close()


def test_an_address_is_never_drawn_on_the_key_line(browser, serve):
    """The chord's own legend is the one thing its chips must not cover.

    A chip is placed from its member's corner in a layer above everything, and the key line
    stands in the bottom-left corner of that same layer. A member whose first line begins
    there therefore wears its address on top of the line — which is the legend saying what
    the digits mean, on screen for exactly as long as the chips are. The banner at the top
    has always been dodged; the line at the foot was not, and the change that paints every
    list at once put four times as many chips in reach of it.

    Dropped rather than nudged clear: moved up, the chip would name a member it no longer
    sits on, and the address works whether or not the page draws it."""
    page, errors = open_page(browser, serve(FOOTED_PAGE))
    resized(page, 900, 700)
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()

    # Swept rather than asked once. The line's whole band is reserved at the document's foot,
    # so the end of the page is exactly where this cannot happen; what puts a member in the
    # corner is an ordinary scroll position with a link resting on the bottom edge. Each
    # step waits for the runtime's own paint frame, since the chips follow a scroll on a
    # frame of their own and boxes read in the same turn are the positions it just left.
    fouled = page.evaluate(
        f"""async () => {{
             const line = () => document.querySelector('.lf-keyline').getBoundingClientRect();
             const hit = (a, b) => a.left < b.right && b.left < a.right
                                && a.top < b.bottom && b.top < a.bottom;
             const out = [];
             const room = document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight;
             for (let i = 0; i <= 20; i++) {{
               document.scrollingElement.scrollTo(0, Math.round((room * i) / 20));
               await ({RENDERED})();
               const bar = line();
               for (const chip of document.querySelectorAll('.lf-addresses > .lf-address'))
                 if (hit(chip.getBoundingClientRect(), bar))
                   out.push(chip.textContent + ' at ' + Math.round(document.scrollingElement.scrollTop));
             }}
             return out;
           }}"""
    )
    assert fouled == [], (
        f"addresses are drawn over the key line that explains them: {fouled}"
    )
    assert errors == []
    page.close()


def test_the_g_chord_reaches_panels_and_document_lists(browser, serve):
    """A mnemonic completes one-off panel travel; a digit refines a document list.

    Threads and asks already have repeatable category walks, so their g chords land in
    the panels that hold those categories. Hyperlinks and folds have no such walk;
    their mnemonic opens the numbered address stage instead."""
    url = serve(ADDRESSED_PAGE)
    d = serve.page_dir

    def comment(anchor, text):
        return events_model.append_event(
            d,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": text,
                "anchor": anchor,
            },
        )["id"]

    c1 = comment({"quote": "passage under discussion"}, "Sharpen this.")
    comment({"quote": "two separate remarks"}, "Second thought.")
    c3 = comment({"section": "p2"}, "The short one too.")
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 3")
    line = page.locator(".lf-keyline")

    # The page's own key is the letter alone: what it opens is a table, and a range on the
    # line here could only ever have counted one of the lists in it.
    expect(line).to_contain_text("go to")
    expect(line).not_to_contain_text("1–3")

    # Wide enough that the panel will stand beside the page rather than over it, which is
    # where a box in the fixed chrome and the page's flow part company: body is narrowed
    # as the layout shell, the panel is fixed and is not inside it, and a chip placed by
    # walking the page's clips came back with the whole reply box clipped away.
    resized(page, 1280, 800)

    # The complete reference and the armed line are two projections of the register. Keep
    # the command identities from the reference so the assertion below fails when a new
    # live continuation reaches dispatch and help but not the visible chord menu.
    page.keyboard.press("?")
    page.keyboard.press("?")
    goto = page.locator(
        ".lf-help-section", has=page.get_by_role("heading", name="Go to")
    )
    reference_commands = set(
        goto.locator("tr[data-lf-command]").evaluate_all(
            "rows => rows.map(row => row.dataset.lfCommand)"
        )
    )
    assert reference_commands, "the page must contribute live Go to commands"
    overlaps = goto.locator("tr[data-lf-command]").evaluate_all(
        """rows => rows.flatMap(row => {
          const [key, action] = row.querySelectorAll(':scope > td');
          const amount = key.firstElementChild.getBoundingClientRect().right
            - action.getBoundingClientRect().left;
          return amount > 0.5 ? [{command: row.dataset.lfCommand, amount}] : [];
        })"""
    )
    assert overlaps == [], f"a complete route overlaps its action: {overlaps}"
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")

    # Armed, the line names the available panels and document lists. Every destination
    # keeps its complete route, with the leader painted as already pressed.
    page.keyboard.press("g")
    key_line(page)
    visible_chord = line.locator(".lf-key:not([hidden])")
    visible_commands = set(
        visible_chord.evaluate_all(
            """hints => hints.flatMap(hint =>
              (hint.dataset.lfCommands || '').split(' ').filter(Boolean))"""
        )
    )
    assert visible_commands == reference_commands, (
        "the armed line and live Go to register diverged: "
        f"line={sorted(visible_commands)}, reference={sorted(reference_commands)}"
    )
    for command, steps, states, words in [
        (
            "navigation.panel.threads",
            ["g", "T"],
            ["pressed", "neutral"],
            "Threads panel",
        ),
        (
            "navigation.panel.decisions",
            ["g", "A"],
            ["pressed", "neutral"],
            "Asks panel",
        ),
        (
            "navigation.page-map",
            ["g", "M"],
            ["pressed", "neutral"],
            "Page map",
        ),
        (
            "navigation.page-map-item",
            ["g", "m", "1–3"],
            ["pressed", "neutral", "neutral"],
            "Page map locations",
        ),
        (
            "navigation.link",
            ["g", "h", "1–2"],
            ["pressed", "neutral", "neutral"],
            "hyperlinks",
        ),
        (
            "navigation.fold",
            ["g", "f", "1"],
            ["pressed", "neutral", "neutral"],
            "folds",
        ),
        (
            "navigation.page.top",
            ["g", "g / G"],
            ["pressed", "neutral"],
            "top / bottom",
        ),
        (
            "navigation.address.back",
            ["esc"],
            ["neutral"],
            "cancel",
        ),
    ]:
        hint = line.locator(f'.lf-key:not([hidden])[data-lf-commands~="{command}"]')
        expect(hint).to_have_count(1)
        sequence = hint.locator(".lf-key-sequence")
        assert (
            sequence.evaluate(
                "el => [...el.querySelectorAll(':scope > kbd')].map(k => k.textContent)"
            )
            == steps
        )
        assert (
            sequence.evaluate(
                "el => [...el.querySelectorAll(':scope > kbd')].map(k => k.dataset.lfKeyState)"
            )
            == states
        )
        expect(sequence).to_have_attribute(
            "aria-label", " then ".join(step.replace(" / ", " or ") for step in steps)
        )
        expect(hint).to_contain_text(words)
    assert "navigation.panel.leaves" not in reference_commands

    # The visible More control and its registered `?` command are one route. An unmatched
    # key first disarms the chord and keeps its ordinary meaning; a pointer press must enter
    # the same shelf rather than inspecting the still-armed stack and skipping to the full
    # reference.
    def disclosure_state():
        return page.evaluate(
            """() => ({
              help: document.querySelector('.lf-help').open,
              expanded: document.querySelector('.lf-keyline').dataset.lfExpanded,
              pressed: document.querySelectorAll(
                '.lf-keyline kbd[data-lf-key-state="pressed"]'
              ).length,
              commands: [...document.querySelectorAll('.lf-keyline .lf-key:not([hidden])')]
                .flatMap(hint => (hint.dataset.lfCommands || '').split(' ').filter(Boolean)),
            })"""
        )

    page.get_by_role("button", name="? more", exact=True).click()
    page.evaluate(RENDERED)
    pointer_disclosure = disclosure_state()
    page.reload()
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 3")
    resized(page, 1280, 800)
    page.keyboard.press("g")
    page.keyboard.press("?")
    page.evaluate(RENDERED)
    key_disclosure = disclosure_state()
    assert pointer_disclosure == key_disclosure, (
        "the visible More control and its ? binding diverged: "
        f"pointer={pointer_disclosure}, key={key_disclosure}"
    )
    page.keyboard.press("Escape")
    page.keyboard.press("g")

    for width in (1280, 420):
        resized(page, width, 800)
        page.wait_for_function(
            """() => {
              const line = document.querySelector('.lf-keyline');
              const chrome = document.querySelector('.lf-chrome');
              return parseFloat(chrome.style.paddingBottom) >= line.offsetHeight + 19;
            }"""
        )
        geometry = line.evaluate(
            """node => {
              const visible = [...node.children].filter(el => el.checkVisibility());
              const tops = [];
              const tolerance = Math.min(...visible.map(el => el.offsetHeight)) / 2;
              for (const el of visible)
                if (tops.every(top => Math.abs(top - el.offsetTop) > tolerance))
                  tops.push(el.offsetTop);
              const box = node.getBoundingClientRect();
              return {
                rows: tops.length,
                clientWidth: node.clientWidth,
                scrollWidth: node.scrollWidth,
                clientHeight: node.clientHeight,
                scrollHeight: node.scrollHeight,
                left: box.left,
                right: box.right,
                viewport: innerWidth,
                height: box.height,
              };
            }"""
        )
        assert geometry["scrollWidth"] <= geometry["clientWidth"], geometry
        assert geometry["scrollHeight"] <= geometry["clientHeight"], geometry
        assert geometry["left"] >= 0 and geometry["right"] <= geometry["viewport"], (
            geometry
        )
        assert geometry["rows"] <= (2 if width == 1280 else 4), geometry
        assert geometry["height"] <= 800 * 0.2, geometry
    resized(page, 1280, 800)
    expect(page.locator(CHIPS).first).to_be_visible()
    # The chips are the eye's copy of a mode; a reader who cannot see them is told the
    # window opened and what it holds, off the same rows the line just drew.
    expect(page.locator(".lf-live")).to_contain_text("Shift+t Threads panel")
    expect(page.locator(".lf-live")).to_contain_text("h hyperlinks")
    expect(page.locator(".lf-live")).not_to_contain_text("1–2 hyperlinks")

    # A panel mnemonic completes the chord and leaves the reader inside that panel, where
    # its own scoped keys are immediately available.
    expect(page.locator(".lf-panel")).not_to_be_visible()
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-panel")).to_be_visible()
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)
    expect(page.locator(f'.lf-thread[data-id="{c1}"] textarea')).to_have_attribute(
        "placeholder", "Reply"
    )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).not_to_be_visible()
    assert page.evaluate("() => document.activeElement === document.body")

    # The Asks chord follows the same contract: show the panel and land on its first row.
    page.keyboard.press("g")
    page.keyboard.press("Shift+a")
    expect(page.locator(".lf-decisions-panel")).to_be_visible()
    expect(page.locator(".lf-decisions-row").first).to_be_focused()
    # A row is the reader standing at the ask it names, so the banner's count says
    # which of how many from the tray as it does from the page.
    expect(page.locator(".lf-decisions")).to_have_text("Asks 0/1")
    expect(page.locator(CHIPS)).to_have_count(0)

    # A direct destination also remembers the workspace it displaced. Threads replaces
    # Asks while it stands; one Escape restores both that tray and its exact focused row.
    ask = page.locator(".lf-decisions-row").first
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-panel")).to_be_visible()
    expect(page.locator(".lf-decisions-panel")).not_to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).not_to_be_visible()
    expect(page.locator(".lf-decisions-panel")).to_be_visible()
    expect(ask).to_be_focused()

    # Page map has its own close step, but that does not waive the same workspace
    # contract: leaving it restores the Asks row it stood over. Its door is the one that
    # can forget, because a dialog delivers `close` in a task of its own — a frame after
    # the dispatcher has already put the reader back — so the door's own return route has
    # to stand down for the press that is unwinding it.
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    sheet = page.get_by_role("dialog", name="Page map", exact=True)
    expect(sheet).to_be_visible()
    expect(
        sheet.get_by_role("searchbox", name="Find a Button or location in Page map")
    ).to_be_focused()
    page.evaluate(
        """() => {
          window.__lfPageMapClosed = false;
          document.querySelector('dialog.lf-page-map-sheet').addEventListener(
            'close',
            () => { window.__lfPageMapClosed = true; },
            {once: true},
          );
        }"""
    )
    page.keyboard.press("Escape")
    page.wait_for_function("() => window.__lfPageMapClosed")
    expect(page.locator(".lf-decisions-panel")).to_be_visible()
    expect(ask).to_be_focused()

    page.keyboard.press("?")
    page.keyboard.press("?")
    asks_help = page.locator(".lf-help-section").filter(
        has=page.get_by_role("heading", name="In the Asks tray", exact=True)
    )
    expect(asks_help.get_by_text("Previous ask", exact=True)).to_have_count(1)
    expect(asks_help.get_by_text("Next ask", exact=True)).to_have_count(1)
    expect(asks_help).not_to_contain_text(re.compile(r"decision", re.IGNORECASE))
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-decisions-panel")).not_to_be_visible()

    # Uppercase M opens the complete Page map rather than the numbered prefix.
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    sheet = page.get_by_role("dialog", name="Page map", exact=True)
    expect(sheet).to_be_visible()
    expect(sheet.locator(".lf-page-map-group")).to_have_count(3)
    expect(
        sheet.get_by_role("searchbox", name="Find a Button or location in Page map")
    ).to_be_focused()
    page.keyboard.press("Escape")

    # Lowercase m continues to the page's numbered location addresses. An information
    # location opens the same thread preview as its marker.
    page.keyboard.press("g")
    page.keyboard.press("m")
    expect_address_steps(page, [["g", "m", "1"], ["g", "m", "2"], ["g", "m", "3"]])
    page.keyboard.press("1")
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(page.locator(".lf-margin-thread textarea").first).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-margin-preview")).to_be_hidden()
    page.keyboard.press("Escape")

    # The hyperlinks, from the head of the page where both are on screen. A chip is hung on the
    # corner a member starts at, which for an inline that wraps is the corner of its first
    # line and not of its bounding box — those run the width of the column, so a digit
    # placed there sits a line above the words it addresses, over somebody else's sentence.
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    page.keyboard.press("g")
    page.keyboard.press("h")
    expect_address_steps(page, [["g", "h", "1"], ["g", "h", "2"]])
    assert page.evaluate(
        """() => {
             const links = [...document.querySelectorAll('#refs a[href]')];
             const chips = [...document.querySelectorAll('.lf-addresses > .lf-address')];
             return {wrapped: links[0].getClientRects().length > 1,
                     on: chips.map((chip, i) => {
                       const c = chip.getBoundingClientRect();
                       const first = links[i].getClientRects()[0];
                       return Math.abs(c.left + c.width / 2 - first.left) < 2
                           && Math.abs(c.bottom - first.top) < 2;
                     })};
           }"""
    ) == {
        "wrapped": True,
        "on": [True, True],
    }, "a chip is not on the corner its link starts at"
    # Two rungs down, because two presses built this window: the letter, then the
    # window itself. test_escape_gives_the_chord_back_one_press_at_a_time owns that.
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")

    # And from the foot of the page, where neither of them can be seen.
    # A list is the document's and not the window's, so an address means the same link at
    # every scroll position and holds where no chip can be drawn for it — counted what is
    # in the window, `g h 2` would name a different link each time the reader moved, and
    # the line would go stale about which digits are live every time the page scrolled.
    # Completing the address clicks the link. Its authored handler prevents navigation,
    # so observing that handler distinguishes activation from assigning the href while the
    # off-screen setup still proves the address names the whole document rather than the
    # current window.
    page.evaluate(
        """() => {
          window.addressedClicks = 0;
          document.querySelector('#lk2').addEventListener('click', event => {
            event.preventDefault();
            window.addressedClicks += 1;
          }, {once: true});
        }"""
    )
    page.evaluate(
        "() => document.scrollingElement.scrollTo(0, document.scrollingElement.scrollHeight)"
    )
    page.keyboard.press("g")
    link_route = line.locator(
        '.lf-key[data-lf-commands~="navigation.link"] > .lf-key-sequence'
    )
    expect(link_route.locator(":scope > kbd")).to_have_text(["g", "h", "1–2"])
    expect(link_route.locator(":scope > kbd").nth(1)).to_have_attribute(
        "data-lf-key-state", "neutral"
    )
    page.keyboard.press("h")
    expect(link_route.locator(":scope > kbd").nth(1)).to_have_attribute(
        "data-lf-key-state", "pressed"
    )
    expect(page.locator(CHIPS)).to_have_count(0)
    page.keyboard.press("2")
    assert page.evaluate("() => window.addressedClicks") == 1
    assert "#p2" not in page.url

    # The panel folds its resolved comments into a <details> of its own, and that box is
    # the chrome's. A list is what the document holds, so it is not addressed: read of the
    # document at large, `f` would offer a digit for a fold the author never wrote
    # and the reader never sees on the page.
    events_model.append_event(d, {"kind": "resolve", "author": "user", "parent": c3})
    told(page)
    expect(page.locator("details.lf-details")).to_have_count(1)
    page.keyboard.press("g")
    fold_route = line.locator(
        '.lf-key[data-lf-commands~="navigation.fold"] > .lf-key-sequence'
    )
    expect(fold_route.locator(":scope > kbd")).to_have_text(["g", "f", "1"])
    page.keyboard.press("Escape")

    # The folds, and the one arrival that changes the page it arrives at. Every
    # other member is reached through a reveal that opens the collapsed boxes on the way;
    # here the box is the member, so that same reveal is the whole motion, and the reader
    # who wanted a section open has it open having asked once.
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    page.keyboard.press("g")
    page.keyboard.press("f")
    expect_address_steps(page, [["g", "f", "1"]])
    assert page.evaluate(
        """() => {
             const c = document.querySelector('.lf-addresses > .lf-address')
                        .getBoundingClientRect();
             const first = document.getElementById('dsc-head').getClientRects()[0];
             return Math.abs(c.left + c.width / 2 - first.left) < 2
                 && Math.abs(c.bottom - first.top) < 2;
           }"""
    ), "the chip is not on the corner the summary starts at"
    expect(page.locator("#dsc")).not_to_have_attribute("open", "")
    page.keyboard.press("1")
    expect(page.locator("#dsc-head")).to_be_focused()
    expect(page.locator("#dsc")).to_have_attribute("open", "")

    # Standing there, the line says which way the next press goes and names every key that
    # goes that way: Space as well as Enter, where a link takes Enter alone and Space under
    # one is the page's own scroll, and the one arrow with somewhere to go. Both cells are
    # read where they are painted — a word fixed at declaration could say only one of the
    # two directions, and a binding set fixed there would name an arrow that does nothing.
    # What the arrows do is the test below this one; here they are what the line offers.
    opened, shut = r"⏎ / space / ←", r"⏎ / space / →"
    expect(line).to_contain_text(re.compile(opened + r"\s*close"))
    page.keyboard.press("Enter")
    expect(page.locator("#dsc")).not_to_have_attribute("open", "")
    # Read once rather than waited for. Opening a disclosure is the one change in what the
    # next press does that no writer in the runtime reports, so the word stood at "close"
    # until a poll came past — and an assertion that retries reads a stale line as an
    # eventually right one, going green on whichever poll happens to land inside its
    # budget. The attribute watch has answered by the time the press returns or nothing
    # has.
    said = key_line(page)
    assert re.search(shut + r"\s*open", said), said
    page.keyboard.press(" ")
    expect(page.locator("#dsc")).to_have_attribute("open", "")
    said = key_line(page)
    assert re.search(opened + r"\s*close", said), said

    # The two completions that take no digit: an edge of the page is one place, so the
    # second key completes the route — G glides to the bottom, g to the top.
    foot = page.evaluate(
        "() => document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight"
    )
    assert foot > 0, "the page must scroll for an edge to be a move at all"
    page.keyboard.press("g")
    expect(line).to_contain_text("top / bottom")
    # Shift spelled out: a bare press("G") synthesizes key "G" with no shift modifier,
    # which a real keyboard cannot do, and the dispatcher rightly reads it as g.
    page.keyboard.press("Shift+G")
    page.wait_for_function(
        "foot => Math.abs(document.scrollingElement.scrollTop - foot) < 1", arg=foot
    )
    page.keyboard.press("g")
    page.keyboard.press("g")
    page.wait_for_function("() => document.scrollingElement.scrollTop === 0")

    # A panel mnemonic completes the chord directly wherever the reader is on the page.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()

    # Typing contexts are untouched: in a box, the whole chord is text.
    page.keyboard.press("t")
    page.keyboard.press("Enter")
    ta1 = page.locator(f'.lf-thread[data-id="{c1}"] textarea')
    expect(ta1).to_be_focused()
    page.keyboard.type("gc1")
    expect(ta1).to_have_value("gc1")
    expect(ta1).to_be_focused()
    assert errors == []
    page.close()


def test_the_g_chord_reaches_the_all_leaves_panel(browser, serve, live_leaf):
    """All leaves is the third panel destination and follows the same focus contract."""
    live_leaf("second", "A second leaf")
    page, errors = open_page(browser, serve(ADDRESSED_PAGE))

    page.keyboard.press("g")
    expect(page.locator(".lf-keyline")).to_contain_text("All leaves panel")
    page.keyboard.press("Shift+l")

    expect(page.locator(".lf-others-panel")).to_be_visible()
    expect(page.locator("a.lf-others-row").first).to_be_focused()
    expect(page.locator(CHIPS)).to_have_count(0)
    assert errors == []
    page.close()


def test_a_g_panel_destination_survives_a_completed_asks_tray(browser, serve):
    """An open panel remains reachable after working its last row completes it."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "One decision",
                '<h1>One decision</h1><lf-decision id="only-decision"><h2>Pick one</h2>'
                '<lf-options id="only" choose>'
                '<lf-option id="first">First</lf-option>'
                '<lf-option id="second">Second</lf-option></lf-options></lf-decision>',
            )
        ),
    )

    page.keyboard.press("g")
    page.keyboard.press("Shift+a")
    expect(page.locator("button.lf-decisions-row")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#only-decision")).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.locator("#only .lf-pick").first).to_be_focused()
    page.keyboard.press("1")
    round_trip(page)
    expect(page.locator("button.lf-decisions-row")).to_have_count(1)
    expect(page.locator(".lf-decisions-answer")).to_have_text("First")
    expect(page.locator(".lf-decisions-panel")).to_have_class(re.compile(r"\bopen\b"))

    page.keyboard.press("g")
    expect(page.locator(".lf-keyline")).to_contain_text("Asks panel")
    page.keyboard.press("Shift+a")
    expect(page.locator(".lf-decisions-row")).to_be_focused()
    assert errors == []
    page.close()


# What the key line is saying, chip by chip. The word is the chip's own trailing span —
# `keySequence` builds the keycaps into a classed element and the word is the unclassed
# one beside it — and the commands are what the row projects, so a duplicate can be
# reported as the pair of rows that made it rather than as a word said twice.
KEY_LINE_HINTS = """() => [...document.querySelectorAll('.lf-keyline .lf-key')]
  .filter(chip => !chip.hidden)
  .map(chip => ({
    commands: chip.dataset.lfCommands,
    word: [...chip.children].filter(c => !c.className).map(c => c.textContent).join(''),
  }))"""


def test_no_two_hints_on_the_key_line_say_the_same_word(browser, serve):
    """The line is a row of words with keycaps over them, and the word is what is read.

    Two rows sharing one leaves the keycaps to carry the whole difference, which is the
    line failing at the one thing it is for. The versions menu once called both Tab
    directions "leave versions"; a keyboard-opened menu now has its precise Escape return
    beside the remaining directional handoff. The page's `c` says "comment on the page",
    distinct from the t/T thread walk.

    Both scenes are read, and each is asserted to hold the rows at issue first: a line
    that had stopped showing them would report a clean result about a page the reader
    never sees. The words are the register's, which is where the fix goes — the line
    prints what the rows say, and inventing a difference here would be this projection
    disagreeing with the reference and the announcements.
    """
    page, errors = open_page(browser, serve(LONG_PAGE, comments=2))

    # The shelf, because the ordinary shortlist shows the first live row and little else:
    # what this is about is two words a reader can see at one time, and the shelf is where
    # the page's own scene is all of it.
    page.keyboard.press("?")
    page.evaluate(RENDERED)
    standing = page.evaluate(KEY_LINE_HINTS)
    assert {"comment.create", "thread.next thread.previous"} <= {
        hint["commands"] for hint in standing
    }, f"the line no longer offers both the comments and the thread walk: {standing}"

    # The registered return frame is nearer than the menu's native Tab handoffs, so the
    # shortlist contains the actual Escape return and one directional handoff.
    page.keyboard.press("Escape")
    open_versions(page)
    page.evaluate(RENDERED)
    versions = page.evaluate(KEY_LINE_HINTS)
    assert {"navigation.return", "version.leave-forward"} <= {
        hint["commands"] for hint in versions
    }, f"the versions menu no longer offers its two visible ways out: {versions}"

    for scene, hints in (("the page", standing), ("the versions menu", versions)):
        said = {}
        for hint in hints:
            said.setdefault(hint["word"], []).append(hint["commands"])
        twice = {word: rows for word, rows in said.items() if len(rows) > 1}
        assert not twice, (
            f"on {scene} the key line says one word for two capabilities, so the "
            f"keycaps are the whole difference: {twice}"
        )
    assert errors == []
    page.close()


def test_a_completed_asks_tray_keeps_the_answer_visible(browser, serve):
    """Finishing a page preserves the tray's route back through the answer."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "One decision",
                '<h1>One decision</h1><lf-decision id="only-decision"><h2>Pick one</h2>'
                '<lf-options id="only" choose>'
                '<lf-option id="first">First</lf-option>'
                '<lf-option id="second">Second</lf-option></lf-options></lf-decision>',
            )
        ),
    )
    page.keyboard.press("g")
    page.keyboard.press("Shift+a")
    expect(page.locator("button.lf-decisions-row")).to_have_count(1)
    # Enter travels to the ask and Tab steps onto a mark, whose digit answers it. Tab
    # rather than the digit straight off the arrival, because where an arrival lands is
    # not this test's subject and it should not go red when that moves.
    page.keyboard.press("Enter")
    page.keyboard.press("Tab")
    page.keyboard.press("1")
    round_trip(page)
    expect(page.locator("button.lf-decisions-row")).to_have_count(1)
    expect(page.locator(".lf-decisions-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(page.locator(".lf-decisions-answer")).to_have_text("First")
    assert errors == []
    page.close()


def test_an_asks_tray_says_when_a_revision_removes_its_last_ask(browser, serve):
    """An empty inventory says the tray rendered, rather than looking broken."""
    source = leaf_page(
        "One decision",
        '<h1>One decision</h1><lf-decision id="only-decision"><h2>Pick one</h2>'
        '<lf-options id="only" choose>'
        '<lf-option id="first">First</lf-option>'
        '<lf-option id="second">Second</lf-option></lf-options></lf-decision>',
    )
    url = serve(source)
    page, errors = open_page(browser, live_url(url))
    page.keyboard.press("g")
    page.keyboard.press("Shift+a")
    expect(page.locator("button.lf-decisions-row")).to_have_count(1)
    note = page.locator(".lf-decisions-panel .lf-empty")
    expect(note).to_have_count(0)

    stamp_page(
        serve.page_dir,
        leaf_page("No decisions", "<h1>No decisions remain</h1>"),
        "remove the last ask",
    )
    wait_for_revision(page, 2)
    expect(page.locator("button.lf-decisions-row")).to_have_count(0)
    expect(page.locator(".lf-decisions-panel")).to_have_class(re.compile(r"\bopen\b"))
    expect(note).to_be_visible()
    expect(note).to_contain_text("Nothing is waiting on you")
    assert errors == []
    page.close()


def test_the_g_chord_opens_an_empty_page_map(browser, serve):
    """A destination with no locations still shows that the command worked."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "Empty page map", "<h1>Empty page map</h1><p>No activity yet.</p>"
            )
        ),
    )

    expect(page.locator(".lf-page-map-action")).to_have_count(0)
    page.keyboard.press("g")
    expect(page.locator(".lf-keyline")).to_contain_text("Page map")
    page.keyboard.press("Shift+m")

    sheet = page.locator(".lf-page-map-sheet")
    expect(sheet).to_be_visible()
    expect(
        sheet.get_by_role("searchbox", name="Find a Button or location in Page map")
    ).to_be_focused()
    expect(sheet).to_contain_text("No Buttons or locations yet")
    expect(sheet.locator(".lf-page-map-action")).to_have_count(0)
    assert errors == []
    page.close()


def test_numbered_addresses_show_progress_on_complete_routes_without_moving(
    browser, serve
):
    """Each inline hint and key-line binding keeps one complete chord in one geometry.

    A press changes the completed key's face from beige to blue. It does not remove that
    key or move the remaining keycaps while the chord narrows to one numbered list."""
    url = serve(ADDRESSED_PAGE)
    page, errors = open_page(browser, url)
    resized(page, 1280, 800)

    page.keyboard.press("g")
    legend = page.locator(
        '.lf-keyline .lf-key[data-lf-commands~="navigation.link"] > .lf-key-sequence'
    )
    expect(legend.locator(":scope > kbd")).to_have_text(["g", "h", "1–2"])
    assert legend.locator(":scope > kbd").evaluate_all(
        "keys => keys.map(key => key.dataset.lfKeyState)"
    ) == ["pressed", "neutral", "neutral"]
    expect_address_steps(
        page,
        [["g", "m", "1"], ["g", "h", "1"], ["g", "h", "2"], ["g", "f", "1"]],
    )
    assert (
        page.locator(f"{CHIPS} kbd").evaluate_all(
            "keys => keys.map(key => key.dataset.lfKeyState)"
        )
        == ["pressed", "neutral", "neutral"] * 4
    )

    def sequence_geometry(locator):
        return locator.evaluate(
            """sequence => {
              const box = sequence.getBoundingClientRect();
              return {
                width: box.width,
                height: box.height,
                keys: [...sequence.querySelectorAll(':scope > kbd')].map(key => {
                  const at = key.getBoundingClientRect();
                  return {left: at.left - box.left, width: at.width, height: at.height};
                }),
              };
            }"""
        )

    def link_geometry():
        return page.locator(CHIPS).evaluate_all(
            """chips => chips.filter(chip => {
                const keys = [...chip.querySelectorAll('kbd')].map(key => key.textContent);
                return keys[0] === 'g' && keys[1] === 'h';
              })
              .map(chip => {
                const box = chip.getBoundingClientRect();
                return {
                  text: chip.textContent,
                  left: box.left,
                  top: box.top,
                  width: box.width,
                  height: box.height,
                  keys: [...chip.querySelectorAll('kbd')].map(key => {
                    const at = key.getBoundingClientRect();
                    return {left: at.left - box.left, width: at.width, height: at.height};
                  }),
                };
              })"""
        )

    initial_legend_geometry = sequence_geometry(legend)
    initial_link_geometry = link_geometry()
    assert len(initial_link_geometry) == 2

    page.keyboard.press("h")
    expect_address_steps(page, [["g", "h", "1"], ["g", "h", "2"]])
    expect(legend.locator(":scope > kbd")).to_have_text(["g", "h", "1–2"])
    expect(legend.locator(":scope > kbd").nth(1)).to_have_attribute(
        "data-lf-key-state", "pressed"
    )
    assert legend.locator(":scope > kbd").evaluate_all(
        "keys => keys.map(key => key.dataset.lfKeyState)"
    ) == ["pressed", "pressed", "neutral"]
    assert (
        page.locator(f"{CHIPS} kbd").evaluate_all(
            "keys => keys.map(key => key.dataset.lfKeyState)"
        )
        == ["pressed", "pressed", "neutral"] * 2
    )
    assert sequence_geometry(legend) == initial_legend_geometry, (
        "the key-line chord moved its keys when h became pressed"
    )
    assert link_geometry() == initial_link_geometry, (
        "the inline chords moved when h became pressed"
    )
    inline = page.locator(f"{CHIPS} .lf-key-sequence > kbd").last
    pending_legend = legend.locator(":scope > kbd").last
    expect(inline).to_have_attribute("data-lf-key-state", "neutral")
    expect(pending_legend).to_have_attribute("data-lf-key-state", "neutral")
    assert page.evaluate(
        """() => {
          const inline = [...document.querySelectorAll(
            '.lf-addresses > .lf-address kbd')].at(-1);
          const legend = document.querySelector(
            '.lf-keyline .lf-key[data-lf-commands~="navigation.link"]'
            + ' > .lf-key-sequence > kbd:last-child');
          const properties = ['border-top-color', 'background-color', 'color',
            'font-family', 'font-size', 'height', 'border-radius'];
          const read = el => Object.fromEntries(properties.map(property =>
            [property, getComputedStyle(el).getPropertyValue(property)]));
          return JSON.stringify(read(inline)) === JSON.stringify(read(legend));
        }"""
    ), "an inline pending key and its bottom-legend binding use different beige faces"
    assert errors == []
    page.close()


def test_only_controls_and_boxes_with_something_out_of_sight_take_a_tab_stop(
    browser, serve
):
    """Anything a mouse can scroll a keyboard has to reach, and the reference is a list
    long enough to scroll — but its rows carry no control, so nothing put the reader in it
    and they could read the first screenful of the key reference and no more.

    The sweep that fixes that asks the box whether it may scroll, and the theme says every
    table may (`table { display: block; overflow-x: auto }`). So pointing it at the
    reference tagged all fourteen of its tables, none of which overflows: leaving the
    reference by Tab went from its native controls to fifteen extra stops, each wearing
    the browser's own ring rather than the layer's. A rule saying a box *could* scroll is
    not the same fact as a box that *has* something out of sight, and only the second is
    somewhere a reader needs to be able to stand.

    Asserted as the whole set rather than a count, because the count was right before and
    the members were wrong: every stop in the overlay has to be a control the reference
    offers or a box that really scrolls."""
    page, errors = open_page(browser, serve(CONTROL_LABEL_PAGE))
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_be_visible()

    stops = page.evaluate(
        """() => [...document.querySelector('.lf-help').querySelectorAll('*')]
                 .filter(e => e.tabIndex >= 0)
                 .map(e => ({
                    tag: e.tagName,
                    scrolls: e.scrollWidth > e.clientWidth
                          || e.scrollHeight > e.clientHeight,
                 }))"""
    )
    assert stops, "the reference offers no tab stop at all, not even its search box"
    controls = {"BUTTON", "INPUT"}
    dead = [s for s in stops if s["tag"] not in controls and not s["scrolls"]]
    assert dead == [], f"tab stops on boxes with nothing out of sight: {dead}"
    assert [s["tag"] for s in stops if s["tag"] in controls] == [
        "BUTTON",
        "INPUT",
        "BUTTON",
        "BUTTON",
    ]

    # And the box that does have something out of sight is one of those stops, which is
    # the whole point of the sweep. Its reachability is what is asserted here and not the
    # scroll itself: the headless shell does not move a focused div for an arrow or a
    # PageDown where Chrome does, so a motion assertion would be measuring the harness.
    # What this can say, and what the defect was, is that the box overflows and that a
    # reader can be put on it.
    results = page.locator(".lf-help-results")
    assert page.evaluate(
        "() => { const r = document.querySelector('.lf-help-results');"
        "        return r.scrollHeight > r.clientHeight; }"
    ), (
        "this reference fits its box, so it proves nothing about reaching one that does not"
    )
    results.focus()
    expect(results).to_be_focused()
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_the_reference_keeps_its_complete_keyboard_layer(browser, serve):
    """The reference has a visible close control and keeps Tab inside the surface.

    It claims the keyboard while open, so letting native Tab fall through to the page
    behind it makes the visible scope and the focus scope disagree. Forward and reverse
    Tab use the same registered walk, while Escape closes and restores the opener."""
    page, errors = open_page(browser, serve(CONTROL_LABEL_PAGE))
    opener = page.get_by_role("button", name="? more", exact=True)
    opener.click()
    opener = page.get_by_role("button", name="? all shortcuts", exact=True)
    opener.click()
    help_el = page.locator(".lf-help")
    close = page.get_by_role("button", name="Back to more shortcuts")
    expect(close).to_be_visible()

    seen = set()
    for _ in range(6):
        page.keyboard.press("Tab")
        active = page.evaluate(
            """() => {
              const e = document.activeElement;
              return {inside: document.querySelector('.lf-help').contains(e),
                      name: e.getAttribute('aria-label') || e.className || e.tagName};
            }"""
        )
        assert active["inside"], f"Tab left the keyboard reference for {active['name']}"
        seen.add(active["name"])
    assert "Back to more shortcuts" in seen, seen

    page.keyboard.press("Shift+Tab")
    assert page.evaluate(
        "() => document.querySelector('.lf-help').contains(document.activeElement)"
    )
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()
    expect(opener).to_be_focused()

    # The native modal makes the page behind it inert. Its reachable light-dismiss gesture
    # is the backdrop, which closes the reference and returns to the door rather than
    # pretending a page control can be pressed through the modal layer.
    opener.click()
    page.mouse.click(2, 2)
    expect(help_el).to_be_hidden()
    expect(opener).to_be_focused()
    assert errors == []
    page.close()


def test_the_reference_runs_available_commands_and_explains_the_rest(browser, serve):
    """The reference is the command register made usable, not a second list of prose.

    Search narrows that register, arrows choose a result, and Enter runs it through the
    same scoped command route as its key. A command outside the reader's current scope
    stays selectable, but explains the scope it needs instead of closing and doing
    nothing. Stable command IDs are exposed on the results so words can change without
    breaking this route or tooling built on it."""
    page, errors = open_page(browser, serve(NOTED_PAGE, comments=2))
    help_el = page.locator(".lf-help")
    search = page.get_by_role("combobox", name="Search keyboard shortcuts")

    page.keyboard.press("?")
    page.keyboard.press("?")
    commands = help_el.locator(".lf-help-command:visible")
    assert commands.count() > 1, "the command grid has no pair of rows to walk"
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(commands.first).to_have_attribute("data-lf-selected", "true")
    first_row = commands.first.locator("xpath=ancestor::tr")
    expect(search).to_have_attribute(
        "aria-activedescendant", first_row.get_attribute("id")
    )
    page.keyboard.press("ArrowUp")
    expect(commands.first).to_have_attribute("data-lf-selected", "true")

    page.keyboard.press("Escape")
    page.keyboard.press("?")
    commands = help_el.locator(".lf-help-command:visible")
    page.keyboard.press("ArrowUp")
    expect(search).to_be_focused()
    expect(commands.last).to_have_attribute("data-lf-selected", "true")
    last_row = commands.last.locator("xpath=ancestor::tr")
    expect(search).to_have_attribute(
        "aria-activedescendant", last_row.get_attribute("id")
    )
    page.keyboard.press("ArrowDown")
    expect(commands.last).to_have_attribute("data-lf-selected", "true")

    search.fill("resolve it")
    result = help_el.locator(
        '.lf-help-command[data-lf-command="thread.resolution.toggle"]'
    )
    expect(result).to_have_count(1)
    expect(result).to_have_attribute("data-lf-command", "thread.resolution.toggle")
    expect(search).to_have_attribute("aria-haspopup", "grid")
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(result).to_have_attribute("data-lf-selected", "true")
    expect(result.locator("xpath=ancestor::tr")).to_have_attribute(
        "aria-selected", "true"
    )
    page.keyboard.type("!")
    expect(search).to_have_value("resolve it!")
    expect(help_el.locator(".lf-help-empty")).to_be_visible()
    page.keyboard.press("Backspace")
    page.keyboard.press("ArrowDown")
    expect(result).to_have_attribute("data-lf-selected", "true")
    page.keyboard.press("Enter")
    expect(help_el).to_be_visible()
    expect(help_el.locator(".lf-help-meta")).to_have_text(
        "Available on a focused thread"
    )
    search.fill("close response choices")
    cancel_reaction = help_el.locator(
        '.lf-help-command[data-lf-command="reaction.cancel"]'
    )
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(cancel_reaction).to_have_attribute("data-lf-selected", "true")
    page.keyboard.press("Enter")
    expect(help_el.locator(".lf-help-meta")).to_have_text(
        "Available with response choices open"
    )

    page.keyboard.press("Escape")
    page.keyboard.press("?")
    search.fill("previous open thread")
    previous = help_el.locator('.lf-help-command[data-lf-command="thread.previous"]')
    expect(previous).to_have_count(1)
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(previous).to_have_attribute("data-lf-selected", "true")
    page.keyboard.press("Enter")
    thread = page.locator(".lf-thread").last
    expect(thread).to_be_focused()
    page.keyboard.press("?")
    page.keyboard.press("?")
    search.fill("resolve it")
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(result).to_have_attribute("data-lf-selected", "true")
    page.keyboard.press("Enter")
    expect(help_el).to_be_hidden()
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    assert errors == []
    page.close()


def test_the_reference_runs_the_exact_numbered_ask_action(browser, serve):
    """Each Ask digit is a distinct command when invoked without a keydown."""
    page, errors = open_page(browser, serve(DECISIONS_PAGE))

    page.keyboard.press("a")
    page.keyboard.press("?")
    page.keyboard.press("?")

    first = page.locator('.lf-help-command[data-lf-command="decision.activate-1"]')
    second = page.locator('.lf-help-command[data-lf-command="decision.activate-2"]')
    expect(first).to_have_text("Activate the “Keep the store” action")
    expect(second).to_have_text("Activate the “Signed tokens” action")
    expect(
        page.locator('.lf-help-command[data-lf-command="decision.activate-nth"]')
    ).to_have_count(0)

    second.click()
    expect(page.locator("#lq-token")).to_have_attribute("chosen", "")
    expect(page.locator("#lq-keep")).not_to_have_attribute("chosen", "")
    round_trip(page)

    assert errors == []
    page.close()


def test_numbered_ask_routes_follow_replaced_controls(browser, serve):
    """A widget can replace its action controls without defining another keymap."""
    page, errors = open_page(
        browser,
        serve(
            leaf_page(
                "draft ask",
                """
<h1 id="h">Release note</h1>
<lf-decision id="note-decision"><h2>How should the note read?</h2>
  <lf-draft id="note" needed><pre>Keep this text editable.</pre></lf-draft>
</lf-decision>
""",
            )
        ),
    )

    page.keyboard.press("a")
    expect(page.locator("#note-decision")).to_be_focused()
    assert "1\nEdit" in key_line(page)

    page.keyboard.press("?")
    page.keyboard.press("?")
    edit = page.locator('.lf-help-command[data-lf-command="decision.activate-1"]')
    expect(edit).to_have_text("Activate the “Edit…” action")
    edit.click()
    expect(page.locator("#note textarea")).to_be_focused()

    save = page.locator(".lf-draft-controls [data-lf-button-key='save']")
    save.focus()
    expect(save).to_be_focused()
    page.keyboard.press("?")
    assert "1–2\nSave / Cancel" in key_line(page)
    page.keyboard.press("?")
    cancel = page.locator('.lf-help-command[data-lf-command="decision.activate-2"]')
    expect(cancel).to_have_text("Activate the “Cancel” action")
    cancel.click()
    expect(page.locator("#note textarea")).to_have_count(0)

    assert errors == []
    page.close()


def test_registered_shortcuts_are_exposed_to_assistive_technology(browser, serve):
    """The same declarations that paint help expose their active keys through ARIA."""
    page, errors = open_page(browser, serve(DECISIONS_PAGE))

    expect(page.get_by_role("button", name="? more", exact=True)).to_have_attribute(
        "aria-keyshortcuts", "?"
    )
    expect(page.locator(".lf-general textarea")).to_have_attribute(
        "aria-keyshortcuts", "Meta+Enter Control+Enter"
    )
    assert page.locator(".lf-version-menu").get_attribute("aria-keyshortcuts") is None

    page.keyboard.press("a")
    mark = page.locator("#live-question .lf-pick").first
    expect(mark).to_have_attribute("aria-keyshortcuts", "ArrowUp ArrowDown Space 1")

    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(mark).to_have_attribute("aria-keyshortcuts", "ArrowUp ArrowDown Space")
    expect(
        page.locator(
            ".lf-help tr", has_text="Next ask this page is waiting on you for"
        ).locator("kbd")
    ).to_have_text("a")
    expect(
        page.locator(
            ".lf-help tr", has_text="Previous ask this page is waiting on you for"
        ).locator("kbd")
    ).to_have_text("A")
    page.keyboard.press("Escape")

    assert page.locator(".lf-decisions").get_attribute("aria-keyshortcuts") is None
    page.locator(".lf-decisions").click()
    expect(page.locator(".lf-decisions-panel")).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown"
    )
    expect(page.locator(".lf-decisions-row").first).to_have_attribute(
        "aria-keyshortcuts", "Enter Space"
    )
    page.keyboard.press("Escape")

    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.get_by_role("button", name="Back to more shortcuts")).to_have_attribute(
        "aria-keyshortcuts", "Escape"
    )
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_the_reference_reads_the_same_way_twice(browser, serve):
    """A widget registers its scope at upgrade, and the set the reference walks is
    insertion-ordered, so the sections came out in whatever order the modules happened to
    finish in. The same build read twice put "On a tab" above "On a card grip" once and
    below it the next time. A reference whose headings move between loads is one a reader
    cannot learn the shape of, and any assertion on it flakes rather than fails — which is
    how it was found, a reviewer taking a reordering for fallout from an unrelated change.

    So the widgets' sections read in the order the page holds them. Asserted twice over:
    the same page loaded twice gives the same list, and that list is the document's own
    order rather than any order at all — a stable-but-wrong order would pass the first
    check alone."""
    url = serve(CONTROL_LABEL_PAGE)
    seen = []
    for _ in range(2):
        page, errors = open_page(browser, url)
        page.keyboard.press("?")
        page.keyboard.press("?")
        expect(page.locator(".lf-help")).to_be_visible()
        seen.append(
            page.evaluate(
                "() => [...document.querySelectorAll('.lf-help h3')].map(h => h.textContent)"
            )
        )
        assert errors == []
        page.close()

    assert seen[0] == seen[1], f"the reference reordered between loads: {seen}"
    assert "On a tab" in seen[0], seen[0]


def test_a_widget_that_renames_its_role_keeps_the_press_offer_gave_it(browser, serve):
    """A tab is built by `offer("button", …)` and then wears `role="tab"`, because that is
    what its strip is. The press it keeps is the strip's own row, declared beside the
    arrows and Home/End that walk it, and it is the only thing that consumes Space —
    which is otherwise the page's scroll.

    That row is what a page-wide control scope used to supply, and the scope was the wrong
    place for it: read off the role it stopped seeing tabs, so Enter did nothing and Space
    threw the reader down the page from a control that looked like it had answered; read
    off the tabindex it claimed every focus target `offer` builds and led with a press over
    a conversation thread that answers nothing. Declared where the strip is, the press
    cannot be lost to a rename or promised where nothing runs it, and the word on the line
    is the strip's own — it names the tab rather than the control.

    Asserted from the state where the press is the only way back: the tab strip is walked
    with arrows, so a focused tab is usually the selected one. Revealing the *other* panel
    leaves focus on a tab that is not selected, which is exactly when Enter has work to
    do."""
    page, errors = open_page(browser, serve(CONTROL_LABEL_PAGE))
    tabs = page.locator("#projects .lf-tab-btn")
    expect(tabs).to_have_count(2)

    tabs.first.focus()
    # Reveal the second panel without moving focus, so the focused tab is not the selected
    # one and Enter has something to do.
    page.evaluate(
        """() => document.querySelector('#tab-bath')
                 .dispatchEvent(new CustomEvent('lf-reveal',
                   {bubbles: true, detail: {target: document.querySelector('#tab-bath')}}))"""
    )
    expect(tabs.first).to_be_focused()
    expect(tabs.nth(1)).to_have_attribute("aria-selected", "true")

    # The line names the press, and the press re-selects the tab the reader is standing on.
    expect(page.locator(".lf-keyline")).to_contain_text("open the tab")
    page.keyboard.press("Enter")
    expect(tabs.first).to_have_attribute("aria-selected", "true")

    # And Space is consumed rather than scrolling the page out from under the press.
    page.evaluate("() => document.querySelector('#tab-bath').click()")
    tabs.first.focus()
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press(" ")
    expect(tabs.first).to_have_attribute("aria-selected", "true")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before, (
        "Space scrolled the page instead of working the control it was promised on"
    )
    assert errors == []
    page.close()


def test_the_g_chord_selects_a_numbered_tab(browser, serve):
    """A tab can be selected from elsewhere on the page through its numbered address.

    Arrow keys serve a reader already standing in the tab strip. The page-level route
    names every tab in document order, then selects and focuses the requested one so its
    local keyboard pattern is immediately available."""
    page, errors = open_page(browser, serve(CONTROL_LABEL_PAGE))
    tabs = page.locator("#projects .lf-tab-btn")
    expect(tabs).to_have_count(2)
    expect(tabs.first).to_have_attribute("aria-selected", "true")

    page.keyboard.press("g")
    page.keyboard.press("t")
    page.keyboard.press("2")

    expect(tabs.nth(1)).to_have_attribute("aria-selected", "true")
    expect(tabs.nth(1)).to_be_focused()
    expect(page.locator("#tab-bath")).not_to_have_attribute("hidden", re.compile(".*"))
    expect(page.locator("#tab-feeders")).to_have_attribute("hidden", re.compile(".*"))
    assert errors == []
    page.close()


def test_numbered_addresses_stop_at_nine_and_choose_in_one_press(browser, serve):
    """A numbered list has nine immediate choices even when the page holds more.

    The cap keeps every address one digit long: `g`, then `h`, then `1` is never ambiguous,
    and the tenth document member does not acquire a hidden multi-key route that the
    shown `1–9` range fails to name."""
    links = "".join(
        f'<li><a id="link-{n}" href="#link-{n}">link {n}</a></li>' for n in range(1, 13)
    )
    lead = "".join(f"<p>Context before the links, line {n}.</p>" for n in range(16))
    tail = "".join(f"<p>Context after the links, line {n}.</p>" for n in range(16))
    page, errors = open_page(
        browser, serve(leaf_page("Twelve links", f"{lead}<ol>{links}</ol>{tail}"))
    )
    page.emulate_media(reduced_motion="reduce")
    line = page.locator(".lf-keyline")
    page.locator("#link-1").scroll_into_view_if_needed()
    page.evaluate(
        """() => {
          const link = document.querySelector('#link-1').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          document.scrollingElement.scrollBy(0, link.top - banner.bottom - 96);
        }"""
    )

    page.keyboard.press("g")
    route = line.locator(
        '.lf-key[data-lf-commands~="navigation.link"] > .lf-key-sequence'
    )
    expect(route.locator(":scope > kbd")).to_have_text(["g", "h", "1–9"])
    expect(route.locator(":scope > kbd").nth(1)).to_have_attribute(
        "data-lf-key-state", "neutral"
    )
    expect_address_steps(page, [["g", "h", str(n)] for n in range(1, 10)])
    page.keyboard.press("h")
    expect(route.locator(":scope > kbd").nth(1)).to_have_attribute(
        "data-lf-key-state", "pressed"
    )
    expect(line).not_to_contain_text(re.compile(r"1–12\s*hyperlinks"))
    expect_address_steps(page, [["g", "h", str(n)] for n in range(1, 10)])
    page.keyboard.press("1")
    page.wait_for_url(re.compile(r"#link-1$"))
    expect(page.locator(CHIPS)).to_have_count(0)

    page.keyboard.press("g")
    page.keyboard.press("h")
    page.keyboard.press("9")
    page.wait_for_url(re.compile(r"#link-9$"))
    revealed = page.locator("#link-9").bounding_box()
    assert revealed is not None
    assert revealed["y"] + revealed["height"] <= page.viewport_size["height"]

    # There is no decimal continuation: 1 completes at the first member, and a later 0
    # is just an unrelated key rather than an address for member 10.
    page.keyboard.press("g")
    page.keyboard.press("h")
    page.keyboard.press("1")
    page.wait_for_url(re.compile(r"#link-1$"))
    page.keyboard.press("0")
    assert page.url.endswith("#link-1")
    assert errors == []
    page.close()


def test_escape_gives_the_chord_back_one_press_at_a_time(browser, serve):
    """The keyboard is a stack and the address chord is two presses of it: `g` opens
    the list menu, and the letter names one list and narrows the hints to its digits. Esc
    gives the letter back and the next Esc closes the window.

    It spent both on one press, which put a reader who had narrowed to the wrong list
    back on the page — pressing `g` again to reach a window that had been standing the
    whole time. Complete routes stay in place while their pressed keys make the two stages
    visible. Direct panel destinations complete on their mnemonic and therefore add no
    intermediate Escape rung."""
    page, errors = open_page(browser, serve(ADDRESSED_PAGE))
    line = page.locator(".lf-keyline")

    page.keyboard.press("g")
    link_route = line.locator(
        '.lf-key[data-lf-commands~="navigation.link"] > .lf-key-sequence'
    )
    expect(link_route.locator(":scope > kbd")).to_have_text(["g", "h", "1–2"])
    assert link_route.locator(":scope > kbd").evaluate_all(
        "keys => keys.map(key => key.dataset.lfKeyState)"
    ) == ["pressed", "neutral", "neutral"]
    expect_address_steps(
        page,
        [["g", "m", "1"], ["g", "h", "1"], ["g", "h", "2"], ["g", "f", "1"]],
    )
    expect(line).to_contain_text("cancel")
    expect(line.locator('[data-lf-commands="navigation.address.back"]')).to_have_class(
        re.compile(r"\blf-chord-control\b")
    )

    # The letter narrows the window to its own list, which is the second layer.
    page.keyboard.press("h")
    expect_address_steps(page, [["g", "h", "1"], ["g", "h", "2"]])
    expect(link_route.locator(":scope > kbd").nth(1)).to_have_attribute(
        "data-lf-key-state", "pressed"
    )
    assert link_route.locator(":scope > kbd").evaluate_all(
        "keys => keys.map(key => key.dataset.lfKeyState)"
    ) == ["pressed", "pressed", "neutral"]
    expect(line).to_contain_text("back to the lists")

    # One press gives that back and no more: the window still stands, over every list.
    page.keyboard.press("Escape")
    expect_address_steps(
        page,
        [["g", "m", "1"], ["g", "h", "1"], ["g", "h", "2"], ["g", "f", "1"]],
    )
    assert link_route.locator(":scope > kbd").evaluate_all(
        "keys => keys.map(key => key.dataset.lfKeyState)"
    ) == ["pressed", "neutral", "neutral"]
    expect(line).to_contain_text("cancel")
    # And a letter still names one, so what came back is the window and not its ghost.
    page.keyboard.press("h")
    expect_address_steps(page, [["g", "h", "1"], ["g", "h", "2"]])

    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(CHIPS)).to_have_count(0)
    expect(line).not_to_contain_text("cancel")
    expect(page.locator(".lf-live")).to_have_text("Go to cancelled")
    assert errors == []
    page.close()


def test_the_arrows_say_which_way_the_section_under_the_reader_goes(browser, serve):
    """⏎ and space toggle a disclosure; → opens it and ← closes it. A direction and not a
    second toggle, which is the whole of what they add: → over a section already open
    leaves it open, where a toggle would have shut it. Only the direction with somewhere
    to go is bound, so the line names ← over an open section and → over a shut one and
    every key it names is a key that works — and each press that must change nothing
    follows one that changed something, since a box nobody has touched passes that
    assertion however dead the scope is.

    Both spellings of a folded section, because a reader standing on one cannot see which
    it is: the platform's <details>, and a settled option group, which is a span the
    widget wrote `aria-expanded` onto. One scope answers for both, and the press goes
    through the element's own click either way, so the keyboard leaves the page in the
    state the pointer would have left it in.

    The word follows either spelling within the press, not within the poll. Neither
    reports itself — an aria-expanded write fires no event at all — so what the line says
    about the key under the reader's finger rests on the attribute watch rather than on
    the two-second poll behind it. Both readings of it are taken once, through
    `key_line`: an assertion that retries cannot tell the watch from a poll that lands
    inside its budget, and the first version of this test went green with the watch
    broken.

    Shift+← is the last thing this holds to: a summary's words are the page's, and
    extending a selection through them must not shut the section they are in."""
    page, errors = open_page(browser, serve(DISCLOSED_PAGE))
    line = page.locator(".lf-keyline")
    opened, shut = r"⏎ / space / ←", r"⏎ / space / →"

    dsc = page.locator("#dsc")
    head = page.locator("#dsc-head")
    head.focus()
    expect(dsc).not_to_have_attribute("open", "")
    expect(line).to_contain_text(re.compile(shut + r"\s*open"))

    page.keyboard.press("ArrowRight")
    expect(dsc).to_have_attribute("open", "")
    # The press does not move the reader off what they pressed it on, so the next one
    # lands on the same section.
    expect(head).to_be_focused()
    said = key_line(page)
    assert re.search(opened + r"\s*close", said), said

    # A direction and not a toggle, which is the one thing ⏎ cannot say: this press
    # follows one that is proven live, so a scope answering nothing at all could not pass
    # it, and a toggle bound to the arrows would have shut the section here.
    page.keyboard.press("ArrowRight")
    expect(dsc).to_have_attribute("open", "")
    # Shift+← is a reader extending a selection through the summary's own words. A named
    # key asks for its modifiers exactly, so it is not this row's binding.
    page.keyboard.press("Shift+ArrowLeft")
    expect(dsc).to_have_attribute("open", "")

    page.keyboard.press("ArrowLeft")
    expect(dsc).not_to_have_attribute("open", "")
    page.keyboard.press("ArrowLeft")
    expect(dsc).not_to_have_attribute("open", "")

    # And the platform's own pair still toggles, once each: the row owns its whole binding
    # set, so the runtime makes the press the browser was going to make.
    page.keyboard.press("Enter")
    expect(dsc).to_have_attribute("open", "")
    page.keyboard.press(" ")
    expect(dsc).not_to_have_attribute("open", "")

    # The other spelling, which keeps its state in ARIA's own attribute rather than in
    # `open`, and whose press is the widget's own handler rather than the platform's.
    row = page.locator("#settled .lf-settled")
    row.focus()
    expect(row).to_have_attribute("aria-expanded", "false")
    expect(line).to_contain_text(re.compile(shut + r"\s*open"))
    page.keyboard.press("ArrowRight")
    expect(row).to_have_attribute("aria-expanded", "true")
    expect(page.locator("#st-keep")).to_be_visible()
    # Nothing reports this one at all — an aria-expanded write fires no event anywhere —
    # so read once: the word is the attribute watch's answer by the time the press
    # returns, or it is the poll's two seconds later, and only an assertion that refuses
    # to retry can tell those apart.
    said = key_line(page)
    assert re.search(opened + r"\s*close", said), said
    # The line is one of two surfaces naming this row's keys, and the other is read by
    # somebody who cannot see the first. A row whose bindings answer from its own state
    # has to repaint both when the state moves, and only the line had a watch: the
    # attribute kept whichever way the row was standing when the scope was declared, so
    # it went on promising the arrow that no longer moves this section and withholding
    # the one that does.
    #
    # Read once for the reason the line is, and by the same clock: the heartbeat repaints
    # scopes too, so a retrying assertion goes green on the tick that lands inside its
    # budget and the fix it is meant to hold has nothing to fail against.
    assert row.get_attribute("aria-keyshortcuts") == "Enter Space ArrowLeft"
    page.keyboard.press("ArrowRight")
    expect(row).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("ArrowLeft")
    expect(row).to_have_attribute("aria-expanded", "false")
    expect(page.locator("#st-keep")).to_be_hidden()
    page.evaluate(RENDERED)
    assert row.get_attribute("aria-keyshortcuts") == "Enter Space ArrowRight"

    # A disclosure in a message, where the disclosure scope does not reach: thread markup
    # is a second document beside the version, and the arrows are the page's. A diff,
    # because what is being asked is what a widget's own row names — a widget re-wording
    # this press reads its bindings from DISCLOSE, which answers for where the element
    # stands as well as which way it is standing, so the row cannot offer a key that
    # nothing there runs. The platform's pair still works it, so what differs is the
    # offer rather than the capability.
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-diff",
            "author": "claude",
            "revision": 1,
            "text": "The patch, for the record.",
            "markup": '<lf-diff id="msg-diff"><pre>'
            "diff --git a/gateway/limits.py b/gateway/limits.py\n"
            "--- a/gateway/limits.py\n"
            "+++ b/gateway/limits.py\n"
            "@@ -38,2 +38,2 @@ class Limiter:\n"
            "     def bucket_key(self, request):\n"
            "-        return request.remote_addr\n"
            "+        return request.token.id\n"
            "</pre></lf-diff>",
        },
    )
    told(page)
    # Opened, because standing somewhere is where focus is and a shut panel has nowhere to
    # stand: without this the summary took no focus, the reader was still on the page's own
    # row, and the line went on describing that one — an assertion that would have passed
    # for the wrong reason had the two been in the same state.
    page.get_by_role("button", name=re.compile("Threads")).click()
    staged = page.locator("#msg-diff summary").first
    expect(staged).to_be_visible()
    staged.focus()
    expect(staged).to_be_focused()
    # Every live row rather than the two hints that fit: the panel's own rows win the line
    # where the reader is standing in it, and what is asked here is what the register
    # answers, not which two chips got the room.
    key_line(page)  # the repaint's own frame, as everywhere else here
    chips = page.evaluate(
        "() => [...document.querySelectorAll('.lf-keyline .lf-key')]"
        ".map(c => c.textContent)"
    )
    assert any("⏎ / space" in c for c in chips), chips
    assert not any("←" in c or "→" in c for c in chips), chips
    # And the press, which is the half that would matter if no surface said anything: the
    # arrow is the page's here and moves nothing, where the platform's pair still folds it.
    opened_now = staged.evaluate("el => el.parentElement.open")
    page.keyboard.press("ArrowLeft")
    assert staged.evaluate("el => el.parentElement.open") is opened_now
    page.keyboard.press("Enter")
    assert staged.evaluate("el => el.parentElement.open") is not opened_now
    assert errors == []
    page.close()


def test_the_key_line_says_what_a_press_will_do(browser, serve):
    """The key line and dispatcher read one return frame for each keyboard entry."""
    url = serve(NOTED_PAGE)
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "One thread.",
            "anchor": {"quote": "first passage"},
        },
    )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")
    line = page.locator(".lf-keyline")

    # Page scope: the standing verbs, thread rows only over threads, and no esc
    # chip — there is nothing to back out of.
    expect(line).to_contain_text("threads")
    expect(line).to_contain_text("more")
    expect(line).not_to_contain_text("esc")

    # Armed with the panel closed: the direct panel destination and its way out are visible.
    page.keyboard.press("g")
    expect(line).to_contain_text("Threads panel")
    expect(line).to_contain_text("cancel")
    page.keyboard.press("Escape")
    expect(line).not_to_contain_text("Threads panel")
    # The blue prefix is gone with the chord; the ordinary line may reuse the same words.
    expect(page.locator('.lf-keyline kbd[data-lf-key-state="pressed"]')).to_have_count(
        0
    )

    # c is comment everywhere. From the page it enters the page composer directly, and
    # one Escape undoes the one entry: field, panel, and focus origin together.
    page.keyboard.press("c")
    expect(page.locator(".lf-general textarea")).to_be_focused()
    expect(line).to_contain_text("send")
    expect(line).to_contain_text("back")
    # A send key on an empty box is answered, not swallowed — silence reads as a
    # send that happened.
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator(".lf-notice")).to_contain_text("Nothing to send")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()
    expect(line).not_to_contain_text("close threads")
    assert page.evaluate("() => document.activeElement === document.body")

    # g T is navigation to Threads. Its one completed chord enters one surface, and one
    # Escape restores the page instead of stranding focus on the panel toggle.
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("?")
    page.keyboard.press("?")
    help_el = page.locator(".lf-help")
    expect(help_el).to_be_visible()
    returning = help_el.locator(
        "section",
        has=page.get_by_role("heading", name="After entering a surface", exact=True),
    )
    expect(returning.locator('[data-lf-command="navigation.return"]')).to_contain_text(
        "Return from Threads panel"
    )
    expect(help_el.locator('[data-lf-command="navigation.back"]')).to_have_count(0)
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")

    # The fast rung: t reopens onto a thread, and Esc from it is one press out.
    # Every rung earns a press here because Esc is the only keyboard collapse.
    page.keyboard.press("t")
    expect(page.locator(".lf-thread")).to_be_focused()
    expect(line).to_contain_text("close threads")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()
    assert errors == []
    page.close()


def test_a_comments_quoted_passage_is_in_the_keyboard_journey(browser, serve):
    """The pointer's return-to-passage action is a focusable, named control too."""
    lead = "".join(f"<p>Earlier reading context, line {n}.</p>" for n in range(14))
    tail = "".join(f"<p>Later reading context, line {n}.</p>" for n in range(14))
    noted_page = NOTED_PAGE.replace('<p id="p1">', f'{lead}<p id="p1">').replace(
        '<figure id="fig">', f'{tail}<figure id="fig">'
    )
    url = serve(noted_page)
    d = serve.page_dir
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Check this wording.",
            "anchor": {"section": "p1", "quote": "first passage"},
        },
    )
    page, errors = open_page(browser, live_url(url))
    page.emulate_media(reduced_motion="reduce")
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")

    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("t")
    expect(page.locator(".lf-thread")).to_be_focused()
    page.keyboard.press("Tab")
    quote = page.locator(".lf-thread .lf-quote")
    expect(quote).to_be_focused()
    expect(quote).to_have_attribute("role", "button")
    expect(quote).to_have_attribute("aria-keyshortcuts", "Enter Space")
    expect(page.locator(".lf-keyline")).to_contain_text("return to the passage")

    quote.evaluate(
        """node => node.addEventListener('click', () => {
          node.dataset.keyboardActivations =
            String(Number(node.dataset.keyboardActivations || 0) + 1);
        })"""
    )
    passage = page.locator("#p1")
    passage.scroll_into_view_if_needed()
    page.evaluate(
        """() => {
          const passage = document.querySelector('#p1').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          document.scrollingElement.scrollBy(0, passage.top - banner.bottom - 96);
        }"""
    )
    before = page.evaluate(
        """() => {
          const passage = document.querySelector('#p1').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          return {scroll: document.scrollingElement.scrollTop, top: passage.top,
                  bottom: passage.bottom, banner: banner.bottom, height: innerHeight};
        }"""
    )
    assert before["top"] > before["banner"] + 48
    assert before["bottom"] < before["height"] - 48
    page.keyboard.press("Enter")
    page.keyboard.press("Space")
    expect(quote).to_have_attribute("data-keyboard-activations", "2")
    after = page.evaluate(
        """() => ({
          scroll: document.scrollingElement.scrollTop,
          top: document.querySelector('#p1').getBoundingClientRect().top,
        })"""
    )
    assert after["scroll"] == pytest.approx(before["scroll"], abs=0.5)
    assert after["top"] == pytest.approx(before["top"], abs=0.5)

    # One painted pixel is not a readable arrival. Carry the passage almost entirely
    # behind the fixed banner, then the same quote must bring it back into view.
    page.evaluate(
        """() => {
          const passage = document.querySelector('#p1').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          document.scrollingElement.scrollBy(0, passage.bottom - banner.bottom - 1);
        }"""
    )
    sliver = page.evaluate(
        """() => {
          const passage = document.querySelector('#p1').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          return {scroll: document.scrollingElement.scrollTop, top: passage.top,
                  bottom: passage.bottom, banner: banner.bottom};
        }"""
    )
    assert sliver["top"] < sliver["banner"] < sliver["bottom"]
    page.keyboard.press("Enter")
    returned = page.evaluate(
        """() => ({
          scroll: document.scrollingElement.scrollTop,
          top: document.querySelector('#p1').getBoundingClientRect().top,
          banner: document.querySelector('.lf-banner').getBoundingClientRect().bottom,
        })"""
    )
    assert returned["scroll"] != pytest.approx(sliver["scroll"], abs=0.5)
    assert returned["top"] > returned["banner"]

    # A resolved thread keeps its page placement even though its folded quote has no live
    # mark. On a covering phone panel, that retained destination remains an enabled
    # keyboard action, spends the sheet, and returns to the passage.
    page.get_by_role("button", name="Resolve").click()
    round_trip(page)
    resized(page, 390, 800)
    details = page.locator(".lf-details")
    details.evaluate("el => { el.open = true; }")
    resolved_quote = details.locator(".lf-quote")
    expect(resolved_quote).not_to_have_class(re.compile(r"\bdetached\b"))
    expect(resolved_quote).to_have_attribute("aria-disabled", "false")
    page.evaluate(
        "() => document.scrollingElement.scrollTo(0, document.scrollingElement.scrollHeight)"
    )
    placed_before = page.evaluate("() => document.scrollingElement.scrollTop")
    resolved_quote.focus()
    expect(page.locator(".lf-keyline")).to_contain_text("return to the passage")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-panel")).to_be_hidden()
    placed_after = page.evaluate(
        """() => {
          const passage = document.querySelector('#p1').getBoundingClientRect();
          const banner = document.querySelector('.lf-banner').getBoundingClientRect();
          return {scroll: document.scrollingElement.scrollTop, top: passage.top,
                  bottom: passage.bottom, banner: banner.bottom, height: innerHeight};
        }"""
    )
    assert placed_after["scroll"] != placed_before
    assert placed_after["top"] > placed_after["banner"]
    assert placed_after["bottom"] < placed_after["height"]

    # When a later version removes the passage altogether, the same folded quote is an
    # informative disabled stop. A pointer press has no destination to spend the sheet on,
    # so the covering panel and the page behind it both stay where the reader left them.
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    without_passage = re.sub(r'<p id="p1">.*?</p>', "", noted_page, flags=re.DOTALL)
    (d / ".fixture-versions" / "v2.html").write_text(without_passage)
    stamp_version_file(d, 2, "remove the quoted passage")
    wait_for_revision(page, 2)
    details.evaluate("el => { el.open = true; }")
    resolved_quote = details.locator(".lf-quote")
    expect(resolved_quote).to_have_class(re.compile(r"\bdetached\b"))
    expect(resolved_quote).to_have_attribute("aria-disabled", "true")
    assert resolved_quote.get_attribute("aria-keyshortcuts") is None
    expect(page.locator(".lf-panel")).to_be_visible()
    stranded_before = page.evaluate("() => document.scrollingElement.scrollTop")
    quote_box = resolved_quote.bounding_box()
    assert quote_box is not None
    page.mouse.click(
        quote_box["x"] + quote_box["width"] / 2,
        quote_box["y"] + quote_box["height"] / 2,
    )
    expect(page.locator(".lf-panel")).to_be_visible()
    assert page.evaluate("() => document.scrollingElement.scrollTop") == stranded_before
    resolved_quote.focus()
    expect(page.locator(".lf-keyline")).not_to_contain_text("return to the passage")
    assert errors == []
    page.close()


def test_a_text_box_keeps_its_keys_from_the_widget_around_it(browser, serve):
    """A widget scope may contain a text box, but its bare keys still type there.

    The focused element's own rows remain nearer so a draft can keep its specific Escape
    and a wired composer can send with Mod+Enter. The text-entry scope then claims the
    characters and editing keys before an ancestor widget can see them."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    page.evaluate(
        """async () => {
          const { keys } = await import('/runtime/widget-api.js');
          const host = document.createElement('section');
          host.id = 'key-owning-widget';
          const box = document.createElement('textarea');
          host.append(box);
          document.querySelector('main').append(host);
          keys(host, 'Around a text box', [
            {id: 'test.widget',
             keys: ['a', 'Enter', 'Shift+ArrowLeft', 'Mod+z', 'Escape'],
             does: 'Work the widget', line: 'work widget',
             run: (binding) => host.dataset.fired = binding},
          ]);
          box.focus();
        }"""
    )

    page.keyboard.press("a")
    page.keyboard.press("Enter")
    expect(page.locator("#key-owning-widget textarea")).to_have_value("a\n")
    assert page.locator("#key-owning-widget").get_attribute("data-fired") is None
    page.keyboard.press("Shift+ArrowLeft")
    page.keyboard.press("Control+z")
    assert page.locator("#key-owning-widget").get_attribute("data-fired") is None

    # An unrelated core layer may stand at the same time. The widget ancestor remains
    # nearer for keys the text-entry shield does not claim; only editing stays native.
    page.locator(".lf-version").click()
    expect(page.locator(".lf-version-menu")).to_be_visible()
    page.locator("#key-owning-widget textarea").focus()
    page.keyboard.press("Escape")
    expect(page.locator("#key-owning-widget")).to_have_attribute("data-fired", "Escape")
    expect(page.locator(".lf-version-menu")).to_be_visible()
    assert errors == []
    page.close()


def test_a_scope_cannot_give_one_live_key_two_meanings(browser, serve):
    """An ambiguous row set is refused at the register boundary.

    Reusing a key in mutually exclusive states remains valid; a card grip relies on that
    to make Enter and Space mean grab before the move and drop during it."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    answers = page.evaluate(
        """async () => {
          const { keys } = await import('/runtime/widget-api.js');
          const { activeRows, answers: bindingAnswers, canonicalBinding } =
            await import('/runtime/keyboard/bindings.js');
          const { createReturnStack } =
            await import('/runtime/keyboard/return-stack.js');
          const { paintKeys } = await import('/runtime/keyboard/scopes.js');
          const declare = (id, rows) => {
            const button = document.createElement('button');
            button.id = id;
            document.querySelector('main').append(button);
            try {
              keys(button, id, rows);
              return 'declared';
            } catch (error) {
              return error.message;
            } finally {
              button.remove();
            }
          };
          const conflicts = (rows) => {
            try {
              activeRows(rows, 'Alias meanings');
              return 'accepted';
            } catch (error) {
              return error.message;
            }
          };
          const keptInvalid = (id, when) => {
            const button = document.createElement('button');
            button.id = id;
            document.querySelector('main').append(button);
            let declaration = 'declared';
            try {
              keys(button, id, [
                {id: 'test.kept-first', keys: ['F4'], does: 'First kept meaning', line: 'first', run: () => {}},
                {id: 'test.kept-second', keys: ['F4'], does: 'Second kept meaning', line: 'second', run: () => {}},
              ], when);
            } catch (error) {
              declaration = error.message;
            }
            const paints = [];
            for (let i = 0; i < 2; i++) {
              try {
                paintKeys();
                paints.push('painted');
              } catch (error) {
                paints.push(error.message);
              }
            }
            return {declaration, paints};
          };
          const malformedFrame = () => {
            const stack = createReturnStack({
              focused: () => document.body,
              paintHere: () => {},
              readingBlock: () => document.querySelector('main'),
            });
            try {
              stack.invoke(
                {id: 'test.bad-frame', returnFrame: () => ({active: () => true})},
                'F8',
                () => {},
              );
              return 'accepted';
            } catch (error) {
              return error.message;
            }
          };
          return {
            ambiguous: declare('ambiguous', [
              {id: 'test.first', keys: ['F2'], does: 'First meaning', line: 'first', run: () => {}},
              {id: 'test.second', keys: ['F2'], does: 'Second meaning', line: 'second', run: () => {}},
            ]),
            exclusive: declare('exclusive', [
              {id: 'test.first-state', keys: ['F2'], does: 'First state', line: 'first',
               when: () => true, run: () => {}},
              {id: 'test.second-state', keys: ['F2'], does: 'Second state', line: 'second',
               when: () => false, run: () => {}},
            ]),
            missingIdentity: declare('missing-identity', [
              {keys: ['F5'], does: 'Anonymous command', line: 'anonymous', run: () => {}},
            ]),
            malformedIdentity: declare('malformed-identity', [
              {id: 'Sentence shaped identity', keys: ['F5'], does: 'Named badly',
               line: 'bad identity', run: () => {}},
            ]),
            duplicateIdentity: declare('duplicate-identity', [
              {id: 'test.same', keys: ['F5'], does: 'First route', line: 'first', run: () => {}},
              {id: 'test.same', keys: ['F6'], does: 'Second route', line: 'second', run: () => {}},
            ]),
            modifierAlias: conflicts([
              {keys: ['Mod+Shift+x'], does: 'First alias'},
              {keys: ['Shift+Mod+x'], does: 'Second alias'},
            ]),
            caseAlias: conflicts([
              {keys: ['a'], does: 'Lowercase alias'},
              {keys: ['A'], does: 'Uppercase alias'},
            ]),
            punctuationAlias: conflicts([
              {keys: ['?'], does: 'Layout-owned punctuation'},
              {keys: ['Shift+?'], does: 'Shifted alias'},
            ]),
            spacePair: conflicts([
              {keys: [' '], does: 'Read down'},
              {keys: ['Shift+ '], does: 'Read up'},
            ]),
            spaceIdentity: [canonicalBinding(' '), canonicalBinding('Shift+ ')],
            spaceAnswers: {
              down: bindingAnswers(' ', {
                key: ' ', metaKey: false, ctrlKey: false, altKey: false, shiftKey: false,
              }),
              downFromShift: bindingAnswers(' ', {
                key: ' ', metaKey: false, ctrlKey: false, altKey: false, shiftKey: true,
              }),
              up: bindingAnswers('Shift+ ', {
                key: ' ', metaKey: false, ctrlKey: false, altKey: false, shiftKey: true,
              }),
              upWithoutShift: bindingAnswers('Shift+ ', {
                key: ' ', metaKey: false, ctrlKey: false, altKey: false, shiftKey: false,
              }),
            },
            noncanonical: declare('noncanonical', [
              {id: 'test.noncanonical', keys: ['Shift+Mod+x'], does: 'Noncanonical binding',
               line: 'work', run: () => {}},
            ]),
            namedSpace: declare('named-space', [
              {id: 'test.named-space', keys: ['Space'], does: 'Named space binding',
               line: 'work', run: () => {}},
            ]),
            invalidReturnFrame: declare('invalid-return-frame', [
              {id: 'test.invalid-return-frame', keys: ['F8'], does: 'Enter badly',
               line: 'enter', returnFrame: {}, run: () => {}},
            ]),
            returnWithoutCommand: declare('return-without-command', [
              {id: 'test.return-without-command', keys: ['F8'], does: 'Enter nowhere',
               line: 'enter', returnFrame: () => ({})},
            ]),
            malformedFrame: malformedFrame(),
            immediateTransaction: keptInvalid('kept-immediate'),
            gatedTransaction: keptInvalid('kept-gated', () => true),
          };
        }"""
    )
    assert "two live meanings for F2" in answers["ambiguous"], answers
    assert answers["exclusive"] == "declared", answers
    assert "has no stable command id" in answers["missingIdentity"], answers
    assert "is not a stable command id" in answers["malformedIdentity"], answers
    assert "declares test.same twice" in answers["duplicateIdentity"], answers
    assert "two live meanings for Shift+Mod+x" in answers["modifierAlias"], answers
    assert "two live meanings for A" in answers["caseAlias"], answers
    assert "two live meanings for Shift+?" in answers["punctuationAlias"], answers
    assert answers["spacePair"] == "accepted", answers
    assert answers["spaceIdentity"] == [" ", "Shift+ "], answers
    assert answers["spaceAnswers"] == {
        "down": True,
        "downFromShift": False,
        "up": True,
        "upWithoutShift": False,
    }, answers
    assert "write the canonical Mod+Shift+x" in answers["noncanonical"], answers
    assert 'write the canonical " "' in answers["namedSpace"], answers
    assert "returnFrame that is not a function" in answers["invalidReturnFrame"], (
        answers
    )
    assert (
        "declares a return frame but runs no entry" in answers["returnWithoutCommand"]
    ), answers
    assert "must return active, close, does, and line" in answers["malformedFrame"], (
        answers
    )
    assert "two live meanings for F4" in answers["immediateTransaction"]["declaration"]
    assert answers["immediateTransaction"]["paints"] == ["painted", "painted"]
    assert answers["gatedTransaction"]["declaration"] == "declared"
    assert "two live meanings for F4" in answers["gatedTransaction"]["paints"][0]
    assert answers["gatedTransaction"]["paints"][1] == "painted"

    # Help merges instances with the same title for presentation. Repeated keys there
    # belong to separate focus locations, so they are not a conflict in either scope.
    page.evaluate(
        """async () => {
          const { keys } = await import('/runtime/widget-api.js');
          let first;
          for (const label of ['First', 'Second']) {
            const button = document.createElement('button');
            button.textContent = label;
            document.querySelector('main').append(button);
            if (!first) first = button;
            keys(button, 'Repeated controls', [
              {id: 'test.repeated', keys: ['F3'], does: () => `Work ${label}`,
               line: 'work', run: () => button.dataset.fired = '1'},
              ...(label === 'Second' ? [{
                id: 'test.second-only', keys: ['F6'], does: 'Work only the second',
                line: 'second only', reach: 'on the second control',
                run: () => button.dataset.secondFired = '1',
              }] : []),
            ]);
          }
          first.focus();
        }"""
    )
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.get_by_role("dialog", name="Keyboard reference")).to_be_visible()
    search = page.get_by_role("combobox", name="Search keyboard shortcuts")
    search.fill("work only the second")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.locator(".lf-help-meta")).to_have_text(
        "Available on the second control"
    )
    search.fill("work first")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.get_by_role("button", name="First", exact=True)).to_have_attribute(
        "data-fired", "1"
    )
    expect(page.get_by_role("button", name="Second", exact=True)).not_to_have_attribute(
        "data-fired", "1"
    )
    assert errors == []
    page.close()


def test_signoff_uses_its_visible_button_and_g_l_never_falls_through(browser, serve):
    """Approval is a button action; a dead chord destination cannot turn into it."""
    html = NOTED_PAGE.replace(
        '<script type="module" src="/leaf.js"></script>',
        '<meta name="lf-review" content="sign-off">\n'
        '<script type="module" src="/leaf.js"></script>',
    )
    page, errors = open_page(browser, serve(html))
    approve = page.locator(".lf-signoff")
    expect(approve).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))

    # All leaves is conditional. With no neighbouring leaf, its chord must not be
    # reinterpreted as a page action carrying the same final key.
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(approve).to_have_text("Approve version")
    assert not [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "done"
    ]

    approve.focus()
    page.keyboard.press("Enter")
    round_trip(page)
    expect(approve).to_have_text("✓ Version approved")
    expect(approve).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))
    assert "(L)" not in approve.get_attribute("title")
    done = [e for e in events_model.read_events(serve.page_dir) if e["kind"] == "done"]
    assert len(done) == 1, done
    assert done[0]["text"] == "Looks good"
    assert errors == []
    page.close()


def test_character_shortcuts_can_be_turned_off_without_losing_the_keyboard(
    browser, serve
):
    """Speech-input and error-prone readers can disable every character command.

    The visible More button remains a native keyboard route back to the preference;
    Enter, Escape, and other non-character controls keep their ordinary meanings."""
    url = serve(DECISIONS_PAGE)
    events_model.append_event(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "A note."},
    )
    page, errors = open_page(browser, url)
    more = page.locator(".lf-key-more")
    expect(more).to_have_attribute("aria-label", "? more")
    key_faces = page.evaluate(
        """() => ['.lf-key-more kbd', '.lf-keyline .lf-key:not([hidden]) kbd']
          .map(sel => { const s = getComputedStyle(document.querySelector(sel));
            return {height: s.height, padding: s.padding, border: s.borderTopWidth,
                    radius: s.borderRadius, font: s.fontFamily};
          })"""
    )
    assert key_faces[0] == key_faces[1], key_faces
    version = page.locator(".lf-version")
    expect(version).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))
    expect(version).to_have_attribute("title", re.compile(r"\(g V\)$"))
    expect(page.locator(".lf-latest-chip")).to_have_attribute(
        "title", re.compile(r"\(g V v\)$")
    )
    # A numbered destination changes the live chord's progress, not the complete route
    # this control exposes.
    page.keyboard.press("g")
    page.keyboard.press("m")
    expect(page.locator(".lf-keyline")).to_contain_text("Page map locations")
    expect(page.locator(".lf-latest-chip")).to_have_attribute(
        "title", re.compile(r"\(g V v\)$")
    )
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-general textarea")).to_have_attribute(
        "placeholder", re.compile(r" · c$")
    )
    page.keyboard.press("c")
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")
    reply = page.locator(".lf-thread textarea")
    expect(reply).to_have_attribute("placeholder", "Reply")
    page.keyboard.press("Escape")

    page.keyboard.press("?")
    page.keyboard.press("?")
    toggle = page.get_by_role("button", name="Character shortcuts")
    expect(toggle).to_have_attribute("aria-pressed", "true")
    toggle.click()
    expect(toggle).to_have_attribute("aria-pressed", "false")
    expect(page.locator(".lf-help")).not_to_contain_text("Go to the Threads panel")

    page.keyboard.press("Escape")
    expect(version).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))
    expect(version).not_to_have_attribute("title", re.compile(r"\(g V\)$"))
    expect(page.locator(".lf-latest-chip")).not_to_have_attribute(
        "title", re.compile(r"\(g V v\)$")
    )
    expect(page.locator(".lf-general textarea")).not_to_have_attribute(
        "placeholder", re.compile(r" · c$")
    )
    expect(reply).to_have_attribute("placeholder", "Reply")
    # Space is checkbox activation, not a character shortcut. The option's local
    # navigation and activation remain available while letters, digits, and punctuation
    # are off.
    mark = page.locator("#live-question .lf-pick").first
    mark.focus()
    shortcuts = mark.get_attribute("aria-keyshortcuts").split()
    assert shortcuts == ["ArrowUp", "ArrowDown", "Space"], shortcuts
    page.keyboard.press("Space")
    expect(page.locator("#lq-keep")).to_have_attribute("chosen", "")

    expect(more).to_have_attribute("aria-label", "More keyboard shortcuts")
    assert more.get_attribute("aria-keyshortcuts") is None
    page.keyboard.press("c")
    expect(page.locator(".lf-panel")).to_be_hidden()
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_be_hidden()

    # The preference survives a visit, and the non-character Enter path can reverse it.
    page.reload()
    page.wait_for_function("() => document.body.hasAttribute('data-lf-presented')")
    more = page.locator(".lf-key-more")
    expect(more).to_have_attribute("aria-label", "More keyboard shortcuts")
    more.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-help")).to_be_visible()
    toggle = page.get_by_role("button", name="Character shortcuts")
    expect(toggle).to_have_attribute("aria-pressed", "false")
    toggle.focus()
    page.keyboard.press("Enter")
    expect(toggle).to_have_attribute("aria-pressed", "true")
    create = page.locator('.lf-help-command[data-lf-command="comment.create"]')
    expect(create).to_have_attribute("data-lf-available", "true")
    create.click()
    expect(page.locator(".lf-help")).to_be_hidden()
    expect(version).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))
    expect(version).to_have_attribute("title", re.compile(r"\(g V\)$"))
    expect(page.locator(".lf-general textarea")).to_be_focused()
    expect(page.locator(".lf-general textarea")).to_have_attribute(
        "placeholder", re.compile(r"(⌘⏎|Ctrl\+⏎)$")
    )
    expect(page.locator(".lf-panel")).to_be_visible()
    # Running the declaration from the reference goes through the same return-stack
    # invocation as its physical key, so Escape returns to the reference's door.
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()
    expect(more).to_be_focused()
    assert errors == []
    page.close()


def test_a_key_the_runtime_binds_is_a_key_some_surface_names(browser, serve):
    """One declaration per binding, and every surface is a projection of it. The d/u
    reading-page pair is the case that named this: a runtime key must be visible wherever
    the keyboard vocabulary is projected.

    Where it is projected is the shelf and the reference, not the resting line, which
    holds two chips and spends neither on scrolling. So the line is asked for the row it
    holds rather than the row it paints, and the reference below is read for the words —
    a key named on no surface at all is what this refuses.

    It is refused now, where a scope is declared, so the next binding written without a
    word fails on the page that introduces it rather than going quiet on every page after
    it. A row that presses nothing needs none — F7 is the browser's caret browsing, real
    and worth knowing and not what the next press does."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    line = page.locator(".lf-keyline")
    movement = line.locator('.lf-key[data-lf-commands~="page.down"]')
    expect(movement).to_have_count(1)
    expect(movement).to_have_attribute("data-lf-commands", re.compile(r"\bpage\.up\b"))
    expect(movement.locator("kbd")).to_have_text("d / u")
    expect(movement).to_contain_text("page down / up")
    # Declared and worded, and painted where the reader asks rather than on the resting
    # glance. The reference below is the surface that names it, and this is the pair of
    # counts that tells a row the line declined to paint from a row that says nothing.
    expect(
        line.locator('.lf-key:not([hidden])[data-lf-commands~="page.down"]')
    ).to_have_count(0)
    resized(page, 420, 800)
    compact = line.evaluate(
        """node => {
          const visible = [...node.children].filter(el => el.checkVisibility());
          const tops = [];
          const tolerance = Math.min(...visible.map(el => el.offsetHeight)) / 2;
          for (const el of visible)
            if (tops.every(top => Math.abs(top - el.offsetTop) > tolerance))
              tops.push(el.offsetTop);
          return {
            rows: tops.length,
            clientWidth: node.clientWidth,
            scrollWidth: node.scrollWidth,
            clientHeight: node.clientHeight,
            scrollHeight: node.scrollHeight,
          };
        }"""
    )
    assert compact["rows"] <= 2, compact
    assert compact["scrollWidth"] <= compact["clientWidth"], compact
    assert compact["scrollHeight"] <= compact["clientHeight"], compact

    # Linux's wider system face wraps this line at the smallest supported window, and the
    # disclosure is the one control on it: whatever the face costs, More stays painted and
    # the line stays inside its own box rather than clipping the way out of itself.
    resized(page, 320, 800)
    page.evaluate(RENDERED)
    smallest = line.evaluate(
        """node => {
          const more = node.querySelector('.lf-key-more');
          return {
            moreShown: more.checkVisibility(),
            clientWidth: node.clientWidth,
            scrollWidth: node.scrollWidth,
            clientHeight: node.clientHeight,
            scrollHeight: node.scrollHeight,
          };
        }"""
    )
    assert smallest["moreShown"], smallest
    assert smallest["scrollWidth"] <= smallest["clientWidth"], smallest
    assert smallest["scrollHeight"] <= smallest["clientHeight"], smallest
    resized(page, 1280, 800)
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_contain_text("Move 60% of a page down")
    expect(page.locator(".lf-help")).to_contain_text("Move 60% of a page up")
    expect(page.locator(".lf-help")).to_contain_text("Caret browsing")
    page.keyboard.press("Escape")
    expect(line).not_to_contain_text("F7")

    refused = page.evaluate(
        """async () => {
          const { keys } = await import('/runtime/widget-api.js');
          try {
            keys(document.body, 'A project scope', [
              { id: 'test.no-line', keys: ['F2'],
                does: 'a press with nothing to say for itself',
                run: () => {} },
            ]);
            return 'declared';
          } catch (e) {
            return e.message;
          }
        }"""
    )
    assert "no word for the key line" in refused, refused

    # The other half of what this gate is for, and the quieter failure. `answers` asks
    # after Mod, Alt and Shift by name and reads every other prefix as absent, so a
    # binding written `Ctrl+k` is not a key that never fires — it is `k`, which fires on
    # a bare press while both surfaces spell the chip "Ctrl+k" and the press the chip
    # names does nothing. A declaration that means a different key than it says is the
    # one thing no surface can project, so it is refused where declarations enter.
    modified = page.evaluate(
        """async () => {
          const { keys } = await import('/runtime/widget-api.js');
          try {
            keys(document.body, 'A project scope', [
              { id: 'test.bad-modifier', keys: ['Ctrl+k'],
                does: 'a modifier the matcher never asks about',
                line: 'a key that is really just k', run: () => {} },
            ]);
            return 'declared';
          } catch (e) {
            return e.message;
          }
        }"""
    )
    assert "Ctrl is no modifier" in modified, modified
    assert "Mod, Alt, Shift" in modified, modified

    # Routes split one compact row into separately addressable commands. Every declared
    # binding therefore needs exactly one route: otherwise dispatch can gain a press that
    # both the reference and key line omit from their shared presentation projection.
    routed = page.evaluate(
        """async () => {
          const { keys } = await import('/runtime/widget-api.js');
          const declare = row => {
            try {
              keys(document.body, 'A routed project scope', [row]);
              return 'declared';
            } catch (e) {
              return e.message;
            }
          };
          return {
            missing: declare({
              id: 'test.missing-route', keys: ['F2', 'F3'],
              does: 'Move either way', line: 'move either way', run: () => {},
              routes: [{
                id: 'test.missing-route.first', binding: 'F2',
                does: 'Move one way', line: 'move one way',
              }],
            }),
            duplicate: declare({
              id: 'test.duplicate-route', keys: ['F4'],
              does: 'Move once', line: 'move once', run: () => {},
              routes: [
                {
                  id: 'test.duplicate-route.first', binding: 'F4',
                  does: 'Move first', line: 'move first',
                },
                {
                  id: 'test.duplicate-route.second', binding: 'F4',
                  does: 'Move second', line: 'move second',
                },
              ],
            }),
          };
        }"""
    )
    assert "has no route for F3" in routed["missing"], routed
    assert "routes F4 twice" in routed["duplicate"], routed

    # A registered result may deliberately precede the platform's own half of a press.
    # It still enters through the same register — and therefore the same surfaces and
    # scoping — but the dispatcher must not cancel that native result. The versions menu
    # uses this for the Tab that closes it before the browser moves focus past its door.
    native = page.evaluate(
        """async () => {
          const { keys } = await import('/runtime/widget-api.js');
          const owner = document.createElement('div');
          owner.tabIndex = -1;
          document.body.append(owner);
          owner.focus();
          let ran = 0;
          keys(owner, 'A native companion', [
            { id: 'test.native-companion', keys: ['F2'],
              does: 'Run before the browser', line: 'run first',
              native: true, run: () => ran++ },
          ]);
          const event = new KeyboardEvent(
            'keydown', {key: 'F2', bubbles: true, cancelable: true}
          );
          owner.dispatchEvent(event);
          owner.remove();
          return {ran, prevented: event.defaultPrevented};
        }"""
    )
    assert native == {"ran": 1, "prevented": False}, native
    assert errors == []
    page.close()


def test_a_partially_shadowed_row_keeps_each_other_live_binding(browser, serve):
    """Shadowing is per binding, so one local `d` must not hide the page row's live `u`.

    Multi-key rows keep related commands compact, but presentation cannot treat that visual
    grouping as dispatch ownership. The effective row retains the unshadowed route, its own
    direction word, and the same command identity the reference exposes."""
    html = NOTED_PAGE.replace("</main>", '<div style="height: 2400px"></div></main>')
    page, errors = open_page(browser, serve(html))
    page.evaluate(
        """async () => {
          const { keys } = await import('/runtime/widget-api.js');
          const target = document.createElement('button');
          target.id = 'local-down';
          target.textContent = 'Local down';
          document.querySelector('main').prepend(target);
          keys(target, 'On local down', [{
            id: 'test.local-down', keys: ['d'], does: 'Local down', line: 'local down',
            run: () => { target.dataset.pressed = '1'; },
          }]);
          target.focus();
        }"""
    )

    # The row the line holds rather than the one it paints. Both are the same projection —
    # renderLine builds every live row and then hides what it has no room for — and the
    # resting line now spends both chips on the two presses that say something back, so
    # asking for a painted chip would be asking about the width instead of the shadowing.
    line = page.locator(".lf-keyline")
    up = line.locator('.lf-key[data-lf-commands="page.up"]')
    expect(up).to_have_count(1)
    expect(up.locator("kbd")).to_have_text("u")
    expect(up).to_contain_text("page up")
    expect(line.locator('[data-lf-commands~="page.down"]')).to_have_count(0)

    before = page.evaluate("() => { scrollTo(0, 1000); return scrollY; }")
    assert before > 0
    page.keyboard.press("u")
    page.wait_for_function("before => scrollY < before", arg=before)
    assert page.locator("#local-down").get_attribute("data-pressed") is None
    assert errors == []
    page.close()


def test_the_register_is_the_only_way_a_key_enters_the_runtime():
    """Every surface that names a key is a projection of the register, which holds only if
    nothing binds a key behind its back. That is not a property a rendered page can be
    asked about — a listener nobody declared looks exactly like no listener at all until
    the press it eats goes missing — so it is pinned in the source, the way the
    document-level class surface is.

    Two are allowed and both are named here. The dispatcher is the register's own. The aim
    latch is not a binding at all: holding ⌥ arms nothing and answers no press, it paints
    what a click would take, and its keyup half has no place in a table of presses. A third
    is how every drift this register replaced began — a `keydown` beside a display list,
    the two of them free to disagree about which keys the widget answers."""
    layer = ROOT / "skills/leaf"
    sources = [
        layer / "assets/leaf.js",
        *sorted((layer / "assets/runtime").rglob("*.js")),
        *sorted((layer / "packages").glob("*/widgets/*.js")),
        *sorted((ROOT / "examples/packages").glob("*/widgets/*.js")),
    ]
    listeners = [
        f"{src.name}:{n}"
        for src in sources
        for n, line in enumerate(src.read_text().splitlines(), 1)
        if 'addEventListener("keydown"' in line
    ]
    assert len(listeners) == 2, (
        f"the runtime's keydown listeners changed: {listeners}. A key belongs in the "
        "register (keys(el, title, rows)), which is what lets a surface promise it."
    )


def test_native_controls_need_no_generic_space_binding(browser, serve):
    """The reference has no synthetic generic-control command. Specialized controls
    such as a board grip still declare the Space meaning that belongs to their widget."""
    page, errors = open_page(browser, serve(BOARD_PAGE))
    page.keyboard.press("?")
    page.keyboard.press("?")
    help_el = page.locator(".lf-help")
    expect(help_el).not_to_contain_text("On a control")
    expect(help_el.locator("tr", has_text="Grab the card")).to_contain_text("space")
    page.keyboard.press("Escape")

    # And the key does what the reference says it does.
    grip = page.locator("lf-board .lf-grip").first
    grip.focus()
    page.keyboard.press(" ")
    expect(page.locator(".lf-lift")).to_have_count(1)
    expect(page.locator(".lf-keyline")).to_contain_text("drop")
    page.keyboard.press("Escape")
    expect(page.locator(".lf-lift")).to_have_count(0)
    assert errors == []
    page.close()


def test_holding_a_key_repeats_only_where_the_press_is_a_walk(
    browser, serve, live_leaf
):
    """A held key repeats keydown where a real button fires once. A walk wants that — t
    down threads, d down decisions, arrows down the tray — and a press that toggles or navigates
    does not: a held `]` was a page navigation per repeat, and a held pick a `choose` per
    repeat, each of them one decision the reader made once. So a row says whether it
    repeats and the default is no, where before only `offer`'s own listener had thought
    about it and the global table had not.

    No gesture Playwright makes carries the repeat flag, so the press is dispatched with
    it set. That is the event a held key sends and the handler under test is the one the
    page installed; the tap below it, dispatched the same way and answered, is what says
    so rather than leaving the held press to pass for want of reaching anything."""
    live_leaf("second", "A second leaf")
    page, errors = open_page(browser, serve(DECISIONS_PAGE, comments=3))
    press = """([key, repeat, shiftKey = false]) => document.dispatchEvent(
        new KeyboardEvent('keydown',
          {key, repeat, shiftKey, bubbles: true, cancelable: true}))"""

    page.keyboard.press("t")
    expect(page.locator(".lf-thread").first).to_be_focused()
    page.evaluate(press, ["t", True])  # a walk repeats
    expect(page.locator(".lf-thread").nth(1)).to_be_focused()

    page.keyboard.press("a")
    expect(page.locator("#live-question-decision[data-lf-decision]")).to_have_count(1)
    page.evaluate(press, ["a", True])  # the same grammar repeats for asks
    expect(page.locator("#sug-refill[data-lf-decision]")).to_have_count(1)

    tray = page.locator(".lf-others-panel")
    page.keyboard.press("g")
    page.evaluate(press, ["l", True, True])  # a panel destination does not repeat
    expect(tray).to_be_hidden()
    page.evaluate(press, ["l", False, True])  # the same event, answered
    expect(tray).to_be_visible()
    assert errors == []
    page.close()


def test_the_key_line_keeps_local_and_page_hints_and_progressively_reveals_the_rest(
    browser, serve
):
    """The short line is a glance, not the keyboard reference. It keeps the first
    innermost live action and the way out when the current scene has one. One `? more`
    unfolds a bounded shelf of current commands; `? all shortcuts` then opens the
    complete searchable register.

    The panel's general box is the causal contrast for the cap. A full page row crosses
    into the panel and paints over the box; the bounded shortlist ends before it. The
    overlap is tested before opening the reference so a searchable popup cannot make the
    symptom disappear merely by covering both surfaces."""
    page, errors = open_page(browser, serve(NOTED_PAGE, comments=2))
    page.set_viewport_size({"width": 1200, "height": 800})
    page.get_by_role("button", name=re.compile("^Threads")).click()

    line = page.locator(".lf-keyline")
    visible_hints = line.locator(".lf-key:not([hidden])")
    assert visible_hints.count() == 2, page.evaluate(
        """() => { const line = document.querySelector('.lf-keyline'); return {
          client: line.clientWidth, scroll: line.scrollWidth,
          max: getComputedStyle(line).maxWidth,
          hints: [...line.querySelectorAll('.lf-key')].map(el => ({
            text: el.textContent, hidden: el.hidden
          }))
        }; }"""
    )
    assert not page.evaluate(
        """() => {
          const a = document.querySelector('.lf-keyline').getBoundingClientRect();
          const b = document.querySelector('.lf-general').getBoundingClientRect();
          return a.left < b.right && a.right > b.left &&
                 a.top < b.bottom && a.bottom > b.top;
        }"""
    ), "the key line covers the general comment box"

    # Moving into the box changes both contextual hints without introducing a second
    # shortlist: the same scope order the dispatcher uses supplies them, so what the line
    # says is what the innermost live scope answers and not a list kept beside it.
    #
    # Stand on the list directly: the banner button that opened the panel is chrome, and
    # its `c` meaning is deliberately outside this key-line projection test.
    page.locator(".lf-threads").focus()
    expect(page.locator(".lf-threads")).to_be_focused()
    expect(visible_hints.nth(0)).not_to_contain_text("send")
    page.keyboard.press("c")
    expect(visible_hints).to_have_count(2)
    expect(visible_hints.nth(0)).to_contain_text("send")
    expect(visible_hints.nth(1)).to_contain_text("back to threads")

    more = page.get_by_role("button", name="? more", exact=True)
    expect(more).to_have_attribute("aria-expanded", "false")
    more.click()
    help_el = page.locator(".lf-help")
    search = page.get_by_role("combobox", name="Search keyboard shortcuts")
    expect(help_el).to_be_hidden()
    expect(line).to_have_attribute("data-lf-expanded", "true")
    expect(page.locator(".lf-live")).to_contain_text(
        "More keyboard shortcuts shown. Press question mark again for all shortcuts"
    )
    assert visible_hints.count() > 2
    expect(line).to_contain_text("less")
    for width in (1200, 420):
        page.set_viewport_size({"width": width, "height": 800})
        page.evaluate(RENDERED)
        geometry = line.evaluate(
            """node => {
              const visible = [...node.children].filter(el => el.checkVisibility());
              const boxes = visible.map(el => el.getBoundingClientRect());
              const tolerance = Math.min(...visible.map(el => el.offsetHeight)) / 2;
              const rows = [];
              for (const el of visible)
                if (rows.every(top => Math.abs(top - el.offsetTop) > tolerance))
                  rows.push(el.offsetTop);
              return {
                rows: rows.length,
                clientWidth: node.clientWidth,
                scrollWidth: node.scrollWidth,
                clientHeight: node.clientHeight,
                scrollHeight: node.scrollHeight,
                bandHeight: Math.max(...boxes.map(box => box.bottom))
                          - Math.min(...boxes.map(box => box.top)),
                maxItemHeight: Math.max(...boxes.map(box => box.height)),
              };
            }"""
        )
        assert geometry["rows"] <= 2, geometry
        assert geometry["scrollWidth"] <= geometry["clientWidth"], geometry
        assert geometry["scrollHeight"] <= geometry["clientHeight"], geometry
        assert geometry["bandHeight"] <= geometry["maxItemHeight"] * 2 + 8, geometry
    page.set_viewport_size({"width": 1200, "height": 800})
    page.evaluate(RENDERED)
    more = page.get_by_role("button", name="? all shortcuts", exact=True)
    expect(more).to_have_attribute("aria-expanded", "true")
    more.click()
    expect(help_el).to_be_visible()
    expect(search).to_be_focused()
    expect(page.get_by_role("button", name="Back to more shortcuts")).to_be_visible()
    expect(help_el).not_to_contain_text("With more keyboard shortcuts")

    search.fill("Cancel item selection")
    expect(help_el.locator("tr:not([hidden])")).to_have_count(1)
    expect(help_el.locator("tr:not([hidden])").first).to_contain_text(
        "Cancel item selection"
    )

    search.fill("thread panel")
    expect(
        help_el.get_by_role("heading", name="In the thread panel", exact=True)
    ).to_be_visible()
    expect(help_el.locator("tr:not([hidden])")).not_to_have_count(0)

    search.fill("no such shortcut")
    expect(help_el.locator(".lf-help-empty")).to_be_visible()
    expect(help_el.locator("tr:not([hidden])")).to_have_count(0)
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()
    expect(line).to_have_attribute("data-lf-expanded", "true")
    expect(
        page.get_by_role("button", name="? all shortcuts", exact=True)
    ).to_be_focused()
    page.keyboard.press("Escape")
    expect(line).to_have_attribute("data-lf-expanded", "false")
    expect(page.locator(".lf-live")).to_contain_text("Fewer keyboard shortcuts shown")
    expect(page.get_by_role("button", name="? more", exact=True)).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(visible_hints).to_have_count(2)
    assert errors == []
    page.close()


def test_the_resting_key_line_names_the_presses_that_say_something_back(browser, serve):
    """The sentence a reader reads before they have pressed anything.

    It used to be `/ search page · s select item · ? more · d / u page down / up`: two
    ways of finding something to act on, one way of scrolling a page that scrolls under
    any wheel, and not one word about the remark the page exists to collect — `c` and `r`
    were display: none until `?`. The two presses that say something back lead it now,
    and the ways of choosing what to say it about are what `?` unfolds.

    Read off `:not([hidden])`, because renderLine leaves every live row in the DOM and
    hides the ones it will not paint: `to_contain_text` on the line answers about the
    register and would pass over a chip nobody can see."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    line = page.locator(".lf-keyline")
    shown = line.locator(".lf-key:not([hidden])")
    expect(shown).to_have_count(2)
    expect(page.get_by_role("button", name="? more", exact=True)).to_be_visible()
    # One settled read, which pins the count, the order, the keys and the words together.
    assert key_line(page) == "c\ncomment on the page\nr\nreact\n?\nmore", key_line(page)

    # Still declared, and off the glance nobody asked for. Each is in the DOM and each is
    # hidden — the pair of counts is what separates a row the line declined to paint from
    # a row that stopped existing.
    for command in ("page.search.open", "selection.open", "page.down"):
        expect(line.locator(f'.lf-key[data-lf-commands~="{command}"]')).to_have_count(1)
        expect(
            line.locator(f'.lf-key:not([hidden])[data-lf-commands~="{command}"]')
        ).to_have_count(0)

    # And named in full by the reference, which lists every live capability rather than
    # the ones the current width has room for.
    page.keyboard.press("?")
    page.keyboard.press("?")
    help_el = page.locator(".lf-help")
    expect(help_el).to_be_visible()
    expect(help_el).to_contain_text("Search all the text on the page")
    expect(help_el).to_contain_text("Select a visible item by hint")
    expect(help_el).to_contain_text("Move 60% of a page down")
    expect(help_el).to_contain_text("Move 60% of a page up")
    assert errors == []
    page.close()


def test_a_coarse_pointer_is_given_no_key_line_and_keeps_no_room_for_one(
    browser, serve
):
    """A touch device has no keyboard to advertise, so the line has nothing to say and
    stands down whole rather than shrinking: every hint on it names a key the reader
    cannot press, and it spends a box on them over the words of a page whose window is
    the smallest one there is.

    The room goes with it. syncLayout reads the standing line's own box, so the band
    reserved at the foot of the document and of either list is the line's footprint or
    nothing at all — a reservation for a line nobody is shown is a strip of blank paper
    under the last paragraph."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    try:
        page, errors = open_page(browser, serve(NOTED_PAGE), context=context)
        assert page.evaluate("() => matchMedia('(pointer: coarse)').matches"), (
            "the touch fixture never reached Leaf's coarse-pointer rules"
        )
        expect(page.locator(".lf-keyline")).to_be_hidden()
        room = page.evaluate(
            """() => {
              const line = document.querySelector('.lf-keyline');
              const chrome = document.querySelector('.lf-chrome');
              return {
                display: getComputedStyle(line).display,
                height: line.getBoundingClientRect().height,
                reserved: getComputedStyle(chrome).paddingBottom,
                moreShown: document.querySelector('.lf-key-more').checkVisibility(),
              };
            }"""
        )
        assert room == {
            "display": "none",
            "height": 0,
            "reserved": "0px",
            "moreShown": False,
        }, room

        # And the page is still whole underneath. Everything that asks how far down the
        # page reaches asks it of the line's box, and a line with no box answers 0 — the
        # top of the window — which reads as "all of it is covered". Item hints and the
        # search's own highlight are drawn for boxes above that answer, so a tablet got
        # `s` naming nothing and `/` painting no match, with the page itself intact and
        # nothing on screen saying why.
        page.keyboard.press("s")
        expect(page.locator(".lf-target-hint").first).to_be_visible()
        page.keyboard.press("Escape")
        assert errors == []
        page.close()
    finally:
        context.close()
    # The control the reading above needs, because `paddingBottom` computes to "0px" on a
    # chrome root syncLayout never wrote to: the same page at the same size under a fine
    # pointer has to reserve a band, or "reserved nothing" and "reserved nowhere" are the
    # same green.
    fine, errors = open_page(browser, serve(NOTED_PAGE))
    resized(fine, 390, 844)
    fine.evaluate(RENDERED)
    reserved = fine.evaluate(
        "() => getComputedStyle(document.querySelector('.lf-chrome')).paddingBottom"
    )
    assert reserved != "0px" and float(reserved.removesuffix("px")) > 20, reserved
    assert errors == []
    fine.close()


FOOT_CONTROL_PAGE = NOTED_PAGE.replace(
    "</main>",
    '<div style="height: 2400px"></div>'
    '<lf-decision id="foot-d"><h2 id="foot-h">The last question</h2>'
    '<lf-options id="foot-o" choose>'
    '<lf-option id="foot-keep">Keep it</lf-option>'
    '<lf-option id="foot-change">Change it</lf-option>'
    "</lf-options></lf-decision></main>",
)

# The band the line stands in, and the room the document keeps for it. `footprint` is the
# whole of what the line takes at the foot of the window — its height plus every inset
# holding it off that foot — and `reserved` is what syncLayout gives up for it.
FOOT_ROOM = """() => {
  const line = document.querySelector('.lf-keyline').getBoundingClientRect();
  const box = document.getElementById('foot-change').getBoundingClientRect();
  const chrome = document.querySelector('.lf-chrome');
  const s = document.scrollingElement;
  return {
    atEnd: s.scrollTop + s.clientHeight >= s.scrollHeight - 1,
    lineHeight: line.height,
    footprint: document.documentElement.clientHeight - line.top,
    reserved: parseFloat(getComputedStyle(chrome).paddingBottom),
    clearance: line.top - box.bottom,
  };
}"""

# Where the line's chips are, and where its one real control is. The band is the whole
# fixed box; More is the only part of it that answers a press, so a hit test aimed at the
# page has to be aimed past it. Both are read from the rendered boxes rather than stated,
# because the chips' width is the register's answer for the current scene.
UNDER_THE_LINE = """(id) => {
  const line = document.querySelector('.lf-keyline').getBoundingClientRect();
  const more = document.querySelector('.lf-key-more').getBoundingClientRect();
  const el = document.getElementById(id);
  const box = el.getBoundingClientRect();
  const left = Math.max(line.left, box.left);
  const right = Math.min(more.left, box.right);
  const x = (left + right) / 2;
  const y = line.top + line.height / 2;
  const at = document.elementFromPoint(x, y);
  return {
    band: right - left,
    covered: Math.min(line.bottom, box.bottom) - Math.max(line.top, box.top),
    reaches: Boolean(at) && (el === at || el.contains(at)),
    hit: at ? at.tagName + "." + (at.className || "") : null,
    aim: {x, y}, line: {left: line.left, top: line.top, bottom: line.bottom},
    more: {left: more.left}, box: {left: box.left, right: box.right,
      top: box.top, bottom: box.bottom},
  };
}"""


def test_the_key_line_stands_in_a_band_of_its_own(browser, serve):
    """The line is fixed at the foot of the window, so what it owes the page is a band:
    room of its own where the document ends, and no press taken from what it stands over
    on the way there.

    The room was measured as the line's height alone. Its own 14px inset came out of the
    20px of air that was supposed to be left over, so the document's last line cleared the
    line by five pixels rather than twenty; over a covering sheet, which lifts the line by
    the whole height of the panel's foot, the reservation was short by that lift. The band
    from the line's top to a region's own foot is one measurement and covers every inset.

    The press is the other half. The line and its chips take no pointer events, so a
    control the line stands over on some scroll position is still a control. Its More
    button does take them, and deliberately: it is the only pointer route to the keyboard
    reference and so to the character-shortcut preference, which cannot be made to depend
    on the character key it turns off. The band is aimed past it here for that reason."""
    page, errors = open_page(browser, serve(FOOT_CONTROL_PAGE))
    control = page.locator("#foot-change")
    expect(control).to_be_visible()

    page.evaluate(
        "() => { const s = document.scrollingElement; s.scrollTo({top: s.scrollHeight}); }"
    )
    page.evaluate(RENDERED)
    ended = page.evaluate(FOOT_ROOM)
    assert ended["atEnd"] and ended["lineHeight"] > 0, ended
    # The band, and the air over it. Reserving the height alone spent 14 of the 20px on
    # the line's own inset and left five, which clears and says nothing about whether the
    # reservation knows what it is reserving for.
    assert ended["reserved"] >= ended["footprint"] + 20, ended
    assert ended["clearance"] >= 20, (
        f"the document's last control ends in the key line's band: {ended}"
    )

    # A covering sheet lifts the line over the whole of its own foot, and the band grows
    # by that lift. This is where a reservation counting only the line's height parts
    # company with the line: 148px of footprint standing on 51px of reserved room.
    resized(page, 420, 900)
    page.get_by_role("button", name=re.compile("^Threads")).click()
    page.evaluate(RENDERED)
    covered = page.evaluate(FOOT_ROOM)
    # The lift is what this phase is about, so it has to have happened: without it the
    # footprint is the resting one and the reservation below is the resting question again.
    assert covered["footprint"] > ended["footprint"] + 20, (
        f"the sheet never lifted the line, so the reservation is untested here: {covered}"
    )
    assert covered["reserved"] >= covered["footprint"] + 20, (
        f"the sheet lifted the line off a reservation that never heard about it: {covered}"
    )
    page.keyboard.press("Escape")

    # And where the reader is not at the end, the line is standing over the page. The
    # control keeps the press: the chips are painted, not pressable. Narrow, because that
    # is where the chips and the reading column share room at all — at 1200 the column
    # starts to the right of them and it is More that overhangs its first few pixels.
    resized(page, 520, 800)
    page.evaluate(
        """() => {
          const line = document.querySelector('.lf-keyline').getBoundingClientRect();
          const box = document.getElementById('foot-change').getBoundingClientRect();
          scrollBy(0, box.top + box.height / 2 - (line.top + line.height / 2));
        }"""
    )
    page.evaluate(RENDERED)
    under = page.evaluate(UNDER_THE_LINE, "foot-change")
    assert under["band"] > 8 and under["covered"] > 0, (
        f"the aim never reached page under the line's chips, so it proves nothing: {under}"
    )
    assert under["reaches"], (
        f"the key line took a press aimed at the control underneath it: {under}"
    )

    # More is the exception, and the one that has to stay: it is the only pointer route to
    # the reference, and so to the preference that turns character shortcuts off. A reader
    # who has turned them off cannot be asked to press `?` to get back. Asked as a press
    # rather than as a declaration, the same way the chips above were.
    expect(page.get_by_role("button", name="? more", exact=True)).to_be_visible()
    assert page.evaluate(
        """() => {
          const more = document.querySelector('.lf-key-more');
          const box = more.getBoundingClientRect();
          const at = document.elementFromPoint(box.left + box.width / 2,
                                               box.top + box.height / 2);
          return more === at || more.contains(at);
        }"""
    ), "the line's own control stopped answering a press"
    assert errors == []
    page.close()


def test_the_expanded_key_line_stands_down_for_a_page_press_and_another_command(
    browser, serve
):
    """The shelf is transient help, so either kind of onward motion folds it. The
    page-click owner handles presses outside the line, while the dispatcher folds it
    before a registered command runs."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    line = page.locator(".lf-keyline")

    page.keyboard.press("?")
    expect(line).to_have_attribute("data-lf-expanded", "true")
    page.locator("#t").click()
    expect(line).to_have_attribute("data-lf-expanded", "false")

    page.keyboard.press("?")
    expect(line).to_have_attribute("data-lf-expanded", "true")
    page.keyboard.press("g")
    expect(line).to_have_attribute("data-lf-expanded", "false")
    expect(line.locator('kbd[data-lf-key-state="pressed"]').first).to_have_text("g")
    assert errors == []
    page.close()


def test_the_walk_reaches_more_and_goes_on_after_the_line_has_repainted(browser, serve):
    """A frame passes between one Tab and the next for every reader, and none for a test.

    `renderLine` runs under `paintHere`'s frame, so it repaints the key line just after
    focus lands somewhere — including on More, the line's own button. Clearing the line
    with `textContent = ""` took More out of the document, and removing a focused element
    blurs it; it came straight back as the same node, connected, with the reader dropped
    to `body`. The button was never gone to look at and never gone from the DOM to assert
    on, so nothing but standing on it one frame later could see it.

    That is why the frame is the whole of this test. Pressed back to back the walk is
    whole, because the repaint has not run yet between the presses — the failure hid
    behind the one habit every browser test has. So each press waits two frames, and the
    contrast is against the same walk pressed fast: they have to agree.

    Reaching More is the claim, and going on past it is the other half — a walk that
    loses focus to `body` does not stop, it silently restarts, and a reader tabbing
    through their own page never gets past the banner."""
    page, errors = open_page(browser, serve(NOTED_PAGE, comments=2))
    who = """() => {
      let e = document.activeElement;
      while (e?.shadowRoot?.activeElement) e = e.shadowRoot.activeElement;
      return e === document.body ? 'body' : (e?.className || e?.tagName || 'null');
    }"""

    walks = {}
    for settled in (False, True):
        # Start each walk from the page rather than from the last control in the
        # previous walk. Blurring preserves that control as the sequential focus
        # starting point, which only happened to wrap before the page gained a visual
        # reaction proxy as its first Tab stop.
        page.evaluate("() => document.body.focus()")
        trail = []
        for _ in range(24):
            page.keyboard.press("Tab")
            if settled:
                page.evaluate(RENDERED)
            trail.append(page.evaluate(who))
        walks["frame" if settled else "fast"] = trail

    # The two walks have to be the same walk. A count of lost stops would need a
    # threshold, and there is no honest one: this page's order is three controls and a
    # wrap, so a `body` every fourth press is the walk working. What says focus was lost
    # is that waiting changed where the presses went.
    assert walks["fast"] == walks["frame"], (
        "a frame between presses changed the tab order:\n"
        f"  fast  {walks['fast']}\n  frame {walks['frame']}"
    )
    for how, trail in walks.items():
        assert any("lf-key-more" in at for at in trail), (
            f"tabbing {how}, the walk never stood on More in 24 presses: {trail}"
        )

    # Standing on More, the repaint must leave the reader on it.
    page.evaluate("() => document.activeElement?.blur()")
    for _ in range(24):
        page.keyboard.press("Tab")
        if page.evaluate(
            "() => document.activeElement?.classList?.contains('lf-key-more')"
        ):
            break
    expect(page.locator(".lf-key-more")).to_be_focused()
    page.evaluate(RENDERED)
    expect(page.locator(".lf-key-more")).to_be_focused()

    assert errors == []
    page.close()


def test_a_page_at_rest_repaints_the_key_line_only_when_the_state_moves(browser, serve):
    """A repaint that schedules the next one is a loop no surface reports.

    `paintCoreControls` runs inside `paintHere` and writes what the More control
    currently says, `aria-expanded` among it. The runtime watches `open` and
    `aria-expanded` over the whole document, because those two attributes are how both
    spellings of a disclosure keep which way they stand, and it repaints the line for
    either. So the paint delivered its own write back to itself and asked for another
    frame, and the page went on repainting for as long as it was open — every browser
    test on every page paying for it, which is where it showed: the nightly suite ran
    half again as long and the run went over its bound with a fifth of the tests unread.

    Nothing on screen says so, which is why the reading is the page's own frames against
    its own state applications. Every application repaints the line and says so through
    `lf-actions`, the heartbeat's re-application of state the page already holds
    included, so a line that repaints more often than the state moves is repainting for
    a reason the page has not got."""
    page, errors = open_page(browser, serve(NOTED_PAGE, comments=2))
    page.evaluate(
        """() => {
          const probe = { frames: 0, paints: 0, applied: 0 };
          window.__lfProbe = probe;
          document.addEventListener("lf-actions", () => { probe.applied += 1; });
          new MutationObserver(() => { probe.paints += 1; }).observe(
            document.querySelector(".lf-keyline"),
            { attributes: true, childList: true, subtree: true },
          );
          const tick = () => { probe.frames += 1; requestAnimationFrame(tick); };
          requestAnimationFrame(tick);
        }"""
    )
    # The window is the page's own frames rather than a duration: a loop of this shape
    # repaints once per frame whatever the machine's speed, so counting frames is what
    # makes the contrast the same size on a loaded runner as on a desk.
    page.wait_for_function("() => window.__lfProbe.frames >= 90")
    probe = page.evaluate("() => window.__lfProbe")

    assert probe["paints"] <= probe["applied"] + 1, (
        "the key line repainted without the state moving over "
        f"{probe['frames']} frames: {probe}"
    )
    assert errors == []
    page.close()


def test_escape_backs_out_from_a_control_nothing_is_typed_into(browser, serve):
    """A scope takes the keys it uses, so a control that has no Escape of its own
    leaves the rung standing behind it. The banner's version chooser swallowed it,
    so the panel could not be closed by key right after the user worked it; the
    fix's first attempt was a two-item denylist, which an authored slider walked
    straight past. The chooser is a button now, so what holds the rule is the
    page's own controls — which is where it always mattered, a page being free to
    author any of them.

    A slider and a select answer here for the two sides of the claim. The slider
    types nothing, so the typing scope never stands over it at all; the select's
    letters jump its options, so it stands and takes them — and takes only them,
    which is what leaves this press to the page. Reaching the rung used to be a
    branch inside the typing scope's own row, restating another scope's word.

    Which rung the press reaches is the ladder's own business, and it unwinds from
    where the reader is: standing out on the page, the first thing they are in is
    the control they are standing on, and the panel behind them is a layer they are
    not in. So the press takes two — and the panel closing on the second is the
    whole of what this test is about, the control having had every chance to
    swallow the first."""
    html = NOTED_PAGE.replace(
        "</main>",
        '<input id="zoom" type="range">'
        '<select id="pick"><option>one</option><option>two</option></select></main>',
    )
    page, errors = open_page(browser, serve(html))
    # The mouse opens between rounds because c is the select's own letter, and the
    # press has to be made the same way on both to be comparing anything.
    for control in ("#zoom", "#pick"):
        page.get_by_role("button", name=re.compile("^Threads")).click()
        expect(page.locator(".lf-panel")).to_be_visible()
        page.locator(control).focus()
        expect(page.locator(".lf-keyline")).to_contain_text("let go")
        page.keyboard.press("Escape")
        assert page.evaluate("() => document.activeElement === document.body")
        expect(page.locator(".lf-keyline")).to_contain_text("close threads")
        page.keyboard.press("Escape")
        expect(page.locator(".lf-panel")).to_be_hidden()
    assert errors == []
    page.close()


def test_a_control_that_types_nothing_keeps_the_pages_keyboard(browser, serve):
    """A scope claims the keys it uses and leaves the rest standing. This one used to
    claim the lot: the typing scope stood wherever focus was in a form control, on the
    reading that a letter is a keystroke there — true of a text box, false of a radio, a
    checkbox and a slider, none of which the platform ever hands a letter. So a reader
    standing on a screenshot's before/after switch lost c, the walks, the version keys and
    the reference itself, and the line went blank rather than wrong, which is how it
    reaches its author as "the keyboard stopped working".

    One key had already been rescued from that swallow by hand, in a branch inside the
    typing scope's own row. Every other key it took stayed taken, and that is what says the
    swallow was the wrong shape rather than one key short.

    The claim has to hold in both directions or it has bought nothing, so the control's
    own key is asserted beside the page's: a page whose keyboard stands over a radio must
    not be taking Space off it."""
    html = NOTED_PAGE.replace(
        "</main>",
        '<label><input id="flip" type="radio" name="frame"> after</label>'
        '<input id="note" type="text"></main>',
    )
    page, errors = open_page(browser, serve(html))
    line = page.locator(".lf-keyline")
    # Two page rows, because the claim is the whole keyboard rather than one key: `c` is
    # painted at rest, and the movement row is one `?` further in. A scope that swallowed
    # the page would take both, and the box below is where both go.
    comment = line.locator('.lf-key:not([hidden])[data-lf-commands~="comment.create"]')
    movement = line.locator('.lf-key:not([hidden])[data-lf-commands~="page.down"]')

    page.locator("#flip").focus()
    expect(comment).to_have_count(1)
    page.keyboard.press("?")
    expect(movement).to_have_count(1)
    expect(movement).to_have_attribute("data-lf-commands", re.compile(r"\bpage\.up\b"))
    page.keyboard.press("Escape")
    expect(page.locator("#flip")).to_be_focused()
    page.keyboard.press("Space")
    expect(page.locator("#flip")).to_be_checked()
    # The letter reaches the page, which is the whole claim; where it then goes is the
    # standing's business — a reader on the radio is standing on it, so the box that
    # opens is about it rather than about the page. Named in full, because "comment on
    # the" matches every destination this key has and would assert nothing about which.
    expect(line).to_contain_text("comment on the control")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer")).to_contain_text("flip")
    page.keyboard.press("Escape")
    expect(page.locator("#flip")).to_be_focused()

    # The box beside it, where every one of those letters is the reader's. The line
    # names none of them, which is the same register saying so.
    page.locator("#note").focus()
    expect(comment).to_have_count(0)
    expect(movement).to_have_count(0)
    page.keyboard.press("c")
    expect(page.locator("#note")).to_have_value("c")
    expect(page.locator(".lf-help")).to_be_hidden()
    page.keyboard.press("?")
    expect(page.locator("#note")).to_have_value("c?")
    expect(page.locator(".lf-help")).to_be_hidden()
    assert errors == []
    page.close()


def test_a_label_press_keeps_the_controls_keyboard_standing(browser, serve):
    """Leaf treats a label's native activation as one keyboard standing.

    Chromium moves focus through body between mousedown and native label activation.
    That intermediate state must not repaint focus-derived surfaces. The native click
    and text selection must still work."""
    html = leaf_page(
        "label focus",
        """
<h1 id="frames">Choose a frame</h1>
<lf-decision id="first-question-decision"><h2>Which first frame?</h2>
<lf-options id="first-question" choose>
  <lf-option id="first-frame"><strong>First</strong>
    <label><input id="first" type="radio" name="first-frame">
      <span>first state</span></label>
  </lf-option>
  <lf-option id="neither-first-frame"><strong>Neither</strong></lf-option>
</lf-options></lf-decision>
<lf-decision id="frame-question-decision"><h2>Which next frame?</h2>
<lf-options id="frame-question" choose>
  <lf-option id="after-frame"><strong>After</strong>
    <label id="frame-label"><input id="frame" type="radio" name="frame">
      <span>after state</span></label>
  </lf-option>
  <lf-option id="before-frame"><strong>Before</strong></lf-option>
</lf-options></lf-decision>
""",
    )
    page, errors = open_page(
        browser, serve(html, anchored=[("frames", "Choose a frame")])
    )
    first = page.locator("#first")
    control = page.locator("#frame")
    words = page.locator("#frame-label span")
    first.focus()
    standing = key_line(page)
    assert "let go" in standing
    expect(page.locator("#first-question-decision[data-lf-decision]")).to_have_count(1)

    # A secondary contact does not drive native label activation, so it must not
    # start the logical transaction either.
    page.evaluate(
        """() => {
          const init = {bubbles: true, composed: true, pointerId: 98,
                        pointerType: 'touch', isPrimary: false, button: 0};
          document.querySelector('#frame-label').dispatchEvent(
            new PointerEvent('pointerdown', init)
          );
          document.activeElement.blur();
        }"""
    )
    assert "let go" not in key_line(page)
    page.evaluate(
        """() => dispatchEvent(new PointerEvent('pointerup', {
          bubbles: true, composed: true, pointerId: 98,
          pointerType: 'touch', isPrimary: false, button: 0
        }))"""
    )
    first.focus()
    assert key_line(page) == standing

    bounds = words.bounding_box()
    assert bounds is not None
    middle = (bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2)
    page.mouse.move(*middle)
    page.mouse.down()
    page.evaluate(
        """() => {
          const init = {bubbles: true, composed: true, pointerId: 99,
                        pointerType: 'touch', isPrimary: true, button: 0};
          document.body.dispatchEvent(new PointerEvent('pointerdown', init));
          dispatchEvent(new PointerEvent('pointerup', init));
        }"""
    )
    assert key_line(page) == standing
    held_decision = page.locator("#first-question-decision[data-lf-decision]")
    expect(held_decision).to_have_count(1)
    expect(held_decision).to_have_css("--lf-here-ring", "decision")
    page.mouse.up()
    expect(control).to_be_checked()
    expect(control).to_be_focused()
    expect(page.locator("#frame-question-decision[data-lf-decision]")).to_have_count(1)

    # The press has its own frame and the drag comes after it, so the line's only route
    # to the word is the selection the drag makes: the reader is taking words out of a
    # label, and from the first glyph Escape clears that selection rather than letting
    # go of the control. Framed the other way round the press's frame painted the line
    # after the drag had already run, and the word arrived whether or not anything
    # followed the selection.
    hold_selection(
        page,
        (bounds["x"] + 2, middle[1]),
        (bounds["x"] + bounds["width"] - 2, middle[1]),
        steps=10,
        frame_the_press=True,
    )
    assert "after state" in page.evaluate("() => getSelection().toString()")
    assert "unselect" in key_line(page)
    page.mouse.up()
    assert "let go" not in key_line(page)

    # A focused thread has a runtime-owned scope outside the generic control register.
    # It reads the same logical focus while the press moves toward the label's control.
    page.evaluate("() => getSelection().removeAllRanges()")
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    thread = page.locator(".lf-threads > .lf-thread")
    thread.focus()
    thread_standing = key_line(page)
    assert "reply" in thread_standing
    bounds = words.bounding_box()
    assert bounds is not None
    page.mouse.move(
        bounds["x"] + bounds["width"] / 2, bounds["y"] + bounds["height"] / 2
    )
    page.mouse.down()
    assert key_line(page) == thread_standing
    expect(thread).to_have_css("--lf-here-ring", "thread")
    page.mouse.up()
    assert "reply" not in key_line(page)
    assert errors == []
    page.close()


def test_the_other_response_row_can_turn_the_compact_field_into_a_suggestion(
    browser, serve
):
    """A selected passage offers Suggest without reopening the retired composer card."""
    page, errors = open_page(browser, serve(INLINE_PAGE))
    page.locator("#p").click(click_count=3)
    box = page.locator(".lf-fab-input")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(box).not_to_be_focused()
    page.keyboard.press("c")
    expect(box).to_be_focused()
    expect(box).to_have_attribute(
        "placeholder", re.compile(r"^Comment… .*(⌘⏎|Ctrl\+⏎)$")
    )

    page.keyboard.press("Tab")
    choices = page.locator(".lf-fab-bar")
    suggest = choices.locator(".lf-fab-suggest")
    expect(choices).to_be_visible()
    expect(choices.locator(".lf-fab")).to_be_focused()
    page.keyboard.press("Tab")
    expect(suggest).to_be_focused()

    page.keyboard.press("Enter")
    expect(box).to_be_focused()
    expect(box).to_have_attribute(
        "placeholder", re.compile(r"^Replacement text .*(⌘⏎|Ctrl\+⏎)$")
    )
    expect(box).to_have_value(
        re.compile("A paragraph carrying bold text and emphasis inside it")
    )
    page.evaluate(RENDERED)
    expect(box).to_have_attribute(
        "placeholder", re.compile(r"^Replacement text .*(⌘⏎|Ctrl\+⏎)$")
    )
    assert errors == []
    page.close()


def test_a_passage_selection_keeps_native_copy_and_context_menu(browser, serve):
    """Leaf may offer a response without taking the browser's selection gestures."""
    context = browser.new_context(
        viewport={"width": 1200, "height": 900},
        permissions=["clipboard-read", "clipboard-write"],
    )
    try:
        page, errors = open_page(browser, serve(INLINE_PAGE), context=context)
        paragraph = page.locator("#p")
        paragraph.click(click_count=3)
        expect(page.locator(".lf-fab-bar")).to_be_visible()

        selected = page.evaluate("() => getSelection().toString()")
        assert "A paragraph carrying" in selected
        is_mac = page.evaluate(
            "() => /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)"
        )
        page.keyboard.press("Meta+c" if is_mac else "Control+c")
        assert page.evaluate("() => navigator.clipboard.readText()") == selected

        page.evaluate(
            """() => {
              window.lfContextMenu = null;
              document.addEventListener('contextmenu', event => {
                setTimeout(() => {
                  window.lfContextMenu = {
                    prevented: event.defaultPrevented,
                    selection: getSelection().toString(),
                  };
                });
              }, {capture: true, once: true});
            }"""
        )
        paragraph.click(button="right")
        page.wait_for_function("() => window.lfContextMenu !== null")
        assert page.evaluate("() => window.lfContextMenu") == {
            "prevented": False,
            "selection": selected,
        }
        assert errors == []
        page.close()
    finally:
        context.close()


def test_focus_paint_releases_every_text_box_crossed_before_a_frame(browser, serve):
    """A synchronous input sync cannot hide an intermediate focus from repaint."""
    page, errors = open_page(browser, serve(INLINE_PAGE, comments=2))
    page.locator(".lf-threads-toggle").click()
    general = page.locator(".lf-general textarea")
    replies = page.locator(".lf-thread textarea")
    general.focus()
    key_line(page)
    assert re.search(r"(⌘⏎|Ctrl\+⏎)$", general.get_attribute("placeholder"))

    # Cross A -> B (and sync B) -> C in one turn, before the coalesced focus paint.
    replies.evaluate_all(
        """boxes => {
          boxes[0].focus();
          boxes[0].dispatchEvent(new Event('input', {bubbles: true}));
          boxes[1].focus();
        }"""
    )
    key_line(page)
    assert general.get_attribute("placeholder") == "Comment on the page · c"
    assert replies.nth(0).get_attribute("placeholder") == "Reply"
    assert re.search(r"(⌘⏎|Ctrl\+⏎)$", replies.nth(1).get_attribute("placeholder"))
    assert errors == []
    page.close()


def test_the_key_line_names_the_selected_comment_and_its_other_responses(
    browser, serve
):
    """Comment enters a selected passage's field; the line names send and Tab exit."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))
    line = page.locator(".lf-keyline")
    help_el = page.locator(".lf-help")

    # Nothing in hand: c names and enters the page comment directly.
    expect(line).to_contain_text("comment on the page")
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(help_el).to_contain_text("Comment on the page")
    page.keyboard.press("Escape")

    # A real selection keeps the browser selection until Comment explicitly enters its
    # field. Once there, letters and `?` belong to the comment rather than falling through
    # to page shortcuts.
    box = page.locator("#prose").bounding_box()
    select(
        page,
        (box["x"] + 1, box["y"] + 4),
        (box["x"] + box["width"] - 1, box["y"] + box["height"] - 4),
        steps=12,
    )
    field = page.locator(".lf-fab-input")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(field).not_to_be_focused()
    page.keyboard.press("c")
    expect(field).to_be_focused()
    expect(line).to_contain_text("comment")
    expect(line).to_contain_text("other responses")
    page.keyboard.type("?")
    expect(field).to_have_value("?")
    page.keyboard.press("Escape")

    # An explicit visual target follows the same contract, but its accessible field name
    # identifies the item rather than a quoted passage.
    page.locator("#fig svg").click(modifiers=["Alt"])
    expect(field).to_be_focused()
    expect(field).to_have_attribute("aria-label", re.compile("figure"))
    expect(line).to_contain_text("other responses")
    page.keyboard.press("Escape")

    assert errors == []
    page.close()


def test_typing_in_a_selected_comment_wins_over_page_shortcuts(browser, serve):
    """Once Comment focuses a selected passage's field, shortcut letters are text."""
    page, errors = open_page(browser, serve(TARGETS_PAGE))

    box = page.locator("#prose").bounding_box()
    select(
        page,
        (box["x"] + 1, box["y"] + 4),
        (box["x"] + box["width"] - 1, box["y"] + box["height"] - 4),
        steps=12,
    )
    fab = page.locator(".lf-fab-input")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(fab).not_to_be_focused()
    page.keyboard.press("c")
    expect(fab).to_be_focused()
    page.keyboard.press("c")
    expect(fab).to_have_value("c")
    page.keyboard.press("Escape")
    page.evaluate("() => document.body.focus()")

    version = page.locator(".lf-version")
    version.evaluate(
        """control => control.addEventListener('click', () => {
          control.dataset.shortcutClicks =
            String(Number(control.dataset.shortcutClicks || 0) + 1);
        })"""
    )
    open_versions(page)
    expect(page.locator(".lf-version-menu")).to_be_visible()
    expect(version).to_have_attribute("data-shortcut-clicks", "1")
    page.keyboard.press("Escape")

    page.keyboard.press("?")
    page.keyboard.press("?")
    reference = page.locator(".lf-help")
    close = page.locator(".lf-help-close")
    expect(reference).to_be_visible()
    close.evaluate(
        """control => control.addEventListener('click', () => {
          control.dataset.shortcutClicks =
            String(Number(control.dataset.shortcutClicks || 0) + 1);
        })"""
    )
    page.keyboard.press("Escape")
    expect(reference).to_be_hidden()
    expect(close).to_have_attribute("data-shortcut-clicks", "1")

    assert errors == []
    page.close()


def test_submit_shortcuts_activate_the_controls_that_promise_the_action(browser, serve):
    """Every durable editor inserts a newline with Enter and sends with Mod+Enter."""
    html = TARGETS_PAGE.replace(
        "</main>", '<lf-draft id="plan"><pre>Ship it.</pre></lf-draft></main>'
    )
    page, errors = open_page(browser, serve(html))

    box = page.locator("#prose").bounding_box()
    select(
        page,
        (box["x"] + 1, box["y"] + 4),
        (box["x"] + box["width"] - 1, box["y"] + box["height"] - 4),
        steps=12,
    )
    composer = page.locator(".lf-composer")
    field = page.locator(".lf-fab-input")
    expect(page.locator(".lf-fab-bar")).to_be_visible()
    expect(field).not_to_be_focused()
    page.keyboard.press("c")
    expect(field).to_be_focused()
    send = composer.locator(".lf-composer-row .primary")
    send.evaluate(
        """control => control.addEventListener('click', () => {
          document.body.dataset.composerShortcutClicks =
            String(Number(document.body.dataset.composerShortcutClicks || 0) + 1);
        })"""
    )
    field.fill("Send through the compact control.")
    page.keyboard.press("Enter")
    assert page.locator("body").get_attribute("data-composer-shortcut-clicks") is None
    expect(field).to_have_value("Send through the compact control.\n")
    expect(field).to_have_attribute("aria-keyshortcuts", "Meta+Enter Control+Enter")
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator("body")).to_have_attribute("data-composer-shortcut-clicks", "1")
    expect(composer).to_be_hidden()

    controls = page.locator(".lf-draft-controls[data-lf-for='plan']")
    controls.get_by_role("button", name="Edit").click()
    editor = page.locator("#plan textarea")
    editor.fill("Save through the visible control.")
    save = controls.get_by_role("button", name="Save")
    save.evaluate(
        """control => control.addEventListener('click', () => {
          document.body.dataset.draftShortcutClicks =
            String(Number(document.body.dataset.draftShortcutClicks || 0) + 1);
        })"""
    )
    page.keyboard.press("ControlOrMeta+Enter")
    expect(page.locator("body")).to_have_attribute("data-draft-shortcut-clicks", "1")
    expect(page.locator("#plan .lf-draft-body")).to_have_text(
        "Save through the visible control."
    )

    round_trip(page)
    assert errors == []
    page.close()


def test_a_key_on_screen_is_a_key_that_works(browser, serve):
    """Every surface naming a key promises the press does something now. One table
    kept the words from drifting and not the surfaces: the key line asked `when`,
    the ? overlay didn't, and a shortcut could hold its liveness where no surface
    could ask — inside its own run — so the overlay offered g 1–9 with no thread to
    reply to, and named a walk through a list of one. Liveness is one declaration,
    and the dispatcher, the line, and the overlay all ask it. The chord's lists are
    where that division earns its keep twice over: a list the page hasn't got is a
    row the reference must not name, and the section holds only what this page can
    answer — the edges always among them, every page having a top. Its rows carry the
    complete chord, so no heading has to supply a key the row itself omits."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir
    page, errors = open_page(browser, live_url(url))
    help_el = page.locator(".lf-help")

    # No open threads, one version: the reference names only what a press would do.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    # Nothing is selected and the reader is standing nowhere, so c's own row names the
    # page comment it enters. Threads navigation remains the separate g T command.
    expect(help_el).to_contain_text("Comment on the page")
    # The chord's section stands on every page — the edges need no list — but holds
    # no row for a list this page hasn't got. Each row says the whole press from the
    # standing page rather than asking its heading to supply the first g.
    expect(help_el.get_by_role("heading", name="Go to", exact=True)).to_be_visible()
    expect(
        help_el.locator("tr", has_text="top of the page").locator(
            ".lf-key-sequence > kbd"
        )
    ).to_have_text(["g", "g"])
    expect(
        help_el.locator("tr", has_text="bottom of the page").locator(
            ".lf-key-sequence > kbd"
        )
    ).to_have_text(["g", "G"])
    expect(
        help_el.locator("tr", has_text="bottom of the page").locator(".lf-key-sequence")
    ).to_have_attribute("aria-label", "g then Shift+g")
    versions_route = help_el.locator(
        'tr[data-lf-command="version.open"] .lf-key-sequence'
    )
    expect(versions_route.locator("kbd")).to_have_text(["g", "V"])
    expect(versions_route).to_have_attribute("aria-label", "g then Shift+v")
    chord_control = help_el.locator('tr[data-lf-command="navigation.address.back"]')
    expect(chord_control).to_have_class(re.compile(r"\blf-chord-control\b"))
    expect(chord_control.locator("td").first).to_have_css("border-top-style", "solid")
    expect(help_el).not_to_contain_text("open comment's reply box")
    # And no link scope: this page holds none, while the machine's own tray is full of
    # them — a scope asked about the document at large was had by every page there is.
    expect(help_el).not_to_contain_text("On a link")
    expect(help_el).not_to_contain_text("Next open thread")
    expect(help_el).not_to_contain_text("Previous open thread")
    expect(help_el).not_to_contain_text("On a focused thread")
    expect(help_el).not_to_contain_text("waiting on you for")
    # A first version has a useful chooser but no neighbouring version to walk. Escape is
    # the popover's native dismissal and therefore is not a Leaf shortcut row.
    expect(help_el).to_contain_text("The versions, and what each one changed")
    expect(help_el).not_to_contain_text("Close the versions menu")
    expect(help_el).not_to_contain_text("Previous version")
    expect(help_el).not_to_contain_text("Next version")
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()

    # The dispatcher asks the same declaration: neither half of the pair runs while
    # there is no thread to walk.
    page.keyboard.press("t")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-panel")).to_be_hidden()
    line = page.locator(".lf-keyline")
    expect(line).not_to_contain_text("t / T")

    # Threads arrive, making both the category walk and the Threads panel useful.
    for text in ["A thread.", "Another."]:
        events_model.append_event(
            d, {"kind": "comment", "author": "user", "revision": 1, "text": text}
        )
    told(page)
    expect(page.locator(".lf-thread")).to_have_count(2)
    # The key line repaints on the same render that made them live — no focus
    # change to lean on, so the repaint is the thread render's own.
    expect(line).to_contain_text("threads")
    page.keyboard.press("?")
    expect(
        help_el.locator("tr", has_text="Go to the Threads panel").locator(
            ".lf-key-sequence > kbd"
        )
    ).to_have_text(["g", "T"])
    expect(
        help_el.locator("tr", has_text="Go to the Threads panel").locator(
            ".lf-key-sequence"
        )
    ).to_have_attribute("aria-label", "g then Shift+t")
    expect(help_el).not_to_contain_text("link on screen")
    expect(help_el).not_to_contain_text("waiting on you for")
    expect(help_el).to_contain_text("Next open thread")
    expect(help_el).to_contain_text("Previous open thread")
    expect(
        help_el.locator("tr", has_text="Next open thread").locator("kbd")
    ).to_have_text("t")
    expect(
        help_el.locator("tr", has_text="Previous open thread").locator("kbd")
    ).to_have_text("T")
    expect(help_el).to_contain_text("On a focused thread")
    # Still one version, so there is no version walk to advertise.
    expect(help_el).not_to_contain_text("Close the versions menu")
    expect(help_el).not_to_contain_text("Previous version")
    expect(help_el).not_to_contain_text("Next version")
    page.keyboard.press("Escape")

    # A v2 lands and the live page follows it; on v2 the menu's own keys are
    # live, having a list to walk and a base to walk onto.
    (d / ".fixture-versions" / "v2.html").write_text(NOTED_PAGE)
    stamp_version_file(d, 2, "two")
    wait_for_revision(page, 2)
    expect(page.locator('.lf-version-diff[data-lf-version="1"]')).to_have_count(1)
    expect(page.locator(".lf-version-menu")).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown Enter Space v"
    )
    page.keyboard.press("?")
    expect(help_el).to_contain_text("In the versions menu")
    expect(help_el).to_contain_text("Previous version")
    expect(help_el).to_contain_text("Next version")
    page.keyboard.press("Escape")

    # A resolved thread stays focusable after the last open one is gone, and the
    # scene branch that restates the t/T row over it asks the same liveness.
    page.keyboard.press("c")
    for n in [1, 2]:
        page.locator(".lf-threads > .lf-thread").first.get_by_role(
            "button", name="Resolve"
        ).click()
        expect(page.locator(".lf-details summary")).to_have_text(f"Resolved ({n})")
    # The summary counts the log before the disclosure finishes folding its list.
    expect(page.locator(".lf-details .lf-thread")).to_have_count(2)
    page.locator(".lf-details summary").click()
    resolved = page.locator(".lf-details .lf-thread").first
    resolved.click()
    expect(resolved).to_be_focused()
    expect(line).to_contain_text("close threads")
    expect(line).not_to_contain_text("t / T")

    # And no disclosure scope, with the panel's own <details> standing open beside the
    # reader. A capability is what they can reach from where the scope holds, and this box
    # is the chrome's — it declares the keys it answers itself. Asked of the document at
    # large, the scope arrives on every page that has ever had a comment resolved.
    expect(page.locator(".lf-details[open]")).to_have_count(1)
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    expect(help_el).not_to_contain_text("On a disclosure")
    page.keyboard.press("Escape")
    assert errors == []
    page.close()


def test_the_resolve_key_changes_the_focused_threads_resolution(browser, serve):
    """x changes the resolution of the thread the reader is standing on.

    It resolves the thread t/T landed on through the button's own press, so
    focus lands where the button already sends it — on the thread that takes the
    resolved one's place. On a resolved thread the same state key reopens it, while
    Enter performs that thread's available primary action: reply when open and reopen
    when resolved."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir

    def comment(text):
        return events_model.append_event(
            d, {"kind": "comment", "author": "user", "revision": 1, "text": text}
        )["id"]

    c1 = comment("First thought.")
    c2 = comment("Second thought.")
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 2")
    line = page.locator(".lf-keyline")

    def tab_to(target, limit=40):
        for _ in range(limit):
            page.keyboard.press("Tab")
            if target.evaluate("node => node === document.activeElement"):
                return
        raise AssertionError("Tab did not reach the expected control")

    # At page scope nothing promises x — its target is the focused thread, and
    # none is — while the overlay teaches the capability, scope in its words.
    expect(line).not_to_contain_text("resolve")
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_contain_text("On a focused thread")
    expect(page.locator(".lf-help")).to_contain_text("Resolve it")
    focused_section = page.locator(".lf-help-section").filter(
        has=page.get_by_role("heading", name="On a focused thread", exact=True)
    )
    expect(focused_section.get_by_text("Resolve it", exact=True)).to_have_count(1)
    page.keyboard.press("Escape")

    # t lands on the first thread and the line offers resolve; x takes it, and
    # focus lands on the thread now holding the resolved one's place, so t/T
    # and a second x walk on from there.
    page.keyboard.press("t")
    expect(page.locator(f'.lf-thread[data-id="{c1}"]')).to_be_focused()
    expect(line).to_contain_text("resolve")
    page.keyboard.press("x")
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    expect(page.locator(f'.lf-thread[data-id="{c2}"]')).to_be_focused()
    expect(line).to_contain_text("resolve")

    # The native disclosure and Reopen control put a resolved thread in the ordinary Tab
    # journey. Enter is the primary route and the same x state key is available there.
    expect(page.locator(f'.lf-details .lf-thread[data-id="{c1}"]')).to_have_count(1)
    summary = page.locator(".lf-details summary")
    tab_to(summary)
    page.keyboard.press("Enter")
    resolved = page.locator(f'.lf-details .lf-thread[data-id="{c1}"]')
    reopen_control = resolved.get_by_role("button", name="Reopen")
    tab_to(reopen_control)
    expect(reopen_control).to_be_focused()
    expect(line).to_contain_text("reopen")
    page.keyboard.press("Enter")
    round_trip(page)
    reopened = page.locator(f'.lf-threads > .lf-thread[data-id="{c1}"]')
    expect(reopened.locator(":scope > .lf-compose textarea")).to_be_focused()
    expect(line).to_contain_text("back to thread")
    page.keyboard.press("Escape")
    expect(reopened).to_be_focused()
    expect(line).to_contain_text("reply")

    # The state key is reversible from either visible state control too: Tab to Resolve,
    # resolve with x, then Tab to Reopen and use the same x to reverse it.
    resolve_control = reopened.get_by_role("button", name="Resolve")
    tab_to(resolve_control)
    expect(resolve_control).to_be_focused()
    expect(line).to_contain_text("resolve")
    page.keyboard.press("x")
    round_trip(page)
    expect(page.locator(".lf-details summary")).to_have_text("Resolved (1)")
    resolved = page.locator(f'.lf-details .lf-thread[data-id="{c1}"]')
    reopen_control = resolved.get_by_role("button", name="Reopen")
    tab_to(reopen_control)
    expect(reopen_control).to_be_focused()
    page.keyboard.press("x")
    round_trip(page)
    expect(reopened.locator(":scope > .lf-compose textarea")).to_be_focused()
    assert errors == []
    page.close()


def test_escape_on_a_declaring_control_does_exactly_what_it_says(browser, serve):
    """One press is one action: the rung is the innermost scope in reach that binds
    Escape, and the dispatcher runs that one and no other. The draft editor's Esc used
    to be two — the edit cancelled and the runtime's ladder closed the panel behind it
    — and the cancel discarded the user's words against the never-lose-text norm. Each
    control kept that by hand once and the stack keeps it now, so this is the test that
    says the structure holds. The editor closes keeping the edit, the panel stands, and
    a grabbed card's Esc cancels the move and nothing else."""
    html = BOARD_PAGE.replace(
        "</main>", '<lf-draft id="plan"><pre>Ship it.</pre></lf-draft></main>'
    )
    url = serve(html)
    events_model.append_event(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "A thread."},
    )
    page, errors = open_page(browser, url)
    page.wait_for_function("() => document.querySelectorAll('.lf-thread').length === 1")
    page.keyboard.press("c")  # panel open, so the old second action would show
    expect(page.locator(".lf-panel")).to_be_visible()

    page.locator(".lf-draft-controls .lf-draft-pencil").click()
    ta = page.locator("lf-draft textarea")
    expect(ta).to_be_focused()
    ta.fill("Ship it — but louder.")
    page.keyboard.press("Escape")
    expect(ta).to_have_count(0)  # the editor closed…
    expect(page.locator(".lf-panel")).to_be_visible()  # …and only the editor
    # The edit was set aside, not discarded: reopening resumes it.
    page.locator(".lf-draft-controls .lf-draft-pencil").click()
    expect(page.locator("lf-draft textarea")).to_have_value("Ship it — but louder.")
    page.keyboard.press("Escape")

    # A grabbed card: Esc cancels the move, and the panel it would have closed stands.
    grip = page.locator("#card-heater .lf-grip")
    grip.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".lf-keyline")).to_contain_text("cancel the move")
    # The contract's flip side: the chord refuses to arm over a control that has
    # claimed Escape, or one press would have two owners — the grip consuming it,
    # the chord promising its cancel.
    page.keyboard.press("g")
    # No blue pressed key appears, which proves the chord refused to arm even if the
    # ordinary line happens to reuse one of its words.
    expect(page.locator('.lf-keyline kbd[data-lf-key-state="pressed"]')).to_have_count(
        0
    )
    expect(page.locator(".lf-keyline")).to_contain_text("cancel the move")
    page.keyboard.press("Escape")
    # The grab is over (an uncancelled one would also leave the card in Todo),
    # the line is back to the resting grip, and the panel the ladder would have
    # closed stands.
    expect(page.locator(".lf-lift")).to_have_count(0)
    expect(page.locator(".lf-keyline")).to_contain_text("grab the card")
    expect(page.locator("#col-todo #card-heater")).to_have_count(1)
    expect(page.locator(".lf-panel")).to_be_visible()
    assert errors == []
    page.close()


def test_c_comments_on_what_the_reader_is_standing_in(browser, serve):
    """Focus supplies an element anchor. `c` once read the 💬 alone, so a reader
    working from the keys had two destinations where explicit pointer targeting had
    three: an item, a quote, or the whole page. A
    focused link put them on an option and the box that opened still said "Comment on the
    page" — the ⌥ aim's "the item under the pointer" with no twin for the cursor.

    Where they are standing is the unanswered decision first, because that is what the page
    has already told them: markHere rings the whole ask when a/A lands on its control.
    Below a decision it is the innermost item, which is the aim's own reading — so a focused
    link speaks for the paragraph holding it, no id of its own being what an anchor needs.

    One box either way: `commentOnTarget` writes `{section: item.id}`, which is the anchor a
    widget's own conversation seat collects, so a remark made here lands in that seat's
    conversation rather than beside it. Reaching for the seat directly instead was five
    questions — escaping an author's id, whether the box can take focus, which box when
    the seat holds several, what design mode files, where the reader already stood — for
    a focus landing.

    The control is the same press from the same page with the reader standing nowhere in
    it, where `c` opens the page-comment box rather than this item's composer. Without it a
    green here would follow just as well from a composer that opened on everything.

    Focus is dropped between the phases rather than backed out of, because each press
    lands the reader in a box and the typing scope owns the letter there."""
    page, errors = open_page(browser, serve(WHERE_I_STAND_PAGE))
    line = page.locator(".lf-keyline")

    def drop():
        if (
            page.locator(".lf-composer[data-lf-open]").count()
            or page.locator(".lf-general textarea:focus").count()
        ):
            page.keyboard.press("Escape")
        page.evaluate("() => document.activeElement?.blur()")

    # Standing nowhere in the page: the page itself is the contextual target.
    expect(line).to_contain_text("comment on the page")
    page.keyboard.press("c")
    expect(page.locator(".lf-general textarea")).to_be_focused()
    drop()

    # A decision: the composer opens on the question rather than on the option the
    # walk happens to stand the reader on, and rather than on the page.
    page.keyboard.press("a")
    expect(page.locator("#shape-decision")).to_have_attribute("data-lf-decision", "1")
    expect(line).to_contain_text("comment on the decision")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer")).to_contain_text("decision")
    drop()

    # A settled group: not a decision at all, and the conversation seat it still holds is
    # inside `hidden="until-found"`, so a press that reached into the seat focused a box
    # that cannot take focus and did nothing at all. Named by its own words rather than by
    # "options", which the composer standing open from the phase above already says — an
    # assertion true before the press is no assertion about the press.
    page.locator("#settled .lf-settled").focus()
    expect(line).to_contain_text("comment on the options")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_contain_text("Decided last week")
    drop()

    # A decision with no seat: focus on its action names the rewrite, and the composer
    # anchors there rather than on the page.
    page.evaluate(RENDERED)
    rewrite_action = page.locator('[data-lf-margin-for="sug-window"] .lf-sug-accept')
    rewrite_action.focus()
    expect(rewrite_action).to_be_focused()
    expect(page.locator("#sug-window")).to_have_attribute("data-lf-decision", "1")
    expect(line).to_contain_text("comment on the rewrite")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    expect(page.locator(".lf-composer")).to_contain_text("rewrite")
    drop()

    # A link inside a question, open and settled: the same markup, and the same answer.
    # Standing in a decision is not working one — a reader who focused a link has named
    # something more particular than the question around it, and answering the question
    # there both overrode what they named and made the reply turn on whether that question
    # happened to be open. The settled one is the contrast that shows it was the openness
    # doing it: it always said "option", and the open one used to say "options".
    for expected_id in ("sh-steel", "st-keep"):
        drop()
        page.evaluate(RENDERED)
        if expected_id == "st-keep":
            settled = page.locator("#settled .lf-settled")
            settled.click()
            expect(settled).to_have_attribute("aria-expanded", "true")
        link = page.locator(f"#{expected_id} a")
        link.focus()
        expect(link).to_be_focused()
        expect(line).to_contain_text("comment on the option")
        page.keyboard.press("c")
        expect(page.locator(".lf-composer")).to_be_visible()
        assert page.evaluate(
            "() => document.querySelector('.lf-composer blockquote')?.textContent ?? ''"
        ).startswith("§ option · "), "the box named the question, not the option"
        drop()

    # Below any ask, the innermost item: the paragraph the focused link sits in.
    page.evaluate(RENDERED)
    passage_link = page.locator("#p1 a")
    passage_link.focus()
    expect(passage_link).to_be_focused()
    expect(line).to_contain_text("comment on the paragraph")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_contain_text("paragraph")

    assert errors == []
    page.close()


def test_the_ring_holds_on_a_seat_the_agent_has_still_to_answer(browser, serve):
    """Where the reader is standing and what the reader still owes are two facts, and a
    widget mid-conversation with the agent is where they part. Its seat holds the words
    the reader just wrote, its answer is unmade and its controls are live, and it has left
    the banner and the tray because the next word there is the agent's — but the reader
    is standing in it all the same, and it is still the question they are working.

    Read off the reader's list, both the ring and `c` went with the count: the moment the
    remark was sent the ring left from under the reader, and `c` fell through from the
    question to whichever item their focus happened to rest in. That is a different
    conversation, not a shorter way into the same one — a remark on the widget is filed
    where a remark on the question the widget stands as is not — so the next line of a
    remark landed somewhere the first line was not. The agent's reply moved both back.
    Nothing the reader did moved either, which is the whole of the complaint; the reply
    phase here is what says the ring has stopped tracking the count rather than merely
    tracking it late.

    A picked group is the control on the other side. It is answered, so it is off both
    readings and must stay off: the switch is about a seat the reader is mid-sentence in,
    not about reopening what a pick has closed.

    The seat and the ask are the project widget SEATED_ASK_ENTRY declares, for the reason
    test_a_seat_conversation_leaves_the_pick_it_is_about_live gives: the split is between
    two declarations, and since 292de9c no shipped entry carries both."""
    url = serve(
        leaf_page(
            "mid-sentence",
            """
<h1 id="t">Mid-sentence</h1>
<lf-decision id="shape-decision"><h2>Galvanised steel for the frame?</h2>
<lf-verdict id="shape" asks>Drop-in, and it needs no sealing.</lf-verdict></lf-decision>
<lf-decision id="picked-decision"><h2>Should we keep it?</h2>
<lf-options id="picked" choose>
  <lf-option id="pk-keep" chosen><strong>Keep it</strong> Settled by a pick.</lf-option>
  <lf-option id="pk-drop"><strong>Drop it</strong> The alternative.</lf-option>
</lf-options></lf-decision>
<p id="p2">A passage carrying
<lf-suggestion id="sug-window">
  <lf-old>Refill every feeder each morning.</lf-old>
  <lf-new>Refill when the camera shows it half-empty.</lf-new>
</lf-suggestion></p>
""",
        ),
        layer_registry=SEATED_ASK_LAYER,
        layer_widgets=SEATED_ASK_WIDGETS,
    )
    d = serve.page_dir
    events_model.append_event(
        d,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Steel, unless the sealing is quick?",
            "anchor": {"section": "shape"},
        },
    )

    page, errors = open_page(browser, url)
    line = page.locator(".lf-keyline")
    decisions = page.locator(".lf-decisions")

    # The completion count includes every active Ask: the authored pick is complete;
    # the seated Ask and suggestion are not.
    expect(decisions).to_have_text("Asks 1/3")
    decisions.click()
    expect(page.locator("button.lf-decisions-row")).to_have_count(3)
    expect(
        page.locator('.lf-decisions-row[data-lf-at="shape-decision"]')
    ).to_have_count(1)
    expect(
        page.locator('.lf-decisions-row[data-lf-at="picked-decision"]')
    ).to_have_count(1)
    expect(page.locator('.lf-decisions-row[data-lf-at="sug-window"]')).to_have_count(1)

    # The reader is standing in it all the same — and first with the tray still open, the
    # one state where the ring has a second surface to reach: the inventory row.
    page.locator("#shape .lf-settle").focus()
    expect(page.locator("#shape-decision")).to_have_attribute("data-lf-decision", "1")
    expect(page.locator("button.lf-decisions-row")).to_have_count(3)
    expect(
        page.locator('.lf-decisions-row[data-lf-at="shape-decision"]')
    ).to_have_attribute("data-lf-decision", "1")
    page.evaluate("() => document.activeElement?.blur()")
    decisions.click()

    # And with it shut, which is every other reading below.
    page.locator("#shape .lf-settle").focus()
    expect(page.locator("#shape-decision")).to_have_attribute("data-lf-decision", "1")
    expect(line).to_contain_text("comment on the decision")
    # The count is completion, not the open walk's position, so focus leaves it stable.
    expect(decisions).to_have_text("Asks 1/3")

    # Answering hands the question back, and the count moves while the ring does not.
    # Focus is not touched again from here, so the ring read below is the one painted
    # above: blurring and coming back would re-derive it and repeat the phase instead of
    # measuring that it stayed through the news.
    #
    # The source is the reader's again once the conversation in its answer control has
    # been answered.
    for root in [
        e["id"] for e in events_model.read_events(d) if e.get("kind") == "comment"
    ]:
        events_model.append_event(
            d,
            {
                "kind": "reply",
                "author": "claude",
                "revision": 1,
                "parent": root,
                "text": "Sealing is an afternoon.",
            },
        )
    told(page)
    # Back on the reader's open list, the same Ask is still incomplete, so the
    # completion count remains stable.
    expect(decisions).to_have_text("Asks 1/3")
    expect(page.locator("#shape .lf-settle")).to_be_focused()
    expect(page.locator("#shape-decision")).to_have_attribute("data-lf-decision", "1")
    expect(line).to_contain_text("comment on the decision")
    page.evaluate("() => document.activeElement?.blur()")

    # The picked group is the control on the other side: answered, so off both readings,
    # and the switch leaves it there. Read through the key line, because `markHere` paints
    # inside `paintHere`'s frame — an absence read in the same round trip as the focus is
    # the frame before the paint, and stays green while a ring lands here a frame later.
    # The word is the other half of the same fact: with `standingIn` null the reading falls
    # through to the innermost item, which from a pick is the option and not the question.
    page.locator("#picked .lf-pick").first.focus()
    expect(line).to_contain_text(re.compile(r"comment on the option(?!s)"))
    assert page.locator("[data-lf-decision]").count() == 0, (
        "an answered group wears the ring the switch was not about"
    )

    assert errors == []
    page.close()


def test_c_in_a_thread_reaches_that_threads_own_box(browser, serve):
    """The panel's open list is the one part of the chrome that holds a conversation of
    its own, so a press meaning "say something about this" belongs to that box rather
    than to the page the panel stands over. `conversationBox` states the same rule from
    the other side when it declines to seat a widget standing inside a thread, and the
    asks and the `a`/`A` walk include the ones an agent sent — without this the same
    question answered one way on the page and another in the panel.

    A resolved thread is the case that has to be asked separately, and the reason this
    test exists at all: it is built by the same `threadNode` and wears the same class,
    under the Resolved disclosure, where it keeps a tab stop and a Reopen button. Reading
    the class alone put the reader in a thread whose reply box is not there, and the press
    died on the null with the panel's own `c` never reached. Whether there is a box is what
    tells them apart — `standingConversation` asks for one rather than for the class — so
    the resolved thread falls through to the general box, which is the honest answer for a
    thread with no box of its own to offer."""
    url = serve(PANEL_PAGE)
    d = serve.page_dir
    live = panel_comment(d, "Six weeks reads long.", {"section": "lede"})
    gone = panel_comment(d, "Settled already.", {"section": "how-cap"})
    events_model.append_event(d, {"kind": "resolve", "author": "user", "parent": gone})

    page, errors = open_page(browser, url)
    line = page.locator(".lf-keyline")

    # Threads navigation is g T; page c is reserved for the page comment.
    expect(line).to_contain_text("comment on the page")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()

    # Standing in the open thread, it means that thread's reply box. `t` walks on from
    # where the press above left the reader, no backing out of a box first.
    page.keyboard.press("t")
    expect(page.locator(f'.lf-thread[data-id="{live}"]')).to_be_focused()
    expect(line).to_contain_text("comment on the thread")
    page.keyboard.press("c")
    expect(
        page.locator(f'.lf-thread[data-id="{live}"] > .lf-compose textarea')
    ).to_be_focused()

    # And Esc gives that press back: the thread, then the panel. In the panel the old
    # class-only reading and the new climb agree, so this is the consistency half rather
    # than the gate — test_c_in_a_seated_conversation_reaches_the_thread_it_is_in is what
    # actually goes red if the climb regresses, the page being where they diverge.
    expect(line).to_contain_text("back to thread")
    page.keyboard.press("Escape")
    expect(page.locator(f'.lf-thread[data-id="{live}"]')).to_be_focused()
    expect(line).to_contain_text("back")
    page.evaluate("() => document.activeElement?.blur()")

    # A resolved thread has no box, so the press falls through to the general box rather
    # than reaching for one that is not there. The panel's own row answers it, saying so in
    # the panel's words; what matters is that the thread is not named, which is the phase
    # above's answer and would be the wrong one here.
    page.locator(".lf-details > summary").click()
    page.locator(f'.lf-details .lf-thread[data-id="{gone}"]').focus()
    expect(line).not_to_contain_text("comment on the thread")
    page.keyboard.press("c")
    expect(page.locator(".lf-general textarea")).to_be_focused()

    assert errors == []
    page.close()


def test_c_in_a_seated_conversation_reaches_the_thread_it_is_in(browser, serve):
    """The page side of the same question. A widget that seats its own conversation
    (`x-conversation`) holds one thread per exchange, each with its own box, and the
    reader can stand in any of them — so "say something about this" means the box of the
    thread they are in, exactly as it does in the panel. One reading answers both, because
    a rule for the panel and a different one for the page is two answers to one question:
    read off the panel's class alone, the page side sent every thread on a seat to the
    oldest one's box.

    Two threads, and the reader in the second: with one there is no wrong answer to give,
    so the pair is what makes the assertion mean anything. The first phase is the control
    — a decision beside the seat, where standing on the widget opens the composer on that
    widget, so a green below is the standing being read and not every press landing in a
    conversation.

    The agent has answered both remarks, so each thread here is a whole exchange. Nothing
    in this test turns on that: the press reads where the reader is standing rather than
    the reader's list, so the seat answers the same way before a reply and after one."""
    url = serve(
        leaf_page(
            "seated",
            """
<h1 id="t">Seated</h1>
<lf-decision id="shape-decision"><h2>Which material?</h2>
<lf-options id="shape" choose>
  <lf-option id="sh-steel"><strong>Steel</strong> Galvanised, drop-in.</lf-option>
  <lf-option id="sh-cedar"><strong>Cedar</strong> Cheap; needs sealing.</lf-option>
</lf-options></lf-decision>
<lf-command id="hub" label="The rail">
  <lf-task id="fitting" status="active" talk><strong>Who fits the rail?</strong>
  Either crew can take it, and neither has said which week.</lf-task>
</lf-command>
""",
        )
    )
    d = serve.page_dir
    said = []
    for text in ("First remark.", "Second remark."):
        events_model.append_event(
            d,
            {
                "kind": "comment",
                "author": "user",
                "revision": 1,
                "text": text,
                "anchor": {"section": "fitting"},
            },
        )
        said.append(events_model.read_events(d)[-1]["id"])
        events_model.append_event(
            d,
            {
                "kind": "reply",
                "author": "claude",
                "revision": 1,
                "parent": said[-1],
                "text": "Noted.",
            },
        )

    page, errors = open_page(browser, url)
    line = page.locator(".lf-keyline")
    threads = page.locator(".lf-conversation-thread")
    expect(threads).to_have_count(2)

    # The control: standing on a widget that seats nothing, so the press has no thread
    # to prefer and opens the composer on the widget itself.
    page.locator("#shape .lf-pick").first.focus()
    expect(line).to_contain_text("comment on the decision")
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    page.keyboard.press("Escape")
    page.evaluate("() => document.activeElement?.blur()")

    # Standing in the second thread, the press means that thread's box.
    second = page.locator(f'.lf-conversation-thread[data-thread="{said[1]}"]')
    second.focus()
    expect(line).to_contain_text("comment on the thread")
    page.keyboard.press("c")
    expect(second.locator("> .lf-say textarea")).to_be_focused()

    # And Esc hands back the press that got them there, which is the keyboard-is-a-stack
    # rule read on the page rather than in the panel. The box asked for `.lf-thread` and
    # the panel alone, so out here the rung fell through to the page's own "let go": one
    # press in from the thread, one press out to body, with the thread they had been
    # standing in two feet away and no key back to it. Both ends read one climb now, so
    # the word going in ("comment on the thread") and the word coming out are about the
    # same element.
    expect(line).to_contain_text("back to thread")
    page.keyboard.press("Escape")
    expect(second).to_be_focused()
    # One rung, not two: the page's own way out is the press after this one.
    expect(line).to_contain_text("let go")
    page.keyboard.press("Escape")
    assert page.evaluate("() => document.activeElement === document.body")

    assert errors == []
    page.close()


def test_c_travels_to_an_item_its_own_scroller_has_taken_away(browser, serve):
    """What the press asks is whether the item is in front of the reader, and only the
    page shows that. An item's own box is the box it would have — unclipped — so a card
    carried out of a board's sideways scroller still reports one inside the window, and a
    gate reading that called it visible and opened the box on something entirely off
    screen. `shownRect` is the reading the ⌥ aim's own paint takes, and this press is its
    keyboard twin: the two decide "in front of the reader" alike or they are not twins.

    The control is the same board with the scroller left alone, where the card is really
    in front of the reader and nothing moves — the pointer's answer on the same card. A
    test with only the scrolled case would pass just as well on a press that always
    travelled, which is the behaviour this replaced."""
    url = serve(
        leaf_page(
            "carried",
            """
<h1 id="t">Carried</h1>
<lf-board id="b">
"""
            + "\n".join(
                f'<lf-column id="col{i}" label="Column {i}">'
                f'<lf-card id="card{i}">Card {i} with a '
                f'<a href="https://example.invalid/{i}">link {i}</a> inside it.</lf-card>'
                "</lf-column>"
                for i in range(8)
            )
            + """
</lf-board>
""",
        )
    )
    seen = """() => {
      const r = document.querySelector('#card0').getBoundingClientRect();
      return {left: Math.round(r.left), onScreen: r.right > 0 && r.left < innerWidth};
    }"""

    # The control: nothing scrolled, so the card is in front of the reader and stays put.
    page, errors = open_page(browser, url)
    page.locator("#card0 a").focus()
    was = page.evaluate(seen)
    assert was["onScreen"], "the control needs the card visible to begin with"
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(seen)["left"] == was["left"], (
        "the page moved under a reader who could already see the card"
    )
    page.close()

    # Carried out of its own scroller after the reader stood on it — focus first, because
    # focusing a card is itself a scroll and would undo the carrying it is meant to survive.
    page, errors = open_page(browser, url)
    page.locator("#card0 a").focus()
    page.evaluate(
        "() => { const b = document.querySelector('#b'); b.scrollLeft = b.scrollWidth; }"
    )
    assert not page.evaluate(seen)["onScreen"], (
        "the board did not carry the card off screen, so this proves nothing"
    )
    page.keyboard.press("c")
    expect(page.locator(".lf-composer")).to_be_visible()
    assert page.evaluate(seen)["onScreen"], (
        "the box opened on a card the board had carried out of sight"
    )
    assert errors == []
    page.close()


def test_c_comments_and_g_t_navigates_to_threads(browser, serve):
    """c is contextual comment; g T is the one route into the Threads list."""
    page, errors = open_page(browser, serve(NOTED_PAGE))
    page.keyboard.press("c")  # page: straight into its comment box
    expect(page.locator(".lf-general textarea")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()

    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("c")  # panel context: the same page comment box
    expect(page.locator(".lf-general textarea")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("c")
    expect(page.locator(".lf-general textarea")).to_be_focused()
    expect(page.locator(".lf-panel")).to_have_class(re.compile("open"))
    page.keyboard.press("Escape")
    expect(page.locator(".lf-threads")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-panel")).to_be_hidden()
    assert page.evaluate("() => document.activeElement === document.body")
    assert errors == []
    page.close()


def test_the_panels_own_c_answers_a_page_whose_log_has_not_arrived(browser, serve):
    """A page whose first poll cannot reach the server is a page the reader still writes
    on: the general box stands, its placeholder names the key that reaches it, and the
    banner says only that a comment will not send yet. What it has not got is a thread
    list, so narrowing by what awaits the reader is dead. Find remains available as the
    panel's empty search, and the scope used to take `c` down with the missing list.

    The page's c enters the box directly. g T independently reaches the empty Threads
    list, where the panel's own search remains available.

    Offline rather than mid-load, because it is the state that stays: a loading page
    answers a moment later, and a page whose server has stopped is where a reader sits."""
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = watched(page)
    page.route("**/api/state*", refuse)
    try:
        page.goto(serve(NOTED_PAGE), wait_until="load")
        page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")
        expect(page.locator(".lf-status-text")).to_have_text(
            "Server offline — reconnecting. Keep this page open so pending changes can send."
        )

        page.keyboard.press("c")
        expect(page.locator(".lf-general textarea")).to_be_focused()
        page.keyboard.press("Escape")
        page.keyboard.press("g")
        page.keyboard.press("Shift+t")
        expect(page.locator(".lf-threads")).to_be_focused()

        # The missing list takes away its waiting filter, but not the panel's own search:
        # a search over nothing still belongs to the scope in front of the page.
        line = page.locator(".lf-keyline")
        expect(line).not_to_contain_text("waiting on you")
        expect(line).to_contain_text("find")

        assert errors == []
    finally:
        page.close()


# Where the reader is standing, in the terms the next Tab is decided by: the document
# position of the focused element, and whether it is the first stop in the document.
STANDING = """() => {
  const at = document.activeElement;
  const first = document.querySelector('.lf-skip');
  return {
    name: at?.className || at?.tagName || 'nothing',
    isFirstStop: at === first,
    top: at ? at.getBoundingClientRect().top : null,
    inChrome: Boolean(at?.closest?.('.lf-chrome')),
  };
}"""


def test_the_reference_hands_the_reader_back_to_the_page_they_were_reading(
    browser, serve
):
    """Closing a mode gives back the press that opened it, and the reader's place with it.

    A reader working from the page stands on `body`: `letGo` puts them there so Space and
    PageDown reach the document's own scroll box. `?` from there recorded `body` as the
    door and closing handed focus back to it — and focusing `body` resets the browser's
    sequential focus navigation starting point, so the next Tab began at the top of the
    document. A reader who opened the reference four screens down to look a key up was
    charged the whole page to get back to where they had been.

    The reading is the next Tab rather than the focused element, because that is the fact
    that was wrong: the restore itself looked fine both before and after, focus being on
    nothing either way. The skip link is the document's first stop, so landing on it is
    exactly the failure written down.
    """
    page, errors = open_page(browser, serve(LONG_PAGE))
    page.evaluate("() => document.getElementById('p40').scrollIntoView()")
    page_at_rest(page)
    reading = page.evaluate(
        "() => document.getElementById('p40').getBoundingClientRect().top"
    )
    # Twice: the first press unfolds the shelf, the second opens the reference.
    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-help")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-help")).to_be_hidden()

    page.keyboard.press("Tab")
    standing = page.evaluate(STANDING)
    assert not standing["isFirstStop"], (
        f"after the reference closed, the reader's next Tab went to the first stop in "
        f"the document ({standing}) rather than on from the words they were reading at "
        f"{reading:.0f}px"
    )
    # And nothing of the borrow is left on the author's paragraph: `tabindex` is not in
    # PAGE_PAINT_ATTRIBUTES, so a stop left standing would be runtime paint the replay
    # signature has no vocabulary for.
    assert (
        page.evaluate("() => document.querySelectorAll('main [tabindex]').length") == 0
    )
    assert errors == []
    page.close()


def test_a_reader_at_the_top_of_the_document_is_one_press_from_the_chrome(
    browser, serve
):
    """The runtime's layer follows `main`, so reaching it by Tab meant reaching it last.

    Document order is right for reading — the page is what the reader came for — and it
    is the whole tab order too, so on a page of any length the banner, the panel and the
    key line stood behind every link, fold and control the author wrote. A keyboard reader
    arriving at the top of the document had no way to the layer that is not the page.

    The press is what is asserted rather than the link's presence: a skip link that is in
    the DOM and does not land anybody is the failure this is about, one step later.

    On the corpus, because a page of plain paragraphs would put the chrome one Tab away
    on its own and this would pass with the link taken out.
    """
    example = next(e for e in EXAMPLES if e.stem == "corpus")
    page, errors = open_page(browser, serve(example))
    page.evaluate("() => document.body.focus()")
    page.keyboard.press("Tab")
    standing = page.evaluate(STANDING)
    assert standing["isFirstStop"], (
        f"the first Tab from the top of the document landed on {standing['name']}, so "
        f"the layer is still behind the whole page"
    )
    assert standing["top"] >= 0, (
        f"the skip link takes focus and is not on screen: {standing}"
    )
    page.keyboard.press("Enter")
    landed = page.evaluate(STANDING)
    assert landed["inChrome"], (
        f"the skip link's press left the reader on {landed['name']}, outside the layer "
        f"it names"
    )
    assert errors == []
    page.close()
