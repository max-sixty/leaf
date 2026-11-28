"""Go-to addresses: the `g` sequence's generated hints, the Page Map's destinations, and
the links and new tabs they open."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import PANEL_PAGE, live_url, panel_comment
from render_cases_navigation import (
    ADDRESSED_PAGE,
    BINDING_BADGE_PAGE,
    CHIPS,
    CONTROL_LABEL_PAGE,
    CROWDED_PAGE,
    FOOTED_PAGE,
    ROUTE_CHIPS,
    address_code,
    address_codes,
    go_to_address,
)
from render_harness import (
    LONG_PAGE,
    RELEASE_FOCUS,
    held_frames,
    leaf_page,
    open_page,
    resized,
    scroll_settled,
    shown,
    told,
)

from browser.navigation import expect_walk_position
from browser.threads import open_panel_thread
from leaf.source.render_checks import one_frame, rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_render_of_an_external_links_words_keeps_its_mark(browser, serve):
    """The mark after a link that leaves the page survives a render of its words and a
    revision that leaves the link as written."""
    source = leaf_page(
        "kept link",
        '<h1 id="t">Links</h1><p id="holder">Read <a id="ext" '
        'href="https://example.com/source">the source</a> first.</p>'
        '<p id="other">Other words.</p>',
    )
    page = open_page(browser, live_url(serve(source)))
    link = page.locator("#ext")
    expect(link).to_have_attribute("data-lf-external", "")
    expect(page.locator("#ext ~ *")).to_have_count(0)
    page.evaluate(
        """async () => {
          const { setChildren } = await window.__lfWidgetApi();
          const link = document.getElementById('ext');
          setChildren(link, [document.createTextNode('the source')]);
        }"""
    )
    rendered(page)
    expect(link).to_have_attribute("data-lf-external", "")

    # A source revision compares authored hrefs, not the marker prepaint lent the
    # first document. An unrelated edit leaves the same link and its mark.
    page.evaluate("window.keptLink = document.getElementById('ext')")
    (serve.page_dir / "index.html").write_text(
        source.replace("Other words.", "Revised other words.")
    )
    told(page)
    expect(page.locator("#other")).to_have_text("Revised other words.")
    assert page.evaluate("window.keptLink === document.getElementById('ext')")
    expect(link).to_have_attribute("data-lf-external", "")


def test_a_stage_built_before_its_host_arrives_holds_its_links_and_bounds(
    browser, serve
):
    """A widget may fill its shadow stage while its host is still detached. What stands
    in the stage arrives with the host: its external link is marked, and its bounded
    block is the reading region scrolling its lines and opens at its end."""
    page = open_page(
        browser, serve(leaf_page("staged", '<h1 id="t">Staged</h1><p>Before.</p>'))
    )
    held = page.evaluate(
        """async () => {
          const { shadowStage } = await window.__lfWidgetApi();
          const { scrollerFor } = await window.__lfWidgetApi();
          const host = document.createElement('div');
          const link = Object.assign(document.createElement('a'), {
            href: 'https://example.com/staged', textContent: 'staged source'});
          const log = document.createElement('div');
          log.setAttribute('data-lf-bound', 'end');
          log.style.cssText = 'max-block-size: 120px; overflow: auto';
          for (let n = 0; n < 40; n++)
            log.append(Object.assign(document.createElement('p'),
              {textContent: `Line ${n}`}));
          shadowStage(host, [link, log]);
          document.querySelector('main').append(host);
          await new Promise(requestAnimationFrame);
          await new Promise(requestAnimationFrame);
          return {
            marked: link.hasAttribute('data-lf-external'),
            scroller: scrollerFor(log.querySelector('p')) === log,
            atEnd: log.scrollHeight - log.scrollTop - log.clientHeight <= 2,
          };
        }"""
    )
    assert held == {"marked": True, "scroller": True, "atEnd": True}


def test_a_link_hint_leaves_a_newer_gesture_where_it_is(browser, serve):
    """A link hint's navigation step may wait on what holds its destination. A press made
    meanwhile is the user's newer word: neither the landing nor the hint's focus
    takes them back from it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "held link",
                """
<h1>Held link</h1>
<p><a id="internal" href="#arrival">Read the conclusion</a>.</p>
<p><button id="elsewhere" type="button">Elsewhere</button></p>
<div style="height: 1600px"></div>
<section id="holder"><h2 id="arrival">Conclusion</h2></section>
""",
            )
        ),
    )
    # Revealing the holder waits for its update, which the test holds.
    page.evaluate(
        """() => {
          const holder = document.getElementById('holder');
          holder.hidden = 'until-found';
          holder.addEventListener('beforematch', () => {
            holder.updateComplete = new Promise((r) => (window.__release = r));
          });
        }"""
    )
    go_to_address(page, "Link", "internal")
    page.wait_for_url(re.compile(r"#arrival$"))
    page.wait_for_function("() => typeof window.__release === 'function'")
    expect(page.locator("#arrival")).not_to_be_in_viewport()
    page.locator("#elsewhere").click()
    page.evaluate("() => window.__release()")
    one_frame(page)
    one_frame(page)
    expect(page.locator("#elsewhere")).to_be_focused()
    expect(page.locator("#arrival")).not_to_be_in_viewport()


