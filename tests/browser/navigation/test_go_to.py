"""Go-to addresses: the `g` sequence's generated hints, the Page Map's destinations, and
the links and new tabs they open."""

import re

import pytest
from interact_support import append_carried_log_record
from leaf import event_log as events_model
from leaf.render_checks import one_frame, rendered
from playwright.sync_api import expect
from render_cases_interaction import ASKS_PAGE
from render_cases_navigation import (
    ADDRESSED_PAGE,
    CHIPS,
    CONTROL_LABEL_PAGE,
    CROWDED_PAGE,
    FOOTED_PAGE,
    NOTED_PAGE,
    _publish,
    address_code,
    address_codes,
    go_to_address,
)
from render_harness import (
    leaf_page,
    open_page,
    opened_tab,
    resized,
    sending,
    shortcut_bar_text,
    shown,
)

from browser.navigation import (
    KEY_LINE_HINTS,
)

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_render_that_keeps_an_external_link_gives_back_the_mark_it_dropped(
    browser, serve
):
    """The link's treatment stands inside the link, so a render that rebuilds the
    children around a kept link leaves nothing beside it to lose. A render that rebuilds
    the link's own words drops its mark, and the link must get the mark back, or it keeps
    describing itself by an id nothing carries."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "kept link",
                '<h1 id="t">Links</h1><p id="holder">Read <a id="ext" '
                'href="https://example.com/source">the source</a> first.</p>',
            )
        ),
    )
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
    expect(link.locator(":scope > .lf-external-mark")).to_have_count(1)
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
            marked: Boolean(link.querySelector(':scope > .lf-external-mark')),
            scroller: scrollerFor(log.querySelector('p')) === log,
            atEnd: log.scrollHeight - log.scrollTop - log.clientHeight <= 2,
          };
        }"""
    )
    assert held == {"target": "_blank", "marked": True, "scroller": True, "atEnd": True}


def test_opened_tab_replaces_the_native_target_with_one_it_can_control(
    browser, one_user
):
    """One native target proves the press, then leaves no unreachable tab behind."""
    page = one_user.new_page()
    destination = "about:blank#expected"
    page.set_content(f'<a id="open" target="_blank" href="{destination}">open</a>')
    browser_session = browser.new_browser_cdp_session()

    def targets():
        return {
            target["targetId"]: target["url"]
            for target in browser_session.send("Target.getTargets")["targetInfos"]
            if target["type"] == "page"
        }

    before = targets()
    presses = 0
    native = {}

    def press():
        nonlocal presses
        presses += 1
        page.locator("#open").click()
        native.update(
            {
                target_id: url
                for target_id, url in targets().items()
                if target_id not in before
            }
        )

    tab = opened_tab(page, destination, press)
    assert presses == 1
    assert len(native) == 1
    assert tab.context is page.context
    assert tab.url == destination
    after = targets()
    assert not (native.keys() & after.keys())
    assert [url for target_id, url in after.items() if target_id not in before] == [
        destination
    ]
    tab.close()
    assert targets() == before
    browser_session.detach()


def test_a_link_hint_leaves_a_newer_gesture_where_it_is(browser, serve):
    """A link hint's trip may wait on what holds its destination. A press made
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
    page.evaluate(
        """() => document.getElementById('holder').addEventListener('lf-reveal',
             (event) => event.detail.present(new Promise((r) => (window.__release = r))))"""
    )
    go_to_address(page, "Link", "internal")
    page.wait_for_url(re.compile(r"#arrival$"))
    page.wait_for_function("() => typeof window.__release === 'function'")
    page.locator("#elsewhere").click()
    page.evaluate("() => window.__release()")
    one_frame(page)
    one_frame(page)
    expect(page.locator("#elsewhere")).to_be_focused()
    expect(page.locator("#arrival")).not_to_be_in_viewport()


def test_generated_hints_include_links_revealed_by_a_page_widget(browser, serve):
    """A visible page route stays addressable when its widget generated the anchors.

    The roomy table of contents is page navigation even though its links are generated
    chrome. Arming the sequence reveals those labels, gives every visible row a hint, and
    following one lands at the heading through the ordinary link route.
    """
    page = open_page(
        browser,
        serve(
            leaf_page(
                "generated page links",
                """
