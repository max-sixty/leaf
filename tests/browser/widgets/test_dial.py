"""A detail dial: Skim folds all but the lede, the gists and the headings above them
and keeps the reader's place, ⋯ unfolds one section, Everything opens every
closed detail, and Read takes back exactly what the dial changed."""

import re

import pytest
from playwright.sync_api import expect
from render_harness import (
    PREVIEW,
    clocked,
    dwelt,
    leaf_page,
    open_page,
    preview_parts,
    resized,
)

from leaf.source.render_checks import one_frame
from leaf_dev.example_data import named_source

pytestmark = pytest.mark.shifts_unsurveyed


def section(name, paragraphs):
    body = "".join(
        f'<p id="{name}-{n}">{f"Supporting detail for {name}. " * 30}</p>'
        for n in range(paragraphs)
    )
    return (
        f'<section id="{name}"><h2>{name.title()}</h2>'
        f'<p class="gist" id="{name}-gist">The {name} section concludes this.</p>'
        f'{body}<details id="{name}-more"><summary>Method</summary><p>How.</p></details>'
        "</section>"
    )


# Long enough that the page still scrolls at Skim, so the place can be kept.
SECTIONS = ("impact", "cause", "fix", "timeline", "method", "owners", "followups")
DIAL_PAGE = leaf_page(
    "Dial",
    '<h1>Report</h1><p class="lf-lede">What happened.</p><lf-dial id="dial"></lf-dial>'
    + "".join(section(name, 3) for name in SECTIONS),
)


def depth(page, label):
    """Press a depth with the pointer where it stands, as the reader does."""
    box = page.locator("lf-dial .lf-dial-depth", has_text=label).bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def top(page, selector):
    """Where the node stands once the blocks have finished gliding into place."""
    page.wait_for_function("() => document.getAnimations().length === 0")
    return page.locator(selector).evaluate("node => node.getBoundingClientRect().top")


