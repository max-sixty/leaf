"""One native contents route across in-flow and margin presentations."""

import io

import pytest
from PIL import Image
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import leaf_page, open_page, resized, rgb_pixels, told

from leaf.source.render_checks import rendered, wait_until_ready


@pytest.mark.parametrize("initially_open", [False, True])
def test_an_outline_first_paints_with_its_complete_reading_scope(
    browser, serve, initially_open
):
    """Reading proceeds during parsing; the index later includes its complete scope."""
    source = leaf_page(
        "streamed contents",
        f"""<h1 id="page-title">Field guide</h1>
<lf-tabs id="topics"><lf-tab id="topic" label="Preparation">
  <lf-toc id="contents"{" open" if initially_open else ""}></lf-toc>
  <h2 id="first">Take inventory</h2><p>Read the current counts.</p>
  <!--pause-parsing-->
  <h2 id="second">Save a snapshot</h2><p>Keep a reference.</p>
</lf-tab></lf-tabs>""",
    )
    context = browser.new_context(viewport={"width": 390, "height": 844})
    held = []
    context.route("**/parse-pause.js", lambda route: held.append(route))
    url = serve(source)

    def pause_delivery(route):
        # Authored scripts defer until parsing finishes. Interrupt the delivered
        # stream instead, to make a paint between incoming headings deterministic.
        response = route.fetch()
        route.fulfill(
            response=response,
            body=response.text().replace(
                "<!--pause-parsing-->", '<script src="/parse-pause.js"></script>'
            ),
        )

    context.route(url, pause_delivery)
    page = context.new_page()
    try:
        page.goto(url, wait_until="commit")
        page.locator("#first").wait_for(state="attached")
        page.evaluate("() => new Promise(requestAnimationFrame)")
        assert page.evaluate("document.readyState") == "loading"
        expect(page.locator("#page-title")).to_be_visible()
        expect(page.locator("#first")).to_be_visible()
        assert page.locator("#contents li").count() == 0

        held.pop().fulfill(status=200, content_type="text/javascript", body="")
        wait_until_ready(page)
        expect(page.locator("#first")).to_be_visible()
        expect(page.locator("#second")).to_be_visible()
        expect(page.locator("#contents li a")).to_have_text(
            ["Take inventory", "Save a snapshot"]
        )
        if not initially_open:
            expect(page.locator("#contents summary")).to_be_visible()
            page.locator("#contents summary").click()
        expect(page.locator("#contents li a").first).to_be_visible()
    finally:
        for route in held:
            route.abort()


