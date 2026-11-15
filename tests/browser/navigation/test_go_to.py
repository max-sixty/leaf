"""Go-to addresses: the `g` sequence's generated hints, the Page Map's destinations, and
the links and new tabs they open."""

import re

import pytest
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATIONS_PAGE, live_url
from render_cases_navigation import (
    ADDRESSED_PAGE,
    CHIPS,
    CONTROL_LABEL_PAGE,
    CROWDED_PAGE,
    FOOTED_PAGE,
    _publish,
    address_code,
    address_codes,
    go_to_address,
)
from render_harness import (
    PANEL,
    leaf_page,
    open_page,
    panel_view,
    resized,
    shown,
    told,
)

from browser.navigation import expect_walk_position
from browser.threads import open_panel_thread
from leaf import event_log as events_model
from leaf.render_checks import one_frame, rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_render_of_an_external_links_words_keeps_its_treatment(browser, serve):
    """CSS paint and the root's accessible description survive a link's text render."""
    source = leaf_page(
        "kept link",
        '<h1 id="t">Links</h1><p id="holder">Read <a id="ext" '
        'href="https://example.com/source">the source</a> first.</p>'
        '<p id="other">Other words.</p>',
    )
    page = open_page(browser, live_url(serve(source)))
    link = page.locator("#ext")
    expect(link).to_have_accessible_description("opens in a new tab")
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
    expect(link).to_have_accessible_description("opens in a new tab")

    # A source revision compares authored hrefs, not the marker prepaint lent the
    # first document. An unrelated edit leaves the same link and its treatment.
    page.evaluate("window.keptLink = document.getElementById('ext')")
    (serve.page_dir / "index.html").write_text(
        source.replace("Other words.", "Revised other words.")
    )
    told(page)
    expect(page.locator("#other")).to_have_text("Revised other words.")
    assert page.evaluate("window.keptLink === document.getElementById('ext')")
    expect(link).to_have_attribute("data-lf-external", "")
    expect(link).to_have_accessible_description("opens in a new tab")


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
            target: link.getAttribute('target'),
            marked: link.hasAttribute('data-lf-external'),
            scroller: scrollerFor(log.querySelector('p')) === log,
            atEnd: log.scrollHeight - log.scrollTop - log.clientHeight <= 2,
          };
        }"""
    )
    assert held == {"target": "_blank", "marked": True, "scroller": True, "atEnd": True}


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
    expect(links.first).to_have_css("opacity", "0")

    page.keyboard.press("g")
    chips = page.locator(f'{CHIPS}[data-lf-go-to-kind="Link"]')
    expect(chips).to_have_count(4)
    first_code = chips.first.get_attribute("data-lf-hint-code")
    assert first_code
    page.keyboard.press("Tab")
    expect(page.locator(".lf-live")).to_have_text(
        f"Hint {first_code}: Link, Migration plan. Press Enter to go there."
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
    panel, and its code still takes it (keyboard/hints.js, `seatHints`)."""
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
            '.lf-go-to-hints .lf-go-to-hint[data-lf-hint-code]')]
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
        f"Hint {under_code}: Link, Over the top. Press Enter to go there."
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
    page.evaluate("async () => (await window.__lfWidgetApi()).notice('Moved to Done.')")
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
    expect(page.locator(CHIPS)).to_have_count(5)

    shown = address_codes(page)
    markers = {address_code(page, "Link", f"fn{n}") for n in (1, 2, 3)}
    assert len(shown) == 2, shown
    assert not markers & set(shown), (markers, shown)
    page.keyboard.type(address_code(page, "Link", "fn1"))
    page.wait_for_url(re.compile(r"#s1$"))