def test_generated_hints_include_links_revealed_by_a_page_widget(browser, serve):
    """A visible page route stays addressable when its widget generated the anchors.

    A contents spine is page navigation even though its links are generated chrome.
    Arming the sequence reveals those labels, gives every visible row a hint, and
    following one lands at the heading through the ordinary link route.
    """
    page = open_page(
        browser,
        serve(
            leaf_page(
                "generated page links",
                """
<aside><div class="layout-track"><lf-toc id="contents"></lf-toc></div></aside>
<div class="layout-column"><h1>Migration plan</h1>
<section><h2>Prepare</h2><p>Take a snapshot.</p></section>
<div style="height: 700px"></div>
<section><h2 id="move">Move</h2><p>Shift one cohort at a time.</p></section>
<div style="height: 700px"></div>
<section><h2 id="verify">Verify</h2><p>Compare the totals.</p></section></div>
""",
                layout="sidebar",
            )
        ),
    )
    resized(page, 1400, 900)
    nav = page.get_by_role("navigation", name="On this page")
    links = nav.get_by_role("link")
    expect(links).to_have_count(4)
    expect(nav.locator(".lf-toc-labels")).to_have_css("opacity", "0")

    page.keyboard.press("g")
    chips = page.locator(f'{CHIPS}[data-lf-go-to-kind="Link"]')
    expect(chips).to_have_count(4)
    first_code = chips.first.get_attribute("data-lf-hint-code")
    assert first_code
    page.keyboard.press("Tab")
    expect(page.locator(".lf-live")).to_have_text(
        f"Hint {first_code}: Link, Migration plan. Enter go to target"
    )
    prepare_link = links.nth(1)
    prepare_href = prepare_link.get_attribute("href")
    assert prepare_href
    code = chips.nth(1).get_attribute("data-lf-hint-code")
    assert code
    page.keyboard.type(code)
    page.wait_for_url(re.compile(rf"{re.escape(prepare_href)}$"))
    expect(page.get_by_role("heading", name="Prepare", exact=True)).to_be_focused()


