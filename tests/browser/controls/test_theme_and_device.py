"""How theme tokens and the device shape the chrome: motion inputs and preference, panel
default width, elevation, coarse-pointer aims, safe areas, and phone-width wrapping."""

import pytest
from playwright.sync_api import expect
from render_cases_layout import UNBREAKABLE_PAGE
from render_harness import (
    LONG_PAGE,
    displayed,
    leaf_page,
    open_page,
    open_threads,
    page_comment,
    panel_menu,
    panel_settled,
    resized,
    write,
)

from leaf.render_checks import wait_until_ready

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_type_scale_follows_root_font_size_with_rounded_key_badges(browser, serve):
    """Prose, working density and code follow the reader's root size; the badge
    allocation remains whole pixels and controls retain their input routes."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Readable controls",
                '<h1>Readable controls</h1><p id="prose">Body words.</p>'
                '<pre id="code">const answer = 42;</pre>'
                '<span id="badge" style="display:inline-block;inline-size:var(--lf-key-badge-size)">A</span>'
                '<section class="density-working"><p id="dense">Working words.</p>'
                '<pre id="dense-code">const answer = 42;</pre>'
                '<span id="dense-badge" style="display:inline-block;inline-size:var(--lf-key-badge-size)">B</span>'
                '<label class="choice"><input type="checkbox">Include notes</label></section>',
            )
        ),
    )

    def sizes():
        return page.evaluate("""() => Object.fromEntries(
          ['prose', 'code', 'badge', 'dense', 'dense-code', 'dense-badge'].map(id => {
            const style = getComputedStyle(document.getElementById(id));
            return [id, parseFloat(id.includes('badge') ? style.inlineSize : style.fontSize)];
          }))""")

    before = sizes()
    assert before == {
        "prose": 17,
        "code": 13.5,
        "badge": 19,
        "dense": 14,
        "dense-code": 13,
        "dense-badge": 18,
    }
    page.add_style_tag(content=":root { font-size: 20px; }")
    after = sizes()
    for name in ("prose", "code", "dense", "dense-code"):
        assert after[name] == before[name] * 1.25, after
    assert after["badge"] == 23 and after["dense-badge"] == 21, after
    choice = page.get_by_role("checkbox", name="Include notes")
    choice.press("Space")
    expect(choice).to_be_checked()


@pytest.mark.parametrize("touch", [False, True])
def test_native_choices_keep_small_marks_in_label_sized_targets(browser, serve, touch):
    """Authored choices share their label's hit area and focus ring without boxing
    selection or enlarging the native mark for a finger."""
    source = leaf_page(
        "Preview settings",
        '<h1>Preview settings</h1><div role="group" aria-label="Detail">'
        '<label class="choice"><input type="radio" name="detail" value="summary" checked>'
        "<span>Summary</span></label>"
        '<label class="choice"><input type="radio" name="detail" value="full">'
        "<span>Full detail</span></label></div>"
        '<label class="choice"><input type="checkbox" name="notes">'
        "<span>Include notes</span></label>",
    )
    context = browser.new_context(has_touch=touch)
    page = open_page(browser, serve(source), context=context)
    full = page.get_by_role("radio", name="Full detail")
    face = page.locator("label").filter(has=full)
    before = face.bounding_box()
    words = face.get_by_text("Full detail")
    words.tap() if touch else words.click()
    expect(full).to_be_checked()
    full.press("ArrowLeft")
    summary = page.get_by_role("radio", name="Summary", exact=True)
    expect(summary).to_be_checked()
    expect(summary).to_be_focused()
    assert face.bounding_box() == before
    ring = (
        page.locator("label")
        .filter(has=summary)
        .evaluate("el => getComputedStyle(el).outlineStyle")
    )
    assert ring == "solid"
    words = page.get_by_text("Include notes", exact=True)
    words.tap() if touch else words.click()
    expect(page.get_by_role("checkbox", name="Include notes")).to_be_checked()
    readings = page.locator("label.choice").evaluate_all("""labels => labels.map(label => {
      const style = getComputedStyle(label), box = label.getBoundingClientRect();
      const mark = label.querySelector('input').getBoundingClientRect();
      return {height: box.height, floor: parseFloat(style.getPropertyValue('--aim-floor')),
        mark: mark.height, border: style.borderStyle, background: style.backgroundColor};
    })""")
    for reading in readings:
        assert reading["height"] >= reading["floor"]
        assert reading["mark"] < reading["floor"]
        assert reading["border"] == "none"
        assert reading["background"] == "rgba(0, 0, 0, 0)"


def test_stylesheet_motion_inputs_drive_css_and_web_animations(browser, serve):
    """A theme's time expressions reach both consumers through native CSS resolution."""
    source = leaf_page(
        "Motion inputs",
        '<h1>Motion inputs</h1><p id="subject">A visible arrival.</p>'
        '<lf-suggestion id="edit"><lf-old><p>Before</p></lf-old>'
        "<lf-new><p>After</p></lf-new></lf-suggestion>",
        head="""<style>:root {
          --lf-motion-flash: calc(.7s + 30ms);
          --lf-motion-fold: 170ms;
          --lf-motion-agent-arrival: .91s;
        }</style>""",
    )
    context = browser.new_context(reduced_motion="no-preference")
    page = open_page(browser, serve(source), context=context)
    result = page.evaluate("""async () => {
      const owner = await window.__lfWidgetApi();
      const chrome = document.querySelector('.lf-chrome');
      const arrival = document.createElement('button');
      arrival.className = 'lf-margin-entry';
      arrival.dataset.lfAgentArrival = '1';
      chrome.append(arrival);
      const cssArrival = getComputedStyle(arrival).animationDuration;
      const cssFold = getComputedStyle(document.querySelector('lf-old')).transitionDuration;
      const {flashDuration, agentArrivalDuration} = await window.__lfCheckApi();
      const animation = owner.backgroundFlash(document.querySelector('#subject'), flashDuration());
      const played = animation.effect.getTiming().duration;
      animation.finish();
      arrival.remove();
      return {cssArrival, cssFold, played,
        fold: owner.foldDuration(), agent: agentArrivalDuration()};
    }""")
    assert result == {
        "cssArrival": "0.91s",
        "cssFold": "0.17s",
        "played": 730,
        "fold": 170,
        "agent": 910,
    }