def test_depths_fold_keep_the_place_and_restore(browser, serve):
    """Skim leaves the headings, lede and gists, and the gist of the paragraph at the
    reading line lands where that paragraph stood; ⋯ shows one section; Everything opens
    the closed details; Read takes every fold, marker and opened detail back."""
    page = open_page(browser, serve(DIAL_PAGE))
    folded = page.locator("[data-lf-dial-folded]")
    markers = page.locator(".lf-dial-more")

    page.locator("#cause-1").evaluate(
        "p => document.scrollingElement.scrollTop += "
        "p.getBoundingClientRect().top - innerHeight * 0.25 + 10"
    )
    reading = top(page, "#cause-1")
    depth(page, "Skim")
    expect(page.locator("lf-dial .lf-dial-depth", has_text="Skim")).to_have_attribute(
        "aria-checked", "true"
    )
    # Each section's three paragraphs and its closed detail.
    expect(folded).to_have_count(4 * len(SECTIONS))
    for name in ("impact", "cause", "fix"):
        expect(page.locator(f"#{name} h2")).to_be_visible()
        expect(page.locator(f"#{name}-gist")).to_be_visible()
        expect(page.locator(f"#{name}-0")).to_be_hidden()
    expect(markers).to_have_count(len(SECTIONS))
    assert abs(top(page, "#cause-gist") - reading) < 2
    # A section's ⋯ is the last box its section holds, so the marks drawn on the
    # section, such as a comment's aim, hold the ⋯ whole.
    assert page.locator("#cause .lf-dial-more").evaluate(
        "m => m.getBoundingClientRect().bottom"
        " <= m.closest('section').getBoundingClientRect().bottom + 0.5"
    )

    skim_face = page.locator("lf-dial .lf-dial-depth", has_text="Skim")
    skim_ink = skim_face.evaluate("r => getComputedStyle(r).borderColor")
    page.locator("#cause .lf-dial-more button").click()
    expect(page.locator("#cause-0")).to_be_visible()
    expect(page.locator("#impact-0")).to_be_hidden()
    expect(page.locator("#cause-0")).to_be_focused()
    # The page now shows more than Skim, so Skim's selection steps back, and pressing
    # it folds the page to Skim again.
    assert skim_face.evaluate("r => getComputedStyle(r).borderColor") != skim_ink
    depth(page, "Skim")
    expect(page.locator("#cause-0")).to_be_hidden()
    expect(folded).to_have_count(4 * len(SECTIONS))
    expect(skim_face).to_have_css("border-color", skim_ink)

    depth(page, "Everything")
    expect(folded).to_have_count(0)
    expect(page.locator("details[open]")).to_have_count(len(SECTIONS))

    depth(page, "Read")
    expect(folded).to_have_count(0)
    expect(markers).to_have_count(0)
    expect(page.locator("details[open]")).to_have_count(0)
    expect(page.locator("main [hidden]")).to_have_count(0)

    # The depths are one radio group: an arrow from Read chooses the depth beside it.
    read = page.get_by_role("radio", name=re.compile(r"^Read \d+ min$"))
    skim = page.get_by_role("radio", name=re.compile(r"^Skim \d+ min$"))
    read.focus()
    page.keyboard.press("ArrowLeft")
    expect(skim).to_be_focused()
    expect(skim).to_have_attribute("aria-checked", "true")
    expect(folded).to_have_count(4 * len(SECTIONS))
    page.keyboard.press("ArrowRight")
    expect(read).to_have_attribute("aria-checked", "true")
    expect(folded).to_have_count(0)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_turn_that_glides_keeps_the_place_in_every_engine(request, serve, engine):
    """With motion on, Skim then Read on the detail example left the gist standing for
    the paragraph being read 360.7px below the reading line in Firefox, and Read moved it
    another 347.9px, while Chromium held it: Firefox's scroll anchoring follows a block
    to where its glide draws it, and scrolled the page by the glide. The gliding blocks
    are no anchors while they glide."""
    page = open_page(
        request.getfixturevalue(engine), serve(named_source("incident-report"))
    )
    page.emulate_media(reduced_motion="no-preference")
    resized(page, 1440, 900)
    page.locator("#incident-cause-1").evaluate(
        "p => document.scrollingElement.scrollTop += "
        "p.getBoundingClientRect().top - innerHeight * 0.25 + 10"
    )
    reading = top(page, "#incident-cause-1")
    depth(page, "Skim")
    expect(page.locator("#incident-cause-1")).to_be_hidden()
    gist = top(page, "#incident-cause-gist")
    assert gist == pytest.approx(reading, abs=1)
    depth(page, "Read")
    expect(page.locator("#incident-cause-1")).to_be_visible()
    assert top(page, "#incident-cause-gist") == pytest.approx(gist, abs=1)