def test_generated_hints_fit_the_visible_screen(browser, serve):
    """Every opaque route's chip fits at viewport edges, including one cut by the
    window's top. A link showing one pixel at the foot, where the panel's band leaves
    its chip no seat beside it, has its chip withheld rather than stood above the
    panel, and its code still takes it (readings/key-badges/hints.js, `seatHints`)."""
    page = open_page(
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
  <a id="at-top" href="#top">At the top</a>
  <a id="over-top" href="#top">Over the top</a>
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
  #at-top { left: 45vw; top: 1px; }
  #over-top { left: 60vw; top: -8px; }
  #crowded-left { left: 1px; top: 400px; }
  #crowded-neighbor { left: 80px; top: 400px; }
</style>""",
            )
        ),
    )
    over_top = page.locator("#over-top")
    over_top.evaluate(
        """link => {
          link.style.top = '-18px';
          link.addEventListener('click', () => { link.dataset.activated = 'true'; });
        }"""
    )
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()
    reading = page.evaluate(
        """() => ({
          width: document.documentElement.clientWidth,
          height: document.documentElement.clientHeight,
          chips: [...document.querySelectorAll(
            '.lf-go-to-hints .lf-go-to-hint[data-lf-hint-code][data-lf-go-to-kind="Link"]')]
            .map(chip => ({
            route: chip.textContent,
            code: chip.dataset.lfHintCode,
            target: chip.dataset.lfGoToTarget,
            shown: chip.checkVisibility({visibilityProperty: true}),
            ...chip.getBoundingClientRect().toJSON(),
          })),
        })"""
    )
    assert len(reading["chips"]) == 7, reading
    assert [chip["target"] for chip in reading["chips"] if not chip["shown"]] == [
        "bottom"
    ], reading
    for chip in reading["chips"]:
        if not chip["shown"]:
            continue
        assert 0 <= chip["left"] < chip["right"] <= reading["width"], reading
        assert 0 <= chip["top"] < chip["bottom"] <= reading["height"], reading
        assert chip["route"] == chip["code"], chip
    under_code = address_code(page, "Link", "over-top")
    under_index = page.locator(CHIPS).evaluate_all(
        """(chips, code) => chips.findIndex(chip => chip.dataset.lfHintCode === code)""",
        under_code,
    )
    for _ in range(under_index + 1):
        page.keyboard.press("Tab")
    expect(page.locator(".lf-live")).to_have_text(
        f"Hint {under_code}: Link, Over the top. Enter go to target"
    )
    page.keyboard.press("Enter")
    expect(over_top).to_have_attribute("data-activated", "true")
    expect(page.locator("#top")).to_be_focused()

    page.keyboard.press("g")
    code = address_code(page, "Link", "crowded-neighbor")
    page.keyboard.type(code)
    expect(page.locator(CHIPS)).to_have_count(0)
    expect(page.locator("#top")).to_be_focused()

    bottom = page.locator("#bottom")
    bottom.evaluate(
        "link => link.addEventListener('click', () => { link.dataset.activated = 'true'; })"
    )
    page.keyboard.press("g")
    page.keyboard.type(address_code(page, "Link", "bottom"))
    expect(bottom).to_have_attribute("data-activated", "true")


def test_a_transient_notice_does_not_move_generated_address_hints(browser, serve):
    """Generated hints reserve stable status, not a transient notice's footprint."""
    page = open_page(browser, serve(ADDRESSED_PAGE))
    # Wide enough that the panel, centred at the window's foot, ends short of the corner
    # the link is fixed in.
    resized(page, 1920, 800)
    page.evaluate("() => document.scrollingElement.scrollTo(0, 0)")
    page.locator("#lk2").evaluate(
        "node => Object.assign(node.style, {position: 'fixed', right: '18px', bottom: '18px'})"
    )

    page.keyboard.press("g")
    fixed_link_selector = (
        f'{CHIPS}[data-lf-go-to-kind="Link"][data-lf-go-to-target="lk2"]'
    )
    fixed_link_hint = page.locator(fixed_link_selector)
    expect(fixed_link_hint).to_be_visible()
    quiet_top = page.evaluate(
        "selector => document.querySelector(selector).getBoundingClientRect().top",
        fixed_link_selector,
    )
    page.keyboard.press("Escape")
    expect(fixed_link_hint).to_have_count(0)

    # The paint that can read a notice is the one taken while it shows, and only a
    # notice wide enough to reach under the hint could move it.
    page.evaluate("async () => (await window.__lfCheckApi()).notice('Moved to Done.')")
    expect(page.locator(".lf-fp-field leaf-text")).to_have_attribute(
        "data-lf-says", "notice"
    )
    page.keyboard.press("g")
    expect(fixed_link_hint).to_be_visible()
    assert (
        page.evaluate(
            "selector => document.querySelector(selector).getBoundingClientRect().top",
            fixed_link_selector,
        )
        == quiet_top
    )
    expect(page.locator(".lf-fp-field leaf-text")).to_have_attribute(
        "data-lf-says", "notice"
    )


def test_adjacent_footnote_markers_keep_their_codes_without_chips(browser, serve):
    """Adjacent footnote markers are narrower than a key, so no chip beside one could say
    which it names: each is withheld, while the page's other links keep theirs and each
    marker's code still takes it."""
    page = open_page(browser, serve(CROWDED_PAGE))
    resized(page, 1280, 800)
    page.keyboard.press("g")
    expect(page.locator(ROUTE_CHIPS)).to_have_count(5)

    shown = address_codes(page, ROUTE_CHIPS)
    markers = {address_code(page, "Link", f"fn{n}") for n in (1, 2, 3)}
    assert len(shown) == 2, shown
    assert not markers & set(shown), (markers, shown)
    page.keyboard.type(address_code(page, "Link", "fn1"))
    page.wait_for_url(re.compile(r"#s1$"))


@pytest.mark.parametrize(
    "drawing",
    [
        '<svg id="drawing" width="400" height="120"><foreignObject x="80" y="40" '
        'width="200" height="40"><div xmlns="http://www.w3.org/1999/xhtml">'
        '<a id="run" href="#top">$ wt merge</a></div></foreignObject></svg>',
        # Drawn at twice its viewBox, the link in the far half of its foreignObject.
        '<svg id="drawing" width="400" height="120" viewBox="0 0 200 60">'
        '<foreignObject x="40" y="20" width="100" height="20"><div '
        'xmlns="http://www.w3.org/1999/xhtml" style="padding-left: 60px; font-size: 8px">'
        '<a id="run" href="#top">merge</a></div></foreignObject></svg>',
    ],
    ids=["drawn", "scaled"],
)
def test_a_chip_stands_beside_a_link_in_an_svg_drawing_s_html(browser, serve, drawing):
    """Chromium resolves no anchor to an element inside a foreignObject, so the chip
    anchored to a link there stood off the window while its code still followed it. A
    drawing scaled by its viewBox draws its HTML at that scale, and the foreignObject
    shows all of it there (dom/geometry.js, `drawnViewport`), so a link in the far half of
    one still has its chip."""
    page = open_page(
        browser,
        serve(
            leaf_page("Drawn terminal", f'<h1 id="top">Drawn terminal</h1>{drawing}')
        ),
    )
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()
    rendered(page)
    chips = page.evaluate(
        """(selector) => {
          const run = document.getElementById('run').getBoundingClientRect();
          return [...document.querySelectorAll(selector)].map((chip) => {
            const r = chip.getBoundingClientRect();
            const gap = Math.hypot(
              Math.max(run.left - r.right, r.left - run.right, 0),
              Math.max(run.top - r.bottom, r.top - run.bottom, 0));
            return [chip.dataset.lfGoToKind, chip.dataset.lfGoToTarget, Math.round(gap)];
          });
        }""",
        CHIPS,
    )
    assert any(gap == 0 for *_, gap in chips), chips


def test_narrowing_the_map_leaves_every_kept_chip_where_it_stood(browser, serve):
    """A kind filter and a typed letter only hide the chips they rule out. Reseated
    alone, a filtered column of folds stood on its rows' corners, half over the links
    between them, and a typed letter swapped its rows' chips between columns."""
    rows = "".join(
        f'<li><a href="#top">link {at}</a></li>'
        if at % 2 == 0
        else f"<li><details><summary>fold {at}</summary>more</details></li>"
        for at in range(24)
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Dense rows",
                '<h1 id="top">Dense rows</h1><ul id="rows">' + rows + "</ul>",
                head="<style>#rows{list-style:none;padding:0;margin:0}"
                "#rows li,#rows a,#rows details,#rows summary{all:unset;display:block;"
                "font:12px/14px monospace}</style>",
            )
        ),
    )
    resized(page, 1280, 800)
    page.keyboard.press("g")
    expect(page.locator(ROUTE_CHIPS)).to_have_count(24)
    rendered(page)
    seats = """(selector) => Object.fromEntries([...document.querySelectorAll(selector)]
      .filter((chip) => chip.checkVisibility({visibilityProperty: true}))
      .map((chip) => {
        const r = chip.getBoundingClientRect();
        return [chip.dataset.lfHintCode, [r.left, r.top]];
      }))"""
    whole = page.evaluate(seats, ROUTE_CHIPS)
    assert len(whole) == 24, whole

    letter = next(code for code in whole if len(code) == 2)[0]
    page.keyboard.press(letter)
    rendered(page)
    typed = page.evaluate(seats, ROUTE_CHIPS)
    assert typed and all(code.startswith(letter) for code in typed), typed
    assert {code: whole[code] for code in typed} == typed

    page.keyboard.press("Escape")
    page.keyboard.press("f")
    rendered(page)
    folds = page.evaluate(seats, ROUTE_CHIPS)
    assert len(folds) == 12, folds
    assert {code: whole[code] for code in folds} == folds


