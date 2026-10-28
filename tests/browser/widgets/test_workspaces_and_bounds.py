"""Workspace and pane layout and bounded reading regions: which box scrolls, how a pane
passes its height on, and where a bounded log keeps its reader."""

import re

import pytest
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    ROOT,
    displayed,
    expect_obligations_answered,
    fills_the_window,
    leaf_page,
    open_page,
    pane_scroll_behavior,
    regions_side_by_side,
    resized,
    scroll_settled,
    sending,
    stamp_page,
    told,
    wait_for_revision,
)

from browser.widgets import (
    PLAYGROUND_PAGE,
)
from leaf import data as data_model
from leaf import event_log as events_model
from leaf.render_checks import evaluate_probe, rendered, wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


WORKSPACE_PAGE = leaf_page(
    "workspace reading regions",
    """
  <header>
    <h1>Review queue</h1>
    <p id="review-status"><span class="tag warn">3 waiting</span></p>
  </header>
  <div id="review-regions">
    <lf-pane id="queue" label="Items">
      <div>
        <p>Queue start</p>
        <div style="height: 1100px"></div>
        <p>Queue end</p>
      </div>
    </lf-pane>
    <lf-pane id="detail" label="Selected item">
      <div>
        <p>Detail start</p>
        <div style="height: 1100px"></div>
        <p>Detail end</p>
      </div>
    </lf-pane>
  </div>
  <footer>2 items</footer>
""",
    head=regions_side_by_side("review-regions"),
    layout="workspace",
)


def test_workspace_root_scrollbar_appears_only_when_page_overflows(
    scrollbar_browser, serve
):
    """A workspace scrolls its own panes, so a platform with classic scrollbars shows
    the root's track only where the workspace flows past the window."""
    page = open_page(
        scrollbar_browser,
        serve(WORKSPACE_PAGE),
        # macOS draws the root's scrollbar as an overlay, which takes no width; a styled
        # track is classic on every host, as Linux and Windows draw it.
        init_script="""(() => {
          const sheet = new CSSStyleSheet();
          sheet.replaceSync('html::-webkit-scrollbar { width: 15px; }');
          document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
        })()""",
    )
    resized(page, 1200, 900)
    assert page.evaluate(
        """() => {
          const root = document.documentElement;
          return root.scrollHeight === root.clientHeight &&
            root.clientWidth === window.innerWidth;
        }"""
    )

    resized(page, 1200, 420)
    assert page.evaluate(
        """() => {
          const root = document.documentElement;
          root.scrollTop = root.scrollHeight;
          return root.scrollHeight > root.clientHeight &&
            root.clientWidth < window.innerWidth && root.scrollTop > 0;
        }"""
    )


@pytest.mark.parametrize("captured", [False, True], ids=["block", "text-document"])
def test_a_bounded_document_reader_chains_wheel_at_its_edge(browser, serve, captured):
    """A bound inside a document keeps its own reading position but lets the user
    continue down the document once its last line is reached."""
    content = (
        '<lf-text-document id="reader" source="capture" label="Run log" '
        'data-bound="start"></lf-text-document>'
        if captured
        else '<div id="reader" data-bound="start">'
        + "<p>Run log line</p>" * 100
        + "</div>"
    )
    url = serve(
        leaf_page(
            "Bounded reader in a document",
            "<h1>Run log</h1>" + content + '<div style="height:1500px"></div>',
        )
    )
    if captured:
        data_model.cmd_data_set(serve.page_dir, "capture", "Run log line\n" * 100)
    page = open_page(browser, url)
    if captured:
        # The caption stays above the source that scrolls, as wide as its figure.
        capture = page.locator("#reader")
        caption = capture.locator("figcaption")
        expect(caption).to_be_visible()
        assert capture.evaluate("el => el.scrollHeight === el.clientHeight")
        assert caption.evaluate(
            "el => Math.abs(el.getBoundingClientRect().width - "
            "el.parentElement.getBoundingClientRect().width) <= 2"
        )
    reader = page.locator("#reader pre" if captured else "#reader")
    assert reader.evaluate("el => el.scrollHeight > el.clientHeight")
    reader.evaluate("el => el.scrollTop = el.scrollHeight")
    reader.hover()
    before = page.evaluate("document.scrollingElement.scrollTop")
    page.mouse.wheel(0, 400)
    page.wait_for_function(
        "before => document.scrollingElement.scrollTop > before",
        arg=before,
    )


def test_a_root_workspace_bounds_independent_regions_and_flows_when_it_cannot_fit(
    browser, serve
):
    """The workspace Layout takes the whole window, wider than a sidebar page's capped
    frame, and the window's height: each pane's body scrolls on its own. Its
    header is one row, the title with the status beside it, so the panes keep the
    window. A window too short to hold it hands the scroll to the page."""
    frame = """() => {
      const main = document.querySelector('main');
      const style = getComputedStyle(main);
      const box = main.getBoundingClientRect();
      return [box.left + parseFloat(style.paddingLeft),
              box.width - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)];
    }"""
    declared = open_page(
        browser,
        serve(
            WORKSPACE_PAGE.replace('class="layout-workspace"', 'class="layout-sidebar"')
        ),
    )
    resized(declared, 1920, 720)
    wide = declared.evaluate(frame)
    declared.close()
    page = open_page(browser, serve(WORKSPACE_PAGE))
    resized(page, 1920, 720)
    workspace = page.locator("main")
    queue_pane = page.locator("#queue")
    queue = page.locator("#queue > :not(header, footer)")
    detail = page.locator("#detail > :not(header, footer)")

    pane_scroll_behavior(page, queue_pane, "bounded")
    fills_the_window(page, workspace, True)
    own = page.evaluate(frame)
    assert own[0] < wide[0] and own[1] > wide[1], (own, wide)
    header = page.evaluate(
        """() => {
          const title = document.querySelector('main > header h1');
          const status = document.getElementById('review-status');
          const t = title.getBoundingClientRect(), s = status.getBoundingClientRect();
          return {oneRow: s.top < t.bottom && s.left >= t.right};
        }"""
    )
    assert header["oneRow"], header
    assert page.evaluate("() => document.scrollingElement.scrollTop") == 0
    readings = page.evaluate(
        """() => {
          const body = id => document.querySelector(`#${id} > :not(header, footer)`);
          const queue = body('queue');
          const detail = body('detail');
          return {queue: [queue.clientHeight, queue.scrollHeight],
                  detail: [detail.clientHeight, detail.scrollHeight]};
        }"""
    )
    assert readings["queue"][1] > readings["queue"][0], readings
    assert readings["detail"][1] > readings["detail"][0], readings
    expect(queue).to_have_attribute("data-lf-more-below", "")
    expect(detail).to_have_attribute("data-lf-more-below", "")
    queue.evaluate("el => el.scrollTop = 300")
    page.wait_for_function(
        "() => document.querySelector('#queue > :not(header, footer)').scrollTop > 0"
    )
    assert detail.evaluate("el => el.scrollTop") == 0
    # A pane that leaves the document and returns registers its body again, so the cue
    # that the body holds more comes back with it.
    queue_pane.evaluate(
        """owner => lfUnwatched(() => {
          const parent = owner.parentNode;
          const next = owner.nextSibling;
          owner.remove();
          parent.insertBefore(owner, next);
        })"""
    )
    pane_scroll_behavior(page, queue_pane, "bounded")
    expect(queue).to_have_attribute("data-lf-more-below", "")
    queue.evaluate("el => el.scrollTop = el.scrollHeight")
    expect(queue).not_to_have_attribute("data-lf-more-below", "")
    # Resizing existing content adds unread room without a scroll event. Its cue
    # must accompany that layout, before a later animation frame can repair it.
    grew = queue.evaluate(
        """el => new Promise(resolve => {
          const content = el.querySelector(':scope > div');
          let growing = false;
          const sizes = new ResizeObserver(() => {
            if (!growing) {
              requestAnimationFrame(() => {
                growing = true;
                content.style.height = '1300px';
              });
              return;
            }
            queueMicrotask(() => {
              sizes.disconnect();
              resolve({more: el.hasAttribute('data-lf-more-below'),
                       remaining: el.scrollHeight - el.clientHeight - el.scrollTop});
            });
          });
          sizes.observe(content);
        })"""
    )
    assert grew["remaining"] > 100, grew
    assert grew["more"], grew
    expect(queue).to_have_attribute("data-lf-more-below", "")

    # A window too short to hold the regions hands the scroll to the page, and the
    # page's grid keeps the columns its width allows: the hold decides heights, not
    # placement.
    resized(page, 1280, 420)
    pane_scroll_behavior(page, queue_pane, "flow")
    fills_the_window(page, workspace, False)
    flow = page.evaluate(
        """() => {
          const queue = document.querySelector('#queue').getBoundingClientRect();
          const detail = document.querySelector('#detail').getBoundingClientRect();
          return {queue, detail};
        }"""
    )
    assert flow["detail"]["left"] >= flow["queue"]["right"] - 1, flow
    assert flow["queue"]["height"] > 1100, flow
    expect(queue).not_to_have_attribute("data-lf-more-below", "")
    expect(detail).not_to_have_attribute("data-lf-more-below", "")
    # The scroll behavior is the window's, not the one the user came from.
    resized(page, 1280, 720)
    pane_scroll_behavior(page, queue_pane, "bounded")
    fills_the_window(page, workspace, True)