@pytest.mark.parametrize("initially_open", [False, True])
def test_contents_disclosure_keeps_its_links_focus_and_open_state(
    browser, serve, initially_open
):
    source = leaf_page(
        "adaptive contents",
        '<aside><div class="layout-track"><lf-toc id="contents"'
        + (" open" if initially_open else "")
        + '></lf-toc></div></aside><div class="layout-column"><h1>Report</h1>'
        '<section id="evidence"><h2>Evidence</h2><p>Read the counts.</p></section>'
        '<section id="decision"><h2>Decision</h2><p>Choose the next step.</p></section></div>',
        layout="sidebar",
    )
    page = open_page(browser, live_url(serve(source)))
    resized(page, 390, 844)
    toc = page.locator("lf-toc")
    disclosure = toc.locator("details")
    summary = toc.locator("summary")
    expect(summary).to_be_visible()
    if initially_open:
        expect(toc.get_by_role("link", name="Evidence", exact=True)).to_be_visible()
        summary.click()
    expect(disclosure).not_to_have_attribute("open", "")
    expect(toc.get_by_role("link")).to_have_count(0)
    summary.focus()
    page.keyboard.press("Enter")
    link = toc.get_by_role("link", name="Evidence", exact=True)
    expect(link).to_be_visible()
    link.focus()
    (serve.page_dir / "index.html").write_text(
        source.replace("Read the counts.", "Read the revised counts."), encoding="utf-8"
    )
    told(page)
    rendered(page)
    expect(link).to_be_focused()
    expect(disclosure).to_have_attribute("open", "")
    resized(page, 1440, 900)
    expect(summary).to_be_hidden()
    expect(link).to_be_focused()
    resized(page, 390, 844)
    expect(link).to_be_visible()
    expect(link).to_be_focused()
    summary.click()
    resized(page, 1440, 900)
    # Margin exposure is native open state, so every engine exposes the links.
    expect(disclosure).to_have_attribute("open", "")
    expect(toc.get_by_role("link", name="Evidence", exact=True)).to_be_visible()
    first_link = toc.get_by_role("link", name="Report", exact=True)
    first_link.focus()
    expect(first_link).to_be_focused()
    page.keyboard.press("Tab")
    expect(link).to_be_focused()
    resized(page, 390, 844)
    expect(disclosure).to_have_attribute("open", "")
    expect(link).to_be_focused()
    page.emulate_media(media="print")
    expect(toc.get_by_role("link", name="Report", exact=True)).to_be_visible()
    expect(link).to_be_visible()

    page.emulate_media(media="screen")
    rendered(page)
    expect(disclosure).to_have_attribute("open", "")
    summary.click()
    resized(page, 1440, 900)
    expect(disclosure).to_have_attribute("open", "")
    resized(page, 390, 844)
    expect(disclosure).not_to_have_attribute("open", "")
    page.emulate_media(media="print")
    expect(disclosure).to_have_attribute("open", "")
    expect(toc.get_by_role("link")).to_have_count(3)
    page.emulate_media(media="screen")
    expect(disclosure).not_to_have_attribute("open", "")
    expect(toc.get_by_role("link")).to_have_count(0)


def test_a_sidebar_page_track_beside_the_body_stands_its_outline_open(browser, serve):
    """The room a sidebar page gives its track is for navigation. Folded there, the
    outline left a third of the window empty beside a long review; stacked above the
    body, it folds again so the reader reaches the body."""
    sections = "".join(
        f'<section id="s{n}"><h2>Section {n}</h2><p>{"Words. " * 80}</p></section>'
        for n in range(1, 5)
    )
    source = leaf_page(
        "sidebar contents",
        '<header><h1>Review</h1></header><aside id="rail">'
        '<div class="layout-track"><section class="lf-panel">'
        '<lf-toc id="contents"></lf-toc></section></div></aside>'
        f'<div id="body">{sections}</div>',
        layout="sidebar",
    )
    page = open_page(browser, live_url(serve(source)))
    resized(page, 1440, 900)
    toc = page.locator("lf-toc")
    disclosure = toc.locator("details")
    rail = page.locator("#rail").bounding_box()
    body = page.locator("#body").bounding_box()
    assert rail["x"] + rail["width"] <= body["x"], (rail, body)
    expect(toc.locator("summary")).to_be_hidden()
    expect(disclosure).to_have_attribute("open", "")
    expect(toc.get_by_role("link", name="Section 3", exact=True)).to_be_visible()
    resized(page, 700, 900)
    rail = page.locator("#rail").bounding_box()
    body = page.locator("#body").bounding_box()
    assert rail["y"] + rail["height"] <= body["y"], (rail, body)
    assert rail["x"] == pytest.approx(body["x"], abs=1)
    expect(toc.locator("summary")).to_be_visible()
    expect(disclosure).not_to_have_attribute("open", "")