<h1>Migration plan</h1>
<aside class="sidebar"><lf-toc id="contents"></lf-toc></aside>
<section><h2>Prepare</h2><p>Take a snapshot.</p></section>
<div style="height: 700px"></div>
<section><h2 id="move">Move</h2><p>Shift one cohort at a time.</p></section>
<div style="height: 700px"></div>
<section><h2 id="verify">Verify</h2><p>Compare the totals.</p></section>
""",
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
    """Every opaque route fits at viewport edges, including below the banner."""
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
    under_banner = page.locator("#under-banner")
    under_banner.evaluate(
        """link => {
          const covered = document.querySelector('.lf-banner').getBoundingClientRect().bottom;
          link.style.top = `${covered - 18}px`;
          link.addEventListener('click', () => { link.dataset.activated = 'true'; });
        }"""
    )
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()
    reading = page.evaluate(
        """() => ({
          width: document.documentElement.clientWidth,
          height: document.documentElement.clientHeight,
          banner: document.querySelector('.lf-banner').getBoundingClientRect().bottom,
          chips: [...document.querySelectorAll(
            '.lf-go-to-hints .lf-go-to-hint[data-lf-hint-code]')]
            .map(chip => ({
            route: chip.textContent,
            code: chip.dataset.lfHintCode,
            ...chip.getBoundingClientRect().toJSON(),
          })),
        })"""
    )
    assert len(reading["chips"]) == 7, reading
    for chip in reading["chips"]:
        assert 0 <= chip["left"] < chip["right"] <= reading["width"], reading
        assert reading["banner"] <= chip["top"] < chip["bottom"] <= reading["height"], (
            reading
        )
        assert chip["route"] == chip["code"], chip
    under_code = address_code(page, "Link", "under-banner")
    under_index = page.locator(CHIPS).evaluate_all(
        """(chips, code) => chips.findIndex(chip => chip.dataset.lfHintCode === code)""",
        under_code,
    )
    for _ in range(under_index + 1):
        page.keyboard.press("Tab")
    expect(page.locator(".lf-live")).to_have_text(
        f"Hint {under_code}: Link, Under the banner. Press Enter to go there."
    )
    page.keyboard.press("Enter")
    expect(under_banner).to_have_attribute("data-activated", "true")
    expect(page.locator("#top")).to_be_focused()

    page.keyboard.press("g")
    code = address_code(page, "Link", "crowded-neighbor")
    page.keyboard.type(code)
    expect(page.locator(CHIPS)).to_have_count(0)
    expect(page.locator("#top")).to_be_focused()


def test_a_transient_notice_does_not_move_generated_address_hints(browser, serve):
    """Generated hints reserve stable status, not a transient notice's footprint."""
    page = open_page(browser, serve(ADDRESSED_PAGE))
    # Wide enough that the armed line's one row ends short of the corner the link is
    # fixed in; at 1280 the row fills the window and More stands over the link.
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
    page.evaluate(
        "async () => (await window.__lfWidgetApi()).notice('Moved to Done — sent.')"
    )
    expect(page.locator(".lf-notice")).to_be_visible()
    page.keyboard.press("g")
    expect(fixed_link_hint).to_be_visible()
    assert (
        page.evaluate(
            "selector => document.querySelector(selector).getBoundingClientRect().top",
            fixed_link_selector,
        )
        == quiet_top
    )
    expect(page.locator(".lf-notice")).to_be_visible()