def test_motion_preference_changes_are_heard_without_reloading(browser, serve):
    """The JS motion contract follows a live media preference, like the CSS does."""
    page = open_page(browser, serve(LONG_PAGE))
    reading = """() => window.__lfWidgetApi().then(
      motion => ({reduced: motion.reducedMotion(), scroll: motion.scrollBehavior()}))"""
    assert page.evaluate(reading) == {"reduced": False, "scroll": "smooth"}

    page.emulate_media(reduced_motion="reduce")
    assert page.evaluate(reading) == {"reduced": True, "scroll": "instant"}
    step = page.evaluate(
        "() => { const s = getComputedStyle(document.scrollingElement); return ("
        " document.scrollingElement.clientHeight - parseFloat(s.scrollPaddingTop)"
        " - parseFloat(s.scrollPaddingBottom)) * 0.6; }"
    )
    page.evaluate(
        "() => document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})"
    )
    page.keyboard.press("d")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == pytest.approx(
        step, abs=1
    ), "the navigation factory kept its load-time motion preference"

    page.emulate_media(reduced_motion="no-preference")
    assert page.evaluate(reading) == {"reduced": False, "scroll": "smooth"}

    page.evaluate(
        """() => {
          window.__lfFrames = [];
          window.requestAnimationFrame = callback =>
            (window.__lfFrames.push(callback), window.__lfFrames.length);
          window.cancelAnimationFrame = () => {};
          document.scrollingElement.scrollTo({top: 0, behavior: 'instant'});
        }"""
    )
    page.keyboard.press("d")
    assert page.evaluate("() => window.__lfFrames.length") > 0
    page.emulate_media(reduced_motion="reduce")
    page.evaluate(
        """() => {
          const frames = window.__lfFrames.splice(0);
          for (const callback of frames) callback(0);
        }"""
    )
    assert page.evaluate("() => document.scrollingElement.scrollTop") == pytest.approx(
        step, abs=1
    ), "an active glide kept moving after the user asked for reduced motion"