def test_generated_hints_follow_the_page_while_it_moves(browser, serve):
    """A map that blanked while the page moved would take the codes off the screen the
    user is reading them from, though every one of them still works: membership is
    frozen for the length of the scroll either way, so nothing is gained by hiding it.
    The chips ride with the things they name instead, in both maps, dropping out one by
    one as their members leave the screen."""
    links = "".join(
        f'<p><a id="lk{i}" href="#top">Link number {i} on a dense page</a></p>'
        for i in range(120)
    )
    page = open_page(
        browser,
        serve(leaf_page("dense links", f'<h1 id="top">Dense</h1>{links}')),
    )
    resized(page, 1280, 900)
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()
    # The chips show only once the map is drawn at rest, and `rendered` waits for every
    # repaint that arming it queued, so the map stands still before the page moves. A
    # map armed into a page already moving is a different case, held by
    # tests/runtime/hint-session.test.mjs.
    rendered(page)

    # A smooth scroll is the case that holds the session in motion: a programmatic step
    # ends in its own frame, and Chrome sends `scrollend` for each one.
    travel = page.evaluate(
        """async () => {
          const sel = '.lf-go-to-hints .lf-go-to-hint[data-lf-hint-code]';
          // A chip whose target sits well inside the room, so neither reading is held
          // against the window's head at one end or the panel at the other.
          const code = [...document.querySelectorAll(sel)]
            .map(chip => chip.dataset.lfGoToTarget)
            .find(id => {
              const top = document.querySelector('#' + id).getBoundingClientRect().top;
              return top > 300 && top < 500;
            });
          const chipTop = () => {
            const chip = document.querySelector(
              `.lf-go-to-hint[data-lf-go-to-target="${code}"]`);
            return chip ? chip.getBoundingClientRect().top : null;
          };
          const targetTop = () =>
            document.querySelector('#' + code).getBoundingClientRect().top;
          const before = {chip: chipTop(), target: targetTop()};
          const moving = [];
          // Keep this target above the viewport's top clamp throughout the sweep.
          document.scrollingElement.scrollTo({top: 180, behavior: 'smooth'});
          for (let frame = 0; frame < 8; frame++) {
            // After the frame's own callbacks, not inside one: a reading taken from a
            // callback registered a frame earlier is queued ahead of the runtime's
            // repaint, and reads the chip where the last frame put it against a target
            // already at this frame's offset — one frame's travel of pure measurement.
            await new Promise(painted =>
              requestAnimationFrame(() => setTimeout(painted, 0)));
            if (frame >= 3)
              moving.push({
                chips: document.querySelectorAll(sel).length,
                gap: chipTop() === null ? null : targetTop() - chipTop(),
                scroll: document.scrollingElement.scrollTop,
              });
          }
          return {before, moving};
        }"""
    )

    assert travel["before"]["chip"] is not None, travel
    blank = [seen for seen in travel["moving"] if not seen["chips"]]
    assert not blank, f"the map blanked while the page was still moving: {travel}"
    # The chip keeps the offset it had at rest, to the pixel, every frame of the way.
    resting = travel["before"]["target"] - travel["before"]["chip"]
    assert all(abs(seen["gap"] - resting) < 2 for seen in travel["moving"]), (
        f"a chip came off the target it names while the page moved: {travel}"
    )


def test_a_map_armed_as_a_walk_lands_names_what_the_landed_page_shows(browser, serve):
    """`g` pressed while a `t` walk glides lands the glide and names what the page shows
    where the walk left it, as `g` pressed after the walk does. There the thread card the
    walk opened covers the thread's margin entry, so the entry gets no hint. Read in the
    task that landed the glide, the card still stood where the glide had carried it, a
    frame behind the scroll, and the map named the entry, which Tab then walked to first;
    read again as that scroll ended, before the frame that moved the card, it named it
    again (dom/arrivals.js, `scrollDrawn`)."""
    source = LONG_PAGE.replace(
        "<p id='p20'>Paragraph 20.", "<p id='p20'>Paragraph 20. <a href='#p20'>Mid</a>"
    ).replace(
        "<p id='p42'>Paragraph 42.",
        "<p id='p42'>Paragraph 42. <a id='near' href='#p42'>Near</a>",
    )
    url = serve(source, anchored=[("p41", "Paragraph 41.")])

    def hints(during):
        page = open_page(browser, url)
        resized(page, 1440, 900)
        page.locator("#p20 a").focus()
        scroll_settled(page)
        rendered(page)
        start = page.evaluate("scrollY")
        if during:
            with held_frames(page) as step:
                page.keyboard.press("t")
                for _ in range(30):
                    if page.evaluate("scrollY") != start:
                        break
                    step()
                else:
                    raise AssertionError("the walk's glide never set off")
                step()
                page.keyboard.press("g")
        else:
            page.keyboard.press("t")
            scroll_settled(page)
            rendered(page)
            page.keyboard.press("g")
        scroll_settled(page)
        rendered(page)
        expect(page.locator(CHIPS).first).to_be_visible()
        return page.evaluate(
            """sel => [...document.querySelectorAll(sel)]
              .map(chip => `${chip.dataset.lfGoToKind} ${chip.dataset.lfGoToTarget}`)
              .sort()""",
            CHIPS,
        )

    after = hints(during=False)
    assert "Link near" in after, after
    assert hints(during=True) == after