def test_a_spine_sidebar_draws_its_map_only_beside_the_body(browser, serve):
    """Stacked above the body, the contents is the in-flow disclosure, since the map,
    a window tall, would push the body's first words a screen down. Stacked, the aside and
    `.layout-sidebar` are one width, but Chromium computed them a float rounding error
    apart at some widths (a 960px window among them), so the test reads every width in
    a band either side of the wrap."""
    sections = "".join(
        f'<section id="s{n}"><h2>Section {n}</h2><p>{"Words. " * 80}</p></section>'
        for n in range(1, 5)
    )
    source = leaf_page(
        "margin contents",
        '<aside id="rail"><div class="layout-track"><lf-toc id="contents"></lf-toc>'
        f'</div></aside><div class="layout-column" id="body"><h1>Review</h1>{sections}</div>',
        layout="sidebar",
    )
    page = open_page(browser, live_url(serve(source)))
    readings = page.evaluate("""() => {
      const main = document.querySelector('main');
      const rail = document.getElementById('rail'), body = document.getElementById('body');
      const toc = document.getElementById('contents');
      const readings = [];
      for (let width = 760; width <= 960; width++) {
        main.style.inlineSize = `${width}px`;
        readings.push({width,
          stacked: rail.getBoundingClientRect().bottom <= body.getBoundingClientRect().top,
          map: getComputedStyle(toc.querySelector('.lf-toc-markers')).display === 'block'});
      }
      main.style.inlineSize = '';
      return readings;
    }""")
    assert {r["stacked"] for r in readings} == {True, False}
    assert [r["width"] for r in readings if r["map"] == r["stacked"]] == []


SECTIONS = "".join(
    f'<section><h2 id="s{n}">Section {n}</h2><p>{"Words. " * 60}</p></section>'
    for n in range(1, 4)
)
MAP_TRACK = '<div class="layout-track"><lf-toc id="contents"></lf-toc></div>'


@pytest.mark.parametrize(
    ("body", "head", "folded"),
    [
        pytest.param(
            '<aside id="route"><div class="layout-track"><lf-toc id="contents"></lf-toc>'
            '<p id="status">Two branches wait on review before the window opens.</p>'
            f'</div></aside><div class="layout-column" id="body">{SECTIONS}</div>',
            "",
            False,
            id="status-beside-the-map",
        ),
        pytest.param(
            f'<div class="layout-column" id="body">{SECTIONS}</div>'
            f'<aside id="route">{MAP_TRACK}</aside>',
            "",
            False,
            id="aside-after-the-body",
        ),
        pytest.param(
            f'<aside id="route">{MAP_TRACK}</aside><div id="body">{SECTIONS}</div>',
            "<style>main { --lf-aside: 56px; }</style>",
            True,
            id="narrow-sidebar-of-the-page",
        ),
    ],
)
def test_a_sidebar_the_layout_does_not_narrow_keeps_the_map_s_words_shown(
    browser, serve, body, head, folded
):
    """Only a sidebar the Layout narrows to the map's spine lets the map rest as that
    spine and lay its labels over the body. The prose stands centred in the window
    beside an outline column too, whichever side of the body the aside stands on. A document's sidebar keeps a column's room
    for a status beside the map, where the narrowed sidebar would have crushed the
    status to a word a line, and for an aside after the body, where the labels would
    have spread past the window's edge; the outline stands open in that column. A
    narrow sidebar the page asks for keeps its width, too narrow for the outline's
    words, so the map folds into the disclosure there rather than hiding labels its
    track would clip."""
    source = leaf_page("sidebar of a column", body, head=head, layout="sidebar")
    page = open_page(browser, live_url(serve(source)))
    resized(page, 1440, 900)
    toc = page.locator("#contents")
    expect(toc.locator(".lf-toc-rows")).not_to_have_css("display", "flex")
    if folded:
        expect(toc.locator("summary")).to_be_visible()
        return
    assert page.locator("#route").evaluate("node => node.offsetWidth") >= 200
    off_centre = page.evaluate(
        "() => { const box = document.querySelector('#body p').getBoundingClientRect();"
        " return Math.round((box.left + box.right) / 2 - innerWidth / 2); }"
    )
    assert abs(off_centre) <= 1, off_centre
    expect(toc.locator(".lf-toc-heading")).to_be_visible()
    expect(toc.get_by_role("link", name="Section 1", exact=True)).to_have_css(
        "opacity", "1"
    )


