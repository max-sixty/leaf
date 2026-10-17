"""How theme tokens and the device shape the chrome: motion inputs and preference, panel
default width, elevation, coarse-pointer aims, safe areas, and phone-width wrapping."""

import pytest
from leaf.render_checks import wait_until_ready
from playwright.sync_api import expect
from render_cases_layout import UNBREAKABLE_PAGE
from render_harness import (
    LONG_PAGE,
    leaf_page,
    open_page,
    page_comment,
    panel_settled,
    resized,
    write,
)

from browser.controls import (
    _touch_drag,
)

pytestmark = pytest.mark.shifts_unsurveyed


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
      const cue = document.createElement('div');
      cue.className = 'lf-msg flash';
      const arrival = document.createElement('button');
      arrival.className = 'lf-margin-entry';
      arrival.dataset.lfAgentArrival = '1';
      chrome.append(cue, arrival);
      const cssFlash = getComputedStyle(cue).animationDuration;
      const cssArrival = getComputedStyle(arrival).animationDuration;
      const cssFold = getComputedStyle(document.querySelector('lf-old')).transitionDuration;
      const {flashDuration, agentArrivalDuration} = await window.__lfCheckApi();
      const animation = owner.backgroundFlash(document.querySelector('#subject'), flashDuration());
      const played = animation.effect.getTiming().duration;
      animation.finish();
      cue.remove(); arrival.remove();
      return {cssFlash, cssArrival, cssFold, played,
        fold: owner.foldDuration(), agent: agentArrivalDuration()};
    }""")
    assert result == {
        "cssFlash": "0.73s",
        "cssArrival": "0.91s",
        "cssFold": "0.17s",
        "played": 730,
        "fold": 170,
        "agent": 910,
    }


def test_a_panel_uses_the_stylesheet_default_until_the_user_draws_it(browser, serve):
    """The default is a theme input; a retained user choice is a separate authority."""
    source = leaf_page(
        "Panel width input",
        "<h1>Panel width input</h1><p>Keep the chosen edge.</p>",
        head="<style>:root {--lf-thread-panel-default-width:calc(30rem + 16px)}</style>",
    )
    page = open_page(browser, serve(source))
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    panel = page.locator(".lf-thread-panel")
    initial = page.evaluate("""() => parseFloat(getComputedStyle(document.documentElement)
      .getPropertyValue('--lf-thread-panel-default-width'))""")
    assert initial > 480
    assert panel.bounding_box()["width"] == pytest.approx(initial)
    page.evaluate("""() => {
      document.documentElement.style.setProperty('--lf-thread-panel-default-width','508px');
      dispatchEvent(new Event('resize'));
    }""")
    assert panel.bounding_box()["width"] == pytest.approx(508)
    edge = panel.get_by_role("separator")
    edge.focus()
    edge.press("ArrowLeft")
    assert panel.bounding_box()["width"] == pytest.approx(532)
    page.evaluate("""() => {
      document.documentElement.style.setProperty('--lf-thread-panel-default-width','600px');
      dispatchEvent(new Event('resize'));
    }""")
    assert panel.bounding_box()["width"] == pytest.approx(532)
    page.reload()
    wait_until_ready(page)
    assert panel.bounding_box()["width"] == pytest.approx(532)


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


def test_coarse_pointer_chrome_gives_its_compact_controls_humane_aims(browser, serve):
    """Touch keeps Leaf's compact paint while expanding the boxes a finger works."""
    html = LONG_PAGE.replace(
        "<title>long</title>",
        '<title>long</title><meta name="lf-review" content="sign-off">',
    )
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    page = open_page(browser, serve(html, comments=1), context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches"), (
        "the touch fixture never reached Leaf's coarse-pointer rules"
    )

    # A phone's row holds Threads and More; Approval leads More.
    primary = page.locator(".lf-threads-toggle, .lf-banner-more")
    expect(primary).to_have_count(2)
    for index in range(primary.count()):
        box = primary.nth(index).bounding_box()
        assert box["width"] >= 43.9 and box["height"] >= 43.9, (
            f"a primary touch aim stayed at {box}"
        )

    page.locator(".lf-threads-toggle").tap()
    panel_settled(page)
    # The shortcut bar is not among them: a touch device has no keyboard to advertise, so
    # the whole line stands down and takes its More control with it.
    expect(page.locator(".lf-shortcut-bar")).to_be_hidden()
    compact = page.locator(
        ".lf-thread-panel .lf-react:visible, .lf-thread-panel-head .lf-btn:visible"
    )
    assert compact.count() >= 1, "the covering panel exposed no compact touch controls"
    for index in range(compact.count()):
        box = compact.nth(index).bounding_box()
        assert box["width"] >= 43.9 and box["height"] >= 43.9, (
            f"a compact panel control kept a mouse-sized aim: {box}"
        )
    page.get_by_role("button", name="Close threads").tap()
    panel_settled(page, open=False)

    # The page comment's empty action and Send both keep a finger-sized aim.
    page_comment(page)
    for words in ("", "Review this page"):
        write(page.locator(".lf-page-comment-card leaf-text"), words)
        action = page.locator(".lf-page-comment-card .lf-general button:visible")
        expect(action).to_be_visible()
        box = action.bounding_box()
        assert box["width"] >= 43.9 and box["height"] >= 43.9, (
            f"the page comment card's action kept a mouse-sized aim: {box}"
        )
    page.keyboard.press("Escape")
    expect(page.locator(".lf-page-comment-card")).to_be_hidden()

    # Across the covering boundary the banner fits the same touch aims. Its toolbar and
    # a keyboard ring remain inside the derived edge rather than centred through it.
    for width in (840, 841, 900, 1200, 1440):
        resized(page, width, 844)
        page.locator(".lf-threads-toggle").focus()
        geometry = page.locator(".lf-threads-toggle").evaluate(
            """control => {
                  const banner = control.closest('.lf-banner').getBoundingClientRect();
                  const toolbar = control.parentElement.getBoundingClientRect();
                  const box = control.getBoundingClientRect();
                  const style = getComputedStyle(control);
                  const outset = parseFloat(style.outlineWidth) +
                    parseFloat(style.outlineOffset);
                  return {banner: {top: banner.top, bottom: banner.bottom},
                          toolbar: {top: toolbar.top, bottom: toolbar.bottom},
                          ring: {top: box.top - outset, bottom: box.bottom + outset}};
                }"""
        )
        for item in ("toolbar", "ring"):
            # Centered flex boxes round to device pixels independently of the
            # banner's stated height; subpixel overhang is not a clipped aim.
            assert (
                geometry[item]["top"] >= geometry["banner"]["top"] - 1
                and geometry[item]["bottom"] <= geometry["banner"]["bottom"] + 1
            ), f"the wide coarse {item} escaped its banner at {width}px: {geometry}"

    # The browser's root is Leaf's page scrollport, and native touch beginning in
    # fixed chrome reaches it. The row itself has nothing to travel along: what it
    # cannot hold is behind its menu, so a finger dragged sideways across it moves
    # nothing rather than uncovering a control that was hiding off the edge.
    cdp = context.new_cdp_session(page)
    resized(page, 390, 700)
    page.wait_for_function(
        "() => getComputedStyle(document.scrollingElement).overflowY !== 'hidden'"
    )
    actions = page.locator(".lf-banner-actions")
    page.evaluate(
        """async () => {
              const toolbar = await window.__lfCheckApi();
              for (let i = 0; i < 3; i++) {
                const button = document.createElement('button');
                button.className = 'lf-ui lf-btn';
                button.textContent = `Secondary touch destination ${i + 1}`;
                toolbar.registerBannerControl({
                  key: `test-touch-secondary-${i}`,
                  control: button,
                  rank: toolbar.BANNER_CONTROL_RANK.blanket + (i + 1) / 10,
                  row: { label: button.textContent, group: "page" },
                });
              }
            }"""
    )
    crowded = actions.evaluate(
        "el => ({shown: el.clientWidth, needed: el.scrollWidth,"
        " folded: document.querySelector('.lf-banner-menu').children.length})"
    )
    assert crowded["folded"] >= 3 and crowded["shown"] == crowded["needed"], (
        f"the crowded touch row did not fold what it could not hold: {crowded}"
    )
    point = actions.bounding_box()
    x = point["x"] + point["width"] / 2
    y = point["y"] + point["height"] / 2
    page.evaluate("() => { document.scrollingElement.scrollTop = 200; }")
    _touch_drag(cdp, x, y, dy=-160)
    page.wait_for_function("() => document.scrollingElement.scrollTop > 200")
    vertical = page.evaluate(
        "() => ({toolbar: document.querySelector('.lf-banner-actions').scrollLeft,"
        " page: document.scrollingElement.scrollTop,"
        " overflow: getComputedStyle(document.scrollingElement).overflowY})"
    )
    assert (
        vertical["toolbar"] == 0
        and vertical["page"] > 200
        and vertical["overflow"] != "hidden"
    ), f"a vertical touch over the row never reached the page: {vertical}"
    page.evaluate("() => { document.scrollingElement.scrollTop = 200; }")
    _touch_drag(cdp, x, y, dx=-160)
    horizontal = page.evaluate(
        "() => ({toolbar: document.querySelector('.lf-banner-actions').scrollLeft,"
        " page: document.scrollingElement.scrollTop})"
    )
    assert horizontal["toolbar"] == 0, (
        f"the row still had a strip of itself to drag along: {horizontal}"
    )

    resized(page, 1200, 700)
    status = page.locator(".lf-banner-status").bounding_box()
    page.evaluate("() => { document.scrollingElement.scrollTop = 200; }")
    _touch_drag(
        cdp,
        status["x"] + status["width"] / 2,
        status["y"] + status["height"] / 2,
        dy=-160,
    )
    page.wait_for_function("() => document.scrollingElement.scrollTop > 200")
    assert page.evaluate("() => document.scrollingElement.scrollTop") > 200, (
        "the status half of the fixed banner remained a dead touch-scroll strip"
    )


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
    """The bottom bar keeps the inset tokens stated by the stylesheet: it stands on the
    window's foot, grows by the bottom inset, and holds its hints inside the side insets.
    The insets are stated on the root, where the band's own height reads them."""
    page = open_page(browser, serve(LONG_PAGE))
    resized(page, 500, 700)
    insets = {"left": 17, "right": 31, "bottom": 23}
    page.evaluate(
        """insets => {
          for (const [side, value] of Object.entries(insets))
            document.documentElement.style.setProperty(`--lf-safe-${side}`, `${value}px`);
        }""",
        insets,
    )
    page.locator(".lf-threads-toggle").click()
    panel_settled(page)
    expect(page.locator(".lf-shortcut-bar")).to_be_visible()
    boxes = page.evaluate(
        """() => {
          const rect = node => {
            const r = node.getBoundingClientRect();
            return {left: r.left, right: r.right, top: r.top, bottom: r.bottom};
          };
          const bar = document.querySelector('.lf-shortcut-bar');
          const hints = [...bar.querySelectorAll(".lf-shortcut:not([data-lf-off-line])")];
          return {shortcut_bar: rect(bar), first: rect(hints[0]),
                  width: innerWidth, height: innerHeight};
        }"""
    )
    band = boxes["shortcut_bar"]
    assert abs(band["bottom"] - boxes["height"]) < 1, boxes
    assert abs(band["bottom"] - band["top"] - (44 + insets["bottom"])) < 1, boxes
    assert boxes["first"]["left"] >= 18 + insets["left"] - 1, boxes
    assert boxes["first"]["bottom"] <= boxes["height"] - insets["bottom"] + 1, boxes