def test_a_page_target_s_hint_is_never_drawn_on_the_panel(browser, serve):
    """The panel stays clear of the chips naming the page's links while they follow a
    scroll; only the panel's own controls wear chips on it."""
    page = open_page(browser, serve(FOOTED_PAGE))
    resized(page, 900, 700)
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()

    # Swept rather than asked once: what puts a member under the panel is a scroll
    # position with a link resting on the bottom edge. Each step waits for the runtime's
    # own paint frame, since the chips follow a scroll on a frame of their own and boxes
    # read in the same turn are the positions it just left.
    room = page.evaluate(
        "() => document.scrollingElement.scrollHeight"
        " - document.scrollingElement.clientHeight"
    )
    fouled = []
    for i in range(21):
        page.evaluate(
            "top => document.scrollingElement.scrollTo(0, top)", round(room * i / 20)
        )
        rendered(page)
        fouled += page.evaluate(
            """() => {
                 const bar = document.querySelector('.lf-floating-panel')
                   .getBoundingClientRect();
                 const hit = (a, b) => a.left < b.right && b.left < a.right
                                    && a.top < b.bottom && b.top < a.bottom;
                 return [...document.querySelectorAll(
                   '.lf-go-to-hints .lf-go-to-hint[data-lf-hint-code][data-lf-go-to-kind="Link"]')]
                   .filter(chip => hit(chip.getBoundingClientRect(), bar))
                   .map(chip => chip.textContent + ' at '
                     + Math.round(document.scrollingElement.scrollTop));
               }"""
        )
    assert fouled == [], f"hints are drawn over the panel: {fouled}"


def test_the_g_chord_opens_an_empty_page_map(browser, serve):
    """A destination with no locations still shows that the command worked."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Empty Page Map", "<h1>Empty Page Map</h1><p>No activity yet.</p>"
            )
        ),
    )

    expect(page.locator(".lf-page-map-action")).to_have_count(0)
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")

    sheet = page.locator(".lf-page-map-dialog")
    expect(sheet).to_be_visible()
    expect(
        sheet.get_by_role(
            "searchbox", name="Find an action, status or location in Page Map"
        )
    ).to_be_focused()
    # The one close control every surface wears: the cross, named for what it closes,
    # its drawn ✕ ending where the header does, on the edge the sheet's words share.
    header = sheet.locator(".lf-dialog-head")
    close = header.get_by_role("button", name="Close Page Map", exact=True)
    cross = close.locator('svg[data-lf-icon="cross"]')
    expect(cross).to_have_count(1)
    header_box = header.bounding_box()
    assert header_box
    ink_end = cross.evaluate("""svg => {
      const box = svg.getBBox(), at = svg.getScreenCTM();
      return at.a * (box.x + box.width + parseFloat(getComputedStyle(svg).strokeWidth) / 2) + at.e;
    }""")
    assert ink_end == pytest.approx(header_box["x"] + header_box["width"], abs=1), (
        header_box,
        ink_end,
    )
    expect(sheet).to_contain_text(
        "No margin controls, status indicators or locations yet"
    )
    expect(sheet.locator(".lf-page-map-action")).to_have_count(0)


def test_an_armed_go_to_is_named_beside_the_way_out_that_closes_it_from_any_step(
    browser, serve
):
    """While Go-to waits for a key, the panel's row names it beside its ✕, chips or
    none, where the field says what Go-to found, and the ✕ takes the map off from any
    step, a filter typed or none. The field's end says Close and esc while Escape would
    take the map off, and nothing while it would take back a typed letter first."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Links", '<h1>Links</h1><p><a id="one" href="#one">One link</a></p>'
            )
        ),
    )
    field = page.locator(".lf-fp-field leaf-text")
    name = page.locator(".lf-fp-mode")
    leave = page.locator('.lf-fp-row > .lf-fp-exit[aria-label="Close Go to"]')
    page.locator("body").focus()
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()
    expect(name).to_have_text("Go to")
    expect(leave).to_be_visible()
    expect(field).to_have_attribute("placeholder", re.compile(r" · Close esc$"))
    expect(field).not_to_have_attribute("placeholder", re.compile("Go-to"))
    # A filter that keeps the link's chip.
    page.keyboard.press("h")
    expect(page.locator(f"{CHIPS}:visible")).to_have_count(1)
    expect(name).to_have_text("Go to")
    expect(field).not_to_have_attribute("placeholder", re.compile("Close"))
    page.keyboard.press("Escape")
    expect(field).to_have_attribute("placeholder", re.compile(r" · Close esc$"))
    page.keyboard.press("t")
    expect(field).to_have_attribute("placeholder", "No visible threads")
    leave.click()
    expect(page.locator("body")).not_to_have_attribute("data-lf-go-to-active", "")
    expect(page.locator(".lf-live")).to_have_text("Go to cancelled")
    expect(name).to_be_hidden()
    expect(leave).to_have_count(0)


def test_the_g_chord_selects_a_visible_tab_hint(browser, serve):
    """A tab can be selected from elsewhere on the page through its generated hint.

    Arrow keys serve a user already focused in the tab strip. The page-level route
    names every visible tab, then selects and focuses the requested one so its
    local keyboard pattern is immediately available."""
    page = open_page(browser, serve(CONTROL_LABEL_PAGE))
    tabs = page.locator("#projects .lf-tab-btn")
    expect(tabs).to_have_count(2)
    expect(tabs.first).to_have_attribute("aria-selected", "true")

    # Tabs need no separate kind mnemonic to remain directly reachable: the complete
    # generated map keeps their activation and focus behavior.
    page.keyboard.press("g")
    expect(page.locator(f'{CHIPS}[data-lf-go-to-kind="Tab"]')).to_have_count(2)
    page.keyboard.type(address_code(page, "Tab", "lf-tab-tab-bath"))

    expect(tabs.nth(1)).to_have_attribute("aria-selected", "true")
    expect(tabs.nth(1)).to_be_focused()
    expect(page.locator("#tab-bath")).not_to_have_attribute("hidden", re.compile(".*"))
    expect(page.locator("#tab-feeders")).to_have_attribute("hidden", re.compile(".*"))
    page.keyboard.press("ArrowLeft")
    expect(tabs.first).to_be_focused()
    # Both tabs stand in view around the ring, so the step declares no position.
    expect_walk_position(page, None)