@pytest.mark.parametrize("direction", ["ltr", "rtl"])
def test_a_contents_spine_rests_beside_the_prose_and_reveals_its_labels_over_it(
    browser, serve, direction
):
    """The narrowed sidebar stands at the body's inline start in either direction, and
    the prose stands centred in the window, as a column page's does. At
    rest the map lays nothing over the prose, and pointing at its spine shows its labels
    over the page past the spine's track, inside the window. On paper, where nothing
    points at it, the sidebar takes a column's room and the outline reads whole."""
    source = leaf_page(
        "contents spine",
        f'<aside id="route">{MAP_TRACK}</aside><div class="layout-column" id="body">'
        f"<h1>Review</h1>{SECTIONS}</div>",
        layout="sidebar",
    ).replace('<html lang="en">', f'<html lang="en" dir="{direction}">')
    page = open_page(browser, live_url(serve(source)))
    resized(page, 1440, 900)
    geometry = page.evaluate("""() => {
      const box = selector => document.querySelector(selector).getBoundingClientRect();
      const aside = box('#route'), prose = box('#body p'), rows = box('#contents .lf-toc-rows');
      const rtl = getComputedStyle(document.body).direction === 'rtl';
      return {
        forward: rtl ? -1 : 1,
        asideWidth: aside.width,
        asideEnd: rtl ? aside.left : aside.right,
        asideBeforeProse: rtl ? aside.left >= prose.right : aside.right <= prose.left,
        proseStart: rtl ? prose.right : prose.left,
        proseOffCentre: Math.round((prose.left + prose.right) / 2 - innerWidth / 2),
        proseY: prose.top + prose.height / 2,
        spine: rtl ? rows.right : rows.left,
        rowsY: rows.top + rows.height / 2,
      };
    }""")
    forward = geometry["forward"]
    assert forward == (-1 if direction == "rtl" else 1)
    assert geometry["asideWidth"] <= 64, geometry
    assert geometry["asideBeforeProse"], geometry
    assert abs(geometry["proseOffCentre"]) <= 1, geometry
    covered = page.evaluate(
        """([forward, proseStart, y]) => {
          const toc = document.getElementById('contents');
          return Array.from({length: 9}, (_, step) => proseStart + forward * (4 + step * 40))
            .filter(x => toc.contains(document.elementFromPoint(x, y)));
        }""",
        [forward, geometry["proseStart"], geometry["proseY"]],
    )
    assert covered == []
    spine_x = geometry["spine"] + forward * 3
    assert page.evaluate(
        "([x, y]) => document.getElementById('contents')"
        ".contains(document.elementFromPoint(x, y))",
        [spine_x, geometry["rowsY"]],
    )

    page.mouse.move(spine_x, geometry["rowsY"])
    label = page.locator("#contents").get_by_role("link", name="Section 2", exact=True)
    expect(page.locator("#contents .lf-toc-labels")).to_have_css("opacity", "1")
    revealed = label.evaluate(
        """(link, asideEnd) => {
          const box = link.getBoundingClientRect();
          const rtl = getComputedStyle(link).direction === 'rtl';
          return {
            inWindow: box.left >= 0 && box.right <= innerWidth,
            pastTrack: rtl ? box.left < asideEnd : box.right > asideEnd,
            scrollsSideways: document.documentElement.scrollWidth > innerWidth,
          };
        }""",
        geometry["asideEnd"],
    )
    assert revealed == {"inWindow": True, "pastTrack": True, "scrollsSideways": False}

    page.emulate_media(media="print")
    assert page.locator("#route").evaluate("node => node.offsetWidth") >= 200
    expect(page.locator("#contents .lf-toc-start")).to_be_visible()


# Pauses each CSS transition the next gesture starts, in the frame the browser starts
# it, and collects them in `window.heldFades` until `window.stopHolding()`. A
# transition's `transitionrun` event is dispatched in the frame after the style change
# that created it, well inside a fade, and before the third frame after the gesture,
# when FADES_HELD counts them.
HOLD_FADES = """() => {
  window.heldFades = new Set();
  const holding = new AbortController();
  window.stopHolding = () => holding.abort();
  document.addEventListener('transitionrun', () => {
    for (const fade of document.getAnimations()) {
      if (!(fade instanceof CSSTransition) || window.heldFades.has(fade)) continue;
      fade.pause();
      window.heldFades.add(fade);
    }
  }, {capture: true, signal: holding.signal});
}"""
FADES_HELD = """async () => {
  for (let frame = 0; frame < 3; frame++)
    await new Promise(requestAnimationFrame);
  return window.heldFades.size;
}"""