def test_the_page_comment_card_keeps_its_action_inside_the_side_safe_area(
    browser, serve
):
    """The page comment card stays inside both unsafe side edges, on a phone where it
    spans the window and beside it where it hangs from its control."""
    page = open_page(browser, serve(LONG_PAGE))
    page.evaluate(
        """() => {
          document.body.style.setProperty('--lf-safe-right', '31px');
          document.body.style.setProperty('--lf-safe-left', '23px');
        }"""
    )
    for width in (500, 420):
        resized(page, width, 700)
        page_comment(page)
        expect(
            page.locator(".lf-page-comment-card .lf-general button:visible")
        ).to_be_visible()
        boxes = page.evaluate(
            """() => {
              const rect = selector => {
                const r = document.querySelector(selector).getBoundingClientRect();
                return {left: r.left, right: r.right, top: r.top, bottom: r.bottom};
              };
              return {card: rect('.lf-page-comment-card'),
                      action: rect('.lf-page-comment-card .lf-general button:not([hidden])'),
                      viewport: {width: innerWidth, height: innerHeight}};
            }"""
        )
        assert boxes["action"]["right"] <= boxes["viewport"]["width"] - 31 + 1, (
            f"the page comment card's action sat under the side safe area at {width}px: "
            f"{boxes}"
        )
        assert boxes["card"]["left"] >= 23 - 1, (
            f"the page comment card sat under the left safe area at {width}px: {boxes}"
        )
        page.keyboard.press("Escape")
        expect(page.locator(".lf-page-comment-card")).to_be_hidden()

    # The banner declares its face once; the page comment card follows that face
    # even when its declaration changes independently of the viewport width.
    resized(page, 1000, 700)
    page.evaluate(
        "document.documentElement.style.setProperty('--lf-banner-face', 'phone')"
    )
    page_comment(page)
    box = page.locator(".lf-page-comment-card").bounding_box()
    assert box["x"] == pytest.approx(23 + 8)
    assert box["x"] + box["width"] == pytest.approx(1000 - 31 - 8)


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
  const found = [];
  const eaten = new Set();
  const eat = (sheet) => {
    if (!sheet || eaten.has(sheet)) return;
    eaten.add(sheet);
    let list;
    try { list = sheet.cssRules; } catch { return; }  // a sheet from another origin
    const walk = (from) => {
      for (const rule of from) {
        const named = rule.style ? [...rule.style] : [];
        const lifted = (name) => ['box-shadow', 'filter'].includes(name) || name.startsWith('--');
        for (const property of named.filter(lifted)) {
          const value = rule.style.getPropertyValue(property).trim();
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
    the next one from writing a fifteenth. The `--raise-*` tokens (theme.css, beside
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