def test_go_to_names_leaf_s_own_controls_but_not_its_own_way_out(browser, serve):
    """Go-to's map holds the controls Leaf draws over the page as it holds the page's
    own: with Threads open, the floating panel's tabs and the leaf wear chips, though
    Go-to arms as the Threads view fades in. A tab a Go-to key already opens wears that
    key, as On Me wears M, and a tab no key opens, as Menu, wears a code that presses
    it. Each tab's chip stands on the tab's words rather than on its box's corner, in
    the padding it shares with the tab before it. The ✕ and the field's Close that end
    Go-to wear none, since each would only do what Escape does
    (panel/floating-panel.js, `heldByStance`)."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Own controls",
                '<h1 id="top">Own controls</h1><p><a id="one" href="#top">One</a></p>',
            )
        ),
    )
    panel = page.locator(".lf-floating-panel")
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    expect(panel).to_have_attribute("data-lf-open", "threads")
    page.keyboard.press("g")
    chips = page.locator(CHIPS)
    expect(chips.first).to_be_visible()
    expect(page.locator(".lf-fp-row > .lf-fp-exit")).to_have_accessible_name(
        "Close Go to"
    )
    routes = heard_routes(page)
    assert {"Link, One", "Control, Menu", "Control, On Me", "Control, Threads"} <= set(
        routes
    ), routes
    assert any(route.startswith("Control, Page menu") for route in routes), routes
    assert not [route for route in routes if "Go to" in route or "esc" in route], routes
    for name in ("Menu", "On Me", "Threads"):
        tab = page.locator(".lf-fp-tab", has_text=name).bounding_box()
        chip = page.locator(
            f'{CHIPS}[data-lf-hint-code="{routes[f"Control, {name}"]}"]'
        ).bounding_box()
        assert tab and chip, name
        middle = (chip["x"] + chip["width"] / 2, chip["y"] + chip["height"] / 2)
        assert middle[0] > tab["x"] + 2 and middle[1] > tab["y"] + 2, (name, chip, tab)

    assert routes["Control, On Me"] == "M", routes

    page.keyboard.press("Escape")
    expect(page.locator("body")).not_to_have_attribute("data-lf-go-to-active", "")
    page.keyboard.press("g")
    expect(chips.first).to_be_visible()
    page.keyboard.type(routes["Control, Menu"])
    expect(panel).to_have_attribute("data-lf-open", "menu")
    expect(page.locator(".lf-fp-tab", has_text="Menu")).to_be_focused()
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    expect(panel).to_have_attribute("data-lf-open", "queue")


def test_a_menu_row_a_go_to_key_runs_wears_that_key(browser, serve):
    """A row of the leaf's menu whose command a Go-to key already runs, as `g H` hides
    the annotations, says that key at its end and wears it as its Go-to chip, and the
    key does what the row does."""
    page = open_page(
        browser,
        serve(leaf_page("Menu keys", '<h1 id="top">Menu keys</h1><p>Words.</p>')),
    )
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    page.locator(".lf-fp-tab", has_text="Menu").click()
    page.locator(".lf-fp-item", has_text="Annotations").click()
    row = page.locator(".lf-fp-item", has_text="Hide annotations")
    expect(row.locator(".lf-fp-end")).to_have_text(re.compile(r"^\s*g\s*H\s*$"))
    page.keyboard.press("g")
    chip = page.locator(f'{CHIPS}[data-lf-hint-code="H"]')
    expect(chip).to_be_visible()
    box, at = row.bounding_box(), chip.bounding_box()
    assert (
        box
        and at
        and box["y"] <= at["y"] + at["height"] / 2 <= box["y"] + box["height"]
    )
    page.keyboard.press("Shift+h")
    expect(page.locator("body")).not_to_have_attribute("data-lf-go-to-active", "")
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    page.locator(".lf-fp-tab", has_text="Menu").click()
    page.locator(".lf-fp-item", has_text="Annotations").click()
    expect(page.locator(".lf-fp-item", has_text="Show annotations")).to_be_visible()


def test_go_to_armed_as_a_panel_view_replaces_another_names_the_arriving_view(
    browser, serve
):
    """A panel view replaces another in one paint, and fades in. Go-to armed as it
    arrives shows its chips on the arriving view, so the view's own controls wear
    chips and no code changes after the first chips show."""
    url = serve(PANEL_PAGE)
    panel_comment(serve.page_dir, "Why forty?", {"section": "how-cap"})
    page = open_page(browser, url)
    panel = page.locator(".lf-floating-panel")
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    expect(panel).to_have_attribute("data-lf-open", "queue")
    rendered(page)
    page.keyboard.press("g")
    page.keyboard.press("Shift+t")
    page.evaluate(
        """() => { window.seenCodes = [];
          const tick = () => {
            const codes = [...document.querySelectorAll('.lf-go-to-hint[data-lf-hint-code]')]
              .filter((chip) => chip.checkVisibility({ visibilityProperty: true }))
              .map((chip) => chip.dataset.lfHintCode).sort().join(' ');
            if (codes && window.seenCodes.at(-1) !== codes) window.seenCodes.push(codes);
            requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick); }"""
    )
    page.keyboard.press("g")
    expect(panel).to_have_attribute("data-lf-open", "threads")
    expect(page.locator(CHIPS).first).to_be_visible()
    rendered(page)
    # Read before `heard_routes` walks the map, whose Tabs can show further chips.
    seen = page.evaluate("window.seenCodes")
    assert len(seen) == 1, seen
    routes = heard_routes(page)
    view = page.locator(".lf-fp-view").bounding_box()
    in_view = [
        box
        for box in page.locator(CHIPS).evaluate_all(
            "chips => chips.map((chip) => chip.getBoundingClientRect().toJSON())"
        )
        if view
        and view["y"] <= box["y"] + box["height"] / 2 <= view["y"] + view["height"]
    ]
    assert in_view, routes


def test_a_message_s_controls_wear_chips_only_while_they_show(browser, serve):
    """A message's controls stay transparent until the pointer or focus is on the
    message, and take a press meanwhile. Go-to names what the user sees, so a reply's
    Add reaction wears no chip at rest and wears one once the pointer shows it."""
    url = serve(PANEL_PAGE)
    root = panel_comment(serve.page_dir, "Why forty?", {"section": "how-cap"})
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "agent": "Claude",
            "parent": root,
            "revision": 1,
            "text": "Forty is what the slowest device we ship on can hold.",
        },
    )
    page = open_page(browser, url)
    view = open_panel_thread(page, root)
    page.evaluate(RELEASE_FOCUS)
    page.mouse.move(4, 4)
    react = view.locator(".lf-react-trigger")
    expect(react).to_have_css("opacity", "0")
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()
    routes = heard_routes(page)
    assert "Control, Resolve thread" in routes, routes
    assert "Control, Add reaction" not in routes, routes

    page.keyboard.press("Escape")
    view.locator(".lf-msg").last.hover()
    expect(react).to_have_css("opacity", "1")
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()
    assert "Control, Add reaction" in heard_routes(page)


def test_a_decision_s_picks_keep_their_chips_when_go_to_arms_on_it(browser, serve):
    """On a decision, each option's pick stands transparent under its digit until Go-to,
    arming, takes the digits away in the frame it paints. The map is read from that
    scene, so every pick wears a chip."""
    page = open_page(browser, serve(BINDING_BADGE_PAGE))
    page.keyboard.press("m")
    page.keyboard.press("Tab")
    expect(page.locator("#c-heater .lf-key-badge")).to_be_visible()
    page.keyboard.press("g")
    routes = heard_routes(page)
    for name in ("Immersion heater", "Heated cable", "Break the ice"):
        assert [route for route in routes if name in route], (name, routes)


def test_a_copy_control_s_code_copies(browser, serve):
    """Web Awesome copies on a click of the button it draws inside its copy control, so
    the control answers Go-to's press of its host the same way, and a code block's
    Copy wears a chip whose code copies the block's source."""
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Copy by code",
                '<h1 id="top">Copy by code</h1><pre id="run"><code>echo hello</code></pre>',
            )
        ),
        context=context,
    )
    page.evaluate("navigator.clipboard.writeText('kept')")
    page.locator("#run").hover()
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()
    routes = heard_routes(page)
    copy = next((code for route, code in routes.items() if "Copy" in route), None)
    assert copy, routes
    page.keyboard.press("Escape")
    page.keyboard.press("g")
    page.keyboard.type(copy)
    page.wait_for_function(
        "() => navigator.clipboard.readText().then(text => text.trim() === 'echo hello')"
    )