def test_a_chip_stands_beside_a_link_in_an_svg_drawing_s_html(browser, serve):
    """Chromium resolves no anchor to an element inside a foreignObject, so the chip
    anchored to a link there stood off the window while its code still followed it."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Drawn terminal",
                '<h1 id="top">Drawn terminal</h1><svg id="drawing" width="400" '
                'height="120"><foreignObject x="80" y="40" width="200" height="40">'
                '<div xmlns="http://www.w3.org/1999/xhtml"><a id="run" '
                'href="#top">$ wt merge</a></div></foreignObject></svg>',
            )
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
    expect(page.locator(CHIPS)).to_have_count(24)
    rendered(page)
    seats = """() => Object.fromEntries([...document.querySelectorAll(
        '.lf-go-to-hints .lf-go-to-hint[data-lf-hint-code]')]
      .filter((chip) => chip.checkVisibility({visibilityProperty: true}))
      .map((chip) => {
        const r = chip.getBoundingClientRect();
        return [chip.dataset.lfHintCode, [r.left, r.top]];
      }))"""
    whole = page.evaluate(seats)
    assert len(whole) == 24, whole

    letter = next(code for code in whole if len(code) == 2)[0]
    page.keyboard.press(letter)
    rendered(page)
    typed = page.evaluate(seats)
    assert typed and all(code.startswith(letter) for code in typed), typed
    assert {code: whole[code] for code in typed} == typed

    page.keyboard.press("Escape")
    page.keyboard.press("f")
    rendered(page)
    folds = page.evaluate(seats)
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
    # Longer than the session's settle, so the map has stood still and the user has had
    # the chance to read it. A map armed into a page already moving is a different case,
    # held by tests/runtime/hint-session.test.mjs.
    page.wait_for_timeout(200)

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


def test_a_generated_hint_is_never_drawn_on_the_panel(browser, serve):
    """The panel stays clear while visible hints follow a scroll."""
    page = open_page(browser, serve(FOOTED_PAGE))
    resized(page, 900, 700)
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()

    # Swept rather than asked once. The panel's room is reserved at the document's foot,
    # so the end of the page is exactly where this cannot happen; what puts a member under
    # it is an ordinary scroll position with a link resting on the bottom edge. Each
    # step waits for the runtime's own paint frame, since the chips follow a scroll on a
    # frame of their own and boxes read in the same turn are the positions it just left.
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
                   '.lf-go-to-hints .lf-go-to-hint[data-lf-hint-code]')]
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
    # at the header's end.
    header = sheet.locator(".lf-dialog-head")
    close = header.get_by_role("button", name="Close Page Map", exact=True)
    expect(close.locator('svg[data-lf-icon="cross"]')).to_have_count(1)
    header_box, close_box = header.bounding_box(), close.bounding_box()
    assert header_box and close_box
    assert close_box["x"] + close_box["width"] == pytest.approx(
        header_box["x"] + header_box["width"], abs=0.5
    ), (header_box, close_box)
    expect(sheet).to_contain_text(
        "No margin controls, status indicators or locations yet"
    )
    expect(sheet.locator(".lf-page-map-action")).to_have_count(0)


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
    page.keyboard.type(address_code(page, "Tab", "tab-bath"))

    expect(tabs.nth(1)).to_have_attribute("aria-selected", "true")
    expect(tabs.nth(1)).to_be_focused()
    expect(page.locator("#tab-bath")).not_to_have_attribute("hidden", re.compile(".*"))
    expect(page.locator("#tab-feeders")).to_have_attribute("hidden", re.compile(".*"))
    page.keyboard.press("ArrowLeft")
    expect(tabs.first).to_be_focused()
    expect_walk_position(page, "Tab 1 of 2")


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
    assert len(codes) == len(set(codes)) == 23
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
    assert [said.split(": ")[1].split(",")[0] for said in heard] == [
        "Fold",
        "Control",
    ], heard
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
    expect(page.locator(CHIPS)).to_have_count(2)
    for chip in page.locator(CHIPS).all():
        expect(chip).to_be_visible()
    expect(page.locator(".lf-go-to-hints")).to_have_attribute("aria-hidden", "true")
    expect(page.locator(".lf-live")).to_contain_text("2 visible targets")

    page.keyboard.press("Tab")
    first_code = address_code(page, "Link", "first")
    expect_walk_position(page, "Target 1 of 2")
    expect(page.locator(".lf-live")).to_have_text(
        f"Hint {first_code}: Link, First destination. Press Enter to go there."
    )
    expect(page.locator(f'{CHIPS}[data-lf-go-to-target="first"]')).to_have_class(
        re.compile(r"\blf-current\b")
    )

    page.keyboard.press("Tab")
    expect_walk_position(page, "Target 2 of 2")
    page.keyboard.press("Enter")
    page.wait_for_url(re.compile(r"#arrival$"))
    expect(page.locator("#arrival")).to_be_focused()
    expect(page.locator("#arrival")).to_be_in_viewport()
    page.evaluate(
        "() => document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})"
    )
    expect(page.locator(CHIPS)).to_have_count(0)


def test_global_destinations_switch_from_a_covering_workspace(
    browser, serve, live_leaf
):
    """An open view keeps the global Go-to addresses that can replace it."""
    live_leaf("second", "A second leaf")
    url = serve(OBLIGATIONS_PAGE, comments=1)
    _publish(serve.page_dir, 2, OBLIGATIONS_PAGE, "two")
    page = open_page(browser, url)
    resized(page, 420, 800)

    def view(name):
        return page.locator(panel_view(name))

    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(view("leaves")).to_be_visible()

    for key, opened, closed in (
        ("Shift+m", "queue", "leaves"),
        ("Shift+t", "threads", "queue"),
    ):
        page.keyboard.press("g")
        expect(page.locator("body")).to_have_attribute("data-lf-go-to-active", "")
        page.keyboard.press(key)
        expect(view(opened)).to_be_visible()
        expect(view(closed)).to_have_count(0)

    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    page_map = page.locator(".lf-page-map-dialog")
    expect(page_map).to_be_visible()
    expect(page_map.get_by_role("searchbox")).to_be_focused()
    page.keyboard.press("Escape")
    expect(page_map).to_be_hidden()

    # From a thread open in the panel, Versions opens over the leaf's menu in the
    # thread's place, as every view does; Escape steps back to the menu, then puts the
    # view away.
    thread_id = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event["kind"] == "comment"
    )
    open_panel_thread(page, thread_id).focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+v")
    versions = view("versions")
    expect(versions).to_be_visible()
    assert versions.evaluate("view => view.contains(document.activeElement)")
    expect(versions.locator(".lf-fp-version")).to_have_count(2)
    expect(page.locator(".lf-fp-head .lf-fp-back")).to_have_accessible_name(
        "Back to Menu"
    )
    page.keyboard.press("Escape")
    expect(versions).to_have_count(0)
    expect(page.locator(PANEL)).to_have_attribute("data-lf-open", "menu")
    page.keyboard.press("Escape")
    expect(page.locator(PANEL)).not_to_have_attribute("data-lf-open", re.compile("."))