def test_a_workspace_reaches_the_window_foot_and_its_readers_clear_the_panel(
    browser, serve
):
    page = open_page(browser, serve(WORKSPACE_PAGE))
    resized(page, 1200, 900)
    geometry = page.evaluate(
        """() => {
          const main = document.querySelector('main');
          const reader = document.querySelector('#queue > :not(header, footer)');
          reader.scrollTop = reader.scrollHeight;
          return {
            mainBottom: main.getBoundingClientRect().bottom,
            windowBottom: innerHeight,
            endBottom: [...reader.querySelectorAll('p')].at(-1).getBoundingClientRect().bottom,
            panelTop: document.querySelector('.lf-fp-row').getBoundingClientRect().top,
            paneBottom: document.querySelector('#queue').getBoundingClientRect().bottom,
            footerTop: document.querySelector('main > footer').getBoundingClientRect().top,
          };
        }"""
    )
    assert abs(geometry["mainBottom"] - geometry["windowBottom"]) <= 1, geometry
    assert geometry["endBottom"] <= geometry["panelTop"], geometry
    assert geometry["footerTop"] - geometry["paneBottom"] <= 1, geometry
    assert page.evaluate("document.scrollingElement.scrollHeight <= innerHeight + 1")
    page.locator("body").focus()
    page.keyboard.press(".")
    expect(page.locator(".lf-floating-panel")).to_have_attribute("data-rest", "mark")
    assert page.locator("main").evaluate(
        "node => Math.abs(node.getBoundingClientRect().bottom - innerHeight) <= 1"
    )


def test_a_workspace_body_scroller_clears_the_panel(browser, serve):
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Single-body workspace",
                '<header><h1>Work</h1></header><div id="reader">'
                '<div style="height:1100px"></div><p>End of work</p></div>',
                layout="workspace",
            )
        ),
    )
    resized(page, 1200, 900)
    geometry = page.evaluate(
        """() => {
          const reader = document.querySelector('#reader');
          reader.scrollTop = reader.scrollHeight;
          return {
            scrolls: reader.scrollHeight > reader.clientHeight,
            endBottom: reader.querySelector('p').getBoundingClientRect().bottom,
            panelTop: document.querySelector('.lf-fp-row').getBoundingClientRect().top,
          };
        }"""
    )
    assert geometry["scrolls"], geometry
    assert geometry["endBottom"] <= geometry["panelTop"], geometry


def test_a_flowing_workspace_keeps_its_header_over_what_a_next_lands_on(browser, serve):
    """On a phone the workspace flows and the page scrolls, and its header sticks at the
    window's top, so a tally's Next on me stays under the pointer that pressed it. The
    obligation it lands on stands below the header, which the landing clears, and a
    tab set's sticky strip sticks under it."""

    def item(key):
        return (
            f'<lf-tab id="t-{key}" label="{key}"><lf-ask id="{key}-decision">'
            f'<h2>Pick the {key}</h2><div style="height: 900px"></div>'
            f'<lf-options id="{key}" choose><lf-option id="{key}-a">Alpha</lf-option>'
            "</lf-options></lf-ask></lf-tab>"
        )

    page = open_page(
        browser,
        serve(
            leaf_page(
                "A phone queue",
                '<header><h1>Which alerts should still page?</h1><p id="status">'
                '<lf-tally id="left" for="queue" next></lf-tally>'
                '<span class="tag warn">7 mostly noise</span></p></header>'
                '<lf-tabs id="queue" list="side">'
                + item("first")
                + item("second")
                + "</lf-tabs>"
                '<lf-tabs id="views"><lf-tab id="v-one" label="One">'
                '<div id="v-long" style="height: 1600px"></div></lf-tab>'
                '<lf-tab id="v-two" label="Two"><p>Two</p></lf-tab></lf-tabs>',
                layout="workspace",
            )
        ),
    )
    resized(page, 390, 844)
    button = page.locator("#left").get_by_role("button", name="Next on me")
    before = button.bounding_box()
    button.click()
    expect(page.locator("#first-decision")).to_be_focused()
    button.click()
    second = page.locator("#second-decision")
    expect(second).to_be_focused()
    scroll_settled(page)
    assert page.evaluate("() => document.scrollingElement.scrollTop") > 0
    assert button.bounding_box() == before
    header = page.locator("main > header").bounding_box()
    assert second.bounding_box()["y"] >= header["y"] + header["height"], (
        second.bounding_box(),
        header,
    )
    # A tab set in the body sticks its strip under the header, not behind it.
    page.locator("#v-long").evaluate("el => el.scrollIntoView({block: 'center'})")
    scroll_settled(page)
    strip = page.locator("#views > .lf-tabstrip").bounding_box()
    assert strip["y"] >= header["y"] + header["height"] - 1, (strip, header)
    # The stuck header covers the gutters with paint alone; its box stays in the column.
    assert evaluate_probe(page, "misplacedBoxes") == []