def heard_routes(page):
    """Walk the armed map aloud, each hint once, once it has said what it holds, and
    answer each route it says with the code that takes it."""
    rendered(page)
    live = page.locator(".lf-live")
    expect(live).to_have_text(re.compile(r"^Go to — \d+ visible target"))
    heard = []
    for _ in range(page.locator(CHIPS).count()):
        page.keyboard.press("Tab")
        expect(live).to_have_text(re.compile(r"^Hint \w+: "))
        if heard:
            expect(live).not_to_have_text(heard[-1])
        heard.append(live.text_content())
    said = [re.fullmatch(r"Hint (\w+): (.+?)\.? Enter.*", one) for one in heard]
    assert all(said), heard
    return {match.group(2): match.group(1) for match in said if match}


def test_generated_hints_branch_after_the_single_letter_alphabet(browser, serve):
    """A dense visible scene gets one prefix-free namespace with two-letter tails."""
    links = "".join(
        f'<a id="link-{n}" href="#link-{n}">link {n}</a>' for n in range(1, 24)
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Dense links",
                f'<h1>Dense links</h1><nav id="links">{links}</nav>',
                head="""<style>
                  #links { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; }
                  #links a { display: block; padding: 6px; }
                </style>""",
            )
        ),
    )
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()
    codes = address_codes(page)
    # The 23 links and the floating panel's leaf.
    assert len(codes) == len(set(codes)) == 24
    assert all(code.isalpha() and code.islower() for code in codes)
    assert all(
        not other.startswith(code) for code in codes for other in codes if code != other
    )
    # Named routes own their letters even when unavailable in this scene. Read the
    # declared grammar so a new destination cannot stale a copied alphabet or count.
    reserved = page.evaluate(
        """async () => {
          const {pageScopes} = await window.__lfCheckApi();
          const {allBindings: bindings} = await window.__lfCheckApi();
          const generated = 'navigation.target';
          const scope = pageScopes().find(scope => scope.rows?.some(row => row.id === generated));
          return [...new Set(scope.rows.filter(row => row.id !== generated)
            .flatMap(bindings).filter(key => /^[a-z]$/.test(key)))];
        }"""
    )
    assert reserved
    assert not set("".join(codes)) & set(reserved)
    single_letters = {code for code in codes if len(code) == 1}
    branched = [code for code in codes if len(code) == 2]
    assert len(single_letters) + len(branched) == len(codes)
    assert len(branched) > 1 and len({code[0] for code in branched}) == 1

    prefix = branched[0][0]
    assert single_letters | {prefix} == set("abcdefghijklmnopqrstuvwxyz") - set(
        reserved
    )
    continuing_hint = page.locator(
        f'{CHIPS}[data-lf-hint-code="{branched[0]}"] .lf-binding-sequence'
    )
    sequence_size = continuing_hint.evaluate(
        """sequence => {
          window.__lfContinuingHint = sequence;
          window.__lfContinuingKey = sequence.querySelector('kbd');
          const box = sequence.getBoundingClientRect();
          return {width: box.width, height: box.height};
        }"""
    )
    page.keyboard.press(prefix)
    assert address_codes(page) == branched, {
        "codes": address_codes(page),
        "errors": shown(page.lf_errors),
        "live": page.locator(".lf-live").text_content(),
    }
    continued_hint = page.locator(
        f'{CHIPS}[data-lf-hint-code="{branched[0]}"] .lf-binding-sequence'
    )
    assert continued_hint.evaluate(
        """sequence =>
          sequence === window.__lfContinuingHint &&
          sequence.querySelector('kbd') === window.__lfContinuingKey"""
    ), "progress repaint replaced an unchanged hint or its first keycap"
    continued_size = continued_hint.evaluate(
        """sequence => {
          const box = sequence.getBoundingClientRect();
          return {width: box.width, height: box.height};
        }"""
    )
    assert continued_size == pytest.approx(sequence_size, abs=0.1)
    assert continued_hint.locator("kbd").evaluate_all(
        "keys => keys.map(key => [key.textContent, key.dataset.lfSequenceStepState])"
    ) == [[prefix, "pressed"], [branched[0][1], "neutral"]]
    expect(continued_hint).to_have_css("gap", "1px")