@pytest.mark.parametrize("sections", [3, 80], ids=["map", "long"])
def test_a_contents_spine_fades_its_words_as_one_and_frees_the_prose_at_once(
    browser, serve, sections
):
    """Leaving the revealed map fades all its words at one pace: the part of each word
    over the prose fades with the part in the spine's track. From the first frame of the fade, the prose past
    the track takes the pointer, so a pointer that returns there reaches the page
    rather than reopening the map, while a pointer on the track at rest stands on its
    row's link, so the link's hover and preview need no further move. Mid-fade, a label
    past the track still shows."""
    body = "".join(
        f'<section><h2 id="s{n}">Section {n}</h2><p>{"Words. " * 20}</p>'
        f'<h3 id="s{n}-detail">Detail {n}</h3><p>{"Words. " * 20}</p></section>'
        for n in range(1, sections + 1)
    )
    source = leaf_page(
        "contents spine fade",
        f'<aside id="route">{MAP_TRACK}</aside><div class="layout-column" id="body">'
        f"<h1>Review</h1>{body}</div>",
        layout="sidebar",
    )
    page = open_page(browser, live_url(serve(source)))
    resized(page, 1440, 900)
    toc = page.locator("#contents")
    if sections > 3:
        expect(
            toc.locator(".lf-toc-labels a:not([data-lf-toc-shown])").first
        ).to_be_attached()
    track = toc.bounding_box()
    y = track["y"] + 200
    page.mouse.move(track["x"] + 3, y)
    expect(toc.locator(".lf-toc-labels")).to_have_css("opacity", "1")
    # The browser holds each transition the gesture starts as it starts, so a driver
    # that pauses between the gesture and its next call can't let the fade finish
    # before it is read at its start, midway and its end.
    page.evaluate(HOLD_FADES)
    page.mouse.move(track["x"] + 900, y)
    assert page.evaluate(FADES_HELD) > 0, "leaving the map started no transition"
    frames = page.evaluate(
        """([x, y]) => {
          window.stopHolding();
          const toc = document.getElementById('contents');
          const words = [...toc.querySelectorAll('.lf-toc-link')]
            .filter(node => node.checkVisibility({visibilityProperty: true}));
          return [0, 120, 240].map(time => {
            for (const fade of window.heldFades) fade.currentTime = time;
            // What the reader sees of a word is its opacity times its ancestors'.
            const opacities = words.map(node => {
              let seen = 1;
              for (let at = node; at && at !== toc; at = at.parentElement)
                seen *= Number(getComputedStyle(at).opacity);
              return seen;
            });
            return {
              time,
              least: Math.min(...opacities),
              most: Math.max(...opacities),
              mapTakesProse: toc.contains(document.elementFromPoint(x, y)),
            };
          });
        }""",
        [track["x"] + track["width"] + 150, y],
    )
    start, middle, end = frames
    assert start["most"] == 1 and 0 < middle["most"] < 1 and end["most"] == 0, frames
    wrong = [f for f in frames if f["most"] > f["least"] or f["mapTakesProse"]]
    assert wrong == [], frames
    page.evaluate("window.heldFades.forEach(fade => fade.finish())")
    in_track = page.evaluate(
        """trackEnd => {
          const nav = document.querySelector('#contents .lf-toc-nav');
          const shown = nav.getBoundingClientRect();
          return [...nav.querySelectorAll('li .lf-toc-link')].flatMap(link => {
            const box = link.getBoundingClientRect();
            if (!link.checkVisibility({visibilityProperty: true}) || box.left >= trackEnd - 4
              || box.top < shown.top || box.bottom > shown.bottom)
              return [];
            const y = box.top + Math.min(box.height, 16) / 2;
            const hit = document.elementFromPoint(trackEnd - 4, y);
            return [{depth: link.parentElement.dataset.lfDepth, lands: hit === link}];
          });
        }""",
        track["x"] + track["width"],
    )
    # A long route leaves its subsections off the map.
    depths = {"0", "1"} if sections == 3 else {"0"}
    assert {row["depth"] for row in in_track} == depths, in_track
    assert all(row["lands"] for row in in_track), in_track

    page.mouse.move(track["x"] + 3, y)
    expect(toc.locator(".lf-toc-labels")).to_have_css("opacity", "1")
    page.evaluate(HOLD_FADES)
    page.mouse.move(track["x"] + 900, y)
    assert page.evaluate(FADES_HELD) > 0, "leaving the map started no transition"
    label = page.evaluate(
        """trackEnd => {
          window.stopHolding();
          for (const fade of window.heldFades) fade.currentTime = 100;
          const range = document.createRange();
          range.selectNodeContents(document.querySelector('#contents li .lf-toc-link'));
          const text = range.getClientRects()[0];
          const start = Math.max(text.left, trackEnd + 2);
          return {x: start, y: text.top, width: text.right - start, height: text.height};
        }""",
        track["x"] + track["width"],
    )
    assert label["width"] > 10, label
    past_track = Image.open(io.BytesIO(page.screenshot(clip=label))).convert("RGB")
    assert len(set(rgb_pixels(past_track))) > 1, label