def test_coarse_pointer_panel_lists_give_humane_aims(browser, serve):
    """Touch keeps the panel's compact paint while its lists' rows take a finger-sized
    aim."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    page = open_page(browser, serve(LONG_PAGE, comments=1), context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches"), (
        "the touch fixture never reached Leaf's coarse-pointer rules"
    )

    def humane(locator, what):
        assert locator.count() >= 1, f"no {what} to aim at"
        for index in range(locator.count()):
            box = locator.nth(index).bounding_box()
            assert box["width"] >= 43.9 and box["height"] >= 43.9, (
                f"a {what} kept a mouse-sized aim: {box}"
            )

    # The rows of the panel's lists, which a finger picks among.
    open_threads(page)
    humane(page.locator(".lf-fp-thread:visible"), "Threads row")
    page.locator(".lf-fp-close").tap()
    panel_settled(page, open=False)
    humane(panel_menu(page, touch=True).locator(".lf-fp-item:visible"), "menu row")


def test_a_run_with_nothing_to_break_on_stays_inside_the_box_holding_it(browser, serve):
    """Native values and prose paths wrap within their allocated boxes at phone width."""
    page = open_page(browser, serve(UNBREAKABLE_PAGE))
    resized(page, 420, 900)
    inside = """(id) => {
                  const el = document.getElementById(id);
                  const inner = el.querySelector("[data-lf-said='value']") ?? el;
                  const range = document.createRange();
                  range.selectNodeContents(inner);
                  const style = getComputedStyle(el);
                  return range.getBoundingClientRect().right -
                         (el.getBoundingClientRect().right - parseFloat(style.paddingRight));
                }"""
    assert page.evaluate(inside, "m-token") <= 0, (
        "a metric's value paints outside its card"
    )
    assert page.evaluate(inside, "p-token") <= 0, (
        "a path in prose paints outside the column"
    )


def test_dynamic_chrome_offsets_keep_the_safe_area_in_their_arithmetic(browser, serve):
    """The panel keeps the inset tokens stated by the stylesheet: it stands clear of the
    window's foot by the bottom inset, and inside the side insets, with a view open as
    with none. The insets are stated on the root, where the panel's own offsets read
    them."""
    page = open_page(browser, serve(LONG_PAGE))
    insets = {"left": 17, "right": 31, "bottom": 23}
    page.evaluate(
        """insets => {
          for (const [side, value] of Object.entries(insets))
            document.documentElement.style.setProperty(`--lf-safe-${side}`, `${value}px`);
        }""",
        insets,
    )
    reading = """() => {
      const r = document.querySelector('.lf-floating-panel').getBoundingClientRect();
      return {left: r.left, right: r.right, bottom: r.bottom,
              width: innerWidth, height: innerHeight};
    }"""
    for width in (500, 420):
        resized(page, width, 700)
        for opened in (False, True):
            if opened:
                page.locator(".lf-fp-on-user").click()
            panel_settled(page, open=opened)
            box = page.evaluate(reading)
            assert box["bottom"] <= box["height"] - insets["bottom"], (width, box)
            assert box["left"] >= insets["left"] - 1, (width, box)
            assert box["right"] <= box["width"] - insets["right"] + 1, (width, box)
        page.locator(".lf-fp-close").click()

    # The page comment's Send stands inside the side insets too, where words are typed.
    write(page_comment(page), "Review this page")
    send = page.locator(".lf-fp-send:visible").bounding_box()
    assert send["x"] + send["width"] <= 420 - insets["right"] + 1, send


# Every declaration in the page's composed layer that spells a lift: a box-shadow, a
# filter's drop-shadow(), or a custom property either reads, with a blur radius written
# out. A ring is `0 0 0 Npx`
# and an inset band is `inset …`, so
# the reading asks for a third length that is not nought — which is the one thing that
# separates elevation from the other two uses of the property, and is decidable from the
# declaration where "is this a shadow" is not.
#
# Flat and condition-blind: nothing re-runs a selector, and a shadow painted only in some
# other medium is one this reading should say nothing about.
ELEVATION_SHADOWS = """() => {
  // A shadow list's layers, or a filter's drop-shadow() arguments, which may hold a
  // colour function's own parentheses.
  const layersOf = (property, value) => {
    if (property !== 'filter') return value.split(/,(?![^(]*\\))/);
    const layers = [];
    for (let at = value.indexOf('drop-shadow('); at >= 0;
         at = value.indexOf('drop-shadow(', at + 1)) {
      let depth = 0, end = at + 'drop-shadow'.length;
      for (; end < value.length; end++) {
        if (value[end] === '(') depth++;
        else if (value[end] === ')' && --depth === 0) break;
      }
      layers.push(value.slice(at + 'drop-shadow('.length, end));
    }
    return layers;
  };
  // A height is written from its drop and blur tokens (base.css), so those read as
  // the lengths they hold, and a rule spelling a lift from them is still a lift.
  const theme = getComputedStyle(document.documentElement);
  const parts = (value) => value.replace(/var\\((--raise-\\d-(?:drop|blur))\\)/g,
    (_, name) => theme.getPropertyValue(name).trim());
  const found = [];
  const eaten = new Set();
  const eat = (sheet) => {
    if (!sheet || eaten.has(sheet)) return;
    eaten.add(sheet);
    let list;
    try { list = sheet.cssRules; } catch { return; }  // a sheet from another origin
    const walk = (from) => {
      for (const rule of from) {
        // Position-try descriptors expose item(i), but not indexed properties.
        const named = rule.style
          ? Array.from({length: rule.style.length}, (_, i) => rule.style.item(i)) : [];
        const lifted = (name) => ['box-shadow', 'filter'].includes(name) || name.startsWith('--');
        for (const property of named.filter(lifted)) {
          const value = parts(rule.style.getPropertyValue(property).trim());
          if (!value || value === 'none') continue;
          // The blur, which is the third length of a layer, past the two offsets. A ring
          // writes `0 0 0 Npx` and has none; an inset band is not a lift at all. Read per
          // layer, because a control may state its ring and its lift in one declaration.
          const lifts = layersOf(property, value).filter((layer) => {
            if (/(^|\\s)inset(\\s|$)/.test(layer)) return false;
            // Functions in a shadow can contain numbers (rgb, calc). Only lengths
            // at the shadow layer's top level describe its offsets and blur.
            let depth = 0;
            const outside = [...layer].map((char) => {
              if (char === '(') { depth++; return ' '; }
              if (char === ')') { depth--; return ' '; }
              return depth ? ' ' : char;
            }).join('');
            const lengths = outside.trim().split(/\\s+/)
              .filter((token) => /^-?(\\d*\\.)?\\d+(px)?$/.test(token));
            return lengths.length >= 3 && parseFloat(lengths[2]) !== 0
              && lengths.some((token) => token.endsWith('px'));
          });
          if (!lifts.length) continue;
          const own = rule.selectorText;
          const up = rule.parentRule?.selectorText;
          found.push({
            said: own && up ? `${up} { ${own}` : (own ?? up ?? '(a declaration)'),
            property,
            value: lifts.map((layer) => layer.trim()).join(', '),
          });
        }
        if (rule.cssRules) walk(rule.cssRules);
      }
    };
    walk(list);
  };
  const roots = [document];
  for (const root of roots) {
    for (const sheet of root.styleSheets) eat(sheet);
    for (const sheet of root.adoptedStyleSheets) eat(sheet);
    for (const el of root.querySelectorAll('*')) if (el.shadowRoot) roots.push(el.shadowRoot);
  }
  return found;
}"""


# A box that spends --shade, since the token itself is the same `light-dark()` text
# under either scheme.
PAINTED_SHADE = """() => {
  const probe = document.createElement('div');
  probe.style.color = 'var(--shade)';
  document.body.append(probe);
  const ink = getComputedStyle(probe).color;
  probe.remove();
  return ink;
}"""


def test_every_lift_names_one_of_the_theme_s_heights_cast_in_the_scheme_s_ink(
    browser, serve
):
    """A box stands at one of three heights, and only the theme spells them out.

    Twenty-nine lifts once wrote fourteen geometries between them, so two menus beside
    each other stood at different heights for no reason anyone chose, and nothing kept
    the next one from writing a fifteenth. The `--raise-*` tokens (base.css, beside
    --shade) are now the only declarations that write a blur; every other rule, a
    filter's drop-shadow() included, names one, with a hairline or ring beside it where
    its edge needs one.

    A drop shadow written as rgba(0,0,0,α) can only be right about one ground: at .12
    over the light paper a menu lifts its ground by 10 L*, and over the dark paper by
    1.4. So the heights are cast in --shade, the ink stated once per scheme, and the two
    schemes are then asked for different answers from it.

    Asked of the declarations rather than of the paint, because that is where the fault
    is: "does this name the token" is exact, where a screenshot of a blurred edge is not.
    """
    page = open_page(browser, serve(LONG_PAGE))
    lifted = page.evaluate(ELEVATION_SHADOWS)
    heights = {s["property"] for s in lifted if s["property"].startswith("--raise-")}
    assert heights == {"--raise-1", "--raise-2", "--raise-3"}, (
        f"the layer spells the heights {sorted(heights)}, not --raise-1 to --raise-3: "
        f"this reading has stopped finding them and the assertions below are about "
        f"nothing"
    )
    spelled = [s for s in lifted if not s["property"].startswith("--raise-")]
    assert not spelled, (
        f"{len(spelled)} lifts write their own geometry rather than naming a --raise-* "
        f"height:\n  "
        + "\n  ".join(f"{s['said']} — {s['property']}: {s['value']}" for s in spelled)
    )
    raw = [s for s in lifted if "var(--shade)" not in s["value"]]
    assert not raw, (
        f"{len(raw)} heights are cast in a colour of their own rather than in --shade, "
        f"so the dark scheme cannot answer for them:\n  "
        + "\n  ".join(f"{s['said']} — {s['property']}: {s['value']}" for s in raw)
    )
    light = page.evaluate(PAINTED_SHADE)
    page.close()

    dark = open_page(browser, serve(LONG_PAGE), color_scheme="dark")
    shade = dark.evaluate(PAINTED_SHADE)
    assert shade.strip() and shade.strip() != light.strip(), (
        f"both schemes cast their shadows in {shade!r}, so routing them through a token "
        f"bought the dark page nothing it did not already have"
    )


def test_authored_label_room_keeps_toolbar_still_before_runtime(
    browser, serve, subtests
):
    """Labels and numeric readouts hold their space from authored paint to completion."""
    source = leaf_page(
        "Playback",
        """<h1>Playback</h1>