def test_go_to_leaves_a_diffs_line_numbers_to_the_target_picker(browser, serve):
    """A diff's line numbers get no chip: commenting on a line is the target picker's,
    and a chip on every line buried the file's own routes. The file's fold and Comment
    keep theirs (control-faces.js, `gutter`)."""
    patch = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        "@@ -1,2 +1,2 @@\n-old\n+new\n same\n"
    )
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Diff routes",
                '<h1>Diff routes</h1><lf-diff id="patch"><pre>'
                + patch
                + "</pre></lf-diff>",
            )
        ),
    )
    expect(page.locator("lf-diff .lf-diff-line-comment")).to_have_count(3)
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()
    live = page.locator(".lf-live")
    heard = []
    for _ in range(page.locator(CHIPS).count()):
        page.keyboard.press("Tab")
        expect(live).to_have_text(re.compile(r"^Hint \w+: "))
        if heard:
            expect(live).not_to_have_text(heard[-1])
        heard.append(live.text_content())
    assert [
        said.split(": ")[1].split(",")[0] for said in heard if "app.py" in said
    ] == ["Fold", "Control"], heard
    assert not [said for said in heard if " line " in said], heard


def test_generated_hints_are_browsable_without_entering_the_paint_layer(browser, serve):
    """The map paints, Tab speaks it, and Enter activates the hint heard. The session's
    letters, walk and rereading are `tests/runtime/hint-session.test.mjs`'s."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Browsable hints",
                """
<h1 id="top">Browsable hints</h1>
<p><a id="first" href="#top">First destination</a></p>
<p><a id="second" href="#arrival">Second destination</a></p>
<h2 id="arrival">Arrival</h2>
""",
            )
        ),
    )
    page.keyboard.press("g")
    # The two links and the floating panel's leaf.
    expect(page.locator(CHIPS)).to_have_count(3)
    for chip in page.locator(CHIPS).all():
        expect(chip).to_be_visible()
    expect(page.locator(".lf-go-to-hints")).to_have_attribute("aria-hidden", "true")
    expect(page.locator(".lf-live")).to_contain_text("3 visible targets")

    page.keyboard.press("Tab")
    first_code = address_code(page, "Link", "first")
    # Every hint stands on screen, the heard one marked, so the walk says no position.
    expect_walk_position(page, None)
    expect(page.locator(".lf-live")).to_have_text(
        f"Hint {first_code}: Link, First destination. Enter go to target"
    )
    expect(page.locator(f'{CHIPS}[data-lf-go-to-target="first"]')).to_have_class(
        re.compile(r"\blf-current\b")
    )

    page.keyboard.press("Tab")
    page.keyboard.press("Enter")
    page.wait_for_url(re.compile(r"#arrival$"))
    expect(page.locator("#arrival")).to_be_focused()
    expect(page.locator("#arrival")).to_be_in_viewport()
    page.evaluate(
        "() => document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})"
    )
    expect(page.locator(CHIPS)).to_have_count(0)


def test_a_revision_under_an_armed_go_to_keeps_its_letters_and_walk(browser, serve):
    """A revision moves the page under an armed Go-to map with no scroll. Each chip rides
    its target, and every letter the user has read and the target the walk stands on
    stay, so the letter they just read takes what they read it on (readings/key-badges/hints.js)."""
    links = "".join(
        f'<p><a id="l{n}" href="#top">Destination {n}</a></p>' for n in range(1, 6)
    )
    heading = '<h1 id="top">Kept letters</h1>'
    source = leaf_page("Kept letters", heading + links)
    page = open_page(browser, live_url(serve(source)))
    page.keyboard.press("g")
    expect(page.locator(ROUTE_CHIPS)).to_have_count(5)
    codes = {n: address_code(page, "Link", f"l{n}") for n in range(1, 6)}
    for _ in range(3):
        page.keyboard.press("Tab")
    expect(page.locator(f'{CHIPS}[data-lf-go-to-target="l3"]')).to_have_class(
        re.compile(r"\blf-current\b")
    )

    added = '<p>New words with <a id="new" href="#top">a new link</a>.</p>'
    (serve.page_dir / "index.html").write_text(source.replace(heading, heading + added))
    told(page)
    expect(page.locator("#new")).to_be_visible()
    rendered(page)
    assert {n: address_code(page, "Link", f"l{n}") for n in range(1, 6)} == codes
    expect(page.locator(f'{CHIPS}[data-lf-go-to-target="l3"]')).to_have_class(
        re.compile(r"\blf-current\b")
    )
    page.keyboard.press("Tab")
    expect(page.locator(f'{CHIPS}[data-lf-go-to-target="l4"]')).to_have_class(
        re.compile(r"\blf-current\b")
    )
    expect(page.locator(".lf-live")).to_contain_text("Destination 4")