PANE_BAND_PAGE = leaf_page(
    "A pane that opens on its words",
    """
  <div id="band-regions">
    <lf-pane id="band-queue" label="Queue"><ul><li>First ticket</li></ul></lf-pane>
    <lf-pane id="band-detail" label="Detail">
      <div id="band-body">
        <section id="band-ticket">
          <p class="eyebrow" id="band-eyebrow">ESC-1 · sev 1</p>
          <h2>The ticket's title</h2>
          <p>What happened.</p>
        </section>
        <section><h2>Another ticket</h2><p>Its account.</p></section>
      </div>
    </lf-pane>
  </div>
""",
    head=regions_side_by_side("band-regions", "1fr 2fr"),
    layout="workspace",
)


def test_a_pane_opens_on_its_first_words_through_a_bare_wrapper(browser, serve):
    """A pane's body trims the margin at its top edge, and a declared section wrapping its
    content passes its first child's margin to that edge. The eyebrow above a heading
    carries the heading's 48px, which stood as an empty band at the top of the pane;
    the body's own padding is all that stands above the first words."""
    page = open_page(browser, serve(PANE_BAND_PAGE))
    resized(page, 1440, 900)
    rendered(page)
    above = page.evaluate(
        """() => {
          const body = document.getElementById('band-body');
          const top = body.getBoundingClientRect().top
            + parseFloat(getComputedStyle(body).paddingTop);
          return document.getElementById('band-eyebrow').getBoundingClientRect().top - top;
        }"""
    )
    assert abs(above) < 1, above


def test_a_table_at_a_pane_top_is_under_no_sticky_header(browser, serve):
    """A workspace pane's body starts `--lf-top` at minus its top padding and a table
    starts it at 0, since each scrolls; neither stacks a header, so a cell scrolled to
    just below the pane's top edge reads as shown from where it stands."""
    filler = "<p>Filler.</p>" * 40
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Pane table",
                '<header><h1>Pane table</h1></header><lf-pane id="p1" label="Detail">'
                "<header><h2>Detail</h2></header><div><p>Lead paragraph.</p>"
                '<table id="t1"><tbody><tr><td id="c1">one</td><td>1</td></tr>'
                "<tr><td>two</td><td>2</td></tr></tbody></table>"
                + filler
                + "</div></lf-pane>",
                layout="workspace",
            )
        ),
    )
    resized(page, 1280, 720)
    read = page.evaluate(
        """async () => {
        const geometry = await window.__lfCheckApi();
        const body = document.querySelector('#p1 > div');
        const cell = document.querySelector('#c1');
        const band = geometry.shownBand(body);
        body.scrollTop += cell.getBoundingClientRect().top - band.top - 5;
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        return {
            band: geometry.shownBand(body).top,
            cell: cell.getBoundingClientRect().top,
            shown: geometry.shownRect(cell, new Map())?.top,
        };
    }"""
    )
    assert read["cell"] == pytest.approx(read["band"] + 5, abs=1), read
    assert read["shown"] == pytest.approx(read["cell"], abs=0.5), read


def clear_of_the_bottom_chrome(page, selector):
    """Scroll the target's reading box to its end and measure it against the panel.

    The row is the fixed chrome a page's last line has to scroll clear of; a page whose
    end room is missing leaves that line under it however far the user scrolls."""
    return page.evaluate(
        """async selector => {
          const {scrollerFor} = await window.__lfWidgetApi();
          const target = document.querySelector(selector);
          const scroller = scrollerFor(target) ?? document.scrollingElement;
          scroller.scrollTop = scroller.scrollHeight;
          const row = document.querySelector('.lf-fp-row').getBoundingClientRect();
          const box = target.getBoundingClientRect();
          return {bottom: box.bottom, row: row.top, clear: box.bottom <= row.top + 1};
        }""",
        selector,
    )


LONG_PANE = """<lf-pane id="workspace-pane" label="Long reading"><div>
  <p>Start</p><div style="height: 900px"></div><p id="pane-end">End</p>
</div></lf-pane>"""


SECTIONED_PANE_PAGE = leaf_page(
    "a pane in a section",
    f"""<div id="cells">
  <section><h2>Section heading</h2>{LONG_PANE}</section>
  <section><h2>Beside it</h2><p>A short cell.</p></section>
</div>""",
    head=regions_side_by_side("cells"),
    layout="workspace",
)


THREE_PART_OBLIGATION_PAGE = leaf_page(
    "a three-part obligation as the workspace",
    """
  <lf-ask id="workspace-ask">
    <h2>Which release should go out?</h2>
    <div id="ask-context" style="height: 900px">The context the user weighs.</div>
    <lf-options id="workspace-options" choose>
      <lf-option id="workspace-ship">Ship it</lf-option>
      <lf-option id="workspace-hold">Hold it</lf-option>
    </lf-options>
  </lf-ask>
""",
    layout="workspace",
)


def test_a_bounded_stream_that_is_all_a_pane_holds_takes_the_panes_height(
    browser, serve
):
    """A full-height workspace's pane body has the window's height to give, so a bounded
    stream that is all it holds fills it rather than scrolling 28rem of it; one beside
    other blocks keeps its bound, and so does a bounded block inside another, whose
    holder has only a cap and no height to give."""
    rows = "".join(f"<p>Event {i}.</p>" for i in range(80))
    source = leaf_page(
        "Streams in panes",
        f"""<header><h1>Streams</h1></header>
<div id="regions">
<lf-pane id="alone" label="Alone"><div id="alone-body">
<div id="feed" data-bound="start">{rows}</div></div></lf-pane>
<lf-pane id="mixed" label="Mixed"><div><p>Intro.</p>
<div id="beside" data-bound="start">{rows}</div>
<div id="outer" data-bound="start" style="--lf-bound: 300px">
<div id="inner" data-bound="start" style="--lf-bound: 120px">{rows}</div></div>
</div></lf-pane>
</div>""",
        head=regions_side_by_side("regions"),
        layout="workspace",
    )
    page = open_page(browser, serve(source))
    resized(page, 1440, 900)
    at = page.evaluate(
        """() => {
          const box = id => document.getElementById(id).getBoundingClientRect();
          const body = document.getElementById('alone-body');
          const style = getComputedStyle(body);
          return {
            feed: Math.round(box('feed').height),
            room: Math.round(body.clientHeight - parseFloat(style.paddingTop)
              - parseFloat(style.paddingBottom)),
            beside: Math.round(box('beside').height),
            inner: Math.round(box('inner').height),
            rem: parseFloat(getComputedStyle(document.documentElement).fontSize),
          };
        }"""
    )
    assert at["feed"] == pytest.approx(at["room"], abs=1), at
    assert at["beside"] == round(28 * at["rem"]), at
    assert at["inner"] == 120, at