def centre_x(locator):
    box = locator.bounding_box()
    return box["x"] + box["width"] / 2


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_pointing_at_a_depth_hangs_each_depth_s_page_under_its_button(
    request, serve, engine
):
    """Each depth says under its word how long it takes to read. Pointing at one hangs
    each depth's page under its own button, Skim's shortest and Everything's longest,
    with Leaf's own preview face unseen, and fades on the page what Skim would fold. A
    press on another depth keeps them up the whole time it is held and as it is let go,
    however long it was held, and moves the frame to it; Escape puts them away and
    leaves focus on the depth."""
    page = open_page(clocked(request.getfixturevalue(engine)), serve(DIAL_PAGE))
    buttons = page.locator("lf-dial .lf-dial-depth")
    expect(buttons.locator(".lf-dial-time")).to_have_text([re.compile(r"\d+ min")] * 3)
    panel = page.locator(".lf-dial-hang-panel")
    sheets = panel.locator(".lf-dial-hang-page")
    frame = panel.locator(".lf-dial-hang-frame")
    read = buttons.filter(has_text="Read")
    read.hover()
    expect(panel).to_have_attribute("data-lf-open", "")
    expect(page.locator(PREVIEW)).to_have_attribute("data-lf-face", "unseen")
    expect(page.locator(PREVIEW)).to_be_hidden()
    page.wait_for_function("() => document.getAnimations().length === 0")
    for i in range(3):
        assert centre_x(sheets.nth(i)) == pytest.approx(centre_x(buttons.nth(i)), abs=1)
    heights = [sheets.nth(i).bounding_box()["height"] for i in range(3)]
    assert heights[0] < heights[1] <= heights[2]
    assert centre_x(frame) == pytest.approx(centre_x(read), abs=1)
    buttons.filter(has_text="Skim").hover()
    expect(page.locator('[data-lf-dial-ghost="goes"]').first).to_be_attached()

    everything = buttons.filter(has_text="Everything")
    everything.hover()
    page.mouse.down()
    # The sheets would go a frame after the press puts Leaf's preview away.
    one_frame(page)
    one_frame(page)
    expect(panel).to_have_attribute("data-lf-open", "")
    # Held past the warmth the put-away preview leaves, after which the pointer's next
    # preview there would wait for its dwell.
    dwelt(page, "WARM")
    panel.evaluate(
        """panel => new MutationObserver(() => {
          if (!panel.hasAttribute("data-lf-open")) panel.dataset.closed = "";
        }).observe(panel, {attributes: true, attributeFilter: ["data-lf-open"]})"""
    )
    page.mouse.up()
    expect(page.locator("details[open]")).to_have_count(len(SECTIONS))
    # Past the dwell that would bring back sheets the release had put away.
    dwelt(page)
    expect(panel).to_have_attribute("data-lf-open", "")
    assert panel.get_attribute("data-closed") is None
    page.wait_for_function("() => document.getAnimations().length === 0")
    assert centre_x(frame) == pytest.approx(centre_x(everything), abs=1)

    page.keyboard.press("Escape")
    expect(panel).not_to_have_attribute("data-lf-open", "")
    expect(page.get_by_role("radio", name=re.compile("^Everything"))).to_be_focused()


