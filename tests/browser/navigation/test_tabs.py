"""Tab sets and tabbed sections, and the feature gallery's journeys through them."""

import json
import re

import pytest
from leaf import data as data_model
from leaf import event_log as events_model
from leaf.render_checks import rendered
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    FEATURE_GALLERY,
    PANEL,
    RELEASE_FOCUS,
    consume_browser_errors,
    http_error_console,
    leaf_page,
    open_page,
    panel_control,
    panel_settled,
    resized,
    sending,
    stamp_page,
    wait_for_revision,
    write,
)

from browser.threads import open_panel_thread

pytestmark = pytest.mark.shifts_unsurveyed


# The gallery sections a preview may name, and the page tab each opens.
GALLERY_DESTINATIONS = {
    "bg-core-surfaces": "Decisions",
    "bg-thread-states": "Threads",
    "bg-panel-views": "Threads",
    "bg-quoted-and-visual": "Page & layout",
    "bg-external-data": "Data & work",
    "bg-interactions": "Interactions",
}


def test_the_feature_gallery_exercises_its_core_journeys(browser, serve, live_leaf):
    """The gallery is a journey through the core, not merely its samples beside it.

    A preview can name a gallery section directly: arriving at a fragment held in a
    closed tab is one runtime path whichever section it names, so one arrival proves
    it, and the same page answers which tab holds every other destination. Each core
    surface then opens and shows the gallery's own content: its obligation in On me, its
    open, resolved, and media threads in Threads, its earlier version, the other open
    page, and at phone width its Page Map. Live external data, the Threads tab's
    presets operating a sample's panel, sign-off gating, design comments and transport
    refusal are real journeys on it too.

    One page carries all of them because opening the gallery is most of their cost;
    how each surface behaves belongs to that surface's own tests."""
    live_leaf("second", "A second Leaf page")
    destination = "#bg-external-data"
    root = live_url(serve(FEATURE_GALLERY))
    page = open_page(browser, root + destination)
    gallery_tab = page.locator("#bg-gallery-tabs").get_by_role
    expect(gallery_tab("tab", name="Data & work")).to_have_attribute(
        "aria-selected", "true"
    )
    # The handover key is exchanged for a cookie before the address is shown.
    expect(page).to_have_url(root.split("?", 1)[0] + destination)
    expect(page.locator(":target")).to_have_attribute("id", destination[1:])
    expect(page.locator(destination)).to_be_in_viewport()

    holders = page.evaluate(
        """ids => Object.fromEntries(ids.map(id => {
          const target = document.getElementById(id);
          const panel = target?.closest('#bg-gallery-tabs > lf-tab');
          const tab = panel && document.querySelector(
            `#bg-gallery-tabs [role="tab"][aria-controls="${panel.id}"]`);
          return [id, {tag: target?.localName || null,
                       tab: tab?.textContent.trim() || null}];
        }))""",
        list(GALLERY_DESTINATIONS),
    )
    assert holders == {
        id: {"tag": "section", "tab": view} for id, view in GALLERY_DESTINATIONS.items()
    }

    links = page.get_by_role("navigation", name="On this page").get_by_role(
        "link", include_hidden=True
    )
    targets = links.evaluate_all(
        """links => links.map(link => {
          const href = link.getAttribute('href');
          const target = document.getElementById(decodeURIComponent(href.slice(1)));
          return {href, tag: target?.localName || null,
                  generated: target?.dataset.lfGen === '1'};
        })"""
    )
    assert targets[0] == {"href": "#bg-title", "tag": "hgroup", "generated": False}
    assert all(
        target["tag"] == "section" and not target["generated"] for target in targets[1:]
    ), targets
    assert len({target["href"] for target in targets}) == len(targets), targets

    # One captured source supplies a following view under its authored label.
    live = page.locator("#bg-source-live")
    original = (
        '[route]\nname = "covered terrace"\ndistance_km = 1.8\nstatus = "sample"\n'
    )
    expect(live.locator("code")).to_have_text(original)
    expect(live.locator("figcaption")).to_have_text(
        "feature-gallery-source.toml · lines 1–4"
    )
    changed = '[route]\nname = "river path"\ndistance_km = 2.1\nstatus = "updated"\n'
    data_model.cmd_data_set(serve.page_dir, "gallery-source", changed)
    expect(live.locator("code")).to_have_text(changed)
    expect(page.locator("#bg-measurement-guide")).to_contain_text(
        "measurement is behind its source"
    )

    # The core chrome, each surface showing the gallery's own content.
    resized(page, 1600, 900)
    expect(page.locator(".lf-fp-leaf")).to_have_attribute(
        "aria-label", re.compile(r"^Page menu · \S")
    )
    panel_control(page, "queue").click()
    map_obligation = page.locator(".lf-fp-on-item").filter(
        has_text="Which map should the sample team carry?"
    )
    expect(map_obligation).to_have_count(1)
    expect(map_obligation).to_have_attribute(
        "data-key", '["widget","widget:bg-choice"]'
    )
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    gallery_tab("tab", name="Decisions").click()
    page.locator("#bg-question-api > summary").click()
    page.get_by_role("button", name="Read current obligation", exact=True).click()
    reading = json.loads(page.locator("#bg-question-reading").inner_text())
    assert reading["id"] == "widget:bg-choice"
    assert reading["source"]["id"] == "bg-choice"
    assert reading["prompt"]["target"] == "bg-choice-ask"
    assert reading["status"] == "open"

    gallery_tab("tab", name="Threads").click()
    panel_control(page, "threads").click()
    panel_settled(page, view="threads")
    rows = page.locator(".lf-fp-thread")
    filters = page.locator(".lf-fp-filters button")
    filters.filter(has_text="Resolved").click()
    expect(rows).not_to_have_count(0)
    filters.filter(has_text="Open").click()
    media_thread = open_panel_thread(page, "2be2443f0bb6cc49fc86b52f340e6073")
    media_thread.locator(".lf-message-media").click()
    viewer = page.get_by_role("dialog", name="Image preview")
    expect(viewer.locator("img")).to_have_attribute(
        "src", "/media/051bee487bfb5d13.png"
    )
    page.keyboard.press("Escape")
    expect(viewer).to_be_hidden()
    page.keyboard.press("Escape")
    panel_settled(page, open=False)

    # The Threads tab's presets each open a thread in a sample's panel, and the one
    # chosen survives its Reset.
    frame = page.frame_locator("#bg-panel-sample iframe")
    shown = frame.locator('.lf-fp-view[data-view="thread"]:not([data-leaving])')
    expect(shown).to_have_count(0)
    page.locator('#bg-panel-presets [data-view="overview"]').click()
    expect(shown).to_have_attribute("data-thread", "72e031c5bf0d485ba9054628e09869d4")

    page.keyboard.press("Tab")
    you_button = page.locator('#bg-panel-presets [data-view="you"]')
    expect(you_button).to_be_focused()
    assert you_button.evaluate("element => element.matches(':focus-visible')")
    page.keyboard.press("Space")
    expect(shown).to_have_attribute("data-thread", "2be2443f0bb6cc49fc86b52f340e6073")
    expect(you_button).to_be_focused()

    for view, thread, title in (
        ("you", "2be2443f0bb6cc49fc86b52f340e6073", "Workshop room photo"),
        ("resolved", "bab3cdfcfb8c02aacbb27da731de947a", "Projector map"),
        ("summary", "9ee465bb3f9c1fa309ea9cb1767fa365", "Afternoon workshop"),
        ("progress", "bg-progress-question", "Schedule checks"),
        (
            "overview",
            "72e031c5bf0d485ba9054628e09869d4",
            "Is lunch provided, or should attendees make their own plans?",
        ),
    ):
        page.locator(f'#bg-panel-presets [data-view="{view}"]').click()
        expect(shown).to_have_attribute("data-thread", thread)
        expect(frame.locator(".lf-fp-title")).to_have_text(title)

    page.locator('#bg-panel-presets [data-view="resolved"]').click()
    expect(shown).to_have_attribute("data-thread", "bab3cdfcfb8c02aacbb27da731de947a")
    page.locator("#bg-panel-sample").get_by_role(
        "button", name="Reset", exact=True
    ).click()
    page.locator("#bg-panel-sample").evaluate("async sample => { await sample.ready; }")
    expect(shown).to_have_attribute("data-thread", "bab3cdfcfb8c02aacbb27da731de947a")
    # Latest commands and Reset cancel pending presentation across the port.
    result = page.locator("#bg-panel-sample").evaluate(
        """sample => Promise.all([
          sample.showThread('2be2443f0bb6cc49fc86b52f340e6073',
            {surface: 'panel', waiting: 'user'}),
          sample.showThread('bab3cdfcfb8c02aacbb27da731de947a',
            {surface: 'panel', status: 'resolved'})
        ])"""
    )
    assert result == [False, True]
    expect(frame.locator(".lf-fp-title")).to_have_text("Projector map")
    result = page.locator("#bg-panel-sample").evaluate(
        """async sample => {
          const old = sample.showThread('2be2443f0bb6cc49fc86b52f340e6073',
            {surface: 'panel', waiting: 'user'});
          await sample.reset();
          return old;
        }"""
    )
    assert result is False
    expect(frame.locator(".lf-fp-title")).to_have_text("Projector map")

    panel_control(page, "versions").click()
    expect(page.locator(".lf-fp-version").filter(has_text="v1")).to_be_visible()
    page.locator(".lf-fp-leaf").click()

    panel_control(page, "leaves", at="navigate").click()
    expect(page.locator("a.lf-fp-page")).to_contain_text("A second Leaf page")
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)

    resized(page, 390, 900)
    page.evaluate("scrollTo(0, 0)")
    expect(page.locator("#bg-sidebar")).to_be_hidden()
    # A phone drops the contents spine out of the flow rather than stacking it above
    # the reading, so the page's first section still opens within the first screen;
    # left in the flow it lands a screen below the fold. Which section that is belongs
    # to the gallery's authored order: naming one heading here made a section added
    # above it read as a layout failure.
    expect(page.locator("#bg-view-threads > section").first).to_be_in_viewport()
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    page_map = page.get_by_role("dialog", name="Page Map", exact=True)
    expect(page_map).to_be_visible()
    page.keyboard.press("Escape")
    expect(page_map).to_be_hidden()

    # Sign-off gating, a design comment, and a transport refusal.
    resized(page, 1280, 900)
    gallery_tab("tab", name="Decisions").click()
    approve = panel_control(page, "approval")
    expect(approve).to_contain_text("Approve version")
    expect(approve).to_be_disabled()
    expect(page.locator(".lf-fp-approval")).to_have_attribute(
        "title", "Answer every open widget before approving this work"
    )
    page.locator(".lf-fp-leaf").click()

    option = page.locator("#bg-choice-street")
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("l")
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    option.scroll_into_view_if_needed()
    option_box = option.bounding_box()
    assert option_box is not None
    page.mouse.click(
        option_box["x"] + option_box["width"] / 2,
        option_box["y"] + option_box["height"] / 2,
    )
    expect(page.locator("#lf-composer-quote")).to_have_text(
        "design · lf-option · bg-choice-street"
    )
    expect(option).not_to_have_attribute("chosen", "")
    write(
        page.locator(".lf-composer leaf-text"), "The sample option needs less padding."
    )
    with sending(page, "the design comment"):
        page.keyboard.press("ControlOrMeta+Enter")
    design_comment = [
        event
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment" and event.get("about") == "design"
    ][-1]
    assert design_comment["anchor"] == {"section": "bg-choice-street"}
    # Design mode withholds the card, so the send opened the new thread in the panel,
    # and that opening is the send's to undo: one Escape puts the view away, and the
    # next leaves design mode, the press that came before it.
    expect(page.locator(PANEL)).to_have_attribute("data-open", "thread")
    page.evaluate(RELEASE_FOCUS)
    page.keyboard.press("Escape")
    panel_settled(page, open=False)
    expect(page.locator("body")).to_have_attribute("data-lf-design-mode", "")
    page.keyboard.press("Escape")
    expect(page.locator("body")).not_to_have_attribute("data-lf-design-mode", "")

    def reject(route):
        route.fulfill(
            status=400,
            json={"ok": False, "error": "gallery transport refusal", "final": True},
        )

    page.route("**/api/event", reject)
    change = page.locator('[data-lf-margin-for="bg-replace"]')
    accept = change.get_by_role(
        "button", name=re.compile(r"^Accept the suggested change")
    )
    accept.focus()
    page.keyboard.press("Enter")
    retry = change.get_by_role("button", name="Retry", exact=True)
    expect(retry).to_be_visible()
    expect(change.get_by_role("button", name="Cancel", exact=True)).to_be_visible()
    expect(change).to_contain_text("Failed")
    change.get_by_role("button", name="Cancel", exact=True).focus()
    page.keyboard.press("Enter")
    expect(retry).to_have_count(0)

    consume_browser_errors(page, http_error_console(400))