def test_a_pane_inside_a_plain_section_of_a_workspace_flows(browser, serve):
    """Only a box that passes the height on holds what it contains. A section in the
    body's grid is a grouping, so a pane in one takes its natural height and the body,
    which fills the window, scrolls it. The control is the same pane as the workspace's
    body, which fills the window.

    Whatever the user scrolls to in that full-height workspace clears the panel's row,
    as a document's last line does: the body scrolls as a whole and its end stands
    above the band. So only the pane that is the body reserves the panel's room in its
    own reader; the pane inside the section, which the body's end room already
    clears, keeps its inset alone."""
    page = open_page(browser, serve(SECTIONED_PANE_PAGE))
    resized(page, 1280, 720)
    pane = page.locator("#workspace-pane")
    pane_scroll_behavior(page, pane, "flow")
    assert pane.evaluate(
        """async node => {
          const leaf = await window.__lfWidgetApi();
          return leaf.regionScrollBehavior(node) === 'flow'
            && leaf.scrollerFor(node) === document.getElementById('cells');
        }"""
    )
    fills_the_window(page, page.locator("main"), True)
    # Every reader asks one owner which box scrolls a node, so the body that now scrolls
    # is the answer for the pane it carries: page steps and reading-place recovery move
    # the box the user sees move.
    carrier = page.evaluate(
        """async () => {
          const {scrollerFor} = await window.__lfWidgetApi();
          return scrollerFor(document.getElementById('pane-end'))?.id ?? null;
        }"""
    )
    assert carrier == "cells", carrier
    page.locator("#pane-end").evaluate("node => node.scrollIntoView({block: 'end'})")
    end = clear_of_the_bottom_chrome(page, "#pane-end")
    assert end["clear"], end
    # The body's end room already clears the panel, so the pane keeps only its inset.
    assert foot_reserve(page) == 0
    page.close()

    direct = leaf_page("a pane as the workspace body", LONG_PANE, layout="workspace")
    page = open_page(browser, serve(direct))
    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#workspace-pane"), "bounded")
    fills_the_window(page, page.locator("main"), True)
    # A pane that reaches the window's foot keeps the panel's room in its reader.
    assert foot_reserve(page) > 0


def foot_reserve(page):
    """How far #workspace-pane's reader pads its end beyond the pane inset."""
    return page.locator("#workspace-pane > div").evaluate(
        """reader => {
          const style = getComputedStyle(reader);
          return Math.round(
            parseFloat(style.paddingBlockEnd) -
              parseFloat(style.getPropertyValue('--pane-inset'))
          );
        }"""
    )


ZONE_PACKAGE = {
    "lf-zone": {
        "description": "A project package's differently named pane.",
        "type": "object",
        "properties": {"id": {"type": "string"}, "label": {"type": "string"}},
        "required": ["id", "label"],
        "additionalProperties": False,
        "x-content": "markup",
        "x-reading-role": "pane",
        "x-upgrade": False,
    }
}


NESTED_PANES_PAGE = leaf_page(
    "a pane in a pane's body",
    """<div id="cells">
  <lf-zone id="outer-zone" label="Zones"><div>
    <lf-zone id="inner-zone" label="Inner zone"><div>
      <p>A zone's reading.</p><div style="height: 900px"></div>
    </div></lf-zone>
  </div></lf-zone>
  <lf-pane id="outer-pane" label="Panes"><div>
    <lf-pane id="inner-pane" label="Inner pane"><div>
      <p>A pane's reading.</p><div style="height: 900px"></div>
    </div></lf-pane>
  </div></lf-pane>
</div>""",
    head=regions_side_by_side("cells"),
    layout="workspace",
)


def test_a_package_pane_is_held_where_an_lf_pane_is(browser, serve):
    """Which panes a full-height workspace scrolls is read from the pane role, whichever
    package names the tag. A package's pane that is a cell of the body scrolls its own
    body, and one written inside that pane's body is content there and scrolls with it,
    exactly as lf-panes nested the same way do. The role arrives with the document, so
    the workspace holds the same panes while the runtime has not started."""
    boot = []
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()
    page.route("**/leaf.js", lambda route: boot.append(route))
    url = serve(NESTED_PANES_PAGE, layer_registry=ZONE_PACKAGE)

    def scroll_behaviors():
        for tag in ("zone", "pane"):
            pane_scroll_behavior(page, page.locator(f"#outer-{tag}"), "bounded")
            pane_scroll_behavior(page, page.locator(f"#inner-{tag}"), "flow")

    try:
        with page.expect_request("**/leaf.js"):
            page.goto(url, wait_until="commit")
        displayed(page)
        assert boot, "the runtime was not held"
        scroll_behaviors()
        boot.pop().continue_()
        wait_until_ready(page)
        scroll_behaviors()
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")


def test_an_lf_ask_gives_its_answer_what_its_context_leaves(browser, serve):
    """An lf-ask as the workspace's body gives its last part, the answer, what its heading
    and context leave, and never less than the answer's own height: below a context
    taller than the window the options keep theirs, nothing is drawn over them, and the
    body scrolls. A playground below a premise fits itself to what is left, its controls
    scrolling within the window."""
    page = open_page(browser, serve(THREE_PART_OBLIGATION_PAGE))
    resized(page, 1280, 720)
    geometry = page.evaluate(
        """() => ({
          context: document.querySelector('#ask-context').getBoundingClientRect().bottom,
          options: document.querySelector('#workspace-options').getBoundingClientRect(),
        })"""
    )
    assert geometry["options"]["top"] >= geometry["context"] - 1, geometry
    assert geometry["options"]["height"] > 40, geometry
    ask = page.locator("#workspace-ask")
    assert ask.evaluate("node => node.scrollHeight > node.clientHeight")
    ask.evaluate("node => { node.scrollTop = node.scrollHeight; }")
    end = clear_of_the_bottom_chrome(page, "#workspace-options")
    assert end["clear"], end
    page.close()

    with_premise = (
        PLAYGROUND_PAGE.replace("<h1>Card playground</h1>\n", "")
        .replace(
            "<h2>How should the card look?</h2>",
            "<h2>How should the card look?</h2>\n  <p>The card leads the release page.</p>",
        )
        .replace('<main class="layout-column">', '<main class="layout-workspace">')
    )
    page = open_page(browser, serve(with_premise))
    resized(page, 1280, 720)
    expect(page.locator("#card-playground-ask")).to_have_css("display", "flex")
    pane_scroll_behavior(
        page, page.locator(".lf-playground-controls-region"), "bounded"
    )
    fills_the_window(page, page.locator("main"), True)