def test_generated_hints_spread_without_hiding_a_crowded_target(browser, serve):
    """Crowded opaque routes are separated; none can be inferred if its face is dropped."""
    page = open_page(browser, serve(CROWDED_PAGE))
    resized(page, 1280, 800)
    page.keyboard.press("g")
    expect(page.locator(CHIPS)).to_have_count(5)

    piles = page.evaluate(
        """() => {
             const boxes = [...document.querySelectorAll(
               '.lf-go-to-hints .lf-go-to-hint[data-lf-hint-code]')]
               .map(chip => ({
                 code: chip.dataset.lfHintCode,
                 r: chip.getBoundingClientRect(),
               }));
             const hit = (a, b) => a.left < b.right && b.left < a.right
                                && a.top < b.bottom && b.top < a.bottom;
             const found = [];
             for (let i = 0; i < boxes.length; i++)
               for (let j = i + 1; j < boxes.length; j++)
                 if (hit(boxes[i].r, boxes[j].r))
                   found.push(boxes[i].code + ' under ' + boxes[j].code);
             return {found, drawn: boxes.map(b => b.code)};
           }"""
    )
    assert piles["found"] == [], (
        f"hints are drawn on top of each other: {piles['found']} "
        f"(drawn: {piles['drawn']})"
    )
    assert len(piles["drawn"]) == 5, piles
    page.keyboard.type(address_code(page, "Link", "fn1"))
    page.wait_for_url(re.compile(r"#s1$"))


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
          // against the banner at one end or the window's foot at the other.
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


def test_a_generated_hint_is_never_drawn_on_the_key_line(browser, serve):
    """The sequence's own legend remains clear while visible hints follow a scroll."""
    page = open_page(browser, serve(FOOTED_PAGE))
    resized(page, 900, 700)
    page.keyboard.press("g")
    expect(page.locator(CHIPS).first).to_be_visible()

    # Swept rather than asked once. The line's whole band is reserved at the document's foot,
    # so the end of the page is exactly where this cannot happen; what puts a member in the
    # corner is an ordinary scroll position with a link resting on the bottom edge. Each
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
                 const bar = document.querySelector('.lf-shortcut-bar')
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
    assert fouled == [], (
        f"hints are drawn over the shortcut bar that explains them: {fouled}"
    )


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
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("Page Map")
    page.keyboard.press("Shift+p")

    sheet = page.locator(".lf-page-map-dialog")
    expect(sheet).to_be_visible()
    expect(
        sheet.get_by_role(
            "searchbox", name="Find an action, status, or location in Page Map"
        )
    ).to_be_focused()
    # The one close control every surface wears: the cross, named for what it closes,
    # at the header's end.
    header = sheet.locator(".lf-page-map-head")
    close = header.get_by_role("button", name="Close Page Map", exact=True)
    expect(close.locator('svg[data-lf-icon="cross"]')).to_have_count(1)
    header_box, close_box = header.bounding_box(), close.bounding_box()
    assert header_box and close_box
    assert close_box["x"] + close_box["width"] == pytest.approx(
        header_box["x"] + header_box["width"], abs=0.5
    ), (header_box, close_box)
    expect(sheet).to_contain_text(
        "No margin controls, status indicators, or locations yet"
    )
    expect(sheet.locator(".lf-page-map-action")).to_have_count(0)


