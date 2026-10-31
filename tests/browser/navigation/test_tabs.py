"""Tab sets and tabbed sections."""

import re

import pytest
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    FEATURE_GALLERY,
    leaf_page,
    open_page,
    resized,
    stamp_page,
    wait_for_revision,
)

from leaf.render_checks import rendered


# A live revision that puts a tab set above this one moves it 430px down the window
# (issue #4036, "Keep what a live revision adds above the reader from moving it").
@pytest.mark.shifts_unsurveyed
@pytest.mark.parametrize(
    "placement",
    # Directly in main beside other blocks, and inside one; alone in main is the
    # first case without its neighbours.
    ["among-blocks", "nested"],
)
def test_the_gallery_tab_set_uses_the_boundary_of_its_composition(
    browser, serve, placement
):
    """Authored flow chooses the face independently of primary view history.

    The first set directly in main owns URL/history; another arriving before it
    changes that owner without framing a set the page still declares as flow.
    """
    sample = re.search(
        r'<lf-tabs id="bg-tabs">.*?</lf-tabs>', FEATURE_GALLERY.read_text(), re.DOTALL
    )
    assert sample is not None
    sample = sample[0]
    if placement != "nested":
        sample = sample.replace("<lf-tabs ", '<lf-tabs class="layout-flow" ', 1)
        sample = sample.replace("<lf-tab ", '<lf-tab class="layout-flow" ')
    heading = "<header><h1>Project views</h1></header>"
    body = {
        "alone": heading + sample,
        "among-blocks": heading
        + "<aside><p>Contents</p></aside>"
        + sample
        + "<p>This conclusion follows the tab set.</p>",
        "nested": heading + "<section>" + sample + "</section>",
    }[placement]
    embedded = placement == "nested"
    page = open_page(
        browser,
        live_url(serve(leaf_page("Root tab gallery", body))),
    )
    tabs = page.locator("#bg-tabs")
    expect(tabs).to_have_css("border-left-width", "1px" if embedded else "0px")
    choices = tabs.get_by_role("tab")
    expect(choices).to_have_count(2)
    choices.nth(1).click()
    expect(choices.nth(1)).to_have_attribute("aria-selected", "true")
    if not embedded:
        page.wait_for_url(re.compile(r"#bg-tab-context$"))
        page.go_back()
        expect(choices.first).to_have_attribute("aria-selected", "true")
        page.go_forward()
        expect(choices.nth(1)).to_have_attribute("aria-selected", "true")
    page.reload()
    expect(tabs.get_by_role("tab").nth(1)).to_have_attribute("aria-selected", "true")
    if not embedded:
        page.evaluate("window.__retainedTabs = document.querySelector('#bg-tabs')")
        source = serve.page_dir / "index.html"
        original = source.read_text()
        # An earlier set takes over primary navigation; this one's authored flow
        # and retained panel stay as they were.
        stamp_page(
            serve.page_dir,
            original.replace(
                '<lf-tabs class="layout-flow" id="bg-tabs">',
                '<lf-tabs id="earlier-tabs"><lf-tab id="earlier-tab" label="Earlier">'
                "<p>Earlier views.</p></lf-tab></lf-tabs>"
                '<lf-tabs class="layout-flow" id="bg-tabs">',
            ),
            "Add an earlier tab set",
        )
        wait_for_revision(page, 2)
        expect(tabs).to_have_css("border-left-width", "0px")
        expect(tabs).to_have_css("--lf-views-flow", "page")
        assert page.evaluate(
            "window.__retainedTabs === document.querySelector('#bg-tabs')"
        )
        stamp_page(serve.page_dir, original, "Restore page tabs")
        wait_for_revision(page, 3)
        expect(tabs).to_have_css("border-left-width", "0px")
        expect(tabs.get_by_role("tab").nth(1)).to_have_attribute(
            "aria-selected", "true"
        )


def test_overflowing_section_tabs_reveal_and_open_their_sections(browser, serve):
    """A tabbed section whose names overflow its column at desktop width offers
    working pointer and key routes."""
    sample = re.search(
        r'<lf-tabs id="bg-rollout-tabs">.*?</lf-tabs>',
        FEATURE_GALLERY.read_text(),
        re.DOTALL,
    )
    assert sample is not None
    body = (
        "<header><h1>Search rollout</h1></header>"
        '<section id="bg-tab-set"><h2>A rollout review in a narrow column</h2>'
        + sample[0]
        + "</section>"
    )
    # The gallery's own rule narrows the column, so six names overflow at desktop.
    narrow = "<style>#bg-rollout-tabs { max-inline-size: 26rem; }</style>"
    page = open_page(
        browser,
        live_url(serve(leaf_page("Rollout review", body, head=narrow))) + "#bg-tab-set",
    )
    resized(page, 1200, 900)
    tabs = page.locator("#bg-rollout-tabs")
    strip = tabs.locator(":scope > .lf-tabstrip")
    tabs.scroll_into_view_if_needed()
    choices = tabs.get_by_role("tab")
    expect(choices).to_have_count(6)
    expect(choices.first).to_have_attribute("aria-selected", "true")
    assert strip.evaluate("el => el.scrollWidth > el.clientWidth")

    strip.locator('.lf-tabstrip-scroll[data-to="end"] > span').click()
    page.wait_for_function(
        "document.querySelector('#bg-rollout-tabs > .lf-tabstrip').scrollLeft > 0"
    )
    expect(choices.first).to_have_attribute("aria-selected", "true")
    # The keyboard reaches a tab from the pointer control without requiring that
    # control to take a separate stop; End then brings the last section into view.
    choices.first.click()
    page.keyboard.press("End")
    expect(choices.last).to_be_focused()
    expect(choices.last).to_have_attribute("aria-selected", "true")
    expect(page.locator("#bg-rollout-handoff-text")).to_be_visible()
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    expect(choices.nth(1)).to_be_focused()
    expect(choices.nth(1)).to_have_attribute("aria-selected", "true")
    expect(page.locator("#bg-rollout-scope-text")).to_be_visible()