def test_the_page_end_clears_the_bottom_chrome_around_a_workspace(browser, serve):
    """A document keeps its end room with a pane inside it; a workspace that flows gives
    its last block that room, and a full-height one does not scroll."""
    document = leaf_page(
        "a pane mid-document",
        f"""
<h1>A document with a pane</h1>
<p>Before the pane.</p>
{LONG_PANE}
{"<p>After the pane.</p>" * 30}
<p id="document-end">The document's last line.</p>
""",
    )
    page = open_page(browser, serve(document))
    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#workspace-pane"), "flow")
    room = page.evaluate(
        """() => {
          const probe = document.createElement('div');
          probe.style.cssText = 'position:fixed;visibility:hidden;height:var(--lf-foot-room)';
          document.body.append(probe);
          const band = probe.getBoundingClientRect().height;
          probe.remove();
          return {
            padding: parseFloat(getComputedStyle(document.body).paddingBottom),
            band,
            panel: innerHeight
              - document.querySelector('.lf-fp-row').getBoundingClientRect().top,
          };
        }"""
    )
    # The page's end room is the band's stated height, which holds the panel's row.
    assert room["padding"] == room["band"] >= room["panel"] > 0, room
    end = clear_of_the_bottom_chrome(page, "#document-end")
    assert end["clear"], end
    page.close()

    root = leaf_page("a workspace", LONG_PANE, layout="workspace")
    page = open_page(browser, serve(root))
    resized(page, 1280, 420)
    pane_scroll_behavior(page, page.locator("#workspace-pane"), "flow")
    end = clear_of_the_bottom_chrome(page, "#pane-end")
    assert end["clear"], end

    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#workspace-pane"), "bounded")
    fills_the_window(page, page.locator("main"), True)


@pytest.mark.parametrize(
    "container", ["views", "pane", "plain", "workspace-footer", "pane-footer"]
)
def test_workspace_end_room_stays_inside_the_last_reading_region(
    browser, serve, container
):
    """The frame reaches the window's foot; its final control scrolls clear of chrome.

    Nested page and side views exercise the transfer: reserving clearance on the
    outside view instead leaves a band below the actual reading pane.
    """
    reading = '<p>Start</p><div style="height:1200px"></div><button id="reading-end">Finish review</button>'
    if container.endswith("footer"):
        body, button = reading.split("<button", 1)
        footer = '<footer style="text-align:center"><button' + button + "</footer>"
        if container == "workspace-footer":
            content = '<section id="reading">' + body + "</section>" + footer
            frame = "main"
        else:
            content = (
                '<lf-pane id="frame" label="Review"><div id="reading">'
                + body
                + "</div>"
                + footer
                + "</lf-pane>"
            )
            frame = "#frame"
        scroller = "#reading"
    elif container == "views":
        content = (
            '<lf-tabs id="outer"><lf-tab id="review" label="Review">'
            '<lf-tabs id="frame" list="side"><lf-tab id="reading" label="Experiment">'
            + reading
            + '</lf-tab><lf-tab id="other" label="Other"><p>Other result</p></lf-tab>'
            "</lf-tabs></lf-tab></lf-tabs>"
        )
        scroller = "#reading"
    elif container == "pane":
        content = (
            '<lf-pane id="frame" label="Review"><div id="reading">'
            + reading
            + "</div></lf-pane>"
        )
        scroller = "#reading"
    else:
        content = '<div id="frame">' + reading + "</div>"
        scroller = "#frame"
    if not container.endswith("footer"):
        frame = "#frame"
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Review results",
                "<header><h1>Review results</h1></header>" + content,
                layout="workspace",
            )
        ),
    )
    for width, height in [(1440, 1000), (695, 988)]:
        resized(page, width, height)
        if width >= 720:
            page.locator(scroller).evaluate("el => el.scrollTop = el.scrollHeight")
        page.evaluate(
            "() => document.scrollingElement.scrollTop = document.scrollingElement.scrollHeight"
        )
        geometry = page.evaluate(
            """selector => {
            const frame = document.querySelector(selector).getBoundingClientRect();
            const end = document.getElementById('reading-end').getBoundingClientRect();
            const panel = document.querySelector('.lf-fp-row').getBoundingClientRect();
            return {frameBottom: frame.bottom, endBottom: end.bottom, panelTop: panel.top, height: innerHeight};
        }""",
            frame,
        )
        assert geometry["frameBottom"] == pytest.approx(height, abs=6), geometry
        assert geometry["endBottom"] <= geometry["panelTop"] + 1, geometry


def test_a_comment_in_a_pane_leaves_its_grammar_whole(browser, serve):
    """A comment in a pane stands as a pin in the pane's own lane, over the block it
    serves. Leaf inserts nothing into the pane, so a pane whose one body element is that
    block keeps it as its one body and goes on scrolling it."""
    source = leaf_page(
        "a comment in a pane",
        """
  <lf-pane id="workspace-pane" label="Only a paragraph">
    <p id="only">A paragraph that is the whole body of its pane.</p>
  </lf-pane>
""",
        layout="workspace",
    )
    page = open_page(browser, serve(source))
    resized(page, 1000, 720)
    pane_scroll_behavior(page, page.locator("#workspace-pane"), "bounded")
    page.locator("#only").click(click_count=3)
    page.locator(".lf-fab-input").click()
    page.keyboard.type("A thread on the paragraph.")
    with sending(page, "the comment on the paragraph"):
        page.keyboard.press("ControlOrMeta+Enter")
    page.keyboard.press("Escape")  # off the paragraph the send landed on, and its card
    row = page.locator('.lf-margin-lane [data-lf-margin-for="only"]')
    expect(row).to_have_count(1)
    expect(row).to_have_attribute("data-lf-place", "pin")
    expect(page.locator("#workspace-pane .lf-margin-cluster")).to_have_count(0)
    expect(page.locator("#workspace-pane > *")).to_have_count(1)
    pane_scroll_behavior(page, page.locator("#workspace-pane"), "bounded")


def test_regions_inside_a_bounded_pane_body_flow_within_the_body_that_scrolls(
    browser, serve
):
    """A pane written inside a bounded pane's body is that body's content, loose or in a
    section: it takes its natural height and the outer body scrolls it, so reading keys
    and continuity name the box that actually moves. The control is the outer pane,
    which fills the same window."""
    source = leaf_page(
        "regions inside a pane body",
        """
  <lf-pane id="host" label="Host"><div id="host-body">
    <p>Host start</p>
    <section>
      <lf-pane id="inner-pane" label="Inner pane">
        <div><p>Start</p><div style="height: 900px"></div><p>End</p></div>
      </lf-pane>
    </section>
    <lf-pane id="loose-pane" label="Loose pane">
      <div><p>Start</p><div style="height: 900px"></div><p>End</p></div>
    </lf-pane>
  </div></lf-pane>
""",
        layout="workspace",
    )
    page = open_page(browser, serve(source))
    resized(page, 1280, 720)
    pane_scroll_behavior(page, page.locator("#host"), "bounded")
    for inner in ("#inner-pane", "#loose-pane"):
        pane_scroll_behavior(page, page.locator(inner), "flow")
    readings = page.evaluate(
        """async () => {
          const leaf = await window.__lfWidgetApi();
          const host = document.querySelector('#host-body');
          return Object.fromEntries(['inner-pane', 'loose-pane'].map(id => {
            const body = document.querySelector(`#${id} > div`);
            return [id, {scroll_behavior: leaf.regionScrollBehavior(id),
                         scroller: leaf.scrollerFor(document.getElementById(id)) === host,
                         fits: body.scrollHeight <= body.clientHeight}];
          }).concat([['host', host.scrollHeight > host.clientHeight]]));
        }"""
    )
    assert readings == {
        "inner-pane": {"scroll_behavior": "flow", "scroller": True, "fits": True},
        "loose-pane": {"scroll_behavior": "flow", "scroller": True, "fits": True},
        "host": True,
    }