def test_a_folded_block_that_sets_its_own_height_takes_no_room(browser, serve):
    """A folded `lf-diagram` kept the 170px its package's `min-block-size` reserved, so
    Skim left a blank gap where the drawing was. A block Skim folds takes no room
    whatever height the page or its package gave it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Dial",
                '<h1>Report</h1><lf-dial id="dial"></lf-dial>'
                '<section id="flow"><h2>Flow</h2>'
                '<p class="gist" id="flow-gist">Every order ends in one queue.</p>'
                '<div id="drawn">A sized block.</div></section>'
                '<section id="next"><h2 id="next-heading">Next</h2>'
                '<p class="gist">The warehouse picks in order.</p></section>',
                head="<style>#drawn { block-size: 240px; min-block-size: 170px; }</style>",
            )
        ),
    )
    depth(page, "Skim")
    expect(page.locator("#drawn")).to_have_attribute("data-lf-dial-folded", "")
    expect(page.locator("#drawn")).to_be_hidden()


SQUARE = '<svg viewBox="0 0 10 10" width="40" height="40"><rect width="10" height="10"/></svg>'


def test_skim_keeps_what_the_author_marks_whatever_it_is(browser, serve):
    """Skim kept every picture by a list of tags, so it folded a video or a canvas a
    skimmer needed and kept pictures one didn't. Skim keeps whatever the author marks
    `.gist`, of any kind, and the heading above it: a figure with its caption, a chart, a
    video, a canvas, a picture in a tab, a picture marked inside a figure, with the
    figure's caption, and a paragraph or list item holding a gist, whole, words and
    links beside it included. A picture the author didn't mark folds with the words
    around it, headings inside it included, and so does an `aside`. A section, list
    item or aside of blocks is laid out in place, a button among its blocks included,
    so a gist in one keeps its support folded. A gist or heading inside a closed
    disclosure stays closed, since Skim shows nothing Read doesn't, so a section
    holding only those folds whole."""
    chart = (
        '<lf-chart class="gist" id="latency-chart"><pre>{ ariaLabel: "p99 by hour", '
        "marks: [Plot.lineY([1, 3, 2])] }"
        "</pre></lf-chart>"
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Dial",
                '<h1>Report</h1><p class="lf-lede">What happened.</p>'
                '<lf-dial id="dial"></lf-dial>'
                '<section id="cause"><h2 id="cause-heading">Cause</h2>'
                '<p class="gist" id="cause-gist">The key changed.</p>'
                '<p id="cause-0">How the key changed.</p>'
                f'<figure class="gist" id="key-figure">{SQUARE}'
                '<figcaption id="key-caption">The key, before and after.</figcaption>'
                "</figure>"
                f'<figure id="cause-aside">{SQUARE}</figure>'
                '<p id="cause-1">More detail.</p>'
                '<button id="cause-copy" type="button">Copy the key</button>'
                '<p id="shot-line">The dashboard then: <img class="gist" id="shot" '
                'alt="The dashboard" width="40" height="30"> at 3%.</p>'
                '<p id="unmarked-line"><img alt="The cache" width="40" height="30">'
                " The cache at 16:30.</p>"
                '<ul><li><p class="gist" id="finding-gist">4.2 changed the key.</p>'
                '<p id="finding-support">Found by diffing the releases.</p></li>'
                '<li><img class="gist" alt="Run 3" width="40" height="30"> '
                '<a id="run-link" href="#key-figure">Run 3</a> '
                '<em id="run-rate">hit rate 3%</em></li></ul>'
                '<aside id="cause-note"><p>The canary missed it.</p></aside>'
                '<aside><p class="gist" id="aside-gist">No flag guarded the key.</p>'
                '<p id="aside-support">Cache keys ship unflagged.</p></aside>'
                '<details id="cause-raw" open><summary id="cause-raw-summary">Raw'
                f'</summary><figure class="gist" id="cause-raw-figure">{SQUARE}'
                "</figure></details></section>"
                '<section id="latency"><h2 id="latency-heading">Latency</h2>'
                f'<figure id="latency-figure"><h4>Before</h4>{SQUARE}<h4>After</h4>'
                f"{SQUARE}<figcaption>p99 before and after.</figcaption></figure>"
                f'{chart}<p id="latency-0">p99 doubled.</p></section>'
                '<section id="demo"><h2 id="demo-heading">Demo</h2>'
                '<video class="gist" id="demo-video" width="40" height="30"></video>'
                '<canvas class="gist" id="demo-canvas" width="40" height="30"></canvas>'
                '<figure><img class="gist" id="demo-shot" alt="The checkout" '
                'width="40" height="30"><figcaption id="demo-caption">The checkout '
                "after the fix.</figcaption></figure>"
                '<p id="demo-0">Recorded on staging.</p></section>'
                '<section id="views"><h2 id="views-heading">Views</h2>'
                '<lf-tabs id="views-tabs"><lf-tab id="views-a" label="Before">'
                f'<figure class="gist" id="views-figure">{SQUARE}</figure></lf-tab>'
                '</lf-tabs><p id="views-0">Both views.</p></section>'
                '<section id="method" style="border: 1px solid">'
                '<h2 id="method-heading">Method</h2>'
                f'<figure id="method-figure">{SQUARE}</figure>'
                '<details id="method-raw"><summary>Raw</summary><h3>Runs</h3>'
                f'<figure class="gist" id="raw-figure">{SQUARE}</figure></details>'
                "</section>",
            )
        ),
    )
    depth(page, "Skim")
    for kept in (
        "#cause-heading",
        "#cause-gist",
        "#key-figure",
        "#key-caption",
        "#shot-line",
        "#finding-gist",
        "#aside-gist",
        "#run-link",
        "#run-rate",
        "#cause-raw-summary",
        "#cause-raw-figure",
        "#latency-heading",
        "#latency-chart",
        "#demo-heading",
        "#demo-video",
        "#demo-canvas",
        "#demo-shot",
        "#demo-caption",
        "#views-heading",
        "#views-figure",
    ):
        expect(page.locator(kept)).to_be_visible()
    for folded in (
        "#cause-0",
        "#cause-aside",
        "#cause-1",
        "#cause-copy",
        "#unmarked-line",
        "#finding-support",
        "#cause-note",
        "#aside-support",
        "#latency-figure",
        "#latency-0",
        "#demo-0",
        "#views-0",
        "#method",
        "#method-heading",
        "#method-figure",
        "#method-raw",
    ):
        expect(page.locator(folded)).to_be_hidden()
    depth(page, "Everything")
    expect(page.locator("#raw-figure")).to_be_visible()
    depth(page, "Read")
    expect(page.locator("main [hidden]")).to_have_count(0)


def test_a_dial_in_a_sidebar_page_s_body_governs_the_body_alone(browser, serve):
    """A dial in a sidebar page's body governs the body: Skim folds the body's blocks,
    leaves the sidebar's contents shown, sets no ⋯ among the Layout's regions, and
    leaves the sidebar and the body where they stood."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Dial",
                '<aside id="route"><div class="layout-track">'
                '<lf-toc id="contents"></lf-toc></div></aside>'
                '<div class="layout-column" id="body"><h1>Report</h1>'
                '<p class="lf-lede">What happened.</p><lf-dial id="dial"></lf-dial>'
                + "".join(section(name, 3) for name in SECTIONS)
                + "</div>",
                layout="sidebar",
            )
        ),
    )
    resized(page, 1400, 900)
    regions = page.locator("main > *")
    across = "nodes => nodes.map(n => [n.getBoundingClientRect().x, n.offsetWidth])"
    before = regions.evaluate_all(across)
    depth(page, "Skim")
    expect(page.locator("#impact-0")).to_be_hidden()
    expect(page.locator("#contents")).to_be_visible()
    expect(page.locator("#route [data-lf-dial-folded]")).to_have_count(0)
    expect(regions).to_have_count(2)
    assert regions.evaluate_all(across) == before