def test_the_g_chord_selects_a_visible_tab_hint(browser, serve):
    """A tab can be selected from elsewhere on the page through its generated hint.

    Arrow keys serve a user already standing in the tab strip. The page-level route
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
    expect(page.locator(".lf-walk-position")).to_have_text("Tab 1 of 2")


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
    line = page.locator(".lf-shortcut-bar")

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
        "line": shortcut_bar_text(page),
        "live": page.locator(".lf-live").text_content(),
    }
    expect(line).to_contain_text("back one letter")
    target_route = line.locator(
        '.lf-shortcut:not([data-lf-off-line])[data-lf-command-ids~="navigation.target"]'
    )
    assert target_route.locator("kbd").evaluate_all(
        "keys => keys.map(key => [key.textContent, key.dataset.lfSequenceStepState])"
    ) == [["g", "pressed"], [prefix, "pressed"], ["…", "neutral"]]
    browse_route = line.locator(
        '.lf-shortcut:not([data-lf-off-line])[data-lf-command-ids~="navigation.target.next"]'
    )
    browse_faces = browse_route.locator("kbd").evaluate_all(
        "keys => keys.map(key => [key.textContent, key.dataset.lfSequenceStepState])"
    )
    assert [state for _, state in browse_faces] == ["pressed", "neutral"], browse_faces
    assert browse_faces[0][0] == "g", browse_faces
    assert re.fullmatch(r"⇥ / (⇧|Shift\+)⇥", browse_faces[1][0]), browse_faces
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
    line = page.locator(".lf-shortcut-bar")

    page.keyboard.press("g")
    expect(page.locator(CHIPS)).to_have_count(2)
    for chip in page.locator(CHIPS).all():
        expect(chip).to_be_visible()
    expect(page.locator(".lf-go-to-hints")).to_have_attribute("aria-hidden", "true")
    expect(page.locator(".lf-live")).to_contain_text("2 visible targets")
    expect(line).to_contain_text("browse hints")
    expect(line).to_contain_text("cancel")
    expect(line.locator('[data-lf-command-ids="navigation.go-to.back"]')).to_have_class(
        re.compile(r"\blf-sequence-command\b")
    )

    page.keyboard.press("Tab")
    first_code = address_code(page, "Link", "first")
    expect(page.locator(".lf-walk-position")).to_have_text("Target 1 of 2")
    expect(page.locator(".lf-live")).to_have_text(
        f"Hint {first_code}: Link, First destination. Press Enter to go there."
    )
    expect(page.locator(f'{CHIPS}[data-lf-go-to-target="first"]')).to_have_class(
        re.compile(r"\blf-current\b")
    )

    page.keyboard.press("Tab")
    expect(page.locator(".lf-walk-position")).to_have_text("Target 2 of 2")
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
    """A covering auxiliary surface keeps the global Go-to addresses that can replace it."""
    live_leaf("second", "A second leaf")
    url = serve(ASKS_PAGE, comments=1)
    _publish(serve.page_dir, 2, ASKS_PAGE, "two")
    page = open_page(browser, url)
    resized(page, 420, 800)

    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(page.locator(".lf-others-panel")).to_be_visible()

    for key, opened, closed in (
        ("Shift+m", ".lf-queue-panel", ".lf-others-panel"),
        ("Shift+t", ".lf-thread-panel", ".lf-queue-panel"),
    ):
        page.keyboard.press("g")
        expect(page.locator("body")).to_have_attribute("data-lf-go-to-active", "")
        expect(page.locator(".lf-go-to-hints [data-lf-hint-code]")).to_have_count(0)
        page.keyboard.press(key)
        expect(page.locator(opened)).to_be_visible()
        expect(page.locator(closed)).to_be_hidden()
        assert bool(page.locator("dialog:modal").count())

    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    page_map = page.locator(".lf-page-map-dialog")
    expect(page_map).to_be_visible()
    expect(page_map.get_by_role("searchbox")).to_be_focused()
    assert bool(page.locator("dialog:modal").count())
    page.keyboard.press("Escape")
    expect(page_map).to_be_hidden()

    origin = page.locator(".lf-thread").first.locator(":scope > .lf-thread-summary")
    origin.focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+v")
    versions = page.locator(".lf-version-menu")
    expect(versions).to_be_visible()
    expect(versions.locator('.lf-version-row[data-lf-version="1"]')).to_be_focused()
    assert bool(page.locator("dialog:modal").count())
    rendered(page)
    version_hints = {hint["commands"] for hint in page.evaluate(KEY_LINE_HINTS)}
    # The phone-width line has room for the scope's first hint only; its presence is what
    # says the covering surface left the versions scope in place.
    assert "version.later version.earlier" in version_hints, (
        f"the covering auxiliary surface displaced the versions scope: {version_hints}"
    )

    page.keyboard.press("ArrowUp")
    expect(versions.locator('.lf-version-row[data-lf-version="2"]')).to_be_focused()
    page.keyboard.press("1")
    expect(versions).to_be_hidden()
    expect(origin).to_be_focused()

    page.keyboard.press("g")
    page.keyboard.press("Shift+v")
    expect(versions).to_be_visible()
    versions.locator("button:visible").last.focus()
    page.keyboard.press("Tab")
    expect(versions).to_be_hidden()
    assert page.locator(".lf-thread-panel").evaluate(
        "panel => panel.contains(document.activeElement)"
    ), "Tab left the version popover but escaped its covering auxiliary surface"

    # Escape unwinds to the menu's parent, More, whatever the user stood on before g V;
    # the covering surface stays standing under it.
    origin.focus()
    page.keyboard.press("g")
    page.keyboard.press("Shift+v")
    expect(versions).to_be_visible()
    page.keyboard.press("Escape")
    expect(versions).to_be_hidden()
    expect(page.locator(".lf-version")).to_be_focused()
    expect(page.locator(".lf-thread-panel")).to_be_visible()


def test_signoff_uses_its_visible_button_and_g_l_never_falls_through(browser, serve):
    """Approval is a button action; a dead sequence destination cannot turn into it."""
    html = NOTED_PAGE.replace(
        "</head>",
        '<meta name="lf-review" content="sign-off">\n</head>',
    )
    page = open_page(browser, serve(html))
    approve = page.locator(".lf-signoff")
    expect(approve).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))

    # All pages is conditional. With no neighbouring leaf, its sequence must not be
    # reinterpreted as a page action carrying the same final key.
    page.keyboard.press("g")
    page.keyboard.press("Shift+l")
    expect(approve).to_have_text("Approve version")
    assert not [
        e for e in events_model.read_events(serve.page_dir) if e["kind"] == "done"
    ]

    approve.focus()
    with sending(page, "the approval"):
        page.keyboard.press("Enter")
    expect(approve).to_have_text("✓ Version approved")
    expect(approve).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))
    assert "(L)" not in approve.get_attribute("title")
    done = [e for e in events_model.read_events(serve.page_dir) if e["kind"] == "done"]
    assert [event["version"] for event in done] == [1], done


def test_banner_destinations_use_transient_target_overlays(browser, serve):
    """The g sequence labels visible primary controls without changing their layout."""
    url = serve(ASKS_PAGE)
    append_carried_log_record(
        serve.page_dir,
        {"kind": "comment", "author": "user", "revision": 1, "text": "A note."},
    )
    page = open_page(browser, url)
    resized(page, 1600, 900)
    more = page.locator(".lf-shortcut-more")
    expect(more).to_have_attribute("aria-label", "? more")
    key_faces = page.evaluate(
        """() => ['.lf-shortcut-more kbd', '.lf-shortcut-bar .lf-shortcut:not([data-lf-off-line]) kbd']
          .map(sel => { const s = getComputedStyle(document.querySelector(sel));
            return {height: s.height, padding: s.padding, border: s.borderTopWidth,
                    radius: s.borderRadius, font: s.fontFamily};
          })"""
    )
    assert key_faces[0] == key_faces[1], key_faces
    banner_destinations = {
        "navigation.panel.threads": (page.locator(".lf-threads-toggle"), "T"),
        "navigation.drawer.queue": (page.locator(".lf-queue"), "M"),
    }
    for control, suffix in banner_destinations.values():
        expect(control).to_have_attribute("title", re.compile(rf"\(g {suffix}\)$"))
        expect(control.locator(".lf-target-picker-hint")).to_have_count(0)
    expect(page.locator(".lf-go-to-hints [data-lf-go-to-command]")).to_have_count(0)
    expect(page.locator(".lf-latest-chip")).to_have_attribute(
        "title", re.compile(r"\(g V v\)$")
    )
    # Put an ordinary page destination where the Threads hint will first stand. The
    # second placement pass must treat the already-seated control hint as occupied.
    threads_box = page.locator(".lf-threads-toggle").bounding_box()
    page.evaluate(
        """box => {
          const probe = document.createElement('a');
          probe.id = 'hint-collision-probe';
          probe.href = '#hint-collision-probe';
          probe.textContent = 'Collision probe';
          const bannerBottom = document.querySelector('.lf-banner')
            .getBoundingClientRect().bottom;
          Object.assign(probe.style, {
            position: 'fixed', left: `${box.x}px`, top: `${bannerBottom + 4}px`,
          });
          document.querySelector('main').append(probe);
        }""",
        threads_box,
    )

    before = page.locator(".lf-banner").bounding_box()
    page.keyboard.press("g")
    expect(page.locator(".lf-shortcut-bar")).to_contain_text("visible target")
    for command in ("version.open",):
        expect(
            page.locator(f'.lf-go-to-hints [data-lf-go-to-command="{command}"]')
        ).to_have_count(0)
    expect(
        page.locator(f'{CHIPS}[data-lf-go-to-target="hint-collision-probe"]')
    ).to_be_visible()
    for command, (control, suffix) in banner_destinations.items():
        hint = page.locator(
            f'.lf-go-to-hints .lf-go-to-hint[data-lf-go-to-command="{command}"]'
        )
        expect(hint).to_be_visible()
        assert hint.locator("kbd").evaluate_all(
            "keys => keys.map(key => [key.textContent, key.dataset.lfSequenceStepState])"
        ) == [["g", "pressed"], [suffix, "neutral"]]
        expect(control.locator(".lf-target-picker-hint")).to_have_count(0)
        hint_box, control_box = control.evaluate(
            """(control, command) => [
              document.querySelector(
                `.lf-go-to-hints [data-lf-go-to-command="${command}"]`
              ).getBoundingClientRect().toJSON(),
              control.getBoundingClientRect().toJSON(),
            ]""",
            command,
        )
        assert hint_box["y"] - control_box["y"] - control_box[
            "height"
        ] == pytest.approx(2, abs=0.5), (
            command,
            hint_box,
            control_box,
        )
        assert hint_box["x"] + hint_box["width"] / 2 == pytest.approx(
            control_box["x"] + control_box["width"] / 2, abs=0.5
        ), (command, hint_box, control_box)
    all_hints = page.locator(".lf-go-to-hints .lf-go-to-hint:visible")
    boxes = all_hints.evaluate_all(
        """hints => hints.map(hint => {
          const box = hint.getBoundingClientRect();
          return {left: box.left, right: box.right, top: box.top, bottom: box.bottom};
        })"""
    )
    assert all(
        not (
            left["left"] < right["right"]
            and right["left"] < left["right"]
            and left["top"] < right["bottom"]
            and right["top"] < left["bottom"]
        )
        for index, left in enumerate(boxes)
        for right in boxes[index + 1 :]
    ), boxes
    assert page.locator(".lf-banner").bounding_box() == before

    # A narrow banner folds less-used controls away. The surviving controls also have
    # open space above, but each destination hint belongs immediately below its control.
    resized(page, 390, 800)
    for command, control in (
        ("navigation.panel.threads", page.locator(".lf-threads-toggle")),
    ):
        hint = page.locator(
            f'.lf-go-to-hints .lf-go-to-hint[data-lf-go-to-command="{command}"]'
        )
        expect(hint).to_be_visible()
        hint_box, control_box = control.evaluate(
            """(control, command) => [
              document.querySelector(
                `.lf-go-to-hints [data-lf-go-to-command="${command}"]`
              ).getBoundingClientRect().toJSON(),
              control.getBoundingClientRect().toJSON(),
            ]""",
            command,
        )
        assert hint_box["y"] - control_box["y"] - control_box[
            "height"
        ] == pytest.approx(2, abs=0.5), (
            command,
            hint_box,
            control_box,
        )
        assert hint_box["x"] + hint_box["width"] / 2 == pytest.approx(
            control_box["x"] + control_box["width"] / 2, abs=0.5
        ), (command, hint_box, control_box)
    expect(page.locator(".lf-latest-chip")).to_have_attribute(
        "title", re.compile(r"\(g V v\)$")
    )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-go-to-hints [data-lf-go-to-command]")).to_have_count(0)

    page.keyboard.press("?")
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).not_to_contain_text(
        "Letter, number & punctuation shortcuts"
    )
    expect(page.locator(".lf-command-reference-meta")).to_be_visible()