def test_an_inline_tab_keeps_its_panel_inside_one_visible_boundary(browser, serve):
    """The strip reads as an index inside the one frame that bounds its views.

    The strip stands on the frame's own ground, and the selected name takes the page
    tabs' rule under it rather than a face of its own, so the tab around it grows no
    second frame inside the shared surface. The strip's closing rule keeps the index
    distinct from the panel, whose enclosing frame still answers how far that
    selected view runs.
    """
    page = open_page(
        browser,
        serve(
            leaf_page(
                "bounded tabs",
                """
<h1 id="heading">Parallel work</h1>
<p id="shared">This context belongs to every view.</p>
<section id="views-section">
<lf-tabs id="views">
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
</section>
<section id="next-section"><h2 id="next-heading">Whole-page conclusion</h2></section>
""",
            )
        ),
    )
    boundary = page.evaluate(
        """() => {
          const tabs = document.querySelector('#views');
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
            const underline = tab.closest('.lf-tabstrip').querySelector('.lf-tab-selection');
            const underlineStyle = style(underline);
            const line = box(underline), name = box(label);
            return {
              ground: tabStyle.backgroundColor,
              border: ['Top', 'Right', 'Bottom', 'Left'].map(
                edge => parseFloat(tabStyle[`border${edge}Width`])),
              shadow: tabStyle.boxShadow,
              tabDecoration: tabStyle.textDecorationLine,
              labelGround: labelStyle.backgroundColor,
              labelShadow: labelStyle.boxShadow,
              labelRule: {
                width: parseFloat(labelStyle.borderBottomWidth),
                color: labelStyle.borderBottomColor,
              },
              underline: {
                height: parseFloat(underlineStyle.blockSize),
                color: underlineStyle.backgroundColor,
                visible: line.left < name.right && name.left < line.right ? 'visible' : 'hidden',
              },
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
              ground: style(strip).backgroundColor,
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
    assert boundary["divider"]["ground"] == boundary["frame"]["ground"], boundary
    assert boundary["selected"]["labelGround"] == "rgba(0, 0, 0, 0)", boundary
    assert boundary["inactive"]["labelGround"] == "rgba(0, 0, 0, 0)", boundary
    assert boundary["selected"]["labelShadow"] == "none", boundary
    assert boundary["selected"]["labelRule"]["color"] == "rgba(0, 0, 0, 0)", boundary
    assert boundary["inactive"]["labelRule"]["color"] == "rgba(0, 0, 0, 0)", boundary
    assert boundary["selected"]["underline"] == {
        "height": 2,
        "color": boundary["selected"]["labelInk"],
        "visible": "visible",
    }, boundary
    assert boundary["inactive"]["underline"]["visible"] == "hidden", boundary
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

    selected = page.locator('#views [aria-selected="true"]')
    selected.focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    expect(selected).to_be_focused()
    focus = selected.locator(".lf-tab-name").evaluate(
        """element => {
          const style = getComputedStyle(element);
          return {width: parseFloat(style.outlineWidth), style: style.outlineStyle};
        }"""
    )
    assert focus["width"] > 0 and focus["style"] != "none", focus


def test_a_pressed_tab_stops_naming_the_key_that_opens_it(browser, serve):
    """The strip names Enter and Space while focus stands on a closed tab. A press
    focuses the tab before it opens it, and a person's press spans frames, so the strip
    reads the focused closed tab first and must drop those keys once the tab opens."""
    body = (
        "<header><h1>Two views</h1></header><section><h2>Views</h2>"
        '<lf-tabs id="views"><lf-tab id="views-one" label="One"><p>First view.</p>'
        '</lf-tab><lf-tab id="views-two" label="Two"><p>Second view.</p></lf-tab>'
        "</lf-tabs></section>"
    )
    page = open_page(browser, live_url(serve(leaf_page("Two views", body))))
    strip = page.locator("#views > .lf-tabstrip")
    tab = page.locator("#views").get_by_role("tab", name="Two")
    box = tab.bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    rendered(page)
    expect(strip).to_have_attribute("aria-keyshortcuts", re.compile(r"\bEnter\b"))
    page.mouse.up()
    expect(tab).to_have_attribute("aria-selected", "true")
    rendered(page)
    assert "Enter" not in strip.get_attribute("aria-keyshortcuts")