<div id="toolbar">
  <button id="playback" class="button" data-room="Play&#10;Pause&#10;Resume&#10;Replay">
    <span>Play</span>
  </button>
  <label id="speed">Speed <select><option>1×</option><option>0.5×</option></select></label>
  <span id="status" role="status"
        data-room="Ready to compare.&#10;Playing.&#10;Paused.&#10;Finished. Replay to compare again.">
    <span>Ready to compare.</span>
  </span>
</div>
<div id="timeline-row">
  <input id="timeline" type="range" min="0" max="1200" value="0" aria-label="Timeline">
  <output id="time" data-room="1200 / 1200ms"><span>0 / 1200ms</span></output>
</div>
<p id="following">The comparison stays beneath the controls.</p>
<script type="module">
const button = document.querySelector('#playback');
const status = document.querySelector('#status > span');
const states = [
  ['Pause', 'Playing.', 20], ['Resume', 'Paused.', 300],
  ['Replay', 'Finished. Replay to compare again.', 1200], ['Play', 'Ready to compare.', 0]
];
let next = 0;
button.addEventListener('click', () => {
  const [label, message, time] = states[next++ % states.length];
  button.firstElementChild.textContent = label;
  status.textContent = message;
  document.querySelector('#timeline').value = time;
  document.querySelector('#time > span').textContent = `${time} / 1200ms`;
});
button.dataset.connected = '';
</script>""",
        head="""<style>
#toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
#speed { white-space: nowrap; }
#timeline-row { display: flex; align-items: center; gap: 12px; }
#timeline { flex: 1; min-inline-size: 0; }
#time { font-variant-numeric: tabular-nums; }
</style>""",
    )
    boot = []
    page = browser.new_page(viewport={"width": 390, "height": 900})
    page.route("**/leaf.js", lambda route: boot.append(route))
    geometry = """() => Object.fromEntries(
      ['playback', 'speed', 'status', 'timeline', 'time', 'following'].map(id =>
        [id, document.getElementById(id).getBoundingClientRect().toJSON()]))"""
    try:
        with page.expect_request("**/leaf.js"):
            page.goto(serve(source), wait_until="commit")
        displayed(page)
        assert boot, "the positive control did not hold runtime startup"
        before_startup = page.evaluate(geometry)
        boot.pop().continue_()
        wait_until_ready(page)
        expect(page.locator("#playback")).to_have_attribute("data-connected", "")
        assert page.evaluate(geometry) == before_startup
        for width in (390, 900):
            with subtests.test(width=width):
                page.set_viewport_size({"width": width, "height": 900})
                before = page.evaluate(geometry)
                button = page.get_by_role("button", name="Play", exact=True)
                button.click()
                expect(
                    page.get_by_role("button", name="Pause", exact=True)
                ).to_be_focused()
                assert page.evaluate(geometry) == before
                page.keyboard.press("Space")
                expect(
                    page.get_by_role("button", name="Resume", exact=True)
                ).to_be_focused()
                assert page.evaluate(geometry) == before
                page.keyboard.press("Enter")
                expect(
                    page.get_by_role("button", name="Replay", exact=True)
                ).to_be_focused()
                expect(page.locator("#status")).to_have_text(
                    "Finished. Replay to compare again."
                )
                expect(page.locator("#time")).to_have_text("1200 / 1200ms")
                assert page.evaluate(geometry) == before
                if width == 900:
                    assert page.locator("#status > span").evaluate(
                        "el => el.scrollWidth <= el.clientWidth"
                    ), "the status was clipped despite room for its full wording"
                page.keyboard.press("Enter")
                expect(
                    page.get_by_role("button", name="Play", exact=True)
                ).to_be_focused()
                assert page.evaluate(geometry) == before
    finally:
        for route in boot:
            route.continue_()
        page.unroute_all(behavior="wait")