def test_a_release_page_is_wide_and_keeps_the_log_on_its_newest_line(browser, serve):
    """A sidebar page of body and track: the lede starts at the page's edge and keeps
    the reading measure, as does the status callout, every other region of the body
    shares the body's two edges and every region of the track its content edges,
    leaving room for focus rings inside the track, and the
    checks table's box fills its panel. On a narrow
    window the track stacks under the body, and the bounded log opens on its newest
    line. Paper shows the log whole."""
    example = ROOT / "examples" / "live-progress.html"
    context = browser.new_context(viewport={"width": 1600, "height": 1000})
    page = open_page(browser, live_url(serve(example)), context=context)
    body = ["lp-status", "lp-traffic", "lp-log"]
    rail = ["lp-steps", "lp-checks", "lp-release"]
    ids = [*body, *rail, "lp-checks-table", "lp-lede", "lp-current-state"]
    boxes = f"""() => {{
      const read = Object.fromEntries({ids!r}.map(id =>
        [id, document.getElementById(id).getBoundingClientRect().toJSON()]));
      const main = document.querySelector('main');
      const style = getComputedStyle(main);
      const box = main.getBoundingClientRect();
      const left = box.left + parseFloat(style.paddingLeft);
      const right = box.right - parseFloat(style.paddingRight);
      read.main = {{left, right, width: right - left}};
      const track = document.querySelector('[data-lf-track-body]');
      const trackBox = track.getBoundingClientRect();
      const trackStyle = getComputedStyle(track);
      read.track = {{
        right: trackBox.right,
        contentRight: trackBox.right - parseFloat(trackStyle.paddingRight),
      }};
      return read;
    }}"""

    wide = page.evaluate(boxes)
    page_box = wide["main"]
    assert page_box["width"] > 1080, "the page should take the room past the wide width"
    assert wide["lp-lede"]["left"] == pytest.approx(page_box["left"], abs=1)
    assert wide["lp-lede"]["width"] <= 720 + 1
    assert wide["lp-current-state"]["left"] == pytest.approx(page_box["left"], abs=1)
    assert wide["lp-current-state"]["width"] == pytest.approx(720, abs=1)
    for track in (body, rail):
        for edge in ("left", "right"):
            assert {round(wide[i][edge]) for i in track} == {
                round(wide[track[0]][edge])
            }
    assert wide["lp-status"]["left"] == pytest.approx(page_box["left"], abs=1)
    assert wide["track"]["right"] == pytest.approx(page_box["right"], abs=1)
    assert wide["lp-steps"]["right"] == pytest.approx(
        wide["track"]["contentRight"], abs=1
    )
    assert wide["lp-log"]["right"] < wide["lp-steps"]["left"]
    assert wide["lp-checks-table"]["width"] > wide["lp-checks"]["width"] - 48
    listing = page.locator("#lp-live-log pre")
    assert listing.evaluate(
        "pre => pre.scrollHeight > pre.clientHeight && "
        "pre.scrollHeight - pre.scrollTop - pre.clientHeight <= 2"
    ), "the bounded log should open on its newest line"
    assert page.evaluate("scrollY") == 0, "following the log should not move the page"
    page.locator("#lp-live-log").scroll_into_view_if_needed()
    expect(page.locator("#lp-live-log figcaption")).to_be_in_viewport()

    resized(page, 560, 900)
    narrow = page.evaluate(boxes)
    assert narrow["lp-steps"]["top"] >= narrow["lp-log"]["bottom"]
    assert narrow["lp-checks"]["top"] >= narrow["lp-steps"]["bottom"]
    assert narrow["lp-steps"]["width"] == narrow["lp-log"]["width"]

    page.emulate_media(media="print")
    assert listing.evaluate("pre => getComputedStyle(pre).maxHeight") == "none"


FEED_PAGE = leaf_page(
    "A feed that follows its newest entry",
    """<h1>Feed</h1>
<div id="feed" data-bound="end"></div>""",
)


def test_a_bound_at_its_end_follows_a_rebuilt_feed_until_the_user_scrolls_back(
    browser, serve
):
    """A widget that replaces its children on every change stays on its newest entry
    while the user is at the end, and leaves a user who scrolled back where they
    stopped."""
    page = open_page(browser, live_url(serve(FEED_PAGE)))
    rebuild = """count => document.getElementById('feed').replaceChildren(
      ...Array.from({length: count}, (_, i) => Object.assign(
        document.createElement('p'), {textContent: `entry ${i}`})))"""
    at_end = """() => { const feed = document.getElementById('feed');
      return feed.scrollHeight > feed.clientHeight
        && feed.scrollHeight - feed.scrollTop - feed.clientHeight <= 2; }"""
    page.evaluate(rebuild, 60)
    page.wait_for_function(at_end)
    page.evaluate(rebuild, 90)
    page.wait_for_function(at_end)

    # The bound follows its end during resize delivery. Its continuation cue reads
    # that final position in the same paint, even if reach observed the old one first.
    resized_end = page.locator("#feed").evaluate(
        """el => new Promise(resolve => {
          let shrinking = false;
          const sizes = new ResizeObserver(() => {
            if (!shrinking) {
              requestAnimationFrame(() => {
                shrinking = true;
                el.style.maxHeight = '200px';
              });
              return;
            }
            queueMicrotask(() => {
              sizes.disconnect();
              resolve({more: el.hasAttribute('data-lf-more-below'),
                       remaining: el.scrollHeight - el.clientHeight - el.scrollTop});
            });
          });
          sizes.observe(el);
        })"""
    )
    assert resized_end["remaining"] <= 2, resized_end
    assert not resized_end["more"], resized_end

    page.locator("#feed").evaluate("feed => feed.scrollTop = 200")
    page.wait_for_function("() => document.getElementById('feed').scrollTop === 200")
    page.evaluate(rebuild, 120)
    page.evaluate("() => new Promise(requestAnimationFrame)")
    assert page.locator("#feed").evaluate("feed => feed.scrollTop") == 200