@pytest.mark.parametrize(
    "placement",
    # Directly in main beside other blocks, and inside one; alone in main is the
    # first case without its neighbours.
    ["among-blocks", "nested"],
)
def test_the_gallery_tab_set_uses_the_boundary_of_its_composition(
    browser, serve, placement
):
    """The same tab vocabulary has page or section scope from where it is placed: the
    first set directly in main is page navigation whatever stands beside it, and a set
    inside another block is a tabbed section."""
    sample = re.search(
        r'<lf-tabs id="bg-tabs">.*?</lf-tabs>', FEATURE_GALLERY.read_text(), re.DOTALL
    )
    assert sample is not None
    heading = "<header><h1>Project views</h1></header>"
    body = {
        "alone": heading + sample[0],
        "among-blocks": heading
        + '<aside class="sidebar"><p>Contents</p></aside>'
        + sample[0]
        + "<p>This conclusion follows the tab set.</p>",
        "nested": heading + "<section>" + sample[0] + "</section>",
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
        # An earlier tab set in main takes over the page's navigation, and this one
        # becomes a tabbed section without being rebuilt.
        stamp_page(
            serve.page_dir,
            original.replace(
                '<lf-tabs id="bg-tabs">',
                '<lf-tabs id="earlier-tabs"><lf-tab id="earlier-tab" label="Earlier">'
                "<p>Earlier views.</p></lf-tab></lf-tabs>"
                '<lf-tabs id="bg-tabs">',
            ),
            "Add an earlier tab set",
        )
        wait_for_revision(page, 2)
        expect(tabs).to_have_css("border-left-width", "1px")
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


@pytest.mark.parametrize("intervene", [False, True])
def test_a_tab_layout_completion_preserves_native_navigation(browser, serve, intervene):
    source = leaf_page(
        "Tab readings",
        '<lf-tabs id="views">'
        + "".join(
            f'<lf-tab id="view-{name.lower()}" label="{name}"><h1>{name}</h1>'
            '<div style="height: 1800px"></div></lf-tab>'
            for name in ("First", "Second")
        )
        + "</lf-tabs>",
    )
    page = open_page(browser, serve(source))
    page.get_by_role("tab", name="Second", exact=True).focus()
    page.evaluate("scrollTo(0, 400)")
    page.keyboard.press("Enter")
    rendered(page)
    page.evaluate("""() => {
      const held = new Promise(resolve => { window.releaseTabLayout = resolve; });
      document.querySelector('#views').addEventListener('lf-layout', event => {
        event.detail.present(held);
        window.tabLayoutStarted = true;
      }, {once: true});
    }""")
    try:
        page.get_by_role("tab", name="First", exact=True).click()
        page.wait_for_function("window.tabLayoutStarted === true")
        assert page.evaluate("location.hash") == "#view-first"
        native_arrival = page.evaluate("scrollY")
        expected = native_arrival + (200 if intervene else 0)
        if intervene:
            page.mouse.move(500, 450)
            page.mouse.wheel(0, 200)
            page.wait_for_function(
                "expected => Math.abs(scrollY - expected) < 1", arg=expected
            )
    finally:
        page.evaluate("releaseTabLayout()")
    rendered(page)
    assert page.evaluate("scrollY") == pytest.approx(expected, abs=1)


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
    assert boundary["selected"]["labelRule"] == {
        "width": 2,
        "color": boundary["selected"]["labelInk"],
    }, boundary
    assert boundary["inactive"]["labelRule"]["color"] == "rgba(0, 0, 0, 0)", boundary
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