def test_a_section_without_a_gist_folds_whole(browser, serve):
    """Skim kept every heading, so a section the author gave no gist still showed its
    heading over nothing. A heading stands only for a lede or gist it heads, in a
    `section`, in flat markup or inside a `header`, so such a section folds whole. It
    joins the gap before it, under one ⋯ whose preview names the sections it holds:
    a gist-less section after a nested one drew a second ⋯ under the first."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Dial",
                '<hgroup id="title"><h1>Report</h1></hgroup>'
                '<p class="lf-lede">What happened.</p><lf-dial id="dial"></lf-dial>'
                '<section id="cause"><h2>Cause</h2>'
                '<p class="gist" id="cause-gist">The key changed.</p>'
                '<section id="detail"><h3 id="detail-heading">Detail</h3>'
                '<p id="detail-0">How the key changed.</p></section></section>'
                '<section id="method"><h2 id="method-heading">Method</h2>'
                '<p id="method-0">How we measured.</p></section>'
                '<section id="impact"><header><h2 id="impact-heading">Impact</h2>'
                '<p id="impact-byline">By the on-call team.</p></header>'
                '<p class="gist">Checkout slowed.</p></section>'
                '<h2 id="fix-heading">Fix</h2><p class="gist">Roll back.</p>'
                '<h3 id="steps-heading">Steps</h3><p id="steps-0">First this.</p>'
                '<h2 id="appendix-heading">Appendix</h2><p id="appendix-0">Raw.</p>',
            )
        ),
    )
    depth(page, "Skim")
    for kept in (
        "#title h1",
        "#cause h2",
        "#cause-gist",
        "#impact-heading",
        "#fix-heading",
    ):
        expect(page.locator(kept)).to_be_visible()
    for folded in (
        "#detail-heading",
        "#method-heading",
        "#method-0",
        "#impact-byline",
        "#steps-heading",
        "#appendix-heading",
        "#appendix-0",
    ):
        expect(page.locator(folded)).to_be_hidden()
    # One ⋯ for each gap: Cause's rest with Method, the byline, and Fix's rest.
    expect(page.locator("main .lf-dial-more")).to_have_count(3)
    gap = page.locator("#cause .lf-dial-more button")
    assert preview_parts(gap) == ["Show the rest", "Detail", "Method"]
    assert preview_parts(page.locator("#impact .lf-dial-more button")) == [
        "Show the rest"
    ]
    gap.click()
    expect(page.locator("#detail-heading")).to_be_visible()
    expect(page.locator("#method-heading")).to_be_visible()
    expect(page.locator("#appendix-heading")).to_be_hidden()
    depth(page, "Read")
    expect(page.locator("main [hidden]")).to_have_count(0)