def test_a_declared_inner_scroller_can_be_rebuilt_without_taking_a_nested_bound(
    browser, serve
):
    """The host names its scrolling box even when a nested bound has a match first.
    Replacing that box registers its successor and resumes following its end."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Nested bounded listings",
                '<h1>Logs</h1><div id="outer" data-bound="end">'
                '<div id="inner" data-bound="start"><div class="listing">'
                + "<p>Nested entry</p>" * 30
                + '</div></div><div id="listing" class="listing"></div></div>',
                head="""<style>
                  #outer { --lf-bound-box: .listing; max-block-size: none;
                    overflow: visible; }
                  #inner, #outer > .listing { max-block-size: 120px; overflow: auto; }
                </style>""",
            )
        ),
    )
    regions = """async () => {
      const { readingRegions } = await window.__lfCheckApi();
      return Object.fromEntries(readingRegions()
        .filter(({host}) => ['outer', 'inner'].includes(host.id))
        .map(({host, body}) => [host.id, body.id]));
    }"""
    assert page.evaluate(regions) == {"outer": "listing", "inner": "inner"}
    page.evaluate(
        """() => {
          const box = document.createElement('div');
          box.id = 'replacement'; box.className = 'listing';
          box.innerHTML = '<p>Arrived entry</p>'.repeat(60);
          document.getElementById('listing').replaceWith(box);
        }"""
    )
    page.wait_for_function(
        """() => { const box = document.getElementById('replacement');
          return box.scrollHeight > box.clientHeight &&
            box.scrollHeight - box.scrollTop - box.clientHeight <= 2; }"""
    )
    assert page.evaluate(regions) == {"outer": "replacement", "inner": "inner"}


def test_logs_in_a_hidden_tab_open_on_their_newest_entries(browser, serve):
    """A bounded log in a tab the user is not viewing grows, and another arrives,
    without Leaf styling or measuring either while the tab is hidden. Opening the tab
    shows each log's newest entry, every time the logs grew while hidden. Such a read
    makes the browser style the hidden panel first, and in Chromium that forced pass left
    a decided suggestion's retired words showing (#1868)."""
    entry = "<p>Entry: the deploy copied a shard to the new key format.</p>"
    url = serve(
        leaf_page(
            "Logs in a hidden tab",
            '<h1>Deploy</h1><section><lf-tabs id="views">'
            '<lf-tab id="summary" label="Summary"><p>Running.</p></lf-tab>'
            f'<lf-tab id="history" label="History"><div id="log" data-bound="end">'
            f"{entry * 30}</div></lf-tab></lf-tabs></section>",
        )
    )
    page = open_page(browser, live_url(url))
    resized(page, 1280, 900)
    tabs = page.locator("#views")
    summary = tabs.get_by_role("tab", name="Summary", exact=True)
    history = tabs.get_by_role("tab", name="History", exact=True)
    page.evaluate(
        """() => {
          window.lfAsked = [];
          const inLog = (el) =>
            el instanceof Element && document.getElementById('history')
              .contains(el.closest('[data-lf-bound]'));
          const style = window.getComputedStyle;
          window.getComputedStyle = function (el, ...rest) {
            if (inLog(el)) window.lfAsked.push(`style ${el.localName}`);
            return style.call(this, el, ...rest);
          };
          for (const name of ['scrollTop', 'scrollHeight', 'clientHeight']) {
            const read = Object.getOwnPropertyDescriptor(Element.prototype, name);
            Object.defineProperty(Element.prototype, name, {
              ...read,
              get() {
                if (inLog(this)) window.lfAsked.push(`${name} ${this.localName}`);
                return read.get.call(this);
              },
            });
          }
        }"""
    )
    grow = """([id, count]) => document.getElementById(id).append(
      ...Array.from({length: count}, (_, i) => Object.assign(
        document.createElement('p'), {textContent: `Arrived ${i}`})))"""
    arrive = """() => document.getElementById('history').append(Object.assign(
      document.createElement('div'), {id: 'later'}))"""
    at_end = """() => ['log', 'later'].every((id) => {
      const log = document.getElementById(id);
      return log.scrollHeight > log.clientHeight
        && log.scrollHeight - log.scrollTop - log.clientHeight <= 2; })"""

    expect(summary).to_have_attribute("aria-selected", "true")
    page.evaluate(arrive)
    page.evaluate("() => document.getElementById('later').dataset.lfBound = 'end'")
    page.evaluate(grow, ["later", 30])
    for _ in range(2):
        expect(summary).to_have_attribute("aria-selected", "true")
        page.evaluate(grow, ["log", 20])
        page.evaluate(grow, ["later", 20])
        rendered(page)
        assert page.evaluate("() => window.lfAsked.splice(0)") == []
        history.click()
        page.wait_for_function(at_end)
        summary.click()
        page.evaluate("() => window.lfAsked.splice(0)")


def test_closed_details_region_is_not_sampled_until_open(browser, serve):
    url = serve(
        leaf_page(
            "Log in a disclosure",
            '<details id="history"><summary>History</summary>'
            '<div id="log" data-bound="end"><p>Entry</p></div></details>',
        )
    )
    page = open_page(browser, live_url(url))
    region_ids = """async () => {
      const { readingRegions, unconcealedReadingRegions } =
        await window.__lfCheckApi();
      return {
        registered: readingRegions().map(({ id }) => id),
        sampled: unconcealedReadingRegions().map(({ id }) => id),
      };
    }"""
    closed = page.evaluate(region_ids)
    assert "lf-region:log:bound" in closed["registered"]
    assert "lf-region:log:bound" not in closed["sampled"]
    page.locator("#history summary").click()
    assert "lf-region:log:bound" in page.evaluate(region_ids)["sampled"]


def revised_log(first, last):
    """A page whose log bounded at its end holds entries `first` to `last`."""
    filler = "".join(
        f"<p>Filler paragraph {n}, long enough to occupy a line of reading.</p>"
        for n in range(20)
    )
    entries = "".join(
        f"<p>Entry {n}: the deploy copied shard {n} to the new key format.</p>"
        for n in range(first, last)
    )
    return leaf_page(
        "a revised log",
        f'<h1 id="t">Deploy</h1>{filler}<div id="log" data-bound="end">{entries}'
        f"</div>{filler}",
    )