def test_the_revealed_contents_spine_covers_every_box_the_body_paints(browser, serve):
    """On a window narrow enough that the prose stands just past the spine, the revealed
    map lies over the body's start edge and covers every box the body paints there: a
    table, which the theme makes a positioned scroll box, bullets the page draws in
    positioned boxes, and a box the page lifts with its own z-index. The narrowed
    sidebar's Layout paints its aside over the body for this (layouts.css)."""
    source = leaf_page(
        "contents spine over positioned boxes",
        '<aside id="route"><div class="layout-track"><lf-toc id="contents"></lf-toc>'
        '</div></aside><div class="layout-column" id="body"><h1>Review</h1>'
        '<section id="s1"><h2>Steps</h2><ul class="steps" id="steps">'
        "<li>Drain the queue</li><li>Rotate the key</li></ul></section>"
        '<section id="s2"><h2>Owners</h2><table id="owners"><tr><th>Step</th>'
        "<th>Owner</th></tr><tr><td>Drain</td><td>Payments</td></tr></table></section>"
        '<section id="s3"><h2>Notes</h2><p id="lifted">Check the replicas.</p>'
        f"<p>{'Words. ' * 400}</p></section></div>",
        head="<style>.steps li { position: relative; list-style: none; }"
        ' .steps li::before { content: ""; position: absolute; inset: 0.6em auto auto'
        " -1em; width: 0.4em; height: 0.4em; border-radius: 50%; background: currentColor; }"
        " #lifted { position: relative; z-index: 3; }</style>",
        layout="sidebar",
    )
    page = open_page(browser, live_url(serve(source)))
    resized(page, 960, 900)
    rows = page.locator("#contents .lf-toc-rows").bounding_box()
    page.mouse.move(rows["x"] + 2, rows["y"] + rows["height"] / 2)
    expect(page.locator("#contents .lf-toc-labels")).to_have_css("opacity", "1")
    uncovered = page.evaluate("""() => {
      const toc = document.getElementById('contents');
      const nav = toc.querySelector('.lf-toc-nav').getBoundingClientRect();
      return ['#steps li', '#owners td', '#lifted'].flatMap(selector => {
        const box = document.querySelector(selector).getBoundingClientRect();
        const x = box.left + 4, y = box.top + box.height / 2;
        if (x > nav.right || y > nav.bottom) return [`${selector} lies outside the map`];
        return toc.contains(document.elementFromPoint(x, y)) ? [] : [selector];
      });
    }""")
    assert uncovered == []