def test_a_revision_leaves_a_following_log_at_its_end_and_a_reader_on_their_line(
    browser, serve
):
    """A bounded log is a reading region, so a revision restores the place the user had
    in it. The place of a log following its newest entry is its end: restoring the line
    that stood at its top would have left the user above the entries the revision
    added, and ended the following. A user who scrolled back keeps the line they were
    reading, however many entries arrived above it."""
    url = serve(revised_log(10, 60))
    page = open_page(browser, live_url(url))
    resized(page, 1280, 900)
    log = page.locator("#log")
    at_end = """log => log.scrollHeight > log.clientHeight
      && log.scrollHeight - log.scrollTop - log.clientHeight <= 2"""
    page.wait_for_function(f"({at_end})(document.getElementById('log'))")
    page.evaluate(
        """log => { const at = log.getBoundingClientRect();
          document.scrollingElement.scrollBy({
            top: at.top + at.height / 2 - innerHeight / 2, behavior: 'instant'}); }""",
        log.element_handle(),
    )
    scroll_settled(page)

    (serve.page_dir / "index.html").write_text(revised_log(10, 80))
    told(page)
    expect(log.locator("p")).to_have_count(70)
    rendered(page)
    assert log.evaluate(at_end), "the revision left the log above its newest entries"

    # Scrolled back to Entry 30, with ten entries arriving above it.
    reading = log.locator("p", has_text="Entry 30:")
    log.evaluate(
        """(log, line) => log.scrollTop += line.getBoundingClientRect().top
          - log.getBoundingClientRect().top""",
        reading.element_handle(),
    )
    scroll_settled(page, "#log")
    where = """([log, line]) => line.getBoundingClientRect().top
      - log.getBoundingClientRect().top"""
    handles = [log.element_handle(), reading.element_handle()]
    before = page.evaluate(where, handles)
    (serve.page_dir / "index.html").write_text(revised_log(0, 80))
    told(page)
    expect(log.locator("p")).to_have_count(80)
    rendered(page)
    after = page.evaluate(
        where,
        [log.element_handle(), log.locator("p", has_text="Entry 30:").element_handle()],
    )
    assert after == pytest.approx(before, abs=2), "the reader lost their line"
    assert not log.evaluate(at_end)


def test_monitoring_evidence_moves_without_stealing_position_or_the_summary(
    browser, serve
):
    """Replaceable log evidence does not become the authority for release state.

    The release escape path is a question the operator answers: the page lists it
    among its obligations, and the pick reaches the agent as an action naming the option."""
    example = ROOT / "examples" / "live-progress.html"
    page = open_page(browser, live_url(serve(example)))
    expect_obligations_answered(page, "0/1")
    with sending(page, "the rollback pick"):
        page.locator("#lp-rollback-now").click()
    pick = events_model.read_events(serve.page_dir)[-1]
    assert (pick["kind"], pick["widget"], pick["action"]) == (
        "action",
        "lp-rollback",
        "choose",
    )
    assert pick["detail"] == {"value": ["lp-rollback-now"]}
    expect_obligations_answered(page, "1/1")

    log = page.locator("#lp-live-log")
    listing = log.locator("pre")

    # A user who scrolled back through the log stays where they stopped.
    listing.evaluate("pre => pre.scrollTop = 120")
    page.wait_for_function(
        "() => document.querySelector('#lp-live-log pre').scrollTop === 120"
    )
    original = listing.text_content()
    data_model.cmd_data_set(
        serve.page_dir,
        "release-log",
        f"{original.rstrip()}\n14:24:49 observer  checkout remains healthy\n",
    )
    told(page)
    expect(log).to_contain_text("14:24:49 observer  checkout remains healthy")
    assert listing.evaluate("pre => pre.scrollTop") == 120

    # One at the end follows what arrives there.
    listing.evaluate("pre => pre.scrollTop = pre.scrollHeight")
    data_model.cmd_data_set(
        serve.page_dir,
        "release-log",
        f"{listing.text_content().rstrip()}\n14:24:54 observer  sample=49 healthy\n",
    )
    told(page)
    expect(log).to_contain_text("14:24:54 observer  sample=49 healthy")
    page.wait_for_function(
        """() => { const pre = document.querySelector('#lp-live-log pre');
          return pre.scrollHeight - pre.scrollTop - pre.clientHeight <= 2; }"""
    )

    current = (serve.page_dir / "index.html").read_text(encoding="utf-8")
    incorporated = current
    revisions = (
        (
            (
                "The production canary is paused at 25%. Customer checkout is healthy, but\n"
                "        finance export is one row short and must reconcile before traffic expands."
            ),
            (
                "Finance export parity now passes. The production release is expanding from\n"
                "        the 25% canary to all checkout traffic."
            ),
        ),
        (
            "<strong>Paused at 25%</strong>",
            "<strong>Promoting to 100%</strong>",
        ),
        (
            (
                "Automatic promotion stopped when the finance-parity check failed. The candidate\n"
                "        remains live for canary traffic while Ledger traces a partial-refund fixture\n"
                "        mismatch; the exact failing producer is not yet established."
            ),
            (
                "The rebuilt export contains every expected order. Traffic is increasing\n"
                "        while the observer keeps the release checks active."
            ),
        ),
        (
            '<dl id="lp-k-traffic" class="metric"><dt>candidate traffic</dt><dd><strong>25%</strong></dd></dl>',
            '<dl id="lp-k-traffic" class="metric"><dt>target traffic</dt><dd><strong>100%</strong></dd></dl>',
        ),
        (
            '<dl id="lp-k-checks" class="metric"><dt>checks passing</dt><dd><strong>4 of 5</strong></dd></dl>',
            '<dl id="lp-k-checks" class="metric"><dt>checks passing</dt><dd><strong>5 of 5</strong></dd></dl>',
        ),
        (
            '<li id="lp-step-checks"><small class="tag danger">blocked · now</small>',
            '<li id="lp-step-checks"><small class="tag ok">done · 14:25</small>',
        ),
        (
            (
                "<strong>Pass release checks</strong> Finance export has 1,998 of 1,999\n"
                "            expected rows."
            ),
            "<strong>Pass release checks</strong> All five production checks pass.",
        ),
        (
            '<li id="lp-step-promote"><small class="tag">planned</small>',
            '<li id="lp-step-promote"><small class="tag warn">active · now</small>',
        ),
        (
            "Four checks pass. One blocks promotion.",
            "All five checks pass. Promotion is running.",
        ),
        (
            '<span class="release-check-result" data-status="fail">Fail</span>',
            '<span class="release-check-result" data-status="pass">Pass</span>',
        ),
        (
            "<code>1,998</code> / <code>1,999</code> rows",
            "<code>1,999</code> / <code>1,999</code> rows",
        ),
    )
    # The example's line wrapping is layout, not content: match each passage across
    # whatever whitespace the source wraps it with.
    for before, after in revisions:
        pattern = r"\s+".join(map(re.escape, before.split())).replace("><", r">\s*<")
        incorporated, count = re.subn(
            pattern, lambda _, after=after: after, incorporated, count=1
        )
        assert count == 1, before
    stamp = stamp_page(
        serve.page_dir,
        incorporated,
        "Pass finance parity and promote checkout-v2",
    )
    wait_for_revision(page, stamp["version"])
    expect(page.locator("#lp-lede")).to_contain_text("expanding")
    expect(page.locator("#lp-current-state")).to_contain_text("Promoting to 100%")
    expect(page.locator("#lp-k-traffic dd strong")).to_have_text("100%")
    expect(page.locator("#lp-k-checks dd strong")).to_have_text("5 of 5")
    expect(page.locator("#lp-step-checks > small")).to_have_text("done · 14:25")
    expect(page.locator("#lp-step-promote > small")).to_have_text("active · now")
    expect(page.locator("#lp-checks-note")).to_have_text(
        "All five checks pass. Promotion is running."
    )
    expect(page.locator("#lp-check-finance .release-check-result")).to_have_text("Pass")
    expect(log).to_contain_text("14:24:49 observer  checkout remains healthy")
